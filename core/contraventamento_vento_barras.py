"""Vento viga a viga, pilar a pilar, no contraventamento de estruturas abertas.

A página Contraventamento de estruturas abertas pode tirar o vento do esqueleto do modelo em vez
dos pórticos regulares: cada barra recebe o vento dela (:mod:`core.vento_por_barras` — sombra,
φ/C_a e η por plano, NBR 6123:2023, 8.3 e 8.4) e a força vai aos pisos pelas mesmas faixas de
influência da grade (:mod:`core.vento_estrutura_aberta`): meia altura do andar de baixo e do de
cima; a metade de baixo do primeiro andar vai direto à fundação; acima da faixa do último piso,
tudo vai para ele.

* **Barra**: a carga é uniforme ao longo dela, então a força se divide pelas faixas na proporção da
  altura que a barra tem em cada uma; barra deitada vai inteira para a faixa da cota dela.
* **Guarda-corpo, escada, painel e equipamento**: a força vai para a faixa da cota do centro.
* Cada **direção** calculada é uma ação de vento. As perpendiculares carregam uma direção do
  contraventamento; as diagonais (45°…), as duas ao mesmo tempo. W0 e W180 podem ter valores
  diferentes (o plano de barlavento muda), por isso cada sentido entra com o seu.
* **Excentricidade**: a resultante do vento perpendicular passa onde a estrutura a põe (medida do
  centro da planta dos pisos); a excentricidade informada na página (NBR 6123, 6.1.4: vento
  oblíquo e vizinhança) soma-se a essa.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from core import leitura_do_modelo as ld
from core import vento_estrutura_aberta as va
from core import vento_por_barras as vpb

#: Vigas deitadas a menos disso uma da outra (na vertical) formam o mesmo nível do esqueleto.
TOLERANCIA_DO_NIVEL_M = 0.15
#: Um nível do esqueleto precisa de pelo menos esta fração do comprimento de vigas do maior.
FRACAO_MINIMA_DO_NIVEL = 0.25
NIVEL_MINIMO_M = 0.50  # acima do terreno (vigas de baldrame ficam de fora)
SEN_DEITADA = math.sin(math.radians(3.0))
#: Cota informada e nível do esqueleto "batem" até esta diferença.
DIFERENCA_DE_COTA_M = 0.15
#: Medida em planta informada e a do esqueleto "batem" até a maior destas duas diferenças.
DIFERENCA_DE_PLANTA_M = 0.30
DIFERENCA_DE_PLANTA_RELATIVA = 0.10
EXCENTRICIDADE_MAXIMA = 0.5
DIRECOES = ("X", "Y")


class VentoDoEsqueletoInvalido(ValueError):
    """Dado que o cálculo não aceita; a mensagem diz o que corrigir."""


def _n(valor: float, casas: int = 2) -> str:
    if round(valor, casas) == 0:
        valor = 0.0
    return f"{valor:.{casas}f}".replace(".", ",")


def _cotas(cotas: Sequence[float]) -> str:
    return "; ".join(_n(z) for z in cotas)


# ---------------------------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CasoNosNiveis:
    """Uma direção do vento levada aos pisos: força em X e em Y em cada nível (kN)."""

    angulo: int
    perpendicular: bool
    fx_kN: tuple[float, ...]
    fy_kN: tuple[float, ...]
    fx_base_kN: float  # faixa da base: direto à fundação
    fy_base_kN: float
    torcao_kNm: float  # em torno do eixo vertical pelo centro de :mod:`core.vento_por_barras`

    @property
    def codigo(self) -> str:
        return f"W{self.angulo}"

    @property
    def rotulo(self) -> str:
        return f"W{self.angulo} ({vpb.SENTIDOS.get(self.angulo, '')})"

    def forcas_kN(self, direcao: str) -> tuple[float, ...]:
        return self.fx_kN if direcao == "X" else self.fy_kN

    def base_kN(self, direcao: str) -> float:
        return self.fx_base_kN if direcao == "X" else self.fy_base_kN

    def cortantes_kN(self, direcao: str) -> tuple[float, ...]:
        """Cortante do andar i (entre o nível i − 1 e o nível i): as forças de i para cima."""
        forcas = self.forcas_kN(direcao)
        return tuple(sum(forcas[i:]) for i in range(len(forcas)))

    def total_kN(self, direcao: str) -> float:
        return sum(self.forcas_kN(direcao)) + self.base_kN(direcao)


@dataclass(frozen=True)
class VentoDoEsqueleto:
    """O vento barra a barra do esqueleto, nos pisos do contraventamento."""

    resultado: vpb.ResultadoPorBarras
    cotas_m: tuple[float, ...]  # dos pisos, a partir do terreno
    casos: tuple[CasoNosNiveis, ...]
    niveis_do_esqueleto_m: tuple[float, ...]  # cotas das vigas deitadas (a partir do terreno)
    planta_m: tuple[float, float]  # medidas X × Y da planta dos pisos do esqueleto
    centro_m: tuple[float, float]  # centro da planta dos pisos (eixos da planta)
    #: Distância da resultante do vento perpendicular ao centro da planta dos pisos, como fração
    #: da dimensão perpendicular à força ("X": vento em X, medida em Y).
    excentricidade_real: Mapping[str, float] = field(default_factory=dict)
    eixo_vertical: str = "Y"
    arquivo: str = ""
    avisos: tuple[str, ...] = ()

    def caso(self, angulo: int) -> CasoNosNiveis | None:
        return next((c for c in self.casos if c.angulo == angulo), None)

    def maior_total_kN(self, direcao: str) -> float:
        """A maior força total do vento na direção, entre todos os casos (módulo)."""
        return max((abs(c.total_kN(direcao)) for c in self.casos), default=0.0)

    def maior_cortante_kN(self, direcao: str, andar: int) -> float:
        return max((abs(c.cortantes_kN(direcao)[andar - 1]) for c in self.casos), default=0.0)


# ---------------------------------------------------------------------------------------------
# Faixas de influência
# ---------------------------------------------------------------------------------------------
def faixas(cotas_m: Sequence[float]) -> tuple[tuple[float, float], ...]:
    """A faixa de cada nível: da meia altura do andar de baixo à do de cima (a última vai até o
    infinito: o que fica acima do último piso vai para ele)."""
    resultado = []
    for i, z in enumerate(cotas_m):
        baixo = (cotas_m[i - 1] + z) / 2.0 if i > 0 else z / 2.0
        alto = (z + cotas_m[i + 1]) / 2.0 if i + 1 < len(cotas_m) else math.inf
        resultado.append((baixo, alto))
    return tuple(resultado)


def _faixa_do_ponto(z: float, f: Sequence[tuple[float, float]]) -> int | None:
    """Índice da faixa da cota ``z``; ``None`` na faixa da base."""
    if z < f[0][0]:
        return None
    for i, (baixo, alto) in enumerate(f):
        if baixo <= z < alto:
            return i
    return len(f) - 1


def reparte(z_a: float, z_b: float, f: Sequence[tuple[float, float]]) -> tuple[float, list[float]]:
    """Frações de uma carga uniforme entre as cotas ``z_a`` e ``z_b``: (base, [cada nível])."""
    baixo, alto = min(z_a, z_b), max(z_a, z_b)
    niveis = [0.0] * len(f)
    if alto - baixo < 1e-6:
        i = _faixa_do_ponto((baixo + alto) / 2.0, f)
        if i is None:
            return 1.0, niveis
        niveis[i] = 1.0
        return 0.0, niveis
    altura = alto - baixo
    base = max(0.0, min(alto, f[0][0]) - baixo) / altura
    for i, (fb, fa) in enumerate(f):
        niveis[i] = max(0.0, min(alto, fa) - max(baixo, fb)) / altura
    return base, niveis


# ---------------------------------------------------------------------------------------------
# A planta dos pisos e os níveis do esqueleto
# ---------------------------------------------------------------------------------------------
def _deitada(b: vpb.BarraAoVento) -> bool:
    return abs(b.fim[2] - b.inicio[2]) <= SEN_DEITADA * b.comprimento_m


def niveis_do_esqueleto(barras: Sequence[vpb.BarraAoVento], terreno: float) -> tuple[float, ...]:
    """As cotas (a partir do terreno) onde o esqueleto tem vigas deitadas de verdade: grupos de
    vigas a menos de 15 cm um do outro, com pelo menos 25 % do comprimento do maior grupo."""
    deitadas = sorted(
        ((b.meio[2] - terreno, b.comprimento_m) for b in barras if _deitada(b)),
        key=lambda x: x[0],
    )
    grupos: list[list[tuple[float, float]]] = []
    for z, comprimento in deitadas:
        if grupos and z - grupos[-1][-1][0] <= TOLERANCIA_DO_NIVEL_M:
            grupos[-1].append((z, comprimento))
        else:
            grupos.append([(z, comprimento)])
    pesos = [sum(c for _, c in g) for g in grupos]
    if not pesos:
        return ()
    maior = max(pesos)
    niveis = []
    for g, peso in zip(grupos, pesos, strict=True):
        cota = sum(z * c for z, c in g) / peso
        if cota >= NIVEL_MINIMO_M and peso >= FRACAO_MINIMA_DO_NIVEL * maior:
            niveis.append(round(cota, 2))
    return tuple(niveis)


def _planta_dos_pisos(
    barras: Sequence[vpb.BarraAoVento], terreno: float, cotas: Sequence[float]
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Medidas (X, Y) e centro da planta das vigas deitadas nos pisos (ou em qualquer nível do
    esqueleto, se nenhuma cai nas cotas informadas)."""

    def nas(cotas_alvo: Sequence[float]) -> list[vpb.BarraAoVento]:
        return [
            b
            for b in barras
            if _deitada(b)
            and any(abs(b.meio[2] - terreno - z) <= TOLERANCIA_DO_NIVEL_M for z in cotas_alvo)
        ]

    escolhidas = nas(cotas) or nas(niveis_do_esqueleto(barras, terreno))
    if not escolhidas:
        return None
    xs = [p[0] for b in escolhidas for p in (b.inicio, b.fim)]
    ys = [p[1] for b in escolhidas for p in (b.inicio, b.fim)]
    return (max(xs) - min(xs), max(ys) - min(ys)), (
        (max(xs) + min(xs)) / 2,
        (max(ys) + min(ys)) / 2,
    )


