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
3. **Grupo de soldas de filete**, NBR 8800 6.2 (tabela das soldas, perna mínima e 6.2.6.2) — ou
   NBR 14762 10.2.3 quando a parte mais fina tem até 4,75 mm —, com força cortante, normal e
   momento no plano: aumento pela direção da força (6.2.5.2 a e c) e centro instantâneo de rotação
   (6.2.5.2 b), ou o método elástico, a favor da segurança. As regras das soldas estão em
   :mod:`core.soldas`; a barra soldada na chapa de nó e a chapa soldada no apoio, em
   :mod:`core.ligacoes_soldadas`.

Os coeficientes conferidos nas normas (NBR 8800:2008 e 2025, NBR 14762:2010); a 2025 muda os
coeficientes do corte do parafuso (0,45/0,56), via :mod:`core.bolted_connection`, e o número das
tabelas das soldas. Casos especiais (ligações rígidas, chapa de extremidade com momento,
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
from core import soldas as sd
from core.beam_charts import ImagemDiagrama, _fonte
from core.desenho_girado import Tela as _Tela
from core.desenho_girado import angulo_do_giro, texto_do_giro
from core.desenho_girado import cota_alinhada as _cota_alinhada
from core.desenho_girado import eixos_da_peca as _eixos_da_peca
from core.desenho_girado import legenda as _legenda
from core.desenho_girado import mais as _mais
from core.desenho_girado import rotulo as _rotulo
from core.desenho_girado import seta as _seta_px
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
GAMMA_W2 = 1.35  # NBR 8800 tabela das soldas (nota de γ_w2), combinações normais
FOLGA_FURO = 2.0  # NBR 8800 5.2.4.1 a): furo + 2 mm na área líquida (0 com furo de broca)
NORMAS = sd.NORMAS
NORMAS_ROTULOS = sd.NORMAS_ROTULOS
ELETRODOS = sd.ELETRODOS  # NBR 8800 Tabela A.4
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
    #: No modo "dimensionar", a entrada com os comprimentos adotados (a figura sai dela).
    adotada: Any = None

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
perna_minima = sd.perna_minima  # Tabela 11 (2025) / Tabela 10 (2008)
perna_maxima = sd.perna_maxima  # 6.2.6.2.2


def _limites_do_filete(
    perna: float,
    t_menor: float,
    t_borda: float | None,
    comprimento: float,
    rotulo: str = "",
    norma: str = sd.NBR_2025,
) -> list[Verificacao]:
    return sd.limites_do_filete(norma, perna, t_menor, t_borda, comprimento, rotulo)


def resistencia_filete_por_mm(perna_mm: float, eletrodo: str) -> float:
    """Metal da solda, por mm de filete (kN/mm): 0,60·f_w·(0,707·perna)/γ_w2, combinação normal."""
    return sd.resistencia_filete_por_mm(perna_mm, ELETRODOS[eletrodo], GAMMA_W2)


def _ref_metal_da_solda(norma: str) -> str:
    return sd.ref(norma, f"6.2.5.1, {sd.tabela(norma, 'resistencia')}", vista_na_2025=True)


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
    furo_com_broca: bool = False  # 5.2.4.1 a): área líquida sem os 2 mm
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


def _alma_da_viga(
    e: EntradaChapaSimples | EntradaCantoneiraDupla,
    d: float,
    tw: float,
    fy_v: float,
    fu_v: float,
    n: int,
    s: float,
    dhl: float,
    v: float,
) -> list[Verificacao]:
    """Alma da viga apoiada: cisalhamento e, com recorte, colapso por rasgamento e flexão."""
    linhas: list[Verificacao] = []
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

    return linhas


def _furo_de_broca(broca: bool, dh: float) -> list[Verificacao]:
    """A linha que diz que a área líquida vai sem os 2 mm (furos feitos com broca)."""
    if not broca:
        return []
    return [
        Verificacao(
            "Furo na área líquida",
            dh,
            None,
            "mm",
            "NBR 8800 5.2.4.1 a)",
            "furos feitos com broca: a largura do próprio furo, sem somar os 2 mm",
            status="INFO",
            tipo="informativo",
        )
    ]


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
    dhl = dh + (0.0 if e.furo_com_broca else FOLGA_FURO)
    n, s, tp = e.n_parafusos, e.passo_mm, e.t_chapa_mm
    hp, a = e.altura_chapa_mm, e.distancia_solda_furo_mm
    v, nt = e.v_sd_kN, e.n_sd_kN
    m_kNm = v * a / 1000.0
    linhas: list[Verificacao] = _furo_de_broca(e.furo_com_broca, dh)

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

    linhas.extend(_alma_da_viga(e, d, tw, fy_v, fu_v, n, s, dhl, v))

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
            _ref_metal_da_solda(e.norma),
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
    linhas.extend(
        _limites_do_filete(e.perna_solda_mm, min(tp, e.t_apoio_mm), tp, comprimento, norma=e.norma)
    )

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
# 1b. Dupla cantoneira (viga–viga e viga–pilar)
# =============================================================================================
CANTONEIRA_DUPLA = "cantoneira_dupla"


@dataclass(frozen=True)
class EntradaCantoneiraDupla:
    perfil: str = "W 250 x 17,9"  # viga apoiada
    aco_viga: str = "ASTM A572 Gr 50"
    apoio: str = APOIO_VIGA
    t_apoio_mm: float = 5.8
    aco_apoio: str = "ASTM A572 Gr 50"
    recorte: bool = True
    recorte_altura_mm: float = 30.0
    recorte_comprimento_mm: float = 100.0
    cantoneira: str = 'L 3" × 5/16"'
    aco_cantoneira: str = "ASTM A36"
    comprimento_mm: float = 210.0  # altura das cantoneiras
    parafuso: str = '3/4"'
    grau: str = "A325"
    rosca_no_plano: bool = True
    furo_com_broca: bool = False  # 5.2.4.1 a): área líquida sem os 2 mm
    n_parafusos: int = 3  # por linha vertical (na alma; no apoio, a mesma quantidade em cada aba)
    passo_mm: float = 70.0
    borda_vertical_mm: float = 35.0  # na cantoneira, do furo à ponta
    gabarito_alma_mm: float = 45.0  # da quina da cantoneira (face do apoio) aos furos da alma
    gabarito_apoio_mm: float = 45.0  # da quina aos furos no apoio
    borda_alma_mm: float = 35.0  # dos furos à ponta da viga
    topo_alma_mm: float = 40.0
    v_sd_kN: float = 40.0
    norma: str = "NBR8800_2024"
    anglo: bool = False


def calcular_cantoneira_dupla(e: EntradaCantoneiraDupla) -> ResultadoLigacao:
    """Duas cantoneiras parafusadas na alma da viga (corte duplo) e no apoio (corte simples)."""
    from core import cantoneiras as ct

    if (
        e.n_parafusos < 1
        or min(
            e.passo_mm if e.n_parafusos > 1 else 1.0,
            e.borda_vertical_mm,
            e.gabarito_alma_mm,
            e.gabarito_apoio_mm,
            e.borda_alma_mm,
            e.topo_alma_mm,
            e.t_apoio_mm,
        )
        <= 0
    ):
        raise LigacaoInvalida(
            "Parafusos, passo, bordas, gabaritos e espessuras precisam ser maiores que zero."
        )
    if e.v_sd_kN < 0:
        raise LigacaoInvalida("Informe a força cortante de cálculo como valor positivo.")
    if e.norma not in NORMAS or e.apoio not in APOIOS:
        raise LigacaoInvalida("Escolha a norma e o apoio da lista.")
    for aco in (e.aco_viga, e.aco_cantoneira, e.aco_apoio):
        if aco not in ACOS:
            raise LigacaoInvalida(f"Aço desconhecido: {aco!r}.")
    if e.parafuso not in bc.PARAFUSOS or e.grau not in bc.GRAUS:
        raise LigacaoInvalida("Escolha o parafuso e o grau da lista.")
    if e.cantoneira not in ct.CATALOGO_CANTONEIRAS:
        raise LigacaoInvalida(f"Cantoneira desconhecida: {e.cantoneira!r}.")
    try:
        perfil = sc.obter_perfil(e.perfil)
    except (KeyError, sc.ErroDeCatalogo) as erro:
        raise LigacaoInvalida(f"Perfil desconhecido: {e.perfil!r}.") from erro
    cant = ct.obter_cantoneira(e.cantoneira)
    ta, aba = cant.t_mm, cant.b_mm
    d, tw, tf = perfil.altura_mm, perfil.espessura_alma_mm, perfil.espessura_mesa_mm
    fy_v, fu_v = ACOS[e.aco_viga]
    fy_a, fu_a = ACOS[e.aco_cantoneira]
    _fy_s, fu_s = ACOS[e.aco_apoio]
    par = bc.dados_parafuso(e.parafuso)
    db, dh, emin = float(par["d_b"]), float(par["d_h"]), float(par["e_min"])
    dhl = dh + (0.0 if e.furo_com_broca else FOLGA_FURO)
    n, s, v, comp = e.n_parafusos, e.passo_mm, e.v_sd_kN, e.comprimento_mm
    if e.borda_vertical_mm * 2 + (n - 1) * s > comp + 1e-6:
        raise LigacaoInvalida(
            "Os furos não cabem na cantoneira: comprimento ≥ 2·borda + (n − 1)·passo."
        )
    linhas: list[Verificacao] = _furo_de_broca(e.furo_com_broca, dh)

    # ------------------------------------------------------------------ parafusos na alma (corte duplo)
    coords = [(0.0, k * s) for k in range(n)]
    m_alma = v * e.gabarito_alma_mm / 1000
    f_alma = _forca_no_parafuso(coords, v, 0.0, m_alma)
    fv2 = bc.resist_corte(db, e.grau, e.norma, e.rosca_no_plano, 2)
    lf_cant = [e.borda_vertical_mm - dh / 2, aba - e.gabarito_alma_mm - dh / 2]
    lf_alma = [e.borda_alma_mm - dh / 2]
    if n > 1:
        lf_cant.append(s - dh)
        lf_alma.append(s - dh)
    if e.recorte:
        lf_alma.append(e.topo_alma_mm - dh / 2)
    fc_cant = 2 * bc.resist_contato(db, ta, fu_a, min(lf_cant), e.norma)
    fc_alma = bc.resist_contato(db, tw, fu_v, min(lf_alma), e.norma)
    r_alma = min(fv2, fc_cant, fc_alma)
    linhas.append(
        Verificacao(
            "Parafusos na alma (corte duplo, M = V·g)",
            f_alma,
            r_alma,
            "kN",
            "NBR 8800 6.3.3.2 e 6.3.3.3",
            f"{n} × {e.parafuso} {e.grau}; M = V·g = {_n(m_alma, 3)} kN·m; F_v,Rd (2 planos) = "
            f"{_n(fv2)} kN; contato nas 2 cantoneiras {_n(fc_cant)} kN, na alma {_n(fc_alma)} kN",
        )
    )
    # ------------------------------------------------------------------ parafusos no apoio (corte simples)
    f_apoio = v / (2 * n)
    fv1 = bc.resist_corte(db, e.grau, e.norma, e.rosca_no_plano, 1)
    lf_apoio = [e.borda_vertical_mm - dh / 2] + ([s - dh] if n > 1 else [])
    fc_cant_apoio = bc.resist_contato(db, ta, fu_a, min(lf_apoio), e.norma)
    fc_apoio = bc.resist_contato(db, e.t_apoio_mm, fu_s, s - dh if n > 1 else None, e.norma)
    r_apoio = min(fv1, fc_cant_apoio, fc_apoio)
    linhas.append(
        Verificacao(
            "Parafusos no apoio (corte simples)",
            f_apoio,
            r_apoio,
            "kN",
            "NBR 8800 6.3.3.2 e 6.3.3.3",
            f"2 × {n} parafusos com V/(2n); F_v,Rd = {_n(fv1)} kN; contato na cantoneira "
            f"{_n(fc_cant_apoio)} kN, no apoio {_n(fc_apoio)} kN (t = {_n(e.t_apoio_mm, 1)} mm); "
            "a excentricidade da aba no apoio é desprezada (gabarito curto)",
        )
    )
    # ------------------------------------------------------------------ cantoneiras
    linhas.append(
        Verificacao(
            "Cantoneiras: escoamento por cisalhamento",
            v,
            0.60 * fy_a * 2 * comp * ta / GAMMA_A1 / 1000,
            "kN",
            "NBR 8800 6.5.5 a)",
            f"duas abas de {_n(comp, 0)} × {_n(ta, 2)} mm",
        )
    )
    linhas.append(
        Verificacao(
            "Cantoneiras: ruptura por cisalhamento",
            v,
            0.60 * fu_a * 2 * (comp - n * dhl) * ta / GAMMA_A2 / 1000,
            "kN",
            "NBR 8800 6.5.5 b)",
            f"A_nv = 2·({_n(comp, 0)} − {n}·{_n(dhl, 1)})·{_n(ta, 2)} mm",
        )
    )
    agv = (comp - e.borda_vertical_mm) * ta
    anv = agv - (n - 0.5) * dhl * ta
    ant = (aba - e.gabarito_alma_mm - 0.5 * dhl) * ta
    linhas.append(
        Verificacao(
            "Cantoneiras: colapso por rasgamento (aba na alma)",
            v,
            2 * bc.resist_colapso_rasgamento(agv, anv, ant, fy_a, fu_a, e.norma, 1.0),
            "kN",
            "NBR 8800 6.5.6",
            f"cada cantoneira: A_gv = {_n(agv, 0)}, A_nv = {_n(anv, 0)}, A_nt = {_n(ant, 0)} mm²",
        )
    )
    # ------------------------------------------------------------------ alma da viga e geometria
    linhas.extend(_alma_da_viga(e, d, tw, fy_v, fu_v, n, s, dhl, v))
    alma_livre = d - tf - (e.recorte_altura_mm if e.recorte else tf)
    ocupado = comp + max(e.topo_alma_mm - e.borda_vertical_mm, 0.0)
    linhas.append(
        _maximo(
            "Cantoneiras cabem na alma livre da viga",
            ocupado,
            alma_livre,
            "mm",
            "geometria",
            f"cantoneiras de {_n(comp, 0)} mm",
        )
    )
    for nome, gab in (("na alma", e.gabarito_alma_mm), ("no apoio", e.gabarito_apoio_mm)):
        linhas.append(
            _minimo(
                f"Furo à borda da aba ({nome})",
                emin,
                aba - gab,
                "mm",
                "NBR 8800 6.3.11",
                f"aba {_n(aba, 1)} mm − gabarito {_n(gab, 0)} mm",
            )
        )
        linhas.append(
            _minimo(
                f"Folga para apertar o parafuso ({nome})",
                ta + db,
                gab,
                "mm",
                "detalhe construtivo",
                "gabarito ≥ t + d_b, para a porca não encostar na outra aba",
            )
        )
    linhas.append(
        _minimo(
            "Distância do furo à ponta da viga",
            emin,
            e.borda_alma_mm,
            "mm",
            "NBR 8800 6.3.11",
            "e ≥ e_mín",
        )
    )
    linhas.extend(
        replace(v_, tipo="limite")
        for v_ in bc.disposicoes_construtivas(
            db, dh, emin, ta, e.borda_vertical_mm, s if n > 1 else 0.0
        )
    )
    if e.anglo:
        linhas.extend(bc.criterio_anglo(n, e.grau, db))
    titulo = (
        f"Ligação flexível por dupla cantoneira — {e.perfil} em "
        f"{APOIOS[e.apoio].split(' (')[0].lower()}"
    )
    return ResultadoLigacao(
        CANTONEIRA_DUPLA,
        titulo,
        e,
        tuple(linhas),
        {"forca_parafuso_alma_kN": f_alma, "forca_parafuso_apoio_kN": f_apoio},
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
ARRANJO_HORIZONTAIS = "dois_horizontais"
ARRANJO_TRES_LADOS = "tres_lados"
ARRANJO_CONTORNO = "contorno"
ARRANJOS = {
    ARRANJO_UM: "Um filete (vertical)",
    ARRANJO_PARALELOS: "Dois filetes paralelos (verticais)",
    ARRANJO_HORIZONTAIS: "Dois filetes horizontais (em cima e embaixo)",
    ARRANJO_TRES_LADOS: "Três lados (vertical + dois horizontais, em C)",
    ARRANJO_CONTORNO: "Contorno retangular",
}
#: Filetes numa linha ou paralelos: valem para o aumento pela direção da força (6.2.5.2 a).
ARRANJOS_EM_LINHA = (ARRANJO_UM, ARRANJO_PARALELOS, ARRANJO_HORIZONTAIS)
METODO_DIRECAO = "direcao"
METODO_ELASTICO = "elastico"
METODOS_SOLDA = {
    METODO_DIRECAO: "Pela direção da força e centro instantâneo (6.2.5.2)",
    METODO_ELASTICO: "Elástico, sem o aumento pela direção (a favor da segurança)",
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
    norma: str = sd.NBR_2025
    combinacao: str = sd.COMBINACAO_NORMAL
    metodo: str = METODO_DIRECAO


def _segmentos(e: EntradaSolda) -> list[tuple[float, float, float, float]]:
    h, b = e.comprimento_mm, e.largura_mm
    if e.arranjo == ARRANJO_UM:
        return [(0.0, 0.0, 0.0, h)]
    if e.arranjo == ARRANJO_PARALELOS:
        return [(0.0, 0.0, 0.0, h), (b, 0.0, b, h)]
    if e.arranjo == ARRANJO_HORIZONTAIS:
        return [(0.0, 0.0, b, 0.0), (0.0, h, b, h)]
    if e.arranjo == ARRANJO_TRES_LADOS:
        return [(0.0, 0.0, 0.0, h), (0.0, 0.0, b, 0.0), (0.0, h, b, h)]
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


def _metal_da_solda_do_grupo(
    e: EntradaSolda, f_elastica: float, q: float, avisos: list[str]
) -> Verificacao:
    """A linha do metal da solda: método elástico, 6.2.5.2 a), c) ou b) (centro instantâneo)."""
    base = f"0,60·f_w·(0,707·perna)/γ_w2 = {_n(q * 10, 2)} kN/cm, {e.eletrodo} (f_w = {_n(ELETRODOS[e.eletrodo], 0)} MPa)"
    ref_tabela = _ref_metal_da_solda(e.norma)
    elastica = Verificacao(
        "Solda: metal da solda", f_elastica * 10, q * 10, "kN/cm", ref_tabela,
        f"{base}; método elástico, sem o aumento pela direção (a favor da segurança)",
    )  # fmt: skip
    p = math.hypot(e.n_sd_kN, e.v_sd_kN)
    if e.metodo == METODO_ELASTICO or (p == 0 and e.m_sd_kNm == 0):
        return elastica
    segs = _segmentos(e)
    if e.m_sd_kNm == 0:
        if e.arranjo in ARRANJOS_EM_LINHA:
            vertical = e.arranjo != ARRANJO_HORIZONTAIS
            ao_longo, atraves = (e.v_sd_kN, e.n_sd_kN) if vertical else (e.n_sd_kN, e.v_sd_kN)
            theta = math.degrees(math.atan2(abs(atraves), abs(ao_longo)))
            k = sd.fator_direcao(theta)
            return Verificacao(
                "Solda: metal da solda", f_elastica * 10, q * k * 10, "kN/cm",
                sd.ref(e.norma, "6.2.5.2 a)", vista_na_2025=True),
                f"{base} × (1 + 0,5·sen^1,5 θ) = × {_n(k, 3)}; θ = {_n(theta, 1)}° entre a "
                "resultante e o eixo dos filetes (carga pelo centro do grupo)",
            )  # fmt: skip
        if e.n_sd_kN == 0 or e.v_sd_kN == 0:
            na_vertical = e.n_sd_kN == 0  # força vertical: os verticais são longitudinais
            longitudinal = sum(
                math.hypot(x2 - x1, y2 - y1) for x1, y1, x2, y2 in segs if (x1 == x2) == na_vertical
            )
            transversal = (
                sum(math.hypot(x2 - x1, y2 - y1) for x1, y1, x2, y2 in segs) - longitudinal
            )
            f_l, f_t = q * longitudinal, q * transversal
            return Verificacao(
                "Solda: metal da solda", p, sd.combinacao_longitudinal_transversal(f_l, f_t), "kN",
                sd.ref(e.norma, "6.2.5.2 c)"),
                f"maior entre F_wl + F_wt e 0,85·F_wl + 1,5·F_wt; F_wl = {_n(f_l, 1)} kN "
                f"({_n(longitudinal, 0)} mm longitudinais), F_wt = {_n(f_t, 1)} kN "
                f"({_n(transversal, 0)} mm transversais); {base}",
            )  # fmt: skip
        avisos.append(
            "Carga inclinada pelo centro de um grupo com filetes nas duas direções: o aumento de "
            "6.2.5.2 a) vale só para filetes em linha ou paralelos — ficou o método elástico."
        )
        return elastica
    try:
        cir = sd.centro_instantaneo(
            [sd.Segmento(*s) for s in segs], e.perna_mm, q, e.n_sd_kN, e.v_sd_kN, e.m_sd_kNm * 1000
        )
    except (ArithmeticError, ValueError):
        cir = None
    if cir is None or not cir.convergiu or cir.fator <= 0:
        avisos.append(
            "O centro instantâneo não convergiu para esta carga: ficou o método elástico, a favor "
            "da segurança."
        )
        return elastica
    if p > 0:
        solicitante, unidade, carga = (
            p,
            "kN",
            f"|P| = {_n(p, 2)} kN com M = {_n(e.m_sd_kNm, 2)} kN·m",
        )
    else:
        solicitante, unidade, carga = abs(e.m_sd_kNm), "kN·m", "só o momento"
    return Verificacao(
        "Solda: metal da solda", solicitante, cir.capacidade_kN, unidade,
        sd.ref(e.norma, "6.2.5.2 b)", vista_na_2025=True),
        f"centro instantâneo de rotação a ({_n(cir.x_mm, 1)}; {_n(cir.y_mm, 1)}) mm do centro do "
        f"grupo, {carga}; fator de capacidade {_n(cir.fator, 3)}; Δu e Δm do filete pelo ângulo "
        f"de cada trecho (6.2.5.2 b); {base}",
    )  # fmt: skip


#: Pernas de filete usuais na fabricação (mm), para a perna sugerida.
PERNAS_COMERCIAIS = (3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0)


def _atende_tudo(r: ResultadoLigacao) -> bool:
    return all(v.status not in ("NÃO OK", "ALERTA") for v in r.verificacoes)


def perna_sugerida(e: EntradaSolda, perna_estimada_mm: float) -> float | None:
    """A menor perna comercial, a partir da estimada, com que TODAS as verificações atendem.

    A estimativa (perna × aproveitamento do metal da solda) olha só a resistência da solda; a
    perna mínima e a máxima, o metal-base e uma troca do que governa só aparecem refazendo o
    cálculo com a perna comercial. ``None`` quando nenhuma perna da lista atende (o metal-base ou
    a perna máxima na borda não melhoram com a perna).
    """
    for perna in PERNAS_COMERCIAIS:
        if perna < perna_estimada_mm - 1e-9:
            continue
        if _atende_tudo(_calcular_solda(replace(e, perna_mm=perna))):
            return perna
    return None


def calcular_solda(e: EntradaSolda) -> ResultadoLigacao:
    """O grupo de filetes e, quando a resistência da solda dá a estimativa, a perna sugerida."""
    r = _calcular_solda(e)
    estimada = r.grandezas.get("perna_estimada_mm")
    if estimada is not None:
        sugerida = perna_sugerida(e, estimada)
        if sugerida is not None:
            r.grandezas["perna_sugerida_mm"] = sugerida
    return r


def _calcular_solda(e: EntradaSolda) -> ResultadoLigacao:
    if e.arranjo not in ARRANJOS:
        raise LigacaoInvalida(f"Arranjo desconhecido: {e.arranjo!r}.")
    if e.eletrodo not in ELETRODOS:
        raise LigacaoInvalida(f"Eletrodo desconhecido: {e.eletrodo!r}.")
    if e.aco not in ACOS:
        raise LigacaoInvalida(f"Aço desconhecido: {e.aco!r}.")
    if e.norma not in NORMAS or e.combinacao not in sd.COMBINACOES or e.metodo not in METODOS_SOLDA:
        raise LigacaoInvalida("Escolha a norma, a combinação e o método da lista.")
    if min(e.comprimento_mm, e.perna_mm, e.t1_mm, e.t2_mm) <= 0 or (
        e.arranjo != ARRANJO_UM and e.largura_mm <= 0
    ):
        raise LigacaoInvalida(
            "Comprimento, largura, perna e espessuras precisam ser maiores que zero."
        )
    fy, fu = ACOS[e.aco]
    fw = ELETRODOS[e.eletrodo]
    c = sd.coeficientes(e.combinacao)
    t_menor = min(e.t1_mm, e.t2_mm)
    f, _f_long, total = forca_por_mm_na_solda(e)
    linhas: list[Verificacao] = []
    avisos: list[str] = []
    tef = 0.7 * e.perna_mm
    perna_estimada: float | None = None
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
        q = sd.resistencia_filete_por_mm(e.perna_mm, fw, c.w2)
        metal = _metal_da_solda_do_grupo(e, f, q, avisos)
        linhas.append(metal)
        if metal.aproveitamento is not None:
            perna_estimada = e.perna_mm * metal.aproveitamento  # a capacidade é linear na perna
        r_mb, texto_mb = sd.metal_base_ao_cisalhamento_por_mm(t_menor, fy, fu, c)
        linhas.append(
            Verificacao(
                "Metal-base junto à solda (cisalhamento)",
                f * 10,
                r_mb * 10,
                "kN/cm",
                sd.ref(e.norma, "6.5.5"),
                f"{texto_mb} por cm, t = {_n(t_menor, 2)} mm (parte menos espessa); força por cm "
                "pelo método elástico",
            )
        )
    menor_linha = min(math.hypot(x2 - x1, y2 - y1) for x1, y1, x2, y2 in _segmentos(e))
    linhas.extend(_limites_do_filete(e.perna_mm, t_menor, e.t1_mm, menor_linha, norma=e.norma))
    titulo = f"Solda de filete — {ARRANJOS[e.arranjo].lower()}, perna {_n(e.perna_mm, 0)} mm"
    grandezas = {"forca_kN_cm": f * 10, "comprimento_total_mm": total}
    if perna_estimada is not None:
        grandezas["perna_estimada_mm"] = perna_estimada
    return ResultadoLigacao(SOLDA, titulo, e, tuple(linhas), grandezas, tuple(avisos))


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
_CHAPA_AZUL = "#bfdbfe"  # chapas soldadas (legenda: azul)
_BARRA = "#d1d5db"  # barra (legenda: cinza)
_APOIO = "#e2e8f0"
_WHITMORE = "#1d4ed8"  # seção de Whitmore (tracejado)


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


def _chamada(
    d: ImageDraw.ImageDraw,
    alvo: tuple[float, float],
    rotulo: tuple[float, float],
    numero: int,
    cor: str,
) -> None:
    """Linha de chamada do ponto ``alvo`` até um círculo numerado em ``rotulo`` (px).

    O texto fica na legenda, pelo número: assim os rótulos não se sobrepõem no desenho.
    """
    raio = 10 * _ESC
    d.line([alvo, rotulo], fill=cor, width=_ESC)
    d.ellipse(
        [alvo[0] - 3 * _ESC, alvo[1] - 3 * _ESC, alvo[0] + 3 * _ESC, alvo[1] + 3 * _ESC], fill=cor
    )
    x, y = rotulo
    d.ellipse([x - raio, y - raio, x + raio, y + raio], fill="#ffffff", outline=cor, width=2 * _ESC)
    d.text((x, y), str(numero), fill=cor, font=_fonte(12 * _ESC), anchor="mm")


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


def figura_cantoneira_dupla(e: EntradaCantoneiraDupla) -> ImagemDiagrama:
    """Vista lateral: a ponta da viga com a cantoneira (aba na alma), os furos e o apoio."""
    from core import cantoneiras as ct

    aba = ct.obter_cantoneira(e.cantoneira).b_mm
    como_chapa = EntradaChapaSimples(
        perfil=e.perfil,
        apoio=e.apoio,
        recorte=e.recorte,
        recorte_altura_mm=e.recorte_altura_mm,
        recorte_comprimento_mm=e.recorte_comprimento_mm,
        parafuso=e.parafuso,
        grau=e.grau,
        n_parafusos=e.n_parafusos,
        passo_mm=e.passo_mm,
        borda_vertical_mm=e.borda_vertical_mm,
        distancia_solda_furo_mm=e.gabarito_alma_mm,
        borda_horizontal_chapa_mm=max(aba - e.gabarito_alma_mm, 1.0),
        borda_alma_mm=e.borda_alma_mm,
        topo_alma_mm=e.topo_alma_mm,
        t_chapa_mm=ct.obter_cantoneira(e.cantoneira).t_mm,
        v_sd_kN=e.v_sd_kN,
    )
    base = figura_chapa_simples(como_chapa)
    titulo = "Ligação flexível por dupla cantoneira (vista lateral)"
    legenda = (
        f"Duas cantoneiras {e.cantoneira} ({e.aco_cantoneira}) de {_n(e.comprimento_mm, 0)} mm, "
        f"{e.n_parafusos} parafusos {e.parafuso} {e.grau} em corte duplo na alma da {e.perfil} e "
        f"{2 * e.n_parafusos} em corte simples no apoio; a aba aparece na posição da chapa (sem "
        "solda)."
    )
    return ImagemDiagrama(titulo, legenda, base.png, base.largura_px, base.altura_px)


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


def _momento_px(
    d: ImageDraw.ImageDraw,
    centro: tuple[float, float],
    raio: float,
    anti_horario: bool,
    giro_graus: float = 0.0,
) -> None:
    """Arco de 270° com a ponta no sentido do momento (na tela, y para baixo)."""
    cx, cy = centro
    inicio = 200.0 - giro_graus  # o desenho girado leva o arco junto
    d.arc(
        [cx - raio, cy - raio, cx + raio, cy + raio], inicio, inicio + 270, fill=_FORCA,
        width=3 * _ESC,
    )  # fmt: skip
    # o PIL mede o ângulo no sentido horário da tela: o arco vai de 200° a 470° (= 110°)
    t = math.radians(inicio if anti_horario else inicio + 270.0)
    px, py = cx + raio * math.cos(t), cy + raio * math.sin(t)
    tx, ty = (math.sin(t), -math.cos(t)) if anti_horario else (-math.sin(t), math.cos(t))
    nx, ny = -ty, tx
    ponta = 12 * _ESC
    d.polygon(
        [
            (px + tx * ponta * 0.7, py + ty * ponta * 0.7),
            (px - tx * ponta * 0.5 + nx * ponta * 0.55, py - ty * ponta * 0.5 + ny * ponta * 0.55),
            (px - tx * ponta * 0.5 - nx * ponta * 0.55, py - ty * ponta * 0.5 - ny * ponta * 0.55),
        ],
        fill=_FORCA,
    )


def figura_solda(e: EntradaSolda, giro_graus: float = 0.0) -> ImagemDiagrama:
    """O grupo de filetes na chapa, o centro geométrico, as forças nele e a legenda.

    ``giro_graus`` gira só o desenho (anti-horário), para a ligação ficar como está na estrutura:
    as forças continuam nos eixos x e y da chapa, que aparecem no canto.
    """
    giro = angulo_do_giro(giro_graus)
    largura_px, altura_px = 900, 480
    h = e.comprimento_mm
    b = e.largura_mm if e.arranjo != ARRANJO_UM else 60.0
    imagem = Image.new("RGB", (largura_px * _ESC, altura_px * _ESC), "#ffffff")
    dr = ImageDraw.Draw(imagem)
    # y da chapa para cima; na tela, para baixo
    tela = _Tela([(-10.0, -(h + 10.0)), (b + 10.0, 10.0)], (150, 110, 490, 400), giro)

    def p(x: float, y: float) -> tuple[float, float]:
        return tela(x, -y)

    chapa = [p(-10, -10), p(b + 10, -10), p(b + 10, h + 10), p(-10, h + 10)]
    dr.polygon(chapa, fill=_CHAPA_AZUL, outline=_LINHA, width=2 * _ESC)
    segs = _segmentos(e)
    for x1, y1, x2, y2 in segs:
        dr.line([p(x1, y1), p(x2, y2)], fill=_SOLDA, width=6 * _ESC)
    # cotas fora da chapa (fora da região carregada)
    esquerda, baixo = tela.direcao(-1.0, 0.0), tela.direcao(0.0, 1.0)
    _cota_alinhada(dr, p(-10, 0), p(-10, h), esquerda, f"L = {_n(h, 0)}", 20 * _ESC)
    if e.arranjo != ARRANJO_UM:
        _cota_alinhada(dr, p(0, -10), p(b, -10), baixo, f"b = {_n(b, 0)}", 12 * _ESC)
    # centro geométrico do grupo de linhas
    comp = [math.hypot(x2 - x1, y2 - y1) for x1, y1, x2, y2 in segs]
    total = sum(comp)
    xc = sum((x1 + x2) / 2 * c for (x1, _a, x2, _b), c in zip(segs, comp, strict=True)) / total
    yc = sum((y1 + y2) / 2 * c for (_a, y1, _b, y2), c in zip(segs, comp, strict=True)) / total
    centro = p(xc, yc)
    dr.ellipse(
        [centro[0] - 6 * _ESC, centro[1] - 6 * _ESC, centro[0] + 6 * _ESC, centro[1] + 6 * _ESC],
        outline=_TEXTO,
        width=2 * _ESC,
    )
    eixo_x, eixo_y = tela.direcao(1.0, 0.0), tela.direcao(0.0, -1.0)  # +x e +y da chapa
    for eixo in (eixo_x, eixo_y):
        dr.line([_mais(centro, eixo, -10 * _ESC), _mais(centro, eixo, 10 * _ESC)], fill=_TEXTO, width=_ESC)  # fmt: skip
    # forças de cálculo aplicadas no centro geométrico
    fonte = _fonte(12 * _ESC)
    forcas: list[str] = []
    if e.v_sd_kN:
        s = 1 if e.v_sd_kN > 0 else -1  # como no cálculo: V positivo para +y (para cima)
        sentido = (s * eixo_y[0], s * eixo_y[1])
        _seta_px(dr, _mais(centro, sentido, 14 * _ESC), _mais(centro, sentido, 78 * _ESC), _FORCA)
        _rotulo(
            dr, _mais(centro, sentido, 66 * _ESC), eixo_x, 10 * _ESC, "V", _FORCA, fonte, fundo=True
        )
        if giro:
            direcao_v = "+y da chapa" if s > 0 else "−y da chapa"
        else:
            direcao_v = "para cima" if s > 0 else "para baixo"
        forcas.append(f"V = {_n(e.v_sd_kN, 1)} kN ({direcao_v})")
    if e.n_sd_kN:
        s = 1 if e.n_sd_kN > 0 else -1  # N positivo para +x (para a direita)
        sentido = (s * eixo_x[0], s * eixo_x[1])
        _seta_px(dr, _mais(centro, sentido, 14 * _ESC), _mais(centro, sentido, 82 * _ESC), _FORCA)
        _rotulo(
            dr, _mais(centro, sentido, 70 * _ESC), eixo_y, 12 * _ESC, "N", _FORCA, fonte, fundo=True
        )
        if giro:
            direcao_n = "+x da chapa" if s > 0 else "−x da chapa"
        else:
            direcao_n = "para a direita" if s > 0 else "para a esquerda"
        forcas.append(f"N = {_n(e.n_sd_kN, 1)} kN ({direcao_n})")
    if e.m_sd_kNm:
        _momento_px(dr, centro, 34 * _ESC, e.m_sd_kNm > 0, giro)
        canto = (-eixo_x[0] + eixo_y[0], -eixo_x[1] + eixo_y[1])
        _rotulo(dr, centro, canto, 44 * _ESC, "M", _FORCA, fonte, fundo=True)
        forcas.append(
            f"M = {_n(abs(e.m_sd_kNm), 2)} kN·m ({'anti-horário' if e.m_sd_kNm > 0 else 'horário'})"
        )
    itens_do_giro: list[tuple[str, str, str]] = []
    if giro:  # os eixos da chapa num canto fixo da figura
        _eixos_da_peca(dr, (70 * _ESC, 430 * _ESC), tela)
        itens_do_giro = [
            ("", _COTA, f"Desenho girado {texto_do_giro(giro)}:"),
            ("", _COTA, "   x e y são os eixos da chapa (canto do desenho)"),
        ]
    titulo = "Grupo de soldas de filete"
    dr.text((18 * _ESC, 14 * _ESC), titulo, fill=_TEXTO, font=_fonte(16 * _ESC))
    dr.text(
        (18 * _ESC, 38 * _ESC),
        f"{ARRANJOS[e.arranjo]}, perna {_n(e.perna_mm, 0)} mm ({e.eletrodo}). Cotas em mm.",
        fill=_COTA,
        font=_fonte(11 * _ESC),
    )
    _legenda(
        dr,
        600 * _ESC,
        130 * _ESC,
        [
            ("linha", _SOLDA, f"Cordões de solda (perna {_n(e.perna_mm, 0)} mm)"),
            ("area", _CHAPA_AZUL, "Chapa soldada"),
            ("ponto", _TEXTO, "Centro geométrico do grupo"),
            ("seta", _FORCA, "Forças de cálculo, no centro geométrico:"),
            *(("", _FORCA, f"   {texto}") for texto in forcas),
            *itens_do_giro,
        ],
    )
    legenda = (
        f"{ARRANJOS[e.arranjo]}: L = {_n(h, 0)} mm"
        + (f", b = {_n(b, 0)} mm" if e.arranjo != ARRANJO_UM else "")
        + f"; perna {_n(e.perna_mm, 0)} mm; forças aplicadas no centro geométrico do grupo."
    )
    return ImagemDiagrama(
        titulo, legenda, _png(imagem, largura_px, altura_px), largura_px, altura_px
    )


#: Os tipos da barra soldada e da chapa no apoio moram em :mod:`core.ligacoes_soldadas`.
CHAPA_NO_APOIO = "chapa_no_apoio"
BARRA_SOLDADA = "barra_soldada"
TIPOS_SOLDADOS = (CHAPA_NO_APOIO, BARRA_SOLDADA)
#: As ligações cujo desenho pode girar (só o desenho: o cálculo não muda).
TIPOS_QUE_GIRAM = (SOLDA, CHAPA_NO_APOIO, BARRA_SOLDADA)

_ENTRADAS: dict[str, type] = {
    CHAPA_SIMPLES: EntradaChapaSimples,
    CANTONEIRA_DUPLA: EntradaCantoneiraDupla,
    PERFIL_FRIO: EntradaPerfilFrio,
    SOLDA: EntradaSolda,
}


def _classe_da_entrada(tipo: str) -> type:
    if tipo in TIPOS_SOLDADOS:
        from core import ligacoes_soldadas as ls

        return ls.ENTRADAS[tipo]
    return _ENTRADAS[tipo]


def figura(r: ResultadoLigacao, giro_graus: float = 0.0) -> ImagemDiagrama:
    """O desenho da ligação; ``giro_graus`` gira o das soldas (os outros não giram)."""
    if r.tipo in TIPOS_SOLDADOS:
        from core import ligacoes_soldadas as ls

        return ls.figura(r.adotada if r.adotada is not None else r.entrada, giro_graus)
    if r.tipo == CHAPA_SIMPLES:
        return figura_chapa_simples(r.entrada)
    if r.tipo == CANTONEIRA_DUPLA:
        return figura_cantoneira_dupla(r.entrada)
    if r.tipo == PERFIL_FRIO:
        return figura_perfil_frio(r.entrada)
    return figura_solda(r.entrada, giro_graus)


def figura_gravada(dados: Mapping[str, Any]) -> ImagemDiagrama:
    """A figura a partir do que o registro gravou (``{"tipo", "entrada"}`` e o giro, se houver)."""
    classe = _classe_da_entrada(str(dados["tipo"]))
    nomes = {f.name for f in fields(classe)}
    entrada = classe(**{k: v for k, v in dict(dados["entrada"]).items() if k in nomes})
    giro = float(dados.get("giro_graus") or 0.0)
    return figura(ResultadoLigacao(str(dados["tipo"]), "", entrada, ()), giro)


def calcular(entrada: Any) -> ResultadoLigacao:
    if isinstance(entrada, EntradaChapaSimples):
        return calcular_chapa_simples(entrada)
    if isinstance(entrada, EntradaCantoneiraDupla):
        return calcular_cantoneira_dupla(entrada)
    if isinstance(entrada, EntradaPerfilFrio):
        return calcular_perfil_frio(entrada)
    if isinstance(entrada, EntradaSolda):
        return calcular_solda(entrada)
    from core import ligacoes_soldadas as ls

    return ls.calcular(entrada)


# =============================================================================================
# Registro
# =============================================================================================
_METODO = {
    CANTONEIRA_DUPLA: (
        "Ligação flexível (rotulada) por duas cantoneiras: a cortante passa da alma da viga aos "
        "parafusos em corte duplo (com o momento V·g), às cantoneiras e aos parafusos no apoio em "
        "corte simples. Cantoneiras e alma pela NBR 8800 6.5."
    ),
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
        "Grupo de filetes no plano: metal da solda pela tabela das soldas da NBR 8800, com o "
        "aumento pela direção da força (6.2.5.2 a) para filetes em linha ou paralelos, a combinação "
        "de filetes longitudinais e transversais (6.2.5.2 c) e o centro instantâneo de rotação "
        "(6.2.5.2 b) quando há momento — ou o método elástico, a favor da segurança; metal-base "
        "pela 6.5.5, ou pela NBR 14762 10.2.3 quando a parte mais fina tem até 4,75 mm; limites de "
        "perna e de comprimento da 6.2.6.2."
    ),
    CHAPA_NO_APOIO: (
        "Chapa soldada no apoio (junta em T): a força normal à face do apoio, a cortante ao longo "
        "da solda e o momento no plano da chapa passam pela solda — filete (contínuo ou "
        "intermitente, de um ou dos dois lados), penetração total ou parcial, pela tabela das "
        "soldas da NBR 8800 e 6.2.5.2 a) —, pela chapa junto à solda (6.5.3 a 6.5.5) e pelo apoio "
        "(metal-base junto à solda e, na mesa de um perfil I ou H, 5.7.2 a 5.7.4). Forças por mm "
        "pelo método elástico; no modo dimensionar, o menor comprimento que passa, no passo de "
        "projeto."
    ),
    BARRA_SOLDADA: (
        "Barra axial (cantoneira ou chapa sobreposta) soldada na chapa de nó por filetes "
        "longitudinais no dorso e na borda — balanceados pelo centro geométrico da barra (6.1.8.1) "
        "ou iguais (6.1.8.2) — e, se houver, transversal na ponta (6.2.5.2 c). Barra à tração pelo "
        "item 5.2 com o C_t de 5.2.5; chapa de nó na seção de Whitmore (30° a partir do começo dos "
        "filetes) à tração e à compressão (6.5.3, 6.5.4) e ao colapso por rasgamento (6.5.6); a "
        "solda da chapa de nó no apoio com as componentes da força da barra. Força da ligação com "
        "o mínimo de 45 kN (6.1.5.2) e, quando pedido, o critério Anglo, item 9.1."
    ),
}
_PREMISSAS = {
    CANTONEIRA_DUPLA: [
        "Parafusos da alma com o momento V·g (g da face do apoio aos furos), a favor da segurança.",
        "Parafusos do apoio com V/(2n), sem a excentricidade da aba (gabarito curto).",
        "O apoio (alma da viga principal ou pilar) é verificado só no contato dos parafusos.",
    ],
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
        "Filetes de perna uniforme, no mesmo plano, com a carga no plano do grupo.",
        "Centro instantâneo de rotação pela 6.2.5.2 b): Δu e Δm de cada trecho pelo ângulo da força.",
        "Metal-base pela força por mm do método elástico, na parte menos espessa.",
    ],
    CHAPA_NO_APOIO: [
        "Forças por mm de solda pelo método elástico; com momento, sem o aumento pela direção.",
        "A chapa junto à solda é verificada no comprimento soldado (a favor da segurança na "
        "solda intermitente); a flambagem da chapa livre fica com o projetista.",
        "Na mesa de um perfil, a força normal centrada na alma e k = t_f (sem o raio de "
        "concordância); o perfil do apoio como um todo fica para o cálculo dele.",
        "Penetração parcial: garganta efetiva informada pela profundidade do chanfro (Tabela 6 "
        "da 2025; Tabela 5 da 2008).",
        "Penetração total em junta em T com chapa de espera não retirada: metal da solda com "
        "tenacidade Charpy de pelo menos 27 J, ensaiada a 4 °C ou menos (6.2.4.2).",
    ],
    BARRA_SOLDADA: [
        "Os filetes começam na ponta da barra; o cobrimento da superposição é o maior filete, "
        "salvo quando informado.",
        "Com filete na ponta, ele trabalha na resistência da tabela, sem o aumento (primeira "
        "expressão de 6.2.5.2 c).",
        "C_t da cantoneira com ℓ_c = média dos filetes longitudinais (a favor da segurança); "
        "na 2025, sem os limites 0,90 e 0,60 da 2008 e não menor que A_c/A_g (5.2.5 c).",
        "C_t da chapa só com filetes longitudinais: na 2025, 3ℓ_c²/(3ℓ_c² + b²)·(1 − t/(2ℓ_c)) "
        "com ℓ_c = média dos dois filetes (5.2.5 d); na 2008, 1,00, 0,87 ou 0,75 pelo menor filete.",
        "A compressão da barra (flambagem) é do cálculo da barra; aqui só a chapa de nó.",
    ],
}
_REFERENCIAS = [
    "ABNT NBR 8800:2025 — 6.1.5, 6.1.8, Tabela 9 (soldas), 6.2.5.2, Tabelas 10 e 11, 6.5.3 a "
    "6.5.6.",
    "ABNT NBR 8800:2008 — 5.2.5, 5.7, 6.1.5, 6.1.8, 6.2 (soldas), 6.3 (parafusos), 6.5 "
    "(elementos de ligação), Anexo A.",
    "ABNT NBR 14762:2010 — 9.6 (tração), 10.2 (soldas), 10.3 (parafusos), 10.4 (colapso por rasgamento).",
    "AISC 360-16 — J2.4 (centro instantâneo de rotação dos filetes).",
    "AISC Steel Construction Manual — Parte 9 (vigas recortadas, seção de Whitmore) e Parte 10 "
    "(chapa simples).",
]


def _entradas_do_registro(e: Any) -> dict[str, Any]:
    if isinstance(e, EntradaSolda):
        dados = asdict(e)
        dados["arranjo"] = ARRANJOS.get(e.arranjo, e.arranjo)
        dados["metodo"] = METODOS_SOLDA.get(e.metodo, e.metodo)
        dados["combinacao"] = sd.COMBINACOES.get(e.combinacao, e.combinacao)
    elif type(e).__name__ in ("EntradaChapaNoApoio", "EntradaBarraSoldada"):
        from core import ligacoes_soldadas as ls

        dados = ls.campos_do_registro(e)
    else:
        dados = asdict(e)
    saida = {k: v for k, v in dados.items() if v is not None and v != ""}
    if "norma" in saida:
        saida["norma"] = NORMAS_ROTULOS.get(str(saida["norma"]), saida["norma"])
    return saida


def destaque(r: ResultadoLigacao) -> str:
    g = r.governante
    texto = f"{r.titulo}: {r.status}; maior aproveitamento {_n(100 * r.aproveitamento_maximo, 1)} %"
    if g is not None:
        texto += f" ({g.nome.lower()})"
    return texto + "."


def registro_ligacao(
    r: ResultadoLigacao,
    *,
    contexto: Mapping[str, Any] | None = None,
    responsavel: str = "",
    giro_graus: float = 0.0,
) -> dict[str, Any]:
    """O registro técnico da ligação; ``giro_graus`` é o giro do desenho no memorial."""
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
    desenho = r.adotada if r.adotada is not None else r.entrada
    figura_ligacao: dict[str, Any] = {"tipo": r.tipo, "entrada": asdict(desenho)}
    giro = angulo_do_giro(giro_graus) if r.tipo in TIPOS_QUE_GIRAM else 0.0
    if giro:
        figura_ligacao["giro_graus"] = giro
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
            "figura_ligacao": figura_ligacao,
        },
        metodo=_METODO[r.tipo],
        premissas=list(_PREMISSAS[r.tipo]),
        alertas=alertas,
        referencias=list(_REFERENCIAS),
        conclusao=texto,
        responsavel=responsavel,
    )


