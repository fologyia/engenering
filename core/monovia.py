"""Viga de monovia (talha que corre na mesa inferior de um perfil I).

O que a verificação cobre:

* cargas da talha: rodas iguais (2 por eixo), impacto vertical (critério Anglo 5.4: +20 % da carga
  içada e +10 % das partes móveis, editáveis) e força lateral na mesa inferior (fração da carga
  içada + talha, 10 % por padrão, como a força transversal das pontes rolantes);
* esforços pela posição mais desfavorável das rodas: viga biapoiada (dois eixos simétricos à
  seção de momento máximo) ou balanço engastado (rodas na ponta);
* flexão vertical pela ABNT NBR 8800:2025 (Anexo G, com FLT; a carga abaixo do centro de
  cisalhamento é estabilizante — ignorada, a favor da segurança), cortante (5.4.3);
* flexão lateral resistida só pela mesa inferior (a força entra na mesa: a torção vira flexão da
  mesa) e a interação 5.5.1;
* flexão local da mesa inferior sob as rodas pela EN 1993-6:2007, 6.7 (F_f,Rd e o comprimento
  efetivo da Tabela 6.2) e as tensões locais da Tabela 6.? (coeficientes c_x e c_y), combinadas
  com a tensão global na mesa (von Mises), como no CMAA 74 e na BS 2853;
* flechas vertical (L/500, sem impacto — Anglo Tabela 3) e horizontal (L/400 — Anglo Tabela 4);
* a mesa onde a viga pendura ou apoia (5.7, pelo módulo de forças localizadas).

Unidades: mm, MPa, N internamente; kN e kN·m nas entradas e saídas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from core import forcas_localizadas as fl
from core import nbr8800 as nb
from core import perfil_i as pi
from core import verificacao_modulo as vm
from core.verificacao import Verificacao

MODULO_ID = "monovia"
MODULO_TITULO = "Viga de monovia"

BIAPOIADA = "Biapoiada (vão entre apoios)"
BALANCO = "Balanço engastado (rodas na ponta)"
SISTEMAS = (BIAPOIADA, BALANCO)

PENDURADA = "Pendurada pela mesa superior (tirante ou chapa)"
APOIADA = "Apoiada sobre a mesa inferior (viga ou console)"
APOIOS = (PENDURADA, APOIADA)

G = 9.80665e-3  # kN por kg

REFERENCIAS = (
    "ABNT NBR 8800:2025 — 5.4 (flexão e cortante), 5.5.1 (interação), 5.7 (forças localizadas), "
    "Anexo G (momento resistente) e Anexo B (deslocamentos).",
    "EN 1993-6:2007 — Eurocode 3, Part 6: Crane supporting structures, 6.7 (flexão local da mesa "
    "inferior sob as rodas) e Tabela 6.2 (comprimento efetivo).",
    "Critério Anglo American — 5.4 (impacto de monovias: +20 % da carga içada, +10 % das partes "
    "móveis) e Tabelas 3 e 4 (flechas L/500 vertical e L/400 horizontal).",
    "CMAA 74 / BS 2853 — tensões locais na mesa inferior combinadas com as globais.",
)


@dataclass(frozen=True)
class EntradaMonovia:
    familia: str = pi.FAMILIA_W
    perfil: str = "W 310 x 38,7"
    d: float = 400.0
    bf: float = 180.0
    tf: float = 12.5
    tw: float = 8.0
    filete: float = 5.0
    aco: str = "ASTM A572 Gr 50"
    gama_a1: float = pi.GAMA_A1
    sistema: str = BIAPOIADA
    L: float = 5000.0  # vão ou balanço (mm)
    Lb: float = 5000.0  # comprimento destravado da mesa comprimida (mm)
    capacidade: float = 20.0  # carga içada nominal (kN)
    peso_talha: float = 3.0  # talha + trole (kN)
    rodas_por_eixo: int = 2
    eixos: int = 2
    entre_eixos: float = 300.0  # distância entre os eixos da talha (mm)
    n_roda: float = 20.0  # distância do ponto de contato da roda à borda da mesa (mm)
    impacto_carga: float = 0.20
    impacto_moveis: float = 0.10
    lateral: float = 0.10  # força lateral total / (carga içada + talha)
    gama_g: float = 1.25
    gama_q: float = 1.50
    ponta_sem_enrijecedor: bool = (
        False  # a roda chega à ponta livre sem enrijecedor (EN Tab. 6.2 a)
    )
    flecha_vertical: float = 500.0  # L/…
    flecha_horizontal: float = 400.0
    apoio: str = PENDURADA
    ln_apoio: float = 150.0  # comprimento de apoio (mm)
    largura_apoio: float = 100.0


@dataclass
class ResultadoMonovia:
    entrada: EntradaMonovia
    perfil: pi.PerfilI
    fy: float
    esforcos: dict[str, float]
    grupos: list[vm.Grupo]
    avisos: list[str]

    @property
    def linhas(self) -> list[Verificacao]:
        return vm.decisivas(self.grupos)

    @property
    def situacao(self) -> str:
        return vm.situacao(self.linhas)

    @property
    def utilizacao_maxima(self) -> float:
        return vm.utilizacao_maxima(self.linhas)


def obter_perfil(e: EntradaMonovia) -> pi.PerfilI:
    if e.familia == pi.FAMILIA_SOLDADO:
        return pi.soldado(e.d, e.bf, e.tf, e.tw, e.filete)
    return pi.perfil(e.perfil)


def validar(e: EntradaMonovia) -> list[str]:
    erros: list[str] = []
    try:
        p = obter_perfil(e)
    except (ValueError, KeyError) as exc:
        return [f"Perfil: {exc}"]
    if e.aco not in pi.ACOS:
        erros.append("Escolha o aço.")
    for nome, valor in (("O vão", e.L), ("O comprimento destravado", e.Lb)):
        if valor <= 0:
            erros.append(f"{nome} deve ser positivo.")
    if e.capacidade <= 0:
        erros.append("A carga içada deve ser positiva.")
    if e.peso_talha < 0 or e.entre_eixos < 0:
        erros.append("O peso da talha e a distância entre eixos não podem ser negativos.")
    if e.eixos not in (1, 2) or e.rodas_por_eixo not in (1, 2):
        erros.append("A talha tem 1 ou 2 eixos e 1 ou 2 rodas por eixo.")
    if e.eixos == 2 and e.entre_eixos >= e.L:
        erros.append("A distância entre eixos deve ser menor que o vão.")
    if not (0 <= e.n_roda < (p.bf - p.tw) / 2):
        erros.append(
            "A posição da roda (n) deve ficar dentro da aba da mesa: 0 ≤ n < (b_f − t_w)/2."
        )
    if e.flecha_vertical <= 0 or e.flecha_horizontal <= 0:
        erros.append("Os limites de flecha devem ser positivos.")
    return erros


# ---------------------------------------------------------------- esforços
def _esforcos_biapoiada(P: float, a: float, L: float, eixos: int) -> tuple[float, float]:
    """Momento máximo e reação máxima de 1 ou 2 cargas P (N, mm) num vão L."""
    if eixos == 1 or a <= 0:
        return P * eixos * L / 4, P * eixos
    m_dois = 2 * P * (L / 2 - a / 4) ** 2 / L
    m_um = P * L / 4
    return max(m_dois, m_um), P + P * (L - a) / L


def _flecha_biapoiada(P: float, a: float, L: float, EI: float, eixos: int) -> float:
    """Flecha no meio do vão com as cargas simétricas ao meio (posição de flecha ≈ máxima)."""
    if eixos == 1 or a <= 0:
        return P * eixos * L**3 / (48 * EI)
    b = (L - a) / 2
    return P * b * (3 * L**2 - 4 * b**2) / (24 * EI)


def _esforcos_balanco(P: float, a: float, L: float, eixos: int) -> tuple[float, float]:
    if eixos == 1 or a <= 0:
        return P * eixos * L, P * eixos
    return P * L + P * max(L - a, 0.0), 2 * P


def _flecha_balanco(P: float, a: float, L: float, EI: float, eixos: int) -> float:
    def ponta(x: float) -> float:  # carga a x do engaste, flecha na ponta
        return P * x**2 * (3 * L - x) / (6 * EI)

    if eixos == 1 or a <= 0:
        return eixos * ponta(L)
    return ponta(L) + ponta(max(L - a, 0.0))


def coeficientes_locais(mu: float) -> dict[str, float]:
    """EN 1993-6:2007, 6.7, mesa de faces paralelas: c_x e c_y nos pontos 0 (junto à alma),
    1 (sob a roda) e 2 (borda). Tensão local = c·F/t_f² (positivo = tração na face de baixo)."""
    return {
        "cx0": 0.050 - 0.580 * mu + 0.148 * math.exp(3.015 * mu),
        "cx1": 2.230 - 1.490 * mu + 1.390 * math.exp(-18.33 * mu),
        "cx2": 0.730 - 1.580 * mu + 2.910 * math.exp(-6.00 * mu),
        "cy0": -2.110 + 1.977 * mu + 0.0076 * math.exp(6.53 * mu),
        "cy1": 10.108 - 7.408 * mu - 10.108 * math.exp(-1.364 * mu),
        "cy2": 0.0,
    }


def comprimento_efetivo(
    m: float, n: float, x_w: float, ponta_sem_enrijecedor: bool, eixos: int
) -> tuple[float, str]:
    """EN 1993-6 Tabela 6.2: l_eff de uma roda."""
    s = m + n
    if ponta_sem_enrijecedor:
        return 2 * s, "roda junto à ponta sem enrijecedor: 2·(m + n)"
    limite = 4 * math.sqrt(2) * s
    if eixos == 1 or x_w <= 0 or x_w >= limite:
        return limite, "roda longe da ponta: 4·√2·(m + n)"
    return 2 * math.sqrt(2) * s + 0.5 * x_w, "rodas vizinhas a x_w: 2·√2·(m + n) + 0,5·x_w"


def _n(valor: float, casas: int = 1) -> str:
    return pi.numero(valor, casas)


def calcular(e: EntradaMonovia) -> ResultadoMonovia:
    p = obter_perfil(e)
    fy = pi.ACOS[e.aco][0]
    E, g1 = pi.E_ACO, e.gama_a1
    avisos = list(pi.avisos_do_perfil(p))
    q = p.massa * G  # kN/m = N/mm
    # cargas por eixo (N): serviço, com impacto, de cálculo
    carga = e.capacidade * 1000
    talha = e.peso_talha * 1000
    P_serv = (carga + talha) / e.eixos
    P_imp = (carga * (1 + e.impacto_carga) + talha * (1 + e.impacto_moveis)) / e.eixos
    P_d = (carga * (1 + e.impacto_carga) + talha * (1 + e.impacto_moveis)) * e.gama_q / e.eixos
    H_d = e.lateral * (carga + talha) * e.gama_q / e.eixos  # lateral por eixo, de cálculo
    H_serv = e.lateral * (carga + talha) / e.eixos
    L, a = e.L, (e.entre_eixos if e.eixos == 2 else 0.0)
    if e.sistema == BIAPOIADA:
        M_rodas, R_rodas = _esforcos_biapoiada(P_d, a, L, e.eixos)
        M_q, R_q = q * L**2 / 8, q * L / 2
        flecha_v = _flecha_biapoiada(P_serv, a, L, E * p.Ix, e.eixos)
        L_ref = L
    else:
        M_rodas, R_rodas = _esforcos_balanco(P_d, a, L, e.eixos)
        M_q, R_q = q * L**2 / 2, q * L
        flecha_v = _flecha_balanco(P_serv, a, L, E * p.Ix, e.eixos)
        L_ref = 2 * L  # NBR 8800 Tabela B.1, nota a: o dobro do balanço
    Md = M_rodas + e.gama_g * M_q
    Vd = R_rodas + e.gama_g * R_q
    # lateral: mesma posição das rodas, só a mesa inferior trabalha
    razao_h = H_d / P_d if P_d > 0 else 0.0
    M_lat = M_rodas * razao_h
    I_mesa = p.tf * p.bf**3 / 12
    Z_mesa = p.tf * p.bf**2 / 4
    W_mesa = p.tf * p.bf**2 / 6
    if e.sistema == BIAPOIADA:
        flecha_h = _flecha_biapoiada(H_serv, a, L, E * I_mesa, e.eixos)
    else:
        flecha_h = _flecha_balanco(H_serv, a, L, E * I_mesa, e.eixos)
    esforcos = {
        "P_eixo_servico_kN": P_serv / 1000,
        "P_eixo_calculo_kN": P_d / 1000,
        "F_roda_calculo_kN": P_d / e.rodas_por_eixo / 1000,
        "H_eixo_calculo_kN": H_d / 1000,
        "M_Sd_kNm": Md / 1e6,
        "M_lat_kNm": M_lat / 1e6,
        "V_Sd_kN": Vd / 1000,
        "R_servico_kN": _reacao_servico(e, P_serv, q) / 1000,
        "flecha_v_mm": flecha_v,
        "flecha_h_mm": flecha_h,
    }
    ref = "ABNT NBR 8800:2025, "
    grupos: list[vm.Grupo] = []
    # 1. flexão e cortante
    perfil_aco = p.perfil_aco()
    flex = nb.verificar_flexao(
        perfil_aco,
        fy,
        E,
        pi.G_ACO,
        Md,
        eixo="x",
        comprimento_destravado_mm=e.Lb,
        cb=1.0,
        soldado=p.soldado,
    )
    cis = nb.verificar_cisalhamento(perfil_aco, fy, E, Vd)
    MxRd = flex.resistencia_Nmm
    MyRd = min(Z_mesa, 1.5 * W_mesa) * fy / g1
    linhas_globais = [
        vm.linha_info(
            "Cargas por eixo da talha",
            P_d / 1000,
            "kN",
            "Critério Anglo 5.4; ABNT NBR 8800:2025, 4.8",
            f"γ_q·[Q·(1 + {_n(100 * e.impacto_carga, 0)} %) + G_t·(1 + "
            f"{_n(100 * e.impacto_moveis, 0)} %)]/{e.eixos} eixo(s) = {_n(P_d / 1000, 2)} kN; "
            f"por roda {_n(P_d / e.rodas_por_eixo / 1000, 2)} kN; serviço {_n(P_serv / 1000, 2)} kN",
        ),
        Verificacao(
            "Flexão vertical",
            Md / 1e6,
            MxRd / 1e6,
            "kN·m",
            ref + "5.4.2 e Anexo G",
            f"M_Sd = rodas na posição crítica + γ_g·q·L²/{'8' if e.sistema == BIAPOIADA else '2'} "
            f"(q = {_n(q, 3)} kN/m); M_Rd governado por {flex.modo_governante}, "
            f"L_b = {_n(e.Lb, 0)} mm, C_b = 1",
        ),
        Verificacao(
            "Cortante",
            Vd / 1000,
            cis.resistencia_N / 1000,
            "kN",
            ref + "5.4.3",
            f"V_Rd = {cis.regime}, k_v = {_n(cis.kv, 1)}",
        ),
        Verificacao(
            "Flexão lateral da mesa inferior",
            M_lat / 1e6,
            MyRd / 1e6,
            "kN·m",
            ref + "5.4.2 (mesa isolada)",
            f"força lateral de {_n(100 * e.lateral, 0)} % de (Q + G_t) na mesa inferior; "
            f"M_y,Rd = Z_mesa·f_y/γ_a1, Z_mesa = t_f·b_f²/4 = {_n(Z_mesa / 1000, 1)} cm³",
        ),
    ]
    inter = Md / MxRd + M_lat / MyRd if MxRd > 0 and MyRd > 0 else math.inf
    linhas_globais.append(
        Verificacao(
            "Interação: flexão vertical + lateral",
            inter,
            1.0,
            "",
            ref + "5.5.1.2 (N = 0)",
            f"M_x,Sd/M_x,Rd + M_lat/M_y,Rd = {_n(Md / MxRd, 3)} + {_n(M_lat / MyRd, 3)}",
        )
    )
    grupos.append(vm.Grupo("Flexão e cortante", linhas_globais))
    # 2. mesa inferior sob as rodas (EN 1993-6, 6.7)
    F_roda = P_d / e.rodas_por_eixo
    F_roda_serv = P_imp / e.rodas_por_eixo
    if p.tipo == pi.LAMINADO:
        m = 0.5 * (p.bf - p.tw) - 0.8 * p.raio - e.n_roda
        texto_m = "m = 0,5·(b_f − t_w) − 0,8·r − n"
    else:
        m = 0.5 * (p.bf - p.tw) - 0.8 * math.sqrt(2) * p.raio - e.n_roda
        texto_m = "m = 0,5·(b_f − t_w) − 0,8·√2·a − n"
    linhas_mesa: list[Verificacao] = []
    if m <= 0:
        linhas_mesa.append(
            Verificacao(
                "Posição da roda na mesa",
                None,
                None,
                "",
                "EN 1993-6:2007, 6.7",
                f"{texto_m} = {_n(m, 1)} mm ≤ 0: a roda está sobre o raio/filete; reveja n",
                status="NÃO OK",
                tipo="limite",
            )
        )
    else:
        l_eff, caso = comprimento_efetivo(m, e.n_roda, a, e.ponta_sem_enrijecedor, e.eixos)
        dist_mesa = p.d / 2 - p.tf / 2
        sigma_f = Md / p.Ix * dist_mesa  # no meio da mesa (sob a alma) a flexão lateral é nula
        reducao = max(1 - (sigma_f / (fy / g1)) ** 2, 0.0)
        Ff = l_eff * p.tf**2 * fy / (4 * m * g1) * reducao
        linhas_mesa.append(
            Verificacao(
                "Flexão local da mesa inferior",
                F_roda / 1000,
                Ff / 1000,
                "kN",
                "EN 1993-6:2007, 6.7(3) e Tabela 6.2",
                f"F_f,Rd = l_eff·t_f²·f_y/(4·m·γ_a1)·[1 − (σ_f/(f_y/γ_a1))²], {texto_m} = "
                f"{_n(m, 1)} mm, l_eff = {_n(l_eff, 0)} mm ({caso}), σ_f = {_n(sigma_f, 1)} MPa",
                equacoes=(
                    "F_f,Rd = l_eff t_f^2 f_y / (4 m γ_a1) [1 - (σ_f / (f_y/γ_a1))^2]",
                    f"F_f,Rd = {_n(l_eff, 0)} · {_n(p.tf, 2)}^2 · {_n(fy, 0)} / (4 · {_n(m, 1)} · "
                    f"{_n(g1, 2)}) · {_n(reducao, 3)} = {_n(Ff / 1000, 2)} kN",
                ),
            )
        )
        # tensões locais em serviço (com impacto) + globais em serviço, von Mises no ponto 0
        mu = 2 * e.n_roda / (p.bf - p.tw)
        c = coeficientes_locais(mu)
        if e.sistema == BIAPOIADA:
            Ms = _esforcos_biapoiada(P_imp, a, L, e.eixos)[0] + M_q
        else:
            Ms = _esforcos_balanco(P_imp, a, L, e.eixos)[0] + M_q
        sig_g = Ms / p.Ix * (p.d / 2)
        maior = 0.0
        ponto = "0"
        for k in ("0", "1", "2"):
            sx = c["cx" + k] * F_roda_serv / p.tf**2 + sig_g
            sy = c["cy" + k] * F_roda_serv / p.tf**2
            vm_ = math.sqrt(sx**2 + sy**2 - sx * sy)
            if vm_ > maior:
                maior, ponto = vm_, k
        linhas_mesa.append(
            Verificacao(
                "Tensão combinada na mesa inferior (serviço)",
                maior,
                fy,
                "MPa",
                "EN 1993-6:2007, 6.7(1); CMAA 74",
                f"von Mises de σ_x = σ_global + c_x·F/t_f² e σ_y = c_y·F/t_f² no ponto {ponto} "
                f"(0 = junto à alma, 1 = sob a roda, 2 = borda), μ = 2n/(b_f − t_w) = {_n(mu, 3)}; "
                "cargas de serviço com impacto",
                obrigatoria=False,
                status="OK" if maior <= fy else "ALERTA",
                aproveitamento=maior / fy,
            )
        )
    grupos.append(vm.Grupo("Mesa inferior sob as rodas", linhas_mesa))
    # 3. flechas
    lim_v = L_ref / e.flecha_vertical
    lim_h = L_ref / e.flecha_horizontal
    grupos.append(
        vm.Grupo(
            "Deslocamentos (serviço, sem impacto)",
            [
                vm.linha_limite(
                    "Flecha vertical",
                    flecha_v,
                    lim_v,
                    "mm",
                    "Critério Anglo, Tabela 3 (monovias); ABNT NBR 8800:2025, Anexo B",
                    f"talha + carga içada sem impacto; limite L/{_n(e.flecha_vertical, 0)}"
                    + (" com L = 2 × balanço" if e.sistema == BALANCO else ""),
                ),
                vm.linha_limite(
                    "Flecha horizontal",
                    flecha_h,
                    lim_h,
                    "mm",
                    "Critério Anglo, Tabela 4",
                    f"força lateral na mesa inferior (I da mesa = {_n(I_mesa / 1e4, 0)} cm⁴); "
                    f"limite L/{_n(e.flecha_horizontal, 0)}",
                ),
            ],
        )
    )
    # 4. mesa no apoio (5.7)
    tipo = fl.TRACAO if e.apoio == PENDURADA else fl.COMPRESSAO
    forca = fl.ForcaLocalizada(
        "Apoio", Vd / 1000, tipo, e.ln_apoio, e.largura_apoio, 0.0, False, 0.0
    )
    ent_fl = fl.EntradaForcas(
        familia=e.familia, perfil=e.perfil, d=e.d, bf=e.bf, tf=e.tf, tw=e.tw, filete=e.filete,
        aco=e.aco, gama_a1=g1, forcas=(forca,),
    )  # fmt: skip
    r_fl = fl.calcular(ent_fl)
    grupos.append(vm.Grupo("Mesa e alma no apoio", r_fl.forcas[0].linhas))
    avisos.append(
        "Monovia sob muitos ciclos de carga: verifique a fadiga das soldas e dos furos na página "
        "Fadiga da estrutura (NBR 8800:2025, Anexo H)."
    )
    return ResultadoMonovia(e, p, fy, esforcos, grupos, avisos)


def _reacao_servico(e: EntradaMonovia, P_serv: float, q: float) -> float:
    a = e.entre_eixos if e.eixos == 2 else 0.0
    if e.sistema == BIAPOIADA:
        return _esforcos_biapoiada(P_serv, a, e.L, e.eixos)[1] + q * e.L / 2
    return _esforcos_balanco(P_serv, a, e.L, e.eixos)[1] + q * e.L


def registro(r: ResultadoMonovia) -> dict[str, Any]:
    e = r.entrada
    entradas = {
        "perfil": r.perfil.descricao,
        "aco": f"{e.aco} (f_y = {_n(r.fy, 0)} MPa)",
        "sistema": e.sistema,
        "vao_mm": e.L,
        "comprimento_destravado_mm": e.Lb,
        "talha": (
            f"carga içada {_n(e.capacidade, 1)} kN, talha {_n(e.peso_talha, 1)} kN, {e.eixos} "
            f"eixo(s) × {e.rodas_por_eixo} roda(s), entre eixos {_n(e.entre_eixos, 0)} mm, "
            f"roda a {_n(e.n_roda, 0)} mm da borda da mesa"
        ),
        "impactos": (
            f"+{_n(100 * e.impacto_carga, 0)} % na carga içada, +{_n(100 * e.impacto_moveis, 0)} % "
            f"nas partes móveis; lateral {_n(100 * e.lateral, 0)} %"
        ),
        "coeficientes": f"γ_g = {_n(e.gama_g, 2)}, γ_q = {_n(e.gama_q, 2)}, γ_a1 = {_n(e.gama_a1, 2)}",
        "apoio": e.apoio,
    }
    esf = r.esforcos
    tabela = {
        "titulo": "Esforços de cálculo",
        "colunas": ["Grandeza", "Valor"],
        "linhas": [
            ["Carga por roda (cálculo)", f"{_n(esf['F_roda_calculo_kN'], 2)} kN"],
            ["M_Sd vertical", f"{_n(esf['M_Sd_kNm'], 2)} kN·m"],
            ["M lateral (mesa inferior)", f"{_n(esf['M_lat_kNm'], 2)} kN·m"],
            ["V_Sd", f"{_n(esf['V_Sd_kN'], 2)} kN"],
            ["Reação de serviço por apoio", f"{_n(esf['R_servico_kN'], 2)} kN"],
        ],
    }
    return vm.registro_padrao(
        modulo_id=MODULO_ID,
        modulo_titulo=MODULO_TITULO,
        titulo=f"Viga de monovia — {r.perfil.nome}, {_n(e.capacidade, 1)} kN",
        grupos=r.grupos,
        entradas=entradas,
        metodo=(
            "Viga de monovia com talha na mesa inferior: flexão vertical e cortante pela ABNT "
            "NBR 8800:2025, flexão lateral só na mesa inferior, flexão local da mesa sob as rodas "
            "pela EN 1993-6:2007 (6.7), flechas pelo critério Anglo e a mesa no apoio pela 5.7."
        ),
        premissas=[
            "Rodas na posição mais desfavorável: no vão, os dois eixos simétricos à seção de "
            "momento máximo; no balanço, a roda dianteira na ponta.",
            "A carga abaixo do centro de cisalhamento é estabilizante; o programa não conta com "
            "esse benefício na FLT (C_b = 1).",
            "A força lateral entra na mesa inferior e é resistida só por ela (a torção vira "
            "flexão da mesa), a favor da segurança.",
            "Balanço tratado como engastado no apoio; a rotação do apoio aumenta a flecha real.",
            "A tensão combinada na mesa usa cargas de serviço com impacto e é um alerta (não "
            "reprova): a NBR não tem essa verificação; o limite f_y segue o CMAA 74.",
        ],
        referencias=REFERENCIAS,
        objeto=f"A viga de monovia {r.perfil.nome}",
        alertas=r.avisos,
        tabelas=[tabela],
    )


def com(e: EntradaMonovia, **mudancas: Any) -> EntradaMonovia:
    return replace(e, **mudancas)
