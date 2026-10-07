"""Cargas do vento num pórtico transversal de galpão e solução rápida pelo solver 2D do programa.

O pórtico é o plano y–z de :mod:`core.vento_edificio`: pilar esquerdo (y = 0), duas metades de
rafter (a esquerda e a direita do meio do vão) e pilar direito (y = b). Cada metade recebe a pressão
líquida ``q·(C_e − c_pi)`` da zona que a cobre, vezes o espaçamento ``s`` entre pórticos, e vira uma
carga por metro **normal ao elemento**: positiva quando a pressão empurra o elemento para dentro da
edificação (sobrepressão); negativa quando o puxa para fora (sucção).

No vento a ±90° as zonas são as mesmas ao longo de ``a``; no vento a 0° mudam com a posição do
pórtico em relação à empena de barlavento, e por isso o resultado traz uma linha por faixa.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core import structural_2d as estrutural
from core import vento_coeficientes as coef
from core.vento_edificio import (
    COBERTURA_UMA_AGUA,
    CasoDeVento,
    GeometriaEdificio,
    ResultadoEdificio,
)

#: ids dos elementos, nesta ordem (também a ordem dos nós 1 → 5 do modelo).
PILAR_ESQUERDO = "pilar_esquerdo"
AGUA_ESQUERDA = "agua_esquerda"
AGUA_DIREITA = "agua_direita"
PILAR_DIREITO = "pilar_direito"
MEMBROS = (PILAR_ESQUERDO, AGUA_ESQUERDA, AGUA_DIREITA, PILAR_DIREITO)

ROTULOS_MEMBROS: dict[str, str] = {
    PILAR_ESQUERDO: "Pilar esquerdo (y = 0)",
    AGUA_ESQUERDA: "Água esquerda (rafter até o meio do vão)",
    AGUA_DIREITA: "Água direita (do meio do vão ao pilar direito)",
    PILAR_DIREITO: "Pilar direito (y = b)",
}


ROTULOS_CURTOS_MEMBROS: dict[str, str] = {
    PILAR_ESQUERDO: "Pilar esq.",
    AGUA_ESQUERDA: "Água esq.",
    AGUA_DIREITA: "Água dir.",
    PILAR_DIREITO: "Pilar dir.",
}


@dataclass(frozen=True, slots=True)
class Membro:
    id: str
    no_i: int
    no_j: int
    #: nós em (y, z), metros
    p_i: tuple[float, float]
    p_j: tuple[float, float]
    #: normal externa unitária (y, z) — aponta para fora da edificação
    normal_externa: tuple[float, float]

    @property
    def comprimento_m(self) -> float:
        return math.hypot(self.p_j[0] - self.p_i[0], self.p_j[1] - self.p_i[1])


@dataclass(frozen=True, slots=True)
class GeometriaPortico:
    nos: tuple[tuple[float, float], ...]
    membros: tuple[Membro, ...]

    def membro(self, id_: str) -> Membro:
        for membro in self.membros:
            if membro.id == id_:
                return membro
        raise KeyError(id_)


def geometria_do_portico(g: GeometriaEdificio) -> GeometriaPortico:
    """Nós (y, z) e normais externas: 1 base esquerda, 2 beiral esquerdo, 3 meio do vão, 4 beiral
    direito, 5 base direita. O pilar direito vai da base (5) ao beiral (4)."""
    b = g.b_m
    z_meio = (g.h_parede_y0_m + g.h_parede_yb_m) / 2.0
    if g.cobertura != COBERTURA_UMA_AGUA:
        z_meio = g.h_topo_m
    nos = (
        (0.0, 0.0),
        (0.0, g.h_parede_y0_m),
        (b / 2.0, z_meio),
        (b, g.h_parede_yb_m),
        (b, 0.0),
    )
    seno, cosseno = g.sin_theta, g.cos_theta
    if g.cobertura == COBERTURA_UMA_AGUA:  # a água inteira desce para +y
        n_esq = n_dir = (seno, cosseno)
    else:  # plana: seno = 0, as duas normais são (0, 1)
        n_esq, n_dir = (-seno, cosseno), (seno, cosseno)
    membros = (
        Membro(PILAR_ESQUERDO, 1, 2, nos[0], nos[1], (-1.0, 0.0)),
        Membro(AGUA_ESQUERDA, 2, 3, nos[1], nos[2], n_esq),
        Membro(AGUA_DIREITA, 3, 4, nos[2], nos[3], n_dir),
        Membro(PILAR_DIREITO, 5, 4, nos[4], nos[3], (1.0, 0.0)),
    )
    return GeometriaPortico(nos, membros)


@dataclass(frozen=True, slots=True)
class CargaNoMembro:
    membro: str
    zona: str
    ce: float
    pressao_liquida_kN_m2: float
    #: pressão líquida × espaçamento: kN por metro de elemento, normal a ele
    carga_kN_m: float


@dataclass(frozen=True, slots=True)
class CasoPortico:
    nome: str
    alpha: int
    cpi: coef.SugestaoCpi
    #: faixa de ``x`` (distância da empena de barlavento) a que o caso se aplica; ``None`` a ±90°
    faixa_x_m: tuple[float, float] | None
    cargas: tuple[CargaNoMembro, ...]

    def carga(self, membro: str) -> CargaNoMembro:
        for item in self.cargas:
            if item.membro == membro:
                return item
        raise KeyError(membro)


def _carga(caso: CasoDeVento, membro: str, id_zona: str, espacamento: float) -> CargaNoMembro:
    pressao = next(p for p in caso.pressoes if p.zona.id == id_zona)
    liquida = pressao.pressao_liquida_kN_m2
    return CargaNoMembro(membro, pressao.zona.nome, pressao.zona.ce, liquida, liquida * espacamento)


def casos_do_portico(resultado: ResultadoEdificio) -> list[CasoPortico]:
    """Cargas do pórtico por direção do vento, por ``c_pi`` e, a 0°, por faixa de posição."""
    entrada = resultado.entrada
    g = resultado.geometria
    s = entrada.espacamento_porticos_m
    uma_agua = entrada.cobertura == COBERTURA_UMA_AGUA
    a, b, x1 = g.a_m, g.b_m, g.x_m
    saida: list[CasoPortico] = []
    for caso in resultado.casos:
        alpha = caso.alpha
        if alpha in (90, -90):
            if alpha == 90:
                parede_esq, parede_dir = "A", "B"
                agua_esq, agua_dir = ("HI", "LJ") if uma_agua else ("EFI", "GHJ")
            else:
                parede_esq, parede_dir = "B", "A"
                agua_esq, agua_dir = "HI", "LJ"
            cargas = (
                _carga(caso, PILAR_ESQUERDO, parede_esq, s),
                _carga(caso, AGUA_ESQUERDA, agua_esq, s),
                _carga(caso, AGUA_DIREITA, agua_dir, s),
                _carga(caso, PILAR_DIREITO, parede_dir, s),
            )
            saida.append(CasoPortico(caso.nome, alpha, caso.cpi, None, cargas))
            continue
        # Vento a 0°: as faixas de x onde mudam a zona da parede ou a do telhado.
        pontos = sorted({0.0, x1, a / 2.0, a} | ({b / 2.0} if uma_agua else set()))
        pontos = [p for p in pontos if 0.0 <= p <= a]
        for inicio, fim in zip(pontos, pontos[1:], strict=False):
            if fim - inicio < 1e-9:
                continue
            meio = (inicio + fim) / 2.0
            parede = "A1B1" if meio < x1 else ("A2B2" if meio < a / 2.0 else "A3B3")
            if uma_agua:
                telhado = (
                    "HL_ate_b2" if meio < b / 2.0 else ("HL_de_b2" if meio < a / 2.0 else "IJ")
                )
            else:
                telhado = "EG" if meio < x1 else ("FH" if meio < a / 2.0 else "IJ")
            cargas = (
                _carga(caso, PILAR_ESQUERDO, parede, s),
                _carga(caso, AGUA_ESQUERDA, telhado, s),
                _carga(caso, AGUA_DIREITA, telhado, s),
                _carga(caso, PILAR_DIREITO, parede, s),
            )
            saida.append(CasoPortico(caso.nome, alpha, caso.cpi, (inicio, fim), cargas))
    return saida


def tabela_do_portico(casos: list[CasoPortico]) -> list[dict[str, object]]:
    """Uma linha por caso e por elemento, para a tela e o memorial."""
    linhas: list[dict[str, object]] = []
    for caso in casos:
        faixa = (
            "toda a extensão"
            if caso.faixa_x_m is None
            else f"{caso.faixa_x_m[0]:.2f} a {caso.faixa_x_m[1]:.2f} m".replace(".", ",")
        )
        for item in caso.cargas:
            linhas.append(
                {
                    "Caso": caso.nome,
                    "Faixa a partir da empena de barlavento": faixa,
                    "Elemento": ROTULOS_MEMBROS[item.membro],
                    "Zona": item.zona,
                    "C_e": item.ce,
                    "Δp (kN/m²)": item.pressao_liquida_kN_m2,
                    "Carga normal (kN/m)": item.carga_kN_m,
                }
            )
    return linhas


def tabela_compacta_do_portico(casos: list[CasoPortico]) -> list[dict[str, object]]:
    """Uma linha por caso, com a carga normal (kN/m) de cada elemento — a leitura rápida."""
    linhas: list[dict[str, object]] = []
    for caso in casos:
        faixa = (
            "toda a extensão"
            if caso.faixa_x_m is None
            else f"{caso.faixa_x_m[0]:.1f} a {caso.faixa_x_m[1]:.1f} m".replace(".", ",")
        )
        linha: dict[str, object] = {"Caso": caso.nome, "Faixa (da empena de barlavento)": faixa}
        for id_ in MEMBROS:
            linha[ROTULOS_CURTOS_MEMBROS[id_] + " (kN/m)"] = caso.carga(id_).carga_kN_m
        linhas.append(linha)
    return linhas


# ---------------------------------------------------------------------------
# Solução pelo solver 2D
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SecaoDoElemento:
    area_mm2: float
    inercia_mm4: float
    modulo_elasticidade_MPa: float = 200_000.0


@dataclass(frozen=True, slots=True)
class SolucaoPortico:
    caso: CasoPortico
    reacoes: tuple[dict[str, float | int], ...]
    esforcos: tuple[dict[str, float | int | str], ...]
    #: deslocamentos de cada nó (mm), com sinal: x é a direção de b (y da edificação), y é vertical
    deslocamentos: tuple[dict[str, float | int], ...]
    deslocamento_horizontal_max_mm: float
    deslocamento_vertical_max_mm: float
    avisos: tuple[str, ...]
    soma_cargas_horizontais_kN: float
    soma_cargas_verticais_kN: float


def _carga_local_N_mm(membro: Membro, carga_kN_m: float) -> float:
    """Carga normal (positiva para dentro) na componente local y do solver; kN/m ≡ N/mm."""
    dx = membro.p_j[0] - membro.p_i[0]
    dz = membro.p_j[1] - membro.p_i[1]
    comprimento = math.hypot(dx, dz)
    local_y = (-dz / comprimento, dx / comprimento)
    para_dentro = (-membro.normal_externa[0], -membro.normal_externa[1])
    return carga_kN_m * (para_dentro[0] * local_y[0] + para_dentro[1] * local_y[1])


def resolver_portico(
    geometria: GeometriaPortico,
    caso: CasoPortico,
    *,
    pilar: SecaoDoElemento,
    rafter: SecaoDoElemento,
    bases_engastadas: bool = True,
) -> SolucaoPortico:
    """Pórtico plano sob o vento do ``caso``: reações, esforços nas extremidades e deslocamentos.

    As cargas são só as do vento (sem peso próprio nem sobrecarga); combinações com outras ações
    ficam em Casos e combinações de carga.
    """
    nos = []
    for indice, (y, z) in enumerate(geometria.nos, start=1):
        base = indice in (1, 5)
        nos.append(
            estrutural.NoPortico(
                indice,
                y * 1000.0,
                z * 1000.0,
                restringe_x=base,
                restringe_y=base,
                restringe_rotacao=base and bases_engastadas,
            )
        )
    elementos = []
    soma_h = soma_v = 0.0
    for numero, membro in enumerate(geometria.membros, start=1):
        secao = pilar if membro.id in (PILAR_ESQUERDO, PILAR_DIREITO) else rafter
        carga = caso.carga(membro.id).carga_kN_m
        elementos.append(
            estrutural.ElementoPortico(
                numero,
                membro.no_i,
                membro.no_j,
                secao.area_mm2,
                secao.inercia_mm4,
                secao.modulo_elasticidade_MPa,
                _carga_local_N_mm(membro, carga),
            )
        )
        # Força sobre o elemento: pressão positiva empurra para dentro (−normal externa).
        soma_h += -carga * membro.normal_externa[0] * membro.comprimento_m
        soma_v += -carga * membro.normal_externa[1] * membro.comprimento_m
    resultado = estrutural.analisar_portico(nos, elementos)
    esforcos: list[dict[str, float | int | str]] = []
    for item in resultado.esforcos_elementos:
        membro = geometria.membros[int(item["elemento"]) - 1]
        esforcos.append(
            {
                "elemento": ROTULOS_MEMBROS[membro.id],
                "N_i (kN)": item["Ni_N"] / 1e3,
                "V_i (kN)": item["Vi_N"] / 1e3,
                "M_i (kN·m)": item["Mi_Nmm"] / 1e6,
                "N_j (kN)": item["Nj_N"] / 1e3,
                "V_j (kN)": item["Vj_N"] / 1e3,
                "M_j (kN·m)": item["Mj_Nmm"] / 1e6,
            }
        )
    reacoes = tuple(
        {
            "no": int(r["no"]),
            "Rh (kN)": r["rx_N"] / 1e3,
            "Rv (kN)": r["ry_N"] / 1e3,
            "M (kN·m)": r["mz_Nmm"] / 1e6,
        }
        for r in resultado.reacoes_nodais
        if int(r["no"]) in (1, 5)
    )
    return SolucaoPortico(
        caso=caso,
        reacoes=reacoes,
        esforcos=tuple(esforcos),
        deslocamentos=tuple(
            {"no": int(d["no"]), "ux_mm": float(d["ux_mm"]), "uy_mm": float(d["uy_mm"])}
            for d in resultado.deslocamentos_nodais
        ),
        deslocamento_horizontal_max_mm=max(abs(d["ux_mm"]) for d in resultado.deslocamentos_nodais),
        deslocamento_vertical_max_mm=max(abs(d["uy_mm"]) for d in resultado.deslocamentos_nodais),
        avisos=resultado.avisos,
        soma_cargas_horizontais_kN=soma_h,
        soma_cargas_verticais_kN=soma_v,
    )
