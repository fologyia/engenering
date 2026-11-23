"""Ligação rígida viga–pilar com chapa de extremidade estendida (4 parafusos na mesa tracionada).

A ligação "4E" (quatro parafusos junto à mesa tracionada: dois por fora e dois por dentro, sem
nervura na chapa) é a ligação de momento parafusada mais usada em pórticos de plataformas e
galpões. A verificação segue o modelo de linhas de plastificação com chapa grossa (sem efeito de
alavanca) do AISC Design Guide 4 (2ª ed.)/Design Guide 16 e da AISC 358-16, capítulo 6, com as
resistências e os coeficientes da ABNT NBR 8800:2025:

* parafusos tracionados: M_Rd = 2·F_t,Rd·(h₀ + h₁) (6.3.3.1);
* escoamento da chapa: M_Rd = f_y·t_p²·Y_p/γ_a1 e a condição de chapa grossa (≥ 1,11 × a
  resistência dos parafusos, para não haver alavanca);
* cisalhamento da extensão da chapa, corte e pressão de contato dos parafusos do lado comprimido;
* soldas da viga na chapa (mesa e alma);
* pilar: flexão da mesa (Y_c, com ou sem enrijecedores de continuidade), escoamento local,
  enrugamento e instabilidade da alma (5.7.3, 5.7.4, 5.7.6), cisalhamento do painel de alma
  (5.7.7) com chapa de reforço opcional, e os enrijecedores (5.7.9);
* disposições: espaçamentos, bordas e as folgas de aperto.

Unidades: mm, MPa, N internamente; kN e kN·m nas entradas e saídas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any

from core import bolted_connection as bc
from core import forcas_localizadas as fl
from core import perfil_i as pi
from core import soldas as sd
from core import verificacao_modulo as vm
from core.verificacao import Verificacao

MODULO_ID = "ligacao_rigida"
MODULO_TITULO = "Ligação rígida viga–pilar"
NORMA = "NBR8800_2024"  # chave interna da ABNT NBR 8800:2025 em core.bolted_connection

DIAMETROS = tuple(bc.PARAFUSOS)
GRAUS = ("A325", "A490")
PENETRACAO = "Penetração total"
FILETE = "Filete dos dois lados"
SOLDAS_DA_MESA = (PENETRACAO, FILETE)
ELETRODOS = dict(sd.ELETRODOS)
GAMA_W2 = 1.35
FATOR_CHAPA_GROSSA = 1.11  # AISC DG16 / AISC 358 6.10: t_p para os parafusos romperem sem alavanca

REFERENCIAS = (
    "ABNT NBR 8800:2025 — 6.3 (parafusos), 6.2 (soldas), 6.5 (elementos de ligação), 5.7 "
    "(forças localizadas, painel de alma e enrijecedores).",
    "AISC 358-16, capítulo 6 — Bolted unstiffened extended end-plate (4E): Tabelas 6.2 (Y_p) e "
    "6.5 (Y_c), procedimento de 6.10.",
    "AISC Design Guide 4, 2nd ed. (Extended End-Plate Moment Connections) e Design Guide 16 "
    "(Flush and Extended Multiple-Row Moment End-Plate Connections) — chapa grossa.",
)


@dataclass(frozen=True)
class PerfilEscolhido:
    familia: str = pi.FAMILIA_W
    nome: str = "W 410 x 46,1"
    d: float = 400.0
    bf: float = 180.0
    tf: float = 12.5
    tw: float = 8.0
    filete: float = 5.0

    def perfil(self) -> pi.PerfilI:
        if self.familia == pi.FAMILIA_SOLDADO:
            return pi.soldado(self.d, self.bf, self.tf, self.tw, self.filete)
        return pi.perfil(self.nome)


@dataclass(frozen=True)
class EntradaRigida:
    viga: PerfilEscolhido = field(default_factory=PerfilEscolhido)
    pilar: PerfilEscolhido = field(
        default_factory=lambda: PerfilEscolhido(pi.FAMILIA_W, "HP 310 x 79,0 (H)")
    )
    aco_viga: str = "ASTM A572 Gr 50"
    aco_pilar: str = "ASTM A572 Gr 50"
    aco_chapa: str = "ASTM A36"
    gama_a1: float = pi.GAMA_A1
    gama_a2: float = pi.GAMA_A2
    # esforços de cálculo
    M: float = 120.0  # kN·m (momento negativo no apoio: traciona a mesa de cima)
    V: float = 80.0  # kN
    N_pilar: float = 300.0  # kN de compressão no pilar
    V_pilar: float = 0.0  # kN — cortante no pilar, que alivia o painel
    outro_lado: bool = False
    M2: float = 0.0  # kN·m da viga do outro lado (positivo = também traciona a mesa de cima)
    topo_do_pilar: bool = False  # forças a menos de d do topo do pilar
    # parafusos e chapa
    diametro: str = '3/4"'
    grau: str = "A325"
    rosca_no_plano: bool = True
    bp: float = 160.0  # largura da chapa
    tp: float = 22.4  # espessura da chapa
    g: float = 100.0  # gabarito entre as duas colunas de parafusos
    pfo: float = 45.0  # da face externa da mesa tracionada à fileira de fora
    pfi: float = 45.0  # da face interna da mesa tracionada à fileira de dentro
    de: float = 40.0  # da fileira de fora à borda da chapa
    simetrica: bool = True  # a chapa estende-se também do lado comprimido (momento reversível)
    parafusos_comprimidos: int = 4  # parafusos que levam o cortante (lado comprimido)
    # soldas da viga
    solda_mesa: str = PENETRACAO
    perna_mesa: float = 10.0
    perna_alma: float = 8.0
    eletrodo: str = "E70"
    # reforços do pilar
    enrijecedores: bool = False
    ts: float = 12.5
    bs: float = 80.0
    corte: float = 20.0
    reforco_alma: float = 0.0  # espessura de cada chapa de reforço da alma (0 = sem)


def validar(e: EntradaRigida) -> list[str]:
    erros: list[str] = []
    for rotulo, escolha in (("Viga", e.viga), ("Pilar", e.pilar)):
        try:
            escolha.perfil()
        except (ValueError, KeyError) as exc:
            erros.append(f"{rotulo}: {exc}")
    if erros:
        return erros
    for aco in (e.aco_viga, e.aco_pilar, e.aco_chapa):
        if aco not in pi.ACOS:
            erros.append(f"Aço desconhecido: {aco}.")
    if e.M <= 0:
        erros.append("O momento de cálculo deve ser positivo (a ligação é verificada para |M|).")
    if e.V < 0:
        erros.append("O cortante é o valor absoluto.")
    for nome, valor in (("b_p", e.bp), ("t_p", e.tp), ("g", e.g), ("p_fo", e.pfo),
                        ("p_fi", e.pfi), ("borda", e.de)):  # fmt: skip
        if valor <= 0:
            erros.append(f"{nome} deve ser positivo.")
    viga = e.viga.perfil()
    if e.g >= e.bp:
        erros.append("O gabarito g deve ser menor que a largura da chapa.")
    if e.g <= viga.tw:
        erros.append("O gabarito g deve ser maior que a espessura da alma da viga.")
    if viga.d - 2 * viga.tf - e.pfi <= viga.d / 2:
        erros.append("A fileira de dentro ficou abaixo da meia altura da viga: reduza p_fi.")
    if e.parafusos_comprimidos < 2:
        erros.append("Pelo menos 2 parafusos levam o cortante.")
    if e.enrijecedores and (e.ts <= 0 or e.bs <= 0 or e.corte >= e.bs):
        erros.append("Enrijecedores: espessura e largura positivas, recorte menor que a largura.")
    if e.reforco_alma < 0:
        erros.append("A chapa de reforço da alma não pode ter espessura negativa.")
    return erros


# ---------------------------------------------------------------- linhas de plastificação
def y_p_4e(
    bp: float, g: float, pfo: float, pfi: float, h0: float, h1: float
) -> tuple[float, float]:
    """AISC 358-16 Tabela 6.2 (4E): Y_p da chapa e o s usado (p_fi limitado a s)."""
    s = 0.5 * math.sqrt(bp * g)
    pfi_ = min(pfi, s)
    Yp = bp / 2 * (h1 * (1 / pfi_ + 1 / s) + h0 * (1 / pfo) - 0.5) + 2 / g * (h1 * (pfi_ + s))
    return Yp, s


def y_c_4e(
    bcf: float, g: float, h0: float, h1: float, c: float, psi: float | None, pso: float | None
) -> tuple[float, float]:
    """AISC 358-16 Tabela 6.5 (4E): Y_c da mesa do pilar, sem ou com enrijecedores."""
    s = 0.5 * math.sqrt(bcf * g)
    if psi is None or pso is None:
        Yc = (
            bcf / 2 * (h1 / s + h0 / s)
            + 2 / g * (h1 * (s + 3 * c / 4) + h0 * (s + c / 4) + c**2 / 2)
            + g / 2
        )
    else:
        Yc = bcf / 2 * (h1 * (1 / s + 1 / psi) + h0 * (1 / s + 1 / pso)) + 2 / g * (
            h1 * (s + psi) + h0 * (s + pso)
        )
    return Yc, s


def _n(valor: float, casas: int = 1) -> str:
    return pi.numero(valor, casas)


@dataclass
class ResultadoRigida:
    entrada: EntradaRigida
    viga: pi.PerfilI
    pilar: pi.PerfilI
    grupos: list[vm.Grupo]
    geometria: dict[str, float]
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


def calcular(e: EntradaRigida) -> ResultadoRigida:
    viga, pilar = e.viga.perfil(), e.pilar.perfil()
    fy_b = pi.ACOS[e.aco_viga][0]
    fy_c, fu_c = pi.ACOS[e.aco_pilar]
    fy_p, fu_p = pi.ACOS[e.aco_chapa]
    g1, g2 = e.gama_a1, e.gama_a2
    avisos = pi.avisos_do_perfil(viga) + pi.avisos_do_perfil(pilar)
    par = bc.dados_parafuso(e.diametro)
    db, dh = par["d_b"], par["d_h"]
    M = e.M * 1e6
    d, tbf, bbf, tbw = viga.d, viga.tf, viga.bf, viga.tw
    h0 = d - tbf / 2 + e.pfo
    h1 = d - 1.5 * tbf - e.pfi
    Ff = M / (d - tbf)
    ref = "ABNT NBR 8800:2025, "
    ref358 = "AISC 358-16, "
    grupos: list[vm.Grupo] = []
    # ---------------- parafusos e chapa
    Ft = bc.resist_tracao_parafuso(db, e.grau, NORMA) * 1000  # N
    M_par = 2 * Ft * (h0 + h1)
    Yp, s_p = y_p_4e(e.bp, e.g, e.pfo, e.pfi, h0, h1)
    M_chapa = fy_p * e.tp**2 * Yp / g1
    linhas: list[Verificacao] = [
        Verificacao(
            "Parafusos tracionados",
            e.M,
            M_par / 1e6,
            "kN·m",
            ref + "6.3.3.1; " + ref358 + "6.10 (chapa grossa)",
            f"2·F_t,Rd·(h₀ + h₁), F_t,Rd = 0,75·A_b·f_ub/γ_a2 = {_n(Ft / 1000, 1)} kN, "
            f"h₀ = {_n(h0, 1)} mm, h₁ = {_n(h1, 1)} mm",
            equacoes=(
                "M_Rd = 2 F_t,Rd (h_0 + h_1)",
                f"M_Rd = 2 · {_n(Ft / 1000, 2)} · ({_n(h0, 1)} + {_n(h1, 1)}) / 1000 = "
                f"{_n(M_par / 1e6, 2)} kN·m",
            ),
        ),
        Verificacao(
            "Escoamento da chapa (linhas de plastificação)",
            e.M,
            M_chapa / 1e6,
            "kN·m",
            ref358 + "Tabela 6.2 (4E); " + ref + "4.9 (γ_a1)",
            f"f_y·t_p²·Y_p/γ_a1, Y_p = {_n(Yp, 0)} mm, s = ½·√(b_p·g) = {_n(s_p, 1)} mm"
            + (" (p_fi limitado a s)" if e.pfi > s_p else ""),
            equacoes=(
                "M_Rd = f_y t_p^2 Y_p / γ_a1",
                f"M_Rd = {_n(fy_p, 0)} · {_n(e.tp, 1)}^2 · {_n(Yp, 0)} / {_n(g1, 2)} = "
                f"{_n(M_chapa / 1e6, 2)} kN·m",
            ),
        ),
    ]
    grossa = M_chapa >= FATOR_CHAPA_GROSSA * M_par
    linhas.append(
        Verificacao(
            "Chapa grossa (sem efeito de alavanca)",
            FATOR_CHAPA_GROSSA * M_par / 1e6,
            M_chapa / 1e6,
            "kN·m",
            "AISC Design Guide 16, 3.1; " + ref358 + "6.10",
            "M_Rd,chapa ≥ 1,11·M_Rd,parafusos: a chapa não dobra antes de os parafusos "
            "romperem; se não passar, há efeito de alavanca, que este cálculo não inclui — "
            "aumente t_p",
            status="OK" if grossa else "ALERTA",
            aproveitamento=FATOR_CHAPA_GROSSA * M_par / M_chapa if M_chapa > 0 else math.inf,
            obrigatoria=False,
        )
    )
    An = (e.bp - 2 * (dh + bc.folga_do_furo(NORMA))) * e.tp
    linhas += [
        Verificacao(
            "Extensão da chapa: escoamento por cisalhamento",
            Ff / 2 / 1000,
            0.6 * fy_p * e.bp * e.tp / g1 / 1000,
            "kN",
            ref + "6.5.5 a); " + ref358 + "6.10 passo 8",
            "F_f/2 ≤ 0,60·f_y·b_p·t_p/γ_a1, F_f = M/(d − t_f)",
        ),
        Verificacao(
            "Extensão da chapa: ruptura por cisalhamento",
            Ff / 2 / 1000,
            0.6 * fu_p * An / g2 / 1000,
            "kN",
            ref + "6.5.5 b); " + ref358 + "6.10 passo 9",
            f"F_f/2 ≤ 0,60·f_u·A_n/γ_a2, A_n = (b_p − 2·(d_h + 2))·t_p = {_n(An, 0)} mm²",
        ),
    ]
    Fv = bc.resist_corte(db, e.grau, NORMA, e.rosca_no_plano) * 1000
    nc = e.parafusos_comprimidos
    linhas.append(
        Verificacao(
            "Corte nos parafusos do lado comprimido",
            e.V,
            nc * Fv / 1000,
            "kN",
            ref + "6.3.3.2; " + ref358 + "6.10 passo 10",
            f"{nc} parafusos × F_v,Rd = {_n(Fv / 1000, 1)} kN (os tracionados não contam)",
        )
    )
    lf_chapa = bc.lf_borda(e.de, dh) if e.simetrica else None
    contato_chapa = bc.resist_contato(db, e.tp, fu_p, lf_chapa, NORMA)
    contato_pilar = bc.resist_contato(db, pilar.tf, fu_c, None, NORMA)
    linhas.append(
        Verificacao(
            "Pressão de contato (chapa e mesa do pilar)",
            e.V,
            nc * min(contato_chapa, contato_pilar),
            "kN",
            ref + "6.3.3.3",
            f"{nc} × mín(chapa {_n(contato_chapa, 1)}; mesa do pilar {_n(contato_pilar, 1)}) kN",
        )
    )
    grupos.append(vm.Grupo("Parafusos e chapa de extremidade", linhas))
    # ---------------- soldas da viga na chapa
    fw = ELETRODOS[e.eletrodo]
    soldas: list[Verificacao] = []
    if e.solda_mesa == PENETRACAO:
        soldas.append(
            vm.linha_info(
                "Solda da mesa tracionada",
                Ff / 1000,
                "kN",
                ref + "6.2.5 (Tabela 9)",
                "penetração total com metal de solda compatível: vale a resistência do "
                "metal-base da mesa",
            )
        )
    else:
        comp = 2 * bbf - tbw
        rd = sd.resistencia_filete_por_mm(e.perna_mesa, fw, GAMA_W2) * comp
        soldas.append(
            Verificacao(
                "Solda da mesa tracionada",
                Ff / 1000,
                rd,
                "kN",
                ref + "6.2.5 (Tabela 9)",
                f"filetes de {_n(e.perna_mesa, 1)} mm dos dois lados da mesa, L = 2·b_f − t_w = "
                f"{_n(comp, 0)} mm, {e.eletrodo}",
            )
        )
    por_mm = sd.resistencia_filete_por_mm(e.perna_alma, fw, GAMA_W2)  # kN/mm
    comp_v = 2 * (d / 2 - tbf)
    soldas.append(
        Verificacao(
            "Solda da alma: cortante",
            e.V,
            por_mm * comp_v,
            "kN",
            ref + "6.2.5; AISC Design Guide 4, 3.1",
            f"2 filetes de {_n(e.perna_alma, 1)} mm entre a meia altura e a mesa comprimida "
            f"(L = {_n(comp_v, 0)} mm)",
        )
    )
    soldas.append(
        Verificacao(
            "Solda da alma junto aos parafusos tracionados",
            fy_b * tbw / g1 / 1000,
            2 * por_mm,
            "kN/mm",
            ref358 + "6.10 passo 11 (AISC Design Guide 4, 3.1)",
            "os dois filetes desenvolvem o escoamento da alma, f_y·t_w/γ_a1, por mm",
        )
    )
    soldas += sd.limites_do_filete(sd.NBR_2025, e.perna_alma, min(tbw, e.tp), None, comp_v,
                                   "Filete da alma")  # fmt: skip
    grupos.append(vm.Grupo("Soldas da viga na chapa", soldas))
    # ---------------- pilar
    E = pi.E_ACO
    c = e.pfo + e.pfi + tbf
    psi = pso = None
    if e.enrijecedores:
        psi = max(e.pfi - (e.ts - tbf) / 2, 1.0)
        pso = max(e.pfo - (e.ts - tbf) / 2, 1.0)
    Yc, s_c = y_c_4e(pilar.bf, e.g, h0, h1, c, psi, pso)
    M_mesa = fy_c * pilar.tf**2 * Yc / g1
    lp: list[Verificacao] = [
        Verificacao(
            "Flexão da mesa do pilar",
            e.M,
            M_mesa / 1e6,
            "kN·m",
            ref358 + "Tabela 6.5 (4E)" + (" com enrijecedores" if e.enrijecedores else ""),
            f"f_y·t_fc²·Y_c/γ_a1, Y_c = {_n(Yc, 0)} mm, s = {_n(s_c, 1)} mm, c = {_n(c, 1)} mm",
        )
    ]
    ln = tbf + 2 * (e.perna_mesa if e.solda_mesa == FILETE else 0.0) + 2 * e.tp
    perto = e.topo_do_pilar
    menores: list[float] = []
    rd = fl.escoamento_local_da_alma(pilar, fy_c, g1, ln, perto) / 1000
    menores.append(rd)
    lp.append(
        Verificacao(
            "Alma do pilar: escoamento local",
            Ff / 1000,
            rd,
            "kN",
            ref + ("5.7.3.2 b)" if perto else "5.7.3.2 a)"),
            f"ℓ_n = t_fb + 2·w + 2·t_p = {_n(ln, 1)} mm, k = {_n(pilar.k, 1)} mm",
        )
    )
    rd_e, item = fl.enrugamento_da_alma(pilar, fy_c, E, g1, ln, perto)
    rd_e /= 1000
    menores.append(rd_e)
    lp.append(
        Verificacao(
            "Alma do pilar: enrugamento",
            Ff / 1000,
            rd_e,
            "kN",
            ref + item,
            f"força da mesa comprimida da viga, ℓ_n = {_n(ln, 1)} mm",
        )
    )
    par_de_forcas = e.outro_lado and e.M2 > 0
    if par_de_forcas:
        rd_i = fl.instabilidade_por_compressao(pilar, fy_c, E, g1, perto) / 1000
        menores.append(rd_i)
        Ff2 = e.M2 * 1e6 / (d - tbf)
        lp.append(
            Verificacao(
                "Alma do pilar: instabilidade por compressão",
                min(Ff, Ff2) / 1000,
                rd_i,
                "kN",
                ref + "5.7.6.2",
                "as mesas comprimidas das duas vigas empurram a alma dos dois lados",
            )
        )
    # painel de alma
    M_total = abs(e.M - (e.M2 if e.outro_lado else 0.0)) * 1e6
    F_painel = max(M_total / (d - tbf) - abs(e.V_pilar) * 1000, 0.0)
    rd_p, texto_p = fl.painel_de_alma(pilar, fy_c, E, g1, e.N_pilar * 1000, e.enrijecedores)
    reforco = 0.0
    if e.reforco_alma > 0:
        reforco = 2 * 0.6 * fy_c * pilar.d * e.reforco_alma / g1
    lp.append(
        Verificacao(
            "Painel de alma do pilar: cisalhamento",
            F_painel / 1000,
            (rd_p + reforco) / 1000,
            "kN",
            ref + "5.7.7.1" + (" e 5.7.7.2" if reforco else ""),
            f"F_Sd = |M₁ − M₂|/(d − t_f) − V_pilar; F_Rd = {texto_p}"
            + (f" + 2 chapas de reforço de {_n(e.reforco_alma, 1)} mm" if reforco else "")
            + (
                ""
                if F_painel <= rd_p + reforco
                else "; não passa: use chapas de reforço da alma (5.7.7.2) ou enrijecedores diagonais (5.7.7.3)"
            ),
        )
    )
    precisa = any(
        v.status == "NÃO OK" for v in lp if v.nome.startswith(("Alma do pilar", "Flexão da mesa"))
    )
    if e.enrijecedores:
        lp = [fl._cobre(v, True) if v.nome.startswith("Alma do pilar") else v for v in lp]
    grupos.append(vm.Grupo("Pilar", lp))
    if e.enrijecedores:
        enr = fl.Enrijecedor(
            bs=e.bs, ts=e.ts, dois_lados=True,
            posicao=fl.EXTREMIDADE if e.topo_do_pilar else fl.INTERNA, corte=e.corte,
            ajustado=False, aco=e.aco_chapa, perna_alma=e.perna_alma, perna_mesa=e.perna_alma,
            eletrodo=e.eletrodo, altura_total=True,
        )  # fmt: skip
        ent = fl.EntradaForcas(
            familia=e.pilar.familia, perfil=e.pilar.nome, d=e.pilar.d, bf=e.pilar.bf,
            tf=e.pilar.tf, tw=e.pilar.tw, filete=e.pilar.filete, aco=e.aco_pilar, gama_a1=g1,
            gama_a2=g2, usar_enrijecedor=True, enrijecedor=enr,
        )  # fmt: skip
        forca = fl.ForcaLocalizada("Mesa comprimida da viga", Ff / 1000,
                                   fl.PAR if par_de_forcas else fl.COMPRESSAO, ln, bbf, 1e9)  # fmt: skip
        linhas_enr = fl._linhas_do_enrijecedor(
            ent,
            pilar,
            fy_c,
            forca,
            min(menores),
            True,
            largura_que_entrega=bbf,
            espessura_que_entrega=tbf,
        )
        # sem a solda na mesa: o enrijecedor de continuidade é soldado às duas mesas
        grupos.append(vm.Grupo("Enrijecedores de continuidade", linhas_enr))
    elif precisa:
        bs, ts = fl.sugestao_de_enrijecedor(pilar)
        lp.append(
            Verificacao(
                "Enrijecedores de continuidade necessários",
                None,
                None,
                "",
                ref + "5.7.3.3, 5.7.4.3 e 5.7.6.4",
                f"a alma do pilar não resiste sozinha: use enrijecedores alinhados às mesas da "
                f"viga (por exemplo, {bs:g} × {_n(max(ts, tbf), 1)} mm de cada lado)",
                status="NÃO OK",
                tipo="limite",
            )
        )
    # ---------------- disposições
    disp: list[Verificacao] = []
    e_min = par["e_min"]
    folga_aperto = db + 12.7
    disp += [
        vm.linha_limite("Gabarito entre parafusos", e.g, 3 * db, "mm", ref + "6.3.9",
                        f"g ≥ 3·d_b = {_n(3 * db, 1)} mm", minimo=True),
        vm.linha_limite("Distância à borda da chapa (fora)", e.de, e_min, "mm",
                        ref + "6.3.11 (Tabela 14)", f"≥ {_n(e_min, 0)} mm (borda cortada)",
                        minimo=True),
        vm.linha_limite("Distância à borda lateral da chapa", (e.bp - e.g) / 2, e_min, "mm",
                        ref + "6.3.11 (Tabela 14)", f"(b_p − g)/2 ≥ {_n(e_min, 0)} mm",
                        minimo=True),
        vm.linha_limite("Distância à borda da mesa do pilar", (pilar.bf - e.g) / 2, e_min, "mm",
                        ref + "6.3.11 (Tabela 14)", f"(b_fc − g)/2 ≥ {_n(e_min, 0)} mm",
                        minimo=True),
        vm.linha_limite("Folga para aperto (p_fo)", e.pfo, folga_aperto, "mm",
                        "AISC Design Guide 4, 2.1 (p_f ≥ d_b + 1/2\")",
                        f"p_fo ≥ {_n(folga_aperto, 1)} mm", minimo=True, obrigatoria=False),
        vm.linha_limite("Folga para aperto (p_fi)", e.pfi, folga_aperto, "mm",
                        "AISC Design Guide 4, 2.1 (p_f ≥ d_b + 1/2\")",
                        f"p_fi ≥ {_n(folga_aperto, 1)} mm", minimo=True, obrigatoria=False),
        vm.linha_limite("Largura da chapa", e.bp, bbf + 25.4, "mm",
                        ref358 + "6.8 (b_p ≤ b_bf + 1\")", f"b_bf ≤ b_p ≤ {_n(bbf + 25.4, 1)} mm",
                        obrigatoria=False),
        vm.linha_limite("Largura útil da chapa", e.bp, bbf, "mm", ref358 + "6.8",
                        f"b_p ≥ b_bf = {_n(bbf, 1)} mm", minimo=True),
    ]  # fmt: skip
    grupos.append(vm.Grupo("Disposições construtivas", disp))
    geometria = {
        "h0": h0, "h1": h1, "Yp": Yp, "Yc": Yc, "Ff_kN": Ff / 1000,
        "altura_da_chapa": d + e.pfo + e.de + (e.pfo + e.de if e.simetrica else 25.0),
        "M_Rd_kNm": min(M_par, M_chapa, M_mesa) / 1e6,
    }  # fmt: skip
    return ResultadoRigida(e, viga, pilar, grupos, geometria, avisos)


def registro(r: ResultadoRigida) -> dict[str, Any]:
    e = r.entrada
    entradas = {
        "viga": f"{r.viga.descricao}; {e.aco_viga}",
        "pilar": f"{r.pilar.descricao}; {e.aco_pilar}",
        "esforcos": (
            f"M = {_n(e.M, 1)} kN·m, V = {_n(e.V, 1)} kN; pilar N = {_n(e.N_pilar, 1)} kN"
            + (f"; viga do outro lado M₂ = {_n(e.M2, 1)} kN·m" if e.outro_lado else "")
        ),
        "parafusos": (
            f"8 × {e.diametro} {e.grau} ({4} junto à mesa tracionada), g = {_n(e.g, 0)} mm, "
            f"p_fo = {_n(e.pfo, 0)} mm, p_fi = {_n(e.pfi, 0)} mm"
            if e.simetrica
            else f"6 × {e.diametro} {e.grau}, g = {_n(e.g, 0)} mm"
        ),
        "chapa": (
            f"{_n(e.bp, 0)} × {_n(e.tp, 1)} mm, {e.aco_chapa}, altura ≈ "
            f"{_n(r.geometria['altura_da_chapa'], 0)} mm"
        ),
        "soldas": (
            f"mesa: {e.solda_mesa.lower()}"
            + (f" {_n(e.perna_mesa, 1)} mm" if e.solda_mesa == FILETE else "")
            + f"; alma: filetes de {_n(e.perna_alma, 1)} mm, {e.eletrodo}"
        ),
        "reforcos_do_pilar": (
            ("enrijecedores de continuidade " + f"{_n(e.bs, 0)} × {_n(e.ts, 1)} mm")
            if e.enrijecedores
            else "sem enrijecedores"
        )
        + (f"; chapas de reforço da alma de {_n(e.reforco_alma, 1)} mm" if e.reforco_alma else ""),
    }
    return vm.registro_padrao(
        modulo_id=MODULO_ID,
        modulo_titulo=MODULO_TITULO,
        titulo=f"Ligação rígida — {r.viga.nome} em {r.pilar.nome}",
        grupos=r.grupos,
        entradas=entradas,
        metodo=(
            "Chapa de extremidade estendida com quatro parafusos junto à mesa tracionada (4E), "
            "pelo modelo de linhas de plastificação com chapa grossa da AISC 358-16 (capítulo 6) "
            "e dos AISC Design Guides 4 e 16, com as resistências da ABNT NBR 8800:2025; pilar "
            "pela 5.7 da NBR 8800:2025."
        ),
        premissas=[
            "Chapa grossa: os parafusos rompem antes de a chapa dobrar, sem efeito de alavanca "
            "(condição verificada).",
            "O cortante da viga passa só pelos parafusos do lado comprimido.",
            "O momento vira um binário nas mesas da viga, de braço d − t_f.",
            "Painel de alma do pilar com a força |M₁ − M₂|/(d − t_f) descontado o cortante do "
            "pilar.",
            "A viga em si (flexão, cortante e FLT) é verificada à parte.",
        ],
        referencias=REFERENCIAS,
        objeto="A ligação",
        alertas=r.avisos,
    )


def com(e: EntradaRigida, **mudancas: Any) -> EntradaRigida:
    return replace(e, **mudancas)
