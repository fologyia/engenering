"""Ligações do mezanino e da escada: os casos comuns, com a tabela de verificações e o registro.

Três cálculos, cada um fechando numa lista de :class:`~core.verificacao.Verificacao` (o memorial a
mostra como "o que passou / o que não passou"):

1. **Ligação flexível por chapa simples** (viga–viga ou viga–pilar), NBR 8800: chapa soldada no
   apoio (alma da viga principal, mesa ou alma do pilar) e parafusada na alma da viga apoiada, uma
   linha vertical de parafusos, com ou sem recorte da mesa superior. Parafusos (corte e pressão de
   contato na chapa e na alma, com a excentricidade ``a`` da linha de solda à linha dos
   parafusos), chapa (cisalhamento, colapso por rasgamento, flexão e tração/compressão), alma da
   viga (cisalhamento, colapso por rasgamento e flexão na seção do recorte), solda da chapa no
   apoio (filetes dos dois lados, método elástico) e as disposições construtivas.
2. **Ligação parafusada em perfil formado a frio**, NBR 14762:2010 (10.3, 10.4 e 9.6): corte do
   parafuso, rasgamento e esmagamento no perfil e na chapa, tração na seção líquida com o C_t do
   perfil ligado só pela alma, colapso por rasgamento, espaçamentos e a regra dos 50 % (10.1).
3. **Grupo de soldas de filete**, NBR 8800 6.2 (Tabela 8, Tabela 10 e 6.2.6.2) — ou NBR 14762
   10.2.3 quando a parte mais fina tem até 4,75 mm —, com força cortante, normal e momento no
   plano pelo método elástico.

Os coeficientes conferidos nas normas (NBR 8800:2008, NBR 14762:2010); o Projeto de revisão da
NBR 8800 (2024) muda os coeficientes do corte do parafuso (0,45/0,56), via
:mod:`core.bolted_connection`. Casos especiais (ligações rígidas, chapa de extremidade com momento,
enrijecedores, ligações de perfis tubulares, efeito de alavanca) ficam fora: o programa cobre o caso
comum e o caso específico é do projetista.

Unidades: mm, MPa, kN e kN·m. Sem Streamlit.
"""

from __future__ import annotations

import io
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, fields, replace
from typing import Any

from PIL import Image, ImageDraw

from core import bolted_connection as bc
from core import section_catalog as sc
from core.beam_charts import ImagemDiagrama, _fonte
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    linhas_para_registro,
    numero_json,
    status_geral,
)

MODULO_ID = "ligacoes_estruturais"
MODULO_TITULO = "Ligações estruturais"

GAMMA_A1 = 1.10  # NBR 8800 4.8.2
GAMMA_A2 = 1.35
GAMMA_W2 = 1.35  # NBR 8800 Tabela 8, nota k (combinações normais)
FOLGA_FURO = 2.0  # NBR 8800 5.2.4.1: furo + 2 mm na área líquida
NORMAS = ("NBR8800_2024", "NBR8800_2008")
NORMAS_ROTULOS = {
    "NBR8800_2024": "NBR 8800 (Projeto de revisão 2024)",
    "NBR8800_2008": "NBR 8800:2008",
}
ELETRODOS = {"E60": 415.0, "E70": 485.0, "E80": 550.0}  # NBR 8800 Tabela A.4
LIMITE_CHAPA_FINA = 4.75  # NBR 14762 10.2.1 e 10.3.1

#: Aços das chapas finas com qualificação estrutural (NBR 14762 Tabela 1) e o limite para aço sem
#: qualificação (4.2), (f_y, f_u) em MPa. Os aços de chapa grossa vêm da NBR 8800 (bc.ACOS).
ACOS_FRIO: dict[str, tuple[float, float]] = {
    "ZAR 250 (NBR 7008)": (250.0, 360.0),
    "ZAR 280 (NBR 7008)": (280.0, 380.0),
    "ZAR 345 (NBR 7008)": (345.0, 430.0),
    "CF-26 (NBR 6649)": (260.0, 400.0),
    "CF-28 (NBR 6649)": (280.0, 440.0),
    "Sem qualificação estrutural (NBR 14762 4.2)": (180.0, 300.0),
}
ACOS: dict[str, tuple[float, float]] = {
    **{k: (float(v[0]), float(v[1])) for k, v in bc.ACOS.items()},
    **ACOS_FRIO,
}

#: Parafusos da NBR 14762 Tabela 16 (f_ub em MPa; o A325 depende do diâmetro) e 4.4.
SEM_QUALIFICACAO = "Sem qualificação estrutural"
PARAFUSOS_FRIO = (
    "ASTM A307",
    "ASTM A325",
    "ISO 898-1 classe 4.6",
    "ISO 4016 classe 8.8",
    SEM_QUALIFICACAO,
)


def fub_frio(especificacao: str, d_mm: float) -> float:
    """f_ub (MPa) pela NBR 14762 Tabela 16 (e 4.4 para o parafuso sem qualificação)."""
    if especificacao == "ASTM A307":
        return 415.0 if d_mm >= 12.7 - 1e-6 else 370.0
    if especificacao == "ASTM A325":
        return 825.0 if d_mm <= 25.4 + 1e-6 else 725.0
    if especificacao == "ISO 898-1 classe 4.6":
        return 400.0
    if especificacao == "ISO 4016 classe 8.8":
        return 800.0
    if especificacao == SEM_QUALIFICACAO:
        return 300.0
    raise ValueError(f"Parafuso desconhecido: {especificacao!r}.")


class LigacaoInvalida(ValueError):
    """Dado que o cálculo não aceita; a mensagem diz o que corrigir."""


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor + 0.0:.{casas}f}".replace(".", ",")


def _minimo(
    nome: str, exigido: float, adotado: float, unidade: str, ref: str, formula: str
) -> Verificacao:
    """Limite inferior: passa com adotado ≥ exigido (aproveitamento = exigido/adotado)."""
    status = "OK" if adotado >= exigido - 1e-9 else "NÃO OK"
    return Verificacao(nome, exigido, adotado, unidade, ref, formula, status=status, tipo="limite")


def _maximo(
    nome: str, valor: float, limite: float, unidade: str, ref: str, formula: str
) -> Verificacao:
    status = "OK" if valor <= limite + 1e-9 else "NÃO OK"
    return Verificacao(nome, valor, limite, unidade, ref, formula, status=status, tipo="limite")


def _na(nome: str, ref: str, motivo: str) -> Verificacao:
    return Verificacao(nome, None, None, "—", ref, motivo, status="N/A", tipo="limite")


@dataclass(frozen=True)
class ResultadoLigacao:
    tipo: str
    titulo: str
    entrada: Any
    verificacoes: tuple[Verificacao, ...]
    grandezas: dict[str, float] = field(default_factory=dict)
    avisos: tuple[str, ...] = ()

    @property
    def status(self) -> str:
        return status_geral(list(self.verificacoes))

    @property
    def aproveitamento_maximo(self) -> float:
        valores = [
            v.aproveitamento
            for v in self.verificacoes
            if v.tipo == "resistencia" and v.aproveitamento is not None
        ]
        return max(valores) if valores else 0.0

    @property
    def governante(self) -> Verificacao | None:
        com = [
            v for v in self.verificacoes if v.tipo == "resistencia" and v.aproveitamento is not None
        ]
        return max(com, key=lambda v: v.aproveitamento or 0.0) if com else None


# =============================================================================================
# Solda de filete: tabelas da NBR 8800
# =============================================================================================
def perna_minima(t_menor_mm: float) -> float:
    """NBR 8800 Tabela 10 (pela parte menos espessa)."""
    if t_menor_mm <= 6.35:
        return 3.0
    if t_menor_mm <= 12.5:
        return 5.0
    if t_menor_mm <= 19.0:
        return 6.0
    return 8.0


def perna_maxima(t_borda_mm: float) -> float:
    """NBR 8800 6.2.6.2.2: ao longo da borda de uma chapa."""
    return t_borda_mm if t_borda_mm < 6.35 else t_borda_mm - 1.5


def _limites_do_filete(
    perna: float, t_menor: float, t_borda: float | None, comprimento: float, rotulo: str = ""
) -> list[Verificacao]:
    sufixo = f" ({rotulo})" if rotulo else ""
    linhas = [
        _minimo(
            f"Solda: perna mínima{sufixo}",
            perna_minima(t_menor),
            perna,
            "mm",
            "NBR 8800 6.2.6.2.1, Tabela 10",
            f"parte menos espessa t = {_n(t_menor, 1)} mm",
        )
    ]
    if t_borda is not None:
        linhas.append(
            _maximo(
                f"Solda: perna máxima na borda da chapa{sufixo}",
                perna,
                perna_maxima(t_borda),
                "mm",
                "NBR 8800 6.2.6.2.2",
                "t < 6,35 mm: perna ≤ t; senão perna ≤ t − 1,5 mm",
            )
        )
    linhas.append(
        _minimo(
            f"Solda: comprimento mínimo{sufixo}",
            max(4 * perna, 40.0),
            comprimento,
            "mm",
            "NBR 8800 6.2.6.2.3",
            "L ≥ 4·perna e ≥ 40 mm",
        )
    )
    return linhas


