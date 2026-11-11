"""Tolerâncias e ajustes ISO pela NBR 6158:1995 (ISO 286-1), de 0 a 500 mm.

O sistema da norma, e não uma lista de ajustes prontos: qualquer classe de furo (A a U, JS) ou de
eixo (a a u, js), em qualquer grau de IT1 a IT18, sai de três tabelas:

* Tabela 1: os graus de tolerância-padrão IT;
* Tabela 2: os afastamentos fundamentais dos eixos;
* Tabela 3: os dos furos, que repetem os dos eixos com o sinal trocado, mais o Δ (= IT_n − IT_n−1)
  nos furos K, M e N até IT8 e P a U até IT7, e o caso especial do M6 de 250 a 315 mm.

Os valores conferidos nas Tabelas 15 a 38 (afastamentos limites) estão nos testes. Ficaram de fora
as letras de uso raro (cd, ef, fg, j, v a zc e as maiúsculas) e as dimensões acima de 500 mm.

Todos os afastamentos aqui estão em micrômetros (µm), e as dimensões em milímetros.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core import elementos_eixos as ee
from core.elementos_base import Resultado
from core.memorial_verificacoes import decimal_ptbr

MODULO_ID = "ajustes_e_tolerancias"
MODULO_TITULO = "Ajustes e tolerâncias"
REFERENCIA = "ABNT NBR 6158:1995 — Sistema de tolerâncias e ajustes (ISO 286-1)"
DIMENSAO_MAXIMA = 500.0

COM_FOLGA = "Com folga"
INCERTO = "Incerto"
COM_INTERFERENCIA = "Com interferência"


class ErroDeAjuste(ValueError):
    """O que não existe na norma, dito em palavras de quem escolheu a classe."""


# ---------------------------------------------------------------------------------------------
# Faixas de dimensão (Tabela 1 e grupos intermediários da Tabela 4)
# ---------------------------------------------------------------------------------------------

#: Limite superior (inclusive) de cada faixa principal, em mm.
FAIXAS = (3, 6, 10, 18, 30, 50, 80, 120, 180, 250, 315, 400, 500)
#: Faixas intermediárias: a, b, c, r, s, t e u mudam dentro de algumas faixas principais.
FAIXAS_FINAS = (
    3, 6, 10, 14, 18, 24, 30, 40, 50, 65, 80, 100, 120, 140, 160, 180, 200, 225, 250, 280, 315,
    355, 400, 450, 500,
)  # fmt: skip


def _indice(limites: tuple[int, ...], d: float) -> int:
    if not math.isfinite(d) or d <= 0.0:
        raise ErroDeAjuste("O diâmetro precisa ser um número maior que zero.")
    for i, ate in enumerate(limites):
        if d <= ate:
            return i
    raise ErroDeAjuste(
        f"A página cobre a NBR 6158 até {DIMENSAO_MAXIMA:.0f} mm. Acima disso, a norma tem tabelas "
        "próprias, para uso experimental em parte delas."
    )


def faixa(d: float) -> tuple[float, float]:
    """A faixa principal da dimensão: (acima de, até e inclusive), em mm."""
    i = _indice(FAIXAS, d)
    return (0.0 if i == 0 else float(FAIXAS[i - 1]), float(FAIXAS[i]))


# ---------------------------------------------------------------------------------------------
# Tabela 1 — graus de tolerância-padrão, em µm (IT12 a IT18 vêm em mm na norma)
# ---------------------------------------------------------------------------------------------

_IT: dict[int, tuple[float, ...]] = {
    1: (0.8, 1, 1, 1.2, 1.5, 1.5, 2, 2.5, 3.5, 4.5, 6, 7, 8),
    2: (1.2, 1.5, 1.5, 2, 2.5, 2.5, 3, 4, 5, 7, 8, 9, 10),
    3: (2, 2.5, 2.5, 3, 4, 4, 5, 6, 8, 10, 12, 13, 15),
    4: (3, 4, 4, 5, 6, 7, 8, 10, 12, 14, 16, 18, 20),
    5: (4, 5, 6, 8, 9, 11, 13, 15, 18, 20, 23, 25, 27),
    6: (6, 8, 9, 11, 13, 16, 19, 22, 25, 29, 32, 36, 40),
    7: (10, 12, 15, 18, 21, 25, 30, 35, 40, 46, 52, 57, 63),
    8: (14, 18, 22, 27, 33, 39, 46, 54, 63, 72, 81, 89, 97),
    9: (25, 30, 36, 43, 52, 62, 74, 87, 100, 115, 130, 140, 155),
    10: (40, 48, 58, 70, 84, 100, 120, 140, 160, 185, 210, 230, 250),
    11: (60, 75, 90, 110, 130, 160, 190, 220, 250, 290, 320, 360, 400),
    12: (100, 120, 150, 180, 210, 250, 300, 350, 400, 460, 520, 570, 630),
    13: (140, 180, 220, 270, 330, 390, 460, 540, 630, 720, 810, 890, 970),
    14: (250, 300, 360, 430, 520, 620, 740, 870, 1000, 1150, 1300, 1400, 1550),
    15: (400, 480, 580, 700, 840, 1000, 1200, 1400, 1600, 1850, 2100, 2300, 2500),
    16: (600, 750, 900, 1100, 1300, 1600, 1900, 2200, 2500, 2900, 3200, 3600, 4000),
    17: (1000, 1200, 1500, 1800, 2100, 2500, 3000, 3500, 4000, 4600, 5200, 5700, 6300),
    18: (1400, 1800, 2200, 2700, 3300, 3900, 4600, 5400, 6300, 7200, 8100, 8900, 9700),
}
GRAUS = tuple(_IT)


def tolerancia(grau: int, d: float) -> float:
    """IT do grau na dimensão, em µm (Tabela 1)."""
    if grau not in _IT:
        raise ErroDeAjuste(f"O grau IT{grau} não existe: a norma vai de IT1 a IT18.")
    if grau >= 14 and d <= 1.0:
        raise ErroDeAjuste("Os graus IT14 a IT18 não valem para dimensões até 1 mm (Tabela 1).")
    return float(_IT[grau][_indice(FAIXAS, d)])


def delta(grau: int, d: float) -> float:
    """Δ = IT_n − IT_(n−1), da Tabela 3. Até 3 mm a norma dá Δ = 0."""
    if not 3 <= grau <= 8:
        raise ErroDeAjuste(f"O Δ da Tabela 3 só existe de IT3 a IT8, e não em IT{grau}.")
    if d <= 3.0:
        return 0.0
    return tolerancia(grau, d) - tolerancia(grau - 1, d)


# ---------------------------------------------------------------------------------------------
# Tabela 2 — afastamentos fundamentais dos eixos, em µm
# ---------------------------------------------------------------------------------------------

#: Afastamento superior (es) de a até h, por faixa fina (a, b, c) ou principal (d até h).
_ES_FINO = {
    "a": (
        -270, -270, -280, -290, -290, -300, -300, -310, -320, -340, -360, -380, -410, -460, -520,
        -580, -660, -740, -820, -920, -1050, -1200, -1350, -1500, -1650,
    ),
    "b": (
        -140, -140, -150, -150, -150, -160, -160, -170, -180, -190, -200, -220, -240, -260, -280,
        -310, -340, -380, -420, -480, -540, -600, -680, -760, -840,
    ),
    "c": (
        -60, -70, -80, -95, -95, -110, -110, -120, -130, -140, -150, -170, -180, -200, -210, -230,
        -240, -260, -280, -300, -330, -360, -400, -440, -480,
    ),
}  # fmt: skip
_ES = {
    "d": (-20, -30, -40, -50, -65, -80, -100, -120, -145, -170, -190, -210, -230),
    "e": (-14, -20, -25, -32, -40, -50, -60, -72, -85, -100, -110, -125, -135),
    "f": (-6, -10, -13, -16, -20, -25, -30, -36, -43, -50, -56, -62, -68),
    "g": (-2, -4, -5, -6, -7, -9, -10, -12, -14, -15, -17, -18, -20),
    "h": (0,) * 13,
}
#: Afastamento inferior (ei) de k até p, por faixa principal. O k vale só de IT4 a IT7.
_EI = {
    "k": (0, 1, 1, 1, 2, 2, 2, 3, 3, 4, 4, 4, 5),
    "m": (2, 4, 6, 7, 8, 9, 11, 13, 15, 17, 20, 21, 23),
    "n": (4, 8, 10, 12, 15, 17, 20, 23, 27, 31, 34, 37, 40),
    "p": (6, 12, 15, 18, 22, 26, 32, 37, 43, 50, 56, 62, 68),
}
#: Afastamento inferior (ei) de r até u, por faixa fina. O t só começa acima de 24 mm.
_EI_FINO: dict[str, tuple[int | None, ...]] = {
    "r": (
        10, 15, 19, 23, 23, 28, 28, 34, 34, 41, 43, 51, 54, 63, 65, 68, 77, 80, 84, 94, 98, 108,
        114, 126, 132,
    ),
    "s": (
        14, 19, 23, 28, 28, 35, 35, 43, 43, 53, 59, 71, 79, 92, 100, 108, 122, 130, 140, 158, 170,
        190, 208, 232, 252,
    ),
    "t": (
        None, None, None, None, None, None, 41, 48, 54, 66, 75, 91, 104, 122, 134, 146, 166, 180,
        196, 218, 240, 268, 294, 330, 360,
    ),
    "u": (
        18, 23, 28, 33, 33, 41, 48, 60, 70, 87, 102, 124, 144, 170, 190, 210, 236, 258, 284, 315,
        350, 390, 435, 490, 540,
    ),
}  # fmt: skip

LETRAS_DE_EIXO = (
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "js",
    "k",
    "m",
    "n",
    "p",
    "r",
    "s",
    "t",
    "u",
)
LETRAS_DE_FURO = tuple(letra.upper() for letra in LETRAS_DE_EIXO)


def _fundamental_do_eixo(letra: str, grau: int, d: float) -> tuple[str, float]:
    """("es" ou "ei", valor) do eixo, pela Tabela 2."""
    if letra in ("a", "b") and d <= 1.0:
        raise ErroDeAjuste("Os afastamentos a e b não valem para dimensões até 1 mm (Tabela 2).")
    if letra in _ES_FINO:
        return "es", float(_ES_FINO[letra][_indice(FAIXAS_FINAS, d)])
    if letra in _ES:
        return "es", float(_ES[letra][_indice(FAIXAS, d)])
    if letra == "k":
        valor = _EI["k"][_indice(FAIXAS, d)] if 4 <= grau <= 7 else 0
        return "ei", float(valor)
    if letra in _EI:
        return "ei", float(_EI[letra][_indice(FAIXAS, d)])
    if letra in _EI_FINO:
        fino = _EI_FINO[letra][_indice(FAIXAS_FINAS, d)]
        if fino is None:
            raise ErroDeAjuste(
                f"O afastamento {letra} só existe acima de 24 mm (Tabela 2). Use u, que é parecido."
            )
        return "ei", float(fino)
    raise ErroDeAjuste(f"A letra {letra} não está nesta página.")


def _js(grau: int, d: float) -> float:
    """Meia tolerância de js e JS, como na Tabela 32 (js7 de 18 a 30 mm: ±10,5 µm).

    A nota B das Tabelas 2 e 3 permite arredondar o IT ímpar de 7 a 11 para o par de baixo; é uma
    opção, e a tabela da norma não arredonda.
    """
    return tolerancia(grau, d) / 2.0


# ---------------------------------------------------------------------------------------------
# Classes, zonas e ajustes
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Classe:
    letra: str
    grau: int

    @property
    def furo(self) -> bool:
        return self.letra[0].isupper()

    @property
    def nome(self) -> str:
        return f"{self.letra}{self.grau}"


_PADRAO_DA_CLASSE = re.compile(r"^\s*([A-Za-z]{1,2})\s*(?:IT)?\s*(\d{1,2})\s*$")


def classe(texto: str) -> Classe:
    """ "H7", "js6", "s6": letra e grau. Maiúscula é furo, minúscula é eixo."""
    achado = _PADRAO_DA_CLASSE.match(str(texto))
    if not achado:
        raise ErroDeAjuste(
            f"“{texto}” não é uma classe de tolerância: escreva a letra e o grau, como H7 ou s6."
        )
    letra, grau = achado.group(1), int(achado.group(2))
    if letra.lower() == "js":
        letra = "JS" if letra[0].isupper() else "js"
    if letra not in LETRAS_DE_EIXO and letra not in LETRAS_DE_FURO:
        raise ErroDeAjuste(
            f"A letra {letra} não está nesta página. Furos: {', '.join(LETRAS_DE_FURO)}. "
            f"Eixos: {', '.join(LETRAS_DE_EIXO)}."
        )
    if grau not in _IT:
        raise ErroDeAjuste(f"O grau {grau} não existe: a norma vai de IT1 a IT18.")
    return Classe(letra, grau)


@dataclass(frozen=True)
class Zona:
    """O campo de tolerância de uma classe numa dimensão: afastamentos em µm."""

    classe: Classe
    d: float
    superior: float
    inferior: float

    @property
    def tolerancia(self) -> float:
        return self.superior - self.inferior

    @property
    def maxima(self) -> float:
        return self.d + self.superior / 1000.0

    @property
    def minima(self) -> float:
        return self.d + self.inferior / 1000.0


def afastamentos_do_eixo(letra: str, grau: int, d: float) -> tuple[float, float]:
    """(es, ei) do eixo, em µm."""
    it = tolerancia(grau, d)
    if letra == "js":
        meia = _js(grau, d)
        return meia, -meia
    lado, valor = _fundamental_do_eixo(letra, grau, d)
    if lado == "es":
        return valor, valor - it
    return valor + it, valor


def afastamentos_do_furo(letra: str, grau: int, d: float) -> tuple[float, float]:
    """(ES, EI) do furo, em µm."""
    it = tolerancia(grau, d)
    minuscula = letra.lower()
    if minuscula == "js":
        meia = _js(grau, d)
        return meia, -meia
    lado, valor = _fundamental_do_eixo(minuscula, grau, d)
    if lado == "es":  # A a H: EI = −es
        inferior = -valor
        return inferior + it, inferior
    if letra == "M" and grau == 6 and 250.0 < d <= 315.0:
        superior = -9.0  # nota D da Tabela 3
    elif letra in ("K", "M", "N"):
        superior = _superior_de_k_m_n(letra, grau, d)
    elif grau <= 7:  # P a U até IT7: ES = −ei + Δ
        superior = -valor + (delta(grau, d) if grau >= 3 else 0.0)
    else:  # P a U acima de IT7: ES = −ei
        superior = -valor
    return superior, superior - it


def _superior_de_k_m_n(letra: str, grau: int, d: float) -> float:
    i = _indice(FAIXAS, d)
    pequeno = d <= 3.0
    if letra == "K":
        if grau > 8:
            if not pequeno:
                raise ErroDeAjuste("A Tabela 3 só dá o furo K até IT8 acima de 3 mm.")
            return 0.0  # até 3 mm, K acima de IT8 tem ES = 0
        base = 0.0 if pequeno else -float(_EI["k"][i])
    elif letra == "M":
        base = -float(_EI["m"][i])
        if grau > 8:
            return base
    else:
        if grau > 8:
            if d <= 1.0:
                raise ErroDeAjuste("O furo N acima de IT8 não vale para dimensões até 1 mm.")
            return -float(_EI["n"][i]) if pequeno else 0.0
        base = -float(_EI["n"][i])
    if grau < 3:
        raise ErroDeAjuste(
            f"Os furos K, M e N usam o Δ da Tabela 3, que começa em IT3, e não em IT{grau}."
        )
    return base + delta(grau, d)


def zona(texto: str | Classe, d: float) -> Zona:
    c = texto if isinstance(texto, Classe) else classe(texto)
    if c.furo:
        superior, inferior = afastamentos_do_furo(c.letra, c.grau, d)
    else:
        superior, inferior = afastamentos_do_eixo(c.letra, c.grau, d)
    return Zona(c, float(d), superior + 0.0, inferior + 0.0)  # + 0.0 tira o −0 do H e do h


@dataclass(frozen=True)
class Ajuste:
    d: float
    furo: Zona
    eixo: Zona

    @property
    def nome(self) -> str:
        return f"{self.furo.classe.nome}/{self.eixo.classe.nome}"

    @property
    def folga_maxima(self) -> float:
        """Furo no máximo com o eixo no mínimo, em µm. Negativo é interferência."""
        return self.furo.superior - self.eixo.inferior

    @property
    def folga_minima(self) -> float:
        return self.furo.inferior - self.eixo.superior

    @property
    def interferencia_maxima(self) -> float:
        return -self.folga_minima

    @property
    def interferencia_minima(self) -> float:
        return -self.folga_maxima

    @property
    def tipo(self) -> str:
        if self.folga_minima >= 0.0:
            return COM_FOLGA
        if self.folga_maxima <= 0.0:
            return COM_INTERFERENCIA
        return INCERTO

    @property
    def sistema(self) -> str:
        if self.furo.classe.letra == "H":
            return "Furo-base"
        if self.eixo.classe.letra == "h":
            return "Eixo-base"
        return "Livre"


def ajuste(d: float, furo: str | Classe, eixo: str | Classe) -> Ajuste:
    zona_do_furo, zona_do_eixo = zona(furo, d), zona(eixo, d)
    if not zona_do_furo.classe.furo:
        raise ErroDeAjuste("A classe do furo vai com letra maiúscula, como H7.")
    if zona_do_eixo.classe.furo:
        raise ErroDeAjuste("A classe do eixo vai com letra minúscula, como s6.")
    return Ajuste(float(d), zona_do_furo, zona_do_eixo)


def ajuste_pelo_nome(d: float, nome: str) -> Ajuste:
    """ "H7/s6" → o ajuste."""
    partes = str(nome).replace(" ", "").split("/")
    if len(partes) != 2:
        raise ErroDeAjuste(f"“{nome}” não é um ajuste: escreva furo/eixo, como H7/s6.")
    return ajuste(d, partes[0], partes[1])


# ---------------------------------------------------------------------------------------------
# Ajustes recomendados (os preferidos da ISO 286-2, nos dois sistemas)
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class AjusteRecomendado:
    nome: str
    uso: str


RECOMENDADOS = (
    AjusteRecomendado("H11/c11", "Folga larga: peças que dilatam muito ou montagem grosseira."),
    AjusteRecomendado("H9/d9", "Folga livre: mancal com variação grande de temperatura."),
    AjusteRecomendado("H8/f7", "Folga de giro: eixo girando em bucha, com lubrificação."),
    AjusteRecomendado("H7/g6", "Deslizante: peça que corre no eixo com pouca folga."),
    AjusteRecomendado("H7/h6", "Localização com folga: monta e desmonta à mão."),
    AjusteRecomendado("H7/k6", "Incerto, de localização: monta com macete."),
    AjusteRecomendado("H7/n6", "Incerto, mais preso: monta com prensa leve."),
    AjusteRecomendado("H7/p6", "Interferência leve: localização rígida, sem transmitir torque."),
    AjusteRecomendado("H7/r6", "Interferência média: transmite torque pequeno."),
    AjusteRecomendado("H7/s6", "Interferência forte: transmite torque, monta com prensa."),
    AjusteRecomendado("H7/u6", "Forçado: torque alto, monta a quente ou a frio."),
    AjusteRecomendado("C11/h11", "Eixo-base, folga larga."),
    AjusteRecomendado("D9/h9", "Eixo-base, folga livre."),
    AjusteRecomendado("F8/h7", "Eixo-base, folga de giro."),
    AjusteRecomendado("G7/h6", "Eixo-base, deslizante."),
    AjusteRecomendado("K7/h6", "Eixo-base, incerto de localização."),
    AjusteRecomendado("N7/h6", "Eixo-base, incerto mais preso."),
    AjusteRecomendado("P7/h6", "Eixo-base, interferência leve."),
    AjusteRecomendado("S7/h6", "Eixo-base, interferência forte."),
    AjusteRecomendado("U7/h6", "Eixo-base, forçado."),
)
POR_NOME = {a.nome: a for a in RECOMENDADOS}


def recomendados(d: float) -> list[Ajuste]:
    """Os ajustes preferidos que existem nesta dimensão (t, por exemplo, só acima de 24 mm)."""
    lista = []
    for item in RECOMENDADOS:
        try:
            lista.append(ajuste_pelo_nome(d, item.nome))
        except ErroDeAjuste:
            continue
    return lista


# ---------------------------------------------------------------------------------------------
# Aperto de um ajuste com interferência (o cálculo do Assistente de cargas)
# ---------------------------------------------------------------------------------------------

#: Os dados do aperto, sem o diâmetro e a interferência, que vêm do ajuste escolhido.
CAMPOS_DO_APERTO = tuple(
    c for c in ee.CAMPOS_AJUSTE if c.chave not in ("d_mm", "ajuste", "delta_min_um", "delta_max_um")
)
PADROES_DO_APERTO = {c.chave: c.padrao for c in CAMPOS_DO_APERTO}


def aperto(a: Ajuste, valores: Mapping[str, Any]) -> Resultado:
    """Pressão, torque que o atrito segura, tensões e montagem, com a interferência do ajuste."""
    if a.interferencia_maxima <= 0.0:
        raise ErroDeAjuste(f"O ajuste {a.nome} não tem interferência: não há aperto para calcular.")
    dados = {**PADROES_DO_APERTO, **dict(valores)}
    dados.update(
        d_mm=a.d,
        ajuste=ee.AJUSTE_MANUAL,
        delta_min_um=a.interferencia_minima,
        delta_max_um=a.interferencia_maxima,
    )
    if a.interferencia_minima <= 0.0:
        raise ErroDeAjuste(
            f"O ajuste {a.nome} é incerto: no pior caso ele fica com folga e não segura nada por "
            "atrito. Para transmitir torque, escolha um ajuste com interferência."
        )
    return ee.calcular_ajuste(dados)


@dataclass(frozen=True)
class Escolha:
    ajuste: Ajuste
    uso: str
    transmite: bool | None  # None: sem interferência, não se aplica
    escoa: bool | None
    aquecimento: float | None


def escolher(d: float, valores: Mapping[str, Any] | None = None) -> list[Escolha]:
    """Cada ajuste recomendado na dimensão, e, com os dados do aperto, se ele segura e se escoa."""
    lista = []
    for a in recomendados(d):
        transmite: bool | None = None
        escoa: bool | None = None
        aquecimento: float | None = None
        if valores is not None and a.tipo == COM_INTERFERENCIA:
            try:
                r = aperto(a, valores)
            except ValueError:
                transmite = False
            else:
                por_nome = {v.nome: v for v in r.verificacoes}
                transmite = por_nome["Transmissão por atrito"].status == "OK"
                escoa = not (
                    por_nome["Escoamento no furo do cubo"].status == "OK"
                    and por_nome["Escoamento na superfície do eixo"].status == "OK"
                )
                aquecimento = next(
                    (float(m.valor) for m in r.metricas if m.rotulo == "Aquecimento para montar"),
                    None,
                )
        lista.append(Escolha(a, POR_NOME[a.nome].uso, transmite, escoa, aquecimento))
    return lista


def melhor_que_segura(escolhas: list[Escolha]) -> Escolha | None:
    """O ajuste mais leve que transmite sem escoar: menos aperto é montagem mais fácil."""
    servem = [e for e in escolhas if e.transmite and e.escoa is False]
    return min(servem, key=lambda e: e.ajuste.interferencia_maxima, default=None)


# ---------------------------------------------------------------------------------------------
# Texto para o desenho e para o registro
# ---------------------------------------------------------------------------------------------


def numero(valor: float, casas: int = 3) -> str:
    texto = f"{valor:.{casas}f}"
    if "." in texto:  # só os zeros depois da vírgula: 190 continua 190
        texto = texto.rstrip("0").rstrip(".")
    return texto.replace(".", ",") if texto not in ("-0", "") else "0"


def cota_do_desenho(z: Zona) -> str:
    """Como vai no desenho: Ø50 H7 (+0,025 / 0)."""

    def em_mm(valor: float) -> str:
        if valor == 0.0:
            return "0"
        return f"{valor / 1000.0:+.3f}".replace(".", ",")

    d = numero(z.d, 3)
    return f"Ø{d} {z.classe.nome} ({em_mm(z.superior)} / {em_mm(z.inferior)})"


def linhas_das_zonas(a: Ajuste) -> list[dict[str, str]]:
    """A tabela do furo e do eixo: afastamentos em µm e dimensões em mm."""
    return [
        {
            "Peça": peca,
            "Classe": z.classe.nome,
            "Afastamento superior (µm)": numero(z.superior, 1),
            "Afastamento inferior (µm)": numero(z.inferior, 1),
            "Tolerância (µm)": numero(z.tolerancia, 1),
            "Dimensão máxima (mm)": numero(z.maxima, 4),
            "Dimensão mínima (mm)": numero(z.minima, 4),
        }
        for peca, z in (("Furo", a.furo), ("Eixo", a.eixo))
    ]


def resumo(a: Ajuste) -> str:
    if a.tipo == COM_FOLGA:
        return (
            f"Ø{numero(a.d)} {a.nome}: ajuste com folga, de {numero(a.folga_minima, 1)} a "
            f"{numero(a.folga_maxima, 1)} µm."
        )
    if a.tipo == COM_INTERFERENCIA:
        return (
            f"Ø{numero(a.d)} {a.nome}: ajuste com interferência, de "
            f"{numero(a.interferencia_minima, 1)} a {numero(a.interferencia_maxima, 1)} µm."
        )
    return (
        f"Ø{numero(a.d)} {a.nome}: ajuste incerto, de {numero(a.interferencia_maxima, 1)} µm de "
        f"interferência a {numero(a.folga_maxima, 1)} µm de folga."
    )


def registro(
    a: Ajuste, aperto_calculado: Resultado | None = None, valores: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """O registro no projeto: o ajuste, e o aperto quando ele foi calculado."""
    from core.technical_records import criar_registro_tecnico
    from core.verificacao import (
        STATUS_REGISTRO,
        linhas_para_registro,
        numero_json,
        status_geral,
    )

    verificacoes = list(aperto_calculado.verificacoes) if aperto_calculado is not None else []
    status = (
        STATUS_REGISTRO.get(status_geral(verificacoes), "Pendente") if verificacoes else ("Atende")
    )
    texto = resumo(a)
    if aperto_calculado is not None:
        texto += " " + decimal_ptbr(aperto_calculado.resumo)
    entradas: dict[str, Any] = {
        "diametro_mm": numero_json(a.d, 4),
        "classe_do_furo": a.furo.classe.nome,
        "classe_do_eixo": a.eixo.classe.nome,
    }
    if aperto_calculado is not None and valores is not None:
        entradas["aperto"] = {
            chave: (numero_json(float(v), 6) if isinstance(v, (int, float)) else str(v))
            for chave, v in valores.items()
        }
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=f"Ajuste Ø{numero(a.d)} {a.nome}",
        status=status,
        resumo=texto,
        entradas=entradas,
        resultados={
            "tipo": a.tipo,
            "folga_minima_um": numero_json(a.folga_minima, 1),
            "folga_maxima_um": numero_json(a.folga_maxima, 1),
            "furo": cota_do_desenho(a.furo),
            "eixo": cota_do_desenho(a.eixo),
            "verificações": linhas_para_registro(verificacoes),
            "destaque_memorial": texto,
            "tabelas_memorial": [
                {
                    "legenda": f"Ajuste Ø{numero(a.d)} {a.nome} pela NBR 6158.",
                    "cabecalhos": list(linhas_das_zonas(a)[0]),
                    "linhas": [list(linha.values()) for linha in linhas_das_zonas(a)],
                    "fonte": 7.5,
                }
            ],
        },
        metodo=(
            "Graus de tolerância (Tabela 1) e afastamentos fundamentais (Tabelas 2 e 3) da NBR "
            "6158. Folga máxima = ES − ei; folga mínima = EI − es. Com interferência, a pressão "
            "sai de Lamé (Shigley, cap. 3), com a interferência útil descontada da rugosidade."
        ),
        premissas=[
            "Peças à mesma temperatura, a 20 °C, sem erro de forma.",
            *(list(aperto_calculado.hipoteses) if aperto_calculado is not None else []),
        ],
        referencias=[REFERENCIA, *(aperto_calculado.referencias if aperto_calculado else ())],
        conclusao=texto,
    )
