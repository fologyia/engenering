"""Peças, seções e chapas: equilíbrio de corpo rígido, seção montada e chapa tracionada com furo."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from core.desenho_estatica import figura_da_secao, figura_do_equilibrio
from core.elementos_base import (
    Campo,
    Caso,
    Coluna,
    Envio,
    Figura,
    Metrica,
    Resultado,
    Tabela,
    Valores,
    exigir,
    informativo,
    limite,
)
from core.elementos_vigas import INFORMAR

GRUPO = "Peças, seções e chapas"

HIBBELER = "Hibbeler, Estática"
HIBBELER_RM = "Hibbeler, Resistência dos Materiais"
PILKEY = "Pilkey, Peterson's Stress Concentration Factors, Chart 4.1"
SHIGLEY_3 = "Shigley, Elementos de Máquinas, cap. 3"


# ---------------------------------------------------------------------------
# Equilíbrio de uma peça
# ---------------------------------------------------------------------------

PINO_E_ROLETE = "Pino em A e rolete em B"
ENGASTE = "Engaste em A"
ROLETE_Y = "Rolete segura na vertical"
ROLETE_X = "Rolete segura na horizontal"


def calcular_equilibrio(v: Valores) -> Resultado:
    cargas: Sequence[Mapping[str, Any]] = v["cargas"]
    exigir(len(cargas) >= 1, "Informe ao menos uma carga na tabela.")
    xa, ya = float(v["xa_m"]), float(v["ya_m"])
    forcas = [
        (
            float(c["x_m"]),
            float(c["y_m"]),
            float(c["fx_kN"]),
            float(c["fy_kN"]),
            float(c["m_kNm"]),
        )
        for c in cargas
    ]
    soma_fx = sum(f[2] for f in forcas)
    soma_fy = sum(f[3] for f in forcas)
    # Momento em torno de A, anti-horário positivo.
    momento_a = sum((x - xa) * fy - (y - ya) * fx + m for x, y, fx, fy, m in forcas)

    reacoes: list[tuple[str, float, float, float, float]] = []
    linhas: list[dict[str, object]] = []
    momento_engaste = 0.0
    if v["apoios"] == ENGASTE:
        ax, ay = -soma_fx, -soma_fy
        momento_engaste = -momento_a
        reacoes.append(("A", xa, ya, ax, ay))
        linhas.append(
            {"Apoio": "A", "Rx (kN)": ax, "Ry (kN)": ay, "Momento (kN·m)": momento_engaste}
        )
        metricas = [
            Metrica("Reação Ax", ax, "kN"),
            Metrica("Reação Ay", ay, "kN"),
            Metrica("Momento no engaste", momento_engaste, "kN·m"),
        ]
    else:
        xb, yb = float(v["xb_m"]), float(v["yb_m"])
        if v["rolete"] == ROLETE_Y:
            exigir(
                abs(xb - xa) > 1e-9,
                "Com o rolete que segura na vertical, A e B não podem estar na mesma vertical: a "
                "peça giraria em torno de A.",
            )
            bx, by = 0.0, -momento_a / (xb - xa)
        else:
            exigir(
                abs(yb - ya) > 1e-9,
                "Com o rolete que segura na horizontal, A e B não podem estar na mesma horizontal: "
                "a peça giraria em torno de A.",
            )
            bx, by = momento_a / (yb - ya), 0.0
        ax, ay = -soma_fx - bx, -soma_fy - by
        reacoes.extend([("A", xa, ya, ax, ay), ("B", xb, yb, bx, by)])
        linhas.append({"Apoio": "A", "Rx (kN)": ax, "Ry (kN)": ay, "Momento (kN·m)": 0.0})
        linhas.append({"Apoio": "B", "Rx (kN)": bx, "Ry (kN)": by, "Momento (kN·m)": 0.0})
        metricas = [
            Metrica("Reação Ax", ax, "kN"),
            Metrica("Reação Ay", ay, "kN"),
            Metrica("Reação em B", math.hypot(bx, by), "kN"),
        ]
    resultante = math.hypot(soma_fx, soma_fy)
    metricas.append(Metrica("Resultante das cargas", resultante, "kN"))

    residuo_f = math.hypot(
        soma_fx + sum(r[3] for r in reacoes), soma_fy + sum(r[4] for r in reacoes)
    )
    residuo_m = abs(
        momento_a + momento_engaste + sum((r[1] - xa) * r[4] - (r[2] - ya) * r[3] for r in reacoes)
    )
    figura = figura_do_equilibrio(
        [(x, y, fx, fy) for x, y, fx, fy, _ in forcas],
        [(x, y, m) for x, y, _, _, m in forcas if abs(m) > 1e-12],
        reacoes,
    )
    maior = max(reacoes, key=lambda r: math.hypot(r[3], r[4]))
    return Resultado(
        resumo=(
            f"Maior reação de {math.hypot(maior[3], maior[4]):.2f} kN no apoio {maior[0]}. "
            f"Resultante das cargas: {resultante:.2f} kN."
        ),
        metricas=tuple(metricas),
        verificacoes=(
            informativo(
                "Soma das forças com as reações",
                round(residuo_f, 6),
                "kN",
                "ΣF = 0: deve dar zero",
                HIBBELER,
            ),
            informativo(
                "Soma dos momentos com as reações",
                round(residuo_m, 6),
                "kN·m",
                "ΣM = 0: deve dar zero",
                HIBBELER,
            ),
        ),
        tabelas=(
            Tabela(
                "Reações nos apoios",
                tuple(linhas),
                "Rx para a direita, Ry para cima e momento anti-horário.",
            ),
        ),
        figuras=(Figura("Peça", figura.png, "Cargas em laranja e reações em verde."),),
        hipoteses=(
            "Corpo rígido no plano: a deformação da peça não muda a posição das cargas.",
            "Pino segura as duas direções e deixa girar. Rolete segura uma direção. Engaste segura "
            "tudo.",
            "Atrito nos apoios desprezado.",
        ),
        referencias=(HIBBELER,),
    )


CAMPOS_EQUILIBRIO: tuple[Campo, ...] = (
    Campo(
        "apoios",
        "Como a peça está apoiada",
        "Pino e rolete é o caso geral com duas reações. Engaste é a peça presa em um só ponto, "
        "como um suporte soldado.",
        PINO_E_ROLETE,
        opcoes=(PINO_E_ROLETE, ENGASTE),
        secao="Apoios",
    ),
    Campo(
        "xa_m",
        "Posição x do apoio A",
        "Coordenada horizontal do apoio A.",
        0.0,
        "m",
        passo=0.1,
        secao="Apoios",
    ),
    Campo(
        "ya_m",
        "Posição y do apoio A",
        "Coordenada vertical do apoio A.",
        0.0,
        "m",
        passo=0.1,
        secao="Apoios",
    ),
    Campo(
        "xb_m",
        "Posição x do apoio B",
        "Coordenada horizontal do apoio B.",
        3.0,
        "m",
        passo=0.1,
        secao="Apoios",
        quando=("apoios", (PINO_E_ROLETE,)),
    ),
    Campo(
        "yb_m",
        "Posição y do apoio B",
        "Coordenada vertical do apoio B.",
        0.0,
        "m",
        passo=0.1,
        secao="Apoios",
        quando=("apoios", (PINO_E_ROLETE,)),
    ),
    Campo(
        "rolete",
        "Direção do rolete",
        "O rolete só faz força nesta direção.",
        ROLETE_Y,
        opcoes=(ROLETE_Y, ROLETE_X),
        secao="Apoios",
        quando=("apoios", (PINO_E_ROLETE,)),
    ),
    Campo(
        "cargas",
        "Cargas",
        "Uma linha por carga, com o ponto de aplicação. Fx positiva para a direita, Fy para cima e "
        "momento anti-horário.",
        (
            {"x_m": 1.0, "y_m": 0.5, "fx_kN": 0.0, "fy_kN": -10.0, "m_kNm": 0.0},
            {"x_m": 2.0, "y_m": 0.5, "fx_kN": 4.0, "fy_kN": -6.0, "m_kNm": 0.0},
        ),
        secao="Cargas",
        colunas=(
            Coluna("x_m", "x", "Coordenada horizontal do ponto da carga.", 0.0, "m"),
            Coluna("y_m", "y", "Coordenada vertical do ponto da carga.", 0.0, "m"),
            Coluna("fx_kN", "Fx", "Componente horizontal da força.", 0.0, "kN"),
            Coluna("fy_kN", "Fy", "Componente vertical da força.", 0.0, "kN"),
            Coluna("m_kNm", "Momento", "Momento aplicado neste ponto.", 0.0, "kN·m"),
        ),
    ),
)


# ---------------------------------------------------------------------------
# Seção montada
# ---------------------------------------------------------------------------

CHEIO = "Cheio"
FURO = "Furo"
RETANGULO = "Retângulo"
CIRCULO = "Círculo"


def calcular_secao(v: Valores) -> Resultado:
    partes: Sequence[Mapping[str, Any]] = v["partes"]
    exigir(len(partes) >= 1, "Informe ao menos uma parte da seção.")
    densidade = float(v["densidade_kg_m3"])
    area_total = soma_ax = soma_ay = 0.0
    dados: list[tuple[float, float, float, float, float, float, float]] = []
    for numero, parte in enumerate(partes, start=1):
        forma = parte["forma"]
        b = float(parte["b_mm"])
        h = b if forma == CIRCULO or parte["h_mm"] is None else float(parte["h_mm"])
        x, y = float(parte["x_mm"]), float(parte["y_mm"])
        sinal = -1.0 if parte["tipo"] == FURO else 1.0
        if forma == CIRCULO:
            area = math.pi * b**2 / 4.0
            ix = iy = math.pi * b**4 / 64.0
        else:
            area = b * h
            ix, iy = b * h**3 / 12.0, h * b**3 / 12.0
        exigir(area > 0.0, f"Parte {numero}: a área precisa ser positiva.")
        area_total += sinal * area
        soma_ax += sinal * area * x
        soma_ay += sinal * area * y
        dados.append((sinal, area, ix, iy, x, y, b))
    exigir(area_total > 1e-9, "Os furos tiraram mais área do que as partes cheias têm.")
    xc, yc = soma_ax / area_total, soma_ay / area_total
    ix = sum(s * (i + a * (y - yc) ** 2) for s, a, i, _, _, y, _ in dados)
    iy = sum(s * (j + a * (x - xc) ** 2) for s, a, _, j, x, _, _ in dados)
    ixy = sum(s * a * (x - xc) * (y - yc) for s, a, _, _, x, y, _ in dados)
    exigir(ix > 0.0 and iy > 0.0, "A seção resultou em inércia nula: confira as partes.")
    media = (ix + iy) / 2.0
    raio = math.hypot((ix - iy) / 2.0, ixy)
    i_1, i_2 = media + raio, media - raio
    angulo = 0.5 * math.degrees(math.atan2(-2.0 * ixy, ix - iy))

    cheias = [
        (
            float(p["x_mm"]),
            float(p["y_mm"]),
            float(p["b_mm"]),
            float(p["b_mm"]) if p["forma"] == CIRCULO or p["h_mm"] is None else float(p["h_mm"]),
        )
        for p in partes
        if p["tipo"] == CHEIO
    ]
    exigir(bool(cheias), "A seção precisa de ao menos uma parte cheia.")
    y_max = max(y + h / 2.0 for _, y, _, h in cheias)
    y_min = min(y - h / 2.0 for _, y, _, h in cheias)
    x_max = max(x + b / 2.0 for x, _, b, _ in cheias)
    x_min = min(x - b / 2.0 for x, _, b, _ in cheias)
    w_sup = ix / (y_max - yc)
    w_inf = ix / (yc - y_min)
    w_x = min(w_sup, w_inf)
    w_y = iy / max(x_max - xc, xc - x_min)
    r_min = math.sqrt(min(ix, iy) / area_total)
    massa = area_total * 1e-6 * densidade

    desenho = [
        (
            float(p["b_mm"]),
            float(p["b_mm"]) if p["forma"] == CIRCULO or p["h_mm"] is None else float(p["h_mm"]),
            float(p["x_mm"]),
            float(p["y_mm"]),
            p["tipo"] == FURO,
            p["forma"] == CIRCULO,
        )
        for p in partes
    ]
    figura = figura_da_secao(desenho, (xc, yc))
    linhas = (
        {"Grandeza": "Área A", "Valor": area_total, "Unidade": "mm²"},
        {"Grandeza": "Centro de gravidade x", "Valor": xc, "Unidade": "mm"},
        {"Grandeza": "Centro de gravidade y", "Valor": yc, "Unidade": "mm"},
        {"Grandeza": "Inércia Ix", "Valor": ix, "Unidade": "mm⁴"},
        {"Grandeza": "Inércia Iy", "Valor": iy, "Unidade": "mm⁴"},
        {"Grandeza": "Produto de inércia Ixy", "Valor": ixy, "Unidade": "mm⁴"},
        {"Grandeza": "Inércia principal maior", "Valor": i_1, "Unidade": "mm⁴"},
        {"Grandeza": "Inércia principal menor", "Valor": i_2, "Unidade": "mm⁴"},
        {"Grandeza": "Ângulo do eixo principal", "Valor": angulo, "Unidade": "°"},
        {"Grandeza": "W superior (em x)", "Valor": w_sup, "Unidade": "mm³"},
        {"Grandeza": "W inferior (em x)", "Valor": w_inf, "Unidade": "mm³"},
        {"Grandeza": "W em y", "Valor": w_y, "Unidade": "mm³"},
        {"Grandeza": "Raio de giração mínimo", "Valor": r_min, "Unidade": "mm"},
        {"Grandeza": "Massa por metro", "Valor": massa, "Unidade": "kg/m"},
    )
    alertas: list[str] = []
    if abs(ixy) > 0.02 * math.sqrt(ix * iy):
        alertas.append(
            "A seção não tem eixo de simetria alinhado com x e y: os eixos principais estão "
            f"girados de {angulo:.1f}°, e a carga em y gera flexão oblíqua."
        )
    valores_envio: dict[str, float | int | str | bool] = {
        "tipo_secao": INFORMAR,
        "a_mm2": area_total,
        "i_mm4": ix,
        "w_mm3": w_x,
    }
    return Resultado(
        resumo=(
            f"Área de {area_total:.0f} mm², Ix de {ix / 1e4:.0f} cm⁴ e W de {w_x / 1e3:.1f} cm³, "
            f"com o centro de gravidade em y = {yc:.1f} mm."
        ),
        metricas=(
            Metrica("Área", area_total, "mm²", 0),
            Metrica("Ix", ix / 1e4, "cm⁴", 1),
            Metrica("Iy", iy / 1e4, "cm⁴", 1),
            Metrica("Menor W em x", w_x / 1e3, "cm³", 1),
            Metrica("Massa", massa, "kg/m"),
        ),
        tabelas=(Tabela("Propriedades da seção", linhas),),
        figuras=(Figura("Seção", figura.png, "Seção em escala, com o centro de gravidade."),),
        alertas=tuple(alertas),
        hipoteses=(
            "Partes de mesmo material, ligadas entre si: a seção trabalha como uma peça só. Isso "
            "pede solda ou parafusos que passem o cortante entre as partes.",
            "Furo tira a área de dentro de uma parte cheia, e não pode ficar fora dela.",
            "Partes cheias não se sobrepõem: se duas se cruzam, a área comum conta duas vezes.",
        ),
        referencias=(HIBBELER_RM,),
        envios=(
            Envio("viga_reacoes", "Usar esta seção numa viga", valores_envio),
            Envio("coluna_simples", "Usar esta seção numa coluna", valores_envio),
        ),
    )


CAMPOS_SECAO: tuple[Campo, ...] = (
    Campo(
        "partes",
        "Partes da seção",
        "Some retângulos e círculos, e tire furos. x e y são o centro da parte, com a origem onde "
        "for mais fácil. No círculo, a largura é o diâmetro.",
        (
            {
                "tipo": CHEIO,
                "forma": RETANGULO,
                "b_mm": 200.0,
                "h_mm": 16.0,
                "x_mm": 0.0,
                "y_mm": 208.0,
            },
            {
                "tipo": CHEIO,
                "forma": RETANGULO,
                "b_mm": 8.0,
                "h_mm": 200.0,
                "x_mm": 0.0,
                "y_mm": 100.0,
            },
            {
                "tipo": CHEIO,
                "forma": RETANGULO,
                "b_mm": 120.0,
                "h_mm": 12.0,
                "x_mm": 0.0,
                "y_mm": -6.0,
            },
        ),
        secao="Seção",
        colunas=(
            Coluna("tipo", "Tipo", "Cheio soma e furo subtrai.", CHEIO, opcoes=(CHEIO, FURO)),
            Coluna(
                "forma",
                "Forma",
                "Retângulo ou círculo.",
                RETANGULO,
                opcoes=(RETANGULO, CIRCULO),
            ),
            Coluna(
                "b_mm",
                "b ou Ø",
                "Largura na direção x. No círculo, é o diâmetro.",
                100.0,
                "mm",
                minimo=0.01,
            ),
            Coluna(
                "h_mm",
                "h",
                "Altura na direção y. No círculo, fica vazia.",
                10.0,
                "mm",
                minimo=0.01,
                opcional=True,
            ),
            Coluna("x_mm", "x", "Posição do centro da parte em x.", 0.0, "mm"),
            Coluna("y_mm", "y", "Posição do centro da parte em y.", 0.0, "mm"),
        ),
    ),
    Campo(
        "densidade_kg_m3",
        "Densidade do material",
        "Para a massa por metro. Aço: 7 850 kg/m³.",
        7850.0,
        "kg/m³",
        minimo=1.0,
        passo=50.0,
        secao="Material",
    ),
)


# ---------------------------------------------------------------------------
# Chapa tracionada com furo
# ---------------------------------------------------------------------------


def fator_kt_furo(d_sobre_b: float) -> float:
    """K_t da chapa com furo central sob tração, na tensão da seção líquida (Pilkey, Chart 4.1)."""
    resto = 1.0 - d_sobre_b
    return 2.0 + 0.284 * resto - 0.600 * resto**2 + 1.32 * resto**3


def calcular_chapa(v: Valores) -> Resultado:
    b = float(v["b_mm"])
    t = float(v["t_mm"])
    d = float(v["d_mm"])
    n = int(v["n"])
    forca = float(v["f_kN"]) * 1000.0
    sy = float(v["sy_MPa"])
    su = float(v["sut_MPa"])
    fs = float(v["fs"])
    exigir(n * d < b, "Os furos somados precisam ser menores que a largura da chapa.")
    exigir(su >= sy, "A ruptura não pode ser menor que o escoamento.")
    bruta = b * t
    liquida = (b - n * d) * t
    sigma_bruta = forca / bruta
    sigma_liquida = forca / liquida
    faixa = b / n
    kt = fator_kt_furo(d / faixa)
    pico = kt * sigma_liquida
    capacidade = min(sy * bruta, su * liquida) / fs
    alertas: list[str] = []
    if pico > sy:
        alertas.append(
            f"O pico na borda do furo ({pico:.0f} MPa) passa do escoamento. Em material dúctil "
            "sob carga estática isso é aceito, porque a tensão se redistribui. Em carga repetida "
            "ou material frágil, não: use a Análise de fadiga."
        )
    return Resultado(
        resumo=(
            f"A chapa aguenta {capacidade / 1000:.1f} kN com FS = {fs:.2f}. Tensão de "
            f"{sigma_bruta:.1f} MPa na seção bruta e {sigma_liquida:.1f} MPa na seção do furo."
        ),
        metricas=(
            Metrica("A chapa aguenta", capacidade / 1000.0, "kN", 1),
            Metrica("Tensão na seção bruta", sigma_bruta, "MPa", 1),
            Metrica("Tensão na seção do furo", sigma_liquida, "MPa", 1),
            Metrica("Fator Kt", kt, "", 2),
            Metrica("Pico no furo", pico, "MPa", 0),
        ),
        verificacoes=(
            limite(
                "Escoamento da seção bruta",
                sigma_bruta,
                sy / fs,
                "MPa",
                f"σ = F/(b·t); limite S_y/FS = {sy:.0f}/{fs:.2f}",
                SHIGLEY_3,
            ),
            limite(
                "Ruptura da seção com furos",
                sigma_liquida,
                su / fs,
                "MPa",
                f"σ = F/((b − n·d)·t); limite S_u/FS = {su:.0f}/{fs:.2f}",
                SHIGLEY_3,
            ),
            informativo(
                "Pico de tensão na borda do furo",
                pico,
                "MPa",
                f"σ_max = K_t·σ_liq, K_t = {kt:.2f}",
                PILKEY,
            ),
        ),
        alertas=tuple(alertas),
        hipoteses=(
            "Chapa plana sob tração uniforme, com os furos na mesma seção transversal.",
            "Com vários furos, cada um fica no centro de uma faixa de largura b/n.",
            "Sob carga estática, em material dúctil, vale a tensão média da seção: o pico do furo "
            "só governa em fadiga ou em material frágil.",
            "O esmagamento pelo parafuso e o rasgamento da borda são da página Ligações "
            "estruturais.",
        ),
        referencias=(SHIGLEY_3, PILKEY),
    )


CAMPOS_CHAPA: tuple[Campo, ...] = (
    Campo(
        "b_mm",
        "Largura da chapa",
        "Largura total, perpendicular à força.",
        100.0,
        "mm",
        minimo=0.1,
        passo=5.0,
        secao="Chapa",
    ),
    Campo(
        "t_mm",
        "Espessura",
        "Espessura da chapa.",
        10.0,
        "mm",
        minimo=0.1,
        passo=1.0,
        secao="Chapa",
    ),
    Campo(
        "d_mm",
        "Diâmetro do furo",
        "Diâmetro real do furo, com a folga em relação ao parafuso.",
        18.0,
        "mm",
        minimo=0.1,
        passo=1.0,
        secao="Chapa",
    ),
    Campo(
        "n",
        "Furos na mesma seção",
        "Quantidade de furos na linha transversal à força.",
        1,
        minimo=1,
        maximo=20,
        passo=1,
        secao="Chapa",
    ),
    Campo(
        "f_kN",
        "Força de tração",
        "Força total na chapa.",
        80.0,
        "kN",
        minimo=0.0,
        passo=5.0,
        secao="Carga e material",
    ),
    Campo(
        "sy_MPa",
        "Escoamento",
        "ASTM A36: 250 MPa.",
        250.0,
        "MPa",
        minimo=1.0,
        passo=10.0,
        secao="Carga e material",
    ),
    Campo(
        "sut_MPa",
        "Ruptura",
        "ASTM A36: 400 MPa.",
        400.0,
        "MPa",
        minimo=1.0,
        passo=10.0,
        secao="Carga e material",
    ),
    Campo(
        "fs",
        "Fator de segurança",
        "Vale para o escoamento e para a ruptura. Comece com 1,5.",
        1.5,
        minimo=1.0,
        maximo=6.0,
        passo=0.1,
        secao="Carga e material",
    ),
)

CASOS: tuple[Caso, ...] = (
    Caso(
        "equilibrio_peca",
        "Equilíbrio de uma peça",
        GRUPO,
        "Reações de uma peça qualquer, com forças em qualquer direção.",
        "Peça, suporte ou alavanca sobre dois apoios ou presa em um engaste. Sai a força em cada "
        "apoio.",
        CAMPOS_EQUILIBRIO,
        calcular_equilibrio,
        r"\sum F_x=0,\quad \sum F_y=0,\quad \sum M_A=0",
    ),
    Caso(
        "secao_montada",
        "Seção montada",
        GRUPO,
        "Área, centro de gravidade, inércia e W de uma seção feita de partes.",
        "Some chapas e barras, tire furos e veja as propriedades. O resultado pode seguir para "
        "uma viga ou para uma coluna.",
        CAMPOS_SECAO,
        calcular_secao,
        r"\bar y=\frac{\sum A_i y_i}{\sum A_i},\quad I_x=\sum\left(I_i+A_i d_i^2\right)",
    ),
    Caso(
        "chapa_furo",
        "Chapa tracionada com furo",
        GRUPO,
        "Seção bruta, seção com furos e o pico de tensão na borda.",
        "Barra chata ou chapa com furos na mesma seção. Diz quanto ela aguenta e o tamanho do pico "
        "de tensão no furo.",
        CAMPOS_CHAPA,
        calcular_chapa,
        r"\sigma=\frac{F}{(b-n\,d)\,t},\quad \sigma_{max}=K_t\,\sigma",
    ),
)
