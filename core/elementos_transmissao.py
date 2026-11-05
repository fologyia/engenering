"""Transmissão de potência: do motor às forças que chegam ao eixo.

Acionamento e redutor, engrenagens cilíndricas (dentes retos e helicoidais), cônicas e coroa com
sem-fim, correias, correntes de rolos e flange de acoplamento. A engrenagem cilíndrica é verificada
pela equação de Lewis e pela de contato (Shigley, cap. 14): é o pré-dimensionamento, e a NBR 8400
6.7.5 deixa o método das engrenagens a critério do fabricante, desde que a origem seja indicada. O
cálculo completo pela AGMA 2001 ou pela ISO 6336 não é feito aqui.
"""

from __future__ import annotations

import math

from core.elementos_base import (
    Campo,
    Caso,
    Envio,
    Metrica,
    Resultado,
    Tabela,
    Valores,
    exigir,
    faixa_recomendada,
    informativo,
    limite,
    minimo,
    recomendacao,
    recomendacao_minima,
)

GRUPO = "Transmissão de potência"

SHIGLEY_13 = "Shigley, Elementos de Máquinas, cap. 13"
SHIGLEY_14 = "Shigley, Elementos de Máquinas, cap. 14"
SHIGLEY_15 = "Shigley, Elementos de Máquinas, cap. 15"
SHIGLEY_17 = "Shigley, Elementos de Máquinas, cap. 17"

#: Fator de forma de Lewis Y, ângulo de pressão 20° e dente normal (Shigley, Tabela 14-2).
_LEWIS = (
    (12, 0.245),
    (13, 0.261),
    (14, 0.277),
    (15, 0.290),
    (16, 0.296),
    (17, 0.303),
    (18, 0.309),
    (19, 0.314),
    (20, 0.322),
    (21, 0.328),
    (22, 0.331),
    (24, 0.337),
    (26, 0.346),
    (28, 0.353),
    (30, 0.359),
    (34, 0.371),
    (38, 0.384),
    (43, 0.397),
    (50, 0.409),
    (60, 0.422),
    (75, 0.435),
    (100, 0.447),
    (150, 0.460),
    (300, 0.472),
    (400, 0.480),
)
_LEWIS_CREMALHEIRA = 0.485

PROCESSOS = ("Fresado", "Caracol (hob)", "Retificado", "Fundido")
GRAUS_AGMA = ("Grau 1", "Grau 2")


def potencia_em_torque(potencia_kW: float, rotacao_rpm: float) -> float:
    """Torque em N·m: T = 9550·P/n."""
    exigir(rotacao_rpm > 0, "A rotação deve ser maior que zero.")
    return 60_000.0 * potencia_kW / (2.0 * math.pi * rotacao_rpm)


def fator_lewis(dentes: float) -> float:
    """Y interpolado na Tabela 14-2. Acima de 400 dentes tende ao valor da cremalheira."""
    exigir(dentes >= _LEWIS[0][0], "O fator de Lewis começa em 12 dentes.")
    for (z1, y1), (z2, y2) in zip(_LEWIS, _LEWIS[1:], strict=False):
        if z1 <= dentes <= z2:
            return y1 + (y2 - y1) * (dentes - z1) / (z2 - z1)
    return _LEWIS_CREMALHEIRA


def fator_dinamico(processo: str, velocidade_m_s: float) -> float:
    """K_v de Barth e AGMA (Shigley, eq. 14-4), com V em m/s."""
    v = velocidade_m_s
    if processo == "Fundido":
        return (3.05 + v) / 3.05
    if processo == "Fresado":
        return (6.1 + v) / 6.1
    if processo == "Caracol (hob)":
        return (3.56 + math.sqrt(v)) / 3.56
    if processo == "Retificado":
        return math.sqrt((5.56 + math.sqrt(v)) / 5.56)
    raise ValueError(f"Processo de fabricação desconhecido: {processo}.")


def resistencia_flexao_agma(dureza_HB: float, grau: str) -> float:
    """S_t de aço beneficiado, em MPa (Shigley, Figura 14-2)."""
    return 0.533 * dureza_HB + 88.3 if grau == "Grau 1" else 0.703 * dureza_HB + 113.0


def resistencia_contato_agma(dureza_HB: float, grau: str) -> float:
    """S_c de aço beneficiado, em MPa (Shigley, Figura 14-5)."""
    return 2.22 * dureza_HB + 200.0 if grau == "Grau 1" else 2.41 * dureza_HB + 237.0


def coeficiente_elastico(modulo_GPa: float, poisson: float) -> float:
    """C_p em √MPa para duas peças do mesmo material; 191 para aço."""
    return math.sqrt(modulo_GPa * 1000.0 / (2.0 * math.pi * (1.0 - poisson**2)))


# ---------------------------------------------------------------------------
# Acionamento e redutor
# ---------------------------------------------------------------------------


def calcular_acionamento(v: Valores) -> Resultado:
    potencia = float(v["potencia_kW"])
    rotacao = float(v["rotacao_rpm"])
    estagios = [
        (float(v["i1"]), float(v["eta1"])),
        (float(v["i2"]), float(v["eta2"])),
        (float(v["i3"]), float(v["eta3"])),
    ]
    reducao = math.prod(i for i, _ in estagios)
    rendimento = math.prod(eta for _, eta in estagios)
    torque_motor = potencia_em_torque(potencia, rotacao)
    rotacao_saida = rotacao / reducao
    torque_saida = torque_motor * reducao * rendimento
    torque_projeto = torque_saida * float(v["fator_servico"])
    torque_pico = torque_saida * float(v["fator_partida"])
    potencia_saida = potencia * rendimento

    omega = 2.0 * math.pi * rotacao / 60.0
    inercia = float(v["inercia_motor"]) + float(v["inercia_carga"]) / reducao**2
    torque_carga_motor = float(v["torque_resistente"]) / (reducao * rendimento)
    torque_acelerador = torque_motor * float(v["fator_partida"]) - torque_carga_motor
    verificacoes = []
    alertas: list[str] = []
    tempo = None
    if torque_acelerador > 0:
        tempo = inercia * omega / torque_acelerador
    else:
        alertas.append(
            "O torque de partida do motor não vence o torque resistente: a máquina não parte."
        )
    capacidade = float(v["capacidade_redutor"])
    verificacoes.append(
        minimo(
            "Partida do motor",
            torque_motor * float(v["fator_partida"]),
            torque_carga_motor,
            "N·m",
            "T_partida ≥ T_res/(i·η)",
            "Dinâmica do acionamento",
        )
    )
    if capacidade > 0:
        verificacoes.append(
            limite(
                "Torque de projeto no redutor",
                torque_projeto,
                capacidade,
                "N·m",
                f"K_s·T_saída = {float(v['fator_servico']):.2f}·{torque_saida:.1f}",
                "Catálogo do redutor",
            )
        )
    tabela = tuple(
        {
            "Estágio": numero,
            "Redução i": i,
            "Rendimento η": eta,
            "Rotação na saída (rpm)": rotacao / math.prod(x for x, _ in estagios[:numero]),
            "Torque na saída (N·m)": torque_motor * math.prod(x * y for x, y in estagios[:numero]),
        }
        for numero, (i, eta) in enumerate(estagios, start=1)
        if i != 1.0 or eta != 1.0
    )
    metricas = [
        Metrica("Torque no motor", torque_motor, "N·m", 1),
        Metrica("Rotação na saída", rotacao_saida, "rpm", 1),
        Metrica("Torque na saída", torque_saida, "N·m", 1),
        Metrica("Torque de projeto", torque_projeto, "N·m", 1),
        Metrica("Torque de pico", torque_pico, "N·m", 1),
        Metrica("Potência na saída", potencia_saida, "kW", 2),
    ]
    if tempo is not None:
        metricas.append(Metrica("Tempo de partida", tempo, "s", 2))
    return Resultado(
        resumo=(
            f"{potencia:.1f} kW a {rotacao:.0f} rpm viram {torque_saida:.0f} N·m a "
            f"{rotacao_saida:.1f} rpm na saída (redução {reducao:.2f}, rendimento {rendimento:.3f})."
        ),
        metricas=tuple(metricas),
        verificacoes=tuple(verificacoes),
        tabelas=(Tabela("Estágios do redutor", tabela),) if tabela else (),
        alertas=tuple(alertas),
        hipoteses=(
            "Regime permanente na potência informada; o fator de serviço cobre a sobrecarga.",
            "O tempo de partida supõe torque de partida constante e torque resistente constante.",
            "A inércia da carga é levada ao eixo do motor dividindo por i².",
        ),
        referencias=("T = 9550·P/n", "AGMA: fatores de sobrecarga típicos (Shigley, cap. 14)"),
        envios=(
            Envio(
                "engrenagem",
                "Usar no cálculo da engrenagem",
                {"potencia_kW": potencia, "rotacao_rpm": rotacao},
            ),
            Envio(
                "correia",
                "Usar no cálculo da correia",
                {"potencia_kW": potencia, "rotacao_rpm": rotacao},
            ),
            Envio(
                "chaveta",
                "Levar o torque de saída para a chaveta",
                {"torque_Nm": torque_saida, "fator_servico": float(v["fator_servico"])},
            ),
            Envio(
                "acoplamento",
                "Levar o torque de saída para o flange",
                {"torque_Nm": torque_saida, "fator_servico": float(v["fator_servico"])},
            ),
        ),
    )


