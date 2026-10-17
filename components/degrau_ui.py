"""Interface da página Degrau de escada em grade.

Só desenha a interface: todo cálculo está em :mod:`core.degrau_escada`, o registro e as tabelas
em :mod:`core.degrau_registro` e o PDF em :mod:`core.degrau_relatorio`. A página recalcula a cada
interação: o quadro-resumo, a tabela das 38 verificações, o memorial do modelo adotado, os 64
modelos do catálogo e o texto da requisição. Entrada que não dá para calcular vira erro claro —
nada é corrigido em silêncio.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from components.degrau_help import AJUDA
from components.project_tools import botao_registrar_calculo
from components.ui import fronteira_modelo
from components.verification_table import COR_STATUS, mostrar_tabela_verificacoes
from core import degrau_escada as de
from core import degrau_registro as reg
from core import escada_lances as el
from core import longarina_escada as le
from core import portico_figuras as pf
from core import portico_plano as pp
from core import section_catalog as sc
from core.contraventamento_barras import ACOS
from core.degrau_relatorio import gerar_pdf_degrau

OPCOES_SELECAO = {de.SELECAO_AUTOMATICA: "Automática", de.SELECAO_MANUAL: "Manual"}
MODELOS = [m.nome for m in de.catalogo()]
OPCOES_MALHA = [de.QUALQUER, *de.MALHAS]
OPCOES_LIGACAO = [de.QUALQUER, *de.LIGACOES]
COR_ADOTADO = "background-color: rgba(250, 204, 21, 0.38)"
COR_SIM = "background-color: rgba(34, 197, 94, 0.28)"
COR_NAO = "background-color: rgba(239, 68, 68, 0.20)"
FAMILIAS_DA_LONGARINA = ("U (canal laminado)", "W (mesa larga)", "I duplamente simétrico")


def _pt(valor: float, casas: int = 2) -> str:
    return de.numero_pt(valor, casas)


# ---------------------------------------------------------------------------
# Widgets com a persistência da sessão e o “?” sempre presentes
# ---------------------------------------------------------------------------
def _numero(
    rotulo: str,
    chave: str,
    valor: float,
    ajuda: str,
    *,
    minimo: float = 0.0,
    maximo: float | None = None,
    passo: float | None = None,
    formato: str | None = None,
    desligado: bool = False,
    alvo: Any = st,
) -> float:
    return float(
        alvo.number_input(
            rotulo,
            min_value=float(minimo),
            max_value=maximo,
            value=float(valor),
            step=passo,
            format=formato,
            key=chave,
            persist_state="session",
            help=ajuda,
            disabled=desligado,
        )
    )


def _opcional(
    rotulo: str,
    chave: str,
    ajuda: str,
    *,
    minimo: float,
    passo: float,
    inteiro: bool = False,
    alvo: Any = st,
) -> float | int | None:
    """Campo que pode ficar vazio (vazio = o programa escolhe)."""
    valor = alvo.number_input(
        rotulo,
        min_value=int(minimo) if inteiro else float(minimo),
        value=None,
        step=int(passo) if inteiro else float(passo),
        placeholder="automático",
        key=chave,
        persist_state="session",
        help=ajuda,
    )
    if valor is None:
        return None
    return int(valor) if inteiro else float(valor)


def _selecao(
    rotulo: str,
    chave: str,
    opcoes: list[str],
    ajuda: str,
    *,
    formatar: Any = None,
    desligado: bool = False,
    alvo: Any = st,
    padrao: str | None = None,
) -> str:
    if st.session_state.get(chave) not in opcoes:
        st.session_state.pop(chave, None)
    return str(
        alvo.selectbox(
            rotulo,
            opcoes,
            index=opcoes.index(padrao) if padrao in opcoes else 0,
            format_func=formatar or str,
            key=chave,
            persist_state="session",
            help=ajuda,
            disabled=desligado,
        )
    )


# ---------------------------------------------------------------------------
# Formulários
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Identificacao:
    obra: str
    tag: str
    responsavel: str
    data: date


def formulario_identificacao() -> Identificacao:
    with st.container(border=True):
        st.subheader("1. Identificação", help=AJUDA["sec_1"])
        colunas = st.columns(4)
        obra = colunas[0].text_input(
            "Obra", key="dg_obra", persist_state="session", help=AJUDA["obra"]
        )
        tag = colunas[1].text_input("TAG", key="dg_tag", persist_state="session", help=AJUDA["tag"])
        responsavel = colunas[2].text_input(
            "Responsável", key="dg_responsavel", persist_state="session", help=AJUDA["responsavel"]
        )
        data = colunas[3].date_input(
            "Data",
            value=date.today(),
            format="DD/MM/YYYY",
            key="dg_data",
            persist_state="session",
            help=AJUDA["data"],
        )
    return Identificacao(obra.strip(), tag.strip(), responsavel.strip(), data)


@dataclass(frozen=True)
class DadosEnquadramento:
    enquadramento: str
    espelho_fechado: bool
    uso: str


def formulario_enquadramento() -> DadosEnquadramento:
    with st.container(border=True):
        st.subheader("2. Enquadramento", help=AJUDA["sec_2"])
        enquadramento = st.radio(
            "Enquadramento legal",
            list(de.ENQUADRAMENTOS),
            format_func=lambda chave: de.ENQUADRAMENTOS[chave],
            key="dg_enquadramento",
            persist_state="session",
            horizontal=True,
            help=AJUDA["enquadramento"],
        )
        st.caption(
            "Pela NR-22 (22.10.6), a escada de acesso a máquina ou equipamento segue o Anexo III "
            "da NR-12. Os demais acessos na mineração seguem a NR-22 (22.10.1.1)."
        )
        colunas = st.columns(2)
        espelho_fechado = colunas[0].toggle(
            "Degrau com espelho fechado",
            key="dg_espelho_fechado",
            persist_state="session",
            help=AJUDA["espelho_fechado"],
        )
        colunas[0].caption(
            "Grade vazada é escada **sem** espelho (NR-12 Anexo III item 11). Com espelho fechado "
            "vale o item 12."
        )
        uso = _selecao(
            "Uso (Anglo 10.2)",
            "dg_uso",
            list(de.USOS),
            AJUDA["uso"],
            formatar=lambda chave: de.USOS[chave],
            alvo=colunas[1],
        )
    return DadosEnquadramento(str(enquadramento), bool(espelho_fechado), uso)


@dataclass(frozen=True)
class DadosGeometria:
    H_mm: float
    h_alvo_mm: float
    n_imposto: int | None
    b_imposto_mm: float | None
    C_imposto_mm: float | None
    C_padronizado: bool
    L_mm: float
    reducao_largura_mm: float
    altura_max_lance_mm: float | None
    patamar_mm: float


def formulario_geometria() -> DadosGeometria:
    with st.container(border=True):
        st.subheader("3. Geometria", help=AJUDA["sec_3"])
        linha1 = st.columns(4)
        H = _numero(
            "Desnível total H (mm)",
            "dg_H",
            3600.0,
            AJUDA["H"],
            minimo=0.0,
            passo=50.0,
            alvo=linha1[0],
        )
        h_alvo = _numero(
            "Espelho alvo (mm)",
            "dg_h_alvo",
            175.0,
            AJUDA["h_alvo"],
            minimo=0.0,
            passo=1.0,
            alvo=linha1[1],
        )
        n_imposto = _opcional(
            "Nº de espelhos imposto",
            "dg_n",
            AJUDA["n_imposto"],
            minimo=0,
            passo=1,
            inteiro=True,
            alvo=linha1[2],
        )
        L = _numero(
            "Comprimento do degrau L (mm)",
            "dg_L",
            800.0,
            AJUDA["L"],
            minimo=0.0,
            passo=50.0,
            alvo=linha1[3],
        )
        linha2 = st.columns(4)
        b_imposto = _opcional(
            "Piso b imposto (mm)", "dg_b", AJUDA["b_imposto"], minimo=0.0, passo=5.0, alvo=linha2[0]
        )
        C_imposto = _opcional(
            "Profundidade C imposta (mm)",
            "dg_C",
            AJUDA["C_imposto"],
            minimo=0.0,
            passo=5.0,
            alvo=linha2[1],
        )
        reducao = _numero(
            "Redução da largura útil (mm)",
            "dg_reducao",
            0.0,
            AJUDA["reducao_largura"],
            minimo=0.0,
            passo=10.0,
            alvo=linha2[2],
        )
        patamar = _numero(
            "Comprimento do patamar (mm)",
            "dg_patamar",
            900.0,
            AJUDA["patamar"],
            minimo=0.0,
            passo=50.0,
            alvo=linha2[3],
        )
        linha3 = st.columns(2)
        altura_max = _opcional(
            "Altura máxima por lance imposta (mm)",
            "dg_altura_lance",
            AJUDA["altura_max_lance"],
            minimo=0.0,
            passo=100.0,
            alvo=linha3[0],
        )
        padronizado = linha3[1].toggle(
            "Usar C padronizado (175, 200, … 300)",
            value=True,
            key="dg_C_padronizado",
            persist_state="session",
            help=AJUDA["C_padronizado"],
        )
    return DadosGeometria(
        H, h_alvo, n_imposto if n_imposto is None else int(n_imposto), b_imposto, C_imposto,
        bool(padronizado), L, reducao, altura_max, patamar,
    )  # fmt: skip


@dataclass(frozen=True)
class DadosDegrau:
    selecao: str
    malha: str
    ligacao: str
    modelo_manual: str
    superficie: str
    chapa_xadrez: bool
    acabamento: str
    material: str
    lado_barra_mm: float
    parafuso: str
    n_parafusos: int


def formulario_degrau() -> DadosDegrau:
    with st.container(border=True):
        st.subheader("4. Degrau", help=AJUDA["sec_4"])
        selecao = st.radio(
            "Seleção do modelo",
            list(OPCOES_SELECAO),
            format_func=lambda chave: OPCOES_SELECAO[chave],
            key="dg_selecao",
            persist_state="session",
            horizontal=True,
            help=AJUDA["selecao"],
        )
        manual = selecao == de.SELECAO_MANUAL
        linha1 = st.columns(3)
        malha = _selecao(
            "Malha preferencial",
            "dg_malha",
            OPCOES_MALHA,
            AJUDA["malha"],
            formatar=lambda chave: chave if chave == de.QUALQUER else de.MALHAS[chave],
            desligado=manual,
            alvo=linha1[0],
            padrao="A",
        )
        ligacao = _selecao(
            "Barras de ligação",
            "dg_ligacao",
            OPCOES_LIGACAO,
            AJUDA["ligacao"],
            formatar=lambda chave: chave if chave == de.QUALQUER else de.LIGACOES[chave],
            desligado=manual,
            alvo=linha1[1],
            padrao="4",
        )
        modelo = _selecao(
            "Modelo (seleção manual)",
            "dg_modelo",
            MODELOS,
            AJUDA["modelo_manual"],
            desligado=not manual,
            alvo=linha1[2],
            padrao=de.MODELO_MANUAL_PADRAO,
        )
        linha2 = st.columns(4)
        superficie = _selecao(
            "Superfície",
            "dg_superficie",
            list(de.SUPERFICIES),
            AJUDA["superficie"],
            formatar=lambda chave: de.SUPERFICIES[chave],
            alvo=linha2[0],
        )
        xadrez = linha2[1].toggle(
            "Chapa xadrez no bocel",
            value=True,
            key="dg_xadrez",
            persist_state="session",
            help=AJUDA["xadrez"],
        )
        acabamento = _selecao(
            "Acabamento",
            "dg_acabamento",
            list(de.ACABAMENTOS),
            AJUDA["acabamento"],
            formatar=lambda chave: de.ACABAMENTOS[chave],
            alvo=linha2[2],
        )
        material = _selecao(
            "Material",
            "dg_material",
            list(de.MATERIAIS),
            AJUDA["material"],
            alvo=linha2[3],
        )
        linha3 = st.columns(3)
        lado = _numero(
            "Lado da barra de ligação (mm) — ADOTADO só para estimar o peso",
            "dg_lado_barra",
            6.0,
            AJUDA["lado_barra"],
            minimo=0.0,
            passo=0.5,
            alvo=linha3[0],
        )
        parafuso = _selecao(
            "Parafuso A307 galvanizado",
            "dg_parafuso",
            list(de.PARAFUSOS),
            AJUDA["parafuso"],
            alvo=linha3[1],
            padrao=de.PARAFUSO_PADRAO,
        )
        n_parafusos = linha3[2].number_input(
            "Nº de parafusos por lado",
            min_value=1,
            value=2,
            step=1,
            key="dg_n_parafusos",
            persist_state="session",
            help=AJUDA["n_parafusos"],
        )
    return DadosDegrau(
        str(selecao), malha, ligacao, modelo, superficie, bool(xadrez), acabamento, material,
        lado, parafuso, int(n_parafusos),
    )  # fmt: skip


@dataclass(frozen=True)
class DadosCargas:
    q: float
    P: float
    P_iso: float
    b_c: float
    n_ef: int | None
    gamma_g: float
    gamma_q: float
    gamma_a1: float
    gamma_a2: float
    Cb: float
    flecha_div: float
    flecha_iso_div: float
    flecha_iso_max: float
    gc_superior: float
    gc_intermediario: float
    gc_rodape: float
    gc_espacamento: float


def formulario_cargas() -> DadosCargas:
    with st.container(border=True):
        st.subheader("5. Cargas, coeficientes e limites", help=AJUDA["sec_5"])
        with st.expander("Valores das normas — abra para alterar", icon=":material/tune:"):
            linha1 = st.columns(4)
            q = _numero(
                "q — sobrecarga (kN/m²)",
                "dg_q",
                3.00,
                AJUDA["q"],
                passo=0.25,
                formato="%.2f",
                alvo=linha1[0],
            )
            P = _numero(
                "P — concentrada no ELU (kN)",
                "dg_P",
                2.50,
                AJUDA["P"],
                passo=0.25,
                formato="%.2f",
                alvo=linha1[1],
            )
            P_iso = _numero(
                "P_ISO — concentrada para flecha (kN)",
                "dg_P_iso",
                1.50,
                AJUDA["P_iso"],
                passo=0.25,
                formato="%.2f",
                alvo=linha1[2],
            )
            b_c = _numero(
                "b_c — largura de aplicação (mm)",
                "dg_b_c",
                100.0,
                AJUDA["b_c"],
                passo=10.0,
                alvo=linha1[3],
            )
            linha2 = st.columns(4)
            n_ef = _opcional(
                "n_ef imposto",
                "dg_n_ef",
                AJUDA["n_ef"],
                minimo=1,
                passo=1,
                inteiro=True,
                alvo=linha2[0],
            )
            gamma_g = _numero(
                "γg",
                "dg_gamma_g",
                1.25,
                AJUDA["gamma_g"],
                passo=0.05,
                formato="%.2f",
                alvo=linha2[1],
            )
            gamma_q = _numero(
                "γq",
                "dg_gamma_q",
                1.50,
                AJUDA["gamma_q"],
                passo=0.05,
                formato="%.2f",
                alvo=linha2[2],
            )
            cb = _numero(
                "Cb", "dg_cb", 1.00, AJUDA["cb"], passo=0.05, formato="%.2f", alvo=linha2[3]
            )
            linha3 = st.columns(4)
            gamma_a1 = _numero(
                "γa1",
                "dg_gamma_a1",
                1.10,
                AJUDA["gamma_a1"],
                passo=0.05,
                formato="%.2f",
                alvo=linha3[0],
            )
            gamma_a2 = _numero(
                "γa2",
                "dg_gamma_a2",
                1.35,
                AJUDA["gamma_a2"],
                passo=0.05,
                formato="%.2f",
                alvo=linha3[1],
            )
            flecha = _numero(
                "Flecha distribuída: L/",
                "dg_flecha",
                300.0,
                AJUDA["flecha_div"],
                passo=10.0,
                alvo=linha3[2],
            )
            flecha_iso = _numero(
                "Flecha ISO: L/",
                "dg_flecha_iso",
                300.0,
                AJUDA["flecha_iso_div"],
                passo=10.0,
                alvo=linha3[3],
            )
            flecha_iso_max = _numero(
                "Flecha ISO máxima (mm)",
                "dg_flecha_iso_max",
                6.0,
                AJUDA["flecha_iso_max"],
                passo=0.5,
                formato="%.1f",
            )
        st.subheader("6. Guarda-corpo (só conferência)", help=AJUDA["sec_6"])
        with st.expander("Medidas do guarda-corpo", icon=":material/fence:"):
            linha4 = st.columns(4)
            gc_sup = _numero(
                "Travessão superior (mm)",
                "dg_gc_sup",
                1200.0,
                AJUDA["gc_sup"],
                passo=50.0,
                alvo=linha4[0],
            )
            gc_int = _numero(
                "Travessão intermediário (mm)",
                "dg_gc_int",
                700.0,
                AJUDA["gc_int"],
                passo=10.0,
                alvo=linha4[1],
            )
            gc_rod = _numero(
                "Rodapé (mm)", "dg_gc_rod", 200.0, AJUDA["gc_rod"], passo=10.0, alvo=linha4[2]
            )
            gc_esp = _numero(
                "Espaçamento entre barras (mm)",
                "dg_gc_esp",
                150.0,
                AJUDA["gc_esp"],
                passo=10.0,
                alvo=linha4[3],
            )
    return DadosCargas(
        q, P, P_iso, b_c, n_ef if n_ef is None else int(n_ef), gamma_g, gamma_q, gamma_a1, gamma_a2,
        cb, flecha, flecha_iso, flecha_iso_max, gc_sup, gc_int, gc_rod, gc_esp,
    )  # fmt: skip


@dataclass(frozen=True)
class DadosPatamares:
    patamares: tuple[el.PatamarInformado, ...]
    ajustar: bool
    em_u: bool


COLUNAS_PATAMARES = {
    "altura": "Altura do patamar (mm)",
    "comprimento": "Comprimento (mm)",
    "largura": "Largura (mm)",
    "volta": "Lance seguinte volta (U)",
}


def formulario_patamares() -> DadosPatamares:
    """Os patamares que o projeto pedir (vazio = divisão automática em lances iguais)."""
    with st.container(border=True):
        st.subheader("Lances e patamares", help=AJUDA["sec_patamares"])
        vazia = pd.DataFrame(
            {
                COLUNAS_PATAMARES["altura"]: pd.Series(dtype="float"),
                COLUNAS_PATAMARES["comprimento"]: pd.Series(dtype="float"),
                COLUNAS_PATAMARES["largura"]: pd.Series(dtype="float"),
                COLUNAS_PATAMARES["volta"]: pd.Series(dtype="bool"),
            }
        )
        st.caption(AJUDA["patamares_tabela"])
        editada = st.data_editor(
            vazia,
            num_rows="dynamic",
            hide_index=True,
            key="dg_patamares",
            width="stretch",
            column_config={
                COLUNAS_PATAMARES["altura"]: st.column_config.NumberColumn(
                    min_value=0.0, step=10.0, help=AJUDA["pat_altura"]
                ),
                COLUNAS_PATAMARES["comprimento"]: st.column_config.NumberColumn(
                    min_value=0.0, step=50.0, help=AJUDA["pat_comprimento"]
                ),
                COLUNAS_PATAMARES["largura"]: st.column_config.NumberColumn(
                    min_value=0.0, step=50.0, help=AJUDA["pat_largura"]
                ),
                COLUNAS_PATAMARES["volta"]: st.column_config.CheckboxColumn(
                    default=False, help=AJUDA["pat_volta"]
                ),
            },
        )
        linha = st.columns(2)
        ajustar = linha[0].toggle(
            "Ajustar a altura dos patamares ao espelho",
            value=True,
            key="dg_pat_ajustar",
            persist_state="session",
            help=AJUDA["pat_ajustar"],
        )
        em_u = linha[1].toggle(
            "Lances em U (sem patamares na tabela)",
            value=False,
            key="dg_pat_em_u",
            persist_state="session",
            help=AJUDA["pat_em_u"],
        )
    patamares = []
    for _, linha_tabela in editada.iterrows():
        altura = linha_tabela.get(COLUNAS_PATAMARES["altura"])
        if altura is None or pd.isna(altura):
            continue
        comprimento = linha_tabela.get(COLUNAS_PATAMARES["comprimento"])
        largura = linha_tabela.get(COLUNAS_PATAMARES["largura"])
        volta = linha_tabela.get(COLUNAS_PATAMARES["volta"])
        patamares.append(
            el.PatamarInformado(
                altura_mm=float(altura),
                comprimento_mm=0.0
                if comprimento is None or pd.isna(comprimento)
                else float(comprimento),
                largura_mm=None if largura is None or pd.isna(largura) else float(largura),
                volta=bool(volta) if volta is not None and not pd.isna(volta) else False,
            )
        )
    return DadosPatamares(tuple(patamares), bool(ajustar), bool(em_u))


def formulario_longarina() -> le.EntradaLongarina | None:
    """As longarinas (opcional): perfil, aço, apoios, trechos horizontais e cargas."""
    with st.container(border=True):
        st.subheader("7. Longarina", help=AJUDA["sec_7"])
        ligada = st.toggle(
            "Calcular a longarina",
            key="dg_longarina",
            persist_state="session",
            help=AJUDA["longarina"],
        )
        if not ligada:
            return None
        padrao = le.EntradaLongarina()
        perfis = [n for n, p in sc.listar_perfis().items() if p.familia in FAMILIAS_DA_LONGARINA]
        linha = st.columns(4)
        perfil = _selecao(
            "Perfil da longarina",
            "dg_lg_perfil",
            perfis,
            AJUDA["lg_perfil"],
            alvo=linha[0],
            padrao=padrao.perfil,
        )
        aco = _selecao(
            "Aço", "dg_lg_aco", list(ACOS), AJUDA["lg_aco"], alvo=linha[1], padrao="ASTM A36"
        )
        gc = _numero(
            "Guarda-corpo (kN/m)",
            "dg_lg_gc",
            padrao.guarda_corpo_kN_m,
            AJUDA["lg_gc"],
            passo=0.05,
            formato="%.2f",
            alvo=linha[2],
        )
        piso = _numero(
            "Piso do patamar (kN/m²)",
            "dg_lg_piso",
            padrao.piso_patamar_kN_m2,
            AJUDA["lg_piso"],
            passo=0.05,
            formato="%.2f",
            alvo=linha[3],
        )
        linha = st.columns(4)
        apoio_pe = _selecao(
            "Apoio no pé",
            "dg_lg_apoio_pe",
            list(le.APOIOS),
            AJUDA["lg_apoio_pe"],
            formatar=le.APOIOS.get,
            alvo=linha[0],
            padrao=padrao.apoio_pe,
        )
        apoio_topo = _selecao(
            "Apoio no topo",
            "dg_lg_apoio_topo",
            list(le.APOIOS),
            AJUDA["lg_apoio_topo"],
            formatar=le.APOIOS.get,
            alvo=linha[1],
            padrao=padrao.apoio_topo,
        )
        trecho_pe = _numero(
            "Trecho horizontal no pé (m)",
            "dg_lg_trecho_pe",
            0.0,
            AJUDA["lg_trecho_pe"],
            passo=0.05,
            formato="%.2f",
            alvo=linha[2],
        )
        trecho_topo = _numero(
            "Trecho horizontal no topo (m)",
            "dg_lg_trecho_topo",
            0.0,
            AJUDA["lg_trecho_topo"],
            passo=0.05,
            formato="%.2f",
            alvo=linha[3],
        )
        linha = st.columns(4)
        vao = _opcional(
            "Distância horizontal do trecho inclinado (m)",
            "dg_lg_vao",
            AJUDA["lg_vao"],
            minimo=0.1,
            passo=0.1,
            alvo=linha[0],
        )
        lb = _opcional(
            "Comprimento destravado (m)",
            "dg_lg_lb",
            AJUDA["lg_lb"],
            minimo=0.05,
            passo=0.05,
            alvo=linha[1],
        )
    return le.EntradaLongarina(
        perfil=perfil,
        aco=aco,
        vao_horizontal_m=vao,
        guarda_corpo_kN_m=gc,
        trecho_pe_m=trecho_pe,
        trecho_topo_m=trecho_topo,
        apoio_pe=apoio_pe,
        apoio_topo=apoio_topo,
        piso_patamar_kN_m2=piso,
        lb_m=lb,
    )


@st.cache_data(max_entries=24, show_spinner=False)
def _figuras_da_longarina(
    modelo_json: str, servico_json: str, titulo: str, caso: str
) -> list[tuple[str, str, bytes]]:
    """As figuras de uma longarina (guardadas: redesenhar a cada clique deixaria a página lenta)."""
    principal = pp.resolver(pp.de_dicionario(json.loads(modelo_json)))
    servico = pp.resolver(pp.de_dicionario(json.loads(servico_json)))
    return [
        (f.titulo, f.legenda, f.png)
        for f in pf.figuras_do_portico(
            principal, prefixo=titulo, caso=caso, deformada=servico, caso_deformada=le.ELS
        )
    ]


@st.cache_data(max_entries=24, show_spinner=False)
def _figura_da_escada(dados_json: str) -> tuple[str, bytes]:
    figura = el.figura_esquematico(*el.geometria_do_dicionario(json.loads(dados_json)))
    return figura.legenda, figura.png


def _aba_escada(escada: el.EscadaComPatamares) -> None:
    st.subheader("Esquemático da escada", help=AJUDA["res_escada"])
    legenda, png = _figura_da_escada(json.dumps(el.para_dicionario(escada), sort_keys=True))
    st.image(png, caption=legenda, width="stretch")
    st.dataframe(
        pd.DataFrame(el.linhas_dos_lances(escada), columns=el.CABECALHO_LANCES),
        hide_index=True,
        width="stretch",
    )
    if escada.patamares:
        st.dataframe(
            pd.DataFrame(el.linhas_dos_patamares(escada), columns=el.CABECALHO_PATAMARES),
            hide_index=True,
            width="stretch",
        )
    for aviso in escada.avisos:
        st.warning(aviso, icon=":material/warning:")


def _aba_longarina(resultado: le.ResultadoLongarina) -> None:
    st.subheader(
        f"Longarina {resultado.entrada.perfil} — {resultado.status}", help=AJUDA["res_longarina"]
    )
    for aviso in resultado.avisos:
        st.info(aviso, icon=":material/info:")
    titulos = [lg.titulo for lg in resultado.longarinas]
    escolhida = resultado.governante
    if len(titulos) > 1:
        nome = _selecao(
            "Longarina",
            "dg_lg_escolhida",
            titulos,
            AJUDA["res_lg_escolha"],
            padrao=resultado.governante.titulo,
        )
        escolhida = resultado.longarinas[titulos.index(nome)]
    lg = escolhida
    inclinado = next(t for t in lg.trechos if t.barra == le.TRECHO_INCLINADO)
    rb = lg.elu.barra(le.TRECHO_INCLINADO)
    linha = st.columns(4)
    linha[0].metric(
        "Horizontal / inclinado (m)",
        f"{_pt(lg.vao_horizontal_m, 2)} / {_pt(lg.vao_inclinado_m, 2)}",
        help=AJUDA["res_lg_vao"],
    )
    linha[0].caption(
        ("informada" if lg.vao_informado else "linha dos bocéis, n·b")
        + f" · α = {_pt(lg.alfa_graus, 1)}°"
    )
    maior_dy = max(t.deslocamento_vertical_mm for t in lg.trechos)
    linha[1].metric("Deslocamento vertical (mm)", _pt(maior_dy, 2), help=AJUDA["res_lg_desloc"])
    linha[1].caption(
        f"flecha {_pt(abs(inclinado.flecha_mm), 2)} mm ≤ L/350 = "
        f"{_pt(inclinado.limite_flecha_mm, 1)} mm (trecho inclinado)"
    )
    m_rd = inclinado.resultado.mx_rd
    linha[2].metric(
        "M_Sd / M_Rd (kN·m)",
        f"{_pt(abs(rb.m_max.m), 2)} / {_pt(m_rd, 2) if m_rd else '—'}",
        help=AJUDA["res_lg_momento"],
    )
    linha[2].caption(f"aproveitamento {100 * lg.aproveitamento_maximo:.0f} % · {lg.status}")
    ry = max(abs(r.ry) for r in lg.reacoes(le.ELU))
    linha[3].metric("Maior reação vertical ELU (kN)", _pt(ry, 2), help=AJUDA["res_lg_reacao"])
    rx = max(abs(r.rx) for r in lg.reacoes(le.ELU))
    linha[3].caption(
        f"empuxo horizontal ELU {_pt(rx, 2)} kN" if rx > 0.005 else "sem empuxo horizontal"
    )

    st.subheader("Diagramas", help=AJUDA["res_lg_figuras"])
    figuras = _figuras_da_longarina(
        json.dumps(pp.para_dicionario(lg.porticos[le.ELU]), sort_keys=True),
        json.dumps(pp.para_dicionario(lg.porticos[le.ELS]), sort_keys=True),
        lg.titulo,
        f"ELU ({_pt(lg.gamma_g)}·G + {_pt(lg.gamma_q)}·Q)",
    )
    tensao = ["Tensão"] if len(figuras) == 7 else []
    nomes = ["Modelo", "Reações", "Normal", "Cortante", "Momento", *tensao, "Deformada"]
    for aba, (_titulo, legenda, png) in zip(st.tabs(nomes), figuras, strict=True):
        with aba:
            st.image(png, caption=legenda, width="stretch")

    st.subheader("Cargas por longarina", help=AJUDA["res_lg_cargas"])
    st.dataframe(
        pd.DataFrame(le.linhas_das_cargas(lg), columns=["Carga", "Valor", "Unidade", "Origem"]),
        hide_index=True,
        width="stretch",
    )
    st.subheader("Trechos", help=AJUDA["res_lg_trechos"])
    st.dataframe(
        pd.DataFrame(le.linhas_dos_trechos(lg), columns=le.CABECALHO_TRECHOS),
        hide_index=True,
        width="stretch",
    )
    st.subheader("Reações", help=AJUDA["res_lg_reacoes"])
    st.dataframe(
        pd.DataFrame(le.linhas_das_reacoes(lg), columns=le.CABECALHO_REACOES),
        hide_index=True,
        width="stretch",
    )
    mostrar_tabela_verificacoes(list(lg.verificacoes))


def montar_entrada(
    enq: DadosEnquadramento, geo: DadosGeometria, deg: DadosDegrau, car: DadosCargas
) -> de.EntradaDegrau:
    return de.EntradaDegrau(
        enquadramento=enq.enquadramento,
        espelho_fechado=enq.espelho_fechado,
        uso=enq.uso,
        H_mm=geo.H_mm,
        h_alvo_mm=geo.h_alvo_mm,
        n_imposto=geo.n_imposto,
        b_imposto_mm=geo.b_imposto_mm,
        C_imposto_mm=geo.C_imposto_mm,
        C_padronizado=geo.C_padronizado,
        L_mm=geo.L_mm,
        reducao_largura_mm=geo.reducao_largura_mm,
        altura_max_lance_imposta_mm=geo.altura_max_lance_mm,
        patamar_mm=geo.patamar_mm,
        selecao=deg.selecao,
        malha_preferida=deg.malha,
        ligacao_preferida=deg.ligacao,
        modelo_manual=deg.modelo_manual,
        superficie=deg.superficie,
        chapa_xadrez=deg.chapa_xadrez,
        acabamento=deg.acabamento,
        material=deg.material,
        lado_barra_ligacao_mm=deg.lado_barra_mm,
        parafuso=deg.parafuso,
        n_parafusos_por_lado=deg.n_parafusos,
        q_kN_m2=car.q,
        P_kN=car.P,
        P_iso_kN=car.P_iso,
        b_c_mm=car.b_c,
        n_ef_imposto=car.n_ef,
        gamma_g=car.gamma_g,
        gamma_q=car.gamma_q,
        gamma_a1=car.gamma_a1,
        gamma_a2=car.gamma_a2,
        Cb=car.Cb,
        flecha_div=car.flecha_div,
        flecha_iso_div=car.flecha_iso_div,
        flecha_iso_max_mm=car.flecha_iso_max,
        gc_superior_mm=car.gc_superior,
        gc_intermediario_mm=car.gc_intermediario,
        gc_rodape_mm=car.gc_rodape,
        gc_espacamento_mm=car.gc_espacamento,
    )


# ---------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------
def _mapear(estilo: Any, funcao: Any, subset: list[str]) -> Any:
    """``Styler.map`` (pandas ≥ 2.1) ou o antigo ``applymap``."""
    aplicar = getattr(estilo, "map", None) or estilo.applymap
    return aplicar(funcao, subset=subset)


def _resumo(r: de.ResultadoEscada) -> None:
    e, g, ln, a = r.entrada, r.geometria, r.lances, r.adotado
    with st.container(border=True):
        st.subheader("Quadro-resumo", help=AJUDA["sec_res"])
        linha1 = st.columns(3)
        linha1[0].metric("Modelo adotado", a.modelo.nome, help=AJUDA["res_modelo"])
        linha1[0].caption(r.selecao.mensagem)
        linha1[1].metric(
            "Espelho h × piso b (mm)",
            f"{_pt(g.h_mm, 1)} × {_pt(g.b_mm, 0)}",
            help=AJUDA["res_espelho_piso"],
        )
        linha1[1].caption(f"2h + b = {_pt(g.blondel_mm, 1)} mm · α = {_pt(g.alfa_graus, 2)}°")
        linha1[2].metric(
            "Profundidade C × L (mm)",
            f"{_pt(g.C_mm, 0)} × {_pt(e.L_mm, 0)}",
            help=AJUDA["res_c_l"],
        )
        linha1[2].caption(f"F = {g.F_mm} mm · r = {_pt(g.r_mm, 0)} mm")
        linha2 = st.columns(3)
        linha2[0].metric(
            "Espelhos / degraus em grade",
            f"{g.n} / {ln.n_degraus_grade}",
            help=AJUDA["res_lances"],
        )
        linha2[0].caption(ln.texto)
        linha2[1].metric(
            "Aproveitamento máximo",
            f"{100 * r.aproveitamento_maximo:.0f} %",
            help=AJUDA["res_aproveitamento"],
        )
        linha2[2].metric(
            "Peso: degrau / total (kg)",
            f"{_pt(r.peso_unitario_kg, 2)} / {_pt(r.peso_total_kg, 1)}",
            help=AJUDA["res_peso"],
        )
        linha3 = st.columns(3)
        linha3[0].metric(
            "Situação da geometria",
            f"Nível {g.faixa.nivel} de 4",
            help=AJUDA["res_situacao"],
        )
        linha3[0].caption(g.faixa.mensagem)
        linha3[1].metric("Status geral", r.status, help=AJUDA["res_status"])
        linha3[1].caption(de.texto_da_contagem(r.contagem))
        linha3[2].metric(
            "Deslocamento do degrau (mm)",
            f"{_pt(a.delta_d_mm, 2)} / {_pt(a.delta_iso_mm, 2)}",
            help=AJUDA["res_desloc_degrau"],
        )
        linha3[2].caption("carga distribuída / carga concentrada da ISO")
    for aviso in r.avisos:
        st.warning(aviso, icon=":material/warning:")


def _aba_verificacoes(r: de.ResultadoEscada) -> None:
    st.subheader("As 38 verificações", help=AJUDA["res_verificacoes"])
    so_atencao = st.toggle(
        "Mostrar só o que merece atenção (NÃO OK, ALERTA e N/A)",
        key="dg_so_atencao",
        persist_state="session",
        help=AJUDA["so_atencao"],
    )
    tabela = pd.DataFrame(reg.tabela_de_verificacoes(r), columns=list(reg.COLUNAS_VERIFICACAO))
    if so_atencao:
        tabela = tabela[tabela["Status"].isin(["NÃO OK", "ALERTA", "N/A"])]
    exibicao = tabela.copy()
    exibicao["Aproveitamento (%)"] = [
        "—" if v is None or pd.isna(v) else f"{v:.0f}" for v in tabela["Aproveitamento (%)"]
    ]
    estilo = _mapear(exibicao.style, lambda v: COR_STATUS.get(v, ""), ["Status"])
    st.dataframe(
        estilo,
        hide_index=True,
        width="stretch",
        height=min(40 + 35 * len(exibicao), 620),
        column_config={
            "Verificação": st.column_config.TextColumn(
                width="large", help=AJUDA["col_verificacao"]
            ),
            "Norma/item": st.column_config.TextColumn(width="medium", help=AJUDA["col_norma"]),
            "Valor": st.column_config.TextColumn(width="small", help=AJUDA["col_valor"]),
            "Limite": st.column_config.TextColumn(width="small", help=AJUDA["col_limite"]),
            "Aproveitamento (%)": st.column_config.TextColumn(
                width="small", help=AJUDA["col_aproveitamento"]
            ),
            "Status": st.column_config.TextColumn(width="small", help=AJUDA["col_status"]),
            "Observação": st.column_config.TextColumn(width="large", help=AJUDA["col_observacao"]),
        },
    )
    if so_atencao and tabela.empty:
        st.success("Nenhuma verificação com NÃO OK, ALERTA ou N/A.", icon=":material/check_circle:")


def _aba_memorial(r: de.ResultadoEscada) -> None:
    st.subheader("Geometria da escada", help=AJUDA["res_geometria"])
    st.dataframe(
        pd.DataFrame(reg.linhas_da_geometria(r), columns=["Grandeza", "Valor", "Un.", "Cálculo"]),
        hide_index=True,
        width="stretch",
    )
    st.subheader(
        f"Memorial do modelo adotado — {r.adotado.modelo.nome}", help=AJUDA["res_memorial"]
    )
    st.dataframe(
        pd.DataFrame(
            reg.linhas_do_dimensionamento(r), columns=["Grandeza", "Valor", "Un.", "Cálculo"]
        ),
        hide_index=True,
        width="stretch",
    )


def _aba_catalogo(r: de.ResultadoEscada) -> None:
    st.subheader("Os 64 modelos do catálogo", help=AJUDA["res_catalogo"])
    tabela = pd.DataFrame(reg.linhas_do_catalogo(r))

    def destacar(linha: pd.Series) -> list[str]:
        return [COR_ADOTADO if linha["Adotado"] else ""] * len(linha)

    formatos = {
        "λ": "{:.1f}",
        "λp": "{:.1f}",
        "λr": "{:.1f}",
        "M_Rd (kN·m)": "{:.4f}",
        "Peso do degrau (kg)": "{:.3f}",
        "u flexão distribuída": "{:.3f}",
        "u flexão concentrada": "{:.3f}",
        "u cisalhamento": "{:.3f}",
        "u flecha distribuída": "{:.3f}",
        "u flecha ISO": "{:.3f}",
        "u máx": "{:.3f}",
        "Malha p (mm)": "{:.0f}",
        "Barras de ligação s (mm)": "{:.0f}",
    }
    estilo = tabela.style.apply(destacar, axis=1).format(formatos)
    estilo = _mapear(estilo, lambda v: COR_SIM if v == "SIM" else COR_NAO, ["Atende"])
    st.dataframe(estilo, hide_index=True, width="stretch", height=480)
    st.caption(
        f"Adotado: {r.adotado.modelo.nome} (linha amarela). “Atende” = u máx ≤ 1 e L dentro do "
        "máximo recomendado."
    )


def _aba_requisicao(r: de.ResultadoEscada, ident: Identificacao) -> None:
    st.subheader("Texto para a requisição", help=AJUDA["res_requisicao"])
    st.code(r.especificacao, language=None, wrap_lines=True)
    colunas = st.columns(2)
    colunas[0].metric("Peso unitário", f"{_pt(r.peso_unitario_kg, 2)} kg", help=AJUDA["res_peso"])
    colunas[1].metric(
        f"Peso total ({r.lances.n_degraus_grade} degraus)",
        f"{_pt(r.peso_total_kg, 1)} kg",
        help=AJUDA["res_peso"],
    )
    st.subheader("Exportar", help=AJUDA["res_exportar"])
    botoes = st.columns(3)
    botoes[0].download_button(
        "Verificações em CSV",
        data=reg.csv_das_verificacoes(r),
        file_name="degrau_escada_verificacoes.csv",
        mime="text/csv",
        icon=":material/download:",
        width="stretch",
        key="dg_baixar_verificacoes",
        help=AJUDA["btn_csv_verificacoes"],
    )
    botoes[1].download_button(
        "Os 64 modelos em CSV",
        data=reg.csv_do_catalogo(r),
        file_name="degrau_escada_catalogo.csv",
        mime="text/csv",
        icon=":material/download:",
        width="stretch",
        key="dg_baixar_catalogo",
        help=AJUDA["btn_csv_catalogo"],
    )
    _botao_pdf(botoes[2], r, ident)


def _pdf_bytes(r: de.ResultadoEscada, ident: Identificacao) -> bytes:
    return gerar_pdf_degrau(
        r,
        {
            "obra": ident.obra,
            "tag": ident.tag,
            "responsavel": ident.responsavel,
            "data": ident.data,
        },
    )


def _botao_pdf(alvo: Any, r: de.ResultadoEscada, ident: Identificacao) -> None:
    """Botão do PDF: o arquivo só é gerado no clique (``data`` aceita uma função)."""
    opcoes: dict[str, Any] = {
        "file_name": "degrau_escada_relatorio.pdf",
        "mime": "application/pdf",
        "icon": ":material/picture_as_pdf:",
        "width": "stretch",
        "key": "dg_baixar_pdf",
        "help": AJUDA["btn_pdf"],
    }
    try:
        alvo.download_button("Relatório em PDF", data=lambda: _pdf_bytes(r, ident), **opcoes)
    except Exception:  # noqa: BLE001 - Streamlit sem download adiado: gera já, como os CSV
        alvo.download_button("Relatório em PDF", data=_pdf_bytes(r, ident), **opcoes)


def _blocos_fixos(r: de.ResultadoEscada) -> None:
    st.subheader("Conflitos entre normas", help=AJUDA["res_conflitos"])
    st.warning(
        "\n".join(f"{i}. {item}" for i, item in enumerate(reg.CONFLITOS_ENTRE_NORMAS, start=1)),
        icon=":material/balance:",
    )
    st.subheader("Avisos e limites do cálculo", help=AJUDA["res_avisos"])
    fronteira_modelo(list(reg.AVISOS_FIXOS), titulo="Conferir antes de emitir")


def _registrar(
    r: de.ResultadoEscada,
    ident: Identificacao,
    escada: el.EscadaComPatamares,
    longarina: le.ResultadoLongarina | None,
) -> None:
    contexto: dict[str, Any] = {"data_do_calculo": ident.data.isoformat()}
    if ident.obra:
        contexto["obra"] = ident.obra
    if ident.tag:
        contexto["tag"] = ident.tag
    registro = reg.registro_degrau(
        r,
        contexto=contexto,
        responsavel=ident.responsavel,
        escada=escada,
        longarina=longarina,
    )
    with st.container(border=True):
        st.subheader("Registrar no projeto", help=AJUDA["reg_registrar"])
        botao_registrar_calculo(
            registro,
            key="registrar_degrau_escada",
            rotulo="Registrar o degrau no projeto ativo",
        )


def mostrar_degrau_de_escada() -> None:
    """Desenha a página: entradas, resultados e registro."""
    fronteira_modelo(list(reg.NAO_FAZ), titulo="O que esta página não faz")
    ident = formulario_identificacao()
    enq = formulario_enquadramento()
    geo = formulario_geometria()
    patamares = formulario_patamares()
    deg = formulario_degrau()
    car = formulario_cargas()
    longarina = formulario_longarina()
    entrada = montar_entrada(enq, geo, deg, car)
    erros = de.validar_entrada(entrada)
    if erros:
        for erro in erros:
            st.error(erro, icon=":material/error:")
        st.stop()
    try:
        resultado = de.calcular_escada(entrada)
    except de.EntradaInvalida as erro:
        st.error(f"Não foi possível calcular: {erro}", icon=":material/error:")
        st.stop()
    try:
        escada = el.montar_escada(
            resultado,
            patamares.patamares,
            ajustar_ao_espelho=patamares.ajustar,
            lances_em_u=patamares.em_u,
        )
    except de.EntradaInvalida as erro:
        st.error(f"Não foi possível montar os patamares: {erro}", icon=":material/error:")
        st.stop()
    resultado = el.aplicar_na_escada(resultado, escada)
    calculo_longarina: le.ResultadoLongarina | None = None
    erro_longarina = ""
    if longarina is not None:
        try:
            calculo_longarina = le.calcular_longarina(resultado, longarina, escada)
        except le.LongarinaInvalida as erro:
            erro_longarina = str(erro)
    st.header("Resultados")
    _resumo(resultado)
    nomes_das_abas = [
        "Verificações",
        "Escada",
        "Memorial do modelo adotado",
        "Os 64 modelos",
        "Requisição e exportação",
    ]
    if longarina is not None:
        nomes_das_abas.insert(1, "Longarina")
    abas = st.tabs(nomes_das_abas)
    if longarina is not None:
        with abas[1]:
            if calculo_longarina is not None:
                _aba_longarina(calculo_longarina)
            else:
                st.error(
                    f"Não foi possível calcular a longarina: {erro_longarina}",
                    icon=":material/error:",
                )
        abas = [abas[0], *abas[2:]]
    aba_verificacoes, aba_escada, aba_memorial, aba_catalogo, aba_requisicao = abas
    with aba_escada:
        _aba_escada(escada)
    with aba_verificacoes:
        _aba_verificacoes(resultado)
    with aba_memorial:
        _aba_memorial(resultado)
    with aba_catalogo:
        _aba_catalogo(resultado)
    with aba_requisicao:
        _aba_requisicao(resultado, ident)
    _blocos_fixos(resultado)
    _registrar(resultado, ident, escada, calculo_longarina)
