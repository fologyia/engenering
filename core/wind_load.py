"""Ação do vento pela ABNT NBR 6123:2023 — velocidade, pressão dinâmica e força de arrasto numa peça.

O caminho é o da norma, sem atalhos::

    V_k = V_0 · S_1 · S_2 · S_3          (m/s)
    q   = 0,613 · V_k²                   (N/m²)
    F   = C_f · q · A_e                  (força de arrasto numa área efetiva)

A cadeia de fatores (``S_1``, ``S_2``, ``S_3``, ``V_k`` e ``q``) mora em :mod:`core.vento_nbr6123`,
com os parâmetros da edição de 2023; este módulo a usa para uma peça isolada — plataforma, barra,
perfil ou painel — em que o coeficiente aerodinâmico entra como dado. Para a edificação
paralelepipédica (paredes, telhado, pórtico), use :mod:`core.vento_edificio`.

Os nomes antigos continuam valendo (``fator_s1``, ``fator_s2``, ``fator_s3``, ``GRUPOS_S3``…), porque
a página de Estruturas de aço e os registros já salvos os usam.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.vento_nbr6123 import (
    ALTURA_GRADIENTE_M,
    ALTURA_MINIMA_S2_M,
    CATEGORIAS_RUGOSIDADE,
    CLASSES_EDIFICACAO,
    FATOR_PRESSAO_DINAMICA,
    FATOR_RAJADA,
    PARAMETROS_S2,
    calcular_vento_no_local,
    fator_s1,
    fator_s2,
    fator_s3,
    numero_ptbr,
    pressao_dinamica_N_m2,
    velocidade_caracteristica,
)
from core.vento_nbr6123 import GRUPOS_S3 as _GRUPOS_S3_COMPLETO

__all__ = [
    "ALTURA_GRADIENTE_M",
    "ALTURA_MINIMA_S2_M",
    "CATEGORIAS_RUGOSIDADE",
    "CLASSES_EDIFICACAO",
    "COEFICIENTES_ARRASTO_USUAIS",
    "FATOR_RAJADA",
    "GRUPOS_S3",
    "MASSA_ESPECIFICA_AR_FATOR",
    "PARAMETROS_S2",
    "ResultadoVento",
    "calcular_vento",
    "fator_s1",
    "fator_s2",
    "fator_s3",
    "pressao_dinamica_N_m2",
    "velocidade_caracteristica",
]

#: grupo → (S_3, descrição) — Tabela 4 da NBR 6123:2023 (o período de recorrência fica em
#: :data:`core.vento_nbr6123.GRUPOS_S3`).
GRUPOS_S3: dict[int, tuple[float, str]] = {
    grupo: (s3, descricao) for grupo, (s3, _periodo, descricao) in _GRUPOS_S3_COMPLETO.items()
}

# ---------------------------------------------------------------------------
# Coeficientes de arrasto usuais — orientação, não substituem as tabelas
# ---------------------------------------------------------------------------

COEFICIENTES_ARRASTO_USUAIS: dict[str, float] = {
    "Perfil aberto isolado (I, U, H, cantoneira), vento normal à face — Tabela 26": 2.0,
    "Barra retangular de cantos vivos, seção quadrada — Tabela 26": 2.0,
    "Tubo circular liso, Re ≥ 4,2×10⁵ — Tabela 27": 0.6,
    "Tubo circular rugoso ou Re < 4,2×10⁵ — Tabela 27": 1.2,
    "Treliça plana de perfis de faces planas, índice de área exposta ≤ 0,3 — Figura 12": 1.8,
    "Edificação paralelepipédica fechada, vento normal à face maior — Figura 4": 1.3,
}

MASSA_ESPECIFICA_AR_FATOR = FATOR_PRESSAO_DINAMICA  # q = 0,613·Vk² (ar a 15 °C, 1 atm)


def _positivo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not valor > 0 or valor == float("inf"):
        raise ValueError(f"{nome} deve ser um número positivo.")
    return valor


@dataclass(frozen=True, slots=True)
class ResultadoVento:
    v0_m_s: float
    s1: float
    s2: float
    s3: float
    categoria: str
    classe: str
    altura_m: float
    vk_m_s: float
    pressao_N_m2: float
    coeficiente_arrasto: float
    area_efetiva_m2: float | None
    largura_exposta_m: float | None
    forca_kN: float | None
    carga_linear_kN_m: float | None
    memoria: tuple[str, ...] = field(default=())

    @property
    def pressao_kN_m2(self) -> float:
        return self.pressao_N_m2 / 1e3


def calcular_vento(
    v0_m_s: float,
    *,
    s1: float = 1.0,
    categoria: str = "II",
    classe: str = "A",
    altura_m: float = 10.0,
    grupo_s3: int = 3,
    s3: float | None = None,
    coeficiente_arrasto: float = 2.0,
    area_efetiva_m2: float | None = None,
    largura_exposta_m: float | None = None,
) -> ResultadoVento:
    """Velocidade característica, pressão dinâmica e força de arrasto.

    ``area_efetiva_m2`` dá a força total ``F = C_f·q·A_e``; ``largura_exposta_m``
    (altura do perfil ou da faixa exposta, em m) dá a carga por metro
    ``w = C_f·q·d`` para lançar numa barra do modelo. Os dois são opcionais.
    ``s3`` explícito sobrepõe o valor do grupo (por exemplo, o do Anexo B ou o critério do
    cliente).
    """
    no_local = calcular_vento_no_local(
        v0_m_s,
        s1=s1,
        categoria=categoria,
        classe=classe,
        altura_m=altura_m,
        grupo_s3=grupo_s3,
        s3=s3,
    )
    q = no_local.q_N_m2
    cf = _positivo("Cf", coeficiente_arrasto)
    forca = None
    carga_linear = None
    memoria = list(no_local.memoria)
    if area_efetiva_m2 is not None:
        area = _positivo("área efetiva", area_efetiva_m2)
        forca = cf * q * area / 1e3
        memoria.append(
            f"F = C_f·q·A_e = {numero_ptbr(cf)} × {numero_ptbr(q / 1e3, 3)} kN/m² × "
            f"{numero_ptbr(area, 3)} m² = {numero_ptbr(forca, 3)} kN"
        )
    if largura_exposta_m is not None:
        largura = _positivo("largura exposta", largura_exposta_m)
        carga_linear = cf * q * largura / 1e3
        memoria.append(
            f"w = C_f·q·d = {numero_ptbr(cf)} × {numero_ptbr(q / 1e3, 3)} kN/m² × "
            f"{numero_ptbr(largura, 3)} m = {numero_ptbr(carga_linear, 4)} kN/m"
        )
    return ResultadoVento(
        v0_m_s=no_local.v0_m_s,
        s1=no_local.s1,
        s2=no_local.s2,
        s3=no_local.s3,
        categoria=no_local.categoria,
        classe=no_local.classe or str(classe).strip().upper(),
        altura_m=float(altura_m),
        vk_m_s=no_local.vk_m_s,
        pressao_N_m2=q,
        coeficiente_arrasto=cf,
        area_efetiva_m2=None if area_efetiva_m2 is None else float(area_efetiva_m2),
        largura_exposta_m=None if largura_exposta_m is None else float(largura_exposta_m),
        forca_kN=forca,
        carga_linear_kN_m=carga_linear,
        memoria=tuple(memoria),
    )
