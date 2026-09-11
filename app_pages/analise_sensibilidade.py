"""Laboratório industrial de sensibilidade e propagação de incertezas."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from components.project_tools import (
    botao_registrar_calculo,
    construir_registro_tecnico,
    sincronizar_projeto_ativo,
)
from components.ui import cabecalho_pagina, configurar_pagina
from core.project_store import obter_projeto_ativo
from core.sensitivity import (
    DISTRIBUICOES,
    analisar_monte_carlo,
    analisar_oat,
    listar_modelos,
    obter_modelo,
    sugerir_de_registro,
)

configurar_pagina("Análise de sensibilidade", ":material/tune:")

cabecalho_pagina(
    "Análise de sensibilidade",
    "Descubra quais entradas governam o resultado e quanto a incerteza informada pode alterar a decisão de engenharia.",
    categoria="ROBUSTEZ DO PROJETO",
    icone=":material/tune:",
    cor="violet",
    ajuda_modulo="Análise de sensibilidade",
    acoes=(("app_pages/central_relatorios.py", "Memorial", ":material/description:"),),
    modulo_id="analise_sensibilidade",
)

st.info(
    "**Para que serve:** você raramente conhece uma medida com precisão "
    "absoluta — uma dimensão, uma carga, uma propriedade de material sempre "
    "tem uma margem de incerteza. Este módulo testa o que acontece com o "
    "resultado se essas entradas variarem dentro da margem que você informar, "
    "e aponta qual delas mais pesa na decisão final.",
    icon=":material/lightbulb:",
)

sincronizar_projeto_ativo()
projeto = obter_projeto_ativo()
modelos = listar_modelos()
mapa_modelos = {item.id: item for item in modelos}

with st.expander("Partir de um cálculo já registrado", expanded=False):
    registros_compativeis = []
    for registro in (projeto or {}).get("registros_tecnicos", []):
        sugestao = sugerir_de_registro(registro)
        if sugestao:
            registros_compativeis.append((registro, sugestao))
    if registros_compativeis:
        mapa_registros = {
            registro["id"]: f"{registro.get('modulo')} · {registro.get('titulo')}"
            for registro, _ in registros_compativeis
        }
        origem_id = st.selectbox("Registro de origem", list(mapa_registros), format_func=lambda valor: mapa_registros[valor])
        if st.button("Carregar entradas rastreadas", icon=":material/input:"):
            registro, sugestao = next(item for item in registros_compativeis if item[0]["id"] == origem_id)
            st.session_state["sens_modelo_id"] = sugestao["modelo_id"]
            st.session_state["sens_prefill"] = sugestao["entradas"]
            st.session_state["sens_origem_registro"] = {
                "id": registro["id"],
                "titulo": mapa_registros[origem_id],
            }
            st.success("Entradas disponíveis carregadas. Revise incertezas e critério antes de calcular.")
            st.rerun()
    else:
        st.caption("O projeto ativo ainda não possui análise estática ou de fadiga compatível com importação automática.")

if "sens_modelo_id" not in st.session_state or st.session_state["sens_modelo_id"] not in mapa_modelos:
    st.session_state["sens_modelo_id"] = "seguranca_vm"

modelo_id = st.selectbox(
    "Modelo de resposta",
    list(mapa_modelos),
    format_func=lambda valor: mapa_modelos[valor].titulo,
    key="sens_modelo_id",
)
modelo = obter_modelo(modelo_id)
st.caption(f"{modelo.descricao}  ·  **{modelo.equacao}**")

prefill = st.session_state.get("sens_prefill", {})
linhas = []
for entrada in modelo.entradas:
    valor_prefill = prefill.get(entrada.chave)
    nominal = entrada.padrao if valor_prefill is None else float(valor_prefill)
    linhas.append(
        {
            "chave": entrada.chave,
            "Variável": entrada.rotulo,
            "Nominal": nominal,
            "Unidade": entrada.unidade,
            "Incerteza (%)": 10.0,
            "Distribuição": "Uniforme",
        }
    )

with st.form(f"form_sensibilidade_{modelo_id}"):
    st.markdown("##### Entradas e incertezas")
    dados_editados = st.data_editor(
        pd.DataFrame(linhas),
        hide_index=True,
        disabled=["chave", "Variável", "Unidade"],
        width="stretch",
        column_config={
            "chave": None,
            "Variável": st.column_config.TextColumn("Variável", width="large"),
            "Nominal": st.column_config.NumberColumn("Valor nominal", format="%.6g", required=True),
            "Unidade": st.column_config.TextColumn("Unidade"),
            "Incerteza (%)": st.column_config.NumberColumn(
                "Incerteza (%)", min_value=0.0, max_value=90.0, step=0.5,
                help="Normal: 1 desvio-padrão. Uniforme/Triangular: meia largura da faixa.",
            ),
            "Distribuição": st.column_config.SelectboxColumn("Distribuição", options=list(DISTRIBUICOES), required=True),
        },
        key=f"editor_sens_{modelo_id}",
    )

    c1, c2, c3 = st.columns(3)
    variacao_oat = c1.number_input("Variação OAT (± %)", min_value=0.1, max_value=90.0, value=10.0, step=1.0)
    amostras = c2.number_input("Amostras Monte Carlo", min_value=200, max_value=50_000, value=3_000, step=500)
    semente = c3.number_input("Semente reproduzível", min_value=0, max_value=2_147_483_647, value=42, step=1)

    st.markdown("##### Critério de aceitação")
    c1, c2, c3 = st.columns([1, 1, 2])
    criterio_ativo = c1.checkbox("Avaliar não atendimento", value=True)
    operador_padrao = ">=" if modelo.melhor_quando == "maior" else "<="
    operador = c2.selectbox("Resultado deve ser", ["<=", ">="], index=1 if operador_padrao == ">=" else 0, disabled=not criterio_ativo)
    limite = c3.number_input(
        f"Limite de {modelo.saida} ({modelo.unidade_saida})",
        value=1.5 if modelo.melhor_quando == "maior" else 1.0,
        disabled=not criterio_ativo,
    )
    calcular = st.form_submit_button("Executar sensibilidade e incerteza", type="primary", icon=":material/monitoring:")

if calcular:
    try:
        entradas = {str(linha["chave"]): float(linha["Nominal"]) for _, linha in dados_editados.iterrows()}
        configuracao = {
            str(linha["chave"]): {
                "incerteza_percentual": float(linha["Incerteza (%)"]),
                "distribuicao": str(linha["Distribuição"]),
            }
            for _, linha in dados_editados.iterrows()
        }
        criterio = {"ativo": criterio_ativo, "operador": operador, "limite": float(limite)}
        oat = analisar_oat(modelo_id, entradas, variacao_percentual=float(variacao_oat))
        monte_carlo = analisar_monte_carlo(
            modelo_id,
            entradas,
            configuracao,
            amostras=int(amostras),
            semente=int(semente),
            criterio=criterio,
        )
    except ValueError as erro:
        st.error(str(erro), icon=":material/error:")
    else:
        st.session_state["sens_resultado"] = {
            "modelo_id": modelo_id,
            "entradas": entradas,
            "configuracao": configuracao,
            "criterio": criterio,
            "oat": oat,
            "monte_carlo": monte_carlo,
            "origem": st.session_state.get("sens_origem_registro"),
        }

resultado = st.session_state.get("sens_resultado")
if resultado and resultado.get("modelo_id") == modelo_id:
    oat = resultado["oat"]
    mc = resultado["monte_carlo"]
    governante = oat["ranking"][0]
    probabilidade = mc.get("probabilidade_nao_atendimento_pct")

    st.subheader("Leitura executiva")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Resultado nominal", f"{oat['saida_nominal']:.4g} {modelo.unidade_saida}")
    m2.metric("Entrada governante", governante["variavel"], f"{governante['impacto_percentual']:.1f}% de faixa")
    m3.metric("Faixa P05–P95", f"{mc['p05']:.4g} – {mc['p95']:.4g}")
    m4.metric("Risco de não atender", "Não avaliado" if probabilidade is None else f"{probabilidade:.2f}%")

    ranking_df = pd.DataFrame(oat["ranking"])
    grafico_ranking = (
        alt.Chart(ranking_df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("impacto_percentual:Q", title="Variação total da saída (% do nominal)"),
            y=alt.Y("variavel:N", sort="-x", title=None),
            color=alt.Color("direcao_critica:N", title="Piora ao", scale=alt.Scale(range=["#7C3AED", "#D97706"])),
            tooltip=[
                alt.Tooltip("variavel:N", title="Entrada"),
                alt.Tooltip("impacto_percentual:Q", title="Impacto", format=".2f"),
                alt.Tooltip("elasticidade:Q", title="Elasticidade", format=".3f"),
                alt.Tooltip("direcao_critica:N", title="Direção crítica"),
            ],
        )
        .properties(height=max(220, 42 * len(ranking_df)))
    )
    st.altair_chart(grafico_ranking, width="stretch")
    st.caption(
        "**OAT (\"uma variável por vez\")**: varia uma entrada de cada vez, mantendo as demais "
        "fixas, e mede o efeito isolado no resultado. A barra mede esse efeito. Elasticidade "
        "próxima de 4, por exemplo, indica que 1% na entrada produz aproximadamente 4% na "
        "saída ao redor do ponto nominal — quanto maior a barra, mais essa entrada merece ser "
        "medida com cuidado."
    )

    st.subheader("Curva de resposta")
    mapa_variaveis = {item["chave"]: item["variavel"] for item in oat["ranking"]}
    variavel_curva = st.selectbox("Entrada explorada", list(mapa_variaveis), format_func=lambda valor: mapa_variaveis[valor])
    curva = pd.DataFrame(oat["curvas"][variavel_curva])
    grafico_curva = (
        alt.Chart(curva)
        .mark_line(point=True, color="#6D28D9")
        .encode(
            x=alt.X("entrada:Q", title=mapa_variaveis[variavel_curva]),
            y=alt.Y("saida:Q", title=f"{modelo.saida} ({modelo.unidade_saida})", scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("entrada:Q", format=".5g"), alt.Tooltip("saida:Q", format=".5g")],
        )
        .properties(height=300)
    )
    st.altair_chart(grafico_curva, width="stretch")

    st.subheader("Propagação de incertezas")
    st.caption(
        "**Simulação de Monte Carlo**: sorteia milhares de combinações aleatórias de entradas, "
        "respeitando a incerteza e a distribuição de cada uma, e recalcula o resultado em cada "
        "sorteio. O histograma abaixo mostra a faixa provável de resultados, não só o valor "
        "nominal único."
    )
    h1, h2 = st.columns([3, 2])
    amostra_df = pd.DataFrame({"Resultado": mc["amostra_saida"]})
    histograma = (
        alt.Chart(amostra_df)
        .mark_bar(color="#0F766E", opacity=0.85)
        .encode(
            x=alt.X("Resultado:Q", bin=alt.Bin(maxbins=40), title=f"{modelo.saida} ({modelo.unidade_saida})"),
            y=alt.Y("count():Q", title="Frequência"),
            tooltip=[alt.Tooltip("count():Q", title="Amostras")],
        )
        .properties(height=280)
    )
    h1.altair_chart(histograma, width="stretch")
    correlacoes = pd.DataFrame(mc["correlacoes_spearman"])
    h2.dataframe(
        correlacoes.rename(columns={"variavel": "Entrada", "correlacao": "Correlação"})[["Entrada", "Correlação"]],
        hide_index=True,
        width="stretch",
        column_config={"Correlação": st.column_config.NumberColumn(format="%.3f")},
    )
    h2.caption(
        "**Correlação de Spearman**: de -1 a 1, mostra o quanto o resultado tende a subir ou "
        "descer junto com cada entrada nas simulações. Não prova causa e efeito isoladamente."
    )

    with st.expander("Tabela completa e premissas do resultado"):
        st.dataframe(
            ranking_df.rename(
                columns={
                    "variavel": "Entrada", "nominal": "Nominal", "saida_menos": "Saída em −Δ",
                    "saida_mais": "Saída em +Δ", "impacto_percentual": "Impacto (%)",
                    "elasticidade": "Elasticidade", "direcao_critica": "Direção crítica",
                }
            )[["Entrada", "Nominal", "Saída em −Δ", "Saída em +Δ", "Impacto (%)", "Elasticidade", "Direção crítica"]],
            hide_index=True,
            width="stretch",
        )
        st.write(f"Amostras válidas: {mc['amostras_validas']} de {mc['amostras_solicitadas']}; semente {mc['semente']}.")
        st.warning(mc["aviso"], icon=":material/warning:")

    atende_nominal = True
    if resultado["criterio"].get("ativo"):
        if resultado["criterio"]["operador"] == "<=":
            atende_nominal = oat["saida_nominal"] <= resultado["criterio"]["limite"]
        else:
            atende_nominal = oat["saida_nominal"] >= resultado["criterio"]["limite"]
    status = "Informativo"
    if probabilidade is not None:
        status = "Atende" if atende_nominal and probabilidade <= 5.0 else ("Atenção" if atende_nominal else "Não atende")
    conclusao = (
        f"{governante['variavel']} é a entrada mais influente no intervalo OAT de ±{oat['variacao_percentual']:.1f}%. "
        + ("Critério probabilístico não definido." if probabilidade is None else f"Probabilidade estimada de não atendimento = {probabilidade:.2f}%.")
    )
    registro = construir_registro_tecnico(
        modulo="Análise de sensibilidade",
        modulo_id="analise_sensibilidade",
        titulo=f"Sensibilidade — {modelo.titulo}",
        status=status,
        resumo=f"OAT e Monte Carlo aplicados ao modelo: {modelo.descricao}",
        entradas={
            **resultado["entradas"],
            "incertezas": resultado["configuracao"],
            "registro_origem": (resultado.get("origem") or {}).get("id"),
        },
        resultados={
            "saida_nominal": oat["saida_nominal"],
            "unidade_saida": modelo.unidade_saida,
            "variavel_governante": governante["variavel"],
            "impacto_governante_pct": governante["impacto_percentual"],
            "p05": mc["p05"], "p50": mc["p50"], "p95": mc["p95"],
            "probabilidade_nao_atendimento_pct": probabilidade,
            "ranking_sensibilidade": [
                {"variavel": item["variavel"], "impacto_percentual": item["impacto_percentual"], "elasticidade": item["elasticidade"], "direcao_critica": item["direcao_critica"]}
                for item in oat["ranking"]
            ],
            "correlacoes_spearman": mc["correlacoes_spearman"],
        },
        metodo="Variação uma-a-uma (OAT) e simulação de Monte Carlo com semente fixa.",
        equacoes=[modelo.equacao],
        criterios=[resultado["criterio"]] if resultado["criterio"].get("ativo") else [],
        incertezas=resultados_config if (resultados_config := resultado["configuracao"]) else {},
        premissas=[
            "As faixas e distribuições foram informadas pelo usuário.",
            "As entradas são tratadas como independentes; correlações físicas não cadastradas não são simuladas.",
            "OAT é local ao intervalo informado e não substitui exploração de modos de falha diferentes.",
        ],
        alertas=[] if status == "Atende" else [conclusao],
        referencias=["Registro de origem e base de cálculo do projeto devem ser conferidos antes da decisão."],
        conclusao=conclusao,
        responsavel=(projeto or {}).get("responsavel", ""),
    )
    botao_registrar_calculo(
        registro,
        key="registrar_sensibilidade",
        rotulo="Registrar sensibilidade no projeto ativo",
        tipo="primary",
    )

st.divider()
st.warning(
    "Sensibilidade não corrige um modelo inadequado. Verifique domínio, unidades, mecanismos físicos, correlações entre entradas e critérios normativos.",
    icon=":material/gavel:",
)
