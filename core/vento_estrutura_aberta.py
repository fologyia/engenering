"""Vento em estruturas abertas — plataformas, mezaninos, pipe racks e estruturas reticuladas sem
fechamento — pela ABNT NBR 6123:2023, capítulo 8 (com 7.2.4).

A estrutura é vista como **reticulados planos paralelos** (8.3 e 8.4): para o vento ao longo de X,
cada pórtico no plano x = constante é um reticulado; o de barlavento recebe a força cheia e cada um
dos seguintes é multiplicado pelo fator de proteção η do reticulado imediatamente a barlavento.

* ``F_a = C_a·q·A_e`` (8.3), com ``C_a`` da Figura 12 (barras prismáticas de faces planas) em
  função do índice de área exposta ``φ = A_e/A_contorno``;
* ``η`` da Figura 14, em função de ``φ`` e do afastamento relativo ``e/h_b``;
* guarda-corpos são reticulados à parte (índice ``φ`` próprio, rodapé incluído); só os
  perpendiculares ao vento carregam — "a força do vento sobre as faces paralelas à direção do vento
  é considerada nula" (8.5);
* equipamentos: cilindro vertical pelas Tabelas 27 e 28 (``C_a`` pelo número de Reynolds e o fator
  ``K`` de comprimento finito, com a ponta apoiada no piso obstruída — 8.1.3); caixa ou painel com o
  ``C_a`` informado (2,0 a favor da segurança).

As forças são levadas aos níveis dos pisos por faixas de influência (meia altura do andar de baixo e
de cima). A metade inferior do primeiro andar vai direto à fundação. ``q`` de cada faixa é o do seu
topo (a favor da segurança). Barras de seção circular também usam a Figura 12 (C_a = 1,6 a 2,0, mais
do que os 1,1 da Figura 13): simplificação a favor da segurança.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from core import vento_nbr6123 as vb

EDICAO = vb.EDICAO

# Figura 12 — reticulado plano de barras prismáticas de faces planas: a curva é poligonal sobre a
# grade de 0,1 (transcrita da figura: 2,0 → 1,6 de φ = 0 a 0,5; 1,6 até 0,7; volta a 2,0 em 1,0).
_FIGURA_12: tuple[tuple[float, float], ...] = (
    (0.0, 2.0),
    (0.1, 1.9),
    (0.2, 1.8),
    (0.3, 1.7),
    (0.5, 1.6),
    (0.7, 1.6),
    (0.8, 1.7),
    (0.9, 1.8),
    (1.0, 2.0),
)

# Figura 14 — retas de (φ = 0; η = 1,1) a (φ = 0,6; patamar) com η ≤ 1; patamar por e/h_b.
_PATAMARES_ETA: tuple[tuple[float, float], ...] = (
    (0.5, 0.2),
    (1.0, 0.3),
    (2.0, 0.4),
    (3.0, 0.5),
    (4.0, 0.6),
    (5.0, 0.7),
    (6.0, 0.8),
    (7.0, 1.0),
)
PHI_DO_PATAMAR = 0.6

# Tabela 28 — fator de redução K para barras de comprimento finito.
_RAZOES_TABELA_28 = (2.0, 5.0, 10.0, 20.0, 40.0, 50.0, 100.0)
_TABELA_28: dict[str, tuple[float, ...]] = {
    "circular_subcritico": (0.58, 0.62, 0.68, 0.74, 0.82, 0.87, 0.98),
    "circular_acima_do_critico": (0.80, 0.80, 0.82, 0.90, 0.98, 0.99, 1.00),
    "faces_planas": (0.62, 0.66, 0.69, 0.81, 0.87, 0.90, 0.95),
}

FORMA_CILINDRO = "cilindro vertical"
FORMA_CAIXA = "caixa ou painel"
FORMAS_DE_EQUIPAMENTO = (FORMA_CILINDRO, FORMA_CAIXA)
CA_CAIXA_PADRAO = 2.0

INDICE_GUARDA_CORPO_PADRAO = 0.30
ALTURA_GUARDA_CORPO_PADRAO_M = 1.10


class VentoAbertoInvalido(ValueError):
    """Dado que o cálculo não aceita; a mensagem diz o que corrigir."""


def _positivo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor <= 0:
        raise VentoAbertoInvalido(f"{nome} precisa ser maior que zero.")
    return valor


def _interpolar(pontos: Sequence[tuple[float, float]], x: float) -> float:
    if x <= pontos[0][0]:
        return pontos[0][1]
    for (x0, y0), (x1, y1) in zip(pontos, pontos[1:], strict=False):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pontos[-1][1]


# ---------------------------------------------------------------------------------------------
# Coeficientes do capítulo 8
# ---------------------------------------------------------------------------------------------
def ca_reticulado_plano(phi: float) -> float:
    """``C_a`` de um reticulado plano isolado de barras de faces planas (Figura 12)."""
    phi = float(phi)
    if not 0.0 <= phi <= 1.0:
        raise VentoAbertoInvalido("O índice de área exposta φ precisa estar entre 0 e 1.")
    return _interpolar(_FIGURA_12, phi)


def patamar_eta(afastamento_relativo: float) -> float:
    """Valor de ``η`` para φ ≥ 0,6, interpolado linearmente entre as curvas de ``e/h_b``."""
    e_h = _positivo("O afastamento relativo e/h_b", afastamento_relativo)
    return _interpolar(_PATAMARES_ETA, e_h)


def fator_de_protecao(phi: float, afastamento_relativo: float) -> float:
    """``η`` da Figura 14 para o reticulado protegido pelo de barlavento (índice ``φ``)."""
    phi = float(phi)
    if not 0.0 <= phi <= 1.0:
        raise VentoAbertoInvalido("O índice de área exposta φ precisa estar entre 0 e 1.")
    patamar = patamar_eta(afastamento_relativo)
    eta = 1.1 - (1.1 - patamar) * min(phi, PHI_DO_PATAMAR) / PHI_DO_PATAMAR
    return min(1.0, eta)


def ca_de_n_reticulados(ca1: float, n: int, eta: float) -> float:
    """``C_an = C_a1·[1 + (n − 1)·η]`` (8.4) — n reticulados iguais e igualmente afastados."""
    if int(n) < 1:
        raise VentoAbertoInvalido("O número de reticulados precisa ser ao menos 1.")
    return ca1 * (1.0 + (int(n) - 1) * eta)


def numero_de_reynolds(vk_m_s: float, d_m: float) -> float:
    """``Re = 70 000·V_k·d`` (V_k em m/s; d em m)."""
    return 70_000.0 * _positivo("V_k", vk_m_s) * _positivo("O diâmetro", d_m)


def ca_cilindro(reynolds: float) -> float:
    """``C_a`` de barra prismática de seção circular de comprimento infinito (Tabela 27)."""
    re = _positivo("O número de Reynolds", reynolds)
    if re < 4.2e5:
        return 1.2
    if re < 8.4e5:
        return 0.6
    if re < 2.3e6:
        return 0.7
    return 0.8


def fator_k_comprimento(razao_l_c: float, tipo: str) -> float:
    """Fator ``K`` de comprimento finito (Tabela 28). Acima de 100 vale 1,0; abaixo de 2, o de 2."""
    if tipo not in _TABELA_28:
        raise VentoAbertoInvalido(f"Tipo de barra desconhecido para a Tabela 28: {tipo!r}.")
    razao = _positivo("A relação ℓ/c", razao_l_c)
    if razao > _RAZOES_TABELA_28[-1]:
        return 1.0
    return _interpolar(tuple(zip(_RAZOES_TABELA_28, _TABELA_28[tipo], strict=True)), razao)


# ---------------------------------------------------------------------------------------------
# Modelo da estrutura aberta
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Equipamento:
    """Equipamento ou carga exposta apoiada num nível (cotas a partir do piso desse nível)."""

    nome: str
    nivel: int  # 1 = primeiro piso acima da base
    forma: str = FORMA_CAIXA
    dimensao_x_m: float = 1.0  # medida ao longo de X (frontal ao vento Y); diâmetro no cilindro
    dimensao_y_m: float = 1.0  # medida ao longo de Y (frontal ao vento X)
    altura_m: float = 1.0
    peso_kN: float = 0.0
    ca: float | None = None  # None: 2,0 na caixa; Tabelas 27 e 28 no cilindro


@dataclass(frozen=True)
class GeometriaAberta:
    """Planta retangular ``L_x × L_y`` com pórticos regulares e pisos nas cotas dadas."""

    comprimento_x_m: float = 12.0
    largura_y_m: float = 6.0
    cotas_m: tuple[float, ...] = (4.0,)
    vaos_x: int = 2
    vaos_y: int = 1
    largura_pilar_m: float = 0.25  # maior dimensão da seção do pilar (vista pelo vento)
    altura_viga_m: float = 0.30  # vigas de piso nos pórticos
    # Contraventamento das linhas paralelas a X (planos y = constante, resistem ao vento em X)
    largura_diagonal_x_m: float = 0.064  # largura da diagonal vista pelo vento
    diagonais_por_painel_x: int = 2  # X ou V invertido: 2; diagonal simples: 1
    meio_painel_x: bool = False  # V invertido: cada diagonal vence meio painel
    paineis_contraventados_x: int = 1  # por andar, em cada linha paralela a X
    linhas_contraventadas_x: int = 2
    # Contraventamento das linhas paralelas a Y (planos x = constante)
    largura_diagonal_y_m: float = 0.064
    diagonais_por_painel_y: int = 2
    meio_painel_y: bool = False
    paineis_contraventados_y: int = 1
    linhas_contraventadas_y: int = 2
    guarda_corpo: bool = True
    altura_guarda_corpo_m: float = ALTURA_GUARDA_CORPO_PADRAO_M
    indice_guarda_corpo: float = INDICE_GUARDA_CORPO_PADRAO
    equipamentos: tuple[Equipamento, ...] = ()

    @property
    def altura_m(self) -> float:
        return self.cotas_m[-1] if self.cotas_m else 0.0

    @property
    def altura_total_m(self) -> float:
        return self.altura_m + (self.altura_guarda_corpo_m if self.guarda_corpo else 0.0)

    def alturas_dos_andares(self) -> tuple[float, ...]:
        anteriores = (0.0, *self.cotas_m[:-1])
        return tuple(z - z0 for z, z0 in zip(self.cotas_m, anteriores, strict=True))


@dataclass(frozen=True)
class ParametrosVento:
    v0_m_s: float = 35.0
    s1: float = 1.0
    categoria: str = "III"
    grupo_s3: int = 3
    s3: float | None = None


def validar_geometria(g: GeometriaAberta) -> list[str]:
    erros: list[str] = []
    for nome, valor in (
        ("O comprimento L_x", g.comprimento_x_m),
        ("A largura L_y", g.largura_y_m),
        ("A largura do pilar", g.largura_pilar_m),
        ("A altura da viga", g.altura_viga_m),
        ("A largura da diagonal das linhas em X", g.largura_diagonal_x_m),
        ("A largura da diagonal das linhas em Y", g.largura_diagonal_y_m),
    ):
        if not (math.isfinite(valor) and valor > 0):
            erros.append(f"{nome} precisa ser maior que zero.")
    if not g.cotas_m:
        erros.append("Informe ao menos um nível de piso.")
    else:
        anterior = 0.0
        for z in g.cotas_m:
            if not z > anterior:
                erros.append("As cotas dos pisos precisam ser positivas e crescentes.")
                break
            anterior = z
    if g.vaos_x < 1 or g.vaos_y < 1:
        erros.append("Cada direção precisa de ao menos um vão.")
    if g.diagonais_por_painel_x not in (1, 2) or g.diagonais_por_painel_y not in (1, 2):
        erros.append("Cada painel contraventado tem 1 ou 2 diagonais.")
    for nome, paineis, vaos, linhas, planos in (
        ("X", g.paineis_contraventados_x, g.vaos_x, g.linhas_contraventadas_x, g.vaos_y + 1),
        ("Y", g.paineis_contraventados_y, g.vaos_y, g.linhas_contraventadas_y, g.vaos_x + 1),
    ):
        if not 1 <= paineis <= vaos:
            erros.append(
                f"Os painéis contraventados por linha na direção {nome} vão de 1 até o número de "
                f"vãos ({vaos})."
            )
        if not 1 <= linhas <= planos:
            erros.append(
                f"As linhas contraventadas na direção {nome} vão de 1 até o número de linhas de "
                f"pilares ({planos})."
            )
    if g.guarda_corpo and not (g.altura_guarda_corpo_m > 0 and 0.0 < g.indice_guarda_corpo <= 1.0):
        erros.append("O guarda-corpo precisa de altura > 0 e índice φ entre 0 e 1.")
    for eq in g.equipamentos:
        if not 1 <= eq.nivel <= len(g.cotas_m):
            erros.append(f"{eq.nome}: o nível precisa estar entre 1 e {len(g.cotas_m)}.")
        if eq.forma not in FORMAS_DE_EQUIPAMENTO:
            erros.append(f"{eq.nome}: forma desconhecida ({eq.forma!r}).")
        if not (eq.dimensao_x_m > 0 and eq.dimensao_y_m > 0 and eq.altura_m > 0):
            erros.append(f"{eq.nome}: dimensões precisam ser maiores que zero.")
        if eq.peso_kN < 0:
            erros.append(f"{eq.nome}: o peso não pode ser negativo.")
        if eq.ca is not None and not eq.ca > 0:
            erros.append(f"{eq.nome}: C_a precisa ser maior que zero.")
    return erros


# ---------------------------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class PlanoReticulado:
    """Um pórtico perpendicular ao vento: área exposta, φ, C_a e η."""

    posicao: int  # 1 = barlavento
    contraventado: bool
    area_exposta_m2: float
    area_contorno_m2: float
    phi: float
    ca: float
    eta: float  # 1,0 no de barlavento
    coordenada_m: float = 0.0  # posição do pórtico ao longo da direção do vento (x ou y)


@dataclass(frozen=True)
class ForcaNoNivel:
    nivel: int
    cota_m: float
    faixa_m: tuple[float, float]
    q_N_m2: float
    estrutura_kN: float
    guarda_corpo_kN: float
    equipamentos_kN: float

    @property
    def total_kN(self) -> float:
        return self.estrutura_kN + self.guarda_corpo_kN + self.equipamentos_kN


@dataclass(frozen=True)
class VentoNaDirecao:
    direcao: str  # "X" ou "Y"
    largura_frontal_m: float
    afastamento_m: float
    altura_hb_m: float
    planos: tuple[PlanoReticulado, ...]
    niveis: tuple[ForcaNoNivel, ...]
    forca_na_base_kN: float  # metade inferior do 1º andar, direto à fundação
    detalhes_equipamentos: tuple[str, ...] = ()
    #: Força da estrutura (pilares, vigas, diagonais) em cada pórtico e nível: [pórtico][nível].
    estrutura_por_portico_kN: tuple[tuple[float, ...], ...] = ()
    #: Guarda-corpo em cada pórtico e nível (só o primeiro e o último pórtico recebem).
    guarda_corpo_por_portico_kN: tuple[tuple[float, ...], ...] = ()
    base_por_portico_kN: tuple[float, ...] = ()
    pilares_por_portico: int = 0
    #: Equipamentos por nível: (nome, força em kN, cota do centro em m).
    equipamentos_por_nivel: tuple[tuple[tuple[str, float, float], ...], ...] = ()
    #: Carga por metro do guarda-corpo (barlavento, sotavento) em cada nível, kN/m.
    guarda_corpo_kN_m: tuple[tuple[float, float], ...] = ()

    @property
    def forcas_nos_niveis_kN(self) -> tuple[float, ...]:
        return tuple(n.total_kN for n in self.niveis)

    @property
    def cortantes_dos_andares_kN(self) -> tuple[float, ...]:
        """Cortante do andar i (entre o nível i − 1 e o nível i): soma das forças de i para cima."""
        forcas = self.forcas_nos_niveis_kN
        return tuple(sum(forcas[i:]) for i in range(len(forcas)))

    @property
    def total_kN(self) -> float:
        return sum(self.forcas_nos_niveis_kN) + self.forca_na_base_kN

    @property
    def momento_na_base_kNm(self) -> float:
        return sum(n.total_kN * n.cota_m for n in self.niveis)


@dataclass(frozen=True)
class ResultadoVentoAberto:
    geometria: GeometriaAberta
    parametros: ParametrosVento
    vento_no_topo: vb.VentoNoLocal
    x: VentoNaDirecao
    y: VentoNaDirecao
    avisos: tuple[str, ...] = field(default_factory=tuple)

    def direcao(self, nome: str) -> VentoNaDirecao:
        return self.x if nome == "X" else self.y


# ---------------------------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------------------------
def _vento(p: ParametrosVento, z_m: float, classe: str) -> vb.VentoNoLocal:
    return vb.calcular_vento_no_local(
        p.v0_m_s,
        s1=p.s1,
        categoria=p.categoria,
        classe=classe,
        altura_m=max(z_m, 0.1),
        grupo_s3=p.grupo_s3,
        s3=p.s3,
    )


def _faixas(g: GeometriaAberta) -> list[tuple[float, float]]:
    cotas = list(g.cotas_m)
    faixas = []
    for i, z in enumerate(cotas):
        baixo = (cotas[i - 1] + z) / 2.0 if i > 0 else z / 2.0
        if i + 1 < len(cotas):
            alto = (z + cotas[i + 1]) / 2.0
        else:
            alto = z + (g.altura_guarda_corpo_m if g.guarda_corpo else 0.0)
        faixas.append((baixo, alto))
    return faixas


def _area_diagonais_do_andar(
    painel_m: float,
    altura_andar_m: float,
    paineis: int,
    diagonais_por_painel: int,
    largura_m: float,
    meio_painel: bool,
) -> float:
    projecao = painel_m / 2.0 if meio_painel else painel_m
    comprimento = math.hypot(projecao, altura_andar_m)
    return paineis * diagonais_por_painel * comprimento * largura_m


def _calcular_direcao(
    g: GeometriaAberta,
    p: ParametrosVento,
    direcao: str,
    classe: str,
    ordem_inversa: bool,
) -> VentoNaDirecao:
    if direcao == "X":
        largura = g.largura_y_m  # frontal ao vento X
        n_planos = g.vaos_x + 1
        afastamento = g.comprimento_x_m / g.vaos_x
        pilares_por_plano = g.vaos_y + 1
        painel = g.largura_y_m / g.vaos_y
        # Os planos x = constante contêm as diagonais que resistem ao vento em Y.
        linhas_contraventadas = g.linhas_contraventadas_y
        paineis = g.paineis_contraventados_y
        diagonais = (g.diagonais_por_painel_y, g.largura_diagonal_y_m, g.meio_painel_y)
    else:
        largura = g.comprimento_x_m
        n_planos = g.vaos_y + 1
        afastamento = g.largura_y_m / g.vaos_y
        pilares_por_plano = g.vaos_x + 1
        painel = g.comprimento_x_m / g.vaos_x
        linhas_contraventadas = g.linhas_contraventadas_x
        paineis = g.paineis_contraventados_x
        diagonais = (g.diagonais_por_painel_x, g.largura_diagonal_x_m, g.meio_painel_x)
    altura = g.altura_m
    alturas_andares = g.alturas_dos_andares()
    # Linhas contraventadas: as das extremidades primeiro (o arranjo usual), depois as internas.
    ordem_planos = list(range(n_planos))
    extremos_primeiro = sorted(ordem_planos, key=lambda k: (min(k, n_planos - 1 - k), k))
    contraventados = set(extremos_primeiro[:linhas_contraventadas])
    if ordem_inversa:
        ordem_planos.reverse()

    def area_estrutura(k: int, baixo: float, alto: float, nivel: int | None) -> float:
        """Área exposta do plano k entre as cotas ``baixo`` e ``alto`` (nivel: índice da faixa)."""
        topo_pilar = min(alto, altura)
        area = pilares_por_plano * g.largura_pilar_m * max(0.0, topo_pilar - baixo)
        if nivel is None:
            if k in contraventados:
                area += 0.5 * _area_diagonais_do_andar(
                    painel, alturas_andares[0], paineis, *diagonais
                )
            return area
        if nivel is not None:
            area += g.altura_viga_m * largura
            if k in contraventados:
                # metade das diagonais do andar abaixo e metade das do andar acima
                area += 0.5 * _area_diagonais_do_andar(
                    painel, alturas_andares[nivel], paineis, *diagonais
                )
                if nivel + 1 < len(alturas_andares):
                    area += 0.5 * _area_diagonais_do_andar(
                        painel, alturas_andares[nivel + 1], paineis, *diagonais
                    )
        return area

    # Índice de área exposta de cada plano no contorno completo (largura × altura da estrutura).
    contorno = largura * altura
    planos: list[PlanoReticulado] = []
    phi_anterior = None
    hb = min(largura, altura)
    e_hb = afastamento / hb
    for posicao, k in enumerate(ordem_planos, start=1):
        area_total = pilares_por_plano * g.largura_pilar_m * altura + len(g.cotas_m) * (
            g.altura_viga_m * largura
        )
        if k in contraventados:
            area_total += sum(
                _area_diagonais_do_andar(painel, h_andar, paineis, *diagonais)
                for h_andar in alturas_andares
            )
        phi = min(1.0, area_total / contorno)
        eta = 1.0 if phi_anterior is None else fator_de_protecao(phi_anterior, e_hb)
        planos.append(
            PlanoReticulado(
                posicao=posicao,
                contraventado=k in contraventados,
                area_exposta_m2=area_total,
                area_contorno_m2=contorno,
                phi=phi,
                ca=ca_reticulado_plano(phi),
                eta=eta,
                coordenada_m=k * afastamento,
            )
        )
        phi_anterior = phi

    faixas = _faixas(g)
    niveis: list[ForcaNoNivel] = []
    detalhes_eq: list[str] = []
    por_portico: list[list[float]] = [[] for _ in planos]
    gc_por_portico: list[list[float]] = [[] for _ in planos]
    equip_por_nivel: list[tuple[tuple[str, float, float], ...]] = []
    gc_por_metro: list[tuple[float, float]] = []
    # Guarda-corpo: um de barlavento e um de sotavento; o de sotavento protegido pelo primeiro.
    if g.guarda_corpo:
        ca_gc = ca_reticulado_plano(g.indice_guarda_corpo)
        eta_gc = fator_de_protecao(
            g.indice_guarda_corpo, (afastamento * (n_planos - 1)) / g.altura_guarda_corpo_m
        )
        area_gc = g.indice_guarda_corpo * g.altura_guarda_corpo_m * largura
    for i, (baixo, alto) in enumerate(faixas):
        vento = _vento(p, alto, classe)
        q_kN = vento.q_N_m2 / 1e3
        parcelas = [
            plano.eta * plano.ca * q_kN * area_estrutura(k, baixo, alto, i)
            for plano, k in zip(planos, ordem_planos, strict=True)
        ]
        for j, parcela in enumerate(parcelas):
            por_portico[j].append(parcela)
        estrutura = sum(parcelas)
        guarda = 0.0
        if g.guarda_corpo:
            q_gc = _vento(p, g.cotas_m[i] + g.altura_guarda_corpo_m, classe).q_N_m2 / 1e3
            barlavento = ca_gc * q_gc * area_gc
            sotavento = eta_gc * barlavento
            guarda = barlavento + sotavento
            gc_por_metro.append((barlavento / largura, sotavento / largura))
            for j in range(len(planos)):
                if j == 0:
                    gc_por_portico[j].append(barlavento)
                elif j == len(planos) - 1:
                    gc_por_portico[j].append(sotavento)
                else:
                    gc_por_portico[j].append(0.0)
        else:
            gc_por_metro.append((0.0, 0.0))
            for j in range(len(planos)):
                gc_por_portico[j].append(0.0)
        equipamentos = 0.0
        deste_nivel: list[tuple[str, float, float]] = []
        for eq in g.equipamentos:
            if eq.nivel != i + 1:
                continue
            forca, texto = _forca_equipamento(eq, g.cotas_m[i], direcao, p, classe)
            equipamentos += forca
            detalhes_eq.append(texto)
            deste_nivel.append((eq.nome, forca, g.cotas_m[i] + eq.altura_m / 2.0))
        equip_por_nivel.append(tuple(deste_nivel))
        niveis.append(
            ForcaNoNivel(
                nivel=i + 1,
                cota_m=g.cotas_m[i],
                faixa_m=(baixo, alto),
                q_N_m2=vento.q_N_m2,
                estrutura_kN=estrutura,
                guarda_corpo_kN=guarda,
                equipamentos_kN=equipamentos,
            )
        )
    # Faixa da base: pilares de 0 até a metade do primeiro andar.
    base_alto = faixas[0][0]
    q_base = _vento(p, base_alto, classe).q_N_m2 / 1e3
    base_por_portico = [
        plano.eta * plano.ca * q_base * area_estrutura(k, 0.0, base_alto, None)
        for plano, k in zip(planos, ordem_planos, strict=True)
    ]
    forca_base = sum(base_por_portico)
    return VentoNaDirecao(
        direcao=direcao,
        largura_frontal_m=largura,
        afastamento_m=afastamento,
        altura_hb_m=hb,
        planos=tuple(planos),
        niveis=tuple(niveis),
        forca_na_base_kN=forca_base,
        detalhes_equipamentos=tuple(detalhes_eq),
        estrutura_por_portico_kN=tuple(tuple(v) for v in por_portico),
        guarda_corpo_por_portico_kN=tuple(tuple(v) for v in gc_por_portico),
        base_por_portico_kN=tuple(base_por_portico),
        pilares_por_portico=pilares_por_plano,
        equipamentos_por_nivel=tuple(equip_por_nivel),
        guarda_corpo_kN_m=tuple(gc_por_metro),
    )


def _forca_equipamento(
    eq: Equipamento, cota_m: float, direcao: str, p: ParametrosVento, classe: str
) -> tuple[float, str]:
    topo = cota_m + eq.altura_m
    vento = _vento(p, topo, classe)
    q_kN = vento.q_N_m2 / 1e3
    if eq.forma == FORMA_CILINDRO:
        d = eq.dimensao_x_m
        area = d * eq.altura_m
        if eq.ca is not None:
            ca, origem = eq.ca, "informado"
        else:
            re = numero_de_reynolds(vento.vk_m_s, d)
            ca_infinito = ca_cilindro(re)
            tipo = "circular_subcritico" if re < 4.2e5 else "circular_acima_do_critico"
            # Base apoiada no piso: um extremo obstruído — ℓ/d dobra (8.1.3).
            k = fator_k_comprimento(2.0 * eq.altura_m / d, tipo)
            ca = ca_infinito * k
            origem = f"Tab. 27 (Re = {re:.2g}) × K = {k:.2f} (Tab. 28, 2ℓ/d)"
    else:
        frontal = eq.dimensao_y_m if direcao == "X" else eq.dimensao_x_m
        area = frontal * eq.altura_m
        ca = CA_CAIXA_PADRAO if eq.ca is None else eq.ca
        origem = "informado" if eq.ca is not None else "2,0 (a favor da segurança)"
    forca = ca * q_kN * area
    texto = (
        f"{eq.nome} (nível {eq.nivel}, vento {direcao}): F = C_a·q·A = {ca:.2f} × "
        f"{q_kN:.3f} kN/m² × {area:.2f} m² = {forca:.2f} kN; C_a {origem}"
    )
    return forca, texto


def calcular_vento_aberto(g: GeometriaAberta, p: ParametrosVento) -> ResultadoVentoAberto:
    """Forças do vento por nível, nas direções X e Y (cada uma vale nos dois sentidos)."""
    erros = validar_geometria(g)
    if erros:
        raise VentoAbertoInvalido(" ".join(erros))
    _positivo("V₀", p.v0_m_s)
    maior = max(g.comprimento_x_m, g.largura_y_m, g.altura_total_m)
    classe = vb.classe_da_edificacao(maior)
    avisos: list[str] = []
    resultados = {}
    for direcao in ("X", "Y"):
        a = _calcular_direcao(g, p, direcao, classe, ordem_inversa=False)
        b = _calcular_direcao(g, p, direcao, classe, ordem_inversa=True)
        # Vento nos dois sentidos: vale o arranjo que dá mais força (os planos podem diferir).
        resultados[direcao] = a if a.total_kN >= b.total_kN else b
        phis = [pl.phi for pl in resultados[direcao].planos]
        if max(phis) > 0.6:
            avisos.append(
                f"Vento em {direcao}: pórtico com φ = {max(phis):.2f} — quase fechado. Confira se "
                "não é o caso de tratá-lo como placa ou edificação (Figura 12 vale para φ ≤ 1, "
                "mas a proteção entre pórticos cai)."
            )
    if g.altura_total_m > 0 and g.altura_total_m / min(g.comprimento_x_m, g.largura_y_m) > 6:
        avisos.append(
            "Estrutura esbelta (altura maior que 6 vezes a menor dimensão em planta): avalie os "
            "efeitos dinâmicos do vento (NBR 6123, capítulo 9)."
        )
    topo = _vento(p, g.altura_total_m, classe)
    avisos.extend(topo.avisos)
    return ResultadoVentoAberto(
        geometria=g,
        parametros=p,
        vento_no_topo=topo,
        x=resultados["X"],
        y=resultados["Y"],
        avisos=tuple(avisos),
    )


# ---------------------------------------------------------------------------------------------
# Saídas para o modelo (SolidWorks, Robot): forças nos nós e cargas distribuídas
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CargaNodal:
    """Força horizontal num nível de um pórtico, e a parcela de cada pilar (nó pilar–viga)."""

    direcao: str
    portico: int  # 1 = barlavento
    coordenada_m: float
    nivel: int  # 0 = base (vai direto à fundação)
    cota_m: float
    estrutura_kN: float
    guarda_corpo_kN: float
    pilares: int

    @property
    def total_kN(self) -> float:
        return self.estrutura_kN + self.guarda_corpo_kN

    @property
    def por_pilar_kN(self) -> float:
        return self.total_kN / self.pilares if self.pilares else self.total_kN


def cargas_nodais(r: VentoNaDirecao, *, incluir_base: bool = False) -> list[CargaNodal]:
    """Uma linha por pórtico e nível: a força que vai nos nós daquele nível do pórtico.

    A soma de todas as linhas (mais os equipamentos) é a força do vento na direção. A faixa da base
    (até meio primeiro andar) vai direto à fundação e só entra com ``incluir_base``.
    """
    linhas: list[CargaNodal] = []
    for j, plano in enumerate(r.planos):
        if incluir_base and r.base_por_portico_kN:
            linhas.append(
                CargaNodal(
                    r.direcao,
                    plano.posicao,
                    plano.coordenada_m,
                    0,
                    0.0,
                    r.base_por_portico_kN[j],
                    0.0,
                    r.pilares_por_portico,
                )
            )
        for i, nivel in enumerate(r.niveis):
            linhas.append(
                CargaNodal(
                    direcao=r.direcao,
                    portico=plano.posicao,
                    coordenada_m=plano.coordenada_m,
                    nivel=nivel.nivel,
                    cota_m=nivel.cota_m,
                    estrutura_kN=r.estrutura_por_portico_kN[j][i],
                    guarda_corpo_kN=r.guarda_corpo_por_portico_kN[j][i],
                    pilares=r.pilares_por_portico,
                )
            )
    return linhas


@dataclass(frozen=True)
class CargaDistribuida:
    direcao: str
    portico: int
    elemento: str
    trecho: str
    w_kN_m: float
    calculo: str = ""


def _m(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",")


def cargas_distribuidas(g: GeometriaAberta, r: VentoNaDirecao) -> list[CargaDistribuida]:
    """Carga por metro em cada pilar, viga e guarda-corpo dos pórticos (q da faixa de cada nível).

    Para quem prefere lançar o vento nas barras em vez de nos nós. Pilares: ``η·C_a·q·b``; vigas
    de cada piso: ``η·C_a·q·d``; guarda-corpo: ``C_a·q·φ·h`` na viga de borda (o de sotavento com
    o seu η). As diagonais ficam de fora (o vento nelas já está na força nos nós, e numa barra
    inclinada a carga por metro depende do modelo).
    """
    faixas = _faixas(g)
    q_niveis = [n.q_N_m2 / 1e3 for n in r.niveis]
    linhas: list[CargaDistribuida] = []
    for j, plano in enumerate(r.planos):
        fator = plano.eta * plano.ca
        # Pilares em faixas; a primeira começa na base e usa o q do primeiro nível (maior que o
        # da base: a favor da segurança).
        for i, (baixo, alto) in enumerate(faixas):
            inicio = 0.0 if i == 0 else baixo
            fim = min(alto, g.altura_m)
            if fim > inicio:
                linhas.append(
                    CargaDistribuida(
                        r.direcao,
                        plano.posicao,
                        "Pilares (cada um)",
                        f"z = {_m(inicio)} a {_m(fim)} m",
                        fator * q_niveis[i] * g.largura_pilar_m,
                        f"η·C_a·q·b = {plano.eta:.3f}·{plano.ca:.2f}·{q_niveis[i]:.3f}·"
                        f"{g.largura_pilar_m:.3f}",
                    )
                )
        for i, nivel in enumerate(r.niveis):
            linhas.append(
                CargaDistribuida(
                    r.direcao,
                    plano.posicao,
                    f"Vigas do nível {nivel.nivel}",
                    f"z = {_m(nivel.cota_m)} m, ao longo de {_m(r.largura_frontal_m)} m",
                    fator * q_niveis[i] * g.altura_viga_m,
                    f"η·C_a·q·d = {plano.eta:.3f}·{plano.ca:.2f}·{q_niveis[i]:.3f}·"
                    f"{g.altura_viga_m:.3f}",
                )
            )
            if r.guarda_corpo_kN_m and j in (0, len(r.planos) - 1):
                w = r.guarda_corpo_kN_m[i][0 if j == 0 else 1]
                if w > 0:
                    linhas.append(
                        CargaDistribuida(
                            r.direcao,
                            plano.posicao,
                            f"Guarda-corpo do nível {nivel.nivel}",
                            f"viga de borda a z = {_m(nivel.cota_m)} m",
                            w,
                            "C_a·q·φ·h" + (" (barlavento)" if j == 0 else " × η (sotavento)"),
                        )
                    )
    return linhas
