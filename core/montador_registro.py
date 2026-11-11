"""Guardar uma montagem e ligar cálculos entre si.

Uma montagem salva vira um registro técnico do projeto: entra no memorial e na Central de validação
como qualquer outro cálculo, e leva junto o desenho, para reabrir depois. O arquivo JSON faz o mesmo
papel fora do projeto.

A referência é o caminho inverso. Um bloco aponta para o resultado de um registro pelo id e pela
assinatura do registro, e guarda o valor que usou. Se o registro mudar, some ou deixar de ter aquele
resultado, ``conferir_referencias`` diz. O vínculo também vai em ``dependencias_ids``: é ele que faz
a Central de validação marcar o cálculo como desatualizado.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core import montador as mt
from core import montador_blocos as mb
from core import montador_casos as mcs
from core import montador_grandezas as g
from core.montador_grandezas import Sistema, Unidades
from core.technical_records import STATUS_SUPERADO, criar_registro_tecnico

FORMATO = "mecanica-toolkit/montagem/v1"
AUSENTE = "ausente"
INCOMPATIVEL = "incompativel"
DESATUALIZADA = "desatualizada"
EM_DIA = "em_dia"
_REFERENCIAS_DA_PARTE = {
    mb.SOLIDOS: (
        "Budynas e Nisbett, Elementos de Máquinas de Shigley.",
        "Hibbeler, Resistência dos Materiais.",
    ),
    mb.FLUIDOS: ("White, Mecânica dos Fluidos.", "Çengel e Cimbala, Mecânica dos Fluidos."),
}


class ErroDeArquivo(ValueError):
    """O arquivo não é uma montagem que dê para abrir."""


def documento(
    dominio: str,
    grafo: Mapping[str, Any],
    valores: Mapping[str, float | None],
    origens: Mapping[str, str],
    alvo: str | None,
    adotado: float | None,
    unidades: Sequence[str],
    casos: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Tudo o que reabre a montagem como ela estava."""
    doc = {
        "formato": FORMATO,
        "dominio": dominio,
        "grafo": json.loads(json.dumps(grafo, ensure_ascii=False)),
        "valores": {k: v for k, v in valores.items() if v is not None},
        "origens": dict(origens),
        "alvo": alvo,
        "adotado": adotado,
        "unidades": list(unidades),
    }
    normalizados = mcs.normalizar(casos)
    if normalizados is not None and normalizados["lista"]:
        doc["casos"] = normalizados
    return doc


