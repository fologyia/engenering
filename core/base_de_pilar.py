"""Base de pilar de perfil I, H ou U pela ABNT NBR 8800:2025, Subseção 6.7 (Bases de pilares).

Placa de base retangular soldada ao pilar e presa ao bloco de concreto por chumbadores, com
argamassa expansiva de assentamento (6.7.1.2). Dois tipos (Figura 21): **tipo 1**, chumbadores
externos às mesas (4 ≤ n_b ≤ 8), e **tipo 2**, chumbadores internos (n_b = 4). Momento só em torno
do eixo de maior inércia (6.7.1.3).

**Pilar de perfil U** (canal laminado). A 6.7 é escrita para o perfil I ou H; o U vai pelo mesmo
método (6.7.1.1 admite outras soluções, atendendo 6.1.1.3), com a placa centrada no **centro
geométrico** do U (onde atuam N, M e M_y do modelo), a alma ao longo de ℓx e as mesas abertas para
+y. O U é tratado como **meia seção I de mesa 2·b_f** cortada pela alma: os balanços em ℓx são os
mesmos da I (m = (ℓx − 0,95·d)/2, mesas nos dois lados); em ℓy, as linhas de engaste ficam no dorso
da alma e a 0,80·b_f dele (a linha 0,80·(2·b_f)/2 da I equivalente), e n é o maior dos dois
balanços (o do dorso e o das pontas das mesas); o trecho entre as mesas usa n₀ = √(d·2·b_f)/4 e o
fator X com 2·b_f. Só a tipo 1 e a rotulada em x (chumbadores fora das mesas) valem para o U: a
tipo 2 e as outras contam com chumbadores dos dois lados da alma. A solda do contorno leva os esforços do
centro do U ao centro do grupo de filetes (dorso, mesas por fora e por dentro, face interna da
alma).

Três disposições comuns fora da Figura 21 (6.7.1.1 admite outras, atendendo 6.1.1.3) vão pelo
**método geral**, o mesmo da 6.7 com os chumbadores em mais de uma linha: a base **rotulada em y**
(2 chumbadores no eixo y, um de cada lado da alma: gira no eixo forte), a **rotulada em x** (2 no
eixo x, um fora de cada mesa, na linha da alma: gira no eixo fraco; ℓy = máx(2·a₁; perfil + 25 mm))
e a de chumbadores **internos e externos** (4 + 4). Nos casos com momento grande (C3 e T3) a pressão de contato é a mesma da norma
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

**Várias combinações.** A base de verdade passa por compressão alta numa combinação e por tração
(ou momento grande com pouca compressão) em outra. Com ``EntradaBase.casos``, cada combinação passa
pelo cálculo inteiro (o caso C1 a T3 sai de cada uma) e o resultado é a **envoltória**: em cada
verificação vale a combinação mais desfavorável, com o nome dela no começo da fórmula, e a base
desenhada é a da combinação que governa.

**Soldas** (:mod:`core.base_de_pilar_soldas`): o contorno do pilar na placa (método elástico com
N, M, M_y e V, ou só a tração com a compressão por contato), os filetes da placa de cisalhamento e
os das arruelas soldadas, com os limites de 6.2.6.

**Cortante no concreto** (ACI 318-19), quando a ancoragem no concreto é verificada: com as arruelas
soldadas, a ruptura da borda do bloco pela fila da frente (17.7.2), o arrancamento por alavanca do
grupo (17.7.3) e a interação tração × cortante (17.8); com a placa de cisalhamento, a ruptura do
concreto à frente dela (17.11.3).
Unidades: mm, N, MPa (kN e kN·m na entrada e na saída).
"""

from __future__ import annotations

import functools
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, fields, replace
from itertools import combinations
from typing import Any

from core import base_de_pilar_soldas as bs
from core import section_catalog as sc
from core import soldas as sd
from core.bolted_connection import coeficientes_contato
from core.ligacoes import ACOS, ACOS_FRIO
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    ORDEM_STATUS,
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
TIPO_ROTULADA = "rotulada_2"  # em y: os 2 chumbadores no eixo y, um de cada lado da alma
TIPO_ROTULADA_X = "rotulada_x"  # em x: os 2 chumbadores no eixo x, fora das mesas
TIPO_INTERNOS_E_EXTERNOS = "internos_e_externos"
TIPOS = {
    TIPO_1: "Tipo 1 — chumbadores externos às mesas",
    TIPO_2: "Tipo 2 — chumbadores internos (entre as mesas)",
    TIPO_ROTULADA: "Rotulada em y — 2 chumbadores no eixo y, um de cada lado da alma",
    TIPO_ROTULADA_X: "Rotulada em x — 2 chumbadores no eixo x, fora das mesas",
    TIPO_INTERNOS_E_EXTERNOS: "Internos e externos — 4 + 4 chumbadores",
}
#: Como a base aparece nas frases ("Base tipo 1 do W …", "Base rotulada do W …").
NOMES_CURTOS = {
    TIPO_1: "tipo 1",
    TIPO_2: "tipo 2",
    TIPO_ROTULADA: "rotulada em y",
    TIPO_ROTULADA_X: "rotulada em x",
    TIPO_INTERNOS_E_EXTERNOS: "com chumbadores internos e externos",
}
#: Os tipos da Figura 21; os outros vão pelo método geral (extensão da 6.7).
TIPOS_DA_NORMA = (TIPO_1, TIPO_2)
#: Quantos chumbadores cada disposição admite.
QUANTIDADES = {
    TIPO_1: (4, 6, 8),
    TIPO_2: (4,),
    TIPO_ROTULADA: (2,),
    TIPO_ROTULADA_X: (2,),
    TIPO_INTERNOS_E_EXTERNOS: (8,),
}
#: Disposições com chumbadores fora das mesas (a₁ da borda ao furo em ℓx).
TIPOS_EXTERNOS = (TIPO_1, TIPO_ROTULADA_X, TIPO_INTERNOS_E_EXTERNOS)
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
CORTANTE_DIRETOS = "chumbadores_diretos"
CORTANTE_AUTO = "automatico"
CORTANTES = {
    CORTANTE_ATRITO: "Só o atrito da placa na argamassa",
    CORTANTE_PLACA: "Placa de cisalhamento (6.7.2.4)",
    CORTANTE_ARRUELAS: "Arruelas especiais soldadas à placa (6.7.2.5)",
    CORTANTE_DIRETOS: "Chumbadores direto no furo da placa (com aviso)",
    CORTANTE_AUTO: "Automático (atrito ou chumbadores diretos)",
}
#: Os dispositivos em que a cortante passa pelos chumbadores.
CORTANTE_PELOS_CHUMBADORES = (CORTANTE_ARRUELAS, CORTANTE_DIRETOS)
#: Chumbadores direto no furo folgado: o engate é desigual e só metade conta (AISC DG1), até 2 —
#: na base de 2 chumbadores, 1 leva a cortante inteira até o outro encostar.
ENGATADOS_SEM_ARRUELA = 2


def engatados_sem_arruela(n_b: int) -> int:
    """Quantos chumbadores levam a cortante direto no furo folgado: metade, de 1 a 2."""
    return max(1, min(ENGATADOS_SEM_ARRUELA, n_b // 2))


# Distribuição da pressão de contato sob a placa.
DISTRIBUICAO_NBR = "bloco_uniforme"
DISTRIBUICAO_ELASTICA = "elastica"
DISTRIBUICOES = {
    DISTRIBUICAO_NBR: "Bloco uniforme da NBR 8800:2025 (6.7) — padrão",
    DISTRIBUICAO_ELASTICA: "Linear elástica (placa rígida, chumbadores pela compatibilidade)",
}
E_ACO = 200_000.0  # MPa (NBR 8800, 4.5.2.9)
# ACI 318-19: aço do chumbador à tração (17.6.1, φ 0,75) e à cortante (17.7.1, φ 0,65), com
# 0,80 sobre V_sa quando há camada de argamassa de assentamento (17.7.1.2.1).
PHI_ACO_TRACAO = 0.75
PHI_ACO_CORTANTE = 0.65
FATOR_ARGAMASSA = 0.80
FU_TETO_ACI = 862.0  # f_uta ≤ mín(1,9·f_ya; 862 MPa), ACI 318-19 17.6.1.2
FY_ARMADURA_DE_ANCORAGEM = 500.0  # CA-50 (NBR 7480); φ 0,75 da ACI 318-19 17.5.2.1
FAMILIAS_I = ("W (mesa larga)", "HP (perfil de estaca)", "I duplamente simétrico")
FAMILIAS_U = ("U (canal laminado)",)
FORMA_I = "I"
FORMA_U = "U"
#: As disposições que o pilar U admite (a tipo 2 e as outras precisam dos dois lados da alma).
TIPOS_DO_U = (TIPO_1, TIPO_ROTULADA_X)
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
GRUPO_CONSTRUTIVAS_FORMULA = "Disposições construtivas (por fórmula)"
GRUPO_SOLDAS = bs.GRUPO_SOLDAS
#: A ordem dos grupos na tela (a envoltória junta os de todas as combinações nesta ordem).
ORDEM_DOS_GRUPOS = (
    GRUPO_GEOMETRIA, GRUPO_CONCRETO_E_PLACA, GRUPO_CHUMBADORES, GRUPO_CORTANTE, GRUPO_SOLDAS,
    GRUPO_CONSTRUTIVAS, GRUPO_CONSTRUTIVAS_FORMULA,
)  # fmt: skip
PHI_CORTANTE_CONCRETO = 0.70  # ACI 318-19 17.5.3, condição B (sem armadura suplementar)
ACO_DO_PILAR_PADRAO = "ASTM A572 Gr 50"
#: Interação tração × cortante (ACI 318-19 17.8): dispensada quando uma das razões ≤ 0,2.
LIMITE_SEM_INTERACAO = 0.2


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
    # classes da ISO 898-1 que a NBR 8800 (6.3) admite, com os valores nominais
    "ISO 898-1 classe 4.6": AcoChumbador(240.0, 400.0, False),
    "ISO 898-1 classe 8.8": AcoChumbador(640.0, 800.0, False),
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
        LinhaTabela18('3/4"', 19, 40, 80, 120, 450, 150, 175, 50, 27, 6.3, "50 × 50", 40, 20, 900, 125, 10),
        LinhaTabela18('7/8"', 22, 45, 90, 140, 465, 200, 225, 50, 30, 6.3, "65 × 65", 50, 20, 900, 100, 10),
        LinhaTabela18('1"', 25, 50, 100, 160, 465, 200, 225, 50, 33, 8.0, "75 × 75", 60, 25, 900, 125, 12.5),
        LinhaTabela18('1 1/4"', 32, 65, 130, 190, 525, 225, 250, 60, 40, 9.5, "75 × 75", 60, 25, 1100, 100, 12.5),
        LinhaTabela18('1 1/2"', 38, 80, 160, 230, 610, 250, 275, 70, 46, 9.5, "90 × 90", 70, 25, 1300, 150, 16),
        LinhaTabela18('1 3/4"', 44, 90, 180, 270, 700, 300, 325, 70, 52, 12.5, "100 × 100", 80, 25, 1600, 125, 16),
        LinhaTabela18('2"', 50, 100, 200, 300, 850, 350, 375, 100, 58, 16.0, "125 × 125", 90, 30, 1800, 100, 16),
    )
}  # fmt: skip


@dataclass(frozen=True)
class CasoDeCarga:
    """Uma combinação de cálculo (ELU) na base: N positivo na compressão, M em kN·m, V em kN."""

    nome: str
    n_sd_kN: float
    m_sd_kNm: float = 0.0
    m_sd_y_kNm: float = 0.0
    v_sd_kN: float = 0.0
    vx_kN: float | None = None
    vy_kN: float | None = None
    mz_kNm: float = 0.0


def caso_de_dicionario(dados: Mapping[str, Any] | CasoDeCarga) -> CasoDeCarga:
    if isinstance(dados, CasoDeCarga):
        return dados
    return CasoDeCarga(
        str(dados.get("nome") or "").strip(),
        float(dados.get("n_sd_kN") or 0.0),
        float(dados.get("m_sd_kNm") or 0.0),
        float(dados.get("m_sd_y_kNm") or 0.0),
        float(dados.get("v_sd_kN") or 0.0),
        None if dados.get("vx_kN") is None else float(dados["vx_kN"]),
        None if dados.get("vy_kN") is None else float(dados["vy_kN"]),
        float(dados.get("mz_kNm") or 0.0),
    )


@dataclass(frozen=True)
class EntradaBase:
    """Os dados da base. Esforços de cálculo: N positivo na compressão, M em torno de x (kN·m).

    Com ``casos`` (várias combinações), os esforços de cada uma substituem N, M, M_y e V, e o
    resultado é a envoltória.
    """

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
    # chumbador fora da Tabela 18 (6.7.1.1): as medidas saem das fórmulas de MedidasPorFormula
    por_formula: bool = False  # então ``chumbador`` é uma chave de ROSCAS ou CHUMBADOR_LIVRE
    d_b_mm: float = 0.0  # CHUMBADOR_LIVRE: o diâmetro digitado
    passo_mm: float = 0.0  # CHUMBADOR_LIVRE: o passo da rosca (0 = o da métrica grossa mais perto)
    d_f_mm: float = 0.0  # por fórmula: o furo na placa (0 = o da regra)
    # várias combinações (envoltória): vazio = só os esforços acima
    casos: tuple[CasoDeCarga, ...] = ()
    # soldas (perna 0 = automática: a menor comercial que passa)
    aco_pilar: str = ACO_DO_PILAR_PADRAO
    eletrodo: str = bs.ELETRODO_PADRAO
    perna_pilar_mm: float = 0.0
    solda_mesas_por_dentro: bool = True
    solda_alma: bool = True
    compressao_por_contato: bool = False  # extremidade do pilar faceada (AISC 360-22 J1.4 a)
    perna_cisalhamento_mm: float = 0.0
    cisalhamento_penetracao_total: bool = (
        False  # placa de cisalhamento soldada com penetração total
    )
    perna_arruela_mm: float = 0.0
    bloco_z_mm: float = 0.0  # altura do bloco h_a (0 = a mínima): cortante no concreto
    # tamanho da placa informado (0 = o mínimo pela 6.7.2.1); maior que o mínimo, os chumbadores
    # ficam a a₁ da borda em ℓx (tipo 1) e centrados em ℓy
    lx_mm: float = 0.0
    ly_mm: float = 0.0
    # como a pressão de contato se distribui: o bloco uniforme da 6.7 ou a linear elástica
    distribuicao: str = DISTRIBUICAO_NBR
    vx_kN: float | None = None
    vy_kN: float | None = None
    mz_kNm: float = 0.0
    modo_bloco: str = "pre_dimensionamento"
    desloc_x_mm: float = 0.0  # centro da placa em relação ao centro do bloco
    desloc_y_mm: float = 0.0
    sistema_ancoragem: str = ""  # certificado, barra, condições de instalação
    categoria_aci: int = 0  # 0 = qualificação desconhecida
    aco_ductil: bool | None = None  # entradas antigas não declaram a ductilidade
    armadura_suplementar: bool = False
    tau_cr_MPa: float = 0.0
    tau_uncr_MPa: float = 0.0
    n_sustentada_kN: float | None = None  # maior demanda sustentada individual
    s_min_produto_mm: float = 0.0
    c_min_produto_mm: float = 0.0
    h_min_produto_mm: float = 0.0
    graute_rd_MPa: float = 0.0
    folga_servico_mm: float | None = None
    chapa_ponta_esp_mm: float = 0.0


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
    forma: str = FORMA_I  # FORMA_U: pilar U com o dorso da alma em y = y_dorso
    # U: a placa é centrada no centro geométrico do U; y_dorso = −x̄ (mesas abertas para +y, o
    # lado que M_y > 0 comprime) ou +x̄ (U espelhado, com M_y < 0: as contas usam |M_y|)
    y_dorso: float = 0.0

    @property
    def abertura(self) -> float:
        """+1 com as mesas do U abertas para +y, −1 para −y (0 na I)."""
        if not self.e_u:
            return 0.0
        return 1.0 if self.y_dorso <= 0 else -1.0

    @property
    def e_u(self) -> bool:
        return self.forma == FORMA_U

    @property
    def b_eq(self) -> float:
        """A largura de mesa da I equivalente (o U é meia I de mesa 2·b_f)."""
        return 2 * self.b_f if self.e_u else self.b_f

    @property
    def faixa_y(self) -> tuple[float, float]:
        """De onde a onde vai o perfil em y (mm, a partir do centro da placa)."""
        if self.e_u:
            return tuple(sorted((self.y_dorso, self.y_dorso + self.abertura * self.b_f)))  # type: ignore[return-value]
        return -self.b_f / 2, self.b_f / 2

    @property
    def engaste_y(self) -> tuple[float, float]:
        """As linhas de engaste do balanço n (y de baixo, y de cima): ±0,80·b_f/2 na I; no U, o
        dorso da alma e 0,80·b_f a partir dele."""
        if self.e_u:
            return tuple(sorted((self.y_dorso, self.y_dorso + self.abertura * 0.80 * self.b_f)))  # type: ignore[return-value]
        return -0.80 * self.b_f / 2, 0.80 * self.b_f / 2


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
    # as disposições usadas: a linha da Tabela 18 ou, por fórmula, as medidas calculadas
    disposicoes: LinhaTabela18 | None = None
    por_formula: MedidasPorFormula | None = None
    # por fórmula: (critério, d_b necessário em mm ou None se nenhum diâmetro atende, fonte)
    diametros: tuple[tuple[str, float | None, str], ...] = field(default=())
    # várias combinações: o resultado de cada uma e o nome da que governa
    casos: tuple[ResultadoDoCaso, ...] = field(default=())
    combinacao_governante: str = ""
    plano_pressao: tuple[float, float, float] = (0, 0, 0)
    residuos: tuple[float, float, float] = (0, 0, 0)  # kN e kN·m
    centro_pressao: tuple[float, float] | None = None
    perna_do_pilar: float = 0.0  # mm, a perna adotada na solda do pilar (a maior das combinações)

    @property
    def linha(self) -> LinhaTabela18:
        """As disposições construtivas da base (Tabela 18 ou por fórmula)."""
        return self.disposicoes or disposicoes(self.entrada)

    @property
    def status(self) -> str:
        return status_geral(list(self.verificacoes))

    @property
    def situacao(self) -> str:
        if self.status == "ALERTA":
            return "Inconclusivo"
        if self.status == "OK" and self.entrada.modo_bloco == "pre_dimensionamento":
            return "Pré-dimensionado"
        return self.status

    @property
    def equilibrio_valido(self) -> bool:
        return not any(
            v.nome.startswith("Equilíbrio") and v.status == "NÃO OK" for v in self.verificacoes
        )

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

    @property
    def envoltoria(self) -> bool:
        return bool(self.casos)


@dataclass(frozen=True)
class ResultadoDoCaso:
    """Uma combinação da envoltória e a base calculada só com ela."""

    caso: CasoDeCarga
    resultado: ResultadoBase


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor + 0.0:.{casas}f}".replace(".", ",")


def perfis_i() -> list[str]:
    """Os perfis I e H do catálogo, os do método da 6.7 (6.7.1.1)."""
    return [n for n, p in sc.listar_perfis().items() if p.familia in FAMILIAS_I]


def perfis_u() -> list[str]:
    """Os perfis U do catálogo (método da 6.7 estendido, ver o começo do módulo)."""
    return [n for n, p in sc.listar_perfis().items() if p.familia in FAMILIAS_U]


def perfis_do_pilar() -> list[str]:
    """Os perfis que a página oferece: os I e H e, depois, os U."""
    return perfis_i() + perfis_u()


def forma_do_perfil(nome: str) -> str:
    """FORMA_U para um U do catálogo; FORMA_I nos outros (o cálculo recusa o que não for I nem U)."""
    try:
        familia = sc.obter_perfil(nome).familia
    except (KeyError, sc.ErroDeCatalogo):
        return FORMA_I
    return FORMA_U if familia in FAMILIAS_U else FORMA_I


def tipos_do_perfil(nome: str) -> tuple[str, ...]:
    """As disposições que o perfil admite."""
    return TIPOS_DO_U if forma_do_perfil(nome) == FORMA_U else tuple(TIPOS)


def centroide_do_u(d: float, b_f: float, t_w: float, t_f: float) -> float:
    """x̄ do U (mm): distância do dorso da alma ao centro geométrico (alma d·t_w e duas mesas)."""
    a_alma = d * t_w
    a_mesas = 2 * (b_f - t_w) * t_f
    return (a_alma * t_w / 2 + a_mesas * (t_w + (b_f - t_w) / 2)) / (a_alma + a_mesas)


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
        k = min(
            (e.bloco_x_mm - 2 * abs(e.desloc_x_mm)) / lx,
            (e.bloco_y_mm - 2 * abs(e.desloc_y_mm)) / ly,
        )
        return max(k, 1.0) ** 2
    return max(e.razao_a2_a1, 1.0)


# =============================================================================================
# Chumbador fora da Tabela 18: as medidas por fórmula
# =============================================================================================
# A 6.7.1.1 admite outras configurações, desde que atendam 6.1.1.3. Fora dos diâmetros da
# Tabela 18, cada medida que ela dava sai de uma fórmula com fonte: a porca da ASME B18.2.6 (que
# a NBR 8800, 6.3, manda usar nas barras redondas rosqueadas), o furo e a arruela da AISC (Manual,
# Tabela 14-2, e Design Guide 1: são os mesmos furos da Tabela 18, em mm), o espaçamento e a borda
# da ACI 318-19 (17.9.2, que dão os 4·d_b e os ≈ 6·d_b da Tabela 18), o embutimento pelo cone de
# concreto (ACI 318-19 17.6.2) e o concreto mínimo da NBR 6118 (Tabela 7.1). A ancoragem no
# concreto passa a ser sempre verificada pela ACI 318-19, Capítulo 17.
CHUMBADOR_LIVRE = "livre"
SERIE_UNC = "UNC (ASME B1.1)"
SERIE_ISO = "ISO métrica grossa (ISO 261)"
SERIE_INFORMADA = "passo informado"
FAMILIA_POLEGADA = "polegada"
FAMILIA_METRICA = "métrica"
#: Como a série aparece nas frases ("série em polegada (UNC)", "série métrica (ISO)").
NOMES_DAS_FAMILIAS = {FAMILIA_POLEGADA: "em polegada (UNC)", FAMILIA_METRICA: "métrica (ISO)"}


@dataclass(frozen=True)
class Rosca:
    """O diâmetro e a rosca de um chumbador fora da Tabela 18 (mm)."""

    nome: str
    d_b: float
    passo: float
    serie: str

    @property
    def familia(self) -> str:
        return FAMILIA_POLEGADA if self.serie == SERIE_UNC else FAMILIA_METRICA

    @property
    def area_bruta(self) -> float:
        return math.pi * self.d_b**2 / 4

    @property
    def area_resistente(self) -> float:
        """A_s da rosca: π/4·(d − 0,9743·p)² na UNC (ASME B1.1), π/4·(d − 0,9382·p)² na ISO 898-1."""
        k = 0.9743 if self.serie == SERIE_UNC else 0.9382
        return math.pi / 4 * (self.d_b - k * self.passo) ** 2


def _polegadas(nome: str) -> float:
    """'2 1/2"' → 63,5 mm."""
    total = 0.0
    for parte in nome.rstrip('"').split():
        if "/" in parte:
            cima, baixo = parte.split("/")
            total += int(cima) / int(baixo)
        else:
            total += int(parte)
    return 25.4 * total


#: Fios por polegada da rosca UNC (ASME B1.1) dos chumbadores de 1/2" a 4" (ASTM F1554).
_FIOS_UNC = {
    '1/2"': 13, '5/8"': 11, '3/4"': 10, '7/8"': 9, '1"': 8, '1 1/8"': 7, '1 1/4"': 7,
    '1 3/8"': 6, '1 1/2"': 6, '1 3/4"': 5, '2"': 4.5, '2 1/4"': 4.5, '2 1/2"': 4, '2 3/4"': 4,
    '3"': 4, '3 1/4"': 4, '3 1/2"': 4, '3 3/4"': 4, '4"': 4,
}  # fmt: skip
#: Passo da rosca métrica grossa (ISO 261), mm.
_PASSOS_ISO = {
    10: 1.5, 12: 1.75, 16: 2.0, 20: 2.5, 24: 3.0, 27: 3.0, 30: 3.5, 33: 3.5, 36: 4.0, 39: 4.0,
    42: 4.5, 45: 4.5, 48: 5.0, 52: 5.0, 56: 5.5, 60: 5.5, 64: 6.0,
}  # fmt: skip
#: Os diâmetros comerciais que o modo por fórmula oferece, em ordem crescente em cada família.
ROSCAS: dict[str, Rosca] = {
    **{n: Rosca(n, _polegadas(n), 25.4 / fios, SERIE_UNC) for n, fios in _FIOS_UNC.items()},
    **{f"M{d}": Rosca(f"M{d}", float(d), p, SERIE_ISO) for d, p in _PASSOS_ISO.items() if d >= 12},
}
#: φ·k das distâncias da ACI 318-19 17.9.2 (sem dados do produto): espaçamento e borda em d_a.
#: Concretado: espaçamento 4·d_a (sem protensão) e borda 6·d_a (a do chumbador apertado, a favor
#: da segurança; a Tabela 18 usa a₃ ≈ 6·d_b). Pós-instalado: espaçamento 6·d_a; borda 6·d_a
#: (químico) e 8·d_a (expansão controlada por torque).
ESPACAMENTO_ACI = {ANCORAGEM_PORCA: 4.0, ANCORAGEM_GANCHO: 4.0, ANCORAGEM_QUIMICO: 6.0, ANCORAGEM_EXPANSAO: 6.0}  # fmt: skip
BORDA_ACI = {ANCORAGEM_PORCA: 6.0, ANCORAGEM_GANCHO: 6.0, ANCORAGEM_QUIMICO: 6.0, ANCORAGEM_EXPANSAO: 8.0}  # fmt: skip
CHAPA_ALEM_DO_FURO = 6.35  # ¼ in de chapa além do furo para furar sem desviar (AISC, FAQ 7.1.7)
FOLGA_DA_ARGAMASSA = 15.0  # mm de argamassa entre a arruela de nivelamento e o concreto
FIOS_ALEM_DA_PORCA = 3  # a rosca passa 3 fios da porca de cima (engajamento completo)
ROSCA_DENTRO_DO_CONCRETO = 25.0  # r₁ − h₂: 25 mm em todas as linhas da Tabela 18
R2_MINIMO = 50.0  # o menor r₂ da Tabela 18
FCK_MIN_NBR_6118 = 20.0  # concreto armado na classe de agressividade I (NBR 6118, Tabela 7.1)
EMBUTIMENTO_MINIMO_EM_D = (
    12.0  # piso do embutimento calculado (o padrão do programa no pós-instalado)
)
EMBUTIMENTO_MAXIMO = 3000.0  # mm: até onde a busca do embutimento pelo cone vai
NOTA_POR_FORMULA = (
    "Chumbador fora da Tabela 18 (6.7.1.1): medidas por fórmula — porca pela ASME B18.2.6, furo "
    "e arruela pela AISC (Manual, Tabela 14-2, e Design Guide 1), espaçamento e borda pela ACI "
    "318-19 (17.9.2), embutimento pelo cone de concreto (ACI 318-19 17.6.2) e f_ck mínimo pela NBR "
    "6118 (Tabela 7.1). A ancoragem no concreto é sempre verificada pela ACI 318-19, Capítulo 17, "
    "e o bloco e a armadura dele são dimensionados pela NBR 6118."
)


@dataclass(frozen=True)
class MedidasPorFormula:
    """As medidas de um chumbador fora da Tabela 18, cada uma com a conta e a fonte."""

    rosca: Rosca
    linha: LinhaTabela18  # no formato da Tabela 18 (h1 = embutimento h_ef)
    lado_da_porca: float  # s, entre faces (mm)
    altura_da_porca: float
    comprimento: float  # da barra inteira (mm)
    massa_kg: float  # de um chumbador
    contas: tuple[tuple[str, str, str], ...]  # (medida, valor, conta e fonte)


def _acima(valor: float, passo: float = 5.0) -> float:
    """O múltiplo de ``passo`` logo acima (ou igual)."""
    return math.ceil(valor / passo - 1e-9) * passo


