"""Quadro de cargas para as fundações a partir dos esforços do modelo (SolidWorks).

Para cada barra marcada como **Pilar** na tabela das barras, os esforços na ponta de **base** em
cada caso de carga importado — **sem combinar nem majorar** (critério Anglo AA-BR-DPST-DR-0001,
item 5.9: as ações dos quadros de cargas para as fundações não são combinadas nem majoradas; quem
projeta a fundação faz as combinações dela).

* A base é a ponta inicial ou final da lista de pontos do pilar no arquivo do SolidWorks. No modo
  automático o programa a acha pelo **peso próprio**: nos casos de gravidade (o PP e os de reação
  só vertical), dentro de cada elemento a compressão cresce para baixo — e o mesmo no estudo único
  com gravidade e vento juntos. Um caso só de vento não serve: o pilar de barlavento é tracionado
  e a maior força fica na base com o sinal trocado. Sem peso no pilar, vale a ponta mais
  comprimida nos casos de gravidade; sem isso, a combinação de pontas em que a soma das bases
  fecha com a reação vertical (quando só uma fecha); sem nada disso, o programa pede a escolha.
* Convenção: **N** = força vertical na fundação, compressão positiva; **V₁, V₂, M₁, M₂ e T** = os
  esforços internos na seção da base, nos eixos 1 e 2 da seção do SolidWorks (o eixo forte está na
  tabela das barras).
* Conferência: a soma de N nas bases de todos os pilares tem de bater com a reação vertical total do
  modelo (arquivo "Listar forças resultantes"), quando todos os apoios são bases de pilares.
* **Nos eixos do modelo**: com a direção da seção de cada pilar no Simulation
  (:mod:`core.direcoes_da_secao`), a força e o momento horizontais que o pilar faz na fundação saem
  nos eixos do SolidWorks (F e M em X e Z, com Y vertical) — o que quem projeta a base usa.

Sem Streamlit.
"""

from __future__ import annotations

import io
import itertools
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from core import criterio_anglo as ca
from core import esforcos_modelo as em
from core import plano_de_cargas as pc
from core.technical_records import criar_registro_tecnico

BASE_AUTOMATICA = em.BASE_AUTOMATICA
BASE_INICIO = em.BASE_INICIO
BASE_FIM = em.BASE_FIM
BASES = em.BASES
TOLERANCIA_BASE = 0.005  # diferença relativa mínima de compressão entre as pontas
CODIGO_PP = "PP"
#: Caso de gravidade: a reação é para cima e a horizontal não passa desta fração da vertical.
HORIZONTAL_DA_GRAVIDADE = 0.10
#: O arquivo do SolidWorks traz cinco algarismos: a variação da normal dentro dos elementos só
#: conta acima do arredondamento somado (e de um mínimo, em kN).
ALGARISMOS_DO_ARQUIVO = 1e-4
PESO_MINIMO_KN = 0.005
#: Acima disto o programa não tenta as bases pela soma (2ⁿ combinações).
PILARES_PELA_SOMA = 12

ORIGEM_ESCOLHIDA = "escolhida"
ORIGEM_PESO = "automática (peso próprio: a compressão cresce para a base)"
ORIGEM_GRAVIDADE = "automática (ponta mais comprimida nos casos de gravidade)"
ORIGEM_SOMA = "automática (a soma das bases fecha com a reação vertical do modelo)"
SEM_GRAVIDADE = (
    "sem caso de peso próprio (PP) ou de carga só vertical para saber qual ponta é a de baixo: "
    "escolha a base na tabela das barras"
)
MESMA_COMPRESSAO = "as duas pontas têm a mesma compressão: escolha a base na tabela das barras"


@dataclass(frozen=True)
class CargaNaBase:
    pilar: str
    caso: str
    n: float  # compressão positiva
    v1: float
    v2: float
    m1: float
    m2: float
    t: float


@dataclass(frozen=True)
class PilarDoQuadro:
    pilar: str
    perfil: str
    eixo_forte: str
    base: str | None  # BASE_INICIO, BASE_FIM ou None (não deu para saber)
    origem_da_base: str  # "escolhida", "automática (…)" ou o motivo de não saber
    cargas: tuple[CargaNaBase, ...]
    #: A ponta de baixo pelo peso próprio, quando a base escolhida na tabela é a outra.
    base_pelo_peso: str | None = None


