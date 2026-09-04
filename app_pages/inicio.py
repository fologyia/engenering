import streamlit as st

from core import materials as mat
from core import steel_sections as secoes


try:
    materiais = mat.carregar_materiais()
except (FileNotFoundError, ValueError) as erro:
    st.error(f"Não foi possível carregar a base de materiais: {erro}")
    st.stop()

with st.container(border=True):
    with st.container(horizontal=True):
        st.badge(
            "Engenharia mecânica",
            icon=":material/precision_manufacturing:",
            color="primary",
        )
        st.badge(
            "Análise e pré-dimensionamento",
            icon=":material/verified:",
            color="green",
        )
    st.title("Mecânica Toolkit")
    st.markdown(
        "Organize **projetos industriais permanentes**, transforme dados em verificações "
        "rastreáveis e consolide validações e memoriais técnicos."
    )
    st.caption(
        "Foco em equipamentos, sistemas, estruturas de aço, carregamentos, tensões, "
        "fadiga, documentação e referências normativas."
    )
    with st.container(horizontal=True, horizontal_alignment="right"):
        st.page_link(
            "app_pages/gestao_projetos.py",
            label="Projetos permanentes",
            icon=":material/folder_managed:",
        )
        st.page_link(
            "app_pages/assistente_projeto.py",
            label="Projeto guiado",
            icon=":material/route:",
        )
        st.page_link(
            "app_pages/conversor_unidades.py",
            label="Converter unidades",
            icon=":material/swap_horiz:",
        )
        st.page_link(
            "app_pages/guia_geral.py",
            label="Guia geral",
            icon=":material/help:",
            help="Coleta de dados, exemplos preenchidos e interpretação.",
            query_params={"modulo": "Comece aqui"},
        )
        st.page_link(
            "app_pages/casos_carga.py",
            label="Estruturar casos de carga",
            icon=":material/arrow_forward:",
            icon_position="right",
        )

projeto_ativo = st.session_state.get("projeto_ativo")
if projeto_ativo:
    with st.container(border=True):
        st.badge(
            "Projeto ativo",
            icon=":material/folder_open:",
            color="green",
        )
        st.subheader(projeto_ativo["nome"])
        if projeto_ativo.get("descricao"):
            st.caption(projeto_ativo["descricao"])
        st.markdown(
            f"**Código:** {projeto_ativo.get('codigo', 'não definido')}  ·  "
            f"**Revisão:** {int(projeto_ativo.get('revisao', 0)):02d}  ·  "
            f"**Situação:** {projeto_ativo.get('status', 'Em elaboração')}"
        )
        st.caption(
            f"Objetivo: {projeto_ativo.get('objetivo') or 'ainda não definido'}. "
            "O banco local mantém dados, registros e revisões entre sessões."
        )
        with st.container(horizontal=True, horizontal_alignment="right"):
            st.page_link(
                "app_pages/gestao_projetos.py",
                label="Abrir projeto",
                icon=":material/edit_note:",
            )
            st.page_link(
                "app_pages/central_validacao.py",
                label="Validar",
                icon=":material/fact_check:",
            )
            st.page_link(
                "app_pages/central_relatorios.py",
                label="Gerar memorial",
                icon=":material/description:",
            )

with st.container(horizontal=True):
    st.metric(
        ":material/apps: Áreas integradas",
        13,
        border=True,
        help="Gestão, validação, relatórios, análises, estruturas, ferramentas e biblioteca normativa.",
    )
    st.metric(
        ":material/database: Materiais",
        len(materiais),
        border=True,
        help="Valores típicos de referência cadastrados.",
    )
    st.metric(
        ":material/view_in_ar: Perfis geométricos",
        len(secoes.CATALOGO_PERFIS),
        border=True,
        help="Perfis idealizados disponíveis na área de estruturas de aço.",
    )

