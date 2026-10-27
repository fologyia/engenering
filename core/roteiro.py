"""Roteiro do projeto com o SolidWorks: os passos, sempre na mesma ordem, e onde o projeto está.

Cada passo diz o que fazer, onde (uma página do programa ou o SolidWorks), que arquivo entra e
que arquivo sai, e o que conferir antes de seguir. A situação de cada passo sai do documento do
projeto ativo: base técnica, esqueleto, plano de cargas, casos importados, registros. Os passos
feitos só no SolidWorks não deixam rastro no projeto — ficam "feitos" quando o passo seguinte,
que usa o que eles geraram, já aconteceu.

Sem Streamlit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core import base_tecnica as bt
from core import cargas_esqueleto as ce
from core import leitura_do_modelo as ld
from core import lista_de_material as lm
from core import plano_de_cargas as pc

SOLIDWORKS = "SolidWorks"

FASE_PREPARAR = "1. Preparar o projeto"
FASE_CARGAS = "2. Cargas"
FASE_SOLIDWORKS = "3. No SolidWorks"
FASE_RESULTADOS = "4. Resultados e verificações"
FASE_FECHAR = "5. Fechar o memorial"
FASES = (FASE_PREPARAR, FASE_CARGAS, FASE_SOLIDWORKS, FASE_RESULTADOS, FASE_FECHAR)


@dataclass(frozen=True)
class Passo:
    numero: int
    fase: str
    titulo: str
    onde: str  # o título da página ou "SolidWorks"
    pagina: str | None  # app_pages/… para o atalho; None no SolidWorks
    entra: str
    sai: str
    fazer: tuple[str, ...]
    conferir: str


PASSOS: tuple[Passo, ...] = (
    Passo(
        1,
        FASE_PREPARAR,
        "Escolher o projeto",
        "Projetos permanentes",
        "app_pages/gestao_projetos.py",
        "—",
        "o projeto ativo",
        (
            "Crie o projeto (código, cliente, responsáveis) ou abra um existente.",
            "Tudo o que vier depois é gravado nele.",
        ),
        "O nome do projeto aparece no topo das páginas.",
    ),
    Passo(
        2,
        FASE_PREPARAR,
        "Base técnica",
        "Base técnica do projeto",
        "app_pages/base_tecnica.py",
        "—",
        "critério do cliente, vento do local, sobrecarga",
        (
            "Escolha o critério do cliente (Anglo American ou só as normas).",
            "Preencha o vento do local, o tipo de estrutura e a sobrecarga; grave.",
        ),
        "As outras páginas passam a começar com esses valores.",
    ),
    Passo(
        3,
        FASE_PREPARAR,
        "Modelo e macro da lista de corte",
        SOLIDWORKS,
        None,
        "a peça soldada (o esqueleto da estrutura)",
        "Peça_lista_de_corte.csv e Peça_esqueleto.csv (na pasta da peça)",
        (
            "Modele o esqueleto (membros estruturais) e as chapas de piso.",
            "Nomeie os membros com o perfil e a função (W200x31,3 - Pilar).",
            "Rode a macro exportar_lista_de_corte.bas (Ferramentas → Macro → Executar).",
        ),
        "Os dois CSV saem na pasta da peça. Mudou o modelo? Rode de novo.",
    ),
    Passo(
        4,
        FASE_CARGAS,
        "Cargas do esqueleto",
        "Cargas do esqueleto",
        "app_pages/cargas_esqueleto.py",
        "Peça_esqueleto.csv",
        "PE, SC, guarda-corpo, escadas e equipamentos nas barras → plano de cargas",
        (
            "Envie o …_esqueleto.csv e grave no projeto (fica guardado para as outras páginas).",
            "Confira a carga do piso pelas chapas, o guarda-corpo e os equipamentos.",
            "Mande as ações ao plano de cargas.",
        ),
        "Os totais por ação batem com o que você espera da plataforma.",
    ),
    Passo(
        5,
        FASE_CARGAS,
        "Vento",
        "Vento em estruturas abertas",
        "app_pages/vento_estrutura_aberta.py",
        "—",
        "W0, W90, W180 e W270 → plano de cargas",
        (
            "Preencha a geometria (comprimento, largura, cotas, vãos).",
            "Forma de aplicar: Simplificada (uma carga por nível nas vigas na direção do vento).",
            "Envie ao plano de cargas.",
        ),
        "Força por nível e momento na base coerentes com o tamanho da estrutura.",
    ),
    Passo(
        6,
        FASE_CARGAS,
        "Plano de cargas e arquivo do gerenciador",
        "Plano de cargas",
        "app_pages/plano_cargas.py",
        "—",
        "Gerenciador de casos de carga (CSV do SolidWorks)",
        (
            "Confira as ações (PP, PE, SC, W0…) e a conferência do plano (sem erros).",
            "Em Exportar para o modelo, baixe o Gerenciador de casos de carga (CSV do SolidWorks)"
            " e a planilha (aba Cargas do estudo: onde e como criar cada carga).",
        ),
        "A conferência do plano não mostra erro; as combinações estão como você quer.",
    ),
    Passo(
        7,
        FASE_SOLIDWORKS,
        "Montar o estudo e rodar",
        SOLIDWORKS,
        None,
        "o CSV do gerenciador (passo 6)",
        "o estudo resolvido, com um caso primário por ação",
        (
            "Material (aço), juntas das vigas, fixações nas bases dos pilares (e pés de escada),"
            " malha.",
            "Crie as cargas como diz a aba Cargas do estudo, com os nomes da convenção (PP, SC"
            " piso, W +X…).",
            "No Gerenciador de casos de carga: Carregar os dados de entrada (o CSV do passo 6);"
            " Executar.",
        ),
        "Sem fixação, o SolidWorks roda com mola macia e os resultados não valem.",
    ),
    Passo(
        8,
        FASE_SOLIDWORKS,
        "Exportar os resultados",
        SOLIDWORKS,
        None,
        "o estudo resolvido",
        "<estudo>-<caso>-reacoes.csv (macro) e <caso>-forcas.csv (Listar, um por caso)",
        (
            "Rode a macro exportar_casos_de_carga.bas (com a referência do Simulation marcada):"
            " saem as reações de todos os casos.",
            "Em cada caso: Vista de resultados → clique no caso → Resultados → Listar forças da"
            " viga → Salvar como PP-forcas.csv, SC-forcas.csv…",
        ),
        "Um -forcas e um -reacoes para cada caso, com o código do caso no nome.",
    ),
    Passo(
        9,
        FASE_RESULTADOS,
        "Importar e conferir as reações",
        "Esforços do modelo",
        "app_pages/esforcos_modelo.py",
        "todos os -forcas.csv e -reacoes.csv (e o …_esqueleto.csv, se ainda não foi)",
        "os casos importados e a conferência das reações",
        (
            "Escolha o eixo vertical (Y; Z se o modelo foi feito com Z para cima).",
            "Remova os casos antigos, se refez o estudo.",
            "Arraste todos os CSV de uma vez.",
        ),
        "Conferência das reações sem erro: cada caso com a carga do plano, no eixo certo.",
    ),
    Passo(
        10,
        FASE_RESULTADOS,
        "Verificar as barras, as fundações e as placas",
        "Esforços do modelo",
        "app_pages/esforcos_modelo.py",
        "—",
        "verificação das barras, quadro das fundações, placas de base (registros); Excel das "
        "reações nas bases para o engenheiro civil",
        (
            "Na tabela das barras: Aplicar as sugestões; confira tipo, perfil e Lx/Ly/Lb.",
            "Veja o pior caso de cada barra e a verificação; ajuste o modelo se algo não passa.",
            "Registre a verificação, o quadro das fundações e as placas no projeto.",
            "Na página Reações nas bases, baixe o Excel com a força e o momento de cada pé, caso a "
            "caso, para quem projeta a fundação.",
        ),
        "Nenhuma barra sem dados; o que não passa tem motivo entendido.",
    ),
    Passo(
        11,
        FASE_RESULTADOS,
        "Lista de material",
        "Lista de material",
        "app_pages/lista_de_material.py",
        "Peça_lista_de_corte.csv",
        "peso, pintura e orçamento (fora do memorial)",
        (
            "Envie a lista de corte do passo 3 e grave.",
            "Confira o peso contra o PP do modelo.",
        ),
        "O peso da lista e o PP do modelo batem (com as ligações).",
    ),
    Passo(
        12,
        FASE_RESULTADOS,
        "Outras verificações",
        "páginas de cálculo",
        "app_pages/degrau_escada.py",
        "—",
        "registros no projeto",
        (
            "Conforme o projeto: degrau e longarina da escada, ligações, contraventamento,"
            " parafusos, vigas de piso.",
            "Registre cada uma no projeto.",
        ),
        "Cada peça do escopo com o seu cálculo registrado.",
    ),
    Passo(
        13,
        FASE_FECHAR,
        "Limpar os registros",
        "Projetos permanentes",
        "app_pages/gestao_projetos.py",
        "—",
        "só os cálculos válidos no memorial",
        (
            "Em Registros técnicos, marque como superado (ou exclua) o que foi refeito.",
            "Vincule os registros às peças do escopo físico.",
        ),
        "Nenhum cálculo repetido ou antigo no memorial.",
    ),
    Passo(
        14,
        FASE_FECHAR,
        "Gerar o memorial",
        "Central de relatórios",
        "app_pages/central_relatorios.py",
        "—",
        "memorial em Word e PDF",
        (
            "Preencha os dados do projeto que faltam (descrição, base de projeto, conclusão).",
            "Gere o Word e o PDF e revise.",
        ),
        "Nenhum [a preencher] que deveria estar preenchido.",
    ),
)


@dataclass(frozen=True)
class Situacao:
    """``feito``: True, False ou None (passo no SolidWorks sem rastro ainda)."""

    feito: bool | None
    texto: str


def _registros(projeto: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [r for r in projeto.get("registros_tecnicos") or [] if isinstance(r, Mapping)]


def situacoes(projeto: Mapping[str, Any] | None) -> list[Situacao]:
    """A situação de cada passo de :data:`PASSOS`, na mesma ordem."""
    if not isinstance(projeto, Mapping):
        return [Situacao(False, "sem projeto ativo")] + [Situacao(None, "—") for _ in PASSOS[1:]]
    base = bt.base_do_projeto(projeto)
    plano = pc.plano_do_projeto(projeto)
    geometria = ld.geometria_do_projeto(projeto)
    lista = lm.lista_do_projeto(projeto)
    casos = (projeto.get("esforcos_do_modelo") or {}).get("casos") or {}
    com_reacoes = [c for c in casos.values() if isinstance(c, Mapping) and c.get("reacoes")]
    registros = _registros(projeto)
    vigentes = [r for r in registros if not r.get("superado_em")]
    do_modelo = [r for r in vigentes if r.get("modulo_id") == "esforcos_modelo"]
    outros = [r for r in vigentes if r.get("modulo_id") != "esforcos_modelo"]
    do_esqueleto = [a for a in plano.acoes if a.origem == ce.ORIGEM]
    ventos = [c for c in plano.codigos if c in pc.CODIGOS_DE_VENTO]
    erros = [
        i
        for i in pc.conferir_plano(plano, anglo=bool(base and base.anglo))
        if i.nivel == pc.NIVEL_ERRO
    ]
    importado = bool(casos)
    titulos = [str(r.get("titulo") or r.get("descricao") or "") for r in vigentes]
    repetidos = len(titulos) - len(set(titulos))
    nome = str(projeto.get("nome") or projeto.get("codigo") or "projeto ativo")
    return [
        Situacao(True, nome),
        Situacao(base is not None, base.rotulo_cliente if base else "não preenchida"),
        Situacao(
            True if geometria.corpos else None,
            f"esqueleto com {len(geometria.corpos)} corpos"
            if geometria.corpos
            else "no SolidWorks",
        ),
        Situacao(
            bool(geometria.corpos and do_esqueleto),
            f"{len(do_esqueleto)} ação(ões) no plano"
            if do_esqueleto
            else ("esqueleto gravado, cargas não enviadas" if geometria.corpos else "pendente"),
        ),
        Situacao(bool(ventos), ", ".join(ventos) if ventos else "sem vento no plano"),
        Situacao(
            bool(plano.acoes) and not erros,
            f"{len(plano.acoes)} ação(ões)"
            + (f", {len(erros)} erro(s) na conferência" if erros else "")
            if plano.acoes
            else "plano vazio",
        ),
        Situacao(True if importado else None, "feito" if importado else "no SolidWorks"),
        Situacao(True if importado else None, "feito" if importado else "no SolidWorks"),
        Situacao(
            importado and len(com_reacoes) == len(casos),
            f"{len(casos)} caso(s), {len(com_reacoes)} com reações" if casos else "nenhum caso",
        ),
        Situacao(bool(do_modelo), f"{len(do_modelo)} registro(s)" if do_modelo else "pendente"),
        Situacao(bool(lista.itens), f"{len(lista.itens)} item(ns)" if lista.itens else "pendente"),
        Situacao(
            True if outros else None,
            f"{len(outros)} registro(s)" if outros else "conforme o projeto",
        ),
        Situacao(
            (repetidos == 0) if vigentes else None,
            f"{repetidos} cálculo(s) com o mesmo título" if repetidos else "sem repetidos",
        ),
        Situacao(None, f"{len(vigentes)} registro(s) para o memorial"),
    ]


def proximo_passo(lista: Sequence[Situacao]) -> int | None:
    """O número do primeiro passo pendente (False) — onde continuar."""
    for passo, situacao in zip(PASSOS, lista, strict=True):
        if situacao.feito is False:
            return passo.numero
    return None
