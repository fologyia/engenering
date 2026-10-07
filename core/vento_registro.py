"""Registro técnico do vento na edificação (NBR 6123:2023) para o projeto e o memorial.

Monta, a partir de :class:`core.vento_edificio.ResultadoEdificio`, o registro que a página grava
no projeto: as entradas, a tabela de verificações (aplicabilidade e valores de apoio — é o que o
memorial mostra como "o que passou / o que não passou"), as tabelas de pressões por zona, das
vedações e das cargas do pórtico, e o texto de destaque com as pressões dinâmicas.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from core import vento_coeficientes as coef
from core import vento_portico as portico
from core.technical_records import criar_registro_tecnico
from core.vento_edificio import (
    COBERTURAS,
    REFERENCIAS_DE_ALTURA,
    ResultadoEdificio,
)
from core.vento_nbr6123 import numero_ptbr
from core.verificacao import linhas_para_registro, status_geral

MODULO_ID = "vento_nbr6123"
MODULO_TITULO = "Vento nas estruturas"
LARGURA_UTIL_DXA = 9360  # largura útil do memorial, em vinte avos de ponto


def _larguras(pesos: Sequence[int]) -> list[int]:
    total = sum(pesos)
    larguras = [round(LARGURA_UTIL_DXA * p / total) for p in pesos]
    larguras[-1] += LARGURA_UTIL_DXA - sum(larguras)
    return larguras


def _n(valor: float, casas: int = 2) -> str:
    return numero_ptbr(valor, casas)


def _sinal(valor: float, casas: int = 2) -> str:
    return ("+" if valor > 0 else "") + _n(valor, casas)


def _rotulo_cpi(valor: float) -> str:
    return f"c_pi = {_sinal(valor, 2)}"


def tabelas_de_pressoes(resultado: ResultadoEdificio) -> list[dict[str, Any]]:
    """Uma tabela por direção do vento: ``C_e``, área e pressão líquida em cada ``c_pi``."""
    tabelas: list[dict[str, Any]] = []
    for alpha in resultado.alphas:
        casos = resultado.casos_do_angulo(alpha)
        if not casos:
            continue
        cpis = [caso.cpi.valor for caso in casos]
        q = casos[0].vento.q_kN_m2
        linhas: list[list[str]] = []
        for indice, pressao in enumerate(casos[0].pressoes):
            zona = pressao.zona
            linhas.append(
                [
                    f"{zona.nome} — {zona.descricao}",
                    _sinal(zona.ce, 2),
                    _n(zona.area_m2, 1),
                    *[_sinal(caso.pressoes[indice].pressao_liquida_kN_m2, 3) for caso in casos],
                ]
            )
        tabelas.append(
            {
                "legenda": (
                    f"Vento a {alpha}° (classe {casos[0].classe}, q = {_n(q, 3)} kN/m²): coeficientes "
                    "de forma externos, áreas e pressões líquidas Δp = q·(f_v·C_e − c_pi) em kN/m²; "
                    "positiva empurra a superfície para dentro, negativa puxa para fora."
                ),
                "cabecalhos": [
                    "Zona",
                    "C_e",
                    "Área (m²)",
                    *[f"Δp, {_rotulo_cpi(c)}" for c in cpis],
                ],
                "linhas": linhas,
                "larguras": _larguras([46 - 8 * max(len(cpis) - 2, 0), 8, 10, *[18] * len(cpis)]),
                "fonte": 7.2,
            }
        )
    return tabelas


def tabela_de_vedacoes(resultado: ResultadoEdificio) -> dict[str, Any]:
    q = resultado.vento_vedacoes.q_kN_m2
    cpis = sorted({c for linha in resultado.vedacoes for c, _p in linha.liquida_por_cpi})
    linhas = []
    for linha in resultado.vedacoes:
        por_cpi = dict(linha.liquida_por_cpi)
        linhas.append(
            [
                f"{linha.zona} — {linha.descricao}",
                f"{linha.fonte_cpe} = {_sinal(linha.cpe, 2)}",
                *[_sinal(por_cpi[c], 3) if c in por_cpi else "-" for c in cpis],
            ]
        )
    return {
        "legenda": (
            f"Pressões de projeto das vedações e de suas fixações (classe A, topo da edificação, "
            f"q = {_n(q, 3)} kN/m²), em kN/m²: q·(f_v·C_e ou c_pe médio − c_pi)."
        ),
        "cabecalhos": ["Zona", "Coeficiente", *[f"Δp, {_rotulo_cpi(c)}" for c in cpis]],
        "linhas": linhas,
        "larguras": _larguras([46, 18, *[18] * len(cpis)]),
        "fonte": 7.0,
    }


def tabela_do_portico_para_memorial(
    resultado: ResultadoEdificio, casos: Sequence[portico.CasoPortico]
) -> dict[str, Any]:
    s = resultado.entrada.espacamento_porticos_m
    linhas = []
    for caso in casos:
        faixa = (
            ""
            if caso.faixa_x_m is None
            else f" · faixa {_n(caso.faixa_x_m[0], 1)} a {_n(caso.faixa_x_m[1], 1)} m"
        )
        linhas.append(
            [
                f"Vento a {caso.alpha}°, {_rotulo_cpi(caso.cpi.valor)}{faixa}",
                *[_sinal(caso.carga(m).carga_kN_m, 2) for m in portico.MEMBROS],
            ]
        )
    return {
        "legenda": (
            f"Cargas do vento no pórtico transversal (espaçamento {_n(s, 2)} m), em kN por metro de "
            "elemento, normais a ele: positiva = pressão (empurra para dentro); negativa = sucção."
        ),
        "cabecalhos": [
            "Caso",
            "Pilar esquerdo",
            "Água esquerda",
            "Água direita",
            "Pilar direito",
        ],
        "linhas": linhas,
        "larguras": _larguras([36, 16, 16, 16, 16]),
        "fonte": 7.2,
    }


def _entradas(resultado: ResultadoEdificio, contexto: Mapping[str, Any] | None) -> dict[str, Any]:
    e = resultado.entrada
    g = resultado.geometria
    entradas: dict[str, Any] = {
        "edicao_da_norma": "ABNT NBR 6123:2023",
        "v0_m_s": e.v0_m_s,
        "s1": e.s1,
        "categoria_rugosidade": e.categoria,
        "grupo_s3": e.grupo_s3,
        "s3_informado": e.s3,
        "classe_forcada": e.classe,
        "referencia_de_altura": REFERENCIAS_DE_ALTURA[e.referencia_altura],
        "vedacoes_com_092": e.vedacoes_com_092,
        "cobertura": COBERTURAS[e.cobertura],
        "comprimento_a_m": e.comprimento_a_m,
        "largura_b_m": e.largura_b_m,
        "altura_h_m": e.altura_h_m,
        "inclinacao_theta_graus": g.theta_graus,
        "altura_do_topo_m": g.h_topo_m,
        "balanco_do_beiral_m": e.beiral_m,
        "espacamento_porticos_m": e.espacamento_porticos_m,
        "periodo_fundamental_s": e.periodo_fundamental_s,
        "permeabilidade": (
            "c_pi informado: " + "; ".join(_n(v, 2) for v in (e.cpis_informados or ()))
            if e.cpis_informados
            else coef.CENARIOS_PERMEABILIDADE.get(
                e.cenario_permeabilidade, e.cenario_permeabilidade
            )
        ),
        "alta_turbulencia_solicitada": e.alta_turbulencia,
        "efeito_de_vizinhanca": e.com_vizinhanca,
        "afastamento_vizinha_m": e.afastamento_vizinha_m,
        "coeficiente_de_atrito_ct": e.ct_atrito,
    }
    entradas.update(dict(contexto or {}))
    return {chave: valor for chave, valor in entradas.items() if valor is not None}


def _finito(valor: float) -> float | str:
    return round(valor, 4) if math.isfinite(valor) else "—"


def registro_edificacao(
    resultado: ResultadoEdificio,
    *,
    casos_do_portico: Sequence[portico.CasoPortico] = (),
    solucao: portico.SolucaoPortico | None = None,
    contexto: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Registro técnico v2 do vento na edificação (uma análise = um registro)."""
    g = resultado.geometria
    e = resultado.entrada
    verificacoes = list(resultado.verificacoes)
    geral = status_geral(verificacoes)
    q0 = resultado.vento_por_alpha[0]
    q90 = resultado.vento_por_alpha[90]
    destaque = (
        f"Pressão dinâmica sobre a estrutura: q = {_n(q0.q_kN_m2, 3)} kN/m² a 0° (V_k = "
        f"{_n(q0.vk_m_s, 1)} m/s, classe {resultado.classe_por_alpha[0]}) e "
        f"q = {_n(q90.q_kN_m2, 3)} kN/m² a 90° (V_k = {_n(q90.vk_m_s, 1)} m/s, classe "
        f"{resultado.classe_por_alpha[90]}); vedações: q = "
        f"{_n(resultado.vento_vedacoes.q_kN_m2, 3)} kN/m². Força de arrasto F_a = "
        f"{_n(resultado.arrasto[0].forca_kN, 1)} kN a 0° e {_n(resultado.arrasto[90].forca_kN, 1)} kN "
        "a 90°."
    )
    tabelas = [*tabelas_de_pressoes(resultado), tabela_de_vedacoes(resultado)]
    if casos_do_portico:
        tabelas.append(tabela_do_portico_para_memorial(resultado, casos_do_portico))
    resultados: dict[str, Any] = {
        "status_geral": geral,
        "verificações": linhas_para_registro(verificacoes),
        "destaque_memorial": destaque,
        "tabelas_memorial": tabelas,
        "casos_de_vento": [
            {
                "angulo_graus": caso.alpha,
                "cpi": caso.cpi.valor,
                "classe": caso.classe,
                "q_kN_m2": _finito(caso.vento.q_kN_m2),
                "forca_horizontal_x_kN": _finito(caso.fx_kN),
                "forca_horizontal_y_kN": _finito(caso.fy_kN),
                "empuxo_no_telhado_kN": _finito(caso.fz_telhado_kN),
            }
            for caso in resultado.casos
        ],
        "arrasto_global": {
            str(alpha): {
                "ca": _finito(r.ca.valor),
                "forca_kN": _finito(r.forca_kN),
                "torsor_kNm": _finito(r.torsor_kNm),
                "soma_das_zonas_kN": _finito(r.soma_das_zonas_kN),
            }
            for alpha, r in resultado.arrasto.items()
        },
    }
    if casos_do_portico:
        resultados["cargas_do_portico"] = portico.tabela_do_portico(list(casos_do_portico))
    if solucao is not None:
        resultados["solucao_do_portico"] = {
            "caso": solucao.caso.nome,
            "reacoes": [dict(r) for r in solucao.reacoes],
            "deslocamento_horizontal_max_mm": _finito(solucao.deslocamento_horizontal_max_mm),
            "deslocamento_vertical_max_mm": _finito(solucao.deslocamento_vertical_max_mm),
        }
    alertas = [
        f"{v.nome}: {v.formula}" for v in verificacoes if v.status in ("NÃO OK", "ALERTA")
    ] + list(resultado.avisos)
    alertas.append(
        "O coeficiente de arrasto C_a das Figuras 4 e 5 foi lido do gráfico da norma, com "
        "incerteza de ±0,03; confira antes de emitir se o resultado depender dele."
    )
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=(
            f"Vento — {_n(e.comprimento_a_m, 1)} × {_n(e.largura_b_m, 1)} × {_n(e.altura_h_m, 1)} m, "
            f"{COBERTURAS[e.cobertura].split(' (')[0].lower()} (NBR 6123:2023)"
        ),
        status="Atenção" if geral == "ALERTA" else "Calculado",
        resumo=(
            f"Forças do vento na edificação {_n(g.a_m, 1)} × {_n(g.b_m, 1)} m, altura {_n(g.h_m, 1)} m: "
            "pressões por zona de paredes e telhado, vedações, forças globais e cargas do pórtico "
            f"({len(resultado.casos)} caso(s) de vento)."
        ),
        entradas=_entradas(resultado, contexto),
        resultados=resultados,
        metodo=(
            "V_k = V₀·S₁·S₂·S₃ e q = 0,613·V_k² (NBR 6123:2023, 4.2 e 5); coeficientes de forma "
            "externos C_e das Tabelas 6 a 8 e pressão interna c_pi do item 6.3; pressão efetiva "
            "Δp = q·(C_e − c_pi); força F = q·C·A·f_v (4.1); arrasto F_a = q·C_a·A_e·f_v (4.3.3)."
        ),
        premissas=[
            "Edificação paralelepipédica de arestas vivas, planta retangular a × b (a ≥ b) e "
            "cumeeira paralela ao lado maior (Tabelas 6 a 8).",
            "V₀ do mapa de isopletas, informado pelo projetista; relevo e rugosidade conforme "
            "informados.",
            "Classe A, B ou C pela maior dimensão da superfície frontal de cada direção do vento; "
            "S₂ no topo da edificação; vedações em classe A.",
            "Pressão interna pelo método simplificado do item 6.3.2 (ou valores informados).",
            f"Cargas do pórtico transversal = pressão líquida × espaçamento ({_n(e.espacamento_porticos_m, 2)} m); "
            "o pórtico de extremidade recebe a metade.",
        ],
        equacoes=list(resultado.memoria),
        criterios=[
            "Aplicabilidade dos coeficientes: 1 ≤ a/b ≤ 4, h/b ≤ 6 e inclinações dentro das Tabelas 7 e 8.",
            "Regime estático: período fundamental T₁ ≤ 1 s (NBR 6123:2023, 4.1).",
            "Desprendimento de vórtices investigado a partir de h/b ≥ 6 (item 10.2).",
        ],
        alertas=alertas,
        referencias=[
            "ABNT NBR 6123:2023 — Forças devidas ao vento em edificações.",
        ],
        conclusao=destaque,
    )
