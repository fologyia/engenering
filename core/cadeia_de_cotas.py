"""Cadeia de cotas: peças em fila e a folga (ou o aperto) que sobra no fim.

Cada elo é uma medida com o seu sentido: a que **aumenta** a folga (a largura do alojamento) entra
com +, a que **diminui** (o rolamento, o espaçador, o anel) entra com −. A tolerância de cada elo vem
dos afastamentos informados ou de uma classe ISO da NBR 6158 (:mod:`core.ajustes_e_tolerancias`).

Dois jeitos de somar:

* **Pior caso** (aritmético): todos os elos no limite que mais atrapalha ao mesmo tempo. A folga
  sempre fica dentro, mas as tolerâncias somam por inteiro.
* **Estatístico** (raiz da soma dos quadrados): cada medida segue uma distribuição normal centrada
  no meio da tolerância, com a tolerância = ±3σ (processo centrado, Cp = 1). A folga tem média = soma
  das médias e σ = √Σσᵢ². A faixa de ±3σ cobre 99,73 % das montagens. Vale para fabricação em série
  com processos sob controle; para poucas peças, use o pior caso.

Todas as medidas em milímetros.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core import ajustes_e_tolerancias as at

AUMENTA = "Aumenta a folga"
DIMINUI = "Diminui a folga"
SENTIDOS = (AUMENTA, DIMINUI)
MAXIMO_DE_ELOS = 40
SIGMAS = 3.0  # a tolerância de cada elo é ±3σ


class ErroDaCadeia(ValueError):
    """O que está errado na cadeia, dito em palavras de quem montou a tabela."""


@dataclass(frozen=True)
class Elo:
    nome: str
    sentido: str
    nominal: float
    superior: float  # afastamento, mm
    inferior: float
    classe: str = ""  # quando a tolerância veio da NBR 6158

    @property
    def sinal(self) -> int:
        return 1 if self.sentido == AUMENTA else -1

    @property
    def tolerancia(self) -> float:
        return self.superior - self.inferior

    @property
    def media(self) -> float:
        return self.nominal + (self.superior + self.inferior) / 2.0

    @property
    def sigma(self) -> float:
        return self.tolerancia / (2.0 * SIGMAS)


def _numero(valor: Any) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = float(str(valor).replace(",", ".")) if isinstance(valor, str) else float(valor)
    except ValueError:
        return None
    return numero if math.isfinite(numero) else None


def elo_da_linha(linha: Mapping[str, Any], posicao: int) -> Elo:
    """Uma linha da tabela da tela. Com classe ISO, os afastamentos saem da norma."""
    nome = str(linha.get("nome") or "").strip() or f"Elo {posicao}"
    sentido = linha.get("sentido")
    if sentido not in SENTIDOS:
        raise ErroDaCadeia(f"{nome}: escolha se a medida aumenta ou diminui a folga.")
    nominal = _numero(linha.get("nominal"))
    if nominal is None or nominal <= 0:
        raise ErroDaCadeia(f"{nome}: a medida nominal precisa ser um número maior que zero.")
    classe = str(linha.get("classe") or "").strip()
    if classe:
        try:
            zona = at.zona(classe, nominal)
        except at.ErroDeAjuste as erro:
            raise ErroDaCadeia(f"{nome}: {erro}") from erro
        return Elo(nome, sentido, nominal, zona.superior / 1000.0, zona.inferior / 1000.0, classe)
    superior = _numero(linha.get("superior"))
    inferior = _numero(linha.get("inferior"))
    superior = 0.0 if superior is None else superior
    inferior = 0.0 if inferior is None else inferior
    if superior < inferior:
        raise ErroDaCadeia(
            f"{nome}: o afastamento superior ({at.numero(superior)}) não pode ficar abaixo do "
            f"inferior ({at.numero(inferior)})."
        )
    return Elo(nome, sentido, nominal, superior, inferior)


@dataclass(frozen=True)
class Contribuicao:
    elo: Elo
    no_pior_caso: float  # fração da soma das tolerâncias
    na_variancia: float  # fração da variância da folga


@dataclass(frozen=True)
class Cadeia:
    elos: tuple[Elo, ...]
    exigida_min: float | None
    exigida_max: float | None

    @property
    def nominal(self) -> float:
        return sum(e.sinal * e.nominal for e in self.elos)

    @property
    def pior_maxima(self) -> float:
        return sum(
            e.sinal * e.nominal + (e.superior if e.sinal > 0 else -e.inferior) for e in self.elos
        )

    @property
    def pior_minima(self) -> float:
        return sum(
            e.sinal * e.nominal + (e.inferior if e.sinal > 0 else -e.superior) for e in self.elos
        )

    @property
    def media(self) -> float:
        return sum(e.sinal * e.media for e in self.elos)

    @property
    def sigma(self) -> float:
        return math.sqrt(sum(e.sigma**2 for e in self.elos))

    @property
    def estatistica_minima(self) -> float:
        return self.media - SIGMAS * self.sigma

    @property
    def estatistica_maxima(self) -> float:
        return self.media + SIGMAS * self.sigma

    @property
    def contribuicoes(self) -> list[Contribuicao]:
        soma = sum(e.tolerancia for e in self.elos)
        variancia = sum(e.sigma**2 for e in self.elos)
        return sorted(
            (
                Contribuicao(
                    e,
                    e.tolerancia / soma if soma > 0 else 0.0,
                    e.sigma**2 / variancia if variancia > 0 else 0.0,
                )
                for e in self.elos
            ),
            key=lambda c: c.na_variancia,
            reverse=True,
        )

    def fora_abaixo(self) -> float | None:
        """Fração das montagens com folga abaixo da mínima exigida (estatístico)."""
        if self.exigida_min is None:
            return None
        return _abaixo(self.exigida_min, self.media, self.sigma)

    def fora_acima(self) -> float | None:
        if self.exigida_max is None:
            return None
        return 1.0 - _abaixo(self.exigida_max, self.media, self.sigma)

    @property
    def pior_caso_atende(self) -> bool | None:
        if self.exigida_min is None and self.exigida_max is None:
            return None
        return (self.exigida_min is None or self.pior_minima >= self.exigida_min - 1e-12) and (
            self.exigida_max is None or self.pior_maxima <= self.exigida_max + 1e-12
        )

    @property
    def estatistico_atende(self) -> bool | None:
        if self.exigida_min is None and self.exigida_max is None:
            return None
        return (
            self.exigida_min is None or self.estatistica_minima >= self.exigida_min - 1e-12
        ) and (self.exigida_max is None or self.estatistica_maxima <= self.exigida_max + 1e-12)


def _abaixo(limite: float, media: float, sigma: float) -> float:
    if sigma <= 0:
        return 1.0 if media < limite else 0.0
    return 0.5 * (1.0 + math.erf((limite - media) / (sigma * math.sqrt(2.0))))


def montar(
    linhas: Sequence[Mapping[str, Any]],
    exigida_min: float | None = None,
    exigida_max: float | None = None,
) -> Cadeia:
    usadas = [
        linha
        for linha in linhas
        if any(linha.get(k) not in (None, "") for k in ("nome", "nominal", "classe"))
    ]
    if len(usadas) < 2:
        raise ErroDaCadeia("Uma cadeia precisa de ao menos dois elos: o alojamento e uma peça.")
    if len(usadas) > MAXIMO_DE_ELOS:
        raise ErroDaCadeia(f"A cadeia aceita até {MAXIMO_DE_ELOS} elos.")
    elos = tuple(elo_da_linha(linha, i) for i, linha in enumerate(usadas, start=1))
    if not any(e.sinal > 0 for e in elos):
        raise ErroDaCadeia(
            "Nenhum elo aumenta a folga: falta a medida que fecha a cadeia, como a largura do "
            "alojamento."
        )
    if exigida_min is not None and exigida_max is not None and exigida_min > exigida_max:
        raise ErroDaCadeia("A folga mínima exigida não pode passar da máxima.")
    return Cadeia(elos, exigida_min, exigida_max)


#: As colunas da tabela da tela, para cada campo do elo.
COLUNAS_DA_TELA = {
    "nome": "Elo",
    "sentido": "Sentido",
    "nominal": "Nominal (mm)",
    "classe": "Classe ISO",
    "superior": "Afast. superior (mm)",
    "inferior": "Afast. inferior (mm)",
}


def para_a_tela(linhas: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {rotulo: linha.get(campo) for campo, rotulo in COLUNAS_DA_TELA.items()} for linha in linhas
    ]


def da_tela(linhas: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """O que voltou da tabela, nos campos do elo, com no máximo o número de elos aceito."""
    return [
        {campo: linha.get(rotulo) for campo, rotulo in COLUNAS_DA_TELA.items()}
        for linha in list(linhas)[:MAXIMO_DE_ELOS]
    ]


#: O exemplo da tela: dois rolamentos e um espaçador dentro de uma caixa.
EXEMPLO: tuple[dict[str, Any], ...] = (
    {
        "nome": "Largura interna da caixa",
        "sentido": AUMENTA,
        "nominal": 60.0,
        "classe": "",
        "superior": 0.10,
        "inferior": 0.0,
    },
    {
        "nome": "Rolamento 1 (largura)",
        "sentido": DIMINUI,
        "nominal": 20.0,
        "classe": "",
        "superior": 0.0,
        "inferior": -0.12,
    },
    {
        "nome": "Rolamento 2 (largura)",
        "sentido": DIMINUI,
        "nominal": 20.0,
        "classe": "",
        "superior": 0.0,
        "inferior": -0.12,
    },
    {
        "nome": "Espaçador",
        "sentido": DIMINUI,
        "nominal": 19.8,
        "classe": "h11",
        "superior": None,
        "inferior": None,
    },
)


def registro(cadeia: Cadeia, titulo: str = "") -> dict[str, Any]:
    from core.technical_records import criar_registro_tecnico

    def mm(valor: float) -> str:
        return f"{at.numero(valor, 3)} mm"

    atende = cadeia.pior_caso_atende
    status = (
        "Atende"
        if atende in (None, True)
        else ("Atenção" if cadeia.estatistico_atende else "Não atende")
    )
    texto = (
        f"Folga nominal {mm(cadeia.nominal)}; pior caso de {mm(cadeia.pior_minima)} a "
        f"{mm(cadeia.pior_maxima)}; estatístico (±3σ) de {mm(cadeia.estatistica_minima)} a "
        f"{mm(cadeia.estatistica_maxima)}."
    )
    return criar_registro_tecnico(
        modulo=at.MODULO_TITULO,
        modulo_id=at.MODULO_ID,
        titulo=titulo or f"Cadeia de cotas com {len(cadeia.elos)} elos",
        status=status,
        resumo=texto,
        entradas={
            "elos": [
                {
                    "nome": e.nome,
                    "sentido": e.sentido,
                    "nominal_mm": e.nominal,
                    "classe": e.classe or None,
                    "afastamento_superior_mm": round(e.superior, 6),
                    "afastamento_inferior_mm": round(e.inferior, 6),
                }
                for e in cadeia.elos
            ],
            "folga_minima_exigida_mm": cadeia.exigida_min,
            "folga_maxima_exigida_mm": cadeia.exigida_max,
        },
        resultados={
            "folga_nominal_mm": round(cadeia.nominal, 6),
            "pior_caso_mm": [round(cadeia.pior_minima, 6), round(cadeia.pior_maxima, 6)],
            "estatistico_mm": [
                round(cadeia.estatistica_minima, 6),
                round(cadeia.estatistica_maxima, 6),
            ],
            "destaque_memorial": texto,
        },
        metodo=(
            "Soma das medidas com o sentido de cada uma. Pior caso: todos os elos no limite "
            "desfavorável. Estatístico: tolerância de cada elo = ±3σ, σ da folga = √Σσᵢ²."
        ),
        premissas=[
            "Medidas independentes, cada uma com distribuição normal centrada no meio da "
            "tolerância (estatístico).",
            "Peças rígidas, a 20 °C, sem erro de forma.",
        ],
        referencias=[at.REFERENCIA],
        conclusao=texto,
    )