def resistencia_filete_por_mm(perna_mm: float, eletrodo: str) -> float:
    """Metal da solda, por mm de filete (kN/mm): 0,60·f_w·(0,707·perna)/γ_w2 (Tabela 8)."""
    return 0.60 * ELETRODOS[eletrodo] * 0.707 * perna_mm / GAMMA_W2 / 1000.0


# =============================================================================================
# 1. Chapa simples (viga–viga e viga–pilar)
# =============================================================================================
APOIO_VIGA = "viga"
APOIO_PILAR_MESA = "pilar_mesa"
APOIO_PILAR_ALMA = "pilar_alma"
APOIOS = {
    APOIO_VIGA: "Alma de outra viga (viga–viga)",
    APOIO_PILAR_MESA: "Mesa do pilar (viga–pilar)",
    APOIO_PILAR_ALMA: "Alma do pilar (viga–pilar)",
}
CHAPA_SIMPLES = "chapa_simples"


@dataclass(frozen=True)
class EntradaChapaSimples:
    perfil: str = "W 250 x 17,9"  # viga apoiada
    aco_viga: str = "ASTM A572 Gr 50"
    apoio: str = APOIO_VIGA
    t_apoio_mm: float = 5.8  # alma da viga principal ou mesa/alma do pilar (para a solda)
    recorte: bool = True
    recorte_altura_mm: float = 30.0
    recorte_comprimento_mm: float = 100.0
    parafuso: str = '3/4"'
    grau: str = "A325"
    rosca_no_plano: bool = True
    n_parafusos: int = 3
    passo_mm: float = 70.0
    borda_vertical_mm: float = 35.0  # na chapa, do furo ao topo e à base da chapa
    distancia_solda_furo_mm: float = 60.0  # a: da linha de solda à linha dos parafusos
    borda_horizontal_chapa_mm: float = 35.0  # do furo à borda livre da chapa
    borda_alma_mm: float = 35.0  # do furo à ponta da viga apoiada
    topo_alma_mm: float = 40.0  # do parafuso de cima ao topo da alma (recorte) ou à mesa
    t_chapa_mm: float = 8.0
    aco_chapa: str = "ASTM A36"
    perna_solda_mm: float = 6.0
    eletrodo: str = "E70"
    v_sd_kN: float = 40.0
    n_sd_kN: float = 0.0  # tração positiva
    norma: str = "NBR8800_2024"
    anglo: bool = False

    @property
    def altura_chapa_mm(self) -> float:
        return 2 * self.borda_vertical_mm + (self.n_parafusos - 1) * self.passo_mm

    @property
    def largura_chapa_mm(self) -> float:
        return self.distancia_solda_furo_mm + self.borda_horizontal_chapa_mm


def _validar_chapa(e: EntradaChapaSimples) -> None:
    if e.n_parafusos < 1:
        raise LigacaoInvalida("A ligação precisa de pelo menos um parafuso.")
    for nome, valor in (
        ("espessura da chapa", e.t_chapa_mm),
        ("perna da solda", e.perna_solda_mm),
        ("espessura do apoio", e.t_apoio_mm),
        ("passo", e.passo_mm if e.n_parafusos > 1 else 1.0),
        ("distância à borda vertical", e.borda_vertical_mm),
        ("distância da solda aos furos", e.distancia_solda_furo_mm),
        ("distância à borda horizontal da chapa", e.borda_horizontal_chapa_mm),
        ("distância do furo à ponta da viga", e.borda_alma_mm),
        ("distância do parafuso ao topo da alma", e.topo_alma_mm),
    ):
        if not valor > 0:
            raise LigacaoInvalida(f"A {nome} precisa ser maior que zero.")
    if e.recorte and (e.recorte_altura_mm <= 0 or e.recorte_comprimento_mm <= 0):
        raise LigacaoInvalida("Com recorte, informe a altura e o comprimento do recorte.")
    if e.v_sd_kN < 0:
        raise LigacaoInvalida("Informe a força cortante de cálculo como valor positivo.")
    if e.norma not in NORMAS:
        raise LigacaoInvalida(f"Norma desconhecida: {e.norma!r}.")
    if e.apoio not in APOIOS:
        raise LigacaoInvalida(f"Apoio desconhecido: {e.apoio!r}.")
    for aco in (e.aco_viga, e.aco_chapa):
        if aco not in ACOS:
            raise LigacaoInvalida(f"Aço desconhecido: {aco!r}.")
    if e.parafuso not in bc.PARAFUSOS or e.grau not in bc.GRAUS:
        raise LigacaoInvalida("Escolha o parafuso e o grau da lista.")
    if e.eletrodo not in ELETRODOS:
        raise LigacaoInvalida(f"Eletrodo desconhecido: {e.eletrodo!r}.")


def _forca_no_parafuso(coords: list[tuple[float, float]], v: float, n: float, m: float) -> float:
    """O parafuso mais solicitado, com o momento no sentido que soma com a força normal."""
    return max(
        bc.grupo_excentrico_elastico(coords, V=v, N=n, M=sinal * m)["R_max"]
        for sinal in (1.0, -1.0)
    )


