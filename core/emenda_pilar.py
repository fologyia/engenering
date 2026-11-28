"""Emenda de pilar em perfil W/HP com talas parafusadas.

Uma tala externa em cada mesa (corte simples) e duas talas na alma, uma de cada lado (corte
duplo). Funções puras, sem Streamlit.

Referências:

* ABNT NBR 8800:2025 (a numeração dos itens citados vem do texto de revisão de 2024; confirmar na
  edição vigente). As resistências saem daqui.
* Critério de Projeto Anglo American AA-BR-DPST-DR-0001 (itens 8.8, 9.1 e 12).
* AISC Manual, Parte 14 (Column Splices).
* Kulak, Fisher e Struik, *Guide to Design Criteria for Bolted and Riveted Joints*, cap. 13 e 16.
* SCI P207, *Joints in Steel Construction – Moment Connections* (SCI/BCSA, 1995), seção 5. Dele
  vem só o modelo mecânico (distribuição dos esforços, grupo de parafusos, continuidade, ação de
  escora). Os fatores da BS 5950 (K_e, p_y, 0,9·A_net, 1,1·K_s) NÃO são usados.

As resistências reaproveitam :mod:`core.bolted_connection` (corte, contato, deslizamento, áreas do
colapso por rasgamento) e :func:`core.nbr8800.fator_chi`. Unidades internas: mm, N e MPa; as
saídas vêm em kN, kN·m e mm.
"""

from __future__ import annotations

import csv
import io
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from core import bolted_connection as bc
from core import medidas_comerciais as mc
from core import perfis_gerdau_k as gk
from core.nbr8800 import fator_chi
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    linhas_para_registro,
    numero_json,
    status_geral,
)

NORMA = "NBR8800_2024"  # chave interna da ABNT NBR 8800:2025 em core.bolted_connection
NOME_DA_NORMA = "ABNT NBR 8800:2025"
MODULO_ID = "emenda_pilar"
MODULO_TITULO = "Emenda de pilar"

# Coeficientes de ponderação da NBR 8800, Tabela 3 (os mesmos de core.bolted_connection).
GAMA_A1 = bc._P[NORMA]["g_a1"]
GAMA_A2 = bc._P[NORMA]["g_a2"]

# ---------------------------------------------------------------------------------------------
# TABELAS
# ---------------------------------------------------------------------------------------------
FAMILIA_W = "W e HP"
FAMILIA_U = "U"
FAMILIAS = (FAMILIA_W, FAMILIA_U)
_DADOS = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class PerfilEmenda:
    """Dimensões em mm, A em mm², I em mm⁴. No U, ``d_linha`` = h (o catálogo não traz o raio)."""

    nome: str
    familia: str
    d: float
    bf: float
    tw: float
    tf: float
    h: float
    d_linha: float
    A: float
    Ix: float
    Iy: float

    @property
    def R(self) -> float:
        """Raio de concordância mesa–alma: R = (h − d')/2 (no U vale 0; o raio é informado)."""
        return (self.h - self.d_linha) / 2


def _lista(arquivo: str) -> list[dict[str, Any]]:
    dados = json.loads((_DADOS / arquivo).read_text(encoding="utf-8"))
    return list(dados["perfis"] if isinstance(dados, dict) else dados)


def _carregar_perfis() -> dict[str, PerfilEmenda]:
    """W e HP da Gerdau (data/perfis_ref_gerdau.json, h e d' de core/perfis_gerdau_k.py) e os U
    laminados (data/perfis_ref_gerdau_u.json). Catálogos de referência, não os do usuário."""
    perfis: dict[str, PerfilEmenda] = {}
    for c in _lista("perfis_ref_gerdau.json"):
        h, dl = gk.H_E_D_LINHA_MM[gk._normalizar(c["nome"])]
        perfis[c["nome"]] = PerfilEmenda(
            c["nome"], FAMILIA_W, c["altura_mm"], c["largura_mm"], c["espessura_alma_mm"],
            c["espessura_mesa_mm"], float(h), float(dl), c["area_mm2"], c["ix_mm4"], c["iy_mm4"],
        )  # fmt: skip
    for c in _lista("perfis_ref_gerdau_u.json"):
        h = c["altura_mm"] - 2 * c["espessura_mesa_mm"]
        perfis[c["nome"]] = PerfilEmenda(
            c["nome"], FAMILIA_U, c["altura_mm"], c["largura_mm"], c["espessura_alma_mm"],
            c["espessura_mesa_mm"], h, h, c["area_mm2"], c["ix_mm4"], c["iy_mm4"],
        )  # fmt: skip
    return perfis


PERFIS = _carregar_perfis()
PERFIL_PADRAO = "W 200 x 46,1 (H)"
PERFIL_PADRAO_U = 'U 12" x 37,00'


def perfis_da_familia(familia: str) -> list[str]:
    return [n for n, p in PERFIS.items() if p.familia == familia]


#: T2 — aços (NBR 8800, Tabela A.2): (f_y, f_u) em MPa. Os de core.bolted_connection mais o A992.
ACOS: dict[str, tuple[float, float]] = {
    "ASTM A36": bc.ACOS["ASTM A36"],
    "ASTM A572 Gr 50": bc.ACOS["ASTM A572 Gr 50"],
    "ASTM A992": (345.0, 450.0),  # NBR 8800, Tabela A.2
}

#: T3 — parafusos (furo-padrão Tab. 14, borda mínima Tab. 16, F_Tb Tab. 19): todos os de
#: core.bolted_connection.PARAFUSOS; as disposições marcam os que saem de 5/8" a 1" (Anglo).
DIAMETROS = tuple(bc.PARAFUSOS)

#: T4 — graus (Tab. A.3): rótulo → chave de core.bolted_connection.GRAUS.
GRAUS = {"ASTM F3125 A325": "A325", "ASTM F3125 A490": "A490"}

#: T5 — μ (6.3.4.3): rótulo → chave de core.bolted_connection.SUPERFICIES.
SUPERFICIES = {
    "Galvanizada a quente": "galvanizada_sem_tratamento",
    "Classe A": "classe_A_laminada_limpa",
    "Classe B": "classe_B_jateada",
}

DISTRIBUICAO_POR_AREA = "Por área"
DISTRIBUICAO_METADE = "N/2 nas mesas (SCI P207 5.2.2)"
DISTRIBUICOES = (DISTRIBUICAO_POR_AREA, DISTRIBUICAO_METADE)

MINIMO_MENOS_SEVERO = "6.1.6.2 menos severo de a e b"
MINIMO_SO_A = "só a"
MINIMO_SO_B = "só b"
MINIMO_NENHUM = "nenhum"
CRITERIOS_MINIMO = (MINIMO_MENOS_SEVERO, MINIMO_SO_A, MINIMO_SO_B, MINIMO_NENHUM)

# ---------------------------------------------------------------------------------------------
# PARÂMETROS (com a fonte; nada aqui foi inventado)
# ---------------------------------------------------------------------------------------------
ALFA_V_ROSCA_NO_PLANO = bc._P[NORMA]["alfa_N"]  # 0,45 — NBR 6.3.3.2
ALFA_V_ROSCA_FORA = bc._P[NORMA]["alfa_X"]  # 0,56 — NBR 6.3.3.2
FOLGA_AREA_LIQUIDA = bc.folga_do_furo(NORMA)  # 2 mm — NBR 5.2.4.1 a
ENCHIMENTO_SEM_REDUCAO = 6.3  # mm — NBR 6.5.7.2 a
ENCHIMENTO_MAXIMO = 19.0  # mm — NBR 6.5.7.2 a/b
ENCHIMENTO_COEFICIENTE = 0.0154  # 1/mm — NBR 6.5.7.2 a
FRACAO_TRACAO_MINIMA = 0.5  # NBR 6.1.6.2 a: tração de 50 % de N_c,Rd
FRACAO_FORCA_TRANSVERSAL = 0.02  # NBR 6.1.6.2 b: força transversal de 2 % de N_c,Rd
COEF_CONTATO_USINADO = 1.8  # NBR 6.6.2: 1,8·f_y·A/γ_a2
COEF_COMPRIMENTO_TALA = 0.65  # NBR 6.5.4 / Tab. E.1: K = 0,65 na tala entre as fileiras
LIMITE_ESBELTEZ_TALA = 25.0  # NBR 6.5.4: K·L/r ≤ 25 dispensa a flambagem
FATOR_SERVICO_PADRAO = 0.70  # NBR 6.3.4.4 (simplificação: força de serviço ≈ 0,70 × cálculo)
COEF_DESLIZAMENTO = 0.80  # NBR 6.3.4.4
LIGACAO_LONGA_MM = 950.0  # NBR 6.3.8
FATOR_LIGACAO_LONGA = 1.20  # NBR 6.3.8
GAP_MAXIMO_CONTATO = 2.0  # mm — NBR 12.3.5
GAP_CALCOS = 6.3  # mm — NBR 12.3.5
DIAMETRO_MINIMO = 15.875  # mm, 5/8" — Anglo 8.8
DIAMETRO_PREFERIDO_MAXIMO = 25.4  # mm, 1" — Anglo 9.1
ESPESSURA_MINIMA_TALA = 8.0  # mm — Anglo 8.8
ESPACAMENTO_MINIMO_DB = 3.0  # NBR 6.3.9 (mínimo absoluto 2,7·d_b)
ESPACAMENTO_ABSOLUTO_DB = 2.7  # NBR 6.3.9
BORDA_MAXIMA_T = 12.0  # NBR 6.3.12: 12·t
BORDA_MAXIMA_MM = 150.0  # NBR 6.3.12
ESPACAMENTO_MAXIMO_T = 24.0  # NBR 6.3.10 a: 24·t
ESPACAMENTO_MAXIMO_MM = 300.0  # NBR 6.3.10 a
EXTENSAO_MINIMA_MM = 225.0  # SCI P207 5.2.4
PARAFUSOS_MINIMOS = 2  # Anglo 9.1
TALA_ATRITO_MAXIMO_MM = 10.0  # SCI P207 passos 3 e 4 (BS 4604): t ≥ min(d_b/2; 10 mm)

AVISOS_FIXOS = (
    f"{NOME_DA_NORMA}: os itens citados seguem a numeração do texto de revisão de 2024; confirmar "
    "a numeração na edição vigente.",
    "Não verifica a montagem, o sismo nem a flambagem por torção do pilar; a flexão em torno de y "
    "só entra pelo M_y informado (talas e parafusos das mesas).",
)
NOTAS_DE_DESENHO_CONTATO = (
    "Extremidades usinadas – contato obrigatório.",
    "Aproximar os pilares até o contato antes de apertar os parafusos.",
)
AVISO_MOMENTO_SEM_ATRITO = (
    "SCI P207 5.2.1 recomenda parafusos protendidos por atrito em emendas com talas sob momento: o "
    "deslizamento gira a emenda e pode invalidar a continuidade admitida na análise."
)


