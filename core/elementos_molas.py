"""Molas de tração, de torção e prato. A de compressão fica em :mod:`core.elementos_molas_atrito`.

As duas helicoidais seguem o cap. 10 de Shigley, com as Tabelas 10-7 e 10-10 e as equações 10-34 a
10-41 e 10-51 a 10-58. A mola prato segue Almen e László, a base da DIN EN 16984; a norma não está
na pasta de normas, e por isso o limite de tensão é um dado e a fadiga fica para o fabricante.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core.elementos_base import (
    Campo,
    Caso,
    Grafico,
    Metrica,
    Ponto,
    Resultado,
    Valores,
    exigir,
    faixa_recomendada,
    informativo,
    limite,
    minimo,
    recomendacao,
    recomendacao_minima,
)
from core.elementos_molas_atrito import (
    FIOS,
    GRUPO_MOLAS,
    JATEADA,
    SEM_JATEAMENTO,
    SHIGLEY_10,
    ZIMMERLI,
    _sut_do_fio,
    limite_de_zimmerli,
)

ALMEN = "Almen e László, base da DIN EN 16984"
FABRICANTES = "Catálogos de fabricantes de mola prato"

#: Módulo de elasticidade em GPa, na mesma linha da Tabela 10-5 de Shigley que deu o G de ``FIOS``.
ELASTICIDADE = {
    "ASTM A228 corda de piano": 196.5,
    "ASTM A227 trefilado duro": 197.9,
    "ASTM A229 óleo-temperado": 196.5,
    "ASTM A232 cromo-vanádio": 203.4,
    "ASTM A401 cromo-silício": 203.4,
}

#: Fator mínimo contra o escoamento: o mesmo da mola de compressão.
N_ESTATICO = 1.2
#: Tabela 10-7, carga estática, em fração de S_ut. O corpo vai de 45 a 50 %: fica o lado seguro.
FRACAO_CORPO = 0.45
FRACAO_PONTA_TORCAO = 0.40
FRACAO_PONTA_FLEXAO = 0.75
#: Passagem da torção para a flexão pela energia de distorção (Shigley, fim da seção de torção).
FATOR_TORCAO = 0.577
DENSIDADE_DO_ACO = 7.85e-6  # kg/mm³

VIDA_100_MIL = "100 mil ciclos"
VIDA_1_MILHAO = "1 milhão de ciclos"
#: Tabela 10-10: S_r/S_ut em flexão repetida, (sem jato, com jato), por vida. Fio A232 e, nos demais
#: fios, a coluna do A228, que é a mais baixa: a tabela não traz o A227, o A229 nem o A401.
FADIGA_A232 = {VIDA_100_MIL: (0.55, 0.64), VIDA_1_MILHAO: (0.53, 0.62)}
FADIGA_DEMAIS = {VIDA_100_MIL: (0.53, 0.62), VIDA_1_MILHAO: (0.50, 0.60)}
FIO_A232 = "ASTM A232 cromo-vanádio"


def _goodman(alternada: float, media: float, s_e: float, s_u: float) -> float:
    soma = alternada / s_e + media / s_u
    return 1.0 / soma if soma > 0 else math.inf


def _frequencia_propria(rigidez: float, d: float, diametro: float, espiras: float) -> float:
    """Frequência entre dois apoios: k em N/m e massa em kg, f = ½·√(k/m)."""
    massa = math.pi * d**2 / 4.0 * math.pi * diametro * espiras * DENSIDADE_DO_ACO
    return 0.5 * math.sqrt(rigidez * 1000.0 / massa)


# ---------------------------------------------------------------------------
# Mola de tração
# ---------------------------------------------------------------------------


def faixa_da_tensao_inicial(c: float) -> tuple[float, float]:
    """Faixa preferida de τ_i, sem correção, em MPa: eq. 10-41 de Shigley, de psi para MPa."""
    # Índice absurdo (D mil vezes o arame) estourava o exp: a faixa já é zero muito antes.
    meio = 231.0 / math.exp(min(0.105 * c, 700.0))
    largura = 6.9 * (4.0 - (c - 3.0) / 6.5)
    return meio - largura, meio + largura


def calcular_mola_tracao(v: Valores) -> Resultado:
    fio = str(v["fio"])
    d = float(v["d_mm"])
    diametro = float(v["D_mm"])
    corpo = float(v["espiras"])
    f_inicial = float(v["f_inicial_N"])
    f_max = float(v["f_max_N"])
    f_min = float(v["f_min_N"])
    r2 = float(v["r2_mm"])
    exigir(diametro > d, "O diâmetro médio deve ser maior que o diâmetro do fio.")
    exigir(f_max >= f_min, "A força máxima deve ser maior ou igual à mínima.")
    exigir(f_max > f_inicial, "Abaixo da força inicial a mola nem abre: aumente a força máxima.")
    exigir(2.0 * r2 > d, "O raio da dobra do gancho é medido no centro do fio: deve passar de d/2.")

    g = FIOS[fio][2] * 1000.0
    e = ELASTICIDADE[fio] * 1000.0
    sut = _sut_do_fio(fio, d)
    c = diametro / d
    c2 = 2.0 * r2 / d
    kb = (4.0 * c + 2.0) / (4.0 * c - 3.0)
    # No gancho comum, o raio r₁ da eq. 10-35 é o da própria espira: C₁ = C.
    k_a = (4.0 * c**2 - c - 1.0) / (4.0 * c * (c - 1.0))
    k_b = (4.0 * c2 - 1.0) / (4.0 * c2 - 4.0)
    ativas = corpo + g / e
    rigidez = g * d**4 / (8.0 * diametro**3 * ativas)
    comprimento_livre = (2.0 * c - 1.0 + corpo) * d
    deflexao = (f_max - f_inicial) / rigidez

    fator_torcao = 8.0 * diametro / (math.pi * d**3)
    fator_flexao = k_a * 16.0 * diametro / (math.pi * d**3) + 4.0 / (math.pi * d**2)
    tau_corpo = kb * fator_torcao * f_max
    sigma_a = fator_flexao * f_max
    tau_b = k_b * fator_torcao * f_max
    tau_inicial = fator_torcao * f_inicial
    baixo, alto = faixa_da_tensao_inicial(c)

    # Nota da Tabela 10-7: com tensão inicial alta, o corpo fica com o limite da ponta.
    fracao_corpo = FRACAO_PONTA_TORCAO if tau_inicial > alto else FRACAO_CORPO
    verificacoes = [
        minimo(
            "Tensão no corpo",
            fracao_corpo * sut / tau_corpo,
            N_ESTATICO,
            "—",
            f"n = {fracao_corpo * 100:.0f} % de S_ut/τ, com τ = K_B·8FD/(π·d³) = {tau_corpo:.0f} MPa",
            SHIGLEY_10,
        ),
        minimo(
            "Flexão no gancho (ponto A)",
            FRACAO_PONTA_FLEXAO * sut / sigma_a,
            N_ESTATICO,
            "—",
            f"n = 75 % de S_ut/σ_A, com σ_A = {sigma_a:.0f} MPa",
            SHIGLEY_10,
        ),
        minimo(
            "Torção no gancho (ponto B)",
            FRACAO_PONTA_TORCAO * sut / tau_b,
            N_ESTATICO,
            "—",
            f"n = 40 % de S_ut/τ_B, com τ_B = {tau_b:.0f} MPa e C₂ = {c2:.2f}",
            SHIGLEY_10,
        ),
        faixa_recomendada(
            "Tensão inicial",
            tau_inicial,
            baixo,
            alto,
            "MPa",
            f"τ_i = 8F_iD/(π·d³), faixa preferida de {baixo:.0f} a {alto:.0f} MPa para C = {c:.1f}",
            SHIGLEY_10,
        ),
        faixa_recomendada(
            "Índice de mola C", c, 4.0, 12.0, "—", "C = D/d, faixa usual 4 a 12", SHIGLEY_10
        ),
        faixa_recomendada(
            "Espiras do corpo", corpo, 3.0, 15.0, "—", "faixa usual 3 a 15", SHIGLEY_10
        ),
    ]

    alertas: list[str] = []
    if bool(v["ciclica"]):
        f_alternada = (f_max - f_min) / 2.0
        f_media = (f_max + f_min) / 2.0
        ssu = 0.67 * sut
        sse = limite_de_zimmerli(str(v["superficie"]), ssu)
        s_e = sse / FATOR_TORCAO
        n_exigido = float(v["n_fadiga"])
        for nome, fator, limite_e, limite_u, simbolo in (
            ("Fadiga no corpo", kb * fator_torcao, sse, ssu, "τ"),
            ("Fadiga no gancho (ponto A)", fator_flexao, s_e, sut, "σ"),
            ("Fadiga no gancho (ponto B)", k_b * fator_torcao, sse, ssu, "τ"),
        ):
            alternada, media = fator * f_alternada, fator * f_media
            verificacoes.append(
                minimo(
                    nome,
                    _goodman(alternada, media, limite_e, limite_u),
                    n_exigido,
                    "—",
                    f"Goodman com {simbolo}_a = {alternada:.0f} e {simbolo}_m = {media:.0f} MPa, "
                    f"S_e = {limite_e:.0f} MPa",
                    ZIMMERLI,
                )
            )
        if f_min < f_inicial:
            alertas.append(
                "A força mínima fica abaixo da inicial: nesse trecho a mola está fechada e não muda "
                "de comprimento."
            )

    frequencia = _frequencia_propria(rigidez, d, diametro, ativas)
    excitacao = float(v["rotacao_rpm"]) / 60.0
    if excitacao > 0:
        verificacoes.append(
            recomendacao_minima(
                "Frequência própria da mola",
                frequencia,
                15.0 * excitacao,
                "Hz",
                "f ≥ 15 vezes a frequência da excitação, para evitar surto",
                SHIGLEY_10,
            )
        )
    comprimento_fio = math.pi * diametro * (corpo + 1.0) + 2.0 * math.pi * diametro
    massa = math.pi * d**2 / 4.0 * comprimento_fio * DENSIDADE_DO_ACO
    return Resultado(
        resumo=(
            f"k = {rigidez:.2f} N/mm: com {f_max:.0f} N a mola abre {deflexao:.1f} mm. A tensão que "
            f"manda fica no gancho, com {max(sigma_a, tau_b):.0f} MPa."
        ),
        metricas=(
            Metrica("Rigidez k", rigidez, "N/mm", 2),
            Metrica("Abertura na força máxima", deflexao, "mm", 1),
            Metrica("Comprimento livre", comprimento_livre, "mm", 1),
            Metrica("Comprimento na força máxima", comprimento_livre + deflexao, "mm", 1),
            Metrica("Tensão no corpo", tau_corpo, "MPa", 0),
            Metrica("Flexão no gancho", sigma_a, "MPa", 0),
            Metrica("Torção no gancho", tau_b, "MPa", 0),
            Metrica("Tensão inicial", tau_inicial, "MPa", 0),
            Metrica("Resistência S_ut do fio", sut, "MPa", 0),
            Metrica("Frequência própria", frequencia, "Hz", 0),
            Metrica("Massa", massa, "kg", 3),
            Metrica("Índice C", c, "", 2),
        ),
        verificacoes=tuple(verificacoes),
        pontos=(
            Ponto("Corpo, força máxima", 0.0, 0.0, tau_corpo),
            Ponto("Gancho, ponto A", sigma_a),
            Ponto("Gancho, ponto B", 0.0, 0.0, tau_b),
        ),
        alertas=tuple(alertas),
        hipoteses=(
            "Mola helicoidal de tração, de fio redondo, enrolada fechada e com gancho comum nas "
            "duas pontas: o raio maior do gancho é o da espira.",
            "Limites estáticos da Tabela 10-7 de Shigley, para mola sem remoção de assentamento e "
            "com alívio a baixa temperatura. O corpo usa 45 %, o lado seguro da faixa de 45 a 50 %.",
            "Fadiga por Zimmerli, com S_e = S_se/0,577 na flexão do gancho: vale para fios abaixo de "
            "10 mm.",
            "A mola de tração não tem bloco: se o gancho rompe, a carga fica solta. Quando isso for "
            "perigoso, use um cabo de segurança ou passe para uma mola de compressão.",
        ),
        referencias=(SHIGLEY_10,),
    )


def _campo_do_fio(padrao: str) -> Campo:
    return Campo(
        "fio",
        "Material do fio",
        "Corda de piano é a mais resistente nos diâmetros pequenos. Cromo-silício serve para "
        "choque e temperatura mais alta.",
        padrao,
        opcoes=tuple(FIOS),
        secao="Mola",
    )


def _campos_de_fadiga(ajuda: str) -> tuple[Campo, Campo]:
    return (
        Campo(
            "ciclica",
            "Carga repetida (fadiga)",
            ajuda,
            True,
            secao="Serviço",
        ),
        Campo(
            "f_min_N",
            "Força mínima",
            "A menor força do ciclo. Mola que trabalha sempre com alguma força dura mais.",
            60.0,
            "N",
            minimo=0.0,
            passo=5.0,
            secao="Serviço",
            quando=("ciclica", (True,)),
        ),
    )


CAMPOS_TRACAO = (
    _campo_do_fio("ASTM A227 trefilado duro"),
    Campo(
        "d_mm",
        "Diâmetro do fio d",
        "Diâmetro do fio. Quanto mais fino, maior a resistência do material, mas menor a força.",
        3.0,
        "mm",
        minimo=0.1,
        passo=0.1,
        secao="Mola",
    ),
    Campo(
        "D_mm",
        "Diâmetro médio D",
        "Diâmetro da espira, medido no centro do fio.",
        24.0,
        "mm",
        minimo=0.5,
        passo=1.0,
        secao="Mola",
    ),
    Campo(
        "espiras",
        "Espiras do corpo N_b",
        "Número de espiras entre os dois ganchos, que ficam encostadas quando a mola está parada.",
        12.0,
        minimo=1.0,
        maximo=200.0,
        passo=0.5,
        secao="Mola",
    ),
    Campo(
        "f_inicial_N",
        "Força inicial F_i",
        "Força que a mola já tem ao sair da fabricação. Abaixo dela, as espiras nem se separam.",
        45.0,
        "N",
        minimo=0.0,
        passo=5.0,
        secao="Mola",
    ),
    Campo(
        "r2_mm",
        "Raio da dobra do gancho r₂",
        "Raio no centro do fio, na dobra entre o gancho e o corpo. Dobra fechada concentra tensão "
        "e costuma ser onde a mola quebra.",
        6.0,
        "mm",
        minimo=0.1,
        passo=0.5,
        secao="Mola",
    ),
    Campo(
        "f_max_N",
        "Força máxima",
        "A maior força de trabalho.",
        150.0,
        "N",
        minimo=0.001,
        passo=10.0,
        secao="Serviço",
    ),
    *_campos_de_fadiga(
        "Ligue se a força varia durante o serviço. Na tração, o gancho é o ponto fraco."
    ),
    Campo(
        "superficie",
        "Superfície do fio",
        "O jateamento cria compressão na superfície e aumenta bastante a vida à fadiga.",
        SEM_JATEAMENTO,
        opcoes=(SEM_JATEAMENTO, JATEADA),
        secao="Serviço",
        quando=("ciclica", (True,)),
    ),
    Campo(
        "n_fadiga",
        "Fator mínimo à fadiga",
        "Fator de segurança exigido contra a fadiga. Comece com 1,3 a 1,5.",
        1.3,
        minimo=1.0,
        maximo=4.0,
        passo=0.1,
        secao="Serviço",
        quando=("ciclica", (True,)),
    ),
    Campo(
        "rotacao_rpm",
        "Rotação da excitação",
        "Ciclos por minuto da máquina que excita a mola. Deixe 0 para não comparar.",
        0.0,
        "rpm",
        minimo=0.0,
        passo=100.0,
        secao="Serviço",
    ),
)


# ---------------------------------------------------------------------------
# Mola de torção
# ---------------------------------------------------------------------------


def amplitude_de_gerber(sigma_m_sobre_a: float, s_r: float, sut: float) -> float:
    """S_a de Gerber para a linha de carga, eq. 10-58 e seguintes.

    ``sigma_m_sobre_a`` é σ_m/σ_a, o inverso da inclinação r da linha. O S_e sai de S_r, a tensão
    recomendada com carga repetida.
    """
    s_e = (s_r / 2.0) / (1.0 - (s_r / 2.0 / sut) ** 2)
    if sigma_m_sobre_a <= 0:
        return s_e
    r = 1.0 / sigma_m_sobre_a
    return r**2 * sut**2 / (2.0 * s_e) * (-1.0 + math.sqrt(1.0 + (2.0 * s_e / (r * sut)) ** 2))


def calcular_mola_torcao(v: Valores) -> Resultado:
    fio = str(v["fio"])
    d = float(v["d_mm"])
    diametro = float(v["D_mm"])
    corpo = float(v["espiras"])
    l1 = float(v["l1_mm"])
    l2 = float(v["l2_mm"])
    braco = float(v["braco_mm"])
    f_max = float(v["f_max_N"])
    f_min = float(v["f_min_N"])
    d_pino = float(v["d_pino_mm"])
    exigir(diametro > d, "O diâmetro médio deve ser maior que o diâmetro do fio.")
    exigir(f_max >= f_min, "A força máxima deve ser maior ou igual à mínima.")

    e = ELASTICIDADE[fio] * 1000.0
    sut = _sut_do_fio(fio, d)
    # Tabela 10-6 dividida por 0,577: dá os 0,78 e 0,87 de S_ut do livro.
    sy = FIOS[fio][3] * sut / FATOR_TORCAO
    c = diametro / d
    k_i = (4.0 * c**2 - c - 1.0) / (4.0 * c * (c - 1.0))
    momento_max = f_max * braco
    fator = k_i * 32.0 / (math.pi * d**3)
    sigma = fator * momento_max
    ativas = corpo + (l1 + l2) / (3.0 * math.pi * diametro)
    rigidez_por_volta = d**4 * e / (10.8 * diametro * ativas)
    voltas = momento_max / rigidez_por_volta
    # Só o corpo fecha a hélice: tira a parte das pontas.
    voltas_corpo = 10.8 * momento_max * diametro * corpo / (d**4 * e)
    diametro_carregado = corpo * diametro / (corpo + voltas_corpo)
    interno_carregado = diametro_carregado - d
    comprimento_corpo = d * (corpo + 1.0 + voltas_corpo)

    verificacoes = [
        minimo(
            "Tensão na força máxima",
            sy / sigma,
            N_ESTATICO,
            "—",
            f"n = S_y/σ, com S_y = {sy:.0f} MPa e σ = K_i·32M/(π·d³) = {sigma:.0f} MPa",
            SHIGLEY_10,
        ),
        faixa_recomendada(
            "Índice de mola C", c, 4.0, 12.0, "—", "C = D/d, faixa usual 4 a 12", SHIGLEY_10
        ),
        faixa_recomendada(
            "Espiras do corpo", corpo, 3.0, 15.0, "—", "faixa usual 3 a 15", SHIGLEY_10
        ),
    ]
    if d_pino > 0:
        verificacoes += [
            limite(
                "Diâmetro do pino",
                d_pino,
                interno_carregado,
                "mm",
                f"D_p ≤ D'_i, o interno sob carga, que fecha de {diametro - d:.2f} para "
                f"{interno_carregado:.2f} mm",
                SHIGLEY_10,
            ),
        ]

    if bool(v["ciclica"]):
        momento_a = (f_max - f_min) * braco / 2.0
        momento_m = (f_max + f_min) * braco / 2.0
        tabela = FADIGA_A232 if fio == FIO_A232 else FADIGA_DEMAIS
        fracao = tabela[str(v["vida"])][0 if str(v["superficie"]) == SEM_JATEAMENTO else 1]
        s_r = fracao * sut
        s_a = amplitude_de_gerber(momento_m / momento_a if momento_a > 0 else 0.0, s_r, sut)
        sigma_a = fator * momento_a
        n_fadiga = s_a / sigma_a if sigma_a > 0 else math.inf
        verificacoes.append(
            minimo(
                "Fadiga da mola",
                n_fadiga,
                float(v["n_fadiga"]),
                "—",
                f"Gerber com S_r = {fracao * 100:.0f} % de S_ut, S_a = {s_a:.0f} e "
                f"σ_a = {sigma_a:.0f} MPa",
                SHIGLEY_10,
            )
        )

    rigidez_grau = rigidez_por_volta / 360.0
    comprimento_fio = math.pi * diametro * corpo + l1 + l2
    massa = math.pi * d**2 / 4.0 * comprimento_fio * DENSIDADE_DO_ACO
    return Resultado(
        resumo=(
            f"k = {rigidez_grau:.1f} N·mm por grau: com {momento_max:.0f} N·mm a mola gira "
            f"{voltas * 360.0:.0f}° e fica a {sigma:.0f} MPa na fibra interna."
        ),
        metricas=(
            Metrica("Rigidez", rigidez_grau, "N·mm/°", 2),
            Metrica("Giro na força máxima", voltas * 360.0, "°", 1),
            Metrica("Momento máximo", momento_max, "N·mm", 0),
            Metrica("Tensão na força máxima", sigma, "MPa", 0),
            Metrica("Diâmetro interno sob carga", interno_carregado, "mm", 2),
            Metrica("Comprimento do corpo sob carga", comprimento_corpo, "mm", 1),
            Metrica("Resistência S_ut do fio", sut, "MPa", 0),
            Metrica("Limite S_y em flexão", sy, "MPa", 0),
            Metrica("Espiras ativas equivalentes", ativas, "", 2),
            Metrica("Massa", massa, "kg", 3),
            Metrica("Índice C", c, "", 2),
        ),
        verificacoes=tuple(verificacoes),
        pontos=(Ponto("Fio, fibra interna, força máxima", sigma),),
        hipoteses=(
            "Mola helicoidal de torção, de fio redondo. O fio trabalha em flexão, apesar do nome.",
            "A força fecha a mola, no sentido do enrolamento. No sentido contrário, a tensão "
            "residual do enrolamento joga contra e a tabela de fadiga não vale.",
            "Rigidez com o 10,8 de Shigley, que inclui o atrito entre as espiras e com o pino, no "
            "lugar do 10,2 teórico.",
            "Tensão com K_i, na fibra interna, a maior das duas. S_y é a Tabela 10-6 dividida por "
            "0,577.",
            "Fadiga pela Tabela 10-10, que vale sem surto e com a mola aliviada. Ela só traz os "
            "fios A228, A230 e A232: os outros usam a coluna do A228, que é a mais baixa.",
        ),
        referencias=(SHIGLEY_10,),
    )


CAMPOS_TORCAO = (
    _campo_do_fio("ASTM A228 corda de piano"),
    Campo(
        "d_mm",
        "Diâmetro do fio d",
        "Diâmetro do fio. Quanto mais fino, maior a resistência do material, mas menor o momento.",
        3.0,
        "mm",
        minimo=0.1,
        passo=0.1,
        secao="Mola",
    ),
    Campo(
        "D_mm",
        "Diâmetro médio D",
        "Diâmetro da espira, medido no centro do fio.",
        20.0,
        "mm",
        minimo=0.5,
        passo=1.0,
        secao="Mola",
    ),
    Campo(
        "espiras",
        "Espiras do corpo N_b",
        "Número de voltas do corpo da mola, sem contar as duas pernas retas.",
        8.0,
        minimo=1.0,
        maximo=200.0,
        passo=0.25,
        secao="Mola",
    ),
    Campo(
        "l1_mm",
        "Perna 1 ℓ₁",
        "Comprimento reto da perna onde a força é aplicada. As pernas também dobram e somam giro.",
        30.0,
        "mm",
        minimo=0.0,
        passo=5.0,
        secao="Mola",
    ),
    Campo(
        "l2_mm",
        "Perna 2 ℓ₂",
        "Comprimento reto da perna que fica presa.",
        30.0,
        "mm",
        minimo=0.0,
        passo=5.0,
        secao="Mola",
    ),
    Campo(
        "d_pino_mm",
        "Diâmetro do pino D_p",
        "Pino que passa por dentro da mola. A mola fecha sob carga e pode prender nele. Deixe 0 se "
        "não houver pino.",
        14.0,
        "mm",
        minimo=0.0,
        passo=1.0,
        secao="Mola",
    ),
    Campo(
        "f_max_N",
        "Força máxima",
        "A maior força na perna, sempre no sentido que fecha a mola.",
        40.0,
        "N",
        minimo=0.001,
        passo=5.0,
        secao="Serviço",
    ),
    Campo(
        "braco_mm",
        "Braço da força a",
        "Distância do eixo da mola até a linha da força. Força vezes braço dá o momento.",
        40.0,
        "mm",
        minimo=0.1,
        passo=5.0,
        secao="Serviço",
    ),
    Campo(
        "ciclica",
        "Carga repetida (fadiga)",
        "Ligue se a mola abre e fecha durante o serviço, como em tampas e alavancas de retorno.",
        True,
        secao="Serviço",
    ),
    Campo(
        "f_min_N",
        "Força mínima",
        "A menor força do ciclo, no mesmo sentido da máxima. A mola não deve inverter de sentido.",
        10.0,
        "N",
        minimo=0.0,
        passo=5.0,
        secao="Serviço",
        quando=("ciclica", (True,)),
    ),
    Campo(
        "vida",
        "Vida desejada",
        "Número de ciclos que a mola precisa aguentar.",
        VIDA_1_MILHAO,
        opcoes=(VIDA_100_MIL, VIDA_1_MILHAO),
        secao="Serviço",
        quando=("ciclica", (True,)),
    ),
    Campo(
        "superficie",
        "Superfície do fio",
        "O jateamento aumenta a vida à fadiga, mas nem sempre dá para jatear uma mola de torção.",
        SEM_JATEAMENTO,
        opcoes=(SEM_JATEAMENTO, JATEADA),
        secao="Serviço",
        quando=("ciclica", (True,)),
    ),
    Campo(
        "n_fadiga",
        "Fator mínimo à fadiga",
        "Fator de segurança exigido contra a fadiga. Comece com 1,3 a 1,5.",
        1.3,
        minimo=1.0,
        maximo=4.0,
        passo=0.1,
        secao="Serviço",
        quando=("ciclica", (True,)),
    ),
)


# ---------------------------------------------------------------------------
# Mola prato
# ---------------------------------------------------------------------------

POISSON_MOLA = 0.3
#: Abaixo disso a curva sobe sempre; acima tem pico e trecho em que a força cai.
LIMITE_CURVA_QUE_CAI = math.sqrt(2.0)


@dataclass(frozen=True)
class Disco:
    """Um disco de mola prato sem apoios planos (K₄ = 1). Medidas em mm e módulo em MPa."""

    d_e: float
    d_i: float
    t: float
    h0: float
    modulo: float = 206_000.0

    @property
    def delta(self) -> float:
        return self.d_e / self.d_i

    @property
    def k1(self) -> float:
        d = self.delta
        return ((d - 1.0) / d) ** 2 / ((d + 1.0) / (d - 1.0) - 2.0 / math.log(d)) / math.pi

    @property
    def k2(self) -> float:
        d = self.delta
        return 6.0 / math.pi * ((d - 1.0) / math.log(d) - 1.0) / math.log(d)

    @property
    def k3(self) -> float:
        d = self.delta
        return 3.0 / math.pi * (d - 1.0) / math.log(d)

    @property
    def _base(self) -> float:
        return 4.0 * self.modulo / (1.0 - POISSON_MOLA**2) / (self.k1 * self.d_e**2)

    def forca(self, s: float) -> float:
        a, h = s / self.t, self.h0 / self.t
        return self._base * self.t**4 * a * ((h - a) * (h - a / 2.0) + 1.0)

    def rigidez(self, s: float) -> float:
        """dF/ds: pode ser negativa depois do pico da curva."""
        a, h = s / self.t, self.h0 / self.t
        return self._base * self.t**3 * (h**2 - 3.0 * h * a + 1.5 * a**2 + 1.0)

    def tensoes(self, s: float) -> dict[str, float]:
        """As tensões em MPa, com tração positiva. OM é o topo da parede, no meio da largura."""
        c = -self._base * self.t**2 * (s / self.t)
        meio = self.h0 / self.t - s / (2.0 * self.t)
        k2, k3 = self.k2, self.k3
        return {
            "OM": c * 3.0 / math.pi,
            "I": c * (k2 * meio + k3),
            "II": c * (k2 * meio - k3),
            "III": c / self.delta * ((k2 - 2.0 * k3) * meio - k3),
            "IV": c / self.delta * ((k2 - 2.0 * k3) * meio + k3),
        }

    @property
    def curso(self) -> float:
        """Até onde a força sobe: o pico da curva ou, sem pico, o disco plano."""
        h = self.h0 / self.t
        if h <= LIMITE_CURVA_QUE_CAI:
            return self.h0
        return self.t * (h - math.sqrt(3.0 * h**2 - 6.0) / 3.0)

    def deflexao(self, forca: float) -> float:
        """A deflexão de um disco para a força dada, no trecho em que a curva sobe."""
        baixo, alto = 0.0, self.curso
        for _ in range(80):
            meio = (baixo + alto) / 2.0
            if self.forca(meio) < forca:
                baixo = meio
            else:
                alto = meio
        return (baixo + alto) / 2.0


def _curva_da_pilha(
    disco: Disco, grupos: int, por_grupo: int
) -> tuple[tuple[float, float, str], ...]:
    passos = 60
    return tuple(
        (grupos * s, por_grupo * disco.forca(s), "Força")
        for s in (disco.h0 * i / passos for i in range(passos + 1))
    )


def calcular_mola_prato(v: Valores) -> Resultado:
    d_e = float(v["de_mm"])
    d_i = float(v["di_mm"])
    t = float(v["t_mm"])
    h0 = float(v["h0_mm"])
    grupos = int(v["grupos"])
    por_grupo = int(v["por_grupo"])
    f_max = float(v["f_max_N"])
    f_min = float(v["f_min_N"])
    tensao_limite = float(v["limite_MPa"])
    exigir(d_e > 1.2 * d_i, "O diâmetro externo deve passar de 1,2 vez o interno.")
    exigir(f_max >= f_min, "A força máxima deve ser maior ou igual à mínima.")

    disco = Disco(d_e, d_i, t, h0, float(v["e_GPa"]) * 1000.0)
    capacidade = por_grupo * disco.forca(disco.curso)
    exigir(
        f_max <= capacidade,
        f"A pilha só chega a {capacidade:.0f} N: acima disso o disco fica plano ou salta.",
    )
    s_max = disco.deflexao(f_max / por_grupo)
    s_min = disco.deflexao(f_min / por_grupo)
    tensoes = disco.tensoes(s_max)
    altura_livre = grupos * (h0 + por_grupo * t)
    rigidez = disco.rigidez(s_max) * por_grupo / grupos
    forca_de_catalogo = disco.forca(0.75 * h0)

    verificacoes = [
        limite(
            "Compressão na parede (σ_OM)",
            abs(tensoes["OM"]),
            tensao_limite,
            "MPa",
            "|σ_OM| ≤ limite estático do aço do disco",
            ALMEN,
        ),
        recomendacao(
            "Curso de trabalho",
            s_max,
            0.75 * h0,
            "mm",
            "s ≤ 0,75·h₀ por disco: perto do plano, a força medida foge do cálculo",
            FABRICANTES,
        ),
        faixa_recomendada(
            "Razão D_e/D_i",
            disco.delta,
            1.75,
            2.5,
            "—",
            "faixa de validade do cálculo",
            FABRICANTES,
        ),
        faixa_recomendada("Razão D_e/t", d_e / t, 16.0, 40.0, "—", "faixa usual", FABRICANTES),
        faixa_recomendada("Razão h₀/t", h0 / t, 0.4, 1.3, "—", "faixa usual", FABRICANTES),
    ]

    alertas: list[str] = []
    if h0 / t > LIMITE_CURVA_QUE_CAI:
        alertas.append(
            f"Com h₀/t = {h0 / t:.2f}, acima de 1,41, a curva tem pico e depois a força cai. Isso "
            "serve a mecanismo de salto, mas numa pilha em série os discos saltam um de cada vez."
        )
    if bool(v["ciclica"]):
        verificacoes.append(
            recomendacao_minima(
                "Pré-carga mínima",
                f_min / por_grupo,
                0.15 * forca_de_catalogo,
                "N",
                "F_mín ≥ 15 % da força a 0,75·h₀, por disco: sem pré-carga surgem trincas na borda",
                FABRICANTES,
            )
        )
        tensoes_min = disco.tensoes(s_min)
        ponto = "III" if tensoes["III"] >= tensoes["II"] else "II"
        superior, inferior = tensoes[ponto], tensoes_min[ponto]
        verificacoes += [
            informativo(f"σ_o no ponto {ponto}", superior, "MPa", "na força máxima", ALMEN),
            informativo(f"σ_u no ponto {ponto}", inferior, "MPa", "na força mínima", ALMEN),
            informativo("Variação de tensão σ_h", superior - inferior, "MPa", "σ_o − σ_u", ALMEN),
        ]
        alertas.append(
            "A vida à fadiga do disco não é calculada aqui: leve σ_o e σ_u ao diagrama da DIN EN "
            "16984 ou do fabricante."
        )

    destaques = [(grupos * s_max, f_max, f"{f_max:.0f} N")]
    if bool(v["ciclica"]) and s_min < s_max:
        destaques.append((grupos * s_min, f_min, f"{f_min:.0f} N"))
    return Resultado(
        resumo=(
            f"Com {f_max:.0f} N a pilha baixa {grupos * s_max:.2f} mm, com cada disco em "
            f"{s_max / h0 * 100:.0f} % do curso até o plano, e |σ_OM| = {abs(tensoes['OM']):.0f} MPa."
        ),
        metricas=(
            Metrica("Deflexão da pilha", grupos * s_max, "mm", 2),
            Metrica("Altura livre da pilha", altura_livre, "mm", 2),
            Metrica("Altura na força máxima", altura_livre - grupos * s_max, "mm", 2),
            Metrica("Rigidez na força máxima", rigidez, "N/mm", 0),
            Metrica("Força com o disco plano", por_grupo * disco.forca(h0), "N", 0),
            Metrica("Força a 0,75·h₀", por_grupo * forca_de_catalogo, "N", 0),
            Metrica("Tensão σ_OM", tensoes["OM"], "MPa", 0),
            Metrica("Tensão σ_I, borda interna de cima", tensoes["I"], "MPa", 0),
            Metrica("Tensão σ_II, borda interna de baixo", tensoes["II"], "MPa", 0),
            Metrica("Tensão σ_III, borda externa de baixo", tensoes["III"], "MPa", 0),
            Metrica("Discos na pilha", grupos * por_grupo, "", 0),
            Metrica("Razão h₀/t", h0 / t, "", 2),
        ),
        verificacoes=tuple(verificacoes),
        pontos=(
            Ponto("Borda interna de cima (I)", tensoes["I"]),
            Ponto("Borda interna de baixo (II)", tensoes["II"]),
            Ponto("Borda externa de baixo (III)", tensoes["III"]),
        ),
        graficos=(
            Grafico(
                "Curva da pilha",
                "Deflexão da pilha (mm)",
                "Força (N)",
                _curva_da_pilha(disco, grupos, por_grupo),
                cor="#0B6E99",
                destaques=tuple(destaques),
            ),
        ),
        alertas=tuple(alertas),
        hipoteses=(
            "Fórmulas de Almen e László para disco de seção retangular, sem apoios planos, com "
            "coeficiente de Poisson 0,3.",
            "A pilha soma sem atrito: discos em paralelo somam força, grupos em série somam curso. "
            "Na prática, cada superfície em contato acrescenta atrito e a força real é maior ao "
            "comprimir e menor ao soltar.",
            "A borda interna de cima (I) tem a maior tensão, mas ela é local: a verificação "
            "estática olha σ_OM, e por isso o ponto I passa do limite sem reprovar.",
            "Uma pilha longa precisa de guia pelo furo ou por fora, com folga.",
            "Limite de tensão, curso e pré-carga são dados de catálogo: confirme com o fabricante "
            "do disco.",
        ),
        referencias=(ALMEN, FABRICANTES, SHIGLEY_10),
    )


CAMPOS_PRATO = (
    Campo(
        "de_mm",
        "Diâmetro externo D_e",
        "Maior diâmetro do disco. É o que precisa caber no furo ou na guia.",
        40.0,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Disco",
    ),
    Campo(
        "di_mm",
        "Diâmetro interno D_i",
        "Furo do disco, por onde passa a guia. Normalmente é cerca da metade do externo.",
        20.4,
        "mm",
        minimo=0.5,
        passo=0.5,
        secao="Disco",
    ),
    Campo(
        "t_mm",
        "Espessura t",
        "Espessura da chapa do disco. É a medida que mais muda a força.",
        2.25,
        "mm",
        minimo=0.05,
        passo=0.05,
        secao="Disco",
    ),
    Campo(
        "h0_mm",
        "Altura do cone h₀",
        "Quanto o disco baixa até ficar plano, sem contar a espessura.",
        0.9,
        "mm",
        minimo=0.01,
        passo=0.05,
        secao="Disco",
    ),
    Campo(
        "e_GPa",
        "Módulo de elasticidade E",
        "206 GPa para os aços de mola usuais.",
        206.0,
        "GPa",
        minimo=50.0,
        maximo=300.0,
        passo=1.0,
        secao="Disco",
    ),
    Campo(
        "grupos",
        "Grupos em série n_s",
        "Grupos empilhados um contra o outro. Cada grupo a mais soma curso, com a mesma força.",
        4,
        minimo=1,
        maximo=200,
        secao="Pilha",
    ),
    Campo(
        "por_grupo",
        "Discos em paralelo por grupo n_p",
        "Discos encaixados no mesmo sentido dentro de cada grupo. Cada disco a mais soma força, com "
        "o mesmo curso.",
        1,
        minimo=1,
        maximo=10,
        secao="Pilha",
    ),
    Campo(
        "f_max_N",
        "Força máxima",
        "A maior força sobre a pilha.",
        5000.0,
        "N",
        minimo=0.001,
        passo=100.0,
        secao="Serviço",
    ),
    Campo(
        "limite_MPa",
        "Limite estático de σ_OM",
        "Tensão aceita na parede do disco com carga estática. Catálogos trabalham perto de 1400 a "
        "1600 MPa nos aços de mola: confirme com o fabricante.",
        1400.0,
        "MPa",
        minimo=100.0,
        passo=50.0,
        secao="Serviço",
    ),
    Campo(
        "ciclica",
        "Carga repetida (fadiga)",
        "Ligue se a força varia durante o serviço. Saem as tensões para levar ao diagrama de fadiga "
        "do fabricante.",
        True,
        secao="Serviço",
    ),
    Campo(
        "f_min_N",
        "Força mínima",
        "A menor força do ciclo. O disco precisa ficar sempre um pouco comprimido.",
        1500.0,
        "N",
        minimo=0.0,
        passo=100.0,
        secao="Serviço",
        quando=("ciclica", (True,)),
    ),
)


CASOS: tuple[Caso, ...] = (
    Caso(
        "mola_tracao",
        "Mola de tração",
        GRUPO_MOLAS,
        "Rigidez, tensão inicial, ganchos e fadiga.",
        "Mola helicoidal com gancho nas pontas. A quebra costuma ser no gancho, e por isso ele é "
        "verificado nos dois pontos críticos, além do corpo.",
        CAMPOS_TRACAO,
        calcular_mola_tracao,
        r"k=\frac{G\,d^4}{8D^3N_a},\quad "
        r"\sigma_A=F\left[K_A\frac{16D}{\pi d^3}+\frac{4}{\pi d^2}\right]",
    ),
    Caso(
        "mola_torcao",
        "Mola de torção",
        GRUPO_MOLAS,
        "Rigidez por grau, tensão na fibra, folga no pino e fadiga.",
        "Mola que trabalha girando, como as de tampas e alavancas de retorno. Sai o giro, a tensão "
        "de flexão no fio e quanto a mola fecha sobre o pino.",
        CAMPOS_TORCAO,
        calcular_mola_torcao,
        r"\sigma=K_i\frac{32M}{\pi d^3},\quad k'=\frac{d^4E}{10{,}8\,D\,N_a},\quad "
        r"N_a=N_b+\frac{\ell_1+\ell_2}{3\pi D}",
    ),
    Caso(
        "mola_prato",
        "Mola prato (Belleville)",
        GRUPO_MOLAS,
        "Curva não linear, pilha em série e paralelo, tensões nas bordas.",
        "Disco cônico que dá muita força em pouco espaço. Sai a curva da pilha, a deflexão de "
        "trabalho e as tensões nos pontos que a norma usa.",
        CAMPOS_PRATO,
        calcular_mola_prato,
        r"F=\frac{4E}{1-\mu^2}\frac{t^4}{K_1D_e^2}\frac{s}{t}"
        r"\left[\left(\frac{h_0}{t}-\frac{s}{t}\right)"
        r"\left(\frac{h_0}{t}-\frac{s}{2t}\right)+1\right]",
    ),
)