def calcular_chapa_simples(e: EntradaChapaSimples) -> ResultadoLigacao:
    _validar_chapa(e)
    try:
        perfil = sc.obter_perfil(e.perfil)
    except (KeyError, sc.ErroDeCatalogo) as erro:
        raise LigacaoInvalida(f"Perfil desconhecido: {e.perfil!r}.") from erro
    d, tw, tf = perfil.altura_mm, perfil.espessura_alma_mm, perfil.espessura_mesa_mm
    fy_v, fu_v = ACOS[e.aco_viga]
    fy_c, fu_c = ACOS[e.aco_chapa]
    par = bc.dados_parafuso(e.parafuso)
    db, dh, emin = float(par["d_b"]), float(par["d_h"]), float(par["e_min"])
    dhl = dh + FOLGA_FURO
    n, s, tp = e.n_parafusos, e.passo_mm, e.t_chapa_mm
    hp, a = e.altura_chapa_mm, e.distancia_solda_furo_mm
    v, nt = e.v_sd_kN, e.n_sd_kN
    m_kNm = v * a / 1000.0
    linhas: list[Verificacao] = []

    # ------------------------------------------------------------------ parafusos
    coords = [(0.0, k * s) for k in range(n)]
    f_par = _forca_no_parafuso(coords, v, nt, m_kNm)
    fv = bc.resist_corte(db, e.grau, e.norma, e.rosca_no_plano, 1)
    lf_chapa = [e.borda_vertical_mm - dh / 2, e.borda_horizontal_chapa_mm - dh / 2]
    lf_alma = [e.borda_alma_mm - dh / 2]
    if n > 1:
        lf_chapa.append(s - dh)
        lf_alma.append(s - dh)
    if e.recorte:
        lf_alma.append(e.topo_alma_mm - dh / 2)
    fc_chapa = bc.resist_contato(db, tp, fu_c, min(lf_chapa), e.norma)
    fc_alma = bc.resist_contato(db, tw, fu_v, min(lf_alma), e.norma)
    r_par = min(fv, fc_chapa, fc_alma)
    governa = {fv: "corte do parafuso", fc_chapa: "contato na chapa", fc_alma: "contato na alma"}[
        r_par
    ]
    linhas.append(
        Verificacao(
            "Parafuso mais solicitado (V, N e M = V·a)",
            f_par,
            r_par,
            "kN",
            "NBR 8800 6.3.3.2 e 6.3.3.3",
            f"{n} parafusos {e.parafuso} {e.grau}; M = V·a = {_n(v)}·{_n(a / 1000, 3)} = "
            f"{_n(m_kNm, 3)} kN·m; F_v,Rd = {_n(fv)} kN, F_c,Rd chapa = {_n(fc_chapa)} kN, alma "
            f"= {_n(fc_alma)} kN (governa {governa}; ℓ_f mínimo de cada parte)",
        )
    )

    # ------------------------------------------------------------------ chapa
    ag_c = hp * tp
    anv_c = (hp - n * dhl) * tp
    linhas.append(
        Verificacao(
            "Chapa: escoamento por cisalhamento",
            v,
            0.60 * fy_c * ag_c / GAMMA_A1 / 1000,
            "kN",
            "NBR 8800 6.5.5 a)",
            f"0,60·f_y·A_g/γ_a1, A_g = {_n(hp, 0)}·{_n(tp, 1)} mm",
        )
    )
    linhas.append(
        Verificacao(
            "Chapa: ruptura por cisalhamento",
            v,
            0.60 * fu_c * anv_c / GAMMA_A2 / 1000,
            "kN",
            "NBR 8800 6.5.5 b)",
            f"0,60·f_u·A_nv/γ_a2, A_nv = ({_n(hp, 0)} − {n}·{_n(dhl, 1)})·{_n(tp, 1)} mm",
        )
    )
    agv = (e.borda_vertical_mm + (n - 1) * s) * tp
    anv = agv - (n - 0.5) * dhl * tp
    ant = (e.borda_horizontal_chapa_mm - 0.5 * dhl) * tp
    linhas.append(
        Verificacao(
            "Chapa: colapso por rasgamento",
            v,
            bc.resist_colapso_rasgamento(agv, anv, ant, fy_c, fu_c, e.norma, 1.0),
            "kN",
            "NBR 8800 6.5.6",
            f"A_gv = {_n(agv, 0)}, A_nv = {_n(anv, 0)}, A_nt = {_n(ant, 0)} mm²; C_ts = 1,0",
        )
    )
    m_rd_chapa = fy_c * tp * hp**2 / 4 / GAMMA_A1 / 1e6
    linhas.append(
        Verificacao(
            "Chapa: flexão na face do apoio (M = V·a)",
            m_kNm,
            m_rd_chapa,
            "kN·m",
            "NBR 8800 5.4.2 (seção retangular, Z = t·h²/4)",
            "excentricidade a da linha de solda aos parafusos, a favor da segurança",
        )
    )
    n_rd_chapa = None
    if nt > 0:
        an = min((hp - n * dhl) * tp, 0.85 * ag_c)
        n_rd_chapa = min(ag_c * fy_c / GAMMA_A1, an * fu_c / GAMMA_A2) / 1000
        linhas.append(
            Verificacao(
                "Chapa: tração",
                nt,
                n_rd_chapa,
                "kN",
                "NBR 8800 6.5.3",
                f"mín(A_g·f_y/γ_a1; A_e·f_u/γ_a2), A_e = A_n ≤ 0,85·A_g = {_n(an, 0)} mm²",
            )
        )
    elif nt < 0:
        n_rd_chapa = ag_c * fy_c / GAMMA_A1 / 1000
        linhas.append(
            Verificacao(
                "Chapa: compressão (escoamento)",
                -nt,
                n_rd_chapa,
                "kN",
                "NBR 8800 6.5.4 a)",
                "vale com KL/r ≤ 25 (chapa curta junto ao apoio)",
            )
        )
    if n_rd_chapa:
        indice = abs(nt) / n_rd_chapa + m_kNm / m_rd_chapa
        linhas.append(
            Verificacao(
                "Chapa: interação N + M",
                indice,
                1.0,
                "—",
                "NBR 8800 5.5.1.2 (simplificada)",
                "|N|/N_Rd + M/M_Rd ≤ 1",
            )
        )

    # ------------------------------------------------------------------ alma da viga apoiada
    altura_alma = d - e.recorte_altura_mm if e.recorte else d
    linhas.append(
        Verificacao(
            "Alma da viga: escoamento por cisalhamento",
            v,
            0.60 * fy_v * altura_alma * tw / GAMMA_A1 / 1000,
            "kN",
            "NBR 8800 6.5.5 a)",
            f"altura {'recortada ' if e.recorte else ''}{_n(altura_alma, 0)} mm × t_w = {_n(tw, 1)} mm",
        )
    )
    linhas.append(
        Verificacao(
            "Alma da viga: ruptura por cisalhamento na linha dos furos",
            v,
            0.60 * fu_v * (altura_alma - n * dhl) * tw / GAMMA_A2 / 1000,
            "kN",
            "NBR 8800 6.5.5 b)",
            f"A_nv = ({_n(altura_alma, 0)} − {n}·{_n(dhl, 1)})·{_n(tw, 1)} mm",
        )
    )
    if e.recorte:
        agv_w = (e.topo_alma_mm + (n - 1) * s) * tw
        anv_w = agv_w - (n - 0.5) * dhl * tw
        ant_w = (e.borda_alma_mm - 0.5 * dhl) * tw
        linhas.append(
            Verificacao(
                "Alma recortada: colapso por rasgamento",
                v,
                bc.resist_colapso_rasgamento(agv_w, anv_w, ant_w, fy_v, fu_v, e.norma, 1.0),
                "kN",
                "NBR 8800 6.5.6 (Figura 18)",
                f"A_gv = {_n(agv_w, 0)}, A_nv = {_n(anv_w, 0)}, A_nt = {_n(ant_w, 0)} mm²; C_ts = 1,0",
            )
        )
        w_rec = tw * altura_alma**2 / 6
        linhas.append(
            Verificacao(
                "Alma recortada: flexão na seção do recorte (M = V·c)",
                v * e.recorte_comprimento_mm / 1000,
                fy_v * w_rec / GAMMA_A1 / 1e6,
                "kN·m",
                "NBR 8800 6.5 (seção da alma, sem a mesa inferior: a favor da segurança)",
                f"c = {_n(e.recorte_comprimento_mm, 0)} mm; W = t_w·h²/6 = {_n(w_rec / 1e3, 1)} cm³",
            )
        )
        usual = e.recorte_comprimento_mm <= d and e.recorte_altura_mm <= 0.2 * d
        linhas.append(
            Verificacao(
                "Recorte na faixa usual (c ≤ d e d_c ≤ 0,2·d)",
                None,
                None,
                "—",
                "AISC Manual, Parte 9 (vigas recortadas)",
                "dentro da faixa usual"
                if usual
                else "fora da faixa usual: confira a flambagem local da alma recortada à parte",
                status="OK" if usual else "ALERTA",
                tipo="limite",
            )
        )
    else:
        linhas.append(
            _na(
                "Alma recortada: colapso por rasgamento",
                "NBR 8800 6.5.6",
                "sem recorte: a alma continua até a mesa superior",
            )
        )

    # ------------------------------------------------------------------ solda da chapa no apoio
    comprimento = hp
    f_v = v / (2 * comprimento)
    f_n = abs(nt) / (2 * comprimento)
    f_m = 3 * m_kNm * 1000 / comprimento**2
    f_solda = math.hypot(f_n + f_m, f_v)
    r_solda = resistencia_filete_por_mm(e.perna_solda_mm, e.eletrodo)
    linhas.append(
        Verificacao(
            "Solda da chapa no apoio (dois filetes)",
            f_solda * 10,
            r_solda * 10,
            "kN/cm",
            "NBR 8800 6.2.5.1, Tabela 8",
            f"filetes de {_n(e.perna_solda_mm, 0)} mm × {_n(comprimento, 0)} mm, {e.eletrodo}; "
            "método elástico com V, N e M = V·a; 0,60·f_w·(0,707·perna)/γ_w2 por cm",
        )
    )
    linhas.append(
        Verificacao(
            "Metal-base do apoio junto à solda (cisalhamento)",
            2 * f_solda * 10,
            0.60 * min(fy_c, ACOS[e.aco_viga][0]) * e.t_apoio_mm / GAMMA_A1 / 1000 * 10,
            "kN/cm",
            "NBR 8800 6.5.5 a)",
            f"os dois filetes descarregam na espessura do apoio t = {_n(e.t_apoio_mm, 1)} mm "
            "(aço do apoio tomado igual ao da viga)",
        )
    )
    linhas.extend(_limites_do_filete(e.perna_solda_mm, min(tp, e.t_apoio_mm), tp, comprimento))

    # ------------------------------------------------------------------ geometria e disposições
    alma_livre = d - tf - (e.recorte_altura_mm if e.recorte else tf)
    ocupado = hp + max(e.topo_alma_mm - e.borda_vertical_mm, 0.0)
    linhas.append(
        _maximo(
            "Chapa cabe na alma livre da viga",
            ocupado,
            alma_livre,
            "mm",
            "geometria",
            f"altura da chapa {_n(hp, 0)} mm a partir de {_n(max(e.topo_alma_mm - e.borda_vertical_mm, 0), 0)} "
            f"mm do topo da alma {'recortada' if e.recorte else '(face da mesa)'}",
        )
    )
    linhas.append(
        _minimo(
            "Distância do furo à ponta da viga",
            emin,
            e.borda_alma_mm,
            "mm",
            "NBR 8800 6.3.11",
            "e ≥ e_mín da tabela de distâncias à borda",
        )
    )
    linhas.extend(
        replace(v, tipo="limite")  # limite geométrico: não entra no aproveitamento
        for v in bc.disposicoes_construtivas(
            db,
            dh,
            emin,
            tp,
            e.borda_vertical_mm,
            s if n > 1 else 0.0,
            e_v=e.borda_horizontal_chapa_mm,
        )
    )
    limite_ductil = db / 2 + 1.6
    linhas.append(
        Verificacao(
            "Ductilidade: chapa ou alma ≤ d_b/2 + 1,6 mm",
            min(tp, tw),
            limite_ductil,
            "mm",
            "AISC Manual, Parte 10 (chapa simples convencional)",
            "a peça mais fina deve deformar para a ligação girar como flexível",
            status="OK" if min(tp, tw) <= limite_ductil + 1e-9 else "ALERTA",
            tipo="limite",
        )
    )
    if e.anglo:
        linhas.extend(bc.criterio_anglo(n, e.grau, db))
    titulo = (
        f"Ligação flexível por chapa simples — {e.perfil} em "
        f"{APOIOS[e.apoio].split(' (')[0].lower()}"
    )
    return ResultadoLigacao(
        CHAPA_SIMPLES,
        titulo,
        e,
        tuple(linhas),
        {
            "altura_chapa_mm": hp,
            "largura_chapa_mm": e.largura_chapa_mm,
            "forca_no_parafuso_kN": f_par,
            "resistencia_do_parafuso_kN": r_par,
            "momento_V_a_kNm": m_kNm,
            "solda_kN_cm": f_solda * 10,
        },
    )


