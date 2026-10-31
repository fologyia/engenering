"""Base de pilar de perfil I ou H pela ABNT NBR 8800:2025, Subseção 6.7 (Bases de pilares).

Placa de base retangular soldada ao pilar e presa ao bloco de concreto por chumbadores, com
argamassa expansiva de assentamento (6.7.1.2). Dois tipos (Figura 21): **tipo 1**, chumbadores
externos às mesas (4 ≤ n_b ≤ 8), e **tipo 2**, chumbadores internos (n_b = 4). Momento só em torno
do eixo de maior inércia (6.7.1.3).

Duas disposições comuns fora da Figura 21 (6.7.1.1 admite outras, atendendo 6.1.1.3) vão pelo
**método geral**, o mesmo da 6.7 com os chumbadores em mais de uma linha: a base **rotulada** (2
chumbadores internos, um de cada lado da alma, no eixo da placa) e a de chumbadores **internos e
externos** (4 + 4). Nos casos com momento grande (C3 e T3) a pressão de contato é a mesma da norma
(σ_c,Rd no trecho ℓ_c da borda comprimida) e a força em cada chumbador tracionado é proporcional à
distância dele à borda desse trecho (placa rígida); sem contato (T1 e T2), F_i = N/n − M·x_i/Σx².
Com um só alinhamento tracionado as duas regras dão exatamente as equações da norma. A espessura
pela tração usa a flexão da placa entre o chumbador e a mesa (como no tipo 1) ou entre o chumbador e
a alma (como no tipo 2, com ℓ₀).

O chumbador pode ser de outro aço (ASTM F1554, A193 B7, SAE 1020: d_b,min usa o f_ub dele) e de
outro tipo: reto com porca e chapa na ponta (o da Tabela 18), **guarda-chuva** (gancho em J ou L),
**químico** ou de **expansão** (parabolt). A ancoragem no concreto vai pela ACI 318-19, Capítulo 17:
arrancamento da cabeça ou do gancho (17.6.3), cone de concreto do grupo tracionado (17.6.2),
arrancamento lateral da cabeça perto da borda (17.6.4) e, nos pós-instalados, a resistência de
cálculo do fabricante. Ela é sempre verificada nos tipos que a Tabela 18 não cobre e, no reto com
porca, quando pedida.

O momento no eixo de menor inércia (M_Sd,y) não é tratado pelas fórmulas da 6.7: com ele a base vai
pelo mesmo método geral em duas direções (**flexão oblíqua**). Sem tração nos chumbadores, a zona
comprimida é a parte da placa além de uma linha neutra inclinada cujo centro cai na resultante
(e_x = M/N, e_y = M_y/N), com σ_c,Sd = N/A_c ≤ σ_c,Rd; com tração, σ_c,Rd nessa zona e cada
chumbador do outro lado da linha com força proporcional à distância a ela, a linha (posição e
inclinação) e a força ajustadas para equilibrar N, M e M_y. Sem contato, F_i = N/n − M·x_i/Σx² −
M_y·y_i/Σy². Com M_y = 0, tudo volta às contas de uma direção.

Os casos saem da força axial e da excentricidade e = M_Sd/N_Sd (6.7.1.4, Figuras 22 e 23):

* compressão — **C1** (e = 0), **C2** (sem tração nos chumbadores) e **C3** (com tração; não no
  tipo 2);
* tração — **T1** (e = 0), **T2** (0 < e ≤ a, sem pressão de contato) e **T3** (e > a; não no
  tipo 2).

Em cada caso, 6.7.2.2 dá a espessura mínima da placa t_p,min, o diâmetro mínimo do chumbador
d_b,min (quando há tração nele) e a cortante resistente por atrito V_Rd; quando ela não basta (ou
em T1 e T2, sem atrito), a cortante vai por placa de cisalhamento (6.7.2.4) ou por arruelas
especiais soldadas (6.7.2.5) — e então só pelo dispositivo (6.7.2.3). As disposições construtivas
vêm da Tabela 18 e os chumbadores são de aço ASTM A36 ou equivalente (6.7.1.5 c).

As contas usam ``N·(e ± a) = M ± N·a``: assim a força axial nula com momento (flexão pura) cai no
caso de grande excentricidade sem dividir por zero.

A pressão de contato resistente é a de 6.6.5: σ_c,Rd = 0,85·f_ck/γ_c·√(A₂/A₁) ≤ 1,7·f_ck/γ_c, com
A₂ a área do bloco homotética à placa (a maior que cabe nele, concêntrica, quando o bloco não é
homotético). Com as arruelas soldadas, a cortante resistente de um chumbador é o menor entre o
corte da barra rosqueada com a rosca no plano de corte, 0,45·A_b·f_ub/γ_a2 (6.3.3.2 a), e a
pressão de contato no furo da arruela (6.3.3.3). As notas da Tabela 18 entram nos limites: aço A36
e 4 a 8 chumbadores (a), f_ck,mín junto à porca da ponta (b), a₁ do tipo 2 na direção ℓx (f) e as
dimensões mínimas do bloco (e, g); as outras vão no detalhamento (arruelas, armadura do bloco).
Unidades: mm, N, MPa (kN e kN·m na entrada e na saída).
"""

from __future__ import annotations

import functools
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields, replace
from typing import Any

from core import section_catalog as sc
from core import soldas as sd
from core.bolted_connection import coeficientes_contato
from core.ligacoes import ACOS, ACOS_FRIO
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    linhas_para_registro,
    numero_json,
    status_geral,
)

MODULO_ID = "placa_de_base"
MODULO_TITULO = "Placas de base"

TIPO_1 = "tipo_1"
TIPO_2 = "tipo_2"
TIPO_ROTULADA = "rotulada_2"
TIPO_INTERNOS_E_EXTERNOS = "internos_e_externos"
TIPOS = {
    TIPO_1: "Tipo 1 — chumbadores externos às mesas",
    TIPO_2: "Tipo 2 — chumbadores internos (entre as mesas)",
    TIPO_ROTULADA: "Rotulada — 2 chumbadores internos, no eixo da placa",
    TIPO_INTERNOS_E_EXTERNOS: "Internos e externos — 4 + 4 chumbadores",
}
#: Como a base aparece nas frases ("Base tipo 1 do W …", "Base rotulada do W …").
NOMES_CURTOS = {
    TIPO_1: "tipo 1",
    TIPO_2: "tipo 2",
    TIPO_ROTULADA: "rotulada",
    TIPO_INTERNOS_E_EXTERNOS: "com chumbadores internos e externos",
}
#: Os tipos da Figura 21; os outros vão pelo método geral (extensão da 6.7).
TIPOS_DA_NORMA = (TIPO_1, TIPO_2)
#: Quantos chumbadores cada disposição admite.
QUANTIDADES = {
    TIPO_1: (4, 6, 8),
    TIPO_2: (4,),
    TIPO_ROTULADA: (2,),
    TIPO_INTERNOS_E_EXTERNOS: (8,),
}
ANCORAGEM_PORCA = "porca_na_ponta"
ANCORAGEM_GANCHO = "gancho"
ANCORAGEM_QUIMICO = "quimico"
ANCORAGEM_EXPANSAO = "expansao"
ANCORAGENS = {
    ANCORAGEM_PORCA: "Reto com porca e chapa na ponta (Tabela 18)",
    ANCORAGEM_GANCHO: "Guarda-chuva — gancho em J ou L",
    ANCORAGEM_QUIMICO: "Químico — barra roscada com resina (pós-instalado)",
    ANCORAGEM_EXPANSAO: "Expansão mecânica — parabolt (pós-instalado)",
}
#: Como o tipo aparece em legendas e frases curtas.
ANCORAGENS_CURTAS = {
    ANCORAGEM_PORCA: "reto com porca",
    ANCORAGEM_GANCHO: "guarda-chuva",
    ANCORAGEM_QUIMICO: "químico",
    ANCORAGEM_EXPANSAO: "parabolt",
}
CONCRETADOS = (ANCORAGEM_PORCA, ANCORAGEM_GANCHO)  # concretados com o bloco
POS_INSTALADOS = (ANCORAGEM_QUIMICO, ANCORAGEM_EXPANSAO)  # furo no concreto pronto
#: φ da ACI 318-19 17.5.3, condição B (sem armadura suplementar): concretado e pós-instalado.
PHI_CONCRETADO = 0.70
PHI_POS_INSTALADO = 0.65
CORTANTE_ATRITO = "atrito"
CORTANTE_PLACA = "placa_de_cisalhamento"
CORTANTE_ARRUELAS = "arruelas_soldadas"
CORTANTES = {
    CORTANTE_ATRITO: "Só o atrito da placa na argamassa",
    CORTANTE_PLACA: "Placa de cisalhamento (6.7.2.4)",
    CORTANTE_ARRUELAS: "Arruelas especiais soldadas à placa (6.7.2.5)",
}
FAMILIAS_I = ("W (mesa larga)", "HP (perfil de estaca)", "I duplamente simétrico")
MU_PADRAO = 0.45  # placa de base × argamassa expansiva (6.7.2.2 a)
ALFA_V_CHUMBADOR = 0.45  # corte com a rosca no plano, NBR 8800:2025 6.3.3.2 a)
# Arruela especial (Tabela 18, notas a e c): aço com f_y = 345 MPa — f_u = 450 MPa, o menor dos
# aços desse f_y (ASTM A572 Gr 50) — e furo d_b + 1,5 mm.
FU_ARRUELA = 450.0
FOLGA_DO_FURO_DA_ARRUELA = 1.5
N_DA_TABELA_18 = (4, 8)  # nota a: a Tabela 18 vale de 4 a 8 chumbadores
A1_X_MINIMO_TIPO_2 = 10.0  # nota f: a₁ do tipo 2 na direção ℓx, de 10 mm ao da Tabela 18
REF = "NBR 8800:2025"
ACOS_DA_PLACA = tuple(a for a in ACOS if a not in ACOS_FRIO)  # laminados (ASTM A36, A572, A588)
#: Espessuras de chapa grossa do mercado (mm), para a sugestão da base que atende.
ESPESSURAS_COMERCIAIS: tuple[float, ...] = (
    6.3, 8.0, 9.5, 12.5, 16.0, 19.0, 22.4, 25.0, 31.5, 37.5, 44.5, 50.0, 63.0, 75.0, 100.0,
)  # fmt: skip
DENSIDADE_ACO = 7850.0  # kg/m³
#: Lembrete que acompanha toda base (tela e memorial).
NOTA_TABELA_18 = (
    "Tabela 18 (notas): vale para chumbadores de aço ASTM A36, de 4 a 8 por base, com arruelas "
    "especiais de aço com f_y = 345 MPa e furo d_b + 1,5 mm — soldadas à placa só quando passam "
    "a cortante, e com uma também entre a placa e a porca de nivelamento, logo abaixo dela. O "
    "bloco segue a NBR 6118 com as dimensões mínimas da nota e e a armadura mínima da nota h."
)
GRUPO_GEOMETRIA = "Geometria da base"
GRUPO_CONCRETO_E_PLACA = "Concreto e placa de base"
GRUPO_CHUMBADORES = "Chumbadores"
GRUPO_CORTANTE = "Cortante"
GRUPO_CONSTRUTIVAS = "Disposições construtivas (Tabela 18)"


class BaseInvalida(ValueError):
    """Entrada que a verificação não aceita; a mensagem diz o que corrigir."""


@dataclass(frozen=True)
class AcoChumbador:
    f_y: float  # MPa
    f_u: float
    equivalente_a36: bool  # 6.7.1.5 c): f_y igual a 250 MPa e f_u igual a 400 MPa


#: Aços de chumbador (os mesmos nomes e f_u da página Esforços do modelo, mais o A36 e o B7).
ACOS_CHUMBADOR: dict[str, AcoChumbador] = {
    "ASTM A36": AcoChumbador(250.0, 400.0, True),
    "ASTM F1554 Gr 36": AcoChumbador(248.0, 400.0, True),
    "ASTM F1554 Gr 55": AcoChumbador(380.0, 517.0, False),
    "ASTM F1554 Gr 105": AcoChumbador(724.0, 862.0, False),
    "ASTM A193 B7": AcoChumbador(724.0, 862.0, False),
    "SAE 1020": AcoChumbador(210.0, 380.0, False),
}


@dataclass(frozen=True)
class LinhaTabela18:
    """Uma linha da Tabela 18 (disposições construtivas), em mm e MPa."""

    polegada: str
    d_b: float
    a1: float
    a2: float
    a3: float
    h1: float
    h2: float
    r1: float
    r2: float
    d_f: float
    t_arruela: float
    arruela: str
    e_n: float
    fck_min: float
    n_b_min: float  # menor dimensão do bloco
    s_armadura: float
    phi_armadura: float

    @property
    def lado_da_arruela(self) -> float:
        """O lado da arruela especial quadrada (mm)."""
        return float(self.arruela.split("×")[0].strip().replace(",", "."))


