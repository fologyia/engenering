"""Içamento e movimentação de cargas: NBR 8400, cabos, rodas, gancho e olhal.

As tabelas da NBR 8400:1984 foram conferidas no PDF da norma. Um detalhe: a Tabela 28 impressa traz
18 para polia com cabo não rotativo no grupo 4m, no meio da sequência 20 - 22,4 - 25 - 18 - 31,5. É
erro de impressão (a coluna cresce sempre um passo acima do cabo normal da mesma linha), e o valor
adotado aqui é 28. Na mesma norma, o exemplo do Anexo H usa δ = 1,12 para o grupo 4m, mas a Tabela
26 dá 1,18: vale a tabela.

O olhal segue a AISC 360-16, D5 e J7. A ASME BTH-1 tem verificações próprias para olhal de içamento,
que não estão aqui porque o texto da norma não pôde ser conferido.
"""

from __future__ import annotations

import bisect
import math

from core.elementos_base import (
    Campo,
    Caso,
    Envio,
    Grafico,
    Metrica,
    Ponto,
    Resultado,
    Valores,
    exigir,
    informativo,
    limite,
    minimo,
    recomendacao_minima,
)

GRUPO = "Içamento (NBR 8400)"

NBR = "ABNT NBR 8400:1984"
NBR_6327 = "ABNT NBR 6327:2006, Anexo C"
AISC = "AISC 360-16"
SHIGLEY_3 = "Shigley, Elementos de Máquinas, cap. 3"

GRUPOS_MECANISMO = ("1Bm", "1Am", "2m", "3m", "4m", "5m")
CLASSES_FUNCIONAMENTO = ("V0,25", "V0,5", "V1", "V2", "V3", "V4", "V5")
ESTADOS = ("1", "2", "3")

#: Tabela 23: grupo do mecanismo por estado de solicitação e classe de funcionamento.
_TABELA_23 = {
    "1": ("1Bm", "1Bm", "1Bm", "1Am", "2m", "3m", "4m"),
    "2": ("1Bm", "1Bm", "1Am", "2m", "3m", "4m", "5m"),
    "3": ("1Bm", "1Am", "2m", "3m", "4m", "5m", "5m"),
}
#: Tabela 24 e Tabela 26.
Q_RUPTURA = {"1Bm": 1.0, "1Am": 1.0, "2m": 1.12, "3m": 1.25, "4m": 1.40, "5m": 1.60}
DELTA_FADIGA = {"1Bm": 1.0, "1Am": 1.0, "2m": 1.06, "3m": 1.12, "4m": 1.18, "5m": 1.25}
#: Tabela 27: coeficiente Q do cabo (normal, não rotativo).
Q_CABO = {
    "1Bm": (0.265, 0.280),
    "1Am": (0.280, 0.300),
    "2m": (0.300, 0.335),
    "3m": (0.335, 0.375),
    "4m": (0.375, 0.425),
    "5m": (0.425, 0.475),
}
#: Tabela 28: H1 de tambor, polia e polia de compensação, cada um (normal, não rotativo).
H1 = {
    "1Bm": ((16.0, 16.0), (16.0, 18.0), (14.0, 16.0)),
    "1Am": ((16.0, 18.0), (18.0, 20.0), (14.0, 16.0)),
    "2m": ((18.0, 20.0), (20.0, 22.4), (14.0, 16.0)),
    "3m": ((20.0, 22.4), (22.4, 25.0), (16.0, 18.0)),
    "4m": ((22.4, 25.0), (25.0, 28.0), (16.0, 18.0)),  # a norma imprime 18: ver o início do módulo
    "5m": ((25.0, 28.0), (28.0, 31.5), (18.0, 20.0)),
}
#: Tabela 33.
C2_RODA = {"1Bm": 1.12, "1Am": 1.12, "2m": 1.0, "3m": 0.9, "4m": 0.8, "5m": 0.8}
#: Tabela 31: rotação da roda em rpm e c₁, em ordem crescente de rotação.
_C1_ROTACAO = (
    (5.0, 1.17), (5.6, 1.16), (6.3, 1.15), (8.0, 1.14), (10.0, 1.13), (11.2, 1.12), (12.5, 1.11),
    (14.0, 1.10), (16.0, 1.09), (18.0, 1.07), (20.0, 1.06), (22.4, 1.04), (25.0, 1.03),
    (28.0, 1.02), (31.5, 1.00), (35.5, 0.99), (40.0, 0.97), (45.0, 0.96), (50.0, 0.94),
    (56.0, 0.92), (63.0, 0.91), (71.0, 0.89), (80.0, 0.87), (90.0, 0.84), (100.0, 0.82),
    (112.0, 0.79), (125.0, 0.77), (160.0, 0.72), (200.0, 0.66),
)  # fmt: skip
#: Tabela 30: resistência do material da roda em MPa e pressão limite em daN/mm².
_P_LIMITE = ((500.0, 0.50), (600.0, 0.56), (700.0, 0.65), (800.0, 0.72))
#: Tabela 10: coeficiente de majoração por grupo da estrutura.
MX_ESTRUTURA = {"1": 1.0, "2": 1.0, "3": 1.0, "4": 1.06, "5": 1.12, "6": 1.20}

TIPO_PONTE = "Ponte ou pórtico rolante"
TIPO_LANCA = "Guindaste com lança"

CABO_NORMAL = "Normal"
CABO_NAO_ROTATIVO = "Não rotativo"

#: NBR 6327: fator K de MBL = K·d²·R e massa em kg/m por mm² de diâmetro.
CLASSES_CABO = {
    "6 x 19 AF": (0.330, 0.00359),
    "6 x 19 AA": (0.356, 0.00400),
    "6 x 36 AF": (0.330, 0.00367),
    "6 x 36 AA": (0.356, 0.00409),
    "8 x 19 AA": (0.356, 0.00407),
    "8 x 36 AA": (0.356, 0.00417),
}
CABO_INFORMADO = "Informar a carga de ruptura"
CATEGORIAS_CABO = ("1770", "1960", "2160")


def grupo_do_mecanismo(classe: str, estado: str, perigoso: bool = False) -> str:
    """Tabela 23; serviço perigoso sobe um grupo (6.2)."""
    grupo = _TABELA_23[estado][CLASSES_FUNCIONAMENTO.index(classe)]
    if perigoso:
        grupo = GRUPOS_MECANISMO[min(GRUPOS_MECANISMO.index(grupo) + 1, len(GRUPOS_MECANISMO) - 1)]
    return grupo


def coeficiente_dinamico(tipo: str, velocidade_m_s: float) -> float:
    """ψ da Tabela 5, com a velocidade de elevação da carga em m/s."""
    v = velocidade_m_s
    if tipo == TIPO_PONTE:
        if v <= 0.25:
            return 1.15
        return 1.0 + 0.6 * v if v < 1.0 else 1.60
    if v <= 0.5:
        return 1.15
    return 1.0 + 0.3 * v if v < 1.0 else 1.30


def rendimento_do_moitao(ramais: int, eta_polia: float) -> float:
    """Rendimento de um moitão simples com ``ramais`` ramos de cabo."""
    if ramais <= 1 or eta_polia >= 1.0:
        return 1.0
    return (1.0 - eta_polia**ramais) / (ramais * (1.0 - eta_polia))


def h2_das_polias(wt: int) -> float:
    """Tabela 29, com o total W_T de inflexões."""
    if wt <= 5:
        return 1.0
    return 1.12 if wt <= 9 else 1.25


def c1_da_rotacao(rpm: float) -> float:
    """c₁ da Tabela 31, interpolado na rotação e limitado às pontas da tabela."""
    rotacoes = [linha[0] for linha in _C1_ROTACAO]
    if rpm <= rotacoes[0]:
        return _C1_ROTACAO[0][1]
    if rpm >= rotacoes[-1]:
        return _C1_ROTACAO[-1][1]
    i = bisect.bisect_right(rotacoes, rpm) - 1
    (r1, c1), (r2, c2) = _C1_ROTACAO[i], _C1_ROTACAO[i + 1]
    return c1 + (c2 - c1) * (rpm - r1) / (r2 - r1)


