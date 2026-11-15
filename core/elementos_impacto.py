"""Carga de impacto: peso que cai ou corpo que bate com velocidade, pelo balanço de energia.

A energia do corpo vira energia de deformação da peça, que trabalha como uma mola de rigidez k:

* queda de altura h: δ_máx = δ_st·(1 + √(1 + 2h/δ_st)), com δ_st = W/k;
* batida horizontal com velocidade v: δ_máx = v·√(m/k).

A força máxima é k·δ_máx, e o fator de impacto n = F_máx/W multiplica a tensão estática. A conta
despreza a massa da peça e a perda de energia no choque, e por isso fica a favor da segurança
(Hibbeler, cap. 14; Shigley, cap. 4).
"""

from __future__ import annotations

import math

from core.elementos_base import (
    Campo,
    Caso,
    Envio,
    Metrica,
    Resultado,
    Valores,
    exigir,
    informativo,
    limite,
)

GRUPO = "Máquinas e vibração"
G = 9.80665  # m/s²

BARRA = "Barra sob força axial"
BIAPOIADA = "Viga biapoiada, peso no meio"
BALANCO = "Viga em balanço, peso na ponta"
MOLA = "Mola ou apoio de rigidez conhecida"
PECAS = (BARRA, BIAPOIADA, BALANCO, MOLA)

QUEDA = "Queda de uma altura"
BATIDA = "Batida horizontal com velocidade"
MODOS = (QUEDA, BATIDA)

HIBBELER = "Hibbeler, Resistência dos Materiais, cap. 14 (carregamento de impacto)"
SHIGLEY = "Budynas e Nisbett, Elementos de Máquinas de Shigley, cap. 4 (impacto)"


def rigidez(v: Valores) -> tuple[float, str]:
    """Rigidez da peça no ponto do impacto (N/mm) e a fórmula usada."""
    peca = str(v["peca"])
    if peca == MOLA:
        return float(v["k_N_mm"]), "k informado"
    e = float(v["e_GPa"]) * 1000.0
    comprimento = float(v["l_mm"])
    if peca == BARRA:
        area = float(v["area_mm2"])
        return e * area / comprimento, f"k = E·A/L = {e:.0f}·{area:g}/{comprimento:g}"
    inercia = float(v["i_mm4"])
    if peca == BIAPOIADA:
        return 48.0 * e * inercia / comprimento**3, "k = 48·E·I/L³"
    return 3.0 * e * inercia / comprimento**3, "k = 3·E·I/L³"


def tensao_por_newton(v: Valores) -> float:
    """Tensão máxima na peça para 1 N no ponto do impacto (MPa/N); zero para a mola."""
    peca = str(v["peca"])
    if peca == BARRA:
        return 1.0 / float(v["area_mm2"])
    if peca == BIAPOIADA:
        return float(v["l_mm"]) / 4.0 / float(v["w_mm3"])
    if peca == BALANCO:
        return float(v["l_mm"]) / float(v["w_mm3"])
    return 0.0