def memorial_da_ligacao(
    r: ResultadoLigacao,
    *,
    projeto: Mapping[str, Any] | None = None,
    formato: str = "word",
    giro_graus: float = 0.0,
) -> bytes:
    """O memorial só desta ligação, em Word ou PDF, no padrão do memorial do projeto.

    Com o projeto ativo, a capa e o controle levam os dados dele; sem projeto, ficam
    "[a preencher]". Entra só o registro desta ligação (os outros cálculos do projeto não). O
    desenho sai com o mesmo giro da tela.
    """
    import importlib

    from core.technical_records import normalizar_registro_tecnico

    # O gerador do memorial ainda está fora da lista do mypy (adoção gradual): importado pelo nome
    # para não arrastar os módulos dele para a verificação deste.
    relatorio = importlib.import_module("core.project_report")
    registro = normalizar_registro_tecnico(registro_ligacao(r, giro_graus=giro_graus))
    base: dict[str, Any] = dict(projeto) if projeto else {"nome": MODULO_TITULO}
    base["registros_tecnicos"] = [registro]
    nome = (
        "gerar_relatorio_industrial_pdf" if formato == "pdf" else "gerar_relatorio_industrial_word"
    )
    conteudo: bytes = getattr(relatorio, nome)(base, secoes_incluidas=["registros"])
    return conteudo


