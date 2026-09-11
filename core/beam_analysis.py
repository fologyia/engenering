"""Análise de vigas e eixos: cortante, momento, linha elástica e torção.

O módulo resolve uma barra reta (viga ou eixo) por rigidez direta com
elementos de Euler-Bernoulli e recupera os esforços internos de forma
**analítica** dentro de cada elemento. Como os nós são colocados em toda
descontinuidade (apoio, carga pontual, momento, início/fim de carga
distribuída), a carga distribuída dentro de um elemento é sempre uma única
função linear — logo ``V(x)`` é quadrática, ``M(x)`` é cúbica e a linha
elástica ``v(x)`` é um polinômio de quinto grau, todos exatos.

Com a segunda ordem ligada (``K = K_e + K_g``), a linha elástica continua
vindo da parcela elástica ``K_e·u`` — a única que, integrada, reproduz os
deslocamentos nodais — e os esforços internos vêm do conjunto em equilíbrio
``(K_e + K_g)·u`` mais o momento do esforço normal no braço da flecha,
``N̄·(v − v_i)``, com ``V = dM/dx = Q + N̄·θ``. É o que mantém ``M`` e ``V``
contínuos entre elementos e a menos de 0,02 % da solução fechada de
coluna-viga (ver ``docs/vigas_e_eixos.md``).

Convenções (todas em torno do eixo de flexão informado na seção):

* ``x`` cresce da esquerda para a direita; ``y`` é positivo para cima.
* Forças transversais e cargas distribuídas são **positivas para cima**.
* Momentos concentrados são positivos no sentido anti-horário (+z).
* Força axial é positiva em +x; o esforço normal interno ``N`` é positivo
  quando traciona a seção.
* ``V`` segue a convenção clássica (positivo quando gira o trecho à
  esquerda no sentido horário) e ``M`` é positivo quando comprime a fibra
  superior ("barriga para baixo").
* A flecha ``v`` é positiva para cima, coerente com ``E I v'' = M``.

Unidades internas: N, mm, MPa, N·mm.
"""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np

from core.load_to_stress import EstadoPlanoCalculado
from core.section_stress import EsforcosSecao, tensoes_combinadas

# ---------------------------------------------------------------------------
# Tolerâncias e constantes
# ---------------------------------------------------------------------------

# Duas posições mais próximas do que isto são tratadas como o mesmo nó. É
# grande o bastante para absorver arredondamento de entrada (x = 2000.0 vs
# 1999.9999) e pequeno o bastante para não fundir cargas realmente distintas.
TOLERANCIA_POSICAO_MM = 1e-6

# Fusão relativa ao comprimento: posições a menos de 0,01 % de L uma da outra
# caem no mesmo nó (ver ``_tolerancia_de_posicao``).
FRACAO_FUSAO_DE_NOS = 1e-4

GRAVIDADE_M_S2 = 9.80665

# Carga sem caso declarado é permanente: é o que a esmagadora maioria dos
# modelos tem, e evita obrigar quem só quer uma viga simples a aprender
# combinações antes de calcular.
CASO_PADRAO = "Permanente"

# Divisões por trecho que a segunda ordem (e qualquer carga axial) pede por
# padrão: com 8 o fator de carga crítica da coluna biapoiada sai a 0,003 %.
DIVISOES_SEGUNDA_ORDEM = 8

# Teto da malha. O teste de posto e o solver são O(n³) na matriz cheia: com
# 2 000 elementos (4 000 graus de flexão) a análise leva alguns segundos;
# acima disso o tempo cresce com o cubo e nenhum resultado melhora — a
# solução nodal de primeira ordem é exata em qualquer malha e a segunda
# ordem já convergiu com 8 a 32 divisões por trecho.
ELEMENTOS_MAXIMOS = 2_000

# Quantidade de amostras dos diagramas que o programa mira no total. Os
# extremos não dependem disto (as raízes de V, M, θ, w e a caem sempre
# numa amostra); o que a densidade muda é o traçado e o tamanho da tabela —
# e um gráfico com dezenas de milhares de pontos só custa memória.
PONTOS_TOTAIS_ALVO = 4_000

TIPOS_APOIO: dict[str, tuple[bool, bool, bool, bool]] = {
    # tipo: (vertical, horizontal, rotação, torção)
    "rolete": (True, False, False, False),
    "pino": (True, True, False, True),
    "engaste": (True, True, True, True),
    "engaste deslizante": (False, True, True, True),
    "apoio horizontal": (False, True, False, False),
    "mola": (False, False, False, False),
    "livre": (False, False, False, False),
}

DESCRICAO_APOIO: dict[str, str] = {
    "rolete": "Rolete — impede o deslocamento vertical (Δ = 0, M = 0).",
    "pino": "Pino — impede deslocamento vertical e horizontal (Δ = 0, M = 0).",
    "engaste": "Extremidade fixa — impede deslocamento e rotação (Δ = 0, θ = 0).",
    "engaste deslizante": (
        "Engaste deslizante (guiado) — impede a rotação e o deslocamento "
        "axial, mas libera o deslocamento transversal (θ = 0, V = 0)."
    ),
    "apoio horizontal": "Trava axial — impede apenas o deslocamento em x.",
    "mola": (
        "Apoio elástico — não impede nada por si só; a restrição vem da "
        "rigidez kv (N/mm) e/ou kr (N·mm/rad) informada."
    ),
    "livre": "Extremidade livre — sem restrição (V = 0, M = 0).",
}


# ---------------------------------------------------------------------------
# Seção transversal e material
# ---------------------------------------------------------------------------


def _positivo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor <= 0:
        raise ValueError(f"{nome} deve ser um número finito maior que zero.")
    return valor


def _nao_negativo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor < 0:
        raise ValueError(f"{nome} deve ser um número finito não negativo.")
    return valor


def _finito(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor):
        raise ValueError(f"{nome} deve ser um número finito.")
    return valor


@dataclass(frozen=True, slots=True)
class SecaoViga:
    """Propriedades da seção necessárias para esforços e tensões.

    ``modulo_torcao_mm3`` (Wt) é usado como ``tau_max = T / Wt``, o que vale
    tanto para seções circulares (Wt = J / c) quanto para retangulares e
    perfis abertos, onde a tensão máxima **não** é ``T c / J``.
    """

    nome: str
    area_mm2: float
    inercia_mm4: float
    c_superior_mm: float
    c_inferior_mm: float
    momento_estatico_mm3: float
    espessura_cisalhamento_mm: float
    constante_torcao_mm4: float
    modulo_torcao_mm3: float
    area_cisalhamento_mm2: float = 0.0
    descricao: str = ""
    # Inércia em torno do outro eixo principal (zero = desconhecida). Não
    # entra na flexão — o modelo é plano —, mas é o que permite estimar a
    # carga crítica **fora do plano**: uma barra comprimida flamba em torno
    # do eixo de menor inércia, que raramente é o eixo em que ela é fletida.
    inercia_transversal_mm4: float = 0.0

    def __post_init__(self) -> None:
        _positivo("area_mm2", self.area_mm2)
        _positivo("inercia_mm4", self.inercia_mm4)
        _positivo("c_superior_mm", self.c_superior_mm)
        _positivo("c_inferior_mm", self.c_inferior_mm)
        _nao_negativo("momento_estatico_mm3", self.momento_estatico_mm3)
        _nao_negativo("espessura_cisalhamento_mm", self.espessura_cisalhamento_mm)
        _nao_negativo("constante_torcao_mm4", self.constante_torcao_mm4)
        _nao_negativo("modulo_torcao_mm3", self.modulo_torcao_mm3)
        _nao_negativo("area_cisalhamento_mm2", self.area_cisalhamento_mm2)
        _nao_negativo("inercia_transversal_mm4", self.inercia_transversal_mm4)
        if not self.tem_cisalhamento:
            raise ValueError(
                "A seção precisa de Q e t (para V·Q/(I·t)) ou de uma área de "
                "cisalhamento (para V/Av); sem isso a tensão de cisalhamento "
                "seria sempre zero."
            )
        # Limites que toda seção real respeita (I = ∫y²dA ≤ A·c², Q ≤ A·c/2,
        # Av ≤ A). Violá-los não é geometria: é unidade trocada (cm⁴ por mm⁴,
        # I em vez de W…), e o cálculo seguiria com tensões absurdas.
        c_maximo = max(self.c_superior_mm, self.c_inferior_mm)
        if self.inercia_mm4 > self.area_mm2 * c_maximo**2 * (1.0 + 1e-9):
            raise ValueError(
                f"I = {self.inercia_mm4:.4g} mm⁴ é maior que A·c² = "
                f"{self.area_mm2 * c_maximo**2:.4g} mm⁴, o que nenhuma seção tem "
                "(I = ∫y²dA ≤ A·c²). Confira as unidades: I em mm⁴, A em mm², c em mm."
            )
        if self.momento_estatico_mm3 > self.area_mm2 * c_maximo / 2.0 * (1.0 + 1e-9):
            raise ValueError(
                f"Q = {self.momento_estatico_mm3:.4g} mm³ é maior que A·c/2 = "
                f"{self.area_mm2 * c_maximo / 2.0:.4g} mm³, o que nenhuma seção tem. "
                "Confira as unidades de Q (mm³)."
            )
        if self.area_cisalhamento_mm2 > self.area_mm2 * (1.0 + 1e-9):
            raise ValueError(
                f"A área de cisalhamento Av = {self.area_cisalhamento_mm2:.4g} mm² é "
                f"maior que a área da seção A = {self.area_mm2:.4g} mm²."
            )

    @property
    def tem_cisalhamento(self) -> bool:
        exato = self.momento_estatico_mm3 > 0 and self.espessura_cisalhamento_mm > 0
        return exato or self.area_cisalhamento_mm2 > 0

    @property
    def modulo_resistencia_superior_mm3(self) -> float:
        return self.inercia_mm4 / self.c_superior_mm

    @property
    def modulo_resistencia_inferior_mm3(self) -> float:
        return self.inercia_mm4 / self.c_inferior_mm

    @property
    def altura_mm(self) -> float:
        return self.c_superior_mm + self.c_inferior_mm


@dataclass(frozen=True, slots=True)
class MaterialViga:
    """Propriedades do material e de onde elas vieram.

    ``material_id`` aponta para um material qualificado do projeto ativo. É
    o que permite o registro técnico declarar ``materiais_ids`` e a Central
    de Validação avisar quando aquele material for revisado — sem isso, o
    cálculo sabe o valor de Sy mas não sabe de quem ele é.
    """

    nome: str
    modulo_elasticidade_MPa: float
    modulo_cisalhamento_MPa: float
    escoamento_MPa: float | None = None
    densidade_kg_m3: float = 7_850.0
    material_id: str | None = None
    fonte: str = ""

    def __post_init__(self) -> None:
        _positivo("modulo_elasticidade_MPa", self.modulo_elasticidade_MPa)
        _positivo("modulo_cisalhamento_MPa", self.modulo_cisalhamento_MPa)
        if self.escoamento_MPa is not None:
            _positivo("escoamento_MPa", self.escoamento_MPa)
        _nao_negativo("densidade_kg_m3", self.densidade_kg_m3)


def secao_retangular(base_mm: float, altura_mm: float, *, nome: str = "Retangular") -> SecaoViga:
    b = _positivo("base_mm", base_mm)
    h = _positivo("altura_mm", altura_mm)
    maior, menor = (b, h) if b >= h else (h, b)
    # Torção de Saint-Venant em seção retangular maciça (Roark/Shigley).
    j = maior * menor**3 * (1 / 3 - 0.21 * (menor / maior) * (1 - menor**4 / (12 * maior**4)))
    wt = maior**2 * menor**2 / (3 * maior + 1.8 * menor)
    return SecaoViga(
        nome=nome,
        area_mm2=b * h,
        inercia_mm4=b * h**3 / 12.0,
        c_superior_mm=h / 2.0,
        c_inferior_mm=h / 2.0,
        momento_estatico_mm3=b * h**2 / 8.0,
        espessura_cisalhamento_mm=b,
        constante_torcao_mm4=j,
        modulo_torcao_mm3=wt,
        area_cisalhamento_mm2=b * h,
        inercia_transversal_mm4=h * b**3 / 12.0,
        descricao=f"Retangular {b:.4g} × {h:.4g} mm (flexão em torno do eixo horizontal).",
    )


def secao_circular_macica(diametro_mm: float, *, nome: str = "Circular maciça") -> SecaoViga:
    d = _positivo("diametro_mm", diametro_mm)
    inercia = math.pi * d**4 / 64.0
    return SecaoViga(
        nome=nome,
        area_mm2=math.pi * d**2 / 4.0,
        inercia_mm4=inercia,
        c_superior_mm=d / 2.0,
        c_inferior_mm=d / 2.0,
        momento_estatico_mm3=d**3 / 12.0,
        espessura_cisalhamento_mm=d,
        constante_torcao_mm4=2 * inercia,
        modulo_torcao_mm3=math.pi * d**3 / 16.0,
        area_cisalhamento_mm2=math.pi * d**2 / 4.0,
        inercia_transversal_mm4=inercia,
        descricao=f"Barra circular maciça ⌀{d:.4g} mm.",
    )


def secao_tubo_circular(
    diametro_externo_mm: float,
    diametro_interno_mm: float,
    *,
    nome: str = "Tubo circular",
) -> SecaoViga:
    de = _positivo("diametro_externo_mm", diametro_externo_mm)
    di = _nao_negativo("diametro_interno_mm", diametro_interno_mm)
    if di >= de:
        raise ValueError("O diâmetro interno deve ser menor que o externo.")
    inercia = math.pi * (de**4 - di**4) / 64.0
    return SecaoViga(
        nome=nome,
        area_mm2=math.pi * (de**2 - di**2) / 4.0,
        inercia_mm4=inercia,
        c_superior_mm=de / 2.0,
        c_inferior_mm=de / 2.0,
        momento_estatico_mm3=(de**3 - di**3) / 12.0,
        espessura_cisalhamento_mm=de - di,
        constante_torcao_mm4=2 * inercia,
        modulo_torcao_mm3=2 * inercia / (de / 2.0),
        area_cisalhamento_mm2=math.pi * (de**2 - di**2) / 4.0,
        inercia_transversal_mm4=inercia,
        descricao=f"Tubo circular ⌀{de:.4g} × ⌀{di:.4g} mm.",
    )


