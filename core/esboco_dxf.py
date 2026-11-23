"""Desenho em DXF vira esboço: retas, arcos, círculos e polilinhas, com os trechos curvos.

A leitura é do ``ezdxf`` (MIT). Blocos (INSERT) são explodidos; elipses e splines entram como uma
fila de retas, com aviso. Textos, cotas e hachuras do DXF ficam de fora e são contados. A unidade
vem do cabeçalho ($INSUNITS) e tudo vira mm. As pontas que caem no mesmo lugar (pela tolerância)
viram um ponto só, e é assim que as retas soltas do DXF formam contornos.

DWG não entra: é um formato fechado. Quem tem DWG salva como DXF no próprio CAD.
"""

from __future__ import annotations

import io
import math
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from core import esboco as eb

Ponto = tuple[float, float]

#: $INSUNITS → quantos mm vale uma unidade do desenho. Sem unidade (0), vale mm.
UNIDADES: dict[int, tuple[str, float]] = {
    0: ("mm (o arquivo não diz a unidade)", 1.0),
    1: ("polegada", 25.4),
    2: ("pé", 304.8),
    4: ("mm", 1.0),
    5: ("cm", 10.0),
    6: ("m", 1000.0),
    9: ("mil (milésimo de polegada)", 0.0254),
    10: ("jarda", 914.4),
    14: ("dm", 100.0),
}
#: Acima disso o esboço fica pesado demais para a prancheta: escolha as camadas.
MAX_CURVAS = 600
_IGNORADAS = {"TEXT", "MTEXT", "DIMENSION", "HATCH", "POINT", "LEADER", "MLEADER", "ATTRIB"}
_ATTDEF = "ATTDEF"
#: Como dizer o que ficou de fora: (singular, plural).
NOMES_DAS_IGNORADAS = {
    "TEXT": ("texto", "textos"),
    "MTEXT": ("texto", "textos"),
    "DIMENSION": ("cota", "cotas"),
    "HATCH": ("hachura", "hachuras"),
    "POINT": ("ponto", "pontos"),
    "LEADER": ("chamada", "chamadas"),
    "MLEADER": ("chamada", "chamadas"),
    "ATTRIB": ("atributo", "atributos"),
    "outros": ("outra entidade", "outras entidades"),
}


class ErroDeDxf(ValueError):
    """O arquivo não é um DXF que se possa ler, ou não tem nada que vire esboço."""


@dataclass(frozen=True)
class _Reta:
    a: Ponto
    b: Ponto


@dataclass(frozen=True)
class _Arco:
    """Anti-horário de ``inicio`` a ``fim`` em volta de ``centro``; ``inteiro`` é o círculo."""

    centro: Ponto
    raio: float
    inicio: Ponto = (0.0, 0.0)
    fim: Ponto = (0.0, 0.0)
    inteiro: bool = False


@dataclass(frozen=True)
class LeituraDxf:
    esboco: eb.Esboco
    camadas: tuple[str, ...]  # as camadas com geometria, na ordem do arquivo
    usadas: tuple[str, ...]
    unidade: str
    fator_mm: float
    lidas: dict[str, int]
    ignoradas: dict[str, int]
    avisos: tuple[str, ...]


def _abrir(conteudo: bytes) -> Any:
    if conteudo[:4] == b"AC10":  # assinatura do DWG (AC1015, AC1018... AC1032)
        raise ErroDeDxf(
            "Isto é um DWG, formato fechado do AutoCAD. No seu CAD, use Salvar como → DXF e traga o "
            "arquivo .dxf."
        )
    from ezdxf import recover
    from ezdxf.lldxf.const import DXFStructureError

    try:
        doc, _auditor = recover.read(io.BytesIO(conteudo))
    except (DXFStructureError, OSError, UnicodeDecodeError) as erro:
        raise ErroDeDxf(f"Não consegui ler o DXF: {erro}") from erro
    return doc


def _entidades(espaco: Iterable[Any], profundidade: int = 0) -> Iterator[Any]:
    """As entidades, com os blocos explodidos (até 8 níveis de bloco dentro de bloco)."""
    for entidade in espaco:
        if entidade.dxftype() == "INSERT" and profundidade < 8:
            try:
                yield from _entidades(entidade.virtual_entities(), profundidade + 1)
            except Exception:  # bloco com escala não uniforme que não explode: fica de fora
                yield entidade
            continue
        yield entidade


def _xy(v: Any) -> Ponto:
    return (float(v[0]), float(v[1]))


def _arco_do_bulge(a: Ponto, b: Ponto, bulge: float) -> _Arco:
    """O trecho curvo de polilinha: bulge = tan(θ/4), positivo anti-horário de a para b."""
    from ezdxf.math import Vec2, bulge_to_arc

    centro, ang_ini, ang_fim, raio = bulge_to_arc(Vec2(a), Vec2(b), bulge)
    c = _xy(centro)

    def ponto(ang: float) -> Ponto:
        return (c[0] + raio * math.cos(ang), c[1] + raio * math.sin(ang))

    return _Arco(c, float(raio), ponto(ang_ini), ponto(ang_fim))


