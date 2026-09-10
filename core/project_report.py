"""Relatórios modulares do projeto industrial permanente."""

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
from core.memorial_word import CAUTION, POSITIVE, RISK, gerar_memorial_word_padrao
from core.project_validation import validar_projeto
from core.report_plugins import listar_provedores, titulos_secoes_extensao
from core.technical_records import avaliar_contrato_registro

_SECOES_BASE = (
    ("escopo", "Objetivo e escopo"),
    ("base", "Base de projeto"),
    ("componentes", "Equipamentos e escopo físico"),
    ("materiais", "Materiais e propriedades rastreadas"),
    ("normas", "Matriz normativa"),
    ("plano_calculo", "Plano e integridade dos cálculos"),
    ("registros", "Registros técnicos"),
    ("sensibilidade", "Sensibilidade, incertezas e robustez"),
    ("validacao", "Central de validação"),
    ("checklist", "Pendências e checklist"),
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


def _valor(valor: Any) -> str:
    if valor is None:
        return "Não informado"
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, float):
        if not math.isfinite(valor):
            return "Não finito"
        return f"{valor:.5g}".replace(".", ",")
    if isinstance(valor, (list, tuple, set)):
        texto = "; ".join(_valor(item) for item in valor) or "Não informado"
        return texto if len(texto) <= 1400 else texto[:1360] + "… [resumido; consulte o registro permanente]"
    if isinstance(valor, Mapping):
        texto = "; ".join(f"{chave}: {_valor(item)}" for chave, item in valor.items()) or "Não informado"
        return texto if len(texto) <= 1400 else texto[:1360] + "… [resumido; consulte o registro permanente]"
    texto = _texto(valor)
    return texto if len(texto) <= 1400 else texto[:1360] + "… [resumido; consulte o registro permanente]"


def _rotulo_e_unidade(chave: Any) -> tuple[str, str]:
    texto = _texto(chave)
    unidades = {
        "_MPa": "MPa", "_GPa": "GPa", "_kPa": "kPa", "_kN": "kN",
        "_kNm": "kN·m", "_mm4": "mm⁴", "_mm3": "mm³", "_mm2": "mm²",
        "_mm": "mm", "_bar": "bar", "_C": "°C", "_F": "°F", "_ciclos": "ciclos", "_pct": "%",
    }
    unidade = "-"
    base = texto
    for sufixo, candidato in sorted(unidades.items(), key=lambda item: len(item[0]), reverse=True):
        if texto.endswith(sufixo):
            base = texto[: -len(sufixo)]
            unidade = candidato
            break
    rotulo = base.replace("_", " ").strip().capitalize() or texto
    return rotulo, unidade


def _campo_legivel(chave: Any) -> str:
    rotulo, unidade = _rotulo_e_unidade(chave)
    return f"{rotulo} [{unidade}]" if unidade != "-" else rotulo


def _status_relatorio(validacao: Mapping[str, Any]) -> tuple[str, str, str]:
    contagens = validacao.get("contagens", {})
    bloqueios = int(contagens.get("Bloqueio", 0))
    pendencias = int(contagens.get("Pendência", 0))
    atencoes = int(contagens.get("Atenção", 0))
    if bloqueios:
        return (
            "NÃO PRONTO PARA EMISSÃO",
            RISK,
            f"Há {bloqueios} bloqueio(s) que exigem tratamento e disposição técnica.",
        )
    if pendencias:
        return (
            "EM CONSOLIDAÇÃO",
            CAUTION,
            f"Há {pendencias} pendência(s) documental(is) ou técnica(s) em aberto.",
        )
    if atencoes:
        return (
            "PRONTO COM RESSALVAS",
            CAUTION,
            f"Não há bloqueios, mas permanecem {atencoes} ponto(s) de atenção.",
        )
    return (
        "PRONTO PARA REVISÃO",
        POSITIVE,
        "A matriz automática não encontrou bloqueios; a revisão de engenharia continua obrigatória.",
    )