def secao_tubo_retangular(
    largura_mm: float,
    altura_mm: float,
    espessura_mm: float,
    *,
    nome: str = "Tubo retangular",
) -> SecaoViga:
    b = _positivo("largura_mm", largura_mm)
    h = _positivo("altura_mm", altura_mm)
    t = _positivo("espessura_mm", espessura_mm)
    if 2 * t >= min(b, h):
        raise ValueError("A espessura da parede é grande demais para as dimensões informadas.")
    bi, hi = b - 2 * t, h - 2 * t
    inercia = (b * h**3 - bi * hi**3) / 12.0
    # Momento estático das duas almas + mesa superior, na linha neutra.
    q = b * t * (h - t) / 2.0 + 2 * t * ((h / 2.0 - t) ** 2) / 2.0
    # Bredt para seção fechada de parede fina.
    area_media = (b - t) * (h - t)
    perimetro_medio = 2 * ((b - t) + (h - t))
    return SecaoViga(
        nome=nome,
        area_mm2=b * h - bi * hi,
        inercia_mm4=inercia,
        c_superior_mm=h / 2.0,
        c_inferior_mm=h / 2.0,
        momento_estatico_mm3=q,
        espessura_cisalhamento_mm=2 * t,
        constante_torcao_mm4=4 * area_media**2 * t / perimetro_medio,
        modulo_torcao_mm3=2 * area_media * t,
        area_cisalhamento_mm2=2 * t * h,
        inercia_transversal_mm4=(h * b**3 - hi * bi**3) / 12.0,
        descricao=f"Tubo retangular {b:.4g} × {h:.4g} × {t:.4g} mm.",
    )


def secao_i_simetrica(
    altura_mm: float,
    largura_mesa_mm: float,
    espessura_alma_mm: float,
    espessura_mesa_mm: float,
    *,
    nome: str = "Perfil I",
) -> SecaoViga:
    h = _positivo("altura_mm", altura_mm)
    bf = _positivo("largura_mesa_mm", largura_mesa_mm)
    tw = _positivo("espessura_alma_mm", espessura_alma_mm)
    tf = _positivo("espessura_mesa_mm", espessura_mesa_mm)
    if 2 * tf >= h:
        raise ValueError("As mesas não cabem na altura informada.")
    hw = h - 2 * tf
    area = 2 * bf * tf + tw * hw
    inercia = (bf * h**3 - (bf - tw) * hw**3) / 12.0
    q = bf * tf * (h - tf) / 2.0 + tw * hw**2 / 8.0
    # Perfil aberto: J = Σ b t³/3 e tau_max = T t_max / J.
    j = (2 * bf * tf**3 + hw * tw**3) / 3.0
    t_max = max(tf, tw)
    return SecaoViga(
        nome=nome,
        area_mm2=area,
        inercia_mm4=inercia,
        c_superior_mm=h / 2.0,
        c_inferior_mm=h / 2.0,
        momento_estatico_mm3=q,
        espessura_cisalhamento_mm=tw,
        constante_torcao_mm4=j,
        modulo_torcao_mm3=j / t_max,
        area_cisalhamento_mm2=tw * h,
        inercia_transversal_mm4=(2 * tf * bf**3 + hw * tw**3) / 12.0,
        descricao=(
            f"Perfil I {h:.4g} × {bf:.4g} mm (alma {tw:.4g}, mesa {tf:.4g}). "
            "Torção de perfil aberto — muito pouco rígida."
        ),
    )


def _familia_do_perfil(perfil: Any) -> str:
    """Primeira palavra da família, em maiúsculas: "T", "U", "W", "TUBO"…"""
    familia = str(getattr(perfil, "familia", "") or "").strip()
    return familia.split()[0].upper() if familia else ""


def _familia_normalizada(perfil: Any) -> str:
    familia = str(getattr(perfil, "familia", "") or "")
    decomposta = unicodedata.normalize("NFD", familia)
    return "".join(c for c in decomposta if unicodedata.category(c) != "Mn").casefold()


def _modulo_de_torcao_do_perfil(perfil: Any) -> tuple[float, str]:
    """``Wt`` coerente com a forma da seção, e uma nota quando é estimativa.

    ``J / t_máx`` é a torção de Saint-Venant de perfil **aberto** (I, W, U,
    C, T). Aplicada a um tubo — seção fechada — ela dava um ``Wt`` seis
    vezes maior que o de Bredt, ou seja, tensão de torção seis vezes menor
    que a real; numa barra maciça o erro ia para o outro lado. Cada família
    usa a sua fórmula: circular ``J/(d/2)``, tubo retangular Bredt
    ``2·A_m·t``, barra retangular Roark ``a²b²/(3a + 1,8b)``.
    """
    familia = _familia_normalizada(perfil)
    j = float(perfil.j_mm4)
    h = float(perfil.altura_mm)
    b = float(perfil.largura_mm)
    tw = float(perfil.espessura_alma_mm)
    tf = float(perfil.espessura_mesa_mm)
    circular = "circ" in familia or "redond" in familia
    if "tubo" in familia and circular:
        return (j / (h / 2.0), "") if h > 0 else (0.0, "")
    if "tubo" in familia:
        t = min(tw, tf) if min(tw, tf) > 0 else max(tw, tf)
        if t > 0 and b > t and h > t:
            return 2.0 * (b - t) * (h - t) * t, ""
        return (0.0, "")
    if "barra" in familia and circular:
        return (j / (h / 2.0), "") if h > 0 else (0.0, "")
    if "barra" in familia:
        maior, menor = max(h, b), min(h, b)
        if menor > 0:
            return maior**2 * menor**2 / (3.0 * maior + 1.8 * menor), ""
        return (0.0, "")
    t_max = max(tw, tf)
    primeira_palavra = familia.split()[0] if familia.split() else ""
    nota = ""
    if primeira_palavra not in _FAMILIAS_ABERTAS:
        nota = (
            "Wt = J/t_máx, fórmula de perfil aberto: se este perfil for um tubo "
            "ou uma barra maciça, cadastre-o com a família 'Tubo …' ou 'Barra …' "
            "para o programa usar a fórmula certa."
        )
    return (j / t_max if t_max > 0 else 0.0), nota


# Famílias de perfil aberto de parede fina, em que τ_máx = T·t_máx/J.
_FAMILIAS_ABERTAS = frozenset(
    {"i", "w", "u", "c", "t", "hp", "hea", "heb", "hem", "ipe", "ipn", "upn", "l", "cantoneira"}
)


def _area_de_cisalhamento_em_y(perfil: Any) -> tuple[float, str]:
    """Área que resiste ao cortante paralelo às mesas (flexão em torno de y).

    O catálogo tabela a área de cisalhamento da alma (cortante em y, flexão
    em x). Na flexão em torno de y o cortante é resistido pelas **mesas**:
    usar a alma superestimava τ em cerca de três vezes nos perfis I, W e U —
    conservador, mas capaz de reprovar falsamente um membro curto com muito
    cortante. Tubos e barras são tratados pela geometria; família
    desconhecida mantém a área tabelada, com nota.
    """
    familia = _familia_normalizada(perfil)
    primeira = familia.split()[0] if familia.split() else ""
    b = float(perfil.largura_mm)
    tw = float(perfil.espessura_alma_mm)
    tf = float(perfil.espessura_mesa_mm)
    tabelada = float(perfil.area_cisalhamento_mm2)
    circular = "circ" in familia or "redond" in familia
    if "tubo" in familia and not circular:
        t = min(tw, tf) if min(tw, tf) > 0 else max(tw, tf)
        if t > 0 and b > 2 * t:
            return 2.0 * t * (b - 2.0 * t), ""
        return tabelada, ""
    if "tubo" in familia or "barra" in familia:
        return tabelada, ""
    if primeira == "t" and b > 0 and tf > 0:
        return b * tf, ""
    if primeira in _FAMILIAS_ABERTAS and b > 0 and tf > 0:
        return 2.0 * b * tf, ""
    return tabelada, (
        "Cisalhamento com a área de cisalhamento tabelada (alma), conservadora "
        "para a flexão em torno de y."
    )


def _distancias_monossimetricas(perfil: Any, eixo: str) -> tuple[float, float, str] | None:
    """(c_superior, c_inferior, nota) para T em x e U em y; ``None`` se simétrico.

    Quando o perfil traz o centroide (fábricas idealizadas e perfis
    cadastrados com ele), as distâncias saem dele — exatas. As bitolas de
    catálogo não tabelam o centroide, mas tabelam as dimensões (altura,
    largura, alma e mesa), e com elas o centroide sai da composição de
    retângulos com erro pequeno. Usar ``altura / 2`` num T subestimava a
    tensão no talão em mais de 30 % para as bitolas comuns.
    """
    familia = _familia_do_perfil(perfil)
    h = float(perfil.altura_mm)
    bf = float(perfil.largura_mm)
    tw = float(perfil.espessura_alma_mm)
    tf = float(perfil.espessura_mesa_mm)
    centroide_x = float(getattr(perfil, "centroide_x_mm", 0.0) or 0.0)
    centroide_y = float(getattr(perfil, "centroide_y_mm", 0.0) or 0.0)
    if eixo == "x" and 0.0 < centroide_y < h and abs(centroide_y - h / 2.0) > 1e-9 * h:
        return (
            h - centroide_y,
            centroide_y,
            f"Fibras medidas do centroide cadastrado (ȳ = {centroide_y:.1f} mm da base): "
            "fibra superior = topo, fibra inferior = base do perfil.",
        )
    if eixo == "y" and 0.0 < centroide_x < bf and abs(centroide_x - bf / 2.0) > 1e-9 * bf:
        return (
            bf - centroide_x,
            centroide_x,
            f"Fibras medidas do centroide cadastrado (x̄ = {centroide_x:.1f} mm da face "
            "esquerda/dorso): fibra superior = lado direito (pontas das mesas), fibra "
            "inferior = lado esquerdo (dorso).",
        )
    if familia == "T" and eixo == "x" and 0 < tf < h and 0 < tw < bf:
        # Mesa em cima, talão para baixo: centroide medido do topo da mesa.
        area_mesa, area_alma = bf * tf, tw * (h - tf)
        do_topo = (area_mesa * tf / 2.0 + area_alma * (tf + (h - tf) / 2.0)) / (
            area_mesa + area_alma
        )
        return (
            do_topo,
            h - do_topo,
            "Perfil T com a mesa para cima: fibra superior = topo da mesa, "
            f"fibra inferior = ponta do talão (centroide a {do_topo:.1f} mm do topo, "
            "estimado pela geometria idealizada).",
        )
    if familia == "U" and eixo == "y" and 0 < tw < bf and 0 < 2 * tf < h:
        # Dorso da alma de um lado, pontas das mesas do outro.
        area_alma, area_mesas = h * tw, 2.0 * (bf - tw) * tf
        do_dorso = (area_alma * tw / 2.0 + area_mesas * (tw + (bf - tw) / 2.0)) / (
            area_alma + area_mesas
        )
        return (
            bf - do_dorso,
            do_dorso,
            "Perfil U fletido em torno de y: fibra superior = pontas das mesas, "
            f"fibra inferior = dorso da alma (centroide a {do_dorso:.1f} mm do dorso, "
            "estimado pela geometria idealizada).",
        )
    return None


def secao_de_perfil_catalogo(perfil: Any, *, eixo: str = "x") -> SecaoViga:
    """Converte um :class:`core.steel_sections.PerfilAco` em :class:`SecaoViga`.

    O catálogo não tabela o momento estático ``Q``, então o cisalhamento usa
    a rota normativa ``tau = V / A_v`` com a área de cisalhamento do próprio
    catálogo, em vez de um ``Q`` inventado. Para T fletido em x e U fletido
    em y — os casos em que o centroide está longe do meio — as distâncias às
    fibras extremas são estimadas pela geometria idealizada; nos demais
    perfis monossimétricos (C enrijecido) mantém-se ``c = altura / 2``, a
    mesma convenção do catálogo em ``sx_mm3``, e a descrição sinaliza isso.
    """
    eixo = str(eixo).strip().lower()
    if eixo not in {"x", "y"}:
        raise ValueError("O eixo de flexão deve ser 'x' ou 'y'.")
    if eixo == "x":
        inercia = float(perfil.ix_mm4)
        altura = float(perfil.altura_mm)
        espessura = float(perfil.espessura_alma_mm)
    else:
        inercia = float(perfil.iy_mm4)
        altura = float(perfil.largura_mm)
        espessura = float(perfil.espessura_mesa_mm) * 2.0
    monossimetrica = _distancias_monossimetricas(perfil, eixo)
    if monossimetrica is None:
        c_superior = c_inferior = altura / 2.0
        nota = ""
    else:
        c_superior, c_inferior, nota = monossimetrica
    area_cisalhamento = float(perfil.area_cisalhamento_mm2)
    if eixo == "y":
        area_cisalhamento, nota_cisalhamento = _area_de_cisalhamento_em_y(perfil)
        if nota_cisalhamento:
            nota = (nota + " " if nota else "") + nota_cisalhamento
    modulo_torcao, nota_torcao = _modulo_de_torcao_do_perfil(perfil)
    if nota_torcao:
        nota = (nota + " " if nota else "") + nota_torcao
    return SecaoViga(
        nome=str(perfil.nome),
        area_mm2=float(perfil.area_mm2),
        inercia_mm4=inercia,
        c_superior_mm=c_superior,
        c_inferior_mm=c_inferior,
        momento_estatico_mm3=0.0,
        espessura_cisalhamento_mm=espessura,
        constante_torcao_mm4=float(perfil.j_mm4),
        modulo_torcao_mm3=modulo_torcao,
        area_cisalhamento_mm2=area_cisalhamento,
        inercia_transversal_mm4=float(perfil.iy_mm4 if eixo == "x" else perfil.ix_mm4),
        descricao=(
            f"{perfil.nome} — {perfil.descricao} (flexão em torno de {eixo})."
            + (f" {nota}" if nota else "")
        ),
    )