def pressao_limite(sigma_r_MPa: float) -> float | None:
    """P_lim da Tabela 30 em daN/mm²; ``None`` abaixo da faixa da tabela."""
    valor = None
    for resistencia, pressao in _P_LIMITE:
        if sigma_r_MPa > resistencia:
            valor = pressao
    return valor


def _campos_do_grupo(secao: str) -> tuple[Campo, ...]:
    return (
        Campo(
            "classe",
            "Classe de funcionamento",
            "Tempo médio de uso por dia, com o mecanismo em movimento. V0,25: até 0,5 h. V0,5: até "
            "1 h. V1: até 2 h. V2: até 4 h. V3: até 8 h. V4: até 16 h. V5: mais de 16 h.",
            "V2",
            opcoes=CLASSES_FUNCIONAMENTO,
            secao=secao,
        ),
        Campo(
            "estado",
            "Estado de solicitação",
            "Estado 1: raramente com a carga máxima. Estado 2: reduzida, média e máxima por tempos "
            "iguais. Estado 3: quase sempre perto da máxima.",
            "2",
            opcoes=ESTADOS,
            secao=secao,
        ),
        Campo(
            "perigoso",
            "Serviço perigoso",
            "Material em fusão, produtos químicos ou corrosivos: a NBR 8400 manda subir um grupo.",
            False,
            secao=secao,
        ),
    )


# ---------------------------------------------------------------------------
# Ações de içamento
# ---------------------------------------------------------------------------


def calcular_acoes(v: Valores) -> Resultado:
    tipo = str(v["tipo"])
    sg = float(v["peso_kN"])
    sl = float(v["carga_kN"])
    sh = float(v["horizontal_kN"])
    psi = coeficiente_dinamico(tipo, float(v["velocidade_m_s"]))
    mx = MX_ESTRUTURA[str(v["grupo_estrutura"])]
    caso_1 = mx * (sg + psi * sl + sh)
    sem_mx = sg + psi * sl + sh
    assentamento = sg - sl * (psi - 1.0) / 2.0
    alertas = []
    if assentamento < 0:
        alertas.append(
            "Ao baixar a carga, a oscilação pode inverter o sinal: compare a peça também sob "
            f"{assentamento:.1f} kN (5.5.2.1)."
        )
    return Resultado(
        resumo=(
            f"ψ = {psi:.2f} e M_x = {mx:.2f}: solicitação de {caso_1:.1f} kN no caso I, "
            f"contra {sg + sl:.1f} kN estáticos."
        ),
        metricas=(
            Metrica("Coeficiente dinâmico ψ", psi, "", 3),
            Metrica("Majoração M_x", mx, "", 2),
            Metrica("Caso I com M_x", caso_1, "kN", 1),
            Metrica("Caso I sem M_x", sem_mx, "kN", 1),
            Metrica("Assentamento da carga", assentamento, "kN", 1),
            Metrica("Fator sobre o estático", caso_1 / (sg + sl) if sg + sl > 0 else 1.0, "", 2),
        ),
        verificacoes=(
            informativo(
                "Solicitação do caso I",
                caso_1,
                "kN",
                "M_x·(S_G + ψ·S_L + S_H)",
                f"{NBR}, 5.6.1, Tabelas 5 e 10",
            ),
        ),
        alertas=tuple(alertas),
        hipoteses=(
            "Soma feita em módulo: vale quando as três parcelas agem no mesmo sentido na peça.",
            "S_H são os dois efeitos horizontais mais desfavoráveis, sem choque (5.6.1).",
            "O vento (caso II) e os casos excepcionais (caso III) ficam fora desta soma.",
        ),
        referencias=(f"{NBR}, 5.5.2, 5.6.1 e 5.7",),
        envios=(
            Envio(
                "olhal",
                "Levar a carga para o olhal",
                {"forca_kN": sg + sl, "fator_dinamico": psi * mx},
            ),
            Envio(
                "gancho",
                "Levar a carga para o gancho",
                {"forca_kN": caso_1},
            ),
        ),
    )


CAMPOS_ACOES = (
    Campo(
        "tipo",
        "Equipamento",
        "Ponte ou pórtico rolante: estrutura rígida, ψ até 1,60. Guindaste com lança: estrutura "
        "mais flexível, ψ até 1,30.",
        TIPO_PONTE,
        opcoes=(TIPO_PONTE, TIPO_LANCA),
        secao="Equipamento",
    ),
    Campo(
        "velocidade_m_s",
        "Velocidade de elevação",
        "Velocidade com que a carga sobe. Quanto mais rápido, maior o tranco ao tirar a carga do "
        "chão.",
        0.2,
        "m/s",
        minimo=0.0,
        passo=0.05,
        secao="Equipamento",
    ),
    Campo(
        "grupo_estrutura",
        "Grupo da estrutura",
        "Grupo de 1 a 6 da estrutura, nas Tabelas 1 a 4 da NBR 8400. Define o coeficiente M_x: "
        "1,00 até o grupo 3, 1,06 no 4, 1,12 no 5 e 1,20 no 6.",
        "3",
        opcoes=tuple(MX_ESTRUTURA),
        secao="Equipamento",
    ),
    Campo(
        "peso_kN",
        "Peso próprio S_G",
        "Peso das partes do equipamento que atuam na peça analisada.",
        5.0,
        "kN",
        minimo=0.0,
        passo=1.0,
        secao="Cargas",
    ),
    Campo(
        "carga_kN",
        "Carga de serviço S_L",
        "Carga útil mais acessórios de içamento, sem o coeficiente dinâmico.",
        50.0,
        "kN",
        minimo=0.0,
        passo=5.0,
        secao="Cargas",
    ),
    Campo(
        "horizontal_kN",
        "Efeitos horizontais S_H",
        "Os dois efeitos horizontais mais desfavoráveis: aceleração, frenagem, força centrífuga.",
        0.0,
        "kN",
        minimo=0.0,
        passo=1.0,
        secao="Cargas",
    ),
)


# ---------------------------------------------------------------------------
# Cabo, tambor e polias
# ---------------------------------------------------------------------------


def carga_de_ruptura_do_cabo(classe: str, categoria: str, d_mm: float) -> float:
    """Carga de ruptura mínima em N: K·d²·R da NBR 6327."""
    fator, _massa = CLASSES_CABO[classe]
    return fator * d_mm**2 * float(categoria)


