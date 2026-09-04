"""
Conversões de unidades usadas nos módulos de cálculo.

Convenção do projeto: internamente todos os cálculos trabalham em
unidades SI (MPa, mm, °C). As telas do Streamlit podem, no futuro,
oferecer entrada em outras unidades e converter na borda usando estas
funções, mas o núcleo de cálculo (core/) nunca deve assumir outra coisa
além de SI.
"""

MPA_PER_KPSI = 6.894757
MM_PER_IN = 25.4


def kpsi_para_mpa(valor_kpsi: float) -> float:
    return valor_kpsi * MPA_PER_KPSI


def mpa_para_kpsi(valor_mpa: float) -> float:
    return valor_mpa / MPA_PER_KPSI


def mm_para_in(valor_mm: float) -> float:
    return valor_mm / MM_PER_IN


def in_para_mm(valor_in: float) -> float:
    return valor_in * MM_PER_IN


def fahrenheit_para_celsius(t_f: float) -> float:
    return (t_f - 32.0) * 5.0 / 9.0


def celsius_para_fahrenheit(t_c: float) -> float:
    return t_c * 9.0 / 5.0 + 32.0
