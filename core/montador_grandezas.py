"""As letras do montador de fórmulas: nome, dimensão e unidade de cada grandeza.

A conta simbólica não conhece unidade. Os números entram nela sempre na base N, mm e MPa, que fecha
sozinha (1 MPa = 1 N/mm²), e a tela só converte na entrada e na saída.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import sympy as sp

MEDIDA = "medida"  # da seção
COMPRIMENTO = "comprimento"  # da peça: vão, altura da coluna
FORCA = "forca"
MOMENTO = "momento"
DISTRIBUIDA = "distribuida"
TENSAO = "tensao"
MODULO = "modulo"
POTENCIA = "potencia"
ROTACAO = "rotacao"
ANGULO = "angulo"
PURO = "puro"
FLECHA_EI = "flecha_ei"  # δ·E·I: a flecha da viga, sem saber a seção

MEDIDAS = {"mm": 1.0, "cm": 10.0, "m": 1000.0}
FORCAS = {"N": 1.0, "kN": 1000.0}
MOMENTOS = {"N·mm": 1.0, "N·m": 1000.0, "kN·m": 1e6}


@dataclass(frozen=True)
class Unidades:
    """As unidades da tela. Base da conta: N, mm e MPa."""

    medida: str = "mm"
    comprimento: str = "m"
    forca: str = "kN"
    momento: str = "kN·m"

    def fator(self, dimensao: str) -> float:
        """Multiplica o número da tela para chegar na base."""
        if dimensao == MEDIDA:
            return MEDIDAS[self.medida]
        if dimensao == COMPRIMENTO:
            return MEDIDAS[self.comprimento]
        if dimensao == FORCA:
            return FORCAS[self.forca]
        if dimensao == MOMENTO:
            return MOMENTOS[self.momento]
        if dimensao == DISTRIBUIDA:
            return FORCAS[self.forca] / MEDIDAS[self.comprimento]
        if dimensao == FLECHA_EI:
            return FORCAS[self.forca] * MEDIDAS[self.comprimento] ** 3
        return {MODULO: 1000.0, POTENCIA: 1e6, ANGULO: math.pi / 180.0}.get(dimensao, 1.0)

    def rotulo(self, dimensao: str) -> str:
        if dimensao == MEDIDA:
            return self.medida
        if dimensao == COMPRIMENTO:
            return self.comprimento
        if dimensao == FORCA:
            return self.forca
        if dimensao == MOMENTO:
            return self.momento
        if dimensao == DISTRIBUIDA:
            return f"{self.forca}/{self.comprimento}"
        if dimensao == FLECHA_EI:
            return f"{self.forca}·{self.comprimento}³"
        return {
            TENSAO: "MPa",
            MODULO: "GPa",
            POTENCIA: "kW",
            ROTACAO: "rpm",
            ANGULO: "°",
        }.get(dimensao, "")


#: Em que base está cada dimensão na fórmula com números, para quem for usá-la fora do programa.
UNIDADE_BASE = {
    MEDIDA: "mm",
    COMPRIMENTO: "mm",
    FORCA: "N",
    MOMENTO: "N·mm",
    DISTRIBUIDA: "N/mm",
    TENSAO: "MPa",
    MODULO: "MPa",
    POTENCIA: "N·mm/s",
    ROTACAO: "rpm",
    ANGULO: "rad",
    FLECHA_EI: "N·mm³",
}


@dataclass(frozen=True)
class Grandeza:
    """Uma letra das fórmulas. ``chave`` é o nome do símbolo, e o LaTeX sai dele: S_y vira S_{y}."""

    chave: str
    texto: str  # a letra para rótulo sem LaTeX
    nome: str
    dimensao: str
    ajuda: str
    padrao: float | None = None  # na base N, mm, MPa
    aumentar_alivia: bool | None = None  # só para as sugestões de medida comercial

    @property
    def simbolo(self) -> sp.Symbol:
        # Tudo positivo: esforço entra pelo módulo, e assim √(M²) simplifica para M.
        return sp.Symbol(self.chave, positive=True)

    def com_indice(self, indice: int) -> Grandeza:
        """A segunda flexão da mesma seção é outra letra: M₂, e não o mesmo M somado duas vezes."""
        if indice <= 1:
            return self
        return replace(
            self,
            chave=f"{self.chave}_{indice}",
            texto=f"{self.texto}{indice}",
            nome=f"{self.nome} {indice}",
        )


def _g(
    chave: str,
    texto: str,
    nome: str,
    dimensao: str,
    ajuda: str,
    padrao: float | None = None,
) -> Grandeza:
    return Grandeza(chave, texto, nome, dimensao, ajuda, padrao)


# Esforços
M = _g("M_x", "M_x", "Momento em XX", MOMENTO, "Momento em torno de XX: flete no plano de h.")
MY = _g("M_y", "M_y", "Momento em YY", MOMENTO, "Momento em torno de YY: flete no plano de b.")
F_XX = _g(
    "F_xx", "F_xx", "Força do momento em XX", FORCA, "A força que, com o braço, dá o momento em XX."
)
D_XX = _g(
    "d_xx", "d_xx", "Distância do momento em XX", COMPRIMENTO, "O braço da força até a seção."
)
F_YY = _g(
    "F_yy", "F_yy", "Força do momento em YY", FORCA, "A força que, com o braço, dá o momento em YY."
)
D_YY = _g(
    "d_yy", "d_yy", "Distância do momento em YY", COMPRIMENTO, "O braço da força até a seção."
)
N = _g("N", "N", "Força normal", FORCA, "Tração ou compressão ao longo da peça.")
V = _g("V_y", "V_y", "Cortante vertical", FORCA, "Cortante no plano de h: vem junto com M_x.")
VX = _g("V_x", "V_x", "Cortante horizontal", FORCA, "Cortante no plano de b: vem junto com M_y.")
T = _g("T", "T", "Torque", MOMENTO, "O momento que torce a peça em volta do eixo dela.")
F = _g("F", "F", "Força aplicada", FORCA, "A carga concentrada na viga.")
Q = _g("q", "q", "Carga distribuída", DISTRIBUIDA, "Carga por comprimento ao longo da viga.")
P_INT = _g("p", "p", "Pressão interna", TENSAO, "Pressão do fluido dentro do tubo.")
POT = _g("P", "P", "Potência", POTENCIA, "Potência transmitida pelo eixo.")
ROT = _g("n_rot", "n_rot", "Rotação", ROTACAO, "Rotação do eixo.")
L = _g("L", "L", "Comprimento", COMPRIMENTO, "Vão da viga, altura da coluna ou trecho do eixo.")

# Medidas de seção
D = _g("d", "d", "Diâmetro", MEDIDA, "Diâmetro externo da seção.")
PAREDE = _g("t", "t", "Espessura da parede", MEDIDA, "Espessura da parede do tubo.")
RELACAO = _g("k", "k", "Relação d_i/d", PURO, "Diâmetro interno dividido pelo externo: 0 a 1.")
B = _g("b", "b", "Base", MEDIDA, "Largura da seção, perpendicular ao plano da flexão.")
H = _g("h", "h", "Altura", MEDIDA, "Altura da seção, no plano da flexão.")
BF = _g("b_f", "b_f", "Largura da mesa", MEDIDA, "Largura de cada mesa do perfil.")
TF = _g("t_f", "t_f", "Espessura da mesa", MEDIDA, "Espessura de cada mesa do perfil.")
TW = _g("t_w", "t_w", "Espessura da alma", MEDIDA, "Espessura da alma do perfil.")
ESCALA = _g(
    "s",
    "s",
    "Escala do desenho",
    PURO,
    "Multiplica todas as medidas da seção desenhada. 1 é o desenho como está.",
    1.0,
)

# Material e segurança
SY = _g("S_y", "S_y", "Limite de escoamento", TENSAO, "Tensão em que o material escoa.")
SUT = _g("S_ut", "S_ut", "Limite de ruptura", TENSAO, "Tensão em que o material rompe.")
SE = _g("S_e", "S_e", "Limite de fadiga corrigido", TENSAO, "Já com os fatores de Marin.")
E = _g("E", "E", "Módulo de elasticidade", MODULO, "Aço: 200 GPa.", 200000.0)
G = _g("G", "G", "Módulo de cisalhamento", MODULO, "Aço: 80 GPa.", 80000.0)
FS = _g("n", "n", "Fator de segurança", PURO, "Quantas vezes a falha fica acima da carga.", 1.5)

# Coeficientes
KT = _g("K_t", "K_t", "Concentração de tensão normal", PURO, "1 é sem concentração.", 1.0)
KTS = _g("K_ts", "K_ts", "Concentração de cisalhamento", PURO, "1 é sem concentração.", 1.0)
KF = _g("K_f", "K_f", "Fator de fadiga na flexão", PURO, "1 é sem entalhe.", 1.0)
KFS = _g("K_fs", "K_fs", "Fator de fadiga na torção", PURO, "1 é sem entalhe.", 1.0)
K_FLAMB = _g(
    "K",
    "K",
    "Coeficiente de flambagem",
    PURO,
    "1 biarticulada, 0,7 engastada e articulada, 0,5 biengastada, 2 em balanço.",
    1.0,
)

# Fadiga
MA = _g("M_a", "M_a", "Momento alternado", MOMENTO, "Metade da variação do momento.")
MM = _g("M_m", "M_m", "Momento médio", MOMENTO, "A média do momento no ciclo.")
TA = _g("T_a", "T_a", "Torque alternado", MOMENTO, "Metade da variação do torque.")
TM = _g("T_m", "T_m", "Torque médio", MOMENTO, "A média do torque no ciclo.")

# Limites de deformação
RELACAO_FLECHA = _g(
    "r_delta", "L/δ", "Relação vão por flecha", PURO, "300 quer dizer flecha até L/300.", 300.0
)
DELTA_ADM = _g(
    "delta_adm", "δ_adm", "Flecha admissível", MEDIDA, "A maior flecha que a peça pode ter."
)
PHI_ADM = _g("phi_adm", "φ_adm", "Giro admissível", ANGULO, "O maior giro que o trecho pode ter.")

# Só para ligar blocos
FLECHA = _g(
    "Delta_EI", "δ·EI", "Flecha vezes E·I", FLECHA_EI, "Vem do bloco de viga, que não sabe a seção."
)
