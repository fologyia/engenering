"""O menu do programa num lugar só: grupos na ordem do trabalho, páginas na ordem de uso.

A barra lateral (``app.py``), a Visão geral (``app_pages/inicio.py``) e o selo de grupo no topo de
cada página (:func:`components.ui.cabecalho_pagina`) leem daqui, então os três dizem sempre a mesma
coisa. A ordem dos grupos segue o roteiro do projeto (:mod:`core.roteiro`): preparar o projeto,
levantar as cargas, ler o modelo do SolidWorks, verificar barras, ligações e escadas e entregar o
memorial; as ferramentas de mecânica de máquinas e as referências ficam por último.

Sem Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ItemMenu:
    pagina: str  # app_pages/...
    titulo: str
    icone: str
    tarefa: str  # o que a pessoa quer fazer, na voz dela (rota rápida da Visão geral)


@dataclass(frozen=True)
class GrupoMenu:
    nome: str
    icone: str
    descricao: str
    itens: tuple[ItemMenu, ...]


VISAO_GERAL = ItemMenu(
    "app_pages/inicio.py", "Visão geral", ":material/home:", "Ver tudo o que o programa faz"
)

MENU: tuple[GrupoMenu, ...] = (
    GrupoMenu(
        "Projeto",
        ":material/folder_open:",
        "Escolher o projeto, seguir o roteiro e definir a base técnica (normas, aço, critério).",
        (
            ItemMenu(
                "app_pages/roteiro_projeto.py",
                "Roteiro do projeto",
                ":material/format_list_numbered:",
                "Saber o próximo passo do projeto, do modelo ao memorial",
            ),
            ItemMenu(
                "app_pages/gestao_projetos.py",
                "Projetos permanentes",
                ":material/folder_managed:",
                "Criar, abrir ou revisar um projeto e os cálculos registrados nele",
            ),
            ItemMenu(
                "app_pages/painel_industrial.py",
                "Painel industrial",
                ":material/dashboard:",
                "Ver a carteira: o que está travado, vencido ou desatualizado",
            ),
            ItemMenu(
                "app_pages/base_tecnica.py",
                "Base técnica do projeto",
                ":material/tune:",
                "Definir normas, aço, sobrecarga e critério Anglo do projeto",
            ),
        ),
    ),
    GrupoMenu(
        "Cargas e vento",
        ":material/weight:",
        "Levantar as ações, calcular o vento e montar o plano de cargas e as combinações.",
        (
            ItemMenu(
                "app_pages/cargas_esqueleto.py",
                "Cargas do esqueleto",
                ":material/grid_view:",
                "Gerar piso, sobrecarga, guarda-corpo e equipamentos nas barras do esqueleto",
            ),
            ItemMenu(
                "app_pages/vento_estrutura_aberta.py",
                "Vento em estruturas abertas",
                ":material/air:",
                "Calcular o vento de plataforma, mezanino ou pipe rack sem fechamento",
            ),
            ItemMenu(
                "app_pages/vento_nbr6123.py",
                "Vento nas estruturas",
                ":material/storm:",
                "Calcular o vento de edificação fechada ou galpão (NBR 6123)",
            ),
            ItemMenu(
                "app_pages/plano_cargas.py",
                "Plano de cargas",
                ":material/table_chart:",
                "Reunir as ações no plano de cargas e exportar para o SolidWorks",
            ),
            ItemMenu(
                "app_pages/casos_carga.py",
                "Casos e combinações de carga",
                ":material/stacks:",
                "Combinar ou envelopar cenários de carga",
            ),
            ItemMenu(
                "app_pages/assistente_cargas.py",
                "Assistente de cargas",
                ":material/calculate:",
                "Transformar dados de operação em cargas de projeto",
            ),
        ),
    ),
    GrupoMenu(
        "Modelo SolidWorks",
        ":material/view_in_ar:",
        "Ler os esforços do modelo e verificar todas as barras, fundações e placas de base; "
        "lista de material.",
        (
            ItemMenu(
                "app_pages/esforcos_modelo.py",
                "Esforços do modelo",
                ":material/upload_file:",
                "Importar o SolidWorks e verificar barras, fundações e placas de base",
            ),
            ItemMenu(
                "app_pages/lista_de_material.py",
                "Lista de material",
                ":material/inventory_2:",
                "Gerar a lista de material e a lista de corte do modelo",
            ),
            ItemMenu(
                "app_pages/modelo_3d.py",
                "Modelo em 3D",
                ":material/deployed_code:",
                "Ver o modelo em 3D com o perfil real, as cargas, as reações e os resultados",
            ),
        ),
    ),
    GrupoMenu(
        "Barras e vigas",
        ":material/view_week:",
        "Dimensionar uma barra isolada: viga de piso, coluna, contraventamento ou outra peça.",
        (
            ItemMenu(
                "app_pages/viga_de_piso.py",
                "Vigas de piso",
                ":material/view_week:",
                "Dimensionar a viga que apoia o piso da plataforma",
            ),
            ItemMenu(
                "app_pages/flambagem_colunas.py",
                "Flambagem de colunas",
                ":material/vertical_align_center:",
                "Verificar coluna ou barra com compressão, flexão e esforços combinados",
            ),
            ItemMenu(
                "app_pages/contraventamento_estrutura.py",
                "Contraventamento de estruturas abertas",
                ":material/grid_on:",
                "Dimensionar o contraventamento de uma estrutura aberta",
            ),
            ItemMenu(
                "app_pages/estruturas_aco.py",
                "Estruturas de aço",
                ":material/domain:",
                "Verificar barra, treliça ou pórtico de aço com várias normas",
            ),
        ),
    ),
    GrupoMenu(
        "Ligações e bases",
        ":material/link:",
        "Ligações viga–viga e viga–pilar, perfis formados a frio, soldas, parafusos e "
        "contraventamento (placas de base: em Esforços do modelo).",
        (
            ItemMenu(
                "app_pages/ligacoes_estruturais.py",
                "Ligações estruturais",
                ":material/link:",
                "Verificar ligação de viga, de perfil formado a frio ou uma solda",
            ),
            ItemMenu(
                "app_pages/projeto_parafusos.py",
                "Projeto de parafusos",
                ":material/build:",
                "Dimensionar ou conferir uma junta parafusada",
            ),
            ItemMenu(
                "app_pages/ligacao_contraventamento.py",
                "Ligação de contraventamento",
                ":material/hub:",
                "Dimensionar a ligação de contraventamento (chapa de nó, UFM)",
            ),
        ),
    ),
    GrupoMenu(
        "Escadas",
        ":material/stairs:",
        "Degraus em grade, lances, patamares, esquemático e longarinas com diagramas.",
        (
            ItemMenu(
                "app_pages/degrau_escada.py",
                "Degrau de escada em grade",
                ":material/stairs:",
                "Calcular o degrau de escada, os lances, os patamares e a longarina",
            ),
        ),
    ),
    GrupoMenu(
        "Entrega",
        ":material/description:",
        "Conferir as pendências do projeto e gerar o memorial em Word ou PDF.",
        (
            ItemMenu(
                "app_pages/central_validacao.py",
                "Central de validação",
                ":material/fact_check:",
                "Conferir pendências e preparar a liberação do projeto",
            ),
            ItemMenu(
                "app_pages/central_relatorios.py",
                "Central de relatórios",
                ":material/description:",
                "Gerar o memorial de cálculo em Word ou PDF",
            ),
        ),
    ),
    GrupoMenu(
        "Mecânica geral",
        ":material/precision_manufacturing:",
        "Ferramentas de mecânica de máquinas: tensões, eixos, fadiga, Mohr e sensibilidade.",
        (
            ItemMenu(
                "app_pages/analise_estatica.py",
                "Análise estática",
                ":material/functions:",
                "Calcular tensões numa peça com força, momento, torque ou pressão",
            ),
            ItemMenu(
                "app_pages/vigas_eixos.py",
                "Vigas e eixos",
                ":material/linear_scale:",
                "Calcular reações, diagramas e flecha de viga ou eixo",
            ),
            ItemMenu(
                "app_pages/analise_fadiga.py",
                "Análise de fadiga",
                ":material/timeline:",
                "Verificar fadiga de carga que varia com o tempo",
            ),
            ItemMenu(
                "app_pages/circulo_mohr.py",
                "Círculo de Mohr",
                ":material/radio_button_unchecked:",
                "Achar tensões principais a partir das componentes num ponto",
            ),
            ItemMenu(
                "app_pages/analise_sensibilidade.py",
                "Análise de sensibilidade",
                ":material/tune:",
                "Ver quais dados mais mexem no resultado",
            ),
        ),
    ),
    GrupoMenu(
        "Referências e ajuda",
        ":material/menu_book:",
        "Guia, normas, catálogos de perfis e materiais, conversor e assistente.",
        (
            ItemMenu(
                "app_pages/guia_geral.py",
                "Guia geral",
                ":material/help:",
                "Aprender a usar cada página, com exemplos",
            ),
            ItemMenu(
                "app_pages/normas_tecnicas.py",
                "Normas técnicas",
                ":material/library_books:",
                "Localizar a norma aplicável ou pesquisar os PDFs",
            ),
            ItemMenu(
                "app_pages/catalogo_perfis.py",
                "Catálogo de perfis",
                ":material/view_in_ar:",
                "Consultar ou cadastrar perfis",
            ),
            ItemMenu(
                "app_pages/catalogo_materiais.py",
                "Catálogo de materiais",
                ":material/inventory:",
                "Consultar aços e materiais com propriedades",
            ),
            ItemMenu(
                "app_pages/materiais_tecnicos.py",
                "Materiais técnicos",
                ":material/science:",
                "Cadastrar propriedades de material com origem confiável",
            ),
            ItemMenu(
                "app_pages/conversor_unidades.py",
                "Conversor de unidades",
                ":material/swap_horiz:",
                "Converter dados para as unidades do programa",
            ),
            ItemMenu(
                "app_pages/assistente_projeto.py",
                "Assistente de projeto",
                ":material/route:",
                "Montar um roteiro quando ainda não sei qual análise usar",
            ),
        ),
    ),
)


def todos_os_itens() -> list[ItemMenu]:
    return [VISAO_GERAL, *(item for grupo in MENU for item in grupo.itens)]


def grupo_da_pagina(pagina: str) -> GrupoMenu | None:
    """O grupo do menu de uma página (pelo caminho ``app_pages/...`` ou pelo nome do arquivo)."""
    nome = pagina.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".py")
    for grupo in MENU:
        for item in grupo.itens:
            if item.pagina.rsplit("/", 1)[-1].removesuffix(".py") == nome:
                return grupo
    return None
