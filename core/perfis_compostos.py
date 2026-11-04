"""Barras compostas de dois perfis iguais: a seção, os espaçadores e a força de flambagem N_e,m.

Quatro arranjos, todos de dois perfis iguais ligados a intervalos, em contato ou com o afastamento
de uma chapa espaçadora (NBR 8800:2025 5.3.6.2):

* **2 cantoneiras em T** (costas com costas): seção **monossimétrica**, com y como eixo de
  simetria. A flambagem em torno de y se acopla à torção (flexo-torção, 5.3.5.2): ``N_ey`` entra na
  fórmula de ``N_eyz`` já com a redução das ligações;
* **2 cantoneiras em cruz** (opostas pelo canto): os eixos x e y são os principais, a x passando
  pelos centros das duas cantoneiras, e por isso aparecem a cerca de 45° das abas;
* **2 perfis U costas com costas** (forma de I) e **2 perfis U com as mesas de frente** (caixa).

Em todos, a flambagem **em torno de y** é a que faz um perfil escorregar em relação ao outro: só ela
carrega as ligações e sofre a redução. A flambagem em torno de x não produz cortante entre os
perfis. Por isso o programa desenha sempre y passando entre eles.

Regras (``ℓ`` = distância entre as ligações, ``r_mín`` = menor raio de giração de um perfil):

=================  ===========================  ===============================================
Norma              Limite de ``ℓ/r_mín``        Força de flambagem
=================  ===========================  ===============================================
NBR 8800:2008      1/2 da esbeltez (5.3.4.2)    sem redução
NBR 8800:2025      3/4 da esbeltez (5.3.6.1)    ``N_e,m`` (5.3.6.3)
AISC 360-16        3/4 da esbeltez (E6.2)       ``(L_c/r)_m`` (E6.1), a mesma redução
=================  ===========================  ===============================================

Nas três, pelo menos duas ligações ao longo do comprimento, igualmente espaçadas. Na 2025 e no AISC,
as ligações **das pontas** têm de ser soldadas ou com parafusos protendidos (Classe A ou B).

``N_e,m = N_e,o·(L/r)₀²/[(L/r)₀² + (ℓ/r_mín)²]`` com parafusos de aperto normal nos espaçadores; com
solda ou parafusos protendidos, ``N_e,m = N_e,o`` até ``ℓ/r_mín = 40`` e, acima,
``N_e,o·(L/r)₀²/[(L/r)₀² + (K_i·ℓ/r_mín)²]``, com ``K_i`` = 0,50 (cantoneiras em T), 0,75 (U em
forma de I) e 0,86 (os outros). Onde cada item foi conferido: docs/flambagem_de_colunas.md.

Simplificações, todas a favor da segurança: cantoneiras sem os raios de concordância (bate com as
tabelas do AISC, ver os testes); torção com cada perfil trabalhando sozinho (``J`` e ``C_w`` somados,
sem contar com o conjunto); abas e mesas sempre como elementos livres entre as ligações (grupo 3 nas
cantoneiras, "providas de chapas espaçadoras").

Unidades: mm, mm², mm⁴, mm⁶.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from core.column_design import Secao

Ponto = tuple[float, float]

TIPO = "composta"  # Secao.tipo das barras compostas

ARRANJO_2L_T = "2 cantoneiras em T (costas com costas)"
ARRANJO_2L_CRUZ = "2 cantoneiras em cruz (opostas pelo canto)"
ARRANJO_2U_I = "2 perfis U costas com costas (forma de I)"
ARRANJO_2U_CAIXA = "2 perfis U com as mesas de frente (caixa)"
ARRANJOS = (ARRANJO_2L_T, ARRANJO_2L_CRUZ, ARRANJO_2U_I, ARRANJO_2U_CAIXA)
ARRANJOS_DE_CANTONEIRA = (ARRANJO_2L_T, ARRANJO_2L_CRUZ)

#: 5.3.6.3: K_i de cada arranjo; 0,86 é o valor de "todos os outros casos".
K_I = {ARRANJO_2L_T: 0.50, ARRANJO_2L_CRUZ: 0.86, ARRANJO_2U_I: 0.75, ARRANJO_2U_CAIXA: 0.86}
_SUFIXO = {
    ARRANJO_2L_T: "em T",
    ARRANJO_2L_CRUZ: "em cruz",
    ARRANJO_2U_I: "costas com costas",
    ARRANJO_2U_CAIXA: "em caixa",
}

LIGACAO_APERTO_NORMAL = "Parafusos com aperto normal"
LIGACAO_RIGIDA = "Solda ou parafusos protendidos (Classe A ou B)"
#: O aperto normal vem primeiro: é o caso mais comum nos espaçadores e o de menor resistência.
LIGACOES = (LIGACAO_APERTO_NORMAL, LIGACAO_RIGIDA)

ESPACADORES_MINIMOS = 2
#: Barra composta tracionada: limite de ℓ/r_mín de um perfil, recomendação de 5.2.8.2.
ESBELTEZ_DA_PECA_TRACIONADA = 300.0
#: Até aqui, com solda ou parafusos protendidos, as ligações não reduzem a força de flambagem.
ESBELTEZ_SEM_REDUCAO = 40.0

FRACAO_DO_LIMITE = {"NBR8800_2008": 0.5, "NBR8800_2024": 0.75, "AISC360_16_LRFD": 0.75}
TEXTO_DA_FRACAO = {"NBR8800_2008": "1/2", "NBR8800_2024": "3/4", "AISC360_16_LRFD": "3/4"}
REFERENCIA_DO_LIMITE = {
    "NBR8800_2008": "NBR 8800:2008 5.3.4.2",
    "NBR8800_2024": "ABNT NBR 8800:2025 5.3.6.1",
    "AISC360_16_LRFD": "AISC 360-16 E6.2",
}
REFERENCIA_DA_REDUCAO = {
    "NBR8800_2008": "NBR 8800:2008 5.3.4.2",
    "NBR8800_2024": "ABNT NBR 8800:2025 5.3.6.3",
    "AISC360_16_LRFD": "AISC 360-16 E6.1",
}
REFERENCIA_DAS_PONTAS = {
    "NBR8800_2024": "ABNT NBR 8800:2025 5.3.6.2",
    "AISC360_16_LRFD": "AISC 360-16 E6.1",
}


def _positivo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor <= 0:
        raise ValueError(f"{nome} deve ser um número finito maior que zero.")
    return valor


def _afastamento(s: float) -> float:
    s = float(s)
    if not math.isfinite(s) or s < 0:
        raise ValueError("O afastamento s entre os perfis não pode ser negativo.")
    return s


# ---------------------------------------------------------------------------------------------
# A cantoneira de cada perfil
# ---------------------------------------------------------------------------------------------
def _propriedades(
    retangulos: Sequence[tuple[float, float, float, float]],
) -> tuple[float, float, float, float, float, float]:
    """(A, x_G, y_G, I_x, I_y, I_xy) de retângulos (x0, y0, x1, y1), com I pelo centro geométrico."""
    area = sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in retangulos)
    cx = sum((x1 - x0) * (y1 - y0) * (x0 + x1) / 2 for x0, y0, x1, y1 in retangulos) / area
    cy = sum((x1 - x0) * (y1 - y0) * (y0 + y1) / 2 for x0, y0, x1, y1 in retangulos) / area
    ix = iy = ixy = 0.0
    for x0, y0, x1, y1 in retangulos:
        b, h = x1 - x0, y1 - y0
        dx, dy = (x0 + x1) / 2 - cx, (y0 + y1) / 2 - cy
        ix += b * h**3 / 12 + b * h * dy**2
        iy += h * b**3 / 12 + b * h * dx**2
        ixy += b * h * dx * dy
    return area, cx, cy, ix, iy, ixy


@dataclass(frozen=True)
class Cantoneira:
    """Cantoneira de abas ``a`` e ``b`` (podem ser desiguais) e espessura ``t``, sem os raios.

    Com o canto de fora na origem, ``a`` sobe por y e ``b`` corre por x; ``x_b`` e ``y_b`` são a
    distância do canto ao centro geométrico. ``a`` é a aba das costas no arranjo em T.
    """

    nome: str
    a_mm: float
    b_mm: float
    t_mm: float
    area_mm2: float
    x_b_mm: float
    y_b_mm: float
    i_x_mm4: float
    i_y_mm4: float
    i_xy_mm4: float
    j_mm4: float

    @property
    def i_min_mm4(self) -> float:
        media = (self.i_x_mm4 + self.i_y_mm4) / 2
        return media - math.hypot((self.i_x_mm4 - self.i_y_mm4) / 2, self.i_xy_mm4)

    @property
    def r_min_mm(self) -> float:
        return math.sqrt(self.i_min_mm4 / self.area_mm2)

    @property
    def contorno(self) -> tuple[Ponto, ...]:
        a, b, t = self.a_mm, self.b_mm, self.t_mm
        return ((0.0, 0.0), (b, 0.0), (b, t), (t, t), (t, a), (0.0, a))


def cantoneira(a_mm: float, b_mm: float, t_mm: float, nome: str = "") -> Cantoneira:
    """Uma cantoneira a partir das medidas, recusando espessura maior que a aba."""
    a = _positivo("A aba a", a_mm)
    b = _positivo("A aba b", b_mm)
    t = _positivo("A espessura t", t_mm)
    if t >= min(a, b):
        raise ValueError("A espessura t da cantoneira deve ser menor que as duas abas.")
    area, cx, cy, ix, iy, ixy = _propriedades(((0.0, 0.0, t, a), (t, 0.0, b, t)))
    return Cantoneira(
        nome or f"L {a:g}×{b:g}×{t:g}",
        a,
        b,
        t,
        area,
        cx,
        cy,
        ix,
        iy,
        ixy,
        t**3 * (a + b - t) / 3,
    )


def _paredes_das_abas(a: float, b: float, t: float) -> list[dict[str, Any]]:
    """Abas com chapas espaçadoras: grupo 3 da Tabela 4 (F.1 na NBR 2008), elementos livres."""
    if a == b:
        return [dict(tipo="AL", grupo=3, b=a, t=t, n=4)]
    return [dict(tipo="AL", grupo=3, b=a, t=t, n=2), dict(tipo="AL", grupo=3, b=b, t=t, n=2)]


def _secao(
    nome: str,
    arranjo: str,
    area: float,
    ix: float,
    iy: float,
    j: float,
    cw: float,
    y0: float,
    contornos: tuple[tuple[Ponto, ...], ...],
    elementos: list[dict[str, Any]],
    *,
    r_min: float,
    s: float,
    categoria_anglo: str,
    t_min: float,
    medidas: dict[str, float],
) -> Secao:
    pontos = [p for contorno in contornos for p in contorno]
    return Secao(
        nome,
        area,
        ix,
        iy,
        J=j,
        Cw=cw,
        y0=y0,
        Wx=ix / max(abs(p[1]) for p in pontos),
        Wy=iy / max(abs(p[0]) for p in pontos),
        tipo=TIPO,
        elementos=elementos,
        dims=dict(
            arranjo=arranjo,
            contornos=contornos,
            r_min=r_min,
            k_i=K_I[arranjo],
            s=s,
            categoria_anglo=categoria_anglo,
            t_min=t_min,
            **medidas,
        ),
    )


def duas_cantoneiras(peca: Cantoneira, arranjo: str, s_mm: float = 0.0) -> Secao:
    """A seção de duas cantoneiras iguais em T ou em cruz, com ``s_mm`` entre elas."""
    if arranjo not in ARRANJOS_DE_CANTONEIRA:
        raise ValueError(f"Arranjo de cantoneiras desconhecido: {arranjo!r}.")
    s = _afastamento(s_mm)
    a, b, t = peca.a_mm, peca.b_mm, peca.t_mm
    area1, xb, yb = peca.area_mm2, peca.x_b_mm, peca.y_b_mm
    nome = f"2 × {peca.nome} {_SUFIXO[arranjo]}, s = {s:g} mm"
    medidas = dict(a=a, b=b, t=t)
    comuns: dict[str, Any] = dict(
        r_min=peca.r_min_mm, s=s, categoria_anglo="cantoneira", t_min=t, medidas=medidas
    )
    paredes = _paredes_das_abas(a, b, t)
    if arranjo == ARRANJO_2L_T:
        # Abas b em cima (como o T do catálogo) e abas a descendo, de costas uma para a outra. O
        # centro de cisalhamento fica no encontro das linhas médias das abas e o C_w é desprezível.
        direita = tuple((s / 2 + x, yb - y) for x, y in peca.contorno)
        esquerda = tuple((-px, py) for px, py in direita)
        return _secao(
            nome,
            arranjo,
            2 * area1,
            2 * peca.i_x_mm4,
            2 * (peca.i_y_mm4 + area1 * (xb + s / 2) ** 2),
            2 * peca.j_mm4,
            0.0,
            yb - t / 2,
            (esquerda, direita),
            paredes,
            **comuns,
        )
    # Em cruz: uma cantoneira de cada lado da chapa, com a seção simétrica em relação a G. Os eixos
    # paralelos às abas não são principais: gira-se até o principal mais próximo da reta entre os
    # centros das cantoneiras, que vira x. Assim a flexão em y é a que carrega as ligações.
    centro = (s / 2 + xb, yb)
    ix0 = 2 * (peca.i_x_mm4 + area1 * centro[1] ** 2)
    iy0 = 2 * (peca.i_y_mm4 + area1 * centro[0] ** 2)
    ixy0 = 2 * (peca.i_xy_mm4 + area1 * centro[0] * centro[1])

    def inercia(angulo: float) -> float:
        return (
            (ix0 + iy0) / 2 + (ix0 - iy0) / 2 * math.cos(2 * angulo) - ixy0 * math.sin(2 * angulo)
        )

    def afastamento_da_reta(angulo: float) -> float:
        d = (angulo - math.atan2(centro[1], centro[0])) % math.pi
        return min(d, math.pi - d)

    principal = 0.5 * math.atan2(-2 * ixy0, ix0 - iy0)
    giro = min((principal, principal + math.pi / 2), key=afastamento_da_reta)
    cos, sen = math.cos(giro), math.sin(giro)
    direita = tuple(
        ((s / 2 + x) * cos + y * sen, -(s / 2 + x) * sen + y * cos) for x, y in peca.contorno
    )
    esquerda = tuple((-px, -py) for px, py in direita)
    return _secao(
        nome,
        arranjo,
        2 * area1,
        inercia(giro),
        inercia(giro + math.pi / 2),
        2 * peca.j_mm4,
        0.0,
        0.0,
        (esquerda, direita),
        paredes,
        **comuns,
    )


def dois_U(perfil: Secao, arranjo: str, s_mm: float = 0.0, nome_do_perfil: str = "") -> Secao:
    """A seção de dois perfis U iguais, de ``column_design.Secao`` do tipo "U".

    Usa as propriedades do próprio perfil (as do catálogo, quando ele vem de lá). ``J`` e ``C_w`` são
    a soma dos dois perfis: a torção não conta com o conjunto, a favor da segurança.
    """
    if arranjo not in (ARRANJO_2U_I, ARRANJO_2U_CAIXA):
        raise ValueError(f"Arranjo de perfis U desconhecido: {arranjo!r}.")
    if perfil.tipo != "U":
        raise ValueError("O arranjo pede um perfil U.")
    s = _afastamento(s_mm)
    dados = perfil.dims
    d, bf, tf, tw, xb = dados["d"], dados["bf"], dados["tf"], dados["tw"], dados["xb"]
    h = d / 2
    contorno: tuple[Ponto, ...] = (
        (0.0, -h), (bf, -h), (bf, -h + tf), (tw, -h + tf), (tw, h - tf), (bf, h - tf), (bf, h),
        (0.0, h),
    )  # fmt: skip
    if arranjo == ARRANJO_2U_I:
        distancia = xb + s / 2  # as almas de costas, com as mesas para fora
        direita = tuple((s / 2 + x, y) for x, y in contorno)
    else:
        distancia = bf - xb + s / 2  # as pontas das mesas de frente, com as almas para fora
        direita = tuple((s / 2 + bf - x, y) for x, y in contorno)
    esquerda = tuple((-px, py) for px, py in direita)
    nome = nome_do_perfil or perfil.nome
    return _secao(
        f"2 × {nome} {_SUFIXO[arranjo]}, s = {s:g} mm",
        arranjo,
        2 * perfil.A,
        2 * perfil.Ix,
        2 * (perfil.Iy + perfil.A * distancia**2),
        2 * perfil.J,
        2 * perfil.Cw,
        0.0,
        (esquerda, direita),
        [{**elemento, "n": 2 * elemento["n"]} for elemento in perfil.elementos],
        r_min=min(perfil.rx, perfil.ry),
        s=s,
        categoria_anglo="perfil_laminado_L_U",
        t_min=min(tf, tw),
        medidas=dict(d=d, bf=bf, tf=tf, tw=tw),
    )


# ---------------------------------------------------------------------------------------------
# Os espaçadores
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class LigacoesDaComposta:
    """O que o usuário decide sobre as ligações entre os perfis.

    ``comprimento_mm`` é o da barra, entre as ligações das pontas. ``quantidade`` são os espaçadores
    entre as pontas (``None`` = a menor quantidade que a norma aceita).
    """

    comprimento_mm: float
    ligacao: str = LIGACAO_APERTO_NORMAL
    pontas_rigidas: bool = True
    quantidade: int | None = None


@dataclass(frozen=True)
class AvaliacaoDasLigacoes:
    """A distância entre os espaçadores e o que ela faz com a força de flambagem em y."""

    norma: str
    arranjo: str
    comprimento_mm: float
    ligacao: str
    pontas_rigidas: bool
    quantidade: int
    quantidade_minima: int
    espacamento_mm: float  # ℓ adotado
    espacamento_maximo_mm: float  # o ℓ que o limite da norma aceita
    espacamento_sem_reducao_mm: float | None  # até aqui N_e,m = N_e,o; None se sempre reduz
    r_min_mm: float
    k_i: float
    esbeltez_da_peca: float  # ℓ/r_mín
    limite_da_peca: float
    esbeltez_do_conjunto: float  # (L/r)₀ máxima, dos dois eixos
    esbeltez_em_y: float  # (L/r)₀ na direção que carrega as ligações
    fator_de_reducao: float  # N_e,m/N_e,o

    @property
    def atende_o_limite(self) -> bool:
        return self.esbeltez_da_peca <= self.limite_da_peca + 1e-9

    @property
    def tem_quantidade_minima(self) -> bool:
        return self.quantidade >= ESPACADORES_MINIMOS

    @property
    def pede_pontas_rigidas(self) -> bool:
        return self.norma in REFERENCIA_DAS_PONTAS

    @property
    def posicoes_mm(self) -> tuple[float, ...]:
        """A altura de cada espaçador, da ponta de baixo: igualmente espaçados."""
        return tuple(self.espacamento_mm * k for k in range(1, self.quantidade + 1))

    @property
    def formula_da_reducao(self) -> str:
        """Como a redução saiu, com os números (N_e,m/N_e,o)."""
        lam, ell = self.esbeltez_em_y, self.esbeltez_da_peca
        if self.norma == "NBR8800_2008":
            return (
                "A NBR 8800:2008 não reduz N_e pela distância entre as ligações: vale só o limite "
                "de ℓ/r_mín."
            )
        if self.ligacao == LIGACAO_RIGIDA:
            if ell <= ESBELTEZ_SEM_REDUCAO:
                return f"ℓ/r_mín = {ell:.1f} ≤ 40, com solda ou protensão: N_e,m = N_e,o"
            return (
                f"N_e,m/N_e,o = (L/r)₀²/[(L/r)₀² + (K_i·ℓ/r_mín)²] = {lam:.1f}²/({lam:.1f}² + "
                f"({self.k_i:.2f}·{ell:.1f})²) = {self.fator_de_reducao:.3f}"
            )
        return (
            f"N_e,m/N_e,o = (L/r)₀²/[(L/r)₀² + (ℓ/r_mín)²] = {lam:.1f}²/({lam:.1f}² + {ell:.1f}²) "
            f"= {self.fator_de_reducao:.3f}"
        )


def fator_de_reducao(
    norma: str, ligacao: str, esbeltez_em_y: float, esbeltez_da_peca: float, k_i: float
) -> float:
    """``N_e,m/N_e,o`` (NBR 8800:2025 5.3.6.3 = AISC 360-16 E6.1); 1,0 na NBR 8800:2008."""
    if norma == "NBR8800_2008":
        return 1.0
    if ligacao == LIGACAO_RIGIDA:
        if esbeltez_da_peca <= ESBELTEZ_SEM_REDUCAO:
            return 1.0
        termo = k_i * esbeltez_da_peca
    else:
        termo = esbeltez_da_peca
    return esbeltez_em_y**2 / (esbeltez_em_y**2 + termo**2)


def espacadores_na_tracao(comprimento_mm: float, r_min_mm: float) -> int:
    """Menor quantidade de espaçadores da barra só tracionada: ℓ/r_mín ≤ 300 (5.2.8.2).

    Diferente da compressão, a norma não pede um mínimo de dois.
    """
    maximo = ESBELTEZ_DA_PECA_TRACIONADA * r_min_mm
    return max(0, math.ceil(comprimento_mm / maximo - 1e-9) - 1)


def avaliar(
    secao: Secao, ligacoes: LigacoesDaComposta, esbeltez_x: float, esbeltez_y: float, norma: str
) -> AvaliacaoDasLigacoes:
    """Distância máxima, quantidade mínima, a distância adotada e a redução de ``N_ey``.

    ``esbeltez_x`` e ``esbeltez_y`` são K·L/r da barra atuando como uma unidade. Com ``n``
    espaçadores igualmente espaçados, ``ℓ = L/(n + 1)``; a norma pede ``n ≥ 2``.
    """
    if secao.tipo != TIPO:
        raise ValueError("A seção não é uma barra composta.")
    if ligacoes.ligacao not in LIGACOES:
        raise ValueError(f"Ligação desconhecida: {ligacoes.ligacao!r}.")
    comprimento = _positivo("O comprimento da barra", ligacoes.comprimento_mm)
    r_min, k_i = secao.dims["r_min"], secao.dims["k_i"]
    conjunto = max(esbeltez_x, esbeltez_y)
    limite = FRACAO_DO_LIMITE[norma] * conjunto
    maximo = limite * r_min
    # L/(n + 1) ≤ ℓ_máx; a folga evita um espaçador a mais quando a conta dá exata
    minima = max(ESPACADORES_MINIMOS, math.ceil(comprimento / maximo - 1e-9) - 1)
    quantidade = minima if ligacoes.quantidade is None else int(ligacoes.quantidade)
    if quantidade < 0:
        raise ValueError("A quantidade de espaçadores não pode ser negativa.")
    espacamento = comprimento / (quantidade + 1)
    esbeltez_da_peca = espacamento / r_min
    sem_reducao: float | None = None
    if norma != "NBR8800_2008" and ligacoes.ligacao == LIGACAO_RIGIDA:
        sem_reducao = ESBELTEZ_SEM_REDUCAO * r_min
    return AvaliacaoDasLigacoes(
        norma=norma,
        arranjo=secao.dims["arranjo"],
        comprimento_mm=comprimento,
        ligacao=ligacoes.ligacao,
        pontas_rigidas=ligacoes.pontas_rigidas,
        quantidade=quantidade,
        quantidade_minima=minima,
        espacamento_mm=espacamento,
        espacamento_maximo_mm=maximo,
        espacamento_sem_reducao_mm=sem_reducao,
        r_min_mm=r_min,
        k_i=k_i,
        esbeltez_da_peca=esbeltez_da_peca,
        limite_da_peca=limite,
        esbeltez_do_conjunto=conjunto,
        esbeltez_em_y=esbeltez_y,
        fator_de_reducao=fator_de_reducao(
            norma, ligacoes.ligacao, esbeltez_y, esbeltez_da_peca, k_i
        ),
    )
