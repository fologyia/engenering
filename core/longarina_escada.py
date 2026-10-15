"""Longarina da escada em grade: viga biapoiada inclinada que recebe metade de cada degrau.

A longarina vence o lance maior da escada (:mod:`core.degrau_escada`) entre os dois apoios — o pé e
o patamar ou a plataforma. Cada uma das duas longarinas recebe metade da largura do degrau:

* **sobrecarga** ``q`` (kN/m² em planta) × L/2 → kN por metro **horizontal**;
* **peso dos degraus**: meio degrau a cada piso ``b`` → kN por metro horizontal;
* **guarda-corpo** (kN/m ao longo da longarina) e o **peso próprio** do perfil.

As cargas verticais por metro horizontal viram, ao longo da barra inclinada de ângulo α, uma carga
perpendicular ``w·cos²α`` por metro inclinado; a parcela ``w·sen α·cos α`` corre ao longo da barra
(esforço normal, informativo). Com o vão inclinado ``L = L_h / cos α`` o momento é o mesmo da viga
horizontal de vão ``L_h`` (``w·L_h²/8``). A verificação é a da viga de piso
(:mod:`core.viga_de_piso`: NBR 8800 — flexão com FLT, FLM e FLA, cortante, flecha — e o critério
Anglo), com o comprimento destravado igual à distância entre degraus ao longo da longarina (cada
degrau trava a mesa superior). O peso próprio entra inteiro perpendicular à barra (a favor da
segurança).

Deslocamentos: a flecha perpendicular ``δ`` da viga inclinada e o **deslocamento vertical**
``δ / cos α`` (o que o SolidWorks mostra em DY). O vão horizontal, se não for informado, é a
projeção horizontal do lance maior.

Sem Streamlit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from core import degrau_escada as de
from core import viga_de_piso as vp
from core.verificacao import Verificacao, status_geral

G = 9.80665
LIMITE_FLECHA = 350.0  # NBR 8800 Anexo C — vigas de piso; Anglo Tabela 3 — principais


class LongarinaInvalida(ValueError):
    """Dado que o cálculo não aceita; a mensagem diz o que corrigir."""


@dataclass(frozen=True)
class EntradaLongarina:
    perfil: str = 'U 8" x 17,10'
    aco: str = "ASTM A36"
    vao_horizontal_m: float | None = None  # vazio = projeção horizontal do lance maior
    guarda_corpo_kN_m: float = 0.40
    norma: str = "NBR8800_2024"
    anglo: bool = False


@dataclass(frozen=True)
class ResultadoLongarina:
    entrada: EntradaLongarina
    alfa_graus: float
    vao_horizontal_m: float
    vao_informado: bool
    vao_inclinado_m: float
    lb_m: float
    carga_sc_kN_m: float  # por metro horizontal (vertical)
    carga_degraus_kN_m: float
    carga_gc_kN_m: float  # por metro inclinado
    viga: vp.ResultadoVigaDePiso
    flecha_perpendicular_mm: float
    deslocamento_vertical_mm: float
    deslocamento_vertical_sc_mm: float
    limite_flecha_mm: float
    reacao_vertical_kN: float  # característica, em cada apoio
    normal_kN: float  # característica, parcela ao longo da barra (informativo)

    @property
    def verificacoes(self) -> tuple[Verificacao, ...]:
        return self.viga.verificacoes

    @property
    def status(self) -> str:
        return status_geral(list(self.verificacoes))

    @property
    def aproveitamento_maximo(self) -> float:
        return self.viga.aproveitamento_maximo


def calcular_longarina(r: de.ResultadoEscada, e: EntradaLongarina) -> ResultadoLongarina:
    """A longarina do lance maior da escada calculada em ``r``."""
    g, ln, entrada = r.geometria, r.lances, r.entrada
    alfa = math.radians(g.alfa_graus)
    cos_a = math.cos(alfa)
    informado = e.vao_horizontal_m is not None and e.vao_horizontal_m > 0
    vao_h = float(e.vao_horizontal_m) if informado else ln.projecao_lance_maior_mm / 1000.0
    if vao_h <= 0:
        raise LongarinaInvalida(
            "O lance maior não tem projeção horizontal (um degrau só): informe a distância "
            "horizontal entre os apoios da longarina."
        )
    if e.guarda_corpo_kN_m < 0:
        raise LongarinaInvalida("O peso do guarda-corpo não pode ser negativo.")
    vao = vao_h / cos_a
    metade = entrada.L_mm / 2000.0  # m de degrau que cada longarina recebe
    b_m = g.b_mm / 1000.0
    sc_h = entrada.q_kN_m2 * metade
    degraus_h = r.peso_unitario_kg * G / 1e3 / 2 / b_m
    # Perpendicular à barra, por metro inclinado: w·cos²α (a vertical por metro horizontal).
    viga = vp.calcular(
        vp.EntradaVigaDePiso(
            perfil=e.perfil,
            aco=e.aco,
            vao_m=vao,
            largura_influencia_m=1.0,
            lb_m=b_m / cos_a,
            pe_kN_m2=degraus_h * cos_a**2,
            sc_kN_m2=sc_h * cos_a**2,
            linear_extra_kN_m=e.guarda_corpo_kN_m * cos_a,
            tipo=vp.TIPO_PRINCIPAL,
            norma=e.norma,
            anglo=e.anglo,
        )
    )
    pp = viga.peso_proprio_kN_m
    vertical_h = sc_h + degraus_h + (e.guarda_corpo_kN_m + pp) / cos_a
    return ResultadoLongarina(
        entrada=e,
        alfa_graus=g.alfa_graus,
        vao_horizontal_m=vao_h,
        vao_informado=informado,
        vao_inclinado_m=vao,
        lb_m=b_m / cos_a,
        carga_sc_kN_m=sc_h,
        carga_degraus_kN_m=degraus_h,
        carga_gc_kN_m=e.guarda_corpo_kN_m,
        viga=viga,
        flecha_perpendicular_mm=viga.flecha_mm,
        deslocamento_vertical_mm=viga.flecha_mm / cos_a,
        deslocamento_vertical_sc_mm=viga.flecha_sobrecarga_mm / cos_a,
        limite_flecha_mm=vao * 1000.0 / LIMITE_FLECHA,
        reacao_vertical_kN=vertical_h * vao_h / 2,
        normal_kN=vertical_h * vao_h * math.sin(alfa) / 2,
    )


def com_perfil(e: EntradaLongarina, perfil: str) -> EntradaLongarina:
    return replace(e, perfil=perfil)
