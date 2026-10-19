"""Para que lado o Simulation virou a seção de cada pilar: as direções 1 e 2 da viga no espaço.

O SolidWorks Simulation lista os esforços de cada viga nos eixos dela (ajuda do SOLIDWORKS, "Beam
Directions"): o **axial** vai do Fim 1 ao Fim 2, a **direção 1** é paralela à aresta reta mais
longa da seção e a **direção 2** fica a 90° dela, no sentido anti-horário — o triedro axial–1–2 é
destro (conferido nos arquivos reais do usuário: 2 422 elementos de 2 422). O **sentido** da direção
1 não sai da geometria (no mesmo modelo, muda de viga para viga) e a API do Simulation não o dá.
O programa o tira dos próprios resultados:

1. **A linha da direção 1**: a macro v6 mede a seção no SolidWorks (a face reta mais larga ao longo
   da barra é a aresta reta mais longa da seção); sem ela, sai do perfil — U e I com a alma reta
   mais alta que a mesa, tubo retangular — e da direção da alma da macro v5.
2. **O axial**: a ponta da base é a do Fim 1 quando a base é o início da lista (quadro das
   fundações), e o axial sobe; no fim da lista, desce. O peso próprio confere: dentro dos elementos
   do pilar, a carga do PP aponta para baixo.
3. **O sentido**: num caso com carga distribuída transversal no pilar (o vento viga a viga põe
   carga em cada pilar), a carga que o Simulation mostra dentro dos elementos (a variação de V₁ e
   V₂ de uma ponta à outra de cada elemento) tem de apontar para onde o plano de cargas mandou e
   ter o mesmo tamanho. Só um sentido bate. Sem a linha (cantoneira de abas iguais, tubo quadrado
   ou redondo, macro v5), o caso dá o ângulo inteiro; dois casos têm de concordar entre si.

Com o triedro, a reação na base (a força que o apoio faz no pilar) vira um vetor da planta:
``R = F_a·a + F₁·d₁ + F₂·d₂`` com ``F`` a força na ponta da base. Sem um caso com carga no pilar,
o sentido fica sem saber e V₁/V₂ continuam só no rótulo — o motivo vai junto.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core import cena_3d as c3
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import quadro_fundacoes as qf
from core import vento_por_barras as vpb

Ponto = tuple[float, float, float]

CODIGO_PP = "PP"
CARGA_MINIMA_KN = 0.05  # carga transversal total no pilar: abaixo disso, ruído
RAZAO_MINIMA, RAZAO_MAXIMA = 0.5, 2.0  # medida no Simulation ÷ a do plano
ANGULO_MAXIMO_GRAUS = 20.0  # entre a linha da seção e a dos resultados
ESPALHAMENTO_MAXIMO_GRAUS = 10.0  # entre os casos, sem a linha
FOLGA_MINIMA_MM = 1.0  # abaixo disso a aresta mais longa empata (o Simulation escolhe)
FOLGA_DO_PERFIL = 1.15  # alma reta / mesa: acima disso (ou abaixo do inverso), sem dúvida
COS_PERPENDICULAR = 0.9  # a linha precisa ficar perto do plano da seção

LINHA_MACRO = "macro v6 (a face reta mais larga da seção)"
LINHA_PERFIL = "perfil e alma (macro v5)"
LINHA_RESULTADOS = "resultados (a carga no pilar)"


def _sub(a: Sequence[float], b: Sequence[float]) -> Ponto:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Sequence[float], b: Sequence[float]) -> Ponto:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _escala(a: Sequence[float], k: float) -> Ponto:
    return (a[0] * k, a[1] * k, a[2] * k)


def _soma(a: Sequence[float], b: Sequence[float]) -> Ponto:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _norma(a: Sequence[float]) -> float:
    return math.sqrt(_dot(a, a))


def _unitario(a: Sequence[float]) -> Ponto | None:
    n = _norma(a)
    if not math.isfinite(n) or n <= 1e-12:
        return None
    return (a[0] / n, a[1] / n, a[2] / n)


def _no_plano(v: Sequence[float], eixo: Sequence[float]) -> Ponto:
    """A parte de ``v`` perpendicular ao ``eixo`` (unitário)."""
    return _sub(v, _escala(eixo, _dot(v, eixo)))


def _n(valor: float, casas: int = 1) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _graus(radianos: float) -> float:
    """Ângulo em graus em (−180, 180]."""
    g = math.degrees(radianos) % 360.0
    return g - 360.0 if g > 180.0 else g


# ---------------------------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class DirecoesDaSecao:
    """O triedro do Simulation de um pilar, na planta (X e Y horizontais, Z para cima)."""

    viga: str  # o nome no Simulation
    corpo: str
    axial: Ponto  # do Fim 1 ao Fim 2
    d1: Ponto | None
    d2: Ponto | None
    sinal_da_base: float  # força na ponta da base = sinal × esforço interno gravado (−1 no Fim 1)
    linha: str  # de onde veio a linha da direção 1 (LINHA_*), ou vazio
    sentido: str  # os casos que deram o sentido, ou o motivo de não saber
    diferenca_graus: float | None = None  # entre a linha da seção e a dos resultados

    @property
    def sabida(self) -> bool:
        return self.d1 is not None and self.d2 is not None

    def reacao(self, carga: qf.CargaNaBase) -> Ponto | None:
        """A força que o apoio faz no pilar (kN, planta), com o esforço interno da base."""
        if self.d1 is None or self.d2 is None:
            return None
        # A força na ponta da base, nos eixos da viga: sinal × esforço interno; o N do quadro é a
        # compressão positiva (o axial interno é −N).
        s = self.sinal_da_base
        fa, f1, f2 = s * -carga.n, s * carga.v1, s * carga.v2
        return _soma(_soma(_escala(self.axial, fa), _escala(self.d1, f1)), _escala(self.d2, f2))

    def horizontal(self, carga: qf.CargaNaBase) -> Ponto | None:
        """Só a parte transversal da reação (V₁ e V₂ no espaço), kN."""
        if self.d1 is None or self.d2 is None:
            return None
        s = self.sinal_da_base
        return _soma(_escala(self.d1, s * carga.v1), _escala(self.d2, s * carga.v2))


@dataclass(frozen=True)
class DirecoesDosPilares:
    pilares: Mapping[str, DirecoesDaSecao]
    avisos: tuple[str, ...] = ()

    @property
    def sabidas(self) -> int:
        return sum(1 for d in self.pilares.values() if d.sabida)


# ---------------------------------------------------------------------------------------------
# A carga dentro dos elementos
# ---------------------------------------------------------------------------------------------
def carga_nos_elementos(pontos: Sequence[em.PontoDeEsforco]) -> Ponto:
    """A carga distribuída total na barra, nos eixos dela (kN): em cada elemento, a carga é o
    esforço interno no Fim 1 menos o do Fim 2 (sem cargas nos nós, que ficam entre elementos)."""
    por_elemento: dict[str, dict[str, em.PontoDeEsforco]] = {}
    for p in pontos:
        por_elemento.setdefault(p.elemento, {})[p.fim] = p
    total = [0.0, 0.0, 0.0]
    for pontas in por_elemento.values():
        a, b = pontas.get("1"), pontas.get("2")
        if a is None or b is None:
            continue
        total[0] += a.n - b.n
        total[1] += a.v1 - b.v1
        total[2] += a.v2 - b.v2
    return (total[0], total[1], total[2])


def _base_e_topo(corpo: ld.CorpoDoModelo, eixo_vertical: str) -> tuple[Ponto, Ponto]:
    a = vpb.para_a_planta(corpo.inicio, eixo_vertical)
    b = vpb.para_a_planta(corpo.fim, eixo_vertical)
    return (a, b) if a[2] <= b[2] else (b, a)


def _linha_pelo_perfil(
    corpo: ld.CorpoDoModelo, secao: c3.Secao | None, eixo_vertical: str, axial: Ponto
) -> Ponto | None:
    """Sem a macro v6: a aresta reta mais longa pelo perfil e a alma da v5 (só sem dúvida)."""
    if secao is None or corpo.direcao_secao is None:
        return None
    alma = _unitario(_no_plano(vpb.para_a_planta(corpo.direcao_secao, eixo_vertical), axial))
    if alma is None:
        return None
    if secao.forma in (c3.FORMA_U, c3.FORMA_I):
        reta = secao.d - 2.0 * secao.tf
        if reta >= FOLGA_DO_PERFIL * secao.b:
            return alma
        if secao.forma == c3.FORMA_I and secao.b >= FOLGA_DO_PERFIL * reta:
            # A mesa é a mais longa, mas a "alma" da v5 é a medida maior da caixa: só vale se a
            # caixa não for quase quadrada (senão a v5 pode ter dado a mesa).
            if secao.d >= FOLGA_DO_PERFIL * secao.b:
                return _unitario(_cross(axial, alma))
        return None
    if secao.forma == c3.FORMA_TUBO_RETANGULAR and secao.d >= FOLGA_DO_PERFIL * secao.b:
        return alma
    return None


def _angulo_pelo_caso(
    axial: Ponto, aplicada: Ponto, medida: tuple[float, float]
) -> tuple[float, Ponto, Ponto] | None:
    """O ângulo da direção 1 (a partir de e₁, no plano da seção) que leva a carga medida nos eixos
    da viga (``medida`` = carga em 1 e 2) à aplicada; e a base (e₁, e₂) desse plano."""
    referencia = (1.0, 0.0, 0.0) if abs(axial[0]) < 0.9 else (0.0, 1.0, 0.0)
    e1 = _unitario(_no_plano(referencia, axial))
    if e1 is None:  # pragma: no cover - a referência nunca é paralela ao axial
        return None
    e2 = _cross(axial, e1)
    g = (_dot(aplicada, e1), _dot(aplicada, e2))
    return math.atan2(g[1], g[0]) - math.atan2(medida[1], medida[0]), e1, e2


def _media_circular(angulos: Sequence[float]) -> tuple[float, float]:
    """Média de ângulos (rad) e o maior afastamento dela (graus)."""
    media = math.atan2(sum(math.sin(a) for a in angulos), sum(math.cos(a) for a in angulos))
    afastamento = max(abs(_graus(a - media)) for a in angulos)
    return media, afastamento


# ---------------------------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------------------------
def _direcoes_do_pilar(
    pilar: qf.PilarDoQuadro,
    corpo: ld.CorpoDoModelo,
    dados: em.EsforcosDoModelo,
    eixo_vertical: str,
    cargas_aplicadas: Mapping[str, Mapping[str, Ponto]],
    secao: c3.Secao | None,
) -> DirecoesDaSecao:
    base, topo = _base_e_topo(corpo, eixo_vertical)
    subida = _unitario(_sub(topo, base)) or (0.0, 0.0, 1.0)
    pontos_por_caso = {
        k: c.membros[pilar.pilar] for k, c in dados.casos.items() if pilar.pilar in c.membros
    }
    qualquer = next(iter(pontos_por_caso.values()), ())
    vazio = DirecoesDaSecao(pilar.pilar, corpo.nome, subida, None, None, 1.0, "", "")
    if not qualquer or pilar.base is None:
        return _com(vazio, sentido="sem a ponta da base no quadro das fundações")
    ponto_da_base = qualquer[0] if pilar.base == qf.BASE_INICIO else qualquer[-1]
    no_fim_1 = ponto_da_base.fim == "1"
    axial = subida if no_fim_1 else _escala(subida, -1.0)
    sinal = -1.0 if no_fim_1 else 1.0
    vazio = DirecoesDaSecao(pilar.pilar, corpo.nome, axial, None, None, sinal, "", "")
    # O peso próprio confere o axial: a carga ao longo do pilar aponta para baixo.
    pp = pontos_por_caso.get(CODIGO_PP)
    if pp:
        carga_pp = carga_nos_elementos(pp)
        para_baixo = -axial[2]  # componente axial de (0, 0, −1)
        if abs(carga_pp[0]) >= CARGA_MINIMA_KN and abs(para_baixo) > 0.5:
            if carga_pp[0] * para_baixo < 0:
                return _com(
                    vazio,
                    sentido=(
                        "a ordem dos elementos do pilar no arquivo não confere com o peso "
                        "próprio (o PP aponta para cima ao longo dele): escolha a base na tabela "
                        "das barras"
                    ),
                )
    # A linha da direção 1.
    linha: Ponto | None = None
    fonte = ""
    if corpo.direcao_1 is not None:
        folga = corpo.folga_da_direcao_1_mm
        candidata = _unitario(_no_plano(vpb.para_a_planta(corpo.direcao_1, eixo_vertical), axial))
        bruta = _unitario(vpb.para_a_planta(corpo.direcao_1, eixo_vertical))
        if (
            candidata is not None
            and bruta is not None
            and abs(_dot(candidata, bruta)) >= COS_PERPENDICULAR
            and (folga is None or folga >= FOLGA_MINIMA_MM)
        ):
            linha, fonte = candidata, LINHA_MACRO
    if linha is None:
        pelo_perfil = _linha_pelo_perfil(corpo, secao, eixo_vertical, axial)
        if pelo_perfil is not None:
            linha, fonte = pelo_perfil, LINHA_PERFIL
    # O sentido (e, sem a linha, o ângulo) pelos casos com carga transversal no pilar.
    angulos: list[float] = []
    usados: list[str] = []
    recusados: list[str] = []
    base_do_plano: tuple[Ponto, Ponto] | None = None
    for caso, pontos in pontos_por_caso.items():
        if caso == CODIGO_PP:
            continue
        aplicada_total = cargas_aplicadas.get(caso, {}).get(corpo.nome)
        if aplicada_total is None:
            continue
        aplicada = _no_plano(aplicada_total, axial)
        medida_total = carga_nos_elementos(pontos)
        medida = (medida_total[1], medida_total[2])
        tamanho_aplicado, tamanho_medido = _norma(aplicada), math.hypot(*medida)
        if tamanho_aplicado < CARGA_MINIMA_KN:
            continue
        if not RAZAO_MINIMA <= tamanho_medido / tamanho_aplicado <= RAZAO_MAXIMA:
            recusados.append(
                f"{caso}: o Simulation mostra {_n(tamanho_medido, 2)} kN ao longo do pilar e o "
                f"plano manda {_n(tamanho_aplicado, 2)} kN"
            )
            continue
        resultado = _angulo_pelo_caso(axial, aplicada, medida)
        if resultado is None:  # pragma: no cover
            continue
        angulo, e1, e2 = resultado
        angulos.append(angulo)
        usados.append(caso)
        base_do_plano = (e1, e2)
    if not angulos or base_do_plano is None:
        motivo = (
            "sem caso com carga transversal no pilar (importe um caso de vento viga a viga, que "
            "põe carga em cada pilar)"
        )
        if recusados:
            motivo = "a carga no pilar não bate com o plano — " + "; ".join(recusados[:2])
        return _com(vazio, linha=fonte, sentido=motivo)
    media, afastamento = _media_circular(angulos)
    e1, e2 = base_do_plano
    pelos_resultados = _soma(_escala(e1, math.cos(media)), _escala(e2, math.sin(media)))
    casos = ", ".join(usados)
    if linha is None:
        if afastamento > ESPALHAMENTO_MAXIMO_GRAUS:
            return _com(
                vazio,
                sentido=f"os casos {casos} dão direções diferentes ({_n(afastamento)}° de "
                "diferença)",
            )
        d1 = pelos_resultados
        return DirecoesDaSecao(pilar.pilar, corpo.nome, axial, d1, _cross(axial, d1), sinal,
                               LINHA_RESULTADOS, casos)  # fmt: skip
    cos = _dot(linha, pelos_resultados)
    diferenca = math.degrees(math.acos(min(1.0, abs(cos))))
    if diferenca > ANGULO_MAXIMO_GRAUS:
        return _com(
            vazio,
            linha=fonte,
            sentido=(
                f"a direção 1 pela seção e pelos resultados ({casos}) diferem {_n(diferenca)}°: "
                "confira o perfil e o caso"
            ),
            diferenca_graus=diferenca,
        )
    d1 = linha if cos > 0 else _escala(linha, -1.0)
    return DirecoesDaSecao(pilar.pilar, corpo.nome, axial, d1, _cross(axial, d1), sinal, fonte,
                           casos, diferenca)  # fmt: skip


def _com(base: DirecoesDaSecao, **campos: object) -> DirecoesDaSecao:
    from dataclasses import replace

    return replace(base, **campos)  # type: ignore[arg-type]


def direcoes_dos_pilares(
    quadro: qf.QuadroDeFundacoes,
    dados: em.EsforcosDoModelo,
    corpos_das_vigas: Mapping[str, ld.CorpoDoModelo],
    eixo_vertical: str,
    cargas_aplicadas: Mapping[str, Mapping[str, Ponto]],
    secoes: Mapping[str, c3.Secao] | None = None,
) -> DirecoesDosPilares:
    """O triedro de cada pilar do quadro das fundações (pelo nome no Simulation).

    ``cargas_aplicadas``: caso → corpo → carga distribuída total que o plano manda (kN, planta).
    ``secoes``: corpo → seção, para a linha da direção 1 sem a macro v6.
    """
    pilares: dict[str, DirecoesDaSecao] = {}
    for pilar in quadro.pilares:
        corpo = corpos_das_vigas.get(pilar.pilar)
        if corpo is None:
            continue
        try:
            pilares[pilar.pilar] = _direcoes_do_pilar(
                pilar, corpo, dados, eixo_vertical, cargas_aplicadas, (secoes or {}).get(corpo.nome)
            )
        except (ArithmeticError, ValueError) as erro:  # pragma: no cover - dado estragado
            pilares[pilar.pilar] = DirecoesDaSecao(
                pilar.pilar, corpo.nome, (0.0, 0.0, 1.0), None, None, 1.0, "", f"erro: {erro}"
            )
    avisos: list[str] = []
    sem = [d for d in pilares.values() if not d.sabida]
    if pilares and sem:
        motivos: dict[str, list[str]] = {}
        for d in sem:
            motivos.setdefault(d.sentido, []).append(d.viga)
        partes = [
            f"{', '.join(nomes[:3])}{'…' if len(nomes) > 3 else ''}: {motivo}"
            for motivo, nomes in motivos.items()
        ]
        avisos.append(
            f"Reação horizontal sem direção em {len(sem)} de {len(pilares)} pilar(es) — V₁ e V₂ "
            "ficam no rótulo. " + " · ".join(partes[:3]) + "."
        )
    return DirecoesDosPilares(pilares, tuple(avisos))


def conferir_horizontais(
    direcoes: DirecoesDosPilares,
    quadro: qf.QuadroDeFundacoes,
    caso: str,
    reacao_total: Ponto | None,
) -> str:
    """A soma das reações horizontais desenhadas contra a do arquivo de reações (planta), quando
    todos os pilares têm a direção; vazio quando não dá para conferir."""
    if reacao_total is None or not direcoes.pilares or direcoes.sabidas < len(direcoes.pilares):
        return ""
    soma = (0.0, 0.0, 0.0)
    for pilar in quadro.pilares:
        d = direcoes.pilares.get(pilar.pilar)
        carga = next((c for c in pilar.cargas if c.caso == caso), None)
        if d is None or carga is None:
            return ""
        h = d.horizontal(carga)
        if h is None:
            return ""
        soma = _soma(soma, h)
    calculada = math.hypot(soma[0], soma[1])
    arquivo = math.hypot(reacao_total[0], reacao_total[1])
    diferenca = math.hypot(soma[0] - reacao_total[0], soma[1] - reacao_total[1])
    if diferenca <= max(0.05, 0.05 * max(arquivo, calculada)):
        return (
            f"As reações horizontais dos pilares ({_n(calculada, 2)} kN) fecham com a do arquivo "
            f"de reações ({_n(arquivo, 2)} kN) no caso {caso}."
        )
    return (
        f"As reações horizontais dos pilares somam {_n(calculada, 2)} kN e o arquivo de reações "
        f"dá {_n(arquivo, 2)} kN no caso {caso}: há apoio fora dos pilares do quadro, diagonal "
        "chegando na base ou um caso trocado — confira."
    )
