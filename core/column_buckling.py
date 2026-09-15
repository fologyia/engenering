"""Flambagem de colunas pela ABNT NBR 8800:2008 (método dos estados-limites).

Este módulo verifica uma barra comprimida — ou flexocomprimida — com as
equações **da norma**, e não com o modelo elementar de Euler/Johnson e um
fator de segurança global:

* **ações majoradas** (4.7 / Tabela 1): ``N_Sd = γ_g·N_g + γ_q·N_q``, ou
  ``N_Sd`` informado já de cálculo; a resistência é minorada por
  ``γ_a1 = 1,10`` (Tabela 3);
* **curva de flambagem** (5.3.3): ``λ_0 = √(Q·A_g·f_y/N_e)`` e
  ``χ = 0,658^(λ_0²)`` (``λ_0 ≤ 1,5``) ou ``0,877/λ_0²``, que já embute as
  imperfeições geométricas e as tensões residuais — a carga crítica de
  Euler entra só como ``N_e`` de referência;
* **flambagem local** (Anexo F): ``Q = Q_s·Q_a`` das esbeltezes das paredes;
* **flambagem por torção e flexo-torção** (Anexo E): ``N_ez`` e o modo
  acoplado das seções monossimétricas, além de ``N_ex`` e ``N_ey``;
* **flexocompressão** (5.5.1.2): momentos de excentricidade e/ou aplicados,
  amplificados por ``B_1 = C_m/(1 − N_Sd/N_e) ≥ 1`` (Anexo D), na equação
  de interação ``N_Sd/N_Rd + 8/9·(M_x,Sd/M_x,Rd + M_y,Sd/M_y,Rd) ≤ 1``
  (ou ``N_Sd/(2N_Rd) + …`` quando ``N_Sd/N_Rd < 0,2``).

As seções geométricas (retangular, circular, tubo) viram um
:class:`~core.steel_sections.PerfilAco` idealizado e seguem o mesmo caminho
dos perfis de catálogo em :mod:`core.nbr8800`. A opção de área e raio de
giração diretos não tem paredes nem constantes de torção: recebe ``Q = 1`` e
só flambagem por flexão, com aviso.

Unidades: N, mm, MPa e N·mm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core import nbr8800
from core.nbr8800 import ElementoDePlaca, ResultadoFlexaoNBR, ResultadoInteracaoNBR
from core.steel_sections import (
    PerfilAco,
    barra_circular,
    barra_retangular,
    centro_de_cisalhamento_do_perfil,
    tubo_circular,
)

GAMMA_A1 = nbr8800.GAMMA_A1
ESBELTEZ_MAXIMA = nbr8800.ESBELTEZ_MAXIMA_COMPRESSAO  # 5.3.4.1

# Coeficientes de ponderação das ações (Tabela 1, combinações normais):
# permanente de pequena variabilidade (estrutura metálica) 1,25; permanente
# de grande variabilidade ou variável em geral 1,40; equipamentos e
# sobrecargas 1,50. O padrão 1,40/1,40 é o par usual de pré-projeto.
GAMMA_G_PADRAO = 1.40
GAMMA_Q_PADRAO = 1.40
COEFICIENTES_PERMANENTE: dict[str, float] = {
    "Peso próprio de estrutura metálica (γ_g = 1,25)": 1.25,
    "Peso próprio de estrutura pré-moldada (γ_g = 1,30)": 1.30,
    "Elementos industrializados com adições in loco (γ_g = 1,40)": 1.40,
    "Elementos construtivos em geral e equipamentos (γ_g = 1,50)": 1.50,
}
COEFICIENTES_VARIAVEL: dict[str, float] = {
    "Vento (γ_q = 1,40)": 1.40,
    "Ações variáveis em geral / sobrecarga (γ_q = 1,50)": 1.50,
    "Ações truncadas / recalques (γ_q = 1,20)": 1.20,
}

# Coeficiente de Poisson do aço (NBR 8800 4.5.2.9: E = 200 000 MPa,
# G = 77 000 MPa → ν = 0,3).
POISSON_ACO = 0.3


# Fator de comprimento de flambagem K por condição de apoio idealizada
# (Tabela E.1 da NBR 8800, valores teóricos).
CONDICOES_APOIO: dict[str, float] = {
    "Biapoiada (pino-pino)": 1.0,
    "Engastada-livre (em balanço)": 2.0,
    "Engastada-pino": 0.70,
    "Biengastada": 0.50,
    "Biengastada com translação (deslocável)": 1.0,
    "Engastada-pino com translação (deslocável)": 2.0,
}

# Valores recomendados para projeto (Tabela E.1): ligações reais nunca são o
# engaste perfeito, então K sobe.
CONDICOES_APOIO_RECOMENDADAS: dict[str, float] = {
    "Biapoiada (pino-pino)": 1.0,
    "Engastada-livre (em balanço)": 2.1,
    "Engastada-pino": 0.80,
    "Biengastada": 0.65,
    "Biengastada com translação (deslocável)": 1.2,
    "Engastada-pino com translação (deslocável)": 2.0,
}

# Faixa física de K: 0,5 é o mínimo teórico (biengastada) e acima de 3 só
# em pórtico muito deslocável; fora disso quase sempre é erro de digitação.
K_MINIMO, K_MAXIMO = 0.5, 3.0


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


# ---------------------------------------------------------------------------
# Ações de cálculo
# ---------------------------------------------------------------------------


def forca_de_calculo(
    permanente_N: float,
    variavel_N: float = 0.0,
    *,
    gamma_g: float = GAMMA_G_PADRAO,
    gamma_q: float = GAMMA_Q_PADRAO,
) -> float:
    """``N_Sd = γ_g·N_g + γ_q·N_q`` (combinação normal, 4.7.7)."""
    ng = _nao_negativo("permanente_N", permanente_N)
    nq = _nao_negativo("variavel_N", variavel_N)
    gg = _positivo("gamma_g", gamma_g)
    gq = _positivo("gamma_q", gamma_q)
    return gg * ng + gq * nq


# ---------------------------------------------------------------------------
# Mão-francesa: força inclinada chegando na coluna
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EsforcosMaoFrancesa:
    """Componentes e momento que a mão-francesa descarrega na coluna.

    ``forca_N`` é a força de cálculo na barra da mão-francesa; ``theta`` é o
    ângulo entre a barra e o eixo da coluna. A componente horizontal ``H``
    flete a coluna com braço ``a`` (altura do nó em relação à base); a
    vertical ``V`` soma à compressão e, se chega fora do eixo, gera ``V·e``.
    """

    forca_N: float
    angulo_graus: float
    componente_vertical_N: float
    componente_horizontal_N: float
    altura_no_mm: float
    comprimento_mm: float
    vinculo: str
    excentricidade_mm: float
    momento_horizontal_Nmm: float
    momento_excentricidade_Nmm: float
    momento_Nmm: float
    expressao: str


# Momento máximo na coluna por uma força horizontal H aplicada a ``a`` da
# base, para os vínculos usuais da coluna no plano da mão-francesa.
VINCULOS_MAO_FRANCESA: tuple[str, ...] = (
    "Engastada na base, topo livre (balanço)",
    "Biapoiada (pino na base, topo travado)",
    "Engastada na base, topo apoiado",
)


def _momento_forca_horizontal(h: float, a: float, l: float, vinculo: str) -> tuple[float, str]:
    if vinculo == VINCULOS_MAO_FRANCESA[0]:
        return h * a, "M = H·a (engaste na base)"
    if vinculo == VINCULOS_MAO_FRANCESA[1]:
        return h * a * (l - a) / l, "M = H·a·(L − a)/L (sob o nó)"
    if vinculo == VINCULOS_MAO_FRANCESA[2]:
        b = l - a
        m_base = h * a * b * (l + b) / (2.0 * l**2)
        m_no = h * a**2 * b * (3.0 * l - a) / (2.0 * l**3)
        if m_base >= m_no:
            return m_base, "M = H·a·b·(L + b)/(2L²) (engaste na base)"
        return m_no, "M = H·a²·b·(3L − a)/(2L³) (sob o nó)"
    raise ValueError(f"Vínculo desconhecido: {vinculo!r}. Use um de {VINCULOS_MAO_FRANCESA}.")


def esforcos_mao_francesa(
    forca_N: float,
    angulo_graus: float,
    altura_no_mm: float,
    comprimento_mm: float,
    vinculo: str = VINCULOS_MAO_FRANCESA[0],
    excentricidade_mm: float = 0.0,
) -> EsforcosMaoFrancesa:
    """Decompõe a força da mão-francesa e obtém o momento que ela impõe à coluna.

    ``V = F·cos θ`` e ``H = F·sin θ`` (θ entre a barra e a coluna; 45° é o
    usual). O momento da componente horizontal depende do vínculo da coluna
    (:data:`VINCULOS_MAO_FRANCESA`); o da excentricidade, ``V·e``, é somado
    integralmente — conservador, já que só no engaste de base ele chega
    inteiro à seção crítica.
    """
    f = _nao_negativo("forca_N", forca_N)
    theta = float(angulo_graus)
    if not math.isfinite(theta) or not 0.0 < theta < 90.0:
        raise ValueError("angulo_graus deve ficar entre 0 e 90 (exclusive).")
    a = _positivo("altura_no_mm", altura_no_mm)
    l = _positivo("comprimento_mm", comprimento_mm)
    if a > l:
        raise ValueError("altura_no_mm não pode passar do comprimento da coluna.")
    e = _nao_negativo("excentricidade_mm", excentricidade_mm)
    rad = math.radians(theta)
    v, h = f * math.cos(rad), f * math.sin(rad)
    m_h, expressao = _momento_forca_horizontal(h, a, l, vinculo)
    m_e = v * e
    return EsforcosMaoFrancesa(
        forca_N=f,
        angulo_graus=theta,
        componente_vertical_N=v,
        componente_horizontal_N=h,
        altura_no_mm=a,
        comprimento_mm=l,
        vinculo=vinculo,
        excentricidade_mm=e,
        momento_horizontal_Nmm=m_h,
        momento_excentricidade_Nmm=m_e,
        momento_Nmm=m_h + m_e,
        expressao=expressao + (" + V·e" if m_e > 0 else ""),
    )


# ---------------------------------------------------------------------------
# Geometrias
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GeometriaColuna:
    """Seção da coluna: um perfil idealizado ou de catálogo, ou só A e r.

    ``perfil`` é o que permite calcular ``Q`` (paredes) e ``N_ez`` (J, Cw);
    sem ele a verificação fica restrita à flambagem por flexão com
    ``Q = 1``. ``distancia_fibra_*_mm`` é a distância do centroide à fibra
    mais afastada, usada para ``W = I/c`` na resistência à flexão da
    geometria direta; zero significa desconhecida.
    """

    area_mm2: float
    raio_giracao_x_mm: float
    raio_giracao_y_mm: float
    descricao: str = ""
    distancia_fibra_x_mm: float = 0.0
    distancia_fibra_y_mm: float = 0.0
    perfil: PerfilAco | None = None

    def distancia_fibra(self, eixo: str) -> float:
        return self.distancia_fibra_x_mm if eixo == "x" else self.distancia_fibra_y_mm


def _de_perfil(perfil: PerfilAco, descricao: str) -> GeometriaColuna:
    return GeometriaColuna(
        area_mm2=perfil.area_mm2,
        raio_giracao_x_mm=perfil.rx_mm,
        raio_giracao_y_mm=perfil.ry_mm,
        descricao=descricao,
        distancia_fibra_x_mm=max(perfil.distancias_fibras_x_mm),
        distancia_fibra_y_mm=max(perfil.distancias_fibras_y_mm),
        perfil=perfil,
    )


def geometria_retangular(largura_mm: float, altura_mm: float) -> GeometriaColuna:
    """Seção retangular maciça. ``largura`` (b, em x) e ``altura`` (h, em y)."""
    b = _positivo("largura_mm", largura_mm)
    h = _positivo("altura_mm", altura_mm)
    return _de_perfil(
        barra_retangular(f"Retangular {b:g}×{h:g}", h, b), f"Retangular {b:g} × {h:g} mm"
    )


def geometria_circular_macica(diametro_mm: float) -> GeometriaColuna:
    d = _positivo("diametro_mm", diametro_mm)
    return _de_perfil(barra_circular(f"Circular {d:g}", d), f"Circular maciça, d = {d:g} mm")


def geometria_circular_vazada(
    diametro_externo_mm: float, diametro_interno_mm: float
) -> GeometriaColuna:
    de = _positivo("diametro_externo_mm", diametro_externo_mm)
    di = _nao_negativo("diametro_interno_mm", diametro_interno_mm)
    if di >= de:
        raise ValueError("O diâmetro interno deve ser menor que o externo.")
    if di == 0:
        return _de_perfil(barra_circular(f"Circular {de:g}", de), f"Circular maciça, d = {de:g} mm")
    return _de_perfil(
        tubo_circular(f"Tubo {de:g}/{di:g}", de, (de - di) / 2.0), f"Tubular d={de:g}/{di:g} mm"
    )


def geometria_perfil_catalogo(perfil: PerfilAco) -> GeometriaColuna:
    return _de_perfil(perfil, f"Perfil {perfil.nome}")


def geometria_direta(
    area_mm2: float,
    raio_giracao_mm: float,
    raio_giracao_y_mm: float | None = None,
    descricao: str = "Área e raio de giração informados diretamente",
    *,
    distancia_fibra_x_mm: float = 0.0,
    distancia_fibra_y_mm: float = 0.0,
) -> GeometriaColuna:
    """Para seções fora do catálogo: informe A e r já calculados à parte.

    Se a seção for assimétrica (r diferente em cada eixo), informe
    ``raio_giracao_y_mm``; caso contrário os dois eixos usam o mesmo raio.
    As distâncias às fibras só são necessárias para a flexocompressão.
    """
    area = _positivo("area_mm2", area_mm2)
    rx = _positivo("raio_giracao_mm", raio_giracao_mm)
    ry = _positivo("raio_giracao_y_mm", raio_giracao_y_mm) if raio_giracao_y_mm else rx
    return GeometriaColuna(
        area,
        rx,
        ry,
        descricao,
        distancia_fibra_x_mm=_nao_negativo("distancia_fibra_x_mm", distancia_fibra_x_mm),
        distancia_fibra_y_mm=_nao_negativo("distancia_fibra_y_mm", distancia_fibra_y_mm),
    )


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MomentoFletor:
    """Um eixo da flexocompressão: solicitante amplificado e resistente."""

    eixo: str
    momento_primeira_ordem_Nmm: float
    b1: float
    momento_solicitante_Nmm: float
    momento_resistente_Nmm: float | None
    flexao: ResultadoFlexaoNBR | None = None


@dataclass(frozen=True)
class VerificacaoEixo:
    """Leitura da coluna **num eixo só**, como se apenas a flexão nele governasse.

    Serve de auxílio: mostra quanto cada eixo resiste (``χ`` e ``N_c,Rd`` com o
    ``N_e`` daquele eixo) e a interação com o momento do próprio eixo. A
    verificação normativa continua sendo a do modo governante — o menor
    ``N_e`` entre x, y, torção e flexo-torção — combinada com os dois momentos.
    """

    eixo: str
    fator_k: float
    comprimento_efetivo_mm: float
    raio_giracao_mm: float
    esbeltez: float
    ne_N: float
    lambda_0: float
    chi: float
    resistencia_N: float
    utilizacao_axial: float
    momento: MomentoFletor
    indice_interacao: float | None
    utilizacao: float
    governa: bool


@dataclass(frozen=True)
class ResultadoFlambagem:
    comprimento_efetivo_x_mm: float
    comprimento_efetivo_y_mm: float
    comprimento_efetivo_z_mm: float
    esbeltez_x: float
    esbeltez_y: float
    esbeltez_governante: float
    eixo_governante: str
    # Anexo E
    ne_x_N: float
    ne_y_N: float
    ne_z_N: float | None
    ne_acoplada_N: float | None
    ne_N: float
    modo_flambagem: str
    # Anexo F
    fator_q: float
    elementos: tuple[ElementoDePlaca, ...]
    # 5.3.3
    lambda_0: float
    chi: float
    forca_escoamento_N: float  # Q·A_g·f_y
    resistencia_N: float  # N_c,Rd
    forca_solicitante_N: float  # N_Sd
    utilizacao_axial: float
    # 5.5.1.2
    momento_x: MomentoFletor
    momento_y: MomentoFletor
    interacao: ResultadoInteracaoNBR | None
    # Leitura por eixo (auxílio)
    eixo_x: VerificacaoEixo
    eixo_y: VerificacaoEixo
    # Conclusão
    utilizacao: float
    modo_governante: str
    atende: bool
    avisos: tuple[str, ...] = ()

    @property
    def carga_critica_euler_N(self) -> float:
        """``N_e`` do modo governante — a carga de Euler é só referência."""
        return self.ne_N


# ---------------------------------------------------------------------------
# Verificação
# ---------------------------------------------------------------------------


def _avisos_de_entrada(
    kx: float, ky: float, modulo_elasticidade_MPa: float, escoamento_MPa: float
) -> list[str]:
    avisos: list[str] = []
    for nome, k in (("Kx", kx), ("Ky", ky)):
        if not K_MINIMO <= k <= K_MAXIMO:
            avisos.append(
                f"{nome} = {k:g} está fora da faixa física usual ({K_MINIMO:g} a "
                f"{K_MAXIMO:g}): 0,5 é o mínimo teórico (biengastada) e acima de 3 "
                "só em pórtico muito deslocável. Confira o valor."
            )
    e_gpa = modulo_elasticidade_MPa / 1_000.0
    if not 0.5 <= e_gpa <= 1_000.0:
        avisos.append(
            f"E = {e_gpa:.4g} GPa está fora da faixa de qualquer material de "
            "engenharia (0,5 a 1 000 GPa). Este módulo espera E em MPa "
            "(aço ≈ 200 000)."
        )
    if escoamento_MPa > 0.05 * modulo_elasticidade_MPa:
        avisos.append(
            f"f_y/E = {escoamento_MPa / modulo_elasticidade_MPa:.3g} corresponde a "
            "deformação de escoamento acima de 5 %, que nenhum material estrutural "
            "tem. Confira as unidades: f_y e E em MPa."
        )
    return avisos


def fator_amplificacao_b1(forca_solicitante_N: float, ne_N: float, cm: float = 1.0) -> float:
    """``B_1 = C_m/(1 − N_Sd/N_e) ≥ 1,0`` (Anexo D, D.2.2); infinito se ``N_Sd ≥ N_e``."""
    n = _nao_negativo("forca_solicitante_N", forca_solicitante_N)
    ne = _positivo("ne_N", ne_N)
    cm = _positivo("cm", cm)
    if n >= ne:
        return math.inf
    return max(1.0, cm / (1.0 - n / ne))


def _momento_resistente_direto(
    geometria: GeometriaColuna, eixo: str, fy: float
) -> tuple[float | None, str | None]:
    """Geometria sem perfil: ``M_Rd = W·f_y/γ_a1`` com ``W = A·r²/c`` (escoamento)."""
    c = geometria.distancia_fibra(eixo)
    if c <= 0:
        return None, (
            f"Sem a distância do centroide à fibra extrema no eixo {eixo} "
            f"(distancia_fibra_{eixo}_mm) não há como obter M_{eixo},Rd; a "
            "flexocompressão nesse eixo não foi verificada."
        )
    r = geometria.raio_giracao_x_mm if eixo == "x" else geometria.raio_giracao_y_mm
    w = geometria.area_mm2 * r**2 / c
    return w * fy / GAMMA_A1, None


def verificar_flambagem(
    *,
    geometria: GeometriaColuna,
    comprimento_mm: float,
    kx: float,
    ky: float,
    modulo_elasticidade_MPa: float,
    escoamento_MPa: float,
    forca_solicitante_N: float,
    kz: float | None = None,
    modulo_cisalhamento_MPa: float | None = None,
    momento_x_Nmm: float = 0.0,
    momento_y_Nmm: float = 0.0,
    excentricidade_mm: float = 0.0,
    eixo_excentricidade: str = "governante",
    cm: float = 1.0,
    comprimento_destravado_mm: float | None = None,
    cb: float = 1.0,
    soldado: bool = False,
) -> ResultadoFlambagem:
    """Verifica a coluna pela NBR 8800: ``N_c,Rd = χ·Q·A_g·f_y/γ_a1`` e interação N + M.

    ``forca_solicitante_N`` é ``N_Sd`` **já majorado** (use
    :func:`forca_de_calculo`). Os momentos ``momento_*_Nmm`` são de primeira
    ordem e de cálculo; a excentricidade ``e`` acrescenta ``N_Sd·e`` no eixo
    escolhido (``"x"``, ``"y"`` ou ``"governante"``, o de maior esbeltez).
    Ambos são amplificados por ``B_1`` com ``C_m`` (1,0 é conservador).
    ``kz`` é o fator do comprimento de flambagem por torção (sem ele vale o
    maior dos de flexão) e ``comprimento_destravado_mm``/``cb`` entram só na
    FLT do momento resistente em x.
    """
    area = _positivo("area_mm2", geometria.area_mm2)
    rx = _positivo("raio_giracao_x_mm", geometria.raio_giracao_x_mm)
    ry = _positivo("raio_giracao_y_mm", geometria.raio_giracao_y_mm)
    l = _positivo("comprimento_mm", comprimento_mm)
    kx = _positivo("kx", kx)
    ky = _positivo("ky", ky)
    e = _positivo("modulo_elasticidade_MPa", modulo_elasticidade_MPa)
    fy = _positivo("escoamento_MPa", escoamento_MPa)
    g = (
        _positivo("modulo_cisalhamento_MPa", modulo_cisalhamento_MPa)
        if modulo_cisalhamento_MPa
        else e / (2.0 * (1.0 + POISSON_ACO))
    )
    n_sd = _nao_negativo("forca_solicitante_N", forca_solicitante_N)
    mx1 = _nao_negativo("momento_x_Nmm", momento_x_Nmm)
    my1 = _nao_negativo("momento_y_Nmm", momento_y_Nmm)
    excentricidade = _nao_negativo("excentricidade_mm", excentricidade_mm)
    cm = _positivo("cm", cm)
    eixo_excentricidade = str(eixo_excentricidade).strip().lower() or "governante"
    if eixo_excentricidade not in {"x", "y", "governante"}:
        raise ValueError("eixo_excentricidade deve ser 'x', 'y' ou 'governante'.")

    lx, ly = kx * l, ky * l
    lz = _positivo("kz", kz) * l if kz else max(lx, ly)
    esbeltez_x, esbeltez_y = lx / rx, ly / ry
    if esbeltez_x >= esbeltez_y:
        esbeltez_governante, eixo_governante = esbeltez_x, "x"
    else:
        esbeltez_governante, eixo_governante = esbeltez_y, "y"

    avisos = _avisos_de_entrada(kx, ky, e, fy)
    perfil = geometria.perfil
    if perfil is not None:
        compressao = nbr8800.verificar_compressao(
            perfil, fy, e, g, l, kx, ky, n_sd, kz=kz, soldado=soldado
        )
        nex, ney, nez, acoplada = (
            compressao.ne_x_N,
            compressao.ne_y_N,
            compressao.ne_z_N,
            compressao.ne_acoplada_N,
        )
        ne, modo = compressao.ne_N, compressao.modo_flambagem
        q, elementos = compressao.fator_q, compressao.elementos
        lambda_0, chi, resistencia = compressao.lambda_0, compressao.chi, compressao.resistencia_N
        avisos.extend(aviso for aviso in compressao.avisos if "5.3.4.1" not in aviso)
    else:
        # Só A e r: flambagem por flexão nos dois eixos, sem paredes nem torção.
        nex = math.pi**2 * e * area * rx**2 / lx**2
        ney = math.pi**2 * e * area * ry**2 / ly**2
        nez = acoplada = None
        ne, modo = (nex, "x") if nex <= ney else (ney, "y")
        q, elementos = 1.0, ()
        lambda_0 = math.sqrt(q * area * fy / ne)
        chi = nbr8800.fator_chi(lambda_0)
        resistencia = chi * q * area * fy / GAMMA_A1
        avisos.append(
            "Geometria informada só por A e r: o fator Q de flambagem local foi "
            "adotado igual a 1,0 e a flambagem por torção/flexo-torção (N_ez, Anexo E) "
            "não foi verificada. Para perfis abertos ou de parede fina use uma seção "
            "geométrica ou o perfil de catálogo."
        )

    if esbeltez_governante > ESBELTEZ_MAXIMA:
        avisos.append(
            f"KL/r = {esbeltez_governante:.0f} supera o limite de {ESBELTEZ_MAXIMA:.0f} "
            "para barras comprimidas (5.3.4.1): a barra não atende independentemente "
            "da resistência calculada."
        )
    if q < 1.0:
        avisos.append(
            f"Flambagem local reduz a capacidade: Q = {q:.3f} (Anexo F) — "
            + "; ".join(
                f"{item.nome} b/t = {item.razao:.1f} > λ_r = {item.limite_r:.1f}"
                for item in elementos
                if item.razao > item.limite_r
            )
            + "."
        )
    if modo not in {"x", "y"}:
        avisos.append(
            f"O modo de flambagem elástica governante é {modo} (N_e = {ne / 1e3:.1f} kN, "
            "Anexo E), não a flexão pura: a verificação por Euler nos eixos x e y "
            "superestimaria a resistência."
        )

    forca_escoamento = q * area * fy
    utilizacao_axial = math.inf if resistencia <= 0 else n_sd / resistencia

    # -- flexocompressão (5.5.1.2) -------------------------------------------
    eixo_e = eixo_governante if eixo_excentricidade == "governante" else eixo_excentricidade
    if excentricidade > 0:
        if eixo_e == "x":
            mx1 += n_sd * excentricidade
        else:
            my1 += n_sd * excentricidade

    momentos: dict[str, MomentoFletor] = {}
    for eixo, m1, ne_eixo in (("x", mx1, nex), ("y", my1, ney)):
        b1 = fator_amplificacao_b1(n_sd, ne_eixo, cm) if m1 > 0 else 1.0
        m_sd = m1 * b1 if m1 > 0 else 0.0
        flexao: ResultadoFlexaoNBR | None = None
        m_rd: float | None = None
        if m1 > 0:
            if perfil is not None:
                flexao = nbr8800.verificar_flexao(
                    perfil,
                    fy,
                    e,
                    g,
                    0.0 if math.isinf(m_sd) else m_sd,
                    eixo=eixo,
                    comprimento_destravado_mm=(comprimento_destravado_mm if eixo == "x" else None),
                    cb=cb,
                    soldado=soldado,
                )
                m_rd = flexao.resistencia_Nmm
                avisos.extend(flexao.avisos)
            else:
                m_rd, aviso = _momento_resistente_direto(geometria, eixo, fy)
                if aviso:
                    avisos.append(aviso)
            if math.isinf(b1):
                avisos.append(
                    f"N_Sd = {n_sd / 1e3:.1f} kN alcança N_e{eixo} = {ne_eixo / 1e3:.1f} kN: "
                    f"a amplificação B_1 do momento em {eixo} diverge (Anexo D) — a coluna "
                    "não tem rigidez para a carga."
                )
        momentos[eixo] = MomentoFletor(eixo, m1, b1, m_sd, m_rd, flexao)

    interacao: ResultadoInteracaoNBR | None = None
    if (mx1 > 0 and momentos["x"].momento_resistente_Nmm) or (
        my1 > 0 and momentos["y"].momento_resistente_Nmm
    ):
        mx_sd = momentos["x"].momento_solicitante_Nmm
        my_sd = momentos["y"].momento_solicitante_Nmm
        if math.isinf(mx_sd) or math.isinf(my_sd):
            interacao = ResultadoInteracaoNBR(
                utilizacao_axial, math.inf, math.inf, math.inf, "B_1 → ∞ (N_Sd ≥ N_e)", False
            )
        else:
            interacao = nbr8800.verificar_interacao(
                n_sd,
                resistencia,
                mx_sd if momentos["x"].momento_resistente_Nmm else 0.0,
                momentos["x"].momento_resistente_Nmm or 1.0,
                my_sd if momentos["y"].momento_resistente_Nmm else 0.0,
                momentos["y"].momento_resistente_Nmm,
            )

    candidatos = {"Compressão N_c,Rd (5.3)": utilizacao_axial}
    for eixo, momento in momentos.items():
        if momento.momento_resistente_Nmm and momento.momento_solicitante_Nmm > 0:
            candidatos[f"Flexão em {eixo} (5.4.2)"] = (
                momento.momento_solicitante_Nmm / momento.momento_resistente_Nmm
            )
    if interacao is not None:
        candidatos["Interação N + M (5.5.1.2)"] = interacao.indice
    if esbeltez_governante > ESBELTEZ_MAXIMA:
        candidatos["Esbeltez KL/r > 200 (5.3.4.1)"] = math.inf
    governante = max(candidatos, key=lambda chave: candidatos[chave])
    utilizacao = candidatos[governante]

    # -- leitura por eixo ------------------------------------------------------
    eixos: dict[str, VerificacaoEixo] = {}
    for eixo, k, l_eixo, r_eixo, esbeltez_eixo, ne_eixo in (
        ("x", kx, lx, rx, esbeltez_x, nex),
        ("y", ky, ly, ry, esbeltez_y, ney),
    ):
        lambda_0_eixo = math.sqrt(q * area * fy / ne_eixo)
        chi_eixo = nbr8800.fator_chi(lambda_0_eixo)
        resistencia_eixo = chi_eixo * q * area * fy / GAMMA_A1
        axial_eixo = n_sd / resistencia_eixo
        momento = momentos[eixo]
        indice: float | None = None
        if momento.momento_resistente_Nmm and momento.momento_primeira_ordem_Nmm > 0:
            if math.isinf(momento.momento_solicitante_Nmm):
                indice = math.inf
            else:
                razao_m = momento.momento_solicitante_Nmm / momento.momento_resistente_Nmm
                indice = (
                    axial_eixo + 8.0 / 9.0 * razao_m
                    if axial_eixo >= 0.2
                    else axial_eixo / 2.0 + razao_m
                )
        eixos[eixo] = VerificacaoEixo(
            eixo=eixo,
            fator_k=k,
            comprimento_efetivo_mm=l_eixo,
            raio_giracao_mm=r_eixo,
            esbeltez=esbeltez_eixo,
            ne_N=ne_eixo,
            lambda_0=lambda_0_eixo,
            chi=chi_eixo,
            resistencia_N=resistencia_eixo,
            utilizacao_axial=axial_eixo,
            momento=momento,
            indice_interacao=indice,
            utilizacao=max(axial_eixo, indice if indice is not None else 0.0),
            governa=(modo == eixo),
        )

    return ResultadoFlambagem(
        comprimento_efetivo_x_mm=lx,
        comprimento_efetivo_y_mm=ly,
        comprimento_efetivo_z_mm=lz,
        esbeltez_x=esbeltez_x,
        esbeltez_y=esbeltez_y,
        esbeltez_governante=esbeltez_governante,
        eixo_governante=eixo_governante,
        ne_x_N=nex,
        ne_y_N=ney,
        ne_z_N=nez,
        ne_acoplada_N=acoplada,
        ne_N=ne,
        modo_flambagem=modo,
        fator_q=q,
        elementos=tuple(elementos),
        lambda_0=lambda_0,
        chi=chi,
        forca_escoamento_N=forca_escoamento,
        resistencia_N=resistencia,
        forca_solicitante_N=n_sd,
        utilizacao_axial=utilizacao_axial,
        momento_x=momentos["x"],
        momento_y=momentos["y"],
        interacao=interacao,
        eixo_x=eixos["x"],
        eixo_y=eixos["y"],
        utilizacao=utilizacao,
        modo_governante=governante,
        atende=utilizacao <= 1.0,
        avisos=tuple(dict.fromkeys(avisos)),
    )


# ---------------------------------------------------------------------------
# Verificação de um eixo por vez
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResultadoFlambagemEixo:
    """Verificação da coluna **num eixo** com o comprimento destravado e o K dele.

    É o formato de trabalho da página: o engenheiro analisa x-x (por exemplo,
    do piso ao nó da mão-francesa) e y-y (o contraventamento lateral) como
    duas verificações, cada uma com o próprio ``L`` e ``K``, e registra as
    duas. ``N_e`` é o da flexão nesse eixo — ou, se for menor, o da torção
    (seções de simetria dupla) ou o modo flexo-torcional acoplado a esse
    eixo (U em x, T em y) —, então cada registro é normativo por si e o
    pior dos dois governa a coluna.
    """

    eixo: str
    fator_k: float
    comprimento_mm: float
    comprimento_efetivo_mm: float
    comprimento_efetivo_z_mm: float | None
    raio_giracao_mm: float
    esbeltez: float
    # Anexo E
    ne_flexao_N: float
    ne_z_N: float | None
    ne_acoplada_N: float | None
    ne_N: float
    modo_flambagem: str
    # Anexo F
    fator_q: float
    elementos: tuple[ElementoDePlaca, ...]
    # 5.3.3
    lambda_0: float
    chi: float
    forca_escoamento_N: float
    resistencia_N: float
    forca_solicitante_N: float
    utilizacao_axial: float
    # 5.5.1.2
    momento: MomentoFletor
    interacao: ResultadoInteracaoNBR | None
    # Conclusão
    utilizacao: float
    modo_governante: str
    atende: bool
    avisos: tuple[str, ...] = ()


def verificar_flambagem_eixo(
    *,
    eixo: str,
    geometria: GeometriaColuna,
    comprimento_mm: float,
    k: float,
    modulo_elasticidade_MPa: float,
    escoamento_MPa: float,
    forca_solicitante_N: float,
    kz: float | None = None,
    modulo_cisalhamento_MPa: float | None = None,
    momento_Nmm: float = 0.0,
    excentricidade_mm: float = 0.0,
    cm: float = 1.0,
    comprimento_destravado_mm: float | None = None,
    cb: float = 1.0,
    soldado: bool = False,
) -> ResultadoFlambagemEixo:
    """``N_c,Rd`` e interação N + M da coluna **no eixo** ``eixo`` (``"x"`` ou ``"y"``).

    ``comprimento_mm`` é o comprimento destravado para a flexão em torno
    desse eixo (distância entre travamentos nesse plano) e ``k`` o fator de
    flambagem correspondente. ``momento_Nmm`` e ``excentricidade_mm`` são os
    do próprio eixo; ``kz`` multiplica ``comprimento_mm`` para o comprimento
    de flambagem por torção. Os demais parâmetros seguem
    :func:`verificar_flambagem`.
    """
    eixo = str(eixo).strip().lower()
    if eixo not in {"x", "y"}:
        raise ValueError("eixo deve ser 'x' ou 'y'.")
    area = _positivo("area_mm2", geometria.area_mm2)
    r = _positivo(
        f"raio_giracao_{eixo}_mm",
        geometria.raio_giracao_x_mm if eixo == "x" else geometria.raio_giracao_y_mm,
    )
    l = _positivo("comprimento_mm", comprimento_mm)
    k = _positivo("k", k)
    e = _positivo("modulo_elasticidade_MPa", modulo_elasticidade_MPa)
    fy = _positivo("escoamento_MPa", escoamento_MPa)
    g = (
        _positivo("modulo_cisalhamento_MPa", modulo_cisalhamento_MPa)
        if modulo_cisalhamento_MPa
        else e / (2.0 * (1.0 + POISSON_ACO))
    )
    n_sd = _nao_negativo("forca_solicitante_N", forca_solicitante_N)
    m1 = _nao_negativo("momento_Nmm", momento_Nmm)
    excentricidade = _nao_negativo("excentricidade_mm", excentricidade_mm)
    cm = _positivo("cm", cm)

    l_e = k * l
    lz = _positivo("kz", kz) * l if kz else None
    esbeltez = l_e / r
    avisos = _avisos_de_entrada(k, k, e, fy)
    avisos = [aviso.replace("Kx", f"K{eixo}") for aviso in avisos if "Ky" not in aviso]

    perfil = geometria.perfil
    ne_flexao = math.pi**2 * e * area * r**2 / l_e**2
    nez: float | None = None
    acoplada: float | None = None
    ne, modo = ne_flexao, eixo
    lz_usado: float | None = None
    if perfil is not None:
        nex, ney, nez, acoplada, _, _ = nbr8800.forcas_de_flambagem_elastica(
            perfil, e, g, l_e, l_e, lz
        )
        ne_flexao = nex if eixo == "x" else ney
        ne, modo = ne_flexao, eixo
        if nez is not None:
            lz_usado = lz or l_e
        if acoplada is not None:
            # Monossimétrica: a flexão em torno do eixo de simetria acopla
            # com a torção (E.1.2) — U em x, T em y.
            x0, y0 = centro_de_cisalhamento_do_perfil(perfil)
            acopla = (eixo == "x" and abs(x0) > 0) or (eixo == "y" and abs(y0) > 0)
            if acopla:
                ne, modo = acoplada, f"{eixo}z (flexo-torção)"
        elif nez is not None and nez < ne_flexao:
            ne, modo = nez, "z (torção)"
        chi_q1 = nbr8800.fator_chi(math.sqrt(area * fy / ne))
        q, elementos, avisos_q = nbr8800.fator_q(
            perfil, fy, e, soldado=soldado, chi_para_sigma=chi_q1
        )
        avisos.extend(avisos_q)
    else:
        q, elementos = 1.0, ()
        avisos.append(
            "Geometria informada só por A e r: o fator Q de flambagem local foi "
            "adotado igual a 1,0 e a flambagem por torção/flexo-torção (N_ez, Anexo E) "
            "não foi verificada. Para perfis abertos ou de parede fina use uma seção "
            "geométrica ou o perfil de catálogo."
        )

    lambda_0 = math.sqrt(q * area * fy / ne)
    chi = nbr8800.fator_chi(lambda_0)
    resistencia = chi * q * area * fy / GAMMA_A1
    forca_escoamento = q * area * fy
    utilizacao_axial = n_sd / resistencia

    if esbeltez > ESBELTEZ_MAXIMA:
        avisos.append(
            f"K{eixo}L{eixo}/r{eixo} = {esbeltez:.0f} supera o limite de "
            f"{ESBELTEZ_MAXIMA:.0f} para barras comprimidas (5.3.4.1): a barra não "
            "atende independentemente da resistência calculada."
        )
    if q < 1.0:
        avisos.append(
            f"Flambagem local reduz a capacidade: Q = {q:.3f} (Anexo F) — "
            + "; ".join(
                f"{item.nome} b/t = {item.razao:.1f} > λ_r = {item.limite_r:.1f}"
                for item in elementos
                if item.razao > item.limite_r
            )
            + "."
        )
    if modo != eixo:
        avisos.append(
            f"Neste eixo o modo de flambagem elástica governante é {modo} "
            f"(N_e = {ne / 1e3:.1f} kN < N_e{eixo} = {ne_flexao / 1e3:.1f} kN, Anexo E): "
            "a torção governa sobre a flexão e N_c,Rd foi calculado com ela."
        )

    # -- flexocompressão no eixo (5.5.1.2) -----------------------------------
    m1 += n_sd * excentricidade
    b1 = fator_amplificacao_b1(n_sd, ne_flexao, cm) if m1 > 0 else 1.0
    m_sd = m1 * b1 if m1 > 0 else 0.0
    flexao: ResultadoFlexaoNBR | None = None
    m_rd: float | None = None
    if m1 > 0:
        if perfil is not None:
            flexao = nbr8800.verificar_flexao(
                perfil,
                fy,
                e,
                g,
                0.0 if math.isinf(m_sd) else m_sd,
                eixo=eixo,
                comprimento_destravado_mm=(comprimento_destravado_mm if eixo == "x" else None),
                cb=cb,
                soldado=soldado,
            )
            m_rd = flexao.resistencia_Nmm
            avisos.extend(flexao.avisos)
        else:
            m_rd, aviso = _momento_resistente_direto(geometria, eixo, fy)
            if aviso:
                avisos.append(aviso)
        if math.isinf(b1):
            avisos.append(
                f"N_Sd = {n_sd / 1e3:.1f} kN alcança N_e{eixo} = {ne_flexao / 1e3:.1f} kN: "
                f"a amplificação B_1 do momento em {eixo} diverge (Anexo D) — a coluna "
                "não tem rigidez para a carga."
            )
    momento = MomentoFletor(eixo, m1, b1, m_sd, m_rd, flexao)

    interacao: ResultadoInteracaoNBR | None = None
    if m1 > 0 and m_rd:
        if math.isinf(m_sd):
            interacao = ResultadoInteracaoNBR(
                utilizacao_axial, math.inf, 0.0, math.inf, "B_1 → ∞ (N_Sd ≥ N_e)", False
            )
        elif eixo == "x":
            interacao = nbr8800.verificar_interacao(n_sd, resistencia, m_sd, m_rd)
        else:
            interacao = nbr8800.verificar_interacao(n_sd, resistencia, 0.0, 1.0, m_sd, m_rd)

    candidatos = {"Compressão N_c,Rd (5.3)": utilizacao_axial}
    if m_rd and m_sd > 0:
        candidatos[f"Flexão em {eixo} (5.4.2)"] = m_sd / m_rd
    if interacao is not None:
        candidatos["Interação N + M (5.5.1.2)"] = interacao.indice
    if esbeltez > ESBELTEZ_MAXIMA:
        candidatos["Esbeltez KL/r > 200 (5.3.4.1)"] = math.inf
    governante = max(candidatos, key=lambda chave: candidatos[chave])
    utilizacao = candidatos[governante]

    return ResultadoFlambagemEixo(
        eixo=eixo,
        fator_k=k,
        comprimento_mm=l,
        comprimento_efetivo_mm=l_e,
        comprimento_efetivo_z_mm=lz_usado,
        raio_giracao_mm=r,
        esbeltez=esbeltez,
        ne_flexao_N=ne_flexao,
        ne_z_N=nez,
        ne_acoplada_N=acoplada,
        ne_N=ne,
        modo_flambagem=modo,
        fator_q=q,
        elementos=tuple(elementos),
        lambda_0=lambda_0,
        chi=chi,
        forca_escoamento_N=forca_escoamento,
        resistencia_N=resistencia,
        forca_solicitante_N=n_sd,
        utilizacao_axial=utilizacao_axial,
        momento=momento,
        interacao=interacao,
        utilizacao=utilizacao,
        modo_governante=governante,
        atende=utilizacao <= 1.0,
        avisos=tuple(dict.fromkeys(avisos)),
    )
