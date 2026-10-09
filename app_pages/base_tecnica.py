"""Base técnica do projeto: critério do cliente, vento do local, limites e a consulta do critério Anglo."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.base_tecnica_help import AJUDA
from components.base_tecnica_ui import gravar_base, mapa_do_projeto
from components.ui import cabecalho_pagina, configurar_pagina
from core import base_tecnica as bt
from core import criterio_anglo as ca
from core import vento_nbr6123 as vb
from core.project_store import obter_projeto_ativo

configurar_pagina("Base técnica do projeto", ":material/tune:")
cabecalho_pagina(
    "Base técnica do projeto",
    "Preencha uma vez: critério do cliente, vento do local, tipo de estrutura e sobrecarga. As "
    "páginas de cálculo começam com estes valores.",
    categoria="Gestão industrial",
    icone=":material/tune:",
    cor="violet",
    ajuda_modulo="Base técnica do projeto",
    acoes=(("app_pages/plano_cargas.py", "Plano de cargas", ":material/table_chart:"),),
)

mapa_do_projeto(AJUDA["sec_mapa"])

projeto = obter_projeto_ativo()
salva = bt.base_do_projeto(projeto)


def _numero(valor: float, casas: int = 2) -> str:
    return bt.numero(valor, casas)


# ============================================================ formulário
if projeto is None:
    st.info(
        "Nenhum projeto ativo. Abra ou crie um em **Projetos permanentes** para gravar a base "
        "técnica. A consulta do critério Anglo, mais abaixo, funciona sem projeto.",
        icon=":material/folder_off:",
    )
else:
    with st.container(border=True):
        st.subheader("Critério do cliente", help=AJUDA["sec_cliente"])
        cliente = st.radio(
            "Critério de projeto",
            list(bt.CLIENTES),
            index=list(bt.CLIENTES).index(salva.cliente if salva else bt.CLIENTE_ANGLO),
            format_func=lambda chave: bt.CLIENTES[chave],
            key="bt_cliente",
            horizontal=True,
            help=AJUDA["cliente"],
        )
        if cliente == bt.CLIENTE_ANGLO:
            st.caption(f":material/description: {ca.REFERENCIA}. Aplicação: {ca.APLICACAO}")
    inicial = (
        salva if (salva is not None and salva.cliente == cliente) else bt.base_do_cliente(cliente)
    )
    sufixo = f"{projeto['id']}_{cliente}"
    with st.form(f"bt_formulario_{sufixo}", border=True):
        st.subheader("Local e vento", help=AJUDA["sec_local"])
        colunas = st.columns(4)
        local = colunas[0].text_input("Local", value=inicial.local, help=AJUDA["local"])
        v0 = colunas[1].number_input(
            "V₀ (m/s)",
            min_value=10.0,
            max_value=70.0,
            value=float(inicial.vento.v0_m_s),
            step=1.0,
            help=AJUDA["v0"],
        )
        s1 = colunas[2].number_input(
            "S₁",
            min_value=0.5,
            max_value=2.0,
            value=float(inicial.vento.s1),
            step=0.05,
            format="%.2f",
            help=AJUDA["s1"],
        )
        categorias = list(vb.CATEGORIAS_RUGOSIDADE)
        categoria = colunas[3].selectbox(
            "Categoria do terreno",
            categorias,
            index=categorias.index(inicial.vento.categoria),
            help=AJUDA["categoria"],
        )
        colunas = st.columns(2)
        opcoes_s3 = list(bt.OPCOES_S3)
        grupo_s3 = colunas[0].selectbox(
            "S₃",
            opcoes_s3,
            index=opcoes_s3.index(inicial.vento.grupo_s3),
            format_func=lambda g: (
                "Valor do critério do cliente"
                if g == bt.S3_DO_CLIENTE
                else f"Grupo {g} — S₃ = {_numero(vb.GRUPOS_S3[int(g)][0])}"
            ),
            help=AJUDA["s3"],
        )
        s3_cliente = colunas[1].number_input(
            "S₃ do cliente",
            min_value=0.5,
            max_value=1.5,
            value=float(inicial.vento.s3_cliente or ca.S3),
            step=0.01,
            format="%.2f",
            help=AJUDA["s3_cliente"],
        )
        st.subheader("Estrutura e sobrecarga", help=AJUDA["sec_estrutura"])
        colunas = st.columns(3)
        tipo = colunas[0].selectbox(
            "Tipo de estrutura",
            list(bt.TIPOS_DE_ESTRUTURA),
            index=list(bt.TIPOS_DE_ESTRUTURA).index(inicial.tipo_de_estrutura),
            help=AJUDA["tipo"],
        )
        locais = [bt.SOBRECARGA_INFORMADA, *(s.local for s in ca.SOBRECARGAS)]
        sobrecarga_local = colunas[1].selectbox(
            "Sobrecarga (Anglo, Tabela 2)",
            locais,
            index=locais.index(inicial.sobrecarga_local)
            if inicial.sobrecarga_local in locais
            else 0,
            help=AJUDA["sobrecarga_local"],
        )
        sobrecarga = colunas[2].number_input(
            "Sobrecarga informada (kN/m²)",
            min_value=0.0,
            value=float(inicial.sobrecarga_kN_m2),
            step=0.5,
            help=AJUDA["sobrecarga"],
        )
        colunas = st.columns(3)
        agressividade = colunas[0].selectbox(
            "Corrosividade atmosférica",
            list(bt.CLASSES_DE_AGRESSIVIDADE),
            index=list(bt.CLASSES_DE_AGRESSIVIDADE).index(inicial.classe_de_agressividade),
            help=AJUDA["agressividade"],
        )
        vida = colunas[1].number_input(
            "Vida útil (anos)",
            min_value=0.0,
            value=float(inicial.vida_util_anos or 0.0),
            step=5.0,
            help=AJUDA["vida_util"],
        )
        observacoes = colunas[2].text_input(
            "Observações", value=inicial.observacoes, help=AJUDA["observacoes"]
        )
        salvar = st.form_submit_button(
            "Salvar a base técnica",
            type="primary",
            icon=":material/save:",
            help=AJUDA["btn_salvar"],
        )
    if salvar:
        valor_sobrecarga = (
            ca.sobrecarga(sobrecarga_local).valor_kN_m2
            if sobrecarga_local != bt.SOBRECARGA_INFORMADA
            else float(sobrecarga)
        )
        nova = bt.BaseTecnica(
            cliente=cliente,
            local=local.strip(),
            vento=bt.VentoDoLocal(
                v0_m_s=float(v0),
                s1=float(s1),
                categoria=str(categoria),
                grupo_s3=str(grupo_s3),
                s3_cliente=float(s3_cliente) if grupo_s3 == bt.S3_DO_CLIENTE else None,
            ),
            tipo_de_estrutura=str(tipo),
            sobrecarga_local=str(sobrecarga_local),
            sobrecarga_kN_m2=valor_sobrecarga,
            classe_de_agressividade=str(agressividade),
            vida_util_anos=float(vida) or None,
            observacoes=observacoes.strip(),
            atualizado_em=pd.Timestamp.now().isoformat(timespec="seconds"),
        )
        erros = bt.validar(nova)
        if erros:
            for erro in erros:
                st.error(erro, icon=":material/error:")
        elif gravar_base(nova):
            st.toast("Base técnica gravada no projeto.", icon=":material/check_circle:")
            st.rerun()

    if salva is not None:
        with st.container(border=True):
            st.subheader("O que as páginas vão usar", help=AJUDA["sec_local"])
            vento_10m = vb.calcular_vento_no_local(
                salva.vento.v0_m_s,
                s1=salva.vento.s1,
                categoria=salva.vento.categoria,
                classe="A",
                altura_m=10.0,
                s3=salva.vento.s3,
            )
            limite_1 = bt.limite_do_topo(salva, 1)
            colunas = st.columns(3)
            colunas[0].metric(
                "q a 10 m (classe A)",
                f"{_numero(vento_10m.q_N_m2 / 1e3, 3)} kN/m²",
                help=AJUDA["res_q"],
            )
            colunas[1].metric(
                "Deslocamento do topo sob vento",
                f"H/{limite_1.divisor:g}"
                + (f", máx. {limite_1.maximo_mm:g} mm" if limite_1.maximo_mm else ""),
                help=AJUDA["res_limite"],
            )
            colunas[2].metric(
                "Sobrecarga de referência",
                f"{_numero(salva.sobrecarga_kN_m2, 2)} kN/m²",
                help=AJUDA["res_sobrecarga"],
            )
            st.caption(f"{bt.texto_do_vento(salva)}. Limite: {limite_1.referencia}.")
            for aviso in bt.avisos(salva):
                st.warning(aviso, icon=":material/balance:")

# ============================================================ consulta do critério Anglo
st.header("Critério Anglo — consulta", help=AJUDA["sec_consulta"])
st.caption(ca.REFERENCIA)
abas = st.tabs(
    [
        "Sobrecargas",
        "Deslocamentos",
        "Mínimos e chumbadores",
        "Ligações",
        "Combinações",
        "Ações especiais",
        "Vibração",
        "Escadas e guarda-corpos",
        "Materiais",
        "Conflitos",
    ]
)
with abas[0]:
    st.dataframe(
        pd.DataFrame(
            [{"Local": s.local, "kN/m²": s.valor_kN_m2, "Nota": s.nota} for s in ca.SOBRECARGAS]
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption("Item 5.2, Tabela 2 — valores mínimos, quando o projeto mecânico não indicar outro.")
with abas[1]:
    linhas = [
        {"Tabela": d.tabela, "Elemento": d.descricao, "Limite": d.texto}
        for d in (*ca.DESLOCAMENTOS_VERTICAIS, *ca.DESLOCAMENTOS_HORIZONTAIS)
    ]
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    st.caption(
        "Item 7 — L: vão (ou o dobro do balanço); H: altura total da coluna; h: altura do andar. "
        "Valem também as notas da Tabela C.1 da NBR 8800; recomendações mais rigorosas dos "
        "fabricantes prevalecem."
    )
with abas[2]:
    st.dataframe(
        pd.DataFrame(
            [{"Elemento": k, "Mínimo (mm)": v} for k, v in ca.ESPESSURAS_MINIMAS_MM.items()]
            + [{"Elemento": k, "Mínimo (mm)": f"Ø {v}"} for k, v in ca.DIAMETROS_MINIMOS.items()]
        ).astype(str),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        f"Item 8.8. Chapas com {_numero(ca.CHAPA_COM_ULTRASSOM_MM, 1)} mm ou mais: 100 % ensaiadas "
        "por ultrassom (4.5, nota 1)."
    )
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Chumbador": k,
                    "Furo na placa (mm)": v[0],
                    "Furo da arruela (mm)": v[1],
                    "Espessura da arruela (mm)": v[2],
                    "Arruela (mm × mm)": f"{v[3]:g} × {v[3]:g}",
                    "Grout mín. (mm)": v[4],
                }
                for k, v in ca.CHUMBADORES.items()
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption("Item 8.7 — a arruela não é soldada na placa de base.")
with abas[3]:
    st.markdown(
        f"""
