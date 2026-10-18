"""Cargas do piso pelo esqueleto do modelo: a carga por área de cada chapa vai às vigas que a apoiam.

O esqueleto da macro do SolidWorks (:mod:`core.leitura_do_modelo`) traz as chapas (forma CHAPA):
com a macro v5, o contorno da face maior e as aberturas; com a v4, só a caixa — e então só a chapa
que enche a caixa (retangular, sem recorte) é distribuída, porque a caixa de uma chapa recortada
mandaria carga para vigas embaixo de um buraco.

Para cada chapa de piso (até 60° com a horizontal):

* **vigas que a apoiam**: barras quase paralelas ao plano da chapa, logo abaixo dela (a linha de
  centro entre a face de baixo da chapa e uma altura de seção abaixo), cuja projeção cai na chapa;
* **área de influência**: cada pedaço da chapa (amostras a cada 2–10 cm) vai para a viga mais
  perto, no plano da chapa — numa chapa sobre vigas paralelas, metade do vão para cada lado; nos
  cantos de uma malha, as bissetrizes (o método das charneiras, a favor da prática usual);
* **carga**: q (kN/m², na projeção horizontal, como a NBR 6120 dá a sobrecarga) × área de influência
  × cos(inclinação) → total na viga; dividido pelo comprimento da viga, a carga distribuída
  uniforme para aplicar no Simulation (a viga inteira). O trecho carregado fica dito: carga só numa
  parte da viga é aviso.

A conferência fecha por construção: a soma das cargas nas vigas é q × a área projetada das chapas
distribuídas. Ponto da chapa a mais de 0,60 m da viga mais perto (balanço da chapa) é aviso.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace

from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import travamentos as tv

ORIGEM = "Esqueleto do modelo"
#: Linhas do peso do guarda-corpo nas bordas (core.guarda_corpo_do_modelo): o envio do piso as mantém.
MARCA_GUARDA_CORPO = "Guarda-corpo nas bordas"
VERTICAL = "Z (vertical)"  # valor positivo = para baixo (como em Cargas do esqueleto)
COS_PISO = 0.5  # chapa até 60° com a horizontal é piso (degrau, rampa, escada)
COS_PARALELA = 0.1  # viga quase paralela ao plano da chapa
FOLGA_M = 0.06  # entre a linha de centro da viga e a chapa, além da altura da seção
ALTURA_PADRAO_M = 0.30  # sem a seção medida (esqueleto antigo)
PREENCHIMENTO_MINIMO = 0.93  # volume ÷ caixa: abaixo disso a chapa tem recorte
AREA_MINIMA_M2 = 0.10  # menor que isso não é piso (chapa de ligação, nervura)
BALANCO_SUSPEITO_M = 0.60
TRECHO_PARCIAL = 0.80  # carga em menos de 80 % da viga: aviso
AMOSTRAS_POR_LADO = 60

Ponto2 = tuple[float, float]
Ponto3 = tuple[float, float, float]


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------------------------
# Geometria plana
# ---------------------------------------------------------------------------------------------
def area_do_poligono(pontos: Sequence[Ponto2]) -> float:
    soma = 0.0
    for (x1, y1), (x2, y2) in zip(pontos, [*pontos[1:], pontos[0]], strict=True):
        soma += x1 * y2 - x2 * y1
    return abs(soma) / 2


def dentro(ponto: Ponto2, poligono: Sequence[Ponto2]) -> bool:
    """Ponto dentro do polígono (paridade do raio horizontal)."""
    x, y = ponto
    resultado = False
    n = len(poligono)
    for i in range(n):
        x1, y1 = poligono[i]
        x2, y2 = poligono[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            cruza = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < cruza:
                resultado = not resultado
    return resultado


def distancia_ao_segmento(ponto: Ponto2, a: Ponto2, b: Ponto2) -> tuple[float, float]:
    """(distância, parâmetro em [0, 1] ao longo de ab)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    comprimento2 = dx * dx + dy * dy
    t = 0.0
    if comprimento2 > 0:
        t = max(0.0, min(1.0, ((ponto[0] - a[0]) * dx + (ponto[1] - a[1]) * dy) / comprimento2))
    return math.hypot(ponto[0] - a[0] - t * dx, ponto[1] - a[1] - t * dy), t