@dataclass(frozen=True)
class QuadroDeFundacoes:
    pilares: tuple[PilarDoQuadro, ...]
    casos: tuple[str, ...]
    conferencia: tuple[pc.ItemDeConferencia, ...]

    @property
    def pendentes(self) -> tuple[PilarDoQuadro, ...]:
        return tuple(p for p in self.pilares if p.base is None)

    @property
    def de_ponta_cabeca(self) -> tuple[PilarDoQuadro, ...]:
        """Os pilares com a base escolhida na ponta de cima (o peso próprio mostra a outra)."""
        return tuple(p for p in self.pilares if p.base_pelo_peso is not None)


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def casos_de_gravidade(dados: em.EsforcosDoModelo) -> tuple[str, ...]:
    """Os casos em que a carga só desce: o PP (primeiro) e os de reação para cima com a horizontal
    desprezável. Neles a compressão de um pilar nunca diminui de cima para baixo — num caso de
    vento não vale: o pilar de barlavento é tracionado, e a maior força fica na base com o sinal
    trocado."""
    primeiro: list[str] = []
    outros: list[str] = []
    for codigo, caso in dados.casos.items():
        if codigo.strip().upper() == CODIGO_PP:
            primeiro.append(codigo)
            continue
        if caso.reacoes is None:
            continue
        rx, ry, vertical = em.para_o_plano(caso.reacoes.modelo, dados.eixo_vertical)
        if vertical > 0.05 and math.hypot(rx, ry) <= HORIZONTAL_DA_GRAVIDADE * vertical:
            outros.append(codigo)
    return (*primeiro, *outros)


def _pelo_peso_nos_elementos(pontos: Sequence[em.PontoDeEsforco]) -> str | None:
    """A ponta de baixo pela carga ao longo do pilar: dentro de cada elemento a normal muda do
    peso do trecho, e a compressão cresce para baixo. Não depende das cargas que as vigas
    entregam nos nós."""
    variacao = 0.0
    elementos = 0
    maior = max((abs(p.n) for p in pontos), default=0.0)
    for a, b in zip(pontos, pontos[1:], strict=False):
        if a.elemento == b.elemento and a.fim != b.fim:
            variacao += b.n - a.n
            elementos += 1
    if not elementos:
        return None
    if abs(variacao) <= max(PESO_MINIMO_KN, 2.0 * elementos * ALGARISMOS_DO_ARQUIVO * maior):
        return None
    # A normal cai (mais compressão) ao longo da lista: a lista desce, e a base é o fim dela.
    return BASE_FIM if variacao < 0 else BASE_INICIO


def _pela_ponta_mais_comprimida(pontos: Sequence[em.PontoDeEsforco]) -> str | None:
    if len(pontos) < 2:
        return None
    inicio, fim = pontos[0].n, pontos[-1].n
    referencia = max(abs(inicio), abs(fim))
    if referencia <= 1e-9 or abs(inicio - fim) / referencia < TOLERANCIA_BASE:
        return None
    return BASE_INICIO if inicio < fim else BASE_FIM


def _voto(
    pontos_por_caso: Mapping[str, Sequence[em.PontoDeEsforco]],
    gravidade: Sequence[str],
    regra: Any,
) -> str | None:
    """O que a ``regra`` diz nos casos de gravidade: o PP decide; sem ele, os outros casos têm de
    concordar."""
    votos: list[str] = []
    for caso in gravidade:
        pontos = pontos_por_caso.get(caso)
        if not pontos:
            continue
        ponta = regra(pontos)
        if ponta is None:
            continue
        if caso.strip().upper() == CODIGO_PP:
            return str(ponta)
        votos.append(str(ponta))
    return votos[0] if votos and len(set(votos)) == 1 else None


def casos_com_gravidade(dados: em.EsforcosDoModelo) -> tuple[str, ...]:
    """Os casos que não são só de gravidade mas podem tê-la: os de reação para cima com carga
    horizontal junto (o estudo único, com tudo ligado) e os sem o arquivo de reações. Neles só
    vale o peso do pilar dentro dos elementos, nunca a ponta mais comprimida."""
    de_gravidade = set(casos_de_gravidade(dados))
    saida = []
    for codigo, caso in dados.casos.items():
        if codigo in de_gravidade:
            continue
        if caso.reacoes is None:
            saida.append(codigo)
        elif em.para_o_plano(caso.reacoes.modelo, dados.eixo_vertical)[2] > 0.05:
            saida.append(codigo)
    return tuple(saida)


