"""Molas, embreagens, freios e parafusos de potência."""

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
    recomendacao,
    recomendacao_minima,
)

GRUPO_MOLAS = "Molas"
GRUPO_ATRITO = "Freios, embreagens e fusos"

SHIGLEY_8 = "Shigley, Elementos de Máquinas, cap. 8"
SHIGLEY_10 = "Shigley, Elementos de Máquinas, cap. 10"
SHIGLEY_16 = "Shigley, Elementos de Máquinas, cap. 16"
ZIMMERLI = "Zimmerli, em Shigley, cap. 10"

#: Fio de mola: A (MPa·mm^m), m (Shigley, Tabela 10-4), G (GPa, Tabela 10-5) e S_sy/S_ut
#: (Tabela 10-6, depois do assentamento).
FIOS = {
    "ASTM A228 corda de piano": (2211.0, 0.145, 81.0, 0.45),
    "ASTM A227 trefilado duro": (1783.0, 0.190, 80.0, 0.45),
    "ASTM A229 óleo-temperado": (1855.0, 0.187, 77.2, 0.50),
    "ASTM A232 cromo-vanádio": (2005.0, 0.168, 77.2, 0.50),
    "ASTM A401 cromo-silício": (1974.0, 0.108, 77.2, 0.50),
}
#: Pontas: espiras inativas N_e, soma de espiras no bloco, comprimento livre (p·N_a + c·d).
PONTAS = {
    "Esquadradas e esmerilhadas": (2, 0, 2.0),
    "Esquadradas": (2, 1, 3.0),
    "Simples esmerilhadas": (1, 0, 0.0),
    "Simples": (0, 1, 1.0),
}
APOIOS_MOLA = {
    "Duas pontas guiadas e paralelas": 0.5,
    "Uma ponta paralela e outra articulada": 0.707,
    "Duas pontas articuladas": 1.0,
    "Uma ponta livre": 2.0,
}
SEM_JATEAMENTO = "Sem jateamento"
JATEADA = "Jateada (shot peening)"


def _sut_do_fio(fio: str, d_mm: float) -> float:
    a, m, _g, _fator = FIOS[fio]
    return a / d_mm**m


def limite_de_zimmerli(superficie: str, ssu: float) -> float:
    """S_se de Zimmerli pela reta de Goodman: não depende do material, só do jateamento."""
    ssa, ssm = (241.0, 379.0) if superficie == SEM_JATEAMENTO else (398.0, 534.0)
    return ssa / (1.0 - ssm / ssu)