def calcular_cabo(v: Valores) -> Resultado:
    grupo = grupo_do_mecanismo(str(v["classe"]), str(v["estado"]), bool(v["perigoso"]))
    carga = (float(v["carga_kN"]) + float(v["moitao_kN"])) * 1000.0
    ramais = int(v["ramais"])
    eta = float(v["eta_polia"])
    tipo_cabo = str(v["tipo_cabo"])
    classe_cabo = str(v["classe_cabo"])
    d = float(v["d_cabo_mm"])
    d_tambor = float(v["d_tambor_mm"])
    d_polia = float(v["d_polia_mm"])
    d_comp = float(v["d_compensacao_mm"])
    polias = int(v["polias"])
    polias_s = int(v["polias_inversao"])
    tem_polia = polias + polias_s > 0

    eta_moitao = rendimento_do_moitao(ramais, eta)
    tracao = carga / (ramais * eta_moitao)
    if classe_cabo == CABO_INFORMADO:
        ruptura = float(v["ruptura_kN"]) * 1000.0
        massa_metro = 0.0
    else:
        ruptura = carga_de_ruptura_do_cabo(classe_cabo, str(v["categoria"]), d)
        massa_metro = CLASSES_CABO[classe_cabo][1] * d**2

    nao_rotativo = tipo_cabo == CABO_NAO_ROTATIVO
    q = Q_CABO[grupo][1 if nao_rotativo else 0]
    d_min = q * math.sqrt(tracao / 10.0)  # T em daN e d em mm

    # Tabela 28, nota: cabo 6 x 19 usa a coluna do cabo não rotativo.
    coluna_h1 = 1 if nao_rotativo or classe_cabo.startswith("6 x 19") else 0
    h_tambor, h_polia, h_comp = (linha[coluna_h1] for linha in H1[grupo])
    wt = 1 + 2 * polias + 4 * polias_s
    h2 = h2_das_polias(wt)
    # Nota de 6.7.3: dá para manter os enrolamentos até com cabo 25 % acima do mínimo calculado.
    d_base = d_min if d <= 1.25 * d_min else d
    minimo_tambor = h_tambor * d_base
    minimo_polia = h_polia * h2 * d_base
    minimo_comp = h_comp * d_base
    fs = ruptura / tracao

    verificacoes = [
        minimo(
            "Diâmetro do cabo",
            d,
            d_min,
            "mm",
            f"d_c = Q·√T, com Q = {q:.3f} e T = {tracao / 10:.0f} daN",
            f"{NBR}, 6.7.2.1, Tabela 27",
        ),
        minimo(
            "Diâmetro do tambor",
            d_tambor,
            minimo_tambor,
            "mm",
            f"D ≥ H₁·H₂·d_c, com H₁ = {h_tambor:g} e H₂ = 1",
            f"{NBR}, 6.7.3, Tabela 28",
        ),
    ]
    if tem_polia:
        verificacoes.append(
            minimo(
                "Diâmetro das polias",
                d_polia,
                minimo_polia,
                "mm",
                f"D ≥ H₁·H₂·d_c, com H₁ = {h_polia:g}, H₂ = {h2:g} e W_T = {wt}",
                f"{NBR}, 6.7.3, Tabelas 28 e 29",
            )
        )
    if d_comp > 0:
        verificacoes.append(
            minimo(
                "Diâmetro da polia de compensação",
                d_comp,
                minimo_comp,
                "mm",
                f"D ≥ H₁·d_c, com H₁ = {h_comp:g}",
                f"{NBR}, 6.7.3.2",
            )
        )
    verificacoes.append(
        limite(
            "Desvio do cabo no tambor",
            float(v["desvio_graus"]),
            3.5,
            "°",
            "desvio máximo entre o cabo e a ranhura",
            f"{NBR}, 6.7.2.2",
        )
    )
    verificacoes.append(
        informativo(
            "Fator de segurança à ruptura",
            fs,
            "—",
            "MBL/T: a NBR 8400 usa Q no lugar dele",
            NBR_6327,
        )
    )
    alertas: list[str] = []
    if d > 1.25 * d_min:
        alertas.append(
            f"O cabo é mais de 25 % maior que o mínimo calculado ({d_min:.1f} mm): os enrolamentos "
            "passam a ser dimensionados pelo diâmetro real (nota de 6.7.3)."
        )
    if nao_rotativo and classe_cabo != CABO_INFORMADO:
        alertas.append(
            "As classes da lista são de cabo normal. Para cabo não rotativo, informe a carga de "
            "ruptura do catálogo."
        )
    return Resultado(
        resumo=(
            f"Grupo {grupo}: T = {tracao / 1000:.2f} kN pede cabo de {d_min:.1f} mm, tambor de "
            f"{minimo_tambor:.0f} mm e polia de {minimo_polia:.0f} mm."
        ),
        metricas=(
            Metrica("Grupo do mecanismo", grupo),
            Metrica("Tração no cabo", tracao / 1000.0, "kN"),
            Metrica("Rendimento do moitão", eta_moitao, "", 3),
            Metrica("Cabo mínimo", d_min, "mm", 1),
            Metrica("Tambor mínimo", minimo_tambor, "mm", 0),
            Metrica("Polia mínima", minimo_polia, "mm", 0),
            Metrica("Carga de ruptura", ruptura / 1000.0, "kN", 1),
            Metrica("Fator à ruptura", fs, "", 1),
            Metrica(
                "Torque no tambor",
                tracao * d_tambor / 2.0 / 1e6 * float(v["ramos_no_tambor"]),
                "kN·m",
                2,
            ),
            Metrica("Massa do cabo", massa_metro, "kg/m", 2),
        ),
        verificacoes=tuple(verificacoes),
        alertas=tuple(alertas),
        hipoteses=(
            "Método para cabos com mais de 100 fios e resistência de 1600 a 2200 MPa (6.7.2).",
            "Tração do caso I, sem o coeficiente dinâmico. Some as forças de aceleração quando "
            "passarem de 10 % das cargas verticais.",
            "Na carga de ruptura, MBL = K·d²·R, com K da NBR 6327 para cada classe.",
            "A Tabela 28 impressa traz 18 no grupo 4m, em polia com cabo não rotativo. Adotado 28, "
            "que é o valor coerente com a sequência da tabela.",
        ),
        referencias=(f"{NBR}, 6.7.2 e 6.7.3", NBR_6327),
        envios=(
            Envio(
                "eixo_transmissao",
                "Levar a força do cabo para o eixo do tambor",
                {
                    "f1_ativa": True,
                    "f1_fy_kN": tracao * float(v["ramos_no_tambor"]) / 1000.0,
                    "f1_fz_kN": 0.0,
                    "f1_fx_kN": 0.0,
                    "f1_raio_mm": 0.0,
                    "f1_torque_Nm": tracao * d_tambor / 2.0 / 1000.0 * float(v["ramos_no_tambor"]),
                    "f2_ativa": True,
                    "f2_torque_Nm": -(
                        tracao * d_tambor / 2.0 / 1000.0 * float(v["ramos_no_tambor"])
                    ),
                },
            ),
        ),
    )


