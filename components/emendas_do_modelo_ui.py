"""A Emenda de pilar ligada ao modelo do SolidWorks: trazer uma emenda, sugerir as talas e verificar
todas as emendas do modelo de uma vez (:mod:`core.emendas_do_modelo`)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd
import streamlit as st

from components.emenda_pilar_help import AJUDA
from components.project_tools import botao_registrar_calculo
from core import colunas_do_modelo as cdm
from core import emenda_pilar as ep
from core import emendas_do_modelo as edm
from core import leitura_do_modelo as ld
from core import load_combinations as comb
from core import plano_de_cargas as pc
from core import tratamento_do_modelo as tm

PENDENTE = "emp_valores_pendentes"
NOTAS = "emp_notas_da_origem"
CASOS_BASE = "emp_casos_base"


# ---------------------------------------------------------------------------------------------
# Os campos da página
# ---------------------------------------------------------------------------------------------
def _sufixo(e: ep.EntradaEmenda) -> str:
    return "_u" if ep.PERFIS[e.perfil_superior].familia == ep.FAMILIA_U else ""


def campos_dos_perfis_e_esforcos(e: ep.EntradaEmenda) -> dict[str, Any]:
    """Os valores dos campos da página que vêm do modelo: perfis, aço, pilar e esforços."""
    s = _sufixo(e)
    campos: dict[str, Any] = {
        "emp_familia": ep.PERFIS[e.perfil_superior].familia,
        f"emp_perfil_s{s}": e.perfil_superior,
        f"emp_perfil_i{s}": e.perfil_inferior,
        "emp_aco_p": e.aco_perfis,
        "emp_Lx": float(e.Lx), "emp_Kx": float(e.Kx), "emp_Ly": float(e.Ly),
        "emp_Ky": float(e.Ky), "emp_a": float(e.a),
        "emp_vao_b": float(e.vao_b or 0.0),
        "emp_usar_nc": e.Nc_Rd_informado is not None,
    }  # fmt: skip
    if e.Nc_Rd_informado is not None:
        campos["emp_nc"] = float(e.Nc_Rd_informado)
    campos[CASOS_BASE] = [
        {"Caso": c.nome, "N (kN)": c.N, "M_x (kN·m)": c.Mx, "V (kN)": c.V, "M_y (kN·m)": c.My}
        for c in e.casos
    ]
    return campos


def campos_das_talas(e: ep.EntradaEmenda) -> dict[str, Any]:
    s = _sufixo(e)
    return {
        f"emp_bp{s}": float(e.bp), f"emp_tp{s}": float(e.tp), f"emp_nl{s}": int(e.nl),
        "emp_nr": int(e.nr), f"emp_g{s}": float(e.g), "emp_s": float(e.s), "emp_ep": float(e.ep),
        "emp_ec": float(e.ec), "emp_x1_u": float(e.x1_u), "emp_bw": float(e.bw),
        "emp_twp": float(e.twp), "emp_nc_alma": int(e.nc), "emp_m": int(e.m),
        "emp_sh": float(e.sh), "emp_sv": float(e.sv), "emp_ewv": float(e.ewv),
        "emp_ewc": float(e.ewc),
    }  # fmt: skip


def deixar_para_a_proxima(campos: Mapping[str, Any], notas: list[str]) -> None:
    """Os valores entram nos campos na próxima execução, antes de os campos serem desenhados (o
    Streamlit não deixa trocar o valor de um campo que já está na tela)."""
    st.session_state[PENDENTE] = dict(campos)
    st.session_state[NOTAS] = list(notas)


def aplicar_pendentes() -> None:
    """Chamado no começo da página, antes de qualquer campo."""
    campos = st.session_state.pop(PENDENTE, None)
    if not campos:
        return
    for chave, valor in campos.items():
        st.session_state[chave] = valor
    if CASOS_BASE in campos:
        st.session_state.pop("emp_casos", None)  # as edições antigas da tabela não valem mais


def casos_da_tabela(padrao: list[dict[str, Any]]) -> pd.DataFrame:
    linhas = st.session_state.get(CASOS_BASE) or padrao
    return pd.DataFrame(linhas, columns=["Caso", "N (kN)", "M_x (kN·m)", "V (kN)", "M_y (kN·m)"])


def mostrar_notas_da_origem() -> None:
    notas = st.session_state.get(NOTAS) or []
    if notas:
        st.info("\n".join(f"- {n}" for n in notas), icon=":material/info:")


# ---------------------------------------------------------------------------------------------
# O modelo do projeto
# ---------------------------------------------------------------------------------------------
class ModeloDoProjeto:
    def __init__(self, projeto: Mapping[str, Any] | None) -> None:
        self.dados = tm.do_projeto(projeto).dados if projeto else None
        self.geometria = ld.geometria_do_projeto(projeto) if projeto else ld.GeometriaDoModelo()
        self.plano = pc.plano_do_projeto(projeto) if projeto else pc.PlanoDeCargas()
        self.leituras: list[ld.LeituraDaBarra] = []
        self.emendas: list[edm.EmendaDoModelo] = []
        if self.dados is not None and self.dados.casos and self.geometria.corpos:
            self.leituras = ld.ler_barras(self.dados, self.geometria, self.plano)
            self.emendas = edm.achar_emendas(self.dados, self.leituras)

    @property
    def tem_modelo(self) -> bool:
        return self.dados is not None and bool(self.dados.casos) and bool(self.geometria.corpos)


def secao_trazer_do_modelo(modelo: ModeloDoProjeto, padrao: ep.EntradaEmenda) -> None:
    st.subheader("Trazer do modelo do SolidWorks", help=AJUDA["sec_do_modelo"])
    if not modelo.tem_modelo:
        st.caption(
            "O projeto ativo não tem o modelo do SolidWorks (os casos e o esqueleto). Envie em "
            "Esforços do modelo para trazer as emendas de lá; aqui dá para digitar tudo."
        )
        st.page_link("app_pages/esforcos_modelo.py", label="Esforços do modelo",
                     icon=":material/upload_file:")  # fmt: skip
        return
    if not modelo.emendas:
        st.caption(
            "Nenhuma emenda no modelo: dois pilares em pé que se encontram viram emenda, e em "
            "Esforços do modelo (seção Emendas dos pilares) dá para informar uma no meio de um "
            "pilar."
        )
        st.page_link("app_pages/esforcos_modelo.py", label="Esforços do modelo",
                     icon=":material/upload_file:")  # fmt: skip
        return
    c = st.columns([2, 1.4, 1])
    nomes = [e.nome for e in modelo.emendas]
    escolhida = c[0].selectbox("Emenda do modelo", nomes, key="emp_emenda_do_modelo",
                               help=AJUDA["emenda_do_modelo"])  # fmt: skip
    estados = c[1].multiselect(
        "Estados-limite", list(comb.COMBINACOES_ULTIMAS), default=[comb.ELU_NORMAL],
        key="emp_estados", help=AJUDA["estados"],
    )  # fmt: skip
    base = c[2].radio("Base no apoio", cdm.BASES, key="emp_base_modelo", help=AJUDA["base"])
    if not estados:
        st.caption("Escolha pelo menos um estado-limite.")
        return
    if st.button("Trazer esta emenda", icon=":material/download:", key="emp_trazer",
                 help=AJUDA["btn_trazer"]):  # fmt: skip
        assert modelo.dados is not None
        emenda = modelo.emendas[nomes.index(escolhida)]
        preparo = edm.preparar(modelo.dados, modelo.plano, estados)
        if preparo is None:
            st.error("Nenhum caso do plano de cargas foi importado.", icon=":material/error:")
            return
        (esforcos,) = edm.ler_esforcos(modelo.dados, modelo.leituras, preparo, [emenda])
        montada = edm.montar_entrada(
            esforcos, modelo.dados, modelo.geometria, modelo.leituras, padrao, base=str(base)
        )
        if montada.entrada is None:
            st.error(f"{emenda.nome}: {montada.motivo}", icon=":material/error:")
            return
        notas = [f"Trazido do modelo: {emenda.nome} ({emenda.origem}); esforços {esforcos.como}."]
        deixar_para_a_proxima(
            campos_dos_perfis_e_esforcos(montada.entrada),
            notas + list(montada.notas) + list(esforcos.avisos),
        )
        st.rerun()


def botao_sugerir_talas(entrada: ep.EntradaEmenda) -> None:
    st.subheader("Sugerir as talas", help=AJUDA["sec_sugerir"])
    if not st.button("Sugerir as talas para estes perfis, parafuso e esforços",
                     icon=":material/auto_fix_high:", key="emp_sugerir",
                     help=AJUDA["btn_sugerir"]):  # fmt: skip
        return
    try:
        s = ep.sugerir_talas(entrada)
    except ValueError as falha:
        st.error(str(falha), icon=":material/error:")
        return
    if not s.cabe:
        for nota in s.notas:
            st.error(nota, icon=":material/error:")
        return
    deixar_para_a_proxima(campos_das_talas(s.entrada), list(s.notas))
    st.rerun()


def secao_todas_as_emendas(modelo: ModeloDoProjeto, padrao: ep.EntradaEmenda) -> None:
    st.subheader("Todas as emendas do modelo", help=AJUDA["sec_todas"])
    if not modelo.tem_modelo or not modelo.emendas:
        st.caption("Sem emendas no modelo do projeto ativo.")
        return
    estados = st.session_state.get("emp_estados") or [comb.ELU_NORMAL]
    base = str(st.session_state.get("emp_base_modelo") or cdm.BASE_ROTULADA)
    st.caption(
        f"{len(modelo.emendas)} emenda(s). Cada uma com o parafuso, os aços das talas e o tipo de "
        "emenda desta página, e as talas sugeridas para ela. Estados-limite: "
        + ", ".join(estados)
        + "."
    )
    if not st.toggle("Verificar todas as emendas", key="emp_verificar_todas",
                     help=AJUDA["verificar_todas"]):  # fmt: skip
        return
    assert modelo.dados is not None
    verificadas, avisos = edm.verificar_emendas(
        modelo.dados, modelo.geometria, modelo.plano, estados, padrao, base=base,
        leituras=modelo.leituras,
    )  # fmt: skip
    for aviso in avisos:
        st.warning(aviso, icon=":material/warning:")
    st.dataframe(
        pd.DataFrame(edm.linhas_da_tabela(verificadas), columns=list(edm.COLUNAS)),
        hide_index=True,
        width="stretch",
        column_config={
            "Aproveitamento (%)": st.column_config.ProgressColumn(
                min_value=0.0, max_value=100.0, format="%.0f %%"
            ),
            **{c: st.column_config.NumberColumn(format="%.2f") for c in edm.COLUNAS if "(kN" in c},
        },
    )
    botao_registrar_calculo(
        edm.registro_das_emendas(verificadas, padrao, estados),
        key="registrar_emendas_do_modelo",
        rotulo="Registrar todas as emendas no projeto ativo",
        identificar_peca=False,
    )