def envoltoria_convexa(pontos: Sequence[Ponto2]) -> list[Ponto2]:
    """A envoltória convexa (cadeia monótona), no sentido anti-horário."""
    unicos = sorted(set(pontos))
    if len(unicos) <= 2:
        return unicos

    def giro(o: Ponto2, a: Ponto2, b: Ponto2) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    baixo: list[Ponto2] = []
    for p in unicos:
        while len(baixo) >= 2 and giro(baixo[-2], baixo[-1], p) <= 0:
            baixo.pop()
        baixo.append(p)
    cima: list[Ponto2] = []
    for p in reversed(unicos):
        while len(cima) >= 2 and giro(cima[-2], cima[-1], p) <= 0:
            cima.pop()
        cima.append(p)
    return baixo[:-1] + cima[:-1]


def fora_da_envoltoria(ponto: Ponto2, envoltoria: Sequence[Ponto2]) -> float:
    """Quanto o ponto fica fora da envoltória convexa (m); 0 dentro dela."""
    if len(envoltoria) >= 3 and dentro(ponto, envoltoria):
        return 0.0
    if len(envoltoria) == 1:
        return math.dist(ponto, envoltoria[0])
    lados = list(zip(envoltoria, [*envoltoria[1:], envoltoria[0]], strict=True))
    return min(distancia_ao_segmento(ponto, a, b)[0] for a, b in lados)


def _normal_de_newell(pontos: Sequence[Ponto3]) -> Ponto3 | None:
    nx = ny = nz = 0.0
    for (x1, y1, z1), (x2, y2, z2) in zip(pontos, [*pontos[1:], pontos[0]], strict=True):
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return tv._unitario((nx, ny, nz))


# ---------------------------------------------------------------------------------------------
# Chapas de piso
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ChapaDoPiso:
    corpo: ld.CorpoDoModelo
    origem: Ponto3
    e1: Ponto3  # no plano da chapa
    e2: Ponto3
    normal: Ponto3  # para cima
    poligono: tuple[Ponto2, ...]  # m, nos eixos e1 e e2
    aberturas: tuple[tuple[Ponto2, ...], ...]
    fonte: str  # "contorno" (macro v5) ou "retângulo" (chapa que enche a caixa)
    inclinacao_graus: float

    @property
    def nome(self) -> str:
        return self.corpo.nome

    @property
    def area_m2(self) -> float:
        return area_do_poligono(self.poligono) - sum(area_do_poligono(a) for a in self.aberturas)

    @property
    def area_projetada_m2(self) -> float:
        return self.area_m2 * math.cos(math.radians(self.inclinacao_graus))

    def no_plano(self, ponto: Sequence[float]) -> Ponto2:
        d = tv._sub(ponto, self.origem)
        return (tv._dot(d, self.e1), tv._dot(d, self.e2))

    def altura(self, ponto: Sequence[float]) -> float:
        """Distância (m) do ponto ao plano da chapa, positiva para cima."""
        return tv._dot(tv._sub(ponto, self.origem), self.normal)


@dataclass(frozen=True)
class ChapaFora:
    """Chapa que não entra na distribuição, e por quê."""

    nome: str
    motivo: str


def _base(normal: Ponto3, preferida: Ponto3 | None) -> tuple[Ponto3, Ponto3]:
    e1 = None
    if preferida is not None:
        e1 = tv._unitario(tv._sub(preferida, tuple(tv._dot(preferida, normal) * c for c in normal)))
    if e1 is None:
        auxiliar = (1.0, 0.0, 0.0) if abs(normal[0]) < 0.9 else (0.0, 0.0, 1.0)
        e1 = tv._unitario(tv._cross(normal, auxiliar)) or (1.0, 0.0, 0.0)
    e2 = tv._unitario(tv._cross(normal, e1)) or (0.0, 1.0, 0.0)
    return e1, e2


