"""Figuras que vão junto das reações nas bases para quem projeta a fundação.

* :func:`figura_dos_eixos` — a figura padrão: um sistema de eixos só (X e Y na planta, Z para cima)
  com os sentidos positivos das forças e dos momentos da tabela no pé de um pilar, a planta como
  aparece nos desenhos e como ler os sinais (ação × reação, correspondência com o SolidWorks).
* :func:`figura_do_projeto` — o modelo em 3D com cada pé com o rótulo (A1, A2…) e o triedro dos
  eixos da fundação, para achar no desenho a linha da tabela.
* :func:`png_para_o_excel` — as figuras redimensionadas para a aba Desenhos do Excel.

Convenção nos desenhos 2D: ⊙ (círculo com um ponto) é o eixo saindo da tela, a ponta da flecha
vindo para quem olha; ⊗ (círculo com um X) é o eixo entrando na tela, a cauda da flecha se
afastando.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from PIL import Image, ImageDraw

from core import desenho_girado as dg
from core import leitura_do_modelo as ld
from core import reacoes_nas_bases as rb
from core import vento_por_barras as vpb
from core.beam_charts import ImagemDiagrama, _fonte, figura_final

ESC = dg.ESC
_LARGURA_PX, _ALTURA_PX = 1180, 880
_COR_SW = "#7c3aed"  # eixos do SolidWorks
_COR_FUND = "#1d4ed8"  # eixos da fundação
_COR_ACAO = "#b91c1c"
_COR_REACAO = "#15803d"
_COR_QUADRO = "#cbd5e1"
_COR_CONCRETO = "#e2e8f0"
_COR_ACO = "#64748b"

Ponto = tuple[float, float]


def _p(x: float, y: float) -> Ponto:
    return (x * ESC, y * ESC)


def simbolo_saindo(d: ImageDraw.ImageDraw, centro: Ponto, raio: float, cor: str) -> None:
    """⊙ — o eixo saindo da tela (a ponta da flecha vindo para quem olha)."""
    cx, cy = centro
    d.ellipse([cx - raio, cy - raio, cx + raio, cy + raio], fill="#ffffff", outline=cor,
              width=2 * ESC)  # fmt: skip
    r = max(raio * 0.28, 2 * ESC)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=cor)


def simbolo_entrando(d: ImageDraw.ImageDraw, centro: Ponto, raio: float, cor: str) -> None:
    """⊗ — o eixo entrando na tela (a cauda da flecha se afastando de quem olha)."""
    cx, cy = centro
    d.ellipse([cx - raio, cy - raio, cx + raio, cy + raio], fill="#ffffff", outline=cor,
              width=2 * ESC)  # fmt: skip
    k = raio * 0.62
    d.line([(cx - k, cy - k), (cx + k, cy + k)], fill=cor, width=2 * ESC)
    d.line([(cx - k, cy + k), (cx + k, cy - k)], fill=cor, width=2 * ESC)


def _quadro(d: ImageDraw.ImageDraw, caixa: Sequence[float], titulo: str) -> None:
    x0, y0, x1, y1 = (v * ESC for v in caixa)
    d.rounded_rectangle([x0, y0, x1, y1], radius=8 * ESC, outline=_COR_QUADRO, width=ESC)
    d.text((x0 + 12 * ESC, y0 + 10 * ESC), titulo, fill=dg.COR_TEXTO, font=_fonte(13 * ESC))


def _triedro(
    d: ImageDraw.ImageDraw,
    origem: Ponto,
    eixos: Sequence[tuple[str, Ponto]],
    cor: str,
    comprimento: float = 70 * ESC,
) -> None:
    fonte = _fonte(13 * ESC)
    for nome, direcao in eixos:
        ponta = dg.mais(origem, direcao, comprimento)
        dg.seta(d, origem, ponta, cor, largura=3 * ESC, ponta_px=12 * ESC)
        dg.rotulo(d, ponta, direcao, 6 * ESC, nome, cor, fonte)
    d.ellipse([origem[0] - 3 * ESC, origem[1] - 3 * ESC, origem[0] + 3 * ESC,
               origem[1] + 3 * ESC], fill=cor)  # fmt: skip


def _texto(
    d: ImageDraw.ImageDraw, x: float, y: float, linhas: Sequence[tuple[str, str]], tamanho: int = 11
) -> None:
    fonte = _fonte(tamanho * ESC)
    for k, (texto, cor) in enumerate(linhas):
        d.text((x * ESC, (y + k * (tamanho + 6)) * ESC), texto, fill=cor, font=fonte)


#: A projeção oblíqua (cabinet) da figura padrão, px com y para baixo: X para a direita, Z para
#: cima (a frente sem distorção) e Y para o fundo, na diagonal (a planta com o Y "para cima").
_OBLIQUA = {
    "X": (1.0, 0.0),
    "Y": (0.5 * math.cos(math.radians(38)), -0.5 * math.sin(math.radians(38))),
    "Z": (0.0, -1.0),
}
_COR_MOMENTO = "#7c3aed"


def _proj(origem: Ponto, x: float, y: float, z: float, escala: float) -> Ponto:
    """O ponto (x, y, z) da fundação na tela da figura padrão (px)."""
    return (
        origem[0] + escala * (x * _OBLIQUA["X"][0] + y * _OBLIQUA["Y"][0] + z * _OBLIQUA["Z"][0]),
        origem[1] + escala * (x * _OBLIQUA["X"][1] + y * _OBLIQUA["Y"][1] + z * _OBLIQUA["Z"][1]),
    )


def _caixa(
    d: ImageDraw.ImageDraw,
    origem: Ponto,
    escala: float,
    minimo: tuple[float, float, float],
    maximo: tuple[float, float, float],
    cores: tuple[str, str, str],
) -> None:
    """Uma caixa em 3D: as faces que se veem (frente y mínimo, topo z máximo, lado x máximo)."""
    (x0, y0, z0), (x1, y1, z1) = minimo, maximo

    def p(x: float, y: float, z: float) -> Ponto:
        return _proj(origem, x, y, z, escala)

    frente = [p(x0, y0, z0), p(x1, y0, z0), p(x1, y0, z1), p(x0, y0, z1)]
    topo = [p(x0, y0, z1), p(x1, y0, z1), p(x1, y1, z1), p(x0, y1, z1)]
    lado = [p(x1, y0, z0), p(x1, y1, z0), p(x1, y1, z1), p(x1, y0, z1)]
    for face, cor in zip((frente, lado, topo), cores, strict=True):
        d.polygon(face, fill=cor, outline=_COR_ACO, width=ESC)


def _arco_de_momento(
    d: ImageDraw.ImageDraw,
    origem: Ponto,
    escala: float,
    eixo: str,
    centro_no_eixo: float,
    raio: float,
    cor: str,
) -> Ponto:
    """O momento positivo em torno do eixo, pela regra da mão direita: 3/4 de volta num círculo
    em volta do eixo, com a ponta da seta no sentido do giro. Devolve o ponto do rótulo (px)."""
    indice = "XYZ".index(eixo)
    # u × v = o eixo (X: Y→Z; Y: Z→X; Z: X→Y) — girar de u para v é o sentido positivo
    u_i, v_i = (indice + 1) % 3, (indice + 2) % 3

    def ponto(t: float) -> Ponto:
        c = [0.0, 0.0, 0.0]
        c[indice] = centro_no_eixo
        c[u_i] += raio * math.cos(t)
        c[v_i] += raio * math.sin(t)
        return _proj(origem, c[0], c[1], c[2], escala)

    inicio, fim = math.radians(-60), math.radians(210)
    passos = 40
    pontos = [ponto(inicio + (fim - inicio) * k / passos) for k in range(passos + 1)]
    d.line(pontos, fill=cor, width=3 * ESC, joint="curve")
    dg.seta(d, pontos[-3], pontos[-1], cor, largura=3 * ESC, ponta_px=13 * ESC)
    return ponto(math.radians(75))


def figura_dos_eixos(eixo_vertical: str = "Y", eixos: str = rb.EIXOS_FUNDACAO) -> ImagemDiagrama:
    """A figura padrão das reações nas bases: um sistema de eixos só (X e Y na planta, Z para
    cima) com os sentidos positivos das forças e dos momentos da tabela, desenhados no pé de um
    pilar, e a planta como ela aparece nos desenhos. Serve para ler a tabela, a planta de cada
    caso, o modelo 3D e o Excel. ``eixos`` fica por compatibilidade com registros antigos."""
    del eixos
    imagem = Image.new("RGB", (_LARGURA_PX * ESC, _ALTURA_PX * ESC), "#ffffff")
    d = ImageDraw.Draw(imagem)
    titulo = "Padrão de eixos das reações nas bases"
    d.text(_p(18, 14), titulo, fill=dg.COR_TEXTO, font=_fonte(18 * ESC))
    d.text(
        _p(18, 42),
        "Um sistema só para tudo: a tabela, a planta de cada caso, o modelo 3D e o Excel. "
        "Forças em kN, momentos em kN·m, coordenadas em m.",
        fill=dg.COR_COTA,
        font=_fonte(12 * ESC),
    )

    # ------------------------------------------------------------ 1. o pé com os sentidos +
    _quadro(d, (14, 72, 700, 866), "Sentidos POSITIVOS na tabela (ação da estrutura na fundação)")
    escala = 280 * ESC
    origem = _p(300, 480)
    # bloco de fundação (abaixo de z = 0), placa de base e o começo do pilar
    _caixa(d, origem, escala, (-0.55, -0.55, -0.55), (0.55, 0.55, -0.04),
           (_COR_CONCRETO, "#cbd5e1", "#f1f5f9"))  # fmt: skip
    _caixa(d, origem, escala, (-0.22, -0.22, -0.04), (0.22, 0.22, 0.0),
           ("#94a3b8", "#64748b", "#cbd5e1"))  # fmt: skip
    _caixa(d, origem, escala, (-0.07, -0.07, 0.0), (0.07, 0.07, 0.30),
           ("#e2e8f0", "#cbd5e1", "#f8fafc"))  # fmt: skip
    fonte = _fonte(15 * ESC)
    fonte_m = _fonte(14 * ESC)
    comprimento = 1.05
    for nome in "XYZ":
        direcao = [0.0, 0.0, 0.0]
        direcao["XYZ".index(nome)] = comprimento
        ponta = _proj(origem, direcao[0], direcao[1], direcao[2], escala)
        dg.seta(d, origem, ponta, _COR_ACAO, largura=4 * ESC, ponta_px=16 * ESC)
        tela = (ponta[0] - origem[0], ponta[1] - origem[1])
        dg.rotulo(d, ponta, tela, 8 * ESC, f"{nome}  ·  F{nome.lower()} +", _COR_ACAO, fonte)
        meio = _arco_de_momento(d, origem, escala, nome, 0.78 * comprimento, 0.15, _COR_MOMENTO)
        lado = {"X": (0.0, -1.0), "Y": (1.0, 0.4), "Z": (1.0, 0.0)}[nome]
        dg.rotulo(d, meio, lado, 12 * ESC, f"M{nome.lower()} +", _COR_MOMENTO, fonte_m, fundo=True)
    d.ellipse([origem[0] - 4 * ESC, origem[1] - 4 * ESC, origem[0] + 4 * ESC,
               origem[1] + 4 * ESC], fill=dg.COR_TEXTO)  # fmt: skip
    dg.rotulo(d, origem, (-1.0, 0.0), 80 * ESC, "origem: o pé\n(centro da placa)",
              dg.COR_COTA, _fonte(12 * ESC), fundo=True)  # fmt: skip
    _texto(
        d,
        34,
        760,
        [
            ("Setas vermelhas: força positiva no sentido do eixo.", _COR_ACAO),
            ("Setas curvas: momento positivo pela regra da mão direita", _COR_MOMENTO),
            ("(polegar no sentido do eixo, os dedos dão o giro).", _COR_MOMENTO),
            ("Valor negativo na tabela = sentido contrário ao desenhado.", dg.COR_TEXTO),
        ],
        12,
    )

    # ------------------------------------------------------------ 2. a planta dos desenhos
    _quadro(d, (714, 72, 1166, 330), "Nas plantas (vista de cima)")
    origem_p = _p(800, 285)
    fonte_p = _fonte(15 * ESC)
    for nome, direcao_planta in (("X", (1.0, 0.0)), ("Y", (0.0, -1.0))):
        ponta = dg.mais(origem_p, direcao_planta, 110 * ESC)
        dg.seta(d, origem_p, ponta, _COR_FUND, largura=4 * ESC, ponta_px=14 * ESC)
        dg.rotulo(d, ponta, direcao_planta, 8 * ESC, nome, _COR_FUND, fonte_p)
    simbolo_saindo(d, origem_p, 12 * ESC, _COR_FUND)
    dg.rotulo(d, origem_p, (-1.0, 1.0), 14 * ESC, "Z", _COR_FUND, fonte_p)
    simbolo_saindo(d, _p(942, 250), 10 * ESC, _COR_FUND)
    d.text(_p(958, 241), "= o eixo sai do papel", fill=dg.COR_COTA, font=_fonte(12 * ESC))
    _texto(
        d,
        930,
        150,
        [
            ("X para a direita", dg.COR_TEXTO),
            ("Y para cima (no papel)", dg.COR_TEXTO),
            ("Z sai do papel", dg.COR_TEXTO),
            ("(é para cima no espaço)", dg.COR_COTA),
        ],
        12,
    )

    # ------------------------------------------------------------ 3. como ler
    _quadro(d, (714, 344, 1166, 866), "Como ler")
    regras = [
        ("Fz < 0: empurra a fundação para baixo", dg.COR_TEXTO),
        ("= compressão. N = −Fz (positivo).", dg.COR_TEXTO),
        ("Fz > 0: puxa = arrancamento.", dg.COR_TEXTO),
        ("", dg.COR_TEXTO),
        ("H = √(Fx² + Fy²): a horizontal.", dg.COR_TEXTO),
        ("M horizontal = √(Mx² + My²).", dg.COR_TEXTO),
        ("Mz = torção no pé.", dg.COR_TEXTO),
        ("", dg.COR_TEXTO),
        ("Aba “Reação no apoio” = o que o", _COR_REACAO),
        ("SolidWorks mostra: mesmo valor,", _COR_REACAO),
        ("sinal trocado (R = −F).", _COR_REACAO),
    ]
    if eixo_vertical == "Y":
        regras += [
            ("", dg.COR_TEXTO),
            ("No SolidWorks (Y para cima):", _COR_SW),
            ("X = X do SW · Y = −Z do SW", _COR_SW),
            ("Z = Y do SW", _COR_SW),
        ]
    _texto(d, 734, 382, regras, 13)
    legenda = (
        "Padrão de eixos das reações nas bases: X e Y na planta, Z para cima; sentidos positivos "
        "das forças e dos momentos da tabela (ação da estrutura na fundação), regra da mão direita."
    )
    return figura_final(imagem, titulo, legenda)


def cena_do_projeto(
    geometria: ld.GeometriaDoModelo,
    r: rb.ReacoesNasBases,
    *,
    tipos: dict[str, str] | None = None,
) -> Any:
    """A cena 3D do projeto com o rótulo de cada pé (a do desenho e a do memorial); ``None`` sem
    o esqueleto ou sem a posição dos pés."""
    from core import cena_3d as c3
    from core import cena_do_modelo as cm

    pes = [pe for pe in r.pes if pe.ponto is not None]
    if not geometria.corpos or not pes:
        return None
    eixo = r.eixo_vertical if r.eixo_vertical in ("Y", "Z") else "Y"
    barras, legenda, _ = cm.barras_da_cena(geometria, eixo, tipos=tipos or {})
    degraus, paineis = cm.chapas_da_cena(geometria, eixo)
    apoios = []
    textos = []
    for pe in pes:
        ponto = vpb.para_a_planta(pe.ponto, eixo)  # type: ignore[arg-type]
        tipo = {"engastado": c3.APOIO_ENGASTE, "articulado": c3.APOIO_ARTICULADO}.get(
            pe.comportamento, c3.APOIO_DESCONHECIDO
        )
        apoios.append(c3.ApoioCena(ponto, tipo, "", "apoio"))
        textos.append(c3.TextoCena(ponto, pe.rotulo, _COR_FUND))
    return c3.Cena(
        barras=tuple(barras + degraus),
        paineis=tuple(paineis),
        apoios=tuple(apoios),
        textos=tuple(textos),
        titulo="O projeto e os pés",
        subtitulo=(
            f"{geometria.arquivo or 'esqueleto do modelo'} · {len(pes)} pés · eixos da fundação "
            "(X e Y na planta, Z para cima)"
        ),
        legenda=tuple(legenda),
        # o triedro com os eixos da fundação: a cena já está na planta (Z para cima)
        eixo_vertical_do_modelo="Z",
    )


def legenda_do_projeto(r: rb.ReacoesNasBases) -> str:
    pes = [pe for pe in r.pes if pe.ponto is not None]
    return (
        f"Modelo em 3D com os {len(pes)} pés ({', '.join(p.rotulo for p in pes[:12])}"
        + ("…" if len(pes) > 12 else "")
        + ") nos eixos da fundação: X e Y na planta, Z para cima."
    )


def figura_do_projeto(
    geometria: ld.GeometriaDoModelo,
    r: rb.ReacoesNasBases,
    *,
    tipos: dict[str, str] | None = None,
) -> ImagemDiagrama | None:
    """O modelo em 3D (isométrica) com o rótulo de cada pé e o triedro dos eixos da fundação;
    ``None`` sem o esqueleto ou sem a posição dos pés."""
    from io import BytesIO

    from core import cena_3d as c3
    from core import cena_3d_png

    cena = cena_do_projeto(geometria, r, tipos=tipos)
    if cena is None:
        return None
    azimute, elevacao = c3.VISTAS[c3.VISTA_ISOMETRICA]
    desenho = c3.projetar(cena, azimute=azimute, elevacao=elevacao, rotulos_maximos=40)
    imagem = Image.open(BytesIO(cena_3d_png.png_da_cena(desenho))).convert("RGB")
    return figura_final(imagem, "O projeto e os pés", legenda_do_projeto(r))


def png_para_o_excel(figura: ImagemDiagrama, largura_px: int = 1100) -> bytes:
    """O PNG da figura com a largura dada (px) para entrar numa aba do Excel."""
    from io import BytesIO

    imagem = Image.open(BytesIO(figura.png)).convert("RGB")
    if imagem.width > largura_px:
        altura = round(imagem.height * largura_px / imagem.width)
        imagem = imagem.resize((largura_px, altura), Image.Resampling.LANCZOS)
    saida = BytesIO()
    imagem.save(saida, format="PNG")
    return saida.getvalue()