def calcular_impacto(v: Valores) -> Resultado:
    peso = float(v["peso_kN"]) * 1000.0  # N
    exigir(peso > 0, "Informe o peso do corpo que bate.")
    k, texto_k = rigidez(v)
    exigir(k > 0, "A rigidez da peça deu zero.")
    estatica = peso / k  # mm
    if str(v["modo"]) == QUEDA:
        altura = float(v["altura_mm"])
        maxima = estatica * (1.0 + math.sqrt(1.0 + 2.0 * altura / estatica))
        energia = peso * (altura + maxima) / 1000.0  # J
        formula = f"δ_máx = δ_st·(1 + √(1 + 2h/δ_st)), h = {altura:g} mm"
    else:
        velocidade = float(v["velocidade_m_s"])
        massa = peso / G  # kg
        # ½·m·v² = ½·k·δ² → δ = v·√(m/k), com k em N/m
        maxima = velocidade * math.sqrt(massa / (k * 1000.0)) * 1000.0
        energia = 0.5 * massa * velocidade**2
        formula = f"δ_máx = v·√(m/k), v = {velocidade:g} m/s, m = {massa:.1f} kg"
    forca = k * maxima  # N
    fator = forca / peso
    por_newton = tensao_por_newton(v)
    sigma_estatica = peso * por_newton
    sigma = forca * por_newton

    verificacoes = []
    if str(v["peca"]) == MOLA:
        verificacoes.append(
            limite(
                "Força máxima no apoio",
                forca / 1000.0,
                float(v["forca_adm_kN"]),
                "kN",
                f"F_máx = k·δ_máx = {k:g}·{maxima:.2f}",
                HIBBELER,
            )
        )
    else:
        sy = float(v["sy_MPa"])
        fs = float(v["fs"])
        verificacoes.append(
            limite(
                "Tensão máxima no impacto",
                sigma,
                sy / fs,
                "MPa",
                f"σ_máx = n·σ_st = {fator:.2f}·{sigma_estatica:.1f}; limite S_y/FS = {sy:g}/{fs:g}",
                HIBBELER,
            )
        )
    verificacoes.append(
        informativo("Fator de impacto n", fator, "", "n = F_máx/W = δ_máx/δ_st", HIBBELER)
    )
    verificacoes.append(informativo("Deslocamento máximo", maxima, "mm", formula, HIBBELER))

    alertas = []
    if str(v["modo"]) == QUEDA and float(v["altura_mm"]) == 0:
        alertas.append(
            "Altura zero não é carga estática: o peso solto de repente dobra o deslocamento e a "
            "tensão (n = 2)."
        )
    if str(v["peca"]) == BARRA:
        alertas.append(
            "Se o impacto comprime a barra, confira também a flambagem com a força máxima no "
            "caso Flambagem de coluna."
        )
    if fator > 20:
        alertas.append(
            f"Fator de impacto {fator:.0f}: o corpo é muito rígido para o choque. Um batente "
            "elástico ou um amortecedor baixa muito a força."
        )

    envios: list[Envio] = []
    if str(v["peca"]) == BARRA:
        envios.append(
            Envio(
                "coluna_simples",
                "Conferir a flambagem com a força do impacto",
                {"p_kN": forca / 1000.0, "l_m": float(v["l_mm"]) / 1000.0},
            )
        )
    elif str(v["peca"]) == MOLA:
        envios.append(
            Envio(
                "mola_compressao",
                "Conferir a mola helicoidal com a força do impacto",
                {"f_max_N": forca},
            )
        )
    return Resultado(
        resumo=(
            f"O impacto faz {forca / 1000.0:.2f} kN, {fator:.1f} vezes o peso, com "
            f"{maxima:.2f} mm de deslocamento."
            + (f" Tensão máxima: {sigma:.0f} MPa." if por_newton else "")
        ),
        metricas=(
            Metrica("Força máxima", forca / 1000.0, "kN", 2),
            Metrica("Fator de impacto n", fator, "", 2),
            Metrica("Deslocamento máximo", maxima, "mm", 2),
            Metrica("Deslocamento estático", estatica, "mm", 3),
            Metrica("Rigidez k", k, "N/mm", 0),
            Metrica("Energia absorvida", energia, "J", 1),
            *((Metrica("Tensão máxima", sigma, "MPa", 1),) if por_newton else ()),
        ),
        verificacoes=tuple(verificacoes),
        alertas=tuple(alertas),
        hipoteses=(
            "Toda a energia do corpo vira deformação elástica da peça: sem perda no choque e sem "
            "a massa da peça, o que deixa a força a favor da segurança.",
            f"A peça fica no regime elástico e trabalha como uma mola linear de rigidez {texto_k}.",
            "O corpo não ricocheteia antes do deslocamento máximo.",
        ),
        referencias=(HIBBELER, SHIGLEY),
        envios=tuple(envios),
    )


_SO_BARRA = ("peca", (BARRA,))
_SO_VIGA = ("peca", (BIAPOIADA, BALANCO))
_NAO_MOLA = ("peca", (BARRA, BIAPOIADA, BALANCO))

