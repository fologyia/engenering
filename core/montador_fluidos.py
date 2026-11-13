"""Os blocos de mecânica dos fluidos do montador de fórmulas.

A parte de fluidos usa o mesmo motor da parte de materiais, com outro fio em fila: a **linha** sai do
fluido e vai somando a perda de carga trecho a trecho, como a seção soma esforços. Quem verifica lê a
linha no fim. Os blocos de equação, como empuxo ou Manning, são igualdades: não têm limite, e a letra
pedida é a que fecha a conta. A linha é em série, com a mesma vazão em todos os trechos.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import sympy as sp
from fluids import piping as fpiping

from core import montador_blocos as mb
from core import montador_funcoes as fn
from core import montador_grandezas as g
from core import montador_propriedades as mp
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
from core.montador_funcoes import (
    RE_LAMINAR,
    RE_TURBULENTO,
    AtritoDarcy,
    CoeficienteOrificio,
    KCrane,
)
from core.montador_secoes import Validade

ZERO = sp.S.Zero
INFORMAR = "Informar as propriedades"
RUGOSIDADE_INFORMADA = "Informar a rugosidade"
ACIMA_DO_NIVEL = "Bomba acima do nível do líquido"
ABAIXO_DO_NIVEL = "Bomba abaixo do nível do líquido"
SUCCOES = (ACIMA_DO_NIVEL, ABAIXO_DO_NIVEL)
DIAMETRO_INFORMADO = "Informar o diâmetro"
PONTO_DE_OPERACAO = "Ponto de operação"
C_INFORMADO = "Coeficiente informado (C_d)"
ORIFICIO_CANTO = "Placa de orifício ISO 5167-2, tomadas de canto"
ORIFICIO_FLANGE = "Placa de orifício ISO 5167-2, tomadas de flange"
ORIFICIO_D = "Placa de orifício ISO 5167-2, tomadas a D e D/2"
VENTURI_USINADO = "Venturi clássico ISO 5167-4, convergente usinado"
VENTURI_FUNDIDO = "Venturi clássico ISO 5167-4, convergente fundido"
VENTURI_SOLDADO = "Venturi clássico ISO 5167-4, chapa soldada"
#: A ordem das tomadas é a de ``TOMADAS_DO_ORIFICIO``. O C do venturi é o da ISO 5167-4, 5.5.
ORIFICIOS = {ORIFICIO_CANTO: 0, ORIFICIO_FLANGE: 1, ORIFICIO_D: 2}
VENTURIS = {VENTURI_USINADO: 0.995, VENTURI_FUNDIDO: 0.984, VENTURI_SOLDADO: 0.985}
MEDIDORES = (C_INFORMADO, *ORIFICIOS, *VENTURIS)
#: Pressão crítica da água pela IAPWS, para os fluidos de tabela que são água.
P_CRITICA_DA_AGUA = 22.064e6
#: ρ₀ da IEC 60534-2-1: a água a 15 °C, em kg/m³.
RHO_0_IEC = 999.1

#: ρ em kg/m³, μ em Pa·s e pressão de vapor absoluta em Pa. A água foi conferida em duas tabelas
#: (roymech.org e engineeringtoolbox.com): saturação pela IAPWS. O resto são valores típicos.
FLUIDOS_TIPICOS: dict[str, tuple[float, float, float | None]] = {
    "Água a 20 °C": (998.2, 1.0016e-3, 2339.0),
    "Água a 40 °C": (992.2, 6.527e-4, 7385.0),
    "Água a 60 °C": (983.2, 4.660e-4, 19946.0),
    "Água a 80 °C": (971.8, 3.540e-4, 47414.0),
    "Ar a 20 °C": (1.204, 1.825e-5, None),
    "Etanol a 20 °C": (789.0, 1.2e-3, 5800.0),
    "Glicerina a 20 °C": (1261.0, 1.519, None),
    "Óleo de motor a 40 °C": (876.0, 0.2177, None),
    "Óleo hidráulico ISO VG 46 a 40 °C": (870.0, 0.040, None),
}
#: Os fluidos que a CoolProp calcula em qualquer temperatura da faixa deles.
#: Dos gases, os que ficam gás em temperatura ambiente: o metano faz as vezes do gás natural.
_GASES_DA_LINHA = ("Ar seco", "Nitrogênio", "Metano")
POR_TEMPERATURA: dict[str, mp.Fluido] = {
    f"{f.rotulo} pela temperatura (CoolProp)": f
    for f in mp.FLUIDOS
    if f.liquido or f.rotulo in _GASES_DA_LINHA
}
#: Os fluidos de tabela que são gás.
GASES_DE_TABELA = frozenset({"Ar a 20 °C"})
#: Rugosidade absoluta em metros, de tubo novo: com o tempo, ela cresce. Concreto varia de 0,3 a
#: 3 mm conforme o acabamento: 1,5 mm é o meio dessa faixa.
RUGOSIDADES: dict[str, float] = {
    "Aço comercial": 0.045e-3,
    "Aço galvanizado": 0.15e-3,
    "Ferro fundido": 0.26e-3,
    "PVC ou plástico": 1.5e-6,
    "Cobre": 1.5e-6,
    "Concreto": 1.5e-3,
}
#: K de peça aberta por inteiro, em excesso de carga, com a velocidade do tubo. Variam com o diâmetro
#: e o fabricante: são o valor típico de cada peça, para pré-dimensionar.
PECAS: dict[str, float] = {
    "Curva 90° padrão (R/D = 1)": 0.75,
    "Curva 90° raio longo (R/D = 1,5)": 0.45,
    "Curva 45° padrão": 0.35,
    "Curva 45° raio longo": 0.20,
    "Tê, passagem direta": 0.40,
    "Tê, saída lateral": 1.00,
    "Registro de gaveta aberto": 0.17,
    "Válvula de globo aberta": 6.0,
    "Válvula de esfera aberta": 0.05,
    "Válvula de retenção de portinhola": 2.0,
    "Entrada de canto vivo": 0.5,
    "Saída para reservatório": 1.0,
}


@dataclass(frozen=True)
class TuboComercial:
    rotulo: str
    familia: str  # o material da tabela de rugosidade
    externo_mm: float
    parede_mm: float
    serie: str = ""  # a linha do catálogo: Sch 40, Sch 80, PVC soldável

    @property
    def interno_m(self) -> float:
        return (self.externo_mm - 2.0 * self.parede_mm) / 1000.0


#: Diâmetro nominal (DN) e polegadas de cada NPS da tabela.
_NPS: tuple[tuple[float, int, str], ...] = (
    (0.5, 15, "1/2"),
    (0.75, 20, "3/4"),
    (1.0, 25, "1"),
    (1.25, 32, "1 1/4"),
    (1.5, 40, "1 1/2"),
    (2.0, 50, "2"),
    (2.5, 65, "2 1/2"),
    (3.0, 80, "3"),
    (3.5, 90, "3 1/2"),
    (4.0, 100, "4"),
    (5.0, 125, "5"),
    (6.0, 150, "6"),
    (8.0, 200, "8"),
    (10.0, 250, "10"),
    (12.0, 300, "12"),
    (14.0, 350, "14"),
    (16.0, 400, "16"),
    (18.0, 450, "18"),
    (20.0, 500, "20"),
    (24.0, 600, "24"),
)
#: Aço carbono pela ASME B36.10M e inox pela ASME B36.19M, com as tabelas da biblioteca ``fluids``.
#: O Sch 40 vem primeiro: é o tubo de processo mais comum, e o nome dele é o de sempre.
_SERIES_ASME: tuple[tuple[str, str], ...] = (
    ("40", "Aço Sch 40"),
    ("10", "Aço Sch 10"),
    ("80", "Aço Sch 80"),
    ("160", "Aço Sch 160"),
    ("STD", "Aço STD"),
    ("XS", "Aço XS"),
    ("XXS", "Aço XXS"),
    ("10S", "Aço inox Sch 10S"),
    ("40S", "Aço inox Sch 40S"),
    ("80S", "Aço inox Sch 80S"),
)


def _asme() -> list[TuboComercial]:
    tubos: list[TuboComercial] = []
    for schedule, serie in _SERIES_ASME:
        nps, _, externos, paredes = fpiping.schedule_lookup[schedule]  # em mm
        for polegada, dn, texto in _NPS:
            if polegada not in nps:
                continue
            i = nps.index(polegada)
            tubos.append(
                TuboComercial(
                    f"{serie}, DN {dn} ({texto} pol)",
                    "Aço comercial",
                    round(externos[i], 2),
                    round(paredes[i], 2),
                    serie,
                )
            )
    return tubos


def _pvc(dn: int, parede: float) -> TuboComercial:
    return TuboComercial(
        f"PVC soldável, DN {dn}", "PVC ou plástico", float(dn), parede, "PVC soldável"
    )


#: PVC pela ficha técnica da linha soldável (NBR 5648, 750 kPa a 20 °C).
TUBOS_COMERCIAIS: dict[str, TuboComercial] = {
    t.rotulo: t
    for t in (
        *_asme(),
        _pvc(20, 1.5),
        _pvc(25, 1.7),
        _pvc(32, 2.1),
        _pvc(40, 2.4),
        _pvc(50, 3.0),
        _pvc(60, 3.3),
        _pvc(75, 4.2),
        _pvc(85, 4.7),
        _pvc(110, 6.1),
    )
}
#: As peças pelo Crane: K muda com o diâmetro do tubo, pelo f_T.
PECAS_CRANE: tuple[str, ...] = tuple(nome for nome, _ in fn.PECAS_CRANE)


def ler_pecas(texto: str | None, nomes: Collection[str] = PECAS) -> dict[str, int]:
    """As peças de um bloco: guardadas como texto, porque as opções do bloco são texto."""
    try:
        dados = json.loads(texto or "{}")
    except ValueError:
        return {}
    if not isinstance(dados, Mapping):
        return {}
    pecas: dict[str, int] = {}
    for nome, quantos in dados.items():
        if nome in nomes and isinstance(quantos, (int, float)) and quantos > 0:
            pecas[str(nome)] = int(quantos)
    return pecas


def somar_pecas(pecas: Mapping[str, int]) -> float:
    return sum(PECAS[nome] * quantos for nome, quantos in pecas.items())


def ler_pontos(texto: str | None) -> list[tuple[float, float]]:
    """Os pontos da curva da bomba, na base do sistema: vazão em m³/s e altura em m."""
    try:
        dados = json.loads(texto or "[]")
    except ValueError:
        return []
    pontos: list[tuple[float, float]] = []
    if isinstance(dados, list):
        for item in dados:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                try:
                    q, h = float(item[0]), float(item[1])
                except (TypeError, ValueError):
                    continue
                if q >= 0.0 and h > 0.0 and np.isfinite(q) and np.isfinite(h):
                    pontos.append((q, h))
    return pontos


def ajustar_curva(pontos: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """H_0 e a de H = H_0 − a·Q², pelos mínimos quadrados em Q²."""
    if len({q for q, _ in pontos}) < 2:
        raise ErroDeBloco("Dê ao menos dois pontos da curva, com vazões diferentes.")
    quadrados = np.array([q**2 for q, _ in pontos])
    alturas = np.array([h for _, h in pontos])
    inclinacao, h_0 = np.polyfit(quadrados, alturas, 1)
    if inclinacao >= 0.0 or h_0 <= 0.0:
        raise ErroDeBloco("Esses pontos não dão uma curva de bomba: a altura precisa cair com Q.")
    return float(h_0), float(-inclinacao)


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
    #: O estado do fluido, quando as propriedades saem dele (CoolProp): temperatura e pressão
    #: absoluta. Com valores de tabela, fica vazio.
    temperatura: sp.Expr | None = None
    pressao: sp.Expr | None = None
    #: Gás ou líquido, quando o fluido diz; e o fluido da CoolProp, quando as propriedades vêm dela.
    gas: bool = False
    fluido: mp.Fluido | None = None
    agua: bool = False  # água de tabela, para a pressão crítica


def _linha(c: Contexto) -> Linha:
    linha = c.ligados.get("entrada")
    if linha is None:
        raise ErroDeBloco("Ligue um fluido aqui.")
    return linha


def _pela_temperatura(c: Contexto, fluido: mp.Fluido) -> dict[str, Any]:
    """ρ, μ e p_v saem do estado: temperatura e pressão viram letras, e podem até ser a pedida."""
    t, p = c.letra(g.T_FLUIDO), c.letra(g.P_FLUIDO)
    rho, mu = mp.massa_especifica(fluido, t, p), mp.viscosidade(fluido, t, p)
    validades: list[Validade] = []
    if fluido.saturacao and fluido.liquido:
        pv = mp.pressao_de_vapor(fluido, t)
        validades.append(
            Validade(
                p - pv,
                f"Com essa temperatura e essa pressão, {fluido.rotulo.lower()} ferve: a linha deixa "
                "de ser só de líquido. Suba a pressão ou baixe a temperatura.",
                restringe=False,
            )
        )
    else:
        pv = c.letra(g.P_VAPOR)
    minimo, maximo = mp.faixa_de_temperatura(mp.FLUIDOS.index(fluido))
    faixa = (
        f"de {minimo - 273.15:.0f} °C a {maximo - 273.15:.0f} °C".replace(".", ",")
        if maximo < 1500.0
        else f"acima de {minimo - 273.15:.0f} °C".replace(".", ",")
    )
    validades.append(
        Validade(
            (t - minimo) * (maximo - t),
            f"A temperatura saiu da faixa da tabela de {fluido.rotulo.lower()}, que vai {faixa}.",
            restringe=False,
        )
    )
    c.hipoteses.append(
        f"Propriedades de {fluido.rotulo.lower()} pela CoolProp, na temperatura T_f e na pressão "
        "absoluta p_f do fluido. A linha continua de escoamento incompressível e na mesma "
        "temperatura do começo ao fim."
    )
    if not fluido.liquido:
        c.hipoteses.append(
            "Gás tratado como incompressível: vale enquanto a perda de pressão fica pequena perto da "
            "pressão absoluta, até uns 10 %."
        )
    linha = Linha(
        rho,
        mu,
        pv,
        c.letra(g.GRAVIDADE),
        temperatura=t,
        pressao=p,
        gas=not fluido.liquido,
        fluido=fluido,
    )
    return {"saida": replace(linha, validade=tuple(validades))}


def _fluido(c: Contexto) -> dict[str, Any]:
    nome = c.opcoes.get("fluido", "Água a 20 °C")
    pela_temperatura = POR_TEMPERATURA.get(nome)
    if pela_temperatura is not None:
        return _pela_temperatura(c, pela_temperatura)
    if nome in FLUIDOS_TIPICOS:
        rho, mu, pv = FLUIDOS_TIPICOS[nome]
        fonte = f"Tabela: {nome}"
        c.padrao(g.RHO, rho, fonte)
        c.padrao(g.MU, mu, fonte)
        if pv is not None:
            c.padrao(g.P_VAPOR, pv, fonte)
    linha = Linha(c.letra(g.RHO), c.letra(g.MU), c.letra(g.P_VAPOR), c.letra(g.GRAVIDADE))
    return {"saida": replace(linha, gas=nome in GASES_DE_TABELA, agua=nome.startswith("Água"))}


def _tubo(c: Contexto) -> tuple[sp.Expr, sp.Expr, sp.Expr]:
    """D, L e ε do tubo, nesta ordem, com o tubo comercial e o material escolhidos no bloco."""
    comercial = TUBOS_COMERCIAIS.get(c.opcoes.get("comercial", DIAMETRO_INFORMADO))
    material = c.opcoes.get("tubo", "Aço comercial")
    if comercial is not None:
        c.padrao(g.D_TUBO, comercial.interno_m, f"Tabela: {comercial.rotulo}")
        plastico = comercial.familia == "PVC ou plástico"
        if plastico != (material == "PVC ou plástico"):
            c.alertas.append(
                f"O tubo é {comercial.rotulo}, e a rugosidade está como {material}: confira."
            )
    d, comprimento = c.letra(g.D_TUBO), c.letra(g.L_TUBO)
    if material in RUGOSIDADES:
        c.padrao(g.EPSILON, RUGOSIDADES[material], f"Tabela: {material}")
    return d, comprimento, c.letra(g.EPSILON)


def _trecho(c: Contexto) -> dict[str, Any]:
    linha = _linha(c)
    d, comprimento, rugosidade = _tubo(c)
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
    if "pecas" in c.opcoes:
        pecas = ler_pecas(c.opcoes.get("pecas"))
        lista = ", ".join(f"{quantos} × {nome}" for nome, quantos in pecas.items()) or "nenhuma"
        c.padrao(g.K_LOCAL, somar_pecas(pecas), f"Soma das peças: {lista}")
    perda = c.letra(g.K_LOCAL) * velocidade**2 / (2 * linha.gravidade)
    return {"saida": replace(linha, perda=linha.perda + perda)}


def _perdas_crane(c: Contexto) -> dict[str, Any]:
    linha = _linha(c)
    if not linha.trechos:
        raise ErroDeBloco("Ponha um trecho de tubo antes: o K do Crane usa o diâmetro dele.")
    trecho = linha.trechos[-1]
    pecas = ler_pecas(c.opcoes.get("pecas"), PECAS_CRANE)
    if not pecas:
        c.alertas.append("Diga as peças no inspetor do bloco do Crane: por enquanto ele soma zero.")
    k = sum(
        (quantos * KCrane(trecho.d, PECAS_CRANE.index(nome)) for nome, quantos in pecas.items()),
        ZERO,
    )
    c.hipoteses.append(
        "Peças pelo método do Crane (TP-410): K = n·f_T, com o f_T de escoamento todo turbulento em "
        "tubo de aço novo do diâmetro do trecho. Válvulas de passagem plena, abertas."
    )
    turbulento = Validade(
        trecho.reynolds - RE_TURBULENTO,
        "O K do Crane é de escoamento turbulento: com Reynolds abaixo de 4000, a perda nas peças sai "
        "menor que a real.",
        restringe=False,
    )
    perda = k * trecho.velocidade**2 / (2 * linha.gravidade)
    validade = (*linha.validade, turbulento)
    return {"saida": replace(linha, perda=linha.perda + perda, validade=validade)}


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


def _curva_bomba(c: Contexto) -> dict[str, Any]:
    linha = _com_perda(c)
    pontos = ler_pontos(c.opcoes.get("pontos"))
    if pontos:
        h_0, a = ajustar_curva(pontos)
        fonte = f"Curva da bomba: {len(pontos)} pontos"
        c.padrao(g.H_ZERO, h_0, fonte)
        c.padrao(g.A_BOMBA, a, fonte)
    sistema = _altura_do_sistema(c, linha)
    vazao = linha.vazao if linha.vazao is not None else c.letra(g.VAZAO_Q, fixa=True)
    bomba = c.letra(g.H_ZERO) - c.letra(g.A_BOMBA) * vazao**2
    c.hipoteses.append(
        "Curva da bomba em parábola, H = H_0 − a·Q², ajustada nos pontos dados. Ela vale entre o "
        "primeiro e o último ponto do catálogo."
    )
    condicao = Condicao(
        PONTO_DE_OPERACAO,
        PONTO_DE_OPERACAO,
        sistema,
        bomba,
        "H_{sist}",
        "",
        _dados_da_linha(linha),
        linha.validade,
        igualdade=True,
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


def _gas_no_tubo(c: Contexto) -> dict[str, Any]:
    """Escoamento isotérmico de gás num tubo longo (Crane TP-410, eq. 1-6; Menon, cap. 2).

    p₁² − p₂² = G²·(p₁/ρ₁)·[f·L/D + 2·ln(p₁/p₂)], com G = ṁ/A. Pedir p₂ ≥ p_s é pedir que essa
    conta, feita com p_s no lugar de p₂, não passe de p₁²: o lado da esquerda sobe com a vazão.
    """
    linha = _linha(c)
    if not linha.gas:
        raise ErroDeBloco(
            "Este bloco é de gás: escolha no Fluido o ar, o nitrogênio ou o metano pela "
            "temperatura. Para líquido, use o Trecho de tubo."
        )
    d, comprimento, rugosidade = _tubo(c)
    p1 = linha.pressao if linha.pressao is not None else c.letra(g.P_FLUIDO)
    saida = c.letra(g.P_SAIDA_GAS)
    vazao = c.letra(g.VAZAO_Q, fixa=True)
    fluxo = 4 * linha.rho * vazao / (sp.pi * d**2)  # G, em kg/(m²·s)
    reynolds = fluxo * d / linha.mu
    atrito = AtritoDarcy(reynolds, rugosidade / d)
    esquerda = saida**2 + fluxo**2 * p1 / linha.rho * (
        atrito * comprimento / d + 2 * sp.log(p1 / saida)
    )
    c.hipoteses.append(
        "Gás em tubo longo, em temperatura constante (isotérmico), com Q medida na entrada, na "
        "pressão p_f e na temperatura T_f do Fluido. Sem desnível."
    )
    validades = (
        Validade(p1 - saida, "A pressão na saída precisa ficar abaixo da de entrada, p_f."),
        Validade(
            sp.sqrt(p1 / linha.rho) - fluxo * p1 / (linha.rho * saida),
            "Na saída, o gás chega ao limite do escoamento isotérmico (Mach 1/√κ): a vazão não "
            "passa, a pressão de saída não cai até p_s. Aumente o diâmetro.",
            restringe=False,
        ),
        Validade(
            (reynolds - RE_LAMINAR) * (reynolds - RE_TURBULENTO),
            "Reynolds caiu na transição, entre 2300 e 4000: a perda é só uma estimativa.",
            restringe=False,
        ),
    )
    velocidades = (
        ("V_{1}", fluxo / linha.rho),
        ("V_{s}", fluxo * p1 / (linha.rho * saida)),
        ("Re", reynolds),
    )
    condicao = Condicao(
        "Pressão na saída do gás",
        "Gás no tubo",
        esquerda,
        p1**2,
        "p_{s}^{2} + G^{2}\\,\\frac{p_{1}}{\\rho_{1}}\\left(f\\,\\frac{L}{D} + "
        "2\\ln\\frac{p_{1}}{p_{s}}\\right)",
        "",
        velocidades,
        validades,
    )
    return {"condicao": [condicao]}


def _pressao_critica(c: Contexto, linha: Linha) -> sp.Expr:
    fluido = linha.fluido
    if fluido is not None and fluido.saturacao:
        c.padrao(g.P_CRITICA, mp.pressao_critica(fluido), f"CoolProp: {fluido.rotulo}")
    elif fluido is None and linha.agua:
        c.padrao(g.P_CRITICA, P_CRITICA_DA_AGUA, "IAPWS: pressão crítica da água")
    return c.letra(g.P_CRITICA)


def _valvula_controle(c: Contexto) -> dict[str, Any]:
    """K_v pedido pela IEC 60534-2-1 para líquido, em escoamento turbulento.

    K_v = Q·√((ρ/ρ₀)/Δp), com Q em m³/h e Δp em bar. Quando a queda passa de
    Δp_máx = F_L²·(p₁ − F_F·p_v), o líquido cavita na veia contraída e a vazão para de subir: a
    conta usa Δp_máx. F_F = 0,96 − 0,28·√(p_v/p_c).
    """
    linha = _linha(c)
    if linha.gas:
        raise ErroDeBloco("Este bloco é de líquido (IEC 60534-2-1): escolha um líquido no Fluido.")
    vazao = linha.vazao if linha.vazao is not None else c.letra(g.VAZAO_Q, fixa=True)
    p1, queda = c.letra(g.P_MONTANTE), c.letra(g.DP_VALVULA)
    recuperacao = c.letra(g.F_L_VALVULA)
    fator_ff = sp.Float(0.96) - sp.Float(0.28) * sp.sqrt(linha.pv / _pressao_critica(c, linha))
    maxima = recuperacao**2 * (p1 - fator_ff * linha.pv)
    usada = sp.Min(queda, maxima)
    pedido = 3600 * vazao * sp.sqrt(linha.rho / RHO_0_IEC / (usada / 100000))
    c.hipoteses.append(
        "Válvula de controle pela IEC 60534-2-1, líquido em escoamento turbulento, válvula do "
        "tamanho do tubo (sem redução, F_P = 1). K_v em m³/h com 1 bar de queda."
    )
    validades = (
        Validade(p1 - queda, "A queda na válvula precisa ser menor que a pressão antes dela."),
        Validade(
            maxima - queda,
            "Com essa queda, o líquido cavita dentro da válvula (escoamento estrangulado): a vazão "
            "não sobe mais com a queda, e o K_v saiu com Δp_máx. Confira com o fabricante se a "
            "válvula aguenta a cavitação, ou suba a pressão antes dela.",
            restringe=False,
        ),
    )
    condicao = Condicao(
        "K_v da válvula de controle",
        "Válvula de controle",
        pedido,
        c.letra(g.KV_VALVULA),
        "K_{v,ped}",
        "",
        (("\\Delta p_{máx}", maxima), ("F_{F}", fator_ff)),
        validades,
    )
    return {"condicao": [condicao]}


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


def _expansibilidade(tipo: str, beta: sp.Expr, tau: sp.Expr, kappa: sp.Expr) -> sp.Expr:
    """ε do gás: ISO 5167-2, eq. 5 (orifício), e ISO 5167-4, eq. 2 (venturi)."""
    if tipo in ORIFICIOS:
        fator = sp.Float(0.351) + sp.Float(0.256) * beta**4 + sp.Float(0.93) * beta**8
        return 1 - fator * (1 - tau ** (1 / kappa))
    return sp.sqrt(
        kappa
        * tau ** (2 / kappa)
        / (kappa - 1)
        * (1 - beta**4)
        / (1 - beta**4 * tau ** (2 / kappa))
        * (1 - tau ** ((kappa - 1) / kappa))
        / (1 - tau)
    )


def _faixa(valor: sp.Expr, minimo: float, maximo: float) -> sp.Expr:
    return (valor - minimo) * (maximo - valor)


def _validades_da_norma(
    tipo: str, d: sp.Expr, garganta: sp.Expr, beta: sp.Expr, reynolds: sp.Expr
) -> tuple[Validade, ...]:
    """Os limites de uso da ISO 5167: fora deles, o C da norma não vale."""
    if tipo in ORIFICIOS:
        return (
            Validade(
                _faixa(beta, 0.1, 0.75), "β = D_o/D fora de 0,1 a 0,75 (ISO 5167-2, 5.3.1).", False
            ),
            Validade(_faixa(d, 0.05, 1.0), "D fora de 50 a 1000 mm (ISO 5167-2, 5.3.1).", False),
            Validade(garganta - 0.0125, "D_o abaixo de 12,5 mm (ISO 5167-2, 5.3.1).", False),
            Validade(
                reynolds - sp.Max(5000, 16000 * beta**2),
                "Re_D abaixo do mínimo da ISO 5167-2: 5000, e 16000·β² com β acima de 0,56.",
                False,
            ),
        )
    if tipo == VENTURI_USINADO:
        faixas = ((50, 250), (0.4, 0.75), ("2·10⁵", "10⁶", 2e5, 1e6))
    elif tipo == VENTURI_FUNDIDO:
        faixas = ((100, 800), (0.3, 0.75), ("2·10⁵", "2·10⁶", 2e5, 2e6))
    else:
        faixas = ((200, 1200), (0.4, 0.7), ("2·10⁵", "2·10⁶", 2e5, 2e6))
    (d1, d2), (b1, b2), (t1, t2, r1, r2) = faixas
    b1_, b2_ = f"{b1:g}".replace(".", ","), f"{b2:g}".replace(".", ",")
    texto = f"(ISO 5167-4: D de {d1} a {d2} mm, β de {b1_} a {b2_}, Re_D de {t1} a {t2})."
    return (
        Validade(_faixa(d, d1 / 1000, d2 / 1000), f"D fora da faixa do venturi {texto}", False),
        Validade(_faixa(beta, b1, b2), f"β fora da faixa do venturi {texto}", False),
        Validade(_faixa(reynolds, r1, r2), f"Re_D fora da faixa do venturi {texto}", False),
    )


def _medidor(c: Contexto) -> dict[str, Any]:
    linha = _linha(c)
    tipo = c.opcoes.get("tipo", C_INFORMADO)
    d, garganta = c.letra(g.D_TUBO), c.letra(g.D_ORIFICIO)
    area = sp.pi * garganta**2 / 4
    queda = c.letra(g.DELTA_P)
    vazao = c.letra(g.VAZAO_Q)
    beta = garganta / d
    menor = Validade(d - garganta, "O orifício precisa ser menor que o tubo.")
    if tipo not in ORIFICIOS and tipo not in VENTURIS:
        conta = c.letra(g.C_DESCARGA) * area * sp.sqrt(2 * queda / linha.rho) / sp.sqrt(1 - beta**4)
        c.hipoteses.append("No medidor, C_d já inclui as perdas: vale o da norma do medidor.")
        resultado = _equacao("Vazão no medidor", conta, vazao, "Q")
        resultado["condicao"][0] = replace(resultado["condicao"][0], validade=(menor,))
        return resultado
    reynolds = 4 * linha.rho * vazao / (sp.pi * d * linha.mu)
    if tipo in ORIFICIOS:
        coeficiente: sp.Expr = CoeficienteOrificio(d, garganta, reynolds, ORIFICIOS[tipo])
        c.hipoteses.append(
            "Placa de orifício pela ISO 5167-2: C de Reader-Harris/Gallagher, que muda com β e "
            "Re_D. Trechos retos antes e depois da placa nos comprimentos da norma."
        )
    else:
        coeficiente = sp.Float(VENTURIS[tipo])
        c.hipoteses.append(
            "Venturi clássico pela ISO 5167-4, com o C fixo da norma para o tipo de convergente."
        )
    validades = [menor, *_validades_da_norma(tipo, d, garganta, beta, reynolds)]
    expansao: sp.Expr = sp.S.One
    if linha.gas:
        p1 = linha.pressao if linha.pressao is not None else c.letra(g.P_FLUIDO)
        tau = (p1 - queda) / p1
        expansao = _expansibilidade(tipo, beta, tau, c.letra(g.KAPPA))
        validades.append(
            Validade(
                tau - sp.Rational(3, 4),
                "A queda no medidor passou de 25 % da pressão p_f: a ISO 5167 pede p₂/p₁ ≥ 0,75.",
                restringe=False,
            )
        )
    conta = coeficiente * expansao * area * sp.sqrt(2 * queda / linha.rho) / sp.sqrt(1 - beta**4)
    condicao = Condicao(
        "Vazão no medidor",
        "Vazão no medidor",
        conta,
        vazao,
        "Q",
        "",
        (("Re_{D}", reynolds), ("\\beta", beta)),
        tuple(validades),
        igualdade=True,
    )
    return {"condicao": [condicao]}


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
                "Valores típicos de tabela, ou pela temperatura: aí a CoolProp dá ρ, μ e p_v na "
                "temperatura e na pressão do fluido. O metano faz as vezes do gás natural. Para "
                "outro fluido, informe as propriedades.",
                (INFORMAR, *FLUIDOS_TIPICOS, *POR_TEMPERATURA),
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
            Opcao(
                "comercial",
                "Tubo comercial",
                "Preenche D com o diâmetro interno da tabela: aço pela ASME B36.10M, inox pela "
                "B36.19M, ou PVC soldável.",
                (DIAMETRO_INFORMADO, *TUBOS_COMERCIAIS),
                DIAMETRO_INFORMADO,
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
    Bloco(
        "perdas_crane",
        "Peças pelo Crane",
        mb.GRUPO_TUBULACAO,
        "Soma K·V²/(2·g) das peças pelo método do Crane: K muda com o diâmetro do trecho anterior.",
        "h_k = Σ n·f_T·V²/(2·g)",
        (Porta("entrada", "Linha", LINHA),),
        (_SAIDA,),
        _perdas_crane,
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
        "curva_bomba",
        "Curva da bomba",
        "Acha o ponto de operação: onde a curva da bomba cruza a do sistema. Peça a vazão Q.",
        "H_0 − a·Q² = H_est + Δp/(ρ·g) + h_L",
        _curva_bomba,
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
    Bloco(
        "gas_no_tubo",
        "Gás no tubo",
        mb.GRUPO_VERIFICACAO,
        "Gás em tubo longo, isotérmico: a pressão que chega no fim precisa ser pelo menos p_s.",
        "p_s² + G²·(p₁/ρ₁)·(f·L/D + 2·ln(p₁/p_s)) ≤ p₁²",
        (_ENTRADA,),
        (_SAIDA_CONDICAO,),
        _gas_no_tubo,
        (
            Opcao(
                "tubo",
                "Material do tubo",
                "Dá a rugosidade de tubo novo.",
                (*RUGOSIDADES, RUGOSIDADE_INFORMADA),
                "Aço comercial",
            ),
            Opcao(
                "comercial",
                "Tubo comercial",
                "Preenche D com o diâmetro interno da tabela: ASME B36.10M e B36.19M, ou PVC.",
                (DIAMETRO_INFORMADO, *TUBOS_COMERCIAIS),
                DIAMETRO_INFORMADO,
            ),
        ),
        dominio=FLUIDOS,
    ),
    _verificacao(
        "valvula_controle",
        "Válvula de controle",
        "K_v que a válvula precisa ter pela IEC 60534-2-1, com o aviso de cavitação.",
        "Q·√((ρ/ρ₀)/Δp) ≤ K_v",
        _valvula_controle,
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
    Bloco(
        "medidor",
        "Orifício ou venturi",
        mb.GRUPO_EQUACOES,
        "Vazão pela queda de pressão no medidor: C informado ou pela ISO 5167.",
        "Q = C·ε·A·√(2·Δp/ρ)/√(1−β⁴)",
        (_ENTRADA,),
        (_SAIDA_CONDICAO,),
        _medidor,
        (
            Opcao(
                "tipo",
                "Medidor",
                "Pela ISO 5167, o C da placa sai de β e de Reynolds (Reader-Harris/Gallagher), e o "
                "do venturi é o da norma. Com gás, entra a expansibilidade ε.",
                MEDIDORES,
                C_INFORMADO,
            ),
        ),
        dominio=FLUIDOS,
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
