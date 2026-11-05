"""Máquinas na estrutura: disco girante, desbalanceamento, vibração, base, cilindro e placas."""

from __future__ import annotations

import math

from core.elementos_base import (
    Campo,
    Caso,
    Envio,
    Metrica,
    Ponto,
    Resultado,
    Tabela,
    Valores,
    exigir,
    faixa_recomendada,
    limite,
    minimo,
    recomendacao,
)

GRUPO_ROTATIVOS = "Máquinas e vibração"
GRUPO_FLUIDO = "Hidráulica e tampas"

SHIGLEY_3 = "Shigley, Elementos de Máquinas, cap. 3"
ISO_21940 = "ISO 21940-11 (grau de balanceamento G)"
ISO_10816 = "ISO 10816-3 (zonas de severidade de vibração)"
ROARK = "Roark, Formulas for Stress and Strain, cap. 11"
RAO = "Rao, Vibrações Mecânicas (força transmitida)"

GRAUS_G = ("G 1", "G 2,5", "G 6,3", "G 16", "G 40", "G 100")
VALOR_G = {"G 1": 1.0, "G 2,5": 2.5, "G 6,3": 6.3, "G 16": 16.0, "G 40": 40.0, "G 100": 100.0}


# ---------------------------------------------------------------------------
# Disco e volante
# ---------------------------------------------------------------------------


def tensoes_no_disco(
    rho_kg_mm3: float, omega: float, poisson: float, ri: float, ro: float, r: float
) -> tuple[float, float]:
    """σθ e σr em MPa num disco fino girando (Shigley, eq. 3-55). ρ em kg/mm³, ω em rad/s.

    Com mm e kg, ρω²r² sai em kg/(mm·s²); dividindo por 1000 vira N/mm².
    """
    k = rho_kg_mm3 * omega**2 / 1000.0 * (3.0 + poisson) / 8.0
    if ri == 0:
        tangencial = k * (ro**2 - (1.0 + 3.0 * poisson) / (3.0 + poisson) * r**2)
        radial = k * (ro**2 - r**2)
        return tangencial, radial
    tangencial = k * (
        ri**2 + ro**2 + ri**2 * ro**2 / r**2 - (1.0 + 3.0 * poisson) / (3.0 + poisson) * r**2
    )
    radial = k * (ri**2 + ro**2 - ri**2 * ro**2 / r**2 - r**2)
    return tangencial, radial


def calcular_disco_girante(v: Valores) -> Resultado:
    n = float(v["rotacao_rpm"])
    ro = float(v["D_ext_mm"]) / 2.0
    ri = float(v["D_int_mm"]) / 2.0
    t = float(v["t_mm"])
    rho = float(v["densidade_kg_m3"]) * 1e-9
    nu = float(v["poisson"])
    sy = float(v["sy_MPa"])
    fs = float(v["fs"])
    exigir(ro > ri, "O diâmetro externo deve ser maior que o interno.")
    omega = 2.0 * math.pi * n / 60.0

    raio_critico = ri if ri > 0 else 1e-6
    sigma_t, sigma_r = tensoes_no_disco(rho, omega, nu, ri, ro, raio_critico)
    massa = rho * math.pi * (ro**2 - ri**2) * t
    inercia = massa * (ro**2 + ri**2) / 2.0 * 1e-6
    energia = 0.5 * inercia * omega**2
    velocidade = omega * ro / 1000.0
    n_limite = n * math.sqrt(sy / fs / sigma_t) if sigma_t > 0 else math.inf

    ponto = Ponto("Ponto mais carregado do disco", sigma_t, sigma_r)
    verificacoes = [
        limite(
            "Tensão no disco",
            ponto.von_mises,
            sy / fs,
            "MPa",
            "σθ = ρω²(3 + ν)/4·[r_o² + (1 − ν)/(3 + ν)·r_i²] em r_i",
            SHIGLEY_3,
        ),
    ]
    variacao = float(v["energia_kJ"]) * 1000.0
    inercia_necessaria = 0.0
    if variacao > 0:
        cs = float(v["cs"])
        inercia_necessaria = variacao / (cs * omega**2)
        verificacoes.append(
            minimo(
                "Inércia do volante",
                inercia,
                inercia_necessaria,
                "kg·m²",
                f"I = ΔE/(C_s·ω²), com C_s = {cs:g}",
                "Norton, Projeto de Máquinas, cap. 11",
            )
        )
    return Resultado(
        resumo=(
            f"A {n:.0f} rpm a borda anda a {velocidade:.0f} m/s e a maior tensão é de "
            f"{sigma_t:.0f} MPa. Energia acumulada: {energia / 1000:.1f} kJ."
        ),
        metricas=(
            Metrica("Tensão tangencial máxima", sigma_t, "MPa", 1),
            Metrica("Velocidade na borda", velocidade, "m/s", 1),
            Metrica("Rotação limite", n_limite, "rpm", 0),
            Metrica("Inércia", inercia, "kg·m²", 3),
            Metrica("Energia cinética", energia / 1000.0, "kJ", 1),
            Metrica("Massa", massa, "kg", 1),
            Metrica("Inércia necessária", inercia_necessaria, "kg·m²", 3),
        ),
        verificacoes=tuple(verificacoes),
        pontos=(ponto,),
        alertas=(
            ("Um furo central dobra a tensão: compare com o disco sem furo.",) if ri > 0 else ()
        ),
        hipoteses=(
            "Disco fino de espessura constante, material isotrópico e elástico.",
            "Tensão máxima na borda do furo, ou no centro de disco sem furo.",
            "Sem as tensões do ajuste no eixo, que se somam às da rotação.",
            "A rotação limite considera o fator de segurança informado.",
        ),
        referencias=(SHIGLEY_3,),
    )