# ---------------------------------------------------------------------------------------------
# Entrada do cálculo barra a barra
# ---------------------------------------------------------------------------------------------
def _equipamento(
    eq: va.Equipamento, centro: tuple[float, float], terreno: float, cotas: Sequence[float]
) -> vpb.ElementoAoVento:
    nivel = min(max(eq.nivel, 1), len(cotas))
    cilindro = eq.forma == va.FORMA_CILINDRO
    return vpb.ElementoAoVento(
        nome=eq.nome,
        tipo=vpb.TIPO_CILINDRO if cilindro else vpb.TIPO_CAIXA,
        ponto_1=(centro[0], centro[1], terreno + cotas[nivel - 1]),
        altura_m=eq.altura_m,
        largura_x_m=eq.dimensao_x_m,
        largura_y_m=eq.dimensao_x_m if cilindro else eq.dimensao_y_m,
        ca=eq.ca,
    )


def entrada_pelo_esqueleto(
    g: ld.GeometriaDoModelo,
    eixo_vertical: str,
    parametros: va.ParametrosVento,
    *,
    cotas_m: Sequence[float],
    equipamentos: Sequence[va.Equipamento] = (),
    guarda_corpos: Sequence[vpb.ElementoAoVento] = (),
    direcoes: tuple[int, ...] = vpb.DIRECOES_COM_DIAGONAIS,
    protecao: bool = True,
    cota_do_terreno_m: float | None = None,
    nomes_no_simulation: Mapping[str, str] | None = None,
) -> vpb.EntradaPorBarras:
    """As barras do esqueleto, os guarda-corpos das bordas e os equipamentos da página (no centro
    da planta dos pisos, apoiados no piso do nível deles) para o cálculo barra a barra."""
    barras = vpb.barras_do_esqueleto(g, eixo_vertical, nomes_no_simulation)
    if not barras:
        raise VentoDoEsqueletoInvalido(
            "O esqueleto do modelo não tem barras (só chapas): rode a macro de novo na peça com "
            "os membros estruturais."
        )
    terreno = (
        min(min(b.inicio[2], b.fim[2]) for b in barras)
        if cota_do_terreno_m is None
        else float(cota_do_terreno_m)
    )
    planta = _planta_dos_pisos(barras, terreno, cotas_m)
    if planta is None:
        xs = [p[0] for b in barras for p in (b.inicio, b.fim)]
        ys = [p[1] for b in barras for p in (b.inicio, b.fim)]
        centro = ((max(xs) + min(xs)) / 2.0, (max(ys) + min(ys)) / 2.0)
    else:
        centro = planta[1]
    nomes = {b.nome for b in barras}
    # Guarda-corpo de uma viga que não está entre as barras: o programa acha a viga que apoia.
    elementos = [
        *(
            replace(el, barra="") if el.barra and el.barra not in nomes else el
            for el in guarda_corpos
        ),
        *(_equipamento(eq, centro, terreno, cotas_m) for eq in equipamentos),
    ]
    return vpb.EntradaPorBarras(
        barras=tuple(barras),
        parametros=parametros,
        elementos=tuple(elementos),
        direcoes=tuple(direcoes),
        cota_do_terreno_m=cota_do_terreno_m,
        protecao=protecao,
    )


