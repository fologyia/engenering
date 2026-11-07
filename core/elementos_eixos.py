"""Eixos e o que os liga às peças: seção crítica, eixo inteiro, chaveta e ajuste prensado.

- ``eixo_secao``: fadiga e escoamento numa seção, com K_t, K_f e os fatores de Marin de
  :mod:`core.fatigue`. Critérios DE-Goodman, DE-Gerber, DE-ASME elíptico e DE-Soderberg.
- ``eixo_transmissao``: eixo de diâmetro constante sobre dois mancais, em dois planos: reações,
  diagramas, flecha, inclinação nos mancais, torção e primeira rotação crítica (Rayleigh).
- ``chaveta``: DIN 6885, corte e esmagamento.
- ``ajuste_prensado``: Lamé com a interferência dos ajustes da NBR 6158.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass

from core import fatigue as ft
from core.elementos_base import (
    Campo,
    Caso,
    Envio,
    Grafico,
    Metrica,
    Ponto,
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

GRUPO = "Eixos e cubos"

SHIGLEY_6 = "Shigley, Elementos de Máquinas, cap. 6"
SHIGLEY_7 = "Shigley, Elementos de Máquinas, cap. 7"
NORTON_E = "Norton, Projeto de Máquinas, apêndice E (curvas de Peterson)"
NBR_6158 = "ABNT NBR 6158:1995, tabelas 1 e 2"
DIN_6885 = "DIN 6885-1 (dimensões da chaveta paralela)"
DIN_6892 = "DIN 6892 (cálculo da ligação por chaveta)"
DIN_7190 = "DIN 7190 (ajuste prensado: alisamento da rugosidade)"

# K_t = A·(r/d)^b em ressalto de eixo, com os ajustes das curvas de Peterson dados por Norton.
# As duas colunas seguintes dão A e b; a primeira é D/d.
_RESSALTO_FLEXAO = (
    (1.01, 0.91938, -0.17032),
    (1.02, 0.96048, -0.17711),
    (1.03, 0.98061, -0.18381),
    (1.05, 0.98137, -0.19653),
    (1.07, 0.97527, -0.20958),
    (1.10, 0.95120, -0.23757),
    (1.20, 0.97098, -0.21796),
    (1.50, 0.93836, -0.25759),
    (2.00, 0.90879, -0.28598),
    (3.00, 0.89334, -0.30860),
    (6.00, 0.87868, -0.33243),
)
_RESSALTO_AXIAL = (
    (1.01, 0.98413, -0.10474),
    (1.02, 1.01220, -0.12474),
    (1.05, 1.00480, -0.17076),
    (1.07, 0.98498, -0.19548),
    (1.10, 0.98450, -0.20818),
    (1.15, 0.98084, -0.22485),
    (1.20, 0.96272, -0.25527),
    (1.30, 0.99682, -0.25751),
    (1.50, 0.99957, -0.28221),
    (2.00, 1.01470, -0.30035),
)
_RESSALTO_TORCAO = (
    (1.09, 0.90337, -0.12692),
    (1.20, 0.83425, -0.21649),
    (1.33, 0.84897, -0.23161),
    (2.00, 0.86331, -0.23865),
)
_TABELAS_RESSALTO = {
    "flexao": _RESSALTO_FLEXAO,
    "axial": _RESSALTO_AXIAL,
    "torcao": _RESSALTO_TORCAO,
}

ENTALHE_RESSALTO = "Ressalto com raio de concordância"
ENTALHE_CHAVETA = "Rasgo de chaveta (fresa de topo)"
ENTALHE_ANEL = "Canal de anel de retenção"
ENTALHE_FURO = "Furo transversal pequeno"
ENTALHE_PRENSADO = "Cubo prensado no eixo"
ENTALHE_LISO = "Eixo liso"
ENTALHE_MANUAL = "Informar K_t e K_ts"
ENTALHES = (
    ENTALHE_RESSALTO,
    ENTALHE_CHAVETA,
    ENTALHE_ANEL,
    ENTALHE_FURO,
    ENTALHE_PRENSADO,
    ENTALHE_LISO,
    ENTALHE_MANUAL,
)

#: K_t em flexão, K_ts em torção e K_t axial dos entalhes que não dependem de D/d.
KT_FIXOS = {
    ENTALHE_CHAVETA: (2.14, 3.0, 2.14),
    ENTALHE_ANEL: (5.0, 3.0, 5.0),
    ENTALHE_FURO: (3.0, 4.0, 3.0),
    ENTALHE_PRENSADO: (2.0, 1.7, 2.0),
    ENTALHE_LISO: (1.0, 1.0, 1.0),
}

ACABAMENTOS = {
    "Usinado ou estirado a frio": "usinado_ou_estirado_a_frio",
    "Retificado": "retificado",
    "Laminado a quente": "laminado_a_quente",
    "Forjado": "forjado",
}
CONFIABILIDADES = {"50 %": 50, "90 %": 90, "95 %": 95, "99 %": 99, "99,9 %": 99.9}

#: Limites de inclinação nos mancais, em rad (Shigley, Tabela 7-2).
INCLINACAO_MANCAL = {
    "Esferas de sulco profundo": 0.001,
    "Rolos cilíndricos": 0.0008,
    "Rolos cônicos": 0.0005,
    "Esferas autocompensadoras": 0.026,
    "Rolos autocompensadores": 0.026,
}


def _kt_na_tabela(tabela: tuple[tuple[float, float, float], ...], D_d: float, r_d: float) -> float:
    """K_t = A·(r/d)^b, interpolado linearmente em D/d entre as curvas da tabela."""
    relacoes = [linha[0] for linha in tabela]
    if D_d <= relacoes[0]:
        linha = tabela[0]
        return linha[1] * r_d ** linha[2]
    if D_d >= relacoes[-1]:
        linha = tabela[-1]
        return linha[1] * r_d ** linha[2]
    i = bisect.bisect_right(relacoes, D_d) - 1
    r1, a1, b1 = tabela[i]
    r2, a2, b2 = tabela[i + 1]
    k1 = a1 * r_d**b1
    k2 = a2 * r_d**b2
    return k1 + (k2 - k1) * (D_d - r1) / (r2 - r1)


def kt_ressalto(D: float, d: float, r: float, carga: str) -> float:
    """K_t de ressalto em eixo redondo; ``carga`` é "flexao", "axial" ou "torcao"."""
    exigir(D > d, "O diâmetro maior D deve ser maior que o diâmetro d.")
    exigir(r > 0, "O raio de concordância deve ser maior que zero.")
    return max(1.0, _kt_na_tabela(_TABELAS_RESSALTO[carga], D / d, r / d))


def raiz_neuber(Sut_MPa: float, carga: str) -> float:
    """√a de Neuber em √pol (Shigley, eq. 6-35), com S_ut limitado à faixa do ajuste."""
    sut = min(max(Sut_MPa / 6.895, 50.0), 250.0)
    if carga == "torcao":
        return 0.190 - 2.51e-3 * sut + 1.35e-5 * sut**2 - 2.67e-8 * sut**3
    return 0.246 - 3.08e-3 * sut + 1.51e-5 * sut**2 - 2.67e-8 * sut**3


def sensibilidade(Sut_MPa: float, raio_mm: float, carga: str) -> float:
    """q de Neuber (Shigley, eq. 6-34), com o raio em mm."""
    return 1.0 / (1.0 + raiz_neuber(Sut_MPa, carga) / math.sqrt(raio_mm / 25.4))


def limite_de_fadiga(
    Sut_MPa: float, d_mm: float, acabamento: str, confiabilidade: float, temperatura_C: float
) -> tuple[float, dict[str, float]]:
    """S_e do eixo, com os fatores de Marin em flexão de :mod:`core.fatigue`, modelo Shigley."""
    se_linha, _ = ft.se_linha(Sut_MPa, "aco")
    ka = ft.fator_superficie(Sut_MPa, acabamento)
    kb = ft.fator_tamanho(min(d_mm, 254.0), "flexao", "shigley") if d_mm >= 2.79 else 1.0
    kd = ft.fator_temperatura(max(temperatura_C, 20.0), "shigley")
    ke = ft.fator_confiabilidade(confiabilidade)
    fatores = {"S'e": se_linha, "k_a": ka, "k_b": kb, "k_d": kd, "k_e": ke}
    return se_linha * ka * kb * kd * ke, fatores


def _criterios_de_fadiga(
    sa: float, sm: float, se: float, sut: float, sy: float
) -> dict[str, float]:
    """Fator de segurança à fadiga de cada critério. Tudo em MPa; σ'a e σ'm não negativos."""
    if sa <= 0 and sm <= 0:
        return {
            nome: math.inf
            for nome in ("DE-Goodman", "DE-Gerber", "DE-ASME elíptico", "DE-Soderberg")
        }
    goodman = 1.0 / (sa / se + sm / sut)
    soderberg = 1.0 / (sa / se + sm / sy)
    eliptico = 1.0 / math.hypot(sa / se, sm / sy)
    if sm <= 0:
        gerber = se / sa
    elif sa <= 0:
        gerber = sut / sm
    else:
        gerber = (
            0.5
            * (sut / sm) ** 2
            * (sa / se)
            * (-1.0 + math.sqrt(1.0 + (2.0 * sm * se / (sut * sa)) ** 2))
        )
    return {
        "DE-Goodman": goodman,
        "DE-Gerber": gerber,
        "DE-ASME elíptico": eliptico,
        "DE-Soderberg": soderberg,
    }


def diametro_goodman(
    n: float,
    A_Nmm: float,
    B_Nmm: float,
    sut: float,
    acabamento: str,
    confiabilidade: float,
    temperatura_C: float,
) -> float:
    """Diâmetro que dá o fator n por DE-Goodman; S_e depende do diâmetro, então itera.

    ``A`` e ``B`` são as raízes da eq. 7-8 de Shigley: √[4(K_f·M_a)² + 3(K_fs·T_a)²] e o mesmo com
    os valores médios, em N·mm.
    """
    d = 50.0
    for _ in range(40):
        se, _fatores = limite_de_fadiga(sut, d, acabamento, confiabilidade, temperatura_C)
        novo = (16.0 * n / math.pi * (A_Nmm / se + B_Nmm / sut)) ** (1.0 / 3.0)
        if abs(novo - d) < 1e-6:
            return novo
        d = novo
    return d


def calcular_eixo_secao(v: Valores) -> Resultado:
    d = float(v["d_mm"])
    D = float(v["D_mm"])
    r = float(v["r_mm"])
    tipo = str(v["entalhe"])
    sut = float(v["sut_MPa"])
    sy = float(v["sy_MPa"])
    ma = float(v["ma_Nm"]) * 1000.0
    mm = float(v["mm_Nm"]) * 1000.0
    ta = float(v["ta_Nm"]) * 1000.0
    tm = float(v["tm_Nm"]) * 1000.0
    axial = float(v["axial_kN"]) * 1000.0
    n_min = float(v["n_fadiga"])
    n_esc_min = float(v["n_escoamento"])
    acabamento = ACABAMENTOS[str(v["acabamento"])]
    confiabilidade = CONFIABILIDADES[str(v["confiabilidade"])]
    temperatura = float(v["temperatura_C"])
    exigir(sy <= sut, "S_y não pode ser maior que S_ut.")

    alertas: list[str] = []
    if tipo == ENTALHE_RESSALTO:
        kt = kt_ressalto(D, d, r, "flexao")
        kts = kt_ressalto(D, d, r, "torcao")
        kta = kt_ressalto(D, d, r, "axial")
        if not 0.01 <= r / d <= 0.30:
            alertas.append(
                f"r/d = {r / d:.3f} está fora da faixa usual das curvas de Peterson (0,01 a 0,30)."
            )
        if r / d < 0.02:
            alertas.append(
                "Raio muito pequeno para a concordância: K_t cresce depressa. Use r/d ≥ 0,02 ou "
                "um rebaixo de alívio."
            )
    elif tipo == ENTALHE_MANUAL:
        kt = float(v["kt"])
        kts = float(v["kts"])
        kta = kt
    else:
        kt, kts, kta = KT_FIXOS[tipo]

    if tipo == ENTALHE_FURO:
        alertas.append(
            "K_t = 3 e K_ts = 4 são o limite teórico de um furo pequeno, sem contar o diâmetro do "
            "furo. Se tiver a curva de Peterson do caso, use Informar K_t e K_ts."
        )
    elif tipo == ENTALHE_PRENSADO:
        alertas.append(
            "K_t = 2,0 e K_ts = 1,7 são estimativas de ordem de grandeza para a borda do cubo. O "
            "valor real depende do alívio do cubo e da pressão: se tiver dado melhor, use Informar "
            "K_t e K_ts."
        )

    if tipo == ENTALHE_ANEL:
        # O fundo do canal é vivo demais para confiar em q: Shigley adota K_f = K_t.
        q = qs = 1.0
    elif tipo == ENTALHE_CHAVETA:
        raio = 0.02 * d
        q = sensibilidade(sut, raio, "flexao")
        qs = sensibilidade(sut, raio, "torcao")
    elif tipo in (ENTALHE_FURO, ENTALHE_PRENSADO, ENTALHE_MANUAL):
        q = qs = 1.0  # lado seguro: sem raio definido, não há como usar a sensibilidade
    elif tipo == ENTALHE_LISO:
        q = qs = 0.0
    else:
        q = sensibilidade(sut, r, "flexao")
        qs = sensibilidade(sut, r, "torcao")
    kf = 1.0 + q * (kt - 1.0)
    kfs = 1.0 + qs * (kts - 1.0)
    kfa = 1.0 + q * (kta - 1.0)

    se, marin = limite_de_fadiga(sut, d, acabamento, confiabilidade, temperatura)
    if d > 254.0:
        alertas.append("Acima de 254 mm o fator de tamanho é extrapolado: use o valor com cautela.")
    if sut > 1400.0:
        alertas.append("Acima de 1400 MPa o limite de fadiga de referência fica em 700 MPa.")

    z = math.pi * d**3
    area = math.pi * d**2 / 4.0
    sigma_ma = 32.0 * ma / z
    sigma_mm = 32.0 * mm / z
    tau_a = 16.0 * ta / z
    tau_m = 16.0 * tm / z
    sigma_axial = axial / area

    # A parcela axial é média: um eixo girando não alterna a força axial. Em compressão ela não
    # fecha trinca, mas o sinal fica de fora do critério: entra o módulo, do lado seguro.
    sa = math.sqrt((kf * sigma_ma) ** 2 + 3.0 * (kfs * tau_a) ** 2)
    sm = math.sqrt((kf * sigma_mm + kfa * abs(sigma_axial)) ** 2 + 3.0 * (kfs * tau_m) ** 2)
    fatores = _criterios_de_fadiga(sa, sm, se, sut, sy)
    sigma_max = math.sqrt(
        (kf * (sigma_ma + sigma_mm) + kfa * abs(sigma_axial)) ** 2
        + 3.0 * (kfs * (tau_a + tau_m)) ** 2
    )
    n_escoamento = sy / sigma_max if sigma_max > 0 else math.inf

    a_raiz = math.sqrt(4.0 * (kf * ma) ** 2 + 3.0 * (kfs * ta) ** 2)
    b_raiz = math.sqrt(4.0 * (kf * mm) ** 2 + 3.0 * (kfs * tm) ** 2)
    d_min = (
        diametro_goodman(n_min, a_raiz, b_raiz, sut, acabamento, confiabilidade, temperatura)
        if a_raiz + b_raiz > 0
        else 0.0
    )

    verificacoes = [
        minimo(
            "Fadiga por DE-Goodman",
            fatores["DE-Goodman"],
            n_min,
            "—",
            f"1/n = σ'a/S_e + σ'm/S_ut, com σ'a = {sa:.1f} e σ'm = {sm:.1f} MPa",
            f"{SHIGLEY_7} (eq. 7-7)",
        ),
        minimo(
            "Escoamento no primeiro ciclo",
            n_escoamento,
            n_esc_min,
            "—",
            f"n = S_y/σ'máx, com σ'máx = {sigma_max:.1f} MPa",
            f"{SHIGLEY_7} (eq. 7-15)",
        ),
    ]
    for nome in ("DE-Gerber", "DE-ASME elíptico", "DE-Soderberg"):
        verificacoes.append(
            informativo(f"Fadiga por {nome}", fatores[nome], "—", "critério comparativo", SHIGLEY_7)
        )

    ponto_nominal = Ponto(
        "Superfície, sem concentração",
        sigma_ma + sigma_mm + sigma_axial,
        0.0,
        tau_a + tau_m,
    )
    ponto_real = Ponto(
        "Superfície, com K_f e K_fs",
        kf * (sigma_ma + sigma_mm) + kfa * sigma_axial,
        0.0,
        kfs * (tau_a + tau_m),
    )
    # A página de fadiga aplica o K_f dela: recebe as tensões nominais equivalentes.
    nominal_alternada = math.sqrt(sigma_ma**2 + 3.0 * tau_a**2)
    nominal_media = math.sqrt((sigma_mm + sigma_axial) ** 2 + 3.0 * tau_m**2)
    return Resultado(
        resumo=(
            f"S_e = {se:.0f} MPa, K_f = {kf:.2f}, K_fs = {kfs:.2f}: fator à fadiga "
            f"{fatores['DE-Goodman']:.2f} (DE-Goodman) e ao escoamento {n_escoamento:.2f}. "
            f"Diâmetro mínimo para n = {n_min:g}: {d_min:.1f} mm."
        ),
        metricas=(
            Metrica("Fadiga, DE-Goodman", fatores["DE-Goodman"], "", 2),
            Metrica("Escoamento", n_escoamento, "", 2),
            Metrica("Diâmetro mínimo", d_min, "mm", 1),
            Metrica("Limite de fadiga S_e", se, "MPa", 1),
            Metrica("K_t / K_f", f"{kt:.2f} / {kf:.2f}"),
            Metrica("K_ts / K_fs", f"{kts:.2f} / {kfs:.2f}"),
            Metrica("σ'a", sa, "MPa", 1),
            Metrica("σ'm", sm, "MPa", 1),
        ),
        verificacoes=tuple(verificacoes),
        pontos=(ponto_nominal, ponto_real),
        tabelas=(
            Tabela(
                "Fatores de Marin",
                (
                    {"Fator": "S'e de referência (MPa)", "Valor": marin["S'e"]},
                    {"Fator": "Superfície k_a", "Valor": marin["k_a"]},
                    {"Fator": "Tamanho k_b", "Valor": marin["k_b"]},
                    {"Fator": "Temperatura k_d", "Valor": marin["k_d"]},
                    {"Fator": "Confiabilidade k_e", "Valor": marin["k_e"]},
                    {"Fator": "Sensibilidade q em flexão", "Valor": q},
                    {"Fator": "Sensibilidade q em torção", "Valor": qs},
                ),
            ),
        ),
        alertas=tuple(alertas),
        hipoteses=(
            "Eixo redondo maciço e flexão e torção em fase: o caso mais desfavorável.",
            "Fator de carregamento k_c = 1, porque os critérios DE já tratam a torção por von Mises.",
            "A força axial entra como tensão média, sem o fator de carga axial.",
            "Eixo girando sob carga constante: M é todo alternado e T é todo médio.",
        ),
        referencias=(SHIGLEY_6, SHIGLEY_7, NORTON_E),
        fadiga=(nominal_alternada, nominal_media),
    )


CAMPOS_EIXO_SECAO = (
    Campo(
        "d_mm",
        "Diâmetro do eixo d",
        "Diâmetro da seção analisada, o menor do ressalto.",
        50.0,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Geometria",
    ),
    Campo(
        "entalhe",
        "Tipo de entalhe",
        "O que há na seção. É o entalhe, e não a tensão nominal, que quebra o eixo. Rolamento "
        "encostado em ressalto, chaveta e canal de anel são as seções a conferir primeiro.",
        ENTALHE_RESSALTO,
        opcoes=ENTALHES,
        secao="Geometria",
    ),
    Campo(
        "D_mm",
        "Diâmetro maior D",
        "O diâmetro do lado maior do ressalto.",
        70.0,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Geometria",
        quando=("entalhe", (ENTALHE_RESSALTO,)),
    ),
    Campo(
        "r_mm",
        "Raio de concordância r",
        "O raio entre os dois diâmetros. Quanto maior, menor a concentração. Em assento de "
        "rolamento o raio é limitado pelo chanfro do anel.",
        3.0,
        "mm",
        minimo=0.01,
        passo=0.5,
        secao="Geometria",
        quando=("entalhe", (ENTALHE_RESSALTO,)),
    ),
    Campo(
        "kt",
        "K_t em flexão",
        "Fator de concentração teórico em flexão, tirado de uma tabela de Peterson ou de uma "
        "análise por elementos finitos.",
        2.0,
        minimo=1.0,
        maximo=10.0,
        passo=0.1,
        secao="Geometria",
        quando=("entalhe", (ENTALHE_MANUAL,)),
    ),
    Campo(
        "kts",
        "K_ts em torção",
        "Fator de concentração teórico em torção, da mesma fonte do K_t.",
        1.7,
        minimo=1.0,
        maximo=10.0,
        passo=0.1,
        secao="Geometria",
        quando=("entalhe", (ENTALHE_MANUAL,)),
    ),
    Campo(
        "ma_Nm",
        "Momento fletor alternado M_a",
        "A parte do momento que alterna a cada volta. Num eixo girando sob carga constante, é "
        "o momento inteiro.",
        700.0,
        "N·m",
        minimo=0.0,
        passo=10.0,
        secao="Esforços na seção",
    ),
    Campo(
        "mm_Nm",
        "Momento fletor médio M_m",
        "A parte constante do momento. Num eixo girando sob carga constante, é zero.",
        0.0,
        "N·m",
        minimo=0.0,
        passo=10.0,
        secao="Esforços na seção",
    ),
    Campo(
        "ta_Nm",
        "Torque alternado T_a",
        "A parte do torque que varia. Com torque de regime constante, é zero.",
        0.0,
        "N·m",
        minimo=0.0,
        passo=10.0,
        secao="Esforços na seção",
    ),
    Campo(
        "tm_Nm",
        "Torque médio T_m",
        "O torque de regime transmitido pela seção.",
        800.0,
        "N·m",
        minimo=0.0,
        passo=10.0,
        secao="Esforços na seção",
    ),
    Campo(
        "axial_kN",
        "Força axial",
        "Força ao longo do eixo na seção. Tração positiva e compressão negativa.",
        0.0,
        "kN",
        passo=1.0,
        secao="Esforços na seção",
    ),
    Campo(
        "sut_MPa",
        "Resistência à ruptura S_ut",
        "Limite de resistência do aço do eixo. Escolha o material no alto da página para "
        "preencher sozinho.",
        700.0,
        "MPa",
        minimo=100.0,
        passo=10.0,
        secao="Material",
    ),
    Campo(
        "sy_MPa",
        "Limite de escoamento S_y",
        "Limite de escoamento do aço do eixo.",
        600.0,
        "MPa",
        minimo=50.0,
        passo=10.0,
        secao="Material",
    ),
    Campo(
        "acabamento",
        "Acabamento da superfície",
        "Superfície ruim dá início à trinca. Assento de rolamento: retificado. Corpo do eixo: "
        "usinado.",
        "Usinado ou estirado a frio",
        opcoes=tuple(ACABAMENTOS),
        secao="Material",
    ),
    Campo(
        "confiabilidade",
        "Confiabilidade",
        "A chance de a peça sobreviver. O limite de fadiga publicado é a média (50 %). "
        "Para projeto, use 99 %.",
        "99 %",
        opcoes=tuple(CONFIABILIDADES),
        secao="Material",
    ),
    Campo(
        "temperatura_C",
        "Temperatura de trabalho",
        "Até cerca de 250 °C o efeito no limite de fadiga é pequeno.",
        40.0,
        "°C",
        minimo=-40.0,
        maximo=540.0,
        passo=5.0,
        secao="Material",
    ),
    Campo(
        "n_fadiga",
        "Fator mínimo à fadiga",
        "Fator de segurança exigido contra a fadiga. Comece com 1,5 e suba para 2,0 ou mais "
        "quando as cargas forem pouco conhecidas.",
        1.5,
        minimo=1.0,
        maximo=6.0,
        passo=0.1,
        secao="Exigências",
    ),
    Campo(
        "n_escoamento",
        "Fator mínimo ao escoamento",
        "Fator de segurança exigido contra o escoamento no primeiro ciclo, com o pico de carga.",
        1.5,
        minimo=1.0,
        maximo=6.0,
        passo=0.1,
        secao="Exigências",
    ),
)


# ---------------------------------------------------------------------------
# Eixo inteiro sobre dois mancais
# ---------------------------------------------------------------------------

_ESTACOES = (1, 2, 3, 4)
_GRADE = 400


@dataclass(frozen=True)
class _Estacao:
    """Uma carga no eixo, em N, mm e N·mm."""

    nome: str
    x: float
    fy: float
    fz: float
    fx: float
    raio: float
    torque: float
    massa: float


def _plano(
    xa: float,
    xb: float,
    forcas: list[tuple[float, float]],
    binarios: list[tuple[float, float]],
) -> tuple[float, float]:
    """Reações em A e B de um plano, em N, com forças (x, F) e binários (x, C)."""
    vao = xb - xa
    momento_em_a = sum(f * (x - xa) for x, f in forcas) + sum(c for _, c in binarios)
    rb = -momento_em_a / vao
    ra = -sum(f for _, f in forcas) - rb
    return ra, rb


def _momento(
    x: float,
    apoios: list[tuple[float, float]],
    forcas: list[tuple[float, float]],
    binarios: list[tuple[float, float]],
) -> float:
    """Momento fletor em x pelas cargas à esquerda da seção (o sinal só importa no mesmo plano)."""
    m = sum(f * (x - xf) for xf, f in (*apoios, *forcas) if xf <= x)
    return m + sum(c for xc, c in binarios if xc <= x)


def _elastica(xs: list[float], curvaturas: list[float], xa: float, xb: float) -> list[float]:
    """Flecha por dupla integração de M/EI, com flecha nula nos dois mancais."""
    rotacao = [0.0]
    for i in range(1, len(xs)):
        rotacao.append(
            rotacao[-1] + 0.5 * (curvaturas[i] + curvaturas[i - 1]) * (xs[i] - xs[i - 1])
        )
    flecha = [0.0]
    for i in range(1, len(xs)):
        flecha.append(flecha[-1] + 0.5 * (rotacao[i] + rotacao[i - 1]) * (xs[i] - xs[i - 1]))
    ya = _interpolar(xs, flecha, xa)
    yb = _interpolar(xs, flecha, xb)
    inclinacao = (yb - ya) / (xb - xa)
    return [y - ya - inclinacao * (x - xa) for x, y in zip(xs, flecha, strict=True)]


def _interpolar(xs: list[float], ys: list[float], x: float) -> float:
    i = min(max(bisect.bisect_left(xs, x), 1), len(xs) - 1)
    t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
    return ys[i - 1] + t * (ys[i] - ys[i - 1])


def _derivada(xs: list[float], ys: list[float], x: float) -> float:
    i = min(max(bisect.bisect_left(xs, x), 1), len(xs) - 1)
    return (ys[i] - ys[i - 1]) / (xs[i] - xs[i - 1])


def rotacao_critica_rayleigh(
    xs: list[float], massas: list[float], ei: float, xa: float, xb: float
) -> float:
    """Primeira rotação crítica em rpm por Rayleigh, com ``massas`` (kg) nos pontos da grade."""
    g = 9806.65  # mm/s², para ω²; o peso é em N porque E·I está em N·mm²
    pesos = [m * 9.80665 for m in massas]
    forcas = [(x, -p) for x, p in zip(xs, pesos, strict=True) if p > 0]
    ra, rb = _plano(xa, xb, forcas, [])
    apoios = [(xa, ra), (xb, rb)]
    curvas = [_momento(x, apoios, forcas, []) / ei for x in xs]
    flecha = _elastica(xs, curvas, xa, xb)
    numerador = sum(p * abs(y) for p, y in zip(pesos, flecha, strict=True))
    denominador = sum(p * y**2 for p, y in zip(pesos, flecha, strict=True))
    if denominador <= 0:
        return math.inf
    omega = math.sqrt(g * numerador / denominador)
    return omega * 60.0 / (2.0 * math.pi)


def calcular_eixo_transmissao(v: Valores) -> Resultado:
    xa = float(v["xa_mm"])
    xb = float(v["xb_mm"])
    d = float(v["d_mm"])
    e = float(v["e_GPa"]) * 1000.0
    g_mod = e / (2.0 * (1.0 + float(v["poisson"])))
    rotacao = float(v["rotacao_rpm"])
    densidade = float(v["densidade_kg_m3"]) * 1e-9
    exigir(xb > xa, "O mancal B deve ficar depois do mancal A.")

    estacoes = [
        _Estacao(
            f"Carga {i}",
            float(v[f"f{i}_x_mm"]),
            float(v[f"f{i}_fy_kN"]) * 1000.0,
            float(v[f"f{i}_fz_kN"]) * 1000.0,
            float(v[f"f{i}_fx_kN"]) * 1000.0,
            float(v[f"f{i}_raio_mm"]),
            float(v[f"f{i}_torque_Nm"]) * 1000.0,
            float(v[f"f{i}_massa_kg"]),
        )
        for i in _ESTACOES
        if bool(v[f"f{i}_ativa"])
    ]
    exigir(bool(estacoes), "Ative ao menos uma carga no eixo.")
    inicio = min(xa, *(s.x for s in estacoes))
    fim = max(xb, *(s.x for s in estacoes))
    exigir(
        inicio >= 0, "As posições são medidas a partir da ponta esquerda: use valores positivos."
    )
    comprimento = fim - inicio

    forcas_y = [(s.x, s.fy) for s in estacoes if s.fy]
    forcas_z = [(s.x, s.fz) for s in estacoes if s.fz]
    # A força axial aplicada no raio primitivo vira um binário no plano da força radial.
    binarios_y = [(s.x, s.fx * s.raio) for s in estacoes if s.fx and s.raio]
    ray, rby = _plano(xa, xb, forcas_y, binarios_y)
    raz, rbz = _plano(xa, xb, forcas_z, [])
    ra = math.hypot(ray, raz)
    rb = math.hypot(rby, rbz)
    axial_total = sum(s.fx for s in estacoes)
    mancal_axial = str(v["mancal_axial"])
    apoios_y = [(xa, ray), (xb, rby)]
    apoios_z = [(xa, raz), (xb, rbz)]
    area = math.pi * d**2 / 4.0
    inercia = math.pi * d**4 / 64.0
    j_polar = 2.0 * inercia
    ei = e * inercia

    nos = sorted({inicio, fim, xa, xb, *(s.x for s in estacoes)})
    passo = comprimento / _GRADE
    grade = sorted(
        {
            *nos,
            *(inicio + i * passo for i in range(_GRADE + 1)),
        }
    )
    momentos_y = [_momento(x, apoios_y, forcas_y, binarios_y) for x in grade]
    momentos_z = [_momento(x, apoios_z, forcas_z, []) for x in grade]
    resultantes = [math.hypot(a, b) for a, b in zip(momentos_y, momentos_z, strict=True)]
    torques = [sum(s.torque for s in estacoes if s.x <= x) for x in grade]

    desequilibrio = sum(s.torque for s in estacoes)
    alertas: list[str] = []
    if abs(desequilibrio) > 1e-3 * max(abs(s.torque) for s in estacoes) and any(
        s.torque for s in estacoes
    ):
        alertas.append(
            f"A soma dos torques deu {desequilibrio / 1000:.1f} N·m, e não zero: falta informar "
            "de onde sai o torque (o motor ou a carga, com sinal contrário)."
        )

    flecha_y = _elastica(grade, [m / ei for m in momentos_y], xa, xb)
    flecha_z = _elastica(grade, [m / ei for m in momentos_z], xa, xb)
    flecha = [math.hypot(a, b) for a, b in zip(flecha_y, flecha_z, strict=True)]
    inclinacao_a = math.hypot(_derivada(grade, flecha_y, xa), _derivada(grade, flecha_z, xa))
    inclinacao_b = math.hypot(_derivada(grade, flecha_y, xb), _derivada(grade, flecha_z, xb))
    flecha_max = max(flecha)

    # Rotação crítica: o peso do eixo fica dividido pelos pontos da grade.
    massas = [0.0] * len(grade)
    for i in range(len(grade)):
        vizinho_a = grade[i - 1] if i else grade[i]
        vizinho_b = grade[i + 1] if i + 1 < len(grade) else grade[i]
        massas[i] = densidade * area * (vizinho_b - vizinho_a) / 2.0
    for s in estacoes:
        i = min(range(len(grade)), key=lambda k: abs(grade[k] - s.x))
        massas[i] += s.massa
    critica = rotacao_critica_rayleigh(grade, massas, ei, xa, xb)

    torcao_total = 0.0
    for i in range(1, len(grade)):
        torcao_total += abs(torques[i - 1]) * (grade[i] - grade[i - 1]) / (g_mod * j_polar)
    trecho_torcido = sum(grade[i] - grade[i - 1] for i in range(1, len(grade)) if torques[i - 1])
    torcao_grau_m = (
        math.degrees(torcao_total) / (trecho_torcido / 1000.0) if trecho_torcido > 0 else 0.0
    )

    mmax = max(resultantes)
    # A seção crítica é a que tem o maior momento com torque somado por von Mises.
    equivalente = [math.hypot(m, t) for m, t in zip(resultantes, torques, strict=True)]
    i_critico = equivalente.index(max(equivalente))
    m_critico = resultantes[i_critico]
    t_critico = abs(torques[i_critico])
    x_critico = grade[i_critico]
    # N é positivo em tração: uma força à esquerda da seção, apontando para ela, comprime.
    normal_critico = -sum(s.fx for s in estacoes if s.x <= x_critico)
    if x_critico >= (xa if mancal_axial == "A" else xb):
        normal_critico += axial_total
    # O eixo gira e toda fibra passa pelo lado em que a flexão soma com o normal.
    sigma = 32.0 * m_critico / (math.pi * d**3) + abs(normal_critico) / area
    tau = 16.0 * t_critico / (math.pi * d**3)
    ponto = Ponto("Seção crítica, superfície", sigma, 0.0, tau)

    tipo_a = str(v["mancal_a"])
    tipo_b = str(v["mancal_b"])
    verificacoes = [
        limite(
            "Inclinação no mancal A",
            inclinacao_a,
            INCLINACAO_MANCAL[tipo_a],
            "rad",
            f"limite de {tipo_a.lower()}",
            f"{SHIGLEY_7} (Tabela 7-2)",
        ),
        limite(
            "Inclinação no mancal B",
            inclinacao_b,
            INCLINACAO_MANCAL[tipo_b],
            "rad",
            f"limite de {tipo_b.lower()}",
            f"{SHIGLEY_7} (Tabela 7-2)",
        ),
        limite(
            "Flecha máxima",
            flecha_max,
            float(v["flecha_adm_mm"]),
            "mm",
            "dupla integração de M/EI nos dois planos",
            f"{SHIGLEY_7} (Tabela 7-2)",
        ),
        limite(
            "Torção do eixo",
            torcao_grau_m,
            float(v["torcao_adm"]),
            "°/m",
            "θ = T·L/(G·J), no trecho com torque",
            "Prática de eixos de transmissão",
        ),
    ]
    if rotacao > 0:
        verificacoes.append(
            minimo(
                "Distância da rotação crítica",
                critica,
                1.3 * rotacao,
                "rpm",
                "n_cr ≥ 1,3·n (fora da banda de ressonância de ±30 %)",
                f"Rayleigh, em {SHIGLEY_7}",
            )
        )
        verificacoes.append(
            recomendacao_minima(
                "Rotação crítica, folga recomendada",
                critica,
                2.0 * rotacao,
                "rpm",
                "n_cr ≥ 2·n",
                SHIGLEY_7,
            )
        )
    tabela = []
    for x in nos:
        i = min(range(len(grade)), key=lambda k: abs(grade[k] - x))
        nome = "Mancal A" if x == xa else "Mancal B" if x == xb else "Carga"
        for s in estacoes:
            if s.x == x:
                nome = s.nome
        tabela.append(
            {
                "Seção": nome,
                "x (mm)": x,
                "M vertical (N·m)": momentos_y[i] / 1000.0,
                "M horizontal (N·m)": momentos_z[i] / 1000.0,
                "M resultante (N·m)": resultantes[i] / 1000.0,
                "Torque (N·m)": torques[i] / 1000.0,
                "Flecha (mm)": flecha[i],
            }
        )
    passo_grafico = max(1, len(grade) // 200)
    pontos_m = tuple(
        (grade[i], resultantes[i] / 1000.0, "Momento resultante")
        for i in range(0, len(grade), passo_grafico)
    )
    pontos_t = tuple(
        (grade[i], torques[i] / 1000.0, "Torque") for i in range(0, len(grade), passo_grafico)
    )
    pontos_f = tuple((grade[i], flecha[i], "Flecha") for i in range(0, len(grade), passo_grafico))
    return Resultado(
        resumo=(
            f"Reações radiais de {ra / 1000:.2f} kN em A e {rb / 1000:.2f} kN em B. Seção crítica "
            f"em x = {x_critico:.0f} mm: M = {m_critico / 1000:.0f} N·m e "
            f"T = {t_critico / 1000:.0f} N·m. Rotação crítica de {critica:.0f} rpm."
        ),
        metricas=(
            Metrica("Reação radial em A", ra / 1000.0, "kN"),
            Metrica("Reação radial em B", rb / 1000.0, "kN"),
            Metrica("Reação axial", abs(axial_total) / 1000.0, "kN"),
            Metrica("Momento máximo", mmax / 1000.0, "N·m", 1),
            Metrica("Torque máximo", max(abs(t) for t in torques) / 1000.0, "N·m", 1),
            Metrica("Flecha máxima", flecha_max, "mm", 3),
            Metrica("Rotação crítica", critica, "rpm", 0),
            Metrica("Torção", torcao_grau_m, "°/m", 3),
        ),
        verificacoes=tuple(verificacoes),
        pontos=(ponto,),
        tabelas=(Tabela("Esforços nas seções", tuple(tabela)),),
        graficos=(
            Grafico("Momento resultante", "Posição (mm)", "M (N·m)", pontos_m),
            Grafico("Torque", "Posição (mm)", "T (N·m)", pontos_t),
            Grafico("Flecha", "Posição (mm)", "Flecha (mm)", pontos_f),
        ),
        alertas=tuple(alertas),
        hipoteses=(
            "Eixo de diâmetro constante sobre dois mancais tratados como apoios simples.",
            "Momentos nos dois planos somados como vetores: o eixo gira, e a resultante é o que "
            "cada fibra sente.",
            "Rotação crítica de Rayleigh com a flecha do peso: dá um valor um pouco acima do real, "
            "por isso a folga de 30 % é tratada como mínima.",
            "Sem a rigidez dos mancais e da carcaça, que baixa a rotação crítica.",
            "Com ressaltos, confira depois cada seção em Seção de eixo: fadiga e entalhe.",
        ),
        referencias=(SHIGLEY_7,),
        envios=(
            Envio(
                "eixo_secao",
                "Levar a seção crítica para a fadiga",
                {
                    "d_mm": d,
                    "ma_Nm": m_critico / 1000.0,
                    "mm_Nm": 0.0,
                    "ta_Nm": 0.0,
                    "tm_Nm": t_critico / 1000.0,
                    "axial_kN": normal_critico / 1000.0,
                },
            ),
            Envio(
                "rolamento",
                "Levar a reação do mancal A para o rolamento",
                {
                    "fr_kN": ra / 1000.0,
                    "fa_kN": abs(axial_total) / 1000.0 if mancal_axial == "A" else 0.0,
                    "rotacao_rpm": rotacao,
                },
            ),
            Envio(
                "rolamento",
                "Levar a reação do mancal B para o rolamento",
                {
                    "fr_kN": rb / 1000.0,
                    "fa_kN": abs(axial_total) / 1000.0 if mancal_axial == "B" else 0.0,
                    "rotacao_rpm": rotacao,
                },
            ),
        ),
    )


def _campos_da_estacao(i: int, padrao: dict[str, float | bool]) -> tuple[Campo, ...]:
    secao = f"Carga {i}"
    quando = (f"f{i}_ativa", (True,))
    return (
        Campo(
            f"f{i}_ativa",
            f"Usar a carga {i}",
            "Ligue para incluir esta engrenagem, polia ou força no eixo.",
            bool(padrao["ativa"]),
            secao=secao,
        ),
        Campo(
            f"f{i}_x_mm",
            "Posição x",
            "Distância até a ponta esquerda do eixo. Pode ficar fora dos mancais, em balanço.",
            float(padrao["x"]),
            "mm",
            minimo=0.0,
            passo=10.0,
            secao=secao,
            quando=quando,
        ),
        Campo(
            f"f{i}_fy_kN",
            "Força vertical F_y",
            "Componente no plano vertical. Em engrenagem, é a força radial.",
            float(padrao["fy"]),
            "kN",
            passo=0.5,
            secao=secao,
            quando=quando,
        ),
        Campo(
            f"f{i}_fz_kN",
            "Força horizontal F_z",
            "Componente no plano horizontal. Em engrenagem, é a força tangencial.",
            float(padrao["fz"]),
            "kN",
            passo=0.5,
            secao=secao,
            quando=quando,
        ),
        Campo(
            f"f{i}_fx_kN",
            "Força axial F_x",
            "Componente ao longo do eixo, como a de uma engrenagem helicoidal.",
            float(padrao["fx"]),
            "kN",
            passo=0.5,
            secao=secao,
            quando=quando,
        ),
        Campo(
            f"f{i}_raio_mm",
            "Raio da força axial",
            "A que distância do centro do eixo a força axial atua: o raio primitivo da "
            "engrenagem. Essa distância cria um momento que muda as reações.",
            float(padrao["raio"]),
            "mm",
            minimo=0.0,
            passo=5.0,
            secao=secao,
            quando=quando,
        ),
        Campo(
            f"f{i}_torque_Nm",
            "Torque aplicado",
            "Torque que entra (positivo) ou sai (negativo) do eixo neste ponto. A soma de todos "
            "precisa dar zero.",
            float(padrao["torque"]),
            "N·m",
            passo=10.0,
            secao=secao,
            quando=quando,
        ),
        Campo(
            f"f{i}_massa_kg",
            "Massa da peça",
            "Massa da engrenagem ou polia. Entra só na rotação crítica.",
            float(padrao["massa"]),
            "kg",
            minimo=0.0,
            passo=1.0,
            secao=secao,
            quando=quando,
        ),
    )


_PADRAO_ESTACOES: tuple[dict[str, float | bool], ...] = (
    {
        "ativa": True,
        "x": 150.0,
        "fy": 3.0,
        "fz": 8.0,
        "fx": 0.0,
        "raio": 0.0,
        "torque": 800.0,
        "massa": 25.0,
    },
    {
        "ativa": True,
        "x": 500.0,
        "fy": 0.0,
        "fz": 0.0,
        "fx": 0.0,
        "raio": 0.0,
        "torque": -800.0,
        "massa": 10.0,
    },
    {
        "ativa": False,
        "x": 300.0,
        "fy": 0.0,
        "fz": 0.0,
        "fx": 0.0,
        "raio": 0.0,
        "torque": 0.0,
        "massa": 0.0,
    },
    {
        "ativa": False,
        "x": 350.0,
        "fy": 0.0,
        "fz": 0.0,
        "fx": 0.0,
        "raio": 0.0,
        "torque": 0.0,
        "massa": 0.0,
    },
)

CAMPOS_EIXO_TRANSMISSAO = (
    Campo(
        "d_mm",
        "Diâmetro do eixo d",
        "Diâmetro de referência. O cálculo supõe o eixo com este diâmetro do começo ao fim.",
        60.0,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Eixo",
    ),
    Campo(
        "xa_mm",
        "Posição do mancal A",
        "Distância do centro do mancal A até a ponta esquerda do eixo.",
        50.0,
        "mm",
        minimo=0.0,
        passo=10.0,
        secao="Eixo",
    ),
    Campo(
        "xb_mm",
        "Posição do mancal B",
        "Distância do centro do mancal B até a ponta esquerda do eixo.",
        450.0,
        "mm",
        minimo=0.0,
        passo=10.0,
        secao="Eixo",
    ),
    Campo(
        "mancal_a",
        "Tipo do mancal A",
        "O tipo do rolamento define a inclinação que ele aceita. Rolo cônico é o mais exigente; "
        "autocompensador aceita muito mais.",
        "Esferas de sulco profundo",
        opcoes=tuple(INCLINACAO_MANCAL),
        secao="Eixo",
    ),
    Campo(
        "mancal_b",
        "Tipo do mancal B",
        "O tipo do rolamento do outro apoio.",
        "Esferas de sulco profundo",
        opcoes=tuple(INCLINACAO_MANCAL),
        secao="Eixo",
    ),
    Campo(
        "mancal_axial",
        "Quem segura a força axial",
        "Em eixo com dois mancais, só um deve ser fixo no sentido axial; o outro fica livre para "
        "o eixo dilatar.",
        "A",
        opcoes=("A", "B"),
        secao="Eixo",
    ),
    Campo(
        "rotacao_rpm",
        "Rotação de trabalho",
        "Rotação do eixo. Entra na comparação com a rotação crítica.",
        300.0,
        "rpm",
        minimo=0.0,
        passo=10.0,
        secao="Eixo",
    ),
    Campo(
        "e_GPa",
        "Módulo de elasticidade E",
        "Aço: 205 GPa.",
        205.0,
        "GPa",
        minimo=10.0,
        passo=5.0,
        secao="Material e limites",
    ),
    Campo(
        "poisson",
        "Coeficiente de Poisson ν",
        "Aço: 0,30.",
        0.30,
        minimo=0.1,
        maximo=0.45,
        passo=0.01,
        secao="Material e limites",
    ),
    Campo(
        "densidade_kg_m3",
        "Massa específica",
        "Aço: 7850 kg/m³. Dá o peso do próprio eixo na rotação crítica.",
        7850.0,
        "kg/m³",
        minimo=100.0,
        passo=10.0,
        secao="Material e limites",
    ),
    Campo(
        "flecha_adm_mm",
        "Flecha admissível",
        "Maior flecha aceita. Engrenagem de dentes retos: de 0,08 a 0,25 mm, conforme o módulo.",
        0.25,
        "mm",
        minimo=0.001,
        passo=0.01,
        secao="Material e limites",
    ),
    Campo(
        "torcao_adm",
        "Torção admissível",
        "Maior giro por metro de eixo. Eixo de transmissão comum: 0,25 a 0,5 °/m. Valores maiores "
        "fazem o eixo oscilar em torção.",
        0.5,
        "°/m",
        minimo=0.001,
        passo=0.05,
        secao="Material e limites",
    ),
    *(c for i in _ESTACOES for c in _campos_da_estacao(i, _PADRAO_ESTACOES[i - 1])),
)


# ---------------------------------------------------------------------------
# Chaveta paralela
# ---------------------------------------------------------------------------

#: DIN 6885-1: (d acima de, d até, b, h, t₁ no eixo, t₂ no cubo), em mm.
CHAVETAS = (
    (6, 8, 2, 2, 1.2, 1.0),
    (8, 10, 3, 3, 1.8, 1.4),
    (10, 12, 4, 4, 2.5, 1.8),
    (12, 17, 5, 5, 3.0, 2.3),
    (17, 22, 6, 6, 3.5, 2.8),
    (22, 30, 8, 7, 4.0, 3.3),
    (30, 38, 10, 8, 5.0, 3.3),
    (38, 44, 12, 8, 5.0, 3.3),
    (44, 50, 14, 9, 5.5, 3.8),
    (50, 58, 16, 10, 6.0, 4.3),
    (58, 65, 18, 11, 7.0, 4.4),
    (65, 75, 20, 12, 7.5, 4.9),
    (75, 85, 22, 14, 9.0, 5.4),
    (85, 95, 25, 14, 9.0, 5.4),
    (95, 110, 28, 16, 10.0, 6.4),
    (110, 130, 32, 18, 11.0, 7.4),
    (130, 150, 36, 20, 12.0, 8.4),
    (150, 170, 40, 22, 13.0, 9.4),
    (170, 200, 45, 25, 15.0, 10.4),
    (200, 230, 50, 28, 17.0, 11.4),
    (230, 260, 56, 32, 20.0, 12.4),
    (260, 290, 63, 32, 20.0, 12.4),
    (290, 330, 70, 36, 22.0, 14.4),
    (330, 380, 80, 40, 25.0, 15.4),
    (380, 440, 90, 45, 28.0, 17.4),
    (440, 500, 100, 50, 31.0, 19.5),
)


def chaveta_din(d_mm: float) -> tuple[float, float, float, float]:
    """(b, h, t₁, t₂) da DIN 6885-1 para o diâmetro do eixo."""
    for acima, ate, b, h, t1, t2 in CHAVETAS:
        if acima < d_mm <= ate:
            return float(b), float(h), t1, t2
    raise ValueError("A tabela DIN 6885 cobre eixos de 6 a 500 mm: informe as dimensões à mão.")


def calcular_chaveta(v: Valores) -> Resultado:
    d = float(v["d_mm"])
    torque = float(v["torque_Nm"]) * float(v["fator_servico"])
    comprimento = float(v["comprimento_mm"])
    fs = float(v["fs"])
    pontas = str(v["pontas"])
    quantidade = int(v["quantidade"])
    if str(v["dimensoes"]) == "DIN 6885":
        b, h, t1, _t2 = chaveta_din(d)
    else:
        b = float(v["b_mm"])
        h = float(v["h_mm"])
        t1 = float(v["t1_mm"])
    exigir(t1 < h, "A profundidade t₁ no eixo deve ser menor que a altura h da chaveta.")
    util = comprimento - b if pontas == "Arredondadas" else comprimento
    exigir(util > 0, "O comprimento da chaveta precisa ser maior que a largura.")
    # Duas chavetas a 180° nunca dividem a carga por igual: a DIN 6892 credita 75 % da segunda.
    efetivas = 1.0 if quantidade == 1 else 1.5

    forca = 2.0 * torque * 1000.0 / d
    sy_chaveta = float(v["sy_chaveta_MPa"])
    sy_eixo = float(v["sy_eixo_MPa"])
    sy_cubo = float(v["sy_cubo_MPa"])
    tau = forca / (b * util * efetivas)
    p_eixo = forca / (t1 * util * efetivas)
    p_cubo = forca / ((h - t1) * util * efetivas)
    limite_eixo = min(sy_eixo, sy_chaveta) / fs
    limite_cubo = min(sy_cubo, sy_chaveta) / fs
    limite_tau = 0.577 * sy_chaveta / fs
    necessario = max(
        forca / (b * limite_tau * efetivas),
        forca / (t1 * limite_eixo * efetivas),
        forca / ((h - t1) * limite_cubo * efetivas),
    )
    if pontas == "Arredondadas":
        necessario += b

    verificacoes = (
        limite(
            "Cisalhamento da chaveta",
            tau,
            limite_tau,
            "MPa",
            f"τ = F/(b·L) com F = {forca:.0f} N e L útil = {util:.1f} mm",
            DIN_6892,
        ),
        limite(
            "Esmagamento no rasgo do eixo",
            p_eixo,
            limite_eixo,
            "MPa",
            f"p = F/(t₁·L), com t₁ = {t1:g} mm",
            DIN_6892,
        ),
        limite(
            "Esmagamento no rasgo do cubo",
            p_cubo,
            limite_cubo,
            "MPa",
            f"p = F/[(h − t₁)·L], com h − t₁ = {h - t1:g} mm",
            DIN_6892,
        ),
        recomendacao(
            "Comprimento útil",
            util,
            1.5 * d,
            "mm",
            "L ≤ 1,5·d: além disso o torque se concentra no início da chaveta",
            "Shigley, Elementos de Máquinas, cap. 7",
        ),
    )
    return Resultado(
        resumo=(
            f"Chaveta {b:g} × {h:g} × {comprimento:g} mm recebe {forca / 1000:.1f} kN. "
            f"Comprimento mínimo: {necessario:.0f} mm."
        ),
        metricas=(
            Metrica("Força na chaveta", forca / 1000.0, "kN"),
            Metrica("Comprimento mínimo", necessario, "mm", 1),
            Metrica("Seção b × h", f"{b:g} × {h:g}", "mm"),
            Metrica("Rasgo no eixo t₁", t1, "mm", 1),
            Metrica("Cisalhamento τ", tau, "MPa", 1),
            Metrica("Esmagamento no eixo", p_eixo, "MPa", 1),
            Metrica("Esmagamento no cubo", p_cubo, "MPa", 1),
        ),
        verificacoes=verificacoes,
        hipoteses=(
            "Força uniforme ao longo da chaveta, aplicada no raio do eixo.",
            "Limites: S_y/FS para pressão e 0,577·S_y/FS para cisalhamento.",
            "Com carga alternada ou reversão, a chaveta bate no rasgo: o limite usual cai para "
            "cerca de metade, ou adote ajuste prensado.",
            "O rasgo reduz a fadiga do eixo: confira em Seção de eixo com o entalhe de chaveta.",
        ),
        referencias=(DIN_6885, DIN_6892),
        envios=(
            Envio(
                "eixo_secao",
                "Conferir o rasgo do eixo à fadiga",
                {"d_mm": d, "entalhe": ENTALHE_CHAVETA, "tm_Nm": float(v["torque_Nm"])},
            ),
        ),
    )


CAMPOS_CHAVETA = (
    Campo(
        "d_mm",
        "Diâmetro do eixo d",
        "Diâmetro do eixo no ponto da chaveta.",
        50.0,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Carga",
    ),
    Campo(
        "torque_Nm",
        "Torque nominal",
        "O torque que passa pela chaveta.",
        600.0,
        "N·m",
        minimo=0.001,
        passo=10.0,
        secao="Carga",
    ),
    Campo(
        "fator_servico",
        "Fator de serviço K_s",
        "Multiplica o torque. Carga uniforme: 1,0 a 1,25. Choque moderado: 1,5. Choque pesado: 2,0.",
        1.25,
        minimo=1.0,
        maximo=4.0,
        passo=0.05,
        secao="Carga",
    ),
    Campo(
        "fs",
        "Fator de segurança",
        "Margem sobre o escoamento. Comece com 2,0. A chaveta costuma ser a peça sacrificada, "
        "mais fraca que o eixo.",
        2.0,
        minimo=1.0,
        maximo=6.0,
        passo=0.1,
        secao="Carga",
    ),
    Campo(
        "dimensoes",
        "Dimensões da chaveta",
        "DIN 6885: a seção sai sozinha pelo diâmetro do eixo. Informar: você digita a seção, "
        "para uma chaveta especial ou em polegadas.",
        "DIN 6885",
        opcoes=("DIN 6885", "Informar"),
        secao="Chaveta",
    ),
    Campo(
        "b_mm",
        "Largura b",
        "Largura da chaveta.",
        14.0,
        "mm",
        minimo=0.5,
        passo=1.0,
        secao="Chaveta",
        quando=("dimensoes", ("Informar",)),
    ),
    Campo(
        "h_mm",
        "Altura h",
        "Altura total da chaveta.",
        9.0,
        "mm",
        minimo=0.5,
        passo=1.0,
        secao="Chaveta",
        quando=("dimensoes", ("Informar",)),
    ),
    Campo(
        "t1_mm",
        "Profundidade no eixo t₁",
        "Profundidade do rasgo no eixo. O que sobra da altura trabalha no cubo.",
        5.5,
        "mm",
        minimo=0.1,
        passo=0.5,
        secao="Chaveta",
        quando=("dimensoes", ("Informar",)),
    ),
    Campo(
        "comprimento_mm",
        "Comprimento total L",
        "Comprimento total da chaveta. Normalmente é menor que o cubo.",
        80.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Chaveta",
    ),
    Campo(
        "pontas",
        "Pontas da chaveta",
        "Arredondadas (forma A): a parte redonda não transmite carga, e o comprimento útil é "
        "L − b. Retas (forma B): o comprimento útil é L.",
        "Arredondadas",
        opcoes=("Arredondadas", "Retas"),
        secao="Chaveta",
    ),
    Campo(
        "quantidade",
        "Número de chavetas",
        "Uma ou duas chavetas a 180°. Com duas, só se conta 1,5 chaveta, porque o ajuste nunca "
        "divide a carga por igual.",
        1,
        minimo=1,
        maximo=2,
        passo=1,
        secao="Chaveta",
    ),
    Campo(
        "sy_chaveta_MPa",
        "Escoamento da chaveta",
        "Aço de chaveta C45 ou AISI 1045: cerca de 310 a 430 MPa.",
        350.0,
        "MPa",
        minimo=10.0,
        passo=10.0,
        secao="Materiais",
    ),
    Campo(
        "sy_eixo_MPa",
        "Escoamento do eixo",
        "Limite de escoamento do material do eixo.",
        420.0,
        "MPa",
        minimo=10.0,
        passo=10.0,
        secao="Materiais",
    ),
    Campo(
        "sy_cubo_MPa",
        "Escoamento do cubo",
        "Limite de escoamento do cubo. Ferro fundido cinzento não tem escoamento: use o limite "
        "de pressão do fabricante.",
        310.0,
        "MPa",
        minimo=10.0,
        passo=10.0,
        secao="Materiais",
    ),
)


# ---------------------------------------------------------------------------
# Ajuste prensado
# ---------------------------------------------------------------------------

#: Limites superiores das faixas de dimensão da NBR 6158 (Tabela 1, IT6 e IT7, em µm).
_FAIXAS_IT = (3, 6, 10, 18, 30, 50, 80, 120, 180, 250, 315, 400, 500)
_IT6 = (6, 8, 9, 11, 13, 16, 19, 22, 25, 29, 32, 36, 40)
_IT7 = (10, 12, 15, 18, 21, 25, 30, 35, 40, 46, 52, 57, 63)
_FAIXAS_P = _FAIXAS_IT
_EI_P = (6, 12, 15, 18, 22, 26, 32, 37, 43, 50, 56, 62, 68)
#: Faixas finas de r, s, t e u (Tabela 2, afastamento inferior ei, em µm).
_FAIXAS_FINAS = (
    3, 6, 10, 18, 24, 30, 40, 50, 65, 80, 100, 120, 140, 160, 180, 200, 225, 250, 280, 315, 355,
    400, 450, 500,
)  # fmt: skip
_EI_R = (
    10, 15, 19, 23, 28, 28, 34, 34, 41, 43, 51, 54, 63, 65, 68, 77, 80, 84, 94, 98, 108, 114, 126,
    132,
)  # fmt: skip
_EI_S = (
    14, 19, 23, 28, 35, 35, 43, 43, 53, 59, 71, 79, 92, 100, 108, 122, 130, 140, 158, 170, 190,
    208, 232, 252,
)  # fmt: skip
_EI_U = (
    18, 23, 28, 33, 41, 48, 60, 70, 87, 102, 124, 144, 170, 190, 210, 236, 258, 284, 315, 350, 390,
    435, 490, 540,
)  # fmt: skip

AJUSTES = {
    "H7/p6 (leve, com prensa)": ("p", _FAIXAS_P, _EI_P),
    "H7/r6 (médio)": ("r", _FAIXAS_FINAS, _EI_R),
    "H7/s6 (forte)": ("s", _FAIXAS_FINAS, _EI_S),
    "H7/u6 (muito forte, a quente)": ("u", _FAIXAS_FINAS, _EI_U),
}
AJUSTE_MANUAL = "Informar a interferência"


def _na_faixa(limites: tuple[int, ...], valores: tuple[int, ...], d: float) -> int:
    for ate, valor in zip(limites, valores, strict=True):
        if d <= ate:
            return valor
    raise ValueError("A NBR 6158 aqui vai até 500 mm: informe a interferência.")


def interferencia_do_ajuste(d_mm: float, ajuste: str) -> tuple[float, float]:
    """Interferência mínima e máxima (µm) de furo H7 com eixo IT6, pela NBR 6158."""
    _letra, faixas, afastamentos = AJUSTES[ajuste]
    it6 = _na_faixa(_FAIXAS_IT, _IT6, d_mm)
    it7 = _na_faixa(_FAIXAS_IT, _IT7, d_mm)
    ei = _na_faixa(faixas, afastamentos, d_mm)
    es = ei + it6
    return float(ei - it7), float(es)


def pressao_de_ajuste(
    interferencia_mm: float,
    d: float,
    d_furo: float,
    D_cubo: float,
    E_eixo: float,
    nu_eixo: float,
    E_cubo: float,
    nu_cubo: float,
) -> float:
    """Pressão na interface em MPa (Shigley, eq. 3-56), com a interferência diametral."""
    fator_cubo = ((D_cubo**2 + d**2) / (D_cubo**2 - d**2) + nu_cubo) / E_cubo
    fator_eixo = ((d**2 + d_furo**2) / (d**2 - d_furo**2) - nu_eixo) / E_eixo
    return interferencia_mm / (d * (fator_cubo + fator_eixo))


def calcular_ajuste(v: Valores) -> Resultado:
    d = float(v["d_mm"])
    d_furo = float(v["d_furo_mm"])
    D = float(v["D_cubo_mm"])
    L = float(v["L_mm"])
    e_eixo = float(v["e_eixo_GPa"]) * 1000.0
    e_cubo = float(v["e_cubo_GPa"]) * 1000.0
    nu_eixo = float(v["nu_eixo"])
    nu_cubo = float(v["nu_cubo"])
    atrito = float(v["atrito"])
    fs = float(v["fs"])
    torque = float(v["torque_Nm"]) * 1000.0 * float(v["fator_servico"])
    axial = float(v["axial_kN"]) * 1000.0
    sy_cubo = float(v["sy_cubo_MPa"])
    sy_eixo = float(v["sy_eixo_MPa"])
    exigir(D > d, "O diâmetro externo do cubo deve ser maior que o do ajuste.")
    exigir(0 <= d_furo < d, "O furo do eixo deve ser menor que o diâmetro do ajuste.")

    ajuste = str(v["ajuste"])
    if ajuste == AJUSTE_MANUAL:
        delta_min = float(v["delta_min_um"])
        delta_max = float(v["delta_max_um"])
    else:
        delta_min, delta_max = interferencia_do_ajuste(d, ajuste)
    exigir(delta_max >= delta_min, "A interferência máxima deve ser maior ou igual à mínima.")
    alisamento = 0.8 * (float(v["rz_eixo_um"]) + float(v["rz_cubo_um"]))
    efetiva_min = delta_min - alisamento
    efetiva_max = delta_max - alisamento
    exigir(
        efetiva_min > 0, "A rugosidade consome toda a interferência mínima: o ajuste fica solto."
    )

    argumentos = (d, d_furo, D, e_eixo, nu_eixo, e_cubo, nu_cubo)
    p_min = pressao_de_ajuste(efetiva_min / 1000.0, *argumentos)
    p_max = pressao_de_ajuste(efetiva_max / 1000.0, *argumentos)

    capacidade_forca = math.pi * atrito * p_min * d * L
    torque_capaz = capacidade_forca * d / 2.0
    solicitante = math.hypot(axial, 2.0 * torque / d)

    relacao_cubo = (D**2 + d**2) / (D**2 - d**2)
    sigma_t_cubo = p_max * relacao_cubo
    cubo = Ponto("Furo do cubo (pressão máxima)", sigma_t_cubo, -p_max)
    if d_furo > 0:
        sigma_t_eixo = -p_max * (d**2 + d_furo**2) / (d**2 - d_furo**2)
        eixo = Ponto("Superfície do eixo (pressão máxima)", sigma_t_eixo, -p_max)
    else:
        eixo = Ponto("Superfície do eixo (pressão máxima)", -p_max, -p_max)

    alfa = float(v["alfa_um_mK"]) * 1e-6
    folga_montagem = 0.001 * d
    aquecimento = (delta_max / 1000.0 + folga_montagem) / (alfa * d)
    forca_prensa = math.pi * float(v["atrito_prensa"]) * p_max * d * L

    verificacoes = [
        minimo(
            "Transmissão por atrito",
            capacidade_forca,
            solicitante * fs,
            "N",
            f"π·μ·p_mín·d·L ≥ FS·√[F² + (2T/d)²], com p_mín = {p_min:.1f} MPa",
            "Shigley, Elementos de Máquinas, cap. 3",
        ),
        limite(
            "Escoamento no furo do cubo",
            cubo.von_mises,
            sy_cubo,
            "MPa",
            f"Lamé com p_máx = {p_max:.1f} MPa: σθ = p(D² + d²)/(D² − d²)",
            "Shigley, Elementos de Máquinas, cap. 3",
        ),
        limite(
            "Escoamento na superfície do eixo",
            eixo.von_mises,
            sy_eixo,
            "MPa",
            "Lamé com p_máx",
            "Shigley, Elementos de Máquinas, cap. 3",
        ),
        recomendacao(
            "Aquecimento do cubo para montar",
            aquecimento,
            float(v["temperatura_max"]),
            "°C",
            "ΔT = (δ_máx + 0,001·d)/(α·d)",
            "Prática de montagem a quente",
        ),
        faixa_recomendada(
            "Comprimento do ajuste L/d",
            L / d,
            0.5,
            2.0,
            "—",
            "faixa usual 0,5 ≤ L/d ≤ 2",
            "Prática de cubos prensados",
        ),
    ]
    alertas = [
        "Nas bordas do cubo a pressão sobe e a fadiga por atrito (fretting) começa ali: confira "
        "em Seção de eixo com o entalhe de cubo prensado.",
    ]
    return Resultado(
        resumo=(
            f"Interferência de {delta_min:.0f} a {delta_max:.0f} µm: pressão de {p_min:.1f} a "
            f"{p_max:.1f} MPa e capacidade de {torque_capaz / 1000:.0f} N·m por atrito."
        ),
        metricas=(
            Metrica("Interferência mínima", delta_min, "µm", 0),
            Metrica("Interferência máxima", delta_max, "µm", 0),
            Metrica("Pressão mínima", p_min, "MPa", 1),
            Metrica("Pressão máxima", p_max, "MPa", 1),
            Metrica("Torque por atrito", torque_capaz / 1000.0, "N·m", 0),
            Metrica("Força axial por atrito", capacidade_forca / 1000.0, "kN", 1),
            Metrica("Força de prensagem", forca_prensa / 1000.0, "kN", 1),
            Metrica("Aquecimento para montar", aquecimento, "°C", 0),
        ),
        verificacoes=tuple(verificacoes),
        pontos=(cubo, eixo),
        alertas=tuple(alertas),
        hipoteses=(
            "Cilindros longos: pressão uniforme ao longo do ajuste (Lamé), em regime elástico.",
            "Interferência útil = nominal − 0,8·(Rz do eixo + Rz do furo), pelo alisamento da "
            "rugosidade na montagem.",
            "Transmissão verificada com a menor interferência; tensões com a maior.",
            "A força centrífuga, que folga o ajuste em alta rotação, não está incluída.",
        ),
        referencias=(NBR_6158, "Shigley, Elementos de Máquinas, cap. 3", DIN_7190),
        envios=(
            Envio(
                "eixo_secao",
                "Conferir a borda do cubo à fadiga",
                {"d_mm": d, "entalhe": ENTALHE_PRENSADO, "tm_Nm": float(v["torque_Nm"])},
            ),
        ),
    )


CAMPOS_AJUSTE = (
    Campo(
        "d_mm",
        "Diâmetro do ajuste d",
        "Diâmetro nominal do encaixe entre eixo e cubo.",
        80.0,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Geometria",
    ),
    Campo(
        "d_furo_mm",
        "Furo do eixo",
        "Diâmetro do furo central do eixo. Eixo maciço: 0.",
        0.0,
        "mm",
        minimo=0.0,
        passo=1.0,
        secao="Geometria",
    ),
    Campo(
        "D_cubo_mm",
        "Diâmetro externo do cubo",
        "Diâmetro de fora do cubo na região do ajuste. Cubo fino demais escoa.",
        140.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Geometria",
    ),
    Campo(
        "L_mm",
        "Comprimento do ajuste L",
        "Comprimento do encaixe, descontando chanfros.",
        80.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Geometria",
    ),
    Campo(
        "ajuste",
        "Ajuste",
        "Os ajustes H7/p6 a H7/u6 saem das tabelas da NBR 6158. Do mais leve ao mais forte: "
        "quanto maior a letra do eixo, maior a interferência.",
        "H7/s6 (forte)",
        opcoes=(*AJUSTES, AJUSTE_MANUAL),
        secao="Ajuste",
    ),
    Campo(
        "delta_min_um",
        "Interferência mínima",
        "Menor interferência diametral esperada, em micrômetros.",
        50.0,
        "µm",
        minimo=0.0,
        passo=5.0,
        secao="Ajuste",
        quando=("ajuste", (AJUSTE_MANUAL,)),
    ),
    Campo(
        "delta_max_um",
        "Interferência máxima",
        "Maior interferência diametral esperada, em micrômetros.",
        100.0,
        "µm",
        minimo=0.0,
        passo=5.0,
        secao="Ajuste",
        quando=("ajuste", (AJUSTE_MANUAL,)),
    ),
    Campo(
        "rz_eixo_um",
        "Rugosidade Rz do eixo",
        "A montagem amassa os picos da rugosidade e parte da interferência se perde. Retificado: "
        "cerca de 4 µm. Torneado fino: cerca de 6,3 µm.",
        4.0,
        "µm",
        minimo=0.0,
        passo=0.5,
        secao="Ajuste",
    ),
    Campo(
        "rz_cubo_um",
        "Rugosidade Rz do furo",
        "Rugosidade do furo do cubo. Mandrilado ou alargado: de 6,3 a 10 µm.",
        6.3,
        "µm",
        minimo=0.0,
        passo=0.5,
        secao="Ajuste",
    ),
    Campo(
        "torque_Nm",
        "Torque nominal",
        "O torque que o ajuste precisa transmitir sem chaveta.",
        800.0,
        "N·m",
        minimo=0.0,
        passo=50.0,
        secao="Carga",
    ),
    Campo(
        "fator_servico",
        "Fator de serviço K_s",
        "Multiplica o torque. Carga uniforme: 1,0 a 1,25. Choque moderado: 1,5. Choque pesado: 2,0.",
        1.25,
        minimo=1.0,
        maximo=4.0,
        passo=0.05,
        secao="Carga",
    ),
    Campo(
        "axial_kN",
        "Força axial",
        "Força que tenta tirar o cubo do eixo.",
        0.0,
        "kN",
        minimo=0.0,
        passo=1.0,
        secao="Carga",
    ),
    Campo(
        "fs",
        "Fator contra o deslizamento",
        "Margem sobre a capacidade de atrito. Comece com 1,5.",
        1.5,
        minimo=1.0,
        maximo=5.0,
        passo=0.1,
        secao="Carga",
    ),
    Campo(
        "atrito",
        "Atrito em serviço μ",
        "Aço com aço, seco e desengraxado, montado a quente: cerca de 0,15. Lubrificado com "
        "prensa: cerca de 0,10.",
        0.12,
        minimo=0.01,
        maximo=0.5,
        passo=0.01,
        secao="Carga",
    ),
    Campo(
        "atrito_prensa",
        "Atrito na prensagem",
        "Atrito durante a montagem com prensa, com lubrificante: cerca de 0,08 a 0,15.",
        0.10,
        minimo=0.01,
        maximo=0.5,
        passo=0.01,
        secao="Montagem",
    ),
    Campo(
        "alfa_um_mK",
        "Dilatação do cubo α",
        "Coeficiente de dilatação do cubo, em milionésimos por °C. Aço: 11,5. Ferro fundido: 10,5.",
        11.5,
        "µm/(m·°C)",
        minimo=1.0,
        maximo=40.0,
        passo=0.5,
        secao="Montagem",
    ),
    Campo(
        "temperatura_max",
        "Aquecimento máximo aceito",
        "Aquecer demais muda a têmpera do cubo. Aço temperado e revenido: use uma margem abaixo "
        "da temperatura de revenimento. Valor usual: até 250 °C.",
        250.0,
        "°C",
        minimo=20.0,
        maximo=600.0,
        passo=10.0,
        secao="Montagem",
    ),
    Campo(
        "e_eixo_GPa",
        "E do eixo",
        "Módulo de elasticidade do eixo. Aço: 205 GPa.",
        205.0,
        "GPa",
        minimo=10.0,
        passo=5.0,
        secao="Materiais",
    ),
    Campo(
        "nu_eixo",
        "ν do eixo",
        "Coeficiente de Poisson do eixo. Aço: 0,30.",
        0.30,
        minimo=0.1,
        maximo=0.45,
        passo=0.01,
        secao="Materiais",
    ),
    Campo(
        "sy_eixo_MPa",
        "Escoamento do eixo",
        "Limite de escoamento do eixo.",
        420.0,
        "MPa",
        minimo=10.0,
        passo=10.0,
        secao="Materiais",
    ),
    Campo(
        "e_cubo_GPa",
        "E do cubo",
        "Módulo de elasticidade do cubo. Aço: 205 GPa. Ferro fundido nodular: cerca de 170 GPa.",
        205.0,
        "GPa",
        minimo=10.0,
        passo=5.0,
        secao="Materiais",
    ),
    Campo(
        "nu_cubo",
        "ν do cubo",
        "Coeficiente de Poisson do cubo. Aço: 0,30.",
        0.30,
        minimo=0.1,
        maximo=0.45,
        passo=0.01,
        secao="Materiais",
    ),
    Campo(
        "sy_cubo_MPa",
        "Escoamento do cubo",
        "Limite de escoamento do cubo. O ajuste não deve escoar o furo: a interferência se "
        "perderia.",
        420.0,
        "MPa",
        minimo=10.0,
        passo=10.0,
        secao="Materiais",
    ),
)


CASOS: tuple[Caso, ...] = (
    Caso(
        "eixo_transmissao",
        "Eixo sobre dois mancais",
        GRUPO,
        "Cargas nos dois planos: reações, diagramas, flecha, torção e rotação crítica.",
        "Monte o eixo com até quatro cargas (engrenagens, polias, forças). Saem as reações nos "
        "mancais, a seção crítica, a inclinação nos mancais e a primeira rotação crítica.",
        CAMPOS_EIXO_TRANSMISSAO,
        calcular_eixo_transmissao,
        r"M=\sqrt{M_y^2+M_z^2},\quad v''=\frac{M}{EI},\quad "
        r"\omega_{cr}=\sqrt{\frac{g\sum m_i|y_i|}{\sum m_i y_i^2}}",
    ),
    Caso(
        "eixo_secao",
        "Seção de eixo: fadiga e entalhe",
        GRUPO,
        "Ressalto, chaveta, canal de anel ou cubo: K_t, K_f, fadiga e diâmetro mínimo.",
        "Verifica uma seção de eixo com o entalhe que ela tem. Calcula K_t e K_f, o limite de "
        "fadiga pelos fatores de Marin, o fator de segurança e o menor diâmetro aceitável.",
        CAMPOS_EIXO_SECAO,
        calcular_eixo_secao,
        r"\frac{1}{n}=\frac{16}{\pi d^3}\left[\frac{\sqrt{4(K_fM_a)^2+3(K_{fs}T_a)^2}}{S_e}"
        r"+\frac{\sqrt{4(K_fM_m)^2+3(K_{fs}T_m)^2}}{S_{ut}}\right]",
    ),
    Caso(
        "chaveta",
        "Chaveta paralela",
        GRUPO,
        "DIN 6885: cisalhamento, esmagamento no eixo e no cubo e comprimento mínimo.",
        "A seção da chaveta sai da DIN 6885 pelo diâmetro do eixo. O programa confere o "
        "cisalhamento, o esmagamento nos dois rasgos e diz o comprimento mínimo.",
        CAMPOS_CHAVETA,
        calcular_chaveta,
        r"F=\frac{2T}{d},\qquad \tau=\frac{F}{b\,L},\qquad p=\frac{F}{t\,L}",
    ),
    Caso(
        "ajuste_prensado",
        "Ajuste prensado",
        GRUPO,
        "Cubo no eixo sem chaveta: pressão, torque por atrito, tensões e aquecimento.",
        "Usa os ajustes H7/p6 a H7/u6 da NBR 6158 ou uma interferência informada. Sai a pressão, "
        "o torque que o atrito transmite, as tensões de Lamé e a força ou o calor para montar.",
        CAMPOS_AJUSTE,
        calcular_ajuste,
        r"p=\frac{\delta}{d\left[\frac{1}{E_c}\left(\frac{D^2+d^2}{D^2-d^2}+\nu_c\right)"
        r"+\frac{1}{E_e}\left(\frac{d^2+d_i^2}{d^2-d_i^2}-\nu_e\right)\right]}",
    ),
)
