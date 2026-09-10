"""Conversor geral de unidades para entradas e resultados de engenharia."""

import math
from dataclasses import dataclass

MPA_PER_KSI = 6.894757293168
MM_PER_IN = 25.4


@dataclass(frozen=True)
class Unidade:
    """Conversão linear para a unidade-base de uma categoria."""

    simbolo: str
    fator: float
    deslocamento: float = 0.0

    def para_base(self, valor: float) -> float:
        return valor * self.fator + self.deslocamento

    def da_base(self, valor: float) -> float:
        return (valor - self.deslocamento) / self.fator


# As bases coincidem com as unidades mais usadas no aplicativo.
CATEGORIAS: dict[str, dict[str, Unidade]] = {
    "Comprimento": {
        "mm": Unidade("mm", 1.0),
        "cm": Unidade("cm", 10.0),
        "m": Unidade("m", 1_000.0),
        "in": Unidade("in", MM_PER_IN),
        "ft": Unidade("ft", 304.8),
    },
    "Área": {
        "mm²": Unidade("mm²", 1.0),
        "cm²": Unidade("cm²", 100.0),
        "m²": Unidade("m²", 1_000_000.0),
        "in²": Unidade("in²", MM_PER_IN**2),
        "ft²": Unidade("ft²", 304.8**2),
    },
    "Volume": {
        "mm³": Unidade("mm³", 1.0),
        "cm³": Unidade("cm³", 1_000.0),
        "m³": Unidade("m³", 1_000_000_000.0),
        "L": Unidade("L", 1_000_000.0),
        "in³": Unidade("in³", MM_PER_IN**3),
        "ft³": Unidade("ft³", 304.8**3),
    },
    "Força": {
        "N": Unidade("N", 1.0),
        "kN": Unidade("kN", 1_000.0),
        "kgf": Unidade("kgf", 9.80665),
        "lbf": Unidade("lbf", 4.4482216152605),
        "kip": Unidade("kip", 4_448.2216152605),
    },
    "Tensão e pressão": {
        "Pa": Unidade("Pa", 1e-6),
        "kPa": Unidade("kPa", 1e-3),
        "MPa": Unidade("MPa", 1.0),
        "GPa": Unidade("GPa", 1_000.0),
        "bar": Unidade("bar", 0.1),
        "psi": Unidade("psi", 0.006894757293168),
        "ksi": Unidade("ksi", MPA_PER_KSI),
        "kgf/cm²": Unidade("kgf/cm²", 0.0980665),
    },
    "Momento e torque": {
        "N·mm": Unidade("N·mm", 0.001),
        "N·m": Unidade("N·m", 1.0),
        "kN·m": Unidade("kN·m", 1_000.0),
        "kgf·m": Unidade("kgf·m", 9.80665),
        "lbf·in": Unidade("lbf·in", 0.1129848290276),
        "lbf·ft": Unidade("lbf·ft", 1.3558179483314),
    },
    "Carga distribuída": {
        "N/m": Unidade("N/m", 0.001),
        "N/mm": Unidade("N/mm", 1.0),
        "kN/m": Unidade("kN/m", 1.0),
        "kgf/m": Unidade("kgf/m", 0.00980665),
        "lbf/ft": Unidade("lbf/ft", 0.0145939029372),
    },
    "Massa": {
        "g": Unidade("g", 0.001),
        "kg": Unidade("kg", 1.0),
        "t": Unidade("t", 1_000.0),
        "lb": Unidade("lb", 0.45359237),
    },
    "Densidade": {
        "kg/m³": Unidade("kg/m³", 1.0),
        "g/cm³": Unidade("g/cm³", 1_000.0),
        "kg/L": Unidade("kg/L", 1_000.0),
        "lb/ft³": Unidade("lb/ft³", 16.01846337396),
        "lb/in³": Unidade("lb/in³", 27_679.9047102),
    },
    "Temperatura": {
        "°C": Unidade("°C", 1.0, 0.0),
        "°F": Unidade("°F", 5.0 / 9.0, -160.0 / 9.0),
        "K": Unidade("K", 1.0, -273.15),
    },
    "Ângulo": {
        "grau": Unidade("grau", math.pi / 180.0),
        "rad": Unidade("rad", 1.0),
    },
    "Rotação": {
        "rpm": Unidade("rpm", 2.0 * math.pi / 60.0),
        "Hz": Unidade("Hz", 2.0 * math.pi),
        "rad/s": Unidade("rad/s", 1.0),
    },
    "Velocidade": {
        "mm/s": Unidade("mm/s", 0.001),
        "m/s": Unidade("m/s", 1.0),
        "km/h": Unidade("km/h", 1.0 / 3.6),
        "ft/s": Unidade("ft/s", 0.3048),
        "mph": Unidade("mph", 0.44704),
    },
    "Potência": {
        "W": Unidade("W", 1.0),
        "kW": Unidade("kW", 1_000.0),
        "MW": Unidade("MW", 1_000_000.0),
        "cv": Unidade("cv", 735.49875),
        "hp": Unidade("hp", 745.699871582),
    },
    "Energia": {
        "J": Unidade("J", 1.0),
        "kJ": Unidade("kJ", 1_000.0),
        "MJ": Unidade("MJ", 1_000_000.0),
        "N·mm": Unidade("N·mm", 0.001),
        "kWh": Unidade("kWh", 3_600_000.0),
        "BTU": Unidade("BTU", 1_055.05585262),
    },
}


PARES_PADRAO: dict[str, tuple[str, str]] = {
    "Comprimento": ("mm", "in"),
    "Área": ("mm²", "cm²"),
    "Volume": ("cm³", "L"),
    "Força": ("kN", "N"),
    "Tensão e pressão": ("MPa", "psi"),
    "Momento e torque": ("N·m", "kN·m"),
    "Carga distribuída": ("kN/m", "N/mm"),
    "Massa": ("kg", "lb"),
    "Densidade": ("kg/m³", "g/cm³"),
    "Temperatura": ("°C", "°F"),
    "Ângulo": ("grau", "rad"),
    "Rotação": ("rpm", "rad/s"),
    "Velocidade": ("m/s", "km/h"),
    "Potência": ("kW", "hp"),
    "Energia": ("kJ", "BTU"),
}


def listar_categorias() -> list[str]:
    return list(CATEGORIAS)


def listar_unidades(categoria: str) -> list[str]:
    try:
        return list(CATEGORIAS[categoria])
    except KeyError as erro:
        raise ValueError(f"Categoria de unidade desconhecida: {categoria}.") from erro


def converter(valor: float, categoria: str, origem: str, destino: str) -> float:
    """Converte ``valor`` entre duas unidades da mesma categoria."""
    if not math.isfinite(valor):
        raise ValueError("O valor a converter deve ser finito.")
    try:
        unidades = CATEGORIAS[categoria]
    except KeyError as erro:
        raise ValueError(f"Categoria de unidade desconhecida: {categoria}.") from erro
    try:
        unidade_origem = unidades[origem]
        unidade_destino = unidades[destino]
    except KeyError as erro:
        raise ValueError(
            f"Unidade {erro.args[0]!r} não pertence à categoria {categoria!r}."
        ) from erro
    valor_base = unidade_origem.para_base(float(valor))
    return unidade_destino.da_base(valor_base)


def conversoes_da_categoria(
    valor: float, categoria: str, origem: str
) -> list[tuple[str, float]]:
    """Converte um valor para todas as unidades da categoria."""
    return [
        (destino, converter(valor, categoria, origem, destino))
        for destino in listar_unidades(categoria)
    ]
