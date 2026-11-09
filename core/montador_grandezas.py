"""As letras do montador de fórmulas: nome, dimensão e unidade de cada grandeza.

A conta simbólica não conhece unidade. Os números entram nela sempre na base do sistema, e a tela só
converte na entrada e na saída. Cada parte do Montador tem o seu sistema: materiais, estática e fadiga
usam N, mm e MPa, que fecha sozinho (1 MPa = 1 N/mm²); fluidos usam o SI, com m, kg, s, Pa e W.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
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
GIRO_EI = "giro_ei"  # θ·E·I: a inclinação da viga, sem saber a seção
MASSA = "massa"
MICRO = "micro"  # interferência e rugosidade, em µm
TEMPO = "tempo"

# Só de fluidos
DIAMETRO = "diametro"
VAZAO = "vazao"
VELOCIDADE = "velocidade"
PRESSAO = "pressao"
ALTURA = "altura"
MASSA_ESPECIFICA = "massa_especifica"
VISCOSIDADE = "viscosidade"
RUGOSIDADE = "rugosidade"
AREA = "area"
VOLUME = "volume"
ACELERACAO = "aceleracao"
INERCIA = "inercia"
CURVA_BOMBA = "curva_bomba"  # a da parábola H = H_0 − a·Q²

#: Potências de força, comprimento e tempo de cada dimensão. Como cada sistema fecha sozinho na base,
#: é por aqui que se confere se uma fórmula tem os dois lados na mesma unidade.
EXPOENTES: dict[str, tuple[int, int, int]] = {
    MEDIDA: (0, 1, 0),
    COMPRIMENTO: (0, 1, 0),
    FORCA: (1, 0, 0),
    MOMENTO: (1, 1, 0),
    DISTRIBUIDA: (1, -1, 0),
    TENSAO: (1, -2, 0),
    MODULO: (1, -2, 0),
    POTENCIA: (1, 1, -1),
    ROTACAO: (0, 0, -1),
    ANGULO: (0, 0, 0),
    PURO: (0, 0, 0),
    FLECHA_EI: (1, 3, 0),
    GIRO_EI: (1, 2, 0),
    MASSA: (1, -1, 2),
    MICRO: (0, 1, 0),
    TEMPO: (0, 0, 1),
    DIAMETRO: (0, 1, 0),
    VAZAO: (0, 3, -1),
    VELOCIDADE: (0, 1, -1),
    PRESSAO: (1, -2, 0),
    ALTURA: (0, 1, 0),
    MASSA_ESPECIFICA: (1, -4, 2),
    VISCOSIDADE: (1, -2, 1),
    RUGOSIDADE: (0, 1, 0),
    AREA: (0, 2, 0),
    VOLUME: (0, 3, 0),
    ACELERACAO: (0, 1, -2),
    INERCIA: (0, 4, 0),
    CURVA_BOMBA: (0, -5, 2),
}
ROTULOS_DAS_DIMENSOES = {
    PURO: "Número puro",
    MEDIDA: "Medida da seção",
    COMPRIMENTO: "Comprimento",
    FORCA: "Força",
    MOMENTO: "Momento",
    DISTRIBUIDA: "Carga distribuída",
    TENSAO: "Tensão",
    MODULO: "Módulo do material",
    POTENCIA: "Potência",
    ROTACAO: "Rotação",
    ANGULO: "Ângulo",
    FLECHA_EI: "Flecha vezes E·I",
    GIRO_EI: "Inclinação vezes E·I",
    MASSA: "Massa",
    MICRO: "Medida fina, em µm",
    TEMPO: "Tempo",
    DIAMETRO: "Diâmetro",
    VAZAO: "Vazão",
    VELOCIDADE: "Velocidade",
    PRESSAO: "Pressão",
    ALTURA: "Altura",
    MASSA_ESPECIFICA: "Massa específica",
    VISCOSIDADE: "Viscosidade",
    RUGOSIDADE: "Rugosidade",
    AREA: "Área",
    VOLUME: "Volume",
    ACELERACAO: "Aceleração",
    INERCIA: "Momento de inércia",
    CURVA_BOMBA: "Queda da curva da bomba",
}

MEDIDAS = {"mm": 1.0, "cm": 10.0, "m": 1000.0}
FORCAS = {"N": 1.0, "kN": 1000.0}
MOMENTOS = {"N·mm": 1.0, "N·m": 1000.0, "kN·m": 1e6}


@dataclass(frozen=True, eq=False)
class Seletor:
    """Uma unidade que a pessoa escolhe na tela."""

    dimensao: str
    rotulo: str
    ajuda: str
    opcoes: Mapping[str, float]  # multiplica o número da tela para chegar na base
    padrao: str


@dataclass(frozen=True, eq=False)
class Sistema:
    chave: str
    seletores: tuple[Seletor, ...]
    fixas: Mapping[str, tuple[str, float]]
    derivadas: Mapping[str, Callable[[Unidades], tuple[str, float]]]
    aviso_da_base: str
    dimensoes: tuple[str, ...] = ()  # o que uma letra nova pode ser, nesta ordem


@dataclass(frozen=True, eq=False)
class Unidades:
    """As unidades escolhidas na tela, na ordem dos seletores do sistema."""

    sistema: Sistema
    escolhas: tuple[str, ...]

    def par(self, dimensao: str) -> tuple[str, float]:
        for seletor, escolha in zip(self.sistema.seletores, self.escolhas, strict=True):
            if seletor.dimensao == dimensao:
                return escolha, seletor.opcoes[escolha]
        if dimensao in self.sistema.fixas:
            return self.sistema.fixas[dimensao]
        derivada = self.sistema.derivadas.get(dimensao)
        return derivada(self) if derivada else ("", 1.0)

    def fator(self, dimensao: str) -> float:
        """Multiplica o número da tela para chegar na base."""
        return self.par(dimensao)[1]

    def rotulo(self, dimensao: str) -> str:
        return self.par(dimensao)[0]


def unidades_padrao(sistema: Sistema) -> Unidades:
    return Unidades(sistema, tuple(s.padrao for s in sistema.seletores))


def _distribuida(u: Unidades) -> tuple[str, float]:
    return (
        f"{u.rotulo(FORCA)}/{u.rotulo(COMPRIMENTO)}",
        u.fator(FORCA) / u.fator(COMPRIMENTO),
    )


def _flecha_ei(u: Unidades) -> tuple[str, float]:
    return (
        f"{u.rotulo(FORCA)}·{u.rotulo(COMPRIMENTO)}³",
        u.fator(FORCA) * u.fator(COMPRIMENTO) ** 3,
    )


def _giro_ei(u: Unidades) -> tuple[str, float]:
    return (
        f"{u.rotulo(FORCA)}·{u.rotulo(COMPRIMENTO)}²",
        u.fator(FORCA) * u.fator(COMPRIMENTO) ** 2,
    )


SISTEMA_SOLIDOS = Sistema(
    "solidos",
    (
        Seletor(
            MEDIDA,
            "Seção",
            "Unidade das medidas da seção. Trocar converte os números.",
            MEDIDAS,
            "mm",
        ),
        Seletor(
            COMPRIMENTO,
            "Comprimento",
            "Unidade dos comprimentos da peça: vão, coluna, trecho de eixo e braço da força.",
            MEDIDAS,
            "m",
        ),
        Seletor(FORCA, "Força", "Unidade das forças. Trocar converte os números.", FORCAS, "kN"),
        Seletor(
            MOMENTO,
            "Momento",
            "Unidade dos momentos e torques. Trocar converte os números.",
            MOMENTOS,
            "kN·m",
        ),
    ),
    {
        TENSAO: ("MPa", 1.0),
        MODULO: ("GPa", 1000.0),
        POTENCIA: ("kW", 1e6),
        ROTACAO: ("rpm", 1.0),
        ANGULO: ("°", math.pi / 180.0),
        PURO: ("", 1.0),
        AREA: ("mm²", 1.0),
        VOLUME: ("mm³", 1.0),
        INERCIA: ("mm⁴", 1.0),
        # Massa em t, porque N = t·mm/s²: a conta de rotação crítica fecha sozinha em N, mm e s.
        MASSA: ("kg", 1e-3),
        MASSA_ESPECIFICA: ("kg/m³", 1e-12),
        MICRO: ("µm", 1e-3),
        TEMPO: ("h", 3600.0),
    },
    {DISTRIBUIDA: _distribuida, FLECHA_EI: _flecha_ei, GIRO_EI: _giro_ei},
    "Com números, a fórmula está na base: forças em N, medidas em mm, tensões em MPa.",
    (
        PURO,
        MEDIDA,
        COMPRIMENTO,
        FORCA,
        MOMENTO,
        DISTRIBUIDA,
        TENSAO,
        MODULO,
        POTENCIA,
        ROTACAO,
        ANGULO,
        AREA,
        VOLUME,
        INERCIA,
        FLECHA_EI,
        GIRO_EI,
        MASSA,
        MASSA_ESPECIFICA,
        MICRO,
        TEMPO,
    ),
)

SISTEMA_FLUIDOS = Sistema(
    "fluidos",
    (
        Seletor(
            DIAMETRO,
            "Diâmetro",
            "Unidade dos diâmetros de tubo. Trocar converte os números.",
            {"mm": 1e-3, "cm": 1e-2, "m": 1.0, "pol": 0.0254},
            "mm",
        ),
        Seletor(
            COMPRIMENTO,
            "Comprimento",
            "Unidade do comprimento dos trechos. Trocar converte os números.",
            {"m": 1.0, "km": 1000.0},
            "m",
        ),
        Seletor(
            VAZAO,
            "Vazão",
            "Unidade da vazão. Trocar converte os números.",
            {"m³/h": 1.0 / 3600.0, "m³/s": 1.0, "L/s": 1e-3, "L/min": 1e-3 / 60.0},
            "m³/h",
        ),
        Seletor(
            PRESSAO,
            "Pressão",
            "Unidade das pressões. mca é metro de coluna d'água.",
            {"kPa": 1e3, "Pa": 1.0, "bar": 1e5, "mca": 9806.65},
            "kPa",
        ),
        Seletor(
            POTENCIA,
            "Potência",
            "Unidade das potências. Trocar converte os números.",
            {"kW": 1e3, "W": 1.0, "cv": 735.49875},
            "kW",
        ),
    ),
    {
        ALTURA: ("m", 1.0),
        VELOCIDADE: ("m/s", 1.0),
        MASSA_ESPECIFICA: ("kg/m³", 1.0),
        VISCOSIDADE: ("mPa·s", 1e-3),
        RUGOSIDADE: ("mm", 1e-3),
        AREA: ("m²", 1.0),
        VOLUME: ("m³", 1.0),
        ACELERACAO: ("m/s²", 1.0),
        FORCA: ("N", 1.0),
        PURO: ("", 1.0),
        CURVA_BOMBA: ("m/(m³/h)²", 3600.0**2),
    },
    {},
    "Com números, a fórmula está no SI: metros, segundos, quilogramas, pascals e watts.",
    (
        PURO,
        ALTURA,
        DIAMETRO,
        COMPRIMENTO,
        RUGOSIDADE,
        FORCA,
        VAZAO,
        VELOCIDADE,
        PRESSAO,
        POTENCIA,
        MASSA_ESPECIFICA,
        VISCOSIDADE,
        AREA,
        VOLUME,
        ACELERACAO,
        CURVA_BOMBA,
    ),
)


@dataclass(frozen=True)
class Grandeza:
    """Uma letra das fórmulas. ``chave`` é o nome do símbolo, e o LaTeX sai dele: S_y vira S_{y}."""

    chave: str
    texto: str  # a letra para rótulo sem LaTeX
    nome: str
    dimensao: str
    ajuda: str
    padrao: float | None = None  # na base do sistema
    zero_ok: bool = False  # esforço pode ser zero; medida e limite, não
    maximo: float | None = None  # valor que não pode ser alcançado, como k = 1
    minimo: float | None = None  # o menor valor que faz sentido, como K_t = 1
    teto: float | None = None  # o maior valor que faz sentido, como q = 1

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

    def problema_no_valor(self, valor: float) -> str | None:
        """O que está errado com este número, em palavras de quem preencheu."""
        if not math.isfinite(valor):
            return f"{self.texto}: o valor não é um número."
        if valor < 0.0:
            if self.zero_ok:
                return f"{self.texto} entra pelo módulo: digite o valor sem o sinal."
            return f"{self.texto} precisa ser maior que zero."
        if valor == 0.0 and not self.zero_ok:
            return f"{self.texto} precisa ser maior que zero."
        if self.maximo is not None and valor >= self.maximo:
            limite = f"{self.maximo:g}".replace(".", ",")
            return f"{self.texto} precisa ficar abaixo de {limite}."
        if self.minimo is not None and valor < self.minimo:
            limite = f"{self.minimo:g}".replace(".", ",")
            return f"{self.texto} precisa ser pelo menos {limite}."
        if self.teto is not None and valor > self.teto:
            limite = f"{self.teto:g}".replace(".", ",")
            return f"{self.texto} vai no máximo até {limite}."
        return None


def _g(
    chave: str,
    texto: str,
    nome: str,
    dimensao: str,
    ajuda: str,
    padrao: float | None = None,
) -> Grandeza:
    return Grandeza(chave, texto, nome, dimensao, ajuda, padrao)


def _esforco(chave: str, texto: str, nome: str, dimensao: str, ajuda: str) -> Grandeza:
    return Grandeza(chave, texto, nome, dimensao, ajuda, zero_ok=True)


# Esforços
M = _esforco("M_x", "M_x", "Momento em XX", MOMENTO, "Momento em torno de XX: flete no plano de h.")
MY = _esforco(
    "M_y", "M_y", "Momento em YY", MOMENTO, "Momento em torno de YY: flete no plano de b."
)
F_XX = _esforco(
    "F_xx", "F_xx", "Força do momento em XX", FORCA, "A força que, com o braço, dá o momento em XX."
)
D_XX = _esforco(
    "d_xx", "d_xx", "Distância do momento em XX", COMPRIMENTO, "O braço da força até a seção."
)
F_YY = _esforco(
    "F_yy", "F_yy", "Força do momento em YY", FORCA, "A força que, com o braço, dá o momento em YY."
)
D_YY = _esforco(
    "d_yy", "d_yy", "Distância do momento em YY", COMPRIMENTO, "O braço da força até a seção."
)
N = _esforco("N", "N", "Força normal", FORCA, "Tração ou compressão ao longo da peça.")
V = _esforco("V_y", "V_y", "Cortante vertical", FORCA, "Cortante no plano de h: vem junto com M_x.")
VX = _esforco(
    "V_x", "V_x", "Cortante horizontal", FORCA, "Cortante no plano de b: vem junto com M_y."
)
T = _esforco("T", "T", "Torque", MOMENTO, "O momento que torce a peça em volta do eixo dela.")
F = _esforco("F", "F", "Força aplicada", FORCA, "A carga concentrada na viga.")
Q = _esforco("q", "q", "Carga distribuída", DISTRIBUIDA, "Carga por comprimento ao longo da viga.")
P_INT = _esforco("p", "p", "Pressão interna", TENSAO, "Pressão do fluido dentro do tubo.")
POT = _esforco("P", "P", "Potência", POTENCIA, "Potência transmitida pelo eixo.")
ROT = _g("n_rot", "n_rot", "Rotação", ROTACAO, "Rotação do eixo.")
L = _g("L", "L", "Comprimento", COMPRIMENTO, "Vão da viga, altura da coluna ou trecho do eixo.")

# Medidas de seção
D = _g("d", "d", "Diâmetro", MEDIDA, "Diâmetro externo da seção.")
PAREDE = _g("t", "t", "Espessura da parede", MEDIDA, "Espessura da parede do tubo.")
RELACAO = Grandeza(
    "k",
    "k",
    "Relação d_i/d",
    PURO,
    "Diâmetro interno dividido pelo externo: 0 a 1.",
    zero_ok=True,
    maximo=1.0,
)
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
E = _g(
    "E", "E", "Módulo de elasticidade", MODULO, "Aço: 200 GPa. Alumínio: cerca de 70 GPa.", 200000.0
)
G = _g(
    "G", "G", "Módulo de cisalhamento", MODULO, "Aço: 80 GPa. Alumínio: cerca de 27 GPa.", 80000.0
)
FS = _g("n", "n", "Fator de segurança", PURO, "Quantas vezes a falha fica acima da carga.", 1.5)

# Coeficientes
KT = replace(
    _g("K_t", "K_t", "Concentração de tensão normal", PURO, "1 é sem concentração.", 1.0),
    minimo=1.0,
)
KTS = replace(
    _g("K_ts", "K_ts", "Concentração de cisalhamento", PURO, "1 é sem concentração.", 1.0),
    minimo=1.0,
)
KF = replace(
    _g("K_f", "K_f", "Fator de fadiga na flexão", PURO, "1 é sem entalhe.", 1.0), minimo=1.0
)
KFS = replace(
    _g("K_fs", "K_fs", "Fator de fadiga na torção", PURO, "1 é sem entalhe.", 1.0), minimo=1.0
)
K_FLAMB = _g(
    "K",
    "K",
    "Coeficiente de flambagem",
    PURO,
    "1 biarticulada, 0,7 engastada e articulada, 0,5 biengastada, 2 em balanço.",
    1.0,
)

# Fadiga
MA = _esforco("M_a", "M_a", "Momento alternado", MOMENTO, "Metade da variação do momento.")
MM = _esforco("M_m", "M_m", "Momento médio", MOMENTO, "A média do momento no ciclo.")
TA = _esforco("T_a", "T_a", "Torque alternado", MOMENTO, "Metade da variação do torque.")
TM = _esforco("T_m", "T_m", "Torque médio", MOMENTO, "A média do torque no ciclo.")
K_TAMANHO = _g(
    "k_b", "k_b", "Fator de tamanho", PURO, "De Marin. Peça de 50 mm: cerca de 0,81.", 0.85
)
K_TEMPERATURA = _g("k_d", "k_d", "Fator de temperatura", PURO, "1 até cerca de 300 °C.", 1.0)
K_CONFIANCA = _g("k_e", "k_e", "Fator de confiabilidade", PURO, "1 é 50 %. 0,814 é 99 %.", 1.0)
K_DIVERSOS = _g(
    "k_div",
    "k_div",
    "Fator de efeitos diversos",
    PURO,
    "Corrosão, revestimento, solda. 1 quando não há nada disso.",
    1.0,
)
N_CICLOS = replace(
    _g(
        "N_c",
        "N_c",
        "Vida pedida",
        PURO,
        "Ciclos até a falha, de mil a um milhão. Acima disso é vida infinita.",
        1e6,
    ),
    minimo=1e3,
)
D_MAIOR = _g("D_r", "D_r", "Diâmetro maior do ressalto", MEDIDA, "O lado grosso do ressalto.")
R_ENTALHE = _g("r_e", "r_e", "Raio de concordância", MEDIDA, "O raio do canto do ressalto.")
Q_NORMAL = replace(
    _g("q_e", "q_e", "Sensibilidade na flexão", PURO, "De 0 a 1. Na dúvida, 1 a favor.", 1.0),
    teto=1.0,
)
Q_CORTE = replace(
    _g("q_es", "q_es", "Sensibilidade na torção", PURO, "De 0 a 1. Na dúvida, 1 a favor.", 1.0),
    teto=1.0,
)

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

# Engrenagem e polia
D_ENGRENAGEM = _g(
    "d_g",
    "d_g",
    "Diâmetro primitivo da engrenagem",
    MEDIDA,
    "Na engrenagem reta, d = m·z. Na helicoidal, d = m_n·z/cos ψ.",
)
PHI_N = Grandeza(
    "phi_n",
    "φ_n",
    "Ângulo de pressão",
    ANGULO,
    "20° é o padrão. 14,5° em engrenagens antigas, e 25° em algumas de carga alta.",
    math.radians(20.0),
    maximo=math.radians(45.0),
)
PSI = Grandeza(
    "psi",
    "ψ",
    "Ângulo de hélice",
    ANGULO,
    "Zero na engrenagem reta. Na helicoidal, de 15° a 30°.",
    0.0,
    zero_ok=True,
    maximo=math.radians(60.0),
)
D_POLIA = _g(
    "d_pol",
    "d_pol",
    "Diâmetro da polia",
    MEDIDA,
    "Diâmetro primitivo da polia que está neste eixo.",
)
MU_CORREIA = Grandeza(
    "mu_c",
    "μ_c",
    "Atrito da correia",
    PURO,
    "Borracha em polia de ferro fundido: cerca de 0,3. Na correia em V, a cunha entra à parte.",
    0.3,
)
THETA_ABRACAMENTO = Grandeza(
    "theta_c",
    "θ_c",
    "Abraçamento na polia menor",
    ANGULO,
    "180° com polias iguais. Com polias diferentes, é o ângulo na polia menor que manda.",
    math.pi,
    maximo=2.0 * math.pi,
)

# Vigas e eixos
A_CARGA = _g(
    "a_m",
    "a_m",
    "Distância da carga ao apoio",
    COMPRIMENTO,
    "Da carga até o apoio mais perto dela: no máximo L/2.",
)
C_BALANCO = _g(
    "c_b", "c_b", "Balanço da carga", COMPRIMENTO, "Do mancal até a carga que fica do lado de fora."
)
F_1 = _esforco("F_1", "F_1", "Primeira força", FORCA, "A força mais perto do apoio A.")
F_2 = _esforco("F_2", "F_2", "Segunda força", FORCA, "A força mais perto do apoio B.")
A_1 = _g("a_1", "a_1", "Posição da primeira força", COMPRIMENTO, "Do apoio A até a primeira força.")
A_2 = _g("a_2", "a_2", "Posição da segunda força", COMPRIMENTO, "Do apoio A até a segunda força.")

# Rigidez do eixo
THETA_ADM = _g(
    "theta_adm",
    "θ_adm",
    "Inclinação admissível",
    ANGULO,
    "O maior giro da seção que o mancal ou a engrenagem aceitam.",
)
RHO_EIXO = _g(
    "rho_e",
    "ρ_e",
    "Massa específica do eixo",
    MASSA_ESPECIFICA,
    "Aço: 7850 kg/m³. Alumínio: 2700 kg/m³.",
    7850e-12,
)
M_PECA = _g("m_p", "m_p", "Massa da peça", MASSA, "Engrenagem, polia ou volante preso no eixo.")
F_CRITICA = replace(
    _g(
        "f_cr",
        "f_cr",
        "Folga da rotação crítica",
        PURO,
        "Quantas vezes a rotação crítica fica acima da de trabalho. 1,3 é o mínimo, e 2 é a folga "
        "recomendada.",
        1.3,
    ),
    minimo=1.0,
)

# Chaveta
L_CHAVETA = _g(
    "L_ch",
    "L_ch",
    "Comprimento da chaveta",
    MEDIDA,
    "Comprimento total. Com as pontas arredondadas, o que trabalha é L_ch − b.",
)
SY_CHAVETA = _g(
    "S_y_ch",
    "S_y,ch",
    "Escoamento da chaveta",
    TENSAO,
    "Aço de chaveta C45 ou AISI 1045: cerca de 310 a 430 MPa.",
    350.0,
)
SY_CUBO = _g(
    "S_y_cubo",
    "S_y,cubo",
    "Escoamento do cubo",
    TENSAO,
    "Do material do cubo. Ferro fundido cinzento não escoa: use o limite de pressão do fabricante.",
)
K_SERVICO = replace(
    _g(
        "K_s",
        "K_s",
        "Fator de serviço",
        PURO,
        "Multiplica o torque. Carga uniforme: 1,0 a 1,25. Choque moderado: 1,5. Choque pesado: 2,0.",
        1.25,
    ),
    minimo=1.0,
)
B_CHAVETA = _g("b_ch", "b_ch", "Largura da chaveta", MEDIDA, "Largura da seção da chaveta.")
H_CHAVETA = _g("h_ch", "h_ch", "Altura da chaveta", MEDIDA, "Altura total da chaveta.")
T1_CHAVETA = _g(
    "t_1",
    "t_1",
    "Profundidade do rasgo no eixo",
    MEDIDA,
    "O que sobra da altura da chaveta trabalha no cubo.",
)

# Cubo prensado
D_CUBO = _g(
    "D_cubo",
    "D_cubo",
    "Diâmetro externo do cubo",
    MEDIDA,
    "Por fora do cubo, na região do ajuste. Usual: de 1,5 a 2 vezes d.",
)
L_AJUSTE = _g(
    "L_aj",
    "L_aj",
    "Comprimento do ajuste",
    MEDIDA,
    "Quanto do cubo fica apertado no eixo, sem os chanfros. Usual: de 0,5 a 2 vezes d.",
)
MU_AJUSTE = Grandeza(
    "mu_aj",
    "μ_aj",
    "Atrito do ajuste",
    PURO,
    "Aço com aço, seco e montado a quente: cerca de 0,15. Lubrificado e na prensa: cerca de 0,10.",
    0.12,
)
E_CUBO = _g(
    "E_cubo",
    "E_cubo",
    "Módulo do cubo",
    MODULO,
    "Aço: 200 GPa. Ferro fundido cinzento: cerca de 100 GPa.",
    200000.0,
)
NU_EIXO = Grandeza("nu_e", "ν_e", "Poisson do eixo", PURO, "Aço: 0,3.", 0.3, maximo=0.5)
NU_CUBO = Grandeza(
    "nu_cubo", "ν_cubo", "Poisson do cubo", PURO, "Aço: 0,3. Ferro fundido: 0,26.", 0.3, maximo=0.5
)
RZ_EIXO = Grandeza(
    "Rz_e",
    "Rz_e",
    "Rugosidade do eixo",
    MICRO,
    "A montagem amassa os picos, e parte da interferência some. Retificado: cerca de 4 µm.",
    4e-3,
    zero_ok=True,
)
RZ_CUBO = Grandeza(
    "Rz_cubo",
    "Rz_cubo",
    "Rugosidade do furo",
    MICRO,
    "Rugosidade do furo do cubo. Mandrilado ou alargado: de 6,3 a 10 µm.",
    6.3e-3,
    zero_ok=True,
)
DELTA_MIN = _g(
    "delta_min",
    "δ_mín",
    "Interferência mínima",
    MICRO,
    "A menor interferência no diâmetro, com as tolerâncias do eixo e do furo.",
)
DELTA_MAX = _g(
    "delta_max",
    "δ_máx",
    "Interferência máxima",
    MICRO,
    "A maior interferência no diâmetro, com as tolerâncias do eixo e do furo.",
)
F_AX_CUBO = _esforco(
    "F_ac",
    "F_ac",
    "Força axial no cubo",
    FORCA,
    "Força ao longo do eixo que o ajuste também precisa segurar.",
)

# Rolamento
C_DINAMICA = _g("C_din", "C", "Capacidade dinâmica", FORCA, "O C do catálogo do rolamento.")
C_ESTATICA = _g("C_0", "C_0", "Capacidade estática", FORCA, "O C₀ do catálogo do rolamento.")
VIDA_HORAS = _g(
    "L_h",
    "L_h",
    "Vida pedida",
    TEMPO,
    "Máquina de 8 h por dia: de 10 a 25 mil horas. De 24 h por dia: de 40 a 60 mil horas.",
    20000.0 * 3600.0,
)
F_RADIAL_MANCAL = _esforco(
    "F_rm", "F_rm", "Força radial no mancal", FORCA, "A reação do eixo neste mancal."
)
F_AXIAL_MANCAL = Grandeza(
    "F_am",
    "F_am",
    "Força axial no mancal",
    FORCA,
    "Força ao longo do eixo que este rolamento segura. Zero quando o outro mancal segura.",
    0.0,
    zero_ok=True,
)
F_APLICACAO = replace(
    _g(
        "f_ap",
        "f_ap",
        "Fator de aplicação",
        PURO,
        "Engrenagens de precisão: 1,0 a 1,2. Choque leve: 1,2 a 1,5. Britador, moinho e peneira: "
        "1,5 a 3.",
        1.2,
    ),
    minimo=1.0,
)
X_ROLAMENTO = _g(
    "X_r", "X", "Fator radial", PURO, "O X do catálogo para a relação F_a/F_r do caso."
)
Y_ROLAMENTO = Grandeza(
    "Y_r",
    "Y",
    "Fator axial",
    PURO,
    "O Y do catálogo para a relação F_a/F_r do caso.",
    zero_ok=True,
)
S0_MINIMO = _g(
    "s_0",
    "s_0",
    "Segurança estática mínima",
    PURO,
    "Serviço normal: 1. Silencioso: 2. Com choques: de 1,5 a 3.",
    1.5,
)

# Fluidos
RHO = _g("rho", "ρ", "Massa específica", MASSA_ESPECIFICA, "Massa por volume do fluido.")
MU = _g("mu", "μ", "Viscosidade dinâmica", VISCOSIDADE, "Água a 20 °C: cerca de 1 mPa·s.")
P_VAPOR = _g(
    "p_v",
    "p_v",
    "Pressão de vapor",
    PRESSAO,
    "Absoluta, na temperatura do fluido. Água a 20 °C: 2,34 kPa.",
)
GRAVIDADE = _g("g", "g", "Gravidade", ACELERACAO, "Aceleração da gravidade.", 9.81)
VAZAO_Q = _esforco("Q", "Q", "Vazão", VAZAO, "Volume que passa por tempo.")
D_TUBO = _g("D", "D", "Diâmetro interno", DIAMETRO, "Diâmetro interno do tubo.")
L_TUBO = _g("L", "L", "Comprimento do trecho", COMPRIMENTO, "Comprimento reto do trecho de tubo.")
EPSILON = _g(
    "varepsilon",
    "ε",
    "Rugosidade do tubo",
    RUGOSIDADE,
    "Aço comercial: 0,045 mm. PVC: 0,0015 mm.",
)
K_LOCAL = _esforco(
    "K_L",
    "K_L",
    "Soma dos coeficientes K",
    PURO,
    "Curva de 90°: 0,3 a 0,9. Registro aberto: 0,2. Entrada: 0,5. Saída: 1.",
)
H_DISP = _g("H_d", "H_d", "Carga disponível", ALTURA, "Desnível ou altura que empurra o fluido.")
H_EST = _esforco("H_est", "H_est", "Altura estática", ALTURA, "Quanto o fluido precisa subir.")
DELTA_P = _esforco(
    "Delta_p", "Δp", "Diferença de pressão", PRESSAO, "Pressão no fim menos a pressão no começo."
)
H_BOMBA = _g("H_b", "H_b", "Altura da bomba", ALTURA, "A altura que a bomba entrega nessa vazão.")
ETA = Grandeza(
    "eta",
    "η",
    "Rendimento da bomba",
    PURO,
    "De 0 a 1. Bomba centrífuga: 0,6 a 0,8.",
    0.7,
    maximo=1.0,
)
P_MOTOR = _g("P_m", "P_m", "Potência no eixo", POTENCIA, "A potência que o motor entrega à bomba.")
P_ATM = _g(
    "p_atm", "p_atm", "Pressão atmosférica", PRESSAO, "Absoluta. Nível do mar: 101,3 kPa.", 101325.0
)
Z_SUCCAO = _esforco(
    "z_s", "z_s", "Altura de sucção", ALTURA, "Desnível entre o nível do líquido e a bomba."
)
NPSH_R = _g("NPSH_r", "NPSH_r", "NPSH requerido", ALTURA, "Vem da curva da bomba.")
V_ADM = _g("V_adm", "V_adm", "Velocidade máxima", VELOCIDADE, "Água em recalque: 1 a 3 m/s.")
P_REF = _esforco(
    "p_0", "p_0", "Pressão na superfície", PRESSAO, "Manométrica ou absoluta, à sua escolha."
)
H_PROF = _g("h", "h", "Profundidade", ALTURA, "Distância vertical abaixo da superfície.")
P_FUNDO = _g("p_h", "p_h", "Pressão na profundidade", PRESSAO, "Na mesma referência de p_0.")
A_SUPERF = _g("A", "A", "Área da superfície", AREA, "Área molhada da comporta ou parede.")
H_CENTRO = _g(
    "h_c", "h_c", "Profundidade do centroide", ALTURA, "Da superfície livre até o centroide."
)
F_RESULT = _g("F_R", "F_R", "Força resultante", FORCA, "Força do fluido sobre a superfície.")
V_DESLOC = _g("V_d", "V_d", "Volume deslocado", VOLUME, "Volume da parte submersa.")
EMPUXO = _g("F_e", "F_e", "Empuxo", FORCA, "Força para cima, igual ao peso do fluido deslocado.")
C_ARRASTO = _g(
    "C_D", "C_D", "Coeficiente de arrasto", PURO, "Esfera: 0,47. Cilindro: 1,2. Placa: 1,28."
)
A_FRONTAL = _g("A_f", "A_f", "Área frontal", AREA, "Área projetada na direção do escoamento.")
V_REL = _g(
    "V_r", "V_r", "Velocidade relativa", VELOCIDADE, "Velocidade do fluido em relação à peça."
)
F_ARRASTO = _g("F_D", "F_D", "Força de arrasto", FORCA, "Força do fluido na direção do escoamento.")
C_DESCARGA = _g(
    "C_d", "C_d", "Coeficiente de descarga", PURO, "Placa de orifício: 0,6. Venturi: 0,98."
)
D_ORIFICIO = _g("D_o", "D_o", "Diâmetro do orifício", DIAMETRO, "Diâmetro da garganta do medidor.")
MANNING = _g("n_m", "n_m", "Coeficiente de Manning", PURO, "Concreto: 0,013. Terra: 0,025.")
B_CANAL = _g("b_c", "b_c", "Largura do canal", COMPRIMENTO, "Largura do fundo do canal retangular.")
Y_CANAL = _g("y_c", "y_c", "Profundidade da lâmina", COMPRIMENTO, "Altura da água no canal.")
DECLIVIDADE = _g("S_0", "S_0", "Declividade", PURO, "Queda por comprimento: 0,001 é 1 m por km.")
CELERIDADE = _g(
    "a_c", "a_c", "Celeridade da onda", VELOCIDADE, "Tubo de aço com água: cerca de 1000 m/s."
)
DELTA_V = _g(
    "Delta_V",
    "ΔV",
    "Variação de velocidade",
    VELOCIDADE,
    "No fechamento rápido, a velocidade da linha.",
)
P_GOLPE = _g(
    "Delta_p_g", "Δp_g", "Sobrepressão do golpe", PRESSAO, "Pressão extra no fechamento rápido."
)
H_ZERO = _g("H_0", "H_0", "Altura com vazão zero", ALTURA, "O começo da curva da bomba.")
A_BOMBA = _esforco(
    "a_b",
    "a_b",
    "Queda da curva da bomba",
    CURVA_BOMBA,
    "O a de H = H_0 − a·Q². Os pontos do catálogo da bomba dão este valor sozinhos.",
)

_TODAS: tuple[Grandeza, ...] = tuple(
    v for v in tuple(globals().values()) if isinstance(v, Grandeza)
)
_INICIO_DE_FLUIDOS = _TODAS.index(RHO)
#: A mesma letra muda de sentido entre as partes: h é a altura da seção, ou a profundidade.
_LETRAS = {
    SISTEMA_SOLIDOS.chave: _TODAS[:_INICIO_DE_FLUIDOS],
    SISTEMA_FLUIDOS.chave: _TODAS[_INICIO_DE_FLUIDOS:],
}
_SISTEMAS = {SISTEMA_SOLIDOS.chave: SISTEMA_SOLIDOS, SISTEMA_FLUIDOS.chave: SISTEMA_FLUIDOS}


def letras_conhecidas(sistema: str) -> dict[str, Grandeza]:
    """As letras do programa nesta parte, pelo nome do símbolo."""
    return {item.chave: item for item in _LETRAS.get(sistema, ())}


def dimensoes_do_sistema(sistema: str) -> tuple[str, ...]:
    item = _SISTEMAS.get(sistema)
    return item.dimensoes if item is not None else (PURO,)
