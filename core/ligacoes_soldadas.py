"""Ligações soldadas: barra axial na chapa de nó e chapa soldada no apoio (NBR 8800, 2025 e 2008).

Dois cálculos, cada um fechando numa lista de :class:`~core.verificacao.Verificacao`:

1. **Chapa soldada no apoio** (junta em T): filete de um ou dos dois lados, contínuo ou
   intermitente, ou solda de penetração total ou parcial, com a força normal à face do apoio, a
   cortante ao longo da solda e o momento no plano da chapa. Verifica o metal da solda (tabela das
   soldas e 6.2.5.2 a), a chapa junto à solda (6.5.3 a 6.5.5), o apoio (metal-base junto à solda e,
   quando é a mesa de um perfil I ou H, 5.7.2 a 5.7.4) e os limites de 6.2.6.
2. **Barra soldada na chapa de nó** (cantoneira ligada por uma aba ou chapa sobreposta, de um lado
   ou dos dois lados da chapa de nó): filetes longitudinais no dorso e na borda — balanceados ou
   iguais (6.1.8) — e, se houver, o transversal na ponta (6.2.5.2 c); a barra à tração (5.2, C_t
   de 5.2.5); a chapa de nó (seção de Whitmore à tração e à compressão, colapso por rasgamento) e,
   se pedida, a solda da chapa de nó no apoio (o cálculo 1 com as componentes da força da barra).

No modo "dimensionar" o programa acha os comprimentos (arredondados para cima no passo de projeto,
5 mm por padrão) e verifica a ligação com eles; no modo "verificar" os comprimentos são dados.

Os dois cálculos aplicam a força mínima da ligação (6.1.5.2, 45 kN) e, na barra, o critério Anglo
(9.1: 75 % da tração resistente da barra e 3 t) quando pedido. Unidades: mm, MPa, kN e kN·m.
Regras das soldas em :mod:`core.soldas`. Sem Streamlit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from PIL import Image, ImageDraw

from core import cantoneiras as ct
from core import criterio_anglo as ca
from core import nbr8800 as nb
from core import section_catalog as sc
from core import soldas as sd
from core.beam_charts import ImagemDiagrama, _fonte
from core.desenho_girado import Tela as _Tela
from core.desenho_girado import angulo_do_giro, texto_do_giro
from core.desenho_girado import arco_entre as _arco_entre
from core.desenho_girado import cota_alinhada as _cota_alinhada
from core.desenho_girado import fora_de as _fora_de
from core.desenho_girado import legenda as _legenda
from core.desenho_girado import mais as _mais
from core.desenho_girado import rotulo as _rotulo
from core.desenho_girado import seta as _seta_px
from core.desenho_girado import tracejado as _tracejado
from core.desenho_girado import traco_ponto as _traco_ponto
from core.ligacoes import (
    _APOIO,
    _BARRA,
    _CHAPA_AZUL,
    _COTA,
    _ESC,
    _FORCA,
    _LINHA,
    _SOLDA,
    _TEXTO,
    _WHITMORE,
    ACOS,
    ELETRODOS,
    LigacaoInvalida,
    ResultadoLigacao,
    _chamada,
    _png,
)
from core.verificacao import Verificacao

CHAPA_NO_APOIO = "chapa_no_apoio"
BARRA_SOLDADA = "barra_soldada"

MODO_DIMENSIONAR = "dimensionar"
MODO_VERIFICAR = "verificar"
MODOS = {
    MODO_DIMENSIONAR: "Dimensionar (o programa acha os comprimentos)",
    MODO_VERIFICAR: "Verificar (os comprimentos são dados)",
}

TIPO_FILETE = "filete"
TIPO_TOTAL = "penetracao_total"
TIPO_PARCIAL = "penetracao_parcial"
TIPOS_DE_SOLDA = {
    TIPO_FILETE: "Filete",
    TIPO_TOTAL: "Penetração total",
    TIPO_PARCIAL: "Penetração parcial",
}

APOIO_CHAPA = "chapa"
APOIO_PERFIL = "perfil"
APOIOS = {
    APOIO_CHAPA: "Chapa ou peça qualquer (metal-base junto à solda)",
    APOIO_PERFIL: "Mesa de perfil I ou H (verifica também a mesa e a alma, 5.7)",
}
ORIENTACAO_PARALELA = "paralela"
ORIENTACAO_TRANSVERSAL = "transversal"
ORIENTACOES = {
    ORIENTACAO_PARALELA: "Chapa ao longo do eixo do perfil do apoio",
    ORIENTACAO_TRANSVERSAL: "Chapa atravessando a mesa do perfil do apoio",
}
FAMILIAS_DE_APOIO = ("W (mesa larga)", "HP (perfil de estaca)", "I duplamente simétrico")
#: Comprimento máximo que o modo "dimensionar" procura sem comprimento disponível.
COMPRIMENTO_MAXIMO_PROCURADO_MM = 3000.0


def perfis_de_apoio() -> list[str]:
    return [n for n, p in sc.listar_perfis().items() if p.familia in FAMILIAS_DE_APOIO]


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor + 0.0:.{casas}f}".replace(".", ",")


def _info(nome: str, valor: float | None, unidade: str, referencia: str, texto: str) -> Verificacao:
    return Verificacao(
        nome, valor, None, unidade, referencia, texto, status="INFO", tipo="informativo"
    )


def _limite(nome: str, passa: bool | None, referencia: str, texto: str) -> Verificacao:
    status = "ALERTA" if passa is None else ("OK" if passa else "NÃO OK")
    return Verificacao(nome, None, None, "—", referencia, texto, status=status, tipo="limite")


def _valida_aco(aco: str, oque: str) -> tuple[float, float]:
    if aco not in ACOS:
        raise LigacaoInvalida(f"Aço desconhecido ({oque}): {aco!r}.")
    return ACOS[aco]


def _escala_minima(forcas: tuple[float, float, float], aplica: bool) -> tuple[float, float]:
    """6.1.5.2: o fator que leva a resultante (N, V) a 45 kN, com a direção e o sentido dela."""
    n, v, _m = forcas
    p = math.hypot(n, v)
    if not aplica or p <= 0:
        return 1.0, p
    return max(1.0, sd.FORCA_MINIMA_DA_LIGACAO_KN / p), p


def _linha_forca_minima(norma: str, p: float, escala: float) -> Verificacao:
    return _info(
        "Força mínima da ligação",
        p * escala,
        "kN",
        sd.ref(norma, "6.1.5.2"),
        f"força de cálculo {_n(p, 2)} kN < 45 kN: a ligação é dimensionada para 45 kN, na direção "
        "e no sentido da força (exceto travejamento de barras compostas, tirantes de barra "
        "redonda, travessas de fechamento e terças)",
    )


# =============================================================================================
# 1. Chapa soldada no apoio (junta em T)
# =============================================================================================
@dataclass(frozen=True)
class EntradaChapaNoApoio:
    norma: str = sd.NBR_2025
    combinacao: str = sd.COMBINACAO_NORMAL
    modo: str = MODO_DIMENSIONAR
    tipo_solda: str = TIPO_FILETE
    lados: int = 2  # filete e penetração parcial: um ou dois lados da chapa
    t_chapa_mm: float = 12.7
    aco_chapa: str = "ASTM A36"
    comprimento_mm: float = 100.0  # da junta (disponível no modo dimensionar)
    perna_mm: float = 5.0
    profundidade_mm: float = 5.0  # penetração parcial: profundidade do chanfro S
    descontar_3mm: bool = False  # Tabela 6 (2025; Tabela 5 da 2008): garganta = S − 3 mm
    eletrodo: str = "E70"
    intermitente: bool = True
    segmento_mm: float = 40.0
    n_segmentos: int = 1  # por linha de solda
    passo_arredondamento_mm: float = 5.0
    n_sd_kN: float = 40.0  # normal à face do apoio, + tração
    v_sd_kN: float = 0.0  # ao longo da solda
    m_sd_kNm: float = 0.0  # no plano da chapa
    minimo_45kN: bool = True
    apoio: str = APOIO_CHAPA
    t_apoio_mm: float = 12.7
    aco_apoio: str = "ASTM A36"
    perfil_apoio: str = ""
    orientacao: str = ORIENTACAO_PARALELA
    perto_da_extremidade: bool = False


def _validar_chapa_no_apoio(e: EntradaChapaNoApoio) -> None:
    if e.norma not in sd.NORMAS or e.combinacao not in sd.COMBINACOES or e.modo not in MODOS:
        raise LigacaoInvalida("Escolha a norma, a combinação e o modo da lista.")
    if (
        e.tipo_solda not in TIPOS_DE_SOLDA
        or e.apoio not in APOIOS
        or e.orientacao not in ORIENTACOES
    ):
        raise LigacaoInvalida("Escolha o tipo de solda, o apoio e a orientação da lista.")
    if e.eletrodo not in ELETRODOS:
        raise LigacaoInvalida(f"Eletrodo desconhecido: {e.eletrodo!r}.")
    _valida_aco(e.aco_chapa, "chapa")
    _valida_aco(e.aco_apoio, "apoio")
    if min(e.t_chapa_mm, e.comprimento_mm, e.t_apoio_mm) <= 0:
        raise LigacaoInvalida("Espessuras e comprimento precisam ser maiores que zero.")
    if e.tipo_solda == TIPO_FILETE and e.perna_mm <= 0:
        raise LigacaoInvalida("A perna do filete precisa ser maior que zero.")
    if e.tipo_solda != TIPO_TOTAL and e.lados not in (1, 2):
        raise LigacaoInvalida("A solda vai de um lado ou dos dois lados da chapa.")
    if e.tipo_solda == TIPO_PARCIAL:
        garganta = e.profundidade_mm - (3.0 if e.descontar_3mm else 0.0)
        if garganta <= 0:
            raise LigacaoInvalida("A garganta efetiva da penetração parcial ficou ≤ 0.")
        if e.lados * e.profundidade_mm >= e.t_chapa_mm:
            raise LigacaoInvalida(
                "A profundidade do chanfro (somada dos dois lados) passou da espessura da chapa: "
                "isso é penetração total."
            )
    if e.intermitente and e.tipo_solda == TIPO_FILETE:
        if e.segmento_mm <= 0 or e.n_segmentos < 1:
            raise LigacaoInvalida("O segmento intermitente precisa de comprimento e quantidade.")
    if e.apoio == APOIO_PERFIL and e.perfil_apoio not in sc.listar_perfis():
        raise LigacaoInvalida("Escolha o perfil do apoio no catálogo.")


def _segmentos_da_linha(comprimento: float, segmento: float, n: int) -> list[tuple[float, float]]:
    """(início, fim) de cada segmento numa linha de solda de comprimento disponível ``comprimento``."""
    if n <= 1:
        meio = comprimento / 2
        return [(meio - segmento / 2, meio + segmento / 2)]
    passo = (comprimento - segmento) / (n - 1)
    return [(i * passo, i * passo + segmento) for i in range(n)]


@dataclass(frozen=True)
class _Geometria:
    """Uma linha de solda: área por mm (A = Σℓ), I e Z por mm de espessura, fibra extrema."""

    trechos: tuple[tuple[float, float], ...]
    efetivo_mm: float
    inercia_mm3: float
    modulo_plastico_mm2: float
    fibra_mm: float
    menor_trecho_mm: float


def _geometria(trechos: list[tuple[float, float]]) -> _Geometria:
    total = sum(b - a for a, b in trechos)
    yc = sum((a + b) / 2 * (b - a) for a, b in trechos) / total
    inercia = sum((b - a) ** 3 / 12 + (b - a) * ((a + b) / 2 - yc) ** 2 for a, b in trechos)
    plastico = 0.0
    for a, b in trechos:  # ∫|y| dy de cada trecho, com y medido do centro
        u, w = a - yc, b - yc
        plastico += (w * abs(w) - u * abs(u)) / 2 if u * w >= 0 else (u * u + w * w) / 2
    fibra = max(max(abs(a - yc), abs(b - yc)) for a, b in trechos)
    menor = min(b - a for a, b in trechos)
    return _Geometria(tuple(trechos), total, inercia, plastico, fibra, menor)


def _perfil_do_apoio(e: EntradaChapaNoApoio) -> Any | None:
    return sc.listar_perfis()[e.perfil_apoio] if e.apoio == APOIO_PERFIL else None


def _t_apoio(e: EntradaChapaNoApoio) -> float:
    perfil = _perfil_do_apoio(e)
    return float(perfil.espessura_mesa_mm) if perfil is not None else e.t_apoio_mm


def _verificacoes_do_apoio_perfil(
    e: EntradaChapaNoApoio, c: sd.Coeficientes, n: float, h_eq: float, geo: _Geometria
) -> list[Verificacao]:
    """5.7.2 a 5.7.4: a força normal à mesa do perfil do apoio, centrada na alma."""
    perfil = _perfil_do_apoio(e)
    if perfil is None or h_eq <= 0:
        return []
    fy = ACOS[e.aco_apoio][0]
    tf, tw = float(perfil.espessura_mesa_mm), float(perfil.espessura_alma_mm)
    d, bf = float(perfil.altura_mm), float(perfil.largura_mm)
    k = tf  # sem o raio de concordância (o catálogo não traz): a favor da segurança
    pegada = e.t_chapa_mm + (2 * e.perna_mm if e.tipo_solda == TIPO_FILETE else 0.0)
    if e.orientacao == ORIENTACAO_PARALELA:
        ln, atravessa = geo.efetivo_mm, pegada
    else:
        ln, atravessa = pegada, geo.efetivo_mm
    linhas: list[Verificacao] = []
    nome_perfil = f"{e.perfil_apoio} (t_f = {_n(tf, 1)}, t_w = {_n(tw, 1)} mm)"
    if n > 0:
        if atravessa < 0.15 * bf:
            linhas.append(
                Verificacao(
                    "Apoio: flexão local da mesa",
                    None,
                    None,
                    "kN",
                    sd.ref(e.norma, "5.7.2.1"),
                    f"largura de atuação {_n(atravessa, 1)} mm < 0,15·b_f = {_n(0.15 * bf, 1)} mm: "
                    "a verificação não é exigida",
                    status="N/A",
                )
            )
        else:
            fator = 0.5 if e.perto_da_extremidade else 1.0
            linhas.append(
                Verificacao(
                    "Apoio: flexão local da mesa",
                    h_eq,
                    fator * 6.25 * tf**2 * fy / c.a1 / 1000,
                    "kN",
                    sd.ref(e.norma, "5.7.2.2" + (" e 5.7.2.3" if fator < 1 else "")),
                    f"6,25·t_f²·f_y/γ_a1{' × 0,5 (a menos de 10·t_f da ponta)' if fator < 1 else ''}; "
                    f"{nome_perfil}",
                )
            )
    perto = e.perto_da_extremidade
    linhas.append(
        Verificacao(
            "Apoio: escoamento local da alma",
            h_eq,
            1.10 * ((2.5 if perto else 5.0) * k + ln) * fy * tw / c.a1 / 1000,
            "kN",
            sd.ref(e.norma, "5.7.3.2 " + ("b)" if perto else "a)")),
            f"1,10·({'2,5' if perto else '5'}·k + ℓ_n)·f_y·t_w/γ_a1, ℓ_n = {_n(ln, 1)} mm, "
            f"k = t_f (sem o raio, a favor da segurança); {nome_perfil}",
        )
    )
    if n < 0:
        raiz = math.sqrt(sd.E_ACO * fy * tf / tw)
        razao = (tw / tf) ** 1.5
        if not perto:
            fator, colchete, texto = (
                0.66,
                1 + 3 * (ln / d) * razao,
                "0,66·t_w²·[1 + 3·(ℓ_n/d)·(t_w/t_f)^1,5]",
            )
            item = "5.7.4.2 a)"
        elif ln / d <= 0.2:
            fator, colchete, texto = (
                0.33,
                1 + 3 * (ln / d) * razao,
                "0,33·t_w²·[1 + 3·(ℓ_n/d)·(t_w/t_f)^1,5]",
            )
            item = "5.7.4.2 b)"
        else:
            fator, colchete = 0.33, 1 + (4 * ln / d - 0.2) * razao
            texto, item = "0,33·t_w²·[1 + (4·ℓ_n/d − 0,2)·(t_w/t_f)^1,5]", "5.7.4.2 b)"
        linhas.append(
            Verificacao(
                "Apoio: enrugamento da alma",
                h_eq,
                fator * tw**2 * colchete * raiz / c.a1 / 1000,
                "kN",
                sd.ref(e.norma, item),
                f"{texto}·√(E·f_y·t_f/t_w)/γ_a1, ℓ_n = {_n(ln, 1)} mm, d = {_n(d, 0)} mm",
            )
        )
    return linhas


def _texto_metal_base(t_menor: float, comprimento: float, fy: float) -> str:
    return (
        f"A_MB = {_n(t_menor, 2)} × {_n(comprimento, 0)} mm (menor espessura × comprimento), "
        f"f_y = {_n(fy, 0)} MPa (o menor dos metais-base)"
    )


def _metal_base_normal(
    prefixo: str,
    n: float,
    m_kNm: float,
    t_menor: float,
    comprimento: float,
    fy: float,
    c: sd.Coeficientes,
    referencia: str,
) -> Verificacao:
    """Tabela 9, penetração total e parcial: metal-base A_MB·f_y/γ_a1 sob a força normal à solda."""
    n_rd = t_menor * comprimento * fy / c.a1 / 1000
    texto_mb = _texto_metal_base(t_menor, comprimento, fy)
    sentido = "tração" if n >= 0 else "compressão"
    if abs(m_kNm) > 0:
        m_rd = t_menor * comprimento**2 / 4 * fy / c.a1 / 1e6
        return Verificacao(
            f"{prefixo}: {sentido} normal e momento (metal-base)",
            abs(n) / n_rd + abs(m_kNm) / m_rd,
            1.0,
            "—",
            referencia,
            f"|N|/(A_MB·f_y/γ_a1) + M/(Z·f_y/γ_a1) ≤ 1, Z = t·L²/4 (soma linear, a favor da "
            f"segurança); N_Rd = {_n(n_rd, 1)} kN, M_Rd = {_n(m_rd, 2)} kN·m; {texto_mb}",
        )
    return Verificacao(
        f"{prefixo}: {sentido} normal (metal-base)",
        abs(n),
        n_rd,
        "kN",
        referencia,
        f"A_MB·f_y/γ_a1; {texto_mb}",
    )


def _verificar_chapa_no_apoio(
    e: EntradaChapaNoApoio, trechos: list[tuple[float, float]], forcas: tuple[float, float, float]
) -> list[Verificacao]:
    """As verificações para uma geometria de solda já escolhida e as forças de cálculo (N, V, M)."""
    n, v, m_kNm = forcas
    m = abs(m_kNm) * 1000.0
    c = sd.coeficientes(e.combinacao)
    norma = e.norma
    fy_c, fu_c = ACOS[e.aco_chapa]
    fy_s, fu_s = ACOS[e.aco_apoio]
    t_apoio = _t_apoio(e)
    t_menor = min(e.t_chapa_mm, t_apoio)
    fw = ELETRODOS[e.eletrodo]
    geo = _geometria(trechos)
    lados = 1 if e.tipo_solda == TIPO_TOTAL else e.lados
    # forças por mm de junta (somadas as linhas dos lados) na fibra mais solicitada
    f_n = abs(n) / geo.efetivo_mm + m * geo.fibra_mm / geo.inercia_mm3
    f_v = abs(v) / geo.efetivo_mm
    linhas: list[Verificacao] = []
    a_chapa = e.t_chapa_mm * geo.efetivo_mm
    tabela = sd.tabela(norma, "resistencia")
    if e.tipo_solda == TIPO_FILETE:
        perna = sd.perna_considerada(e.perna_mm, geo.menor_trecho_mm)
        q = sd.resistencia_filete_por_mm(perna, fw, c.w2)
        f = math.hypot(f_n, f_v) / lados
        base = (
            f"{lados} filete(s) de {_n(e.perna_mm, 1)} mm × {_n(geo.efetivo_mm, 0)} mm, {e.eletrodo}; "
            f"0,60·f_w·(0,707·perna)/γ_w2 = {_n(q * 10, 2)} kN/cm"
            + (
                f" (perna considerada L/4 = {_n(perna, 2)} mm, 6.2.6.2.3)"
                if perna < e.perna_mm
                else ""
            )
        )
        if m == 0 and f > 0:
            theta = math.degrees(math.atan2(f_n, f_v))
            k = sd.fator_direcao(theta)
            linhas.append(
                Verificacao(
                    "Solda: metal da solda",
                    f * 10,
                    q * k * 10,
                    "kN/cm",
                    sd.ref(norma, "6.2.5.2 a)", vista_na_2025=True),
                    f"{base} × (1 + 0,5·sen^1,5 θ) = × {_n(k, 3)}; θ = {_n(theta, 1)}° entre a "
                    "resultante e o eixo da solda",
                )  # fmt: skip
            )
        else:
            linhas.append(
                Verificacao(
                    "Solda: metal da solda",
                    f * 10,
                    q * 10,
                    "kN/cm",
                    sd.ref(norma, f"6.2.5.1, {tabela}", vista_na_2025=True),
                    f"{base}; com momento, método elástico sem o aumento pela direção (a carga fica "
                    "fora do plano dos filetes: 6.2.5.2 b não se aplica)",
                )  # fmt: skip
            )
    elif e.tipo_solda == TIPO_PARCIAL:
        if n != 0 or m > 0:  # Tabela 9: o menor entre o metal-base a) e o metal da solda b)
            linhas.append(
                _metal_base_normal(
                    "Penetração parcial", n, m_kNm, t_menor, geo.efetivo_mm,
                    min(fy_c, fy_s), c, sd.ref(norma, tabela, vista_na_2025=True),
                )
            )  # fmt: skip
        garganta = e.profundidade_mm - (3.0 if e.descontar_3mm else 0.0)
        cap_normal = 0.60 * fw * garganta * lados / c.w1 / 1000
        cap_corte = 0.60 * fw * garganta * lados / c.w2 / 1000
        texto_g = (
            f"garganta efetiva {_n(garganta, 1)} mm "
            f"({'S − 3 mm' if e.descontar_3mm else 'S'}, {sd.tabela(norma, 'garganta_efetiva')}), "
            f"{lados} lado(s)"
        )
        if f_v == 0:
            cap, texto = (
                cap_normal,
                f"0,60·A_w·f_w/γ_w1 (γ_w1 = {_n(c.w1, 2)}, {sd.ref_gama_w(norma, 'w1')})",
            )
        elif f_n == 0:
            cap, texto = (
                cap_corte,
                f"0,60·A_w·f_w/γ_w2 (γ_w2 = {_n(c.w2, 2)}, {sd.ref_gama_w(norma, 'w2')})",
            )
        else:
            cap = cap_corte
            texto = (
                "resultante (soma vetorial) com 0,60·A_w·f_w/γ_w2, o menor dos dois "
                f"(γ_w2 = {_n(c.w2, 2)}), a favor da segurança"
            )
        linhas.append(
            Verificacao(
                "Solda: metal da solda (penetração parcial)",
                math.hypot(f_n, f_v) * 10,
                cap * 10,
                "kN/cm",
                sd.ref(norma, tabela, vista_na_2025=True),
                f"{texto}; {texto_g}, {e.eletrodo}",
            )
        )
        linhas.append(
            sd.linha_minimo(
                "Solda: garganta mínima da penetração parcial",
                sd.garganta_minima(t_menor, norma),
                garganta,
                "mm",
                sd.ref(norma, sd.tabela(norma, "garganta"), vista_na_2025=True),
                f"parte menos espessa t = {_n(t_menor, 2)} mm",
            )
        )
    else:  # penetração total
        fy = min(fy_c, fy_s)
        n_rd = t_menor * geo.efetivo_mm * fy / c.a1 / 1000
        texto_mb = _texto_metal_base(t_menor, geo.efetivo_mm, fy)
        if n != 0 or m > 0:
            linhas.append(
                _metal_base_normal(
                    "Penetração total", n, m_kNm, t_menor, geo.efetivo_mm, fy, c,
                    sd.ref(norma, tabela, vista_na_2025=True),
                )
            )  # fmt: skip
        if v != 0:
            linhas.append(
                Verificacao(
                    "Penetração total: cisalhamento (metal-base)",
                    abs(v),
                    0.60 * n_rd,
                    "kN",
                    sd.ref(norma, tabela, vista_na_2025=True),
                    f"0,60·A_MB·f_y/γ_a1; {texto_mb}",
                )
            )
        linhas.append(_compatibilidade(e, n, v, t_apoio))
    # ------------------------------------------------------------------ chapa junto à solda (6.5)
    if e.tipo_solda != TIPO_TOTAL:
        texto_area = (
            f"chapa t = {_n(e.t_chapa_mm, 2)} mm no comprimento soldado {_n(geo.efetivo_mm, 0)} mm "
            f"(A = {_n(a_chapa, 0)} mm²)"
        )
        n_rd_esc = a_chapa * fy_c / c.a1 / 1000
        if n > 0:
            linhas.append(
                Verificacao(
                    "Chapa junto à solda: tração (escoamento)",
                    n,
                    n_rd_esc,
                    "kN",
                    sd.ref(norma, "6.5.3 a)"),
                    f"A·f_y/γ_a1; {texto_area}",
                )  # fmt: skip
            )
            linhas.append(
                Verificacao(
                    "Chapa junto à solda: tração (ruptura)",
                    n,
                    a_chapa * fu_c / c.a2 / 1000,
                    "kN",
                    sd.ref(norma, "6.5.3 b)"),
                    f"A_e·f_u/γ_a2, A_e = A (sem furos); {texto_area}",
                )  # fmt: skip
            )
        elif n < 0:
            linhas.append(
                Verificacao(
                    "Chapa junto à solda: compressão",
                    -n,
                    n_rd_esc,
                    "kN",
                    sd.ref(norma, "6.5.4 a)"),
                    f"A·f_y/γ_a1 (KL/r ≤ 25: chapa curta junto ao apoio — a flambagem da chapa "
                    f"livre fica com o projetista); {texto_area}",
                )  # fmt: skip
            )
        if m > 0:
            m_rd = e.t_chapa_mm * geo.modulo_plastico_mm2 * fy_c / c.a1 / 1e6
            linhas.append(
                Verificacao(
                    "Chapa junto à solda: força normal e momento",
                    abs(n) / n_rd_esc + abs(m_kNm) / m_rd,
                    1.0,
                    "—",
                    sd.ref(norma, "6.5.3 e 6.5.4"),
                    f"|N|/N_Rd + M/M_Rd ≤ 1 (soma linear, a favor da segurança), M_Rd = Z·f_y/γ_a1 = "
                    f"{_n(m_rd, 2)} kN·m; {texto_area}",
                )
            )
        if v != 0:
            linhas.append(
                Verificacao(
                    "Chapa junto à solda: cisalhamento (escoamento)",
                    abs(v),
                    0.60 * a_chapa * fy_c / c.a1 / 1000,
                    "kN",
                    sd.ref(norma, "6.5.5 a)"),
                    f"0,60·A_g·f_y/γ_a1; {texto_area}",
                )  # fmt: skip
            )
            linhas.append(
                Verificacao(
                    "Chapa junto à solda: cisalhamento (ruptura)",
                    abs(v),
                    0.60 * a_chapa * fu_c / c.a2 / 1000,
                    "kN",
                    sd.ref(norma, "6.5.5 b)"),
                    f"0,60·A_nv·f_u/γ_a2, A_nv = A (sem furos); {texto_area}",
                )  # fmt: skip
            )
        if v != 0:
            r_mb, texto_mb = sd.metal_base_ao_cisalhamento_por_mm(t_apoio, fy_s, fu_s, c)
            linhas.append(
                Verificacao(
                    "Apoio: metal-base junto à solda (cisalhamento)",
                    f_v * 10,
                    r_mb * 10,
                    "kN/cm",
                    sd.ref(norma, "6.5.5"),
                    f"a parcela ao longo da solda das {lados} linha(s) descarrega na espessura do "
                    f"apoio t = {_n(t_apoio, 2)} mm; {texto_mb} por cm",
                )
            )
    h_eq = (abs(n) / geo.efetivo_mm + m * geo.fibra_mm / geo.inercia_mm3) * geo.efetivo_mm
    linhas.extend(_verificacoes_do_apoio_perfil(e, c, n, h_eq if n else 0.0, geo))
    # ------------------------------------------------------------------ limites (6.2.6)
    if e.tipo_solda == TIPO_FILETE:
        linhas.extend(
            sd.limites_do_filete(
                norma,
                e.perna_mm,
                t_menor,
                None,
                geo.menor_trecho_mm,
                nome_do_comprimento=(
                    "comprimento mínimo do segmento" if e.intermitente else "comprimento mínimo"
                ),
            )
        )
        if e.intermitente:
            linhas.append(_intermitente_permitido(e, c, (n, v, m_kNm), t_menor))
            ocupado = sum(b - a for a, b in trechos)
            linhas.append(
                sd.linha_maximo(
                    "Solda intermitente: segmentos cabem na junta",
                    ocupado,
                    e.comprimento_mm,
                    "mm",
                    sd.ref(norma, "6.2.6.2.4"),
                    f"{len(trechos)} segmento(s) de {_n(trechos[0][1] - trechos[0][0], 0)} mm por "
                    f"linha num comprimento de {_n(e.comprimento_mm, 0)} mm",
                )
            )
    if e.tipo_solda == TIPO_PARCIAL and e.lados == 1 and (n != 0 or m > 0):
        linhas.append(
            _limite(
                "Penetração parcial de um lado só",
                None,
                sd.ref(norma, "6.2.6.1"),
                "com força normal ou momento a raiz da solda fica tracionada e a junta tende a "
                "girar: prefira solda dos dois lados (ou filetes de reforço)",
            )
        )
    return linhas


def _compatibilidade(e: EntradaChapaNoApoio, n: float, v: float, t_apoio: float) -> Verificacao:
    """Penetração total: metal da solda compatível com um dos metais-base (nota a da Tabela 7)."""
    norma = e.norma
    if n < 0 and v == 0 and norma == sd.NBR_2025:
        testes = [
            sd.eletrodo_compativel_a_compressao(e.aco_chapa, e.t_chapa_mm, e.eletrodo),
            sd.eletrodo_compativel_a_compressao(e.aco_apoio, t_apoio, e.eletrodo),
        ]
        regra = "compressão normal: permitido até 70 MPa abaixo do metal compatível"
    else:
        maior = n > 0
        testes = [
            sd.eletrodo_compativel(e.aco_chapa, e.t_chapa_mm, e.eletrodo, so_a_maior_classe=maior),
            sd.eletrodo_compativel(e.aco_apoio, t_apoio, e.eletrodo, so_a_maior_classe=maior),
        ]
        regra = (
            "tração normal: compatibilidade total, e com duas classes no grupo só a maior (nota e)"
            if maior
            else "compatibilidade total"
        )
    passa: bool | None = True if True in testes else (None if None in testes else False)
    if norma == sd.NBR_2008:
        referencia = sd.ref(norma, sd.tabela(norma, "compatibilidade"))
    else:  # a coluna de compatibilidade da Tabela 9 e os grupos da Tabela 8
        referencia = sd.ref(
            norma,
            f"{sd.tabela(norma, 'resistencia')}, compatibilidade, e "
            f"{sd.tabela(norma, 'compatibilidade')}",
            vista_na_2025=True,
        )
    texto = f"{e.eletrodo} com {e.aco_chapa} e {e.aco_apoio}; {regra}"
    if passa is None:
        texto += "; aço fora da tabela de compatibilidade: confirme o eletrodo"
    return _limite("Penetração total: metal da solda compatível", passa, referencia, texto)


def _intermitente_permitido(
    e: EntradaChapaNoApoio, c: sd.Coeficientes, forcas: tuple[float, float, float], t_menor: float
) -> Verificacao:
    """6.2.6.2.4: intermitente só quando a solda contínua de perna mínima já sobra."""
    n, v, m_kNm = forcas
    perna = sd.perna_minima(t_menor)
    geo = _geometria([(0.0, e.comprimento_mm)])
    f_n = abs(n) / geo.efetivo_mm + abs(m_kNm) * 1000 * geo.fibra_mm / geo.inercia_mm3
    f = math.hypot(f_n, abs(v) / geo.efetivo_mm) / e.lados
    q = sd.resistencia_filete_por_mm(perna, ELETRODOS[e.eletrodo], c.w2)
    return Verificacao(
        "Solda intermitente: permitida",
        f * 10,
        q * 10,
        "kN/cm",
        sd.ref(e.norma, "6.2.6.2.4"),
        f"a solda contínua de perna mínima ({_n(perna, 0)} mm) em {_n(e.comprimento_mm, 0)} mm "
        "precisa resistir mais que o exigido (método elástico, sem o aumento); senão use contínua",
        tipo="limite",
        status="OK" if f <= q + 1e-12 else "NÃO OK",
    )


def _resistencia_passa(linhas: list[Verificacao]) -> bool:
    return all(
        (v.aproveitamento is None or v.aproveitamento <= 1.0 + 1e-9)
        for v in linhas
        if v.tipo == "resistencia"
    ) and not any(v.status == "NÃO OK" and "comprimento mínimo" in v.nome for v in linhas)


def _trechos_continuos(comprimento: float) -> list[tuple[float, float]]:
    return [(0.0, comprimento)]


def calcular_chapa_no_apoio(e: EntradaChapaNoApoio) -> ResultadoLigacao:
    _validar_chapa_no_apoio(e)
    escala, p = _escala_minima((e.n_sd_kN, e.v_sd_kN, e.m_sd_kNm), e.minimo_45kN)
    forcas = (e.n_sd_kN * escala, e.v_sd_kN * escala, e.m_sd_kNm * escala)
    intermitente = e.intermitente and e.tipo_solda == TIPO_FILETE
    adotada = e
    if e.modo == MODO_DIMENSIONAR:
        passo = e.passo_arredondamento_mm if e.passo_arredondamento_mm > 0 else 5.0
        if intermitente:
            segmento = sd.adotar(max(e.segmento_mm, sd.comprimento_minimo(e.perna_mm)), passo)
            maximo = max(1, int(e.comprimento_mm // segmento))
            escolhido = maximo
            for n_seg in range(1, maximo + 1):
                trechos = _segmentos_da_linha(e.comprimento_mm, segmento, n_seg)
                if _resistencia_passa(_verificar_chapa_no_apoio(e, trechos, forcas)):
                    escolhido = n_seg
                    break
            adotada = replace(e, modo=MODO_VERIFICAR, segmento_mm=segmento, n_segmentos=escolhido)
        else:
            inicio = sd.adotar(
                sd.comprimento_minimo(e.perna_mm) if e.tipo_solda == TIPO_FILETE else passo, passo
            )
            limite = e.comprimento_mm if e.comprimento_mm > 0 else COMPRIMENTO_MAXIMO_PROCURADO_MM
            escolhido_l = limite
            comprimento = inicio
            while comprimento <= limite + 1e-9:
                if _resistencia_passa(
                    _verificar_chapa_no_apoio(e, _trechos_continuos(comprimento), forcas)
                ):
                    escolhido_l = comprimento
                    break
                comprimento += passo
            adotada = replace(e, modo=MODO_VERIFICAR, comprimento_mm=escolhido_l)
    if intermitente:
        trechos = _segmentos_da_linha(
            adotada.comprimento_mm, adotada.segmento_mm, adotada.n_segmentos
        )
    else:
        trechos = _trechos_continuos(adotada.comprimento_mm)
    linhas = _verificar_chapa_no_apoio(adotada, trechos, forcas)
    avisos: list[str] = []
    if escala > 1.0:
        linhas.insert(0, _linha_forca_minima(e.norma, p, escala))
    if e.modo == MODO_DIMENSIONAR:
        if intermitente:
            texto = (
                f"{adotada.n_segmentos} segmento(s) de {_n(adotada.segmento_mm, 0)} mm por linha, "
                f"em {_n(e.comprimento_mm, 0)} mm de junta"
            )
        else:
            texto = f"comprimento da solda {_n(adotada.comprimento_mm, 0)} mm"
        linhas.insert(0, _info("Solda adotada", None, "—", "", texto))
        if not _resistencia_passa(linhas):
            avisos.append(
                "Nem o maior comprimento disponível resolve: aumente a perna, a espessura da chapa "
                "ou o comprimento da junta."
            )
    geo = _geometria(trechos)
    rotulo = TIPOS_DE_SOLDA[e.tipo_solda].lower()
    if intermitente:
        rotulo += " intermitente"
    titulo = f"Chapa soldada no apoio — {rotulo}, {_n(geo.efetivo_mm, 0)} mm por linha"
    grandezas = {
        "comprimento_efetivo_mm": geo.efetivo_mm,
        "n_kN": forcas[0],
        "v_kN": forcas[1],
        "m_kNm": forcas[2],
    }
    if intermitente:
        grandezas["n_segmentos"] = float(adotada.n_segmentos)
        grandezas["segmento_mm"] = adotada.segmento_mm
    return ResultadoLigacao(
        CHAPA_NO_APOIO, titulo, e, tuple(linhas), grandezas, tuple(avisos), adotada=adotada
    )


# =============================================================================================
# 2. Barra soldada na chapa de nó
# =============================================================================================
PECA_CANTONEIRA = "cantoneira"
PECA_CHAPA = "chapa"
PECAS = {
    PECA_CANTONEIRA: "Cantoneira ligada por uma aba",
    PECA_CHAPA: "Chapa (tala) sobreposta",
}
DISTRIBUICAO_BALANCEADA = "balanceada"
DISTRIBUICAO_IGUAL = "igual"
DISTRIBUICOES = {
    DISTRIBUICAO_BALANCEADA: "Balanceada: o centro da solda no eixo da barra (6.1.8.1)",
    DISTRIBUICAO_IGUAL: "Igual no dorso e na borda (6.1.8.2, barra sem fadiga)",
}
TAN_30 = math.tan(math.radians(30.0))


@dataclass(frozen=True)
class EntradaBarraSoldada:
    norma: str = sd.NBR_2025
    combinacao: str = sd.COMBINACAO_NORMAL
    modo: str = MODO_DIMENSIONAR
    peca: str = PECA_CANTONEIRA
    cantoneira: str = 'L 2" × 1/4"'
    largura_mm: float = 50.8  # chapa: largura (distância entre os filetes)
    t_peca_mm: float = 6.35  # chapa: espessura
    aco_peca: str = "ASTM A36"
    duas_pecas: bool = False  # uma de cada lado da chapa de nó
    t_no_mm: float = 8.0
    aco_no: str = "ASTM A36"
    largura_no_mm: float = 0.0  # da chapa de nó na seção de Whitmore (0: não limita)
    eletrodo: str = "E70"
    perna_mm: float = 4.0
    distribuicao: str = DISTRIBUICAO_BALANCEADA
    solda_na_ponta: bool = False
    l_dorso_mm: float = 130.0  # verificar
    l_borda_mm: float = 55.0
    cobrimento_mm: float = 0.0  # 0: igual ao maior filete
    passo_arredondamento_mm: float = 5.0
    n_t_sd_kN: float = 100.0
    n_c_sd_kN: float = 0.0
    k_no: float = 1.2
    l_livre_no_mm: float = 100.0
    minimo_45kN: bool = True
    anglo: bool = False
    com_apoio: bool = True
    theta_graus: float = 60.0
    l_apoio_mm: float = 115.0  # disponível (dimensionar) ou da solda (verificar)
    perna_apoio_mm: float = 6.0
    excentricidade_mm: float = 0.0
    apoio: str = APOIO_CHAPA
    t_apoio_mm: float = 19.0
    aco_apoio: str = "ASTM A572 Gr 50"
    perfil_apoio: str = ""
    orientacao: str = ORIENTACAO_PARALELA
    perto_da_extremidade: bool = False


@dataclass(frozen=True)
class _Barra:
    nome: str
    largura: float  # C: distância entre os filetes do dorso e da borda
    t: float
    area: float
    x_barra: float  # do dorso ao centro geométrico (e_c de 5.2.5)
    area_conectada: float  # A_c de 5.2.5: a aba ligada da cantoneira; a chapa inteira


def _barra(e: EntradaBarraSoldada) -> _Barra:
    if e.peca == PECA_CANTONEIRA:
        try:
            cant = ct.obter_cantoneira(e.cantoneira)
        except (KeyError, ValueError):
            raise LigacaoInvalida(f"Cantoneira desconhecida: {e.cantoneira!r}.") from None
        return _Barra(
            cant.nome, cant.b_mm, cant.t_mm, cant.area_mm2, cant.x_barra_mm, cant.area_aba_mm2
        )
    nome = f"Chapa {_n(e.largura_mm, 1)} × {_n(e.t_peca_mm, 2)} mm"
    area = e.largura_mm * e.t_peca_mm
    return _Barra(nome, e.largura_mm, e.t_peca_mm, area, e.largura_mm / 2, area)


def _validar_barra(e: EntradaBarraSoldada) -> None:
    if e.norma not in sd.NORMAS or e.combinacao not in sd.COMBINACOES or e.modo not in MODOS:
        raise LigacaoInvalida("Escolha a norma, a combinação e o modo da lista.")
    if e.peca not in PECAS or e.distribuicao not in DISTRIBUICOES:
        raise LigacaoInvalida("Escolha a peça e a distribuição da solda da lista.")
    if e.eletrodo not in ELETRODOS:
        raise LigacaoInvalida(f"Eletrodo desconhecido: {e.eletrodo!r}.")
    for aco, oque in ((e.aco_peca, "barra"), (e.aco_no, "chapa de nó"), (e.aco_apoio, "apoio")):
        _valida_aco(aco, oque)
    if min(e.t_no_mm, e.perna_mm) <= 0 or (
        e.peca == PECA_CHAPA and min(e.largura_mm, e.t_peca_mm) <= 0
    ):
        raise LigacaoInvalida("Espessuras, largura e perna precisam ser maiores que zero.")
    if e.modo == MODO_VERIFICAR and min(e.l_dorso_mm, e.l_borda_mm) <= 0:
        raise LigacaoInvalida("Informe os comprimentos dos filetes do dorso e da borda.")
    if e.n_t_sd_kN < 0 or e.n_c_sd_kN < 0 or (e.n_t_sd_kN == 0 and e.n_c_sd_kN == 0):
        raise LigacaoInvalida("Informe a tração ou a compressão de cálculo da barra (positivas).")
    if e.com_apoio and not (0 < e.theta_graus <= 90 and e.l_apoio_mm > 0 and e.perna_apoio_mm > 0):
        raise LigacaoInvalida(
            "Solda no apoio: o ângulo fica entre 0° e 90°, e comprimento e perna maiores que zero."
        )


@dataclass(frozen=True)
class _Forcas:
    n_ligacao: float  # força de cálculo da ligação (com 6.1.5.2 e Anglo)
    n_peca: float  # por peça (metade com duas peças)
    origem: str


def _forca_da_ligacao(
    e: EntradaBarraSoldada, barra: _Barra, c: sd.Coeficientes
) -> tuple[_Forcas, list[Verificacao]]:
    fy, fu = ACOS[e.aco_peca]
    pecas = 2 if e.duas_pecas else 1
    n = max(e.n_t_sd_kN, e.n_c_sd_kN)
    linhas: list[Verificacao] = []
    origem = "a força de cálculo da barra"
    if e.anglo:
        n_t_rd = pecas * barra.area * fy / c.a1 / 1000
        minima = ca.capacidade_minima_da_ligacao_kN(n_t_rd)
        linhas.append(
            _info(
                "Critério Anglo: força mínima da ligação",
                minima,
                "kN",
                "Anglo 9.1",
                f"máx(75 % de A_g·f_y/γ_a1 da barra = 0,75 × {_n(n_t_rd, 1)} kN; 3 t = 29,42 kN)",
            )
        )
        if minima > n:
            n, origem = minima, "o mínimo do critério Anglo (item 9.1)"
    if e.minimo_45kN and n < sd.FORCA_MINIMA_DA_LIGACAO_KN:
        linhas.append(_linha_forca_minima(e.norma, n, sd.FORCA_MINIMA_DA_LIGACAO_KN / n))
        n, origem = sd.FORCA_MINIMA_DA_LIGACAO_KN, "o mínimo de 45 kN (6.1.5.2)"
    return _Forcas(n, n / pecas, origem), linhas


def _forca_de_compressao(e: EntradaBarraSoldada) -> float:
    """A compressão de cálculo da ligação, com o mínimo de 45 kN (6.1.5.2) quando aplicado."""
    if e.minimo_45kN:
        return max(e.n_c_sd_kN, sd.FORCA_MINIMA_DA_LIGACAO_KN)
    return e.n_c_sd_kN


def _por_mm_longitudinal(
    e: EntradaBarraSoldada, barra: _Barra, c: sd.Coeficientes
) -> tuple[float, float, str]:
    """(metal da solda, governante com o metal-base, de onde vem) por mm de filete longitudinal."""
    q = sd.resistencia_filete_por_mm(e.perna_mm, ELETRODOS[e.eletrodo], c.w2)
    fy_p, fu_p = ACOS[e.aco_peca]
    fy_n, fu_n = ACOS[e.aco_no]
    pecas = 2 if e.duas_pecas else 1
    mb_peca, _ = sd.metal_base_ao_cisalhamento_por_mm(barra.t, fy_p, fu_p, c)
    mb_no, _ = sd.metal_base_ao_cisalhamento_por_mm(e.t_no_mm, fy_n, fu_n, c)
    candidatos = [
        (q, "o metal da solda"),
        (mb_peca, "o metal-base da barra"),
        (mb_no / pecas, "o metal-base da chapa de nó"),
    ]
    r, origem = min(candidatos, key=lambda x: x[0])
    return q, r, origem


def _parcelas(
    e: EntradaBarraSoldada, barra: _Barra, n_peca: float, f_ponta: float
) -> tuple[float, float]:
    """(F do dorso, F da borda): balanceadas pelo centro da barra ou iguais."""
    longitudinal = max(n_peca - f_ponta, 0.0)
    if e.distribuicao == DISTRIBUICAO_BALANCEADA and e.peca == PECA_CANTONEIRA:
        c_ = barra.largura
        f1 = n_peca * (c_ - barra.x_barra) / c_ - f_ponta / 2
        f2 = n_peca * barra.x_barra / c_ - f_ponta / 2
        return max(f1, 0.0), max(f2, 0.0)
    return longitudinal / 2, longitudinal / 2


def _comprimento_necessario(forca: float, r_por_mm: float, perna: float, norma: str) -> float:
    """O menor L com r·β(L)·L ≥ F (β do filete longo, 6.2.2.2 d).

    Na 2025 o comprimento efetivo para em 180·d_w (L > 300·d_w): quando nem isso basta, devolve
    300·d_w — mais comprimento não ajuda — e a verificação mostra que não passa.
    """
    if forca <= 0:
        return 0.0
    teto = sd.EFETIVO_DO_FILETE_MUITO_LONGO * perna
    if norma == sd.NBR_2025 and forca > r_por_mm * teto + 1e-9:
        return sd.RAZAO_DO_FILETE_MUITO_LONGO * perna
    comprimento = forca / r_por_mm
    for _ in range(60):
        novo = forca / (r_por_mm * sd.beta_filete_longo(comprimento, perna))
        if abs(novo - comprimento) < 1e-6:
            break
        comprimento = novo
    return comprimento


def _dimensionar_filetes(
    e: EntradaBarraSoldada, barra: _Barra, forcas: _Forcas, c: sd.Coeficientes
) -> tuple[float, float]:
    q, r, _ = _por_mm_longitudinal(e, barra, c)
    f_ponta = q * barra.largura if e.solda_na_ponta else 0.0
    f1, f2 = _parcelas(e, barra, forcas.n_peca, f_ponta)
    minimo = sd.comprimento_minimo(e.perna_mm)
    if e.peca == PECA_CHAPA and not e.solda_na_ponta:
        minimo = max(minimo, barra.largura)  # 6.2.6.2.3: cada filete ≥ distância entre eles
    passo = e.passo_arredondamento_mm if e.passo_arredondamento_mm > 0 else 5.0
    a = sd.adotar(max(_comprimento_necessario(f1, r, e.perna_mm, e.norma), minimo), passo)
    b = sd.adotar(max(_comprimento_necessario(f2, r, e.perna_mm, e.norma), minimo), passo)
    if e.cobrimento_mm <= 0:  # o cobrimento é o maior filete: 6.2.6.2.5
        cobrimento = sd.adotar(sd.cobrimento_minimo(min(barra.t, e.t_no_mm)), passo)
        if max(a, b) < cobrimento:
            balanceada = e.distribuicao == DISTRIBUICAO_BALANCEADA and e.peca == PECA_CANTONEIRA
            a = cobrimento
            b = b if balanceada else cobrimento  # simétrica: os dois filetes iguais
    return a, b


def _entrada_do_apoio(e: EntradaBarraSoldada, forca: float) -> EntradaChapaNoApoio:
    """A chapa de nó soldada no apoio, com as componentes da força da barra (+ tração)."""
    theta = math.radians(e.theta_graus)
    h = forca * math.sin(theta)
    return EntradaChapaNoApoio(
        norma=e.norma,
        combinacao=e.combinacao,
        modo=e.modo,
        tipo_solda=TIPO_FILETE,
        lados=2,
        t_chapa_mm=e.t_no_mm,
        aco_chapa=e.aco_no,
        comprimento_mm=e.l_apoio_mm,
        perna_mm=e.perna_apoio_mm,
        eletrodo=e.eletrodo,
        intermitente=False,
        passo_arredondamento_mm=e.passo_arredondamento_mm,
        n_sd_kN=h,
        v_sd_kN=forca * math.cos(theta),
        m_sd_kNm=h * e.excentricidade_mm / 1000.0,
        minimo_45kN=False,  # já aplicado na força da ligação
        apoio=e.apoio,
        t_apoio_mm=e.t_apoio_mm,
        aco_apoio=e.aco_apoio,
        perfil_apoio=e.perfil_apoio,
        orientacao=e.orientacao,
        perto_da_extremidade=e.perto_da_extremidade,
    )


def _pior_por_nome(*listas: list[Verificacao]) -> list[Verificacao]:
    """Junta as linhas de vários casos (tração e compressão), ficando com a pior de cada nome."""
    ordem: list[str] = []
    pior: dict[str, Verificacao] = {}
    peso = {"NÃO OK": 3, "ALERTA": 2, "OK": 1}
    for linhas in listas:
        for v in linhas:
            atual = pior.get(v.nome)
            if atual is None:
                ordem.append(v.nome)
                pior[v.nome] = v
                continue
            chave_v = (peso.get(v.status, 0), v.aproveitamento or 0.0)
            chave_a = (peso.get(atual.status, 0), atual.aproveitamento or 0.0)
            if chave_v > chave_a:
                pior[v.nome] = v
    return [pior[nome] for nome in ordem]


def _com_prefixo(linhas: list[Verificacao], prefixo: str) -> list[Verificacao]:
    saida = []
    for v in linhas:
        nome = v.nome[0].lower() + v.nome[1:] if v.nome else v.nome
        saida.append(replace(v, nome=f"{prefixo}{nome}"))
    return saida


def calcular_barra_soldada(e: EntradaBarraSoldada) -> ResultadoLigacao:
    _validar_barra(e)
    norma = e.norma
    c = sd.coeficientes(e.combinacao)
    barra = _barra(e)
    pecas = 2 if e.duas_pecas else 1
    forcas, linhas = _forca_da_ligacao(e, barra, c)
    if e.modo == MODO_DIMENSIONAR:
        a, b = _dimensionar_filetes(e, barra, forcas, c)
        linhas.insert(
            0,
            _info(
                "Filetes adotados",
                None,
                "—",
                "",
                f"dorso {_n(a, 0)} mm e borda {_n(b, 0)} mm, perna {_n(e.perna_mm, 1)} mm, "
                f"para {_n(forcas.n_ligacao, 1)} kN ({forcas.origem})",
            ),
        )
    else:
        a, b = e.l_dorso_mm, e.l_borda_mm
    q, r, origem_r = _por_mm_longitudinal(e, barra, c)
    t_menor = min(barra.t, e.t_no_mm)
    largura = barra.largura
    # ------------------------------------------------------------------ filetes da barra
    ef_a = sd.comprimento_efetivo_longitudinal(a, e.perna_mm, norma)
    ef_b = sd.comprimento_efetivo_longitudinal(b, e.perna_mm, norma)
    r_ponta = q * largura if e.solda_na_ponta else 0.0
    f1, f2 = _parcelas(e, barra, forcas.n_peca, r_ponta)
    texto_r = (
        f"{_n(r * 10, 2)} kN/cm por filete (governa {origem_r}; metal da solda "
        f"0,60·f_w·(0,707·perna)/γ_w2 = {_n(q * 10, 2)} kN/cm, sem o aumento: filete longitudinal)"
    )
    if e.distribuicao == DISTRIBUICAO_BALANCEADA and e.peca == PECA_CANTONEIRA:
        texto_f = f"F₁ = N·(C − x̄)/C{' − F₃/2' if r_ponta else ''}, x̄ = {_n(barra.x_barra, 2)} mm"
        texto_f2 = f"F₂ = N·x̄/C{' − F₃/2' if r_ponta else ''}"
    else:
        texto_f = texto_f2 = f"(N{' − F₃' if r_ponta else ''})/2"
    por_peca = f" por peça (N = {_n(forcas.n_peca, 1)} kN)" if pecas == 2 else ""
    if r_ponta:
        ref_filete = sd.ref(norma, "6.2.5.2 c)")
    elif origem_r == "o metal da solda":
        ref_filete = sd.ref(
            norma, f"6.2.5.1, {sd.tabela(norma, 'resistencia')}", vista_na_2025=True
        )
    else:
        ref_filete = sd.ref(norma, "6.5.5")
    for nome, forca, comp, efetivo, texto in (
        ("Filete do dorso (longitudinal)", f1, a, ef_a, texto_f),
        ("Filete da borda (longitudinal)", f2, b, ef_b, texto_f2),
    ):
        extra = sd.texto_comprimento_efetivo(comp, e.perna_mm, norma)
        linhas.append(
            Verificacao(
                nome,
                forca,
                r * efetivo,
                "kN",
                ref_filete,
                f"{texto}{por_peca}; L = {_n(comp, 0)} mm × {texto_r}{extra}"
                + (
                    f"; F₃ = filete da ponta, q·C = {_n(r_ponta, 1)} kN (primeira expressão de "
                    "6.2.5.2 c)"
                    if r_ponta
                    else ""
                ),
            )
        )
    if r_ponta:
        r_long = r * (ef_a + ef_b)
        linhas.append(
            Verificacao(
                "Filetes da barra: grupo longitudinal + transversal",
                forcas.n_peca,
                sd.combinacao_longitudinal_transversal(r_long, r_ponta),
                "kN",
                sd.ref(norma, "6.2.5.2 c)"),
                f"maior entre F_wl + F_wt e 0,85·F_wl + 1,5·F_wt, F_wl = {_n(r_long, 1)} kN, "
                f"F_wt = {_n(r_ponta, 1)} kN (ponta de {_n(largura, 1)} mm){por_peca}",
            )
        )
    # ------------------------------------------------------------------ limites dos filetes
    linhas.extend(sd.limites_do_filete(norma, e.perna_mm, t_menor, barra.t, min(a, b)))
    cobrimento = e.cobrimento_mm if e.cobrimento_mm > 0 else max(a, b)
    linhas.append(
        sd.linha_minimo(
            "Solda: cobrimento da superposição",
            sd.cobrimento_minimo(t_menor),
            cobrimento,
            "mm",
            sd.ref(norma, "6.2.6.2.5"),
            f"≥ 5·t da parte menos espessa (t = {_n(t_menor, 2)} mm) e ≥ 25 mm"
            + ("; cobrimento tomado igual ao maior filete" if e.cobrimento_mm <= 0 else ""),
        )
    )
    if e.peca == PECA_CHAPA and not e.solda_na_ponta:
        linhas.append(
            sd.linha_minimo(
                "Solda: cada filete ≥ distância entre eles",
                largura,
                min(a, b),
                "mm",
                sd.ref(norma, "6.2.6.2.3"),
                "chapa tracionada ligada só por filetes longitudinais nas bordas",
            )
        )
    # ------------------------------------------------------------------ a barra à tração
    linhas.extend(_barra_a_tracao(e, barra, a, b, c))
    # ------------------------------------------------------------------ a chapa de nó
    linhas.extend(_chapa_de_no(e, barra, a, b, forcas, c))
    # ------------------------------------------------------------------ a chapa de nó no apoio
    avisos: list[str] = []
    adotada = replace(e, modo=MODO_VERIFICAR, l_dorso_mm=a, l_borda_mm=b)
    if e.com_apoio:
        entradas = [_entrada_do_apoio(e, forcas.n_ligacao)] if e.n_t_sd_kN > 0 else []
        if e.n_c_sd_kN > 0:
            entradas.append(_entrada_do_apoio(e, -_forca_de_compressao(e)))
        if e.modo == MODO_DIMENSIONAR:  # o maior dos comprimentos achados, para os dois casos
            l_apoio = max(calcular_chapa_no_apoio(ent).adotada.comprimento_mm for ent in entradas)
        else:
            l_apoio = e.l_apoio_mm
        casos = [
            calcular_chapa_no_apoio(replace(ent, modo=MODO_VERIFICAR, comprimento_mm=l_apoio))
            for ent in entradas
        ]
        linhas_apoio = _pior_por_nome(*[list(caso.verificacoes) for caso in casos])
        prefixo = "Chapa de nó no apoio — "
        if e.modo == MODO_DIMENSIONAR:
            linhas.append(
                _info(
                    f"{prefixo}solda adotada",
                    None,
                    "—",
                    "",
                    f"dois filetes de {_n(e.perna_apoio_mm, 1)} mm × {_n(l_apoio, 0)} mm "
                    f"(disponível {_n(e.l_apoio_mm, 0)} mm)",
                )
            )
        linhas.extend(_com_prefixo(linhas_apoio, prefixo))
        for caso in casos:
            avisos.extend(aviso for aviso in caso.avisos if aviso not in avisos)
        adotada = replace(adotada, l_apoio_mm=l_apoio)
    titulo = (
        f"Barra soldada na chapa de nó — {barra.nome}"
        f"{' (duas peças)' if pecas == 2 else ''}, filetes de {_n(e.perna_mm, 1)} mm"
    )
    grandezas = {
        "l_dorso_mm": a,
        "l_borda_mm": b,
        "n_ligacao_kN": forcas.n_ligacao,
        "largura_whitmore_mm": _largura_whitmore(e, barra, a, b),
        "largura_minima_no_mm": forcas.n_ligacao * c.a1 * 1000 / (e.t_no_mm * ACOS[e.aco_no][0]),
    }
    if e.com_apoio:
        grandezas["l_apoio_mm"] = adotada.l_apoio_mm
    return ResultadoLigacao(
        BARRA_SOLDADA, titulo, e, tuple(linhas), grandezas, tuple(avisos), adotada=adotada
    )


def _coeficiente_ct(
    e: EntradaBarraSoldada, barra: _Barra, a: float, b: float
) -> tuple[float, str, bool | None]:
    """C_t (5.2.5) e o texto; o terceiro valor diz se a ligação é permitida.

    Só a 2008 proíbe ligação por ela: C_t < 0,60 na seção aberta e ℓ_w < b na chapa. Na 2025 a
    seção aberta não tem limite (o C_t não precisa ficar abaixo de A_c/A_g) e a chapa tem fórmula
    própria; o ℓ_w ≥ b da chapa continua, mas em 6.2.6.2.3 (linha dos limites dos filetes).
    """
    if e.peca == PECA_CHAPA:
        if e.solda_na_ponta:
            return (
                1.0,
                "5.2.5 a): força transmitida a toda a chapa (filetes nas bordas e na ponta)",
                True,
            )
        largura = barra.largura
        if e.norma == sd.NBR_2025:
            lc = (a + b) / 2
            valor = 3 * lc**2 / (3 * lc**2 + largura**2) * (1 - barra.t / (2 * lc))
            texto = (
                f"5.2.5 d): 3ℓ_c²/(3ℓ_c² + b²)·(1 − t/(2ℓ_c)), ℓ_c = (ℓ_w1 + ℓ_w2)/2 = "
                f"{_n(lc, 1)} mm, b = {_n(largura, 1)} mm, t = {_n(barra.t, 2)} mm"
            )
            return valor, texto, True
        lw = min(a, b)
        if lw >= 2 * largura:
            return 1.0, f"5.2.5 d): ℓ_w = {_n(lw, 0)} ≥ 2b", True
        if lw >= 1.5 * largura:
            return 0.87, f"5.2.5 d): 2b > ℓ_w = {_n(lw, 0)} ≥ 1,5b", True
        if lw >= largura:
            return 0.75, f"5.2.5 d): 1,5b > ℓ_w = {_n(lw, 0)} ≥ b", True
        return 0.75, f"5.2.5 d): ℓ_w = {_n(lw, 0)} < b = {_n(largura, 0)} mm não é permitido", False
    lc = (a + b) / 2
    bruto = 1 - barra.x_barra / lc
    texto = (
        f"5.2.5 c): 1 − e_c/ℓ_c, e_c = x̄ = {_n(barra.x_barra, 2)} mm, ℓ_c = média dos filetes "
        f"longitudinais = {_n(lc, 1)} mm (a favor da segurança)"
    )
    if e.norma == sd.NBR_2025:
        piso = barra.area_conectada / barra.area
        texto += f"; não menor que A_c/A_g = {_n(piso, 3)} (A_c: a aba ligada)"
        return min(1.0, max(bruto, piso)), texto, True
    return min(bruto, 0.90), texto + "; limite 0,90", bruto >= 0.60 - 1e-9


def _barra_a_tracao(
    e: EntradaBarraSoldada, barra: _Barra, a: float, b: float, c: sd.Coeficientes
) -> list[Verificacao]:
    if e.n_t_sd_kN <= 0:
        return []
    fy, fu = ACOS[e.aco_peca]
    pecas = 2 if e.duas_pecas else 1
    n = e.n_t_sd_kN / pecas
    ct_, texto_ct, permitido = _coeficiente_ct(e, barra, a, b)
    ref_ct = sd.ref(e.norma, "5.2.5")
    linhas = [
        Verificacao(
            "Barra: tração (escoamento da seção bruta)",
            n,
            barra.area * fy / c.a1 / 1000,
            "kN",
            sd.ref(e.norma, "5.2.2 a)"),
            f"A_g·f_y/γ_a1, {barra.nome}, A_g = {_n(barra.area, 0)} mm²"
            + (" (por peça)" if pecas == 2 else ""),
        ),  # fmt: skip
        Verificacao(
            "Barra: tração (ruptura da seção líquida)",
            n,
            ct_ * barra.area * fu / c.a2 / 1000,
            "kN",
            sd.ref(e.norma, "5.2.2 b), 5.2.4.2 e 5.2.5"),
            f"A_e·f_u/γ_a2, A_e = C_t·A_n, A_n = A_g (sem furos, 5.2.4.2), C_t = {_n(ct_, 3)} — "
            f"{texto_ct}",
        ),  # fmt: skip
    ]
    if permitido is not True:
        linhas.append(
            _limite(
                "Barra: ligação permitida pelo C_t",
                permitido,
                ref_ct,
                "C_t < 0,60 não é permitido (5.2.5 c da 2008): alongue os filetes"
                if e.peca == PECA_CANTONEIRA
                else "cada filete precisa ter pelo menos a largura da chapa (5.2.5 d da 2008)",
            )
        )
    return linhas


def _largura_whitmore(e: EntradaBarraSoldada, barra: _Barra, a: float, b: float) -> float:
    largura = barra.largura + (a + b) * TAN_30
    return min(largura, e.largura_no_mm) if e.largura_no_mm > 0 else largura


def _chapa_de_no(
    e: EntradaBarraSoldada, barra: _Barra, a: float, b: float, forcas: _Forcas, c: sd.Coeficientes
) -> list[Verificacao]:
    fy, fu = ACOS[e.aco_no]
    t = e.t_no_mm
    norma = e.norma
    bruta = barra.largura + (a + b) * TAN_30
    bw = _largura_whitmore(e, barra, a, b)
    limitada = e.largura_no_mm > 0 and e.largura_no_mm < bruta
    area = bw * t
    texto_w = (
        f"seção de Whitmore b_W = C + (L_dorso + L_borda)·tg 30° = {_n(bruta, 1)} mm"
        + (f", limitada à largura da chapa {_n(e.largura_no_mm, 1)} mm" if limitada else "")
        + f", t = {_n(t, 2)} mm"
    )
    minima = forcas.n_ligacao * c.a1 * 1000 / (t * fy)
    linhas: list[Verificacao] = []
    if e.n_t_sd_kN > 0:
        linhas.append(
            Verificacao(
                "Chapa de nó: tração na seção de Whitmore (escoamento)",
                forcas.n_ligacao,
                area * fy / c.a1 / 1000,
                "kN",
                sd.ref(norma, "6.5.3 a)"),
                f"A_g·f_y/γ_a1; {texto_w}; largura mínima pelo escoamento N·γ_a1/(t·f_y) = "
                f"{_n(minima, 1)} mm",
            )  # fmt: skip
        )
        linhas.append(
            Verificacao(
                "Chapa de nó: tração na seção de Whitmore (ruptura)",
                forcas.n_ligacao,
                area * fu / c.a2 / 1000,
                "kN",
                sd.ref(norma, "6.5.3 b)"),
                f"A_e·f_u/γ_a2, A_e = A_g (sem furos); {texto_w}",
            )  # fmt: skip
        )
        agv = t * (a + b)
        ant = t * barra.largura
        rn = min(0.60 * fu * agv + fu * ant, 0.60 * fy * agv + fu * ant)
        linhas.append(
            Verificacao(
                "Chapa de nó: colapso por rasgamento",
                forcas.n_ligacao,
                rn / c.a2 / 1000,
                "kN",
                sd.ref(norma, "6.5.6"),
                f"(0,60·f_u·A_nv + C_ts·f_u·A_nt)/γ_a2 ≤ (0,60·f_y·A_gv + C_ts·f_u·A_nt)/γ_a2, "
                f"A_gv = A_nv = t·(L_dorso + L_borda) = {_n(agv, 0)} mm², A_nt = t·C = {_n(ant, 0)} mm², "
                "C_ts = 1,0",
            )  # fmt: skip
        )
    if e.n_c_sd_kN > 0:
        n_c = _forca_de_compressao(e)
        raio = t / math.sqrt(12)
        esbeltez = e.k_no * e.l_livre_no_mm / raio
        if esbeltez <= 25:
            resistencia = area * fy / c.a1 / 1000
            texto = f"KL/r = {_n(esbeltez, 1)} ≤ 25: A_g·f_y/γ_a1 (6.5.4 a)"
            item = "6.5.4 a)"
        else:
            lambda_0 = esbeltez / math.pi * math.sqrt(fy / sd.E_ACO)
            chi = nb.fator_chi(lambda_0)
            resistencia = chi * area * fy / c.a1 / 1000
            texto = (
                f"KL/r = {_n(esbeltez, 1)} > 25: χ·A_g·f_y/γ_a1 pelo item 5.3, λ₀ = {_n(lambda_0, 3)}, "
                f"χ = {_n(chi, 3)}, " + ("A_ef = A_g (5.3.4)" if norma == sd.NBR_2025 else "Q = 1")
            )
            item = "6.5.4 b) e item 5.3"
        linhas.append(
            Verificacao(
                "Chapa de nó: compressão na seção de Whitmore",
                n_c,
                resistencia,
                "kN",
                sd.ref(norma, item),
                f"{texto}; K = {_n(e.k_no, 2)}, L = {_n(e.l_livre_no_mm, 0)} mm, r = t/√12; {texto_w}",
            )  # fmt: skip
        )
    return linhas


# =============================================================================================
# Figuras
# =============================================================================================
_ABA_SALIENTE = "#9ca3af"  # a aba da cantoneira que sai da chapa de nó (vista de topo)


def _envoltoria(pontos: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Fecho convexo (cadeia monótona), para o contorno da chapa de nó."""
    pts = sorted(set(pontos))
    if len(pts) <= 2:
        return pts

    def giro(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    baixo: list[tuple[float, float]] = []
    for q in pts:
        while len(baixo) >= 2 and giro(baixo[-2], baixo[-1], q) <= 0:
            baixo.pop()
        baixo.append(q)
    cima: list[tuple[float, float]] = []
    for q in reversed(pts):
        while len(cima) >= 2 and giro(cima[-2], cima[-1], q) <= 0:
            cima.pop()
        cima.append(q)
    return baixo[:-1] + cima[:-1]


def _corta_na_face_do_apoio(poligono: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """A parte do polígono com x ≥ 0: a chapa de nó termina na face do apoio, não a atravessa."""
    saida: list[tuple[float, float]] = []
    for i, p in enumerate(poligono):
        q = poligono[(i + 1) % len(poligono)]
        if p[0] >= 0:
            saida.append(p)
        if (p[0] >= 0) != (q[0] >= 0):
            t = p[0] / (p[0] - q[0])
            saida.append((0.0, p[1] + t * (q[1] - p[1])))
    return saida


def figura_chapa_no_apoio(e: EntradaChapaNoApoio, giro_graus: float = 0.0) -> ImagemDiagrama:
    """Vista lateral (a junta, com os segmentos de solda), corte (filete ou penetração) e legenda.

    ``giro_graus`` gira só a vista lateral (anti-horário), para ela ficar como está na estrutura;
    o corte é um detalhe da solda e fica de pé.
    """
    giro = angulo_do_giro(giro_graus)
    largura_px, altura_px = 980, 440
    imagem = Image.new("RGB", (largura_px * _ESC, altura_px * _ESC), "#ffffff")
    dr = ImageDraw.Draw(imagem)
    fonte = _fonte(12 * _ESC)
    comprimento = e.comprimento_mm
    intermitente = e.intermitente and e.tipo_solda == TIPO_FILETE
    trechos = (
        _segmentos_da_linha(comprimento, e.segmento_mm, e.n_segmentos)
        if intermitente
        else [(0.0, comprimento)]
    )
    # ------------------------------------------------------------------ vista lateral
    balanco = 0.9 * comprimento
    x_apoio, topo, base = -0.18 * comprimento, -0.12 * comprimento, 1.12 * comprimento
    seta_mm = 0.35 * comprimento  # a seta da força normal, para fora da chapa
    tela = _Tela(
        [
            (x_apoio - 0.1 * comprimento, topo),
            (balanco + seta_mm + 0.05 * comprimento, base),
        ],
        (80, 80, 450, 400),
        giro,
    )
    apoio = [tela(x_apoio, topo), tela(0, topo), tela(0, base), tela(x_apoio, base)]
    dr.polygon(apoio, fill=_APOIO, outline=_LINHA, width=2 * _ESC)
    chapa = [tela(0, 0), tela(balanco, 0), tela(balanco, comprimento), tela(0, comprimento)]
    dr.polygon(chapa, fill=_CHAPA_AZUL, outline=_LINHA, width=2 * _ESC)
    for a, b in trechos:
        dr.line([tela(0, a), tela(0, b)], fill=_SOLDA, width=7 * _ESC)
    esquerda, direita = tela.direcao(-1.0, 0.0), tela.direcao(1.0, 0.0)
    baixo = tela.direcao(0.0, 1.0)
    _cota_alinhada(
        dr, tela(x_apoio, 0), tela(x_apoio, comprimento), esquerda, _n(comprimento, 0), 14 * _ESC
    )
    if intermitente:
        a, b = trechos[0]
        _rotulo(
            dr, tela(0, (a + b) / 2), direita, 10 * _ESC, f"segmento {_n(b - a, 0)}", _SOLDA, fonte
        )
    if e.n_sd_kN:
        perto = _mais(tela(balanco, comprimento / 2), direita, 8 * _ESC)
        longe = tela(balanco + seta_mm, comprimento / 2)
        if e.n_sd_kN > 0:
            _seta_px(dr, perto, longe, _FORCA)
        else:
            _seta_px(dr, longe, perto, _FORCA)
        _rotulo(dr, longe, direita, 6 * _ESC, f"N = {_n(e.n_sd_kN, 1)} kN", _FORCA, fonte)
    if e.v_sd_kN:
        alto, embaixo = (
            tela(balanco * 0.6, comprimento * 0.25),
            tela(balanco * 0.6, comprimento * 0.75),
        )
        if e.v_sd_kN > 0:
            _seta_px(dr, alto, embaixo, _FORCA)
        else:
            _seta_px(dr, embaixo, alto, _FORCA)
        _rotulo(dr, embaixo, direita, 8 * _ESC, f"V = {_n(e.v_sd_kN, 1)} kN", _FORCA, fonte)
    if e.m_sd_kNm:
        _rotulo(
            dr, tela(balanco * 0.3, comprimento), baixo, 12 * _ESC,
            f"M = {_n(e.m_sd_kNm, 2)} kN·m", _FORCA, fonte,
        )  # fmt: skip
    dr.text((80 * _ESC, 62 * _ESC), "Vista lateral", fill=_COTA, font=fonte)
    # ------------------------------------------------------------------ corte
    t = e.t_chapa_mm
    escala = min(90 * _ESC / max(t, 1.0), 10 * _ESC)
    face, meio = 560 * _ESC, 250 * _ESC
    meia = t / 2 * escala
    dr.rectangle(
        [face - 24 * _ESC, meio - 110 * _ESC, face, meio + 110 * _ESC],
        fill=_APOIO,
        outline=_LINHA,
        width=2 * _ESC,
    )
    dr.rectangle(
        [face, meio - meia, face + 150 * _ESC, meio + meia],
        fill=_CHAPA_AZUL,
        outline=_LINHA,
        width=2 * _ESC,
    )
    if e.tipo_solda == TIPO_FILETE:
        perna = max(e.perna_mm * escala, 4 * _ESC)
        for s in (-1, 1) if e.lados == 2 else (-1,):
            borda = meio + s * meia
            dr.polygon(
                [(face, borda), (face + perna, borda), (face, borda + s * perna)], fill=_SOLDA
            )
        texto_corte = f"{e.lados} filete(s) de {_n(e.perna_mm, 1)} mm"
    elif e.tipo_solda == TIPO_TOTAL:
        dr.polygon(
            [(face, meio - meia), (face + meia * 1.1, meio - meia), (face, meio + meia)],
            fill=_SOLDA,
        )
        dr.polygon(
            [(face, meio + meia), (face + meia * 1.1, meio + meia), (face, meio - meia)],
            fill=_SOLDA,
        )
        texto_corte = "penetração total"
    else:
        prof = e.profundidade_mm * escala
        for s in (-1, 1) if e.lados == 2 else (-1,):
            borda = meio + s * meia
            dr.polygon(
                [(face, borda), (face + prof * 0.9, borda), (face, borda - s * prof)], fill=_SOLDA
            )
        texto_corte = f"penetração parcial, S = {_n(e.profundidade_mm, 1)} mm"
    dr.text((face - 24 * _ESC, meio - 130 * _ESC), "Corte", fill=_COTA, font=fonte)
    dr.text(
        (face - 24 * _ESC, meio + 124 * _ESC),
        f"chapa t = {_n(t, 1)} mm\n{texto_corte}",
        fill=_TEXTO,
        font=_fonte(11 * _ESC),
    )
    titulo = "Chapa soldada no apoio"
    rotulo = TIPOS_DE_SOLDA[e.tipo_solda].lower() + (" intermitente" if intermitente else "")
    if intermitente:
        cordao = f"{len(trechos)} × {_n(trechos[0][1] - trechos[0][0], 0)} mm por linha"
    else:
        cordao = f"{_n(comprimento, 0)} mm"
    apoio_texto = (
        f"Apoio: {e.perfil_apoio}" if e.apoio == APOIO_PERFIL and e.perfil_apoio else "Apoio"
    )
    itens: list[tuple[str, str, str]] = [
        ("linha", _SOLDA, f"Solda: {cordao}"),
        ("area", _CHAPA_AZUL, f"Chapa soldada ({_n(t, 1)} mm)"),
        ("area", _APOIO, apoio_texto),
        ("seta", _FORCA, "Forças de cálculo na chapa"),
    ]
    if giro:
        itens += [("", _COTA, "Vista lateral girada"), ("", _COTA, texto_do_giro(giro))]
    _legenda(dr, 740 * _ESC, 110 * _ESC, itens)
    dr.text((18 * _ESC, 14 * _ESC), titulo, fill=_TEXTO, font=_fonte(16 * _ESC))
    dr.text(
        (18 * _ESC, 38 * _ESC),
        f"Junta em T, {rotulo} ({e.eletrodo}). Cotas em mm.",
        fill=_COTA,
        font=_fonte(11 * _ESC),
    )
    legenda = (
        f"Chapa de {_n(t, 1)} mm soldada no apoio: {rotulo}, "
        + (
            f"{len(trechos)} segmento(s) de {_n(trechos[0][1] - trechos[0][0], 0)} mm por linha em "
            if intermitente
            else ""
        )
        + f"{_n(comprimento, 0)} mm de junta."
    )
    return ImagemDiagrama(titulo, legenda, _png(imagem, largura_px, altura_px), largura_px, altura_px)  # fmt: skip


@dataclass(frozen=True)
class _DesenhoDaBarra:
    """A geometria da figura da barra na chapa de nó, em mm (x para a direita, y para baixo).

    O apoio fica à esquerda, com a face soldada em x = 0. A chapa de nó cabe os filetes e a seção
    de Whitmore, só encosta no apoio no trecho soldado (0 ≤ y ≤ ℓ_apoio) e a ponta da barra fica
    a ``folga`` da face.
    """

    barra: _Barra
    ux: float  # ao longo da barra, saindo do apoio (y para baixo)
    uy: float
    y_trabalho: float  # onde o eixo da barra encontra a face do apoio
    folga: float
    s_ponta: float  # a ponta da barra, ao longo do eixo a partir da face
    s_corte: float  # onde a barra é interrompida no desenho
    k: float  # o "Z" da linha de interrupção
    chapa: tuple[tuple[float, float], ...]
    contorno_da_barra: tuple[tuple[float, float], ...]
    apoio: tuple[tuple[float, float], ...]
    largura_apoio: float
    enquadrar: tuple[
        tuple[float, float], ...
    ]  # tudo o que precisa caber, chamadas e cotas inclusive

    def mm(self, s: float, n: float) -> tuple[float, float]:
        """s ao longo do eixo a partir da face do apoio, n do dorso para a borda (mm)."""
        d = n - self.barra.x_barra  # o eixo passa pelo centro geométrico, a x̄ do dorso
        return (s * self.ux + d * self.uy, self.y_trabalho + s * self.uy - d * self.ux)


def _desenho_da_barra(e: EntradaBarraSoldada) -> _DesenhoDaBarra:
    barra = _barra(e)
    a, b, c_, xb = e.l_dorso_mm, e.l_borda_mm, barra.largura, barra.x_barra
    sobre = max(a, b)
    abre_a, abre_b = a * TAN_30, b * TAN_30
    theta = math.radians(e.theta_graus) if e.com_apoio else math.pi / 2
    ux, uy = math.sin(theta), math.cos(theta)
    l_apoio = e.l_apoio_mm if e.com_apoio else 0.0
    folga = max(15.0, 2.0 * e.t_no_mm)  # da barra e da chapa (fora da solda) até a face do apoio
    m_lado = max(10.0, 2.5 * e.perna_mm)  # chapa além das bordas da barra (onde ficam os filetes)
    m_fim = max(15.0, 0.12 * sobre)  # chapa além do fim dos filetes
    m_w = max(8.0, 0.06 * sobre)  # chapa além das pontas da seção de Whitmore
    if e.com_apoio:
        # a chapa só encosta no apoio no trecho soldado: a ponta da barra e o canto da chapa
        # junto da seção de Whitmore ficam a ``folga`` da face
        s_ponta = max((folga + xb * uy) / ux, m_w + (folga + (abre_a + m_w + xb) * uy) / ux)
    else:
        s_ponta = 0.0
    s_fim = s_ponta + sobre + m_fim
    s_corte = s_fim + 0.45 * sobre + 25.0
    k = 0.12 * c_ + 3.0
    g = _DesenhoDaBarra(
        barra, ux, uy, l_apoio / 2 + e.excentricidade_mm if e.com_apoio else 0.0, folga,
        s_ponta, s_corte, k, (), (), (), 0.0, (),
    )  # fmt: skip
    mm = g.mm
    pontos_da_chapa = [
        mm(s_ponta - m_w, -abre_a - m_w),
        mm(s_ponta - m_w, c_ + abre_b + m_w),
        mm(s_fim, -m_lado),
        mm(s_fim, c_ + m_lado),
    ]
    if e.com_apoio:
        pontos_da_chapa += [(0.0, 0.0), (0.0, l_apoio)]
    chapa = _envoltoria(pontos_da_chapa)
    if e.com_apoio:
        chapa = _corta_na_face_do_apoio(chapa)
    contorno_da_barra = [
        mm(s_ponta, 0), mm(s_corte, 0), mm(s_corte, 0.38 * c_), mm(s_corte + k, 0.46 * c_),
        mm(s_corte - k, 0.54 * c_), mm(s_corte, 0.62 * c_), mm(s_corte, c_), mm(s_ponta, c_),
    ]  # fmt: skip
    margem = 0.3 * sobre + 25.0  # espaço para as chamadas, fora da chapa
    enquadrar = [
        *chapa,
        *contorno_da_barra,
        mm(s_corte + k + 0.3 * sobre + 38.0, xb),  # a seta da força
        mm(s_ponta + 0.6 * a, -abre_a * 0.45 - margem),
        mm(s_ponta + 0.6 * b, c_ + abre_b * 0.45 + margem),
        mm(s_ponta - m_w, -abre_a - m_w - 0.6 * margem),
    ]
    apoio: list[tuple[float, float]] = []
    largura_apoio = 0.0
    if e.com_apoio:
        ys = [y for x, y in chapa if abs(x) < 1e-6] + [0.0, l_apoio]
        alto, baixo = min(ys), max(ys)
        sobra = 0.12 * (baixo - alto) + 12.0
        largura_apoio = max(12.0, 0.06 * s_corte)
        apoio = [
            (-largura_apoio, alto - sobra), (0.0, alto - sobra),
            (0.0, baixo + sobra), (-largura_apoio, baixo + sobra),
        ]  # fmt: skip
        enquadrar += [*apoio, (-largura_apoio - 0.3 * sobre - 20.0, l_apoio / 2)]
    return replace(
        g,
        chapa=tuple(chapa),
        contorno_da_barra=tuple(contorno_da_barra),
        apoio=tuple(apoio),
        largura_apoio=largura_apoio,
        enquadrar=tuple(enquadrar),
    )


def figura_barra_soldada(e: EntradaBarraSoldada, giro_graus: float = 0.0) -> ImagemDiagrama:
    """A barra sobre a chapa de nó: filetes, seção de Whitmore, eixo da barra, apoio e legenda.

    Vista da face da chapa de nó, com o apoio à esquerda e a barra a θ da face (a geometria vem de
    :func:`_desenho_da_barra`). O eixo da barra (a linha da força) passa pelo centro geométrico,
    a x̄ do dorso; na cantoneira, a aba saliente aparece no dorso. Os comprimentos vão por
    chamadas numeradas, com o texto na legenda. ``giro_graus`` gira só o desenho (anti-horário),
    para ficar como está na estrutura.
    """
    giro = angulo_do_giro(giro_graus)
    largura_px, altura_px = 1000, 540
    imagem = Image.new("RGB", (largura_px * _ESC, altura_px * _ESC), "#ffffff")
    dr = ImageDraw.Draw(imagem)
    fonte = _fonte(12 * _ESC)
    g = _desenho_da_barra(e)
    barra, mm = g.barra, g.mm
    a, b, c_, xb = e.l_dorso_mm, e.l_borda_mm, barra.largura, barra.x_barra
    sobre = max(a, b)
    abre_a, abre_b = a * TAN_30, b * TAN_30
    ux, uy, nx, ny = g.ux, g.uy, g.uy, -g.ux  # n: do dorso para a borda
    l_apoio = e.l_apoio_mm if e.com_apoio else 0.0
    y_trabalho, s_ponta, s_corte, k = g.y_trabalho, g.s_ponta, g.s_corte, g.k
    largura_apoio = g.largura_apoio
    chapa_mm, barra_mm, apoio_mm = g.chapa, g.contorno_da_barra, g.apoio
    seta_inicio, seta_fim = s_corte + k + 8.0, s_corte + k + 8.0 + 0.3 * sobre + 20.0
    tela = _Tela(g.enquadrar, (60, 80, 630, 520), giro)
    # ------------------------------------------------------------------ peças
    chapa = [tela(*q) for q in chapa_mm]
    dr.polygon(chapa, fill=_CHAPA_AZUL, outline=_LINHA, width=2 * _ESC)
    apoio = [tela(*q) for q in apoio_mm]
    if apoio:
        dr.polygon(apoio, fill=_APOIO, outline=_LINHA, width=2 * _ESC)
    dr.polygon([tela(*q) for q in barra_mm], fill=_BARRA, outline=_LINHA, width=2 * _ESC)
    if e.peca == PECA_CANTONEIRA:  # a aba que sai da chapa, vista de topo, no dorso
        aba = [mm(s_ponta, 0), mm(s_corte, 0), mm(s_corte, barra.t), mm(s_ponta, barra.t)]
        dr.polygon([tela(*q) for q in aba], fill=_ABA_SALIENTE, outline=_LINHA, width=_ESC)
    # Whitmore: 30° do começo de cada filete (lado da barra) até a ponta, tracejado
    w_dorso, w_borda = tela(*mm(s_ponta, -abre_a)), tela(*mm(s_ponta, c_ + abre_b))
    _tracejado(dr, tela(*mm(s_ponta + a, 0)), w_dorso, _WHITMORE, largura=_ESC, traco=5 * _ESC)
    _tracejado(dr, tela(*mm(s_ponta + b, c_)), w_borda, _WHITMORE, largura=_ESC, traco=5 * _ESC)
    _tracejado(dr, w_dorso, w_borda, _WHITMORE, largura=2 * _ESC)
    # os filetes
    dr.line([tela(*mm(s_ponta, 0)), tela(*mm(s_ponta + a, 0))], fill=_SOLDA, width=7 * _ESC)
    dr.line([tela(*mm(s_ponta, c_)), tela(*mm(s_ponta + b, c_))], fill=_SOLDA, width=7 * _ESC)
    if e.solda_na_ponta:
        dr.line([tela(*mm(s_ponta, 0)), tela(*mm(s_ponta, c_))], fill=_SOLDA, width=7 * _ESC)
    if e.com_apoio:
        dr.line([tela(0, 0), tela(0, l_apoio)], fill=_SOLDA, width=7 * _ESC)
    # ------------------------------------------------------------------ eixo, ângulo e cotas
    ao_longo = tela.direcao(ux, uy)
    inicio_eixo = tela(*mm(0.0, xb)) if e.com_apoio else tela(*mm(s_ponta - 20.0, xb))
    _traco_ponto(dr, inicio_eixo, tela(*mm(s_corte + 2 * k, xb)), _COTA)
    if e.com_apoio:
        trabalho = tela(0.0, y_trabalho)
        dr.ellipse(
            [trabalho[0] - 4 * _ESC, trabalho[1] - 4 * _ESC, trabalho[0] + 4 * _ESC, trabalho[1] + 4 * _ESC],
            fill=_COTA,
        )  # fmt: skip
        meio = _arco_entre(dr, trabalho, 38 * _ESC, tela.direcao(0.0, 1.0), ao_longo, _COTA)
        texto_theta = f"θ = {_n(e.theta_graus, 0)}°"
        _rotulo(dr, trabalho, meio, 50 * _ESC, texto_theta, _COTA, fonte, fundo=True)
        esquerda = tela.direcao(-1.0, 0.0)
        afastamento = largura_apoio * tela.esc + 14 * _ESC
        if e.excentricidade_mm:  # a excentricidade mais perto; a solda por fora dela
            _cota_alinhada(
                dr, tela(0, l_apoio / 2), trabalho, esquerda,
                f"e = {_n(e.excentricidade_mm, 0)}", afastamento,
            )  # fmt: skip
            afastamento += 60 * _ESC
        _cota_alinhada(dr, tela(0, 0), tela(0, l_apoio), esquerda, _n(l_apoio, 0), afastamento)
    # a força na barra, depois da interrupção
    perto, longe = tela(*mm(seta_inicio, xb)), tela(*mm(seta_fim, xb))
    if e.n_t_sd_kN > 0:
        _seta_px(dr, perto, longe, _FORCA)
        if e.n_c_sd_kN > 0:  # tração e compressão: ponta nos dois lados
            _seta_px(dr, longe, perto, _FORCA)
    else:
        _seta_px(dr, longe, perto, _FORCA)
    _rotulo(dr, longe, ao_longo, 8 * _ESC, "N", _FORCA, fonte)
    # ------------------------------------------------------------------ chamadas numeradas
    obstaculos = [chapa, apoio] if apoio else [chapa]
    para_o_dorso, para_a_borda = tela.direcao(-nx, -ny), tela.direcao(nx, ny)
    alvo = tela(*mm(s_ponta + 0.6 * a, 0))
    _chamada(dr, alvo, _fora_de(alvo, para_o_dorso, obstaculos, 26 * _ESC), 1, _SOLDA)
    alvo = tela(*mm(s_ponta + 0.6 * b, c_))
    _chamada(dr, alvo, _fora_de(alvo, para_a_borda, obstaculos, 26 * _ESC), 2, _SOLDA)
    rumo = tela.direcao(-nx + 0.8 * ux, -ny + 0.8 * uy)  # para longe do apoio
    _chamada(dr, w_dorso, _fora_de(w_dorso, rumo, obstaculos, 26 * _ESC), 3, _WHITMORE)
    largura_w = _largura_whitmore(e, barra, a, b)
    itens: list[tuple[str, str, str]] = [
        ("numero:1", _SOLDA, f"Filete do dorso: {_n(a, 0)} mm"),
        ("numero:2", _SOLDA, f"Filete da borda: {_n(b, 0)} mm"),
    ]
    if e.solda_na_ponta:
        itens.append(("linha", _SOLDA, f"Filete na ponta da barra: {_n(c_, 0)} mm"))
    itens.append(("numero:3", _WHITMORE, f"Seção de Whitmore: {_n(largura_w, 0)} mm"))
    if e.com_apoio:
        alvo = tela(0, l_apoio * 0.2)
        rumo = tela.direcao(-0.6, -1.0)
        _chamada(dr, alvo, _fora_de(alvo, rumo, obstaculos, 24 * _ESC), 4, _SOLDA)
        itens.append(
            (
                "numero:4",
                _SOLDA,
                f"Solda no apoio: dois filetes de {_n(e.perna_apoio_mm, 0)} × {_n(l_apoio, 0)} mm",
            )
        )
    # ------------------------------------------------------------------ legenda
    if e.n_t_sd_kN > 0:
        forca = f"N = {_n(e.n_t_sd_kN, 1)} kN de tração"
        if e.n_c_sd_kN > 0:
            forca += f" e {_n(e.n_c_sd_kN, 1)} kN de compressão"
    else:
        forca = f"N = {_n(e.n_c_sd_kN, 1)} kN de compressão"
    itens += [
        ("", _TEXTO, ""),
        ("linha", _SOLDA, f"Cordões de solda (perna {_n(e.perna_mm, 1)} mm na barra)"),
        ("area", _CHAPA_AZUL, f"Chapa de nó ({_n(e.t_no_mm, 1)} mm)"),
        ("area", _BARRA, f"Barra: {barra.nome}"),
    ]
    if e.peca == PECA_CANTONEIRA:
        itens.append(("area", _ABA_SALIENTE, "Aba saliente da cantoneira (no dorso)"))
    if e.com_apoio:
        itens.append(("area", _APOIO, "Apoio"))
    itens += [
        ("tracejado", _WHITMORE, "Seção de Whitmore (30° do começo dos filetes)"),
        ("eixo", _COTA, "Eixo da barra: a linha da força (a x̄ do dorso)"),
        ("seta", _FORCA, forca),
    ]
    if e.com_apoio:
        excentrico = (
            f", excentricidade {_n(e.excentricidade_mm, 0)} mm" if e.excentricidade_mm else ""
        )
        itens.append(
            ("", _TEXTO, f"θ = {_n(e.theta_graus, 0)}° entre a barra e o apoio{excentrico}")
        )
    if giro:
        itens.append(("", _COTA, f"Desenho girado {texto_do_giro(giro)}"))
    _legenda(dr, 660 * _ESC, 84 * _ESC, itens)
    titulo = "Barra soldada na chapa de nó"
    pecas = " (duas peças, uma de cada lado)" if e.duas_pecas else ""
    dr.text((18 * _ESC, 14 * _ESC), titulo, fill=_TEXTO, font=_fonte(16 * _ESC))
    dr.text(
        (18 * _ESC, 38 * _ESC),
        f"{barra.nome}{pecas}; chapa de nó {_n(e.t_no_mm, 1)} mm; filetes de {_n(e.perna_mm, 1)} mm "
        f"({e.eletrodo}). Cotas em mm.",
        fill=_COTA,
        font=_fonte(11 * _ESC),
    )
    legenda = (
        f"{barra.nome}{pecas} na chapa de nó de {_n(e.t_no_mm, 1)} mm: filete do dorso "
        f"{_n(a, 0)} mm, da borda {_n(b, 0)} mm"
        + (", com filete na ponta" if e.solda_na_ponta else "")
        + (f"; chapa de nó soldada no apoio em {_n(l_apoio, 0)} mm" if e.com_apoio else "")
        + "."
    )
    return ImagemDiagrama(titulo, legenda, _png(imagem, largura_px, altura_px), largura_px, altura_px)  # fmt: skip


#: Códigos que o memorial mostra pelo texto.
_ROTULOS_DOS_CODIGOS: dict[str, dict[str, str]] = {
    "modo": MODOS,
    "tipo_solda": TIPOS_DE_SOLDA,
    "apoio": APOIOS,
    "orientacao": ORIENTACOES,
    "peca": PECAS,
    "distribuicao": DISTRIBUICOES,
    "combinacao": sd.COMBINACOES,
}


def _sem_apoio_que_nao_se_aplica(dados: dict[str, Any]) -> None:
    if dados.get("apoio") == APOIO_PERFIL:
        dados.pop("t_apoio_mm", None)
    else:
        for chave in ("perfil_apoio", "orientacao", "perto_da_extremidade"):
            dados.pop(chave, None)


def campos_do_registro(e: EntradaChapaNoApoio | EntradaBarraSoldada) -> dict[str, Any]:
    """Os dados de entrada para o memorial: só os que valem para o caso, com os códigos em texto."""
    dados: dict[str, Any] = {k: getattr(e, k) for k in e.__dataclass_fields__}
    if isinstance(e, EntradaChapaNoApoio):
        if e.tipo_solda != TIPO_FILETE:
            for chave in ("perna_mm", "intermitente", "segmento_mm", "n_segmentos"):
                dados.pop(chave, None)
        if e.tipo_solda != TIPO_PARCIAL:
            dados.pop("profundidade_mm", None)
            dados.pop("descontar_3mm", None)
        if e.tipo_solda == TIPO_TOTAL:
            dados.pop("lados", None)
        if not e.intermitente:
            dados.pop("segmento_mm", None)
            dados.pop("n_segmentos", None)
        elif e.modo == MODO_DIMENSIONAR:
            dados.pop("n_segmentos", None)
        _sem_apoio_que_nao_se_aplica(dados)
    else:
        if e.peca == PECA_CANTONEIRA:
            dados.pop("largura_mm", None)
            dados.pop("t_peca_mm", None)
        else:
            dados.pop("cantoneira", None)
            dados.pop("distribuicao", None)
        if e.modo == MODO_DIMENSIONAR:
            dados.pop("l_dorso_mm", None)
            dados.pop("l_borda_mm", None)
        if e.n_c_sd_kN <= 0:
            dados.pop("k_no", None)
            dados.pop("l_livre_no_mm", None)
        if e.com_apoio:
            _sem_apoio_que_nao_se_aplica(dados)
        else:
            for chave in (
                "theta_graus", "l_apoio_mm", "perna_apoio_mm", "excentricidade_mm", "apoio",
                "t_apoio_mm", "aco_apoio", "perfil_apoio", "orientacao", "perto_da_extremidade",
            ):  # fmt: skip
                dados.pop(chave, None)
    if e.modo == MODO_VERIFICAR:
        dados.pop("passo_arredondamento_mm", None)
    for chave, rotulos in _ROTULOS_DOS_CODIGOS.items():
        if chave in dados:
            dados[chave] = rotulos.get(str(dados[chave]), dados[chave])
    if "lados" in dados:
        dados["lados"] = "dois" if dados["lados"] == 2 else "um"
    return dados


ENTRADAS: dict[str, type] = {
    CHAPA_NO_APOIO: EntradaChapaNoApoio,
    BARRA_SOLDADA: EntradaBarraSoldada,
}


def calcular(entrada: EntradaChapaNoApoio | EntradaBarraSoldada) -> ResultadoLigacao:
    if isinstance(entrada, EntradaChapaNoApoio):
        return calcular_chapa_no_apoio(entrada)
    return calcular_barra_soldada(entrada)


def figura(
    entrada: EntradaChapaNoApoio | EntradaBarraSoldada, giro_graus: float = 0.0
) -> ImagemDiagrama:
    """O desenho da ligação; ``giro_graus`` gira só o desenho (anti-horário)."""
    if isinstance(entrada, EntradaChapaNoApoio):
        return figura_chapa_no_apoio(entrada, giro_graus)
    return figura_barra_soldada(entrada, giro_graus)
