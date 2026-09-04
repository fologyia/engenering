"""Verificações preliminares de ligações estruturais em aço."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ResultadoLigacaoParafusada:
    resistencia_cisalhamento_parafusos_N: float
    resistencia_tracao_parafusos_N: float
    resistencia_pressao_contato_N: float
    resistencia_deslizamento_N: float
    interacao_parafuso: float
    fator_cisalhamento: float
    fator_tracao: float
    fator_contato: float
    fator_deslizamento: float


@dataclass(frozen=True)
class ResultadoChapaLigacao:
    resistencia_secao_liquida_N: float
    resistencia_cisalhamento_bloco_N: float
    fator_secao_liquida: float
    fator_cisalhamento_bloco: float


@dataclass(frozen=True)
class ResultadoSoldaFilete:
    area_efetiva_mm2: float
    resistencia_N: float
    fator_seguranca: float


def _positivo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor <= 0:
        raise ValueError(f"{nome} deve ser maior que zero.")
    return valor


def _nao_negativo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor < 0:
        raise ValueError(f"{nome} não pode ser negativo.")
    return valor


def _fracao(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or not 0 < valor <= 1:
        raise ValueError(f"{nome} deve estar em (0, 1].")
    return valor


def _fator(resistencia: float, solicitacao: float) -> float:
    if solicitacao <= 0:
        return math.inf
    return resistencia / solicitacao


def verificar_ligacao_parafusada(
    numero_parafusos: int,
    area_parafuso_mm2: float,
    fu_parafuso_MPa: float,
    coeficiente_cisalhamento: float,
    coeficiente_tracao: float,
    phi_parafuso: float,
    numero_planos_corte: int,
    forca_cortante_N: float,
    forca_tracao_N: float,
    espessura_chapa_mm: float,
    fu_chapa_MPa: float,
    diametro_parafuso_mm: float,
    distancia_livre_carga_mm: float,
    coeficiente_contato_lc: float,
    coeficiente_limite_contato: float,
    phi_contato: float,
    pre_tensao_parafuso_N: float,
    coeficiente_atrito: float,
    numero_interfaces_atrito: int,
    phi_deslizamento: float,
) -> ResultadoLigacaoParafusada:
    if int(numero_parafusos) != numero_parafusos or numero_parafusos < 1:
        raise ValueError("numero_parafusos deve ser um inteiro positivo.")
    if int(numero_planos_corte) != numero_planos_corte or numero_planos_corte < 1:
        raise ValueError("numero_planos_corte deve ser um inteiro positivo.")
    if (
        int(numero_interfaces_atrito) != numero_interfaces_atrito
        or numero_interfaces_atrito < 1
    ):
        raise ValueError("numero_interfaces_atrito deve ser inteiro positivo.")
    n = int(numero_parafusos)
    nc = int(numero_planos_corte)
    ns = int(numero_interfaces_atrito)
    ab = _positivo("area_parafuso_mm2", area_parafuso_mm2)
    fu_b = _positivo("fu_parafuso_MPa", fu_parafuso_MPa)
    cnv = _positivo("coeficiente_cisalhamento", coeficiente_cisalhamento)
    cnt = _positivo("coeficiente_tracao", coeficiente_tracao)
    phi_b = _fracao("phi_parafuso", phi_parafuso)
    vd = _nao_negativo("forca_cortante_N", forca_cortante_N)
    td = _nao_negativo("forca_tracao_N", forca_tracao_N)
    t = _positivo("espessura_chapa_mm", espessura_chapa_mm)
    fu_p = _positivo("fu_chapa_MPa", fu_chapa_MPa)
    d = _positivo("diametro_parafuso_mm", diametro_parafuso_mm)
    lc = _positivo("distancia_livre_carga_mm", distancia_livre_carga_mm)
    c_lc = _positivo("coeficiente_contato_lc", coeficiente_contato_lc)
    c_lim = _positivo(
        "coeficiente_limite_contato", coeficiente_limite_contato
    )
    phi_c = _fracao("phi_contato", phi_contato)
    tb = _nao_negativo("pre_tensao_parafuso_N", pre_tensao_parafuso_N)
    mu = _nao_negativo("coeficiente_atrito", coeficiente_atrito)
    phi_s = _fracao("phi_deslizamento", phi_deslizamento)

    rv = n * nc * phi_b * cnv * fu_b * ab
    rt = n * phi_b * cnt * fu_b * ab
    contato_por_furo = phi_c * min(
        c_lc * lc * t * fu_p,
        c_lim * d * t * fu_p,
    )
    rc = n * contato_por_furo
    rs = phi_s * mu * ns * n * tb
    interacao = (
        (vd / rv) ** 2 + (td / rt) ** 2
        if rv > 0 and rt > 0
        else math.inf
    )
    return ResultadoLigacaoParafusada(
        resistencia_cisalhamento_parafusos_N=rv,
        resistencia_tracao_parafusos_N=rt,
        resistencia_pressao_contato_N=rc,
        resistencia_deslizamento_N=rs,
        interacao_parafuso=interacao,
        fator_cisalhamento=_fator(rv, vd),
        fator_tracao=_fator(rt, td),
        fator_contato=_fator(rc, vd),
        fator_deslizamento=_fator(rs, vd),
    )


def verificar_chapa_ligacao(
    fu_chapa_MPa: float,
    fy_chapa_MPa: float,
    area_liquida_tracao_mm2: float,
    area_bruta_cisalhamento_mm2: float,
    area_liquida_cisalhamento_mm2: float,
    area_liquida_tracao_bloco_mm2: float,
    fator_distribuicao_tracao: float,
    phi_ruptura: float,
    forca_solicitante_N: float,
) -> ResultadoChapaLigacao:
    fu = _positivo("fu_chapa_MPa", fu_chapa_MPa)
    fy = _positivo("fy_chapa_MPa", fy_chapa_MPa)
    ant = _positivo("area_liquida_tracao_mm2", area_liquida_tracao_mm2)
    agv = _positivo(
        "area_bruta_cisalhamento_mm2", area_bruta_cisalhamento_mm2
    )
    anv = _positivo(
        "area_liquida_cisalhamento_mm2", area_liquida_cisalhamento_mm2
    )
    ant_bloco = _positivo(
        "area_liquida_tracao_bloco_mm2", area_liquida_tracao_bloco_mm2
    )
    ubs = _fracao("fator_distribuicao_tracao", fator_distribuicao_tracao)
    phi = _fracao("phi_ruptura", phi_ruptura)
    sd = _nao_negativo("forca_solicitante_N", forca_solicitante_N)

    rd_liquida = phi * fu * ant
    rn_bloco_1 = 0.60 * fy * agv + ubs * fu * ant_bloco
    rn_bloco_2 = 0.60 * fu * anv + ubs * fu * ant_bloco
    rd_bloco = phi * min(rn_bloco_1, rn_bloco_2)
    return ResultadoChapaLigacao(
        resistencia_secao_liquida_N=rd_liquida,
        resistencia_cisalhamento_bloco_N=rd_bloco,
        fator_secao_liquida=_fator(rd_liquida, sd),
        fator_cisalhamento_bloco=_fator(rd_bloco, sd),
    )


def verificar_solda_filete(
    tamanho_perna_mm: float,
    comprimento_total_mm: float,
    resistencia_eletrodo_MPa: float,
    coeficiente_resistencia_solda: float,
    phi_solda: float,
    forca_solicitante_N: float,
) -> ResultadoSoldaFilete:
    perna = _positivo("tamanho_perna_mm", tamanho_perna_mm)
    comprimento = _positivo("comprimento_total_mm", comprimento_total_mm)
    fexx = _positivo("resistencia_eletrodo_MPa", resistencia_eletrodo_MPa)
    coeficiente = _positivo(
        "coeficiente_resistencia_solda", coeficiente_resistencia_solda
    )
    phi = _fracao("phi_solda", phi_solda)
    sd = _nao_negativo("forca_solicitante_N", forca_solicitante_N)
    area = 0.707 * perna * comprimento
    resistencia = phi * coeficiente * fexx * area
    return ResultadoSoldaFilete(
        area_efetiva_mm2=area,
        resistencia_N=resistencia,
        fator_seguranca=_fator(resistencia, sd),
    )