def chapas_do_piso(
    g: ld.GeometriaDoModelo, eixo_vertical: str
) -> tuple[list[ChapaDoPiso], list[ChapaFora]]:
    """As chapas de piso do esqueleto, e as chapas que ficam de fora (com o motivo)."""
    cima = tv.vertical(eixo_vertical)
    chapas: list[ChapaDoPiso] = []
    fora: list[ChapaFora] = []
    for corpo in g.corpos:
        if corpo.forma != ld.FORMA_CHAPA:
            continue
        if len(corpo.contorno) >= 3:
            normal = _normal_de_newell(corpo.contorno)
            if normal is None:
                fora.append(ChapaFora(corpo.nome, "contorno sem área"))
                continue
            if tv._dot(normal, cima) < 0:
                normal = (-normal[0], -normal[1], -normal[2])
            if tv._dot(normal, cima) < COS_PISO:
                continue  # chapa em pé (ligação, nervura): não é piso
            origem = corpo.contorno[0]
            e1, e2 = _base(normal, tv._sub(corpo.contorno[1], corpo.contorno[0]))

            def plano(
                p: Sequence[float], o: Ponto3 = origem, a: Ponto3 = e1, b: Ponto3 = e2
            ) -> Ponto2:
                d = tv._sub(p, o)
                return (tv._dot(d, a), tv._dot(d, b))

            poligono = tuple(plano(p) for p in corpo.contorno)
            aberturas = tuple(tuple(plano(p) for p in a) for a in corpo.aberturas if len(a) >= 3)
            fonte = "contorno"
        else:
            eixo = tv._unitario(corpo.vetor)
            if eixo is None or corpo.secao_mm is None:
                fora.append(ChapaFora(corpo.nome, "sem as medidas da chapa"))
                continue
            largura = None
            if corpo.direcao_secao is not None:
                largura = tv._unitario(corpo.direcao_secao)
            if largura is None:
                # Sem a orientação (macro v4): a largura na horizontal, perpendicular ao eixo.
                largura = tv._unitario(tv._cross(cima, eixo))
            if largura is None:
                continue
            normal = tv._unitario(tv._cross(eixo, largura))
            if normal is None:
                continue
            if tv._dot(normal, cima) < 0:
                normal = (-normal[0], -normal[1], -normal[2])
            if tv._dot(normal, cima) < COS_PISO:
                continue
            comprimento, larg = corpo.comprimento_m, corpo.secao_mm[0] / 1e3
            if comprimento * larg < AREA_MINIMA_M2:
                continue
            espessura = corpo.secao_mm[1] / 1e3
            if corpo.volume_m3 is None or espessura <= 0:
                fora.append(
                    ChapaFora(corpo.nome, "sem o volume: não dá para saber se é retangular")
                )
                continue
            preenchimento = corpo.volume_m3 / (comprimento * larg * espessura)
            if preenchimento < PREENCHIMENTO_MINIMO:
                fora.append(
                    ChapaFora(
                        corpo.nome,
                        f"recortada (a chapa ocupa {_n(100 * preenchimento, 0)} % da caixa "
                        f"{_n(comprimento)} × {_n(larg)} m): sem o contorno da macro v5, a carga "
                        "não é distribuída",
                    )
                )
                continue
            origem = (
                (corpo.inicio[0] + corpo.fim[0]) / 2,
                (corpo.inicio[1] + corpo.fim[1]) / 2,
                (corpo.inicio[2] + corpo.fim[2]) / 2,
            )
            e1, e2 = eixo, tv._unitario(tv._cross(normal, eixo)) or largura
            meio_c, meio_l = comprimento / 2, larg / 2
            poligono = ((-meio_c, -meio_l), (meio_c, -meio_l), (meio_c, meio_l), (-meio_c, meio_l))
            aberturas = ()
            fonte = "retângulo"
        if area_do_poligono(poligono) < AREA_MINIMA_M2:
            continue
        inclinacao = math.degrees(math.acos(max(-1.0, min(1.0, tv._dot(normal, cima)))))
        chapas.append(
            ChapaDoPiso(corpo, origem, e1, e2, normal, poligono, aberturas, fonte, inclinacao)
        )
    return chapas, fora