- Ligações principais (vigas, colunas, contraventamentos): **{ca.PARAFUSO_PRINCIPAL}** (9.1).
- Ligações secundárias: {ca.PARAFUSO_SECUNDARIO}.
- No mínimo **{ca.PARAFUSOS_MINIMOS_POR_LIGACAO} parafusos** por ligação; evitar diâmetro acima de **1"**;
  protensão de no mínimo **70 %** da resistência à ruptura do parafuso.
- Treliças e contraventamentos dimensionados pela esbeltez: a ligação resiste a **75 %** da tração
  da peça e a no mínimo **3 t** (29,4 kN).
- Ligações de extremidade de vigas: 75 % da carga uniforme admissível (tabelas do AISC).
- Ligações sujeitas a reversão de esforços ou em que o deslizamento é indesejável: **por atrito**.
- O torque dos parafusos deve estar no projeto; soldas pela AWS D1.1, juntas de topo com
  penetração total.
"""
    )
    st.dataframe(
        pd.DataFrame(
            [
                {"Espessura da chapa": "até 6,3 mm", "Filete mínimo (mm)": 3},
                {"Espessura da chapa": "6,3 a 12,7 mm", "Filete mínimo (mm)": 5},
                {"Espessura da chapa": "12,7 a 19,0 mm", "Filete mínimo (mm)": 6},
                {"Espessura da chapa": "acima de 19,0 mm", "Filete mínimo (mm)": 8},
            ]
        ),
        hide_index=True,
    )
    st.caption("Item 9.2.1, Tabela 6.")
with abas[4]:
    st.markdown("\n".join(f"{i}. {c}" for i, c in enumerate(ca.COMBINACOES_MINIMAS, start=1)))
    st.caption(f"Item 5.9 — {ca.LEGENDA_COMBINACOES} {ca.QUADRO_DE_CARGAS_FUNDACOES}")
with abas[5]:
    st.dataframe(
        pd.DataFrame([{"Caso": a, "Impacto mínimo": b} for a, b in ca.IMPACTOS]),
        hide_index=True,
        width="stretch",
    )
    st.caption("Item 5.3.")
    st.markdown("\n".join(f"- {t}" for t in ca.PONTE_ROLANTE))
    st.caption("Item 5.4 — pontes e pórticos rolantes.")
    st.markdown(
        f"""
