"""Croquis dos casos de máquinas do Assistente de cargas, nas mesmas letras dos campos.

Reaproveita as primitivas de :mod:`components.load_models`. O desenho é fixo e sem escala: ele serve
para mostrar o que cada letra do formulário significa, e o resultado do cálculo vai nas tabelas.
"""

from __future__ import annotations

import math

from components.load_models import (
    _ALTURA_VIEWBOX,
    _CARGA,
    _CONTORNO,
    _CORPO,
    _COTA,
    _LARGURA_VIEWBOX,
    _arco_torque,
    _cota_horizontal,
    _cota_vertical,
    _linha_eixo,
    _pecas,
    _ponto_avaliado,
    _retangulo,
    _seta,
    _texto,
)


def _forca(x: float, y: float, rotulo: str, **kw: object) -> str:
    return _texto(x, y, rotulo, cor=_CARGA, tamanho=12, peso="700", italico=True, **kw)  # type: ignore[arg-type]


def _circulo(cx: float, cy: float, r: float, *, cheio: bool = True) -> str:
    preenchimento = _CORPO if cheio else "#FFFFFF"
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{preenchimento}" stroke="{_CONTORNO}" '
        'stroke-width="2"/>'
    )


def _linha(x1: float, y1: float, x2: float, y2: float, *, largura: float = 2.0) -> str:
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{_CONTORNO}" '
        f'stroke-width="{largura}" stroke-linecap="round"/>'
    )


def _caminho(d: str, *, fechado: bool = True) -> str:
    preenchimento = _CORPO if fechado else "none"
    return (
        f'<path d="{d}" fill="{preenchimento}" stroke="{_CONTORNO}" stroke-width="2" '
        'stroke-linejoin="round"/>'
    )


def _mancal(x: float, y: float) -> str:
    return (
        f'<polygon points="{x},{y} {x - 9},{y + 14} {x + 9},{y + 14}" fill="{_CORPO}" '
        f'stroke="{_CONTORNO}" stroke-width="1.6"/>'
    )


def _acionamento() -> str:
    return _pecas(
        _retangulo(14, 50, 60, 50),
        _texto(44, 79, "Motor", cor=_CONTORNO, tamanho=11),
        _linha(74, 75, 106, 75),
        _retangulo(106, 40, 76, 70),
        _texto(144, 79, "i, η", cor=_CONTORNO, tamanho=12, italico=True),
        _linha(182, 75, 216, 75),
        _circulo(236, 75, 22),
        _texto(236, 79, "J", cor=_CONTORNO, tamanho=12, italico=True),
        _texto(44, 40, "P, n", cor=_CARGA, tamanho=12, peso="700", italico=True),
        _texto(236, 40, "T, n₂", cor=_CARGA, tamanho=12, peso="700", italico=True),
    )


def _engrenagem() -> str:
    def dentes(cx: float, cy: float, r: float, n: int) -> str:
        return "".join(
            _linha(
                cx + r * math.cos(2 * math.pi * i / n),
                cy + r * math.sin(2 * math.pi * i / n),
                cx + (r + 6) * math.cos(2 * math.pi * i / n),
                cy + (r + 6) * math.sin(2 * math.pi * i / n),
                largura=3.0,
            )
            for i in range(n)
        )

    return _pecas(
        _circulo(90, 66, 30),
        dentes(90, 66, 30, 14),
        _circulo(186, 66, 50),
        dentes(186, 66, 50, 26),
        _texto(78, 52, "z₁", cor=_CONTORNO, tamanho=12, italico=True),
        _texto(186, 70, "z₂", cor=_CONTORNO, tamanho=12, italico=True),
        _seta(126, 66, 126, 16),
        _forca(112, 20, "F_t"),
        _seta(126, 66, 92, 66),
        _forca(104, 84, "F_r"),
        _cota_horizontal(116, 60, 120, "d₁"),
    )


def _conica() -> str:
    return _pecas(
        _caminho("M 60,40 L 140,76 L 60,112 Z"),
        _caminho("M 140,76 L 104,24 L 188,24 Z"),
        _linha_eixo(30, 76, 220, 76),
        _linha_eixo(146, 8, 146, 130),
        _texto(52, 80, "z₁", cor=_CONTORNO, tamanho=12, italico=True),
        _texto(158, 20, "z₂", cor=_CONTORNO, tamanho=12, italico=True),
        _seta(112, 92, 112, 132),
        _forca(120, 128, "F_r", ancora="start"),
        _seta(106, 92, 72, 92),
        _forca(82, 106, "F_a"),
        _texto(214, 70, "γ", cor=_COTA, italico=True),
    )


