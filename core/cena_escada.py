"""A escada em 3D — lances, degraus, longarinas, patamares, guarda-corpos e apoios — para o núcleo
:mod:`core.cena_3d`, em dois modos:

* **Escada detalhada**: cada degrau (grade) como uma peça, as duas longarinas com o perfil, os
  patamares, o guarda-corpo de verdade (corrimão, travessa e montantes) e os apoios das pontas;
* **Casca translúcida**: o lance como uma tampa translúcida na linha dos bocéis e o guarda-corpo
  como painéis translúcidos — o volume da escada, para ver o conjunto ou para o relatório.

Vale para a escada da página Degrau de escada (:class:`core.escada_lances.EscadaComPatamares`, ou o
que o registro grava dela) e é a mesma regra dos lances que vêm como chapa no esqueleto do
SolidWorks (:mod:`core.cena_do_modelo`). Eixos: x ao longo da escada (a vista lateral), y na largura,
z para cima, em metros; escada em U (patamar com volta) põe o lance seguinte ao lado. Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from core import cena_3d as c3
from core import escada_lances as el

MODO_DETALHADO = "Escada detalhada"
MODO_CASCA = "Casca translúcida"
MODOS = (MODO_DETALHADO, MODO_CASCA)

COR_DEGRAU = "#9aa3ad"
COR_LONGARINA = "#d4760a"
COR_PATAMAR = "#b9c3ce"
COR_GUARDA_CORPO = "#a9bcd6"
COR_CASCA = "#7c9cc4"
ESPESSURA_DO_DEGRAU_M = 0.035
CANTO_A_LONGARINA_PADRAO_MM = 25.0
VAO_ENTRE_LANCES_EM_U_M = 0.10
TUBO = c3.Secao(c3.FORMA_TUBO_CIRCULAR, 0.042, 0.042)
VAO_DE_MONTANTE_M = 1.2


def _ponto(x: float, y: float, z: float) -> c3.Ponto:
    return (float(x), float(y), float(z))


def _guarda_corpo(
    nome: str, a: c3.Ponto, b: c3.Ponto, altura: float, modo: str
) -> tuple[list[c3.BarraCena], list[c3.PainelCena]]:
    """Um trecho de guarda-corpo sobre a linha a–b (a altura é medida na vertical)."""

    def em_cima(p: c3.Ponto, h: float) -> c3.Ponto:
        return (p[0], p[1], p[2] + h)

    if modo == MODO_CASCA:
        return [], [
            c3.PainelCena(
                nome, (a, b, em_cima(b, altura), em_cima(a, altura)), COR_CASCA, 0.22, "gc"
            )
        ]
    barras = [
        c3.BarraCena(f"{nome} corrimão", em_cima(a, altura), em_cima(b, altura), TUBO, None,
                     COR_GUARDA_CORPO, grupo="gc"),
        c3.BarraCena(f"{nome} travessa", em_cima(a, altura / 2), em_cima(b, altura / 2), TUBO,
                     None, COR_GUARDA_CORPO, grupo="gc"),
    ]  # fmt: skip
    comprimento = math.dist(a, b)
    montantes = max(1, round(comprimento / VAO_DE_MONTANTE_M))
    for k in range(montantes + 1):
        s = k / montantes
        p = _ponto(*(a[i] + s * (b[i] - a[i]) for i in range(3)))
        barras.append(c3.BarraCena(f"{nome} montante {k}", p, em_cima(p, altura), TUBO, None,
                                   COR_GUARDA_CORPO, grupo="gc"))  # fmt: skip
    return barras, []


def cena_da_escada(
    H_mm: float,
    lances: Sequence[el.Lance],
    patamares: Sequence[el.Patamar] = (),
    *,
    modo: str = MODO_DETALHADO,
    secao_da_longarina: c3.Secao | None = None,
    altura_do_guarda_corpo_m: float = 1.10,
    apoio_pe: str = c3.APOIO_ARTICULADO,
    apoio_topo: str = c3.APOIO_ARTICULADO,
    titulo: str = "Escada em 3D",
    subtitulo: str = "",
    profundidade_do_degrau_mm: float | None = None,
    canto_a_longarina_mm: float = CANTO_A_LONGARINA_PADRAO_MM,
) -> c3.Cena:
    """A cena da escada; lances e patamares como :mod:`core.escada_lances` os monta.

    A geometria é a da vista lateral do degrau: a linha dos bocéis passa por ``(x_pe, nível
    inicial)``; o espelho j fica em ``x_pe + j·b`` e o degrau j vai do bocel dele, em
    ``x_pe + j·b``, até o espelho seguinte, ``x_pe + (j + 1)·b`` — o último degrau chega na borda
    do patamar (ou da chegada) e o primeiro sai do primeiro espelho. Um lance que sai de um
    patamar começa no primeiro espelho, que fica na borda do patamar: a longarina e o
    guarda-corpo dele não entram no patamar (a longarina se liga na viga da borda). O lance que
    sai do piso de partida apoia no piso, na linha dos bocéis.

    ``profundidade_do_degrau_mm`` (C): o degrau vai do bocel para trás C, passando o recobrimento
    r = C − b por baixo da frente do seguinte (sem ela, C = b). ``canto_a_longarina_mm`` (e): a
    borda de cima da longarina fica e acima do bocel, na perpendicular à inclinação.
    """
    secao = secao_da_longarina or c3.Secao(c3.FORMA_U, 0.2032, 0.0574, 0.0056, 0.0099)
    altura_gc = altura_do_guarda_corpo_m if altura_do_guarda_corpo_m > 0 else 1.10
    barras: list[c3.BarraCena] = []
    paineis: list[c3.PainelCena] = []
    apoios: list[c3.ApoioCena] = []
    deslocamento = 0.0  # y do lado de cada lance (escada em U: o próximo vai ao lado)
    voltas = {p.numero: p.volta for p in patamares}
    faixas_dos_lances: dict[int, tuple[float, float]] = {}
    for k, lance in enumerate(lances):
        largura = max(lance.largura_mm, 300.0) / 1000.0
        y0, y1 = deslocamento, deslocamento + largura
        faixas_dos_lances[lance.numero] = (y0, y1)
        z0, z1 = lance.nivel_inicial_mm / 1000.0, lance.nivel_final_mm / 1000.0
        x_pe, x_topo = lance.x_pe_mm / 1000.0, lance.x_topo_mm / 1000.0
        sentido = 1.0 if lance.sentido >= 0 else -1.0
        h, b = lance.h_mm / 1000.0, lance.b_mm / 1000.0
        profundidade = (
            profundidade_do_degrau_mm / 1000.0
            if profundidade_do_degrau_mm and profundidade_do_degrau_mm > 0
            else b
        )
        cos_alfa = b / math.hypot(b, h) if b > 0 else 1.0
        # Onde o lance começa: no piso de partida, a linha dos bocéis no piso; saindo de um
        # patamar, o primeiro espelho, na borda dele (nada do lance entra no patamar).
        if k == 0 or lance.n_espelhos < 2:
            x_ini, z_ini = x_pe, z0
        else:
            x_ini, z_ini = x_pe + sentido * b, z0 + h
        # Longarinas: a borda de cima e acima da linha dos bocéis (perpendicular), o eixo meia
        # altura da seção abaixo dela; na vertical, divididos por cos α.
        baixa = (secao.d / 2 - max(canto_a_longarina_mm, 0.0) / 1000.0) / cos_alfa
        for lado, y in (("esquerda", y0), ("direita", y1)):
            a = _ponto(x_ini, y, z_ini - baixa)
            c = _ponto(x_topo, y, z1 - baixa)
            if modo == MODO_DETALHADO:
                barras.append(c3.BarraCena(f"Longarina L{lance.numero} {lado}", a, c, secao,
                                           (0.0, 0.0, 1.0), COR_LONGARINA, grupo="longarina"))  # fmt: skip
            bocel_a, bocel_c = _ponto(x_ini, y, z_ini), _ponto(x_topo, y, z1)
            gc_barras, gc_paineis = _guarda_corpo(
                f"GC L{lance.numero} {lado}", bocel_a, bocel_c, altura_gc, modo
            )
            barras += gc_barras
            paineis += gc_paineis
        if modo == MODO_DETALHADO:
            for j in range(1, max(lance.n_espelhos, 1)):
                z = z0 + j * h
                # Do bocel do degrau j (no espelho j) para trás a profundidade C: até o espelho
                # j + 1 e o recobrimento r por baixo do degrau seguinte.
                x_meio = x_pe + sentido * (j * b + profundidade / 2)
                barras.append(
                    c3.BarraCena(
                        f"Degrau L{lance.numero}.{j}",
                        _ponto(x_meio, y0 + 0.02, z - ESPESSURA_DO_DEGRAU_M / 2),
                        _ponto(x_meio, y1 - 0.02, z - ESPESSURA_DO_DEGRAU_M / 2),
                        c3.Secao(c3.FORMA_CHEIA, ESPESSURA_DO_DEGRAU_M, profundidade),
                        (0.0, 0.0, 1.0),
                        COR_DEGRAU,
                        grupo="degrau",
                    )
                )
        else:
            paineis.append(
                c3.PainelCena(
                    f"Lance {lance.numero}",
                    (_ponto(x_ini, y0, z_ini), _ponto(x_topo, y0, z1), _ponto(x_topo, y1, z1),
                     _ponto(x_ini, y1, z_ini)),
                    COR_CASCA,
                    0.30,
                    "lance",
                )
            )  # fmt: skip
        if k == 0:
            for y in (y0, y1):
                apoios.append(c3.ApoioCena(_ponto(x_pe, y, z0 - secao.d), apoio_pe))
        if k == len(lances) - 1:
            for y in (y0, y1):
                apoios.append(c3.ApoioCena(_ponto(x_topo, y, z1 - secao.d), apoio_topo))
        if voltas.get(lance.numero):
            deslocamento += largura + VAO_ENTRE_LANCES_EM_U_M
    # Patamares: entre o lance de baixo e o de cima (em U, ocupa a largura dos dois).
    for p in patamares:
        z = p.nivel_mm / 1000.0
        xa, xb = p.x_inicio_mm / 1000.0, p.x_fim_mm / 1000.0
        de_baixo = faixas_dos_lances.get(p.numero, (0.0, p.largura_mm / 1000.0))
        de_cima = faixas_dos_lances.get(p.numero + 1, de_baixo)
        y0, y1 = min(de_baixo[0], de_cima[0]), max(de_baixo[1], de_cima[1])
        cantos = (_ponto(xa, y0, z), _ponto(xb, y0, z), _ponto(xb, y1, z), _ponto(xa, y1, z))
        paineis.append(c3.PainelCena(f"Patamar {p.numero}", cantos, COR_PATAMAR,
                                     0.85 if modo == MODO_DETALHADO else 0.30, "patamar"))  # fmt: skip
        # Guarda-corpo do patamar: os dois lados ao longo da escada; a ponta só na escada em U
        # (na reta, a ponta é a saída para o lance de cima — fechá-la tranca a passagem).
        lados = [(cantos[0], cantos[1]), (cantos[3], cantos[2])]
        if p.volta:
            lados.append((cantos[1], cantos[2]))
        for i, (a, c) in enumerate(lados):
            gc_barras, gc_paineis = _guarda_corpo(f"GC P{p.numero}.{i}", a, c, altura_gc, modo)
            barras += gc_barras
            paineis += gc_paineis
    return c3.Cena(
        barras=tuple(barras),
        paineis=tuple(paineis),
        apoios=tuple(apoios),
        titulo=titulo,
        subtitulo=subtitulo
        or (
            f"{len(lances)} lance(s), desnível {H_mm / 1000:.2f} m · {modo.lower()}".replace(
                ".", ","
            )
        ),
        legenda=(
            (
                (COR_LONGARINA, "longarina"),
                (COR_DEGRAU, "degrau"),
                (COR_GUARDA_CORPO, "guarda-corpo"),
            )
            if modo == MODO_DETALHADO
            else ((COR_CASCA, "lance e guarda-corpo (translúcidos)"),)
        ),
        eixo_vertical_do_modelo="Z",
    )


def cena_do_registro(dados: Mapping[str, Any]) -> c3.Cena:
    """A cena gravada no registro (``escada_3d``): o esquemático da escada e as opções do 3D."""
    esquematico = dados.get("esquematico")
    if not isinstance(esquematico, Mapping):
        raise ValueError("Registro sem o esquemático da escada.")
    H, lances, patamares = el.geometria_do_dicionario(esquematico)
    secao = dados.get("secao")
    return cena_da_escada(
        H,
        lances,
        patamares,
        modo=str(dados.get("modo") or MODO_DETALHADO),
        secao_da_longarina=c3.Secao(**secao) if isinstance(secao, Mapping) else None,
        altura_do_guarda_corpo_m=float(dados.get("altura_do_guarda_corpo_m") or 1.10),
        apoio_pe=str(dados.get("apoio_pe") or c3.APOIO_ARTICULADO),
        apoio_topo=str(dados.get("apoio_topo") or c3.APOIO_ARTICULADO),
        profundidade_do_degrau_mm=_numero(dados.get("profundidade_do_degrau_mm")),
        canto_a_longarina_mm=(
            CANTO_A_LONGARINA_PADRAO_MM
            if (canto := _numero(dados.get("canto_a_longarina_mm"))) is None
            else canto
        ),
    )


def _numero(valor: Any) -> float | None:
    if isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) and numero >= 0 else None


def para_o_registro(
    esc: el.EscadaComPatamares,
    *,
    modo: str,
    secao_da_longarina: c3.Secao | None,
    altura_do_guarda_corpo_m: float,
    apoio_pe: str = c3.APOIO_ARTICULADO,
    apoio_topo: str = c3.APOIO_ARTICULADO,
    profundidade_do_degrau_mm: float | None = None,
    canto_a_longarina_mm: float = CANTO_A_LONGARINA_PADRAO_MM,
) -> dict[str, Any]:
    secao = secao_da_longarina
    return {
        "esquematico": el.para_dicionario(esc),
        "modo": modo if modo in MODOS else MODO_DETALHADO,
        "secao": None
        if secao is None
        else {"forma": secao.forma, "d": secao.d, "b": secao.b, "tw": secao.tw, "tf": secao.tf},
        "altura_do_guarda_corpo_m": altura_do_guarda_corpo_m,
        "apoio_pe": apoio_pe,
        "apoio_topo": apoio_topo,
        "profundidade_do_degrau_mm": profundidade_do_degrau_mm,
        "canto_a_longarina_mm": canto_a_longarina_mm,
    }
