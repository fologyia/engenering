"""Mancais e contato: rolamento, bucha, pino de articulação e contato de Hertz."""

from __future__ import annotations

import math

from core.elementos_base import (
    Campo,
    Caso,
    Metrica,
    Ponto,
    Resultado,
    Valores,
    exigir,
    faixa_recomendada,
    informativo,
    limite,
    minimo,
    recomendacao_minima,
)

GRUPO = "Mancais, pinos e contato"

ISO_281 = "ISO 281:2007 (vida básica e fator a₁)"
SHIGLEY_11 = "Shigley, Elementos de Máquinas, cap. 11"
SHIGLEY_3 = "Shigley, Elementos de Máquinas, cap. 3"
NBR_8400_ROL = "ABNT NBR 8400:1984, 6.7.1 e Tabela 20"
EN_1993 = "EN 1993-1-8, Tabela 3.10 (momento no pino)"
JOHNSON = "Johnson, Contact Mechanics, cap. 4 e 6"

#: Fator de vida para a confiabilidade (ISO 281:2007).
A1_CONFIABILIDADE = {
    "90 %": 1.0,
    "95 %": 0.64,
    "96 %": 0.55,
    "97 %": 0.47,
    "98 %": 0.37,
    "99 %": 0.25,
}

#: Fa/C0, e, Y2 do rolamento rígido de esferas (Shigley, Tabela 11-1); X2 = 0,56.
_TABELA_XY = (
    (0.014, 0.19, 2.30),
    (0.021, 0.21, 2.15),
    (0.028, 0.22, 1.99),
    (0.042, 0.24, 1.85),
    (0.056, 0.26, 1.71),
    (0.070, 0.27, 1.63),
    (0.084, 0.28, 1.55),
    (0.110, 0.30, 1.45),
    (0.170, 0.34, 1.31),
    (0.280, 0.38, 1.15),
    (0.420, 0.42, 1.04),
    (0.560, 0.44, 1.00),
)

#: NBR 8400, Tabela 20: duração teórica de utilização por classe de funcionamento, em horas.
VIDA_POR_CLASSE = {
    "V0,25": 800.0,
    "V0,5": 1600.0,
    "V1": 3200.0,
    "V2": 6300.0,
    "V3": 12500.0,
    "V4": 25000.0,
    "V5": 50000.0,
}
#: NBR 8400, Tabela 22: média cúbica K de cada estado de solicitação.
MEDIA_CUBICA = {"1": 0.53, "2": 0.67, "3": 0.85}

TIPOS_ROLAMENTO = (
    "Esferas, sulco profundo",
    "Esferas, X e Y informados",
    "Rolos, X e Y informados",
)
REGIME_CONSTANTE = "Carga constante"
REGIME_SM = "NBR 8400: força vinda do motor (K·F_máx)"
REGIME_SR = "NBR 8400: reação da carga ((2F_máx + F_mín)/3)"
REGIMES = (REGIME_CONSTANTE, REGIME_SM, REGIME_SR)
VIDA_INFORMADA = "Informar em horas"