- Monovias: simplesmente apoiadas; impacto de +{ca.MONOVIA_IMPACTO_CARGA:.0%} sobre a carga levantada e
  +{ca.MONOVIA_IMPACTO_PARTES_MOVEIS:.0%} sobre as partes móveis (5.5).
- Temperatura: ±{ca.TEMPERATURA_VARIACAO_C:g} °C em estruturas hiperestáticas; juntas de dilatação acima de
  {ca.JUNTA_DE_DILATACAO_M:g} m (5.8).
- Linha de vida: {ca.LINHA_DE_VIDA_kN:g} kN por ponto de ancoragem, no ponto mais desfavorável; postes de
  {ca.LINHA_DE_VIDA_ALTURA_POSTE_M:g} m acima da viga (5.10).
- Chutes, calhas e tanques: considerar entupimento com o material de maior peso específico (5.11).
""".replace("%", " %")
    )
with abas[6]:
    colunas = st.columns(3)
    ne = colunas[0].number_input(
        "Frequência da estrutura Ne (Hz)",
        min_value=0.1,
        value=20.0,
        step=0.5,
        key="bt_vib_ne",
        help=AJUDA["vib_ne"],
    )
    nm = colunas[1].number_input(
        "Frequência do equipamento Nm (Hz)",
        min_value=0.1,
        value=15.0,
        step=0.5,
        key="bt_vib_nm",
        help=AJUDA["vib_nm"],
    )
    rpm = colunas[2].number_input(
        "Rotação n (rpm)",
        min_value=1.0,
        value=900.0,
        step=10.0,
        key="bt_vib_rpm",
        help=AJUDA["vib_rpm"],
    )
    avaliacao = ca.avaliar_frequencia(ne, nm, rpm)
    colunas = st.columns(4)
    colunas[0].metric("Ne / Nm", _numero(avaliacao.razao, 3), help=AJUDA["res_vib"])
    colunas[1].metric(
        "Situação", "atende" if avaliacao.atende else "não atende", help=AJUDA["res_vib"]
    )
    colunas[2].metric(
        "Coeficiente dinâmico",
        "∞"
        if avaliacao.coeficiente_dinamico == float("inf")
        else _numero(avaliacao.coeficiente_dinamico, 2),
        help=AJUDA["res_vib"],
    )
    colunas[3].metric(
        "Amplitudes máximas (mm)",
        f"A_v {_numero(avaliacao.amplitude_vertical_max_mm, 3)} · A_h "
        f"{_numero(avaliacao.amplitude_horizontal_max_mm, 3)}",
        help=AJUDA["res_vib"],
    )
    st.caption(
        f"Faixa: {avaliacao.faixa}"
        + (" — Ne é múltiplo de Nm (o critério proíbe)." if avaliacao.multiplo else ".")
        + " Item 5.7: preferível 1,25·Nm < Ne < 1,5·Nm; se não couber, 0,575·Nm < Ne < 0,8·Nm "
        "ou Ne < 0,425·Nm."
    )
with abas[7]:
    st.markdown(
        f"""
