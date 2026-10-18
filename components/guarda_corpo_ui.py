"""Guarda-corpo nas bordas do piso (pelo esqueleto do modelo), na página Cargas do esqueleto.

O cálculo está em :mod:`core.guarda_corpo_do_modelo`; o desenho, em
:mod:`components.figura_guarda_corpo`.
"""

from __future__ import annotations

import zlib
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

import pandas as pd
import streamlit as st

from components.base_tecnica_ui import base_ativa, gravar_campos_do_projeto
from components.figura_guarda_corpo import svg_bordas_do_piso
from components.guarda_corpo_help import AJUDA
from components.robustez import secao_protegida
from core import guarda_corpo_do_modelo as gm
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc

COLUNA_USAR = "Tem guarda-corpo"
COLUNAS_A_MAO = ("Viga", "De (m)", "Até (m)", "Tipo")


def _numero_ou_vazio(valor: Any) -> float | None:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return None if numero != numero else numero  # NaN do editor = vazio


def _ajustes(
    escolha: gm.EscolhaDoGuardaCorpo, geometria: ld.GeometriaDoModelo, chave: str
) -> gm.EscolhaDoGuardaCorpo:
    """As duas chaves da escada automática e a tabela dos trechos à mão."""
    aberto = bool(
        escolha.a_mao or not escolha.acesso_pelas_longarinas or not escolha.guarda_corpo_nos_lances
    )
    with st.expander("Ajustes: escada automática e trechos à mão", expanded=aberto):
        colunas = st.columns(2)
        longarinas = colunas[0].toggle(
            "Achar o acesso da escada pelas longarinas",
            value=escolha.acesso_pelas_longarinas,
            key=f"{chave}_longarinas",
            help=AJUDA["opcao_longarinas"],
        )
        lances = colunas[1].toggle(
            "Guarda-corpo nos lances de escada",
            value=escolha.guarda_corpo_nos_lances,
            key=f"{chave}_lances",
            help=AJUDA["opcao_lances"],
        )
        vigas = sorted(c.nome for c in geometria.corpos if c.e_barra and gm._corpo_valido(c))
        inicial = pd.DataFrame(
            [[m.viga, m.de_m, m.ate_m, m.tipo] for m in escolha.a_mao], columns=COLUNAS_A_MAO
        )
        st.caption("Trechos à mão", help=AJUDA["tabela_a_mao"])
        editada = st.data_editor(
            inicial,
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key=f"{chave}_a_mao",
            column_config={
                "Viga": st.column_config.SelectboxColumn(
                    options=vigas, required=True, help="A viga do esqueleto."
                ),
                "De (m)": st.column_config.NumberColumn(
                    min_value=0.0, format="%.2f", help="Do início da viga (vazio: 0)."
                ),
                "Até (m)": st.column_config.NumberColumn(
                    min_value=0.0, format="%.2f", help="Do início da viga (vazio: o fim dela)."
                ),
                "Tipo": st.column_config.SelectboxColumn(
                    options=list(gm.TIPOS_A_MAO),
                    default=gm.TIPO_MAO_GUARDA_CORPO,
                    required=True,
                    help="Guarda-corpo onde o programa não achou; acesso ou portão onde não tem.",
                ),
            },
        )
        manuais = []
        for linha in editada.to_dict("records"):
            viga = str(linha.get("Viga") or "").strip()
            if not viga or viga == "None":
                continue
            tipo = str(linha.get("Tipo") or gm.TIPO_MAO_GUARDA_CORPO)
            manuais.append(
                gm.TrechoAMao(
                    viga, _numero_ou_vazio(linha.get("De (m)")), _numero_ou_vazio(linha.get("Até (m)")),
                    tipo if tipo in gm.TIPOS_A_MAO else gm.TIPO_MAO_GUARDA_CORPO,
                )
            )  # fmt: skip
    return replace(
        escolha,
        acesso_pelas_longarinas=bool(longarinas),
        guarda_corpo_nos_lances=bool(lances),
        a_mao=tuple(manuais),
    )


