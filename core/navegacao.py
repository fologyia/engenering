"""O menu do programa num lugar só: grupos na ordem do trabalho, páginas na ordem de uso.

A barra lateral (:mod:`components.menu_lateral`), a Visão geral (``app_pages/inicio.py``) e o selo
de grupo no topo de cada página (:func:`components.ui.cabecalho_pagina`) leem daqui, então os três
dizem sempre a mesma coisa. A ordem dos grupos segue o roteiro do projeto (:mod:`core.roteiro`):
preparar o projeto, levantar as cargas, ler o modelo do SolidWorks, verificar barras, escadas e
ligações e entregar o memorial; os cálculos de máquinas, as seções e as referências ficam por último.

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
    secao: str = ""  # o submenu dentro do grupo; vazio = direto no grupo
    outros_nomes: tuple[str, ...] = ()  # nomes antigos e apelidos: a busca acha por eles também


@dataclass(frozen=True)
class GrupoMenu:
    nome: str
    icone: str
    descricao: str
    itens: tuple[ItemMenu, ...]

    def secoes(self) -> list[tuple[str, list[ItemMenu]]]:
        """Os submenus na ordem em que aparecem; itens sem seção ficam num bloco de nome vazio."""
        saida: list[tuple[str, list[ItemMenu]]] = []
        for item in self.itens:
            if not saida or saida[-1][0] != item.secao:
                saida.append((item.secao, []))
            saida[-1][1].append(item)
        return saida


VISAO_GERAL = ItemMenu(
    "app_pages/inicio.py", "Visão geral", ":material/home:", "Ver tudo o que o programa faz"
)

BARRAS = "Barras e vigas"
LIGACOES = "Ligações e bases"
PECAS = "Peças de máquinas"
TENSOES = "Tensões e fadiga"
FLUIDOS = "Fluidos"

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
                "Projetos",
                ":material/folder_managed:",
                "Criar, abrir ou revisar um projeto e os cálculos registrados nele",
                outros_nomes=("Projetos permanentes", "Gestão de projetos industriais"),
            ),
            ItemMenu(
                "app_pages/painel_industrial.py",
                "Painel dos projetos",
                ":material/dashboard:",
                "Ver a carteira: o que está travado, vencido ou desatualizado",
                outros_nomes=("Painel industrial",),
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
                "Vento em edificações",
                ":material/storm:",
                "Calcular o vento de edificação fechada ou galpão (NBR 6123)",
                outros_nomes=("Vento nas estruturas",),
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
        ),
    ),
    GrupoMenu(
        "Modelo SolidWorks",
        ":material/view_in_ar:",
        "Ler os esforços do modelo e verificar barras, pilares, fundações e placas de base; "
        "reações para o projeto civil, sensores, modelo em 3D e lista de material.",
        (
            ItemMenu(
                "app_pages/esforcos_modelo.py",
                "Esforços do modelo",
                ":material/upload_file:",
                "Importar o SolidWorks e verificar barras, fundações e placas de base",
            ),
            ItemMenu(
                "app_pages/colunas_do_modelo.py",
                "Pilares do modelo",
                ":material/view_column:",
                "Verificar todos os pilares com os travamentos lidos do esqueleto, em x e em y",
                outros_nomes=("Colunas do modelo",),
            ),
            ItemMenu(
                "app_pages/reacoes_nas_bases.py",
                "Reações nas bases",
                ":material/foundation:",
                "Mandar ao engenheiro civil as forças e momentos de cada pé, caso a caso (Excel)",
            ),
            ItemMenu(
                "app_pages/sensores_do_modelo.py",
                "Sensores do modelo",
                ":material/sensors:",
                "Levar ao memorial a tensão, o deslocamento e o FS dos sensores do SolidWorks",
            ),
            ItemMenu(
                "app_pages/modelo_3d.py",
                "Modelo em 3D",
                ":material/deployed_code:",
                "Ver o modelo em 3D com o perfil real, as cargas, as reações e os resultados",
            ),
            ItemMenu(
                "app_pages/lista_de_material.py",
                "Lista de material",
                ":material/inventory_2:",
                "Gerar a lista de material e a lista de corte do modelo",
            ),
        ),
    ),
    GrupoMenu(
        "Estrutura metálica",
        ":material/domain:",
        "Uma peça de cada vez: vigas, colunas, contraventamento, escada, treliças e pórticos; "
        "ligações, parafusos e placas de base pela NBR 8800:2025.",
        (
            ItemMenu(
                "app_pages/viga_de_piso.py",
                "Vigas de piso",
                ":material/view_week:",
                "Dimensionar a viga que apoia o piso da plataforma, com a vibração do piso",
                secao=BARRAS,
            ),
            ItemMenu(
                "app_pages/flambagem_colunas.py",
                "Flambagem de colunas",
                ":material/vertical_align_center:",
                "Verificar coluna ou barra com compressão, flexão e esforços combinados",
                secao=BARRAS,
            ),
            ItemMenu(
                "app_pages/contraventamento_estrutura.py",
                "Contraventamento",
                ":material/grid_on:",
                "Dimensionar o contraventamento de uma estrutura aberta",
                secao=BARRAS,
                outros_nomes=("Contraventamento de estruturas abertas",),
            ),
            ItemMenu(
                "app_pages/degrau_escada.py",
                "Escada em grade",
                ":material/stairs:",
                "Calcular o degrau de escada, os lances, os patamares e a longarina",
                secao=BARRAS,
                outros_nomes=("Degrau de escada em grade",),
            ),
            ItemMenu(
                "app_pages/escada_marinheiro.py",
                "Escada marinheiro",
                ":material/stairs:",
                "Conferir a escada fixa vertical e a gaiola pela NR-12 e dimensionar degrau e montante",
                secao=BARRAS,
                outros_nomes=("Escada vertical", "Escada tipo marinheiro"),
            ),
            ItemMenu(
                "app_pages/estruturas_aco.py",
                "Barras, treliças e pórticos",
                ":material/architecture:",
                "Verificar barra, treliça ou pórtico de aço com várias normas",
                secao=BARRAS,
                outros_nomes=("Estruturas de aço",),
            ),
            ItemMenu(
                "app_pages/ligacoes_estruturais.py",
                "Ligações estruturais",
                ":material/link:",
                "Verificar ligação de viga, de perfil formado a frio ou uma solda",
                secao=LIGACOES,
            ),
            ItemMenu(
                "app_pages/projeto_parafusos.py",
                "Projeto de parafusos",
                ":material/build:",
                "Dimensionar ou conferir uma junta parafusada",
                secao=LIGACOES,
                outros_nomes=("Juntas parafusadas",),
            ),
            ItemMenu(
                "app_pages/ligacao_contraventamento.py",
                "Ligação de contraventamento",
                ":material/hub:",
                "Dimensionar a ligação de contraventamento (chapa de nó, UFM)",
                secao=LIGACOES,
            ),
            ItemMenu(
                "app_pages/placa_de_base.py",
                "Placas de base",
                ":material/anchor:",
                "Dimensionar a placa de base e os chumbadores de um pilar",
                secao=LIGACOES,
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
                "Validação do projeto",
                ":material/fact_check:",
                "Conferir pendências e preparar a liberação do projeto",
                outros_nomes=("Central de validação",),
            ),
            ItemMenu(
                "app_pages/central_relatorios.py",
                "Memorial de cálculo",
                ":material/description:",
                "Gerar o memorial de cálculo em Word ou PDF",
                outros_nomes=("Central de relatórios", "Relatórios"),
            ),
        ),
    ),
    GrupoMenu(
        "Mecânica",
        ":material/precision_manufacturing:",
        "Peças de máquinas (parafusos, molas, eixos, engrenagens, ajustes), tensões e fadiga, "
        "tubulação e redes de fluidos.",
        (
            ItemMenu(
                "app_pages/assistente_cargas.py",
                "Cálculo de peças",
                ":material/calculate:",
                "Parafusos, roscas, molas, eixos, engrenagens, vigas e outras peças, caso a caso",
                secao=PECAS,
                outros_nomes=("Assistente de cargas", "Elementos de máquinas"),
            ),
            ItemMenu(
                "app_pages/montador_formulas.py",
                "Montador de fórmulas",
                ":material/function:",
                "Ligar seção, esforços e critério e isolar a medida, a carga ou o material",
                secao=PECAS,
            ),
            ItemMenu(
                "app_pages/vigas_eixos.py",
                "Vigas e eixos",
                ":material/linear_scale:",
                "Calcular reações, diagramas e flecha de viga ou eixo",
                secao=PECAS,
            ),
            ItemMenu(
                "app_pages/ajustes_e_tolerancias.py",
                "Ajustes e tolerâncias",
                ":material/settings_input_component:",
                "Furo e eixo pela NBR 6158, aperto do ajuste prensado e cadeia de cotas",
                secao=PECAS,
            ),
            ItemMenu(
                "app_pages/analise_estatica.py",
                "Análise estática",
                ":material/functions:",
                "Calcular tensões numa peça com força, momento, torque ou pressão",
                secao=TENSOES,
            ),
            ItemMenu(
                "app_pages/circulo_mohr.py",
                "Círculo de Mohr",
                ":material/radio_button_unchecked:",
                "Achar tensões principais a partir das componentes num ponto",
                secao=TENSOES,
            ),
            ItemMenu(
                "app_pages/analise_fadiga.py",
                "Análise de fadiga",
                ":material/timeline:",
                "Verificar fadiga de carga que varia com o tempo",
                secao=TENSOES,
            ),
            ItemMenu(
                "app_pages/analise_sensibilidade.py",
                "Análise de sensibilidade",
                ":material/query_stats:",
                "Ver quais dados mais mexem no resultado",
                secao=TENSOES,
            ),
            ItemMenu(
                "app_pages/montador_fluidos.py",
                "Montador de fluidos",
                ":material/water_drop:",
                "Ligar fluido, tubo e verificação e isolar a vazão, o diâmetro ou a potência",
                secao=FLUIDOS,
            ),
            ItemMenu(
                "app_pages/rede_de_tubos.py",
                "Rede de tubos",
                ":material/lan:",
                "Rede com ramais e malhas: a vazão de cada trecho e a pressão de cada nó",
                secao=FLUIDOS,
            ),
        ),
    ),
    GrupoMenu(
        "Seções e materiais",
        ":material/category:",
        "Desenhar uma seção, consultar ou cadastrar perfis e materiais.",
        (
            ItemMenu(
                "app_pages/desenhar_secao.py",
                "Desenhar seção",
                ":material/draw:",
                "Desenhar uma seção qualquer e usá-la nos outros cálculos",
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
                "Materiais do projeto",
                ":material/science:",
                "Cadastrar no projeto propriedades de material com origem rastreável",
                outros_nomes=("Materiais técnicos",),
            ),
        ),
    ),
    GrupoMenu(
        "Referências e ajuda",
        ":material/menu_book:",
        "Guia, escolha do cálculo, normas técnicas e conversor de unidades.",
        (
            ItemMenu(
                "app_pages/guia_geral.py",
                "Guia geral",
                ":material/help:",
                "Aprender a usar cada página, com exemplos",
            ),
            ItemMenu(
                "app_pages/assistente_projeto.py",
                "Assistente de projeto",
                ":material/route:",
                "Montar um roteiro quando ainda não sei qual análise usar",
            ),
            ItemMenu(
                "app_pages/normas_tecnicas.py",
                "Normas técnicas",
                ":material/library_books:",
                "Localizar a norma aplicável ou pesquisar os PDFs",
            ),
            ItemMenu(
                "app_pages/conversor_unidades.py",
                "Conversor de unidades",
                ":material/swap_horiz:",
                "Converter dados para as unidades do programa",
            ),
        ),
    ),
)


def todos_os_itens() -> list[ItemMenu]:
    return [VISAO_GERAL, *(item for grupo in MENU for item in grupo.itens)]


def item_da_pagina(pagina: str) -> ItemMenu | None:
    """O item de menu de uma página, pelo caminho ``app_pages/...``."""
    return next((item for item in todos_os_itens() if item.pagina == pagina), None)


def grupo_da_pagina(pagina: str) -> GrupoMenu | None:
    """O grupo do menu de uma página (pelo caminho ``app_pages/...`` ou pelo nome do arquivo)."""
    nome = pagina.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".py")
    for grupo in MENU:
        for item in grupo.itens:
            if item.pagina.rsplit("/", 1)[-1].removesuffix(".py") == nome:
                return grupo
    return None