def base_pelos_esforcos(
    pontos_por_caso: Mapping[str, Sequence[em.PontoDeEsforco]],
    gravidade: Sequence[str] | None = None,
    com_gravidade: Sequence[str] = (),
) -> tuple[str | None, str]:
    """A ponta de baixo do pilar pelo que os esforços mostram, e de onde veio (ou por que não).

    ``gravidade``: os casos de carga só vertical (:func:`casos_de_gravidade`); sem a lista, o PP
    ou, sem ele, todos os casos. ``com_gravidade``: os casos com gravidade e carga horizontal
    juntas (:func:`casos_com_gravidade`). A ordem das provas: o peso próprio dentro dos elementos
    nos casos de gravidade; o mesmo nos casos com gravidade (todos têm de concordar); e, sem peso
    no pilar, a ponta mais comprimida — esta só nos casos de gravidade."""
    if gravidade is None:
        gravidade = [c for c in pontos_por_caso if c.strip().upper() == CODIGO_PP] or list(
            pontos_por_caso
        )
    pelo_peso = _voto(pontos_por_caso, gravidade, _pelo_peso_nos_elementos) or _voto(
        pontos_por_caso, com_gravidade, _pelo_peso_nos_elementos
    )
    if pelo_peso is not None:
        return pelo_peso, ORIGEM_PESO
    pela_ponta = _voto(pontos_por_caso, gravidade, _pela_ponta_mais_comprimida)
    if pela_ponta is not None:
        return pela_ponta, ORIGEM_GRAVIDADE
    if not any(pontos_por_caso.get(c) for c in gravidade):
        return None, SEM_GRAVIDADE
    return None, MESMA_COMPRESSAO


def ponta_da_base(
    pontos_por_caso: Mapping[str, Sequence[em.PontoDeEsforco]],
    escolha: str,
    gravidade: Sequence[str] | None = None,
    com_gravidade: Sequence[str] = (),
) -> tuple[str | None, str]:
    """A ponta da base e de onde ela veio (escolhida, automática ou o motivo de não saber)."""
    if escolha in (BASE_INICIO, BASE_FIM):
        return escolha, ORIGEM_ESCOLHIDA
    return base_pelos_esforcos(pontos_por_caso, gravidade, com_gravidade)


def _carga_na_ponta(
    pilar: str, caso: str, pontos: Sequence[em.PontoDeEsforco], base: str
) -> CargaNaBase:
    p = pontos[0] if base == BASE_INICIO else pontos[-1]
    return CargaNaBase(pilar, caso, -p.n + 0.0, p.v1, p.v2, p.m1, p.m2, p.t)


def _bases_pela_soma(
    dados: em.EsforcosDoModelo,
    pontos: Mapping[str, Mapping[str, Sequence[em.PontoDeEsforco]]],
    bases: Mapping[str, str | None],
) -> dict[str, str]:
    """As bases que faltam, pela soma: a combinação de pontas em que as bases de todos os pilares
    somam a reação vertical do modelo em todos os casos. Só devolve a ponta do pilar que é a
    mesma em todas as combinações que fecham."""
    pendentes = [p for p, b in bases.items() if b is None]
    verticais = {
        codigo: em.para_o_plano(caso.reacoes.modelo, dados.eixo_vertical)[2]
        for codigo, caso in dados.casos.items()
        if caso.reacoes is not None
    }
    if not pendentes or len(pendentes) > PILARES_PELA_SOMA or not verticais:
        return {}
    if any(codigo not in pontos[p] for p in bases for codigo in verticais):
        return {}  # pilar sem pontos num caso: a soma não diz nada

    def n_na_ponta(pilar: str, caso: str, base: str) -> float:
        lista = pontos[pilar][caso]
        return -(lista[0] if base == BASE_INICIO else lista[-1]).n

    fixo = {
        caso: sum(n_na_ponta(p, caso, b) for p, b in bases.items() if b is not None)
        for caso in verticais
    }
    fecham: list[tuple[str, ...]] = []
    for combinacao in itertools.product((BASE_INICIO, BASE_FIM), repeat=len(pendentes)):
        if all(
            abs(
                fixo[caso]
                + sum(n_na_ponta(p, caso, b) for p, b in zip(pendentes, combinacao, strict=True))
                - vertical
            )
            <= max(0.02 * abs(vertical), 0.02)
            for caso, vertical in verticais.items()
        ):
            fecham.append(combinacao)
    if not fecham:
        return {}
    return {
        pilar: fecham[0][k]
        for k, pilar in enumerate(pendentes)
        if all(c[k] == fecham[0][k] for c in fecham)
    }


