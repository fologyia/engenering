"""Funções do montador que não têm forma fechada: a letra fica na fórmula, e o número sai daqui.

O fator de atrito é o caso típico: Colebrook é implícita. Na fórmula ele aparece como f(Re, ε/D), e
a conta numérica resolve por iteração. Os fatores de Marin e a sensibilidade ao entalhe vão por trás
da mesma porta: mudam de fórmula por faixa, e o diâmetro pedido pode estar dentro deles. Quem
acrescentar outra função assim registra em ``FUNCOES``, para o motor saber calcular com ela em número.

As contas de fadiga são as de ``core/elementos_eixos.py`` e ``core/fatigue.py``, escritas para receber
vetores: o Cálculo de peças e o Montador têm de dar o mesmo número.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np
import sympy as sp
from fluids import fittings as ff
from fluids import flow_meter as fm

from core import elementos_eixos as ee
from core import elementos_mancais as em
from core import elementos_molas_atrito as ema
from core import elementos_transmissao as et
from core import fatigue as ft
from core.montador_propriedades import FUNCOES as FUNCOES_DAS_PROPRIEDADES
from core.montador_propriedades import Propriedade

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
            try:  # um número de dentro sem valor (a água abaixo de 0 °C) deixa o f sem valor
                valor = float(fator_de_atrito(float(re), float(relativa)))
            except (TypeError, ValueError):
                return None
            return sp.Float(valor, prec) if math.isfinite(valor) else None
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
#: S_cr da coluna por Johnson ou por Euler, conforme a esbeltez: a mesma do fuso no Assistente.
tensao_critica_coluna = _em_vetor(ema.tensao_critica_coluna)
#: Y de Lewis pela Tabela 14-2 de Shigley, a mesma do Assistente: abaixo de 12 dentes não existe.
fator_de_lewis = _em_vetor(et.fator_lewis)


class _Numerica(sp.Function):
    """Uma função que a sympy trata como uma letra positiva, com o número vindo de fora."""

    is_real = True
    is_positive = True
    funcao: Any = None
    texto = ""

    def _eval_evalf(self, prec: int) -> sp.Float | None:
        if all(a.is_number for a in self.args):
            try:  # um número de dentro que ficou sem valor deixa esta sem valor também
                valor = float(type(self).funcao(*(float(a) for a in self.args)))
            except (TypeError, ValueError):
                return None
            return sp.Float(valor, prec)
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


class FatorLewis(_Numerica):
    nargs = 1
    funcao = staticmethod(fator_de_lewis)
    texto = "Y"


class TensaoCritica(_Numerica):
    nargs = 3
    funcao = staticmethod(tensao_critica_coluna)
    texto = "S_{cr}"


#: As peças pelo método do Crane (Flow of Fluids, TP-410), com o f_T de escoamento todo turbulento em
#: tubo de aço novo, que depende do diâmetro. As contas são as da biblioteca ``fluids``: válvula de
#: passagem plena, sem redução. As curvas e os tês vão pelo múltiplo de f_T da tabela do Crane.
def _vezes_ft(n: float) -> Callable[[float], float]:
    return lambda d: n * ff.ft_Crane(d)


PECAS_CRANE: tuple[tuple[str, Callable[[float], float]], ...] = (
    ("Cotovelo 90° padrão (30·f_T)", _vezes_ft(30.0)),
    ("Curva 90°, r/D = 1 (20·f_T)", lambda d: ff.bend_rounded_Crane(d, 90.0, bend_diameters=1.0)),
    ("Curva 90°, r/D = 1,5", lambda d: ff.bend_rounded_Crane(d, 90.0, bend_diameters=1.5)),
    ("Curva 90°, r/D = 3", lambda d: ff.bend_rounded_Crane(d, 90.0, bend_diameters=3.0)),
    ("Cotovelo 45° padrão (16·f_T)", _vezes_ft(16.0)),
    ("Curva de retorno 180° (50·f_T)", _vezes_ft(50.0)),
    ("Tê, passagem direta (20·f_T)", _vezes_ft(20.0)),
    ("Tê, saída lateral (60·f_T)", _vezes_ft(60.0)),
    ("Registro de gaveta aberto (8·f_T)", lambda d: ff.K_gate_valve_Crane(d, d, 0.0)),
    ("Válvula de globo aberta (340·f_T)", lambda d: ff.K_globe_valve_Crane(d, d)),
    ("Válvula angular aberta (150·f_T)", lambda d: ff.K_angle_valve_Crane(d, d, style=1)),
    ("Válvula de esfera aberta (3·f_T)", lambda d: ff.K_ball_valve_Crane(d, d, 0.0)),
    ("Válvula macho, passagem reta (18·f_T)", lambda d: ff.K_plug_valve_Crane(d, d, 0.0)),
    ("Válvula borboleta centrada (45, 35 ou 25·f_T)", lambda d: ff.K_butterfly_valve_Crane(d)),
    ("Retenção de portinhola (100·f_T)", lambda d: ff.K_swing_check_valve_Crane(D=d)),
    (
        "Retenção de portinhola, passagem livre (50·f_T)",
        lambda d: ff.K_swing_check_valve_Crane(D=d, angled=False),
    ),
    (
        "Retenção de levantamento (600·f_T)",
        lambda d: ff.K_lift_check_valve_Crane(d, d, angled=False),
    ),
    ("Entrada de canto vivo (K = 0,5)", lambda d: 0.5),
    ("Saída para reservatório (K = 1)", lambda d: 1.0),
)
#: As tomadas da placa de orifício da ISO 5167-2, na ordem do número que entra na fórmula.
TOMADAS_DO_ORIFICIO = ("corner", "flange", "D")


def _k_crane(d: float, indice: float) -> float:
    return PECAS_CRANE[int(indice)][1](d) if d > 0.0 else math.nan


def _c_do_orificio(d: float, garganta: float, re: float, tomada: float) -> float:
    """C de Reader-Harris/Gallagher (ISO 5167-2:2003, eq. 4). Com μ = 1, a vazão em massa dá Re."""
    if d <= 0.0 or garganta <= 0.0 or garganta >= d or re <= 0.0:
        return math.nan
    return fm.C_Reader_Harris_Gallagher(
        d, garganta, 1.0, 1.0, re * math.pi * d / 4.0, TOMADAS_DO_ORIFICIO[int(tomada)]
    )


k_do_crane = _em_vetor(_k_crane)
coeficiente_do_orificio = _em_vetor(_c_do_orificio)


class KCrane(_Numerica):
    nargs = 2
    funcao = staticmethod(k_do_crane)
    texto = "K_{Crane}"

    def _latex(self, printer: Any, exp: Any = None) -> str:
        texto = f"K_{{Crane}}\\left({printer.doprint(self.args[0])}\\right)"
        return f"{texto}^{{{printer.doprint(exp)}}}" if exp is not None else texto


class CoeficienteOrificio(_Numerica):
    nargs = 4
    funcao = staticmethod(coeficiente_do_orificio)
    texto = "C"

    def _latex(self, printer: Any, exp: Any = None) -> str:
        d, garganta, re, _ = (printer.doprint(a) for a in self.args)
        texto = f"C\\left({garganta}/{d},\\,{re}\\right)"
        return f"{texto}^{{{printer.doprint(exp)}}}" if exp is not None else texto


#: Elas não têm forma fechada: simplificar não adianta e custa caro.
NUMERICAS: tuple[type[sp.Function], ...] = (
    Propriedade,
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
    FatorLewis,
    TensaoCritica,
    KCrane,
    CoeficienteOrificio,
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
    FatorLewis,
)
#: As que vêm de uma biblioteca de fora, como as propriedades dos fluidos pela CoolProp: a planilha
#: leva o valor calculado, porque o Excel não tem a biblioteca.
DA_BIBLIOTECA: tuple[type[sp.Function], ...] = (Propriedade, KCrane, CoeficienteOrificio)
#: O que o ``lambdify`` precisa para calcular estas funções em número.
FUNCOES: dict[str, Any] = {
    **FUNCOES_DAS_PROPRIEDADES,
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
    "FatorLewis": fator_de_lewis,
    "TensaoCritica": tensao_critica_coluna,
    "KCrane": k_do_crane,
    "CoeficienteOrificio": coeficiente_do_orificio,
}