def _mm(valor: float) -> str:
    return f"{valor:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def passo_iso_mais_perto(d_b: float) -> float:
    """O passo da rosca métrica grossa (ISO 261) do diâmetro de tabela mais perto de d_b."""
    return _PASSOS_ISO[min(_PASSOS_ISO, key=lambda d: (abs(d - d_b), d))]


def rosca_do_chumbador(e: EntradaBase) -> Rosca:
    """A rosca do chumbador por fórmula (comercial ou digitado)."""
    if e.chumbador == CHUMBADOR_LIVRE:
        if e.passo_mm > 0:
            return Rosca(f"{_mm(e.d_b_mm)} mm", e.d_b_mm, e.passo_mm, SERIE_INFORMADA)
        return Rosca(f"{_mm(e.d_b_mm)} mm", e.d_b_mm, passo_iso_mais_perto(e.d_b_mm), SERIE_ISO)
    return ROSCAS[e.chumbador]


def roscas_da_familia(familia: str) -> list[Rosca]:
    """Os diâmetros comerciais de uma família (polegada ou métrica), do menor ao maior."""
    return sorted((r for r in ROSCAS.values() if r.familia == familia), key=lambda r: r.d_b)


def furo_padrao(d_b: float) -> float:
    """d_f (mm): furo alargado da placa, d_b + 8 mm (a folga da Tabela 18 em todos os diâmetros).

    Abaixo de 19 mm e acima de 50 mm, a folga (d_f − d_b) da ponta da tabela. Arredondado para o
    milímetro de cima.
    """
    pontos = [(linha.d_b, linha.d_f) for linha in TABELA_18.values()]
    if d_b <= pontos[0][0]:
        furo = d_b + pontos[0][1] - pontos[0][0]
    elif d_b >= pontos[-1][0]:
        furo = d_b + pontos[-1][1] - pontos[-1][0]
    else:
        furo = next(
            f0 + (f1 - f0) * (d_b - d0) / (d1 - d0)
            for (d0, f0), (d1, f1) in zip(pontos, pontos[1:], strict=False)
            if d0 <= d_b <= d1
        )
    return _acima(furo, 1.0)


def furo_justo(e: EntradaBase, tab: LinhaTabela18) -> bool:
    """O furo informado é menor que o padrão (d_b + 8 mm) para o diâmetro."""
    return e.por_formula and e.d_f_mm > 0 and tab.d_f < furo_padrao(tab.d_b) - 1e-9


def espessura_da_arruela(d_b: float) -> float:
    """A chapa comercial com espessura ≥ d_b/3 (AISC Design Guide 1), com 2 % de tolerância."""
    alvo = d_b / 3 / 1.02
    return next((t for t in ESPESSURAS_COMERCIAIS if t >= alvo), _acima(d_b / 3, 1.0))


def lado_da_arruela(d_b: float, d_f: float) -> float:
    """Lado da arruela que cobre o furo com o chumbador encostado na borda dele: 2·d_f − d_b."""
    return _acima(2 * d_f - d_b)


def medidas_por_formula(e: EntradaBase, h_ef: float | None = None) -> MedidasPorFormula:
    """As disposições construtivas de um chumbador fora da Tabela 18 (sem h_ef: 12·d_b)."""
    rosca = rosca_do_chumbador(e)
    d, p = rosca.d_b, rosca.passo
    s = 1.5 * d + 3.2  # porca sextavada pesada, entre faces (ASME B18.2.6)
    altura = d  # altura da porca pesada ≈ d_b
    d_f = e.d_f_mm or furo_padrao(d)
    lado = lado_da_arruela(d, d_f)
    t_a = e.t_arruela_mm or espessura_da_arruela(d)
    k_s, k_c = ESPACAMENTO_ACI[e.ancoragem], BORDA_ACI[e.ancoragem]
    a2 = _acima(max(k_s * d, lado))
    a1 = _acima(max(a2 / 2, lado / 2, d_f / 2 + CHAPA_ALEM_DO_FURO))
    a3 = _acima(k_c * d)
    e_n = e.e_n_mm or _acima(altura + t_a + FOLGA_DA_ARGAMASSA)
    fios = FIOS_ALEM_DA_PORCA * p
    h2 = _acima(e_n + e.t_placa_mm + t_a + altura + fios)
    r1 = h2 + ROSCA_DENTRO_DO_CONCRETO
    r2 = max(R2_MINIMO, _acima(altura + fios))
    calculado = h_ef is None
    h = e.h_ef_mm or (h_ef if h_ef is not None else EMBUTIMENTO_MINIMO_EM_D * d)
    ponta = {
        ANCORAGEM_PORCA: e.chapa_ponta_esp_mm
        + altura
        + fios,  # a porca da ponta e a rosca abaixo dela
        ANCORAGEM_GANCHO: e.e_h_mm or 4.5 * d,  # o gancho (a curva não entra)
    }.get(e.ancoragem, 0.0)
    comprimento = h + h2 + ponta
    massa = rosca.area_bruta * comprimento * 1e-9 * DENSIDADE_ACO
    linha = LinhaTabela18(
        rosca.nome, d, a1, a2, a3, h, h2, r1, r2, d_f, t_a, f"{_mm(lado)} × {_mm(lado)}", e_n,
        FCK_MIN_NBR_6118, 0.0, 0.0, 0.0,
    )  # fmt: skip
    rotulo_k = "chumbador concretado" if e.ancoragem in CONCRETADOS else "pós-instalado"
    if e.h_ef_mm:
        conta_h = "informado"
    elif calculado:
        conta_h = f"provisório: {_mm(EMBUTIMENTO_MINIMO_EM_D)}·d_b (sai do cone de concreto)"
    else:
        conta_h = (
            "o menor, de 25 em 25 mm, que passa no cone de concreto dos tracionados (ACI 318-19 "
            "17.6.2) — se nenhum passa, o que mais ajuda neste bloco —, nunca menos que "
            f"{_mm(EMBUTIMENTO_MINIMO_EM_D)}·d_b = {_mm(EMBUTIMENTO_MINIMO_EM_D * d)} mm"
        )
    contas = (
        (
            "Rosca",
            f"Ø {rosca.nome}: d_b = {_mm(d)} mm, passo {_n(p, 2)} mm, rosca {rosca.serie}",
            f"A_b = {_n(rosca.area_bruta, 0)} mm²; área resistente A_s = π/4·(d − "
            f"{'0,9743' if rosca.serie == SERIE_UNC else '0,9382'}·p)² = {_n(rosca.area_resistente, 0)} "
            f"mm² ({'ASME B1.1' if rosca.serie == SERIE_UNC else 'ISO 898-1'}); a NBR usa "
            f"0,75·A_b = {_n(0.75 * rosca.area_bruta, 0)} mm²",
        ),
        (
            "Porca sextavada pesada",
            f"s = {_mm(s)} mm entre faces, altura ≈ {_mm(altura)} mm",
            "s = 1,5·d_b + 3,2 mm (ASME B18.2.6, a que a NBR 8800, 6.3, pede nas barras redondas "
            "rosqueadas)",
        ),
        (
            "Furo na placa d_f",
            f"{_mm(d_f)} mm",
            "informado" if e.d_f_mm else "furo alargado d_b + 8 mm (NBR 8800, furos alargados)",
        ),
        (
            "Arruela especial",
            f"{_mm(lado)} × {_mm(lado)} × {_mm(t_a)} mm",
            "lado ≥ 2·d_f − d_b: cobre o furo com o chumbador encostado na borda dele; espessura "
            + ("informada" if e.t_arruela_mm else "≥ d_b/3, chapa comercial")
            + " (AISC, Design Guide 1)",
        ),
        (
            "Espaçamento a₂",
            f"{_mm(a2)} mm",
            f"a₂ ≥ máx({_mm(k_s)}·d_b; lado da arruela) = máx({_mm(k_s * d)}; {_mm(lado)}) "
            f"({rotulo_k}, ACI 318-19 17.9.2)",
        ),
        (
            "Furo à borda da placa a₁",
            f"{_mm(a1)} mm",
            f"a₁ ≥ máx(a₂/2; lado/2; d_f/2 + 6,4) = máx({_mm(a2 / 2)}; {_mm(lado / 2)}; "
            f"{_mm(d_f / 2 + CHAPA_ALEM_DO_FURO)}): a₂ = 2·a₁ em todas as linhas da Tabela 18, a "
            "arruela inteira na placa e ¼ in de chapa além do furo (AISC, FAQ 7.1.7)",
        ),
        (
            "Chumbador à face do bloco a₃",
            f"{_mm(a3)} mm",
            f"a₃ ≥ {_mm(k_c)}·d_b = {_mm(k_c * d)} mm ({rotulo_k}, ACI 318-19 17.9.2)",
        ),
        (
            "Argamassa e_n",
            f"{_mm(e_n)} mm",
            "informada"
            if e.e_n_mm
            else f"porca de nivelamento ({_mm(altura)}) + arruela ({_mm(t_a)}) + "
            f"{_mm(FOLGA_DA_ARGAMASSA)} mm de argamassa sob a arruela",
        ),
        (
            "Projeção acima do concreto h₂",
            f"{_mm(h2)} mm",
            f"h₂ ≥ e_n + t_p + t_a + porca + {FIOS_ALEM_DA_PORCA} fios = {_mm(e_n)} + "
            f"{_mm(e.t_placa_mm)} + {_mm(t_a)} + {_mm(altura)} + {_mm(fios)}",
        ),
        (
            "Rosca de cima r₁ e de baixo r₂",
            f"r₁ = {_mm(r1)} mm, r₂ = {_mm(r2)} mm",
            f"r₁ = h₂ + {_mm(ROSCA_DENTRO_DO_CONCRETO)} (assim em todas as linhas da Tabela 18); "
            f"r₂ ≥ máx({_mm(R2_MINIMO)}; porca + {FIOS_ALEM_DA_PORCA} fios), {_mm(R2_MINIMO)} mm é "
            "o menor da Tabela 18",
        ),
        ("Embutimento h_ef", f"{_mm(h)} mm", conta_h),
        (
            "Barra de um chumbador",
            f"{_mm(comprimento)} mm, {_n(massa, 2)} kg",
            "h_ef + h₂"
            + {ANCORAGEM_PORCA: " + porca e fios da ponta", ANCORAGEM_GANCHO: " + gancho e_h"}.get(
                e.ancoragem, ""
            )
            + f"; massa = A_b·L·{_mm(DENSIDADE_ACO)} kg/m³",
        ),
        (
            "Concreto do bloco",
            f"f_ck ≥ {_mm(FCK_MIN_NBR_6118)} MPa",
            "NBR 6118, Tabela 7.1: concreto armado na classe de agressividade I (II pede 25, III "
            "30 e IV 40 MPa)",
        ),
    )
    return MedidasPorFormula(rosca, linha, s, altura, comprimento, massa, contas)


def disposicoes(e: EntradaBase) -> LinhaTabela18:
    """A linha da Tabela 18 do chumbador ou, por fórmula, as medidas calculadas (h_ef provisório)."""
    if e.por_formula:
        return medidas_por_formula(e).linha
    return TABELA_18[e.chumbador]


def nome_do_chumbador(e: EntradaBase) -> str:
    """'1"' na Tabela 18; por fórmula, o nome da rosca ('M30', '2 1/2"', '30 mm')."""
    return rosca_do_chumbador(e).nome if e.por_formula else e.chumbador


def ancoragem_verificada(e: EntradaBase) -> bool:
    """A ancoragem no concreto vai pela ACI 318-19: pedida, fora do reto com porca ou por fórmula."""
    return (
        e.verificar_concreto
        or e.ancoragem != ANCORAGEM_PORCA
        or e.por_formula
        or e.tipo not in TIPOS_DA_NORMA
        or not ACOS_CHUMBADOR[e.aco_chumbador].equivalente_a36
        or forma_do_perfil(e.perfil) == FORMA_U
        or e.cortante
        in (
            *CORTANTE_PELOS_CHUMBADORES,
            CORTANTE_AUTO,
        )  # fora da 6.7: a cortante vai toda pela ACI 318-19
    )


def area_resistente(e: EntradaBase, tab: LinhaTabela18) -> float:
    """A_se da rosca do chumbador (mm²): a da rosca por fórmula ou a UNC do diâmetro da Tabela 18."""
    if e.por_formula:
        return rosca_do_chumbador(e).area_resistente
    rosca = ROSCAS.get(tab.polegada)
    return rosca.area_resistente if rosca is not None else 0.75 * math.pi * tab.d_b**2 / 4


def passo_da_rosca(e: EntradaBase, tab: LinhaTabela18) -> float:
    if e.por_formula:
        return rosca_do_chumbador(e).passo
    rosca = ROSCAS.get(tab.polegada)
    return rosca.passo if rosca is not None else passo_iso_mais_perto(tab.d_b)


def f_uta(aco: AcoChumbador) -> float:
    """f_uta da ACI 318-19 17.6.1.2: mín(f_u; 1,9·f_y; 862 MPa)."""
    return min(aco.f_u, 1.9 * aco.f_y, FU_TETO_ACI)


def modulo_do_concreto(fck: float) -> float:
    """E_cs (MPa) da NBR 6118:2014 8.2.8: α_i·5600·√f_ck, α_i = 0,8 + 0,2·f_ck/80 ≤ 1 (granito)."""
    return min(0.8 + 0.2 * fck / 80, 1.0) * 5600 * math.sqrt(fck)


def _validar(e: EntradaBase) -> None:
    if (
        e.tipo not in TIPOS
        or e.cortante not in CORTANTES
        or e.combinacao not in sd.COMBINACOES
        or e.ancoragem not in ANCORAGENS
        or e.distribuicao not in DISTRIBUICOES
    ):
        raise BaseInvalida(
            "Escolha a disposição, a ancoragem, a combinação e o dispositivo da lista."
        )
    if e.modo_bloco not in ("verificacao", "pre_dimensionamento") or e.categoria_aci not in (
        0,
        1,
        2,
        3,
    ):
        raise BaseInvalida("Modo do bloco ou categoria da ancoragem inválida.")
    for dados in (e, *e.casos):
        if any(isinstance(v, float) and not math.isfinite(v) for v in vars(dados).values()):
            raise BaseInvalida("Os valores informados devem ser finitos.")
    if (
        min(
            e.tau_cr_MPa,
            e.tau_uncr_MPa,
            e.n_sustentada_kN or 0,
            e.folga_servico_mm or 0,
            e.s_min_produto_mm,
            e.c_min_produto_mm,
            e.h_min_produto_mm,
            e.graute_rd_MPa,
            e.chapa_ponta_esp_mm,
        )
        < 0
    ):
        raise BaseInvalida("Resistências, distâncias e tração sustentada devem ser não negativas.")
    if e.n_chumbadores < 2:
        raise BaseInvalida("Número de chumbadores incompatível com a disposição.")
    if e.aco_chumbador not in ACOS_CHUMBADOR:
        raise BaseInvalida(f"Aço do chumbador desconhecido: {e.aco_chumbador!r}.")
    if e.por_formula:
        if e.chumbador != CHUMBADOR_LIVRE and e.chumbador not in ROSCAS:
            raise BaseInvalida(f"Diâmetro de chumbador desconhecido: {e.chumbador!r}.")
        if e.chumbador == CHUMBADOR_LIVRE and not 6.0 <= e.d_b_mm <= 150.0:
            raise BaseInvalida("Informe o diâmetro do chumbador entre 6 e 150 mm.")
        if e.passo_mm < 0 or e.d_f_mm < 0:
            raise BaseInvalida("O passo da rosca e o furo na placa não podem ser negativos.")
        d_b = rosca_do_chumbador(e).d_b
        if e.passo_mm and not 0.05 * d_b <= e.passo_mm <= 0.25 * d_b:
            raise BaseInvalida(
                f"Passo da rosca fora do usual para Ø {_mm(d_b)} mm: entre 5 % e 25 % do diâmetro."
            )
        if e.d_f_mm and e.d_f_mm <= d_b:
            raise BaseInvalida("O furo na placa precisa ser maior que o diâmetro do chumbador.")
    elif e.chumbador not in TABELA_18:
        raise BaseInvalida(f"Chumbador fora da Tabela 18: {e.chumbador!r}.")
    if e.aco_placa not in ACOS_DA_PLACA:
        raise BaseInvalida(f"Aço da placa desconhecido: {e.aco_placa!r}.")
    if min(e.t_placa_mm, e.fck_MPa, e.mu) <= 0:
        raise BaseInvalida(
            "Espessura da placa, f_ck e coeficiente de atrito precisam ser positivos."
        )
    medidas = (
        e.a1_mm, e.a1_x_mm, e.a2_mm, e.bloco_x_mm, e.bloco_y_mm, e.e_n_mm, e.t_arruela_mm,
        e.lx_mm, e.ly_mm,
    )  # fmt: skip
    if min(*medidas, e.e_h_mm, e.chapa_na_ponta_mm, e.h_ef_mm, e.n_rd_fabricante_kN) < 0:
        raise BaseInvalida("Medidas da base não podem ser negativas.")
    if e.v_sd_kN < 0:
        raise BaseInvalida("Informe a cortante de cálculo em valor absoluto (V_Sd ≥ 0).")
    if not e.bloco_x_mm and e.desloc_x_mm or not e.bloco_y_mm and e.desloc_y_mm:
        raise BaseInvalida("Informe a dimensão real do bloco na direção do deslocamento.")
    if e.cortante == CORTANTE_PLACA and min(e.b_v_mm, e.b_h_mm, e.t_pv_mm) <= 0:
        raise BaseInvalida("Placa de cisalhamento: altura, largura e espessura positivas.")
    if e.aco_pilar not in ACOS:
        raise BaseInvalida(f"Aço do pilar desconhecido: {e.aco_pilar!r}.")
    if e.eletrodo not in sd.ELETRODOS:
        raise BaseInvalida(f"Eletrodo desconhecido: {e.eletrodo!r}.")
    pernas = (e.perna_pilar_mm, e.perna_cisalhamento_mm, e.perna_arruela_mm, e.bloco_z_mm)
    if min(pernas) < 0:
        raise BaseInvalida("As pernas das soldas e a altura do bloco não podem ser negativas.")
    nomes = [c.nome for c in e.casos]
    if any(not nome for nome in nomes):
        raise BaseInvalida("Dê um nome a cada combinação da tabela.")
    if len(set(nomes)) != len(nomes):
        raise BaseInvalida("Há combinações com o mesmo nome: use um nome para cada.")
    if any(c.v_sd_kN < 0 for c in e.casos):
        raise BaseInvalida("Informe a cortante de cada combinação em valor absoluto (V_Sd ≥ 0).")


def geometria(e: EntradaBase) -> Geometria:
    """As grandezas de 6.7.2.1 e a posição dos chumbadores (Figura 21)."""
    try:
        perfil = sc.obter_perfil(e.perfil)
    except (KeyError, sc.ErroDeCatalogo):
        raise BaseInvalida(f"Perfil desconhecido: {e.perfil!r}.") from None
    if perfil.familia not in FAMILIAS_I + FAMILIAS_U:
        raise BaseInvalida(
            "A Subseção 6.7 trata de pilares de perfil I ou H (6.7.1.1); o programa estende o "
            "método ao perfil U. Escolha um W, HP, I ou U do catálogo."
        )
    forma = FORMA_U if perfil.familia in FAMILIAS_U else FORMA_I
    if forma == FORMA_U and e.tipo not in TIPOS_DO_U:
        raise BaseInvalida(
            "Pilar U: só a tipo 1 ou a rotulada em x (chumbadores fora das mesas). A tipo 2, a "
            "rotulada em y e a de internos e externos contam com chumbadores dos dois lados da "
            "alma, e o U só tem um."
        )
    tab = disposicoes(e)
    d, b_f = perfil.altura_mm, perfil.largura_mm
    t_w, t_f = perfil.espessura_alma_mm, perfil.espessura_mesa_mm
    # Geometria física: dorso em −y, independente do sinal dos esforços.
    y_dorso = -centroide_do_u(d, b_f, t_w, t_f) if forma == FORMA_U else 0.0
    a1 = e.a1_mm or tab.a1
    a2 = e.a2_mm or tab.a2
    a1_x = (e.a1_x_mm or tab.a1) if e.tipo == TIPO_2 else a1  # nota f da Tabela 18
    n_b = e.n_chumbadores
    lx = d + 4 * a1_x  # a₁ do furo à borda e a₁ do furo à mesa (tipo 1) ou 2·a₁ até a mesa
    if e.tipo in TIPOS_DA_NORMA:
        ly = (0.5 * n_b - 1) * a2 + 2 * a1
    elif e.tipo == TIPO_ROTULADA_X:  # uma fileira no eixo x: a placa cobre o perfil (+ 12,5 mm)
        if forma == FORMA_U:
            meia = max(abs(y_dorso), b_f - abs(y_dorso))
        else:
            meia = b_f / 2
        ly = max(2 * a1, 2 * meia + 25.0)
    else:  # duas fileiras em y, a₂ entre elas
        ly = a2 + 2 * a1
    if e.lx_mm:
        if e.lx_mm < lx - 1e-6:
            raise BaseInvalida(
                f"A placa em ℓx precisa de ao menos {lx:.0f} mm com este perfil, a₁ e chumbador "
                "(d + 4·a₁): aumente ℓx ou deixe 0."
            )
        lx = e.lx_mm
    if e.ly_mm:
        if e.ly_mm < ly - 1e-6:
            raise BaseInvalida(
                f"A placa em ℓy precisa de ao menos {ly:.0f} mm com estes a₁ e a₂: aumente ℓy ou "
                "deixe 0."
            )
        ly = e.ly_mm
    l0: float | None = {
        TIPO_1: None,
        TIPO_2: (0.5 * n_b - 1) * a2 + 1.75 * (a2 - t_w),
        TIPO_ROTULADA: 1.75 * (a2 - t_w),  # um chumbador de cada lado da alma
        TIPO_ROTULADA_X: None,  # fora das mesas
        TIPO_INTERNOS_E_EXTERNOS: a2 + 1.75 * (a2 - t_w),  # dois de cada lado da alma
    }[e.tipo]
    a = {
        TIPO_1: lx / 2 - a1,
        TIPO_2: a2 / 2,
        TIPO_ROTULADA: 0.0,
        TIPO_ROTULADA_X: lx / 2 - a1,
        TIPO_INTERNOS_E_EXTERNOS: lx / 2 - a1,
    }[e.tipo]
    m = (lx - 0.95 * d) / 2
    if forma == FORMA_U:  # o maior dos dois balanços: além do dorso e além de 0,80·b_f
        x_barra = abs(y_dorso)
        n = max(ly / 2 - x_barra, ly / 2 - (0.80 * b_f - x_barra))
        n0 = math.sqrt(d * 2 * b_f) / 4  # a I equivalente, de mesa 2·b_f
    else:
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
    elif e.tipo == TIPO_ROTULADA_X:  # um de cada lado, no eixo x (na linha da alma)
        ys = [0.0]
        linhas_x = [-a, a]
    else:
        ys = [-a2 / 2, a2 / 2]
        linhas_x = [0.0] if e.tipo == TIPO_ROTULADA else [-a, -a2 / 2, a2 / 2, a]
    posicoes = tuple((x, y) for x in linhas_x for y in ys)
    return Geometria(
        d, b_f, t_w, t_f, a1, a2, lx, ly, l0, a, m, n, n0, exc,
        e.e_n_mm or tab.e_n, e.t_arruela_mm or tab.t_arruela, posicoes, a1_x, forma, y_dorso,
    )  # fmt: skip


def contorno_do_perfil(g: Geometria) -> list[tuple[float, float]]:
    """O contorno do pilar em planta (mm, do centro da placa): a I com as mesas paralelas a y, ou
    o U com o dorso da alma em y = y_dorso e as mesas abertas para o lado do centro."""
    d, bf, tf, tw = g.d, g.b_f, g.t_f, g.t_w
    if g.e_u:
        y0, s = g.y_dorso, g.abertura
        y_alma, y_ponta = y0 + s * tw, y0 + s * bf
        return [
            (-d / 2, y0), (d / 2, y0), (d / 2, y_ponta), (d / 2 - tf, y_ponta),
            (d / 2 - tf, y_alma), (-d / 2 + tf, y_alma), (-d / 2 + tf, y_ponta), (-d / 2, y_ponta),
        ]  # fmt: skip
    return [
        (-d / 2, -bf / 2), (-d / 2 + tf, -bf / 2), (-d / 2 + tf, -tw / 2), (d / 2 - tf, -tw / 2),
        (d / 2 - tf, -bf / 2), (d / 2, -bf / 2), (d / 2, bf / 2), (d / 2 - tf, bf / 2),
        (d / 2 - tf, tw / 2), (-d / 2 + tf, tw / 2), (-d / 2 + tf, bf / 2), (-d / 2, bf / 2),
    ]  # fmt: skip


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
    t45, texto45 = espessura_a_45_graus(g, forcas, fy_d)
    if t45 > 0:
        espessura = max(espessura, t45)
        partes.append(texto45)
    return espessura, "; ".join(partes) or "sem chumbador tracionado"


def espessura_a_45_graus(g: Geometria, forcas: tuple[float, ...], fy_d: float) -> tuple[float, str]:
    """t_p de cada chumbador externo tracionado, com a largura efetiva aberta a 45°.

    A placa trabalha em balanço da linha do chumbador até a face da mesa (m = |x| − d/2, a seção
    crítica) numa largura b_eff aberta a 45° a partir do chumbador — de cada lado, o menor entre
    m, a distância à borda da placa e a metade do espaçamento ao vizinho da mesma linha (sem
    sobrepor) —; t = √(4·F_t·m/(b_eff·f_y/γ_a1)). Complementa a fórmula da 6.7 (a linha inteira
    na largura ℓy): quando os chumbadores são poucos numa placa larga, a 45° governa.
    """
    dados = dados_a_45_graus(g, forcas, fy_d)
    if dados is None:
        return 0.0, ""
    t, f, m, b_eff, x, y = dados
    return t, (
        f"a 45° no chumbador mais exigido (x; y) = ({_n(x, 0)}; {_n(y, 0)}) mm: m = |x| − d/2 "
        f"= {_n(m, 1)} mm até a face da mesa, b_eff = {_n(b_eff, 1)} mm (45° de cada lado, "
        f"limitada pela borda da placa e pela metade do espaçamento), F_t = "
        f"{_n(f / 1e3, 2)} kN: t = √(4·F_t·m/(b_eff·f_y/γ_a1)) = {_n(t, 1)} mm"
    )


@dataclass(frozen=True)
class AberturaA45:
    """A placa de um chumbador externo tracionado: balanço m até a face da mesa e a largura
    aberta a 45° de cada lado (limitada pela borda e pela metade do espaçamento), em mm e N."""

    x: float
    y: float
    f: float
    m: float
    lado_mais: float  # para y crescente
    lado_menos: float

    @property
    def b_eff(self) -> float:
        return max(self.lado_mais, 0.0) + max(self.lado_menos, 0.0)


def aberturas_a_45_graus(g: Geometria, forcas: tuple[float, ...]) -> list[AberturaA45]:
    """A abertura a 45° de cada chumbador externo tracionado (o desenho e a conta usam esta)."""
    saida: list[AberturaA45] = []
    for (x, y), f in zip(g.posicoes, forcas, strict=True):
        if f <= 0 or abs(x) <= g.d / 2 + 1e-9:
            continue
        m = abs(x) - g.d / 2
        na_linha = [y2 for x2, y2 in g.posicoes if abs(x2 - x) < 1e-6 and abs(y2 - y) > 1e-6]
        acima = [y2 - y for y2 in na_linha if y2 > y]
        abaixo = [y - y2 for y2 in na_linha if y2 < y]
        lado_mais = min(m, g.ly / 2 - y, min(acima) / 2 if acima else math.inf)
        lado_menos = min(m, y + g.ly / 2, min(abaixo) / 2 if abaixo else math.inf)
        abertura = AberturaA45(x, y, f, m, lado_mais, lado_menos)
        if abertura.b_eff > 0:
            saida.append(abertura)
    return saida


