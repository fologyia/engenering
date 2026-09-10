"""Análise de sensibilidade e incerteza para modelos industriais auditáveis."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class EntradaModelo:
    chave: str
    rotulo: str
    unidade: str
    padrao: float
    minimo: float | None = None
    maximo: float | None = None


@dataclass(frozen=True)
class ModeloSensibilidade:
    id: str
    titulo: str
    descricao: str
    equacao: str
    saida: str
    unidade_saida: str
    melhor_quando: str
    entradas: tuple[EntradaModelo, ...]
    calcular: Callable[[Mapping[str, float]], float]


def _axial(x: Mapping[str, float]) -> float:
    return x["forca_kN"] * 1_000.0 / x["area_mm2"]


def _vaso(x: Mapping[str, float]) -> float:
    return x["pressao_MPa"] * x["diametro_mm"] / (2.0 * x["espessura_mm"])


def _flexao(x: Mapping[str, float]) -> float:
    return x["momento_kNm"] * 1_000_000.0 / x["modulo_resistente_mm3"]


def _flecha(x: Mapping[str, float]) -> float:
    # 1 kN/m = 1 N/mm; E em GPa é convertido para N/mm².
    return 5.0 * x["carga_kN_m"] * x["vao_mm"] ** 4 / (
        384.0 * x["E_GPa"] * 1_000.0 * x["inercia_mm4"]
    )


def _termica(x: Mapping[str, float]) -> float:
    return x["alpha_um_mC"] * 1e-6 * x["delta_T_C"] * x["comprimento_mm"]


def _von_mises(x: Mapping[str, float]) -> float:
    return math.sqrt(
        x["sigma_x_MPa"] ** 2
        - x["sigma_x_MPa"] * x["sigma_y_MPa"]
        + x["sigma_y_MPa"] ** 2
        + 3.0 * x["tau_xy_MPa"] ** 2
    )


def _seguranca_vm(x: Mapping[str, float]) -> float:
    equivalente = _von_mises(x)
    return x["Sy_MPa"] / equivalente if equivalente > 0 else math.inf


def _goodman(x: Mapping[str, float]) -> float:
    denominador = x["sigma_a_MPa"] / x["Se_MPa"] + x["sigma_m_MPa"] / x["Sut_MPa"]
    if denominador <= 0:
        return math.inf
    return 1.0 / denominador


def _utilizacao(x: Mapping[str, float]) -> float:
    return x["demanda"] / x["capacidade"]


def _carga_critica_euler(x: Mapping[str, float]) -> float:
    comprimento_efetivo_mm = x["K"] * x["L_mm"]
    return math.pi**2 * x["E_GPa"] * 1_000.0 * x["I_mm4"] / comprimento_efetivo_mm**2


MODELOS: dict[str, ModeloSensibilidade] = {
    "tensao_axial": ModeloSensibilidade(
        "tensao_axial", "Tensão axial média", "Barra, tirante ou área resistente sob força normal.",
        "σ = F / A", "Tensão axial", "MPa", "menor",
        (EntradaModelo("forca_kN", "Força axial", "kN", 100.0), EntradaModelo("area_mm2", "Área resistente", "mm²", 1_000.0, 1e-9)), _axial,
    ),
    "vaso_parede_fina": ModeloSensibilidade(
        "vaso_parede_fina", "Tensão circunferencial em vaso", "Triagem de cilindro de parede fina sob pressão interna.",
        "σh = p D / (2 t)", "Tensão circunferencial", "MPa", "menor",
        (
            EntradaModelo("pressao_MPa", "Pressão de projeto", "MPa", 1.0, 0.0),
            EntradaModelo("diametro_mm", "Diâmetro adotado", "mm", 1_000.0, 1e-9),
            EntradaModelo("espessura_mm", "Espessura resistente", "mm", 10.0, 1e-9),
        ), _vaso,
    ),
    "tensao_flexao": ModeloSensibilidade(
        "tensao_flexao", "Tensão de flexão", "Seção estrutural sob momento fletor.",
        "σ = M / W", "Tensão de flexão", "MPa", "menor",
        (EntradaModelo("momento_kNm", "Momento fletor", "kN·m", 25.0), EntradaModelo("modulo_resistente_mm3", "Módulo resistente", "mm³", 250_000.0, 1e-9)), _flexao,
    ),
    "flecha_viga": ModeloSensibilidade(
        "flecha_viga", "Flecha de viga biapoiada", "Viga prismática com carga uniformemente distribuída.",
        "δmax = 5 q L⁴ / (384 E I)", "Flecha máxima", "mm", "menor",
        (
            EntradaModelo("carga_kN_m", "Carga distribuída", "kN/m", 5.0),
            EntradaModelo("vao_mm", "Vão", "mm", 4_000.0, 1e-9),
            EntradaModelo("E_GPa", "Módulo de elasticidade", "GPa", 200.0, 1e-9),
            EntradaModelo("inercia_mm4", "Momento de inércia", "mm⁴", 80_000_000.0, 1e-9),
        ), _flecha,
    ),
    "dilatacao_termica": ModeloSensibilidade(
        "dilatacao_termica", "Dilatação térmica livre", "Variação dimensional sem restrição mecânica.",
        "ΔL = α ΔT L", "Variação de comprimento", "mm", "menor",
        (
            EntradaModelo("alpha_um_mC", "Coeficiente de expansão", "µm/(m·°C)", 12.0),
            EntradaModelo("delta_T_C", "Variação de temperatura", "°C", 80.0),
            EntradaModelo("comprimento_mm", "Comprimento", "mm", 6_000.0, 1e-9),
        ), _termica,
    ),
    "von_mises": ModeloSensibilidade(
        "von_mises", "Tensão equivalente de von Mises", "Estado plano de tensões no ponto crítico.",
        "σvm = √(σx² − σxσy + σy² + 3τxy²)", "Tensão equivalente", "MPa", "menor",
        (
            EntradaModelo("sigma_x_MPa", "Tensão σx", "MPa", 120.0),
            EntradaModelo("sigma_y_MPa", "Tensão σy", "MPa", 30.0),
            EntradaModelo("tau_xy_MPa", "Cisalhamento τxy", "MPa", 25.0),
        ), _von_mises,
    ),
    "seguranca_vm": ModeloSensibilidade(
        "seguranca_vm", "Fator de segurança ao escoamento", "Razão entre Sy e a tensão equivalente de von Mises.",
        "n = Sy / σvm", "Fator de segurança", "-", "maior",
        (
            EntradaModelo("sigma_x_MPa", "Tensão σx", "MPa", 120.0),
            EntradaModelo("sigma_y_MPa", "Tensão σy", "MPa", 30.0),
            EntradaModelo("tau_xy_MPa", "Cisalhamento τxy", "MPa", 25.0),
            EntradaModelo("Sy_MPa", "Limite de escoamento", "MPa", 250.0, 1e-9),
        ), _seguranca_vm,
    ),
    "goodman": ModeloSensibilidade(
        "goodman", "Fator de segurança de Goodman", "Sensibilidade do ponto de fadiga às resistências e tensões adotadas.",
        "1/n = σa/Se + σm/Sut", "Fator de segurança de Goodman", "-", "maior",
        (
            EntradaModelo("sigma_a_MPa", "Tensão alternada", "MPa", 80.0, 0.0),
            EntradaModelo("sigma_m_MPa", "Tensão média", "MPa", 50.0),
            EntradaModelo("Se_MPa", "Limite de fadiga corrigido", "MPa", 180.0, 1e-9),
            EntradaModelo("Sut_MPa", "Resistência à tração", "MPa", 450.0, 1e-9),
        ), _goodman,
    ),
    "utilizacao": ModeloSensibilidade(
        "utilizacao", "Índice demanda/capacidade", "Modelo universal para ações, resistência, vazão, potência ou outro par compatível.",
        "U = demanda / capacidade", "Índice de utilização", "-", "menor",
        (EntradaModelo("demanda", "Demanda", "unidade consistente", 80.0), EntradaModelo("capacidade", "Capacidade", "mesma unidade", 100.0, 1e-9)), _utilizacao,
    ),
    "carga_critica_euler": ModeloSensibilidade(
        "carga_critica_euler", "Carga crítica de flambagem (Euler)", "Coluna esbelta sob compressão centrada; sensibilidade do comprimento destravado e da rigidez.",
        "Pcr = π²EI / (KL)²", "Carga crítica", "N", "maior",
        (
            EntradaModelo("E_GPa", "Módulo de elasticidade", "GPa", 200.0, 1e-9),
            EntradaModelo("I_mm4", "Momento de inércia", "mm⁴", 500_000.0, 1e-9),
            EntradaModelo("K", "Fator de comprimento efetivo", "-", 1.0, 1e-9),
            EntradaModelo("L_mm", "Comprimento real", "mm", 2_000.0, 1e-9),
        ), _carga_critica_euler,
    ),
}


DISTRIBUICOES = ("Uniforme", "Normal", "Triangular")


def listar_modelos() -> list[ModeloSensibilidade]:
    return list(MODELOS.values())


def obter_modelo(modelo_id: str) -> ModeloSensibilidade:
    try:
        return MODELOS[str(modelo_id)]
    except KeyError as erro:
        raise ValueError(f"Modelo de sensibilidade desconhecido: {modelo_id}") from erro


def _validar_entradas(modelo: ModeloSensibilidade, entradas: Mapping[str, Any]) -> dict[str, float]:
    normalizadas: dict[str, float] = {}
    for especificacao in modelo.entradas:
        try:
            valor = float(entradas[especificacao.chave])
        except (KeyError, TypeError, ValueError) as erro:
            raise ValueError(f"Informe um valor numérico para {especificacao.rotulo}.") from erro
        if not math.isfinite(valor):
            raise ValueError(f"{especificacao.rotulo} deve ser finito.")
        if especificacao.minimo is not None and valor < especificacao.minimo:
            raise ValueError(f"{especificacao.rotulo} deve ser ≥ {especificacao.minimo:g} {especificacao.unidade}.")
        if especificacao.maximo is not None and valor > especificacao.maximo:
            raise ValueError(f"{especificacao.rotulo} deve ser ≤ {especificacao.maximo:g} {especificacao.unidade}.")
        normalizadas[especificacao.chave] = valor
    return normalizadas


def calcular_saida(modelo_id: str, entradas: Mapping[str, Any]) -> float:
    modelo = obter_modelo(modelo_id)
    valores = _validar_entradas(modelo, entradas)
    try:
        resultado = float(modelo.calcular(valores))
    except (ArithmeticError, OverflowError, ValueError, ZeroDivisionError) as erro:
        raise ValueError(f"O modelo não pôde ser avaliado: {erro}") from erro
    if not math.isfinite(resultado):
        raise ValueError("O resultado nominal não é finito; revise tensões, resistências e denominadores.")
    return resultado


def analisar_oat(
    modelo_id: str,
    entradas: Mapping[str, Any],
    *,
    variacao_percentual: float = 10.0,
    pontos_curva: int = 13,
) -> dict[str, Any]:
    """Varia uma entrada por vez e calcula elasticidade local e faixa de efeito."""
    modelo = obter_modelo(modelo_id)
    valores = _validar_entradas(modelo, entradas)
    variacao = float(variacao_percentual) / 100.0
    if not (0 < variacao <= 0.9):
        raise ValueError("A variação OAT deve estar entre 0 e 90%.")
    base = calcular_saida(modelo_id, valores)
    ranking: list[dict[str, Any]] = []
    curvas: dict[str, list[dict[str, float]]] = {}

    for especificacao in modelo.entradas:
        x0 = valores[especificacao.chave]
        escala = abs(x0) if abs(x0) > 1e-12 else 1.0
        delta = variacao * escala
        xmin = x0 - delta
        xmax = x0 + delta
        if especificacao.minimo is not None:
            xmin = max(xmin, especificacao.minimo)
        if especificacao.maximo is not None:
            xmax = min(xmax, especificacao.maximo)
        if math.isclose(xmin, xmax):
            raise ValueError(f"Não há faixa válida para variar {especificacao.rotulo}.")

        menos = dict(valores)
        mais = dict(valores)
        menos[especificacao.chave] = xmin
        mais[especificacao.chave] = xmax
        ymenos = calcular_saida(modelo_id, menos)
        ymais = calcular_saida(modelo_id, mais)
        amplitude_relativa = abs(ymais - ymenos) / max(abs(base), 1e-12) * 100.0
        derivada = (ymais - ymenos) / (xmax - xmin)
        elasticidade = derivada * escala / max(abs(base), 1e-12)
        pior = min(ymenos, ymais) if modelo.melhor_quando == "maior" else max(ymenos, ymais)
        melhor = max(ymenos, ymais) if modelo.melhor_quando == "maior" else min(ymenos, ymais)
        ranking.append(
            {
                "chave": especificacao.chave,
                "variavel": especificacao.rotulo,
                "unidade": especificacao.unidade,
                "nominal": x0,
                "saida_menos": ymenos,
                "saida_mais": ymais,
                "pior_saida": pior,
                "melhor_saida": melhor,
                "impacto_percentual": amplitude_relativa,
                "elasticidade": elasticidade,
                "direcao_critica": "aumentar" if pior == ymais else "reduzir",
            }
        )

        pontos = []
        for x in np.linspace(xmin, xmax, max(5, int(pontos_curva))):
            caso = dict(valores)
            caso[especificacao.chave] = float(x)
            pontos.append({"entrada": float(x), "saida": calcular_saida(modelo_id, caso)})
        curvas[especificacao.chave] = pontos

    ranking.sort(key=lambda item: item["impacto_percentual"], reverse=True)
    return {
        "modelo_id": modelo.id,
        "saida_nominal": base,
        "unidade_saida": modelo.unidade_saida,
        "variacao_percentual": float(variacao_percentual),
        "ranking": ranking,
        "curvas": curvas,
    }


def _amostrar(
    rng: np.random.Generator,
    nominal: float,
    incerteza_pct: float,
    distribuicao: str,
    tamanho: int,
    minimo: float | None,
    maximo: float | None,
) -> np.ndarray:
    escala = max(abs(nominal), 1.0) * max(float(incerteza_pct), 0.0) / 100.0
    if distribuicao == "Normal":
        amostra = rng.normal(nominal, escala, tamanho)
    elif distribuicao == "Triangular":
        amostra = rng.triangular(nominal - escala, nominal, nominal + escala, tamanho)
    else:
        amostra = rng.uniform(nominal - escala, nominal + escala, tamanho)
    if minimo is not None:
        amostra = np.maximum(amostra, minimo)
    if maximo is not None:
        amostra = np.minimum(amostra, maximo)
    return amostra


def analisar_monte_carlo(
    modelo_id: str,
    entradas: Mapping[str, Any],
    configuracao_incerteza: Mapping[str, Mapping[str, Any]],
    *,
    amostras: int = 3_000,
    semente: int = 42,
    criterio: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Propaga incertezas informadas; não atribui distribuições por conta própria."""
    modelo = obter_modelo(modelo_id)
    valores = _validar_entradas(modelo, entradas)
    quantidade = int(amostras)
    if not (200 <= quantidade <= 50_000):
        raise ValueError("Use entre 200 e 50.000 amostras.")
    rng = np.random.default_rng(int(semente))
    amostras_entradas: dict[str, np.ndarray] = {}
    for especificacao in modelo.entradas:
        config = configuracao_incerteza.get(especificacao.chave, {})
        distribuicao = str(config.get("distribuicao", "Uniforme"))
        if distribuicao not in DISTRIBUICOES:
            raise ValueError(f"Distribuição inválida para {especificacao.rotulo}.")
        amostras_entradas[especificacao.chave] = _amostrar(
            rng,
            valores[especificacao.chave],
            float(config.get("incerteza_percentual", 0.0)),
            distribuicao,
            quantidade,
            especificacao.minimo,
            especificacao.maximo,
        )

    saidas = np.empty(quantidade, dtype=float)
    for indice in range(quantidade):
        caso = {chave: float(valores_amostra[indice]) for chave, valores_amostra in amostras_entradas.items()}
        try:
            saidas[indice] = float(modelo.calcular(caso))
        except (ArithmeticError, OverflowError, ValueError, ZeroDivisionError):
            saidas[indice] = np.nan
    validas = np.isfinite(saidas)
    if validas.mean() < 0.99:
        raise ValueError("Mais de 1% das amostras produziram resultado inválido; reduza as incertezas ou revise o domínio.")
    saidas = saidas[validas]
    entrada_df = pd.DataFrame({chave: valores_amostra[validas] for chave, valores_amostra in amostras_entradas.items()})
    entrada_df["saida"] = saidas
    correlacoes = entrada_df.rank(pct=True).corr()["saida"].drop("saida").sort_values(key=abs, ascending=False)

    probabilidade = None
    criterio_normalizado = None
    if criterio and bool(criterio.get("ativo", False)):
        operador = str(criterio.get("operador", "<="))
        limite = float(criterio.get("limite"))
        if operador == "<=":
            falhas = saidas > limite
        elif operador == ">=":
            falhas = saidas < limite
        else:
            raise ValueError("O critério deve usar <= ou >=.")
        probabilidade = float(np.mean(falhas) * 100.0)
        criterio_normalizado = {"ativo": True, "operador": operador, "limite": limite}

    limite_grafico = min(5_000, len(saidas))
    return {
        "amostras_solicitadas": quantidade,
        "amostras_validas": int(len(saidas)),
        "semente": int(semente),
        "media": float(np.mean(saidas)),
        "desvio_padrao": float(np.std(saidas, ddof=1)),
        "p05": float(np.quantile(saidas, 0.05)),
        "p50": float(np.quantile(saidas, 0.50)),
        "p95": float(np.quantile(saidas, 0.95)),
        "minimo": float(np.min(saidas)),
        "maximo": float(np.max(saidas)),
        "probabilidade_nao_atendimento_pct": probabilidade,
        "criterio": criterio_normalizado,
        "correlacoes_spearman": [
            {"chave": chave, "variavel": next(item.rotulo for item in modelo.entradas if item.chave == chave), "correlacao": float(valor)}
            for chave, valor in correlacoes.items()
        ],
        "amostra_saida": [float(valor) for valor in saidas[:limite_grafico]],
        "aviso": "Resultado probabilístico condicionado às distribuições, faixas e independência informadas pelo usuário.",
    }