- Espelho de {ca.ESPELHO_MIN_MM:g} a {ca.ESPELHO_MAX_MM:g} mm; passo pela fórmula de Blondel
  ({ca.BLONDEL_MIN_MM:g} ≤ 2h + b ≤ {ca.BLONDEL_MAX_MM:g}); degrau com largura mínima b + 20 mm (10.2).
- Largura mínima das escadas: {ca.LARGURA_ESCADA_GERAL_MM:g} mm em geral; {ca.LARGURA_ESCADA_PERMANENCIA_MM:g} mm
  com permanência constante de pessoas (exceto até 3.700 mm acima do piso zero).
- Guarda-corpo com no mínimo {ca.GUARDA_CORPO_ALTURA_MIN_MM:g} mm de altura e espaçamento entre barras de
  no máximo {ca.GUARDA_CORPO_ESPACAMENTO_MAX_MM:g} mm; detalhes típicos AA-BR-DPST-ES-0001 a 0004.
- Pisos: preferencialmente chapa expandida de 6,3 mm; grade fixada com clipes; grade serrilhada em
  rampas (8.6).
- Contraventamentos longitudinais em X trabalhando à tração; cantoneiras tracionadas montadas com
  redução de comprimento (Tabela 5: 2 mm de 3 a 6 m; 3 mm de 6 a 10 m; 5 mm acima) (8.2).
- Esbeltez: tração ≤ 300 (exceto barras redondas e peças com pré-tensão); compressão ≤ 200 (8.3).
"""
    )
    st.page_link(
        "app_pages/degrau_escada.py", label="Degrau de escada em grade", icon=":material/stairs:"
    )
with abas[8]:
    st.dataframe(
        pd.DataFrame([{"Uso": a, "Material": b} for a, b in ca.MATERIAIS]),
        hide_index=True,
        width="stretch",
    )
    st.caption("Item 4.5, Tabela 1. Filtragem e Porto: Tabela 7 e proteção do item 12.")
with abas[9]:
    for texto in ca.CONFLITOS:
        st.warning(texto, icon=":material/balance:")