def _milhar(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", " ")


def fatores_xy(fa: float, fr: float, c0: float) -> tuple[float, float, float]:
    """X, Y e e do rolamento rígido de esferas, interpolando Y e e em Fa/C0."""
    if fa <= 0:
        return 1.0, 0.0, 0.0
    relacao = min(max(fa / c0, _TABELA_XY[0][0]), _TABELA_XY[-1][0])
    for (r1, e1, y1), (r2, e2, y2) in zip(_TABELA_XY, _TABELA_XY[1:], strict=False):
        if r1 <= relacao <= r2:
            t = (relacao - r1) / (r2 - r1)
            e = e1 + t * (e2 - e1)
            y = y1 + t * (y2 - y1)
            break
    if fr > 0 and fa / fr <= e:
        return 1.0, 0.0, e
    return 0.56, y, e


def calcular_rolamento(v: Valores) -> Resultado:
    tipo = str(v["tipo"])
    regime = str(v["regime"])
    fr = float(v["fr_kN"]) * 1000.0
    fa = float(v["fa_kN"]) * 1000.0
    rotacao = float(v["rotacao_rpm"])
    c = float(v["c_kN"]) * 1000.0
    c0 = float(v["c0_kN"]) * 1000.0
    fator = float(v["fator_aplicacao"])
    a1 = A1_CONFIABILIDADE[str(v["confiabilidade"])]
    exigir(fr + fa > 0, "Informe a força radial ou a axial.")
    expoente = 3.0 if tipo.startswith("Esferas") else 10.0 / 3.0

    estado = str(v["estado"])
    if regime == REGIME_SM:
        fr_media = MEDIA_CUBICA[estado] * fr
    elif regime == REGIME_SR:
        fr_media = (2.0 * fr + float(v["fr_min_kN"]) * 1000.0) / 3.0
    else:
        fr_media = fr

    if tipo == "Esferas, sulco profundo":
        x, y, e = fatores_xy(fa, fr_media, c0)
    else:
        x = float(v["x"])
        y = float(v["y"])
        e = 0.0
    equivalente = max(fr_media, x * fr_media + y * fa) * fator
    p0 = max(fr, 0.6 * fr + 0.5 * fa)

    l10 = (c / equivalente) ** expoente
    l10h = 1e6 * l10 / (60.0 * rotacao)
    vida = a1 * l10h
    if str(v["criterio_vida"]) == VIDA_INFORMADA:
        exigida = float(v["vida_h"])
        origem = "vida pedida pelo projeto"
    else:
        exigida = VIDA_POR_CLASSE[str(v["criterio_vida"])]
        origem = f"NBR 8400, Tabela 20, classe {v['criterio_vida']}"
    c_necessario = equivalente * (60.0 * rotacao * exigida / (1e6 * a1)) ** (1.0 / expoente)
    s0 = c0 / p0
    carga_minima = (0.01 if tipo.startswith("Esferas") else 0.02) * c

    verificacoes = (
        minimo(
            "Vida do rolamento",
            vida,
            exigida,
            "h",
            f"L = a₁·(C/P)^p·10⁶/(60n), com P = {equivalente:.0f} N e {origem}",
            ISO_281,
        ),
        minimo(
            "Segurança estática s₀",
            s0,
            float(v["s0_minimo"]),
            "—",
            f"s₀ = C₀/P₀, com P₀ = {p0:.0f} N",
            "ISO 76 (capacidade estática)",
        ),
        recomendacao_minima(
            "Carga mínima para o rolamento rolar",
            equivalente,
            carga_minima,
            "N",
            "P ≥ 0,01·C em esferas e 0,02·C em rolos: abaixo disso os corpos deslizam",
            "Prática de catálogo (SKF)",
        ),
    )
    return Resultado(
        resumo=(
            f"Carga equivalente de {equivalente / 1000:.2f} kN: vida de {_milhar(vida)} h "
            f"(exigida: {_milhar(exigida)} h). C necessário: {c_necessario / 1000:.1f} kN."
        ),
        metricas=(
            Metrica("Vida ajustada", vida, "h", 0),
            Metrica("Vida básica L₁₀h", l10h, "h", 0),
            Metrica("Carga equivalente P", equivalente / 1000.0, "kN"),
            Metrica("C necessário", c_necessario / 1000.0, "kN", 1),
            Metrica("Segurança estática s₀", s0, "", 2),
            Metrica("Fator X", x, "", 2),
            Metrica("Fator Y", y, "", 2),
            Metrica("Razão e", e, "", 3),
        ),
        verificacoes=verificacoes,
        hipoteses=(
            "Vida calculada com lubrificação adequada e sem contaminação severa (a_ISO = 1).",
            "Fatores a₁ da ISO 281:2007. Confira na norma quando a confiabilidade for exigência "
            "contratual.",
            "Em esferas de sulco profundo, X e Y saem da Tabela 11-1 de Shigley; nos outros "
            "tipos, do catálogo do rolamento.",
            "O fator de aplicação multiplica a carga equivalente.",
            "A carga estática P₀ vale para rolamento de esferas de sulco profundo; nos outros "
            "tipos, use o valor de P₀ do catálogo.",
        ),
        referencias=(ISO_281, SHIGLEY_11, NBR_8400_ROL),
    )


CAMPOS_ROLAMENTO = (
    Campo(
        "tipo",
        "Tipo de rolamento",
        "Esferas de sulco profundo: o programa acha X e Y. Nos outros, copie X e Y do catálogo. "
        "O expoente da vida é 3 em esferas e 10/3 em rolos.",
        TIPOS_ROLAMENTO[0],
        opcoes=TIPOS_ROLAMENTO,
        secao="Rolamento",
    ),
    Campo(
        "c_kN",
        "Capacidade dinâmica C",
        "Capacidade de carga dinâmica, do catálogo do rolamento.",
        62.0,
        "kN",
        minimo=0.01,
        passo=1.0,
        secao="Rolamento",
    ),
    Campo(
        "c0_kN",
        "Capacidade estática C₀",
        "Capacidade de carga estática, do catálogo do rolamento.",
        44.0,
        "kN",
        minimo=0.01,
        passo=1.0,
        secao="Rolamento",
    ),
    Campo(
        "x",
        "Fator radial X",
        "Fator X do catálogo para a relação Fa/Fr do caso.",
        0.56,
        minimo=0.0,
        maximo=2.0,
        passo=0.01,
        secao="Rolamento",
        quando=("tipo", TIPOS_ROLAMENTO[1:]),
    ),
    Campo(
        "y",
        "Fator axial Y",
        "Fator Y do catálogo para a relação Fa/Fr do caso.",
        1.5,
        minimo=0.0,
        maximo=5.0,
        passo=0.01,
        secao="Rolamento",
        quando=("tipo", TIPOS_ROLAMENTO[1:]),
    ),
    Campo(
        "fr_kN",
        "Força radial F_r",
        "Reação radial no mancal. Em regime variável, a maior delas.",
        5.0,
        "kN",
        minimo=0.0,
        passo=0.5,
        secao="Carga",
    ),
    Campo(
        "fa_kN",
        "Força axial F_a",
        "Força na direção do eixo que este rolamento segura.",
        1.0,
        "kN",
        minimo=0.0,
        passo=0.5,
        secao="Carga",
    ),
    Campo(
        "rotacao_rpm",
        "Rotação",
        "Rotação do anel que gira.",
        300.0,
        "rpm",
        minimo=0.1,
        passo=10.0,
        secao="Carga",
    ),
    Campo(
        "fator_aplicacao",
        "Fator de aplicação",
        "Cobre as cargas que o cálculo não vê. Transmissão por engrenagens de precisão: 1,0 a 1,2. "
        "Máquinas com choque leve: 1,2 a 1,5. Britador, moinho, peneira: 1,5 a 3,0.",
        1.2,
        minimo=1.0,
        maximo=4.0,
        passo=0.05,
        secao="Carga",
    ),
    Campo(
        "regime",
        "Regime de carga",
        "Em equipamento de içamento, a NBR 8400 troca a carga máxima por uma carga média. Força "
        "vinda do motor: K·F_máx. Reação da carga: (2F_máx + F_mín)/3.",
        REGIME_CONSTANTE,
        opcoes=REGIMES,
        secao="Carga",
    ),
    Campo(
        "estado",
        "Estado de solicitação",
        "Da Tabela 21 da NBR 8400. Estado 1: quase sempre carga reduzida. Estado 2: reduzidas, "
        "médias e máximas por tempos iguais. Estado 3: quase sempre perto da máxima.",
        "2",
        opcoes=("1", "2", "3"),
        secao="Carga",
        quando=("regime", (REGIME_SM,)),
    ),
    Campo(
        "fr_min_kN",
        "Força radial mínima",
        "A menor reação no mancal durante o serviço, normalmente com o equipamento sem carga.",
        1.0,
        "kN",
        minimo=0.0,
        passo=0.5,
        secao="Carga",
        quando=("regime", (REGIME_SR,)),
    ),
    Campo(
        "criterio_vida",
        "Vida exigida",
        "A vida que o rolamento precisa dar. Máquinas comuns de 8 h/dia: de 10 a 25 mil horas. "
        "24 h/dia: de 40 a 60 mil horas. As classes V são as da Tabela 20 da NBR 8400.",
        VIDA_INFORMADA,
        opcoes=(VIDA_INFORMADA, *VIDA_POR_CLASSE),
        secao="Exigências",
    ),
    Campo(
        "vida_h",
        "Vida em horas",
        "Vida exigida em horas de operação.",
        20000.0,
        "h",
        minimo=1.0,
        passo=1000.0,
        secao="Exigências",
        quando=("criterio_vida", (VIDA_INFORMADA,)),
    ),
    Campo(
        "confiabilidade",
        "Confiabilidade",
        "A vida L₁₀ é a que 90 % dos rolamentos alcançam. Pedir mais confiabilidade reduz a vida "
        "pelo fator a₁ da ISO 281:2007.",
        "90 %",
        opcoes=tuple(A1_CONFIABILIDADE),
        secao="Exigências",
    ),
    Campo(
        "s0_minimo",
        "s₀ mínimo",
        "Segurança estática exigida. Serviço silencioso e suave: 2. Normal: 1. Com choques: 1,5 a "
        "3. Rolamento parado ou oscilando: a partir de 1.",
        1.5,
        minimo=0.5,
        maximo=6.0,
        passo=0.1,
        secao="Exigências",
    ),
)


# ---------------------------------------------------------------------------
# Bucha
# ---------------------------------------------------------------------------


def calcular_bucha(v: Valores) -> Resultado:
    forca = float(v["forca_kN"]) * 1000.0
    d = float(v["d_mm"])
    largura = float(v["largura_mm"])
    movimento = str(v["movimento"])
    if movimento == "Rotação contínua":
        velocidade = math.pi * d * float(v["rotacao_rpm"]) / 60_000.0
    else:
        # Num ciclo o pino vai e volta: percorre 2·θ, com θ o giro total de uma ponta à outra.
        giro = math.radians(float(v["giro_graus"]))
        ciclos_s = float(v["ciclos_min"]) / 60.0
        velocidade = 2.0 * giro * (d / 2.0 / 1000.0) * ciclos_s
    pressao = forca / (d * largura)
    pv = pressao * velocidade
    verificacoes = (
        limite(
            "Pressão na bucha",
            pressao,
            float(v["p_adm_MPa"]),
            "MPa",
            "p = F/(d·L) na área projetada",
            "Catálogo do material da bucha",
        ),
        limite(
            "Velocidade de deslizamento",
            velocidade,
            float(v["v_adm_m_s"]),
            "m/s",
            "V = π·d·n/60000, ou a média do giro em oscilação",
            "Catálogo do material da bucha",
        ),
        limite(
            "Produto pV",
            pv,
            float(v["pv_adm"]),
            "MPa·m/s",
            f"pV = {pressao:.2f}·{velocidade:.4f}: mede o calor gerado no atrito",
            "Catálogo do material da bucha",
        ),
        faixa_recomendada(
            "Proporção L/d",
            largura / d,
            0.5,
            1.5,
            "—",
            "0,5 ≤ L/d ≤ 1,5: bucha longa encosta só nas pontas",
            "Norton, Projeto de Máquinas, cap. 10",
        ),
    )
    return Resultado(
        resumo=(f"Pressão de {pressao:.2f} MPa a {velocidade:.3f} m/s: pV = {pv:.3f} MPa·m/s."),
        metricas=(
            Metrica("Pressão p", pressao, "MPa"),
            Metrica("Velocidade V", velocidade, "m/s", 3),
            Metrica("Produto pV", pv, "MPa·m/s", 3),
            Metrica("Calor no atrito", float(v["atrito"]) * forca * velocidade, "W", 0),
        ),
        verificacoes=verificacoes,
        hipoteses=(
            "Mancal seco ou com lubrificação limite: a pressão é a média na área projetada.",
            "Os limites padrão são típicos de bronze e devem ser trocados pelos do fabricante.",
            "Mancal hidrodinâmico (filme de óleo cheio) não é tratado aqui.",
        ),
        referencias=("Norton, Projeto de Máquinas, cap. 10",),
    )


CAMPOS_BUCHA = (
    Campo(
        "forca_kN",
        "Força radial F",
        "A força que o eixo ou pino faz sobre a bucha.",
        20.0,
        "kN",
        minimo=0.0,
        passo=1.0,
        secao="Carga",
    ),
    Campo(
        "movimento",
        "Movimento",
        "Rotação contínua: eixo girando sempre no mesmo sentido. Oscilação: pino de articulação "
        "que vai e volta, como os de cilindro hidráulico.",
        "Oscilação",
        opcoes=("Oscilação", "Rotação contínua"),
        secao="Carga",
    ),
    Campo(
        "rotacao_rpm",
        "Rotação",
        "Rotação do eixo na bucha.",
        60.0,
        "rpm",
        minimo=0.0,
        passo=5.0,
        secao="Carga",
        quando=("movimento", ("Rotação contínua",)),
    ),
    Campo(
        "giro_graus",
        "Giro total",
        "Ângulo de uma ponta à outra do movimento.",
        60.0,
        "°",
        minimo=0.0,
        maximo=360.0,
        passo=5.0,
        secao="Carga",
        quando=("movimento", ("Oscilação",)),
    ),
    Campo(
        "ciclos_min",
        "Ciclos por minuto",
        "Quantas vezes por minuto o pino vai e volta.",
        6.0,
        "ciclos/min",
        minimo=0.0,
        passo=1.0,
        secao="Carga",
        quando=("movimento", ("Oscilação",)),
    ),
    Campo(
        "d_mm",
        "Diâmetro interno d",
        "Diâmetro do eixo ou do pino dentro da bucha.",
        50.0,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Bucha",
    ),
    Campo(
        "largura_mm",
        "Largura da bucha L",
        "Comprimento de contato.",
        50.0,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Bucha",
    ),
    Campo(
        "p_adm_MPa",
        "Pressão admissível",
        "Limite de pressão do material. Bronze fundido, serviço leve: cerca de 25 MPa. "
        "Copie o valor do fabricante da bucha.",
        25.0,
        "MPa",
        minimo=0.1,
        passo=1.0,
        secao="Limites do material",
    ),
    Campo(
        "v_adm_m_s",
        "Velocidade admissível",
        "Limite de velocidade do material. Bronze fundido lubrificado: cerca de 2,5 m/s.",
        2.5,
        "m/s",
        minimo=0.001,
        passo=0.1,
        secao="Limites do material",
    ),
    Campo(
        "pv_adm",
        "pV admissível",
        "Limite do produto pressão × velocidade. Bronze fundido com graxa: cerca de 1,75 MPa·m/s.",
        1.75,
        "MPa·m/s",
        minimo=0.001,
        passo=0.05,
        secao="Limites do material",
    ),
    Campo(
        "atrito",
        "Coeficiente de atrito μ",
        "Bronze com aço, com graxa: cerca de 0,10 a 0,15. Serve para estimar o calor gerado.",
        0.12,
        minimo=0.01,
        maximo=0.6,
        passo=0.01,
        secao="Limites do material",
    ),
)


# ---------------------------------------------------------------------------
# Pino de articulação
# ---------------------------------------------------------------------------


def calcular_pino(v: Valores) -> Resultado:
    forca = float(v["forca_kN"]) * 1000.0 * float(v["fator_dinamico"])
    d = float(v["d_mm"])
    t_olhal = float(v["t_olhal_mm"])
    t_garfo = float(v["t_garfo_mm"])
    folga = float(v["folga_mm"])
    fs = float(v["fs"])
    sy_pino = float(v["sy_pino_MPa"])
    sy_chapa = float(v["sy_chapa_MPa"])

    area = math.pi * d**2 / 4.0
    tau_medio = forca / (2.0 * area)
    tau_max = 4.0 / 3.0 * tau_medio
    momento = forca / 8.0 * (t_olhal + 4.0 * folga + 2.0 * t_garfo)
    sigma = 32.0 * momento / (math.pi * d**3)
    p_olhal = forca / (d * t_olhal)
    p_garfo = forca / (2.0 * d * t_garfo)
    interacao = (sigma / (sy_pino / fs)) ** 2 + (tau_medio / (0.577 * sy_pino / fs)) ** 2
    verificacoes = (
        limite(
            "Flexão no pino",
            sigma,
            sy_pino / fs,
            "MPa",
            f"M = F/8·(b + 4c + 2a) = {momento / 1000:.1f} N·m; σ = 32M/(π·d³)",
            EN_1993,
        ),
        limite(
            "Cisalhamento no pino (2 planos)",
            tau_max,
            0.577 * sy_pino / fs,
            "MPa",
            "τ_máx = 4/3·F/(2A), o pico no centro da seção",
            "Corte em seção circular maciça",
        ),
        limite(
            "Flexão com cortante",
            interacao,
            1.0,
            "—",
            "(σ/σ_adm)² + (τ/τ_adm)² ≤ 1",
            EN_1993,
        ),
        limite(
            "Esmagamento no olhal central",
            p_olhal,
            sy_chapa / fs,
            "MPa",
            "p = F/(d·b)",
            "Pressão de contato média",
        ),
        limite(
            "Esmagamento no garfo",
            p_garfo,
            sy_chapa / fs,
            "MPa",
            "p = F/(2·d·a)",
            "Pressão de contato média",
        ),
    )
    alertas = []
    if d < 3.0 * folga:
        alertas.append(
            "Folga grande perto do diâmetro: o pino trabalha mais à flexão que ao corte."
        )
    return Resultado(
        resumo=(
            f"Com F = {forca / 1000:.1f} kN de projeto, o pino flete a {sigma:.0f} MPa e corta a "
            f"{tau_max:.0f} MPa."
        ),
        metricas=(
            Metrica("Momento no pino", momento / 1000.0, "N·m", 1),
            Metrica("Flexão σ", sigma, "MPa", 1),
            Metrica("Cisalhamento τ máx", tau_max, "MPa", 1),
            Metrica("Esmagamento no olhal", p_olhal, "MPa", 1),
            Metrica("Esmagamento no garfo", p_garfo, "MPa", 1),
        ),
        verificacoes=verificacoes,
        pontos=(
            Ponto("Fibra extrema, meio do pino", sigma, 0.0, 0.0),
            Ponto("Centro da seção, plano de corte", 0.0, 0.0, tau_max),
        ),
        alertas=tuple(alertas),
        hipoteses=(
            "Pino biapoiado no garfo, com carga distribuída no olhal e no garfo.",
            "Cada lado do garfo recebe metade da força.",
            "Pino com folga de rotação: sem pré-carga e com contato distribuído.",
        ),
        referencias=(EN_1993,),
    )


CAMPOS_PINO = (
    Campo(
        "forca_kN",
        "Força no pino F",
        "A força total que passa do olhal para o garfo.",
        100.0,
        "kN",
        minimo=0.0,
        passo=5.0,
        secao="Carga",
    ),
    Campo(
        "fator_dinamico",
        "Fator dinâmico",
        "Multiplica a força para cobrir choques. Cilindro hidráulico suave: 1,0 a 1,25. "
        "Içamento: use o ψ da NBR 8400 (caso Ações de içamento).",
        1.25,
        minimo=1.0,
        maximo=4.0,
        passo=0.05,
        secao="Carga",
    ),
    Campo(
        "fs",
        "Fator de segurança",
        "Margem sobre o escoamento. Comece com 2,0.",
        2.0,
        minimo=1.0,
        maximo=6.0,
        passo=0.1,
        secao="Carga",
    ),
    Campo(
        "d_mm",
        "Diâmetro do pino d",
        "Diâmetro do pino nos planos de corte.",
        40.0,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Geometria",
    ),
    Campo(
        "t_olhal_mm",
        "Espessura do olhal b",
        "Espessura da chapa central.",
        40.0,
        "mm",
        minimo=0.5,
        passo=1.0,
        secao="Geometria",
    ),
    Campo(
        "t_garfo_mm",
        "Espessura de cada lado do garfo a",
        "Espessura de uma das chapas externas.",
        20.0,
        "mm",
        minimo=0.5,
        passo=1.0,
        secao="Geometria",
    ),
    Campo(
        "folga_mm",
        "Folga entre olhal e garfo c",
        "Espaço vazio entre a chapa central e cada lado do garfo. Quanto maior, maior o momento "
        "no pino.",
        2.0,
        "mm",
        minimo=0.0,
        passo=0.5,
        secao="Geometria",
    ),
    Campo(
        "sy_pino_MPa",
        "Escoamento do pino",
        "Pino de aço temperado AISI 4140: cerca de 650 a 760 MPa.",
        650.0,
        "MPa",
        minimo=10.0,
        passo=10.0,
        secao="Materiais",
    ),
    Campo(
        "sy_chapa_MPa",
        "Escoamento das chapas",
        "Limite de escoamento do olhal e do garfo. Com bucha, use o limite do material da bucha.",
        345.0,
        "MPa",
        minimo=10.0,
        passo=5.0,
        secao="Materiais",
    ),
)


# ---------------------------------------------------------------------------
# Contato de Hertz
# ---------------------------------------------------------------------------

GEOMETRIA_ESFERA_PLANO = "Esfera sobre plano"
GEOMETRIA_ESFERAS = "Esfera contra esfera"
GEOMETRIA_CILINDRO_PLANO = "Cilindro sobre plano"
GEOMETRIA_CILINDROS = "Cilindro contra cilindro"
GEOMETRIAS = (
    GEOMETRIA_CILINDRO_PLANO,
    GEOMETRIA_CILINDROS,
    GEOMETRIA_ESFERA_PLANO,
    GEOMETRIA_ESFERAS,
)
GEOMETRIAS_LINHA = (GEOMETRIA_CILINDRO_PLANO, GEOMETRIA_CILINDROS)
GEOMETRIAS_DUAS = (GEOMETRIA_CILINDROS, GEOMETRIA_ESFERAS)


def contato_de_hertz(
    geometria: str,
    forca_N: float,
    d1: float,
    d2: float,
    comprimento: float,
    E1: float,
    nu1: float,
    E2: float,
    nu2: float,
) -> dict[str, float]:
    """Semilargura, pressão máxima e profundidade do cisalhamento máximo, em mm e MPa."""
    e_efetivo = 1.0 / ((1.0 - nu1**2) / E1 + (1.0 - nu2**2) / E2)
    curvatura = 2.0 / d1 + (2.0 / d2 if geometria in GEOMETRIAS_DUAS else 0.0)
    raio = 1.0 / curvatura
    if geometria in GEOMETRIAS_LINHA:
        por_mm = forca_N / comprimento
        b = math.sqrt(4.0 * por_mm * raio / (math.pi * e_efetivo))
        p0 = 2.0 * por_mm / (math.pi * b)
        return {
            "a": b,
            "p0": p0,
            "tau_max": 0.30 * p0,
            "z": 0.78 * b,
            "von_mises": 0.56 * p0,
            "limite_escoamento": 1.79,
            "aproximacao": 0.0,
        }
    a = (3.0 * forca_N * raio / (4.0 * e_efetivo)) ** (1.0 / 3.0)
    p0 = 3.0 * forca_N / (2.0 * math.pi * a**2)
    return {
        "a": a,
        "p0": p0,
        "tau_max": 0.31 * p0,
        "z": 0.48 * a,
        "von_mises": 0.62 * p0,
        "limite_escoamento": 1.61,
        "aproximacao": a**2 / raio,
    }


def calcular_hertz(v: Valores) -> Resultado:
    geometria = str(v["geometria"])
    forca = float(v["forca_kN"]) * 1000.0
    d1 = float(v["d1_mm"])
    d2 = float(v["d2_mm"])
    comprimento = float(v["comprimento_mm"])
    e1 = float(v["e1_GPa"]) * 1000.0
    e2 = float(v["e2_GPa"]) * 1000.0
    sy = float(v["sy_MPa"])
    fs = float(v["fs"])
    r = contato_de_hertz(
        geometria, forca, d1, d2, comprimento, e1, float(v["nu1"]), e2, float(v["nu2"])
    )
    p0 = r["p0"]
    limite_inicio = r["limite_escoamento"] * sy / fs
    p_adm = float(v["p_adm_MPa"])
    verificacoes = [
        limite(
            "Início de escoamento abaixo da superfície",
            p0,
            limite_inicio,
            "MPa",
            f"p₀ ≤ {r['limite_escoamento']:.2f}·S_y/FS",
            JOHNSON,
        ),
        informativo(
            "Cisalhamento máximo abaixo da superfície",
            r["tau_max"],
            "MPa",
            f"a {r['z']:.3f} mm de profundidade: é daí que parte a trinca de fadiga de contato",
            JOHNSON,
        ),
    ]
    if p_adm > 0:
        verificacoes.insert(
            1,
            limite(
                "Pressão admissível informada",
                p0,
                p_adm,
                "MPa",
                "p₀ ≤ p_adm",
                "Valor do projeto ou do catálogo",
            ),
        )
    return Resultado(
        resumo=(
            f"Pressão máxima de {p0:.0f} MPa e área de contato com semilargura de {r['a']:.3f} mm."
        ),
        metricas=(
            Metrica("Pressão máxima p₀", p0, "MPa", 0),
            Metrica("Semilargura do contato", r["a"], "mm", 3),
            Metrica("τ máx abaixo da superfície", r["tau_max"], "MPa", 0),
            Metrica("Profundidade do τ máx", r["z"], "mm", 3),
            Metrica("von Mises máximo", r["von_mises"], "MPa", 0),
            Metrica("Aproximação dos corpos", r["aproximacao"], "mm", 4),
        ),
        verificacoes=tuple(verificacoes),
        hipoteses=(
            "Materiais elásticos, superfícies lisas e sem atrito na região de contato.",
            "A área de contato é pequena perto dos raios das peças.",
            "No contato em linha, a carga é uniforme no comprimento e o estado é de deformação "
            "plana.",
            "No contato em linha a aproximação dos corpos não tem valor único e sai zero.",
        ),
        referencias=(SHIGLEY_3, JOHNSON),
    )


CAMPOS_HERTZ = (
    Campo(
        "geometria",
        "Geometria do contato",
        "Roda em trilho, rolo em pista e came com seguidor: contato em linha, entre cilindros. "
        "Esfera de rolamento em pista plana: contato em ponto.",
        GEOMETRIA_CILINDRO_PLANO,
        opcoes=GEOMETRIAS,
        secao="Contato",
    ),
    Campo(
        "forca_kN",
        "Força de contato F",
        "A força que aperta as duas peças uma contra a outra.",
        100.0,
        "kN",
        minimo=0.001,
        passo=5.0,
        secao="Contato",
    ),
    Campo(
        "d1_mm",
        "Diâmetro da peça 1",
        "Diâmetro da roda, do rolo ou da esfera.",
        500.0,
        "mm",
        minimo=0.1,
        passo=10.0,
        secao="Contato",
    ),
    Campo(
        "d2_mm",
        "Diâmetro da peça 2",
        "Diâmetro da segunda peça.",
        200.0,
        "mm",
        minimo=0.1,
        passo=10.0,
        secao="Contato",
        quando=("geometria", GEOMETRIAS_DUAS),
    ),
    Campo(
        "comprimento_mm",
        "Comprimento de contato L",
        "Comprimento da linha de contato, como a largura útil do boleto do trilho.",
        50.0,
        "mm",
        minimo=0.1,
        passo=5.0,
        secao="Contato",
        quando=("geometria", GEOMETRIAS_LINHA),
    ),
    Campo(
        "e1_GPa",
        "E da peça 1",
        "Módulo de elasticidade. Aço: 205 GPa.",
        205.0,
        "GPa",
        minimo=1.0,
        passo=5.0,
        secao="Materiais",
    ),
    Campo(
        "nu1",
        "ν da peça 1",
        "Coeficiente de Poisson. Aço: 0,30.",
        0.30,
        minimo=0.1,
        maximo=0.45,
        passo=0.01,
        secao="Materiais",
    ),
    Campo(
        "e2_GPa",
        "E da peça 2",
        "Módulo de elasticidade da segunda peça.",
        205.0,
        "GPa",
        minimo=1.0,
        passo=5.0,
        secao="Materiais",
    ),
    Campo(
        "nu2",
        "ν da peça 2",
        "Coeficiente de Poisson da segunda peça.",
        0.30,
        minimo=0.1,
        maximo=0.45,
        passo=0.01,
        secao="Materiais",
    ),
    Campo(
        "sy_MPa",
        "Escoamento da peça mais mole",
        "Limite de escoamento da peça de menor resistência no contato.",
        500.0,
        "MPa",
        minimo=10.0,
        passo=10.0,
        secao="Materiais",
    ),
    Campo(
        "fs",
        "Fator de segurança",
        "Margem sobre o início do escoamento. Contato estático: comece com 1,5.",
        1.5,
        minimo=1.0,
        maximo=5.0,
        passo=0.1,
        secao="Materiais",
    ),
    Campo(
        "p_adm_MPa",
        "Pressão admissível",
        "Limite de pressão de contato vindo de catálogo ou norma. Deixe 0 se não houver.",
        0.0,
        "MPa",
        minimo=0.0,
        passo=50.0,
        secao="Materiais",
    ),
)


CASOS: tuple[Caso, ...] = (
    Caso(
        "rolamento",
        "Rolamento: vida e carga estática",
        GRUPO,
        "L₁₀, fator de confiabilidade, X e Y automáticos, s₀ e C necessário; regime NBR 8400.",
        "Para conferir um rolamento escolhido ou achar a capacidade necessária. Aceita as cargas "
        "médias da NBR 8400 para mecanismos de içamento.",
        CAMPOS_ROLAMENTO,
        calcular_rolamento,
        r"P=XF_r+YF_a,\qquad L_{10h}=\frac{10^6}{60n}\left(\frac{C}{P}\right)^p,\qquad "
        r"s_0=\frac{C_0}{P_0}",
    ),
    Caso(
        "bucha",
        "Bucha de deslizamento",
        GRUPO,
        "Pressão, velocidade e pV, em rotação ou em pino oscilante.",
        "Para bucha de bronze ou polímero, seca ou com graxa: o caso dos pinos de articulação. "
        "Confere os três limites do material.",
        CAMPOS_BUCHA,
        calcular_bucha,
        r"p=\frac{F}{d\,L},\qquad V=\frac{\pi\,d\,n}{60000},\qquad pV\le (pV)_{adm}",
    ),
    Caso(
        "pino_articulacao",
        "Pino de articulação",
        GRUPO,
        "Olhal e garfo: flexão e corte no pino, esmagamento nas chapas.",
        "Pino de cilindro hidráulico, de manilha ou de articulação. Inclui a flexão do pino, "
        "que costuma governar e fica de fora quando se olha só o corte.",
        CAMPOS_PINO,
        calcular_pino,
        r"M=\frac{F}{8}(b+4c+2a),\quad \sigma=\frac{32M}{\pi d^3},\quad "
        r"\tau_{max}=\frac{4}{3}\frac{F}{2A}",
    ),
    Caso(
        "hertz",
        "Contato de Hertz",
        GRUPO,
        "Roda e trilho, rolo e pista, esfera e plano: pressão e tensão abaixo da superfície.",
        "Calcula a pressão máxima de contato, a largura da área de contato e a profundidade em "
        "que o cisalhamento é máximo, de onde parte a fadiga de contato.",
        CAMPOS_HERTZ,
        calcular_hertz,
        r"p_0=\frac{2F}{\pi\,b\,L},\quad b=\sqrt{\frac{4FR}{\pi L E^*}},\quad "
        r"\frac{1}{E^*}=\frac{1-\nu_1^2}{E_1}+\frac{1-\nu_2^2}{E_2}",
    ),
)
