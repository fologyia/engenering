"""Comprimentos de flambagem pelo esqueleto do modelo: onde cada barra é travada, e em que direção.

O esqueleto da macro do SolidWorks (:mod:`core.leitura_do_modelo`) dá a linha de centro de cada
corpo. Uma barra é travada numa direção ``d`` onde outra barra se liga a ela (a ponta da outra
encosta nela, ou as duas se cruzam) **e** a outra tem componente em ``d`` (|cos| ≥ 0,5): uma viga
que chega ao pilar na direção X segura o pilar em X, não em Z. Entre dois travamentos, o trecho
destravado; o maior trecho é o comprimento de flambagem naquela direção, com K = 1 — o B₂ da
segunda ordem global (página Contraventamento) cobre o deslocamento lateral da estrutura (NBR 8800,
método da amplificação dos esforços). Ponta sem nada que a trave numa direção (e fora do apoio) é
balanço: K = 2,1, a favor da segurança (NBR 8800, Anexo E).

* **Pilar**: as duas direções em planta. Com a orientação da seção (macro v5: a direção da medida
  maior da seção, a alma de um I ou de um U), Lx é o trecho na direção da alma e Ly na da mesa; sem
  ela, Lx = Ly = o maior dos dois (a favor da segurança).
* **Viga**: Lx (no plano vertical) entre os apoios verticais (pontas e pilares, mãos-francesas
  embaixo); Ly e Lb entre os travamentos laterais (vigas e contraventamentos que chegam de lado).
  Chapa de piso apoiada na mesa superior trava a mesa comprimida no momento positivo, se for
  presa à viga — fica dito no motivo; o Lb sugerido não conta com ela.
* **Barra inclinada**: no plano vertical da barra e fora dele; contraventamento: Lx = Ly = o maior.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from core import leitura_do_modelo as ld

Vetor = tuple[float, float, float]

COS_TRAVA = 0.5  # a outra barra trava a direção d se |u_outra · d| ≥ 0,5 (60°)
COS_PARALELA = 0.95  # barras quase paralelas não se travam no meio (só nas pontas)
K_BALANCO = 2.1  # engaste e ponta livre (NBR 8800, Tabela E.1, valor recomendado)
PONTA_RELATIVA = 0.02  # ligação a menos de 2 % do comprimento (ou de 0,10 m) conta na ponta
TOLERANCIA_NO_M = 0.10  # ligações mais próximas que isso são o mesmo nó
BALANCO_DESPREZAVEL_M = 0.40  # sobra de esqueleto além do nó que não é balanço


def _sub(a: Sequence[float], b: Sequence[float]) -> Vetor:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Sequence[float], b: Sequence[float]) -> Vetor:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norma(a: Sequence[float]) -> float:
    return math.sqrt(_dot(a, a))


def _unitario(a: Sequence[float]) -> Vetor | None:
    n = _norma(a)
    return None if n < 1e-12 else (a[0] / n, a[1] / n, a[2] / n)


def vertical(eixo_vertical: str) -> Vetor:
    return (0.0, 1.0, 0.0) if eixo_vertical == "Y" else (0.0, 0.0, 1.0)


def mais_proximos(
    p1: Sequence[float], q1: Sequence[float], p2: Sequence[float], q2: Sequence[float]
) -> tuple[float, float, float]:
    """Os pontos mais próximos entre os segmentos p1q1 e p2q2: (s, t, distância), s e t em [0, 1]."""
    d1, d2, r = _sub(q1, p1), _sub(q2, p2), _sub(p1, p2)
    a, e, f = _dot(d1, d1), _dot(d2, d2), _dot(d2, r)
    if a <= 1e-18 and e <= 1e-18:
        return 0.0, 0.0, _norma(r)
    if a <= 1e-18:
        s, t = 0.0, min(1.0, max(0.0, f / e))
    else:
        c = _dot(d1, r)
        if e <= 1e-18:
            s, t = min(1.0, max(0.0, -c / a)), 0.0
        else:
            b = _dot(d1, d2)
            denominador = a * e - b * b
            s = min(1.0, max(0.0, (b * f - c * e) / denominador)) if denominador > 1e-18 else 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t, s = 0.0, min(1.0, max(0.0, -c / a))
            elif t > 1.0:
                t, s = 1.0, min(1.0, max(0.0, (b - c) / a))
    ponto1 = (p1[0] + d1[0] * s, p1[1] + d1[1] * s, p1[2] + d1[2] * s)
    ponto2 = (p2[0] + d2[0] * t, p2[1] + d2[1] * t, p2[2] + d2[2] * t)
    return s, t, _norma(_sub(ponto1, ponto2))


@dataclass(frozen=True)
class Ligacao:
    """Outra barra ligada a esta, a ``posicao_m`` do início (m), com a direção dela."""

    posicao_m: float
    corpo: str
    direcao: Vetor
    na_ponta_da_outra: bool


def ligacoes(g: ld.GeometriaDoModelo, corpo: ld.CorpoDoModelo) -> list[Ligacao]:
    """As barras que se ligam a ``corpo``: a ponta delas encosta nele, ou os dois se cruzam."""
    u = _unitario(corpo.vetor)
    if u is None:
        return []
    resultado = []
    for outro in g.corpos:
        if outro is corpo or outro.nome == corpo.nome or outro.forma == ld.FORMA_CHAPA:
            continue
        v = _unitario(outro.vetor)
        if v is None:
            continue
        s, t, distancia = mais_proximos(corpo.inicio, corpo.fim, outro.inicio, outro.fim)
        if distancia > ld.TOLERANCIA_LIGACAO_M:
            continue
        na_ponta_da_outra = t <= PONTA_RELATIVA or t >= 1 - PONTA_RELATIVA
        interior_desta = PONTA_RELATIVA < s < 1 - PONTA_RELATIVA
        if interior_desta and not na_ponta_da_outra and abs(_dot(u, v)) >= COS_PARALELA:
            continue  # paralelas lado a lado: não é ligação
        resultado.append(Ligacao(s * corpo.comprimento_m, outro.nome, v, na_ponta_da_outra))
    return sorted(resultado, key=lambda lig: lig.posicao_m)


def chapa_em_cima(g: ld.GeometriaDoModelo, corpo: ld.CorpoDoModelo, eixo_vertical: str) -> str:
    """O nome de uma chapa apoiada sobre a barra horizontal (mesa superior), ou ``""``."""
    cima = vertical(eixo_vertical)
    meio = tuple((a + b) / 2 for a, b in zip(corpo.inicio, corpo.fim, strict=True))
    altura = (corpo.secao_mm[0] / 1e3) if corpo.secao_mm else 0.30
    for chapa in g.corpos:
        if chapa.forma != ld.FORMA_CHAPA:
            continue
        centro = tuple((a + b) / 2 for a, b in zip(chapa.inicio, chapa.fim, strict=True))
        acima = _dot(_sub(centro, meio), cima)
        if not 0.0 <= acima <= altura / 2 + 0.06:
            continue
        # Dentro da caixa da chapa em planta (o meio da viga sob a chapa).
        eixo = _unitario(chapa.vetor)
        if eixo is None or chapa.secao_mm is None:
            continue
        largura = _unitario(_cross(cima, eixo))
        if largura is None:
            continue
        delta = _sub(meio, centro)
        if (
            abs(_dot(delta, eixo)) <= chapa.comprimento_m / 2
            and abs(_dot(delta, largura)) <= chapa.secao_mm[0] / 2e3
        ):
            return chapa.nome
    return ""


@dataclass(frozen=True)
class ComprimentosSugeridos:
    lx_m: float | None
    ly_m: float | None
    lb_m: float | None
    motivo: str
    travamentos_m: tuple[float, ...] = ()
    balanco: bool = False


def _no_apoio(g: ld.GeometriaDoModelo, ponto: Sequence[float], eixo_vertical: str) -> bool:
    i = 1 if eixo_vertical == "Y" else 2
    piso = min(min(c.inicio[i], c.fim[i]) for c in g.corpos)
    return abs(ponto[i] - piso) <= ld.TOLERANCIA_LIGACAO_M


def _agrupar(pontos: Sequence[float]) -> list[float]:
    """Pontos a menos de 0,10 m um do outro são o mesmo nó (a média deles)."""
    grupos: list[list[float]] = []
    for p in sorted(pontos):
        if grupos and p - grupos[-1][-1] <= TOLERANCIA_NO_M:
            grupos[-1].append(p)
        else:
            grupos.append([p])
    return [sum(g) / len(g) for g in grupos]


def _trecho(
    comprimento: float,
    pontos: Sequence[float],
    inicio_travado: bool,
    fim_travado: bool,
) -> tuple[float | None, bool]:
    """O maior trecho destravado e se há balanço (ponta livre: K = 2,1 no trecho dela).

    A ponta de um esqueleto passa um pouco do nó (a peça vai até a face, o corte tem folga): esse
    resto de até 0,40 m não é balanço quando a barra tem um vão de verdade.
    """
    perto = _perto_da_ponta(comprimento)
    internos = [p for p in pontos if perto < p < comprimento - perto]
    nos = _agrupar(
        [*internos, *((0.0,) if inicio_travado else ()), *((comprimento,) if fim_travado else ())]
    )
    if not nos:
        return None, False
    trechos = [b - a for a, b in zip(nos, nos[1:], strict=False)]
    balancos = []
    if not inicio_travado and nos[0] > 0:
        balancos.append(nos[0])
    if not fim_travado and comprimento - nos[-1] > 0:
        balancos.append(comprimento - nos[-1])
    relevantes = [b for b in balancos if b > BALANCO_DESPREZAVEL_M or not trechos]
    trechos += [K_BALANCO * b for b in relevantes]
    maior = max(trechos, default=0.0)
    return (maior if maior > 0 else None), bool(relevantes)


def _perto_da_ponta(comprimento: float) -> float:
    return max(PONTA_RELATIVA * comprimento, TOLERANCIA_NO_M)


def _m(valor: float | None) -> str:
    return "—" if valor is None else f"{valor:.2f}".replace(".", ",")


def comprimentos(
    g: ld.GeometriaDoModelo,
    corpo: ld.CorpoDoModelo,
    tipo: str,
    eixo_vertical: str,
) -> ComprimentosSugeridos:
    """Lx, Ly e Lb sugeridos pelos travamentos do esqueleto (K = 1; balanço, K = 2,1)."""
    u = _unitario(corpo.vetor)
    if u is None or corpo.comprimento_m <= 0:
        return ComprimentosSugeridos(None, None, None, "")
    cima = vertical(eixo_vertical)
    comprimento = corpo.comprimento_m
    todas = ligacoes(g, corpo)

    def travam(direcao: Vetor, apoios_contam: bool) -> list[float]:
        # Apoio (pilar, poste que termina na barra) segura a viga de lado e contra a torção.
        return [
            lig.posicao_m
            for lig in todas
            if abs(_dot(lig.direcao, direcao)) >= COS_TRAVA
            or (
                apoios_contam
                and lig.na_ponta_da_outra
                and abs(_dot(lig.direcao, cima)) >= COS_TRAVA
            )
        ]

    def ponta_travada(posicao: float, ponto: Sequence[float]) -> bool:
        # Na ponta, qualquer ligação faz um nó da estrutura (o deslocamento do nó é o da
        # estrutura, que o B₂ cobre); só a ponta que não encosta em nada é livre (balanço).
        if _no_apoio(g, ponto, eixo_vertical):
            return True
        return any(
            abs(lig.posicao_m - posicao) <= _perto_da_ponta(comprimento) + 1e-9 for lig in todas
        )

    def na_direcao(
        direcao: Vetor, apoios_contam: bool = False
    ) -> tuple[float | None, bool, list[float]]:
        pontos = travam(direcao, apoios_contam)
        maior, balanco = _trecho(
            comprimento,
            pontos,
            ponta_travada(0.0, corpo.inicio),
            ponta_travada(comprimento, corpo.fim),
        )
        return maior, balanco, pontos

    orientacao = None
    if corpo.direcao_secao is not None:
        a = _sub(corpo.direcao_secao, tuple(_dot(corpo.direcao_secao, u) * x for x in u))
        orientacao = _unitario(a)
    lateral_horizontal = _unitario(_cross(u, cima))
    if abs(_dot(u, cima)) >= ld.VERTICAL_MINIMO:
        # Pilar: as duas direções em planta (ou as da seção, com a orientação).
        if orientacao is not None:
            d1 = orientacao
            d2 = _unitario(_cross(u, d1)) or (1.0, 0.0, 0.0)
        else:
            d1, d2 = (1.0, 0.0, 0.0), ((0.0, 0.0, 1.0) if eixo_vertical == "Y" else (0.0, 1.0, 0.0))
        l1, b1, p1 = na_direcao(d1)
        l2, b2, p2 = na_direcao(d2)
        travamentos = tuple(sorted({*p1, *p2}))
        balanco = b1 or b2
        if orientacao is not None:
            lx, ly = l1, l2
            motivo = (
                f"pilar travado a cada {_m(l1)} m na direção da alma e {_m(l2)} m na da mesa "
                "(orientação da seção pela macro)"
            )
        else:
            maior = max((v for v in (l1, l2) if v is not None), default=None)
            lx = ly = maior
            nomes = ("X", "Z") if eixo_vertical == "Y" else ("X", "Y")
            motivo = (
                f"pilar: maior trecho destravado de {_m(l1)} m em {nomes[0]} e {_m(l2)} m em "
                f"{nomes[1]}; sem a orientação da seção (macro v5), Lx = Ly = o maior"
            )
        if balanco:
            motivo += "; ponta livre numa direção: balanço, K = 2,1"
        return ComprimentosSugeridos(lx, ly, ly, motivo, travamentos, balanco)
    if lateral_horizontal is None:
        return ComprimentosSugeridos(None, None, None, "")
    no_plano = _unitario(_cross(lateral_horizontal, u)) or cima
    if orientacao is not None and abs(_dot(orientacao, lateral_horizontal)) > 0.7:
        # Seção deitada: a alma está na horizontal.
        no_plano, lateral_horizontal = lateral_horizontal, no_plano
    lx, bx, px = na_direcao(no_plano)
    ly, by, py = na_direcao(lateral_horizontal, apoios_contam=True)
    travamentos = tuple(sorted({*px, *py}))
    balanco = bx or by
    if tipo in (ld.TIPO_CONTRAVENTAMENTO, "Diagonal"):
        maior = max((v for v in (lx, ly) if v is not None), default=None)
        motivo = (
            f"contraventamento: {_m(lx)} m no plano e {_m(ly)} m fora dele entre ligações; "
            "Lx = Ly = o maior"
        )
        return ComprimentosSugeridos(maior, maior, maior, motivo, travamentos, balanco)
    motivo = (
        f"viga: apoios verticais a cada {_m(lx)} m (Lx); travamentos laterais a cada {_m(ly)} m "
        "(Ly e Lb)"
    )
    chapa = chapa_em_cima(g, corpo, eixo_vertical) if abs(_dot(u, cima)) <= 0.1 else ""
    if chapa:
        motivo += (
            f"; a chapa {chapa} apoia na mesa superior: presa à viga, ela trava a mesa comprimida "
            "no momento positivo e o Lb pode ser menor — o sugerido não conta com ela"
        )
    if balanco:
        motivo += "; ponta livre: balanço, K = 2,1"
    return ComprimentosSugeridos(lx, ly, ly, motivo, travamentos, balanco)