def montar_quadro(dados: em.EsforcosDoModelo) -> QuadroDeFundacoes:
    casos = tuple(dados.casos)
    gravidade = casos_de_gravidade(dados)
    com_gravidade = casos_com_gravidade(dados)
    pontos: dict[str, dict[str, Sequence[em.PontoDeEsforco]]] = {}
    bases: dict[str, str | None] = {}
    origens: dict[str, str] = {}
    ao_contrario: dict[str, str] = {}
    for nome in dados.nomes_dos_membros:
        cfg = dados.membros.get(nome, em.ConfiguracaoDoMembro())
        if cfg.tipo != "Pilar":
            continue
        # Sem pontos num caso (arquivo gravado incompleto), o pilar fica fora desse caso.
        pontos[nome] = {k: c.membros[nome] for k, c in dados.casos.items() if c.membros.get(nome)}
        bases[nome], origens[nome] = ponta_da_base(pontos[nome], cfg.base, gravidade, com_gravidade)
        if origens[nome] == ORIGEM_ESCOLHIDA:
            pelos_esforcos, de_onde = base_pelos_esforcos(pontos[nome], gravidade, com_gravidade)
            if de_onde == ORIGEM_PESO and pelos_esforcos != bases[nome]:
                ao_contrario[nome] = str(pelos_esforcos)
    for nome, pela_soma in _bases_pela_soma(dados, pontos, bases).items():
        bases[nome], origens[nome] = pela_soma, ORIGEM_SOMA
    pilares: list[PilarDoQuadro] = []
    for nome, base in bases.items():
        cfg = dados.membros.get(nome, em.ConfiguracaoDoMembro())
        cargas = (
            tuple(_carga_na_ponta(nome, caso, lista, base) for caso, lista in pontos[nome].items())
            if base is not None
            else ()
        )
        pilares.append(
            PilarDoQuadro(
                nome,
                cfg.perfil,
                cfg.eixo_forte,
                base,
                origens[nome],
                cargas,
                ao_contrario.get(nome),
            )
        )
    return QuadroDeFundacoes(tuple(pilares), casos, tuple(_conferir(dados, pilares)))


def com_as_bases_automaticas(
    dados: em.EsforcosDoModelo, pilares: Sequence[str] | None = None
) -> em.EsforcosDoModelo:
    """Os esforços com a base dos ``pilares`` (ou de todos) de volta em Automática: o programa
    acha a ponta de baixo pelo peso próprio."""
    return em.com_membros(
        dados,
        {
            nome: replace(cfg, base=BASE_AUTOMATICA)
            for nome, cfg in dados.membros.items()
            if cfg.base != BASE_AUTOMATICA and (pilares is None or nome in pilares)
        },
    )