# =============================================================================================
# 2. Perfil formado a frio parafusado (NBR 14762)
# =============================================================================================
PERFIL_FRIO = "perfil_frio"
PERFIL_A_MAO = "Informado à mão"


@dataclass(frozen=True)
class EntradaPerfilFrio:
    perfil: str = "C ideal 150×50×17×3"
    t_perfil_mm: float | None = None  # à mão: espessura, área e x̄
    area_perfil_mm2: float | None = None
    excentricidade_mm: float | None = None  # x̄: centroide ao plano de cisalhamento (face da alma)
    aco_perfil: str = "ZAR 250 (NBR 7008)"
    t_chapa_mm: float = 6.35
    aco_chapa: str = "ASTM A36"
    parafuso: str = '1/2"'
    especificacao: str = "ASTM A307"
    rosca_no_plano: bool = True
    planos_de_corte: int = 1
    n_linhas: int = 1  # linhas paralelas à força axial
    n_por_linha: int = 2  # parafusos em cada linha, na direção da força axial
    passo_mm: float = 50.0  # s, na direção da força axial
    gabarito_mm: float = 50.0  # g, entre linhas
    borda_mm: float = 30.0  # e: do furo à extremidade do perfil, na direção da força axial
    borda_lateral_mm: float = 30.0  # e₁: do furo à borda, na direção transversal
    n_sd_kN: float = 15.0  # tração positiva
    v_sd_kN: float = 0.0  # transversal à barra, no plano da ligação
    barra_axial: bool = True  # treliça ou contraventamento: vale a regra dos 50 % (10.1 a)
    n_rd_barra_kN: float | None = None  # para a regra dos 50 % (vazio: a tração calculada aqui)


def _dados_perfil_frio(e: EntradaPerfilFrio) -> tuple[float, float, float]:
    """(t, A, x̄) do perfil: do catálogo ou informados à mão."""
    if e.perfil == PERFIL_A_MAO:
        if not (e.t_perfil_mm and e.area_perfil_mm2 and e.excentricidade_mm is not None):
            raise LigacaoInvalida("Perfil à mão: informe a espessura, a área e o x̄.")
        return float(e.t_perfil_mm), float(e.area_perfil_mm2), float(e.excentricidade_mm)
    try:
        p = sc.obter_perfil(e.perfil)
    except (KeyError, sc.ErroDeCatalogo) as erro:
        raise LigacaoInvalida(f"Perfil desconhecido: {e.perfil!r}.") from erro
    x = p.centroide_x_mm or p.largura_mm / 2
    return p.espessura_alma_mm, p.area_mm2, x


def furo_padrao_frio(d_mm: float) -> float:
    """NBR 14762 Tabela 15: d + 0,8 (d < 12,5 mm) ou d + 1,5 mm."""
    return d_mm + (0.8 if d_mm < 12.5 else 1.5)


def coef_ct_perfil(e: EntradaPerfilFrio, d: float, x: float, largura_g: float) -> tuple[float, str]:
    """C_t da NBR 14762 9.6.2 c), item 3 (perfil ligado só pela alma)."""
    if e.n_por_linha >= 2:
        comprimento = (e.n_por_linha - 1) * e.passo_mm
        bruto = 1 - 1.2 * x / comprimento
        return min(
            bruto, 0.9
        ), f"C_t = 1 − 1,2·x̄/L = 1 − 1,2·{_n(x, 1)}/{_n(comprimento, 0)} (≤ 0,9; ≥ 0,4)"
    g = largura_g
    return min(
        2.5 * d / g, 1.0
    ), f"todos na mesma seção: C_t = 2,5·d/g = 2,5·{_n(d, 1)}/{_n(g, 0)} ≤ 1"


def calcular_perfil_frio(e: EntradaPerfilFrio) -> ResultadoLigacao:
    if e.n_linhas < 1 or e.n_por_linha < 1:
        raise LigacaoInvalida("A ligação precisa de pelo menos um parafuso.")
    if e.planos_de_corte not in (1, 2):
        raise LigacaoInvalida("Planos de corte: 1 ou 2.")
    for aco in (e.aco_perfil, e.aco_chapa):
        if aco not in ACOS:
            raise LigacaoInvalida(f"Aço desconhecido: {aco!r}.")
    if e.parafuso not in bc.PARAFUSOS:
        raise LigacaoInvalida("Escolha o diâmetro do parafuso da lista.")
    if e.especificacao not in PARAFUSOS_FRIO:
        raise LigacaoInvalida("Escolha a especificação do parafuso da lista.")
    positivos = [e.borda_mm, e.borda_lateral_mm, e.t_chapa_mm]
    if e.n_por_linha > 1:
        positivos.append(e.passo_mm)
    if e.n_linhas > 1:
        positivos.append(e.gabarito_mm)
    if min(positivos) <= 0:
        raise LigacaoInvalida("Passo, gabarito, bordas e espessuras precisam ser maiores que zero.")
    t, area, x = _dados_perfil_frio(e)
    fy_p, fu_p = ACOS[e.aco_perfil]
    fy_c, fu_c = ACOS[e.aco_chapa]
    d = float(bc.dados_parafuso(e.parafuso)["d_b"])
    df = furo_padrao_frio(d)
    n = e.n_linhas * e.n_por_linha
    nt, vt = e.n_sd_kN, e.v_sd_kN
    f_ax, f_tr = abs(nt) / n, abs(vt) / n
    f_par = math.hypot(f_ax, f_tr)
    linhas: list[Verificacao] = []
    avisos: list[str] = []

    # ------------------------------------------------------------------ parafuso
    fub = fub_frio(e.especificacao, d)
    coef = (
        0.4
        if (
            e.rosca_no_plano
            or e.especificacao in ("ASTM A307", "ISO 898-1 classe 4.6", SEM_QUALIFICACAO)
        )
        else 0.5
    )
    ab = math.pi * d**2 / 4
    fv = coef * ab * fub / 1.35 / 1000 * e.planos_de_corte
    linhas.append(
        Verificacao(
            "Parafuso: cisalhamento",
            f_par,
            fv,
            "kN",
            "NBR 14762 10.3.7",
            f"{n} parafusos {e.parafuso} ({e.especificacao}, f_ub = {_n(fub, 0)} MPa); "
            f"F_v,Rd = {_n(coef, 1)}·A_b·f_ub/1,35 × {e.planos_de_corte} plano(s)",
        )
    )

    # ------------------------------------------------------------------ rasgamento e esmagamento
    axial_por_parafuso = [fv]  # resistência de um parafuso na direção da força axial
    for nome, tt, fu in (("no perfil", t, fu_p), ("na chapa", e.t_chapa_mm, fu_c)):
        if tt <= LIMITE_CHAPA_FINA + 1e-9:
            e_ax = min(e.borda_mm, e.passo_mm) if e.n_por_linha > 1 else e.borda_mm
            axial_por_parafuso.append(tt * e_ax * fu / 1.45 / 1000)
            if f_ax > 0:
                linhas.append(
                    Verificacao(
                        f"Rasgamento {nome} (direção da força axial)",
                        f_ax,
                        tt * e_ax * fu / 1.45 / 1000,
                        "kN",
                        "NBR 14762 10.3.4",
                        f"F_Rd = t·e·f_u/1,45, e = {_n(e_ax, 0)} mm (borda ou passo, o menor)",
                    )
                )
            if f_tr > 0:
                e_tr = (
                    min(e.borda_lateral_mm, e.gabarito_mm) if e.n_linhas > 1 else e.borda_lateral_mm
                )
                linhas.append(
                    Verificacao(
                        f"Rasgamento {nome} (direção transversal)",
                        f_tr,
                        tt * e_tr * fu / 1.45 / 1000,
                        "kN",
                        "NBR 14762 10.3.4",
                        f"F_Rd = t·e·f_u/1,45, e = {_n(e_tr, 0)} mm",
                    )
                )
            alfa = min(0.183 * tt + 1.53, 3.0)
            axial_por_parafuso.append(alfa * d * tt * fu / 1.55 / 1000)
            linhas.append(
                Verificacao(
                    f"Esmagamento {nome}",
                    f_par,
                    alfa * d * tt * fu / 1.55 / 1000,
                    "kN",
                    "NBR 14762 10.3.5",
                    f"F_Rd = α_e·d·t·f_u/1,55, α_e = 0,183·t + 1,53 = {_n(alfa, 3)} (t = {_n(tt, 2)} mm)",
                )
            )
        else:
            lf = min(
                [e.borda_mm - (df + 0) / 2, e.borda_lateral_mm - df / 2]
                + ([e.passo_mm - df] if e.n_por_linha > 1 else [])
                + ([e.gabarito_mm - df] if e.n_linhas > 1 else [])
            )
            contato = bc.resist_contato(d, tt, fu, lf, "NBR8800_2008")
            axial_por_parafuso.append(contato)
            linhas.append(
                Verificacao(
                    f"Pressão de contato e rasgamento {nome} (t > 4,75 mm)",
                    f_par,
                    contato,
                    "kN",
                    "NBR 14762 10.3.1 → NBR 8800 6.3.3.3",
                    f"t = {_n(tt, 2)} mm > 4,75 mm: vale a NBR 8800 (ℓ_f = {_n(lf, 1)} mm)",
                )
            )
    if t > LIMITE_CHAPA_FINA + 1e-9:
        avisos.append(
            "O perfil tem mais de 4,75 mm: as ligações parafusadas dele seguem a NBR 8800 (NBR 14762 10.3.1)."
        )

    # ------------------------------------------------------------------ tração no perfil
    n_t_rd = None
    largura_g = e.gabarito_mm if e.n_linhas > 1 else 2 * e.borda_lateral_mm
    if nt > 0:
        ct, texto_ct = coef_ct_perfil(e, d, x, largura_g)
        an = area - e.n_linhas * df * t
        n_t_rd = min(area * fy_p / 1.10, ct * an * fu_p / 1.65) / 1000
        linhas.append(
            Verificacao(
                "Perfil: tração (escoamento da seção bruta e ruptura da seção líquida)",
                nt,
                n_t_rd,
                "kN",
                "NBR 14762 9.6.2",
                f"mín(A·f_y/1,10; C_t·A_n·f_u/1,65), A = {_n(area, 0)} mm², A_n = {_n(an, 0)} mm²; "
                + texto_ct,
            )
        )
        if e.n_por_linha >= 2:
            bruto = 1 - 1.2 * x / ((e.n_por_linha - 1) * e.passo_mm)
            linhas.append(
                _minimo(
                    "Perfil: C_t ≥ 0,4 (ligação permitida)",
                    0.4,
                    bruto,
                    "—",
                    "NBR 14762 9.6.2 c) 3)",
                    "aumente o comprimento da ligação (mais parafusos ou passo maior)",
                )
            )
        # colapso por rasgamento (10.4) com duas ou mais linhas
        if e.n_linhas >= 2:
            comprimento = e.borda_mm + (e.n_por_linha - 1) * e.passo_mm
            agv = 2 * comprimento * t
            anv = agv - 2 * (e.n_por_linha - 0.5) * df * t
            ant = (e.n_linhas - 1) * (e.gabarito_mm - df) * t
            frd = min(0.6 * agv * fy_p + ant * fu_p, 0.6 * anv * fu_p + ant * fu_p) / 1.65 / 1000
            linhas.append(
                Verificacao(
                    "Perfil: colapso por rasgamento",
                    nt,
                    frd,
                    "kN",
                    "NBR 14762 10.4",
                    f"A_gv = {_n(agv, 0)}, A_nv = {_n(anv, 0)}, A_nt = {_n(ant, 0)} mm²; γ = 1,65",
                )
            )
        else:
            linhas.append(
                _na(
                    "Perfil: colapso por rasgamento",
                    "NBR 14762 10.4",
                    "uma linha de parafusos: o bloco não se forma entre linhas (vale a seção líquida)",
                )
            )

    # ------------------------------------------------------------------ regra dos 50 % (10.1 a)
    if nt != 0 and e.barra_axial:
        referencia = e.n_rd_barra_kN if e.n_rd_barra_kN else n_t_rd
        if referencia:
            capacidade = n * min(axial_por_parafuso)
            linhas.append(
                _minimo(
                    "Ligação ≥ 50 % da força axial resistente da barra",
                    0.5 * referencia,
                    capacidade,
                    "kN",
                    "NBR 14762 10.1 a)",
                    f"resistência do grupo n·F_Rd = {_n(capacidade)} kN; barra "
                    f"{_n(referencia)} kN ({'informada' if e.n_rd_barra_kN else 'tração calculada aqui'})",
                )
            )
        else:
            linhas.append(
                Verificacao(
                    "Ligação ≥ 50 % da força axial resistente da barra",
                    None,
                    None,
                    "kN",
                    "NBR 14762 10.1 a)",
                    "barra comprimida: informe a força axial resistente da barra para conferir",
                    status="ALERTA",
                    tipo="limite",
                )
            )

    # ------------------------------------------------------------------ espaçamentos (10.3.3)
    if e.n_por_linha > 1:
        linhas.append(
            _minimo(
                "Distância livre entre furos (passo)",
                2 * d,
                e.passo_mm - df,
                "mm",
                "NBR 14762 10.3.3.1",
                "livre entre bordas de furos ≥ 2·d",
            )
        )
    if e.n_linhas > 1:
        linhas.append(
            _minimo(
                "Distância livre entre furos (gabarito)",
                2 * d,
                e.gabarito_mm - df,
                "mm",
                "NBR 14762 10.3.3.1",
                "livre entre bordas de furos ≥ 2·d",
            )
        )
    for nome, borda in (("na direção da força", e.borda_mm), ("lateral", e.borda_lateral_mm)):
        linhas.append(
            _minimo(
                f"Distância livre do furo à borda ({nome})",
                d,
                borda - df / 2,
                "mm",
                "NBR 14762 10.3.3.1",
                "livre da borda do furo à extremidade ≥ d",
            )
        )
    titulo = f"Ligação parafusada em perfil formado a frio — {e.perfil if e.perfil != PERFIL_A_MAO else 'perfil informado'}"
    return ResultadoLigacao(
        PERFIL_FRIO,
        titulo,
        e,
        tuple(linhas),
        {"forca_no_parafuso_kN": f_par, "t_perfil_mm": t, "area_mm2": area, "x_mm": x},
        tuple(avisos),
    )


