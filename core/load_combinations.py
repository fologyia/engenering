"""Combinações de ações por estados-limite (NBR 8681 e NBR 8800, 4.8.7 do Projeto de 2024).

Dois modos, sobre as mesmas ações:

* **lista explícita** (:func:`gerar_combinacoes`): cada combinação com a ação variável principal, as
  acompanhantes e os fatores escritos — o que vai para a tabela e para o memorial;
* **envoltória rigorosa por esforço** (:func:`extremo` e :func:`envoltoria`): para cada esforço, o
  maior e o menor valor de cálculo, aplicando as regras da norma que a lista explícita não consegue
  aplicar a vários esforços ao mesmo tempo — ação variável favorável fica de fora ("ações variáveis
  e excepcionais favoráveis à segurança não podem ser incluídas nas combinações", nota a da
  Tabela 1), cada permanente entra com o γ desfavorável ou com o favorável conforme o sinal do seu
  efeito, e ações do mesmo **grupo exclusivo** (vento a 0°, 90°, 180° e 270°; posições alternativas
  de uma sobrecarga) nunca atuam juntas.

Estados-limite cobertos (4.8.7.2 e 4.8.7.3):

* ELU normal: ``F_d = Σγ_g·F_G + γ_q1·F_Q1 + Σγ_qj·ψ_0j·F_Qj``;
* ELU especial ou de construção: mesma forma, com os γ da linha "especiais ou de construção" da
  Tabela 1 e ``ψ_0,ef`` (= ψ_0, ou ψ_2 se a ação especial for de curtíssima duração);
* ELU excepcional: ``F_d = Σγ_g·F_G + F_Q,exc + Σγ_qj·ψ_0j,ef·F_Qj`` (ψ_0,ef = ψ_2);
* ELS rara: ``ΣF_G + F_Q1 + Σψ_1j·F_Qj``; frequente: ``ΣF_G + ψ_1·F_Q1 + Σψ_2j·F_Qj``;
  quase permanente: ``ΣF_G + Σψ_2j·F_Qj``.

Os esforços de cada ação são os valores característicos. ``n_kN``, ``v_kN`` e ``m_kNm`` atendem às
telas que trabalham com N, V e M; ``efeitos`` aceita qualquer outro esforço com nome (a força numa
diagonal, o cortante de um andar...). Um esforço listado em ``efeitos_reversiveis`` pode ter
qualquer sinal (a força nocional das imperfeições, por exemplo): entra sempre no sentido
desfavorável.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

TIPO_PERMANENTE = "Permanente"
TIPO_VARIAVEL = "Variável"
TIPO_EXCEPCIONAL = "Excepcional"
TIPOS_DE_ACAO = (TIPO_PERMANENTE, TIPO_VARIAVEL, TIPO_EXCEPCIONAL)

ELU_NORMAL = "ELU normal"
ELU_ESPECIAL = "ELU especial ou de construção"
ELU_EXCEPCIONAL = "ELU excepcional"
ELS_RARA = "ELS rara"
ELS_FREQUENTE = "ELS frequente"
ELS_QUASE_PERMANENTE = "ELS quase permanente"
COMBINACOES_ULTIMAS = (ELU_NORMAL, ELU_ESPECIAL, ELU_EXCEPCIONAL)
COMBINACOES_DE_SERVICO = (ELS_RARA, ELS_FREQUENTE, ELS_QUASE_PERMANENTE)
TODOS_OS_ESTADOS = COMBINACOES_ULTIMAS + COMBINACOES_DE_SERVICO
ESTADOS_PADRAO = (ELU_NORMAL, ELS_RARA, ELS_FREQUENTE, ELS_QUASE_PERMANENTE)

#: Número máximo de combinações explícitas antes de pedir que as ações sejam agrupadas.
LIMITE_DE_COMBINACOES = 5000

_EFEITOS_BASICOS = {"N": "n_kN", "V": "v_kN", "M": "m_kNm"}


@dataclass(frozen=True)
class AcaoEstrutural:
    nome: str
    tipo: str
    n_kN: float
    v_kN: float
    m_kNm: float
    gamma: float
    psi0: float = 1.0
    psi1: float = 1.0
    psi2: float = 1.0
    # γ da ação permanente quando ela ALIVIA o efeito (NBR 8681: 1,0). Só com ele a combinação
    # "permanentes favoráveis" é gerada — é a que governa vento de sucção e tombamento.
    gamma_favoravel: float | None = None
    categoria: str = ""
    #: Ações com o mesmo grupo (não vazio) nunca atuam juntas na mesma combinação.
    grupo: str = ""
    #: γ das combinações especiais ou de construção; ``None`` usa o das normais (a favor da
    #: segurança).
    gamma_especial: float | None = None
    #: γ das combinações excepcionais; ``None`` usa 1,0 nas variáveis e o especial (ou o normal)
    #: nas permanentes.
    gamma_excepcional: float | None = None
    #: Esforços com nome além de N, V e M (valores característicos).
    efeitos: Mapping[str, float] = field(default_factory=dict)
    #: Esforços cujo sinal é livre (entram sempre no sentido desfavorável).
    efeitos_reversiveis: frozenset[str] = frozenset()

    def valor(self, efeito: str) -> float:
        """Valor característico do esforço ``efeito`` ("N", "V", "M" ou um nome de ``efeitos``)."""
        if efeito in _EFEITOS_BASICOS:
            return float(getattr(self, _EFEITOS_BASICOS[efeito]))
        return float(self.efeitos.get(efeito, 0.0))


@dataclass(frozen=True)
class CategoriaAcao:
    """Coeficientes de ponderação e de combinação de uma categoria de ação."""

    rotulo: str
    tipo: str
    gamma: float
    gamma_favoravel: float | None
    psi0: float
    psi1: float
    psi2: float
    referencia: str
    gamma_especial: float | None = None
    gamma_excepcional: float | None = None


def _permanente(
    rotulo: str, normal: float, especial: float, excepcional: float, referencia: str
) -> CategoriaAcao:
    return CategoriaAcao(
        rotulo, TIPO_PERMANENTE, normal, 1.00, 1.0, 1.0, 1.0, referencia, especial, excepcional
    )


def _variavel(
    rotulo: str,
    normal: float,
    especial: float,
    psis: tuple[float, float, float],
    referencia: str,
) -> CategoriaAcao:
    return CategoriaAcao(
        rotulo, TIPO_VARIAVEL, normal, None, psis[0], psis[1], psis[2], referencia, especial, 1.00
    )


# Tabelas 1 e 2 da NBR 8800 (combinações normais, especiais ou de construção e excepcionais), que
# remetem à NBR 8681. As permanentes trazem o γ favorável (1,0); as variáveis, os fatores ψ. Duas
# categorias vêm da revisão de 2024 — equipamentos com 1,25, junto com a estrutura de aço, e a
# sobrecarga de cobertura na linha de bibliotecas e depósitos (ψ0 = 0,8) — e estão com a edição no
# nome para a escolha ser consciente.
CATEGORIAS_NBR8800: tuple[CategoriaAcao, ...] = (
    _permanente("Peso próprio de estrutura metálica", 1.25, 1.15, 1.10, "NBR 8800 Tab. 1"),
    _permanente("Peso próprio de estrutura pré-moldada", 1.30, 1.20, 1.15, "NBR 8800 Tab. 1"),
    _permanente("Peso próprio de estrutura moldada no local", 1.35, 1.25, 1.15, "NBR 8800 Tab. 1"),
    _permanente(
        "Elementos construtivos industrializados (grades, pisos, guarda-corpos)",
        1.35,
        1.25,
        1.15,
        "NBR 8800 Tab. 1",
    ),
    _permanente(
        "Elementos construtivos industrializados com adições in loco",
        1.40,
        1.30,
        1.20,
        "NBR 8800 Tab. 1",
    ),
    _permanente(
        "Elementos construtivos em geral e equipamentos", 1.50, 1.40, 1.30, "NBR 8800 Tab. 1"
    ),
    _variavel(
        "Sobrecarga de uso — sem predominância de equipamentos fixos nem de pessoas",
        1.50,
        1.30,
        (0.5, 0.4, 0.3),
        "NBR 8800 Tab. 1 e 2",
    ),
    _variavel(
        "Sobrecarga de uso — predominância de equipamentos fixos ou concentração de pessoas",
        1.50,
        1.30,
        (0.7, 0.6, 0.4),
        "NBR 8800 Tab. 1 e 2",
    ),
    _variavel(
        "Sobrecarga de uso — bibliotecas, arquivos, depósitos, oficinas e garagens",
        1.50,
        1.30,
        (0.8, 0.7, 0.6),
        "NBR 8800 Tab. 1 e 2",
    ),
    _variavel(
        "Guarda-corpo e cargas de pessoas em plataformas (NBR 6120)",
        1.50,
        1.30,
        (0.7, 0.6, 0.4),
        "NBR 6120 + NBR 8800 Tab. 2",
    ),
    _permanente(
        "Peso próprio de equipamentos (Projeto NBR 8800:2024)",
        1.25,
        1.15,
        1.10,
        "Projeto NBR 8800:2024, Tab. 1",
    ),
    _variavel(
        "Sobrecarga de cobertura (Projeto NBR 8800:2024)",
        1.50,
        1.30,
        (0.8, 0.7, 0.6),
        "Projeto NBR 8800:2024, Tab. 1 e 2",
    ),
    _variavel("Vento (NBR 6123)", 1.40, 1.20, (0.6, 0.3, 0.0), "NBR 8800 Tab. 1 e 2"),
    _variavel("Variação de temperatura", 1.20, 1.00, (0.6, 0.5, 0.3), "NBR 8800 Tab. 1 e 2"),
    _variavel(
        "Ação variável truncada (limitada fisicamente)",
        1.20,
        1.10,
        (1.0, 1.0, 1.0),
        "NBR 8800 Tab. 1 (nota f da Tab. 2: ψ = 1,0)",
    ),
    _variavel(
        "Forças horizontais de equipamentos em operação",
        1.50,
        1.30,
        (0.7, 0.6, 0.4),
        "NBR 8800 Tab. 1 e 2 (uso e ocupação)",
    ),
    _variavel(
        "Passarelas de pedestres",
        1.50,
        1.30,
        (0.6, 0.4, 0.3),
        "Projeto NBR 8800:2024, Tab. 2",
    ),
    _variavel(
        "Pontes rolantes — vigas de rolamento",
        1.50,
        1.30,
        (1.0, 0.8, 0.5),
        "Projeto NBR 8800:2024, Tab. 2",
    ),
    _variavel(
        "Pontes rolantes — pilares e subestruturas das vigas de rolamento",
        1.50,
        1.30,
        (0.7, 0.6, 0.4),
        "Projeto NBR 8800:2024, Tab. 2",
    ),
    CategoriaAcao(
        "Ação excepcional (impacto, explosão, incêndio)",
        TIPO_EXCEPCIONAL,
        1.00,
        None,
        0.0,
        0.0,
        0.0,
        "NBR 8800 4.8.7.2.4",
        1.00,
        1.00,
    ),
)

CATEGORIA_PERSONALIZADA = "— personalizada (γ e ψ informados) —"


def categoria_nbr(rotulo: str) -> CategoriaAcao:
    for categoria in CATEGORIAS_NBR8800:
        if categoria.rotulo == rotulo:
            return categoria
    raise ValueError(f"Categoria de ação desconhecida: {rotulo!r}.")


def acao_da_categoria(
    nome: str,
    rotulo_categoria: str,
    n_kN: float = 0.0,
    v_kN: float = 0.0,
    m_kNm: float = 0.0,
    *,
    grupo: str = "",
    efeitos: Mapping[str, float] | None = None,
    efeitos_reversiveis: Iterable[str] = (),
) -> AcaoEstrutural:
    """Ação já com os coeficientes da NBR 8800/8681 da sua categoria."""
    categoria = categoria_nbr(rotulo_categoria)
    return AcaoEstrutural(
        nome=nome,
        tipo=categoria.tipo,
        n_kN=n_kN,
        v_kN=v_kN,
        m_kNm=m_kNm,
        gamma=categoria.gamma,
        psi0=categoria.psi0,
        psi1=categoria.psi1,
        psi2=categoria.psi2,
        gamma_favoravel=categoria.gamma_favoravel,
        categoria=categoria.rotulo,
        grupo=grupo,
        gamma_especial=categoria.gamma_especial,
        gamma_excepcional=categoria.gamma_excepcional,
        efeitos=dict(efeitos or {}),
        efeitos_reversiveis=frozenset(efeitos_reversiveis),
    )


def acao_para_dicionario(acao: AcaoEstrutural) -> dict[str, object]:
    """A ação em tipos que o JSON aceita (para o registro técnico)."""
    return {
        "nome": acao.nome,
        "tipo": acao.tipo,
        "categoria": acao.categoria,
        "grupo": acao.grupo,
        "n_kN": acao.n_kN,
        "v_kN": acao.v_kN,
        "m_kNm": acao.m_kNm,
        "gamma": acao.gamma,
        "gamma_favoravel": acao.gamma_favoravel,
        "gamma_especial": acao.gamma_especial,
        "gamma_excepcional": acao.gamma_excepcional,
        "psi0": acao.psi0,
        "psi1": acao.psi1,
        "psi2": acao.psi2,
        "efeitos": {str(k): float(v) for k, v in acao.efeitos.items()},
        "efeitos_reversiveis": sorted(acao.efeitos_reversiveis),
    }


@dataclass(frozen=True)
class Combinacao:
    nome: str
    estado_limite: str
    acao_principal: str
    n_kN: float
    v_kN: float
    m_kNm: float
    expressao: str
    fatores: Mapping[str, float] = field(default_factory=dict)

    def valor(self, acoes: Sequence[AcaoEstrutural], efeito: str) -> float:
        """Valor de cálculo de ``efeito`` nesta combinação (sinais como dados)."""
        return sum(self.fatores.get(acao.nome, 0.0) * acao.valor(efeito) for acao in acoes)


@dataclass(frozen=True)
class Extremo:
    """O maior (``sentido = +1``) ou o menor (``-1``) valor de cálculo de um esforço."""

    efeito: str
    estado_limite: str
    sentido: int
    valor: float
    acao_principal: str
    fatores: Mapping[str, float]
    expressao: str


# ---------------------------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------------------------
def _finito(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor):
        raise ValueError(f"{nome} deve ser finito.")
    return valor


def _validar(acoes: Iterable[AcaoEstrutural]) -> list[AcaoEstrutural]:
    itens = list(acoes)
    if not itens:
        raise ValueError("Informe pelo menos uma ação.")
    nomes = [acao.nome.strip() for acao in itens]
    if any(not nome for nome in nomes):
        raise ValueError("Toda ação deve possuir um nome.")
    if len(set(nomes)) != len(nomes):
        raise ValueError("Os nomes das ações devem ser únicos.")
    for acao in itens:
        if acao.tipo not in TIPOS_DE_ACAO:
            raise ValueError("O tipo deve ser Permanente, Variável ou Excepcional.")
        _finito("n_kN", acao.n_kN)
        _finito("v_kN", acao.v_kN)
        _finito("m_kNm", acao.m_kNm)
        for chave, valor in acao.efeitos.items():
            _finito(f"efeito {chave!r} de {acao.nome}", valor)
        for nome, gamma in (
            ("gamma", acao.gamma),
            ("gamma_especial", acao.gamma_especial),
            ("gamma_excepcional", acao.gamma_excepcional),
        ):
            if gamma is not None and (not math.isfinite(gamma) or gamma < 0):
                raise ValueError(f"{nome} não pode ser negativo.")
        if acao.gamma_favoravel is not None and not 0 <= acao.gamma_favoravel <= acao.gamma:
            raise ValueError("gamma_favoravel deve estar entre 0 e gamma.")
        if acao.tipo == TIPO_PERMANENTE and acao.grupo.strip():
            raise ValueError(
                f"{acao.nome}: grupo exclusivo só vale para ações variáveis (as permanentes "
                "atuam sempre)."
            )
        for nome, valor in (
            ("psi0", acao.psi0),
            ("psi1", acao.psi1),
            ("psi2", acao.psi2),
        ):
            if not 0 <= valor <= 1:
                raise ValueError(f"{nome} deve estar entre 0 e 1.")
    return itens


# ---------------------------------------------------------------------------------------------
# Coeficientes por estado-limite
# ---------------------------------------------------------------------------------------------
def gamma_desfavoravel(acao: AcaoEstrutural, estado: str) -> float:
    """γ da ação quando ela agrava o efeito, no estado-limite ``estado``."""
    if estado == ELU_NORMAL:
        return acao.gamma
    if estado == ELU_ESPECIAL:
        return acao.gamma if acao.gamma_especial is None else acao.gamma_especial
    if estado == ELU_EXCEPCIONAL:
        if acao.gamma_excepcional is not None:
            return acao.gamma_excepcional
        if acao.tipo == TIPO_PERMANENTE:
            return acao.gamma if acao.gamma_especial is None else acao.gamma_especial
        return 1.0
    return 1.0


def gamma_favoravel(acao: AcaoEstrutural, estado: str) -> float | None:
    """γ da permanente que alivia o efeito; ``None`` quando não há (variáveis e serviço)."""
    if acao.tipo != TIPO_PERMANENTE or estado not in COMBINACOES_ULTIMAS:
        return None
    return acao.gamma_favoravel


def _fator_principal(acao: AcaoEstrutural, estado: str) -> float:
    if estado == ELS_RARA:
        return 1.0
    if estado == ELS_FREQUENTE:
        return acao.psi1
    if estado == ELU_EXCEPCIONAL and acao.tipo == TIPO_EXCEPCIONAL:
        return 1.0  # F_Q,exc entra com o seu valor
    return gamma_desfavoravel(acao, estado)


def _fator_acompanhante(acao: AcaoEstrutural, estado: str, especial_curta_duracao: bool) -> float:
    if estado == ELU_NORMAL:
        return acao.gamma * acao.psi0
    if estado == ELU_ESPECIAL:
        psi = acao.psi2 if especial_curta_duracao else acao.psi0
        return gamma_desfavoravel(acao, estado) * psi
    if estado == ELU_EXCEPCIONAL:
        return gamma_desfavoravel(acao, estado) * acao.psi2
    if estado == ELS_RARA:
        return acao.psi1
    return acao.psi2  # frequente e quase permanente


def _grupos(variaveis: Sequence[AcaoEstrutural]) -> dict[str, list[AcaoEstrutural]]:
    grupos: dict[str, list[AcaoEstrutural]] = {}
    for acao in variaveis:
        chave = acao.grupo.strip() or f"\0{acao.nome}"
        grupos.setdefault(chave, []).append(acao)
    return grupos


def _chave_do_grupo(acao: AcaoEstrutural) -> str:
    return acao.grupo.strip() or f"\0{acao.nome}"


def _expressao(itens: Sequence[AcaoEstrutural], fatores: Mapping[str, float]) -> str:
    termos = [f"{fatores[a.nome]:.3g}·{a.nome}" for a in itens if fatores.get(a.nome, 0.0) != 0.0]
    return " + ".join(termos) if termos else "0"


def _somar(
    acoes: Sequence[AcaoEstrutural], fatores: Mapping[str, float]
) -> tuple[float, float, float]:
    n = sum(fatores.get(acao.nome, 0.0) * acao.n_kN for acao in acoes)
    v = sum(fatores.get(acao.nome, 0.0) * acao.v_kN for acao in acoes)
    m = sum(fatores.get(acao.nome, 0.0) * acao.m_kNm for acao in acoes)
    return n, v, m


# ---------------------------------------------------------------------------------------------
# Lista explícita
# ---------------------------------------------------------------------------------------------
def gerar_combinacoes(
    acoes: Iterable[AcaoEstrutural],
    estados: Sequence[str] = ESTADOS_PADRAO,
    *,
    especial_curta_duracao: bool = False,
    limite: int = LIMITE_DE_COMBINACOES,
) -> list[Combinacao]:
    """Combinações explícitas dos estados-limite pedidos, na ordem de ``estados``.

    Em cada combinação com ação variável principal, cada grupo exclusivo contribui com no máximo
    uma acompanhante — uma combinação por escolha. As permanentes entram desfavoráveis e, quando
    alguma declarar γ favorável, também numa segunda combinação "(permanentes favoráveis)". A
    lista não retira acompanhantes favoráveis (ela não sabe qual esforço interessa): para isso use
    :func:`envoltoria`.
    """
    itens = _validar(acoes)
    for estado in estados:
        if estado not in TODOS_OS_ESTADOS:
            raise ValueError(f"Estado-limite desconhecido: {estado!r}.")
    permanentes = [a for a in itens if a.tipo == TIPO_PERMANENTE]
    variaveis = [a for a in itens if a.tipo == TIPO_VARIAVEL]
    excepcionais = [a for a in itens if a.tipo == TIPO_EXCEPCIONAL]
    grupos = _grupos(variaveis)
    tem_favoravel = any(a.gamma_favoravel is not None for a in permanentes)
    combinacoes: list[Combinacao] = []

    def adicionar(
        estado: str,
        principal: AcaoEstrutural | None,
        acompanhantes: Sequence[AcaoEstrutural],
        favoraveis: bool,
        rotulo_extra: str,
    ) -> None:
        fatores: dict[str, float] = {}
        for acao in permanentes:
            fav = gamma_favoravel(acao, estado)
            fatores[acao.nome] = (
                fav if (favoraveis and fav is not None) else (gamma_desfavoravel(acao, estado))
            )
        if principal is not None:
            fatores[principal.nome] = _fator_principal(principal, estado)
        for acao in acompanhantes:
            fatores[acao.nome] = _fator_acompanhante(acao, estado, especial_curta_duracao)
        n, v, m = _somar(itens, fatores)
        if estado == ELS_QUASE_PERMANENTE:
            nome = estado
        else:
            nome = f"{estado} — {principal.nome if principal else 'sem variável'} principal"
        if rotulo_extra:
            nome += f" ({rotulo_extra})"
        if favoraveis:
            nome += " (permanentes favoráveis)"
        combinacoes.append(
            Combinacao(
                nome=nome,
                estado_limite=estado,
                acao_principal=principal.nome if principal else "—",
                n_kN=n,
                v_kN=v,
                m_kNm=m,
                expressao=_expressao(itens, fatores),
                fatores=fatores,
            )
        )
        if len(combinacoes) > limite:
            raise ValueError(
                f"Mais de {limite} combinações: agrupe as ações que não atuam juntas (mesmo grupo "
                "exclusivo) ou reduza a lista."
            )

    def escolhas(excluir: str | None) -> list[tuple[list[AcaoEstrutural], str]]:
        listas = [membros for chave, membros in grupos.items() if chave != excluir]
        resultado = []
        for combinacao in itertools.product(*listas):
            ambiguos = [a.nome for a in combinacao if len(grupos[_chave_do_grupo(a)]) > 1]
            resultado.append((list(combinacao), "com " + ", ".join(ambiguos) if ambiguos else ""))
        return resultado or [([], "")]

    for estado in estados:
        if estado == ELS_QUASE_PERMANENTE:
            for acompanhantes, extra in escolhas(None):
                adicionar(estado, None, acompanhantes, False, extra)
            continue
        if estado == ELU_EXCEPCIONAL:
            for principal in excepcionais:
                for acompanhantes, extra in escolhas(None):
                    adicionar(estado, principal, acompanhantes, False, extra)
                    if tem_favoravel:
                        adicionar(estado, principal, acompanhantes, True, extra)
            continue
        if not variaveis:
            adicionar(estado, None, [], False, "")
            continue
        for principal in variaveis:
            for acompanhantes, extra in escolhas(_chave_do_grupo(principal)):
                adicionar(estado, principal, acompanhantes, False, extra)
                if tem_favoravel and estado in COMBINACOES_ULTIMAS:
                    adicionar(estado, principal, acompanhantes, True, extra)
    return combinacoes


# ---------------------------------------------------------------------------------------------
# Envoltória rigorosa por esforço
# ---------------------------------------------------------------------------------------------
def _contribuicao(acao: AcaoEstrutural, efeito: str, sentido: int) -> float:
    valor = acao.valor(efeito)
    if efeito in acao.efeitos_reversiveis:
        return abs(valor) * sentido
    return valor


def extremo(
    acoes: Iterable[AcaoEstrutural],
    efeito: str,
    estado: str = ELU_NORMAL,
    sentido: int = 1,
    *,
    especial_curta_duracao: bool = False,
) -> Extremo | None:
    """O valor de cálculo mais desfavorável de ``efeito`` no sentido pedido.

    Testa cada ação variável como principal (e a combinação sem variável); para cada uma, cada
    permanente entra com o γ desfavorável ou o favorável, e cada grupo de acompanhantes entra com
    o membro que mais agrava — ou com nenhum, se todos aliviam. ``None`` quando o estado-limite
    não tem combinação (ELU excepcional sem ação excepcional).
    """
    itens = _validar(acoes)
    if estado not in TODOS_OS_ESTADOS:
        raise ValueError(f"Estado-limite desconhecido: {estado!r}.")
    if sentido not in (1, -1):
        raise ValueError("O sentido deve ser +1 (máximo) ou −1 (mínimo).")
    permanentes = [a for a in itens if a.tipo == TIPO_PERMANENTE]
    variaveis = [a for a in itens if a.tipo == TIPO_VARIAVEL]
    excepcionais = [a for a in itens if a.tipo == TIPO_EXCEPCIONAL]
    grupos = _grupos(variaveis)

    if estado == ELU_EXCEPCIONAL:
        candidatos: list[AcaoEstrutural | None] = list(excepcionais)
        if not candidatos:
            return None
    elif estado == ELS_QUASE_PERMANENTE:
        candidatos = [None]
    else:
        candidatos = [None, *variaveis]

    melhor: Extremo | None = None
    for principal in candidatos:
        fatores: dict[str, float] = {}
        total = 0.0
        for acao in permanentes:
            c = _contribuicao(acao, efeito, sentido)
            fav = gamma_favoravel(acao, estado)
            fator = gamma_desfavoravel(acao, estado)
            if c * sentido < 0 and fav is not None:
                fator = fav
            fatores[acao.nome] = fator
            total += fator * c
        grupo_principal = None
        if principal is not None:
            fator = _fator_principal(principal, estado)
            fatores[principal.nome] = fator
            total += fator * _contribuicao(principal, efeito, sentido)
            if principal.tipo == TIPO_VARIAVEL:
                grupo_principal = _chave_do_grupo(principal)
        acompanha = estado == ELS_QUASE_PERMANENTE or principal is not None
        if acompanha:
            for chave, membros in grupos.items():
                if chave == grupo_principal:
                    continue
                melhor_membro, melhor_parcela = None, 0.0
                for acao in membros:
                    fator = _fator_acompanhante(acao, estado, especial_curta_duracao)
                    parcela = fator * _contribuicao(acao, efeito, sentido)
                    if parcela * sentido > melhor_parcela * sentido + 1e-12:
                        melhor_membro, melhor_parcela = acao, parcela
                if melhor_membro is not None:
                    fatores[melhor_membro.nome] = _fator_acompanhante(
                        melhor_membro, estado, especial_curta_duracao
                    )
                    total += melhor_parcela
        if melhor is None or total * sentido > melhor.valor * sentido + 1e-12:
            melhor = Extremo(
                efeito=efeito,
                estado_limite=estado,
                sentido=sentido,
                valor=total,
                acao_principal=principal.nome if principal else "—",
                fatores=dict(fatores),
                expressao=_expressao(itens, fatores),
            )
    return melhor


def envoltoria(
    acoes: Iterable[AcaoEstrutural],
    efeitos: Sequence[str],
    estados: Sequence[str] = ESTADOS_PADRAO,
    *,
    especial_curta_duracao: bool = False,
) -> list[Extremo]:
    """Máximo e mínimo de cada esforço em cada estado-limite (os que existirem)."""
    itens = _validar(acoes)
    resultado: list[Extremo] = []
    for efeito in efeitos:
        for estado in estados:
            for sentido in (1, -1):
                achado = extremo(
                    itens,
                    efeito,
                    estado,
                    sentido,
                    especial_curta_duracao=especial_curta_duracao,
                )
                if achado is not None:
                    resultado.append(achado)
    return resultado


def maior_modulo(
    acoes: Iterable[AcaoEstrutural],
    efeito: str,
    estado: str = ELU_NORMAL,
    *,
    especial_curta_duracao: bool = False,
) -> Extremo | None:
    """O extremo de maior valor absoluto (máximo ou mínimo) — para esforços que invertem."""
    itens = list(acoes)
    candidatos = [
        extremo(itens, efeito, estado, s, especial_curta_duracao=especial_curta_duracao)
        for s in (1, -1)
    ]
    validos = [c for c in candidatos if c is not None]
    if not validos:
        return None
    return max(validos, key=lambda c: abs(c.valor))