def dados_a_45_graus(
    g: Geometria, forcas: tuple[float, ...], fy_d: float
) -> tuple[float, float, float, float, float, float] | None:
    """(t, F_t, m, b_eff, x, y) do chumbador externo que pede a placa mais grossa a 45°."""
    melhor: tuple[float, float, float, float, float, float] | None = None
    for a in aberturas_a_45_graus(g, forcas):
        t = math.sqrt(4 * a.f * a.m / (a.b_eff * fy_d))
        if melhor is None or t > melhor[0]:
            melhor = (t, a.f, a.m, a.b_eff, a.x, a.y)
    return melhor


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


def _intervalo_na_reta(
    poligono: Sequence[Ponto], eixo: int, valor: float
) -> tuple[float, float] | None:
    """O trecho do polígono convexo sobre a reta coordenada[1 − eixo] = valor, em coordenada[eixo]."""
    outro = 1 - eixo
    pontos: list[float] = []
    for k, a in enumerate(poligono):
        b = poligono[(k + 1) % len(poligono)]
        if (a[outro] - valor) * (b[outro] - valor) <= 0 and a[outro] != b[outro]:
            t = (valor - a[outro]) / (b[outro] - a[outro])
            pontos.append(a[eixo] + t * (b[eixo] - a[eixo]))
    return (min(pontos), max(pontos)) if pontos else None


def espessura_pela_zona(
    g: Geometria,
    zona: tuple[Ponto, ...],
    sigma: float,
    fy_d: float,
    plano: tuple[float, float, float] | None = None,
) -> tuple[float, str]:
    """Máximo do momento integrado em faixas unitárias independentes.

    Entre vértices e cruzamentos do polígono com o engaste os limites da
    integral são afins. Para pressão afim, q é um polinômio de grau até três.
    Avalia os extremos de cada intervalo e as raízes internas de dq/dy.
    """
    if not zona:
        return 0.0, "sem zona comprimida"
    w0, ax, ay = plano or (sigma, 0.0, 0.0)
    linhas = (
        (0, 0.475 * g.d, 1),
        (0, -0.475 * g.d, -1),
        (1, g.engaste_y[1], 1),
        (1, g.engaste_y[0], -1),
    )
    pior, descricao = 0.0, "a zona comprimida não passa das linhas de engaste"
    for eixo, linha, sinal in linhas:
        outro = 1 - eixo
        cortes = {p[outro] for p in zona}
        for p, r in zip(zona, zona[1:] + zona[:1], strict=True):
            if (p[eixo] - linha) * (r[eixo] - linha) < 0:
                cortes.add(
                    p[outro] + (r[outro] - p[outro]) * (linha - p[eixo]) / (r[eixo] - p[eixo])
                )
        ordenados = sorted(cortes)

        def momento(v, eixo=eixo, sinal=sinal, linha=linha):
            limites = _intervalo_na_reta(zona, eixo, v)
            if limites is None:
                return 0.0
            a, b = sorted(max(0.0, sinal * (u - linha)) for u in limites)
            grad, transv = (ax, ay) if eixo == 0 else (ay, ax)
            return max(
                0.0,
                (w0 + grad * linha + transv * v) * (b * b - a * a) / 2
                + sinal * grad * (b**3 - a**3) / 3,
            )

        for ini, fim in zip(ordenados, ordenados[1:], strict=False):
            h = (fim - ini) / 3
            q0, q1, q2, q3 = [momento(v) for v in (ini, ini + h, ini + 2 * h, fim)]
            d1, d2, d3 = q1 - q0, q2 - 2 * q1 + q0, q3 - 3 * q2 + 3 * q1 - q0
            a, b, c = d3 / 6, (d2 - d3) / 2, d1 - d2 / 2 + d3 / 3
            candidatos = [(q0, ini), (q3, fim)]
            disc = b * b - 3 * a * c
            if abs(a) > 1e-12 * max(1, abs(b), abs(c)) and disc >= 0:
                raizes = [(-b + s * math.sqrt(disc)) / (3 * a) for s in (-1, 1)]
            else:
                raizes = [-c / (2 * b)] if b else []
            candidatos.extend((momento(ini + h * u), ini + h * u) for u in raizes if 0 < u < 3)
            q, v = max(candidatos)
            if q > pior:
                pior = q
                descricao = (
                    f"Faixa unitária em {'y' if eixo == 0 else 'x'} = {_n(v)} mm, "
                    f"engaste em {_n(linha)} mm. q = ∫p·u du = {_n(q / 1000)} kN·m/m."
                )
    return math.sqrt(4 * pior / fy_d), descricao


def corte_de_pressao(r: ResultadoBase) -> tuple[float, float, float, float, float] | None:
    """Corte x na ordenada do centro de pressão, com a pressão nas duas pontas."""
    if not r.zona_comprimida or r.centro_pressao is None:
        return None
    y = r.centro_pressao[1]
    trecho = _intervalo_na_reta(r.zona_comprimida, 0, y)
    if trecho is None:
        return None
    w, ax, ay = r.plano_pressao
    a, b = trecho
    return a, b, max(0, w + ax * a + ay * y), max(0, w + ax * b + ay * y), y


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


@dataclass(frozen=True)
class DistribuicaoElastica:
    """A placa rígida com pressão linear (sem tração no concreto) e chumbadores elásticos.

    O deslocamento da placa contra o concreto é um plano, w = σ₀ + a_x·x + a_y·y (em MPa: a
    pressão onde ele é positivo). Onde w < 0 a placa levanta: cada chumbador ali estica e puxa
    com F_i = n·A_se·(−w_i), n = E_s/E_cs — a compatibilidade do método elástico clássico (o
    chumbador como armadura de uma seção de concreto armado).
    """

    caso: str
    zona: tuple[Ponto, ...]
    plano: tuple[float, float, float]
    sigma_max: float  # MPa
    compressao: float  # N: a resultante da pressão de contato
    forcas: tuple[float, ...]  # N, uma por chumbador
    equilibrio: bool
    razao_modular: float
    rigidez: float  # n·A_se (mm²)


def _momentos_do_poligono(p: list[Ponto]) -> tuple[float, float, float, float, float, float]:
    """(A, ∫x, ∫y, ∫x², ∫x·y, ∫y²) de um polígono simples (anti-horário), a partir da origem."""
    a = sx = sy = ixx = ixy = iyy = 0.0
    for i, (x0, y0) in enumerate(p):
        x1, y1 = p[(i + 1) % len(p)]
        c = x0 * y1 - x1 * y0
        a += c
        sx += (x0 + x1) * c
        sy += (y0 + y1) * c
        ixx += (x0 * x0 + x0 * x1 + x1 * x1) * c
        iyy += (y0 * y0 + y0 * y1 + y1 * y1) * c
        ixy += (x0 * y1 + 2 * x0 * y0 + 2 * x1 * y1 + x1 * y0) * c
    return a / 2, sx / 6, sy / 6, ixx / 12, ixy / 24, iyy / 12


def _zona_do_plano(lx: float, ly: float, q: tuple[float, float, float]) -> list[Ponto]:
    w0, a_x, a_y = q
    if abs(a_x) < 1e-300 and abs(a_y) < 1e-300:
        return _parte_da_placa(lx, ly, 1.0, 0.0, -lx) if w0 > 0 else []
    return _parte_da_placa(lx, ly, a_x, a_y, -w0)


def _resolver_3x3(h: list[list[float]], b: list[float]) -> list[float] | None:
    """h·d = b por eliminação com pivô; None se singular."""
    m = [linha[:] + [b[i]] for i, linha in enumerate(h)]
    for col in range(3):
        piv = max(range(col, 3), key=lambda r: abs(m[r][col]))
        escala = max(abs(m[r][c]) for r in range(3) for c in range(3)) or 1.0
        if abs(m[piv][col]) <= 1e-14 * escala:
            return None
        m[col], m[piv] = m[piv], m[col]
        for r in range(3):
            if r != col:
                k = m[r][col] / m[col][col]
                for c in range(col, 4):
                    m[r][c] -= k * m[col][c]
    return [m[i][3] / m[i][i] for i in range(3)]


@functools.lru_cache(maxsize=256)
def distribuicao_elastica(
    g: Geometria, axial: float, mx: float, my: float, fck: float, area_se: float
) -> DistribuicaoElastica:
    """O equilíbrio elástico da placa rígida (N em N, + compressão; M em N·mm, M comprime x > 0).

    Minimiza a energia Π = ½∫w₊²·dA + ½·Σ n·A_se·w₋² − (N·σ₀ + M·a_x + M_y·a_y), convexa nos três
    parâmetros do plano: o mínimo é o equilíbrio (∫σ − ΣF = N, ∫σ·x − ΣF·x = M, ∫σ·y − ΣF·y = M_y)
    com a compatibilidade. Newton com busca na linha; as integrais no polígono são exatas.
    """
    n_mod = E_ACO / modulo_do_concreto(fck)
    rho = n_mod * area_se
    lx, ly, pos = g.lx, g.ly, g.posicoes
    carga = (axial, mx, my)

    def estado(q: tuple[float, float, float]) -> tuple[float, list[float], list[list[float]]]:
        w0, a_x, a_y = q
        zona = _zona_do_plano(lx, ly, q)
        a, sx, sy, ixx, ixy, iyy = _momentos_do_poligono(zona) if len(zona) >= 3 else (0.0,) * 6
        grad = [
            w0 * a + a_x * sx + a_y * sy,
            w0 * sx + a_x * ixx + a_y * ixy,
            w0 * sy + a_x * ixy + a_y * iyy,
        ]
        hess = [[a, sx, sy], [sx, ixx, ixy], [sy, ixy, iyy]]
        energia = 0.5 * (
            w0 * w0 * a + 2 * w0 * (a_x * sx + a_y * sy)
            + a_x * a_x * ixx + 2 * a_x * a_y * ixy + a_y * a_y * iyy
        )  # fmt: skip
        for x, y in pos:
            w = w0 + a_x * x + a_y * y
            if w < 0:
                v = (1.0, x, y)
                energia += 0.5 * rho * w * w
                for i in range(3):
                    grad[i] += rho * w * v[i]
                    for j in range(3):
                        hess[i][j] += rho * v[i] * v[j]
        energia -= sum(c * qi for c, qi in zip(carga, q, strict=True))
        grad = [gi - c for gi, c in zip(grad, carga, strict=True)]
        return energia, grad, hess

    area = lx * ly
    if axial > 0:
        q = (axial / area, 12 * mx / (ly * lx**3), 12 * my / (lx * ly**3))
    else:
        soma_x = sum(x * x for x, _ in pos)
        soma_y = sum(y * y for _, y in pos)
        q = (
            axial / (rho * len(pos)),
            mx / (rho * soma_x) if soma_x > 0 else 0.0,
            my / (rho * soma_y) if soma_y > 0 else 0.0,
        )
    escala = max(abs(axial), (mx + my) / max(lx, ly), 1.0)
    convergiu = False
    energia, grad, hess = estado(q)
    for _ in range(200):
        tamanho = [1.0, lx / 2, ly / 2]
        if max(abs(gi) / t for gi, t in zip(grad, tamanho, strict=True)) <= 1e-9 * escala:
            convergiu = True
            break
        passo = _resolver_3x3(hess, [-gi for gi in grad])
        if passo is None:  # direção sem rigidez: gradiente simples
            passo = [-gi / (abs(hess[i][i]) or rho or 1.0) for i, gi in enumerate(grad)]
        t = 1.0
        while t > 1e-12:
            novo = (q[0] + t * passo[0], q[1] + t * passo[1], q[2] + t * passo[2])
            e_novo, g_novo, h_novo = estado(novo)
            if e_novo <= energia + 1e-4 * t * sum(
                gi * p for gi, p in zip(grad, passo, strict=True)
            ):
                break
            t /= 2
        else:
            break
        q, energia, grad, hess = novo, e_novo, g_novo, h_novo
        if max(abs(v) for v in q) > 1e12:  # sem equilíbrio: a energia cai sem limite
            break
    # o equilíbrio vale pelos resíduos (∫σ − ΣF − N, ...), não pelo critério de parada do Newton:
    # perto da solução a busca na linha para por arredondamento com o equilíbrio já satisfeito
    _, residuo, _ = estado(q)
    folga = 1e-6 * escala
    convergiu = convergiu or (
        max(abs(v) for v in q) < 1e12
        and abs(residuo[0]) <= folga
        and abs(residuo[1]) <= folga * lx / 2
        and abs(residuo[2]) <= folga * ly / 2
    )
    zona = _zona_do_plano(lx, ly, q)
    w0, a_x, a_y = q
    if len(zona) >= 3:
        a, sx, sy, *_ = _momentos_do_poligono(zona)
        compressao = w0 * a + a_x * sx + a_y * sy
        sigma_max = max(w0 + a_x * x + a_y * y for x, y in zona)
    else:
        zona, sigma_max, compressao = [], 0.0, 0.0
    forcas = tuple(max(-rho * (w0 + a_x * x + a_y * y), 0.0) for x, y in pos)
    tracao = max(forcas) > 1e-6 * max(abs(axial), 1.0)
    if axial > 0 or (axial == 0 and compressao > 0):
        caso = ("C1" if mx == my == 0 else "C2") if not tracao else "C3"
    elif axial < 0:
        caso = ("T1" if mx == my == 0 else "T2") if compressao <= 1e-6 * abs(axial) else "T3"
    else:
        caso = "C1"
    if not tracao:
        forcas = tuple(0.0 for _ in pos)
    return DistribuicaoElastica(
        caso, tuple(zona), q, sigma_max, max(compressao, 0.0), forcas, convergiu, n_mod, rho
    )


def balanco_sob_pressao(g: Geometria, l_c: float, caso: str, n0_lam: float) -> float:
    """ℓ_max da placa com σ_c,Rd só no trecho ℓ_c (C3 e T3).

    Com ℓ_c ≥ balanço, o balanço inteiro; com ℓ_c menor, p = √(ℓ_c·(2·balanço − ℓ_c)) — a 6.7 faz
    isso no m, e o programa faz o mesmo no n (AISC Design Guide 1, 3.3: a fórmula de Y < m vale
    também para n). Com o n inteiro sob σ_c,Rd, uma faixa comprimida de 1 mm exigiria a mesma
    placa que a base toda comprimida: t_p não cairia com a carga.
    """

    def reduzido(balanco: float) -> float:
        if l_c >= balanco:
            return balanco
        return math.sqrt(max(l_c * (2 * balanco - l_c), 0.0))

    l_max = max(reduzido(g.m), reduzido(g.n))
    if caso in ("C2", "C3") and l_c >= g.m:
        l_max = max(l_max, n0_lam)
    return l_max


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


def _equacoes_da_base(
    e: EntradaBase,
    g: Geometria,
    contas: Mapping[str, Any],
    *,
    sigma_rd: float,
    razao: float,
    gc: float,
    fy: float,
    gama_a1: float,
    gama_a2: float,
    f_t: float,
    f_ub: float,
    a_se: float,
    axial: float,
    forcas: tuple[float, ...],
    d_min: float | None,
) -> dict[str, tuple[str, ...]]:
    """As contas das verificações principais em notação de equação (memorial em Word)."""
    saida: dict[str, tuple[str, ...]] = {}
    fy_d = fy / gama_a1
    rd = (
        "σ_c,Rd = 0,85·f_ck/γ_c·√(A_2/A_1) ≤ 1,7·f_ck/γ_c",
        f"σ_c,Rd = mín(0,85 × {_n(e.fck_MPa, 1)}/{_n(gc, 1)} × √({_n(razao, 2)}); "
        f"1,7 × {_n(e.fck_MPa, 1)}/{_n(gc, 1)}) = {_n(sigma_rd, 2)} MPa",
    )
    saida["Concreto: pressão de contato"] = rd
    saida["Concreto: pressão de contato σ_c,Sd ≤ σ_c,Rd"] = rd
    if "compressao" in contas:
        l_max, sigma_sd, l_c = contas["compressao"]
        saida["Concreto: pressão de contato σ_c,Sd ≤ σ_c,Rd"] = (
            *rd,
            "σ_c,Sd = N_Sd/(ℓ_c·ℓ_y)",
            f"σ_c,Sd = {_n(axial, 0)}/({_n(l_c, 1)} × {_n(g.ly, 0)}) = {_n(sigma_sd, 2)} MPa ≤ "
            f"σ_c,Rd = {_n(sigma_rd, 2)} MPa",
        )
    placa: list[str] = []
    if "compressao" in contas:
        l_max, sigma_sd, _ = contas["compressao"]
        t1 = l_max * math.sqrt(2 * sigma_sd / fy_d)
        placa += [
            "t_p,min = ℓ_máx·√(2·σ_c,Sd/(f_y/γ_a1))",
            f"t_p,min = {_n(l_max, 1)} × √(2 × {_n(sigma_sd, 3)}/({_n(fy, 0)}/{_n(gama_a1, 2)})) "
            f"= {_n(t1, 2)} mm",
        ]
    if "pressao_rd" in contas:
        l_max, l_c = contas["pressao_rd"]
        t1 = l_max * math.sqrt(2 * sigma_rd / fy_d)
        placa += [
            "t_p,min1 = ℓ_máx·√(2·σ_c,Rd/(f_y/γ_a1))",
            f"t_p,min1 = {_n(l_max, 1)} × √(2 × {_n(sigma_rd, 2)}/({_n(fy, 0)}/{_n(gama_a1, 2)})) "
            f"= {_n(t1, 2)} mm",
        ]
    if "zona" in contas:
        placa.extend(contas["zona"])
    if "linha" in contas and g.m > g.a1:
        f_linha = contas["linha"]
        n_b = e.n_chumbadores
        t2 = math.sqrt(2 * n_b * f_linha * (g.m - g.a1) / (g.ly * fy_d))
        placa += [
            "t_p,min2 = √(2·n_b·F_t,Sd·(m − a_1)/(ℓ_y·f_y/γ_a1))",
            f"t_p,min2 = √(2 × {n_b} × {_n(f_linha, 0)} × {_n(g.m - g.a1, 1)}/({_n(g.ly, 0)} × "
            f"{_n(fy, 0)}/{_n(gama_a1, 2)})) = {_n(t2, 2)} mm",
        ]
    dados = dados_a_45_graus(g, forcas, fy_d)
    if dados is not None:
        t45, f45, m45, b45, _, _ = dados
        placa += [
            "t_p,45 = √(4·F_t·m/(b_eff·f_y/γ_a1))",
            f"t_p,45 = √(4 × {_n(f45, 0)} × {_n(m45, 1)}/({_n(b45, 1)} × {_n(fy, 0)}/"
            f"{_n(gama_a1, 2)})) = {_n(t45, 2)} mm",
        ]
    if placa:
        placa.append(
            f"t_p,min = {_n(contas['t_min'], 2)} mm. Chapa adotada t_p = {_n(e.t_placa_mm, 2)} mm"
        )
        saida["Placa de base: espessura t_p ≥ t_p,min"] = tuple(placa)
    if d_min is not None and f_t > 0:
        saida["Chumbador: diâmetro d_b ≥ d_b,min"] = (
            "d_b,min = √(4·F_t,Sd/(0,75·π·f_ub/γ_a2))",
            f"d_b,min = √(4 × {_n(f_t, 0)}/(0,75 × π × {_n(f_ub, 0)}/{_n(gama_a2, 2)})) = "
            f"{_n(d_min, 2)} mm",
        )
    if "cortante_aco" in contas:
        v_i, n_eng, f_ut = contas["cortante_aco"]
        aco_v = (PHI_ACO_CORTANTE if e.aco_ductil else 0.60) * 0.6 * a_se * f_ut * FATOR_ARGAMASSA
        saida["Chumbador: aço à cortante (ACI 318-19)"] = (
            "V_ua,i = |V/n + M_z·(−y_i, x_i)/Σr²|"
            if e.mz_kNm and e.cortante == CORTANTE_ARRUELAS
            else "V_ua,i = V_Sd/n_eng",
            f"φ·V_sa = {_n(0.65 if e.aco_ductil else 0.60)}·0,6·A_se·f_uta·0,80",
            f"φ·V_sa = {_n(0.65 if e.aco_ductil else 0.60)} × 0,6 × {_n(a_se, 0)} × {_n(f_ut, 0)} × 0,80 = {_n(aco_v / 1e3, 2)} kN "
            f"(solicitação V_ua,i = {_n(v_i / 1e3, 2)} kN)",
        )
    if "flexao" in contas:
        fl = contas["flexao"]
        saida[LINHA_FLEXAO_NA_ARGAMASSA] = (
            "M = V_i·(e_n + t_p/2 + Δ)",
            f"M = {_n(fl.v_i, 0)} × {_n(fl.braco, 1)} = {_n(fl.momento, 0)} N·mm",
            "σ = M/(1,5·W) + F_t/A_se ≤ f_y/γ_a1",
            f"σ = {_n(fl.momento, 0)}/(1,5 × {_n(fl.w, 0)}) + {_n(fl.f_t, 0)}/{_n(fl.a_se, 0)} = "
            f"{_n(fl.sigma, 1)} MPa (limite {_n(fl.limite, 1)} MPa)",
        )
    return saida


def _comprimento_da_barra(e: EntradaBase, g: Geometria, tab: LinhaTabela18) -> str:
    """L = h_ef + h₂ + ponta, com h₂ conferido com e_n + t_p + arruela + porca + 3 fios (mm)."""
    passo = passo_da_rosca(e, tab)
    h_ef = embutimento(e, tab)
    acima_minimo = g.e_n + e.t_placa_mm + g.t_arruela + tab.d_b + FIOS_ALEM_DA_PORCA * passo
    h2 = max(tab.h2, acima_minimo)
    ponta = {
        ANCORAGEM_PORCA: e.chapa_ponta_esp_mm + tab.d_b + FIOS_ALEM_DA_PORCA * passo,
        ANCORAGEM_GANCHO: e.e_h_mm or 4.5 * tab.d_b,
    }.get(e.ancoragem, 0.0)
    total = h_ef + h2 + ponta
    massa = math.pi * tab.d_b**2 / 4 * total * 1e-9 * DENSIDADE_ACO
    nome_ponta = {
        ANCORAGEM_PORCA: ("chapa de ponta + " if e.chapa_ponta_esp_mm else "")
        + "porca da ponta + 3 fios",
        ANCORAGEM_GANCHO: "gancho e_h",
    }.get(e.ancoragem, "")
    return (
        f"L = h_ef + h₂{' + ' + nome_ponta if nome_ponta else ''} = {_n(h_ef, 0)} + {_n(h2, 0)}"
        + (f" + {_n(ponta, 0)}" if ponta else "")
        + f" = {_n(total, 0)} mm, {_n(massa, 2)} kg; acima do concreto h₂ ≥ e_n + t_p + arruela + "
        f"porca + 3 fios = {_n(acima_minimo, 0)} mm"
    )


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
    if e.por_formula:
        return (
            f"reto, {ponta} na ponta (por fórmula): h_ef = {_n(embutimento(e, tab), 0)} mm, "
            f"h₂ = {_n(tab.h2, 0)} mm, r₁ = {_n(tab.r1, 0)} mm, r₂ = {_n(tab.r2, 0)} mm"
        )
    return (
        f"reto, {ponta} na ponta (Tabela 18): h₁ = {_n(tab.h1, 0)} mm, h₂ = {_n(tab.h2, 0)} mm, "
        f"r₁ = {_n(tab.r1, 0)} mm, r₂ = {_n(tab.r2, 0)} mm"
    )


def embutimento(e: EntradaBase, tab: LinhaTabela18) -> float:
    """h_ef (mm): o informado ou, sem ele, h₁ da Tabela 18 (concretado) ou 12·d_b (pós-instalado).

    Por fórmula, o h₁ das medidas calculadas (o do cone, depois que as forças são conhecidas).
    """
    if e.h_ef_mm > 0:
        return e.h_ef_mm
    if e.por_formula:
        return tab.h1
    return 12 * tab.d_b if e.ancoragem in POS_INSTALADOS else tab.h1


def bloco_minimo(e: EntradaBase, g: Geometria, tab: LinhaTabela18) -> tuple[float, float, float]:
    """(N_b ao longo de ℓx, B_b ao longo de ℓy, altura A_b) mínimos do bloco em mm (Tabela 18, nota e).

    Com a placa centrada, ℓ + 2·(a₃ − a₁) põe cada chumbador externo a a₃ da face do bloco e, no
    tipo 2, a borda da placa a a₃ − a₁ dela (nota g). A altura usa o embutimento (h₁ da tabela).
    """
    folga = max(2 * g.e_n, 2 * (tab.a3 - tab.a1))
    n_b = max(tab.n_b_min, g.lx + folga)
    if e.por_formula:  # sem a Tabela 18: a₃ da ACI 318-19 17.9.2 e a altura pelo embutimento
        return n_b, g.ly + folga, embutimento(e, tab) + 100.0
    return n_b, g.ly + folga, max(embutimento(e, tab) + 100.0, n_b)


def bloco_para_o_cone(
    e: EntradaBase, g: Geometria, tab: LinhaTabela18
) -> tuple[float, float, bool]:
    """O bloco ao longo de ℓx e de ℓy e se foi informado; sem ele, o mínimo da nota e da Tabela 18."""
    if e.bloco_x_mm > 0 and e.bloco_y_mm > 0:
        return e.bloco_x_mm, e.bloco_y_mm, True
    n_b, b_b, _ = bloco_minimo(e, g, tab)
    return e.bloco_x_mm or n_b, e.bloco_y_mm or b_b, False


def area_de_apoio_da_ponta(e: EntradaBase, tab: LinhaTabela18) -> float:
    """A_brg (mm²) da porca sextavada pesada (s = 1,5·d + 3,2 mm entre faces) ou da chapa."""
    s = 1.5 * tab.d_b + 3.2
    cabeca = e.chapa_na_ponta_mm**2 if e.chapa_na_ponta_mm > s else math.sqrt(3) / 2 * s**2
    return cabeca - math.pi * tab.d_b**2 / 4


def limites_bloco(e: EntradaBase, bx: float, by: float) -> tuple[float, float, float, float]:
    return (
        -bx / 2 - e.desloc_x_mm,
        bx / 2 - e.desloc_x_mm,
        -by / 2 - e.desloc_y_mm,
        by / 2 - e.desloc_y_mm,
    )


def phi_tracao_concreto(e: EntradaBase) -> float:
    if e.ancoragem in CONCRETADOS:
        return 0.75 if e.armadura_suplementar else PHI_CONCRETADO
    categoria = e.categoria_aci or 3
    return (0.65, 0.55, 0.45)[categoria - 1] + (0.10 if e.armadura_suplementar else 0.0)


def area_projetada(
    pontos: Iterable[Ponto], raio: float, limites: tuple[float, float, float, float]
) -> float:
    """União exata dos quadrados recortados nas faces do bloco, em mm²."""
    x0, x1, y0, y1 = limites
    retangulos = [
        (max(x0, x - raio), min(x1, x + raio), max(y0, y - raio), min(y1, y + raio))
        for x, y in pontos
    ]
    cortes = sorted({x for a, b, _, _ in retangulos for x in (a, b)})
    area = 0.0
    for a, b in zip(cortes, cortes[1:], strict=False):
        fim = y0
        for baixo, alto in sorted((c, d) for l, r, c, d in retangulos if l <= a and b <= r):
            area += (b - a) * max(0.0, alto - max(baixo, fim))
            fim = max(fim, alto)
    return area


def aderencia(
    e: EntradaBase, g: Geometria, tab: LinhaTabela18, forcas: tuple[float, ...]
) -> tuple[float, float, str] | None:
    """N_ba e N_ag nominais (N), concreto fissurado de peso normal."""
    ativos = [(p, f) for p, f in zip(g.posicoes, forcas, strict=True) if f > 0]
    if not ativos or min(e.tau_cr_MPa, e.tau_uncr_MPa) <= 0:
        return None
    limites = limites_bloco(e, *bloco_para_o_cone(e, g, tab)[:2])
    x0, x1, y0, y1 = limites
    pontos = [p for p, _ in ativos]
    c_na = 10 * tab.d_b * math.sqrt(e.tau_uncr_MPa / 7.6)
    a0 = 4 * c_na**2
    area = area_projetada(pontos, c_na, limites)
    c_min = min(min(x - x0, x1 - x, y - y0, y1 - y) for x, y in pontos)
    total = sum(f for _, f in ativos)
    ecc = [
        abs(sum(p[k] * f for p, f in ativos) / total - sum(p[k] for p in pontos) / len(pontos))
        for k in (0, 1)
    ]
    psi_ec = 1 / ((1 + ecc[0] / c_na) * (1 + ecc[1] / c_na))
    psi_ed = min(1.0, 0.7 + 0.3 * max(0.0, c_min) / c_na)
    nba = e.tau_cr_MPa * math.pi * tab.d_b * embutimento(e, tab)
    nag = nba * area / a0 * psi_ed * psi_ec
    texto = (
        f"N_ba = τ_cr·π·d_a·h_ef = {_n(nba / 1000)} kN. c_Na = {_n(c_na)} mm. "
        f"A_Na/A_Na0 = {_n(area, 1)}/{_n(a0, 1)}. ψ_ec = {_n(psi_ec, 4)}, "
        f"ψ_ed = {_n(psi_ed, 4)}, ψ_cp = λ_a = 1 (concreto fissurado de peso normal). "
        f"N_ag = {_n(nag / 1000)} kN, φ = {_n(phi_tracao_concreto(e))}."
    )
    return nba, nag, texto