CAMPOS_DISCO_GIRANTE = (
    Campo(
        "rotacao_rpm",
        "Rotação",
        "Rotação máxima de trabalho, incluindo disparo se houver.",
        1800.0,
        "rpm",
        minimo=0.1,
        passo=50.0,
        secao="Serviço",
    ),
    Campo(
        "D_ext_mm",
        "Diâmetro externo",
        "Diâmetro externo do disco.",
        800.0,
        "mm",
        minimo=1.0,
        passo=10.0,
        secao="Disco",
    ),
    Campo(
        "D_int_mm",
        "Diâmetro do furo",
        "Diâmetro do furo central. Sem furo: 0.",
        100.0,
        "mm",
        minimo=0.0,
        passo=5.0,
        secao="Disco",
    ),
    Campo(
        "t_mm",
        "Espessura",
        "Espessura do disco.",
        60.0,
        "mm",
        minimo=0.1,
        passo=5.0,
        secao="Disco",
    ),
    Campo(
        "densidade_kg_m3",
        "Massa específica",
        "Aço: 7850 kg/m³. Ferro fundido: cerca de 7200 kg/m³.",
        7850.0,
        "kg/m³",
        minimo=100.0,
        passo=10.0,
        secao="Material",
    ),
    Campo(
        "poisson",
        "Coeficiente de Poisson ν",
        "Aço: 0,30.",
        0.30,
        minimo=0.1,
        maximo=0.45,
        passo=0.01,
        secao="Material",
    ),
    Campo(
        "sy_MPa",
        "Limite de escoamento",
        "Limite de escoamento do material do disco.",
        310.0,
        "MPa",
        minimo=10.0,
        passo=10.0,
        secao="Material",
    ),
    Campo(
        "fs",
        "Fator de segurança",
        "Margem sobre o escoamento. Peça girando solta muita energia ao romper: comece com 2,5.",
        2.5,
        minimo=1.0,
        maximo=8.0,
        passo=0.1,
        secao="Material",
    ),
    Campo(
        "energia_kJ",
        "Energia a acumular no ciclo",
        "A variação de energia que o volante precisa absorver em cada ciclo. Deixe 0 se não for "
        "um volante.",
        0.0,
        "kJ",
        minimo=0.0,
        passo=1.0,
        secao="Volante",
    ),
    Campo(
        "cs",
        "Flutuação de velocidade C_s",
        "Variação de velocidade aceita. Britadores e prensas: de 0,05 a 0,20. Bombas: de 0,03 a "
        "0,05.",
        0.10,
        minimo=0.005,
        maximo=0.5,
        passo=0.01,
        secao="Volante",
    ),
)


# ---------------------------------------------------------------------------
# Desbalanceamento e vibração
# ---------------------------------------------------------------------------

MODO_ISO = "Rotor balanceado (grau G)"
MODO_EXCENTRICO = "Massa excêntrica intencional"


def transmissibilidade(razao: float, amortecimento: float) -> float:
    """TR = F transmitida/F aplicada, para razão de frequências r = f/f_n."""
    numerador = 1.0 + (2.0 * amortecimento * razao) ** 2
    denominador = (1.0 - razao**2) ** 2 + (2.0 * amortecimento * razao) ** 2
    return math.sqrt(numerador / denominador)


def calcular_desbalanceamento(v: Valores) -> Resultado:
    rotacao = float(v["rotacao_rpm"])
    massa = float(v["massa_total_kg"])
    omega = 2.0 * math.pi * rotacao / 60.0
    if str(v["modo"]) == MODO_ISO:
        grau = VALOR_G[str(v["grau"])]
        rotor = float(v["massa_rotor_kg"])
        excentricidade = grau / omega  # mm
        produto = rotor * excentricidade  # kg·mm
    else:
        produto = float(v["massa_excentrica_kg"]) * float(v["raio_mm"])
        excentricidade = produto / max(float(v["massa_rotor_kg"]), 1e-9)
    forca = produto / 1000.0 * omega**2

    frequencia = rotacao / 60.0
    deflexao = float(v["deflexao_mm"])
    ligacao = str(v["apoio"])
    amortecimento = float(v["amortecimento"])
    if ligacao == "Sobre molas ou coxins":
        fn = math.sqrt(9806.65 / deflexao) / (2.0 * math.pi)
    else:
        fn = float(v["fn_estrutura_Hz"])
    razao = frequencia / fn
    tr = transmissibilidade(razao, amortecimento)
    transmitida = forca * tr
    apoios = int(v["apoios"])
    por_apoio = transmitida / apoios
    amplitude = (
        produto
        / massa
        * razao**2
        / math.sqrt((1.0 - razao**2) ** 2 + (2.0 * amortecimento * razao) ** 2)
    )
    velocidade_rms = amplitude * omega / math.sqrt(2.0)

    verificacoes = [
        limite(
            "Afastamento da ressonância",
            razao,
            0.7,
            "—",
            "r = f/f_n: fique fora de 0,7 a 1,4",
            RAO,
        )
        if razao < 1.0
        else minimo(
            "Afastamento da ressonância",
            razao,
            1.4,
            "—",
            "r = f/f_n: fique fora de 0,7 a 1,4; acima de √2 o apoio passa a isolar",
            RAO,
        ),
        limite(
            "Velocidade de vibração",
            velocidade_rms,
            float(v["v_adm_mm_s"]),
            "mm/s rms",
            f"v = X·ω/√2, com X = {amplitude:.3f} mm",
            ISO_10816,
        ),
    ]
    alertas = []
    if 0.7 <= razao <= 1.4:
        alertas.append(
            f"A máquina opera perto da ressonância do apoio (r = {razao:.2f}): a força é ampliada "
            f"{tr:.1f} vezes. Mude a rigidez do apoio ou a rotação."
        )
    if razao > 1.0:
        alertas.append(
            "A máquina passa pela ressonância ao partir e ao parar: a parada lenta é a fase mais "
            "severa."
        )
    return Resultado(
        resumo=(
            f"Força rotativa de {forca / 1000:.2f} kN a {frequencia:.1f} Hz; "
            f"chegam {transmitida / 1000:.2f} kN ao apoio (TR = {tr:.2f})."
        ),
        metricas=(
            Metrica("Força rotativa", forca / 1000.0, "kN", 3),
            Metrica("Excentricidade", excentricidade, "mm", 4),
            Metrica("Frequência de excitação", frequencia, "Hz", 2),
            Metrica("Frequência própria do apoio", fn, "Hz", 2),
            Metrica("Razão r = f/f_n", razao, "", 2),
            Metrica("Transmissibilidade", tr, "", 2),
            Metrica("Força na estrutura", transmitida / 1000.0, "kN", 3),
            Metrica("Por apoio", por_apoio / 1000.0, "kN", 3),
            Metrica("Amplitude", amplitude, "mm", 3),
            Metrica("Velocidade rms", velocidade_rms, "mm/s", 2),
        ),
        verificacoes=tuple(verificacoes),
        alertas=tuple(alertas),
        hipoteses=(
            "Um grau de liberdade na direção da força, com o apoio dividindo a carga por igual.",
            "Estrutura de apoio bem mais rígida que as molas, quando há molas.",
            "A força gira: nos apoios ela aparece em duas direções, defasadas 90°.",
            "Sem as harmônicas da máquina, que podem excitar outras frequências da estrutura.",
        ),
        referencias=(ISO_21940, RAO, ISO_10816),
        envios=(
            Envio(
                "base_maquina",
                "Levar a força para a base da máquina",
                {"fh_x_kN": transmitida / 1000.0},
            ),
        ),
    )


