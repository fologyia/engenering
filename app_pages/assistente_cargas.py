import pandas as pd
import streamlit as st

from components.assistente_cargas_ui import caso_aberto, painel, tela_do_caso
from components.ui import cabecalho_pagina, configurar_pagina

configurar_pagina("Cálculo de peças", ":material/manufacturing:")

cabecalho_pagina(
    "Cálculo de peças",
    "Parafusos, roscas, vigas, barras, perfis e elementos de máquinas: as forças que chegam em "
    "cada peça e se ela aguenta.",
    categoria="Preparação de dados",
    icone=":material/manufacturing:",
    cor="violet",
    ajuda_modulo="Cálculo de peças",
    acoes=(("app_pages/circulo_mohr.py", "Círculo de Mohr", ":material/donut_large:"),),
    modulo_id="assistente_cargas",
)
envelope_referencia = st.session_state.get("cargas_envelope_projeto")
if envelope_referencia and envelope_referencia.get("componentes"):
    with st.expander(
        f"Consultar o envelope de {envelope_referencia.get('projeto_nome') or 'Casos de carga'}",
        expanded=False,
        icon=":material/layers:",
    ):
        st.caption(
            "Valores governantes calculados em **Casos e combinações de carga**. Escolha abaixo "
            "qual eixo corresponde ao esforço do caso selecionado: o programa não faz essa "
            "correspondência sozinho, pois depende de qual eixo local da peça cada resultante "
            "representa."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Componente": dados["rotulo"],
                        "Valor governante": dados["valor_governante"],
                        "Unidade": dados["unidade"],
                        "Cenário governante": dados["cenario_governante"],
                    }
                    for dados in envelope_referencia["componentes"].values()
                ]
            ),
            hide_index=True,
            width="stretch",
            column_config={
                "Valor governante": st.column_config.NumberColumn(format="%.4g"),
            },
        )
        st.page_link(
            "app_pages/casos_carga.py",
            label="Reabrir Casos e combinações de carga",
            icon=":material/arrow_back:",
        )

caso = caso_aberto()
if caso is None:
    painel()
else:
    tela_do_caso(caso)

st.caption(
    "Modelos de pré-dimensionamento e de verificação de resistência dos materiais. Para o projeto "
    "final, confirme as hipóteses, as propriedades do material e a norma aplicável."
)