CAMPOS_CABO = (
    *_campos_do_grupo("Grupo do mecanismo"),
    Campo(
        "carga_kN",
        "Carga útil",
        "A carga nominal içada.",
        100.0,
        "kN",
        minimo=0.001,
        passo=5.0,
        secao="Sistema de cabos",
    ),
    Campo(
        "moitao_kN",
        "Peso do moitão e do gancho",
        "Peso que sobe junto com a carga.",
        3.0,
        "kN",
        minimo=0.0,
        passo=0.5,
        secao="Sistema de cabos",
    ),
    Campo(
        "ramais",
        "Número de ramais",
        "Quantos ramos de cabo seguram o moitão. Moitão simples de 2 polias: 4 ramais.",
        4,
        minimo=1,
        maximo=24,
        passo=1,
        secao="Sistema de cabos",
    ),
    Campo(
        "ramos_no_tambor",
        "Ramos que chegam ao tambor",
        "Quantos ramos enrolam no tambor: 1 em cabo simples e 2 em tambor com duas hélices, "
        "usado para a carga subir sem andar de lado.",
        2,
        minimo=1,
        maximo=2,
        passo=1,
        secao="Sistema de cabos",
    ),
    Campo(
        "eta_polia",
        "Rendimento de cada polia",
        "Polia com rolamento: 0,98. Polia com bucha: 0,96.",
        0.98,
        minimo=0.8,
        maximo=1.0,
        passo=0.01,
        secao="Sistema de cabos",
    ),
    Campo(
        "desvio_graus",
        "Desvio do cabo na ranhura",
        "Ângulo entre o cabo e a ranhura do tambor, no fim do curso.",
        2.0,
        "°",
        minimo=0.0,
        maximo=45.0,
        passo=0.5,
        secao="Sistema de cabos",
    ),
    Campo(
        "tipo_cabo",
        "Tipo de cabo",
        "Cabo não rotativo não gira sob carga, mas aceita pior as flexões: pede Q e H maiores.",
        CABO_NORMAL,
        opcoes=(CABO_NORMAL, CABO_NAO_ROTATIVO),
        secao="Cabo",
    ),
    Campo(
        "classe_cabo",
        "Classe do cabo",
        "Da NBR 6327. AF é alma de fibra e AA é alma de aço. A carga de ruptura sai de K·d²·R.",
        "6 x 36 AA",
        opcoes=(*CLASSES_CABO, CABO_INFORMADO),
        secao="Cabo",
    ),
    Campo(
        "categoria",
        "Categoria de resistência",
        "Resistência nominal dos arames, em N/mm².",
        "1960",
        opcoes=CATEGORIAS_CABO,
        secao="Cabo",
    ),
    Campo(
        "ruptura_kN",
        "Carga de ruptura do cabo",
        "Carga de ruptura mínima do catálogo.",
        170.0,
        "kN",
        minimo=0.1,
        passo=5.0,
        secao="Cabo",
        quando=("classe_cabo", (CABO_INFORMADO,)),
    ),
    Campo(
        "d_cabo_mm",
        "Diâmetro do cabo",
        "Diâmetro nominal escolhido.",
        16.0,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Cabo",
    ),
    Campo(
        "d_tambor_mm",
        "Diâmetro de enrolamento do tambor",
        "Diâmetro medido no centro do cabo enrolado.",
        400.0,
        "mm",
        minimo=1.0,
        passo=10.0,
        secao="Enrolamento",
    ),
    Campo(
        "d_polia_mm",
        "Diâmetro de enrolamento das polias",
        "Diâmetro das polias móveis e de desvio, medido no centro do cabo.",
        450.0,
        "mm",
        minimo=1.0,
        passo=10.0,
        secao="Enrolamento",
    ),
    Campo(
        "d_compensacao_mm",
        "Diâmetro da polia de compensação",
        "A polia parada que só iguala os ramos. Deixe 0 se não houver.",
        250.0,
        "mm",
        minimo=0.0,
        passo=10.0,
        secao="Enrolamento",
    ),
    Campo(
        "polias",
        "Polias sem inversão",
        "Polias em que o cabo não inverte o sentido da curva. Cada uma vale W = 2.",
        3,
        minimo=0,
        maximo=20,
        passo=1,
        secao="Enrolamento",
    ),
    Campo(
        "polias_inversao",
        "Polias com curva em S",
        "Polias que invertem o sentido do enrolamento. Cada uma vale W = 4 e cansa mais o cabo.",
        0,
        minimo=0,
        maximo=20,
        passo=1,
        secao="Enrolamento",
    ),
)


# ---------------------------------------------------------------------------
# Roda de ponte rolante
# ---------------------------------------------------------------------------


def calcular_roda(v: Valores) -> Resultado:
    grupo = grupo_do_mecanismo(str(v["classe"]), str(v["estado"]), bool(v["perigoso"]))
    f_max = float(v["f_max_kN"]) * 100.0  # em daN
    f_min = float(v["f_min_kN"]) * 100.0
    d = float(v["d_mm"])
    boleto = float(v["boleto_mm"])
    raio = float(v["raio_mm"])
    velocidade = float(v["velocidade_m_min"])
    sigma_r = float(v["sigma_r_MPa"])
    exigir(f_max >= f_min, "A carga máxima da roda deve ser maior ou igual à mínima.")
    largura = boleto - 2.0 * raio if str(v["superficie"]) == "Plana" else boleto - 4.0 * raio / 3.0
    exigir(largura > 0, "O raio do boleto consome toda a largura: confira o trilho.")

    rotacao = velocidade * 1000.0 / (math.pi * d)
    c1 = c1_da_rotacao(rotacao)
    c2 = C2_RODA[grupo]
    p_lim = pressao_limite(sigma_r)
    alertas: list[str] = []
    if p_lim is None:
        p_lim = 0.0
        alertas.append(
            "A Tabela 30 começa acima de 500 MPa: com esta resistência a norma não dá pressão "
            "limite. Use material melhor."
        )
    if d > 1250.0:
        alertas.append("As fórmulas valem até 1250 mm de diâmetro (6.7.4, nota 13).")
    if not 5.0 <= rotacao <= 200.0:
        alertas.append(f"Rotação de {rotacao:.1f} rpm fora da Tabela 31: c₁ na ponta da tabela.")

    f_media = (f_min + 2.0 * f_max) / 3.0
    pressao = f_media / (largura * d)
    admissivel = p_lim * c1 * c2
    verificacoes = [
        limite(
            "Pressão na roda, casos I e II",
            pressao,
            admissivel,
            "daN/mm²",
            f"F_r/(b·D) ≤ P_lim·c₁·c₂ = {p_lim:.2f}·{c1:.3f}·{c2:.2f}",
            f"{NBR}, 6.7.4, Tabelas 30, 31 e 33",
        ),
    ]
    f_caso3 = float(v["f_caso3_kN"]) * 100.0
    if f_caso3 > 0:
        verificacoes.append(
            limite(
                "Pressão na roda, caso III",
                f_caso3 / (largura * d),
                1.4 * p_lim,
                "daN/mm²",
                f"F_r/(b·D) ≤ 1,4·P_lim, com b = {largura:.1f} mm",
                f"{NBR}, 6.7.4",
            )
        )
    d_minimo = f_media / (largura * admissivel) if admissivel > 0 else math.inf
    return Resultado(
        resumo=(
            f"Grupo {grupo}: F_r = {f_media / 100:.1f} kN, largura útil {largura:.1f} mm e pressão "
            f"de {pressao:.3f} daN/mm² para {admissivel:.3f} admissíveis."
        ),
        metricas=(
            Metrica("Grupo do mecanismo", grupo),
            Metrica("Carga média F_r", f_media / 100.0, "kN", 1),
            Metrica("Largura útil b", largura, "mm", 1),
            Metrica("Rotação da roda", rotacao, "rpm", 1),
            Metrica("c₁", c1, "", 3),
            Metrica("c₂", c2, "", 2),
            Metrica("P_lim", p_lim, "daN/mm²", 2),
            Metrica("Diâmetro mínimo", d_minimo if math.isfinite(d_minimo) else "—", "mm", 0),
        ),
        verificacoes=tuple(verificacoes),
        alertas=tuple(alertas),
        hipoteses=(
            "F_r = (F_mín + 2·F_máx)/3, sem o coeficiente dinâmico ψ (6.7.4.1).",
            "Largura útil do boleto: ℓ − 2r em superfície plana e ℓ − 4r/3 em superfície curva.",
            "c₁ interpolado na Tabela 31 pela rotação da roda.",
            "Pressão fictícia, obtida da fórmula de Hertz, para comparar com P_lim. Não é a pressão "
            "real de contato.",
            "Folga lateral mínima entre roda e boleto: 10 mm no carro e 20 mm na ponte.",
        ),
        referencias=(f"{NBR}, 6.7.4",),
    )


