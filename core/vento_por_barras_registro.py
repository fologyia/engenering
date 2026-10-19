"""Registro técnico (memorial) do vento barra a barra. Sem Streamlit.

Fica no mesmo módulo da página (Vento em estruturas abertas): o memorial traz o resumo por
direção, a força que chega a cada nível (:mod:`core.vento_por_nivel`), os reticulados com φ, C_a
e η, a carga de cada barra em cada direção (kN/m) e os guarda-corpos, escadas e equipamentos com
a barra que recebe cada um.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from core import vento_aberto_registro as var
from core import vento_por_barras as vpb
from core import vento_por_nivel as vpn
from core.technical_records import criar_registro_tecnico
from core.verificacao import numero_json

METODO = "Barra a barra (viga a viga, pilar a pilar)"


def _n(valor: float, casas: int = 2) -> str:
    if not math.isfinite(valor):
        return "∞"
    if round(valor, casas) == 0:
        valor = 0.0  # sem "−0,0"
    return f"{valor:.{casas}f}".replace(".", ",")


def linhas_do_resumo(r: vpb.ResultadoPorBarras) -> list[list[str]]:
    return [
        [
            d.codigo,
            vpb.SENTIDOS[d.angulo],
            "perpendicular" if d.perpendicular else "diagonal",
            _n(d.estrutura_kN),
            _n(d.elementos_kN),
            _n(d.total_kN),
            _n(d.momento_tombamento_kNm, 1),
            _n(d.torcao_kNm, 1),
        ]
        for d in r.direcoes
    ]


def linhas_dos_reticulados(r: vpb.ResultadoPorBarras) -> list[list[str]]:
    linhas = []
    for d in r.direcoes:
        for p in d.planos:
            linhas.append(
                [
                    d.codigo,
                    p.nome,
                    str(len(p.barras)),
                    _n(p.area_m2, 3),
                    _n(p.contorno_m2, 2),
                    _n(p.phi),
                    _n(p.ca),
                    _n(p.afastamento_m) if p.afastamento_m else "—",
                    _n(p.eta),
                ]
            )
    return linhas


def linhas_das_barras(r: vpb.ResultadoPorBarras) -> list[list[str]]:
    """Uma linha por barra: a carga (kN/m) em cada direção calculada."""
    linhas = []
    for b in r.entrada.barras:
        valores = []
        for d in r.direcoes:
            f = d.da_barra(b.nome)
            valores.append(_n(f.kN_m, 3) if f and f.forca_kN > 1e-9 else "—")
        linhas.append([b.rotulo, b.perfil or "—", _n(b.comprimento_m), *valores])
    return linhas


def linhas_dos_elementos(r: vpb.ResultadoPorBarras) -> list[list[str]]:
    linhas = []
    for d in r.direcoes:
        for el in d.elementos:
            destino = ", ".join(p.barra for p in el.parcelas) or "—"
            linhas.append(
                [
                    d.codigo,
                    el.elemento,
                    el.tipo,
                    _n(el.area_m2, 3),
                    _n(el.ca),
                    _n(el.q_N_m2 / 1e3, 3),
                    _n(el.forca_kN, 3),
                    destino,
                ]
            )
    return linhas


def tabelas_para_memorial(
    r: vpb.ResultadoPorBarras, eixo_vertical: str = "Y"
) -> list[dict[str, Any]]:
    codigos = [d.codigo for d in r.direcoes]
    largura_codigo = max(4, round(48 / max(len(codigos), 1)))
    tabelas: list[dict[str, Any]] = [
        {
            "legenda": (
                "Vento barra a barra: força característica em cada direção (W0 sopra para +X, "
                "W90 para +Y da planta), nas barras e nos elementos, com o momento de tombamento e a "
                "torção em torno do centro da planta."
            ),
            "cabecalhos": [
                "Caso",
                "Sentido",
                "Direção",
                "Barras (kN)",
                "Elementos (kN)",
                "Total (kN)",
                "Tombamento (kN·m)",
                "Torção (kN·m)",
            ],
            "linhas": linhas_do_resumo(r),
            "larguras": var._larguras([8, 11, 13, 12, 13, 11, 16, 13]),
            "fonte": 7.4,
        }
    ]
    vn = vpn.vento_por_nivel(r)
    if vn.niveis:
        tabelas.append(
            {
                "legenda": (
                    "Força do vento em cada nível (kN, característica): cada barra leva o vento "
                    "dela às duas pontas, metade em cada, e a ponta no meio de outra barra passa às "
                    "pontas dela; a linha base é o que chega ao pé dos pilares, direto à fundação. "
                    "A última coluna é a linha do modelo por onde passa a força do nível."
                ),
                "cabecalhos": [
                    "Caso",
                    "Nível",
                    "Cota (m)",
                    "F_x (kN)",
                    "F_y (kN)",
                    "Passa em (modelo)",
                ],
                "linhas": vpn.linhas_por_nivel_para_memorial(vn, eixo_vertical),
                "larguras": var._larguras([8, 22, 9, 10, 10, 30]),
                "fonte": 7.2,
            }
        )
    reticulados = linhas_dos_reticulados(r)
    if reticulados:
        tabelas.append(
            {
                "legenda": (
                    "Reticulados (planos perpendiculares ao vento), de barlavento (R1) para "
                    "sotavento: área de sombra, contorno, φ, C_a (Figura 12), afastamento ao "
                    "anterior e fator de proteção η (Figura 14) da parte que fica atrás dele."
                ),
                "cabecalhos": [
                    "Caso",
                    "Plano",
                    "Barras",
                    "A_e (m²)",
                    "Contorno (m²)",
                    "φ",
                    "C_a",
                    "e (m)",
                    "η",
                ],
                "linhas": reticulados,
                "larguras": var._larguras([9, 9, 9, 12, 14, 10, 10, 10, 10]),
                "fonte": 7.2,
            }
        )
    tabelas.append(
        {
            "legenda": (
                "Carga distribuída do vento em cada barra (kN/m, uniforme na barra, na direção do "
                "vento) — F = C_a·η·q·A, com A = ℓ·sen θ·c a área de sombra."
            ),
            "cabecalhos": ["Barra", "Perfil", "ℓ (m)", *codigos],
            "linhas": linhas_das_barras(r),
            "larguras": var._larguras([30, 16, 7, *([largura_codigo] * len(codigos))]),
            "fonte": 6.8,
        }
    )
    elementos = linhas_dos_elementos(r)
    if elementos:
        tabelas.append(
            {
                "legenda": (
                    "Guarda-corpos, escadas, painéis e equipamentos: área exposta, C_a, q, força e a "
                    "barra que recebe."
                ),
                "cabecalhos": [
                    "Caso",
                    "Elemento",
                    "Tipo",
                    "A (m²)",
                    "C_a",
                    "q (kN/m²)",
                    "F (kN)",
                    "Barra que recebe",
                ],
                "linhas": elementos,
                "larguras": var._larguras([7, 14, 15, 9, 7, 10, 9, 29]),
                "fonte": 7.0,
            }
        )
    return tabelas


def texto_de_destaque(r: vpb.ResultadoPorBarras) -> str:
    g = r.governante
    return (
        f"Vento barra a barra em {len(r.entrada.barras)} barras"
        + (f" e {len(r.entrada.elementos)} elementos" if r.entrada.elementos else "")
        + f", {len(r.direcoes)} direções: a maior força é a do {g.codigo} "
        f"({vpb.SENTIDOS[g.angulo]}), {_n(g.total_kN)} kN, tombamento "
        f"{_n(g.momento_tombamento_kNm, 1)} kN·m; q no topo "
        f"{_n(r.vento_no_topo.q_N_m2 / 1e3, 3)} kN/m² a {_n(r.altura_m)} m do terreno."
    )


def registro_vento_por_barras(
    r: vpb.ResultadoPorBarras,
    *,
    origem_das_barras: str = "",
    contexto: Mapping[str, Any] | None = None,
    responsavel: str = "",
    avisos_da_base: list[str] | None = None,
    eixo_vertical: str = "Y",
) -> dict[str, Any]:
    e = r.entrada
    p = e.parametros
    entradas: dict[str, Any] = {
        "metodo_do_vento": METODO,
        "origem_das_barras": origem_das_barras or None,
        "numero_de_barras": len(e.barras),
        "elementos_ao_vento": "; ".join(f"{el.nome} ({el.tipo.lower()})" for el in e.elementos)
        or None,
        "direcoes_calculadas": ", ".join(f"{d}°" for d in sorted(set(e.direcoes))),
        "protecao_entre_reticulados": e.protecao,
        "cota_do_terreno_m": numero_json(r.cota_do_terreno_m, 3),
        "altura_da_estrutura_m": numero_json(r.altura_m, 3),
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
    g = r.governante
    return criar_registro_tecnico(
        modulo=var.MODULO_TITULO,
        modulo_id=var.MODULO_ID,
        titulo=f"Vento barra a barra{(' ' + tag) if tag else ''} — {len(e.barras)} barras",
        status="Calculado",
        resumo=destaque,
        entradas=entradas,
        resultados={
            "destaque_memorial": destaque,
            "tabelas_memorial": tabelas_para_memorial(r, eixo_vertical),
            "direcao_de_maior_forca": g.codigo,
            "forca_total_maior_kN": numero_json(g.total_kN),
            "momento_de_tombamento_maior_kNm": numero_json(
                max(d.momento_tombamento_kNm for d in r.direcoes)
            ),
            "q_no_topo_kN_m2": numero_json(r.vento_no_topo.q_N_m2 / 1e3, 4),
        },
        metodo=(
            "Toda estrutura de barras retas é um reticulado (NBR 6123 8.3): a força em cada barra "
            "é C_a·η·q·A, com A = ℓ·sen θ·c a área de sombra (projeção da barra num plano "
            "perpendicular ao vento, pela seção e pela direção da alma). No vento perpendicular às "
            "faces, as barras perpendiculares ao vento formam os reticulados: φ e C_a da Figura 12 "
            "por plano e o fator de proteção η da Figura 14 na parte que fica atrás do contorno do "
            "plano imediatamente a barlavento (8.4). Barras fora dos planos e o vento diagonal: "
            "C_a = 2,0 e sem proteção. q pela cota do ponto mais alto de cada barra."
        ),
        premissas=[
            "Carga uniforme em cada barra, com o q do ponto mais alto dela (a favor da segurança).",
            "Vento diagonal (45°, 135°, 225°, 315°), quando calculado: verificação a mais, com "
            "C_a = 2,0 e sem proteção — a NBR 6123 (8.5) pede as direções perpendiculares às faces.",
            "Guarda-corpos, escadas e painéis como reticulados com o seu φ, sem proteção; "
            "equipamentos como caixa (C_a = 2,0) ou cilindro (Tabelas 27 e 28).",
            "Chapas do esqueleto (piso, apoios de carga) não recebem vento sozinhas: as superfícies "
            "reais entram como painel.",
            "Efeitos dinâmicos (capítulo 9) fora.",
        ],
        equacoes=[
            "V_k = V₀·S₁·S₂·S₃; q = 0,613·V_k²",
            "F = C_a·η·q·A; A = ℓ·sen θ·c (área de sombra)",
            "φ = A_e/A_contorno de cada reticulado; C_a pela Figura 12; η pela Figura 14 (φ e e/h_b)",
        ],
        criterios=["Forças características: as combinações saem do plano de cargas (NBR 8800)."],
        alertas=[*r.avisos, *(avisos_da_base or [])],
        referencias=[
            "ABNT NBR 6123:2023 — 4.2, 5 (S₁, S₂, S₃) e capítulo 8: 8.3 (reticulados planos, "
            "Figura 12, área de sombra), 8.4 (reticulados múltiplos, Figura 14), 8.5 (faces "
            "paralelas ao vento), 8.1.2 e 8.1.3 (Tabelas 27 e 28).",
        ],
        conclusao=destaque,
        responsavel=responsavel,
    )
