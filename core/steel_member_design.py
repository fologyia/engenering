"""Pré-dimensionamento de barras de aço por estados-limite.

As equações são compatíveis com práticas usuais de projeto por estados-limite,
mas os coeficientes são argumentos explícitos e devem ser confirmados na norma
aplicável.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from core.steel_sections import PerfilAco


@dataclass(frozen=True)
class ResultadoTracao:
    resistencia_escoamento_N: float
    resistencia_ruptura_N: float
    resistencia_governante_N: float
    modo_governante: str
    utilizacao: float


@dataclass(frozen=True)
class ResultadoCompressao:
    esbeltez_x: float
    esbeltez_y: float
    carga_euler_x_N: float
    carga_euler_y_N: float
    indice_esbeltez_reduzido: float
    fator_reducao_chi: float
    resistencia_N: float
    utilizacao: float


@dataclass(frozen=True)
class ResultadoFlexao:
    resistencia_secao_Nmm: float
    momento_critico_ltb_Nmm: float
    resistencia_flexao_Nmm: float
    resistencia_cisalhamento_N: float
    utilizacao_momento: float
    utilizacao_cisalhamento: float


@dataclass(frozen=True)
class ResultadoInteracao:
    razao_axial: float
    razao_momento_x: float
    razao_momento_y: float
    indice_interacao: float
    atende: bool


@dataclass(frozen=True)
class ResultadoDeflexao:
    deflexao_total_mm: float
    limite_mm: float
    razao_vao_deflexao: float
    utilizacao: float


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


def _fracao(nome: str, valor: float, aceita_zero: bool = False) -> float:
    valor = float(valor)
    minimo_valido = valor >= 0 if aceita_zero else valor > 0
    if not math.isfinite(valor) or not minimo_valido or valor > 1:
        intervalo = "[0, 1]" if aceita_zero else "(0, 1]"
        raise ValueError(f"{nome} deve estar em {intervalo}.")
    return valor


def _utilizacao(solicitacao: float, resistencia: float) -> float:
    solicitacao = _nao_negativo("solicitacao", solicitacao)
    resistencia = _positivo("resistencia", resistencia)
    return solicitacao / resistencia


def verificar_tracao(
    perfil: PerfilAco,
    fy_MPa: float,
    fu_MPa: float,
    area_liquida_mm2: float,
    coeficiente_reducao_area: float,
    forca_solicitante_N: float,
    phi_escoamento: float = 0.90,
    phi_ruptura: float = 0.75,
) -> ResultadoTracao:
    fy = _positivo("fy_MPa", fy_MPa)
    fu = _positivo("fu_MPa", fu_MPa)
    an = _positivo("area_liquida_mm2", area_liquida_mm2)
    if an > perfil.area_mm2:
        raise ValueError("A área líquida não pode superar a área bruta.")
    ct = _fracao("coeficiente_reducao_area", coeficiente_reducao_area)
    phi_y = _fracao("phi_escoamento", phi_escoamento)
    phi_u = _fracao("phi_ruptura", phi_ruptura)
    solicitante = _nao_negativo("forca_solicitante_N", forca_solicitante_N)

    rd_y = phi_y * fy * perfil.area_mm2
    rd_u = phi_u * fu * ct * an
    if rd_y <= rd_u:
        governante, modo = rd_y, "Escoamento da seção bruta"
    else:
        governante, modo = rd_u, "Ruptura da seção líquida efetiva"
    return ResultadoTracao(
        resistencia_escoamento_N=rd_y,
        resistencia_ruptura_N=rd_u,
        resistencia_governante_N=governante,
        modo_governante=modo,
        utilizacao=_utilizacao(solicitante, governante),
    )


def verificar_compressao(
    perfil: PerfilAco,
    fy_MPa: float,
    modulo_elasticidade_MPa: float,
    comprimento_mm: float,
    kx: float,
    ky: float,
    fator_local_Q: float,
    forca_solicitante_N: float,
    phi_compressao: float = 0.90,
) -> ResultadoCompressao:
    fy = _positivo("fy_MPa", fy_MPa)
    e = _positivo("modulo_elasticidade_MPa", modulo_elasticidade_MPa)
    l = _positivo("comprimento_mm", comprimento_mm)
    kx = _positivo("kx", kx)
    ky = _positivo("ky", ky)
    q = _fracao("fator_local_Q", fator_local_Q)
    phi = _fracao("phi_compressao", phi_compressao)
    solicitante = _nao_negativo("forca_solicitante_N", forca_solicitante_N)

    lx = kx * l
    ly = ky * l
    esbeltez_x = lx / perfil.rx_mm
    esbeltez_y = ly / perfil.ry_mm
    ne_x = math.pi**2 * e * perfil.ix_mm4 / lx**2
    ne_y = math.pi**2 * e * perfil.iy_mm4 / ly**2
    ne = min(ne_x, ne_y)
    lambda_0 = math.sqrt(q * perfil.area_mm2 * fy / ne)
    if lambda_0 <= 1.5:
        chi = 0.658 ** (lambda_0**2)
    else:
        chi = 0.877 / lambda_0**2
    chi = min(1.0, chi)
    resistencia = phi * chi * q * perfil.area_mm2 * fy

    return ResultadoCompressao(
        esbeltez_x=esbeltez_x,
        esbeltez_y=esbeltez_y,
        carga_euler_x_N=ne_x,
        carga_euler_y_N=ne_y,
        indice_esbeltez_reduzido=lambda_0,
        fator_reducao_chi=chi,
        resistencia_N=resistencia,
        utilizacao=_utilizacao(solicitante, resistencia),
    )


def momento_critico_ltb(
    perfil: PerfilAco,
    modulo_elasticidade_MPa: float,
    modulo_cisalhamento_MPa: float,
    comprimento_destravado_mm: float,
    cb: float = 1.0,
) -> float:
    """Momento crítico elástico de LTB para perfil I duplamente simétrico."""
    e = _positivo("modulo_elasticidade_MPa", modulo_elasticidade_MPa)
    g = _positivo("modulo_cisalhamento_MPa", modulo_cisalhamento_MPa)
    lb = _positivo("comprimento_destravado_mm", comprimento_destravado_mm)
    cb = _positivo("cb", cb)
    if perfil.cw_mm6 <= 0:
        return math.inf
    termo = (
        e * perfil.iy_mm4 * g * perfil.j_mm4
        + (math.pi * e / lb) ** 2 * perfil.iy_mm4 * perfil.cw_mm6
    )
    return cb * math.pi / lb * math.sqrt(termo)


def verificar_flexao_cisalhamento(
    perfil: PerfilAco,
    fy_MPa: float,
    modulo_elasticidade_MPa: float,
    modulo_cisalhamento_MPa: float,
    comprimento_destravado_mm: float,
    momento_solicitante_Nmm: float,
    cortante_solicitante_N: float,
    cb: float = 1.0,
    fator_local_Q: float = 1.0,
    fator_reducao_cisalhamento: float = 1.0,
    phi_flexao: float = 0.90,
    phi_cisalhamento: float = 0.90,
) -> ResultadoFlexao:
    fy = _positivo("fy_MPa", fy_MPa)
    q = _fracao("fator_local_Q", fator_local_Q)
    cv = _fracao(
        "fator_reducao_cisalhamento", fator_reducao_cisalhamento
    )
    phi_b = _fracao("phi_flexao", phi_flexao)
    phi_v = _fracao("phi_cisalhamento", phi_cisalhamento)
    momento = _nao_negativo("momento_solicitante_Nmm", momento_solicitante_Nmm)
    cortante = _nao_negativo(
        "cortante_solicitante_N", cortante_solicitante_N
    )

    mn_secao = q * fy * perfil.zx_mm3
    mcr = momento_critico_ltb(
        perfil,
        modulo_elasticidade_MPa,
        modulo_cisalhamento_MPa,
        comprimento_destravado_mm,
        cb,
    )
    md = phi_b * min(mn_secao, mcr)
    vd = (
        phi_v
        * 0.60
        * fy
        * perfil.area_cisalhamento_mm2
        * cv
    )
    return ResultadoFlexao(
        resistencia_secao_Nmm=phi_b * mn_secao,
        momento_critico_ltb_Nmm=mcr,
        resistencia_flexao_Nmm=md,
        resistencia_cisalhamento_N=vd,
        utilizacao_momento=_utilizacao(momento, md),
        utilizacao_cisalhamento=_utilizacao(cortante, vd),
    )


def verificar_interacao(
    forca_solicitante_N: float,
    resistencia_axial_N: float,
    momento_x_Nmm: float,
    resistencia_momento_x_Nmm: float,
    momento_y_Nmm: float = 0.0,
    resistencia_momento_y_Nmm: float | None = None,
) -> ResultadoInteracao:
    n = _nao_negativo("forca_solicitante_N", forca_solicitante_N)
    nr = _positivo("resistencia_axial_N", resistencia_axial_N)
    mx = _nao_negativo("momento_x_Nmm", momento_x_Nmm)
    mrx = _positivo("resistencia_momento_x_Nmm", resistencia_momento_x_Nmm)
    my = _nao_negativo("momento_y_Nmm", momento_y_Nmm)
    if resistencia_momento_y_Nmm is None:
        if my > 0:
            raise ValueError("Informe a resistência à flexão no eixo y.")
        mry = 1.0
    else:
        mry = _positivo(
            "resistencia_momento_y_Nmm", resistencia_momento_y_Nmm
        )
    rn = n / nr
    rmx = mx / mrx
    rmy = my / mry
    if rn >= 0.20:
        indice = rn + 8.0 / 9.0 * (rmx + rmy)
    else:
        indice = rn / 2.0 + rmx + rmy
    return ResultadoInteracao(
        razao_axial=rn,
        razao_momento_x=rmx,
        razao_momento_y=rmy,
        indice_interacao=indice,
        atende=indice <= 1.0,
    )


def verificar_deflexao_viga(
    perfil: PerfilAco,
    modulo_elasticidade_MPa: float,
    comprimento_mm: float,
    carga_distribuida_N_mm: float,
    carga_concentrada_N: float,
    condicao: str,
    limite_relativo: float,
) -> ResultadoDeflexao:
    e = _positivo("modulo_elasticidade_MPa", modulo_elasticidade_MPa)
    l = _positivo("comprimento_mm", comprimento_mm)
    q = _nao_negativo("carga_distribuida_N_mm", carga_distribuida_N_mm)
    p = _nao_negativo("carga_concentrada_N", carga_concentrada_N)
    divisor = _positivo("limite_relativo", limite_relativo)
    ei = e * perfil.ix_mm4
    if condicao == "Biapoiada":
        delta_q = 5.0 * q * l**4 / (384.0 * ei)
        delta_p = p * l**3 / (48.0 * ei)
    elif condicao == "Balanço":
        delta_q = q * l**4 / (8.0 * ei)
        delta_p = p * l**3 / (3.0 * ei)
    else:
        raise ValueError("Condição deve ser 'Biapoiada' ou 'Balanço'.")
    delta = delta_q + delta_p
    limite = l / divisor
    return ResultadoDeflexao(
        deflexao_total_mm=delta,
        limite_mm=limite,
        razao_vao_deflexao=math.inf if delta == 0 else l / delta,
        utilizacao=delta / limite,
    )