# =============================================================================================
# 3. Grupo de soldas de filete
# =============================================================================================
SOLDA = "solda"
ARRANJO_UM = "um_filete"
ARRANJO_PARALELOS = "dois_paralelos"
ARRANJO_CONTORNO = "contorno"
ARRANJOS = {
    ARRANJO_UM: "Um filete (vertical)",
    ARRANJO_PARALELOS: "Dois filetes paralelos (verticais)",
    ARRANJO_CONTORNO: "Contorno retangular",
}


@dataclass(frozen=True)
class EntradaSolda:
    arranjo: str = ARRANJO_PARALELOS
    comprimento_mm: float = 150.0  # vertical (na direção de V)
    largura_mm: float = 100.0  # distância entre filetes paralelos / largura do contorno
    perna_mm: float = 6.0
    eletrodo: str = "E70"
    t1_mm: float = 8.0  # chapa soldada (borda da solda)
    t2_mm: float = 8.0  # peça que recebe
    aco: str = "ASTM A36"
    v_sd_kN: float = 40.0  # vertical, ao longo dos filetes
    n_sd_kN: float = 0.0  # horizontal, no plano
    m_sd_kNm: float = 0.0  # no plano (torção do grupo)


def _segmentos(e: EntradaSolda) -> list[tuple[float, float, float, float]]:
    h, b = e.comprimento_mm, e.largura_mm
    if e.arranjo == ARRANJO_UM:
        return [(0.0, 0.0, 0.0, h)]
    if e.arranjo == ARRANJO_PARALELOS:
        return [(0.0, 0.0, 0.0, h), (b, 0.0, b, h)]
    return [(0.0, 0.0, 0.0, h), (b, 0.0, b, h), (0.0, 0.0, b, 0.0), (0.0, h, b, h)]


def forca_por_mm_na_solda(e: EntradaSolda) -> tuple[float, float, float]:
    """Maior força por mm de filete (kN/mm) pelo método elástico: (resultante, longitudinal, total L)."""
    seg = _segmentos(e)
    comprimentos = [math.hypot(x2 - x1, y2 - y1) for x1, y1, x2, y2 in seg]
    total = sum(comprimentos)
    xc = (
        sum((x1 + x2) / 2 * c for (x1, _y1, x2, _y2), c in zip(seg, comprimentos, strict=True))
        / total
    )
    yc = (
        sum((y1 + y2) / 2 * c for (_x1, y1, _x2, y2), c in zip(seg, comprimentos, strict=True))
        / total
    )
    j = 0.0
    for (x1, y1, x2, y2), c in zip(seg, comprimentos, strict=True):
        mx, my = (x1 + x2) / 2 - xc, (y1 + y2) / 2 - yc
        j += c * (mx**2 + my**2) + c**3 / 12  # J da linha (próprio + translação)
    m = e.m_sd_kNm * 1000.0
    pior = (0.0, 0.0)
    for x1, y1, x2, y2 in seg:
        for k in range(11):
            px = x1 + (x2 - x1) * k / 10 - xc
            py = y1 + (y2 - y1) * k / 10 - yc
            fx = e.n_sd_kN / total - (m * py / j if j else 0.0)
            fy = e.v_sd_kN / total + (m * px / j if j else 0.0)
            r = math.hypot(fx, fy)
            if r > pior[0]:
                pior = (r, fy)
    return pior[0], pior[1], total


