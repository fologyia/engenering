"""Plano de cargas do projeto: as ações com nome padrão, de onde vieram e as combinações.

Fica no documento do projeto em ``projeto["plano_de_cargas"]``. Cada ação tem um **código** fixo
(PP, PE, EQ, EO, SC, W0, W90, W180, W270, T+, T−, PRV, HT, HL, MO, IM, EX), a **categoria** da NBR
8800 (que dá γ e ψ), o **grupo** exclusivo (o vento nas quatro direções nunca atua junto), a
**origem** (a página ou o registro que a gerou) e as **cargas** que vão para o modelo — uma
linha por elemento (pórtico, nível, barra), com valor, unidade e direção, para lançar no
SolidWorks ou no Robot. Os valores são característicos: as combinações saem daqui com os seus
coeficientes, e o quadro de cargas para fundações usa as ações **sem** combinar nem majorar
(critério Anglo 5.9).

Sem Streamlit.
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from typing import Any

from core import criterio_anglo as ca
from core import load_combinations as comb

CATEGORIA_PP = "Peso próprio de estrutura metálica"
CATEGORIA_PE = "Elementos construtivos industrializados (grades, pisos, guarda-corpos)"
CATEGORIA_EQ = "Peso próprio de equipamentos (Projeto NBR 8800:2024)"
CATEGORIA_SC = "Sobrecarga de uso — predominância de equipamentos fixos ou concentração de pessoas"
CATEGORIA_VENTO = "Vento (NBR 6123)"
CATEGORIA_TEMPERATURA = "Variação de temperatura"
CATEGORIA_PONTE = "Pontes rolantes — pilares e subestruturas das vigas de rolamento"
CATEGORIA_EXCEPCIONAL = "Ação excepcional (impacto, explosão, incêndio)"
CATEGORIA_OPERACAO = "Forças horizontais de equipamentos em operação"

GRUPO_VENTO = "Vento"
GRUPO_TEMPERATURA = "Temperatura"
GRUPO_HT = "Ponte — horizontal transversal"


@dataclass(frozen=True)
class CodigoDeAcao:
    codigo: str
    nome: str
    categoria: str
    grupo: str = ""
    descricao: str = ""


CODIGOS: tuple[CodigoDeAcao, ...] = (
    CodigoDeAcao(
        "PP", "Peso próprio da estrutura", CATEGORIA_PP, descricao="Perfis, chapas e ligações."
    ),
    CodigoDeAcao(
        "PE",
        "Permanentes de elementos construtivos",
        CATEGORIA_PE,
        descricao="Piso (grade ou chapa), guarda-corpos, tubulações, bandejas, cobertura e fechamento.",
    ),
    CodigoDeAcao(
        "EQ",
        "Equipamentos (vazios)",
        CATEGORIA_EQ,
        descricao="Peso próprio dos equipamentos fixos.",
    ),
    CodigoDeAcao(
        "EO",
        "Equipamentos em operação (conteúdo)",
        "Sobrecarga de uso — bibliotecas, arquivos, depósitos, oficinas e garagens",
        descricao="Material processado, água, produto; entupimento de chutes e calhas (Anglo 5.11).",
    ),
    CodigoDeAcao(
        "SC",
        "Sobrecarga de uso",
        CATEGORIA_SC,
        descricao="Pessoas, ferramentas, manutenção (Anglo Tabela 2).",
    ),
    CodigoDeAcao("W0", "Vento a 0° (+X)", CATEGORIA_VENTO, GRUPO_VENTO),
    CodigoDeAcao("W90", "Vento a 90° (+Y)", CATEGORIA_VENTO, GRUPO_VENTO),
    CodigoDeAcao("W180", "Vento a 180° (−X)", CATEGORIA_VENTO, GRUPO_VENTO),
    CodigoDeAcao("W270", "Vento a 270° (−Y)", CATEGORIA_VENTO, GRUPO_VENTO),
    CodigoDeAcao(
        "T+", "Temperatura +10 °C", CATEGORIA_TEMPERATURA, GRUPO_TEMPERATURA, "Anglo 5.8."
    ),
    CodigoDeAcao(
        "T−", "Temperatura −10 °C", CATEGORIA_TEMPERATURA, GRUPO_TEMPERATURA, "Anglo 5.8."
    ),
    CodigoDeAcao(
        "PRV",
        "Ponte rolante — vertical",
        CATEGORIA_PONTE,
        descricao="Rodas majoradas em 25 % (Anglo 5.4).",
    ),
    CodigoDeAcao("HT", "Ponte rolante — horizontal transversal", CATEGORIA_PONTE, GRUPO_HT),
    CodigoDeAcao("HL", "Ponte rolante — horizontal longitudinal", CATEGORIA_PONTE),
    CodigoDeAcao(
        "MO",
        "Monovia",
        CATEGORIA_PONTE,
        descricao="Impacto: +20 % da carga e +10 % das partes móveis (Anglo 5.5).",
    ),
    CodigoDeAcao(
        "IM",
        "Impacto e cargas dinâmicas de equipamentos",
        CATEGORIA_OPERACAO,
        descricao="Anglo 5.3.",
    ),
    CodigoDeAcao(
        "EX",
        "Ação excepcional",
        CATEGORIA_EXCEPCIONAL,
        descricao="Choque, explosão; linha de vida (15 kN, Anglo 5.10).",
    ),
)
CODIGOS_POR_NOME = {c.codigo: c for c in CODIGOS}

#: Combinação mínima do critério Anglo (5.9) → códigos que ela precisa.
COMBINACOES_ANGLO: tuple[tuple[str, tuple[tuple[str, ...], ...]], ...] = (
    (ca.COMBINACOES_MINIMAS[0], (("PP",), ("SC",), ("EQ",), ("PRV",), ("MO",))),
    (ca.COMBINACOES_MINIMAS[1], (("PP",), ("SC",), ("EQ",), ("PRV",), ("HT",), ("MO",))),
    (ca.COMBINACOES_MINIMAS[2], (("PP",), ("EQ",), ("W0", "W90", "W180", "W270"))),
    (
        ca.COMBINACOES_MINIMAS[3],
        (("PP",), ("EQ",), ("SC",), ("PRV",), ("MO",), ("W0", "W90", "W180", "W270")),
    ),
    (
        ca.COMBINACOES_MINIMAS[4],
        (("PP",), ("EQ",), ("SC",), ("PRV",), ("HT",), ("MO",), ("W0", "W90", "W180", "W270")),
    ),
    (ca.COMBINACOES_MINIMAS[5], (("HL",), ("W0", "W90", "W180", "W270"))),
)
#: Códigos que só existem se o projeto tiver o equipamento (não contam como faltantes).
CODIGOS_OPCIONAIS = frozenset({"PRV", "HT", "HL", "MO"})

UNIDADES = ("kN", "kN/m", "kN/m²", "kN·m", "°C")
DIRECOES = ("X", "Y", "Z (vertical)", "—")


class PlanoInvalido(ValueError):
    """Dado que o plano não aceita; a mensagem diz o que corrigir."""


@dataclass(frozen=True)
class CargaDoModelo:
    """Uma linha do que vai para o modelo: onde, quanto e em que direção."""

    elemento: str
    valor: float
    unidade: str = "kN"
    direcao: str = "X"
    observacao: str = ""


@dataclass(frozen=True)
class Acao:
    codigo: str
    nome: str
    categoria: str
    grupo: str = ""
    origem: str = "Informada"
    registro_id: str = ""
    descricao: str = ""
    resumo: str = ""
    cargas: tuple[CargaDoModelo, ...] = ()
    atualizado_em: str = ""

    @property
    def tipo(self) -> str:
        return comb.categoria_nbr(self.categoria).tipo


@dataclass(frozen=True)
class PlanoDeCargas:
    acoes: tuple[Acao, ...] = ()
    atualizado_em: str = ""

    def acao(self, codigo: str) -> Acao | None:
        return next((a for a in self.acoes if a.codigo == codigo), None)

    @property
    def codigos(self) -> tuple[str, ...]:
        return tuple(a.codigo for a in self.acoes)


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------------------------
# Criação, validação e edição
# ---------------------------------------------------------------------------------------------
def nova_acao(
    codigo: str,
    *,
    nome: str = "",
    categoria: str = "",
    grupo: str | None = None,
    origem: str = "Informada",
    registro_id: str = "",
    descricao: str = "",
    resumo: str = "",
    cargas: Iterable[CargaDoModelo] = (),
) -> Acao:
    padrao = CODIGOS_POR_NOME.get(codigo)
    return Acao(
        codigo=codigo.strip(),
        nome=nome.strip() or (padrao.nome if padrao else codigo),
        categoria=categoria or (padrao.categoria if padrao else CATEGORIA_SC),
        grupo=(padrao.grupo if padrao else "") if grupo is None else grupo,
        origem=origem,
        registro_id=registro_id,
        descricao=descricao or (padrao.descricao if padrao else ""),
        resumo=resumo,
        cargas=tuple(cargas),
        atualizado_em=agora(),
    )


def validar_acao(a: Acao) -> list[str]:
    erros: list[str] = []
    if not a.codigo:
        erros.append("Toda ação precisa de um código.")
    try:
        categoria = comb.categoria_nbr(a.categoria)
    except ValueError:
        erros.append(f"{a.codigo}: categoria desconhecida ({a.categoria!r}).")
    else:
        if categoria.tipo == comb.TIPO_PERMANENTE and a.grupo:
            erros.append(f"{a.codigo}: ação permanente não pode ter grupo exclusivo.")
    for c in a.cargas:
        if not math.isfinite(c.valor):
            erros.append(f"{a.codigo}: valor inválido em {c.elemento!r}.")
        if c.unidade not in UNIDADES:
            erros.append(f"{a.codigo}: unidade desconhecida ({c.unidade!r}).")
    return erros


def com_acao(plano: PlanoDeCargas, acao: Acao) -> PlanoDeCargas:
    """Inclui a ação, ou substitui a de mesmo código (o plano tem um código por ação)."""
    erros = validar_acao(acao)
    if erros:
        raise PlanoInvalido(" ".join(erros))
    outras = [a for a in plano.acoes if a.codigo != acao.codigo]
    ordem = {c.codigo: i for i, c in enumerate(CODIGOS)}
    acoes = sorted([*outras, acao], key=lambda a: (ordem.get(a.codigo, len(ordem)), a.codigo))
    return PlanoDeCargas(tuple(acoes), agora())


def sem_acao(plano: PlanoDeCargas, codigo: str) -> PlanoDeCargas:
    return PlanoDeCargas(tuple(a for a in plano.acoes if a.codigo != codigo), agora())


# ---------------------------------------------------------------------------------------------
# Leitura e gravação no projeto
# ---------------------------------------------------------------------------------------------
def para_dicionario(plano: PlanoDeCargas) -> dict[str, Any]:
    return {"acoes": [asdict(a) for a in plano.acoes], "atualizado_em": plano.atualizado_em}


def de_dicionario(dados: Mapping[str, Any] | None) -> PlanoDeCargas:
    if not isinstance(dados, Mapping):
        return PlanoDeCargas()
    acoes = []
    for item in dados.get("acoes") or []:
        if not isinstance(item, Mapping):
            continue
        cargas = tuple(
            CargaDoModelo(
                elemento=str(c.get("elemento") or ""),
                valor=float(c.get("valor") or 0.0),
                unidade=str(c.get("unidade") or "kN"),
                direcao=str(c.get("direcao") or "—"),
                observacao=str(c.get("observacao") or ""),
            )
            for c in item.get("cargas") or []
            if isinstance(c, Mapping)
        )
        acoes.append(
            Acao(
                codigo=str(item.get("codigo") or ""),
                nome=str(item.get("nome") or ""),
                categoria=str(item.get("categoria") or CATEGORIA_SC),
                grupo=str(item.get("grupo") or ""),
                origem=str(item.get("origem") or "Informada"),
                registro_id=str(item.get("registro_id") or ""),
                descricao=str(item.get("descricao") or ""),
                resumo=str(item.get("resumo") or ""),
                cargas=cargas,
                atualizado_em=str(item.get("atualizado_em") or ""),
            )
        )
    return PlanoDeCargas(tuple(acoes), str(dados.get("atualizado_em") or ""))


def plano_do_projeto(projeto: Mapping[str, Any] | None) -> PlanoDeCargas:
    if not isinstance(projeto, Mapping):
        return PlanoDeCargas()
    return de_dicionario(projeto.get("plano_de_cargas"))


# ---------------------------------------------------------------------------------------------
# Combinações
# ---------------------------------------------------------------------------------------------
def acoes_para_combinar(plano: PlanoDeCargas) -> list[comb.AcaoEstrutural]:
    """As ações do plano como ações de combinação (os esforços ficam por conta do modelo)."""
    return [comb.acao_da_categoria(a.codigo, a.categoria, grupo=a.grupo) for a in plano.acoes]


#: Colunas do editor de ações da página Estruturas de aço (combinações de uma barra).
COLUNAS_DOS_ESFORCOS = (
    "nome",
    "categoria",
    "tipo",
    "grupo",
    "N (kN)",
    "V (kN)",
    "M (kN·m)",
    "γ",
    "ψ0",
    "ψ1",
    "ψ2",
)


def linhas_para_esforcos(plano: PlanoDeCargas) -> list[list[Any]]:
    """As ações do plano como linhas do editor de combinações de uma barra.

    Código, categoria, tipo, grupo e coeficientes vêm do plano; N, V e M ficam zerados para o
    engenheiro preencher com os esforços característicos da barra tirados do modelo.
    """
    linhas: list[list[Any]] = []
    for a in plano.acoes:
        cat = comb.categoria_nbr(a.categoria)
        linhas.append(
            [
                a.codigo,
                a.categoria,
                cat.tipo,
                a.grupo,
                0.0,
                0.0,
                0.0,
                cat.gamma,
                cat.psi0,
                cat.psi1,
                cat.psi2,
            ]
        )
    return linhas


@dataclass(frozen=True)
class LinhaDeCombinacao:
    numero: int
    nome: str
    estado_limite: str
    expressao: str
    fatores: Mapping[str, float] = field(default_factory=dict)


def combinacoes(
    plano: PlanoDeCargas,
    estados: Sequence[str] = comb.ESTADOS_PADRAO,
    *,
    especial_curta_duracao: bool = False,
) -> list[LinhaDeCombinacao]:
    """Todas as combinações explícitas, numeradas (o número serve de nome no modelo)."""
    if not plano.acoes:
        return []
    lista = comb.gerar_combinacoes(
        acoes_para_combinar(plano), estados, especial_curta_duracao=especial_curta_duracao
    )
    return [
        LinhaDeCombinacao(i, c.nome, c.estado_limite, c.expressao, dict(c.fatores))
        for i, c in enumerate(lista, start=1)
    ]


@dataclass(frozen=True)
class CoberturaAnglo:
    combinacao: str
    presentes: tuple[str, ...]
    faltantes: tuple[str, ...]  # códigos obrigatórios ausentes
    opcionais_ausentes: tuple[str, ...]  # PRV, HT, HL, MO: só se houver o equipamento

    @property
    def coberta(self) -> bool:
        return not self.faltantes


def cobertura_das_combinacoes_anglo(plano: PlanoDeCargas) -> list[CoberturaAnglo]:
    """Quais combinações mínimas do critério Anglo (5.9) o plano já consegue formar."""
    existentes = set(plano.codigos)
    resultado = []
    for texto, requisitos in COMBINACOES_ANGLO:
        presentes, faltantes, opcionais = [], [], []
        for alternativas in requisitos:
            achado = [c for c in alternativas if c in existentes]
            if achado:
                presentes.extend(achado)
            elif all(c in CODIGOS_OPCIONAIS for c in alternativas):
                opcionais.append("/".join(alternativas))
            else:
                faltantes.append("/".join(alternativas))
        resultado.append(
            CoberturaAnglo(texto, tuple(presentes), tuple(faltantes), tuple(opcionais))
        )
    return resultado


# ---------------------------------------------------------------------------------------------
# Exportação (CSV com separador ";" e vírgula decimal — abre direto no Excel em português)
# ---------------------------------------------------------------------------------------------
def _csv(cabecalho: Sequence[str], linhas: Iterable[Sequence[Any]]) -> bytes:
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(cabecalho)
    for linha in linhas:
        escritor.writerow(
            [f"{v:.4f}".replace(".", ",") if isinstance(v, float) else v for v in linha]
        )
    return saida.getvalue().encode("utf-8-sig")


def csv_das_acoes(plano: PlanoDeCargas) -> bytes:
    linhas = []
    for a in plano.acoes:
        cat = comb.categoria_nbr(a.categoria)
        linhas.append(
            [
                a.codigo,
                a.nome,
                cat.tipo,
                a.categoria,
                a.grupo,
                cat.gamma,
                "" if cat.gamma_favoravel is None else cat.gamma_favoravel,
                cat.psi0,
                cat.psi1,
                cat.psi2,
                a.origem,
                a.resumo,
            ]
        )
    return _csv(
        [
            "Código",
            "Nome",
            "Tipo",
            "Categoria NBR 8800",
            "Grupo exclusivo",
            "γ",
            "γ favorável",
            "ψ0",
            "ψ1",
            "ψ2",
            "Origem",
            "Resumo",
        ],
        linhas,
    )


def csv_das_cargas(plano: PlanoDeCargas) -> bytes:
    """Uma linha por carga de cada ação: o que lançar no modelo (valores característicos)."""
    linhas = [
        [a.codigo, a.nome, c.elemento, c.direcao, c.valor, c.unidade, c.observacao]
        for a in plano.acoes
        for c in a.cargas
    ]
    return _csv(["Ação", "Nome", "Elemento", "Direção", "Valor", "Unidade", "Observação"], linhas)


def csv_das_combinacoes(
    plano: PlanoDeCargas, estados: Sequence[str] = comb.ESTADOS_PADRAO
) -> bytes:
    lista = combinacoes(plano, estados)
    codigos = list(plano.codigos)
    linhas = [
        [
            c.numero,
            c.estado_limite,
            c.nome,
            *[float(c.fatores.get(k, 0.0)) for k in codigos],
            c.expressao,
        ]
        for c in lista
    ]
    return _csv(["Nº", "Estado-limite", "Combinação", *codigos, "Expressão"], linhas)


def resumo_do_plano(plano: PlanoDeCargas) -> str:
    if not plano.acoes:
        return "Plano de cargas vazio."
    return f"{len(plano.acoes)} ação(ões): " + ", ".join(plano.codigos)


def acoes_de_vento(
    origem: str,
    forcas_por_direcao: Mapping[str, Sequence[CargaDoModelo]],
    *,
    resumo_por_direcao: Mapping[str, str] | None = None,
    registro_id: str = "",
) -> list[Acao]:
    """W0, W90, W180 e W270 a partir das cargas de +X e +Y (as de −X e −Y com o sinal trocado)."""
    resumo_por_direcao = resumo_por_direcao or {}
    acoes = []
    for codigo, direcao, sinal in (
        ("W0", "X", 1.0),
        ("W90", "Y", 1.0),
        ("W180", "X", -1.0),
        ("W270", "Y", -1.0),
    ):
        cargas = [
            replace(c, valor=sinal * c.valor, direcao=("+" if sinal > 0 else "−") + direcao)
            for c in forcas_por_direcao.get(direcao, ())
        ]
        acoes.append(
            nova_acao(
                codigo,
                origem=origem,
                registro_id=registro_id,
                resumo=resumo_por_direcao.get(direcao, ""),
                cargas=cargas,
            )
        )
    return acoes