CAMPOS_RODA = (
    *_campos_do_grupo("Grupo do mecanismo"),
    Campo(
        "f_max_kN",
        "Carga máxima na roda",
        "Com o carro carregado com a carga nominal na ponta do lado da roda, sem coeficiente "
        "dinâmico.",
        120.0,
        "kN",
        minimo=0.001,
        passo=5.0,
        secao="Cargas",
    ),
    Campo(
        "f_min_kN",
        "Carga mínima na roda",
        "Com o carro vazio na ponta oposta à roda.",
        40.0,
        "kN",
        minimo=0.0,
        passo=5.0,
        secao="Cargas",
    ),
    Campo(
        "f_caso3_kN",
        "Carga média do caso III",
        "Carga média com o equipamento fora de serviço. Deixe 0 para não verificar o caso III.",
        0.0,
        "kN",
        minimo=0.0,
        passo=5.0,
        secao="Cargas",
    ),
    Campo(
        "d_mm",
        "Diâmetro da roda D",
        "Diâmetro da superfície de rolamento. Acima de 1250 mm a norma não se aplica.",
        630.0,
        "mm",
        minimo=50.0,
        passo=10.0,
        secao="Roda e trilho",
    ),
    Campo(
        "velocidade_m_min",
        "Velocidade de translação",
        "Velocidade da ponte ou do carro.",
        63.0,
        "m/min",
        minimo=0.1,
        passo=5.0,
        secao="Roda e trilho",
    ),
    Campo(
        "sigma_r_MPa",
        "Resistência do material da roda",
        "Resistência à ruptura do aço da roda, antes de qualquer tratamento de superfície: a "
        "norma não credita a dureza superficial no P_lim.",
        750.0,
        "MPa",
        minimo=100.0,
        passo=10.0,
        secao="Roda e trilho",
    ),
    Campo(
        "boleto_mm",
        "Largura do boleto ℓ",
        "Largura total da cabeça do trilho.",
        75.0,
        "mm",
        minimo=5.0,
        passo=1.0,
        secao="Roda e trilho",
    ),
    Campo(
        "raio_mm",
        "Raio de canto do boleto r",
        "Raio dos cantos da cabeça do trilho.",
        8.0,
        "mm",
        minimo=0.0,
        passo=1.0,
        secao="Roda e trilho",
    ),
    Campo(
        "superficie",
        "Superfície de rolamento",
        "Trilho de boleto plano ou curvo. O curvo dá largura útil maior, com o mesmo boleto.",
        "Curva",
        opcoes=("Curva", "Plana"),
        secao="Roda e trilho",
    ),
)


# ---------------------------------------------------------------------------
# Peça de mecanismo: ruptura e fadiga
# ---------------------------------------------------------------------------


def calcular_mecanismo(v: Valores) -> Resultado:
    grupo = grupo_do_mecanismo(str(v["classe"]), str(v["estado"]), bool(v["perigoso"]))
    sigma_r = float(v["sigma_r_MPa"])
    axial = float(v["sigma_axial_MPa"])
    flexao = abs(float(v["sigma_flexao_MPa"]))
    tau = abs(float(v["tau_MPa"]))
    ferro = str(v["material"]) == "Ferro fundido cinzento"
    q = Q_RUPTURA[grupo]
    fsr = 2.8
    fsr_3 = 2.0
    if ferro:
        # Nota da Tabela 25: q e FS_r sobem 25 % para ferro fundido cinzento.
        q *= 1.25
        fsr *= 1.25
        fsr_3 *= 1.25
    sigma_a = sigma_r / (q * fsr)

    def equivalente(multiplicador: float) -> tuple[float, str]:
        normal = abs(axial) * multiplicador
        momento = flexao * multiplicador
        corte = tau * multiplicador
        fator = 1.25 if axial > 0 else 1.0
        valor = math.sqrt((fator * normal + momento) ** 2 + 3.0 * corte**2)
        if axial > 0:
            return valor, "√[(1,25·σ_t + σ_f)² + 3τ²] ≤ σ_a"
        return valor, "√[(σ_c + σ_f)² + 3τ²] ≤ σ_a"

    valor_1, regra = equivalente(1.0)
    verificacoes = [
        limite(
            "Ruptura, casos I e II",
            valor_1,
            sigma_a,
            "MPa",
            f"{regra}, com σ_a = σ_r/(q·FS_r) = {sigma_r:.0f}/({q:.2f}·{fsr:.2f})",
            f"{NBR}, 6.6.1, Tabelas 24 e 25",
        )
    ]
    pontos = [Ponto("Peça, casos I e II", axial + flexao, 0.0, tau)]
    if bool(v["levantamento"]):
        sigma_a_3 = sigma_r / (q * fsr_3)
        valor_3, regra_3 = equivalente(1.6)
        verificacoes.append(
            limite(
                "Ruptura, caso III (1,6 × caso I)",
                valor_3,
                sigma_a_3,
                "MPa",
                f"{regra_3}, com FS_r = {fsr_3:.2f}",
                f"{NBR}, 6.5.1 e 6.6.1",
            )
        )
        pontos.append(Ponto("Peça, caso III", 1.6 * (axial + flexao), 0.0, 1.6 * tau))
    delta = DELTA_FADIGA[grupo]
    sigma_max = float(v["sigma_max_fadiga_MPa"])
    sigma_af = float(v["sigma_af_MPa"])
    if sigma_af > 0:
        verificacoes.append(
            limite(
                "Fadiga",
                delta * sigma_max,
                sigma_af,
                "MPa",
                f"δ·σ_máx ≤ σ_af, com δ = {delta:g}",
                f"{NBR}, 6.6.3, Tabela 26",
            )
        )
    alertas = []
    if sigma_af <= 0:
        alertas.append(
            "A fadiga não foi verificada: informe σ_af ou use Seção de eixo: fadiga e entalhe."
        )
    return Resultado(
        resumo=f"Grupo {grupo}: tensão admissível de {sigma_a:.0f} MPa nos casos I e II.",
        metricas=(
            Metrica("Grupo do mecanismo", grupo),
            Metrica("q", q, "", 2),
            Metrica("FS_r", fsr, "", 2),
            Metrica("σ_a, casos I e II", sigma_a, "MPa", 1),
            Metrica("Tensão equivalente", valor_1, "MPa", 1),
            Metrica("δ de fadiga", delta, "", 2),
        ),
        verificacoes=tuple(verificacoes),
        pontos=tuple(pontos),
        alertas=tuple(alertas),
        hipoteses=(
            "Critério de ruptura dos mecanismos: σ_a sobre a resistência à ruptura, e não sobre o "
            "escoamento (6.6.1).",
            "A tração pesa 1,25 vez porque a compressão não abre trinca.",
            "No levantamento, o caso III é 1,6 vez o caso I (6.5.1). Nos outros movimentos, entre "
            "com as tensões do caso III e desligue a opção.",
            "Tensões de cálculo nominais da seção da peça.",
        ),
        referencias=(f"{NBR}, 6.5 e 6.6",),
    )


CAMPOS_MECANISMO = (
    *_campos_do_grupo("Grupo do mecanismo"),
    Campo(
        "material",
        "Material",
        "Em ferro fundido cinzento, a norma sobe q e FS_r em 25 %.",
        "Aço",
        opcoes=("Aço", "Ferro fundido cinzento"),
        secao="Material",
    ),
    Campo(
        "sigma_r_MPa",
        "Resistência à ruptura σ_r",
        "Limite de resistência do material da peça.",
        600.0,
        "MPa",
        minimo=50.0,
        passo=10.0,
        secao="Material",
    ),
    Campo(
        "sigma_axial_MPa",
        "Tensão axial",
        "Tração positiva e compressão negativa, nos casos I e II.",
        0.0,
        "MPa",
        passo=5.0,
        secao="Tensões na peça",
    ),
    Campo(
        "sigma_flexao_MPa",
        "Tensão de flexão σ_f",
        "Tensão de flexão máxima na seção.",
        80.0,
        "MPa",
        passo=5.0,
        secao="Tensões na peça",
    ),
    Campo(
        "tau_MPa",
        "Tensão de cisalhamento τ",
        "Cisalhamento na seção, inclusive o de torção.",
        30.0,
        "MPa",
        passo=5.0,
        secao="Tensões na peça",
    ),
    Campo(
        "levantamento",
        "Movimento de levantamento",
        "Ligado, o programa confere também o caso III como 1,6 vez o caso I, conforme 6.5.1.",
        True,
        secao="Tensões na peça",
    ),
    Campo(
        "sigma_max_fadiga_MPa",
        "Tensão máxima em fadiga",
        "A maior tensão do ciclo, no caso I de solicitação.",
        80.0,
        "MPa",
        minimo=0.0,
        passo=5.0,
        secao="Fadiga",
    ),
    Campo(
        "sigma_af_MPa",
        "Tensão limite à fadiga σ_af",
        "Limite à fadiga no ponto, já com o efeito do entalhe (Anexo H da norma). Deixe 0 para "
        "não verificar.",
        0.0,
        "MPa",
        minimo=0.0,
        passo=5.0,
        secao="Fadiga",
    ),
)