CAMPOS_IMPACTO: tuple[Campo, ...] = (
    Campo(
        "peca",
        "Peça que recebe o impacto",
        "Escolha como a peça trabalha. Para outro arranjo, informe a rigidez no ponto do choque "
        "em Mola ou apoio de rigidez conhecida.",
        BIAPOIADA,
        opcoes=PECAS,
        secao="Peça",
    ),
    Campo(
        "l_mm",
        "Comprimento L",
        "Comprimento da barra ou vão da viga.",
        2000.0,
        "mm",
        minimo=1.0,
        passo=50.0,
        secao="Peça",
        quando=_NAO_MOLA,
    ),
    Campo(
        "area_mm2",
        "Área da seção A",
        "Área da seção transversal da barra.",
        1000.0,
        "mm²",
        minimo=0.1,
        passo=50.0,
        secao="Peça",
        quando=_SO_BARRA,
    ),
    Campo(
        "i_mm4",
        "Momento de inércia I",
        "Da seção da viga, em torno do eixo da flexão. Os perfis do catálogo trazem o valor, "
        "às vezes em cm⁴ (1 cm⁴ = 10 000 mm⁴).",
        26.0e6,
        "mm⁴",
        minimo=1.0,
        passo=1e5,
        secao="Peça",
        quando=_SO_VIGA,
    ),
    Campo(
        "w_mm3",
        "Módulo resistente W",
        "Da seção da viga: I dividido pela distância da linha neutra à fibra mais longe "
        "(1 cm³ = 1000 mm³).",
        252e3,
        "mm³",
        minimo=1.0,
        passo=1e3,
        secao="Peça",
        quando=_SO_VIGA,
    ),
    Campo(
        "e_GPa",
        "Módulo de elasticidade E",
        "Aço: 200 GPa. Alumínio: 70 GPa.",
        200.0,
        "GPa",
        minimo=1.0,
        passo=5.0,
        secao="Peça",
        quando=_NAO_MOLA,
    ),
    Campo(
        "k_N_mm",
        "Rigidez no ponto do choque k",
        "Força que desloca o ponto do choque em 1 mm: mola, batente de borracha ou estrutura.",
        500.0,
        "N/mm",
        minimo=0.001,
        passo=10.0,
        secao="Peça",
        quando=("peca", (MOLA,)),
    ),
    Campo(
        "forca_adm_kN",
        "Força admissível no apoio",
        "Maior força que a mola ou o batente aceita, do catálogo ou do cálculo do apoio.",
        20.0,
        "kN",
        minimo=0.001,
        passo=1.0,
        secao="Peça",
        quando=("peca", (MOLA,)),
    ),
    Campo(
        "sy_MPa",
        "Limite de escoamento S_y",
        "ASTM A36: 250 MPa. ASTM A572 grau 50: 345 MPa.",
        250.0,
        "MPa",
        minimo=1.0,
        passo=10.0,
        secao="Peça",
        quando=_NAO_MOLA,
    ),
    Campo(
        "fs",
        "Fator de segurança",
        "Sobre o escoamento. Impacto tem incerteza grande: 1,5 a 2 é o usual.",
        1.5,
        minimo=1.0,
        maximo=10.0,
        passo=0.1,
        secao="Peça",
        quando=_NAO_MOLA,
    ),
    Campo(
        "modo",
        "Tipo de impacto",
        "Queda: o peso cai de uma altura sobre a peça. Batida: o corpo chega na horizontal com "
        "uma velocidade, como um carro no batente.",
        QUEDA,
        opcoes=MODOS,
        secao="Impacto",
    ),
    Campo(
        "peso_kN",
        "Peso do corpo W",
        "Peso de quem cai ou bate. 1 kN ≈ 102 kg.",
        2.0,
        "kN",
        minimo=0.0001,
        passo=0.5,
        secao="Impacto",
    ),
    Campo(
        "altura_mm",
        "Altura de queda h",
        "Do ponto de onde o corpo sai até encostar na peça. Zero é o peso solto de repente.",
        10.0,
        "mm",
        minimo=0.0,
        passo=10.0,
        secao="Impacto",
        quando=("modo", (QUEDA,)),
    ),
    Campo(
        "velocidade_m_s",
        "Velocidade no choque v",
        "Velocidade do corpo no instante em que encosta. 1 m/s = 3,6 km/h.",
        1.0,
        "m/s",
        minimo=0.0,
        passo=0.1,
        secao="Impacto",
        quando=("modo", (BATIDA,)),
    ),
)

CASOS: tuple[Caso, ...] = (
    Caso(
        "impacto",
        "Carga de impacto por queda ou batida",
        GRUPO,
        "Peso que cai ou corpo que bate: força máxima, fator de impacto e tensão na peça.",
        "Peso que cai sobre uma viga, carro que bate no batente, carga que pega o cabo de "
        "repente. A energia do choque vira deformação da peça: sai a força máxima, quantas vezes "
        "ela é maior que o peso e a tensão que ela causa.",
        CAMPOS_IMPACTO,
        calcular_impacto,
        r"\delta_{max}=\delta_{st}\left(1+\sqrt{1+\frac{2h}{\delta_{st}}}\right),\quad "
        r"F_{max}=k\,\delta_{max},\quad \sigma_{max}=\frac{F_{max}}{W}\,\sigma_{st}",
    ),
)
