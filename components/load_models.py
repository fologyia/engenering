"""Catálogo dos modelos do Assistente de cargas.

Reúne num único lugar o que antes estava espalhado pela página: o rótulo do
modelo, a que grupo de peça ele pertence, o texto que explica quando usá-lo,
quais esforços ele aceita, quais componentes de tensão ele devolve, a fórmula
e o croqui da seção. A página monta a seleção e o cartão a partir daqui, de
modo que incluir um modelo novo é acrescentar uma entrada nesta tabela.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import streamlit as st


# Paleta alinhada ao tema em .streamlit/config.toml.
_CONTORNO = "#0B6E99"
_CORPO = "#DDF2FA"
_CARGA = "#B95C00"
_COTA = "#64748B"
_EIXO = "#94A3B8"

_LARGURA_VIEWBOX = 280
_ALTURA_VIEWBOX = 150


# --------------------------------------------------------------------------
# Primitivas de desenho
# --------------------------------------------------------------------------


def _seta(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    cor: str = _CARGA,
    largura: float = 2.0,
    cabeca: float = 7.0,
) -> str:
    """Segmento com ponta triangular, desenhado sem depender de ``marker``.

    Marcadores SVG precisam de ``id`` global; como vários croquis podem
    coexistir na mesma página, a ponta é um polígono comum.
    """
    angulo = math.atan2(y2 - y1, x2 - x1)
    base_x = x2 - cabeca * math.cos(angulo)
    base_y = y2 - cabeca * math.sin(angulo)
    esquerda = (
        base_x - 0.45 * cabeca * math.sin(angulo),
        base_y + 0.45 * cabeca * math.cos(angulo),
    )
    direita = (
        base_x + 0.45 * cabeca * math.sin(angulo),
        base_y - 0.45 * cabeca * math.cos(angulo),
    )
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{base_x:.1f}" '
        f'y2="{base_y:.1f}" stroke="{cor}" stroke-width="{largura}" '
        f'stroke-linecap="round"/>'
        f'<polygon points="{x2:.1f},{y2:.1f} {esquerda[0]:.1f},'
        f'{esquerda[1]:.1f} {direita[0]:.1f},{direita[1]:.1f}" fill="{cor}"/>'
    )


def _texto(
    x: float,
    y: float,
    conteudo: str,
    *,
    cor: str = _COTA,
    tamanho: float = 11.0,
    ancora: str = "middle",
    peso: str = "500",
    italico: bool = False,
) -> str:
    estilo = ' font-style="italic"' if italico else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" fill="{cor}" font-size="{tamanho}" '
        f'text-anchor="{ancora}" font-weight="{peso}"{estilo}>{conteudo}</text>'
    )


def _cota_vertical(x: float, y1: float, y2: float, rotulo: str) -> str:
    """Linha de cota com traços nas pontas e rótulo à direita."""
    return (
        f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{_COTA}" '
        f'stroke-width="1"/>'
        f'<line x1="{x - 4}" y1="{y1}" x2="{x + 4}" y2="{y1}" '
        f'stroke="{_COTA}" stroke-width="1"/>'
        f'<line x1="{x - 4}" y1="{y2}" x2="{x + 4}" y2="{y2}" '
        f'stroke="{_COTA}" stroke-width="1"/>'
        + _texto(x + 8, (y1 + y2) / 2 + 4, rotulo, ancora="start", italico=True)
    )


def _cota_horizontal(
    y: float, x1: float, x2: float, rotulo: str, *, acima: bool = False
) -> str:
    return (
        f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{_COTA}" '
        f'stroke-width="1"/>'
        f'<line x1="{x1}" y1="{y - 4}" x2="{x1}" y2="{y + 4}" '
        f'stroke="{_COTA}" stroke-width="1"/>'
        f'<line x1="{x2}" y1="{y - 4}" x2="{x2}" y2="{y + 4}" '
        f'stroke="{_COTA}" stroke-width="1"/>'
        + _texto(
            (x1 + x2) / 2, y - 6 if acima else y + 15, rotulo, italico=True
        )
    )


def _arco_torque(
    cx: float,
    cy: float,
    raio: float,
    rotulo: str,
    *,
    inicio: float = -2.4,
    fim: float = 0.9,
    cor: str = _CARGA,
) -> str:
    """Arco com ponta de seta, usado para torque e momento fletor."""
    x1 = cx + raio * math.cos(inicio)
    y1 = cy + raio * math.sin(inicio)
    x2 = cx + raio * math.cos(fim)
    y2 = cy + raio * math.sin(fim)
    grande = 1 if (fim - inicio) > math.pi else 0
    # A ponta segue a tangente do arco no ponto final.
    ponta_x = x2 + 0.1 * raio * -math.sin(fim)
    ponta_y = y2 + 0.1 * raio * math.cos(fim)
    return (
        f'<path d="M {x1:.1f},{y1:.1f} A {raio},{raio} 0 {grande} 1 '
        f'{x2:.1f},{y2:.1f}" fill="none" stroke="{cor}" stroke-width="2"/>'
        + _seta(x2, y2, ponta_x, ponta_y, cor=cor, cabeca=6.0)
        + _texto(cx, cy - raio - 6, rotulo, cor=cor, tamanho=12, peso="600")
    )


def _linha_eixo(x1: float, y1: float, x2: float, y2: float) -> str:
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{_EIXO}" '
        f'stroke-width="1" stroke-dasharray="5 4"/>'
    )


def _pecas(*elementos: str) -> str:
    return "".join(elementos)


def _retangulo(x: float, y: float, largura: float, altura: float) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{largura}" height="{altura}" '
        f'fill="{_CORPO}" stroke="{_CONTORNO}" stroke-width="2" rx="2"/>'
    )


def _ponto_avaliado(x: float, y: float, rotulo: str = "ponto") -> str:
    return (
        f'<circle cx="{x}" cy="{y}" r="4.5" fill="{_CARGA}"/>'
        f'<circle cx="{x}" cy="{y}" r="8" fill="none" stroke="{_CARGA}" '
        f'stroke-width="1.2" stroke-dasharray="3 3"/>'
        + _texto(x, y - 13, rotulo, cor=_CARGA, tamanho=10, peso="600")
    )


# --------------------------------------------------------------------------
# Croquis
# --------------------------------------------------------------------------


def _croqui_barra_axial() -> str:
    return _pecas(
        _linha_eixo(20, 75, 260, 75),
        _retangulo(75, 55, 130, 40),
        _seta(70, 75, 25, 75),
        _seta(210, 75, 255, 75),
        _texto(38, 66, "F", cor=_CARGA, tamanho=13, peso="700", italico=True),
        _texto(242, 66, "F", cor=_CARGA, tamanho=13, peso="700", italico=True),
        _texto(140, 79, "A", cor=_CONTORNO, tamanho=13, italico=True),
        _texto(140, 120, "tração (+) ou compressão (−)"),
    )


def _croqui_barra_excentrica() -> str:
    centro_x, centro_y = 140.0, 78.0
    ponto_x, ponto_y = centro_x + 22, centro_y - 26
    return _pecas(
        _retangulo(95, 38, 90, 80),
        _linha_eixo(85, centro_y, 195, centro_y),
        _linha_eixo(centro_x, 28, centro_x, 128),
        f'<circle cx="{ponto_x}" cy="{ponto_y}" r="6" fill="none" '
        f'stroke="{_CARGA}" stroke-width="2"/>'
        f'<line x1="{ponto_x - 4}" y1="{ponto_y - 4}" x2="{ponto_x + 4}" '
        f'y2="{ponto_y + 4}" stroke="{_CARGA}" stroke-width="2"/>'
        f'<line x1="{ponto_x - 4}" y1="{ponto_y + 4}" x2="{ponto_x + 4}" '
        f'y2="{ponto_y - 4}" stroke="{_CARGA}" stroke-width="2"/>',
        _texto(
            ponto_x + 12, ponto_y - 6, "F", cor=_CARGA, tamanho=13,
            ancora="start", peso="700", italico=True,
        ),
        f'<line x1="{centro_x}" y1="{centro_y}" x2="{centro_x}" '
        f'y2="{ponto_y}" stroke="{_CARGA}" stroke-width="1.2" '
        f'stroke-dasharray="3 3"/>'
        f'<line x1="{centro_x}" y1="{ponto_y}" x2="{ponto_x}" '
        f'y2="{ponto_y}" stroke="{_CARGA}" stroke-width="1.2" '
        f'stroke-dasharray="3 3"/>',
        _texto(centro_x - 6, centro_y - 12, "e", cor=_CARGA, ancora="end",
               italico=True),
        _texto(centro_x + 11, ponto_y - 6, "e", cor=_CARGA, italico=True),
        _cota_horizontal(128, 95, 185, "b"),
        _cota_vertical(193, 38, 118, "h"),
    )


def _croqui_eixo_macico() -> str:
    return _pecas(
        _linha_eixo(20, 78, 222, 78),
        f'<rect x="70" y="58" width="140" height="40" fill="{_CORPO}" '
        f'stroke="{_CONTORNO}" stroke-width="2"/>',
        f'<ellipse cx="210" cy="78" rx="11" ry="20" fill="{_CORPO}" '
        f'stroke="{_CONTORNO}" stroke-width="2"/>',
        f'<ellipse cx="70" cy="78" rx="11" ry="20" fill="#C7E6F4" '
        f'stroke="{_CONTORNO}" stroke-width="2"/>',
        _seta(64, 78, 26, 78),
        _texto(38, 69, "F", cor=_CARGA, tamanho=13, peso="700", italico=True),
        _arco_torque(140, 78, 34, "T"),
        _texto(140, 133, "M aplicado na mesma seção", cor=_CARGA, tamanho=10),
        _cota_vertical(232, 58, 98, "d"),
    )


def _croqui_eixo_vazado() -> str:
    return _pecas(
        _linha_eixo(20, 78, 222, 78),
        f'<rect x="70" y="58" width="140" height="40" fill="{_CORPO}" '
        f'stroke="{_CONTORNO}" stroke-width="2"/>',
        f'<line x1="70" y1="68" x2="210" y2="68" stroke="{_CONTORNO}" '
        f'stroke-width="1" stroke-dasharray="4 3"/>'
        f'<line x1="70" y1="88" x2="210" y2="88" stroke="{_CONTORNO}" '
        f'stroke-width="1" stroke-dasharray="4 3"/>',
        f'<ellipse cx="210" cy="78" rx="11" ry="20" fill="{_CORPO}" '
        f'stroke="{_CONTORNO}" stroke-width="2"/>',
        f'<ellipse cx="210" cy="78" rx="5.5" ry="10" fill="#FFFFFF" '
        f'stroke="{_CONTORNO}" stroke-width="1.5"/>',
        _seta(64, 78, 26, 78),
        _texto(38, 69, "F", cor=_CARGA, tamanho=13, peso="700", italico=True),
        _arco_torque(140, 78, 34, "T"),
        _cota_vertical(232, 58, 98, "De"),
        _seta(232, 120, 213, 84, cor=_COTA, largura=1.2, cabeca=5),
        _texto(236, 126, "Di", ancora="start", italico=True),
    )


def _croqui_mola() -> str:
    espiras = []
    topo, passo = 46.0, 13.0
    for indice in range(5):
        y = topo + indice * passo
        espiras.append(
            f'<path d="M 108,{y:.0f} A 32,9 0 0 0 172,{y + passo / 2:.0f}" '
            f'fill="none" stroke="{_CONTORNO}" stroke-width="4" '
            f'stroke-linecap="round"/>'
            f'<path d="M 172,{y + passo / 2:.0f} A 32,9 0 0 0 '
            f'108,{y + passo:.0f}" fill="none" stroke="{_CONTORNO}" '
            f'stroke-width="1.6" stroke-dasharray="4 3"/>'
        )
    return _pecas(
        _linha_eixo(140, 26, 140, 132),
        "".join(espiras),
        _seta(140, 26, 140, 44),
        _seta(140, 130, 140, 112),
        _texto(148, 34, "F", cor=_CARGA, tamanho=13, ancora="start",
               peso="700", italico=True),
        _texto(148, 128, "F", cor=_CARGA, tamanho=13, ancora="start",
               peso="700", italico=True),
        _cota_horizontal(144, 108, 172, "D/2", acima=True),
        _texto(96, 90, "d", cor=_COTA, ancora="end", italico=True),
        _seta(100, 87, 108, 84, cor=_COTA, largura=1.2, cabeca=5),
    )


def _croqui_viga_retangular() -> str:
    return _pecas(
        _retangulo(100, 30, 80, 90),
        _linha_eixo(100, 75, 190, 75),
        _texto(96, 79, "y=0", cor=_EIXO, tamanho=9, ancora="end"),
        _ponto_avaliado(140, 46, "y"),
        _arco_torque(62, 75, 24, "M"),
        _seta(228, 52, 228, 100),
        _texto(236, 80, "V", cor=_CARGA, tamanho=13, ancora="start",
               peso="700", italico=True),
        _cota_horizontal(130, 100, 180, "b"),
        _cota_vertical(190, 30, 120, "h"),
    )


def _croqui_biaxial() -> str:
    return _pecas(
        _retangulo(98, 34, 84, 80),
        _linha_eixo(88, 74, 192, 74),
        _linha_eixo(140, 24, 140, 124),
        _seta(140, 74, 140, 28, cor=_EIXO, largura=1.2, cabeca=6),
        _seta(140, 74, 190, 74, cor=_EIXO, largura=1.2, cabeca=6),
        _texto(132, 32, "y", cor=_COTA, ancora="end", italico=True),
        _texto(186, 68, "z", cor=_COTA, italico=True),
        _ponto_avaliado(174, 42, "(y, z)"),
        _arco_torque(52, 74, 22, "Mz"),
        _arco_torque(228, 74, 22, "My"),
    )


def _croqui_secao_i() -> str:
    perfil = (
        "M 95,28 L 185,28 L 185,42 L 148,42 L 148,106 L 185,106 L 185,120 "
        "L 95,120 L 95,106 L 132,106 L 132,42 L 95,42 Z"
    )
    return _pecas(
        f'<path d="{perfil}" fill="{_CORPO}" stroke="{_CONTORNO}" '
        f'stroke-width="2" stroke-linejoin="round"/>',
        _linha_eixo(85, 74, 195, 74),
        _ponto_avaliado(140, 35, "y"),
        _arco_torque(52, 74, 22, "M"),
        _seta(232, 50, 232, 100),
        _texto(240, 78, "V", cor=_CARGA, tamanho=13, ancora="start",
               peso="700", italico=True),
        _cota_horizontal(130, 95, 185, "b"),
        _cota_vertical(196, 28, 120, "h"),
        _texto(88, 38, "tf", cor=_COTA, ancora="end", tamanho=10,
               italico=True),
        _seta(166, 98, 150, 90, cor=_COTA, largura=1.2, cabeca=5),
        _texto(169, 101, "tw", cor=_COTA, tamanho=10, ancora="start",
               italico=True),
    )


def _croqui_tubular_retangular() -> str:
    return _pecas(
        _retangulo(96, 34, 88, 80),
        f'<rect x="106" y="44" width="68" height="60" fill="#FFFFFF" '
        f'stroke="{_CONTORNO}" stroke-width="1.6"/>',
        _linha_eixo(86, 74, 194, 74),
        _ponto_avaliado(118, 39, "y"),
        _arco_torque(140, 78, 22, "T"),
        _cota_horizontal(126, 96, 106, "t"),
        _cota_vertical(192, 34, 114, "h"),
        _cota_horizontal(128, 96, 184, "b"),
    )


def _croqui_pino() -> str:
    return _pecas(
        f'<rect x="40" y="52" width="132" height="22" fill="{_CORPO}" '
        f'stroke="{_CONTORNO}" stroke-width="2"/>',
        f'<rect x="108" y="74" width="132" height="22" fill="#C7E6F4" '
        f'stroke="{_CONTORNO}" stroke-width="2"/>',
        f'<rect x="132" y="42" width="16" height="64" rx="3" fill="#FDE7CF" '
        f'stroke="{_CARGA}" stroke-width="2"/>',
        f'<line x1="96" y1="74" x2="184" y2="74" stroke="{_CARGA}" '
        f'stroke-width="1.5" stroke-dasharray="4 3"/>',
        _seta(66, 116, 98, 79, cor=_CARGA, largura=1.2, cabeca=5),
        _texto(24, 126, "plano de corte", cor=_CARGA, tamanho=10,
               ancora="start"),
        _seta(44, 63, 20, 63),
        _seta(236, 85, 260, 85),
        _texto(30, 54, "F", cor=_CARGA, tamanho=13, peso="700", italico=True),
        _texto(250, 77, "F", cor=_CARGA, tamanho=13, peso="700",
               italico=True),
        _cota_horizontal(120, 132, 148, "d"),
    )


def _croqui_cilindro_fino() -> str:
    pressao = "".join(
        _seta(140, 78, 140 + 26 * math.cos(a), 78 + 26 * math.sin(a),
              cor=_CARGA, largura=1.4, cabeca=5)
        for a in (0.0, 1.05, 2.1, 3.14, 4.19, 5.24)
    )
    return _pecas(
        f'<rect x="70" y="48" width="140" height="60" fill="{_CORPO}" '
        f'stroke="{_CONTORNO}" stroke-width="2"/>',
        f'<ellipse cx="210" cy="78" rx="13" ry="30" fill="{_CORPO}" '
        f'stroke="{_CONTORNO}" stroke-width="2"/>',
        f'<ellipse cx="70" cy="78" rx="13" ry="30" fill="none" '
        f'stroke="{_CONTORNO}" stroke-width="1.4" stroke-dasharray="4 3"/>',
        pressao,
        _texto(140, 74, "p", cor=_CARGA, tamanho=12, peso="700",
               italico=True),
        _texto(105, 40, "σθ (circunferencial)", cor=_CONTORNO, tamanho=10,
               ancora="start"),
        _seta(96, 108, 96, 122, cor=_CONTORNO, largura=1.4, cabeca=5),
        _texto(102, 126, "σlong", cor=_CONTORNO, tamanho=10, ancora="start"),
        _cota_vertical(232, 48, 108, "D"),
        _texto(258, 60, "t", cor=_COTA, italico=True),
    )


def _croqui_esfera() -> str:
    pressao = "".join(
        _seta(140, 76, 140 + 34 * math.cos(a), 76 + 34 * math.sin(a),
              cor=_CARGA, largura=1.4, cabeca=5)
        for a in (0.0, 0.9, 1.8, 2.7, 3.6, 4.5, 5.4)
    )
    return _pecas(
        f'<circle cx="140" cy="76" r="50" fill="{_CORPO}" '
        f'stroke="{_CONTORNO}" stroke-width="2"/>',
        f'<circle cx="140" cy="76" r="44" fill="#FFFFFF" '
        f'stroke="{_CONTORNO}" stroke-width="1.4"/>',
        pressao,
        _texto(140, 72, "p", cor=_CARGA, tamanho=12, peso="700",
               italico=True),
        _cota_horizontal(136, 90, 190, "D/2"),
        _seta(226, 24, 180, 47, cor=_COTA, largura=1.2, cabeca=5),
        _texto(230, 22, "t", ancora="start", italico=True),
    )


def _croqui_parede_espessa() -> str:
    interna = "".join(
        _seta(140, 76, 140 + 26 * math.cos(a), 76 + 26 * math.sin(a),
              cor=_CARGA, largura=1.4, cabeca=5)
        for a in (0.79, 2.36, 3.93, 5.50)
    )
    externa = "".join(
        _seta(140 + 66 * math.cos(a), 76 + 66 * math.sin(a),
              140 + 54 * math.cos(a), 76 + 54 * math.sin(a),
              cor=_CONTORNO, largura=1.4, cabeca=5)
        for a in (0.78, 2.36, 3.93, 5.5)
    )
    return _pecas(
        f'<circle cx="140" cy="76" r="52" fill="{_CORPO}" '
        f'stroke="{_CONTORNO}" stroke-width="2"/>',
        f'<circle cx="140" cy="76" r="26" fill="#FFFFFF" '
        f'stroke="{_CONTORNO}" stroke-width="2"/>',
        interna,
        externa,
        _texto(140, 98, "pi", cor=_CARGA, tamanho=11, peso="700",
               italico=True),
        _texto(214, 30, "pe", cor=_CONTORNO, tamanho=11, peso="700",
               italico=True),
        _cota_vertical(172, 50, 76, "ri"),
        _cota_vertical(200, 24, 76, "re"),
        _texto(140, 144, "σr não é desprezível na parede espessa",
               tamanho=10),
    )


def _croqui_perfil_u() -> str:
    perfil = (
        "M 96,30 L 176,30 L 176,42 L 108,42 L 108,108 L 176,108 L 176,120 "
        "L 96,120 Z"
    )
    return _pecas(
        f'<path d="{perfil}" fill="{_CORPO}" stroke="{_CONTORNO}" '
        f'stroke-width="2" stroke-linejoin="round"/>',
        _linha_eixo(60, 75, 186, 75),
        _ponto_avaliado(140, 36, "y"),
        # O centro de cisalhamento fora da alma é a particularidade do U.
        f'<circle cx="60" cy="75" r="6" fill="none" stroke="{_CARGA}" '
        f'stroke-width="1.8"/>'
        f'<line x1="56" y1="71" x2="64" y2="79" stroke="{_CARGA}" '
        f'stroke-width="1.8"/>'
        f'<line x1="56" y1="79" x2="64" y2="71" stroke="{_CARGA}" '
        f'stroke-width="1.8"/>',
        _texto(60, 97, "centro de", cor=_CARGA, tamanho=9, peso="600"),
        _texto(60, 108, "cisalhamento", cor=_CARGA, tamanho=9, peso="600"),
        _cota_horizontal(132, 60, 102, "e"),
        _seta(232, 50, 232, 100),
        _texto(240, 78, "V", cor=_CARGA, tamanho=13, ancora="start",
               peso="700", italico=True),
        _cota_vertical(188, 30, 120, "h"),
        _cota_horizontal(126, 96, 176, "bf"),
        _texto(90, 40, "tf", cor=_COTA, ancora="end", tamanho=10,
               italico=True),
        _seta(86, 62, 100, 70, cor=_COTA, largura=1.2, cabeca=5),
        _texto(82, 59, "tw", cor=_COTA, ancora="end", tamanho=10,
               italico=True),
    )


def _croqui_cantoneira() -> str:
    perfil = "M 108,26 L 122,26 L 122,102 L 198,102 L 198,116 L 108,116 Z"
    centro_x, centro_y = 134.0, 90.0
    return _pecas(
        f'<path d="{perfil}" fill="{_CORPO}" stroke="{_CONTORNO}" '
        f'stroke-width="2" stroke-linejoin="round"/>',
        _linha_eixo(96, centro_y, 212, centro_y),
        _linha_eixo(centro_x, 20, centro_x, 130),
        _texto(216, centro_y + 4, "z", ancora="start", italico=True),
        _texto(centro_x, 16, "y", italico=True),
        # Eixo principal a 45°: a linha neutra não acompanha z.
        f'<line x1="90" y1="134" x2="180" y2="44" stroke="{_CARGA}" '
        f'stroke-width="1.5" stroke-dasharray="6 4"/>',
        _texto(184, 48, "eixo principal", cor=_CARGA, tamanho=9,
               ancora="start", peso="600"),
        _texto(184, 59, "a 45°", cor=_CARGA, tamanho=9, ancora="start",
               peso="600"),
        f'<circle cx="{centro_x}" cy="{centro_y}" r="3.5" '
        f'fill="{_CONTORNO}"/>',
        _cota_horizontal(128, 108, 198, "b (as duas abas)"),
        _texto(104, 22, "t", ancora="end", tamanho=10, italico=True),
    )


# --------------------------------------------------------------------------
# Catálogo
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ModeloCarga:
    """Tudo o que a página precisa saber sobre um modelo de conversão."""

    chave: str
    grupo: str
    resumo: str
    descricao: str
    entradas: tuple[str, ...]
    saidas: tuple[str, ...]
    formula: str
    croqui: str


GRUPO_BARRAS = "Barras e tirantes"
GRUPO_EIXOS = "Eixos e molas"
GRUPO_VIGAS = "Vigas de seção cheia"
GRUPO_PERFIS = "Perfis estruturais"
GRUPO_LIGACOES = "Pinos e parafusos"
GRUPO_PRESSAO = "Vasos e tubos sob pressão"

ORDEM_GRUPOS = (
    GRUPO_BARRAS,
    GRUPO_EIXOS,
    GRUPO_VIGAS,
    GRUPO_PERFIS,
    GRUPO_LIGACOES,
    GRUPO_PRESSAO,
)

ICONES_GRUPO = {
    GRUPO_BARRAS: ":material/straighten:",
    GRUPO_EIXOS: ":material/settings:",
    GRUPO_VIGAS: ":material/view_week:",
    GRUPO_PERFIS: ":material/domain:",
    GRUPO_LIGACOES: ":material/hardware:",
    GRUPO_PRESSAO: ":material/propane_tank:",
}

MODELO_SECAO_I = "Seção I sob força axial, flexão e cortante"

# Rótulos usados antes desta revisão continuam válidos como entrada.
ALIASES = {
    "Seção I sob força axial e flexão": MODELO_SECAO_I,
}

_MODELOS = (
    ModeloCarga(
        chave="Barra sob carga axial",
        grupo=GRUPO_BARRAS,
        resumo="Puxada ou empurrada no sentido do comprimento, carga no centro.",
        descricao=(
            "Uma peça reta sendo puxada (tração) ou empurrada (compressão) "
            "no sentido do seu comprimento — como um tirante ou uma coluna "
            "curta. A tensão é a mesma em toda a seção."
        ),
        entradas=("F", "A"),
        saidas=("σx",),
        formula=r"\sigma_x=\frac{F}{A}",
        croqui=_croqui_barra_axial(),
    ),
    ModeloCarga(
        chave="Barra sob carga axial excêntrica",
        grupo=GRUPO_BARRAS,
        resumo="Carga axial aplicada fora do centro: comprime de um lado, "
        "traciona do outro.",
        descricao=(
            "A mesma barra, mas com a força deslocada do centroide — o caso "
            "de um pilar carregado na borda ou de um tirante com chapa "
            "desalinhada. A excentricidade cria flexão junto com o esforço "
            "axial e pode inverter o sinal da tensão em um dos lados."
        ),
        entradas=("F", "e", "b", "h"),
        saidas=("σx",),
        formula=(
            r"\sigma_x=\frac{F}{A}\left(1+\frac{12\,e_y\,y}{h^2}"
            r"+\frac{12\,e_z\,z}{b^2}\right)"
        ),
        croqui=_croqui_barra_excentrica(),
    ),
    ModeloCarga(
        chave="Eixo circular maciço",
        grupo=GRUPO_EIXOS,
        resumo="Eixo redondo cheio sob força axial, flexão e torção juntas.",
        descricao=(
            "Um eixo redondo e cheio (sem furo no meio) que pode estar sendo "
            "puxado/empurrado, dobrado e torcido ao mesmo tempo. O resultado "
            "é avaliado na superfície, onde a torção é máxima."
        ),
        entradas=("F", "M", "T", "d"),
        saidas=("σx", "τxy"),
        formula=(
            r"\sigma_x=\frac{F}{A}\pm\frac{32M}{\pi d^3},"
            r"\qquad \tau_{xy}=\frac{16T}{\pi d^3}"
        ),
        croqui=_croqui_eixo_macico(),
    ),
    ModeloCarga(
        chave="Eixo circular vazado",
        grupo=GRUPO_EIXOS,
        resumo="Tubo redondo sob os mesmos esforços do eixo maciço.",
        descricao=(
            "Um tubo — eixo redondo oco — sob os mesmos tipos de esforço do "
            "eixo maciço. Costuma render mais rigidez por quilo, já que o "
            "material fica longe do centro."
        ),
        entradas=("F", "M", "T", "De", "Di"),
        saidas=("σx", "τxy"),
        formula=(
            r"\sigma_x=\frac{F}{A}\pm\frac{M(D_e/2)}{I},"
            r"\qquad \tau_{xy}=\frac{T(D_e/2)}{J}"
        ),
        croqui=_croqui_eixo_vazado(),
    ),
    ModeloCarga(
        chave="Mola helicoidal de compressão",
        grupo=GRUPO_EIXOS,
        resumo="Fio enrolado em espiras: a carga vira torção no fio.",
        descricao=(
            "Uma mola helicoidal de espiras circulares. A força axial da mola "
            "chega ao fio como torção, e o ponto mais solicitado é a fibra "
            "interna da espira — por isso o fator de Wahl, que corrige a "
            "curvatura e o cisalhamento direto."
        ),
        entradas=("F", "D", "d"),
        saidas=("τxy",),
        formula=r"\tau=K_w\,\frac{8FD}{\pi d^3},\qquad K_w=f(C),\ C=D/d",
        croqui=_croqui_mola(),
    ),
    ModeloCarga(
        chave="Viga de seção retangular",
        grupo=GRUPO_VIGAS,
        resumo="Viga retangular que dobra e sofre corte transversal.",
        descricao=(
            "Uma viga retangular (como uma régua de canto) que dobra e também "
            "sofre corte transversal. A flexão é máxima nas fibras extremas e "
            "o cisalhamento é máximo no centroide — escolha o ponto conforme "
            "o que você quer verificar."
        ),
        entradas=("F", "M", "V", "b", "h"),
        saidas=("σx", "τxy"),
        formula=(
            r"\sigma_x=\frac{F}{A}-\frac{My}{I},\qquad "
            r"\tau_{xy}=\frac{3V}{2A}"
            r"\left[1-\left(\frac{2y}{h}\right)^2\right]"
        ),
        croqui=_croqui_viga_retangular(),
    ),
    ModeloCarga(
        chave="Seção retangular com flexão biaxial",
        grupo=GRUPO_VIGAS,
        resumo="Barra retangular que dobra nas duas direções ao mesmo tempo.",
        descricao=(
            "Uma barra retangular que dobra em duas direções ao mesmo tempo, "
            "não só em uma. A tensão crítica cai em um dos cantos da seção, "
            "onde as duas flexões se somam."
        ),
        entradas=("F", "My", "Mz", "b", "h"),
        saidas=("σx",),
        formula=(
            r"\sigma_x=\frac{F}{A}+\frac{M_y z}{I_y}"
            r"-\frac{M_z y}{I_z}"
        ),
        croqui=_croqui_biaxial(),
    ),
    ModeloCarga(
        chave=MODELO_SECAO_I,
        grupo=GRUPO_PERFIS,
        resumo="Perfil I: flexão nas mesas e cisalhamento na alma.",
        descricao=(
            "Uma viga com seção em forma de 'I', muito comum em estruturas "
            "metálicas. As mesas absorvem a flexão e a alma absorve o "
            "cortante, por isso o cisalhamento é calculado com o momento "
            "estático do ponto escolhido."
        ),
        entradas=("F", "M", "V", "h", "b", "tf", "tw"),
        saidas=("σx", "τxy"),
        formula=(
            r"\sigma_x=\frac{F}{A}-\frac{My}{I},\qquad "
            r"\tau_{xy}=\frac{VQ}{I\,t}"
        ),
        croqui=_croqui_secao_i(),
    ),
    ModeloCarga(
        chave="Perfil U sob força axial, flexão e cortante",
        grupo=GRUPO_PERFIS,
        resumo="Canal laminado: como o I, mas com o centro de cisalhamento "
        "fora da alma.",
        descricao=(
            "O perfil U (canal, canaleta) fletido no eixo forte — o de "
            "simetria. As contas de flexão e de cortante são as mesmas do "
            "perfil I, mas o centro de cisalhamento fica fora da alma: um "
            "cortante aplicado no centroide também torce a peça."
        ),
        entradas=("F", "M", "V", "h", "bf", "tf", "tw"),
        saidas=("σx", "τxy"),
        formula=(
            r"\sigma_x=\frac{F}{A}-\frac{My}{I},\qquad "
            r"\tau_{xy}=\frac{VQ}{I\,t}"
        ),
        croqui=_croqui_perfil_u(),
    ),
    ModeloCarga(
        chave="Cantoneira de abas iguais",
        grupo=GRUPO_PERFIS,
        resumo="Perfil L: os eixos das abas não são principais, então a "
        "flexão sai oblíqua.",
        descricao=(
            "Uma cantoneira (perfil L) de abas iguais. É o caso em que a "
            "fórmula σ = My/I sozinha engana: como o produto de inércia nos "
            "eixos das abas não é nulo, um momento aplicado em torno de uma "
            "aba inclina a linha neutra e a peça flexiona fora do plano de "
            "carregamento."
        ),
        entradas=("F", "My", "Mz", "b", "t"),
        saidas=("σx",),
        formula=(
            r"\sigma_x=\frac{F}{A}+\frac{(M_yI_z+M_zI_{yz})z"
            r"-(M_yI_{yz}+M_zI_y)y}{I_yI_z-I_{yz}^2}"
        ),
        croqui=_croqui_cantoneira(),
    ),
    ModeloCarga(
        chave="Perfil tubular retangular (caixão)",
        grupo=GRUPO_PERFIS,
        resumo="Tubo retangular fechado: flexão mais torção pela fórmula "
        "de Bredt.",
        descricao=(
            "Um perfil tubular retangular de parede fina — o tubo quadrado ou "
            "retangular usado em chassis, pórticos e estruturas soldadas. "
            "Sendo uma seção fechada, resiste bem à torção, calculada pelo "
            "fluxo de cisalhamento de Bredt."
        ),
        entradas=("F", "M", "T", "b", "h", "t"),
        saidas=("σx", "τxy"),
        formula=(
            r"\sigma_x=\frac{F}{A}-\frac{My}{I},\qquad "
            r"\tau=\frac{T}{2A_m t}"
        ),
        croqui=_croqui_tubular_retangular(),
    ),
    ModeloCarga(
        chave="Pinos ou parafusos sob cisalhamento",
        grupo=GRUPO_LIGACOES,
        resumo="Pino cortado transversalmente pela força, em um ou dois "
        "planos.",
        descricao=(
            "Um pino ou parafuso sendo cortado transversalmente pela força, "
            "como uma tesoura corta um papel. O modelo divide a carga "
            "igualmente entre os pinos e os planos de corte e devolve a "
            "tensão média na seção."
        ),
        entradas=("F", "d", "nº de pinos", "planos"),
        saidas=("τxy",),
        formula=r"\tau_{média}=\frac{F}{n_p\,n_c\,(\pi d^2/4)}",
        croqui=_croqui_pino(),
    ),
    ModeloCarga(
        chave="Vaso cilíndrico de parede fina",
        grupo=GRUPO_PRESSAO,
        resumo="Tubo ou vaso pressurizado com D/t ≥ 20, mais axial e torque.",
        descricao=(
            "Um tubo ou vaso de pressão com parede fina, como um cilindro de "
            "gás ou uma tubulação pressurizada. Aceita ainda força axial e "
            "torque externos somados à pressão. Vale enquanto D/t ≥ 20."
        ),
        entradas=("p", "D", "t", "F", "T"),
        saidas=("σx", "σy", "τxy"),
        formula=(
            r"\sigma_\theta=\frac{pD}{2t},\quad "
            r"\sigma_{long}=\frac{pD}{4t}+\frac{F}{\pi Dt},\quad "
            r"\tau=\frac{2T}{\pi D^2t}"
        ),
        croqui=_croqui_cilindro_fino(),
    ),
    ModeloCarga(
        chave="Vaso esférico de parede fina",
        grupo=GRUPO_PRESSAO,
        resumo="Tanque esférico pressurizado: mesma tensão nas duas direções.",
        descricao=(
            "Um vaso esférico de parede fina, como um tanque redondo "
            "pressurizado. Por simetria, as duas tensões de membrana são "
            "iguais e valem metade da circunferencial de um cilindro de "
            "mesmo diâmetro."
        ),
        entradas=("p", "D", "t"),
        saidas=("σx", "σy"),
        formula=r"\sigma_x=\sigma_y=\frac{pD}{4t}",
        croqui=_croqui_esfera(),
    ),
    ModeloCarga(
        chave="Cilindro de parede espessa",
        grupo=GRUPO_PRESSAO,
        resumo="Solução de Lamé para D/t < 20, quando σr deixa de ser "
        "desprezível.",
        descricao=(
            "O modelo a usar quando a parede é grossa demais para a hipótese "
            "de membrana (D/t abaixo de 20): tubos de alta pressão, blocos "
            "hidráulicos, camisas de cilindro. A tensão varia ao longo da "
            "espessura e a radial deixa de ser desprezível."
        ),
        entradas=("pi", "pe", "ri", "re", "r"),
        saidas=("σx", "σy"),
        formula=(
            r"\sigma_{r,\theta}=\frac{p_i r_i^2-p_e r_e^2}{r_e^2-r_i^2}"
            r"\mp\frac{(p_i-p_e)r_i^2r_e^2}{r^2\,(r_e^2-r_i^2)}"
        ),
        croqui=_croqui_parede_espessa(),
    ),
)

CATALOGO: dict[str, ModeloCarga] = {modelo.chave: modelo for modelo in _MODELOS}

GRUPOS: dict[str, list[str]] = {
    grupo: [modelo.chave for modelo in _MODELOS if modelo.grupo == grupo]
    for grupo in ORDEM_GRUPOS
}

MODELO_PADRAO = _MODELOS[0].chave


def resolver_chave(valor: object) -> str:
    """Normaliza um rótulo vindo de outra página ou de uma sessão antiga."""
    if isinstance(valor, str):
        valor = ALIASES.get(valor, valor)
        if valor in CATALOGO:
            return valor
    return MODELO_PADRAO


# --------------------------------------------------------------------------
# Renderização
# --------------------------------------------------------------------------


def montar_svg(modelo: ModeloCarga) -> str:
    """SVG completo do croqui, pronto para ``st.image``.

    A fonte vai declarada no próprio SVG porque ele é servido dentro de uma
    tag ``img``, isolada do CSS da página.
    """
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_LARGURA_VIEWBOX} {_ALTURA_VIEWBOX}" role="img" '
        f'font-family="Inter, system-ui, -apple-system, sans-serif">'
        f"<title>Croqui: {modelo.chave}</title>"
        f"{modelo.croqui}</svg>"
    )


def desenhar_croqui(modelo: ModeloCarga) -> None:
    """Mostra o croqui do modelo, dimensionado à largura do contêiner.

    ``st.html`` não serve aqui: ele sanitiza a marcação pelo perfil HTML e
    descarta os elementos SVG inteiros. ``st.image`` reconhece uma string
    SVG e a embute como data URI.
    """
    st.image(montar_svg(modelo), width="stretch")


def cartao_modelo(modelo: ModeloCarga) -> None:
    """Cartão do modelo escolhido: croqui, o que entra, o que sai e a fórmula.

    Responde, antes de o usuário digitar qualquer número, à pergunta que
    antes só era respondida no resultado: este modelo devolve cisalhamento?
    Devolve tensão nas duas direções? É isso que decide se o estado serve
    para o Círculo de Mohr ou se vai chegar lá degenerado.
    """
    with st.container(border=True):
        croqui, texto = st.columns([2, 3], vertical_alignment="center")
        with croqui:
            desenhar_croqui(modelo)
        with texto:
            st.markdown(f"**{modelo.chave}**")
            st.caption(modelo.descricao)
            with st.container(horizontal=True):
                st.badge(
                    "Você informa: " + " · ".join(modelo.entradas),
                    icon=":material/input:",
                    color="gray",
                )
                st.badge(
                    "Devolve: " + " · ".join(modelo.saidas),
                    icon=":material/output:",
                    color="blue",
                )
            if len(modelo.saidas) == 1:
                st.caption(
                    ":material/info: Este modelo devolve uma única componente "
                    "— no Círculo de Mohr o estado aparecerá como uniaxial "
                    "ou de cisalhamento puro."
                )
        st.latex(modelo.formula)


def tabela_comparativa() -> list[dict[str, str]]:
    """Linhas para comparar todos os modelos lado a lado."""
    return [
        {
            "Grupo": modelo.grupo,
            "Modelo": modelo.chave,
            "Quando usar": modelo.resumo,
            "Você informa": " · ".join(modelo.entradas),
            "Devolve": " · ".join(modelo.saidas),
        }
        for modelo in _MODELOS
    ]
