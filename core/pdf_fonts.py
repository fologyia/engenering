"""Fonte TrueType com acentos, letras gregas e símbolos para os PDFs.

A Helvetica embutida no reportlab não tem σ, τ, √, ² nem ≥: cada PDF
precisava trocar os símbolos por "sigma", "sqrt", "^2" e "<=", e a equação
saía diferente da que o módulo escreveu. Uma TrueType do sistema resolve
isso — Segoe UI, Arial ou Calibri no Windows; DejaVu ou Liberation no Linux
do CI. Sem nenhuma delas, o chamador volta à Helvetica e reaplica as
substituições, para o memorial nunca deixar de sair.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass

# (nome de registro, arquivo regular, arquivo negrito). Os nomes soltos são
# procurados nas pastas de fontes que o reportlab já conhece (c:/windows/fonts
# entre elas); os caminhos absolutos cobrem as distribuições Linux comuns.
_CANDIDATAS = (
    ("SegoeUI", "segoeui.ttf", "segoeuib.ttf"),
    ("Arial", "arial.ttf", "arialbd.ttf"),
    ("Calibri", "calibri.ttf", "calibrib.ttf"),
    ("DejaVuSans", "DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
    (
        "DejaVuSans",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    ("LiberationSans", "LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf"),
    (
        "LiberationSans",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ),
)


@dataclass(frozen=True, slots=True)
class FontePdf:
    """Nomes de fonte registrados no reportlab e se eles cobrem Unicode."""

    regular: str
    negrito: str
    unicode: bool


_HELVETICA = FontePdf("Helvetica", "Helvetica-Bold", False)


@functools.cache
def fonte_pdf() -> FontePdf:
    """Registra a primeira TrueType disponível e devolve seus nomes.

    O resultado fica em cache: registrar a fonte é caro e o reportlab a
    mantém no processo. Falhas de leitura (arquivo ausente, fonte
    corrompida) apenas passam para a próxima candidata.
    """
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        return _HELVETICA
    for nome, regular, negrito in _CANDIDATAS:
        nome_negrito = f"{nome}-Bold"
        try:
            pdfmetrics.registerFont(TTFont(nome, regular))
            pdfmetrics.registerFont(TTFont(nome_negrito, negrito))
        except Exception:  # noqa: BLE001 - qualquer falha só descarta a candidata
            continue
        # Sem a família registrada, <b> dentro de um Paragraph não acha o negrito.
        pdfmetrics.registerFontFamily(
            nome, normal=nome, bold=nome_negrito, italic=nome, boldItalic=nome_negrito
        )
        return FontePdf(nome, nome_negrito, True)
    return _HELVETICA


_SUBSTITUICOES_ASCII = {
    "σvm": "sigma_vm",
    "σx": "sigma_x",
    "σy": "sigma_y",
    "σa": "sigma_a",
    "σm": "sigma_m",
    "τxy": "tau_xy",
    "ΔL": "Delta_L",
    "ΔT": "Delta_T",
    "≥": ">=",
    "≤": "<=",
    "σ": "sigma",
    "τ": "tau",
    "Δ": "Delta",
    "Σ": "SUM",
    "γ": "gamma",
    "α": "alpha",
    "ν": "nu",
    "λ": "lambda",
    "θ": "theta",
    "√": "sqrt",
    "→": "->",
    "∞": "infinito",
    "×": "x",
    "²": "^2",
    "³": "^3",
    "⁴": "^4",
    "–": "-",
    "—": "-",
}


def texto_para_fonte(texto: str, fonte: FontePdf) -> str:
    """Devolve o texto como a fonte consegue imprimi-lo.

    Com uma TrueType Unicode o texto sai intacto; com Helvetica, os
    símbolos que ela não tem viram a grafia ASCII equivalente.
    """
    if fonte.unicode:
        return texto
    for original, substituto in _SUBSTITUICOES_ASCII.items():
        texto = texto.replace(original, substituto)
    return texto