def linhas_resumo(verificacoes: Sequence[Verificacao]) -> list[str]:
    """As linhas que não passaram, em texto curto (para avisos da página)."""
    return [f"{v.nome}: {v.formula}" for v in verificacoes if v.status == "NÃO OK"]


# =============================================================================================
# Resumo para a tela: frase do resultado, detalhamento adotado e verificações por grupo
# =============================================================================================
GRUPO_SOLDA = "Resistência da solda"
GRUPO_METAL_BASE = "Metal-base e chapa junto à solda"
GRUPO_PARAFUSOS = "Parafusos e contato"
GRUPO_BARRA = "Barra"
GRUPO_CHAPA_DE_NO = "Chapa de nó"
GRUPO_SOLDA_NO_APOIO = "Solda da chapa de nó no apoio"
GRUPO_VIGA = "Viga apoiada"
GRUPO_LIMITES = "Limites geométricos e de detalhe"
GRUPO_OUTROS = "Ligação"
#: Prefixo das linhas da solda da chapa de nó no apoio (barra soldada).
PREFIXO_SOLDA_NO_APOIO = "Chapa de nó no apoio — "


def grupo_da_verificacao(v: Verificacao) -> str:
    """Em que grupo a linha aparece na tabela da tela (só para ler: o cálculo não muda)."""
    nome = v.nome
    if nome.startswith(PREFIXO_SOLDA_NO_APOIO):
        return GRUPO_SOLDA_NO_APOIO
    if v.tipo == "limite":
        return GRUPO_LIMITES
    if nome.startswith("Barra"):
        return GRUPO_BARRA
    if nome.startswith("Chapa de nó"):
        return GRUPO_CHAPA_DE_NO
    if "metal-base" in nome.lower() or nome.startswith(("Apoio", "Chapa junto à solda")):
        return GRUPO_METAL_BASE
    if nome.startswith(("Solda", "Filete", "Penetração")):
        return GRUPO_SOLDA
    if nome.startswith(("Parafuso", "Rasgamento", "Esmagamento", "Pressão de contato")):
        return GRUPO_PARAFUSOS
    if nome.startswith(("Alma da viga", "Alma recortada")):
        return GRUPO_VIGA
    if ":" in nome:
        return nome.split(":", 1)[0]
    return GRUPO_OUTROS


