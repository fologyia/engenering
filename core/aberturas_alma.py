"""Aberturas na alma de vigas de aço (passagem de tubulação, eletrocalha, duto).

ABNT NBR 8800:2025, Anexo F: as aberturas devem entrar no dimensionamento (F.1 e F.2), exceto as
circulares sem reforço que atendem às condições de F.3 (viga biapoiada com carga uniforme, alma e
mesa compactas, abertura no terço médio da altura e nos dois quartos centrais do vão, centros a
2,5 diâmetros e cortante nos apoios até 50 % da resistência). Fora disso, o Anexo F manda usar
"um método que se baseie em princípios reconhecidos": o programa usa o AISC Design Guide 2
(Darwin, 1990) para aberturas retangulares ou circulares sem reforço em vigas de aço:

    M_m = M_p·[1 − ΔA_s·(h₀/4 + e)/Z],  ΔA_s = h₀·t_w
    V_m = V_m,sup + V_m,inf,  V_m,tê = V_p,tê·√6/(ν + √3) ≤ V_p,tê,  V_p,tê = f_y·t_w·s/√3
    (M_Sd/M_Rd)³ + (V_Sd/V_Rd)³ ≤ 1,  com M_Rd = M_m/γ_a1 e V_Rd = V_m/γ_a1

(circular: h₀ = D₀ no momento e h₀ = 0,9·D₀, a₀ = 0,45·D₀ no cortante), mais os limites de
proporção do guia. Viga biapoiada com carga uniforme de cálculo; aberturas sem reforço.

Unidades: mm, MPa, N internamente; kN, kN/m e kN·m nas entradas e saídas.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from itertools import pairwise
from typing import Any

from core import nbr8800 as nb
from core import perfil_i as pi
from core import verificacao_modulo as vm
from core.verificacao import Verificacao

MODULO_ID = "aberturas_alma"
MODULO_TITULO = "Aberturas na alma"
CIRCULAR = "Circular"
RETANGULAR = "Retangular"
FORMAS = (CIRCULAR, RETANGULAR)

REFERENCIAS = (
    "ABNT NBR 8800:2025 — Anexo F (normativo) Aberturas em almas de vigas: F.1 a F.3.",
    "AISC Design Guide 2 — Steel and Composite Beams with Web Openings (Darwin, 1990): "
    "resistência à flexão e ao cortante na abertura, interação cúbica e limites de proporção.",
)


@dataclass(frozen=True)
class Abertura:
    nome: str = "Passagem de tubo"
    forma: str = CIRCULAR
    largura: float = 150.0  # D₀ (circular) ou a₀ (retangular), ao longo da viga
    altura: float = 150.0  # h₀ (retangular; no circular é igual ao diâmetro)
    x: float = 2500.0  # do apoio esquerdo ao centro da abertura
    e: float = 0.0  # excentricidade do centro em relação à meia altura (+ para cima)


@dataclass(frozen=True)
class EsforcoNaAbertura:
    combinacao: str
    momento_kNm: float
    cortante_kN: float


@dataclass(frozen=True)
class EsforcosImportados:
    locais: tuple[tuple[EsforcoNaAbertura, ...], ...]
    maximo_momento_kNm: float
    maximo_cortante_kN: float
    cortante_apoios_kN: float


@dataclass(frozen=True)
class EntradaAberturas:
    familia: str = pi.FAMILIA_W
    perfil: str = "W 410 x 46,1"
    d: float = 400.0
    bf: float = 180.0
    tf: float = 12.5
    tw: float = 8.0
    aco: str = "ASTM A572 Gr 50"
    gama_a1: float = pi.GAMA_A1
    L: float = 7000.0
    q: float = 30.0  # kN/m de cálculo
    Lb: float = 0.0  # destravado para o momento da viga (0 = contida)
    aberturas: tuple[Abertura, ...] = field(
        default_factory=lambda: (
            Abertura(),
            Abertura("Eletrocalha", RETANGULAR, 300.0, 120.0, 4200.0, 0.0),
        )
    )
    esforcos: EsforcosImportados | None = None


def obter_perfil(e: EntradaAberturas) -> pi.PerfilI:
    if e.familia == pi.FAMILIA_SOLDADO:
        return pi.soldado(e.d, e.bf, e.tf, e.tw)
    return pi.perfil(e.perfil)


def validar(e: EntradaAberturas) -> list[str]:
    erros: list[str] = []
    try:
        p = obter_perfil(e)
    except (ValueError, KeyError) as exc:
        return [f"Perfil: {exc}"]
    if e.aco not in pi.ACOS:
        erros.append("Escolha o aço.")
    if e.L <= 0 or e.q < 0:
        erros.append("Vão positivo e carga não negativa.")
    if not e.aberturas:
        erros.append("Informe pelo menos uma abertura.")
    if e.esforcos and (
        len(e.esforcos.locais) != len(e.aberturas) or any(not casos for casos in e.esforcos.locais)
    ):
        erros.append("Informe os esforços simultâneos de cada abertura.")
    for a in e.aberturas:
        h0 = a.largura if a.forma == CIRCULAR else a.altura
        if a.largura <= 0 or h0 <= 0:
            erros.append(f"{a.nome}: as medidas devem ser positivas.")
        elif abs(a.e) + h0 / 2 >= p.h_interna / 2:
            erros.append(
                f"{a.nome}: a abertura invade a mesa (reveja a altura e a excentricidade)."
            )
        if not 0 < a.x < e.L:
            erros.append(f"{a.nome}: o centro deve ficar dentro do vão.")
    return erros


def _n(valor: float, casas: int = 1) -> str:
    return pi.numero(valor, casas)


def momento_maximo_na_abertura(p: pi.PerfilI, fy: float, h0: float, e: float) -> float:
    """DG2: M_m = M_p·[1 − h₀·t_w·(h₀/4 + |e|)/Z] (N·mm)."""
    Mp = p.Zx * fy
    return Mp * (1 - h0 * p.tw * (h0 / 4 + abs(e)) / p.Zx)


def cortante_maximo_na_abertura(
    p: pi.PerfilI, fy: float, a0: float, h0: float, e: float
) -> tuple[float, float, float]:
    """DG2: V_m = Σ V_p,tê·√6/(ν + √3) ≤ V_p,tê nos dois tês (N); devolve também s_sup e s_inf."""
    s_sup = p.d / 2 - h0 / 2 - e
    s_inf = p.d / 2 - h0 / 2 + e
    total = 0.0
    for s in (s_sup, s_inf):
        Vp = fy * p.tw * s / math.sqrt(3)
        nu = a0 / s
        total += min(Vp * math.sqrt(6) / (nu + math.sqrt(3)), Vp)
    return total, s_sup, s_inf


@dataclass
class ResultadoAberturas:
    entrada: EntradaAberturas
    perfil: pi.PerfilI
    fy: float
    grupos: list[vm.Grupo]
    dispensa: bool
    avisos: list[str]

    @property
    def linhas(self) -> list[Verificacao]:
        return vm.decisivas(self.grupos)

    @property
    def situacao(self) -> str:
        return vm.situacao(self.linhas)


def _condicoes_f3(
    e: EntradaAberturas, p: pi.PerfilI, fy: float, V_apoio: float, V_Rd: float
) -> list[Verificacao]:
    """F.3: aberturas circulares sem reforço que dispensam cálculo."""
    ref = "ABNT NBR 8800:2025, F.3"
    E = pi.E_ACO
    linhas = [
        vm.linha_limite("Alma compacta (h/t_w)", p.h_interna / p.tw, 3.76 * math.sqrt(E / fy), "",
                        ref, "h/t_w ≤ 3,76·√(E/f_y)"),
        vm.linha_limite("Mesa comprimida (b_f/2t_f)", p.bf / (2 * p.tf), 0.38 * math.sqrt(E / fy),
                        "", ref, "b_fc/(2·t_fc) ≤ 0,38·√(E/f_y)"),
        vm.linha_limite("Cortante nos apoios", V_apoio, 0.5 * V_Rd, "kN", ref + " d)",
                        "V_Sd ≤ 0,5·V_Rd"),
    ]  # fmt: skip
    circulares = [a for a in e.aberturas if a.forma == CIRCULAR]
    for a in e.aberturas:
        if a.forma != CIRCULAR:
            linhas.append(vm.linha_alerta(f"{a.nome}: forma", ref, "só aberturas circulares"))
            continue
        D = a.largura
        linhas.append(
            vm.linha_limite(f"{a.nome}: terço médio da altura", abs(a.e) + D / 2, p.d / 6, "mm",
                            ref + " b)", "|e| + D/2 ≤ d/6")
        )  # fmt: skip
        dentro = a.x - D / 2 >= e.L / 4 - 1e-9 and a.x + D / 2 <= 3 * e.L / 4 + 1e-9
        linhas.append(
            Verificacao(f"{a.nome}: dois quartos centrais do vão", a.x, None, "mm", ref + " b)",
                        f"a abertura inteira entre L/4 = {_n(e.L / 4, 0)} e 3L/4 = "
                        f"{_n(3 * e.L / 4, 0)} mm", status="OK" if dentro else "NÃO OK",
                        tipo="limite")
        )  # fmt: skip
    for i, a in enumerate(circulares):
        for b in circulares[i + 1 :]:
            dist = abs(a.x - b.x)
            linhas.append(
                vm.linha_limite(f"Espaço entre {a.nome} e {b.nome}", dist,
                                2.5 * max(a.largura, b.largura), "mm", ref + " c)",
                                "centros a pelo menos 2,5·D da maior", minimo=True)
            )  # fmt: skip
    return linhas


def calcular(e: EntradaAberturas) -> ResultadoAberturas:
    p = obter_perfil(e)
    fy = pi.ACOS[e.aco][0]
    g1 = e.gama_a1
    E = pi.E_ACO
    q = e.q  # N/mm
    L = e.L
    avisos = list(pi.avisos_do_perfil(p))
    perfil_aco = p.perfil_aco()
    dados = e.esforcos
    V_apoio = dados.cortante_apoios_kN * 1000 if dados else q * L / 2
    V_max = dados.maximo_cortante_kN * 1000 if dados else V_apoio
    M_max = dados.maximo_momento_kNm * 1e6 if dados else q * L**2 / 8
    cis = nb.verificar_cisalhamento(perfil_aco, fy, E, V_max)
    V_Rd = cis.resistencia_N
    flex = nb.verificar_flexao(perfil_aco, fy, E, pi.G_ACO, M_max, eixo="x",
                               comprimento_destravado_mm=e.Lb or None, cb=1.0 if dados else 1.14,
                               soldado=p.soldado)  # fmt: skip
    grupos: list[vm.Grupo] = []
    gerais = [
        Verificacao("Viga sem aberturas: flexão", M_max / 1e6, flex.resistencia_Nmm / 1e6,
                    "kN·m", "ABNT NBR 8800:2025, 5.4.2",
                    f"{'Máximo exportado' if dados else 'q·L²/8'}; {flex.modo_governante}"),
        Verificacao("Viga sem aberturas: cortante", V_max / 1000, V_Rd / 1000, "kN",
                    "ABNT NBR 8800:2025, 5.4.3", "Máximo exportado" if dados else "q·L/2"),
    ]  # fmt: skip
    grupos.append(vm.Grupo("Viga", gerais))
    f3 = _condicoes_f3(e, p, fy, V_apoio / 1000, V_Rd / 1000)
    dispensa = all(v.status == "OK" for v in f3)
    grupos.append(
        vm.Grupo(
            "Dispensa da NBR 8800 (F.3)",
            [
                replace(
                    v,
                    status="INFO",
                    tipo="informativo",
                    formula=v.formula + " — não atendida: a dispensa de F.3 não vale",
                )
                if v.status != "OK"
                else v
                for v in f3
            ]  # fmt: skip
            if not dispensa
            else f3,
        )
    )
    if dispensa:
        avisos.append(
            "As aberturas atendem a F.3: a NBR 8800 dispensa cálculos específicos. As verificações "
            "do AISC Design Guide 2 aparecem como conferência."
        )
    else:
        avisos.append(
            "As aberturas não se enquadram em F.3: verificadas pelo AISC Design Guide 2 (F.2)."
        )
    for i, a in enumerate(e.aberturas):
        circ = a.forma == CIRCULAR
        D = a.largura
        h0_m = D if circ else a.altura
        a0_v, h0_v = (0.45 * D, 0.9 * D) if circ else (a.largura, a.altura)
        Mm = momento_maximo_na_abertura(p, fy, h0_m, a.e)
        Vm, s_sup, s_inf = cortante_maximo_na_abertura(p, fy, a0_v, h0_v, a.e)
        M_Rd, V_Rd_ab = Mm / g1, Vm / g1
        caso_governante = "Viga biapoiada"
        if dados:
            demanda = max(
                dados.locais[i],
                key=lambda c: (
                    abs(c.momento_kNm * 1e6 / M_Rd) ** 3 + abs(c.cortante_kN * 1000 / V_Rd_ab) ** 3
                ),
            )
            M, V = abs(demanda.momento_kNm) * 1e6, abs(demanda.cortante_kN) * 1000
            caso_governante = demanda.combinacao
        else:
            M = q * a.x * (L - a.x) / 2
            V = abs(q * (L / 2 - a.x))
        inter = (M / M_Rd) ** 3 + (V / V_Rd_ab) ** 3
        ref = "AISC Design Guide 2 (F.2)"
        linhas = [
            vm.linha_info("Esforços no centro da abertura", M / 1e6, "kN·m", caso_governante,
                          f"M = {_n(M / 1e6, 2)} kN·m, V = {_n(V / 1000, 2)} kN a "
                          f"{_n(a.x, 0)} mm do apoio"),
            vm.linha_info("Momento resistente na abertura", Mm / g1 / 1e6, "kN·m", ref,
                          f"M_p·[1 − h₀·t_w·(h₀/4 + |e|)/Z]/γ_a1, h₀ = {_n(h0_m, 0)} mm"),
            vm.linha_info("Cortante resistente na abertura", Vm / g1 / 1000, "kN", ref,
                          f"Σ V_p,tê·√6/(ν + √3) ≤ V_p,tê, tês de {_n(s_sup, 0)} e "
                          f"{_n(s_inf, 0)} mm, a₀ = {_n(a0_v, 0)} mm"),
            Verificacao("Interação momento × cortante", inter, 1.0, "", ref,
                        f"(M/M_Rd)³ + (V/V_Rd)³ = {_n((M / M_Rd) ** 3, 3)} + "
                        f"{_n((V / V_Rd_ab) ** 3, 3)}"),
            vm.linha_limite("Altura da abertura", h0_m, 0.7 * p.d, "mm", ref + ", 3.7",
                            "h₀ ≤ 0,7·d"),
            vm.linha_limite("Altura do tê mais baixo", min(s_sup, s_inf), 0.15 * p.d, "mm",
                            ref + ", 3.7", "s ≥ 0,15·d", minimo=True),
        ]  # fmt: skip
        if not circ:
            linhas += [
                vm.linha_limite("Proporção a₀/h₀", a.largura / a.altura, 3.0, "", ref + ", 3.7",
                                "a₀/h₀ ≤ 3,0"),
                vm.linha_limite("Esbeltez da abertura", a.largura / a.altura + 6 * a.altura / p.d,
                                5.6, "", ref + ", 3.7", "a₀/h₀ + 6·h₀/d ≤ 5,6 (sem reforço)"),
                vm.linha_limite("Proporção do tê", a.largura / min(s_sup, s_inf), 12.0, "",
                                ref + ", 3.7", "ν = a₀/s ≤ 12"),
            ]  # fmt: skip
        dist_apoio = min(a.x, L - a.x) - (D if circ else a.largura) / 2
        linhas.append(
            vm.linha_limite("Distância ao apoio", dist_apoio, p.d, "mm", ref + ", 3.7",
                            "borda da abertura a pelo menos d do apoio", minimo=True,
                            obrigatoria=False)
        )  # fmt: skip
        if dispensa:
            linhas = [replace(v, status="INFO", tipo="informativo") if v.tipo != "informativo" else v
                      for v in linhas]  # fmt: skip
        grupos.append(vm.Grupo(f"Abertura: {a.nome}", linhas))
    # espaçamento entre aberturas (DG2): borda a borda ≥ maior altura (retangular) ou 1,5·D
    ordenadas = sorted(e.aberturas, key=lambda x: x.x)
    esp: list[Verificacao] = []
    for a, b in pairwise(ordenadas):
        livre = (b.x - b.largura / 2) - (a.x + a.largura / 2)
        exig = max(
            1.5 * a.largura if a.forma == CIRCULAR else a.altura,
            1.5 * b.largura if b.forma == CIRCULAR else b.altura,
        )
        esp.append(vm.linha_limite(f"Entre {a.nome} e {b.nome}", livre, exig, "mm",
                                   "AISC Design Guide 2, 3.7", "espaço livre ≥ h₀ (ou 1,5·D₀)",
                                   minimo=True))  # fmt: skip
    if esp:
        grupos.append(vm.Grupo("Espaço entre aberturas", esp))
    return ResultadoAberturas(e, p, fy, grupos, dispensa, avisos)


def registro(r: ResultadoAberturas) -> dict[str, Any]:
    e = r.entrada
    entradas = {
        "perfil": r.perfil.descricao,
        "aco": f"{e.aco} (f_y = {_n(r.fy, 0)} MPa)",
        "viga": f"biapoiada, L = {_n(e.L, 0)} mm, "
        + ("esforços importados do Robot" if e.esforcos else f"q_d = {_n(e.q, 2)} kN/m"),
        "aberturas": "; ".join(
            f"{a.nome}: {a.forma.lower()} "
            + (
                f"Ø {_n(a.largura, 0)}"
                if a.forma == CIRCULAR
                else f"{_n(a.largura, 0)} × {_n(a.altura, 0)}"
            )
            + f" mm a {_n(a.x, 0)} mm do apoio, e = {_n(a.e, 0)} mm"
            for a in e.aberturas
        ),
    }
    return vm.registro_padrao(
        modulo_id=MODULO_ID,
        modulo_titulo=MODULO_TITULO,
        titulo=f"Aberturas na alma — {r.perfil.nome}",
        grupos=r.grupos,
        entradas=entradas,
        metodo=(
            "Aberturas na alma pela ABNT NBR 8800:2025, Anexo F: dispensa de F.3 para aberturas "
            "circulares; nos demais casos, resistência na abertura pelo AISC Design Guide 2 "
            "(aberturas sem reforço em viga de aço)."
        ),
        premissas=[
            "Viga biapoiada com esforços do Robot e aberturas sem chapa de reforço."
            if e.esforcos
            else "Viga biapoiada com carga uniforme de cálculo; aberturas sem chapa de reforço.",
            "Abertura circular: h₀ = D₀ na flexão; h₀ = 0,9·D₀ e a₀ = 0,45·D₀ no cortante (DG2).",
            "Coeficiente γ_a1 da NBR 8800 no lugar de φ = 0,90 do guia.",
        ],
        referencias=REFERENCIAS,
        objeto=f"A viga {r.perfil.nome} com aberturas",
        alertas=r.avisos,
    )


def com(e: EntradaAberturas, **mudancas: Any) -> EntradaAberturas:
    return replace(e, **mudancas)


def aberturas_de_tabela(linhas: Sequence[dict[str, Any]]) -> tuple[Abertura, ...]:
    def numero(valor: Any, padrao: float) -> float:
        try:
            x = float(valor)
        except (TypeError, ValueError):
            return padrao
        return x if math.isfinite(x) else padrao

    saida: list[Abertura] = []
    for i, linha in enumerate(linhas):
        forma = str(linha.get("Forma") or CIRCULAR)
        saida.append(
            Abertura(
                nome=str(linha.get("Abertura") or "").strip() or f"Abertura {i + 1}",
                forma=forma if forma in FORMAS else CIRCULAR,
                largura=numero(linha.get("Largura ou D (mm)"), 0.0),
                altura=numero(linha.get("Altura (mm)"), 0.0),
                x=numero(linha.get("Centro a partir do apoio (mm)"), 0.0),
                e=numero(linha.get("Excentricidade (mm)"), 0.0),
            )
        )
    return tuple(saida)


def tabela_das_aberturas(aberturas: Sequence[Abertura]) -> list[dict[str, Any]]:
    return [
        {
            "Abertura": a.nome,
            "Forma": a.forma,
            "Largura ou D (mm)": a.largura,
            "Altura (mm)": a.altura,
            "Centro a partir do apoio (mm)": a.x,
            "Excentricidade (mm)": a.e,
        }
        for a in aberturas
    ]