CAMPOS_DESBALANCEAMENTO = (
    Campo(
        "modo",
        "Origem da força",
        "Rotor balanceado: a força sai do grau G da ISO 21940. Massa excêntrica: peneira ou "
        "alimentador vibratório, em que o desbalanceamento é proposital.",
        MODO_ISO,
        opcoes=(MODO_ISO, MODO_EXCENTRICO),
        secao="Força",
    ),
    Campo(
        "rotacao_rpm",
        "Rotação",
        "Rotação de trabalho da máquina.",
        1750.0,
        "rpm",
        minimo=0.1,
        passo=10.0,
        secao="Força",
    ),
    Campo(
        "massa_rotor_kg",
        "Massa do rotor",
        "Massa da parte que gira.",
        500.0,
        "kg",
        minimo=0.001,
        passo=10.0,
        secao="Força",
    ),
    Campo(
        "grau",
        "Grau de balanceamento",
        "G 2,5: motores, turbinas e compressores. G 6,3: ventiladores, bombas, volantes e máquinas "
        "de processo em geral. G 16: eixos cardã e partes de britadores. G 40 e G 100: rodas e "
        "motores alternativos, raros em máquina de processo. São valores típicos: confira na "
        "ISO 21940-11.",
        "G 6,3",
        opcoes=GRAUS_G,
        secao="Força",
        quando=("modo", (MODO_ISO,)),
    ),
    Campo(
        "massa_excentrica_kg",
        "Massa excêntrica",
        "Soma das massas excêntricas que giram.",
        20.0,
        "kg",
        minimo=0.0,
        passo=1.0,
        secao="Força",
        quando=("modo", (MODO_EXCENTRICO,)),
    ),
    Campo(
        "raio_mm",
        "Raio da massa excêntrica",
        "Distância do centro de massa da excêntrica até o eixo.",
        100.0,
        "mm",
        minimo=0.0,
        passo=5.0,
        secao="Força",
        quando=("modo", (MODO_EXCENTRICO,)),
    ),
    Campo(
        "massa_total_kg",
        "Massa total sobre o apoio",
        "Massa de tudo o que vibra junto: máquina, base e parte móvel.",
        1500.0,
        "kg",
        minimo=0.001,
        passo=50.0,
        secao="Apoio",
    ),
    Campo(
        "apoio",
        "Tipo de apoio",
        "Sobre molas ou coxins: a frequência sai da deflexão estática. Direto na estrutura: "
        "informe a frequência própria da estrutura.",
        "Sobre molas ou coxins",
        opcoes=("Sobre molas ou coxins", "Direto na estrutura"),
        secao="Apoio",
    ),
    Campo(
        "deflexao_mm",
        "Deflexão estática",
        "Quanto a máquina afunda nas molas com o próprio peso. Mais deflexão isola melhor.",
        10.0,
        "mm",
        minimo=0.01,
        passo=1.0,
        secao="Apoio",
        quando=("apoio", ("Sobre molas ou coxins",)),
    ),
    Campo(
        "fn_estrutura_Hz",
        "Frequência própria da estrutura",
        "Primeira frequência própria da estrutura ou viga de apoio, na direção da força. Pode "
        "vir de uma análise de frequência no SolidWorks.",
        12.0,
        "Hz",
        minimo=0.01,
        passo=1.0,
        secao="Apoio",
        quando=("apoio", ("Direto na estrutura",)),
    ),
    Campo(
        "amortecimento",
        "Fator de amortecimento ζ",
        "Molas de aço: 0,01. Coxim de borracha: 0,05 a 0,10. Estrutura de aço: de 0,01 a 0,02.",
        0.05,
        minimo=0.001,
        maximo=0.9,
        passo=0.01,
        secao="Apoio",
    ),
    Campo(
        "apoios",
        "Número de apoios",
        "Quantos pés dividem a força.",
        4,
        minimo=1,
        maximo=32,
        passo=1,
        secao="Apoio",
    ),
    Campo(
        "v_adm_mm_s",
        "Velocidade de vibração aceita",
        "Limite de velocidade rms. Máquinas médias sobre base rígida: 2,8 mm/s é bom e 4,5 mm/s "
        "é aceitável por pouco tempo (ISO 10816-3).",
        4.5,
        "mm/s",
        minimo=0.1,
        passo=0.1,
        secao="Apoio",
    ),
)


# ---------------------------------------------------------------------------
# Base de máquina
# ---------------------------------------------------------------------------


