"""Fonte do PDF: com a Helvetica de reserva, nenhum caractere sai como glifo ausente."""

from __future__ import annotations

from core import pdf_fonts as pf


def test_helvetica_de_reserva_imprime_indices_e_gregos():
    texto = pf.texto_para_fonte("V_k = V₀·S₁·S₂·S₃; η, φ ≈ 2; ℓ_f; ψ₀", pf._HELVETICA)
    texto.encode("cp1252")  # tudo imprimível na Helvetica (WinAnsi)
    assert "V0·S1·S2·S3" in texto and "eta, phi ~ 2" in texto and "l_f" in texto
    assert "psi0" in texto


def test_fonte_unicode_mantem_o_texto():
    unicode = pf.FontePdf("X", "X-Bold", True)
    assert pf.texto_para_fonte("S₁ η", unicode) == "S₁ η"