def _conferir(
    dados: em.EsforcosDoModelo, pilares: Sequence[PilarDoQuadro]
) -> list[pc.ItemDeConferencia]:
    itens: list[pc.ItemDeConferencia] = []
    if not pilares:
        return [
            pc.ItemDeConferencia(
                pc.NIVEL_ATENCAO,
                "Nenhuma barra marcada como Pilar na tabela das barras: marque os pilares para "
                "montar o quadro.",
            )
        ]
    de_ponta_cabeca = [p.pilar for p in pilares if p.base_pelo_peso is not None]
    if de_ponta_cabeca:
        itens.append(
            pc.ItemDeConferencia(
                pc.NIVEL_ATENCAO,
                f"A base escolhida na tabela das barras é a ponta de cima em {len(de_ponta_cabeca)} "
                f"pilar(es) — {', '.join(de_ponta_cabeca[:4])}{'…' if len(de_ponta_cabeca) > 4 else ''}"
                ": no peso próprio a compressão cresce para a outra ponta. Volte a coluna Base "
                "(pilar) para Automática.",
            )
        )
    sem_base = [p.pilar for p in pilares if p.base is None]
    if sem_base:
        itens.append(
            pc.ItemDeConferencia(
                pc.NIVEL_ATENCAO,
                f"Escolha a base de {len(sem_base)} pilar(es) na tabela das barras: "
                f"{', '.join(sem_base[:4])}{'…' if len(sem_base) > 4 else ''}.",
            )
        )
    for caso, importado in dados.casos.items():
        if importado.reacoes is None:
            continue
        vertical = em.para_o_plano(importado.reacoes.modelo, dados.eixo_vertical)[2]
        soma = sum(c.n for p in pilares for c in p.cargas if c.caso == caso)
        if sem_base:
            continue
        diferenca = abs(soma - vertical)
        if diferenca <= max(0.02 * abs(vertical), 0.1):
            itens.append(
                pc.ItemDeConferencia(
                    pc.NIVEL_OK,
                    f"{caso}: a soma das bases ({_n(soma)} kN) bate com a reação vertical do modelo "
                    f"({_n(vertical)} kN).",
                )
            )
        else:
            itens.append(
                pc.ItemDeConferencia(
                    pc.NIVEL_ATENCAO,
                    f"{caso}: a soma das bases dos pilares dá {_n(soma)} kN e a reação vertical do "
                    f"modelo, {_n(vertical)} kN — há apoios que não são base de pilar marcado, ou "
                    "alguma base está na ponta errada.",
                )
            )
    return itens


COLUNAS = (
    "Pilar",
    "Perfil",
    "Caso",
    "Ação",
    "N (kN, compressão +)",
    "V1 (kN)",
    "V2 (kN)",
    "M1 (kN·m)",
    "M2 (kN·m)",
    "T (kN·m)",
    "Eixo forte",
    "Base",
)


#: (pilar, caso) → (F, F, M, M) do pilar na fundação nos eixos horizontais do modelo.
NoModelo = Mapping[tuple[str, str], tuple[float, float, float, float]]


def colunas_no_modelo(eixos: tuple[str, str]) -> tuple[str, ...]:
    a, b = eixos
    return (f"F{a} (kN)", f"F{b} (kN)", f"M{a} (kN·m)", f"M{b} (kN·m)")


def colunas(
    no_modelo: NoModelo | None = None, eixos: tuple[str, str] = ("X", "Z")
) -> tuple[str, ...]:
    return (*COLUNAS, *colunas_no_modelo(eixos)) if no_modelo else COLUNAS


def linhas_do_quadro(
    quadro: QuadroDeFundacoes,
    plano: pc.PlanoDeCargas,
    no_modelo: NoModelo | None = None,
) -> list[list[object]]:
    """Uma linha por pilar e caso; com ``no_modelo``, mais as quatro colunas nos eixos do modelo
    (vazias no pilar sem a direção da seção)."""
    linhas: list[list[object]] = []
    for p in quadro.pilares:
        for c in p.cargas:
            acao = plano.acao(c.caso)
            linha: list[object] = [
                p.pilar,
                p.perfil or "—",
                c.caso,
                acao.nome if acao else "—",
                c.n,
                c.v1,
                c.v2,
                c.m1,
                c.m2,
                c.t,
                p.eixo_forte,
                f"{p.base} ({p.origem_da_base})",
            ]
            if no_modelo:
                valores = no_modelo.get((p.pilar, c.caso))
                linha.extend(valores if valores is not None else ("", "", "", ""))
            linhas.append(linha)
    return linhas


COLUNAS_DAS_BASES = ("Pilar", "Base no arquivo", "Como o programa soube", "Situação")
NOTA_DAS_BASES = (
    "A base é a ponta de baixo do pilar na lista de pontos do arquivo de forças. O programa a acha "
    "pelo peso próprio (no PP a compressão cresce para baixo) e nunca por um caso de vento."
)