def nome_no_grupo(v: Verificacao) -> str:
    """O nome da linha dentro do grupo, sem repetir o que o título do grupo já diz."""
    nome = v.nome.removeprefix(PREFIXO_SOLDA_NO_APOIO)
    nome = nome.removeprefix(f"{grupo_da_verificacao(v)}: ")
    return nome[:1].upper() + nome[1:]


def verificacoes_por_grupo(r: ResultadoLigacao) -> list[tuple[str, list[Verificacao]]]:
    """As verificações (sem as linhas só informativas) em grupos, para a tabela da tela."""
    grupos: dict[str, list[Verificacao]] = {}
    for v in r.verificacoes:
        if v.tipo == "informativo":
            continue
        grupos.setdefault(grupo_da_verificacao(v), []).append(v)

    # na ordem em que o cálculo os traz; os limites geométricos e de detalhe no fim
    nomes = sorted(grupos, key=lambda nome: nome == GRUPO_LIMITES)
    return [(nome, grupos[nome]) for nome in nomes]


def referencias_pendentes(r: ResultadoLigacao) -> list[str]:
    """As referências da edição atual ainda não vistas no texto (marcadas "a confirmar")."""
    return list(dict.fromkeys(v.referencia for v in r.verificacoes if sd.a_confirmar(v.referencia)))