# ---------------------------------------------------------------------------------------------
# ENTRADAS
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CasoEsforco:
    """Esforços de cálculo na cota da emenda: N em kN (+ compressão, − tração), M em kN·m, V em kN."""

    nome: str
    N: float
    Mx: float
    V: float
    My: float = 0.0


CASOS_PADRAO = (
    CasoEsforco("Caso 1", 600.0, 25.0, 20.0),
    CasoEsforco("Caso 2", -80.0, 25.0, 20.0),
)


@dataclass(frozen=True)
class EntradaEmenda:
    # 1.1 perfis e materiais
    perfil_superior: str = PERFIL_PADRAO
    perfil_inferior: str = PERFIL_PADRAO
    aco_perfis: str = "ASTM A572 Gr 50"
    aco_talas: str = "ASTM A36"
    E: float = 200_000.0
    gama_a1: float = GAMA_A1
    gama_a2: float = GAMA_A2
    # 1.2 parafusos
    diametro: str = '3/4"'
    grau: str = "ASTM F3125 A325"
    rosca_no_plano: bool = True
    verificar_deslizamento: bool = False
    superficie: str = "Galvanizada a quente"
    fator_servico: float = FATOR_SERVICO_PADRAO
    # 1.3 tipo de emenda
    contato: bool = True
    gap: float = 0.0
    # 1.4 pilar
    Lx: float = 6000.0
    Kx: float = 1.0
    Ly: float = 6000.0
    Ky: float = 1.0
    a: float = 1200.0
    #: vão da situação b de 6.1.6.2 (o trecho entre travamentos que contém a emenda);
    #: vazio = L_x. Vem do esqueleto quando a emenda sai do modelo.
    vao_b: float | None = None
    Nc_Rd_informado: float | None = None  # kN
    criterio_minimo: str = MINIMO_MENOS_SEVERO
    distribuicao: str = DISTRIBUICAO_POR_AREA
    # 1.5 esforços
    casos: tuple[CasoEsforco, ...] = CASOS_PADRAO
    # 1.6 talas das mesas
    bp: float = 200.0
    tp: float = 12.5
    nl: int = 2
    nr: int = 2
    g: float = 110.0
    s: float = 75.0
    ep: float = 40.0
    ec: float = 40.0
    # 1.7 talas da alma
    bw: float = 150.0
    twp: float = 8.0
    nc: int = 2
    m: int = 2
    sh: float = 75.0
    sv: float = 75.0
    ewv: float = 40.0
    ewc: float = 40.0
    # talas internas nas mesas (corte duplo): 2 por mesa no W (uma de cada lado da alma), 1 no U,
    # encostadas na ponta da mesa, com o comprimento da externa. A força da mesa se divide entre
    # a externa e as internas pela área (simplificação usual; AISC Manual Parte 14).
    talas_internas: bool = False
    bi: float = 80.0  # largura de cada tala interna (mm)
    ti: float = 12.5  # espessura (mm)
    # só no U: o catálogo não traz o raio de concordância; x1 = do dorso da alma à 1ª linha de furos
    raio_u: float = 0.0
    x1_u: float = 45.0


def validar(e: EntradaEmenda) -> list[str]:
    """Erros que impedem o cálculo (lista vazia = pode calcular)."""
    erros: list[str] = []
    for nome in (e.perfil_superior, e.perfil_inferior):
        if nome not in PERFIS:
            erros.append(f"Perfil desconhecido: {nome}.")
    for nome in (e.aco_perfis, e.aco_talas):
        if nome not in ACOS:
            erros.append(f"Aço desconhecido: {nome}.")
    if e.diametro not in DIAMETROS:
        erros.append(f"Parafuso desconhecido: {e.diametro}.")
    if e.grau not in GRAUS:
        erros.append(f"Grau desconhecido: {e.grau}.")
    if e.superficie not in SUPERFICIES:
        erros.append(f"Superfície desconhecida: {e.superficie}.")
    if e.distribuicao not in DISTRIBUICOES:
        erros.append(f"Distribuição desconhecida: {e.distribuicao}.")
    if e.criterio_minimo not in CRITERIOS_MINIMO:
        erros.append(f"Critério de mínimo desconhecido: {e.criterio_minimo}.")
    positivos = {
        "E": e.E, "γ_a1": e.gama_a1, "γ_a2": e.gama_a2, "L_x": e.Lx, "K_x": e.Kx, "L_y": e.Ly,
        "K_y": e.Ky, "b_p": e.bp, "t_p": e.tp, "g": e.g, "s": e.s, "e_p": e.ep, "e_c": e.ec,
        "b_w": e.bw, "t_w,p": e.twp, "s_h": e.sh, "s_v": e.sv, "e_wv": e.ewv, "e_wc": e.ewc,
        "fator serviço/cálculo": e.fator_servico,
    }  # fmt: skip
    if e.talas_internas:
        positivos |= {"b_i": e.bi, "t_i": e.ti}
    erros += [f"{nome} precisa ser maior que zero." for nome, v in positivos.items() if v <= 0]
    for nome, n in (("n_l", e.nl), ("n_r", e.nr), ("n_c", e.nc), ("m", e.m)):
        if n < 1:
            erros.append(f"{nome} precisa ser pelo menos 1.")
    if e.gap < 0:
        erros.append("A fresta não pode ser negativa.")
    vao = e.vao_b if e.vao_b is not None else e.Lx
    if e.vao_b is not None and e.vao_b <= 0:
        erros.append("O vão da situação b precisa ser maior que zero.")
    elif not 0 <= e.a < vao:
        erros.append("A altura da emenda precisa ficar dentro do vão (0 ≤ a < L).")
    if e.Nc_Rd_informado is not None and e.Nc_Rd_informado <= 0:
        erros.append("N_c,Rd informado precisa ser maior que zero (ou fique vazio).")
    if not e.casos:
        erros.append("Informe pelo menos um caso de esforços.")
    eh_u = e.perfil_superior in PERFIS and PERFIS[e.perfil_superior].familia == FAMILIA_U
    if (
        e.perfil_superior in PERFIS
        and e.perfil_inferior in PERFIS
        and PERFIS[e.perfil_superior].familia != PERFIS[e.perfil_inferior].familia
    ):
        erros.append("Os dois trechos precisam ser da mesma família (W/HP ou U).")
    if not eh_u and e.nl >= 1 and e.bp <= (e.nl - 1) * e.g:
        erros.append("A tala da mesa é mais estreita que o gabarito dos furos.")
    if eh_u:
        bf = PERFIS[e.perfil_superior].bf
        if e.x1_u <= 0 or e.x1_u + (e.nl - 1) * e.g >= bf:
            erros.append("No U, os furos precisam caber na mesa: 0 < x1 e x1 + (n_l − 1)·g < b_f.")
        if e.raio_u < 0:
            erros.append("O raio de concordância não pode ser negativo.")
    if e.talas_internas and not eh_u and e.nl % 2:
        erros.append("Com talas internas no W, n_l precisa ser par (metade de cada lado da alma).")
    if e.nc >= 1 and e.bw <= (e.nc - 1) * e.sh:
        erros.append("A tala da alma é mais estreita que o espaçamento dos furos.")
    if not erros:
        sup, inf = PERFIS[e.perfil_superior], PERFIS[e.perfil_inferior]
        for local, ts in (
            ("na mesa", abs(inf.d - sup.d) / 2),
            ("na alma", abs(inf.tw - sup.tw) / 2),
        ):
            if ts > ENCHIMENTO_MAXIMO:
                erros.append(
                    f"Enchimento {local} de {ts:.1f} mm passa de 19 mm: estender o enchimento "
                    "(6.5.7.2-b)."
                )
    return erros


# ---------------------------------------------------------------------------------------------
# FUNÇÕES DO MODELO MECÂNICO (testadas com o exemplo do SCI P207, 5.4)
# ---------------------------------------------------------------------------------------------
def diametro_do_parafuso(designacao: str) -> float:
    """d_b em mm: o exato da polegada (3/4" = 19,05 mm) ou o métrico."""
    if '"' in designacao:
        return bc._fracao(designacao.rstrip('"')) * bc.POL_MM
    return bc.PARAFUSOS[designacao][0]


def furo_padrao(designacao: str) -> float:
    """d_h do furo-padrão (NBR 8800:2025, Tabela 14), por core.bolted_connection."""
    return bc.dimensoes_do_furo(designacao, bc.FURO_PADRAO, NORMA)[0]


def fator_enchimento(ts: float) -> float:
    """β da NBR 6.5.7.2 a: 1 até 6,3 mm; 1 − 0,0154·(t_s − 6,3) até 19 mm; acima, erro."""
    if ts < 0:
        raise ValueError("Espessura de enchimento negativa.")
    if ts <= ENCHIMENTO_SEM_REDUCAO:
        return 1.0
    if ts <= ENCHIMENTO_MAXIMO:
        return 1.0 - ENCHIMENTO_COEFICIENTE * (ts - ENCHIMENTO_SEM_REDUCAO)
    raise ValueError("Enchimento acima de 19 mm: estender o enchimento (6.5.7.2-b).")


def forcas_nas_mesas(N: float, M: float, z: float, k: float) -> tuple[float, float]:
    """(F_f,t ; F_f,c) em kN. N em kN (+ compressão), M em kN·m, z em mm, k = parcela de N por mesa.

    F_f,t = |M|/z − N·k ;  F_f,c = |M|/z + N·k  (SCI P207, 5.3 passo 1, com k = 1/2).
    """
    binario = abs(M) * 1000.0 / z
    return binario - N * k, binario + N * k


def soma_r2(n_a: int, p_a: float, n_b: int, p_b: float) -> float:
    """Σr² (mm²) de uma grade n_a × n_b com passos p_a e p_b, medido do centro."""
    return n_a * n_b * ((n_a**2 - 1) / 12 * p_a**2 + (n_b**2 - 1) / 12 * p_b**2)


@dataclass(frozen=True)
class ForcaNoGrupo:
    soma_r2: float  # mm²
    componente_1: float  # kN
    componente_2: float  # kN
    resultante: float  # kN


def grupo_da_alma(
    V: float, Nw: float, m: int, nc: int, sv: float, sh: float, e: float
) -> ForcaNoGrupo:
    """Parafuso de canto do grupo da alma (método elástico). V, N_w em kN; medidas em mm.

    M_w = |V|·e; Σr² = m·n_c·[(m²−1)/12·s_v² + (n_c²−1)/12·s_h²];
    R_h = |V|/(m·n_c) + M_w·((m−1)·s_v/2)/Σr²;  R_v = N_w/(m·n_c) + M_w·((n_c−1)·s_h/2)/Σr².
    """
    n = m * nc
    r2 = soma_r2(m, sv, nc, sh)
    Mw = abs(V) * e
    Rh = abs(V) / n + (Mw * ((m - 1) * sv / 2) / r2 if r2 else 0.0)
    Rv = Nw / n + (Mw * ((nc - 1) * sh / 2) / r2 if r2 else 0.0)
    return ForcaNoGrupo(r2, Rh, Rv, math.hypot(Rh, Rv))