CAMPOS_ACIONAMENTO = (
    Campo(
        "potencia_kW",
        "Potência do motor",
        "A potência nominal que entra no acionamento. Se a máquina pede menos do que o motor "
        "entrega, use a potência absorvida; o torque de partida entra à parte.",
        15.0,
        "kW",
        minimo=0.001,
        passo=1.0,
        secao="Motor",
    ),
    Campo(
        "rotacao_rpm",
        "Rotação do motor",
        "Rotação nominal do eixo do motor (motor de 4 polos em 60 Hz: cerca de 1750 rpm).",
        1750.0,
        "rpm",
        minimo=0.1,
        passo=10.0,
        secao="Motor",
    ),
    Campo(
        "fator_partida",
        "Torque de partida / nominal",
        "Quantas vezes o torque de partida passa do nominal. Motor de indução com partida direta: "
        "cerca de 2,0 a 2,5. Com inversor ou soft-starter: perto de 1,0 a 1,5.",
        2.0,
        minimo=0.5,
        maximo=5.0,
        passo=0.1,
        secao="Motor",
    ),
    Campo(
        "i1",
        "Redução do 1º estágio",
        "Relação de velocidades do estágio: rotação de entrada dividida pela de saída. "
        "Deixe 1 se o estágio não existir.",
        5.0,
        minimo=0.01,
        passo=0.5,
        secao="Redutor",
    ),
    Campo(
        "eta1",
        "Rendimento do 1º estágio",
        "Par de engrenagens cilíndricas: 0,97 a 0,99. Correia: 0,95 a 0,98. Corrente: 0,96 a 0,98. "
        "Sem-fim: 0,50 a 0,90, conforme o ângulo da hélice.",
        0.97,
        minimo=0.05,
        maximo=1.0,
        passo=0.01,
        secao="Redutor",
    ),
    Campo(
        "i2",
        "Redução do 2º estágio",
        "Relação de velocidades do segundo estágio. Deixe 1 se ele não existir.",
        4.0,
        minimo=0.01,
        passo=0.5,
        secao="Redutor",
    ),
    Campo(
        "eta2",
        "Rendimento do 2º estágio",
        "Rendimento do segundo estágio. Deixe 1 se ele não existir.",
        0.97,
        minimo=0.05,
        maximo=1.0,
        passo=0.01,
        secao="Redutor",
    ),
    Campo(
        "i3",
        "Redução do 3º estágio",
        "Relação de velocidades do terceiro estágio. Deixe 1 se ele não existir.",
        1.0,
        minimo=0.01,
        passo=0.5,
        secao="Redutor",
    ),
    Campo(
        "eta3",
        "Rendimento do 3º estágio",
        "Rendimento do terceiro estágio. Deixe 1 se ele não existir.",
        1.0,
        minimo=0.05,
        maximo=1.0,
        passo=0.01,
        secao="Redutor",
    ),
    Campo(
        "fator_servico",
        "Fator de serviço K_s",
        "Cobre a sobrecarga da aplicação. Motor elétrico com máquina uniforme: 1,00. Choque "
        "moderado (britador leve, transportador carregado): 1,25. Choque pesado (moinho, "
        "britador): 1,75. Valores da tabela de fator de sobrecarga da AGMA.",
        1.25,
        minimo=1.0,
        maximo=4.0,
        passo=0.05,
        secao="Carga",
    ),
    Campo(
        "capacidade_redutor",
        "Torque nominal do redutor",
        "Torque de saída de catálogo do redutor. Deixe 0 se ainda não houver redutor escolhido: "
        "a linha de verificação não aparece.",
        0.0,
        "N·m",
        minimo=0.0,
        passo=50.0,
        secao="Carga",
    ),
    Campo(
        "torque_resistente",
        "Torque resistente na saída",
        "O torque que a máquina pede no eixo de saída durante a partida. Serve para saber se o "
        "motor parte a máquina e em quanto tempo.",
        200.0,
        "N·m",
        minimo=0.0,
        passo=10.0,
        secao="Partida",
    ),
    Campo(
        "inercia_motor",
        "Inércia do motor",
        "Momento de inércia do rotor, do catálogo do motor.",
        0.1,
        "kg·m²",
        minimo=0.0,
        passo=0.01,
        secao="Partida",
    ),
    Campo(
        "inercia_carga",
        "Inércia da carga na saída",
        "Momento de inércia de tudo o que gira no eixo de saída: tambor, polia, rotor da máquina.",
        20.0,
        "kg·m²",
        minimo=0.0,
        passo=1.0,
        secao="Partida",
    ),
)


# ---------------------------------------------------------------------------
# Engrenagem cilíndrica
# ---------------------------------------------------------------------------