def frase_do_resultado(r: ResultadoLigacao) -> str:
    """O resultado numa frase, para o topo dos resultados."""
    aproveitamento = f"{_n(100 * r.aproveitamento_maximo, 0)} %"
    if r.status == "NÃO OK":
        reprovadas = [v for v in r.verificacoes if v.status == "NÃO OK"]
        quais = "verificação" if len(reprovadas) == 1 else "verificações"
        return (
            f"Não atende: {len(reprovadas)} {quais} não passa{'m' if len(reprovadas) > 1 else ''} "
            f"(maior aproveitamento {aproveitamento})."
        )
    if r.status == "ALERTA":
        return (
            f"Atende às resistências (aproveitamento máximo {aproveitamento}), com ressalva para "
            "conferir nas verificações marcadas ALERTA."
        )
    return f"Atende às verificações executadas — aproveitamento máximo de {aproveitamento}."


def _mm(valor: float, casas: int = 0) -> str:
    return f"{_n(valor, casas)} mm"


def _detalhes_do_tipo(r: ResultadoLigacao) -> list[tuple[str, str]]:
    e = r.adotada if r.adotada is not None else r.entrada
    g = r.grandezas
    if r.tipo == SOLDA:
        linhas = [
            ("Arranjo", ARRANJOS[e.arranjo]),
            ("Eletrodo", e.eletrodo),
            ("Perna dos filetes (informada)", _mm(e.perna_mm, 0)),
            ("Comprimento total de solda", _mm(g.get("comprimento_total_mm", 0.0))),
        ]
        if "perna_estimada_mm" in g:
            linhas.append(
                ("Perna mínima estimada pela resistência", _mm(g["perna_estimada_mm"], 1))
            )
            sugerida = g.get("perna_sugerida_mm")
            if sugerida is None:
                linhas.append(
                    (
                        "Perna comercial que atende",
                        "nenhuma até 16 mm atende todas as verificações: o que reprova não "
                        "melhora com a perna (metal-base ou perna máxima na borda)",
                    )
                )
            elif abs(sugerida - e.perna_mm) < 1e-9:
                linhas.append(("Perna adotada", f"{_mm(sugerida)} — todas as verificações atendem"))
            else:
                linhas.append(
                    (
                        "Perna comercial que atende",
                        f"{_mm(sugerida)} — com ela, todas as verificações refeitas atendem",
                    )
                )
        return linhas
    if r.tipo == BARRA_SOLDADA:
        from core import ligacoes_soldadas as ls

        barra = ls._barra(e)
        linhas = [
            ("Barra", barra.nome + (" (uma de cada lado da chapa de nó)" if e.duas_pecas else "")),
            ("Eletrodo", e.eletrodo),
            ("Perna dos filetes da barra", _mm(e.perna_mm, 0)),
            ("Filete do dorso", _mm(e.l_dorso_mm)),
            ("Filete da borda", _mm(e.l_borda_mm)),
        ]
        if e.solda_na_ponta:
            linhas.append(("Filete na ponta da barra", _mm(barra.largura)))
        linhas.append(("Seção de Whitmore", _mm(g.get("largura_whitmore_mm", 0.0))))
        if e.com_apoio and "l_apoio_mm" in g:
            linhas.append(
                (
                    "Solda da chapa de nó no apoio",
                    f"dois filetes de {_mm(e.perna_apoio_mm, 0)} × {_mm(g['l_apoio_mm'])}"
                    + (
                        f" (disponível {_mm(r.entrada.l_apoio_mm)})"
                        if r.entrada.modo == ls.MODO_DIMENSIONAR
                        else ""
                    ),
                )
            )
        if "n_ligacao_kN" in g:
            linhas.append(("Força de cálculo da ligação", f"{_n(g['n_ligacao_kN'], 1)} kN"))
        return linhas
    if r.tipo == CHAPA_NO_APOIO:
        from core import ligacoes_soldadas as ls

        linhas = [("Tipo de solda", ls.TIPOS_DE_SOLDA[e.tipo_solda]), ("Eletrodo", e.eletrodo)]
        lados = "dois lados" if e.lados == 2 else "um lado"
        if e.tipo_solda == ls.TIPO_FILETE:
            linhas.append(("Perna do filete", f"{_mm(e.perna_mm, 0)}, {lados} da chapa"))
        elif e.tipo_solda == ls.TIPO_PARCIAL:
            linhas.append(("Profundidade do chanfro S", f"{_mm(e.profundidade_mm, 1)}, {lados}"))
        if "n_segmentos" in g:
            solda = f"{g['n_segmentos']:.0f} × {_mm(g['segmento_mm'])} por linha (intermitente)"
        else:
            solda = f"{_mm(g.get('comprimento_efetivo_mm', e.comprimento_mm))} contínuo"
        linhas.append(("Solda", f"{solda}, em {_mm(e.comprimento_mm)} de junta"))
        linhas.append(("Chapa", f"{_mm(e.t_chapa_mm, 1)} ({e.aco_chapa})"))
        return linhas
    if r.tipo == CHAPA_SIMPLES:
        return [
            (
                "Chapa",
                f"{_n(e.t_chapa_mm, 1)} × {_n(g.get('largura_chapa_mm', 0.0), 0)} × "
                f"{_n(g.get('altura_chapa_mm', 0.0), 0)} mm ({e.aco_chapa})",
            ),
            ("Parafusos", f"{e.n_parafusos} × {e.parafuso} {e.grau}"),
            (
                "Solda da chapa no apoio",
                f"dois filetes de {_mm(e.perna_solda_mm, 0)} ({e.eletrodo})",
            ),
        ]
    if r.tipo == CANTONEIRA_DUPLA:
        return [
            ("Cantoneiras", f"2 × {e.cantoneira} de {_mm(e.comprimento_mm)} ({e.aco_cantoneira})"),
            ("Parafusos na alma", f"{e.n_parafusos} × {e.parafuso} {e.grau}, corte duplo"),
            ("Parafusos no apoio", f"{2 * e.n_parafusos} × {e.parafuso} {e.grau}, corte simples"),
        ]
    if r.tipo == PERFIL_FRIO:
        return [
            (
                "Parafusos",
                f"{e.n_linhas} linha(s) × {e.n_por_linha} = {e.n_linhas * e.n_por_linha} × "
                f"{e.parafuso} {e.especificacao}",
            ),
            ("Chapa", _mm(e.t_chapa_mm, 2)),
        ]
    return []


