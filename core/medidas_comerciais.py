"""Medidas que se compram: as séries comerciais e normalizadas, e qual campo usa qual série.

A caixinha do desenho sugere o vizinho comercial do valor digitado, e o estudo de uma medida procura
o primeiro valor comercial que passa. Série só existe onde há uma tabela de verdade por trás. Um
comprimento qualquer fica sem série: sugerir número "bonito" ali só daria falsa segurança.

Tudo em mm. As séries de mercado variam de fornecedor para fornecedor, e por isso cada uma diz de
onde veio. O programa sugere, e quem confirma a disponibilidade é a compra.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Serie:
    nome: str
    valores: tuple[float, ...]
    fonte: str


CHAPAS = Serie(
    "Chapas de aço",
    (
        0.6, 0.75, 0.9, 1.06, 1.2, 1.5, 1.9, 2.0, 2.25, 2.65, 3.0, 3.35, 3.75, 4.25, 4.75, 5.0,
        6.3, 8.0, 9.5, 12.5, 16.0, 19.0, 22.4, 25.0, 31.5, 37.5, 44.5, 50.0, 63.0, 75.0, 100.0,
    ),
    "Espessuras usuais de usina no Brasil. Confirmar com o fornecedor.",
)  # fmt: skip
PARAFUSOS = Serie(
    "Parafusos métricos",
    (
        3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 27.0, 30.0, 33.0,
        36.0, 39.0, 42.0, 45.0, 48.0, 52.0, 56.0, 60.0, 64.0,
    ),
    "Diâmetros nominais da ISO 261.",
)  # fmt: skip
EIXOS = Serie(
    "Assentos de rolamento",
    (
        10.0, 12.0, 15.0, 17.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0, 65.0, 70.0,
        75.0, 80.0, 85.0, 90.0, 95.0, 100.0, 105.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0,
        170.0, 180.0, 190.0, 200.0, 220.0, 240.0, 260.0, 280.0, 300.0,
    ),
    "Furos de rolamento da ISO 15: o eixo costuma ser feito para caber neles.",
)  # fmt: skip
BARRAS_REDONDAS = Serie(
    "Barras redondas",
    (
        6.0, 8.0, 10.0, 12.0, 14.0, 15.0, 16.0, 18.0, 19.0, 20.0, 22.0, 25.0, 28.0, 30.0, 32.0,
        35.0, 38.0, 40.0, 45.0, 50.0, 55.0, 60.0, 63.0, 65.0, 70.0, 75.0, 80.0, 85.0, 90.0, 95.0,
        100.0, 110.0, 120.0, 130.0, 140.0, 150.0,
    ),
    "Diâmetros usuais de barra laminada e trefilada. Confirmar com o fornecedor.",
)  # fmt: skip
ARAME_DE_MOLA = Serie(
    "Arame de mola",
    (
        0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 2.8, 3.0, 3.2, 3.5, 3.8, 4.0,
        4.5, 5.0, 5.6, 6.0, 6.3, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 18.0,
        20.0,
    ),
    "Diâmetros da EN 10270-1 mais usados.",
)  # fmt: skip
MODULOS = Serie(
    "Módulos de engrenagem",
    (
        1.0, 1.125, 1.25, 1.375, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5,
        6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 25.0, 28.0, 32.0,
        36.0, 40.0, 45.0, 50.0,
    ),
    "Módulos da ISO 54. As duas séries juntas: a primeira escolha é a de 1, 1,25, 1,5, 2, 2,5, 3…",
)  # fmt: skip
POLIAS = Serie(
    "Polias em V",
    (
        50.0, 56.0, 63.0, 71.0, 75.0, 80.0, 90.0, 100.0, 112.0, 118.0, 125.0, 132.0, 140.0, 150.0,
        160.0, 170.0, 180.0, 200.0, 212.0, 224.0, 236.0, 250.0, 280.0, 300.0, 315.0, 355.0, 375.0,
        400.0, 425.0, 450.0, 475.0, 500.0, 530.0, 560.0, 600.0, 630.0, 710.0, 750.0, 800.0, 900.0,
        1000.0, 1120.0, 1250.0,
    ),
    "Diâmetros primitivos da ISO 4183.",
)  # fmt: skip
PASSOS_DE_CORRENTE = Serie(
    "Correntes de rolos",
    (6.35, 8.0, 9.525, 12.7, 15.875, 19.05, 25.4, 31.75, 38.1, 44.45, 50.8, 63.5, 76.2),
    "Passos da ISO 606.",
)
FUSOS = Serie(
    "Roscas trapezoidais",
    (
        8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0, 30.0, 32.0, 36.0, 40.0,
        44.0, 48.0, 50.0, 52.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0, 85.0, 90.0, 95.0, 100.0,
        110.0, 120.0, 130.0, 140.0,
    ),
    "Diâmetros nominais da ISO 2904.",
)  # fmt: skip
PASSOS_DE_FUSO = Serie(
    "Passos de rosca trapezoidal",
    (1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0),
    "Passos da ISO 2904.",
)
CABOS = Serie(
    "Cabos de aço",
    (
        6.4, 8.0, 9.5, 11.5, 13.0, 14.5, 16.0, 19.0, 22.0, 26.0, 29.0, 32.0, 35.0, 38.0, 42.0,
        45.0, 48.0, 52.0,
    ),
    "Diâmetros usuais de catálogo no Brasil. Confirmar com o fornecedor.",
)  # fmt: skip
CAMISAS = Serie(
    "Camisas de cilindro",
    (
        8.0, 10.0, 12.0, 16.0, 20.0, 25.0, 32.0, 40.0, 50.0, 63.0, 80.0, 90.0, 100.0, 110.0,
        125.0, 140.0, 160.0, 180.0, 200.0, 220.0, 250.0, 280.0, 320.0, 360.0, 400.0, 450.0, 500.0,
    ),
    "Diâmetros de camisa da ISO 3320.",
)  # fmt: skip
HASTES = Serie(
    "Hastes de cilindro",
    (
        4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 25.0, 28.0, 32.0, 36.0,
        40.0, 45.0, 50.0, 56.0, 63.0, 70.0, 80.0, 90.0, 100.0, 110.0, 125.0, 140.0, 160.0, 180.0,
        200.0, 220.0, 250.0, 280.0, 320.0, 360.0,
    ),
    "Diâmetros de haste da ISO 3320.",
)  # fmt: skip
CANTONEIRAS_ABA = Serie(
    "Abas de cantoneira",
    (25.4, 31.75, 38.1, 44.45, 50.8, 63.5, 76.2, 88.9, 101.6, 127.0, 152.4, 203.2),
    "Abas usuais em polegadas. Confirmar com o fornecedor.",
)
CANTONEIRAS_T = Serie(
    "Espessuras de cantoneira",
    (3.2, 4.76, 6.35, 7.94, 9.53, 11.1, 12.7, 15.88, 19.05, 22.2, 25.4),
    "Espessuras usuais em polegadas. Confirmar com o fornecedor.",
)
CHAVETAS_B = Serie(
    "Largura de chaveta",
    (
        2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 25.0, 28.0, 32.0,
        36.0, 40.0, 45.0, 50.0,
    ),
    "Larguras da ISO 773.",
)  # fmt: skip
CHAVETAS_H = Serie(
    "Altura de chaveta",
    (
        2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0,
        25.0, 28.0,
    ),
    "Alturas da ISO 773.",
)  # fmt: skip
PERNAS_DE_SOLDA = Serie(
    "Pernas de filete de solda",
    (3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0),
    "As mesmas pernas da página de Ligações soldadas.",
)
RODAS = Serie(
    "Rodas de ponte rolante",
    (100.0, 125.0, 160.0, 200.0, 250.0, 315.0, 400.0, 500.0, 630.0, 800.0, 1000.0, 1250.0),
    "Série de números preferenciais R10, a usual em rodas.",
)

#: Para cada caso, a série de cada campo. Numa tabela, a chave é a coluna.
SERIE_DO_CAMPO: dict[str, dict[str, Serie]] = {
    "viga_reacoes": {"t_mm": CHAPAS},
    "flexao_secao": {"t_mm": CHAPAS},
    "coluna_simples": {"t_mm": CHAPAS},
    "trelica_plana": {"t_mm": CHAPAS},
    "barra_torcao": {"d_mm": BARRAS_REDONDAS},
    "chapa_furo": {"t_mm": CHAPAS},
    "engrenagem": {"modulo_mm": MODULOS},
    "engrenagem_conica": {"modulo_mm": MODULOS},
    "sem_fim": {"modulo_mm": MODULOS},
    "correia": {"d_mm": POLIAS, "D_mm": POLIAS},
    "corrente": {"passo_mm": PASSOS_DE_CORRENTE},
    "acoplamento": {"d_parafuso_mm": PARAFUSOS, "espessura_mm": CHAPAS},
    "eixo_transmissao": {"d_mm": EIXOS},
    "eixo_secao": {"d_mm": EIXOS, "D_mm": EIXOS},
    "chaveta": {"d_mm": EIXOS, "b_mm": CHAVETAS_B, "h_mm": CHAVETAS_H},
    "ajuste_prensado": {"d_mm": EIXOS},
    "bucha": {"d_mm": EIXOS},
    "pino_articulacao": {"d_mm": BARRAS_REDONDAS, "t_olhal_mm": CHAPAS, "t_garfo_mm": CHAPAS},
    "mola_compressao": {"d_mm": ARAME_DE_MOLA},
    "mola_tracao": {"d_mm": ARAME_DE_MOLA},
    "mola_torcao": {"d_mm": ARAME_DE_MOLA},
    "freio_cinta": {"t_mm": CHAPAS},
    "parafuso_potencia": {"d_mm": FUSOS, "passo_mm": PASSOS_DE_FUSO},
    "cabo_tambor": {"d_cabo_mm": CABOS},
    "roda_ponte": {"d_mm": RODAS},
    "olhal": {"t_mm": CHAPAS, "d_pino_mm": BARRAS_REDONDAS, "solda_mm": PERNAS_DE_SOLDA},
    "disco_girante": {"t_mm": CHAPAS},
    "cilindro_hidraulico": {"d_camisa_mm": CAMISAS, "d_haste_mm": HASTES, "tampa_mm": CHAPAS},
    "placa_circular": {"t_mm": CHAPAS},
    "placa_retangular": {"t_mm": CHAPAS},
    "Eixo circular maciço": {"d_mm": EIXOS},
    "Eixo circular vazado": {"de_mm": EIXOS},
    "Mola helicoidal de compressão": {"d_mm": ARAME_DE_MOLA},
    "Seção I sob força axial, flexão e cortante": {"tf_mm": CHAPAS, "tw_mm": CHAPAS},
    "Perfil U sob força axial, flexão e cortante": {"tf_mm": CHAPAS, "tw_mm": CHAPAS},
    "Cantoneira de abas iguais": {"aba_mm": CANTONEIRAS_ABA, "t_mm": CANTONEIRAS_T},
    "Perfil tubular retangular (caixão)": {"t_mm": CHAPAS},
    "Pinos ou parafusos sob cisalhamento": {"d_mm": PARAFUSOS},
    "Vaso cilíndrico de parede fina": {"t_mm": CHAPAS},
    "Vaso esférico de parede fina": {"t_mm": CHAPAS},
}


def serie_do_campo(caso_id: str, alvo: Any) -> Serie | None:
    """``alvo`` é a chave do campo ou uma célula de tabela (o que vale nela é a coluna)."""
    chave = alvo if isinstance(alvo, str) else alvo.coluna
    return SERIE_DO_CAMPO.get(caso_id, {}).get(chave)


def valores_que_cabem(serie: Serie, inicio: float, fim: float) -> list[float]:
    """Os valores da série dentro de uma faixa, do menor para o maior."""
    return [valor for valor in serie.valores if inicio - 1e-9 <= valor <= fim + 1e-9]
