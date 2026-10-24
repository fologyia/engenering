"""Modelo de dados, cargas e resultados da análise de vigas e eixos."""

from __future__ import annotations

from dataclasses import dataclass

from core.beam_sections import MaterialViga, SecaoViga, _finito, _nao_negativo, _positivo

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
