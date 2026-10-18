"""Desenhos do vento barra a barra: a estrutura em 3D com a carga de cada barra, a planta com os
reticulados e a vista de quem olha pelo vento (a "sombra" que a NBR 6123 usa).

Cada função devolve texto SVG para ``st.image``. As cores da carga vão do claro (pouca) ao escuro
(muita); as setas pequenas mostram para onde a carga empurra cada barra. Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from components import desenho_svg as d
from components.cena_3d_svg import svg_da_cena
from core import cena_3d as c3
from core import cena_do_modelo as cm
from core import vento_por_barras as vpb

Ponto = tuple[float, float, float]
ALTURA_DA_SETA_DE_VENTO = 0.6  # da altura da estrutura


def _titulo_da_direcao(angulo: int) -> str:
    return f"Vento a {angulo}° ({vpb.SENTIDOS.get(angulo, '')})"


def _maior_carga(direcao: vpb.VentoNaDirecao) -> float:
    return max((f.kN_m for f in direcao.barras), default=0.0) or 1.0


def _limites(r: vpb.ResultadoPorBarras) -> tuple[float, float, float, float, float, float]:
    xs, ys, zs = [], [], []
    for b in r.entrada.barras:
        for p in (b.inicio, b.fim):
            xs.append(p[0])
            ys.append(p[1])
            zs.append(p[2])
    for el in r.entrada.elementos:
        for p in (el.ponto_1, el.ponto_2):
            if p is not None:
                xs.append(p[0])
                ys.append(p[1])
                zs.append(p[2] + el.altura_m)
    return min(xs), max(xs), min(ys), max(ys), r.cota_do_terreno_m, max(zs)


def _cantos_do_elemento(el: vpb.ElementoAoVento) -> list[list[Ponto]]:
    """As faces (polígonos 3D) que representam o elemento no desenho."""
    if el.em_linha and el.ponto_2 is not None:
        base = min(el.ponto_1[2], el.ponto_2[2])
        a = (el.ponto_1[0], el.ponto_1[1], base)
        b = (el.ponto_2[0], el.ponto_2[1], base)
        h = el.altura_m
        return [[a, b, (b[0], b[1], base + h), (a[0], a[1], base + h)]]
    cx, cy, z0 = el.ponto_1
    h = el.altura_m
    if el.tipo == vpb.TIPO_CILINDRO:
        raio = el.largura_x_m / 2
        anel = [
            (cx + raio * math.cos(2 * math.pi * k / 16), cy + raio * math.sin(2 * math.pi * k / 16))
            for k in range(16)
        ]
        faces = [[(x, y, z0) for x, y in anel], [(x, y, z0 + h) for x, y in anel]]
        for k in range(16):
            (x1, y1), (x2, y2) = anel[k], anel[(k + 1) % 16]
            faces.append([(x1, y1, z0), (x2, y2, z0), (x2, y2, z0 + h), (x1, y1, z0 + h)])
        return faces
    lx, ly = el.largura_x_m / 2, el.largura_y_m / 2
    cantos = [(cx - lx, cy - ly), (cx + lx, cy - ly), (cx + lx, cy + ly), (cx - lx, cy + ly)]
    faces = [[(x, y, z0) for x, y in cantos], [(x, y, z0 + h) for x, y in cantos]]
    for k in range(4):
        (x1, y1), (x2, y2) = cantos[k], cantos[(k + 1) % 4]
        faces.append([(x1, y1, z0), (x2, y2, z0), (x2, y2, z0 + h), (x1, y1, z0 + h)])
    return faces


def _envoltoria(pontos: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Envoltória convexa (cadeia monótona)."""
    p = sorted(set(pontos))
    if len(p) <= 2:
        return list(p)

    def giro(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    baixo: list[tuple[float, float]] = []
    for q in p:
        while len(baixo) >= 2 and giro(baixo[-2], baixo[-1], q) <= 0:
            baixo.pop()
        baixo.append(q)
    cima: list[tuple[float, float]] = []
    for q in reversed(p):
        while len(cima) >= 2 and giro(cima[-2], cima[-1], q) <= 0:
            cima.pop()
        cima.append(q)
    return baixo[:-1] + cima[:-1]


def _rotulo_curto(nome: str, limite: int = 22) -> str:
    return nome if len(nome) <= limite else nome[: limite - 1] + "…"


# ---------------------------------------------------------------------------------------------
# 3D
# ---------------------------------------------------------------------------------------------
def cena_do_vento(
    r: vpb.ResultadoPorBarras,
    angulo: int,
    *,
    quantos_rotulos: int = 5,
    eixo_vertical: str = "Y",
) -> c3.Cena:
    """A cena 3D do vento numa direção: cada barra com o perfil de verdade, na cor da carga, com o
    pente das barras mais carregadas, os elementos e a seta grande do vento."""
    direcao = r.direcao(angulo)
    w = vpb.vento(angulo)
    maior = _maior_carga(direcao)
    forcas = {f.barra: f for f in direcao.barras}
    mais_carregadas = {
        f.barra
        for f in sorted(direcao.barras, key=lambda f: -f.forca_kN)[:quantos_rotulos]
        if f.forca_kN > 1e-9
    }
    barras: list[c3.BarraCena] = []
    distribuidas: list[c3.CargaDistribuidaCena] = []
    for b in r.entrada.barras:
        f = forcas.get(b.nome)
        fracao = (f.kN_m / maior) if f is not None and f.forca_kN > 1e-9 else 0.0
        cor = d.cor_da_escala(0.15 + 0.85 * fracao) if fracao > 0 else d.COR_ESTRUTURA_CLARA
        rotulo = (
            f"{_rotulo_curto(b.nome)}: {d.n(f.kN_m, 3)} kN/m"
            if f is not None and b.nome in mais_carregadas
            else ""
        )
        barras.append(
            c3.BarraCena(
                b.nome,
                b.inicio,
                b.fim,
                cm.secao_do_perfil(b.perfil, (b.maior_m * 1000, b.menor_m * 1000)),
                b.direcao_maior,
                cor,
                rotulo,
            )
        )
        if f is not None and fracao >= 0.2:
            distribuidas.append(
                c3.CargaDistribuidaCena(
                    b.inicio, b.fim, (f.fx_kN_m, f.fy_kN_m, 0.0), "", d.COR_VENTO_ESCURO
                )  # fmt: skip
            )
    paineis: list[c3.PainelCena] = []
    textos: list[c3.TextoCena] = []
    for el in r.entrada.elementos:
        faces = _cantos_do_elemento(el)
        if el.tipo == vpb.TIPO_CILINDRO:
            base = el.ponto_1
            barras.append(
                c3.BarraCena(
                    el.nome,
                    base,
                    (base[0], base[1], base[2] + el.altura_m),
                    c3.Secao(c3.FORMA_TUBO_CIRCULAR, el.largura_x_m, el.largura_x_m),
                    None,
                    "#9aa7b8",
                )  # fmt: skip
            )
        else:
            for face in faces:
                paineis.append(c3.PainelCena(el.nome, tuple(face), d.COR_PAINEL,
                                             0.22 if el.em_linha else 0.35))  # fmt: skip
        topo = faces[0] if el.em_linha else faces[1]
        centro = tuple(sum(p[k] for p in topo) / len(topo) for k in range(3))
        textos.append(c3.TextoCena(centro, _rotulo_curto(el.nome, 18), "#2f4a6d"))  # type: ignore[arg-type]
    x0, x1, y0, y1, z0, z1 = _limites(r)
    centro_planta = ((x0 + x1) / 2, (y0 + y1) / 2)
    recuo = abs(w[0]) * (x1 - x0) / 2 + abs(w[1]) * (y1 - y0) / 2 + 0.1 * max(x1 - x0, y1 - y0, 1)
    ponta = (
        centro_planta[0] - w[0] * recuo,
        centro_planta[1] - w[1] * recuo,
        z0 + ALTURA_DA_SETA_DE_VENTO * (z1 - z0),
    )
    seta = c3.SetaCena(ponta, w, _titulo_da_direcao(angulo), d.COR_VENTO, larga=True,
                       comprimento_relativo=0.55)  # fmt: skip
    subtitulo = (
        f"{d.n(direcao.total_kN, 2)} kN no total ({d.n(direcao.estrutura_kN, 2)} kN nas barras"
        + (f", {d.n(direcao.elementos_kN, 2)} kN nos elementos" if direcao.elementos else "")
        + f") · tombamento {d.n(direcao.momento_tombamento_kNm, 1)} kN·m · torção "
        f"{d.n(direcao.torcao_kNm, 1)} kN·m"
    )
    return c3.Cena(
        barras=tuple(barras),
        paineis=tuple(paineis),
        setas=(seta,),
        distribuidas=tuple(distribuidas),
        textos=tuple(textos),
        titulo=f"{_titulo_da_direcao(angulo)} — carga em cada barra",
        subtitulo=subtitulo,
        escala=c3.EscalaDeCor(0.0, maior, "kN/m", "carga distribuída na barra"),
        eixo_vertical_do_modelo=eixo_vertical,
    )


def svg_vento_3d(
    r: vpb.ResultadoPorBarras,
    angulo: int,
    *,
    quantos_rotulos: int = 5,
    eixo_vertical: str = "Y",
    perfil_real: bool = True,
) -> str:
    """A estrutura vista de cima e de barlavento (o vento entra pela esquerda), cada barra com o
    perfil e a cor da sua carga (kN/m), o pente das mais carregadas e a seta grande do vento."""
    cena = cena_do_vento(r, angulo, quantos_rotulos=quantos_rotulos, eixo_vertical=eixo_vertical)
    desenho = c3.projetar(cena, azimute=angulo - 120.0, elevacao=26.0, largura=900.0,
                          altura=600.0, perfil_real=perfil_real)  # fmt: skip
    return svg_da_cena(desenho)


# ---------------------------------------------------------------------------------------------
# Planta
# ---------------------------------------------------------------------------------------------
def svg_vento_planta(r: vpb.ResultadoPorBarras, angulo: int) -> str:
    """A planta (de cima): as barras na cor da carga, os pilares com a seção na posição da alma, os
    reticulados (planos perpendiculares ao vento) com η, os elementos e as cotas gerais."""
    direcao = r.direcao(angulo)
    largura, altura = 900.0, 600.0
    x0, x1, y0, y1, _, _ = _limites(r)
    w = vpb.vento(angulo)
    lateral = (-w[1], w[0])
    margem = max(0.5, 0.08 * max(x1 - x0, y1 - y0))
    pontos = [(x0 - margem, -(y0 - margem)), (x1 + margem, -(y1 + margem))]
    enq = d.Enquadramento(pontos, (150, 120, largura - 150, altura - 130))

    def t(x: float, y: float) -> tuple[float, float]:
        return enq((x, -y))

    corpo: list[str] = []
    rotulos = d.Rotulos((10, 60, largura - 10, altura - 40))
    # planos (reticulados) perpendiculares ao vento
    centro = ((x0 + x1) / 2, (y0 + y1) / 2)
    meia_lateral = abs(lateral[0]) * (x1 - x0) / 2 + abs(lateral[1]) * (y1 - y0) / 2 + margem * 0.6
    for plano in direcao.planos:
        s = plano.coordenada_m
        base = (
            centro[0] + w[0] * (s - (centro[0] * w[0] + centro[1] * w[1])),
            centro[1] + w[1] * (s - (centro[0] * w[0] + centro[1] * w[1])),
        )
        a = (base[0] - lateral[0] * meia_lateral, base[1] - lateral[1] * meia_lateral)
        b = (base[0] + lateral[0] * meia_lateral, base[1] + lateral[1] * meia_lateral)
        cor = d.COR_CONTRAVENTADO
        corpo.append(
            d.linha(*t(*a), *t(*b), cor=cor, largura=1.0, tracejado="7 4 1.5 4", opacidade=0.55)
        )
        rotulo = f"{plano.nome} · η {d.n(plano.eta, 2)}"
        bx, by = t(*b)
        corpo.append(d.etiqueta(*rotulos.lugar(bx, by, rotulo, 9.5), rotulo, tamanho=9.5, cor=cor))
    maior = _maior_carga(direcao)
    escala = enq.escala
    # vigas e diagonais primeiro, pilares por cima
    pilares = []
    for b in r.entrada.barras:
        u = vpb._unitario(b.vetor)
        vertical = u is not None and abs(u[2]) > 0.95
        if vertical:
            pilares.append(b)
            continue
        f = direcao.da_barra(b.nome)
        fracao = (f.kN_m / maior) if f and f.forca_kN > 1e-9 else 0.0
        cor = d.cor_da_escala(0.15 + 0.85 * fracao) if fracao > 0 else d.COR_ESTRUTURA_CLARA
        espessura = max(2.0, min(b.menor_m * escala, 9.0))
        tracejado = "6 3" if u is not None and abs(u[2]) > 0.2 else ""
        corpo.append(
            d.linha(
                *t(b.inicio[0], b.inicio[1]),
                *t(b.fim[0], b.fim[1]),
                cor="#4a3527",
                largura=espessura + 1.4,
                opacidade=0.3,
                tracejado=tracejado,
            )
        )
        corpo.append(
            d.linha(
                *t(b.inicio[0], b.inicio[1]),
                *t(b.fim[0], b.fim[1]),
                cor=cor,
                largura=espessura,
                tracejado=tracejado,
            )
        )
    for b in pilares:
        f = direcao.da_barra(b.nome)
        fracao = (f.kN_m / maior) if f and f.forca_kN > 1e-9 else 0.0
        cor = d.cor_da_escala(0.15 + 0.85 * fracao) if fracao > 0 else d.COR_ESTRUTURA_CLARA
        cx, cy = t(b.inicio[0], b.inicio[1])
        alma = b.direcao_maior or (1.0, 0.0, 0.0)
        giro = -math.degrees(math.atan2(alma[1], alma[0]))
        a_px = max(b.maior_m * escala, 9.0)
        m_px = max(b.menor_m * escala, 7.0)
        corpo.append(
            f'<g transform="rotate({giro:.1f} {cx:.1f} {cy:.1f})">'
            + _secao_i(cx, cy, a_px, m_px, cor)
            + "</g>"
        )
        corpo.append(
            d.texto(
                cx + m_px / 2 + 8,
                cy + a_px / 2 + 6,
                _rotulo_curto(b.nome, 16),
                tamanho=9,
                ancora="start",
                cor=d.COR_SUAVE,
            )
        )
    # elementos
    for el in r.entrada.elementos:
        if el.em_linha and el.ponto_2 is not None:
            corpo.append(
                d.linha(
                    *t(el.ponto_1[0], el.ponto_1[1]),
                    *t(el.ponto_2[0], el.ponto_2[1]),
                    cor=d.COR_PAINEL,
                    largura=3.0,
                    tracejado="2 3",
                )
            )
            mx = (el.ponto_1[0] + el.ponto_2[0]) / 2
            my = (el.ponto_1[1] + el.ponto_2[1]) / 2
            rotulo = _rotulo_curto(el.nome, 18)
            corpo.append(
                d.etiqueta(*rotulos.lugar(*t(mx, my), rotulo, 9), rotulo, tamanho=9, cor="#2f4a6d")
            )
        else:
            cx, cy = el.ponto_1[0], el.ponto_1[1]
            if el.tipo == vpb.TIPO_CILINDRO:
                px, py = t(cx, cy)
                corpo.append(
                    f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{el.largura_x_m / 2 * escala:.1f}" '
                    f'fill="#9aa7b8" fill-opacity="0.35" stroke="#4f6b91"/>'
                )
            else:
                lx, ly = el.largura_x_m / 2, el.largura_y_m / 2
                corpo.append(
                    d.poligono(
                        [
                            t(cx - lx, cy - ly),
                            t(cx + lx, cy - ly),
                            t(cx + lx, cy + ly),
                            t(cx - lx, cy + ly),
                        ],
                        preenchimento="#9aa7b8",
                        contorno="#4f6b91",
                        opacidade=0.35,
                    )
                )
            rotulo = _rotulo_curto(el.nome, 18)
            corpo.append(
                d.etiqueta(*rotulos.lugar(*t(cx, cy), rotulo, 9), rotulo, tamanho=9, cor="#2f4a6d")
            )
    # cotas gerais
    corpo.append(
        d.cota(
            *t(x0, y0 - margem * 0.9),
            *t(x1, y0 - margem * 0.9),
            f"{d.n(x1 - x0, 2)} m",
            afastamento=12,
        )
    )
    corpo.append(
        d.cota(
            *t(x1 + margem * 0.9, y0),
            *t(x1 + margem * 0.9, y1),
            f"{d.n(y1 - y0, 2)} m",
            afastamento=-12,
        )
    )
    # vento
    meio_x, meio_y = t(*centro)
    (ax_, ay_), (bx_, by_) = t(x0, y0), t(x1, y1)
    meia_x, meia_y = abs(bx_ - ax_) / 2 + 28, abs(by_ - ay_) / 2 + 28
    # da borda da planta (na direção de onde vem o vento) para dentro, 70 px de seta
    alcance = min(
        meia_x / abs(w[0]) if abs(w[0]) > 1e-9 else math.inf,
        meia_y / abs(w[1]) if abs(w[1]) > 1e-9 else math.inf,
    )
    ex, ey = meio_x - w[0] * alcance, meio_y + w[1] * alcance
    sx, sy = ex - w[0] * 75, ey + w[1] * 75
    corpo.append(d.seta_de_vento(sx, sy, ex, ey, espessura=16))
    titulo_seta = _titulo_da_direcao(angulo)
    corpo.append(
        d.etiqueta(
            *rotulos.lugar(sx, sy - 26 if w[1] <= 0.5 else sy + 26, titulo_seta, 11),
            titulo_seta,
            tamanho=11,
            cor=d.COR_VENTO_ESCURO,
            peso="bold",
        )
    )
    # norte da planta: os eixos
    origem = (largura - 70.0, altura - 40.0)
    corpo.append(d.seta(*origem, origem[0] + 30, origem[1], cor=d.COR_SUAVE, largura=1.4, cabeca=6))
    corpo.append(d.seta(*origem, origem[0], origem[1] - 30, cor=d.COR_SUAVE, largura=1.4, cabeca=6))
    corpo.append(
        d.texto(origem[0] + 40, origem[1], "X", tamanho=10.5, cor=d.COR_SUAVE, peso="bold")
    )
    corpo.append(
        d.texto(origem[0], origem[1] - 40, "Y", tamanho=10.5, cor=d.COR_SUAVE, peso="bold")
    )
    corpo.append(
        d.legenda(
            22,
            altura - 18,
            (
                (d.cor_da_escala(0.8), "", "barra carregada (cor = kN/m)"),
                (d.COR_ESTRUTURA_CLARA, "", "sem carga (ao longo do vento)"),
                (d.COR_ESTRUTURA_CLARA, "6 3", "inclinada"),
                (d.COR_CONTRAVENTADO, "7 4 1.5 4", "reticulado (plano ⟂ vento)"),
                (d.COR_PAINEL, "2 3", "guarda-corpo / escada / painel"),
            ),
        )
    )
    return d.documento(
        largura,
        altura,
        corpo,
        f"Planta — {_titulo_da_direcao(angulo).lower()}",
        subtitulo=(
            "Reticulados numerados de barlavento (R1) para sotavento; η é a proteção da parte que "
            "fica atrás do anterior."
            if direcao.planos
            else "Vento diagonal: todas as barras com C_a = 2,0, sem proteção (a favor da "
            "segurança)."
        ),
    )


def _secao_i(cx: float, cy: float, altura: float, largura: float, cor: str) -> str:
    """Um I em planta, com a alma ao longo do eixo x local (antes do giro)."""
    mesa = max(1.6, largura * 0.16)
    alma = max(1.2, altura * 0.08)
    x0, x1 = cx - altura / 2, cx + altura / 2
    y0, y1 = cy - largura / 2, cy + largura / 2
    return (
        d.poligono(
            ((x0, y0), (x0 + mesa, y0), (x0 + mesa, y1), (x0, y1)),
            preenchimento=cor,
            contorno="#3a2a20",
            largura=0.6,
        )
        + d.poligono(
            ((x1 - mesa, y0), (x1, y0), (x1, y1), (x1 - mesa, y1)),
            preenchimento=cor,
            contorno="#3a2a20",
            largura=0.6,
        )
        + d.poligono(
            (
                (x0 + mesa, cy - alma / 2),
                (x1 - mesa, cy - alma / 2),
                (x1 - mesa, cy + alma / 2),
                (x0 + mesa, cy + alma / 2),
            ),
            preenchimento=cor,
            contorno="#3a2a20",
            largura=0.6,
        )
    )


# ---------------------------------------------------------------------------------------------
# Vista pelo vento (a sombra)
# ---------------------------------------------------------------------------------------------
def svg_vento_sombra(r: vpb.ResultadoPorBarras, angulo: int) -> str:
    """O que o vento "vê": a sombra de cada barra num plano perpendicular a ele. Os reticulados de
    barlavento ficam na frente e em tom forte; as partes protegidas (η < 1), mais claras."""
    direcao = r.direcao(angulo)
    largura, altura = 900.0, 520.0
    lateral = (-math.sin(math.radians(angulo)), math.cos(math.radians(angulo)), 0.0)

    def proj(p: Sequence[float]) -> tuple[float, float]:
        # quem olha para onde o vento sopra tem o lado direito em (sen θ, −cos θ)
        return (-(p[0] * lateral[0] + p[1] * lateral[1]), -(p[2]))

    pontos = []
    for b in r.entrada.barras:
        pontos.extend((proj(b.inicio), proj(b.fim)))
    for el in r.entrada.elementos:
        for face in _cantos_do_elemento(el):
            pontos.extend(proj(p) for p in face)
    pontos.append((pontos[0][0], -r.cota_do_terreno_m))
    enq = d.Enquadramento(pontos, (70, 80, largura - 230, altura - 70))
    escala = enq.escala

    def t(p: Sequence[float]) -> tuple[float, float]:
        return enq(proj(p))

    corpo: list[str] = []
    xs = [enq(p)[0] for p in pontos]
    _, y_chao = t((0.0, 0.0, r.cota_do_terreno_m))
    corpo.append(d.terreno(min(xs) - 30, max(xs) + 30, y_chao))
    ordem_planos = {p.nome: k for k, p in enumerate(direcao.planos)}
    n_planos = max(len(direcao.planos), 1)
    forcas = {f.barra: f for f in direcao.barras}
    barras = sorted(
        r.entrada.barras,
        key=lambda b: -ordem_planos.get(forcas[b.nome].plano, n_planos),
    )
    for b in barras:
        f = forcas[b.nome]
        if f.area_m2 <= 1e-9:
            continue
        a, c = t(b.inicio), t(b.fim)
        comprimento = math.hypot(c[0] - a[0], c[1] - a[1])
        meia = max(f.largura_vista_m * escala / 2, 1.0)
        if comprimento <= 1e-6:
            continue
        ux, uy = (c[0] - a[0]) / comprimento, (c[1] - a[1]) / comprimento
        px, py = -uy * meia, ux * meia
        k = ordem_planos.get(f.plano)
        if k is None:
            cor, opac = "#8c96a3", 0.55
        else:
            cor = d.cor_da_escala(
                1.0 - 0.75 * k / max(n_planos - 1, 1), ("#d9e3f0", "#7c9cc4", "#1f5fbf", "#123a75")
            )
            opac = 0.9 if f.eta >= 0.999 else 0.55
        corpo.append(
            d.poligono(
                (
                    (a[0] + px, a[1] + py),
                    (c[0] + px, c[1] + py),
                    (c[0] - px, c[1] - py),
                    (a[0] - px, a[1] - py),
                ),
                preenchimento=cor,
                contorno="#1d2a3a",
                largura=0.5,
                opacidade=opac,
            )
        )
    for el in r.entrada.elementos:
        silhueta = _envoltoria([t(p) for face in _cantos_do_elemento(el) for p in face])
        corpo.append(
            d.poligono(
                silhueta,
                preenchimento=d.COR_PAINEL,
                contorno="#4f6b91",
                opacidade=0.3,
                tracejado="3 2",
            )
        )
    # contornos dos reticulados
    for plano in direcao.planos[:6]:
        l0, l1, z0, z1 = plano.retangulo
        p0, p1 = enq((-l1, -z1)), enq((-l0, -z0))
        corpo.append(
            f'<rect x="{p0[0]:.1f}" y="{p0[1]:.1f}" width="{p1[0] - p0[0]:.1f}" '
            f'height="{p1[1] - p0[1]:.1f}" fill="none" stroke="{d.COR_CONTRAVENTADO}" '
            f'stroke-width="0.8" stroke-dasharray="4 3" stroke-opacity="0.5"/>'
        )
    # quadro dos reticulados à direita
    xq, yq = largura - 210, 86
    corpo.append(
        d.texto(xq, yq, "Reticulados (de barlavento)", tamanho=11, ancora="start", peso="bold")
    )
    for k, plano in enumerate(direcao.planos[:12]):
        y = yq + 20 + 17 * k
        corpo.append(
            d.texto(
                xq,
                y,
                f"{plano.nome}: φ {d.n(plano.phi, 2)} · C_a {d.n(plano.ca, 2)}"
                f" · η {d.n(plano.eta, 2)}",
                tamanho=10,
                ancora="start",
                cor=d.COR_SUAVE,
            )
        )
    if len(direcao.planos) > 12:
        corpo.append(
            d.texto(
                xq,
                yq + 20 + 17 * 12,
                f"… e mais {len(direcao.planos) - 12}",
                tamanho=10,
                ancora="start",
                cor=d.COR_SUAVE,
            )
        )
    if not direcao.planos:
        corpo.append(
            d.texto(
                xq,
                yq + 20,
                "vento diagonal: sem planos,",
                tamanho=10,
                ancora="start",
                cor=d.COR_SUAVE,
            )
        )
        corpo.append(
            d.texto(
                xq,
                yq + 36,
                "C_a = 2,0 e η = 1 em tudo",
                tamanho=10,
                ancora="start",
                cor=d.COR_SUAVE,
            )
        )
    corpo.append(
        d.legenda(
            22,
            altura - 18,
            (
                ("#123a75", "", "barlavento (R1)"),
                ("#7c9cc4", "", "reticulados de trás"),
                ("#8c96a3", "", "fora dos planos (C_a 2,0)"),
                (d.COR_PAINEL, "3 2", "elementos"),
            ),
        )
    )
    return d.documento(
        largura,
        altura,
        corpo,
        f"O que o vento vê — {_titulo_da_direcao(angulo).lower()}",
        subtitulo="Área de sombra de cada barra (projeção num plano perpendicular ao vento, "
        "NBR 6123 8.3); tom claro = parte protegida pelo reticulado da frente (η).",
    )
