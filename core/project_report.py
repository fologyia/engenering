"""Memorial de cálculo do projeto industrial permanente, em Word e PDF.

O documento é um molde: os cálculos registrados pelos módulos entram
completos (entradas, equações, resultados, figuras, premissas e conclusão),
o restante fica marcado com :data:`A_PREENCHER` para o responsável completar
no Word. Nada aqui julga o projeto — validação, checklist e bloqueios são
assunto das páginas de gestão, não do memorial.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from datetime import datetime
from html import escape
from io import BytesIO
from typing import Any

from core.materials_registry import avaliar_material, resumir_fonte
from core.memorial_word import gerar_memorial_word_padrao
from core.pdf_fonts import fonte_pdf, texto_para_fonte
from core.project_criteria import normalizar_criterios_projeto, resumo_criterios_projeto
from core.record_charts import imagens_do_registro
from core.report_plugins import listar_provedores, titulos_secoes_extensao
from core.technical_records import (
    SEPARADOR_PECA,
    agrupar_registros_por_componente,
    avaliar_contrato_registro,
    rotulo_componente,
)

#: Marca de campo a completar à mão. É o que faz o memorial servir de molde:
#: no Word, um Ctrl+F por este texto percorre tudo o que ainda falta.
A_PREENCHER = "[a preencher]"

#: Módulos cujos registros ficam fora do memorial mesmo existindo no projeto:
#: casos e combinações de carga são cadastro, não verificação, e o Círculo
#: de Mohr é etapa intermediária — a verificação que interessa é a análise
#: que consome o estado de tensões.
MODULOS_FORA_DO_MEMORIAL = frozenset({"casos_carga", "circulo_mohr"})

_SECOES_BASE = (
    ("escopo", "Objetivo e escopo"),
    ("base", "Base de projeto"),
    ("componentes", "Equipamentos e escopo físico"),
    ("materiais", "Materiais"),
    ("plano_calculo", "Quadro-resumo dos cálculos"),
    ("registros", "Memória de cálculo"),
    ("sensibilidade", "Sensibilidade, incertezas e robustez"),
    ("conclusao", "Conclusão e recomendações"),
)


def _montar_catalogo_secoes() -> dict[str, str]:
    extensoes = titulos_secoes_extensao()
    catalogo: dict[str, str] = {}
    incluidos: set[str] = set()
    for chave, titulo in _SECOES_BASE:
        catalogo[chave] = titulo
        for provedor in listar_provedores(apos=chave):
            catalogo[provedor.id] = provedor.titulo
            incluidos.add(provedor.id)
    for chave, titulo in extensoes.items():
        if chave not in incluidos:
            catalogo[chave] = titulo
    return catalogo


SECOES_RELATORIO = _montar_catalogo_secoes()


def _texto(valor: Any, padrao: str = "Não informado") -> str:
    texto = str(valor).strip() if valor is not None else ""
    return texto or padrao


def _campo(valor: Any) -> str:
    """Campo de projeto: quando vazio, vira marca para preencher no Word."""
    return _texto(valor, A_PREENCHER)


def _formatar_numero(valor: float) -> str:
    """Cinco algarismos significativos, em notação pt-BR.

    ``.5g`` escreve 200000 como ``2e+05`` — um módulo de elasticidade
    ilegível num memorial. Números grandes voltam à forma inteira com
    separador de milhar; só os muito pequenos ficam em notação científica.
    """
    texto = f"{valor:.5g}"
    if "e" in texto and abs(valor) >= 1:
        return f"{valor:,.0f}".replace(",", ".")
    return texto.replace(".", ",")


def _valor(valor: Any) -> str:
    if valor is None:
        return "Não informado"
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, float):
        if not math.isfinite(valor):
            return "Não finito"
        return _formatar_numero(valor)
    if isinstance(valor, (list, tuple, set)):
        texto = "; ".join(_valor(item) for item in valor) or "Não informado"
        return (
            texto
            if len(texto) <= 1400
            else texto[:1360] + "… [resumido; consulte o registro permanente]"
        )
    if isinstance(valor, Mapping):
        texto = (
            "; ".join(f"{chave}: {_valor(item)}" for chave, item in valor.items())
            or "Não informado"
        )
        return (
            texto
            if len(texto) <= 1400
            else texto[:1360] + "… [resumido; consulte o registro permanente]"
        )
    texto = _texto(valor)
    return (
        texto
        if len(texto) <= 1400
        else texto[:1360] + "… [resumido; consulte o registro permanente]"
    )


def _rotulo_e_unidade(chave: Any) -> tuple[str, str]:
    texto = _texto(chave)
    unidades = {
        "_MPa": "MPa",
        "_GPa": "GPa",
        "_kPa": "kPa",
        "_kN": "kN",
        "_kNm": "kN·m",
        "_mm4": "mm⁴",
        "_mm3": "mm³",
        "_mm2": "mm²",
        "_mm": "mm",
        "_bar": "bar",
        "_C": "°C",
        "_F": "°F",
        "_ciclos": "ciclos",
        "_pct": "%",
    }
    unidade = "-"
    base = texto
    for sufixo, candidato in sorted(unidades.items(), key=lambda item: len(item[0]), reverse=True):
        if texto.endswith(sufixo):
            base = texto[: -len(sufixo)]
            unidade = candidato
            break
    base = base.replace("_", " ").strip()
    # Só a inicial sobe: ``str.capitalize`` rebaixaria "Fy (kN)" a "Fy (kn)".
    rotulo = (base[:1].upper() + base[1:]) if base else texto
    return rotulo, unidade


def _campo_legivel(chave: Any) -> str:
    rotulo, unidade = _rotulo_e_unidade(chave)
    return f"{rotulo} [{unidade}]" if unidade != "-" else rotulo


def _chave_interna(chave: Any) -> bool:
    """Chaves de vínculo (UUIDs) que não dizem nada impressas."""
    texto = _texto(chave, "")
    return texto.endswith(("_id", "_ids")) or texto == "registro_origem"


def _lista_de_mapas(valor: Any) -> bool:
    return (
        isinstance(valor, Sequence)
        and not isinstance(valor, (str, bytes))
        and len(valor) > 0
        and all(isinstance(item, Mapping) for item in valor)
    )


def _tabela_de_lista(chave: Any, itens: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Uma lista de dicionários (reações, envoltória, ranking) vira tabela.

    Impressa como texto corrido — "x (m): 0; Apoio: pino; Fy (kN): 45; …" —
    a reação de apoio era ilegível. Aqui cada dicionário é uma linha e as
    chaves, na ordem em que aparecem, são as colunas.
    """
    colunas: list[str] = []
    for item in itens:
        for nome in item:
            if nome not in colunas:
                colunas.append(str(nome))
    legenda = f"{_campo_legivel(chave)}."
    if not colunas or len(colunas) > 8:
        return {
            "legenda": legenda,
            "cabecalhos": ["Item", "Valor"],
            "linhas": [[str(indice), _valor(item)] for indice, item in enumerate(itens, start=1)],
            "larguras": [900, 8460],
            "fonte": 7.2,
        }
    largura = 9360 // len(colunas)
    larguras = [largura] * len(colunas)
    larguras[-1] += 9360 - largura * len(colunas)
    return {
        "legenda": legenda,
        "cabecalhos": [_campo_legivel(nome) for nome in colunas],
        "linhas": [[_valor(item.get(nome)) for nome in colunas] for item in itens],
        "larguras": larguras,
        "fonte": 7.2,
    }