@dataclass(frozen=True)
class AreaDoCone:
    """A área projetada do cone de concreto do grupo tracionado (ACI 318-19 17.6.2), em mm."""

    tracionados: tuple[tuple[float, float, float], ...]  # (x, y, F)
    bx: float
    by: float
    informado: bool
    h_ef_informado: float
    h_ef: float  # o útil (reduzido perto de 3 ou 4 bordas)
    bordas: tuple[float, float, float, float]  # c à face −x, +x, −y, +y
    retangulo: tuple[float, float, float, float]  # x0, x1, y0, y1 de A_Nc, dentro do bloco
    a_nco: float
    area_uniao: float

    @property
    def reduzido(self) -> bool:
        return self.h_ef < self.h_ef_informado - 1e-9

    @property
    def a_nc(self) -> float:
        return self.area_uniao


def area_do_cone(
    e: EntradaBase, g: Geometria, tab: LinhaTabela18, forcas: tuple[float, ...]
) -> AreaDoCone | None:
    """A área A_Nc do grupo tracionado no bloco (a conta e o desenho usam esta); None sem tração."""
    tracionados = tuple((x, y, f) for (x, y), f in zip(g.posicoes, forcas, strict=True) if f > 0)
    if not tracionados:
        return None
    bx, by, informado = bloco_para_o_cone(e, g, tab)
    xs = [x for x, _, _ in tracionados]
    ys = [y for _, y, _ in tracionados]
    limites = limites_bloco(e, bx, by)
    x0, x1, y0, y1 = limites
    bordas = (min(xs) - x0, x1 - max(xs), min(ys) - y0, y1 - max(ys))
    h_informado = h = embutimento(e, tab)
    s_max = max(max(xs) - min(xs), max(ys) - min(ys))
    proximas = [c for c in bordas if c < 1.5 * h]
    if len(proximas) >= 3:
        h = min(h, max(max(proximas) / 1.5, s_max / 3))
    retangulo = (
        max(min(xs) - 1.5 * h, x0),
        min(max(xs) + 1.5 * h, x1),
        max(min(ys) - 1.5 * h, y0),
        min(max(ys) + 1.5 * h, y1),
    )
    return AreaDoCone(
        tracionados,
        bx,
        by,
        informado,
        h_informado,
        h,
        bordas,
        retangulo,
        9 * h * h,
        area_projetada(zip(xs, ys, strict=True), 1.5 * h, limites),
    )


def cone_de_concreto(
    e: EntradaBase, g: Geometria, tab: LinhaTabela18, forcas: tuple[float, ...]
) -> tuple[float, float, str] | None:
    """(Σ F_t, φ·N_cbg, conta) do cone do grupo tracionado (ACI 318-19 17.6.2); None sem tração.

    Bloco centrado na placa; ψ_c,N = ψ_cp,N = 1,0 (concreto fissurado); h_ef reduzido pela
    17.6.2.1.2 quando o grupo fica perto de três ou mais bordas.
    """
    area = area_do_cone(e, g, tab, forcas)
    if area is None:
        return None
    tracionados = area.tracionados
    concretado = e.ancoragem in CONCRETADOS
    bx, by, informado = area.bx, area.by, area.informado
    xs = [x for x, _, _ in tracionados]
    ys = [y for _, y, _ in tracionados]
    bordas = area.bordas
    h = area.h_ef
    reducao = (
        f" (h_ef reduzido de {_n(area.h_ef_informado, 0)} mm pela 17.6.2.1.2: perto de 3 ou 4 "
        "bordas)"
        if area.reduzido
        else ""
    )
    a_nco = area.a_nco
    a_nc = area.a_nc
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
    phi = phi_tracao_concreto(e)
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
        f"com centro em ({_n(e.desloc_x_mm)}, {_n(e.desloc_y_mm)}) mm no bloco; ψ_c,N = 1,0 (fissurado)"
    )
    return total, resistente, texto


def cone_truncado(
    e: EntradaBase, g: Geometria, tab: LinhaTabela18, forcas: tuple[float, ...]
) -> str:
    """O aviso de cone cortado pela borda do bloco (1,5·h_ef > c_a,mín), ou "" sem ele."""
    tracionados = [(x, y) for (x, y), f in zip(g.posicoes, forcas, strict=True) if f > 0]
    if not tracionados:
        return ""
    bx, by, _ = bloco_para_o_cone(e, g, tab)
    xs = [x for x, _ in tracionados]
    ys = [y for _, y in tracionados]
    x0, x1, y0, y1 = limites_bloco(e, bx, by)
    bordas = [min(xs) - x0, x1 - max(xs), min(ys) - y0, y1 - max(ys)]
    h = embutimento(e, tab)
    c_min = max(min(bordas), 0.0)
    if 1.5 * h <= c_min + 1e-9:
        return ""
    proximas = [c for c in bordas if c < 1.5 * h]
    texto = (
        f"c_a,mín = {_n(c_min, 0)} mm < 1,5·h_ef = {_n(1.5 * h, 0)} mm: o cone toca a borda e "
        "perde área (A_Nc < A_Nco, ψ_ed,N < 1). "
    )
    if len(proximas) >= 3:
        h_util = max(max(proximas) / 1.5, (max(max(xs) - min(xs), max(ys) - min(ys))) / 3)
        return texto + (
            f"Com {len(proximas)} bordas perto, a ACI limita o h_ef útil a "
            f"máx(c_a,máx/1,5; s/3) = {_n(min(h_util, h), 0)} mm (17.6.2.1.2): embutir mais não "
            "aumenta a resistência ao cone (sem esse limite, a conta daria resistência caindo com "
            "h_ef^−0,5). Aumente o bloco ou use armadura de ancoragem (17.5.2.1)"
        )
    return texto + (
        "Aumentar h_ef ainda ajuda, mas rende menos que com o cone inteiro; aumentar o bloco (ou "
        "afastar o chumbador da borda) rende mais"
    )


