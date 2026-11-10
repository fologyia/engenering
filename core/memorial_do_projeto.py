"""Juntar num documento só o resultado das várias páginas do mesmo projeto.

Cada página grava o seu cálculo no projeto ("Registrar no projeto"): a verificação das barras, os
pilares, as ligações, as placas de base, as reações nas bases… O memorial (Central de relatórios)
junta esses registros. Este módulo arruma o que entra:

* **um de cada** — o mesmo cálculo registrado de novo fica só com o mais novo (nas páginas do
  modelo inteiro, o mesmo tipo de cálculo; nas outras, a cópia idêntica): os de antes viram
  "Superado" (ficam no histórico, saem do memorial);
* **na ordem do projeto** — cargas, vento, barras, pilares, vigas, escadas, ligações, placas de
  base, fundações e o modelo em 3D, como o fluxo do projeto (:mod:`core.roteiro`);
* **o que falta** — num projeto com o modelo do SolidWorks, as etapas do modelo que ainda não
  têm registro aparecem com a página onde registrar.

Sem Streamlit.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from core.project_records import superar_registro
from core.technical_records import registro_superado


@dataclass(frozen=True)
class Etapa:
    nome: str
    pagina: str
    #: (modulo_id, começo do título) — título vazio vale para qualquer registro do módulo.
    registros: tuple[tuple[str, str], ...]
    #: Aparece mesmo sem registro quando o projeto tem os resultados do SolidWorks.
    do_modelo: bool = False


ETAPAS: tuple[Etapa, ...] = (
    Etapa("Cargas do esqueleto", "app_pages/cargas_esqueleto.py", (("cargas_esqueleto", ""),)),
    Etapa(
        "Vento",
        "app_pages/vento_nbr6123.py",
        (("vento_nbr6123", ""), ("vento_estrutura_aberta", "")),
    ),
    Etapa(
        "Contraventamento",
        "app_pages/contraventamento_estrutura.py",
        (("contraventamento_estrutura", ""),),
    ),
    Etapa(
        "Verificação das barras",
        "app_pages/esforcos_modelo.py",
        (("esforcos_modelo", "Verificação das barras"),),
        do_modelo=True,
    ),
    Etapa("Sensores do modelo", "app_pages/sensores_do_modelo.py", (("sensores_do_modelo", ""),)),
    Etapa(
        "Pilares",
        "app_pages/colunas_do_modelo.py",
        (("colunas_do_modelo", ""), ("flambagem_colunas", "")),
        do_modelo=True,
    ),
    Etapa(
        "Vigas, eixos e pisos",
        "app_pages/viga_de_piso.py",
        (("viga_de_piso", ""), ("vigas_eixos", "")),
    ),
    Etapa(
        "Escadas e acessos",
        "app_pages/degrau_escada.py",
        (("degrau_escada", ""), ("estruturas_aco", "")),
    ),
    Etapa(
        "Ligações",
        "app_pages/ligacoes_estruturais.py",
        (
            ("ligacoes_estruturais", ""),
            ("projeto_parafusos", ""),
            ("ligacao_contraventamento", ""),
        ),
    ),
    Etapa(
        "Placas de base",
        "app_pages/esforcos_modelo.py",
        (("esforcos_modelo", "Placas de base"), ("placa_de_base", "")),
        do_modelo=True,
    ),
    Etapa(
        "Fundações",
        "app_pages/reacoes_nas_bases.py",
        (("esforcos_modelo", "Quadro de cargas"), ("reacoes_nas_bases", "")),
        do_modelo=True,
    ),
    Etapa("Modelo em 3D", "app_pages/modelo_3d.py", (("modelo_3d", ""),)),
)
OUTROS = "Outros cálculos"


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def indice_da_etapa(registro: Mapping[str, Any]) -> int:
    """A posição da etapa do registro em :data:`ETAPAS` (``len(ETAPAS)`` = outros cálculos)."""
    modulo = _texto(registro.get("modulo_id")).casefold()
    titulo = _texto(registro.get("titulo")).casefold()
    for indice, etapa in enumerate(ETAPAS):
        for modulo_da_etapa, comeco in etapa.registros:
            if modulo == modulo_da_etapa and titulo.startswith(comeco.casefold()):
                return indice
    return len(ETAPAS)


#: Páginas cujo cálculo é o modelo inteiro (um por projeto): registrar de novo é atualizar.
DO_MODELO_INTEIRO = frozenset(
    {
        "esforcos_modelo",
        "colunas_do_modelo",
        "reacoes_nas_bases",
        "cargas_esqueleto",
        "sensores_do_modelo",
    }
)


def chave_do_calculo(registro: Mapping[str, Any]) -> tuple[str, ...]:
    """O mesmo cálculo.

    * Nas páginas do modelo inteiro (:data:`DO_MODELO_INTEIRO`): a mesma página e o mesmo tipo
      de cálculo (o título até o “—”: "Verificação das barras do modelo", "Placas de base dos
      pilares"…) — o registro novo é a versão nova do mesmo cálculo.
    * Nas outras: a cópia idêntica (mesma página, título, peça, entradas e resultados). Duas
      colunas diferentes com o mesmo título são dois cálculos e ficam os dois.
    """
    modulo = _texto(registro.get("modulo_id")).casefold()
    titulo = " ".join(_texto(registro.get("titulo")).casefold().split())
    if modulo in DO_MODELO_INTEIRO:
        return (modulo, titulo.split(" — ")[0])
    componentes = registro.get("componentes_ids") or ()
    conteudo = json.dumps(
        [registro.get("entradas"), registro.get("resultados")],
        sort_keys=True,
        default=str,
        ensure_ascii=False,
    )
    return (
        modulo,
        titulo,
        _texto(registro.get("peca")).casefold(),
        ",".join(sorted(_texto(c) for c in componentes))
        if isinstance(componentes, Sequence)
        else "",
        conteudo,
    )


def _vigentes(registros: Sequence[Mapping[str, Any]]) -> list[tuple[int, Mapping[str, Any]]]:
    return [
        (posicao, r)
        for posicao, r in enumerate(registros)
        if isinstance(r, Mapping) and _texto(r.get("id")) and not registro_superado(r)
    ]


def _quando(posicao: int, registro: Mapping[str, Any]) -> tuple[str, int]:
    """Mais novo = criado depois; no empate (ou sem data), o que está mais para o fim da lista."""
    return (_texto(registro.get("criado_em")), posicao)


def repetidos(registros: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """Os registros vigentes que outro mais novo do mesmo cálculo substitui: {antigo: novo}."""
    grupos: dict[tuple[str, ...], list[tuple[int, Mapping[str, Any]]]] = {}
    for posicao, r in _vigentes(registros):
        grupos.setdefault(chave_do_calculo(r), []).append((posicao, r))
    saida: dict[str, str] = {}
    for itens in grupos.values():
        if len(itens) < 2:
            continue
        itens.sort(key=lambda par: _quando(*par))
        novo = _texto(itens[-1][1].get("id"))
        for _, antigo in itens[:-1]:
            saida[_texto(antigo.get("id"))] = novo
    return saida


def ordem_do_projeto(
    registros: Sequence[Mapping[str, Any]], *, fora: Sequence[str] = ()
) -> list[str]:
    """Os ids que entram no memorial: um de cada cálculo, vigentes, na ordem das etapas (e, na
    mesma etapa, na ordem em que foram registrados). ``fora`` = módulos que não entram."""
    sobram = repetidos(registros)
    excluidos = {m.casefold() for m in fora}
    entram = [
        (posicao, r)
        for posicao, r in _vigentes(registros)
        if _texto(r.get("id")) not in sobram
        and _texto(r.get("modulo_id")).casefold() not in excluidos
    ]
    entram.sort(key=lambda par: (indice_da_etapa(par[1]), _quando(*par)))
    return [_texto(r.get("id")) for _, r in entram]


@dataclass(frozen=True)
class LinhaDaEtapa:
    etapa: str
    pagina: str
    calculos: int  # os que entram (um de cada)
    repetidos: int  # os que o mais novo substitui
    titulos: tuple[str, ...]
    ultimo: str  # data do mais novo (dd/mm/aaaa)

    @property
    def situacao(self) -> str:
        if not self.calculos:
            return "Falta registrar"
        texto = f"{self.calculos} cálculo(s)"
        if self.repetidos:
            texto += f" · {self.repetidos} repetido(s) a tirar"
        return texto


def _data(iso: str) -> str:
    data = iso[:10]
    if len(data) == 10 and data[4] == "-" and data[7] == "-":
        return f"{data[8:10]}/{data[5:7]}/{data[:4]}"
    return ""


def quadro(projeto: Mapping[str, Any], *, fora: Sequence[str] = ()) -> list[LinhaDaEtapa]:
    """Uma linha por etapa: as que têm registro e, num projeto com o modelo do SolidWorks, as
    etapas do modelo ainda sem registro (com a página onde registrar)."""
    registros = [r for r in projeto.get("registros_tecnicos", []) or [] if isinstance(r, Mapping)]
    excluidos = {m.casefold() for m in fora}
    registros = [r for r in registros if _texto(r.get("modulo_id")).casefold() not in excluidos]
    sobram = repetidos(registros)
    com_modelo = bool(projeto.get("esforcos_do_modelo"))
    por_etapa: dict[int, list[Mapping[str, Any]]] = {}
    tirar: dict[int, int] = {}
    for _, r in _vigentes(registros):
        indice = indice_da_etapa(r)
        if _texto(r.get("id")) in sobram:
            tirar[indice] = tirar.get(indice, 0) + 1
        else:
            por_etapa.setdefault(indice, []).append(r)
    linhas: list[LinhaDaEtapa] = []
    for indice in range(len(ETAPAS) + 1):
        itens = por_etapa.get(indice, [])
        etapa = ETAPAS[indice] if indice < len(ETAPAS) else None
        if not itens and not tirar.get(indice) and not (etapa and etapa.do_modelo and com_modelo):
            continue
        linhas.append(
            LinhaDaEtapa(
                etapa.nome if etapa else OUTROS,
                etapa.pagina if etapa else "",
                len(itens),
                tirar.get(indice, 0),
                tuple(_texto(r.get("titulo")) for r in itens),
                _data(max((_texto(r.get("criado_em")) for r in itens), default="")),
            )
        )
    return linhas


def juntar(
    projeto: Mapping[str, Any], *, fora: Sequence[str] = ()
) -> tuple[dict[str, Any], int, list[str]]:
    """O projeto arrumado para o memorial: os repetidos superados pelo mais novo e a composição
    do memorial com um de cada, na ordem do projeto. Devolve (projeto, superados, ids na ordem)."""
    documento = deepcopy(dict(projeto))
    sobram = repetidos(documento.get("registros_tecnicos", []) or [])
    for antigo, novo in sobram.items():
        documento = superar_registro(
            documento,
            antigo,
            motivo="Registrado de novo: vale o mais novo (Juntar o projeto, Central de relatórios).",
            substituto_id=novo,
        )
    ordem = ordem_do_projeto(documento.get("registros_tecnicos", []) or [], fora=fora)
    todos = [
        _texto(r.get("id"))
        for r in documento.get("registros_tecnicos", []) or []
        if isinstance(r, Mapping) and _texto(r.get("id"))
    ]
    configuracao = dict(documento.get("configuracao_relatorio") or {})
    configuracao["registros_incluidos"] = ordem
    configuracao["ordem_registros"] = ordem + [i for i in todos if i not in ordem]
    documento["configuracao_relatorio"] = configuracao
    return documento, len(sobram), ordem