def calcular_base(v: Valores) -> Resultado:
    peso = float(v["peso_kN"]) * 1000.0
    lx = float(v["lx_mm"])
    ly = float(v["ly_mm"])
    cx = float(v["cx_mm"])
    cy = float(v["cy_mm"])
    altura = float(v["altura_mm"])
    fx = float(v["fh_x_kN"]) * 1000.0
    fy = float(v["fh_y_kN"]) * 1000.0
    fz = float(v["fz_kN"]) * 1000.0
    torque = float(v["torque_Nm"]) * 1000.0
    eixo = str(v["eixo_torque"])
    area_rosca = float(v["area_rosca_mm2"])
    fy_ch = float(v["sy_chumbador_MPa"])
    fs = float(v["fs"])
    atrito = float(v["atrito"])

    # Quatro pés nos cantos de um retângulo lx × ly, com o centro em (0, 0).
    pes = (
        ("Pé 1 (−x, −y)", -lx / 2.0, -ly / 2.0),
        ("Pé 2 (+x, −y)", lx / 2.0, -ly / 2.0),
        ("Pé 3 (+x, +y)", lx / 2.0, ly / 2.0),
        ("Pé 4 (−x, +y)", -lx / 2.0, ly / 2.0),
    )
    soma_x2 = sum(p[1] ** 2 for p in pes)
    soma_y2 = sum(p[2] ** 2 for p in pes)
    vertical = peso + fz
    mx = peso * cy + fy * altura + (torque if eixo == "x" else 0.0)
    my = peso * cx + fx * altura + (torque if eixo == "y" else 0.0)
    # R_i positivo comprime o apoio. O peso em +x carrega os pés de +x.
    linhas = []
    reacoes = []
    for nome, x, y in pes:
        reacao = vertical / 4.0 + my * x / soma_x2 + mx * y / soma_y2
        reacoes.append(reacao)
        linhas.append({"Pé": nome, "Reação (kN)": reacao / 1000.0})
    menor = min(reacoes)
    maior = max(reacoes)
    tracao = max(-menor, 0.0)
    horizontal = math.hypot(fx, fy)

    # Sem atrito garantido: o cortante vai para os chumbadores se a força vencer o atrito.
    resistencia_atrito = atrito * max(menor, 0.0) * 4.0
    corte_no_chumbador = max(horizontal - resistencia_atrito, 0.0) / 4.0
    sigma = tracao / area_rosca
    tau = corte_no_chumbador / area_rosca
    combinada = math.sqrt(sigma**2 + 3.0 * tau**2)

    verificacoes = [
        limite(
            "Tensão no chumbador",
            combinada,
            fy_ch / fs,
            "MPa",
            f"√(σ² + 3τ²), com T = {tracao / 1000:.2f} kN e V = {corte_no_chumbador / 1000:.2f} kN",
            "von Mises no núcleo do chumbador",
        ),
        faixa_recomendada(
            "Tração no pé (arrancamento)",
            tracao / 1000.0,
            0.0,
            0.0,
            "kN",
            "R_mín ≥ 0: se um pé levanta, confira a ancoragem no concreto",
            "Estática de corpo rígido",
        ),
    ]
    alertas = []
    if menor < 0:
        alertas.append(
            f"Um pé tenta levantar com {tracao / 1000:.2f} kN. Confira a ancoragem em Placas de "
            "base; no concreto, a ruptura do cone costuma governar."
        )
    return Resultado(
        resumo=(
            f"Reações de {menor / 1000:.2f} a {maior / 1000:.2f} kN nos pés. "
            + (
                f"Tração de {tracao / 1000:.2f} kN no pior pé."
                if tracao > 0
                else "Nenhum pé levanta."
            )
        ),
        metricas=(
            Metrica("Maior reação", maior / 1000.0, "kN"),
            Metrica("Menor reação", menor / 1000.0, "kN"),
            Metrica("Força horizontal total", horizontal / 1000.0, "kN"),
            Metrica("Corte no chumbador", corte_no_chumbador / 1000.0, "kN"),
            Metrica("Tensão no chumbador", combinada, "MPa", 1),
        ),
        verificacoes=tuple(verificacoes),
        tabelas=(Tabela("Reações nos pés", tuple(linhas), "Positivo comprime o apoio."),),
        alertas=tuple(alertas),
        hipoteses=(
            "Base rígida sobre quatro pés iguais, nos cantos de um retângulo.",
            "O torque de reação entra somado às outras parcelas: é o pior sentido.",
            "Parafusos iguais, um por pé, com apoios de mesma rigidez.",
            "Força horizontal dividida entre os quatro chumbadores depois de descontado o atrito.",
            "Em chumbador protendido, a pré-carga não entra nesta soma.",
        ),
        referencias=("Estática de corpo rígido",),
    )


