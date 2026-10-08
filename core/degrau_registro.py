"""Registro técnico, tabelas e CSV do degrau de escada em grade (memorial e exportações).

Monta, a partir de :class:`core.degrau_escada.ResultadoEscada`, o registro que a página grava no
projeto: as entradas, a tabela de verificações (o memorial a mostra como "o que passou / o que não
passou", com o item da norma em cada linha), as tabelas de geometria, de dimensionamento do modelo
adotado e do catálogo, e o texto de destaque. Sem Streamlit.
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Mapping, Sequence
from typing import Any

from core import degrau_escada as de
from core.technical_records import criar_registro_tecnico
from core.verificacao import STATUS_REGISTRO, linhas_para_registro, numero_json

MODULO_ID = "degrau_escada"
MODULO_TITULO = "Degrau de escada em grade"
LARGURA_UTIL_DXA = 9360  # largura útil do memorial, em vinte avos de ponto

REFERENCIAS = [
    "NR-12, Anexo III — escadas, rampas e passarelas.",
    "NR-22, itens 22.6.5, 22.9.3 e 22.10 — mineração (Portaria MTE 105/2026).",
    "Critério de Projeto Anglo American AA-BR-DPST-DR-0001 Rev.1 (22/12/2025).",
    "ABNT NBR 8800:2008 — projeto de estruturas de aço (5.4, Anexo G e 6.3.3.2).",
    "ABNT NBR 6120 — ações para o cálculo de estruturas (degraus isolados).",
    "ISO 14122-3 — meios de acesso permanente a máquinas: escadas e guarda-corpos.",
    'Catálogo Selmec "Degraus" (DS) — dimensões, furação e larguras recomendadas.',
]

AVISOS_FIXOS = (
    "O catálogo não informa a carga-base das larguras recomendadas: o programa exige a largura "
    "do catálogo e o cálculo atendidos ao mesmo tempo.",
    "A chapa xadrez do bocel não foi considerada na distribuição da carga (a favor da segurança).",
    "O peso é uma estimativa (barra de ligação com lado adotado, mais 20 % do catálogo).",
    "Conferir os desenhos-padrão Anglo AA-BR-DPST-ES-0001 a 0004 (Anglo 8.4 e 10.2).",
    "Item da NBR 6120 da carga de 2,5 kN a conferir na edição 2019 (o 2.2.1.7 é da edição 1980).",
    "Aço inoxidável está fora do escopo da NBR 8800: os valores de fy e E são indicativos.",
)

NAO_FAZ = (
    "Longarina, patamar e ligações da longarina.",
    "Guarda-corpo: o programa só confere as dimensões informadas.",
    "Pressão de contato do parafuso na chapa lateral: o catálogo não informa a espessura.",
)

CONFLITOS_ENTRE_NORMAS = (
    "NR-22 (espelho de 180 a 200 mm) × Anglo (160 a 180 mm): só h = 180 mm atende aos dois.",
    "NR-12 item 12 (com espelho, h de 200 a 250 mm) × Anglo: sem interseção.",
    "Guarda-corpo NR (1,10 a 1,20 m) × Anglo (≥ 1,30 m).",
    'Parafuso Anglo ≥ 5/8" × furo padrão Selmec 9/16" (só aceita 1/2").',
    "Catálogo (C ≤ 300 mm) × Anglo: exige h ≥ 175 mm.",
)


def _larguras(pesos: Sequence[int]) -> list[int]:
    total = sum(pesos)
    larguras = [round(LARGURA_UTIL_DXA * p / total) for p in pesos]
    larguras[-1] += LARGURA_UTIL_DXA - sum(larguras)
    return larguras


def _n(valor: float, casas: int = 2) -> str:
    return de.numero_pt(valor, casas)


def _finito(valor: float, casas: int = 4) -> float | str:
    return numero_json(valor, casas) if math.isfinite(valor) else "—"


#: Colunas da tabela de verificações da página, do PDF e do CSV (seção 7 da especificação).
COLUNAS_VERIFICACAO = (
    "Verificação",
    "Norma/item",
    "Valor",
    "Limite",
    "Aproveitamento (%)",
    "Status",
    "Observação",
)


def _numero_da_tabela(valor: float | None, unidade: str) -> str:
    if valor is None:
        return "—"
    if math.isinf(valor):
        return "∞"
    texto = de.numero_pt(valor, 3)
    return f"{texto} {unidade}" if unidade not in ("", "—", "-") else texto


def tabela_de_verificacoes(r: de.ResultadoEscada) -> list[dict[str, Any]]:
    """As 38 verificações com Valor, Limite e Aproveitamento; ``None`` onde não se aplica."""
    return [
        {
            "Verificação": v.nome,
            "Norma/item": v.referencia,
            "Valor": _numero_da_tabela(v.valor, v.unidade),
            "Limite": _numero_da_tabela(v.limite, v.unidade),
            "Aproveitamento (%)": None if v.aproveitamento is None else 100.0 * v.aproveitamento,
            "Status": v.status,
            "Observação": v.formula,
        }
        for v in r.verificacoes
    ]


def csv_das_verificacoes(r: de.ResultadoEscada) -> bytes:
    """CSV (UTF-8 com BOM, abre direto no Excel) com as 38 verificações e a unidade."""
    saida = io.StringIO()
    escritor = csv.writer(saida, lineterminator="\r\n")
    escritor.writerow(
        [*COLUNAS_VERIFICACAO[:4], "Unidade", *COLUNAS_VERIFICACAO[4:]],
    )
    for v in r.verificacoes:
        escritor.writerow(
            [
                v.nome,
                v.referencia,
                "" if v.valor is None else f"{v.valor:.4f}",
                "" if v.limite is None else f"{v.limite:.4f}",
                v.unidade if v.unidade != "—" else "",
                "" if v.aproveitamento is None else f"{100.0 * v.aproveitamento:.1f}",
                v.status,
                v.formula,
            ]
        )
    return saida.getvalue().encode("utf-8-sig")


# ---------------------------------------------------------------------------------------------
# Tabelas
# ---------------------------------------------------------------------------------------------
def linhas_do_catalogo(r: de.ResultadoEscada) -> list[dict[str, Any]]:
    """Os 64 modelos, uma linha cada (valores numéricos), com o adotado marcado."""
    adotado = r.adotado.modelo.nome
    linhas: list[dict[str, Any]] = []
    for x in r.tabela_modelos:
        m = x.modelo
        linhas.append(
            {
                "Modelo": m.nome,
                "Malha p (mm)": m.p_mm,
                "Barras de ligação s (mm)": m.s_mm,
                "Barra h × t (mm)": f"{m.h_b_mm} x {de.numero_pt_fixo(m.t_b_mm)}",
                "L máx recomendado (mm)": m.L_max_mm,
                "n_bb": x.n_bb,
                "n_ef": x.n_ef,
                "λ": x.lam,
                "λp": x.lam_p,
                "λr": x.lam_r,
                "M_Rd (kN·m)": x.MRd_kNm,
                "Peso do degrau (kg)": x.peso_degrau_kg,
                "u flexão distribuída": x.u_flex_d,
                "u flexão concentrada": x.u_flex_c,
                "u cisalhamento": x.u_cis,
                "u flecha distribuída": x.u_fl_d,
                "u flecha ISO": x.u_fl_i,
                "u máx": x.u_max,
                "Atende": "SIM" if x.atende else "NÃO",
                "Na preferência": "SIM" if x.na_preferencia else "NÃO",
                "Adotado": "ADOTADO" if m.nome == adotado else "",
            }
        )
    return linhas


def csv_do_catalogo(r: de.ResultadoEscada) -> bytes:
    """CSV (UTF-8 com BOM, abre direto no Excel) com os 64 modelos."""
    linhas = linhas_do_catalogo(r)
    saida = io.StringIO()
    escritor = csv.writer(saida, lineterminator="\r\n")
    cabecalho = list(linhas[0])
    escritor.writerow(cabecalho)
    for linha in linhas:
        escritor.writerow(
            [f"{v:.4f}" if isinstance(v, float) else v for v in (linha[c] for c in cabecalho)]
        )
    return saida.getvalue().encode("utf-8-sig")


def linhas_da_geometria(r: de.ResultadoEscada) -> list[list[str]]:
    """Geometria da escada: grandeza, valor, unidade, cálculo e referência."""
    e, g, ln, lg = r.entrada, r.geometria, r.lances, r.larguras
    f = g.faixa
    faixa_legal = (
        f"{_n(f.hL_min, 0)} a {_n(f.hL_max, 0)} mm" if f.hL_min > 0 else f"até {_n(f.hL_max, 0)} mm"
    )
    return [
        [
            "Nível de atendimento do espelho",
            str(f.nivel),
            "-",
            f"{f.mensagem}. Faixa legal do espelho: {faixa_legal}.",
        ],
        [
            "Nº de espelhos n",
            str(g.n),
            "-",
            f"automático {f.n_auto}" + (f"; imposto {e.n_imposto}" if e.n_imposto else ""),
        ],
        ["Espelho h", _n(g.h_mm), "mm", f"H/n = {_n(e.H_mm, 0)}/{g.n}"],
        [
            "Piso b",
            _n(g.b_mm),
            "mm",
            "imposto"
            if e.b_imposto_mm is not None
            else "menor múltiplo de 5 mm que cumpre Anglo 10.2 e a norma legal",
        ],
        ["Blondel 2h + b", _n(g.blondel_mm), "mm", "Anglo 10.2: 630 a 640 mm"],
        ["Inclinação α", _n(g.alfa_graus, 3), "°", "atan(h/b)"],
        [
            "Profundidade do degrau C",
            _n(g.C_mm),
            "mm",
            "imposta"
            if e.C_imposto_mm is not None
            else "C ≥ b + 20 (Anglo 10.2), série do catálogo",
        ],
        ["Furação F da chapa lateral", str(g.F_mm), "mm", "Selmec, tabela C × F"],
        ["Sobreposição r = C − b", _n(g.r_mm), "mm", "NR-12 Anexo III 11 f)"],
        [
            "Distribuição dos lances",
            ln.texto,
            "-",
            f"até {_n(ln.altura_max_lance_mm, 0)} mm por lance",
        ],
        [
            "Degraus em grade",
            str(ln.n_degraus_grade),
            "-",
            "n − nº de lances (o último espelho chega ao patamar)",
        ],
        ["Projeção horizontal total", _n(ln.projecao_total_mm, 0), "mm", "degraus × b + patamares"],
        [
            "Largura útil",
            _n(lg.util_mm, 0),
            "mm",
            f"mínimo legal {_n(lg.minima_legal_mm, 0)} mm; mínimo Anglo {_n(lg.minima_anglo_mm, 0)} mm",
        ],
    ]


def linhas_do_dimensionamento(r: de.ResultadoEscada) -> list[list[str]]:
    """Memorial do modelo adotado: propriedades da barra, FLT, cargas, esforços, flechas, parafuso."""
    a, e, rp = r.adotado, r.entrada, r.reacoes
    m = a.modelo
    mat = r.material
    return [
        [
            "Barra portante",
            f"{m.h_b_mm} x {de.numero_pt_fixo(m.t_b_mm)}",
            "mm",
            f"passo p = {_n(m.p_mm, 0)} mm; barras de ligação a cada s = {_n(m.s_mm, 0)} mm",
        ],
        [
            "Material",
            mat.nome,
            "-",
            f"fy = {_n(mat.fy, 0)} MPa; E = {_n(mat.E, 0)} MPa; ρ = {_n(mat.rho, 0)} kg/m³",
        ],
        ["Barras na profundidade n_bb", str(a.n_bb), "-", "int((C − t)/p) + 1"],
        [
            "Barras sob a carga concentrada n_ef",
            str(a.n_ef),
            "-",
            "mín(n_bb; int(b_c/p) + 1); modelo de grelha, a favor da segurança",
        ],
        ["Área A", _n(a.area_mm2, 1), "mm²", "h·t"],
        ["Inércia I", _n(a.inercia_mm4, 1), "mm⁴", "t·h³/12"],
        ["Módulo elástico W", _n(a.W_mm3, 1), "mm³", "t·h²/6"],
        ["Módulo plástico Z", _n(a.Z_mm3, 1), "mm³", "t·h²/4"],
        ["Constante de torção J", _n(a.J_mm4, 1), "mm⁴", "h·t³/3·(1 − 0,63·t/h)"],
        ["Raio de giração r_y", _n(a.r_y_mm, 3), "mm", "t/√12"],
        ["Esbeltez λ", _n(a.lam, 2), "-", "L_b / r_y, com L_b = s"],
        ["Esbeltez limite λp", _n(a.lam_p, 2), "-", "0,13·E·√(J·A)/M_pl (NBR 8800 Tab. G.1)"],
        ["Esbeltez limite λr", _n(a.lam_r, 2), "-", "2,00·E·√(J·A)/M_r (NBR 8800 Tab. G.1)"],
        ["Momento de plastificação M_pl", _n(a.Mpl_Nmm / 1e6, 4), "kN·m", "Z·fy"],
        ["Momento de início de escoamento M_r", _n(a.Mr_Nmm / 1e6, 4), "kN·m", "W·fy"],
        ["Regime da FLT", a.regime_flt, "-", f"C_b = {_n(e.Cb, 2)}"],
        [
            "M_Rk por barra",
            _n(a.MRk_Nmm / 1e6, 4),
            "kN·m",
            "NBR 8800 Tab. G.1, seção sólida retangular",
        ],
        ["M_Rd por barra", _n(a.MRd_kNm, 4), "kN·m", f"M_Rk/γa1, γa1 = {_n(e.gamma_a1, 2)}"],
        ["V_Rd por barra", _n(a.VRd_kN, 3), "kN", "0,60·A·fy/γa1 (NBR 8800 5.4.3)"],
        [
            "Peso da grade",
            _n(a.peso_grade_kg_m2, 3),
            "kg/m²",
            f"(h·t/p + a²/s)·ρ, a = {_n(e.lado_barra_ligacao_mm, 1)} mm (adotado)",
        ],
        [
            "Peso próprio g",
            _n(a.g_kN_m2, 4),
            "kN/m²",
            "peso da grade × 1,20 (Selmec nota 4) × 9,81",
        ],
        [
            "Carga distribuída de cálculo w",
            _n(a.w_d_kN_m, 4),
            "kN/m",
            f"(γg·g + γq·q)·C = ({_n(e.gamma_g)}·{_n(a.g_kN_m2, 4)} + {_n(e.gamma_q)}·{_n(e.q_kN_m2)})·{_n(a.C_mm, 0)}/1000",
        ],
        [
            "M_Sd, carga distribuída",
            _n(a.M_sd_d_kNm, 4),
            "kN·m",
            f"w·L²/8; u = {_n(a.u_flex_d, 4)}",
        ],
        [
            "Carga concentrada de cálculo P_d",
            _n(a.P_d_kN, 3),
            "kN",
            f"γq·P = {_n(e.gamma_q)}·{_n(e.P_kN)}",
        ],
        [
            "M_Sd, carga concentrada",
            _n(a.M_sd_c_kNm, 4),
            "kN·m",
            f"P_d·L/4 + peso das n_ef barras; u = {_n(a.u_flex_c, 4)}",
        ],
        ["V_Sd por barra", _n(a.V_sd_kN, 3), "kN", f"P_d/n_ef + peso/2; u = {_n(a.u_cis, 4)}"],
        [
            "Flecha, carga distribuída",
            _n(a.delta_d_mm, 3),
            "mm",
            f"limite L/{_n(e.flecha_div, 0)} = {_n(a.limite_d_mm, 3)} mm; u = {_n(a.u_fl_d, 4)}",
        ],
        [
            "Flecha ISO 14122-3",
            _n(a.delta_iso_mm, 3),
            "mm",
            f"P = {_n(e.P_iso_kN)} kN; limite {_n(a.limite_iso_mm, 3)} mm; u = {_n(a.u_fl_i, 4)}",
        ],
        [
            "Reação característica R_g + R_q",
            f"{_n(rp.R_g_kN, 4)} + {_n(rp.R_q_kN, 4)}",
            "kN",
            "por chapa lateral",
        ],
        [
            "Reação de cálculo R_d",
            _n(rp.R_d_kN, 4),
            "kN",
            "maior entre γg·R_g + γq·R_q e γg·R_g + γq·P",
        ],
        [
            f"Parafuso A307 {rp.parafuso}",
            _n(rp.F_vRd_kN, 3),
            "kN",
            f"F_v,Rd = 0,40·A_b·f_ub/γa2; {rp.n_parafusos} por lado, u = {_n(rp.u_par, 4)}",
        ],
    ]


def tabelas_para_memorial(r: de.ResultadoEscada) -> list[dict[str, Any]]:
    """As tabelas prontas que o memorial imprime depois de "O que passou"."""
    grandezas = _larguras([34, 18, 8, 40])
    adotado = r.adotado
    atendem = sorted(
        (x for x in r.tabela_modelos if x.atende),
        key=lambda x: (x.peso_degrau_kg, x.modelo.nome),
    )
    # Até 12 linhas: os mais leves que atendem; o adotado sempre aparece (a preferência, a
    # escolha manual ou a falta de modelo que atenda o põem fora dos 12 mais leves).
    mostrados = atendem[:12]
    if adotado.modelo.nome not in {x.modelo.nome for x in mostrados}:
        mostrados = [*mostrados[:11], adotado] if len(mostrados) >= 12 else [*mostrados, adotado]
    catalogo = {
        "legenda": (
            "Modelos do catálogo que atendem ao cálculo e à largura recomendada, do mais leve ao "
            f"mais pesado (até 12 de {len(r.tabela_modelos)}), e o adotado; u máx é o maior "
            "aproveitamento das cinco verificações do degrau."
        ),
        "cabecalhos": ["Modelo", "Peso (kg)", "u máx", "Atende", "Na preferência", "Adotado"],
        "linhas": [
            [
                x.modelo.nome,
                _n(x.peso_degrau_kg, 3),
                _n(x.u_max, 3),
                "sim" if x.atende else "não",
                "sim" if x.na_preferencia else "não",
                "adotado" if x.modelo.nome == adotado.modelo.nome else "",
            ]
            for x in sorted(mostrados, key=lambda x: (x.peso_degrau_kg, x.modelo.nome))
        ],
        "larguras": _larguras([26, 16, 14, 14, 16, 14]),
        "fonte": 7.2,
    }
    return [
        {
            "legenda": "Geometria da escada: espelho, piso, profundidade, lances e largura.",
            "cabecalhos": ["Grandeza", "Valor", "Un.", "Cálculo"],
            "linhas": linhas_da_geometria(r),
            "larguras": grandezas,
            "fonte": 7.2,
        },
        {
            "legenda": (
                f"Dimensionamento do modelo adotado ({adotado.modelo.nome}): propriedades da barra, flambagem "
                "lateral com torção, cargas, esforços, flechas, reações e parafuso."
            ),
            "cabecalhos": ["Grandeza", "Valor", "Un.", "Cálculo"],
            "linhas": linhas_do_dimensionamento(r),
            "larguras": grandezas,
            "fonte": 7.0,
        },
        catalogo,
        {
            "legenda": "Texto para a requisição de compra (nota 1 do catálogo Selmec).",
            "cabecalhos": ["Descrição do item"],
            "linhas": [[r.especificacao]],
            "larguras": [LARGURA_UTIL_DXA],
            "fonte": 7.4,
        },
    ]


# ---------------------------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------------------------
def _entradas(r: de.ResultadoEscada, contexto: Mapping[str, Any] | None) -> dict[str, Any]:
    e = r.entrada
    entradas: dict[str, Any] = {
        "enquadramento": de.ENQUADRAMENTOS[e.enquadramento],
        "espelho_fechado": e.espelho_fechado,
        "uso": de.USOS[e.uso],
        "desnivel_H_mm": e.H_mm,
        "espelho_alvo_mm": e.h_alvo_mm,
        "n_espelhos_imposto": e.n_imposto,
        "piso_b_imposto_mm": e.b_imposto_mm,
        "profundidade_C_imposta_mm": e.C_imposto_mm,
        "C_padronizado": e.C_padronizado,
        "comprimento_L_mm": e.L_mm,
        "reducao_da_largura_util_mm": e.reducao_largura_mm,
        "altura_max_lance_imposta_mm": e.altura_max_lance_imposta_mm,
        "patamar_mm": e.patamar_mm,
        "selecao_do_modelo": "Manual" if e.selecao == de.SELECAO_MANUAL else "Automática",
        "malha_preferida": e.malha_preferida
        if e.malha_preferida == de.QUALQUER
        else de.MALHAS[e.malha_preferida],
        "ligacao_preferida": e.ligacao_preferida
        if e.ligacao_preferida == de.QUALQUER
        else de.LIGACOES[e.ligacao_preferida],
        "modelo_manual": e.modelo_manual if e.selecao == de.SELECAO_MANUAL else None,
        "superficie": de.SUPERFICIES[e.superficie],
        "chapa_xadrez_no_bocel": e.chapa_xadrez,
        "acabamento": de.ACABAMENTOS[e.acabamento],
        "material": e.material,
        "lado_barra_ligacao_mm": e.lado_barra_ligacao_mm,
        "parafuso": e.parafuso,
        "n_parafusos_por_lado": e.n_parafusos_por_lado,
        "sobrecarga_q_kN_m2": e.q_kN_m2,
        "carga_concentrada_P_kN": e.P_kN,
        "carga_ISO_kN": e.P_iso_kN,
        "largura_de_aplicacao_mm": e.b_c_mm,
        "n_ef_imposto": e.n_ef_imposto,
        "gamma_g": e.gamma_g,
        "gamma_q": e.gamma_q,
        "gamma_a1": e.gamma_a1,
        "gamma_a2": e.gamma_a2,
        "cb": e.Cb,
        "flecha_distribuida_L_sobre": e.flecha_div,
        "flecha_ISO_L_sobre": e.flecha_iso_div,
        "flecha_ISO_maxima_mm": e.flecha_iso_max_mm,
        "gc_travessao_superior_mm": e.gc_superior_mm,
        "gc_travessao_intermediario_mm": e.gc_intermediario_mm,
        "gc_rodape_mm": e.gc_rodape_mm,
        "gc_espacamento_mm": e.gc_espacamento_mm,
    }
    entradas.update(dict(contexto or {}))
    return {chave: valor for chave, valor in entradas.items() if valor is not None}


def texto_de_destaque(r: de.ResultadoEscada) -> str:
    g, ln, a = r.geometria, r.lances, r.adotado
    return (
        f"Degrau adotado: {a.modelo.nome} (C = {_n(g.C_mm, 0)} mm × L = {_n(r.entrada.L_mm, 0)} mm, "
        f"{_n(r.peso_unitario_kg, 2)} kg cada; {ln.n_degraus_grade} degraus, "
        f"{_n(r.peso_total_kg, 1)} kg no total). Escada de {g.n} espelhos de {_n(g.h_mm, 1)} mm e "
        f"piso de {_n(g.b_mm, 0)} mm (2h + b = {_n(g.blondel_mm, 1)} mm; α = {_n(g.alfa_graus, 1)}°), "
        f"em {ln.texto}. Verificações: {de.texto_da_contagem(r.contagem)}; maior aproveitamento "
        f"{_n(100 * r.aproveitamento_maximo, 1)} %."
    )


def registro_degrau(
    r: de.ResultadoEscada, *, contexto: Mapping[str, Any] | None = None, responsavel: str = ""
) -> dict[str, Any]:
    """Registro técnico v2 do degrau (um cálculo = um registro)."""
    e, g, ln, a = r.entrada, r.geometria, r.lances, r.adotado
    verificacoes = list(r.verificacoes)
    geral = r.status
    destaque = texto_de_destaque(r)
    tag = str((contexto or {}).get("tag") or "").strip()
    resultados: dict[str, Any] = {
        "status_geral": geral,
        "verificações": linhas_para_registro(verificacoes),
        "utilizacao_maxima": _finito(r.aproveitamento_maximo),
        "destaque_memorial": destaque,
        "tabelas_memorial": tabelas_para_memorial(r),
        "modelo_adotado": a.modelo.nome,
        "número_de_espelhos": g.n,
        "espelho_h_mm": _finito(g.h_mm, 3),
        "piso_b_mm": _finito(g.b_mm, 2),
        "inclinação_graus": _finito(g.alfa_graus, 3),
        "profundidade_C_mm": _finito(g.C_mm, 1),
        "furação_F_mm": g.F_mm,
        "distribuição_dos_lances": ln.texto,
        "degraus_em_grade": ln.n_degraus_grade,
        "projeção_horizontal_total_mm": _finito(ln.projecao_total_mm, 1),
        "peso_unitário_kg": _finito(r.peso_unitario_kg, 3),
        "peso_total_kg": _finito(r.peso_total_kg, 2),
    }
    alertas = [f"{v.nome}: {v.formula}" for v in verificacoes if v.status in ("NÃO OK", "ALERTA")]
    alertas.extend(r.avisos)
    alertas.extend(AVISOS_FIXOS)
    alertas.extend(f"Não faz: {item}" for item in NAO_FAZ)
    nome_peca = f" {tag}" if tag else ""
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=(
            f"Degrau de escada{nome_peca} — {a.modelo.nome}, H = {_n(e.H_mm, 0)} mm "
            f"({g.n} espelhos)"
        ),
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=(
            f"Degrau de escada em grade eletrofundida {a.modelo.nome}: {g.n} espelhos de "
            f"{_n(g.h_mm, 1)} mm, piso {_n(g.b_mm, 0)} mm, C = {_n(g.C_mm, 0)} mm, L = "
            f"{_n(e.L_mm, 0)} mm; {de.texto_da_contagem(r.contagem)}."
        ),
        entradas=_entradas(r, contexto),
        resultados=resultados,
        metodo=(
            "Geometria da escada pelo requisito legal (NR-12 Anexo III ou NR-22), pelo Critério "
            "Anglo (espelho 160 a 180 mm, Blondel 630 a 640 mm) e pelo limite do catálogo Selmec "
            "(C ≤ 300 mm), nessa ordem de prioridade; degrau biapoiado nas chapas laterais, com "
            "flexão (flambagem lateral com torção, NBR 8800 Tab. G.1), cisalhamento, flechas e "
            "parafusos A307; 64 modelos avaliados e o mais leve que atende é adotado."
        ),
        premissas=[
            "Vão do degrau = L, biapoiado nas chapas laterais; as barras de ligação travam o "
            "bordo comprimido (L_b = passo s das barras de ligação).",
            "Sobrecarga distribuída q em todas as barras; carga concentrada P junto ao bocel "
            "sobre n_ef barras, sem somar à distribuída.",
            "n_ef = int(b_c/p) + 1, limitado a n_bb: o modelo de grelha deu 4,0 a 4,9 barras efetivas "
            "na malha 30 e 3,0 a 3,2 na malha 41, então o valor adotado é igual ou menor.",
            "A chapa xadrez do bocel não entra na distribuição da carga (a favor da segurança).",
            "Peso da grade: barras portantes e barras de ligação de lado adotado, mais 20 % "
            "(Selmec nota 4); é estimativa.",
        ],
        equacoes=[
            "n_bb = int((C − t)/p) + 1; n_ef = mín(n_bb; int(b_c/p) + 1)",
            "λp = 0,13·E·√(J·A)/M_pl; λr = 2,00·E·√(J·A)/M_r; M_cr = 2,00·C_b·E·√(J·A)/λ",
            "M_Rk = M_pl (λ ≤ λp); M_pl − (M_pl − M_r)·(λ − λp)/(λr − λp) (λp < λ ≤ λr); "
            "mín(M_pl; M_cr) (λ > λr); M_Rd = M_Rk/γa1",
            "ELU distribuída: (γg·g + γq·q)·C·L²/8 ≤ n_bb·M_Rd",
            "ELU concentrada: γq·P·L/4 + γg·g·C·L²/8·n_ef/n_bb ≤ n_ef·M_Rd",
            "V_Rd = 0,60·A·fy/γa1",
            "δ = 5·(g + q)·C·L⁴/(384·E·n_bb·I) ≤ L/300; δ_ISO = P·L³/(48·E·n_ef·I) ≤ "
            "mín(L/300; 6 mm)",
            "F_v,Rd = 0,40·A_b·f_ub/γa2",
        ],
        criterios=[
            "Espelho, piso, largura, lances, patamar e inclinação: NR-12 Anexo III (itens 11 e 12) "
            "ou NR-22 (22.10.1.1); Critério Anglo 10.2.",
            "Degrau: u = solicitante/resistente ≤ 1 em flexão, cisalhamento e flechas; "
            'parafuso A307 ≥ 5/8" e no mínimo 2 por lado.',
            "Guarda-corpo: só conferência das dimensões (NR-12 Anexo III 7; NR-22 22.6.5; Anglo "
            "10.2).",
        ],
        alertas=alertas,
        referencias=REFERENCIAS,
        conclusao=destaque,
        responsavel=responsavel,
    )