def _sem_fim() -> str:
    filetes = "".join(_linha(60 + 16 * i, 96, 74 + 16 * i, 126, largura=2.0) for i in range(9))
    return _pecas(
        _retangulo(52, 96, 160, 30),
        filetes,
        _linha_eixo(20, 111, 250, 111),
        _circulo(132, 48, 42),
        _texto(132, 52, "z₂", cor=_CONTORNO, tamanho=12, italico=True),
        _arco_torque(34, 111, 14, "T"),
        _texto(236, 104, "λ", cor=_COTA, italico=True),
    )


def _correia() -> str:
    return _pecas(
        _circulo(74, 76, 28),
        _circulo(194, 76, 54),
        _linha(70, 48, 190, 22),
        _linha(70, 104, 190, 130),
        _seta(120, 37, 150, 30),
        _forca(120, 26, "F₁"),
        _seta(150, 122, 120, 116),
        _forca(120, 138, "F₂"),
        _texto(74, 80, "d", cor=_CONTORNO, tamanho=12, italico=True),
        _texto(194, 80, "D", cor=_CONTORNO, tamanho=12, italico=True),
        _linha_eixo(74, 76, 194, 76),
        _texto(134, 72, "C", cor=_COTA, italico=True),
    )


def _corrente() -> str:
    elos = "".join(
        f'<circle cx="{76 + 16 * i}" cy="46" r="4" fill="{_CONTORNO}"/>'
        f'<circle cx="{76 + 16 * i}" cy="110" r="4" fill="{_CONTORNO}"/>'
        for i in range(8)
    )
    return _pecas(
        _circulo(70, 78, 30),
        _circulo(206, 78, 44),
        elos,
        _linha(76, 46, 188, 40, largura=1.4),
        _linha(76, 110, 188, 116, largura=1.4),
        _texto(70, 82, "z₁", cor=_CONTORNO, tamanho=12, italico=True),
        _texto(206, 82, "z₂", cor=_CONTORNO, tamanho=12, italico=True),
        _cota_horizontal(26, 92, 108, "p", acima=True),
        _forca(150, 36, "F_t"),
    )


def _acoplamento() -> str:
    return _pecas(
        _retangulo(120, 20, 18, 110),
        _retangulo(142, 20, 18, 110),
        _retangulo(26, 58, 94, 34),
        _retangulo(160, 58, 94, 34),
        _linha(112, 36, 168, 36, largura=4.0),
        _linha(112, 114, 168, 114, largura=4.0),
        _arco_torque(66, 75, 20, "T"),
        _cota_vertical(186, 36, 114, "D"),
        _texto(114, 16, "n parafusos", cor=_COTA, tamanho=10, ancora="middle"),
    )


def _eixo_inteiro() -> str:
    return _pecas(
        _linha_eixo(10, 70, 270, 70),
        _retangulo(24, 62, 232, 16),
        _mancal(60, 78),
        _mancal(210, 78),
        _seta(120, 24, 120, 60),
        _forca(130, 34, "F₁", ancora="start"),
        _seta(244, 24, 244, 60),
        _forca(236, 34, "F₂", ancora="end"),
        _texto(60, 108, "A", cor=_CONTORNO, tamanho=12, peso="700"),
        _texto(210, 108, "B", cor=_CONTORNO, tamanho=12, peso="700"),
        _cota_horizontal(126, 60, 210, "x_B − x_A"),
        _texto(26, 50, "T", cor=_CARGA, tamanho=12, peso="700", italico=True),
    )


def _eixo_ressalto() -> str:
    perfil = (
        "M 26,52 L 118,52 Q 130,52 132,38 L 254,38 L 254,112 L 132,112 Q 130,98 118,98 L 26,98 Z"
    )
    return _pecas(
        _caminho(perfil),
        _linha_eixo(12, 75, 268, 75),
        _ponto_avaliado(122, 50, "r"),
        _cota_vertical(34, 52, 98, "d"),
        _cota_vertical(232, 38, 112, "D"),
        _arco_torque(72, 75, 16, "M"),
        _texto(190, 134, "o entalhe é o que quebra o eixo", tamanho=10),
    )


def _chaveta() -> str:
    return _pecas(
        _circulo(140, 78, 62),
        _circulo(140, 78, 36, cheio=False),
        _retangulo(128, 30, 24, 24),
        _cota_horizontal(16, 128, 152, "b", acima=True),
        _cota_vertical(170, 30, 54, "h"),
        _texto(140, 82, "d", cor=_COTA, italico=True),
        _arco_torque(140, 78, 26, ""),
        _seta(96, 42, 124, 42),
        _forca(86, 40, "F", ancora="end"),
    )


