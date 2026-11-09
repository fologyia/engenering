"""Funções do montador que não têm forma fechada: a letra fica na fórmula, e o número sai daqui.

O fator de atrito é o caso típico: Colebrook é implícita. Na fórmula ele aparece como f(Re, ε/D), e
a conta numérica resolve por iteração. Os fatores de Marin e a sensibilidade ao entalhe vão por trás
da mesma porta: mudam de fórmula por faixa, e o diâmetro pedido pode estar dentro deles. Quem
acrescentar outra função assim registra em ``FUNCOES``, para o motor saber calcular com ela em número.

As contas de fadiga são as de ``core/elementos_eixos.py`` e ``core/fatigue.py``, escritas para receber
vetores: o Assistente de cargas e o Montador têm de dar o mesmo número.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np
import sympy as sp

from core import elementos_eixos as ee
from core import elementos_mancais as em
from core import fatigue as ft

RE_LAMINAR = 2300.0
RE_TURBULENTO = 4000.0
_ITERACOES = 12


def _colebrook(re: np.ndarray, relativa: np.ndarray) -> np.ndarray:
    """Ponto fixo em 1/√f, partindo de Haaland: converge em poucas voltas em todo o ábaco de Moody."""
    x = -1.8 * np.log10((relativa / 3.7) ** 1.11 + 6.9 / re)
    for _ in range(_ITERACOES):
        x = -2.0 * np.log10(relativa / 3.7 + 2.51 * x / re)
    return 1.0 / x**2


def fator_de_atrito(re: Any, relativa: Any) -> Any:
    """f de Darcy: 64/Re no laminar, Colebrook no turbulento e uma reta entre os dois.

    Na transição o escoamento não tem um f definido. A reta só mantém a conta contínua, para a busca
    da raiz não saltar; quem cai nessa faixa recebe aviso.
    """
    re = np.asarray(re, dtype=float)
    relativa = np.asarray(relativa, dtype=float)
    with np.errstate(all="ignore"):
        no_limite = np.full(re.shape, RE_TURBULENTO)
        turbulento = _colebrook(np.maximum(re, RE_TURBULENTO), relativa)
        fim_da_transicao = _colebrook(no_limite, relativa)
        peso = (re - RE_LAMINAR) / (RE_TURBULENTO - RE_LAMINAR)
        transicao = (1.0 - peso) * 64.0 / RE_LAMINAR + peso * fim_da_transicao
        f = np.where(
            re <= RE_LAMINAR,
            64.0 / re,
            np.where(re < RE_TURBULENTO, transicao, turbulento),
        )
    f = np.where(re > 0.0, f, np.nan)
    return float(f) if f.ndim == 0 else f


class AtritoDarcy(sp.Function):
    """f(Re, ε/D): a sympy trata como uma letra positiva, e o número vem de ``fator_de_atrito``."""

    nargs = 2
    is_real = True
    is_positive = True

    def _eval_evalf(self, prec: int) -> sp.Float | None:
        re, relativa = self.args
        if re.is_number and relativa.is_number:
            return sp.Float(float(fator_de_atrito(float(re), float(relativa))), prec)
        return None

    def _latex(self, printer: Any, exp: Any = None) -> str:
        re, relativa = self.args
        texto = f"f\\left({printer.doprint(re)},\\,{printer.doprint(relativa)}\\right)"
        return f"{texto}^{{{printer.doprint(exp)}}}" if exp is not None else texto


def _em_vetor(funcao: Callable[..., float]) -> Callable[..., Any]:
    """Uma conta de um número passa a aceitar vetores. Valor fora do válido vira nan."""

    def um(*numeros: float) -> float:
        try:
            return float(funcao(*numeros))
        except (ValueError, ZeroDivisionError, OverflowError):
            return math.nan

    vetorizada = np.vectorize(um, otypes=[float])

    def chamar(*numeros: Any) -> Any:
        resposta = vetorizada(*numeros)
        return float(resposta) if np.ndim(resposta) == 0 else resposta

    return chamar


#: A posição é o número que entra na fórmula: a sympy só guarda números.
MATERIAIS_DE_FADIGA = ("aco", "ferro_fundido", "aluminio", "cobre")
_NOME_EM_FADIGA = {"aco": "aco", "ferro_fundido": "ferro", "aluminio": "aluminio", "cobre": "cobre"}


def _limite_base(sut: float, indice: float) -> float:
    return ft.se_linha(sut, _NOME_EM_FADIGA[MATERIAIS_DE_FADIGA[int(indice)]])[0]


def _superficie(sut: float, a: float, b: float) -> float:
    return min(a * sut**b, 1.0)


def _tamanho(d: float) -> float:
    return ft.fator_tamanho(min(d, 254.0), "flexao", "shigley") if d >= 2.79 else 1.0


def _sensibilidade(sut: float, raio: float, torcao: float) -> float:
    return ee.sensibilidade(sut, raio, "torcao" if torcao else "flexao")


def _kt(diametro_maior: float, d: float, raio: float, torcao: float) -> float:
    if d <= 0.0:
        return math.nan
    return ee.kt_ressalto(diametro_maior, d, raio, "torcao" if torcao else "flexao")


def _vida(s_1000: float, se: float, ciclos: float) -> float:
    """S_f(N) da reta log-log entre 10³ e 10⁶ ciclos. Depois de 10⁶ segue caindo: a favor."""
    return s_1000 * (ciclos / 1e3) ** (math.log10(se / s_1000) / 3.0)


#: A ordem dos ajustes é o número que entra na fórmula, como nos materiais de fadiga.
AJUSTES_DO_CUBO = tuple(ee.AJUSTES)


def _chaveta(d: float, coluna: int) -> float:
    """b, h ou t₁ da DIN 6885-1, em mm. Fora da tabela, a conta não existe."""
    return ee.chaveta_din(d)[coluna]


def _interferencia(d: float, indice: float, maxima: int) -> float:
    """Interferência do ajuste H7 da NBR 6158 na base, em mm: a tabela dá em µm."""
    return ee.interferencia_do_ajuste(d, AJUSTES_DO_CUBO[int(indice)])[maxima] / 1000.0


def _equivalente_esferas(radial: float, axial: float, c0: float) -> float:
    """P = máx(F_r; X·F_r + Y·F_a), com X e Y da Tabela 11-1 de Shigley, como no Assistente."""
    x, y, _ = em.fatores_xy(axial, radial, c0)
    return max(radial, x * radial + y * axial)


def _equivalente_xy(radial: float, axial: float, x: float, y: float) -> float:
    return max(radial, x * radial + y * axial)


def _estatica(radial: float, axial: float) -> float:
    """P₀ = máx(F_r; 0,6·F_r + 0,5·F_a), a do rolamento rígido de esferas."""
    return max(radial, 0.6 * radial + 0.5 * axial)


limite_base = _em_vetor(_limite_base)
fator_de_superficie = _em_vetor(_superficie)
fator_de_tamanho = _em_vetor(_tamanho)
sensibilidade_neuber = _em_vetor(_sensibilidade)
kt_do_ressalto = _em_vetor(_kt)
resistencia_em_vida = _em_vetor(_vida)
largura_da_chaveta = _em_vetor(lambda d: _chaveta(d, 0))
altura_da_chaveta = _em_vetor(lambda d: _chaveta(d, 1))
rasgo_da_chaveta = _em_vetor(lambda d: _chaveta(d, 2))
interferencia_minima = _em_vetor(lambda d, i: _interferencia(d, i, 0))
interferencia_maxima = _em_vetor(lambda d, i: _interferencia(d, i, 1))
carga_equivalente_esferas = _em_vetor(_equivalente_esferas)
carga_equivalente_xy = _em_vetor(_equivalente_xy)
carga_estatica = _em_vetor(_estatica)


class _Numerica(sp.Function):
    """Uma função que a sympy trata como uma letra positiva, com o número vindo de fora."""

    is_real = True
    is_positive = True
    funcao: Any = None
    texto = ""

    def _eval_evalf(self, prec: int) -> sp.Float | None:
        if all(a.is_number for a in self.args):
            valor = type(self).funcao(*(float(a) for a in self.args))
            return sp.Float(float(valor), prec)
        return None

    def _latex(self, printer: Any, exp: Any = None) -> str:
        texto = self.texto
        return f"{texto}^{{{printer.doprint(exp)}}}" if exp is not None else texto


class LimiteBase(_Numerica):
    nargs = 2
    funcao = staticmethod(limite_base)
    texto = "S_{e}'"


class FatorSuperficie(_Numerica):
    nargs = 3
    funcao = staticmethod(fator_de_superficie)
    texto = "k_{a}"


class FatorTamanho(_Numerica):
    nargs = 1
    funcao = staticmethod(fator_de_tamanho)
    texto = "k_{b}"


class SensibilidadeNeuber(_Numerica):
    nargs = 3
    funcao = staticmethod(sensibilidade_neuber)
    texto = "q"


class KtRessalto(_Numerica):
    nargs = 4
    funcao = staticmethod(kt_do_ressalto)
    texto = "K_{t}"


class ResistenciaEmVida(_Numerica):
    nargs = 3
    funcao = staticmethod(resistencia_em_vida)
    texto = "S_{f}"


class LarguraDaChaveta(_Numerica):
    nargs = 1
    funcao = staticmethod(largura_da_chaveta)
    texto = "b_{ch}"


class AlturaDaChaveta(_Numerica):
    nargs = 1
    funcao = staticmethod(altura_da_chaveta)
    texto = "h_{ch}"


class RasgoDaChaveta(_Numerica):
    nargs = 1
    funcao = staticmethod(rasgo_da_chaveta)
    texto = "t_{1}"


class InterferenciaMinima(_Numerica):
    nargs = 2
    funcao = staticmethod(interferencia_minima)
    texto = "\\delta_{mín}"


class InterferenciaMaxima(_Numerica):
    nargs = 2
    funcao = staticmethod(interferencia_maxima)
    texto = "\\delta_{máx}"


class CargaEquivalenteEsferas(_Numerica):
    nargs = 3
    funcao = staticmethod(carga_equivalente_esferas)
    texto = "P"


class CargaEquivalenteXY(_Numerica):
    nargs = 4
    funcao = staticmethod(carga_equivalente_xy)
    texto = "P"


class CargaEstatica(_Numerica):
    nargs = 2
    funcao = staticmethod(carga_estatica)
    texto = "P_{0}"


#: Elas não têm forma fechada: simplificar não adianta e custa caro.
NUMERICAS: tuple[type[sp.Function], ...] = (
    AtritoDarcy,
    LimiteBase,
    FatorSuperficie,
    FatorTamanho,
    SensibilidadeNeuber,
    KtRessalto,
    ResistenciaEmVida,
    LarguraDaChaveta,
    AlturaDaChaveta,
    RasgoDaChaveta,
    InterferenciaMinima,
    InterferenciaMaxima,
    CargaEquivalenteEsferas,
    CargaEquivalenteXY,
    CargaEstatica,
)
#: As que vêm de tabela ou de escolha: a planilha leva o valor calculado, e não uma fórmula.
TABELADAS: tuple[type[sp.Function], ...] = (
    KtRessalto,
    LarguraDaChaveta,
    AlturaDaChaveta,
    RasgoDaChaveta,
    InterferenciaMinima,
    InterferenciaMaxima,
    CargaEquivalenteEsferas,
)
#: O que o ``lambdify`` precisa para calcular estas funções em número.
FUNCOES: dict[str, Any] = {
    "AtritoDarcy": fator_de_atrito,
    "LimiteBase": limite_base,
    "FatorSuperficie": fator_de_superficie,
    "FatorTamanho": fator_de_tamanho,
    "SensibilidadeNeuber": sensibilidade_neuber,
    "KtRessalto": kt_do_ressalto,
    "ResistenciaEmVida": resistencia_em_vida,
    "LarguraDaChaveta": largura_da_chaveta,
    "AlturaDaChaveta": altura_da_chaveta,
    "RasgoDaChaveta": rasgo_da_chaveta,
    "InterferenciaMinima": interferencia_minima,
    "InterferenciaMaxima": interferencia_maxima,
    "CargaEquivalenteEsferas": carga_equivalente_esferas,
    "CargaEquivalenteXY": carga_equivalente_xy,
    "CargaEstatica": carga_estatica,
}
