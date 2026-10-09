"""Plano de cargas do projeto: ações com código padrão, cargas para o modelo, combinações e a
exportação para o SolidWorks, o Robot e outros programas."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.base_tecnica_help import AJUDA
from components.base_tecnica_ui import (
    gravar_acoes_no_plano,
    gravar_plano,
    mapa_do_projeto,
)
from components.figuras_estrutura import svg_convencao_de_eixos
from components.ui import cabecalho_pagina, configurar_pagina
from core import base_tecnica as bt
from core import criterio_anglo as ca
from core import exportacao_cargas as ex
from core import load_combinations as comb
from core import plano_de_cargas as pc
from core.memorial_verificacoes import decimal_ptbr
from core.project_store import obter_projeto_ativo

configurar_pagina("Plano de cargas", ":material/table_chart:")
cabecalho_pagina(
    "Plano de cargas",
    "As ações do projeto com código padrão, de onde vieram, as cargas que vão para o modelo "
    "(SolidWorks, Robot) e as combinações ELU e ELS — prontas para exportar.",
    categoria="Gestão industrial",
    icone=":material/table_chart:",
    cor="violet",
    ajuda_modulo="Plano de cargas",
    acoes=(
        ("app_pages/base_tecnica.py", "Base técnica", ":material/tune:"),
        ("app_pages/vento_estrutura_aberta.py", "Vento em estruturas abertas", ":material/air:"),
    ),
)
mapa_do_projeto(AJUDA["sec_mapa"])

projeto = obter_projeto_ativo()
if projeto is None:
    st.info(
        "Nenhum projeto ativo. Abra ou crie um em **Projetos permanentes**: o plano de cargas fica "
        "guardado no projeto.",
        icon=":material/folder_off:",
    )
    st.stop()

plano = pc.plano_do_projeto(projeto)
base = bt.base_do_projeto(projeto)
anglo = base is not None and base.anglo
ICONES = {
    pc.NIVEL_ERRO: ":material/error:",
    pc.NIVEL_ATENCAO: ":material/warning:",
    pc.NIVEL_OK: ":material/check_circle:",
}

# ============================================================ conferência
with st.container(border=True):
    st.subheader("Conferência do plano", help=AJUDA["sec_conferencia"])
    for item in pc.conferir_plano(plano, anglo=anglo):
        mostrar = {pc.NIVEL_ERRO: st.error, pc.NIVEL_ATENCAO: st.warning}.get(
            item.nivel, st.success
        )
        mostrar(item.texto, icon=ICONES[item.nivel])

# ============================================================ ações
with st.container(border=True):
    st.subheader(f"Ações ({len(plano.acoes)})", help=AJUDA["sec_plano"])
    if plano.acoes:
        linhas = []
        for a in plano.acoes:
            cat = comb.categoria_nbr(a.categoria)
            linhas.append(
                {
                    "Código": a.codigo,
                    "Símbolo": pc.simbolo(a),
                    "Nome": a.nome,
                    "Tipo": cat.tipo,
                    "Categoria NBR 8800": a.categoria,
                    "Grupo": a.grupo or "—",
                    "γ": cat.gamma,
                    "ψ0": cat.psi0,
                    "ψ1": cat.psi1,
                    "ψ2": cat.psi2,
                    "Origem": a.origem,
                    "Cargas": len(a.cargas),
                    "Resumo": a.resumo,
                }
            )
        st.dataframe(
            pd.DataFrame(linhas),
            hide_index=True,
            width="stretch",
            column_config={
                **{
                    c: st.column_config.NumberColumn(format="%.2f") for c in ("γ", "ψ0", "ψ1", "ψ2")
                },
                "Símbolo": st.column_config.TextColumn(
                    help="↓ gravidade; setas do vento na planta (W0 → +X, W90 ↑ +Y…); ΔT temperatura."
                ),
            },
        )
        st.caption(
            "Símbolos: ↓ g cargas de gravidade · → ↑ ← ↓ vento na planta (W0 = +X, W90 = +Y, "
            "W180 = −X, W270 = −Y) · ΔT temperatura · ⇄ ⇅ forças horizontais da ponte rolante."
        )
        for a in plano.acoes:
            with st.expander(f"{pc.simbolo(a)}  {a.codigo} — {a.nome} ({len(a.cargas)} carga(s))"):
                if a.descricao:
                    st.caption(a.descricao)
                if a.cargas:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Elemento": c.elemento,
                                    "Direção": c.direcao,
                                    "Valor": c.valor,
                                    "Unidade": c.unidade,
                                    "Observação": c.observacao,
                                }
                                for c in a.cargas
                            ]
                        ),
                        hide_index=True,
                        width="stretch",
                        column_config={"Valor": st.column_config.NumberColumn(format="%.3f")},
                    )
                colunas = st.columns(2)
                if colunas[0].button(
                    f"Editar {a.codigo}",
                    icon=":material/edit:",
                    key=f"pc_editar_{a.codigo}",
                    help=AJUDA["btn_editar"],
                ):
                    st.session_state["pc_codigo"] = a.codigo
                    st.session_state["pc_versao"] = int(st.session_state.get("pc_versao", 0)) + 1
                    st.rerun()
                if colunas[1].button(
                    f"Remover {a.codigo}",
                    icon=":material/delete:",
                    key=f"pc_remover_{a.codigo}",
                    help=AJUDA["btn_remover"],
                ):
                    if gravar_plano(
                        pc.sem_acao(plano, a.codigo), f"Plano de cargas: {a.codigo} removida"
                    ):
                        st.rerun()
    else:
        st.caption(
            "Plano vazio. Gere o vento nas páginas de vento (botão “Enviar ao plano de cargas”) e "
            "inclua aqui os pesos, a sobrecarga e as demais ações."
        )
    colunas = st.columns(2)
    if (
        colunas[0].button(
            "Incluir a sobrecarga da base técnica",
            icon=":material/add:",
            key="pc_incluir_sobrecarga",
            help=AJUDA["btn_sobrecarga"],
            disabled=base is None,
        )
        and base is not None
    ):
        acao = pc.nova_acao(
            "SC",
            origem="Base técnica do projeto",
            descricao=f"{base.sobrecarga_local} ({base.rotulo_cliente}).",
            resumo=f"{bt.numero(base.sobrecarga_kN_m2, 2)} kN/m² em todos os pisos",
            cargas=[
                pc.CargaDoModelo(
                    "Todos os pisos",
                    base.sobrecarga_kN_m2,
                    "kN/m²",
                    "Z (vertical)",
                    base.sobrecarga_local,
                )
            ],
        )
        if gravar_acoes_no_plano([acao], origem="Base técnica"):
            st.rerun()
    if colunas[1].button(
        "Incluir temperatura ±10 °C (Anglo 5.8)",
        icon=":material/thermostat:",
        key="pc_incluir_temperatura",
        help=AJUDA["btn_temperatura"],
    ):
        acoes = [
            pc.nova_acao(
                codigo,
                origem=ca.item("5.8"),
                resumo=f"{sinal}{ca.TEMPERATURA_VARIACAO_C:g} °C uniforme",
                cargas=[
                    pc.CargaDoModelo(
                        "Toda a estrutura", sinal_valor * ca.TEMPERATURA_VARIACAO_C, "°C", "—"
                    )
                ],
            )
            for codigo, sinal, sinal_valor in (("T+", "+", 1.0), ("T−", "−", -1.0))
        ]
        if gravar_acoes_no_plano(acoes, origem="critério Anglo 5.8"):
            st.rerun()

# ============================================================ adicionar ou editar
with st.container(border=True):
    st.subheader("Adicionar ou editar uma ação", help=AJUDA["sec_adicionar"])
    codigos = [c.codigo for c in pc.CODIGOS]
    codigo = st.selectbox(
        "Código",
        codigos,
        format_func=lambda c: (
            f"{pc.SIMBOLOS.get(c, '•')}  {c} — {pc.CODIGOS_POR_NOME[c].nome}"
            + ("  (no plano)" if plano.acao(c) else "")
        ),
        key="pc_codigo",
        help=AJUDA["codigo"],
    )
    existente = plano.acao(codigo)
    versao = int(st.session_state.get("pc_versao", 0))
    sufixo = f"{codigo}_{versao}"
    if existente:
        st.caption(
            f":material/edit_note: {codigo} já está no plano (origem: {existente.origem}). Os campos "
            "trazem o que está gravado; gravar substitui a ação."
        )
    with st.form(f"pc_formulario_{sufixo}", border=False):
        colunas = st.columns([2, 3])
        nome = colunas[0].text_input(
            "Nome",
            value=existente.nome if existente else "",
            key=f"pc_nome_{sufixo}",
            help=AJUDA["nome"],
            placeholder="vazio = nome padrão",
        )
        categorias = [c.rotulo for c in comb.CATEGORIAS_NBR8800]
        opcoes_categoria = ["", *categorias]
        categoria = colunas[1].selectbox(
            "Categoria (vazio = a do código)",
            opcoes_categoria,
            index=opcoes_categoria.index(existente.categoria)
            if existente and existente.categoria in opcoes_categoria
            else 0,
            format_func=lambda c: c or "a padrão do código",
            key=f"pc_categoria_{sufixo}",
            help=AJUDA["categoria_nbr"],
        )
        descricao = st.text_input(
            "Descrição",
            value=existente.descricao if existente else "",
            key=f"pc_descricao_{sufixo}",
            help=AJUDA["descricao"],
        )
        st.markdown("**Cargas para o modelo** (opcional)", help=AJUDA["cargas_tabela"])
        st.caption(
            "Z (vertical): valor positivo = para baixo. X e Y: o sinal vai no valor "
            "(−2 em X empurra para −X). Unidades do plano: kN, kN/m, kN/m², kN·m e °C — a "
            "exportação converte para o programa de destino."
        )
        tabela = st.data_editor(
            pd.DataFrame(
                [
                    {
                        "Elemento": c.elemento,
                        "Valor": c.valor,
                        "Unidade": c.unidade,
                        "Direção": c.direcao,
                        "Observação": c.observacao,
                    }
                    for c in (existente.cargas if existente else ())
                ],
                columns=["Elemento", "Valor", "Unidade", "Direção", "Observação"],
            ),
            num_rows="dynamic",
            hide_index=True,
            key=f"pc_cargas_{sufixo}",
            column_config={
                "Elemento": st.column_config.TextColumn(
                    help="Onde a carga é aplicada: pórtico, nível, viga, nó, piso."
                ),
                "Valor": st.column_config.NumberColumn(help="Valor característico."),
                "Unidade": st.column_config.SelectboxColumn(
                    options=list(pc.UNIDADES), help="Unidade do valor."
                ),
                "Direção": st.column_config.SelectboxColumn(
                    options=list(pc.DIRECOES), help="Eixo da carga (Z = vertical, para baixo)."
                ),
                "Observação": st.column_config.TextColumn(help="Nota livre."),
            },
        )
        gravar = st.form_submit_button(
            "Gravar a ação", type="primary", icon=":material/save:", help=AJUDA["btn_adicionar"]
        )
    if gravar:
        cargas = []
        for _, linha in tabela.iterrows():
            if pd.isna(linha.get("Valor")) or not str(linha.get("Elemento") or "").strip():
                continue
            cargas.append(
                pc.CargaDoModelo(
                    str(linha["Elemento"]).strip(),
                    float(linha["Valor"]),
                    str(linha.get("Unidade") or "kN"),
                    str(linha.get("Direção") or "—"),
                    str(linha.get("Observação") or ""),
                )
            )
        acao = pc.nova_acao(
            codigo,
            nome=nome,
            categoria=categoria,
            descricao=descricao,
            cargas=cargas,
            origem=existente.origem if existente else "Informada",
            registro_id=existente.registro_id if existente else "",
            resumo=existente.resumo if existente else "",
        )
        erros = pc.validar_acao(acao)
        if erros:
            for erro in erros:
                st.error(erro, icon=":material/error:")
        elif gravar_acoes_no_plano([acao], origem="informada" if not existente else "edição"):
            st.session_state["pc_versao"] = versao + 1
            st.rerun()

if not plano.acoes:
    st.stop()

# ============================================================ combinações
with st.container(border=True):
    st.subheader("Combinações", help=AJUDA["res_combinacoes"])
    estados = st.multiselect(
        "Estados-limite",
        list(comb.TODOS_OS_ESTADOS),
        default=list(comb.ESTADOS_PADRAO),
        key="pc_estados",
        help=AJUDA["estados"],
    )
    lista = pc.combinacoes(plano, estados) if estados else []
    st.caption(
        f"{len(lista)} combinações. Fatores das Tabelas 1 e 2 da NBR 8800; o vento nas quatro "
        "direções é um grupo exclusivo. Valores característicos no modelo, combinações aqui."
    )
    if lista:
        ver = st.radio(
            "Mostrar",
            ["Matriz de fatores", "Expressões"],
            horizontal=True,
            key="pc_ver_como",
            help=AJUDA["ver_como"],
        )
        if ver == "Matriz de fatores":
            cabecalho, linhas_matriz = ex.matriz_de_combinacoes(plano, estados)
            matriz = pd.DataFrame(
                [linha[:-1] for linha in linhas_matriz], columns=cabecalho[:-1]
            ).replace(0.0, None)

            def _cor(valor: object) -> str:
                if not isinstance(valor, float) or pd.isna(valor):
                    return ""
                if valor > 1.0 + 1e-9:
                    return "background-color: #f6d2c1; color: #712b13"
                return "background-color: #d6e6f7; color: #0c447c"

            st.dataframe(
                matriz.style.map(_cor, subset=list(plano.codigos)).format(
                    lambda v: "" if v is None or pd.isna(v) else f"{v:.2f}".replace(".", ","),
                    subset=list(plano.codigos),
                ),
                hide_index=True,
                width="stretch",
                height=min(460, 40 + 35 * len(matriz)),
            )
            st.caption(
                "Laranja: fator maior que 1 (a ação entra majorada) · azul: fator até 1 "
                "(acompanhante com ψ, permanente favorável ou serviço) · vazio: a ação não entra."
            )
        else:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Combinação": ex.nome_da_combinacao(c, len(lista)),
                            "Estado-limite": c.estado_limite,
                            "Expressão": decimal_ptbr(c.expressao),
                        }
                        for c in lista
                    ]
                ),
                hide_index=True,
                width="stretch",
                height=min(460, 40 + 35 * len(lista)),
            )
    if anglo:
        st.subheader("Combinações mínimas do critério Anglo (5.9)", help=AJUDA["res_anglo"])
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Combinação mínima": c.combinacao,
                        "Situação": "pode ser formada" if c.coberta else "faltam ações",
                        "Faltam": ", ".join(c.faltantes) or "—",
                        "Só se houver o equipamento": ", ".join(c.opcionais_ausentes) or "—",
                    }
                    for c in pc.cobertura_das_combinacoes_anglo(plano)
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption(f"{ca.LEGENDA_COMBINACOES} {ca.QUADRO_DE_CARGAS_FUNDACOES}")

# ============================================================ exportar para o modelo
with st.container(border=True):
    st.subheader("Exportar para o modelo", help=AJUDA["sec_modelo"])
    colunas = st.columns(2)
    nome_sistema = colunas[0].selectbox(
        "Unidades do programa",
        list(ex.SISTEMAS),
        key="pc_unidades",
        help=AJUDA["unidades_destino"],
    )
    eixos = colunas[1].selectbox(
        "Eixo vertical do modelo",
        list(ex.EIXOS),
        key="pc_eixos",
        help=AJUDA["eixos_destino"],
    )
    sistema = ex.SISTEMAS[nome_sistema]
    st.subheader("Convenção de eixos e sinais", help=AJUDA["res_convencao"])
    st.image(svg_convencao_de_eixos(eixos), width="stretch")
    linhas_carga = ex.linhas_de_carga(plano, sistema, eixos)
    st.subheader(f"Cargas por caso ({len(linhas_carga)})", help=AJUDA["res_previa"])
    if linhas_carga:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Caso": linha.caso,
                        "Tipo": linha.tipo,
                        "Onde aplicar": linha.elemento,
                        "Valor": linha.valor,
                        "Unidade": linha.unidade,
                        "Fx": linha.fx,
                        "Fy": linha.fy,
                        "Fz": linha.fz,
                        "Sentido": linha.sentido,
                        "No SolidWorks": linha.solidworks,
                    }
                    for linha in linhas_carga
                ]
            ),
            hide_index=True,
            width="stretch",
            height=min(420, 40 + 35 * len(linhas_carga)),
            column_config={
                c: st.column_config.NumberColumn(format="%.4g") for c in ("Valor", "Fx", "Fy", "Fz")
            },
        )
    else:
        st.caption("Nenhuma carga para o modelo ainda: só as combinações serão exportadas.")
    codigo_projeto = str(projeto.get("codigo") or "projeto")
    estados_exportados = estados or list(comb.ESTADOS_PADRAO)
    st.download_button(
        "Planilha completa (Excel)",
        data=ex.xlsx_do_plano(
            plano,
            sistema=sistema,
            eixos=eixos,
            estados=estados_exportados,
            titulo=f"{projeto.get('nome', '')} ({codigo_projeto})",
            anglo=anglo,
        ),
        file_name=f"plano_de_cargas_{codigo_projeto}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/table_view:",
        type="primary",
        key="pc_xlsx",
        help=AJUDA["btn_xlsx"],
    )
    colunas = st.columns(4)
    for coluna, (rotulo, dados, arquivo, chave, ajuda) in zip(
        colunas,
        (
            (
                "Cargas por caso (CSV)",
                ex.csv_de_cargas(plano, sistema, eixos),
                "cargas",
                "csv_cargas",
                AJUDA["btn_csv_cargas"],
            ),
            (
                "Combinações — matriz (CSV)",
                ex.csv_matriz(plano, estados_exportados),
                "combinacoes_matriz",
                "csv_matriz",
                AJUDA["btn_csv_matriz"],
            ),
            (
                "Combinações — lista (CSV)",
                ex.csv_lista(plano, estados_exportados),
                "combinacoes_lista",
                "csv_lista",
                AJUDA["btn_csv_lista"],
            ),
            ("Ações (CSV)", pc.csv_das_acoes(plano), "acoes", "csv_acoes", AJUDA["btn_csv_acoes"]),
        ),
        strict=True,
    ):
        coluna.download_button(
            rotulo,
            data=dados,
            file_name=f"plano_de_cargas_{arquivo}_{codigo_projeto}.csv",
            mime="text/csv",
            icon=":material/download:",
            key=f"pc_{chave}",
            help=ajuda,
            width="stretch",
        )
    with st.expander("Como lançar no SolidWorks, no Robot e em outros programas"):
        st.markdown(
            "\n".join(
                f"**{t.capitalize()}**" if t.isupper() else (f"- {t}" if t else "")
                for t in ex.texto_leia_me(sistema, eixos, anglo=anglo)[3:]
            )
        )
