"""Critério de Projeto Anglo American — Estruturas Metálicas, AA-BR-DPST-DR-0001, Rev. 1 (22/12/2025).

Os valores do critério que o programa usa ou mostra, cada um com o item do documento. O critério se
aplica ao Sistema Minas-Rio (Conceição do Mato Dentro-MG, mineroduto e filtragem do porto no Rio de
Janeiro). Sem Streamlit.

Três pontos do texto pedem atenção e estão marcados no programa (``CONFLITOS``):

* **S₃ = 0,95** (5.6) é o valor que a NBR 6123:**1988** dava às "instalações industriais com baixo
  fator de ocupação" (grupo 3 daquela edição). Na edição de **2023**, indústrias são o grupo 3 com
  S₃ = 1,00, e 0,95 ficou para edificações **sem ocupação humana** (grupo 4). Usar 0,95 dá pressão
  dinâmica 10 % menor que a da norma vigente.
* A Tabela 4 tem duas linhas para colunas de plataformas sob vento (H/400; e H/300 com no máximo
  30 mm) e duas para colunas ao nível da cobertura (H/300; e H/400): o programa usa a mais rigorosa.
* No coeficiente dinâmico (5.7) o texto traz ``1/(1 − Ne²/m)`` quando ``Nm > Ne``; o programa lê
  ``Ne²/Nm²``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

CODIGO = "AA-BR-DPST-DR-0001"
REVISAO = "1"
DATA = "22/12/2025"
TITULO = "Critério de Projeto — Estruturas Metálicas"
REFERENCIA = f"Anglo American {CODIGO}, Rev. {REVISAO} ({DATA}) — {TITULO}"
ROTULO_CURTO = f"Anglo {CODIGO}"
APLICACAO = (
    "Sistema Minas-Rio: planta de beneficiamento em Conceição do Mato Dentro-MG, mineroduto e "
    "planta de filtragem do porto (Rio de Janeiro-RJ)."
)


def item(numero: str) -> str:
    """Referência curta a um item do critério (ex.: ``Anglo 5.6``)."""
    return f"Anglo {numero}"


# ---------------------------------------------------------------------------------------------
# 5.6 — Vento (Conceição do Mato Dentro-MG)
# ---------------------------------------------------------------------------------------------
V0_M_S = 35.0
S1 = 1.0
S3 = 0.95
LOCAL_DO_VENTO = "Conceição do Mato Dentro-MG"
GRUPO_S3_NBR_2023_EQUIVALENTE = 4  # S₃ = 0,95 na Tabela 4 da edição de 2023
GRUPO_S3_NBR_2023_INDUSTRIAL = 3  # S₃ = 1,00: indústrias na edição de 2023

# ---------------------------------------------------------------------------------------------
# 5.2 — Sobrecargas mínimas (Tabela 2)
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Sobrecarga:
    local: str
    valor_kN_m2: float
    nota: str = ""


SOBRECARGAS: tuple[Sobrecarga, ...] = (
    Sobrecarga(
        "Coberturas — áreas de processo",
        0.50,
        "Nota 1: maior se houver derramamento ou acúmulo de material.",
    ),
    Sobrecarga("Coberturas — áreas auxiliares e administrativas", 0.25, "Nota 1."),
    Sobrecarga("Plataformas de operação em geral", 5.00),
    Sobrecarga("Plataformas de manutenção em geral", 5.00, "Nota 2."),
    Sobrecarga(
        "Plataformas de manutenção com equipamentos móveis (antes do projeto básico)", 10.00
    ),
    Sobrecarga(
        "Plataformas de manutenção com equipamentos móveis (básico e detalhado)",
        5.00,
        "Mais a carga do equipamento carregado na posição mais crítica de cada elemento.",
    ),
    Sobrecarga(
        "Plataformas de manutenção de moinhos, transportadores, britadores e peneiras",
        10.00,
        "Nota 2; pode ser maior para troca de placas e revestimentos (nota 4).",
    ),
    Sobrecarga(
        "Plataformas de salas elétricas com acesso de equipamentos",
        5.00,
        "Mais o peso do maior equipamento previsto.",
    ),
    Sobrecarga(
        "Passadiço ao longo de transportadores de correia",
        3.00,
        "Nota 2; maior se houver transbordo.",
    ),
    Sobrecarga(
        "Escadas e passadiços em geral", 3.00, "Inclusive passadiços laterais às pontes rolantes."
    ),
    Sobrecarga(
        "Passadiços de salas elétricas, bombeamento, pipe racks, armazéns e similares",
        4.00,
        "Nota 5.",
    ),
    Sobrecarga("Cabines de controle", 10.00),
    Sobrecarga("Salas de controle", 5.00),
    Sobrecarga("Salas de cabos", 5.00),
    Sobrecarga("Salas de painéis", 10.00),
)


def sobrecarga(local: str) -> Sobrecarga:
    for s in SOBRECARGAS:
        if s.local == local:
            return s
    raise ValueError(f"Local fora da Tabela 2 do critério Anglo: {local!r}.")


# ---------------------------------------------------------------------------------------------
# 5.3 a 5.5, 5.8 e 5.10 — impactos, pontes rolantes, monovias, temperatura, linha de vida
# ---------------------------------------------------------------------------------------------
IMPACTOS: tuple[tuple[str, str], ...] = (
    (
        "Máquinas rotativas (motores, redutores, transportadores, misturadores)",
        "+20 % da carga estática vertical máxima",
    ),
    (
        "Equipamentos vibratórios sem carga dinâmica conhecida — vertical",
        "+100 % do peso em operação",
    ),
    (
        "Equipamentos vibratórios sem carga dinâmica conhecida — horizontal",
        "25 % do peso em operação",
    ),
    ("Veículos com pneus", "+30 % da carga vertical máxima"),
    ("Tirantes que suportam pisos", "+33 % da carga vertical máxima"),
)
IMPACTO_ROTATIVAS = 0.20
IMPACTO_VIBRATORIO_VERTICAL = 1.00
IMPACTO_VIBRATORIO_HORIZONTAL = 0.25
IMPACTO_VEICULOS = 0.30
IMPACTO_TIRANTES = 0.33

PONTE_ROLANTE: tuple[str, ...] = (
    "Majoração das cargas verticais das rodas: 25 %.",
    "Força transversal no topo do trilho, de cada lado: o maior entre 10 % de (carga içada + trole "
    "+ dispositivos) e 5 % de (carga içada + peso total da ponte).",
    "Força longitudinal no topo do trilho, de cada lado: 20 % da soma das cargas máximas das rodas "
    "motoras e/ou com freio.",
    "No máximo 3 vias de rolamento atuando juntas; choque nos batentes pela AIST TR-6.",
    "O vento entra integralmente mesmo combinado com as forças horizontais da ponte.",
)
MONOVIA_IMPACTO_CARGA = 0.20
MONOVIA_IMPACTO_PARTES_MOVEIS = 0.10
TEMPERATURA_VARIACAO_C = 10.0
JUNTA_DE_DILATACAO_M = 120.0
LINHA_DE_VIDA_kN = 15.0
LINHA_DE_VIDA_ALTURA_POSTE_M = 0.8

# ---------------------------------------------------------------------------------------------
# 5.9 — Combinações mínimas (NBR 8800)
# ---------------------------------------------------------------------------------------------
COMBINACOES_MINIMAS: tuple[str, ...] = (
    "Permanente + Sobrecarga + Equipamento + PRV + Monovia",
    "Permanente + Sobrecarga + Equipamento + PRV ± HT + Monovia",
    "Permanente + Equipamento vazio + Vento",
    "Permanente + Equipamento vazio + Sobrecarga + PRV + Monovia + Vento",
    "Permanente + Equipamento vazio + Sobrecarga + PRV ± HT + Monovia + Vento",
    "HL + Vento (para o contraventamento vertical)",
)
LEGENDA_COMBINACOES = (
    "PRV: ponte rolante vertical; HT: horizontal transversal; HL: horizontal longitudinal."
)
QUADRO_DE_CARGAS_FUNDACOES = "As ações dos quadros de cargas para as fundações não devem ser combinadas nem majoradas (item 5.9)."

# ---------------------------------------------------------------------------------------------
# 7 — Deslocamentos máximos (Tabelas 3 e 4)
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class LimiteDeDeslocamento:
    descricao: str
    divisor: float | None  # L/divisor ou H/divisor
    maximo_mm: float | None = None
    base: str = "L"  # "L", "H" ou "h"
    condicao: str = ""
    tabela: str = "Tabela 3"

    @property
    def texto(self) -> str:
        partes = []
        if self.divisor:
            partes.append(f"{self.base}/{self.divisor:g}")
        if self.maximo_mm:
            partes.append(f"máx. {self.maximo_mm:g} mm")
        texto = ", ".join(partes) or "—"
        return f"{texto} ({self.condicao})" if self.condicao else texto

    def limite_mm(self, comprimento_mm: float) -> float:
        valores = []
        if self.divisor:
            valores.append(comprimento_mm / self.divisor)
        if self.maximo_mm:
            valores.append(self.maximo_mm)
        return min(valores) if valores else math.inf


DESLOCAMENTOS_VERTICAIS: tuple[LimiteDeDeslocamento, ...] = (
    LimiteDeDeslocamento("Vigas de cobertura", 250),
    LimiteDeDeslocamento("Vigas de piso principais", 350),
    LimiteDeDeslocamento("Vigas de piso secundárias", 300, condicao="L/300 a L/200"),
    LimiteDeDeslocamento("Estruturas de apoio de correias transportadoras", 350),
    LimiteDeDeslocamento("Vigas de rolamento — ponte < 20 tf", 600),
    LimiteDeDeslocamento("Vigas de rolamento — ponte ≥ 20 tf", 800),
    LimiteDeDeslocamento("Monovias", 500, condicao="sem o coeficiente de impacto"),
    LimiteDeDeslocamento("Vigas que suportam colunas", 500),
    LimiteDeDeslocamento("Vigas que suportam equipamentos vibratórios", 800),
    LimiteDeDeslocamento("Terças e travessas de fechamento", 200, 30.0),
)

DESLOCAMENTOS_HORIZONTAIS: tuple[LimiteDeDeslocamento, ...] = (
    LimiteDeDeslocamento("Monovias e vigas de rolamento (horizontal)", 400, tabela="Tabela 4"),
    LimiteDeDeslocamento(
        "Colunas ao nível da cobertura", 400, base="H", condicao="com vento", tabela="Tabela 4"
    ),
    LimiteDeDeslocamento(
        "Colunas ao nível da cobertura", 500, base="H", condicao="sem vento", tabela="Tabela 4"
    ),
    LimiteDeDeslocamento(
        "Colunas ao nível das plataformas de equipamentos",
        400,
        base="H",
        condicao="com vento",
        tabela="Tabela 4",
    ),
    LimiteDeDeslocamento(
        "Colunas ao nível das vigas de piso com equipamentos",
        400,
        20.0,
        base="H",
        condicao="sem vento",
        tabela="Tabela 4",
    ),
    LimiteDeDeslocamento(
        "Colunas de pipe rack e cable rack",
        250,
        base="H",
        condicao="tubulação, bandejamento ou vento",
        tabela="Tabela 4",
    ),
    LimiteDeDeslocamento(
        "Deslocamento relativo entre dois pisos consecutivos", 500, base="h", tabela="Tabela 4"
    ),
    LimiteDeDeslocamento(
        "Colunas ao nível dos caminhos de rolamento",
        300,
        35.0,
        base="H",
        condicao="com vento",
        tabela="Tabela 4",
    ),
    LimiteDeDeslocamento(
        "Colunas ao nível dos caminhos de rolamento",
        400,
        50.0,
        base="H",
        condicao="sem vento, só ponte rolante",
        tabela="Tabela 4",
    ),
    LimiteDeDeslocamento("Travessas de fechamento", 150, 30.0, tabela="Tabela 4"),
    LimiteDeDeslocamento(
        "Vigas horizontais de travamento de vigas de rolamento",
        800,
        15.0,
        condicao="com vento",
        tabela="Tabela 4",
    ),
)

#: Tipos de estrutura aberta e o limite do deslocamento horizontal sob vento (o mais rigoroso
#: quando a Tabela 4 traz duas linhas para o mesmo caso).
TIPO_PLATAFORMA = "Plataforma de equipamentos"
TIPO_PIPE_RACK = "Pipe rack ou cable rack"
TIPO_COBERTURA = "Estrutura com cobertura"
LIMITE_DO_TOPO_POR_TIPO: dict[str, LimiteDeDeslocamento] = {
    TIPO_PLATAFORMA: DESLOCAMENTOS_HORIZONTAIS[3],
    TIPO_PIPE_RACK: DESLOCAMENTOS_HORIZONTAIS[5],
    TIPO_COBERTURA: DESLOCAMENTOS_HORIZONTAIS[1],
}
LIMITE_ENTRE_PISOS = DESLOCAMENTOS_HORIZONTAIS[6]

# ---------------------------------------------------------------------------------------------
# 8 — Estruturas e elementos
# ---------------------------------------------------------------------------------------------
ESBELTEZ_TRACAO = 300.0  # 8.3 (não se aplica a barras redondas e peças montadas com pré-tensão)
ESBELTEZ_COMPRESSAO = 200.0  # 8.3

#: Tabela 5 — redução do comprimento de cantoneiras de contraventamento tracionadas (protensão).
REDUCAO_CANTONEIRAS: tuple[tuple[float, float, float | None], ...] = (
    (0.0, 3.0, None),
    (3.0, 6.0, 2.0),
    (6.0, 10.0, 3.0),
    (10.0, math.inf, 5.0),
)


def reducao_de_comprimento_mm(comprimento_m: float) -> float | None:
    """Tabela 5: ``None`` (não se aplica) até 3 m; 2, 3 ou 5 mm acima."""
    for minimo, maximo, reducao in REDUCAO_CANTONEIRAS:
        if minimo < comprimento_m <= maximo or (minimo == 0.0 and comprimento_m <= maximo):
            return reducao
    return REDUCAO_CANTONEIRAS[-1][2]


#: 8.8 — espessuras e diâmetros mínimos.
ESPESSURAS_MINIMAS_MM: dict[str, float] = {
    "Perfis soldados": 4.75,
    "Perfis laminados H e W": 4.80,
    "Perfis laminados L e U": 4.80,
    "Chapas de ligação e enrijecedores": 8.00,
    "Cantoneiras": 4.75,
    "Placas de base": 16.0,
    "Placas de base de elementos leves": 12.5,
    "Chapas xadrez de piso": 6.35,
    "Chapas expandidas de piso": 6.35,
    "Chapas de perfis dobrados a frio": 3.00,
    "Barras chatas de grades de piso": 2.00,
}
DIAMETROS_MINIMOS: dict[str, str] = {
    "Chumbadores convencionais": '5/8"',
    "Chumbadores químicos": '1/2"',
    "Tirantes": '1/2"',
    "Parafusos": '5/8"',
}
DIAMETROS_MINIMOS_MM: dict[str, float] = {
    "Chumbadores convencionais": 15.875,
    "Chumbadores químicos": 12.7,
    "Tirantes": 12.7,
    "Parafusos": 15.875,
}
CHAPA_COM_ULTRASSOM_MM = 31.5  # 4.5, nota 1: 100 % ensaiadas por ultrassom

#: 8.7 — chumbador → (furo na placa D_c, furo da arruela D_a, espessura da arruela, lado da
#: arruela quadrada, altura mínima do grout), em mm. A arruela não é soldada na placa.
CHUMBADORES: dict[str, tuple[float, float, float, float, float]] = {
    '5/8"': (28, 18, 9.5, 40, 50),
    '3/4"': (33, 21, 9.5, 50, 50),
    '7/8"': (40, 25, 9.5, 70, 50),
    '1"': (45, 28, 12.5, 80, 50),
    '1 1/4"': (50, 34, 12.5, 80, 50),
    '1 1/2"': (60, 40, 12.5, 90, 50),
    '1 3/4"': (70, 47, 19.0, 100, 50),
    '2"': (80, 53, 22.0, 125, 50),
}

# ---------------------------------------------------------------------------------------------
# 9 — Ligações
# ---------------------------------------------------------------------------------------------
PARAFUSOS_MINIMOS_POR_LIGACAO = 2
DIAMETRO_MAXIMO_PREFERENCIAL_MM = 25.4  # evitar acima de 1"
PROTENSAO_MINIMA_DA_RUPTURA = 0.70
CAPACIDADE_MINIMA_DA_LIGACAO = 0.75  # da resistência à tração da peça (treliças/contraventamentos)
CAPACIDADE_MINIMA_DA_LIGACAO_kN = 3.0 * 9.80665  # 3 t
CAPACIDADE_MINIMA_VIGA = 0.75  # da carga uniforme admissível (AISC)
PARAFUSO_PRINCIPAL = "ASTM F3125 Gr A325, galvanizado a fogo, rosca no plano de corte"
PARAFUSO_SECUNDARIO = "ASTM A307 Gr A, galvanizado a fogo (corrimãos, travessas, terças, escadas)"

#: Tabela 6 — filete mínimo por espessura da chapa.
FILETE_MINIMO: tuple[tuple[float, float], ...] = (
    (6.3, 3.0),
    (12.7, 5.0),
    (19.0, 6.0),
    (math.inf, 8.0),
)


def filete_minimo_mm(espessura_mm: float) -> float:
    for limite, filete in FILETE_MINIMO:
        if espessura_mm <= limite:
            return filete
    return FILETE_MINIMO[-1][1]


def capacidade_minima_da_ligacao_kN(resistencia_tracao_da_peca_kN: float) -> float:
    """9.1: ligações de treliças e contraventamentos ≥ 75 % da tração da peça e ≥ 3 t."""
    return max(
        CAPACIDADE_MINIMA_DA_LIGACAO * resistencia_tracao_da_peca_kN,
        CAPACIDADE_MINIMA_DA_LIGACAO_kN,
    )


# ---------------------------------------------------------------------------------------------
# 5.7 — Ações vibratórias
# ---------------------------------------------------------------------------------------------
FAIXA_PREFERENCIAL = (1.25, 1.5)  # 1,25·Nm < Ne < 1,5·Nm
FAIXA_ALTERNATIVA = (0.575, 0.8)  # 0,575·Nm < Ne < 0,8·Nm
LIMITE_INFERIOR = 0.425  # Ne < 0,425·Nm


@dataclass(frozen=True)
class AvaliacaoDeFrequencia:
    razao: float
    faixa: str
    atende: bool
    multiplo: bool
    coeficiente_dinamico: float
    amplitude_vertical_max_mm: float
    amplitude_horizontal_max_mm: float


def avaliar_frequencia(
    ne_hz: float, nm_hz: float, rotacao_rpm: float | None = None
) -> AvaliacaoDeFrequencia:
    """Frequência própria ``Ne`` da estrutura contra a do equipamento ``Nm`` (5.7)."""
    if not (ne_hz > 0 and nm_hz > 0):
        raise ValueError("As frequências precisam ser maiores que zero.")
    r = ne_hz / nm_hz
    if FAIXA_PREFERENCIAL[0] < r < FAIXA_PREFERENCIAL[1]:
        faixa, atende = "preferencial (1,25 a 1,5·Nm)", True
    elif FAIXA_ALTERNATIVA[0] < r < FAIXA_ALTERNATIVA[1]:
        faixa, atende = "alternativa (0,575 a 0,8·Nm)", True
    elif r < LIMITE_INFERIOR:
        faixa, atende = "abaixo de 0,425·Nm", True
    else:
        faixa, atende = "fora das faixas do critério", False
    multiplo = r >= 1.0 and abs(r - round(r)) < 0.02
    if nm_hz < ne_hz:
        coef = 1.0 / (1.0 - (nm_hz / ne_hz) ** 2)
    elif nm_hz > ne_hz:
        coef = 1.0 / (1.0 - (ne_hz / nm_hz) ** 2)
    else:
        coef = math.inf
    n = rotacao_rpm if rotacao_rpm else nm_hz * 60.0
    return AvaliacaoDeFrequencia(
        razao=r,
        faixa=faixa,
        atende=atende and not multiplo,
        multiplo=multiplo,
        coeficiente_dinamico=coef,
        amplitude_vertical_max_mm=240.0 / n,
        amplitude_horizontal_max_mm=300.0 / n,
    )


# ---------------------------------------------------------------------------------------------
# 10.2 — Escadas e guarda-corpos
# ---------------------------------------------------------------------------------------------
ESPELHO_MIN_MM = 160.0
ESPELHO_MAX_MM = 180.0
BLONDEL_MIN_MM = 630.0
BLONDEL_MAX_MM = 640.0
LARGURA_ESCADA_GERAL_MM = 800.0
LARGURA_ESCADA_PERMANENCIA_MM = 1100.0
GUARDA_CORPO_ALTURA_MIN_MM = 1300.0
GUARDA_CORPO_ESPACAMENTO_MAX_MM = 150.0

# ---------------------------------------------------------------------------------------------
# 4.5 — Materiais (Tabela 1)
# ---------------------------------------------------------------------------------------------
MATERIAIS: tuple[tuple[str, str], ...] = (
    ("Perfis laminados", "ASTM A36; ASTM A572 Gr 50"),
    ("Chapas e perfis soldados", "ASTM A36; ASTM A572 Gr 50; ASTM A588"),
    ("Perfis dobrados a frio", "ASTM A36; ASTM A570 Gr 36; ASTM A588; NBR 14762"),
    ("Tirantes", "SAE 1020; ASTM A36"),
    ("Tubos e perfis tubulares", "ASTM A53, A500, A501"),
    ("Parafusos — ligações principais", PARAFUSO_PRINCIPAL),
    ("Parafusos — ligações secundárias", PARAFUSO_SECUNDARIO),
    ("Eletrodos", "E70XX — AWS A5.1 e A5.5"),
    ("Chapa xadrez", "ASTM A36"),
    ("Grade de piso", "ASTM A36; NBR 16696 (galvanizada)"),
    ("Tubo de guarda-corpo e postes de linha de vida", "ASTM A53 Gr A"),
)

# ---------------------------------------------------------------------------------------------
# Conflitos e interpretações
# ---------------------------------------------------------------------------------------------
CONFLITOS: tuple[str, ...] = (
    "S₃ = 0,95 (item 5.6) é o valor que a NBR 6123:1988 dava a instalações industriais com baixo fator "
    "de ocupação. Na NBR 6123:2023, indústrias são o grupo 3 (S₃ = 1,00) e 0,95 vale para "
    "edificações sem ocupação humana (grupo 4). Com 0,95 a pressão dinâmica fica cerca de 10 % "
    "menor que a da norma vigente: confirme com a Anglo qual adotar.",
    "Tabela 4: colunas de plataformas sob vento aparecem com H/400 e com H/300 (máx. 30 mm); "
    "colunas ao nível da cobertura com H/300 e com H/400. O programa usa a mais rigorosa (H/400).",
    "Item 5.7: o coeficiente dinâmico para Nm > Ne está escrito 1/(1 − Ne²/m); o programa usa "
    "1/(1 − Ne²/Nm²).",
)