def detalhamento_adotado(r: ResultadoLigacao) -> list[tuple[str, str]]:
    """O que vai para o desenho, em texto completo, mais as linhas só informativas do cálculo."""
    linhas = _detalhes_do_tipo(r)
    for v in r.verificacoes:
        if v.tipo != "informativo" or "adotad" in v.nome:  # "adotados" já vêm nas linhas do tipo
            continue
        if v.solicitante is not None:
            texto = f"{_n(v.solicitante, 1)} {v.unidade} — {v.formula}"
        else:
            texto = v.formula
        linhas.append((v.nome, texto))
    return linhas


# =============================================================================================
# Reações já registradas no projeto (para não redigitar)
# =============================================================================================
@dataclass(frozen=True)
class ReacaoRegistrada:
    rotulo: str
    v_kN: float  # vertical (cortante na ligação), de cálculo
    n_kN: float  # horizontal (normal na ligação), de cálculo; positivo puxando a viga


#: Momento na ponta da viga acima disso aparece no rótulo: a chapa simples não o leva.
MOMENTO_NA_PONTA_KNM = 0.5
TIPOS_LIGADOS = ("Viga", "Diagonal", "Contraventamento")


def _n_pt(valor: float, casas: int = 1) -> str:
    if round(valor, casas) == 0:
        valor = 0.0  # sem "-0,0"
    return f"{valor:.{casas}f}".replace(".", ",")