def _filtrar_registros(
    projeto: Mapping[str, Any], registros_ids: Sequence[str] | None
) -> list[Mapping[str, Any]]:
    registros = [
        item for item in projeto.get("registros_tecnicos", []) if isinstance(item, Mapping)
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
    nivel = "Completo" if percentual == 100 else ("Utilizável com ressalvas" if percentual >= 67 else "Incompleto")
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
        "casos_carga": projeto.get("casos_carga", []),
        "combinacoes_carga": projeto.get("combinacoes_carga", []),
        "normas": projeto.get("normas", []),
        "registros": list(registros),
        "checklist": projeto.get("checklist", []),
    }
    serializado = json.dumps(pacote, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def _metadados(
    projeto: Mapping[str, Any], metadata_extra: Mapping[str, Any] | None
) -> dict[str, Any]:
    extras = dict(metadata_extra or {})
    emissao = extras.get("emissao") or datetime.now().astimezone().strftime("%d/%m/%Y")
    return {
        "titulo": extras.get("titulo") or "Memorial técnico do projeto industrial",
        "subtitulo": extras.get("subtitulo") or "Base de projeto, registros técnicos e central de validação",
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
    validacao = validar_projeto(projeto)
    status = _status_relatorio(validacao)
    metadata = _metadados(projeto, metadata_extra)
    registros = _filtrar_registros(projeto, registros_ids)
    componentes = [item for item in projeto.get("componentes", []) if isinstance(item, Mapping)]
    materiais = [item for item in projeto.get("materiais_projeto", []) if isinstance(item, Mapping)]
    normas = [item for item in projeto.get("normas", []) if isinstance(item, Mapping)]
    checklist = [item for item in projeto.get("checklist", []) if isinstance(item, Mapping)]
    casos_carga = [item for item in projeto.get("casos_carga", []) if isinstance(item, Mapping)]
    combinacoes_carga = [item for item in projeto.get("combinacoes_carga", []) if isinstance(item, Mapping)]
    base = projeto.get("base_projeto", {}) if isinstance(projeto.get("base_projeto"), Mapping) else {}
    registros_sensibilidade = [
        item for item in registros if "sensibilidade" in _texto(item.get("modulo"), "").casefold()
    ]
    registros_capitulos = [
        item for item in registros
        if item not in registros_sensibilidade or "sensibilidade" not in ativas
    ]
    hash_snapshot = _hash_snapshot(projeto, registros, sorted(ativas), metadata)
    metadata["snapshot_hash"] = hash_snapshot

    resumo = [
        {"rotulo": "Situação", "valor": validacao["prontidao"]},
        {"rotulo": "Registros", "valor": str(len(registros))},
        {"rotulo": "Materiais rastreados", "valor": str(len(materiais))},
        {"rotulo": "Índice documental", "valor": f"{validacao['indice_documental']}%"},
        {"rotulo": "Revisão", "valor": metadata["revisao"]},
    ]
    resumo_executivo = {
        "linhas": [
            ["Projeto", _texto(projeto.get("nome")), f"Código {_texto(projeto.get('codigo'))}."],
            ["Unidade / área", f"{_texto(projeto.get('unidade_industrial'))} / {_texto(projeto.get('area'))}", f"TAG: {_texto(projeto.get('tag_equipamento'))}."],
            ["Escopo físico", f"{len(componentes)} item(ns)", "Equipamentos, estruturas, linhas ou pontos cadastrados."],
            ["Carregamentos", f"{len(casos_carga)} caso(s) / {len(combinacoes_carga)} combinação(ões)", "Cenários e fatores permanentes vinculados ao projeto."],
            ["Materiais", f"{len(materiais)} cadastro(s) de projeto", f"{sum(avaliar_material(item)['nivel'] in {'Confirmado', 'Rastreável'} for item in materiais)} com confiança confirmada ou rastreável."],
            ["Base normativa", f"{len(normas)} referência(s)", f"{sum(bool(item.get('conferida')) for item in normas)} conferida(s) no documento-fonte."],
            ["Robustez", f"{len(registros_sensibilidade)} análise(s)", "Sensibilidade e incerteza separadas do resultado determinístico."],
            ["Validação", validacao["prontidao"], f"{validacao['total_achados']} achado(s); índice documental {validacao['indice_documental']}%."],
        ]
    }

    secoes: list[dict[str, Any]] = []
    numero = 3

    contexto_extensoes = {
        "registros": registros,
        "validacao": validacao,
        "metadata": metadata,
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
            conteudo["titulo"] = f"{numero}. {SECOES_RELATORIO[provedor.id]}"
            secoes.append(conteudo)
            numero += 1

    def adicionar(
        chave: str, conteudo: dict[str, Any], *, incluir_extensoes: bool = True
    ) -> None:
        nonlocal numero
        if chave not in ativas:
            pass
        else:
            conteudo["titulo"] = f"{numero}. {SECOES_RELATORIO[chave]}"
            secoes.append(conteudo)
            numero += 1
        if incluir_extensoes:
            anexar_extensoes(chave)

    adicionar(
        "escopo",
        {
            "paragrafos": [
                _texto(projeto.get("objetivo"), "Objetivo ainda não documentado."),
                _texto(projeto.get("descricao"), "Descrição do projeto ainda não documentada."),
                f"Processo ou serviço: {_texto(projeto.get('processo'))}. Regime de operação: {_texto(projeto.get('regime_operacao'))}.",
            ],
            "nota": "O memorial é válido somente para o escopo, os dados e as revisões identificados neste documento.",
        },
    )
    adicionar(
        "base",
        {
            "tabelas": [{
                "legenda": "Base de projeto e critérios adotados.",
                "cabecalhos": ["Tópico", "Registro"],
                "linhas": [
                    ["Desenhos e documentos", _texto(base.get("referencias_desenho"))],
                    ["Base dos carregamentos", _texto(base.get("base_carregamentos"))],
                    ["Condições de operação", _texto(base.get("condicoes_operacao"))],
                    ["Critérios de aceitação", _texto(base.get("criterio_aceitacao"))],
                    ["Vida requerida", _texto(base.get("vida_requerida"))],
                    ["Limitações e exclusões", _texto(base.get("limitacoes"))],
                ],
                "larguras": [2600, 6760],
                "fonte": 8.2,
            }]
        },
    )
    adicionar(
        "componentes",
        {
            "paragrafos": ["Relação permanente dos equipamentos, sistemas, estruturas e pontos incluídos no escopo."],
            "tabelas": [{
                "cabecalhos": ["TAG", "Descrição / serviço", "Material / fonte", "Desenho", "Criticidade"],
                "linhas": [
                    [
                        _texto(item.get("tag")),
                        f"{_texto(item.get('descricao'))}\n{_texto(item.get('servico'), '')}",
                        f"{_texto(item.get('material'))}\n{_texto(item.get('fonte_material'), '')}",
                        _texto(item.get("desenho")),
                        _texto(item.get("criticidade")),
                    ]
                    for item in componentes
                ] or [["-", "Nenhum item cadastrado", "-", "-", "-"]],
                "larguras": [1200, 2600, 2300, 1700, 1560],
                "fonte": 7.4,
            }]
        },
    )
    adicionar(
        "materiais",
        {
            "paragrafos": [
                "Propriedades de catálogo permanecem orientativas. Esta seção lista apenas os materiais cadastrados no projeto, com sua proveniência e avaliação documental.",
                "O índice de rastreabilidade mede evidência disponível; não substitui especificação, certificado, ensaio ou aprovação técnica.",
            ],
            "tabelas": [{
                "cabecalhos": ["Material / condição", "Propriedades", "Origem / documento", "Confiança", "Aplicabilidade"],
                "linhas": [
                    [
                        f"{_texto(item.get('nome'))}\n{_texto(item.get('condicao'), '')} · {_texto(item.get('forma_produto'), '')}",
                        "; ".join(
                            f"{_rotulo_e_unidade(chave)[0]}={_valor(valor)} {_rotulo_e_unidade(chave)[1]}".strip()
                            for chave, valor in (item.get("propriedades", {}) if isinstance(item.get("propriedades"), Mapping) else {}).items()
                            if valor is not None
                        ) or "Sem propriedades registradas",
                        resumir_fonte(item),
                        f"{avaliar_material(item)['nivel']}\n{avaliar_material(item)['indice_rastreabilidade']}%",
                        _texto(item.get("aplicabilidade")),
                    ]
                    for item in materiais
                ] or [["Nenhum material de projeto", "-", "-", "Referência", "Cadastrar e vincular antes da emissão"]],
                "larguras": [2100, 1900, 2100, 1200, 2060],
                "fonte": 7.0,
            }],
        },
    )
    adicionar(
        "normas",
        {
            "paragrafos": ["A marca de conferência significa apenas que a edição e o escopo foram verificados no documento-fonte cadastrado."],
            "tabelas": [{
                "cabecalhos": ["Código", "Edição", "Escopo no projeto", "Obrigatória", "Conferida", "Fonte"],
                "linhas": [
                    [_texto(item.get("codigo")), _texto(item.get("edicao")), _texto(item.get("escopo")), _valor(item.get("obrigatoria", False)), _valor(item.get("conferida", False)), _texto(item.get("fonte"))]
                    for item in normas
                ] or [["-", "-", "Nenhuma referência cadastrada", "-", "-", "-"]],
                "larguras": [1400, 900, 2800, 1100, 1100, 2060],
                "fonte": 7.3,
            }]
        },
    )

    adicionar(
        "plano_calculo",
        {
            "paragrafos": [
                "O plano abaixo define a ordem dos capítulos selecionados e evidencia campos ausentes antes da emissão. A sequência é preservada no Word e no PDF."
            ],
            "tabelas": [{
                "cabecalhos": ["Ordem", "Módulo / registro", "Situação", "Integridade", "Lacunas"],
                "linhas": [
                    [
                        str(indice),
                        (
                            f"{_texto(item.get('modulo'))}\n{_texto(item.get('titulo'))}\n"
                            f"{_texto(item.get('modulo_id'), 'legado')} v{_texto(item.get('modulo_versao'), '-')}"
                        ),
                        _texto(item.get("status")),
                        f"{avaliar_integridade_registro(item)['nivel']} ({avaliar_integridade_registro(item)['percentual']}%)",
                        ", ".join(avaliar_integridade_registro(item)["faltantes"]) or "Nenhuma lacuna estrutural",
                    ]
                    for indice, item in enumerate(registros, start=1)
                ] or [["-", "Nenhum registro selecionado", "Pendente", "Incompleto", "Anexar cálculos"]],
                "larguras": [700, 2900, 1300, 1900, 2560],
                "fonte": 7.2,
            }],
        },
    )

    if "registros" in ativas:
        titulo_secao = f"{numero}. {SECOES_RELATORIO['registros']}"
        secoes.append({
            "titulo": titulo_secao,
            "paragrafos": ["Cada registro abaixo preserva entradas, resultados, premissas, alertas e conclusão do módulo que o originou."],
        })
        for indice, registro in enumerate(registros_capitulos, start=1):
            entradas = registro.get("entradas", {}) if isinstance(registro.get("entradas"), Mapping) else {}
            resultados = registro.get("resultados", {}) if isinstance(registro.get("resultados"), Mapping) else {}
            contrato = avaliar_contrato_registro(registro)
            secoes.append({
                "titulo": f"{numero}.{indice} {_texto(registro.get('titulo'), 'Registro técnico')}",
                "nivel": 2,
                "paragrafos": [
                    f"Módulo: {_texto(registro.get('modulo'))}. Situação: {_texto(registro.get('status'))}.",
                    _texto(registro.get("resumo"), "Resumo não informado."),
                    f"Método: {_texto(registro.get('metodo'), 'Não detalhado no registro de origem.')} Integridade: {avaliar_integridade_registro(registro)['percentual']}%.",
                    (
                        f"Contrato: {_texto(registro.get('schema_registro'), 'registro legado')}; "
                        f"módulo {_texto(registro.get('modulo_id'), 'não identificado')} v{_texto(registro.get('modulo_versao'), '-')}; "
                        f"assinatura {'válida' if contrato['assinatura_valida'] else 'não disponível ou divergente'}."
                    ),
                    f"Conclusão: {_texto(registro.get('conclusao'))}",
                ],
                "bullets": [f"Premissa: {_valor(item)}" for item in registro.get("premissas", [])]
                + [f"Critério: {_valor(item)}" for item in registro.get("criterios", [])]
                + [f"Alerta: {_valor(item)}" for item in registro.get("alertas", [])]
                + [f"Referência: {_valor(item)}" for item in registro.get("referencias", [])],
                "formulas": [_valor(item) for item in registro.get("equacoes", [])],
                "tabelas": [
                    {
                        "legenda": "Entradas registradas.",
                        "cabecalhos": ["Campo", "Valor"],
                        "linhas": [[_campo_legivel(chave), _valor(valor)] for chave, valor in entradas.items()] or [["-", "Não registradas"]],
                        "larguras": [3000, 6360],
                        "fonte": 7.8,
                    },
                    {
                        "legenda": "Resultados registrados.",
                        "cabecalhos": ["Grandeza / critério", "Valor"],
                        "linhas": [[_campo_legivel(chave), _valor(valor)] for chave, valor in resultados.items()] or [["-", "Não registrados"]],
                        "larguras": [3000, 6360],
                        "fonte": 7.8,
                    },
                ],
            })
        if not registros_capitulos:
            secoes[-1]["nota"] = "Nenhum registro técnico foi selecionado para esta emissão."
        numero += 1
    anexar_extensoes("registros")

    if "sensibilidade" in ativas:
        titulo_secao = f"{numero}. {SECOES_RELATORIO['sensibilidade']}"
        secoes.append({
            "titulo": titulo_secao,
            "paragrafos": [
                "As análises abaixo mostram dependência local das entradas e, quando disponível, propagação probabilística das incertezas declaradas. Elas não corrigem limitações do modelo físico."
            ],
        })
        for indice, registro in enumerate(registros_sensibilidade, start=1):
            resultados_sens = registro.get("resultados", {}) if isinstance(registro.get("resultados"), Mapping) else {}
            ranking = resultados_sens.get("ranking_sensibilidade", [])
            correlacoes = resultados_sens.get("correlacoes_spearman", [])
            criterio_prob = resultados_sens.get("probabilidade_nao_atendimento_pct")
            secoes.append({
                "titulo": f"{numero}.{indice} {_texto(registro.get('titulo'), 'Análise de sensibilidade')}",
                "nivel": 2,
                "paragrafos": [
                    _texto(registro.get("resumo"), "Resumo não informado."),
                    f"Resultado nominal: {_valor(resultados_sens.get('saida_nominal'))} {_texto(resultados_sens.get('unidade_saida'), '')}. "
                    f"Faixa P05–P95: {_valor(resultados_sens.get('p05'))} a {_valor(resultados_sens.get('p95'))}. "
                    f"Probabilidade de não atendimento: {_valor(criterio_prob) if criterio_prob is not None else 'não avaliada'}{('%' if criterio_prob is not None else '')}.",
                    f"Conclusão: {_texto(registro.get('conclusao'))}",
                ],
                "tabelas": [
                    {
                        "legenda": "Ranking por efeito OAT no intervalo informado.",
                        "cabecalhos": ["Entrada", "Impacto (%)", "Elasticidade", "Direção crítica"],
                        "linhas": [
                            [_texto(item.get("variavel")), _valor(item.get("impacto_percentual")), _valor(item.get("elasticidade")), _texto(item.get("direcao_critica"))]
                            for item in ranking if isinstance(item, Mapping)
                        ] or [["Não registrado", "-", "-", "-"]],
                        "larguras": [3500, 1800, 1800, 2260],
                        "fonte": 7.8,
                    },
                    {
                        "legenda": "Associação monotônica na simulação de Monte Carlo.",
                        "cabecalhos": ["Entrada", "Correlação de Spearman"],
                        "linhas": [
                            [_texto(item.get("variavel")), _valor(item.get("correlacao"))]
                            for item in correlacoes if isinstance(item, Mapping)
                        ] or [["Não registrada", "-"]],
                        "larguras": [5200, 4160],
                        "fonte": 8.0,
                    },
                ],
                "nota": _texto(registro.get("metodo"), "Verifique faixas, distribuições, correlações e semente usadas."),
            })
        if not registros_sensibilidade:
            secoes[-1]["nota"] = "Nenhuma análise de sensibilidade foi selecionada para esta emissão."
        numero += 1

    achados = validacao["achados"]
    adicionar(
        "validacao",
        {
            "paragrafos": [
                f"Prontidão: {validacao['prontidao']}. Índice documental: {validacao['indice_documental']}%.",
                validacao["aviso"],
            ],
            "tabelas": [{
                "cabecalhos": ["ID", "Severidade", "Categoria / módulo", "Achado", "Ação recomendada"],
                "linhas": [[item["id"], item["severidade"], f"{item['categoria']}\n{item['modulo']}", f"{item['titulo']}\n{item['detalhe']}", item["recomendacao"]] for item in achados]
                or [["-", "Informação", "Validação", "Nenhum achado automático", "Manter revisão independente"]],
                "larguras": [700, 1100, 1700, 2860, 3000],
                "fonte": 6.9,
            }]
        },
    )
    adicionar(
        "checklist",
        {
            "tabelas": [{
                "cabecalhos": ["Item", "Categoria", "Responsável", "Prazo", "Estado", "Crítico", "Evidência"],
                "linhas": [[_texto(item.get("item")), _texto(item.get("categoria")), _texto(item.get("responsavel")), _texto(item.get("prazo")), _texto(item.get("estado")), _valor(item.get("critico", False)), _texto(item.get("evidencia"))] for item in checklist]
                or [["Nenhum item cadastrado", "-", "-", "-", "-", "-", "-"]],
                "larguras": [2300, 1100, 1300, 900, 1000, 800, 1960],
                "fonte": 6.9,
            }]
        },
    )
    adicionar(
        "conclusao",
        {
            "paragrafos": [
                f"Situação automática: {status[0]}. {status[2]}",
                "A liberação depende da revisão de engenharia, da confirmação das fontes normativas e do encerramento formal dos bloqueios aplicáveis.",
                f"Identificador reproduzível desta composição: SHA-256 {hash_snapshot[:16]}… O hash muda quando seleção, ordem, dados ou metadados mudam.",
            ],
            "bullets": [
                "Confirmar que os carregamentos representam partida, parada, operação, manutenção e condições anormais aplicáveis.",
                "Rastrear materiais, espessuras, geometria e condições de contorno aos documentos controlados.",
                "Encerrar ou aceitar formalmente cada pendência, mantendo responsável e evidência.",
                "Emitir nova revisão sempre que entradas, critérios ou resultados forem alterados.",
            ],
        },
    )

    quadro_dados: list[dict[str, str]] = []
    for registro in registros:
        for grupo, chave in (("Entradas", "entradas"), ("Resultados", "resultados")):
            dados = registro.get(chave, {}) if isinstance(registro.get(chave), Mapping) else {}
            for grandeza, valor in dados.items():
                if grandeza in {"ranking_sensibilidade", "correlacoes_spearman"}:
                    # Estes dados já aparecem em tabelas próprias, mais legíveis.
                    continue
                if grandeza == "incertezas" and isinstance(valor, Mapping):
                    for variavel, configuracao in valor.items():
                        rotulo, unidade = _rotulo_e_unidade(variavel)
                        quadro_dados.append({
                            "Grupo": f"{_texto(registro.get('modulo'))} - Incertezas",
                            "Grandeza": rotulo,
                            "Símbolo": "-",
                            "Valor": (
                                f"{_valor(configuracao.get('incerteza_percentual'))}% · {_texto(configuracao.get('distribuicao'))}"
                                if isinstance(configuracao, Mapping)
                                else _valor(configuracao)
                            ),
                            "Unidade": unidade,
                            "Observação": "Faixa/distribuição declarada; conferir o registro permanente",
                        })
                    continue
                rotulo, unidade = _rotulo_e_unidade(grandeza)
                quadro_dados.append({
                    "Grupo": f"{_texto(registro.get('modulo'))} - {grupo}",
                    "Grandeza": rotulo,
                    "Símbolo": "-",
                    "Valor": _valor(valor),
                    "Unidade": unidade,
                    "Observação": _texto(registro.get("titulo")),
                })
    if not quadro_dados:
        quadro_dados.append({"Grupo": "Projeto", "Grandeza": "Registros técnicos", "Símbolo": "-", "Valor": "Nenhum selecionado", "Unidade": "-", "Observação": "Completar antes da emissão final"})

    partes = [
        [
            _texto(registro.get("modulo")),
            _texto(registro.get("documento"), metadata["codigo"]),
            _texto(registro.get("revisao"), metadata["revisao"]),
            _texto(registro.get("status")),
            _texto(registro.get("responsavel"), metadata["responsavel"]),
            _texto(registro.get("conclusao")),
        ]
        for registro in registros
    ] or [["Projeto industrial", metadata["codigo"], metadata["revisao"], validacao["prontidao"], metadata["responsavel"], "Nenhum registro técnico selecionado"]]

    metadata["numero_integracao"] = numero
    metadata["numero_aprovacoes"] = numero + 1

    return {
        "metadata": metadata,
        "resumo": resumo,
        "resumo_executivo": resumo_executivo,
        "status": status,
        "secoes": secoes,
        "quadro_dados": quadro_dados,
        "partes_complementares": partes,
        "validacao": validacao,
        "registros": registros,
        "secoes_incluidas": list(ativas),
        "snapshot_hash": hash_snapshot,
        "numero_integracao": numero,
        "numero_aprovacoes": numero + 1,
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
        status=modelo["status"],
        secoes=modelo["secoes"],
        quadro_dados=modelo["quadro_dados"],
        partes_complementares=modelo["partes_complementares"],
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
            PageBreak,
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
    azul = colors.HexColor("#16324F")
    azul_medio = colors.HexColor("#24577A")
    azul_claro = colors.HexColor("#EAF2F8")
    cinza = colors.HexColor("#5F6B76")
    cinza_claro = colors.HexColor("#F4F6F8")
    borda = colors.HexColor("#C9D4DE")

    memoria = BytesIO()
    documento = SimpleDocTemplate(
        memoria,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=18 * mm,
        bottomMargin=17 * mm,
        title=str(metadata["titulo"]),
        author=str(metadata["responsavel"]),
        subject="Memorial técnico de projeto industrial",
    )
    base = getSampleStyleSheet()
    estilos = {
        "titulo": ParagraphStyle("IndustrialTitulo", parent=base["Title"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=azul, alignment=TA_LEFT, spaceAfter=4 * mm),
        "subtitulo": ParagraphStyle("IndustrialSubtitulo", parent=base["Normal"], fontSize=8.7, leading=11.5, textColor=cinza, spaceAfter=4 * mm),
        "h1": ParagraphStyle("IndustrialH1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=azul, spaceBefore=4 * mm, spaceAfter=2.3 * mm, keepWithNext=True),
        "h2": ParagraphStyle("IndustrialH2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=azul_medio, spaceBefore=3 * mm, spaceAfter=2 * mm, keepWithNext=True),
        "corpo": ParagraphStyle("IndustrialCorpo", parent=base["BodyText"], fontSize=8.2, leading=11.2, textColor=colors.HexColor("#26323D"), spaceAfter=1.8 * mm),
        "corpo_keep": ParagraphStyle("IndustrialCorpoKeep", parent=base["BodyText"], fontSize=8.2, leading=11.2, textColor=colors.HexColor("#26323D"), spaceAfter=1.8 * mm, keepWithNext=True),
        "pequeno": ParagraphStyle("IndustrialPequeno", parent=base["BodyText"], fontSize=6.6, leading=8.2, textColor=colors.HexColor("#26323D")),
        "cabecalho": ParagraphStyle("IndustrialCabecalho", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=6.8, leading=8, textColor=colors.white, alignment=TA_CENTER),
        "status": ParagraphStyle("IndustrialStatus", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=colors.white, alignment=TA_CENTER),
    }

    def texto_pdf(valor: Any) -> str:
        texto = _texto(valor)
        substituicoes = {
            "σvm": "sigma_vm", "σx": "sigma_x", "σy": "sigma_y", "σa": "sigma_a",
            "σm": "sigma_m", "τxy": "tau_xy", "ΔL": "Delta_L", "ΔT": "Delta_T",
            "≥": ">=", "≤": "<=", "σ": "sigma", "τ": "tau", "Δ": "Delta",
            "Σ": "SUM", "γ": "gamma", "α": "alpha", "ν": "nu", "√": "sqrt",
            "→": "->", "∞": "infinito",
            "²": "^2", "³": "^3", "⁴": "^4", "–": "-", "—": "-",
        }
        for original, substituto in substituicoes.items():
            texto = texto.replace(original, substituto)
        return texto

    def par(valor: Any, estilo: str = "corpo") -> Any:
        return Paragraph(escape(texto_pdf(valor)).replace("\n", "<br/>"), estilos[estilo])

    def tabela(cabecalhos: Sequence[Any], linhas: Sequence[Sequence[Any]], larguras: Sequence[float]) -> Any:
        dados = [[par(item, "cabecalho") for item in cabecalhos]] + [[par(item, "pequeno") for item in linha] for linha in linhas]
        tab = LongTable(dados, colWidths=[valor * mm for valor in larguras], repeatRows=1, hAlign="LEFT")
        tab.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), azul_medio),
            ("GRID", (0, 0), (-1, -1), 0.35, borda),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, cinza_claro]),
        ]))
        return tab

    historia: list[Any] = [par(metadata["titulo"], "titulo"), par(metadata["subtitulo"], "subtitulo")]
    identificacao = [
        ["Projeto", _texto(metadata.get("projeto")), "Código / revisão", f"{_texto(metadata.get('codigo'))} / {metadata.get('revisao')}"],
        ["Cliente", _texto(metadata.get("cliente")), "Situação", _texto(metadata.get("situacao"))],
        ["Responsável", _texto(metadata.get("responsavel")), "Emissão", _texto(metadata.get("emissao"))],
        ["Snapshot", f"{_texto(metadata.get('snapshot_hash'))[:16]}…", "Aprovador", _texto(metadata.get("aprovador"))],
    ]
    historia.append(tabela(["Campo", "Valor", "Campo", "Valor"], identificacao, [25, 65, 28, 62]))
    historia.append(Spacer(1, 4 * mm))
    status_texto, status_cor, status_detalhe = modelo["status"]
    status_tab = Table([[par(status_texto, "status")], [par(status_detalhe)]], colWidths=[180 * mm])
    status_tab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{status_cor}")),
        ("BACKGROUND", (0, 1), (-1, 1), azul_claro),
        ("BOX", (0, 0), (-1, -1), 0.6, borda),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    historia.extend([status_tab, Spacer(1, 3 * mm), par("1. Resumo executivo", "h1")])
    resumo_linhas = [[item[0], item[1], item[2]] for item in modelo["resumo_executivo"]["linhas"]]
    historia.append(tabela(["Item", "Valor", "Leitura rápida"], resumo_linhas, [42, 63, 75]))
    historia.extend([par("2. Controle do documento", "h1"), tabela(["Rev.", "Data", "Situação", "Elaborado", "Verificado"], [[metadata["revisao"], metadata["emissao"], metadata["situacao"], metadata["responsavel"], metadata["verificador"]]], [14, 25, 46, 48, 47])])

    for secao in modelo["secoes"]:
        historia.append(par(secao.get("titulo"), "h2" if int(secao.get("nivel", 1)) == 2 else "h1"))
        paragrafos_secao = list(secao.get("paragrafos", []))
        for indice_paragrafo, texto in enumerate(paragrafos_secao):
            manter_com_tabela = bool(secao.get("tabelas")) and indice_paragrafo == len(paragrafos_secao) - 1
            historia.append(par(texto, "corpo_keep" if manter_com_tabela else "corpo"))
        if secao.get("nota"):
            nota = Table([[par(f"Nota: {secao['nota']}")]], colWidths=[180 * mm])
            nota.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), azul_claro), ("BOX", (0, 0), (-1, -1), 0.5, borda), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
            historia.append(nota)
        for item in secao.get("bullets", []):
            historia.append(Paragraph(f"<b>-</b>&nbsp; {escape(texto_pdf(item))}", estilos["corpo"]))
        for formula in secao.get("formulas", []):
            formula_box = Table([[par(f"Equação: {_valor(formula)}")]], colWidths=[180 * mm])
            formula_box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), azul_claro),
                ("BOX", (0, 0), (-1, -1), 0.45, borda),
                ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            historia.append(formula_box)
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
            historia.append(tabela(especificacao["cabecalhos"], especificacao["linhas"], larguras_mm))
            historia.append(Spacer(1, 2 * mm))

    historia.extend([
        par(f"{modelo['numero_integracao']}. Integração com outras partes do projeto", "h1"),
        par("Cada disciplina conserva código, revisão, responsável, situação e conclusão próprios.", "corpo_keep"),
        tabela(
            ["Parte / módulo", "Documento", "Rev.", "Situação", "Responsável", "Observações"],
            modelo["partes_complementares"],
            [31, 31, 13, 26, 31, 48],
        ),
        par(f"{modelo['numero_aprovacoes']}. Aprovações", "h1"),
        tabela(
            ["Função", "Nome", "Assinatura / data"],
            [["Elaboração", metadata["responsavel"], ""], ["Verificação", metadata["verificador"], ""], ["Aprovação", metadata["aprovador"], ""]],
            [42, 65, 73],
        ),
        PageBreak(),
        par("Apêndice A - Quadro consolidado de entradas e resultados", "h1"),
        par("Os valores abaixo são reproduzidos dos registros selecionados. A unidade e a origem devem ser conferidas no módulo de cálculo."),
        tabela(
            ["Grupo", "Grandeza", "Valor", "Unidade", "Observação"],
            [[linha["Grupo"], linha["Grandeza"], linha["Valor"], linha["Unidade"], linha["Observação"]] for linha in modelo["quadro_dados"]],
            [42, 46, 32, 22, 38],
        ),
    ])

    def rodape(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(borda)
        canvas.setFillColor(azul)
        canvas.setFont("Helvetica-Bold", 6.8)
        canvas.drawString(15 * mm, 289 * mm, "MECÂNICA TOOLKIT | MEMORIAL TÉCNICO")
        canvas.setFillColor(cinza)
        canvas.setFont("Helvetica", 6.8)
        canvas.drawRightString(195 * mm, 289 * mm, f"{_texto(metadata['codigo'])} · Rev. {_texto(metadata['revisao'])}")
        canvas.setStrokeColor(borda)
        canvas.line(15 * mm, 285 * mm, 195 * mm, 285 * mm)
        canvas.line(15 * mm, 12 * mm, 195 * mm, 12 * mm)
        canvas.setFillColor(cinza)
        canvas.setFont("Helvetica", 6.8)
        canvas.drawString(15 * mm, 8 * mm, f"{_texto(metadata['codigo'])} · Rev. {_texto(metadata['revisao'])}")
        canvas.drawRightString(195 * mm, 8 * mm, f"Página {doc.page}")
        canvas.restoreState()

    documento.build(historia, onFirstPage=rodape, onLaterPages=rodape)
    return memoria.getvalue()