CAMPOS_BASE = (
    Campo(
        "peso_kN",
        "Peso da máquina",
        "Peso total apoiado na base.",
        30.0,
        "kN",
        minimo=0.0,
        passo=1.0,
        secao="Cargas",
    ),
    Campo(
        "fz_kN",
        "Força vertical extra",
        "Outra força vertical em operação, para baixo positiva, como o peso do material.",
        0.0,
        "kN",
        passo=1.0,
        secao="Cargas",
    ),
    Campo(
        "fh_x_kN",
        "Força horizontal em x",
        "Força horizontal na máquina, ao longo de x: tração de correia, partida, desbalanceamento.",
        3.0,
        "kN",
        minimo=0.0,
        passo=0.5,
        secao="Cargas",
    ),
    Campo(
        "fh_y_kN",
        "Força horizontal em y",
        "Força horizontal na máquina, ao longo de y.",
        0.0,
        "kN",
        minimo=0.0,
        passo=0.5,
        secao="Cargas",
    ),
    Campo(
        "altura_mm",
        "Altura da força horizontal",
        "Altura da força acima dos apoios. Ela vira momento e tira carga de um lado da base.",
        600.0,
        "mm",
        minimo=0.0,
        passo=10.0,
        secao="Cargas",
    ),
    Campo(
        "torque_Nm",
        "Torque de reação",
        "O motor empurra a base com torque igual e contrário ao do eixo. Na partida, use o torque "
        "de pico.",
        1200.0,
        "N·m",
        minimo=0.0,
        passo=50.0,
        secao="Cargas",
    ),
    Campo(
        "eixo_torque",
        "Eixo do torque",
        "A direção do eixo da máquina: x ou y. O torque de reação gira a base em torno dele.",
        "x",
        opcoes=("x", "y"),
        secao="Cargas",
    ),
    Campo(
        "lx_mm",
        "Distância entre pés em x",
        "Entre os centros dos pés, na direção x.",
        1600.0,
        "mm",
        minimo=1.0,
        passo=50.0,
        secao="Base",
    ),
    Campo(
        "ly_mm",
        "Distância entre pés em y",
        "Entre os centros dos pés, na direção y.",
        800.0,
        "mm",
        minimo=1.0,
        passo=50.0,
        secao="Base",
    ),
    Campo(
        "cx_mm",
        "Centro de gravidade em x",
        "Deslocamento do centro de gravidade em relação ao centro da base, em x.",
        0.0,
        "mm",
        passo=10.0,
        secao="Base",
    ),
    Campo(
        "cy_mm",
        "Centro de gravidade em y",
        "Deslocamento do centro de gravidade em relação ao centro da base, em y.",
        0.0,
        "mm",
        passo=10.0,
        secao="Base",
    ),
    Campo(
        "area_rosca_mm2",
        "Área resistente do chumbador",
        "Área da rosca. M16: 157 mm². M20: 245 mm². M24: 353 mm². M30: 561 mm².",
        245.0,
        "mm²",
        minimo=1.0,
        passo=10.0,
        secao="Fixação",
    ),
    Campo(
        "sy_chumbador_MPa",
        "Escoamento do chumbador",
        "ASTM A307: cerca de 250 MPa. ASTM A193 B7: 720 MPa. Classe 8.8: 640 MPa.",
        250.0,
        "MPa",
        minimo=10.0,
        passo=10.0,
        secao="Fixação",
    ),
    Campo(
        "fs",
        "Fator de segurança",
        "Margem sobre o escoamento do chumbador. Comece com 2,0.",
        2.0,
        minimo=1.0,
        maximo=6.0,
        passo=0.1,
        secao="Fixação",
    ),
    Campo(
        "atrito",
        "Atrito com o apoio",
        "Parte da força horizontal que o atrito segura. Aço com aço: até 0,3. Com vibração: use "
        "0, que é o lado seguro.",
        0.0,
        minimo=0.0,
        maximo=0.6,
        passo=0.05,
        secao="Fixação",
    ),
)


# ---------------------------------------------------------------------------
# Cilindro hidráulico
# ---------------------------------------------------------------------------


def calcular_cilindro(v: Valores) -> Resultado:
    pressao = float(v["pressao_bar"]) / 10.0
    d = float(v["d_camisa_mm"])
    haste = float(v["d_haste_mm"])
    parede = float(v["parede_mm"])
    curso = float(v["curso_mm"])
    fixacao = float(v["k"])
    vazao = float(v["vazao_l_min"])
    sy_h = float(v["sy_haste_MPa"])
    sy_c = float(v["sy_camisa_MPa"])
    e = float(v["e_GPa"]) * 1000.0
    fs = float(v["fs"])
    exigir(haste < d, "A haste deve ser mais fina que a camisa.")

    area_pistao = math.pi * d**2 / 4.0
    area_haste = math.pi * haste**2 / 4.0
    area_anular = area_pistao - area_haste
    forca_avanco = pressao * area_pistao
    forca_recuo = pressao * area_anular
    velocidade_avanco = vazao * 1e6 / 60.0 / area_pistao
    velocidade_recuo = vazao * 1e6 / 60.0 / area_anular
    potencia = pressao * vazao / 60.0  # MPa·(L/min)/60 dá kW

    ro = d / 2.0 + parede
    ri = d / 2.0
    sigma_t = pressao * (ro**2 + ri**2) / (ro**2 - ri**2)
    sigma_l = pressao * ri**2 / (ro**2 - ri**2)
    camisa = Ponto("Face interna da camisa", sigma_t, sigma_l, 0.0, -pressao)
    sigma_haste = forca_avanco / area_haste

    comprimento = float(v["comprimento_mm"])
    inercia = math.pi * haste**4 / 64.0
    raio = haste / 4.0
    indice = fixacao * comprimento / raio
    transicao = math.pi * math.sqrt(2.0 * e / sy_h)
    if indice >= transicao:
        critica = math.pi**2 * e * inercia / (fixacao * comprimento) ** 2
    else:
        critica = sy_h * (1.0 - sy_h * indice**2 / (4.0 * math.pi**2 * e)) * area_haste
    fator_flambagem = critica / forca_avanco

    tampa = float(v["tampa_mm"])
    sigma_tampa = 0.75 * pressao * (d / 2.0) ** 2 / tampa**2
    verificacoes = (
        limite(
            "Parede da camisa",
            camisa.von_mises,
            sy_c / fs,
            "MPa",
            "Lamé na face interna, com tampa: σθ, σ longitudinal e σr = −p",
            SHIGLEY_3,
        ),
        limite(
            "Tensão na haste",
            sigma_haste,
            sy_h / fs,
            "MPa",
            "σ = F/A",
            "Compressão simples",
        ),
        minimo(
            "Flambagem da haste",
            fator_flambagem,
            float(v["fs_flambagem"]),
            "—",
            f"P_cr/F, com KL/r = {indice:.0f} (Johnson ou Euler)",
            "Shigley, Elementos de Máquinas, cap. 4",
        ),
        limite(
            "Tampa plana",
            sigma_tampa,
            sy_c / fs,
            "MPa",
            "σ = 3p·a²/(4t²), placa circular engastada",
            ROARK,
        ),
        faixa_recomendada(
            "Razão de áreas haste/pistão",
            area_haste / area_pistao,
            0.1,
            0.6,
            "—",
            "faixa usual 0,1 a 0,6",
            "Prática de cilindros (ISO 6020)",
        ),
    )
    p_contrapressao = pressao * area_pistao / area_anular
    return Resultado(
        resumo=(
            f"Avança com {forca_avanco / 1000:.1f} kN e recua com {forca_recuo / 1000:.1f} kN, a "
            f"{velocidade_avanco:.0f} e {velocidade_recuo:.0f} mm/s."
        ),
        metricas=(
            Metrica("Força de avanço", forca_avanco / 1000.0, "kN", 1),
            Metrica("Força de recuo", forca_recuo / 1000.0, "kN", 1),
            Metrica("Velocidade de avanço", velocidade_avanco, "mm/s", 0),
            Metrica("Velocidade de recuo", velocidade_recuo, "mm/s", 0),
            Metrica("Potência hidráulica", potencia, "kW", 1),
            Metrica("Tempo de avanço", curso / velocidade_avanco, "s", 1),
            Metrica("Carga crítica da haste", critica / 1000.0, "kN", 0),
            Metrica("Pressão na câmara da haste", p_contrapressao * 10.0, "bar", 0),
        ),
        verificacoes=verificacoes,
        pontos=(camisa,),
        alertas=(
            f"Se a saída da câmara da haste for estrangulada, a pressão ali pode chegar a "
            f"{p_contrapressao * 10.0:.0f} bar (multiplicação de pressão). Confira as vedações.",
        ),
        hipoteses=(
            "Pressão uniforme e força axial, sem carga lateral na haste.",
            "Haste e camisa tratadas como uma só coluna de seção igual à da haste: do lado seguro.",
            "Tampa plana engastada na camisa, com os parafusos ou a solda verificados à parte.",
        ),
        referencias=(SHIGLEY_3, ROARK),
        envios=(
            Envio(
                "pino_articulacao",
                "Verificar o pino de articulação",
                {"forca_kN": forca_avanco / 1000.0},
            ),
        ),
    )


