"""Longarina da escada em grade pelo núcleo de pórtico plano: uma por lance, inclinada ou dobrada.

Cada lance da escada (:mod:`core.escada_lances`) tem a sua longarina. O modelo é plano
(:mod:`core.portico_plano`), com a geometria do lance:

* trecho **inclinado** pela linha dos bocéis: ``n·b`` na horizontal (ou a distância informada) e o
  desnível do lance na vertical — ``α = atan(h/b)``;
* trechos **horizontais** opcionais no **pé** e no **topo** (a longarina que continua sob o patamar
  ou a plataforma, a "barra dobrada" das escadas): o nó da dobra é rígido;
* **apoios** nas duas pontas: pino (segura vertical e horizontal), rolete (só a vertical, como o
  furo oblongo) ou engaste. Com pino nas duas pontas e longarina dobrada aparece o **empuxo
  horizontal**; numa longarina reta pino–pino com carga vertical ele é nulo.

Cargas características por longarina (metade da largura de cada degrau):

* **Q** — sobrecarga ``q`` (kN/m² em planta) × largura/2, por metro **horizontal**; nos trechos
  horizontais, com a largura do patamar;
* **G** — peso dos degraus (meio degrau a cada piso ``b``, por metro horizontal), guarda-corpo e
  peso próprio do perfil (por metro de barra, levados à horizontal por ``1/cos α``) e, nos trechos
  horizontais, o piso do patamar.

Combinações: ELU ``γg·G + γq·Q`` (os coeficientes da página do degrau) e ELS ``G + Q``. Cada
trecho é verificado pelo mesmo motor da verificação das barras do modelo
(:func:`core.verificacao_barras.verificar_barra_com_esforcos`: NBR 8800 5.5.1.2 com todos os modos
de flambagem, FLT/FLM/FLA, cortante e o limite de esbeltez do critério Anglo), com ``L_x`` = o
trecho e ``L_y = L_b`` = a distância entre degraus ao longo da barra (cada degrau trava a
longarina), ou o valor informado. A flecha é a do ELS, perpendicular à barra e medida em relação
à reta entre as pontas deslocadas, limitada a ``L/350`` (NBR 8800 Anexo C, vigas de piso; Anglo
Tabela 3, principais).

Lances com a mesma geometria (espelhos, piso, larguras de patamar) saem numa longarina só.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from core import degrau_escada as de
from core import escada_lances as el
from core import portico_plano as pp
from core import section_catalog as sc
from core import verificacao_barras as vb
from core.verificacao import Verificacao, status_geral

G = 9.80665
LIMITE_FLECHA = 350.0  # NBR 8800 Anexo C — vigas de piso; Anglo Tabela 3 — principais
PINO, ROLETE, ENGASTE = "pino", "rolete", "engaste"
APOIOS = {
    PINO: "Pino (segura na vertical e na horizontal)",
    ROLETE: "Rolete (só na vertical: furo oblongo, desliza)",
    ENGASTE: "Engaste (base soldada ou rígida)",
}
ELU = "ELU normal"
ELS = "ELS (G + Q)"
TRECHO_PE, TRECHO_INCLINADO, TRECHO_TOPO = "pé", "inclinada", "topo"


class LongarinaInvalida(ValueError):
    """Dado que o cálculo não aceita; a mensagem diz o que corrigir."""


@dataclass(frozen=True)
class EntradaLongarina:
    perfil: str = 'U 8" x 17,10'
    aco: str = "ASTM A36"
    vao_horizontal_m: float | None = None  # trecho inclinado do lance mais longo; vazio = n·b
    guarda_corpo_kN_m: float = 0.40
    trecho_pe_m: float = 0.0
    trecho_topo_m: float = 0.0
    apoio_pe: str = PINO
    apoio_topo: str = PINO
    piso_patamar_kN_m2: float = 0.40
    lb_m: float | None = None  # vazio = distância entre degraus ao longo da barra
    norma: str = "NBR8800_2024"


@dataclass(frozen=True)
class CargasDaLongarina:
    """Cargas características numa longarina (kN/m)."""

    sobrecarga_kN_m: float  # vertical, por metro horizontal, no trecho inclinado
    degraus_kN_m: float  # vertical, por metro horizontal
    guarda_corpo_kN_m: float  # por metro de barra
    peso_proprio_kN_m: float  # por metro de barra
    sobrecarga_topo_kN_m: float
    piso_topo_kN_m: float
    sobrecarga_pe_kN_m: float
    piso_pe_kN_m: float

    def permanente_inclinada(self, cos_a: float) -> float:
        """G no trecho inclinado, por metro horizontal."""
        return self.degraus_kN_m + (self.guarda_corpo_kN_m + self.peso_proprio_kN_m) / cos_a

    @property
    def permanente_topo(self) -> float:
        return self.piso_topo_kN_m + self.guarda_corpo_kN_m + self.peso_proprio_kN_m

    @property
    def permanente_pe(self) -> float:
        return self.piso_pe_kN_m + self.guarda_corpo_kN_m + self.peso_proprio_kN_m


@dataclass(frozen=True)
class TrechoVerificado:
    barra: str
    comprimento_m: float
    angulo_graus: float
    lb_m: float
    resultado: vb.ResultadoDaBarra
    flecha_mm: float  # ELS, perpendicular, em relação à reta entre as pontas
    limite_flecha_mm: float
    deslocamento_vertical_mm: float  # ELS, maior |dy| no trecho

    @property
    def linha_da_flecha(self) -> Verificacao:
        return Verificacao(
            f"Flecha (G + Q) ≤ L/{LIMITE_FLECHA:.0f}",
            abs(self.flecha_mm),
            self.limite_flecha_mm,
            "mm",
            "NBR 8800 Anexo C; Anglo Tab. 3",
            f"L = {de.numero_pt(self.comprimento_m, 3)} m; flecha em relação à reta entre as pontas; "
            f"deslocamento vertical máximo {de.numero_pt(self.deslocamento_vertical_mm, 2)} mm",
        )

    @property
    def verificacoes(self) -> tuple[Verificacao, ...]:
        return (*self.resultado.linhas, self.linha_da_flecha)


@dataclass(frozen=True)
class LongarinaDoLance:
    lances: tuple[int, ...]  # os lances com esta mesma longarina
    lance: el.Lance
    vao_horizontal_m: float
    vao_informado: bool
    desnivel_m: float
    alfa_graus: float
    cargas: CargasDaLongarina
    gamma_g: float
    gamma_q: float
    porticos: dict[str, pp.Portico]  # "G", "Q", ELU, ELS
    resultados: dict[str, pp.ResultadoPortico]
    trechos: tuple[TrechoVerificado, ...]

    @property
    def titulo(self) -> str:
        if len(self.lances) == 1:
            return f"Longarina do lance {self.lances[0]}"
        return "Longarina dos lances " + ", ".join(str(n) for n in self.lances)

    @property
    def elu(self) -> pp.ResultadoPortico:
        return self.resultados[ELU]

    @property
    def els(self) -> pp.ResultadoPortico:
        return self.resultados[ELS]

    @property
    def vao_inclinado_m(self) -> float:
        return math.hypot(self.vao_horizontal_m, self.desnivel_m)

    @property
    def verificacoes(self) -> tuple[Verificacao, ...]:
        """Todas as linhas, com o trecho no nome (para o registro e o memorial)."""
        varios = len(self.trechos) > 1
        saida = []
        for t in self.trechos:
            for v in t.verificacoes:
                nome = f"{self.titulo}" + (f" ({t.barra})" if varios else "") + f" — {v.nome}"
                saida.append(
                    Verificacao(
                        nome,
                        v.solicitante,
                        v.resistente,
                        v.unidade,
                        v.referencia,
                        v.formula,
                        v.status,
                        v.aproveitamento,
                        v.tipo,
                    )
                )
        return tuple(saida)

    @property
    def decisivas(self) -> tuple[Verificacao, ...]:
        """Só as linhas com critério (OK, ALERTA, NÃO OK): as que o memorial lista."""
        return tuple(v for v in self.verificacoes if v.status in ("OK", "ALERTA", "NÃO OK"))

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

    def reacoes(self, caso: str) -> tuple[pp.Reacao, ...]:
        return self.resultados[caso].reacoes


@dataclass(frozen=True)
class ResultadoLongarina:
    entrada: EntradaLongarina
    longarinas: tuple[LongarinaDoLance, ...]
    avisos: tuple[str, ...] = field(default_factory=tuple)

    @property
    def verificacoes(self) -> tuple[Verificacao, ...]:
        return tuple(v for lg in self.longarinas for v in lg.verificacoes)

    @property
    def decisivas(self) -> tuple[Verificacao, ...]:
        return tuple(v for lg in self.longarinas for v in lg.decisivas)

    @property
    def status(self) -> str:
        return status_geral(list(self.verificacoes))

    @property
    def aproveitamento_maximo(self) -> float:
        return max((lg.aproveitamento_maximo for lg in self.longarinas), default=0.0)

    @property
    def governante(self) -> LongarinaDoLance:
        return max(self.longarinas, key=lambda lg: lg.aproveitamento_maximo)


def _apoio(no: str, tipo: str) -> pp.Apoio:
    if tipo == PINO:
        return pp.pino(no)
    if tipo == ROLETE:
        return pp.rolete(no)
    if tipo == ENGASTE:
        return pp.engaste(no)
    raise LongarinaInvalida(f"Apoio desconhecido: {tipo!r}.")


def _validar(e: EntradaLongarina) -> None:
    if e.guarda_corpo_kN_m < 0 or e.piso_patamar_kN_m2 < 0:
        raise LongarinaInvalida(
            "O peso do guarda-corpo e o do piso do patamar não podem ser negativos."
        )
    if e.trecho_pe_m < 0 or e.trecho_topo_m < 0:
        raise LongarinaInvalida("Os trechos horizontais não podem ser negativos.")
    if e.vao_horizontal_m is not None and e.vao_horizontal_m <= 0:
        raise LongarinaInvalida("A distância horizontal informada precisa ser maior que zero.")
    if e.lb_m is not None and e.lb_m <= 0:
        raise LongarinaInvalida("O comprimento destravado informado precisa ser maior que zero.")
    if e.apoio_pe not in APOIOS or e.apoio_topo not in APOIOS:
        raise LongarinaInvalida("Escolha o apoio do pé e o do topo entre pino, rolete e engaste.")
    if e.apoio_pe == ROLETE and e.apoio_topo == ROLETE:
        raise LongarinaInvalida(
            "Com rolete nas duas pontas a longarina desliza na horizontal: use pino ou engaste em "
            "pelo menos uma delas."
        )
    if e.aco not in vb.ACOS:
        raise LongarinaInvalida(f"Aço desconhecido: {e.aco!r}.")


def _geometria(
    lance: el.Lance, e: EntradaLongarina, vao_h: float
) -> tuple[tuple[pp.No, ...], list[tuple[str, str, str]]]:
    """Nós (A, B, …, da ponta do pé à do topo) e trechos (nome, nó i, nó j), em metros."""
    desnivel = lance.altura_mm / 1000.0
    pontos: list[tuple[float, float]] = []
    trechos: list[str] = []
    if e.trecho_pe_m > 0:
        pontos.append((-e.trecho_pe_m, 0.0))
        trechos.append(TRECHO_PE)
    pontos += [(0.0, 0.0), (vao_h, desnivel)]
    trechos.append(TRECHO_INCLINADO)
    if e.trecho_topo_m > 0:
        pontos.append((vao_h + e.trecho_topo_m, desnivel))
        trechos.append(TRECHO_TOPO)
    nomes = [chr(ord("A") + k) for k in range(len(pontos))]
    nos = tuple(pp.No(n, x, y) for n, (x, y) in zip(nomes, pontos, strict=True))
    return nos, [(t, nomes[k], nomes[k + 1]) for k, t in enumerate(trechos)]


def _portico(
    nos: tuple[pp.No, ...],
    trechos: Sequence[tuple[str, str, str]],
    secao: pp.Secao,
    e: EntradaLongarina,
    cargas_por_trecho: dict[str, float],
    nome_da_carga: str,
) -> pp.Portico:
    return pp.Portico(
        nos=nos,
        barras=tuple(pp.Barra(t, i, j, secao) for t, i, j in trechos),
        apoios=(_apoio(nos[0].nome, e.apoio_pe), _apoio(nos[-1].nome, e.apoio_topo)),
        cargas_distribuidas=tuple(
            pp.CargaDistribuida(
                t, -cargas_por_trecho[t], direcao=pp.GLOBAL_Y_PROJETADA, nome=nome_da_carga
            )
            for t, _i, _j in trechos
            if cargas_por_trecho[t] > 0
        ),
    )


def _longarina_do_lance(
    r: de.ResultadoEscada,
    esc: el.EscadaComPatamares,
    lance: el.Lance,
    numeros: tuple[int, ...],
    e: EntradaLongarina,
    vao_informado: float | None,
) -> LongarinaDoLance:
    entrada = r.entrada
    perfil = sc.obter_perfil(e.perfil)
    secao = pp.secao_de_perfil(e.perfil)
    vao_h = vao_informado if vao_informado else lance.vao_longarina_mm / 1000.0
    desnivel = lance.altura_mm / 1000.0
    if lance.n_espelhos < 2 or desnivel <= 0:
        raise LongarinaInvalida(
            f"O lance {lance.numero} tem um espelho só: não há longarina inclinada para calcular."
        )
    cos_a = vao_h / math.hypot(vao_h, desnivel)
    largura = lance.largura_mm / 1000.0
    acima = esc.patamares[lance.numero - 1] if lance.numero - 1 < len(esc.patamares) else None
    abaixo = esc.patamares[lance.numero - 2] if lance.numero >= 2 else None
    largura_topo = (acima.largura_mm if acima else lance.largura_mm) / 1000.0
    largura_pe = (abaixo.largura_mm if abaixo else lance.largura_mm) / 1000.0
    q, piso = entrada.q_kN_m2, e.piso_patamar_kN_m2
    cargas = CargasDaLongarina(
        sobrecarga_kN_m=q * largura / 2,
        degraus_kN_m=r.peso_unitario_kg * G / 1e3 / 2 / (lance.b_mm / 1000.0),
        guarda_corpo_kN_m=e.guarda_corpo_kN_m,
        peso_proprio_kN_m=perfil.massa_kg_m * G / 1e3,
        sobrecarga_topo_kN_m=q * largura_topo / 2,
        piso_topo_kN_m=piso * largura_topo / 2,
        sobrecarga_pe_kN_m=q * largura_pe / 2,
        piso_pe_kN_m=piso * largura_pe / 2,
    )
    permanente = {
        TRECHO_INCLINADO: cargas.permanente_inclinada(cos_a),
        TRECHO_TOPO: cargas.permanente_topo,
        TRECHO_PE: cargas.permanente_pe,
    }
    variavel = {
        TRECHO_INCLINADO: cargas.sobrecarga_kN_m,
        TRECHO_TOPO: cargas.sobrecarga_topo_kN_m,
        TRECHO_PE: cargas.sobrecarga_pe_kN_m,
    }
    gg, gq = entrada.gamma_g, entrada.gamma_q
    nos, trechos = _geometria(lance, e, vao_h)
    casos = {
        "G": ({t: permanente[t] for t in permanente}, "G"),
        "Q": ({t: variavel[t] for t in variavel}, "Q"),
        ELU: ({t: gg * permanente[t] + gq * variavel[t] for t in permanente}, ""),
        ELS: ({t: permanente[t] + variavel[t] for t in permanente}, ""),
    }
    porticos = {
        caso: _portico(nos, trechos, secao, e, valores, nome)
        for caso, (valores, nome) in casos.items()
    }
    try:
        resultados = {caso: pp.resolver(p) for caso, p in porticos.items()}
    except pp.PorticoInvalido as erro:
        raise LongarinaInvalida(str(erro)) from erro
    verificados = []
    for nome, _i, _j in trechos:
        rb_elu = resultados[ELU].barra(nome)
        rb_els = resultados[ELS].barra(nome)
        if nome == TRECHO_INCLINADO:
            lb = e.lb_m or (lance.b_mm / 1000.0) / cos_a
        else:
            lb = e.lb_m or rb_elu.comprimento_m
        lb = min(lb, rb_elu.comprimento_m)
        esforcos = [
            vb.EsforcoNoPonto(ELU, f"x = {de.numero_pt(p.x, 2)} m", p.n, p.m, p.v)
            for p in rb_elu.pontos
        ]
        try:
            resultado = vb.verificar_barra_com_esforcos(
                f"{nome}",
                e.perfil,
                e.aco,
                esforcos,
                lx_m=rb_elu.comprimento_m,
                ly_m=lb,
                lb_m=lb,
                norma=e.norma,
                tipo="longarina",
            )
        except (KeyError, ValueError) as erro:
            raise LongarinaInvalida(f"Não foi possível verificar o trecho {nome}: {erro}") from erro
        verificados.append(
            TrechoVerificado(
                barra=nome,
                comprimento_m=rb_elu.comprimento_m,
                angulo_graus=rb_elu.angulo_graus,
                lb_m=lb,
                resultado=resultado,
                flecha_mm=rb_els.flecha_max.flecha * 1e3,
                limite_flecha_mm=rb_els.comprimento_m * 1e3 / LIMITE_FLECHA,
                deslocamento_vertical_mm=max(abs(p.dy) for p in rb_els.pontos) * 1e3,
            )
        )
    return LongarinaDoLance(
        lances=numeros,
        lance=lance,
        vao_horizontal_m=vao_h,
        vao_informado=bool(vao_informado),
        desnivel_m=desnivel,
        alfa_graus=math.degrees(math.atan2(desnivel, vao_h)),
        cargas=cargas,
        gamma_g=gg,
        gamma_q=gq,
        porticos=porticos,
        resultados=resultados,
        trechos=tuple(verificados),
    )


def calcular_longarina(
    r: de.ResultadoEscada, e: EntradaLongarina, escada: el.EscadaComPatamares | None = None
) -> ResultadoLongarina:
    """As longarinas da escada: uma por geometria de lance, do primeiro ao último lance."""
    _validar(e)
    try:
        sc.obter_perfil(e.perfil)
    except (KeyError, sc.ErroDeCatalogo) as erro:
        raise LongarinaInvalida(f"Perfil desconhecido: {e.perfil!r}.") from erro
    esc = escada or el.montar_escada(r)
    avisos: list[str] = []
    grupos: dict[tuple[object, ...], list[el.Lance]] = {}
    for lance in esc.lances:
        if lance.n_espelhos < 2:
            avisos.append(
                f"Lance {lance.numero}: um espelho só, sem longarina inclinada (não calculado)."
            )
            continue
        acima = esc.patamares[lance.numero - 1] if lance.numero - 1 < len(esc.patamares) else None
        abaixo = esc.patamares[lance.numero - 2] if lance.numero >= 2 else None
        # a largura do patamar só pesa quando a longarina tem trecho horizontal daquele lado
        largura_topo = (acima.largura_mm if acima else lance.largura_mm) if e.trecho_topo_m else 0
        largura_pe = (abaixo.largura_mm if abaixo else lance.largura_mm) if e.trecho_pe_m else 0
        chave = (
            lance.n_espelhos,
            round(lance.h_mm, 3),
            round(lance.b_mm, 3),
            round(lance.largura_mm, 1),
            round(largura_topo, 1),
            round(largura_pe, 1),
        )
        grupos.setdefault(chave, []).append(lance)
    if not grupos:
        raise LongarinaInvalida("A escada não tem lance com mais de um espelho.")
    mais_longo = max(lance.n_espelhos for lances in grupos.values() for lance in lances)
    if e.vao_horizontal_m and len({k[0] for k in grupos}) > 1:
        avisos.append(
            "A distância horizontal informada vale para o lance mais longo "
            f"({mais_longo} espelhos); os outros usam a projeção da linha dos bocéis (n·b)."
        )
    longarinas = []
    for lances in grupos.values():
        representante = lances[0]
        informado = e.vao_horizontal_m if representante.n_espelhos == mais_longo else None
        longarinas.append(
            _longarina_do_lance(
                r, esc, representante, tuple(x.numero for x in lances), e, informado
            )
        )
    return ResultadoLongarina(e, tuple(longarinas), tuple(avisos))


# ---------------------------------------------------------------------------------------------
# Tabelas (página e memorial)
# ---------------------------------------------------------------------------------------------
def _n(valor: float, casas: int = 2) -> str:
    return de.numero_pt_fixo(0.0 if abs(valor) < 0.5 * 10**-casas else valor, casas)


def linhas_das_cargas(lg: LongarinaDoLance) -> list[list[str]]:
    c = lg.cargas
    cos_a = math.cos(math.radians(lg.alfa_graus))
    linhas = [
        ["Sobrecarga (Q), trecho inclinado", _n(c.sobrecarga_kN_m, 3), "kN/m horiz.", "q·L/2"],
        ["Degraus (G)", _n(c.degraus_kN_m, 3), "kN/m horiz.", "meio degrau a cada piso b"],
        ["Guarda-corpo (G)", _n(c.guarda_corpo_kN_m, 3), "kN/m de barra", "informado"],
        ["Peso próprio do perfil (G)", _n(c.peso_proprio_kN_m, 3), "kN/m de barra", "catálogo"],
        [
            "G total no trecho inclinado",
            _n(c.permanente_inclinada(cos_a), 3),
            "kN/m horiz.",
            "degraus + (guarda-corpo + peso próprio)/cos α",
        ],
    ]
    nomes = {t.barra for t in lg.trechos}
    if TRECHO_TOPO in nomes:
        linhas += [
            [
                "Sobrecarga no trecho do topo (Q)",
                _n(c.sobrecarga_topo_kN_m, 3),
                "kN/m",
                "q·largura do patamar/2",
            ],
            [
                "G total no trecho do topo",
                _n(c.permanente_topo, 3),
                "kN/m",
                "piso + guarda-corpo + peso próprio",
            ],
        ]
    if TRECHO_PE in nomes:
        linhas += [
            ["Sobrecarga no trecho do pé (Q)", _n(c.sobrecarga_pe_kN_m, 3), "kN/m", "q·largura/2"],
            [
                "G total no trecho do pé",
                _n(c.permanente_pe, 3),
                "kN/m",
                "piso + guarda-corpo + peso próprio",
            ],
        ]
    linhas.append(
        [
            "Combinação ELU",
            f"{_n(lg.gamma_g)}·G + {_n(lg.gamma_q)}·Q",
            "—",
            "ELS: G + Q (flechas)",
        ]
    )
    return linhas


CABECALHO_REACOES = ["Apoio", "Caso", "Rx (kN)", "Ry (kN)", "Mz (kN·m)"]


def linhas_das_reacoes(lg: LongarinaDoLance) -> list[list[str]]:
    linhas = []
    for caso in ("G", "Q", ELS, ELU):
        for reacao in lg.reacoes(caso):
            linhas.append(
                [
                    reacao.no,
                    caso,
                    _n(reacao.rx),
                    _n(reacao.ry),
                    _n(reacao.mz) if abs(reacao.mz) > 1e-9 else "—",
                ]
            )
    return linhas


CABECALHO_TRECHOS = [
    "Trecho",
    "L (m)",
    "Ângulo (°)",
    "N mín/máx (kN)",
    "V máx (kN)",
    "M máx (kN·m)",
    "Flecha (mm)",
    "Aproveitamento",
    "Situação",
]


def linhas_dos_trechos(lg: LongarinaDoLance) -> list[list[str]]:
    linhas = []
    for t in lg.trechos:
        rb = lg.elu.barra(t.barra)
        ns = [p.n for p in rb.pontos]
        aprov = t.resultado.aproveitamento
        flecha_u = abs(t.flecha_mm) / t.limite_flecha_mm if t.limite_flecha_mm > 0 else 0.0
        maior = max(aprov or 0.0, flecha_u)
        linhas.append(
            [
                t.barra,
                _n(t.comprimento_m, 3),
                _n(t.angulo_graus, 1),
                f"{_n(min(ns))} / {_n(max(ns))}",
                _n(abs(rb.v_max.v)),
                _n(rb.m_max.m),
                f"{_n(abs(t.flecha_mm))} ≤ {_n(t.limite_flecha_mm, 1)}",
                f"{100 * maior:.0f} %",
                status_geral(list(t.verificacoes)),
            ]
        )
    return linhas