TABELA_18: dict[str, LinhaTabela18] = {
    linha.polegada: linha
    for linha in (
        LinhaTabela18('3/4"', 19, 40, 80, 120, 450, 150, 175, 50, 33, 6.3, "50 × 50", 40, 20, 900, 125, 10),
        LinhaTabela18('7/8"', 22, 45, 90, 140, 465, 200, 225, 50, 40, 6.3, "65 × 65", 50, 20, 900, 100, 10),
        LinhaTabela18('1"', 25, 50, 100, 160, 465, 200, 225, 50, 45, 8.0, "75 × 75", 60, 25, 900, 125, 12.5),
        LinhaTabela18('1 1/4"', 32, 65, 130, 190, 525, 225, 250, 60, 50, 9.5, "75 × 75", 60, 25, 1100, 100, 12.5),
        LinhaTabela18('1 1/2"', 38, 80, 160, 230, 610, 250, 275, 70, 60, 9.5, "90 × 90", 70, 25, 1300, 150, 16),
        LinhaTabela18('1 3/4"', 44, 90, 180, 270, 700, 300, 325, 70, 70, 12.5, "100 × 100", 80, 25, 1600, 125, 16),
        LinhaTabela18('2"', 50, 100, 200, 300, 850, 350, 375, 100, 80, 16.0, "125 × 125", 90, 30, 1800, 100, 16),
    )
}  # fmt: skip


@dataclass(frozen=True)
class EntradaBase:
    """Os dados da base. Esforços de cálculo: N positivo na compressão, M em torno de x (kN·m)."""

    perfil: str = "W 250 x 32,7"
    tipo: str = TIPO_1
    n_chumbadores: int = 4
    chumbador: str = '1"'
    a1_mm: float = 0.0  # 0 = o da Tabela 18
    a2_mm: float = 0.0
    t_placa_mm: float = 25.0
    aco_placa: str = "ASTM A36"
    fck_MPa: float = 25.0
    razao_a2_a1: float = 1.0  # A₂/A₁ quando o bloco não é informado
    bloco_x_mm: float = 0.0  # N_b do bloco, ao longo de ℓx (0 = não informado)
    bloco_y_mm: float = 0.0  # B_b, ao longo de ℓy
    n_sd_kN: float = 300.0
    m_sd_kNm: float = 0.0
    v_sd_kN: float = 20.0
    combinacao: str = sd.COMBINACAO_NORMAL
    cortante: str = CORTANTE_ATRITO
    mu: float = MU_PADRAO
    b_v_mm: float = 150.0  # placa de cisalhamento: altura enterrada (Figura 24)
    b_h_mm: float = 150.0  # largura
    t_pv_mm: float = 19.0  # espessura
    e_n_mm: float = 0.0  # argamassa de assentamento (0 = a da Tabela 18)
    t_arruela_mm: float = 0.0  # arruela especial soldada (0 = a da Tabela 18)
    aco_chumbador: str = "ASTM A36"
    ancoragem: str = ANCORAGEM_PORCA
    e_h_mm: float = 0.0  # gancho: comprimento horizontal (0 = 4,5·d_b)
    m_sd_y_kNm: float = 0.0  # momento no eixo de menor inércia: a 6.7 não trata
    verificar_concreto: bool = (
        False  # ancoragem pela ACI 318-19 no reto com porca (nos outros, sempre)
    )
    armadura_de_ancoragem: bool = False  # armadura do bloco costura o cone (ACI 318-19 17.5.2.1)
    chapa_na_ponta_mm: float = 0.0  # lado da chapa quadrada na ponta (0 = só a porca pesada)
    h_ef_mm: float = 0.0  # embutimento efetivo (0 = h₁ da Tabela 18; pós-instalado: 12·d_b)
    n_rd_fabricante_kN: float = 0.0  # pós-instalado: tração resistente de cálculo de um chumbador
    a1_x_mm: float = 0.0  # tipo 2: a₁ na direção ℓx, de 10 mm ao da Tabela 18 (0 = o da tabela)


@dataclass(frozen=True)
class Geometria:
    d: float
    b_f: float
    t_w: float
    t_f: float
    a1: float
    a2: float
    lx: float
    ly: float
    l0: float | None
    a: float  # da linha de chumbadores mais externa ao eixo da placa
    m: float
    n: float
    n0: float
    e: float  # excentricidade M/N (mm); infinita na flexão pura
    e_n: float
    t_arruela: float
    posicoes: tuple[tuple[float, float], ...]  # chumbadores (x, y) a partir do centro da placa
    a1_x: float = 0.0  # tipo 2: a₁ entre a mesa e a borda em ℓx (nota f); nos outros, = a₁


@dataclass(frozen=True)
class ResultadoBase:
    entrada: EntradaBase
    caso: str
    geometria: Geometria
    sigma_c_rd: float  # MPa
    sigma_c_sd: float | None  # MPa (C1 e C2)
    l_c: float | None  # mm: comprimento da placa sob pressão de contato
    f_t_sd: float  # N, por chumbador tracionado (0 sem tração)
    forcas_nos_chumbadores: tuple[float, ...]  # N, uma por chumbador (posições da geometria)
    t_p_min: float
    d_b_min: float | None
    v_rd: float  # N, a cortante resistente adotada
    verificacoes: tuple[Verificacao, ...]
    avisos: tuple[str, ...] = ()
    detalhamento: tuple[tuple[str, str], ...] = field(default=())
    grupos: tuple[tuple[str, tuple[Verificacao, ...]], ...] = field(default=())
    # flexão oblíqua: a zona da placa sob pressão (polígono em mm, a partir do centro da placa)
    zona_comprimida: tuple[tuple[float, float], ...] = field(default=())

    @property
    def status(self) -> str:
        return status_geral(list(self.verificacoes))

    @property
    def massa_da_placa_kg(self) -> float:
        g = self.geometria
        return g.lx * g.ly * self.entrada.t_placa_mm * 1e-9 * DENSIDADE_ACO

    @property
    def aproveitamento_maximo(self) -> float:
        valores = [v.aproveitamento for v in self.verificacoes if v.aproveitamento is not None]
        return max(valores) if valores else 0.0

    @property
    def governante(self) -> Verificacao | None:
        com = [v for v in self.verificacoes if v.aproveitamento is not None]
        return max(com, key=lambda v: v.aproveitamento or 0.0) if com else None


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor + 0.0:.{casas}f}".replace(".", ",")


def perfis_i() -> list[str]:
    """Os perfis I e H do catálogo, os únicos que o método cobre (6.7.1.1)."""
    return [n for n, p in sc.listar_perfis().items() if p.familia in FAMILIAS_I]


def gama_c(combinacao: str) -> float:
    """γ_c do concreto (NBR 6118): 1,4 nas combinações normais, 1,2 nas excepcionais."""
    return 1.2 if combinacao == sd.COMBINACAO_EXCEPCIONAL else 1.4


def tensao_resistente_do_concreto(fck: float, razao_a2_a1: float, combinacao: str) -> float:
    """σ_c,Rd = 0,85·f_ck/γ_c·√(A₂/A₁) ≤ 1,7·f_ck/γ_c (6.6.5; MPa)."""
    gc = gama_c(combinacao)
    return min(0.85 * fck / gc * math.sqrt(max(razao_a2_a1, 1.0)), 1.7 * fck / gc)


def razao_de_areas(e: EntradaBase, lx: float, ly: float) -> float:
    """A₂/A₁ pelo bloco, ou a informada (6.6.5).

    Bloco homotético à placa: A₂ é a área dele (6.6.5 a). Senão, a maior área homotética à placa
    e concêntrica que cabe no bloco (6.6.5 b; a regra da ACI 318 e da AISC J8). Placa centrada.
    """
    if e.bloco_x_mm > 0 and e.bloco_y_mm > 0:
        k = min(e.bloco_x_mm / lx, e.bloco_y_mm / ly)
        return max(k, 1.0) ** 2
    return max(e.razao_a2_a1, 1.0)


def _validar(e: EntradaBase) -> None:
    if (
        e.tipo not in TIPOS
        or e.cortante not in CORTANTES
        or e.combinacao not in sd.COMBINACOES
        or e.ancoragem not in ANCORAGENS
    ):
        raise BaseInvalida(
            "Escolha a disposição, a ancoragem, a combinação e o dispositivo da lista."
        )
    if e.aco_chumbador not in ACOS_CHUMBADOR:
        raise BaseInvalida(f"Aço do chumbador desconhecido: {e.aco_chumbador!r}.")
    if e.chumbador not in TABELA_18:
        raise BaseInvalida(f"Chumbador fora da Tabela 18: {e.chumbador!r}.")
    if e.aco_placa not in ACOS_DA_PLACA:
        raise BaseInvalida(f"Aço da placa desconhecido: {e.aco_placa!r}.")
    if min(e.t_placa_mm, e.fck_MPa, e.mu) <= 0:
        raise BaseInvalida(
            "Espessura da placa, f_ck e coeficiente de atrito precisam ser positivos."
        )
    medidas = (e.a1_mm, e.a1_x_mm, e.a2_mm, e.bloco_x_mm, e.bloco_y_mm, e.e_n_mm, e.t_arruela_mm)
    if min(*medidas, e.e_h_mm, e.chapa_na_ponta_mm, e.h_ef_mm, e.n_rd_fabricante_kN) < 0:
        raise BaseInvalida("Medidas da base não podem ser negativas.")
    if e.v_sd_kN < 0:
        raise BaseInvalida("Informe a cortante de cálculo em valor absoluto (V_Sd ≥ 0).")
    if e.cortante == CORTANTE_PLACA and min(e.b_v_mm, e.b_h_mm, e.t_pv_mm) <= 0:
        raise BaseInvalida("Placa de cisalhamento: altura, largura e espessura positivas.")