def vigas_que_apoiam(
    g: ld.GeometriaDoModelo, chapa: ChapaDoPiso
) -> list[tuple[ld.CorpoDoModelo, Ponto2, Ponto2]]:
    """As barras logo abaixo da chapa, quase paralelas a ela, com a projeção no plano dela."""
    xs = [p[0] for p in chapa.poligono]
    ys = [p[1] for p in chapa.poligono]
    folga_planta = 0.10
    espessura = chapa.corpo.secao_mm[1] / 1e3 if chapa.corpo.secao_mm else 0.0
    resultado = []
    for corpo in g.corpos:
        if not corpo.e_barra or corpo.forma == ld.FORMA_BLOCO:
            continue
        eixo = tv._unitario(corpo.vetor)
        if eixo is None or abs(tv._dot(eixo, chapa.normal)) > COS_PARALELA:
            continue
        meio = tuple((a + b) / 2 for a, b in zip(corpo.inicio, corpo.fim, strict=True))
        altura = (corpo.secao_mm[0] / 1e3) if corpo.secao_mm else ALTURA_PADRAO_M
        # A origem de um contorno está numa face da chapa; a do retângulo, no meio da espessura.
        abaixo = -chapa.altura(meio)
        if not -FOLGA_M <= abaixo <= altura + espessura + FOLGA_M:
            continue
        a, b = chapa.no_plano(corpo.inicio), chapa.no_plano(corpo.fim)
        if (
            max(a[0], b[0]) < min(xs) - folga_planta
            or min(a[0], b[0]) > max(xs) + folga_planta
            or max(a[1], b[1]) < min(ys) - folga_planta
            or min(a[1], b[1]) > max(ys) + folga_planta
        ):
            continue
        resultado.append((corpo, a, b))
    return resultado


# ---------------------------------------------------------------------------------------------
# Distribuição
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class InfluenciaNaViga:
    """O que uma chapa manda para uma viga (sem a carga): área projetada e o trecho."""

    viga: str
    chapa: str
    area_projetada_m2: float
    trecho_m: float
    comprimento_m: float


@dataclass(frozen=True)
class CargaNaViga:
    caso: str
    viga: str
    kN_m: float  # uniforme na viga inteira: total ÷ comprimento
    total_kN: float
    trecho_m: float
    comprimento_m: float
    chapas: tuple[str, ...]


@dataclass(frozen=True)
class DistribuicaoDoPiso:
    chapas: tuple[ChapaDoPiso, ...]
    fora: tuple[ChapaFora, ...]
    influencias: tuple[InfluenciaNaViga, ...]
    cargas: tuple[CargaNaViga, ...]
    avisos: tuple[str, ...]

    @property
    def casos(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(c.caso for c in self.cargas))

    def do_caso(self, caso: str) -> list[CargaNaViga]:
        return [c for c in self.cargas if c.caso == caso]

    def total(self, caso: str) -> float:
        return sum(c.total_kN for c in self.cargas if c.caso == caso)

    @property
    def area_distribuida_m2(self) -> float:
        return sum(i.area_projetada_m2 for i in self.influencias)


