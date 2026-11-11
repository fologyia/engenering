"""As peças de um eixo no Montador: o que entrega o esforço e o que o eixo carrega.

A engrenagem e a polia dão as forças que dobram o eixo. A chaveta, o cubo prensado e o rolamento
são as peças que ficam nele, cada uma com as condições que a fazem passar. A inclinação e a rotação
crítica dizem se o eixo, além de aguentar, fica rígido o bastante.

As contas são as do Cálculo de peças (``core/elementos_eixos.py``, ``elementos_transmissao.py`` e
``elementos_mancais.py``), escritas em letras: o Montador e o Assistente têm de dar o mesmo número.
Os blocos entram no catálogo por ``montador_blocos.registrar``, como os de fluidos.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import sympy as sp

from core import elementos_eixos as ee
from core import elementos_mancais as em
from core import elementos_molas_atrito as ema
from core import elementos_transmissao as et
from core import montador_blocos as mb
from core import montador_grandezas as g
from core.montador_blocos import (
    CONDICAO,
    GRUPO_CRITERIO,
    GRUPO_ORIGEM,
    GRUPO_PECAS,
    MATERIAL,
    SECAO,
    VALOR,
    Bloco,
    Condicao,
    Contexto,
    ErroDeBloco,
    Opcao,
    Porta,
)
from core.montador_funcoes import (
    AJUSTES_DO_CUBO,
    AlturaDaChaveta,
    CargaEquivalenteEsferas,
    CargaEquivalenteXY,
    CargaEstatica,
    FatorLewis,
    InterferenciaMaxima,
    InterferenciaMinima,
    LarguraDaChaveta,
    RasgoDaChaveta,
    TensaoCritica,
)
from core.montador_secoes import Validade

_ENTRADA = Porta("entrada", "Seção", SECAO)
_MATERIAL = Porta("material", "Material", MATERIAL)
_SAI_CONDICAO = Porta("condicao", "Condição", CONDICAO)
_ENTRA_TORQUE = Porta("T", "T", VALOR, g.MOMENTO)
_ENTRA_D = Porta("d", "d", VALOR, g.MEDIDA)

# ---------------------------------------------------------------------------
# De onde vem o esforço
# ---------------------------------------------------------------------------

PELA_POTENCIA = "Pela potência e rotação"
PELO_TORQUE = "Pelo torque T"
_COMO_ENTRA_O_TORQUE = Opcao(
    "torque",
    "Como entra o torque",
    "Pela potência e pela rotação do eixo, ou pelo próprio torque. Um fio na bolinha T vale mais "
    "que os dois.",
    (PELA_POTENCIA, PELO_TORQUE),
    PELA_POTENCIA,
)
CORREIA_EM_V = "Em V, canal de 38°"
CORREIA_PLANA = "Plana"
_TIPO_DE_CORREIA = Opcao(
    "correia",
    "Tipo de correia",
    "Na correia em V a cunha do canal aumenta o atrito: a mesma força útil pede menos aperto e "
    "carrega menos o eixo.",
    (CORREIA_EM_V, CORREIA_PLANA),
    CORREIA_EM_V,
)
_MEIO_CANAL = sp.pi * 19 / 180  # metade do canal de 38°, o mesmo padrão do Assistente


def _torque(c: Contexto) -> sp.Expr:
    ligado = c.ligados.get("T")
    if ligado is not None:
        return ligado
    if c.opcoes.get("torque", PELA_POTENCIA) == PELO_TORQUE:
        return c.letra(g.T, fixa=True)
    return 30 * c.letra(g.POT, fixa=True) / (sp.pi * c.letra(g.ROT, fixa=True))


def _engrenagem(c: Contexto) -> dict[str, Any]:
    torque = _torque(c)
    diametro = c.letra(g.D_ENGRENAGEM)
    pressao = c.letra(g.PHI_N, fixa=True)
    helice = c.letra(g.PSI)
    tangencial = 2 * torque / diametro
    c.hipoteses.append(
        "Forças de engrenamento no diâmetro primitivo, como no Cálculo de peças: F_t = 2·T/d, "
        "F_r = F_t·tg φ_n/cos ψ e F_a = F_t·tg ψ."
    )
    c.hipoteses.append(
        "A radial e a tangencial ficam a 90° uma da outra: ligue cada uma num plano do eixo, uma em "
        "XX e a outra em YY, e a seção redonda junta as duas."
    )
    if helice != 0:
        c.hipoteses.append(
            "Na helicoidal, a força axial F_a precisa de um mancal que a segure, e o binário "
            "F_a·d/2 fica no plano da radial."
        )
    return {
        "T": torque,
        "F_t": tangencial,
        "F_r": tangencial * sp.tan(pressao) / sp.cos(helice),
        "F_a": tangencial * sp.tan(helice),
    }


def _polia(c: Contexto) -> dict[str, Any]:
    torque = _torque(c)
    diametro = c.letra(g.D_POLIA)
    atrito = c.letra(g.MU_CORREIA, fixa=True)
    abracamento = c.letra(g.THETA_ABRACAMENTO, fixa=True)
    expoente = atrito * abracamento
    if c.opcoes.get("correia", CORREIA_EM_V) == CORREIA_EM_V:
        expoente = expoente / sp.sin(_MEIO_CANAL)
    razao = sp.exp(expoente)
    util = 2 * torque / diametro
    tenso = util * razao / (razao - 1)
    frouxo = util / (razao - 1)
    c.hipoteses.append(
        "Correia no limite do deslizamento pela equação de Euler: F₁/F₂ = e^(μ·θ), com o canal em "
        "V dividindo por sen 19°. A carga no eixo junta F₁ e F₂, sem a parcela centrífuga, que a "
        "correia equilibra sozinha."
    )
    c.hipoteses.append(
        "A correia montada com mais aperto que o mínimo carrega mais o eixo: a pré-tensão "
        "instalada precisa ser pelo menos (F₁ + F₂)/2, e o eixo sente o que foi instalado."
    )
    return {
        "T": torque,
        "F": sp.sqrt(tenso**2 + frouxo**2 - 2 * tenso * frouxo * sp.cos(abracamento)),
        "F_1": tenso,
    }


# ---------------------------------------------------------------------------
# Par de engrenagens: as forças e o dente, numa conta só
# ---------------------------------------------------------------------------

EIXO_DO_PINHAO = "Eixo do pinhão"
EIXO_DA_COROA = "Eixo da coroa"
_QUAL_EIXO = Opcao(
    "eixo",
    "Eixo desta conta",
    "A potência, a rotação e o torque são do eixo escolhido. As forças são as mesmas nos dois; "
    "na cônica, a radial de um é a axial do outro.",
    (EIXO_DO_PINHAO, EIXO_DA_COROA),
    EIXO_DO_PINHAO,
)
PROCESSO_PADRAO = "Caracol (hob)"
_VELOCIDADE_DO_KV = 25.0  # m/s: acima disso o K_v de Barth e AGMA não vale para engrenagem comum


def fator_dinamico(processo: str, velocidade: sp.Expr) -> sp.Expr:
    """K_v de Barth e AGMA em letra (Shigley, eq. 14-4), igual a ``et.fator_dinamico``."""
    if processo == "Fundido":
        return (sp.Float(3.05) + velocidade) / sp.Float(3.05)
    if processo == "Fresado":
        return (sp.Float(6.1) + velocidade) / sp.Float(6.1)
    if processo == "Retificado":
        return sp.sqrt((sp.Float(5.56) + sp.sqrt(velocidade)) / sp.Float(5.56))
    return (sp.Float(3.56) + sp.sqrt(velocidade)) / sp.Float(3.56)


def _torque_do_pinhao(c: Contexto, z1: sp.Expr, z2: sp.Expr) -> tuple[sp.Expr, sp.Expr, sp.Expr]:
    """Torque deste eixo, torque e rotação do pinhão. Sem perdas no engrenamento."""
    deste_eixo = _torque(c)
    rotacao = c.letra(g.ROT, fixa=True)
    if c.opcoes.get("eixo", EIXO_DO_PINHAO) == EIXO_DA_COROA:
        return deste_eixo, deste_eixo * z1 / z2, rotacao * z2 / z1
    return deste_eixo, deste_eixo, rotacao


def _par_de_engrenagens(c: Contexto) -> dict[str, Any]:
    modulo = c.letra(g.M_MODULO)
    z1, z2 = c.letra(g.Z_PINHAO), c.letra(g.Z_COROA)
    largura = c.letra(g.B_DENTE)
    pressao = c.letra(g.PHI_N, fixa=True)
    helice = c.letra(g.PSI)
    sobrecarga = c.letra(g.K_SOBRECARGA, fixa=True)
    distribuicao = c.letra(g.K_DISTRIBUICAO, fixa=True)
    dureza = c.letra(g.DUREZA, fixa=True)
    poisson = c.letra(g.NU_ENGRENAGEM, fixa=True)
    n = c.letra(g.FS, fixa=True)
    material = c.material()
    modulo_e = material.e if material else c.letra(g.E, fixa=True)
    deste_eixo, torque, rotacao = _torque_do_pinhao(c, z1, z2)

    transversal = sp.atan(sp.tan(pressao) / sp.cos(helice))
    d1 = modulo * z1 / sp.cos(helice)
    d2 = modulo * z2 / sp.cos(helice)
    tangencial = 2 * torque / d1
    velocidade = sp.pi * d1 * rotacao / 60000  # m/s, com d em mm e n em rpm
    processo = c.opcoes.get("processo", PROCESSO_PADRAO)
    grau = c.opcoes.get("grau", et.GRAUS_AGMA[0])
    carga = sobrecarga * fator_dinamico(processo, velocidade) * distribuicao * tangencial
    # Lewis com o número virtual de dentes z/cos³ψ, e as resistências de aço beneficiado da AGMA.
    flexao_1 = carga / (largura * modulo * FatorLewis(z1 / sp.cos(helice) ** 3))
    flexao_2 = carga / (largura * modulo * FatorLewis(z2 / sp.cos(helice) ** 3))
    elastico = sp.sqrt(modulo_e / (2 * sp.pi * (1 - poisson**2)))
    raios = 1 / (d1 * sp.sin(transversal) / 2) + 1 / (d2 * sp.sin(transversal) / 2)
    contato = elastico * sp.sqrt(carga / (largura * sp.cos(transversal)) * raios)
    flexao_admissivel = et.resistencia_flexao_agma(dureza, grau) / n
    contato_admissivel = et.resistencia_contato_agma(dureza, grau) / n
    validade = (
        Validade(z1 - 12, "O fator de Lewis começa em 12 dentes."),
        Validade(z2 - z1, "z_1 é o pinhão, o menor do par: z_2 precisa ser maior ou igual.", False),
        Validade(
            16 * modulo - largura,
            "A largura passou de 16 módulos: o eixo precisa ser muito rígido para o dente encostar "
            "por inteiro.",
            False,
        ),
        Validade(
            largura - 8 * modulo,
            "A largura ficou abaixo de 8 módulos: o dente fica estreito para a carga e caro de "
            "fazer.",
            False,
        ),
        Validade(
            z1 - 2 * sp.cos(helice) / sp.sin(transversal) ** 2,
            "Com tão poucos dentes, o corte adelgaça o pé do dente do pinhão: aumente z_1 ou use "
            "correção de perfil.",
            False,
        ),
        Validade(
            _VELOCIDADE_DO_KV - velocidade,
            "Velocidade na primitiva acima de 25 m/s: o K_v deixa de valer para engrenagem comum, e "
            "a precisão e a lubrificação pedem projeto próprio.",
            False,
        ),
    )
    c.hipoteses.append(
        "Dente de perfil evolvente e altura normal. Pré-dimensionamento por Lewis e por contato de "
        "Hertz, como no Cálculo de peças: não é o cálculo AGMA 2001 nem o ISO 6336."
    )
    c.hipoteses.append(
        "Pinhão e coroa do mesmo aço beneficiado: S_t e S_c das Figuras 14-2 e 14-5 de Shigley "
        "pela dureza. K_v de Barth e AGMA pela fabricação do dente."
    )
    if helice != 0:
        c.hipoteses.append(
            "Na helicoidal, a conta de contato não credita a razão de contato do dente inclinado, a "
            "favor da segurança. A força axial F_a precisa de um mancal que a segure."
        )
    condicoes = [
        Condicao(
            "Flexão no dente do pinhão (Lewis)",
            "Dente",
            flexao_1,
            flexao_admissivel,
            "\\sigma_{1}",
            validade=validade,
        ),
        Condicao(
            "Flexão no dente da coroa (Lewis)",
            "Dente",
            flexao_2,
            flexao_admissivel,
            "\\sigma_{2}",
            validade=validade,
        ),
        Condicao(
            "Pressão de contato no flanco",
            "Dente",
            contato,
            contato_admissivel,
            "\\sigma_{c}",
            validade=validade,
        ),
    ]
    return {
        "T": deste_eixo,
        "F_t": tangencial,
        "F_r": tangencial * sp.tan(pressao) / sp.cos(helice),
        "F_a": tangencial * sp.tan(helice),
        "condicao": condicoes,
    }


def _conica(c: Contexto) -> dict[str, Any]:
    modulo = c.letra(g.M_CONICA)
    z1, z2 = c.letra(g.Z_PINHAO_CONICO), c.letra(g.Z_COROA_CONICA)
    largura = c.letra(g.B_CONICA)
    pressao = c.letra(g.PHI_N, fixa=True)
    deste_eixo = _torque(c)
    coroa = c.opcoes.get("eixo", EIXO_DO_PINHAO) == EIXO_DA_COROA
    torque = deste_eixo * z1 / z2 if coroa else deste_eixo
    cone = sp.atan(z1 / z2)  # ângulo do cone do pinhão, com os eixos a 90°
    d1 = modulo * z1
    medio = d1 - largura * sp.sin(cone)
    tangencial = 2 * torque / medio
    radial = tangencial * sp.tan(pressao) * sp.cos(cone)
    axial = tangencial * sp.tan(pressao) * sp.sin(cone)
    geratriz = d1 / (2 * sp.sin(cone))
    c.validades.extend(
        (
            Validade(medio, "A largura é grande demais para este pinhão: o primitivo médio sumiu."),
            Validade(
                10 * modulo - largura,
                "A largura passou de 10 módulos: a ponta fina do dente quase não trabalha.",
                False,
            ),
            Validade(
                geratriz / 3 - largura,
                "A largura passou de um terço da geratriz do cone: a ponta fina do dente quase não "
                "trabalha.",
                False,
            ),
        )
    )
    c.hipoteses.append(
        "Engrenagem cônica de dente reto com os eixos a 90°: as forças agem no meio da largura do "
        "dente, no primitivo médio (Shigley, cap. 13), como no Cálculo de peças."
    )
    c.hipoteses.append(
        "No eixo da coroa, a radial é a axial do pinhão, e a axial é a radial dele. O binário da "
        "axial vale F_a vezes o raio médio, que sai pela bolinha r_m."
    )
    raio_pinhao = medio / 2
    raio_coroa = medio / 2 * z2 / z1
    return {
        "T": deste_eixo,
        "F_t": tangencial,
        "F_r": axial if coroa else radial,
        "F_a": radial if coroa else axial,
        "r_m": raio_coroa if coroa else raio_pinhao,
    }


# ---------------------------------------------------------------------------
# Chaveta
# ---------------------------------------------------------------------------

DIN_6885 = "DIN 6885 pelo diâmetro"
CHAVETA_INFORMADA = "Informar b, h e t₁"
PONTAS_ARREDONDADAS = "Arredondadas, forma A"
PONTAS_RETAS = "Retas, forma B"
UMA_CHAVETA = "Uma chaveta"
DUAS_CHAVETAS = "Duas a 180°"
_CISALHAMENTO_DO_ACO = sp.Rational(577, 1000)  # 1/√3, como no Assistente


def _diametro(c: Contexto) -> sp.Expr:
    ligado = c.ligados.get("d")
    return ligado if ligado is not None else c.letra(g.D, fixa=True)


def _escoamento_do_eixo(c: Contexto) -> sp.Expr:
    material = c.material()
    return material.sy if material else c.letra(g.SY, fixa=True)


def _chaveta(c: Contexto) -> dict[str, Any]:
    torque = c.letra(g.T, "T", fixa=True)
    d = _diametro(c)
    comprimento = c.letra(g.L_CHAVETA)
    escoamento_chaveta = c.letra(g.SY_CHAVETA, fixa=True)
    escoamento_cubo = c.letra(g.SY_CUBO, fixa=True)
    escoamento_eixo = _escoamento_do_eixo(c)
    n = c.letra(g.FS, fixa=True)
    servico = c.letra(g.K_SERVICO, fixa=True)
    validade: list[Validade] = []
    tabelada = c.opcoes.get("dimensoes", DIN_6885) == DIN_6885
    if tabelada:
        b, h, t1 = LarguraDaChaveta(d), AlturaDaChaveta(d), RasgoDaChaveta(d)
        validade += [
            Validade(d - 6, "A tabela DIN 6885 começa acima de 6 mm: informe a chaveta à mão."),
            Validade(500 - d, "A tabela DIN 6885 vai até 500 mm: informe a chaveta à mão."),
        ]
    else:
        b, h, t1 = c.letra(g.B_CHAVETA), c.letra(g.H_CHAVETA), c.letra(g.T1_CHAVETA)
        validade.append(
            Validade(h - t1, "A profundidade t₁ no eixo precisa ser menor que a altura h_ch.")
        )
    arredondadas = c.opcoes.get("pontas", PONTAS_ARREDONDADAS) == PONTAS_ARREDONDADAS
    util = comprimento - b if arredondadas else comprimento
    efetivas = sp.Rational(3, 2) if c.opcoes.get("quantas", UMA_CHAVETA) == DUAS_CHAVETAS else 1
    validade += [
        Validade(util, "A chaveta precisa ser mais comprida do que larga: sobra L_ch − b ≤ 0."),
        Validade(
            sp.Rational(3, 2) * d - util,
            "O comprimento útil da chaveta passou de 1,5·d: além disso o torque se concentra no "
            "começo dela. Use duas chavetas, um cubo prensado ou um eixo mais grosso.",
            restringe=False,
        ),
    ]
    forca = 2 * servico * torque / d
    tau = forca / (b * util * efetivas)
    no_eixo = forca / (t1 * util * efetivas)
    no_cubo = forca / ((h - t1) * util * efetivas)
    c.hipoteses.append(
        "Chaveta paralela pela DIN 6892: força 2·K_s·T/d no raio do eixo, uniforme ao longo do "
        "comprimento útil. Com duas chavetas, só 1,5 conta, porque elas nunca dividem por igual."
    )
    c.hipoteses.append(
        "Limites: S_y/n na pressão e 0,577·S_y/n no corte. Com carga que inverte, a chaveta bate "
        "no rasgo e o limite usual cai para cerca de metade."
    )
    c.hipoteses.append(
        "O rasgo também enfraquece o eixo à fadiga: ponha o Entalhe com rasgo de chaveta na conta "
        "do eixo."
    )
    feitas = tuple(validade)
    condicoes = [
        Condicao(
            "Cisalhamento da chaveta",
            "Chaveta",
            tau,
            _CISALHAMENTO_DO_ACO * escoamento_chaveta / n,
            "\\tau_{ch}",
            validade=feitas,
        ),
        Condicao(
            "Esmagamento no rasgo do eixo",
            "Chaveta",
            no_eixo,
            escoamento_eixo / n,
            "p_{eixo}",
            validade=feitas,
        ),
        Condicao(
            "Esmagamento no rasgo do cubo",
            "Chaveta",
            no_cubo,
            escoamento_cubo / n,
            "p_{cubo}",
            validade=feitas,
        ),
    ]
    if tabelada:
        # Na DIN 6885 a parte da chaveta que fica no cubo é sempre a mais baixa: a pressão nela manda.
        condicoes.append(
            Condicao(
                "Esmagamento da chaveta",
                "Chaveta",
                no_cubo,
                escoamento_chaveta / n,
                "p_{ch}",
                validade=feitas,
            )
        )
    else:
        condicoes += [
            Condicao(
                f"Esmagamento da chaveta do lado do {lado}",
                "Chaveta",
                pressao,
                escoamento_chaveta / n,
                "p_{ch}",
                validade=feitas,
            )
            for lado, pressao in (("eixo", no_eixo), ("cubo", no_cubo))
        ]
    return {"condicao": condicoes}


# ---------------------------------------------------------------------------
# Cubo prensado
# ---------------------------------------------------------------------------

AJUSTE_PADRAO = "H7/s6 (forte)"


def _cubo_prensado(c: Contexto) -> dict[str, Any]:
    torque = c.letra(g.T, "T", fixa=True)
    axial = c.letra(g.F_AX_CUBO, "F_ac", fixa=True)
    d = _diametro(c)
    material = c.material()
    modulo_eixo = material.e if material else c.letra(g.E, fixa=True)
    escoamento_eixo = _escoamento_do_eixo(c)
    externo = c.letra(g.D_CUBO)
    comprimento = c.letra(g.L_AJUSTE)
    atrito = c.letra(g.MU_AJUSTE, fixa=True)
    modulo_cubo = c.letra(g.E_CUBO, fixa=True)
    poisson_eixo = c.letra(g.NU_EIXO, fixa=True)
    poisson_cubo = c.letra(g.NU_CUBO, fixa=True)
    escoamento_cubo = c.letra(g.SY_CUBO, fixa=True)
    n = c.letra(g.FS, fixa=True)
    servico = c.letra(g.K_SERVICO, fixa=True)
    alisamento = sp.Rational(4, 5) * (c.letra(g.RZ_EIXO, fixa=True) + c.letra(g.RZ_CUBO, fixa=True))
    ajuste = c.opcoes.get("ajuste", AJUSTE_PADRAO)
    if ajuste == ee.AJUSTE_MANUAL:
        minima, maxima = c.letra(g.DELTA_MIN), c.letra(g.DELTA_MAX)
    else:
        indice = AJUSTES_DO_CUBO.index(ajuste) if ajuste in AJUSTES_DO_CUBO else 2
        minima, maxima = InterferenciaMinima(d, indice), InterferenciaMaxima(d, indice)
        c.hipoteses.append(f"Interferência do ajuste {ajuste} pelas tabelas 1 e 2 da NBR 6158.")
    util_minima = minima - alisamento
    relacao = (externo**2 + d**2) / (externo**2 - d**2)
    flexibilidade = (relacao + poisson_cubo) / modulo_cubo + (1 - poisson_eixo) / modulo_eixo
    pressao_minima = util_minima / (d * flexibilidade)
    pressao_maxima = (maxima - alisamento) / (d * flexibilidade)
    validade = (
        Validade(externo - d, "O cubo precisa ser maior que o eixo: D_cubo > d."),
        Validade(
            util_minima,
            "A rugosidade consome toda a interferência mínima: o ajuste fica solto. Use um ajuste "
            "mais forte ou superfícies mais lisas.",
        ),
        Validade(
            comprimento - d / 2,
            "O ajuste ficou curto: abaixo de L_aj = d/2 o cubo tomba no eixo.",
            restringe=False,
        ),
        Validade(
            2 * d - comprimento,
            "O ajuste passou de 2·d: a pressão deixa de ficar uniforme e o ganho some.",
            restringe=False,
        ),
    )
    c.hipoteses.append(
        "Ajuste prensado por Lamé, com eixo maciço e cubo de parede grossa, em regime elástico "
        "(Shigley, cap. 3). A interferência útil é a nominal menos 0,8·(Rz do eixo + Rz do furo)."
    )
    c.hipoteses.append(
        "Transmissão com a menor interferência; tensões com a maior, contra S_y e sem o n, como no "
        "Assistente: é o pico da montagem, que não se repete. A força centrífuga não entra."
    )
    c.hipoteses.append(
        "Na borda do cubo a pressão sobe e começa a fadiga por atrito: ponha o Entalhe com cubo "
        "prensado na conta do eixo."
    )
    solicitante = sp.sqrt(axial**2 + (2 * servico * torque / d) ** 2)
    condicoes = [
        Condicao(
            "Transmissão por atrito",
            "Cubo prensado",
            n * solicitante,
            sp.pi * atrito * pressao_minima * d * comprimento,
            "n \\cdot F_{sol}",
            validade=validade,
        ),
        Condicao(
            "Escoamento no furo do cubo",
            "Cubo prensado",
            pressao_maxima * sp.sqrt(relacao**2 + relacao + 1),
            escoamento_cubo,
            "\\sigma_{eq,cubo}",
            validade=validade,
        ),
        Condicao(
            "Escoamento na superfície do eixo",
            "Cubo prensado",
            pressao_maxima,
            escoamento_eixo,
            "\\sigma_{eq,eixo}",
            validade=validade,
        ),
    ]
    return {"condicao": condicoes}


# ---------------------------------------------------------------------------
# Rolamento
# ---------------------------------------------------------------------------

ESFERAS = "Esferas de sulco profundo"
ESFERAS_INFORMADAS = "Esferas, X e Y do catálogo"
ROLOS_INFORMADOS = "Rolos, X e Y do catálogo"
TIPOS_DE_ROLAMENTO = (ESFERAS, ESFERAS_INFORMADAS, ROLOS_INFORMADOS)


def _rolamento(c: Contexto) -> dict[str, Any]:
    primeira = c.ligados.get("R")
    segunda = c.ligados.get("R_2")
    radial = primeira if primeira is not None else c.letra(g.F_RADIAL_MANCAL)
    if segunda is not None:
        radial = sp.sqrt(radial**2 + segunda**2)
    axial = c.letra(g.F_AXIAL_MANCAL, "F_am")
    rotacao = c.letra(g.ROT, fixa=True)
    dinamica = c.letra(g.C_DINAMICA)
    estatica = c.letra(g.C_ESTATICA)
    vida = c.letra(g.VIDA_HORAS, fixa=True)
    aplicacao = c.letra(g.F_APLICACAO, fixa=True)
    seguranca = c.letra(g.S0_MINIMO, fixa=True)
    tipo = c.opcoes.get("tipo", ESFERAS)
    confianca = c.opcoes.get("confiabilidade", "90 %")
    a1 = sp.Float(em.A1_CONFIABILIDADE.get(confianca, 1.0))
    if tipo == ESFERAS:
        equivalente = aplicacao * CargaEquivalenteEsferas(radial, axial, estatica)
    else:
        x, y = c.letra(g.X_ROLAMENTO), c.letra(g.Y_ROLAMENTO)
        equivalente = aplicacao * CargaEquivalenteXY(radial, axial, x, y)
    expoente = sp.Integer(3) if tipo != ROLOS_INFORMADOS else sp.Rational(10, 3)
    voltas = rotacao * vida / 60  # rpm vezes segundos: a vida está na base, em s
    c.hipoteses.append(
        "Vida pela ISO 281: L = a₁·(C/P)^p em milhões de voltas, com p = 3 em esferas e 10/3 em "
        "rolos. Lubrificação boa e sem contaminação severa (a_ISO = 1)."
    )
    c.hipoteses.append(
        "Em esferas de sulco profundo, X e Y saem da Tabela 11-1 de Shigley pela relação F_a/C₀; "
        "nos outros tipos, do catálogo. O fator de aplicação multiplica P."
    )
    c.hipoteses.append(
        "Carga constante. Em equipamento de içamento, a NBR 8400 troca a carga máxima por uma média: "
        "use o rolamento do Cálculo de peças."
    )
    minimo = sp.Rational(1, 100) if tipo != ROLOS_INFORMADOS else sp.Rational(2, 100)
    validade = (
        Validade(
            equivalente - minimo * dinamica,
            "A carga ficou abaixo do mínimo para o rolamento rolar (P ≥ 0,01·C em esferas e 0,02·C "
            "em rolos): os corpos deslizam e gastam a pista.",
            restringe=False,
        ),
    )
    condicoes = [
        Condicao(
            "Vida do rolamento",
            "Rolamento",
            equivalente * (voltas / (10**6 * a1)) ** (1 / expoente),
            dinamica,
            "P \\cdot (L_{10}/a_{1})^{1/p}",
            validade=validade,
        ),
        Condicao(
            "Segurança estática do rolamento",
            "Rolamento",
            seguranca * CargaEstatica(radial, axial),
            estatica,
            "s_{0} \\cdot P_{0}",
            validade=validade,
        ),
    ]
    return {"condicao": condicoes}


# ---------------------------------------------------------------------------
# Rigidez do eixo
# ---------------------------------------------------------------------------

ENGRENAGEM_RETA = "Engrenagem reta sem abaulamento"
INFORMAR_INCLINACAO = "Informar θ_adm"
#: Shigley, Tabela 7-2: os limites dos mancais são os do Assistente, e a engrenagem reta pede 0,0005.
LIMITES_DE_INCLINACAO: Mapping[str, float] = {
    **{f"Mancal de {nome.lower()}": valor for nome, valor in ee.INCLINACAO_MANCAL.items()},
    ENGRENAGEM_RETA: 0.0005,
}
SO_O_EIXO = "Só o eixo"
PECA_ENTRE_MANCAIS = "Eixo e uma peça entre os mancais"
PECA_EM_BALANCO = "Eixo e uma peça em balanço"


def _inclinacao(c: Contexto) -> dict[str, Any]:
    estado = c.estado()
    primeira = c.ligados.get("giro")
    if primeira is None:
        raise ErroDeBloco("Ligue aqui a saída θ·EI de um bloco de viga.")
    segunda = c.ligados.get("giro_2")
    material = c.material()
    modulo = material.e if material else c.letra(g.E, fixa=True)
    secao = estado.secao
    inclinacao = primeira / (modulo * secao.inercia)
    if segunda is not None:
        inclinacao = sp.sqrt(inclinacao**2 + (segunda / (modulo * secao.inercia_y)) ** 2)
    escolha = c.opcoes.get("limite", next(iter(LIMITES_DE_INCLINACAO)))
    if escolha in LIMITES_DE_INCLINACAO:
        limite: sp.Expr = sp.Float(LIMITES_DE_INCLINACAO[escolha])
        nome = f"Inclinação: {escolha[0].lower()}{escolha[1:]}"
    else:
        limite = c.letra(g.THETA_ADM)
        nome = "Inclinação"
    c.hipoteses.append(
        "Inclinação admissível pela Tabela 7-2 de Shigley. Com os dois planos ligados, as "
        "inclinações se somam como vetores."
    )
    return {
        "condicao": [
            Condicao(nome, "Inclinação", inclinacao, limite, "\\theta", "", (), estado.validade)
        ]
    }


# ---------------------------------------------------------------------------
# Fuso (parafuso de potência)
# ---------------------------------------------------------------------------

COM_COLAR = "Com colar"
SEM_COLAR = "Sem colar (ponta ou mancal sem atrito)"
CONFERIR_FLAMBAGEM = "Conferir a flambagem do fuso"
SO_TRACIONADO = "O fuso só trabalha tracionado"
NAO_EXIGIR_TRAVA = "Só avisar se não trava sozinho"
EXIGIR_TRAVA = "Exigir que a rosca trave sozinha"


def _fuso(c: Contexto) -> dict[str, Any]:
    """Shigley, cap. 8, como o fuso do Assistente (:func:`core.elementos_molas_atrito.calcular_fuso`)."""
    ligada = c.ligados.get("F")
    forca = ligada if ligada is not None else c.letra(g.F_FUSO)
    d = c.letra(g.D_FUSO)
    passo = c.letra(g.P_FUSO)
    entradas = c.letra(g.Z_FUSO, fixa=True)
    atrito = c.letra(g.MU_ROSCA, fixa=True)
    filetes = c.letra(g.FILETES, fixa=True)
    n = c.letra(g.FS, fixa=True)
    material = c.material()
    escoamento = material.sy if material else c.letra(g.SY, fixa=True)
    rosca = c.opcoes.get("rosca", ema.ROSCA_TRAPEZOIDAL)
    secante = 1 / sp.cos(sp.rad(sp.nsimplify(ema.ROSCAS.get(rosca, 15.0))))
    medio = d - passo / 2
    raiz = d - passo
    avanco = entradas * passo
    folga = sp.pi * medio - atrito * avanco * secante
    torque = forca * medio / 2 * (avanco + sp.pi * atrito * medio * secante) / folga
    trava = sp.pi * atrito * medio * secante - avanco  # ≥ 0: a rosca segura a carga sozinha
    if c.opcoes.get("colar", COM_COLAR) == COM_COLAR:
        torque += forca * c.letra(g.MU_COLAR, fixa=True) * c.letra(g.D_COLAR, fixa=True) / 2
    validade = [
        Validade(raiz, "O passo precisa ser menor que o diâmetro do fuso."),
        Validade(
            folga,
            "Com este atrito e este avanço, o fuso trava ao subir: nenhum torque levanta a carga.",
        ),
    ]
    exigir = c.opcoes.get("trava", NAO_EXIGIR_TRAVA) == EXIGIR_TRAVA
    if not exigir:
        validade.append(
            Validade(
                trava,
                "A rosca não é autotravante: sob carga, o fuso desce sozinho. É preciso freio ou "
                "trava.",
                restringe=False,
            )
        )
    feitas = tuple(validade)
    normal = 4 * forca / (sp.pi * raiz**2)
    torcao = 16 * torque / (sp.pi * raiz**3)
    pressao = forca / (sp.pi * medio * filetes * passo / 2)
    flexao = 6 * sp.Rational(38, 100) * forca / (sp.pi * raiz * passo)
    corte_fuso = 3 * forca / (2 * sp.pi * raiz * filetes * passo)
    corte_porca = 3 * forca / (2 * sp.pi * d * filetes * passo)
    cisalhamento = sp.Rational(577, 1000)
    condicoes = [
        Condicao(
            "von Mises no corpo do fuso",
            "Fuso",
            sp.sqrt(normal**2 + 3 * torcao**2),
            escoamento / n,
            "\\sigma_{vM}",
            tensoes=(("\\sigma", normal), ("\\tau", torcao)),
            validade=feitas,
        ),
        Condicao(
            "Pressão nos filetes",
            "Fuso",
            pressao,
            c.letra(g.P_ADM_FILETE, fixa=True),
            "p_{filete}",
            validade=feitas,
        ),
        Condicao(
            "Flexão no filete do fuso",
            "Fuso",
            flexao,
            escoamento / n,
            "\\sigma_{b}",
            validade=feitas,
        ),
        Condicao(
            "Corte nos filetes do fuso",
            "Fuso",
            corte_fuso,
            cisalhamento * escoamento / n,
            "\\tau_{fuso}",
            validade=feitas,
        ),
        Condicao(
            "Corte nos filetes da porca",
            "Fuso",
            corte_porca,
            cisalhamento * c.letra(g.SY_PORCA, fixa=True) / n,
            "\\tau_{porca}",
            validade=feitas,
        ),
    ]
    if exigir:
        condicoes.append(
            Condicao(
                "Autotravamento da rosca",
                "Fuso",
                avanco,
                sp.pi * atrito * medio * secante,
                "\\ell",
                validade=feitas,
            )
        )
    if c.opcoes.get("flambagem", CONFERIR_FLAMBAGEM) == CONFERIR_FLAMBAGEM:
        modulo = material.e if material else c.letra(g.E, fixa=True)
        esbeltez = c.letra(g.K_FUSO, fixa=True) * c.letra(g.L_FUSO, fixa=True) / (raiz / 4)
        critica = TensaoCritica(esbeltez, escoamento, modulo) * sp.pi * raiz**2 / 4
        condicoes.append(
            Condicao(
                "Flambagem do fuso",
                "Fuso",
                c.letra(g.N_FLAMBAGEM, fixa=True) * forca,
                critica,
                "n_{fl} \\cdot F",
                validade=feitas,
            )
        )
        c.hipoteses.append(
            "Flambagem do fuso pela raiz da rosca (r = d_r/4): Johnson na coluna curta e Euler na "
            "longa, como no Cálculo de peças."
        )
    c.hipoteses.append(
        "Fuso pelo Shigley, cap. 8: diâmetro médio d − p/2, raiz d − p e altura de contato p/2, "
        "valores aproximados das roscas trapezoidais. Na rosca normalizada, confira na tabela."
    )
    c.hipoteses.append(
        "O primeiro filete engajado leva 38 % da carga na flexão. A torção do corpo usa o torque "
        "de subida com o colar, o caso mais carregado."
    )
    c.hipoteses.append("Sem carga lateral no fuso: a guia absorve o momento.")
    return {"T": torque, "condicao": condicoes}


def _rotacao_critica(c: Contexto) -> dict[str, Any]:
    estado = c.estado()
    secao = estado.secao
    material = c.material()
    modulo = material.e if material else c.letra(g.E, fixa=True)
    vao = c.letra(g.L, fixa=True)
    densidade = c.letra(g.RHO_EIXO, fixa=True)
    rotacao = c.letra(g.ROT, fixa=True)
    folga = c.letra(g.F_CRITICA, fixa=True)
    rigidez = modulo * secao.inercia_min
    # 1/ω² de Dunkerley: o eixo sozinho, biapoiado, e a peça presa nele, cada um por si.
    inverso = densidade * secao.area * vao**4 / (sp.pi**4 * rigidez)
    massas = c.opcoes.get("massas", SO_O_EIXO)
    if massas == PECA_ENTRE_MANCAIS:
        a = c.letra(g.A_CARGA, fixa=True)
        inverso += c.letra(g.M_PECA) * a**2 * (vao - a) ** 2 / (3 * rigidez * vao)
    elif massas == PECA_EM_BALANCO:
        balanco = c.letra(g.C_BALANCO, fixa=True)
        inverso += c.letra(g.M_PECA) * balanco**2 * (vao + balanco) / (3 * rigidez)
    critica = 30 / (sp.pi * sp.sqrt(inverso))
    c.hipoteses.append(
        "Rotação crítica por Dunkerley: o eixo de seção constante entre os mancais, com a massa "
        "dele, e a peça como massa concentrada. Dunkerley fica abaixo da real, a favor da segurança."
    )
    c.hipoteses.append(
        "Mancais como apoios rígidos. A folga dos mancais e a carcaça baixam a rotação crítica."
    )
    if massas == PECA_EM_BALANCO:
        c.hipoteses.append("A massa do trecho do eixo em balanço não entra na parcela do eixo.")
    return {
        "condicao": [
            Condicao(
                "Rotação crítica",
                "Rotação crítica",
                folga * rotacao,
                critica,
                "f_{cr} \\cdot n",
                "",
                (("n_{cr}", critica),),
                estado.validade,
            )
        ]
    }


BLOCOS_PECAS: tuple[Bloco, ...] = (
    Bloco(
        "engrenagem",
        "Engrenagem",
        GRUPO_ORIGEM,
        "Da potência e do diâmetro primitivo saem as forças que dobram o eixo: F_t, F_r e F_a.",
        "F_t = 2·T/d · F_r = F_t·tg φ",
        (_ENTRA_TORQUE,),
        (
            Porta("T", "T", VALOR, g.MOMENTO),
            Porta("F_t", "F_t", VALOR, g.FORCA),
            Porta("F_r", "F_r", VALOR, g.FORCA),
            Porta("F_a", "F_a", VALOR, g.FORCA),
        ),
        _engrenagem,
        (_COMO_ENTRA_O_TORQUE,),
        numerar=True,
    ),
    Bloco(
        "polia",
        "Polia e correia",
        GRUPO_ORIGEM,
        "Da potência e do diâmetro da polia sai a força que a correia faz no eixo.",
        "F = √(F₁² + F₂² − 2·F₁·F₂·cos θ)",
        (_ENTRA_TORQUE,),
        (
            Porta("T", "T", VALOR, g.MOMENTO),
            Porta("F", "F", VALOR, g.FORCA),
            Porta("F_1", "F₁", VALOR, g.FORCA),
        ),
        _polia,
        (_COMO_ENTRA_O_TORQUE, _TIPO_DE_CORREIA),
        numerar=True,
    ),
    Bloco(
        "par_engrenagens",
        "Par de engrenagens",
        GRUPO_PECAS,
        "O par inteiro: as forças no eixo e o dente, por flexão (Lewis) e por contato. Isola o "
        "módulo, a largura ou a dureza.",
        "σ = K_o·K_v·K_m·F_t/(b·m·Y)",
        (_ENTRA_TORQUE, _MATERIAL),
        (
            Porta("T", "T", VALOR, g.MOMENTO),
            Porta("F_t", "F_t", VALOR, g.FORCA),
            Porta("F_r", "F_r", VALOR, g.FORCA),
            Porta("F_a", "F_a", VALOR, g.FORCA),
            _SAI_CONDICAO,
        ),
        _par_de_engrenagens,
        (
            _COMO_ENTRA_O_TORQUE,
            _QUAL_EIXO,
            Opcao(
                "processo",
                "Fabricação do dente",
                "Dá o fator dinâmico K_v: dente mais preciso sofre menos choque. Caracol (hob) é o "
                "processo comum; retificado, o de precisão.",
                et.PROCESSOS,
                PROCESSO_PADRAO,
            ),
            Opcao(
                "grau",
                "Qualidade do aço (AGMA)",
                "Grau 1: aço comercial. Grau 2: aço com controle de limpeza e de tratamento "
                "térmico, com resistência maior.",
                et.GRAUS_AGMA,
                et.GRAUS_AGMA[0],
            ),
        ),
        numerar=True,
    ),
    Bloco(
        "engrenagem_conica",
        "Engrenagem cônica",
        GRUPO_ORIGEM,
        "Par cônico de dente reto, com os eixos a 90°: as forças no eixo do pinhão ou da coroa.",
        "F_t = 2·T/d_m · F_r = F_t·tg φ·cos γ",
        (_ENTRA_TORQUE,),
        (
            Porta("T", "T", VALOR, g.MOMENTO),
            Porta("F_t", "F_t", VALOR, g.FORCA),
            Porta("F_r", "F_r", VALOR, g.FORCA),
            Porta("F_a", "F_a", VALOR, g.FORCA),
            Porta("r_m", "r_m", VALOR, g.MEDIDA),
        ),
        _conica,
        (_COMO_ENTRA_O_TORQUE, _QUAL_EIXO),
        numerar=True,
    ),
    Bloco(
        "chaveta",
        "Chaveta",
        GRUPO_PECAS,
        "Chaveta paralela: corte e esmagamento no eixo, no cubo e na própria chaveta.",
        "F = 2·K_s·T/d",
        (_ENTRA_TORQUE, _ENTRA_D, _MATERIAL),
        (_SAI_CONDICAO,),
        _chaveta,
        (
            Opcao(
                "dimensoes",
                "Dimensões",
                "Pela DIN 6885, b, h e t₁ saem do diâmetro, e mudam com ele. Informar serve para "
                "chaveta especial ou em polegadas.",
                (DIN_6885, CHAVETA_INFORMADA),
                DIN_6885,
            ),
            Opcao(
                "pontas",
                "Pontas",
                "Arredondadas: a parte redonda não carrega, e o comprimento útil é L_ch − b. "
                "Retas: o útil é L_ch.",
                (PONTAS_ARREDONDADAS, PONTAS_RETAS),
                PONTAS_ARREDONDADAS,
            ),
            Opcao(
                "quantas",
                "Quantidade",
                "Duas chavetas a 180° contam como 1,5: o ajuste nunca divide a carga por igual.",
                (UMA_CHAVETA, DUAS_CHAVETAS),
                UMA_CHAVETA,
            ),
        ),
        numerar=True,
    ),
    Bloco(
        "cubo_prensado",
        "Cubo prensado",
        GRUPO_PECAS,
        "Ajuste com interferência: o torque que o aperto segura e a tensão no cubo e no eixo.",
        "T ≤ π·μ·p·d·L·d/2",
        (_ENTRA_TORQUE, Porta("F_ac", "F_ac", VALOR, g.FORCA), _ENTRA_D, _MATERIAL),
        (_SAI_CONDICAO,),
        _cubo_prensado,
        (
            Opcao(
                "ajuste",
                "Ajuste",
                "De H7/p6 a H7/u6 a interferência sai das tabelas da NBR 6158 e muda com o "
                "diâmetro. Quanto maior a letra do eixo, mais forte o aperto.",
                (*AJUSTES_DO_CUBO, ee.AJUSTE_MANUAL),
                AJUSTE_PADRAO,
            ),
        ),
        numerar=True,
    ),
    Bloco(
        "rolamento",
        "Rolamento",
        GRUPO_PECAS,
        "Ligue a reação do mancal e diga a vida em horas: sai a capacidade C que o rolamento "
        "precisa ter.",
        "L = a₁·(C/P)^p",
        (
            Porta("R", "R", VALOR, g.FORCA),
            Porta("R_2", "R", VALOR, g.FORCA),
            Porta("F_am", "F_am", VALOR, g.FORCA),
        ),
        (_SAI_CONDICAO,),
        _rolamento,
        (
            Opcao(
                "tipo",
                "Tipo de rolamento",
                "Esferas de sulco profundo: o programa acha X e Y. Nos outros, copie X e Y do "
                "catálogo. O expoente da vida é 3 em esferas e 10/3 em rolos.",
                TIPOS_DE_ROLAMENTO,
                ESFERAS,
            ),
            Opcao(
                "confiabilidade",
                "Confiabilidade",
                "A vida L₁₀ é a que 90 % dos rolamentos alcançam. Pedir mais reduz a vida pelo "
                "fator a₁ da ISO 281.",
                tuple(em.A1_CONFIABILIDADE),
                "90 %",
            ),
        ),
        numerar=True,
    ),
    Bloco(
        "fuso",
        "Fuso (parafuso de potência)",
        GRUPO_PECAS,
        "Rosca que transforma giro em força: o torque para subir, o corpo, os filetes, a "
        "flambagem e se ele trava sozinho. Isola o diâmetro, o passo ou a carga.",
        "T = F·d_m/2·(ℓ + π·μ·d_m·sec α)/(π·d_m − μ·ℓ·sec α)",
        (Porta("F", "F", VALOR, g.FORCA), _MATERIAL),
        (Porta("T", "T", VALOR, g.MOMENTO), _SAI_CONDICAO),
        _fuso,
        (
            Opcao(
                "rosca",
                "Rosca",
                "Trapezoidal ISO é a usual no Brasil (Tr 40×7). Quadrada rende mais, mas é cara de "
                "fazer. O ângulo do filete aumenta o atrito.",
                tuple(ema.ROSCAS),
                ema.ROSCA_TRAPEZOIDAL,
            ),
            Opcao(
                "colar",
                "Colar",
                "O colar é onde o fuso ou a porca encosta e gira: com atrito, ele soma torque.",
                (COM_COLAR, SEM_COLAR),
                COM_COLAR,
            ),
            Opcao(
                "flambagem",
                "Flambagem",
                "Fuso que empurra a carga trabalha comprimido e pode flambar. Se ele só puxa, não.",
                (CONFERIR_FLAMBAGEM, SO_TRACIONADO),
                CONFERIR_FLAMBAGEM,
            ),
            Opcao(
                "trava",
                "Autotravamento",
                "Exigir faz a rosca segurar a carga parada sem freio. Vibração reduz o atrito: em "
                "carga sobre pessoas, ponha freio ou trava mesmo assim.",
                (NAO_EXIGIR_TRAVA, EXIGIR_TRAVA),
                NAO_EXIGIR_TRAVA,
            ),
        ),
        numerar=True,
    ),
    Bloco(
        "inclinacao",
        "Inclinação",
        GRUPO_CRITERIO,
        "Rigidez do eixo no mancal ou na engrenagem. Liga a seção e a saída θ·EI das vigas: uma "
        "por plano.",
        "θ = (θ·EI)/(E·I)",
        (
            _ENTRADA,
            Porta("giro", "θ·EI", VALOR, g.GIRO_EI),
            Porta("giro_2", "θ·EI", VALOR, g.GIRO_EI),
            _MATERIAL,
        ),
        (_SAI_CONDICAO,),
        _inclinacao,
        (
            Opcao(
                "limite",
                "Limite",
                "O mancal e a engrenagem aceitam pouco giro: o rolamento esquenta e o dente toca "
                "só numa ponta. Valores da Tabela 7-2 de Shigley.",
                (*LIMITES_DE_INCLINACAO, INFORMAR_INCLINACAO),
                next(iter(LIMITES_DE_INCLINACAO)),
            ),
        ),
    ),
    Bloco(
        "rotacao_critica",
        "Rotação crítica",
        GRUPO_CRITERIO,
        "O eixo não pode girar perto da frequência em que ele vibra sozinho.",
        "f_cr·n ≤ n_cr",
        (_ENTRADA, _MATERIAL),
        (_SAI_CONDICAO,),
        _rotacao_critica,
        (
            Opcao(
                "massas",
                "O que gira junto",
                "A massa do eixo sempre entra. Engrenagem, polia ou volante pesam mais: ponha a "
                "peça entre os mancais ou em balanço.",
                (SO_O_EIXO, PECA_ENTRE_MANCAIS, PECA_EM_BALANCO),
                SO_O_EIXO,
            ),
        ),
    ),
)

mb.registrar(BLOCOS_PECAS)