def _de_polilinha(pontos: list[tuple[Ponto, float]], fechada: bool) -> list[_Reta | _Arco]:
    trechos: list[_Reta | _Arco] = []
    pares = list(zip(pontos, pontos[1:], strict=False))
    if fechada and len(pontos) > 1:
        pares.append((pontos[-1], pontos[0]))
    for (a, bulge), (b, _) in pares:
        if math.hypot(b[0] - a[0], b[1] - a[1]) <= 0:
            continue
        trechos.append(_arco_do_bulge(a, b, bulge) if abs(bulge) > 1e-12 else _Reta(a, b))
    return trechos


def _geometria(entidade: Any, avisos: Counter[str]) -> list[_Reta | _Arco] | None:
    """Os trechos da entidade, no plano xy do desenho (WCS). None: não é geometria."""
    tipo = entidade.dxftype()
    if tipo == "LINE":
        return [_Reta(_xy(entidade.dxf.start), _xy(entidade.dxf.end))]
    if tipo == "CIRCLE":
        centro = _xy(entidade.ocs().to_wcs(entidade.dxf.center))
        return [_Arco(centro, float(entidade.dxf.radius), inteiro=True)]
    if tipo == "ARC":
        centro = _xy(entidade.ocs().to_wcs(entidade.dxf.center))
        inicio, fim = _xy(entidade.start_point), _xy(entidade.end_point)
        if entidade.dxf.extrusion[2] < 0:  # visto por baixo: no desenho, roda ao contrário
            inicio, fim = fim, inicio
        return [_Arco(centro, float(entidade.dxf.radius), inicio, fim)]
    if tipo == "LWPOLYLINE":
        ocs = entidade.ocs()
        espelho = entidade.dxf.extrusion[2] < 0
        pontos = [
            (_xy(ocs.to_wcs((x, y, entidade.dxf.elevation))), -b if espelho else b)
            for x, y, b in entidade.get_points("xyb")
        ]
        return _de_polilinha(pontos, bool(entidade.closed))
    if tipo == "POLYLINE":
        if entidade.is_2d_polyline:
            ocs = entidade.ocs()
            espelho = entidade.dxf.extrusion[2] < 0
            pontos = [
                (
                    _xy(ocs.to_wcs(v.dxf.location)),
                    -float(v.dxf.bulge) if espelho else float(v.dxf.bulge),
                )
                for v in entidade.vertices
            ]
        else:
            pontos = [(_xy(v.dxf.location), 0.0) for v in entidade.vertices]
        return _de_polilinha(pontos, bool(entidade.is_closed))
    if tipo in ("ELLIPSE", "SPLINE"):
        fila = [_xy(p) for p in entidade.flattening(0.01)]
        avisos["Elipses e splines entraram como filas de retas curtas (sem raio)."] += 1
        return [_Reta(a, b) for a, b in zip(fila, fila[1:], strict=False)]
    return None


def camadas(conteudo: bytes) -> tuple[str, ...]:
    """As camadas que têm geometria (o que vira esboço), na ordem em que aparecem."""
    doc = _abrir(conteudo)
    vistas: dict[str, None] = {}
    lixo: Counter[str] = Counter()
    for entidade in _entidades(doc.modelspace()):
        if _geometria(entidade, lixo) is not None:
            vistas.setdefault(str(entidade.dxf.layer), None)
    return tuple(vistas)


def ler_dxf(
    conteudo: bytes,
    *,
    usar: Iterable[str] | None = None,
    levar_para_origem: bool = True,
) -> LeituraDxf:
    """O DXF como esboço em mm. ``usar``: as camadas que entram (todas, se None)."""
    doc = _abrir(conteudo)
    codigo = int(doc.header.get("$INSUNITS", 0) or 0)
    unidade, fator = UNIDADES.get(codigo, (f"mm (código de unidade {codigo} não conhecido)", 1.0))
    escolhidas = None if usar is None else set(usar)
    trechos: list[_Reta | _Arco] = []
    todas: dict[str, None] = {}
    lidas: Counter[str] = Counter()
    ignoradas: Counter[str] = Counter()
    avisos: Counter[str] = Counter()
    for entidade in _entidades(doc.modelspace()):
        tipo = entidade.dxftype()
        geometria = _geometria(entidade, avisos)
        if geometria is None:
            if tipo != _ATTDEF:
                ignoradas[tipo if tipo in _IGNORADAS else "outros"] += 1
            continue
        camada = str(entidade.dxf.layer)
        todas.setdefault(camada, None)
        if escolhidas is not None and camada not in escolhidas:
            continue
        lidas[tipo] += 1
        trechos += geometria
    if not trechos:
        raise ErroDeDxf("Nada no DXF vira esboço (retas, arcos, círculos ou polilinhas).")
    if len(trechos) > MAX_CURVAS:
        raise ErroDeDxf(
            f"O DXF tem {len(trechos)} curvas nas camadas escolhidas; a prancheta aguenta até "
            f"{MAX_CURVAS}. Escolha só as camadas da peça (sem cotas, textos e molduras)."
        )
    trechos = [_em_mm(t, fator) for t in trechos]
    if levar_para_origem:
        trechos = _para_a_origem(trechos)
    return LeituraDxf(
        esboco=_esboco(trechos),
        camadas=tuple(todas),
        usadas=tuple(c for c in todas if escolhidas is None or c in escolhidas),
        unidade=unidade,
        fator_mm=fator,
        lidas=dict(lidas),
        ignoradas=dict(ignoradas),
        avisos=tuple(avisos),
    )


