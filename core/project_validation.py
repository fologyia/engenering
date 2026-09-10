"""Validação documental e técnica de projetos industriais.

As regras deste módulo não substituem a verificação de conformidade normativa.
Elas detectam lacunas, inconsistências e resultados técnicos já registrados pelo
próprio usuário, produzindo uma fila rastreável para a Central de Validação.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from core.materials_registry import avaliar_material
from core.validation_plugins import executar_regras

SEVERIDADES = ("Bloqueio", "Atenção", "Pendência", "Informação")
ORDEM_SEVERIDADE = {nome: indice for indice, nome in enumerate(SEVERIDADES)}


@dataclass(frozen=True)
class AchadoValidacao:
    id: str
    severidade: str
    categoria: str
    titulo: str
    detalhe: str
    recomendacao: str
    modulo: str = "Projeto"
    evidencia: str = ""

    def como_dict(self) -> dict[str, str]:
        return asdict(self)


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def _numero(valor: Any) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, str):
        limpo = valor.strip().replace(" ", "").replace(",", ".")
        if not limpo:
            return None
        valor = limpo
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def _achado(
    contador: int,
    severidade: str,
    categoria: str,
    titulo: str,
    detalhe: str,
    recomendacao: str,
    *,
    modulo: str = "Projeto",
    evidencia: str = "",
) -> AchadoValidacao:
    return AchadoValidacao(
        id=f"VAL-{contador:04d}",
        severidade=severidade,
        categoria=categoria,
        titulo=titulo,
        detalhe=detalhe,
        recomendacao=recomendacao,
        modulo=modulo,
        evidencia=evidencia,
    )


def _procurar_numero(dados: Mapping[str, Any], nomes: Sequence[str]) -> float | None:
    normalizados = {str(chave).lower().strip(): valor for chave, valor in dados.items()}
    for nome in nomes:
        if nome.lower() in normalizados:
            numero = _numero(normalizados[nome.lower()])
            if numero is not None:
                return numero
    return None


def validar_projeto(projeto: Mapping[str, Any]) -> dict[str, Any]:
    """Executa a matriz de validação e devolve achados e indicadores.

    O índice documental mede somente o preenchimento e a rastreabilidade dos
    campos previstos. Ele não certifica segurança, conformidade ou aprovação.
    """

    achados: list[AchadoValidacao] = []

    def adicionar(*args: Any, **kwargs: Any) -> None:
        achados.append(_achado(len(achados) + 1, *args, **kwargs))

    campos_criticos = {
        "nome": "nome do projeto",
        "codigo": "código do projeto",
        "cliente": "cliente ou solicitante",
        "unidade_industrial": "unidade industrial",
        "area": "área/setor",
        "tag_equipamento": "TAG do equipamento ou sistema",
        "objetivo": "objetivo do projeto",
        "responsavel": "responsável técnico",
    }
    preenchidos = 0
    pontos_totais = len(campos_criticos)
    for campo, rotulo in campos_criticos.items():
        if _texto(projeto.get(campo)):
            preenchidos += 1
        else:
            severidade = "Bloqueio" if campo in {"nome", "codigo", "objetivo"} else "Pendência"
            adicionar(
                severidade,
                "Identificação",
                f"Falta informar {rotulo}",
                "O campo está vazio no cadastro permanente do projeto.",
                f"Preencha {rotulo} em Gestão de projetos > Dados gerais.",
            )

    for campo, rotulo in (("verificador", "verificador"), ("aprovador", "aprovador")):
        pontos_totais += 1
        if _texto(projeto.get(campo)):
            preenchidos += 1
        else:
            adicionar(
                "Atenção",
                "Responsabilidades",
                f"{rotulo.capitalize()} não definido",
                "A cadeia de elaboração, verificação e aprovação está incompleta.",
                f"Defina o {rotulo} antes da emissão do memorial final.",
            )

    base = projeto.get("base_projeto", {}) if isinstance(projeto.get("base_projeto"), Mapping) else {}
    campos_base = {
        "referencias_desenho": "referências de desenhos e documentos",
        "base_carregamentos": "base dos carregamentos",
        "condicoes_operacao": "condições de operação e projeto",
        "criterio_aceitacao": "critérios de aceitação",
        "limitacoes": "limitações e exclusões de escopo",
    }
    for campo, rotulo in campos_base.items():
        pontos_totais += 1
        if _texto(base.get(campo)):
            preenchidos += 1
        else:
            adicionar(
                "Pendência",
                "Base de projeto",
                f"Sem {rotulo}",
                "A premissa ainda não está documentada na base de projeto.",
                f"Registre {rotulo}, incluindo origem, revisão e unidade quando aplicável.",
            )

    componentes = [item for item in projeto.get("componentes", []) if isinstance(item, Mapping)]
    pontos_totais += 1
    if componentes:
        preenchidos += 1
    else:
        adicionar(
            "Bloqueio",
            "Escopo físico",
            "Nenhum equipamento ou componente cadastrado",
            "Não há uma lista de itens industriais vinculada ao projeto.",
            "Cadastre ao menos o equipamento, linha, estrutura ou ponto de verificação principal.",
        )
    for indice, item in enumerate(componentes, start=1):
        identificacao = _texto(item.get("tag")) or _texto(item.get("descricao")) or f"item {indice}"
        for campo, rotulo in (("tag", "TAG"), ("descricao", "descrição"), ("material", "material")):
            pontos_totais += 1
            if _texto(item.get(campo)):
                preenchidos += 1
            else:
                adicionar(
                    "Pendência",
                    "Escopo físico",
                    f"{identificacao}: {rotulo} ausente",
                    "O cadastro do item não contém informação suficiente para rastreá-lo.",
                    f"Complete o campo {rotulo} do item {identificacao}.",
                )
        if _texto(item.get("material")) and not _texto(item.get("fonte_material")):
            adicionar(
                "Atenção",
                "Materiais",
                f"{identificacao}: propriedade sem fonte",
                "Há material informado, mas não foi registrada a norma, certificado ou especificação de origem.",
                "Inclua a fonte do material e confirme se os valores representam a condição real de fornecimento.",
            )

    materiais = [item for item in projeto.get("materiais_projeto", []) if isinstance(item, Mapping)]
    pontos_totais += 1
    if materiais:
        preenchidos += 1
    elif any(_texto(item.get("material")) for item in componentes):
        adicionar(
            "Atenção",
            "Materiais",
            "Materiais do escopo não foram qualificados",
            "Há designações nos componentes, mas a biblioteca do projeto não contém origem, condição e propriedades rastreadas.",
            "Cadastre os materiais em Materiais técnicos e vincule-os aos itens do escopo.",
        )
    ids_materiais = {_texto(item.get("id")) for item in materiais}
    for material in materiais:
        avaliacao = avaliar_material(material)
        pontos_totais += 1
        if avaliacao["nivel"] in {"Confirmado", "Rastreável"}:
            preenchidos += 1
        vinculacoes = [str(item) for item in material.get("vinculacoes", []) if str(item).strip()]
        if avaliacao["nivel"] == "Referência" and vinculacoes:
            adicionar(
                "Bloqueio",
                "Materiais",
                f"{_texto(material.get('nome'))}: dado orientativo vinculado ao escopo",
                f"O material está classificado como Referência ({avaliacao['indice_rastreabilidade']}% de rastreabilidade) e alimenta {len(vinculacoes)} item(ns).",
                "Substitua valores típicos por fonte controlada aplicável ou documente formalmente a disposição técnica.",
                evidencia="; ".join(avaliacao["pendencias"][:3]),
            )
        elif avaliacao["nivel"] == "Condicional":
            adicionar(
                "Atenção",
                "Materiais",
                f"{_texto(material.get('nome'))}: confiança condicional",
                f"Índice de rastreabilidade = {avaliacao['indice_rastreabilidade']}%.",
                "Complete a proveniência, a aplicabilidade e a conferência antes da emissão final.",
                evidencia="; ".join(avaliacao["pendencias"][:3]),
            )
    for componente in componentes:
        material_id = _texto(componente.get("material_id"))
        if material_id and material_id not in ids_materiais:
            adicionar(
                "Bloqueio",
                "Materiais",
                f"{_texto(componente.get('tag')) or _texto(componente.get('descricao'))}: vínculo de material inválido",
                "O componente aponta para um cadastro que não existe mais na biblioteca do projeto.",
                "Refaça o vínculo em Materiais técnicos e confira a fonte registrada.",
            )

    normas = [item for item in projeto.get("normas", []) if isinstance(item, Mapping)]
    pontos_totais += 1
    if normas:
        preenchidos += 1
    else:
        adicionar(
            "Bloqueio",
            "Normas",
            "Matriz normativa vazia",
            "O projeto não possui normas, especificações ou procedimentos vinculados.",
            "Cadastre as referências aplicáveis e confirme edição, escopo e origem do documento.",
        )
    for indice, item in enumerate(normas, start=1):
        codigo = _texto(item.get("codigo")) or f"referência {indice}"
        pontos_totais += 2
        if _texto(item.get("codigo")):
            preenchidos += 1
        else:
            adicionar(
                "Pendência", "Normas", "Referência sem código", "Uma linha da matriz normativa não possui identificação.",
                "Informe o código da norma, procedimento, desenho ou especificação."
            )
        if _texto(item.get("edicao")):
            preenchidos += 1
        else:
            adicionar(
                "Atenção", "Normas", f"{codigo}: edição não informada", "A revisão/edição aplicável não está rastreada.",
                "Confira o PDF controlado e registre a edição ou revisão aplicável."
            )
        if not bool(item.get("conferida", False)):
            adicionar(
                "Pendência",
                "Normas",
                f"{codigo}: conteúdo ainda não conferido",
                "A referência foi cadastrada, mas não foi marcada como conferida no documento-fonte.",
                "Abra o PDF da norma, valide edição e cláusulas aplicáveis e marque a conferência.",
            )

    registros = [item for item in projeto.get("registros_tecnicos", []) if isinstance(item, Mapping)]
    pontos_totais += 1
    if registros:
        preenchidos += 1
    else:
        adicionar(
            "Bloqueio",
            "Cálculos",
            "Nenhum registro técnico vinculado",
            "O projeto ainda não recebeu resultados dos módulos de cálculo nem verificações manuais.",
            "Execute uma análise e use 'Registrar no projeto ativo', ou crie um registro manual.",
        )

    for indice, registro in enumerate(registros, start=1):
        modulo = _texto(registro.get("modulo")) or "Registro técnico"
        titulo = _texto(registro.get("titulo")) or f"Registro {indice}"
        status = _texto(registro.get("status")).lower()
        entradas = registro.get("entradas", {}) if isinstance(registro.get("entradas"), Mapping) else {}
        resultados = registro.get("resultados", {}) if isinstance(registro.get("resultados"), Mapping) else {}
        premissas = registro.get("premissas", [])
        referencias = registro.get("referencias", [])
        conclusao = _texto(registro.get("conclusao"))
        for valor, rotulo in (
            (entradas, "entradas"),
            (resultados, "resultados"),
            (premissas, "premissas"),
            (referencias, "referências"),
            (conclusao, "conclusão"),
        ):
            pontos_totais += 1
            if valor:
                preenchidos += 1
            else:
                adicionar(
                    "Pendência",
                    "Registros técnicos",
                    f"{titulo}: sem {rotulo}",
                    f"O registro do módulo {modulo} não documenta {rotulo}.",
                    f"Complete {rotulo} antes de usar este registro no memorial final.",
                    modulo=modulo,
                )

        if any(chave in status for chave in ("não atende", "nao atende", "reprovado")):
            adicionar(
                "Bloqueio", "Resultado técnico", f"{titulo}: resultado não atende", conclusao or "O registro foi marcado como não atendido.",
                "Revise dados, premissas e solução de engenharia; não emita como aprovado sem tratamento.", modulo=modulo,
            )
        elif any(chave in status for chave in ("pendente", "inconclusivo", "atenção", "atencao")):
            adicionar(
                "Pendência", "Resultado técnico", f"{titulo}: resultado pendente", conclusao or "O registro não possui conclusão definitiva.",
                "Resolva a pendência técnica e atualize o status do registro.", modulo=modulo,
            )

        alertas = registro.get("alertas", [])
        if isinstance(alertas, Sequence) and not isinstance(alertas, (str, bytes)):
            for alerta in alertas:
                if _texto(alerta):
                    adicionar(
                        "Atenção", "Resultado técnico", f"{titulo}: alerta do cálculo", _texto(alerta),
                        "Avalie o alerta e registre a decisão técnica no projeto.", modulo=modulo,
                    )

        fator = _procurar_numero(resultados, ("fator_seguranca", "fator de segurança", "fator_governante", "n_min"))
        meta = _procurar_numero(resultados, ("fator_seguranca_minimo", "fator mínimo", "meta_fs", "n_requerido"))
        utilizacao = _procurar_numero(resultados, ("utilizacao_maxima", "utilização máxima", "indice_utilizacao", "índice de utilização"))
        if fator is not None and meta is not None and fator < meta:
            adicionar(
                "Bloqueio", "Critério numérico", f"{titulo}: fator abaixo da meta", f"Fator registrado = {fator:g}; mínimo requerido = {meta:g}.",
                "Revise o dimensionamento e documente a disposição da não conformidade.", modulo=modulo,
                evidencia=f"{fator:g} < {meta:g}",
            )
        if utilizacao is not None and utilizacao > 1.0:
            adicionar(
                "Bloqueio", "Critério numérico", f"{titulo}: utilização superior a 100%", f"Índice de utilização registrado = {utilizacao:.3f}.",
                "Redimensione ou justifique o critério antes de liberar o projeto.", modulo=modulo,
                evidencia=f"utilização = {utilizacao:.3f}",
            )
        probabilidade = _procurar_numero(
            resultados,
            ("probabilidade_nao_atendimento_pct", "probabilidade de não atendimento", "risco_nao_atendimento_pct"),
        )
        if "sensibilidade" in modulo.casefold() and probabilidade is not None and probabilidade > 5.0:
            adicionar(
                "Atenção" if probabilidade <= 20.0 else "Bloqueio",
                "Sensibilidade e incerteza",
                f"{titulo}: risco probabilístico relevante",
                f"Probabilidade registrada de não atendimento = {probabilidade:.2f}%.",
                "Revise margens, distribuições, correlações e valores governantes; documente a decisão de engenharia.",
                modulo=modulo,
                evidencia=f"P(não atendimento) = {probabilidade:.2f}%",
            )

    checklist = [item for item in projeto.get("checklist", []) if isinstance(item, Mapping)]
    for indice, item in enumerate(checklist, start=1):
        pontos_totais += 1
        estado = _texto(item.get("estado")) or "Aberto"
        titulo = _texto(item.get("item")) or f"Item {indice}"
        concluido = estado.lower() in {"concluído", "concluido", "fechado", "não aplicável", "nao aplicavel"}
        if concluido:
            preenchidos += 1
        else:
            adicionar(
                "Bloqueio" if bool(item.get("critico", False)) else "Pendência",
                "Checklist",
                f"Checklist aberto: {titulo}",
                f"Estado atual: {estado}. Responsável: {_texto(item.get('responsavel')) or 'não definido'}.",
                "Conclua, registre evidência ou classifique formalmente como não aplicável.",
            )

    # Extensões independentes podem acrescentar regras sem aumentar este
    # orquestrador central. A versão da regra segue na evidência do achado.
    for regra, resultado_regra in executar_regras(projeto):
        preenchidos += resultado_regra.pontos_preenchidos
        pontos_totais += resultado_regra.pontos_totais
        for achado_regra in resultado_regra.achados:
            evidencia = achado_regra.evidencia
            identificacao_regra = f"Regra {regra.id} v{regra.versao}"
            evidencia = f"{identificacao_regra}; {evidencia}" if evidencia else identificacao_regra
            adicionar(
                achado_regra.severidade,
                achado_regra.categoria,
                achado_regra.titulo,
                achado_regra.detalhe,
                achado_regra.recomendacao,
                modulo=achado_regra.modulo,
                evidencia=evidencia,
            )

    achados.sort(key=lambda item: (ORDEM_SEVERIDADE.get(item.severidade, 99), item.categoria, item.titulo))
    contagens = {severidade: sum(item.severidade == severidade for item in achados) for severidade in SEVERIDADES}
    indice = round(100.0 * preenchidos / max(pontos_totais, 1))
    if contagens["Bloqueio"]:
        prontidao = "Não pronto para emissão"
    elif contagens["Pendência"]:
        prontidao = "Em consolidação"
    elif contagens["Atenção"]:
        prontidao = "Pronto com ressalvas"
    else:
        prontidao = "Pronto para revisão"

    return {
        "prontidao": prontidao,
        "indice_documental": indice,
        "contagens": contagens,
        "total_achados": len(achados),
        "pontos_preenchidos": preenchidos,
        "pontos_totais": pontos_totais,
        "achados": [item.como_dict() for item in achados],
        "aviso": (
            "O índice mede preenchimento e rastreabilidade no aplicativo. "
            "Não representa certificação, conformidade normativa ou aprovação de engenharia."
        ),
    }