def calcular_mola(v: Valores) -> Resultado:
    fio = str(v["fio"])
    d = float(v["d_mm"])
    diametro = float(v["D_mm"])
    na = float(v["ativas"])
    f_max = float(v["f_max_N"])
    f_min = float(v["f_min_N"])
    comprimento_livre = float(v["L0_mm"])
    pontas = str(v["pontas"])
    exigir(diametro > d, "O diâmetro médio deve ser maior que o diâmetro do fio.")
    exigir(f_max >= f_min, "A força máxima deve ser maior ou igual à mínima.")

    _a, _m, g_GPa, fator_sy = FIOS[fio]
    g = g_GPa * 1000.0
    sut = _sut_do_fio(fio, d)
    ssy = fator_sy * sut
    ssu = 0.67 * sut
    c = diametro / d
    ks = 1.0 + 0.5 / c
    kb = (4.0 * c + 2.0) / (4.0 * c - 3.0)
    rigidez = g * d**4 / (8.0 * diametro**3 * na)
    inativas, soma_bloco, c_livre = PONTAS[pontas]
    total = na + inativas
    bloco = d * (total + soma_bloco)
    if pontas == "Simples esmerilhadas":
        passo = comprimento_livre / (na + 1.0)
    else:
        passo = (comprimento_livre - c_livre * d) / na
    curso_bloco = comprimento_livre - bloco
    exigir(curso_bloco > 0, "O comprimento livre não passa do comprimento de bloco.")
    forca_bloco = rigidez * curso_bloco
    deflexao_max = f_max / rigidez

    tau_max = ks * 8.0 * f_max * diametro / (math.pi * d**3)
    tau_bloco = ks * 8.0 * forca_bloco * diametro / (math.pi * d**3)
    n_bloco = ssy / tau_bloco
    n_trabalho = ssy / tau_max
    folga = (forca_bloco - f_max) / f_max if f_max > 0 else math.inf

    alfa = APOIOS_MOLA[str(v["apoio"])]
    limite_flambagem = 2.63 * diametro / alfa

    verificacoes = [
        minimo(
            "Tensão com a mola fechada (bloco)",
            n_bloco,
            1.2,
            "—",
            f"n = S_sy/τ_bloco, com S_sy = {ssy:.0f} MPa e τ = {tau_bloco:.0f} MPa",
            SHIGLEY_10,
        ),
        minimo(
            "Tensão na força máxima",
            n_trabalho,
            1.2,
            "—",
            f"τ = K_s·8FD/(π·d³) = {tau_max:.0f} MPa",
            SHIGLEY_10,
        ),
        minimo(
            "Reserva de curso até fechar",
            folga,
            0.15,
            "—",
            "(F_bloco − F_máx)/F_máx ≥ 0,15",
            SHIGLEY_10,
        ),
        faixa_recomendada(
            "Índice de mola C", c, 4.0, 12.0, "—", "C = D/d, faixa usual 4 a 12", SHIGLEY_10
        ),
        faixa_recomendada("Espiras ativas", na, 3.0, 15.0, "—", "faixa usual 3 a 15", SHIGLEY_10),
        limite(
            "Flambagem da mola",
            comprimento_livre,
            limite_flambagem,
            "mm",
            f"L₀ ≤ 2,63·D/α, com α = {alfa:g}",
            SHIGLEY_10,
        ),
    ]

    if bool(v["ciclica"]):
        f_alternada = (f_max - f_min) / 2.0
        f_media = (f_max + f_min) / 2.0
        tau_a = kb * 8.0 * f_alternada * diametro / (math.pi * d**3)
        tau_m = kb * 8.0 * f_media * diametro / (math.pi * d**3)
        sse = limite_de_zimmerli(str(v["superficie"]), ssu)
        n_fadiga = 1.0 / (tau_a / sse + tau_m / ssu) if tau_a + tau_m > 0 else math.inf
        verificacoes.append(
            minimo(
                "Fadiga da mola",
                n_fadiga,
                float(v["n_fadiga"]),
                "—",
                f"Goodman torsional com S_se = {sse:.0f} MPa, τ_a = {tau_a:.0f} e τ_m = {tau_m:.0f}",
                ZIMMERLI,
            )
        )

    area = math.pi * d**2 / 4.0
    comprimento_fio = math.pi * diametro * total
    massa = area * comprimento_fio * 7.85e-6
    massa_ativa = area * math.pi * diametro * na * 7.85e-6
    # k em N/m e massa em kg: f = ½·√(k/m) entre dois apoios.
    frequencia = 0.5 * math.sqrt(rigidez * 1000.0 / massa_ativa)
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
    return Resultado(
        resumo=(
            f"k = {rigidez:.1f} N/mm: com {f_max:.0f} N a mola encurta {deflexao_max:.1f} mm e "
            f"fica a {tau_max:.0f} MPa."
        ),
        metricas=(
            Metrica("Rigidez k", rigidez, "N/mm", 2),
            Metrica("Deflexão na força máxima", deflexao_max, "mm", 1),
            Metrica("Tensão na força máxima", tau_max, "MPa", 0),
            Metrica("Comprimento de bloco", bloco, "mm", 1),
            Metrica("Passo", passo, "mm", 2),
            Metrica("Força para fechar", forca_bloco, "N", 0),
            Metrica("Resistência S_ut do fio", sut, "MPa", 0),
            Metrica("Frequência própria", frequencia, "Hz", 0),
            Metrica("Massa", massa, "kg", 3),
            Metrica("Índice C", c, "", 2),
        ),
        verificacoes=tuple(verificacoes),
        pontos=(Ponto("Fio, fibra interna, força máxima", 0.0, 0.0, tau_max),),
        hipoteses=(
            "Mola helicoidal de compressão, de fio redondo, com espiras de passo pequeno.",
            "Limite estático S_sy com assentamento, pela Tabela 10-6 de Shigley.",
            "Fadiga por Zimmerli: vale para fios abaixo de 10 mm e não depende do material.",
            "Limite de flambagem para mola de aço, em que o resultado não depende da deflexão.",
        ),
        referencias=(SHIGLEY_10,),
    )


