import streamlit as st

from core.atualizacao_de_codigo import renovar_modulos_desatualizados

# O Streamlit Cloud atualiza os arquivos num push sem reiniciar o processo: antes de importar os
# módulos do programa, descarta os que ficaram velhos na memória (core/atualizacao_de_codigo.py).
renovar_modulos_desatualizados()

from components.acesso_ui import acesso_na_lateral, exigir_acesso
from components.armazenamento_ui import preparar_armazenamento, situacao_na_lateral
from components.project_tools import sincronizar_projeto_ativo
from components.robustez import executar_pagina, iniciar_execucao, secao_protegida
from core import navegacao as nv

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
# Falhas inesperadas não aparecem na tela: viram um aviso discreto no fim da página, com uma
# referência, e o detalhe vai para o arquivo de diagnóstico (components/robustez.py).
iniciar_execucao()

# Com a senha de acesso definida (core/acesso.py), nada abaixo roda antes de ela ser digitada.
exigir_acesso()
st.session_state.setdefault("projeto_assistente_etapa", 1)
# Antes de qualquer leitura do banco: segredos do espelho no GitHub e restauração do que o disco
# da hospedagem perdeu num reinício.
with secao_protegida("armazenamento"):
    preparar_armazenamento()
with secao_protegida("projeto ativo"):
    sincronizar_projeto_ativo()


# O menu inteiro vem de core/navegacao.py (a Visão geral e o selo de cada página leem de lá).
paginas_por_caminho: dict[str, st.Page] = {}


def _pagina(item: nv.ItemMenu, *, inicial: bool = False) -> st.Page:
    pagina = st.Page(item.pagina, title=item.titulo, icon=item.icone, default=inicial)
    paginas_por_caminho[item.pagina] = pagina
    return pagina


menu: dict[str, list[st.Page]] = {"": [_pagina(nv.VISAO_GERAL, inicial=True)]}
for grupo in nv.MENU:
    menu[grupo.nome] = [_pagina(item) for item in grupo.itens]
pagina = st.navigation(menu, position="sidebar", expanded=True)
st.session_state["_pagina_atual"] = next(
    (caminho for caminho, p in paginas_por_caminho.items() if p is pagina), ""
)

with secao_protegida("lateral"):
    situacao_na_lateral()
    acesso_na_lateral()
executar_pagina(pagina)

with st.sidebar:
    st.caption("Projetos industriais • análise • rastreabilidade")
