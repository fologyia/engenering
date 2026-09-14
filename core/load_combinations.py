"""Gerador editável de combinações de ações por estados-limite."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass


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
    # γ da ação permanente quando ela ALIVIA o efeito (NBR 8681: 1,0). Só
    # com ele a combinação "permanentes favoráveis" é gerada — é a que
    # governa vento de sucção e tombamento.
    gamma_favoravel: float | None = None
    categoria: str = ""


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


# Tabelas 1 e 2 da NBR 8800:2008 (combinações normais), que remetem à
# NBR 8681. As ações permanentes trazem o γ favorável (1,0) para a
# combinação em que elas aliviam; as variáveis, os fatores ψ da NBR 8681.
CATEGORIAS_NBR8800: tuple[CategoriaAcao, ...] = (
    CategoriaAcao(
        "Peso próprio de estrutura metálica",
        "Permanente",
        1.25,
        1.00,
        1.0,
        1.0,
        1.0,
        "NBR 8800 Tab. 1",
    ),
    CategoriaAcao(
        "Peso próprio de estrutura pré-moldada",
        "Permanente",
        1.30,
        1.00,
        1.0,
        1.0,
        1.0,
        "NBR 8800 Tab. 1",
    ),
    CategoriaAcao(
        "Peso próprio de estrutura moldada no local",
        "Permanente",
        1.35,
        1.00,
        1.0,
        1.0,
        1.0,
        "NBR 8800 Tab. 1",
    ),
    CategoriaAcao(
        "Elementos construtivos industrializados (grades, pisos, guarda-corpos)",
        "Permanente",
        1.35,
        1.00,
        1.0,
        1.0,
        1.0,
        "NBR 8800 Tab. 1",
    ),
    CategoriaAcao(
        "Elementos construtivos industrializados com adições in loco",
        "Permanente",
        1.40,
        1.00,
        1.0,
        1.0,
        1.0,
        "NBR 8800 Tab. 1",
    ),
    CategoriaAcao(
        "Elementos construtivos em geral e equipamentos",
        "Permanente",
        1.50,
        1.00,
        1.0,
        1.0,
        1.0,
        "NBR 8800 Tab. 1",
    ),
    CategoriaAcao(
        "Sobrecarga de uso — sem predominância de equipamentos fixos nem de pessoas",
        "Variável",
        1.50,
        None,
        0.5,
        0.4,
        0.3,
        "NBR 8800 Tab. 1 e 2",
    ),
    CategoriaAcao(
        "Sobrecarga de uso — predominância de equipamentos fixos ou concentração de pessoas",
        "Variável",
        1.50,
        None,
        0.7,
        0.6,
        0.4,
        "NBR 8800 Tab. 1 e 2",
    ),
    CategoriaAcao(
        "Sobrecarga de uso — bibliotecas, arquivos, depósitos, oficinas e garagens",
        "Variável",
        1.50,
        None,
        0.8,
        0.7,
        0.6,
        "NBR 8800 Tab. 1 e 2",
    ),
    CategoriaAcao(
        "Guarda-corpo e cargas de pessoas em plataformas (NBR 6120)",
        "Variável",
        1.50,
        None,
        0.7,
        0.6,
        0.4,
        "NBR 6120 + NBR 8800 Tab. 2",
    ),
    CategoriaAcao("Vento (NBR 6123)", "Variável", 1.40, None, 0.6, 0.3, 0.0, "NBR 8800 Tab. 1 e 2"),
    CategoriaAcao(
        "Variação de temperatura", "Variável", 1.20, None, 0.6, 0.5, 0.3, "NBR 8800 Tab. 1 e 2"
    ),
    CategoriaAcao(
        "Ação variável truncada (limitada fisicamente)",
        "Variável",
        1.20,
        None,
        0.7,
        0.6,
        0.4,
        "NBR 8800 Tab. 1",
    ),
)

CATEGORIA_PERSONALIZADA = "— personalizada (γ e ψ informados) —"


def categoria_nbr(rotulo: str) -> CategoriaAcao:
    for categoria in CATEGORIAS_NBR8800:
        if categoria.rotulo == rotulo:
            return categoria
    raise ValueError(f"Categoria de ação desconhecida: {rotulo!r}.")


def acao_da_categoria(
    nome: str, rotulo_categoria: str, n_kN: float, v_kN: float, m_kNm: float
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
    )


@dataclass(frozen=True)
class Combinacao:
    nome: str
    estado_limite: str
    acao_principal: str
    n_kN: float
    v_kN: float
    m_kNm: float
    expressao: str


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
        if acao.tipo not in {"Permanente", "Variável"}:
            raise ValueError("O tipo deve ser Permanente ou Variável.")
        _finito("n_kN", acao.n_kN)
        _finito("v_kN", acao.v_kN)
        _finito("m_kNm", acao.m_kNm)
        if acao.gamma < 0:
            raise ValueError("gamma não pode ser negativo.")
        if acao.gamma_favoravel is not None and not 0 <= acao.gamma_favoravel <= acao.gamma:
            raise ValueError("gamma_favoravel deve estar entre 0 e gamma.")
        for nome, valor in (
            ("psi0", acao.psi0),
            ("psi1", acao.psi1),
            ("psi2", acao.psi2),
        ):
            if not 0 <= valor <= 1:
                raise ValueError(f"{nome} deve estar entre 0 e 1.")
    return itens


def _somar(
    acoes: list[AcaoEstrutural],
    fatores: dict[str, float],
) -> tuple[float, float, float]:
    n = sum(fatores[acao.nome] * acao.n_kN for acao in acoes)
    v = sum(fatores[acao.nome] * acao.v_kN for acao in acoes)
    m = sum(fatores[acao.nome] * acao.m_kNm for acao in acoes)
    return n, v, m


def gerar_combinacoes(acoes: Iterable[AcaoEstrutural]) -> list[Combinacao]:
    """Gera ELU fundamental e ELS rara, frequente e quase permanente.

    Os coeficientes ``gamma`` e ``psi`` são fornecidos pelo usuário para manter
    o gerador aplicável às categorias específicas da norma e do projeto.
    """
    itens = _validar(acoes)
    variaveis = [acao for acao in itens if acao.tipo == "Variável"]
    combinacoes: list[Combinacao] = []
    # NBR 8681: quando a ação permanente alivia o efeito da variável (vento
    # de sucção, tombamento), o seu γ cai para o valor favorável. Gera-se a
    # segunda combinação sempre que alguma permanente declarar esse γ.
    tem_favoravel = any(
        acao.tipo == "Permanente" and acao.gamma_favoravel is not None for acao in itens
    )

    principais = variaveis or [None]
    for principal in principais:
        variantes: list[tuple[str, bool]] = [("", False)]
        if tem_favoravel and principal is not None:
            variantes.append((" (permanentes favoráveis)", True))
        for sufixo, favoravel in variantes:
            fatores_elu = {}
            termos_elu = []
            for acao in itens:
                if acao.tipo == "Permanente":
                    fator = (
                        acao.gamma_favoravel
                        if favoravel and acao.gamma_favoravel is not None
                        else acao.gamma
                    )
                elif acao is principal:
                    fator = acao.gamma
                else:
                    fator = acao.gamma * acao.psi0
                fatores_elu[acao.nome] = fator
                termos_elu.append(f"{fator:.3g}·{acao.nome}")
            n, v, m = _somar(itens, fatores_elu)
            principal_nome = principal.nome if principal else "Sem variável"
            combinacoes.append(
                Combinacao(
                    nome=f"ELU — {principal_nome} principal{sufixo}",
                    estado_limite="ELU fundamental",
                    acao_principal=principal_nome,
                    n_kN=n,
                    v_kN=v,
                    m_kNm=m,
                    expressao=" + ".join(termos_elu),
                )
            )

        if principal is None:
            continue
        for estado, psi_principal, psi_acompanhante, rotulo in (
            ("ELS rara", 1.0, "psi0", "rara"),
            ("ELS frequente", principal.psi1, "psi2", "frequente"),
        ):
            fatores_els = {}
            termos_els = []
            for acao in itens:
                if acao.tipo == "Permanente":
                    fator = 1.0
                elif acao is principal:
                    fator = float(psi_principal)
                else:
                    fator = float(getattr(acao, psi_acompanhante))
                fatores_els[acao.nome] = fator
                termos_els.append(f"{fator:.3g}·{acao.nome}")
            n, v, m = _somar(itens, fatores_els)
            combinacoes.append(
                Combinacao(
                    nome=f"ELS {rotulo} — {principal.nome} principal",
                    estado_limite=estado,
                    acao_principal=principal.nome,
                    n_kN=n,
                    v_kN=v,
                    m_kNm=m,
                    expressao=" + ".join(termos_els),
                )
            )

    fatores_qp = {acao.nome: 1.0 if acao.tipo == "Permanente" else acao.psi2 for acao in itens}
    n, v, m = _somar(itens, fatores_qp)
    combinacoes.append(
        Combinacao(
            nome="ELS quase permanente",
            estado_limite="ELS quase permanente",
            acao_principal="—",
            n_kN=n,
            v_kN=v,
            m_kNm=m,
            expressao=" + ".join(f"{fatores_qp[acao.nome]:.3g}·{acao.nome}" for acao in itens),
        )
    )
    return combinacoes