# ---------------------------------------------------------------------------
# Apoios, rótulas e cargas
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Apoio:
    x_mm: float
    tipo: str = "pino"
    rigidez_vertical_N_mm: float = 0.0
    rigidez_rotacional_Nmm_rad: float = 0.0
    rotulo: str = ""

    def __post_init__(self) -> None:
        _finito("x_mm", self.x_mm)
        if self.tipo not in TIPOS_APOIO:
            validos = ", ".join(sorted(TIPOS_APOIO))
            raise ValueError(f"Tipo de apoio desconhecido: {self.tipo!r}. Use um de: {validos}.")
        _nao_negativo("rigidez_vertical_N_mm", self.rigidez_vertical_N_mm)
        _nao_negativo("rigidez_rotacional_Nmm_rad", self.rigidez_rotacional_Nmm_rad)
        # Uma mola num grau já travado seria silenciosamente inútil: o
        # deslocamento é zero e a rigidez nunca entra na conta.
        if self.rigidez_vertical_N_mm > 0 and TIPOS_APOIO[self.tipo][0]:
            raise ValueError(
                f"O apoio do tipo {self.tipo!r} já impede o deslocamento vertical, "
                "então a rigidez kv não teria efeito. Use o tipo 'mola'."
            )
        if self.rigidez_rotacional_Nmm_rad > 0 and TIPOS_APOIO[self.tipo][2]:
            raise ValueError(
                f"O apoio do tipo {self.tipo!r} já impede a rotação, então a "
                "rigidez kr não teria efeito. Use o tipo 'mola'."
            )
        if self.tipo == "mola" and not (
            self.rigidez_vertical_N_mm > 0 or self.rigidez_rotacional_Nmm_rad > 0
        ):
            raise ValueError(
                "Um apoio do tipo 'mola' precisa de kv (N/mm) e/ou kr (N·mm/rad) "
                "maior que zero — sem rigidez ele não segura nada."
            )

    @property
    def restringe_vertical(self) -> bool:
        return TIPOS_APOIO[self.tipo][0]

    @property
    def restringe_horizontal(self) -> bool:
        return TIPOS_APOIO[self.tipo][1]

    @property
    def restringe_rotacao(self) -> bool:
        return TIPOS_APOIO[self.tipo][2]

    @property
    def restringe_torcao(self) -> bool:
        return TIPOS_APOIO[self.tipo][3]

    @property
    def e_elastico(self) -> bool:
        return self.rigidez_vertical_N_mm > 0 or self.rigidez_rotacional_Nmm_rad > 0


@dataclass(frozen=True, slots=True)
class Rotula:
    """Articulação interna: transmite V e N, mas libera o momento fletor."""

    x_mm: float

    def __post_init__(self) -> None:
        _finito("x_mm", self.x_mm)


@dataclass(frozen=True, slots=True)
class CargaPontual:
    x_mm: float
    fy_N: float
    caso: str = CASO_PADRAO
    rotulo: str = ""

    def __post_init__(self) -> None:
        _finito("x_mm", self.x_mm)
        _finito("fy_N", self.fy_N)


@dataclass(frozen=True, slots=True)
class MomentoConcentrado:
    x_mm: float
    mz_Nmm: float
    caso: str = CASO_PADRAO
    rotulo: str = ""

    def __post_init__(self) -> None:
        _finito("x_mm", self.x_mm)
        _finito("mz_Nmm", self.mz_Nmm)


@dataclass(frozen=True, slots=True)
class CargaDistribuida:
    x_inicial_mm: float
    x_final_mm: float
    w_inicial_N_mm: float
    w_final_N_mm: float | None = None
    caso: str = CASO_PADRAO
    rotulo: str = ""

    def __post_init__(self) -> None:
        _finito("x_inicial_mm", self.x_inicial_mm)
        _finito("x_final_mm", self.x_final_mm)
        _finito("w_inicial_N_mm", self.w_inicial_N_mm)
        if self.w_final_N_mm is not None:
            _finito("w_final_N_mm", self.w_final_N_mm)
        if self.x_final_mm <= self.x_inicial_mm:
            raise ValueError(
                "A carga distribuída precisa de x final maior que x inicial "
                f"(recebido {self.x_inicial_mm} → {self.x_final_mm})."
            )

    @property
    def w_final(self) -> float:
        return self.w_inicial_N_mm if self.w_final_N_mm is None else self.w_final_N_mm

    def intensidade_em(self, x_mm: float) -> float:
        comprimento = self.x_final_mm - self.x_inicial_mm
        fracao = (x_mm - self.x_inicial_mm) / comprimento
        return self.w_inicial_N_mm + (self.w_final - self.w_inicial_N_mm) * fracao


@dataclass(frozen=True, slots=True)
class CargaAxial:
    x_mm: float
    fx_N: float
    caso: str = CASO_PADRAO
    rotulo: str = ""

    def __post_init__(self) -> None:
        _finito("x_mm", self.x_mm)
        _finito("fx_N", self.fx_N)


@dataclass(frozen=True, slots=True)
class CargaAxialDistribuida:
    x_inicial_mm: float
    x_final_mm: float
    a_inicial_N_mm: float
    a_final_N_mm: float | None = None
    caso: str = CASO_PADRAO
    rotulo: str = ""

    def __post_init__(self) -> None:
        _finito("x_inicial_mm", self.x_inicial_mm)
        _finito("x_final_mm", self.x_final_mm)
        _finito("a_inicial_N_mm", self.a_inicial_N_mm)
        if self.a_final_N_mm is not None:
            _finito("a_final_N_mm", self.a_final_N_mm)
        if self.x_final_mm <= self.x_inicial_mm:
            raise ValueError("A carga axial distribuída precisa de x final maior que x inicial.")

    @property
    def a_final(self) -> float:
        return self.a_inicial_N_mm if self.a_final_N_mm is None else self.a_final_N_mm

    def intensidade_em(self, x_mm: float) -> float:
        comprimento = self.x_final_mm - self.x_inicial_mm
        fracao = (x_mm - self.x_inicial_mm) / comprimento
        return self.a_inicial_N_mm + (self.a_final - self.a_inicial_N_mm) * fracao


@dataclass(frozen=True, slots=True)
class Torque:
    x_mm: float
    t_Nmm: float
    caso: str = CASO_PADRAO
    rotulo: str = ""

    def __post_init__(self) -> None:
        _finito("x_mm", self.x_mm)
        _finito("t_Nmm", self.t_Nmm)


@dataclass(frozen=True, slots=True)
class Viga:
    """Modelo completo de uma barra reta (viga ou eixo)."""

    comprimento_mm: float
    secao: SecaoViga
    material: MaterialViga
    apoios: tuple[Apoio, ...] = ()
    rotulas: tuple[Rotula, ...] = ()
    cargas_pontuais: tuple[CargaPontual, ...] = ()
    momentos: tuple[MomentoConcentrado, ...] = ()
    cargas_distribuidas: tuple[CargaDistribuida, ...] = ()
    cargas_axiais: tuple[CargaAxial, ...] = ()
    cargas_axiais_distribuidas: tuple[CargaAxialDistribuida, ...] = ()
    torques: tuple[Torque, ...] = ()
    considerar_peso_proprio: bool = False
    considerar_segunda_ordem: bool = False
    divisoes_por_trecho: int = 1
    nome: str = "Viga"

    def __post_init__(self) -> None:
        _positivo("comprimento_mm", self.comprimento_mm)
        divisoes = self.divisoes_por_trecho
        if isinstance(divisoes, bool) or int(divisoes) != divisoes or int(divisoes) < 1:
            raise ValueError(
                "divisoes_por_trecho deve ser um inteiro maior ou igual a 1 "
                f"(recebido {divisoes!r})."
            )

    def com_peso_proprio(self) -> Viga:
        """Devolve uma cópia com o peso próprio já convertido em carga."""
        if not self.considerar_peso_proprio:
            return self
        peso_N_mm = (
            self.secao.area_mm2
            * 1e-6  # mm² -> m²
            * self.material.densidade_kg_m3
            * GRAVIDADE_M_S2
            / 1_000.0  # N/m -> N/mm
        )
        if peso_N_mm <= 0:
            return self
        extra = CargaDistribuida(
            x_inicial_mm=0.0,
            x_final_mm=self.comprimento_mm,
            w_inicial_N_mm=-peso_N_mm,
            rotulo="Peso próprio",
        )
        return Viga(
            comprimento_mm=self.comprimento_mm,
            secao=self.secao,
            material=self.material,
            apoios=self.apoios,
            rotulas=self.rotulas,
            cargas_pontuais=self.cargas_pontuais,
            momentos=self.momentos,
            cargas_distribuidas=(*self.cargas_distribuidas, extra),
            cargas_axiais=self.cargas_axiais,
            cargas_axiais_distribuidas=self.cargas_axiais_distribuidas,
            torques=self.torques,
            considerar_peso_proprio=False,
            considerar_segunda_ordem=self.considerar_segunda_ordem,
            divisoes_por_trecho=self.divisoes_por_trecho,
            nome=self.nome,
        )


# ---------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PontoDiagrama:
    x_mm: float
    normal_N: float
    cortante_N: float
    momento_Nmm: float
    torque_Nmm: float
    deslocamento_mm: float
    rotacao_rad: float
    deslocamento_axial_mm: float
    giro_torcao_rad: float
    tensao_axial_MPa: float
    tensao_flexao_superior_MPa: float
    tensao_flexao_inferior_MPa: float
    tensao_normal_superior_MPa: float
    tensao_normal_inferior_MPa: float
    tensao_cisalhamento_MPa: float
    tensao_torcao_MPa: float
    von_mises_MPa: float
    tresca_MPa: float
    ponto_critico: str
    sigma_critico_MPa: float = 0.0
    tau_critico_MPa: float = 0.0


@dataclass(frozen=True, slots=True)
class Reacao:
    x_mm: float
    tipo: str
    rotulo: str
    fy_N: float
    fx_N: float
    mz_Nmm: float
    mt_Nmm: float


@dataclass(frozen=True, slots=True)
class Extremo:
    grandeza: str
    valor: float
    x_mm: float
    unidade: str


@dataclass(frozen=True, slots=True)
class ResultadoViga:
    viga: Viga
    pontos: tuple[PontoDiagrama, ...]
    reacoes: tuple[Reacao, ...]
    extremos: dict[str, Extremo]
    avisos: tuple[str, ...] = ()
    grau_hiperestaticidade: int = 0
    fator_seguranca_escoamento: float | None = None
    verificacao_flecha: dict[str, float] | None = None
    fator_carga_critica: float | None = None
    segunda_ordem: bool = False
    numero_elementos: int = 0
    # Estimativa fora do plano da flexão (mesmo comprimento de flambagem,
    # inércia transversal); ``None`` quando não há compressão, quando a
    # inércia transversal é desconhecida ou quando ela é a maior das duas.
    fator_carga_critica_transversal: float | None = None

    # -- atalhos de leitura -------------------------------------------------
    @property
    def cortante_maximo_N(self) -> float:
        return self.extremos["cortante"].valor

    @property
    def momento_maximo_Nmm(self) -> float:
        return self.extremos["momento"].valor

    @property
    def flecha_maxima_mm(self) -> float:
        return self.extremos["flecha"].valor

    @property
    def von_mises_maximo_MPa(self) -> float:
        return self.extremos["von_mises"].valor

    def serie(self, atributo: str) -> tuple[tuple[float, float], ...]:
        return tuple((p.x_mm, getattr(p, atributo)) for p in self.pontos)


# ---------------------------------------------------------------------------
# Montagem da malha
# ---------------------------------------------------------------------------


def _tolerancia_de_posicao(comprimento: float) -> float:
    """Distância abaixo da qual duas posições viram o mesmo nó.

    Absoluta (1e-6 mm) para absorver arredondamento, e relativa (1e-4 do
    comprimento) para não criar um elemento minúsculo entre duas cargas
    quase coincidentes: a rigidez EI/L³ desse elemento fica bilhões de vezes
    maior que a dos vizinhos, a matriz perde o condicionamento e o solver
    acusava "mecanismo" numa viga perfeitamente estável. Fundir cargas a
    0,6 mm uma da outra numa viga de 6 m muda os braços de alavanca em 1e-4
    — nada, para uma análise de vigas.
    """
    return max(TOLERANCIA_POSICAO_MM, comprimento * FRACAO_FUSAO_DE_NOS)


def _mesmo_ponto(a: float, b: float, tolerancia: float = TOLERANCIA_POSICAO_MM) -> bool:
    return abs(a - b) <= tolerancia


def _inserir(posicoes: list[float], valor: float, tolerancia: float) -> None:
    for existente in posicoes:
        if _mesmo_ponto(existente, valor, tolerancia):
            return
    posicoes.append(valor)


def _validar_posicao(nome: str, x: float, comprimento: float, tolerancia: float) -> float:
    x = _finito(nome, x)
    if x < -tolerancia or x > comprimento + tolerancia:
        raise ValueError(
            f"{nome} = {x:.4g} mm está fora da viga (0 a {comprimento:.4g} mm)."
        )
    return min(max(x, 0.0), comprimento)


@dataclass(frozen=True, slots=True)
class _Malha:
    """Nós da malha e como ela foi refinada."""

    posicoes: list[float]
    trechos: int
    divisoes: int
    divisoes_pedidas: int
    tolerancia: float

    def no_de(self, x: float) -> int:
        for indice, posicao in enumerate(self.posicoes):
            if _mesmo_ponto(posicao, x, self.tolerancia):
                return indice
        raise ValueError(f"Posição {x:.4g} mm não corresponde a nenhum nó da malha.")

    def ajustar(self, x: float) -> float:
        """Coordenada do nó em que ``x`` cai — o modelo é "encaixado" na malha."""
        return self.posicoes[self.no_de(x)]


def _ajustar_modelo_a_malha(viga: Viga, malha: _Malha) -> Viga:
    """Cópia do modelo com toda posição movida para o nó em que ela caiu.

    Depois da fusão de nós, uma carga declarada a 0,3 mm de um apoio passa
    a agir *no* apoio; ajustar o modelo mantém a conferência de equilíbrio,
    o esquema da página e o registro coerentes com o que foi resolvido.
    """
    comprimento = viga.comprimento_mm
    tolerancia = malha.tolerancia

    def no(nome: str, x: float) -> float:
        return malha.ajustar(_validar_posicao(nome, x, comprimento, tolerancia))

    return replace(
        viga,
        apoios=tuple(replace(a, x_mm=no("posição do apoio", a.x_mm)) for a in viga.apoios),
        rotulas=tuple(replace(r, x_mm=no("posição da rótula", r.x_mm)) for r in viga.rotulas),
        cargas_pontuais=tuple(
            replace(c, x_mm=no("posição da carga pontual", c.x_mm)) for c in viga.cargas_pontuais
        ),
        momentos=tuple(replace(m, x_mm=no("posição do momento", m.x_mm)) for m in viga.momentos),
        cargas_distribuidas=tuple(
            _distribuida_ajustada(c, no("início da carga distribuída", c.x_inicial_mm), no("fim da carga distribuída", c.x_final_mm), tolerancia)
            for c in viga.cargas_distribuidas
        ),
        cargas_axiais=tuple(
            replace(c, x_mm=no("posição da carga axial", c.x_mm)) for c in viga.cargas_axiais
        ),
        cargas_axiais_distribuidas=tuple(
            _distribuida_ajustada(c, no("início da carga axial distribuída", c.x_inicial_mm), no("fim da carga axial distribuída", c.x_final_mm), tolerancia)
            for c in viga.cargas_axiais_distribuidas
        ),
        torques=tuple(replace(t, x_mm=no("posição do torque", t.x_mm)) for t in viga.torques),
    )


