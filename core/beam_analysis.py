"""Análise de vigas e eixos: cortante, momento, linha elástica e torção.

O módulo resolve uma barra reta (viga ou eixo) por rigidez direta com
elementos de Euler-Bernoulli e recupera os esforços internos de forma
**analítica** dentro de cada elemento. Como os nós são colocados em toda
descontinuidade (apoio, carga pontual, momento, início/fim de carga
distribuída), a carga distribuída dentro de um elemento é sempre uma única
função linear — logo ``V(x)`` é quadrática, ``M(x)`` é cúbica e a linha
elástica ``v(x)`` é um polinômio de quinto grau, todos exatos.

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

from dataclasses import dataclass, field
import math
from typing import Iterable, Sequence

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

GRAVIDADE_M_S2 = 9.80665

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
        if not self.tem_cisalhamento:
            raise ValueError(
                "A seção precisa de Q e t (para V·Q/(I·t)) ou de uma área de "
                "cisalhamento (para V/Av); sem isso a tensão de cisalhamento "
                "seria sempre zero."
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
    nome: str
    modulo_elasticidade_MPa: float
    modulo_cisalhamento_MPa: float
    escoamento_MPa: float | None = None
    densidade_kg_m3: float = 7_850.0

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
        descricao=(
            f"Perfil I {h:.4g} × {bf:.4g} mm (alma {tw:.4g}, mesa {tf:.4g}). "
            "Torção de perfil aberto — muito pouco rígida."
        ),
    )


def secao_de_perfil_catalogo(perfil, *, eixo: str = "x") -> SecaoViga:
    """Converte um :class:`core.steel_sections.PerfilAco` em :class:`SecaoViga`.

    O catálogo não tabela o momento estático ``Q``, então o cisalhamento usa
    a rota normativa ``tau = V / A_v`` com a área de cisalhamento do próprio
    catálogo, em vez de um ``Q`` inventado. Para perfis monossimétricos (U,
    C, T) mantém-se ``c = altura / 2``, a mesma convenção que o catálogo já
    usa em ``sx_mm3`` — é aproximado, e a descrição da seção sinaliza isso.
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
    c = altura / 2.0
    j = float(perfil.j_mm4)
    t_max = max(float(perfil.espessura_mesa_mm), float(perfil.espessura_alma_mm))
    return SecaoViga(
        nome=str(perfil.nome),
        area_mm2=float(perfil.area_mm2),
        inercia_mm4=inercia,
        c_superior_mm=c,
        c_inferior_mm=c,
        momento_estatico_mm3=0.0,
        espessura_cisalhamento_mm=espessura,
        constante_torcao_mm4=j,
        modulo_torcao_mm3=j / t_max if t_max > 0 else 0.0,
        area_cisalhamento_mm2=float(perfil.area_cisalhamento_mm2),
        descricao=f"{perfil.nome} — {perfil.descricao} (flexão em torno de {eixo}).",
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
    rotulo: str = ""

    def __post_init__(self) -> None:
        _finito("x_mm", self.x_mm)
        _finito("fy_N", self.fy_N)


@dataclass(frozen=True, slots=True)
class MomentoConcentrado:
    x_mm: float
    mz_Nmm: float
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
    nome: str = "Viga"

    def __post_init__(self) -> None:
        _positivo("comprimento_mm", self.comprimento_mm)

    def com_peso_proprio(self) -> "Viga":
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


def _mesmo_ponto(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCIA_POSICAO_MM


def _inserir(posicoes: list[float], valor: float) -> None:
    for existente in posicoes:
        if _mesmo_ponto(existente, valor):
            return
    posicoes.append(valor)


def _validar_posicao(nome: str, x: float, comprimento: float) -> float:
    x = _finito(nome, x)
    if x < -TOLERANCIA_POSICAO_MM or x > comprimento + TOLERANCIA_POSICAO_MM:
        raise ValueError(
            f"{nome} = {x:.4g} mm está fora da viga (0 a {comprimento:.4g} mm)."
        )
    return min(max(x, 0.0), comprimento)


def _posicoes_nodais(viga: Viga) -> list[float]:
    comprimento = viga.comprimento_mm
    posicoes: list[float] = [0.0, comprimento]
    for apoio in viga.apoios:
        _inserir(posicoes, _validar_posicao("posição do apoio", apoio.x_mm, comprimento))
    for rotula in viga.rotulas:
        _inserir(posicoes, _validar_posicao("posição da rótula", rotula.x_mm, comprimento))
    for carga in viga.cargas_pontuais:
        _inserir(posicoes, _validar_posicao("posição da carga pontual", carga.x_mm, comprimento))
    for momento in viga.momentos:
        _inserir(posicoes, _validar_posicao("posição do momento", momento.x_mm, comprimento))
    for carga in viga.cargas_axiais:
        _inserir(posicoes, _validar_posicao("posição da carga axial", carga.x_mm, comprimento))
    for torque in viga.torques:
        _inserir(posicoes, _validar_posicao("posição do torque", torque.x_mm, comprimento))
    for carga in viga.cargas_distribuidas:
        _inserir(posicoes, _validar_posicao("início da carga distribuída", carga.x_inicial_mm, comprimento))
        _inserir(posicoes, _validar_posicao("fim da carga distribuída", carga.x_final_mm, comprimento))
    for carga in viga.cargas_axiais_distribuidas:
        _inserir(posicoes, _validar_posicao("início da carga axial distribuída", carga.x_inicial_mm, comprimento))
        _inserir(posicoes, _validar_posicao("fim da carga axial distribuída", carga.x_final_mm, comprimento))
    posicoes.sort()
    return posicoes


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
    esforcos_flexao: np.ndarray = field(default_factory=lambda: np.zeros(4))
    esforco_axial_i: float = 0.0
    esforco_torcao_i: float = 0.0
    v_i: float = 0.0
    theta_i: float = 0.0
    u_i: float = 0.0
    phi_i: float = 0.0


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
        posto = int(np.linalg.matrix_rank(kff, tol=max(1e-12, 1e-12 * float(np.abs(kff).max() or 1.0))))
        if posto < len(livres):
            mecanismos = len(livres) - posto
            raise ValueError(
                f"O modelo é instável em {contexto}: há {mecanismos} movimento(s) de corpo "
                "rígido ou mecanismo(s) sem restrição. Revise os apoios (e as rótulas "
                "internas, que não podem deixar um trecho isolado sem apoio)."
            )
        try:
            deslocamentos[livres] = np.linalg.solve(kff, f[livres])
        except np.linalg.LinAlgError as erro:  # pragma: no cover - proteção extra
            raise ValueError(
                f"Não foi possível resolver o sistema de {contexto}: matriz singular."
            ) from erro
    reacoes = k @ deslocamentos - f
    return deslocamentos, reacoes


def analisar_viga(viga: Viga, *, pontos_por_elemento: int = 61) -> ResultadoViga:
    """Resolve a viga e devolve diagramas, reações, tensões e extremos."""
    if pontos_por_elemento < 3:
        raise ValueError("pontos_por_elemento deve ser pelo menos 3.")

    viga = viga.com_peso_proprio()
    comprimento = viga.comprimento_mm
    secao, material = viga.secao, viga.material
    avisos: list[str] = []

    if not viga.apoios:
        raise ValueError("Informe pelo menos um apoio — sem apoio a viga não tem equilíbrio.")

    posicoes = _posicoes_nodais(viga)
    n_nos = len(posicoes)
    if n_nos < 2:
        raise ValueError("A viga precisa de pelo menos dois nós.")

    indice_por_x: dict[int, int] = {}

    def no_de(x: float) -> int:
        for indice, posicao in enumerate(posicoes):
            if _mesmo_ponto(posicao, x):
                return indice
        raise ValueError(f"Posição {x:.4g} mm não corresponde a nenhum nó da malha.")

    # -- rótulas -----------------------------------------------------------
    nos_rotula: set[int] = set()
    for rotula in viga.rotulas:
        x = _validar_posicao("posição da rótula", rotula.x_mm, comprimento)
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
        x = _validar_posicao("posição do apoio", apoio.x_mm, comprimento)
        indice = no_de(x)
        if indice in apoios_por_no:
            raise ValueError(f"Há mais de um apoio em x = {x:.4g} mm.")
        if indice in nos_rotula and apoio.restringe_rotacao:
            raise ValueError(
                f"Em x = {x:.4g} mm há uma rótula e um apoio que impede a rotação. "
                "Escolha um dos dois: a rótula libera exatamente o que o engaste trava."
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

    # -- sistema de flexão ---------------------------------------------------
    k_flexao = np.zeros((n_dof_flexao, n_dof_flexao))
    f_flexao = np.zeros(n_dof_flexao)
    for elemento in elementos:
        dofs = list(elemento.dofs_flexao)
        k_flexao[np.ix_(dofs, dofs)] += _rigidez_flexao(ei, elemento.comprimento)
        f_flexao[dofs] += _cargas_equivalentes_flexao(
            elemento.w_i, elemento.w_j, elemento.comprimento
        )
    for carga in viga.cargas_pontuais:
        indice = no_de(_validar_posicao("posição da carga pontual", carga.x_mm, comprimento))
        f_flexao[dof_v[indice]] += carga.fy_N
    for momento in viga.momentos:
        indice = no_de(_validar_posicao("posição do momento", momento.x_mm, comprimento))
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

    deslocamentos_flexao, reacoes_flexao = _resolver_sistema(
        k_flexao, f_flexao, restritos_flexao, "flexão (translação vertical / rotação)"
    )

    # -- sistema axial -------------------------------------------------------
    k_axial = np.zeros((n_nos, n_nos))
    f_axial = np.zeros(n_nos)
    for elemento in elementos:
        dofs = list(elemento.dofs_axial)
        rigidez = ea / elemento.comprimento
        k_axial[np.ix_(dofs, dofs)] += rigidez * np.array([[1.0, -1.0], [-1.0, 1.0]])
        f_axial[dofs] += _cargas_equivalentes_axial(elemento.a_i, elemento.a_j, elemento.comprimento)
    for carga in viga.cargas_axiais:
        indice = no_de(_validar_posicao("posição da carga axial", carga.x_mm, comprimento))
        f_axial[indice] += carga.fx_N

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
        if any(abs(c.fx_N) > 0 for c in viga.cargas_axiais) or viga.cargas_axiais_distribuidas:
            avisos.append(
                f"Nenhum apoio trava o eixo x: o deslocamento axial foi fixado em "
                f"x = {posicoes[ancora]:.4g} mm apenas como referência. Os esforços "
                "normais são autoequilibrados e não dependem dessa escolha."
            )

    deslocamentos_axiais, reacoes_axiais = _resolver_sistema(
        k_axial, f_axial, restritos_axial, "esforço axial"
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
        indice = no_de(_validar_posicao("posição do torque", torque.x_mm, comprimento))
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
        elemento.v_i = float(u_local[0])
        elemento.theta_i = float(u_local[1])

        dofs_axial = list(elemento.dofs_axial)
        u_axial = deslocamentos_axiais[dofs_axial]
        rigidez_axial = ea / elemento.comprimento
        forcas_axiais = rigidez_axial * np.array(
            [u_axial[0] - u_axial[1], u_axial[1] - u_axial[0]]
        ) - _cargas_equivalentes_axial(elemento.a_i, elemento.a_j, elemento.comprimento)
        elemento.esforco_axial_i = float(forcas_axiais[0])
        elemento.u_i = float(u_axial[0])

        if gj > 0:
            dofs_torcao = list(elemento.dofs_torcao)
            u_torcao = deslocamentos_torcao[dofs_torcao]
            rigidez_torcao = gj / elemento.comprimento
            elemento.esforco_torcao_i = float(rigidez_torcao * (u_torcao[1] - u_torcao[0]))
            elemento.phi_i = float(u_torcao[0])

    # -- amostragem dos diagramas -------------------------------------------
    pontos: list[PontoDiagrama] = []
    for elemento in elementos:
        for x_local in _amostras(elemento, pontos_por_elemento, ei):
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
    )


def _amostras(elemento: _Elemento, quantidade: int, ei: float) -> list[float]:
    """Pontos locais do elemento, incluindo raízes de V(x) = 0 e θ(x) = 0.

    Incluir as raízes garante que o máximo do momento e a flecha máxima
    caiam exatamente sobre uma amostra, em vez de dependerem da densidade
    da malha.
    """
    l = elemento.comprimento
    valores = list(np.linspace(0.0, l, quantidade))
    v_i = float(elemento.esforcos_flexao[0])
    m_i = float(elemento.esforcos_flexao[1])
    inclinacao = (elemento.w_j - elemento.w_i) / l
    # V(x) = v_i + w_i x + (w_j - w_i) x² / (2 L)
    for raiz in _raizes_polinomio([inclinacao / 2.0, elemento.w_i, v_i], l):
        valores.append(raiz)
    # EI θ(x) = EI θ_i + v_i x²/2 - m_i x + w_i x³/6 + (w_j - w_i) x⁴/(24 L)
    for raiz in _raizes_polinomio(
        [inclinacao / 24.0, elemento.w_i / 6.0, v_i / 2.0, -m_i, ei * elemento.theta_i], l
    ):
        valores.append(raiz)
    valores = sorted(set(round(valor, 9) for valor in valores if 0.0 <= valor <= l))
    return valores


def _raizes_polinomio(coeficientes: Sequence[float], limite: float) -> list[float]:
    """Raízes reais em ``[0, limite]``, com os coeficientes em ordem decrescente."""
    coeficientes = [float(valor) for valor in coeficientes]
    while coeficientes and abs(coeficientes[0]) < 1e-14:
        coeficientes = coeficientes[1:]
    if len(coeficientes) < 2:
        return []
    try:
        raizes = np.roots(coeficientes)
    except np.linalg.LinAlgError:  # pragma: no cover - numpy raramente falha aqui
        return []
    return [
        float(raiz.real)
        for raiz in raizes
        if abs(raiz.imag) < 1e-9 and -1e-9 <= raiz.real <= limite + 1e-9
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
    v_i = float(elemento.esforcos_flexao[0])
    m_i = float(elemento.esforcos_flexao[1])
    x = x_local

    cortante = v_i + w_i * x + delta_w * x**2 / 2.0
    momento = v_i * x - m_i + w_i * x**2 / 2.0 + delta_w * x**3 / 6.0
    rotacao = elemento.theta_i + (
        v_i * x**2 / 2.0 - m_i * x + w_i * x**3 / 6.0 + delta_w * x**4 / 24.0
    ) / ei
    flecha = elemento.v_i + elemento.theta_i * x + (
        v_i * x**3 / 6.0 - m_i * x**2 / 2.0 + w_i * x**4 / 24.0 + delta_w * x**5 / 120.0
    ) / ei

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


def _calcular_extremos(pontos: Sequence[PontoDiagrama]) -> dict[str, Extremo]:
    """Extremo = valor de maior módulo, preservando o sinal original."""
    extremos: dict[str, Extremo] = {}
    for chave, atributo, unidade in _EXTREMOS:
        melhor = max(pontos, key=lambda ponto: abs(getattr(ponto, atributo)))
        extremos[chave] = Extremo(
            grandeza=chave,
            valor=float(getattr(melhor, atributo)),
            x_mm=melhor.x_mm,
            unidade=unidade,
        )
    # A tensão normal extrema pode estar na fibra superior; refaz o confronto.
    melhor_superior = max(pontos, key=lambda ponto: abs(ponto.tensao_normal_superior_MPa))
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
        posicoes_apoio = sorted(reacao.x_mm for reacao in resultado.reacoes)
        if len(posicoes_apoio) >= 2:
            vao_mm = posicoes_apoio[-1] - posicoes_apoio[0]
        else:
            vao_mm = resultado.viga.comprimento_mm
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


def tabela_diagramas(resultado: ResultadoViga) -> list[dict[str, float]]:
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
    """Resíduo do equilíbrio global — controle numérico do próprio solver."""
    viga = resultado.viga
    soma_fy = sum(reacao.fy_N for reacao in resultado.reacoes)
    soma_fx = sum(reacao.fx_N for reacao in resultado.reacoes)
    soma_mz = sum(
        reacao.mz_Nmm + reacao.fy_N * reacao.x_mm for reacao in resultado.reacoes
    )
    soma_mt = sum(reacao.mt_Nmm for reacao in resultado.reacoes)
    escala_forca = 0.0
    for carga in viga.cargas_pontuais:
        soma_fy += carga.fy_N
        soma_mz += carga.fy_N * carga.x_mm
        escala_forca = max(escala_forca, abs(carga.fy_N))
    for momento in viga.momentos:
        soma_mz += momento.mz_Nmm
    for carga in viga.cargas_distribuidas:
        comprimento = carga.x_final_mm - carga.x_inicial_mm
        resultante = (carga.w_inicial_N_mm + carga.w_final) * comprimento / 2.0
        if abs(carga.w_inicial_N_mm + carga.w_final) > 0:
            braco = carga.x_inicial_mm + comprimento * (
                carga.w_inicial_N_mm + 2.0 * carga.w_final
            ) / (3.0 * (carga.w_inicial_N_mm + carga.w_final))
        else:
            braco = carga.x_inicial_mm + comprimento / 2.0
        soma_fy += resultante
        soma_mz += resultante * braco
        escala_forca = max(escala_forca, abs(resultante))
    for carga in viga.cargas_axiais:
        soma_fx += carga.fx_N
    for carga in viga.cargas_axiais_distribuidas:
        comprimento = carga.x_final_mm - carga.x_inicial_mm
        soma_fx += (carga.a_inicial_N_mm + carga.a_final) * comprimento / 2.0
    for torque in viga.torques:
        soma_mt += torque.t_Nmm
    escala_forca = max(escala_forca, 1.0)
    return {
        "residuo_fy_N": soma_fy,
        "residuo_fx_N": soma_fx,
        "residuo_mz_Nmm": soma_mz,
        "residuo_mt_Nmm": soma_mt,
        "residuo_relativo": abs(soma_fy) / escala_forca,
    }
