"""O que o esqueleto do modelo diz para a página Contraventamento de estruturas abertas.

Em vez de digitar a planta, as cotas, os vãos e o contraventamento, o programa lê o esqueleto da
macro do SolidWorks:

* **Pilares**: barras em pé (até 15° do prumo) que chegam no chão; as linhas de pilares em X e em
  Y dão os vãos e as medidas **entre eixos** (L_x, L_y).
* **Pisos**: as cotas das vigas deitadas (:func:`core.contraventamento_vento_barras.niveis_do_esqueleto`)
  e a **área de piso** de cada nível pelas chapas deitadas (o peso por área multiplica essa área,
  não L_x × L_y — numa plataforma em balanço ou com recorte, as duas são diferentes).
* **Diagonais de contraventamento**: barras inclinadas num plano vertical X ou Y que vencem pelo
  menos metade da altura do andar e saem do pé de um pilar (ou do nível de baixo, junto a ele).
  Mão-francesa (curta, perto do topo) e longarina de escada (não sai de pilar) não contam. Duas
  diagonais que se cruzam no mesmo plano e andar são um **X**; que se encontram em cima, um **V
  invertido**; sozinha, **diagonal simples**. Duas barras no mesmo lugar (pontas a menos de 15 cm)
  viram aviso — no Simulation, cada uma é uma viga inteira.
* **Perfis**: o mais comum dos pilares e das vigas; o das diagonais, se for de uma família da
  página (cantoneira, tubo, barra redonda).

Uma direção sem diagonal nenhuma é dita com todas as letras: a estabilidade nela é de pórtico
(engaste ou ligação rígida, mãos-francesas), e a página não verifica isso.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from core import cargas_pelo_modelo as cpm
from core import contraventamento_barras as cb
from core import contraventamento_plataforma as cp
from core import contraventamento_vento_barras as cvb
from core import leitura_do_modelo as ld
from core import vento_por_barras as vpb

COS_PILAR = math.cos(math.radians(15.0))
PE_NO_CHAO_M = 0.30
MESMA_LINHA_M = 0.25  # pilares e planos de diagonais a menos disso são da mesma linha
JUNTO_AO_PILAR_M = 0.35  # a ponta de baixo da diagonal sai do pilar
NO_NIVEL_M = 0.50  # a ponta de baixo da diagonal fica no pé do andar
ALTURA_MINIMA = 0.50  # fração da altura do andar que a diagonal vence
INCLINACAO_DIAGONAL = (15.0, 75.0)  # graus com a horizontal
NO_PLANO = 0.90  # |cos| da projeção horizontal com X ou Y
SOBREPOSTAS_M = 0.15
ENCONTRO_M = 0.30
PISO_DEITADO_GRAUS = 5.0
NIVEL_DA_CHAPA_M = 0.30

Ponto = tuple[float, float, float]


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


@dataclass(frozen=True)
class Diagonal:
    nome: str
    baixo: Ponto  # planta, m (z a partir do terreno)
    alto: Ponto
    perfil: str
    direcao: str  # "X" ou "Y": a força que ela resiste
    plano_m: float  # y (direção X) ou x (direção Y) do plano
    andar: int


@dataclass(frozen=True)
class SistemaNoEsqueleto:
    """O contraventamento de uma direção como a página pede."""

    direcao: str
    tipo: str
    linhas: int
    paineis_por_linha: int
    perfil: str  # o mais comum das diagonais
    familia: str  # cb.FAMILIA_* ou vazio (perfil fora das famílias da página)
    diagonais: tuple[str, ...]


@dataclass(frozen=True)
class EsqueletoDoContraventamento:
    lx_m: float
    ly_m: float
    vaos_x: int
    vaos_y: int
    cotas_m: tuple[float, ...]
    area_de_piso_m2: float | None
    pilar: str
    viga: str
    sistemas: dict[str, SistemaNoEsqueleto] = field(default_factory=dict)
    pilares: tuple[str, ...] = ()
    linhas_de_pilares: tuple[int, int] = (0, 0)  # quantas linhas de pilares em X e em Y
    maos_francesas: int = 0
    avisos: tuple[str, ...] = ()

    def sistema(self, direcao: str) -> SistemaNoEsqueleto | None:
        return self.sistemas.get(direcao)


def _agrupar(valores: Sequence[float], tolerancia: float) -> list[float]:
    """Os centros dos grupos de valores a menos de ``tolerancia`` um do outro."""
    grupos: list[list[float]] = []
    for v in sorted(valores):
        if grupos and v - grupos[-1][-1] <= tolerancia:
            grupos[-1].append(v)
        else:
            grupos.append([v])
    return [sum(g) / len(g) for g in grupos]


def _mais_comum(nomes: Sequence[str]) -> str:
    validos = [n for n in nomes if n]
    return Counter(validos).most_common(1)[0][0] if validos else ""


def _familia(perfil: str) -> str:
    for familia in cb.FAMILIAS:
        if perfil and perfil in cb.perfis_da_familia(familia):
            return familia
    return ""


def _andar(z: float, cotas: Sequence[float]) -> int:
    """O andar (1 = do chão ao primeiro piso) que contém a cota ``z``."""
    abaixo = 0.0
    for i, cota in enumerate(cotas, start=1):
        if z <= cota:
            return i
        abaixo = cota
    return len(cotas) if cotas and z > abaixo else 1


def ler_esqueleto(
    g: ld.GeometriaDoModelo, eixo_vertical: str, cota_do_terreno_m: float | None = None
) -> EsqueletoDoContraventamento | None:
    """O que o esqueleto diz da estrutura; ``None`` sem barras."""
    blocos = {c.nome for c in g.corpos if c.forma == ld.FORMA_BLOCO}
    barras = [b for b in vpb.barras_do_esqueleto(g, eixo_vertical) if b.nome not in blocos]
    if not barras:
        return None
    if cota_do_terreno_m is not None:
        terreno = float(cota_do_terreno_m)
    else:
        pelos_pilares = vpb.terreno_dos_pilares(barras)
        terreno = (
            min(min(b.inicio[2], b.fim[2]) for b in barras)
            if pelos_pilares is None
            else pelos_pilares
        )

    def rel(p: Ponto) -> Ponto:
        return (p[0], p[1], p[2] - terreno)

    avisos: list[str] = []
    cotas = cvb.niveis_do_esqueleto(barras, terreno)
    # Pilares: em pé, com o pé no chão e o topo no primeiro piso (o poste de um patamar de
    # escada não é pilar da plataforma).
    pilares = []
    postes = []
    for b in barras:
        dz = abs(b.fim[2] - b.inicio[2])
        if b.comprimento_m > 0 and dz / b.comprimento_m >= COS_PILAR:
            pe = rel(b.inicio if b.inicio[2] <= b.fim[2] else b.fim)
            topo = max(b.inicio[2], b.fim[2]) - terreno
            if pe[2] <= PE_NO_CHAO_M:
                if not cotas or topo >= cotas[0] - NO_NIVEL_M:
                    pilares.append((b, pe))
                else:
                    postes.append(b.nome)
    if postes:
        avisos.append(
            f"{', '.join(postes[:3])}{'…' if len(postes) > 3 else ''}: em pé no chão, mas sem "
            "chegar ao piso (poste de patamar de escada?) — não conta como pilar da plataforma."
        )
    xs = _agrupar([pe[0] for _, pe in pilares], MESMA_LINHA_M)
    ys = _agrupar([pe[1] for _, pe in pilares], MESMA_LINHA_M)
    planta = cvb._planta_dos_pisos(barras, terreno, cotas)
    piso_x, piso_y = planta[0] if planta else (0.0, 0.0)
    if len(xs) >= 2:
        lx, vaos_x = xs[-1] - xs[0], len(xs) - 1
    else:
        lx, vaos_x = piso_x, 1
    if len(ys) >= 2:
        ly, vaos_y = ys[-1] - ys[0], len(ys) - 1
    else:
        ly, vaos_y = piso_y, 1
    for direcao, linhas, piso in (("X", xs, piso_x), ("Y", ys, piso_y)):
        if pilares and len(linhas) < 2:
            avisos.append(
                f"Os pilares estão numa linha só na direção {direcao}: a estrutura vai em balanço "
                f"nessa direção (piso de {_n(piso)} m). L_{direcao.lower()} fica com a medida do "
                "piso, e o modelo da página (pórticos entre linhas de pilares) não representa "
                "bem esse balanço — confira os pilares à flexão pelo modelo."
            )
    if not pilares:
        avisos.append("O esqueleto não tem barras em pé chegando no chão (pilares).")
    # Área de piso por nível: as chapas deitadas.
    area = None
    try:
        chapas, _ = cpm.chapas_do_piso(g, eixo_vertical)
    except (ArithmeticError, ValueError):  # pragma: no cover - chapa estragada
        chapas = []
    por_nivel = []
    for cota in cotas:
        soma = 0.0
        for chapa in chapas:
            if chapa.inclinacao_graus > PISO_DEITADO_GRAUS:
                continue
            z = vpb.para_a_planta(chapa.origem, eixo_vertical)[2] - terreno
            if abs(z - cota) <= NIVEL_DA_CHAPA_M:
                soma += chapa.area_m2
        por_nivel.append(soma)
    if por_nivel and all(a > 0 for a in por_nivel):
        area = max(por_nivel)
        if max(por_nivel) > 1.05 * min(por_nivel):
            avisos.append(
                "Os pisos têm áreas diferentes ("
                + "; ".join(f"{_n(a)} m²" for a in por_nivel)
                + "): a página usa uma área só por nível — ficou a maior."
            )
    elif cotas:
        avisos.append(
            "Sem chapas de piso deitadas nos níveis: a área de piso fica L_x × L_y (confira)."
        )
    # Diagonais.
    perfis = ld.perfis_do_esqueleto(g)
    descricoes = {c.nome: c.descricao for c in g.corpos}
    nos_pes = [pe for _, pe in pilares]
    diagonais: list[Diagonal] = []
    maos = 0
    alturas = [cotas[0], *(b - a for a, b in zip(cotas, cotas[1:], strict=False))] if cotas else []
    for b in barras:
        a, c = rel(b.inicio), rel(b.fim)
        baixo, alto = (a, c) if a[2] <= c[2] else (c, a)
        dz = alto[2] - baixo[2]
        horizontal = math.hypot(alto[0] - baixo[0], alto[1] - baixo[1])
        if horizontal <= 1e-6 or not cotas:
            continue
        angulo = math.degrees(math.atan2(dz, horizontal))
        if not INCLINACAO_DIAGONAL[0] <= angulo <= INCLINACAO_DIAGONAL[1]:
            continue
        ux, uy = (alto[0] - baixo[0]) / horizontal, (alto[1] - baixo[1]) / horizontal
        andar = _andar((baixo[2] + alto[2]) / 2.0, cotas)
        pe_do_andar = cotas[andar - 2] if andar >= 2 else 0.0
        altura = alturas[andar - 1]
        junto = any(
            math.hypot(baixo[0] - p[0], baixo[1] - p[1]) <= JUNTO_AO_PILAR_M for p in nos_pes
        )
        no_pe = abs(baixo[2] - pe_do_andar) <= NO_NIVEL_M
        if not (junto and no_pe and dz >= ALTURA_MINIMA * altura):
            if junto and dz < ALTURA_MINIMA * altura:
                maos += 1  # curta, saindo do pilar: mão-francesa
            continue
        if abs(ux) >= NO_PLANO:
            direcao, plano = "X", (baixo[1] + alto[1]) / 2.0
        elif abs(uy) >= NO_PLANO:
            direcao, plano = "Y", (baixo[0] + alto[0]) / 2.0
        else:
            avisos.append(
                f"{b.nome}: diagonal fora dos planos X e Y (em planta, a {_n(math.degrees(math.atan2(uy, ux)), 0)}° "
                "de X) — a página só conta linhas contraventadas em X ou em Y."
            )
            continue
        perfil = perfis.get(b.nome, ("", ""))[0] or descricoes.get(b.nome, "")
        diagonais.append(Diagonal(b.nome, baixo, alto, perfil, direcao, plano, andar))
    # Duas barras no mesmo lugar.
    unicas: list[Diagonal] = []
    for d in diagonais:
        igual = next(
            (
                u
                for u in unicas
                if math.dist(u.baixo, d.baixo) <= SOBREPOSTAS_M
                and math.dist(u.alto, d.alto) <= SOBREPOSTAS_M
            ),
            None,
        )
        if igual is not None:
            avisos.append(
                f"{igual.nome} e {d.nome} estão no mesmo lugar (pontas a menos de "
                f"{_n(100 * SOBREPOSTAS_M, 0)} cm): no Simulation, cada corpo é uma viga inteira "
                "— a diagonal conta duas vezes na rigidez e no peso. Se for um corpo partido, "
                "junte-os no SolidWorks; aqui conta uma só."
            )
            continue
        unicas.append(d)
    sistemas: dict[str, SistemaNoEsqueleto] = {}
    for direcao in ("X", "Y"):
        da_direcao = [d for d in unicas if d.direcao == direcao]
        if not da_direcao:
            continue
        planos = _agrupar([d.plano_m for d in da_direcao], MESMA_LINHA_M)
        tipos: list[str] = []
        paineis = 1
        for plano in planos:
            for andar in sorted({d.andar for d in da_direcao}):
                grupo = [
                    d
                    for d in da_direcao
                    if d.andar == andar and abs(d.plano_m - plano) <= MESMA_LINHA_M
                ]
                if not grupo:
                    continue
                tipo, n = _tipo_do_grupo(grupo, direcao)
                tipos.append(tipo)
                paineis = max(paineis, n)
        perfil = _mais_comum([d.perfil for d in da_direcao])
        familia = _familia(perfil)
        if not familia:
            avisos.append(
                f"Diagonais em {direcao} ({perfil or 'perfil desconhecido'}): não é cantoneira, "
                "tubo nem barra redonda do catálogo — "
                "a página não verifica esse perfil; escolha o equivalente e confira à parte."
            )
        sistemas[direcao] = SistemaNoEsqueleto(
            direcao=direcao,
            tipo=Counter(tipos).most_common(1)[0][0],
            linhas=len(planos),
            paineis_por_linha=paineis,
            perfil=perfil,
            familia=familia,
            diagonais=tuple(d.nome for d in da_direcao),
        )
    for direcao in ("X", "Y"):
        if direcao not in sistemas and pilares:
            avisos.append(
                f"Sem contraventamento em {direcao} no esqueleto"
                + (f" (só {maos} mão(s)-francesa(s))" if maos else "")
                + f": a estabilidade em {direcao} é de pórtico — engaste na base, ligação rígida "
                "ou mãos-francesas — e esta página não verifica isso. Verifique os pilares à "
                "flexão com o modelo (B₂ pelo modelo) e não use o resultado desta direção."
            )
    pilar = _mais_comum([perfis.get(b.nome, ("", ""))[0] for b, _ in pilares])
    vigas = [
        perfis.get(b.nome, ("", ""))[0]
        for b in barras
        if abs(b.fim[2] - b.inicio[2]) <= 0.05 * b.comprimento_m
        and any(abs(b.meio[2] - terreno - z) <= 0.15 for z in cotas)
    ]
    return EsqueletoDoContraventamento(
        lx_m=round(lx, 2),
        ly_m=round(ly, 2),
        vaos_x=vaos_x,
        vaos_y=vaos_y,
        cotas_m=tuple(cotas),
        area_de_piso_m2=round(area, 2) if area else None,
        pilar=pilar,
        viga=_mais_comum(vigas),
        sistemas=sistemas,
        pilares=tuple(b.nome for b, _ in pilares),
        linhas_de_pilares=(len(xs), len(ys)),
        maos_francesas=maos,
        avisos=tuple(dict.fromkeys(avisos)),
    )


def _tipo_do_grupo(grupo: Sequence[Diagonal], direcao: str) -> tuple[str, int]:
    """O tipo e os painéis das diagonais de um plano e andar."""
    k = 0 if direcao == "X" else 1

    def subida(d: Diagonal) -> float:
        return math.copysign(1.0, d.alto[k] - d.baixo[k])

    def faixa(d: Diagonal) -> tuple[float, float]:
        return (min(d.baixo[k], d.alto[k]), max(d.baixo[k], d.alto[k]))

    usadas: set[int] = set()
    x = v = 0
    for i, a in enumerate(grupo):
        for j in range(i + 1, len(grupo)):
            b = grupo[j]
            if i in usadas or j in usadas or subida(a) == subida(b):
                continue
            fa, fb = faixa(a), faixa(b)
            sobreposicao = min(fa[1], fb[1]) - max(fa[0], fb[0])
            if math.dist(a.alto, b.alto) <= ENCONTRO_M:
                v += 1
                usadas |= {i, j}
            elif sobreposicao >= 0.5 * min(fa[1] - fa[0], fb[1] - fb[0]):
                x += 1
                usadas |= {i, j}
    sozinhas = len(grupo) - len(usadas)
    if x and not v:
        return cp.TIPO_X_TRACAO, x + sozinhas
    if v and not x:
        return cp.TIPO_V_INVERTIDO, v + sozinhas
    if not x and not v:
        return cp.TIPO_DIAGONAL_SIMPLES, sozinhas
    return cp.TIPO_X_TRACAO, x + v + sozinhas


def conferir_com_a_pagina(
    esq: EsqueletoDoContraventamento, e: cp.EntradaContraventamento
) -> list[str]:
    """O que a página tem diferente do esqueleto (para o aviso)."""
    diferencas = []

    def longe(a: float, b: float) -> bool:
        return abs(a - b) > max(0.10, 0.05 * max(abs(a), abs(b)))

    if longe(e.comprimento_x_m, esq.lx_m) or longe(e.largura_y_m, esq.ly_m):
        diferencas.append(
            f"L_x × L_y {_n(e.comprimento_x_m)} × {_n(e.largura_y_m)} m (esqueleto: "
            f"{_n(esq.lx_m)} × {_n(esq.ly_m)} m)"
        )
    if (e.vaos_x, e.vaos_y) != (esq.vaos_x, esq.vaos_y):
        diferencas.append(f"vãos {e.vaos_x} × {e.vaos_y} (esqueleto: {esq.vaos_x} × {esq.vaos_y})")
    if esq.cotas_m and not cvb.cotas_batem(esq.cotas_m, e.cotas_m):
        diferencas.append(
            "cotas "
            + "; ".join(_n(z) for z in e.cotas_m)
            + " m (esqueleto: "
            + "; ".join(_n(z) for z in esq.cotas_m)
            + " m)"
        )
    for direcao in cp.DIRECOES:
        s = esq.sistema(direcao)
        if s is None:
            continue
        pagina = e.sistema(direcao)
        if (pagina.tipo, pagina.linhas, pagina.paineis_por_linha) != (
            s.tipo,
            s.linhas,
            s.paineis_por_linha,
        ):
            diferencas.append(
                f"contraventamento em {direcao} ({cp.TIPOS[s.tipo].split(' (')[0]}, {s.linhas} "
                f"linha(s) × {s.paineis_por_linha} painel(éis) no esqueleto)"
            )
    return diferencas
