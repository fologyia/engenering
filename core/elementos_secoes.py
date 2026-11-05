"""Os modelos de seção do Assistente de cargas, agora com ponto crítico e material.

Cada modelo avalia vários pontos da seção de uma vez (fibras extremas, centroide, junção da mesa com
a alma, cantos), e não só o ponto que o usuário escolheria: quem não sabe onde a peça sofre mais é
justamente quem mais precisa da resposta. O ponto de maior von Mises é comparado com S_y/FS, com o
K_t informado, e segue para o Círculo de Mohr ou para a Análise estática.

As contas continuam em :mod:`core.load_to_stress` e :mod:`core.additional_load_models`. Os ids dos
casos são os rótulos antigos dos modelos, porque o Assistente de projeto grava esses rótulos.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable

from core import additional_load_models as modelos
from core import load_to_stress as cargas
from core.elementos_base import (
    Campo,
    Caso,
    Metrica,
    Ponto,
    Resultado,
    Valores,
    exigir,
    faixa_recomendada,
    informativo,
    limite,
    recomendacao_minima,
)
from core.load_to_stress import EstadoPlanoCalculado

GRUPO_BARRAS = "Barras e tirantes"
GRUPO_EIXOS = "Eixos e molas"
GRUPO_VIGAS = "Vigas de seção cheia"
GRUPO_PERFIS = "Perfis estruturais"
GRUPO_LIGACOES = "Pinos e parafusos"
GRUPO_PRESSAO = "Vasos e tubos sob pressão"

MODELO_SECAO_I = "Seção I sob força axial, flexão e cortante"
REFERENCIA_RM = "Resistência dos materiais; ver docs/assistente_e_criterios.md"

#: Coeficientes de Saint-Venant para torção de seção retangular (b/c, α, β).
_SAINT_VENANT = (
    (1.0, 0.208, 0.141),
    (1.5, 0.231, 0.196),
    (1.75, 0.239, 0.214),
    (2.0, 0.246, 0.229),
    (2.5, 0.258, 0.249),
    (3.0, 0.267, 0.263),
    (4.0, 0.282, 0.281),
    (6.0, 0.299, 0.299),
    (8.0, 0.307, 0.307),
    (10.0, 0.313, 0.313),
)
_SAINT_VENANT_INFINITO = (1.0 / 3.0, 1.0 / 3.0)


def _campos_da_verificacao(sy: float = 250.0) -> tuple[Campo, ...]:
    secao = "Material e segurança"
    return (
        Campo(
            "sy_MPa",
            "Limite de escoamento S_y",
            "Limite de escoamento do material. Escolha o material no alto da página para "
            "preencher sozinho. Deixe 0 para não comparar com o material.",
            sy,
            "MPa",
            minimo=0.0,
            passo=10.0,
            secao=secao,
        ),
        Campo(
            "fs",
            "Fator de segurança",
            "Margem exigida sobre o escoamento. Carga bem conhecida: 1,5. Carga incerta ou falha "
            "grave: 2,0 ou mais.",
            1.5,
            minimo=1.0,
            maximo=8.0,
            passo=0.1,
            secao=secao,
        ),
        Campo(
            "kt",
            "Concentração de tensão K_t",
            "Multiplica a tensão no ponto. Seção lisa: 1,0. Furo em chapa: cerca de 3. Em carga "
            "estática de material dúctil pode ficar em 1,0, porque o escoamento local redistribui "
            "a tensão.",
            1.0,
            minimo=1.0,
            maximo=10.0,
            passo=0.1,
            secao=secao,
        ),
    )


def _campos_do_ponto(*, com_z: bool = False, rotulo: str = "Coordenada y") -> tuple[Campo, ...]:
    """Ponto a mais na varredura, para quem precisa de um lugar exato da seção."""
    secao = "Ponto a mais"
    quando = ("ponto_extra", (True,))
    campos = [
        Campo(
            "ponto_extra",
            "Avaliar outro ponto",
            "A varredura já olha os pontos que costumam governar. Ligue para acrescentar um ponto "
            "exato, como a posição de um furo ou de um extensômetro.",
            False,
            secao=secao,
        ),
        Campo(
            "y_extra_mm",
            rotulo,
            "Medida a partir do centroide, positiva para cima. Em cilindro, é o raio do ponto.",
            0.0,
            "mm",
            passo=1.0,
            secao=secao,
            quando=quando,
        ),
    ]
    if com_z:
        campos.append(
            Campo(
                "z_extra_mm",
                "Coordenada z",
                "Medida a partir do centroide, positiva para a direita.",
                0.0,
                "mm",
                passo=1.0,
                secao=secao,
                quando=quando,
            )
        )
    return tuple(campos)


def _ponto(nome: str, estado: EstadoPlanoCalculado) -> Ponto:
    return Ponto(nome, estado.sigma_x, estado.sigma_y, estado.tau_xy)


def _fechar(
    v: Valores,
    pontos: Iterable[Ponto],
    base: EstadoPlanoCalculado,
    *,
    alertas: Iterable[str] = (),
    metricas: Iterable[Metrica] = (),
    verificacoes: Iterable = (),
    extra: Callable[[float, float], Ponto] | None = None,
) -> Resultado:
    """Junta a varredura de pontos, o material e os avisos do modelo num só resultado."""
    lista = tuple(pontos)
    if extra is not None and bool(v.get("ponto_extra")):
        y = float(v.get("y_extra_mm", 0.0))
        z = float(v.get("z_extra_mm", 0.0))
        lista = (*lista, extra(y, z))
    critico = max(lista, key=lambda p: p.von_mises)
    kt = float(v["kt"])
    sy = float(v["sy_MPa"])
    fs = float(v["fs"])
    tensao = kt * critico.von_mises
    linhas = []
    if sy > 0:
        linhas.append(
            limite(
                "von Mises no ponto crítico",
                tensao,
                sy / fs,
                "MPa",
                f"σ_VM·K_t = {critico.von_mises:.1f}·{kt:g} em: {critico.nome}",
                REFERENCIA_RM,
            )
        )
    else:
        linhas.append(
            informativo(
                "von Mises no ponto crítico",
                tensao,
                "MPa",
                f"sem comparação: S_y não informado; ponto: {critico.nome}",
                REFERENCIA_RM,
            )
        )
    linhas.append(
        informativo(
            "Tresca no ponto crítico",
            kt * critico.tresca,
            "MPa",
            "σ₁ − σ₃",
            REFERENCIA_RM,
        )
    )
    linhas.extend(verificacoes)
    s1, _s2, s3 = critico.principais
    numeros = (
        Metrica("von Mises máximo", critico.von_mises, "MPa", 2),
        Metrica("σx no ponto crítico", critico.sigma_x, "MPa", 2),
        Metrica("τxy no ponto crítico", critico.tau_xy, "MPa", 2),
        Metrica("σ₁", s1, "MPa", 2),
        Metrica("σ₃", s3, "MPa", 2),
        *metricas,
    )
    if sy > 0:
        fator = sy / tensao if tensao > 0 else math.inf
        numeros = (Metrica("Fator de segurança obtido", fator, "", 2), *numeros)
    return Resultado(
        resumo=f"{base.descricao}. Ponto crítico: {critico.nome}, com {critico.von_mises:.1f} MPa.",
        metricas=numeros,
        verificacoes=tuple(linhas),
        pontos=lista,
        alertas=tuple(alertas),
        hipoteses=base.hipoteses,
        referencias=(REFERENCIA_RM,),
    )


def _flambagem(forca: float) -> tuple[str, ...]:
    if forca < 0:
        return (
            "A barra está sob compressão. Esta tensão não mede flambagem: uma barra esbelta falha "
            "por instabilidade bem antes de escoar. Verifique em Flambagem de colunas.",
        )
    return ()


# ---------------------------------------------------------------------------
# Barras
# ---------------------------------------------------------------------------


def calcular_barra(v: Valores) -> Resultado:
    forca = float(v["forca_kN"])
    estado = cargas.barra_axial(forca * 1000.0, float(v["area_mm2"]))
    return _fechar(v, (_ponto("Seção da barra", estado),), estado, alertas=_flambagem(forca))


def calcular_excentrica(v: Valores) -> Resultado:
    b = float(v["b_mm"])
    h = float(v["h_mm"])
    forca = float(v["forca_kN"])
    ey = float(v["ey_mm"])
    ez = float(v["ez_mm"])

    def canto(nome: str, y: float, z: float) -> Ponto:
        return _ponto(nome, modelos.barra_axial_excentrica(forca * 1000.0, b, h, ey, ez, y, z))

    pontos = (
        canto("Canto (+y, +z)", h / 2.0, b / 2.0),
        canto("Canto (+y, −z)", h / 2.0, -b / 2.0),
        canto("Canto (−y, +z)", -h / 2.0, b / 2.0),
        canto("Canto (−y, −z)", -h / 2.0, -b / 2.0),
    )
    nucleo = modelos.fator_nucleo_central(b, h, ey, ez)
    alertas = list(_flambagem(forca))
    if nucleo > 1.0:
        alertas.append(
            "A carga está fora do núcleo central: parte da seção traciona enquanto o resto "
            "comprime. Em concreto ou em apoio sem aderência, isso é perda de contato."
        )
    base = modelos.barra_axial_excentrica(forca * 1000.0, b, h, ey, ez, 0.0, 0.0)
    return _fechar(
        v,
        pontos,
        base,
        alertas=alertas,
        metricas=(Metrica("Posição no núcleo central", nucleo, "", 2),),
        extra=lambda y, z: canto("Ponto informado", y, z),
    )


CAMPOS_BARRA = (
    Campo(
        "forca_kN",
        "Força axial F",
        "Positiva para tração e negativa para compressão.",
        20.0,
        "kN",
        passo=1.0,
        secao="Carga e seção",
    ),
    Campo(
        "area_mm2",
        "Área da seção A",
        "Área resistente. Em barra com furos ou com rosca, use a área líquida.",
        200.0,
        "mm²",
        minimo=0.001,
        passo=10.0,
        secao="Carga e seção",
    ),
    *_campos_da_verificacao(),
)

CAMPOS_EXCENTRICA = (
    Campo(
        "b_mm",
        "Largura b (direção z)",
        "Dimensão da seção na direção z.",
        60.0,
        "mm",
        minimo=0.001,
        passo=5.0,
        secao="Seção",
    ),
    Campo(
        "h_mm",
        "Altura h (direção y)",
        "Dimensão da seção na direção y.",
        100.0,
        "mm",
        minimo=0.001,
        passo=5.0,
        secao="Seção",
    ),
    Campo(
        "forca_kN",
        "Força axial F",
        "Positiva para tração e negativa para compressão.",
        -150.0,
        "kN",
        passo=5.0,
        secao="Carga",
    ),
    Campo(
        "ey_mm",
        "Excentricidade e_y",
        "Deslocamento da carga na direção y, a partir do centroide.",
        20.0,
        "mm",
        passo=1.0,
        secao="Carga",
    ),
    Campo(
        "ez_mm",
        "Excentricidade e_z",
        "Deslocamento da carga na direção z, a partir do centroide.",
        0.0,
        "mm",
        passo=1.0,
        secao="Carga",
    ),
    *_campos_do_ponto(com_z=True),
    *_campos_da_verificacao(),
)


# ---------------------------------------------------------------------------
# Eixos e mola simples
# ---------------------------------------------------------------------------


def calcular_eixo_macico(v: Valores) -> Resultado:
    d = float(v["d_mm"])
    forca = float(v["forca_kN"]) * 1000.0
    momento = float(v["momento_Nm"]) * 1000.0
    torque = float(v["torque_Nm"]) * 1000.0
    cortante = float(v["cortante_kN"]) * 1000.0
    tracionada = cargas.eixo_circular_macico(d, forca, momento, torque, "tracionada")
    comprimida = cargas.eixo_circular_macico(d, forca, momento, torque, "comprimida")
    area = math.pi * d**2 / 4.0
    # Na linha neutra a flexão some, mas o cortante 4V/3A soma à torção de um dos lados.
    tau_neutra = abs(tracionada.tau_xy) + 4.0 * abs(cortante) / (3.0 * area)
    pontos = (
        _ponto("Superfície, lado tracionado", tracionada),
        _ponto("Superfície, lado comprimido", comprimida),
        Ponto("Superfície, na linha neutra", forca / area, 0.0, tau_neutra),
    )
    return _fechar(v, pontos, tracionada, alertas=_flambagem(forca))


def calcular_eixo_vazado(v: Valores) -> Resultado:
    de = float(v["de_mm"])
    di = float(v["di_mm"])
    forca = float(v["forca_kN"]) * 1000.0
    momento = float(v["momento_Nm"]) * 1000.0
    torque = float(v["torque_Nm"]) * 1000.0
    cortante = float(v["cortante_kN"]) * 1000.0
    tracionada = modelos.eixo_circular_vazado(de, di, forca, momento, torque, "tracionada")
    comprimida = modelos.eixo_circular_vazado(de, di, forca, momento, torque, "comprimida")
    area = math.pi * (de**2 - di**2) / 4.0
    tau_neutra = abs(tracionada.tau_xy) + 2.0 * abs(cortante) / area
    pontos = (
        _ponto("Superfície, lado tracionado", tracionada),
        _ponto("Superfície, lado comprimido", comprimida),
        Ponto("Superfície, na linha neutra", forca / area, 0.0, tau_neutra),
    )
    return _fechar(v, pontos, tracionada, alertas=_flambagem(forca))


def calcular_mola_simples(v: Valores) -> Resultado:
    forca = float(v["forca_N"])
    d_medio = float(v["D_mm"])
    d_fio = float(v["d_mm"])
    wahl = bool(v["wahl"])
    estado = modelos.mola_helicoidal(forca, d_medio, d_fio, wahl)
    indice = modelos.indice_mola(d_medio, d_fio)
    return _fechar(
        v,
        (_ponto("Fibra interna do fio", estado),),
        estado,
        metricas=(
            Metrica("Índice C = D/d", indice, "", 2),
            Metrica("Fator de Wahl", modelos.fator_wahl(indice) if wahl else 1.0, "", 3),
        ),
        verificacoes=(
            faixa_recomendada("Índice de mola", indice, 4.0, 12.0, "—", "C = D/d", REFERENCIA_RM),
        ),
    )


def _campos_de_eixo() -> tuple[Campo, ...]:
    return (
        Campo(
            "forca_kN",
            "Força axial F",
            "Positiva para tração e negativa para compressão.",
            0.0,
            "kN",
            passo=1.0,
            secao="Esforços",
        ),
        Campo(
            "momento_Nm",
            "Momento fletor |M|",
            "Valor absoluto do momento na seção. Os dois lados são avaliados.",
            500.0,
            "N·m",
            minimo=0.0,
            passo=10.0,
            secao="Esforços",
        ),
        Campo(
            "torque_Nm",
            "Torque T",
            "O sinal define o sinal de τxy.",
            300.0,
            "N·m",
            passo=10.0,
            secao="Esforços",
        ),
        Campo(
            "cortante_kN",
            "Força cortante V",
            "Em eixo curto e muito carregado, o cortante soma à torção na linha neutra. Em eixo "
            "longo, ele quase não pesa.",
            0.0,
            "kN",
            minimo=0.0,
            passo=1.0,
            secao="Esforços",
        ),
    )


CAMPOS_EIXO_MACICO = (
    Campo(
        "d_mm",
        "Diâmetro d",
        "Diâmetro do eixo na seção analisada.",
        30.0,
        "mm",
        minimo=0.001,
        passo=1.0,
        secao="Seção",
    ),
    *_campos_de_eixo(),
    *_campos_da_verificacao(420.0),
)

CAMPOS_EIXO_VAZADO = (
    Campo(
        "de_mm",
        "Diâmetro externo D_e",
        "Diâmetro de fora do tubo.",
        40.0,
        "mm",
        minimo=0.002,
        passo=1.0,
        secao="Seção",
    ),
    Campo(
        "di_mm",
        "Diâmetro interno D_i",
        "Diâmetro do furo. Deve ser menor que o externo.",
        25.0,
        "mm",
        minimo=0.0,
        passo=1.0,
        secao="Seção",
    ),
    *_campos_de_eixo(),
    *_campos_da_verificacao(310.0),
)

CAMPOS_MOLA_SIMPLES = (
    Campo(
        "forca_N",
        "Força na mola F",
        "Em newtons, não em kN: molas costumam trabalhar nessa faixa.",
        500.0,
        "N",
        passo=10.0,
        secao="Mola",
    ),
    Campo(
        "D_mm",
        "Diâmetro médio D",
        "Medido no eixo do fio, não na face externa das espiras.",
        40.0,
        "mm",
        minimo=0.002,
        passo=1.0,
        secao="Mola",
    ),
    Campo(
        "d_mm",
        "Diâmetro do fio d",
        "Diâmetro do fio. Deve ser menor que o diâmetro médio.",
        5.0,
        "mm",
        minimo=0.001,
        passo=0.5,
        secao="Mola",
    ),
    Campo(
        "wahl",
        "Aplicar o fator de Wahl",
        "Corrige a curvatura da espira e o cisalhamento direto. Sem ele a tensão sai subestimada, "
        "sobretudo em molas de índice baixo.",
        True,
        secao="Mola",
    ),
    *_campos_da_verificacao(1400.0),
)


# ---------------------------------------------------------------------------
# Vigas
# ---------------------------------------------------------------------------


def calcular_viga_retangular(v: Valores) -> Resultado:
    b = float(v["b_mm"])
    h = float(v["h_mm"])
    forca = float(v["forca_kN"]) * 1000.0
    momento = float(v["momento_Nm"]) * 1000.0
    cortante = float(v["cortante_kN"]) * 1000.0

    def em(nome: str, y: float) -> Ponto:
        return _ponto(nome, cargas.viga_retangular(b, h, y, forca, momento, cortante))

    pontos = (
        em("Fibra superior", h / 2.0),
        em("Um quarto acima do centroide", h / 4.0),
        em("Centroide", 0.0),
        em("Um quarto abaixo do centroide", -h / 4.0),
        em("Fibra inferior", -h / 2.0),
    )
    return _fechar(
        v,
        pontos,
        cargas.viga_retangular(b, h, 0.0, forca, momento, cortante),
        extra=lambda y, _z: em("Ponto informado", y),
    )


def calcular_biaxial(v: Valores) -> Resultado:
    b = float(v["b_mm"])
    h = float(v["h_mm"])
    forca = float(v["forca_kN"]) * 1000.0
    my = float(v["my_Nm"]) * 1000.0
    mz = float(v["mz_Nm"]) * 1000.0

    def canto(nome: str, y: float, z: float) -> Ponto:
        return _ponto(nome, modelos.secao_retangular_flexao_biaxial(b, h, y, z, forca, my, mz))

    pontos = (
        canto("Canto (+y, +z)", h / 2.0, b / 2.0),
        canto("Canto (+y, −z)", h / 2.0, -b / 2.0),
        canto("Canto (−y, +z)", -h / 2.0, b / 2.0),
        canto("Canto (−y, −z)", -h / 2.0, -b / 2.0),
    )
    return _fechar(
        v,
        pontos,
        modelos.secao_retangular_flexao_biaxial(b, h, 0.0, 0.0, forca, my, mz),
        extra=lambda y, z: canto("Ponto informado", y, z),
    )


def _campos_de_flexao(momento: float, cortante: float) -> tuple[Campo, ...]:
    return (
        Campo(
            "forca_kN",
            "Força axial F",
            "Positiva para tração e negativa para compressão.",
            0.0,
            "kN",
            passo=1.0,
            secao="Esforços",
        ),
        Campo(
            "momento_Nm",
            "Momento fletor M",
            "Momento positivo comprime a região de y positivo, acima do centroide.",
            momento,
            "N·m",
            passo=10.0,
            secao="Esforços",
        ),
        Campo(
            "cortante_kN",
            "Força cortante V",
            "O sinal define o sinal de τxy.",
            cortante,
            "kN",
            passo=0.5,
            secao="Esforços",
        ),
    )


CAMPOS_VIGA = (
    Campo(
        "b_mm",
        "Largura b",
        "Largura da seção.",
        20.0,
        "mm",
        minimo=0.001,
        passo=1.0,
        secao="Seção",
    ),
    Campo(
        "h_mm",
        "Altura h",
        "Altura da seção.",
        40.0,
        "mm",
        minimo=0.001,
        passo=1.0,
        secao="Seção",
    ),
    *_campos_de_flexao(500.0, 1.0),
    *_campos_do_ponto(),
    *_campos_da_verificacao(),
)

CAMPOS_BIAXIAL = (
    Campo(
        "b_mm",
        "Largura b (direção z)",
        "Dimensão da seção na direção z.",
        40.0,
        "mm",
        minimo=0.001,
        passo=1.0,
        secao="Seção",
    ),
    Campo(
        "h_mm",
        "Altura h (direção y)",
        "Dimensão da seção na direção y.",
        60.0,
        "mm",
        minimo=0.001,
        passo=1.0,
        secao="Seção",
    ),
    Campo(
        "forca_kN",
        "Força axial F",
        "Positiva para tração e negativa para compressão.",
        0.0,
        "kN",
        passo=1.0,
        secao="Esforços",
    ),
    Campo(
        "my_Nm",
        "Momento M_y",
        "Momento em torno do eixo y: faz a tensão variar ao longo de z.",
        200.0,
        "N·m",
        passo=10.0,
        secao="Esforços",
    ),
    Campo(
        "mz_Nm",
        "Momento M_z",
        "Momento em torno do eixo z: faz a tensão variar ao longo de y.",
        500.0,
        "N·m",
        passo=10.0,
        secao="Esforços",
    ),
    *_campos_do_ponto(com_z=True),
    *_campos_da_verificacao(),
)


# ---------------------------------------------------------------------------
# Perfis
# ---------------------------------------------------------------------------


def calcular_perfil_i(v: Valores) -> Resultado:
    h = float(v["h_mm"])
    b = float(v["b_mm"])
    tf = float(v["tf_mm"])
    tw = float(v["tw_mm"])
    forca = float(v["forca_kN"]) * 1000.0
    momento = float(v["momento_Nm"]) * 1000.0
    cortante = float(v["cortante_kN"]) * 1000.0

    def em(nome: str, y: float) -> Ponto:
        return _ponto(nome, modelos.secao_i_flexao(h, b, tf, tw, y, forca, momento, cortante))

    meia_alma = h / 2.0 - tf
    pontos = (
        em("Fibra superior", h / 2.0),
        em("Junção mesa-alma superior, na alma", meia_alma * (1.0 - 1e-9)),
        em("Centroide", 0.0),
        em("Junção mesa-alma inferior, na alma", -meia_alma * (1.0 - 1e-9)),
        em("Fibra inferior", -h / 2.0),
    )
    return _fechar(
        v,
        pontos,
        modelos.secao_i_flexao(h, b, tf, tw, 0.0, forca, momento, cortante),
        extra=lambda y, _z: em("Ponto informado", y),
    )


def calcular_perfil_u(v: Valores) -> Resultado:
    h = float(v["h_mm"])
    b = float(v["b_mm"])
    tf = float(v["tf_mm"])
    tw = float(v["tw_mm"])
    forca = float(v["forca_kN"]) * 1000.0
    momento = float(v["momento_Nm"]) * 1000.0
    cortante = float(v["cortante_kN"]) * 1000.0

    def em(nome: str, y: float) -> Ponto:
        return _ponto(nome, modelos.secao_u_flexao(h, b, tf, tw, y, forca, momento, cortante))

    meia_alma = h / 2.0 - tf
    pontos = (
        em("Fibra superior", h / 2.0),
        em("Junção mesa-alma superior, na alma", meia_alma * (1.0 - 1e-9)),
        em("Centroide", 0.0),
        em("Junção mesa-alma inferior, na alma", -meia_alma * (1.0 - 1e-9)),
        em("Fibra inferior", -h / 2.0),
    )
    props = modelos.propriedades_perfil_u(h, b, tf, tw)
    alertas = []
    if cortante != 0.0:
        alertas.append(
            "O centro de cisalhamento do perfil U fica fora da alma, do lado oposto ao das mesas. "
            "Um cortante que não passe por ele acrescenta torção que este modelo não calcula."
        )
    return _fechar(
        v,
        pontos,
        modelos.secao_u_flexao(h, b, tf, tw, 0.0, forca, momento, cortante),
        alertas=alertas,
        extra=lambda y, _z: em("Ponto informado", y),
        metricas=(
            Metrica("Área", props["area"] / 100.0, "cm²", 2),
            Metrica("Centroide (da face da alma)", props["z_centroide"], "mm", 2),
            Metrica("Centro de cisalhamento", props["excentricidade_centro_cisalhamento"], "mm", 2),
        ),
    )


def calcular_cantoneira(v: Valores) -> Resultado:
    aba = float(v["aba_mm"])
    t = float(v["t_mm"])
    forca = float(v["forca_kN"]) * 1000.0
    my = float(v["my_Nm"]) * 1000.0
    mz = float(v["mz_Nm"]) * 1000.0
    props = modelos.propriedades_cantoneira_abas_iguais(aba, t)
    c = props["centroide"]

    def em(nome: str, y: float, z: float) -> Ponto:
        return _ponto(nome, modelos.cantoneira_abas_iguais(aba, t, y, z, forca, my, mz))

    pontos = (
        em("Ponta da aba vertical", aba - c, -c),
        em("Ponta da aba horizontal", -c, aba - c),
        em("Canto externo", -c, -c),
    )
    inclinacao = modelos.angulo_linha_neutra(
        my, mz, props["inercia_y"], props["inercia_z"], props["produto_inercia"]
    )
    alertas = []
    if (my != 0.0 or mz != 0.0) and abs(inclinacao) > 1.0:
        alertas.append(
            f"A linha neutra está a {inclinacao:.1f}° do eixo z: a cantoneira flexiona para fora "
            "do plano de carregamento. Sem contenção lateral, a flecha e a tensão reais são "
            "maiores que as de uma flexão reta."
        )
    return _fechar(
        v,
        pontos,
        modelos.cantoneira_abas_iguais(aba, t, 0.0, 0.0, forca, my, mz),
        alertas=alertas,
        extra=lambda y, z: em("Ponto informado", y, z),
        metricas=(
            Metrica("Área", props["area"] / 100.0, "cm²", 2),
            Metrica("Centroide (da face)", c, "mm", 2),
            Metrica("Inclinação da linha neutra", inclinacao, "°", 1),
            Metrica("I_máx", props["inercia_maxima"] / 1e4, "cm⁴", 1),
            Metrica("I_mín", props["inercia_minima"] / 1e4, "cm⁴", 1),
        ),
    )


def calcular_caixao(v: Valores) -> Resultado:
    b = float(v["b_mm"])
    h = float(v["h_mm"])
    t = float(v["t_mm"])
    forca = float(v["forca_kN"]) * 1000.0
    momento = float(v["momento_Nm"]) * 1000.0
    torque = float(v["torque_Nm"]) * 1000.0

    def em(nome: str, y: float) -> Ponto:
        return _ponto(nome, modelos.secao_tubular_retangular(b, h, t, y, forca, momento, torque))

    pontos = (em("Fibra superior", h / 2.0), em("Centroide", 0.0), em("Fibra inferior", -h / 2.0))
    relacao = min(b, h) / t
    return _fechar(
        v,
        pontos,
        modelos.secao_tubular_retangular(b, h, t, 0.0, forca, momento, torque),
        extra=lambda y, _z: em("Ponto informado", y),
        verificacoes=(
            recomendacao_minima(
                "Parede fina (menor lado/t)",
                relacao,
                10.0,
                "—",
                "abaixo de 10 a fórmula de Bredt perde precisão",
                REFERENCIA_RM,
            ),
        ),
    )


def _campos_de_perfil(mesa_padrao: float) -> tuple[Campo, ...]:
    return (
        Campo(
            "h_mm",
            "Altura total h",
            "Altura total do perfil.",
            200.0,
            "mm",
            minimo=0.01,
            passo=5.0,
            secao="Seção",
        ),
        Campo(
            "b_mm",
            "Largura da mesa b",
            "Largura da mesa. Em perfil U, medida da face externa da alma até a ponta da mesa.",
            mesa_padrao,
            "mm",
            minimo=0.01,
            passo=5.0,
            secao="Seção",
        ),
        Campo(
            "tf_mm",
            "Espessura da mesa t_f",
            "Espessura da mesa. As duas mesas somadas devem ser menores que a altura.",
            10.0,
            "mm",
            minimo=0.001,
            passo=0.5,
            secao="Seção",
        ),
        Campo(
            "tw_mm",
            "Espessura da alma t_w",
            "Espessura da alma. Deve ser menor que a largura da mesa.",
            6.0,
            "mm",
            minimo=0.001,
            passo=0.5,
            secao="Seção",
        ),
    )


CAMPOS_PERFIL_I = (
    *_campos_de_perfil(100.0),
    *_campos_de_flexao(5000.0, 0.0),
    *_campos_do_ponto(),
    *_campos_da_verificacao(),
)
CAMPOS_PERFIL_U = (
    *_campos_de_perfil(75.0),
    *_campos_de_flexao(5000.0, 50.0),
    *_campos_do_ponto(),
    *_campos_da_verificacao(),
)

CAMPOS_CANTONEIRA = (
    Campo(
        "aba_mm",
        "Comprimento da aba b",
        "Comprimento de cada aba.",
        100.0,
        "mm",
        minimo=0.002,
        passo=5.0,
        secao="Seção",
    ),
    Campo(
        "t_mm",
        "Espessura t",
        "Espessura das abas.",
        10.0,
        "mm",
        minimo=0.001,
        passo=0.5,
        secao="Seção",
    ),
    Campo(
        "forca_kN",
        "Força axial F",
        "Positiva para tração e negativa para compressão.",
        0.0,
        "kN",
        passo=1.0,
        secao="Esforços",
    ),
    Campo(
        "my_Nm",
        "Momento M_y",
        "Momento em torno do eixo y (vertical): faz a tensão variar ao longo de z.",
        0.0,
        "N·m",
        passo=10.0,
        secao="Esforços",
    ),
    Campo(
        "mz_Nm",
        "Momento M_z",
        "Momento em torno do eixo z (horizontal): faz a tensão variar ao longo de y.",
        1000.0,
        "N·m",
        passo=10.0,
        secao="Esforços",
    ),
    *_campos_do_ponto(com_z=True),
    *_campos_da_verificacao(),
)

CAMPOS_CAIXAO = (
    Campo(
        "b_mm",
        "Largura b (direção z)",
        "Largura externa do tubo.",
        60.0,
        "mm",
        minimo=0.003,
        passo=5.0,
        secao="Seção",
    ),
    Campo(
        "h_mm",
        "Altura h (direção y)",
        "Altura externa do tubo.",
        100.0,
        "mm",
        minimo=0.003,
        passo=5.0,
        secao="Seção",
    ),
    Campo(
        "t_mm",
        "Espessura da parede t",
        "Espessura da parede. Deve ser menor que metade do menor lado.",
        5.0,
        "mm",
        minimo=0.001,
        passo=0.5,
        secao="Seção",
    ),
    Campo(
        "forca_kN",
        "Força axial F",
        "Positiva para tração e negativa para compressão.",
        0.0,
        "kN",
        passo=1.0,
        secao="Esforços",
    ),
    Campo(
        "momento_Nm",
        "Momento fletor M",
        "Momento positivo comprime a região de y positivo.",
        2000.0,
        "N·m",
        passo=50.0,
        secao="Esforços",
    ),
    Campo(
        "torque_Nm",
        "Torque T",
        "O sinal define o sinal de τxy.",
        500.0,
        "N·m",
        passo=10.0,
        secao="Esforços",
    ),
    *_campos_do_ponto(),
    *_campos_da_verificacao(),
)


# ---------------------------------------------------------------------------
# Torção de seção retangular
# ---------------------------------------------------------------------------


def coeficientes_saint_venant(relacao: float) -> tuple[float, float]:
    """α e β para b/c ≥ 1, interpolados; acima de 10 a seção é tratada como chapa fina."""
    for (r1, a1, b1), (r2, a2, b2) in zip(_SAINT_VENANT, _SAINT_VENANT[1:], strict=False):
        if r1 <= relacao <= r2:
            t = (relacao - r1) / (r2 - r1)
            return a1 + t * (a2 - a1), b1 + t * (b2 - b1)
    return _SAINT_VENANT_INFINITO


def calcular_torcao_retangular(v: Valores) -> Resultado:
    lado_1 = float(v["b_mm"])
    lado_2 = float(v["c_mm"])
    b = max(lado_1, lado_2)
    c = min(lado_1, lado_2)
    torque = float(v["torque_Nm"]) * 1000.0
    comprimento = float(v["comprimento_mm"])
    g = float(v["g_GPa"]) * 1000.0
    alfa, beta = coeficientes_saint_venant(b / c)
    tau = torque / (alfa * b * c**2)
    giro = torque * comprimento / (beta * b * c**3 * g)
    base = EstadoPlanoCalculado(
        0.0,
        0.0,
        tau,
        "Seção retangular em torção livre",
        (
            "Torção de Saint-Venant, sem restrição ao empenamento.",
            "Tensão máxima no meio do lado maior; nos cantos a tensão é nula.",
            "Seção maciça. Em seção aberta de chapa fina, some as parcelas de cada chapa.",
        ),
    )
    return _fechar(
        v,
        (Ponto("Meio do lado maior", 0.0, 0.0, tau),),
        base,
        metricas=(
            Metrica("Cisalhamento τ máx", tau, "MPa", 2),
            Metrica("Giro total", math.degrees(giro), "°", 3),
            Metrica("Coeficiente α", alfa, "", 3),
            Metrica("Coeficiente β", beta, "", 3),
        ),
    )


CAMPOS_TORCAO = (
    Campo(
        "b_mm",
        "Lado b",
        "Um lado da seção. O programa identifica qual é o maior.",
        60.0,
        "mm",
        minimo=0.01,
        passo=5.0,
        secao="Seção",
    ),
    Campo(
        "c_mm",
        "Lado c",
        "O outro lado da seção.",
        30.0,
        "mm",
        minimo=0.01,
        passo=1.0,
        secao="Seção",
    ),
    Campo(
        "torque_Nm",
        "Torque T",
        "O torque na seção.",
        500.0,
        "N·m",
        passo=10.0,
        secao="Esforços",
    ),
    Campo(
        "comprimento_mm",
        "Comprimento",
        "Comprimento da barra sob torção. Dá o giro total.",
        1000.0,
        "mm",
        minimo=0.01,
        passo=50.0,
        secao="Esforços",
    ),
    Campo(
        "g_GPa",
        "Módulo de cisalhamento G",
        "Aço: 79 GPa.",
        79.0,
        "GPa",
        minimo=1.0,
        passo=1.0,
        secao="Esforços",
    ),
    *_campos_da_verificacao(),
)


# ---------------------------------------------------------------------------
# Pino, vasos
# ---------------------------------------------------------------------------


def calcular_pinos(v: Valores) -> Resultado:
    forca = float(v["forca_kN"]) * 1000.0
    planos = 1 if str(v["corte"]) == "Simples" else 2
    estado = modelos.pino_cisalhamento(forca, float(v["d_mm"]), int(v["pinos"]), planos)
    return _fechar(
        v,
        (_ponto("Plano de corte, tensão média", estado),),
        estado,
        alertas=(
            "Este modelo traz só o corte médio. Para flexão do pino e esmagamento das chapas, "
            "use Pino de articulação.",
        ),
    )


def _membrana(diametro: float, espessura: float) -> tuple[list[str], list]:
    relacao = cargas.relacao_diametro_espessura(diametro, espessura)
    alertas = []
    if relacao < 20.0:
        alertas.append(
            "D/t < 20: a hipótese de parede fina pode ser inadequada. Use Cilindro de parede "
            "espessa."
        )
    linhas = [
        recomendacao_minima(
            "Parede fina (D/t)",
            relacao,
            20.0,
            "—",
            "abaixo de 20 as fórmulas de membrana perdem validade",
            REFERENCIA_RM,
        )
    ]
    return alertas, linhas


def calcular_cilindro_fino(v: Valores) -> Resultado:
    d = float(v["d_mm"])
    t = float(v["t_mm"])
    estado = modelos.tubo_fino_pressao_axial_torcao(
        float(v["pressao_MPa"]),
        d,
        t,
        bool(v["fechado"]),
        float(v["forca_kN"]) * 1000.0,
        float(v["torque_Nm"]) * 1000.0,
    )
    alertas, linhas = _membrana(d, t)
    return _fechar(
        v,
        (_ponto("Parede (x longitudinal, y circunferencial)", estado),),
        estado,
        alertas=alertas,
        verificacoes=linhas,
    )


def calcular_esfera(v: Valores) -> Resultado:
    d = float(v["d_mm"])
    t = float(v["t_mm"])
    estado = modelos.vaso_esferico_parede_fina(float(v["pressao_MPa"]), d, t)
    alertas, linhas = _membrana(d, t)
    return _fechar(v, (_ponto("Parede", estado),), estado, alertas=alertas, verificacoes=linhas)


def calcular_parede_espessa(v: Valores) -> Resultado:
    pi = float(v["pi_MPa"])
    pe = float(v["pe_MPa"])
    ri = float(v["ri_mm"])
    re = float(v["re_mm"])
    fechado = bool(v["fechado"])
    exigir(re > ri, "O raio externo deve ser maior que o interno.")

    def em(nome: str, r: float) -> Ponto:
        radial, circunferencial, longitudinal = modelos.tensoes_lame(pi, pe, ri, re, r, fechado)
        return Ponto(nome, radial, circunferencial, 0.0, longitudinal)

    pontos = (
        em("Parede interna", ri),
        em("Meio da parede", (ri + re) / 2.0),
        em("Parede externa", re),
    )
    base = EstadoPlanoCalculado(
        0.0,
        0.0,
        0.0,
        "Cilindro de parede espessa (Lamé)",
        (
            "Cilindro longo, de parede espessa, material elástico linear.",
            "Pressões interna e externa uniformes; sem gradiente térmico.",
            "O estado é triaxial e o von Mises desta página usa as três tensões. As outras "
            "análises recebem σ radial e σ circunferencial: a longitudinal fica aqui.",
            "As direções radial, circunferencial e longitudinal já são principais.",
            "Descontinuidades, bocais e tampas não incluídos.",
        ),
    )
    relacao = 2.0 * re / (re - ri)
    alertas = []
    if relacao >= 20.0:
        alertas.append(
            "Com D_e/t ≥ 20, o modelo de parede fina daria resultado equivalente com menos dados."
        )
    return _fechar(
        v,
        pontos,
        base,
        alertas=alertas,
        metricas=(Metrica("Relação D_e/t", relacao, "", 1),),
        extra=lambda r, _z: em("Raio informado", r),
    )


CAMPOS_PINOS = (
    Campo(
        "forca_kN",
        "Força total F",
        "A força que atravessa o conjunto de pinos.",
        20.0,
        "kN",
        passo=1.0,
        secao="Ligação",
    ),
    Campo(
        "d_mm",
        "Diâmetro resistente d",
        "Diâmetro no plano de corte. Se o corte cruzar a rosca, use o da raiz.",
        10.0,
        "mm",
        minimo=0.001,
        passo=1.0,
        secao="Ligação",
    ),
    Campo(
        "pinos",
        "Número de pinos",
        "Quantos pinos dividem a força.",
        1,
        minimo=1,
        maximo=500,
        passo=1,
        secao="Ligação",
    ),
    Campo(
        "corte",
        "Planos de corte",
        "Simples: duas chapas. Duplo: chapa central entre duas outras.",
        "Simples",
        opcoes=("Simples", "Duplo"),
        secao="Ligação",
    ),
    *_campos_da_verificacao(900.0),
)


def _campos_de_vaso() -> tuple[Campo, ...]:
    return (
        Campo(
            "pressao_MPa",
            "Pressão interna p",
            "1 MPa vale 10 bar.",
            2.0,
            "MPa",
            minimo=0.0,
            passo=0.1,
            secao="Vaso",
        ),
        Campo(
            "d_mm",
            "Diâmetro médio D",
            "Diâmetro medido no meio da parede.",
            500.0,
            "mm",
            minimo=0.001,
            passo=10.0,
            secao="Vaso",
        ),
        Campo(
            "t_mm",
            "Espessura t",
            "Espessura da parede.",
            5.0,
            "mm",
            minimo=0.001,
            passo=0.5,
            secao="Vaso",
        ),
    )


CAMPOS_CILINDRO_FINO = (
    *_campos_de_vaso(),
    Campo(
        "fechado",
        "Extremidades fechadas",
        "Com tampas, a pressão também puxa a parede no sentido do comprimento.",
        True,
        secao="Vaso",
    ),
    Campo(
        "forca_kN",
        "Força axial adicional F",
        "Força externa ao longo do tubo, além da pressão.",
        0.0,
        "kN",
        passo=1.0,
        secao="Esforços externos",
    ),
    Campo(
        "torque_Nm",
        "Torque adicional T",
        "Torque externo no tubo, além da pressão.",
        0.0,
        "N·m",
        passo=10.0,
        secao="Esforços externos",
    ),
    *_campos_da_verificacao(),
)

CAMPOS_ESFERA = (*_campos_de_vaso(), *_campos_da_verificacao())

CAMPOS_PAREDE_ESPESSA = (
    Campo(
        "pi_MPa",
        "Pressão interna p_i",
        "1 MPa vale 10 bar.",
        50.0,
        "MPa",
        passo=1.0,
        secao="Cilindro",
    ),
    Campo(
        "pe_MPa",
        "Pressão externa p_e",
        "Pressão por fora do cilindro.",
        0.0,
        "MPa",
        passo=1.0,
        secao="Cilindro",
    ),
    Campo(
        "ri_mm",
        "Raio interno r_i",
        "Raio do furo.",
        50.0,
        "mm",
        minimo=0.001,
        passo=1.0,
        secao="Cilindro",
    ),
    Campo(
        "re_mm",
        "Raio externo r_e",
        "Raio de fora. Deve ser maior que o interno.",
        80.0,
        "mm",
        minimo=0.001,
        passo=1.0,
        secao="Cilindro",
    ),
    Campo(
        "fechado",
        "Extremidades fechadas",
        "Inclui a tensão longitudinal gerada pelas tampas.",
        True,
        secao="Cilindro",
    ),
    *_campos_do_ponto(rotulo="Raio avaliado"),
    *_campos_da_verificacao(),
)


CASOS: tuple[Caso, ...] = (
    Caso(
        "Barra sob carga axial",
        "Barra sob carga axial",
        GRUPO_BARRAS,
        "Puxada ou empurrada no sentido do comprimento, carga no centro.",
        "Uma peça reta sendo puxada (tração) ou empurrada (compressão) no sentido do seu "
        "comprimento, como um tirante ou uma coluna curta. A tensão é a mesma em toda a seção.",
        CAMPOS_BARRA,
        calcular_barra,
        r"\sigma_x=\frac{F}{A}",
    ),
    Caso(
        "Barra sob carga axial excêntrica",
        "Barra sob carga axial excêntrica",
        GRUPO_BARRAS,
        "Carga axial aplicada fora do centro: comprime de um lado, traciona do outro.",
        "A força está deslocada do centroide, como num pilar carregado na borda. A excentricidade "
        "cria flexão e pode inverter o sinal da tensão em um dos lados. Os quatro cantos são "
        "avaliados.",
        CAMPOS_EXCENTRICA,
        calcular_excentrica,
        r"\sigma_x=\frac{F}{A}\left(1+\frac{12\,e_y\,y}{h^2}+\frac{12\,e_z\,z}{b^2}\right)",
    ),
    Caso(
        "Eixo circular maciço",
        "Eixo circular maciço",
        GRUPO_EIXOS,
        "Eixo redondo cheio sob força axial, flexão, torção e cortante.",
        "Eixo redondo cheio, puxado, dobrado e torcido ao mesmo tempo. Os lados tracionado e "
        "comprimido e a linha neutra são avaliados na superfície.",
        CAMPOS_EIXO_MACICO,
        calcular_eixo_macico,
        r"\sigma_x=\frac{F}{A}\pm\frac{32M}{\pi d^3},\qquad \tau_{xy}=\frac{16T}{\pi d^3}",
    ),
    Caso(
        "Eixo circular vazado",
        "Eixo circular vazado",
        GRUPO_EIXOS,
        "Tubo redondo sob os mesmos esforços do eixo maciço.",
        "Um tubo sob os mesmos esforços do eixo maciço. Costuma render mais rigidez por quilo, já "
        "que o material fica longe do centro.",
        CAMPOS_EIXO_VAZADO,
        calcular_eixo_vazado,
        r"\sigma_x=\frac{F}{A}\pm\frac{M(D_e/2)}{I},\qquad \tau_{xy}=\frac{T(D_e/2)}{J}",
    ),
    Caso(
        "Mola helicoidal de compressão",
        "Mola helicoidal de compressão",
        GRUPO_EIXOS,
        "Fio enrolado em espiras: a carga vira torção no fio. Só a tensão.",
        "Só a tensão no fio. Para rigidez, bloco, flambagem e fadiga, use o caso completo no "
        "grupo Molas.",
        CAMPOS_MOLA_SIMPLES,
        calcular_mola_simples,
        r"\tau=K_w\,\frac{8FD}{\pi d^3},\qquad K_w=f(C),\ C=D/d",
    ),
    Caso(
        "Viga de seção retangular",
        "Viga de seção retangular",
        GRUPO_VIGAS,
        "Viga retangular que dobra e sofre corte transversal.",
        "A flexão é máxima nas fibras extremas e o cisalhamento é máximo no centroide. O programa "
        "avalia cinco pontos da altura e indica o pior.",
        CAMPOS_VIGA,
        calcular_viga_retangular,
        r"\sigma_x=\frac{F}{A}-\frac{My}{I},\quad "
        r"\tau_{xy}=\frac{3V}{2A}\left[1-\left(\frac{2y}{h}\right)^2\right]",
    ),
    Caso(
        "Seção retangular com flexão biaxial",
        "Seção retangular com flexão biaxial",
        GRUPO_VIGAS,
        "Barra retangular que dobra nas duas direções ao mesmo tempo.",
        "A tensão crítica cai em um dos cantos da seção, onde as duas flexões se somam. Os quatro "
        "cantos são avaliados.",
        CAMPOS_BIAXIAL,
        calcular_biaxial,
        r"\sigma_x=\frac{F}{A}+\frac{M_y z}{I_y}-\frac{M_z y}{I_z}",
    ),
    Caso(
        "Torção de seção retangular",
        "Torção de seção retangular",
        GRUPO_VIGAS,
        "Barra retangular torcida: cisalhamento de Saint-Venant e giro.",
        "Em seção não circular, a fórmula de eixo redondo não vale: a tensão máxima fica no meio "
        "do lado maior e os cantos ficam sem tensão.",
        CAMPOS_TORCAO,
        calcular_torcao_retangular,
        r"\tau_{max}=\frac{T}{\alpha\,b\,c^2},\qquad \theta=\frac{T\,L}{\beta\,b\,c^3\,G}",
    ),
    Caso(
        MODELO_SECAO_I,
        MODELO_SECAO_I,
        GRUPO_PERFIS,
        "Perfil I: flexão nas mesas e cisalhamento na alma.",
        "As mesas absorvem a flexão e a alma absorve o cortante. Além das fibras extremas e do "
        "centroide, a junção entre mesa e alma entra na varredura, porque ali as duas se somam.",
        CAMPOS_PERFIL_I,
        calcular_perfil_i,
        r"\sigma_x=\frac{F}{A}-\frac{My}{I},\qquad \tau_{xy}=\frac{VQ}{I\,t}",
    ),
    Caso(
        "Perfil U sob força axial, flexão e cortante",
        "Perfil U sob força axial, flexão e cortante",
        GRUPO_PERFIS,
        "Canal laminado: como o I, mas com o centro de cisalhamento fora da alma.",
        "As contas de flexão e cortante são as do perfil I, mas um cortante aplicado no centroide "
        "também torce a peça.",
        CAMPOS_PERFIL_U,
        calcular_perfil_u,
        r"\sigma_x=\frac{F}{A}-\frac{My}{I},\qquad \tau_{xy}=\frac{VQ}{I\,t}",
    ),
    Caso(
        "Cantoneira de abas iguais",
        "Cantoneira de abas iguais",
        GRUPO_PERFIS,
        "Perfil L: os eixos das abas não são principais, então a flexão sai oblíqua.",
        "A fórmula σ = My/I sozinha engana aqui: o produto de inércia não é nulo e a linha neutra "
        "inclina. As duas pontas e o canto são avaliados.",
        CAMPOS_CANTONEIRA,
        calcular_cantoneira,
        r"\sigma_x=\frac{F}{A}+\frac{(M_yI_z+M_zI_{yz})z-(M_yI_{yz}+M_zI_y)y}{I_yI_z-I_{yz}^2}",
    ),
    Caso(
        "Perfil tubular retangular (caixão)",
        "Perfil tubular retangular (caixão)",
        GRUPO_PERFIS,
        "Tubo retangular fechado: flexão mais torção pela fórmula de Bredt.",
        "O tubo quadrado ou retangular usado em chassis e pórticos. Sendo fechado, resiste bem à "
        "torção, calculada pelo fluxo de cisalhamento de Bredt.",
        CAMPOS_CAIXAO,
        calcular_caixao,
        r"\sigma_x=\frac{F}{A}-\frac{My}{I},\qquad \tau=\frac{T}{2A_m t}",
    ),
    Caso(
        "Pinos ou parafusos sob cisalhamento",
        "Pinos ou parafusos sob cisalhamento",
        GRUPO_LIGACOES,
        "Pino cortado transversalmente pela força, em um ou dois planos.",
        "Divide a carga entre os pinos e os planos de corte e devolve a tensão média.",
        CAMPOS_PINOS,
        calcular_pinos,
        r"\tau_{media}=\frac{F}{n_p\,n_c\,(\pi d^2/4)}",
    ),
    Caso(
        "Vaso cilíndrico de parede fina",
        "Vaso cilíndrico de parede fina",
        GRUPO_PRESSAO,
        "Tubo ou vaso pressurizado com D/t ≥ 20, mais axial e torque.",
        "Tubo ou vaso com parede fina, como um cilindro de gás ou uma tubulação. Aceita força "
        "axial e torque somados à pressão.",
        CAMPOS_CILINDRO_FINO,
        calcular_cilindro_fino,
        r"\sigma_\theta=\frac{pD}{2t},\quad \sigma_{long}=\frac{pD}{4t}+\frac{F}{\pi Dt},\quad "
        r"\tau=\frac{2T}{\pi D^2t}",
    ),
    Caso(
        "Vaso esférico de parede fina",
        "Vaso esférico de parede fina",
        GRUPO_PRESSAO,
        "Tanque esférico pressurizado: mesma tensão nas duas direções.",
        "Por simetria, as duas tensões de membrana são iguais e valem metade da circunferencial "
        "de um cilindro de mesmo diâmetro.",
        CAMPOS_ESFERA,
        calcular_esfera,
        r"\sigma_x=\sigma_y=\frac{pD}{4t}",
    ),
    Caso(
        "Cilindro de parede espessa",
        "Cilindro de parede espessa",
        GRUPO_PRESSAO,
        "Solução de Lamé, com as três tensões: vale quando D/t < 20.",
        "Para tubos de alta pressão, blocos hidráulicos e camisas de cilindro. O estado é triaxial "
        "e o von Mises mostrado usa as três tensões, nas paredes interna e externa.",
        CAMPOS_PAREDE_ESPESSA,
        calcular_parede_espessa,
        r"\sigma_{r,\theta}=\frac{p_i r_i^2-p_e r_e^2}{r_e^2-r_i^2}"
        r"\mp\frac{(p_i-p_e)r_i^2r_e^2}{r^2\,(r_e^2-r_i^2)}",
    ),
)
