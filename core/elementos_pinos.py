"""Pinos e parafusos ao corte: vários planos de corte, pino em balanço e pino transversal no eixo.

Tudo aqui sai do equilíbrio do pino (:mod:`core.esforcos_no_pino`): as chapas ou o furo empurram o
pino, e o cortante e o momento vêm dessas forças. A tensão média sozinha engana: com chapas grossas,
quem manda costuma ser a flexão do pino ou o esmagamento da chapa, e o caso mostra isso.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core import bolt_design as bd
from core import desenho_pinos as dp
from core import esforcos_no_pino as ep
from core.elementos_base import (
    Campo,
    Caso,
    Figura,
    Metrica,
    Ponto,
    Resultado,
    Tabela,
    Valores,
    exigir,
    limite,
    recomendacao,
)
from core.elementos_mancais import EN_1993
from core.elementos_secoes import GRUPO_LIGACOES

CORTE_CIRCULAR = "Corte em seção circular"
CONTATO = "Pressão de contato média"
CHAPA_FURADA = "Tensões médias na chapa furada"
EQUILIBRIO_NO_FURO = "Equilíbrio do pino com pressão linear no furo"
EQUILIBRIO_NO_EIXO = "Equilíbrio do pino com pressão linear no eixo e uniforme no cubo"

FATOR_CORTE = 0.577  # von Mises em cisalhamento puro

PINO_MACICO = "Pino maciço"
PINO_VAZADO = "Pino vazado"
PARAFUSO_FUSTE = "Parafuso, corte no fuste"
PARAFUSO_ROSCA = "Parafuso, corte na rosca"
ELEMENTOS = (PINO_MACICO, PINO_VAZADO, PARAFUSO_FUSTE, PARAFUSO_ROSCA)
PARAFUSOS = (PARAFUSO_FUSTE, PARAFUSO_ROSCA)
ROSCAS = tuple(nome for nome in bd.ROSCAS_METRICAS if "×" not in nome)

#: Estudo do número de planos: até quantos a tabela compara.
PLANOS_DO_ESTUDO = 6


@dataclass(frozen=True)
class SecaoDoPino:
    """O que o corte enxerga do pino: ``d`` é o nominal, que apoia na chapa."""

    d: float
    area: float
    modulo: float  # módulo de flexão W, mm³
    fator_tau: float  # τ_máx = fator·V/A


def secao_do_pino(v: Valores) -> SecaoDoPino:
    elemento = str(v["elemento"])
    if elemento in PARAFUSOS:
        rosca = bd.ROSCAS_METRICAS[str(v["rosca"])]
        d = rosca.diametro_mm
        if elemento == PARAFUSO_ROSCA:
            # O diâmetro equivalente à área de tração, para a flexão ficar na mesma seção do corte.
            d_eq = math.sqrt(4.0 * rosca.area_tracao_mm2 / math.pi)
            return SecaoDoPino(d, rosca.area_tracao_mm2, math.pi * d_eq**3 / 32.0, 4.0 / 3.0)
        return SecaoDoPino(d, math.pi * d**2 / 4.0, math.pi * d**3 / 32.0, 4.0 / 3.0)
    d = float(v["d_mm"])
    if elemento == PINO_VAZADO:
        di = float(v["d_i_mm"])
        exigir(di < d, "O furo do pino deve ser menor que o diâmetro externo.")
        area = math.pi * (d**2 - di**2) / 4.0
        modulo = math.pi * (d**4 - di**4) / (32.0 * d)
        fator = 4.0 / 3.0 * (d**2 + d * di + di**2) / (d**2 + di**2)
        return SecaoDoPino(d, area, modulo, fator)
    return SecaoDoPino(d, math.pi * d**2 / 4.0, math.pi * d**3 / 32.0, 4.0 / 3.0)


@dataclass(frozen=True)
class Chapas:
    a: float
    b: float
    c: float
    largura: float
    borda: float


@dataclass(frozen=True)
class Tensoes:
    """As tensões de um pino para uma força e um número de planos. Em MPa, salvo ``momento``."""

    planos: int
    cortante: float
    tau_media: float
    tau_max: float
    momento: float
    sigma: float
    p_ponta: float
    p_dentro: float
    rasgo: float
    liquida: float


def tensoes_do_pino(forca: float, planos: int, s: SecaoDoPino, c: Chapas) -> Tensoes:
    """``forca`` é a de um pino. A chapa de dentro leva 2V, porque tem um plano de cada lado."""
    chapas = ep.chapas_alternadas(planos, forca, c.a, c.b, c.c)
    diagrama = ep.diagrama_das_chapas(chapas)
    v = forca / planos
    forcas = [(v, c.a)] + ([(2.0 * v, c.b)] if planos > 1 else [])
    return Tensoes(
        planos,
        v,
        v / s.area,
        s.fator_tau * v / s.area,
        diagrama.momento_max,
        diagrama.momento_max / s.modulo,
        v / (s.d * c.a),
        2.0 * v / (s.d * c.b) if planos > 1 else 0.0,
        max(f / (2.0 * t * (c.borda - s.d / 2.0)) for f, t in forcas),
        max(f / ((c.largura - s.d) * t) for f, t in forcas),
    )


@dataclass(frozen=True)
class Limites:
    sigma: float
    tau: float
    contato: float
    corte_na_chapa: float
    tracao_na_chapa: float


def _limites(v: Valores) -> Limites:
    fs = float(v["fs"])
    sy, chapa = float(v["sy_MPa"]) / fs, float(v["sy_chapa_MPa"]) / fs
    return Limites(sy, FATOR_CORTE * sy, chapa, FATOR_CORTE * chapa, chapa)


def _razoes(t: Tensoes, lim: Limites) -> dict[str, float]:
    """Solicitação sobre limite de cada critério, na ordem das verificações."""
    interacao = (t.sigma / lim.sigma) ** 2 + (t.tau_media / lim.tau) ** 2
    razoes = {
        "Cisalhamento no pino": t.tau_max / lim.tau,
        "Flexão no pino": t.sigma / lim.sigma,
        "Flexão com cortante": interacao,
        "Esmagamento na chapa da ponta": t.p_ponta / lim.contato,
        "Rasgamento até a borda": t.rasgo / lim.corte_na_chapa,
        "Seção líquida da chapa": t.liquida / lim.tracao_na_chapa,
    }
    if t.planos > 1:
        razoes["Esmagamento na chapa de dentro"] = t.p_dentro / lim.contato
    return razoes


def _forca_limite(forca: float, nome: str, razao: float) -> float:
    """A força em que o critério chega a 100 %. A interação cresce com o quadrado da força."""
    if razao <= 0:
        return math.inf
    return forca / math.sqrt(razao) if nome == "Flexão com cortante" else forca / razao


def _titulo_dos_planos(planos: int) -> str:
    if planos == 1:
        return "corte simples"
    if planos == 2:
        return "corte duplo"
    return f"{planos} planos de corte"


def calcular_pinos(v: Valores) -> Resultado:
    forca_total = float(v["forca_kN"]) * 1000.0
    pinos = int(v["pinos"])
    planos = int(v["planos"])
    elemento = str(v["elemento"])
    secao = secao_do_pino(v)
    chapas = Chapas(
        float(v["a_mm"]),
        float(v["b_mm"]),
        float(v["c_mm"]),
        float(v["w_mm"]),
        float(v["e_mm"]),
    )
    exigir(chapas.largura > secao.d, "A largura da chapa deve ser maior que o diâmetro do furo.")
    exigir(
        chapas.borda > secao.d / 2.0,
        "O furo precisa ficar dentro da chapa: a distância à borda deve passar de d/2.",
    )
    forca = forca_total / pinos
    t = tensoes_do_pino(forca, planos, secao, chapas)
    lim = _limites(v)
    razoes = _razoes(t, lim)
    camadas = ep.chapas_alternadas(planos, forca, chapas.a, chapas.b, chapas.c)
    diagrama = ep.diagrama_das_chapas(camadas)

    verificacoes = [
        limite(
            "Cisalhamento no pino",
            t.tau_max,
            lim.tau,
            "MPa",
            f"τ_máx = {secao.fator_tau:.2f}·V/A, com V = F/(n_p·n_c) = {t.cortante / 1000:.2f} kN",
            CORTE_CIRCULAR,
        ),
        limite(
            "Flexão no pino",
            t.sigma,
            lim.sigma,
            "MPa",
            f"σ = M/W, com M = {t.momento / 1000:.1f} N·m ao longo do pino",
            EN_1993,
        ),
        limite(
            "Flexão com cortante",
            razoes["Flexão com cortante"],
            1.0,
            "—",
            "(σ/σ_adm)² + (τ_méd/τ_adm)² ≤ 1",
            EN_1993,
        ),
        limite(
            "Esmagamento na chapa da ponta",
            t.p_ponta,
            lim.contato,
            "MPa",
            "p = V/(d·a)",
            CONTATO,
        ),
    ]
    if planos > 1:
        verificacoes.append(
            limite(
                "Esmagamento na chapa de dentro",
                t.p_dentro,
                lim.contato,
                "MPa",
                "p = 2V/(d·b): um plano de cada lado",
                CONTATO,
            )
        )
    verificacoes += [
        limite(
            "Rasgamento até a borda",
            t.rasgo,
            lim.corte_na_chapa,
            "MPa",
            "τ = f/(2·t·(e − d/2)), na chapa mais carregada",
            CHAPA_FURADA,
        ),
        limite(
            "Seção líquida da chapa",
            t.liquida,
            lim.tracao_na_chapa,
            "MPa",
            "σ = f/((w − d)·t), na chapa mais carregada",
            CHAPA_FURADA,
        ),
    ]

    alertas: list[str] = []
    if planos % 2 == 1 and elemento not in PARAFUSOS:
        alertas.append(
            "Com número ímpar de planos, as forças das chapas formam um binário e o pino tende a "
            "girar. Use cabeça e porca, ou um número par de planos."
        )
    if planos >= 3:
        alertas.append(
            "Com três planos ou mais, a divisão igual da força depende de furos justos e chapas "
            "rígidas: uma folga maior num furo sobrecarrega os outros planos."
        )
    if secao.d < 3.0 * chapas.c:
        alertas.append(
            "Folga grande perto do diâmetro: o pino trabalha mais à flexão que ao corte."
        )
    if elemento in PARAFUSOS:
        alertas.append(
            "Este caso olha o parafuso como um pino, sem aperto. Em ligação de estrutura, use "
            "Projeto de parafusos, com os coeficientes da norma."
        )

    limites = {nome: _forca_limite(forca_total, nome, razao) for nome, razao in razoes.items()}
    governa = min(limites, key=lambda nome: limites[nome])
    criterios = Tabela(
        "Até onde cada critério vai",
        tuple(
            {
                "Critério": nome,
                "Força total (kN)": round(limites[nome] / 1000.0, 2),
                "Aproveitamento (%)": round(forca_total / limites[nome] * 100.0, 0),
            }
            for nome in sorted(limites, key=lambda nome: limites[nome])
        ),
        "A força total em que cada critério chega ao limite, com as medidas de agora.",
    )
    tabela_chapas = Tabela(
        "Força em cada chapa",
        tuple(
            {
                "Chapa": f"{k + 1} ({'ponta' if k in (0, planos) else 'dentro'})",
                "Espessura (mm)": camada.espessura,
                "Força por pino (kN)": round(abs(camada.forca) / 1000.0, 2),
                "Esmagamento (MPa)": round(abs(camada.forca) / (secao.d * camada.espessura), 1),
            }
            for k, camada in enumerate(camadas)
        ),
        "As chapas se alternam: cada plano leva a mesma força, e a de dentro soma dois planos.",
    )
    estudo = Tabela(
        "Com outro número de planos",
        tuple(
            _linha_do_estudo(n, forca, secao, chapas, lim, planos)
            for n in _planos_do_estudo(planos)
        ),
        "Mesma força, mesmo pino e mesmas chapas. Mais planos reduzem o corte, mas a partir de "
        "certo ponto as chapas crescem e a flexão deixa de cair.",
    )

    figura = dp.figura_das_chapas(
        camadas,
        diagrama,
        secao.d,
        parafuso=elemento in PARAFUSOS,
        vazado=elemento == PINO_VAZADO,
        rosca_no_corte=elemento == PARAFUSO_ROSCA,
        titulo="Pino nas chapas",
        legenda=(
            f"{elemento}, {_titulo_dos_planos(planos)}, {planos + 1} chapas: forças de um pino, "
            "planos de corte numerados e diagramas ao longo do pino."
        ),
    )
    capacidade = limites[governa]
    return Resultado(
        resumo=(
            f"{pinos} × {elemento.lower()} em {_titulo_dos_planos(planos)}: cada plano leva "
            f"{t.cortante / 1000:.2f} kN. Quem limita é {governa.lower()}, com a ligação aguentando "
            f"até {capacidade / 1000:.1f} kN."
        ),
        metricas=(
            Metrica("Força que a ligação aguenta", capacidade / 1000.0, "kN", 1),
            Metrica("Força por plano V", t.cortante / 1000.0, "kN", 2),
            Metrica("τ médio", t.tau_media, "MPa", 1),
            Metrica("τ máximo", t.tau_max, "MPa", 1),
            Metrica("Momento no pino", t.momento / 1000.0, "N·m", 1),
            Metrica("Flexão σ", t.sigma, "MPa", 1),
            Metrica("Esmagamento na ponta", t.p_ponta, "MPa", 1),
            Metrica("Esmagamento dentro", t.p_dentro, "MPa", 1),
            Metrica("Planos de corte", planos, "", 0),
            Metrica("Chapas", planos + 1, "", 0),
        ),
        verificacoes=tuple(verificacoes),
        pontos=(
            Ponto("Fibra extrema, momento máximo", t.sigma),
            Ponto("Centro da seção, plano de corte", 0.0, 0.0, t.tau_max),
        ),
        tabelas=(criterios, tabela_chapas, estudo),
        figuras=(Figura("Pino nas chapas", figura.png, figura.legenda),),
        alertas=tuple(alertas),
        hipoteses=(
            "A força se divide por igual entre os pinos e, em cada pino, entre os planos de corte.",
            "Cada chapa empurra o pino por igual na própria espessura.",
            "Com número ímpar de planos, o binário fica metade em cada ponta do pino: na cabeça e "
            "na porca do parafuso.",
            "Furo com o diâmetro do pino. Chapas iguais ao longo do pino: a nas pontas e b dentro.",
            "Parafuso sem atrito entre as chapas: quem leva a força é o corte, não o aperto.",
            "Carga estática. Limites por escoamento, com o corte a 0,577·S_y.",
        ),
        referencias=(CORTE_CIRCULAR, EN_1993, CONTATO, CHAPA_FURADA),
    )


def _planos_do_estudo(atual: int) -> list[int]:
    return sorted({*range(1, PLANOS_DO_ESTUDO + 1), atual})


def _linha_do_estudo(
    planos: int, forca: float, s: SecaoDoPino, c: Chapas, lim: Limites, atual: int
) -> dict[str, float | int | str]:
    t = tensoes_do_pino(forca, planos, s, c)
    razoes = _razoes(t, lim)
    return {
        "Planos": planos,
        "Situação": "atual" if planos == atual else "",
        "V por plano (kN)": round(t.cortante / 1000.0, 2),
        "τ máx (MPa)": round(t.tau_max, 1),
        "Flexão (MPa)": round(t.sigma, 1),
        "Esmagamento (MPa)": round(max(t.p_ponta, t.p_dentro), 1),
        "Aproveitamento (%)": round(max(razoes.values()) * 100.0, 0),
    }


_SO_PINO = ("elemento", (PINO_MACICO, PINO_VAZADO))
_SO_PARAFUSO = ("elemento", PARAFUSOS)


def _campos_do_material(
    sy: float, sy_chapa: float, rotulo_chapa: str, ajuda: str
) -> tuple[Campo, ...]:
    return (
        Campo(
            "sy_MPa",
            "Escoamento do pino S_y",
            "Limite de escoamento do pino ou parafuso. Parafuso 8.8: 640 MPa. Escolha o material no "
            "alto da página para preencher sozinho.",
            sy,
            "MPa",
            minimo=10.0,
            passo=10.0,
            secao="Materiais",
        ),
        Campo(
            "sy_chapa_MPa",
            rotulo_chapa,
            ajuda,
            sy_chapa,
            "MPa",
            minimo=10.0,
            passo=5.0,
            secao="Materiais",
        ),
        Campo(
            "fs",
            "Fator de segurança",
            "Margem sobre o escoamento. Carga bem conhecida: 1,5. Carga incerta, choque ou falha "
            "grave: 2,0 ou mais.",
            1.5,
            minimo=1.0,
            maximo=8.0,
            passo=0.1,
            secao="Materiais",
        ),
    )


CAMPOS_PINOS = (
    Campo(
        "forca_kN",
        "Força total F",
        "A força que atravessa a ligação inteira, somando todos os pinos.",
        20.0,
        "kN",
        minimo=0.001,
        passo=1.0,
        secao="Ligação",
    ),
    Campo(
        "pinos",
        "Número de pinos n_p",
        "Quantos pinos dividem a força.",
        1,
        minimo=1,
        maximo=500,
        passo=1,
        secao="Ligação",
    ),
    Campo(
        "planos",
        "Planos de corte por pino n_c",
        "Quantas vezes cada pino seria cortado. Duas chapas dão um plano, garfo com olhal dá dois, e "
        "cada chapa a mais soma um. O desenho muda junto.",
        2,
        minimo=1,
        maximo=8,
        passo=1,
        secao="Ligação",
    ),
    Campo(
        "elemento",
        "O que trabalha ao corte",
        "Pino vazado perde área, mas guarda quase toda a resistência à flexão. Parafuso com a rosca "
        "no plano de corte perde cerca de um quarto da área.",
        PINO_MACICO,
        opcoes=ELEMENTOS,
        secao="Pino",
    ),
    Campo(
        "d_mm",
        "Diâmetro do pino d",
        "Diâmetro externo do pino, igual ao do furo.",
        16.0,
        "mm",
        minimo=0.5,
        passo=1.0,
        secao="Pino",
        quando=_SO_PINO,
    ),
    Campo(
        "d_i_mm",
        "Furo do pino d_i",
        "Diâmetro do furo central do pino vazado.",
        6.0,
        "mm",
        minimo=0.1,
        passo=1.0,
        secao="Pino",
        quando=("elemento", (PINO_VAZADO,)),
    ),
    Campo(
        "rosca",
        "Parafuso",
        "O diâmetro nominal apoia nas chapas. Com a rosca no plano, a área de corte é a de tração.",
        "M16",
        opcoes=ROSCAS,
        secao="Pino",
        quando=_SO_PARAFUSO,
    ),
    Campo(
        "a_mm",
        "Espessura das chapas da ponta a",
        "Espessura das duas chapas de fora.",
        8.0,
        "mm",
        minimo=0.1,
        passo=1.0,
        secao="Chapas",
    ),
    Campo(
        "b_mm",
        "Espessura das chapas de dentro b",
        "Espessura de cada chapa entre dois planos de corte. Ela recebe o dobro da força da chapa "
        "de ponta.",
        12.0,
        "mm",
        minimo=0.1,
        passo=1.0,
        secao="Chapas",
        quando=("planos", (2, 3, 4, 5, 6, 7, 8)),
    ),
    Campo(
        "c_mm",
        "Folga entre chapas c",
        "Espaço vazio entre duas chapas. Quanto maior, maior o momento no pino.",
        1.0,
        "mm",
        minimo=0.0,
        passo=0.5,
        secao="Chapas",
    ),
    Campo(
        "w_mm",
        "Largura da chapa por pino w",
        "Largura de chapa que cabe a cada pino, medida na direção perpendicular à força.",
        60.0,
        "mm",
        minimo=0.5,
        passo=5.0,
        secao="Chapas",
    ),
    Campo(
        "e_mm",
        "Distância do centro à borda e",
        "Do centro do furo até a ponta da chapa, na direção da força. Pouca borda rasga a chapa.",
        30.0,
        "mm",
        minimo=0.5,
        passo=1.0,
        secao="Chapas",
    ),
    *_campos_do_material(
        640.0,
        250.0,
        "Escoamento das chapas",
        "Limite de escoamento das chapas. ASTM A36: 250 MPa.",
    ),
)


# ---------------------------------------------------------------------------
# Pino em balanço
# ---------------------------------------------------------------------------


def calcular_pino_balanco(v: Valores) -> Resultado:
    forca = float(v["forca_kN"]) * 1000.0
    d = float(v["d_mm"])
    braco = float(v["braco_mm"])
    engaste = float(v["engaste_mm"])
    t_chapa = float(v["t_chapa_mm"])
    fs = float(v["fs"])
    exigir(braco >= t_chapa / 2.0, "A chapa não pode entrar no furo: a precisa ser ao menos t/2.")

    pino = ep.PinoEmBalanco(forca, braco, engaste, d)
    area = math.pi * d**2 / 4.0
    modulo = math.pi * d**3 / 32.0
    tau_media = forca / area
    tau_max = 4.0 / 3.0 * tau_media
    momento = pino.momento_max
    sigma = momento / modulo
    p_chapa = forca / (d * t_chapa)
    sy = float(v["sy_MPa"]) / fs
    sy_chapa = float(v["sy_chapa_MPa"]) / fs
    sy_furo = float(v["sy_furo_MPa"]) / fs
    tau_adm = FATOR_CORTE * sy
    interacao = (sigma / sy) ** 2 + (tau_media / tau_adm) ** 2
    minimo_de_engaste = ep.engaste_minimo(forca, braco, d, sy_furo)

    figura = dp.figura_do_balanco(
        pino,
        t_chapa,
        titulo="Pino em balanço",
        legenda=(
            "Pino preso no furo, com a pressão linear no engaste. O maior momento fica dentro do "
            "furo, não na boca."
        ),
    )
    verificacoes = (
        limite(
            "Flexão no pino",
            sigma,
            sy,
            "MPa",
            f"M_máx = {momento / 1000:.1f} N·m, a {pino.profundidade_do_momento_max:.1f} mm dentro "
            "do furo",
            EQUILIBRIO_NO_FURO,
        ),
        limite(
            "Cisalhamento no pino",
            tau_max,
            tau_adm,
            "MPa",
            "τ_máx = 4/3·F/A",
            CORTE_CIRCULAR,
        ),
        limite(
            "Flexão com cortante",
            interacao,
            1.0,
            "—",
            "(σ/σ_adm)² + (τ_méd/τ_adm)² ≤ 1",
            EN_1993,
        ),
        limite(
            "Pressão na boca do furo",
            pino.pressao_max,
            sy_furo,
            "MPa",
            "p = F/(d·L)·(4 + 6·a/L)",
            EQUILIBRIO_NO_FURO,
        ),
        limite(
            "Esmagamento na chapa",
            p_chapa,
            sy_chapa,
            "MPa",
            "p = F/(d·t)",
            CONTATO,
        ),
    )
    return Resultado(
        resumo=(
            f"O pino flete a {sigma:.0f} MPa e aperta o furo a {pino.pressao_max:.0f} MPa na boca. "
            f"Com essa força, o engaste não pode ser menor que {minimo_de_engaste:.1f} mm."
        ),
        metricas=(
            Metrica("Momento máximo", momento / 1000.0, "N·m", 1),
            Metrica("Momento na boca do furo", forca * braco / 1000.0, "N·m", 1),
            Metrica("Flexão σ", sigma, "MPa", 1),
            Metrica("τ máximo", tau_max, "MPa", 1),
            Metrica("Pressão na boca do furo", pino.pressao_max, "MPa", 1),
            Metrica("Pressão no fundo do furo", pino.pressao_no_fundo, "MPa", 1),
            Metrica("Engaste mínimo", minimo_de_engaste, "mm", 1),
            Metrica("Esmagamento na chapa", p_chapa, "MPa", 1),
        ),
        verificacoes=verificacoes,
        pontos=(
            Ponto("Fibra extrema, momento máximo", sigma),
            Ponto("Centro da seção, boca do furo", 0.0, 0.0, tau_max),
        ),
        figuras=(Figura("Pino em balanço", figura.png, figura.legenda),),
        hipoteses=(
            "Pino rígido num furo ajustado, com pressão variando em linha reta ao longo do engaste.",
            "A força entra pelo meio da chapa, a uma distância a da boca do furo.",
            "Com folga no furo, o pino encosta só nas pontas do engaste e a pressão real é maior.",
            "Carga estática. Limites por escoamento, com o corte a 0,577·S_y.",
        ),
        referencias=(EQUILIBRIO_NO_FURO, CORTE_CIRCULAR, EN_1993, CONTATO),
    )


CAMPOS_BALANCO = (
    Campo(
        "forca_kN",
        "Força F",
        "A força que a chapa ou o braço aplica na ponta livre do pino.",
        15.0,
        "kN",
        minimo=0.001,
        passo=0.5,
        secao="Pino",
    ),
    Campo(
        "d_mm",
        "Diâmetro do pino d",
        "Diâmetro do pino, igual ao do furo.",
        25.0,
        "mm",
        minimo=0.5,
        passo=1.0,
        secao="Pino",
    ),
    Campo(
        "braco_mm",
        "Braço a",
        "Distância da boca do furo até a linha da força. É ela que cria o momento.",
        15.0,
        "mm",
        minimo=0.0,
        passo=1.0,
        secao="Pino",
    ),
    Campo(
        "engaste_mm",
        "Engaste L",
        "Quanto do pino fica dentro do furo. Engaste curto aumenta muito a pressão na boca.",
        40.0,
        "mm",
        minimo=0.5,
        passo=1.0,
        secao="Pino",
    ),
    Campo(
        "t_chapa_mm",
        "Espessura da chapa t",
        "Chapa ou olhal que carrega a ponta livre do pino.",
        12.0,
        "mm",
        minimo=0.1,
        passo=1.0,
        secao="Pino",
    ),
    *_campos_do_material(
        640.0,
        250.0,
        "Escoamento da chapa",
        "Limite de escoamento da chapa que carrega o pino.",
    ),
    Campo(
        "sy_furo_MPa",
        "Escoamento do bloco",
        "Limite de escoamento da peça onde o pino está preso. Ferro fundido e alumínio limitam "
        "bem antes do pino.",
        250.0,
        "MPa",
        minimo=10.0,
        passo=5.0,
        secao="Materiais",
    ),
)


# ---------------------------------------------------------------------------
# Pino transversal no eixo
# ---------------------------------------------------------------------------


def calcular_pino_transversal(v: Valores) -> Resultado:
    torque = float(v["torque_Nm"]) * 1000.0
    eixo = float(v["d_eixo_mm"])
    cubo = float(v["d_cubo_mm"])
    d = float(v["d_mm"])
    fs = float(v["fs"])
    kts = float(v["kts"])
    exigir(cubo > eixo, "O diâmetro do cubo deve ser maior que o do eixo.")
    exigir(d < eixo, "O pino deve ser mais fino que o eixo.")

    # Cada lado do eixo é um plano de corte: T = F·D.
    forca = torque / eixo
    area = math.pi * d**2 / 4.0
    tau_media = forca / area
    tau_max = 4.0 / 3.0 * tau_media
    p_eixo = 6.0 * torque / (d * eixo**2)
    p_cubo = 4.0 * torque / (d * (cubo**2 - eixo**2))
    modulo_liquido = math.pi * eixo**3 / 16.0 - d * eixo**2 / 6.0
    exigir(modulo_liquido > 0, "O furo tira quase todo o eixo: reduza o diâmetro do pino.")
    tau_eixo = kts * torque / modulo_liquido
    sy = float(v["sy_MPa"]) / fs
    sy_eixo = float(v["sy_eixo_MPa"]) / fs
    sy_cubo = float(v["sy_chapa_MPa"]) / fs
    tau_adm = FATOR_CORTE * sy

    figura = dp.figura_do_transversal(
        eixo,
        cubo,
        d,
        forca,
        torque / 1000.0,
        p_eixo,
        p_cubo,
        titulo="Pino transversal",
        legenda=(
            "Corte do eixo e do cubo: dois planos de corte, pressão crescendo do centro para a "
            "borda no eixo e constante no cubo."
        ),
    )
    verificacoes = (
        limite(
            "Cisalhamento no pino",
            tau_max,
            tau_adm,
            "MPa",
            f"τ_máx = 4/3·F/A, com F = T/D = {forca / 1000:.2f} kN em cada plano",
            CORTE_CIRCULAR,
        ),
        limite(
            "Pressão no eixo",
            p_eixo,
            sy_eixo,
            "MPa",
            "p = 6T/(d·D²), na borda do eixo",
            EQUILIBRIO_NO_EIXO,
        ),
        limite(
            "Pressão no cubo",
            p_cubo,
            sy_cubo,
            "MPa",
            "p = 4T/(d·(D_c² − D²))",
            EQUILIBRIO_NO_EIXO,
        ),
        limite(
            "Torção no eixo com o furo",
            tau_eixo,
            FATOR_CORTE * sy_eixo,
            "MPa",
            f"τ = K_ts·T/(π·D³/16 − d·D²/6), com K_ts = {kts:g}",
            EQUILIBRIO_NO_EIXO,
        ),
        recomendacao(
            "Pino em relação ao eixo",
            d / eixo,
            0.3,
            "—",
            "d/D ≤ 0,3: a seção líquida do eixo vale para furo pequeno",
            EQUILIBRIO_NO_EIXO,
        ),
    )
    return Resultado(
        resumo=(
            f"Cada lado do pino leva {forca / 1000:.2f} kN e corta a {tau_max:.0f} MPa. A pressão "
            f"chega a {p_eixo:.0f} MPa no eixo e a {p_cubo:.0f} MPa no cubo."
        ),
        metricas=(
            Metrica("Força em cada plano", forca / 1000.0, "kN", 2),
            Metrica("τ máximo no pino", tau_max, "MPa", 1),
            Metrica("Pressão no eixo", p_eixo, "MPa", 1),
            Metrica("Pressão no cubo", p_cubo, "MPa", 1),
            Metrica("τ no eixo com o furo", tau_eixo, "MPa", 1),
            Metrica("Razão d/D", d / eixo, "", 2),
        ),
        verificacoes=verificacoes,
        pontos=(Ponto("Centro do pino, plano de corte", 0.0, 0.0, tau_max),),
        figuras=(Figura("Pino transversal", figura.png, figura.legenda),),
        hipoteses=(
            "Pino atravessando o eixo e o cubo, com dois planos de corte na superfície do eixo.",
            "No eixo, a pressão cresce em linha reta do centro para a borda; no cubo, é constante.",
            "Carga estática. Com torque variável, verifique o eixo à fadiga em Seção de eixo à "
            "fadiga: o furo é um concentrador forte.",
        ),
        referencias=(EQUILIBRIO_NO_EIXO, CORTE_CIRCULAR),
    )


CAMPOS_TRANSVERSAL = (
    Campo(
        "torque_Nm",
        "Torque T",
        "O torque que passa do eixo para o cubo pelo pino.",
        200.0,
        "N·m",
        minimo=0.001,
        passo=10.0,
        secao="Ligação",
    ),
    Campo(
        "d_eixo_mm",
        "Diâmetro do eixo D",
        "Diâmetro do eixo, onde o pino atravessa.",
        40.0,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Ligação",
    ),
    Campo(
        "d_cubo_mm",
        "Diâmetro do cubo D_c",
        "Diâmetro externo do cubo ou do colar em volta do eixo.",
        70.0,
        "mm",
        minimo=1.0,
        passo=1.0,
        secao="Ligação",
    ),
    Campo(
        "d_mm",
        "Diâmetro do pino d",
        "Diâmetro do pino. Mais grosso aguenta mais, mas enfraquece o eixo.",
        10.0,
        "mm",
        minimo=0.5,
        passo=1.0,
        secao="Ligação",
    ),
    *_campos_do_material(
        640.0,
        250.0,
        "Escoamento do cubo",
        "Limite de escoamento do cubo ou do colar.",
    ),
    Campo(
        "sy_eixo_MPa",
        "Escoamento do eixo",
        "Limite de escoamento do eixo. AISI 1045 trefilado: cerca de 500 MPa.",
        500.0,
        "MPa",
        minimo=10.0,
        passo=10.0,
        secao="Materiais",
    ),
    Campo(
        "kts",
        "Concentração no furo K_ts",
        "Multiplica a torção no eixo. Em carga estática de aço dúctil pode ficar em 1,0, porque o "
        "escoamento local redistribui a tensão. Com carga repetida, use o valor do furo transversal.",
        1.0,
        minimo=1.0,
        maximo=6.0,
        passo=0.1,
        secao="Materiais",
    ),
)


CASOS: tuple[Caso, ...] = (
    Caso(
        "Pinos ou parafusos sob cisalhamento",
        "Pinos ou parafusos sob cisalhamento",
        GRUPO_LIGACOES,
        "Pino ou parafuso com um ou mais planos de corte, com as chapas.",
        "Escolha quantos planos de corte o pino tem: o desenho muda e sai a força em cada chapa, o "
        "corte, a flexão do pino, o esmagamento, o rasgamento e até onde a ligação vai.",
        CAMPOS_PINOS,
        calcular_pinos,
        r"V=\frac{F}{n_p\,n_c},\quad \tau_{max}=\frac{4}{3}\frac{V}{A},\quad "
        r"\sigma=\frac{M}{W},\quad p=\frac{V}{d\,a}",
    ),
    Caso(
        "pino_balanco",
        "Pino em balanço",
        GRUPO_LIGACOES,
        "Pino preso num furo, com a carga fora: flexão e pressão no engaste.",
        "Pino de braço, de roda ou de articulação com um lado só. Sai a pressão na boca do furo, o "
        "maior momento, que fica dentro do furo, e o menor engaste que resolve.",
        CAMPOS_BALANCO,
        calcular_pino_balanco,
        r"p_{max}=\frac{F}{d\,L}\left(4+\frac{6a}{L}\right),\quad \sigma=\frac{32M_{max}}{\pi d^3}",
    ),
    Caso(
        "pino_transversal",
        "Pino transversal no eixo",
        GRUPO_LIGACOES,
        "Pino que atravessa eixo e cubo para passar torque.",
        "Trava de cubo, colar ou manivela. Sai o corte nos dois planos, a pressão no eixo e no cubo "
        "e quanto o furo enfraquece o eixo.",
        CAMPOS_TRANSVERSAL,
        calcular_pino_transversal,
        r"\tau=\frac{4T}{\pi d^2 D},\quad p_{eixo}=\frac{6T}{d\,D^2},\quad "
        r"p_{cubo}=\frac{4T}{d\,(D_c^2-D^2)}",
    ),
)
