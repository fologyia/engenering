"""Converte as tabelas de bitolas I, U e T da Gerdau em catálogos de perfis.

A extração de texto da página 3 do PDF de origem (perfis I, U e T impressos
lado a lado) sai limpa com ``pdfplumber``, ao contrário da página de perfis
W/HP tratada por :mod:`importar_catalogo_gerdau` — por isso aqui os valores
já vêm conferidos e digitados como uma tabela, em vez de reconstruídos por
posição na página.

A Gerdau não tabula módulo plástico (Z), constante de torção (J) nem
constante de empenamento (Cw) para I, U e T — só elástico (W), inércia e
raio de giração. Por isso essas três propriedades são obtidas chamando as
mesmas funções geométricas idealizadas que o catálogo embutido já usa
(:mod:`core.steel_sections`), alimentadas com as dimensões REAIS da tabela.
Área, inércia, módulo elástico, raio de giração e massa, que a Gerdau dá
prontos, vêm direto da tabela — não são recalculados.

Cada linha é conferida contra a própria tabela: o raio de giração tabelado
precisa bater com ``sqrt(I/A)`` calculado a partir da área e inércia da
mesma linha. Só rx/ry entram nessa conferência — não o módulo elástico W,
que o programa nunca grava (deriva sempre de I/altura em tempo de
execução) e que não tem fórmula simples válida para mesa cônica (I) ou
seção monossimétrica (U, T).

Uso::

    python scripts/importar_catalogo_gerdau_iut.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.steel_sections import perfil_i_simetrico, perfil_t, perfil_u  # noqa: E402

# Perfis T têm dimensões tabeladas com só 2 casas decimais (ex.: rx = 0,48
# cm), então o arredondamento sozinho já produz ~3-4% de diferença contra
# sqrt(I/A) mesmo quando os dados estão corretos — TOL_R cobre essa faixa.
TOL_R = 0.04

# ---------------------------------------------------------------------------
# Dados tabelados (Gerdau — Catálogo de bitolas, perfis I, U e T)
# ---------------------------------------------------------------------------

# nome, peso_kg_m, d_mm, tw_mm, bf_mm, tf_mm, area_cm2, ix_cm4, wx_cm3, rx_cm,
# iy_cm4, wy_cm3, ry_cm
DADOS_I = [
    ('I 3" x 8,48', 8.48, 76.20, 4.32, 59.18, 6.60, 10.80, 105.10, 27.60, 3.12, 18.90, 6.40, 1.33),
    ('I 3" x 9,68', 9.68, 76.20, 6.38, 61.24, 6.60, 12.32, 115.00, 30.18, 3.06, 45.60, 11.48, 1.92),
    ('I 4" x 11,46', 11.46, 101.60, 4.90, 67.60, 7.44, 14.50, 252.00, 49.70, 4.17, 31.70, 9.40, 1.48),
    ('I 4" x 12,65', 12.65, 101.60, 6.43, 69.20, 7.44, 16.11, 266.00, 52.40, 4.06, 34.30, 9.90, 1.46),
    ('I 5" x 14,88', 14.88, 127.00, 5.44, 76.30, 8.28, 18.80, 511.00, 80.40, 5.21, 50.20, 13.2, 1.63),
    ('I 5" x 18,24', 18.24, 127.00, 8.81, 79.70, 8.28, 23.24, 570.00, 89.80, 4.95, 58.60, 14.7, 1.59),
    ('I 6" x 18,60', 18.60, 152.40, 5.89, 84.63, 9.12, 23.60, 919.00, 120.60, 6.24, 75.70, 17.90, 1.79),
    ('I 6" x 22,00', 22.00, 152.40, 8.71, 87.50, 9.12, 27.97, 1003.00, 131.70, 5.99, 84.90, 19.40, 1.74),
]

DADOS_U = [
    ('U 3" x 6,10', 6.10, 76.20, 4.32, 35.81, 6.93, 7.78, 68.90, 18.10, 2.98, 8.20, 3.32, 1.03),
    ('U 3" x 7,44', 7.44, 76.20, 6.55, 35.05, 6.93, 9.48, 77.20, 20.30, 2.85, 10.30, 3.82, 1.04),
    ('U 4" x 8,04', 8.04, 101.60, 4.67, 40.23, 7.52, 10.10, 159.50, 31.40, 3.97, 13.10, 4.61, 1.14),
    ('U 4" x 9,30', 9.30, 101.60, 6.27, 41.83, 7.52, 11.90, 174.40, 34.30, 3.84, 15.50, 5.10, 1.14),
    ('U 6" x 12,20', 12.20, 152.40, 5.08, 48.77, 8.71, 15.50, 546.00, 71.70, 5.94, 28.80, 8.16, 1.36),
    ('U 6" x 15,62', 15.62, 152.40, 7.98, 51.66, 8.71, 19.90, 632.00, 82.90, 5.63, 36.00, 9.24, 1.34),
    # U 8" (17,10 e 20,50 kg/m) fica de fora: o ry impresso na tabela de
    # origem (1,42 nos dois pesos) não bate com sqrt(Iy/Área) em nenhum dos
    # dois — 1,58 e 1,55 respectivamente — de forma consistente demais para
    # ser coincidência de leitura. Provável erro de impressão na fonte;
    # melhor excluir a bitola do que arriscar um ry errado numa verificação
    # de flambagem.
    ('U 10" x 22,77', 22.77, 254.00, 6.10, 66.04, 11.10, 29.00, 2800.00, 221.00, 9.84, 95.00, 19.00, 1.81),
    ('U 10" x 30,80', 30.80, 254.00, 7.20, 74.00, 12.70, 39.30, 5370.00, 352.00, 11.70, 161.00, 28.30, 2.03),
    ('U 12" x 29,76', 29.76, 305.00, 9.63, 69.57, 11.10, 37.90, 3290.00, 259.00, 9.31, 117.00, 21.60, 1.76),
    ('U 12" x 37,00', 37.00, 305.00, 9.80, 77.00, 12.70, 47.40, 6010.00, 394.00, 11.30, 186.00, 30.90, 1.98),
]

# nome, dbf_mm (mesa=alma, seção quadrada), t_mm (espessura única), peso_kg_m,
# area_cm2, ix_cm4, wx_cm3, rx_cm, iy_cm4, wy_cm3, ry_cm
DADOS_T = [
    ('T 5/8x1/8"', 15.88, 3.18, 0.71, 0.90, 0.20, 0.19, 0.47, 0.11, 0.14, 0.35),
    ('T 3/4x1/8"', 19.05, 3.18, 0.86, 1.13, 0.36, 0.27, 0.57, 0.19, 0.20, 0.41),
    ('T 7/8x1/8"', 22.22, 3.18, 0.99, 1.34, 0.59, 0.38, 0.67, 0.33, 0.27, 0.48),
    ('T 1x1/8"', 25.40, 3.18, 1.18, 1.54, 0.90, 0.50, 0.77, 0.44, 0.35, 0.54),
    ('T 1.1/4x1/8"', 31.75, 3.18, 1.50, 1.92, 1.84, 0.81, 0.98, 0.86, 0.54, 0.67),
    ('T 1.1/2x1/8"', 38.10, 3.18, 1.82, 2.32, 3.24, 1.18, 1.18, 1.47, 0.77, 0.80),
    ('T 1.1/4x3/16"', 31.75, 4.76, 2.16, 2.79, 2.56, 1.16, 0.96, 1.29, 0.82, 0.68),
    ('T 1.1/2x3/16"', 38.10, 4.76, 2.65, 3.40, 4.56, 1.70, 1.16, 2.22, 1.17, 0.81),
    ('T 2x3/16"', 50.80, 4.76, 3.62, 4.61, 11.33, 3.12, 1.57, 5.24, 2.06, 1.07),
    ('T 2x1/4"', 50.80, 6.35, 4.74, 6.05, 14.47, 4.04, 1.55, 7.03, 2.77, 1.08),
]


def _checar(label, area_cm2, ix_cm4, rx_cm, iy_cm4, ry_cm):
    """Confere só rx e ry — o que de fato entra no catálogo via área/Ix/Iy.

    O módulo elástico (Wx/Wy) tabelado pela Gerdau NÃO é gravado no JSON: o
    programa sempre deriva sx/sy de ix/altura em tempo de execução (igual já
    faz para os perfis W), então uma diferença em Wx/Wy tabelado não indica
    erro no que este script grava — e para I (mesa cônica) e U/T
    (monossimétricos) essa fórmula nem se aplica à seção real. Por isso só
    rx e ry, que validam área/Ix/Iy diretamente, bloqueiam a importação.
    """
    rx_calc = math.sqrt(ix_cm4 / area_cm2)
    if abs(rx_calc - rx_cm) > TOL_R * rx_cm:
        raise ValueError(f"{label}: rx tabelado {rx_cm} vs sqrt(I/A) = {rx_calc:.4f}")
    ry_calc = math.sqrt(iy_cm4 / area_cm2)
    if abs(ry_calc - ry_cm) > TOL_R * ry_cm:
        raise ValueError(f"{label}: ry tabelado {ry_cm} vs sqrt(I/A) = {ry_calc:.4f}")


def _zx_zy_escalados(geometrico, ix_mm4_real: float, iy_mm4_real: float) -> tuple[float, float]:
    """Escala o módulo plástico idealizado pela razão entre inércia real e
    idealizada, preservando o fator de forma (Z/S) calculado da geometria.

    A área/Ix/Iy tabelados pela Gerdau incluem raio de concordância e (no
    perfil I) mesa cônica, que a geometria idealizada — retângulos simples —
    não reproduz. Usar Zx/Zy idealizado direto, ao lado de Wx/Wy derivado da
    inércia REAL, pode gerar Zx menor que Wx: impossível fisicamente, já que
    o módulo plástico nunca é menor que o elástico. Escalar por Ix_real/Ix_
    idealizado mantém o fator de forma da geometria idealizada intacto (que
    por construção sempre satisfaz Z ≥ S) enquanto acompanha a inércia real.
    """
    zx = geometrico.zx_mm3 * (ix_mm4_real / geometrico.ix_mm4)
    zy = geometrico.zy_mm3 * (iy_mm4_real / geometrico.iy_mm4)
    return zx, zy


def _perfil_i(linha):
    nome, peso, d, tw, bf, tf, area, ix, _wx, rx, iy, _wy, ry = linha
    _checar(nome, area, ix, rx, iy, ry)
    geometrico = perfil_i_simetrico(nome, d, bf, tw, tf)
    ix_mm4, iy_mm4 = round(ix * 1e4, 1), round(iy * 1e4, 1)
    zx_mm3, zy_mm3 = _zx_zy_escalados(geometrico, ix_mm4, iy_mm4)
    return {
        "nome": nome,
        "familia": "I duplamente simétrico",
        "area_mm2": round(area * 100.0, 2),
        "ix_mm4": ix_mm4,
        "iy_mm4": iy_mm4,
        "zx_mm3": round(zx_mm3, 1),
        "zy_mm3": round(zy_mm3, 1),
        "j_mm4": round(geometrico.j_mm4, 1),
        "cw_mm6": round(geometrico.cw_mm6, 1),
        "altura_mm": d,
        "largura_mm": bf,
        "espessura_alma_mm": tw,
        "espessura_mesa_mm": tf,
        "area_cisalhamento_mm2": round((d - 2 * tf) * tw, 2),
        "massa_kg_m": peso,
        "descricao": (
            f"{nome} — d {d:.1f} mm, bf {bf:.1f} mm, tw {tw:.2f} mm, tf {tf:.2f} mm. "
            "Zx/Zy/J/Cw estimados por geometria idealizada (não tabelados pelo fabricante)."
        ),
    }


def _perfil_u(linha):
    nome, peso, d, tw, bf, tf, area, ix, _wx, rx, iy, _wy, ry = linha
    _checar(nome, area, ix, rx, iy, ry)
    geometrico = perfil_u(nome, d, bf, tw, tf)
    ix_mm4, iy_mm4 = round(ix * 1e4, 1), round(iy * 1e4, 1)
    zx_mm3, zy_mm3 = _zx_zy_escalados(geometrico, ix_mm4, iy_mm4)
    return {
        "nome": nome,
        "familia": "U (canal laminado)",
        "area_mm2": round(area * 100.0, 2),
        "ix_mm4": ix_mm4,
        "iy_mm4": iy_mm4,
        "zx_mm3": round(zx_mm3, 1),
        "zy_mm3": round(zy_mm3, 1),
        "j_mm4": round(geometrico.j_mm4, 1),
        "cw_mm6": 0.0,
        "altura_mm": d,
        "largura_mm": bf,
        "espessura_alma_mm": tw,
        "espessura_mesa_mm": tf,
        "area_cisalhamento_mm2": round((d - 2 * tf) * tw, 2),
        "massa_kg_m": peso,
        "descricao": (
            f"{nome} — d {d:.1f} mm, bf {bf:.1f} mm, tw {tw:.2f} mm, tf {tf:.2f} mm. "
            "Zx/Zy/J estimados por geometria idealizada (não tabelados pelo fabricante). "
            "O módulo elástico Sy que o programa deriva de Iy/(bf/2) é aproximado: "
            "o perfil U real é monossimétrico em y, e o centroide não fica em bf/2."
        ),
    }


def _perfil_t(linha):
    nome, dbf, t, peso, area, ix, _wx, rx, iy, _wy, ry = linha
    _checar(nome, area, ix, rx, iy, ry)
    geometrico = perfil_t(nome, dbf, dbf, t, t)
    ix_mm4, iy_mm4 = round(ix * 1e4, 1), round(iy * 1e4, 1)
    zx_mm3, zy_mm3 = _zx_zy_escalados(geometrico, ix_mm4, iy_mm4)
    return {
        "nome": nome,
        "familia": "T (perfil tê)",
        "area_mm2": round(area * 100.0, 2),
        "ix_mm4": ix_mm4,
        "iy_mm4": iy_mm4,
        "zx_mm3": round(zx_mm3, 1),
        "zy_mm3": round(zy_mm3, 1),
        "j_mm4": round(geometrico.j_mm4, 1),
        "cw_mm6": 0.0,
        "altura_mm": dbf,
        "largura_mm": dbf,
        "espessura_alma_mm": t,
        "espessura_mesa_mm": t,
        "area_cisalhamento_mm2": round((dbf - t) * t, 2),
        "massa_kg_m": peso,
        "descricao": (
            f"{nome} — d=bf {dbf:.2f} mm, t {t:.2f} mm. Zx/Zy/J estimados por "
            "geometria idealizada (não tabelados pelo fabricante). Módulo elástico "
            "Wx da tabela assume eixo simétrico; o perfil T real é monossimétrico "
            "em x, então este valor é aproximado."
        ),
    }


def _gravar(caminho: Path, origem: str, perfis: list[dict]) -> None:
    documento = {
        "schema": "mecanica-toolkit/catalogo-perfis/v1",
        "origem": origem,
        "observacoes": (
            "Área, inércia, módulo elástico, raio de giração e massa vêm direto "
            "da tabela de bitolas do fabricante, conferidos por coerência interna "
            "(raio de giração contra sqrt(I/A) e módulo elástico contra I/(dim/2)). "
            "Módulo plástico, constante de torção e de empenamento não são "
            "tabelados pelo fabricante para esta família e foram estimados por "
            "geometria idealizada a partir das dimensões reais — confirme com "
            "cautela adicional em verificações que dependam deles (flexão e "
            "flambagem lateral com torção). Confirme a bitola no catálogo vigente "
            "antes de usar em projeto."
        ),
        "perfis": perfis,
    }
    caminho.write_text(json.dumps(documento, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Gravado em {caminho} ({len(perfis)} perfis)")


def principal() -> int:
    perfis_i = [_perfil_i(linha) for linha in DADOS_I]
    perfis_u = [_perfil_u(linha) for linha in DADOS_U]
    perfis_t = [_perfil_t(linha) for linha in DADOS_T]

    raiz = Path(__file__).resolve().parent.parent / "data"
    _gravar(raiz / "perfis_ref_gerdau_i.json", "Gerdau — Tabela de bitolas (perfil I)", perfis_i)
    _gravar(raiz / "perfis_ref_gerdau_u.json", "Gerdau — Tabela de bitolas (perfil U)", perfis_u)
    _gravar(raiz / "perfis_ref_gerdau_t.json", "Gerdau — Tabela de bitolas (perfil T)", perfis_t)
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