def calcular_solda(e: EntradaSolda) -> ResultadoLigacao:
    if e.arranjo not in ARRANJOS:
        raise LigacaoInvalida(f"Arranjo desconhecido: {e.arranjo!r}.")
    if e.eletrodo not in ELETRODOS:
        raise LigacaoInvalida(f"Eletrodo desconhecido: {e.eletrodo!r}.")
    if e.aco not in ACOS:
        raise LigacaoInvalida(f"Aço desconhecido: {e.aco!r}.")
    if min(e.comprimento_mm, e.perna_mm, e.t1_mm, e.t2_mm) <= 0 or (
        e.arranjo != ARRANJO_UM and e.largura_mm <= 0
    ):
        raise LigacaoInvalida(
            "Comprimento, largura, perna e espessuras precisam ser maiores que zero."
        )
    fy, fu = ACOS[e.aco]
    fw = ELETRODOS[e.eletrodo]
    t_menor = min(e.t1_mm, e.t2_mm)
    f, _f_long, total = forca_por_mm_na_solda(e)
    linhas: list[Verificacao] = []
    tef = 0.7 * e.perna_mm
    if t_menor <= LIMITE_CHAPA_FINA + 1e-9:
        # NBR 14762 10.2.3 — metal-base fino: o menor entre as direções (a favor da segurança)
        razao = e.comprimento_mm / t_menor
        if razao < 25:
            paralelo = (1 - 0.01 * razao) * t_menor * fu / 1.65
            texto_par = f"[1 − 0,01·L/t]·t·f_u/1,65 (L/t = {_n(razao, 1)})"
        else:
            paralelo = 0.75 * t_menor * fu / 2.0
            texto_par = f"0,75·t·f_u/2,00 (L/t = {_n(razao, 1)})"
        normal = t_menor * fu / 1.55
        linhas.append(
            Verificacao(
                "Metal-base fino: ruptura junto à solda",
                f * 10,
                min(paralelo, normal) / 1000 * 10,
                "kN/cm",
                "NBR 14762 10.2.3 a) e b)",
                f"t = {_n(t_menor, 2)} mm ≤ 4,75; paralela {texto_par}; normal t·f_u/1,55; vale a menor",
            )
        )
        if t_menor > 2.5:
            linhas.append(
                Verificacao(
                    "Solda: ruptura do metal da solda",
                    f * 10,
                    0.75 * tef * fw / 1.65 / 1000 * 10,
                    "kN/cm",
                    "NBR 14762 10.2.3 c)",
                    f"0,75·t_ef·f_w/1,65, t_ef = 0,7·perna = {_n(tef, 2)} mm",
                )
            )
    else:
        linhas.append(
            Verificacao(
                "Solda: metal da solda",
                f * 10,
                resistencia_filete_por_mm(e.perna_mm, e.eletrodo) * 10,
                "kN/cm",
                "NBR 8800 6.2.5.1, Tabela 8",
                f"0,60·f_w·(0,707·perna)/γ_w2, {e.eletrodo} (f_w = {_n(fw, 0)} MPa); "
                "aumento por direção (6.2.5.2) desprezado, a favor da segurança",
            )
        )
        linhas.append(
            Verificacao(
                "Metal-base junto à solda (cisalhamento)",
                f * 10,
                0.60 * fy * t_menor / GAMMA_A1 / 1000 * 10,
                "kN/cm",
                "NBR 8800 6.5.5 a)",
                f"0,60·f_y·t/γ_a1 por cm, t = {_n(t_menor, 1)} mm (parte menos espessa)",
            )
        )
    linhas.extend(_limites_do_filete(e.perna_mm, t_menor, e.t1_mm, e.comprimento_mm))
    titulo = f"Solda de filete — {ARRANJOS[e.arranjo].lower()}, perna {_n(e.perna_mm, 0)} mm"
    return ResultadoLigacao(
        SOLDA, titulo, e, tuple(linhas), {"forca_kN_cm": f * 10, "comprimento_total_mm": total}
    )


# =============================================================================================
# Figuras
# =============================================================================================
_ESC = 2
_LINHA = "#1e293b"
_CHAPA = "#cbd5e1"
_ALMA = "#f1f5f9"
_SOLDA = "#b91c1c"
_FURO = "#ffffff"
_TEXTO = "#0f172a"
_COTA = "#475569"
_FORCA = "#b45309"


