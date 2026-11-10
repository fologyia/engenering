"""Contratos e registro central dos módulos técnicos do aplicativo.

O catálogo é deliberadamente independente do Streamlit. A interface usa os
metadados de navegação, enquanto registros, validações e relatórios usam a
identidade e a versão do mesmo contrato.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModuloTecnico:
    """Descrição estável de uma capacidade técnica do programa."""

    id: str
    titulo: str
    versao: str
    pagina: str
    grupo_navegacao: str
    ordem: int
    icone: str
    descricao: str
    aliases: tuple[str, ...] = ()
    schema_registro: str = "mecanica-toolkit/registro-tecnico/v2"
    provedor_relatorio: str = "registros"


_MODULOS: dict[str, ModuloTecnico] = {}


def registrar_modulo(modulo: ModuloTecnico, *, substituir: bool = False) -> None:
    """Registra um módulo e impede colisões silenciosas de identidade."""
    chave = modulo.id.strip().casefold()
    if not chave:
        raise ValueError("O módulo técnico precisa de um identificador.")
    if chave in _MODULOS and not substituir:
        raise ValueError(f"Módulo técnico já registrado: {modulo.id}.")
    _MODULOS[chave] = modulo


def obter_modulo(modulo_id: str) -> ModuloTecnico:
    try:
        return _MODULOS[str(modulo_id).strip().casefold()]
    except KeyError as erro:
        raise KeyError(f"Módulo técnico não registrado: {modulo_id}.") from erro


def resolver_modulo(valor: str | None) -> ModuloTecnico | None:
    """Resolve ID, título ou alias sem depender de grafia ou capitalização."""
    procurado = str(valor or "").strip().casefold()
    if not procurado:
        return None
    if procurado in _MODULOS:
        return _MODULOS[procurado]
    for modulo in _MODULOS.values():
        candidatos = (modulo.titulo, *modulo.aliases)
        if any(procurado == candidato.strip().casefold() for candidato in candidatos):
            return modulo
    return None


def listar_modulos(*, grupo: str | None = None) -> list[ModuloTecnico]:
    modulos: Iterable[ModuloTecnico] = _MODULOS.values()
    if grupo is not None:
        alvo = grupo.strip().casefold()
        modulos = (
            modulo for modulo in modulos if modulo.grupo_navegacao.strip().casefold() == alvo
        )
    return sorted(modulos, key=lambda item: (item.ordem, item.titulo.casefold()))


def _registrar_padrao() -> None:
    modulos = (
        ModuloTecnico(
            id="casos_carga",
            titulo="Casos e combinações de carga",
            versao="1.0",
            pagina="app_pages/casos_carga.py",
            grupo_navegacao="Cargas e vento",
            ordem=50,
            icone=":material/layers:",
            descricao="Cenários operacionais, combinações vetoriais e envelopes rastreáveis.",
            aliases=("Casos de carga", "Combinações de carga"),
            provedor_relatorio="carregamentos",
        ),
        ModuloTecnico(
            id="cargas_esqueleto",
            titulo="Cargas do esqueleto",
            versao="1.0",
            pagina="app_pages/cargas_esqueleto.py",
            grupo_navegacao="Cargas e vento",
            ordem=10,
            icone=":material/grid_view:",
            descricao=(
                "O que não está no modelo do esqueleto (piso, guarda-corpo, escadas, equipamentos, "
                "tubulações, ligações, sobrecarga) como cargas características nas barras."
            ),
            aliases=("Cargas para o modelo", "Cargas do piso e acessórios"),
        ),
        ModuloTecnico(
            id="esforcos_modelo",
            titulo="Esforços do modelo",
            versao="1.0",
            pagina="app_pages/esforcos_modelo.py",
            grupo_navegacao="Modelo SolidWorks",
            ordem=10,
            icone=":material/upload_file:",
            descricao=(
                "Resultados do SolidWorks Simulation (forças das vigas e reações) conferidos contra o "
                "plano de cargas, combinados ponto a ponto e verificados barra a barra pela NBR 8800."
            ),
            aliases=("Esforços do SolidWorks", "Verificação das barras do modelo"),
        ),
        ModuloTecnico(
            id="colunas_do_modelo",
            titulo="Colunas do modelo",
            versao="1.0",
            pagina="app_pages/colunas_do_modelo.py",
            grupo_navegacao="Modelo SolidWorks",
            ordem=12,
            icone=":material/view_column:",
            descricao=(
                "Todos os pilares do modelo do SolidWorks com os travamentos lidos do esqueleto, "
                "em x e em y: o K de cada trecho pela Tabela E.1 e a verificação pela NBR 8800."
            ),
            aliases=("Pilares do modelo", "Travamentos dos pilares"),
        ),
        ModuloTecnico(
            id="reacoes_nas_bases",
            titulo="Reações nas bases",
            versao="1.0",
            pagina="app_pages/reacoes_nas_bases.py",
            grupo_navegacao="Modelo SolidWorks",
            ordem=14,
            icone=":material/foundation:",
            descricao=(
                "A força e o momento de cada pé, caso a caso e sem combinar, para quem projeta a "
                "fundação: a ação na fundação e a reação no apoio, o sistema de coordenadas e o "
                "Excel."
            ),
            aliases=("Reações das bases", "Cargas para a fundação"),
        ),
        ModuloTecnico(
            id="sensores_do_modelo",
            titulo="Sensores do modelo",
            versao="1.0",
            pagina="app_pages/sensores_do_modelo.py",
            grupo_navegacao="Modelo SolidWorks",
            ordem=15,
            icone=":material/sensors:",
            descricao=(
                "O quadro dos sensores do gerenciador de casos de carga do SolidWorks (tensão, "
                "deslocamento, fator de segurança) conferido contra o plano de cargas: escoamento "
                "nas ELU, deslocamento nas ELS e o quadro completo no memorial."
            ),
            aliases=("Sensores do SolidWorks", "Resultados do gerenciador de casos de carga"),
        ),
        ModuloTecnico(
            id="modelo_3d",
            titulo="Modelo em 3D",
            versao="1.0",
            pagina="app_pages/modelo_3d.py",
            grupo_navegacao="Modelo SolidWorks",
            ordem=30,
            icone=":material/deployed_code:",
            descricao=(
                "O esqueleto do SolidWorks em 3D com o perfil real das barras, chapas, escadas e "
                "guarda-corpos (detalhados ou como casca translúcida), cargas, apoios e reações; a "
                "vista registrada vai ao memorial."
            ),
            aliases=("Modelo 3D", "Vista 3D", "Visualização 3D"),
        ),
        ModuloTecnico(
            id="analise_estatica",
            titulo="Análise estática",
            versao="1.1",
            pagina="app_pages/analise_estatica.py",
            grupo_navegacao="Mecânica geral",
            ordem=10,
            icone=":material/analytics:",
            descricao="Estado plano de tensões, equivalentes e margens estáticas.",
        ),
        ModuloTecnico(
            id="vento_nbr6123",
            titulo="Vento nas estruturas",
            versao="1.0",
            pagina="app_pages/vento_nbr6123.py",
            grupo_navegacao="Cargas e vento",
            ordem=30,
            icone=":material/air:",
            descricao=(
                "Forças do vento em edificações pela NBR 6123:2023: pressão dinâmica, coeficientes "
                "por zona de paredes e telhado, pressão interna, vedações, arrasto, torção e "
                "cargas do pórtico transversal."
            ),
            aliases=(
                "Vento",
                "NBR 6123",
                "Ação do vento",
                "Forças do vento",
                "Pressão do vento",
                "Cargas de vento",
                "Galpão",
            ),
        ),
        ModuloTecnico(
            id="vento_estrutura_aberta",
            titulo="Vento em estruturas abertas",
            versao="1.0",
            pagina="app_pages/vento_estrutura_aberta.py",
            grupo_navegacao="Cargas e vento",
            ordem=20,
            icone=":material/air:",
            descricao=(
                "Vento em plataformas, mezaninos e pipe racks pela NBR 6123:2023 (capítulo 8): "
                "pórticos como reticulados com proteção η, guarda-corpos e equipamentos; forças por "
                "nível, nos nós e nas barras para o modelo."
            ),
            aliases=(
                "Vento em plataforma",
                "Vento estrutura aberta",
                "Reticulados",
                "Pipe rack vento",
                "Forças do vento nos pórticos",
            ),
        ),
        ModuloTecnico(
            id="flambagem_colunas",
            titulo="Flambagem de colunas",
            versao="3.0",
            pagina="app_pages/flambagem_colunas.py",
            grupo_navegacao="Barras e vigas",
            ordem=20,
            icone=":material/architecture:",
            descricao=(
                "Barra inteira comprimida ou flexocomprimida pela NBR 8800:2008, pelo Projeto "
                "NBR 8800:2025 e pelo AISC 360-16: todos os modos, B_1, interação N + Mx + My "
                "e critério Anglo."
            ),
            aliases=(
                "Flambagem",
                "Euler",
                "Índice de esbeltez",
                "NBR 8800",
                "AISC 360",
                "Coluna",
            ),
        ),
        ModuloTecnico(
            id="vigas_eixos",
            titulo="Vigas e eixos",
            versao="1.0",
            pagina="app_pages/vigas_eixos.py",
            grupo_navegacao="Mecânica geral",
            ordem=20,
            icone=":material/linear_scale:",
            descricao=(
                "Diagramas de cortante e momento, linha elástica, torção e "
                "cargas combinadas em barras retas."
            ),
            aliases=(
                "Viga",
                "Vigas",
                "Eixos",
                "Diagramas de esforços",
                "Linha elástica",
                "Cortante e momento",
            ),
            provedor_relatorio="vigas_eixos",
        ),
        ModuloTecnico(
            id="analise_fadiga",
            titulo="Análise de fadiga",
            versao="1.2",
            pagina="app_pages/analise_fadiga.py",
            grupo_navegacao="Mecânica geral",
            ordem=30,
            icone=":material/cycle:",
            descricao="Resistência à fadiga, critérios de tensão média e vida estimada.",
        ),
        ModuloTecnico(
            id="assistente_cargas",
            titulo="Assistente de cargas",
            versao="2.1",
            pagina="app_pages/assistente_cargas.py",
            grupo_navegacao="Mecânica geral",
            ordem=60,
            icone=":material/manufacturing:",
            descricao="Parafusos, vigas, barras, perfis e elementos de máquinas.",
        ),
        ModuloTecnico(
            id="desenhar_secao",
            titulo="Desenhar seção",
            versao="1.0",
            pagina="app_pages/desenhar_secao.py",
            grupo_navegacao="Seções e materiais",
            ordem=61,
            icone=":material/draw:",
            descricao="Prancheta de seções: propriedades, torção e uso em qualquer cálculo.",
        ),
        ModuloTecnico(
            id="circulo_mohr",
            titulo="Círculo de Mohr",
            versao="1.1",
            pagina="app_pages/circulo_mohr.py",
            grupo_navegacao="Mecânica geral",
            ordem=40,
            icone=":material/donut_large:",
            descricao="Transformações, tensões principais e estados 2D/3D.",
        ),
        ModuloTecnico(
            id="montador_formulas",
            titulo="Montador de fórmulas",
            versao="1.0",
            pagina="app_pages/montador_formulas.py",
            grupo_navegacao="Mecânica geral",
            ordem=45,
            icone=":material/function:",
            descricao="Blocos de seção, esforços e critério, com a fórmula isolada na grandeza.",
        ),
        ModuloTecnico(
            id="montador_fluidos",
            titulo="Montador de fluidos",
            versao="1.0",
            pagina="app_pages/montador_fluidos.py",
            grupo_navegacao="Mecânica dos fluidos",
            ordem=70,
            icone=":material/water_drop:",
            descricao="Blocos de fluido, tubulação e verificação, com a fórmula isolada.",
        ),
        ModuloTecnico(
            id="rede_de_tubos",
            titulo="Rede de tubos",
            versao="1.0",
            pagina="app_pages/rede_de_tubos.py",
            grupo_navegacao="Mecânica dos fluidos",
            ordem=71,
            icone=":material/lan:",
            descricao=(
                "Rede de tubos com ramais e malhas, com reservatórios e bombas: vazão, velocidade e "
                "perda de cada trecho e pressão de cada nó."
            ),
            aliases=("Rede de distribuição", "Hardy Cross"),
        ),
        ModuloTecnico(
            id="analise_sensibilidade",
            titulo="Análise de sensibilidade",
            versao="1.0",
            pagina="app_pages/analise_sensibilidade.py",
            grupo_navegacao="Mecânica geral",
            ordem=50,
            icone=":material/tune:",
            descricao="Influência local, Monte Carlo e risco de não atendimento.",
        ),
        ModuloTecnico(
            id="projeto_parafusos",
            titulo="Projeto de parafusos",
            versao="1.0",
            pagina="app_pages/projeto_parafusos.py",
            grupo_navegacao="Ligações e bases",
            ordem=20,
            icone=":material/build:",
            descricao="Verificação orientativa de juntas e grupos parafusados.",
        ),
        ModuloTecnico(
            id="degrau_escada",
            titulo="Degrau de escada em grade",
            versao="1.0",
            pagina="app_pages/degrau_escada.py",
            grupo_navegacao="Barras e vigas",
            ordem=10,
            icone=":material/stairs:",
            descricao=(
                "Degrau de escada industrial em grade de piso eletrofundida (Selmec DS): "
                "espelho, piso, lances, 64 modelos, flexão, flechas e parafusos, com NR-12, "
                "NR-22, Critério Anglo, NBR 8800 e ISO 14122-3."
            ),
            aliases=(
                "Degrau de escada",
                "Escada industrial",
                "Grade de piso",
                "Degraus Selmec",
                "Escada NR-12",
            ),
        ),
        ModuloTecnico(
            id="viga_de_piso",
            titulo="Vigas de piso",
            versao="1.0",
            pagina="app_pages/viga_de_piso.py",
            grupo_navegacao="Barras e vigas",
            ordem=10,
            icone=":material/view_week:",
            descricao=(
                "Viga que apoia a grade da plataforma: combinações da NBR 8800, flexão com FLT, "
                "cortante, flecha pelo critério Anglo e pela NBR, reação para a ligação e o perfil "
                "mais leve que atende."
            ),
            aliases=("Viga de piso", "Viga da plataforma", "Viga de grade"),
        ),
        ModuloTecnico(
            id="ligacoes_estruturais",
            titulo="Ligações estruturais",
            versao="1.0",
            pagina="app_pages/ligacoes_estruturais.py",
            grupo_navegacao="Ligações e bases",
            ordem=10,
            icone=":material/link:",
            descricao=(
                "Chapa simples e dupla cantoneira viga–viga e viga–pilar (NBR 8800), perfil "
                "formado a frio parafusado (NBR 14762) e ligações soldadas — grupo de filetes, "
                "barra na chapa de nó e chapa no apoio (filete, penetração total ou parcial) —, "
                "com a figura da ligação, as verificações e o memorial."
            ),
            aliases=(
                "Ligação viga-viga",
                "Ligação viga-pilar",
                "Chapa simples",
                "Ligação parafusada perfil frio",
                "Solda de filete",
                "Solda de penetração",
                "Cantoneira soldada",
            ),
        ),
        ModuloTecnico(
            id="contraventamento_estrutura",
            titulo="Contraventamento de estruturas abertas",
            versao="1.0",
            pagina="app_pages/contraventamento_estrutura.py",
            grupo_navegacao="Barras e vigas",
            ordem=30,
            icone=":material/grid_on:",
            descricao=(
                "Contraventamento vertical de plataformas, mezaninos e pipe racks: vento por "
                "reticulados (NBR 6123:2023, cap. 8), combinações ELU/ELS com forças nocionais, "
                "B₂, diagonais (cantoneira, tubo ou tirante), ligações e deslocamentos."
            ),
            aliases=(
                "Contraventamento de plataforma",
                "Estrutura aberta",
                "Plataforma aberta",
                "Pipe rack",
                "Mezanino",
                "Diagonais de contraventamento",
                "Vento em reticulados",
            ),
        ),
        ModuloTecnico(
            id="ligacao_contraventamento",
            titulo="Ligação de contraventamento",
            versao="1.0",
            pagina="app_pages/ligacao_contraventamento.py",
            grupo_navegacao="Ligações e bases",
            ordem=30,
            icone=":material/hub:",
            descricao=(
                "Chapa de nó de contraventamento em canto viga–coluna pelo Método das Forças "
                "Uniformes (AISC Design Guide 29): forças nas interfaces, parafusos, Whitmore, "
                "bloco de cisalhamento, flambagem da chapa, soldas e alma, em LRFD ou ASD."
            ),
            aliases=(
                "Contraventamento",
                "Chapa de nó",
                "Gusset",
                "Método das Forças Uniformes",
                "Ligação de contraventamento vertical",
                "Design Guide 29",
            ),
        ),
        ModuloTecnico(
            id="placa_de_base",
            titulo="Placas de base",
            versao="1.0",
            pagina="app_pages/placa_de_base.py",
            grupo_navegacao="Ligações e bases",
            ordem=40,
            icone=":material/anchor:",
            descricao=(
                "Base de pilar de perfil I ou H pela NBR 8800:2025 (6.7): casos C1 a T3, espessura "
                "da placa, chumbadores, cortante por atrito, placa de cisalhamento ou arruelas "
                "soldadas, Tabela 18, desenho em planta e corte e a base mais leve que atende."
            ),
            aliases=(
                "Placa de base",
                "Base de pilar",
                "Chumbadores",
                "Chumbador",
                "Placa de base NBR 8800",
            ),
        ),
        ModuloTecnico(
            id="estruturas_aco",
            titulo="Estruturas de aço",
            versao="1.1",
            pagina="app_pages/estruturas_aco.py",
            grupo_navegacao="Barras e vigas",
            ordem=40,
            icone=":material/domain:",
            descricao="Barras, ligações, combinações e modelos estruturais 2D.",
        ),
    )
    for modulo in modulos:
        registrar_modulo(modulo)


_registrar_padrao()
