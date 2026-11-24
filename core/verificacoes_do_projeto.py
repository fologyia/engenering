"""Quais verificações complementares de estrutura metálica o projeto ativo pede.

Lê o que o projeto já tem — o plano de cargas (monovia, ponte rolante, impacto, equipamentos), a
lista de material (tubos, perfis dobrados), os registros técnicos (vigas, pilares) — e diz, para
cada uma das verificações complementares, se ela já está registrada, se o projeto dá sinal de que
ela é necessária (com o motivo) ou se só vale "quando houver". Sem Streamlit.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

REGISTRADA = "Registrada"
INDICADA = "Indicada pelo projeto"
SE_HOUVER = "Quando houver"


@dataclass(frozen=True)
class Verificacao:
    titulo: str
    pagina: str
    modulo_id: str
    quando: str  # quando ela se aplica, em geral


@dataclass(frozen=True)
class Sugestao:
    verificacao: Verificacao
    motivo: str  # o sinal no projeto ("" sem sinal)
    registros: int  # registros vigentes do módulo

    @property
    def situacao(self) -> str:
        if self.registros:
            return REGISTRADA
        return INDICADA if self.motivo else SE_HOUVER


VERIFICACOES: tuple[Verificacao, ...] = (
    Verificacao("Forças localizadas na alma", "app_pages/forcas_localizadas.py",
                "forcas_localizadas",
                "vigas apoiadas por cima ou por baixo em outras vigas, pés de equipamento na mesa"),
    Verificacao("Viga de monovia", "app_pages/monovia.py", "monovia",
                "talha correndo na mesa de baixo de uma viga"),
    Verificacao("Contenção lateral (travamentos)", "app_pages/contencao_lateral.py",
                "contencao_lateral",
                "pilares ou vigas calculados com travamentos intermediários"),
    Verificacao("Viga mista", "app_pages/viga_mista.py", "viga_mista",
                "laje de concreto ligada às vigas por conectores"),
    Verificacao("Aberturas na alma", "app_pages/aberturas_alma.py", "aberturas_alma",
                "furos na alma para tubulação, eletrocalha ou duto"),
    Verificacao("Terças e travessas", "app_pages/tercas.py", "tercas_formadas_a_frio",
                "cobertura ou fechamento com terças e travessas de chapa dobrada"),
    Verificacao("Ligação rígida viga–pilar", "app_pages/ligacao_rigida.py", "ligacao_rigida",
                "pórticos sem contraventamento, com ligações de momento"),
    Verificacao("Nós de treliça tubular", "app_pages/nos_tubulares.py", "nos_tubulares",
                "treliças de tubo com as diagonais soldadas no banzo"),
    Verificacao("Fadiga da estrutura", "app_pages/fadiga_estrutural.py", "fadiga_estrutural",
                "talhas, pontes rolantes, peneiras, britadores: carga repetida muitas vezes"),
    Verificacao("Estrutura em incêndio", "app_pages/incendio.py", "incendio",
                "edificação com tempo requerido de resistência ao fogo (NBR 14432)"),
)  # fmt: skip

_CODIGOS_CICLICOS = {"MO": "monovia", "PRV": "ponte rolante", "HT": "ponte rolante",
                     "HL": "ponte rolante", "IM": "impacto de equipamentos"}  # fmt: skip


def _codigos_do_plano(projeto: Mapping[str, Any]) -> set[str]:
    plano = projeto.get("plano_de_cargas")
    acoes = plano.get("acoes") if isinstance(plano, Mapping) else None
    codigos: set[str] = set()
    for acao in acoes if isinstance(acoes, Sequence) and not isinstance(acoes, str) else ():
        if isinstance(acao, Mapping) and acao.get("codigo"):
            codigos.add(str(acao["codigo"]).strip().upper())
    return codigos


def _perfis_da_lista(projeto: Mapping[str, Any]) -> list[str]:
    lista = projeto.get("lista_de_material")
    itens = lista.get("itens") if isinstance(lista, Mapping) else None
    nomes: list[str] = []
    for item in itens if isinstance(itens, Sequence) and not isinstance(itens, str) else ():
        if isinstance(item, Mapping):
            nomes.append(str(item.get("descricao") or "").strip())
    return [n for n in nomes if n]


def _registros_vigentes(projeto: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    registros = projeto.get("registros_tecnicos")
    if not isinstance(registros, Sequence) or isinstance(registros, str):
        return []
    return [
        r for r in registros if isinstance(r, Mapping) and not r.get("superado_em")
    ]  # fmt: skip


def _e_tubo(nome: str) -> bool:
    n = nome.casefold()
    return (
        n.startswith(("tc ", "tr ", "tq ", "tubo", "ø", "hss", "chs", "rhs", "shs")) or "tubo" in n
    )


def _e_dobrado(nome: str) -> bool:
    """Perfil de chapa dobrada: Ue, C ou Z seguidos da medida, "C ideal…", cartola, enrijecido."""
    n = nome.casefold().replace(" ", "")
    return (
        bool(re.match(r"^(ue|c|z)\d", n))
        or n.startswith(("cideal", "cartola"))
        or ("enrijecido" in n)
    )


def sugestoes(projeto: Mapping[str, Any] | None) -> list[Sugestao]:
    """Uma sugestão por verificação, na ordem de :data:`VERIFICACOES`."""
    if not isinstance(projeto, Mapping):
        return [Sugestao(v, "", 0) for v in VERIFICACOES]
    codigos = _codigos_do_plano(projeto)
    perfis = _perfis_da_lista(projeto)
    registros = _registros_vigentes(projeto)
    por_modulo: dict[str, int] = {}
    for r in registros:
        chave = str(r.get("modulo_id") or "")
        por_modulo[chave] = por_modulo.get(chave, 0) + 1

    def ha(*modulos: str) -> bool:
        return any(por_modulo.get(m) for m in modulos)

    motivos: dict[str, str] = {}
    if "MO" in codigos:
        motivos["monovia"] = "o plano de cargas tem a monovia (MO)"
    ciclicos = sorted({_CODIGOS_CICLICOS[c] for c in codigos if c in _CODIGOS_CICLICOS})
    if ciclicos:
        motivos["fadiga_estrutural"] = "o plano tem carga repetida: " + ", ".join(ciclicos)
    if "EQ" in codigos or ha("viga_de_piso", "esforcos_modelo"):
        motivos["forcas_localizadas"] = (
            "o projeto tem vigas verificadas"
            + (" e equipamentos no plano (EQ)" if "EQ" in codigos else "")
            + ": confira as que apoiam pela mesa ou recebem carga concentrada"
        )
    if ha("colunas_do_modelo", "flambagem_colunas"):
        motivos["contencao_lateral"] = (
            "há pilares verificados: os travamentos que reduzem o comprimento de flambagem "
            "precisam de força e rigidez"
        )
    tubos = [p for p in perfis if _e_tubo(p)]
    if tubos:
        motivos["nos_tubulares"] = f"a lista de material tem tubos ({tubos[0]})"
    dobrados = [p for p in perfis if _e_dobrado(p)]
    if dobrados:
        motivos["tercas_formadas_a_frio"] = (
            f"a lista de material tem perfil dobrado ({dobrados[0]})"
        )
    return [
        Sugestao(v, motivos.get(v.modulo_id, ""), por_modulo.get(v.modulo_id, 0))
        for v in VERIFICACOES
    ]


def resumo(lista: Sequence[Sugestao]) -> dict[str, int]:
    contagem = {REGISTRADA: 0, INDICADA: 0, SE_HOUVER: 0}
    for s in lista:
        contagem[s.situacao] += 1
    return contagem