# ---------------------------------------------------------------------------
# Gancho e peças curvas
# ---------------------------------------------------------------------------

SECAO_RETANGULAR = "Retangular"
SECAO_CIRCULAR = "Circular"
SECAO_TRAPEZOIDAL = "Trapezoidal"


def propriedades_viga_curva(
    secao: str, ri: float, h: float, b: float, bo: float, diametro: float
) -> dict[str, float]:
    """Área, raios do centroide e da linha neutra e fibra externa (Shigley, Tabela 3-4)."""
    if secao == SECAO_RETANGULAR:
        ro = ri + h
        area = b * h
        rc = ri + h / 2.0
        rn = h / math.log(ro / ri)
    elif secao == SECAO_CIRCULAR:
        raio = diametro / 2.0
        ro = ri + diametro
        area = math.pi * raio**2
        rc = ri + raio
        rn = raio**2 / (2.0 * (rc - math.sqrt(rc**2 - raio**2)))
    elif secao == SECAO_TRAPEZOIDAL:
        ro = ri + h
        area = (b + bo) * h / 2.0
        rc = ri + h * (b + 2.0 * bo) / (3.0 * (b + bo))
        rn = area / ((b * ro - bo * ri) / h * math.log(ro / ri) - (b - bo))
    else:
        raise ValueError(f"Seção desconhecida: {secao}.")
    return {"area": area, "ro": ro, "rc": rc, "rn": rn, "e": rc - rn}


def tensao_viga_curva(
    r: float, forca: float, momento: float, area: float, rn: float, e: float
) -> float:
    """σ em r: F/A + M(r_n − r)/(A·e·r). M positivo traciona a fibra interna."""
    return forca / area + momento * (rn - r) / (area * e * r)


def calcular_gancho(v: Valores) -> Resultado:
    secao = str(v["secao"])
    forca = float(v["forca_kN"]) * 1000.0
    ri = float(v["ri_mm"])
    props = propriedades_viga_curva(
        secao, ri, float(v["h_mm"]), float(v["b_mm"]), float(v["bo_mm"]), float(v["diametro_mm"])
    )
    area, ro, rc, rn, e = (props[k] for k in ("area", "ro", "rc", "rn", "e"))
    braco = rc if str(v["braco_modo"]) == "Carga no centro de curvatura" else float(v["braco_mm"])
    momento = forca * braco
    interna = tensao_viga_curva(ri, forca, momento, area, rn, e)
    externa = tensao_viga_curva(ro, forca, momento, area, rn, e)
    sy = float(v["sy_MPa"])
    fs = float(v["fs"])

    if secao == SECAO_CIRCULAR:
        inercia = math.pi * float(v["diametro_mm"]) ** 4 / 64.0
        c_interna = float(v["diametro_mm"]) / 2.0
    elif secao == SECAO_RETANGULAR:
        inercia = float(v["b_mm"]) * float(v["h_mm"]) ** 3 / 12.0
        c_interna = float(v["h_mm"]) / 2.0
    else:
        h, b, bo = float(v["h_mm"]), float(v["b_mm"]), float(v["bo_mm"])
        inercia = h**3 * (b**2 + 4.0 * b * bo + bo**2) / (36.0 * (b + bo))
        c_interna = rc - ri
    reta = forca / area + momento * c_interna / inercia

    verificacoes = (
        limite(
            "Fibra interna (tração)",
            abs(interna),
            sy / fs,
            "MPa",
            f"σ_i = F/A + M(r_n − r_i)/(A·e·r_i), com M = {momento / 1e6:.2f} kN·m e e = {e:.2f} mm",
            f"{SHIGLEY_3} (Winkler-Bach)",
        ),
        limite(
            "Fibra externa (compressão)",
            abs(externa),
            sy / fs,
            "MPa",
            "σ_o = F/A + M(r_n − r_o)/(A·e·r_o)",
            f"{SHIGLEY_3} (Winkler-Bach)",
        ),
        recomendacao_minima(
            "Curvatura da peça",
            rc / (ro - ri),
            1.0,
            "—",
            "r_c/h ≥ 1: abaixo disso a seção se deforma e a teoria perde precisão",
            SHIGLEY_3,
        ),
    )
    passos = 40
    curva = []
    for i in range(passos + 1):
        r = ri + (ro - ri) * i / passos
        curva.append((r, tensao_viga_curva(r, forca, momento, area, rn, e), "σ na seção"))
    alertas = []
    if interna > 1.3 * reta:
        alertas.append(
            f"A fórmula de viga reta daria {reta:.0f} MPa e a viga curva dá {interna:.0f} MPa: a "
            "curvatura sobe a tensão na fibra interna."
        )
    return Resultado(
        resumo=(
            f"Fibra interna a {interna:.0f} MPa e externa a {externa:.0f} MPa, com a linha neutra "
            f"deslocada {e:.1f} mm para dentro."
        ),
        metricas=(
            Metrica("Fibra interna σ_i", interna, "MPa", 1),
            Metrica("Fibra externa σ_o", externa, "MPa", 1),
            Metrica("Pela viga reta", reta, "MPa", 1),
            Metrica("Raio do centroide r_c", rc, "mm", 1),
            Metrica("Raio da linha neutra r_n", rn, "mm", 2),
            Metrica("Deslocamento e", e, "mm", 2),
            Metrica("Momento", momento / 1e6, "kN·m", 2),
            Metrica("Área", area, "mm²", 0),
        ),
        verificacoes=verificacoes,
        pontos=(
            Ponto("Fibra interna", interna),
            Ponto("Fibra externa", externa),
        ),
        graficos=(Grafico("Tensão ao longo da seção", "Raio r (mm)", "σ (MPa)", tuple(curva)),),
        alertas=tuple(alertas),
        hipoteses=(
            "Teoria de Winkler-Bach: seções planas continuam planas e a tensão varia como uma "
            "hipérbole.",
            "Material elástico até o limite; gancho forjado real escoa aos poucos na fibra interna.",
            "Seção com eixo de simetria no plano de curvatura.",
            "Ganchos de catálogo seguem a própria norma de produto; este caso serve para peças "
            "especiais, anéis e olhais curvos.",
        ),
        referencias=(SHIGLEY_3,),
    )


