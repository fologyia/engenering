"""A seção desenhada no formato dos casos do programa: tabelas, Word e registro no projeto."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from core import nbr8800 as nbr
from core import secao_desenhada as sd
from core.desenho_estatica import figura_das_partes
from core.elementos_base import (
    Campo,
    Caso,
    Coluna,
    Figura,
    Metrica,
    Resultado,
    Tabela,
    Valores,
    limite,
)
from core.section_catalog import perfil_de_dicionario
from core.verificacao import Verificacao

FORMA_ROTULO = {sd.RET: "Retângulo", sd.CIRC: "Círculo", sd.POLI: "Polígono"}
FORMA_DO_ROTULO = {rotulo: forma for forma, rotulo in FORMA_ROTULO.items()}
CHEIO = "Cheio"
FURO = "Furo"
MODULO_E_MPA = 200_000.0
#: Formas em que a norma sabe qual é a alma. Numa seção livre, fica só a tensão.
FORMAS_COM_ALMA = {"I", "U", "T", "caixao"}


def texto_dos_pontos(pontos: Sequence[Sequence[float]]) -> str:
    return "; ".join(f"{x:g} {y:g}" for x, y in pontos)


def pontos_do_texto(texto: str) -> list[tuple[float, float]]:
    """``"0 0; 100 0; 100 50"``, aceitando vírgula decimal."""
    pontos: list[tuple[float, float]] = []
    for pedaco in str(texto or "").split(";"):
        numeros = pedaco.replace(",", ".").split()
        if not numeros:
            continue
        if len(numeros) != 2:
            raise sd.ErroDeSecao(f"Ponto inválido: {pedaco.strip()!r}. Escreva x e y: 100 50.")
        try:
            pontos.append((float(numeros[0]), float(numeros[1])))
        except ValueError:
            raise sd.ErroDeSecao(f"Ponto inválido: {pedaco.strip()!r}.") from None
    return pontos


def linha_da_parte(parte: Mapping[str, Any]) -> dict[str, Any]:
    forma = parte["forma"]
    poligono = forma == sd.POLI
    return {
        "forma": FORMA_ROTULO[forma],
        "tipo": FURO if parte.get("furo") else CHEIO,
        "x": None if poligono else parte.get("x", 0.0),
        "y": None if poligono else parte.get("y", 0.0),
        "b": None if poligono else parte.get("b", 0.0),
        "h": None if poligono or forma == sd.CIRC else parte.get("h", 0.0),
        "giro": None if forma != sd.RET else parte.get("giro", 0.0),
        "pontos": texto_dos_pontos(parte.get("pontos") or ()) if poligono else "",
        "grupo": int(parte.get("grupo") or 0),
    }


def parte_da_linha(linha: Mapping[str, Any]) -> dict[str, Any]:
    forma = FORMA_DO_ROTULO.get(str(linha.get("forma")), sd.RET)

    def numero(chave: str) -> float:
        valor = linha.get(chave)
        return 0.0 if valor is None or valor != valor else float(valor)

    largura = numero("b")
    return {
        "forma": forma,
        "x": numero("x"),
        "y": numero("y"),
        "b": largura,
        "h": largura if forma == sd.CIRC else numero("h"),
        "giro": numero("giro"),
        "furo": linha.get("tipo") == FURO,
        "pontos": pontos_do_texto(str(linha.get("pontos") or "")) if forma == sd.POLI else [],
        "grupo": int(numero("grupo")),
    }


def linhas_de_propriedades(p: sd.Propriedades, densidade: float) -> tuple[dict[str, Any], ...]:
    def linha(nome: str, valor: float, unidade: str) -> dict[str, Any]:
        return {"Grandeza": nome, "Valor": valor, "Unidade": unidade}

    return (
        linha("Área A", p.area, "mm²"),
        linha("Massa por metro", p.massa(densidade), "kg/m"),
        linha("Altura total", p.altura, "mm"),
        linha("Largura total", p.largura, "mm"),
        linha("Centro de gravidade x", p.xc, "mm"),
        linha("Centro de gravidade y", p.yc, "mm"),
        linha("Inércia Ix", p.ix, "mm⁴"),
        linha("Inércia Iy", p.iy, "mm⁴"),
        linha("Produto de inércia Ixy", p.ixy, "mm⁴"),
        linha("Inércia principal maior", p.i1, "mm⁴"),
        linha("Inércia principal menor", p.i2, "mm⁴"),
        linha("Ângulo do eixo principal", p.angulo, "°"),
        linha("Raio de giração rx", p.rx, "mm"),
        linha("Raio de giração ry", p.ry, "mm"),
        linha("Raio de giração mínimo", p.r_min, "mm"),
        linha("W em x, topo", p.wx_topo, "mm³"),
        linha("W em x, base", p.wx_base, "mm³"),
        linha("W em y, direita", p.wy_direita, "mm³"),
        linha("W em y, esquerda", p.wy_esquerda, "mm³"),
        linha("Módulo plástico Zx", p.zx, "mm³"),
        linha("Módulo plástico Zy", p.zy, "mm³"),
        linha("Constante de torção J", p.j, "mm⁴"),
        linha("Módulo de torção Wt", p.w_torcao, "mm³"),
        linha("Constante de empenamento Cw", p.cw, "mm⁶"),
        linha("Centro de cisalhamento x, do G", p.x_s, "mm"),
        linha("Centro de cisalhamento y, do G", p.y_s, "mm"),
        linha("Momento estático Qx no G", p.qx, "mm³"),
        linha("Momento estático Qy no G", p.qy, "mm³"),
        linha("Largura de aço na linha do G (flexão em x)", p.bx, "mm"),
        linha("Área de cortante vertical (I·b/Q)", p.area_cortante_x, "mm²"),
    )


def resultado_da_secao(analise: sd.Analise, densidade: float) -> Resultado:
    p = analise.prop
    forma = sd.reconhecer(analise.partes)
    figura = figura_das_partes(analise.partes, p)
    return Resultado(
        resumo=(
            f"{forma.nome}: área de {p.area / 100:.2f} cm², Ix de {p.ix / 1e4:.1f} cm⁴, "
            f"Iy de {p.iy / 1e4:.1f} cm⁴ e {p.massa(densidade):.2f} kg/m."
        ),
        metricas=(
            Metrica("Área", p.area / 100, "cm²", 2),
            Metrica("Ix", p.ix / 1e4, "cm⁴", 1),
            Metrica("Iy", p.iy / 1e4, "cm⁴", 1),
            Metrica("Menor W em x", p.wx / 1e3, "cm³", 1),
            Metrica("J", p.j / 1e4, "cm⁴", 2),
            Metrica("Massa", p.massa(densidade), "kg/m", 2),
        ),
        tabelas=(Tabela("Propriedades da seção", linhas_de_propriedades(p, densidade)),),
        figuras=(Figura("Seção", figura.png, figura.legenda),),
        alertas=tuple(sd.alertas_da_secao(analise, forma)),
        hipoteses=(
            "Partes encostadas trabalham como uma peça só: isso pede solda ou parafusos que passem "
            "o cortante entre elas.",
            "Área, inércias e módulos saem da figura final: parte sobre parte conta uma vez.",
            "J, Cw e o centro de cisalhamento saem de elementos finitos sobre a função de "
            "empenamento (Saint-Venant).",
        ),
    )


def _calcular(v: Valores) -> Resultado:
    partes = sd.partes_de_lista(parte_da_linha(linha) for linha in v["partes"])
    return resultado_da_secao(sd.analisar(partes), float(v["densidade_kg_m3"]))


CASO = Caso(
    id="secao_desenhada",
    titulo="Seção desenhada",
    grupo="Seções e materiais",
    resumo="Propriedades de uma seção qualquer, desenhada na prancheta.",
    descricao="Propriedades geométricas e de torção da seção desenhada.",
    campos=(
        Campo(
            "partes",
            "Partes",
            "Cada parte da seção.",
            (),
            colunas=(
                Coluna("forma", "Forma", "Retângulo, círculo ou polígono.", "Retângulo"),
                Coluna("tipo", "Tipo", "Cheio ou furo.", CHEIO),
                Coluna("x", "x", "Centro em x.", 0.0, "mm", opcional=True),
                Coluna("y", "y", "Centro em y.", 0.0, "mm", opcional=True),
                Coluna("b", "b ou Ø", "Largura ou diâmetro.", 0.0, "mm", opcional=True),
                Coluna("h", "h", "Altura.", 0.0, "mm", opcional=True),
                Coluna("giro", "Giro", "Giro da chapa.", 0.0, "°", opcional=True),
                Coluna("pontos", "Pontos", "Pontos do polígono.", "", opcional=True),
            ),
        ),
        Campo("densidade_kg_m3", "Densidade", "Massa específica.", 7850.0, "kg/m³"),
    ),
    calcular=_calcular,
)


def verificacoes_de_tensao(
    analise: sd.Analise,
    mapa: sd.MapaDeTensoes,
    fy: float,
    fs: float,
    vx_kn: float = 0.0,
    vy_kn: float = 0.0,
) -> tuple[list[Verificacao], list[str]]:
    """As tensões contra o escoamento e, em perfil conhecido, o cortante pela norma.

    τ_y = f_y/√3 é o escoamento por cisalhamento pelo critério de von Mises. Isso não enxerga
    flambagem: uma alma esbelta perde a força antes de escoar, e por isso a norma entra junto, quando
    o programa reconhece a forma. O resultado fala de tensão no material, e não substitui as
    verificações de flambagem da barra.
    """
    admissivel = fy / fs
    linhas = [
        limite(
            "Tensão normal",
            max(abs(mapa.sigma_max), abs(mapa.sigma_min)),
            admissivel,
            "MPa",
            "|σ| ≤ f_y/FS",
            "Tensão elástica",
        ),
        limite(
            "Cisalhamento",
            mapa.tau_max,
            admissivel / math.sqrt(3.0),
            "MPa",
            "τ ≤ f_y/(√3·FS)",
            "Critério de von Mises",
        ),
        limite(
            "Tensão combinada",
            mapa.mises,
            admissivel,
            "MPa",
            "√(σ² + 3τ²) ≤ f_y/FS",
            "Critério de von Mises",
        ),
    ]
    avisos: list[str] = []
    if not (vx_kn or vy_kn) or sd.reconhecer(analise.partes).tipo not in FORMAS_COM_ALMA:
        return linhas, avisos
    try:
        perfil = perfil_de_dicionario(sd.perfil_da_secao("Seção desenhada", analise))
    except (sd.ErroDeSecao, ValueError):
        return linhas, avisos
    for rotulo, eixo, cortante in (("na alma", "x", vy_kn), ("nas mesas", "y", vx_kn)):
        if not cortante:
            continue
        norma = nbr.verificar_cisalhamento(perfil, fy, MODULO_E_MPA, abs(cortante) * 1e3, eixo=eixo)
        linhas.append(
            limite(
                f"Cortante {rotulo} pela norma",
                abs(cortante),
                norma.resistencia_N / 1e3,
                "kN",
                f"V_Rd com λ = {norma.esbeltez_alma:.1f} e λ_p = {norma.lambda_p:.1f}",
                "NBR 8800, 5.4.3",
            )
        )
        if norma.esbeltez_alma > norma.lambda_p:
            avisos.append(
                f"Cortante {rotulo}: λ = {norma.esbeltez_alma:.1f} passa de λ_p = "
                f"{norma.lambda_p:.1f}. A chapa flamba por cisalhamento antes de escoar, e quem "
                "manda é a linha da norma, e não a tensão."
            )
    return linhas, avisos
