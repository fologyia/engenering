"""Solda de filete sob carga excêntrica: o cordão tratado como linha, sem Streamlit.

O método é o de Shigley (cap. 9) e o elástico do AISC: cada cordão vira uma linha de espessura
unitária, as propriedades do conjunto saem por integração exata de cada trecho reto, e a força por
milímetro de cordão num ponto é a soma vetorial de três partes:

* no plano da junta: o cortante dividido pelo comprimento e o torque pela distância ao centroide
  (f = V/L + T·r/J_u);
* fora do plano: a força normal e os momentos, pela flexão de uma seção feita de linhas
  (f = N/L + a·y + b·x, com a e b tirados de I_ux, I_uy e I_uxy, o que vale também para o
  cordão em L, cujos eixos não são principais).

Como as três componentes variam em linha reta ao longo de cada trecho, a maior resultante fica sempre
numa ponta de trecho, e só as pontas precisam ser conferidas.

A resistência vem da norma escolhida, com as mesmas regras das Ligações soldadas
(:mod:`core.soldas`): NBR 8800 com cargas de cálculo ou AISC 360 em tensões admissíveis (ASD) com
cargas de serviço. Para a ligação estrutural completa, com chapa de nó e cantoneiras, o caminho é
a página Ligações soldadas.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from core import soldas as sd
from core.desenho_estatica import figura_dos_cordoes
from core.elementos_base import (
    Campo,
    Caso,
    Coluna,
    Figura,
    Metrica,
    Resultado,
    Tabela,
    Valores,
    exigir,
    informativo,
    limite,
)

GRUPO = "Pinos, chapas e soldas"

UM_VERTICAL = "Um cordão vertical"
DOIS_VERTICAIS = "Dois cordões verticais"
DOIS_HORIZONTAIS = "Dois cordões horizontais"
EM_L = "Em L"
EM_C = "Em C (três lados)"
RETANGULO = "Contorno retangular"
ANEL = "Anel em volta de tubo ou eixo"
LIVRE = "Cordões livres (tabela)"
PADROES = (UM_VERTICAL, DOIS_VERTICAIS, DOIS_HORIZONTAIS, EM_L, EM_C, RETANGULO, ANEL, LIVRE)

NBR = "NBR 8800 (cargas de cálculo)"
ASD = "AISC 360 ASD (cargas de serviço)"
CRITERIOS = (NBR, ASD)

SHIGLEY_9 = "Budynas e Nisbett, Elementos de Máquinas de Shigley, cap. 9 (solda como linha)"
AISC_J2 = "AISC 360-16, J2.4 e Tabela J2.5 (ASD, Ω = 2,00)"
AISC_J4 = "AISC 360-16, J4.2 (ASD: Ω = 1,50 no escoamento e 2,00 na ruptura)"

#: Trechos retos do anel: com 72 cordas, J_u fica a 0,1 % do círculo exato.
CORDAS_DO_ANEL = 72


@dataclass(frozen=True)
class Trecho:
    """Um cordão reto, em mm."""

    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def comprimento(self) -> float:
        return math.hypot(self.x2 - self.x1, self.y2 - self.y1)


@dataclass(frozen=True)
class PropriedadesDaLinha:
    """Propriedades do conjunto de cordões por unidade de garganta (mm, mm³)."""

    comprimento: float
    xc: float
    yc: float
    i_ux: float
    i_uy: float
    i_uxy: float

    @property
    def j_u(self) -> float:
        return self.i_ux + self.i_uy


def trechos_do_padrao(v: Valores) -> list[Trecho]:
    """Os cordões do desenho escolhido; a origem é o canto de baixo à esquerda."""
    padrao = str(v["padrao"])
    b = float(v["b_mm"])
    d = float(v["d_mm"])
    if padrao == UM_VERTICAL:
        return [Trecho(0.0, 0.0, 0.0, d)]
    if padrao == DOIS_VERTICAIS:
        return [Trecho(0.0, 0.0, 0.0, d), Trecho(b, 0.0, b, d)]
    if padrao == DOIS_HORIZONTAIS:
        return [Trecho(0.0, 0.0, b, 0.0), Trecho(0.0, d, b, d)]
    if padrao == EM_L:
        return [Trecho(0.0, 0.0, b, 0.0), Trecho(0.0, 0.0, 0.0, d)]
    if padrao == EM_C:
        return [Trecho(0.0, d, b, d), Trecho(0.0, 0.0, 0.0, d), Trecho(0.0, 0.0, b, 0.0)]
    if padrao == RETANGULO:
        return [
            Trecho(0.0, 0.0, b, 0.0),
            Trecho(b, 0.0, b, d),
            Trecho(b, d, 0.0, d),
            Trecho(0.0, d, 0.0, 0.0),
        ]
    if padrao == ANEL:
        raio = float(v["d_anel_mm"]) / 2.0
        angulos = [2.0 * math.pi * i / CORDAS_DO_ANEL for i in range(CORDAS_DO_ANEL + 1)]
        pontos = [(raio * math.cos(a), raio * math.sin(a)) for a in angulos]
        return [Trecho(*pontos[i], *pontos[i + 1]) for i in range(CORDAS_DO_ANEL)]
    trechos = [
        Trecho(float(t["x1_mm"]), float(t["y1_mm"]), float(t["x2_mm"]), float(t["y2_mm"]))
        for t in v["cordoes"]
    ]
    exigir(len(trechos) >= 1, "Informe ao menos um cordão na tabela.")
    for i, trecho in enumerate(trechos, start=1):
        exigir(trecho.comprimento > 0.5, f"Cordão {i}: o início e o fim estão no mesmo ponto.")
    return trechos


def propriedades(trechos: Sequence[Trecho]) -> PropriedadesDaLinha:
    """Comprimento, centroide e momentos de inércia de linha, exatos para trechos retos."""
    total = sum(t.comprimento for t in trechos)
    exigir(total > 0, "Os cordões não têm comprimento.")
    xc = sum(t.comprimento * (t.x1 + t.x2) / 2.0 for t in trechos) / total
    yc = sum(t.comprimento * (t.y1 + t.y2) / 2.0 for t in trechos) / total
    i_ux = i_uy = i_uxy = 0.0
    for t in trechos:
        xa, ya, xb, yb = t.x1 - xc, t.y1 - yc, t.x2 - xc, t.y2 - yc
        comprimento = t.comprimento
        i_ux += comprimento * (ya * ya + ya * yb + yb * yb) / 3.0
        i_uy += comprimento * (xa * xa + xa * xb + xb * xb) / 3.0
        i_uxy += comprimento * (2 * xa * ya + xa * yb + xb * ya + 2 * xb * yb) / 6.0
    return PropriedadesDaLinha(total, xc, yc, i_ux, i_uy, i_uxy)


def _coeficientes_da_flexao(
    prop: PropriedadesDaLinha, trechos: Sequence[Trecho], mx: float, my: float
) -> tuple[float, float]:
    """(a, b) de f = a·y + b·x, com ∫f·y = Mx e ∫f·x = My (N·mm em N/mm)."""
    if abs(mx) < 1e-9 and abs(my) < 1e-9:
        return 0.0, 0.0
    escala = max(prop.i_ux + prop.i_uy, 1e-9)
    det = prop.i_ux * prop.i_uy - prop.i_uxy**2
    if det > 1e-9 * escala * escala:
        a = (mx * prop.i_uy - my * prop.i_uxy) / det
        b = (my * prop.i_ux - mx * prop.i_uxy) / det
        return a, b
    # Todos os cordões numa reta só: ela resiste ao momento que a dobra, nunca ao que gira em
    # torno dela.
    maior = max(trechos, key=lambda t: t.comprimento)
    ux = (maior.x2 - maior.x1) / maior.comprimento
    uy = (maior.y2 - maior.y1) / maior.comprimento
    i_s = prop.i_ux + prop.i_uy
    exigir(
        abs(mx * ux - my * uy) <= 1e-6 * (abs(mx) + abs(my)),
        "Com os cordões numa reta só, a solda não resiste ao momento em torno da própria linha: "
        "acrescente um cordão fora dela ou zere esse momento.",
    )
    k = (mx * uy + my * ux) / i_s
    return k * uy, k * ux


@dataclass(frozen=True)
class ForcaNoPonto:
    nome: str
    x: float
    y: float
    no_plano: float  # N/mm
    fora_do_plano: float  # N/mm, positiva puxa a solda
    resultante: float  # N/mm


def forcas_nas_pontas(
    trechos: Sequence[Trecho],
    prop: PropriedadesDaLinha,
    n: float,
    mx: float,
    my: float,
    vx: float,
    vy: float,
    t: float,
) -> list[ForcaNoPonto]:
    """Força por mm de cordão em cada ponta de trecho (N, N·mm → N/mm)."""
    exigir(
        abs(t) < 1e-9 or prop.j_u > 1e-9,
        "Os cordões não resistem ao torque no plano da junta.",
    )
    a, b = _coeficientes_da_flexao(prop, trechos, mx, my)
    vistos: dict[tuple[float, float], str] = {}
    for i, trecho in enumerate(trechos, start=1):
        for x, y, ponta in ((trecho.x1, trecho.y1, "início"), (trecho.x2, trecho.y2, "fim")):
            chave = (round(x, 6), round(y, 6))
            vistos.setdefault(chave, f"Cordão {i}, {ponta}")
    forcas = []
    for (x, y), nome in vistos.items():
        rx, ry = x - prop.xc, y - prop.yc
        fx = vx / prop.comprimento
        fy = vy / prop.comprimento
        if prop.j_u > 1e-9:
            fx -= t * ry / prop.j_u
            fy += t * rx / prop.j_u
        fz = n / prop.comprimento + a * ry + b * rx
        no_plano = math.hypot(fx, fy)
        forcas.append(ForcaNoPonto(nome, x, y, no_plano, fz, math.hypot(no_plano, fz)))
    return forcas


def _resistencias(
    v: Valores, perna: float, t_chapa: float
) -> tuple[float, float, str, str, str, str]:
    """(solda, metal-base) em N/mm, com as fórmulas e as referências."""
    fw = sd.ELETRODOS[str(v["eletrodo"])]
    fy = float(v["sy_MPa"])
    fu = float(v["sut_MPa"])
    garganta = sd.GARGANTA_DO_FILETE * perna
    if str(v["criterio"]) == NBR:
        c = sd.coeficientes(sd.COMBINACAO_NORMAL)
        solda = sd.resistencia_filete_por_mm(perna, fw, c.w2) * 1000.0
        base, texto_base = sd.metal_base_ao_cisalhamento_por_mm(t_chapa, fy, fu, c)
        norma = sd.NBR_2025
        return (
            solda,
            base * 1000.0,
            f"0,60·f_w·(0,707·perna)/γ_w2 = 0,60·{fw:.0f}·{garganta:.2f}/{c.w2:g}",
            sd.ref(norma, f"6.2.5, {sd.tabela(norma, 'resistencia')}", vista_na_2025=True),
            f"{texto_base}, t = {t_chapa:g} mm",
            sd.ref(norma, "6.5.5"),
        )
    escoamento = 0.40 * fy * t_chapa
    ruptura = 0.30 * fu * t_chapa
    texto = (
        f"0,60·S_y·t/1,50 = 0,40·{fy:.0f}·{t_chapa:g}"
        if escoamento <= ruptura
        else f"0,60·S_ut·t/2,00 = 0,30·{fu:.0f}·{t_chapa:g}"
    )
    return (
        0.30 * fw * garganta,
        min(escoamento, ruptura),
        f"0,60·F_EXX·(0,707·perna)/2,00 = 0,30·{fw:.0f}·{garganta:.2f}",
        AISC_J2,
        texto,
        AISC_J4,
    )


def calcular_solda(v: Valores) -> Resultado:
    trechos = trechos_do_padrao(v)
    prop = propriedades(trechos)
    perna = float(v["perna_mm"])
    t_chapa = float(v["t_mm"])
    forcas = forcas_nas_pontas(
        trechos,
        prop,
        float(v["n_kN"]) * 1000.0,
        float(v["mx_kNm"]) * 1e6,
        float(v["my_kNm"]) * 1e6,
        float(v["vx_kN"]) * 1000.0,
        float(v["vy_kN"]) * 1000.0,
        float(v["t_kNm"]) * 1e6,
    )
    critico = max(forcas, key=lambda f: f.resultante)
    maior_no_plano = max(forcas, key=lambda f: f.no_plano)
    exigir(critico.resultante > 0, "Informe ao menos uma força ou um momento.")

    menor_cordao = min(t.comprimento for t in trechos)
    if str(v["padrao"]) == ANEL:
        menor_cordao = prop.comprimento  # o anel é um cordão só, sem pontas
    perna_calculo = sd.perna_considerada(perna, menor_cordao)
    solda, base, texto_solda, ref_solda, texto_base, ref_base = _resistencias(
        v, perna_calculo, t_chapa
    )
    garganta = sd.GARGANTA_DO_FILETE * perna_calculo
    tau = critico.resultante / garganta

    verificacoes = [
        limite(
            "Metal da solda no ponto mais carregado",
            critico.resultante,
            solda,
            "N/mm",
            f"{texto_solda}; ponto: {critico.nome}",
            ref_solda,
        ),
        limite(
            "Metal-base junto à solda (cisalhamento)",
            maior_no_plano.no_plano,
            base,
            "N/mm",
            f"parcela no plano da junta, {maior_no_plano.nome}; {texto_base}",
            ref_base,
        ),
        *sd.limites_do_filete(
            sd.NBR_2025,
            perna,
            t_chapa,
            t_chapa if bool(v["na_borda"]) else None,
            menor_cordao,
            nome_do_comprimento="comprimento do menor cordão",
        ),
        informativo(
            "Tensão na garganta, ponto mais carregado",
            tau,
            "MPa",
            f"τ = f/(0,707·perna) = {critico.resultante:.0f}/{garganta:.2f}",
            SHIGLEY_9,
        ),
    ]
    alertas = []
    if perna_calculo < perna - 1e-9:
        alertas.append(
            f"O menor cordão tem {menor_cordao:.0f} mm, menos de 4 vezes a perna: a conta usa a "
            f"perna de {perna_calculo:.1f} mm (L/4), como manda a NBR 8800, 6.2.6.2.3."
        )
    cargas = (
        "AISC em tensões admissíveis: as forças entram sem majorar, como cargas de serviço."
        if str(v["criterio"]) == ASD
        else "NBR 8800: as forças entram já majoradas, como cargas de cálculo."
    )

    linhas = tuple(
        {
            "Ponto": f.nome,
            "x (mm)": f.x,
            "y (mm)": f.y,
            "No plano (N/mm)": f.no_plano,
            "Fora do plano (N/mm)": f.fora_do_plano,
            "Resultante (N/mm)": f.resultante,
        }
        for f in sorted(forcas, key=lambda f: -f.resultante)
    )
    figura = figura_dos_cordoes(
        [(t.x1, t.y1, t.x2, t.y2) for t in trechos],
        [(f.x, f.y, f.resultante) for f in forcas],
        (prop.xc, prop.yc),
        (critico.x, critico.y),
    )
    return Resultado(
        resumo=(
            f"Ponto mais carregado ({critico.nome}): {critico.resultante:.0f} N/mm, contra "
            f"{solda:.0f} N/mm do filete de {perna:g} mm {v['eletrodo']}."
        ),
        metricas=(
            Metrica("Força no ponto crítico", critico.resultante, "N/mm", 0),
            Metrica("Resistência do filete", solda, "N/mm", 0),
            Metrica("Tensão na garganta", tau, "MPa", 1),
            Metrica("Comprimento total", prop.comprimento, "mm", 0),
            Metrica("J_u", prop.j_u, "mm³", 0),
            Metrica("I_ux", prop.i_ux, "mm³", 0),
        ),
        verificacoes=tuple(verificacoes),
        tabelas=(
            Tabela(
                "Força por mm de cordão nas pontas",
                linhas,
                "Origem no canto de baixo à esquerda do desenho. A maior força fica sempre numa "
                "ponta de cordão.",
            ),
        ),
        figuras=(Figura("Cordões de solda", figura.png, figura.legenda),),
        alertas=tuple(alertas),
        hipoteses=(
            cargas,
            "Solda de filete de pernas iguais, garganta 0,707·perna.",
            "Peça ligada rígida: a força por mm varia em linha reta a partir do centroide dos "
            "cordões (método elástico).",
            "As três componentes (no plano por cortante, no plano por torque e fora do plano) "
            "somam como vetores e toda a resultante vai como cisalhamento na garganta.",
            "Sem o aumento de resistência pela direção da força (1 + 0,5·sen^1,5 θ): a favor da "
            "segurança.",
            "Momentos Mx e My positivos puxam a solda nos lados +y e +x.",
        ),
        referencias=(SHIGLEY_9, ref_solda, ref_base),
    )


_NAO_ANEL_NEM_LIVRE = ("padrao", tuple(p for p in PADROES if p not in (ANEL, LIVRE)))
_COM_B = ("padrao", tuple(p for p in PADROES if p not in (UM_VERTICAL, ANEL, LIVRE)))

CAMPOS_SOLDA: tuple[Campo, ...] = (
    Campo(
        "padrao",
        "Desenho dos cordões",
        "Como os cordões estão em volta da peça. Em cordões livres, cada linha da tabela é um "
        "cordão reto.",
        EM_C,
        opcoes=PADROES,
        secao="Cordões",
    ),
    Campo(
        "b_mm",
        "Largura b",
        "Medida na horizontal (direção x): distância entre os cordões verticais ou comprimento "
        "dos horizontais.",
        75.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Cordões",
        quando=_COM_B,
    ),
    Campo(
        "d_mm",
        "Altura d",
        "Medida na vertical (direção y): comprimento dos cordões verticais ou distância entre "
        "os horizontais.",
        150.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Cordões",
        quando=_NAO_ANEL_NEM_LIVRE,
    ),
    Campo(
        "d_anel_mm",
        "Diâmetro do anel D",
        "Diâmetro do tubo ou do eixo soldado em volta.",
        100.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Cordões",
        quando=("padrao", (ANEL,)),
    ),
    Campo(
        "cordoes",
        "Cordões",
        "Uma linha para cada cordão reto, do início ao fim. A origem pode ficar em qualquer lugar.",
        (
            {"x1_mm": 0.0, "y1_mm": 0.0, "x2_mm": 0.0, "y2_mm": 150.0},
            {"x1_mm": 0.0, "y1_mm": 0.0, "x2_mm": 75.0, "y2_mm": 0.0},
        ),
        secao="Cordões",
        quando=("padrao", (LIVRE,)),
        colunas=(
            Coluna("x1_mm", "x início", "Posição x do início do cordão.", 0.0, "mm"),
            Coluna("y1_mm", "y início", "Posição y do início do cordão.", 0.0, "mm"),
            Coluna("x2_mm", "x fim", "Posição x do fim do cordão.", 0.0, "mm"),
            Coluna("y2_mm", "y fim", "Posição y do fim do cordão.", 0.0, "mm"),
        ),
    ),
    Campo(
        "perna_mm",
        "Perna do filete",
        "Medida do lado do triângulo da solda. A garganta é 0,707 vez a perna.",
        8.0,
        "mm",
        minimo=1.0,
        maximo=50.0,
        passo=1.0,
        secao="Solda e material",
    ),
    Campo(
        "eletrodo",
        "Eletrodo",
        "Resistência do metal da solda: E60 = 415 MPa, E70 = 485 MPa, E80 = 550 MPa (NBR 8800, "
        "Tabela A.4). E70 é o mais comum com aço estrutural.",
        "E70",
        opcoes=tuple(sd.ELETRODOS),
        secao="Solda e material",
    ),
    Campo(
        "t_mm",
        "Espessura da parte mais fina t",
        "A chapa mais fina das que a solda une. Define a perna mínima e o cisalhamento do "
        "metal-base.",
        12.5,
        "mm",
        minimo=1.0,
        passo=0.5,
        secao="Solda e material",
    ),
    Campo(
        "na_borda",
        "Cordão na borda da chapa",
        "Ligado quando o filete corre ao longo da borda da chapa: a perna fica limitada pela "
        "espessura dela.",
        False,
        secao="Solda e material",
    ),
    Campo(
        "sy_MPa",
        "Limite de escoamento S_y",
        "Do metal-base. ASTM A36: 250 MPa. ASTM A572 grau 50: 345 MPa.",
        250.0,
        "MPa",
        minimo=100.0,
        passo=5.0,
        secao="Solda e material",
    ),
    Campo(
        "sut_MPa",
        "Resistência à ruptura S_ut",
        "Do metal-base. ASTM A36: 400 MPa. ASTM A572 grau 50: 450 MPa.",
        400.0,
        "MPa",
        minimo=100.0,
        passo=5.0,
        secao="Solda e material",
    ),
    Campo(
        "criterio",
        "Critério de resistência",
        "NBR 8800: forças já majoradas e coeficientes γ da norma. AISC ASD: forças de serviço e "
        "tensões admissíveis, o jeito usual em peça de máquina.",
        NBR,
        opcoes=CRITERIOS,
        secao="Solda e material",
    ),
    Campo(
        "n_kN",
        "Força normal N",
        "Perpendicular ao plano da junta, no centroide dos cordões. Positiva puxa a solda.",
        0.0,
        "kN",
        passo=1.0,
        secao="Cargas no centroide dos cordões",
    ),
    Campo(
        "mx_kNm",
        "Momento Mx",
        "Momento fora do plano, em torno do eixo x. Positivo puxa a solda do lado +y. Força "
        "perpendicular à junta a uma distância a: M = F·a.",
        0.0,
        "kN·m",
        passo=0.5,
        secao="Cargas no centroide dos cordões",
    ),
    Campo(
        "my_kNm",
        "Momento My",
        "Momento fora do plano, em torno do eixo y. Positivo puxa a solda do lado +x.",
        0.0,
        "kN·m",
        passo=0.5,
        secao="Cargas no centroide dos cordões",
    ),
    Campo(
        "vx_kN",
        "Cortante Vx",
        "Força no plano da junta, na direção x.",
        0.0,
        "kN",
        passo=1.0,
        secao="Cargas no centroide dos cordões",
    ),
    Campo(
        "vy_kN",
        "Cortante Vy",
        "Força no plano da junta, na direção y. Para baixo é negativa.",
        -40.0,
        "kN",
        passo=1.0,
        secao="Cargas no centroide dos cordões",
    ),
    Campo(
        "t_kNm",
        "Torque no plano T",
        "Momento no plano da junta, positivo anti-horário. Força P no plano a uma distância e do "
        "centroide: T = P·e, com o sinal do giro.",
        -6.0,
        "kN·m",
        passo=0.5,
        secao="Cargas no centroide dos cordões",
    ),
)

CASOS: tuple[Caso, ...] = (
    Caso(
        "solda_filete",
        "Solda de filete sob carga excêntrica",
        GRUPO,
        "Cordões em volta de suporte, console ou tubo: força em cada ponta e o filete que atende.",
        "Suporte, console, orelha ou tubo soldado com filete. Informe o desenho dos cordões, a perna "
        "e as cargas no centroide: sai a força por mm em cada ponta, o ponto crítico e a conferência "
        "do metal da solda, do metal-base e das medidas mínimas da NBR 8800. Para a ligação "
        "estrutural com chapa de nó ou cantoneiras, use a página Ligações soldadas.",
        CAMPOS_SOLDA,
        calcular_solda,
        r"f=\sqrt{\left(\frac{V}{L}+\frac{T\,r}{J_u}\right)^2+\left(\frac{N}{L}+a\,y+b\,x\right)^2},"
        r"\quad f\le 0{,}60\,f_w\,(0{,}707\,h)/\gamma_{w2}",
    ),
)
