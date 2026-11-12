"""Propriedades dos fluidos pela CoolProp: a letra fica na fórmula, e o número vem da biblioteca.

Funciona como o fator de atrito: na conta simbólica, ρ da água é ρ(T, p), uma função das letras da
temperatura e da pressão. Na hora do número, a CoolProp calcula, pelo modelo de referência de cada
fluido (a água pela IAPWS-95). Assim a temperatura pode ser a letra pedida: "até que temperatura a
bomba não cavita" vira uma conta como outra qualquer.

Fora da faixa de um fluido, ou num estado que não existe, a função dá "sem número", e a conta trata
como trata uma raiz de negativo. A CoolProp só é carregada quando uma conta precisa dela.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache, lru_cache
from typing import Any

import numpy as np
import sympy as sp

from core import montador_grandezas as g


@dataclass(frozen=True)
class Fluido:
    rotulo: str
    coolprop: str
    curto: str  # para a fórmula: ρ da água sai como ρ_água
    liquido: bool  # na linha de fluidos, que é de líquido incompressível
    saturacao: bool  # tem pressão de vapor


#: Os nomes conferidos na CoolProp 8. Os incompressíveis (INCOMP::) são líquidos de tabela: valem só
#: na faixa de temperatura deles, e não têm estado de vapor.
FLUIDOS: tuple[Fluido, ...] = (
    Fluido("Água", "Water", "água", True, True),
    Fluido("Etanol", "Ethanol", "etanol", True, True),
    Fluido("Etilenoglicol a 30 % em água", "INCOMP::MEG-30%", "MEG", True, False),
    Fluido("Propilenoglicol a 30 % em água", "INCOMP::MPG-30%", "MPG", True, False),
    Fluido("Óleo térmico Therminol 66", "INCOMP::T66", "T66", True, False),
    Fluido("Óleo térmico Therminol VP-1", "INCOMP::TVP1", "VP1", True, False),
    Fluido("Óleo de silicone Syltherm 800", "INCOMP::S800", "S800", True, False),
    Fluido("Óleo térmico Dowtherm Q", "INCOMP::DowQ", "DowQ", True, False),
    Fluido("Ar seco", "Air", "ar", False, False),
    Fluido("Nitrogênio", "Nitrogen", "N_2", False, False),
    Fluido("CO₂ (R744)", "CarbonDioxide", "CO_2", False, True),
    Fluido("Amônia (R717)", "Ammonia", "NH_3", False, True),
    Fluido("R134a", "R134a", "R134a", False, True),
    Fluido("Metano", "Methane", "CH_4", False, True),
)
POR_ROTULO = {f.rotulo: f for f in FLUIDOS}


@dataclass(frozen=True)
class Saida:
    coolprop: str
    dimensao: str
    simbolo: str  # LaTeX
    positiva: bool


RHO, MU, PV, CP, K, H, S, T, P, X, PR = range(11)
SAIDAS: tuple[Saida, ...] = (
    Saida("D", g.MASSA_ESPECIFICA, "\\rho", True),
    Saida("V", g.VISCOSIDADE, "\\mu", True),
    Saida("P", g.PRESSAO, "p_{v}", True),
    Saida("C", g.CALOR_ESPECIFICO, "c_{p}", True),
    Saida("L", g.CONDUTIVIDADE, "k", True),
    Saida("H", g.ENERGIA_ESPECIFICA, "h", False),
    Saida("S", g.ENTROPIA_ESPECIFICA, "s", False),
    Saida("T", g.TEMPERATURA, "T", True),
    Saida("P", g.PRESSAO, "p", True),
    Saida("Q", g.PURO, "x", False),
    Saida("Prandtl", g.PURO, "Pr", True),
)
#: As duas entradas de cada estado. Título x = 0 é o líquido saturado.
TP, TX, PX, PH, PS = range(5)
PARES: tuple[tuple[str, str], ...] = (("T", "P"), ("T", "Q"), ("P", "Q"), ("P", "H"), ("P", "S"))


@cache
def _coolprop() -> Any:
    import CoolProp.CoolProp as biblioteca  # noqa: N813  (carrega só quando uma conta precisa)

    return biblioteca


def versao() -> str:
    return str(_coolprop().get_global_param_string("version"))


@cache
def faixa_de_temperatura(fluido: int) -> tuple[float, float]:
    """A faixa em que o modelo do fluido vale, em K."""
    biblioteca = _coolprop()
    nome = FLUIDOS[fluido].coolprop
    return float(biblioteca.PropsSI("Tmin", nome)), float(biblioteca.PropsSI("Tmax", nome))


@lru_cache(maxsize=65536)
def _um(fluido: int, saida: int, par: int, a: float, b: float) -> float:
    entrada_a, entrada_b = PARES[par]
    try:
        valor = float(
            _coolprop().PropsSI(
                SAIDAS[saida].coolprop, entrada_a, a, entrada_b, b, FLUIDOS[fluido].coolprop
            )
        )
    except ValueError:
        return math.nan
    return valor if math.isfinite(valor) else math.nan


def propriedade(fluido: Any, saida: Any, par: Any, a: Any, b: Any) -> Any:
    """A conta em número, de um valor ou de uma grade inteira. Estado que não existe vira nan."""
    f, s, e = int(fluido), int(saida), int(par)
    va, vb = np.broadcast_arrays(np.asarray(a, dtype=float), np.asarray(b, dtype=float))
    if va.ndim == 0:
        return _um(f, s, e, float(va), float(vb))
    planos_a, planos_b = va.ravel(), vb.ravel()
    resultado = np.full(planos_a.shape, np.nan)
    validos = np.isfinite(planos_a) & np.isfinite(planos_b)
    if PARES[e][0] == "T":
        minimo, maximo = faixa_de_temperatura(f)
        validos &= (planos_a >= minimo) & (planos_a <= maximo)
    if validos.any():
        entrada_a, entrada_b = PARES[e]
        try:
            valores = np.asarray(
                _coolprop().PropsSI(
                    SAIDAS[s].coolprop,
                    entrada_a,
                    planos_a[validos],
                    entrada_b,
                    planos_b[validos],
                    FLUIDOS[f].coolprop,
                ),
                dtype=float,
            )
        except ValueError:
            valores = np.array(
                [
                    _um(f, s, e, float(x), float(y))
                    for x, y in zip(planos_a[validos], planos_b[validos], strict=True)
                ]
            )
        resultado[validos] = np.where(np.isfinite(valores), valores, np.nan)
    return resultado.reshape(va.shape)


class Propriedade(sp.Function):
    """ρ, μ, p_v, c_p, h, s… de um fluido, em função de duas letras do estado.

    Os três primeiros argumentos são números inteiros: o fluido, a saída e o par de entradas, nas
    tabelas deste módulo. Os dois últimos são as letras do estado.
    """

    nargs = 5
    is_real = True

    def _eval_is_positive(self) -> bool | None:
        saida = self.args[1]
        return True if saida.is_Integer and SAIDAS[int(saida)].positiva else None

    def _eval_evalf(self, prec: int) -> sp.Float | None:
        if all(a.is_number for a in self.args):
            try:
                valor = float(propriedade(*(float(a) for a in self.args)))
            except (TypeError, ValueError):
                return None
            return sp.Float(valor, prec) if math.isfinite(valor) else None
        return None

    def _latex(self, printer: Any, exp: Any = None) -> str:
        fluido, saida, par, a, b = self.args
        simbolo = SAIDAS[int(saida)].simbolo
        nome = FLUIDOS[int(fluido)].curto
        if par in (TX, PX) and b == 0:
            dentro = printer.doprint(a)  # saturação: só a temperatura ou a pressão
        else:
            dentro = f"{printer.doprint(a)},\\,{printer.doprint(b)}"
        base, _, indice = simbolo.partition("_")
        indice = indice.strip("{}")
        rotulo = (
            f"{base}_{{{indice},\\mathrm{{{nome}}}}}"
            if indice
            else f"{base}_{{\\mathrm{{{nome}}}}}"
        )
        texto = f"{rotulo}\\left({dentro}\\right)"
        return f"\\left({texto}\\right)^{{{printer.doprint(exp)}}}" if exp is not None else texto

    def rotulo_word(self) -> tuple[str, str]:
        """A letra e o índice no Word, onde a fórmula fica com o nome do fluido embaixo."""
        fluido, saida = int(self.args[0]), int(self.args[1])
        simbolo = SAIDAS[saida].simbolo.replace("\\", "")
        base, _, indice = simbolo.partition("_")
        nome = FLUIDOS[fluido].curto
        trocas = {"rho": "ρ", "mu": "μ"}
        return trocas.get(base, base), f"{indice.strip('{}')},{nome}" if indice else nome


def _f(fluido: Fluido, saida: int, par: int, a: sp.Expr, b: sp.Expr) -> sp.Expr:
    return Propriedade(sp.Integer(FLUIDOS.index(fluido)), sp.Integer(saida), sp.Integer(par), a, b)


def massa_especifica(fluido: Fluido, t: sp.Expr, p: sp.Expr) -> sp.Expr:
    return _f(fluido, RHO, TP, t, p)


def viscosidade(fluido: Fluido, t: sp.Expr, p: sp.Expr) -> sp.Expr:
    return _f(fluido, MU, TP, t, p)


def pressao_de_vapor(fluido: Fluido, t: sp.Expr) -> sp.Expr:
    return _f(fluido, PV, TX, t, sp.Integer(0))


def temperatura_de_saturacao(fluido: Fluido, p: sp.Expr) -> sp.Expr:
    return _f(fluido, T, PX, p, sp.Integer(0))


#: Para o ``lambdify``: o nome da classe vira a função que calcula em número.
FUNCOES: dict[str, Callable[..., Any]] = {"Propriedade": propriedade}

__all__ = [
    "FLUIDOS",
    "FUNCOES",
    "Fluido",
    "POR_ROTULO",
    "Propriedade",
    "SAIDAS",
    "faixa_de_temperatura",
    "massa_especifica",
    "pressao_de_vapor",
    "propriedade",
    "temperatura_de_saturacao",
    "versao",
    "viscosidade",
]
