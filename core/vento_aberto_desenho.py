"""Desenhos do vento em estruturas abertas (NBR 6123:2023, capítulo 8), para a página e o memorial.

* :func:`cena_dos_porticos` — a grade de pórticos em 3D, com a **força de cada pórtico em cada
  nível** (a de barlavento cheia, as de trás com o seu η), a faixa da base e o φ, o C_a e o η de
  cada pórtico;
* :func:`cena_do_vento` — o vento barra a barra em 3D: cada barra com o perfil e a cor da carga;
* :func:`desenho_das_forcas_por_nivel` — a elevação com a força do vento em cada nível nas duas
  direções, a cortante de cada andar, a força que vai direto à fundação e o momento na base.

As duas cenas usam o núcleo :mod:`core.cena_3d` (SVG na página, PNG no memorial); o diagrama dos
níveis é um :class:`core.cena_3d.Desenho2D` montado direto, que os mesmos dois desenhistas leem. O
registro guarda a cena (ou os números do diagrama) e o memorial a desenha de novo. Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core import cena_3d as c3
from core import cena_do_modelo as cm
from core import vento_estrutura_aberta as va
from core import vento_por_barras as vpb
from core import vento_por_nivel as vpn

Ponto = tuple[float, float, float]

COR_VENTO = "#d4760a"
COR_VENTO_ESCURO = "#a14f00"
COR_CONTRAVENTADO = "#1f5fbf"
COR_PORTICO = "#5b6470"
COR_LIGACAO = "#aab1bb"  # vigas na direção do vento e linhas paralelas a ele
COR_PAINEL = "#7c9cc4"
COR_TEXTO = "#1f2328"
COR_SUAVE = "#6b7280"
COR_BASE = "#8a7f72"
COR_CORTANTE = "#1f5fbf"
COR_CORTANTE_FUNDO = "#dbe7f7"
#: Da altura da estrutura: onde a seta grande do vento chega.
ALTURA_DA_SETA_DE_VENTO = 0.6


def _n(valor: float, casas: int = 1) -> str:
    if not math.isfinite(valor):
        return "∞"
    if round(valor, casas) == 0:
        valor = 0.0
    return f"{valor:.{casas}f}".replace(".", ",")


def titulo_da_direcao(angulo: int) -> str:
    return f"Vento a {angulo}° ({vpb.SENTIDOS.get(angulo, '')})"


def rotulo_curto(nome: str, limite: int = 22) -> str:
    return nome if len(nome) <= limite else nome[: limite - 1] + "…"


def _vezes(v: Sequence[float], k: float) -> Ponto:
    return (v[0] * k, v[1] * k, v[2] * k)


def _azimute_da_vista(sentido: Sequence[float]) -> float:
    """De barlavento e de um lado, de cima: o olho fica 55° girado da direção de onde vem o vento."""
    de_onde = math.degrees(math.atan2(-sentido[1], -sentido[0]))
    return de_onde + 55.0


# ---------------------------------------------------------------------------------------------
# A grade de pórticos (método dos reticulados por pórtico)
# ---------------------------------------------------------------------------------------------
def _sentido_da_grade(d: va.VentoNaDirecao) -> tuple[float, float, float]:
    """Para onde o vento sopra: do pórtico de barlavento (P1) para os outros."""
    coordenadas = [p.coordenada_m for p in d.planos]
    p1 = next((p.coordenada_m for p in d.planos if p.posicao == 1), min(coordenadas))
    sinal = -1.0 if len(coordenadas) > 1 and p1 >= max(coordenadas) - 1e-9 else 1.0
    return (sinal, 0.0, 0.0) if d.direcao == "X" else (0.0, sinal, 0.0)


def vista_dos_porticos(d: va.VentoNaDirecao) -> tuple[float, float]:
    return _azimute_da_vista(_sentido_da_grade(d)), 24.0


def forca_do_portico_no_nivel(d: va.VentoNaDirecao, j: int, i: int) -> float:
    """Força do pórtico ``j`` (índice em ``d.planos``) no nível ``i``: estrutura + guarda-corpo."""
    estrutura = d.estrutura_por_portico_kN[j][i] if d.estrutura_por_portico_kN else 0.0
    guarda = d.guarda_corpo_por_portico_kN[j][i] if d.guarda_corpo_por_portico_kN else 0.0
    return estrutura + guarda


def cena_dos_porticos(g: va.GeometriaAberta, d: va.VentoNaDirecao) -> c3.Cena:
    """A plataforma em 3D com a força de cada pórtico perpendicular ao vento em cada nível.

    Pilares e vigas com a largura do cálculo; os pórticos perpendiculares ao vento em azul (com
    diagonais) ou grafite; as vigas que vão na direção do vento claras. Uma seta por pórtico e
    nível, do tamanho da força; a faixa da base (até meio primeiro andar) vai à fundação.
    """
    sentido = _sentido_da_grade(d)
    xs = [g.comprimento_x_m * i / g.vaos_x for i in range(g.vaos_x + 1)]
    ys = [g.largura_y_m * j / g.vaos_y for j in range(g.vaos_y + 1)]
    h = g.altura_m
    pilar = c3.Secao(c3.FORMA_CHEIA, g.largura_pilar_m, g.largura_pilar_m)
    viga = c3.Secao(c3.FORMA_CHEIA, g.altura_viga_m, min(0.15, g.altura_viga_m))
    em_x = d.direcao == "X"
    # Coordenada ao longo do vento → plano (pórtico) e a sua posição de barlavento a sotavento.
    planos = {round(p.coordenada_m, 6): p for p in d.planos}

    def plano_de(x: float, y: float) -> va.PlanoReticulado | None:
        return planos.get(round(x if em_x else y, 6))

    def cor_da_viga(p: va.PlanoReticulado | None) -> str:
        if p is None:
            return COR_LIGACAO
        return COR_CONTRAVENTADO if p.contraventado else COR_PORTICO

    barras: list[c3.BarraCena] = []
    for x in xs:
        for y in ys:
            p = plano_de(x, y)
            cor = COR_CONTRAVENTADO if p is not None and p.contraventado else COR_PORTICO
            barras.append(c3.BarraCena(f"P {x:g} {y:g}", (x, y, 0.0), (x, y, h), pilar, None, cor))
    for z in g.cotas_m:
        for y in ys:  # vigas ao longo de X
            for x0, x1 in zip(xs, xs[1:], strict=False):
                cor = cor_da_viga(None if em_x else plano_de(x0, y))
                nome = f"VX {z:g} {y:g} {x0:g}"
                barras.append(c3.BarraCena(nome, (x0, y, z), (x1, y, z), viga, (0, 0, 1.0), cor))
        for x in xs:  # vigas ao longo de Y
            for y0, y1 in zip(ys, ys[1:], strict=False):
                cor = cor_da_viga(plano_de(x, y0) if em_x else None)
                nome = f"VY {z:g} {x:g} {y0:g}"
                barras.append(c3.BarraCena(nome, (x, y0, z), (x, y1, z), viga, (0, 0, 1.0), cor))
    # Diagonais (posição esquemática: nos primeiros painéis das linhas contraventadas).
    for direcao_da_linha in ("X", "Y"):
        if direcao_da_linha == "X":  # linhas y = constante, painéis ao longo de x
            linhas = sorted(range(len(ys)), key=lambda k: (min(k, len(ys) - 1 - k), k))
            contraventadas = [ys[k] for k in linhas[: g.linhas_contraventadas_x]]
            paineis = list(zip(xs, xs[1:], strict=False))[: g.paineis_contraventados_x]
            por_painel, meio = g.diagonais_por_painel_x, g.meio_painel_x
        else:
            linhas = sorted(range(len(xs)), key=lambda k: (min(k, len(xs) - 1 - k), k))
            contraventadas = [xs[k] for k in linhas[: g.linhas_contraventadas_y]]
            paineis = list(zip(ys, ys[1:], strict=False))[: g.paineis_contraventados_y]
            por_painel, meio = g.diagonais_por_painel_y, g.meio_painel_y
        paralela = (direcao_da_linha == "X") == em_x  # linha paralela ao vento
        cor = COR_LIGACAO if paralela else COR_CONTRAVENTADO
        for c in contraventadas:
            baixo = 0.0
            for z in g.cotas_m:
                for s0, s1 in paineis:
                    meio_s = (s0 + s1) / 2
                    if meio:  # V invertido: das pontas embaixo ao meio em cima
                        trechos = [((s0, baixo), (meio_s, z)), ((s1, baixo), (meio_s, z))]
                    else:
                        trechos = [((s0, baixo), (s1, z))]
                        if por_painel == 2:
                            trechos.append(((s0, z), (s1, baixo)))
                    for (sa, za), (sb, zb) in trechos:
                        a = (sa, c, za) if direcao_da_linha == "X" else (c, sa, za)
                        b = (sb, c, zb) if direcao_da_linha == "X" else (c, sb, zb)
                        barras.append(c3.BarraCena(f"D {a} {b}", a, b, None, None, cor))
                baixo = z
    # Guarda-corpo: corrimão no perímetro de cada piso e montantes nos cantos (linhas).
    if g.guarda_corpo:
        lx, ly = g.comprimento_x_m, g.largura_y_m
        cantos = ((0.0, 0.0), (lx, 0.0), (lx, ly), (0.0, ly))
        for z in g.cotas_m:
            topo = z + g.altura_guarda_corpo_m
            for k in range(4):
                (xa, ya), (xb, yb) = cantos[k], cantos[(k + 1) % 4]
                barras.append(c3.BarraCena(f"GC {z:g} {k}", (xa, ya, topo), (xb, yb, topo), None,
                                           None, COR_PAINEL))  # fmt: skip
                barras.append(c3.BarraCena(f"GCm {z:g} {k}", (xa, ya, z), (xa, ya, topo), None,
                                           None, COR_PAINEL))  # fmt: skip
    # Forças: uma seta por pórtico e nível, no meio do pórtico, chegando pelo lado de barlavento.
    setas: list[c3.SetaCena] = []
    meio_da_frente = g.largura_y_m / 2 if em_x else g.comprimento_x_m / 2
    textos: list[c3.TextoCena] = []

    def no(u: float, z: float) -> Ponto:
        """O meio do pórtico na coordenada u (ao longo do vento), na cota z."""
        return (u, meio_da_frente, z) if em_x else (meio_da_frente, u, z)

    for j, plano in enumerate(d.planos):
        u = plano.coordenada_m
        for i, nivel in enumerate(d.niveis):
            forca = forca_do_portico_no_nivel(d, j, i)
            if forca <= 1e-9:
                continue
            rotulo = f"P{plano.posicao}: {_n(forca)} kN"
            setas.append(
                c3.SetaCena(no(u, nivel.cota_m), _vezes(sentido, forca), rotulo, COR_VENTO)
            )
        if d.base_por_portico_kN and d.niveis and d.base_por_portico_kN[j] > 1e-9:
            z_base = d.niveis[0].faixa_m[0] / 2
            forca_base = d.base_por_portico_kN[j]
            setas.append(c3.SetaCena(no(u, z_base), _vezes(sentido, forca_base), "", COR_BASE))
        topo = h + (g.altura_guarda_corpo_m if g.guarda_corpo else 0.0) + 0.06 * max(h, 1.0)
        canto = (u, 0.0, topo) if em_x else (0.0, u, topo)
        texto = f"P{plano.posicao} · φ {_n(plano.phi, 2)} · C_a {_n(plano.ca, 2)} · η {_n(plano.eta, 2)}"
        cor = COR_CONTRAVENTADO if plano.contraventado else COR_PORTICO
        textos.append(c3.TextoCena(canto, texto, cor))
    # O total de cada nível (todos os pórticos, guarda-corpos e equipamentos), na frente.
    p1 = next((p.coordenada_m for p in d.planos if p.posicao == 1), 0.0)
    for nivel in d.niveis:
        ponto = (p1, 0.0, nivel.cota_m) if em_x else (0.0, p1, nivel.cota_m)
        rotulo = f"nível {nivel.nivel} (z = {_n(nivel.cota_m, 2)} m): {_n(nivel.total_kN)} kN"
        textos.append(c3.TextoCena(ponto, rotulo, COR_VENTO_ESCURO))
    # A seta grande do vento, chegando ao pórtico de barlavento.
    largura = max(g.comprimento_x_m, g.largura_y_m, h)
    recuo = 0.32 * largura
    z_seta = 0.22 * h
    alvo = (p1 - sentido[0] * recuo, meio_da_frente, z_seta)
    if not em_x:
        alvo = (meio_da_frente, p1 - sentido[1] * recuo, z_seta)
    setas.append(c3.SetaCena(alvo, sentido, f"Vento em {d.direcao}", COR_VENTO, larga=True,
                             comprimento_relativo=0.3))  # fmt: skip
    equipamentos = sum(f for nivel in d.equipamentos_por_nivel for _, f, _ in nivel)
    subtitulo = (
        f"{_n(d.total_kN)} kN no total, momento na base {_n(d.momento_na_base_kNm)} kN·m · setas: "
        f"força de cada pórtico em cada nível; cinza: base ({_n(d.forca_na_base_kN)} kN, vai à "
        "fundação)"
        + (f"; equipamentos {_n(equipamentos)} kN no centro deles" if equipamentos > 1e-9 else "")
    )
    return c3.Cena(
        barras=tuple(barras),
        setas=tuple(setas),
        textos=tuple(textos),
        titulo=f"Vento em {d.direcao} (classe {d.classe or '—'}) — força em cada pórtico e nível",
        subtitulo=subtitulo,
        legenda=(
            (COR_CONTRAVENTADO, "pórtico contraventado"),
            (COR_PORTICO, "pórtico sem diagonais"),
            (COR_PAINEL, "guarda-corpo"),
            (COR_VENTO, "força (característica)"),
        ),
        eixo_vertical_do_modelo="",
    )


def figura_dos_porticos_para_o_registro(
    g: va.GeometriaAberta, d: va.VentoNaDirecao
) -> dict[str, object]:
    azimute, elevacao = vista_dos_porticos(d)
    return {
        "cena": c3.cena_para_dicionario(cena_dos_porticos(g, d)),
        "legenda": (
            f"Vento em {d.direcao}: força característica de cada pórtico em cada nível (NBR 6123:2023, "
            "8.3 e 8.4) — o de barlavento cheio, os de trás com o fator de proteção η."
        ),
        "azimute": azimute,
        "elevacao": elevacao,
        "perfil_real": True,
    }


# ---------------------------------------------------------------------------------------------
# O vento barra a barra
# ---------------------------------------------------------------------------------------------
def maior_carga(direcao: vpb.VentoNaDirecao) -> float:
    return max((f.kN_m for f in direcao.barras), default=0.0) or 1.0


def limites_do_desenho(
    r: vpb.ResultadoPorBarras,
) -> tuple[float, float, float, float, float, float]:
    xs, ys, zs = [], [], []
    for b in r.entrada.barras:
        for p in (b.inicio, b.fim):
            xs.append(p[0])
            ys.append(p[1])
            zs.append(p[2])
    for el in r.entrada.elementos:
        for q in (el.ponto_1, el.ponto_2):
            if q is not None:
                xs.append(q[0])
                ys.append(q[1])
                zs.append(q[2] + el.altura_m)
    return min(xs), max(xs), min(ys), max(ys), r.cota_do_terreno_m, max(zs)


def faces_do_elemento(el: vpb.ElementoAoVento) -> list[list[Ponto]]:
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


def vista_do_vento(angulo: int) -> tuple[float, float]:
    """(azimute, elevação) da vista 3D do vento barra a barra (a mesma da página)."""
    return angulo - 120.0, 26.0


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
    maior = maior_carga(direcao)
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
        cor = c3.cor_da_escala(0.15 + 0.85 * fracao) if fracao > 0 else COR_LIGACAO
        rotulo = (
            f"{rotulo_curto(b.nome)}: {_n(f.kN_m, 3)} kN/m"
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
                    b.inicio, b.fim, (f.fx_kN_m, f.fy_kN_m, 0.0), "", COR_VENTO_ESCURO
                )  # fmt: skip
            )
    paineis: list[c3.PainelCena] = []
    textos: list[c3.TextoCena] = []
    for el in r.entrada.elementos:
        faces = faces_do_elemento(el)
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
                paineis.append(c3.PainelCena(el.nome, tuple(face), COR_PAINEL,
                                             0.22 if el.em_linha else 0.35))  # fmt: skip
        topo = faces[0] if el.em_linha else faces[1]
        centro = (
            sum(p[0] for p in topo) / len(topo),
            sum(p[1] for p in topo) / len(topo),
            sum(p[2] for p in topo) / len(topo),
        )
        textos.append(c3.TextoCena(centro, rotulo_curto(el.nome, 18), "#2f4a6d"))
    x0, x1, y0, y1, z0, z1 = limites_do_desenho(r)
    centro_planta = ((x0 + x1) / 2, (y0 + y1) / 2)
    recuo = abs(w[0]) * (x1 - x0) / 2 + abs(w[1]) * (y1 - y0) / 2 + 0.1 * max(x1 - x0, y1 - y0, 1)
    ponta = (
        centro_planta[0] - w[0] * recuo,
        centro_planta[1] - w[1] * recuo,
        z0 + ALTURA_DA_SETA_DE_VENTO * (z1 - z0),
    )
    seta = c3.SetaCena(ponta, w, titulo_da_direcao(angulo), COR_VENTO, larga=True,
                       comprimento_relativo=0.55)  # fmt: skip
    subtitulo = (
        f"{_n(direcao.total_kN, 2)} kN no total ({_n(direcao.estrutura_kN, 2)} kN nas barras"
        + (f", {_n(direcao.elementos_kN, 2)} kN nos elementos" if direcao.elementos else "")
        + f") · tombamento {_n(direcao.momento_tombamento_kNm, 1)} kN·m · torção "
        f"{_n(direcao.torcao_kNm, 1)} kN·m"
    )
    return c3.Cena(
        barras=tuple(barras),
        paineis=tuple(paineis),
        setas=(seta,),
        distribuidas=tuple(distribuidas),
        textos=tuple(textos),
        titulo=f"{titulo_da_direcao(angulo)} — carga em cada barra",
        subtitulo=subtitulo,
        escala=c3.EscalaDeCor(0.0, maior, "kN/m", "carga distribuída na barra"),
        eixo_vertical_do_modelo=eixo_vertical,
    )


def figura_do_vento_para_o_registro(
    r: vpb.ResultadoPorBarras, angulo: int, *, eixo_vertical: str = "Y"
) -> dict[str, object]:
    azimute, elevacao = vista_do_vento(angulo)
    return {
        "cena": c3.cena_para_dicionario(cena_do_vento(r, angulo, eixo_vertical=eixo_vertical)),
        "legenda": (
            f"{titulo_da_direcao(angulo)}: carga característica em cada barra (kN/m), pela área de "
            "sombra (NBR 6123:2023, 8.3 e 8.4)."
        ),
        "azimute": azimute,
        "elevacao": elevacao,
        "perfil_real": True,
    }


# ---------------------------------------------------------------------------------------------
# A força em cada nível (elevação)
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ForcasNosNiveis:
    """As forças de uma direção do vento levadas aos níveis da estrutura."""

    rotulo: str  # "Vento em X", "W0 (+X)"…
    cotas_m: tuple[float, ...]  # dos níveis, a partir do terreno
    forcas_kN: tuple[float, ...]  # característica, em cada nível
    base_kN: float  # o que vai direto à fundação

    @property
    def total_kN(self) -> float:
        return sum(self.forcas_kN) + self.base_kN

    @property
    def momento_na_base_kNm(self) -> float:
        """Σ F·z dos níveis (a parcela da base chega ao pé e não faz braço)."""
        return sum(f * z for f, z in zip(self.forcas_kN, self.cotas_m, strict=True))

    @property
    def cortantes_kN(self) -> tuple[float, ...]:
        """Cortante do andar abaixo de cada nível: a soma das forças dele para cima."""
        return tuple(sum(self.forcas_kN[i:]) for i in range(len(self.forcas_kN)))


def forcas_da_grade(r: va.ResultadoVentoAberto) -> list[ForcasNosNiveis]:
    return [
        ForcasNosNiveis(
            f"Vento em {d.direcao} (classe {d.classe or '—'})",
            tuple(n.cota_m for n in d.niveis),
            tuple(n.total_kN for n in d.niveis),
            d.forca_na_base_kN,
        )
        for d in (r.x, r.y)
    ]


def forcas_do_barra_a_barra(vn: vpn.VentoPorNivel) -> list[ForcasNosNiveis]:
    """Uma coluna para X (a maior entre W0 e W180) e uma para Y (W90 e W270), com a força de cada
    nível na direção do vento (o módulo de F_x e F_y)."""
    saida = []
    for par in ((0, 180), (90, 270)):
        candidatas = [d for d in vn.direcoes if d.angulo in par and d.niveis]
        if not candidatas:
            continue
        d = max(candidatas, key=lambda d: math.hypot(d.fx_kN, d.fy_kN))
        saida.append(
            ForcasNosNiveis(
                f"{d.codigo} ({vpb.SENTIDOS.get(d.angulo, '')})",
                tuple(n.nivel.cota_m for n in d.niveis),
                tuple(n.forca_kN for n in d.niveis),
                math.hypot(d.fx_base_kN, d.fy_base_kN),
            )
        )
    return saida


def _texto_largura(conteudo: str, tamanho: float) -> float:
    return c3.largura_do_texto(conteudo, tamanho)


def desenho_das_forcas_por_nivel(
    colunas: Sequence[ForcasNosNiveis], *, titulo: str = "", subtitulo: str = ""
) -> c3.Desenho2D:
    """A elevação: em cada direção, os níveis em escala, a força de cada um (seta do tamanho da
    força), a cortante de cada andar em degraus, a base que vai à fundação e o momento na base."""
    largura = 460.0 * max(len(colunas), 1) + 40.0
    altura = 560.0
    topo_util, base_util = 120.0, altura - 120.0
    cotas = [z for c in colunas for z in c.cotas_m]
    z_max = max([*cotas, 0.5]) * 1.08
    maior = max([f for c in colunas for f in (*c.forcas_kN, c.base_kN)] + [1e-9])
    maior_v = max([v for c in colunas for v in c.cortantes_kN] + [1e-9])

    def y_de(z: float) -> float:
        return base_util - (base_util - topo_util) * z / z_max

    itens: list[c3.Poligono2D | c3.Linha2D | c3.Seta2D | c3.Etiqueta2D] = []
    for k, c in enumerate(colunas):
        x0 = 40.0 + 460.0 * k
        x_pilar = x0 + 232.0
        itens.append(c3.Etiqueta2D(x0 + 230, 92, c.rotulo, COR_VENTO_ESCURO, 12.5, "bold", False))
        # terreno e o "pilar" (a altura da estrutura)
        itens.append(c3.Linha2D((x0 + 30, base_util), (x0 + 400, base_util), COR_BASE, 1.6))
        for xh in range(int(x0 + 34), int(x0 + 400), 10):
            itens.append(c3.Linha2D((xh, base_util), (xh - 6, base_util + 7), COR_BASE, 0.8))
        topo = max(c.cotas_m, default=0.0)
        itens.append(c3.Linha2D((x_pilar, base_util), (x_pilar, y_de(topo)), "#3f4652", 3.0))
        # cortante em degraus, à direita do pilar
        escala_v = 110.0 / maior_v
        abaixo = 0.0
        for z, v in zip(c.cotas_m, c.cortantes_kN, strict=True):
            ya, yb = y_de(abaixo), y_de(z)
            xa, xv = x_pilar + 12, x_pilar + 12 + v * escala_v
            degrau = ((xa, ya), (xv, ya), (xv, yb), (xa, yb))
            itens.append(c3.Poligono2D(degrau, COR_CORTANTE_FUNDO, COR_CORTANTE, 0.8, 0.9))
            rotulo = f"V = {_n(v)} kN"
            meio = (ya + yb) / 2
            x_rotulo = xv + 6 + _texto_largura(rotulo, 9.5) / 2
            itens.append(c3.Etiqueta2D(x_rotulo, meio, rotulo, COR_CORTANTE, 9.5))
            abaixo = z
        # níveis e forças
        for i, (z, f) in enumerate(zip(c.cotas_m, c.forcas_kN, strict=True)):
            y = y_de(z)
            itens.append(c3.Linha2D((x_pilar - 40, y), (x_pilar + 10, y), "#3f4652", 2.2))
            comprimento = 30.0 + 100.0 * f / maior
            cauda, ponta = (x_pilar - 42 - comprimento, y), (x_pilar - 42, y)
            itens.append(c3.Seta2D(cauda, ponta, COR_VENTO, 2.6, 10.0))
            rotulo = f"F{i + 1} = {_n(f)} kN"
            meio = x_pilar - 42 - comprimento / 2
            itens.append(c3.Etiqueta2D(meio, y - 13, rotulo, COR_VENTO_ESCURO, 10.0, "bold"))
            itens.append(
                c3.Etiqueta2D(x0 + 22, y, f"{_n(z, 2)} m", COR_SUAVE, 9.5, "normal", False)
            )
        if c.base_kN > 1e-9:
            y = base_util - 12
            comprimento = 20.0 + 100.0 * c.base_kN / maior
            cauda, ponta = (x_pilar - 4 - comprimento, y), (x_pilar - 4, y)
            itens.append(c3.Seta2D(cauda, ponta, COR_BASE, 1.8, 8.0))
            rotulo = f"base {_n(c.base_kN)} kN → fundação"
            meio = x_pilar - 8 - _texto_largura(rotulo, 9.5) / 2  # termina antes do pilar
            itens.append(c3.Etiqueta2D(meio, y - 15, rotulo, COR_BASE, 9.5))
        # resumo embaixo
        resumo = f"Total {_n(c.total_kN)} kN · M na base = Σ F·z = {_n(c.momento_na_base_kNm)} kN·m"
        itens.append(
            c3.Etiqueta2D(x0 + 230, base_util + 46, resumo, COR_TEXTO, 10.5, "bold", False)
        )
    return c3.Desenho2D(
        largura,
        altura,
        tuple(itens),
        titulo or "Força do vento em cada nível",
        subtitulo
        or "Forças características. Em azul, a cortante de cada andar (a soma das forças dele para "
        "cima): é o que o contraventamento do andar leva.",
        legenda=(
            (COR_VENTO, "força no nível"),
            (COR_CORTANTE, "cortante do andar"),
            (COR_BASE, "base"),
        ),
    )


def niveis_para_o_registro(
    colunas: Sequence[ForcasNosNiveis], *, titulo: str = "", subtitulo: str = ""
) -> dict[str, object]:
    return {
        "titulo": titulo,
        "subtitulo": subtitulo,
        "colunas": [
            {
                "rotulo": c.rotulo,
                "cotas_m": [round(z, 4) for z in c.cotas_m],
                "forcas_kN": [round(f, 4) for f in c.forcas_kN],
                "base_kN": round(c.base_kN, 4),
            }
            for c in colunas
        ],
    }


def niveis_do_registro(dados: Mapping[str, Any]) -> tuple[list[ForcasNosNiveis], str, str]:
    """O inverso de :func:`niveis_para_o_registro`; o que vier estragado fica de fora."""
    colunas: list[ForcasNosNiveis] = []
    brutas = dados.get("colunas")
    for item in brutas if isinstance(brutas, list) else []:
        try:
            cotas = tuple(float(z) for z in item["cotas_m"])
            forcas = tuple(float(f) for f in item["forcas_kN"])
            base = float(item.get("base_kN") or 0.0)
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        valores = (*cotas, *forcas, base)
        if len(cotas) != len(forcas) or not all(math.isfinite(v) for v in valores):
            continue
        colunas.append(ForcasNosNiveis(str(item.get("rotulo") or ""), cotas, forcas, base))
    return colunas, str(dados.get("titulo") or ""), str(dados.get("subtitulo") or "")
