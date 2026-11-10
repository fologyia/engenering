"""Tratamento automático da leitura do modelo do SolidWorks.

Entre o que fica gravado no projeto — os arquivos como chegaram e a tabela das barras como o
usuário a deixou — e o que as páginas usam, esta camada conserta sozinha o que tem **prova nos
próprios arquivos** e diz o que fez. O que não tem prova fica para o painel "Antes de verificar"
(:mod:`core.diagnostico_do_modelo`), que avisa e ensina a corrigir.

Três destinos para um erro de leitura:

* **tratado, certo** (:data:`CERTO`): a prova está nos arquivos e não depende de opinião. O
  programa usa o valor certo e só lista o que fez, sem pedir nada.
* **tratado, a conferir** (:data:`CONFERIR`): o programa trata, porque a prova é forte, mas o
  tratamento muda os números de um caso — vira um item "Para conferir" no painel.
* **não tratável**: falta um arquivo, o estudo está errado no SolidWorks, dois casos têm o mesmo
  resultado. Só o painel resolve, com os passos.

Os tratamentos, na ordem em que rodam (um depende do anterior):

0. **Escala das reações**: a reação total mil vezes maior ou menor que a soma dos apoios da
   macro (ou, sem eles e no fim, que a soma das bases dos pilares) é o arquivo de reações lido
   com o separador decimal trocado — com poucos números, "7.500" não prova se é 7500 ou 7,5.
1. **Reação total pelos apoios da macro**: sem o arquivo de reações de um caso, a reação total é
   a soma das reações nos apoios (``-apoios.csv``).
2. **Eixo vertical**: no PP só há gravidade; se a reação dele está em outro eixo, para cima, e
   as barras mostram o peso próprio ao longo delas, o eixo vertical gravado está trocado.
3. **Nomes dos ventos**: quando cada vento do estudo é, em direção e valor, um vento do plano com
   outro nome, e a troca fecha entre eles, cada resultado vai para o caso certo.
4. **Gravidade junto num caso** (a conferir): a reação vertical do caso passa do plano exatamente
   pelo peso do PP *e* a normal varia dentro dos elementos de cada pilar como no PP — o estudo
   foi duplicado do PP sem tirar a gravidade. O estudo é linear: o programa desconta o PP ponto
   a ponto.
5. **Tabela das barras**: tipo vazio, perfil que veio só do nome da viga e eixo forte contra a
   seção do modelo. Os comprimentos de flambagem não entram: são escolha de projeto.
6. **Base do pilar**: a base escolhida na ponta que o peso próprio mostra ser a de cima volta
   para a automática.

Nada disso muda o que está gravado. Quando a página grava uma edição feita sobre os dados
tratados, :meth:`ModeloTratado.para_gravar` devolve aos casos recalculados (item 4) os números
do arquivo; os outros tratamentos podem ficar gravados, porque são o valor certo.

Cada tratamento é protegido: se um falha com um dado fora do esperado, o estado volta ao de
antes dele, a falha fica registrada (:mod:`core.diagnostico`) e os outros rodam.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from core import apoios_do_modelo as am
from core import diagnostico_do_modelo as dm
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import quadro_fundacoes as qf

CERTO = "certo"
CONFERIR = "conferir"

T_ESCALA = "escala_das_reacoes"
T_REACOES = "reacoes_pelos_apoios"
T_EIXO = "eixo_vertical"
T_VENTOS = "nomes_dos_ventos"
T_GRAVIDADE = "gravidade_no_caso"
T_TABELA = "tabela_das_barras"
T_BASE = "base_do_pilar"

CODIGO_PP = "PP"
#: O nome do "arquivo" de reações quando a reação total saiu dos apoios da macro.
ARQUIVO_PELOS_APOIOS = "soma dos apoios da macro"
#: A sobra da reação vertical que denuncia a gravidade junto: o peso do PP, até esta diferença.
TOLERANCIA_DA_SOBRA = 0.03
#: A variação da normal dentro dos elementos de um pilar "é a do PP" até esta diferença.
TOLERANCIA_DO_PESO = 0.05
#: Abaixo disto (kN) o PP não serve de prova de nada.
PESO_MINIMO_DO_PP_KN = 0.5


@dataclass(frozen=True)
class Tratamento:
    """Uma correção que o programa fez sozinho na leitura do modelo."""

    codigo: str
    titulo: str
    texto: str  # o que foi feito e a prova
    confianca: str = CERTO
    onde: tuple[str, ...] = ()  # casos ou barras


@dataclass(frozen=True)
class ModeloTratado:
    """O modelo como o programa o usa (``dados``, ``apoios``) e como está gravado (``bruto``)."""

    bruto: em.EsforcosDoModelo
    dados: em.EsforcosDoModelo
    apoios_brutos: am.ApoiosDoModelo
    apoios: am.ApoiosDoModelo
    geometria: ld.GeometriaDoModelo
    tratamentos: tuple[Tratamento, ...] = ()
    #: tratamentos que falharam e ficaram sem aplicar (nome e referência da ocorrência)
    falhas: tuple[str, ...] = ()
    #: código gravado → código usado (os ventos com o nome trocado)
    renomeados: Mapping[str, str] = field(default_factory=dict)
    #: casos (código usado) com os números mudados só na memória
    recalculados: frozenset[str] = frozenset()

    @property
    def certos(self) -> tuple[Tratamento, ...]:
        return tuple(t for t in self.tratamentos if t.confianca == CERTO)

    @property
    def a_conferir(self) -> tuple[Tratamento, ...]:
        return tuple(t for t in self.tratamentos if t.confianca == CONFERIR)

    def tratou(self, codigo: str) -> bool:
        return any(t.codigo == codigo for t in self.tratamentos)

    def para_gravar(self, novos: em.EsforcosDoModelo) -> em.EsforcosDoModelo:
        """O que gravar depois de uma edição feita sobre os dados tratados.

        Os casos recalculados só na memória (a gravidade descontada) voltam a ter os números do
        arquivo, a não ser que a edição tenha trocado o arquivo do caso. O resto fica como está:
        eixo vertical, nomes dos ventos, tabela das barras e a reação pelos apoios são o valor
        certo e podem ficar gravados."""
        if not self.recalculados:
            return novos
        de_volta = {novo: antigo for antigo, novo in self.renomeados.items()}
        casos = dict(novos.casos)
        for codigo in self.recalculados:
            atual, tratado = casos.get(codigo), self.dados.casos.get(codigo)
            original = self.bruto.casos.get(de_volta.get(codigo, codigo))
            if atual is None or tratado is None or original is None:
                continue
            if atual.membros is not tratado.membros:
                continue  # chegou um arquivo de forças novo para o caso: vale o novo
            do_arquivo = replace(
                atual,
                membros=original.membros,
                arquivo=original.arquivo,
                assinatura=original.assinatura,
            )
            if atual.reacoes is tratado.reacoes:  # as reações também não foram trocadas
                do_arquivo = replace(
                    do_arquivo,
                    reacoes=original.reacoes,
                    arquivo_reacoes=original.arquivo_reacoes,
                )
            casos[codigo] = do_arquivo
        return replace(novos, casos=casos)

    @property
    def apoios_para_gravar(self) -> am.ApoiosDoModelo | None:
        """Os apoios a gravar junto de :meth:`para_gravar`: com os casos renomeados como os
        esforços. ``None`` quando nada muda no que está gravado."""
        if not self.renomeados:
            return None
        return am.trocar_codigos(self.apoios_brutos, self.renomeados)


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _lista(itens: Sequence[str], limite: int = 6) -> str:
    itens = list(itens)
    if len(itens) > limite:
        return ", ".join(itens[:limite]) + f" e mais {len(itens) - limite}"
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


# ---------------------------------------------------------------------------------------------
# O estado que os tratamentos mudam
# ---------------------------------------------------------------------------------------------
@dataclass
class _Estado:
    dados: em.EsforcosDoModelo
    apoios: am.ApoiosDoModelo
    plano: pc.PlanoDeCargas
    geometria: ld.GeometriaDoModelo
    tratamentos: list[Tratamento] = field(default_factory=list)
    renomeados: dict[str, str] = field(default_factory=dict)
    recalculados: set[str] = field(default_factory=set)

    def copia(self) -> tuple[Any, ...]:
        return (
            self.dados,
            self.apoios,
            list(self.tratamentos),
            dict(self.renomeados),
            set(self.recalculados),
        )

    def restaurar(self, copia: tuple[Any, ...]) -> None:
        self.dados, self.apoios, self.tratamentos, self.renomeados, self.recalculados = copia


def _pp(dados: em.EsforcosDoModelo) -> em.CasoImportado | None:
    return next((c for k, c in dados.casos.items() if k.strip().upper() == CODIGO_PP), None)


def _pesos_ao_longo(caso: em.CasoImportado) -> dict[str, float]:
    """Barra → variação da normal dentro dos elementos (kN), só onde ela é clara: os pilares e
    as barras inclinadas num caso com gravidade."""
    saida: dict[str, float] = {}
    for barra, pontos in caso.membros.items():
        variacao, limiar = qf.variacao_dentro_dos_elementos(pontos)
        if abs(variacao) > limiar:
            saida[barra] = variacao
    return saida


# ---------------------------------------------------------------------------------------------
# 0. Escala das reações
# ---------------------------------------------------------------------------------------------
def _fator_de_mil(lido: Sequence[float], certo: Sequence[float]) -> float | None:
    """1000 se o vetor lido é o certo vezes mil, 0,001 se é o certo dividido por mil; ``None``
    se não é nenhum dos dois (ou se o certo é pequeno demais para provar)."""
    tamanho = math.sqrt(sum(v * v for v in certo))
    if tamanho <= 0.005:
        return None
    for fator in (1000.0, 0.001):
        diferenca = math.sqrt(sum((a - fator * b) ** 2 for a, b in zip(lido, certo, strict=True)))
        if diferenca <= 0.01 * fator * tamanho:
            return fator
    return None


def _reacoes_na_escala(reacoes: em.Reacoes, fator: float) -> em.Reacoes:
    def escala(v: tuple[float, float, float] | None) -> tuple[float, float, float] | None:
        return None if v is None else (v[0] / fator, v[1] / fator, v[2] / fator)

    modelo = escala(reacoes.modelo)
    assert modelo is not None
    return em.Reacoes(modelo, escala(reacoes.selecao), escala(reacoes.momento_modelo))


def _texto_da_escala(codigos: Sequence[str], contra: str) -> Tratamento:
    return Tratamento(
        T_ESCALA,
        "Reação total lida com o separador decimal errado",
        f"A reação total de {_lista(codigos)} saiu mil vezes maior ou menor que {contra}: no "
        "arquivo de reações, com poucos números, o ponto e a vírgula se confundem (“7.500” é "
        "7500 ou 7,5). O programa usou o valor que fecha.",
        CERTO,
        tuple(codigos),
    )


def _escala_pelos_apoios(e: _Estado) -> None:
    """A reação total contra a soma dos apoios da macro: se diferem de exatamente mil vezes, o
    arquivo de reações foi lido com o separador decimal trocado."""
    casos = dict(e.dados.casos)
    feitos: list[str] = []
    for codigo, caso in casos.items():
        apoios = e.apoios.casos.get(codigo)
        if caso.reacoes is None or apoios is None or not apoios.nos:
            continue
        soma = [sum(no.forca_N[k] for no in apoios.nos) / 1e3 for k in range(3)]
        fator = _fator_de_mil(caso.reacoes.modelo, soma)
        if fator is not None:
            casos[codigo] = replace(caso, reacoes=_reacoes_na_escala(caso.reacoes, fator))
            feitos.append(codigo)
    if feitos:
        e.dados = replace(e.dados, casos=casos)
        e.tratamentos.append(_texto_da_escala(feitos, "a soma das reações nos apoios da macro"))


def _escala_pelas_bases(e: _Estado) -> None:
    """Sem os apoios da macro: a reação vertical contra a soma das bases dos pilares."""
    quadro = qf.montar_quadro(e.dados)
    if not quadro.pilares or quadro.pendentes:
        return
    casos = dict(e.dados.casos)
    feitos: list[str] = []
    for codigo, caso in casos.items():
        if caso.reacoes is None or codigo in e.apoios.casos:
            continue
        soma = sum(c.n for p in quadro.pilares for c in p.cargas if c.caso == codigo)
        vertical = em.para_o_plano(caso.reacoes.modelo, e.dados.eixo_vertical)[2]
        fator = _fator_de_mil([vertical], [soma]) if abs(soma) > 0.1 else None
        if fator is not None:
            casos[codigo] = replace(caso, reacoes=_reacoes_na_escala(caso.reacoes, fator))
            feitos.append(codigo)
    if feitos:
        e.dados = replace(e.dados, casos=casos)
        e.tratamentos.append(_texto_da_escala(feitos, "a soma das bases dos pilares"))


# ---------------------------------------------------------------------------------------------
# 1. Reação total pelos apoios da macro
# ---------------------------------------------------------------------------------------------
def _reacoes_pelos_apoios(e: _Estado) -> None:
    feitos: list[str] = []
    dados = e.dados
    for codigo, caso in dados.casos.items():
        apoios = e.apoios.casos.get(codigo)
        if caso.reacoes is not None or apoios is None or not apoios.nos:
            continue
        soma = tuple(sum(no.forca_N[k] for no in apoios.nos) / 1e3 for k in range(3))
        if not all(math.isfinite(v) for v in soma):
            continue
        dados = em.com_reacoes(
            dados, codigo, em.Reacoes(modelo=(soma[0], soma[1], soma[2])), ARQUIVO_PELOS_APOIOS
        )
        feitos.append(codigo)
    if not feitos:
        return
    e.dados = dados
    e.tratamentos.append(
        Tratamento(
            T_REACOES,
            "Reação total pelos apoios da macro",
            f"Faltava o arquivo de reações de {_lista(feitos)}. A reação total do caso é a soma "
            "das reações nos apoios (arquivos -apoios.csv da macro), e o programa usou essa soma.",
            CERTO,
            tuple(feitos),
        )
    )


# ---------------------------------------------------------------------------------------------
# 2. Eixo vertical
# ---------------------------------------------------------------------------------------------
def _eixo_da_reacao(caso: em.CasoImportado | None) -> tuple[str, float] | None:
    """O eixo que leva quase toda a reação do caso e a componente nele (kN, com o sinal)."""
    if caso is None or caso.reacoes is None:
        return None
    modelo = caso.reacoes.modelo
    componentes = [abs(v) for v in modelo]
    total = math.hypot(*componentes)
    dominante = componentes.index(max(componentes))
    if total <= 0.01 or componentes[dominante] <= 0.9 * total:
        return None
    return "XYZ"[dominante], modelo[dominante]


def eixo_vertical_provado(
    dados: em.EsforcosDoModelo, plano: pc.PlanoDeCargas | None = None
) -> str | None:
    """O eixo vertical que os arquivos provam ("Y" ou "Z"), ou ``None`` sem prova.

    A prova é o PP, com quatro condições — para um arquivo de vento salvo com o nome do PP não
    virar o eixo do modelo:

    1. quase toda a reação do PP está num eixo só;
    2. ela aponta para cima (a reação segura o peso);
    3. o PP tem a assinatura do peso próprio: a normal varia dentro dos elementos de alguma barra
       (um vento aplicado nos nós não faz isso);
    4. nenhum caso que o plano diz ser só de carga vertical tem a reação em outro eixo.
    """
    pp = _pp(dados)
    do_pp = _eixo_da_reacao(pp)
    if pp is None or do_pp is None:
        return None
    eixo, componente = do_pp
    if eixo not in ("Y", "Z") or componente <= 0 or not _pesos_ao_longo(pp):
        return None
    if plano is not None:
        for codigo, caso in dados.casos.items():
            acao = plano.acao(codigo)
            if caso is pp or acao is None or not acao.cargas or not em._so_vertical(acao):
                continue
            do_caso = _eixo_da_reacao(caso)
            if do_caso is not None and do_caso[0] != eixo:
                return None
    return eixo


def _eixo_vertical(e: _Estado) -> None:
    eixo = eixo_vertical_provado(e.dados, e.plano)
    gravado = e.dados.eixo_vertical
    if eixo is None or eixo == gravado:
        return
    e.dados = replace(e.dados, eixo_vertical=eixo)
    e.tratamentos.append(
        Tratamento(
            T_EIXO,
            "Eixo vertical do modelo",
            f"O projeto estava com {gravado} para cima, mas no PP (só gravidade) a reação "
            f"aparece em {eixo}, para cima, e as barras mostram o peso próprio ao longo delas. O "
            f"programa usou {eixo} para cima.",
            CERTO,
        )
    )


# ---------------------------------------------------------------------------------------------
# 3. Nomes dos ventos
# ---------------------------------------------------------------------------------------------
def _nomes_dos_ventos(e: _Estado) -> None:
    mapa = em.mapa_de_nomes_dos_ventos(e.dados, e.plano)
    if not mapa:
        return
    e.dados = em.trocar_codigos(e.dados, mapa)
    e.apoios = am.trocar_codigos(e.apoios, mapa)
    e.renomeados.update(mapa)
    trocas = _lista([f"{antigo} → {novo}" for antigo, novo in mapa.items()])
    e.tratamentos.append(
        Tratamento(
            T_VENTOS,
            "Casos de vento com o nome trocado",
            f"Cada vento enviado é, em direção e valor, um vento do plano com outro nome, e a "
            f"troca fecha entre eles ({trocas}). O programa usou cada resultado no caso que ele é "
            "de verdade — forças, reações e apoios. No SolidWorks os nomes continuam trocados: "
            "renomeie lá para as próximas vezes.",
            CERTO,
            tuple(mapa),
        )
    )


# ---------------------------------------------------------------------------------------------
# 4. Gravidade junto num caso
# ---------------------------------------------------------------------------------------------
def _mesma_malha(a: em.CasoImportado, b: em.CasoImportado) -> bool:
    if set(a.membros) != set(b.membros):
        return False
    return all(
        [p.chave for p in a.membros[barra]] == [p.chave for p in b.membros[barra]]
        for barra in a.membros
    )


def _menos(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _caso_sem_o_pp(caso: em.CasoImportado, pp: em.CasoImportado) -> em.CasoImportado:
    membros = {
        barra: tuple(
            em.PontoDeEsforco(
                p.elemento, p.fim, *(x - y for x, y in zip(p.vetor(), q.vetor(), strict=True))
            )
            for p, q in zip(pontos, pp.membros[barra], strict=True)
        )
        for barra, pontos in caso.membros.items()
    }
    assert caso.reacoes is not None and pp.reacoes is not None  # conferido por quem chama
    r, g = caso.reacoes, pp.reacoes
    reacoes = em.Reacoes(
        modelo=_menos(r.modelo, g.modelo),
        selecao=_menos(r.selecao, g.selecao) if r.selecao and g.selecao else None,
        momento_modelo=(
            _menos(r.momento_modelo, g.momento_modelo)
            if r.momento_modelo and g.momento_modelo
            else None
        ),
    )
    return replace(caso, membros=membros, reacoes=reacoes)


def _apoios_sem_o_pp(caso: am.ApoiosDoCaso, pp: am.ApoiosDoCaso) -> am.ApoiosDoCaso | None:
    """Os apoios do caso menos os do PP, nó a nó; ``None`` se os nós não são os mesmos."""
    do_pp = {no.no: no for no in pp.nos}
    if len(do_pp) != len(pp.nos) or {no.no for no in caso.nos} != set(do_pp):
        return None
    nos = tuple(
        replace(
            no,
            forca_N=_menos(no.forca_N, do_pp[no.no].forca_N),
            momento_Nm=_menos(no.momento_Nm, do_pp[no.no].momento_Nm),
        )
        for no in caso.nos
    )
    fixacoes_do_pp = dict(pp.por_fixacao)
    por_fixacao = (
        tuple(
            (nome, tuple(x - y for x, y in zip(valores, fixacoes_do_pp[nome], strict=True)))
            for nome, valores in caso.por_fixacao
        )
        if {nome for nome, _ in caso.por_fixacao} == set(fixacoes_do_pp)
        and all(len(v) == len(fixacoes_do_pp[n]) for n, v in caso.por_fixacao)
        else ()
    )
    return replace(caso, nos=nos, por_fixacao=por_fixacao)


def casos_com_a_gravidade_junto(dados: em.EsforcosDoModelo, plano: pc.PlanoDeCargas) -> list[str]:
    """Os casos que vieram com a gravidade do PP junto, com as duas provas:

    1. a reação vertical passa do que o plano manda exatamente pelo peso do PP (3 %);
    2. dentro dos elementos de cada pilar a normal varia como no PP (5 %) — a assinatura do peso
       próprio, que nenhuma carga do caso imita.

    Só entram os casos do plano com a carga vertical esperada sabida e com a mesma malha do PP.
    """
    pp = _pp(dados)
    if pp is None or pp.reacoes is None:
        return []
    peso = em.para_o_plano(pp.reacoes.modelo, dados.eixo_vertical)[2]
    assinatura = _pesos_ao_longo(pp)
    if peso <= PESO_MINIMO_DO_PP_KN or not assinatura:
        return []
    achados: list[str] = []
    for codigo, caso in dados.casos.items():
        if caso is pp or caso.reacoes is None:
            continue
        acao = plano.acao(codigo)
        if acao is None:
            continue
        esperado = em.total_esperado(acao)
        if esperado is None and acao.cargas:
            continue  # carga por área ou distribuída sem comprimento: não dá para separar
        vertical = em.para_o_plano(caso.reacoes.modelo, dados.eixo_vertical)[2]
        sobra = vertical - (-esperado[2] if esperado is not None else 0.0)
        if abs(sobra - peso) > TOLERANCIA_DA_SOBRA * peso or not _mesma_malha(caso, pp):
            continue
        do_caso = {
            barra: qf.variacao_dentro_dos_elementos(caso.membros[barra])[0] for barra in assinatura
        }
        if all(
            abs(do_caso[barra] - variacao) <= max(TOLERANCIA_DO_PESO * abs(variacao), 0.002)
            for barra, variacao in assinatura.items()
        ):
            achados.append(codigo)
    return achados


def _gravidade_no_caso(e: _Estado) -> None:
    pp = _pp(e.dados)
    codigos = casos_com_a_gravidade_junto(e.dados, e.plano)
    if pp is None or pp.reacoes is None or not codigos:
        return
    peso = em.para_o_plano(pp.reacoes.modelo, e.dados.eixo_vertical)[2]
    casos = dict(e.dados.casos)
    apoios = dict(e.apoios.casos)
    apoios_do_pp = next((a for k, a in apoios.items() if k.strip().upper() == CODIGO_PP), None)
    sem_apoios: list[str] = []
    for codigo in codigos:
        casos[codigo] = _caso_sem_o_pp(casos[codigo], pp)
        if codigo in apoios:
            novos = _apoios_sem_o_pp(apoios[codigo], apoios_do_pp) if apoios_do_pp else None
            if novos is None:
                del apoios[codigo]  # sem como descontar: o caso sai pela base dos pilares
                sem_apoios.append(codigo)
            else:
                apoios[codigo] = novos
    e.dados = replace(e.dados, casos=casos)
    e.apoios = replace(e.apoios, casos=apoios)
    e.recalculados.update(codigos)
    e.tratamentos.append(
        Tratamento(
            T_GRAVIDADE,
            f"{_lista(codigos)}: a gravidade veio junto e foi descontada",
            f"A reação vertical de {_lista(codigos)} passa do que o plano manda exatamente pelo "
            f"peso do PP ({_n(peso)} kN), e dentro dos elementos de cada pilar a normal varia "
            "como no PP: o estudo foi duplicado do PP sem excluir a gravidade. Como o estudo é "
            "linear, o programa descontou o PP ponto a ponto, nas forças, nas reações"
            + (
                " e nos apoios"
                if not sem_apoios
                else f" (os apoios de {_lista(sem_apoios)} não têm os mesmos nós do PP e ficaram "
                "de fora: o caso sai pela base dos pilares)"
            )
            + ". O que está gravado não mudou. Confira; para não depender disso, exclua a "
            "gravidade do estudo no SolidWorks, rode de novo e envie os arquivos.",
            CONFERIR,
            tuple(codigos),
        )
    )


# ---------------------------------------------------------------------------------------------
# 5. Tabela das barras
# ---------------------------------------------------------------------------------------------
def _tabela_das_barras(e: _Estado) -> None:
    leituras = ld.ler_barras(e.dados, e.geometria, e.plano)
    sugerido, _ = ld.aplicar_sugestoes(e.dados, leituras)
    novos: dict[str, em.ConfiguracaoDoMembro] = {}
    tipos: list[str] = []
    perfis: list[str] = []
    eixos: list[str] = []
    for leitura in leituras:
        atual = e.dados.membros.get(leitura.barra, em.ConfiguracaoDoMembro())
        proposto = sugerido.membros.get(leitura.barra, atual)
        # Os comprimentos de flambagem são escolha de projeto: ficam com o botão das sugestões.
        novo = replace(
            atual, tipo=proposto.tipo, perfil=proposto.perfil, eixo_forte=proposto.eixo_forte
        )
        if novo == atual:
            continue
        novos[leitura.barra] = novo
        if novo.tipo != atual.tipo:
            tipos.append(leitura.barra)
        if novo.perfil != atual.perfil:
            perfis.append(leitura.barra)
        if novo.eixo_forte != atual.eixo_forte and leitura.origem_do_eixo in ld.EIXOS_CERTOS:
            eixos.append(leitura.barra)
    if not novos:
        return
    e.dados = em.com_membros(e.dados, novos)
    com_esqueleto = bool(e.geometria.corpos)
    if tipos:
        e.tratamentos.append(
            Tratamento(
                T_TABELA,
                "Tipo das barras",
                f"{len(tipos)} barra(s) estavam sem tipo na tabela ({_lista(tipos, 4)}). O "
                "programa usou o da "
                + (
                    "posição no esqueleto"
                    if com_esqueleto
                    else "leitura dos esforços no peso próprio"
                )
                + " (vertical = pilar, horizontal = viga, inclinada = contraventamento). Para "
                "mudar, escolha o tipo na tabela das barras.",
                CERTO,
                tuple(tipos),
            )
        )
    if perfis:
        e.tratamentos.append(
            Tratamento(
                T_TABELA,
                "Perfil das barras",
                f"O perfil de {len(perfis)} barra(s) estava vazio ou vinha só do nome da viga "
                f"({_lista(perfis, 4)}). O programa usou "
                + (
                    "o do modelo (lista de corte conferida pela área da seção), que é a seção "
                    "que a análise usou."
                    if com_esqueleto
                    else "o que o nome da viga indica."
                ),
                CERTO,
                tuple(perfis),
            )
        )
    if eixos:
        e.tratamentos.append(
            Tratamento(
                T_TABELA,
                "Eixo forte das barras",
                f"Em {len(eixos)} barra(s) o eixo forte da tabela era o outro momento "
                f"({_lista(eixos, 4)}). Pela seção do modelo, o Simulation põe a direção 1 na "
                "aresta reta mais longa — ao longo da alma, o M₂ é o do eixo forte; ao longo da "
                "mesa, o M₁. O programa usou o momento certo.",
                CERTO,
                tuple(eixos),
            )
        )


# ---------------------------------------------------------------------------------------------
# 6. Base do pilar
# ---------------------------------------------------------------------------------------------
def _base_do_pilar(e: _Estado) -> None:
    virados = [p.pilar for p in qf.montar_quadro(e.dados).de_ponta_cabeca]
    if not virados:
        return
    e.dados = qf.com_as_bases_automaticas(e.dados, virados)
    e.tratamentos.append(
        Tratamento(
            T_BASE,
            "Base do pilar escolhida na ponta de cima",
            f"Na tabela das barras, a base de {_lista(virados, 4)} estava escolhida na ponta que "
            "é a de cima: no peso próprio a compressão do pilar cresce para a outra ponta. O "
            "programa usou a ponta de baixo.",
            CERTO,
            tuple(virados),
        )
    )


#: Os tratamentos, na ordem em que rodam.
TRATAMENTOS: tuple[tuple[str, Callable[[_Estado], None]], ...] = (
    ("escala das reações pelos apoios", _escala_pelos_apoios),
    ("reação total pelos apoios", _reacoes_pelos_apoios),
    ("eixo vertical", _eixo_vertical),
    ("nomes dos ventos", _nomes_dos_ventos),
    ("gravidade junto num caso", _gravidade_no_caso),
    ("tabela das barras", _tabela_das_barras),
    ("base do pilar", _base_do_pilar),
    ("escala das reações pelas bases", _escala_pelas_bases),
)


# ---------------------------------------------------------------------------------------------
# O conjunto
# ---------------------------------------------------------------------------------------------
def tratar(
    dados: em.EsforcosDoModelo,
    apoios: am.ApoiosDoModelo | None = None,
    plano: pc.PlanoDeCargas | None = None,
    geometria: ld.GeometriaDoModelo | None = None,
) -> ModeloTratado:
    """O modelo tratado: o que o programa usa, o que ele consertou sozinho e o que falhou."""
    apoios = apoios or am.ApoiosDoModelo()
    geometria = geometria or ld.GeometriaDoModelo()
    if not dados.casos:
        return ModeloTratado(dados, dados, apoios, apoios, geometria)
    estado = _Estado(dados, apoios, plano or pc.PlanoDeCargas(), geometria)
    falhas: list[str] = []
    for nome, passo in TRATAMENTOS:
        copia = estado.copia()
        try:
            passo(estado)
        except Exception as erro:
            from core import diagnostico as dg

            if dg.levantar_erros():
                raise
            estado.restaurar(copia)
            ocorrencia = dg.ocorrencia_de_falha(
                f"Esforços do modelo › Tratamento automático › {nome}", erro
            )
            dg.gravar(ocorrencia)
            falhas.append(f"{nome} (ref. {ocorrencia.referencia})")
    return ModeloTratado(
        dados,
        estado.dados,
        apoios,
        estado.apoios,
        geometria,
        tuple(estado.tratamentos),
        tuple(falhas),
        dict(estado.renomeados),
        frozenset(estado.recalculados),
    )


def do_projeto(projeto: Mapping[str, Any] | None) -> ModeloTratado:
    """O modelo tratado do projeto gravado: o ponto de entrada das páginas do SolidWorks."""
    projeto = projeto or {}
    return tratar(
        em.esforcos_do_projeto(projeto),
        am.do_projeto(projeto),
        pc.plano_do_projeto(projeto),
        ld.geometria_do_projeto(projeto),
    )


def achados(tratado: ModeloTratado) -> list[dm.Achado]:
    """O que do tratamento vai para o painel "Antes de verificar": os tratamentos a conferir e
    os que falharam. Os certos não viram achado (ficam na lista "O programa tratou sozinho")."""
    saida = [
        dm.Achado(
            dm.NIVEL_ATENCAO,
            t.titulo,
            t.texto,
            detalhe={"tratamento": t.codigo, "onde": list(t.onde)},
        )
        for t in tratado.a_conferir
    ]
    if tratado.falhas:
        saida.append(
            dm.Achado(
                dm.NIVEL_ATENCAO,
                "Não deu para tratar sozinho: " + _lista(list(tratado.falhas)),
                "Um dado fora do esperado parou esse tratamento automático; os outros rodaram "
                "normalmente. O que ele trataria aparece no painel como item para corrigir, se "
                "for o caso.",
                (
                    "Envie de novo os arquivos do SolidWorks, sem editar, e clique em Gravar no "
                    "projeto.",
                    "Se continuar, mande a referência para corrigir o programa.",
                ),
                detalhe={"falhas": list(tratado.falhas)},
            )
        )
    return saida


def resumo(tratado: ModeloTratado) -> str:
    """Uma frase para as outras páginas: quantos pontos o programa tratou sozinho."""
    if not tratado.tratamentos:
        return ""
    quantos = len(tratado.tratamentos)
    return (
        f"O programa tratou sozinho {quantos} ponto(s) da leitura do modelo: "
        + "; ".join(dict.fromkeys(t.titulo for t in tratado.tratamentos))
        + ". O detalhe está em Esforços do modelo, no painel “Antes de verificar”."
    )