# ---------------------------------------------------------------------------------------------
# Do resultado barra a barra aos pisos
# ---------------------------------------------------------------------------------------------
def _validar_cotas(cotas_m: Sequence[float]) -> None:
    if not cotas_m:
        raise VentoDoEsqueletoInvalido("Informe ao menos a cota de um piso.")
    if not all(math.isfinite(z) and z > 0 for z in cotas_m):
        raise VentoDoEsqueletoInvalido("As cotas dos pisos precisam ser maiores que zero.")
    if any(b <= a for a, b in zip(cotas_m, cotas_m[1:], strict=False)):
        raise VentoDoEsqueletoInvalido("As cotas dos pisos precisam crescer de baixo para cima.")


def vento_nos_niveis(
    r: vpb.ResultadoPorBarras,
    cotas_m: Sequence[float],
    *,
    eixo_vertical: str = "Y",
    arquivo: str = "",
) -> VentoDoEsqueleto:
    """Cada direção do resultado barra a barra levada aos pisos das ``cotas_m`` (do terreno)."""
    cotas = tuple(float(z) for z in cotas_m)
    _validar_cotas(cotas)
    f = faixas(cotas)
    terreno = r.cota_do_terreno_m
    por_nome = {b.nome: b for b in r.entrada.barras}
    casos: list[CasoNosNiveis] = []
    for d in r.direcoes:
        fx = [0.0] * len(cotas)
        fy = [0.0] * len(cotas)
        base_x = base_y = 0.0
        for na_barra in d.barras:
            b = por_nome.get(na_barra.barra)
            if b is None:  # pragma: no cover - o resultado vem das mesmas barras
                continue
            total_x = na_barra.fx_kN_m * na_barra.comprimento_m
            total_y = na_barra.fy_kN_m * na_barra.comprimento_m
            base, fracoes = reparte(b.inicio[2] - terreno, b.fim[2] - terreno, f)
            base_x += total_x * base
            base_y += total_y * base
            for i, fracao in enumerate(fracoes):
                fx[i] += total_x * fracao
                fy[i] += total_y * fracao
        for el in d.elementos:
            faixa = _faixa_do_ponto(el.ponto[2] - terreno, f)
            if faixa is None:
                base_x += el.fx_kN
                base_y += el.fy_kN
            else:
                fx[faixa] += el.fx_kN
                fy[faixa] += el.fy_kN
        casos.append(
            CasoNosNiveis(
                angulo=d.angulo,
                perpendicular=d.perpendicular,
                fx_kN=tuple(fx),
                fy_kN=tuple(fy),
                fx_base_kN=base_x,
                fy_base_kN=base_y,
                torcao_kNm=d.torcao_kNm,
            )
        )
    barras = r.entrada.barras
    niveis = niveis_do_esqueleto(barras, terreno)
    planta = _planta_dos_pisos(barras, terreno, cotas)
    if planta is None:
        xs = [p[0] for b in barras for p in (b.inicio, b.fim)]
        ys = [p[1] for b in barras for p in (b.inicio, b.fim)]
        medidas = (max(xs) - min(xs), max(ys) - min(ys))
        centro = r.centro_m
    else:
        medidas, centro = planta
    excentricidade: dict[str, float] = {}
    for d in r.direcoes:
        if not d.perpendicular:
            continue
        direcao = "X" if d.angulo in (0, 180) else "Y"
        forca = d.fx_kN if direcao == "X" else d.fy_kN
        if abs(forca) <= 1e-9:
            continue
        # Momento em torno do centro de vpb: T = (x − cx)·F_y − (y − cy)·F_x.
        if direcao == "X":
            posicao = r.centro_m[1] - d.torcao_kNm / forca
            dimensao, meio = medidas[1], centro[1]
        else:
            posicao = r.centro_m[0] + d.torcao_kNm / forca
            dimensao, meio = medidas[0], centro[0]
        if dimensao <= 0:
            continue
        excentricidade[direcao] = max(
            excentricidade.get(direcao, 0.0), abs(posicao - meio) / dimensao
        )
    avisos = list(r.avisos)
    avisos.extend(_avisos_dos_niveis(niveis, cotas))
    return VentoDoEsqueleto(
        resultado=r,
        cotas_m=cotas,
        casos=tuple(casos),
        niveis_do_esqueleto_m=niveis,
        planta_m=medidas,
        centro_m=centro,
        excentricidade_real=excentricidade,
        eixo_vertical=eixo_vertical,
        arquivo=arquivo,
        avisos=tuple(dict.fromkeys(avisos)),
    )