def sugerir_de_registro(registro: Mapping[str, Any]) -> dict[str, Any] | None:
    """Mapeia registros conhecidos sem ocultar campos faltantes.

    Prefere o ``modulo_id`` estável do contrato técnico; o texto do título
    continua servindo de fallback para registros antigos que não tinham
    esse campo.
    """
    modulo_id = str(registro.get("modulo_id", "")).strip().casefold()
    modulo = str(registro.get("modulo", "")).casefold()
    entradas = registro.get("entradas", {}) if isinstance(registro.get("entradas"), Mapping) else {}
    resultados = registro.get("resultados", {}) if isinstance(registro.get("resultados"), Mapping) else {}
    if modulo_id == "analise_estatica" or (not modulo_id and ("estática" in modulo or "estatica" in modulo)):
        return {
            "modelo_id": "seguranca_vm",
            "entradas": {
                "sigma_x_MPa": entradas.get("sigma_x_MPa"),
                "sigma_y_MPa": entradas.get("sigma_y_MPa"),
                "tau_xy_MPa": entradas.get("tau_xy_MPa"),
                "Sy_MPa": entradas.get("Sy_MPa"),
            },
        }
    if modulo_id == "circulo_mohr" and "sigma_x_MPa" in entradas and "sigma_z_MPa" not in entradas:
        return {
            "modelo_id": "seguranca_vm",
            "entradas": {
                "sigma_x_MPa": entradas.get("sigma_x_MPa"),
                "sigma_y_MPa": entradas.get("sigma_y_MPa"),
                "tau_xy_MPa": entradas.get("tau_xy_MPa"),
            },
        }
    if modulo_id == "analise_fadiga" or (not modulo_id and "fadiga" in modulo):
        return {
            "modelo_id": "goodman",
            "entradas": {
                "sigma_a_MPa": resultados.get("sigma_a_efetiva_MPa", entradas.get("sigma_a_nominal_MPa")),
                "sigma_m_MPa": entradas.get("sigma_m_MPa"),
                "Se_MPa": resultados.get("Se_corrigido_MPa"),
                "Sut_MPa": entradas.get("Sut_MPa"),
            },
        }
    if modulo_id == "vigas_eixos":
        # A seção governante da barra já vem resolvida no registro; o que a
        # sensibilidade precisa é do par (tensão equivalente, resistência).
        return {
            "modelo_id": "seguranca_vm",
            "entradas": {
                "sigma_x_MPa": resultados.get("tensao_normal_extrema_MPa"),
                "sigma_y_MPa": 0.0,
                "tau_xy_MPa": resultados.get("tensao_torcao_maxima_MPa"),
                "Sy_MPa": (entradas.get("material") or {}).get("escoamento_MPa")
                if isinstance(entradas.get("material"), Mapping)
                else None,
            },
        }
    if modulo_id == "flambagem_colunas":
        eixo = str(resultados.get("eixo_governante") or "x")
        raio = entradas.get(f"raio_giracao_{eixo}_mm")
        area = entradas.get("area_mm2")
        inercia = None
        if raio is not None and area is not None:
            try:
                inercia = float(area) * float(raio) ** 2
            except (TypeError, ValueError):
                inercia = None
        modulo_elasticidade = entradas.get("modulo_elasticidade_MPa")
        return {
            "modelo_id": "carga_critica_euler",
            "entradas": {
                "E_GPa": modulo_elasticidade / 1_000.0 if modulo_elasticidade else None,
                "I_mm4": inercia,
                "K": entradas.get("kx" if eixo == "x" else "ky"),
                "L_mm": entradas.get("comprimento_mm"),
            },
        }
    return None
