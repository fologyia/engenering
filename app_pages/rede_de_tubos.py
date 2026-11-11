"""Rede de tubos: desenhe a rede na prancheta; as tabelas só completam o que o desenho não dá.

Os dados moram em ``st.session_state`` e três lugares os mudam: a prancheta, o painel do item
selecionado e as tabelas. Os três entram por callback, antes de o script rodar. ``rede_versao``
conta as mudanças: a prancheta ignora um desenho mais velho que o dela.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd
import streamlit as st

from components.prancheta_rede_ui import prancheta_da_rede
from components.project_tools import botao_registrar_calculo
from components.rede_de_tubos_help import AJUDA
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from components.verification_table import mostrar_tabela_verificacoes
from core import montador_fluidos as fl
from core import rede_de_tubos as rt

configurar_pagina("Rede de tubos", ":material/lan:")
cabecalho_pagina(
    "Rede de tubos",
    "Desenhe a rede: reservatórios, nós de consumo e os tubos entre eles, com ramais e malhas. "
    "A página dá a vazão de cada tubo e a pressão de cada nó, com a rede inteira resolvida de "
    "uma vez.",
    categoria="Mecânica",
    icone=":material/lan:",
    modulo_id=rt.MODULO_ID,
)
st.page_link(
    "app_pages/montador_fluidos.py",
    label="Ir para o Montador de fluidos (linha em série, bomba e NPSH)",
    icon=":material/water_drop:",
)

DADOS = "rede_dados"
VERSAO = "rede_versao"
AJUSTE = "rede_ajuste"
SELECAO = "rede_selecao"
REVISAO = "rede_tabela_rev"
CHAVE_PRANCHETA = "rede_prancheta"
INFORMAR = fl.INFORMAR
MATERIAIS = [*fl.RUGOSIDADES, rt.OUTRO_MATERIAL]
TIPOS = {rt.RESERVATORIO: "Reservatório", rt.CONSUMO: "Consumo"}
estado = st.session_state


def _trocar(dados: Mapping[str, Any], *, versao: int | None = None, ajustar: bool = False) -> None:
    estado[DADOS] = {
        "nos": [dict(n) for n in dados.get("nos") or ()],
        "trechos": [dict(t) for t in dados.get("trechos") or ()],
    }
    estado[VERSAO] = estado.get(VERSAO, 0) + 1 if versao is None else versao
    estado[REVISAO] = estado.get(REVISAO, 0) + 1
    if ajustar:
        estado[AJUSTE] = estado.get(AJUSTE, 0) + 1


if not isinstance(estado.get(DADOS), dict):
    _trocar(rt.exemplo_desenhado(), versao=0, ajustar=True)


def _ao_desenhar() -> None:
    evento = getattr(estado.get(CHAVE_PRANCHETA), "edicao", None)
    if not evento:
        return
    dados = evento.get("dados") or {}
    if not isinstance(dados.get("nos"), list) or not isinstance(dados.get("trechos"), list):
        return
    _trocar(dados, versao=int(evento.get("versao", 0)))


def _ao_selecionar() -> None:
    selecao = getattr(estado.get(CHAVE_PRANCHETA), "selecao", None)
    estado[SELECAO] = dict(selecao) if isinstance(selecao, Mapping) else None


def _ao_mudar_campo(lista: str, id_: str, campo: str, chave: str) -> None:
    dados = {k: [dict(x) for x in v] for k, v in estado[DADOS].items()}
    for item in dados[lista]:
        if item.get("id") == id_:
            valor = estado.get(chave)
            if campo == "tipo":
                valor = next((k for k, v in TIPOS.items() if v == valor), rt.CONSUMO)
                item["nivel"] = item.get("nivel") or (item.get("cota") or 0.0) + 20.0
            item[campo] = valor
    _trocar(dados)


def _voltar_ao_exemplo() -> None:
    estado[SELECAO] = None
    _trocar(rt.exemplo_desenhado(), ajustar=True)


def _limpar() -> None:
    estado[SELECAO] = None
    _trocar({"nos": [], "trechos": []}, ajustar=True)


# ============================================================ fluido e limites
with st.container(border=True), secao_protegida("Fluido e limites"):
    st.subheader("Fluido e limites", help=AJUDA["sec_fluido"])
    colunas = st.columns(6)
    nome_fluido = colunas[0].selectbox(
        "Fluido",
        [*fl.FLUIDOS_TIPICOS, INFORMAR],
        key="rede_fluido",
        persist_state="session",
        help=AJUDA["fluido"],
    )
    if nome_fluido == INFORMAR:
        rho = colunas[1].number_input(
            "ρ (kg/m³)", min_value=0.01, value=998.2, key="rede_rho", help=AJUDA["rho"]
        )
        mu = colunas[1].number_input(
            "μ (Pa·s)",
            min_value=1e-7,
            value=1.0016e-3,
            format="%.6f",
            key="rede_mu",
            help=AJUDA["mu"],
        )
    else:
        rho, mu, _ = fl.FLUIDOS_TIPICOS[nome_fluido]
        colunas[1].caption(f"ρ = {rho:g} kg/m³\n\nμ = {mu:.4g} Pa·s".replace(".", ","))
    p_min = colunas[2].number_input(
        "Pressão mínima (m)", min_value=0.0, value=10.0, step=1.0, key="rede_p_min",
        persist_state="session", help=AJUDA["p_min"],
    )  # fmt: skip
    p_max = colunas[3].number_input(
        "Pressão máxima (m)", min_value=0.0, value=40.0, step=1.0, key="rede_p_max",
        persist_state="session", help=AJUDA["p_max"],
    )  # fmt: skip
    v_max = colunas[4].number_input(
        "Velocidade máxima (m/s)", min_value=0.1, value=3.0, step=0.1, key="rede_v_max",
        persist_state="session", help=AJUDA["v_max"],
    )  # fmt: skip
    v_min = colunas[5].number_input(
        "Velocidade mínima (m/s)", min_value=0.0, value=0.0, step=0.1, key="rede_v_min",
        persist_state="session", help=AJUDA["v_min"],
    )  # fmt: skip

dados = estado[DADOS]
nos, trechos, faltas = rt.rede_do_desenho(dados, fl.RUGOSIDADES)
erros = [*faltas, *rt.problemas(nos, trechos)] if nos else []
fluido = rt.Fluido(nome_fluido, float(rho), float(mu))
limites = rt.Limites(float(p_min), float(p_max), float(v_max), float(v_min))
resultado: rt.ResultadoDaRede | None = None
falha = ""
if nos and trechos and not erros:
    try:
        resultado = rt.resolver(nos, trechos, fluido, limites)
    except rt.ErroDaRede as erro:
        falha = str(erro)

# ============================================================ prancheta + selecionado
with st.container(border=True):
    st.subheader("Desenho da rede", help=AJUDA["sec_desenho"])
    prancha, lateral = st.columns([2.6, 1], gap="small")
    with prancha:
        prancheta_da_rede(
            {
                "dados": dados,
                "versao": estado[VERSAO],
                "ajustar": estado.get(AJUSTE, 0),
                "marcas": None if resultado is None else rt.marcas_para_o_desenho(dados, resultado),
            },
            key=CHAVE_PRANCHETA,
            ao_desenhar=_ao_desenhar,
            ao_selecionar=_ao_selecionar,
        )
    with lateral, st.container(border=True):
        selecao = estado.get(SELECAO) or {}
        versao = estado[VERSAO]
        item: dict[str, Any] | None = None
        lista = "nos" if selecao.get("tipo") == "no" else "trechos"
        if selecao.get("tipo") in ("no", "trecho"):
            item = next((x for x in dados[lista] if x.get("id") == selecao.get("id")), None)
        if item is None:
            st.markdown("**Nada selecionado**")
            st.caption(AJUDA["sel_nada"])
        elif lista == "nos":
            base = f"rede_sel_{item['id']}_{versao}"

            def campo(nome: str) -> tuple[str, dict[str, Any]]:
                chave = f"{base}_{nome}"
                return chave, {
                    "key": chave,
                    "on_change": _ao_mudar_campo,
                    "args": ("nos", item["id"], nome, chave),
                }

            reservatorio = item.get("tipo") == rt.RESERVATORIO
            st.markdown(
                f"**{'Reservatório' if reservatorio else 'Nó de consumo'} {item.get('nome')}**"
            )
            st.text_input(
                "Nome", value=str(item.get("nome") or ""), help=AJUDA["no_nome"], **campo("nome")[1]
            )
            st.selectbox(
                "Tipo", list(TIPOS.values()), index=0 if reservatorio else 1,
                help=AJUDA["no_tipo"], **campo("tipo")[1],
            )  # fmt: skip
            st.number_input(
                "Cota (m)", value=float(item.get("cota") or 0.0), step=0.5, format="%.2f",
                help=AJUDA["no_cota"], **campo("cota")[1],
            )  # fmt: skip
            if reservatorio:
                st.number_input(
                    "Nível da água (m)", value=float(item.get("nivel") or 0.0), step=0.5,
                    format="%.2f", help=AJUDA["no_nivel"], **campo("nivel")[1],
                )  # fmt: skip
            else:
                st.number_input(
                    "Retirada (L/s)", value=float(item.get("retirada") or 0.0), step=0.5,
                    format="%.3f", help=AJUDA["no_retirada"], **campo("retirada")[1],
                )  # fmt: skip
            if resultado is not None:
                r_no = next((n for n in resultado.nos if n.nome == item.get("nome")), None)
                if r_no is not None:
                    st.caption(
                        f"Carga {r_no.carga_m:.2f} m · pressão {r_no.pressao_m:.2f} m "
                        f"({r_no.pressao_kPa:.1f} kPa)".replace(".", ",")
                    )
        else:
            base = f"rede_sel_{item['id']}_{versao}"

            def campo(nome: str) -> tuple[str, dict[str, Any]]:
                chave = f"{base}_{nome}"
                return chave, {
                    "key": chave,
                    "on_change": _ao_mudar_campo,
                    "args": ("trechos", item["id"], nome, chave),
                }

            desenhado = rt.comprimento_desenhado(dados, item)
            st.markdown(f"**Tubo {item.get('nome')}**")
            st.text_input(
                "Nome", value=str(item.get("nome") or ""), help=AJUDA["tr_nome"], **campo("nome")[1]
            )
            st.number_input(
                "Diâmetro interno (mm)", value=float(item.get("diametro") or 0.0), min_value=0.0,
                step=5.0, format="%.1f", help=AJUDA["tr_diametro"], **campo("diametro")[1],
            )  # fmt: skip
            material = str(item.get("material") or MATERIAIS[0])
            st.selectbox(
                "Material", MATERIAIS,
                index=MATERIAIS.index(material) if material in MATERIAIS else 0,
                help=AJUDA["tr_material"], **campo("material")[1],
            )  # fmt: skip
            st.number_input(
                "Comprimento real (m)",
                value=None if item.get("comprimento") is None else float(item["comprimento"]),
                min_value=0.0, step=1.0, format="%.2f",
                placeholder=f"{desenhado:.2f} pelo desenho".replace(".", ","),
                help=AJUDA["tr_comprimento"], **campo("comprimento")[1],
            )  # fmt: skip
            st.number_input(
                "K das peças", value=float(item.get("k") or 0.0), min_value=0.0, step=0.1,
                format="%.2f", help=AJUDA["tr_k"], **campo("k")[1],
            )  # fmt: skip
            st.number_input(
                "Bomba (m)", value=float(item.get("bomba") or 0.0), step=1.0, format="%.1f",
                help=AJUDA["tr_bomba"], **campo("bomba")[1],
            )  # fmt: skip
            if resultado is not None:
                r_tr = next((t for t in resultado.trechos if t.nome == item.get("nome")), None)
                if r_tr is not None:
                    st.caption(
                        f"{r_tr.sentido}: {abs(r_tr.vazao_L_s):.2f} L/s, {r_tr.velocidade:.2f} "
                        f"m/s, perda {r_tr.perda_m:.3f} m, {r_tr.regime}".replace(".", ",")
                    )
    botoes = st.columns([1, 1, 4])
    botoes[0].button(
        "Voltar ao exemplo", key="rede_exemplo", on_click=_voltar_ao_exemplo,
        help=AJUDA["exemplo"], icon=":material/restart_alt:", width="stretch",
    )  # fmt: skip
    botoes[1].button(
        "Limpar o desenho", key="rede_limpar", on_click=_limpar, help=AJUDA["limpar"],
        icon=":material/delete_sweep:", width="stretch",
    )  # fmt: skip


# ============================================================ tabelas, só para completar
def _ao_editar_tabela(lista: str, chave: str) -> None:
    mudancas = estado.get(chave) or {}
    dados_ = {k: [dict(x) for x in v] for k, v in estado[DADOS].items()}
    colunas_ = COLUNAS_NOS if lista == "nos" else COLUNAS_TRECHOS
    for indice, campos in (mudancas.get("edited_rows") or {}).items():
        i = int(indice)
        if not 0 <= i < len(dados_[lista]):
            continue
        for rotulo, valor in campos.items():
            campo = colunas_.get(rotulo)
            if campo is None:
                continue
            if campo == "tipo":
                valor = next((k for k, v in TIPOS.items() if v == valor), rt.CONSUMO)
            if isinstance(valor, float) and valor != valor:
                valor = None
            dados_[lista][i][campo] = valor
    _trocar(dados_)


COLUNAS_NOS = {
    "Nó": "nome",
    "Tipo": "tipo",
    "Cota (m)": "cota",
    "Nível da água (m)": "nivel",
    "Retirada (L/s)": "retirada",
}
COLUNAS_TRECHOS = {
    "Tubo": "nome",
    "Diâmetro interno (mm)": "diametro",
    "Material": "material",
    "Rugosidade (mm)": "rugosidade",
    "Comprimento real (m)": "comprimento",
    "K das peças": "k",
    "Bomba (m)": "bomba",
}
nomes = {str(n.get("id")): str(n.get("nome") or n.get("id")) for n in dados["nos"]}
with st.container(border=True), secao_protegida("Completar nas tabelas"):
    st.subheader("Completar nas tabelas", help=AJUDA["sec_tabelas"])
    if not dados["nos"]:
        st.caption("O desenho está vazio: as tabelas aparecem quando houver nós.")
    else:
        chave = f"rede_tabela_nos_{estado[REVISAO]}"
        tabela = pd.DataFrame(
            [
                {
                    "Nó": n.get("nome"),
                    "Tipo": TIPOS.get(str(n.get("tipo")), "Consumo"),
                    "Cota (m)": n.get("cota"),
                    "Nível da água (m)": n.get("nivel"),
                    "Retirada (L/s)": n.get("retirada"),
                }
                for n in dados["nos"]
            ]
        ).astype(
            {"Cota (m)": "float64", "Nível da água (m)": "float64", "Retirada (L/s)": "float64"}
        )
        st.data_editor(
            tabela,
            key=chave,
            hide_index=True,
            num_rows="fixed",
            width="stretch",
            on_change=_ao_editar_tabela,
            args=("nos", chave),
            column_config={
                "Nó": st.column_config.TextColumn(help=AJUDA["no_nome"]),
                "Tipo": st.column_config.SelectboxColumn(
                    options=list(TIPOS.values()), help=AJUDA["no_tipo"]
                ),
                "Cota (m)": st.column_config.NumberColumn(format="%.2f", help=AJUDA["no_cota"]),
                "Nível da água (m)": st.column_config.NumberColumn(
                    format="%.2f", help=AJUDA["no_nivel"]
                ),
                "Retirada (L/s)": st.column_config.NumberColumn(
                    format="%.3f", help=AJUDA["no_retirada"]
                ),
            },
        )
    if dados["trechos"]:
        chave = f"rede_tabela_trechos_{estado[REVISAO]}"
        tabela = pd.DataFrame(
            [
                {
                    "Tubo": t.get("nome"),
                    "De": nomes.get(str(t.get("de")), "?"),
                    "Para": nomes.get(str(t.get("para")), "?"),
                    "Desenhado (m)": round(rt.comprimento_desenhado(dados, t), 2),
                    "Comprimento real (m)": t.get("comprimento"),
                    "Diâmetro interno (mm)": t.get("diametro"),
                    "Material": t.get("material") or MATERIAIS[0],
                    "Rugosidade (mm)": t.get("rugosidade"),
                    "K das peças": t.get("k"),
                    "Bomba (m)": t.get("bomba"),
                }
                for t in dados["trechos"]
            ]
        ).astype(
            {
                "Comprimento real (m)": "float64",
                "Diâmetro interno (mm)": "float64",
                "Rugosidade (mm)": "float64",
                "K das peças": "float64",
                "Bomba (m)": "float64",
            }
        )
        st.data_editor(
            tabela,
            key=chave,
            hide_index=True,
            num_rows="fixed",
            width="stretch",
            on_change=_ao_editar_tabela,
            args=("trechos", chave),
            disabled=["De", "Para", "Desenhado (m)"],
            column_config={
                "Tubo": st.column_config.TextColumn(help=AJUDA["tr_nome"]),
                "De": st.column_config.TextColumn(help=AJUDA["tr_de"]),
                "Para": st.column_config.TextColumn(help=AJUDA["tr_para"]),
                "Desenhado (m)": st.column_config.NumberColumn(
                    format="%.2f", help=AJUDA["tr_desenhado"]
                ),
                "Comprimento real (m)": st.column_config.NumberColumn(
                    min_value=0.0, format="%.2f", help=AJUDA["tr_comprimento"]
                ),
                "Diâmetro interno (mm)": st.column_config.NumberColumn(
                    min_value=0.0, format="%.1f", help=AJUDA["tr_diametro"]
                ),
                "Material": st.column_config.SelectboxColumn(
                    options=MATERIAIS, help=AJUDA["tr_material"]
                ),
                "Rugosidade (mm)": st.column_config.NumberColumn(
                    min_value=0.0, format="%.4f", help=AJUDA["tr_rugosidade"]
                ),
                "K das peças": st.column_config.NumberColumn(
                    min_value=0.0, format="%.2f", help=AJUDA["tr_k"]
                ),
                "Bomba (m)": st.column_config.NumberColumn(format="%.1f", help=AJUDA["tr_bomba"]),
            },
        )

# ============================================================ resultado
with st.container(border=True), secao_protegida("Resultado da rede"):
    st.subheader("Resultado da rede", help=AJUDA["sec_resultado"])
    if not nos or not trechos:
        st.info(
            "Desenhe ao menos um reservatório, um nó e um tubo entre eles: o resultado aparece "
            "aqui e no próprio desenho.",
            icon=":material/draw:",
        )
        st.stop()
    for erro in erros:
        st.error(erro, icon=":material/error:")
    if falha:
        st.error(falha, icon=":material/error:")
    if resultado is None:
        st.stop()
    if resultado.status == "OK":
        st.success(
            "A rede atende: pressões e velocidades dentro dos limites.",
            icon=":material/check_circle:",
        )
    else:
        st.error(
            "A rede não atende em algum ponto: o que não passa está em vermelho no desenho e NÃO "
            "OK na tabela de verificação.",
            icon=":material/error:",
        )
    consumo = [n for n in resultado.nos if not n.reservatorio]
    menor = min(consumo, key=lambda n: n.pressao_m, default=None)
    maior = max(resultado.trechos, key=lambda t: t.velocidade)
    metricas = st.columns(4)
    metricas[0].metric(
        "Consumo", f"{resultado.consumo_L_s:.2f} L/s".replace(".", ","), help=AJUDA["res_consumo"]
    )
    metricas[1].metric(
        "Menor pressão",
        "—" if menor is None else f"{menor.pressao_m:.1f} m ({menor.nome})".replace(".", ","),
        help=AJUDA["res_pressao"],
    )
    metricas[2].metric(
        "Maior velocidade",
        f"{maior.velocidade:.2f} m/s ({maior.nome})".replace(".", ","),
        help=AJUDA["res_velocidade"],
    )
    metricas[3].metric(
        "Fechamento das malhas",
        f"{rt.soma_nas_malhas(trechos, resultado):.1e} m".replace(".", ","),
        help=AJUDA["res_malhas"],
    )
    for aviso in resultado.avisos:
        st.warning(aviso, icon=":material/warning:")
    st.dataframe(
        pd.DataFrame(rt.linhas_dos_trechos(resultado), columns=list(rt.COLUNAS_TRECHOS)),
        hide_index=True,
        width="stretch",
    )
    st.dataframe(
        pd.DataFrame(rt.linhas_dos_nos(resultado), columns=list(rt.COLUNAS_NOS)),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Pressão em metros de coluna do fluido. Nos reservatórios, a vazão é o que cada um manda "
        "para a rede (negativa: ele recebe)."
    )
    mostrar_tabela_verificacoes(list(resultado.verificacoes))
    st.download_button(
        "Resultados da rede (CSV)",
        data=rt.csv_da_rede(resultado),
        file_name="rede_de_tubos.csv",
        mime="text/csv",
        icon=":material/download:",
        key="rede_csv",
        help=AJUDA["csv"],
    )
    st.subheader("Registrar no projeto", help=AJUDA["registrar"])
    botao_registrar_calculo(
        rt.registro_da_rede(nos, trechos, resultado),
        key="registrar_rede_de_tubos",
        rotulo="Registrar a rede no projeto ativo",
        identificar_peca=False,
    )
