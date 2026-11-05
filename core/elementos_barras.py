"""Barras: força axial, torção, coluna simples, treliça plana e pórtico simples.

Barra em trechos e treliça têm solução direta por rigidez, aqui mesmo. O pórtico usa o núcleo
:mod:`core.portico_plano`, o mesmo da longarina de escada, e os desenhos no estilo do Ftool.

Sinal: tração positiva. Nas barras em trechos, a força ou o torque vale no fim do trecho, medido a
partir da ponta presa da esquerda.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from core import column_design as cd
from core import portico_figuras as pf
from core import portico_plano as pp
from core.beam_charts import COR_FLECHA, COR_NORMAL, COR_TORQUE
from core.desenho_estatica import figura_da_barra, figura_da_trelica
from core.elementos_base import (
    Campo,
    Caso,
    Coluna,
    Envio,
    Figura,
    Grafico,
    Metrica,
    Resultado,
    Tabela,
    Valores,
    exigir,
    informativo,
    limite,
    recomendacao,
)
from core.elementos_vigas import (
    campos_de_material,
    campos_de_secao,
    nomes_dos_perfis,
    secao_do_caso,
)
from core.verificacao import Verificacao

GRUPO = "Barras e estruturas"

HIBBELER = "Hibbeler, Resistência dos Materiais"
SHIGLEY_4 = "Shigley, Elementos de Máquinas, cap. 4"
NBR_E1 = "ABNT NBR 8800:2008, Tabela E.1"

KS = {
    "Articulada nas duas pontas (K = 1,0)": cd.K_recomendado("rotula-rotula"),
    "Engastada e livre (K = 2,1)": cd.K_recomendado("engaste-livre"),
    "Engastada e articulada (K = 0,80)": cd.K_recomendado("engaste-rotula"),
    "Engastada nas duas pontas (K = 0,65)": cd.K_recomendado("engaste-engaste"),
}


# ---------------------------------------------------------------------------
# Corrente de trechos, em força axial ou em torção
# ---------------------------------------------------------------------------


def resolver_corrente(
    rigidezes: Sequence[float],
    cargas: Sequence[float],
    iniciais: Sequence[float],
    *,
    presa_nas_duas: bool,
) -> tuple[list[float], list[float], float, float]:
    """Trechos em série, presos à esquerda e, se pedido, também à direita.

    ``iniciais`` é a força interna de cada trecho com os nós parados (térmica); ``cargas`` é a
    carga no fim de cada trecho. Devolve os deslocamentos dos nós (o primeiro é zero), o esforço
    interno de cada trecho e as reações das duas pontas, com sinal de força sobre a barra.
    """
    n = len(rigidezes)
    livres = n - 1 if presa_nas_duas else n
    deslocamentos = [0.0] * (n + 1)
    if livres > 0:
        k = np.zeros((livres, livres))
        f = np.array(cargas[:livres], dtype=float)
        for e, rigidez in enumerate(rigidezes):
            # Os nós livres contam do primeiro depois da ponta presa: o trecho e liga e − 1 a e.
            esquerda, direita = e - 1, e
            if esquerda >= 0:
                k[esquerda, esquerda] += rigidez
                f[esquerda] -= iniciais[e]
            if direita < livres:
                k[direita, direita] += rigidez
                f[direita] += iniciais[e]
            if esquerda >= 0 and direita < livres:
                k[esquerda, direita] -= rigidez
                k[direita, esquerda] -= rigidez
        solucao = np.linalg.solve(k, f)
        for no in range(livres):
            deslocamentos[no + 1] = float(solucao[no])
    esforcos = [
        rigidez * (deslocamentos[e + 1] - deslocamentos[e]) - iniciais[e]
        for e, rigidez in enumerate(rigidezes)
    ]
    reacao_esquerda = -esforcos[0]
    reacao_direita = esforcos[-1] - cargas[-1] if presa_nas_duas else 0.0
    return deslocamentos, esforcos, reacao_esquerda, reacao_direita


def _degraus(
    comprimentos: Sequence[float], valores: Sequence[float], nome: str, escala: float = 1.0
) -> tuple[tuple[float, float, str], ...]:
    pontos: list[tuple[float, float, str]] = []
    x = 0.0
    for comprimento, valor in zip(comprimentos, valores, strict=True):
        pontos.append((x, valor * escala, nome))
        x += comprimento
        pontos.append((x, valor * escala, nome))
    return tuple(pontos)


def _linha_quebrada(
    comprimentos: Sequence[float], valores: Sequence[float], nome: str
) -> tuple[tuple[float, float, str], ...]:
    pontos = [(0.0, valores[0], nome)]
    x = 0.0
    for comprimento, valor in zip(comprimentos, valores[1:], strict=True):
        x += comprimento
        pontos.append((x, valor, nome))
    return tuple(pontos)


PRESA_ESQUERDA = "Presa só na ponta esquerda"
PRESA_DUAS = "Presa nas duas pontas"


# ---------------------------------------------------------------------------
# Barra axial
# ---------------------------------------------------------------------------


def calcular_barra_axial(v: Valores) -> Resultado:
    trechos: Sequence[Mapping[str, Any]] = v["trechos"]
    exigir(len(trechos) >= 1, "Informe ao menos um trecho na tabela.")
    presa_duas = v["apoio"] == PRESA_DUAS
    comprimentos = [float(t["l_mm"]) for t in trechos]
    areas = [float(t["a_mm2"]) for t in trechos]
    modulos = [float(t["e_GPa"]) * 1000.0 for t in trechos]
    cargas = [float(t["f_kN"]) * 1000.0 for t in trechos]
    sy = float(v["sy_MPa"])
    fs = float(v["fs"])
    delta_t = float(v["dt_C"])
    alfa = float(v["alfa"]) * 1e-6
    rigidezes = [a * e / l for a, e, l in zip(areas, modulos, comprimentos, strict=True)]
    iniciais = [a * e * alfa * delta_t for a, e in zip(areas, modulos, strict=True)]
    desloc, esforcos, r_esq, r_dir = resolver_corrente(
        rigidezes, cargas, iniciais, presa_nas_duas=presa_duas
    )
    tensoes = [n / a for n, a in zip(esforcos, areas, strict=True)]
    alongamentos = [desloc[i + 1] - desloc[i] for i in range(len(trechos))]
    admissivel = sy / fs
    indice = max(range(len(tensoes)), key=lambda i: abs(tensoes[i]))

    linhas = tuple(
        {
            "Trecho": i + 1,
            "Esforço N (kN)": esforcos[i] / 1000.0,
            "Regime": "Tração"
            if esforcos[i] > 1e-9
            else "Compressão"
            if esforcos[i] < -1e-9
            else "Sem força",
            "Tensão (MPa)": tensoes[i],
            "Alongamento (mm)": alongamentos[i],
            "Deslocamento no fim (mm)": desloc[i + 1],
        }
        for i in range(len(trechos))
    )
    verificacoes = [
        limite(
            f"Tensão no trecho {indice + 1}",
            abs(tensoes[indice]),
            admissivel,
            "MPa",
            f"σ = N/A; limite S_y/FS = {sy:.0f}/{fs:.2f}",
            HIBBELER,
        ),
        informativo(
            "Soma das forças e das reações",
            round(abs(sum(cargas) + r_esq + r_dir) / 1000.0, 6),
            "kN",
            "Deve ser zero: confere o equilíbrio da barra",
            HIBBELER,
        ),
    ]
    alertas: list[str] = []
    envios: list[Envio] = []
    comprimidos = [i for i, n in enumerate(esforcos) if n < -1e-9]
    if comprimidos:
        pior = min(comprimidos, key=lambda i: esforcos[i])
        alertas.append(
            f"O trecho {pior + 1} está comprimido com {abs(esforcos[pior]) / 1000:.1f} kN. Barra "
            "comprimida pode flambar antes de escoar: confira no caso Coluna simples."
        )
        envios.append(
            Envio(
                "coluna_simples",
                "Conferir a flambagem do trecho comprimido",
                {"p_kN": abs(esforcos[pior]) / 1000.0, "l_m": comprimentos[pior] / 1000.0},
            )
        )
    figura = figura_da_barra(
        comprimentos,
        areas,
        [n / 1000.0 for n in esforcos],
        [c / 1000.0 for c in cargas],
        presa_nas_duas=presa_duas,
        unidade_esforco="kN",
        unidade_carga="kN",
        titulo="Barra sob força axial",
    )
    metricas = [
        Metrica("Reação à esquerda", r_esq / 1000.0, "kN"),
        Metrica("Maior tensão", abs(tensoes[indice]), "MPa", 1),
        Metrica("Deslocamento no fim", desloc[-1], "mm", 3),
        Metrica("Alongamento máximo", max(alongamentos, key=abs), "mm", 3),
    ]
    if presa_duas:
        metricas.insert(1, Metrica("Reação à direita", r_dir / 1000.0, "kN"))
        metricas[3] = Metrica("Maior deslocamento", max(desloc, key=abs), "mm", 3)
    return Resultado(
        resumo=(
            f"Maior tensão de {abs(tensoes[indice]):.1f} MPa no trecho {indice + 1}, e "
            f"deslocamento máximo de {abs(max(desloc, key=abs)):.3f} mm."
        ),
        metricas=tuple(metricas),
        verificacoes=tuple(verificacoes),
        tabelas=(Tabela("Trecho a trecho", linhas),),
        graficos=(
            Grafico(
                "Esforço normal ao longo da barra",
                "Posição x (mm)",
                "N (kN)",
                _degraus(comprimentos, esforcos, "Esforço", 1e-3),
                area=True,
                cor=COR_NORMAL,
            ),
            Grafico(
                "Deslocamento ao longo da barra",
                "Posição x (mm)",
                "u (mm)",
                _linha_quebrada(comprimentos, desloc, "Deslocamento"),
                area=True,
                cor=COR_FLECHA,
            ),
        ),
        figuras=(Figura("Barra", figura.png, "Trechos com o esforço de cada um, em escala."),),
        alertas=tuple(alertas),
        hipoteses=(
            "Trechos prismáticos, com a carga no eixo da barra. Perto das mudanças de seção e dos "
            "pontos de carga a tensão local é maior.",
            "Material elástico e linear.",
            "Força positiva para a direita, aplicada no fim do trecho da mesma linha. As reações "
            "seguem o mesmo sinal: negativa aponta para a esquerda.",
        ),
        referencias=(HIBBELER,),
        envios=tuple(envios),
    )


CAMPOS_BARRA_AXIAL: tuple[Campo, ...] = (
    Campo(
        "apoio",
        "Como a barra está presa",
        "Presa nas duas pontas, a barra não consegue alongar livre: as reações dependem da "
        "rigidez dos trechos.",
        PRESA_ESQUERDA,
        opcoes=(PRESA_ESQUERDA, PRESA_DUAS),
        secao="Barra",
    ),
    Campo(
        "trechos",
        "Trechos",
        "Uma linha por trecho, da esquerda para a direita. A força vale no fim do trecho, positiva "
        "para a direita. Barra redonda de 20 mm: 314 mm².",
        (
            {"l_mm": 500.0, "a_mm2": 800.0, "e_GPa": 200.0, "f_kN": 0.0},
            {"l_mm": 300.0, "a_mm2": 400.0, "e_GPa": 200.0, "f_kN": 40.0},
        ),
        secao="Barra",
        colunas=(
            Coluna("l_mm", "Comprimento", "Comprimento do trecho.", 300.0, "mm", minimo=0.01),
            Coluna("a_mm2", "Área", "Área da seção do trecho.", 400.0, "mm²", minimo=0.01),
            Coluna(
                "e_GPa",
                "E",
                "Módulo de elasticidade. Aço: 200 GPa. Alumínio: 70 GPa.",
                200.0,
                "GPa",
                minimo=0.1,
            ),
            Coluna(
                "f_kN",
                "Força no fim",
                "Força aplicada no fim do trecho. Positiva para a direita.",
                0.0,
                "kN",
            ),
        ),
    ),
    Campo(
        "dt_C",
        "Variação de temperatura",
        "Aumento de temperatura da barra inteira. Só gera tensão se a barra estiver presa nas "
        "duas pontas.",
        0.0,
        "°C",
        passo=5.0,
        secao="Temperatura",
    ),
    Campo(
        "alfa",
        "Dilatação térmica",
        "Em milionésimos por grau. Aço: 12. Alumínio: 23.",
        12.0,
        "10⁻⁶/°C",
        minimo=0.0,
        passo=1.0,
        secao="Temperatura",
    ),
    Campo(
        "sy_MPa",
        "Escoamento do material",
        "Limite de escoamento do material mais fraco da barra.",
        250.0,
        "MPa",
        minimo=1.0,
        passo=10.0,
        secao="Limites",
    ),
    Campo(
        "fs",
        "Fator de segurança",
        "A tensão admissível é o escoamento dividido por este fator. Comece com 1,5.",
        1.5,
        minimo=1.0,
        maximo=6.0,
        passo=0.1,
        secao="Limites",
    ),
)


# ---------------------------------------------------------------------------
# Barra em torção
# ---------------------------------------------------------------------------


def calcular_barra_torcao(v: Valores) -> Resultado:
    trechos: Sequence[Mapping[str, Any]] = v["trechos"]
    exigir(len(trechos) >= 1, "Informe ao menos um trecho na tabela.")
    presa_duas = v["apoio"] == PRESA_DUAS
    g = float(v["g_GPa"]) * 1000.0
    sy = float(v["sy_MPa"])
    fs = float(v["fs"])
    limite_giro = float(v["giro_limite"])
    comprimentos = [float(t["l_mm"]) for t in trechos]
    externos = [float(t["d_mm"]) for t in trechos]
    internos = [0.0 if t["di_mm"] is None else float(t["di_mm"]) for t in trechos]
    torques = [float(t["t_Nm"]) * 1000.0 for t in trechos]
    for numero, (d, di) in enumerate(zip(externos, internos, strict=True), start=1):
        exigir(di < d, f"Trecho {numero}: o diâmetro interno precisa ser menor que o externo.")
    inercias = [math.pi * (d**4 - di**4) / 32.0 for d, di in zip(externos, internos, strict=True)]
    rigidezes = [g * j / l for j, l in zip(inercias, comprimentos, strict=True)]
    giros, esforcos, r_esq, r_dir = resolver_corrente(
        rigidezes, torques, [0.0] * len(trechos), presa_nas_duas=presa_duas
    )
    tensoes = [abs(t) * (d / 2.0) / j for t, d, j in zip(esforcos, externos, inercias, strict=True)]
    relativos = [giros[i + 1] - giros[i] for i in range(len(trechos))]
    por_metro = [
        abs(math.degrees(rel)) / (l / 1000.0)
        for rel, l in zip(relativos, comprimentos, strict=True)
    ]
    admissivel = 0.577 * sy / fs
    indice = max(range(len(tensoes)), key=lambda i: tensoes[i])
    pior_giro = max(range(len(por_metro)), key=lambda i: por_metro[i])
    giro_maximo = max(giros, key=abs)

    verificacoes = [
        limite(
            f"Cisalhamento no trecho {indice + 1}",
            tensoes[indice],
            admissivel,
            "MPa",
            f"τ = T·r/J; limite 0.577·S_y/FS = 0.577·{sy:.0f}/{fs:.2f}",
            HIBBELER,
        ),
        recomendacao(
            f"Giro por metro no trecho {pior_giro + 1}",
            por_metro[pior_giro],
            limite_giro,
            "°/m",
            "θ/L = T/(G·J)",
            "Prática de projeto de eixos",
        ),
        informativo(
            "Soma dos torques e das reações",
            round(abs(sum(torques) + r_esq + r_dir) / 1000.0, 6),
            "N·m",
            "Deve ser zero: confere o equilíbrio da barra",
            HIBBELER,
        ),
    ]
    linhas = tuple(
        {
            "Trecho": i + 1,
            "Torque (N·m)": esforcos[i] / 1000.0,
            "Tensão (MPa)": tensoes[i],
            "Giro no trecho (°)": math.degrees(relativos[i]),
            "Giro por metro (°/m)": por_metro[i],
            "Giro no fim (°)": math.degrees(giros[i + 1]),
        }
        for i in range(len(trechos))
    )
    figura = figura_da_barra(
        comprimentos,
        externos,
        [t / 1000.0 for t in esforcos],
        [t / 1000.0 for t in torques],
        presa_nas_duas=presa_duas,
        unidade_esforco="N·m",
        unidade_carga="N·m",
        titulo="Barra em torção",
        legenda="Trechos com o torque de cada um.",
        torque=True,
    )
    metricas = [
        Metrica("Reação à esquerda", r_esq / 1000.0, "N·m", 1),
        Metrica("Maior tensão", tensoes[indice], "MPa", 1),
        Metrica("Giro máximo", math.degrees(giro_maximo), "°", 3),
        Metrica("Maior giro por metro", por_metro[pior_giro], "°/m", 3),
    ]
    if presa_duas:
        metricas.insert(1, Metrica("Reação à direita", r_dir / 1000.0, "N·m", 1))
    return Resultado(
        resumo=(
            f"Maior cisalhamento de {tensoes[indice]:.1f} MPa no trecho {indice + 1}, e giro de "
            f"{abs(math.degrees(giro_maximo)):.3f}° na ponta mais girada."
        ),
        metricas=tuple(metricas),
        verificacoes=tuple(verificacoes),
        tabelas=(Tabela("Trecho a trecho", linhas),),
        graficos=(
            Grafico(
                "Torque ao longo da barra",
                "Posição x (mm)",
                "T (N·m)",
                _degraus(comprimentos, esforcos, "Torque", 1e-3),
                area=True,
                cor=COR_TORQUE,
            ),
            Grafico(
                "Giro ao longo da barra",
                "Posição x (mm)",
                "θ (°)",
                _linha_quebrada(comprimentos, [math.degrees(g_) for g_ in giros], "Giro"),
                area=True,
                cor=COR_FLECHA,
            ),
        ),
        figuras=(Figura("Barra", figura.png, "Trechos com o torque de cada um, em escala."),),
        hipoteses=(
            "Seção circular maciça ou tubular. Para outras seções, use os casos de torção de "
            "seção.",
            "Torque aplicado no fim do trecho da mesma linha. Perto de ressaltos, a tensão local "
            "é maior: veja o caso Eixo: seção crítica à fadiga.",
            "Material elástico e linear.",
        ),
        referencias=(HIBBELER, SHIGLEY_4),
    )


CAMPOS_BARRA_TORCAO: tuple[Campo, ...] = (
    Campo(
        "apoio",
        "Como a barra está presa",
        "Presa nas duas pontas, cada ponta recebe uma parte do torque, conforme a rigidez.",
        PRESA_ESQUERDA,
        opcoes=(PRESA_ESQUERDA, PRESA_DUAS),
        secao="Barra",
    ),
    Campo(
        "trechos",
        "Trechos",
        "Uma linha por trecho, da esquerda para a direita. O torque vale no fim do trecho. Barra "
        "maciça: deixe o diâmetro interno vazio.",
        (
            {"l_mm": 400.0, "d_mm": 50.0, "di_mm": None, "t_Nm": 0.0},
            {"l_mm": 300.0, "d_mm": 40.0, "di_mm": None, "t_Nm": 300.0},
        ),
        secao="Barra",
        colunas=(
            Coluna("l_mm", "Comprimento", "Comprimento do trecho.", 300.0, "mm", minimo=0.01),
            Coluna(
                "d_mm", "Diâmetro externo", "Diâmetro externo do trecho.", 40.0, "mm", minimo=0.01
            ),
            Coluna(
                "di_mm",
                "Diâmetro interno",
                "Só para tubo. Vazio é barra maciça.",
                None,
                "mm",
                minimo=0.0,
                opcional=True,
            ),
            Coluna(
                "t_Nm",
                "Torque no fim",
                "Torque aplicado no fim do trecho, com sinal para o sentido.",
                0.0,
                "N·m",
            ),
        ),
    ),
    Campo(
        "g_GPa",
        "Módulo de cisalhamento G",
        "Aço: 77 GPa. Alumínio: 26 GPa.",
        77.0,
        "GPa",
        minimo=0.1,
        passo=1.0,
        secao="Material e limites",
    ),
    Campo(
        "sy_MPa",
        "Escoamento do material",
        "Limite de escoamento do material.",
        250.0,
        "MPa",
        minimo=1.0,
        passo=10.0,
        secao="Material e limites",
    ),
    Campo(
        "fs",
        "Fator de segurança",
        "Margem sobre o escoamento ao cisalhamento. Comece com 1,5.",
        1.5,
        minimo=1.0,
        maximo=6.0,
        passo=0.1,
        secao="Material e limites",
    ),
    Campo(
        "giro_limite",
        "Giro máximo por metro",
        "Eixo de transmissão costuma ficar entre 0,25 e 1 grau por metro. Sem exigência de "
        "rigidez, use um valor alto.",
        1.0,
        "°/m",
        minimo=0.01,
        passo=0.25,
        secao="Material e limites",
    ),
)


# ---------------------------------------------------------------------------
# Coluna simples
# ---------------------------------------------------------------------------


def carga_critica(
    area: float, raio: float, comprimento_efetivo: float, sy: float, e: float
) -> float:
    """Euler para coluna longa e Johnson para coluna intermediária (Shigley 4-43 e 4-48)."""
    esbeltez = comprimento_efetivo / raio
    transicao = math.sqrt(2.0 * math.pi**2 * e / sy)
    if esbeltez >= transicao:
        return math.pi**2 * e * area / esbeltez**2
    return area * (sy - (sy * esbeltez / (2.0 * math.pi)) ** 2 / e)


def calcular_coluna(v: Valores) -> Resultado:
    secao = secao_do_caso({**v, "eixo": "x"})
    p = float(v["p_kN"]) * 1000.0
    comprimento = float(v["l_m"]) * 1000.0
    k = KS[str(v["condicao"])]
    sy = float(v["sy_MPa"])
    e = float(v["e_GPa"]) * 1000.0
    fs = float(v["fs"])
    area = secao.area_mm2
    raio = secao.r_min_mm
    efetivo = k * comprimento
    esbeltez = efetivo / raio
    transicao = math.sqrt(2.0 * math.pi**2 * e / sy)
    longa = esbeltez >= transicao
    modo = "Euler, coluna longa" if longa else "Johnson, coluna intermediária"
    critica = carga_critica(area, raio, efetivo, sy, e)
    alertas: list[str] = []
    if secao.perfil is not None:
        alertas.append(
            "Esta é a conta clássica de elementos de máquinas. Para barra de estrutura de aço, a "
            "norma tem curva própria, mais baixa, com flambagem local e por torção: use o caso "
            "Perfil de aço ou a página Flambagem de colunas."
        )
    linhas_l = [comprimento * i / 60.0 for i in range(6, 121)]
    curva = tuple(
        (x / 1000.0, carga_critica(area, raio, k * x, sy, e) / fs / 1000.0, "Carga admissível")
        for x in linhas_l
    )
    return Resultado(
        resumo=(
            f"A coluna aguenta {critica / fs / 1000:.1f} kN com FS = {fs:.2f}, pela fórmula de "
            f"{modo}. Esbeltez de {esbeltez:.0f}."
        ),
        metricas=(
            Metrica("Carga crítica", critica / 1000.0, "kN", 1),
            Metrica("Carga admissível", critica / fs / 1000.0, "kN", 1),
            Metrica("Esbeltez K·L/r", esbeltez, "", 0),
            Metrica("Raio de giração mínimo", raio, "mm", 1),
            Metrica("Fator K", k, "", 2),
        ),
        verificacoes=(
            limite(
                "Flambagem",
                fs * p / 1000.0,
                critica / 1000.0,
                "kN",
                f"FS·P ≤ P_cr; {modo}",
                f"{SHIGLEY_4}, Eq. 4-43 e 4-48",
            ),
            limite(
                "Compressão simples",
                p / area,
                sy / fs,
                "MPa",
                "σ = P/A; limite S_y/FS",
                HIBBELER,
            ),
            recomendacao(
                "Esbeltez",
                esbeltez,
                200.0,
                "",
                "K·L/r ≤ 200",
                "ABNT NBR 8800, 5.3.4",
            ),
            informativo(
                "Esbeltez de transição",
                transicao,
                "",
                "(L/r)₁ = √(2π²E/S_y)",
                f"{SHIGLEY_4}, Eq. 4-46",
            ),
        ),
        graficos=(
            Grafico(
                "Carga admissível conforme o comprimento",
                "Comprimento L (m)",
                "P (kN)",
                curva,
                destaques=((comprimento / 1000.0, critica / fs / 1000.0, "esta coluna"),),
            ),
        ),
        alertas=tuple(alertas),
        hipoteses=(
            "Barra reta, de seção constante, com a carga no centro da seção.",
            "Flambagem por flexão em torno do eixo de menor inércia. Flambagem local e por torção "
            "ficam de fora.",
            f"Valores de K da {NBR_E1}, que já consideram que o engaste real não é perfeito.",
            "Excentricidade e flexão junto com a compressão: use o caso Perfil de aço.",
        ),
        referencias=(SHIGLEY_4, NBR_E1, HIBBELER),
    )


CAMPOS_COLUNA: tuple[Campo, ...] = (
    Campo(
        "p_kN",
        "Força de compressão",
        "Força axial de serviço.",
        60.0,
        "kN",
        minimo=0.0,
        passo=5.0,
        secao="Coluna",
    ),
    Campo(
        "l_m",
        "Comprimento",
        "Distância entre os apoios.",
        2.0,
        "m",
        minimo=0.01,
        passo=0.25,
        secao="Coluna",
    ),
    Campo(
        "condicao",
        "Como as pontas estão presas",
        "Define o fator K. Na dúvida, use a condição mais livre.",
        "Articulada nas duas pontas (K = 1,0)",
        opcoes=tuple(KS),
        secao="Coluna",
    ),
    *campos_de_secao(com_eixo=False, perfil_padrao="TR ideal 100×50×3"),
    *campos_de_material(),
)


# ---------------------------------------------------------------------------
# Treliça plana
# ---------------------------------------------------------------------------

LIVRE = "Livre"
PINO = "Pino"
ROLETE_Y = "Rolete que segura Y"
ROLETE_X = "Rolete que segura X"
APOIOS_DE_NO = (LIVRE, PINO, ROLETE_Y, ROLETE_X)


@dataclass(frozen=True)
class ResultadoTrelica:
    deslocamentos: dict[str, tuple[float, float]]  # mm
    forcas: tuple[float, ...]  # kN, na ordem das barras, tração positiva
    comprimentos: tuple[float, ...]  # m
    reacoes: dict[str, tuple[float, float]]  # kN
    hiperestatica: int


def resolver_trelica(
    nos: Sequence[Mapping[str, Any]],
    barras: Sequence[Mapping[str, Any]],
    ea_kn: float,
) -> ResultadoTrelica:
    nomes = [str(n["nome"]) for n in nos]
    exigir(len(set(nomes)) == len(nomes), "Há nós com o mesmo nome na tabela de nós.")
    indice = {nome: i for i, nome in enumerate(nomes)}
    gdl = 2 * len(nos)
    coordenadas = [(float(n["x_m"]), float(n["y_m"])) for n in nos]
    vistos: set[frozenset[str]] = set()
    pares: list[tuple[int, int]] = []
    for numero, barra in enumerate(barras, start=1):
        a, b = str(barra["i"]), str(barra["j"])
        exigir(
            a in indice and b in indice,
            f"Barra {numero}: use nomes de nós da tabela de nós ({a} e {b}).",
        )
        exigir(a != b, f"Barra {numero}: os dois nós são o mesmo.")
        par = frozenset((a, b))
        exigir(par not in vistos, f"Barra {numero}: já existe uma barra entre {a} e {b}.")
        vistos.add(par)
        pares.append((indice[a], indice[b]))

    k = np.zeros((gdl, gdl))
    f = np.zeros(gdl)
    geometria: list[tuple[float, float, float]] = []
    for numero, (i, j) in enumerate(pares, start=1):
        dx = coordenadas[j][0] - coordenadas[i][0]
        dy = coordenadas[j][1] - coordenadas[i][1]
        comprimento = math.hypot(dx, dy)
        exigir(comprimento > 1e-9, f"Barra {numero}: os dois nós estão no mesmo lugar.")
        c, s = dx / comprimento, dy / comprimento
        geometria.append((c, s, comprimento))
        local = ea_kn / comprimento * np.outer([-c, -s, c, s], [-c, -s, c, s])
        graus = [2 * i, 2 * i + 1, 2 * j, 2 * j + 1]
        k[np.ix_(graus, graus)] += local

    presos: list[int] = []
    for i, no in enumerate(nos):
        tipo = no["apoio"]
        if tipo in (PINO, ROLETE_X):
            presos.append(2 * i)
        if tipo in (PINO, ROLETE_Y):
            presos.append(2 * i + 1)
        f[2 * i] += float(no["fx_kN"])
        f[2 * i + 1] += float(no["fy_kN"])

    exigir(len(presos) >= 3, "A treliça precisa de ao menos três restrições: um pino e um rolete.")
    livres = [g for g in range(gdl) if g not in presos]
    escala = ea_kn / max(g[2] for g in geometria)
    if livres:
        reduzida = k[np.ix_(livres, livres)] / escala
        if np.linalg.matrix_rank(reduzida, tol=1e-9) < len(livres):
            raise ValueError(
                "A treliça não é estável: faltam barras ou apoios, e algum nó fica solto ou gira "
                "sem resistência. Confira se cada nó tem ao menos duas barras não alinhadas."
            )
        solucao = np.linalg.solve(k[np.ix_(livres, livres)], f[livres])
    else:
        solucao = np.zeros(0)
    u = np.zeros(gdl)
    u[livres] = solucao
    reacoes_vetor = k @ u - f

    # O arredondamento tira o resíduo da solução (1e-15): barra sem força tem que mostrar zero.
    forcas: list[float] = []
    for (i, j), (c, s, comprimento) in zip(pares, geometria, strict=True):
        delta = (u[2 * j] - u[2 * i]) * c + (u[2 * j + 1] - u[2 * i + 1]) * s
        forcas.append(round(float(ea_kn * delta / comprimento), 9))
    reacoes = {
        str(n["nome"]): (
            round(float(reacoes_vetor[2 * i]), 9) if 2 * i in presos else 0.0,
            round(float(reacoes_vetor[2 * i + 1]), 9) if 2 * i + 1 in presos else 0.0,
        )
        for i, n in enumerate(nos)
        if n["apoio"] != LIVRE
    }
    deslocamentos = {
        str(n["nome"]): (float(u[2 * i]) * 1000.0, float(u[2 * i + 1]) * 1000.0)
        for i, n in enumerate(nos)
    }
    return ResultadoTrelica(
        deslocamentos,
        tuple(forcas),
        tuple(g[2] for g in geometria),
        reacoes,
        len(pares) + len(presos) - gdl,
    )


def calcular_trelica(v: Valores) -> Resultado:
    secao = secao_do_caso({**v, "eixo": "x"})
    nos: Sequence[Mapping[str, Any]] = v["nos"]
    barras: Sequence[Mapping[str, Any]] = v["barras"]
    exigir(len(nos) >= 2 and len(barras) >= 1, "Informe os nós e ao menos uma barra.")
    area = secao.area_mm2
    e_mpa = float(v["e_GPa"]) * 1000.0
    sy = float(v["sy_MPa"])
    fs = float(v["fs"])
    resposta = resolver_trelica(nos, barras, e_mpa * area / 1000.0)

    linhas = []
    pior_tracao: tuple[float, int] | None = None
    pior_compressao: tuple[float, int, float] | None = None
    for numero, (barra, forca, comprimento) in enumerate(
        zip(barras, resposta.forcas, resposta.comprimentos, strict=True), start=1
    ):
        if forca > 1e-9:
            regime = "Tração"
            capacidade = sy * area / fs / 1000.0
        elif forca < -1e-9:
            regime = "Compressão"
            critica = carga_critica(area, secao.r_min_mm, comprimento * 1000.0, sy, e_mpa)
            capacidade = critica / fs / 1000.0
        else:
            regime = "Sem força"
            capacidade = sy * area / fs / 1000.0
        uso = abs(forca) / capacidade
        if forca > 1e-9 and (pior_tracao is None or uso > pior_tracao[0]):
            pior_tracao = (uso, numero)
        if forca < -1e-9 and (pior_compressao is None or uso > pior_compressao[0]):
            pior_compressao = (uso, numero, capacidade)
        linhas.append(
            {
                "Barra": f"{barra['i']}-{barra['j']}",
                "L (m)": comprimento,
                "Força (kN)": forca,
                "Regime": regime,
                "Tensão (MPa)": forca * 1000.0 / area,
                "Limite (kN)": capacidade,
                "Aproveitamento (%)": uso * 100.0,
            }
        )
    verificacoes = []
    if pior_tracao is not None:
        linha = linhas[pior_tracao[1] - 1]
        verificacoes.append(
            limite(
                f"Barra tracionada {linha['Barra']}",
                float(linha["Força (kN)"]),  # type: ignore[arg-type]
                float(linha["Limite (kN)"]),  # type: ignore[arg-type]
                "kN",
                f"N ≤ S_y·A/FS = {sy:.0f}·{area:.0f}/{fs:.2f}",
                HIBBELER,
            )
        )
    if pior_compressao is not None:
        linha = linhas[pior_compressao[1] - 1]
        verificacoes.append(
            limite(
                f"Barra comprimida {linha['Barra']}",
                abs(float(linha["Força (kN)"])),  # type: ignore[arg-type]
                float(linha["Limite (kN)"]),  # type: ignore[arg-type]
                "kN",
                f"N ≤ P_cr/FS, com K = 1 e r = {secao.r_min_mm:.1f} mm",
                f"{SHIGLEY_4}, Eq. 4-43 e 4-48",
            )
        )
    maior_no = max(resposta.deslocamentos, key=lambda n: math.hypot(*resposta.deslocamentos[n]))
    maior_d = math.hypot(*resposta.deslocamentos[maior_no])
    alertas: list[str] = []
    if resposta.hiperestatica > 0:
        alertas.append(
            f"A treliça tem {resposta.hiperestatica} barra(s) ou apoio(s) a mais que o necessário: "
            "as forças dependem da rigidez, e a mesma seção foi usada em todas as barras."
        )
    apoios = {
        str(n["nome"]): "pino" if n["apoio"] == PINO else "rolete"
        for n in nos
        if n["apoio"] != LIVRE
    }
    cargas = {str(n["nome"]): (float(n["fx_kN"]), float(n["fy_kN"])) for n in nos}
    figura = figura_da_trelica(
        [(str(n["nome"]), float(n["x_m"]), float(n["y_m"])) for n in nos],
        [
            (str(b["i"]), str(b["j"]), forca)
            for b, forca in zip(barras, resposta.forcas, strict=True)
        ],
        apoios,
        cargas,
    )
    maior_tracao = max(resposta.forcas)
    maior_compressao = min(resposta.forcas)
    return Resultado(
        resumo=(
            f"Maior tração de {max(0.0, maior_tracao):.1f} kN, maior compressão de "
            f"{abs(min(0.0, maior_compressao)):.1f} kN e deslocamento de {maior_d:.2f} mm no nó "
            f"{maior_no}."
        ),
        metricas=(
            Metrica("Maior tração", max(0.0, maior_tracao), "kN", 1),
            Metrica("Maior compressão", abs(min(0.0, maior_compressao)), "kN", 1),
            Metrica("Maior deslocamento", maior_d, "mm"),
            Metrica("Barras", float(len(barras)), "", 0),
        ),
        verificacoes=tuple(verificacoes),
        tabelas=(
            Tabela("Força em cada barra", tuple(linhas), "Tração positiva."),
            Tabela(
                "Reações nos apoios",
                tuple(
                    {"Nó": nome, "Rx (kN)": rx, "Ry (kN)": ry}
                    for nome, (rx, ry) in resposta.reacoes.items()
                ),
                "Rx positiva para a direita e Ry para cima.",
            ),
            Tabela(
                "Deslocamento dos nós",
                tuple(
                    {"Nó": nome, "dx (mm)": dx, "dy (mm)": dy}
                    for nome, (dx, dy) in resposta.deslocamentos.items()
                ),
            ),
        ),
        figuras=(Figura("Treliça", figura.png, "Força em cada barra, em kN."),),
        alertas=tuple(alertas),
        hipoteses=(
            "Barras ligadas por pinos, com carga só nos nós: cada barra recebe só força axial.",
            "Todas as barras com a mesma seção e o mesmo material.",
            "Compressão por Euler e Johnson, com K = 1 e o comprimento entre nós. Flambagem local "
            "e ligações ficam de fora.",
            "Peso próprio não incluído: some nas cargas dos nós.",
        ),
        referencias=(HIBBELER, SHIGLEY_4),
    )


CAMPOS_TRELICA: tuple[Campo, ...] = (
    Campo(
        "nos",
        "Nós",
        "Uma linha por nó, com o nome, a posição, o apoio e as cargas. Fy negativa é para baixo.",
        (
            {"nome": "A", "x_m": 0.0, "y_m": 0.0, "apoio": PINO, "fx_kN": 0.0, "fy_kN": 0.0},
            {"nome": "B", "x_m": 2.0, "y_m": 0.0, "apoio": LIVRE, "fx_kN": 0.0, "fy_kN": -20.0},
            {"nome": "C", "x_m": 4.0, "y_m": 0.0, "apoio": LIVRE, "fx_kN": 0.0, "fy_kN": -20.0},
            {"nome": "D", "x_m": 6.0, "y_m": 0.0, "apoio": ROLETE_Y, "fx_kN": 0.0, "fy_kN": 0.0},
            {"nome": "E", "x_m": 2.0, "y_m": 2.0, "apoio": LIVRE, "fx_kN": 0.0, "fy_kN": 0.0},
            {"nome": "F", "x_m": 4.0, "y_m": 2.0, "apoio": LIVRE, "fx_kN": 0.0, "fy_kN": 0.0},
        ),
        secao="Geometria e cargas",
        colunas=(
            Coluna("nome", "Nó", "Nome curto do nó, usado na tabela de barras.", ""),
            Coluna("x_m", "x", "Posição horizontal.", 0.0, "m"),
            Coluna("y_m", "y", "Posição vertical.", 0.0, "m"),
            Coluna(
                "apoio",
                "Apoio",
                "Pino segura nas duas direções, e o rolete em uma só.",
                LIVRE,
                opcoes=APOIOS_DE_NO,
            ),
            Coluna("fx_kN", "Fx", "Carga horizontal no nó. Positiva para a direita.", 0.0, "kN"),
            Coluna("fy_kN", "Fy", "Carga vertical no nó. Positiva para cima.", 0.0, "kN"),
        ),
    ),
    Campo(
        "barras",
        "Barras",
        "Uma linha por barra, com os nomes dos dois nós.",
        (
            {"i": "A", "j": "B"},
            {"i": "B", "j": "C"},
            {"i": "C", "j": "D"},
            {"i": "A", "j": "E"},
            {"i": "E", "j": "F"},
            {"i": "F", "j": "D"},
            {"i": "B", "j": "E"},
            {"i": "C", "j": "F"},
            {"i": "B", "j": "F"},
        ),
        secao="Geometria e cargas",
        colunas=(
            Coluna("i", "Nó inicial", "Nome de um nó da tabela de nós.", ""),
            Coluna("j", "Nó final", "Nome de um nó da tabela de nós.", ""),
        ),
    ),
    *campos_de_secao(com_eixo=False, perfil_padrao="TR ideal 100×50×3"),
    *campos_de_material(),
)


# ---------------------------------------------------------------------------
# Pórtico simples
# ---------------------------------------------------------------------------

PORTICO = "Pórtico de um vão"
CONSOLE = "Console em L"
MAO_FRANCESA = "Console com mão-francesa"
BASE_ENGASTADA = "Engastada"
BASE_ROTULADA = "Rotulada"


def portico_do_caso(v: Valores) -> pp.Portico:
    forma = v["forma"]
    altura = float(v["h_m"])
    vao = float(v["l_m"])
    pilar = pp.secao_de_perfil(str(v["perfil_pilar"]), eixo="x")
    viga = pp.secao_de_perfil(str(v["perfil_viga"]), eixo="x")
    q = float(v["q_kNm"])
    p = float(v["p_kN"])
    horizontal = float(v["h_kN"])
    if forma == PORTICO:
        base = pp.engaste if v["base"] == BASE_ENGASTADA else pp.pino
        return pp.Portico(
            nos=(
                pp.No("A", 0.0, 0.0),
                pp.No("B", 0.0, altura),
                pp.No("C", vao, altura),
                pp.No("D", vao, 0.0),
            ),
            barras=(
                pp.Barra("Pilar esquerdo", "A", "B", pilar),
                pp.Barra("Viga", "B", "C", viga),
                pp.Barra("Pilar direito", "D", "C", pilar),
            ),
            apoios=(base("A"), base("D")),
            cargas_nodais=(pp.CargaNodal("B", fx=horizontal),),
            cargas_distribuidas=(pp.CargaDistribuida("Viga", -q),),
            cargas_pontuais=(pp.CargaPontual("Viga", vao / 2.0, fy=-p),),
        )
    if forma == CONSOLE:
        return pp.Portico(
            nos=(pp.No("A", 0.0, 0.0), pp.No("B", 0.0, altura), pp.No("C", vao, altura)),
            barras=(
                pp.Barra("Pilar", "A", "B", pilar),
                pp.Barra("Viga", "B", "C", viga),
            ),
            apoios=(pp.engaste("A"),),
            cargas_nodais=(pp.CargaNodal("C", fx=horizontal, fy=-p),),
            cargas_distribuidas=(pp.CargaDistribuida("Viga", -q),),
        )
    a = float(v["a_m"])
    exigir(0.0 < a < vao, "A mão-francesa precisa chegar em um ponto dentro da viga.")
    return pp.Portico(
        nos=(
            pp.No("A", 0.0, 0.0),
            pp.No("B", 0.0, altura),
            pp.No("D", a, altura),
            pp.No("C", vao, altura),
        ),
        barras=(
            pp.Barra("Viga, até a mão-francesa", "B", "D", viga),
            pp.Barra("Viga, em balanço", "D", "C", viga),
            pp.Barra("Mão-francesa", "A", "D", pilar, rotula_j=True),
        ),
        apoios=(pp.pino("A"), pp.pino("B")),
        cargas_nodais=(pp.CargaNodal("C", fx=horizontal, fy=-p),),
        cargas_distribuidas=(
            pp.CargaDistribuida("Viga, até a mão-francesa", -q),
            pp.CargaDistribuida("Viga, em balanço", -q),
        ),
    )


def _limites_de_deslocamento(
    v: Valores, resposta: pp.ResultadoPortico, divisor: int
) -> list[Verificacao]:
    """Pórtico: topo do pilar e flecha da viga. Console: a ponta, com L igual a duas vezes o balanço."""
    referencia_norma = "ABNT NBR 8800, Anexo C, como referência"
    if v["forma"] == PORTICO:
        altura = float(v["h_m"]) * 1000.0
        vao = float(v["l_m"]) * 1000.0
        topo = abs(resposta.deslocamentos["B"][0]) * 1000.0
        flecha = abs(resposta.barra("Viga").flecha_max.flecha) * 1000.0
        return [
            limite(
                "Deslocamento horizontal do topo",
                topo,
                altura / divisor,
                "mm",
                f"δ ≤ h/{divisor}",
                referencia_norma,
            ),
            limite(
                "Flecha da viga",
                flecha,
                vao / divisor,
                "mm",
                f"δ ≤ L/{divisor}, medida da reta entre as pontas da viga",
                referencia_norma,
            ),
        ]
    dobro = 2.0 * float(v["l_m"]) * 1000.0
    ponta = math.hypot(*resposta.deslocamentos["C"][:2]) * 1000.0
    return [
        limite(
            "Deslocamento da ponta do console",
            ponta,
            dobro / divisor,
            "mm",
            f"δ ≤ 2·L/{divisor}: no balanço, L é o dobro do comprimento",
            referencia_norma,
        ),
    ]


def calcular_portico(v: Valores) -> Resultado:
    portico = portico_do_caso(v)
    sy = float(v["sy_MPa"])
    fs = float(v["fs"])
    try:
        resposta = pp.resolver(portico)
    except pp.PorticoInvalido as erro:
        raise ValueError(str(erro)) from erro
    admissivel = sy / fs
    linhas = []
    pior = None
    for barra in resposta.barras:
        tensao = barra.tensao_max.tensao_MPa if barra.tensao_max else 0.0
        linhas.append(
            {
                "Barra": barra.barra.nome,
                "Perfil": barra.barra.secao.nome,
                "Normal máx. (kN)": barra.n_max.n,
                "Cortante máx. (kN)": barra.v_max.v,
                "Momento máx. (kN·m)": barra.m_max.m,
                "Tensão (MPa)": tensao,
            }
        )
        if pior is None or (tensao or 0.0) > (pior[0] or 0.0):
            pior = (tensao, barra)
    assert pior is not None
    tensao_pior, barra_pior = pior
    # O maior deslocamento pode estar no meio da barra, longe de qualquer nó.
    deslocamento = (
        max(math.hypot(b.deslocamento_max.dx, b.deslocamento_max.dy) for b in resposta.barras)
        * 1000.0
    )
    divisor = int(str(v["limite_d"]).removeprefix("L/"))
    ponto = barra_pior.tensao_max
    verificacoes = [
        limite(
            f"Tensão em {barra_pior.barra.nome.lower()}",
            tensao_pior or 0.0,
            admissivel,
            "MPa",
            f"|N|/A + |M|/W; limite S_y/FS = {sy:.0f}/{fs:.2f}",
            HIBBELER,
        ),
        *_limites_de_deslocamento(v, resposta, divisor),
        informativo(
            "Soma das forças menos as reações",
            round(resposta.residuo_kN, 6),
            "kN",
            "Deve ser zero: confere o equilíbrio",
            HIBBELER,
        ),
    ]
    reacoes = tuple(
        {"Apoio": r.no, "Rx (kN)": r.rx, "Ry (kN)": r.ry, "Momento (kN·m)": r.mz}
        for r in resposta.reacoes
    )
    figuras = (
        Figura(
            "Modelo",
            pf.figura_estrutura(resposta, largura_px=760, altura_max_px=520).png,
            "Geometria, apoios e cargas.",
        ),
        Figura(
            "Momento fletor",
            pf.figura_diagrama(resposta, "M", largura_px=760, altura_max_px=520).png,
            "Momento do lado tracionado.",
        ),
        Figura(
            "Deformada",
            pf.figura_deformada(resposta, largura_px=760, altura_max_px=520).png,
            "Deformada ampliada, com o maior deslocamento.",
        ),
    )
    alertas = [
        "Conta de tensão, sem flambagem. Pilar comprimido e viga sem travamento lateral pedem a "
        "verificação pela norma: use o caso Perfil de aço com os esforços da tabela."
    ]
    alertas.extend(resposta.avisos)
    envios: list[Envio] = []
    if ponto is not None:
        envios.append(
            Envio(
                "perfil_nbr8800",
                f"Verificar {barra_pior.barra.nome.lower()} pela norma",
                {
                    "perfil": barra_pior.barra.secao.nome,
                    "n_kN": ponto.n,
                    "mx_kNm": abs(ponto.m),
                    "v_kN": abs(barra_pior.v_max.v),
                    "lb_m": barra_pior.comprimento_m,
                    "lx_m": barra_pior.comprimento_m,
                    "ly_m": barra_pior.comprimento_m,
                },
            )
        )
    return Resultado(
        resumo=(
            f"Maior tensão de {tensao_pior or 0.0:.1f} MPa em {barra_pior.barra.nome.lower()} e "
            f"maior deslocamento de {deslocamento:.2f} mm."
        ),
        metricas=(
            Metrica("Maior momento", max(abs(b.m_max.m) for b in resposta.barras), "kN·m"),
            Metrica("Maior normal", max(abs(b.n_max.n) for b in resposta.barras), "kN"),
            Metrica("Maior tensão", tensao_pior or 0.0, "MPa", 1),
            Metrica("Maior deslocamento", deslocamento, "mm"),
        ),
        verificacoes=tuple(verificacoes),
        tabelas=(
            Tabela("Reações nos apoios", reacoes, "Rx para a direita, Ry para cima."),
            Tabela("Esforços em cada barra", tuple(linhas)),
        ),
        figuras=figuras,
        alertas=tuple(alertas),
        hipoteses=(
            "Barras de eixo reto, com a seção no eixo forte, no plano do desenho.",
            "Análise de primeira ordem: não amplia os esforços pela deformação da estrutura.",
            "Ligações entre viga e pilar rígidas, salvo a ponta da mão-francesa, que é rotulada.",
            "Forças de serviço, sem majorar.",
        ),
        referencias=(HIBBELER,),
        envios=tuple(envios),
    )


_SEM_MAO_FRANCESA = ("forma", (PORTICO, CONSOLE))

CAMPOS_PORTICO: tuple[Campo, ...] = (
    Campo(
        "forma",
        "Forma da estrutura",
        "Pórtico: dois pilares e uma viga. Console em L: pilar engastado e viga em balanço. "
        "Mão-francesa: viga presa na parede com uma diagonal por baixo.",
        PORTICO,
        opcoes=(PORTICO, CONSOLE, MAO_FRANCESA),
        secao="Geometria",
    ),
    Campo(
        "h_m",
        "Altura",
        "Do apoio até o eixo da viga. Na mão-francesa, é a distância na parede entre os dois "
        "apoios.",
        3.0,
        "m",
        minimo=0.05,
        passo=0.25,
        secao="Geometria",
    ),
    Campo(
        "l_m",
        "Vão ou balanço",
        "Comprimento da viga.",
        5.0,
        "m",
        minimo=0.05,
        passo=0.25,
        secao="Geometria",
    ),
    Campo(
        "a_m",
        "Onde a mão-francesa chega na viga",
        "Distância da parede até o ponto em que a diagonal encontra a viga.",
        1.5,
        "m",
        minimo=0.01,
        passo=0.25,
        secao="Geometria",
        quando=("forma", (MAO_FRANCESA,)),
    ),
    Campo(
        "base",
        "Base dos pilares",
        "Engastada segura o giro. Rotulada deixa girar e faz o pórtico deslocar mais.",
        BASE_ROTULADA,
        opcoes=(BASE_ROTULADA, BASE_ENGASTADA),
        secao="Geometria",
        quando=("forma", (PORTICO,)),
    ),
    Campo(
        "perfil_pilar",
        "Perfil do pilar ou da mão-francesa",
        "Perfil do catálogo, trabalhando no eixo forte.",
        "W 200 x 26,6",
        secao="Perfis",
        opcoes_de=nomes_dos_perfis,
    ),
    Campo(
        "perfil_viga",
        "Perfil da viga",
        "Perfil do catálogo, trabalhando no eixo forte.",
        "W 250 x 28,4",
        secao="Perfis",
        opcoes_de=nomes_dos_perfis,
    ),
    Campo(
        "q_kNm",
        "Carga distribuída na viga",
        "Para baixo, ao longo de toda a viga.",
        5.0,
        "kN/m",
        passo=1.0,
        secao="Cargas",
    ),
    Campo(
        "p_kN",
        "Força concentrada",
        "Para baixo. No meio da viga no pórtico e na ponta da viga nos consoles.",
        10.0,
        "kN",
        passo=1.0,
        secao="Cargas",
    ),
    Campo(
        "h_kN",
        "Força horizontal",
        "Para a direita. No topo do pilar esquerdo no pórtico e na ponta da viga nos consoles.",
        2.0,
        "kN",
        passo=1.0,
        secao="Cargas",
    ),
    Campo(
        "sy_MPa",
        "Escoamento do material",
        "ASTM A36: 250 MPa. ASTM A572 Gr 50: 345 MPa.",
        345.0,
        "MPa",
        minimo=1.0,
        passo=10.0,
        secao="Limites",
    ),
    Campo(
        "fs",
        "Fator de segurança",
        "A tensão admissível é o escoamento dividido por este fator. Comece com 1,5.",
        1.5,
        minimo=1.0,
        maximo=6.0,
        passo=0.1,
        secao="Limites",
    ),
    Campo(
        "limite_d",
        "Limite de deslocamento",
        "No pórtico, vale para a altura e para o vão da viga. No console, para duas vezes o "
        "balanço.",
        "L/300",
        opcoes=("L/150", "L/200", "L/250", "L/300", "L/350", "L/400", "L/500"),
        secao="Limites",
    ),
)

CASOS: tuple[Caso, ...] = (
    Caso(
        "barra_axial",
        "Barra sob força axial",
        GRUPO,
        "Tensão, alongamento e reações, com trechos de seções diferentes.",
        "Barra puxada ou comprimida, de um ou vários trechos, presa em uma ou nas duas pontas. "
        "Considera também a variação de temperatura.",
        CAMPOS_BARRA_AXIAL,
        calcular_barra_axial,
        r"\sigma=\frac{N}{A},\quad \delta=\sum\frac{N_i L_i}{A_i E_i}+\alpha\,\Delta T\,L",
    ),
    Caso(
        "barra_torcao",
        "Barra em torção",
        GRUPO,
        "Torque, cisalhamento e giro, em eixos e tubos com trechos diferentes.",
        "Barra redonda ou tubo, de um ou vários trechos, presa em uma ou nas duas pontas.",
        CAMPOS_BARRA_TORCAO,
        calcular_barra_torcao,
        r"\tau=\frac{T\,r}{J},\quad \theta=\sum\frac{T_i L_i}{G\,J_i}",
    ),
    Caso(
        "coluna_simples",
        "Coluna simples",
        GRUPO,
        "Quanto a barra aguenta à compressão antes de flambar.",
        "Conta clássica de Euler e Johnson, para haste, tirante comprimido, suporte ou pé de "
        "máquina. Mostra a carga admissível para qualquer comprimento.",
        CAMPOS_COLUNA,
        calcular_coluna,
        r"P_{cr}=\frac{\pi^2 E A}{(KL/r)^2},\quad P_{cr}=A\left[S_y-"
        r"\frac{1}{E}\left(\frac{S_y\,KL/r}{2\pi}\right)^2\right]",
    ),
    Caso(
        "trelica_plana",
        "Treliça plana",
        GRUPO,
        "Força em cada barra, reações e deslocamento dos nós.",
        "Monte os nós e as barras em duas tabelas. Sai a força em cada barra, com tração e "
        "compressão no desenho, e a verificação das piores.",
        CAMPOS_TRELICA,
        calcular_trelica,
        r"K\,u=F,\quad N=\frac{E A}{L}\,\Delta L",
    ),
    Caso(
        "portico_simples",
        "Pórtico simples ou console",
        GRUPO,
        "Pórtico de um vão, console em L e mão-francesa, com diagramas e deformada.",
        "Estruturas planas pequenas: escolha a forma, os perfis e as cargas e veja as reações, "
        "os esforços, o momento e a deformada.",
        CAMPOS_PORTICO,
        calcular_portico,
        r"\sigma=\frac{|N|}{A}+\frac{|M|}{W},\quad K\,u=F",
    ),
)