def _em_mm(t: _Reta | _Arco, fator: float) -> _Reta | _Arco:
    def m(p: Ponto) -> Ponto:
        return (p[0] * fator, p[1] * fator)

    if isinstance(t, _Reta):
        return _Reta(m(t.a), m(t.b))
    return _Arco(m(t.centro), t.raio * fator, m(t.inicio), m(t.fim), t.inteiro)


def _caixa(trechos: list[_Reta | _Arco]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for t in trechos:
        if isinstance(t, _Reta):
            xs += [t.a[0], t.b[0]]
            ys += [t.a[1], t.b[1]]
        else:
            xs += [t.centro[0] - t.raio, t.centro[0] + t.raio]
            ys += [t.centro[1] - t.raio, t.centro[1] + t.raio]
    return min(xs), min(ys), max(xs), max(ys)


def _para_a_origem(trechos: list[_Reta | _Arco]) -> list[_Reta | _Arco]:
    x0, y0, x1, y1 = _caixa(trechos)
    dx, dy = -(x0 + x1) / 2.0, -(y0 + y1) / 2.0

    def m(p: Ponto) -> Ponto:
        return (p[0] + dx, p[1] + dy)

    saida: list[_Reta | _Arco] = []
    for t in trechos:
        if isinstance(t, _Reta):
            saida.append(_Reta(m(t.a), m(t.b)))
        else:
            saida.append(_Arco(m(t.centro), t.raio, m(t.inicio), m(t.fim), t.inteiro))
    return saida


def _esboco(trechos: list[_Reta | _Arco]) -> eb.Esboco:
    x0, y0, x1, y1 = _caixa(trechos)
    tamanho = math.hypot(x1 - x0, y1 - y0) or 100.0
    tolerancia = 1e-5 * tamanho
    pontos: dict[str, Ponto] = {eb.ORIGEM: (0.0, 0.0)}
    curvas: list[eb.Curva] = []
    restricoes: list[eb.Restricao] = []
    # Grade de busca: pontas que caem no mesmo lugar viram um ponto só, sem varrer tudo.
    grade: dict[tuple[int, int], list[str]] = {}

    def ponto(p: Ponto, *, juntar: bool = True) -> str:
        chave = (round(p[0] / tolerancia), round(p[1] / tolerancia))
        if juntar:
            for i in (-1, 0, 1):
                for j in (-1, 0, 1):
                    for pid in grade.get((chave[0] + i, chave[1] + j), ()):
                        x, y = pontos[pid]
                        if math.hypot(x - p[0], y - p[1]) <= tolerancia:
                            return pid
        pid = f"p{len(pontos)}"
        pontos[pid] = (float(p[0]), float(p[1]))
        if juntar:
            grade.setdefault(chave, []).append(pid)
        return pid

    centros: dict[tuple[int, int], str] = {}

    def centro(p: Ponto) -> str:
        chave = (round(p[0] / tolerancia), round(p[1] / tolerancia))
        if chave not in centros:
            centros[chave] = ponto(p, juntar=False)
        return centros[chave]

    for t in trechos:
        if isinstance(t, _Reta):
            a, b = ponto(t.a), ponto(t.b)
            if a == b:
                continue
            cid = f"c{len(curvas) + 1}"
            curvas.append(eb.Curva(cid, eb.LINHA, (a, b)))
            (xa, ya), (xb, yb) = pontos[a], pontos[b]
            escala = max(abs(xb - xa), abs(yb - ya))
            if abs(ya - yb) <= 1e-9 * escala:
                restricoes.append(
                    eb.Restricao(f"r{len(restricoes) + 1}", eb.HORIZONTAL, curvas=(cid,))
                )
            elif abs(xa - xb) <= 1e-9 * escala:
                restricoes.append(
                    eb.Restricao(f"r{len(restricoes) + 1}", eb.VERTICAL, curvas=(cid,))
                )
            continue
        if t.raio <= tolerancia:
            continue
        c = centro(t.centro)
        cid = f"c{len(curvas) + 1}"
        if t.inteiro:
            curvas.append(eb.Curva(cid, eb.CIRCULO, (c,), t.raio))
            continue
        inicio, fim = ponto(t.inicio), ponto(t.fim)
        if inicio != fim:
            curvas.append(eb.Curva(cid, eb.ARCO, (c, inicio, fim)))
    return eb.Esboco(pontos, tuple(curvas), tuple(restricoes))