def calcular_engrenagem(v: Valores) -> Resultado:
    potencia = float(v["potencia_kW"])
    rotacao = float(v["rotacao_rpm"])
    modulo = float(v["modulo_mm"])
    z1 = int(v["z1"])
    z2 = int(v["z2"])
    phi_n = math.radians(float(v["angulo_pressao"]))
    psi = math.radians(float(v["angulo_helice"]))
    largura = float(v["largura_mm"])
    ko = float(v["ko"])
    km = float(v["km"])
    fs = float(v["fs"])
    exigir(z2 >= z1, "Informe o pinhão em z₁: z₂ deve ser maior ou igual a z₁.")
    exigir(z1 >= 12, "O fator de Lewis começa em 12 dentes.")

    phi_t = math.atan(math.tan(phi_n) / math.cos(psi))
    d1 = modulo * z1 / math.cos(psi)
    d2 = modulo * z2 / math.cos(psi)
    velocidade = math.pi * d1 * rotacao / 60_000.0
    torque = potencia_em_torque(potencia, rotacao)
    ft = 2.0 * torque * 1000.0 / d1
    fr = ft * math.tan(phi_n) / math.cos(psi)
    fa = ft * math.tan(psi)
    fn = ft / (math.cos(phi_n) * math.cos(psi))
    kv = fator_dinamico(str(v["processo"]), velocidade)

    z_virtual_1 = z1 / math.cos(psi) ** 3
    z_virtual_2 = z2 / math.cos(psi) ** 3
    y1 = fator_lewis(z_virtual_1)
    y2 = fator_lewis(z_virtual_2)
    sigma1 = ko * kv * km * ft / (largura * modulo * y1)
    sigma2 = ko * kv * km * ft / (largura * modulo * y2)

    cp = coeficiente_elastico(float(v["e_GPa"]), float(v["poisson"]))
    r1 = d1 * math.sin(phi_t) / 2.0
    r2 = d2 * math.sin(phi_t) / 2.0
    sigma_c = cp * math.sqrt(
        ko * kv * km * ft / (largura * math.cos(phi_t)) * (1.0 / r1 + 1.0 / r2)
    )

    grau = str(v["grau"])
    s_t = resistencia_flexao_agma(float(v["dureza_HB"]), grau)
    s_c = resistencia_contato_agma(float(v["dureza_HB"]), grau)
    z_min = 2.0 * math.cos(psi) / math.sin(phi_t) ** 2
    distancia = (d1 + d2) / 2.0

    verificacoes = [
        limite(
            "Flexão no dente do pinhão (Lewis)",
            sigma1,
            s_t / fs,
            "MPa",
            f"σ = K_o·K_v·K_m·F_t/(b·m·Y) com Y = {y1:.3f}",
            f"{SHIGLEY_14} (eq. de Lewis)",
        ),
        limite(
            "Flexão no dente da coroa (Lewis)",
            sigma2,
            s_t / fs,
            "MPa",
            f"σ = K_o·K_v·K_m·F_t/(b·m·Y) com Y = {y2:.3f}",
            f"{SHIGLEY_14} (eq. de Lewis)",
        ),
        limite(
            "Pressão de contato no flanco",
            sigma_c,
            s_c / fs,
            "MPa",
            "σ_c = C_p·√[K·F_t/(b·cos φ)·(1/r₁ + 1/r₂)]",
            f"{SHIGLEY_14} (contato de Hertz)",
        ),
        faixa_recomendada(
            "Largura do dente b/m",
            largura / modulo,
            8.0,
            16.0,
            "—",
            "faixa usual 8 ≤ b/m ≤ 16",
            "Norton, Projeto de Máquinas, cap. 12",
        ),
        recomendacao_minima(
            "Dentes do pinhão sem adelgaçamento",
            z1,
            z_min,
            "dentes",
            "z_mín = 2·cos ψ/sen²φ_t",
            SHIGLEY_13,
        ),
    ]
    alertas: list[str] = []
    if velocidade > 25.0:
        alertas.append(
            f"Velocidade na primitiva de {velocidade:.1f} m/s: o K_v deixa de valer para "
            "engrenagem comum. Acima de 25 m/s a precisão e a lubrificação precisam de projeto "
            "específico."
        )
    if math.degrees(psi) > 0:
        alertas.append(
            "Dente helicoidal: a força axial F_a precisa de mancal que a segure. A conta de "
            "contato não credita a razão de contato do dente inclinado, o que deixa o resultado "
            "do lado seguro."
        )
    return Resultado(
        resumo=(
            f"Pinhão d = {d1:.1f} mm: F_t = {ft / 1000:.2f} kN, F_r = {fr / 1000:.2f} kN e "
            f"F_a = {fa / 1000:.2f} kN no eixo."
        ),
        metricas=(
            Metrica("Força tangencial F_t", ft / 1000.0, "kN"),
            Metrica("Força radial F_r", fr / 1000.0, "kN"),
            Metrica("Força axial F_a", fa / 1000.0, "kN"),
            Metrica("Força normal F_n", fn / 1000.0, "kN"),
            Metrica("Primitivo do pinhão d₁", d1, "mm", 1),
            Metrica("Primitivo da coroa d₂", d2, "mm", 1),
            Metrica("Entre centros", distancia, "mm", 1),
            Metrica("Velocidade na primitiva", velocidade, "m/s"),
            Metrica("Fator dinâmico K_v", kv, "", 3),
            Metrica("Relação i", z2 / z1, "", 3),
            Metrica("Torque na coroa", torque * z2 / z1, "N·m", 1),
        ),
        verificacoes=tuple(verificacoes),
        tabelas=(
            Tabela(
                "Forças no eixo do pinhão",
                (
                    {"Força": "Tangencial F_t", "Valor (kN)": ft / 1000.0, "Direção": "tangente"},
                    {"Força": "Radial F_r", "Valor (kN)": fr / 1000.0, "Direção": "para o centro"},
                    {
                        "Força": "Axial F_a",
                        "Valor (kN)": fa / 1000.0,
                        "Direção": "ao longo do eixo",
                    },
                ),
                "Na coroa as forças são iguais e opostas.",
            ),
        ),
        alertas=tuple(alertas),
        hipoteses=(
            "Dentes de perfil evolvente, altura normal e ângulo de pressão usual.",
            "Pré-dimensionamento por Lewis e por contato de Hertz: não é o cálculo AGMA 2001 "
            "nem o ISO 6336.",
            "O fator de Lewis usa o número virtual de dentes z/cos³ψ.",
            "A resistência S_t e S_c é de aço beneficiado (Figuras 14-2 e 14-5 de Shigley).",
            "Pinhão e coroa do mesmo material; K_m cobre o desalinhamento.",
        ),
        referencias=(
            SHIGLEY_13,
            SHIGLEY_14,
            "NBR 8400:1984 6.7.5 (o método é do fabricante, que deve indicar a origem)",
        ),
        envios=(
            Envio(
                "eixo_transmissao",
                "Levar as forças para o eixo do pinhão",
                {
                    "f1_ativa": True,
                    "f1_fy_kN": fr / 1000.0,
                    "f1_fz_kN": ft / 1000.0,
                    "f1_fx_kN": fa / 1000.0,
                    "f1_raio_mm": d1 / 2.0,
                    "f1_torque_Nm": torque,
                    "f2_ativa": True,
                    "f2_torque_Nm": -(torque),
                    "rotacao_rpm": rotacao,
                },
            ),
        ),
    )