def assinatura(doc: Mapping[str, Any]) -> str:
    """Muda quando a conta muda: arrastar um bloco não conta como alteração."""

    def sem_posicao(dados: Mapping[str, Any]) -> dict[str, Any]:
        nos = []
        for no in dados.get("nos") or ():
            item = {k: v for k, v in no.items() if k not in ("x", "y")}
            if isinstance(item.get("grafo"), Mapping):
                item["grafo"] = sem_posicao(item["grafo"])
            nos.append(item)
        return {"nos": nos, "fios": dados.get("fios") or []}

    conteudo = {
        "grafo": sem_posicao(doc.get("grafo") or {}),
        "valores": doc.get("valores"),
        "alvo": doc.get("alvo"),
        "adotado": doc.get("adotado"),
    }
    if doc.get("casos"):
        conteudo["casos"] = doc["casos"]
    texto = json.dumps(conteudo, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def em_json(doc: Mapping[str, Any]) -> bytes:
    return json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")


def ler_documento(conteudo: bytes | str, dominio: str, sistema: Sistema) -> dict[str, Any]:
    """Confere o arquivo antes de abrir: o que veio de fora não entra sem olhar."""
    try:
        doc = json.loads(conteudo)
    except (ValueError, UnicodeDecodeError) as erro:
        raise ErroDeArquivo("Este arquivo não é um JSON válido.") from erro
    if not isinstance(doc, Mapping) or doc.get("formato") != FORMATO:
        raise ErroDeArquivo("Este arquivo não é uma montagem do programa.")
    if doc.get("dominio") != dominio:
        raise ErroDeArquivo("Esta montagem é da outra parte do Montador.")
    grafo = doc.get("grafo")
    if not isinstance(grafo, Mapping) or not isinstance(grafo.get("nos"), list):
        raise ErroDeArquivo("A montagem não tem blocos que dê para ler.")
    if not isinstance(grafo.get("fios"), list):
        raise ErroDeArquivo("A montagem não tem fios que dê para ler.")
    valores = {}
    for chave, valor in (doc.get("valores") or {}).items():
        if isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor):
            valores[str(chave)] = float(valor)
    unidades = list(doc.get("unidades") or ())
    certas = len(unidades) == len(sistema.seletores) and all(
        escolha in seletor.opcoes
        for escolha, seletor in zip(unidades, sistema.seletores, strict=True)
    )
    if not certas:
        unidades = [s.padrao for s in sistema.seletores]
    adotado = doc.get("adotado")
    return {
        "formato": FORMATO,
        "dominio": dominio,
        "grafo": dict(grafo),
        "valores": valores,
        "origens": {str(k): str(v) for k, v in (doc.get("origens") or {}).items()},
        "alvo": doc.get("alvo") if isinstance(doc.get("alvo"), str) else None,
        "adotado": (
            float(adotado)
            if isinstance(adotado, (int, float))
            and not isinstance(adotado, bool)
            and math.isfinite(adotado)
            and adotado > 0.0
            else None
        ),
        "unidades": unidades,
        "casos": mcs.normalizar(doc.get("casos")),
    }


def _formula_em_texto(expressao: Any) -> str:
    return str(expressao).replace("**", "^").replace("*", "·")


def _numero(valor: float) -> str:
    if 1e4 <= abs(valor) < 1e12:  # 200.000, e não 2e+05
        return f"{valor:,.0f}".replace(",", ".")
    return f"{valor:.4g}".replace(".", ",")


def texto_da_resposta(resposta: mt.Resposta, u: Unidades) -> str:
    """h ≥ 37,95 mm."""
    if resposta.valor is None:
        return f"{resposta.alvo.texto} sem número: faltam valores."
    rotulo = u.rotulo(resposta.alvo.dimensao)
    sinal = {mt.MINIMO: "≥", mt.MAXIMO: "≤"}.get(resposta.sentido or "", "=")
    numero = _numero(resposta.valor / u.fator(resposta.alvo.dimensao))
    return f"{resposta.alvo.texto} {sinal} {numero} {rotulo}".strip()


def saidas_publicas(
    dominio: str, resposta: mt.Resposta, valores: Mapping[str, float]
) -> list[dict[str, Any]]:
    """O que outro cálculo pode ler daqui, com a grandeza e o valor na base do sistema."""
    publicas: list[dict[str, Any]] = []
    if resposta.valor is not None:
        publicas.append(
            {
                "chave": resposta.alvo.chave,
                "rotulo": f"{resposta.alvo.texto}: {resposta.alvo.nome} (resposta)",
                "dimensao": resposta.alvo.dimensao,
                "valor": resposta.valor,
                "dominio": dominio,
            }
        )
    montagem = resposta.montagem
    if montagem is not None:
        for item in montagem.grandezas:
            valor = valores.get(item.chave)
            if valor is not None and item.chave != resposta.alvo.chave:
                publicas.append(
                    {
                        "chave": item.chave,
                        "rotulo": f"{item.texto}: {item.nome}",
                        "dimensao": item.dimensao,
                        "valor": valor,
                        "dominio": dominio,
                    }
                )
    return publicas


def _dimensao_da_letra(montagem: mt.Montagem, chave: str) -> str:
    grandeza = montagem.grandeza(chave)
    return grandeza.dimensao if grandeza is not None else ""


def _rotulo_da_letra(montagem: mt.Montagem, chave: str, u: Unidades) -> str:
    grandeza = montagem.grandeza(chave)
    if grandeza is None:
        return chave
    rotulo = u.rotulo(grandeza.dimensao)
    return f"{grandeza.texto} ({rotulo})" if rotulo else grandeza.texto