def reacoes_do_modelo(projeto: Mapping[str, Any] | None) -> list[ReacaoRegistrada]:
    """As forças de cálculo nas pontas das barras do modelo importado (Esforços do modelo).

    Para cada viga (e diagonal; sem tipo na tabela, pelo peso próprio), em cada ponta (o Fim 1 e o Fim 2 da viga no Simulation), a
    combinação ELU do plano de cargas com o maior cortante no plano da alma — o do eixo forte da
    tabela das barras: V₁ quando o eixo forte é o M₂ — e o normal na mesma combinação (tração
    positiva). O momento do eixo forte na ponta, quando passa de 0,5 kN·m, vai no rótulo: a
    ligação flexível (chapa simples, cantoneira dupla) não o leva — a junta do modelo é rígida.
    """
    from core import esforcos_modelo as em
    from core import leitura_do_modelo as ld
    from core import load_combinations as comb
    from core import plano_de_cargas as pc

    dados = em.esforcos_do_projeto(projeto)
    if not dados.casos:
        return []
    plano = pc.plano_do_projeto(projeto)
    preparo = em.preparar_combinacoes(dados, plano, list(comb.COMBINACOES_ULTIMAS))
    if preparo is None or not preparo.nomes:
        return []
    saida: list[ReacaoRegistrada] = []
    for nome in dados.nomes_dos_membros:
        cfg = dados.membros.get(nome, em.ConfiguracaoDoMembro())
        tipo = cfg.tipo
        if tipo == "—":  # sem tipo na tabela: o que o peso próprio diz
            tipo = ld.tipo_pelos_esforcos(dados, nome, plano)[0]
        if tipo not in TIPOS_LIGADOS:
            continue
        combinados, metodo, _ = em.combinados_do_membro(nome, preparo)
        if metodo.startswith("soma"):
            continue  # sem os pontos alinhados, não há "a ponta"
        rotulos = list(dict.fromkeys(r for _, r, _ in combinados))
        if len(rotulos) < 2:
            continue
        forte = 1 if cfg.eixo_forte == em.EIXO_M2 else 2  # (N, V1, V2, M1, M2, T)
        momento = 4 if cfg.eixo_forte == em.EIXO_M2 else 3
        for ponta, rotulo in (("ponta do Fim 1", rotulos[0]), ("ponta do Fim 2", rotulos[-1])):
            na_ponta = [(c, v) for c, r, v in combinados if r == rotulo]
            if not na_ponta:
                continue
            combinacao, vetor = max(na_ponta, key=lambda cv: abs(cv[1][forte]))
            v, n, m = abs(vetor[forte]), vetor[0], vetor[momento]
            texto = f"Modelo — {nome}, {ponta}: V {_n_pt(v)} kN · N {_n_pt(n)} kN"
            if abs(m) > MOMENTO_NA_PONTA_KNM:
                texto += f" · M {_n_pt(abs(m))} kN·m (ligação flexível não leva)"
            saida.append(ReacaoRegistrada(f"{texto} ({combinacao})", v, n))
    return saida