def _ajuste() -> str:
    return _pecas(
        _retangulo(70, 30, 140, 92),
        f'<rect x="20" y="52" width="240" height="48" fill="#C7E6F4" stroke="{_CONTORNO}" '
        'stroke-width="2"/>',
        _linha_eixo(8, 76, 272, 76),
        _seta(120, 40, 120, 50),
        _seta(160, 112, 160, 102),
        _texto(140, 46, "p", cor=_CARGA, tamanho=12, peso="700", italico=True),
        _cota_vertical(232, 52, 100, "d"),
        _cota_horizontal(132, 70, 210, "L"),
        _texto(60, 28, "cubo D", cor=_COTA, tamanho=10),
    )


def _rolamento() -> str:
    esferas = "".join(
        f'<circle cx="{140 + 40 * math.cos(2 * math.pi * i / 8):.1f}" '
        f'cy="{78 + 40 * math.sin(2 * math.pi * i / 8):.1f}" r="9" fill="{_CARGA}"/>'
        for i in range(8)
    )
    return _pecas(
        _circulo(140, 78, 58),
        _circulo(140, 78, 50, cheio=False),
        _circulo(140, 78, 30),
        _circulo(140, 78, 22, cheio=False),
        esferas,
        _seta(140, 6, 140, 18),
        _forca(150, 16, "F_r", ancora="start"),
        _seta(236, 78, 204, 78),
        _forca(240, 74, "F_a", ancora="start"),
    )


def _bucha() -> str:
    return _pecas(
        _circulo(140, 70, 52),
        _circulo(140, 70, 42),
        _circulo(140, 70, 34, cheio=False),
        _seta(140, 6, 140, 34),
        _forca(150, 20, "F", ancora="start"),
        _cota_horizontal(130, 106, 174, "d"),
        _texto(232, 72, "L", cor=_COTA, italico=True),
        _texto(232, 88, "(largura)", cor=_COTA, tamanho=10),
    )


def _pino() -> str:
    return _pecas(
        _retangulo(92, 26, 18, 100),
        _retangulo(170, 26, 18, 100),
        _retangulo(118, 40, 44, 72),
        f'<rect x="76" y="66" width="128" height="20" rx="4" fill="#FDE7CF" stroke="{_CARGA}" '
        'stroke-width="2"/>',
        _cota_horizontal(22, 118, 162, "b", acima=True),
        _cota_horizontal(132, 92, 110, "a"),
        _texto(114, 36, "c", cor=_COTA, tamanho=11, italico=True),
        _seta(236, 76, 206, 76),
        _forca(240, 72, "d", ancora="start"),
    )


def _hertz() -> str:
    return _pecas(
        _circulo(140, 56, 44),
        _retangulo(40, 100, 200, 36),
        f'<ellipse cx="140" cy="100" rx="22" ry="5" fill="{_CARGA}" opacity="0.6"/>',
        _seta(140, 2, 140, 26),
        _forca(150, 14, "F", ancora="start"),
        _texto(140, 60, "d₁", cor=_CONTORNO, tamanho=12, italico=True),
        _texto(210, 94, "p₀", cor=_CARGA, tamanho=12, peso="700", italico=True),
    )


def _mola() -> str:
    espiras = "".join(
        _linha(112 if i % 2 == 0 else 168, 28 + 12 * i, 168 if i % 2 == 0 else 112, 40 + 12 * i)
        for i in range(7)
    )
    return _pecas(
        espiras,
        _seta(140, 2, 140, 24),
        _forca(150, 14, "F", ancora="start"),
        _linha(100, 112, 180, 112, largura=3.0),
        _cota_horizontal(128, 112, 168, "D"),
        _texto(182, 70, "N_a, d", cor=_COTA, ancora="start", italico=True),
        _cota_vertical(70, 28, 112, "L₀"),
    )


def _mola_tracao() -> str:
    espiras = "".join(
        _linha(80 + 12 * i, 104 if i % 2 == 0 else 56, 92 + 12 * i, 56 if i % 2 == 0 else 104)
        for i in range(10)
    )
    return _pecas(
        espiras,
        _caminho("M 80,104 C 40,110 36,80 62,80", fechado=False),
        _caminho("M 200,56 C 240,50 244,80 218,80", fechado=False),
        _seta(238, 80, 270, 80),
        _seta(40, 80, 8, 80),
        _forca(24, 70, "F"),
        _cota_vertical(214, 56, 104, "D"),
        _texto(140, 40, "N_b, d", cor=_COTA, italico=True),
        _texto(46, 124, "r₂", cor=_COTA, italico=True),
    )


def _mola_torcao() -> str:
    return _pecas(
        _circulo(96, 84, 42, cheio=False),
        _circulo(96, 84, 34, cheio=False),
        _circulo(96, 84, 15),
        _linha(96, 42, 236, 42, largura=3.0),
        _linha(62, 110, 16, 136, largura=3.0),
        _seta(236, 14, 236, 40),
        _forca(246, 28, "F", ancora="start"),
        _linha(96, 74, 96, 94, largura=1.0),
        _linha(86, 84, 106, 84, largura=1.0),
        _cota_horizontal(124, 96, 236, "a"),
        _cota_vertical(150, 42, 126, "D"),
        _texto(96, 106, "D_p", cor=_COTA, italico=True),
        _texto(190, 34, "N_b, d", cor=_COTA, italico=True),
    )