def registro_tecnico(
    *,
    modulo: str,
    modulo_id: str,
    dominio: str,
    titulo: str,
    resposta: mt.Resposta,
    montagem: mt.Montagem,
    doc: Mapping[str, Any],
    u: Unidades,
) -> dict[str, Any]:
    """O registro do projeto: as entradas na unidade da tela e o desenho para reabrir."""
    valores = resposta.valores_usados
    entradas: dict[str, Any] = {}
    for item in montagem.grandezas:
        valor = valores.get(item.chave)
        if valor is None:
            continue
        rotulo = u.rotulo(item.dimensao)
        titulo_campo = f"{item.texto} ({rotulo})" if rotulo else item.texto
        entradas[titulo_campo] = valor / u.fator(item.dimensao)
    resultados: dict[str, Any] = {}
    alvo = resposta.alvo
    rotulo_alvo = u.rotulo(alvo.dimensao)
    if resposta.valor is not None:
        chave = f"{alvo.texto} ({rotulo_alvo})" if rotulo_alvo else alvo.texto
        resultados[chave] = resposta.valor / u.fator(alvo.dimensao)
    conferidas = resposta.conferencia_adotada or resposta.conferencia
    medidas = [linha.uso for linha in conferidas if not linha.igualdade]
    if medidas:
        resultados["utilizacao"] = max(medidas)
    if resposta.manda is not None:
        resultados["condicao_que_manda"] = resposta.manda.condicao.nome
    if montagem.casos:
        resultados["caso_que_manda"] = (
            resposta.manda.condicao.caso if resposta.manda is not None else ""
        ) or montagem.caso_base
        entradas["casos_de_carga"] = {
            nome: {
                _rotulo_da_letra(montagem, chave, u): valor
                / u.fator(_dimensao_da_letra(montagem, chave))
                for chave, valor in proprios
                if montagem.grandeza(chave) is not None
            }
            for nome, proprios in montagem.casos
        }
    if resposta.adotado is not None:
        chave = f"{alvo.texto} adotado ({rotulo_alvo})" if rotulo_alvo else f"{alvo.texto} adotado"
        resultados[chave] = resposta.adotado / u.fator(alvo.dimensao)
    equacoes = [
        f"{alvo.texto} = {_formula_em_texto(i.formula.expressao)} ({i.condicao.nome})"
        for i in resposta.isoladas
        if i.formula is not None
    ]
    criterios = [f"{linha.nome}: uso de {_numero(linha.uso * 100.0)} %" for linha in conferidas]
    conclusao = texto_da_resposta(resposta, u)
    if resposta.manda is not None:
        conclusao += f", por {resposta.manda.condicao.nome}"
    registro = criar_registro_tecnico(
        modulo=modulo,
        modulo_id=modulo_id,
        titulo=titulo,
        status="Calculado",
        resumo=conclusao,
        entradas=entradas,
        resultados=resultados,
        premissas=montagem.hipoteses,
        metodo=(
            "Montador de fórmulas: cada critério roda nos pontos que importam, e a resposta vem da "
            "condição que manda. Pré-dimensionamento, que não substitui a verificação por norma."
        ),
        equacoes=equacoes,
        criterios=criterios,
        alertas=(*montagem.alertas, *resposta.alertas),
        referencias=_REFERENCIAS_DA_PARTE.get(dominio, ()),
        conclusao=f"{conclusao}.",
    )
    registro["montagem"] = dict(doc)
    registro["saidas_publicas"] = saidas_publicas(dominio, resposta, valores)
    ids = sorted(ids_referenciados(mt.grafo_de_dados(doc["grafo"])))
    if ids:
        registro["dependencias_ids"] = ids
    return registro


