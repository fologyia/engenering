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
            grupo_navegacao="Gestão industrial",
            ordem=15,
            icone=":material/layers:",
            descricao="Cenários operacionais, combinações vetoriais e envelopes rastreáveis.",
            aliases=("Casos de carga", "Combinações de carga"),
            provedor_relatorio="carregamentos",
        ),
        ModuloTecnico(
            id="esforcos_modelo",
            titulo="Esforços do modelo",
            versao="1.0",
            pagina="app_pages/esforcos_modelo.py",
            grupo_navegacao="Gestão industrial",
            ordem=14,
            icone=":material/upload_file:",
            descricao=(
                "Resultados do SolidWorks Simulation (forças das vigas e reações) conferidos contra o "
                "plano de cargas, combinados ponto a ponto e verificados barra a barra pela NBR 8800."
            ),
            aliases=("Esforços do SolidWorks", "Verificação das barras do modelo"),
        ),
        ModuloTecnico(
            id="analise_estatica",
            titulo="Análise estática",
            versao="1.1",
            pagina="app_pages/analise_estatica.py",
            grupo_navegacao="Análises técnicas",
            ordem=10,
            icone=":material/analytics:",
            descricao="Estado plano de tensões, equivalentes e margens estáticas.",
        ),
        ModuloTecnico(
            id="vento_nbr6123",
            titulo="Vento nas estruturas",
            versao="1.0",
            pagina="app_pages/vento_nbr6123.py",
            grupo_navegacao="Análises técnicas",
            ordem=12,
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
            grupo_navegacao="Análises técnicas",
            ordem=13,
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
            grupo_navegacao="Análises técnicas",
            ordem=15,
            icone=":material/architecture:",
            descricao=(
                "Barra inteira comprimida ou flexocomprimida pela NBR 8800:2008, pelo Projeto "
                "NBR 8800:2024 e pelo AISC 360-16: todos os modos, B_1, interação N + Mx + My "
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
            grupo_navegacao="Análises técnicas",
            ordem=25,
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
            grupo_navegacao="Análises técnicas",
            ordem=20,
            icone=":material/cycle:",
            descricao="Resistência à fadiga, critérios de tensão média e vida estimada.",
        ),
        ModuloTecnico(
            id="assistente_cargas",
            titulo="Assistente de cargas",
            versao="1.1",
            pagina="app_pages/assistente_cargas.py",
            grupo_navegacao="Análises técnicas",
            ordem=30,
            icone=":material/manufacturing:",
            descricao="Conversão de esforços e geometrias em estados de tensão.",
        ),
        ModuloTecnico(
            id="circulo_mohr",
            titulo="Círculo de Mohr",
            versao="1.1",
            pagina="app_pages/circulo_mohr.py",
            grupo_navegacao="Análises técnicas",
            ordem=40,
            icone=":material/donut_large:",
            descricao="Transformações, tensões principais e estados 2D/3D.",
        ),
        ModuloTecnico(
            id="analise_sensibilidade",
            titulo="Análise de sensibilidade",
            versao="1.0",
            pagina="app_pages/analise_sensibilidade.py",
            grupo_navegacao="Análises técnicas",
            ordem=50,
            icone=":material/tune:",
            descricao="Influência local, Monte Carlo e risco de não atendimento.",
        ),
        ModuloTecnico(
            id="projeto_parafusos",
            titulo="Projeto de parafusos",
            versao="1.0",
            pagina="app_pages/projeto_parafusos.py",
            grupo_navegacao="Dimensionamento complementar",
            ordem=10,
            icone=":material/build:",
            descricao="Verificação orientativa de juntas e grupos parafusados.",
        ),
        ModuloTecnico(
            id="degrau_escada",
            titulo="Degrau de escada em grade",
            versao="1.0",
            pagina="app_pages/degrau_escada.py",
            grupo_navegacao="Dimensionamento complementar",
            ordem=15,
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
            id="contraventamento_estrutura",
            titulo="Contraventamento de estruturas abertas",
            versao="1.0",
            pagina="app_pages/contraventamento_estrutura.py",
            grupo_navegacao="Dimensionamento complementar",
            ordem=16,
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
            grupo_navegacao="Dimensionamento complementar",
            ordem=17,
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
            id="estruturas_aco",
            titulo="Estruturas de aço",
            versao="1.1",
            pagina="app_pages/estruturas_aco.py",
            grupo_navegacao="Dimensionamento complementar",
            ordem=20,
            icone=":material/domain:",
            descricao="Barras, ligações, combinações e modelos estruturais 2D.",
        ),
    )
    for modulo in modulos:
        registrar_modulo(modulo)


_registrar_padrao()