def _mola_prato() -> str:
    return _pecas(
        _caminho("M 50,92 L 104,62 L 104,74 L 50,104 Z"),
        _caminho("M 230,92 L 176,62 L 176,74 L 230,104 Z"),
        _linha_eixo(140, 28, 140, 118),
        _seta(104, 22, 104, 58),
        _seta(176, 22, 176, 58),
        _forca(140, 20, "F"),
        _cota_horizontal(120, 50, 230, "D_e"),
        _cota_horizontal(52, 104, 176, "D_i", acima=True),
        _cota_vertical(250, 62, 92, "h₀"),
        _texto(36, 100, "t", cor=_COTA, italico=True),
    )


def _disco_freio() -> str:
    return _pecas(
        _circulo(150, 80, 56),
        _circulo(150, 80, 30, cheio=False),
        _cota_vertical(218, 24, 136, "D"),
        _cota_horizontal(14, 120, 180, "d", acima=True),
        _arco_torque(150, 80, 18, ""),
        _seta(52, 80, 90, 80),
        _forca(46, 76, "F", ancora="end"),
        _texto(150, 60, "T", cor=_CARGA, tamanho=12, peso="700", italico=True),
    )


def _cinta() -> str:
    return _pecas(
        _circulo(120, 82, 48),
        '<path d="M 76,62 A 54,54 0 1 0 158,44" fill="none" stroke="#B95C00" stroke-width="4"/>',
        _linha(76, 62, 60, 20, largura=2.0),
        _linha(160, 44, 246, 20, largura=2.0),
        _texto(52, 24, "P₁", cor=_CARGA, tamanho=12, peso="700", italico=True),
        _texto(176, 22, "P₂", cor=_CARGA, tamanho=12, peso="700", italico=True),
        _texto(120, 86, "D", cor=_CONTORNO, tamanho=12, italico=True),
        _seta(252, 20, 252, 60),
        _forca(246, 62, "F", ancora="end"),
    )


def _fuso() -> str:
    filetes = "".join(_linha(40 + 14 * i, 60, 52 + 14 * i, 90, largura=2.0) for i in range(14))
    return _pecas(
        _retangulo(36, 60, 208, 30),
        filetes,
        _retangulo(110, 44, 60, 62),
        _texto(140, 79, "porca", cor=_CONTORNO, tamanho=11),
        _seta(262, 75, 248, 75),
        _forca(256, 62, "F"),
        _arco_torque(22, 75, 12, "T"),
        _cota_horizontal(120, 110, 170, "n filetes"),
        _texto(70, 112, "d, p", cor=_COTA, italico=True),
    )


def _cabo() -> str:
    return _pecas(
        _linha(92, 30, 210, 100, largura=1.6),
        _linha(48, 30, 170, 100, largura=1.6),
        _circulo(70, 30, 22),
        _texto(70, 34, "D", cor=_CONTORNO, tamanho=12, italico=True),
        _circulo(190, 100, 20),
        _linha(190, 120, 190, 128, largura=2.0),
        _seta(190, 124, 190, 146),
        _forca(200, 142, "Q + G", ancora="start"),
        _texto(30, 66, "tambor", cor=_COTA, tamanho=10, ancora="start"),
        _texto(214, 92, "moitão", cor=_COTA, tamanho=10, ancora="start"),
        _forca(150, 54, "T"),
    )


def _roda() -> str:
    return _pecas(
        _circulo(140, 64, 50),
        _retangulo(102, 114, 76, 14),
        _retangulo(120, 128, 40, 10),
        _seta(140, 2, 140, 20),
        _forca(150, 14, "F_r", ancora="start"),
        _texto(140, 68, "D", cor=_CONTORNO, tamanho=12, italico=True),
        _cota_vertical(214, 114, 128, "boleto ℓ"),
        _texto(64, 124, "b = ℓ − 2r", cor=_COTA, tamanho=10, italico=True),
    )


def _mecanismo() -> str:
    return _pecas(
        _retangulo(64, 56, 152, 40),
        _linha_eixo(40, 76, 240, 76),
        _seta(64, 76, 28, 76),
        _seta(216, 76, 252, 76),
        _forca(40, 68, "σ_t"),
        _ponto_avaliado(140, 58, "σ_f, τ"),
        _texto(140, 126, "σ_a = σ_r/(q·FS_r)", cor=_COTA, tamanho=12, italico=True),
    )