CAMPOS_CILINDRO = (
    Campo(
        "pressao_bar",
        "Pressão de trabalho",
        "Pressão máxima de operação, em bar.",
        160.0,
        "bar",
        minimo=0.1,
        passo=10.0,
        secao="Serviço",
    ),
    Campo(
        "vazao_l_min",
        "Vazão",
        "Vazão que entra no cilindro.",
        40.0,
        "L/min",
        minimo=0.01,
        passo=5.0,
        secao="Serviço",
    ),
    Campo(
        "d_camisa_mm",
        "Diâmetro da camisa",
        "Diâmetro interno do cilindro. Padrões ISO: 40, 50, 63, 80, 100, 125, 160, 200 mm.",
        100.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Cilindro",
    ),
    Campo(
        "d_haste_mm",
        "Diâmetro da haste",
        "Diâmetro da haste do pistão.",
        56.0,
        "mm",
        minimo=1.0,
        passo=2.0,
        secao="Cilindro",
    ),
    Campo(
        "parede_mm",
        "Parede da camisa",
        "Espessura da parede.",
        10.0,
        "mm",
        minimo=0.1,
        passo=1.0,
        secao="Cilindro",
    ),
    Campo(
        "tampa_mm",
        "Espessura da tampa",
        "Espessura da tampa plana.",
        30.0,
        "mm",
        minimo=0.1,
        passo=1.0,
        secao="Cilindro",
    ),
    Campo(
        "curso_mm",
        "Curso",
        "Curso do pistão.",
        600.0,
        "mm",
        minimo=0.1,
        passo=10.0,
        secao="Cilindro",
    ),
    Campo(
        "comprimento_mm",
        "Comprimento de flambagem",
        "Distância entre os pinos com o cilindro todo aberto, ou o comprimento livre da haste "
        "na fixação rígida.",
        1400.0,
        "mm",
        minimo=1.0,
        passo=10.0,
        secao="Flambagem",
    ),
    Campo(
        "k",
        "Fator de comprimento K",
        "Duas pontas com pino: 1,0. Base fixa e ponta guiada: 0,7. Base fixa e ponta livre: 2,0.",
        1.0,
        minimo=0.5,
        maximo=2.5,
        passo=0.1,
        secao="Flambagem",
    ),
    Campo(
        "fs_flambagem",
        "Fator mínimo à flambagem",
        "Margem sobre a carga crítica. Comece com 3,5, a prática de catálogos de cilindros.",
        3.5,
        minimo=1.0,
        maximo=8.0,
        passo=0.5,
        secao="Flambagem",
    ),
    Campo(
        "e_GPa",
        "Módulo de elasticidade E",
        "Aço: 205 GPa.",
        205.0,
        "GPa",
        minimo=10.0,
        passo=5.0,
        secao="Materiais",
    ),
    Campo(
        "sy_haste_MPa",
        "Escoamento da haste",
        "Haste de aço cromado C45: cerca de 500 MPa.",
        500.0,
        "MPa",
        minimo=10.0,
        passo=10.0,
        secao="Materiais",
    ),
    Campo(
        "sy_camisa_MPa",
        "Escoamento da camisa",
        "Tubo brunido ST52: cerca de 355 MPa.",
        355.0,
        "MPa",
        minimo=10.0,
        passo=5.0,
        secao="Materiais",
    ),
    Campo(
        "fs",
        "Fator de segurança",
        "Margem sobre o escoamento. Comece com 2,0.",
        2.0,
        minimo=1.0,
        maximo=6.0,
        passo=0.1,
        secao="Materiais",
    ),
)


# ---------------------------------------------------------------------------
# Placas
# ---------------------------------------------------------------------------

BORDA_ENGASTADA = "Engastada"
BORDA_APOIADA = "Simplesmente apoiada"

#: Placa retangular, ν = 0,3 (Roark, Tabela 11.4): a/b, β e α; casos 1a e 8a.
_PLACA_APOIADA = (
    (1.0, 0.2874, 0.0444),
    (1.2, 0.3762, 0.0616),
    (1.4, 0.4530, 0.0770),
    (1.6, 0.5172, 0.0906),
    (1.8, 0.5688, 0.1017),
    (2.0, 0.6102, 0.1110),
    (3.0, 0.7134, 0.1335),
    (4.0, 0.7410, 0.1400),
    (5.0, 0.7476, 0.1417),
)
_PLACA_APOIADA_INFINITA = (0.7500, 0.1421)
_PLACA_ENGASTADA = (
    (1.0, 0.3078, 0.0138),
    (1.2, 0.3834, 0.0188),
    (1.4, 0.4356, 0.0226),
    (1.6, 0.4680, 0.0251),
    (1.8, 0.4872, 0.0267),
    (2.0, 0.4974, 0.0277),
)
_PLACA_ENGASTADA_INFINITA = (0.5000, 0.0284)


