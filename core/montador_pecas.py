"""As peças de um eixo no Montador: o que entrega o esforço e o que o eixo carrega.

A engrenagem e a polia dão as forças que dobram o eixo. A chaveta, o cubo prensado e o rolamento
são as peças que ficam nele, cada uma com as condições que a fazem passar. A inclinação e a rotação
crítica dizem se o eixo, além de aguentar, fica rígido o bastante.

As contas são as do Assistente de cargas (``core/elementos_eixos.py``, ``elementos_transmissao.py`` e
``elementos_mancais.py``), escritas em letras: o Montador e o Assistente têm de dar o mesmo número.
Os blocos entram no catálogo por ``montador_blocos.registrar``, como os de fluidos.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import sympy as sp

from core import elementos_eixos as ee
from core import elementos_mancais as em
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
    InterferenciaMaxima,
    InterferenciaMinima,
    LarguraDaChaveta,
    RasgoDaChaveta,
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
        "Forças de engrenamento no diâmetro primitivo, como no Assistente de cargas: F_t = 2·T/d, "
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
        "use o rolamento do Assistente de cargas."
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
