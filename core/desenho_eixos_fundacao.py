"""Figuras que vão junto das reações nas bases para quem projeta a fundação.

* :func:`figura_dos_eixos` — o sistema de coordenadas: os eixos do SolidWorks e os da fundação no
  mesmo desenho isométrico, a correspondência entre eles, a planta (Z saindo da tela, ⊙) e a vista
  de frente (Y entrando na tela, ⊗), e o pé de um pilar com a **ação** da estrutura na fundação (o
  que vai nas tabelas) e a **reação** da fundação na estrutura (o que o SolidWorks mostra).
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

#: As direções na tela do desenho isométrico (px, y para baixo), nos eixos do SolidWorks com o Y
#: para cima: X para a direita e para baixo, Z para a esquerda e para baixo, Y para cima.
_ISO = {
    "X": (math.cos(math.radians(30)), math.sin(math.radians(30))),
    "Y": (0.0, -1.0),
    "Z": (-math.cos(math.radians(30)), math.sin(math.radians(30))),
}


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


def _com_simbolo(d: ImageDraw.ImageDraw, x: float, y: float, simbolo: object, texto: str) -> None:
    """⊙ ou ⊗ desenhado (a fonte nem sempre tem o caractere) e o texto ao lado."""
    simbolo(d, _p(x + 7, y + 8), 6 * ESC, _COR_FUND)  # type: ignore[operator]
    d.text(_p(x + 20, y), texto, fill=dg.COR_COTA, font=_fonte(11 * ESC))


def _momento(
    d: ImageDraw.ImageDraw, centro: Ponto, raio: float, cor: str, *, anti_horario: bool
) -> None:
    """Seta curva de momento (3/4 de volta) em torno do centro, px, horária ou anti-horária na tela.

    O PIL mede o ângulo no sentido horário da tela (y para baixo): a tangente horária no ângulo a
    é (−sen a, cos a)."""
    cx, cy = centro
    inicio, fim = 150.0, 390.0  # por cima: da esquerda, passando no alto, até a direita
    d.arc([cx - raio, cy - raio, cx + raio, cy + raio], inicio, fim, fill=cor, width=3 * ESC)
    a = math.radians(inicio if anti_horario else fim)
    ponta = (cx + raio * math.cos(a), cy + raio * math.sin(a))
    tangente = (-math.sin(a), math.cos(a))
    if anti_horario:
        tangente = (-tangente[0], -tangente[1])
    dg.seta(d, dg.mais(ponta, tangente, -2 * ESC), dg.mais(ponta, tangente, 2 * ESC), cor,
            largura=3 * ESC, ponta_px=12 * ESC)  # fmt: skip


def figura_dos_eixos(eixo_vertical: str = "Y", eixos: str = rb.EIXOS_FUNDACAO) -> ImagemDiagrama:
    """O sistema de coordenadas das tabelas e a ação × a reação no pé de um pilar."""
    imagem = Image.new("RGB", (_LARGURA_PX * ESC, _ALTURA_PX * ESC), "#ffffff")
    d = ImageDraw.Draw(imagem)
    modelo_com_y = eixo_vertical == "Y"
    nas_tabelas = "do SolidWorks" if eixos == rb.EIXOS_MODELO and modelo_com_y else "da fundação"
    d.text(_p(18, 14), "Sistema de coordenadas das reações nas bases", fill=dg.COR_TEXTO,
           font=_fonte(17 * ESC))  # fmt: skip
    d.text(
        _p(18, 40),
        f"As tabelas e o Excel estão nos eixos {nas_tabelas}. Forças em kN, momentos em kN·m, "
        "coordenadas em m; momentos pela regra da mão direita (polegar no sentido do eixo).",
        fill=dg.COR_COTA,
        font=_fonte(11 * ESC),
    )

    # ------------------------------------------------------------ 1. os dois triedros
    _quadro(d, (14, 70, 590, 420), "1. Os eixos no espaço (vista isométrica)")
    if modelo_com_y:
        sw = [("X", _ISO["X"]), ("Y", _ISO["Y"]), ("Z", _ISO["Z"])]
        fund = [("X", _ISO["X"]), ("Y", (-_ISO["Z"][0], -_ISO["Z"][1])), ("Z", _ISO["Y"])]
    else:
        sw = [("X", _ISO["X"]), ("Y", (-_ISO["Z"][0], -_ISO["Z"][1])), ("Z", _ISO["Y"])]
        fund = sw
    _triedro(d, _p(150, 250), sw, _COR_SW)
    d.text(_p(70, 340), "SolidWorks (modelo)", fill=_COR_SW, font=_fonte(12 * ESC))
    _triedro(d, _p(420, 250), fund, _COR_FUND)
    d.text(_p(340, 340), "Fundação (tabelas e Excel)", fill=_COR_FUND, font=_fonte(12 * ESC))
    if modelo_com_y:
        correspondencia = [
            ("X da fundação = X do SolidWorks", dg.COR_TEXTO),
            ("Y da fundação = −Z do SolidWorks", dg.COR_TEXTO),
            ("Z da fundação = Y do SolidWorks (para cima)", dg.COR_TEXTO),
        ]
    else:
        correspondencia = [("O modelo já tem o Z para cima: os eixos são os mesmos.", dg.COR_TEXTO)]
    _texto(d, 34, 362, correspondencia, 11)

    # ------------------------------------------------------------ 2. planta e frente (2D)
    _quadro(d, (604, 70, 1166, 420), "2. Nas vistas 2D (planta e frente)")
    fonte = _fonte(13 * ESC)
    # planta: X para a direita, Y para cima, Z saindo da tela
    origem = _p(680, 290)
    for nome, direcao in (("X", (1.0, 0.0)), ("Y", (0.0, -1.0))):
        ponta = dg.mais(origem, direcao, 80 * ESC)
        dg.seta(d, origem, ponta, _COR_FUND, largura=3 * ESC, ponta_px=12 * ESC)
        dg.rotulo(d, ponta, direcao, 6 * ESC, nome, _COR_FUND, fonte)
    simbolo_saindo(d, origem, 10 * ESC, _COR_FUND)
    dg.rotulo(d, origem, (-1.0, 1.0), 12 * ESC, "Z", _COR_FUND, fonte)
    _texto(d, 630, 330, [("Planta (vista de cima)", dg.COR_TEXTO)], 11)
    _com_simbolo(d, 630, 354, simbolo_saindo, "Z sai da tela: para cima")
    # frente: X para a direita, Z para cima, Y entrando na tela
    origem = _p(930, 290)
    for nome, direcao in (("X", (1.0, 0.0)), ("Z", (0.0, -1.0))):
        ponta = dg.mais(origem, direcao, 80 * ESC)
        dg.seta(d, origem, ponta, _COR_FUND, largura=3 * ESC, ponta_px=12 * ESC)
        dg.rotulo(d, ponta, direcao, 6 * ESC, nome, _COR_FUND, fonte)
    simbolo_entrando(d, origem, 10 * ESC, _COR_FUND)
    dg.rotulo(d, origem, (-1.0, 1.0), 12 * ESC, "Y", _COR_FUND, fonte)
    _texto(d, 880, 330, [("Frente (olhando para +Y)", dg.COR_TEXTO)], 11)
    _com_simbolo(d, 880, 354, simbolo_entrando, "Y entra na tela: afasta-se")
    _com_simbolo(d, 630, 390, simbolo_saindo, "ponta da flecha vindo para você")
    _com_simbolo(d, 880, 390, simbolo_entrando, "cauda da flecha indo embora")

    # ------------------------------------------------------------ 3. ação × reação
    _quadro(d, (14, 434, 1166, 866), "3. Ação e reação no pé de um pilar (vista de frente, X × Z)")
    _pe_com_setas(d, 150, _COR_ACAO, acao=True)
    _pe_com_setas(d, 600, _COR_REACAO, acao=False)
    _texto(
        d,
        40,
        800,
        [
            ("AÇÃO da estrutura na fundação = o que vai nas tabelas e no Excel (carga para projetar "
             "a fundação).", _COR_ACAO),
            ("REAÇÃO da fundação na estrutura = o que o SolidWorks mostra no apoio. "
             "Reação = −Ação: o mesmo valor, sentido contrário.", _COR_REACAO),
            ("Fz < 0 na ação é para baixo: compressão (N = −Fz, positiva). Fz > 0 é arrancamento. "
             "Mz é a torção no pé.", dg.COR_COTA),
        ],
        11,
    )  # fmt: skip
    titulo = "Sistema de coordenadas das reações nas bases"
    legenda = (
        f"Eixos {nas_tabelas} usados nas tabelas: correspondência com o SolidWorks, ⊙ saindo e ⊗ "
        "entrando na tela, e a ação da estrutura na fundação × a reação da fundação na estrutura."
    )
    return figura_final(imagem, titulo, legenda)


def _pe_com_setas(d: ImageDraw.ImageDraw, x0: float, cor: str, *, acao: bool) -> None:
    """O pé do pilar sobre o bloco (vista de frente) com as forças positivas de quem age."""
    fonte = _fonte(12 * ESC)
    cx = x0 + 140
    topo_bloco = 640
    # bloco de fundação (concreto) e pilar (aço) com a placa de base
    d.rectangle([_p(cx - 110, topo_bloco), _p(cx + 110, topo_bloco + 90)], fill=_COR_CONCRETO,
                outline=_COR_ACO, width=2 * ESC)  # fmt: skip
    for k in range(-100, 110, 22):
        d.line([_p(cx + k, topo_bloco + 90), _p(cx + k + 18, topo_bloco + 72)], fill="#94a3b8",
               width=ESC)  # fmt: skip
    d.rectangle([_p(cx - 38, topo_bloco - 8), _p(cx + 38, topo_bloco)], fill=_COR_ACO)
    d.rectangle([_p(cx - 16, 525), _p(cx + 16, topo_bloco - 8)], fill="#cbd5e1", outline=_COR_ACO,
                width=2 * ESC)  # fmt: skip
    centro = _p(cx, topo_bloco - 50)
    titulo = (
        "AÇÃO: a estrutura empurra a fundação" if acao else "REAÇÃO: a fundação segura a estrutura"
    )
    d.text(_p(x0 + 10, 470), titulo, fill=cor, font=_fonte(13 * ESC))
    if acao:
        # compressão: para baixo, chegando no bloco; H no sentido +X; My
        dg.seta(d, _p(cx + 60, topo_bloco - 120), _p(cx + 60, topo_bloco - 10), cor,
                largura=4 * ESC, ponta_px=14 * ESC)  # fmt: skip
        dg.rotulo(d, _p(cx + 60, topo_bloco - 120), (1.0, 0.0), 6 * ESC,
                  "N (compressão)\nFz < 0", cor, fonte)  # fmt: skip
        dg.seta(d, _p(cx - 130, topo_bloco - 4), _p(cx - 40, topo_bloco - 4), cor,
                largura=4 * ESC, ponta_px=14 * ESC)  # fmt: skip
        dg.rotulo(d, _p(cx - 130, topo_bloco - 4), (-1.0, 0.0), 6 * ESC, "Fx > 0", cor, fonte)
        _momento(d, centro, 44 * ESC, cor, anti_horario=False)
        dg.rotulo(d, centro, (-1.0, -1.0), 50 * ESC, "My > 0", cor, fonte)
    else:
        dg.seta(d, _p(cx + 60, topo_bloco + 10), _p(cx + 60, topo_bloco - 100), cor,
                largura=4 * ESC, ponta_px=14 * ESC)  # fmt: skip
        dg.rotulo(d, _p(cx + 60, topo_bloco - 100), (1.0, 0.0), 6 * ESC,
                  "Reação vertical\n= −Fz da ação", cor, fonte)  # fmt: skip
        dg.seta(d, _p(cx - 40, topo_bloco - 4), _p(cx - 130, topo_bloco - 4), cor,
                largura=4 * ESC, ponta_px=14 * ESC)  # fmt: skip
        dg.rotulo(d, _p(cx - 130, topo_bloco - 4), (-1.0, 0.0), 6 * ESC, "−Fx", cor, fonte)
        _momento(d, centro, 44 * ESC, cor, anti_horario=True)
        dg.rotulo(d, centro, (-1.0, -1.0), 50 * ESC, "−My", cor, fonte)
    # o triedro da vista: X para a direita, Z para cima, Y entrando (⊗)
    origem = _p(x0 + 330, 760)
    for nome, direcao in (("X", (1.0, 0.0)), ("Z", (0.0, -1.0))):
        ponta = dg.mais(origem, direcao, 40 * ESC)
        dg.seta(d, origem, ponta, _COR_FUND, largura=2 * ESC, ponta_px=9 * ESC)
        dg.rotulo(d, ponta, direcao, 4 * ESC, nome, _COR_FUND, _fonte(11 * ESC))
    simbolo_entrando(d, origem, 7 * ESC, _COR_FUND)
    dg.rotulo(d, origem, (-1.0, 1.0), 9 * ESC, "Y", _COR_FUND, _fonte(11 * ESC))


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
