"""Registro de provedores independentes de seções do memorial industrial."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from core.load_cases import (
    CHAVES_CARGA,
    ROTULOS_CARGA,
    UNIDADES_CARGA,
    calcular_envelope,
    fatores_legiveis,
)

ConstrutorSecao = Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class ProvedorSecaoRelatorio:
    id: str
    titulo: str
    apos: str
    ordem: int
    construir: ConstrutorSecao


_PROVEDORES: dict[str, ProvedorSecaoRelatorio] = {}


def registrar_provedor(
    provedor: ProvedorSecaoRelatorio, *, substituir: bool = False
) -> None:
    chave = provedor.id.strip().casefold()
    if chave in _PROVEDORES and not substituir:
        raise ValueError(f"Provedor de relatório já registrado: {provedor.id}.")
    _PROVEDORES[chave] = provedor


def listar_provedores(*, apos: str | None = None) -> list[ProvedorSecaoRelatorio]:
    provedores = list(_PROVEDORES.values())
    if apos is not None:
        alvo = apos.strip().casefold()
        provedores = [item for item in provedores if item.apos.strip().casefold() == alvo]
    return sorted(provedores, key=lambda item: (item.ordem, item.id))


def titulos_secoes_extensao() -> dict[str, str]:
    return {item.id: item.titulo for item in listar_provedores()}


def _texto(valor: Any, padrao: str = "Não informado") -> str:
    texto = str(valor).strip() if valor is not None else ""
    return texto or padrao


def _numero(valor: Any) -> str:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return _texto(valor)
    if not math.isfinite(numero):
        return "Não finito"
    return f"{numero:.5g}".replace(".", ",")


def _float_seguro(valor: Any) -> float | None:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def _secao_carregamentos(
    projeto: Mapping[str, Any], contexto: Mapping[str, Any]
) -> dict[str, Any]:
    casos = [
        item for item in projeto.get("casos_carga", []) if isinstance(item, Mapping)
    ]
    combinacoes = [
        item
        for item in projeto.get("combinacoes_carga", [])
        if isinstance(item, Mapping)
    ]
    try:
        envelope = calcular_envelope(
            casos,
            combinacoes,
            incluir_casos_isolados=not bool(combinacoes),
        )
        erro = ""
    except ValueError as exc:
        envelope = {"componentes": {}, "total_cenarios": 0}
        erro = str(exc)

    linhas_casos = []
    for caso in casos:
        vetor = caso.get("cargas", {}) if isinstance(caso.get("cargas"), Mapping) else {}
        ativos = []
        for chave in CHAVES_CARGA:
            valor = _float_seguro(vetor.get(chave, 0))
            if valor is None:
                ativos.append(f"{ROTULOS_CARGA[chave]}=valor inválido")
            elif abs(valor) > 1e-12:
                ativos.append(
                    f"{ROTULOS_CARGA[chave]}={_numero(valor)} {UNIDADES_CARGA[chave]}"
                )
        linhas_casos.append(
            [
                _texto(caso.get("codigo")),
                _texto(caso.get("nome")),
                f"{_texto(caso.get('condicao'))}\n{_texto(caso.get('natureza'))}",
                _texto(caso.get("tag")),
                "; ".join(ativos) or "Vetor nulo",
                f"{_texto(caso.get('origem'))}\n{_texto(caso.get('referencia'), '')}",
            ]
        )

    linhas_combinacoes = []
    for combinacao in combinacoes:
        linhas_combinacoes.append(
            [
                _texto(combinacao.get("nome")),
                _texto(combinacao.get("tipo")),
                fatores_legiveis(combinacao, casos),
                "Ativa" if bool(combinacao.get("ativo", True)) else "Inativa",
                _texto(combinacao.get("descricao"), ""),
            ]
        )

    linhas_envelope = []
    for chave in CHAVES_CARGA:
        item = envelope.get("componentes", {}).get(chave)
        if not item:
            continue
        linhas_envelope.append(
            [
                item["rotulo"],
                _numero(item["minimo"]),
                _numero(item["maximo"]),
                _numero(item["valor_governante"]),
                item["unidade"],
                _texto(item["cenario_governante"]),
            ]
        )

    paragrafos = [
        "Os casos preservam a origem física dos carregamentos. As combinações somam componentes algébricos e mantêm o cenário governante de cada grandeza.",
        f"Foram cadastrados {len(casos)} caso(s), {len(combinacoes)} combinação(ões) e avaliados {envelope.get('total_cenarios', 0)} cenário(s).",
    ]
    if erro:
        paragrafos.append(f"Falha de consistência detectada no conjunto de cargas: {erro}")
    return {
        "paragrafos": paragrafos,
        "tabelas": [
            {
                "legenda": "Casos de carga permanentes do projeto.",
                "cabecalhos": ["Código", "Caso", "Condição / natureza", "TAG", "Vetor não nulo", "Origem / referência"],
                "linhas": linhas_casos or [["-", "Nenhum caso cadastrado", "-", "-", "-", "-"]],
                "larguras": [1000, 1600, 1500, 900, 2600, 1760],
                "fonte": 6.8,
            },
            {
                "legenda": "Combinações registradas; os fatores não são definidos automaticamente como normativos.",
                "cabecalhos": ["Combinação", "Tipo", "Parcelas e fatores", "Estado", "Descrição"],
                "linhas": linhas_combinacoes or [["-", "-", "Nenhuma combinação cadastrada", "-", "-"]],
                "larguras": [1800, 1400, 3000, 1000, 2160],
                "fonte": 7.0,
            },
            {
                "legenda": "Envelope algébrico por componente.",
                "cabecalhos": ["Componente", "Mínimo", "Máximo", "Governante", "Unidade", "Cenário governante"],
                "linhas": linhas_envelope or [["-", "-", "-", "-", "-", "Sem cenários válidos"]],
                "larguras": [1700, 1100, 1100, 1200, 900, 3360],
                "fonte": 7.2,
            },
        ],
        "nota": (
            "O envelope não representa simultaneidade entre máximos de linhas diferentes. "
            "Confirme os fatores nas normas, especificações e bases de carregamento aplicáveis."
        ),
    }


def _registros_do_modulo(projeto: Mapping[str, Any], modulo_id: str) -> list[Mapping[str, Any]]:
    return [
        item
        for item in projeto.get("registros_tecnicos", [])
        if isinstance(item, Mapping)
        and str(item.get("modulo_id", "")).strip().casefold() == modulo_id
    ]


def _resultados(registro: Mapping[str, Any]) -> Mapping[str, Any]:
    valor = registro.get("resultados")
    return valor if isinstance(valor, Mapping) else {}


def _entradas(registro: Mapping[str, Any]) -> Mapping[str, Any]:
    valor = registro.get("entradas")
    return valor if isinstance(valor, Mapping) else {}


def _com_unidade(valor: Any, unidade: str, *, em: Any = None) -> str:
    """Valor formatado, opcionalmente com a abscissa onde ele ocorre."""
    numero = _float_seguro(valor)
    if numero is None:
        return "Não informado"
    texto = f"{_numero(numero)} {unidade}"
    posicao = _float_seguro(em)
    return texto if posicao is None else f"{texto}\n(x = {_numero(posicao)} m)"


def _secao_vigas_eixos(
    projeto: Mapping[str, Any], contexto: Mapping[str, Any]
) -> dict[str, Any]:
    """Diagramas e seções governantes das barras analisadas.

    Sem esta seção, uma viga registrada aparecia no memorial apenas como
    mais uma linha genérica da tabela de registros — o memorial trazia o
    número, mas não a seção que o governou nem a combinação que o produziu.
    """
    registros = _registros_do_modulo(projeto, "vigas_eixos")

    linhas_barras = []
    linhas_esforcos = []
    linhas_verificacao = []
    linhas_reacoes = []
    linhas_combinacoes = []

    for registro in registros:
        entradas, resultados = _entradas(registro), _resultados(registro)
        titulo = _texto(registro.get("titulo"))
        secao = entradas.get("secao") if isinstance(entradas.get("secao"), Mapping) else {}
        material = (
            entradas.get("material") if isinstance(entradas.get("material"), Mapping) else {}
        )
        apoios = entradas.get("apoios") if isinstance(entradas.get("apoios"), list) else []
        comprimento = _float_seguro(entradas.get("comprimento_mm"))

        linhas_barras.append(
            [
                titulo,
                _texto(secao.get("nome")),
                _texto(material.get("fonte")) or _texto(material.get("nome")),
                (
                    "Não informado"
                    if comprimento is None
                    else f"{_numero(comprimento / 1_000.0)} m"
                ),
                "; ".join(
                    f"{_texto(item.get('tipo'))} em "
                    f"{_numero((_float_seguro(item.get('x_mm')) or 0.0) / 1_000.0)} m"
                    for item in apoios
                    if isinstance(item, Mapping)
                )
                or "Não informado",
                _texto(resultados.get("grau_hiperestaticidade")),
            ]
        )

        linhas_esforcos.append(
            [
                titulo,
                _com_unidade(
                    resultados.get("cortante_maximo_kN"),
                    "kN",
                    em=resultados.get("cortante_maximo_x_m"),
                ),
                _com_unidade(
                    resultados.get("momento_maximo_kNm"),
                    "kN·m",
                    em=resultados.get("momento_maximo_x_m"),
                ),
                _com_unidade(resultados.get("normal_maximo_kN"), "kN"),
                _com_unidade(resultados.get("torque_maximo_kNm"), "kN·m"),
                _com_unidade(
                    resultados.get("flecha_maxima_mm"),
                    "mm",
                    em=resultados.get("flecha_maxima_x_m"),
                ),
            ]
        )

        fator = _float_seguro(resultados.get("fator_seguranca_escoamento"))
        meta = _float_seguro(resultados.get("fator_seguranca_minimo"))
        flecha = _float_seguro(resultados.get("flecha_maxima_mm"))
        admissivel = _float_seguro(resultados.get("flecha_admissivel_mm"))
        if flecha is None or admissivel is None or admissivel <= 0:
            situacao_flecha = "Não verificada"
        else:
            situacao_flecha = "Atende" if abs(flecha) <= admissivel else "Excedida"
        linhas_verificacao.append(
            [
                titulo,
                _com_unidade(resultados.get("tensao_normal_extrema_MPa"), "MPa"),
                _com_unidade(resultados.get("von_mises_maximo_MPa"), "MPa"),
                "Não informado" if fator is None else _numero(fator),
                "Não informado" if meta is None else _numero(meta),
                (
                    "Não verificada"
                    if admissivel is None
                    else f"{_numero(admissivel)} mm\n{_texto(resultados.get('criterio_flecha'), '')}\n{situacao_flecha}"
                ),
            ]
        )

        reacoes = resultados.get("reacoes")
        for reacao in reacoes if isinstance(reacoes, list) else []:
            if not isinstance(reacao, Mapping):
                continue
            linhas_reacoes.append(
                [
                    titulo,
                    f"{_numero(_float_seguro(reacao.get('x (m)')) or 0.0)} m",
                    _texto(reacao.get("Apoio")),
                    _numero(_float_seguro(reacao.get("Fy (kN)")) or 0.0),
                    _numero(_float_seguro(reacao.get("Fx (kN)")) or 0.0),
                    _numero(_float_seguro(reacao.get("Mz (kN·m)")) or 0.0),
                ]
            )

        governantes = resultados.get("envoltoria_governantes")
        for item in governantes if isinstance(governantes, list) else []:
            if not isinstance(item, Mapping):
                continue
            linhas_combinacoes.append(
                [
                    titulo,
                    _texto(item.get("Grandeza")),
                    _texto(item.get("Combinação governante")),
                    _numero(_float_seguro(item.get("Valor")) or 0.0),
                    _texto(item.get("Unidade")),
                    _numero(_float_seguro(item.get("x (m)")) or 0.0),
                ]
            )

    paragrafos = [
        "Barras retas verificadas por rigidez direta com elementos de "
        "Euler-Bernoulli. Dentro de cada trecho, o esforço cortante, o momento "
        "fletor e a linha elástica vêm de integração analítica, e não de "
        "interpolação da malha.",
        f"Foram registradas {len(registros)} análise(s) de viga ou eixo neste projeto.",
    ]
    if linhas_combinacoes:
        paragrafos.append(
            "As barras com combinações declaradas foram resolvidas uma vez por "
            "combinação; a tabela de envoltória indica qual delas governa cada "
            "grandeza, que raramente é a mesma para todas."
        )

    tabelas = [
        {
            "legenda": "Barras analisadas, seção, material e condições de apoio.",
            "cabecalhos": ["Barra", "Seção", "Material", "Comprimento", "Apoios", "Grau hip."],
            "linhas": linhas_barras or [["-", "Nenhuma barra registrada", "-", "-", "-", "-"]],
            "larguras": [1900, 1500, 2000, 1000, 2160, 800],
            "fonte": 6.8,
        },
        {
            "legenda": "Esforços internos e deslocamento máximos, com a seção em que ocorrem.",
            "cabecalhos": ["Barra", "V máx", "M máx", "N máx", "T máx", "Flecha máx"],
            "linhas": linhas_esforcos or [["-", "-", "-", "-", "-", "-"]],
            "larguras": [1900, 1500, 1600, 1400, 1400, 1560],
            "fonte": 6.8,
        },
        {
            "legenda": "Verificação de resistência e de deslocamento em serviço.",
            "cabecalhos": ["Barra", "σ extrema", "σ von Mises", "FS", "Meta", "Flecha admissível"],
            "linhas": linhas_verificacao or [["-", "-", "-", "-", "-", "-"]],
            "larguras": [1900, 1400, 1400, 900, 900, 2860],
            "fonte": 6.8,
        },
        {
            "legenda": "Reações de apoio, na convenção positiva para cima e para +x.",
            "cabecalhos": ["Barra", "Posição", "Apoio", "Fy (kN)", "Fx (kN)", "Mz (kN·m)"],
            "linhas": linhas_reacoes or [["-", "-", "-", "-", "-", "-"]],
            "larguras": [2400, 1200, 1600, 1400, 1400, 1360],
            "fonte": 6.8,
        },
    ]
    if linhas_combinacoes:
        tabelas.append(
            {
                "legenda": "Envoltória: combinação governante de cada grandeza.",
                "cabecalhos": ["Barra", "Grandeza", "Combinação", "Valor", "Unidade", "x (m)"],
                "linhas": linhas_combinacoes,
                "larguras": [1900, 1900, 2000, 1300, 1000, 1260],
                "fonte": 6.8,
            }
        )

    return {
        "paragrafos": paragrafos,
        "tabelas": tabelas,
        "nota": (
            "O modelo é linear: não amplifica a flecha pela compressão axial "
            "(efeito P–Δ), não verifica flambagem nem inclui deformação por "
            "cisalhamento, relevante quando L/h < 10. Os fatores de combinação "
            "são os declarados no modelo; o programa não atribui coeficiente "
            "normativo automaticamente."
        ),
    }


registrar_provedor(
    ProvedorSecaoRelatorio(
        id="vigas_eixos",
        titulo="Vigas e eixos: diagramas e seções governantes",
        apos="registros",
        ordem=10,
        construir=_secao_vigas_eixos,
    )
)


registrar_provedor(
    ProvedorSecaoRelatorio(
        id="carregamentos",
        titulo="Casos, combinações e envelopes de carga",
        apos="base",
        ordem=10,
        construir=_secao_carregamentos,
    )
)