def montagens_do_projeto(projeto: Mapping[str, Any] | None, modulo_id: str) -> list[dict[str, Any]]:
    """As montagens salvas no projeto, da mais nova para a mais velha. Superada não aparece."""
    if not projeto:
        return []
    lista = [
        dict(r)
        for r in projeto.get("registros_tecnicos", [])
        if isinstance(r, Mapping)
        and r.get("modulo_id") == modulo_id
        and isinstance(r.get("montagem"), Mapping)
        and r.get("status") != STATUS_SUPERADO
    ]
    return sorted(lista, key=lambda r: str(r.get("criado_em")), reverse=True)


# ---------------------------------------------------------------------------
# Referências
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fonte:
    """Um resultado de outro cálculo do projeto que pode virar um bloco."""

    registro_id: str
    registro_titulo: str
    assinatura: str
    campo: str
    rotulo: str
    valor: float
    dimensao: str | None  # None: o registro não diz a grandeza, e quem escolhe é o usuário
    fator: float  # do número guardado para a base do sistema


def unidades_conhecidas(u: Unidades) -> dict[str, tuple[str, float]]:
    """Cada unidade do sistema: rótulo → (dimensão, fator para a base)."""
    tabela: dict[str, tuple[str, float]] = {}
    for seletor in u.sistema.seletores:
        for rotulo, fator in seletor.opcoes.items():
            tabela.setdefault(rotulo, (seletor.dimensao, fator))
    for dimensao, (rotulo, fator) in u.sistema.fixas.items():
        if rotulo:
            tabela.setdefault(rotulo, (dimensao, fator))
    return tabela


def _unidade_pelo_nome(campo: str) -> str:
    """Muitos registros trazem a unidade no fim do nome: sigma_x_MPa ou "Reação (kN)"."""
    limpo = campo.strip()
    if limpo.endswith(")") and "(" in limpo:
        return limpo[limpo.rindex("(") + 1 : -1]
    final = limpo.rsplit("_", 1)[-1]
    return {"kNm": "kN·m", "Nm": "N·m", "Nmm": "N·mm"}.get(final, final)


def fontes_do_projeto(projeto: Mapping[str, Any] | None, dominio: str, u: Unidades) -> list[Fonte]:
    """Só resultados com número: texto e situação não entram numa fórmula."""
    if not projeto:
        return []
    tabela = unidades_conhecidas(u)
    fontes: list[Fonte] = []
    for registro in projeto.get("registros_tecnicos", []):
        if not isinstance(registro, Mapping) or registro.get("status") == STATUS_SUPERADO:
            continue
        id_ = str(registro.get("id"))
        titulo = f"{registro.get('modulo')}: {registro.get('titulo')}"
        marca = str(registro.get("hash_calculo") or "")
        publicas = [s for s in registro.get("saidas_publicas") or () if s.get("dominio") == dominio]
        for saida in publicas:
            fontes.append(
                Fonte(
                    id_,
                    titulo,
                    marca,
                    str(saida["chave"]),
                    str(saida["rotulo"]),
                    float(saida["valor"]),
                    str(saida["dimensao"]),
                    1.0,
                )
            )
        if publicas:
            continue
        for campo, valor in (registro.get("resultados") or {}).items():
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                continue
            if not math.isfinite(valor):
                continue
            conhecida = tabela.get(_unidade_pelo_nome(str(campo)))
            fontes.append(
                Fonte(
                    id_,
                    titulo,
                    marca,
                    str(campo),
                    str(campo),
                    float(valor),
                    conhecida[0] if conhecida else None,
                    conhecida[1] if conhecida else 1.0,
                )
            )
    return fontes


def opcoes_da_fonte(
    fonte: Fonte, dimensao: str | None = None, fator: float | None = None
) -> dict[str, str]:
    """O que o bloco guarda: a identidade do registro e o valor que usou, na base."""
    fator_final = fonte.fator if fator is None else fator
    return {
        "registro": fonte.registro_id,
        "titulo": fonte.registro_titulo,
        "assinatura": fonte.assinatura,
        "campo": fonte.campo,
        "rotulo": fonte.rotulo,
        "dimensao": str(dimensao or fonte.dimensao or ""),
        "fator": repr(fator_final),
        "bruto": repr(fonte.valor),
        "valor": repr(fonte.valor * fator_final),
    }