def _tabelas_de_dados(
    dados: Mapping[str, Any], *, legenda: str, rotulo_campo: str, vazio: str
) -> list[dict[str, Any]]:
    """Tabela campo/valor dos escalares, mais uma tabela por lista de mapas."""
    linhas: list[list[str]] = []
    subtabelas: list[dict[str, Any]] = []
    for chave, valor in dados.items():
        if _chave_interna(chave):
            continue
        if _lista_de_mapas(valor):
            subtabelas.append(_tabela_de_lista(chave, valor))
            continue
        linhas.append([_campo_legivel(chave), _valor(valor)])
    principal = {
        "legenda": legenda,
        "cabecalhos": [rotulo_campo, "Valor"],
        "linhas": linhas or [["-", vazio]],
        "larguras": [3000, 6360],
        "fonte": 7.8,
    }
    return [principal, *subtabelas]


_SITUACOES = {
    "atende": "atendem",
    "atenção": "atencao",
    "atencao": "atencao",
    "não atende": "nao_atendem",
    "nao atende": "nao_atendem",
}


def sintetizar_calculos(registros: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Conta os cálculos pela situação que o módulo declarou ao registrá-los.

    "Atende", "Atenção" e "Não atende" são as situações que os módulos
    gravam; "Calculado" e afins não comparam com critério nenhum e entram
    como "sem verificação de critério". É a única leitura de conjunto que o
    memorial faz — e ela vem dos cálculos, não do programa.
    """
    contagem = {"total": len(registros), "atendem": 0, "atencao": 0, "nao_atendem": 0, "outros": 0}
    for registro in registros:
        situacao = _texto(registro.get("status"), "").casefold()
        contagem[_SITUACOES.get(situacao, "outros")] += 1
    partes = []
    if contagem["atendem"]:
        n = contagem["atendem"]
        partes.append(f"{n} {'atende' if n == 1 else 'atendem'}")
    if contagem["atencao"]:
        partes.append(f"{contagem['atencao']} com atenção")
    if contagem["nao_atendem"]:
        n = contagem["nao_atendem"]
        partes.append(f"{n} não {'atende' if n == 1 else 'atendem'}")
    if contagem["outros"]:
        partes.append(f"{contagem['outros']} sem verificação de critério")
    total = contagem["total"]
    if total == 0:
        texto = "Nenhum cálculo anexado"
    else:
        texto = f"{total} {'cálculo' if total == 1 else 'cálculos'}"
        if partes:
            texto += " — " + " · ".join(partes)
    contagem["texto"] = texto
    return contagem


def _filtrar_registros(
    projeto: Mapping[str, Any], registros_ids: Sequence[str] | None
) -> list[Mapping[str, Any]]:
    registros = [
        item
        for item in projeto.get("registros_tecnicos", [])
        if isinstance(item, Mapping)
        and str(item.get("modulo_id") or "").strip().casefold() not in MODULOS_FORA_DO_MEMORIAL
    ]
    if registros_ids is None:
        return registros
    ordem = {str(item): indice for indice, item in enumerate(registros_ids)}
    return sorted(
        (item for item in registros if str(item.get("id")) in ordem),
        key=lambda item: ordem[str(item.get("id"))],
    )


def avaliar_integridade_registro(registro: Mapping[str, Any]) -> dict[str, Any]:
    """Mede completude do capítulo; não valida o cálculo de engenharia."""
    itens = {
        "Entradas": registro.get("entradas"),
        "Resultados": registro.get("resultados"),
        "Método": registro.get("metodo") or registro.get("resumo"),
        "Premissas": registro.get("premissas"),
        "Referências": registro.get("referencias"),
        "Conclusão": registro.get("conclusao"),
    }
    preenchidos = sum(bool(valor) for valor in itens.values())
    percentual = round(100 * preenchidos / len(itens))
    faltantes = [rotulo for rotulo, valor in itens.items() if not valor]
    nivel = (
        "Completo"
        if percentual == 100
        else ("Utilizável com ressalvas" if percentual >= 67 else "Incompleto")
    )
    contrato = avaliar_contrato_registro(registro)
    return {
        "percentual": percentual,
        "nivel": nivel,
        "faltantes": faltantes,
        "contrato": "Versionado" if registro.get("schema_registro") else "Legado",
        "assinatura": (
            "Válida"
            if contrato["assinatura_valida"]
            else ("Divergente" if contrato["assinatura_presente"] else "Ausente")
        ),
    }


def _peca_registro(
    registro: Mapping[str, Any], componentes_por_id: Mapping[str, Mapping[str, Any]]
) -> str:
    """Nome curto da peça verificada, para quadros e legendas.

    Prefere o nome livre informado no registro; sem ele, usa o TAG do
    componente vinculado. Registros antigos, sem nenhum dos dois, aparecem
    como "-", e não como um texto inventado.
    """
    peca = _texto(registro.get("peca"), "")
    if peca:
        return peca
    vinculados = [
        componentes_por_id[str(valor)]
        for valor in registro.get("componentes_ids", []) or []
        if str(valor) in componentes_por_id
    ]
    return ", ".join(rotulo_componente(item) for item in vinculados) or "-"


def _titulo_sem_peca(registro: Mapping[str, Any]) -> str:
    """Título do cálculo sem o prefixo da peça, para quadros que já a mostram."""
    titulo = _texto(registro.get("titulo"), "Registro técnico")
    peca = _texto(registro.get("peca"), "")
    prefixo = f"{peca}{SEPARADOR_PECA}"
    if peca and titulo.startswith(prefixo) and len(titulo) > len(prefixo):
        return titulo[len(prefixo) :]
    return titulo


def _hash_snapshot(
    projeto: Mapping[str, Any],
    registros: Sequence[Mapping[str, Any]],
    secoes: Sequence[str],
    metadata: Mapping[str, Any],
) -> str:
    pacote = {
        "projeto_id": projeto.get("id"),
        "projeto_revisao": projeto.get("revisao"),
        "secoes": list(secoes),
        "metadata": dict(metadata),
        "componentes": projeto.get("componentes", []),
        "materiais_projeto": projeto.get("materiais_projeto", []),
        "registros": list(registros),
    }
    serializado = json.dumps(
        pacote, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def _metadados(
    projeto: Mapping[str, Any], metadata_extra: Mapping[str, Any] | None
) -> dict[str, Any]:
    extras = dict(metadata_extra or {})
    emissao = extras.get("emissao") or datetime.now().astimezone().strftime("%d/%m/%Y")
    return {
        "titulo": extras.get("titulo") or "Memorial de cálculo do projeto industrial",
        "subtitulo": extras.get("subtitulo") or "Base de projeto e memória de cálculo",
        "projeto": projeto.get("nome"),
        "cliente": projeto.get("cliente"),
        "codigo": extras.get("codigo") or projeto.get("codigo"),
        "revisao": extras.get("revisao") or f"{int(projeto.get('revisao', 0)):02d}",
        "responsavel": extras.get("responsavel") or projeto.get("responsavel"),
        "verificador": extras.get("verificador") or projeto.get("verificador"),
        "aprovador": extras.get("aprovador") or projeto.get("aprovador"),
        "situacao": extras.get("situacao") or projeto.get("status"),
        "emissao": emissao,
    }


def montar_modelo_relatorio(
    projeto: Mapping[str, Any],
    *,
    secoes_incluidas: Sequence[str] | None = None,
    registros_ids: Sequence[str] | None = None,
    metadata_extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Monta um modelo neutro, usado igualmente por Word e PDF."""

    ativas = set(secoes_incluidas or SECOES_RELATORIO)
    metadata = _metadados(projeto, metadata_extra)
    registros = _filtrar_registros(projeto, registros_ids)
    componentes = [item for item in projeto.get("componentes", []) if isinstance(item, Mapping)]
    componentes_por_id = {
        str(item.get("id")): item for item in componentes if str(item.get("id") or "").strip()
    }
    materiais = [item for item in projeto.get("materiais_projeto", []) if isinstance(item, Mapping)]
    base = (
        projeto.get("base_projeto", {}) if isinstance(projeto.get("base_projeto"), Mapping) else {}
    )
    registros_sensibilidade = [
        item for item in registros if "sensibilidade" in _texto(item.get("modulo"), "").casefold()
    ]
    registros_capitulos = [
        item
        for item in registros
        if item not in registros_sensibilidade or "sensibilidade" not in ativas
    ]
    hash_snapshot = _hash_snapshot(projeto, registros, sorted(ativas), metadata)
    metadata["snapshot_hash"] = hash_snapshot
    sintese = sintetizar_calculos(registros)

    resumo = [
        {"rotulo": "Cálculos anexados", "valor": str(len(registros))},
        {"rotulo": "Peças no escopo", "valor": str(len(componentes))},
        {"rotulo": "Revisão", "valor": metadata["revisao"]},
        {"rotulo": "Emissão", "valor": metadata["emissao"]},
    ]
    rastreaveis = sum(
        avaliar_material(item)["nivel"] in {"Confirmado", "Rastreável"} for item in materiais
    )
    linhas_resumo = [
        ["Projeto", _campo(projeto.get("nome")), f"Código {_campo(projeto.get('codigo'))}."],
        [
            "Unidade / área",
            f"{_campo(projeto.get('unidade_industrial'))} / {_campo(projeto.get('area'))}",
            f"TAG: {_campo(projeto.get('tag_equipamento'))}.",
        ],
        [
            "Escopo físico",
            f"{len(componentes)} item(ns)",
            "Equipamentos, estruturas, linhas ou pontos cadastrados.",
        ],
        [
            "Materiais",
            f"{len(materiais)} cadastro(s) de projeto",
            f"{rastreaveis} com origem confirmada ou rastreável.",
        ],
        [
            "Cálculos anexados",
            sintese["texto"],
            "Situação declarada por cada módulo ao registrar o cálculo.",
        ],
    ]
    if registros_sensibilidade:
        linhas_resumo.append(
            [
                "Robustez",
                f"{len(registros_sensibilidade)} análise(s)",
                "Sensibilidade e incerteza separadas do resultado determinístico.",
            ]
        )

    secoes: list[dict[str, Any]] = []
    numero = 3

    contexto_extensoes = {
        "registros": registros,
        "metadata": metadata,
        "secoes_ativas": sorted(ativas),
    }

    def anexar_extensoes(chave: str) -> None:
        """Emite os provedores ancorados em ``chave``.

        Nem toda seção do memorial passa por ``adicionar``: algumas montam
        vários capítulos e são anexadas diretamente. Sem este gancho
        explícito, um provedor registrado com ``apos="registros"`` seria
        silenciosamente descartado — o pior tipo de falha num ponto de
        extensão, porque nada indica que ele existe.
        """
        nonlocal numero
        for provedor in listar_provedores(apos=chave):
            if provedor.id not in ativas:
                continue
            conteudo = provedor.construir(projeto, contexto_extensoes)
            if not conteudo:
                # O provedor não tem o que dizer neste projeto (nenhuma viga
                # registrada, por exemplo): uma seção só de tabelas vazias
                # engordaria o memorial sem informar nada.
                continue
            conteudo["titulo"] = f"{numero}. {SECOES_RELATORIO[provedor.id]}"
            secoes.append(conteudo)
            numero += 1

    def adicionar(chave: str, conteudo: dict[str, Any], *, incluir_extensoes: bool = True) -> None:
        nonlocal numero
        if chave in ativas:
            conteudo["titulo"] = f"{numero}. {SECOES_RELATORIO[chave]}"
            secoes.append(conteudo)
            numero += 1
        if incluir_extensoes:
            anexar_extensoes(chave)

    adicionar(
        "escopo",
        {
            "paragrafos": [
                f"Objetivo: {_campo(projeto.get('objetivo'))}",
                f"Descrição: {_campo(projeto.get('descricao'))}",
                f"Processo ou serviço: {_campo(projeto.get('processo'))}. "
                f"Regime de operação: {_campo(projeto.get('regime_operacao'))}.",
            ],
            "nota": "O memorial é válido somente para o escopo, os dados e as revisões identificados neste documento.",
        },
    )
    # Critérios estruturados e documentos de entrada entram na base de
    # projeto quando existem: são eles que dizem contra o que os cálculos
    # foram cobrados e sobre quais documentos o escopo foi montado.
    criterios_estruturados = projeto.get("criterios_projeto")
    linhas_base = [
        ["Desenhos e documentos", _campo(base.get("referencias_desenho"))],
        ["Base dos carregamentos", _campo(base.get("base_carregamentos"))],
        ["Condições de operação", _campo(base.get("condicoes_operacao"))],
        ["Critérios de aceitação", _campo(base.get("criterio_aceitacao"))],
        ["Vida requerida", _campo(base.get("vida_requerida"))],
        ["Limitações e exclusões", _campo(base.get("limitacoes"))],
    ]
    if isinstance(criterios_estruturados, Mapping):
        criterios_norm = normalizar_criterios_projeto(criterios_estruturados)
        normativo = criterios_norm["normativo"]
        linhas_base.append(
            ["Critérios técnicos do projeto", resumo_criterios_projeto(criterios_norm)]
        )
        linhas_base.append(
            [
                "Norma principal e aceitação",
                f"{_campo(normativo.get('norma_principal'))} {_texto(normativo.get('edicao'), '')}".strip()
                + f" — {_campo(normativo.get('criterio_aceitacao'))}",
            ]
        )
    else:
        linhas_base.append(["Critérios técnicos do projeto", A_PREENCHER])
    tabelas_base = [
        {
            "legenda": "Base de projeto e critérios adotados.",
            "cabecalhos": ["Tópico", "Registro"],
            "linhas": linhas_base,
            "larguras": [2600, 6760],
            "fonte": 8.2,
        }
    ]
    documentos_entrada = [item for item in projeto.get("anexos", []) if isinstance(item, Mapping)]
    if documentos_entrada:
        tabelas_base.append(
            {
                "legenda": "Documentos de entrada controlados.",
                "cabecalhos": ["Código", "Título", "Tipo", "Revisão", "Emitente", "Situação"],
                "linhas": [
                    [
                        _campo(item.get("codigo")),
                        _campo(item.get("titulo")),
                        _campo(item.get("tipo")),
                        _campo(item.get("revisao")),
                        _campo(item.get("emitente")),
                        _campo(item.get("situacao")),
                    ]
                    for item in documentos_entrada
                ],
                "larguras": [1300, 2900, 1500, 900, 1600, 1160],
                "fonte": 7.3,
            }
        )
    adicionar("base", {"tabelas": tabelas_base})
    adicionar(
        "componentes",
        {
            "paragrafos": [
                "Relação permanente dos equipamentos, sistemas, estruturas e pontos incluídos no escopo."
            ],
            "tabelas": [
                {
                    "cabecalhos": [
                        "TAG",
                        "Descrição / serviço",
                        "Material / fonte",
                        "Desenho",
                        "Criticidade",
                    ],
                    "linhas": [
                        [
                            _campo(item.get("tag")),
                            f"{_campo(item.get('descricao'))}\n{_texto(item.get('servico'), '')}",
                            f"{_campo(item.get('material'))}\n{_texto(item.get('fonte_material'), '')}",
                            _campo(item.get("desenho")),
                            _campo(item.get("criticidade")),
                        ]
                        for item in componentes
                    ]
                    or [["-", "Nenhum item cadastrado", "-", "-", "-"]],
                    "larguras": [1200, 2600, 2300, 1700, 1560],
                    "fonte": 7.4,
                }
            ],
        },
    )
    adicionar(
        "materiais",
        {
            "paragrafos": [
                "Materiais cadastrados no projeto, com origem e avaliação documental. "
                "Propriedades de catálogo são orientativas e não substituem especificação, "
                "certificado ou ensaio."
            ],
            "tabelas": [
                {
                    "cabecalhos": [
                        "Material / condição",
                        "Propriedades",
                        "Origem / documento",
                        "Confiança",
                        "Aplicabilidade",
                    ],
                    "linhas": [
                        [
                            f"{_campo(item.get('nome'))}\n{_texto(item.get('condicao'), '')} · {_texto(item.get('forma_produto'), '')}",
                            "; ".join(
                                f"{_rotulo_e_unidade(chave)[0]}={_valor(valor)} {_rotulo_e_unidade(chave)[1]}".strip()
                                for chave, valor in (
                                    item.get("propriedades", {})
                                    if isinstance(item.get("propriedades"), Mapping)
                                    else {}
                                ).items()
                                if valor is not None
                            )
                            or "Sem propriedades registradas",
                            resumir_fonte(item),
                            f"{avaliar_material(item)['nivel']}\n{avaliar_material(item)['indice_rastreabilidade']}%",
                            _campo(item.get("aplicabilidade")),
                        ]
                        for item in materiais
                    ]
                    or [["Nenhum material de projeto", "-", "-", "-", A_PREENCHER]],
                    "larguras": [2100, 1900, 2100, 1200, 2060],
                    "fonte": 7.0,
                }
            ],
        },
    )

    adicionar(
        "plano_calculo",
        {
            "paragrafos": [
                "Cálculos anexados a esta emissão, na ordem em que aparecem na memória de cálculo."
            ],
            "tabelas": [
                {
                    "cabecalhos": ["Ordem", "Peça", "Cálculo", "Módulo", "Situação"],
                    "linhas": [
                        [
                            str(indice),
                            _peca_registro(item, componentes_por_id),
                            _titulo_sem_peca(item),
                            _texto(item.get("modulo")),
                            _texto(item.get("status")),
                        ]
                        for indice, item in enumerate(registros, start=1)
                    ]
                    or [["-", "-", "Nenhum cálculo anexado", "-", "-"]],
                    "larguras": [700, 2000, 3460, 1900, 1300],
                    "fonte": 7.4,
                }
            ],
        },
    )

    if "registros" in ativas:
        titulo_secao = f"{numero}. {SECOES_RELATORIO['registros']}"
        grupos = agrupar_registros_por_componente(registros_capitulos, componentes)
        # Só vale a pena abrir um nível por peça quando há vínculo com o escopo
        # físico; um projeto sem componentes cadastrados segue com a lista
        # plana de antes, sem um subtítulo "sem peça vinculada" inútil.
        agrupar = any(grupo["componente"] is not None for grupo in grupos)
        secoes.append(
            {
                "titulo": titulo_secao,
                "paragrafos": [
                    "Cada cálculo abaixo reproduz as entradas, as equações, os resultados, "
                    "as premissas e a conclusão registradas pelo módulo que o produziu."
                    + (
                        " Os cálculos estão agrupados pela peça do escopo físico que verificam; os sem vínculo ficam ao final."
                        if agrupar
                        else ""
                    )
                ],
            }
        )

        def capitulo_registro(
            numeracao: str, nivel: int, registro: Mapping[str, Any]
        ) -> dict[str, Any]:
            entradas = (
                registro.get("entradas", {})
                if isinstance(registro.get("entradas"), Mapping)
                else {}
            )
            resultados = (
                registro.get("resultados", {})
                if isinstance(registro.get("resultados"), Mapping)
                else {}
            )
            peca = _peca_registro(registro, componentes_por_id)
            imagens, aviso_imagens = imagens_do_registro(registro, projeto)
            paragrafos = [
                f"Módulo: {_texto(registro.get('modulo'))}. Peça: {peca}. Situação: {_texto(registro.get('status'))}.",
                f"Resumo: {_campo(registro.get('resumo'))}",
                f"Método: {_campo(registro.get('metodo'))}",
            ]
            if aviso_imagens:
                paragrafos.append(aviso_imagens)
            return {
                "titulo": f"{numeracao} {_texto(registro.get('titulo'), 'Registro técnico')}",
                "nivel": nivel,
                "paragrafos": paragrafos,
                "bullets": [f"Premissa: {_valor(item)}" for item in registro.get("premissas", [])]
                + [f"Critério: {_valor(item)}" for item in registro.get("criterios", [])]
                + [f"Alerta: {_valor(item)}" for item in registro.get("alertas", [])]
                + [f"Referência: {_valor(item)}" for item in registro.get("referencias", [])],
                "formulas": [_valor(item) for item in registro.get("equacoes", [])],
                "imagens": imagens,
                "tabelas": _tabelas_de_dados(
                    entradas,
                    legenda="Entradas registradas.",
                    rotulo_campo="Campo",
                    vazio="Não registradas",
                )
                + _tabelas_de_dados(
                    resultados,
                    legenda="Resultados registrados.",
                    rotulo_campo="Grandeza / critério",
                    vazio="Não registrados",
                ),
                "paragrafos_finais": [f"Conclusão: {_campo(registro.get('conclusao'))}"],
            }

        # Sem agrupamento os registros ficam em ``N.i``; com ele, cada peça vira
        # ``N.g`` e os cálculos dela vêm logo abaixo, em ``N.g.i``.
        if agrupar:
            for indice_grupo, grupo in enumerate(grupos, start=1):
                componente = grupo["componente"]
                descricao_grupo = (
                    [
                        f"Serviço: {_campo(componente.get('servico'))}. Material: {_campo(componente.get('material'))}. "
                        f"Desenho: {_campo(componente.get('desenho'))}. Criticidade: {_campo(componente.get('criticidade'))}.",
                        f"{len(grupo['registros'])} cálculo(s) vinculado(s) a esta peça.",
                    ]
                    if componente is not None
                    else [
                        "Cálculos salvos sem vínculo com um item do escopo físico. Para que apareçam sob a peça "
                        "correspondente, informe a identificação da peça ao registrar o cálculo."
                    ]
                )
                secoes.append(
                    {
                        "titulo": f"{numero}.{indice_grupo} {grupo['rotulo']}",
                        "nivel": 2,
                        "paragrafos": descricao_grupo,
                    }
                )
                for indice, registro in enumerate(grupo["registros"], start=1):
                    secoes.append(
                        capitulo_registro(f"{numero}.{indice_grupo}.{indice}", 3, registro)
                    )
        else:
            for indice, registro in enumerate(registros_capitulos, start=1):
                secoes.append(capitulo_registro(f"{numero}.{indice}", 2, registro))
        if not registros_capitulos:
            secoes[-1]["nota"] = "Nenhum cálculo foi anexado a esta emissão."
        numero += 1
    anexar_extensoes("registros")

    if "sensibilidade" in ativas and registros_sensibilidade:
        titulo_secao = f"{numero}. {SECOES_RELATORIO['sensibilidade']}"
        secoes.append(
            {
                "titulo": titulo_secao,
                "paragrafos": [
                    "As análises abaixo mostram dependência local das entradas e, quando disponível, propagação probabilística das incertezas declaradas. Elas não corrigem limitações do modelo físico."
                ],
            }
        )
        for indice, registro in enumerate(registros_sensibilidade, start=1):
            resultados_sens = (
                registro.get("resultados", {})
                if isinstance(registro.get("resultados"), Mapping)
                else {}
            )
            ranking = resultados_sens.get("ranking_sensibilidade", [])
            correlacoes = resultados_sens.get("correlacoes_spearman", [])
            criterio_prob = resultados_sens.get("probabilidade_nao_atendimento_pct")
            secoes.append(
                {
                    "titulo": f"{numero}.{indice} {_texto(registro.get('titulo'), 'Análise de sensibilidade')}",
                    "nivel": 2,
                    "paragrafos": [
                        f"Resumo: {_campo(registro.get('resumo'))}",
                        f"Resultado nominal: {_valor(resultados_sens.get('saida_nominal'))} {_texto(resultados_sens.get('unidade_saida'), '')}. "
                        f"Faixa P05–P95: {_valor(resultados_sens.get('p05'))} a {_valor(resultados_sens.get('p95'))}. "
                        f"Probabilidade de não atendimento: {_valor(criterio_prob) if criterio_prob is not None else 'não avaliada'}{('%' if criterio_prob is not None else '')}.",
                    ],
                    "tabelas": [
                        {
                            "legenda": "Ranking por efeito OAT no intervalo informado.",
                            "cabecalhos": [
                                "Entrada",
                                "Impacto (%)",
                                "Elasticidade",
                                "Direção crítica",
                            ],
                            "linhas": [
                                [
                                    _texto(item.get("variavel")),
                                    _valor(item.get("impacto_percentual")),
                                    _valor(item.get("elasticidade")),
                                    _texto(item.get("direcao_critica")),
                                ]
                                for item in ranking
                                if isinstance(item, Mapping)
                            ]
                            or [["Não registrado", "-", "-", "-"]],
                            "larguras": [3500, 1800, 1800, 2260],
                            "fonte": 7.8,
                        },
                        {
                            "legenda": "Associação monotônica na simulação de Monte Carlo.",
                            "cabecalhos": ["Entrada", "Correlação de Spearman"],
                            "linhas": [
                                [_texto(item.get("variavel")), _valor(item.get("correlacao"))]
                                for item in correlacoes
                                if isinstance(item, Mapping)
                            ]
                            or [["Não registrada", "-"]],
                            "larguras": [5200, 4160],
                            "fonte": 8.0,
                        },
                    ],
                    "paragrafos_finais": [f"Conclusão: {_campo(registro.get('conclusao'))}"],
                    "nota": _texto(
                        registro.get("metodo"),
                        "Verifique faixas, distribuições, correlações e semente usadas.",
                    ),
                }
            )
        numero += 1

    adicionar(
        "conclusao",
        {
            "paragrafos": [f"Síntese dos cálculos anexados: {sintese['texto']}."],
            "bullets": [
                f"{_texto(registro.get('titulo'), 'Registro técnico')} "
                f"({_texto(registro.get('status'))}): {_campo(registro.get('conclusao'))}"
                for registro in registros
            ],
            "paragrafos_finais": [
                f"Conclusão geral: {A_PREENCHER}",
                f"Recomendações: {A_PREENCHER}",
            ],
        },
    )

    metadata["numero_aprovacoes"] = numero

    return {
        "metadata": metadata,
        "resumo": resumo,
        "resumo_executivo": {"linhas": linhas_resumo},
        "secoes": secoes,
        "sintese": sintese,
        "registros": registros,
        "secoes_incluidas": list(ativas),
        "snapshot_hash": hash_snapshot,
        "numero_aprovacoes": numero,
    }


def gerar_relatorio_industrial_word(
    projeto: Mapping[str, Any],
    *,
    secoes_incluidas: Sequence[str] | None = None,
    registros_ids: Sequence[str] | None = None,
    metadata_extra: Mapping[str, Any] | None = None,
) -> bytes:
    modelo = montar_modelo_relatorio(
        projeto,
        secoes_incluidas=secoes_incluidas,
        registros_ids=registros_ids,
        metadata_extra=metadata_extra,
    )
    return gerar_memorial_word_padrao(
        metadata=modelo["metadata"],
        resumo=modelo["resumo"],
        resumo_executivo=modelo["resumo_executivo"],
        secoes=modelo["secoes"],
    )


def gerar_relatorio_industrial_pdf(
    projeto: Mapping[str, Any],
    *,
    secoes_incluidas: Sequence[str] | None = None,
    registros_ids: Sequence[str] | None = None,
    metadata_extra: Mapping[str, Any] | None = None,
) -> bytes:
    """Gera versão PDF com o mesmo modelo documental do Word."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Image,
            LongTable,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as erro:
        raise RuntimeError("A exportação PDF requer reportlab.") from erro

    modelo = montar_modelo_relatorio(
        projeto,
        secoes_incluidas=secoes_incluidas,
        registros_ids=registros_ids,
        metadata_extra=metadata_extra,
    )
    metadata = modelo["metadata"]
    fonte = fonte_pdf()
    azul = colors.HexColor("#16324F")
    azul_medio = colors.HexColor("#24577A")
    azul_claro = colors.HexColor("#EAF2F8")
    cinza = colors.HexColor("#5F6B76")
    cinza_claro = colors.HexColor("#F4F6F8")
    borda = colors.HexColor("#C9D4DE")
    texto_corpo = colors.HexColor("#26323D")

    memoria = BytesIO()
    documento = SimpleDocTemplate(
        memoria,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=18 * mm,
        bottomMargin=17 * mm,
        title=str(metadata["titulo"]),
        author=_texto(metadata["responsavel"], "Mecânica Toolkit"),
        subject="Memorial de cálculo de projeto industrial",
    )
    base = getSampleStyleSheet()
    estilos = {
        "titulo": ParagraphStyle(
            "IndustrialTitulo",
            parent=base["Title"],
            fontName=fonte.negrito,
            fontSize=18,
            leading=22,
            textColor=azul,
            alignment=TA_LEFT,
            spaceAfter=4 * mm,
        ),
        "subtitulo": ParagraphStyle(
            "IndustrialSubtitulo",
            parent=base["Normal"],
            fontName=fonte.regular,
            fontSize=8.7,
            leading=11.5,
            textColor=cinza,
            spaceAfter=4 * mm,
        ),
        "h1": ParagraphStyle(
            "IndustrialH1",
            parent=base["Heading1"],
            fontName=fonte.negrito,
            fontSize=12,
            leading=15,
            textColor=azul,
            spaceBefore=4 * mm,
            spaceAfter=2.3 * mm,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "IndustrialH2",
            parent=base["Heading2"],
            fontName=fonte.negrito,
            fontSize=10,
            leading=13,
            textColor=azul_medio,
            spaceBefore=3 * mm,
            spaceAfter=2 * mm,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "IndustrialH3",
            parent=base["Heading3"],
            fontName=fonte.negrito,
            fontSize=9,
            leading=12,
            textColor=azul_medio,
            spaceBefore=2.5 * mm,
            spaceAfter=1.5 * mm,
            keepWithNext=True,
        ),
        "corpo": ParagraphStyle(
            "IndustrialCorpo",
            parent=base["BodyText"],
            fontName=fonte.regular,
            fontSize=8.2,
            leading=11.2,
            textColor=texto_corpo,
            spaceAfter=1.8 * mm,
        ),
        "corpo_keep": ParagraphStyle(
            "IndustrialCorpoKeep",
            parent=base["BodyText"],
            fontName=fonte.regular,
            fontSize=8.2,
            leading=11.2,
            textColor=texto_corpo,
            spaceAfter=1.8 * mm,
            keepWithNext=True,
        ),
        "pequeno": ParagraphStyle(
            "IndustrialPequeno",
            parent=base["BodyText"],
            fontName=fonte.regular,
            fontSize=6.6,
            leading=8.2,
            textColor=texto_corpo,
        ),
        "cabecalho": ParagraphStyle(
            "IndustrialCabecalho",
            parent=base["BodyText"],
            fontName=fonte.negrito,
            fontSize=6.8,
            leading=8,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
    }

    def texto_pdf(valor: Any) -> str:
        # Vazio fica vazio: os textos padrão ("Não informado", "[a preencher]")
        # já foram decididos ao montar o modelo, e uma célula de assinatura
        # em branco tem de sair em branco.
        texto = "" if valor is None else str(valor)
        return texto_para_fonte(texto, fonte)

    def par(valor: Any, estilo: str = "corpo") -> Any:
        return Paragraph(escape(texto_pdf(valor)).replace("\n", "<br/>"), estilos[estilo])

    def tabela(
        cabecalhos: Sequence[Any], linhas: Sequence[Sequence[Any]], larguras: Sequence[float]
    ) -> Any:
        dados = [[par(item, "cabecalho") for item in cabecalhos]] + [
            [par(item, "pequeno") for item in linha] for linha in linhas
        ]
        tab = LongTable(
            dados, colWidths=[valor * mm for valor in larguras], repeatRows=1, hAlign="LEFT"
        )
        tab.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), azul_medio),
                    ("GRID", (0, 0), (-1, -1), 0.35, borda),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, cinza_claro]),
                ]
            )
        )
        return tab

    def caixa(conteudo: Any, *, fundo: Any = azul_claro) -> Any:
        box = Table([[conteudo]], colWidths=[180 * mm])
        box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), fundo),
                    ("BOX", (0, 0), (-1, -1), 0.5, borda),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return box

    historia: list[Any] = [
        par(metadata["titulo"], "titulo"),
        par(metadata["subtitulo"], "subtitulo"),
    ]
    identificacao = [
        [
            "Projeto",
            _campo(metadata.get("projeto")),
            "Código / revisão",
            f"{_campo(metadata.get('codigo'))} / {_texto(metadata.get('revisao'), '00')}",
        ],
        ["Cliente", _campo(metadata.get("cliente")), "Situação", _campo(metadata.get("situacao"))],
        [
            "Elaborado por",
            _campo(metadata.get("responsavel")),
            "Emissão",
            _texto(metadata.get("emissao")),
        ],
        [
            "Verificado por",
            _campo(metadata.get("verificador")),
            "Aprovado por",
            _campo(metadata.get("aprovador")),
        ],
    ]
    historia.append(tabela(["Campo", "Valor", "Campo", "Valor"], identificacao, [25, 65, 28, 62]))
    historia.append(Spacer(1, 3 * mm))
    historia.append(par("1. Resumo executivo", "h1"))
    resumo_linhas = [[item[0], item[1], item[2]] for item in modelo["resumo_executivo"]["linhas"]]
    historia.append(tabela(["Item", "Valor", "Leitura rápida"], resumo_linhas, [42, 63, 75]))
    historia.extend(
        [
            par("2. Controle do documento", "h1"),
            tabela(
                ["Rev.", "Data", "Situação", "Elaborado", "Verificado"],
                [
                    [
                        metadata["revisao"],
                        metadata["emissao"],
                        _campo(metadata["situacao"]),
                        _campo(metadata["responsavel"]),
                        _campo(metadata["verificador"]),
                    ],
                    # Linhas em branco para as próximas revisões: o molde já
                    # sai com lugar para elas.
                    ["", "", "", "", ""],
                    ["", "", "", "", ""],
                ],
                [14, 25, 46, 48, 47],
            ),
        ]
    )

    for secao in modelo["secoes"]:
        historia.append(
            par(secao.get("titulo"), {2: "h2", 3: "h3"}.get(int(secao.get("nivel", 1)), "h1"))
        )
        paragrafos_secao = list(secao.get("paragrafos", []))
        for indice_paragrafo, texto in enumerate(paragrafos_secao):
            manter_com_tabela = (
                bool(secao.get("tabelas")) and indice_paragrafo == len(paragrafos_secao) - 1
            )
            historia.append(par(texto, "corpo_keep" if manter_com_tabela else "corpo"))
        if secao.get("nota"):
            historia.append(caixa(par(f"Nota: {secao['nota']}")))
        for item in secao.get("bullets", []):
            historia.append(
                Paragraph(f"<b>-</b>&nbsp; {escape(texto_pdf(item))}", estilos["corpo"])
            )
        for formula in secao.get("formulas", []):
            historia.append(caixa(par(f"Equação: {_valor(formula)}")))
            historia.append(Spacer(1, 1.5 * mm))
        for imagem in secao.get("imagens", []):
            conteudo = imagem.get("png")
            if not conteudo:
                continue
            largura_mm = float(imagem.get("largura_mm", 165.0))
            proporcao = float(imagem.get("altura_px", 1)) / max(
                float(imagem.get("largura_px", 1)), 1.0
            )
            historia.append(
                Image(
                    BytesIO(conteudo),
                    width=largura_mm * mm,
                    height=largura_mm * proporcao * mm,
                )
            )
            if imagem.get("legenda"):
                historia.append(par(imagem["legenda"], "pequeno"))
            historia.append(Spacer(1, 2 * mm))
        for especificacao in secao.get("tabelas", []):
            if especificacao.get("legenda"):
                historia.append(par(especificacao["legenda"], "pequeno"))
            larguras_word = especificacao.get("larguras", [])
            total = sum(larguras_word) or 1
            larguras_mm = [180 * valor / total for valor in larguras_word]
            historia.append(
                tabela(especificacao["cabecalhos"], especificacao["linhas"], larguras_mm)
            )
            historia.append(Spacer(1, 2 * mm))
        for texto in secao.get("paragrafos_finais", []):
            historia.append(par(texto))

    historia.extend(
        [
            par(f"{modelo['numero_aprovacoes']}. Aprovações", "h1"),
            tabela(
                ["Função", "Nome", "Assinatura", "Data"],
                [
                    ["Elaboração", _campo(metadata["responsavel"]), "", "____/____/________"],
                    ["Verificação", _campo(metadata["verificador"]), "", "____/____/________"],
                    ["Aprovação", _campo(metadata["aprovador"]), "", "____/____/________"],
                ],
                [35, 60, 55, 30],
            ),
        ]
    )

    def rodape(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(borda)
        canvas.setFillColor(azul)
        canvas.setFont(fonte.negrito, 6.8)
        canvas.drawString(15 * mm, 289 * mm, "MECÂNICA TOOLKIT | MEMORIAL DE CÁLCULO")
        canvas.setFillColor(cinza)
        canvas.setFont(fonte.regular, 6.8)
        identificacao_curta = (
            f"{_campo(metadata['codigo'])} · Rev. {_texto(metadata['revisao'], '00')}"
        )
        canvas.drawRightString(195 * mm, 289 * mm, identificacao_curta)
        canvas.setStrokeColor(borda)
        canvas.line(15 * mm, 285 * mm, 195 * mm, 285 * mm)
        canvas.line(15 * mm, 12 * mm, 195 * mm, 12 * mm)
        canvas.setFillColor(cinza)
        canvas.setFont(fonte.regular, 6.8)
        canvas.drawString(15 * mm, 8 * mm, identificacao_curta)
        canvas.drawRightString(195 * mm, 8 * mm, f"Página {doc.page}")
        canvas.restoreState()

    documento.build(historia, onFirstPage=rodape, onLaterPages=rodape)
    return memoria.getvalue()