def grupo_da_mesa(Ff: float, Mf: float, nl: int, nr: int, g: float, s: float) -> ForcaNoGrupo:
    """Parafuso de canto da mesa com F_f (kN) e o momento M_f (kN·mm) no plano da mesa (P207 passo 5).

    F_y = F_f/n_b + M_f·((n_l−1)·g/2)/Σr²;  F_x = M_f·((n_r−1)·s/2)/Σr². Devolve (F_y, F_x).
    """
    n = nl * nr
    r2 = soma_r2(nl, g, nr, s)
    Fy = Ff / n + (Mf * ((nl - 1) * g / 2) / r2 if r2 else 0.0)
    Fx = Mf * ((nr - 1) * s / 2) / r2 if r2 else 0.0
    return ForcaNoGrupo(r2, Fy, Fx, math.hypot(Fx, Fy))


def posicoes_dos_furos(n: int, passo: float) -> list[float]:
    """Distâncias das linhas de furos ao centro da tala: (i − (n−1)/2)·passo."""
    return [(i - (n - 1) / 2) * passo for i in range(n)]


def modulo_liquido(
    b: float, t: float, dh_n: float, posicoes: Sequence[float], n_talas: int = 1
) -> tuple[float, float]:
    """(I_net por tala em mm⁴ ; W_net do conjunto em mm³) para a flexão no plano da tala (nota C).

    I_net = t·b³/12 − Σ[t·d_h,n³/12 + t·d_h,n·x_i²];  W_net = n_talas·I_net/(b/2).
    """
    I = t * b**3 / 12 - sum(t * dh_n**3 / 12 + t * dh_n * x**2 for x in posicoes)
    return I, n_talas * I / (b / 2)


def resist_contato(l_f: float, t: float, f_u: float, d_b: float, gama_a2: float) -> float:
    """F_c (kN) = min(1,2·ℓ_f·t·f_u ; 2,4·d_b·t·f_u)/γ_a2 (NBR 6.3.3.3 a), por core.bolted_connection."""
    return bc.resist_contato(d_b, t, f_u, l_f, NORMA) * GAMA_A2 / gama_a2


def resist_rasgamento(
    Agv: float, Anv: float, Ant: float, f_y: float, f_u: float, gama_a2: float
) -> float:
    """F_r,Rd (kN), NBR 6.5.6 com C_ts = 1, por core.bolted_connection."""
    return bc.resist_colapso_rasgamento(Agv, Anv, Ant, f_y, f_u, NORMA, 1.0) * GAMA_A2 / gama_a2


# ---------------------------------------------------------------------------------------------
# RESULTADO
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class EsforcosDoCaso:
    nome: str
    origem: str  # "usuário" ou "mínimo 6.1.6.2 (a/b)"
    N: float
    Mx: float
    V: float
    My: float
    Fft: float
    Ffc: float
    Tf: float
    Cf: float
    Cc: float
    Mf: float  # kN·m, em cada mesa
    Ffr: float  # kN, parafuso de canto da mesa
    Nw: float
    Mw: float  # kN·m
    Rh: float
    Rv: float
    Rw: float


@dataclass(frozen=True)
class CasoMinimo:
    Nc_Rd: float
    Na: float
    Ffa: float
    H: float
    Mb: float  # kN·m
    Vb: float
    Ffb: float
    adotado: str  # "a", "b" ou "" (nenhum)
    caso: CasoEsforco | None


@dataclass
class ResultadoEmenda:
    entrada: EntradaEmenda
    superior: PerfilEmenda
    inferior: PerfilEmenda
    propriedades: dict[str, float]
    estimativa_invalida: bool
    Nc_Rd_estimado: float
    Nc_Rd: float
    lambda0: float
    chi: float
    minimo: CasoMinimo
    casos: list[EsforcosDoCaso]
    envoltoria: dict[str, float]
    mesa: list[Verificacao]
    alma: list[Verificacao]
    disposicoes: list[Verificacao]
    avisos: list[str] = field(default_factory=list)
    notas_de_desenho: tuple[str, ...] = ()

    @property
    def resistencia(self) -> list[Verificacao]:
        return self.mesa + self.alma

    @property
    def status_resistencia(self) -> str:
        return status_geral(self.resistencia)

    @property
    def itens_a_verificar(self) -> list[Verificacao]:
        return [v for v in self.disposicoes if v.status != "OK" and v.status != "N/A"]

    @property
    def governante(self) -> Verificacao | None:
        com_valor = [v for v in self.resistencia if v.aproveitamento is not None]
        return max(com_valor, key=lambda v: v.aproveitamento or 0.0, default=None)

    @property
    def utilizacao_maxima(self) -> float:
        g = self.governante
        return 0.0 if g is None or g.aproveitamento is None else g.aproveitamento

    @property
    def situacao(self) -> str:
        return "ATENDE" if self.status_resistencia in ("OK", "N/A") else "NÃO ATENDE"

    @property
    def resumo_da_situacao(self) -> str:
        n = len(self.itens_a_verificar)
        disp = "nenhum item a VERIFICAR" if n == 0 else f"{n} item(ns) a VERIFICAR"
        return f"resistência {self.situacao}; disposições: {disp}"

    @property
    def total_de_parafusos(self) -> int:
        e = self.entrada
        return 2 * (2 * e.nl * e.nr + e.nc * e.m)


def _n(valor: float, casas: int = 1) -> str:
    """Número em pt-BR, sem zeros à direita (19,05; 12,5; 200)."""
    texto = f"{valor:.{casas}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto.replace(".", ",")


# ---------------------------------------------------------------------------------------------
# CÁLCULO
# ---------------------------------------------------------------------------------------------
def _linha(
    nome: str, sd: float | None, rd: float | None, unidade: str, ref: str, formula: str,
    ativa: bool = True,
) -> Verificacao:  # fmt: skip
    if not ativa:
        return Verificacao(nome, None, None, unidade, ref, formula, status="N/A")
    return Verificacao(nome, sd, rd, unidade, ref, formula)


def _regra(nome: str, valor: float, limite: str, atende: bool, ref: str, unidade: str = "mm",
           ativa: bool = True) -> Verificacao:  # fmt: skip
    if not ativa:
        return Verificacao(nome, None, None, unidade, ref, limite, status="N/A", tipo="limite")
    return Verificacao(
        nome, valor, None, unidade, ref, limite, status="OK" if atende else "ALERTA", tipo="limite"
    )


def estimar_nc_rd(
    perfil: PerfilEmenda, e: EntradaEmenda, fy: float
) -> tuple[float, float, float, bool]:
    """(N_c,Rd,est em kN ; λ_0 ; χ ; estimativa inválida) — NBR 5.3, sem flambagem local."""
    Nex = math.pi**2 * e.E * perfil.Ix / (e.Kx * e.Lx) ** 2
    Ney = math.pi**2 * e.E * perfil.Iy / (e.Ky * e.Ly) ** 2
    lambda0 = math.sqrt(perfil.A * fy / min(Nex, Ney))
    chi = fator_chi(lambda0)
    raiz = math.sqrt(e.E / fy)
    aba = perfil.bf if perfil.familia == FAMILIA_U else perfil.bf / 2  # no U a mesa é uma aba só
    invalida = aba / perfil.tf > 0.56 * raiz or perfil.d_linha / perfil.tw > 1.49 * raiz
    return chi * perfil.A * fy / e.gama_a1 / 1000, lambda0, chi, invalida


def caso_minimo(Nc_Rd: float, alfa_f: float, z: float, e: EntradaEmenda) -> CasoMinimo:
    """NBR 6.1.6.2 como mínimo recomendado: a (tração 0,5·N_c,Rd) ou b (H = 0,02·N_c,Rd)."""
    Na = FRACAO_TRACAO_MINIMA * Nc_Rd
    Ffa = Na / 2 if e.distribuicao == DISTRIBUICAO_METADE else Na * alfa_f
    H = FRACAO_FORCA_TRANSVERSAL * Nc_Rd
    vao = e.vao_b if e.vao_b is not None else e.Lx
    Mb = H * e.a * (vao - e.a) / vao / 1000  # kN·m
    Vb = H * max(e.a, vao - e.a) / vao
    Ffb = Mb * 1000 / z
    if e.criterio_minimo == MINIMO_NENHUM:
        adotado = ""
    elif e.criterio_minimo == MINIMO_SO_A:
        adotado = "a"
    elif e.criterio_minimo == MINIMO_SO_B:
        adotado = "b"
    else:
        adotado = "a" if Ffa <= Ffb else "b"
    caso = None
    if adotado == "a":
        caso = CasoEsforco("Mínimo 6.1.6.2 a", -Na, 0.0, 0.0)
    elif adotado == "b":
        caso = CasoEsforco("Mínimo 6.1.6.2 b", 0.0, Mb, Vb)
    return CasoMinimo(Nc_Rd, Na, Ffa, H, Mb, Vb, Ffb, adotado, caso)