CAMPOS_ENGRENAGEM = (
    Campo(
        "potencia_kW",
        "Potência transmitida",
        "A potência que passa pelo par de engrenagens, no eixo do pinhão.",
        15.0,
        "kW",
        minimo=0.001,
        passo=1.0,
        secao="Serviço",
    ),
    Campo(
        "rotacao_rpm",
        "Rotação do pinhão",
        "Rotação do eixo do pinhão, a engrenagem menor do par.",
        1750.0,
        "rpm",
        minimo=0.1,
        passo=10.0,
        secao="Serviço",
    ),
    Campo(
        "ko",
        "Fator de sobrecarga K_o",
        "Cobre os choques do acionamento e da máquina. Uniforme nos dois lados: 1,00. Choque "
        "moderado: 1,25. Choque pesado: 1,75.",
        1.25,
        minimo=1.0,
        maximo=4.0,
        passo=0.05,
        secao="Serviço",
    ),
    Campo(
        "km",
        "Fator de distribuição K_m",
        "Cobre a carga mal distribuída na largura do dente por desalinhamento e flexão do eixo. "
        "Engrenagem rígida e bem alinhada: 1,3. Montagem comum: 1,6. Pouco rígida: 2,0.",
        1.6,
        minimo=1.0,
        maximo=3.0,
        passo=0.1,
        secao="Serviço",
    ),
    Campo(
        "fs",
        "Fator de segurança",
        "Margem sobre as resistências S_t e S_c. Comece com 1,5 para serviço comum e com 2,0 "
        "quando a falha para a produção ou expõe pessoas.",
        1.5,
        minimo=1.0,
        maximo=6.0,
        passo=0.1,
        secao="Serviço",
    ),
    Campo(
        "modulo_mm",
        "Módulo normal m",
        "O tamanho do dente. Valores normalizados: 1; 1,25; 1,5; 2; 2,5; 3; 4; 5; 6; 8; 10; 12.",
        5.0,
        "mm",
        minimo=0.1,
        passo=0.5,
        secao="Geometria",
    ),
    Campo(
        "z1",
        "Dentes do pinhão z₁",
        "Número de dentes da engrenagem menor. Abaixo de 17 dentes (ângulo de 20°) o corte "
        "adelgaça o pé do dente, salvo se houver correção de perfil.",
        25,
        minimo=12,
        maximo=400,
        passo=1,
        secao="Geometria",
    ),
    Campo(
        "z2",
        "Dentes da coroa z₂",
        "Número de dentes da engrenagem maior. Em redutores, evite que a razão seja um número "
        "inteiro exato, para que os mesmos dentes não se encontrem sempre.",
        81,
        minimo=12,
        maximo=2000,
        passo=1,
        secao="Geometria",
    ),
    Campo(
        "largura_mm",
        "Largura do dente b",
        "A largura útil do dente. A faixa usual é de 8 a 16 vezes o módulo: mais que isso exige "
        "eixos muito rígidos para o dente encostar por inteiro.",
        60.0,
        "mm",
        minimo=0.1,
        passo=2.0,
        secao="Geometria",
    ),
    Campo(
        "angulo_pressao",
        "Ângulo de pressão φ",
        "Padrão atual: 20°. Em dente helicoidal, é o ângulo normal.",
        20.0,
        "°",
        minimo=14.5,
        maximo=25.0,
        passo=0.5,
        secao="Geometria",
    ),
    Campo(
        "angulo_helice",
        "Ângulo de hélice ψ",
        "Zero para dente reto. Dente helicoidal: de 10° a 30°. Quanto maior, mais suave o "
        "engrenamento e maior a força axial nos mancais.",
        0.0,
        "°",
        minimo=0.0,
        maximo=45.0,
        passo=1.0,
        secao="Geometria",
    ),
    Campo(
        "processo",
        "Fabricação do dente",
        "Define o fator dinâmico K_v: dente mais preciso sofre menos choque entre os dentes. "
        "Caracol (hob) é o processo comum; retificado, o de precisão.",
        "Caracol (hob)",
        opcoes=PROCESSOS,
        secao="Geometria",
    ),
    Campo(
        "dureza_HB",
        "Dureza do material",
        "Dureza Brinell do aço do dente. Aço beneficiado comum: de 200 a 350 HB.",
        300.0,
        "HB",
        minimo=120.0,
        maximo=500.0,
        passo=10.0,
        secao="Material",
    ),
    Campo(
        "grau",
        "Qualidade do aço (AGMA)",
        "Grau 1: aço comercial. Grau 2: aço com controle de limpeza e de tratamento térmico, "
        "com resistência maior.",
        "Grau 1",
        opcoes=GRAUS_AGMA,
        secao="Material",
    ),
    Campo(
        "e_GPa",
        "Módulo de elasticidade E",
        "Aço: 205 GPa. Entra na pressão de contato.",
        205.0,
        "GPa",
        minimo=10.0,
        passo=5.0,
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
)


# ---------------------------------------------------------------------------
# Engrenagem cônica
# ---------------------------------------------------------------------------


def calcular_conica(v: Valores) -> Resultado:
    torque = float(v["torque_Nm"])
    modulo = float(v["modulo_mm"])
    z1 = int(v["z1"])
    z2 = int(v["z2"])
    largura = float(v["largura_mm"])
    phi = math.radians(float(v["angulo_pressao"]))
    exigir(z2 >= z1, "Informe o pinhão em z₁: z₂ deve ser maior ou igual a z₁.")

    gama = math.atan2(z1, z2)
    d1 = modulo * z1
    geratriz = d1 / (2.0 * math.sin(gama))
    d_medio = d1 - largura * math.sin(gama)
    exigir(d_medio > 0, "A largura é grande demais para este pinhão.")
    ft = 2.0 * torque * 1000.0 / d_medio
    fr = ft * math.tan(phi) * math.cos(gama)
    fa = ft * math.tan(phi) * math.sin(gama)
    return Resultado(
        resumo=(
            f"No pinhão: F_t = {ft / 1000:.2f} kN, F_r = {fr / 1000:.2f} kN e "
            f"F_a = {fa / 1000:.2f} kN, com γ = {math.degrees(gama):.1f}°."
        ),
        metricas=(
            Metrica("Força tangencial F_t", ft / 1000.0, "kN"),
            Metrica("Força radial no pinhão", fr / 1000.0, "kN"),
            Metrica("Força axial no pinhão", fa / 1000.0, "kN"),
            Metrica("Ângulo do cone γ", math.degrees(gama), "°", 1),
            Metrica("Primitivo médio", d_medio, "mm", 1),
            Metrica("Geratriz do cone A₀", geratriz, "mm", 1),
        ),
        verificacoes=(
            recomendacao(
                "Largura do dente",
                largura,
                min(10.0 * modulo, geratriz / 3.0),
                "mm",
                "b ≤ menor entre 10·m e A₀/3",
                SHIGLEY_13,
            ),
        ),
        tabelas=(
            Tabela(
                "Forças nos dois eixos (eixos a 90°)",
                (
                    {"Peça": "Pinhão", "Radial (kN)": fr / 1000.0, "Axial (kN)": fa / 1000.0},
                    {"Peça": "Coroa", "Radial (kN)": fa / 1000.0, "Axial (kN)": fr / 1000.0},
                ),
                "A força axial de um eixo é a radial do outro.",
            ),
        ),
        hipoteses=(
            "Eixos a 90° e dente reto: as forças atuam no meio da largura do dente.",
            "Aqui saem só as forças no eixo; a tensão no dente não é verificada neste caso.",
        ),
        referencias=(SHIGLEY_13,),
        envios=(
            Envio(
                "eixo_transmissao",
                "Levar as forças para o eixo do pinhão",
                {
                    "f1_ativa": True,
                    "f1_fy_kN": fr / 1000.0,
                    "f1_fz_kN": ft / 1000.0,
                    "f1_fx_kN": fa / 1000.0,
                    "f1_raio_mm": d_medio / 2.0,
                    "f1_torque_Nm": torque,
                    "f2_ativa": True,
                    "f2_torque_Nm": -(torque),
                },
            ),
        ),
    )


CAMPOS_CONICA = (
    Campo(
        "torque_Nm",
        "Torque no pinhão",
        "O torque do eixo do pinhão. Use o torque de projeto, já com o fator de serviço.",
        200.0,
        "N·m",
        minimo=0.001,
        passo=10.0,
        secao="Carga",
    ),
    Campo(
        "modulo_mm",
        "Módulo m",
        "O módulo medido na extremidade maior do dente.",
        4.0,
        "mm",
        minimo=0.1,
        passo=0.5,
        secao="Geometria",
    ),
    Campo(
        "z1",
        "Dentes do pinhão z₁",
        "Número de dentes da engrenagem menor.",
        18,
        minimo=6,
        passo=1,
        secao="Geometria",
    ),
    Campo(
        "z2",
        "Dentes da coroa z₂",
        "Número de dentes da engrenagem maior.",
        36,
        minimo=6,
        passo=1,
        secao="Geometria",
    ),
    Campo(
        "largura_mm",
        "Largura do dente b",
        "A largura do dente, medida ao longo da geratriz do cone. Limite usual: 10 módulos ou um "
        "terço da geratriz, o que for menor.",
        24.0,
        "mm",
        minimo=0.1,
        passo=2.0,
        secao="Geometria",
    ),
    Campo(
        "angulo_pressao",
        "Ângulo de pressão φ",
        "Padrão: 20°.",
        20.0,
        "°",
        minimo=14.5,
        maximo=25.0,
        passo=0.5,
        secao="Geometria",
    ),
)


# ---------------------------------------------------------------------------
# Sem-fim e coroa
# ---------------------------------------------------------------------------


def atrito_sem_fim(velocidade_escorregamento_m_s: float) -> float:
    """f de bronze fosforoso com sem-fim endurecido (Shigley, eq. 15-38), com V em m/s."""
    pes_min = velocidade_escorregamento_m_s * 196.85
    if pes_min <= 0:
        return 0.15
    if pes_min < 10.0:
        return 0.124 * math.exp(-0.074 * pes_min**0.645)
    return 0.103 * math.exp(-0.110 * pes_min**0.450) + 0.012


def calcular_sem_fim(v: Valores) -> Resultado:
    torque = float(v["torque_Nm"])
    rotacao = float(v["rotacao_rpm"])
    modulo = float(v["modulo_mm"])
    entradas = int(v["entradas"])
    z2 = int(v["z2"])
    d_w = float(v["d_sem_fim_mm"])
    phi_n = math.radians(float(v["angulo_pressao"]))

    d_g = modulo * z2
    lam = math.atan(entradas * modulo / d_w)
    v_esc = math.pi * d_w * rotacao / (60_000.0 * math.cos(lam))
    atrito = atrito_sem_fim(v_esc) if bool(v["atrito_automatico"]) else float(v["atrito"])

    w_t = 2.0 * torque * 1000.0 / d_w
    normal = w_t / (math.cos(phi_n) * math.sin(lam) + atrito * math.cos(lam))
    w_a = normal * (math.cos(phi_n) * math.cos(lam) - atrito * math.sin(lam))
    w_r = normal * math.sin(phi_n)
    rendimento = (math.cos(phi_n) - atrito * math.tan(lam)) / (
        math.cos(phi_n) + atrito / math.tan(lam)
    )
    exigir(w_a > 0 and rendimento > 0, "Com este atrito e esta hélice o sem-fim não transmite.")
    reducao = z2 / entradas
    torque_coroa = w_a * d_g / 2.0 / 1000.0
    potencia = torque * 2.0 * math.pi * rotacao / 60_000.0
    perda = potencia * (1.0 - rendimento)
    autotravante = atrito >= math.cos(phi_n) * math.tan(lam)

    alertas = []
    if autotravante:
        alertas.append(
            "Pela conta o par é autotravante, mas vibração e queda do atrito liberam o giro. "
            "Em içamento, não dispense o freio confiando nisso."
        )
    return Resultado(
        resumo=(
            f"Redução {reducao:.1f}, rendimento {rendimento * 100:.1f} %, "
            f"{torque_coroa:.0f} N·m na coroa."
            + (" O par é autotravante." if autotravante else " O par não é autotravante.")
        ),
        metricas=(
            Metrica("Rendimento", rendimento * 100.0, "%", 1),
            Metrica("Ângulo de avanço λ", math.degrees(lam), "°", 2),
            Metrica("Atrito f", atrito, "", 4),
            Metrica("Torque na coroa", torque_coroa, "N·m", 1),
            Metrica("Rotação na coroa", rotacao / reducao, "rpm", 1),
            Metrica("Calor a dissipar", perda, "kW", 2),
            Metrica("Velocidade de escorregamento", v_esc, "m/s", 2),
            Metrica("Entre centros", (d_w + d_g) / 2.0, "mm", 1),
        ),
        verificacoes=(
            faixa_recomendada(
                "Diâmetro do sem-fim",
                d_w,
                ((d_w + d_g) / 2.0 / 25.4) ** 0.875 / 3.0 * 25.4,
                ((d_w + d_g) / 2.0 / 25.4) ** 0.875 / 1.7 * 25.4,
                "mm",
                "C^0,875/3 ≤ d ≤ C^0,875/1,7 (em polegadas)",
                SHIGLEY_15,
            ),
            informativo(
                "Limite de autotravamento",
                math.degrees(math.atan(atrito / math.cos(phi_n))),
                "°",
                "trava quando tan λ ≤ f/cos φ_n",
                SHIGLEY_15,
            ),
        ),
        tabelas=(
            Tabela(
                "Forças nos dois eixos",
                (
                    {
                        "Peça": "Sem-fim",
                        "Tangencial (kN)": w_t / 1000.0,
                        "Axial (kN)": w_a / 1000.0,
                    },
                    {"Peça": "Coroa", "Tangencial (kN)": w_a / 1000.0, "Axial (kN)": w_t / 1000.0},
                ),
                f"A força radial vale {w_r / 1000:.2f} kN nos dois.",
            ),
        ),
        alertas=tuple(alertas),
        hipoteses=(
            "Eixos reversos a 90° e sem-fim acionando a coroa.",
            "O atrito automático vale para sem-fim de aço endurecido e coroa de bronze.",
            "A capacidade de desgaste e a dissipação térmica vêm do catálogo do fabricante.",
        ),
        referencias=(SHIGLEY_15,),
    )


CAMPOS_SEM_FIM = (
    Campo(
        "torque_Nm",
        "Torque no sem-fim",
        "O torque no eixo do sem-fim, que é o eixo de entrada.",
        60.0,
        "N·m",
        minimo=0.001,
        passo=5.0,
        secao="Serviço",
    ),
    Campo(
        "rotacao_rpm",
        "Rotação do sem-fim",
        "Rotação do eixo de entrada.",
        1750.0,
        "rpm",
        minimo=0.1,
        passo=10.0,
        secao="Serviço",
    ),
    Campo(
        "modulo_mm",
        "Módulo axial m",
        "Módulo medido na direção do eixo do sem-fim.",
        5.0,
        "mm",
        minimo=0.1,
        passo=0.5,
        secao="Geometria",
    ),
    Campo(
        "entradas",
        "Entradas do sem-fim",
        "Número de filetes do sem-fim. Com 1 entrada a redução é maior e o rendimento é menor.",
        2,
        minimo=1,
        maximo=8,
        passo=1,
        secao="Geometria",
    ),
    Campo(
        "z2",
        "Dentes da coroa z₂",
        "Número de dentes da coroa. Mínimo usual: 21 a 40, conforme o ângulo de pressão.",
        40,
        minimo=10,
        passo=1,
        secao="Geometria",
    ),
    Campo(
        "d_sem_fim_mm",
        "Primitivo do sem-fim d",
        "Diâmetro primitivo do sem-fim. Junto com o módulo define o ângulo de avanço.",
        60.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Geometria",
    ),
    Campo(
        "angulo_pressao",
        "Ângulo de pressão normal φ_n",
        "Valores usuais: 14,5°, 20°, 25° e 30°.",
        20.0,
        "°",
        minimo=10.0,
        maximo=35.0,
        passo=0.5,
        secao="Geometria",
    ),
    Campo(
        "atrito_automatico",
        "Atrito pela velocidade",
        "Ligado, o programa estima o atrito pela velocidade de escorregamento (aço com bronze). "
        "Desligado, você informa o valor.",
        True,
        secao="Atrito",
    ),
    Campo(
        "atrito",
        "Coeficiente de atrito f",
        "Atrito entre o sem-fim e a coroa. Partindo do repouso: cerca de 0,15.",
        0.05,
        minimo=0.001,
        maximo=0.5,
        passo=0.005,
        secao="Atrito",
        quando=("atrito_automatico", (False,)),
    ),
)


# ---------------------------------------------------------------------------
# Correia
# ---------------------------------------------------------------------------


def geometria_da_correia(d: float, D: float, C: float) -> tuple[float, float, float]:
    """Ângulos de abraçamento na polia menor e na maior (rad) e comprimento da correia."""
    exigir(D >= d, "Informe em D a polia maior.")
    exigir(2.0 * C > D - d, "Entre centros curto demais: a correia não fecha nas duas polias.")
    desvio = math.asin((D - d) / (2.0 * C))
    menor = math.pi - 2.0 * desvio
    maior = math.pi + 2.0 * desvio
    comprimento = math.sqrt(4.0 * C**2 - (D - d) ** 2) + (D * maior + d * menor) / 2.0
    return menor, maior, comprimento


def calcular_correia(v: Valores) -> Resultado:
    tipo = str(v["tipo"])
    potencia = float(v["potencia_kW"]) * float(v["fator_servico"])
    rotacao = float(v["rotacao_rpm"])
    d = float(v["d_mm"])
    D = float(v["D_mm"])
    C = float(v["C_mm"])
    atrito = float(v["atrito"])
    massa = float(v["massa_kg_m"])
    correias = int(v["correias"])

    menor, _maior, comprimento = geometria_da_correia(d, D, C)
    velocidade = math.pi * d * rotacao / 60_000.0
    torque = potencia_em_torque(potencia, rotacao)
    ft = 2.0 * torque * 1000.0 / d
    fc = massa * velocidade**2 * correias
    meia_ranhura = math.radians(float(v["angulo_ranhura"]) / 2.0)
    expoente = atrito * menor / (math.sin(meia_ranhura) if tipo == "Em V" else 1.0)
    razao = math.exp(expoente)
    f1_estatica = ft * razao / (razao - 1.0)
    f2_estatica = ft / (razao - 1.0)
    f1 = f1_estatica + fc
    f2 = f2_estatica + fc
    pretensao_min = (f1_estatica + f2_estatica) / 2.0
    carga_eixo = math.sqrt(
        f1_estatica**2 + f2_estatica**2 - 2.0 * f1_estatica * f2_estatica * math.cos(menor)
    )
    informada = float(v["pretensao_kN"]) * 1000.0

    verificacoes = [
        recomendacao_minima(
            "Ângulo de abraçamento na polia menor",
            math.degrees(menor),
            120.0,
            "°",
            "θ = π − 2·asen[(D − d)/(2C)]",
            SHIGLEY_17,
        ),
        recomendacao(
            "Velocidade da correia",
            velocidade,
            30.0,
            "m/s",
            "V = π·d·n/60000; acima de 30 m/s a força centrífuga consome a capacidade",
            SHIGLEY_17,
        ),
        faixa_recomendada(
            "Entre centros",
            C,
            0.7 * (D + d),
            2.0 * (D + d),
            "mm",
            "0,7(D + d) ≤ C ≤ 2(D + d)",
            SHIGLEY_17,
        ),
    ]
    if informada > 0:
        verificacoes.insert(
            0,
            minimo(
                "Pré-tensão instalada contra o deslizamento",
                informada,
                pretensao_min,
                "N",
                "F_i ≥ F_t·(e^(μθ) + 1)/[2(e^(μθ) − 1)]",
                SHIGLEY_17,
            ),
        )
    return Resultado(
        resumo=(
            f"Precisa de pré-tensão de {pretensao_min / 1000:.2f} kN no conjunto; "
            f"o eixo recebe {carga_eixo / 1000:.2f} kN."
        ),
        metricas=(
            Metrica("Força útil F_t", ft / 1000.0, "kN"),
            Metrica("Ramo tenso F₁", f1 / 1000.0, "kN"),
            Metrica("Ramo frouxo F₂", f2 / 1000.0, "kN"),
            Metrica("Carga no eixo", carga_eixo / 1000.0, "kN"),
            Metrica("Pré-tensão mínima", pretensao_min / 1000.0, "kN"),
            Metrica("Comprimento da correia", comprimento, "mm", 0),
            Metrica("Velocidade", velocidade, "m/s"),
            Metrica("Abraçamento", math.degrees(menor), "°", 1),
            Metrica("Por correia, ramo tenso", f1 / 1000.0 / correias, "kN"),
        ),
        verificacoes=tuple(verificacoes),
        hipoteses=(
            "F₁ e F₂ estão no limite do deslizamento pela equação de Euler (capstan).",
            "A carga no eixo não inclui a parcela centrífuga, que a correia equilibra sozinha.",
            "A pré-tensão é a do conjunto de correias, dividida por igual entre elas.",
            "A vida da correia e a potência por correia vêm do catálogo do fabricante.",
        ),
        referencias=(SHIGLEY_17,),
        envios=(
            Envio(
                "eixo_transmissao",
                "Levar a carga para o eixo",
                {
                    "f1_ativa": True,
                    "f1_fy_kN": carga_eixo / 1000.0,
                    "f1_fz_kN": 0.0,
                    "f1_fx_kN": 0.0,
                    "f1_raio_mm": 0.0,
                    "f1_torque_Nm": torque,
                    "f2_ativa": True,
                    "f2_torque_Nm": -(torque),
                    "rotacao_rpm": rotacao,
                },
            ),
        ),
    )


CAMPOS_CORREIA = (
    Campo(
        "tipo",
        "Tipo de correia",
        "Correia em V aperta nos flancos da ranhura e por isso transmite mais com a mesma "
        "tensão. Correia plana só depende do atrito na face.",
        "Em V",
        opcoes=("Em V", "Plana"),
        secao="Serviço",
    ),
    Campo(
        "potencia_kW",
        "Potência transmitida",
        "A potência que passa pela correia.",
        15.0,
        "kW",
        minimo=0.001,
        passo=1.0,
        secao="Serviço",
    ),
    Campo(
        "rotacao_rpm",
        "Rotação da polia menor",
        "Rotação do eixo da polia menor.",
        1750.0,
        "rpm",
        minimo=0.1,
        passo=10.0,
        secao="Serviço",
    ),
    Campo(
        "fator_servico",
        "Fator de serviço K_s",
        "Multiplica a potência. Carga uniforme: 1,1 a 1,2. Choque moderado: 1,3 a 1,4. "
        "Britador ou moinho: 1,5 ou mais.",
        1.2,
        minimo=1.0,
        maximo=4.0,
        passo=0.05,
        secao="Serviço",
    ),
    Campo(
        "d_mm",
        "Diâmetro da polia menor d",
        "Diâmetro primitivo da polia menor.",
        150.0,
        "mm",
        minimo=1.0,
        passo=10.0,
        secao="Geometria",
    ),
    Campo(
        "D_mm",
        "Diâmetro da polia maior D",
        "Diâmetro primitivo da polia maior.",
        450.0,
        "mm",
        minimo=1.0,
        passo=10.0,
        secao="Geometria",
    ),
    Campo(
        "C_mm",
        "Entre centros C",
        "Distância entre os centros das polias.",
        800.0,
        "mm",
        minimo=1.0,
        passo=10.0,
        secao="Geometria",
    ),
    Campo(
        "correias",
        "Número de correias",
        "Quantas correias trabalham em paralelo.",
        3,
        minimo=1,
        maximo=30,
        passo=1,
        secao="Geometria",
    ),
    Campo(
        "angulo_ranhura",
        "Ângulo da ranhura",
        "Só para correia em V. Valor usual: 34° a 38°.",
        38.0,
        "°",
        minimo=20.0,
        maximo=60.0,
        passo=1.0,
        secao="Geometria",
        quando=("tipo", ("Em V",)),
    ),
    Campo(
        "atrito",
        "Coeficiente de atrito μ",
        "Borracha sobre ferro fundido ou aço: cerca de 0,3 em correia em V e de 0,3 a 0,5 em "
        "correia plana de boa qualidade.",
        0.3,
        minimo=0.05,
        maximo=1.0,
        passo=0.01,
        secao="Correia",
    ),
    Campo(
        "massa_kg_m",
        "Massa por metro",
        "Massa de uma correia, por metro. Dá a força centrífuga, que reduz a capacidade em "
        "velocidade alta.",
        0.2,
        "kg/m",
        minimo=0.0,
        passo=0.01,
        secao="Correia",
    ),
    Campo(
        "pretensao_kN",
        "Pré-tensão instalada",
        "A pré-tensão do conjunto no ramo, como será ajustada na montagem. Deixe 0 para o "
        "programa só calcular o mínimo necessário.",
        0.0,
        "kN",
        minimo=0.0,
        passo=0.1,
        secao="Correia",
    ),
)


# ---------------------------------------------------------------------------
# Corrente de rolos
# ---------------------------------------------------------------------------


def elos_da_corrente(passo: float, z1: int, z2: int, C: float) -> tuple[float, int]:
    """Comprimento em passos e o número par de elos logo acima dele."""
    elos = 2.0 * C / passo + (z1 + z2) / 2.0 + (z2 - z1) ** 2 * passo / (4.0 * math.pi**2 * C)
    inteiro = math.ceil(elos)
    return elos, inteiro + inteiro % 2


def calcular_corrente(v: Valores) -> Resultado:
    potencia = float(v["potencia_kW"])
    rotacao = float(v["rotacao_rpm"])
    passo = float(v["passo_mm"])
    z1 = int(v["z1"])
    z2 = int(v["z2"])
    C = float(v["C_mm"])
    fileiras = int(v["fileiras"])
    ks = float(v["fator_servico"])
    exigir(z2 >= z1, "Informe a roda menor em z₁.")

    d1 = passo / math.sin(math.pi / z1)
    d2 = passo / math.sin(math.pi / z2)
    exigir(2.0 * C > d2 - d1, "Entre centros curto demais para estas rodas.")
    velocidade = z1 * passo * rotacao / 60_000.0
    ft = ks * potencia * 1000.0 / velocidade
    fc = float(v["massa_kg_m"]) * velocidade**2
    ruptura = float(v["ruptura_kN"]) * 1000.0 * fileiras
    elos, elos_par = elos_da_corrente(passo, z1, z2, C)
    variacao = 1.0 - math.cos(math.pi / z1)
    carga_eixo = 1.15 * ft
    fs = ruptura / (ft + fc)
    verificacoes = (
        minimo(
            "Fator de segurança à ruptura",
            fs,
            float(v["fs_minimo"]),
            "—",
            f"F_r/(F_t + F_c) = {ruptura:.0f}/{ft + fc:.0f}",
            "Prática de catálogo de correntes (Renold, Tsubaki)",
        ),
        recomendacao_minima(
            "Dentes da roda menor",
            z1,
            17.0,
            "dentes",
            "acima de 17 dentes o efeito poligonal cai para menos de 2 %",
            SHIGLEY_17,
        ),
        recomendacao(
            "Dentes da roda maior",
            z2,
            120.0,
            "dentes",
            "z₂ ≤ 120: acima disso a corrente alongada salta da roda",
            SHIGLEY_17,
        ),
        faixa_recomendada(
            "Entre centros em passos",
            C / passo,
            30.0,
            50.0,
            "passos",
            "faixa usual 30 a 50 passos",
            SHIGLEY_17,
        ),
        recomendacao(
            "Relação de transmissão", z2 / z1, 7.0, "—", "i ≤ 7 em um só estágio", SHIGLEY_17
        ),
    )
    return Resultado(
        resumo=(
            f"Tração de {ft / 1000:.2f} kN a {velocidade:.2f} m/s, corrente de {elos_par} elos e "
            f"fator de segurança {fs:.1f}."
        ),
        metricas=(
            Metrica("Tração F_t", ft / 1000.0, "kN"),
            Metrica("Velocidade", velocidade, "m/s"),
            Metrica("Primitivo da roda menor", d1, "mm", 1),
            Metrica("Primitivo da roda maior", d2, "mm", 1),
            Metrica("Número de elos", elos_par, "", 0),
            Metrica("Variação de velocidade", variacao * 100.0, "%", 2),
            Metrica("Carga no eixo", carga_eixo / 1000.0, "kN"),
            Metrica("Fator de segurança", fs, "", 1),
        ),
        verificacoes=verificacoes,
        hipoteses=(
            "Carga no eixo adotada em 1,15·F_t, prática de catálogo para corrente na horizontal.",
            "A capacidade por desgaste (potência de catálogo) é conferida no fabricante; aqui "
            "vai só a segurança à ruptura.",
            f"Comprimento exato de {elos:.2f} passos; adota-se o par acima para evitar elo "
            "de redução.",
        ),
        referencias=(SHIGLEY_17,),
    )


CAMPOS_CORRENTE = (
    Campo(
        "potencia_kW",
        "Potência transmitida",
        "A potência que passa pela corrente.",
        7.5,
        "kW",
        minimo=0.001,
        passo=0.5,
        secao="Serviço",
    ),
    Campo(
        "rotacao_rpm",
        "Rotação da roda menor",
        "Rotação do eixo da roda menor.",
        300.0,
        "rpm",
        minimo=0.1,
        passo=10.0,
        secao="Serviço",
    ),
    Campo(
        "fator_servico",
        "Fator de serviço K_s",
        "Multiplica a tração. Carga uniforme: 1,0. Choque moderado: 1,3. Choque pesado: 1,5 a 1,7.",
        1.3,
        minimo=1.0,
        maximo=4.0,
        passo=0.05,
        secao="Serviço",
    ),
    Campo(
        "passo_mm",
        "Passo da corrente p",
        "Passos usuais (ISO 606): 9,525; 12,7; 15,875; 19,05; 25,4; 31,75; 38,1; 44,45; 50,8.",
        25.4,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Geometria",
    ),
    Campo(
        "z1",
        "Dentes da roda menor z₁",
        "Abaixo de 17 dentes a corrente sobe e desce demais a cada dente e a marcha fica irregular.",
        19,
        minimo=6,
        maximo=150,
        passo=1,
        secao="Geometria",
    ),
    Campo(
        "z2",
        "Dentes da roda maior z₂",
        "Até cerca de 120 dentes.",
        57,
        minimo=6,
        maximo=300,
        passo=1,
        secao="Geometria",
    ),
    Campo(
        "C_mm",
        "Entre centros C",
        "Distância entre os centros das rodas. O usual é de 30 a 50 passos.",
        1016.0,
        "mm",
        minimo=1.0,
        passo=10.0,
        secao="Geometria",
    ),
    Campo(
        "fileiras",
        "Fileiras da corrente",
        "Corrente simples: 1. Dupla: 2. Tripla: 3.",
        1,
        minimo=1,
        maximo=6,
        passo=1,
        secao="Corrente",
    ),
    Campo(
        "ruptura_kN",
        "Carga de ruptura por fileira",
        "Carga mínima de ruptura de uma fileira, do catálogo. ISO 606 16B (25,4 mm): 60 kN.",
        60.0,
        "kN",
        minimo=0.001,
        passo=1.0,
        secao="Corrente",
    ),
    Campo(
        "massa_kg_m",
        "Massa por metro",
        "Massa da corrente por metro, do catálogo. Dá a força centrífuga.",
        2.7,
        "kg/m",
        minimo=0.0,
        passo=0.1,
        secao="Corrente",
    ),
    Campo(
        "fs_minimo",
        "Fator de segurança mínimo",
        "Mínimo usual sobre a ruptura: 8 em transmissão comum. Em içamento de pessoas ou de "
        "cargas sobre pessoas, siga a norma do equipamento.",
        8.0,
        minimo=1.0,
        maximo=30.0,
        passo=0.5,
        secao="Corrente",
    ),
)


# ---------------------------------------------------------------------------
# Flange de acoplamento
# ---------------------------------------------------------------------------


def calcular_acoplamento(v: Valores) -> Resultado:
    torque = float(v["torque_Nm"]) * float(v["fator_servico"])
    parafusos = int(v["parafusos"])
    circulo = float(v["circulo_mm"])
    d = float(v["d_parafuso_mm"])
    t = float(v["espessura_mm"])
    fs = float(v["fs"])
    sy_p = float(v["sy_parafuso_MPa"])
    sy_f = float(v["sy_flange_MPa"])
    atrito = float(v["atrito"])
    pre_carga = float(v["pre_carga_kN"]) * 1000.0

    forca = 2.0 * torque * 1000.0 / (parafusos * circulo)
    area = math.pi * d**2 / 4.0
    tau = forca / area
    esmagamento = forca / (d * t)
    torque_atrito = atrito * pre_carga * parafusos * circulo / 2.0 / 1000.0
    verificacoes = [
        limite(
            "Cisalhamento no parafuso",
            tau,
            0.577 * sy_p / fs,
            "MPa",
            f"τ = 2T/(n·D·A) ≤ 0,577·Sy/FS, com F = {forca:.0f} N por parafuso",
            "von Mises em cisalhamento puro",
        ),
        limite(
            "Esmagamento no furo do flange",
            esmagamento,
            sy_f / fs,
            "MPa",
            "σ = F/(d·t) ≤ Sy/FS",
            "Pressão de contato média",
        ),
    ]
    if pre_carga > 0:
        verificacoes.append(
            minimo(
                "Torque transmitido por atrito",
                torque_atrito,
                torque,
                "N·m",
                "T_at = μ·F_p·n·D/2",
                "Junta de atrito",
            )
        )
    return Resultado(
        resumo=f"Cada parafuso recebe {forca / 1000:.2f} kN com T = {torque:.0f} N·m de projeto.",
        metricas=(
            Metrica("Força por parafuso", forca / 1000.0, "kN"),
            Metrica("Tensão no parafuso", tau, "MPa", 1),
            Metrica("Esmagamento", esmagamento, "MPa", 1),
            Metrica("Torque de projeto", torque, "N·m", 1),
            Metrica("Torque por atrito", torque_atrito, "N·m", 1),
        ),
        verificacoes=tuple(verificacoes),
        hipoteses=(
            "Todos os parafusos dividem a carga por igual: vale para parafuso ajustado ao furo.",
            "Com folga no furo, o acoplamento trabalha por atrito e os parafusos só entram em "
            "corte depois de escorregar. Nesse caso informe a pré-carga.",
            "Parafuso de corpo cheio no plano de corte; se a rosca cruzar o plano, use o "
            "diâmetro da raiz.",
        ),
        referencias=("Norton, Projeto de Máquinas, cap. 10",),
    )


CAMPOS_ACOPLAMENTO = (
    Campo(
        "torque_Nm",
        "Torque nominal",
        "O torque que passa pelo acoplamento.",
        1500.0,
        "N·m",
        minimo=0.001,
        passo=50.0,
        secao="Carga",
    ),
    Campo(
        "fator_servico",
        "Fator de serviço K_s",
        "Multiplica o torque. Carga uniforme: 1,0 a 1,25. Choque moderado: 1,5. Choque pesado: 2,0.",
        1.5,
        minimo=1.0,
        maximo=4.0,
        passo=0.05,
        secao="Carga",
    ),
    Campo(
        "fs",
        "Fator de segurança",
        "Margem sobre o escoamento. Comece com 2,0 para acoplamento.",
        2.0,
        minimo=1.0,
        maximo=6.0,
        passo=0.1,
        secao="Carga",
    ),
    Campo(
        "parafusos",
        "Número de parafusos",
        "Parafusos no círculo do flange.",
        8,
        minimo=1,
        maximo=64,
        passo=1,
        secao="Flange",
    ),
    Campo(
        "circulo_mm",
        "Diâmetro do círculo de furos D",
        "Diâmetro em que estão os centros dos parafusos.",
        180.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Flange",
    ),
    Campo(
        "d_parafuso_mm",
        "Diâmetro resistente do parafuso d",
        "Diâmetro no plano de corte: o do corpo liso ou o da raiz da rosca.",
        16.0,
        "mm",
        minimo=0.5,
        passo=1.0,
        secao="Flange",
    ),
    Campo(
        "espessura_mm",
        "Espessura do flange t",
        "Espessura de um dos flanges, a menor das duas.",
        20.0,
        "mm",
        minimo=0.5,
        passo=1.0,
        secao="Flange",
    ),
    Campo(
        "sy_parafuso_MPa",
        "Escoamento do parafuso",
        "Classe 8.8: 640 MPa. Classe 10.9: 900 MPa.",
        640.0,
        "MPa",
        minimo=1.0,
        passo=10.0,
        secao="Materiais",
    ),
    Campo(
        "sy_flange_MPa",
        "Escoamento do flange",
        "Limite de escoamento do material do flange.",
        310.0,
        "MPa",
        minimo=1.0,
        passo=10.0,
        secao="Materiais",
    ),
    Campo(
        "pre_carga_kN",
        "Pré-carga por parafuso",
        "Força de aperto de cada parafuso. Deixe 0 para não verificar o atrito.",
        0.0,
        "kN",
        minimo=0.0,
        passo=5.0,
        secao="Atrito",
    ),
    Campo(
        "atrito",
        "Coeficiente de atrito μ",
        "Aço com aço limpo e sem pintura: cerca de 0,30. Superfície tratada: até 0,50.",
        0.30,
        minimo=0.05,
        maximo=0.8,
        passo=0.01,
        secao="Atrito",
    ),
)


CASOS: tuple[Caso, ...] = (
    Caso(
        "acionamento",
        "Motor e redutor",
        GRUPO,
        "Da potência do motor ao torque na saída, com partida e redutor de até 3 estágios.",
        "Comece por aqui quando você só tem a placa do motor. Sai o torque em cada estágio, o "
        "torque de projeto com o fator de serviço, o torque de pico e o tempo de partida.",
        CAMPOS_ACIONAMENTO,
        calcular_acionamento,
        r"T=\frac{9550\,P}{n},\qquad T_s=T\,i\,\eta,\qquad t=\frac{J\,\omega}{T_p-T_r}",
    ),
    Caso(
        "engrenagem",
        "Engrenagem cilíndrica",
        GRUPO,
        "Dentes retos ou helicoidais: forças no eixo, flexão no dente e pressão de contato.",
        "Calcula as forças que vão para o eixo e faz o pré-dimensionamento do dente por Lewis e "
        "pelo contato de Hertz. Mostra também o fator dinâmico e o risco de adelgaçamento.",
        CAMPOS_ENGRENAGEM,
        calcular_engrenagem,
        r"F_t=\frac{2T}{d},\quad F_r=\frac{F_t\tan\phi_n}{\cos\psi},\quad F_a=F_t\tan\psi,"
        r"\quad \sigma=\frac{K_oK_vK_mF_t}{b\,m\,Y}",
    ),
    Caso(
        "engrenagem_conica",
        "Engrenagem cônica",
        GRUPO,
        "Forças de um par cônico a 90°: a axial de um eixo é a radial do outro.",
        "Para eixos que se cruzam a 90°. Sai a força em cada eixo, tomada no meio da largura do "
        "dente.",
        CAMPOS_CONICA,
        calcular_conica,
        r"F_t=\frac{2T}{d_m},\quad F_r=F_t\tan\phi\cos\gamma,\quad F_a=F_t\tan\phi\sin\gamma",
    ),
    Caso(
        "sem_fim",
        "Sem-fim e coroa",
        GRUPO,
        "Forças, rendimento, calor a dissipar e autotravamento.",
        "O par sem-fim e coroa perde boa parte da potência em atrito. Este caso mostra o "
        "rendimento, o calor gerado e se o par trava sozinho quando o motor para.",
        CAMPOS_SEM_FIM,
        calcular_sem_fim,
        r"\eta=\frac{\cos\phi_n-f\tan\lambda}{\cos\phi_n+f\cot\lambda}",
    ),
    Caso(
        "correia",
        "Correia e polias",
        GRUPO,
        "Ramos tenso e frouxo, pré-tensão mínima, comprimento e carga no eixo.",
        "Serve para correia em V e plana. Sai a pré-tensão necessária para não deslizar e a força "
        "que a correia põe no eixo e nos mancais.",
        CAMPOS_CORREIA,
        calcular_correia,
        r"\frac{F_1-F_c}{F_2-F_c}=e^{\mu\theta/\sin(\beta/2)},\qquad F_t=F_1-F_2",
    ),
    Caso(
        "corrente",
        "Corrente de rolos",
        GRUPO,
        "Tração, número de elos, efeito poligonal e segurança à ruptura.",
        "Para transmissão por corrente de rolos. Sai a tração, o comprimento em elos (par), a "
        "variação de velocidade do efeito poligonal e o fator de segurança à ruptura.",
        CAMPOS_CORRENTE,
        calcular_corrente,
        r"d=\frac{p}{\sin(\pi/z)},\qquad V=\frac{z\,p\,n}{60000},\qquad F_t=\frac{P}{V}",
    ),
    Caso(
        "acoplamento",
        "Flange de acoplamento",
        GRUPO,
        "Parafusos de um flange sob torque: corte, esmagamento e atrito.",
        "Dois flanges unidos por parafusos em círculo. Verifica o corte nos parafusos, o "
        "esmagamento no furo e, se houver pré-carga, o torque por atrito.",
        CAMPOS_ACOPLAMENTO,
        calcular_acoplamento,
        r"F=\frac{2T}{n\,D},\qquad \tau=\frac{F}{A},\qquad T_{at}=\mu\,F_p\,n\,\frac{D}{2}",
    ),
)