with st.container(border=True):
    st.badge("Rota rápida", icon=":material/route:", color="blue")
    st.subheader("Por onde devo começar?")
    situacoes = [
        "Quero manter dados, cálculos e revisões de um projeto industrial",
        "Quero conferir pendências e preparar a liberação de um projeto",
        "Quero gerar um memorial consolidado em Word ou PDF",
        "Ainda não sei qual análise usar ou quero montar um roteiro",
        "Preciso converter os dados para as unidades do programa",
        "Tenho vários cenários operacionais e preciso combinar ou envelopar cargas",
        "Tenho forças, momentos, torque ou pressão e as dimensões da peça",
        "Já tenho as componentes de tensão em um ponto",
        "Minha carga varia com o tempo e quero verificar fadiga",
        "Quero dimensionar ou conferir uma junta parafusada",
        "Quero verificar uma barra, ligação, treliça ou pórtico de aço",
        "Quero localizar a norma aplicável ou pesquisar meus PDFs",
        "Quero cadastrar propriedades de material com origem confiável",
        "Quero saber quais entradas governam o resultado e avaliar incertezas",
    ]
    situacao = st.selectbox("Escolha o que você possui", situacoes)

    recomendacoes = {
        situacoes[0]: (
            "Projetos permanentes",
            "Centraliza identificação, base de projeto, escopo físico, normas, registros, checklist e revisões.",
            "app_pages/gestao_projetos.py",
            ":material/folder_managed:",
        ),
        situacoes[1]: (
            "Central de validação",
            "Separa bloqueios, atenções e pendências e permite convertê-los em ações rastreáveis.",
            "app_pages/central_validacao.py",
            ":material/fact_check:",
        ),
        situacoes[2]: (
            "Central de relatórios",
            "Seleciona seções e registros e gera Word editável e PDF a partir da mesma revisão.",
            "app_pages/central_relatorios.py",
            ":material/description:",
        ),
        situacoes[3]: (
            "Assistente de projeto",
            "Organiza objetivo, dados e checklist antes de abrir o cálculo correto.",
            "app_pages/assistente_projeto.py",
            ":material/route:",
        ),
        situacoes[4]: (
            "Conversor de unidades",
            "Converte grandezas de engenharia para as unidades indicadas nos campos.",
            "app_pages/conversor_unidades.py",
            ":material/swap_horiz:",
        ),
        situacoes[5]: (
            "Casos e combinações de carga",
            "Mantém cenários físicos, fatores explícitos e o vetor governante de cada componente.",
            "app_pages/casos_carga.py",
            ":material/layers:",
        ),
        situacoes[6]: (
            "Assistente de cargas",
            "Transforma cargas e geometria em σx, σy e τxy.",
            "app_pages/assistente_cargas.py",
            ":material/manufacturing:",
        ),
        situacoes[7]: (
            "Análise estática",
            "Verifica von Mises, tensões principais e segurança ao escoamento. "
            "Use Mohr quando precisar girar o plano ou analisar um tensor 3D.",
            "app_pages/analise_estatica.py",
            ":material/analytics:",
        ),
        situacoes[8]: (
            "Análise de fadiga",
            "Corrige o limite de resistência e avalia Goodman, Soderberg e vida S–N.",
            "app_pages/analise_fadiga.py",
            ":material/cycle:",
        ),
        situacoes[9]: (
            "Projeto de parafusos",
            "Avalia pré-carga, torque, separação, deslizamento, chapa e fadiga axial.",
            "app_pages/projeto_parafusos.py",
            ":material/build:",
        ),
        situacoes[10]: (
            "Estruturas de aço",
            "Reúne perfis, barras, combinações, ligações e análise estrutural 2D.",
            "app_pages/estruturas_aco.py",
            ":material/domain:",
        ),
        situacoes[11]: (
            "Normas técnicas",
            "Organiza referências por segmento e pesquisa seus PDFs por arquivo e página.",
            "app_pages/normas_tecnicas.py",
            ":material/library_books:",
        ),
        situacoes[12]: (
            "Materiais técnicos",
            "Separa referência preliminar de propriedade rastreada a certificado, norma, fabricante ou ensaio.",
            "app_pages/materiais_tecnicos.py",
            ":material/science:",
        ),
        situacoes[13]: (
            "Análise de sensibilidade",
            "Ordena entradas por influência e propaga as incertezas declaradas com OAT e Monte Carlo.",
            "app_pages/analise_sensibilidade.py",
            ":material/tune:",
        ),
    }
    titulo, descricao, destino, icone = recomendacoes[situacao]
    st.info(f"**Recomendação: {titulo}.** {descricao}", icon=icone)
    st.page_link(
        destino,
        label=f"Abrir {titulo.lower()}",
        icon=":material/arrow_forward:",
        icon_position="right",
        width="stretch",
    )

st.subheader("Explore as ferramentas")
st.caption("Cada módulo mostra suas hipóteses, unidades e critérios de leitura.")