def cotas_batem(niveis: Sequence[float], cotas: Sequence[float]) -> bool:
    """Os níveis de vigas do esqueleto são os pisos informados (até 15 cm de diferença)?"""
    return len(niveis) == len(cotas) and all(
        abs(a - b) <= DIFERENCA_DE_COTA_M for a, b in zip(niveis, cotas, strict=True)
    )


def _avisos_dos_niveis(niveis: Sequence[float], cotas: Sequence[float]) -> list[str]:
    if not niveis:
        return [
            "O esqueleto não tem vigas deitadas para conferir as cotas dos pisos: as forças vão "
            "aos pisos pelas cotas informadas."
        ]
    if cotas_batem(niveis, cotas):
        return []
    return [
        f"As vigas do esqueleto estão nas cotas {_cotas(niveis)} m (a partir do terreno) e os "
        f"pisos informados nas cotas {_cotas(cotas)} m: o vento vai aos pisos pelas cotas "
        "informadas, e o cortante de cada andar depende delas — confira (ou use as do esqueleto "
        "nos ajustes da geometria)."
    ]


def avisos_da_planta(ve: VentoDoEsqueleto, lx_m: float, ly_m: float) -> list[str]:
    """A planta da página (peso por área, painéis) contra a do esqueleto (vento)."""
    px, py = ve.planta_m

    def perto(a: float, b: float) -> bool:
        return abs(a - b) <= max(DIFERENCA_DE_PLANTA_M, DIFERENCA_DE_PLANTA_RELATIVA * max(a, b))

    if perto(px, lx_m) and perto(py, ly_m):
        return []
    if perto(px, ly_m) and perto(py, lx_m):
        return [
            f"A planta dos pisos do esqueleto tem {_n(px)} m em X e {_n(py)} m em Y; a página tem "
            f"L_x = {_n(lx_m)} m e L_y = {_n(ly_m)} m — parecem trocadas. As direções X e Y do "
            "contraventamento são as da planta do modelo: troque L_x e L_y (e os vãos)."
        ]
    return [
        f"A planta dos pisos do esqueleto ({_n(px)} × {_n(py)} m, X × Y) não bate com L_x × L_y "
        f"da página ({_n(lx_m)} × {_n(ly_m)} m): o peso por área e os painéis usam as medidas da "
        "página e o vento usa o esqueleto — confira."
    ]