def calcular(e: EntradaEmenda) -> ResultadoEmenda:
    erros = validar(e)
    if erros:
        raise ValueError(" ".join(erros))
    sup, inf = PERFIS[e.perfil_superior], PERFIS[e.perfil_inferior]
    fy, fu = ACOS[e.aco_perfis]
    fyp, fup = ACOS[e.aco_talas]
    g1, g2 = e.gama_a1, e.gama_a2

    # 3.1 propriedades derivadas
    eh_u = sup.familia == FAMILIA_U
    R = e.raio_u if eh_u else sup.R
    bf_min, tf_min = min(sup.bf, inf.bf), min(sup.tf, inf.tf)
    tw_min, tw_max = min(sup.tw, inf.tw), max(sup.tw, inf.tw)
    dl_min = min(sup.h, inf.h) - 2 * e.raio_u if eh_u else min(sup.d_linha, inf.d_linha)
    db = diametro_do_parafuso(e.diametro)
    dh = furo_padrao(e.diametro)
    dhn = dh + FOLGA_AREA_LIQUIDA
    grau = GRAUS[e.grau]
    Ab = bc.area_bruta(db)
    Fv = bc.resist_corte(db, grau, NORMA, e.rosca_no_plano, 1) * GAMA_A2 / g2
    _, _, borda_min, *_ = bc.PARAFUSOS[e.diametro]
    F_Tb = bc.protensao_minima(e.diametro, grau)
    mu = bc.mu_superficie(SUPERFICIES[e.superficie], NORMA) or 0.0
    # no U os dorsos das almas ficam alinhados: a diferença de alma vai inteira para dentro
    tsf, tsw = abs(inf.d - sup.d) / 2, abs(inf.tw - sup.tw) / (1 if eh_u else 2)
    beta_f, beta_w = fator_enchimento(tsf), fator_enchimento(tsw)

    # 3.2 N_c,Rd
    Nc_est, lambda0, chi, invalida = estimar_nc_rd(sup, e, fy)
    Nc_Rd = e.Nc_Rd_informado if e.Nc_Rd_informado is not None else Nc_est

    # 3.3 distribuição e caso mínimo
    alfa_f = sup.bf * sup.tf / sup.A
    alfa_w = 1 - 2 * alfa_f
    z = sup.d - sup.tf
    metade = e.distribuicao == DISTRIBUICAO_METADE
    k = 0.5 if metade else alfa_f
    aw = 0.0 if metade else alfa_w
    minimo = caso_minimo(Nc_Rd, alfa_f, z, e)

    # 3.5 geometria derivada
    nb, nbw = e.nl * e.nr, e.nc * e.m
    largura_furos = (e.nl - 1) * e.g
    if eh_u:
        # U: x a partir do dorso da alma; a tala externa encosta no dorso
        e2_alma = e.x1_u  # tala: do furo ao lado da alma
        e2 = e.bp - e.x1_u - largura_furos  # tala: do furo à borda livre
        e2c = bf_min - e.x1_u - largura_furos  # mesa do pilar: só a borda livre
        folga = e.x1_u - tw_max - R
    else:
        e2 = e2_alma = (e.bp - largura_furos) / 2
        e2c = (bf_min - largura_furos) / 2
        folga = e.g / 2 - tw_max / 2 - R
    ewh = (e.bw - (e.nc - 1) * e.sh) / 2
    # talas internas: encostadas na ponta da mesa (borda externa = e_2c); n_li linhas em cada
    n_int = (1 if eh_u else 2) if e.talas_internas else 0
    n_li = e.nl // max(n_int, 1)
    e2i = e.bi - e2c - (n_li - 1) * e.g  # da linha mais interna à borda da tala junto à alma
    bi_max = (bf_min - tw_max - R) if eh_u else ((bf_min - tw_max) / 2 - R)
    A_ext, A_int = e.bp * e.tp, n_int * e.bi * e.ti
    frac_ext = A_ext / (A_ext + A_int)
    n_planos = 2 if e.talas_internas else 1
    Lp = 2 * (e.ec + (e.nr - 1) * e.s + e.ep) + e.gap
    Lw = 2 * (e.ewc + (e.m - 1) * e.sv + e.ewv) + e.gap
    exc_alma = e.ewc + (e.m - 1) * e.sv / 2 + e.gap / 2
    _, W_net_p = modulo_liquido(e.bp, e.tp, dhn, posicoes_dos_furos(e.nl, e.g), 1)
    _, W_net_w = modulo_liquido(e.bw, e.twp, dhn, posicoes_dos_furos(e.nc, e.sh), 2)

    # 3.4 esforços por caso
    todos = [(c, "usuário") for c in e.casos]
    if minimo.caso is not None:
        todos.append((minimo.caso, f"mínimo 6.1.6.2 ({minimo.adotado})"))
    casos: list[EsforcosDoCaso] = []
    for c, origem in todos:
        Fft, Ffc = forcas_nas_mesas(c.N, c.Mx, z, k)
        Tf = max(0.0, Fft)
        Cf = 0.0 if e.contato else max(0.0, Ffc)
        Cc = max(0.0, Ffc) if e.contato else 0.0
        Mf = abs(c.My) / 2  # kN·m
        mesa_g = grupo_da_mesa(max(Tf, Cf), Mf * 1000, e.nl, e.nr, e.g, e.s)
        Nw = max(0.0, -c.N) * aw if e.contato else abs(c.N) * aw
        alma_g = grupo_da_alma(c.V, Nw, e.m, e.nc, e.sv, e.sh, exc_alma)
        casos.append(
            EsforcosDoCaso(
                c.nome, origem, c.N, c.Mx, c.V, c.My, Fft, Ffc, Tf, Cf, Cc, Mf,
                mesa_g.resultante, Nw, abs(c.V) * exc_alma / 1000, alma_g.componente_1,
                alma_g.componente_2, alma_g.resultante,
            )
        )  # fmt: skip

    def _max(attr: str) -> float:
        return max((getattr(x, attr) for x in casos), default=0.0)

    T, C, Cc = _max("Tf"), _max("Cf"), _max("Cc")
    env = {
        "Ffr_max": _max("Ffr"), "Mf_max": _max("Mf"), "T": T, "C": C, "Cc": Cc,
        "Fmax": max(T, C), "Vmax": max(abs(x.V) for x in casos), "Nw_max": _max("Nw"),
        "Mw_max": _max("Mw"), "Rw_max": _max("Rw"),
    }  # fmt: skip
    longa = (e.nr - 1) * e.s > LIGACAO_LONGA_MM and not e.verificar_deslizamento and T > 0
    fator_longa = FATOR_LIGACAO_LONGA if longa else 1.0

    # 4.1 mesa
    def fc(lf: float, t: float, f_u: float) -> float:
        return resist_contato(lf, t, f_u, db, g2)

    R5 = e.bp * e.tp * fyp / g1 / 1000
    R6 = min((e.bp - e.nl * dhn) * e.tp, 0.85 * e.bp * e.tp) * fup / g2 / 1000

    def rasgamento(
        eb: float, t: float, bordas: float, f_y: float, f_u: float, central: bool,
        n_linhas: int | None = None, n_pecas: int = 1,
    ) -> float:  # fmt: skip
        """Nota A. ``bordas`` = soma das distâncias às duas bordas laterais; ``n_pecas`` iguais."""
        nl = e.nl if n_linhas is None else n_linhas
        Agv, Anv, Ant_c = bc.areas_bloco_central(eb, e.s, e.g, nl, e.nr, t, dh, NORMA)
        Ant = Ant_c if central else (bordas - dhn) * t
        return n_pecas * resist_rasgamento(Agv, Anv, Ant, f_y, f_u, g2)

    def rasgamento_em_l(
        eb: float, t: float, borda: float, n_linhas: int, f_y: float, f_u: float
    ) -> float:
        """Bloco em L: um plano de cisalhamento (na linha do outro lado) e tração até uma borda."""
        Agv = (eb + (e.nr - 1) * e.s) * t
        Anv = Agv - (e.nr - 0.5) * dhn * t
        Ant = (borda + (n_linhas - 1) * e.g - (n_linhas - 0.5) * dhn) * t
        return resist_rasgamento(Agv, Anv, Ant, f_y, f_u, g2)

    def rasgamento_mesa_u() -> float:
        """U: um plano de cisalhamento (a linha junto à alma) e tração até a borda livre."""
        return rasgamento_em_l(e.ec, tf_min, e2c, e.nl, fy, fu)

    def rasgamento_internas() -> float:
        """Cada tala interna: o menor entre as duas bordas (nota A) e o L para cada borda."""
        return n_int * min(
            rasgamento(e.ep, e.ti, e2c + e2i, fyp, fup, False, n_li, 1),
            rasgamento_em_l(e.ep, e.ti, e2c, n_li, fyp, fup),
            rasgamento_em_l(e.ep, e.ti, e2i, n_li, fyp, fup),
        )

    def comprimida(b: float, t: float, n: int) -> float:
        """Nota B: tala comprimida entre as fileiras junto à emenda (NBR 6.5.4)."""
        Le = COEF_COMPRIMENTO_TALA * (2 * e.ec + e.gap)
        r = t / math.sqrt(12)
        chi = 1.0
        if Le / r > LIMITE_ESBELTEZ_TALA:
            chi = fator_chi((Le / r) / math.pi * math.sqrt(fyp / e.E))
        return chi * n * b * t * fyp / g1 / 1000

    R9 = None if e.contato else comprimida(e.bp, e.tp, 1)
    T_ext, C_ext = T * frac_ext, C * frac_ext
    T_int, C_int = T - T_ext, C - C_ext
    internas = e.talas_internas

    # 1b: tala da mesa com flexão em y
    Ap, Af = A_ext, bf_min * tf_min
    Wp, W_mesa = e.tp * e.bp**2 / 6, tf_min * bf_min**2 / 6
    tem_my = env["Mf_max"] > 0
    dispensa_1b = Ap >= Af and Wp >= W_mesa
    Mrd_p = W_net_p * fyp / g1 / 1e6  # kN·m
    # com talas internas, a externa leva a fração da área dela (força e momento)
    inter = max(
        (frac_ext * (max(x.Tf, x.Cf) / min(R5, R6) + x.Mf / Mrd_p) for x in casos), default=0.0
    )
    if not tem_my:
        linha_1b = _linha("1b. Tala da mesa: força axial + flexão em y", None, None, "–",
                          "SCI P207 5.3 passo 5; NBR 6.5.3", "F_f/R_d + M_f/(W_net,p·f_y,p/γ_a1) ≤ 1",
                          ativa=False)  # fmt: skip
    elif dispensa_1b:
        linha_1b = Verificacao(
            "1b. Tala da mesa: força axial + flexão em y", None, None, "–",
            "SCI P207 5.3 passo 5", "dispensada: A_p ≥ A_f e W_p ≥ W_mesa", status="OK",
            tipo="limite",
        )  # fmt: skip
    else:
        linha_1b = _linha("1b. Tala da mesa: força axial + flexão em y", inter, 1.0, "–",
                          "SCI P207 5.3 passo 5; NBR 6.5.3",
                          "F_f/min(R5; R6) + M_f/(W_net,p·f_y,p/γ_a1) ≤ 1")  # fmt: skip

    dupla = "corte duplo" if internas else "corte simples"
    nota_ext = " (parcela da tala externa)" if internas else ""
    bordas_ext = e2 + e2_alma
    mesa = [
        _linha(f"1. Corte do parafuso mais solicitado da mesa ({dupla})",
               nb * env["Ffr_max"] * fator_longa, nb * n_planos * Fv * beta_f, "kN",
               "NBR 6.3.3.2; 6.5.7.2; SCI P207 passo 5",
               f"n_b·F_f,r,máx ≤ n_b·{n_planos}·F_v,Rd·β_f"
               + (" (×1,20, ligação longa 6.3.8)" if longa else "")),
        linha_1b,
        _linha("2. Pressão de contato na tala externa, tração" + nota_ext, T_ext,
               e.nl * (fc(e.ep - dh / 2, e.tp, fup) + (e.nr - 1) * fc(e.s - dh, e.tp, fup)), "kN",
               "NBR 6.3.3.3 a", "n_l·[F_c(e_p − d_h/2) + (n_r − 1)·F_c(s − d_h)]"),
        _linha("3. Pressão de contato na mesa do pilar, tração", T,
               e.nl * (fc(e.ec - dh / 2, tf_min, fu) + (e.nr - 1) * fc(e.s - dh, tf_min, fu)), "kN",
               "NBR 6.3.3.3 a", "n_l·[F_c(e_c − d_h/2) + (n_r − 1)·F_c(s − d_h)]"),
        _linha("4. Pressão de contato, compressão" + (" (mesa e tala externa)" if internas else ""),
               C, nb * min(fc(e.s - dh, e.tp, fup) / frac_ext, fc(e.s - dh, tf_min, fu)), "kN",
               "NBR 6.3.3.3 a",
               "n_b·mín[F_c(s − d_h, t_p)/fração externa, F_c(s − d_h, t_f)]" if internas
               else "n_b·mín[F_c(s − d_h, t_p), F_c(s − d_h, t_f)]", ativa=not e.contato),
        _linha("5. Tala externa da mesa, escoamento da seção bruta" + nota_ext, T_ext, R5, "kN",
               "NBR 6.5.3 a", "b_p·t_p·f_y,p/γ_a1"),
        _linha("6. Tala externa da mesa, ruptura da seção líquida" + nota_ext, T_ext, R6, "kN",
               "NBR 6.5.3 b", "mín[(b_p − n_l·d_h,n)·t_p ; 0,85·b_p·t_p]·f_u,p/γ_a2"),
        _linha("7. Tala externa da mesa, colapso por rasgamento até as bordas" + nota_ext, T_ext,
               rasgamento(e.ep, e.tp, bordas_ext, fyp, fup, False), "kN", "NBR 6.5.6 (C_ts = 1)",
               "mín(0,6·f_u·A_nv + f_u·A_nt ; 0,6·f_y·A_gv + f_u·A_nt)/γ_a2"),
        _linha("8. Tala externa da mesa, colapso por rasgamento do bloco central" + nota_ext,
               T_ext, rasgamento(e.ep, e.tp, bordas_ext, fyp, fup, True), "kN",
               "NBR 6.5.6 (C_ts = 1)", "A_nt = (n_l − 1)·(g − d_h,n)·t_p", ativa=e.nl > 1),
        _linha("9. Tala externa da mesa comprimida" + nota_ext, C_ext, R9, "kN", "NBR 6.5.4",
               "K·L/r ≤ 25: b_p·t_p·f_y,p/γ_a1; senão χ·b_p·t_p·f_y,p/γ_a1", ativa=not e.contato),
        _linha("2i. Pressão de contato nas talas internas, tração", T_int,
               e.nl * (fc(e.ep - dh / 2, e.ti, fup) + (e.nr - 1) * fc(e.s - dh, e.ti, fup)), "kN",
               "NBR 6.3.3.3 a", "n_l·[F_c(e_p − d_h/2, t_i) + (n_r − 1)·F_c(s − d_h, t_i)]",
               ativa=internas),
        _linha("4i. Pressão de contato nas talas internas, compressão", C_int,
               nb * fc(e.s - dh, e.ti, fup), "kN", "NBR 6.3.3.3 a", "n_b·F_c(s − d_h, t_i)",
               ativa=internas and not e.contato),
        _linha("5i. Talas internas, escoamento da seção bruta", T_int,
               n_int * e.bi * e.ti * fyp / g1 / 1000, "kN", "NBR 6.5.3 a",
               "n_int·b_i·t_i·f_y,p/γ_a1", ativa=internas),
        _linha("6i. Talas internas, ruptura da seção líquida", T_int,
               min(n_int * (e.bi - n_li * dhn) * e.ti, 0.85 * n_int * e.bi * e.ti) * fup / g2 / 1000,
               "kN", "NBR 6.5.3 b",
               "mín[n_int·(b_i − n_li·d_h,n)·t_i ; 0,85·n_int·b_i·t_i]·f_u,p/γ_a2", ativa=internas),
        _linha("7i. Talas internas, colapso por rasgamento até as bordas", T_int,
               rasgamento_internas() if internas else None, "kN", "NBR 6.5.6 (C_ts = 1)",
               "n_int·mín(nota A com e_2c e e_2i ; bloco em L até e_2c ; em L até e_2i)",
               ativa=internas),
        _linha("8i. Talas internas, colapso por rasgamento do bloco central", T_int,
               rasgamento(e.ep, e.ti, 0.0, fyp, fup, True, n_li, n_int) if internas else None,
               "kN", "NBR 6.5.6 (C_ts = 1)", "A_nt = n_int·(n_li − 1)·(g − d_h,n)·t_i",
               ativa=internas and n_li > 1),
        _linha("9i. Talas internas comprimidas", C_int,
               comprimida(e.bi, e.ti, n_int) if internas else None, "kN", "NBR 6.5.4",
               "K·L/r ≤ 25: n_int·b_i·t_i·f_y,p/γ_a1; senão com χ",
               ativa=internas and not e.contato),
        _linha("10. Mesa do pilar, colapso por rasgamento"
               + (" até a borda livre (U)" if eh_u else " até as bordas"), T,
               rasgamento_mesa_u() if eh_u else rasgamento(e.ec, tf_min, 2 * e2c, fy, fu, False),
               "kN", "NBR 6.5.6 (C_ts = 1)",
               "U: um plano junto à alma e tração até a borda livre" if eh_u
               else "nota A com e_c, t_f,mín, e_2c"),
        _linha("11. Mesa do pilar, ruptura da seção líquida", T,
               (bf_min - e.nl * dhn) * tf_min * fu / g2 / 1000, "kN", "NBR 6.5.3 b",
               "(b_f,mín − n_l·d_h,n)·t_f,mín·f_u/γ_a2"),
        _linha("12. Compressão por contato das extremidades usinadas", Cc,
               COEF_CONTATO_USINADO * bf_min * tf_min * fy / g2 / 1000, "kN", "NBR 6.6.2",
               "1,8·b_f,mín·t_f,mín·f_y/γ_a2", ativa=e.contato),
        _linha("13. Deslizamento dos parafusos da mesa (ELS)", e.fator_servico * env["Fmax"],
               nb * bc.resist_deslizamento(F_Tb, mu, NORMA, n_planos, 1.0), "kN", "NBR 6.3.4.4",
               f"n_b·0,80·μ·C_e·F_Tb·{n_planos} (C_e = 1)", ativa=e.verificar_deslizamento),
    ]  # fmt: skip

    # 4.2 alma
    Rw = env["Rw_max"] * fator_longa
    alma = [
        _linha("14. Corte do parafuso mais solicitado da alma (corte duplo)", Rw, 2 * Fv * beta_w,
               "kN", "NBR 6.3.3.2; 6.5.7.2", "R_w,máx ≤ 2·F_v,Rd·β_w"),
        _linha("15. Pressão de contato na alma do pilar", Rw,
               fc(min(e.ewc - dh / 2, e.sv - dh if e.m > 1 else math.inf,
                      e.sh - dh if e.nc > 1 else math.inf), tw_min, fu), "kN", "NBR 6.3.3.3 a",
               "F_c(mín(e_wc − d_h/2, s_v − d_h, s_h − d_h), t_w,mín)"),
        _linha("16. Pressão de contato nas 2 talas da alma", Rw,
               fc(min(e.ewv - dh / 2, ewh - dh / 2, e.sv - dh if e.m > 1 else math.inf,
                      e.sh - dh if e.nc > 1 else math.inf), 2 * e.twp, fup), "kN",
               "NBR 6.3.3.3 a", "F_c(mín(e_wv − d_h/2, e_wh − d_h/2, s_v − d_h, s_h − d_h), 2·t_w,p)"),
        _linha("17. Talas da alma, cortante, escoamento", env["Vmax"],
               0.6 * fyp * 2 * e.bw * e.twp / g1 / 1000, "kN", "NBR 6.5.5 a",
               "0,6·f_y,p·2·b_w·t_w,p/γ_a1"),
        _linha("18. Talas da alma, cortante, ruptura", env["Vmax"],
               0.6 * fup * 2 * (e.bw - e.nc * dhn) * e.twp / g2 / 1000, "kN", "NBR 6.5.5 b",
               "0,6·f_u,p·2·(b_w − n_c·d_h,n)·t_w,p/γ_a2"),
        _linha("19. Talas da alma, flexão no plano (M = V·e)", env["Mw_max"],
               W_net_w * fyp / g1 / 1e6, "kN·m", "NBR 6.5; SCI P207 5.4",
               "W_net·f_y,p/γ_a1 (2 talas, seção líquida elástica)"),
        _linha("20. Talas da alma, força axial, escoamento", env["Nw_max"],
               2 * e.bw * e.twp * fyp / g1 / 1000, "kN", "NBR 6.5.3 a", "2·b_w·t_w,p·f_y,p/γ_a1"),
        _linha("21. Talas da alma, força axial, ruptura", env["Nw_max"],
               min(2 * (e.bw - e.nc * dhn) * e.twp, 0.85 * 2 * e.bw * e.twp) * fup / g2 / 1000,
               "kN", "NBR 6.5.3 b", "mín[2·(b_w − n_c·d_h,n)·t_w,p ; 0,85·2·b_w·t_w,p]·f_u,p/γ_a2"),
        _linha("22. Deslizamento do parafuso mais solicitado da alma (ELS, 2 planos)",
               e.fator_servico * env["Rw_max"], bc.resist_deslizamento(F_Tb, mu, NORMA, 2, 1.0),
               "kN", "NBR 6.3.4.4", "0,80·μ·F_Tb·2", ativa=e.verificar_deslizamento),
    ]  # fmt: skip

    # 4.3 disposições construtivas
    ext = e.ec + (e.nr - 1) * e.s + e.ep
    t_atrito = min(db / 2, TALA_ATRITO_MAXIMO_MM)
    esp_min = ESPACAMENTO_MINIMO_DB * db
    bordas = {"e_p": e.ep, "e_c": e.ec, "e_2": min(e2, e2_alma), "e_2c": e2c, "e_wv": e.ewv,
              "e_wc": e.ewc, "e_wh": ewh}  # fmt: skip
    if internas:
        bordas["e_2i"] = e2i
    lim_borda_p = min(BORDA_MAXIMA_T * e.tp, BORDA_MAXIMA_MM)
    lim_borda_w = min(BORDA_MAXIMA_T * e.twp, BORDA_MAXIMA_MM)
    lim_borda_i = min(BORDA_MAXIMA_T * e.ti, BORDA_MAXIMA_MM)
    lim_esp_f = min(
        ESPACAMENTO_MAXIMO_T * min(e.tp, tf_min, e.ti if internas else math.inf),
        ESPACAMENTO_MAXIMO_MM,
    )
    lim_esp_w = min(ESPACAMENTO_MAXIMO_T * min(e.twp, tw_min), ESPACAMENTO_MAXIMO_MM)
    esp_f = [x for x, n in ((e.s, e.nr), (e.g, e.nl)) if n > 1]
    esp_w = [x for x, n in ((e.sh, e.nc), (e.sv, e.m)) if n > 1]
    disp = [
        _regra("Diâmetro mínimo do parafuso", db, "d_b ≥ 15,875 mm (5/8\")", db >= DIAMETRO_MINIMO - 1e-9,
               "Anglo 8.8"),
        _regra("Diâmetro máximo preferido", db, "d_b ≤ 25,4 mm (1\")",
               db <= DIAMETRO_PREFERIDO_MAXIMO + 1e-9, "Anglo 9.1"),
        _regra("Espessura da tala da mesa", e.tp, "t_p ≥ 8 mm", e.tp >= ESPESSURA_MINIMA_TALA, "Anglo 8.8"),
        _regra("Espessura das talas da alma", e.twp, "t_w,p ≥ 8 mm", e.twp >= ESPESSURA_MINIMA_TALA,
               "Anglo 8.8"),
        _regra("Largura da tala da mesa", e.bp, f"b_p ≤ b_f,mín = {_n(bf_min)} mm", e.bp <= bf_min + 1e-9,
               "geometria"),
        _regra("Largura das talas da alma", e.bw, f"b_w ≤ d'_mín = {_n(dl_min)} mm", e.bw <= dl_min + 1e-9,
               "geometria"),
        _regra("Espaçamento mínimo na mesa (s, g)", min(e.s, e.g) if e.nl > 1 else e.s,
               f"≥ 3·d_b = {_n(esp_min)} mm (mínimo absoluto 2,7·d_b)",
               min(esp_f, default=math.inf) >= esp_min - 1e-9, "NBR 6.3.9", ativa=bool(esp_f)),
        _regra("Espaçamento mínimo na alma (s_h, s_v)", min(esp_w, default=0.0),
               f"≥ 3·d_b = {_n(esp_min)} mm", min(esp_w, default=math.inf) >= esp_min - 1e-9,
               "NBR 6.3.9", ativa=bool(esp_w)),
        _regra("Distância mínima às bordas", min(bordas.values()),
               f"{', '.join(bordas)} ≥ {_n(borda_min)} mm",
               min(bordas.values()) >= borda_min - 1e-9, "NBR 6.3.11, Tab. 16"),
        _regra("Distância máxima às bordas, tala da mesa", max(e.ep, e2, e2_alma),
               f"máx(e_p, e_2) ≤ mín(12·t_p ; 150) = {_n(lim_borda_p)} mm",
               max(e.ep, e2, e2_alma) <= lim_borda_p + 1e-9, "NBR 6.3.12"),
        _regra("Distância máxima às bordas, talas internas", max(e.ep, e2c, e2i),
               f"máx(e_p, e_2c, e_2i) ≤ mín(12·t_i ; 150) = {_n(lim_borda_i)} mm",
               max(e.ep, e2c, e2i) <= lim_borda_i + 1e-9, "NBR 6.3.12", ativa=internas),
        _regra("Espessura das talas internas", e.ti, "t_i ≥ 8 mm", e.ti >= ESPESSURA_MINIMA_TALA,
               "Anglo 8.8", ativa=internas),
        _regra("Largura das talas internas", e.bi,
               f"b_i ≤ {'b_f − t_w − R' if eh_u else '(b_f − t_w)/2 − R'} = {_n(bi_max)} mm",
               e.bi <= bi_max + 1e-9, "geometria (cabe ao lado da alma e do raio)", ativa=internas),
        _regra("Raio de concordância do U informado", R, "R > 0 (o catálogo não traz o raio)",
               R > 0, "conferir no catálogo do fabricante", ativa=eh_u),
        _regra("Distância máxima às bordas, talas da alma", max(e.ewv, ewh),
               f"máx(e_wv, e_wh) ≤ mín(12·t_w,p ; 150) = {_n(lim_borda_w)} mm",
               max(e.ewv, ewh) <= lim_borda_w + 1e-9, "NBR 6.3.12"),
        _regra("Espaçamento máximo na mesa", max(esp_f, default=0.0),
               f"máx(s, g) ≤ mín(24·t ; 300) = {_n(lim_esp_f)} mm",
               max(esp_f, default=0.0) <= lim_esp_f + 1e-9, "NBR 6.3.10 a", ativa=bool(esp_f)),
        _regra("Espaçamento máximo na alma", max(esp_w, default=0.0),
               f"máx(s_h, s_v) ≤ mín(24·t ; 300) = {_n(lim_esp_w)} mm",
               max(esp_w, default=0.0) <= lim_esp_w + 1e-9, "NBR 6.3.10 a", ativa=bool(esp_w)),
        _regra("Folga para porca e arruela junto ao raio", folga,
               f"{'x1 − t_w,máx − R' if eh_u else 'g/2 − t_w,máx/2 − R'} ≥ d_b = {_n(db, 2)} mm",
               folga >= db - 1e-9,
               "aproximação do raio da arruela F436"),
        _regra("Parafusos por lado da emenda (mesa e alma)", float(min(nb, nbw)), "n ≥ 2",
               min(nb, nbw) >= PARAFUSOS_MINIMOS, "Anglo 9.1", unidade="–"),
        _regra("Enchimento na mesa", tsf, "t_s,f ≤ 19 mm", tsf <= ENCHIMENTO_MAXIMO, "NBR 6.5.7.2"),
        _regra("Fresta com contato", e.gap,
               "gap ≤ 2 mm (entre 2 e 6,3 mm, preencher com calços de aço)",
               e.gap <= GAP_MAXIMO_CONTATO + 1e-9, "NBR 12.3.5", ativa=e.contato),
        _regra("Continuidade: área da tala da mesa", Ap + A_int,
               f"{'b_p·t_p + n_int·b_i·t_i' if internas else 'b_p·t_p'} ≥ b_f·t_f = {_n(Af, 0)} mm²",
               Ap + A_int >= Af - 1e-9, "SCI P207 5.2.4", unidade="mm²"),
        _regra("Continuidade: extensão de cada lado", ext,
               f"e_c + (n_r − 1)·s + e_p ≥ máx(b_f,mín ; 225) = {_n(max(bf_min, EXTENSAO_MINIMA_MM))} mm",
               ext >= max(bf_min, EXTENSAO_MINIMA_MM) - 1e-9, "SCI P207 5.2.4"),
        _regra("Espessura mínima das talas em ligação por atrito", min(e.tp, e.twp),
               f"t_p, t_w,p ≥ mín(d_b/2 ; 10) = {_n(t_atrito)} mm",
               min(e.tp, e.twp) >= t_atrito - 1e-9, "SCI P207 passos 3 e 4 (BS 4604)",
               ativa=e.verificar_deslizamento),
        _regra("Ligação longa", (e.nr - 1) * e.s, "(n_r − 1)·s ≤ 950 mm (senão forças ×1,20)",
               not longa, "NBR 6.3.8"),
    ]  # fmt: skip

    avisos = list(AVISOS_FIXOS)
    if invalida and e.Nc_Rd_informado is None:
        avisos.insert(
            0, "Perfil com elemento esbelto (flambagem local): estimativa inválida, informe N_c,Rd."
        )
    if longa:
        avisos.append(
            "Ligação longa (NBR 6.3.8): as forças nos parafusos foram multiplicadas por 1,20."
        )
    if any(abs(c.Mx) > 0 for c in e.casos) and not e.verificar_deslizamento:
        avisos.append(AVISO_MOMENTO_SEM_ATRITO)
    if not e.contato and e.gap > GAP_MAXIMO_CONTATO:
        avisos.append(
            "Sem contato: toda a compressão passa pelas talas e pelos parafusos (verificações 4 e 9)."
        )
    if eh_u:
        avisos.append(
            "Perfil U: a estimativa de N_c,Rd não considera a flambagem por flexo-torção; informe o "
            "N_c,Rd (página Flambagem de colunas). Com M_y, a excentricidade do centro de "
            "cisalhamento não entra."
        )
    if internas:
        avisos.append(
            f"Talas internas: a força da mesa se divide pela área ({_n(100 * frac_ext, 0)} % na "
            "externa); os parafusos da mesa trabalham em corte duplo."
        )
    if tem_my and dispensa_1b:
        avisos.append(
            "Flexão em y: tala da mesa pelo menos igual à mesa; a verificação 1b fica dispensada."
        )

    props = {
        "bf_min": bf_min, "tf_min": tf_min, "tw_min": tw_min, "tw_max": tw_max, "dl_min": dl_min,
        "db": db, "dh": dh, "dhn": dhn, "Ab": Ab, "fub": bc.fub(grau, db, NORMA), "Fv_Rd": Fv,
        "F_Tb": F_Tb, "mu": mu, "borda_min": float(borda_min), "tsf": tsf, "tsw": tsw,
        "beta_f": beta_f, "beta_w": beta_w, "alfa_f": alfa_f, "alfa_w": alfa_w, "z": z, "nb": nb,
        "nbw": nbw, "e2": e2, "e2c": e2c, "ewh": ewh, "folga": folga, "Lp": Lp, "Lw": Lw,
        "exc_alma": exc_alma, "W_net_p": W_net_p, "W_net_w": W_net_w, "extensao": ext,
        "fy": fy, "fu": fu, "fyp": fyp, "fup": fup, "R": R, "e2_lado_alma": e2_alma,
        "n_int": n_int, "n_li": n_li, "e2i": e2i, "bi_max": bi_max, "fracao_externa": frac_ext,
        "n_planos_mesa": n_planos,
    }  # fmt: skip
    return ResultadoEmenda(
        entrada=e, superior=sup, inferior=inf, propriedades=props, estimativa_invalida=invalida,
        Nc_Rd_estimado=Nc_est, Nc_Rd=Nc_Rd, lambda0=lambda0, chi=chi, minimo=minimo, casos=casos,
        envoltoria=env, mesa=mesa, alma=alma, disposicoes=disp, avisos=avisos,
        notas_de_desenho=NOTAS_DE_DESENHO_CONTATO if e.contato else (),
    )  # fmt: skip


