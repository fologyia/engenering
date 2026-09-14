"""Ações e requisitos de plataformas de acesso, passarelas e escadas industriais.

O que o memorial de uma plataforma costuma esquecer e o verificador sempre
cobra: a carga horizontal do guarda-corpo (NBR 6120 / NBR 14718), o impacto
de equipamentos, e a geometria de acesso da NR-12 — altura de guarda-corpo,
rodapé, travessa intermediária, largura útil, degraus pela fórmula de
Blondel e patamares. Os números aqui são os mínimos regulamentares usuais;
o critério do cliente pode ser mais exigente (por exemplo, guarda-corpo de
1,30 m em mineradoras) e por isso todo limite é parâmetro.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Cargas
# ---------------------------------------------------------------------------

# Carga horizontal uniforme no topo do guarda-corpo, kN/m.
CARGAS_GUARDA_CORPO_kN_m: dict[str, float] = {
    "Uso comum — plataformas, passarelas e escadas industriais (NBR 6120:2019; NBR 14718)": 1.0,
    "Locais com concentração de pessoas ou risco de aglomeração (NBR 6120:2019)": 2.0,
}
CARGA_CONCENTRADA_GUARDA_CORPO_kN = (
    1.0  # NBR 14718: força concentrada no corrimão, qualquer direção.
)

# Acréscimo dinâmico sobre a carga estática do equipamento (ASCE 7-22, 4.6.2),
# usado quando o cliente não fixa um coeficiente próprio.
COEFICIENTES_IMPACTO: dict[str, float] = {
    "Máquinas leves (motores, eixos)": 0.20,
    "Máquinas alternativas e unidades de potência": 0.50,
    "Suportes de pisos e passarelas pendurados": 0.33,
    "Máquinas de elevação (elevadores, talhas)": 1.00,
}

# ---------------------------------------------------------------------------
# Geometria de acesso (NR-12; NBR 9077 para a fórmula de Blondel)
# ---------------------------------------------------------------------------

ALTURA_MINIMA_GUARDA_CORPO_M = 1.10
ALTURA_MINIMA_RODAPE_M = 0.20
VAO_MAXIMO_ENTRE_TRAVESSAS_M = 0.40
LARGURA_MINIMA_PASSARELA_M = 0.60
BLONDEL_MINIMO_MM = 630.0
BLONDEL_MAXIMO_MM = 640.0
ALTURA_MAXIMA_ENTRE_PATAMARES_M = 3.00
INCLINACAO_ESCADA_GRAUS = (20.0, 45.0)


def _positivo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor <= 0:
        raise ValueError(f"{nome} deve ser um número positivo.")
    return valor


def _nao_negativo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor < 0:
        raise ValueError(f"{nome} deve ser um número maior ou igual a zero.")
    return valor


@dataclass(frozen=True, slots=True)
class EsforcosMontante:
    """Esforços que a carga do guarda-corpo entrega ao montante e à viga de borda."""

    carga_horizontal_kN_m: float
    altura_m: float
    espacamento_m: float
    forca_horizontal_kN: float
    momento_base_kNm: float
    forca_concentrada_kN: float
    momento_concentrado_kNm: float

    @property
    def momento_governante_kNm(self) -> float:
        return max(self.momento_base_kNm, self.momento_concentrado_kNm)


def esforcos_no_montante(
    carga_horizontal_kN_m: float,
    altura_m: float,
    espacamento_m: float,
    *,
    carga_concentrada_kN: float = CARGA_CONCENTRADA_GUARDA_CORPO_kN,
) -> EsforcosMontante:
    """Montante em balanço: ``H = q·s`` e ``M = q·s·h`` na base; ``P·h`` da concentrada.

    O momento de base é o que a ligação do montante e a viga de borda
    precisam absorver (torção na viga de borda quando o montante está na
    lateral — outro motivo para travar a torção de um perfil U).
    """
    q = _nao_negativo("carga horizontal", carga_horizontal_kN_m)
    h = _positivo("altura do guarda-corpo", altura_m)
    s = _positivo("espaçamento entre montantes", espacamento_m)
    p = _nao_negativo("carga concentrada", carga_concentrada_kN)
    return EsforcosMontante(
        carga_horizontal_kN_m=q,
        altura_m=h,
        espacamento_m=s,
        forca_horizontal_kN=q * s,
        momento_base_kNm=q * s * h,
        forca_concentrada_kN=p,
        momento_concentrado_kNm=p * h,
    )


def carga_com_impacto(carga_estatica_kN: float, coeficiente_impacto: float) -> float:
    """``(1 + i)·P``: o acréscimo dinâmico entra na mesma categoria da carga do equipamento."""
    return _nao_negativo("carga estática", carga_estatica_kN) * (
        1.0 + _nao_negativo("coeficiente de impacto", coeficiente_impacto)
    )


@dataclass(frozen=True, slots=True)
class ItemConformidade:
    requisito: str
    valor: str
    limite: str
    atende: bool
    fonte: str


def _item(
    requisito: str, valor: float, limite: float, atende: bool, fonte: str, unidade: str = "m"
) -> ItemConformidade:
    return ItemConformidade(
        requisito=requisito,
        valor=f"{valor:.2f} {unidade}",
        limite=f"{limite:.2f} {unidade}",
        atende=atende,
        fonte=fonte,
    )


def verificar_guarda_corpo(
    altura_m: float,
    rodape_m: float,
    vao_entre_travessas_m: float,
    *,
    altura_minima_m: float = ALTURA_MINIMA_GUARDA_CORPO_M,
    rodape_minimo_m: float = ALTURA_MINIMA_RODAPE_M,
    vao_maximo_m: float = VAO_MAXIMO_ENTRE_TRAVESSAS_M,
) -> list[ItemConformidade]:
    """Altura, rodapé e vão entre travessas do guarda-corpo (NR-12).

    ``altura_minima_m`` aceita o critério do cliente quando ele supera a NR-12.
    """
    altura = _positivo("altura do guarda-corpo", altura_m)
    rodape = _nao_negativo("altura do rodapé", rodape_m)
    vao = _positivo("vão entre travessas", vao_entre_travessas_m)
    minimo = _positivo("altura mínima", altura_minima_m)
    fonte_altura = "NR-12" + (
        f" (mínimo 1,10 m) e critério do projeto ({minimo:.2f} m)"
        if minimo > ALTURA_MINIMA_GUARDA_CORPO_M + 1e-9
        else ""
    )
    return [
        _item(
            "Altura do guarda-corpo ≥ mínimo", altura, minimo, altura >= minimo - 1e-9, fonte_altura
        ),
        _item(
            "Rodapé ≥ mínimo", rodape, rodape_minimo_m, rodape >= rodape_minimo_m - 1e-9, "NR-12"
        ),
        _item(
            "Vão livre entre travessas ≤ máximo (ou tela)",
            vao,
            vao_maximo_m,
            vao <= vao_maximo_m + 1e-9,
            "NR-12",
        ),
    ]


def verificar_passarela(
    largura_util_m: float, *, largura_minima_m: float = LARGURA_MINIMA_PASSARELA_M
) -> list[ItemConformidade]:
    largura = _positivo("largura útil", largura_util_m)
    return [
        _item(
            "Largura útil da passarela/plataforma ≥ mínimo",
            largura,
            largura_minima_m,
            largura >= largura_minima_m - 1e-9,
            "NR-12",
        )
    ]


def verificar_escada(
    espelho_mm: float,
    piso_mm: float,
    *,
    altura_entre_patamares_m: float | None = None,
    largura_util_m: float | None = None,
    blondel_minimo_mm: float = BLONDEL_MINIMO_MM,
    blondel_maximo_mm: float = BLONDEL_MAXIMO_MM,
    altura_maxima_entre_patamares_m: float = ALTURA_MAXIMA_ENTRE_PATAMARES_M,
    largura_minima_m: float = LARGURA_MINIMA_PASSARELA_M,
) -> list[ItemConformidade]:
    """Degraus pela fórmula de Blondel ``2h + b``, inclinação, patamares e largura."""
    h = _positivo("espelho", espelho_mm)
    b = _positivo("piso do degrau", piso_mm)
    blondel = 2.0 * h + b
    inclinacao = math.degrees(math.atan2(h, b))
    itens = [
        ItemConformidade(
            requisito="Fórmula de Blondel 2h + b dentro da faixa",
            valor=f"{blondel:.0f} mm",
            limite=f"{blondel_minimo_mm:.0f} a {blondel_maximo_mm:.0f} mm",
            atende=blondel_minimo_mm - 1e-9 <= blondel <= blondel_maximo_mm + 1e-9,
            fonte="NR-12; NBR 9077",
        ),
        ItemConformidade(
            requisito="Inclinação da escada de degraus",
            valor=f"{inclinacao:.1f}°",
            limite=f"{INCLINACAO_ESCADA_GRAUS[0]:.0f}° a {INCLINACAO_ESCADA_GRAUS[1]:.0f}°",
            atende=INCLINACAO_ESCADA_GRAUS[0] - 1e-9
            <= inclinacao
            <= INCLINACAO_ESCADA_GRAUS[1] + 1e-9,
            fonte="NR-12",
        ),
    ]
    if altura_entre_patamares_m is not None:
        altura = _positivo("altura entre patamares", altura_entre_patamares_m)
        itens.append(
            _item(
                "Altura vencida entre patamares ≤ máximo",
                altura,
                altura_maxima_entre_patamares_m,
                altura <= altura_maxima_entre_patamares_m + 1e-9,
                "NR-12",
            )
        )
    if largura_util_m is not None:
        largura = _positivo("largura útil da escada", largura_util_m)
        itens.append(
            _item(
                "Largura útil da escada ≥ mínimo",
                largura,
                largura_minima_m,
                largura >= largura_minima_m - 1e-9,
                "NR-12",
            )
        )
    return itens