def geometria(e: EntradaBase) -> Geometria:
    """As grandezas de 6.7.2.1 e a posição dos chumbadores (Figura 21)."""
    try:
        perfil = sc.obter_perfil(e.perfil)
    except (KeyError, sc.ErroDeCatalogo):
        raise BaseInvalida(f"Perfil desconhecido: {e.perfil!r}.") from None
    if perfil.familia not in FAMILIAS_I:
        raise BaseInvalida("A Subseção 6.7 trata de pilares de perfil I ou H (6.7.1.1).")
    tab = TABELA_18[e.chumbador]
    d, b_f = perfil.altura_mm, perfil.largura_mm
    t_w, t_f = perfil.espessura_alma_mm, perfil.espessura_mesa_mm
    a1 = e.a1_mm or tab.a1
    a2 = e.a2_mm or tab.a2
    a1_x = (e.a1_x_mm or tab.a1) if e.tipo == TIPO_2 else a1  # nota f da Tabela 18
    n_b = e.n_chumbadores
    lx = d + 4 * a1_x  # a₁ do furo à borda e a₁ do furo à mesa (tipo 1) ou 2·a₁ até a mesa
    if e.tipo in TIPOS_DA_NORMA:
        ly = (0.5 * n_b - 1) * a2 + 2 * a1
    else:  # duas fileiras em y, a₂ entre elas
        ly = a2 + 2 * a1
    l0: float | None = {
        TIPO_1: None,
        TIPO_2: (0.5 * n_b - 1) * a2 + 1.75 * (a2 - t_w),
        TIPO_ROTULADA: 1.75 * (a2 - t_w),  # um chumbador de cada lado da alma
        TIPO_INTERNOS_E_EXTERNOS: a2 + 1.75 * (a2 - t_w),  # dois de cada lado da alma
    }[e.tipo]
    a = {
        TIPO_1: lx / 2 - a1,
        TIPO_2: a2 / 2,
        TIPO_ROTULADA: 0.0,
        TIPO_INTERNOS_E_EXTERNOS: lx / 2 - a1,
    }[e.tipo]
    m = (lx - 0.95 * d) / 2
    n = (ly - 0.80 * b_f) / 2
    n0 = math.sqrt(d * b_f) / 4
    momento = abs(e.m_sd_kNm) * 1e6
    axial = abs(e.n_sd_kN) * 1e3
    if momento == 0:
        exc = 0.0
    elif axial == 0:
        exc = math.inf
    else:
        exc = momento / axial
    # chumbadores: linhas em x, com os de cada linha a passo a₂ em y (x crescente)
    if e.tipo in TIPOS_DA_NORMA:
        por_linha = max(n_b // 2, 1)
        ys = [(k - (por_linha - 1) / 2) * a2 for k in range(por_linha)]
        linhas_x = [-a, a]
    else:
        ys = [-a2 / 2, a2 / 2]
        linhas_x = [0.0] if e.tipo == TIPO_ROTULADA else [-a, -a2 / 2, a2 / 2, a]
    posicoes = tuple((x, y) for x in linhas_x for y in ys)
    return Geometria(
        d, b_f, t_w, t_f, a1, a2, lx, ly, l0, a, m, n, n0, exc,
        e.e_n_mm or tab.e_n, e.t_arruela_mm or tab.t_arruela, posicoes, a1_x,
    )  # fmt: skip


def caso_da_base(e: EntradaBase, g: Geometria, sigma_c_rd: float) -> str:
    """C1, C2, C3, T1, T2 ou T3 (6.7.1.4)."""
    axial = e.n_sd_kN * 1e3
    momento = abs(e.m_sd_kNm) * 1e6
    if axial >= 0:  # compressão (ou flexão pura)
        if momento == 0:
            return "C1"
        # e ≤ ½(ℓx − N/(σ_c,Rd·ℓy))  ⇔  2M ≤ N·(ℓx − N/(σ_c,Rd·ℓy))
        if 2 * momento <= axial * (g.lx - axial / (sigma_c_rd * g.ly)) + 1e-9:
            return "C2"
        return "C3"
    if momento == 0:
        return "T1"
    return "T2" if momento <= abs(axial) * braco_sem_contato(g) + 1e-9 else "T3"


def braco_sem_contato(g: Geometria) -> float:
    """O maior M/|N| na tração sem pressão de contato: Σx²/(n·x_máx) (é o ``a`` nos tipos 1 e 2).

    Com F_i = N/n − M·x_i/Σx², o chumbador mais comprimido (x_máx) chega a zero nesse limite.
    """
    xs = [x for x, _ in g.posicoes]
    x_max = max(abs(x) for x in xs)
    if x_max <= 0:
        return 0.0
    return sum(x * x for x in xs) / (len(xs) * x_max)


def forcas_sem_contato(g: Geometria, axial: float, momento: float) -> tuple[float, ...]:
    """T1 e T2: F_i = |N|/n − M·x_i/Σx² (N em N, M em N·mm; o momento traciona x < 0)."""
    xs = [x for x, _ in g.posicoes]
    soma = sum(x * x for x in xs)
    n = len(xs)
    return tuple(max(abs(axial) / n - (momento * x / soma if soma > 0 else 0.0), 0.0) for x in xs)


def equilibrio_geral(
    g: Geometria, sigma_c_rd: float, axial: float, momento: float
) -> tuple[float, tuple[float, ...]] | None:
    """C3 e T3 de qualquer disposição: (ℓ_c, força em cada chumbador), ou None sem equilíbrio.

    Bloco σ_c,Rd no trecho ℓ_c da borda comprimida (x > 0), como na 6.7.2.2 c) e f); cada chumbador
    à esquerda da borda desse trecho (x_n = ℓx/2 − ℓ_c) tracionado com força proporcional à
    distância a ela (placa rígida). Vale o menor ℓ_c que equilibra N (+ compressão, em N) e M
    (N·mm). Com uma só linha tracionada, dá a equação de ℓ_c da norma.
    """

    def estado(l_c: float) -> tuple[float, tuple[float, ...]] | None:
        x_n = g.lx / 2 - l_c
        distancias = [max(x_n - x, 0.0) for x, _ in g.posicoes]
        soma = sum(distancias)
        compressao = sigma_c_rd * l_c * g.ly
        if soma <= 0 or compressao < axial:
            return None
        k = (compressao - axial) / soma
        forcas = tuple(k * dist for dist in distancias)
        resistido = compressao * (g.lx / 2 - l_c / 2) - sum(
            f * x for f, (x, _) in zip(forcas, g.posicoes, strict=True)
        )
        return resistido - momento, forcas

    inicio = max(axial, 0.0) / (sigma_c_rd * g.ly)
    if inicio >= g.lx:
        return None
    passos = 400
    anterior = inicio
    for i in range(1, passos + 1):
        l_c = inicio + (g.lx - inicio) * i / passos
        agora = estado(l_c)
        if agora is not None and agora[0] >= 0:
            baixo, alto = anterior, l_c
            for _ in range(80):
                meio = (baixo + alto) / 2
                teste = estado(meio)
                if teste is None or teste[0] < 0:
                    baixo = meio
                else:
                    alto = meio
            final = estado(alto)
            assert final is not None
            return alto, final[1]
        anterior = l_c
    return None


def _espessura_pela_tracao(
    g: Geometria, forcas: tuple[float, ...], fy_d: float
) -> tuple[float, str]:
    """t_p pela tração nos chumbadores, para qualquer disposição (método geral).

    Fora das mesas (|x| > d/2), como no tipo 1: t = √(4·T·c/(ℓy·f_y/γ_a1)), T a força da linha
    (n·F_máx dela) e c = |x| − 0,475·d. Entre as mesas, como no tipo 2: de cada lado da alma,
    t = √(2·n·F_máx·(a₂ − t_w)/(ℓ₀·f_y/γ_a1)), ℓ₀ = (n − 1)·s + 1,75·(a₂ − t_w).
    """
    espessura = 0.0
    partes: list[str] = []
    # a linha toda com a força do chumbador mais carregado dela (na flexão oblíqua elas diferem)
    por_linha: dict[float, tuple[int, float]] = {}
    for (x, _), f in zip(g.posicoes, forcas, strict=True):
        if abs(x) > g.d / 2 and f > 0:
            quantos, maior = por_linha.get(x, (0, 0.0))
            por_linha[x] = (quantos + 1, max(maior, f))
    for x, (quantos, maior) in sorted(por_linha.items()):
        total = quantos * maior
        braco = abs(x) - 0.475 * g.d
        if braco > 0:
            t = math.sqrt(4 * total * braco / (g.ly * fy_d))
            espessura = max(espessura, t)
            partes.append(
                f"linha externa x = {_n(x, 0)} mm: √(4·{_n(total / 1e3, 1)} kN·{_n(braco, 1)}/"
                f"(ℓy·f_y/γ_a1)) = {_n(t, 1)} mm"
            )
    internos = [
        (x, y, f)
        for (x, y), f in zip(g.posicoes, forcas, strict=True)
        if abs(x) < g.d / 2 and f > 0
    ]
    if internos:
        f_max = max(f for _, _, f in internos)
        xs_internos = sorted({x for x, _ in g.posicoes if abs(x) < g.d / 2})
        passo = xs_internos[1] - xs_internos[0] if len(xs_internos) > 1 else 0.0
        for lado in (-1, 1):
            n = sum(1 for _, y, _ in internos if y * lado > 0)
            if not n:
                continue
            l0 = (n - 1) * passo + 1.75 * (g.a2 - g.t_w)
            t = math.sqrt(2 * n * f_max * max(g.a2 - g.t_w, 0.0) / (l0 * fy_d))
            espessura = max(espessura, t)
        partes.append(
            f"chumbadores internos: √(2·n·F_máx·(a₂ − t_w)/(ℓ₀·f_y/γ_a1)), F_máx = "
            f"{_n(f_max / 1e3, 1)} kN"
        )
    return espessura, "; ".join(partes) or "sem chumbador tracionado"


Ponto = tuple[float, float]


@dataclass(frozen=True)
class FlexaoObliqua:
    """O caso da base com M_Sd,y e o equilíbrio em duas direções."""

    caso: str
    zona: tuple[Ponto, ...]  # parte da placa sob pressão (vazia sem contato)
    sigma: float  # MPa na zona: σ_c,Sd sem tração, σ_c,Rd com tração, 0 sem contato
    area: float  # mm²
    forcas: tuple[float, ...]  # N, uma por chumbador
    equilibrio: bool  # False: C3 ou T3 sem solução


def _parte_da_placa(lx: float, ly: float, nx: float, ny: float, s: float) -> list[Ponto]:
    """A parte da placa onde nx·x + ny·y ≥ s (o retângulo cortado por uma reta)."""
    cantos = [(-lx / 2, -ly / 2), (lx / 2, -ly / 2), (lx / 2, ly / 2), (-lx / 2, ly / 2)]
    parte: list[Ponto] = []
    for i, a in enumerate(cantos):
        b = cantos[(i + 1) % 4]
        da = nx * a[0] + ny * a[1] - s
        db = nx * b[0] + ny * b[1] - s
        if da >= 0:
            parte.append(a)
        if (da >= 0) != (db >= 0):
            k = da / (da - db)
            parte.append((a[0] + k * (b[0] - a[0]), a[1] + k * (b[1] - a[1])))
    return parte


def _area_e_centro(poligono: list[Ponto]) -> tuple[float, float, float]:
    """Área (mm²) e centro (mm) de um polígono convexo; zero sem área."""
    dobro = cx = cy = 0.0
    for i, (x0, y0) in enumerate(poligono):
        x1, y1 = poligono[(i + 1) % len(poligono)]
        cruz = x0 * y1 - x1 * y0
        dobro += cruz
        cx += (x0 + x1) * cruz
        cy += (y0 + y1) * cruz
    if abs(dobro) < 1e-9:
        return 0.0, 0.0, 0.0
    return dobro / 2, cx / (3 * dobro), cy / (3 * dobro)


def _bissecao(funcao: Any, a: float, b: float, vezes: int) -> float:
    """O ponto de [a, b] onde ``funcao`` (falsa em a, verdadeira em b) muda."""
    for _ in range(vezes):
        meio = (a + b) / 2
        if funcao(meio):
            b = meio
        else:
            a = meio
    return b


def _zona_pelo_centro(lx: float, ly: float, ex: float, ey: float) -> list[Ponto] | None:
    """Sem tração: a parte da placa além de uma linha neutra com o centro em (e_x, e_y)."""
    if ex >= lx / 2 or ey >= ly / 2:
        return None

    def corte(theta: float) -> tuple[float, list[Ponto]]:
        nx, ny = math.cos(theta), math.sin(theta)
        alcance = nx * lx / 2 + ny * ly / 2
        alvo = nx * ex + ny * ey

        def passou(s: float) -> bool:  # o centro da parte passou da resultante na direção n
            area, cx, cy = _area_e_centro(_parte_da_placa(lx, ly, nx, ny, s))
            return area <= 0 or nx * cx + ny * cy >= alvo

        s = _bissecao(passou, -alcance, alcance, 60)
        parte = _parte_da_placa(lx, ly, nx, ny, s)
        _, cx, cy = _area_e_centro(parte)
        return -ny * (cx - ex) + nx * (cy - ey), parte  # o que sobra na direção da linha

    theta = _bissecao(lambda th: corte(th)[0] >= 0, 0.0, math.pi / 2, 50)
    return corte(theta)[1]


def _sem_contato_obliquo(
    g: Geometria, axial: float, mx: float, my: float
) -> tuple[float, ...] | None:
    """T2 em duas direções: F_i = |N|/n − M·x_i/Σx² − M_y·y_i/Σy²; None se algum comprime."""
    soma_x = sum(x * x for x, _ in g.posicoes)
    soma_y = sum(y * y for _, y in g.posicoes)
    if (mx > 0 and soma_x <= 0) or (my > 0 and soma_y <= 0):
        return None
    n = len(g.posicoes)
    forcas = tuple(
        abs(axial) / n - (mx * x / soma_x if mx else 0.0) - (my * y / soma_y if my else 0.0)
        for x, y in g.posicoes
    )
    return forcas if min(forcas) >= -1e-9 else None


def _com_tracao_obliquo(
    g: Geometria, sigma: float, axial: float, mx: float, my: float
) -> tuple[list[Ponto], tuple[float, ...], float] | None:
    """C3 e T3 em duas direções: (zona, forças, área) ou None sem equilíbrio.

    σ_c,Rd na parte da placa além da linha neutra (n·p ≥ s, n = (cos θ, sen θ)); cada chumbador do
    outro lado com F_i = k·(s − n·p_i) (placa rígida). Para cada θ, s e k equilibram N e o momento
    na direção n (o menor s, como na 6.7); θ fecha o momento na direção da linha.
    """
    lx, ly = g.lx, g.ly
    posicoes = g.posicoes

    def estado(
        theta: float, s: float
    ) -> tuple[float, float, tuple[float, ...], list[Ponto], float] | None:
        nx, ny = math.cos(theta), math.sin(theta)
        parte = _parte_da_placa(lx, ly, nx, ny, s)
        area, cx, cy = _area_e_centro(parte)
        compressao = sigma * area
        distancias = [max(s - (nx * x + ny * y), 0.0) for x, y in posicoes]
        soma = sum(distancias)
        if soma <= 0 or compressao < axial:
            return None
        k = (compressao - axial) / soma
        forcas = tuple(k * d for d in distancias)
        rx = compressao * cx - sum(f * x for f, (x, _) in zip(forcas, posicoes, strict=True)) - mx
        ry = compressao * cy - sum(f * y for f, (_, y) in zip(forcas, posicoes, strict=True)) - my
        return nx * rx + ny * ry, -ny * rx + nx * ry, forcas, parte, area

    def na_direcao(
        theta: float,
    ) -> tuple[float, float, tuple[float, ...], list[Ponto], float] | None:
        nx, ny = math.cos(theta), math.sin(theta)
        alcance = nx * lx / 2 + ny * ly / 2
        if axial > 0:
            if axial >= sigma * lx * ly:
                return None
            s0 = _bissecao(
                lambda s: sigma * _area_e_centro(_parte_da_placa(lx, ly, nx, ny, s))[0] <= axial,
                -alcance,
                alcance,
                50,
            )
        else:
            s0 = alcance
        passos = 32
        anterior = s0
        for i in range(1, passos + 1):
            s = s0 - (s0 + alcance) * i / passos
            agora = estado(theta, s)
            if agora is not None and agora[0] >= 0:

                def falta(valor: float) -> bool:
                    teste = estado(theta, valor)
                    return teste is None or teste[0] < 0

                s_final = _bissecao(lambda v: not falta(v), anterior, s, 40)
                return estado(theta, s_final)
            anterior = s
        return None

    n_dir = 16
    tentativas = [
        (math.pi / 2 * j / n_dir, na_direcao(math.pi / 2 * j / n_dir)) for j in range(n_dir + 1)
    ]
    escala = max(mx + my, abs(axial) * max(lx, ly), 1.0)
    zero = 1e-9 * escala  # só M_y (ou só M): a raiz cai na ponta, θ = 90° (ou 0), com resto ±0
    for (th0, e0), (th1, e1) in zip(tentativas, tentativas[1:], strict=False):
        if e0 is None or e1 is None or not (e0[1] <= zero and e1[1] >= -zero):
            continue
        baixo, alto = th0, th1
        for _ in range(40):
            meio = (baixo + alto) / 2
            teste = na_direcao(meio)
            if teste is None:
                break
            if teste[1] <= 0:
                baixo = meio
            else:
                alto = meio
        final = na_direcao((baixo + alto) / 2) or e1
        if abs(final[0]) <= 1e-4 * escala and abs(final[1]) <= 1e-3 * escala:
            return final[3], final[2], final[4]
    return None


@functools.lru_cache(maxsize=256)
def flexao_obliqua(
    g: Geometria, sigma_c_rd: float, axial: float, mx: float, my: float
) -> FlexaoObliqua:
    """O caso e o equilíbrio da base com momento nos dois eixos (N em N, + compressão; M em N·mm).

    M comprime x > 0 e M_y comprime y > 0 (os dois em valor absoluto).
    """
    sem_chumbador = tuple(0.0 for _ in g.posicoes)
    if axial > 0:
        zona = _zona_pelo_centro(g.lx, g.ly, mx / axial, my / axial)
        if zona is not None:
            area = _area_e_centro(zona)[0]
            if area > 0 and axial / area <= sigma_c_rd * (1 + 1e-9):
                return FlexaoObliqua("C2", tuple(zona), axial / area, area, sem_chumbador, True)
    elif axial < 0:
        forcas = _sem_contato_obliquo(g, axial, mx, my)
        if forcas is not None:
            return FlexaoObliqua("T2", (), 0.0, 0.0, tuple(max(f, 0.0) for f in forcas), True)
    caso = "T3" if axial < 0 else "C3"
    solucao = _com_tracao_obliquo(g, sigma_c_rd, axial, mx, my)
    if solucao is None:
        return FlexaoObliqua(caso, (), sigma_c_rd, 0.0, sem_chumbador, False)
    zona, forcas, area = solucao
    return FlexaoObliqua(caso, tuple(zona), sigma_c_rd, area, forcas, True)


def _ell_c(g: Geometria, sigma_c_rd: float, momento_equivalente: float) -> float | None:
    """ℓ_c de C3 e T3: (ℓx/2 + a) − √((ℓx/2 + a)² − 2·N(e ± a)/(σ_c,Rd·ℓy)); None sem raiz."""
    base = g.lx / 2 + g.a
    discriminante = base**2 - 2 * momento_equivalente / (sigma_c_rd * g.ly)
    if discriminante < 0:
        return None
    return base - math.sqrt(discriminante)


def _limite(nome: str, passa: bool, referencia: str, texto: str) -> Verificacao:
    return Verificacao(nome, None, None, "—", referencia, texto, "OK" if passa else "NÃO OK", tipo="limite")  # fmt: skip


def _info(nome: str, texto: str, referencia: str = "") -> Verificacao:
    return Verificacao(nome, None, None, "—", referencia, texto, "INFO", tipo="informativo")


def _alerta(nome: str, referencia: str, texto: str) -> Verificacao:
    """Ressalva que não reprova, mas não deixa o resultado sair como OK."""
    return Verificacao(nome, None, None, "—", referencia, texto, "ALERTA", tipo="limite")


def _texto_da_ancoragem(e: EntradaBase, tab: LinhaTabela18) -> str:
    if e.ancoragem == ANCORAGEM_GANCHO:
        return (
            f"guarda-chuva (gancho em J ou L), e_h = {_n(e.e_h_mm or 4.5 * tab.d_b, 0)} mm, "
            f"embutimento h_ef = {_n(embutimento(e, tab), 0)} mm"
        )
    if e.ancoragem in POS_INSTALADOS:
        return (
            f"{ANCORAGENS_CURTAS[e.ancoragem]} pós-instalado: embutimento h_ef = "
            f"{_n(embutimento(e, tab), 0)} mm; furo, limpeza e torque pela ficha do fabricante"
        )
    ponta = (
        f"chapa {_n(e.chapa_na_ponta_mm, 0)} × {_n(e.chapa_na_ponta_mm, 0)} mm"
        if e.chapa_na_ponta_mm > 0
        else "porca sextavada pesada"
    )
    return (
        f"reto, {ponta} na ponta (Tabela 18): h₁ = {_n(tab.h1, 0)} mm, h₂ = {_n(tab.h2, 0)} mm, "
        f"r₁ = {_n(tab.r1, 0)} mm, r₂ = {_n(tab.r2, 0)} mm"
    )


def embutimento(e: EntradaBase, tab: LinhaTabela18) -> float:
    """h_ef (mm): o informado ou, sem ele, h₁ da Tabela 18 (concretado) ou 12·d_b (pós-instalado)."""
    if e.h_ef_mm > 0:
        return e.h_ef_mm
    return 12 * tab.d_b if e.ancoragem in POS_INSTALADOS else tab.h1


def bloco_minimo(e: EntradaBase, g: Geometria, tab: LinhaTabela18) -> tuple[float, float, float]:
    """(N_b ao longo de ℓx, B_b ao longo de ℓy, altura A_b) mínimos do bloco em mm (Tabela 18, nota e).

    Com a placa centrada, ℓ + 2·(a₃ − a₁) põe cada chumbador externo a a₃ da face do bloco e, no
    tipo 2, a borda da placa a a₃ − a₁ dela (nota g). A altura usa o embutimento (h₁ da tabela).
    """
    folga = max(2 * g.e_n, 2 * (tab.a3 - tab.a1))
    n_b = max(tab.n_b_min, g.lx + folga)
    return n_b, g.ly + folga, max(embutimento(e, tab) + 100.0, n_b)


def bloco_para_o_cone(
    e: EntradaBase, g: Geometria, tab: LinhaTabela18
) -> tuple[float, float, bool]:
    """O bloco ao longo de ℓx e de ℓy e se foi informado; sem ele, o mínimo da nota e da Tabela 18."""
    if e.bloco_x_mm > 0 and e.bloco_y_mm > 0:
        return e.bloco_x_mm, e.bloco_y_mm, True
    n_b, b_b, _ = bloco_minimo(e, g, tab)
    return n_b, b_b, False


def area_de_apoio_da_ponta(e: EntradaBase, tab: LinhaTabela18) -> float:
    """A_brg (mm²) da porca sextavada pesada (s = 1,5·d + 3,2 mm entre faces) ou da chapa."""
    s = 1.5 * tab.d_b + 3.2
    cabeca = e.chapa_na_ponta_mm**2 if e.chapa_na_ponta_mm > s else math.sqrt(3) / 2 * s**2
    return cabeca - math.pi * tab.d_b**2 / 4


def cone_de_concreto(
    e: EntradaBase, g: Geometria, tab: LinhaTabela18, forcas: tuple[float, ...]
) -> tuple[float, float, str] | None:
    """(Σ F_t, φ·N_cbg, conta) do cone do grupo tracionado (ACI 318-19 17.6.2); None sem tração.

    Bloco centrado na placa; ψ_c,N = ψ_cp,N = 1,0 (concreto fissurado); h_ef reduzido pela
    17.6.2.1.2 quando o grupo fica perto de três ou mais bordas.
    """
    tracionados = [(x, y, f) for (x, y), f in zip(g.posicoes, forcas, strict=True) if f > 0]
    if not tracionados:
        return None
    concretado = e.ancoragem in CONCRETADOS
    bx, by, informado = bloco_para_o_cone(e, g, tab)
    xs = [x for x, _, _ in tracionados]
    ys = [y for _, y, _ in tracionados]
    bordas = [bx / 2 + min(xs), bx / 2 - max(xs), by / 2 + min(ys), by / 2 - max(ys)]
    h = embutimento(e, tab)
    s_max = max(max(xs) - min(xs), max(ys) - min(ys))
    proximas = [c for c in bordas if c < 1.5 * h]
    reducao = ""
    if len(proximas) >= 3:
        h_lim = max(max(proximas) / 1.5, s_max / 3)
        if h_lim < h:
            reducao = f" (h_ef reduzido de {_n(h, 0)} mm pela 17.6.2.1.2: perto de 3 ou 4 bordas)"
            h = h_lim
    a_nco = 9 * h * h
    largura_x = min(max(xs) + 1.5 * h, bx / 2) - max(min(xs) - 1.5 * h, -bx / 2)
    largura_y = min(max(ys) + 1.5 * h, by / 2) - max(min(ys) - 1.5 * h, -by / 2)
    a_nc = min(largura_x * largura_y, len(tracionados) * a_nco)
    c_min = max(min(bordas), 0.0)
    psi_ed = 1.0 if c_min >= 1.5 * h else 0.7 + 0.3 * c_min / (1.5 * h)
    total = sum(f for _, _, f in tracionados)
    excentricidade_x = abs(sum(x * f for x, _, f in tracionados) / total - sum(xs) / len(xs))
    excentricidade_y = abs(sum(y * f for _, y, f in tracionados) / total - sum(ys) / len(ys))
    psi_ec = 1 / (1 + excentricidade_x / (1.5 * h)) / (1 + excentricidade_y / (1.5 * h))
    raiz = math.sqrt(e.fck_MPa)
    if e.ancoragem == ANCORAGEM_PORCA and 280 <= h <= 635:
        n_b = 3.9 * raiz * h ** (5 / 3)
        formula = "N_b = 3,9·√f_c·h_ef^(5/3)"
    else:
        k_c = 10 if concretado else 7
        n_b = k_c * raiz * h**1.5
        formula = f"N_b = {k_c}·√f_c·h_ef^1,5"
    phi = PHI_CONCRETADO if concretado else PHI_POS_INSTALADO
    resistente = phi * a_nc / a_nco * psi_ec * psi_ed * n_b
    bloco = (
        f"bloco {_n(bx, 0)} × {_n(by, 0)} mm"
        if informado
        else f"bloco não informado: {_n(bx, 0)} × {_n(by, 0)} mm (o mínimo da nota e da Tabela 18)"
    )
    texto = (
        f"φ·N_cbg = φ·(A_Nc/A_Nco)·ψ_ec,N·ψ_ed,N·N_b = {_n(phi)} × "
        f"({_n(a_nc / 1e3, 1)}/{_n(a_nco / 1e3, 1)}) × {_n(psi_ec, 3)} × {_n(psi_ed, 3)} × "
        f"{_n(n_b / 1e3, 1)} kN; {formula}, h_ef = {_n(h, 0)} mm{reducao}; {bloco}, placa "
        f"centrada; ψ_c,N = 1,0 (fissurado)"
    )
    return total, resistente, texto


def arrancamento_lateral(
    e: EntradaBase, g: Geometria, tab: LinhaTabela18, forcas: tuple[float, ...]
) -> tuple[float, float, str] | None:
    """(força, φ·N_sbg, conta) do grupo mais solicitado junto a uma borda (ACI 318-19 17.6.4).

    Só para chumbador com cabeça (porca ou chapa na ponta) com borda a menos de 0,4·h_ef. Os
    tracionados de uma mesma linha (mesmo x junto à face em x, mesmo y junto à face em y) formam o
    grupo ao longo dessa borda: N_sbg = (1 + s/(6·c_a1))·N_sb, s entre os extremos.
    """
    if e.ancoragem != ANCORAGEM_PORCA:
        return None
    bx, by, _ = bloco_para_o_cone(e, g, tab)
    h = embutimento(e, tab)
    a_brg = area_de_apoio_da_ponta(e, tab)
    pior: tuple[float, float, str] | None = None
    for eixo in (0, 1):  # 0: borda paralela a y (face em x); 1: borda paralela a x
        grupos: dict[float, list[tuple[float, float, float]]] = {}
        for (x, y), f in zip(g.posicoes, forcas, strict=True):
            if f > 0:
                chave = x if eixo == 0 else y
                grupos.setdefault(chave, []).append((x, y, f))
        for chave, membros in grupos.items():
            c1 = (bx if eixo == 0 else by) / 2 - abs(chave)
            if c1 <= 0 or c1 >= 0.4 * h:
                continue
            ao_longo = [y if eixo == 0 else x for x, y, _ in membros]
            c2 = (by if eixo == 0 else bx) / 2 - max(abs(v) for v in ao_longo)
            n_sb = 13 * c1 * math.sqrt(a_brg) * math.sqrt(e.fck_MPa)
            fator_c2 = (1 + min(max(c2 / c1, 1.0), 3.0)) / 4 if c2 < 3 * c1 else 1.0
            espacamento = max(ao_longo) - min(ao_longo)
            if len(membros) > 1 and espacamento < 6 * c1:
                n_grupo = (1 + espacamento / (6 * c1)) * n_sb * fator_c2
            else:
                n_grupo = len(membros) * n_sb * fator_c2
            resistente = PHI_CONCRETADO * n_grupo
            forca = sum(f for _, _, f in membros)
            texto = (
                f"φ·N_sbg = 0,70 × (1 + s/(6·c_a1))·13·c_a1·√A_brg·√f_c × fator de c_a2 = "
                f"{_n(resistente / 1e3, 1)} kN; c_a1 = {_n(c1, 0)} mm < 0,4·h_ef = "
                f"{_n(0.4 * h, 0)} mm, c_a2 = {_n(c2, 0)} mm, s = {_n(espacamento, 0)} mm, "
                f"A_brg = {_n(a_brg, 0)} mm², {len(membros)} chumbador(es)"
            )
            if pior is None or forca / resistente > pior[0] / pior[1]:
                pior = (forca, resistente, texto)
    return pior


def contato_no_furo_da_arruela(
    tab: LinhaTabela18, t_arruela: float, gama_a2: float
) -> tuple[float, float]:
    """(F_c,Rd em N, ℓ_f em mm) do chumbador no furo da arruela soldada (6.3.3.3, furo-padrão).

    O chumbador encosta no furo da arruela (d_b + 1,5 mm, nota c da Tabela 18), não no da placa
    (d_f, folgado); ℓ_f vai da borda do furo à borda da arruela pelo lado, o caminho mais curto.
    f_u de 450 MPa, o do aço de f_y = 345 MPa da nota a.
    """
    k1, k2 = coeficientes_contato()
    l_f = (tab.lado_da_arruela - (tab.d_b + FOLGA_DO_FURO_DA_ARRUELA)) / 2
    return min(k1 * l_f, k2 * tab.d_b) * t_arruela * FU_ARRUELA / gama_a2, l_f


def verificar_ancoragem(
    e: EntradaBase, g: Geometria, tab: LinhaTabela18, forcas: tuple[float, ...]
) -> tuple[list[Verificacao], list[str]]:
    """Aço, tipo do chumbador e a ancoragem no concreto (ACI 318-19, Capítulo 17)."""
    linhas: list[Verificacao] = []
    avisos: list[str] = []
    aco = ACOS_CHUMBADOR[e.aco_chumbador]
    verificar = e.verificar_concreto or e.ancoragem != ANCORAGEM_PORCA
    ref = "ACI 318-19"
    if not aco.equivalente_a36:
        texto = (
            f"{e.aco_chumbador}: f_y = {_n(aco.f_y, 0)} MPa, f_u = {_n(aco.f_u, 0)} MPa. A norma "
            "pede A36 ou equivalente (f_y = 250, f_u = 400 MPa) e a Tabela 18 vale só para ele "
            "(nota a); d_b,min já usa o f_ub deste aço"
        )
        if verificar:
            linhas.append(
                _info(
                    "Aço do chumbador fora do A36",
                    texto + " e a ancoragem no concreto é verificada abaixo",
                    f"{REF} 6.7.1.5 c)",
                )
            )
        else:
            linhas.append(
                _alerta(
                    "Aço do chumbador equivalente ao ASTM A36",
                    f"{REF} 6.7.1.5 c)",
                    texto + ": ligue a verificação da ancoragem no concreto (ACI 318-19)",
                )
            )
    n_min, n_max = N_DA_TABELA_18
    if e.ancoragem == ANCORAGEM_PORCA and not n_min <= e.n_chumbadores <= n_max:
        nome = f"Tabela 18 com {e.n_chumbadores} chumbadores"
        ref_a = f"{REF} Tabela 18, nota a"
        texto = (
            f"a Tabela 18 vale para {n_min} a {n_max} chumbadores (nota a): com "
            f"{e.n_chumbadores}, o embutimento e o bloco dela não garantem a ancoragem"
        )
        if verificar:
            linhas.append(_info(nome, texto + "; ela é verificada abaixo (ACI 318-19)", ref_a))
        else:
            linhas.append(
                _alerta(nome, ref_a, texto + ": ligue a verificação da ancoragem no concreto")
            )
    if e.ancoragem != ANCORAGEM_PORCA:
        linhas.append(
            _info(
                f"Tipo do chumbador: {ANCORAGENS_CURTAS[e.ancoragem]}",
                "a Tabela 18 é de chumbador reto com porca e chapa na ponta, concretado com o "
                "bloco: a ancoragem deste tipo é verificada pela ACI 318-19, Capítulo 17",
                f"{REF} Tabela 18",
            )
        )
    if not verificar:
        return linhas, avisos
    tracionados = [f for f in forcas if f > 0]
    if not tracionados:
        linhas.append(
            _info(
                "Ancoragem no concreto",
                "sem chumbador tracionado: arrancamento e cone não se aplicam",
                ref,
            )
        )
        return linhas, avisos
    f_max = max(tracionados)
    # 1. arrancamento de um chumbador (ou a resistência do fabricante)
    if e.ancoragem == ANCORAGEM_PORCA:
        a_brg = area_de_apoio_da_ponta(e, tab)
        n_p = PHI_CONCRETADO * 8 * a_brg * e.fck_MPa
        ponta = (
            f"chapa {_n(e.chapa_na_ponta_mm, 0)} × {_n(e.chapa_na_ponta_mm, 0)} mm"
            if e.chapa_na_ponta_mm > 1.5 * tab.d_b + 3.2
            else f"porca sextavada pesada, s = 1,5·d + 3,2 = {_n(1.5 * tab.d_b + 3.2, 1)} mm"
        )
        linhas.append(
            Verificacao(
                "Arrancamento da cabeça (porca ou chapa na ponta)",
                f_max / 1e3,
                n_p / 1e3,
                "kN",
                f"{ref} 17.6.3.2.2 (a)",
                f"φ·N_p = 0,70 × 8·A_brg·f_c = 0,70 × 8 × {_n(a_brg, 0)} × {_n(e.fck_MPa, 0)}; "
                f"A_brg da {ponta}, menos a área da haste; ψ_c,P = 1,0 (fissurado)",
            )
        )
    elif e.ancoragem == ANCORAGEM_GANCHO:
        e_h = e.e_h_mm or 4.5 * tab.d_b
        linhas.append(
            _limite(
                "Guarda-chuva: comprimento do gancho e_h ≥ 3·d_b",
                e_h >= 3 * tab.d_b - 1e-9,
                f"{ref} 17.6.3.2.2 (b)",
                f"e_h = {_n(e_h, 0)} mm, 3·d_b = {_n(3 * tab.d_b, 0)} mm (a fórmula vale de 3·d_b "
                "a 4,5·d_b; acima disso não se conta)",
            )
        )
        e_h_util = min(e_h, 4.5 * tab.d_b)
        n_p = PHI_CONCRETADO * 0.9 * e.fck_MPa * e_h_util * tab.d_b
        linhas.append(
            Verificacao(
                "Guarda-chuva: arrancamento do gancho",
                f_max / 1e3,
                n_p / 1e3,
                "kN",
                f"{ref} 17.6.3.2.2 (b)",
                f"φ·N_p = 0,70 × 0,9·f_c·e_h·d_b = 0,70 × 0,9 × {_n(e.fck_MPa, 0)} × "
                f"{_n(e_h_util, 0)} × {_n(tab.d_b, 0)} (ψ_c,P = 1,0, fissurado)",
            )
        )
        if f_max > n_p:
            avisos.append(
                "O gancho (guarda-chuva) arranca antes do aço: troque por chumbador reto com "
                "porca e chapa na ponta, que resiste bem mais ao arrancamento."
            )
    elif e.n_rd_fabricante_kN > 0:
        linhas.append(
            Verificacao(
                "Pós-instalado: tração resistente do fabricante",
                f_max / 1e3,
                e.n_rd_fabricante_kN,
                "kN",
                "ficha do fabricante (ETA ou ICC-ES)",
                f"N_Rd de um chumbador informado ({_n(e.n_rd_fabricante_kN, 1)} kN), para o "
                f"embutimento h_ef = {_n(embutimento(e, tab), 0)} mm, o concreto fissurado e as "
                "distâncias da obra; inclui aderência (químico) ou deslizamento (expansão)",
            )
        )
    else:
        linhas.append(
            _alerta(
                "Pós-instalado: tração resistente do fabricante",
                "ficha do fabricante (ETA ou ICC-ES)",
                "informe a resistência de cálculo à tração de um chumbador, da ficha do "
                "fabricante: a aderência da resina (químico) e o deslizamento (expansão) dependem "
                "do produto, e o programa não tem como calculá-los",
            )
        )
    # 2. cone de concreto do grupo tracionado
    cone = cone_de_concreto(e, g, tab, forcas)
    if cone is not None:
        total, resistente, texto = cone
        if e.armadura_de_ancoragem:
            linhas.append(
                _info(
                    "Cone de concreto: armadura de ancoragem no bloco",
                    f"sem armadura o cone resistiria {_n(resistente / 1e3, 1)} kN ({texto}); com "
                    f"armadura de ancoragem ela substitui o cone: precisa resistir a ΣF_t = "
                    f"{_n(total / 1e3, 1)} kN com φ = 0,75, ancorada dos dois lados da superfície de "
                    "ruptura (projeto do bloco, NBR 6118)",
                    f"{ref} 17.5.2.1",
                )
            )
        else:
            linhas.append(
                Verificacao(
                    "Cone de concreto dos chumbadores tracionados",
                    total / 1e3,
                    resistente / 1e3,
                    "kN",
                    f"{ref} 17.6.2",
                    texto,
                )
            )
            if total > resistente:
                avisos.append(
                    "O cone de concreto não resiste à tração dos chumbadores: aumente o "
                    "embutimento ou o bloco, ou arme o bloco para costurar o cone (armadura de "
                    "ancoragem, ACI 318-19 17.5.2.1) e marque essa opção."
                )
    # 3. arrancamento lateral da cabeça junto à borda
    lateral = arrancamento_lateral(e, g, tab, forcas)
    if lateral is not None:
        forca, resistente, texto = lateral
        linhas.append(
            Verificacao(
                "Arrancamento lateral da cabeça junto à borda",
                forca / 1e3,
                resistente / 1e3,
                "kN",
                f"{ref} 17.6.4",
                texto,
            )
        )
    return linhas, avisos


def calcular(e: EntradaBase) -> ResultadoBase:
    _validar(e)
    g = geometria(e)
    tab = TABELA_18[e.chumbador]
    c = sd.coeficientes(e.combinacao)
    fy = ACOS[e.aco_placa][0]
    fy_d = fy / c.a1
    gc = gama_c(e.combinacao)
    razao = razao_de_areas(e, g.lx, g.ly)
    sigma_rd = tensao_resistente_do_concreto(e.fck_MPa, razao, e.combinacao)
    tau_rd = min(0.2 * e.fck_MPa / gc, 4.0)
    n_b = e.n_chumbadores
    da_norma = e.tipo in TIPOS_DA_NORMA
    aco_ch = ACOS_CHUMBADOR[e.aco_chumbador]
    axial = e.n_sd_kN * 1e3  # N, + compressão
    momento = abs(e.m_sd_kNm) * 1e6  # N·mm
    momento_y = abs(e.m_sd_y_kNm) * 1e6  # N·mm, eixo de menor inércia (comprime y > 0)
    v_sd = e.v_sd_kN * 1e3
    obliqua = flexao_obliqua(g, sigma_rd, axial, momento, momento_y) if momento_y > 0 else None
    caso = obliqua.caso if obliqua is not None else caso_da_base(e, g, sigma_rd)
    linhas: list[Verificacao] = []
    avisos: list[str] = []
    if not da_norma:
        avisos.append(
            "Disposição fora da Figura 21 da norma: o programa usa o método da 6.7 com os "
            "chumbadores em mais de uma linha (pressão σ_c,Rd no trecho ℓ_c e placa rígida). A "
            "6.7.1.1 admite outras configurações desde que atendam 6.1.1.3 — registre o método no "
            "memorial."
        )
    inicios: list[tuple[str, int]] = [(GRUPO_GEOMETRIA, 0)]  # onde começa cada grupo da tela
    ref_cc = f"{REF} 6.6.5"
    texto_sigma = (
        f"σ_c,Rd = 0,85·f_ck/γ_c·√(A₂/A₁) ≤ 1,7·f_ck/γ_c = mín(0,85 × {_n(e.fck_MPa, 1)}/"
        f"{_n(gc, 1)} × √{_n(razao, 2)}; 1,7 × {_n(e.fck_MPa, 1)}/{_n(gc, 1)}) = {_n(sigma_rd)} MPa"
    )
    # ------------------------------------------------------------------ geometria e limites
    regra_n = {
        TIPO_1: "base tipo 1: 4 ≤ n_b ≤ 8, em duas linhas iguais",
        TIPO_2: "base tipo 2: n_b = 4",
        TIPO_ROTULADA: "base rotulada: 2 chumbadores, um de cada lado da alma",
        TIPO_INTERNOS_E_EXTERNOS: "4 chumbadores externos e 4 internos",
    }[e.tipo]
    linhas.append(
        _limite(
            "Número de chumbadores",
            n_b in QUANTIDADES[e.tipo],
            f"{REF} 6.7.2.1" if da_norma else "disposição do método geral",
            f"{regra_n} (n_b = {n_b})",
        )
    )
    if e.tipo == TIPO_2:
        if caso in ("C3", "T3"):
            linhas.append(
                _limite(
                    "Caso previsto para a base tipo 2",
                    False,
                    f"{REF} 6.7.1.4",
                    f"caso {caso}: a base tipo 2 só cobre C1, C2, T1 e T2 — use a base tipo 1",
                )  # fmt: skip
            )
    linhas.append(
        _limite(
            "Largura da placa ℓy ≥ b_f + 25 mm",
            g.ly >= g.b_f + 25.0 - 1e-9,
            f"{REF} 6.7.2.1",
            (
                f"ℓy = (0,5·n_b − 1)·a₂ + 2·a₁ = (0,5·{n_b} − 1)·{_n(g.a2, 0)} + 2·{_n(g.a1, 0)}"
                if da_norma
                else f"ℓy = a₂ + 2·a₁ = {_n(g.a2, 0)} + 2·{_n(g.a1, 0)}"
            )
            + f" = {_n(g.ly, 0)} mm; b_f + 25 = {_n(g.b_f + 25.0, 0)} mm (senão, aumente a₂ ou a₁)",
        )  # fmt: skip
    )
    if g.l0 is not None:
        linhas.append(
            _limite(
                "ℓ₀ ≤ d (chumbadores internos)",
                g.l0 <= g.d + 1e-9,
                f"{REF} 6.7.2.1",
                f"ℓ₀ = (n − 1)·a₂ + 1,75·(a₂ − t_w) = {_n(g.l0, 1)} mm, n chumbadores de cada lado "
                f"da alma; d = {_n(g.d, 0)} mm",
            )  # fmt: skip
        )
        internos = [(x, y) for x, y in g.posicoes if abs(x) < g.d / 2]
        meia = tab.lado_da_arruela / 2
        folga_alma = min(abs(y) for _, y in internos) - meia - g.t_w / 2
        folga_mesa = g.d / 2 - g.t_f - (max(abs(x) for x, _ in internos) + meia)
        linhas.append(
            _limite(
                "Chumbadores internos: arruela livre da alma e das mesas",
                min(folga_alma, folga_mesa) >= -1e-9,
                "montagem",
                f"arruela {tab.arruela} mm: folga de {_n(folga_alma, 0)} mm até a alma e de "
                f"{_n(folga_mesa, 0)} mm até a mesa (precisam ser ≥ 0; senão, perfil mais alto, "
                "chumbador menor ou outra disposição)",
            )
        )
    if obliqua is not None:
        linhas.append(
            _info(
                "Flexão oblíqua: momento também no eixo de menor inércia",
                f"M_Sd,y = {_n(abs(e.m_sd_y_kNm), 1)} kN·m com M_Sd = {_n(abs(e.m_sd_kNm), 1)} kN·m: "
                "as fórmulas da 6.7 são só do eixo de maior inércia; a base vai pelo método geral em "
                "duas direções (zona comprimida além de uma linha neutra inclinada, placa rígida)",
                f"{REF} 6.7.1.1 e 6.7.1.3",
            )
        )
        avisos.append(
            "Flexão oblíqua (momento nos dois eixos): as fórmulas da 6.7 são só do eixo de maior "
            "inércia, e o programa usa o mesmo método em duas direções — pressão de contato numa "
            "zona da placa limitada por uma linha neutra inclinada e chumbadores com força "
            "proporcional à distância a ela (placa rígida). Registre o método no memorial."
        )
    # ------------------------------------------------------------------ o caso
    inicios.append((GRUPO_CONCRETO_E_PLACA, len(linhas)))
    sigma_sd: float | None = None
    l_c: float | None = None
    f_t = 0.0
    forcas = [0.0] * len(g.posicoes)
    lado_tracionado = [
        i for i, (x, _) in enumerate(g.posicoes) if x < 0
    ]  # o momento traciona x < 0
    lado_comprimido = [i for i, (x, _) in enumerate(g.posicoes) if x > 0]
    t_min = 0.0
    d_min: float | None = None
    v_atrito = 0.0
    x_fator = 4 * g.d * g.b_f / (g.d + g.b_f) ** 2
    lam = 0.0
    if axial > 0:
        x_val = x_fator * axial / (g.lx * g.ly * sigma_rd)
        linhas.append(
            Verificacao(
                "Fator X da pressão sob a placa",
                x_val,
                1.0,
                "—",
                f"{REF} 6.7.2.1",
                f"X = [4·d·b_f/(d + b_f)²]·N_Sd/(ℓx·ℓy·σ_c,Rd) = {_n(x_fator, 3)} × "
                f"{_n(axial / 1e3, 1)} kN/({_n(g.lx, 0)} × {_n(g.ly, 0)} × {_n(sigma_rd)}) ≤ 1 "
                "(caso contrário, refazer a ligação)",
            )  # fmt: skip
        )
        x_val = min(x_val, 1.0)
        lam = min(2 * math.sqrt(x_val) / (1 + math.sqrt(1 - x_val)), 1.0)
    n0_lam = lam * g.n0
    zona: tuple[Ponto, ...] = ()
    if obliqua is not None:
        forcas = list(obliqua.forcas)
        f_t = max(forcas)
        zona = obliqua.zona
        if zona:  # o trecho sob pressão no plano do momento (para o corte)
            l_c = g.lx / 2 - min(x for x, _ in zona)
        texto_zona = f"A_c = {_n(obliqua.area / 100, 0)} cm² (zona além da linha neutra inclinada)"
        if caso == "C2":
            sigma_sd = obliqua.sigma
            l_max = max(g.m, g.n, n0_lam)
            t_min = l_max * math.sqrt(2 * sigma_sd / fy_d)
            v_atrito = min(e.mu * axial / c.a2, tau_rd * g.lx * g.ly)
            texto_t = (
                f"t_p,min = ℓ_max·√(2·σ_c,Sd/(f_y/γ_a1)), ℓ_max = máx(m; n; λ·n₀) = "
                f"{_n(l_max, 1)} mm; {texto_zona}"
            )
        elif caso in ("C3", "T3"):
            linhas.append(
                _limite(
                    "Equilíbrio possível com a placa (flexão oblíqua)",
                    obliqua.equilibrio,
                    f"{REF} 6.7.1.1 (método geral)",
                    "a pressão σ_c,Rd numa zona da placa limitada por uma linha neutra inclinada e "
                    "os chumbadores tracionados equilibram N, M e M_y; senão, alterar a ligação "
                    "(placa maior, chumbadores mais afastados ou concreto melhor)",
                )
            )
            if obliqua.equilibrio:
                # ℓ_c: a maior profundidade da zona em ℓx, a faixa que manda no balanço m (como na
                # 6.7, p quando ℓ_c < m); o balanço n fica inteiro (a favor da segurança)
                profundidade = g.lx / 2 - min(x for x, _ in obliqua.zona)
                if profundidade >= g.m:
                    l_max = max(g.m, g.n, n0_lam) if caso == "C3" else max(g.m, g.n)
                else:
                    l_max = max(math.sqrt(profundidade * (2 * g.m - profundidade)), g.n)
                t_min1 = l_max * math.sqrt(2 * sigma_rd / fy_d)
                t_min2, texto_tracao = _espessura_pela_tracao(g, obliqua.forcas, fy_d)
                t_min = max(t_min1, t_min2)
                v_atrito = min(e.mu * sigma_rd * obliqua.area / c.a2, tau_rd * g.lx * g.ly)
                texto_t = (
                    f"maior entre t_p,min1 = ℓ_max·√(2·σ_c,Rd/(f_y/γ_a1)) = {_n(t_min1, 1)} mm "
                    f"(ℓ_max = {_n(l_max, 1)} mm; ℓ_c = {_n(profundidade, 1)} mm, a maior "
                    f"profundidade da zona em ℓx, e p = √(ℓ_c·(2m − ℓ_c)) se ℓ_c < m) e a flexão "
                    f"pela tração ({texto_tracao}); {texto_zona}"
                )
            else:
                texto_t = "sem solução: a pressão de contato não equilibra os dois momentos"
        else:  # T2: sem contato
            t_min, texto_tracao = _espessura_pela_tracao(g, obliqua.forcas, fy_d)
            texto_t = (
                f"F_i = N/n − M·x_i/Σx² − M_y·y_i/Σy²; flexão da placa pela tração: {texto_tracao}"
            )
            v_atrito = 0.0  # sem pressão de contato, sem atrito (6.7.2.3)
    elif caso == "C1":
        sigma_sd = axial / (g.lx * g.ly)
        l_max = max(g.m, g.n, n0_lam)
        t_min = l_max * math.sqrt(2 * sigma_sd / fy_d)
        v_atrito = min(e.mu * sigma_sd * g.lx * g.ly / c.a2, tau_rd * g.lx * g.ly)
        l_c = g.lx
        texto_t = (
            f"t_p,min = ℓ_max·√(2·σ_c,Sd/(f_y/γ_a1)), ℓ_max = máx(m; n; λ·n₀) = {_n(l_max, 1)} mm"
        )
    elif caso == "C2":
        l_c = g.lx - 2 * momento / axial
        sigma_sd = axial / (l_c * g.ly)
        l_max = max(g.m, g.n, n0_lam)
        t_min = l_max * math.sqrt(2 * sigma_sd / fy_d)
        v_atrito = min(e.mu * sigma_sd * l_c * g.ly / c.a2, tau_rd * g.lx * g.ly)
        texto_t = (
            f"t_p,min = ℓ_max·√(2·σ_c,Sd/(f_y/γ_a1)), ℓ_c = ℓx − 2e = {_n(l_c, 1)} mm, "
            f"ℓ_max = máx(m; n; λ·n₀) = {_n(l_max, 1)} mm"
        )
    elif caso in ("C3", "T3") and not da_norma:
        solucao = equilibrio_geral(g, sigma_rd, axial, momento)
        linhas.append(
            _limite(
                "Equilíbrio possível com a placa (raiz de ℓ_c)",
                solucao is not None,
                f"{REF} 6.7.2.2 {'c' if caso == 'C3' else 'f'}) (método geral)",
                "a pressão σ_c,Rd no trecho ℓ_c e os chumbadores tracionados equilibram N e M; "
                "senão, alterar a ligação (placa maior, chumbadores mais afastados ou concreto melhor)",
            )
        )
        if solucao is not None:
            l_c, forcas_gerais = solucao
            forcas = list(forcas_gerais)
            f_t = max(forcas)
            p = math.sqrt(max(l_c * (2 * g.m - l_c), 0.0))
            if l_c >= g.m:
                l_max = max(g.m, g.n, n0_lam) if caso == "C3" else max(g.m, g.n)
            else:
                l_max = max(p, g.n)
            t_min1 = l_max * math.sqrt(2 * sigma_rd / fy_d)
            t_min2, texto_tracao = _espessura_pela_tracao(g, forcas_gerais, fy_d)
            t_min = max(t_min1, t_min2)
            v_atrito = min(e.mu * sigma_rd * l_c * g.ly / c.a2, tau_rd * g.lx * g.ly)
            texto_t = (
                f"maior entre t_p,min1 = ℓ_max·√(2·σ_c,Rd/(f_y/γ_a1)) = {_n(t_min1, 1)} mm "
                f"(ℓ_max = {_n(l_max, 1)} mm) e a flexão pela tração ({texto_tracao}); "
                f"ℓ_c = {_n(l_c, 1)} mm"
            )
        else:
            texto_t = "sem solução: a pressão de contato não equilibra o momento"
    elif caso in ("C3", "T3"):
        equivalente = momento + axial * g.a if caso == "C3" else momento - abs(axial) * g.a
        l_c = _ell_c(g, sigma_rd, equivalente)
        sinal = "+" if caso == "C3" else "−"
        linhas.append(
            _limite(
                "Equilíbrio possível com a placa (raiz de ℓ_c)",
                l_c is not None,
                f"{REF} 6.7.2.2 {'c' if caso == 'C3' else 'f'})",
                f"(ℓx/2 + a)² ≥ 2·N_Sd·(e {sinal} a)/(σ_c,Rd·ℓy); senão, alterar a ligação "
                "(placa maior, chumbadores mais afastados ou concreto melhor)",
            )  # fmt: skip
        )
        if l_c is not None:
            if caso == "C3":
                f_t = 2 * (sigma_rd * l_c * g.ly - axial) / n_b
            else:
                f_t = 2 * (sigma_rd * l_c * g.ly + abs(axial)) / n_b
            f_t = max(f_t, 0.0)
            for i in lado_tracionado:
                forcas[i] = f_t
            p = math.sqrt(max(l_c * (2 * g.m - l_c), 0.0))
            if l_c >= g.m:
                l_max = max(g.m, g.n, n0_lam) if caso == "C3" else max(g.m, g.n)
            else:
                l_max = max(p, g.n)
            t_min1 = l_max * math.sqrt(2 * sigma_rd / fy_d)
            t_min2 = math.sqrt(2 * n_b * f_t * (g.m - g.a1) / (g.ly * fy_d)) if g.m > g.a1 else 0.0
            t_min = max(t_min1, t_min2)
            v_atrito = min(e.mu * sigma_rd * l_c * g.ly / c.a2, tau_rd * g.lx * g.ly)
            texto_t = (
                f"maior entre t_p,min1 = ℓ_max·√(2·σ_c,Rd/(f_y/γ_a1)) = {_n(t_min1, 1)} mm "
                f"(ℓ_max = {_n(l_max, 1)} mm) e t_p,min2 = √(2·n_b·F_t,Sd·(m − a₁)/(ℓy·f_y/γ_a1)) "
                f"= {_n(t_min2, 1)} mm; ℓ_c = {_n(l_c, 1)} mm"
            )
        else:
            texto_t = "sem solução: a pressão de contato não equilibra o momento"
    elif not da_norma:  # T1 e T2 do método geral
        forcas_gerais = forcas_sem_contato(g, axial, momento)
        forcas = list(forcas_gerais)
        f_t = max(forcas)
        t_min, texto_tracao = _espessura_pela_tracao(g, forcas_gerais, fy_d)
        texto_t = f"F_i = N/n − M·x_i/Σx²; flexão da placa pela tração: {texto_tracao}"
        v_atrito = 0.0  # sem pressão de contato, sem atrito (6.7.2.3)
    else:  # T1 e T2
        if caso == "T1":
            f_t = abs(axial) / n_b
            forcas = [f_t] * len(g.posicoes)
        else:
            f_t = abs(axial) / n_b + momento / (g.a * n_b)
            f_td = abs(axial) / n_b - momento / (g.a * n_b)
            for i in lado_tracionado:
                forcas[i] = f_t
            for i in lado_comprimido:
                forcas[i] = max(f_td, 0.0)
        if e.tipo == TIPO_1:
            t_min = math.sqrt(2 * n_b * f_t * (g.m - g.a1) / (g.ly * fy_d)) if g.m > g.a1 else 0.0
            texto_t = "t_p,min = √(2·n_b·F_t,Sd·(m − a₁)/(ℓy·(f_y/γ_a1))) (base tipo 1)"
        else:
            assert g.l0 is not None
            t_min = math.sqrt(n_b * f_t * max(g.a2 - g.t_w, 0.0) / (g.l0 * fy_d))
            texto_t = "t_p,min = √(n_b·F_t,Sd·(a₂ − t_w)/(ℓ₀·(f_y/γ_a1))) (base tipo 2)"
        v_atrito = 0.0  # sem pressão de contato, sem atrito (6.7.2.3)
    item_caso = {"C1": "a", "C2": "b", "C3": "c", "T1": "d", "T2": "e", "T3": "f"}[caso]
    ref_caso = f"{REF} 6.7.2.2 {item_caso})"
    if obliqua is not None:
        ref_caso = f"{REF} 6.7.2.2 {item_caso}) e 6.7.1.1 (flexão oblíqua)"
    # ------------------------------------------------------------------ concreto e placa
    if sigma_sd is not None and obliqua is not None:
        linhas.append(
            Verificacao(
                "Concreto: pressão de contato σ_c,Sd ≤ σ_c,Rd",
                sigma_sd,
                sigma_rd,
                "MPa",
                ref_cc,
                f"σ_c,Sd = N_Sd/A_c = {_n(axial / 1e3, 1)} kN/{_n(obliqua.area / 100, 0)} cm² = "
                f"{_n(sigma_sd)} MPa, A_c com o centro na resultante (e_x = M/N = "
                f"{_n(momento / axial, 0)} mm, e_y = M_y/N = {_n(momento_y / axial, 0)} mm); "
                f"{texto_sigma}",
            )  # fmt: skip
        )
    elif sigma_sd is not None:
        linhas.append(
            Verificacao(
                "Concreto: pressão de contato σ_c,Sd ≤ σ_c,Rd",
                sigma_sd,
                sigma_rd,
                "MPa",
                ref_cc,
                f"σ_c,Sd = N_Sd/(ℓ_c·ℓy) = {_n(axial / 1e3, 1)} kN/({_n(l_c or g.lx, 0)} × "
                f"{_n(g.ly, 0)}) = {_n(sigma_sd)} MPa; {texto_sigma}",
            )  # fmt: skip
        )
    elif caso in ("C3", "T3"):
        trecho = "na zona comprimida A_c" if obliqua is not None else "no trecho ℓ_c"
        linhas.append(_info("Concreto: pressão de contato", f"σ_c = σ_c,Rd {trecho}; {texto_sigma}", ref_cc))  # fmt: skip
    linhas.append(
        Verificacao(
            "Placa de base: espessura t_p ≥ t_p,min",
            t_min,
            e.t_placa_mm,
            "mm",
            ref_caso,
            f"{texto_t}; f_y = {_n(fy, 0)} MPa ({e.aco_placa}), γ_a1 = {_n(c.a1)}",
        )  # fmt: skip
    )
    # ------------------------------------------------------------------ chumbadores
    inicios.append((GRUPO_CHUMBADORES, len(linhas)))
    if f_t > 0:
        d_min = math.sqrt(4 * f_t / (0.75 * math.pi * aco_ch.f_u / c.a2))
        linhas.append(
            Verificacao(
                "Chumbador: diâmetro d_b ≥ d_b,min",
                d_min,
                tab.d_b,
                "mm",
                ref_caso,
                f"d_b,min = √(4·F_t,Sd/(0,75·π·f_ub/γ_a2)), F_t,Sd = {_n(f_t / 1e3, 1)} kN no "
                f"chumbador mais tracionado, f_ub = {_n(aco_ch.f_u, 0)} MPa ({e.aco_chumbador}), "
                f"γ_a2 = {_n(c.a2)}",
            )  # fmt: skip
        )
    linhas_ancoragem, avisos_ancoragem = verificar_ancoragem(e, g, tab, tuple(forcas))
    linhas.extend(linhas_ancoragem)
    avisos.extend(avisos_ancoragem)
    # ------------------------------------------------------------------ cortante
    inicios.append((GRUPO_CORTANTE, len(linhas)))
    v_rd = v_atrito
    if e.cortante == CORTANTE_ATRITO:
        if v_rd <= 0:  # T1 e T2 (ou C3/T3 sem equilíbrio): não há pressão de contato, nem atrito
            texto_v = (
                f"V_Sd = {_n(v_sd / 1e3, 1)} kN sem pressão de contato sob a placa: não há atrito; "
                "a cortante precisa de placa de cisalhamento ou de arruelas soldadas"
                if v_sd > 0
                else "sem cortante de cálculo"
            )
            linhas.append(
                _limite("Cortante: atrito na argamassa", v_sd <= 0, f"{REF} 6.7.2.3", texto_v)
            )
        else:
            area = "ℓx·ℓy" if caso == "C1" else ("A_c" if obliqua is not None else "ℓ_c·ℓy")
            texto_v = (
                f"V_Rd = μ·σ_c·{area}/γ_a2 ≤ τ_c,Rd·ℓx·ℓy, μ = {_n(e.mu)}, τ_c,Rd = 0,2·f_ck/γ_c "
                f"≤ 4 MPa = {_n(tau_rd)} MPa"
            )
            linhas.append(Verificacao("Cortante: atrito na argamassa", v_sd / 1e3, v_rd / 1e3, "kN", ref_caso, texto_v))  # fmt: skip
        if v_sd > v_rd + 1e-6:
            avisos.append(
                "A cortante passa do atrito: use placa de cisalhamento ou arruelas soldadas "
                "(6.7.2.3); com o dispositivo, só ele resiste à cortante."
            )
    elif e.cortante == CORTANTE_PLACA:
        sigma4 = tensao_resistente_do_concreto(e.fck_MPa, 4.0, e.combinacao)
        v_rd = sigma4 * max(e.b_v_mm - g.e_n, 0.0) * e.b_h_mm
        linhas.append(
            Verificacao(
                "Cortante: placa de cisalhamento",
                v_sd / 1e3,
                v_rd / 1e3,
                "kN",
                f"{REF} 6.7.2.4",
                f"V_Rd = σ_c,Rd·(b_v − e_n)·b_h = {_n(sigma4)} × ({_n(e.b_v_mm, 0)} − {_n(g.e_n, 0)}) "
                f"× {_n(e.b_h_mm, 0)}; σ_c,Rd = 1,7·f_ck/γ_c, com A₂/A₁ = 4 (6.6.5)",
            )  # fmt: skip
        )
        t_pv_min = math.sqrt(2 * v_sd * (e.b_v_mm + g.e_n) / (e.b_h_mm * fy_d)) if v_sd > 0 else 0.0
        linhas.append(
            Verificacao(
                "Placa de cisalhamento: espessura t_pv ≥ t_pv,min",
                t_pv_min,
                e.t_pv_mm,
                "mm",
                f"{REF} 6.7.2.4",
                "t_pv,min = √(2·V_Sd·(b_v + e_n)/(b_h·(f_y/γ_a1)))",
            )  # fmt: skip
        )
        linhas.append(
            Verificacao(
                "Placa de cisalhamento não mais espessa que a placa de base",
                e.t_pv_mm,
                e.t_placa_mm,
                "mm",
                f"{REF} 6.7.2.4",
                "t_pv ≤ t_p; se for preciso mais, aumentar a espessura da placa de base",
            )  # fmt: skip
        )
        m_solda = 0.5 * sigma4 * e.b_h_mm * (e.b_v_mm**2 - g.e_n**2)
        linhas.append(
            _info(
                "Solda da placa de cisalhamento: esforços",
                f"V_Rd = {_n(v_rd / 1e3, 1)} kN com M_Sd = ½·σ_c,Rd·b_h·(b_v² − e_n²) = "
                f"{_n(m_solda / 1e6, 2)} kN·m (sem penetração total, a solda resiste aos dois juntos)",
                f"{REF} 6.7.2.4",
            )  # fmt: skip
        )
    else:  # arruelas soldadas
        a_b = math.pi * tab.d_b**2 / 4
        f_v_barra = ALFA_V_CHUMBADOR * a_b * aco_ch.f_u / c.a2
        f_v_contato, l_f = contato_no_furo_da_arruela(tab, g.t_arruela, c.a2)
        f_v = min(f_v_barra, f_v_contato)  # 6.3.3.2 pede também a 6.3.3.3
        alfa = (
            1.45 * (e.t_placa_mm + 0.5 * g.t_arruela) / tab.d_b * (aco_ch.f_u / fy) * (c.a1 / c.a2)
        )
        teto = 5 * tab.d_b**2 * sigma_rd
        v_rd = 0.0
        for f_ti in forcas:
            t = 0.533 * f_ti
            radicando = (1 + alfa**2) * f_v**2 - t**2
            v_i = (math.sqrt(radicando) - alfa * t) / (1 + alfa**2) if radicando > 0 else 0.0
            v_rd += min(max(v_i, 0.0), teto)
        linhas.append(
            Verificacao(
                "Cortante: arruelas especiais soldadas",
                v_sd / 1e3,
                v_rd / 1e3,
                "kN",
                f"{REF} 6.7.2.5",
                f"V_Rd = Σ V_Rd,i, V_Rd,i = [√((1 + α²)·F_v,Rd,i² − (0,533·F_t,Sd,i)²) − "
                f"α·0,533·F_t,Sd,i]/(1 + α²) ≤ 5·d_b²·σ_c,Rd; α = {_n(alfa, 3)}, t_a = "
                f"{_n(g.t_arruela, 1)} mm; F_v,Rd,i = mín(corte 0,45·A_b·f_ub/γ_a2 = "
                f"{_n(f_v_barra / 1e3, 1)} kN (6.3.3.2 a); contato no furo da arruela "
                f"mín(1,2·ℓ_f; 2,4·d_b)·t_a·f_u/γ_a2 = {_n(f_v_contato / 1e3, 1)} kN (6.3.3.3, "
                f"ℓ_f = {_n(l_f, 1)} mm, f_u = {_n(FU_ARRUELA, 0)} MPa)) = {_n(f_v / 1e3, 1)} kN",
            )  # fmt: skip
        )
        linhas.append(
            _info(
                "Solda das arruelas de cima na placa",
                f"cada solda resiste a F_v,Rd,i = {_n(f_v / 1e3, 1)} kN; as arruelas de baixo, entre "
                "a placa e a porca de nivelamento, não se soldam",
                f"{REF} 6.7.2.5",
            )
        )
    # ------------------------------------------------------------------ disposições construtivas
    ref_18 = f"{REF} Tabela 18"
    inicios.append((GRUPO_CONSTRUTIVAS, len(linhas)))
    # disposições construtivas: limites (OK ou NÃO OK), não aproveitamento
    linhas.append(
        _limite(
            "Distância a₁ (furo à borda da placa)",
            g.a1 >= tab.a1 - 1e-9,
            ref_18,
            f"a₁ = {_n(g.a1, 0)} mm ≥ {_n(tab.a1, 0)} mm para Ø {tab.polegada}",
        )  # fmt: skip
    )
    linhas.append(
        _limite(
            "Espaçamento a₂ entre chumbadores",
            g.a2 >= tab.a2 - 1e-9,
            ref_18,
            f"a₂ = {_n(g.a2, 0)} mm ≥ {_n(tab.a2, 0)} mm para Ø {tab.polegada}",
        )  # fmt: skip
    )
    if e.tipo == TIPO_2:
        linhas.append(
            _limite(
                "Tipo 2: a₁ na direção ℓx",
                A1_X_MINIMO_TIPO_2 - 1e-9 <= g.a1_x <= tab.a1 + 1e-9,
                f"{ref_18}, nota f",
                f"a₁ = {_n(g.a1_x, 0)} mm (a placa passa 2·a₁ = {_n(2 * g.a1_x, 0)} mm da mesa): de "
                f"{_n(A1_X_MINIMO_TIPO_2, 0)} a {_n(tab.a1, 0)} mm para Ø {tab.polegada}",
            )  # fmt: skip
        )
    if e.ancoragem == ANCORAGEM_PORCA:  # nota b: o f_ck,mín é o da região da porca da ponta
        linhas.append(
            _limite(
                "Concreto: f_ck ≥ f_ck,mín",
                e.fck_MPa >= tab.fck_min - 1e-9,
                f"{ref_18}, nota b",
                f"f_ck = {_n(e.fck_MPa, 0)} MPa ≥ {_n(tab.fck_min, 0)} MPa para Ø {tab.polegada}, "
                "para não esmagar o concreto junto à porca da ponta",
            )  # fmt: skip
        )
    n_b_min, b_b_min, a_b_min = bloco_minimo(e, g, tab)
    if e.bloco_x_mm > 0 and e.bloco_y_mm > 0:
        a3_a1 = tab.a3 - tab.a1
        ref_bloco = f"{ref_18}, " + ("notas e e g" if e.tipo == TIPO_2 else "nota e")
        linhas.append(
            _limite(
                "Bloco: N_b ao longo de ℓx",
                e.bloco_x_mm >= n_b_min - 1e-9,
                ref_bloco,
                f"N_b = {_n(e.bloco_x_mm, 0)} mm ≥ máx(N_b,mín; ℓx + 2·e_n; ℓx + 2·(a₃ − a₁)) = "
                f"máx({_n(tab.n_b_min, 0)}; {_n(g.lx + 2 * g.e_n, 0)}; {_n(g.lx + 2 * a3_a1, 0)}) "
                f"= {_n(n_b_min, 0)} mm, com a placa centrada no bloco",
            )  # fmt: skip
        )
        linhas.append(
            _limite(
                "Bloco: B_b ao longo de ℓy",
                e.bloco_y_mm >= b_b_min - 1e-9,
                ref_bloco,
                f"B_b = {_n(e.bloco_y_mm, 0)} mm ≥ máx(ℓy + 2·e_n; ℓy + 2·(a₃ − a₁)) = "
                f"máx({_n(g.ly + 2 * g.e_n, 0)}; {_n(g.ly + 2 * a3_a1, 0)}) = {_n(b_b_min, 0)} mm",
            )  # fmt: skip
        )
    d_a = 0.5 * (embutimento(e, tab) - 0.5 * (tab.r2 + tab.d_b))  # nota h
    soldadas = e.cortante == CORTANTE_ARRUELAS
    detalhamento = (
        ("Placa", f"{_n(g.lx, 0)} × {_n(g.ly, 0)} × {_n(e.t_placa_mm, 1)} mm ({e.aco_placa})"),
        (
            "Chumbadores",
            f"{n_b} × Ø {tab.polegada} ({_n(tab.d_b, 0)} mm), {e.aco_chumbador}, porca sextavada "
            "pesada",
        ),
        ("Disposição", TIPOS[e.tipo]),
        ("Furo na placa", f"d_f = {_n(tab.d_f, 0)} mm"),
        ("Ancoragem", _texto_da_ancoragem(e, tab)),
        (
            "Arruelas especiais",
            f"{tab.arruela} mm, espessura {_n(g.t_arruela, 1)} mm, aço com f_y = 345 MPa, furo "
            f"d_b + 1,5 = {_n(tab.d_b + FOLGA_DO_FURO_DA_ARRUELA, 1)} mm; uma também entre a placa "
            "e a porca de nivelamento; "
            + ("as de cima soldadas à placa (6.7.2.5)" if soldadas else "soltas (nota d)"),
        ),
        (
            "Argamassa expansiva",
            f"e_n = {_n(g.e_n, 0)} mm; f_ck ≥ 2 × {_n(e.fck_MPa, 0)} = {_n(2 * e.fck_MPa, 0)} MPa (6.7.1.5 d)",
        ),  # fmt: skip
        (
            "Armadura mínima do bloco",
            f"Ø {_n(tab.phi_armadura, 1)} mm a cada {_n(tab.s_armadura, 0)} mm; armadura vertical a "
            f"até d_a = ½·[h₁ − 0,5·(r₂ + d_b)] = {_n(d_a, 0)} mm dos chumbadores (nota h; mais "
            "longe, recalcular a armadura)",
        ),  # fmt: skip
        (
            "Bloco mínimo",
            f"N_b ≥ {_n(n_b_min, 0)} mm ao longo de ℓx, B_b ≥ {_n(b_b_min, 0)} mm, altura ≥ "
            f"máx(h₁ + 100; N_b) = {_n(a_b_min, 0)} mm; f_ck,mín = {_n(tab.fck_min, 0)} MPa; "
            "dimensionado pela NBR 6118 (nota e)",
        ),  # fmt: skip
    )
    fins = [inicio for _, inicio in inicios[1:]] + [len(linhas)]
    grupos = tuple(
        (nome, tuple(linhas[inicio:fim]))
        for (nome, inicio), fim in zip(inicios, fins, strict=True)
        if fim > inicio
    )
    return ResultadoBase(
        e, caso, g, sigma_rd, sigma_sd, l_c, f_t, tuple(forcas), t_min, d_min, v_rd,
        tuple(linhas), tuple(avisos), detalhamento, grupos, zona,
    )  # fmt: skip


# =============================================================================================
# A base mais leve que atende, o texto do resultado e o registro técnico
# =============================================================================================
def base_mais_leve(e: EntradaBase) -> ResultadoBase | None:
    """A base que atende com a placa mais leve, trocando o chumbador e a espessura (comercial).

    O resto fica como está (perfil, tipo, número de chumbadores, a₁/a₂ informados, concreto,
    esforços e dispositivo de cortante). None quando nenhuma combinação atende — então o que
    reprova não depende da placa nem do chumbador (por exemplo a cortante ou o concreto). O N_Rd
    do fabricante de um pós-instalado vale só para o diâmetro informado: então só a espessura muda.
    """
    melhor: ResultadoBase | None = None
    fixo = e.ancoragem in POS_INSTALADOS and e.n_rd_fabricante_kN > 0
    for chumbador in [e.chumbador] if fixo else list(TABELA_18):
        for t in ESPESSURAS_COMERCIAIS:
            try:
                r = calcular(replace(e, chumbador=chumbador, t_placa_mm=t))
            except BaseInvalida:
                break
            if r.status == "NÃO OK":
                continue
            if melhor is None or r.massa_da_placa_kg < melhor.massa_da_placa_kg - 1e-9:
                melhor = r
            break  # a próxima espessura deste chumbador só pesa mais
    return melhor


def destaque(r: ResultadoBase) -> str:
    """Uma frase com o resultado (tela, registro e memorial)."""
    e, g = r.entrada, r.geometria
    tab = TABELA_18[e.chumbador]
    tipo = NOMES_CURTOS[e.tipo]
    governante = r.governante
    gov = (
        f"; governa: {governante.nome} ({100 * (governante.aproveitamento or 0):.0f} %)"
        if governante is not None and governante.aproveitamento is not None
        and math.isfinite(governante.aproveitamento)
        else ""
    )  # fmt: skip
    return (
        f"Base {tipo} do {e.perfil}: placa {_n(g.lx, 0)} × {_n(g.ly, 0)} × "
        f"{_n(e.t_placa_mm, 1)} mm ({e.aco_placa}), {e.n_chumbadores} chumbadores Ø {tab.polegada}; "
        f"N_Sd = {_n(e.n_sd_kN, 1)} kN, M_Sd = {_n(e.m_sd_kNm, 1)} kN·m"
        + (f", M_Sd,y = {_n(e.m_sd_y_kNm, 1)} kN·m" if e.m_sd_y_kNm else "")
        + f", V_Sd = {_n(e.v_sd_kN, 1)} kN"
        f" — caso {r.caso}, t_p,min = {_n(r.t_p_min, 1)} mm{gov}."
    )


def entrada_de_dicionario(dados: Mapping[str, Any]) -> EntradaBase:
    """A entrada gravada no registro (só os campos conhecidos; o resto fica no padrão)."""
    conhecidos = {f.name for f in fields(EntradaBase)}
    return EntradaBase(**{k: v for k, v in dados.items() if k in conhecidos})


def registro_base(
    r: ResultadoBase, *, contexto: Mapping[str, Any] | None = None, responsavel: str = ""
) -> dict[str, Any]:
    """O registro técnico da base de pilar, com a entrada para o memorial redesenhar a figura."""
    e, g = r.entrada, r.geometria
    tab = TABELA_18[e.chumbador]
    geral = r.status
    texto = destaque(r)
    entradas: dict[str, Any] = {
        "perfil": e.perfil,
        "tipo_de_base": TIPOS[e.tipo],
        "chumbadores": f"{e.n_chumbadores} × Ø {tab.polegada} ({e.aco_chumbador})",
        "ancoragem": ANCORAGENS[e.ancoragem],
        "ancoragem_no_concreto": "ACI 318-19, Capítulo 17"
        if e.verificar_concreto or e.ancoragem != ANCORAGEM_PORCA
        else None,
        "placa": f"{_n(g.lx, 0)} × {_n(g.ly, 0)} × {_n(e.t_placa_mm, 1)} mm ({e.aco_placa})",
        "a1_mm": g.a1,
        "a1_x_mm": g.a1_x if e.tipo == TIPO_2 else None,
        "a2_mm": g.a2,
        "fck_MPa": e.fck_MPa,
        "razao_A2_A1": round(razao_de_areas(e, g.lx, g.ly), 3),
        "bloco_mm": f"{_n(e.bloco_x_mm, 0)} × {_n(e.bloco_y_mm, 0)}"
        if e.bloco_x_mm > 0 and e.bloco_y_mm > 0
        else None,
        "N_Sd_kN": e.n_sd_kN,
        "M_Sd_kNm": e.m_sd_kNm or None,
        "M_Sd_y_kNm": e.m_sd_y_kNm or None,
        "V_Sd_kN": e.v_sd_kN or None,
        "combinacao": sd.COMBINACOES[e.combinacao],
        "cortante_resistida_por": CORTANTES[e.cortante],
    }
    entradas.update(dict(contexto or {}))
    entradas = {k: v for k, v in entradas.items() if v is not None}
    alertas = [f"{v.nome}: {v.formula}" for v in r.verificacoes if v.status in ("NÃO OK", "ALERTA")]
    alertas.extend(r.avisos)
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=f"Base de pilar {e.perfil} — placa {_n(g.lx, 0)} × {_n(g.ly, 0)} × {_n(e.t_placa_mm, 1)} mm",  # fmt: skip
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=texto,
        entradas=entradas,
        resultados={
            "status_geral": geral,
            "caso": r.caso,
            "verificações": linhas_para_registro(list(r.verificacoes)),
            "utilizacao_maxima": numero_json(r.aproveitamento_maximo, 4),
            "destaque_memorial": texto,
            "figura_base_de_pilar": {"entrada": asdict(e)},
        },
        metodo=(
            "Base de pilar de perfil I ou H com placa retangular, chumbadores e argamassa "
            "expansiva pela ABNT NBR 8800:2025, Subseção 6.7: caso pela força axial e pela "
            "excentricidade (6.7.1.4), espessura mínima da placa, diâmetro mínimo dos chumbadores "
            "e cortante (6.7.2.2 a 6.7.2.5), disposições construtivas da Tabela 18."
            + (
                ""
                if e.tipo in TIPOS_DA_NORMA
                else " Disposição fora da Figura 21 (6.7.1.1): o mesmo método com os chumbadores "
                "em mais de uma linha — pressão σ_c,Rd no trecho ℓ_c e forças nos chumbadores "
                "proporcionais à distância à borda comprimida (placa rígida); sem contato, "
                "F_i = N/n − M·x_i/Σx²."
            )
            + (
                " Flexão oblíqua (M_Sd,y): o mesmo método em duas direções — pressão σ_c na "
                "zona além de uma linha neutra inclinada (sem tração, com o centro na resultante; "
                "com tração, σ_c,Rd e chumbadores proporcionais à distância a ela)."
                if e.m_sd_y_kNm
                else ""
            )
        ),
        premissas=[
            "Esforços de cálculo (ELU); "
            + (
                "momentos nos dois eixos do pilar (flexão oblíqua pelo método geral)."
                if e.m_sd_y_kNm
                else "momento só em torno do eixo de maior inércia do pilar."
            ),
            f"Placa centrada no bloco; chumbadores de {e.aco_chumbador} com porca sextavada "
            f"pesada; ancoragem: {ANCORAGENS[e.ancoragem].lower()}.",
            "Pressão de contato resistente pela 6.6.5: 0,85·f_ck/γ_c·√(A₂/A₁) ≤ 1,7·f_ck/γ_c.",
            NOTA_TABELA_18,
        ],
        alertas=alertas,
        referencias=[
            "ABNT NBR 8800:2025, Subseção 6.7 (bases de pilares) e Tabela 18.",
            "ABNT NBR 8800:2025, 6.6.5 (pressão de contato no concreto).",
        ]
        + (
            ["ABNT NBR 8800:2025, 6.3.3.2 e 6.3.3.3 (corte do chumbador e contato no furo)."]
            if e.cortante == CORTANTE_ARRUELAS
            else []
        )
        + (
            ["ACI 318-19, Capítulo 17 (ancoragem no concreto: arrancamento, cone, borda)."]
            if e.verificar_concreto or e.ancoragem != ANCORAGEM_PORCA
            else []
        ),
        conclusao=texto,
        responsavel=responsavel,
    )


def memorial_da_base(
    r: ResultadoBase, *, projeto: Mapping[str, Any] | None = None, formato: str = "word"
) -> bytes:
    """O memorial só desta base, em Word ou PDF, no padrão do memorial do projeto."""
    import importlib

    from core.technical_records import normalizar_registro_tecnico

    # o gerador do memorial está fora da lista do mypy: importado pelo nome (como em ligacoes)
    relatorio = importlib.import_module("core.project_report")
    registro = normalizar_registro_tecnico(registro_base(r))
    base: dict[str, Any] = dict(projeto) if projeto else {"nome": MODULO_TITULO}
    base["registros_tecnicos"] = [registro]
    nome = (
        "gerar_relatorio_industrial_pdf" if formato == "pdf" else "gerar_relatorio_industrial_word"
    )
    conteudo: bytes = getattr(relatorio, nome)(base, secoes_incluidas=["registros"])
    return conteudo