# ---------------------------------------------------------------------------------------------
# Tabelas
# ---------------------------------------------------------------------------------------------
def linhas_dos_niveis(ve: VentoDoEsqueleto) -> list[list[str]]:
    """Uma linha por caso e nível: força em X, em Y e os cortantes do andar."""
    linhas = []
    for c in ve.casos:
        cx, cy = c.cortantes_kN("X"), c.cortantes_kN("Y")
        for i, z in enumerate(ve.cotas_m):
            linhas.append(
                [
                    c.codigo,
                    str(i + 1),
                    _n(z),
                    _n(c.fx_kN[i]),
                    _n(c.fy_kN[i]),
                    _n(cx[i]),
                    _n(cy[i]),
                ]
            )
        linhas.append([c.codigo, "base", "—", _n(c.fx_base_kN), _n(c.fy_base_kN), "—", "—"])
    return linhas


def linhas_dos_planos(ve: VentoDoEsqueleto) -> list[list[str]]:
    linhas = []
    for d in ve.resultado.direcoes:
        for p in d.planos:
            linhas.append(
                [
                    d.codigo,
                    p.nome,
                    str(len(p.barras)),
                    _n(p.area_m2),
                    _n(p.contorno_m2),
                    _n(p.phi, 3),
                    _n(p.ca),
                    _n(p.eta, 3),
                ]
            )
    return linhas