def _distribuida_ajustada(carga: Any, inicio: float, fim: float, tolerancia: float) -> Any:
    """Distribuída com os extremos nos nós; recusa a que caberia num único nó."""
    if fim <= inicio:
        raise ValueError(
            f"A carga distribuída de x = {carga.x_inicial_mm:.4g} mm a "
            f"{carga.x_final_mm:.4g} mm é mais curta que a distância mínima entre "
            f"nós ({tolerancia:.3g} mm, 0,01 % do comprimento). Troque-a por uma "
            "carga pontual com a mesma resultante."
        )
    return replace(carga, x_inicial_mm=inicio, x_final_mm=fim)


def _posicoes_nodais(viga: Viga) -> _Malha:
    comprimento = viga.comprimento_mm
    tolerancia = _tolerancia_de_posicao(comprimento)
    posicoes: list[float] = [0.0, comprimento]

    def inserir(nome: str, x: float) -> None:
        _inserir(posicoes, _validar_posicao(nome, x, comprimento, tolerancia), tolerancia)

    for apoio in viga.apoios:
        inserir("posição do apoio", apoio.x_mm)
    for rotula in viga.rotulas:
        inserir("posição da rótula", rotula.x_mm)
    for pontual in viga.cargas_pontuais:
        inserir("posição da carga pontual", pontual.x_mm)
    for momento in viga.momentos:
        inserir("posição do momento", momento.x_mm)
    for axial in viga.cargas_axiais:
        inserir("posição da carga axial", axial.x_mm)
    for torque in viga.torques:
        inserir("posição do torque", torque.x_mm)
    for distribuida in viga.cargas_distribuidas:
        inserir("início da carga distribuída", distribuida.x_inicial_mm)
        inserir("fim da carga distribuída", distribuida.x_final_mm)
    for axial_distribuida in viga.cargas_axiais_distribuidas:
        inserir("início da carga axial distribuída", axial_distribuida.x_inicial_mm)
        inserir("fim da carga axial distribuída", axial_distribuida.x_final_mm)
    posicoes.sort()

    divisoes = max(1, int(viga.divisoes_por_trecho))
    pedidas = divisoes
    trechos = len(posicoes) - 1
    tem_axial = bool(viga.cargas_axiais or viga.cargas_axiais_distribuidas)
    if viga.considerar_segunda_ordem or tem_axial:
        # A rigidez geométrica converge com o refino: com um elemento por
        # trecho o fator de carga crítica de uma coluna biapoiada sai 21,6%
        # alto (12EI/L² em vez de π²EI/L²) — e alto demais é justamente o
        # lado inseguro. Refinar não altera V, M nem a flecha de primeira
        # ordem, que são exatos em qualquer malha, então o custo é só tempo.
        # Num modelo com centenas de trechos o refino automático se limita
        # ao teto da malha, em vez de recusar a análise; analisar_viga avisa.
        pedidas = max(divisoes, DIVISOES_SEGUNDA_ORDEM)
        automatico = max(1, min(DIVISOES_SEGUNDA_ORDEM, ELEMENTOS_MAXIMOS // max(trechos, 1)))
        divisoes = max(divisoes, automatico)

    # Sem refino, um elemento por trecho: a solução nodal é exata. Com
    # refino, a malha mira um comprimento de elemento uniforme, L/(trechos ×
    # divisões), com pelo menos um elemento por trecho. Dividir cada trecho
    # em n partes iguais — como antes — transformava um trecho curto (uma
    # carga a 20 mm do apoio) em oito lascas minúsculas ao lado de elementos
    # de metros, e o mau condicionamento voltava pela porta dos fundos.
    alvo = comprimento / max(1, trechos * divisoes)
    refinadas: list[float] = []
    n_elementos = 0
    for inicio, fim in zip(posicoes, posicoes[1:], strict=False):
        partes = max(1, round((fim - inicio) / alvo)) if divisoes > 1 else 1
        refinadas.append(inicio)
        refinadas.extend(inicio + (fim - inicio) * indice / partes for indice in range(1, partes))
        n_elementos += partes
    refinadas.append(posicoes[-1])
    if n_elementos > ELEMENTOS_MAXIMOS:
        raise ValueError(
            f"A malha teria {n_elementos} elementos ({trechos} trecho(s) com até "
            f"{divisoes} divisões), acima do máximo de {ELEMENTOS_MAXIMOS}. Reduza "
            "`divisoes`: a solução de primeira ordem é exata em qualquer malha e a "
            "segunda ordem já converge com 8 a 32 divisões por trecho."
        )
    return _Malha(
        posicoes=refinadas,
        trechos=trechos,
        divisoes=divisoes,
        divisoes_pedidas=pedidas,
        tolerancia=tolerancia,
    )


def _carga_no_elemento(
    cargas: Sequence[CargaDistribuida] | Sequence[CargaAxialDistribuida],
    x_i: float,
    x_j: float,
) -> tuple[float, float]:
    """Soma as intensidades das distribuídas nos dois extremos do elemento."""
    meio = 0.5 * (x_i + x_j)
    w_i = w_j = 0.0
    for carga in cargas:
        if carga.x_inicial_mm - TOLERANCIA_POSICAO_MM <= meio <= carga.x_final_mm + TOLERANCIA_POSICAO_MM:
            w_i += carga.intensidade_em(x_i)
            w_j += carga.intensidade_em(x_j)
    return w_i, w_j


# ---------------------------------------------------------------------------
# Matrizes elementares
# ---------------------------------------------------------------------------


def _rigidez_flexao(ei: float, l: float) -> np.ndarray:
    return (ei / l**3) * np.array(
        [
            [12.0, 6.0 * l, -12.0, 6.0 * l],
            [6.0 * l, 4.0 * l**2, -6.0 * l, 2.0 * l**2],
            [-12.0, -6.0 * l, 12.0, -6.0 * l],
            [6.0 * l, 2.0 * l**2, -6.0 * l, 4.0 * l**2],
        ],
        dtype=float,
    )


def _rigidez_geometrica(normal: float, l: float) -> np.ndarray:
    """Rigidez geométrica consistente de um elemento sob esforço normal.

    ``normal`` é positivo em tração: tração enrijece a barra à flexão e
    compressão a amolece. Somada à rigidez elástica, é o que produz o efeito
    de segunda ordem (P–Δ e P–δ) numa análise ainda linear — a flecha cresce
    porque a compressão reduz a rigidez, não porque a geometria foi
    atualizada.
    """
    return (normal / (30.0 * l)) * np.array(
        [
            [36.0, 3.0 * l, -36.0, 3.0 * l],
            [3.0 * l, 4.0 * l**2, -3.0 * l, -(l**2)],
            [-36.0, -3.0 * l, 36.0, -3.0 * l],
            [3.0 * l, -(l**2), -3.0 * l, 4.0 * l**2],
        ],
        dtype=float,
    )


def _cargas_equivalentes_flexao(w_i: float, w_j: float, l: float) -> np.ndarray:
    """Vetor de engastamento perfeito de uma distribuída linear (positiva ↑)."""
    return np.array(
        [
            l * (7.0 * w_i + 3.0 * w_j) / 20.0,
            l**2 * (3.0 * w_i + 2.0 * w_j) / 60.0,
            l * (3.0 * w_i + 7.0 * w_j) / 20.0,
            -(l**2) * (2.0 * w_i + 3.0 * w_j) / 60.0,
        ],
        dtype=float,
    )


def _cargas_equivalentes_axial(a_i: float, a_j: float, l: float) -> np.ndarray:
    return np.array(
        [l * (2.0 * a_i + a_j) / 6.0, l * (a_i + 2.0 * a_j) / 6.0],
        dtype=float,
    )


# ---------------------------------------------------------------------------
# Solver principal
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _Elemento:
    indice: int
    no_i: int
    no_j: int
    x_i: float
    x_j: float
    comprimento: float
    w_i: float
    w_j: float
    a_i: float
    a_j: float
    dofs_flexao: tuple[int, int, int, int] = (0, 0, 0, 0)
    dofs_axial: tuple[int, int] = (0, 0)
    dofs_torcao: tuple[int, int] = (0, 0)
    # ``esforcos_flexao`` vem só da rigidez elástica (K_e·u − F_eq): são os
    # esforços de extremidade que, integrados com a teoria de primeira
    # ordem, reproduzem exatamente v_j e θ_j — por isso geram a linha
    # elástica. ``esforcos_equilibrio`` inclui a parcela geométrica
    # (K_g·u) e é o conjunto que está em equilíbrio com os nós na
    # configuração deformada — por isso gera V(x) e M(x). Sem segunda
    # ordem os dois são o mesmo vetor.
    esforcos_flexao: np.ndarray = field(default_factory=lambda: np.zeros(4))
    esforcos_equilibrio: np.ndarray = field(default_factory=lambda: np.zeros(4))
    normal_geometrico: float = 0.0
    esforco_axial_i: float = 0.0
    esforco_torcao_i: float = 0.0
    v_i: float = 0.0
    theta_i: float = 0.0
    u_i: float = 0.0
    phi_i: float = 0.0


def _normal_medio(elemento: _Elemento) -> float:
    """Esforço normal médio do elemento (positivo em tração)."""
    n_inicial = -elemento.esforco_axial_i
    n_final = n_inicial - (
        elemento.a_i * elemento.comprimento
        + (elemento.a_j - elemento.a_i) * elemento.comprimento / 2.0
    )
    return 0.5 * (n_inicial + n_final)


def _escala_de_jacobi(matriz: np.ndarray) -> np.ndarray:
    """``1/√|diagonal|`` — leva a matriz a diagonal unitária.

    Translação (N/mm) e rotação (N·mm/rad) diferem por um fator L² só por
    causa das unidades; sem o escalonamento, o teste de posto e o solver
    enxergam um mau condicionamento que não é da estrutura. O escalonamento
    simétrico ``D K D`` preserva a simetria e os autovalores generalizados.
    """
    diagonal = np.abs(np.diag(matriz))
    return 1.0 / np.sqrt(np.where(diagonal > 0, diagonal, 1.0))


def _fator_carga_critica(
    k_elastica: np.ndarray, k_geometrica: np.ndarray, restritos: set[int]
) -> float | None:
    """Multiplicador das cargas axiais que leva o modelo à flambagem.

    Resolve ``K_e φ = λ (−K_g) φ`` nos graus livres. Um fator de 3,2 quer
    dizer que as cargas **axiais** poderiam ser multiplicadas por 3,2 antes
    da instabilidade elástica. Devolve ``None`` quando não há compressão —
    aí não existe carga crítica a reportar.

    O problema é reduzido à forma simétrica ``L⁻¹(−K_g)L⁻ᵀ ψ = μ ψ`` pela
    fatoração de Cholesky ``K_e = L Lᵀ`` (``λ = 1/μ``): os autovalores saem
    reais por construção, sem depender de um filtro de parte imaginária
    que, na forma não simétrica ``K_e⁻¹(−K_g)``, descartava modos por ruído.
    """
    if not np.any(k_geometrica):
        return None
    total = k_elastica.shape[0]
    livres = [i for i in range(total) if i not in restritos]
    if not livres:
        return None
    kff = k_elastica[np.ix_(livres, livres)]
    kgff = k_geometrica[np.ix_(livres, livres)]
    escala = _escala_de_jacobi(kff)
    k_escalada = escala[:, None] * kff * escala[None, :]
    kg_escalada = escala[:, None] * kgff * escala[None, :]
    try:
        cholesky = np.linalg.cholesky(k_escalada)
        # C = L⁻¹ (−K_g) L⁻ᵀ, montada em dois sistemas triangulares.
        parcial = np.linalg.solve(cholesky, -kg_escalada)
        simetrica = np.linalg.solve(cholesky, parcial.T)
    except np.linalg.LinAlgError:
        # K_e não é definida positiva: o modelo é um mecanismo, e o erro
        # explicativo sai do solver de flexão logo em seguida.
        return None
    simetrica = 0.5 * (simetrica + simetrica.T)
    autovalores = np.linalg.eigvalsh(simetrica)
    maior = float(autovalores[-1])
    limiar = 1e-12 * max(1.0, float(np.abs(autovalores).max()))
    if maior <= limiar:
        return None
    return 1.0 / maior


def _resolver_sistema(
    k: np.ndarray,
    f: np.ndarray,
    restritos: set[int],
    contexto: str,
) -> tuple[np.ndarray, np.ndarray]:
    total = k.shape[0]
    livres = [i for i in range(total) if i not in restritos]
    deslocamentos = np.zeros(total)
    if livres:
        kff = k[np.ix_(livres, livres)]
        escala = _escala_de_jacobi(kff)
        k_escalada = escala[:, None] * kff * escala[None, :]
        # Na matriz escalonada um mecanismo aparece como autovalor na casa
        # de 1e-17 do maior (ruído do épsilon da máquina), enquanto o modo
        # mais flexível de uma barra estável decai com n⁴ e ainda está em
        # 1e-13 com 2 000 elementos num vão. O corte em 1e-14 separa os dois
        # com folga de três ordens de grandeza para cada lado. A matriz é
        # simétrica, então os autovalores (em módulo) são os valores
        # singulares — e ``eigvalsh`` custa um quarto do SVD.
        k_escalada = 0.5 * (k_escalada + k_escalada.T)
        autovalores = np.abs(np.linalg.eigvalsh(k_escalada))
        posto = int(np.count_nonzero(autovalores > 1e-14 * float(autovalores.max())))
        if posto < len(livres):
            mecanismos = len(livres) - posto
            raise ValueError(
                f"O modelo é instável em {contexto}: há {mecanismos} movimento(s) de corpo "
                "rígido ou mecanismo(s) sem restrição. Revise os apoios (e as rótulas "
                "internas, que não podem deixar um trecho isolado sem apoio)."
            )
        try:
            # (D K D)(D⁻¹u) = D f  →  u = D · solve(D K D, D f)
            deslocamentos[livres] = escala * np.linalg.solve(k_escalada, escala * f[livres])
        except np.linalg.LinAlgError as erro:  # pragma: no cover - proteção extra
            raise ValueError(
                f"Não foi possível resolver o sistema de {contexto}: matriz singular."
            ) from erro
    reacoes = k @ deslocamentos - f
    return deslocamentos, reacoes


def _avisos_de_material(material: MaterialViga) -> list[str]:
    """Faixas físicas de E, G e Sy: fora delas o erro quase sempre é de unidade.

    São avisos, não erros — madeira, polímeros e ligas especiais existem —,
    mas E em MPa digitado como GPa (mil vezes maior) ou G maior que E/2
    (coeficiente de Poisson negativo) não acontecem em material nenhum.
    """
    avisos: list[str] = []
    e_gpa = material.modulo_elasticidade_MPa / 1_000.0
    g_gpa = material.modulo_cisalhamento_MPa / 1_000.0
    if not 0.5 <= e_gpa <= 1_000.0:
        avisos.append(
            f"E = {e_gpa:.4g} GPa está fora da faixa de qualquer material de "
            "engenharia (0,5 a 1 000 GPa). Confira as unidades: o modelo espera E em "
            "GPa (aço ≈ 200)."
        )
    if g_gpa > 0.5 * e_gpa * (1.0 + 1e-9):
        avisos.append(
            f"G = {g_gpa:.4g} GPa é maior que E/2 = {0.5 * e_gpa:.4g} GPa, o que "
            "corresponde a coeficiente de Poisson negativo. Para metais G ≈ E/2,6; "
            "confira as unidades de E e G."
        )
    if material.escoamento_MPa and material.escoamento_MPa > 0.05 * material.modulo_elasticidade_MPa:
        avisos.append(
            f"Sy = {material.escoamento_MPa:.4g} MPa corresponde a deformação de "
            f"escoamento acima de 5 % (Sy/E = {material.escoamento_MPa / material.modulo_elasticidade_MPa:.3g}), "
            "que nenhum material estrutural tem. Confira as unidades: Sy em MPa e E em GPa."
        )
    return avisos


def analisar_viga(viga: Viga, *, pontos_por_elemento: int = 61) -> ResultadoViga:
    """Resolve a viga e devolve diagramas, reações, tensões e extremos.

    ``pontos_por_elemento`` é um teto por elemento: em malhas grandes a
    amostragem é reduzida para o total ficar perto de
    :data:`PONTOS_TOTAIS_ALVO`, sem nunca cair abaixo de 3 pontos por
    elemento. Os extremos não dependem disso (as raízes de V, M e θ entram
    sempre); só a densidade do traçado muda.
    """
    if pontos_por_elemento < 3:
        raise ValueError("pontos_por_elemento deve ser pelo menos 3.")

    viga = viga.com_peso_proprio()
    secao, material = viga.secao, viga.material
    avisos: list[str] = _avisos_de_material(material)

    if not viga.apoios:
        raise ValueError("Informe pelo menos um apoio — sem apoio a viga não tem equilíbrio.")

    malha = _posicoes_nodais(viga)
    # Daqui em diante toda posição do modelo coincide exatamente com um nó:
    # o que a fusão de nós aproximou fica visível no resultado, e as buscas
    # por nó abaixo não dependem mais de tolerância.
    viga = _ajustar_modelo_a_malha(viga, malha)
    posicoes = malha.posicoes
    no_de = malha.no_de
    n_nos = len(posicoes)
    if n_nos < 2:
        raise ValueError("A viga precisa de pelo menos dois nós.")
    n_elementos = n_nos - 1
    amostras_por_elemento = max(
        3, min(pontos_por_elemento, PONTOS_TOTAIS_ALVO // n_elementos)
    )
    if malha.divisoes_pedidas > malha.divisoes:
        avisos.append(
            f"Com {malha.trechos} trechos, a malha ficou limitada a {malha.divisoes} "
            f"divisão(ões) por trecho (máximo de {ELEMENTOS_MAXIMOS} elementos) em vez "
            f"das {malha.divisoes_pedidas} que a segunda ordem pede. O fator de carga "
            "crítica pode sair alguns por cento alto; V, M e a flecha de primeira ordem "
            "não são afetados."
        )

    # -- rótulas -----------------------------------------------------------
    nos_rotula: set[int] = set()
    for rotula in viga.rotulas:
        x = rotula.x_mm
        indice = no_de(x)
        if indice in (0, n_nos - 1):
            raise ValueError(
                f"A rótula em x = {x:.4g} mm coincide com a extremidade da viga. "
                "Numa extremidade a rotação já é livre, a menos que haja engaste — "
                "use um apoio do tipo rolete ou pino."
            )
        nos_rotula.add(indice)

    # -- apoios ------------------------------------------------------------
    apoios_por_no: dict[int, Apoio] = {}
    for apoio in viga.apoios:
        x = apoio.x_mm
        indice = no_de(x)
        if indice in apoios_por_no:
            raise ValueError(f"Há mais de um apoio em x = {x:.4g} mm.")
        if indice in nos_rotula and apoio.restringe_rotacao:
            raise ValueError(
                f"Em x = {x:.4g} mm há uma rótula e um apoio que impede a rotação. "
                "Escolha um dos dois: a rótula libera exatamente o que o engaste trava."
            )
        if indice in nos_rotula and apoio.rigidez_rotacional_Nmm_rad > 0:
            # Na rótula há duas rotações (uma de cada lado); uma mola kr
            # "para o solo" teria de escolher um lado em silêncio, e uma
            # ligação semirrígida (mola entre os dois lados) é outro modelo.
            raise ValueError(
                f"Em x = {x:.4g} mm há uma rótula e um apoio com rigidez rotacional kr. "
                "A rótula desconecta as rotações dos dois lados, então não há um único "
                "giro para a mola reagir. Use kv apenas, ou retire a rótula."
            )
        apoios_por_no[indice] = apoio

    # -- graus de liberdade -------------------------------------------------
    dof_v = list(range(0, 2 * n_nos, 2))
    dof_theta_esq: list[int] = []
    dof_theta_dir: list[int] = []
    proximo = 2 * n_nos
    for indice in range(n_nos):
        base = 2 * indice + 1
        dof_theta_esq.append(base)
        if indice in nos_rotula:
            dof_theta_dir.append(proximo)
            proximo += 1
        else:
            dof_theta_dir.append(base)
    n_dof_flexao = proximo

    # -- elementos ----------------------------------------------------------
    elementos: list[_Elemento] = []
    for indice in range(n_nos - 1):
        x_i, x_j = posicoes[indice], posicoes[indice + 1]
        l = x_j - x_i
        if l <= TOLERANCIA_POSICAO_MM:
            raise ValueError(f"Elemento de comprimento nulo em x = {x_i:.4g} mm.")
        w_i, w_j = _carga_no_elemento(viga.cargas_distribuidas, x_i, x_j)
        a_i, a_j = _carga_no_elemento(viga.cargas_axiais_distribuidas, x_i, x_j)
        elementos.append(
            _Elemento(
                indice=indice,
                no_i=indice,
                no_j=indice + 1,
                x_i=x_i,
                x_j=x_j,
                comprimento=l,
                w_i=w_i,
                w_j=w_j,
                a_i=a_i,
                a_j=a_j,
                dofs_flexao=(
                    dof_v[indice],
                    dof_theta_dir[indice],
                    dof_v[indice + 1],
                    dof_theta_esq[indice + 1],
                ),
                dofs_axial=(indice, indice + 1),
                dofs_torcao=(indice, indice + 1),
            )
        )

    ei = material.modulo_elasticidade_MPa * secao.inercia_mm4
    ea = material.modulo_elasticidade_MPa * secao.area_mm2
    gj = material.modulo_cisalhamento_MPa * secao.constante_torcao_mm4

    # O esforço normal é resolvido primeiro porque a rigidez geométrica da
    # flexão depende dele. Neste modelo o axial não depende da flecha, então
    # uma única passagem basta — não há iteração a fazer.
    # -- sistema axial -------------------------------------------------------
    k_axial = np.zeros((n_nos, n_nos))
    f_axial = np.zeros(n_nos)
    for elemento in elementos:
        dofs = list(elemento.dofs_axial)
        rigidez = ea / elemento.comprimento
        k_axial[np.ix_(dofs, dofs)] += rigidez * np.array([[1.0, -1.0], [-1.0, 1.0]])
        f_axial[dofs] += _cargas_equivalentes_axial(elemento.a_i, elemento.a_j, elemento.comprimento)
    for axial in viga.cargas_axiais:
        indice = no_de(axial.x_mm)
        f_axial[indice] += axial.fx_N

    restritos_axial = {
        indice for indice, apoio in apoios_por_no.items() if apoio.restringe_horizontal
    }
    if not restritos_axial:
        resultante = float(np.sum(f_axial))
        if abs(resultante) > 1e-6 * max(1.0, float(np.abs(f_axial).max(initial=0.0))):
            raise ValueError(
                "Há carga axial resultante mas nenhum apoio impede o deslocamento "
                "horizontal. Use um apoio do tipo pino, engaste ou trava axial."
            )
        ancora = min(apoios_por_no) if apoios_por_no else 0
        restritos_axial = {ancora}
        tem_axial = any(abs(item.fx_N) > 0 for item in viga.cargas_axiais)
        if tem_axial or viga.cargas_axiais_distribuidas:
            avisos.append(
                f"Nenhum apoio trava o eixo x: o deslocamento axial foi fixado em "
                f"x = {posicoes[ancora]:.4g} mm apenas como referência. Os esforços "
                "normais são autoequilibrados e não dependem dessa escolha."
            )

    deslocamentos_axiais, reacoes_axiais = _resolver_sistema(
        k_axial, f_axial, restritos_axial, "esforço axial"
    )

    # O esforço normal de cada elemento sai já aqui porque a rigidez
    # geométrica da flexão precisa dele antes da montagem.
    for elemento in elementos:
        dofs_axial = list(elemento.dofs_axial)
        u_axial = deslocamentos_axiais[dofs_axial]
        rigidez_axial = ea / elemento.comprimento
        forcas_axiais = rigidez_axial * np.array(
            [u_axial[0] - u_axial[1], u_axial[1] - u_axial[0]]
        ) - _cargas_equivalentes_axial(elemento.a_i, elemento.a_j, elemento.comprimento)
        elemento.esforco_axial_i = float(forcas_axiais[0])
        elemento.u_i = float(u_axial[0])

    # -- sistema de flexão ---------------------------------------------------
    k_flexao = np.zeros((n_dof_flexao, n_dof_flexao))
    k_geometrica = np.zeros((n_dof_flexao, n_dof_flexao))
    f_flexao = np.zeros(n_dof_flexao)
    for elemento in elementos:
        dofs = list(elemento.dofs_flexao)
        k_flexao[np.ix_(dofs, dofs)] += _rigidez_flexao(ei, elemento.comprimento)
        # Esforço normal médio do elemento, já disponível da solução axial.
        normal_medio = _normal_medio(elemento)
        if normal_medio != 0.0:
            k_geometrica[np.ix_(dofs, dofs)] += _rigidez_geometrica(
                normal_medio, elemento.comprimento
            )
        f_flexao[dofs] += _cargas_equivalentes_flexao(
            elemento.w_i, elemento.w_j, elemento.comprimento
        )
    for pontual in viga.cargas_pontuais:
        indice = no_de(pontual.x_mm)
        f_flexao[dof_v[indice]] += pontual.fy_N
    for momento in viga.momentos:
        indice = no_de(momento.x_mm)
        # Num nó com rótula o momento aplicado não tem trecho definido para
        # entrar; recusar é melhor do que escolher um lado silenciosamente.
        if indice in nos_rotula:
            raise ValueError(
                f"Há um momento concentrado exatamente sobre a rótula em "
                f"x = {momento.x_mm:.4g} mm. Desloque um dos dois."
            )
        f_flexao[dof_theta_esq[indice]] += momento.mz_Nmm

    restritos_flexao: set[int] = set()
    for indice, apoio in apoios_por_no.items():
        if apoio.restringe_vertical:
            restritos_flexao.add(dof_v[indice])
        if apoio.restringe_rotacao:
            restritos_flexao.add(dof_theta_esq[indice])
        if apoio.rigidez_vertical_N_mm > 0:
            k_flexao[dof_v[indice], dof_v[indice]] += apoio.rigidez_vertical_N_mm
        if apoio.rigidez_rotacional_Nmm_rad > 0:
            k_flexao[dof_theta_esq[indice], dof_theta_esq[indice]] += apoio.rigidez_rotacional_Nmm_rad

    fator_critico = _fator_carga_critica(k_flexao, k_geometrica, restritos_flexao)
    if viga.considerar_segunda_ordem:
        if fator_critico is not None and fator_critico <= 1.0:
            raise ValueError(
                "A compressão aplicada atinge ou ultrapassa a carga crítica de "
                f"flambagem do modelo (fator de carga crítica = {fator_critico:.3f}). "
                "A análise de segunda ordem não tem solução estável aqui: reduza a "
                "compressão, aumente a inércia ou reduza o comprimento destravado."
            )
        k_flexao_efetiva = k_flexao + k_geometrica
    else:
        k_flexao_efetiva = k_flexao

    deslocamentos_flexao, reacoes_flexao = _resolver_sistema(
        k_flexao_efetiva, f_flexao, restritos_flexao, "flexão (translação vertical / rotação)"
    )

    # -- sistema de torção ---------------------------------------------------
    tem_torque = any(abs(t.t_Nmm) > 0 for t in viga.torques)
    if gj <= 0 and tem_torque:
        raise ValueError(
            "A seção informada tem rigidez à torção nula (G·J = 0); não é possível "
            "analisar torques."
        )
    if tem_torque and secao.modulo_torcao_mm3 <= 0:
        raise ValueError(
            "Há torque aplicado, mas a seção não tem módulo de torção Wt. Sem ele "
            "a tensão de torção sairia zero sem aviso — informe Wt na seção."
        )
    k_torcao = np.zeros((n_nos, n_nos))
    f_torcao = np.zeros(n_nos)
    if gj > 0:
        for elemento in elementos:
            dofs = list(elemento.dofs_torcao)
            rigidez = gj / elemento.comprimento
            k_torcao[np.ix_(dofs, dofs)] += rigidez * np.array([[1.0, -1.0], [-1.0, 1.0]])
    for torque in viga.torques:
        indice = no_de(torque.x_mm)
        f_torcao[indice] += torque.t_Nmm

    restritos_torcao = {
        indice for indice, apoio in apoios_por_no.items() if apoio.restringe_torcao
    }
    if gj <= 0:
        deslocamentos_torcao = np.zeros(n_nos)
        reacoes_torcao = np.zeros(n_nos)
    else:
        if not restritos_torcao:
            resultante = float(np.sum(f_torcao))
            if abs(resultante) > 1e-6 * max(1.0, float(np.abs(f_torcao).max(initial=0.0))):
                raise ValueError(
                    "Há torque resultante mas nenhum apoio impede o giro em torno do "
                    "eixo da barra. Use um apoio do tipo pino ou engaste."
                )
            restritos_torcao = {min(apoios_por_no) if apoios_por_no else 0}
            if tem_torque:
                avisos.append(
                    "Nenhum apoio trava a torção: o giro foi fixado no primeiro apoio "
                    "apenas como referência."
                )
        deslocamentos_torcao, reacoes_torcao = _resolver_sistema(
            k_torcao, f_torcao, restritos_torcao, "torção"
        )

    # -- esforços de extremidade por elemento --------------------------------
    for elemento in elementos:
        dofs = list(elemento.dofs_flexao)
        u_local = deslocamentos_flexao[dofs]
        elemento.esforcos_flexao = (
            _rigidez_flexao(ei, elemento.comprimento) @ u_local
            - _cargas_equivalentes_flexao(elemento.w_i, elemento.w_j, elemento.comprimento)
        )
        elemento.esforcos_equilibrio = elemento.esforcos_flexao
        if viga.considerar_segunda_ordem:
            # O mesmo N médio que entrou em K_g: só assim os esforços de
            # extremidade fecham o equilíbrio nodal na configuração deformada
            # e M(x) sai contínuo de um elemento para o outro.
            elemento.normal_geometrico = _normal_medio(elemento)
            elemento.esforcos_equilibrio = elemento.esforcos_flexao + (
                _rigidez_geometrica(elemento.normal_geometrico, elemento.comprimento)
                @ u_local
            )
        elemento.v_i = float(u_local[0])
        elemento.theta_i = float(u_local[1])

        if gj > 0:
            dofs_torcao = list(elemento.dofs_torcao)
            u_torcao = deslocamentos_torcao[dofs_torcao]
            rigidez_torcao = gj / elemento.comprimento
            elemento.esforco_torcao_i = float(rigidez_torcao * (u_torcao[1] - u_torcao[0]))
            elemento.phi_i = float(u_torcao[0])

    # -- amostragem dos diagramas -------------------------------------------
    pontos: list[PontoDiagrama] = []
    for elemento in elementos:
        for x_local in _amostras(elemento, amostras_por_elemento, ei):
            pontos.append(
                _ponto_diagrama(elemento, x_local, viga, ei, ea, gj)
            )
    pontos.sort(key=lambda ponto: ponto.x_mm)

    # -- reações --------------------------------------------------------------
    reacoes: list[Reacao] = []
    for indice in sorted(apoios_por_no):
        apoio = apoios_por_no[indice]
        fy = float(reacoes_flexao[dof_v[indice]]) if apoio.restringe_vertical else 0.0
        if apoio.rigidez_vertical_N_mm > 0:
            # A mola reage contra o deslocamento: F = -k u.
            fy -= float(apoio.rigidez_vertical_N_mm * deslocamentos_flexao[dof_v[indice]])
        mz = 0.0
        if apoio.restringe_rotacao:
            # Um nó com rótula nunca chega aqui: apoio que trava rotação
            # sobre rótula é recusado acima, então há um único grau.
            mz = float(reacoes_flexao[dof_theta_esq[indice]])
        if apoio.rigidez_rotacional_Nmm_rad > 0:
            mz -= float(
                apoio.rigidez_rotacional_Nmm_rad * deslocamentos_flexao[dof_theta_esq[indice]]
            )
        fx = float(reacoes_axiais[indice]) if apoio.restringe_horizontal else 0.0
        mt = float(reacoes_torcao[indice]) if apoio.restringe_torcao and gj > 0 else 0.0
        reacoes.append(
            Reacao(
                x_mm=posicoes[indice],
                tipo=apoio.tipo,
                rotulo=apoio.rotulo or f"{apoio.tipo.capitalize()} em x = {posicoes[indice] / 1000:.3g} m",
                fy_N=fy,
                fx_N=fx,
                mz_Nmm=mz,
                mt_Nmm=mt,
            )
        )

    if fator_critico is not None and not viga.considerar_segunda_ordem:
        if fator_critico <= 1.0:
            avisos.append(
                "A compressão aplicada ultrapassa a carga crítica de flambagem "
                f"elástica deste modelo (fator de carga crítica = {fator_critico:.3f}): "
                "a barra flamba antes de chegar a essa carga, e os diagramas de "
                "primeira ordem abaixo não representam a resposta real. Reduza a "
                "compressão, aumente a inércia ou reduza o comprimento destravado."
            )
        elif fator_critico < 10.0:
            avisos.append(
                f"A compressão atinge 1/{fator_critico:.1f} da carga crítica de "
                "flambagem elástica deste modelo. Com essa ordem de grandeza, a "
                "flecha real é maior que a calculada: ligue a análise de segunda "
                "ordem para incluir o efeito P–Δ."
            )

    # O modelo é plano: a carga crítica acima é a da flambagem no plano da
    # flexão. Uma barra comprimida flamba em torno do eixo de MENOR inércia,
    # e um perfil I fletido em x tem Iy dez vezes menor que Ix. Com o mesmo
    # comprimento de flambagem nos dois planos, a carga crítica escala com a
    # inércia — é a estimativa que se faz à mão, e é o que se reporta aqui.
    fator_transversal: float | None = None
    if (
        fator_critico is not None
        and secao.inercia_transversal_mm4 > 0
        and secao.inercia_transversal_mm4 < secao.inercia_mm4
    ):
        fator_transversal = fator_critico * secao.inercia_transversal_mm4 / secao.inercia_mm4
        # Mesmo limiar do aviso no plano: com folga de dez vezes não há o
        # que avisar, e o número continua disponível no resultado.
        if fator_transversal < 10.0:
            avisos.append(
                f"Fora do plano da flexão a seção tem inércia menor (I⊥ = "
                f"{secao.inercia_transversal_mm4:.4g} mm⁴ contra I = {secao.inercia_mm4:.4g} mm⁴): "
                "se a barra não tiver travamento lateral, o fator de carga crítica "
                f"cai de {fator_critico:.2f} para cerca de {fator_transversal:.2f} "
                "(mesmo comprimento de flambagem nos dois planos). "
                + (
                    "A compressão já supera essa carga crítica transversal."
                    if fator_transversal <= 1.0
                    else "Confira a flambagem em torno do eixo fraco em Flambagem de colunas."
                )
            )

    extremos = _calcular_extremos(pontos)
    grau = _grau_hiperestaticidade(apoios_por_no.values(), len(nos_rotula))

    fator_seguranca = None
    if material.escoamento_MPa:
        maximo = extremos["von_mises"].valor
        fator_seguranca = (
            math.inf if maximo <= 0 else material.escoamento_MPa / maximo
        )

    return ResultadoViga(
        viga=viga,
        pontos=tuple(pontos),
        reacoes=tuple(reacoes),
        extremos=extremos,
        avisos=tuple(avisos),
        grau_hiperestaticidade=grau,
        fator_seguranca_escoamento=fator_seguranca,
        fator_carga_critica=fator_critico,
        segunda_ordem=viga.considerar_segunda_ordem,
        numero_elementos=n_elementos,
        fator_carga_critica_transversal=fator_transversal,
    )


def _amostras(elemento: _Elemento, quantidade: int, ei: float) -> list[float]:
    """Pontos locais do elemento, incluindo raízes de V, M e θ.

    Incluir as raízes garante que o momento máximo (V = 0), a flecha máxima
    (θ = 0) e a rotação máxima (M = 0, pois dθ/dx = M/EI) caiam exatamente
    sobre uma amostra, em vez de dependerem da densidade da malha.
    """
    l = elemento.comprimento
    valores: list[float] = [float(item) for item in np.linspace(0.0, l, quantidade)]
    v_i = float(elemento.esforcos_flexao[0])
    m_i = float(elemento.esforcos_flexao[1])
    q_i = float(elemento.esforcos_equilibrio[0])
    mq_i = float(elemento.esforcos_equilibrio[1])
    inclinacao = (elemento.w_j - elemento.w_i) / l
    # Sem segunda ordem N̄ = 0: V volta à parábola clássica e M à cúbica.
    fator = elemento.normal_geometrico / ei
    # EI θ(x) = EI θ_i + v_i x²/2 - m_i x + w_i x³/6 + (w_j - w_i) x⁴/(24 L)
    theta = [inclinacao / 24.0, elemento.w_i / 6.0, v_i / 2.0, -m_i, ei * elemento.theta_i]
    # EI (v(x) − v_i) = EI θ_i x + v_i x³/6 − m_i x²/2 + w_i x⁴/24 + (w_j − w_i) x⁵/(120 L)
    flecha = [inclinacao / 120.0, elemento.w_i / 24.0, v_i / 6.0, -m_i / 2.0, ei * elemento.theta_i, 0.0]
    # V(x) = Q(x) + N̄ θ(x), com Q(x) = q_i + w_i x + (w_j - w_i) x² / (2 L).
    cortante = [
        theta[0] * fator,
        theta[1] * fator,
        theta[2] * fator + inclinacao / 2.0,
        theta[3] * fator + elemento.w_i,
        theta[4] * fator + q_i,
    ]
    # M(x) = q_i x − mq_i + w_i x²/2 + (w_j − w_i) x³/(6 L) + N̄ (v(x) − v_i).
    momento = [
        flecha[0] * fator,
        flecha[1] * fator,
        flecha[2] * fator + inclinacao / 6.0,
        flecha[3] * fator + elemento.w_i / 2.0,
        flecha[4] * fator + q_i,
        -mq_i,
    ]
    for polinomio in (theta, cortante, momento):
        valores.extend(_raizes_polinomio(polinomio, l))
    # Uma trapezoidal que troca de sinal dentro do trecho (w = 0) dá um
    # extremo interno de V; o mesmo vale para a axial distribuída e N.
    for inicio, fim in ((elemento.w_i, elemento.w_j), (elemento.a_i, elemento.a_j)):
        if inicio * fim < 0:
            valores.append(l * inicio / (inicio - fim))
    valores = sorted(set(round(valor, 9) for valor in valores if 0.0 <= valor <= l))
    return valores


def _raizes_polinomio(coeficientes: Sequence[float], limite: float) -> list[float]:
    """Raízes reais em ``[0, limite]``, com os coeficientes em ordem decrescente.

    O polinômio é reescrito em ``t = x / limite`` antes de ir ao ``np.roots``:
    com ``x`` em mm e coeficientes que vão de N/mm² a N·mm, os termos
    diferem por muitas ordens de grandeza e a matriz companheira fica mal
    condicionada. Em ``t ∈ [0, 1]`` todos os termos ficam comparáveis, e os
    de maior grau que são desprezíveis nessa escala são descartados — em
    vez de produzir uma raiz "no infinito" cheia de ruído.
    """
    grau = len(coeficientes) - 1
    escalados = [float(valor) * limite ** (grau - indice) for indice, valor in enumerate(coeficientes)]
    maior = max((abs(valor) for valor in escalados), default=0.0)
    if not maior or not math.isfinite(maior):
        return []
    while escalados and abs(escalados[0]) <= 1e-12 * maior:
        escalados = escalados[1:]
    if len(escalados) < 2:
        return []
    try:
        raizes = np.roots(escalados)
    except np.linalg.LinAlgError:  # pragma: no cover - numpy raramente falha aqui
        return []
    return [
        float(raiz.real) * limite
        for raiz in raizes
        if abs(raiz.imag) <= 1e-7 and -1e-9 <= raiz.real <= 1.0 + 1e-9
    ]


def _ponto_diagrama(
    elemento: _Elemento,
    x_local: float,
    viga: Viga,
    ei: float,
    ea: float,
    gj: float,
) -> PontoDiagrama:
    l = elemento.comprimento
    w_i, w_j = elemento.w_i, elemento.w_j
    delta_w = (w_j - w_i) / l
    # Parcela elástica: gera a linha elástica (integração exata de 1ª ordem).
    v_i = float(elemento.esforcos_flexao[0])
    m_i = float(elemento.esforcos_flexao[1])
    # Parcela em equilíbrio (com K_g): gera os esforços internos.
    q_i = float(elemento.esforcos_equilibrio[0])
    mq_i = float(elemento.esforcos_equilibrio[1])
    n_geo = elemento.normal_geometrico
    x = x_local

    rotacao = elemento.theta_i + (
        v_i * x**2 / 2.0 - m_i * x + w_i * x**3 / 6.0 + delta_w * x**4 / 24.0
    ) / ei
    flecha = elemento.v_i + elemento.theta_i * x + (
        v_i * x**3 / 6.0 - m_i * x**2 / 2.0 + w_i * x**4 / 24.0 + delta_w * x**5 / 120.0
    ) / ei
    # Equilíbrio do trecho [0, x] na configuração deformada: o esforço normal
    # N̄ atuando no braço (v − v_i) é o momento P–Δ dentro do elemento, e
    # V = dM/dx = Q + N̄ θ é o cortante na seção (perpendicular ao eixo
    # deformado), que é o que gera a tensão de cisalhamento. Sem segunda
    # ordem N̄ = 0 e as expressões voltam às de primeira ordem.
    transversal = q_i + w_i * x + delta_w * x**2 / 2.0
    momento = (
        q_i * x - mq_i + w_i * x**2 / 2.0 + delta_w * x**3 / 6.0
        + n_geo * (flecha - elemento.v_i)
    )
    cortante = transversal + n_geo * rotacao

    a_i, a_j = elemento.a_i, elemento.a_j
    delta_a = (a_j - a_i) / l
    normal = -elemento.esforco_axial_i - (a_i * x + delta_a * x**2 / 2.0)
    deslocamento_axial = elemento.u_i + (
        -elemento.esforco_axial_i * x - a_i * x**2 / 2.0 - delta_a * x**3 / 6.0
    ) / ea

    torque = elemento.esforco_torcao_i
    giro = elemento.phi_i + (torque * x / gj if gj > 0 else 0.0)

    return _montar_ponto(
        x_global=elemento.x_i + x,
        normal=normal,
        cortante=cortante,
        momento=momento,
        torque=torque,
        flecha=flecha,
        rotacao=rotacao,
        deslocamento_axial=deslocamento_axial,
        giro=giro,
        secao=viga.secao,
    )


def _montar_ponto(
    *,
    x_global: float,
    normal: float,
    cortante: float,
    momento: float,
    torque: float,
    flecha: float,
    rotacao: float,
    deslocamento_axial: float,
    giro: float,
    secao: SecaoViga,
) -> PontoDiagrama:
    # As tensões vêm do núcleo compartilhado com o assistente de cargas, para
    # que as duas páginas nunca divirjam na mesma seção.
    tensoes = tensoes_combinadas(
        EsforcosSecao(
            normal_N=normal,
            momento_Nmm=momento,
            cortante_N=cortante,
            torque_Nmm=torque,
        ),
        secao,
    )
    critico = tensoes.critico

    return PontoDiagrama(
        x_mm=x_global,
        normal_N=normal,
        cortante_N=cortante,
        momento_Nmm=momento,
        torque_Nmm=torque,
        deslocamento_mm=flecha,
        rotacao_rad=rotacao,
        deslocamento_axial_mm=deslocamento_axial,
        giro_torcao_rad=giro,
        tensao_axial_MPa=tensoes.axial_MPa,
        tensao_flexao_superior_MPa=tensoes.flexao_superior_MPa,
        tensao_flexao_inferior_MPa=tensoes.flexao_inferior_MPa,
        tensao_normal_superior_MPa=tensoes.normal_superior_MPa,
        tensao_normal_inferior_MPa=tensoes.normal_inferior_MPa,
        tensao_cisalhamento_MPa=tensoes.cisalhamento_MPa,
        tensao_torcao_MPa=tensoes.torcao_MPa,
        von_mises_MPa=critico.von_mises_MPa,
        tresca_MPa=critico.tresca_MPa,
        ponto_critico=critico.nome,
        sigma_critico_MPa=critico.sigma_MPa,
        tau_critico_MPa=critico.tau_MPa,
    )


def estado_no_ponto_critico(ponto: PontoDiagrama) -> tuple[float, float]:
    """Par (σ, τ) que governou o von Mises daquela seção."""
    return ponto.sigma_critico_MPa, ponto.tau_critico_MPa


def ponto_em(resultado: ResultadoViga, x_mm: float) -> PontoDiagrama:
    """Ponto do diagrama em ``x_mm``, escolhendo o mais solicitado.

    Numa descontinuidade (carga concentrada, apoio, momento aplicado) há dois
    valores na mesma abscissa — um de cada lado. Devolver o de maior von
    Mises é o que interessa para levar a seção adiante: é ele que governa a
    verificação no módulo seguinte.
    """
    if not resultado.pontos:  # pragma: no cover - resultado sempre tem pontos
        raise ValueError("O resultado não contém pontos de diagrama.")
    alvo = _finito("x_mm", x_mm)
    distancia_minima = min(abs(ponto.x_mm - alvo) for ponto in resultado.pontos)
    candidatos = [
        ponto
        for ponto in resultado.pontos
        if abs(abs(ponto.x_mm - alvo) - distancia_minima) <= TOLERANCIA_POSICAO_MM
    ]
    return max(candidatos, key=lambda ponto: ponto.von_mises_MPa)


def secoes_notaveis(resultado: ResultadoViga) -> dict[str, float]:
    """Abscissas que valem a pena levar adiante, por grandeza governante."""
    extremos = resultado.extremos
    return {
        "Seção mais solicitada (von Mises)": extremos["von_mises"].x_mm,
        "Momento fletor máximo": extremos["momento"].x_mm,
        "Cortante máximo": extremos["cortante"].x_mm,
        "Esforço normal máximo": extremos["normal"].x_mm,
        "Torque máximo": extremos["torque"].x_mm,
        "Flecha máxima": extremos["flecha"].x_mm,
    }


def estado_plano_da_secao(
    resultado: ResultadoViga,
    x_mm: float | None = None,
    *,
    ponto: str | None = None,
) -> EstadoPlanoCalculado:
    """Converte uma seção da barra no estado plano usado pelos outros módulos.

    É o mesmo contrato que o assistente de cargas entrega ao Círculo de Mohr
    e à Análise estática, então a seção crítica de uma viga entra nesses
    módulos sem ninguém redigitar número nenhum.
    """
    if x_mm is None:
        x_mm = resultado.extremos["von_mises"].x_mm
    diagrama = ponto_em(resultado, x_mm)
    tensoes = tensoes_combinadas(
        EsforcosSecao(
            normal_N=diagrama.normal_N,
            momento_Nmm=diagrama.momento_Nmm,
            cortante_N=diagrama.cortante_N,
            torque_Nmm=diagrama.torque_Nmm,
        ),
        resultado.viga.secao,
    )
    escolhido = tensoes.critico if ponto is None else tensoes.ponto(ponto)
    return EstadoPlanoCalculado(
        sigma_x=escolhido.sigma_MPa,
        sigma_y=0.0,
        tau_xy=escolhido.tau_MPa,
        descricao=(
            f"{escolhido.nome} da seção em x = {diagrama.x_mm / 1_000.0:.3f} m "
            f"de {resultado.viga.nome} ({resultado.viga.secao.nome})"
        ),
        hipoteses=(
            "Estado plano na superfície da barra: a tensão transversal é nula.",
            "Tensões de flexão, axial, cortante e torção superpostas linearmente.",
            f"Esforços da seção: N = {diagrama.normal_N / 1_000.0:.3f} kN, "
            f"V = {diagrama.cortante_N / 1_000.0:.3f} kN, "
            f"M = {diagrama.momento_Nmm / 1e6:.3f} kN·m, "
            f"T = {diagrama.torque_Nmm / 1e6:.3f} kN·m.",
            "Concentração de tensão e efeitos locais de apoio não incluídos.",
        ),
    )


def amplitudes_de_fadiga(
    resultado: ResultadoViga, x_mm: float | None = None, *, eixo_girante: bool = True
) -> dict[str, float]:
    """Componentes alternada e média para levar à Análise de fadiga.

    Num **eixo girante** a fibra passa alternadamente por tração e compressão
    a cada volta: a flexão é totalmente alternada (``σa = |M| c/I``, média
    zero) e a parcela axial permanece estática. Numa viga fixa o mesmo
    momento é estático — por isso ``eixo_girante=False`` devolve amplitude
    zero, em vez de fingir que há ciclo onde não há.
    """
    if x_mm is None:
        x_mm = resultado.extremos["momento"].x_mm
    diagrama = ponto_em(resultado, x_mm)
    secao = resultado.viga.secao
    flexao = abs(diagrama.momento_Nmm) * max(
        secao.c_superior_mm, secao.c_inferior_mm
    ) / secao.inercia_mm4
    axial = diagrama.normal_N / secao.area_mm2
    if eixo_girante:
        return {
            "x_mm": diagrama.x_mm,
            "sigma_alternada_MPa": flexao,
            "sigma_media_MPa": axial,
            "tensao_torcao_MPa": abs(diagrama.tensao_torcao_MPa),
        }
    return {
        "x_mm": diagrama.x_mm,
        "sigma_alternada_MPa": 0.0,
        "sigma_media_MPa": axial + flexao,
        "tensao_torcao_MPa": abs(diagrama.tensao_torcao_MPa),
    }


_EXTREMOS = (
    ("normal", "normal_N", "N"),
    ("cortante", "cortante_N", "N"),
    ("momento", "momento_Nmm", "N·mm"),
    ("torque", "torque_Nmm", "N·mm"),
    ("flecha", "deslocamento_mm", "mm"),
    ("rotacao", "rotacao_rad", "rad"),
    ("giro_torcao", "giro_torcao_rad", "rad"),
    ("tensao_normal", "tensao_normal_inferior_MPa", "MPa"),
    ("tensao_cisalhamento", "tensao_cisalhamento_MPa", "MPa"),
    ("tensao_torcao", "tensao_torcao_MPa", "MPa"),
    ("von_mises", "von_mises_MPa", "MPa"),
    ("tresca", "tresca_MPa", "MPa"),
)


def _extremo_por_modulo(
    pontos: Sequence[PontoDiagrama], atributo: str
) -> PontoDiagrama:
    """Ponto de maior módulo; empate fica com o de menor ``x``.

    Numa viga simétrica o cortante vale +wL/2 num apoio e −wL/2 no outro:
    o módulo empata e, sem um critério explícito, o sinal reportado passa a
    depender de ruído de arredondamento — refinar a malha invertia o sinal.
    A tolerância relativa absorve esse ruído e o desempate por ``x`` torna a
    escolha reprodutível.

    A folga de 1e-9 é escolhida pelo ruído do solver, que cresce com o número
    de elementos: dois extremos de fato distintos num diagrama de viga nunca
    diferem por menos de uma parte em 1e9.
    """
    maximo = max(abs(getattr(ponto, atributo)) for ponto in pontos)
    limite = maximo * (1.0 - 1e-9)
    empatados = [
        ponto for ponto in pontos if abs(getattr(ponto, atributo)) >= limite
    ]
    return min(empatados, key=lambda ponto: ponto.x_mm)


def _calcular_extremos(pontos: Sequence[PontoDiagrama]) -> dict[str, Extremo]:
    """Extremo = valor de maior módulo, preservando o sinal original."""
    extremos: dict[str, Extremo] = {}
    for chave, atributo, unidade in _EXTREMOS:
        melhor = _extremo_por_modulo(pontos, atributo)
        extremos[chave] = Extremo(
            grandeza=chave,
            valor=float(getattr(melhor, atributo)),
            x_mm=melhor.x_mm,
            unidade=unidade,
        )
    # A tensão normal extrema pode estar na fibra superior; refaz o confronto.
    melhor_superior = _extremo_por_modulo(pontos, "tensao_normal_superior_MPa")
    if abs(melhor_superior.tensao_normal_superior_MPa) > abs(extremos["tensao_normal"].valor):
        extremos["tensao_normal"] = Extremo(
            grandeza="tensao_normal",
            valor=float(melhor_superior.tensao_normal_superior_MPa),
            x_mm=melhor_superior.x_mm,
            unidade="MPa",
        )
    return extremos


def _grau_hiperestaticidade(apoios: Iterable[Apoio], numero_rotulas: int) -> int:
    """Reações incógnitas − equações de equilíbrio no plano (3) − rótulas.

    Apoios elásticos entram como reação: eles de fato aplicam uma força, e
    ignorá-los faria uma viga estável sobre duas molas aparecer com grau
    negativo, como se fosse um mecanismo.
    """
    incognitas = 0
    for apoio in apoios:
        incognitas += int(apoio.restringe_vertical or apoio.rigidez_vertical_N_mm > 0)
        incognitas += int(apoio.restringe_horizontal)
        incognitas += int(apoio.restringe_rotacao or apoio.rigidez_rotacional_Nmm_rad > 0)
    return incognitas - 3 - numero_rotulas


# ---------------------------------------------------------------------------
# Combinações de carga e envoltória
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CombinacaoCarga:
    """Um conjunto de fatores por caso de carga.

    Um caso que **não** aparece em ``fatores`` entra com fator zero: a
    combinação declara o que participa dela, e omitir é o mesmo que dizer
    que aquela ação não age naquele cenário.
    """

    nome: str
    fatores: dict[str, float] = field(default_factory=dict)

    def fator(self, caso: str) -> float:
        """Fator do caso, comparando sem depender de maiúsculas.

        `Sobrecarga=1.5` e `caso=sobrecarga` são a mesma ação para quem
        escreve o modelo; fazer a comparação exata só produziria carga
        zerada em silêncio por causa de uma letra.
        """
        procurado = str(caso).strip().casefold()
        for nome, valor in self.fatores.items():
            if str(nome).strip().casefold() == procurado:
                return float(valor)
        return 0.0

    def casos(self) -> tuple[str, ...]:
        return tuple(self.fatores)


@dataclass(frozen=True, slots=True)
class PontoEnvoltoria:
    x_mm: float
    cortante_max_N: float
    cortante_min_N: float
    momento_max_Nmm: float
    momento_min_Nmm: float
    flecha_max_mm: float
    flecha_min_mm: float
    normal_max_N: float
    normal_min_N: float
    von_mises_max_MPa: float


@dataclass(frozen=True, slots=True)
class ResultadoEnvoltoria:
    viga: Viga
    combinacoes: tuple[CombinacaoCarga, ...]
    resultados: dict[str, ResultadoViga]
    pontos: tuple[PontoEnvoltoria, ...]
    governantes: dict[str, tuple[str, Extremo]]

    def governante(self, grandeza: str) -> tuple[str, Extremo]:
        return self.governantes[grandeza]


def casos_declarados(viga: Viga) -> tuple[str, ...]:
    """Casos de carga citados pelo modelo, na ordem em que aparecem."""
    vistos: list[str] = []
    grupos = (
        viga.cargas_pontuais,
        viga.momentos,
        viga.cargas_distribuidas,
        viga.cargas_axiais,
        viga.cargas_axiais_distribuidas,
        viga.torques,
    )
    for grupo in grupos:
        for carga in grupo:
            nome = str(getattr(carga, "caso", CASO_PADRAO) or CASO_PADRAO)
            if nome not in vistos:
                vistos.append(nome)
    if viga.considerar_peso_proprio and CASO_PADRAO not in vistos:
        vistos.append(CASO_PADRAO)
    return tuple(vistos)


def _escalar(carga: Any, fator: float, campos: tuple[str, ...]) -> Any:
    """Copia a carga multiplicando só as intensidades pelo fator.

    Aceita qualquer uma das dataclasses de carga. O tipo é ``Any`` porque
    ``dataclasses.replace`` não preserva o tipo concreto através de uma
    união para o verificador — e amarrar a assinatura a cada tipo exigiria
    seis sobrecargas para uma função de cinco linhas.
    """
    alteracoes: dict[str, float] = {}
    for campo in campos:
        valor = getattr(carga, campo)
        if valor is not None:
            alteracoes[campo] = valor * fator
    return replace(carga, **alteracoes)


def viga_da_combinacao(viga: Viga, combinacao: CombinacaoCarga) -> Viga:
    """Modelo com cada carga multiplicada pelo fator do seu caso.

    Geometria, apoios e rótulas não mudam: a malha sai idêntica em todas as
    combinações, o que é justamente o que torna a envoltória comparável
    ponto a ponto.
    """

    def fator_de(carga: Any) -> float:
        return combinacao.fator(str(getattr(carga, "caso", CASO_PADRAO) or CASO_PADRAO))

    peso = viga.considerar_peso_proprio
    fator_permanente = combinacao.fator(CASO_PADRAO)
    if peso and fator_permanente != 1.0:
        # O peso próprio é gerado como distribuída; para escaloná-lo sem
        # duplicar a fórmula, ele é materializado antes e escalado junto.
        viga = viga.com_peso_proprio()
        peso = False

    return Viga(
        comprimento_mm=viga.comprimento_mm,
        secao=viga.secao,
        material=viga.material,
        apoios=viga.apoios,
        rotulas=viga.rotulas,
        cargas_pontuais=tuple(
            _escalar(item, fator_de(item), ("fy_N",)) for item in viga.cargas_pontuais
        ),
        momentos=tuple(
            _escalar(item, fator_de(item), ("mz_Nmm",)) for item in viga.momentos
        ),
        cargas_distribuidas=tuple(
            _escalar(item, fator_de(item), ("w_inicial_N_mm", "w_final_N_mm"))
            for item in viga.cargas_distribuidas
        ),
        cargas_axiais=tuple(
            _escalar(item, fator_de(item), ("fx_N",)) for item in viga.cargas_axiais
        ),
        cargas_axiais_distribuidas=tuple(
            _escalar(item, fator_de(item), ("a_inicial_N_mm", "a_final_N_mm"))
            for item in viga.cargas_axiais_distribuidas
        ),
        torques=tuple(
            _escalar(item, fator_de(item), ("t_Nmm",)) for item in viga.torques
        ),
        considerar_peso_proprio=peso,
        considerar_segunda_ordem=viga.considerar_segunda_ordem,
        divisoes_por_trecho=viga.divisoes_por_trecho,
        nome=f"{viga.nome} — {combinacao.nome}",
    )


_GRANDEZAS_ENVOLTORIA = (
    ("cortante", "cortante_N"),
    ("momento", "momento_Nmm"),
    ("flecha", "deslocamento_mm"),
    ("normal", "normal_N"),
    ("von_mises", "von_mises_MPa"),
)


def analisar_envoltoria(
    viga: Viga,
    combinacoes: Sequence[CombinacaoCarga],
    *,
    pontos_por_elemento: int = 61,
) -> ResultadoEnvoltoria:
    """Resolve a barra em cada combinação e monta a envoltória.

    O máximo de uma grandeza e o máximo de outra costumam vir de combinações
    diferentes; por isso a envoltória guarda, para cada extremo, **qual**
    combinação o governou — em vez de devolver um único número solto que
    ninguém sabe de onde veio.
    """
    lista = list(combinacoes)
    if not lista:
        raise ValueError("Informe pelo menos uma combinação de carga.")
    nomes = [combinacao.nome for combinacao in lista]
    if len(set(nomes)) != len(nomes):
        raise ValueError("Os nomes das combinações devem ser únicos.")

    # Um caso citado na combinação mas ausente do modelo é quase sempre erro
    # de digitação — e o efeito seria uma parcela simplesmente não entrar,
    # sem nenhum aviso.
    declarados = {nome.strip().casefold() for nome in casos_declarados(viga)}
    for combinacao in lista:
        desconhecidos = [
            nome
            for nome in combinacao.casos()
            if nome.strip().casefold() not in declarados
        ]
        if desconhecidos:
            disponiveis = ", ".join(casos_declarados(viga)) or "nenhum"
            raise ValueError(
                f"A combinação {combinacao.nome!r} cita casos que não existem no "
                f"modelo: {', '.join(desconhecidos)}. Casos declarados: {disponiveis}."
            )

    resultados: dict[str, ResultadoViga] = {}
    for combinacao in lista:
        try:
            resultados[combinacao.nome] = analisar_viga(
                viga_da_combinacao(viga, combinacao),
                pontos_por_elemento=pontos_por_elemento,
            )
        except ValueError as erro:
            # Com segunda ordem, uma combinação pode passar da carga crítica
            # enquanto as outras resolvem; sem o nome, o erro não diz qual.
            raise ValueError(f"Combinação {combinacao.nome!r}: {erro}") from erro

    # A envoltória é montada sobre as abscissas comuns a todas as
    # combinações. Cada resultado ainda traz as raízes de V(x)=0 e θ(x)=0
    # da sua própria combinação, que naturalmente não coincidem — usar a
    # interseção evita comparar pontos que não existem em todas.
    conjuntos = [
        {round(ponto.x_mm, 9) for ponto in resultado.pontos}
        for resultado in resultados.values()
    ]
    comuns = sorted(set.intersection(*conjuntos))

    por_x: dict[float, list[PontoDiagrama]] = {chave: [] for chave in comuns}
    for resultado in resultados.values():
        for ponto in resultado.pontos:
            chave = round(ponto.x_mm, 9)
            if chave in por_x:
                por_x[chave].append(ponto)

    pontos: list[PontoEnvoltoria] = []
    for chave in comuns:
        grupo = por_x[chave]
        pontos.append(
            PontoEnvoltoria(
                x_mm=chave,
                cortante_max_N=max(p.cortante_N for p in grupo),
                cortante_min_N=min(p.cortante_N for p in grupo),
                momento_max_Nmm=max(p.momento_Nmm for p in grupo),
                momento_min_Nmm=min(p.momento_Nmm for p in grupo),
                flecha_max_mm=max(p.deslocamento_mm for p in grupo),
                flecha_min_mm=min(p.deslocamento_mm for p in grupo),
                normal_max_N=max(p.normal_N for p in grupo),
                normal_min_N=min(p.normal_N for p in grupo),
                von_mises_max_MPa=max(p.von_mises_MPa for p in grupo),
            )
        )

    # Os extremos governantes vêm dos resultados completos (com as raízes de
    # cada combinação), não da malha comum: assim o pico não é arredondado
    # para a amostra mais próxima.
    governantes: dict[str, tuple[str, Extremo]] = {}
    for grandeza, _ in _GRANDEZAS_ENVOLTORIA:
        melhor_nome = ""
        melhor_extremo: Extremo | None = None
        for nome, resultado in resultados.items():
            extremo = resultado.extremos[grandeza]
            if melhor_extremo is None or abs(extremo.valor) > abs(melhor_extremo.valor):
                melhor_nome, melhor_extremo = nome, extremo
        assert melhor_extremo is not None
        governantes[grandeza] = (melhor_nome, melhor_extremo)

    return ResultadoEnvoltoria(
        viga=viga,
        combinacoes=tuple(lista),
        resultados=resultados,
        pontos=tuple(pontos),
        governantes=governantes,
    )


def tabela_envoltoria(envoltoria: ResultadoEnvoltoria) -> list[dict[str, float]]:
    """Envoltória em unidades de engenharia."""
    return [
        {
            "x (m)": ponto.x_mm / 1_000.0,
            "V máx (kN)": ponto.cortante_max_N / 1_000.0,
            "V mín (kN)": ponto.cortante_min_N / 1_000.0,
            "M máx (kN·m)": ponto.momento_max_Nmm / 1e6,
            "M mín (kN·m)": ponto.momento_min_Nmm / 1e6,
            "Flecha máx (mm)": ponto.flecha_max_mm,
            "Flecha mín (mm)": ponto.flecha_min_mm,
            "N máx (kN)": ponto.normal_max_N / 1_000.0,
            "N mín (kN)": ponto.normal_min_N / 1_000.0,
            "von Mises máx (MPa)": ponto.von_mises_max_MPa,
        }
        for ponto in envoltoria.pontos
    ]


def resumo_governantes(envoltoria: ResultadoEnvoltoria) -> list[dict[str, object]]:
    """Qual combinação governa cada grandeza, e onde."""
    conversao = {
        "cortante": (1 / 1_000.0, "kN"),
        "momento": (1 / 1e6, "kN·m"),
        "flecha": (1.0, "mm"),
        "normal": (1 / 1_000.0, "kN"),
        "von_mises": (1.0, "MPa"),
    }
    rotulos = {
        "cortante": "Cortante V",
        "momento": "Momento fletor M",
        "flecha": "Flecha",
        "normal": "Esforço normal N",
        "von_mises": "Tensão de von Mises",
    }
    linhas = []
    for grandeza, _ in _GRANDEZAS_ENVOLTORIA:
        nome, extremo = envoltoria.governantes[grandeza]
        escala, unidade = conversao[grandeza]
        linhas.append(
            {
                "Grandeza": rotulos[grandeza],
                "Combinação governante": nome,
                "Valor": extremo.valor * escala,
                "Unidade": unidade,
                "x (m)": extremo.x_mm / 1_000.0,
            }
        )
    return linhas


# ---------------------------------------------------------------------------
# Verificações de serviço
# ---------------------------------------------------------------------------


def verificar_flecha(
    resultado: ResultadoViga,
    *,
    limite_vao: float = 350.0,
    vao_mm: float | None = None,
) -> dict[str, float | bool | str]:
    """Compara a flecha máxima com o clássico L/limite.

    ``vao_mm`` permite informar o vão real entre apoios quando a barra tem
    balanços; por padrão usa a distância entre o primeiro e o último apoio,
    ou o comprimento total quando há um só apoio (balanço engastado).
    """
    limite_vao = _positivo("limite_vao", limite_vao)
    if vao_mm is None:
        comprimento = resultado.viga.comprimento_mm
        # Só conta como extremo do vão quem segura a barra na vertical: uma
        # trava axial ou um apoio "livre" não define vão nenhum.
        posicoes_apoio = sorted(
            min(max(apoio.x_mm, 0.0), comprimento)
            for apoio in resultado.viga.apoios
            if apoio.restringe_vertical or apoio.rigidez_vertical_N_mm > 0
        )
        if len(posicoes_apoio) >= 2 and posicoes_apoio[-1] - posicoes_apoio[0] > 0:
            vao_mm = posicoes_apoio[-1] - posicoes_apoio[0]
        else:
            vao_mm = comprimento
    vao_mm = _positivo("vao_mm", vao_mm)
    flecha = abs(resultado.extremos["flecha"].valor)
    admissivel = vao_mm / limite_vao
    return {
        "vao_mm": vao_mm,
        "limite_vao": limite_vao,
        "flecha_mm": flecha,
        "flecha_admissivel_mm": admissivel,
        "utilizacao": flecha / admissivel if admissivel > 0 else math.inf,
        "atende": flecha <= admissivel,
        "criterio": f"L/{limite_vao:.0f}",
    }


def tabela_diagramas(resultado: ResultadoViga) -> list[dict[str, float | str]]:
    """Diagramas em unidades de engenharia (m, kN, kN·m, mm, MPa)."""
    return [
        {
            "x (m)": ponto.x_mm / 1_000.0,
            "N (kN)": ponto.normal_N / 1_000.0,
            "V (kN)": ponto.cortante_N / 1_000.0,
            "M (kN·m)": ponto.momento_Nmm / 1e6,
            "T (kN·m)": ponto.torque_Nmm / 1e6,
            "Flecha (mm)": ponto.deslocamento_mm,
            "Rotação (mrad)": ponto.rotacao_rad * 1_000.0,
            "Giro torção (°)": math.degrees(ponto.giro_torcao_rad),
            "σ sup (MPa)": ponto.tensao_normal_superior_MPa,
            "σ inf (MPa)": ponto.tensao_normal_inferior_MPa,
            "τ V (MPa)": ponto.tensao_cisalhamento_MPa,
            "τ T (MPa)": ponto.tensao_torcao_MPa,
            "von Mises (MPa)": ponto.von_mises_MPa,
            "Ponto crítico": ponto.ponto_critico,
        }
        for ponto in resultado.pontos
    ]


def resumo_reacoes(resultado: ResultadoViga) -> list[dict[str, object]]:
    return [
        {
            "x (m)": reacao.x_mm / 1_000.0,
            "Apoio": reacao.tipo,
            "Fy (kN)": reacao.fy_N / 1_000.0,
            "Fx (kN)": reacao.fx_N / 1_000.0,
            "Mz (kN·m)": reacao.mz_Nmm / 1e6,
            "Mt (kN·m)": reacao.mt_Nmm / 1e6,
        }
        for reacao in resultado.reacoes
    ]


def conferir_equilibrio(resultado: ResultadoViga) -> dict[str, float]:
    """Resíduo do equilíbrio global — controle numérico do próprio solver.

    Momentos tomados em torno de ``x = 0``. Com a segunda ordem ligada, as
    reações equilibram as cargas na **configuração deformada**: cada esforço
    normal age no braço da flecha, e esse momento P–Δ (``∫ N dv``, devolvido
    em ``momento_p_delta_Nmm``) entra na soma — sem ele, o resíduo de ΣM
    seria exatamente o efeito de segunda ordem, e não um erro do solver.

    ``residuo_relativo`` é o pior dos quatro resíduos, cada um dividido pela
    escala da sua própria grandeza (força, momento = força × L, torque).
    """
    viga = resultado.viga
    comprimento_total = viga.comprimento_mm
    soma_fy = sum(reacao.fy_N for reacao in resultado.reacoes)
    soma_fx = sum(reacao.fx_N for reacao in resultado.reacoes)
    soma_mz = sum(
        reacao.mz_Nmm + reacao.fy_N * reacao.x_mm for reacao in resultado.reacoes
    )
    soma_mt = sum(reacao.mt_Nmm for reacao in resultado.reacoes)
    escala_forca = escala_axial = escala_torque = 0.0
    escala_momento = 0.0
    for pontual in viga.cargas_pontuais:
        soma_fy += pontual.fy_N
        soma_mz += pontual.fy_N * pontual.x_mm
        escala_forca = max(escala_forca, abs(pontual.fy_N))
    for momento in viga.momentos:
        soma_mz += momento.mz_Nmm
        escala_momento = max(escala_momento, abs(momento.mz_Nmm))
    for distribuida in viga.cargas_distribuidas:
        comprimento = distribuida.x_final_mm - distribuida.x_inicial_mm
        w_i, w_f = distribuida.w_inicial_N_mm, distribuida.w_final
        resultante = (w_i + w_f) * comprimento / 2.0
        # Momento do trapézio de carga em torno de x = 0, escrito sem dividir
        # pela resultante — que pode ser nula numa carga antissimétrica.
        soma_fy += resultante
        soma_mz += resultante * distribuida.x_inicial_mm + comprimento**2 * (w_i + 2.0 * w_f) / 6.0
        escala_forca = max(escala_forca, abs(w_i) * comprimento, abs(w_f) * comprimento)
    for axial in viga.cargas_axiais:
        soma_fx += axial.fx_N
        escala_axial = max(escala_axial, abs(axial.fx_N))
    for axial_distribuida in viga.cargas_axiais_distribuidas:
        comprimento = axial_distribuida.x_final_mm - axial_distribuida.x_inicial_mm
        a_i, a_f = axial_distribuida.a_inicial_N_mm, axial_distribuida.a_final
        soma_fx += (a_i + a_f) * comprimento / 2.0
        escala_axial = max(escala_axial, abs(a_i) * comprimento, abs(a_f) * comprimento)
    for torque in viga.torques:
        soma_mt += torque.t_Nmm
        escala_torque = max(escala_torque, abs(torque.t_Nmm))

    momento_p_delta = 0.0
    if resultado.segunda_ordem:
        # ∫ N dv pelos pontos do diagrama: dentro de cada elemento N̄ é
        # constante e a soma telescopa para N̄ (v_j − v_i), exatamente a
        # parcela que a rigidez geométrica acrescentou às reações.
        pontos = resultado.pontos
        for anterior, atual in zip(pontos, pontos[1:], strict=False):
            momento_p_delta += 0.5 * (anterior.normal_N + atual.normal_N) * (
                atual.deslocamento_mm - anterior.deslocamento_mm
            )
        soma_mz -= momento_p_delta

    escala_forca = max(escala_forca, escala_axial, 1.0)
    escala_momento = max(escala_momento, escala_forca * comprimento_total, 1.0)
    escala_torque = max(escala_torque, 1.0)
    return {
        "residuo_fy_N": soma_fy,
        "residuo_fx_N": soma_fx,
        "residuo_mz_Nmm": soma_mz,
        "residuo_mt_Nmm": soma_mt,
        "momento_p_delta_Nmm": momento_p_delta,
        "residuo_relativo": max(
            abs(soma_fy) / escala_forca,
            abs(soma_fx) / escala_forca,
            abs(soma_mz) / escala_momento,
            abs(soma_mt) / escala_torque,
        ),
    }