def influencias(
    g: ld.GeometriaDoModelo, chapa: ChapaDoPiso
) -> tuple[list[InfluenciaNaViga], float, list[str]]:
    """A área de influência de cada viga sob a chapa, o maior balanço (m) e os avisos.

    Balanço é o quanto a chapa passa da envoltória das vigas que a apoiam (o que fica entre elas é
    vão da chapa, não balanço)."""
    vigas = vigas_que_apoiam(g, chapa)
    if not vigas:
        return (
            [],
            0.0,
            [f"{chapa.nome}: nenhuma viga logo abaixo da chapa — a carga dela fica de fora."],
        )
    xs = [p[0] for p in chapa.poligono]
    ys = [p[1] for p in chapa.poligono]
    passo = max(0.02, min(0.10, min(max(xs) - min(xs), max(ys) - min(ys)) / AMOSTRAS_POR_LADO))
    acumulado: dict[str, float] = {}
    trechos: dict[str, tuple[float, float]] = {}
    contagem = 0
    maior_distancia = 0.0
    # O que fica entre as vigas é vão da chapa; fora da envoltória delas, balanço.
    envoltoria = envoltoria_convexa([p for _, a, b in vigas for p in (a, b)])
    x = min(xs) + passo / 2
    while x < max(xs):
        y = min(ys) + passo / 2
        while y < max(ys):
            ponto = (x, y)
            if dentro(ponto, chapa.poligono) and not any(dentro(ponto, a) for a in chapa.aberturas):
                melhor = min(
                    ((distancia_ao_segmento(ponto, a, b), corpo) for corpo, a, b in vigas),
                    key=lambda par: par[0][0],
                )
                (distancia, t), corpo = melhor
                contagem += 1
                acumulado[corpo.nome] = acumulado.get(corpo.nome, 0.0) + 1
                inicio, fim = trechos.get(corpo.nome, (t, t))
                trechos[corpo.nome] = (min(inicio, t), max(fim, t))
                maior_distancia = max(maior_distancia, fora_da_envoltoria(ponto, envoltoria))
            y += passo
        x += passo
    if not contagem:
        return [], 0.0, [f"{chapa.nome}: o contorno não tem área para distribuir."]
    area = chapa.area_projetada_m2
    resultado = []
    for corpo, _, _ in vigas:
        if corpo.nome not in acumulado:
            continue
        inicio, fim = trechos[corpo.nome]
        resultado.append(
            InfluenciaNaViga(
                viga=corpo.nome,
                chapa=chapa.nome,
                area_projetada_m2=area * acumulado[corpo.nome] / contagem,
                trecho_m=max(fim - inicio, passo / max(corpo.comprimento_m, 1e-9))
                * corpo.comprimento_m,
                comprimento_m=corpo.comprimento_m,
            )
        )
    avisos = []
    if maior_distancia > BALANCO_SUSPEITO_M:
        avisos.append(
            f"{chapa.nome}: um ponto da chapa fica a {_n(maior_distancia)} m da viga mais perto "
            "(balanço da chapa) — confira se falta viga no esqueleto ou se o balanço é de "
            "propósito (a chapa precisa vencê-lo)."
        )
    return resultado, maior_distancia, avisos


def distribuir(
    g: ld.GeometriaDoModelo,
    cargas_por_area: Mapping[str, float],
    eixo_vertical: str,
    *,
    chapas_escolhidas: Iterable[str] | None = None,
) -> DistribuicaoDoPiso:
    """Cada caso (kN/m² na projeção horizontal) nas vigas que apoiam as chapas escolhidas."""
    todas, fora = chapas_do_piso(g, eixo_vertical)
    escolhidas = set(chapas_escolhidas) if chapas_escolhidas is not None else None
    chapas = [c for c in todas if escolhidas is None or c.nome in escolhidas]
    lista: list[InfluenciaNaViga] = []
    avisos: list[str] = []
    for chapa in chapas:
        resultado, _, avisos_da_chapa = influencias(g, chapa)
        lista.extend(resultado)
        avisos.extend(avisos_da_chapa)
    for f in fora:
        avisos.append(f"{f.nome}: {f.motivo}.")
    por_viga: dict[str, list[InfluenciaNaViga]] = {}
    for item in lista:
        por_viga.setdefault(item.viga, []).append(item)
    cargas: list[CargaNaViga] = []
    parciais: list[str] = []
    for caso, q in cargas_por_area.items():
        if not math.isfinite(q) or q == 0:
            continue
        for viga, itens in por_viga.items():
            comprimento = itens[0].comprimento_m
            total = q * sum(i.area_projetada_m2 for i in itens)
            trecho = min(comprimento, sum(i.trecho_m for i in itens))
            cargas.append(
                CargaNaViga(
                    caso=caso,
                    viga=viga,
                    kN_m=total / comprimento if comprimento > 0 else 0.0,
                    total_kN=total,
                    trecho_m=trecho,
                    comprimento_m=comprimento,
                    chapas=tuple(dict.fromkeys(i.chapa for i in itens)),
                )
            )
    for viga, itens in por_viga.items():
        trecho = min(itens[0].comprimento_m, sum(i.trecho_m for i in itens))
        if trecho < TRECHO_PARCIAL * itens[0].comprimento_m:
            parciais.append(f"{viga} ({_n(trecho)} de {_n(itens[0].comprimento_m)} m)")
    if parciais:
        avisos.append(
            f"Carga só em parte da viga: {ld._lista(parciais, 4)}. A tabela dá a carga uniforme "
            "na viga inteira (o mesmo total); para o momento sair certo, divida a viga no "
            "SolidWorks no fim da chapa ou aplique a carga só no trecho."
        )
    return DistribuicaoDoPiso(
        chapas=tuple(chapas),
        fora=tuple(fora),
        influencias=tuple(lista),
        cargas=tuple(cargas),
        avisos=tuple(avisos),
    )


