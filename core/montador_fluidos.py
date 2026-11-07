"""Os blocos de mecânica dos fluidos do montador de fórmulas.

A parte de fluidos usa o mesmo motor da parte de materiais, com outro fio em fila: a **linha** sai do
fluido e vai somando a perda de carga trecho a trecho, como a seção soma esforços. Quem verifica lê a
linha no fim. Os blocos de equação, como empuxo ou Manning, são igualdades: não têm limite, e a letra
pedida é a que fecha a conta. A linha é em série, com a mesma vazão em todos os trechos.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

import sympy as sp

from core import montador_blocos as mb
from core import montador_grandezas as g
from core.montador_blocos import (
    CONDICAO,
    FLUIDOS,
    LINHA,
    Bloco,
    Condicao,
    Contexto,
    ErroDeBloco,
    Opcao,
    Porta,
)
from core.montador_funcoes import RE_LAMINAR, RE_TURBULENTO, AtritoDarcy
from core.montador_secoes import Validade

ZERO = sp.S.Zero
INFORMAR = "Informar as propriedades"
RUGOSIDADE_INFORMADA = "Informar a rugosidade"
ACIMA_DO_NIVEL = "Bomba acima do nível do líquido"
ABAIXO_DO_NIVEL = "Bomba abaixo do nível do líquido"
SUCCOES = (ACIMA_DO_NIVEL, ABAIXO_DO_NIVEL)

#: ρ em kg/m³, μ em Pa·s e pressão de vapor absoluta em Pa. Valores típicos de tabela.
FLUIDOS_TIPICOS: dict[str, tuple[float, float, float | None]] = {
    "Água a 20 °C": (998.0, 1.002e-3, 2339.0),
    "Água a 40 °C": (992.1, 6.53e-4, 7384.0),
    "Água a 60 °C": (983.3, 4.67e-4, 19940.0),
    "Água a 80 °C": (971.8, 3.55e-4, 47390.0),
    "Ar a 20 °C": (1.204, 1.825e-5, None),
    "Etanol a 20 °C": (789.0, 1.2e-3, 5800.0),
    "Glicerina a 20 °C": (1261.0, 1.519, None),
    "Óleo de motor a 40 °C": (876.0, 0.2177, None),
    "Óleo hidráulico ISO VG 46 a 40 °C": (870.0, 0.040, None),
}
#: Rugosidade absoluta em metros. Tubo novo: com o tempo, ela cresce.
RUGOSIDADES: dict[str, float] = {
    "Aço comercial": 0.045e-3,
    "Aço galvanizado": 0.15e-3,
    "Ferro fundido": 0.26e-3,
    "PVC ou plástico": 1.5e-6,
    "Cobre": 1.5e-6,
    "Concreto": 1.5e-3,
}


@dataclass(frozen=True)
class Trecho:
    rotulo: str
    d: sp.Expr
    velocidade: sp.Expr
    reynolds: sp.Expr
    atrito: sp.Expr
    perda: sp.Expr


@dataclass(frozen=True)
class Linha:
    """O fluido e a perda de carga somada até aqui. Vai de bloco em bloco, como a seção."""

    rho: sp.Expr
    mu: sp.Expr
    pv: sp.Expr
    gravidade: sp.Expr
    vazao: sp.Expr | None = None
    trechos: tuple[Trecho, ...] = ()
    perda: sp.Expr = ZERO
    validade: tuple[Validade, ...] = ()


def _linha(c: Contexto) -> Linha:
    linha = c.ligados.get("entrada")
    if linha is None:
        raise ErroDeBloco("Ligue um fluido aqui.")
    return linha


def _fluido(c: Contexto) -> dict[str, Any]:
    nome = c.opcoes.get("fluido", "Água a 20 °C")
    if nome in FLUIDOS_TIPICOS:
        rho, mu, pv = FLUIDOS_TIPICOS[nome]
        fonte = f"Tabela: {nome}"
        c.padrao(g.RHO, rho, fonte)
        c.padrao(g.MU, mu, fonte)
        if pv is not None:
            c.padrao(g.P_VAPOR, pv, fonte)
    return {"saida": Linha(c.letra(g.RHO), c.letra(g.MU), c.letra(g.P_VAPOR), c.letra(g.GRAVIDADE))}


def _trecho(c: Contexto) -> dict[str, Any]:
    linha = _linha(c)
    d, comprimento = c.letra(g.D_TUBO), c.letra(g.L_TUBO)
    material = c.opcoes.get("tubo", "Aço comercial")
    if material in RUGOSIDADES:
        c.padrao(g.EPSILON, RUGOSIDADES[material], f"Tabela: {material}")
    rugosidade = c.letra(g.EPSILON)
    vazao = linha.vazao if linha.vazao is not None else c.letra(g.VAZAO_Q, fixa=True)
    velocidade = 4 * vazao / (sp.pi * d**2)
    reynolds = linha.rho * velocidade * d / linha.mu
    relativa = rugosidade / d
    atrito = AtritoDarcy(reynolds, relativa)
    perda = atrito * comprimento / d * velocidade**2 / (2 * linha.gravidade)
    numero = len(linha.trechos) + 1
    trecho = Trecho(f"trecho {numero}", d, velocidade, reynolds, atrito, perda)
    transicao = Validade(
        (reynolds - RE_LAMINAR) * (reynolds - RE_TURBULENTO),
        "Reynolds caiu na transição, entre 2300 e 4000: lá o fator de atrito não é definido, e a "
        "perda é só uma estimativa.",
        restringe=False,
    )
    rugoso = Validade(
        sp.Rational(1, 20) - relativa,
        "ε/D passou de 0,05: acima disso o ábaco de Moody não vale.",
        restringe=False,
    )
    return {
        "saida": replace(
            linha,
            vazao=vazao,
            trechos=(*linha.trechos, trecho),
            perda=linha.perda + perda,
            validade=(*linha.validade, transicao, rugoso),
        )
    }


def _perda_local(c: Contexto) -> dict[str, Any]:
    linha = _linha(c)
    if not linha.trechos:
        raise ErroDeBloco("Ponha um trecho de tubo antes: a perda usa a velocidade dele.")
    velocidade = linha.trechos[-1].velocidade
    perda = c.letra(g.K_LOCAL) * velocidade**2 / (2 * linha.gravidade)
    return {"saida": replace(linha, perda=linha.perda + perda)}


def _dados_da_linha(linha: Linha) -> tuple[tuple[str, sp.Expr], ...]:
    dados: list[tuple[str, sp.Expr]] = []
    for i, trecho in enumerate(linha.trechos, start=1):
        dados.append((f"V_{{{i}}}", trecho.velocidade))
        dados.append((f"Re_{{{i}}}", trecho.reynolds))
    return tuple(dados)


def _com_perda(c: Contexto) -> Linha:
    linha = _linha(c)
    if not linha.trechos:
        raise ErroDeBloco("Ponha um trecho de tubo antes deste bloco.")
    return linha


def _carga(c: Contexto) -> dict[str, Any]:
    linha = _com_perda(c)
    condicao = Condicao(
        "Perda de carga",
        "Perda de carga",
        linha.perda,
        c.letra(g.H_DISP),
        "h_{L}",
        "",
        _dados_da_linha(linha),
        linha.validade,
    )
    return {"condicao": [condicao]}


def _altura_do_sistema(c: Contexto, linha: Linha) -> sp.Expr:
    return c.letra(g.H_EST) + c.letra(g.DELTA_P) / (linha.rho * linha.gravidade) + linha.perda


def _altura_bomba(c: Contexto) -> dict[str, Any]:
    linha = _com_perda(c)
    condicao = Condicao(
        "Altura da bomba",
        "Altura da bomba",
        _altura_do_sistema(c, linha),
        c.letra(g.H_BOMBA),
        "H_{sist}",
        "",
        _dados_da_linha(linha),
        linha.validade,
    )
    return {"condicao": [condicao]}


def _potencia(c: Contexto) -> dict[str, Any]:
    linha = _com_perda(c)
    altura = _altura_do_sistema(c, linha)
    esquerda = linha.rho * linha.gravidade * linha.vazao * altura / c.letra(g.ETA)
    condicao = Condicao(
        "Potência no eixo",
        "Potência",
        esquerda,
        c.letra(g.P_MOTOR),
        "P_{eixo}",
        "",
        _dados_da_linha(linha),
        linha.validade,
    )
    return {"condicao": [condicao]}


def _npsh(c: Contexto) -> dict[str, Any]:
    linha = _com_perda(c)
    disponivel = (c.letra(g.P_ATM) - linha.pv) / (linha.rho * linha.gravidade)
    requerido = c.letra(g.NPSH_R)
    altura = c.letra(g.Z_SUCCAO)
    if c.opcoes.get("succao", ACIMA_DO_NIVEL) == ACIMA_DO_NIVEL:
        esquerda = requerido + altura + linha.perda
        direita = disponivel
    else:
        esquerda = requerido + linha.perda
        direita = disponivel + altura
    condicao = Condicao(
        "NPSH na sucção",
        "NPSH",
        esquerda,
        direita,
        "NPSH_{r} + z_{s} + h_{L}",
        "",
        _dados_da_linha(linha),
        linha.validade,
    )
    return {"condicao": [condicao]}


def _velocidade(c: Contexto) -> dict[str, Any]:
    linha = _com_perda(c)
    limite = c.letra(g.V_ADM)
    condicoes = [
        Condicao(
            f"Velocidade no {t.rotulo}",
            "Velocidade",
            t.velocidade,
            limite,
            "V",
            t.rotulo,
            (("Re", t.reynolds),),
            linha.validade,
        )
        for t in linha.trechos
    ]
    return {"condicao": condicoes}


def _equacao(nome: str, esquerda: sp.Expr, direita: sp.Expr, letra: str) -> dict[str, Any]:
    return {"condicao": [Condicao(nome, nome, esquerda, direita, letra, "", igualdade=True)]}


def _coluna(c: Contexto) -> dict[str, Any]:
    linha = _linha(c)
    pressao = c.letra(g.P_REF) + linha.rho * linha.gravidade * c.letra(g.H_PROF)
    return _equacao("Pressão na profundidade", pressao, c.letra(g.P_FUNDO), "p_{h}")


def _forca_plana(c: Contexto) -> dict[str, Any]:
    linha = _linha(c)
    forca = linha.rho * linha.gravidade * c.letra(g.H_CENTRO) * c.letra(g.A_SUPERF)
    return _equacao("Força na superfície plana", forca, c.letra(g.F_RESULT), "F_{R}")


def _empuxo(c: Contexto) -> dict[str, Any]:
    linha = _linha(c)
    forca = linha.rho * linha.gravidade * c.letra(g.V_DESLOC)
    return _equacao("Empuxo", forca, c.letra(g.EMPUXO), "F_{e}")


def _arrasto(c: Contexto) -> dict[str, Any]:
    linha = _linha(c)
    forca = c.letra(g.C_ARRASTO) * linha.rho * c.letra(g.V_REL) ** 2 * c.letra(g.A_FRONTAL) / 2
    return _equacao("Arrasto", forca, c.letra(g.F_ARRASTO), "F_{D}")


def _medidor(c: Contexto) -> dict[str, Any]:
    linha = _linha(c)
    d, garganta = c.letra(g.D_TUBO), c.letra(g.D_ORIFICIO)
    area = sp.pi * garganta**2 / 4
    vazao = (
        c.letra(g.C_DESCARGA)
        * area
        * sp.sqrt(2 * c.letra(g.DELTA_P) / linha.rho)
        / sp.sqrt(1 - (garganta / d) ** 4)
    )
    c.hipoteses.append("No medidor, C_d já inclui as perdas: vale o da norma do medidor.")
    resultado = _equacao("Vazão no medidor", vazao, c.letra(g.VAZAO_Q), "Q")
    resultado["condicao"][0] = replace(
        resultado["condicao"][0],
        validade=(
            Validade(
                d - garganta,
                "O orifício precisa ser menor que o tubo.",
            ),
        ),
    )
    return resultado


def _manning(c: Contexto) -> dict[str, Any]:
    largura, profundidade = c.letra(g.B_CANAL), c.letra(g.Y_CANAL)
    area = largura * profundidade
    raio = area / (largura + 2 * profundidade)
    vazao = area * raio ** sp.Rational(2, 3) * sp.sqrt(c.letra(g.DECLIVIDADE)) / c.letra(g.MANNING)
    c.hipoteses.append("Canal retangular em regime uniforme, com n de Manning em unidades do SI.")
    return _equacao("Vazão no canal (Manning)", vazao, c.letra(g.VAZAO_Q), "Q")


def _golpe(c: Contexto) -> dict[str, Any]:
    linha = _linha(c)
    pressao = linha.rho * c.letra(g.CELERIDADE) * c.letra(g.DELTA_V)
    c.hipoteses.append(
        "Joukowsky vale para fechamento rápido: menor que o tempo de ida e volta da onda."
    )
    return _equacao("Golpe de aríete", pressao, c.letra(g.P_GOLPE), "\\Delta p_{g}")


_ENTRADA = Porta("entrada", "Fluido", LINHA)
_SAIDA = Porta("saida", "Linha", LINHA)
_SAIDA_CONDICAO = Porta("condicao", "Condição", CONDICAO)


def _verificacao(
    chave: str,
    nome: str,
    dica: str,
    formula: str,
    calcular: Any,
    opcoes: tuple[Opcao, ...] = (),
) -> Bloco:
    return Bloco(
        chave,
        nome,
        mb.GRUPO_VERIFICACAO,
        dica,
        formula,
        (_ENTRADA,),
        (_SAIDA_CONDICAO,),
        calcular,
        opcoes,
        dominio=FLUIDOS,
    )


def _bloco_equacao(chave: str, nome: str, dica: str, formula: str, calcular: Any) -> Bloco:
    return Bloco(
        chave,
        nome,
        mb.GRUPO_EQUACOES,
        dica,
        formula,
        (_ENTRADA,),
        (_SAIDA_CONDICAO,),
        calcular,
        dominio=FLUIDOS,
    )


BLOCOS_FLUIDOS: tuple[Bloco, ...] = (
    Bloco(
        "fluido",
        "Fluido",
        mb.GRUPO_FLUIDO,
        "Dá o começo da fila: massa específica, viscosidade e pressão de vapor.",
        "ρ · μ · p_v",
        (),
        (Porta("saida", "Fluido", LINHA),),
        _fluido,
        (
            Opcao(
                "fluido",
                "Fluido",
                "Valores típicos de tabela. Para outra condição, escolha informar as propriedades.",
                (INFORMAR, *FLUIDOS_TIPICOS),
                "Água a 20 °C",
            ),
        ),
        dominio=FLUIDOS,
    ),
    Bloco(
        "trecho",
        "Trecho de tubo",
        mb.GRUPO_TUBULACAO,
        "Soma a perda de Darcy-Weisbach, com f de Colebrook no turbulento e 64/Re no laminar.",
        "h_f = f·(L/D)·V²/(2·g)",
        (Porta("entrada", "Fluido", LINHA),),
        (_SAIDA,),
        _trecho,
        (
            Opcao(
                "tubo",
                "Material do tubo",
                "Dá a rugosidade de tubo novo. Tubo usado costuma ter rugosidade maior.",
                (*RUGOSIDADES, RUGOSIDADE_INFORMADA),
                "Aço comercial",
            ),
        ),
        numerar=True,
        dominio=FLUIDOS,
    ),
    Bloco(
        "perda_local",
        "Perdas localizadas",
        mb.GRUPO_TUBULACAO,
        "Soma K·V²/(2·g) com a velocidade do trecho anterior: curvas, registros, entrada e saída.",
        "h_k = K·V²/(2·g)",
        (Porta("entrada", "Linha", LINHA),),
        (_SAIDA,),
        _perda_local,
        numerar=True,
        dominio=FLUIDOS,
    ),
    _verificacao(
        "carga",
        "Carga disponível",
        "A linha sem bomba: a perda precisa caber no desnível.",
        "h_L ≤ H_d",
        _carga,
    ),
    _verificacao(
        "altura_bomba",
        "Altura da bomba",
        "O que a bomba precisa entregar: altura estática, pressão e perdas.",
        "H_est + Δp/(ρ·g) + h_L ≤ H_b",
        _altura_bomba,
    ),
    _verificacao(
        "potencia_bomba",
        "Potência da bomba",
        "A potência no eixo com o rendimento da bomba.",
        "ρ·g·Q·H/η ≤ P_m",
        _potencia,
    ),
    _verificacao(
        "npsh",
        "NPSH",
        "Cavitação: o NPSH disponível precisa passar do requerido. Ligue só a linha de sucção.",
        "NPSH_d ≥ NPSH_r",
        _npsh,
        (
            Opcao(
                "succao",
                "Posição da bomba",
                "Acima do nível, a altura de sucção tira do NPSH. Abaixo, ela soma.",
                SUCCOES,
                ACIMA_DO_NIVEL,
            ),
        ),
    ),
    _verificacao(
        "velocidade",
        "Velocidade máxima",
        "Limite de velocidade em cada trecho da linha.",
        "V = 4·Q/(π·D²) ≤ V_adm",
        _velocidade,
    ),
    _bloco_equacao(
        "coluna",
        "Pressão na profundidade",
        "Fluido parado: a pressão cresce com a profundidade.",
        "p_h = p_0 + ρ·g·h",
        _coluna,
    ),
    _bloco_equacao(
        "forca_plana",
        "Força em superfície plana",
        "Resultante da pressão numa comporta ou parede plana.",
        "F_R = ρ·g·h_c·A",
        _forca_plana,
    ),
    _bloco_equacao(
        "empuxo",
        "Empuxo",
        "Princípio de Arquimedes.",
        "F_e = ρ·g·V_d",
        _empuxo,
    ),
    _bloco_equacao(
        "arrasto",
        "Arrasto",
        "Força do escoamento sobre uma peça.",
        "F_D = C_D·ρ·V²·A/2",
        _arrasto,
    ),
    _bloco_equacao(
        "medidor",
        "Orifício ou venturi",
        "Vazão pela queda de pressão no medidor.",
        "Q = C_d·A·√(2·Δp/ρ)/√(1−β⁴)",
        _medidor,
    ),
    _bloco_equacao(
        "golpe",
        "Golpe de aríete",
        "Sobrepressão de Joukowsky no fechamento rápido.",
        "Δp = ρ·a·ΔV",
        _golpe,
    ),
    Bloco(
        "manning",
        "Canal (Manning)",
        mb.GRUPO_EQUACOES,
        "Canal retangular em regime uniforme. Não precisa do fluido.",
        "Q = A·R^(2/3)·√S/n",
        (),
        (_SAIDA_CONDICAO,),
        _manning,
        dominio=FLUIDOS,
    ),
)

mb.registrar(BLOCOS_FLUIDOS)


def resumo_da_linha(linha: Linha) -> Mapping[str, sp.Expr]:
    """Para o fio da linha no inspetor."""
    dados: dict[str, sp.Expr] = {}
    for i, t in enumerate(linha.trechos, start=1):
        dados[f"V{i}"] = t.velocidade
        dados[f"Re{i}"] = t.reynolds
        dados[f"f{i}"] = t.atrito
        dados[f"h{i}"] = t.perda
    dados["h_L"] = linha.perda
    return dados