def fatores_de_placa(a: float, b: float, borda: str) -> tuple[float, float]:
    """β e α da placa retangular, com a ≥ b, interpolando em a/b."""
    tabela = _PLACA_APOIADA if borda == BORDA_APOIADA else _PLACA_ENGASTADA
    infinita = _PLACA_APOIADA_INFINITA if borda == BORDA_APOIADA else _PLACA_ENGASTADA_INFINITA
    relacao = a / b
    for (r1, b1, a1), (r2, b2, a2) in zip(tabela, tabela[1:], strict=False):
        if r1 <= relacao <= r2:
            t = (relacao - r1) / (r2 - r1)
            return b1 + t * (b2 - b1), a1 + t * (a2 - a1)
    return infinita


def calcular_placa_circular(v: Valores) -> Resultado:
    pressao = float(v["pressao_MPa"])
    raio = float(v["d_mm"]) / 2.0
    t = float(v["t_mm"])
    e = float(v["e_GPa"]) * 1000.0
    nu = float(v["poisson"])
    borda = str(v["borda"])
    rigidez = e * t**3 / (12.0 * (1.0 - nu**2))
    if borda == BORDA_ENGASTADA:
        sigma = 0.75 * pressao * raio**2 / t**2
        flecha = pressao * raio**4 / (64.0 * rigidez)
        local = "na borda"
    else:
        sigma = 3.0 * (3.0 + nu) * pressao * raio**2 / (8.0 * t**2)
        flecha = (5.0 + nu) * pressao * raio**4 / (64.0 * rigidez * (1.0 + nu))
        local = "no centro"
    sy = float(v["sy_MPa"])
    fs = float(v["fs"])
    espessura_minima = t * math.sqrt(sigma / (sy / fs)) if sigma > 0 else 0.0
    verificacoes = (
        limite(
            "Tensão na placa",
            sigma,
            sy / fs,
            "MPa",
            f"máximo {local}: placa circular com borda {borda.lower()}",
            f"{ROARK} (Tabela 11.2)",
        ),
        limite(
            "Flecha",
            flecha,
            float(v["flecha_adm_mm"]),
            "mm",
            "w_máx da placa fina",
            f"{ROARK} (Tabela 11.2)",
        ),
        recomendacao(
            "Validade da teoria de placa fina",
            flecha,
            t / 2.0,
            "mm",
            "w ≤ t/2; acima disso a placa trabalha como membrana",
            ROARK,
        ),
    )
    return Resultado(
        resumo=f"Tensão máxima de {sigma:.1f} MPa {local} e flecha de {flecha:.2f} mm.",
        metricas=(
            Metrica("Tensão máxima", sigma, "MPa", 1),
            Metrica("Flecha máxima", flecha, "mm", 3),
            Metrica("Espessura mínima", espessura_minima, "mm", 1),
        ),
        verificacoes=verificacoes,
        pontos=(
            Ponto(
                f"Ponto mais carregado, {local}",
                sigma,
                sigma if borda == BORDA_APOIADA else nu * sigma,
            ),
        ),
        hipoteses=(
            "Placa fina, material elástico, pressão uniforme, sem furos nem reforços.",
            "Borda engastada exige flange rígido; junta com parafusos fica entre os dois casos.",
        ),
        referencias=(ROARK,),
    )


def calcular_placa_retangular(v: Valores) -> Resultado:
    pressao = float(v["pressao_MPa"])
    lado_1 = float(v["a_mm"])
    lado_2 = float(v["b_mm"])
    a = max(lado_1, lado_2)
    b = min(lado_1, lado_2)
    t = float(v["t_mm"])
    e = float(v["e_GPa"]) * 1000.0
    borda = str(v["borda"])
    beta, alfa = fatores_de_placa(a, b, borda)
    sigma = beta * pressao * b**2 / t**2
    flecha = alfa * pressao * b**4 / (e * t**3)
    sy = float(v["sy_MPa"])
    fs = float(v["fs"])
    verificacoes = (
        limite(
            "Tensão na placa",
            sigma,
            sy / fs,
            "MPa",
            f"σ = β·q·b²/t², com β = {beta:.4f}",
            f"{ROARK} (Tabela 11.4)",
        ),
        limite(
            "Flecha",
            flecha,
            float(v["flecha_adm_mm"]),
            "mm",
            f"w = α·q·b⁴/(E·t³), com α = {alfa:.4f}",
            f"{ROARK} (Tabela 11.4)",
        ),
        recomendacao(
            "Validade da teoria de placa fina",
            flecha,
            t / 2.0,
            "mm",
            "w ≤ t/2; acima disso a placa trabalha como membrana",
            ROARK,
        ),
    )
    return Resultado(
        resumo=f"Tensão máxima de {sigma:.1f} MPa e flecha de {flecha:.2f} mm.",
        metricas=(
            Metrica("Tensão máxima", sigma, "MPa", 1),
            Metrica("Flecha máxima", flecha, "mm", 3),
            Metrica("Coeficiente β", beta, "", 4),
            Metrica("Coeficiente α", alfa, "", 4),
            Metrica("Relação a/b", a / b, "", 2),
        ),
        verificacoes=verificacoes,
        pontos=(Ponto("Ponto mais carregado da placa", sigma, 0.3 * sigma),),
        hipoteses=(
            "Placa fina retangular, pressão uniforme e ν = 0,3.",
            "Coeficientes interpolados em a/b na Tabela 11.4 de Roark.",
        ),
        referencias=(ROARK,),
    )