def _png(imagem: Image.Image, largura: int, altura: int) -> bytes:
    final = imagem.resize((largura, altura), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    final.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _cota_vertical(d: ImageDraw.ImageDraw, x: float, y1: float, y2: float, texto: str) -> None:
    fonte = _fonte(11 * _ESC)
    d.line([(x, y1), (x, y2)], fill=_COTA, width=_ESC)
    for y in (y1, y2):
        d.line([(x - 5 * _ESC, y), (x + 5 * _ESC, y)], fill=_COTA, width=_ESC)
    d.text((x - 6 * _ESC, (y1 + y2) / 2), texto, fill=_COTA, font=fonte, anchor="rm")


def _cota_horizontal(d: ImageDraw.ImageDraw, y: float, x1: float, x2: float, texto: str) -> None:
    fonte = _fonte(11 * _ESC)
    d.line([(x1, y), (x2, y)], fill=_COTA, width=_ESC)
    for x in (x1, x2):
        d.line([(x, y - 5 * _ESC), (x, y + 5 * _ESC)], fill=_COTA, width=_ESC)
    d.text(((x1 + x2) / 2, y + 4 * _ESC), texto, fill=_COTA, font=fonte, anchor="mt")


def figura_chapa_simples(e: EntradaChapaSimples) -> ImagemDiagrama:
    """Vista lateral da ligação: ponta da viga apoiada, recorte, chapa, furos e solda."""
    perfil = sc.obter_perfil(e.perfil)
    d, tf = perfil.altura_mm, perfil.espessura_mesa_mm
    largura_px, altura_px = 900, 560
    esc = min(
        (largura_px - 340) / max(e.largura_chapa_mm + e.recorte_comprimento_mm + 160, 1),
        (altura_px - 140) / d,
    )
    esc *= _ESC
    imagem = Image.new("RGB", (largura_px * _ESC, altura_px * _ESC), "#ffffff")
    dr = ImageDraw.Draw(imagem)
    fonte = _fonte(12 * _ESC)
    x_apoio = 150 * _ESC
    y_topo = 80 * _ESC

    def p(x: float, y: float) -> tuple[float, float]:  # x da linha de solda, y do topo da viga
        return (x_apoio + x * esc, y_topo + y * esc)

    # apoio (alma da viga principal ou pilar), hachurado
    dr.rectangle(
        [x_apoio - 18 * _ESC, y_topo - 30 * _ESC, x_apoio, y_topo + d * esc + 30 * _ESC],
        fill="#e2e8f0",
        outline=_LINHA,
        width=2 * _ESC,
    )
    for k in range(0, int(d * esc / _ESC) + 60, 12):
        y = y_topo - 30 * _ESC + k * _ESC
        dr.line([(x_apoio - 18 * _ESC, y + 10 * _ESC), (x_apoio, y)], fill="#94a3b8", width=_ESC)
    # viga apoiada: começa a uma folga (setback) de 12 mm do apoio
    folga = 12.0
    x0 = folga
    x_fim = e.largura_chapa_mm + e.recorte_comprimento_mm + 160
    rec_h = e.recorte_altura_mm if e.recorte else 0.0
    rec_c = e.recorte_comprimento_mm if e.recorte else 0.0
    contorno = [
        p(x0, rec_h),
        p(x0 + rec_c, rec_h),
        p(x0 + rec_c, 0),
        p(x_fim, 0),
        p(x_fim, d),
        p(x0, d),
    ]
    dr.polygon(contorno, fill=_ALMA, outline=_LINHA, width=2 * _ESC)
    dr.line([p(x0 + rec_c, tf), p(x_fim, tf)], fill=_LINHA, width=_ESC)
    dr.line([p(x0, d - tf), p(x_fim, d - tf)], fill=_LINHA, width=_ESC)
    # chapa e furos
    y_furo0 = rec_h + e.topo_alma_mm if e.recorte else tf + e.topo_alma_mm
    y_chapa = y_furo0 - e.borda_vertical_mm
    hp = e.altura_chapa_mm
    dr.rectangle(
        [p(0, y_chapa), p(e.largura_chapa_mm, y_chapa + hp)],
        fill=_CHAPA,
        outline=_LINHA,
        width=2 * _ESC,
    )
    db = float(bc.dados_parafuso(e.parafuso)["d_b"])
    raio = max(db / 2 * esc, 4 * _ESC)
    x_furo = e.distancia_solda_furo_mm
    for k in range(e.n_parafusos):
        cx, cy = p(x_furo, y_furo0 + k * e.passo_mm)
        dr.ellipse(
            [cx - raio, cy - raio, cx + raio, cy + raio], fill=_FURO, outline=_LINHA, width=2 * _ESC
        )
        dr.line([(cx - raio * 0.7, cy), (cx + raio * 0.7, cy)], fill=_LINHA, width=_ESC)
        dr.line([(cx, cy - raio * 0.7), (cx, cy + raio * 0.7)], fill=_LINHA, width=_ESC)
    # solda (filete) na face do apoio
    a0, a1 = p(0, y_chapa), p(0, y_chapa + hp)
    passo = 6 * _ESC
    y_solda = float(a0[1])
    while y_solda < a1[1]:
        dr.polygon(
            [(a0[0], y_solda), (a0[0] + 7 * _ESC, y_solda), (a0[0], y_solda + passo)], fill=_SOLDA
        )
        y_solda += passo
    # cotas
    x_cota = p(e.largura_chapa_mm, 0)[0] + 30 * _ESC
    _cota_vertical(dr, p(-30, 0)[0], p(0, y_chapa)[1], p(0, y_chapa + hp)[1], f"{_n(hp, 0)}")
    yy = y_chapa
    for trecho in [e.borda_vertical_mm, *[e.passo_mm] * (e.n_parafusos - 1), e.borda_vertical_mm]:
        fim = yy + trecho
        dr.line([(x_cota, p(0, yy)[1]), (x_cota, p(0, fim)[1])], fill=_COTA, width=_ESC)
        dr.line(
            [(x_cota - 4 * _ESC, p(0, yy)[1]), (x_cota + 4 * _ESC, p(0, yy)[1])],
            fill=_COTA,
            width=_ESC,
        )
        dr.text(
            (x_cota + 6 * _ESC, p(0, (yy + fim) / 2)[1]),
            _n(trecho, 0),
            fill=_COTA,
            font=_fonte(11 * _ESC),
            anchor="lm",
        )
        yy = fim
    dr.line(
        [(x_cota - 4 * _ESC, p(0, yy)[1]), (x_cota + 4 * _ESC, p(0, yy)[1])], fill=_COTA, width=_ESC
    )
    y_cota_h = p(0, y_chapa + hp)[1] + 24 * _ESC
    _cota_horizontal(dr, y_cota_h, p(0, 0)[0], p(x_furo, 0)[0], f"a = {_n(x_furo, 0)}")
    _cota_horizontal(
        dr,
        y_cota_h,
        p(x_furo, 0)[0],
        p(e.largura_chapa_mm, 0)[0],
        _n(e.borda_horizontal_chapa_mm, 0),
    )
    if e.recorte:
        _cota_horizontal(
            dr,
            p(0, 0)[1] - 22 * _ESC,
            p(x0, 0)[0],
            p(x0 + rec_c, 0)[0],
            f"recorte {_n(rec_c, 0)} × {_n(rec_h, 0)}",
        )
    # força
    fx, fy = p(x_furo, y_chapa - 10)
    dr.line([(fx, fy - 60 * _ESC), (fx, fy - 8 * _ESC)], fill=_FORCA, width=3 * _ESC)
    dr.polygon(
        [(fx, fy - 4 * _ESC), (fx - 7 * _ESC, fy - 18 * _ESC), (fx + 7 * _ESC, fy - 18 * _ESC)],
        fill=_FORCA,
    )
    dr.text(
        (fx - 10 * _ESC, fy - 30 * _ESC),
        f"V_Sd = {_n(e.v_sd_kN, 1)} kN",
        fill=_FORCA,
        font=fonte,
        anchor="rm",
    )
    titulo = "Ligação flexível por chapa simples (vista lateral)"
    dr.text((18 * _ESC, 14 * _ESC), titulo, fill=_TEXTO, font=_fonte(16 * _ESC))
    dr.text(
        (18 * _ESC, 38 * _ESC),
        f"{e.perfil}; chapa {_n(e.t_chapa_mm, 1)} × {_n(e.largura_chapa_mm, 0)} × {_n(hp, 0)} mm; "
        f"{e.n_parafusos} × {e.parafuso} {e.grau}; filete {_n(e.perna_solda_mm, 0)} mm dos dois lados. Cotas em mm.",
        fill=_COTA,
        font=_fonte(11 * _ESC),
    )
    legenda = (
        f"Chapa simples {_n(e.t_chapa_mm, 1)} mm ({e.aco_chapa}) soldada no apoio com filetes de "
        f"{_n(e.perna_solda_mm, 0)} mm ({e.eletrodo}) e parafusada na alma da {e.perfil} com "
        f"{e.n_parafusos} parafusos {e.parafuso} {e.grau}"
        + (f"; mesa superior recortada {_n(rec_c, 0)} × {_n(rec_h, 0)} mm" if e.recorte else "")
        + "."
    )
    return ImagemDiagrama(
        titulo, legenda, _png(imagem, largura_px, altura_px), largura_px, altura_px
    )


def figura_perfil_frio(e: EntradaPerfilFrio) -> ImagemDiagrama:
    """A alma do perfil com a grade de parafusos, as bordas e as forças."""
    largura_px, altura_px = 900, 420
    comprimento = e.borda_mm + (e.n_por_linha - 1) * e.passo_mm + 160
    altura = 2 * e.borda_lateral_mm + (e.n_linhas - 1) * e.gabarito_mm
    esc = min((largura_px - 260) / comprimento, (altura_px - 170) / altura) * _ESC
    imagem = Image.new("RGB", (largura_px * _ESC, altura_px * _ESC), "#ffffff")
    dr = ImageDraw.Draw(imagem)
    x0, y0 = 120 * _ESC, 110 * _ESC

    def p(x: float, y: float) -> tuple[float, float]:
        return (x0 + x * esc, y0 + y * esc)

    dr.rectangle([p(0, 0), p(comprimento, altura)], fill=_ALMA, outline=_LINHA, width=2 * _ESC)
    dr.rectangle(
        [p(-40, -10), p(e.borda_mm + (e.n_por_linha - 1) * e.passo_mm + 30, altura + 10)],
        outline=_LINHA,
        width=2 * _ESC,
    )
    d = float(bc.dados_parafuso(e.parafuso)["d_b"])
    raio = max(d / 2 * esc, 4 * _ESC)
    for i in range(e.n_por_linha):
        for j in range(e.n_linhas):
            cx, cy = p(e.borda_mm + i * e.passo_mm, e.borda_lateral_mm + j * e.gabarito_mm)
            dr.ellipse(
                [cx - raio, cy - raio, cx + raio, cy + raio],
                fill=_FURO,
                outline=_LINHA,
                width=2 * _ESC,
            )
    y_c = p(0, altura)[1] + 26 * _ESC
    _cota_horizontal(dr, y_c, p(0, 0)[0], p(e.borda_mm, 0)[0], f"e = {_n(e.borda_mm, 0)}")
    if e.n_por_linha > 1:
        _cota_horizontal(
            dr,
            y_c,
            p(e.borda_mm, 0)[0],
            p(e.borda_mm + e.passo_mm, 0)[0],
            f"s = {_n(e.passo_mm, 0)}",
        )
    _cota_vertical(
        dr,
        p(0, 0)[0] - 50 * _ESC,
        p(0, 0)[1],
        p(0, e.borda_lateral_mm)[1],
        f"e₁ = {_n(e.borda_lateral_mm, 0)}",
    )
    if e.n_linhas > 1:
        _cota_vertical(
            dr,
            p(0, 0)[0] - 50 * _ESC,
            p(0, e.borda_lateral_mm)[1],
            p(0, e.borda_lateral_mm + e.gabarito_mm)[1],
            f"g = {_n(e.gabarito_mm, 0)}",
        )
    fonte = _fonte(12 * _ESC)
    if e.n_sd_kN:
        ya = p(0, altura / 2)[1]
        xa = p(comprimento, 0)[0]
        sentido = 1 if e.n_sd_kN > 0 else -1
        dr.line([(xa + 10 * _ESC, ya), (xa + 80 * _ESC, ya)], fill=_FORCA, width=3 * _ESC)
        ponta = xa + (80 if sentido > 0 else 10) * _ESC
        dr.polygon(
            [
                (ponta + sentido * 6 * _ESC, ya),
                (ponta - sentido * 8 * _ESC, ya - 7 * _ESC),
                (ponta - sentido * 8 * _ESC, ya + 7 * _ESC),
            ],
            fill=_FORCA,
        )
        dr.text(
            (xa + 10 * _ESC, ya - 18 * _ESC),
            f"N_Sd = {_n(e.n_sd_kN, 1)} kN",
            fill=_FORCA,
            font=fonte,
            anchor="lm",
        )
    titulo = "Ligação parafusada em perfil formado a frio (alma)"
    dr.text((18 * _ESC, 14 * _ESC), titulo, fill=_TEXTO, font=_fonte(16 * _ESC))
    dr.text(
        (18 * _ESC, 38 * _ESC),
        f"{e.n_linhas * e.n_por_linha} × {e.parafuso} {e.especificacao}; chapa {_n(e.t_chapa_mm, 2)} mm. Cotas em mm.",
        fill=_COTA,
        font=_fonte(11 * _ESC),
    )
    legenda = (
        f"Grade de {e.n_linhas} linha(s) × {e.n_por_linha} parafuso(s) {e.parafuso} na alma do "
        f"perfil, borda e = {_n(e.borda_mm, 0)} mm, lateral e₁ = {_n(e.borda_lateral_mm, 0)} mm."
    )
    return ImagemDiagrama(
        titulo, legenda, _png(imagem, largura_px, altura_px), largura_px, altura_px
    )


def figura_solda(e: EntradaSolda) -> ImagemDiagrama:
    largura_px, altura_px = 700, 460
    h = e.comprimento_mm
    b = e.largura_mm if e.arranjo != ARRANJO_UM else 60.0
    esc = min((largura_px - 300) / max(b, 1), (altura_px - 170) / h) * _ESC
    imagem = Image.new("RGB", (largura_px * _ESC, altura_px * _ESC), "#ffffff")
    dr = ImageDraw.Draw(imagem)
    x0, y0 = 180 * _ESC, 100 * _ESC

    def p(x: float, y: float) -> tuple[float, float]:
        return (x0 + x * esc, y0 + (h - y) * esc)

    dr.rectangle([p(-10, h + 10), p(b + 10, -10)], fill=_CHAPA, outline=_LINHA, width=2 * _ESC)
    for x1, y1, x2, y2 in _segmentos(e):
        dr.line([p(x1, y1), p(x2, y2)], fill=_SOLDA, width=6 * _ESC)
    _cota_vertical(dr, p(-10, 0)[0] - 30 * _ESC, p(0, h)[1], p(0, 0)[1], f"L = {_n(h, 0)}")
    if e.arranjo != ARRANJO_UM:
        _cota_horizontal(dr, p(0, 0)[1] + 26 * _ESC, p(0, 0)[0], p(b, 0)[0], f"b = {_n(b, 0)}")
    fonte = _fonte(12 * _ESC)
    cx, cy = p(b / 2, h / 2)
    if e.v_sd_kN:
        dr.line([(cx, cy - 70 * _ESC), (cx, cy - 6 * _ESC)], fill=_FORCA, width=3 * _ESC)
        dr.polygon(
            [(cx, cy), (cx - 7 * _ESC, cy - 14 * _ESC), (cx + 7 * _ESC, cy - 14 * _ESC)],
            fill=_FORCA,
        )
        dr.text(
            (cx + 10 * _ESC, cy - 56 * _ESC),
            f"V = {_n(e.v_sd_kN, 1)} kN",
            fill=_FORCA,
            font=fonte,
            anchor="lm",
        )
    if e.n_sd_kN:
        dr.text(
            (cx + 10 * _ESC, cy + 16 * _ESC),
            f"N = {_n(e.n_sd_kN, 1)} kN",
            fill=_FORCA,
            font=fonte,
            anchor="lm",
        )
    if e.m_sd_kNm:
        dr.text(
            (cx + 10 * _ESC, cy + 36 * _ESC),
            f"M = {_n(e.m_sd_kNm, 2)} kN·m",
            fill=_FORCA,
            font=fonte,
            anchor="lm",
        )
    titulo = "Grupo de soldas de filete"
    dr.text((18 * _ESC, 14 * _ESC), titulo, fill=_TEXTO, font=_fonte(16 * _ESC))
    dr.text(
        (18 * _ESC, 38 * _ESC),
        f"{ARRANJOS[e.arranjo]}, perna {_n(e.perna_mm, 0)} mm ({e.eletrodo}). Cotas em mm.",
        fill=_COTA,
        font=_fonte(11 * _ESC),
    )
    legenda = (
        f"{ARRANJOS[e.arranjo]}: L = {_n(h, 0)} mm"
        + (f", b = {_n(b, 0)} mm" if e.arranjo != ARRANJO_UM else "")
        + f"; perna {_n(e.perna_mm, 0)} mm."
    )
    return ImagemDiagrama(
        titulo, legenda, _png(imagem, largura_px, altura_px), largura_px, altura_px
    )


_ENTRADAS: dict[str, type] = {
    CHAPA_SIMPLES: EntradaChapaSimples,
    PERFIL_FRIO: EntradaPerfilFrio,
    SOLDA: EntradaSolda,
}


def figura(r: ResultadoLigacao) -> ImagemDiagrama:
    if r.tipo == CHAPA_SIMPLES:
        return figura_chapa_simples(r.entrada)
    if r.tipo == PERFIL_FRIO:
        return figura_perfil_frio(r.entrada)
    return figura_solda(r.entrada)


def figura_gravada(dados: Mapping[str, Any]) -> ImagemDiagrama:
    """A figura a partir do que o registro gravou (``{"tipo", "entrada"}``)."""
    classe = _ENTRADAS[str(dados["tipo"])]
    nomes = {f.name for f in fields(classe)}
    entrada = classe(**{k: v for k, v in dict(dados["entrada"]).items() if k in nomes})
    return figura(ResultadoLigacao(str(dados["tipo"]), "", entrada, ()))


def calcular(entrada: EntradaChapaSimples | EntradaPerfilFrio | EntradaSolda) -> ResultadoLigacao:
    if isinstance(entrada, EntradaChapaSimples):
        return calcular_chapa_simples(entrada)
    if isinstance(entrada, EntradaPerfilFrio):
        return calcular_perfil_frio(entrada)
    return calcular_solda(entrada)


# =============================================================================================
# Registro
# =============================================================================================
_METODO = {
    CHAPA_SIMPLES: (
        "Ligação flexível (rotulada) por chapa simples: a cortante de cálculo e, se houver, a força "
        "normal passam da alma da viga apoiada aos parafusos e à chapa, e da chapa ao apoio pelos "
        "filetes. Parafusos e solda com a excentricidade a (da linha de solda à linha dos "
        "parafusos) pelo método elástico; chapa e alma pela NBR 8800 6.5."
    ),
    PERFIL_FRIO: (
        "Ligação parafusada em perfil formado a frio pela NBR 14762:2010: forças distribuídas "
        "igualmente entre os parafusos (grupo concêntrico); rasgamento, esmagamento, corte do "
        "parafuso, tração na seção líquida com C_t e colapso por rasgamento."
    ),
    SOLDA: (
        "Grupo de filetes no plano pelo método elástico (forças por unidade de comprimento): "
        "metal da solda e metal-base pela NBR 8800 6.2 e 6.5, ou pela NBR 14762 10.2.3 quando a "
        "parte mais fina tem até 4,75 mm; limites de perna e de comprimento da NBR 8800 6.2.6.2."
    ),
}
_PREMISSAS = {
    CHAPA_SIMPLES: [
        "A favor da segurança, o momento V·a entra nos parafusos e também na solda.",
        "Pressão de contato com a menor distância livre ℓ_f de cada parte (chapa e alma), em "
        "qualquer direção.",
        "Flexão na seção do recorte só com a alma (sem a mesa inferior).",
        "O apoio (alma da viga principal ou pilar) é verificado só junto à solda; a alma ou mesa "
        "do apoio como um todo fica para o cálculo do apoio.",
    ],
    PERFIL_FRIO: [
        "Forças iguais em todos os parafusos (sem momento no grupo).",
        "C_t do perfil ligado só pela alma (NBR 14762 9.6.2 c) 3)).",
        "Chapa com mais de 4,75 mm verificada pela NBR 8800 (NBR 14762 10.3.1).",
    ],
    SOLDA: [
        "Método elástico (conservador frente ao do centro instantâneo de rotação, 6.2.5.2 b).",
        "Sem o aumento de resistência pela direção da força (6.2.5.2 a), a favor da segurança.",
    ],
}
_REFERENCIAS = [
    "ABNT NBR 8800:2008 — 6.2 (soldas), 6.3 (parafusos), 6.5 (elementos de ligação), Anexo A.",
    "ABNT NBR 14762:2010 — 9.6 (tração), 10.2 (soldas), 10.3 (parafusos), 10.4 (colapso por rasgamento).",
    "AISC Steel Construction Manual — Parte 9 (vigas recortadas) e Parte 10 (chapa simples).",
]


def _entradas_do_registro(e: Any) -> dict[str, Any]:
    dados = asdict(e)
    return {k: v for k, v in dados.items() if v is not None and v != ""}


def destaque(r: ResultadoLigacao) -> str:
    g = r.governante
    texto = f"{r.titulo}: {r.status}; maior aproveitamento {_n(100 * r.aproveitamento_maximo, 1)} %"
    if g is not None:
        texto += f" ({g.nome.lower()})"
    return texto + "."


def registro_ligacao(
    r: ResultadoLigacao, *, contexto: Mapping[str, Any] | None = None, responsavel: str = ""
) -> dict[str, Any]:
    geral = r.status
    texto = destaque(r)
    entradas = _entradas_do_registro(r.entrada)
    entradas.update(dict(contexto or {}))
    alertas = [f"{v.nome}: {v.formula}" for v in r.verificacoes if v.status in ("NÃO OK", "ALERTA")]
    alertas.extend(r.avisos)
    alertas.append(
        "Não faz: ligações rígidas (com momento), chapa de extremidade, enrijecedores, efeito de "
        "alavanca e a verificação do apoio como um todo — casos específicos ficam com o projetista."
    )
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=r.titulo,
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=texto,
        entradas=entradas,
        resultados={
            "status_geral": geral,
            "verificações": linhas_para_registro(list(r.verificacoes)),
            "utilizacao_maxima": numero_json(r.aproveitamento_maximo, 4),
            "destaque_memorial": texto,
            "figura_ligacao": {"tipo": r.tipo, "entrada": asdict(r.entrada)},
        },
        metodo=_METODO[r.tipo],
        premissas=list(_PREMISSAS[r.tipo]),
        alertas=alertas,
        referencias=list(_REFERENCIAS),
        conclusao=texto,
        responsavel=responsavel,
    )


def linhas_resumo(verificacoes: Sequence[Verificacao]) -> list[str]:
    """As linhas que não passaram, em texto curto (para avisos da página)."""
    return [f"{v.nome}: {v.formula}" for v in verificacoes if v.status == "NÃO OK"]
