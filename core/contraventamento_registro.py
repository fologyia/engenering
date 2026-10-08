"""Registro técnico, tabelas e texto de destaque da ligação de contraventamento (UFM, DG29).

Monta, a partir de :class:`core.contraventamento_ligacao.ResultadoLigacao`, o registro que a página
grava no projeto: entradas, tabela de verificações (o memorial a mostra como "o que passou / o que
não passou", com o item da norma em cada linha), a tabela das forças nas interfaces (como a Tabela
5-1 do guia) e a da geometria do nó. Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from core import contraventamento_chapa as ch
from core import contraventamento_ligacao as lig
from core import contraventamento_ufm as ufm
from core.technical_records import criar_registro_tecnico
from core.verificacao import STATUS_REGISTRO, linhas_para_registro, numero_json, status_geral

MODULO_ID = "ligacao_contraventamento"
MODULO_TITULO = "Ligação de contraventamento (chapa de nó)"
LARGURA_UTIL_DXA = 9360

REFERENCIAS = [
    "AISC Design Guide 29 — Vertical Bracing Connections: Analysis and Design (Muir e Thornton, 2014).",
    "ANSI/AISC 360-16 — Specification for Structural Steel Buildings (seções D, E, F, J2, J3, J4 e J10).",
    "AISC Steel Construction Manual, 15ª ed., Parte 13 (Método das Forças Uniformes) e Parte 9.",
]

FORA_DO_ESCOPO = (
    "Chapa de topo parafusada na coluna e na viga (parafusos tracionados, alavanca): ver o Exemplo 5.1 do guia.",
    "A barra do contraventamento (escoamento, ruptura da seção líquida e bloco de cisalhamento da barra).",
    "Ligações não ortogonais, em treliça, em chevron e na base da coluna (Exemplos 5.9 a 5.12).",
    "Resistência sísmica e ligações com ductilidade especial (Capítulo 6 do guia).",
    "A norma brasileira: os estados-limites e os coeficientes são os do AISC 360-16 (LRFD ou ASD), não os da NBR 8800.",
)


def _larguras(pesos: Sequence[int]) -> list[int]:
    total = sum(pesos)
    larguras = [round(LARGURA_UTIL_DXA * p / total) for p in pesos]
    larguras[-1] += LARGURA_UTIL_DXA - sum(larguras)
    return larguras


def _n(valor: float, casas: int = 1) -> str:
    texto = f"{valor:.{casas}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto.replace(".", ",") or "0"


def _finito(valor: float, casas: int = 3) -> float | str:
    return numero_json(valor, casas) if math.isfinite(valor) else "—"


# ---------------------------------------------------------------------------------------------
# Tabelas
# ---------------------------------------------------------------------------------------------
def linhas_das_interfaces(r: lig.ResultadoLigacao) -> list[list[str]]:
    """Forças de cálculo em cada interface (kN e kN·m), como a Tabela 5-1 do guia."""
    f = r.forcas
    e = r.entrada
    P = max(e.P_tracao_kN, e.P_compressao_kN)
    axial_vc = f.vc_axial_kN - (r.distorcao.HD_kN if r.distorcao else 0.0)
    linhas = [
        ["Contraventamento–chapa", "0", _n(P), "0"],
        [
            "Chapa–viga",
            _n(f.viga_cisalhamento_kN),
            _n(f.viga_normal_kN),
            _n(f.viga_momento_kNm, 2),
        ],
    ]
    if e.caso != ufm.CASO_3:
        linhas.append(
            [
                "Chapa–coluna",
                _n(f.coluna_cisalhamento_kN),
                _n(f.coluna_normal_kN),
                _n(f.coluna_momento_kNm, 2),
            ]
        )
    linhas.append(["Viga–coluna", _n(f.vc_cisalhamento_kN), _n(axial_vc), _n(f.vc_momento_kNm, 2)])
    return linhas


def linhas_da_geometria(r: lig.ResultadoLigacao) -> list[list[str]]:
    """Geometria do nó: grandeza, valor, unidade e cálculo."""
    e, f, a = r.entrada, r.forcas, r.arranjo
    linhas = [
        [
            "Ângulo θ com a vertical",
            _n(e.theta_graus, 2),
            "°",
            "tanθ = deslocamento horizontal / vertical",
        ],
        ["Metade da altura da viga e_b", _n(f.entrada.eb_mm), "mm", "d/2"],
        [
            "Metade da altura da coluna e_c",
            _n(f.entrada.ec_mm),
            "mm",
            "d/2 na mesa; 0 na alma",
        ],
        [
            "α real (centroide da solda na viga)",
            _n(r.alfa_real_mm),
            "mm",
            "t_topo + (corte + l_h)/2",
        ],
        ["α̅ ideal (Eq. 4-1)", _n(f.alfa_ideal_mm), "mm", "α̅ − β̅·tanθ = e_b·tanθ − e_c"],
    ]
    if e.caso != ufm.CASO_3:
        linhas += [
            ["β real (centroide da solda na coluna)", _n(r.beta_real_mm), "mm", "(corte + l_v)/2"],
            ["β̅ ideal (Eq. 4-1)", _n(f.beta_ideal_mm), "mm", "(α̅ + e_c)/tanθ − e_b"],
        ]
    linhas += [
        ["r", _n(f.r_mm), "mm", "√((α̅ + e_c)² + (β̅ + e_b)²)"],
        [
            "Solda chapa–viga: comprimento",
            _n(r.comprimento_da_solda_na_viga_mm),
            "mm",
            "l_h − corte",
        ],
    ]
    if e.caso != ufm.CASO_3:
        linhas.append(
            [
                "Solda chapa–coluna: comprimento",
                _n(r.comprimento_da_solda_na_coluna_mm),
                "mm",
                "l_v − corte",
            ]
        )
    linhas += [
        [
            "Parafusos do contraventamento",
            f"{a.fileiras} × {a.por_fileira}",
            "-",
            f"{e.designacao_do_parafuso} {e.grau_do_parafuso}, passo {_n(a.passo_mm)} mm, gabarito "
            f"{_n(a.gabarito_mm)} mm, extremidade {_n(a.extremidade_mm)} mm",
        ],
        ["Largura de Whitmore l_w", _n(r.largura_de_whitmore_mm), "mm", "g + 2·L·tan30°"],
        [
            "Área efetiva de Whitmore A_w",
            _n(r.area_de_whitmore_mm2),
            "mm²",
            "l_w·t (com a alma da viga, se entra nela)",
        ],
        [
            "Nº mínimo de parafusos",
            _n(r.numero_minimo_de_parafusos),
            "-",
            "P / (resistência do parafuso interno)",
        ],
    ]
    return linhas


def tabelas_para_memorial(r: lig.ResultadoLigacao) -> list[dict[str, Any]]:
    forcas = {
        "legenda": (
            "Forças de cálculo em cada interface do nó (UFM): cisalhante (ao longo da borda), normal "
            "(perpendicular à borda) e momento. Mesmos sinais do guia para contraventamento em tração."
        ),
        "cabecalhos": ["Interface", "Cisalhante (kN)", "Normal (kN)", "Momento (kN·m)"],
        "linhas": linhas_das_interfaces(r),
        "larguras": _larguras([34, 22, 22, 22]),
        "fonte": 7.4,
    }
    geometria = {
        "legenda": "Geometria do nó, da chapa e dos parafusos.",
        "cabecalhos": ["Grandeza", "Valor", "Un.", "Cálculo"],
        "linhas": linhas_da_geometria(r),
        "larguras": _larguras([36, 14, 6, 44]),
        "fonte": 7.2,
    }
    return [forcas, geometria]


# ---------------------------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------------------------
def _entradas(r: lig.ResultadoLigacao, contexto: Mapping[str, Any] | None) -> dict[str, Any]:
    e = r.entrada
    viga, coluna = e.perfil_viga, e.perfil_coluna
    entradas: dict[str, Any] = {
        "metodo": ch.METODOS[e.metodo],
        "forca_de_tracao_kN": e.P_tracao_kN,
        "forca_de_compressao_kN": e.P_compressao_kN,
        "theta_graus": e.theta_graus,
        "caso_do_UFM": ufm.CASOS[e.caso],
        "ajuste_de_alfa_e_beta": ufm.AJUSTES[e.ajuste] if e.caso != ufm.CASO_3 else None,
        "viga": viga.nome,
        "fy_da_viga_MPa": viga.Fy_MPa,
        "coluna": coluna.nome,
        "fy_da_coluna_MPa": coluna.Fy_MPa,
        "ligacao_na_mesa_da_coluna": e.ligacao_na_mesa_da_coluna,
        "reacao_da_viga_kN": e.reacao_viga_kN,
        "transferencia_kN": e.transferencia_kN,
        "x_do_ponto_de_trabalho_mm": e.x_mm if e.caso == ufm.CASO_1 else None,
        "y_do_ponto_de_trabalho_mm": e.y_mm if e.caso == ufm.CASO_1 else None,
        "delta_Vb_kN": e.delta_Vb_kN if e.caso == ufm.CASO_2 and not e.anular_Vb else None,
        "anular_toda_a_vertical_da_viga": e.anular_Vb if e.caso == ufm.CASO_2 else None,
        "t_da_chapa_mm": e.t_chapa_mm,
        "fy_da_chapa_MPa": e.Fy_chapa_MPa,
        "fu_da_chapa_MPa": e.Fu_chapa_MPa,
        "lh_da_chapa_mm": e.lh_mm,
        "corte_horizontal_mm": e.corte_h_mm,
        "lv_da_chapa_mm": e.lv_mm if e.caso != ufm.CASO_3 else None,
        "corte_vertical_mm": e.corte_v_mm if e.caso != ufm.CASO_3 else None,
        "t_da_chapa_de_topo_mm": e.t_chapa_de_topo_mm,
        "parafuso": e.designacao_do_parafuso,
        "grau_do_parafuso": e.grau_do_parafuso,
        "rosca_no_plano_de_corte": e.rosca_no_plano,
        "planos_de_corte": e.planos_de_corte,
        "fileiras_de_parafusos": e.fileiras,
        "parafusos_por_fileira": e.por_fileira,
        "passo_mm": e.passo_mm,
        "gabarito_mm": e.gabarito_mm,
        "extremidade_mm": e.extremidade_mm,
        "t_da_barra_mm": e.t_barra_mm if e.t_barra_mm > 0 else None,
        "comprimento_livre_da_chapa_mm": e.comprimento_de_flambagem_mm
        if e.comprimento_de_flambagem_mm > 0
        else None,
        "K_da_flambagem": e.K_flambagem,
        "trecho_de_whitmore_na_alma_mm": e.trecho_whitmore_na_alma_mm
        if e.trecho_whitmore_na_alma_mm > 0
        else None,
        "FEXX_MPa": e.FEXX_MPa,
        "perna_da_solda_na_viga_mm": e.perna_na_viga_mm,
        "perna_da_solda_na_coluna_mm": e.perna_na_coluna_mm if e.caso != ufm.CASO_3 else None,
        "fator_de_ductilidade_da_solda": e.fator_de_ductilidade,
        "considerar_distorcao": e.considerar_distorcao,
    }
    entradas.update(dict(contexto or {}))
    return {chave: valor for chave, valor in entradas.items() if valor is not None}


def texto_de_destaque(r: lig.ResultadoLigacao) -> str:
    e, f = r.entrada, r.forcas
    P = max(e.P_tracao_kN, e.P_compressao_kN)
    partes = [
        f"Contraventamento com P = {_n(P, 0)} kN a {_n(e.theta_graus, 1)}° da vertical; {ufm.CASOS[e.caso].lower()}.",
        f"Chapa–viga: cisalhante {_n(f.viga_cisalhamento_kN, 0)} kN e normal {_n(f.viga_normal_kN, 0)} kN.",
    ]
    if e.caso != ufm.CASO_3:
        partes.append(
            f"Chapa–coluna: cisalhante {_n(f.coluna_cisalhamento_kN, 0)} kN e normal {_n(f.coluna_normal_kN, 0)} kN."
        )
    partes.append(
        f"Viga–coluna: cisalhante {_n(f.vc_cisalhamento_kN, 0)} kN. Maior aproveitamento: "
        f"{_n(100 * r.aproveitamento_maximo, 1)} %."
    )
    return " ".join(partes)


def registro_ligacao(
    r: lig.ResultadoLigacao, *, contexto: Mapping[str, Any] | None = None, responsavel: str = ""
) -> dict[str, Any]:
    """Registro técnico v2 da ligação (um cálculo = um registro)."""
    e, f = r.entrada, r.forcas
    verificacoes = list(r.verificacoes)
    geral = status_geral(verificacoes)
    destaque = texto_de_destaque(r)
    P = max(e.P_tracao_kN, e.P_compressao_kN)
    tag = str((contexto or {}).get("tag") or "").strip()
    nome_peca = f" {tag}" if tag else ""
    resultados: dict[str, Any] = {
        "status_geral": geral,
        "verificações": linhas_para_registro(verificacoes),
        "utilizacao_maxima": _finito(r.aproveitamento_maximo, 4),
        "destaque_memorial": destaque,
        "tabelas_memorial": tabelas_para_memorial(r),
        "forcas_do_UFM": {
            "alfa_ideal_mm": _finito(f.alfa_ideal_mm, 2),
            "beta_ideal_mm": _finito(f.beta_ideal_mm, 2),
            "r_mm": _finito(f.r_mm, 2),
            "H_b_kN": _finito(f.Hb_kN),
            "V_b_kN": _finito(f.Vb_kN),
            "H_c_kN": _finito(f.Hc_kN),
            "V_c_kN": _finito(f.Vc_kN),
        },
    }
    alertas = [f"{v.nome}: {v.formula}" for v in verificacoes if v.status in ("NÃO OK", "ALERTA")]
    alertas.extend(r.avisos)
    alertas.extend(f"Fora do escopo: {item}" for item in FORA_DO_ESCOPO)
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=(
            f"Ligação de contraventamento{nome_peca} — P = {_n(P, 0)} kN a {_n(e.theta_graus, 0)}° "
            f"({ufm.CASOS[e.caso].split(' (')[0].lower()})"
        ),
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=(
            f"Ligação de contraventamento em canto por chapa de nó de {_n(e.t_chapa_mm, 0)} mm, "
            f"pelo Método das Forças Uniformes do AISC DG29: P = {_n(P, 0)} kN, viga {e.perfil_viga.nome}, "
            f"coluna {e.perfil_coluna.nome}; aproveitamento máximo {_n(100 * r.aproveitamento_maximo, 1)} %."
        ),
        entradas=_entradas(r, contexto),
        resultados=resultados,
        metodo=(
            "Forças nas interfaces pelo Método das Forças Uniformes (DG29, seção 4.2): sem momento nas "
            "interfaces quando α̅ − β̅·tanθ = e_b·tanθ − e_c; casos especiais 1 (ponto de trabalho no "
            "canto), 2 (menos vertical na viga) e 3 (chapa só na viga). Verificações pelo AISC 360-16: "
            "parafusos J3, seção de Whitmore e bloco de cisalhamento J4, soldas J2.4 e alma da viga e "
            "da coluna J10."
        ),
        premissas=[
            "Nó em canto ortogonal com chapa de nó soldada à viga e à coluna e contraventamento parafusado à chapa.",
            "Contraventamento reversível: as forças das interfaces valem para tração e compressão (sinais invertem).",
            "O programa não vê o desenho: Whitmore, comprimento livre da chapa, folgas e distâncias mínimas precisam ser conferidos.",
            "Solda direta à viga e à coluna projetada para o maior entre a tensão de pico e 1,25 da média (DG29, p. 57).",
            "Estados-limites e coeficientes do AISC 360-16 (LRFD: φ·R_n; ASD: R_n/Ω).",
        ],
        equacoes=[
            "r = √((α̅ + e_c)² + (β̅ + e_b)²); H_b = α̅·P/r; V_b = e_b·P/r; V_c = β̅·P/r; H_c = e_c·P/r",
            "α̅ − β̅·tanθ = e_b·tanθ − e_c (Eq. 4-1); M_b = V_b·(α − α̅) (Eq. 4-2); M_c = H_c·(β − β̅) (Eq. 4-3)",
            "Interação da interface da chapa: (M/M_n)² + (N/N_n)² + (V/V_n)⁴ ≤ 1",
            "Solda: D = f/(2·φ·0,60·F_EXX·0,707·(1 + 0,50·sen^1,5 θ)), θ = atan(f_normal/f_cisalhante)",
        ],
        criterios=[
            "Cada verificação: solicitante ≤ disponível (φ·R_n no LRFD; R_n/Ω no ASD).",
            "Perna da solda adotada ≥ necessária e ≥ mínima da Tabela J2.4.",
        ],
        alertas=alertas,
        referencias=REFERENCIAS,
        conclusao=destaque,
        responsavel=responsavel,
    )