def verificacao(r: ResultadoEmenda, numero: str) -> Verificacao:
    """A linha pelo número ("1", "1b", "14"...)."""
    return next(v for v in r.mesa + r.alma if v.nome.split(".")[0] == numero)


def disposicao(r: ResultadoEmenda, inicio: str) -> Verificacao:
    return next(v for v in r.disposicoes if v.nome.startswith(inicio))


# ---------------------------------------------------------------------------------------------
# SAÍDAS
# ---------------------------------------------------------------------------------------------
COLUNAS_ESFORCOS = {
    "nome": "Caso", "origem": "Origem", "N": "N (kN)", "Mx": "M_x (kN·m)", "V": "V (kN)",
    "My": "M_y (kN·m)", "Fft": "F_f,t (kN)", "Ffc": "F_f,c (kN)", "Tf": "T_f (kN)",
    "Cf": "C_f (kN)", "Cc": "C_c (kN)", "Mf": "M_f (kN·m)", "Ffr": "F_f,r (kN)",
    "Nw": "N_w (kN)", "Mw": "M_w (kN·m)", "Rh": "R_h (kN)", "Rv": "R_v (kN)", "Rw": "R_w (kN)",
}  # fmt: skip


def tabela_de_esforcos(r: ResultadoEmenda) -> list[dict[str, Any]]:
    return [{COLUNAS_ESFORCOS[k]: v for k, v in asdict(c).items()} for c in r.casos]