def _gancho() -> str:
    return _pecas(
        '<path d="M 140,6 L 140,34 A 50,50 0 1 1 90,84" fill="none" stroke="#0B6E99" '
        'stroke-width="16" stroke-linecap="round"/>',
        _linha_eixo(140, 84, 240, 84),
        '<circle cx="140" cy="84" r="3" fill="#B95C00"/>',
        _seta(140, 84, 140, 122),
        _forca(150, 116, "F", ancora="start"),
        _texto(164, 78, "r_i", cor=_COTA, italico=True),
        _texto(214, 76, "h", cor=_COTA, italico=True),
    )


def _olhal() -> str:
    return _pecas(
        _caminho("M 70,122 L 210,122 L 182,54 A 42,42 0 0 0 98,54 Z"),
        _circulo(140, 54, 16, cheio=False),
        _seta(140, 54, 140, 6),
        _forca(150, 16, "F", ancora="start"),
        _cota_horizontal(130, 70, 210, "L"),
        _cota_vertical(236, 54, 122, "h"),
        _texto(120, 54, "d", cor=_COTA, ancora="end", italico=True),
        _texto(182, 22, "a", cor=_COTA, italico=True),
        _texto(58, 110, "t", cor=_COTA, italico=True),
    )


def _desbalanceamento() -> str:
    return _pecas(
        _circulo(140, 60, 40),
        '<circle cx="164" cy="42" r="7" fill="#B95C00"/>',
        _seta(164, 42, 204, 14),
        _forca(210, 18, "m·e·ω²", ancora="start"),
        _retangulo(70, 104, 140, 12),
        _linha(92, 116, 84, 122),
        _linha(84, 122, 100, 128),
        _linha(100, 128, 92, 134),
        _linha(188, 116, 180, 122),
        _linha(180, 122, 196, 128),
        _linha(196, 128, 188, 134),
        _retangulo(50, 134, 180, 8),
        _texto(30, 126, "k, ζ", cor=_COTA, ancora="start", italico=True),
    )


def _base() -> str:
    return _pecas(
        _retangulo(70, 34, 140, 62),
        _texto(140, 50, "máquina", cor=_CONTORNO, tamanho=11),
        _retangulo(50, 96, 180, 14),
        _retangulo(62, 110, 18, 14),
        _retangulo(200, 110, 18, 14),
        _seta(36, 60, 68, 60),
        _forca(30, 54, "F_h", ancora="start"),
        _arco_torque(140, 76, 12, ""),
        _cota_horizontal(130, 71, 209, "ℓ_x"),
        _texto(226, 74, "T", cor=_CARGA, tamanho=12, peso="700", italico=True),
    )


def _disco_girante() -> str:
    return _pecas(
        _circulo(130, 76, 62),
        _circulo(130, 76, 14, cheio=False),
        _arco_torque(130, 76, 36, "ω"),
        _cota_vertical(206, 14, 138, "D_ext"),
        _texto(250, 30, "espessura t", cor=_COTA, tamanho=10, italico=True),
    )


def _cilindro() -> str:
    return _pecas(
        _retangulo(40, 44, 122, 64),
        _retangulo(162, 66, 88, 20),
        _retangulo(122, 48, 16, 56),
        _texto(84, 80, "p", cor=_CARGA, tamanho=12, peso="700", italico=True),
        _seta(244, 76, 276, 76),
        _forca(262, 62, "F"),
        _cota_vertical(16, 44, 108, "D"),
        _cota_horizontal(124, 138, 250, "curso"),
        _texto(206, 60, "haste d", cor=_COTA, tamanho=10),
    )


def _placa_circular() -> str:
    pressao = "".join(
        _seta(70 + 28 * i, 24, 70 + 28 * i, 48, largura=1.4, cabeca=5) for i in range(6)
    )
    return _pecas(
        pressao,
        _retangulo(50, 50, 180, 14),
        _retangulo(36, 64, 28, 14),
        _retangulo(216, 64, 28, 14),
        _texto(140, 16, "p", cor=_CARGA, tamanho=12, peso="700", italico=True),
        _cota_horizontal(106, 50, 230, "diâmetro livre"),
        _cota_vertical(248, 50, 64, "t"),
    )


def _placa_retangular() -> str:
    return _pecas(
        f'<polygon points="80,40 230,40 200,114 50,114" fill="{_CORPO}" stroke="{_CONTORNO}" '
        'stroke-width="2"/>',
        _seta(140, 8, 140, 70),
        _forca(150, 20, "q", ancora="start"),
        _cota_horizontal(128, 50, 200, "a (lado maior)"),
        _texto(226, 86, "b", cor=_COTA, italico=True),
        _texto(36, 96, "t", cor=_COTA, italico=True),
    )