CAMPOS_GANCHO = (
    Campo(
        "forca_kN",
        "Força F",
        "A força de cálculo, com os coeficientes dinâmicos já incluídos.",
        50.0,
        "kN",
        minimo=0.001,
        passo=5.0,
        secao="Carga",
    ),
    Campo(
        "braco_modo",
        "Linha da força",
        "Num gancho, a linha da carga passa pelo centro de curvatura. Para outro braço, informe a "
        "distância até o centroide da seção.",
        "Carga no centro de curvatura",
        opcoes=("Carga no centro de curvatura", "Informar o braço"),
        secao="Carga",
    ),
    Campo(
        "braco_mm",
        "Braço até o centroide",
        "Distância entre a linha da força e o centroide da seção.",
        80.0,
        "mm",
        minimo=0.0,
        passo=5.0,
        secao="Carga",
        quando=("braco_modo", ("Informar o braço",)),
    ),
    Campo(
        "ri_mm",
        "Raio interno r_i",
        "Raio da fibra interna da curva, na seção analisada.",
        60.0,
        "mm",
        minimo=0.1,
        passo=5.0,
        secao="Seção",
    ),
    Campo(
        "secao",
        "Forma da seção",
        "A forma é a da seção no ponto mais carregado. Gancho comum: trapezoidal, com a base "
        "maior do lado de dentro.",
        SECAO_TRAPEZOIDAL,
        opcoes=(SECAO_TRAPEZOIDAL, SECAO_RETANGULAR, SECAO_CIRCULAR),
        secao="Seção",
    ),
    Campo(
        "h_mm",
        "Altura da seção h",
        "Da fibra interna à externa.",
        80.0,
        "mm",
        minimo=0.1,
        passo=5.0,
        secao="Seção",
        quando=("secao", (SECAO_TRAPEZOIDAL, SECAO_RETANGULAR)),
    ),
    Campo(
        "b_mm",
        "Largura interna b_i",
        "Largura da seção do lado de dentro da curva. Em seção retangular, é a largura.",
        60.0,
        "mm",
        minimo=0.1,
        passo=5.0,
        secao="Seção",
        quando=("secao", (SECAO_TRAPEZOIDAL, SECAO_RETANGULAR)),
    ),
    Campo(
        "bo_mm",
        "Largura externa b_o",
        "Largura da seção do lado de fora da curva.",
        20.0,
        "mm",
        minimo=0.1,
        passo=5.0,
        secao="Seção",
        quando=("secao", (SECAO_TRAPEZOIDAL,)),
    ),
    Campo(
        "diametro_mm",
        "Diâmetro da seção",
        "Diâmetro do fio ou da barra, como num elo de corrente.",
        40.0,
        "mm",
        minimo=0.1,
        passo=2.0,
        secao="Seção",
        quando=("secao", (SECAO_CIRCULAR,)),
    ),
    Campo(
        "sy_MPa",
        "Limite de escoamento",
        "Limite de escoamento do material da peça.",
        345.0,
        "MPa",
        minimo=10.0,
        passo=10.0,
        secao="Material",
    ),
    Campo(
        "fs",
        "Fator de segurança",
        "Margem sobre o escoamento. Em içamento, comece com 2,0 sobre a carga de cálculo.",
        2.0,
        minimo=1.0,
        maximo=8.0,
        passo=0.1,
        secao="Material",
    ),
)


# ---------------------------------------------------------------------------
# Olhal de içamento
# ---------------------------------------------------------------------------


def calcular_olhal(v: Valores) -> Resultado:
    forca = float(v["forca_kN"]) * 1000.0 * float(v["fator_dinamico"])
    t = float(v["t_mm"])
    w = float(v["w_mm"])
    d_p = float(v["d_pino_mm"])
    d_h = float(v["d_furo_mm"])
    a = float(v["a_mm"])
    fy = float(v["fy_MPa"])
    fu = float(v["fu_MPa"])
    fs_min = float(v["fs_minimo"])
    exigir(d_h >= d_p, "O furo não pode ser menor que o pino.")
    exigir(w > d_h, "A largura do olhal deve ser maior que o furo.")
    exigir(fy <= fu, "F_y não pode ser maior que F_u.")

    be_norma = 2.0 * t + 16.0
    borda = (w - d_h) / 2.0
    be = min(be_norma, borda)
    rn_tracao = fu * 2.0 * t * be
    asf = 2.0 * t * (a + d_p / 2.0)
    rn_corte = 0.6 * fu * asf
    rn_contato = 1.8 * fy * t * d_p
    rn_bruta = fy * w * t
    omega_ruptura = max(2.0, fs_min)
    omega_escoamento = max(1.67, fs_min)

    theta = math.radians(float(v["angulo_graus"]))
    fv = forca * math.cos(theta)
    fh = forca * math.sin(theta)
    h = float(v["h_mm"])
    base = float(v["base_mm"])
    s = float(v["solda_mm"])
    fexx = float(v["fexx_MPa"])
    momento = fh * h
    sigma_base = fv / (base * t) + 6.0 * momento / (t * base**2)
    tau_base = fh / (base * t)
    vm_base = math.sqrt(sigma_base**2 + 3.0 * tau_base**2)
    garganta = 0.707 * s
    area_solda = 2.0 * garganta * base
    modulo_solda = 2.0 * garganta * base**2 / 6.0
    f_normal = fv / area_solda + momento / modulo_solda
    f_corte = fh / area_solda
    f_solda = math.hypot(f_normal, f_corte)

    verificacoes = [
        limite(
            "Tração na seção do furo",
            forca,
            rn_tracao / omega_ruptura,
            "N",
            f"R_n = F_u·2t·b_e, b_e = {be:.1f} mm, Ω = {omega_ruptura:g}",
            f"{AISC}, D5-1",
        ),
        limite(
            "Rasgamento à frente do furo",
            forca,
            rn_corte / omega_ruptura,
            "N",
            f"R_n = 0,6·F_u·A_sf, A_sf = 2t(a + d/2) = {asf:.0f} mm², Ω = {omega_ruptura:g}",
            f"{AISC}, D5-2",
        ),
        limite(
            "Esmagamento do furo",
            forca,
            rn_contato / omega_ruptura,
            "N",
            f"R_n = 1,8·F_y·t·d, Ω = {omega_ruptura:g}",
            f"{AISC}, J7-1",
        ),
        limite(
            "Escoamento da seção bruta",
            forca,
            rn_bruta / omega_escoamento,
            "N",
            f"R_n = F_y·w·t, Ω = {omega_escoamento:g}",
            f"{AISC}, D2-1",
        ),
        limite(
            "Base do olhal",
            vm_base,
            fy / omega_escoamento,
            "MPa",
            f"σ = F_v/(L·t) + 6M/(t·L²), τ = F_h/(L·t), com M = {momento / 1e6:.2f} kN·m",
            "Flexão composta da chapa; von Mises",
        ),
        limite(
            "Solda da base (2 filetes)",
            f_solda,
            0.6 * fexx / omega_ruptura,
            "MPa",
            f"garganta de {garganta:.1f} mm; f ≤ 0,6·F_EXX/Ω, com Ω = {omega_ruptura:g}",
            f"{AISC}, J2-4",
        ),
        minimo(
            "Largura mínima no furo",
            w,
            2.0 * be_norma + d_h,
            "mm",
            "w ≥ 2·b_e + d",
            f"{AISC}, D5.2",
        ),
        minimo(
            "Distância à frente do furo",
            a,
            1.33 * be_norma,
            "mm",
            "a ≥ 1,33·b_e",
            f"{AISC}, D5.2",
        ),
    ]
    if bool(v["gira_sob_carga"]):
        verificacoes.append(
            limite(
                "Folga do furo com giro sob carga",
                d_h - d_p,
                1.0,
                "mm",
                "d_furo − d_pino ≤ 1 mm",
                f"{AISC}, D5.2",
            )
        )
    alertas = []
    if theta > 0:
        alertas.append(
            "A carga inclinada aqui está no plano do olhal. Carga fora do plano flete a chapa no "
            "eixo fraco e não está verificada."
        )
    return Resultado(
        resumo=(
            f"Carga de cálculo de {forca / 1000:.1f} kN e menor capacidade de "
            f"{min(rn_tracao, rn_corte, rn_contato) / omega_ruptura / 1000:.1f} kN entre os modos "
            "de ruptura no furo."
        ),
        metricas=(
            Metrica("Carga de cálculo", forca / 1000.0, "kN", 1),
            Metrica("Tração no furo R_n", rn_tracao / 1000.0, "kN", 0),
            Metrica("Rasgamento R_n", rn_corte / 1000.0, "kN", 0),
            Metrica("Esmagamento R_n", rn_contato / 1000.0, "kN", 0),
            Metrica("Largura efetiva b_e", be, "mm", 1),
            Metrica("Tensão na base", vm_base, "MPa", 1),
            Metrica("Tensão na solda", f_solda, "MPa", 1),
        ),
        verificacoes=tuple(verificacoes),
        alertas=tuple(alertas),
        hipoteses=(
            "Carga no plano do olhal; resistências nominais da AISC 360-16 (D5 e J7).",
            "O fator mínimo informado substitui o Ω da AISC quando for maior. Em içamento, o fator "
            "padrão é mais alto que o de estrutura comum.",
            "A ASME BTH-1, própria para olhais de içamento, não está aplicada aqui. Se ela for "
            "exigida no projeto, faça essa verificação à parte.",
            "O pino é verificado no caso Pino de articulação.",
        ),
        referencias=(f"{AISC}, D2, D5, J2 e J7",),
        envios=(
            Envio(
                "pino_articulacao",
                "Verificar o pino do olhal",
                {
                    "forca_kN": float(v["forca_kN"]),
                    "fator_dinamico": float(v["fator_dinamico"]),
                    "d_mm": d_p,
                    "t_olhal_mm": t,
                },
            ),
        ),
    )