def resumo(r: ResultadoEmenda) -> dict[str, str]:
    e, p = r.entrada, r.propriedades
    g = r.governante
    internas = (
        f"; talas internas {p['n_int']} × {_n(e.bi)} × {_n(e.ti)} × {_n(p['Lp'])} mm (corte duplo)"
        if e.talas_internas
        else ""
    )
    return {
        "Perfis": f"superior {e.perfil_superior}; inferior {e.perfil_inferior} ({e.aco_perfis})",
        "Parafusos": f"{e.diametro} {e.grau}, rosca {'no' if e.rosca_no_plano else 'fora do'} plano",
        "Tala da mesa": f"{_n(e.bp)} × {_n(e.tp)} × {_n(p['Lp'])} mm, {p['nb']} parafusos por lado"
        + internas,
        "Talas da alma": f"2 × {_n(e.bw)} × {_n(e.twp)} × {_n(p['Lw'])} mm, {p['nbw']} parafusos "
        "por lado",
        "Total de parafusos": str(r.total_de_parafusos),
        "Enchimentos": f"mesa {_n(p['tsf'])} mm (β_f = {_n(p['beta_f'], 3)}); alma "
        f"{_n(p['tsw'])} mm (β_w = {_n(p['beta_w'], 3)})",
        "N_c,Rd adotado": f"{_n(r.Nc_Rd)} kN ({'informado' if e.Nc_Rd_informado else 'estimado'})",
        "Situação mínima": {
            "a": "a (tração 0,5·N_c,Rd)",
            "b": "b (força transversal 0,02·N_c,Rd)",
        }.get(r.minimo.adotado, "nenhuma"),
        "Utilização máxima": f"{100 * r.utilizacao_maxima:.0f} % ({g.nome if g else '–'})",
        "Situação geral": r.resumo_da_situacao,
    }


