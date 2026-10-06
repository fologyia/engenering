"""Interface da página Flambagem de colunas.

Só desenha a interface: todo cálculo está em ``core.column_buckling`` (que usa as fórmulas de
``core.column_design``). A verificação roda a cada interação e cobre a barra inteira — os dois
eixos, todos os modos de flambagem, a flexão em x e em y e a interação N + Mx + My — numa só
rodada. O botão "Comparar normas" liga e desliga um painel com a mesma coluna nas três normas.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from components.column_help import AJUDA
from components.project_tools import botao_registrar_calculo
from components.ui import comparador_cenarios, fronteira_modelo
from components.verification_table import COR_BADGE, estilizar, mostrar_tabela_verificacoes
from core import column_buckling as cb
from core import material_catalog as mat
from core import section_catalog as catalogo_perfis
from core.column_design import E_ACO, ESPESSURA_MIN_ANGLO, G_ACO, Secao
from core.materials_registry import avaliar_material, resumir_fonte
from core.project_store import obter_projeto_ativo
from core.verificacao import csv_verificacoes, formatar_percentual

SEC_CATALOGO = "Perfil de aço (catálogo)"
SEC_CIRC = "Barra circular maciça"
SEC_RET = "Barra retangular maciça"
SEC_TUBO_C = "Tubo circular"
SEC_TUBO_R = "Tubo retangular"
SEC_I = "Perfil I (por dimensões)"
SEC_U = "Perfil U (por dimensões)"
SEC_DIRETA = "Área e raio de giração"
SEC_GENERICA = "Seção genérica (propriedades)"
TIPOS_SECAO = (
    SEC_CATALOGO,
    SEC_CIRC,
    SEC_RET,
    SEC_TUBO_C,
    SEC_TUBO_R,
    SEC_I,
    SEC_U,
    SEC_DIRETA,
    SEC_GENERICA,
)

APOIO_MANUAL = "Informar K"

#: Tipo e grupo da Tabela 4 (NBR) / F.1 das paredes que o usuário descreve na seção genérica.
PAREDES: dict[str, tuple[str, int]] = {
    "AA · grupo 1 — parede de tubo retangular": ("AA", 1),
    "AA · grupo 2 — alma": ("AA", 2),
    "AL · grupo 3 — aba de cantoneira": ("AL", 3),
    "AL · grupo 4 — mesa de perfil laminado": ("AL", 4),
    "AL · grupo 5 — mesa de perfil soldado": ("AL", 5),
    "AL · grupo 6 — talão de T": ("AL", 6),
}
MAX_PAREDES = 6

AVISO_IDEALIZADO_LAMINADO = (
    "**Geometria idealizada:** mesas de espessura constante e sem raios de concordância. Num perfil "
    "laminado isso erra I_y, J e C_w (num U C6×8,2, o I_y idealizado chega a +23% do real): para "
    "laminado, prefira o perfil de catálogo. Marque “Perfil soldado” se for o caso."
)
AVISO_IDEALIZADO_SOLDADO = (
    "Geometria idealizada (chapas soldadas, sem raios de concordância): vale para perfil soldado."
)

MODO_CARACTERISTICO = "Cargas características majoradas aqui (γ_g·N_g + γ_q·N_q)"
MODO_CALCULO = "N_Sd já de cálculo (vindo das combinações)"

DIAG_LIVRE = "Não informado (C_m = 1,0)"
DIAG_PONTAS = "Momentos nas pontas (informar M₁/M₂)"
DIAG_TRANSVERSAL = "Força transversal entre os apoios (C_m = 1,0)"
DIAGRAMAS = (DIAG_LIVRE, DIAG_PONTAS, DIAG_TRANSVERSAL)

CB_INFORMAR = "Informar C_b"
CB_DIAGRAMA = "Calcular pelo diagrama de momentos"


def _numero(
    rotulo: str,
    chave: str,
    valor: float,
    ajuda: str,
    *,
    minimo: float | None = 0.001,
    maximo: float | None = None,
    passo: float | None = None,
    formato: str | None = None,
    alvo: Any = st,
) -> float:
    """``number_input`` com a persistência da sessão e o “?” sempre presentes."""
    return float(
        alvo.number_input(
            rotulo,
            min_value=minimo,
            max_value=maximo,
            value=float(valor),
            step=passo,
            format=formato,
            key=chave,
            persist_state="session",
            help=ajuda,
        )
    )


def _acompanhar_padrao(chave: str, padrao: float) -> None:
    """Faz um campo cujo padrão deriva de outro (ex.: meia altura do perfil) seguir o padrão.

    A chave do campo persiste na sessão, então o ``value=`` só valeria na primeira abertura. Se o
    padrão mudou desde a execução anterior, o campo volta a ele; na primeira execução nada é tocado
    (o que já estiver na sessão fica).
    """
    chave_padrao = f"{chave}__padrao"
    anterior = st.session_state.get(chave_padrao)
    if anterior is not None and anterior != padrao:
        st.session_state[chave] = padrao
    st.session_state[chave_padrao] = padrao


def _fmt(valor: float | None, casas: int = 3, unidade: str = "") -> str:
    if valor is None:
        return "—"
    if math.isinf(valor):
        return "∞"
    return f"{valor:.{casas}f}{unidade}"


# ---------------------------------------------------------------------------
# 1. Norma e material
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DadosMaterial:
    norma: str
    fy_MPa: float
    E_MPa: float
    G_MPa: float
    material_id: str | None


def formulario_material() -> DadosMaterial:
    try:
        nomes_materiais = mat.listar_nomes()
    except (FileNotFoundError, ValueError) as erro:
        st.error(f"Não foi possível carregar a base de materiais: {erro}", icon=":material/error:")
        st.stop()
    projeto_ativo = obter_projeto_ativo()
    materiais_projeto = (projeto_ativo or {}).get("materiais_projeto", [])
    opcoes: dict[str, str] = {"manual": "— entrada manual —"}
    for item in materiais_projeto:
        opcoes[f"projeto::{item['id']}"] = (
            f"Projeto · {item.get('nome')} · {avaliar_material(item)['nivel']}"
        )
    for nome in nomes_materiais:
        opcoes[f"catalogo::{nome}"] = f"Catálogo orientativo · {nome}"
    if st.session_state.get("col_material_escolha") not in opcoes:
        st.session_state["col_material_escolha"] = "manual"

    with st.container(border=True):
        st.subheader("1. Norma e material", help=AJUDA["sec_1"])
        linha = st.columns([3, 3, 2])
        with linha[0]:
            norma = st.selectbox(
                "Norma",
                list(cb.NORMAS),
                format_func=lambda n: cb.NORMAS_ROTULOS[n],
                key="col_norma",
                persist_state="session",
                help=AJUDA["norma"],
            )
        with linha[1]:
            escolha_id = st.selectbox(
                "Material de referência (opcional, só para f_y)",
                list(opcoes),
                format_func=lambda valor: opcoes[valor],
                key="col_material_escolha",
                persist_state="session",
                help=AJUDA["material"],
            )
        with linha[2]:
            if norma == "AISC360_16_LRFD":
                st.metric("Fator φ", "0.90", border=True, help=AJUDA["m_resistencia"])
            else:
                st.metric(
                    "Fator 1/γ_a1",
                    f"{1.0 / cb.GAMMA_A1:.3f}",
                    border=True,
                    help=AJUDA["m_resistencia"],
                )
        material_id: str | None = None
        dados_material: Mapping[str, Any] | None = None
        if escolha_id.startswith("projeto::"):
            material_id = escolha_id.split("::", 1)[1]
            material_projeto = next(item for item in materiais_projeto if item["id"] == material_id)
            props = material_projeto.get("propriedades", {})
            dados_material = {
                "Sy_MPa": props.get("Sy_MPa") or 0.0,
                "observacao": resumir_fonte(material_projeto),
            }
        elif escolha_id.startswith("catalogo::"):
            dados_material = mat.obter_material(escolha_id.split("::", 1)[1])
        sy_padrao = (
            float(dados_material["Sy_MPa"])
            if dados_material and dados_material.get("Sy_MPa")
            else 250.0
        )

        propriedades = st.columns(3)
        fy = _numero(
            "Resistência ao escoamento f_y (MPa)",
            f"col_fy_{escolha_id}",
            sy_padrao,
            AJUDA["fy"],
            passo=10.0,
            alvo=propriedades[0],
        )
        modulo_e = _numero(
            "Módulo de elasticidade E (MPa)",
            "col_E",
            E_ACO,
            AJUDA["E"],
            passo=1_000.0,
            alvo=propriedades[1],
        )
        modulo_g = _numero(
            "Módulo de cisalhamento G (MPa)",
            "col_G",
            G_ACO,
            AJUDA["G"],
            passo=1_000.0,
            alvo=propriedades[2],
        )
        if dados_material:
            st.caption(
                f"f_y de referência: {sy_padrao:.0f} MPa — "
                f"{dados_material.get('observacao', 'catálogo orientativo')}."
            )
    return DadosMaterial(norma, fy, modulo_e, modulo_g, material_id)


# ---------------------------------------------------------------------------
# 2. Seção
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DadosSecao:
    secao: Secao
    tipo_escolhido: str
    soldado: bool
    confirmada: bool


def _paredes_da_secao_generica() -> list[dict[str, Any]]:
    st.markdown("**Paredes da seção (flambagem local)**", help=AJUDA["paredes"])
    quantidade = int(
        st.number_input(
            "Tipos de parede para a flambagem local",
            min_value=0,
            max_value=MAX_PAREDES,
            value=0,
            step=1,
            key="col_gen_npar",
            persist_state="session",
            help=AJUDA["par_quantidade"],
        )
    )
    paredes: list[dict[str, Any]] = []
    for i in range(1, quantidade + 1):
        linha = st.columns([3, 1, 1, 1, 1])
        rotulo = linha[0].selectbox(
            f"Parede {i} — tipo e grupo",
            list(PAREDES),
            index=3,
            key=f"col_par_tipo_{i}",
            persist_state="session",
            help=AJUDA["par_tipo"],
        )
        tipo, grupo = PAREDES[rotulo]
        parede: dict[str, Any] = {
            "tipo": tipo,
            "grupo": grupo,
            "b": _numero(
                f"b da parede {i} (mm)", f"col_par_b_{i}", 50.0, AJUDA["par_b"], alvo=linha[1]
            ),
            "t": _numero(
                f"t da parede {i} (mm)", f"col_par_t_{i}", 8.0, AJUDA["par_t"], alvo=linha[2]
            ),
            "n": int(
                linha[3].number_input(
                    f"Quantidade {i}",
                    min_value=1,
                    value=1,
                    step=1,
                    key=f"col_par_n_{i}",
                    persist_state="session",
                    help=AJUDA["par_n"],
                )
            ),
        }
        if grupo == 5:
            parede["kc"] = _numero(
                f"k_c da parede {i}",
                f"col_par_kc_{i}",
                0.5,
                AJUDA["par_kc"],
                minimo=0.35,
                maximo=0.76,
                passo=0.01,
                alvo=linha[4],
            )
        paredes.append(parede)
    return paredes


def _secao_generica() -> Secao:
    nome = st.text_input(
        "Nome da seção",
        value="Seção genérica",
        key="col_gen_nome",
        persist_state="session",
        help=AJUDA["gen_nome"],
    )
    linha1 = st.columns(3)
    area = _numero(
        "Área A (mm²)", "col_gen_A", 5_000.0, AJUDA["gen_A"], formato="%g", alvo=linha1[0]
    )
    ix = _numero("I_x (mm⁴)", "col_gen_Ix", 1e8, AJUDA["gen_Ix"], formato="%g", alvo=linha1[1])
    iy = _numero("I_y (mm⁴)", "col_gen_Iy", 1e7, AJUDA["gen_Iy"], formato="%g", alvo=linha1[2])
    linha2 = st.columns(4)
    j = _numero(
        "J (mm⁴)", "col_gen_J", 0.0, AJUDA["gen_J"], minimo=0.0, formato="%g", alvo=linha2[0]
    )
    cw = _numero(
        "C_w (mm⁶)", "col_gen_Cw", 0.0, AJUDA["gen_Cw"], minimo=0.0, formato="%g", alvo=linha2[1]
    )
    x0 = _numero(
        "x₀ (mm)", "col_gen_x0", 0.0, AJUDA["gen_x0"], minimo=None, formato="%g", alvo=linha2[2]
    )
    y0 = _numero(
        "y₀ (mm)", "col_gen_y0", 0.0, AJUDA["gen_y0"], minimo=None, formato="%g", alvo=linha2[3]
    )
    linha3 = st.columns(4)
    wx = _numero(
        "W_x (mm³)", "col_gen_Wx", 0.0, AJUDA["gen_Wx"], minimo=0.0, formato="%g", alvo=linha3[0]
    )
    wy = _numero(
        "W_y (mm³)", "col_gen_Wy", 0.0, AJUDA["gen_Wy"], minimo=0.0, formato="%g", alvo=linha3[1]
    )
    zx = _numero(
        "Z_x (mm³)", "col_gen_Zx", 0.0, AJUDA["gen_Zx"], minimo=0.0, formato="%g", alvo=linha3[2]
    )
    zy = _numero(
        "Z_y (mm³)", "col_gen_Zy", 0.0, AJUDA["gen_Zy"], minimo=0.0, formato="%g", alvo=linha3[3]
    )
    torcao = st.toggle(
        "A torção pode governar (perfil aberto de parede fina)",
        value=True,
        key="col_gen_torcao",
        persist_state="session",
        help=AJUDA["gen_torcao"],
    )
    paredes = _paredes_da_secao_generica()
    return cb.secao_informada(
        nome,
        area,
        ix,
        iy,
        J_mm4=j,
        Cw_mm6=cw,
        x0_mm=x0,
        y0_mm=y0,
        Wx_mm3=wx,
        Wy_mm3=wy,
        Zx_mm3=zx,
        Zy_mm3=zy,
        elementos=paredes,
        torcao_relevante=torcao,
    )


def _campos_da_secao(tipo: str) -> tuple[Secao, bool]:
    """Desenha os campos do tipo escolhido e devolve a seção (e se o perfil é soldado)."""
    if tipo == SEC_CATALOGO:
        linha = st.columns([3, 1])
        nome = linha[0].selectbox(
            "Perfil",
            list(catalogo_perfis.listar_perfis()),
            key="col_perfil",
            persist_state="session",
            help=AJUDA["perfil"],
        )
        soldado = linha[1].toggle(
            "Perfil soldado",
            value=False,
            key="col_soldado",
            persist_state="session",
            help=AJUDA["soldado"],
        )
        perfil = catalogo_perfis.obter_perfil(nome)
        return cb.secao_de_perfil(perfil, soldado=soldado), soldado
    if tipo == SEC_CIRC:
        d = _numero("Diâmetro d (mm)", "col_circ_d", 50.0, AJUDA["dim_d_circ"], passo=5.0)
        return cb.secao_por_dimensoes("circular_macica", d=d), False
    if tipo == SEC_RET:
        linha = st.columns(2)
        b = _numero(
            "Largura b (mm)", "col_ret_b", 50.0, AJUDA["dim_b_ret"], passo=5.0, alvo=linha[0]
        )
        h = _numero(
            "Altura h (mm)", "col_ret_h", 100.0, AJUDA["dim_h_ret"], passo=5.0, alvo=linha[1]
        )
        return cb.secao_por_dimensoes("retangular_macica", b=b, h=h), False
    if tipo == SEC_TUBO_C:
        linha = st.columns(2)
        diametro = _numero(
            "Diâmetro externo D (mm)",
            "col_tc_D",
            60.0,
            AJUDA["dim_D_tubo"],
            passo=5.0,
            alvo=linha[0],
        )
        espessura = _numero(
            "Espessura t (mm)", "col_tc_t", 4.0, AJUDA["dim_t_tubo"], passo=0.5, alvo=linha[1]
        )
        return cb.secao_por_dimensoes("tubo_circular", D=diametro, t=espessura), False
    if tipo == SEC_TUBO_R:
        linha = st.columns(3)
        largura = _numero(
            "Largura B (mm)", "col_tr_B", 100.0, AJUDA["dim_B_tr"], passo=5.0, alvo=linha[0]
        )
        altura = _numero(
            "Altura H (mm)", "col_tr_H", 150.0, AJUDA["dim_H_tr"], passo=5.0, alvo=linha[1]
        )
        espessura = _numero(
            "Espessura t (mm)", "col_tr_t", 5.0, AJUDA["dim_t_tr"], passo=0.5, alvo=linha[2]
        )
        return cb.secao_por_dimensoes("tubo_retangular", B=largura, H=altura, t=espessura), False
    if tipo in (SEC_I, SEC_U):
        letra = "I" if tipo == SEC_I else "U"
        padrao = (300.0, 150.0, 12.5, 8.0) if letra == "I" else (152.4, 48.8, 8.71, 5.08)
        linha = st.columns(4)
        d = _numero(
            "Altura total d (mm)",
            f"col_{letra}_d",
            padrao[0],
            AJUDA["dim_d_perfil"],
            passo=5.0,
            alvo=linha[0],
        )
        bf = _numero(
            "Largura da mesa b_f (mm)",
            f"col_{letra}_bf",
            padrao[1],
            AJUDA["dim_bf"],
            passo=5.0,
            alvo=linha[1],
        )
        tf = _numero(
            "Espessura da mesa t_f (mm)",
            f"col_{letra}_tf",
            padrao[2],
            AJUDA["dim_tf"],
            passo=0.5,
            alvo=linha[2],
        )
        tw = _numero(
            "Espessura da alma t_w (mm)",
            f"col_{letra}_tw",
            padrao[3],
            AJUDA["dim_tw"],
            passo=0.5,
            alvo=linha[3],
        )
        soldado = st.toggle(
            "Perfil soldado",
            value=False,
            key=f"col_soldado_{letra}",
            persist_state="session",
            help=AJUDA["soldado"],
        )
        if soldado:
            st.caption(AVISO_IDEALIZADO_SOLDADO)
        else:
            st.warning(AVISO_IDEALIZADO_LAMINADO, icon=":material/warning:")
        return cb.secao_por_dimensoes(letra, soldado=soldado, d=d, bf=bf, tf=tf, tw=tw), soldado
    if tipo == SEC_DIRETA:
        linha = st.columns(3)
        area = _numero(
            "Área A (mm²)", "col_direta_A", 1_000.0, AJUDA["direta_A"], passo=50.0, alvo=linha[0]
        )
        rx = _numero(
            "Raio de giração rx (mm)",
            "col_direta_rx",
            15.0,
            AJUDA["direta_rx"],
            passo=1.0,
            alvo=linha[1],
        )
        mesmo_raio = linha[2].checkbox(
            "ry = rx (mesmo raio nos dois eixos)",
            value=True,
            key="col_direta_mesmo_raio",
            persist_state="session",
            help=AJUDA["direta_mesmo_raio"],
        )
        ry = (
            rx
            if mesmo_raio
            else _numero(
                "Raio de giração ry (mm)", "col_direta_ry", rx, AJUDA["direta_ry"], passo=1.0
            )
        )
        fibras = st.columns(2)
        cx = _numero(
            "c em x — centroide à fibra extrema (mm, só para flexão)",
            "col_direta_cx",
            0.0,
            AJUDA["direta_cx"],
            minimo=0.0,
            passo=1.0,
            alvo=fibras[0],
        )
        cy = _numero(
            "c em y — centroide à fibra extrema (mm, só para flexão)",
            "col_direta_cy",
            0.0,
            AJUDA["direta_cy"],
            minimo=0.0,
            passo=1.0,
            alvo=fibras[1],
        )
        secao = cb.secao_direta(area, rx, ry, distancia_fibra_x_mm=cx, distancia_fibra_y_mm=cy)
        return secao, False
    return _secao_generica(), False


def formulario_secao() -> DadosSecao:
    with st.container(border=True):
        st.subheader("2. Seção da coluna", help=AJUDA["sec_2"])
        tipo = st.selectbox(
            "Tipo de seção",
            TIPOS_SECAO,
            index=TIPOS_SECAO.index(SEC_CIRC),
            key="col_tipo_secao",
            persist_state="session",
            help=AJUDA["tipo_secao"],
        )
        try:
            secao, soldado = _campos_da_secao(tipo)
        except ValueError as erro:
            st.error(str(erro), icon=":material/error:")
            st.stop()
        st.caption(f":material/info: {secao.nome}")
        with st.container(horizontal=True):
            st.metric("Área A", f"{secao.A:.0f} mm²", border=True, help=AJUDA["m_area"])
            st.metric("rx", f"{secao.rx:.1f} mm", border=True, help=AJUDA["m_rx"])
            st.metric("ry", f"{secao.ry:.1f} mm", border=True, help=AJUDA["m_ry"])
            st.metric("J", f"{secao.J / 1e3:.1f} ×10³ mm⁴", border=True, help=AJUDA["m_J"])
        confirmada = False
        if secao.tipo == "generica":
            aviso = secao.dims.get("aviso")
            if aviso:
                st.warning(str(aviso).capitalize(), icon=":material/warning:")
            confirmada = st.checkbox(
                "Confirmo: a seção é compacta e a torção não governa",
                value=False,
                key="col_confirma",
                persist_state="session",
                help=AJUDA["confirma_compacta"],
            )
            if not confirmada:
                st.info(
                    "Sem as paredes (b/t) e as constantes de torção, a norma não pode ser aplicada "
                    "por completo: o resultado fica em ALERTA, nunca em OK. Informe as paredes ou "
                    "confirme acima, depois de conferir fora do programa.",
                    icon=":material/info:",
                )
    return DadosSecao(secao, tipo, soldado, confirmada)


# ---------------------------------------------------------------------------
# 3. Comprimentos e apoio
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DadosComprimentos:
    L_total_mm: float
    Lx_mm: float
    Ly_mm: float
    kx: float
    ky: float
    apoio_x: str
    apoio_y: str
    k_recomendado: bool
    Lz_mm: float | None
    kz: float | None


def _apoio(eixo: str, k_recomendado: bool) -> tuple[str, float]:
    x = eixo == "x"
    apoio = st.selectbox(
        f"Condição de apoio — flexão em torno de {eixo} (Tabela E.1)",
        [*cb.CONDICOES_APOIO, APOIO_MANUAL],
        key=f"col_apoio_{eixo}",
        persist_state="session",
        help=AJUDA["apoio_x"] if x else AJUDA["apoio_y"],
    )
    if apoio == APOIO_MANUAL:
        k = _numero(
            f"K{eixo}",
            f"col_k{eixo}_manual",
            1.0,
            AJUDA["Kx_manual"] if x else AJUDA["Ky_manual"],
            minimo=0.01,
            passo=0.05,
        )
    else:
        tabela = cb.CONDICOES_APOIO_RECOMENDADAS if k_recomendado else cb.CONDICOES_APOIO
        k = tabela[apoio]
    return apoio, k


def formulario_comprimentos() -> DadosComprimentos:
    with st.container(border=True):
        st.subheader("3. Comprimentos e apoio — os dois eixos de uma vez", help=AJUDA["sec_3"])
        topo = st.columns([2, 3])
        comprimento = _numero(
            "Comprimento total da coluna L (mm)",
            "col_L",
            2_000.0,
            AJUDA["L_total"],
            passo=100.0,
            alvo=topo[0],
        )
        mesmo = topo[1].toggle(
            "Mesmo comprimento destravado nos dois eixos",
            value=True,
            key="col_mesmo_L",
            persist_state="session",
            help=AJUDA["mesmo_L"],
        )
        if mesmo:
            lx = ly = comprimento
        else:
            destravados = st.columns(2)
            lx = _numero(
                "Comprimento destravado Lx (mm)",
                "col_Lx",
                comprimento,
                AJUDA["Lx"],
                passo=100.0,
                alvo=destravados[0],
            )
            ly = _numero(
                "Comprimento destravado Ly (mm)",
                "col_Ly",
                comprimento,
                AJUDA["Ly"],
                passo=100.0,
                alvo=destravados[1],
            )
        k_recomendado = st.toggle(
            "Usar o K recomendado para projeto (em vez do teórico)",
            value=True,
            key="col_k_recomendado",
            persist_state="session",
            help=AJUDA["k_recomendado"],
        )
        apoios = st.columns(2)
        with apoios[0]:
            apoio_x, kx = _apoio("x", k_recomendado)
        with apoios[1]:
            apoio_y, ky = _apoio("y", k_recomendado)
        st.caption(
            f"K_x·L_x = {kx:.2f} × {lx:.0f} = **{kx * lx:.0f} mm** · "
            f"K_y·L_y = {ky:.2f} × {ly:.0f} = **{ky * ly:.0f} mm** "
            f"({'K recomendado para projeto' if k_recomendado else 'K teórico'}, "
            "exceto onde o K foi informado)."
        )
        torcao_propria = st.toggle(
            "Torção com travamento próprio (informar K_z e L_z)",
            value=False,
            key="col_kz_ativar",
            persist_state="session",
            help=AJUDA["kz_ativar"],
        )
        kz: float | None = None
        lz: float | None = None
        if torcao_propria:
            torcao = st.columns(2)
            kz = _numero(
                "K_z (torção)",
                "col_Kz",
                1.0,
                AJUDA["Kz"],
                minimo=0.01,
                passo=0.05,
                alvo=torcao[0],
            )
            _acompanhar_padrao("col_Lz", max(lx, ly))
            lz = _numero(
                "L_z (mm)", "col_Lz", max(lx, ly), AJUDA["Lz"], passo=100.0, alvo=torcao[1]
            )
    return DadosComprimentos(comprimento, lx, ly, kx, ky, apoio_x, apoio_y, k_recomendado, lz, kz)


# ---------------------------------------------------------------------------
# 4. Esforços solicitantes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DadosCargas:
    N_Sd_kN: float
    permanente_kN: float | None
    variavel_kN: float | None
    gamma_g: float | None
    gamma_q: float | None
    equacao: str


@dataclass(frozen=True)
class DadosFlexao:
    Mx_kNm: float
    My_kNm: float
    ex_mm: float
    ey_mm: float
    diagrama_x: str
    diagrama_y: str
    razao_x: float | None
    razao_y: float | None
    Lb_mm: float | None
    Cb: float
    momentos_cb: tuple[float, float, float, float] | None
    MRd_x_kNm: float | None
    MRd_y_kNm: float | None


def _cargas() -> DadosCargas:
    modo = st.radio(
        "Como informar a força de compressão",
        [MODO_CARACTERISTICO, MODO_CALCULO],
        key="col_modo_carga",
        persist_state="session",
        horizontal=True,
        help=AJUDA["modo_carga"],
    )
    if modo == MODO_CARACTERISTICO:
        permanente = st.columns(2)
        ng = _numero(
            "Permanente N_g (kN)",
            "col_ng",
            30.0,
            AJUDA["ng"],
            minimo=0.0,
            passo=5.0,
            alvo=permanente[0],
        )
        categoria_g = permanente[1].selectbox(
            "Categoria da permanente (Tabela 1)",
            list(cb.COEFICIENTES_PERMANENTE),
            index=2,
            key="col_cat_g",
            persist_state="session",
            help=AJUDA["cat_g"],
        )
        variavel = st.columns(2)
        nq = _numero(
            "Variável N_q (kN)",
            "col_nq",
            20.0,
            AJUDA["nq"],
            minimo=0.0,
            passo=5.0,
            alvo=variavel[0],
        )
        categoria_q = variavel[1].selectbox(
            "Categoria da variável (Tabela 1)",
            list(cb.COEFICIENTES_VARIAVEL),
            index=1,
            key="col_cat_q",
            persist_state="session",
            help=AJUDA["cat_q"],
        )
        gamma_g = cb.COEFICIENTES_PERMANENTE[categoria_g]
        gamma_q = cb.COEFICIENTES_VARIAVEL[categoria_q]
        n_sd = cb.forca_de_calculo(ng * 1e3, nq * 1e3, gamma_g=gamma_g, gamma_q=gamma_q) / 1e3
        st.caption(
            f"N_Sd = {gamma_g:.2f} × {ng:.1f} + {gamma_q:.2f} × {nq:.1f} = **{n_sd:.2f} kN**. "
            "Para mais de duas ações, ou combinações com ψ, use Casos de carga."
        )
        equacao = (
            f"N_Sd = γ_g·N_g + γ_q·N_q = {gamma_g:.2f}·{ng:.2f} + {gamma_q:.2f}·{nq:.2f} "
            f"= {n_sd:.2f} kN"
        )
        return DadosCargas(n_sd, ng, nq, gamma_g, gamma_q, equacao)
    n_sd = _numero(
        "Força de compressão de cálculo N_Sd (kN)",
        "col_nsd",
        70.0,
        AJUDA["nsd"],
        minimo=0.0,
        passo=5.0,
    )
    return DadosCargas(n_sd, None, None, None, None, f"N_Sd = {n_sd:.2f} kN (de cálculo)")


def _campos_de_flexao(eixo: str) -> tuple[float, float, str, float | None]:
    x = eixo == "x"
    momento = _numero(
        f"M{eixo},Sd (kN·m)",
        f"col_M{eixo}",
        0.0,
        AJUDA["Mx"] if x else AJUDA["My"],
        minimo=0.0,
        passo=1.0,
    )
    excentricidade = _numero(
        f"Excentricidade e{eixo} (mm)",
        f"col_e{eixo}",
        0.0,
        AJUDA["ex"] if x else AJUDA["ey"],
        minimo=0.0,
        passo=1.0,
    )
    diagrama = st.selectbox(
        f"Diagrama de momentos em {eixo} (para C_m)",
        DIAGRAMAS,
        key=f"col_diag_{eixo}",
        persist_state="session",
        help=AJUDA["diagrama_x"] if x else AJUDA["diagrama_y"],
    )
    razao: float | None = None
    if diagrama == DIAG_PONTAS:
        razao = _numero(
            f"M₁/M₂ em {eixo}",
            f"col_razao_{eixo}",
            0.0,
            AJUDA["razao_x"] if x else AJUDA["razao_y"],
            minimo=-1.0,
            maximo=1.0,
            passo=0.1,
        )
    return momento, excentricidade, diagrama, razao


def _flexao() -> DadosFlexao:
    st.markdown(
        "**Flexocompressão** (5.5.1.2) — momentos de cálculo de 1ª ordem em torno de x e de y, "
        "além do que a excentricidade e a mão-francesa geram"
    )
    colunas = st.columns(2)
    with colunas[0]:
        mx, ex, diagrama_x, razao_x = _campos_de_flexao("x")
    with colunas[1]:
        my, ey, diagrama_y, razao_y = _campos_de_flexao("y")

    with st.expander("Flexão em x: travamento lateral (FLT) e C_b", icon=":material/tune:"):
        lb = _numero(
            "L_b para FLT (mm, 0 = igual a Ly)",
            "col_Lb",
            0.0,
            AJUDA["Lb"],
            minimo=0.0,
            passo=100.0,
        )
        modo_cb = st.selectbox(
            "Como obter o C_b",
            [CB_INFORMAR, CB_DIAGRAMA],
            key="col_cb_modo",
            persist_state="session",
            help=AJUDA["cb_modo"],
        )
        cb_valor = 1.0
        momentos: tuple[float, float, float, float] | None = None
        if modo_cb == CB_INFORMAR:
            cb_valor = _numero(
                "C_b", "col_cb", 1.0, AJUDA["cb"], minimo=1.0, maximo=3.0, passo=0.05
            )
        else:
            quatro = st.columns(4)
            m_max = _numero(
                "M_max (kN·m)", "col_cb_Mmax", 10.0, AJUDA["cb_Mmax"], passo=1.0, alvo=quatro[0]
            )
            m_a = _numero(
                "M_A, a ¼ (kN·m)",
                "col_cb_MA",
                10.0,
                AJUDA["cb_MA"],
                minimo=0.0,
                passo=1.0,
                alvo=quatro[1],
            )
            m_b = _numero(
                "M_B, no meio (kN·m)",
                "col_cb_MB",
                10.0,
                AJUDA["cb_MB"],
                minimo=0.0,
                passo=1.0,
                alvo=quatro[2],
            )
            m_c = _numero(
                "M_C, a ¾ (kN·m)",
                "col_cb_MC",
                10.0,
                AJUDA["cb_MC"],
                minimo=0.0,
                passo=1.0,
                alvo=quatro[3],
            )
            momentos = (m_max, m_a, m_b, m_c)

    with st.expander(
        "Momento resistente informado (seção sem rotina de cálculo)", icon=":material/edit_note:"
    ):
        informados = st.columns(2)
        mrd_x: float | None = None
        mrd_y: float | None = None
        with informados[0]:
            if st.toggle(
                "Informar M_x,Rd",
                value=False,
                key="col_mrd_x_ativar",
                persist_state="session",
                help=AJUDA["mrd_x_ativar"],
            ):
                mrd_x = _numero("M_x,Rd (kN·m)", "col_mrd_x", 100.0, AJUDA["mrd_x"], passo=5.0)
        with informados[1]:
            if st.toggle(
                "Informar M_y,Rd",
                value=False,
                key="col_mrd_y_ativar",
                persist_state="session",
                help=AJUDA["mrd_y_ativar"],
            ):
                mrd_y = _numero("M_y,Rd (kN·m)", "col_mrd_y", 100.0, AJUDA["mrd_y"], passo=5.0)
    return DadosFlexao(
        mx, my, ex, ey, diagrama_x, diagrama_y, razao_x, razao_y,
        lb if lb > 0 else None, cb_valor, momentos, mrd_x, mrd_y,
    )  # fmt: skip


def formulario_esforcos() -> tuple[DadosCargas, DadosFlexao]:
    with st.container(border=True):
        st.subheader("4. Esforços solicitantes de cálculo", help=AJUDA["sec_4"])
        cargas = _cargas()
        flexao = _flexao()
    return cargas, flexao


# ---------------------------------------------------------------------------
# 5. Mão-francesa
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DadosMaoFrancesa:
    esforcos: cb.EsforcosMaoFrancesa | None
    eixo: str | None
    somar_v: bool
    forca_kN: float | None
    gamma: float | None


def _distancia_fibra(secao: Secao, eixo: str) -> float:
    modulo = secao.Wx if eixo == "x" else secao.Wy
    inercia = secao.Ix if eixo == "x" else secao.Iy
    return inercia / modulo if modulo else 0.0


def formulario_mao_francesa(secao: Secao, comprimento_mm: float) -> DadosMaoFrancesa:
    with st.container(border=True):
        st.subheader("5. Mão-francesa (força inclinada chegando na coluna)", help=AJUDA["sec_5"])
        st.caption(
            "A mão-francesa descarrega na coluna uma força inclinada: a componente horizontal H "
            "flete a coluna (M = H × braço) e a vertical V comprime. O momento calculado aqui é "
            "somado ao do eixo que ela flete e entra na interação N + M — sem isto ele é ignorado."
        )
        incluir = st.toggle(
            "Incluir a mão-francesa nesta verificação",
            value=False,
            key="col_mf_incluir",
            persist_state="session",
            help=AJUDA["mf_incluir"],
        )
        if not incluir:
            return DadosMaoFrancesa(None, None, False, None, None)

        if st.session_state.get("col_mf_altura", 0.0) > comprimento_mm:
            st.session_state["col_mf_altura"] = float(comprimento_mm)
        linha = st.columns(4)
        forca = _numero(
            "Força na mão-francesa F (kN)",
            "col_mf_forca",
            20.0,
            AJUDA["mf_forca"],
            minimo=0.0,
            passo=1.0,
            alvo=linha[0],
        )
        opcoes_gamma = {"Já é de cálculo (γ = 1,00)": 1.0, **cb.COEFICIENTES_VARIAVEL}
        rotulo_gamma = linha[1].selectbox(
            "Majoração de F",
            list(opcoes_gamma),
            index=2,
            key="col_mf_gamma",
            persist_state="session",
            help=AJUDA["mf_gamma"],
        )
        gamma = opcoes_gamma[rotulo_gamma]
        angulo = _numero(
            "Ângulo θ com a coluna (°)",
            "col_mf_angulo",
            45.0,
            AJUDA["mf_angulo"],
            minimo=1.0,
            maximo=89.0,
            passo=5.0,
            alvo=linha[2],
        )
        altura = _numero(
            "Altura do nó a (mm, medida da base)",
            "col_mf_altura",
            min(comprimento_mm, 800.0),
            AJUDA["mf_altura"],
            minimo=min(1.0, float(comprimento_mm)),
            maximo=float(comprimento_mm),
            passo=50.0,
            alvo=linha[3],
        )
        detalhes = st.columns([2, 1, 1, 1])
        vinculo = detalhes[0].selectbox(
            "Vínculo da coluna no plano da mão-francesa",
            list(cb.VINCULOS_MAO_FRANCESA),
            key="col_mf_vinculo",
            persist_state="session",
            help=AJUDA["mf_vinculo"],
        )
        eixo = detalhes[1].selectbox(
            "Eixo que ela flete",
            ["x", "y"],
            key="col_mf_eixo",
            persist_state="session",
            help=AJUDA["mf_eixo"],
        )
        padrao_excentricidade = round(_distancia_fibra(secao, eixo), 1)
        _acompanhar_padrao(f"col_mf_e_{eixo}", padrao_excentricidade)
        excentricidade = _numero(
            "e da ligação (mm)",
            f"col_mf_e_{eixo}",
            padrao_excentricidade,
            AJUDA["mf_exc"],
            minimo=0.0,
            passo=1.0,
            alvo=detalhes[2],
        )
        somar_v = detalhes[3].checkbox(
            "Somar V a N_Sd",
            value=False,
            key="col_mf_somar_v",
            persist_state="session",
            help=AJUDA["mf_somar_v"],
        )
        try:
            esforcos = cb.esforcos_mao_francesa(
                forca * 1e3 * gamma, angulo, altura, comprimento_mm, vinculo, excentricidade
            )
        except ValueError as erro:
            st.error(str(erro), icon=":material/error:")
            st.stop()
        with st.container(horizontal=True):
            st.metric(
                "F_Sd",
                f"{esforcos.forca_N / 1e3:.2f} kN",
                border=True,
                help=f"{AJUDA['mf_metrica']} F × γ = {forca:.2f} × {gamma:.2f}.",
            )
            st.metric(
                "H = F·sen θ",
                f"{esforcos.componente_horizontal_N / 1e3:.2f} kN",
                border=True,
                help=AJUDA["mf_metrica"],
            )
            st.metric(
                "V = F·cos θ",
                f"{esforcos.componente_vertical_N / 1e3:.2f} kN",
                border=True,
                help=AJUDA["mf_metrica"],
            )
            st.metric(
                f"M_{eixo},Sd da mão-francesa",
                f"{esforcos.momento_Nmm / 1e6:.3f} kN·m",
                border=True,
                help=f"{AJUDA['mf_metrica']} {esforcos.expressao}",
            )
        st.caption(
            f"{esforcos.expressao}: H = {esforcos.componente_horizontal_N / 1e3:.2f} kN, "
            f"a = {esforcos.altura_no_mm:.0f} mm, L = {comprimento_mm:.0f} mm → "
            f"M_H = {esforcos.momento_horizontal_Nmm / 1e6:.3f} kN·m"
            + (
                f"; V·e = {esforcos.componente_vertical_N / 1e3:.2f} × "
                f"{esforcos.excentricidade_mm:.1f} mm = "
                f"{esforcos.momento_excentricidade_Nmm / 1e6:.3f} kN·m"
                if esforcos.momento_excentricidade_Nmm > 0
                else ""
            )
            + f". O momento é somado a M_{eixo},Sd e a força horizontal conta como força "
            "transversal entre os apoios (C_m = 1,0)."
        )
    return DadosMaoFrancesa(esforcos, eixo, somar_v, forca, gamma)


# ---------------------------------------------------------------------------
# 6. Critério Anglo
# ---------------------------------------------------------------------------


def formulario_anglo(secao: Secao, soldado: bool) -> dict[str, float]:
    espessuras: dict[str, float] = {}
    with st.container(border=True):
        st.subheader("6. Critério Anglo — esbeltez e espessuras mínimas", help=AJUDA["sec_6"])
        categoria, espessura = cb.categoria_espessura_anglo(secao, soldado)
        if categoria and espessura:
            espessuras[categoria] = espessura
            minimo = ESPESSURA_MIN_ANGLO[categoria]
            st.metric(
                "Menor espessura de parede do perfil",
                f"{espessura:g} mm",
                border=True,
                help=AJUDA["anglo_espessura_auto"],
            )
            st.caption(
                f"Categoria {cb.ROTULOS_ESPESSURA_ANGLO[categoria]}: mínimo de {minimo:g} mm "
                "(Anglo 8.8)."
            )
        else:
            st.caption(
                "A Anglo (8.8) não traz espessura mínima para este tipo de seção; a esbeltez "
                "máxima de 200 (8.3) é sempre verificada."
            )
        with st.expander("Outras partes ligadas à coluna (opcional)", icon=":material/layers:"):
            outras = st.columns(3)
            for rotulo, chave, categoria_extra, ajuda, coluna in (
                (
                    "Chapa de ligação ou enrijecedor (mm)",
                    "col_esp_chapa",
                    "chapa_ligacao_enrijecedor",
                    AJUDA["anglo_chapa"],
                    outras[0],
                ),
                (
                    "Cantoneira (mm)",
                    "col_esp_cantoneira",
                    "cantoneira",
                    AJUDA["anglo_cantoneira"],
                    outras[1],
                ),
                (
                    "Placa de base (mm)",
                    "col_esp_placa",
                    "placa_base",
                    AJUDA["anglo_placa"],
                    outras[2],
                ),
            ):
                valor = _numero(rotulo, chave, 0.0, ajuda, minimo=0.0, passo=0.5, alvo=coluna)
                if valor > 0:
                    espessuras[categoria_extra] = valor
    return espessuras


# ---------------------------------------------------------------------------
# Montagem da entrada
# ---------------------------------------------------------------------------


def montar_entrada(
    material: DadosMaterial,
    secao: DadosSecao,
    comprimentos: DadosComprimentos,
    cargas: DadosCargas,
    flexao: DadosFlexao,
    mao_francesa: DadosMaoFrancesa,
    espessuras: Mapping[str, float],
) -> cb.EntradaColuna:
    mf = mao_francesa.esforcos
    momento_mf = mf.momento_Nmm / 1e6 if mf is not None else 0.0
    n_sd = cargas.N_Sd_kN
    if mf is not None and mao_francesa.somar_v:
        n_sd += mf.componente_vertical_N / 1e3
    mf_em_x = mf is not None and mao_francesa.eixo == "x"
    mf_em_y = mf is not None and mao_francesa.eixo == "y"
    return cb.EntradaColuna(
        secao=secao.secao,
        fy_MPa=material.fy_MPa,
        norma=material.norma,
        E_MPa=material.E_MPa,
        G_MPa=material.G_MPa,
        Lx_mm=comprimentos.Lx_mm,
        Ly_mm=comprimentos.Ly_mm,
        kx=comprimentos.kx,
        ky=comprimentos.ky,
        Lz_mm=comprimentos.Lz_mm,
        kz=comprimentos.kz,
        N_Sd_kN=n_sd,
        Mx_kNm=flexao.Mx_kNm,
        My_kNm=flexao.My_kNm,
        ex_mm=flexao.ex_mm,
        ey_mm=flexao.ey_mm,
        Mx_mao_francesa_kNm=momento_mf if mf_em_x else 0.0,
        My_mao_francesa_kNm=momento_mf if mf_em_y else 0.0,
        razao_m1_m2_x=flexao.razao_x,
        razao_m1_m2_y=flexao.razao_y,
        forcas_transversais_x=flexao.diagrama_x == DIAG_TRANSVERSAL or mf_em_x,
        forcas_transversais_y=flexao.diagrama_y == DIAG_TRANSVERSAL or mf_em_y,
        Lb_mm=flexao.Lb_mm,
        Cb=flexao.Cb,
        momentos_cb_kNm=flexao.momentos_cb,
        MRd_x_informado_kNm=flexao.MRd_x_kNm,
        MRd_y_informado_kNm=flexao.MRd_y_kNm,
        secao_compacta_confirmada=secao.confirmada,
        espessuras_anglo=dict(espessuras) or None,
        com_mao_francesa=mf is not None,
    )


# ---------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------


def _resumo(entrada: cb.EntradaColuna, resultado: cb.ResultadoColuna) -> None:
    comp = resultado.compressao
    sec = entrada.secao
    with st.container(border=True):
        st.subheader("Resumo", help=AJUDA["res_resumo"])
        st.badge(
            f"Status geral: {resultado.status_geral}",
            color=COR_BADGE[resultado.status_geral],
            icon=":material/verified:" if resultado.status_geral == "OK" else ":material/rule:",
            help=AJUDA["res_status"],
        )
        with st.container(horizontal=True):
            st.metric(
                "Aproveitamento máximo",
                formatar_percentual(resultado.aproveitamento_max),
                border=True,
                help=AJUDA["res_aproveitamento"],
            )
            if comp is not None:
                st.metric("N_c,Rd", f"{comp['Nc_Rd']:.2f} kN", border=True, help=AJUDA["res_nc"])
            st.metric("N_Sd", f"{entrada.N_Sd_kN:.2f} kN", border=True, help=AJUDA["res_nsd"])
        lam_x = entrada.kx * entrada.Lx_mm / sec.rx
        lam_y = entrada.ky * entrada.Ly_mm / sec.ry
        with st.container(horizontal=True):
            st.metric("λx = Kx·Lx/rx", f"{lam_x:.1f}", border=True, help=AJUDA["res_lx"])
            st.metric("λy = Ky·Ly/ry", f"{lam_y:.1f}", border=True, help=AJUDA["res_ly"])
            if comp is not None:
                ajuda_ne = (
                    AJUDA["res_ne"] + f"\n\nModo que governa nesta coluna: **{comp['modo']}**."
                )
                st.metric("N_e adotado", f"{comp['Ne']:.1f} kN", border=True, help=ajuda_ne)
                st.metric("χ", f"{comp['chi']:.3f}", border=True, help=AJUDA["res_chi"])
                st.metric(
                    "Q = Q_s·Q_a" if entrada.norma == "NBR8800_2008" else "A_ef/A_g",
                    f"{comp['Q']:.3f}",
                    border=True,
                    help=AJUDA["res_q"],
                )
        tem_mx = resultado.momento_x_primeira_ordem_kNm > 0
        tem_my = resultado.momento_y_primeira_ordem_kNm > 0
        if tem_mx or tem_my:
            with st.container(horizontal=True):
                for eixo, tem, b1, amplificado, mrd, da_norma in (
                    ("x", tem_mx, resultado.b1_x, resultado.momento_x_amplificado_kNm, resultado.mrd_x_kNm, resultado.flexao_x is not None),
                    ("y", tem_my, resultado.b1_y, resultado.momento_y_amplificado_kNm, resultado.mrd_y_kNm, resultado.flexao_y is not None),
                ):  # fmt: skip
                    if not tem:
                        continue
                    st.metric(f"B₁ em {eixo}", _fmt(b1), border=True, help=AJUDA["res_b1"])
                    st.metric(
                        f"M_{eixo},Sd amplificado",
                        _fmt(amplificado, 3, " kN·m"),
                        border=True,
                        help=AJUDA["res_b1"],
                    )
                    st.metric(
                        f"M_{eixo},Rd",
                        "—"
                        if mrd is None
                        else _fmt(mrd, 3, " kN·m" if da_norma else " kN·m (informado)"),
                        border=True,
                        help=AJUDA["res_mrd"],
                    )
                if resultado.indice_interacao is not None:
                    st.metric(
                        "Índice de interação",
                        _fmt(resultado.indice_interacao),
                        border=True,
                        help=AJUDA["res_interacao"],
                    )
        st.markdown(f"**Verificação que governa:** {resultado.governante}")


def _tabela(resultado: cb.ResultadoColuna) -> None:
    with st.container(border=True):
        st.subheader("Tabela de verificações", help=AJUDA["res_tabela"])
        mostrar_tabela_verificacoes(resultado.verificacoes)
        st.download_button(
            "Baixar verificações em CSV",
            data=csv_verificacoes(resultado.verificacoes),
            file_name="flambagem_colunas.csv",
            mime="text/csv",
            icon=":material/download:",
            width="stretch",
            key="col_baixar_csv",
            help=AJUDA["btn_csv"],
        )
        with st.expander(
            "Fórmula e item da norma de cada verificação", icon=":material/functions:"
        ):
            for v in resultado.verificacoes:
                st.markdown(f"**{v.nome}** — `{v.status}` · {v.referencia}")
                if v.formula:
                    st.caption(v.formula)


def _paredes(entrada: cb.EntradaColuna, resultado: cb.ResultadoColuna) -> None:
    comp = resultado.compressao
    if comp is None or not entrada.secao.elementos:
        return
    linhas = cb.tabela_elementos(entrada.secao, entrada.fy_MPa, entrada.norma, comp, entrada.E_MPa)
    tabela = pd.DataFrame([{k: v for k, v in linha.items() if k != "nome"} for linha in linhas])
    with st.container(border=True):
        st.subheader("Paredes da seção — flambagem local", help=AJUDA["res_paredes"])
        st.dataframe(
            tabela,
            hide_index=True,
            width="stretch",
            column_config={
                "b (mm)": st.column_config.NumberColumn(format="%.1f"),
                "t (mm)": st.column_config.NumberColumn(format="%.2f"),
                "b/t": st.column_config.NumberColumn(format="%.1f"),
                "(b/t) lim": st.column_config.NumberColumn(format="%.1f"),
                "Q_s": st.column_config.NumberColumn(format="%.3f"),
                "b_ef (mm)": st.column_config.NumberColumn(format="%.1f"),
            },
        )
        st.caption(
            "Esbelto = b/t acima do limite da Tabela 4. Na NBR 2008, Q_s vale para elemento livre "
            "(AL) e b_ef para elemento apoiado (AA); no Projeto 2024 e no AISC todos usam b_ef."
        )


def _comparar_normas(entrada: cb.EntradaColuna) -> None:
    if st.button(
        "Comparar normas",
        icon=":material/compare_arrows:",
        width="stretch",
        key="col_btn_comparar",
        help=AJUDA["btn_comparar"],
    ):
        st.session_state["col_ver_comparacao"] = not st.session_state.get(
            "col_ver_comparacao", False
        )
    if not st.session_state.get("col_ver_comparacao"):
        return
    with st.container(border=True):
        st.markdown("**Mesma coluna nas três normas**")
        linhas = [
            {
                "Norma": item["rotulo"],
                "Status": item["status"],
                "Aproveitamento máx. (%)": (
                    None
                    if item.get("aproveitamento_max") is None
                    else 100 * item["aproveitamento_max"]
                ),
                "Governa": item.get("governante", ""),
                "N_c,Rd (kN)": item.get("Nc_Rd_kN"),
                "Q ou A_ef/A_g": item.get("fator_Q"),
                "χ": item.get("chi"),
                "M_x,Rd (kN·m)": item.get("MRd_x_kNm"),
                "M_y,Rd (kN·m)": item.get("MRd_y_kNm"),
                "Interação": item.get("indice_interacao"),
                "Observação": item.get("erro", ""),
            }
            for item in cb.comparar_normas(entrada)
        ]
        estilo = estilizar(
            pd.DataFrame(linhas),
            {
                "Aproveitamento máx. (%)": "{:.0f}",
                "N_c,Rd (kN)": "{:.1f}",
                "Q ou A_ef/A_g": "{:.3f}",
                "χ": "{:.3f}",
                "M_x,Rd (kN·m)": "{:.1f}",
                "M_y,Rd (kN·m)": "{:.1f}",
                "Interação": "{:.3f}",
            },
        )
        st.dataframe(estilo, hide_index=True, width="stretch")
        st.caption(
            "A comparação usa os mesmos dados de entrada. Uma norma que bloqueia o cálculo "
            "mostra o motivo em “Observação”. Q é o fator da NBR 2008; nas outras duas a coluna "
            "mostra A_ef/A_g."
        )


def _regras(entrada: cb.EntradaColuna) -> None:
    """B₁, a diferença da FLT entre as versões e as espessuras da Anglo, à vista."""
    with st.container(border=True):
        st.subheader("Regras adotadas nesta verificação", help=AJUDA["res_regras"])
        st.markdown("**Efeito B₁ (momentos amplificados)**")
        st.markdown("\n".join(f"- {regra}" for regra in cb.REGRAS_B1))
        st.markdown("**Flambagem lateral com torção (FLT): diferença entre as versões**")
        st.markdown(
            "\n".join(
                f"- **{texto}**" if norma == entrada.norma else f"- {texto}"
                for norma, texto in cb.EXPLICACAO_FLT.items()
            )
        )
        st.caption("A versão em negrito é a da norma escolhida.")
        st.markdown("**Espessuras mínimas da Anglo (item 8.8)**")
        st.markdown(
            "\n".join(
                f"- {rotulo[:1].upper()}{rotulo[1:]}: {ESPESSURA_MIN_ANGLO[categoria]:g} mm".replace(
                    ".", ","
                )
                for categoria, rotulo in cb.ROTULOS_ESPESSURA_ANGLO.items()
            )
        )
    if entrada.norma == "NBR8800_2008":
        with st.expander(
            "Valores da NBR 8800:2008 marcados “CONFERIR”", icon=":material/fact_check:"
        ):
            st.markdown("\n".join(f"- {item}" for item in cb.CONFERIR_NBR8800_2008))
            st.caption(
                "Foram trazidos de memória no módulo de referência, porque a norma vigente não "
                "estava disponível. Confirme na NBR 8800:2008 antes de liberar o documento."
            )


def _registro(
    entrada: cb.EntradaColuna,
    resultado: cb.ResultadoColuna,
    contexto: Mapping[str, Any],
    material_id: str | None,
    equacoes: list[str],
) -> None:
    comp = resultado.compressao
    registro = cb.registro_coluna(
        entrada,
        resultado,
        contexto=contexto,
        materiais_ids=[material_id] if material_id else [],
        equacoes_de_carga=equacoes,
    )
    with st.container(border=True):
        st.subheader("Registrar no projeto", help=AJUDA["reg_registrar"])
        st.subheader("Comparar cenários", divider=False, help=AJUDA["reg_comparar"])
        comparador_cenarios(
            escopo="flambagem_colunas",
            resumo_entradas={
                "Seção": entrada.secao.nome[:40],
                "Norma": cb.NORMAS_ROTULOS[entrada.norma].split(" (")[0],
                "Lx (mm)": round(entrada.Lx_mm, 0),
                "Ly (mm)": round(entrada.Ly_mm, 0),
            },
            metricas={
                "Status": resultado.status_geral,
                "Aprov. máx.": formatar_percentual(resultado.aproveitamento_max),
                "N_c,Rd (kN)": "—" if comp is None else f"{comp['Nc_Rd']:.2f}",
                "Governa": resultado.governante[:40],
            },
        )
        botao_registrar_calculo(
            registro,
            key="registrar_flambagem_colunas",
            rotulo="Registrar verificação da coluna no projeto ativo",
        )


def _contexto_do_registro(
    secao: DadosSecao,
    comprimentos: DadosComprimentos,
    cargas: DadosCargas,
    flexao: DadosFlexao,
    mao_francesa: DadosMaoFrancesa,
) -> dict[str, Any]:
    contexto: dict[str, Any] = {
        "tipo_secao_escolhido": secao.tipo_escolhido,
        "perfil_soldado": secao.soldado,
        "comprimento_total_mm": comprimentos.L_total_mm,
        "condicao_apoio_x": comprimentos.apoio_x,
        "condicao_apoio_y": comprimentos.apoio_y,
        "k_recomendado_de_norma": comprimentos.k_recomendado,
        "permanente_kN": cargas.permanente_kN,
        "variavel_kN": cargas.variavel_kN,
        "gamma_g": cargas.gamma_g,
        "gamma_q": cargas.gamma_q,
        "diagrama_momentos_x": flexao.diagrama_x,
        "diagrama_momentos_y": flexao.diagrama_y,
    }
    mf = mao_francesa.esforcos
    if mf is None:
        contexto["mao_francesa"] = "não incluída"
    else:
        contexto.update(
            {
                "mao_francesa_forca_kN": mao_francesa.forca_kN,
                "mao_francesa_gamma_f": mao_francesa.gamma,
                "mao_francesa_forca_calculo_kN": mf.forca_N / 1e3,
                "mao_francesa_angulo_graus": mf.angulo_graus,
                "mao_francesa_altura_no_mm": mf.altura_no_mm,
                "mao_francesa_vinculo": mf.vinculo,
                "mao_francesa_eixo": mao_francesa.eixo,
                "mao_francesa_excentricidade_mm": mf.excentricidade_mm,
                "mao_francesa_H_kN": mf.componente_horizontal_N / 1e3,
                "mao_francesa_V_kN": mf.componente_vertical_N / 1e3,
                "mao_francesa_momento_kNm": mf.momento_Nmm / 1e6,
                "mao_francesa_expressao": mf.expressao,
                "mao_francesa_V_somado_a_NSd": mao_francesa.somar_v,
            }
        )
    return contexto


def _equacoes_de_carga(cargas: DadosCargas, mao_francesa: DadosMaoFrancesa) -> list[str]:
    equacoes = [cargas.equacao] if cargas.gamma_g is not None else []
    mf = mao_francesa.esforcos
    if mf is not None:
        equacoes.append(
            f"Mão-francesa: H = F_Sd·sen θ = {mf.forca_N / 1e3:.2f}·sen {mf.angulo_graus:.0f}° = "
            f"{mf.componente_horizontal_N / 1e3:.2f} kN;  "
            f"V = F_Sd·cos θ = {mf.componente_vertical_N / 1e3:.2f} kN;  {mf.expressao} = "
            f"{mf.momento_Nmm / 1e6:.3f} kN·m no eixo {mao_francesa.eixo}"
        )
    return equacoes


# ---------------------------------------------------------------------------
# Página inteira
# ---------------------------------------------------------------------------


def mostrar_flambagem_colunas() -> None:
    """Desenha a página: entradas, resultados, comparação de normas e registro."""
    material = formulario_material()
    secao = formulario_secao()
    comprimentos = formulario_comprimentos()
    cargas, flexao = formulario_esforcos()
    mao_francesa = formulario_mao_francesa(secao.secao, comprimentos.L_total_mm)
    espessuras = formulario_anglo(secao.secao, secao.soldado)

    entrada = montar_entrada(
        material, secao, comprimentos, cargas, flexao, mao_francesa, espessuras
    )
    try:
        resultado = cb.verificar_coluna(entrada)
    except ValueError as erro:
        st.error(f"Não foi possível calcular: {erro}", icon=":material/error:")
        st.stop()

    st.header("Resultados da verificação")
    if resultado.bloqueios:
        corpo = "\n".join(f"- {motivo}" for motivo in resultado.bloqueios)
        st.error(
            f"**O cálculo foi bloqueado em parte** — a norma não cobre este caso e o programa "
            f"não estima:\n\n{corpo}",
            icon=":material/block:",
        )
    for aviso in resultado.avisos:
        st.warning(aviso, icon=":material/warning:")

    _resumo(entrada, resultado)
    _tabela(resultado)
    _paredes(entrada, resultado)
    _comparar_normas(entrada)
    _regras(entrada)
    fronteira_modelo(list(cb.FORA_DO_ESCOPO))
    _registro(
        entrada,
        resultado,
        _contexto_do_registro(secao, comprimentos, cargas, flexao, mao_francesa),
        material.material_id,
        _equacoes_de_carga(cargas, mao_francesa),
    )

    with st.container(border=True):
        st.subheader("Precisa de ajuda para preencher ou interpretar?")
        st.markdown(
            "O **Guia geral** mostra como escolher K, o que são χ, Q e N_ez, como ler a tabela de "
            "verificações e um exemplo completo de coluna."
        )
        st.page_link(
            "app_pages/guia_geral.py",
            label="Abrir o guia de flambagem",
            icon=":material/help:",
            query_params={"modulo": "Flambagem de colunas"},
            width="stretch",
        )
    st.caption(
        "Verificação de barra isolada pela NBR 8800:2008, pelo Projeto NBR 8800:2024 ou pelo "
        "AISC 360-16, com o critério da Anglo. Para a estrutura completa (pórtico, B₂, cargas "
        "nocionais, ligações e placa de base), use Estruturas de aço."
    )
