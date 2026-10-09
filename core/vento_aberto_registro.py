"""Registro técnico e saídas para o modelo do vento em estruturas abertas (NBR 6123:2023, cap. 8).

Monta, a partir de :class:`core.vento_estrutura_aberta.ResultadoVentoAberto`, o registro que vai
para o memorial (forças por nível, pórticos com φ, C_a e η, forças nos nós por pórtico), as ações
W0, W90, W180 e W270 do plano de cargas e os CSV para lançar no modelo. Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from core import plano_de_cargas as pc
from core import vento_estrutura_aberta as va
from core.technical_records import criar_registro_tecnico
from core.verificacao import numero_json

MODULO_ID = "vento_estrutura_aberta"
MODULO_TITULO = "Vento em estruturas abertas"
LARGURA_UTIL_DXA = 9360
ORIGEM = "Vento em estruturas abertas (NBR 6123:2023, cap. 8)"

REFERENCIAS = [
    "ABNT NBR 6123:2023 — Forças devidas ao vento em edificações: 4.2, 5 (S₁, S₂, S₃), 7.2.4 e "
    "capítulo 8 (8.3 reticulados planos isolados, Figura 12; 8.4 reticulados múltiplos, Figura 14; "
    "8.1.2 e 8.1.3, Tabelas 27 e 28).",
]


def _n(valor: float, casas: int = 2) -> str:
    if not math.isfinite(valor):
        return "∞"
    return f"{valor:.{casas}f}".replace(".", ",")


def _larguras(pesos: list[int]) -> list[int]:
    total = sum(pesos)
    larguras = [round(LARGURA_UTIL_DXA * p / total) for p in pesos]
    larguras[-1] += LARGURA_UTIL_DXA - sum(larguras)
    return larguras


# ---------------------------------------------------------------------------------------------
# Tabelas
# ---------------------------------------------------------------------------------------------
def linhas_por_nivel(r: va.ResultadoVentoAberto) -> list[list[str]]:
    linhas = []
    for d in (r.x, r.y):
        for n in d.niveis:
            linhas.append(
                [
                    d.direcao,
                    str(n.nivel),
                    _n(n.cota_m),
                    f"{_n(n.faixa_m[0])} a {_n(n.faixa_m[1])}",
                    _n(n.q_N_m2 / 1e3, 3),
                    _n(n.estrutura_kN),
                    _n(n.guarda_corpo_kN),
                    _n(n.equipamentos_kN),
                    _n(n.total_kN),
                ]
            )
        linhas.append(
            [
                d.direcao,
                "base",
                "0",
                f"0 a {_n(d.niveis[0].faixa_m[0])}",
                "—",
                _n(d.forca_na_base_kN),
                "—",
                "—",
                _n(d.forca_na_base_kN),
            ]
        )
    return linhas


def linhas_dos_porticos(r: va.ResultadoVentoAberto) -> list[list[str]]:
    return [
        [
            d.direcao,
            f"P{p.posicao}",
            _n(p.coordenada_m),
            "sim" if p.contraventado else "não",
            _n(p.area_exposta_m2),
            _n(p.phi, 3),
            _n(p.ca),
            _n(p.eta, 3),
        ]
        for d in (r.x, r.y)
        for p in d.planos
    ]


def linhas_nodais(r: va.ResultadoVentoAberto) -> list[list[str]]:
    linhas = []
    for d in (r.x, r.y):
        for c in va.cargas_nodais(d):
            linhas.append(
                [
                    d.direcao,
                    f"P{c.portico}",
                    _n(c.coordenada_m),
                    str(c.nivel),
                    _n(c.cota_m),
                    _n(c.estrutura_kN),
                    _n(c.guarda_corpo_kN),
                    _n(c.total_kN),
                    f"{c.pilares} × {_n(c.por_pilar_kN)}",
                ]
            )
    return linhas


def tabelas_para_memorial(r: va.ResultadoVentoAberto) -> list[dict[str, Any]]:
    return [
        {
            "legenda": (
                "Força do vento por nível (característica), em cada direção — vale nos dois "
                "sentidos. A faixa da base vai direto à fundação."
            ),
            "cabecalhos": [
                "Dir.",
                "Nível",
                "Cota (m)",
                "Faixa (m)",
                "q (kN/m²)",
                "Estrutura (kN)",
                "Guarda-corpo (kN)",
                "Equip. (kN)",
                "Total (kN)",
            ],
            "linhas": linhas_por_nivel(r),
            "larguras": _larguras([6, 7, 9, 13, 10, 13, 14, 11, 12]),
            "fonte": 7.2,
        },
        {
            "legenda": (
                "Pórticos perpendiculares ao vento: posição, área exposta, φ, C_a (Figura 12) e "
                "fator de proteção η (Figura 14); P1 é o de barlavento."
            ),
            "cabecalhos": [
                "Dir.",
                "Pórtico",
                "Posição (m)",
                "Contrav.",
                "A_e (m²)",
                "φ",
                "C_a",
                "η",
            ],
            "linhas": linhas_dos_porticos(r),
            "larguras": _larguras([8, 10, 13, 12, 13, 12, 12, 12]),
            "fonte": 7.4,
        },
        {
            "legenda": (
                "Forças nos nós de cada pórtico e nível, para o modelo: o total do pórtico e a "
                "parcela por pilar (nó pilar–viga)."
            ),
            "cabecalhos": [
                "Dir.",
                "Pórtico",
                "Posição (m)",
                "Nível",
                "Cota (m)",
                "Estrutura (kN)",
                "Guarda-corpo (kN)",
                "Total (kN)",
                "Por pilar (kN)",
            ],
            "linhas": linhas_nodais(r),
            "larguras": _larguras([6, 9, 11, 7, 9, 13, 14, 11, 16]),
            "fonte": 7.2,
        },
    ]


# ---------------------------------------------------------------------------------------------
# Plano de cargas
# ---------------------------------------------------------------------------------------------
def cargas_para_o_plano(r: va.ResultadoVentoAberto, direcao: str) -> list[pc.CargaDoModelo]:
    """Forças nos nós por pilar (pórtico e nível) e os equipamentos, na direção +X ou +Y."""
    d = r.direcao(direcao)
    cargas = [
        pc.CargaDoModelo(
            elemento=f"Pórtico P{c.portico} (posição {_n(c.coordenada_m)} m), nível {c.nivel} "
            f"(z = {_n(c.cota_m)} m) — cada um dos {c.pilares} nós pilar–viga",
            valor=c.por_pilar_kN,
            unidade="kN",
            direcao=direcao,
            observacao=f"total do pórtico {_n(c.total_kN)} kN",
        )
        for c in va.cargas_nodais(d)
    ]
    for nivel in d.equipamentos_por_nivel:
        for nome, forca, cota in nivel:
            cargas.append(
                pc.CargaDoModelo(
                    elemento=f"{nome} — no centro do equipamento (z = {_n(cota)} m)",
                    valor=forca,
                    unidade="kN",
                    direcao=direcao,
                    observacao="equipamento",
                )
            )
    return cargas


def acoes_para_o_plano(r: va.ResultadoVentoAberto, registro_id: str = "") -> list[pc.Acao]:
    resumos = {
        "X": f"{_n(r.x.total_kN, 1)} kN em X; base {_n(r.x.momento_na_base_kNm, 1)} kN·m",
        "Y": f"{_n(r.y.total_kN, 1)} kN em Y; base {_n(r.y.momento_na_base_kNm, 1)} kN·m",
    }
    return pc.acoes_de_vento(
        ORIGEM,
        {"X": cargas_para_o_plano(r, "X"), "Y": cargas_para_o_plano(r, "Y")},
        resumo_por_direcao=resumos,
        registro_id=registro_id,
    )


def csv_nos_nos(r: va.ResultadoVentoAberto) -> bytes:
    linhas = []
    for d in (r.x, r.y):
        for c in va.cargas_nodais(d, incluir_base=True):
            linhas.append(
                [
                    d.direcao,
                    f"P{c.portico}",
                    c.coordenada_m,
                    c.nivel,
                    c.cota_m,
                    c.estrutura_kN,
                    c.guarda_corpo_kN,
                    c.total_kN,
                    c.pilares,
                    c.por_pilar_kN,
                ]
            )
        for i, nivel in enumerate(d.equipamentos_por_nivel, start=1):
            for nome, forca, cota in nivel:
                linhas.append([d.direcao, nome, "", i, cota, forca, 0.0, forca, 1, forca])
    return pc._csv(
        [
            "Direção",
            "Pórtico",
            "Posição (m)",
            "Nível (0 = base)",
            "Cota (m)",
            "Estrutura (kN)",
            "Guarda-corpo (kN)",
            "Total (kN)",
            "Pilares",
            "Por pilar (kN)",
        ],
        linhas,
    )


def csv_distribuidas(g: va.GeometriaAberta, r: va.ResultadoVentoAberto) -> bytes:
    linhas = [
        [c.direcao, f"P{c.portico}", c.elemento, c.trecho, c.w_kN_m, c.calculo]
        for d in (r.x, r.y)
        for c in va.cargas_distribuidas(g, d)
    ]
    return pc._csv(["Direção", "Pórtico", "Elemento", "Trecho", "w (kN/m)", "Cálculo"], linhas)


# ---------------------------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------------------------
def texto_de_destaque(r: va.ResultadoVentoAberto) -> str:
    g = r.geometria
    return (
        f"Estrutura aberta de {_n(g.comprimento_x_m, 1)} × {_n(g.largura_y_m, 1)} m com pisos a "
        f"{'; '.join(_n(z, 2) for z in g.cotas_m)} m. Vento característico: "
        f"{_n(r.x.total_kN, 1)} kN em X (momento na base {_n(r.x.momento_na_base_kNm, 1)} kN·m) e "
        f"{_n(r.y.total_kN, 1)} kN em Y ({_n(r.y.momento_na_base_kNm, 1)} kN·m); q no topo "
        f"{_n(r.vento_no_topo.q_N_m2 / 1e3, 3)} kN/m²."
    )


def registro_vento_aberto(
    r: va.ResultadoVentoAberto,
    *,
    contexto: Mapping[str, Any] | None = None,
    responsavel: str = "",
    avisos_da_base: list[str] | None = None,
) -> dict[str, Any]:
    g, p = r.geometria, r.parametros
    entradas: dict[str, Any] = {
        "comprimento_x_m": g.comprimento_x_m,
        "largura_y_m": g.largura_y_m,
        "cotas_dos_pisos_m": "; ".join(_n(z, 2) for z in g.cotas_m),
        "vaos_x": g.vaos_x,
        "vaos_y": g.vaos_y,
        "largura_do_pilar_m": g.largura_pilar_m,
        "altura_da_viga_m": g.altura_viga_m,
        "guarda_corpo": g.guarda_corpo,
        "indice_do_guarda_corpo": g.indice_guarda_corpo if g.guarda_corpo else None,
        "equipamentos": "; ".join(
            f"{eq.nome} (nível {eq.nivel}, {eq.forma})" for eq in g.equipamentos
        )
        or None,
        "V0_m_s": p.v0_m_s,
        "S1": p.s1,
        "categoria_de_rugosidade": p.categoria,
        "S3": p.s3 if p.s3 is not None else None,
        "grupo_S3": p.grupo_s3 if p.s3 is None else None,
    }
    entradas.update(dict(contexto or {}))
    entradas = {k: v for k, v in entradas.items() if v is not None}
    destaque = texto_de_destaque(r)
    tag = str((contexto or {}).get("tag") or "").strip()
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=f"Vento em estrutura aberta{(' ' + tag) if tag else ''} — "
        f"{_n(g.comprimento_x_m, 1)} × {_n(g.largura_y_m, 1)} m",
        status="Calculado",
        resumo=destaque,
        entradas=entradas,
        resultados={
            "destaque_memorial": destaque,
            "tabelas_memorial": tabelas_para_memorial(r),
            "forca_total_X_kN": numero_json(r.x.total_kN),
            "forca_total_Y_kN": numero_json(r.y.total_kN),
            "momento_na_base_X_kNm": numero_json(r.x.momento_na_base_kNm),
            "momento_na_base_Y_kNm": numero_json(r.y.momento_na_base_kNm),
            "q_no_topo_kN_m2": numero_json(r.vento_no_topo.q_N_m2 / 1e3, 4),
        },
        metodo=(
            "Cada pórtico perpendicular ao vento é um reticulado plano: F = C_a·q·A_e, com C_a da "
            "Figura 12 pelo índice de área exposta φ; os de trás multiplicados pelo fator de "
            "proteção η da Figura 14 (φ do pórtico à frente e e/h_b). Guarda-corpos como reticulados "
            "próprios; equipamentos cilíndricos pelas Tabelas 27 e 28. Forças levadas aos pisos por "
            "faixas de influência, com q no topo de cada faixa."
        ),
        premissas=[
            "Barras de seção circular tratadas pela Figura 12 (faces planas), a favor da segurança.",
            "h_b = menor dimensão do pórtico (dá e/h_b e η maiores, a favor da segurança).",
            "Só os guarda-corpos perpendiculares ao vento recebem força (item 8.5).",
            "Vento nos dois sentidos de cada direção; vento oblíquo e efeitos dinâmicos fora.",
        ],
        equacoes=[
            "V_k = V₀·S₁·S₂·S₃; q = 0,613·V_k²",
            "F_a = C_a·q·A_e; C_an = C_a1·[1 + (n − 1)·η]",
            "Cilindro: F = C_a·K·q·d·ℓ (Tabelas 27 e 28; base no piso: ℓ/d dobra)",
        ],
        criterios=["Forças características: as combinações saem do plano de cargas (NBR 8800)."],
        alertas=[*r.avisos, *(avisos_da_base or [])],
        referencias=REFERENCIAS,
        conclusao=destaque,
        responsavel=responsavel,
    )
