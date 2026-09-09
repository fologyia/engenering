"""Contratos e registro central dos módulos técnicos do aplicativo.

O catálogo é deliberadamente independente do Streamlit. A interface usa os
metadados de navegação, enquanto registros, validações e relatórios usam a
identidade e a versão do mesmo contrato.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


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
            modulo
            for modulo in modulos
            if modulo.grupo_navegacao.strip().casefold() == alvo
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
            id="flambagem_colunas",
            titulo="Flambagem de colunas",
            versao="1.0",
            pagina="app_pages/flambagem_colunas.py",
            grupo_navegacao="Análises técnicas",
            ordem=15,
            icone=":material/architecture:",
            descricao="Esbeltez, carga crítica de Euler e transição de Johnson para peças comprimidas.",
            aliases=("Flambagem", "Euler", "Índice de esbeltez"),
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