# ---------------------------------------------------------------------------------------------
# Plano de cargas
# ---------------------------------------------------------------------------------------------
def cargas_por_area_do_plano(plano: pc.PlanoDeCargas) -> dict[str, float]:
    """Os casos do plano com carga por área (kN/m²), somada por caso."""
    resultado: dict[str, float] = {}
    for acao in plano.acoes:
        valor = sum(c.valor * c.quantidade for c in acao.cargas if c.unidade == "kN/m²")
        if valor:
            resultado[acao.codigo] = valor
    return resultado


def cargas_do_caso(
    d: DistribuicaoDoPiso, caso: str, nomes_no_simulation: Mapping[str, str] | None = None
) -> list[pc.CargaDoModelo]:
    """As linhas do plano: uma carga distribuída por viga (o corpo no SolidWorks)."""
    nomes = nomes_no_simulation or {}
    linhas = []
    for c in sorted(d.do_caso(caso), key=lambda c: c.viga):
        no_simulation = f" ({nomes[c.viga]})" if c.viga in nomes else ""
        linhas.append(
            pc.CargaDoModelo(
                elemento=f"{c.viga}{no_simulation}",
                valor=round(c.kN_m, 4),
                unidade="kN/m",
                direcao=VERTICAL,
                observacao=(
                    f"{_n(c.total_kN)} kN de {', '.join(c.chapas)}; trecho carregado "
                    f"{_n(c.trecho_m)} de {_n(c.comprimento_m)} m"
                ),
                quantidade=1,
                comprimento_m=c.comprimento_m,
            )
        )
    return linhas


def aplicar_no_plano(
    d: DistribuicaoDoPiso,
    plano: pc.PlanoDeCargas,
    cargas_por_area: Mapping[str, float],
    nomes_no_simulation: Mapping[str, str] | None = None,
) -> pc.PlanoDeCargas:
    """O plano com as cargas de cada caso nas vigas (as outras linhas do caso saem, menos o peso
    do guarda-corpo nas bordas, que tem envio próprio)."""
    for caso, q in cargas_por_area.items():
        linhas = cargas_do_caso(d, caso, nomes_no_simulation)
        if not linhas:
            continue
        anterior = plano.acao(caso)
        resumo = (
            f"{_n(q)} kN/m² nas chapas do esqueleto ({_n(d.area_distribuida_m2)} m² projetados), "
            f"pelas vigas que as apoiam: {_n(d.total(caso))} kN."
        )
        if anterior is None:
            acao = pc.nova_acao(caso, origem=ORIGEM, resumo=resumo, cargas=linhas)
        else:
            do_guarda_corpo = [
                c for c in anterior.cargas if c.observacao.startswith(MARCA_GUARDA_CORPO)
            ]
            if do_guarda_corpo and MARCA_GUARDA_CORPO in anterior.resumo:
                inicio = anterior.resumo.index(MARCA_GUARDA_CORPO)
                resumo += " | " + anterior.resumo[inicio:]
            acao = replace(
                anterior,
                origem=ORIGEM,
                resumo=resumo,
                cargas=tuple([*linhas, *do_guarda_corpo]),
                atualizado_em=pc.agora(),
            )
        plano = pc.com_acao(plano, acao)
    return plano


def csv_das_cargas(
    d: DistribuicaoDoPiso, nomes_no_simulation: Mapping[str, str] | None = None
) -> bytes:
    nomes = nomes_no_simulation or {}
    linhas = [
        "Caso;Viga (corpo no SolidWorks);Viga no Simulation;kN/m;Total (kN);Trecho carregado (m);Comprimento (m);Chapas"
    ]
    for c in d.cargas:
        linhas.append(
            ";".join(
                [
                    c.caso,
                    c.viga,
                    nomes.get(c.viga, ""),
                    _n(c.kN_m, 3).replace(".", ""),
                    _n(c.total_kN, 3).replace(".", ""),
                    _n(c.trecho_m, 3).replace(".", ""),
                    _n(c.comprimento_m, 3).replace(".", ""),
                    ", ".join(c.chapas),
                ]
            )
        )
    return ("\r\n".join(linhas) + "\r\n").encode("utf-8-sig")