def entradas_planas(e: EntradaEmenda) -> list[tuple[str, Any]]:
    dados = asdict(e)
    dados.pop("casos")
    return list(dados.items()) + [
        (f"caso {i + 1}", f"{c.nome}: N={c.N}, Mx={c.Mx}, V={c.V}, My={c.My}")
        for i, c in enumerate(e.casos)
    ]


def csv_completo(r: ResultadoEmenda) -> bytes:
    """Entradas, esforços e verificações num CSV só (separador ;)."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Entradas"])
    w.writerows(entradas_planas(r.entrada))
    w.writerow([])
    w.writerow(["Esforços por caso"])
    linhas = tabela_de_esforcos(r)
    w.writerow(list(COLUNAS_ESFORCOS.values()))
    w.writerows([list(x.values()) for x in linhas])
    for titulo, lista in (("Mesa", r.mesa), ("Alma", r.alma), ("Disposições", r.disposicoes)):
        w.writerow([])
        w.writerow([titulo])
        tab = linhas_para_registro(lista)
        if tab:
            w.writerow(list(tab[0].keys()))
            w.writerows([list(x.values()) for x in tab])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def xlsx_completo(r: ResultadoEmenda) -> bytes:
    """Excel com as abas Entradas, Esforços e Verificações."""
    import pandas as pd

    saida = io.BytesIO()
    with pd.ExcelWriter(saida, engine="openpyxl") as escritor:
        pd.DataFrame(entradas_planas(r.entrada), columns=["Campo", "Valor"]).to_excel(
            escritor, sheet_name="Entradas", index=False
        )
        pd.DataFrame(tabela_de_esforcos(r)).to_excel(escritor, sheet_name="Esforços", index=False)
        linhas = []
        for grupo, lista in (("Mesa", r.mesa), ("Alma", r.alma), ("Disposições", r.disposicoes)):
            linhas += [{"Grupo": grupo, **x} for x in linhas_para_registro(lista)]
        pd.DataFrame(linhas).to_excel(escritor, sheet_name="Verificações", index=False)
    return saida.getvalue()


# ---------------------------------------------------------------------------------------------
# SUGERIR AS TALAS
# ---------------------------------------------------------------------------------------------
#: Limites da busca: até onde o programa sobe as fileiras antes de engrossar a tala.
FILEIRAS_MAXIMAS = 8
FILEIRAS_MAXIMAS_ALMA = 6
#: Que verificação reprovada muda o quê: as do pilar (10 a 12) as talas não resolvem.
DO_PILAR = {"10", "11", "12"}
PARAFUSOS_DA_MESA = {"1", "2", "2i", "3", "4", "4i", "13"}
TALA_DA_MESA = {"1b", "5", "6", "7", "8", "9", "5i", "6i", "7i", "8i", "9i"}
PARAFUSOS_DA_ALMA = {"14", "15", "16", "22"}
TALAS_DA_ALMA = {"17", "18", "19", "20", "21"}


def _acima(valor: float, passo: float = 5.0) -> float:
    return math.ceil(valor / passo - 1e-9) * passo


def _abaixo(valor: float, passo: float = 5.0) -> float:
    return math.floor(valor / passo + 1e-9) * passo


def _chapa_acima(t: float) -> float:
    """A primeira espessura de chapa comercial ≥ t (core.medidas_comerciais.CHAPAS)."""
    return next((c for c in mc.CHAPAS.valores if c >= t - 1e-9), mc.CHAPAS.valores[-1])


@dataclass(frozen=True)
class Sugestao:
    entrada: EntradaEmenda
    resultado: ResultadoEmenda | None
    notas: tuple[str, ...]
    cabe: bool  # False: o parafuso não cabe na mesa ou na alma deste perfil

    @property
    def atende(self) -> bool:
        return self.cabe and self.resultado is not None and self.resultado.situacao == "ATENDE"


def sugerir_talas(e: EntradaEmenda) -> Sugestao:
    """As talas montadas pelas regras da página para o perfil e o parafuso de ``e``.

    Mesa: tala da largura da mesa (múltiplo de 5 mm, ≤ b_f) com espessura comercial ≥ t_f e
    ≥ 8 mm (continuidade e Anglo 8.8); duas linhas no W (uma linha no U) com o gabarito que deixa
    a folga da porca junto ao raio; passo 3·d_b e bordas de 2·d_b (≥ Tabela 16), arredondados a
    5 mm; fileiras que dão a extensão de 225 mm do SCI P207 5.2.4. Alma: duas colunas e duas
    fileiras dentro do d'. Se a resistência não atende, sobe as fileiras (até 8 na mesa e 6 na
    alma) e, depois, a espessura da tala. Não troca o parafuso: isso é escolha de quem projeta.
    """
    erros = [x for x in validar(e) if "tala" not in x.lower() and "furos" not in x.lower()]
    if erros:
        raise ValueError(" ".join(erros))
    sup, inf = PERFIS[e.perfil_superior], PERFIS[e.perfil_inferior]
    eh_u = sup.familia == FAMILIA_U
    db = diametro_do_parafuso(e.diametro)
    borda = float(bc.PARAFUSOS[e.diametro][2])
    bf, tf = min(sup.bf, inf.bf), min(sup.tf, inf.tf)
    tw = max(sup.tw, inf.tw)
    R = e.raio_u if eh_u else sup.R
    dl = (min(sup.h, inf.h) - 2 * e.raio_u) if eh_u else min(sup.d_linha, inf.d_linha)
    passo = _acima(ESPACAMENTO_MINIMO_DB * db)
    ponta = _acima(max(borda, 2 * db))
    notas: list[str] = []
    cabe = True

    bp = _abaixo(bf)
    if eh_u:
        nl, g = 1, passo
        x1 = _acima(tw + R + db)
        if bp - x1 < borda or bf - x1 < borda:
            cabe = False
            notas.append(
                f"O parafuso {e.diametro} não cabe na mesa do {e.perfil_superior}: do dorso à "
                f"linha de furos são {_n(x1)} mm e sobram {_n(bf - x1)} mm até a borda (mínimo "
                f"{_n(borda)} mm). Escolha um parafuso menor."
            )
    else:
        nl, x1 = 2, e.x1_u
        g = _acima(max(passo, 2 * (db + tw / 2 + R)))
        if (bf - g) / 2 < borda:
            cabe = False
            notas.append(
                f"Duas linhas de {e.diametro} não cabem na mesa de {_n(bf)} mm: o gabarito que "
                f"deixa a folga da porca é {_n(g)} mm e sobrariam {_n((bf - g) / 2)} mm até a "
                f"borda (mínimo {_n(borda)} mm). Escolha um parafuso menor."
            )
    tp = _chapa_acima(max(ESPESSURA_MINIMA_TALA, bf * tf / bp))
    extensao = max(bf, EXTENSAO_MINIMA_MM)
    nr = max(2, math.ceil((extensao - 2 * ponta) / passo - 1e-9) + 1)

    nc, m = 2, 2
    bw = _abaixo(dl)
    if bw < passo + 2 * borda:
        nc = 1
        if bw < 2 * borda:
            cabe = False
            notas.append(
                f"A alma do {e.perfil_superior} (d' = {_n(dl)} mm) não comporta o parafuso "
                f"{e.diametro} com as bordas mínimas."
            )
    bw = min(bw, _acima((nc - 1) * passo + 2 * ponta))
    twp = _chapa_acima(max(ESPESSURA_MINIMA_TALA, tw / 2))

    atual = replace(
        e, bp=bp, tp=tp, nl=nl, nr=nr, g=g, s=passo, ep=ponta, ec=ponta, x1_u=x1, bw=bw,
        twp=twp, nc=nc, m=m, sh=passo, sv=passo, ewv=ponta, ewc=ponta,
    )  # fmt: skip
    if not cabe or validar(atual):
        notas += validar(atual)
        return Sugestao(atual, None, tuple(notas), False)
    r = calcular(atual)
    for _ in range(40):
        if r.situacao == "ATENDE":
            break
        numeros = {v.nome.split(".")[0] for v in r.resistencia if v.status == "NÃO OK"}
        do_pilar = numeros & DO_PILAR
        if do_pilar:
            notas.append(
                "Não atende no próprio pilar ("
                + ", ".join(sorted(do_pilar, key=lambda x: int(x)))
                + "): a mesa do pilar não resiste a estes esforços, e trocar as talas não resolve. "
                "Confira o perfil do pilar."
            )
            break
        mudou = False
        if numeros & PARAFUSOS_DA_MESA and atual.nr < FILEIRAS_MAXIMAS:
            atual, mudou = replace(atual, nr=atual.nr + 1), True
        elif numeros & (PARAFUSOS_DA_MESA | TALA_DA_MESA) and atual.tp < mc.CHAPAS.valores[-1]:
            atual, mudou = replace(atual, tp=_chapa_acima(atual.tp + 0.01)), True
        if numeros & PARAFUSOS_DA_ALMA and atual.m < FILEIRAS_MAXIMAS_ALMA:
            atual, mudou = replace(atual, m=atual.m + 1), True
        elif numeros & (PARAFUSOS_DA_ALMA | TALAS_DA_ALMA) and atual.twp < mc.CHAPAS.valores[-1]:
            atual, mudou = replace(atual, twp=_chapa_acima(atual.twp + 0.01)), True
        if not mudou:
            notas.append(
                "Mesmo com o máximo de fileiras e chapas mais grossas a emenda não atende: troque "
                "o parafuso (maior ou A490) ou use talas internas."
            )
            break
        r = calcular(atual)
    if r.situacao == "ATENDE":
        notas.insert(
            0,
            f"Talas sugeridas: mesa {_n(atual.bp)} × {_n(atual.tp)} com {atual.nl} × {atual.nr} "
            f"parafusos por lado; alma 2 × {_n(atual.bw)} × {_n(atual.twp)} com {atual.nc} × "
            f"{atual.m}. Utilização máxima {100 * r.utilizacao_maxima:.0f} %.",
        )
    return Sugestao(atual, r, tuple(notas), True)


# ---------------------------------------------------------------------------------------------
# REGISTRO NO PROJETO E MEMORIAL
# ---------------------------------------------------------------------------------------------
REFERENCIAS = (
    "ABNT NBR 8800:2025 — Projeto de estruturas de aço e de estruturas mistas de aço e concreto "
    "de edifícios (5.2.4, 5.3, 6.1.6, 6.3, 6.5, 6.6.2, 12.3.5).",
    "Anglo American — Critério de Projeto AA-BR-DPST-DR-0001 (itens 8.8, 9.1 e 12).",
    "AISC — Steel Construction Manual, Parte 14 (Column Splices).",
    "Kulak, Fisher e Struik — Guide to Design Criteria for Bolted and Riveted Joints, cap. 13 e 16.",
    "SCI P207 — Joints in Steel Construction: Moment Connections (SCI/BCSA, 1995), seção 5; só o "
    "modelo mecânico.",
)


def texto_de_destaque(r: ResultadoEmenda) -> str:
    g = r.governante
    n = len(r.itens_a_verificar)
    a_verificar = "nenhuma disposição a verificar" if n == 0 else f"{n} disposição(ões) a verificar"
    return (
        f"Emenda {r.entrada.perfil_superior} / {r.entrada.perfil_inferior}: resistência "
        f"{'atende' if r.situacao == 'ATENDE' else 'não atende'}, utilização máxima de "
        f"{100 * r.utilizacao_maxima:.0f} %" + (f" ({g.nome})" if g else "") + f"; {a_verificar}."
    )


def _entradas_do_registro(r: ResultadoEmenda) -> dict[str, object]:
    e, p = r.entrada, r.propriedades
    eh_u = r.superior.familia == FAMILIA_U
    entradas: dict[str, object] = {
        "perfil_superior": e.perfil_superior,
        "perfil_inferior": e.perfil_inferior,
        "aco_dos_perfis": e.aco_perfis,
        "aco_das_talas": e.aco_talas,
        "parafuso": f"{e.diametro} {e.grau}",
        "rosca_no_plano_de_corte": e.rosca_no_plano,
        "verificar_deslizamento": e.verificar_deslizamento,
        "superficie": e.superficie if e.verificar_deslizamento else None,
        "contato": e.contato,
        "fresta_mm": e.gap,
        "comprimentos_de_flambagem": f"K_x·L_x = {_n(e.Kx * e.Lx, 0)} mm; K_y·L_y = "
        f"{_n(e.Ky * e.Ly, 0)} mm",
        "altura_da_emenda_mm": e.a,
        "nc_rd": f"{_n(r.Nc_Rd)} kN ({'informado' if e.Nc_Rd_informado else 'estimado'})",
        "criterio_minimo": e.criterio_minimo,
        "distribuicao": e.distribuicao,
        "tala_da_mesa": f"{_n(e.bp)} × {_n(e.tp)} × {_n(p['Lp'])} mm",
        "parafusos_da_mesa": f"{e.nl} linha(s) × {e.nr} fileira(s) por lado; g = {_n(e.g)}, "
        f"s = {_n(e.s)}, e_p = {_n(e.ep)}, e_c = {_n(e.ec)} mm",
        "talas_internas": f"{p['n_int']} × {_n(e.bi)} × {_n(e.ti)} × {_n(p['Lp'])} mm"
        if e.talas_internas
        else None,
        "furacao_do_u": f"x1 = {_n(e.x1_u)} mm; R = {_n(e.raio_u)} mm" if eh_u else None,
        "talas_da_alma": f"2 × {_n(e.bw)} × {_n(e.twp)} × {_n(p['Lw'])} mm",
        "parafusos_da_alma": f"{e.nc} coluna(s) × {e.m} fileira(s) por lado; s_h = {_n(e.sh)}, "
        f"s_v = {_n(e.sv)}, e_wv = {_n(e.ewv)}, e_wc = {_n(e.ewc)} mm",
        "total_de_parafusos": r.total_de_parafusos,
    }
    return {k: v for k, v in entradas.items() if v is not None}


def _tabela_de_esforcos_do_memorial(r: ResultadoEmenda) -> dict[str, object]:
    cabecalhos = ["Caso", "N (kN)", "M_x (kN·m)", "V (kN)", "M_y (kN·m)", "F_f,t (kN)",
                  "F_f,c (kN)", "N_w (kN)", "R_w (kN)"]  # fmt: skip
    linhas = [
        [c.nome, *(_n(v, 2) for v in (c.N, c.Mx, c.V, c.My, c.Fft, c.Ffc, c.Nw, c.Rw))]
        for c in r.casos
    ]
    return {
        "subtitulo": "Esforços por caso",
        "legenda": "Esforços de cálculo na cota da emenda e forças nas mesas e na alma (F_f,t: "
        "mesa mais tracionada; F_f,c: mesa mais comprimida; R_w: parafuso mais solicitado da alma).",
        "cabecalhos": cabecalhos,
        "linhas": linhas,
        "larguras": [1560] + [975] * 8,
    }


def registro(
    r: ResultadoEmenda, *, figuras: list[dict[str, object]] | None = None
) -> dict[str, object]:
    """O registro técnico da emenda para o projeto ativo e o memorial."""
    e = r.entrada
    # só as linhas que se aplicam a esta emenda (as N/A não entram no memorial)
    todas = [v for v in r.mesa + r.alma + r.disposicoes if v.status != "N/A"]
    geral = status_geral(todas)
    destaque = texto_de_destaque(r)
    resultados: dict[str, object] = {
        "status_geral": geral,
        "verificações": linhas_para_registro(todas),
        "utilizacao_maxima": numero_json(r.utilizacao_maxima, 4),
        "destaque_memorial": destaque,
        # memorial do projeto: tabela pronta; memorial separado (trecho): "Esforços de cálculo"
        "tabelas_memorial": [_tabela_de_esforcos_do_memorial(r)],
        "combinacoes": [
            {
                "Caso": c.nome,
                "N (kN)": c.N,
                "M_x (kN·m)": c.Mx,
                "V (kN)": c.V,
                "M_y (kN·m)": c.My,
                "F_f,t (kN)": c.Fft,
                "F_f,c (kN)": c.Ffc,
                "R_w (kN)": c.Rw,
            }
            for c in r.casos
        ],  # fmt: skip
    }
    if figuras:
        resultados["figuras_2d"] = list(figuras)
    titulo = f"Emenda de pilar — {e.perfil_superior}"
    if e.perfil_inferior != e.perfil_superior:
        titulo += f" / {e.perfil_inferior}"
    if e.talas_internas:
        titulo += " (talas internas)"
    premissas = [
        "Distribuição dos esforços pelo modelo do SCI P207, seção 5: o momento vira um binário "
        "nas mesas, de braço d − t_f; a força normal se divide "
        + ("metade em cada mesa." if e.distribuicao == DISTRIBUICAO_METADE else
           "pela área (b_f·t_f/A em cada mesa e o restante na alma)."),
        "Com contato das extremidades usinadas, a compressão passa pelo contato e as talas levam "
        "tração e cortante." if e.contato else
        "Sem contato: toda a compressão passa pelas talas e pelos parafusos.",
        "Parafusos da alma pelo método elástico, com o momento V·e, e = e_wc + (m − 1)·s_v/2 + "
        "gap/2.",
        "Esforço mínimo da NBR 8800 6.1.6.2 como mínimo recomendado: situação "
        f"{r.minimo.adotado or '—'} ({e.criterio_minimo}).",
        "Resistências pela ABNT NBR 8800:2025; do SCI P207 usa-se só o modelo mecânico, sem os "
        "fatores da BS 5950.",
    ]  # fmt: skip
    if e.talas_internas:
        premissas.append(
            "Talas internas: a força da mesa se divide entre a tala externa e as internas pela "
            "área de cada uma; os parafusos da mesa trabalham em corte duplo."
        )
    if r.superior.familia == FAMILIA_U:
        premissas.append(
            "Perfil U: a tala externa encosta no dorso da alma; a mesa do pilar rasga em bloco "
            "em L até a borda livre; a diferença de espessura das almas vai inteira para o lado de "
            "dentro."
        )
    alertas = [f"{v.nome}: {v.formula}" for v in todas if v.status in ("NÃO OK", "ALERTA")] + [
        a for a in r.avisos if "página" not in a
    ]
    if r.superior.familia == FAMILIA_U and e.Nc_Rd_informado is None:
        alertas.append("Perfil U: o N_c,Rd estimado não considera a flambagem por flexo-torção.")
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=titulo,
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=destaque,
        entradas=_entradas_do_registro(r),
        resultados=resultados,
        metodo=(
            "Emenda de pilar com uma tala externa em cada mesa"
            + (" e talas internas (corte duplo)" if e.talas_internas else " (corte simples)")
            + " e duas talas na alma (corte duplo). Forças nas mesas e na alma pelo modelo "
            "mecânico do SCI P207, seção 5, e resistências pela ABNT NBR 8800:2025."
        ),
        premissas=premissas,
        alertas=alertas,
        referencias=list(REFERENCIAS),
        conclusao=destaque,
    )


def memorial_da_emenda(
    r: ResultadoEmenda,
    *,
    projeto: Mapping[str, Any] | None = None,
    figuras: list[dict[str, object]] | None = None,
    formato: str = "word",
    registro_preparado: Mapping[str, Any] | None = None,
) -> bytes:
    """O memorial só desta emenda: em Word, o trecho para colar no documento oficial
    (:mod:`core.memorial_trecho`); em PDF, o documento do padrão do memorial do projeto."""
    import importlib

    from core.technical_records import normalizar_registro_tecnico

    reg = normalizar_registro_tecnico(registro_preparado or registro(r, figuras=figuras))
    if formato != "pdf":
        from core.memorial_trecho import trecho_de_registro

        return trecho_de_registro(reg, projeto=projeto)
    # o gerador do memorial está fora da lista do mypy: importado pelo nome (como em base_de_pilar)
    relatorio = importlib.import_module("core.project_report")
    base: dict[str, Any] = dict(projeto) if projeto else {"nome": MODULO_TITULO}
    base["registros_tecnicos"] = [reg]
    conteudo: bytes = relatorio.gerar_relatorio_industrial_pdf(base, secoes_incluidas=["registros"])
    return conteudo


def com(e: EntradaEmenda, **mudancas: Any) -> EntradaEmenda:
    """Atalho de ``dataclasses.replace`` para os testes e a página."""
    return replace(e, **mudancas)