modulos = [
    (
        "Projetos permanentes",
        ":material/folder_managed:",
        "Sistema industrial",
        "Mantém base de projeto, escopo, normas, registros, checklist e revisões no banco local.",
        "app_pages/gestao_projetos.py",
        "blue",
    ),
    (
        "Casos e combinações de carga",
        ":material/layers:",
        "Cenários e envelopes",
        "Registra condições operacionais, fatores explícitos e cenários governantes sem misturar máximos independentes.",
        "app_pages/casos_carga.py",
        "blue",
    ),
    (
        "Central de validação",
        ":material/fact_check:",
        "Controle de pendências",
        "Consolida bloqueios, lacunas documentais e resultados técnicos para tratamento.",
        "app_pages/central_validacao.py",
        "orange",
    ),
    (
        "Central de relatórios",
        ":material/description:",
        "Word e PDF modulares",
        "Monta um memorial unificado com capítulos ordenados, materiais, sensibilidade e snapshot reproduzível.",
        "app_pages/central_relatorios.py",
        "green",
    ),
    (
        "Materiais técnicos",
        ":material/science:",
        "Proveniência e confiança",
        "Qualifica condição, produto, propriedades, fonte, lote e aplicabilidade por projeto.",
        "app_pages/materiais_tecnicos.py",
        "green",
    ),
    (
        "Assistente de projeto",
        ":material/route:",
        "Roteiro em quatro etapas",
        "Organiza objetivo, dados, checklist e encaminha ao primeiro cálculo.",
        "app_pages/assistente_projeto.py",
        "violet",
    ),
    (
        "Conversor de unidades",
        ":material/swap_horiz:",
        "SI e sistema inglês",
        "Converte 15 grandezas e mostra equivalências para conferência.",
        "app_pages/conversor_unidades.py",
        "blue",
    ),
    (
        "Assistente de cargas",
        ":material/manufacturing:",
        "Cargas e dimensões",
        "Converte forças, momentos, torque e pressão em componentes de tensão.",
        "app_pages/assistente_cargas.py",
        "violet",
    ),
    (
        "Análise estática",
        ":material/analytics:",
        "Tensões conhecidas",
        "Calcula von Mises, tensões principais, utilização e segurança.",
        "app_pages/analise_estatica.py",
        "blue",
    ),
    (
        "Círculo de Mohr",
        ":material/donut_large:",
        "Transformações 2D e 3D",
        "Encontra planos principais, cisalhamento máximo e tração em um plano.",
        "app_pages/circulo_mohr.py",
        "blue",
    ),
    (
        "Análise de fadiga",
        ":material/cycle:",
        "Carregamento variável",
        "Aplica Marin, Goodman, Soderberg e estima a vida pela curva S–N.",
        "app_pages/analise_fadiga.py",
        "green",
    ),
    (
        "Análise de sensibilidade",
        ":material/tune:",
        "Robustez e incerteza",
        "Classifica entradas por influência e estima a chance de cruzar o critério informado.",
        "app_pages/analise_sensibilidade.py",
        "violet",
    ),
    (
        "Projeto de parafusos",
        ":material/build:",
        "Juntas mecânicas",
        "Verifica aperto, distribuição de carga, separação, atrito e chapa.",
        "app_pages/projeto_parafusos.py",
        "orange",
    ),
    (
        "Estruturas de aço",
        ":material/domain:",
        "Barras e estruturas",
        "Integra perfis, combinações, ligações, treliças e pórticos 2D.",
        "app_pages/estruturas_aco.py",
        "violet",
    ),
    (
        "Normas técnicas",
        ":material/library_books:",
        "Referências e PDFs locais",
        "Separa normas por segmento, indexa PDFs e rastreia resultados por página.",
        "app_pages/normas_tecnicas.py",
        "green",
    ),
]

for inicio_linha in range(0, len(modulos), 3):
    colunas = st.columns(3)
    for coluna, dados_modulo in zip(colunas, modulos[inicio_linha : inicio_linha + 3]):
        titulo_modulo, icone, etiqueta, descricao, pagina, cor = dados_modulo
        with coluna:
            with st.container(border=True, height=215):
                st.badge(etiqueta, color=cor)
                st.subheader(f"{icone} {titulo_modulo}")
                st.caption(descricao)
                st.page_link(
                    pagina,
                    label="Abrir módulo",
                    icon=":material/arrow_forward:",
                    icon_position="right",
                )

fluxo, limites = st.columns(2)
with fluxo:
    with st.container(border=True, height="stretch"):
        st.badge("Método", icon=":material/checklist:", color="green")
        st.subheader("Fluxo recomendado")
        st.markdown(
            """
            1. Faça o diagrama de corpo livre.
            2. Escolha a seção e o ponto crítico.
            3. Confira unidades e sinais.
            4. Compare demanda com resistência.
            5. Revise hipóteses e norma aplicável.
            """
        )
with limites:
    with st.container(border=True, height="stretch"):
        st.badge("Leitura", icon=":material/query_stats:", color="blue")
        st.subheader("Como ler os diagnósticos")
        st.markdown(
            """
            - **Utilização ≤ 1:** capacidade calculada não excedida.
            - **Fator ≥ meta:** margem definida foi alcançada.
            - **Aviso:** hipótese ou margem precisa de revisão.
            - **Erro:** entrada incompatível ou capacidade excedida.
            """
        )

st.warning(
    "Ferramenta de análise e pré-dimensionamento. Projetos reais exigem cargas "
    "completas, propriedades certificadas, normas aplicáveis e revisão de "
    "profissional habilitado.",
    icon=":material/engineering:",
)
