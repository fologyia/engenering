"""Registro técnico, tabelas e texto de destaque do contraventamento de estruturas abertas.

Monta, a partir de :class:`core.contraventamento_plataforma.ResultadoContraventamento`, o registro
que a página grava no projeto: entradas, tabela de verificações (o memorial a mostra como "o que
passou / o que não passou"), e as tabelas do vento por nível, das ações com os seus coeficientes,
dos pórticos (φ, C_a e η) e dos andares (cortante, combinação governante, B₂ e forças nas
diagonais). Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from core import contraventamento_plataforma as cp
from core import load_combinations as comb
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    csv_verificacoes,
    linhas_para_registro,
    numero_json,
)

MODULO_ID = "contraventamento_estrutura"
MODULO_TITULO = "Contraventamento de estruturas abertas"
LARGURA_UTIL_DXA = 9360

REFERENCIAS = [
    "ABNT NBR 6123:2023 — Forças devidas ao vento em edificações (capítulo 8, 7.2.4; Figuras 12 e "
    "14; Tabelas 27 e 28).",
    "ABNT NBR 8800 — Projeto de revisão (maio de 2024): 4.8.7 (combinações), Tabelas 1 e 2, 4.10.4 e "
    "4.10.7 (deslocabilidade e forças nocionais), Anexo C (B₂), 5.2, 5.3.5.4, 6.2.5, 6.3 e 6.5.6, "
    "Anexo B (deslocamentos).",
    "ABNT NBR 8681:2003 — Ações e segurança nas estruturas.",
]

FORA_DO_ESCOPO = (
    "Pilares, vigas e bases: o programa dá o acréscimo de força nos pilares do painel, mas não os "
    "verifica (use Flambagem de colunas e Estruturas de aço).",
    "A chapa de nó: use a página Ligação de contraventamento com as forças mostradas aqui.",
    "O contraventamento horizontal do piso: piso em grade não é diafragma; a força de cada nível "
    "precisa chegar às linhas contraventadas por vigas ou por um contraventamento no plano do piso.",
    "Efeitos dinâmicos do vento (capítulo 9 da NBR 6123), sismo (NBR 15421) e vento oblíquo.",
    "Deformação axial dos pilares no deslocamento (só a das diagonais entra) e a compressão que o "
    "encurtamento dos pilares induz nas diagonais.",
)


def _larguras(pesos: list[int]) -> list[int]:
    total = sum(pesos)
    larguras = [round(LARGURA_UTIL_DXA * p / total) for p in pesos]
    larguras[-1] += LARGURA_UTIL_DXA - sum(larguras)
    return larguras


def _n(valor: float | None, casas: int = 1) -> str:
    if valor is None:
        return "—"
    if not math.isfinite(valor):
        return "∞"
    texto = f"{valor:.{casas}f}"
    return texto.replace(".", ",")


def _cotas(cotas: tuple[float, ...]) -> str:
    return "; ".join(_n(z, 2) for z in cotas)


# ---------------------------------------------------------------------------------------------
# Tabelas
# ---------------------------------------------------------------------------------------------
def linhas_do_vento(r: cp.ResultadoContraventamento) -> list[list[str]]:
    linhas = []
    for d in cp.DIRECOES:
        vento = r.vento.direcao(d)
        for nivel in vento.niveis:
            linhas.append(
                [
                    d,
                    str(nivel.nivel),
                    _n(nivel.cota_m, 2),
                    _n(nivel.q_N_m2 / 1e3, 3),
                    _n(nivel.estrutura_kN, 2),
                    _n(nivel.guarda_corpo_kN, 2),
                    _n(nivel.equipamentos_kN, 2),
                    _n(nivel.total_kN, 2),
                ]
            )
    return linhas


def linhas_dos_porticos(r: cp.ResultadoContraventamento) -> list[list[str]]:
    linhas = []
    for d in cp.DIRECOES:
        vento = r.vento.direcao(d)
        for plano in vento.planos:
            linhas.append(
                [
                    d,
                    str(plano.posicao),
                    "sim" if plano.contraventado else "não",
                    _n(plano.area_exposta_m2, 2),
                    _n(plano.phi, 3),
                    _n(plano.ca, 2),
                    _n(plano.eta, 3),
                ]
            )
    return linhas


def linhas_das_acoes(r: cp.ResultadoContraventamento) -> list[list[str]]:
    linhas = []
    for a in r.acoes:
        linhas.append(
            [
                a.nome,
                a.categoria,
                _n(a.gamma, 2),
                _n(a.gamma_favoravel, 2) if a.gamma_favoravel is not None else "—",
                _n(a.psi0, 2),
                _n(a.psi1, 2),
                _n(a.psi2, 2),
                a.grupo or "—",
            ]
        )
    return linhas


def linhas_dos_andares(r: cp.ResultadoContraventamento) -> list[list[str]]:
    linhas = []
    for a in r.andares:
        linhas.append(
            [
                f"{a.direcao} / {a.andar}",
                _n(abs(a.cortante_elu.valor), 2),
                a.cortante_elu.expressao,
                f"{_n(a.b2, 3)} ({a.deslocabilidade})",
                _n(a.tracao_kN, 2),
                _n(a.compressao_kN, 2),
                _n(a.theta_vertical_graus, 1),
                _n(a.deslocamento_mm, 2),
            ]
        )
    return linhas


def tabelas_para_memorial(r: cp.ResultadoContraventamento) -> list[dict[str, Any]]:
    return [
        {
            "legenda": (
                "Forças do vento por nível (NBR 6123:2023, capítulo 8): pórticos como reticulados "
                "planos com proteção η, guarda-corpos e equipamentos. Cada direção vale nos dois "
                "sentidos."
            ),
            "cabecalhos": [
                "Dir.",
                "Nível",
                "Cota (m)",
                "q (kN/m²)",
                "Estrutura (kN)",
                "Guarda-corpo (kN)",
                "Equip. (kN)",
                "Total (kN)",
            ],
            "linhas": linhas_do_vento(r),
            "larguras": _larguras([8, 8, 11, 12, 15, 16, 13, 17]),
            "fonte": 7.4,
        },
        {
            "legenda": (
                "Pórticos perpendiculares ao vento: área exposta, índice φ, C_a (Figura 12) e "
                "fator de proteção η (Figura 14) — o pórtico 1 é o de barlavento."
            ),
            "cabecalhos": ["Dir.", "Pórtico", "Contrav.", "A_e (m²)", "φ", "C_a", "η"],
            "linhas": linhas_dos_porticos(r),
            "larguras": _larguras([10, 12, 14, 16, 14, 14, 14]),
            "fonte": 7.4,
        },
        {
            "legenda": (
                "Ações e coeficientes (NBR 8800, Tabelas 1 e 2). As gravitacionais levam a força "
                "nocional de 0,3 % (4.10.7.1); o vento está num grupo exclusivo (+X, −X, +Y, −Y)."
            ),
            "cabecalhos": ["Ação", "Categoria", "γ", "γ fav.", "ψ0", "ψ1", "ψ2", "Grupo"],
            "linhas": linhas_das_acoes(r),
            "larguras": _larguras([14, 40, 7, 8, 7, 7, 7, 10]),
            "fonte": 7.0,
        },
        {
            "legenda": (
                "Andares: cortante de cálculo (envoltória ELU) com a combinação governante, B₂ e a "
                "deslocabilidade, forças na diagonal mais carregada (já com B₂ e a excentricidade), "
                "ângulo com a vertical e deslocamento do andar em serviço."
            ),
            "cabecalhos": [
                "Dir. / andar",
                "V_Sd (kN)",
                "Combinação governante",
                "B₂",
                "N_t (kN)",
                "N_c (kN)",
                "θ (°)",
                "Δ (mm)",
            ],
            "linhas": linhas_dos_andares(r),
            "larguras": _larguras([10, 9, 33, 14, 9, 9, 7, 9]),
            "fonte": 7.0,
        },
    ]


# ---------------------------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------------------------
def _entradas(r: cp.ResultadoContraventamento, contexto: Mapping[str, Any] | None) -> dict:
    e = r.entrada
    c = e.cargas
    v = e.vento
    entradas: dict[str, Any] = {
        "comprimento_x_m": e.comprimento_x_m,
        "largura_y_m": e.largura_y_m,
        "cotas_dos_pisos_m": _cotas(e.cotas_m),
        "vaos_x": e.vaos_x,
        "vaos_y": e.vaos_y,
        "largura_do_pilar_m": e.largura_pilar_m,
        "altura_da_viga_m": e.altura_viga_m,
        "guarda_corpo": e.guarda_corpo,
        "altura_do_guarda_corpo_m": e.altura_guarda_corpo_m if e.guarda_corpo else None,
        "indice_do_guarda_corpo": e.indice_guarda_corpo if e.guarda_corpo else None,
        "equipamentos": "; ".join(
            f"{eq.nome} (nível {eq.nivel}, {eq.forma}, {_n(eq.peso_kN)} kN)"
            for eq in e.equipamentos
        )
        or None,
        "V0_m_s": v.v0_m_s,
        "S1": v.s1,
        "categoria_de_rugosidade": v.categoria,
        "grupo_S3": v.grupo_s3 if v.s3 is None else None,
        "S3_informado": v.s3,
        "peso_da_estrutura_kN_m2": c.peso_estrutura_kN_m2,
        "peso_do_piso_kN_m2": c.peso_piso_kN_m2,
        "sobrecarga_kN_m2": c.sobrecarga_kN_m2,
        "categoria_da_sobrecarga": c.categoria_sobrecarga,
        "forcas_horizontais": "; ".join(
            f"{f.nome}: {_n(f.valor_kN)} kN em {f.direcao}, nível {f.nivel}"
            for f in c.forcas_horizontais
        )
        or None,
        "excentricidade": e.excentricidade,
        "combinacao_de_servico": e.combinacao_de_servico,
    }
    for d in cp.DIRECOES:
        s = e.sistema(d)
        entradas[f"contraventamento_{d}"] = (
            f"{cp.TIPOS[s.tipo]}; {s.linhas} linha(s) × {s.paineis_por_linha} painel(éis); "
            f"{s.diagonal.familia} {s.diagonal.perfil} ({s.diagonal.aco}), ligação "
            f"{s.diagonal.ligacao}"
        )
    entradas.update(dict(contexto or {}))
    return {k: val for k, val in entradas.items() if val is not None}


def texto_de_destaque(r: cp.ResultadoContraventamento) -> str:
    gov = r.diagonal_governante()
    partes = [
        f"Vento: {_n(r.vento.x.total_kN, 1)} kN em X e {_n(r.vento.y.total_kN, 1)} kN em Y "
        f"(característicos).",
        f"Diagonal mais solicitada: {gov.direcao}, andar {gov.andar} — N_t = "
        f"{_n(gov.tracao_kN, 1)} kN"
        + (f", N_c = {_n(gov.compressao_kN, 1)} kN" if gov.compressao_kN > 0 else "")
        + f" ({gov.cortante_elu.estado_limite}: {gov.cortante_elu.expressao}).",
        f"B₂ máximo = {_n(max(a.b2 for a in r.andares), 3)}; deslocamento do topo "
        f"{_n(r.deslocamento_topo_mm['X'], 2)} mm em X e {_n(r.deslocamento_topo_mm['Y'], 2)} mm "
        "em Y.",
        f"Maior aproveitamento: {_n(100 * r.aproveitamento_maximo, 1)} %.",
    ]
    return " ".join(partes)


def registro_contraventamento(
    r: cp.ResultadoContraventamento,
    *,
    contexto: Mapping[str, Any] | None = None,
    responsavel: str = "",
) -> dict[str, Any]:
    verificacoes = list(r.verificacoes)
    geral = r.status
    destaque = texto_de_destaque(r)
    lig = cp.forcas_para_ligacao(r)
    tag = str((contexto or {}).get("tag") or "").strip()
    resultados: dict[str, Any] = {
        "status_geral": geral,
        "verificações": linhas_para_registro(verificacoes),
        "utilizacao_maxima": numero_json(r.aproveitamento_maximo, 4),
        "destaque_memorial": destaque,
        "tabelas_memorial": tabelas_para_memorial(r),
        "forcas_para_a_ligacao": {
            "direcao": lig.direcao,
            "andar": lig.andar,
            "tracao_kN": numero_json(lig.tracao_kN),
            "compressao_kN": numero_json(lig.compressao_kN),
            "theta_vertical_graus": numero_json(lig.theta_vertical_graus, 2),
        },
    }
    alertas = [f"{v.nome}: {v.formula}" for v in verificacoes if v.status in ("NÃO OK", "ALERTA")]
    alertas.extend(r.avisos)
    alertas.extend(f"Fora do escopo: {item}" for item in FORA_DO_ESCOPO)
    e = r.entrada
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=(
            f"Contraventamento{(' ' + tag) if tag else ''} — plataforma "
            f"{_n(e.comprimento_x_m, 1)} × {_n(e.largura_y_m, 1)} m, {len(e.cotas_m)} nível(is)"
        ),
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=(
            f"Contraventamento vertical de estrutura aberta {_n(e.comprimento_x_m, 1)} × "
            f"{_n(e.largura_y_m, 1)} m com pisos nas cotas {_cotas(e.cotas_m)} m: vento pela NBR "
            "6123:2023 (reticulados), combinações e forças nocionais pela NBR 8800, B₂ e diagonais "
            f"verificadas; aproveitamento máximo {_n(100 * r.aproveitamento_maximo, 1)} %."
        ),
        entradas=_entradas(r, contexto),
        resultados=resultados,
        metodo=(
            "Vento por reticulados planos paralelos (NBR 6123:2023, 8.3 e 8.4), levado aos pisos "
            "por faixas de influência; ações com os coeficientes das Tabelas 1 e 2 da NBR 8800 e "
            "força nocional de 0,3 % das gravitacionais em todas as combinações; cortante de cada "
            "andar pela envoltória rigorosa das combinações (variável favorável fora, permanente "
            "favorável com γ = 1,0, vento num grupo exclusivo); B₂ do Anexo C com a rigidez axial "
            "das diagonais; força na diagonal N = f·V·B₂/(n_painéis·n_ativas·cos α)."
        ),
        premissas=[
            "Pórticos com vigas rotuladas: o cortante de cada direção vai inteiro para as linhas "
            "contraventadas daquela direção.",
            f"Linha mais carregada com a fração 1/n + e·y_máx/Σy² (e = "
            f"{_n(100 * e.excentricidade, 1)} % da dimensão perpendicular).",
            "Contraventamento em X só tração: a diagonal comprimida é desprezada; nas demais, cada "
            "diagonal ativa recebe a mesma parcela do cortante.",
            "Barras de seção circular tratadas pela Figura 12 (faces planas), a favor da segurança.",
            "Peso da estrutura e do piso informados por área de piso, em cada nível.",
        ],
        equacoes=[
            "F_a = C_a·q·A_e; C_an = C_a1·[1 + (n − 1)·η] (NBR 6123, 8.3 e 8.4)",
            "F_d = Σγ_g·F_G + γ_q1·F_Q1 + Σγ_qj·ψ_0j·F_Qj (NBR 8800, 4.8.7.2.1)",
            "H_nocional = 0,003·ΣF_gravitacional de cálculo (4.10.7.1.1)",
            "B₂ = 1/[1 − (1/R_s)·(Δh/h)·(ΣN_Sd/ΣH_Sd)], R_s = 1 (Anexo C)",
            "N_diagonal = f·V_Sd·B₂/(n_painéis·n_ativas·cos α)",
        ],
        criterios=[
            "Cada verificação de resistência: solicitante ≤ resistente de cálculo.",
            "Deslocabilidade: B₂ ≤ 1,10 pequena; ≤ 1,40 média (amplifica com 80 % da rigidez); "
            "acima, grande (não atende ao método).",
            "Deslocamentos (Anexo B, Tabela B.1): H/300 com um piso; H/400 e h/500 com dois ou mais.",
        ],
        alertas=alertas,
        referencias=REFERENCIAS,
        conclusao=destaque,
        responsavel=responsavel,
    )


def csv_das_verificacoes(r: cp.ResultadoContraventamento) -> bytes:
    return csv_verificacoes(list(r.verificacoes))


def estados_disponiveis() -> tuple[str, ...]:
    return (comb.ELS_RARA, comb.ELS_FREQUENTE)
