import streamlit as st

from components.project_tools import sincronizar_projeto_ativo
from core.technical_modules import listar_modulos, obter_modulo

st.set_page_config(
    page_title="Mecânica Toolkit",
    page_icon=":material/precision_manufacturing:",
    layout="wide",
)
st.logo(
    "assets/logo.svg",
    size="large",
    icon_image="assets/logo_mark.svg",
)

st.session_state.setdefault("projeto_assistente_etapa", 1)
sincronizar_projeto_ativo()


def pagina_modulo(modulo_id: str) -> st.Page:
    modulo = obter_modulo(modulo_id)
    return st.Page(
        modulo.pagina,
        title=modulo.titulo,
        icon=modulo.icone,
    )


paginas_analises = [
    st.Page(item.pagina, title=item.titulo, icon=item.icone)
    for item in listar_modulos(grupo="Análises técnicas")
]
paginas_dimensionamento = [
    st.Page(item.pagina, title=item.titulo, icon=item.icone)
    for item in listar_modulos(grupo="Dimensionamento complementar")
]

pagina = st.navigation(
    {
        "": [
            st.Page(
                "app_pages/inicio.py",
                title="Visão geral",
                icon=":material/home:",
                default=True,
            ),
        ],
        "Gestão industrial": [
            st.Page(
                "app_pages/painel_industrial.py",
                title="Painel industrial",
                icon=":material/dashboard:",
            ),
            st.Page(
                "app_pages/gestao_projetos.py",
                title="Projetos permanentes",
                icon=":material/folder_managed:",
            ),
            pagina_modulo("casos_carga"),
            st.Page(
                "app_pages/central_validacao.py",
                title="Central de validação",
                icon=":material/fact_check:",
            ),
            st.Page(
                "app_pages/central_relatorios.py",
                title="Central de relatórios",
                icon=":material/description:",
            ),
        ],
        "Análises técnicas": paginas_analises,
        "Dimensionamento complementar": paginas_dimensionamento,
        "Ferramentas": [
            st.Page(
                "app_pages/assistente_projeto.py",
                title="Assistente de projeto",
                icon=":material/route:",
            ),
            st.Page(
                "app_pages/conversor_unidades.py",
                title="Conversor de unidades",
                icon=":material/swap_horiz:",
            ),
        ],
        "Referências": [
            st.Page(
                "app_pages/materiais_tecnicos.py",
                title="Materiais técnicos",
                icon=":material/science:",
            ),
            st.Page(
                "app_pages/catalogo_materiais.py",
                title="Catálogo de materiais",
                icon=":material/science:",
            ),
            st.Page(
                "app_pages/catalogo_perfis.py",
                title="Catálogo de perfis",
                icon=":material/view_in_ar:",
            ),
            st.Page(
                "app_pages/normas_tecnicas.py",
                title="Normas técnicas",
                icon=":material/library_books:",
            ),
        ],
        "Ajuda": [
            st.Page(
                "app_pages/guia_geral.py",
                title="Guia geral",
                icon=":material/help:",
            ),
        ],
    },
    position="sidebar",
    expanded=True,
)

pagina.run()

with st.sidebar:
    st.caption("Projetos industriais • análise • rastreabilidade")