CAMPOS_OLHAL = (
    Campo(
        "forca_kN",
        "Carga no olhal",
        "A força nominal que chega a este olhal, sem coeficiente dinâmico. Com várias lingas, "
        "use a força em uma delas.",
        50.0,
        "kN",
        minimo=0.001,
        passo=5.0,
        secao="Carga",
    ),
    Campo(
        "fator_dinamico",
        "Fator dinâmico",
        "Multiplica a carga. Use o ψ da NBR 8400 (caso Ações de içamento). Içamento lento e "
        "controlado: cerca de 1,15.",
        1.15,
        minimo=1.0,
        maximo=4.0,
        passo=0.05,
        secao="Carga",
    ),
    Campo(
        "fs_minimo",
        "Fator mínimo sobre a resistência nominal",
        "Margem sobre a ruptura. Em peça de içamento, comece com 3. O programa usa o maior entre "
        "este valor e o Ω da AISC.",
        3.0,
        minimo=1.67,
        maximo=8.0,
        passo=0.1,
        secao="Carga",
    ),
    Campo(
        "angulo_graus",
        "Inclinação da carga",
        "Ângulo entre a força e a vertical, no plano do olhal. Lingas abertas inclinam a carga.",
        0.0,
        "°",
        minimo=0.0,
        maximo=60.0,
        passo=5.0,
        secao="Carga",
    ),
    Campo(
        "t_mm",
        "Espessura da chapa t",
        "Espessura do olhal. Com chapas de reforço soldadas, some as espessuras.",
        20.0,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Geometria",
    ),
    Campo(
        "w_mm",
        "Largura no furo w",
        "Largura do olhal na linha do furo, perpendicular à força.",
        150.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Geometria",
    ),
    Campo(
        "d_pino_mm",
        "Diâmetro do pino",
        "Diâmetro do pino da manilha.",
        32.0,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Geometria",
    ),
    Campo(
        "d_furo_mm",
        "Diâmetro do furo",
        "Diâmetro do furo do olhal. Se o pino gira sob carga, a folga não passa de 1 mm.",
        33.0,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Geometria",
    ),
    Campo(
        "a_mm",
        "Distância a à frente do furo",
        "Da borda do furo até a borda da chapa, no sentido da força.",
        90.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Geometria",
    ),
    Campo(
        "gira_sob_carga",
        "O pino gira sob carga",
        "Ligue quando o pino gira no furo com a carga aplicada: a folga fica limitada a 1 mm.",
        False,
        secao="Geometria",
    ),
    Campo(
        "h_mm",
        "Altura do furo à base",
        "Do centro do furo até a base soldada. É o braço da parcela horizontal da força.",
        100.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Base",
    ),
    Campo(
        "base_mm",
        "Comprimento da base L",
        "Comprimento da chapa na linha da solda.",
        200.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Base",
    ),
    Campo(
        "solda_mm",
        "Perna do filete s",
        "Perna do filete de solda nos dois lados da chapa.",
        8.0,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Base",
    ),
    Campo(
        "fexx_MPa",
        "Resistência do eletrodo F_EXX",
        "Eletrodo E70: 485 MPa.",
        485.0,
        "MPa",
        minimo=300.0,
        passo=10.0,
        secao="Base",
    ),
    Campo(
        "fy_MPa",
        "Escoamento F_y",
        "Limite de escoamento da chapa. ASTM A36: 250 MPa. ASTM A572 Gr. 50: 345 MPa.",
        345.0,
        "MPa",
        minimo=100.0,
        passo=5.0,
        secao="Material",
    ),
    Campo(
        "fu_MPa",
        "Ruptura F_u",
        "Limite de resistência da chapa. ASTM A36: 400 MPa. ASTM A572 Gr. 50: 450 MPa.",
        450.0,
        "MPa",
        minimo=100.0,
        passo=5.0,
        secao="Material",
    ),
)


CASOS: tuple[Caso, ...] = (
    Caso(
        "acoes_icamento",
        "Ações de içamento",
        GRUPO,
        "Coeficiente dinâmico ψ e majoração M_x: a carga de cálculo do equipamento.",
        "Da carga útil à solicitação de cálculo do caso I da NBR 8400: ψ pela velocidade de "
        "elevação, M_x pelo grupo da estrutura.",
        CAMPOS_ACOES,
        calcular_acoes,
        r"S=M_x\,(S_G+\psi\,S_L+S_H)",
    ),
    Caso(
        "cabo_tambor",
        "Cabo, tambor e polias",
        GRUPO,
        "NBR 8400: diâmetro do cabo, de tambor e polias pelo grupo; ruptura pela NBR 6327.",
        "Sai a tração no cabo com o rendimento do moitão, o cabo mínimo e os enrolamentos "
        "mínimos, e a comparação com o que foi escolhido.",
        CAMPOS_CABO,
        calcular_cabo,
        r"d_c=Q\sqrt{T},\qquad D_e\ge H_1\,H_2\,d_c",
    ),
    Caso(
        "roda_ponte",
        "Roda de ponte rolante",
        GRUPO,
        "NBR 8400: pressão entre roda e trilho, casos I, II e III.",
        "Confere a roda pela pressão limite da norma, com a rotação, o material e o grupo do "
        "mecanismo.",
        CAMPOS_RODA,
        calcular_roda,
        r"\frac{F_r}{b\,D}\le P_{lim}\,c_1\,c_2,\qquad F_r=\frac{F_{min}+2F_{max}}{3}",
    ),
    Caso(
        "mecanismo_nbr8400",
        "Peça de mecanismo",
        GRUPO,
        "NBR 8400: tensão admissível sobre a ruptura, casos I, II e III, e fadiga.",
        "Para eixos e peças de mecanismos de içamento. Em vez do escoamento, a norma usa a "
        "ruptura, com q pelo grupo e FS_r pelo caso de solicitação.",
        CAMPOS_MECANISMO,
        calcular_mecanismo,
        r"\sigma_a=\frac{\sigma_r}{q\,FS_r},\qquad "
        r"\sqrt{(1{,}25\sigma_t+\sigma_f)^2+3\tau^2}\le\sigma_a",
    ),
    Caso(
        "gancho",
        "Gancho e peça curva",
        GRUPO,
        "Viga curva de Winkler-Bach: seção retangular, circular ou trapezoidal.",
        "Em peça curva a linha neutra sai do centroide e a fibra interna sofre mais do que a "
        "fórmula de viga reta mostra.",
        CAMPOS_GANCHO,
        calcular_gancho,
        r"\sigma=\frac{F}{A}+\frac{M(r_n-r)}{A\,e\,r},\qquad e=r_c-r_n",
    ),
    Caso(
        "olhal",
        "Olhal de içamento",
        GRUPO,
        "AISC 360-16 D5: tração, rasgamento, esmagamento, base e solda.",
        "Verifica a chapa com furo para manilha, a base e a solda, com um fator mínimo próprio "
        "para içamento.",
        CAMPOS_OLHAL,
        calcular_olhal,
        r"R_n=F_u\,2t\,b_e,\quad R_n=0{,}6F_u\,2t\left(a+\frac{d}{2}\right),\quad "
        r"R_n=1{,}8F_y\,t\,d",
    ),
)
