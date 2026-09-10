"""Flambagem geral de colunas: esbeltez, Euler e transição de Johnson.

Este módulo é deliberadamente independente de qualquer norma de aço: cobre
o modelo clássico de Euler/Johnson válido para qualquer material e seção
(retangular, circular, tubular, perfil de catálogo ou área/raio de giração
informados diretamente). Para o dimensionamento normativo de perfis de aço
(NBR 8800/AISC, com o fator de redução χ), veja
:mod:`core.steel_member_design`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core.steel_sections import PerfilAco


@dataclass(frozen=True)
class GeometriaColuna:
    """Área e raios de giração nos dois eixos principais da seção."""

    area_mm2: float
    raio_giracao_x_mm: float
    raio_giracao_y_mm: float
    descricao: str = ""


@dataclass(frozen=True)
class ResultadoFlambagem:
    comprimento_efetivo_x_mm: float
    comprimento_efetivo_y_mm: float
    esbeltez_x: float
    esbeltez_y: float
    esbeltez_governante: float
    eixo_governante: str
    esbeltez_transicao: float
    regime: str
    carga_critica_euler_N: float
    tensao_critica_MPa: float
    carga_critica_N: float
    carga_admissivel_N: float
    fator_seguranca: float
    utilizacao: float


# Fator de comprimento efetivo K por condição de apoio idealizada (valores
# teóricos usuais). Condições reais quase sempre ficam entre estes casos —
# o engenheiro deve escolher o mais próximo e favorável à segurança.
CONDICOES_APOIO: dict[str, float] = {
    "Biapoiada (pino-pino)": 1.0,
    "Engastada-livre (em balanço)": 2.0,
    "Engastada-pino": 0.70,
    "Biengastada": 0.50,
}


def _positivo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor <= 0:
        raise ValueError(f"{nome} deve ser um número finito maior que zero.")
    return valor


def _nao_negativo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor < 0:
        raise ValueError(f"{nome} não pode ser negativo.")
    return valor


def geometria_retangular(largura_mm: float, altura_mm: float) -> GeometriaColuna:
    """Seção retangular maciça. ``largura`` e ``altura`` são os dois lados."""
    b = _positivo("largura_mm", largura_mm)
    h = _positivo("altura_mm", altura_mm)
    area = b * h
    ix = b * h**3 / 12.0
    iy = h * b**3 / 12.0
    return GeometriaColuna(
        area_mm2=area,
        raio_giracao_x_mm=math.sqrt(ix / area),
        raio_giracao_y_mm=math.sqrt(iy / area),
        descricao=f"Retangular {b:g} × {h:g} mm",
    )


def geometria_circular_macica(diametro_mm: float) -> GeometriaColuna:
    d = _positivo("diametro_mm", diametro_mm)
    area = math.pi * d**2 / 4.0
    inercia = math.pi * d**4 / 64.0
    raio = math.sqrt(inercia / area)
    return GeometriaColuna(area, raio, raio, f"Circular maciça, d = {d:g} mm")


def geometria_circular_vazada(
    diametro_externo_mm: float, diametro_interno_mm: float
) -> GeometriaColuna:
    de = _positivo("diametro_externo_mm", diametro_externo_mm)
    di = _nao_negativo("diametro_interno_mm", diametro_interno_mm)
    if di >= de:
        raise ValueError("O diâmetro interno deve ser menor que o externo.")
    area = math.pi / 4.0 * (de**2 - di**2)
    inercia = math.pi / 64.0 * (de**4 - di**4)
    raio = math.sqrt(inercia / area)
    return GeometriaColuna(area, raio, raio, f"Tubular d={de:g}/{di:g} mm")


def geometria_perfil_catalogo(perfil: PerfilAco) -> GeometriaColuna:
    return GeometriaColuna(
        area_mm2=perfil.area_mm2,
        raio_giracao_x_mm=perfil.rx_mm,
        raio_giracao_y_mm=perfil.ry_mm,
        descricao=f"Perfil {perfil.nome}",
    )


def geometria_direta(
    area_mm2: float,
    raio_giracao_mm: float,
    raio_giracao_y_mm: float | None = None,
    descricao: str = "Área e raio de giração informados diretamente",
) -> GeometriaColuna:
    """Para seções fora do catálogo: informe A e r já calculados à parte.

    Se a seção for assimétrica (r diferente em cada eixo), informe
    ``raio_giracao_y_mm``; caso contrário os dois eixos usam o mesmo raio.
    """
    area = _positivo("area_mm2", area_mm2)
    rx = _positivo("raio_giracao_mm", raio_giracao_mm)
    ry = _positivo("raio_giracao_y_mm", raio_giracao_y_mm) if raio_giracao_y_mm else rx
    return GeometriaColuna(area, rx, ry, descricao)


def verificar_flambagem(
    *,
    geometria: GeometriaColuna,
    comprimento_mm: float,
    kx: float,
    ky: float,
    modulo_elasticidade_MPa: float,
    escoamento_MPa: float,
    forca_solicitante_N: float,
    fator_seguranca_desejado: float = 2.0,
) -> ResultadoFlambagem:
    """Verifica flambagem por Euler, com transição de Johnson para colunas curtas.

    O modelo assume compressão centrada, coluna prismática e material
    elástico linear até a transição — ver :func:`core.column_buckling` para
    o que fica deliberadamente fora do escopo (imperfeições, excentricidade,
    flambagem local, torcional/flexo-torcional).
    """
    area = _positivo("area_mm2", geometria.area_mm2)
    rx = _positivo("raio_giracao_x_mm", geometria.raio_giracao_x_mm)
    ry = _positivo("raio_giracao_y_mm", geometria.raio_giracao_y_mm)
    l = _positivo("comprimento_mm", comprimento_mm)
    kx = _positivo("kx", kx)
    ky = _positivo("ky", ky)
    e = _positivo("modulo_elasticidade_MPa", modulo_elasticidade_MPa)
    sy = _positivo("escoamento_MPa", escoamento_MPa)
    solicitante = _nao_negativo("forca_solicitante_N", forca_solicitante_N)
    fs_desejado = _positivo("fator_seguranca_desejado", fator_seguranca_desejado)

    lx = kx * l
    ly = ky * l
    esbeltez_x = lx / rx
    esbeltez_y = ly / ry
    if esbeltez_x >= esbeltez_y:
        esbeltez_governante, eixo_governante = esbeltez_x, "x"
    else:
        esbeltez_governante, eixo_governante = esbeltez_y, "y"

    esbeltez_transicao = math.sqrt(2.0 * math.pi**2 * e / sy)
    tensao_euler = math.pi**2 * e / esbeltez_governante**2
    if esbeltez_governante >= esbeltez_transicao:
        regime = "Euler (coluna longa)"
        tensao_critica = tensao_euler
    else:
        regime = "Johnson (coluna curta/intermediária)"
        tensao_critica = sy - (sy**2 / (4.0 * math.pi**2 * e)) * esbeltez_governante**2

    carga_critica_euler = tensao_euler * area
    carga_critica = tensao_critica * area
    carga_admissivel = carga_critica / fs_desejado
    fator_seguranca = math.inf if solicitante <= 0 else carga_critica / solicitante
    utilizacao = 0.0 if carga_admissivel <= 0 else solicitante / carga_admissivel

    return ResultadoFlambagem(
        comprimento_efetivo_x_mm=lx,
        comprimento_efetivo_y_mm=ly,
        esbeltez_x=esbeltez_x,
        esbeltez_y=esbeltez_y,
        esbeltez_governante=esbeltez_governante,
        eixo_governante=eixo_governante,
        esbeltez_transicao=esbeltez_transicao,
        regime=regime,
        carga_critica_euler_N=carga_critica_euler,
        tensao_critica_MPa=tensao_critica,
        carga_critica_N=carga_critica,
        carga_admissivel_N=carga_admissivel,
        fator_seguranca=fator_seguranca,
        utilizacao=utilizacao,
    )
