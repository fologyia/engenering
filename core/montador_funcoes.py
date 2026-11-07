"""Funções do montador que não têm forma fechada: a letra fica na fórmula, e o número sai daqui.

O fator de atrito é o caso típico: Colebrook é implícita. Na fórmula ele aparece como f(Re, ε/D), e
a conta numérica resolve por iteração. Quem acrescentar outra função assim registra em ``FUNCOES``,
para o motor saber calcular com ela em número.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import sympy as sp

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


#: O que o ``lambdify`` precisa para calcular estas funções em número.
FUNCOES: dict[str, Any] = {"AtritoDarcy": fator_de_atrito}