def _campos_de_placa(padrao_t: float) -> tuple[Campo, ...]:
    return (
        Campo(
            "pressao_MPa",
            "Pressão uniforme",
            "Pressão de cálculo sobre a placa. 1 MPa vale 10 bar.",
            0.5,
            "MPa",
            minimo=0.0,
            passo=0.05,
            secao="Carga",
        ),
        Campo(
            "borda",
            "Condição de borda",
            "Engastada: flange rígido ou solda de penetração. Apoiada: chapa só encostada. "
            "Na dúvida, verifique as duas.",
            BORDA_APOIADA,
            opcoes=(BORDA_APOIADA, BORDA_ENGASTADA),
            secao="Carga",
        ),
        Campo(
            "t_mm",
            "Espessura t",
            "Espessura da placa.",
            padrao_t,
            "mm",
            minimo=0.1,
            passo=1.0,
            secao="Placa",
        ),
        Campo(
            "e_GPa",
            "Módulo de elasticidade E",
            "Aço: 205 GPa.",
            205.0,
            "GPa",
            minimo=1.0,
            passo=5.0,
            secao="Material",
        ),
        Campo(
            "sy_MPa",
            "Limite de escoamento",
            "Limite de escoamento da chapa.",
            250.0,
            "MPa",
            minimo=10.0,
            passo=10.0,
            secao="Material",
        ),
        Campo(
            "fs",
            "Fator de segurança",
            "Margem sobre o escoamento. Comece com 1,5.",
            1.5,
            minimo=1.0,
            maximo=6.0,
            passo=0.1,
            secao="Material",
        ),
        Campo(
            "flecha_adm_mm",
            "Flecha admissível",
            "Maior flecha aceita para a função da chapa.",
            5.0,
            "mm",
            minimo=0.001,
            passo=0.5,
            secao="Material",
        ),
    )


CAMPOS_PLACA_CIRCULAR = (
    Campo(
        "d_mm",
        "Diâmetro livre",
        "Diâmetro sem apoio da placa, medido no círculo de parafusos ou na solda.",
        400.0,
        "mm",
        minimo=1.0,
        passo=10.0,
        secao="Placa",
    ),
    *_campos_de_placa(20.0),
    Campo(
        "poisson",
        "Coeficiente de Poisson ν",
        "Aço: 0,30.",
        0.30,
        minimo=0.1,
        maximo=0.45,
        passo=0.01,
        secao="Material",
    ),
)

CAMPOS_PLACA_RETANGULAR = (
    Campo(
        "a_mm",
        "Lado maior a",
        "O maior lado livre da placa.",
        800.0,
        "mm",
        minimo=1.0,
        passo=10.0,
        secao="Placa",
    ),
    Campo(
        "b_mm",
        "Lado menor b",
        "O menor lado livre da placa.",
        500.0,
        "mm",
        minimo=1.0,
        passo=10.0,
        secao="Placa",
    ),
    *_campos_de_placa(20.0),
)


CASOS: tuple[Caso, ...] = (
    Caso(
        "desbalanceamento",
        "Desbalanceamento e vibração",
        GRUPO_ROTATIVOS,
        "Força rotativa (grau G ou excêntrica), ressonância e força na estrutura.",
        "Quanta força uma máquina girando põe na estrutura. Serve para rotor balanceado e para "
        "peneira ou alimentador vibratório. Mostra a distância da ressonância e a transmissibilidade.",
        CAMPOS_DESBALANCEAMENTO,
        calcular_desbalanceamento,
        r"F=m\,e\,\omega^2,\quad e=\frac{G}{\omega},\quad "
        r"TR=\sqrt{\frac{1+(2\zeta r)^2}{(1-r^2)^2+(2\zeta r)^2}}",
    ),
    Caso(
        "base_maquina",
        "Base de máquina",
        GRUPO_ROTATIVOS,
        "Reações nos quatro pés, torque de partida e chumbadores.",
        "Divide o peso, as forças horizontais e o torque de reação pelos quatro pés da base, "
        "e confere a tração e o corte nos chumbadores.",
        CAMPOS_BASE,
        calcular_base,
        r"R_i=\frac{F_z}{4}+\frac{M_y\,x_i}{\sum x^2}+\frac{M_x\,y_i}{\sum y^2}",
    ),
    Caso(
        "disco_girante",
        "Disco girante e volante",
        GRUPO_ROTATIVOS,
        "Tensões por rotação, rotação limite, energia e inércia do volante.",
        "Tensões num disco que gira, a rotação limite e, para volante, a inércia que absorve a "
        "variação de energia do ciclo.",
        CAMPOS_DISCO_GIRANTE,
        calcular_disco_girante,
        r"\sigma_\theta=\rho\omega^2\frac{3+\nu}{8}\left[r_i^2+r_o^2+\frac{r_i^2r_o^2}{r^2}"
        r"-\frac{1+3\nu}{3+\nu}r^2\right]",
    ),
    Caso(
        "cilindro_hidraulico",
        "Cilindro hidráulico",
        GRUPO_FLUIDO,
        "Forças, velocidades, camisa, tampa e flambagem da haste.",
        "Da pressão e da vazão às forças e velocidades. Confere a camisa por Lamé, a tampa plana "
        "e a flambagem da haste, que costuma governar nos cilindros longos.",
        CAMPOS_CILINDRO,
        calcular_cilindro,
        r"F=p\,A,\quad v=\frac{Q}{A},\quad P_{cr}=\frac{\pi^2EI}{(KL)^2}",
    ),
    Caso(
        "placa_circular",
        "Tampa circular",
        GRUPO_FLUIDO,
        "Placa circular sob pressão: tampa, flange cego, fundo de tanque.",
        "Tensão e flecha de uma placa circular sob pressão, engastada ou apoiada.",
        CAMPOS_PLACA_CIRCULAR,
        calcular_placa_circular,
        r"\sigma_{eng}=\frac{3pa^2}{4t^2},\quad \sigma_{ap}=\frac{3(3+\nu)pa^2}{8t^2}",
    ),
    Caso(
        "placa_retangular",
        "Chapa retangular",
        GRUPO_FLUIDO,
        "Chapa sob pressão: janela de inspeção, tampa, parede de silo ou tanque.",
        "Tensão e flecha de uma chapa retangular sob pressão uniforme, pelos coeficientes de "
        "Roark.",
        CAMPOS_PLACA_RETANGULAR,
        calcular_placa_retangular,
        r"\sigma=\beta\frac{q\,b^2}{t^2},\qquad w=\alpha\frac{q\,b^4}{E\,t^3}",
    ),
)