def reacoes_do_projeto(projeto: Mapping[str, Any] | None) -> list[ReacaoRegistrada]:
    """As reações de cálculo (ELU) dos cálculos registrados — vigas de piso e longarinas — e as
    forças nas pontas das barras do modelo importado (:func:`reacoes_do_modelo`).

    Viga de piso: a reação de cálculo e, com o critério Anglo, a mínima da ligação (item 9.1).
    Longarina: o modelo ELU gravado é resolvido de novo e cada apoio dá V = |R_y| e N = R_x.
    """
    from core import portico_plano as pp

    saida: list[ReacaoRegistrada] = []
    for registro in (projeto or {}).get("registros_tecnicos", []) or []:
        if not isinstance(registro, Mapping):
            continue
        res = registro.get("resultados")
        if not isinstance(res, Mapping):
            continue
        titulo = str(registro.get("titulo") or registro.get("modulo") or "cálculo")
        try:
            if registro.get("modulo_id") == "viga_de_piso" and res.get("reacao_de_calculo_kN"):
                v = float(res["reacao_de_calculo_kN"])
                saida.append(ReacaoRegistrada(f"{titulo}: reação de cálculo", v, 0.0))
                minima = res.get("reacao_minima_da_ligacao_kN")
                if minima and float(minima) > v + 1e-9:
                    saida.append(
                        ReacaoRegistrada(
                            f"{titulo}: mínima da ligação (Anglo 9.1)", float(minima), 0.0
                        )
                    )
            for item in res.get("figuras_portico") or []:
                if not isinstance(item, Mapping) or not isinstance(item.get("modelo"), Mapping):
                    continue
                elu = pp.resolver(pp.de_dicionario(item["modelo"]))
                for reacao in elu.reacoes:
                    saida.append(
                        ReacaoRegistrada(
                            f"{item.get('titulo') or titulo}: apoio {reacao.no} (ELU)",
                            abs(reacao.ry),
                            reacao.rx,
                        )
                    )
        except (TypeError, ValueError, KeyError, pp.PorticoInvalido):
            continue  # registro antigo ou estragado: simplesmente não oferece a reação
    try:
        saida.extend(reacoes_do_modelo(projeto))
    except (ArithmeticError, TypeError, ValueError, KeyError):
        pass  # esforços gravados estragados: só não oferece as pontas do modelo
    return saida