def linhas_das_bases(quadro: QuadroDeFundacoes) -> list[list[object]]:
    """Uma linha por pilar: a ponta usada como base, de onde ela veio e se está certa."""
    linhas: list[list[object]] = []
    for p in quadro.pilares:
        if p.base is None:
            situacao = "Falta escolher"
        elif p.base_pelo_peso is not None:
            situacao = f"Ponta de cima: pelo peso próprio a base é o {p.base_pelo_peso.lower()}"
        else:
            situacao = "Certo"
        linhas.append([p.pilar, p.base or "—", p.origem_da_base, situacao])
    return linhas


def matriz_de_compressao(quadro: QuadroDeFundacoes) -> tuple[list[str], list[list[object]]]:
    """Uma linha por pilar e uma coluna por caso, com N (compressão positiva)."""
    cabecalho = ["Pilar", *quadro.casos]
    linhas: list[list[object]] = []
    for p in quadro.pilares:
        por_caso = {c.caso: c.n for c in p.cargas}
        linhas.append([p.pilar, *(por_caso.get(caso, "") for caso in quadro.casos)])
    return cabecalho, linhas


def csv_do_quadro(
    quadro: QuadroDeFundacoes,
    plano: pc.PlanoDeCargas,
    no_modelo: NoModelo | None = None,
    eixos: tuple[str, str] = ("X", "Z"),
) -> bytes:
    return pc._csv(colunas(no_modelo, eixos), linhas_do_quadro(quadro, plano, no_modelo))


NOTA_ANGLO = (
    f"{ca.QUADRO_DE_CARGAS_FUNDACOES} Valores característicos de cada caso; as combinações são de "
    "quem projeta a fundação."
)
CONVENCAO = (
    "N = força vertical na fundação, compressão positiva. V1, V2, M1, M2 e T = esforços internos na "
    "seção da base, nos eixos 1 e 2 da seção do SolidWorks (o eixo forte está na coluna Eixo forte)."
)
CONVENCAO_NO_MODELO = (
    "F e M nos eixos do modelo = força e momento que o pilar faz na fundação, nos eixos "
    "horizontais do SolidWorks (vazio no pilar sem a direção da seção sabida)."
)


def xlsx_do_quadro(
    quadro: QuadroDeFundacoes,
    plano: pc.PlanoDeCargas,
    *,
    titulo: str = "",
    no_modelo: NoModelo | None = None,
    eixos: tuple[str, str] = ("X", "Z"),
) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    livro = Workbook()
    leia = livro.active
    assert leia is not None
    leia.title = "Leia-me"
    for texto in (
        f"Quadro de cargas para as fundações — {titulo}" if titulo else "Quadro de cargas",
        "",
        NOTA_ANGLO,
        CONVENCAO,
        *([CONVENCAO_NO_MODELO] if no_modelo else []),
        f"Casos: {', '.join(quadro.casos)}.",
    ):
        leia.append([texto])
    leia["A1"].font = Font(bold=True)
    leia.column_dimensions["A"].width = 130
    fonte = Font(bold=True, color="FFFFFF")
    fundo = PatternFill("solid", fgColor="1F4E8C")
    cabecalho_m, linhas_m = matriz_de_compressao(quadro)
    for nome, cabecalho, linhas in (
        ("Quadro", colunas(no_modelo, eixos), linhas_do_quadro(quadro, plano, no_modelo)),
        ("Compressão por pilar", cabecalho_m, linhas_m),
    ):
        folha = livro.create_sheet(nome)
        folha.append(list(cabecalho))
        for linha in linhas:
            folha.append(list(linha))
        for celula in folha[1]:
            celula.font, celula.fill = fonte, fundo
            celula.alignment = Alignment(wrap_text=True, vertical="center")
        folha.freeze_panes = "B2"
        for indice, coluna in enumerate(folha.iter_cols(min_row=1, max_row=folha.max_row), 1):
            largura = max((len(str(c.value)) for c in coluna if c.value is not None), default=8)
            folha.column_dimensions[get_column_letter(indice)].width = min(max(10, largura + 2), 50)
            for celula in coluna[1:]:
                if isinstance(celula.value, float):
                    celula.number_format = "0.00"
    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()


