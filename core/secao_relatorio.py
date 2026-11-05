"""A seção desenhada no formato dos casos do programa: tabelas, Word e registro no projeto."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from core import secao_desenhada as sd
from core.desenho_estatica import figura_das_partes
from core.elementos_base import Campo, Caso, Coluna, Figura, Metrica, Resultado, Tabela, Valores

FORMA_ROTULO = {sd.RET: "Retângulo", sd.CIRC: "Círculo", sd.POLI: "Polígono"}
FORMA_DO_ROTULO = {rotulo: forma for forma, rotulo in FORMA_ROTULO.items()}
CHEIO = "Cheio"
FURO = "Furo"


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