def _acoes() -> str:
    return _pecas(
        _retangulo(30, 20, 220, 18),
        _linha(140, 38, 140, 86, largura=1.6),
        _retangulo(112, 86, 56, 40),
        _texto(140, 110, "S_L", cor=_CONTORNO, tamanho=12, italico=True),
        _seta(186, 112, 186, 72),
        _forca(194, 92, "ψ, v", ancora="start"),
        _texto(70, 58, "M_x (S_G + ψ S_L + S_H)", cor=_COTA, tamanho=10, ancora="start"),
    )


def _torcao_retangular() -> str:
    return _pecas(
        _retangulo(90, 36, 100, 70),
        _arco_torque(140, 72, 24, "T"),
        _cota_horizontal(124, 90, 190, "b"),
        _cota_vertical(198, 36, 106, "c"),
        _ponto_avaliado(190, 72, "τ"),
    )


def _apoio_fixo(x: float, y: float) -> str:
    return (
        f'<polygon points="{x},{y} {x - 10},{y + 15} {x + 10},{y + 15}" fill="{_CORPO}" '
        f'stroke="{_CONTORNO}" stroke-width="1.8"/>' + _linha(x - 15, y + 15, x + 15, y + 15)
    )


def _apoio_movel(x: float, y: float) -> str:
    return (
        f'<polygon points="{x},{y} {x - 10},{y + 12} {x + 10},{y + 12}" fill="{_CORPO}" '
        f'stroke="{_CONTORNO}" stroke-width="1.8"/>'
        + _circulo(x - 6, y + 15, 3, cheio=False)
        + _circulo(x + 6, y + 15, 3, cheio=False)
        + _linha(x - 15, y + 18, x + 15, y + 18)
    )


def _parede(x: float, y1: float, y2: float, *, lado: float = -1.0) -> str:
    riscos = "".join(
        _linha(x, y1 + i * 10, x + lado * 8, y1 + i * 10 + 8, largura=1.2)
        for i in range(int((y2 - y1) / 10))
    )
    return _linha(x, y1, x, y2, largura=3.0) + riscos


def _parafuso_axial() -> str:
    return _pecas(
        _retangulo(70, 44, 140, 26),
        _retangulo(70, 82, 140, 26),
        _retangulo(128, 22, 24, 22),
        _retangulo(133, 44, 14, 90),
        _retangulo(124, 108, 32, 16),
        _linha_eixo(140, 10, 140, 142),
        _seta(40, 57, 40, 30),
        _seta(40, 95, 40, 122),
        _forca(30, 26, "P"),
        _forca(30, 134, "P"),
        _cota_vertical(232, 44, 108, "aperto"),
        _texto(172, 34, "F_i", cor=_CONTORNO, tamanho=12, italico=True),
    )


def _rosca_na_peca() -> str:
    filetes = "".join(_linha(128, 66 + 8 * i, 152, 62 + 8 * i, largura=1.4) for i in range(6))
    return _pecas(
        _retangulo(64, 58, 152, 74),
        _retangulo(118, 18, 44, 16),
        _retangulo(128, 34, 24, 74),
        filetes,
        _linha_eixo(140, 8, 140, 142),
        _seta(140, 18, 140, 2),
        _forca(150, 12, "F", ancora="start"),
        _cota_vertical(236, 58, 108, "L_e"),
        _texto(90, 122, "peça", cor=_CONTORNO, tamanho=11),
    )


def _torque_de_aperto() -> str:
    return _pecas(
        _retangulo(60, 92, 160, 30),
        _retangulo(124, 68, 32, 24),
        _retangulo(133, 92, 14, 44),
        _linha(140, 62, 216, 28, largura=7.0),
        _circulo(140, 62, 12),
        _arco_torque(140, 62, 26, ""),
        _forca(176, 24, "T"),
        _seta(120, 68, 120, 96, cor=_COTA),
        _texto(102, 84, "F_i", cor=_CONTORNO, tamanho=12, italico=True),
    )


def _grupo_de_parafusos() -> str:
    furos = "".join(
        _circulo(
            120 + 46 * math.cos(2 * math.pi * i / 8 + 0.39),
            66 + 46 * math.sin(2 * math.pi * i / 8 + 0.39),
            6,
            cheio=False,
        )
        for i in range(8)
    )
    return _pecas(
        _circulo(120, 66, 60),
        furos,
        _linha_eixo(44, 66, 196, 66),
        _linha_eixo(120, 2, 120, 130),
        _texto(202, 70, "x", cor=_COTA, italico=True, ancora="start"),
        _texto(128, 12, "y", cor=_COTA, italico=True, ancora="start"),
        _forca(246, 50, "N, M"),
        _forca(246, 70, "V, T"),
        _cota_horizontal(132, 70, 170, "d_c"),
    )


