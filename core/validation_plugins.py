"""Regras plugáveis consumidas pela Central de Validação."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core.load_cases import CHAVES_CARGA, calcular_envelope
from core.project_checklist import (
    SITUACAO_HOJE,
    SITUACAO_ILEGIVEL,
    SITUACAO_PROXIMO,
    SITUACAO_VENCIDO,
    resumo_checklist,
)
from core.project_criteria import avaliar_criterios_projeto, normalizar_criterios_projeto
from core.project_dependencies import (
    STATUS_ATUAL,
    STATUS_AUSENTE,
    STATUS_CICLO,
    STATUS_DESATUALIZADO,
    STATUS_SEM_DEPENDENCIAS,
    sincronizar_estados_dependencias,
)
from core.technical_records import avaliar_contrato_registro, registro_superado


@dataclass(frozen=True, slots=True)
class AchadoRegra:
    severidade: str
    categoria: str
    titulo: str
    detalhe: str
    recomendacao: str
    modulo: str = "Projeto"
    evidencia: str = ""


@dataclass(frozen=True, slots=True)
class ResultadoRegra:
    achados: tuple[AchadoRegra, ...] = ()
    pontos_preenchidos: int = 0
    pontos_totais: int = 0


ExecutorRegra = Callable[[Mapping[str, Any]], ResultadoRegra]


@dataclass(frozen=True, slots=True)
class RegraValidacao:
    id: str
    titulo: str
    versao: str
    executar: ExecutorRegra


_REGRAS: dict[str, RegraValidacao] = {}


def registrar_regra(regra: RegraValidacao, *, substituir: bool = False) -> None:
    chave = regra.id.strip().casefold()
    if chave in _REGRAS and not substituir:
        raise ValueError(f"Regra de validação já registrada: {regra.id}.")
    _REGRAS[chave] = regra


def listar_regras() -> list[RegraValidacao]:
    return sorted(_REGRAS.values(), key=lambda item: item.id)


def executar_regras(projeto: Mapping[str, Any]) -> list[tuple[RegraValidacao, ResultadoRegra]]:
    return [(regra, regra.executar(projeto)) for regra in listar_regras()]


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def _vetor_nao_nulo(vetor: Mapping[str, Any]) -> bool:
    for chave in CHAVES_CARGA:
        try:
            valor = float(vetor.get(chave, 0) or 0)
        except (TypeError, ValueError):
            return False
        if abs(valor) > 1e-12:
            return True
    return False


def _regra_contratos(projeto: Mapping[str, Any]) -> ResultadoRegra:
    achados: list[AchadoRegra] = []
    registros = [
        item
        for item in projeto.get("registros_tecnicos", [])
        if isinstance(item, Mapping)
    ]
    for indice, registro in enumerate(registros, start=1):
        avaliacao = avaliar_contrato_registro(registro)
        titulo = _texto(registro.get("titulo")) or f"Registro {indice}"
        modulo = _texto(registro.get("modulo")) or "Registro técnico"
        if avaliacao["assinatura_presente"] and not avaliacao["assinatura_valida"]:
            achados.append(
                AchadoRegra(
                    "Bloqueio",
                    "Integridade do cálculo",
                    f"{titulo}: assinatura do cálculo divergente",
                    "Entradas, resultados ou critérios diferem do conteúdo que originou o hash armazenado.",
                    "Regere o registro pelo módulo de origem ou documente uma nova revisão controlada.",
                    modulo=modulo,
                    evidencia=_texto(registro.get("hash_calculo")),
                )
            )
        elif not avaliacao["assinatura_presente"]:
            achados.append(
                AchadoRegra(
                    "Informação",
                    "Contrato técnico",
                    f"{titulo}: registro anterior ao contrato versionado",
                    "O conteúdo permanece legível, mas não possui assinatura técnica do esquema v2.",
                    "Ao revisar este cálculo, registre-o novamente pelo módulo correspondente.",
                    modulo=modulo,
                )
            )
        if avaliacao["faltantes"] and registro.get("schema_registro"):
            achados.append(
                AchadoRegra(
                    "Pendência",
                    "Contrato técnico",
                    f"{titulo}: contrato incompleto",
                    "Campos ausentes: " + ", ".join(avaliacao["faltantes"]) + ".",
                    "Complete o registro pelo módulo de origem antes da emissão.",
                    modulo=modulo,
                )
            )
    return ResultadoRegra(achados=tuple(achados))


def _regra_casos_carga(projeto: Mapping[str, Any]) -> ResultadoRegra:
    achados: list[AchadoRegra] = []
    casos = [item for item in projeto.get("casos_carga", []) if isinstance(item, Mapping)]
    combinacoes = [
        item
        for item in projeto.get("combinacoes_carga", [])
        if isinstance(item, Mapping)
    ]
    if not casos:
        return ResultadoRegra(
            achados=(
                AchadoRegra(
                    "Informação",
                    "Carregamentos",
                    "Casos de carga ainda não estruturados",
                    "A base de carregamentos pode existir em texto, mas não há cenários vetoriais permanentes.",
                    "Use Casos e combinações de carga quando o projeto exigir envelope e rastreabilidade por cenário.",
                    modulo="Casos de carga",
                ),
            )
        )

    preenchidos = 0
    total = 0
    ids = {str(item.get("id")) for item in casos if _texto(item.get("id"))}
    ativos = 0
    for indice, caso in enumerate(casos, start=1):
        nome = _texto(caso.get("codigo")) or _texto(caso.get("nome")) or f"Caso {indice}"
        vetor = caso.get("cargas") if isinstance(caso.get("cargas"), Mapping) else {}
        if bool(caso.get("ativo", True)):
            ativos += 1
        for valor, rotulo in (
            (_texto(caso.get("nome")), "nome"),
            (_texto(caso.get("tag")), "TAG"),
            (_texto(caso.get("origem")) or _texto(caso.get("referencia")), "origem ou referência"),
            (_vetor_nao_nulo(vetor), "vetor não nulo"),
        ):
            total += 1
            if valor:
                preenchidos += 1
            else:
                severidade = "Bloqueio" if rotulo == "vetor não nulo" else "Pendência"
                achados.append(
                    AchadoRegra(
                        severidade,
                        "Carregamentos",
                        f"{nome}: {rotulo} ausente",
                        "O caso não possui informação suficiente para uso rastreável no envelope.",
                        f"Complete {rotulo} na Central de casos de carga.",
                        modulo="Casos de carga",
                    )
                )

    if ativos >= 2 and not combinacoes:
        achados.append(
            AchadoRegra(
                "Pendência",
                "Carregamentos",
                "Casos ativos sem combinações cadastradas",
                f"Há {ativos} casos ativos, mas o envelope considera somente casos isolados.",
                "Cadastre combinações e confirme os fatores na base normativa do projeto.",
                modulo="Casos de carga",
            )
        )
    for combinacao in combinacoes:
        fatores = combinacao.get("fatores") if isinstance(combinacao.get("fatores"), Mapping) else {}
        ausentes = sorted(str(caso_id) for caso_id in fatores if str(caso_id) not in ids)
        if ausentes:
            achados.append(
                AchadoRegra(
                    "Bloqueio",
                    "Carregamentos",
                    f"{_texto(combinacao.get('nome')) or 'Combinação'}: referência inválida",
                    "Casos inexistentes: " + ", ".join(ausentes) + ".",
                    "Edite ou recrie a combinação antes de emitir o memorial.",
                    modulo="Casos de carga",
                )
            )
    try:
        calcular_envelope(casos, combinacoes, incluir_casos_isolados=not bool(combinacoes))
    except (TypeError, ValueError) as erro:
        achados.append(
            AchadoRegra(
                "Bloqueio",
                "Carregamentos",
                "Envelope de cargas inconsistente",
                str(erro),
                "Revise fatores, referências e valores numéricos dos casos.",
                modulo="Casos de carga",
            )
        )
    return ResultadoRegra(tuple(achados), preenchidos, total)


_SEVERIDADE_POR_STATUS = {
    STATUS_DESATUALIZADO: "Atenção",
    STATUS_AUSENTE: "Bloqueio",
    STATUS_CICLO: "Bloqueio",
}


def _regra_dependencias(projeto: Mapping[str, Any]) -> ResultadoRegra:
    """Sinaliza cálculos cujas fontes (material, caso de carga, critério ou
    outro registro) mudaram desde que o resultado foi salvo.

    A reavaliação é sempre feita sobre o projeto atual, nunca sobre um
    instantâneo persistido — por isso o achado desaparece assim que o
    cálculo apontado é refeito, sem exigir uma sincronização manual.
    """
    achados: list[AchadoRegra] = []
    sincronizado = sincronizar_estados_dependencias(projeto)
    registros = [
        item
        for item in sincronizado.get("registros_tecnicos", [])
        if isinstance(item, Mapping)
    ]
    preenchidos = 0
    total = 0
    for indice, registro in enumerate(registros, start=1):
        if registro_superado(registro):
            continue
        estado = (
            registro.get("estado_dependencias", {})
            if isinstance(registro.get("estado_dependencias"), Mapping)
            else {}
        )
        status = _texto(estado.get("status")) or STATUS_SEM_DEPENDENCIAS
        if status == STATUS_SEM_DEPENDENCIAS:
            continue
        total += 1
        if status == STATUS_ATUAL:
            preenchidos += 1
            continue
        titulo = _texto(registro.get("titulo")) or f"Registro {indice}"
        modulo = _texto(registro.get("modulo")) or "Registro técnico"
        motivos_brutos = estado.get("motivos", [])
        motivos = (
            [str(motivo) for motivo in motivos_brutos]
            if isinstance(motivos_brutos, Sequence) and not isinstance(motivos_brutos, (str, bytes))
            else []
        )
        detalhe = " ".join(motivos) or f"Estado das dependências: {status}."
        achados.append(
            AchadoRegra(
                _SEVERIDADE_POR_STATUS.get(status, "Atenção"),
                "Rastreabilidade de cálculo",
                f"{titulo}: {status.lower()}",
                detalhe,
                f"Reabra o módulo {modulo} e refaça este cálculo com os dados atuais do projeto.",
                modulo=modulo,
                evidencia="; ".join(motivos[:3]),
            )
        )
    return ResultadoRegra(tuple(achados), preenchidos, total)


# ---------------------------------------------------------------------------
# Regras que olham o resultado de engenharia, não só a documentação
# ---------------------------------------------------------------------------

# Chaves de fator de segurança usadas pelos módulos. O nome varia porque cada
# verificação tem o seu critério; o que importa é comparar com a meta.
_CHAVES_FATOR = (
    "fator_seguranca",
    "fator_seguranca_escoamento",
    "fator_seguranca_ruptura",
    "fator_ruptura",
    "fator_seguranca_minimo_calculado",
    "menor_fator",
)

_STATUS_REPROVADO = {"não atende", "nao atende", "reprovado"}
_STATUS_ATENCAO = {"atenção", "atencao"}


def _float_ou_none(valor: Any) -> float | None:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def _meta_do_projeto(projeto: Mapping[str, Any]) -> float:
    criterios = normalizar_criterios_projeto(projeto.get("criterios_projeto"))
    meta = _float_ou_none(criterios["seguranca"]["fator_seguranca_minimo"])
    return meta if meta and meta > 0 else 1.5


def _utilizacao_maxima(projeto: Mapping[str, Any]) -> float:
    criterios = normalizar_criterios_projeto(projeto.get("criterios_projeto"))
    limite = _float_ou_none(criterios["seguranca"]["utilizacao_maxima"])
    return limite if limite and limite > 0 else 1.0


def _regra_margens_calculadas(projeto: Mapping[str, Any]) -> ResultadoRegra:
    """Confronta o que os módulos calcularam com a meta do próprio projeto.

    As demais regras verificam se o cálculo está documentado e atualizado.
    Esta verifica se ele **passa** — sem isso, um projeto pode chegar
    completo, assinado e coerente à emissão carregando um fator de segurança
    abaixo do critério que o próprio projeto declarou.
    """
    achados: list[AchadoRegra] = []
    registros = [
        item
        for item in projeto.get("registros_tecnicos", [])
        if isinstance(item, Mapping)
    ]
    meta = _meta_do_projeto(projeto)
    limite_utilizacao = _utilizacao_maxima(projeto)
    avaliados = 0
    dentro_do_criterio = 0

    for indice, registro in enumerate(registros, start=1):
        if registro_superado(registro):
            continue
        titulo = _texto(registro.get("titulo")) or f"Registro {indice}"
        modulo = _texto(registro.get("modulo")) or "Registro técnico"
        resultados = registro.get("resultados")
        resultados = resultados if isinstance(resultados, Mapping) else {}

        # A meta gravada no próprio registro tem prioridade: é a que valia
        # quando o cálculo foi feito, e é a que o memorial reproduz.
        meta_registro = _float_ou_none(resultados.get("fator_seguranca_minimo")) or meta

        fatores = {
            chave: _float_ou_none(resultados.get(chave))
            for chave in _CHAVES_FATOR
            if _float_ou_none(resultados.get(chave)) is not None
        }
        if fatores:
            avaliados += 1
            criterio, menor = min(fatores.items(), key=lambda item: item[1])
            if menor < 1.0:
                achados.append(
                    AchadoRegra(
                        "Bloqueio",
                        "Margem de segurança",
                        f"{titulo}: resistência excedida",
                        f"O menor fator calculado é {menor:.2f} ({criterio}), abaixo de 1,00.",
                        "Revise geometria, material ou carregamento antes de emitir o memorial.",
                        modulo=modulo,
                        evidencia=f"{criterio} = {menor:.3f}",
                    )
                )
            elif menor < meta_registro:
                achados.append(
                    AchadoRegra(
                        "Atenção",
                        "Margem de segurança",
                        f"{titulo}: abaixo da meta do projeto",
                        f"O menor fator calculado é {menor:.2f} ({criterio}), "
                        f"abaixo da meta n ≥ {meta_registro:.2f} declarada nos critérios.",
                        "Aumente a margem ou registre a justificativa técnica da exceção.",
                        modulo=modulo,
                        evidencia=f"{criterio} = {menor:.3f} · meta = {meta_registro:.2f}",
                    )
                )
            else:
                dentro_do_criterio += 1

        utilizacao = _float_ou_none(resultados.get("utilizacao"))
        if utilizacao is None:
            utilizacao = _float_ou_none(resultados.get("utilizacao_maxima"))
        if utilizacao is not None and utilizacao > limite_utilizacao:
            achados.append(
                AchadoRegra(
                    "Bloqueio",
                    "Margem de segurança",
                    f"{titulo}: utilização acima do limite",
                    f"Utilização de {utilizacao * 100:.0f}%, acima do limite de "
                    f"{limite_utilizacao * 100:.0f}% dos critérios do projeto.",
                    "Reforce o componente ou reveja o critério de utilização.",
                    modulo=modulo,
                    evidencia=f"utilização = {utilizacao:.3f}",
                )
            )

        status = _texto(registro.get("status")).casefold()
        if status in _STATUS_REPROVADO:
            achados.append(
                AchadoRegra(
                    "Bloqueio",
                    "Margem de segurança",
                    f"{titulo}: registrado como não atendido",
                    "O próprio módulo concluiu que a verificação não é atendida.",
                    "Trate a não conformidade ou remova o registro superado do escopo.",
                    modulo=modulo,
                )
            )
        elif status in _STATUS_ATENCAO:
            achados.append(
                AchadoRegra(
                    "Atenção",
                    "Margem de segurança",
                    f"{titulo}: registrado com ressalva",
                    "O módulo concluiu a verificação com margem pequena.",
                    "Confirme se a ressalva é aceitável para o critério de aceitação do projeto.",
                    modulo=modulo,
                )
            )

    return ResultadoRegra(
        achados=tuple(achados),
        pontos_preenchidos=dentro_do_criterio,
        pontos_totais=avaliados,
    )


def _regra_deslocamentos(projeto: Mapping[str, Any]) -> ResultadoRegra:
    """Serviço (flecha) é verificação separada da resistência.

    Uma barra pode atender folgadamente à tensão e ainda assim ser inviável
    por deslocamento. Como o critério de flecha não está nos critérios do
    projeto, a regra só confronta o que o próprio módulo registrou.
    """
    achados: list[AchadoRegra] = []
    for indice, registro in enumerate(
        [i for i in projeto.get("registros_tecnicos", []) if isinstance(i, Mapping)],
        start=1,
    ):
        if registro_superado(registro):
            continue
        resultados = registro.get("resultados")
        resultados = resultados if isinstance(resultados, Mapping) else {}
        flecha = _float_ou_none(resultados.get("flecha_maxima_mm"))
        admissivel = _float_ou_none(resultados.get("flecha_admissivel_mm"))
        if flecha is None or admissivel is None or admissivel <= 0:
            continue
        if abs(flecha) > admissivel:
            titulo = _texto(registro.get("titulo")) or f"Registro {indice}"
            achados.append(
                AchadoRegra(
                    "Atenção",
                    "Estado limite de serviço",
                    f"{titulo}: flecha acima do critério",
                    f"Flecha máxima de {abs(flecha):.2f} mm contra "
                    f"{admissivel:.2f} mm admissíveis "
                    f"({_texto(resultados.get('criterio_flecha')) or 'critério informado'}).",
                    "Aumente a inércia, reduza o vão ou registre a aceitação do deslocamento.",
                    modulo=_texto(registro.get("modulo")) or "Registro técnico",
                    evidencia=f"flecha = {abs(flecha):.3f} mm",
                )
            )
    return ResultadoRegra(achados=tuple(achados))


# ---------------------------------------------------------------------------
# Regras de gestão: prazos, critérios e documentos de entrada
# ---------------------------------------------------------------------------


def _regra_prazos_checklist(projeto: Mapping[str, Any]) -> ResultadoRegra:
    """Um item aberto com prazo vencido é mais que "aberto".

    A regra geral já cobra todo item em aberto; esta acrescenta a dimensão
    de tempo, que antes o programa não lia: vencido vira Atenção, a vencer
    na semana vira Informação, e um prazo que não dá para interpretar
    ("após a parada") é apontado para virar data.
    """
    achados: list[AchadoRegra] = []
    resumo = resumo_checklist(projeto.get("checklist", []))
    for linha in resumo["itens_abertos"]:
        responsavel = linha["responsavel"] or "sem responsável"
        if linha["situacao"] == SITUACAO_VENCIDO:
            achados.append(
                AchadoRegra(
                    "Atenção",
                    "Prazos",
                    f"Prazo vencido: {linha['item']}",
                    f"Venceu em {linha['prazo_texto']} ({abs(linha['dias'])} dia(s) atrás); "
                    f"responsável: {responsavel}; estado: {linha['estado']}.",
                    "Conclua o item, registre a evidência ou renegocie o prazo com o responsável.",
                    modulo="Checklist",
                    evidencia=f"{linha['dias']} dia(s)" + (" · crítico" if linha["critico"] else ""),
                )
            )
        elif linha["situacao"] in {SITUACAO_HOJE, SITUACAO_PROXIMO}:
            achados.append(
                AchadoRegra(
                    "Informação",
                    "Prazos",
                    f"Vence em breve: {linha['item']}",
                    f"Prazo em {linha['prazo_texto']} ({linha['dias']} dia(s)); responsável: {responsavel}.",
                    "Confirme com o responsável se o prazo será cumprido.",
                    modulo="Checklist",
                )
            )
        elif linha["situacao"] == SITUACAO_ILEGIVEL:
            achados.append(
                AchadoRegra(
                    "Informação",
                    "Prazos",
                    f"Prazo não interpretável: {linha['item']}",
                    f"O prazo '{linha['prazo_texto']}' não é uma data; o programa não consegue avisar quando vencer.",
                    "Registre o prazo como data (dd/mm/aaaa) no checklist.",
                    modulo="Checklist",
                )
            )
    return ResultadoRegra(achados=tuple(achados))


def _regra_criterios_projeto(projeto: Mapping[str, Any]) -> ResultadoRegra:
    """Critérios técnicos: sem eles, a validação usa o padrão do programa.

    Não é bloqueio nem pendência — um projeto pode legitimamente aceitar
    n ≥ 1,5 e utilização ≤ 1,0 — mas a pessoa precisa saber que os limites
    contra os quais os cálculos estão sendo cobrados não foram escolhidos
    por ela.
    """
    criterios = projeto.get("criterios_projeto")
    if not isinstance(criterios, Mapping):
        return ResultadoRegra(
            achados=(
                AchadoRegra(
                    "Informação",
                    "Critérios do projeto",
                    "Critérios técnicos ainda não definidos",
                    "As metas de fator de segurança, utilização e risco usadas pela validação "
                    "são o padrão do programa (n ≥ 1,5; utilização ≤ 1,0; risco ≤ 5%).",
                    "Defina os critérios em Gestão de projetos > Critérios para que os limites sejam os do projeto.",
                    modulo="Critérios",
                ),
            )
        )
    avaliacao = avaliar_criterios_projeto(criterios)
    achados: list[AchadoRegra] = []
    if avaliacao["faltantes"]:
        achados.append(
            AchadoRegra(
                "Atenção",
                "Critérios do projeto",
                "Critérios técnicos incompletos",
                "Faltam: " + "; ".join(avaliacao["faltantes"]) + ".",
                "Complete a base normativa e a referência dos fatores em Gestão de projetos > Critérios.",
                modulo="Critérios",
            )
        )
    for alerta in avaliacao["alertas"]:
        achados.append(
            AchadoRegra(
                "Informação",
                "Critérios do projeto",
                alerta,
                "Os critérios do projeto foram definidos, mas este ponto ficou em aberto.",
                "Estruture o valor nos critérios ou registre por que não se aplica.",
                modulo="Critérios",
            )
        )
    total = 3
    preenchidos = total - min(len(avaliacao["faltantes"]), total)
    return ResultadoRegra(tuple(achados), preenchidos, total)


_SITUACOES_DOCUMENTO_VIGENTE = frozenset({"vigente", "recebido", "aprovado"})
_SITUACOES_DOCUMENTO_AGUARDANDO = frozenset({"aguardando recebimento", "aguardando", "pendente"})
_SITUACOES_DOCUMENTO_SUPERADO = frozenset({"superado", "cancelado", "obsoleto"})


def _regra_documentos_entrada(projeto: Mapping[str, Any]) -> ResultadoRegra:
    """Documentos de entrada: o que o cálculo assume que recebeu.

    Um desenho "aguardando recebimento" citado por um componente significa
    que o escopo foi montado sobre um documento que ainda não existe; um
    desenho superado ainda citado significa que a peça aponta para uma
    revisão que já não vale.
    """
    achados: list[AchadoRegra] = []
    documentos = [item for item in projeto.get("anexos", []) if isinstance(item, Mapping)]
    if not documentos:
        return ResultadoRegra()
    componentes = [item for item in projeto.get("componentes", []) if isinstance(item, Mapping)]
    citados = " ".join(_texto(item.get("desenho")).casefold() for item in componentes)
    preenchidos = 0
    total = 0
    for indice, documento in enumerate(documentos, start=1):
        codigo = _texto(documento.get("codigo")) or _texto(documento.get("titulo")) or f"documento {indice}"
        situacao = _texto(documento.get("situacao")).casefold()
        total += 1
        completo = bool(_texto(documento.get("codigo")) and _texto(documento.get("revisao")))
        if completo and situacao in _SITUACOES_DOCUMENTO_VIGENTE:
            preenchidos += 1
        if not _texto(documento.get("revisao")):
            achados.append(
                AchadoRegra(
                    "Atenção",
                    "Documentos de entrada",
                    f"{codigo}: revisão não informada",
                    "Sem a revisão, não dá para saber contra qual emissão do documento o cálculo foi feito.",
                    "Informe a revisão do documento na aba Documentos.",
                    modulo="Documentos",
                )
            )
        citado = bool(_texto(documento.get("codigo"))) and _texto(documento.get("codigo")).casefold() in citados
        if situacao in _SITUACOES_DOCUMENTO_AGUARDANDO:
            achados.append(
                AchadoRegra(
                    "Pendência",
                    "Documentos de entrada",
                    f"{codigo}: aguardando recebimento",
                    "O documento está previsto como entrada do projeto, mas ainda não foi recebido."
                    + (" Um componente do escopo já o cita." if citado else ""),
                    "Cobre o emitente ou registre a premissa adotada enquanto o documento não chega.",
                    modulo="Documentos",
                )
            )
        elif situacao in _SITUACOES_DOCUMENTO_SUPERADO and citado:
            achados.append(
                AchadoRegra(
                    "Atenção",
                    "Documentos de entrada",
                    f"{codigo}: documento superado ainda citado no escopo",
                    "Um componente do escopo físico aponta para um documento marcado como superado.",
                    "Atualize a referência do componente para a revisão vigente e confira o cálculo.",
                    modulo="Documentos",
                )
            )
    return ResultadoRegra(tuple(achados), preenchidos, total)


registrar_regra(RegraValidacao("contrato-registro", "Contrato dos registros técnicos", "1.0", _regra_contratos))
registrar_regra(RegraValidacao("casos-carga", "Casos e combinações de carga", "1.0", _regra_casos_carga))
registrar_regra(RegraValidacao("dependencias-calculo", "Atualidade dos cálculos dependentes", "1.0", _regra_dependencias))
registrar_regra(RegraValidacao("margens-calculadas", "Margens de segurança calculadas", "1.0", _regra_margens_calculadas))
registrar_regra(RegraValidacao("deslocamentos", "Deslocamentos em serviço", "1.0", _regra_deslocamentos))
registrar_regra(RegraValidacao("prazos-checklist", "Prazos do checklist", "1.0", _regra_prazos_checklist))
registrar_regra(RegraValidacao("criterios-projeto", "Critérios técnicos do projeto", "1.0", _regra_criterios_projeto))
registrar_regra(RegraValidacao("documentos-entrada", "Documentos de entrada", "1.0", _regra_documentos_entrada))
