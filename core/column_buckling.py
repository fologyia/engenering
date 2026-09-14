"""Flambagem geral de colunas: esbeltez, Euler, transição de Johnson e secante.

Este módulo é deliberadamente independente de qualquer norma de aço: cobre
o modelo clássico de Euler/Johnson válido para qualquer material e seção
(retangular, circular, tubular, perfil de catálogo ou área/raio de giração
informados diretamente). Para o dimensionamento normativo de perfis de aço
(NBR 8800/AISC, com o fator de redução χ), veja
:mod:`core.steel_member_design`.

O que o modelo faz e o que ele só **avisa**:

* carga crítica de Euler (coluna longa) e parábola de Johnson (curta e
  intermediária), no eixo de maior esbeltez;
* opcionalmente, a **fórmula da secante** para carga excêntrica — a tensão
  máxima na fibra extrema com a amplificação de segunda ordem, e a carga
  que leva essa fibra ao escoamento;
* avisos para o que fica fora do cálculo mas pode governar: esbeltez de
  parede (flambagem local), esbeltez global acima do limite usual de
  norma, K fora da faixa física e unidades implausíveis de E e Sy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core.steel_sections import PerfilAco


@dataclass(frozen=True)
class ElementoLocal:
    """Uma parede de parede fina cuja esbeltez ``b/t`` pode governar.

    O limite é ``coeficiente·√(E/Sy)`` (chapas: mesa, alma, parede de tubo
    retangular) ou ``coeficiente·E/Sy`` (tubo circular, ``D/t``), os
    coeficientes usuais de norma para elemento comprimido não esbelto.
    """

    nome: str
    razao: float
    coeficiente: float
    quadratico: bool = False

    def limite(self, modulo_elasticidade_MPa: float, escoamento_MPa: float) -> float:
        base = modulo_elasticidade_MPa / escoamento_MPa
        return self.coeficiente * (base if self.quadratico else math.sqrt(base))


@dataclass(frozen=True)
class GeometriaColuna:
    """Área, raios de giração e, quando conhecidas, as distâncias às fibras.

    ``distancia_fibra_x_mm`` é a distância do centroide à fibra mais afastada
    na flexão em torno de **x** (meia altura numa seção simétrica), usada só
    pela fórmula da secante; zero significa desconhecida. ``elementos_locais``
    lista as paredes cuja esbeltez ``b/t`` o cálculo confere para avisar de
    flambagem local.
    """

    area_mm2: float
    raio_giracao_x_mm: float
    raio_giracao_y_mm: float
    descricao: str = ""
    distancia_fibra_x_mm: float = 0.0
    distancia_fibra_y_mm: float = 0.0
    elementos_locais: tuple[ElementoLocal, ...] = ()

    def distancia_fibra(self, eixo: str) -> float:
        return self.distancia_fibra_x_mm if eixo == "x" else self.distancia_fibra_y_mm


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
    avisos: tuple[str, ...] = ()
    # Fórmula da secante (só com excentricidade > 0): eixo de flexão da
    # excentricidade, tensão máxima na fibra extrema sob a carga atuante,
    # carga que leva essa fibra ao escoamento e o fator P_y / P.
    eixo_excentricidade: str = ""
    excentricidade_mm: float = 0.0
    tensao_maxima_secante_MPa: float | None = None
    carga_escoamento_secante_N: float | None = None
    fator_seguranca_secante: float | None = None


# Fator de comprimento efetivo K por condição de apoio idealizada (valores
# teóricos). Condições reais quase sempre ficam entre estes casos — o
# engenheiro deve escolher o mais próximo e favorável à segurança.
CONDICOES_APOIO: dict[str, float] = {
    "Biapoiada (pino-pino)": 1.0,
    "Engastada-livre (em balanço)": 2.0,
    "Engastada-pino": 0.70,
    "Biengastada": 0.50,
    "Biengastada com translação (deslocável)": 1.0,
    "Engastada-pino com translação (deslocável)": 2.0,
}

# Valores recomendados para projeto (AISC, Tabela C-A-7.1; NBR 8800 usa os
# mesmos): ligações reais nunca são o engaste perfeito, então K sobe.
CONDICOES_APOIO_RECOMENDADAS: dict[str, float] = {
    "Biapoiada (pino-pino)": 1.0,
    "Engastada-livre (em balanço)": 2.1,
    "Engastada-pino": 0.80,
    "Biengastada": 0.65,
    "Biengastada com translação (deslocável)": 1.2,
    "Engastada-pino com translação (deslocável)": 2.0,
}

# Esbeltez global acima da qual as normas de aço deixam de admitir a peça
# comprimida (NBR 8800 e AISC: 200). Não é limite físico do modelo — Euler
# continua valendo —, mas uma coluna nessa faixa é frágil a imperfeições.
ESBELTEZ_MAXIMA_USUAL = 200.0

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
# Geometrias
# ---------------------------------------------------------------------------


def geometria_retangular(largura_mm: float, altura_mm: float) -> GeometriaColuna:
    """Seção retangular maciça. ``largura`` (b, em x) e ``altura`` (h, em y)."""
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
        distancia_fibra_x_mm=h / 2.0,
        distancia_fibra_y_mm=b / 2.0,
    )


def geometria_circular_macica(diametro_mm: float) -> GeometriaColuna:
    d = _positivo("diametro_mm", diametro_mm)
    area = math.pi * d**2 / 4.0
    inercia = math.pi * d**4 / 64.0
    raio = math.sqrt(inercia / area)
    return GeometriaColuna(
        area,
        raio,
        raio,
        f"Circular maciça, d = {d:g} mm",
        distancia_fibra_x_mm=d / 2.0,
        distancia_fibra_y_mm=d / 2.0,
    )


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
    espessura = (de - di) / 2.0
    return GeometriaColuna(
        area,
        raio,
        raio,
        f"Tubular d={de:g}/{di:g} mm",
        distancia_fibra_x_mm=de / 2.0,
        distancia_fibra_y_mm=de / 2.0,
        # Tubo circular comprimido: D/t ≤ 0,11·E/Sy para a parede não flambar
        # antes da coluna (limite de elemento não esbelto das normas de aço).
        elementos_locais=(
            ElementoLocal("parede do tubo (D/t)", de / espessura, 0.11, quadratico=True),
        ),
    )


def _familia(perfil: PerfilAco) -> str:
    familia = str(getattr(perfil, "familia", "") or "").strip().casefold()
    return familia.split()[0] if familia else ""


def _elementos_locais_do_perfil(perfil: PerfilAco) -> tuple[ElementoLocal, ...]:
    """Paredes do perfil e os coeficientes de esbeltez limite (AISC B4.1a).

    Mesa de I/W/HP/T (``b/2t``) e mesa de U/C (``b/t``): 0,56; alma de I/W/
    U/C (``h/tw``): 1,49; talão do T (``d/tw``): 0,75; parede de tubo
    retangular (``b/t``): 1,40; tubo circular (``D/t``): 0,11·E/Sy. Perfis
    maciços não têm parede a flambar.
    """
    familia = _familia(perfil)
    h = float(perfil.altura_mm)
    b = float(perfil.largura_mm)
    tw = float(perfil.espessura_alma_mm)
    tf = float(perfil.espessura_mesa_mm)
    completa = str(getattr(perfil, "familia", "") or "").casefold()
    if tw <= 0 or tf <= 0:
        return ()
    if "tubo" in completa and ("circ" in completa or "redond" in completa):
        return (ElementoLocal("parede do tubo (D/t)", h / tw, 0.11, quadratico=True),)
    if "tubo" in completa:
        t = min(tw, tf)
        return (ElementoLocal("parede maior do tubo (b/t)", (max(h, b) - 2.0 * t) / t, 1.40),)
    if "barra" in completa:
        return ()
    if familia in {"i", "w", "hp", "hea", "heb", "hem", "ipe", "ipn"}:
        return (
            ElementoLocal("mesa (b/2t)", (b / 2.0) / tf, 0.56),
            ElementoLocal("alma (h/tw)", (h - 2.0 * tf) / tw, 1.49),
        )
    if familia in {"u", "c", "upn"}:
        return (
            ElementoLocal("mesa (b/t)", b / tf, 0.56),
            ElementoLocal("alma (h/tw)", (h - 2.0 * tf) / tw, 1.49),
        )
    if familia == "t":
        return (
            ElementoLocal("mesa (b/2t)", (b / 2.0) / tf, 0.56),
            ElementoLocal("talão (d/tw)", h / tw, 0.75),
        )
    return ()


def geometria_perfil_catalogo(perfil: PerfilAco) -> GeometriaColuna:
    distancias_x = getattr(perfil, "distancias_fibras_x_mm", (perfil.altura_mm / 2.0,) * 2)
    distancias_y = getattr(perfil, "distancias_fibras_y_mm", (perfil.largura_mm / 2.0,) * 2)
    return GeometriaColuna(
        area_mm2=perfil.area_mm2,
        raio_giracao_x_mm=perfil.rx_mm,
        raio_giracao_y_mm=perfil.ry_mm,
        descricao=f"Perfil {perfil.nome}",
        distancia_fibra_x_mm=max(distancias_x),
        distancia_fibra_y_mm=max(distancias_y),
        elementos_locais=_elementos_locais_do_perfil(perfil),
    )


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
    As distâncias às fibras só são necessárias para a fórmula da secante.
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
# Fórmula da secante
# ---------------------------------------------------------------------------


def tensao_maxima_secante(
    carga_N: float,
    *,
    area_mm2: float,
    raio_giracao_mm: float,
    distancia_fibra_mm: float,
    comprimento_efetivo_mm: float,
    excentricidade_mm: float,
    modulo_elasticidade_MPa: float,
) -> float:
    """``σ_máx = (P/A)·[1 + (e·c/r²)·sec((L_e/2r)·√(P/(E·A)))]``.

    É a tensão de compressão na fibra extrema de uma coluna com carga
    excêntrica, já com a amplificação de segunda ordem (a flecha aumenta o
    braço da carga). Tende ao infinito quando ``P`` se aproxima da carga de
    Euler — por isso a carga de escoamento pela secante é sempre menor que
    a crítica, e a diferença é justamente o efeito da imperfeição.
    """
    carga = _nao_negativo("carga_N", carga_N)
    area = _positivo("area_mm2", area_mm2)
    raio = _positivo("raio_giracao_mm", raio_giracao_mm)
    c = _nao_negativo("distancia_fibra_mm", distancia_fibra_mm)
    le = _positivo("comprimento_efetivo_mm", comprimento_efetivo_mm)
    e = _nao_negativo("excentricidade_mm", excentricidade_mm)
    modulo = _positivo("modulo_elasticidade_MPa", modulo_elasticidade_MPa)
    if carga == 0.0:
        return 0.0
    argumento = (le / (2.0 * raio)) * math.sqrt(carga / (modulo * area))
    if argumento >= math.pi / 2.0:
        return math.inf
    return (carga / area) * (1.0 + (e * c / raio**2) / math.cos(argumento))


def carga_de_escoamento_secante(
    escoamento_MPa: float,
    *,
    area_mm2: float,
    raio_giracao_mm: float,
    distancia_fibra_mm: float,
    comprimento_efetivo_mm: float,
    excentricidade_mm: float,
    modulo_elasticidade_MPa: float,
) -> float:
    """Carga ``P_y`` que leva a fibra extrema ao escoamento pela secante.

    ``σ_máx(P)`` cresce monotonicamente com ``P`` e diverge na carga de
    Euler do eixo, então a raiz está sempre em ``(0, P_cr)`` e a bisseção a
    encontra sem chute inicial.
    """
    sy = _positivo("escoamento_MPa", escoamento_MPa)
    area = _positivo("area_mm2", area_mm2)
    raio = _positivo("raio_giracao_mm", raio_giracao_mm)
    le = _positivo("comprimento_efetivo_mm", comprimento_efetivo_mm)
    modulo = _positivo("modulo_elasticidade_MPa", modulo_elasticidade_MPa)
    parametros = dict(
        area_mm2=area,
        raio_giracao_mm=raio,
        distancia_fibra_mm=distancia_fibra_mm,
        comprimento_efetivo_mm=le,
        excentricidade_mm=excentricidade_mm,
        modulo_elasticidade_MPa=modulo,
    )
    carga_euler = math.pi**2 * modulo * area / (le / raio) ** 2
    baixo, alto = 0.0, min(carga_euler, sy * area * (1.0 + 1e-9))
    # Sem excentricidade a secante vira σ = P/A: a raiz é o esmagamento ou
    # Euler, o que vier primeiro.
    if tensao_maxima_secante(alto * (1.0 - 1e-12), **parametros) <= sy:
        return alto
    for _ in range(200):
        meio = 0.5 * (baixo + alto)
        if tensao_maxima_secante(meio, **parametros) > sy:
            alto = meio
        else:
            baixo = meio
        if alto - baixo <= 1e-12 * alto:
            break
    return 0.5 * (baixo + alto)


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
            f"Sy/E = {escoamento_MPa / modulo_elasticidade_MPa:.3g} corresponde a "
            "deformação de escoamento acima de 5 %, que nenhum material estrutural "
            "tem. Confira as unidades: Sy e E em MPa."
        )
    return avisos


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
    excentricidade_mm: float = 0.0,
    eixo_excentricidade: str = "governante",
) -> ResultadoFlambagem:
    """Verifica flambagem por Euler, com transição de Johnson para colunas curtas.

    O modelo assume compressão centrada, coluna prismática e material
    elástico linear até a transição. Com ``excentricidade_mm > 0`` a
    fórmula da secante entra como verificação adicional: tensão máxima na
    fibra extrema sob a carga atuante e carga que leva essa fibra ao
    escoamento. ``eixo_excentricidade`` é o eixo de flexão que a
    excentricidade provoca (``"x"``, ``"y"`` ou ``"governante"``).

    Imperfeições, flambagem local e torcional não entram no número — mas o
    resultado **avisa** quando a esbeltez de parede, a esbeltez global ou o
    K indicam que elas podem governar.
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
    excentricidade = _nao_negativo("excentricidade_mm", excentricidade_mm)
    eixo_excentricidade = str(eixo_excentricidade).strip().lower() or "governante"
    if eixo_excentricidade not in {"x", "y", "governante"}:
        raise ValueError("eixo_excentricidade deve ser 'x', 'y' ou 'governante'.")

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

    avisos = _avisos_de_entrada(kx, ky, e, sy)
    if esbeltez_governante > ESBELTEZ_MAXIMA_USUAL:
        avisos.append(
            f"Esbeltez governante λ = {esbeltez_governante:.0f} acima de "
            f"{ESBELTEZ_MAXIMA_USUAL:.0f}, o limite usual de norma para peças "
            "comprimidas: a carga crítica de Euler continua válida, mas uma coluna "
            "assim é muito sensível a imperfeições, excentricidade e vibração."
        )
    for elemento in geometria.elementos_locais:
        limite = elemento.limite(e, sy)
        if elemento.razao > limite:
            avisos.append(
                f"Flambagem local pode governar: {elemento.nome} = {elemento.razao:.1f} "
                f"acima do limite de elemento não esbelto ({limite:.1f}"
                + (", 0,11·E/Sy" if elemento.quadratico else f", {elemento.coeficiente:g}·√(E/Sy)")
                + "). Este módulo não considera a flambagem da parede — a capacidade "
                "real é menor que a calculada; use Estruturas de aço ou uma seção mais compacta."
            )

    # -- fórmula da secante ---------------------------------------------------
    eixo_secante = eixo_governante if eixo_excentricidade == "governante" else eixo_excentricidade
    tensao_secante: float | None = None
    carga_escoamento: float | None = None
    fator_secante: float | None = None
    if excentricidade > 0:
        raio = rx if eixo_secante == "x" else ry
        comprimento_efetivo = lx if eixo_secante == "x" else ly
        distancia_fibra = geometria.distancia_fibra(eixo_secante)
        if distancia_fibra <= 0:
            raise ValueError(
                "A fórmula da secante precisa da distância do centroide à fibra "
                f"extrema no eixo {eixo_secante} (distancia_fibra_{eixo_secante}_mm), "
                "que esta geometria não informa."
            )
        parametros = dict(
            area_mm2=area,
            raio_giracao_mm=raio,
            distancia_fibra_mm=distancia_fibra,
            comprimento_efetivo_mm=comprimento_efetivo,
            excentricidade_mm=excentricidade,
            modulo_elasticidade_MPa=e,
        )
        tensao_secante = tensao_maxima_secante(solicitante, **parametros)
        carga_escoamento = carga_de_escoamento_secante(sy, **parametros)
        fator_secante = math.inf if solicitante <= 0 else carga_escoamento / solicitante
        if math.isinf(tensao_secante):
            avisos.append(
                f"Com excentricidade e = {excentricidade:g} mm no eixo {eixo_secante}, a "
                "carga atuante já atinge a carga de Euler desse eixo: a flecha cresce "
                "sem limite (fórmula da secante)."
            )
        elif fator_secante < fs_desejado:
            avisos.append(
                f"Com excentricidade e = {excentricidade:g} mm no eixo {eixo_secante}, a "
                f"fibra extrema atinge Sy com P = {carga_escoamento / 1_000.0:.2f} kN "
                f"(fator {fator_secante:.2f} contra o desejado {fs_desejado:g}); a tensão "
                f"máxima sob a carga atuante é {tensao_secante:.1f} MPa. A excentricidade "
                "governa sobre Euler/Johnson."
            )

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
        avisos=tuple(avisos),
        eixo_excentricidade=eixo_secante if excentricidade > 0 else "",
        excentricidade_mm=excentricidade,
        tensao_maxima_secante_MPa=tensao_secante,
        carga_escoamento_secante_N=carga_escoamento,
        fator_seguranca_secante=fator_secante,
    )