def _viga_reacoes() -> str:
    seta_q = "".join(_seta(52 + 26 * i, 30, 52 + 26 * i, 58, cabeca=5.0) for i in range(8))
    return _pecas(
        _linha(52, 30, 234, 30, largura=2.0).replace(_CONTORNO, _CARGA),
        seta_q,
        _retangulo(40, 62, 206, 12),
        _apoio_fixo(52, 74),
        _apoio_movel(234, 74),
        _forca(146, 22, "q"),
        _seta(52, 136, 52, 116, cor=_COTA),
        _seta(234, 136, 234, 116, cor=_COTA),
        _texto(64, 134, "R_A", cor=_COTA, tamanho=11, ancora="start"),
        _texto(222, 134, "R_B", cor=_COTA, tamanho=11, ancora="end"),
        _cota_horizontal(112, 80, 206, "L"),
    )


def _perfil_flexao() -> str:
    return _pecas(
        _retangulo(70, 12, 90, 12),
        _retangulo(109, 24, 12, 82),
        _retangulo(70, 106, 90, 12),
        _linha_eixo(46, 65, 184, 65),
        _arco_torque(218, 65, 22, "M"),
        _texto(190, 69, "x", cor=_COTA, italico=True),
        _cota_vertical(36, 12, 118, "d"),
        _cota_horizontal(130, 70, 160, "b_f"),
        _texto(126, 58, "t_w", cor=_COTA, tamanho=11, ancora="start"),
    )


def _flexao_de_secao() -> str:
    return _pecas(
        _retangulo(66, 24, 66, 102),
        _linha_eixo(50, 75, 150, 75),
        _caminho("M 176,24 L 226,24 L 176,75 Z"),
        _caminho("M 176,75 L 126,126 L 176,126 Z"),
        _linha(176, 18, 176, 132),
        _forca(236, 30, "σ", ancora="start"),
        _forca(112, 140, "σ", ancora="start"),
        _arco_torque(38, 75, 18, "M"),
    )


def _barra_em_trechos() -> str:
    return _pecas(
        _parede(44, 34, 116),
        _retangulo(44, 46, 100, 58),
        _retangulo(144, 58, 70, 34),
        _seta(214, 75, 256, 75),
        _forca(258, 66, "F", ancora="end"),
        _texto(94, 79, "A₁", cor=_CONTORNO, tamanho=12, italico=True),
        _texto(179, 79, "A₂", cor=_CONTORNO, tamanho=12, italico=True),
        _cota_horizontal(124, 44, 144, "L₁"),
        _cota_horizontal(124, 144, 214, "L₂"),
    )


def _barra_em_torcao() -> str:
    return _pecas(
        _parede(44, 34, 116),
        _retangulo(44, 50, 106, 50),
        _retangulo(150, 58, 72, 34),
        _linha_eixo(30, 75, 258, 75),
        _arco_torque(222, 75, 26, "T"),
        _cota_horizontal(124, 44, 150, "L₁"),
        _cota_horizontal(124, 150, 222, "L₂"),
        _texto(98, 79, "d₁", cor=_CONTORNO, tamanho=12, italico=True),
        _texto(186, 79, "d₂", cor=_CONTORNO, tamanho=12, italico=True),
    )


def _coluna() -> str:
    return _pecas(
        _apoio_fixo(140, 124),
        _retangulo(132, 34, 16, 90),
        _caminho("M 140,34 Q 186,79 140,124", fechado=False),
        _circulo(140, 34, 4, cheio=False),
        _seta(140, 2, 140, 28),
        _forca(150, 14, "P", ancora="start"),
        _cota_vertical(96, 34, 124, "L"),
        _texto(196, 82, "flambagem", cor=_CONTORNO, tamanho=11, ancora="start"),
    )


def _trelica() -> str:
    nos = ((40, 110), (106, 110), (172, 110), (238, 110), (106, 44), (172, 44))
    barras = ((0, 1), (1, 2), (2, 3), (0, 4), (4, 5), (5, 3), (1, 4), (2, 5), (1, 5))
    return _pecas(
        "".join(_linha(nos[a][0], nos[a][1], nos[b][0], nos[b][1], largura=3.0) for a, b in barras),
        "".join(_circulo(x, y, 3.5, cheio=False) for x, y in nos),
        _apoio_fixo(40, 114),
        _apoio_movel(238, 114),
        _seta(106, 116, 106, 144),
        _seta(172, 116, 172, 144),
        _forca(118, 142, "F", ancora="start"),
        _forca(184, 142, "F", ancora="start"),
    )


