"""Catálogo de referência e materiais rastreáveis de projetos industriais.

O catálogo CSV continua sendo uma fonte prática para estimativas preliminares,
mas nunca é promovido automaticamente a dado aprovado. Materiais de projeto
carregam condição de fornecimento, propriedades, origem e evidências próprias.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

CAMINHO_CATALOGO = Path(__file__).resolve().parents[1] / "data" / "materials.csv"

TIPOS_ORIGEM = (
    "Certificado do lote / MTR",
    "Relatório de ensaio",
    "Norma ou especificação",
    "Ficha técnica do fabricante",
    "Literatura técnica",
    "Valor típico / estimativa",
)

NIVEIS_CONFIANCA = ("Confirmado", "Rastreável", "Condicional", "Referência")

PROPRIEDADES = {
    "Sut_MPa": ("Resistência à tração", "MPa"),
    "Sy_MPa": ("Limite de escoamento", "MPa"),
    "E_GPa": ("Módulo de elasticidade", "GPa"),
    "nu": ("Coeficiente de Poisson", "-"),
    "densidade_kg_m3": ("Densidade", "kg/m³"),
    "temperatura_min_C": ("Temperatura mínima qualificada", "°C"),
    "temperatura_max_C": ("Temperatura máxima qualificada", "°C"),
}


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def _numero(valor: Any) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


@lru_cache(maxsize=1)
def _carregar_catalogo_cache() -> tuple[dict[str, Any], ...]:
    if not CAMINHO_CATALOGO.exists():
        raise FileNotFoundError(f"Catálogo de materiais não encontrado: {CAMINHO_CATALOGO}")
    dataframe = pd.read_csv(CAMINHO_CATALOGO)
    registros: list[dict[str, Any]] = []
    for indice, linha in dataframe.iterrows():
        nome = _texto(linha.get("nome"))
        categoria = _texto(linha.get("categoria"))
        registros.append(
            {
                "id": f"catalogo-{indice + 1:03d}",
                "origem_registro": "catalogo_referencia",
                "nome": nome,
                "familia": categoria.replace("_", " ").title(),
                "condicao": _inferir_condicao(nome),
                "forma_produto": "Confirmar no documento de compra",
                "lote": "",
                "propriedades": {
                    "Sut_MPa": _numero(linha.get("Sut_MPa")),
                    "Sy_MPa": _numero(linha.get("Sy_MPa")),
                    "E_GPa": None,
                    "nu": None,
                    "densidade_kg_m3": None,
                    "temperatura_min_C": None,
                    "temperatura_max_C": None,
                },
                "origem_tipo": "Valor típico / estimativa",
                "fonte": "Catálogo interno de valores orientativos",
                "documento": "",
                "edicao": "",
                "pagina_clausula": "",
                "data_verificacao": "",
                "responsavel_verificacao": "",
                "aplicabilidade": _texto(linha.get("observacao")),
                "observacoes": (
                    "Não usar como propriedade aprovada sem confirmação por certificado, "
                    "especificação controlada ou ensaio aplicável."
                ),
                "vinculacoes": [],
            }
        )
    return tuple(registros)


def _inferir_condicao(nome: str) -> str:
    marcadores = (
        "laminado a quente",
        "estirado a frio",
        "temperado e revenido",
        "normalizado",
        "recozido",
        "solubilizado",
        "H900",
        "T3",
        "T6",
        "H32",
        "meio duro",
        "fundido",
    )
    nome_minusculo = nome.lower()
    for marcador in marcadores:
        if marcador.lower() in nome_minusculo:
            return marcador
    return "Condição a confirmar"


def listar_catalogo_referencia() -> list[dict[str, Any]]:
    """Retorna cópia do catálogo; todos os itens permanecem como referência."""
    return deepcopy(list(_carregar_catalogo_cache()))


def criar_material_projeto(
    *,
    nome: str,
    familia: str,
    condicao: str,
    forma_produto: str,
    propriedades: Mapping[str, Any],
    origem_tipo: str,
    fonte: str,
    documento: str = "",
    edicao: str = "",
    pagina_clausula: str = "",
    lote: str = "",
    data_verificacao: str = "",
    responsavel_verificacao: str = "",
    aplicabilidade: str = "",
    observacoes: str = "",
    vinculacoes: Sequence[str] = (),
) -> dict[str, Any]:
    """Cria um registro JSON-seguro; a confiança é sempre recalculada."""
    nome_limpo = _texto(nome)
    if not nome_limpo:
        raise ValueError("Informe a designação do material.")
    if origem_tipo not in TIPOS_ORIGEM:
        raise ValueError("Selecione um tipo de origem reconhecido.")
    props = {chave: _numero(propriedades.get(chave)) for chave in PROPRIEDADES}
    _validar_propriedades(props)
    material = {
        "id": str(uuid4()),
        "origem_registro": "projeto",
        "nome": nome_limpo,
        "familia": _texto(familia),
        "condicao": _texto(condicao),
        "forma_produto": _texto(forma_produto),
        "lote": _texto(lote),
        "propriedades": props,
        "origem_tipo": origem_tipo,
        "fonte": _texto(fonte),
        "documento": _texto(documento),
        "edicao": _texto(edicao),
        "pagina_clausula": _texto(pagina_clausula),
        "data_verificacao": _texto(data_verificacao),
        "responsavel_verificacao": _texto(responsavel_verificacao),
        "aplicabilidade": _texto(aplicabilidade),
        "observacoes": _texto(observacoes),
        "vinculacoes": [str(item) for item in vinculacoes if str(item).strip()],
    }
    material["avaliacao"] = avaliar_material(material)
    return material


def _validar_propriedades(propriedades: Mapping[str, Any]) -> None:
    sut = _numero(propriedades.get("Sut_MPa"))
    sy = _numero(propriedades.get("Sy_MPa"))
    e = _numero(propriedades.get("E_GPa"))
    nu = _numero(propriedades.get("nu"))
    densidade = _numero(propriedades.get("densidade_kg_m3"))
    tmin = _numero(propriedades.get("temperatura_min_C"))
    tmax = _numero(propriedades.get("temperatura_max_C"))
    if sut is not None and sut <= 0:
        raise ValueError("Sut deve ser positivo quando informado.")
    if sy is not None and sy < 0:
        raise ValueError("Sy não pode ser negativo.")
    if sut is not None and sy is not None and sy > sut:
        raise ValueError("Sy não pode superar Sut para o mesmo estado do material.")
    if e is not None and e <= 0:
        raise ValueError("O módulo de elasticidade deve ser positivo.")
    if nu is not None and not (-1.0 < nu < 0.5):
        raise ValueError("O coeficiente de Poisson deve ficar entre -1 e 0,5.")
    if densidade is not None and densidade <= 0:
        raise ValueError("A densidade deve ser positiva.")
    if tmin is not None and tmax is not None and tmin > tmax:
        raise ValueError("A temperatura mínima não pode superar a máxima.")


def avaliar_material(material: Mapping[str, Any]) -> dict[str, Any]:
    """Pontua rastreabilidade, sem transformar o índice em aprovação técnica."""
    props = material.get("propriedades", {}) if isinstance(material.get("propriedades"), Mapping) else {}
    pontos = 0
    pendencias: list[str] = []

    for campo, peso, rotulo in (
        ("nome", 5, "designação"),
        ("familia", 3, "família"),
        ("condicao", 4, "condição de fornecimento/tratamento"),
        ("forma_produto", 3, "forma e faixa dimensional do produto"),
    ):
        if _texto(material.get(campo)):
            pontos += peso
        else:
            pendencias.append(f"Informar {rotulo}.")

    propriedades_informadas = sum(_numero(props.get(chave)) is not None for chave in PROPRIEDADES)
    pontos += min(20, propriedades_informadas * 4)
    if _numero(props.get("Sut_MPa")) is None and _numero(props.get("Sy_MPa")) is None:
        pendencias.append("Informar ao menos uma resistência mecânica aplicável.")

    origem = _texto(material.get("origem_tipo"))
    peso_origem = {
        "Certificado do lote / MTR": 20,
        "Relatório de ensaio": 20,
        "Norma ou especificação": 16,
        "Ficha técnica do fabricante": 13,
        "Literatura técnica": 7,
        "Valor típico / estimativa": 2,
    }.get(origem, 0)
    pontos += peso_origem
    if peso_origem < 13:
        pendencias.append("Substituir o valor orientativo por fonte controlada aplicável ao produto real.")

    if _texto(material.get("fonte")):
        pontos += 8
    else:
        pendencias.append("Identificar a organização ou fonte emissora.")
    if _texto(material.get("documento")):
        pontos += 8
    else:
        pendencias.append("Identificar certificado, norma, relatório ou ficha técnica.")
    if _texto(material.get("edicao")) or _texto(material.get("lote")):
        pontos += 6
    else:
        pendencias.append("Registrar edição/revisão ou lote/corrida.")
    if _texto(material.get("pagina_clausula")):
        pontos += 4
    if _texto(material.get("responsavel_verificacao")):
        pontos += 5
    else:
        pendencias.append("Definir quem conferiu a fonte.")
    if _texto(material.get("data_verificacao")):
        pontos += 4
    if _texto(material.get("aplicabilidade")):
        pontos += 5
    else:
        pendencias.append("Justificar a aplicabilidade à forma, condição e temperatura de serviço.")
    if _numero(props.get("temperatura_min_C")) is not None and _numero(props.get("temperatura_max_C")) is not None:
        pontos += 5
    else:
        pendencias.append("Registrar a faixa de temperatura qualificada quando relevante.")

    pontos = min(100, pontos)
    fonte_primaria = origem in {"Certificado do lote / MTR", "Relatório de ensaio"}
    verificado = bool(_texto(material.get("responsavel_verificacao")) and _texto(material.get("data_verificacao")))
    if pontos >= 85 and fonte_primaria and verificado:
        nivel = "Confirmado"
    elif pontos >= 70 and origem not in {"Literatura técnica", "Valor típico / estimativa"}:
        nivel = "Rastreável"
    elif pontos >= 40:
        nivel = "Condicional"
    else:
        nivel = "Referência"
    return {
        "nivel": nivel,
        "indice_rastreabilidade": pontos,
        "pendencias": list(dict.fromkeys(pendencias)),
        "avaliado_em": date.today().isoformat(),
        "aviso": "O índice mede evidência e preenchimento; não aprova o material nem substitui a especificação de engenharia.",
    }


def material_com_avaliacao(material: Mapping[str, Any]) -> dict[str, Any]:
    atualizado = deepcopy(dict(material))
    atualizado["avaliacao"] = avaliar_material(atualizado)
    return atualizado


def verificar_temperatura(material: Mapping[str, Any], temperatura_c: float | None) -> dict[str, str]:
    """Confere apenas a faixa cadastrada; não estima redução de propriedades."""
    if temperatura_c is None:
        return {"status": "Não avaliada", "mensagem": "Temperatura de serviço não informada."}
    props = material.get("propriedades", {}) if isinstance(material.get("propriedades"), Mapping) else {}
    tmin = _numero(props.get("temperatura_min_C"))
    tmax = _numero(props.get("temperatura_max_C"))
    if tmin is None or tmax is None:
        return {"status": "Pendente", "mensagem": "A fonte cadastrada não possui faixa de temperatura qualificada."}
    if tmin <= float(temperatura_c) <= tmax:
        return {"status": "Dentro da faixa", "mensagem": f"{temperatura_c:g} °C está entre {tmin:g} e {tmax:g} °C."}
    return {"status": "Fora da faixa", "mensagem": f"{temperatura_c:g} °C está fora da faixa cadastrada de {tmin:g} a {tmax:g} °C."}


def resumir_fonte(material: Mapping[str, Any]) -> str:
    partes = [
        _texto(material.get("origem_tipo")),
        _texto(material.get("documento")),
        _texto(material.get("edicao")),
        (f"lote {_texto(material.get('lote'))}" if _texto(material.get("lote")) else ""),
    ]
    return " · ".join(item for item in partes if item) or "Fonte não informada"