def _barras_de_ancoragem(a_s: float) -> str:
    """Uma sugestão de barras para a armadura de ancoragem (ramos que cruzam o cone)."""
    for phi in (6.3, 8.0, 10.0, 12.5, 16.0, 20.0, 25.0):
        ramos = max(2, math.ceil(a_s / (math.pi * phi**2 / 4) - 1e-9))
        if ramos <= 4:
            area = ramos * math.pi * phi**2 / 4
            return f"por exemplo {ramos} ramos de Ø {_n(phi, 1)} mm = {_n(area, 0)} mm²"
    return "barras grossas: detalhar no projeto do bloco"


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
                x += e.desloc_x_mm
                y += e.desloc_y_mm
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
            resistente = phi_tracao_concreto(e) * n_grupo
            forca = sum(f for _, _, f in membros)
            texto = (
                f"φ·N_sbg = {_n(phi_tracao_concreto(e))} × (1 + s/(6·c_a1))·13·c_a1·√A_brg·√f_c × fator de c_a2 = "
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
    return contato_na_arruela(tab.lado_da_arruela, tab.d_b, t_arruela, gama_a2)


def contato_na_arruela(
    lado: float, d_b: float, t_arruela: float, gama_a2: float
) -> tuple[float, float]:
    """(F_c,Rd em N, ℓ_f em mm) no furo d_b + 1,5 mm de uma arruela quadrada de ``lado`` mm."""
    k1, k2 = coeficientes_contato()
    l_f = (lado - (d_b + FOLGA_DO_FURO_DA_ARRUELA)) / 2
    return min(k1 * l_f, k2 * d_b) * t_arruela * FU_ARRUELA / gama_a2, l_f


@dataclass(frozen=True)
class CortanteDasArruelas:
    """A cortante resistente pelas arruelas especiais soldadas (6.7.2.5), em N."""

    v_rd: float
    f_v: float  # F_v,Rd,i de um chumbador
    f_v_barra: float  # corte da barra rosqueada (6.3.3.2 a)
    f_v_contato: float  # contato no furo da arruela (6.3.3.3)
    l_f: float
    alfa: float


def cortante_das_arruelas(
    d_b: float,
    lado: float,
    t_arruela: float,
    t_placa: float,
    forcas: tuple[float, ...],
    f_ub: float,
    fy_placa: float,
    c: sd.Coeficientes,
    sigma_c_rd: float,
) -> CortanteDasArruelas:
    """V_Rd = Σ V_Rd,i da 6.7.2.5, com F_v,Rd,i = mín(corte da barra; contato no furo da arruela)."""
    f_v_barra = ALFA_V_CHUMBADOR * math.pi * d_b**2 / 4 * f_ub / c.a2
    f_v_contato, l_f = contato_na_arruela(lado, d_b, t_arruela, c.a2)
    f_v = min(f_v_barra, f_v_contato)  # 6.3.3.2 pede também a 6.3.3.3
    alfa = 1.45 * (t_placa + 0.5 * t_arruela) / d_b * (f_ub / fy_placa) * (c.a1 / c.a2)
    teto = 5 * d_b**2 * sigma_c_rd
    v_rd = 0.0
    for f_ti in forcas:
        t = 0.533 * f_ti
        radicando = (1 + alfa**2) * f_v**2 - t**2
        v_i = (math.sqrt(radicando) - alfa * t) / (1 + alfa**2) if radicando > 0 else 0.0
        v_rd += min(max(v_i, 0.0), teto)
    return CortanteDasArruelas(v_rd, f_v, f_v_barra, f_v_contato, l_f, alfa)


def verificar_ancoragem(
    e: EntradaBase, g: Geometria, tab: LinhaTabela18, forcas: tuple[float, ...]
) -> tuple[list[Verificacao], list[str]]:
    """Aço, tipo do chumbador e a ancoragem no concreto (ACI 318-19, Capítulo 17)."""
    linhas: list[Verificacao] = []
    avisos: list[str] = []
    aco = ACOS_CHUMBADOR[e.aco_chumbador]
    verificar = ancoragem_verificada(e)
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
    fora_da_faixa = not n_min <= e.n_chumbadores <= n_max
    if not e.por_formula and fora_da_faixa:
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
    if e.ancoragem != ANCORAGEM_PORCA and not e.por_formula:
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
    if e.ancoragem in POS_INSTALADOS:
        faltam = []
        if not e.sistema_ancoragem.strip() or not e.categoria_aci:
            faltam.append("certificado, identificação da barra e categoria de instalação")
        if not e.h_ef_mm:
            faltam.append("embutimento qualificado para o produto")
        bx, by, _ = bloco_para_o_cone(e, g, tab)
        x0, x1, y0, y1 = limites_bloco(e, bx, by)
        for nome, real, minimo in (
            (
                "espaçamento",
                min(math.dist(a, b) for a, b in combinations(g.posicoes, 2)),
                e.s_min_produto_mm,
            ),
            (
                "distância à borda",
                min(min(x - x0, x1 - x, y - y0, y1 - y) for x, y in g.posicoes),
                e.c_min_produto_mm,
            ),
            ("espessura do concreto", altura_do_bloco(e, g, tab)[0], e.h_min_produto_mm),
        ):
            if minimo:
                linhas.append(
                    _limite(
                        "Produto: " + nome,
                        real >= minimo,
                        "Certificado do produto",
                        f"{_n(real)} mm disponíveis, mínimo {_n(minimo)} mm.",
                    )
                )
            else:
                faltam.append(nome + " mínimo do certificado")
        if faltam:
            linhas.append(
                _alerta(
                    "Qualificação da ancoragem pós-instalada",
                    ref + " 17.5 e 17.9",
                    "Inconclusivo. Informar " + ", ".join(faltam) + ".",
                )
            )
        else:
            linhas.append(
                _info(
                    "Qualificação da ancoragem pós-instalada",
                    e.sistema_ancoragem + f", categoria {e.categoria_aci}.",
                )
            )
    if e.ancoragem == ANCORAGEM_QUIMICO:
        if e.n_sustentada_kN is None or not e.tau_cr_MPa:
            linhas.append(
                _alerta(
                    "Tração sustentada da resina",
                    ref + " 17.5.2.2",
                    "Informar τ_cr e a maior tração sustentada individual de cálculo.",
                )
            )
        else:
            nba = e.tau_cr_MPa * math.pi * tab.d_b * embutimento(e, tab)
            linhas.append(
                Verificacao(
                    "Tração sustentada da resina",
                    e.n_sustentada_kN,
                    0.55 * phi_tracao_concreto(e) * nba / 1000,
                    "kN",
                    ref + " 17.5.2.2",
                    f"0,55·φ·N_ba, φ = {_n(phi_tracao_concreto(e))}, N_ba = {_n(nba / 1000)} kN.",
                )
            )
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
    # 0. o aço do chumbador à tração (ACI 318-19 17.6.1): entra na interação 17.8
    a_se = area_resistente(e, tab)
    f_ut = f_uta(aco)
    linhas.append(
        Verificacao(
            LINHA_ACO_TRACAO_ACI,
            f_max / 1e3,
            (PHI_ACO_TRACAO if e.aco_ductil else 0.65) * a_se * f_ut / 1e3,
            "kN",
            f"{ref} 17.6.1",
            f"φ·N_sa = {_n(0.75 if e.aco_ductil else 0.65)}·A_se·f_uta = {_n(0.75 if e.aco_ductil else 0.65)} × {_n(a_se, 0)} mm² × {_n(f_ut, 0)} MPa, f_uta = "
            "mín(f_u; 1,9·f_y; 862 MPa), no chumbador mais tracionado",
            equacoes=(
                f"φ·N_sa = {_n(0.75 if e.aco_ductil else 0.65)}·A_se·f_uta",
                f"φ·N_sa = {_n(0.75 if e.aco_ductil else 0.65)} × {_n(a_se, 0)} × {_n(f_ut, 0)} = "
                f"{_n((PHI_ACO_TRACAO if e.aco_ductil else 0.65) * a_se * f_ut / 1e3, 1)} kN (N_ua = {_n(f_max / 1e3, 2)} kN)",
            ),
        )
    )
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
    elif e.ancoragem == ANCORAGEM_QUIMICO:
        bond = aderencia(e, g, tab, forcas)
        if bond is None:
            linhas.append(
                _alerta(
                    "Aderência da resina",
                    ref + " 17.6.5",
                    "Inconclusivo. Informar as tensões características τ_cr e τ_uncr do sistema.",
                )
            )
        else:
            phi = phi_tracao_concreto(e)
            linhas.append(
                Verificacao(
                    "Aderência da resina no grupo",
                    sum(tracionados) / 1000,
                    phi * bond[1] / 1000,
                    "kN",
                    ref + " 17.6.5",
                    bond[2],
                )
            )
            individuais = []
            for i, f in enumerate(forcas):
                if f > 0:
                    isolado = aderencia(
                        e, g, tab, tuple(f if j == i else 0 for j in range(len(forcas)))
                    )
                    assert isolado is not None
                    individuais.append(
                        Verificacao(
                            "Aderência individual da resina",
                            f / 1000,
                            phi * isolado[1] / 1000,
                            "kN",
                            ref + " 17.6.5",
                            f"Chumbador {i + 1}. " + isolado[2],
                        )
                    )
            linhas.append(max(individuais, key=lambda v: v.aproveitamento or 0.0))
        if e.n_rd_fabricante_kN:
            linhas.append(
                Verificacao(
                    "Limite individual adicional do fabricante",
                    f_max / 1000,
                    e.n_rd_fabricante_kN,
                    "kN",
                    "Certificado do produto",
                    "Limite complementar informado para a barra adotada.",
                )
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
        truncado = cone_truncado(e, g, tab, forcas)
        if truncado:
            linhas.append(
                _info("Borda do bloco corta o cone de concreto", truncado, f"{ref} 17.6.2.1.2")
            )
        if e.armadura_de_ancoragem:
            a_s = f_max / (0.75 * FY_ARMADURA_DE_ANCORAGEM)
            linhas.append(
                _info(
                    "Cone de concreto: armadura de ancoragem no bloco",
                    f"o cone é dispensado (17.5.2.1): sem armadura ele resistiria "
                    f"{_n(resistente / 1e3, 1)} kN ({texto}). A armadura substitui o cone: por "
                    f"chumbador, A_s ≥ N_ua/(0,75·f_y) = {_n(f_max / 1e3, 2)} kN/(0,75 × "
                    f"{_n(FY_ARMADURA_DE_ANCORAGEM, 0)} MPa) = {_n(a_s, 0)} mm² (CA-50; "
                    f"{_barras_de_ancoragem(a_s)}), no grupo ΣF_t = {_n(total / 1e3, 1)} kN → "
                    f"{_n(total / (0.75 * FY_ARMADURA_DE_ANCORAGEM), 0)} mm²; as barras a até 0,5·h_ef "
                    "do chumbador e ancoradas dos dois lados da superfície de ruptura do cone "
                    "(comprimento de ancoragem da NBR 6118 de cada lado)",
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
            if total > resistente and e.por_formula and not e.h_ef_mm:
                avisos.append(
                    f"O cone de concreto não resiste à tração dos chumbadores nem com o embutimento "
                    f"calculado (h_ef = {_n(embutimento(e, tab), 0)} mm, o que mais ajuda neste "
                    "bloco): informe o bloco real ou arme o bloco para costurar o cone (armadura "
                    "de ancoragem, ACI 318-19 17.5.2.1) e marque essa opção. Trocar o diâmetro "
                    "não resolve o cone."
                )
            elif total > resistente:
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


# =============================================================================================
# Cortante no concreto (ACI 318-19, Capítulo 17)
# =============================================================================================
def altura_do_bloco(e: EntradaBase, g: Geometria, tab: LinhaTabela18) -> tuple[float, bool]:
    """A altura h_a do bloco (mm) e se foi informada; sem ela, a mínima (nota e da Tabela 18)."""
    if e.bloco_z_mm > 0:
        return e.bloco_z_mm, True
    return bloco_minimo(e, g, tab)[2], False


def _texto_do_bloco(bx: float, by: float, h_a: float, informado: bool, altura: bool) -> str:
    planta = f"bloco {_n(bx, 0)} × {_n(by, 0)} mm" + ("" if informado else " (o mínimo)")
    return planta + f", h_a = {_n(h_a, 0)} mm" + ("" if altura else " (a mínima)")


def ruptura_da_borda_por_cortante(
    e: EntradaBase, g: Geometria, tab: LinhaTabela18, v_sd: float
) -> tuple[float, float, str] | None:
    """(V_Sd, φ·V_cbg, conta) da ruptura do concreto da borda pela fila da frente (ACI 17.7.2).

    V_Sd é a resultante, sem direção conhecida: vale a pior das duas direções (ℓx e ℓy). A
    cortante inteira vai para a fila de chumbadores mais perto da borda para onde ela empurra (a
    hipótese a favor da segurança do AISC Design Guide 1), c_a1 dessa fila à face do bloco.
    ψ_c,V = 1,0 (fissurado, sem armadura de borda), ψ_ec,V = 1,0, φ = 0,70 (condição B).
    """
    if v_sd <= 0:
        return None
    bx, by, informado = bloco_para_o_cone(e, g, tab)
    h_a, altura = altura_do_bloco(e, g, tab)
    d_a = tab.d_b
    raiz = math.sqrt(e.fck_MPa)
    l_e = min(embutimento(e, tab), 8 * d_a)
    pior: tuple[float, float, str] | None = None
    componentes = (e.vx_kN, e.vy_kN)
    orientada = any(v is not None for v in componentes)
    n_eng = (
        len(g.posicoes)
        if e.cortante == CORTANTE_ARRUELAS
        else engatados_sem_arruela(len(g.posicoes))
    )
    pos_bloco = [(x + e.desloc_x_mm, y + e.desloc_y_mm) for x, y in g.posicoes]
    for indices in combinations(range(len(pos_bloco)), n_eng):
        ativos = [pos_bloco[i] for i in indices]
        for eixo, sinal in ((0, 1), (0, -1), (1, 1), (1, -1)):
            vn = max(0.0, sinal * (componentes[eixo] or 0.0) * 1000) if orientada else v_sd
            vt = abs(componentes[1 - eixo] or 0.0) * 1000 if orientada else 0.0
            if not (vn or vt):
                continue
            ao_longo = [sinal * p[eixo] for p in ativos]
            frente = max(ao_longo)
            fila = [p[1 - eixo] for p in ativos if abs(sinal * p[eixo] - frente) < 1e-6]
            meia_l = (bx if eixo == 0 else by) / 2
            meia_t = (by if eixo == 0 else bx) / 2
            c1 = meia_l - frente
            if c1 <= 0:
                continue
            distancias_laterais = (meia_t + min(fila), meia_t - max(fila))
            c2 = min(distancias_laterais)
            c2_max = max(distancias_laterais)
            s = max(fila) - min(fila)
            reducao = ""
            if c2_max < 1.5 * c1 and h_a < 1.5 * c1:  # 17.7.2.1.2: bloco estreito e baixo
                limite = max(c2_max / 1.5, h_a / 1.5, s / 3)
                if limite < c1:
                    reducao = f" (c_a1 reduzido de {_n(c1, 0)} mm pela 17.7.2.1.2)"
                    c1 = limite
            largura = min(max(fila) + 1.5 * c1, meia_t) - max(min(fila) - 1.5 * c1, -meia_t)
            a_vco = 4.5 * c1 * c1
            a_vc = min(largura * min(1.5 * c1, h_a), len(fila) * a_vco)
            psi_ed = 1.0 if c2 >= 1.5 * c1 else 0.7 + 0.3 * c2 / (1.5 * c1)
            psi_h = max(1.0, math.sqrt(1.5 * c1 / h_a))
            v_b1 = 0.6 * (l_e / d_a) ** 0.2 * math.sqrt(d_a) * raiz * c1**1.5
            v_b2 = 3.7 * raiz * c1**1.5
            v_b = min(v_b1, v_b2)
            phi_v = 0.75 if e.armadura_suplementar else 0.70
            resultante = (e.desloc_x_mm, e.desloc_y_mm)
            ec = abs(sum(p[1 - eixo] for p in ativos) / len(ativos) - resultante[1 - eixo])
            psi_ec = 1 / (1 + ec / (1.5 * c1))
            base = phi_v * a_vc / a_vco * psi_h * v_b * psi_ec
            resistente = base * psi_ed
            razao_normal = vn / resistente if resistente > 0 else math.inf if vn > 0 else 0.0
            razao_paralela = vt / (2 * base) if base > 0 else math.inf if vt > 0 else 0.0
            interacao_borda = math.hypot(razao_normal, razao_paralela)
            demanda = interacao_borda * resistente
            paralelo = vt > 0 and vt / (2 * base) > vn / resistente
            direcao = "ℓx" if eixo == 0 else "ℓy"
            texto = (
                f"face {direcao}{' +' if sinal > 0 else ' −'}, componente {'paralela' if paralelo else 'normal'}, toda na fila da frente ({len(fila)} chumbador(es)): "
                f"φ·V_cbg = φ × (A_Vc/A_Vco)·ψ_ed,V·ψ_h,V·ψ_ec,V·V_b = {_n(phi_v)} × ({_n(a_vc / 1e3, 1)}/"
                f"{_n(a_vco / 1e3, 1)}) × {_n(psi_ed, 3)} × {_n(psi_h, 3)} × {_n(psi_ec, 3)} × {_n(v_b / 1e3, 1)} kN; "
                f"V_b = mín(0,6·(ℓ_e/d_a)^0,2·√d_a·√f_c·c_a1^1,5; 3,7·√f_c·c_a1^1,5), c_a1 = "
                f"{_n(c1, 0)} mm{reducao}, c_a2,min = {_n(c2, 0)} mm, ℓ_e = {_n(l_e, 0)} mm, e′_V = {_n(ec, 0)} mm; "
                f"{_texto_do_bloco(bx, by, h_a, informado, altura)}; ψ_c,V = 1,0 (fissurado)"
            )
            if vt:
                texto += f". Paralela à face: {vt / 1000:.2f} kN; φV∥ = 2 × φV_cbg, sem fator de borda. Interação elíptica conservadora = {_n(interacao_borda, 3)}."
            if pior is None or demanda / resistente > pior[0] / pior[1]:
                pior = (demanda, resistente, texto)
    return pior


def arrancamento_por_alavanca(
    e: EntradaBase, g: Geometria, tab: LinhaTabela18, v_sd: float
) -> tuple[float, float, str] | None:
    """(V_Sd, φ·V_cpg, conta) do arrancamento por alavanca do grupo (pryout, ACI 17.7.3)."""
    if v_sd <= 0:
        return None
    n = len(g.posicoes)
    eng = n if e.cortante == CORTANTE_ARRUELAS else engatados_sem_arruela(n)
    pior = None
    h = embutimento(e, tab)
    k_cp = 1.0 if h < 65.0 else 2.0
    for indices in combinations(range(n), eng):
        forcas = tuple(float(i in indices) for i in range(n))
        cone = cone_de_concreto(e, g, tab, forcas)
        assert cone is not None
        ncb = cone[1] / phi_tracao_concreto(e)
        nominal = ncb
        texto = f"N_cb(g) = {_n(ncb / 1000)} kN"
        if e.ancoragem == ANCORAGEM_QUIMICO:
            bond = aderencia(e, g, tab, forcas)
            if bond is None:
                return None
            nominal = min(ncb, bond[1])
            texto += f", N_a(g) = {_n(bond[1] / 1000)} kN. Governa o menor"
        rd = PHI_CORTANTE_CONCRETO * k_cp * nominal
        if pior is None or rd < pior[1]:
            ids = ", ".join(str(i + 1) for i in indices)
            pior = (
                v_sd,
                rd,
                f"{eng} de {n} chumbadores mobilizados ({ids}). {texto}. "
                f"φ·V_cp(g) = 0,70 × {_n(k_cp, 0)} × {_n(nominal / 1000)} kN.",
            )
    return pior


def ruptura_a_frente_da_placa_de_cisalhamento(
    e: EntradaBase, g: Geometria, tab: LinhaTabela18, v_sd: float
) -> tuple[float, float, str] | None:
    """(V_Sd, φ·V_cb, conta) do concreto à frente da placa de cisalhamento (ACI 17.11.3).

    A placa no centro da base; vale a pior das duas orientações (a cortante não tem direção
    conhecida). c_a1 da face que empurra à face do bloco; A_Vc com a altura h_ef,sl + 1,5·c_a1
    (limitada por h_a), descontada a área de apoio da placa, b_h·h_ef,sl; V_b = 3,7·√f_c·c_a1^1,5.
    """
    if v_sd <= 0:
        return None
    bx, by, informado = bloco_para_o_cone(e, g, tab)
    h_a, altura = altura_do_bloco(e, g, tab)
    h_sl = max(e.b_v_mm - g.e_n, 0.0)
    raiz = math.sqrt(e.fck_MPa)
    pior: tuple[float, float, str] | None = None
    orientacoes = [
        (bx / 2 - abs(e.desloc_x_mm), by / 2 - abs(e.desloc_y_mm), "ℓx"),
        (by / 2 - abs(e.desloc_y_mm), bx / 2 - abs(e.desloc_x_mm), "ℓy"),
    ]
    if e.vx_kN is not None or e.vy_kN is not None:
        if not e.vx_kN:
            return None
        v_sd = abs(e.vx_kN) * 1000
        sinal = 1 if e.vx_kN > 0 else -1
        orientacoes = [
            (
                bx / 2 - sinal * e.desloc_x_mm,
                by / 2 - abs(e.desloc_y_mm),
                "ℓx +" if sinal > 0 else "ℓx −",
            )
        ]
    for meia_l, meia_t, direcao in orientacoes:
        c1 = meia_l - e.t_pv_mm / 2
        if c1 <= 0:
            continue
        c2 = meia_t - e.b_h_mm / 2
        largura = 2 * min(e.b_h_mm / 2 + 1.5 * c1, meia_t)
        a_vc = max(largura * min(h_sl + 1.5 * c1, h_a) - e.b_h_mm * h_sl, 0.0)
        a_vco = 4.5 * c1 * c1
        psi_ed = 1.0 if c2 >= 1.5 * c1 else 0.7 + 0.3 * max(c2, 0.0) / (1.5 * c1)
        psi_h = max(1.0, math.sqrt(1.5 * c1 / h_a))
        v_b = 3.7 * raiz * c1**1.5
        resistente = PHI_CORTANTE_CONCRETO * a_vc / a_vco * psi_ed * psi_h * v_b
        texto = (
            f"cortante ao longo de {direcao}: φ·V_cb = 0,70 × (A_Vc/A_Vco)·ψ_ed,V·ψ_h,V·V_b = 0,70 × "
            f"({_n(a_vc / 1e3, 1)}/{_n(a_vco / 1e3, 1)}) × {_n(psi_ed, 3)} × {_n(psi_h, 3)} × "
            f"{_n(v_b / 1e3, 1)} kN; V_b = 3,7·√f_c·c_a1^1,5, c_a1 = {_n(c1, 0)} mm, h_ef,sl = "
            f"b_v − e_n = {_n(h_sl, 0)} mm (área de apoio descontada de A_Vc); "
            f"{_texto_do_bloco(bx, by, h_a, informado, altura)}"
        )
        if pior is None or resistente < pior[1]:
            pior = (v_sd, resistente, texto)
    return pior


LINHA_ACO_TRACAO_ACI = "Chumbador: aço à tração (ACI 318-19)"
LINHA_FLEXAO_NA_ARGAMASSA = "Chumbador: flexão na camada de argamassa"
#: Barra redonda maciça: M_Rd = Z·f_y/γ_a1 ≤ 1,5·W·f_y/γ_a1 (NBR 8800:2025 5.4.2.2); no círculo
#: Z/W = 16/(3π) = 1,70, então vale o teto 1,5·W.
FATOR_PLASTICO_REDONDO = 1.5


@dataclass(frozen=True)
class FlexaoNaArgamassa:
    """O chumbador fletido pela cortante na camada de argamassa (mm, N, MPa)."""

    n_engatados: int
    v_i: float  # N, cortante de um chumbador
    braco: float  # mm
    momento: float  # N·mm
    d_s: float  # mm, diâmetro da área resistente da rosca
    w: float  # mm³, módulo elástico π·d_s³/32
    sigma_b: float  # MPa, M/(1,5·W)
    sigma_t: float  # MPa, F_t/A_se
    f_t: float
    a_se: float
    f_y: float
    gama_a1: float

    @property
    def sigma(self) -> float:
        return self.sigma_b + self.sigma_t

    @property
    def limite(self) -> float:
        return self.f_y / self.gama_a1

    def texto(self) -> str:
        return (
            f"n_engatados = {self.n_engatados} (os mesmos do aço à cortante): V_i = "
            f"{_n(self.v_i / 1e3, 2)} kN; braço b = e_n + t_p/2 + Δ = {_n(self.braco, 1)} mm (a "
            "força no meio da chapa em contato, sem restrição à rotação, sem apoio lateral do graute); M = V_i·b = "
            f"{_n(self.momento / 1e3, 1)} kN·mm; na rosca, d_s = √(4·A_se/π) = {_n(self.d_s, 2)} mm, "
            f"W = π·d_s³/32 = {_n(self.w, 0)} mm³ e M_Rd pela plastificação da barra redonda, "
            f"Z·f_y ≤ 1,5·W·f_y (NBR 8800 5.4.2.2): σ_b = M/(1,5·W) = {_n(self.sigma_b, 1)} MPa; "
            f"σ_t = F_t/A_se = {_n(self.f_t / 1e3, 2)} kN/{_n(self.a_se, 0)} mm² = "
            f"{_n(self.sigma_t, 1)} MPa; σ = σ_b + σ_t = {_n(self.sigma, 1)} MPa. Limite f_y/γ_a1 = "
            f"{_n(self.f_y, 0)}/{_n(self.gama_a1)} = {_n(self.limite, 1)} MPa (o mesmo que "
            "M/M_Rd + N/N_Rd ≤ 1)"
        )


def flexao_na_argamassa(
    v_sd: float,
    n_engatados: int,
    f_t: float,
    e_n: float,
    t_p: float,
    a_se: float,
    f_y: float,
    gama_a1: float,
    *,
    acrescimo_mm: float = 0.0,
) -> FlexaoNaArgamassa:
    """Flexão do chumbador na argamassa com a tração dele (N, mm, MPa).

    A rosca passa pela camada de argamassa: a seção é a da área resistente (d_s); o momento
    resistente é o da plastificação da barra redonda maciça, limitado a 1,5·W·f_y (NBR 8800
    5.4.2.2), e a interação com a tração é linear.
    """
    n = max(n_engatados, 1)
    v_i = v_sd / n
    braco = e_n + t_p / 2 + acrescimo_mm
    momento = v_i * braco
    d_s = math.sqrt(4 * a_se / math.pi)
    w = math.pi * d_s**3 / 32
    sigma_b = momento / (FATOR_PLASTICO_REDONDO * w)
    sigma_t = f_t / a_se
    return FlexaoNaArgamassa(
        n, v_i, braco, momento, d_s, w, sigma_b, sigma_t, f_t, a_se, f_y, gama_a1
    )


#: Linhas da ancoragem à tração e à cortante que entram na interação da ACI 318-19 17.8.
LINHAS_DE_TRACAO_ACI = (
    LINHA_ACO_TRACAO_ACI,
    "Arrancamento da cabeça (porca ou chapa na ponta)",
    "Guarda-chuva: arrancamento do gancho",
    "Pós-instalado: tração resistente do fabricante",
    "Aderência da resina no grupo",
    "Aderência individual da resina",
    "Limite individual adicional do fabricante",
    "Cone de concreto dos chumbadores tracionados",
    "Arrancamento lateral da cabeça junto à borda",
)
LINHA_RUPTURA_DA_BORDA = "Cortante no concreto: ruptura da borda do bloco"
LINHA_ALAVANCA = "Cortante no concreto: arrancamento por alavanca (pryout)"
LINHA_INTERACAO = "Interação tração × cortante nos chumbadores"
LINHA_FRENTE_DA_PLACA = "Cortante no concreto: ruptura à frente da placa de cisalhamento"
PREFIXO_SOLDA_DO_PILAR = "Solda do pilar na placa"


def interacao_tracao_cortante(
    razao_n: float, razao_v: float, texto_n: str, texto_v: str
) -> Verificacao:
    """ACI 318-19 17.8: N/φN_n + V/φV_n ≤ 1,2 quando as duas razões passam de 0,2."""
    ref = "ACI 318-19 17.8"
    if razao_n <= LIMITE_SEM_INTERACAO or razao_v <= LIMITE_SEM_INTERACAO:
        return Verificacao(
            LINHA_INTERACAO,
            None,
            None,
            "—",
            ref,
            f"N/φN_n = {_n(razao_n, 3)} ({texto_n}) e V/φV_n = {_n(razao_v, 3)} ({texto_v}): com "
            "uma delas ≤ 0,2 a interação é dispensada (17.8.1 e 17.8.2)",
            "OK",
            tipo="limite",
        )
    return Verificacao(
        LINHA_INTERACAO,
        razao_n + razao_v,
        1.2,
        "—",
        f"{ref}.3",
        f"N/φN_n + V/φV_n = {_n(razao_n, 3)} ({texto_n}) + {_n(razao_v, 3)} ({texto_v}) ≤ 1,2; "
        "cada razão com o modo que governa (aço ou concreto)",
    )


def embutimento_pelo_cone(
    e: EntradaBase, g: Geometria, tab: LinhaTabela18, forcas: tuple[float, ...]
) -> float:
    """Por fórmula: o menor h_ef, de 25 em 25 mm, que passa no cone dos tracionados (ACI 17.6.2).

    Nunca menos que 12·d_b. Sem chumbador tracionado, ou com armadura de ancoragem (que substitui o
    cone), fica esse piso. Quando nenhum passa (perto de 3 ou 4 bordas o h_ef útil para de
    crescer), o menor com a melhor relação resistente/solicitante — e o cone reprova.
    """
    piso = _acima(EMBUTIMENTO_MINIMO_EM_D * tab.d_b, 25.0)
    if e.armadura_de_ancoragem or not any(f > 0 for f in forcas):
        return piso
    sem_h = replace(e, h_ef_mm=0.0)
    melhor_h, melhor, sem_ganho = piso, -1.0, 0
    h = piso
    while h <= EMBUTIMENTO_MAXIMO + 1e-9 and sem_ganho < 8:
        cone = cone_de_concreto(sem_h, g, replace(tab, h1=h), forcas)
        if cone is None:
            return piso
        total, resistente, _ = cone
        if resistente >= total:
            return h
        if resistente / total > melhor * (1 + 1e-3):
            melhor_h, melhor, sem_ganho = h, resistente / total, 0
        else:
            sem_ganho += 1
        h += 25.0
    return melhor_h


def _menor_diametro(capacidade: Any, alvo: float, d_max: float = 160.0) -> float | None:
    """O menor d_b (mm) com capacidade(d_b) ≥ alvo, por bisseção; None se nem d_max basta."""
    if capacidade(d_max) < alvo:
        return None
    baixo, alto = 1.0, d_max
    if capacidade(baixo) >= alvo:
        return baixo
    for _ in range(60):
        meio = (baixo + alto) / 2
        if capacidade(meio) >= alvo:
            alto = meio
        else:
            baixo = meio
    return alto


def diametros_por_criterio(
    e: EntradaBase,
    forcas: tuple[float, ...],
    f_t: float,
    v_sd: float,
    c: sd.Coeficientes,
    f_ub: float,
    fy_placa: float,
    sigma_c_rd: float,
    tab: LinhaTabela18,
) -> tuple[tuple[str, float | None, str], ...]:
    """Por fórmula: o d_b que cada critério pede, com as forças desta base (mm; None: nenhum)."""
    linhas: list[tuple[str, float | None, str]] = []
    if f_t > 0:
        linhas.append(
            (
                "Tração no aço",
                math.sqrt(4 * f_t / (0.75 * math.pi * f_ub / c.a2)),
                f"{REF} 6.7.2.2: d_b,min = √(4·F_t,Sd/(0,75·π·f_ub/γ_a2))",
            )
        )
        if e.ancoragem == ANCORAGEM_PORCA and e.chapa_na_ponta_mm <= 1.5 * tab.d_b + 3.2:

            def cabeca(d: float) -> float:  # só a porca pesada na ponta
                return PHI_CONCRETADO * 8 * (math.sqrt(3) / 2 * (1.5 * d + 3.2) ** 2 - math.pi * d**2 / 4) * e.fck_MPa  # fmt: skip

            linhas.append(
                (
                    "Arrancamento da porca da ponta",
                    _menor_diametro(cabeca, f_t),
                    "ACI 318-19 17.6.3.2.2 (a): φ·8·A_brg·f_c, A_brg da porca sextavada pesada",
                )
            )
        elif e.ancoragem == ANCORAGEM_GANCHO:

            def gancho(d: float) -> float:
                return PHI_CONCRETADO * 0.9 * e.fck_MPa * min(e.e_h_mm or 4.5 * d, 4.5 * d) * d

            linhas.append(
                (
                    "Arrancamento do gancho",
                    _menor_diametro(gancho, f_t),
                    "ACI 318-19 17.6.3.2.2 (b): φ·0,9·f_c·e_h·d_b, e_h até 4,5·d_b",
                )
            )
    if e.cortante == CORTANTE_ARRUELAS and v_sd > 0:

        def corte(d: float) -> float:
            d_f = e.d_f_mm if e.d_f_mm > d else furo_padrao(d)
            t_a = e.t_arruela_mm or espessura_da_arruela(d)
            return cortante_das_arruelas(
                d, lado_da_arruela(d, d_f), t_a, e.t_placa_mm, forcas, f_ub, fy_placa, c, sigma_c_rd
            ).v_rd

        linhas.append(
            (
                "Cortante pelas arruelas soldadas",
                _menor_diametro(corte, v_sd),
                f"{REF} 6.7.2.5, com a arruela e o furo por fórmula para cada d_b",
            )
        )
    return tuple(linhas)


#: O cone depende do bloco, do embutimento e da armadura de ancoragem, não do diâmetro: as buscas
#: de diâmetro do modo por fórmula não o usam (senão o bloco mínimo, que cresce com a₃ = 6·d_b,
#: faria um chumbador enorme "passar").
LINHA_DO_CONE = "Cone de concreto dos chumbadores tracionados"
#: As linhas que dependem do bloco (e não do diâmetro): ficam fora das buscas por fórmula.
LINHAS_DO_BLOCO = (
    LINHA_DO_CONE, LINHA_RUPTURA_DA_BORDA, LINHA_ALAVANCA, LINHA_INTERACAO, LINHA_FRENTE_DA_PLACA,
)  # fmt: skip


def chumbadores_passam(r: ResultadoBase) -> bool:
    """Inclui o aço, a flexão, a ancoragem e o mecanismo de cortante."""
    return all(
        v.status not in ("NÃO OK", "ALERTA")
        for grupo, linhas in r.grupos
        if grupo in (GRUPO_CHUMBADORES, GRUPO_CORTANTE)
        for v in linhas
    )


def passa_fora_o_cone(r: ResultadoBase) -> bool:
    """Nenhuma verificação reprova, fora o cone de concreto (que o diâmetro não resolve)."""
    return all(
        v.status != "NÃO OK"
        for v in r.verificacoes
        if v.nome not in LINHAS_DO_BLOCO and not da_solda_do_pilar(v)
    )


def da_solda_do_pilar(v: Verificacao) -> bool:
    """A linha é da solda do pilar na placa (depende do perfil e dos esforços, não da placa)."""
    return v.nome.startswith(PREFIXO_SOLDA_DO_PILAR)


def passa_fora_a_solda_do_pilar(r: ResultadoBase) -> bool:
    """Nenhuma verificação reprova, fora a solda do pilar (que a placa e o chumbador não mudam)."""
    return all(v.status != "NÃO OK" for v in r.verificacoes if not da_solda_do_pilar(v))


def solda_do_pilar_reprova(r: ResultadoBase) -> bool:
    return any(v.status == "NÃO OK" for v in r.verificacoes if da_solda_do_pilar(v))


def menor_diametro_que_atende(e: EntradaBase) -> ResultadoBase | None:
    """Por fórmula: o menor diâmetro comercial, da família do atual, que passa nos chumbadores.

    Cada diâmetro recalcula a base inteira (a₁, a₂, a placa e as forças mudam com ele), com o furo
    pela regra. A espessura da placa fica como está (a base mais leve troca as duas coisas). None
    fora do modo por fórmula ou quando nenhum diâmetro atende (o que reprova não depende dele).
    """
    if not e.por_formula:
        return None
    if e.ancoragem in POS_INSTALADOS and (
        e.n_rd_fabricante_kN or e.sistema_ancoragem or e.tau_cr_MPa or e.tau_uncr_MPa
    ):
        atual = calcular(e)
        return atual if chumbadores_passam(atual) else None
    for rosca in roscas_da_familia(rosca_do_chumbador(e).familia):
        try:
            r = calcular(replace(e, chumbador=rosca.nome, d_b_mm=0.0, passo_mm=0.0, d_f_mm=0.0))
        except BaseInvalida:
            continue
        if chumbadores_passam(r):
            return r
    return None


def calcular(e: EntradaBase) -> ResultadoBase:
    """A base com os esforços da entrada ou, com ``e.casos``, a envoltória das combinações."""
    _validar(e)
    if e.casos:
        return _envoltoria(e)
    return _calcular_um(e)


def _calcular_um(e: EntradaBase) -> ResultadoBase:
    if e.vx_kN is not None or e.vy_kN is not None:
        e = replace(e, v_sd_kN=math.hypot(e.vx_kN or 0.0, e.vy_kN or 0.0))
    if e.aco_ductil is None:
        # O padrão conservador para uma barra sem identificação acompanha o da tela.
        e = replace(
            e,
            aco_ductil=e.ancoragem in CONCRETADOS
            and ACOS_CHUMBADOR[e.aco_chumbador].equivalente_a36,
        )
    g = geometria(e)
    if e.m_sd_y_kNm < 0 and g.e_u:
        g = replace(g, y_dorso=-g.y_dorso)  # eixos internos do solver com momentos positivos
    tab = disposicoes(e)
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
    elastica = e.distribuicao == DISTRIBUICAO_ELASTICA
    a_se = area_resistente(e, tab)
    dist = (
        distribuicao_elastica(g, axial, momento, momento_y, e.fck_MPa, a_se) if elastica else None
    )
    obliqua = (
        flexao_obliqua(g, sigma_rd, axial, momento, momento_y)
        if momento_y > 0 and not elastica
        else None
    )
    if dist is not None:
        caso = dist.caso
    else:
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
    if g.e_u:
        avisos.append(
            "Pilar U: a 6.7 é escrita para o perfil I ou H, e o programa trata o U como meia I de "
            "mesa 2·b_f (placa centrada no centro geométrico do U, linhas de engaste no dorso da "
            "alma e a 0,80·b_f dele). A 6.7.1.1 admite outras soluções desde que atendam 6.1.1.3 — "
            "registre o método no memorial."
        )
    inicios: list[tuple[str, int]] = [(GRUPO_GEOMETRIA, 0)]  # onde começa cada grupo da tela
    if (
        e.bloco_x_mm
        and e.bloco_x_mm + 1e-6 < g.lx + 2 * abs(e.desloc_x_mm)
        or e.bloco_y_mm
        and e.bloco_y_mm + 1e-6 < g.ly + 2 * abs(e.desloc_y_mm)
    ):
        raise BaseInvalida(
            "A placa deve caber inteiramente no bloco, incluindo o deslocamento informado."
        )
    if g.e_u and not e.por_formula:
        linhas.append(
            _info(
                "Aplicação da Tabela 18 ao perfil U",
                "Dimensões de montagem tomadas como referência. A geometria e a resistência do U exigem verificação própria.",
            )
        )
    if e.chapa_na_ponta_mm and not e.chapa_ponta_esp_mm:
        linhas.append(
            _alerta(
                "Montagem da chapa na ponta",
                "Detalhamento da barra",
                "Informar a espessura da chapa para o comprimento de corte.",
            )
        )
    if min(e.bloco_x_mm, e.bloco_y_mm, e.bloco_z_mm) == 0:
        texto_bloco = "Dimensões estimadas do bloco. Resistências condicionadas à execução e à verificação do bloco indicado."
        if e.modo_bloco == "verificacao":
            linhas.append(
                _alerta(
                    "Geometria real do bloco",
                    "Geometria da obra",
                    "Verificação inconclusiva. Informar largura, comprimento e altura reais.",
                )
            )
        else:
            linhas.append(_info("Pré-dimensionamento do bloco", texto_bloco))
    if g.e_u or momento_y:
        linhas.append(
            _alerta(
                "Validação do modelo de placa",
                "Campo de aplicação da NBR 8800, 6.7",
                "Conferir o modelo de faixas e a compatibilidade da ligação com análise independente para esta geometria e carregamento.",
            )
        )
    if g.e_u:
        linhas.append(
            _info(
                "Pilar U: método da 6.7 estendido",
                f"centro geométrico a x̄ = {_n(abs(g.y_dorso), 1)} mm do dorso da alma, no centro "
                f"da placa, mesas abertas para +y nos eixos físicos; "
                f"balanços em ℓy: {_n(g.ly / 2 - abs(g.y_dorso), 1)} mm além do dorso e "
                f"{_n(g.ly / 2 - (0.80 * g.b_f - abs(g.y_dorso)), 1)} mm além de 0,80·b_f (n = o "
                "maior, "
                f"{_n(g.n, 1)} mm); entre as mesas, a I equivalente de mesa 2·b_f = "
                f"{_n(g.b_eq, 0)} mm: n₀ = √(d·2·b_f)/4 = {_n(g.n0, 1)} mm",
                f"{REF} 6.7.1.1 e 6.1.1.3",
            )
        )
    ref_cc = f"{REF} 6.6.5"
    texto_sigma = (
        f"σ_c,Rd = 0,85·f_ck/γ_c·√(A₂/A₁) ≤ 1,7·f_ck/γ_c = mín(0,85 × {_n(e.fck_MPa, 1)}/"
        f"{_n(gc, 1)} × √{_n(razao, 2)}; 1,7 × {_n(e.fck_MPa, 1)}/{_n(gc, 1)}) = {_n(sigma_rd)} MPa"
    )
    # ------------------------------------------------------------------ geometria e limites
    regra_n = {
        TIPO_1: "base tipo 1: 4 ≤ n_b ≤ 8, em duas linhas iguais",
        TIPO_2: "base tipo 2: n_b = 4",
        TIPO_ROTULADA: "base rotulada em y: 2 chumbadores no eixo y, um de cada lado da alma",
        TIPO_ROTULADA_X: "base rotulada em x: 2 chumbadores no eixo x, um fora de cada mesa",
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
    if e.tipo == TIPO_2 and not elastica:
        if caso in ("C3", "T3"):
            linhas.append(
                _limite(
                    "Caso previsto para a base tipo 2",
                    False,
                    f"{REF} 6.7.1.4",
                    f"caso {caso}: a base tipo 2 só cobre C1, C2, T1 e T2 — use a base tipo 1",
                )  # fmt: skip
            )
    texto_ly = (
        "ℓy informada"
        if e.ly_mm
        else f"ℓy = (0,5·n_b − 1)·a₂ + 2·a₁ = (0,5·{n_b} − 1)·{_n(g.a2, 0)} + 2·{_n(g.a1, 0)}"
        if da_norma
        else f"ℓy = máx(2·a₁; 2·máx|y_perfil| + 25) = máx({_n(2*g.a1, 1)}; {_n(2*max(map(abs,g.faixa_y))+25, 1)})"
        if e.tipo == TIPO_ROTULADA_X
        else f"ℓy = a₂ + 2·a₁ = {_n(g.a2, 0)} + 2·{_n(g.a1, 0)}"
    )  # fmt: skip
    if g.e_u:  # a placa centrada no centro geométrico: a folga de 12,5 mm de cada lado do U
        y_min, y_max = g.faixa_y
        folga = g.ly / 2 - max(-y_min, y_max)
        linhas.append(
            _limite(
                "Largura da placa ℓy: 12,5 mm além do U de cada lado",
                folga >= 12.5 - 1e-9,
                f"{REF} 6.7.2.1 (b_f + 25 mm, com a placa centrada no centro geométrico)",
                f"{texto_ly} = {_n(g.ly, 0)} mm; o U vai de y = {_n(y_min, 1)} a "
                f"{_n(y_max, 1)} mm (do dorso às pontas das mesas): sobra {_n(folga, 1)} mm do "
                "lado mais curto, ≥ 12,5 mm (senão, aumente a₂ ou a₁)",
            )
        )
    else:
        linhas.append(
            _limite(
                "Largura da placa ℓy ≥ b_f + 25 mm",
                g.ly >= g.b_f + 25.0 - 1e-9,
                f"{REF} 6.7.2.1",
                f"{texto_ly} = {_n(g.ly, 0)} mm; b_f + 25 = {_n(g.b_f + 25.0, 0)} mm (senão, "
                "aumente a₂ ou a₁)",
            )
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
                f"{_n(folga_mesa, 0)} mm até a mesa, ambas ≥ 0 (senão, perfil mais alto, "
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
    x_fator = 4 * g.d * g.b_eq / (g.d + g.b_eq) ** 2
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
                ("X = [4·d·(2b_f)/(d + 2b_f)²]" if g.e_u else "X = [4·d·b_f/(d + b_f)²]")
                + f"·N_Sd/(ℓx·ℓy·σ_c,Rd) = {_n(x_fator, 3)} × "
                f"{_n(axial / 1e3, 1)} kN/({_n(g.lx, 0)} × {_n(g.ly, 0)} × {_n(sigma_rd)}) ≤ 1 "
                "(caso contrário, refazer a ligação)",
            )  # fmt: skip
        )
        x_val = min(x_val, 1.0)
        lam = min(2 * math.sqrt(x_val) / (1 + math.sqrt(1 - x_val)), 1.0)
    n0_lam = lam * g.n0
    zona: tuple[Ponto, ...] = ()
    contas: dict[str, Any] = {}  # valores para as equações do memorial (_equacoes_da_base)
    if dist is not None:
        forcas = list(dist.forcas)
        f_t = max(forcas) if forcas else 0.0
        zona = dist.zona
        e_cs = modulo_do_concreto(e.fck_MPa)
        linhas.append(
            _info(
                "Distribuição elástica da pressão (placa rígida)",
                f"w = σ₀ + a_x·x + a_y·y: pressão σ = w onde w > 0 (o concreto não puxa) e, onde a "
                f"placa levanta, cada chumbador puxa F_i = n·A_se·(−w_i), proporcional à distância "
                f"à linha neutra; n = E_s/E_cs = {_n(E_ACO, 0)}/{_n(e_cs, 0)} = "
                f"{_n(dist.razao_modular, 2)} (E_cs pela NBR 6118, 8.2.8), A_se = {_n(a_se, 0)} mm²; "
                + (
                    "sem chumbador tracionado"
                    if f_t <= 0
                    else f"{sum(1 for f in forcas if f > 0)} chumbador(es) tracionado(s), "
                    f"F_t,máx = {_n(f_t / 1e3, 2)} kN"
                ),
                "método elástico (6.7.1.1)",
            )
        )
        linhas.append(
            _limite(
                "Equilíbrio elástico da placa",
                dist.equilibrio,
                "método elástico (6.7.1.1)",
                "a pressão linear e os chumbadores equilibram N, M e M_y; senão, alterar a ligação "
                "(placa maior, chumbadores mais afastados ou outra disposição)",
            )
        )
        t_min1 = 0.0
        texto_zona_t = "sem contato com o concreto"
        if dist.equilibrio and zona:
            l_c = g.lx / 2 - min(x for x, _ in zona)
            sigma_sd = dist.sigma_max
            t_min1, texto_zona_t = espessura_pela_zona(g, zona, 0.0, fy_d, plano=dist.plano)
            if l_c >= g.m and axial > 0:  # o λ·n₀ da 6.7 (entre as mesas)
                t_min1 = max(t_min1, n0_lam * math.sqrt(2 * sigma_sd / fy_d))
        t_min2, texto_tracao = (
            _espessura_pela_tracao(g, tuple(forcas), fy_d) if f_t > 0 else (0.0, "")
        )
        t_min = max(t_min1, t_min2)
        v_atrito = min(e.mu * dist.compressao / c.a2, tau_rd * g.lx * g.ly)
        texto_t = (
            f"pela pressão linear na zona comprimida, t_p,min1 = {_n(t_min1, 1)} mm "
            f"({texto_zona_t})"
        )
        if f_t > 0:
            texto_t += (
                f"; pela tração nos chumbadores, t_p,min2 = {_n(t_min2, 1)} mm ({texto_tracao})"
            )
    elif obliqua is not None:
        forcas = list(obliqua.forcas)
        f_t = max(forcas)
        zona = obliqua.zona
        if zona:  # o trecho sob pressão no plano do momento (para o corte)
            l_c = g.lx / 2 - min(x for x, _ in zona)
        texto_zona = f"A_c = {_n(obliqua.area / 100, 0)} cm² (zona além da linha neutra inclinada)"
        if caso == "C2":
            sigma_sd = obliqua.sigma
            # a pressão σ_c,Sd só na zona comprimida: o balanço inteiro sob ela superestimaria
            # a placa quando a zona é um canto (AISC DG1 3.3, a mesma regra da C3)
            t_min, texto_zona_t = espessura_pela_zona(g, zona, sigma_sd, fy_d)
            profundidade = g.lx / 2 - min(x for x, _ in zona)
            if profundidade >= g.m:
                t_min = max(t_min, n0_lam * math.sqrt(2 * sigma_sd / fy_d))
            v_atrito = min(e.mu * axial / c.a2, tau_rd * g.lx * g.ly)
            texto_t = (
                f"σ_c,Sd = {_n(sigma_sd)} MPa só na zona comprimida: {texto_zona_t}; {texto_zona}"
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
                # ℓ_c: a maior profundidade da zona em ℓx, a faixa sob pressão
                profundidade = g.lx / 2 - min(x for x, _ in obliqua.zona)
                t_min1, texto_zona_t = espessura_pela_zona(g, obliqua.zona, sigma_rd, fy_d)
                if caso == "C3" and profundidade >= g.m:  # o λ·n₀ da 6.7 (entre as mesas)
                    t_min1 = max(t_min1, n0_lam * math.sqrt(2 * sigma_rd / fy_d))
                t_min2, texto_tracao = _espessura_pela_tracao(g, obliqua.forcas, fy_d)
                t_min = max(t_min1, t_min2)
                v_atrito = min(e.mu * sigma_rd * obliqua.area / c.a2, tau_rd * g.lx * g.ly)
                texto_t = (
                    f"maior entre a pressão na zona comprimida, t_p,min1 = {_n(t_min1, 1)} mm "
                    f"({texto_zona_t}), e a flexão pela tração ({texto_tracao}); {texto_zona}"
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
        contas["compressao"] = (l_max, sigma_sd, g.lx)
        t_min = l_max * math.sqrt(2 * sigma_sd / fy_d)
        v_atrito = min(e.mu * sigma_sd * g.lx * g.ly / c.a2, tau_rd * g.lx * g.ly)
        l_c = g.lx
        texto_t = (
            f"t_p,min = ℓ_max·√(2·σ_c,Sd/(f_y/γ_a1)), ℓ_max = máx(m; n; λ·n₀) = {_n(l_max, 1)} mm"
        )
    elif caso == "C2":
        l_c = g.lx - 2 * momento / axial
        sigma_sd = axial / (l_c * g.ly)
        l_max = balanco_sob_pressao(g, l_c, caso, n0_lam)
        contas["compressao"] = (l_max, sigma_sd, l_c)
        t_min = l_max * math.sqrt(2 * sigma_sd / fy_d)
        v_atrito = min(e.mu * sigma_sd * l_c * g.ly / c.a2, tau_rd * g.lx * g.ly)
        texto_t = (
            f"t_p,min = ℓ_max·√(2·σ_c,Sd/(f_y/γ_a1)), ℓ_c = ℓx − 2e = {_n(l_c, 1)} mm, "
            f"ℓ_max = {_n(l_max, 1)} mm (máx(m; n; λ·n₀) = {_n(max(g.m, g.n, n0_lam), 1)} mm; com "
            "ℓ_c menor que m ou n, o balanço vira √(ℓ_c·(2·balanço − ℓ_c)), AISC DG1 3.3)"
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
            l_max = balanco_sob_pressao(g, l_c, caso, n0_lam)
            t_min1 = l_max * math.sqrt(2 * sigma_rd / fy_d)
            t_min2, texto_tracao = _espessura_pela_tracao(g, forcas_gerais, fy_d)
            t_min = max(t_min1, t_min2)
            v_atrito = min(e.mu * sigma_rd * l_c * g.ly / c.a2, tau_rd * g.lx * g.ly)
            texto_t = (
                f"maior entre t_p,min1 = ℓ_max·√(2·σ_c,Rd/(f_y/γ_a1)) = {_n(t_min1, 1)} mm "
                f"(ℓ_max = {_n(l_max, 1)} mm; com ℓ_c menor que m ou n, o balanço vira √(ℓ_c·(2·balanço − ℓ_c)), AISC DG1 3.3) e a flexão pela tração ({texto_tracao}); "
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
            l_max = balanco_sob_pressao(g, l_c, caso, n0_lam)
            t_min1 = l_max * math.sqrt(2 * sigma_rd / fy_d)
            t_min2 = math.sqrt(2 * n_b * f_t * (g.m - g.a1) / (g.ly * fy_d)) if g.m > g.a1 else 0.0
            t45, texto45 = espessura_a_45_graus(g, tuple(forcas), fy_d)
            t_min = max(t_min1, t_min2, t45)
            contas["pressao_rd"] = (l_max, l_c)
            contas["linha"] = f_t
            v_atrito = min(e.mu * sigma_rd * l_c * g.ly / c.a2, tau_rd * g.lx * g.ly)
            texto_t = (
                f"maior entre t_p,min1 = ℓ_max·√(2·σ_c,Rd/(f_y/γ_a1)) = {_n(t_min1, 1)} mm "
                f"(ℓ_max = {_n(l_max, 1)} mm; com ℓ_c menor que m ou n, o balanço vira √(ℓ_c·(2·balanço − ℓ_c)), AISC DG1 3.3), t_p,min2 = √(2·n_b·F_t,Sd·(m − a₁)/(ℓy·f_y/γ_a1)) "
                f"= {_n(t_min2, 1)} mm (a linha inteira na largura ℓy, m − a₁ = {_n(g.m - g.a1, 1)} mm)"
                + (f" e a flexão {texto45}" if t45 > 0 else "")
                + f"; ℓ_c = {_n(l_c, 1)} mm"
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
            t_linha = math.sqrt(2 * n_b * f_t * (g.m - g.a1) / (g.ly * fy_d)) if g.m > g.a1 else 0.0
            contas["linha"] = f_t
            t45, texto45 = espessura_a_45_graus(g, tuple(forcas), fy_d)
            t_min = max(t_linha, t45)
            texto_t = (
                f"maior entre t_p,min = √(2·n_b·F_t,Sd·(m − a₁)/(ℓy·(f_y/γ_a1))) = {_n(t_linha, 1)} mm "
                f"(base tipo 1, a linha inteira na largura ℓy; F_t,Sd = {_n(f_t / 1e3, 2)} kN, m − a₁ "
                f"= {_n(g.m - g.a1, 1)} mm)" + (f" e a flexão {texto45}" if t45 > 0 else "")
            )
        else:
            assert g.l0 is not None
            t_min = math.sqrt(n_b * f_t * max(g.a2 - g.t_w, 0.0) / (g.l0 * fy_d))
            texto_t = "t_p,min = √(n_b·F_t,Sd·(a₂ − t_w)/(ℓ₀·(f_y/γ_a1))) (base tipo 2)"
        v_atrito = 0.0  # sem pressão de contato, sem atrito (6.7.2.3)
    contas["t_min"] = t_min
    if (dist or obliqua) and zona:
        contas["zona"] = (
            "q = ∫ p(u)·u du por unidade de largura. t_faixa = √(4·q_máx/f_yd).",
            texto_t,
        )
    # Passagem dos eixos de solução (momentos positivos) aos eixos da placa.
    sx = -1 if e.m_sd_kNm < 0 else 1
    sy = -1 if e.m_sd_y_kNm < 0 else 1
    if not zona and l_c and dist is None and obliqua is None:
        x0, x1 = g.lx / 2 - l_c, g.lx / 2
        zona = ((x0, -g.ly / 2), (x1, -g.ly / 2), (x1, g.ly / 2), (x0, g.ly / 2))
    zona = tuple((sx * x, sy * y) for x, y in zona)
    if sx * sy < 0:
        zona = zona[::-1]
    mapa = {(sx * x, sy * y): f for (x, y), f in zip(g.posicoes, forcas, strict=True)}
    forcas = [mapa[p] for p in g.posicoes]
    g = replace(g, y_dorso=g.y_dorso * sy)
    w0, ax, ay = dist.plano if dist else (sigma_sd if sigma_sd is not None else sigma_rd, 0, 0)
    plano_pressao = (w0, ax * sx, ay * sy)
    a, s1, s2, i11, i12, i22 = _momentos_do_poligono(list(zona))
    w0, ax, ay = plano_pressao
    comp = w0 * a + ax * s1 + ay * s2
    m1 = w0 * s1 + ax * i11 + ay * i12
    m2 = w0 * s2 + ax * i12 + ay * i22
    centro_pressao = (m1 / comp, m2 / comp) if comp > 1e-8 else None
    rn = (comp - sum(forcas) - axial) / 1000
    rm1 = (
        m1 - sum(f * x for f, (x, _) in zip(forcas, g.posicoes, strict=True)) - sx * momento
    ) / 1e6
    rm2 = (
        m2 - sum(f * y for f, (_, y) in zip(forcas, g.posicoes, strict=True)) - sy * momento_y
    ) / 1e6
    tol_n = 1e-7 * max(1.0, abs(axial) / 1000, comp / 1000)
    tol_m = 1e-7 * max(1.0, momento / 1e6, momento_y / 1e6, comp * max(g.lx, g.ly) / 1e6)
    linhas.append(
        _limite(
            "Equilíbrio dos esforços aplicados",
            abs(rn) <= tol_n and max(abs(rm1), abs(rm2)) <= tol_m,
            "Integração da pressão e forças individuais nos eixos da placa",
            f"A_c = {_n(a, 2)} mm², C = {_n(comp / 1000, 4)} kN. "
            f"R_N = {_n(rn, 7)} kN, R_M = {_n(rm1, 8)} e R_M,y = {_n(rm2, 8)} kN·m. "
            "Momentos positivos comprimem x e y positivos, respectivamente.",
        )
    )
    item_caso = {"C1": "a", "C2": "b", "C3": "c", "T1": "d", "T2": "e", "T3": "f"}[caso]
    ref_caso = f"{REF} 6.7.2.2 {item_caso})"
    if obliqua is not None:
        ref_caso = f"{REF} 6.7.2.2 {item_caso}) e 6.7.1.1 (flexão oblíqua)"
    if dist is not None:
        if axial > 0:
            indice = 6 * (momento / g.lx + momento_y / g.ly) / axial
            linhas.append(
                _info(
                    "Núcleo central no modelo linear",
                    f"6|e_x|/ℓx + 6|e_y|/ℓy = {_n(indice, 4)}. "
                    + ("Contato integral." if indice <= 1 else "Contato parcial."),
                )
            )
        ref_caso = f"método elástico da placa rígida ({REF} 6.7.1.1)"
    # ------------------------------------------------------------------ concreto e placa
    if dist is not None and sigma_sd is not None:
        linhas.append(
            Verificacao(
                "Concreto: pressão de contato σ_c,Sd ≤ σ_c,Rd",
                sigma_sd,
                sigma_rd,
                "MPa",
                ref_cc,
                f"σ_c,Sd = σ_máx da distribuição linear elástica = {_n(sigma_sd)} MPa, zona "
                f"comprimida A_c = {_n(_momentos_do_poligono(list(zona))[0] / 100, 0)} cm², "
                f"resultante C = {_n(dist.compressao / 1e3, 1)} kN; {texto_sigma} (se não passa, "
                "aumentar a placa ou o bloco)",
            )  # fmt: skip
        )
    elif sigma_sd is not None and obliqua is not None:
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
    proxima = next((t for t in ESPESSURAS_COMERCIAIS if t >= t_min - 1e-9), None)
    sugestao = ""
    if t_min > e.t_placa_mm * (1 + 1e-9):
        sugestao = f"; t_p,min = {_n(t_min, 2)} mm > t_p = {_n(e.t_placa_mm, 2)} mm: " + (
            f"a chapa comercial seguinte é {_n(proxima, 1)} mm"
            if proxima is not None
            else "acima das chapas comerciais, refaça a base"
        )
    linhas.append(
        Verificacao(
            "Placa de base: espessura t_p ≥ t_p,min",
            t_min,
            e.t_placa_mm,
            "mm",
            ref_caso,
            f"{texto_t}; f_y = {_n(fy, 0)} MPa ({e.aco_placa}), γ_a1 = {_n(c.a1)}{sugestao}"
            + (
                f". Aproveitamento em espessura t_p,min/t_p = {_n(100 * t_min / e.t_placa_mm, 0)} %; "
                f"em momento resistente (∝ t²), (t_p,min/t_p)² = "
                f"{_n(100 * (t_min / e.t_placa_mm) ** 2, 0)} % (o indicador da tabela é o de espessura)"
                if 0 < t_min
                else ""
            ),
        )  # fmt: skip
    )
    if zona and e.graute_rd_MPa:
        pico = max(w0 + ax * x + ay * y for x, y in zona)
        linhas.append(
            Verificacao(
                "Compressão no graute",
                pico,
                e.graute_rd_MPa,
                "MPa",
                "Resistência de cálculo informada",
                "Pico de pressão na superfície de contato.",
            )
        )
    elif zona and e.modo_bloco == "verificacao":
        linhas.append(
            _alerta(
                "Compressão no graute",
                "Material da obra",
                "Informar a resistência de cálculo do graute.",
            )
        )
    # ------------------------------------------------------------------ chumbadores
    inicios.append((GRUPO_CHUMBADORES, len(linhas)))
    medidas: MedidasPorFormula | None = None
    if e.por_formula:  # o embutimento sai do cone, agora que as forças são conhecidas
        h_ef = e.h_ef_mm or embutimento_pelo_cone(e, g, tab, tuple(forcas))
        medidas = medidas_por_formula(e, h_ef)
        tab = medidas.linha
        linhas.append(
            _info(
                "Chumbador fora da Tabela 18 (por fórmula)",
                f"Ø {tab.polegada}: furo, arruela, distâncias, embutimento e concreto calculados "
                "(porca ASME B18.2.6; furo e arruela AISC; a₂ e a₃ ACI 318-19 17.9.2; h_ef pelo "
                "cone; f_ck NBR 6118) e a ancoragem no concreto verificada pela ACI 318-19",
                f"{REF} 6.7.1.1",
            )
        )
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
        rosca = medidas.rosca if medidas is not None else None
        if rosca is not None and rosca.area_resistente < 0.75 * rosca.area_bruta:
            # rosca grossa em diâmetro pequeno: a área da rosca fica abaixo dos 0,75·A_b da norma
            linhas.append(
                Verificacao(
                    "Rosca: tração na área resistente A_s",
                    f_t / 1e3,
                    rosca.area_resistente * aco_ch.f_u / c.a2 / 1e3,
                    "kN",
                    "ASME B1.1 / ISO 898-1",
                    f"F_t,Rd = A_s·f_ub/γ_a2 = {_n(rosca.area_resistente, 0)} × "
                    f"{_n(aco_ch.f_u, 0)}/{_n(c.a2)}; A_s = {_n(rosca.area_resistente, 0)} mm² "
                    f"< 0,75·A_b = {_n(0.75 * rosca.area_bruta, 0)} mm² (a área que a fórmula de "
                    "d_b,min supõe)",
                )
            )
    linhas_ancoragem, avisos_ancoragem = verificar_ancoragem(e, g, tab, tuple(forcas))
    linhas.extend(linhas_ancoragem)
    avisos.extend(avisos_ancoragem)
    # ------------------------------------------------------------------ cortante
    inicios.append((GRUPO_CORTANTE, len(linhas)))
    v_rd = v_atrito
    modo_v = e.cortante
    if caso.startswith("T"):
        v_rd = 0.0
    if modo_v == CORTANTE_AUTO:
        modo_v = CORTANTE_DIRETOS if v_sd > v_rd or e.mz_kNm else CORTANTE_ATRITO
        linhas.append(_info("Mecanismo automático de cortante", CORTANTES[modo_v]))
    if e.mz_kNm:
        linhas.append(
            _alerta(
                "Torção na transferência ao concreto",
                "Modelo do dispositivo de cortante",
                f"M_z = {_n(e.mz_kNm)} kN·m. Verificar a distribuição torsional no dispositivo e no concreto.",
            )
        )
    if modo_v == CORTANTE_PLACA and (
        e.vy_kN or (e.vx_kN is None and v_sd > 0 and e.modo_bloco == "verificacao")
    ):
        linhas.append(
            _alerta(
                "Orientação da placa de cisalhamento",
                "Geometria do dispositivo",
                "A placa resiste normal à sua face (ℓx). Verificar a componente paralela e a orientação real.",
            )
        )
    if modo_v == CORTANTE_ATRITO:
        if v_rd <= 0:  # T1 e T2 (ou C3/T3 sem equilíbrio): não há pressão de contato, nem atrito
            texto_v = (
                f"V_Sd = {_n(v_sd / 1e3, 1)} kN sem pressão de contato sob a placa: não há atrito; "
                "a cortante precisa de placa de cisalhamento ou de arruelas soldadas (ou, com "
                "aviso, dos chumbadores direto no furo)"
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
            if dist is not None:
                texto_v = (
                    f"V_Rd = μ·C/γ_a2 ≤ τ_c,Rd·ℓx·ℓy, C = {_n(dist.compressao / 1e3, 1)} kN (a "
                    f"resultante da pressão elástica), μ = {_n(e.mu)}, τ_c,Rd = 0,2·f_ck/γ_c ≤ 4 MPa "
                    f"= {_n(tau_rd)} MPa"
                )
            linhas.append(Verificacao("Cortante: atrito na argamassa", v_sd / 1e3, v_rd / 1e3, "kN", ref_caso, texto_v))  # fmt: skip
        if v_sd > v_rd + 1e-6:
            avisos.append(
                "O atrito é insuficiente para a cortante de cálculo. Sem compressão admissível não há atrito."
            )
    elif modo_v == CORTANTE_PLACA:
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
        v_rd_placa = v_rd
        if ancoragem_verificada(e):
            frente = ruptura_a_frente_da_placa_de_cisalhamento(e, g, tab, v_sd)
            if frente is not None:
                linhas.append(
                    Verificacao(
                        LINHA_FRENTE_DA_PLACA,
                        frente[0] / 1e3,
                        frente[1] / 1e3,
                        "kN",
                        f"ACI 318-19 17.11.3 {sd.MARCA_A_CONFIRMAR}",
                        frente[2],
                    )
                )
    else:  # pelos chumbadores: arruelas soldadas ou direto no furo da placa
        soldadas = modo_v == CORTANTE_ARRUELAS
        razoes_v: list[tuple[str, float]] = []
        if soldadas:
            arruelas = cortante_das_arruelas(
                tab.d_b, tab.lado_da_arruela, g.t_arruela, e.t_placa_mm, tuple(forcas), aco_ch.f_u,
                fy, c, sigma_rd,
            )  # fmt: skip
            v_rd, f_v, alfa = arruelas.v_rd, arruelas.f_v, arruelas.alfa
            f_v_barra, f_v_contato, l_f = arruelas.f_v_barra, arruelas.f_v_contato, arruelas.l_f
        if soldadas:
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
            razoes_v.append(("aço e contato, 6.7.2.5", v_sd / v_rd if v_rd > 0 else math.inf))
        elif v_sd > 0 or e.mz_kNm:
            folga = max(tab.d_f - tab.d_b, 0.0) / 2
            contados = engatados_sem_arruela(n_b)
            linhas.append(
                _alerta(
                    "Chumbadores direto no furo: deslizamento antes do contato",
                    f"{REF} 6.7.2.3 e AISC Design Guide 1",
                    f"furo d_f = {_n(tab.d_f, 1)} mm com chumbador d_b = {_n(tab.d_b, 2)} mm: a placa "
                    f"desliza até (d_f − d_b)/2 = {_n(folga, 1)} mm antes de encostar, e os "
                    f"chumbadores engatam um a um (só {contados} de {n_b} contado"
                    f"{'s' if contados > 1 else ''}). A norma e o Design Guide 1 pedem "
                    "um dispositivo positivo: arruelas soldadas com furo justo ou placa de "
                    "cisalhamento. O atrito não se soma aos chumbadores (ele age antes do "
                    "deslizamento, eles só depois)",
                )
            )
            if e.folga_servico_mm is not None:
                linhas[-1] = _limite(
                    linhas[-1].nome,
                    folga <= e.folga_servico_mm,
                    linhas[-1].referencia,
                    linhas[-1].formula
                    + f". Limite admissível de serviço: {_n(e.folga_servico_mm)} mm.",
                )
            avisos.append(
                f"Cortante pelos chumbadores direto no furo da placa: a placa desliza até "
                f"{_n(folga, 1)} mm antes do contato e só {contados} de {n_b} chumbadores "
                "foram contados (engate desigual). Prefira arruelas soldadas (furo d_b + 1,5 mm) ou placa de cisalhamento "
                "(6.7.2.3); registre a hipótese no memorial."
            )
        # aço do chumbador à cortante e à flexão na argamassa (ACI 318-19 17.7.1; DG1)
        n_eng = n_b if soldadas else engatados_sem_arruela(n_b)
        v_i = v_sd / n_eng
        cortes = (v_i,) * n_b
        if soldadas and e.mz_kNm:
            # As disposições são centradas na origem da placa e os chumbadores têm a mesma rigidez.
            polar = sum(x * x + y * y for x, y in g.posicoes)
            k_t = e.mz_kNm * 1e6 / polar
            if e.vx_kN is None and e.vy_kN is None:
                cortes = tuple(v_i + abs(k_t) * math.hypot(x, y) for x, y in g.posicoes)
            else:
                vx_i = (e.vx_kN or 0) * 1000 / n_b
                vy_i = (e.vy_kN or 0) * 1000 / n_b
                cortes = tuple(math.hypot(vx_i - k_t * y, vy_i + k_t * x) for x, y in g.posicoes)
            v_i = max(cortes)
            for i, (solicitacao, tracao) in enumerate(zip(cortes, forcas, strict=True), 1):
                capacidade = cortante_das_arruelas(
                    tab.d_b,
                    tab.lado_da_arruela,
                    g.t_arruela,
                    e.t_placa_mm,
                    (tracao,),
                    aco_ch.f_u,
                    fy,
                    c,
                    sigma_rd,
                ).v_rd
                linhas.append(
                    Verificacao(
                        f"Arruela {i}: translação e torção",
                        solicitacao / 1000,
                        capacidade / 1000,
                        "kN",
                        f"{REF} 6.7.2.5 e equilíbrio do grupo",
                        "V_i = |V/n + M_z·(−y_i, x_i)/Σr²|. Com direção desconhecida, soma dos módulos.",
                    )
                )
                razoes_v.append(
                    (f"arruela {i}", solicitacao / capacidade if capacidade else math.inf)
                )
        if not soldadas and v_sd:
            borda = min(min(g.lx / 2 - abs(x), g.ly / 2 - abs(y)) for x, y in g.posicoes)
            passo_real = min(math.dist(a, b) for a, b in combinations(g.posicoes, 2))
            lf = max(0.0, min(borda - tab.d_f / 2, passo_real - tab.d_f))
            k1, k2 = coeficientes_contato()
            fu_placa = ACOS[e.aco_placa][1]
            for nome, fator in (
                ("Rasgamento da placa no furo", k1 * lf),
                ("Esmagamento da placa no furo", k2 * tab.d_b),
            ):
                linhas.append(
                    Verificacao(
                        nome,
                        v_i / 1000,
                        fator * e.t_placa_mm * fu_placa / c.a2 / 1000,
                        "kN",
                        f"{REF} 6.3.3.3",
                        f"ℓ_f = {_n(lf)} mm, f_u = {_n(fu_placa)} MPa.",
                    )
                )
        f_ut = f_uta(aco_ch)
        aco_v = (PHI_ACO_CORTANTE if e.aco_ductil else 0.60) * 0.6 * a_se * f_ut * FATOR_ARGAMASSA
        engate = f"V_Sd/n = {_n(v_sd / 1e3, 1)}/{n_eng} = {_n(v_i / 1e3, 2)} kN por chumbador " + (
            "(os n engatam juntos: furo justo da arruela)"
            if soldadas
            else f"(engate desigual: só {n_eng} de {n_b})"
        )
        if soldadas and e.mz_kNm:
            engate = (
                f"Translação e torção nos {n_eng} chumbadores. V_i,máx = {_n(v_i / 1000, 2)} kN"
            )
        linhas.append(
            Verificacao(
                "Chumbador: aço à cortante (ACI 318-19)",
                v_i / 1e3,
                aco_v / 1e3,
                "kN",
                "ACI 318-19 17.7.1.2 e 17.7.1.2.1",
                f"{engate}; φ·V_sa = {_n(0.65 if e.aco_ductil else 0.60)} × 0,6·A_se·f_uta × 0,80 = {_n(0.65 if e.aco_ductil else 0.60)} × 0,6 × {_n(a_se, 0)} × "
                f"{_n(f_ut, 0)} × 0,80 (0,80 pela argamassa de assentamento, 17.7.1.2.1; f_uta = "
                f"mín(f_u; 1,9·f_y; 862 MPa))",
            )
        )
        razoes_v.append(("aço do chumbador, 17.7.1", v_i / aco_v if aco_v > 0 else math.inf))
        contas["cortante_aco"] = (v_i, n_eng, f_ut)
        if v_i > 0:
            acrescimo = tab.d_b / 2 + ((e.t_placa_mm + g.t_arruela) / 2 if soldadas else 0.0)
            flexoes = (
                flexao_na_argamassa(
                    vi * n_eng,
                    n_eng,
                    ft,
                    g.e_n,
                    e.t_placa_mm,
                    a_se,
                    aco_ch.f_y,
                    c.a1,
                    acrescimo_mm=acrescimo,
                )
                for vi, ft in zip(cortes, forcas, strict=True)
            )
            flexao = max(flexoes, key=lambda fl: fl.sigma)
            contas["flexao"] = flexao
            linhas.append(
                Verificacao(
                    LINHA_FLEXAO_NA_ARGAMASSA,
                    flexao.sigma,
                    flexao.limite,
                    "MPa",
                    "Braço conforme EN 1992-4 §6.2.2.3, α_M = 1, a₃ = d_b/2. Resistência da barra pela NBR 8800 5.4.2.2",
                    flexao.texto(),
                )
            )
        if not soldadas:
            v_rd = n_eng * aco_v
        if ancoragem_verificada(e):
            for nome, conta, ref_aci in (
                (LINHA_RUPTURA_DA_BORDA, ruptura_da_borda_por_cortante, "17.7.2"),
                (LINHA_ALAVANCA, arrancamento_por_alavanca, "17.7.3"),
            ):
                valor = conta(e, g, tab, v_sd)
                if valor is None:
                    if nome == LINHA_ALAVANCA and v_sd > 0 and e.ancoragem == ANCORAGEM_QUIMICO:
                        linhas.append(
                            _alerta(
                                nome,
                                "ACI 318-19 17.7.3",
                                "Inconclusivo. Faltam os dados de aderência da resina para o grupo mobilizado.",
                            )
                        )
                    continue
                linhas.append(
                    Verificacao(
                        nome,
                        valor[0] / 1e3,
                        valor[1] / 1e3,
                        "kN",
                        f"ACI 318-19 {ref_aci}",
                        valor[2],
                    )
                )
                razoes_v.append((ref_aci, valor[0] / valor[1] if valor[1] > 0 else math.inf))
            if f_t > 0 and v_i > 0:  # com tração nos chumbadores, a 17.8 é obrigatória
                aco_t = 0.75 * math.pi * tab.d_b**2 / 4 * aco_ch.f_u / c.a2
                razoes_n = [("aço", f_t / aco_t)]
                razoes_n += [
                    (v.referencia.removeprefix("ACI 318-19 "), v.aproveitamento)
                    for v in linhas_ancoragem
                    if v.nome in LINHAS_DE_TRACAO_ACI and v.aproveitamento is not None
                ]
                texto_n, r_n = max(razoes_n, key=lambda par: par[1])
                texto_v, r_v = max(razoes_v, key=lambda par: par[1])
                linhas.append(interacao_tracao_cortante(r_n, r_v, texto_n, texto_v))
    # ------------------------------------------------------------------ soldas
    inicios.append((GRUPO_SOLDAS, len(linhas)))
    solda = bs.solda_do_pilar(
        d=g.d,
        b_f=g.b_f,
        t_w=g.t_w,
        t_f=g.t_f,
        t_placa=e.t_placa_mm,
        aco_pilar=ACOS[e.aco_pilar],
        axial=axial,
        momento=sx * momento,
        momento_y=sy * momento_y,
        cortante=v_sd,
        vx=e.vx_kN * 1000 if e.vx_kN is not None else None,
        vy=e.vy_kN * 1000 if e.vy_kN is not None else None,
        mz=e.mz_kNm * 1e6,
        aco_placa=ACOS[e.aco_placa],
        perna_informada=e.perna_pilar_mm,
        eletrodo=e.eletrodo,
        mesas_por_dentro=e.solda_mesas_por_dentro,
        alma=e.solda_alma,
        contato=e.compressao_por_contato,
        c=c,
        y_dorso=g.y_dorso if g.e_u else None,  # o U: contorno e centro do grupo próprios
    )
    linhas.extend(solda.linhas)
    if e.cortante == CORTANTE_PLACA:
        _, linhas_lug = bs.solda_da_placa_de_cisalhamento(
            v_rd=v_rd_placa,
            momento=m_solda,
            t_pv=e.t_pv_mm,
            b_h=e.b_h_mm,
            t_placa=e.t_placa_mm,
            perna_informada=e.perna_cisalhamento_mm,
            eletrodo=e.eletrodo,
            c=c,
            penetracao_total=e.cisalhamento_penetracao_total,
        )
        linhas.extend(linhas_lug)
        if any(v.status == "NÃO OK" for v in linhas_lug):
            avisos.append(
                "Os filetes da placa de cisalhamento não levam a cortante e o momento dela: a "
                "6.7.2.4 dimensiona a solda pela resistência da placa. Use solda de penetração "
                "total (marque a opção) ou uma placa de cisalhamento menos alta (b_v)."
            )
    if any(v.status == "NÃO OK" for v in solda.linhas[:2]):
        avisos.append(
            (
                "A solda de filete do pilar na placa não passa com a perna informada: deixe a "
                "perna em 0 (automática) para o programa achar a que passa, ou "
                if e.perna_pilar_mm
                else "A solda de filete do pilar na placa não passa nem com a maior perna que cabe "
                "na mesa: "
            )
            + "solde as mesas com penetração total (resistência igual à da mesa), use um perfil "
            "com mesas mais grossas ou marque a compressão por contato, se a extremidade do pilar "
            "for faceada."
        )
    if modo_v == CORTANTE_ARRUELAS:
        _, linhas_arruela = bs.solda_das_arruelas(
            f_v=f_v,
            lado=tab.lado_da_arruela,
            t_arruela=g.t_arruela,
            t_placa=e.t_placa_mm,
            perna_informada=e.perna_arruela_mm,
            eletrodo=e.eletrodo,
            c=c,
        )
        linhas.extend(linhas_arruela)
    if f_t:
        d_in = tab.d_b + FOLGA_DO_FURO_DA_ARRUELA
        balanco = max(0.0, (tab.d_f - d_in) / 2)
        q_arr = f_t * balanco / (math.pi * d_in)
        linhas.append(
            Verificacao(
                "Arruela: flexão sobre o furo da placa",
                q_arr,
                (345 / c.a1) * g.t_arruela**2 / 6,
                "N·mm/mm",
                "Faixas radiais elásticas",
                f"Reação uniformemente distribuída no perímetro interno. F_t·(d_f − d_in)/(2π·d_in), balanço {_n(balanco)} mm. Resistência f_yd·t_a²/6.",
            )
        )
    # ------------------------------------------------------------------ disposições construtivas
    ref_18 = f"{REF} Tabela 18"
    ref_formula = "por fórmula"
    inicios.append((GRUPO_CONSTRUTIVAS_FORMULA if medidas else GRUPO_CONSTRUTIVAS, len(linhas)))
    espacamento = min(math.dist(a, b) for a, b in combinations(g.posicoes, 2))
    borda_placa = min(min(g.lx / 2 - abs(x), g.ly / 2 - abs(y)) for x, y in g.posicoes)
    # disposições construtivas: limites (OK ou NÃO OK), não aproveitamento
    if medidas is not None:
        linhas.append(
            _limite(
                "Distância a₁ (furo à borda da placa)",
                borda_placa >= tab.a1 - 1e-9,
                f"{ref_formula} (Tabela 18 e AISC)",
                f"borda efetiva = {_n(borda_placa, 1)} mm ≥ {_n(tab.a1, 0)} mm, o mínimo calculado para Ø "
                f"{tab.polegada}: máx(a₂/2; arruela/2; d_f/2 + 6,4 mm)",
            )
        )
        linhas.append(
            _limite(
                "Espaçamento a₂ entre chumbadores",
                espacamento >= tab.a2 - 1e-9,
                "ACI 318-19 17.9.2",
                f"s_real = {_n(espacamento, 1)} mm ≥ {_n(tab.a2, 0)} mm = máx({_mm(ESPACAMENTO_ACI[e.ancoragem])}"
                f"·d_b; lado da arruela) para Ø {tab.polegada}",
            )
        )
    else:
        linhas.append(
            _limite(
                "Distância a₁ (furo à borda da placa)",
                borda_placa >= tab.a1 - 1e-9,
                ref_18,
                f"borda efetiva = {_n(borda_placa, 1)} mm ≥ {_n(tab.a1, 0)} mm para Ø {tab.polegada}",
            )  # fmt: skip
        )
        linhas.append(
            _limite(
                "Espaçamento a₂ entre chumbadores",
                espacamento >= tab.a2 - 1e-9,
                ref_18,
                f"s_real = {_n(espacamento, 1)} mm ≥ {_n(tab.a2, 0)} mm para Ø {tab.polegada}",
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
    if medidas is not None:
        linhas.append(
            _limite(
                "Concreto: f_ck ≥ 20 MPa",
                e.fck_MPa >= FCK_MIN_NBR_6118 - 1e-9,
                "NBR 6118:2014, Tabela 7.1",
                f"f_ck = {_n(e.fck_MPa, 0)} MPa ≥ {_n(FCK_MIN_NBR_6118, 0)} MPa, o mínimo do "
                "concreto armado (classe de agressividade I; II pede 25, III 30 e IV 40 MPa); o "
                "esmagamento junto à porca da ponta é o arrancamento da ACI 318-19 17.6.3",
            )
        )
        altura_porca = medidas.altura_da_porca
        linhas.append(
            _limite(
                "Argamassa: cabem a porca de nivelamento e a arruela",
                g.e_n >= altura_porca + g.t_arruela - 1e-9,
                "montagem (Tabela 18, nota d)",
                f"e_n = {_n(g.e_n, 0)} mm ≥ porca ({_n(altura_porca, 0)} mm) + arruela "
                f"({_n(g.t_arruela, 1)} mm) = {_n(altura_porca + g.t_arruela, 1)} mm",
            )
        )
    if furo_justo(e, tab):
        padrao = furo_padrao(tab.d_b)
        linhas.append(
            _info(
                "Furo justo na placa",
                f"d_f = {_n(tab.d_f, 1)} mm < furo padrão {_n(padrao, 0)} mm para Ø {tab.polegada} "
                "(furo alargado d_b + 8 mm da placa de base): o "
                f"deslizamento cai para {_n((tab.d_f - tab.d_b) / 2, 1)} mm, mas some a tolerância "
                "de locação dos chumbadores — o furo justo exige locação precisa (template ou "
                "gabarito de montagem). Alternativa: furo padrão + arruelas soldadas",
                "AISC Manual, Tabela 14-2; AISC Design Guide 1",
            )
        )
        avisos.append(
            f"Furo justo (d_f = {_n(tab.d_f, 1)} mm, padrão {_n(padrao, 0)} mm): exige locação precisa "
            "dos chumbadores, com template ou gabarito de montagem; alternativa: furo padrão + "
            "arruelas soldadas."
        )
    if medidas is None:  # a rosca acima do concreto (h₂ da Tabela 18) cabe a placa e as porcas?
        passo = passo_da_rosca(e, tab)
        acima = g.e_n + e.t_placa_mm + g.t_arruela + tab.d_b + FIOS_ALEM_DA_PORCA * passo
        linhas.append(
            _limite(
                "Rosca acima do concreto: cabem argamassa, placa, arruela e porca",
                tab.h2 >= acima - 1e-9,
                f"montagem ({ref_18}, h₂)",
                f"h₂ = {_n(tab.h2, 0)} mm ≥ e_n + t_p + t_arruela + porca + 3 fios = "
                f"{_n(g.e_n, 0)} + {_n(e.t_placa_mm, 1)} + {_n(g.t_arruela, 1)} + {_n(tab.d_b, 0)} + "
                f"3 × {_n(passo, 2)} = {_n(acima, 1)} mm (senão, encomende o chumbador com h₂ maior)",
            )
        )
    if medidas is None and e.ancoragem == ANCORAGEM_PORCA:  # nota b: f_ck,mín junto à porca
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
    if e.bloco_z_mm:
        linhas.append(
            _limite(
                "Altura do bloco para o embutimento",
                e.bloco_z_mm >= embutimento(e, tab),
                "Geometria",
                f"h_a = {_n(e.bloco_z_mm)} mm, h_ef = {_n(embutimento(e, tab))} mm.",
            )
        )
    if e.bloco_x_mm > 0 and e.bloco_y_mm > 0:
        a3_a1 = tab.a3 - tab.a1
        if medidas is not None:
            ref_bloco = "ACI 318-19 17.9.2 (a₃)"
        else:
            ref_bloco = f"{ref_18}, " + ("notas e e g" if e.tipo == TIPO_2 else "nota e")
        minimo_tabela = "" if medidas is not None else "N_b,mín; "
        valor_tabela = "" if medidas is not None else f"{_n(tab.n_b_min, 0)}; "
        linhas.append(
            _limite(
                "Bloco: N_b ao longo de ℓx",
                e.bloco_x_mm >= n_b_min + 2 * abs(e.desloc_x_mm) - 1e-9,
                ref_bloco,
                f"N_b = {_n(e.bloco_x_mm, 0)} mm ≥ máx({minimo_tabela}ℓx + 2·e_n; ℓx + 2·(a₃ − a₁)) "
                f"= máx({valor_tabela}{_n(g.lx + 2 * g.e_n, 0)}; {_n(g.lx + 2 * a3_a1, 0)}) "
                f"= {_n(n_b_min, 0)} mm, mais 2|Δx| = {_n(2 * abs(e.desloc_x_mm))} mm",
            )  # fmt: skip
        )
        linhas.append(
            _limite(
                "Bloco: B_b ao longo de ℓy",
                e.bloco_y_mm >= b_b_min + 2 * abs(e.desloc_y_mm) - 1e-9,
                ref_bloco,
                f"B_b = {_n(e.bloco_y_mm, 0)} mm ≥ máx(ℓy + 2·e_n; ℓy + 2·(a₃ − a₁)) = "
                f"máx({_n(g.ly + 2 * g.e_n, 0)}; {_n(g.ly + 2 * a3_a1, 0)}) = {_n(b_b_min, 0)} mm, mais 2|Δy| = {_n(2 * abs(e.desloc_y_mm))} mm",
            )  # fmt: skip
        )
    soldadas = e.cortante == CORTANTE_ARRUELAS
    arruelas_texto = (
        f"{tab.arruela} mm, espessura {_n(g.t_arruela, 1)} mm, aço com f_y = 345 MPa, furo "
        f"d_b + 1,5 = {_n(tab.d_b + FOLGA_DO_FURO_DA_ARRUELA, 1)} mm; uma também entre a placa "
        "e a porca de nivelamento; "
        + ("as de cima soldadas à placa (6.7.2.5)" if soldadas else "soltas (nota d)")
    )
    argamassa_texto = (
        f"e_n = {_n(g.e_n, 0)} mm; f_ck ≥ 2 × {_n(e.fck_MPa, 0)} = {_n(2 * e.fck_MPa, 0)} MPa "
        "(6.7.1.5 d)"
    )
    if medidas is not None:
        rosca = medidas.rosca
        detalhamento: tuple[tuple[str, str], ...] = (
            ("Placa", f"{_n(g.lx, 0)} × {_n(g.ly, 0)} × {_n(e.t_placa_mm, 1)} mm ({e.aco_placa})"),
            (
                "Chumbadores",
                f"{n_b} × Ø {rosca.nome} — d_b = {_mm(rosca.d_b)} mm, passo {_n(rosca.passo, 2)} mm, "
                f"rosca {rosca.serie}; {e.aco_chumbador}, porca sextavada pesada s = "
                f"{_mm(medidas.lado_da_porca)} mm — fora da Tabela 18, por fórmula",
            ),
            ("Disposição", TIPOS[e.tipo]),
            ("Furo na placa", f"d_f = {_mm(tab.d_f)} mm"),
            ("Ancoragem", _texto_da_ancoragem(e, tab)),
            ("Arruelas especiais", arruelas_texto),
            ("Argamassa expansiva", argamassa_texto),
            (
                "Barra de cada chumbador",
                f"{_mm(medidas.comprimento)} mm, {_n(medidas.massa_kg, 2)} kg; rosca de cima "
                f"r₁ = {_mm(tab.r1)} mm e de baixo r₂ = {_mm(tab.r2)} mm",
            ),
            (
                "Armadura do bloco",
                "pela NBR 6118 (a armadura mínima da nota h vale só para a Tabela 18)",
            ),
            (
                "Bloco mínimo",
                f"N_b ≥ {_n(n_b_min, 0)} mm ao longo de ℓx, B_b ≥ {_n(b_b_min, 0)} mm (chumbador "
                f"a a₃ = {_n(tab.a3, 0)} mm da face), altura ≥ h_ef + 100 = {_n(a_b_min, 0)} mm; "
                f"f_ck ≥ {_n(FCK_MIN_NBR_6118, 0)} MPa; dimensionado pela NBR 6118",
            ),
        )
    else:
        d_a = 0.5 * (embutimento(e, tab) - 0.5 * (tab.r2 + tab.d_b))  # nota h
        detalhamento = (
            ("Placa", f"{_n(g.lx, 0)} × {_n(g.ly, 0)} × {_n(e.t_placa_mm, 1)} mm ({e.aco_placa})"),
            (
                "Chumbadores",
                f"{n_b} × Ø {tab.polegada} ({_n(tab.d_b, 0)} mm), {e.aco_chumbador}, porca "
                "sextavada pesada",
            ),
            ("Disposição", TIPOS[e.tipo]),
            ("Furo na placa", f"d_f = {_n(tab.d_f, 0)} mm"),
            ("Ancoragem", _texto_da_ancoragem(e, tab)),
            ("Arruelas especiais", arruelas_texto),
            ("Argamassa expansiva", argamassa_texto),
            ("Barra de cada chumbador", _comprimento_da_barra(e, g, tab)),
            (
                "Armadura mínima do bloco",
                f"Ø {_n(tab.phi_armadura, 1)} mm a cada {_n(tab.s_armadura, 0)} mm; armadura vertical "
                f"a até d_a = ½·[h₁ − 0,5·(r₂ + d_b)] = {_n(d_a, 0)} mm dos chumbadores (nota h; "
                "mais longe, recalcular a armadura)",
            ),  # fmt: skip
            (
                "Bloco mínimo",
                f"N_b ≥ {_n(n_b_min, 0)} mm ao longo de ℓx, B_b ≥ {_n(b_b_min, 0)} mm, altura ≥ "
                f"máx(h₁ + 100; N_b) = {_n(a_b_min, 0)} mm; f_ck,mín = {_n(tab.fck_min, 0)} MPa; "
                "dimensionado pela NBR 6118 (nota e)",
            ),  # fmt: skip
        )
    if e.ancoragem in POS_INSTALADOS and not e.por_formula:
        detalhamento = tuple(
            (nome, valor) for nome, valor in detalhamento if nome != "Armadura mínima do bloco"
        )
        detalhamento += (
            (
                "Armadura do bloco",
                "Dimensionar no projeto de concreto para o sistema pós-instalado.",
            ),
        )
    detalhamento = (
        *detalhamento,
        (
            "Solda do pilar na placa",
            f"filete d_w = {_n(solda.perna, 0)} mm ({e.eletrodo}) "
            + (
                "em todo o contorno (mesas por fora e por dentro, os dois lados da alma)"
                if e.solda_mesas_por_dentro and e.solda_alma
                else "nas mesas por fora"
                + (" e por dentro" if e.solda_mesas_por_dentro else "")
                + (" e na alma" if e.solda_alma else "")
            )
            + ("; extremidade do pilar faceada (contato)" if e.compressao_por_contato else ""),
        ),
    )
    diametros: tuple[tuple[str, float | None, str], ...] = ()
    if medidas is not None:
        diametros = diametros_por_criterio(
            e, tuple(forcas), f_t, v_sd, c, aco_ch.f_u, fy, sigma_rd, tab
        )
    equacoes = _equacoes_da_base(
        e, g, contas, sigma_rd=sigma_rd, razao=razao, gc=gc, fy=fy, gama_a1=c.a1,
        gama_a2=c.a2, f_t=f_t, f_ub=aco_ch.f_u, a_se=a_se, axial=axial, forcas=tuple(forcas),
        d_min=d_min,
    )  # fmt: skip
    linhas = [replace(v, equacoes=equacoes[v.nome]) if v.nome in equacoes else v for v in linhas]
    if e.modo_bloco == "verificacao":
        linhas.append(
            _info(
                "Resistência global do bloco e fundação",
                "Verificação externa. O resultado da ligação pressupõe o bloco, sua armadura e seus apoios dimensionados no projeto de fundação.",
            )
        )
        if f_t > 0:
            linhas.append(
                _alerta(
                    "Efeito de alavanca na tração dos chumbadores",
                    "Compatibilidade da placa",
                    "A tração calculada parte da placa rígida. Conferir o acréscimo por prying na placa deformável.",
                )
            )
        if momento or momento_y:
            linhas.append(
                _info(
                    "Rigidez rotacional da base",
                    "Se o modelo global pressupõe engaste ou mola, confrontar a rigidez da ligação com a adotada no modelo.",
                )
            )
    if e.modo_bloco == "verificacao" and min(e.bloco_x_mm, e.bloco_y_mm, e.bloco_z_mm) == 0:
        for i, v in enumerate(linhas):
            if v.nome in (
                *LINHAS_DO_BLOCO,
                "Arrancamento lateral da cabeça junto à borda",
                "Aderência da resina no grupo",
                "Aderência individual da resina",
                "Produto: distância à borda",
                "Produto: espessura do concreto",
            ):
                linhas[i] = _alerta(
                    v.nome, v.referencia, "Inconclusivo. Informar as três dimensões reais do bloco."
                )
    if not e.por_formula and (
        e.ancoragem != ANCORAGEM_PORCA
        or not ACOS_CHUMBADOR[e.aco_chumbador].equivalente_a36
        or e.n_chumbadores not in range(4, 9)
        or g.e_u
    ):
        for i, v in enumerate(linhas):
            if v.referencia.startswith(ref_18) and v.nome.startswith(
                ("Bloco:", "Distância a₁", "Espaçamento a₂")
            ):
                linhas[i] = _info(
                    v.nome,
                    "Referência construtiva da Tabela 18. " + v.formula,
                    "Medidas de referência, fora do campo da Tabela 18",
                )
    if any(
        v.status == "ALERTA"
        and (
            v.nome.startswith(("Aderência", "Qualificação", "Geometria real"))
            or v.nome == LINHA_ALAVANCA
        )
        for v in linhas
    ):
        linhas = [
            _alerta(
                v.nome,
                v.referencia,
                "Inconclusivo. Faltam resistências de tração ou cortante para a interação.",
            )
            if v.nome == LINHA_INTERACAO and v.status == "OK"
            else v
            for v in linhas
        ]
    linhas = _invalidar_sem_equilibrio(linhas, inicios, avisos)
    if any(v.nome.startswith("Equilíbrio") and v.status == "NÃO OK" for v in linhas):
        zona, centro_pressao, l_c, sigma_sd = (), None, None, None
    fins = [inicio for _, inicio in inicios[1:]] + [len(linhas)]
    grupos = tuple(
        (nome, tuple(linhas[inicio:fim]))
        for (nome, inicio), fim in zip(inicios, fins, strict=True)
        if fim > inicio
    )
    return ResultadoBase(
        e, caso, g, sigma_rd, sigma_sd, l_c, f_t, tuple(forcas), t_min, d_min, v_rd,
        tuple(linhas), tuple(avisos), detalhamento, grupos, zona,
        disposicoes=tab, por_formula=medidas, diametros=diametros, perna_do_pilar=solda.perna,
        plano_pressao=plano_pressao, centro_pressao=centro_pressao, residuos=(rn,rm1,rm2),
    )  # fmt: skip


#: Grupos cujas contas dependem da pressão e das forças nos chumbadores do equilíbrio.
GRUPOS_DO_EQUILIBRIO = (GRUPO_CONCRETO_E_PLACA, GRUPO_CHUMBADORES, GRUPO_CORTANTE)
SEM_EQUILIBRIO = "Não validado: sem equilíbrio nesta combinação"
#: Linhas desses grupos que só usam N, V ou a geometria (valem com ou sem equilíbrio).
NAO_DEPENDEM_DO_EQUILIBRIO = (
    "Equilíbrio",
    "Fator X",
    "Chumbador: aço à cortante",
    "Cortante: placa de cisalhamento",
    "Cortante no concreto",
    "Rosca acima",
)


def _invalidar_sem_equilibrio(
    linhas: list[Verificacao], inicios: list[tuple[str, int]], avisos: list[str]
) -> list[Verificacao]:
    """Sem equilíbrio (a linha "Equilíbrio …" NÃO OK), a pressão, a espessura e as forças nos
    chumbadores não valem: as linhas que dependem delas saem NÃO OK, sem número, em vez de mostrar
    valores de uma solução que não existe (t_p,min = 0 "OK", por exemplo)."""
    if not any(v.nome.startswith("Equilíbrio") and v.status == "NÃO OK" for v in linhas):
        return linhas
    fins = [inicio for _, inicio in inicios[1:]] + [len(linhas)]
    dependentes = {
        i
        for (nome, inicio), fim in zip(inicios, fins, strict=True)
        if nome in GRUPOS_DO_EQUILIBRIO
        for i in range(inicio, fim)
    }
    saida = []
    for i, v in enumerate(linhas):
        if (
            i in dependentes
            # "Ancoragem no concreto: sem chumbador tracionado" vem das forças nulas
            and (
                v.status in ("OK", "NÃO OK")
                or v.nome in ("Ancoragem no concreto", "Concreto: pressão de contato")
            )
            and not v.nome.startswith(NAO_DEPENDEM_DO_EQUILIBRIO)
        ):
            v = replace(
                v,
                solicitante=None,
                resistente=None,
                status="NÃO OK",
                aproveitamento=None,
                tipo="limite",
                formula=f"{SEM_EQUILIBRIO}: o valor desta verificação depende da pressão e das "
                "forças nos chumbadores, que não existem sem equilíbrio",
                equacoes=(),
            )
        saida.append(v)
    avisos.append(
        "Sem equilíbrio em uma combinação: a pressão no concreto, a espessura da placa e as forças "
        "nos chumbadores dela não foram validadas (saem NÃO OK, sem número). Altere a ligação: "
        "placa maior, chumbadores mais afastados ou outra disposição."
    )
    return saida


def _pior_linha(par: tuple[CasoDeCarga, Verificacao]) -> tuple[int, float]:
    v = par[1]
    aproveitamento = v.aproveitamento if v.aproveitamento is not None else -1.0
    return ORDEM_STATUS.get(v.status, 0), aproveitamento


def _pior_resultado(par: ResultadoDoCaso) -> tuple[int, float]:
    r = par.resultado
    return ORDEM_STATUS.get(r.status, 0), r.aproveitamento_maximo


def _com_os_esforcos(e: EntradaBase, caso: CasoDeCarga) -> EntradaBase:
    return replace(
        e,
        casos=(),
        n_sd_kN=caso.n_sd_kN,
        m_sd_kNm=caso.m_sd_kNm,
        m_sd_y_kNm=caso.m_sd_y_kNm,
        v_sd_kN=caso.v_sd_kN,
        vx_kN=caso.vx_kN,
        vy_kN=caso.vy_kN,
        mz_kNm=caso.mz_kNm,
    )


def _envoltoria(e: EntradaBase) -> ResultadoBase:
    """Cada combinação pelo cálculo inteiro; em cada verificação, a mais desfavorável."""
    por_caso = [ResultadoDoCaso(c, _calcular_um(_com_os_esforcos(e, c))) for c in e.casos]
    if e.por_formula and not e.h_ef_mm:
        # o embutimento sai do cone de cada combinação: o chumbador é um só, o mais longo
        h_ef = max(r.resultado.linha.h1 for r in por_caso)
        if any(abs(r.resultado.linha.h1 - h_ef) > 1e-9 for r in por_caso):
            por_caso = [
                ResultadoDoCaso(c, _calcular_um(replace(_com_os_esforcos(e, c), h_ef_mm=h_ef)))
                for c in e.casos
            ]
    perna_automatica = not e.perna_pilar_mm
    if perna_automatica:
        # a solda do pilar é uma só: a perna que passa na combinação mais exigente vale em todas
        perna = max(r.resultado.perna_do_pilar for r in por_caso)
        if any(abs(r.resultado.perna_do_pilar - perna) > 1e-9 for r in por_caso):
            por_caso = [
                ResultadoDoCaso(
                    r.caso, _calcular_um(replace(r.resultado.entrada, perna_pilar_mm=perna))
                )  # fmt: skip
                for r in por_caso
            ]
    governa = max(por_caso, key=_pior_resultado)
    grupos: list[tuple[str, tuple[Verificacao, ...]]] = []
    for nome_grupo in ORDEM_DOS_GRUPOS:
        por_nome: dict[str, list[tuple[CasoDeCarga, Verificacao]]] = {}
        for item in por_caso:
            for nome, linhas_g in item.resultado.grupos:
                if nome != nome_grupo:
                    continue
                for v in linhas_g:
                    if perna_automatica and v.nome.startswith("Solda do pilar"):
                        v = replace(
                            v,
                            formula=v.formula.replace(
                                "(informada)", "(automática: a que passa em todas as combinações)"
                            ),
                        )
                    por_nome.setdefault(v.nome, []).append((item.caso, v))
        linhas: list[Verificacao] = []
        algum_tracionado = any(i.resultado.f_t_sd > 0 for i in por_caso)
        for nome_linha, pares in por_nome.items():
            if nome_linha == "Ancoragem no concreto" and algum_tracionado:
                continue  # "sem chumbador tracionado" de uma combinação não vale para a base
            caso, pior = max(pares, key=_pior_linha)
            iguais = all(
                (v.solicitante, v.resistente, v.status)
                == (pior.solicitante, pior.resistente, pior.status)  # fmt: skip
                for _, v in pares
            )
            if iguais and len(pares) == len(por_caso):
                linhas.append(pior)
            else:
                linhas.append(replace(pior, formula=f"[{caso.nome}] {pior.formula}"))
        if linhas:
            grupos.append((nome_grupo, tuple(linhas)))
    todas = tuple(v for _, linhas_g in grupos for v in linhas_g)
    avisos: list[str] = []
    for item in por_caso:
        for aviso in item.resultado.avisos:
            if aviso not in avisos:
                avisos.append(aviso)
    comprimidas = [c.nome for c in e.casos if c.n_sd_kN > 0]
    tracionadas = [c.nome for c in e.casos if c.n_sd_kN < 0]
    if comprimidas and tracionadas:
        avisos.insert(
            0,
            "A base passa por compressão (" + ", ".join(comprimidas) + ") e por tração ("
            + ", ".join(tracionadas) + "): a placa, o concreto e os chumbadores foram verificados "
            "nas duas situações; o nome entre colchetes na fórmula diz a combinação que manda em "
            "cada verificação.",
        )  # fmt: skip
    r_gov = governa.resultado
    d_mins = [i.resultado.d_b_min for i in por_caso if i.resultado.d_b_min is not None]
    diametros: dict[str, tuple[str, float | None, str]] = {}
    for item in por_caso:
        for nome, d, fonte in item.resultado.diametros:
            antes = diametros.get(nome)
            if antes is None:
                diametros[nome] = (nome, d, fonte)
            elif antes[1] is not None:  # None (nenhum diâmetro atende) fica
                diametros[nome] = (nome, None if d is None else max(d, antes[1]), fonte)
    return replace(
        r_gov,
        entrada=replace(
            e,
            n_sd_kN=governa.caso.n_sd_kN,
            m_sd_kNm=governa.caso.m_sd_kNm,
            m_sd_y_kNm=governa.caso.m_sd_y_kNm,
            v_sd_kN=r_gov.entrada.v_sd_kN,
            vx_kN=governa.caso.vx_kN,
            vy_kN=governa.caso.vy_kN,
            mz_kNm=governa.caso.mz_kNm,
        ),
        verificacoes=todas,
        grupos=tuple(grupos),
        avisos=tuple(avisos),
        t_p_min=max(i.resultado.t_p_min for i in por_caso),
        d_b_min=max(d_mins) if d_mins else None,
        f_t_sd=max(i.resultado.f_t_sd for i in por_caso),
        diametros=tuple(diametros.values()),
        casos=tuple(por_caso),
        combinacao_governante=governa.caso.nome,
        perna_do_pilar=max(i.resultado.perna_do_pilar for i in por_caso),
    )


# =============================================================================================
# A base mais leve que atende, o texto do resultado e o registro técnico
# =============================================================================================
def base_mais_leve(e: EntradaBase) -> ResultadoBase | None:
    """A base que atende com a placa mais leve, trocando o chumbador e a espessura (comercial).

    Recalcula a ligação completa para cada candidato. Dados de produto valem
    somente para a barra qualificada. A primeira espessura que atende para um
    mesmo diâmetro minimiza a massa daquela placa.
    """
    melhor: ResultadoBase | None = None
    fixo = e.ancoragem in POS_INSTALADOS and bool(
        e.n_rd_fabricante_kN or e.sistema_ancoragem or e.tau_cr_MPa or e.tau_uncr_MPa
    )
    if fixo or (e.por_formula and e.chumbador == CHUMBADOR_LIVRE):  # o diâmetro digitado fica
        candidatos = [e]
    elif e.por_formula:  # os comerciais da mesma família, com o furo pela regra
        familia = rosca_do_chumbador(e).familia
        candidatos = [replace(e, chumbador=r.nome, d_f_mm=0.0) for r in roscas_da_familia(familia)]
    else:
        candidatos = [replace(e, chumbador=chumbador) for chumbador in TABELA_18]
    for candidato in candidatos:
        for t in ESPESSURAS_COMERCIAIS:
            try:
                r = calcular(replace(candidato, t_placa_mm=t))
            except BaseInvalida:
                continue
            if r.status != "OK":
                continue
            if melhor is None or r.massa_da_placa_kg < melhor.massa_da_placa_kg - 1e-9:
                melhor = r
            break  # a próxima espessura deste chumbador só pesa mais
    return melhor


#: Em que parte da base cada verificação que reprova trava o projeto.
TRAVA_PLACA = "placa"
TRAVA_CHUMBADOR = "chumbador"
TRAVA_CONCRETO = "concreto"
TRAVA_CORTANTE = "cortante"
TRAVA_GEOMETRIA = "geometria"
TRAVA_SOLDA = "solda"


def categoria_da_trava(v: Verificacao, grupo: str) -> str:
    """A parte da base que uma verificação mede: placa, chumbador, concreto, cortante, …"""
    nome = v.nome
    if grupo == GRUPO_SOLDAS or da_solda_do_pilar(v):
        return TRAVA_SOLDA
    if nome == LINHA_FLEXAO_NA_ARGAMASSA:
        return TRAVA_CHUMBADOR
    if grupo == GRUPO_CORTANTE:
        return TRAVA_CORTANTE
    if nome.startswith(("Placa de base", "Equilíbrio")):
        return TRAVA_PLACA
    if nome.startswith(("Chumbador", "Rosca")):
        return TRAVA_CHUMBADOR
    if grupo in (GRUPO_CONCRETO_E_PLACA, GRUPO_CHUMBADORES) or nome.startswith(
        ("Concreto", "Bloco", "Fator X")
    ):
        return TRAVA_CONCRETO
    return TRAVA_GEOMETRIA


def o_que_trava(r: ResultadoBase) -> dict[str, list[str]]:
    """As verificações que reprovam, por parte da base (na ordem: placa, chumbador, concreto, …)."""
    saida: dict[str, list[str]] = {}
    for grupo, linhas in r.grupos:
        for v in linhas:
            if v.status == "NÃO OK":
                saida.setdefault(categoria_da_trava(v, grupo), []).append(v.nome)
    ordem = (TRAVA_PLACA, TRAVA_CHUMBADOR, TRAVA_CONCRETO, TRAVA_CORTANTE, TRAVA_GEOMETRIA, TRAVA_SOLDA)  # fmt: skip
    return {k: saida[k] for k in ordem if k in saida}


#: O que a base mais leve troca (placa e chumbador): o resto trava a busca.
TRAVAS_DA_BUSCA = (TRAVA_PLACA, TRAVA_CHUMBADOR)


def destaque(r: ResultadoBase) -> str:
    """Uma frase com o resultado (tela, registro e memorial)."""
    e, g = r.entrada, r.geometria
    nome = nome_do_chumbador(e) + (" (fora da Tabela 18)" if e.por_formula else "")
    tipo = NOMES_CURTOS[e.tipo]
    governante = r.governante
    gov = (
        f"; governa: {governante.nome} ({100 * (governante.aproveitamento or 0):.0f} %)"
        if governante is not None and governante.aproveitamento is not None
        and math.isfinite(governante.aproveitamento)
        else ""
    )  # fmt: skip
    esforcos = (
        f"N_Sd = {_n(e.n_sd_kN, 1)} kN, M_Sd = {_n(e.m_sd_kNm, 1)} kN·m"
        + (f", M_Sd,y = {_n(e.m_sd_y_kNm, 1)} kN·m" if e.m_sd_y_kNm else "")
        + f", V_Sd = {_n(e.v_sd_kN, 1)} kN"
    )
    if r.envoltoria:
        esforcos = (
            f"envoltória de {len(r.casos)} combinações (governa «{r.combinacao_governante}»: "
            f"{esforcos})"
        )
    espessura = (
        f"t_p,min = {_n(r.t_p_min, 2)} mm"
        if r.equilibrio_valido
        else "espessura indeterminada por falta de equilíbrio"
    )
    solda = f", filete do pilar d_w = {_n(r.perna_do_pilar, 0)} mm" if r.perna_do_pilar else ""
    return (
        f"Base {tipo} do {e.perfil}: placa {_n(g.lx, 0)} × {_n(g.ly, 0)} × "
        f"{_n(e.t_placa_mm, 1)} mm ({e.aco_placa}), {e.n_chumbadores} chumbadores Ø {nome}"
        f"{solda}; {esforcos} — caso {r.caso}, {espessura}{gov}."
    )


def linhas_das_combinacoes(r: ResultadoBase) -> list[dict[str, Any]]:
    """Uma linha por combinação: os esforços, o caso, o status e a verificação que manda nela."""
    saida = []
    for item in r.casos:
        c, rc = item.caso, item.resultado
        gov = rc.governante
        saida.append(
            {
                "Combinação": c.nome,
                "N_Sd (kN)": c.n_sd_kN,
                "M_Sd (kN·m)": c.m_sd_kNm,
                "M_Sd,y (kN·m)": c.m_sd_y_kNm,
                "V_Sd (kN)": rc.entrada.v_sd_kN,
                "Vx (kN)": c.vx_kN,
                "Vy (kN)": c.vy_kN,
                "Mz (kN·m)": c.mz_kNm,
                "R_N (kN)": rc.residuos[0],
                "R_M (kN·m)": rc.residuos[1],
                "R_M,y (kN·m)": rc.residuos[2],
                "Caso": rc.caso,
                "Status": rc.situacao,
                "Aproveitamento": numero_json(rc.aproveitamento_maximo, 4),
                "Governa": gov.nome if gov is not None else "",
                "t_p,min (mm)": round(rc.t_p_min, 2) if rc.equilibrio_valido else None,
                "F_t máx (kN)": round(rc.f_t_sd / 1e3, 1) if rc.equilibrio_valido else None,
            }
        )
    return saida


def _tabelas_das_combinacoes(r: ResultadoBase) -> list[dict[str, Any]]:
    """Tabelas curtas do relatório PDF: esforços, equilíbrio e resultados por combinação."""
    itens = r.casos
    tabelas: list[dict[str, Any]] = []
    especificacoes = (
        (
            "Esforços aplicados por combinação",
            ["Combinação", "N_Sd (kN)", "M_Sd (kN·m)", "M_Sd,y (kN·m)", "V_Sd (kN)"],
            lambda item: [
                item.caso.nome,
                _n(item.caso.n_sd_kN, 2),
                _n(item.caso.m_sd_kNm, 2),
                _n(item.caso.m_sd_y_kNm, 2),
                _n(item.resultado.entrada.v_sd_kN, 2),
            ],
        ),
        (
            "Componentes e torção por combinação",
            ["Combinação", "Vx (kN)", "Vy (kN)", "Mz (kN·m)"],
            lambda item: [
                item.caso.nome,
                "—" if item.caso.vx_kN is None else _n(item.caso.vx_kN, 2),
                "—" if item.caso.vy_kN is None else _n(item.caso.vy_kN, 2),
                _n(item.caso.mz_kNm, 2),
            ],
        ),
        (
            "Resíduos do equilíbrio por combinação",
            ["Combinação", "R_N (kN)", "R_M (kN·m)", "R_M,y (kN·m)"],
            lambda item: [item.caso.nome, *(_n(x, 7) for x in item.resultado.residuos)],
        ),
        (
            "Verificação por combinação",
            ["Combinação", "Caso", "Situação", "Aproveitamento", "Verificação governante"],
            lambda item: [
                item.caso.nome,
                item.resultado.caso,
                item.resultado.situacao,
                f"{100 * item.resultado.aproveitamento_maximo:.1f} %",
                item.resultado.governante.nome if item.resultado.governante else "—",
            ],
        ),
        (
            "Espessura e tração por combinação",
            ["Combinação", "t_p,min (mm)", "F_t máx (kN)"],
            lambda item: [
                item.caso.nome,
                _n(item.resultado.t_p_min, 2)
                if item.resultado.equilibrio_valido
                else "Indeterminada",
                _n(item.resultado.f_t_sd / 1e3, 2) if item.resultado.equilibrio_valido else "—",
            ],
        ),
    )
    for legenda, cabecalhos, linha in especificacoes:
        tabelas.append(
            {
                "legenda": legenda,
                "cabecalhos": cabecalhos,
                "linhas": [linha(item) for item in itens],
                "fonte": 7.2,
            }
        )
    return tabelas


def entrada_de_dicionario(dados: Mapping[str, Any]) -> EntradaBase:
    """A entrada gravada no registro (só os campos conhecidos; o resto fica no padrão)."""
    conhecidos = {f.name for f in fields(EntradaBase)}
    valores = {k: v for k, v in dados.items() if k in conhecidos}
    if "casos" in valores:
        valores["casos"] = tuple(caso_de_dicionario(c) for c in valores["casos"] or ())
    return EntradaBase(**valores)


def registro_base(
    r: ResultadoBase, *, contexto: Mapping[str, Any] | None = None, responsavel: str = ""
) -> dict[str, Any]:
    """O registro técnico da base de pilar, com a entrada para o memorial redesenhar a figura."""
    e, g = r.entrada, r.geometria
    tab, medidas = r.linha, r.por_formula
    geral = r.status
    texto = destaque(r)
    entradas: dict[str, Any] = {
        "finalidade": r.situacao if r.situacao == "Pré-dimensionado" else e.modo_bloco,
        "τ_cr_MPa": e.tau_cr_MPa or None,
        "τ_uncr_MPa": e.tau_uncr_MPa or None,
        "tração_sustentada_por_barra_kN": e.n_sustentada_kN,
        "graute_resistência_de_cálculo_MPa": e.graute_rd_MPa or None,
        "deslocamento_do_centro_da_placa_mm": f"({_n(e.desloc_x_mm)}, {_n(e.desloc_y_mm)})",
        "sistema_de_ancoragem": e.sistema_ancoragem or None,
        "categoria_da_ancoragem": e.categoria_aci or None,
        "aco_ductil": e.aco_ductil,
        "armadura_suplementar": e.armadura_suplementar,
        "Vx_kN": e.vx_kN,
        "Vy_kN": e.vy_kN,
        "Mz_kNm": e.mz_kNm,
        "perfil": e.perfil,
        "tipo_de_base": TIPOS[e.tipo],
        "chumbadores": f"{e.n_chumbadores} × Ø {nome_do_chumbador(e)} ({e.aco_chumbador})"
        + (" — fora da Tabela 18, medidas por fórmula" if e.por_formula else ""),
        "ancoragem": ANCORAGENS[e.ancoragem],
        "ancoragem_no_concreto": "ACI 318-19, Capítulo 17" if ancoragem_verificada(e) else None,
        "rosca": f"d_b = {_mm(medidas.rosca.d_b)} mm, passo {_n(medidas.rosca.passo, 2)} mm "
        f"rosca {medidas.rosca.serie}, A_s = {_n(medidas.rosca.area_resistente, 0)} mm²"
        if medidas is not None
        else None,
        "furo_e_arruela": f"d_f = {_mm(tab.d_f)} mm; arruela {tab.arruela} × {_mm(g.t_arruela)} mm"
        if medidas is not None
        else None,
        "embutimento_h_ef_mm": embutimento(e, tab) if medidas is not None else None,
        "a3_mm": tab.a3 if medidas is not None else None,
        "placa": f"{_n(g.lx, 0)} × {_n(g.ly, 0)} × {_n(e.t_placa_mm, 1)} mm ({e.aco_placa})",
        "a1_mm": g.a1,
        "a1_x_mm": g.a1_x if e.tipo == TIPO_2 else None,
        "a2_mm": g.a2,
        "fck_MPa": e.fck_MPa,
        "razao_A2_A1": round(razao_de_areas(e, g.lx, g.ly), 3),
        "bloco_mm": f"{_n(e.bloco_x_mm, 0)} × {_n(e.bloco_y_mm, 0)} × {_n(e.bloco_z_mm, 0) if e.bloco_z_mm else 'altura pendente'}"
        if e.bloco_x_mm > 0 and e.bloco_y_mm > 0
        else None,
        "N_Sd_kN": e.n_sd_kN,
        "M_Sd_kNm": e.m_sd_kNm or None,
        "M_Sd_y_kNm": e.m_sd_y_kNm or None,
        "V_Sd_kN": e.v_sd_kN or None,
        "combinacao": sd.COMBINACOES[e.combinacao],
        "cortante_resistida_por": CORTANTES[e.cortante],
        "distribuicao_da_pressao": DISTRIBUICOES[e.distribuicao],
        "combinacoes": "; ".join(
            f"{c.nome}: N {_n(c.n_sd_kN, 1)} kN, M {_n(c.m_sd_kNm, 1)} kN·m"
            + (f", M_y {_n(c.m_sd_y_kNm, 1)} kN·m" if c.m_sd_y_kNm else "")
            + f", V {_n(c.v_sd_kN, 1)} kN"
            for c in e.casos
        )
        or None,
        "combinacao_governante": r.combinacao_governante or None,
        "solda_do_pilar": (
            f"filete d_w = {_n(r.perna_do_pilar, 0)} mm ({e.eletrodo}) "
            + (
                "no contorno inteiro"
                if e.solda_mesas_por_dentro and e.solda_alma
                else "nas mesas por fora"
                + (" e por dentro" if e.solda_mesas_por_dentro else "")
                + (" e na alma" if e.solda_alma else "")
            )
            + ("; compressão por contato (extremidade faceada)" if e.compressao_por_contato else "")
        ),
        "aco_do_pilar": e.aco_pilar,
    }
    entradas.update(dict(contexto or {}))
    entradas = {k: v for k, v in entradas.items() if v is not None}
    alertas = [v.nome for v in r.verificacoes if v.status in ("NÃO OK", "ALERTA")]
    alertas.extend(r.avisos)
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=f"Base de pilar {e.perfil} — placa {_n(g.lx, 0)} × {_n(g.ly, 0)} × {_n(e.t_placa_mm, 1)} mm",  # fmt: skip
        status=r.situacao
        if r.situacao in ("Pré-dimensionado", "Inconclusivo")
        else STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=texto,
        entradas=entradas,
        resultados={
            "status_geral": geral,
            "caso": r.caso,
            "verificações": linhas_para_registro(list(r.verificacoes)),
            "utilizacao_maxima": numero_json(r.aproveitamento_maximo, 4),
            "destaque_memorial": texto,
            "figura_base_de_pilar": {"entrada": asdict(e)},
            # para o memorial separado (core.memorial_trecho): objetivo, grupos, detalhamento
            "objetivo": _objetivo_do_memorial(r),
            "grupos": [
                {"nome": nome, "verificacoes": [v.nome for v in linhas]}
                for nome, linhas in r.grupos
            ],
            "detalhamento": [list(par) for par in r.detalhamento],
            "simbolos": [list(par) for par in simbolos_usados(r)],
            **({"combinacoes": linhas_das_combinacoes(r)} if r.envoltoria else {}),
            **({"tabelas_memorial": _tabelas_das_combinacoes(r)} if r.envoltoria else {}),
        },
        metodo=(
            f"Base de pilar de perfil {'U' if r.geometria.e_u else 'I ou H'} com placa retangular, chumbadores e argamassa "
            "expansiva pela ABNT NBR 8800:2025, Subseção 6.7: caso pela força axial e pela "
            "excentricidade (6.7.1.4), espessura mínima da placa, diâmetro mínimo dos chumbadores "
            "e cortante (6.7.2.2 a 6.7.2.5), "
            + (
                "chumbador fora da Tabela 18 (6.7.1.1) com as disposições por fórmula: porca pela "
                "ASME B18.2.6, furo e arruela pela AISC (Manual, Tabela 14-2, e Design Guide 1), "
                "espaçamento e borda pela ACI 318-19 17.9.2, embutimento pelo cone de concreto "
                "(ACI 318-19 17.6.2) e f_ck mínimo pela NBR 6118."
                if e.por_formula
                else "disposições construtivas da Tabela 18."
            )
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
                if e.m_sd_y_kNm and e.distribuicao == DISTRIBUICAO_NBR
                else ""
            )
            + (
                " Distribuição linear elástica da pressão (6.7.1.1, em lugar do bloco uniforme): "
                "placa rígida, pressão proporcional ao deslocamento contra o concreto (sem "
                "tração) e chumbadores do lado que levanta com força proporcional à distância à "
                "linha neutra, rigidez n·A_se com n = E_s/E_cs (NBR 6118, 8.2.8); equilíbrio de "
                "N, M e M_y pela mínima energia; σ_c,máx ≤ σ_c,Rd."
                if e.distribuicao == DISTRIBUICAO_ELASTICA
                else ""
            )
        ),
        premissas=[
            "Esforços de cálculo (ELU); "
            + (
                "momentos nos dois eixos do pilar (flexão oblíqua pelo método geral)."
                if e.m_sd_y_kNm or any(c.m_sd_y_kNm for c in e.casos)
                else "momento só em torno do eixo de maior inércia do pilar."
            ),
            f"Centro da placa em ({_n(e.desloc_x_mm)}, {_n(e.desloc_y_mm)}) mm a partir do centro do bloco; chumbadores de {e.aco_chumbador} com porca sextavada "
            f"pesada; ancoragem: {ANCORAGENS[e.ancoragem].lower()}.",
            "Pressão de contato resistente pela 6.6.5: 0,85·f_ck/γ_c·√(A₂/A₁) ≤ 1,7·f_ck/γ_c.",
            "Espessura da placa: compressão pelo balanço sob a pressão (com a zona comprimida "
            "menor que o balanço, só a parte comprimida, AISC Design Guide 1, 3.3); tração pela "
            "6.7 (a linha de chumbadores na largura ℓy) e, chumbador a chumbador, em balanço até "
            "a face da mesa (m = |x| − d/2) na largura b_eff aberta a 45°, limitada pelas bordas e "
            "pela metade do espaçamento — vale a maior. A argamassa não entra no balanço da placa.",
            NOTA_POR_FORMULA if e.por_formula else NOTA_TABELA_18,
            *(
                [
                    f"Furo justo na placa (d_f = {_n(tab.d_f, 1)} mm, menor que o padrão de "
                    f"{_n(furo_padrao(tab.d_b), 0)} mm, d_b + 8): hipótese de locação "
                    "precisa dos chumbadores, com template ou gabarito de montagem."
                ]
                if furo_justo(e, tab)
                else []
            ),
            "Solda do pilar na placa pelo método elástico (trechos válidos, N, M, M_y, Vx, Vy e Mz), "
            "resistência do filete pela 6.2.5 sem o fator de direção; "
            + (
                "compressão transmitida por contato na extremidade faceada do pilar."
                if e.compressao_por_contato
                else "a solda leva também a compressão (sem contato garantido)."
            ),
        ]
        + (
            [
                "Cortante pelos chumbadores: "
                + (
                    "arruelas soldadas com furo justo (d_b + 1,5 mm), os n chumbadores engatam "
                    "juntos"
                    if e.cortante == CORTANTE_ARRUELAS
                    else "chumbadores direto no furo folgado da placa — a placa desliza até "
                    "(d_f − d_b)/2 antes do contato e só metade dos chumbadores (1 a 2) foi "
                    "contada (engate desigual); a NBR 8800 (6.7.2.3) e o AISC Design Guide 1 pedem dispositivo "
                    "positivo"
                )
                + "; só eles resistem (o atrito não se soma). Aço pela ACI 318-19 17.7.1 (0,80 "
                "pela argamassa de assentamento), flexão do chumbador na argamassa com braço "
                "e_n + t_p/2 + Δ, ruptura da borda (17.7.2), pryout (17.7.3) e interação 17.8."
            ]
            if e.cortante in CORTANTE_PELOS_CHUMBADORES
            else []
        )
        + (
            [
                f"Envoltória de {len(e.casos)} combinações de cálculo: cada uma pelo cálculo "
                "inteiro; em cada verificação vale a mais desfavorável, indicada junto da "
                "verificação."
            ]
            if e.casos
            else []
        ),
        alertas=alertas,
        referencias=[
            "ABNT NBR 8800:2025, Subseção 6.7 (bases de pilares) e Tabela 18.",
            "ABNT NBR 8800:2025, 6.6.5 (pressão de contato no concreto).",
            "ABNT NBR 8800:2025, 6.2.5, 6.2.6 e 6.5.5 (soldas de filete e metal-base).",
        ]
        + (["AISC 360-22, J1.4 (compressão por contato)."] if e.compressao_por_contato else [])
        + (
            ["ABNT NBR 8800:2025, 6.3.3.2 e 6.3.3.3 (corte do chumbador e contato no furo)."]
            if e.cortante == CORTANTE_ARRUELAS
            else []
        )
        + (
            ["ACI 318-19, Capítulo 17 (ancoragem no concreto: arrancamento, cone, borda)."]
            if ancoragem_verificada(e)
            else []
        )
        + (
            [
                "ACI 318-19, 17.7.1 (aço do chumbador à cortante, com argamassa de assentamento); "
                "EN 1992-4:2018, 6.2.2.3 (braço da cortante), e NBR 8800, 5.4.2.2 (seção resistente)."
            ]
            if e.cortante in CORTANTE_PELOS_CHUMBADORES
            else []
        )
        + (
            ["ABNT NBR 6118:2014, 8.2.8 (módulo de elasticidade do concreto, método elástico)."]
            if e.distribuicao == DISTRIBUICAO_ELASTICA
            else []
        )
        + (
            [
                "ACI 318-19, 17.9.2 (espaçamento e distância à borda mínimos dos chumbadores).",
                "AISC Steel Construction Manual, Tabela 14-2, e AISC Design Guide 1 (furo na "
                "placa e arruela dos chumbadores).",
                "ASME B18.2.6 (porca sextavada pesada); ASME B1.1 e ISO 898-1 (área resistente "
                "da rosca).",
                "ABNT NBR 6118:2014, Tabela 7.1 (classe mínima do concreto).",
            ]
            if e.por_formula
            else []
        ),
        conclusao=texto,
        responsavel=responsavel,
    )


#: Símbolos das contas da base: (como aparece no memorial, o que é, as grafias nas fórmulas).
SIMBOLOS_DA_BASE: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("N_Sd, M_Sd, M_Sd,y, V_Sd", "força axial (+ compressão), momentos nos eixos de maior e de menor inércia e cortante de cálculo", ("N_Sd", "M_Sd", "V_Sd")),
    ("d, b_f, t_w, t_f", "altura, largura da mesa, espessura da alma e da mesa do pilar", ("d/2", "b_f", "t_w")),
    ("ℓx, ℓy, t_p", "dimensões da placa (ℓx ao longo da altura do pilar) e espessura", ("ℓx", "ℓy", "ℓ_y", "t_p")),
    ("a₁, a₂", "distância do furo à borda da placa e espaçamento entre chumbadores (Tabela 18)", ("a₁", "a₂", "a_1")),
    ("m, n, λ·n₀", "balanços da placa além das linhas de engaste (0,95·d e 0,80·b_f)", ("ℓ_max", "ℓ_máx", "m − a", "máx(m; n")),
    ("ℓ_c", "comprimento da placa sob pressão de contato", ("ℓ_c",)),
    ("σ_c,Sd, σ_c,Rd", "pressão de contato solicitante e resistente no concreto", ("σ_c",)),
    ("f_ck, γ_c, A₁, A₂", "resistência característica do concreto, coeficiente do concreto, área da placa e área homotética do bloco", ("f_ck", "A₂", "A_2")),
    ("f_y, γ_a1, γ_a2", "resistência ao escoamento do aço e coeficientes de ponderação da NBR 8800", ("f_y", "γ_a1", "γ_a2")),
    ("F_t, F_t,Sd", "força de tração num chumbador", ("F_t",)),
    ("b_eff", "largura efetiva da placa por chumbador, aberta a 45°", ("b_eff",)),
    ("d_b, d_s, A_se", "diâmetro do chumbador, diâmetro da área resistente da rosca e área resistente", ("d_b", "A_se", "d_s")),
    ("f_ub, f_uta", "resistência à ruptura do aço do chumbador (f_uta ≤ 1,9·f_y ≤ 862 MPa na ACI)", ("f_ub", "f_uta")),
    ("e_n", "espessura da argamassa de assentamento", ("e_n",)),
    ("h_ef", "embutimento efetivo do chumbador no concreto", ("h_ef",)),
    ("A_Nc, A_Nco, ψ", "área projetada do cone de concreto (do grupo e de um chumbador isolado) e fatores de modificação da ACI 318-19", ("A_Nc", "ψ_")),
    ("φ", "fator de redução de resistência da ACI 318-19", ("φ",)),
    ("μ", "coeficiente de atrito entre a placa e a argamassa", ("μ",)),
    ("n_eng", "número de chumbadores que resistem à cortante", ("n_eng", "n_engatados")),
    ("W", "módulo resistente elástico da seção da rosca", ("1,5·W", "W = π")),
)  # fmt: skip


def simbolos_usados(r: ResultadoBase) -> list[tuple[str, str]]:
    """Os símbolos que aparecem nas contas desta base, com o significado."""
    texto = " ".join(
        [v.formula for v in r.verificacoes] + [x for v in r.verificacoes for x in v.equacoes]
    )
    return [(simbolo, significado) for simbolo, significado, grafias in SIMBOLOS_DA_BASE if any(g in texto for g in grafias)]  # fmt: skip


def _objetivo_do_memorial(r: ResultadoBase) -> str:
    e, g = r.entrada, r.geometria
    aci = (
        " e da ancoragem no concreto pela ACI 318-19 (Capítulo 17)"
        if ancoragem_verificada(e)
        else ""
    )
    return (
        f"Este item apresenta a verificação da base do pilar {e.perfil}, com placa "
        f"{_n(g.lx, 0)} × {_n(g.ly, 0)} × {_n(e.t_placa_mm, 1)} mm e {e.n_chumbadores} "
        f"chumbadores Ø {nome_do_chumbador(e)}, pela ABNT NBR 8800:2025 (subseção 6.7){aci}."
    )


def memorial_da_base(
    r: ResultadoBase, *, projeto: Mapping[str, Any] | None = None, formato: str = "word"
) -> bytes:
    """O memorial só desta base: em Word, o trecho para colar no documento oficial
    (:mod:`core.memorial_trecho`); em PDF, o documento do padrão do memorial do projeto."""
    import importlib

    if formato != "pdf":
        from core.desenho_placa_base_contas import figuras_das_contas
        from core.memorial_trecho import trecho_de_registro
        from core.technical_records import normalizar_registro_tecnico

        return trecho_de_registro(
            normalizar_registro_tecnico(registro_base(r)),
            projeto=projeto,
            figuras_por_verificacao=figuras_das_contas(r),
        )

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