def registro_do_quadro(
    quadro: QuadroDeFundacoes,
    plano: pc.PlanoDeCargas,
    *,
    contexto: Mapping[str, Any] | None = None,
    responsavel: str = "",
    no_modelo: NoModelo | None = None,
    eixos: tuple[str, str] = ("X", "Z"),
) -> dict[str, Any]:
    cargas = [c for p in quadro.pilares for c in p.cargas]
    maior = max(cargas, key=lambda c: c.n, default=None)
    destaque = (
        f"Cargas características nas bases de {len(quadro.pilares)} pilar(es) para os casos "
        f"{', '.join(quadro.casos)}, sem combinar nem majorar (critério Anglo, item 5.9)."
        + (
            f" Maior compressão: {_n(maior.n)} kN no {maior.pilar} (caso {maior.caso})."
            if maior is not None
            else ""
        )
    )
    tabela = {
        "legenda": "Quadro de cargas para as fundações — valores característicos por caso. "
        + CONVENCAO,
        "cabecalhos": ["Pilar", "Caso", "N (kN)", "V1 (kN)", "V2 (kN)", "M1 (kN·m)", "M2 (kN·m)"],
        "linhas": [
            [c.pilar, c.caso, _n(c.n), _n(c.v1), _n(c.v2), _n(c.m1), _n(c.m2)] for c in cargas
        ],
        "larguras": [2560, 900, 1180, 1180, 1180, 1180, 1180],
        "fonte": 7.0,
    }
    tabelas_no_modelo = []
    if no_modelo:
        a, b = eixos
        tabelas_no_modelo.append(
            {
                "legenda": "Força e momento horizontais do pilar na fundação, nos eixos do modelo "
                f"do SolidWorks ({a} e {b}) — pela direção da seção de cada pilar no Simulation.",
                "cabecalhos": ["Pilar", "Caso", *colunas_no_modelo(eixos)],
                "linhas": [
                    [pilar, caso, *(_n(v) for v in valores)]
                    for (pilar, caso), valores in no_modelo.items()
                ],
                "larguras": [3000, 1100, 1315, 1315, 1315, 1315],
                "fonte": 7.0,
            }
        )
    cabecalho_m, linhas_m = matriz_de_compressao(quadro)
    matriz = {
        "legenda": "Compressão (N, kN) na base de cada pilar, por caso.",
        "cabecalhos": cabecalho_m,
        "linhas": [
            [str(linha[0]), *(_n(v) if isinstance(v, float) else "—" for v in linha[1:])]
            for linha in linhas_m
        ],
    }
    entradas: dict[str, Any] = {
        "casos_do_modelo": ", ".join(quadro.casos),
        "pilares": len(quadro.pilares),
        "pilares_sem_base": len(quadro.pendentes) or None,
    }
    entradas.update(dict(contexto or {}))
    entradas = {k: v for k, v in entradas.items() if v is not None}
    alertas = [i.texto for i in quadro.conferencia if i.nivel != pc.NIVEL_OK]
    return criar_registro_tecnico(
        modulo="Esforços do modelo",
        modulo_id="esforcos_modelo",
        titulo=f"Quadro de cargas para as fundações — {len(quadro.pilares)} pilar(es)",
        status="Calculado",
        resumo=destaque,
        entradas=entradas,
        resultados={
            "destaque_memorial": destaque,
            "tabelas_memorial": [matriz, tabela, *tabelas_no_modelo],
        },
        metodo=(
            "Esforços na seção de base de cada pilar, tirados das forças das vigas de cada estudo "
            "do SolidWorks Simulation (um estudo por caso de carga). "
            + CONVENCAO
            + (" " + CONVENCAO_NO_MODELO if no_modelo else "")
        ),
        premissas=[NOTA_ANGLO],
        alertas=alertas,
        referencias=[f"{ca.REFERENCIA}, item 5.9."],
        conclusao=destaque,
        responsavel=responsavel,
    )


def resumo_numerico(quadro: QuadroDeFundacoes) -> dict[str, float | int | None]:
    cargas = [c for p in quadro.pilares for c in p.cargas]
    return {
        "pilares": len(quadro.pilares),
        "sem_base": len(quadro.pendentes),
        "maior_compressao": max((c.n for c in cargas), default=None),
        "maior_tracao": min((c.n for c in cargas if c.n < 0), default=None),
        "maior_momento": max((math.hypot(c.m1, c.m2) for c in cargas), default=None),
    }