CAMPOS_MOLA = (
    Campo(
        "fio",
        "Material do fio",
        "Corda de piano é a mais resistente nos diâmetros pequenos. Cromo-silício serve para "
        "choque e temperatura mais alta.",
        "ASTM A229 óleo-temperado",
        opcoes=tuple(FIOS),
        secao="Mola",
    ),
    Campo(
        "d_mm",
        "Diâmetro do fio d",
        "Diâmetro do fio. Quanto mais fino, maior a resistência do material, mas menor a força.",
        12.0,
        "mm",
        minimo=0.1,
        passo=0.5,
        secao="Mola",
    ),
    Campo(
        "D_mm",
        "Diâmetro médio D",
        "Diâmetro da espira, medido no centro do fio.",
        72.0,
        "mm",
        minimo=0.5,
        passo=1.0,
        secao="Mola",
    ),
    Campo(
        "ativas",
        "Espiras ativas N_a",
        "Espiras que deformam de verdade. As das pontas ficam encostadas e não contam.",
        6.0,
        minimo=1.0,
        maximo=100.0,
        passo=0.5,
        secao="Mola",
    ),
    Campo(
        "L0_mm",
        "Comprimento livre L₀",
        "Comprimento da mola sem carga.",
        142.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Mola",
    ),
    Campo(
        "pontas",
        "Tipo de ponta",
        "Esquadrada e esmerilhada apoia melhor e é a mais usada em máquinas.",
        "Esquadradas e esmerilhadas",
        opcoes=tuple(PONTAS),
        secao="Mola",
    ),
    Campo(
        "apoio",
        "Apoio das pontas",
        "Define o risco de flambagem. Uma mola longa que comprime sem guia pode dobrar de lado.",
        "Duas pontas guiadas e paralelas",
        opcoes=tuple(APOIOS_MOLA),
        secao="Mola",
    ),
    Campo(
        "f_max_N",
        "Força máxima",
        "A maior força de trabalho.",
        3500.0,
        "N",
        minimo=0.001,
        passo=50.0,
        secao="Serviço",
    ),
    Campo(
        "ciclica",
        "Carga repetida (fadiga)",
        "Ligue se a força varia durante o serviço, como em peneiras e válvulas.",
        True,
        secao="Serviço",
    ),
    Campo(
        "f_min_N",
        "Força mínima",
        "A menor força do ciclo. Molas costumam trabalhar sempre com alguma pré-carga.",
        1500.0,
        "N",
        minimo=0.0,
        passo=50.0,
        secao="Serviço",
        quando=("ciclica", (True,)),
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
# Embreagem ou freio de disco
# ---------------------------------------------------------------------------

DESGASTE_UNIFORME = "Desgaste uniforme (já assentada)"
PRESSAO_UNIFORME = "Pressão uniforme (nova)"


def calcular_disco(v: Valores) -> Resultado:
    externo = float(v["D_ext_mm"])
    interno = float(v["D_int_mm"])
    forca = float(v["forca_kN"]) * 1000.0
    atrito = float(v["atrito"])
    pares = int(v["pares"])
    criterio = str(v["criterio"])
    exigir(externo > interno, "O diâmetro externo deve ser maior que o interno.")
    ro = externo / 2.0
    ri = interno / 2.0
    if criterio == DESGASTE_UNIFORME:
        raio_efetivo = (ro + ri) / 2.0
        pressao = forca / (2.0 * math.pi * ri * (ro - ri))
    else:
        raio_efetivo = 2.0 / 3.0 * (ro**3 - ri**3) / (ro**2 - ri**2)
        pressao = forca / (math.pi * (ro**2 - ri**2))
    torque = pares * atrito * forca * raio_efetivo / 1000.0
    exigido = float(v["torque_Nm"]) * float(v["fator_servico"])

    inercia = float(v["inercia_kgm2"])
    rotacao = float(v["rotacao_rpm"])
    omega = 2.0 * math.pi * rotacao / 60.0
    carga = float(v["torque_carga_Nm"])
    frear = str(v["funcao"]) == "Freio"
    # Parar: motor fora e a carga ajuda; partir: a carga atrapalha.
    torque_liquido = torque + carga if frear else torque - carga
    verificacoes = [
        minimo(
            "Torque de atrito",
            torque,
            exigido,
            "N·m",
            f"T = N·μ·F·r_ef, com r_ef = {raio_efetivo:.1f} mm",
            SHIGLEY_16,
        ),
        limite(
            "Pressão no forro",
            pressao,
            float(v["p_adm_MPa"]),
            "MPa",
            "p = F/[2π·r_i·(r_o − r_i)] no desgaste uniforme",
            SHIGLEY_16,
        ),
        faixa_recomendada(
            "Razão de diâmetros d/D",
            interno / externo,
            0.45,
            0.80,
            "—",
            "o maior torque, para a pressão dada, sai em d/D = 0,577",
            SHIGLEY_16,
        ),
    ]
    tempo = None
    energia = 0.0
    if torque_liquido > 0 and inercia > 0:
        tempo = inercia * omega / torque_liquido
        energia = 0.5 * inercia * omega**2 * (torque / torque_liquido)
    elif inercia > 0:
        verificacoes.append(
            minimo("Torque líquido", torque_liquido, 0.001, "N·m", "T − T_carga > 0", SHIGLEY_16)
        )
    massa = float(v["massa_kg"])
    calor = float(v["calor_especifico"])
    aumento = energia / (massa * calor) if massa > 0 else 0.0
    temperatura = float(v["temperatura_max"])
    if temperatura > 0 and energia > 0 and massa > 0:
        verificacoes.append(
            recomendacao(
                "Aquecimento por acionamento",
                aumento,
                temperatura,
                "°C",
                f"ΔT = E/(m·c), com E = {energia / 1000:.1f} kJ",
                SHIGLEY_16,
            )
        )
    metricas = [
        Metrica("Torque de atrito", torque, "N·m", 1),
        Metrica("Torque exigido", exigido, "N·m", 1),
        Metrica("Pressão no forro", pressao, "MPa", 3),
        Metrica("Raio efetivo", raio_efetivo, "mm", 1),
        Metrica("Energia dissipada", energia / 1000.0, "kJ", 2),
        Metrica("Aquecimento", aumento, "°C", 1),
    ]
    if tempo is not None:
        metricas.append(Metrica("Tempo de acionamento", tempo, "s", 2))
    return Resultado(
        resumo=f"Transmite {torque:.0f} N·m com pressão de {pressao:.2f} MPa no forro.",
        metricas=tuple(metricas),
        verificacoes=tuple(verificacoes),
        hipoteses=(
            "Desgaste uniforme é o caso de projeto: dá o menor torque e a maior pressão no raio "
            "interno.",
            "Pressão uniforme vale para o forro novo, antes de assentar.",
            "Toda a energia do acionamento vai para a massa informada, sem perda de calor durante "
            "o escorregamento.",
            "O atrito do forro cai com a temperatura; adote o valor mínimo do fabricante.",
        ),
        referencias=(SHIGLEY_16,),
    )


CAMPOS_DISCO = (
    Campo(
        "funcao",
        "Função",
        "Freio: parar uma massa girando. Embreagem: colocar a massa em movimento.",
        "Freio",
        opcoes=("Freio", "Embreagem"),
        secao="Serviço",
    ),
    Campo(
        "torque_Nm",
        "Torque a transmitir",
        "O torque que a peça precisa segurar ou transmitir.",
        500.0,
        "N·m",
        minimo=0.0,
        passo=10.0,
        secao="Serviço",
    ),
    Campo(
        "fator_servico",
        "Fator de serviço",
        "Multiplica o torque. Freio de elevação: use pelo menos 1,5 sobre o torque da carga.",
        1.5,
        minimo=1.0,
        maximo=4.0,
        passo=0.05,
        secao="Serviço",
    ),
    Campo(
        "D_ext_mm",
        "Diâmetro externo D",
        "Diâmetro externo do forro de atrito.",
        400.0,
        "mm",
        minimo=1.0,
        passo=10.0,
        secao="Disco",
    ),
    Campo(
        "D_int_mm",
        "Diâmetro interno d",
        "Diâmetro interno do forro de atrito.",
        240.0,
        "mm",
        minimo=0.1,
        passo=10.0,
        secao="Disco",
    ),
    Campo(
        "pares",
        "Pares de superfícies N",
        "Quantas faces de atrito trabalham. Disco entre duas faces: 2.",
        2,
        minimo=1,
        maximo=30,
        passo=1,
        secao="Disco",
    ),
    Campo(
        "forca_kN",
        "Força de acionamento F",
        "A força das molas ou do cilindro que aperta o disco.",
        8.0,
        "kN",
        minimo=0.001,
        passo=0.5,
        secao="Disco",
    ),
    Campo(
        "atrito",
        "Coeficiente de atrito μ",
        "Forro orgânico seco com aço: 0,30 a 0,40. Sinterizado: 0,25 a 0,35. Em óleo: cerca de "
        "0,10. Adote o mínimo do fabricante.",
        0.30,
        minimo=0.02,
        maximo=0.8,
        passo=0.01,
        secao="Disco",
    ),
    Campo(
        "p_adm_MPa",
        "Pressão admissível no forro",
        "Limite do fabricante. Forro orgânico seco: cerca de 0,3 a 1 MPa.",
        0.5,
        "MPa",
        minimo=0.01,
        passo=0.05,
        secao="Disco",
    ),
    Campo(
        "criterio",
        "Hipótese de cálculo",
        "Desgaste uniforme é a hipótese de projeto: o forro já assentou e o torque é o menor.",
        DESGASTE_UNIFORME,
        opcoes=(DESGASTE_UNIFORME, PRESSAO_UNIFORME),
        secao="Disco",
    ),
    Campo(
        "inercia_kgm2",
        "Inércia no eixo do disco",
        "Inércia de tudo o que gira, levada ao eixo do disco. Deixe 0 para não calcular a energia.",
        5.0,
        "kg·m²",
        minimo=0.0,
        passo=0.5,
        secao="Energia e calor",
    ),
    Campo(
        "rotacao_rpm",
        "Rotação",
        "A rotação de onde se freia, ou até onde se acelera.",
        1750.0,
        "rpm",
        minimo=0.0,
        passo=10.0,
        secao="Energia e calor",
    ),
    Campo(
        "torque_carga_Nm",
        "Torque da carga no acionamento",
        "Torque da máquina durante o acionamento. Em içamento de descida, entre com ele negativo: "
        "a carga puxa a favor do giro.",
        0.0,
        "N·m",
        passo=10.0,
        secao="Energia e calor",
    ),
    Campo(
        "massa_kg",
        "Massa que recebe o calor",
        "Massa do disco de aço ou ferro que absorve a energia.",
        15.0,
        "kg",
        minimo=0.0,
        passo=1.0,
        secao="Energia e calor",
    ),
    Campo(
        "calor_especifico",
        "Calor específico",
        "Aço e ferro fundido: cerca de 500 J/(kg·°C).",
        500.0,
        "J/(kg·°C)",
        minimo=100.0,
        passo=10.0,
        secao="Energia e calor",
    ),
    Campo(
        "temperatura_max",
        "Aquecimento aceito por acionamento",
        "Quanto o disco pode aquecer por acionamento. Deixe 0 para não comparar.",
        50.0,
        "°C",
        minimo=0.0,
        passo=5.0,
        secao="Energia e calor",
    ),
)


# ---------------------------------------------------------------------------
# Freio de cinta
# ---------------------------------------------------------------------------


def calcular_cinta(v: Valores) -> Resultado:
    torque = float(v["torque_Nm"]) * float(v["fator_servico"])
    diametro = float(v["D_mm"])
    largura = float(v["b_mm"])
    angulo = math.radians(float(v["angulo_graus"]))
    atrito = float(v["atrito"])
    braco_forca = float(v["a_mm"])
    braco_cinta = float(v["c_mm"])
    raio = diametro / 2.0

    razao = math.exp(atrito * angulo)
    forca_util = torque * 1000.0 / raio
    p1 = forca_util * razao / (razao - 1.0)
    p2 = forca_util / (razao - 1.0)
    pressao = p1 / (largura * raio)
    alavanca = p2 * braco_cinta / braco_forca
    torque_inverso = (p2 * razao - p2) * raio / 1000.0 / razao
    sy = float(v["sy_MPa"])
    espessura = float(v["t_mm"])
    tensao = p1 / (largura * espessura)
    verificacoes = (
        limite(
            "Pressão máxima no forro",
            pressao,
            float(v["p_adm_MPa"]),
            "MPa",
            "p_máx = P₁/(b·r), na ponta mais tensa da cinta",
            SHIGLEY_16,
        ),
        limite(
            "Força de acionamento",
            alavanca,
            float(v["forca_max_N"]),
            "N",
            "F = P₂·c/a",
            SHIGLEY_16,
        ),
        limite(
            "Tensão na cinta",
            tensao,
            sy / float(v["fs"]),
            "MPa",
            "σ = P₁/(b·t)",
            "Tração na seção da cinta",
        ),
    )
    return Resultado(
        resumo=(
            f"Tensões de {p1 / 1000:.2f} kN e {p2 / 1000:.2f} kN na cinta, com {alavanca:.0f} N "
            "de acionamento."
        ),
        metricas=(
            Metrica("Ramo tenso P₁", p1 / 1000.0, "kN"),
            Metrica("Ramo frouxo P₂", p2 / 1000.0, "kN"),
            Metrica("Pressão máxima", pressao, "MPa", 3),
            Metrica("Força de acionamento", alavanca, "N", 0),
            Metrica("Torque no giro contrário", torque_inverso, "N·m", 1),
            Metrica("Razão P₁/P₂", razao, "", 2),
        ),
        verificacoes=verificacoes,
        alertas=(
            f"O freio de cinta simples só tem esta capacidade em um sentido. No giro contrário, "
            f"o mesmo acionamento dá {torque_inverso:.0f} N·m. Em tambor que gira nos dois "
            "sentidos, use freio de duas sapatas.",
        ),
        hipoteses=(
            "Cinta flexível, atrito constante e equação de Euler (capstan).",
            "Cinta simples, com a ponta frouxa presa à alavanca e a tensa no ponto fixo.",
        ),
        referencias=(SHIGLEY_16,),
    )


CAMPOS_CINTA = (
    Campo(
        "torque_Nm",
        "Torque de frenagem",
        "O torque que o freio precisa segurar no tambor.",
        1000.0,
        "N·m",
        minimo=0.001,
        passo=50.0,
        secao="Serviço",
    ),
    Campo(
        "fator_servico",
        "Fator de serviço",
        "Multiplica o torque. Freio de elevação: pelo menos 1,5.",
        1.5,
        minimo=1.0,
        maximo=4.0,
        passo=0.05,
        secao="Serviço",
    ),
    Campo(
        "D_mm",
        "Diâmetro do tambor",
        "Diâmetro da superfície de frenagem.",
        500.0,
        "mm",
        minimo=1.0,
        passo=10.0,
        secao="Cinta",
    ),
    Campo(
        "b_mm",
        "Largura da cinta",
        "Largura do forro em contato com o tambor.",
        120.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Cinta",
    ),
    Campo(
        "t_mm",
        "Espessura da cinta de aço",
        "Espessura da cinta metálica, sem contar o forro.",
        4.0,
        "mm",
        minimo=0.1,
        passo=0.5,
        secao="Cinta",
    ),
    Campo(
        "angulo_graus",
        "Ângulo abraçado",
        "Quanto a cinta abraça o tambor. Valor usual: de 240° a 270°.",
        270.0,
        "°",
        minimo=30.0,
        maximo=720.0,
        passo=10.0,
        secao="Cinta",
    ),
    Campo(
        "atrito",
        "Coeficiente de atrito μ",
        "Forro orgânico com ferro fundido ou aço: cerca de 0,30. Adote o mínimo do fabricante.",
        0.30,
        minimo=0.02,
        maximo=0.8,
        passo=0.01,
        secao="Cinta",
    ),
    Campo(
        "p_adm_MPa",
        "Pressão admissível no forro",
        "Limite do fabricante. Forro orgânico: cerca de 0,5 a 1 MPa.",
        0.7,
        "MPa",
        minimo=0.01,
        passo=0.05,
        secao="Limites",
    ),
    Campo(
        "a_mm",
        "Braço da força na alavanca a",
        "Distância do pivô da alavanca até a força de acionamento.",
        800.0,
        "mm",
        minimo=1.0,
        passo=10.0,
        secao="Alavanca",
    ),
    Campo(
        "c_mm",
        "Braço da cinta na alavanca c",
        "Distância do pivô da alavanca até o ponto em que a cinta prende.",
        100.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Alavanca",
    ),
    Campo(
        "forca_max_N",
        "Força máxima do atuador",
        "A força que o atuador ou a mola do freio entrega.",
        1000.0,
        "N",
        minimo=1.0,
        passo=50.0,
        secao="Alavanca",
    ),
    Campo(
        "sy_MPa",
        "Escoamento da cinta",
        "Limite de escoamento do aço da cinta.",
        350.0,
        "MPa",
        minimo=10.0,
        passo=10.0,
        secao="Limites",
    ),
    Campo(
        "fs",
        "Fator de segurança",
        "Margem sobre o escoamento da cinta. Comece com 2,0.",
        2.0,
        minimo=1.0,
        maximo=6.0,
        passo=0.1,
        secao="Limites",
    ),
)


# ---------------------------------------------------------------------------
# Parafuso de potência
# ---------------------------------------------------------------------------

ROSCA_TRAPEZOIDAL = "Trapezoidal ISO (30°)"
ROSCA_ACME = "ACME (29°)"
ROSCA_QUADRADA = "Quadrada"
ROSCAS = {ROSCA_TRAPEZOIDAL: 15.0, ROSCA_ACME: 14.5, ROSCA_QUADRADA: 0.0}


def torques_do_fuso(
    forca: float, d_medio: float, avanco: float, atrito: float, alfa_graus: float
) -> tuple[float, float]:
    """Torque para subir e para descer na rosca, em N·mm (Shigley, eq. 8-5 e 8-6)."""
    sec = 1.0 / math.cos(math.radians(alfa_graus))
    denominador_sub = math.pi * d_medio - atrito * avanco * sec
    exigir(denominador_sub > 0, "Com este atrito e este passo, o fuso trava ao subir.")
    subir = forca * d_medio / 2.0 * (avanco + math.pi * atrito * d_medio * sec) / denominador_sub
    descer = (
        forca
        * d_medio
        / 2.0
        * (math.pi * atrito * d_medio * sec - avanco)
        / (math.pi * d_medio + atrito * avanco * sec)
    )
    return subir, descer


def tensao_critica_coluna(indice: float, sy: float, modulo: float) -> float:
    """S_cr por Johnson ou Euler, conforme a esbeltez."""
    transicao = math.pi * math.sqrt(2.0 * modulo / sy)
    if indice <= 0:
        return sy
    if indice >= transicao:
        return math.pi**2 * modulo / indice**2
    return sy * (1.0 - sy * indice**2 / (4.0 * math.pi**2 * modulo))


def calcular_fuso(v: Valores) -> Resultado:
    forca = float(v["forca_kN"]) * 1000.0
    d = float(v["d_mm"])
    passo = float(v["passo_mm"])
    entradas = int(v["entradas"])
    atrito = float(v["atrito"])
    atrito_c = float(v["atrito_colar"])
    d_colar = float(v["d_colar_mm"])
    filetes = float(v["filetes"])
    sy = float(v["sy_MPa"])
    sy_porca = float(v["sy_porca_MPa"])
    fs = float(v["fs"])
    rosca = str(v["rosca"])
    alfa = ROSCAS[rosca]
    exigir(passo < d, "O passo deve ser menor que o diâmetro.")

    d_m = d - passo / 2.0
    d_r = d - passo
    avanco = entradas * passo
    subir, descer = torques_do_fuso(forca, d_m, avanco, atrito, alfa)
    colar = forca * atrito_c * d_colar / 2.0
    torque_sobe = subir + colar
    torque_desce = descer + colar
    rendimento = forca * avanco / (2.0 * math.pi * torque_sobe)
    autotravante = descer > 0

    tau = 16.0 * torque_sobe / (math.pi * d_r**3)
    sigma = -4.0 * forca / (math.pi * d_r**2)
    corpo = Ponto("Corpo do fuso", sigma, 0.0, tau)

    h = passo / 2.0
    pressao = forca / (math.pi * d_m * filetes * h)
    # Shigley: o primeiro filete engajado leva cerca de 38 % da carga.
    carga_filete = 0.38 * forca
    flexao_filete = 6.0 * carga_filete / (math.pi * d_r * passo)
    corte_filete = 3.0 * forca / (2.0 * math.pi * d_r * filetes * passo)
    corte_porca = 3.0 * forca / (2.0 * math.pi * d * filetes * passo)

    verificacoes = [
        limite(
            "von Mises no corpo",
            corpo.von_mises,
            sy / fs,
            "MPa",
            f"σ = 4F/(π·d_r²) e τ = 16T/(π·d_r³), com d_r = {d_r:.2f} mm",
            SHIGLEY_8,
        ),
        limite(
            "Pressão nos filetes",
            pressao,
            float(v["p_adm_MPa"]),
            "MPa",
            "p = F/(π·d_m·n·h)",
            f"{SHIGLEY_8} (Tabela 8-4)",
        ),
        limite(
            "Flexão no filete do fuso",
            flexao_filete,
            sy / fs,
            "MPa",
            "σ_b = 6(0,38F)/(π·d_r·p): o primeiro filete leva 38 % da carga",
            SHIGLEY_8,
        ),
        limite(
            "Corte nos filetes do fuso",
            corte_filete,
            0.577 * sy / fs,
            "MPa",
            "τ = 3F/(2π·d_r·n·p)",
            SHIGLEY_8,
        ),
        limite(
            "Corte nos filetes da porca",
            corte_porca,
            0.577 * sy_porca / fs,
            "MPa",
            "τ = 3F/(2π·d·n·p)",
            SHIGLEY_8,
        ),
    ]
    comprimento = float(v["comprimento_mm"])
    if comprimento > 0:
        raio_giro = d_r / 4.0
        indice = float(v["k"]) * comprimento / raio_giro
        modulo = float(v["e_GPa"]) * 1000.0
        critica = tensao_critica_coluna(indice, sy, modulo) * math.pi * d_r**2 / 4.0
        verificacoes.append(
            minimo(
                "Flambagem do fuso",
                critica / forca,
                float(v["fs_flambagem"]),
                "—",
                f"P_cr/F, com KL/r = {indice:.0f} (Johnson ou Euler)",
                SHIGLEY_8,
            )
        )
    verificacoes.append(
        informativo("Rendimento", rendimento * 100.0, "%", "e = F·ℓ/(2π·T)", SHIGLEY_8)
    )
    alertas = []
    if autotravante:
        alertas.append(
            "O fuso é autotravante pela conta, mas vibração reduz o atrito. Em levantamento de "
            "pessoas ou de carga sobre pessoas, não dispense a trava ou o freio."
        )
    elif torque_desce > 0:
        alertas.append(
            "A rosca sozinha NÃO é autotravante: só o atrito do colar está segurando a carga. Com "
            "vibração ou lubrificação no colar, o fuso desce. É preciso freio ou trava."
        )
    else:
        alertas.append(
            "O fuso NÃO é autotravante: sob carga, ele desce sozinho. É preciso freio ou trava."
        )
    rotacao = float(v["rotacao_rpm"])
    potencia = torque_sobe / 1000.0 * 2.0 * math.pi * rotacao / 60_000.0
    return Resultado(
        resumo=(
            f"Para subir: {torque_sobe / 1000:.1f} N·m, rendimento de {rendimento * 100:.0f} %. "
            + ("O fuso trava sozinho." if autotravante else "O fuso não trava sozinho.")
        ),
        metricas=(
            Metrica("Torque para subir", torque_sobe / 1000.0, "N·m", 1),
            Metrica("Torque para descer", torque_desce / 1000.0, "N·m", 1),
            Metrica("Rendimento", rendimento * 100.0, "%", 1),
            Metrica("Avanço por volta", avanco, "mm", 1),
            Metrica("Velocidade", avanco * rotacao / 60.0, "mm/s", 1),
            Metrica("Potência", potencia, "kW", 2),
            Metrica("Pressão nos filetes", pressao, "MPa", 1),
        ),
        verificacoes=tuple(verificacoes),
        pontos=(corpo,),
        alertas=tuple(alertas),
        hipoteses=(
            "Diâmetro médio d − p/2 e diâmetro da raiz d − p: valores aproximados das roscas "
            "trapezoidais. Em rosca normalizada, use a tabela para a verificação final.",
            "Altura de contato do filete igual a p/2.",
            "Sem carga lateral no fuso: a guia deve absorver o momento.",
            "A torção do corpo usa o torque com o colar, o caso mais carregado do trecho.",
        ),
        referencias=(SHIGLEY_8,),
    )


CAMPOS_FUSO = (
    Campo(
        "forca_kN",
        "Força axial F",
        "A carga que o fuso sobe ou empurra.",
        20.0,
        "kN",
        minimo=0.001,
        passo=1.0,
        secao="Carga",
    ),
    Campo(
        "rotacao_rpm",
        "Rotação",
        "Rotação do fuso ou da porca.",
        60.0,
        "rpm",
        minimo=0.0,
        passo=5.0,
        secao="Carga",
    ),
    Campo(
        "rosca",
        "Tipo de rosca",
        "Trapezoidal é o padrão métrico. Quadrada rende mais, mas é difícil de fabricar e não "
        "compensa o desgaste.",
        ROSCA_TRAPEZOIDAL,
        opcoes=tuple(ROSCAS),
        secao="Rosca",
    ),
    Campo(
        "d_mm",
        "Diâmetro nominal d",
        "Diâmetro externo do fuso.",
        40.0,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Rosca",
    ),
    Campo(
        "passo_mm",
        "Passo p",
        "Distância entre filetes vizinhos.",
        7.0,
        "mm",
        minimo=0.1,
        passo=0.5,
        secao="Rosca",
    ),
    Campo(
        "entradas",
        "Número de entradas",
        "Com mais entradas, o fuso anda mais por volta, mas deixa de travar sozinho.",
        1,
        minimo=1,
        maximo=6,
        passo=1,
        secao="Rosca",
    ),
    Campo(
        "filetes",
        "Filetes engajados na porca n",
        "Comprimento da porca dividido pelo passo.",
        8.0,
        minimo=1.0,
        passo=1.0,
        secao="Rosca",
    ),
    Campo(
        "atrito",
        "Atrito na rosca f",
        "Aço com bronze lubrificado: de 0,10 a 0,15. Aço com aço: de 0,15 a 0,20.",
        0.15,
        minimo=0.01,
        maximo=0.5,
        passo=0.01,
        secao="Atrito",
    ),
    Campo(
        "atrito_colar",
        "Atrito no colar",
        "Atrito no apoio axial. Com rolamento axial: cerca de 0,01. Com colar deslizante: 0,10 a "
        "0,15.",
        0.01,
        minimo=0.0,
        maximo=0.5,
        passo=0.01,
        secao="Atrito",
    ),
    Campo(
        "d_colar_mm",
        "Diâmetro médio do colar",
        "Diâmetro médio do apoio axial.",
        60.0,
        "mm",
        minimo=0.0,
        passo=5.0,
        secao="Atrito",
    ),
    Campo(
        "sy_MPa",
        "Escoamento do fuso",
        "Limite de escoamento do aço do fuso.",
        420.0,
        "MPa",
        minimo=10.0,
        passo=10.0,
        secao="Materiais",
    ),
    Campo(
        "sy_porca_MPa",
        "Escoamento da porca",
        "Limite de escoamento da porca. Bronze: de 150 a 300 MPa.",
        200.0,
        "MPa",
        minimo=10.0,
        passo=10.0,
        secao="Materiais",
    ),
    Campo(
        "p_adm_MPa",
        "Pressão admissível nos filetes",
        "Aço com bronze: de 11 a 17 MPa até 3 m/min na rosca, e menos em velocidade maior.",
        11.0,
        "MPa",
        minimo=0.1,
        passo=1.0,
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
    Campo(
        "comprimento_mm",
        "Comprimento livre comprimido",
        "Maior comprimento do fuso sob compressão. Deixe 0 se ele trabalhar só à tração.",
        800.0,
        "mm",
        minimo=0.0,
        passo=50.0,
        secao="Flambagem",
    ),
    Campo(
        "k",
        "Fator de comprimento K",
        "Duas pontas guiadas: 1,0. Uma engastada e outra guiada: 0,7. Em balanço: 2,0.",
        1.0,
        minimo=0.5,
        maximo=2.5,
        passo=0.1,
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
        secao="Flambagem",
    ),
    Campo(
        "fs_flambagem",
        "Fator mínimo à flambagem",
        "Margem sobre a carga crítica. Comece com 3.",
        3.0,
        minimo=1.0,
        maximo=8.0,
        passo=0.5,
        secao="Flambagem",
    ),
)


CASOS: tuple[Caso, ...] = (
    Caso(
        "mola_compressao",
        "Mola de compressão",
        GRUPO_MOLAS,
        "Rigidez, tensões, bloco, flambagem, fadiga e frequência própria.",
        "Projeto completo de mola helicoidal de compressão: resistência do fio pelo diâmetro, "
        "comprimento de bloco, flambagem e fadiga pelo critério de Zimmerli.",
        CAMPOS_MOLA,
        calcular_mola,
        r"k=\frac{G\,d^4}{8D^3N_a},\quad \tau=K_s\frac{8FD}{\pi d^3},\quad "
        r"L_0\le\frac{2{,}63D}{\alpha}",
    ),
    Caso(
        "embreagem_disco",
        "Freio ou embreagem de disco",
        GRUPO_ATRITO,
        "Torque, pressão no forro, tempo de acionamento, energia e aquecimento.",
        "Sai o torque de atrito, a pressão no forro e, com a inércia da máquina, o tempo de "
        "parada, a energia dissipada e o aquecimento do disco.",
        CAMPOS_DISCO,
        calcular_disco,
        r"T=N\,\mu\,F\,\frac{r_o+r_i}{2},\qquad p_{max}=\frac{F}{2\pi r_i(r_o-r_i)}",
    ),
    Caso(
        "freio_cinta",
        "Freio de cinta",
        GRUPO_ATRITO,
        "Tensões na cinta, pressão no forro e força na alavanca.",
        "Freio de cinta simples. Mostra também como a capacidade cai no giro contrário, um risco "
        "que passa despercebido.",
        CAMPOS_CINTA,
        calcular_cinta,
        r"\frac{P_1}{P_2}=e^{\mu\theta},\quad T=(P_1-P_2)r,\quad p_{max}=\frac{P_1}{b\,r}",
    ),
    Caso(
        "parafuso_potencia",
        "Parafuso de potência (fuso)",
        GRUPO_ATRITO,
        "Torque, rendimento, autotravamento, tensões nos filetes e flambagem.",
        "Fuso de rosca trapezoidal ou quadrada de macaco, prensa ou atuador. Sai o torque para "
        "subir e descer, se o fuso trava sozinho e as tensões no corpo e nos filetes.",
        CAMPOS_FUSO,
        calcular_fuso,
        r"T=\frac{Fd_m}{2}\,\frac{\ell+\pi f d_m\sec\alpha}{\pi d_m-f\ell\sec\alpha}"
        r"+\frac{F f_c d_c}{2}",
    ),
)