@dataclass(frozen=True)
class Diagnostico:
    no: str
    situacao: str
    mensagem: str
    fonte: Fonte | None = None


def conferir_referencias(
    grafo: mt.Grafo, projeto: Mapping[str, Any] | None, dominio: str, u: Unidades
) -> list[Diagnostico]:
    """Compara cada bloco de referência com o registro que ele aponta."""
    fontes = fontes_do_projeto(projeto, dominio, u)
    por_registro = {(f.registro_id, f.campo): f for f in fontes}
    registros = {
        str(r.get("id")): r
        for r in (projeto or {}).get("registros_tecnicos", [])
        if isinstance(r, Mapping)
    }
    diagnosticos: list[Diagnostico] = []
    for no in grafo.nos:
        if no.tipo != mb.REFERENCIA:
            continue
        opcoes = dict(no.opcoes)
        id_ = opcoes.get("registro")
        if not id_:
            continue
        nome = opcoes.get("rotulo", "resultado")
        registro = registros.get(id_)
        if registro is None:
            diagnosticos.append(
                Diagnostico(
                    no.id,
                    AUSENTE,
                    f"A referência a {nome} aponta para um registro que não está no projeto "
                    "ativo. A conta segue com o valor guardado.",
                )
            )
            continue
        if registro.get("status") == STATUS_SUPERADO:
            diagnosticos.append(
                Diagnostico(
                    no.id,
                    DESATUALIZADA,
                    f"O registro de {nome} foi superado. Escolha o cálculo que o substituiu.",
                )
            )
            continue
        fonte = por_registro.get((id_, opcoes.get("campo", "")))
        if fonte is None:
            diagnosticos.append(
                Diagnostico(
                    no.id,
                    INCOMPATIVEL,
                    f"O registro mudou e não tem mais {nome}. Escolha outro resultado.",
                )
            )
            continue
        if registro.get("hash_calculo") != opcoes.get("assinatura"):
            antes = opcoes.get("bruto", "")
            diagnosticos.append(
                Diagnostico(
                    no.id,
                    DESATUALIZADA,
                    f"O cálculo de {nome} mudou: a conta usa {antes}, e ele agora diz "
                    f"{fonte.valor:g}. Atualize a referência.",
                    fonte,
                )
            )
            continue
        diagnosticos.append(Diagnostico(no.id, EM_DIA, f"{nome}: em dia com o registro.", fonte))
    return diagnosticos


def ids_referenciados(grafo: mt.Grafo) -> set[str]:
    return {
        dict(no.opcoes)["registro"]
        for no in grafo.nos
        if no.tipo == mb.REFERENCIA and dict(no.opcoes).get("registro")
    }


def por_id(nos: Iterable[Mapping[str, Any]], alvo: str) -> Mapping[str, Any] | None:
    """Acha um bloco pelo id completo, entrando nos conjuntos: ``c1/n2``."""
    partes = alvo.split("/")
    atual: Mapping[str, Any] | None = None
    lista = nos
    for parte in partes:
        atual = next((n for n in lista if str(n.get("id")) == parte), None)
        if atual is None:
            return None
        lista = (atual.get("grafo") or {}).get("nos") or ()
    return atual


__all__ = [
    "AUSENTE",
    "DESATUALIZADA",
    "Diagnostico",
    "EM_DIA",
    "ErroDeArquivo",
    "FORMATO",
    "Fonte",
    "INCOMPATIVEL",
    "assinatura",
    "conferir_referencias",
    "documento",
    "em_json",
    "fontes_do_projeto",
    "g",
    "ids_referenciados",
    "ler_documento",
    "montagens_do_projeto",
    "opcoes_da_fonte",
    "por_id",
    "registro_tecnico",
    "saidas_publicas",
    "texto_da_resposta",
    "unidades_conhecidas",
]