def _portico() -> str:
    return _pecas(
        _linha(70, 100, 70, 34, largura=5.0),
        _linha(70, 34, 214, 34, largura=5.0),
        _linha(214, 34, 214, 100, largura=5.0),
        _apoio_fixo(70, 100),
        _apoio_fixo(214, 100),
        "".join(_seta(82 + 24 * i, 8, 82 + 24 * i, 28, cabeca=5.0) for i in range(6)),
        _seta(28, 34, 62, 34),
        _forca(146, 6, "q"),
        _forca(32, 26, "H"),
        _cota_horizontal(128, 70, 214, "L"),
        _cota_vertical(244, 34, 100, "h"),
    )


def _equilibrio() -> str:
    return _pecas(
        _caminho("M 50,60 L 110,40 L 226,52 L 232,92 L 120,104 L 44,92 Z"),
        _apoio_fixo(70, 98),
        _apoio_movel(206, 96),
        _seta(132, 8, 132, 44),
        _forca(142, 18, "F₁", ancora="start"),
        _seta(250, 36, 214, 62),
        _forca(256, 34, "F₂", ancora="end"),
        _texto(70, 134, "A", cor=_CONTORNO, tamanho=12, peso="700"),
        _texto(206, 134, "B", cor=_CONTORNO, tamanho=12, peso="700"),
    )


def _secao_montada() -> str:
    return _pecas(
        _retangulo(70, 18, 120, 10),
        _retangulo(124, 28, 12, 78),
        _retangulo(92, 106, 76, 10),
        _linha_eixo(46, 74, 214, 74),
        _circulo(130, 74, 4),
        _texto(218, 78, "CG", cor=_CONTORNO, tamanho=12, peso="700", ancora="start"),
        _cota_vertical(40, 74, 116, "ȳ"),
        _cota_horizontal(128, 92, 168, "b₂"),
        _texto(200, 26, "b₁", cor=_COTA, tamanho=11, italico=True, ancora="start"),
    )


def _chapa_com_furo() -> str:
    return _pecas(
        _retangulo(60, 30, 140, 76),
        _circulo(130, 68, 17, cheio=False),
        _seta(60, 68, 22, 68),
        _seta(200, 68, 238, 68),
        _forca(30, 60, "F"),
        _forca(230, 60, "F"),
        _cota_vertical(250, 30, 106, "b"),
        _cota_horizontal(122, 113, 147, "d"),
    )


CROQUIS: dict[str, str] = {
    "parafuso_axial": _parafuso_axial(),
    "rosca_arrancamento": _rosca_na_peca(),
    "torque_aperto": _torque_de_aperto(),
    "grupo_parafusos": _grupo_de_parafusos(),
    "viga_reacoes": _viga_reacoes(),
    "perfil_nbr8800": _perfil_flexao(),
    "flexao_secao": _flexao_de_secao(),
    "barra_axial": _barra_em_trechos(),
    "barra_torcao": _barra_em_torcao(),
    "coluna_simples": _coluna(),
    "trelica_plana": _trelica(),
    "portico_simples": _portico(),
    "equilibrio_peca": _equilibrio(),
    "secao_montada": _secao_montada(),
    "chapa_furo": _chapa_com_furo(),
    "acionamento": _acionamento(),
    "engrenagem": _engrenagem(),
    "engrenagem_conica": _conica(),
    "sem_fim": _sem_fim(),
    "correia": _correia(),
    "corrente": _corrente(),
    "acoplamento": _acoplamento(),
    "eixo_transmissao": _eixo_inteiro(),
    "eixo_secao": _eixo_ressalto(),
    "chaveta": _chaveta(),
    "ajuste_prensado": _ajuste(),
    "rolamento": _rolamento(),
    "bucha": _bucha(),
    "pino_articulacao": _pino(),
    "hertz": _hertz(),
    "mola_compressao": _mola(),
    "mola_tracao": _mola_tracao(),
    "mola_torcao": _mola_torcao(),
    "mola_prato": _mola_prato(),
    "embreagem_disco": _disco_freio(),
    "freio_cinta": _cinta(),
    "parafuso_potencia": _fuso(),
    "acoes_icamento": _acoes(),
    "cabo_tambor": _cabo(),
    "roda_ponte": _roda(),
    "mecanismo_nbr8400": _mecanismo(),
    "gancho": _gancho(),
    "olhal": _olhal(),
    "desbalanceamento": _desbalanceamento(),
    "base_maquina": _base(),
    "disco_girante": _disco_girante(),
    "cilindro_hidraulico": _cilindro(),
    "placa_circular": _placa_circular(),
    "placa_retangular": _placa_retangular(),
    "Torção de seção retangular": _torcao_retangular(),
}


def svg_do_croqui(titulo: str, desenho: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_LARGURA_VIEWBOX} {_ALTURA_VIEWBOX}" role="img" '
        'font-family="Inter, system-ui, -apple-system, sans-serif">'
        f"<title>Croqui: {titulo}</title>{desenho}</svg>"
    )