def _pt(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def assinatura(bordas: gm.BordasDoPiso) -> str:
    """Muda quando o esqueleto muda (a tabela volta para a sugestão nova)."""
    texto = "|".join(t.chave for t in bordas.trechos)
    return f"{zlib.crc32(texto.encode('utf-8')):08x}"


def escolha_inicial(projeto: Mapping[str, Any] | None) -> gm.EscolhaDoGuardaCorpo:
    """A escolha gravada; sem ela, a altura do critério do projeto (Anglo: 1,30 m)."""
    escolha = gm.escolha_do_projeto(projeto)
    gravada = isinstance((projeto or {}).get(gm.CHAVE_DO_PROJETO), Mapping)
    base = base_ativa()
    if not gravada and base is not None and base.anglo:
        escolha = replace(escolha, altura_m=gm.ALTURA_ANGLO_M)
    return escolha


def mostrar_guarda_corpo_do_modelo(
    projeto: Mapping[str, Any],
    geometria: ld.GeometriaDoModelo,
    eixo_vertical: str,
    nomes_no_simulation: Mapping[str, str],
    plano: pc.PlanoDeCargas,
    *,
    chave: str = "gc",
) -> bool:
    """O bloco inteiro; devolve ``True`` quando gravou algo (a página recarrega)."""
    with st.container(border=True), secao_protegida("Guarda-corpo nas bordas do piso"):
        st.subheader("Guarda-corpo nas bordas do piso", help=AJUDA["sec_guarda_corpo"])
        escolha = _ajustes(escolha_inicial(projeto), geometria, chave)
        bordas = gm.bordas_do_projeto(geometria, eixo_vertical, escolha)
        if not bordas.trechos:
            st.info(
                "Não achei borda de piso no esqueleto (sem chapas de piso e sem vigas horizontais "
                "com paralelas no mesmo nível). Lance os trechos à mão nos ajustes acima, ou use a "
                "forma pelos eixos, abaixo.",
                icon=":material/info:",
            )
            for aviso in bordas.avisos:
                st.caption(f":material/info: {aviso}")
            return False
        # O que foi trocado nesta sessão sobrevive a uma mudança nos ajustes (a tabela é refeita).
        chave_sessao = f"{chave}_trocados_sessao"
        trocados_antes = {**escolha.trocados, **st.session_state.get(chave_sessao, {})}
        tabela = pd.DataFrame(
            [
                {
                    COLUNA_USAR: bordas.marcado(t, trocados_antes) if t.viga else False,
                    "Trecho": t.id,
                    "Situação": t.situacao,
                    "Viga": t.viga or "—",
                    "Viga no Simulation": nomes_no_simulation.get(t.viga, "—"),
                    "Comprimento (m)": round(t.comprimento_m, 3),
                    "Chapa": t.chapa or "—",
                    "Por quê": t.motivo,
                }
                for t in bordas.trechos
            ]
        )
        editada = st.data_editor(
            tabela,
            hide_index=True,
            width="stretch",
            key=f"{chave}_tabela_{assinatura(bordas)}",
            disabled=[c for c in tabela.columns if c != COLUNA_USAR],
            column_config={
                COLUNA_USAR: st.column_config.CheckboxColumn(help=AJUDA["tabela"]),
                "Comprimento (m)": st.column_config.NumberColumn(format="%.2f"),
            },
        )
        marcado_na_tabela = {
            linha["Trecho"]: bool(linha[COLUNA_USAR]) for linha in editada.to_dict("records")
        }
        trocados = {
            t.chave: marcado_na_tabela.get(t.id, t.sugerido)
            for t in bordas.trechos
            if not t.a_mao and marcado_na_tabela.get(t.id, t.sugerido) != t.sugerido
        }
        st.session_state[chave_sessao] = trocados
        escolha_tela = {
            t.chave: marcado_na_tabela.get(t.id, t.sugerido) for t in bordas.trechos if not t.a_mao
        }
        marcados = bordas.marcados(escolha_tela)
        if any(t.a_mao for t in bordas.trechos):
            st.caption(
                ":material/edit: Os trechos M… são os lançados à mão: mude-os na tabela dos ajustes "
                "(aqui a marca deles não vale)."
            )
        colunas = st.columns(4)
        colunas[0].metric("Bordas", bordas.metodo.split(" (")[0], help=AJUDA["res_metodo"])
        colunas[1].metric(
            "Com guarda-corpo",
            f"{_pt(sum(t.comprimento_m for t in marcados))} m",
            help=AJUDA["res_comprimento"],
        )
        colunas[2].metric(
            "Acesso da escada",
            f"{_pt(bordas.comprimento(gm.SITUACAO_ACESSO))} m",
            help=AJUDA["res_acesso"],
        )
        colunas[3].metric(
            "Borda sem viga",
            f"{_pt(bordas.comprimento(gm.SITUACAO_SEM_VIGA))} m",
            help=AJUDA["res_sem_viga"],
        )
        for aviso in bordas.avisos:
            st.warning(aviso, icon=":material/warning:")
        st.caption("Planta das bordas", help=AJUDA["res_desenho"])
        st.image(
            svg_bordas_do_piso(bordas, geometria, eixo_vertical, escolha_tela), width="stretch"
        )
        linha = st.columns(3)
        peso = linha[0].number_input(
            "Peso do guarda-corpo (kN/m)",
            min_value=0.0,
            max_value=5.0,
            value=float(escolha.peso_kN_m),
            step=0.05,
            format="%.2f",
            key=f"{chave}_peso",
            help=AJUDA["peso"],
        )
        altura = linha[1].number_input(
            "Altura do guarda-corpo (m)",
            min_value=0.5,
            max_value=2.5,
            value=float(escolha.altura_m),
            step=0.05,
            format="%.2f",
            key=f"{chave}_altura",
            help=AJUDA["altura"],
        )
        phi = linha[2].number_input(
            "Índice de área exposta φ (vento)",
            min_value=0.05,
            max_value=1.0,
            value=float(escolha.phi),
            step=0.05,
            format="%.2f",
            key=f"{chave}_phi",
            help=AJUDA["phi"],
        )
        pesos = gm.pesos_nas_vigas(marcados, float(peso), nomes_no_simulation)
        st.caption("Peso nas vigas de borda (PE)", help=AJUDA["res_pesos"])
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Viga": p.rotulo,
                        "Trechos": ", ".join(p.trechos),
                        "Com guarda-corpo (m)": p.comprimento_com_guarda_corpo_m,
                        "Viga (m)": p.comprimento_da_viga_m,
                        "Total (kN)": p.total_kN,
                        "kN/m na viga": p.kN_m_na_viga,
                    }
                    for p in pesos
                ]
            ),
            hide_index=True,
            width="stretch",
            column_config={
                "Com guarda-corpo (m)": st.column_config.NumberColumn(format="%.2f"),
                "Viga (m)": st.column_config.NumberColumn(format="%.2f"),
                "Total (kN)": st.column_config.NumberColumn(format="%.3f"),
                "kN/m na viga": st.column_config.NumberColumn(format="%.3f"),
            },
        )
        total = sum(p.total_kN for p in pesos)
        comprimento = sum(t.comprimento_m for t in marcados)
        st.caption(
            f":material/check_circle: Conferência: {_pt(total, 3)} kN nas vigas = "
            f"{_pt(float(peso))} kN/m × {_pt(comprimento)} m de guarda-corpo."
        )
        nova = replace(
            escolha,
            trocados=trocados,
            peso_kN_m=float(peso),
            altura_m=float(altura),
            phi=float(phi),
        )
        dados = gm.para_dicionario(nova, bordas)
        colunas = st.columns(2)
        if colunas[0].button(
            "Gravar e pôr o peso no plano (PE)",
            type="primary",
            icon=":material/send:",
            key=f"{chave}_enviar",
            help=AJUDA["btn_enviar"],
            width="stretch",
        ) and gravar_campos_do_projeto(
            {
                gm.CHAVE_DO_PROJETO: dados,
                "plano_de_cargas": pc.para_dicionario(gm.aplicar_peso_no_plano(plano, pesos)),
            },
            "Guarda-corpo nas bordas: escolha gravada e peso no PE",
        ):
            return True
        if colunas[1].button(
            "Só gravar a escolha (para o vento)",
            icon=":material/save:",
            key=f"{chave}_gravar",
            help=AJUDA["btn_gravar"],
            width="stretch",
        ) and gravar_campos_do_projeto(
            {gm.CHAVE_DO_PROJETO: dados}, "Guarda-corpo nas bordas: escolha gravada"
        ):
            return True
    return False
