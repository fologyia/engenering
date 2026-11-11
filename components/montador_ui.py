"""Tela do Montador: a prancheta de blocos, o inspetor e a fórmula isolada.

Vale para as duas partes do programa, a de materiais e a de fluidos: muda o ``Parte``, com os blocos,
as unidades e os modelos dela. O desenho mora em ``st.session_state`` e entra por callback, antes de o
script rodar: assim a resposta já sai do desenho que acabou de chegar e vai na mesma rodada para a
prancheta. Os valores ficam guardados na base do sistema, e os campos só mostram na unidade da tela:
trocar a unidade não muda a conta. ``revisao`` renova os campos quando os números mudam por fora deles.

A conta roda a cada mudança, e por isso não há resultado velho na tela nem botão de recalcular.
Tudo o que aparece e some fica abaixo da prancheta: acima, um aviso remontaria o componente.
"""

from __future__ import annotations

import html
import json
import math
import time
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st
import sympy as sp

from components import montador_eixo_ui as eixo_ui
from components import repasse_do_montador as rpm
from components import volta_da_secao as vs
from components.edicao_de_tabela import com_edicoes as _com_edicoes
from components.figuras import SO_NA_LARGURA
from components.prancheta_blocos_ui import prancheta_de_blocos
from components.project_tools import (
    botao_registrar_calculo,
    id_registro_existente,
    projeto_ativo_persistente,
)
from components.robustez import registrar_falha
from components.ui import fronteira_modelo
from core import armazenamento
from core import diagnostico as dg
from core import montador as mt
from core import montador_blocos as mb
from core import montador_busca as bs
from core import montador_casos as mcs
from core import montador_catalogo as cat
from core import montador_conjuntos as mc
from core import montador_eixo as me
from core import montador_fluidos as fl
from core import montador_formula as mf
from core import montador_grandezas as g
from core import montador_historico as mh
from core import montador_planilha as mp
from core import montador_registro as rg
from core import montador_repasse as rp
from core import montador_sensibilidade as ms
from core import montador_uso as mus
from core import montador_word as mw
from core.montador_grandezas import Grandeza, Unidades
from core.montador_modelos import Modelo, Parte
from core.montador_secoes import Estado

_NAO_VARRE = "Nenhuma"
_MAX_INCOGNITAS = 3
_DIVISOES = 30
_PADRAO_DO_PROGRAMA = "Padrão do programa"
_DIGITADO = "Digitado"
_DO_MODELO = "Exemplo do modelo"
#: Onde começar a faixa de uma letra sem valor, na base de cada sistema.
_CENTRO_DA_FAIXA = {
    g.MEDIDA: 100.0,
    g.COMPRIMENTO: 1000.0,
    g.FORCA: 1e4,
    g.MOMENTO: 1e6,
    g.TENSAO: 250.0,
    g.DIAMETRO: 0.1,
    g.VAZAO: 0.01,
    g.ALTURA: 10.0,
    g.PRESSAO: 1e5,
    g.VELOCIDADE: 2.0,
    g.POTENCIA: 1e4,
}
_RUIM_NA_SITUACAO = (rg.AUSENTE, rg.INCOMPATIVEL, rg.DESATUALIZADA)
_PIOR_PRIMEIRO = ("erro", "alerta", "falta", "ok")
_MIME_WORD = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_MIME_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_LINHAS_DO_CATALOGO = 12
#: O que o cartão mostra em destaque nos blocos que só entregam um número para o próximo.
_SAIDA_NO_CARTAO = {
    "limite_fadiga": ("se", "S_e", g.TENSAO),
    "entalhe": ("kf", "K_f", g.PURO),
    "engrenagem": ("F_t", "F_t", g.FORCA),
    "polia": ("F", "F", g.FORCA),
    "par_engrenagens": ("F_t", "F_t", g.FORCA),
    "engrenagem_conica": ("F_t", "F_t", g.FORCA),
}
_AJUDA_DA_FORMULA = (
    "Três formas: q*L^2/8 dá um valor; M = q*L^2/8 dá um valor com nome e também uma equação; "
    "M*c/I <= S_y/n dá uma condição. Use * para vezes e ^ para potência. Funções: sqrt, sin, cos, "
    "tan, exp, ln, log10 e abs. Letra igual à do programa usa o mesmo valor e a mesma unidade."
)
_ALTURA_DA_PRANCHETA = 574
_PORQUE_DO_FIO = {
    mb.SECAO: (
        "Este fio não leva um número. Leva a seção com os esforços somados e as tensões de cada "
        "ponto: cada bloco da fila acrescenta o dele, e por isso a ordem dos esforços não muda a "
        "conta. O critério lê tudo isso ponto a ponto."
    ),
    mb.LINHA: (
        "Este fio leva a linha inteira: o fluido, a vazão e os trechos. Cada bloco da fila "
        "acrescenta o dele, e a perda de carga sai da soma de todos."
    ),
    mb.VALOR: (
        "Este fio troca a letra do bloco de destino pela fórmula do bloco de origem. Só liga "
        "grandeza igual: momento entra onde se pede momento."
    ),
    mb.MATERIAL: (
        "Um fio só leva S_y, S_ut, E e G. O mesmo material alimenta todas as verificações, e "
        "trocar o material muda todas de uma vez."
    ),
    mb.CONDICAO: (
        "Este fio leva as condições do critério até o resultado. É lá que se decide quem manda: "
        "o maior dos mínimos, ou o menor dos máximos."
    ),
}
_ESTILO = """
<style>
.st-key-mf_inspetor [data-testid="stNumberInputStepUp"],
.st-key-mf_inspetor [data-testid="stNumberInputStepDown"],
.st-key-mfl_inspetor [data-testid="stNumberInputStepUp"],
.st-key-mfl_inspetor [data-testid="stNumberInputStepDown"] { display: none; }
.st-key-mf_inspetor label p, .st-key-mfl_inspetor label p { font-size: .76rem; }
.st-key-mf_inspetor [data-testid="stVerticalBlock"],
.st-key-mfl_inspetor [data-testid="stVerticalBlock"] { gap: .55rem; }
.mi-topo { display: flex; align-items: center; justify-content: space-between; }
.mi-rot, .mi-secao {
  font-size: .66rem; font-weight: 700; letter-spacing: .09em; text-transform: uppercase;
  opacity: .64;
}
.mi-secao { margin-top: .3rem; }
.mi-resposta {
  border-radius: .45rem; padding: .5rem .65rem; margin-bottom: .15rem;
  background: rgba(27, 140, 90, .10); border: 1px solid rgba(27, 140, 90, .30);
}
.mi-resposta.falta { background: rgba(11, 110, 153, .07); border-color: rgba(11, 110, 153, .24); }
.mi-resposta.erro { background: rgba(190, 50, 40, .08); border-color: rgba(190, 50, 40, .30); }
.mi-valor {
  font-family: "JetBrains Mono", monospace; font-size: 1.08rem; font-weight: 700;
  line-height: 1.3; margin-top: .12rem; overflow-wrap: anywhere;
}
.mi-pagina { font-size: .72rem; margin-top: .6rem; }
.mi-selo {
  font-size: .62rem; font-weight: 700; letter-spacing: .05em; text-transform: uppercase;
  color: #0B6E99; background: rgba(11, 110, 153, .11); padding: .08rem .42rem; border-radius: .3rem;
}
.mi-titulo { font-size: 1.04rem; font-weight: 700; line-height: 1.25; margin-top: .3rem; }
.mi-sub { font-size: .78rem; line-height: 1.4; opacity: .76; margin-top: .22rem; }
.mi-chip {
  display: inline-block; margin-top: .4rem; padding: .1rem .42rem; border-radius: .3rem;
  font-family: "JetBrains Mono", monospace; font-size: .68rem; line-height: 1.5;
  background: rgba(11, 110, 153, .08); color: #17324D;
}
.mi-linha {
  display: flex; justify-content: space-between; gap: .7rem; padding: .2rem 0;
  border-bottom: 1px solid rgba(23, 32, 51, .09); font-size: .78rem; line-height: 1.3;
}
.mi-linha span:last-child {
  font-family: "JetBrains Mono", monospace; font-size: .72rem; text-align: right;
  white-space: nowrap;
}
.mi-tabela { width: 100%; border-collapse: collapse; font-size: .7rem; margin-top: .2rem; }
.mi-tabela th { font-weight: 600; opacity: .7; text-align: right; padding: .1rem .15rem; }
.mi-tabela td {
  font-family: "JetBrains Mono", monospace; text-align: right; padding: .17rem .15rem;
  border-top: 1px solid rgba(23, 32, 51, .09);
}
.mi-tabela th:first-child, .mi-tabela td:first-child {
  text-align: left; font-family: inherit; font-size: .72rem;
}
.mi-ok, .mi-nao { display: flex; gap: .4rem; font-size: .78rem; line-height: 1.55; }
.mi-ok b { color: #0B5F45; }
.mi-nao b { color: #C2415D; }
</style>
"""


def _numero(valor: float) -> str:
    if valor == 0.0 or not math.isfinite(valor):
        return "0"
    if 1e4 <= abs(valor) < 1e12:  # 200.000, e não 2e+05
        return f"{valor:,.0f}".replace(",", ".")
    return f"{valor:.4g}".replace(".", ",")


def _com_unidade(valor: float, grandeza: Grandeza, u: Unidades) -> str:
    rotulo = u.rotulo(grandeza.dimensao)
    numero = _numero(valor / u.fator(grandeza.dimensao))
    return f"{numero} {rotulo}".strip()


def _letra(grandeza: Grandeza) -> str:
    return sp.latex(grandeza.simbolo)


def _para_o_campo(valor: float | None, fator: float) -> float | None:
    """Sem o ruído da conversão: 4,5e-5 m aparece 0,045 mm, e não 0.045000000000000005."""
    return None if valor is None else float(f"{valor / fator:.12g}")


def _titulo_do_campo(grandeza: Grandeza, u: Unidades) -> str:
    rotulo = u.rotulo(grandeza.dimensao)
    return f"{grandeza.texto}: {grandeza.nome}" + (f" ({rotulo})" if rotulo else "")


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------


_DA_MONTAGEM = (
    "grafo",
    "valores",
    "origens",
    "padroes",
    "alvo",
    "adotado",
    "modelo_atual",
    "casos",
)


def _instantaneo(p: Parte) -> dict[str, Any]:
    estado = st.session_state
    return {nome: json.loads(json.dumps(estado.get(p.k(nome)))) for nome in _DA_MONTAGEM}


def _restaurar(p: Parte, foto: Mapping[str, Any], versao: int) -> None:
    """Volta a montagem inteira de uma vez. A cópia é para o histórico não mudar junto com a tela."""
    estado = st.session_state
    copia = json.loads(json.dumps(foto))
    # Acima da versão da prancheta: senão ela fica com o desenho que tem e ignora o que volta.
    _trocar_grafo(p, copia["grafo"], versao=max(versao, estado.get(p.k("versao"), 0)) + 1)
    for nome in _DA_MONTAGEM[1:]:
        estado[p.k(nome)] = copia.get(nome)  # foto antiga, de antes dos casos, vem sem eles
    estado[p.k("revisao")] = estado.get(p.k("revisao"), 0) + 1
    _outra_montagem(p)  # os números já vêm com os blocos certos


def _trocar_grafo(p: Parte, dados: Mapping[str, Any], *, versao: int | None = None) -> None:
    estado = st.session_state
    estado[p.k("grafo")] = dict(dados)
    atual = estado.get(p.k("versao"), 0)
    estado[p.k("versao")] = max(atual, versao or 0) if versao is not None else atual + 1


def _aplicar(p: Parte, modelo: Modelo) -> None:
    estado = st.session_state
    _trocar_grafo(p, modelo.grafo())
    estado[p.k("ajuste")] = estado.get(p.k("ajuste"), 0) + 1
    estado[p.k("valores")] = dict(modelo.valores)
    estado[p.k("origens")] = dict.fromkeys(modelo.valores, _DO_MODELO)
    estado[p.k("padroes")] = {}
    estado[p.k("alvo")] = modelo.alvo
    estado[p.k("adotado")] = None
    estado[p.k("revisao")] = estado.get(p.k("revisao"), 0) + 1
    estado[p.k("modelo_atual")] = modelo.nome
    estado[p.k("casos")] = None
    estado[p.k("titulo")] = modelo.nome
    estado[p.k("selecao")] = None
    estado[p.k("mudanca")] = ""
    estado.pop(p.k("ultima"), None)
    _outra_montagem(p)


def _outra_montagem(p: Parte) -> None:
    """Os valores chegaram junto com os blocos: não há letra de antes para acompanhar."""
    estado = st.session_state
    estado[p.k("letras_por_no")] = None
    estado[p.k("colar")] = {}


def _iniciar(p: Parte) -> None:
    estado = st.session_state
    if p.k("grafo") in estado:
        return
    estado[p.k("unidades")] = tuple(s.padrao for s in p.sistema.seletores)
    _aplicar(p, p.modelos[0])


def _selecionar(p: Parte, selecao: Mapping[str, Any] | None) -> None:
    """A tela também escolhe: o pedido vai para a prancheta na rodada seguinte, uma vez só."""
    estado = st.session_state
    estado[p.k("selecao")] = None if selecao is None else dict(selecao)
    numero = estado.get(p.k("pedidos"), 0) + 1
    estado[p.k("pedidos")] = numero
    pedido: dict[str, Any] = {"n": numero, "caminho": []}
    if selecao is not None and selecao.get("tipo") == "no":
        *caminho, local = str(selecao["id"]).split("/")
        pedido |= {"caminho": caminho, "no": local}
    elif selecao is not None:
        pedido["caminho"] = list(selecao.get("caminho") or ())
        pedido["fio"] = {k: selecao[k] for k in ("de", "saida", "para", "entrada")}
    estado[p.k("pedido")] = pedido


def _ao_escolher_modelo(p: Parte) -> None:
    estado = st.session_state
    modelo = p.por_nome.get(estado.get(p.k("modelo")) or "")
    if modelo is not None:
        estado[p.k("anterior")] = _instantaneo(p)
        _aplicar(p, modelo)


def _ao_editar(p: Parte) -> None:
    estado = st.session_state
    evento = getattr(estado.get(p.k("prancheta")), "edicao", None)
    if not evento or not isinstance(evento.get("grafo"), Mapping):
        return
    _trocar_grafo(p, mc.tirar_portas_mortas(evento["grafo"]), versao=int(evento.get("versao", 0)))
    if not evento.get("so_posicao"):  # arrumar a prancheta não troca a conta
        estado[p.k("modelo_atual")] = None
    elif evento.get("automatico"):
        estado[p.k("juntar")] = True  # a prancheta se arrumou sozinha: não é passo para desfazer
    _guardar_colagens(p, evento.get("colados"))


def _guardar_colagens(p: Parte, colados: Any) -> None:
    """Cada colagem tem uma senha, e a prancheta manda de novo até ver a senha de volta.

    Os números só vão para a cópia depois de montar: é lá que se sabe a letra de cada bloco.
    """
    if not isinstance(colados, Mapping):
        return
    estado = st.session_state
    feitas = set(estado.get(p.k("colagens")) or ())
    pendentes = dict(estado.get(p.k("colar")) or {})
    for senha, pares in colados.items():
        if str(senha) not in feitas and isinstance(pares, Mapping):
            pendentes[str(senha)] = {str(k): str(v) for k, v in pares.items()}
    estado[p.k("colar")] = pendentes


def _ao_selecionar(p: Parte) -> None:
    estado = st.session_state
    evento = getattr(estado.get(p.k("prancheta")), "selecao", None)
    estado[p.k("selecao")] = None if not evento or evento.get("tipo") == "nada" else dict(evento)


def _ao_comandar(p: Parte) -> None:
    """Os pedidos da prancheta vêm em fila, numerados.

    Duas rodadas pedidas juntas viram uma só no Streamlit, e a de antes se perde. Por isso cada
    pedido traz também os de antes que ainda não voltaram confirmados, e aqui só entra o que é novo.
    """
    estado = st.session_state
    evento = getattr(estado.get(p.k("prancheta")), "comando", None)
    if not isinstance(evento, Mapping):
        return
    if "lista" not in evento:
        _comandar(p, evento)  # um pedido só, sem fila
        return
    ultimo = estado.get(p.k("comandos"), 0)
    for item in evento.get("lista") or ():
        n = item.get("n") if isinstance(item, Mapping) else None
        if isinstance(n, bool) or not isinstance(n, int) or n <= ultimo:
            continue
        _comandar(p, item)
        ultimo = n
    estado[p.k("comandos")] = ultimo


def _comandar(p: Parte, item: Mapping[str, Any]) -> None:
    acao = item.get("acao")
    if acao == "agrupar":
        _agrupar(p, item)
    elif acao == "valor":
        _valor_do_cartao(p, item)
    elif acao in ("desfazer", "refazer"):
        _andar_na_historia(p, item, para_tras=acao == "desfazer")


def _agrupar(p: Parte, evento: Mapping[str, Any]) -> None:
    estado = st.session_state
    try:
        novo = mc.agrupar(
            estado[p.k("grafo")], list(evento.get("ids") or ()), "", evento.get("caminho") or ()
        )
    except mc.ErroDeConjunto as erro:
        estado[p.k("erro_conjunto")] = str(erro)
        return
    estado[p.k("erro_conjunto")] = ""
    _trocar_grafo(p, novo, versao=int(evento.get("versao", 0)) + 1)
    estado[p.k("modelo_atual")] = None


def _valor_do_cartao(p: Parte, item: Mapping[str, Any]) -> None:
    """O número digitado no próprio cartão. Chega na unidade da tela e fica guardado na base."""
    estado = st.session_state
    chave = str(item.get("chave") or "")
    dimensao = (estado.get(p.k("campos")) or {}).get(chave)
    if dimensao is None or chave == estado.get(p.k("alvo")):
        return  # a letra saiu da montagem, ou virou a letra pedida, desde o desenho
    u = Unidades(p.sistema, tuple(estado[p.k("unidades")]))
    if item.get("unidade") != u.rotulo(dimensao):
        return  # a unidade da tela mudou desde o desenho: o número seria lido errado
    origens = estado[p.k("origens")]
    if item.get("conferir"):
        if mh.copiada(origens.get(chave)):
            origens[chave] = _DIGITADO
        return
    valor = item.get("valor")
    if valor is not None and (
        isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor)
    ):
        return
    estado[p.k("valores")][chave] = None if valor is None else float(valor) * u.fator(dimensao)
    origens[chave] = _DIGITADO
    estado[p.k("revisao")] += 1


def _andar_na_historia(p: Parte, item: Mapping[str, Any], *, para_tras: bool) -> None:
    estado = st.session_state
    historico = estado.get(p.k("historico"))
    if historico is None:
        return
    versao = item.get("versao")
    versao = versao if isinstance(versao, int) and not isinstance(versao, bool) else 0
    grafo = item.get("grafo")
    # O gesto de logo antes do Ctrl+Z pode ter se perdido no caminho: o desenho vem junto e entra
    # primeiro, para o Ctrl+Z desfazer esse gesto, e não o anterior a ele.
    if isinstance(grafo, Mapping) and versao > estado.get(p.k("versao"), 0):
        novo = mc.tirar_portas_mortas(grafo)
        if rg.assinatura({"grafo": novo}) != rg.assinatura({"grafo": estado[p.k("grafo")]}):
            estado[p.k("modelo_atual")] = None
        _trocar_grafo(p, novo, versao=versao)
    mh.registrar(historico, _instantaneo(p))
    antes = historico["atual"]
    foto = mh.desfazer(historico) if para_tras else mh.refazer(historico)
    if foto is None:
        return
    _restaurar(p, foto, versao)
    estado[p.k("andou")] = {"de": antes, "para": foto, "desfeito": para_tras}


def _limpar(p: Parte) -> None:
    estado = st.session_state
    estado[p.k("anterior")] = _instantaneo(p)
    _trocar_grafo(p, {"nos": [], "fios": []})
    estado[p.k("ajuste")] += 1
    estado[p.k("modelo_atual")] = None
    estado[p.k("casos")] = None
    estado[p.k("titulo")] = p.titulo
    estado[p.k("valores")] = {}
    estado[p.k("origens")] = {}
    estado[p.k("padroes")] = {}
    estado[p.k("alvo")] = None
    estado[p.k("adotado")] = None
    estado[p.k("revisao")] += 1
    estado[p.k("selecao")] = None
    _outra_montagem(p)


def _voltar(p: Parte) -> None:
    """Volta à montagem de antes de um modelo, de Limpar ou de abrir outra."""
    estado = st.session_state
    anterior = estado.get(p.k("anterior"))
    if not anterior:
        return
    atual = _instantaneo(p)
    _trocar_grafo(p, anterior["grafo"])
    for nome in _DA_MONTAGEM[1:]:
        estado[p.k(nome)] = anterior.get(nome)
    estado[p.k("ajuste")] += 1
    estado[p.k("revisao")] += 1
    estado[p.k("selecao")] = None
    estado[p.k("anterior")] = atual
    _outra_montagem(p)


def _abrir_documento(p: Parte, doc: Mapping[str, Any]) -> None:
    estado = st.session_state
    estado[p.k("anterior")] = _instantaneo(p)
    _trocar_grafo(p, doc["grafo"])
    estado[p.k("ajuste")] += 1
    estado[p.k("valores")] = dict(doc["valores"])
    estado[p.k("origens")] = dict(doc["origens"])
    estado[p.k("padroes")] = dict(mt.montar(mt.grafo_de_dados(doc["grafo"])).padroes)
    estado[p.k("alvo")] = doc["alvo"]
    estado[p.k("adotado")] = doc["adotado"]
    estado[p.k("casos")] = doc.get("casos")
    estado[p.k("unidades")] = tuple(doc["unidades"])
    estado[p.k("revisao")] += 1
    estado[p.k("modelo_atual")] = None
    estado[p.k("selecao")] = None
    estado[p.k("salvo")] = rg.assinatura(doc)
    _outra_montagem(p)


def _ao_trocar_unidade(p: Parte) -> None:
    estado = st.session_state
    estado[p.k("unidades")] = tuple(estado[p.k(f"u_{s.dimensao}")] for s in p.sistema.seletores)
    estado[p.k("revisao")] += 1


def _cabecalho(p: Parte) -> None:
    estado = st.session_state
    # O Streamlit apaga o estado do seletor que não foi desenhado: quem manda são as chaves atuais.
    for seletor, escolha in zip(p.sistema.seletores, estado[p.k("unidades")], strict=True):
        estado[p.k(f"u_{seletor.dimensao}")] = escolha
    estado[p.k("modelo")] = estado[p.k("modelo_atual")]
    colunas = st.columns([3.0, 1.5, 1.0, 1.0], vertical_alignment="bottom")
    por_nome = p.por_nome
    colunas[0].selectbox(
        "Começar de um modelo",
        list(por_nome),
        index=None,
        placeholder="Montagem minha, sem modelo",
        key=p.k("modelo"),
        on_change=_ao_escolher_modelo,
        args=(p,),
        format_func=lambda nome: f"{nome}: {por_nome[nome].dica}",
        help="Abre os blocos prontos com números de exemplo. Depois é só mudar por cima.",
    )
    # Um botão só para as unidades: com um seletor por coluna, a linha não cabia em tela de
    # notebook (os rótulos e os botões quebravam no meio da palavra).
    with colunas[1].popover(
        "Unidades",
        icon=":material/straighten:",
        help="As unidades dos números da tela: " + " · ".join(estado[p.k("unidades")]) + ".",
        width="stretch",
    ):
        st.caption("Trocar a unidade converte os números que já estão na tela.")
        for seletor in p.sistema.seletores:
            st.selectbox(
                seletor.rotulo,
                tuple(seletor.opcoes),
                key=p.k(f"u_{seletor.dimensao}"),
                on_change=_ao_trocar_unidade,
                args=(p,),
                help=seletor.ajuda,
            )
    colunas[2].button(
        "Limpar",
        key=p.k("limpar"),
        on_click=_limpar,
        args=(p,),
        help="Apaga os blocos para começar do zero. Voltar, ou Ctrl+Z na prancheta, traz de volta.",
        width="stretch",
    )
    colunas[3].button(
        "Voltar",
        key=p.k("voltar"),
        on_click=_voltar,
        args=(p,),
        disabled=not estado.get(p.k("anterior")),
        help="Volta à montagem de antes de um modelo, de Limpar ou de abrir outra.",
        width="stretch",
    )


def _sincronizar_valores(p: Parte, montagem: mt.Montagem) -> None:
    """Letra nova chega com o padrão dela, e trocar o material atualiza S_y.

    Campo esvaziado fica como None: a chave existe, e o padrão não volta sozinho.
    """
    estado = st.session_state
    valores, conhecidos, origens = (
        estado[p.k("valores")],
        estado[p.k("padroes")],
        estado[p.k("origens")],
    )
    mudou = False
    for grandeza in montagem.grandezas:
        if grandeza.chave not in valores and grandeza.padrao is not None:
            if grandeza.chave not in dict(montagem.padroes):
                valores[grandeza.chave] = grandeza.padrao
                origens[grandeza.chave] = _PADRAO_DO_PROGRAMA
                mudou = True
    fontes = dict(montagem.origens)
    for chave, padrao in montagem.padroes:
        if conhecidos.get(chave) != padrao or chave not in valores:
            conhecidos[chave] = padrao
            valores[chave] = padrao
            origens[chave] = fontes.get(chave, _PADRAO_DO_PROGRAMA)
            mudou = True
    if mudou:
        estado[p.k("revisao")] += 1


def _opcoes_de_alvo(montagem: mt.Montagem) -> list[Grandeza]:
    return [item for item in montagem.grandezas if item.chave in montagem.essenciais]


def _alvo(p: Parte, montagem: mt.Montagem) -> str | None:
    """A letra pedida. Sem escolha, a primeira medida sem valor: é o que costuma faltar."""
    estado = st.session_state
    opcoes = _opcoes_de_alvo(montagem)
    if not opcoes:
        return None
    if estado.get(p.k("alvo")) in {item.chave for item in opcoes}:
        return estado[p.k("alvo")]
    valores = estado[p.k("valores")]
    sem_valor = [item for item in opcoes if valores.get(item.chave) is None]
    medidas = [item for item in sem_valor if item.dimensao in (g.MEDIDA, g.DIAMETRO)]
    escolhida = (medidas or sem_valor or opcoes)[0]
    estado[p.k("alvo")] = escolhida.chave
    return escolhida.chave


def _acompanhar_os_blocos(p: Parte, base: mt.Montagem) -> None:
    """O número segue o bloco: apagar o primeiro trecho não dá ao segundo os números do apagado."""
    estado = st.session_state
    depois = mh.letras_por_no(base)
    antes = estado.get(p.k("letras_por_no"))
    estado[p.k("letras_por_no")] = depois
    trocas = mh.renomes(antes, depois) if antes else {}
    if not trocas:
        return
    em_uso = {chave for _, _, letras in depois.values() for chave in letras}
    alvo = estado.get(p.k("alvo"))
    mh.aplicar_renomes(
        trocas, depois, estado[p.k("valores")], estado[p.k("origens")], estado[p.k("padroes")]
    )
    if alvo in trocas and alvo not in em_uso:
        estado[p.k("alvo")] = trocas[alvo]
    estado[p.k("revisao")] += 1


def _preencher_copias(p: Parte, base: mt.Montagem) -> None:
    """A cópia nasce com os números do original, marcados com a procedência até alguém mexer."""
    estado = st.session_state
    pendentes = estado.get(p.k("colar")) or {}
    if not pendentes:
        return
    colados = {novo: original for pares in pendentes.values() for novo, original in pares.items()}
    padroes_do_bloco = dict(base.padroes)

    def padrao(chave: str) -> float | None:
        if chave in padroes_do_bloco:
            return padroes_do_bloco[chave]
        grandeza = base.grandeza(chave)
        return grandeza.padrao if grandeza is not None else None

    def texto(chave: str) -> str:
        grandeza = base.grandeza(chave)
        return grandeza.texto if grandeza is not None else chave

    mh.copiar_valores(
        mh.letras_da_copia(base, colados),
        estado[p.k("valores")],
        estado[p.k("origens")],
        estado[p.k("padroes")],
        padroes_do_bloco,
        padrao,
        texto,
    )
    estado[p.k("colagens")] = [*(estado.get(p.k("colagens")) or ()), *pendentes][-50:]
    estado[p.k("colar")] = {}
    estado[p.k("revisao")] += 1


def _registrar_historia(p: Parte) -> None:
    """Toda mudança entra aqui, venha de onde vier: da prancheta, do inspetor ou do cartão."""
    estado = st.session_state
    atual = _instantaneo(p)
    juntar = bool(estado.pop(p.k("juntar"), False))
    historico = estado.get(p.k("historico"))
    if historico is None:
        estado[p.k("historico")] = mh.novo(atual)
    else:
        mh.registrar(historico, atual, juntar=juntar)


def _o_que_mudou(
    de: Mapping[str, Any], para: Mapping[str, Any], base: mt.Montagem, u: Unidades
) -> str:
    """O que o Ctrl+Z fez, em poucas palavras: a conta demora um instante, e a tela diz o porquê."""
    m = mh.mudanca(de, para)
    blocos_de = mh.blocos(de.get("grafo") or {})
    blocos_para = mh.blocos(para.get("grafo") or {})
    if m.tipos or len(m.entraram) + len(m.sairam) > 2 or (m.entraram and m.sairam):
        return "a montagem voltou como estava"
    if m.entraram or m.sairam:
        partes = [f"o bloco {_nome_do_no(blocos_para[i])} voltou" for i in m.entraram]
        partes += [f"o bloco {_nome_do_no(blocos_de[i])} saiu" for i in m.sairam]
        return " e ".join(partes)
    partes = []
    valores = para.get("valores") or {}
    mudaram = [c for c in m.valores if base.grandeza(c) is not None]
    if 0 < len(mudaram) <= 2:
        for chave in mudaram:
            grandeza = base.grandeza(chave)
            valor = valores.get(chave)
            if valor is None:
                partes.append(f"{grandeza.texto} ficou como letra")
            else:
                partes.append(f"{grandeza.texto} voltou a {_com_unidade(valor, grandeza, u)}")
    elif mudaram:
        partes.append(f"{len(mudaram)} valores voltaram como eram")
    elif m.origens:
        origens = para.get("origens") or {}
        textos = ", ".join(_texto_da_letra(base, c) for c in m.origens)
        varios = len(m.origens) > 1
        if any(mh.copiada(origens.get(c)) for c in m.origens):
            marcado = "voltaram a ficar marcados" if varios else "voltou a ficar marcado"
            partes.append(f"{textos} {marcado} como cópia")
        else:
            partes.append(f"{textos} {'ficaram conferidos' if varios else 'ficou conferido'}")
    if m.alvo:
        alvo = base.grandeza(str(para.get("alvo") or ""))
        partes.append(f"a letra pedida voltou a {alvo.texto}" if alvo else "a letra pedida voltou")
    elif m.adotado:
        partes.append("o valor adotado voltou")
    if m.opcoes:
        partes.append(f"a escolha do bloco {_nome_do_no(blocos_para[m.opcoes[0]])} voltou")
    elif m.fios:
        partes.append("a ligação voltou como era")
    if not partes and m.lugares:
        partes.append("os blocos voltaram ao lugar")
    return " e ".join(partes[:2])


def _texto_da_letra(base: mt.Montagem, chave: str) -> str:
    grandeza = base.grandeza(chave)
    return grandeza.texto if grandeza is not None else chave


def _contar_o_que_andou(p: Parte, base: mt.Montagem, u: Unidades) -> None:
    estado = st.session_state
    andou = estado.pop(p.k("andou"), None)
    if not andou:
        return
    texto = _o_que_mudou(andou["de"], andou["para"], base, u)
    feito = "Desfeito" if andou["desfeito"] else "Refeito"
    anterior = estado.get(p.k("aviso_historia")) or {}
    estado[p.k("aviso_historia")] = {
        "n": anterior.get("n", 0) + 1,
        "texto": f"{feito}: {texto}." if texto else f"{feito}.",
    }


# ---------------------------------------------------------------------------
# O que vai para a prancheta
# ---------------------------------------------------------------------------


def _sinal(sentido: str | None) -> str:
    return {mt.MINIMO: "≥", mt.MAXIMO: "≤"}.get(sentido or "", "=")


def _pedacos_no_cartao(
    chaves: Sequence[str],
    base: mt.Montagem,
    valores: Mapping[str, float | None],
    alvo: str | None,
    u: Unidades,
) -> list[list[str]]:
    """Cada letra do cartão com a chave dela: na prancheta, dois cliques no pedaço mudam o número."""
    pedacos = []
    for chave in chaves:
        grandeza = base.grandeza(chave)
        if grandeza is None:
            continue
        valor = valores.get(chave)
        if valor is None or chave == alvo:
            pedacos.append([f"{grandeza.texto} = ?", chave])
        else:
            pedacos.append([f"{grandeza.texto} = {_com_unidade(valor, grandeza, u)}", chave])
    return pedacos


def _letras_no_cartao(
    chaves: Sequence[str],
    base: mt.Montagem,
    valores: Mapping[str, float | None],
    alvo: str | None,
    u: Unidades,
) -> str:
    return " · ".join(texto for texto, _ in _pedacos_no_cartao(chaves, base, valores, alvo, u))


def _campos_do_cartao(
    base: mt.Montagem,
    valores: Mapping[str, float | None],
    origens: Mapping[str, str],
    alvo: str | None,
    u: Unidades,
) -> dict[str, dict[str, Any]]:
    """O que a caixinha do cartão precisa de cada letra: o número já na unidade da tela."""
    campos = {}
    for item in base.grandezas:
        valor = valores.get(item.chave)
        campos[item.chave] = {
            "t": item.texto,
            "n": item.nome,
            "v": _para_o_campo(valor, u.fator(item.dimensao)),
            "u": u.rotulo(item.dimensao),
            "alvo": item.chave == alvo,
            "copia": mh.copiada(origens.get(item.chave)) if valor is not None else "",
        }
    return campos


def _conjuntos_de(nos: Sequence[Mapping[str, Any]], prefixo: str = "") -> Iterator[str]:
    for no in nos:
        if no.get("tipo") == mt.CONJUNTO:
            id_ = f"{prefixo}{no['id']}"
            yield id_
            yield from _conjuntos_de(no["grafo"]["nos"], f"{id_}/")


def _marcar_criterios(
    faces: dict[str, dict[str, str]],
    luzes: dict[str, str],
    resposta: mt.Resposta,
    u: Unidades,
) -> None:
    por_bloco: dict[str, list[mt.LinhaConferida]] = {}
    for linha in resposta.conferencia_adotada or resposta.conferencia:
        if not linha.igualdade:
            por_bloco.setdefault(linha.no, []).append(linha)
    for id_, lista in por_bloco.items():
        maior = max(linha.uso for linha in lista)
        face = faces.setdefault(id_, {})
        uso = f"Utilização = {_numero(maior * 100.0)} %"
        # No cartão, os números do critério continuam à vista depois do uso, para mudar ali mesmo.
        face["p"] = [[uso, ""], *(x for x in face.get("p", ()) if x[1])]
        face["a"] = uso
        luzes[id_] = "erro" if maior > 1.0 + 1e-9 else "ok"
    pedidos: dict[str, list[mt.Isolada]] = {}
    for item in resposta.isoladas:
        if item.valor is not None:
            pedidos.setdefault(item.condicao.no, []).append(item)
    for id_, itens in pedidos.items():
        lado = itens[0].lado
        numeros = [i.valor or 0.0 for i in itens if i.lado == lado]
        valor = max(numeros) if lado == mt.MINIMO else min(numeros)
        texto = _com_unidade(valor, resposta.alvo, u)
        faces.setdefault(id_, {})["b"] = f"{resposta.alvo.texto} {_sinal(lado)} {texto}"


def _marcar_resultado(
    id_: str,
    faces: dict[str, dict[str, str]],
    luzes: dict[str, str],
    resposta: mt.Resposta,
    u: Unidades,
) -> None:
    partes = []
    if resposta.manda is not None:
        partes.append(f"{resposta.manda.condicao.nome} manda")
    if resposta.adotado is not None:
        partes.append(f"adotado {_com_unidade(resposta.adotado, resposta.alvo, u)}")
    tem_numero = resposta.valor is not None
    faces[id_] = {
        "a": " · ".join(partes) or f"Em função de {resposta.alvo.texto}",
        "b": rg.texto_da_resposta(resposta, u) if tem_numero else "",
    }
    pior = max((linha.uso for linha in resposta.conferencia_adotada), default=0.0)
    luzes[id_] = "erro" if pior > 1.0 + 1e-9 else "ok" if tem_numero else "falta"


def _faces(
    grafo: mt.Grafo,
    dados: Mapping[str, Any],
    base: mt.Montagem,
    resposta: mt.Resposta | None,
    valores: Mapping[str, float | None],
    alvo: str | None,
    u: Unidades,
    numeros: Mapping[sp.Symbol, sp.Float] | None = None,
) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """O miolo de cada cartão: as letras com valor, o uso do critério e a resposta."""
    faces: dict[str, dict[str, str]] = {}
    luzes: dict[str, str] = {}
    proprias = dict(base.letras_do_bloco)
    for no in grafo.nos:
        bloco = mb.POR_CHAVE[no.tipo]
        letras = proprias.get(no.id, ())
        pedacos = _pedacos_no_cartao(letras, base, valores, alvo, u)
        if not pedacos and bloco.face is not None:
            pedacos = [[bloco.face(dict(no.opcoes)), ""]]
        if bloco.grupo in (mb.GRUPO_MATERIAL, mb.GRUPO_FLUIDO) and bloco.opcoes:
            escolha = dict(no.opcoes).get(bloco.opcoes[0].chave, bloco.opcoes[0].padrao)
            pedacos = [[str(escolha), ""], *pedacos]
        if no.tipo == mb.FORMULA and dict(no.opcoes).get("texto"):
            pedacos = [[dict(no.opcoes)["texto"], ""]]
        pedacos = [x for x in pedacos if x[0]]
        texto = " · ".join(x[0] for x in pedacos)
        if texto:
            faces[no.id] = {"a": texto, "p": pedacos}
        faltam = any(valores.get(c) is None and c != alvo for c in letras)
        luzes[no.id] = "falta" if faltam else "ok"
        destaque = _SAIDA_NO_CARTAO.get(no.tipo)
        if destaque is not None and numeros is not None:
            porta, nome, dimensao = destaque
            numero = _saida_em_numero(base, no.id, porta, dimensao, numeros, u)
            if numero:
                faces.setdefault(no.id, {})["b"] = f"{nome} = {numero}"
    if resposta is not None:
        _marcar_criterios(faces, luzes, resposta, u)
        for no in grafo.nos:
            if no.tipo == mb.RESULTADO:
                _marcar_resultado(no.id, faces, luzes, resposta, u)
    for id_ in _conjuntos_de(dados["nos"]):
        dentro = [no.id for no in grafo.nos if no.id.startswith(f"{id_}/")]
        letras = tuple(dict.fromkeys(c for i in dentro for c in proprias.get(i, ())))
        forte = next((faces[i]["b"] for i in dentro if faces.get(i, {}).get("b")), "")
        pedacos = _pedacos_no_cartao(letras, base, valores, alvo, u)
        faces[id_] = {"a": " · ".join(x[0] for x in pedacos), "b": forte, "p": pedacos}
        achadas = {luzes.get(i) for i in dentro}
        luzes[id_] = next((luz for luz in _PIOR_PRIMEIRO if luz in achadas), "ok")
    return faces, luzes


def _situacao(
    grafo: mt.Grafo,
    montagem: mt.Montagem,
    resposta: mt.Resposta | None,
    falha: str,
    diagnosticos: Sequence[rg.Diagnostico],
    padroes_em_uso: Sequence[str],
    salvo: bool,
    copiados: Sequence[str] = (),
) -> dict[str, str]:
    """A linha acima da prancheta: completo não quer dizer aprovado."""
    if not grafo.nos:
        return {
            "nivel": "falta",
            "titulo": "Prancheta vazia",
            "detalhe": "Comece por uma seção ou por um fluido, e vá clicando na biblioteca.",
        }
    if montagem.erros:
        return {
            "nivel": "falta",
            "titulo": "Modelo incompleto",
            "detalhe": montagem.erros[0][1],
        }
    if not montagem.tem_resultado or not montagem.condicoes:
        return {
            "nivel": "falta",
            "titulo": "Modelo incompleto",
            "detalhe": "Ponha um critério e o bloco Em função de.",
        }
    if falha:
        return {"nivel": "erro", "titulo": "Sem resposta", "detalhe": falha}
    if resposta is None:
        return {"nivel": "falta", "titulo": "Modelo incompleto", "detalhe": ""}
    if resposta.invalidos:
        return {"nivel": "erro", "titulo": "Valor inválido", "detalhe": resposta.invalidos[0]}
    if resposta.faltam:
        nomes = ", ".join(item.texto for item in resposta.faltam)
        return {
            "nivel": "falta",
            "titulo": "Faltam valores",
            "detalhe": f"A fórmula está pronta. Para sair o número, preencha {nomes}.",
        }
    ruins = [d for d in diagnosticos if d.situacao in _RUIM_NA_SITUACAO]
    if ruins:
        return {"nivel": "alerta", "titulo": "Referência a conferir", "detalhe": ruins[0].mensagem}
    quantas = len(montagem.condicoes)
    partes = [f"{quantas} {'condição' if quantas == 1 else 'condições'}"]
    if copiados:
        partes.append(f"número copiado em {', '.join(copiados)}")
    if padroes_em_uso:
        partes.append(f"valor padrão em {', '.join(padroes_em_uso)}")
    partes.append("alterações não salvas" if not salvo else "salvo")
    partes.append("pré-dimensionamento")
    return {"nivel": "ok", "titulo": "Modelo completo", "detalhe": " · ".join(partes)}


def _rastro(grafo: mt.Grafo, resposta: mt.Resposta | None) -> list[str]:
    if resposta is None or resposta.manda is None:
        return []
    return sorted(mt.ids_ate_o_inicio(grafo, [resposta.manda.condicao.no]))


# ---------------------------------------------------------------------------
# Campos
# ---------------------------------------------------------------------------


def _ao_mudar_opcao(p: Parte, no_id: str, opcao: str, chave: str) -> None:
    estado = st.session_state
    no = rg.por_id(estado[p.k("grafo")]["nos"], no_id)
    bloco = mb.POR_CHAVE.get(str(no.get("tipo"))) if no is not None else None
    escolhas = next((o.lista() for o in bloco.opcoes if o.chave == opcao), ()) if bloco else ()
    if no is None or estado.get(chave) not in escolhas:
        return  # o bloco mudou desde que a lista foi desenhada
    no.setdefault("opcoes", {})[opcao] = estado[chave]
    estado[p.k("versao")] += 1
    estado[p.k("modelo_atual")] = None


def _saida_em_numero(
    base: mt.Montagem,
    id_: str,
    porta: str,
    dimensao: str,
    numeros: Mapping[sp.Symbol, sp.Float],
    u: Unidades,
) -> str:
    """O número que sai de uma bolinha, se já não sobrou letra nenhuma."""
    valor = base.saidas.get(id_, {}).get(porta)
    if valor is None:
        return ""
    numero = mt.numero_de(valor, numeros)
    if numero is None:
        return ""
    return f"{_numero(numero / u.fator(dimensao))} {u.rotulo(dimensao)}".strip()


#: A opção do bloco Seção desenhada com o nome da seção salva em Desenhar seção.
OPCAO_DO_DESENHO = "desenho"


def _secao_que_voltou(p: Parte) -> None:
    """A seção desenhada que voltou de Desenhar seção entra no bloco que a pediu."""
    chegou = vs.chegada(p.prefixo)
    if chegou is None:
        return
    estado = st.session_state
    no = rg.por_id(estado[p.k("grafo")]["nos"], str(chegou["campo"]))
    bloco = mb.POR_CHAVE.get(str(no.get("tipo"))) if no is not None else None
    opcao = next((o for o in bloco.opcoes if o.chave == OPCAO_DO_DESENHO), None) if bloco else None
    nome = str(chegou["nome"])
    if no is None or opcao is None or nome not in opcao.lista():
        estado[p.k("aviso_secao")] = (
            f"A seção {nome} foi salva, mas o bloco que a pediu não está mais na montagem: "
            "escolha-a na lista do bloco Seção desenhada."
        )
        return
    no.setdefault("opcoes", {})[OPCAO_DO_DESENHO] = nome
    estado[p.k("versao")] += 1
    estado[p.k("modelo_atual")] = None
    estado[p.k("aviso_secao")] = f"A seção {nome}, que você acabou de desenhar, já está no bloco."


def _opcoes_dos_blocos(p: Parte, nos: Sequence[mt.No]) -> None:
    """A lista de cada bloco que tem escolha, como a seção desenhada e o material."""
    estado = st.session_state
    for no in nos:
        bloco = mb.POR_CHAVE[no.tipo]
        for opcao in bloco.opcoes:
            escolhas = opcao.lista()
            atual = dict(no.opcoes).get(opcao.chave, opcao.padrao)
            chave = f"{p.prefixo}_op_{no.id}_{opcao.chave}"
            estado[chave] = atual if atual in escolhas else opcao.padrao
            st.selectbox(
                f"{bloco.nome}: {opcao.rotulo.lower()}",
                escolhas,
                key=chave,
                on_change=_ao_mudar_opcao,
                args=(p, no.id, opcao.chave, chave),
                help=opcao.ajuda,
            )
            if opcao.chave == OPCAO_DO_DESENHO and st.button(
                "Desenhar uma seção nova",
                icon=":material/draw:",
                key=f"{p.prefixo}_desenhar_{no.id}",
                help=(
                    "Abre Desenhar seção. Desenhe, dê um nome e clique em Salvar e voltar: a "
                    "seção volta já escolhida neste bloco."
                ),
            ):
                vs.ir_desenhar(f"app_pages/{p.modulo_id}.py", p.titulo, p.prefixo, no.id)


def _da_rodada_atual(p: Parte, campo: str) -> bool:
    """Campo de antes de trocar o modelo não grava mais nada.

    Se a prancheta pede uma rodada enquanto a anterior ainda desenha, o navegador manda junto os
    campos velhos, com os números do modelo anterior. A revisão no nome do campo separa os dois.
    """
    return campo.startswith(
        f"{p.prefixo}_v_{st.session_state[p.k('revisao')]}_"
    ) or campo.startswith(f"{p.prefixo}_adotado_{st.session_state[p.k('revisao')]}")


def _no_do_tipo(p: Parte, no_id: str, tipo: str) -> Any:
    """O bloco, se ainda for do tipo esperado: depois de trocar o modelo, o id pode ser outro bloco."""
    no = rg.por_id(st.session_state[p.k("grafo")]["nos"], no_id)
    if no is None or no.get("tipo") != tipo:
        return None
    return no


def _ao_digitar(p: Parte, chave: str, fator: float, campo: str) -> None:
    estado = st.session_state
    if not _da_rodada_atual(p, campo):
        return
    valor = estado.get(campo)
    estado[p.k("valores")][chave] = None if valor is None else float(valor) * fator
    estado[p.k("origens")][chave] = _DIGITADO


def _campo_de_valor(p: Parte, grandeza: Grandeza, u: Unidades) -> None:
    estado = st.session_state
    fator = u.fator(grandeza.dimensao)
    guardado = estado[p.k("valores")].get(grandeza.chave)
    campo = f"{p.prefixo}_v_{estado[p.k('revisao')]}_{grandeza.chave}"
    if campo not in estado:
        estado[campo] = _para_o_campo(guardado, fator)
    # value=None é o que deixa o campo ser esvaziado: o número entra pelo session_state.
    st.number_input(
        _titulo_do_campo(grandeza, u),
        value=None,
        format="%g",
        step=None,
        key=campo,
        on_change=_ao_digitar,
        args=(p, grandeza.chave, fator, campo),
        placeholder="fica como letra",
        help=grandeza.ajuda,
    )


def _origem_dos_valores(p: Parte, letras: Sequence[Grandeza]) -> None:
    """Quem não foi digitado aparece escrito: número sozinho parece decisão de alguém."""
    origens = st.session_state[p.k("origens")]
    valores = st.session_state[p.k("valores")]
    grupos: dict[str, list[str]] = {}
    copias: list[Grandeza] = []
    for item in letras:
        origem = origens.get(item.chave)
        if not origem or origem == _DIGITADO or valores.get(item.chave) is None:
            continue
        if mh.copiada(origem):
            copias.append(item)
        else:
            grupos.setdefault(origem, []).append(item.texto)
    for origem, nomes in grupos.items():
        st.caption(f"{', '.join(nomes)}: {origem.lower() if origem[0] == 'P' else origem}.")
    if not copias:
        return
    novas = ", ".join(item.texto for item in copias)
    fontes = ", ".join(mh.copiada(origens[item.chave]) for item in copias)
    if len(copias) == 1:
        st.caption(f"{novas}: copiado de {fontes}. Confira se serve aqui.")
    else:
        st.caption(f"{novas}: copiados de {fontes}. Confira se servem aqui.")
    st.button(
        "Os números copiados estão certos",
        key=p.k("conferir_copias"),
        on_click=_conferir_copias,
        args=(p, tuple(item.chave for item in copias)),
        help="Marca os números copiados como conferidos: passam a contar como digitados.",
        width="stretch",
    )


def _conferir_copias(p: Parte, chaves: Sequence[str]) -> None:
    origens = st.session_state[p.k("origens")]
    for chave in chaves:
        if mh.copiada(origens.get(chave)):
            origens[chave] = _DIGITADO


def _campos(p: Parte, letras: Sequence[Grandeza], alvo: str | None, u: Unidades) -> None:
    for grandeza in letras:
        if grandeza.chave != alvo:
            _campo_de_valor(p, grandeza, u)
    if alvo and any(item.chave == alvo for item in letras):
        texto = next(item.texto for item in letras if item.chave == alvo)
        st.caption(f"{texto} é a letra pedida: o valor sai da conta.")
    _origem_dos_valores(p, [item for item in letras if item.chave != alvo])


def _numeros_de(
    valores: Mapping[str, float | None], resposta: mt.Resposta | None
) -> dict[sp.Symbol, sp.Float]:
    """Os números da conta: os valores, e a resposta (ou o adotado) no lugar da letra pedida."""
    usados = {k: v for k, v in valores.items() if v is not None}
    if resposta is not None:
        usados = mt.valores_do_caso(resposta)  # com casos de carga, os do caso que manda
        valor = resposta.adotado or resposta.valor
        if valor is not None:
            usados[resposta.alvo.chave] = valor
    return {sp.Symbol(k, positive=True): sp.Float(v) for k, v in usados.items()}


def _numeros_da_conta(p: Parte, resposta: mt.Resposta | None) -> dict[sp.Symbol, sp.Float]:
    return _numeros_de(st.session_state[p.k("valores")], resposta)


# ---------------------------------------------------------------------------
# Inspetor
# ---------------------------------------------------------------------------


def _e(texto: object) -> str:
    return html.escape(str(texto), quote=False)


def _topo_do_inspetor(selo: str, titulo: str, subtitulo: str = "", chip: str = "") -> None:
    partes = [
        '<div class="mi-topo"><span class="mi-rot">Inspetor</span>'
        f'<span class="mi-selo">{_e(selo)}</span></div>',
        f'<div class="mi-titulo">{_e(titulo)}</div>',
    ]
    if subtitulo:
        partes.append(f'<div class="mi-sub">{_e(subtitulo)}</div>')
    if chip:
        partes.append(f'<div class="mi-chip">{_e(chip)}</div>')
    st.html("".join(partes))


@contextmanager
def _parte(p: Parte, nome: str) -> Iterator[None]:
    """Uma parte da página abaixo da prancheta: se ela falhar, as outras continuam na tela."""
    try:
        yield
    except Exception as erro:
        if dg.levantar_erros():
            raise
        registrar_falha(f"{p.titulo} › {nome}", erro)
        st.caption(
            f"A parte “{nome}” não pôde ser mostrada com esta montagem. O resto da página "
            f"continua valendo (ref. {dg.referencia_da_falha(erro)})."
        )


def _resposta_no_inspetor(
    resposta: mt.Resposta | None, falha: str, montagem: mt.Montagem, u: Unidades
) -> None:
    """A resposta fica ao lado da prancheta: mudar um número mostra o efeito sem rolar a página."""
    if falha:
        classe, valor, sub = "erro", "Sem resposta", falha
    elif resposta is None:
        if not montagem.condicoes:
            return
        classe, valor, sub = (
            "falta",
            "Sem resposta",
            "Escolha a letra pedida no bloco Em função de.",
        )
    elif resposta.valor is not None and resposta.manda is not None:
        classe, valor = "", rg.texto_da_resposta(resposta, u)
        sub = f"Quem manda: {resposta.manda.condicao.nome}."
        if resposta.conferencia_adotada:
            pior = max(resposta.conferencia_adotada, key=lambda linha: linha.uso)
            adotado = _com_unidade(resposta.adotado or 0.0, resposta.alvo, u)
            situacao = "não passa" if pior.uso > 1.0 + 1e-9 else "passa"
            sub += (
                f" Com {resposta.alvo.texto} = {adotado}: {situacao}, uso de "
                f"{_numero(pior.uso * 100.0)} %."
            )
            if situacao == "não passa":
                classe = "erro"
    else:
        nomes = ", ".join(item.texto for item in resposta.faltam)
        classe, valor = "falta", f"{resposta.alvo.texto} em letras"
        sub = f"Para sair o número, preencha {nomes}." if nomes else "A fórmula está mais abaixo."
    st.html(
        f'<div class="mi-resposta {classe}"><span class="mi-rot">Resposta</span>'
        f'<div class="mi-valor">{_e(valor)}</div><div class="mi-sub">{_e(sub)}</div></div>'
    )


def _como_usar(p: Parte) -> None:
    primeiro = "uma seção" if p.dominio == mb.SOLIDOS else "um fluido e um trecho de tubo"
    with st.expander("Como usar esta página", icon=":material/help:"):
        st.markdown(
            f"""
1. **Comece de um modelo** parecido com a sua peça, ou clique em **Limpar** e monte do zero.
2. **Monte na prancheta**: clique num bloco da biblioteca à esquerda e ele entra na fila. Comece por
   {primeiro}, depois os esforços, um critério e, no fim, o bloco **Em função de**.
3. **Ponha os números** no inspetor à direita. Campo vazio fica como letra na fórmula.
4. **Escolha a letra pedida** em *Deixar em função de*. A resposta aparece no topo do inspetor, no
   cartão do critério e, com a fórmula, logo abaixo da prancheta.

**Na prancheta**

| Para | Faça |
|---|---|
| Ver só um bloco ou uma ligação | Um clique nele |
| Mudar um número no cartão | Dois cliques no número |
| Ligar dois blocos | Arraste de uma bolinha até a outra |
| Pôr um bloco no meio de uma ligação | Clique na ligação e depois no bloco da biblioteca |
| Apagar o que está selecionado | Tecla Delete |
| Desfazer e refazer | Ctrl+Z e Ctrl+Y |
| Copiar e colar blocos | Ctrl+C e Ctrl+V |
| Arrumar os blocos na tela | Botão Organizar |

Abaixo da resposta ficam: as condições, a busca com várias incógnitas, a escolha no catálogo, o
que mais pesa, a comparação de duas montagens e os documentos (Word, Excel e registro no projeto).
"""
        )


def _titulo_de_secao(texto: str) -> None:
    st.html(f'<div class="mi-secao">{_e(texto)}</div>')


def _titulo_da_pagina(texto: str) -> None:
    st.html(f'<div class="mi-secao mi-pagina">{_e(texto)}</div>')


def _linhas(pares: Sequence[tuple[str, str]]) -> str:
    return "".join(
        f'<div class="mi-linha"><span>{_e(a)}</span><span>{_e(b)}</span></div>' for a, b in pares
    )


def _nome_do_no(bruto: Mapping[str, Any] | None) -> str:
    if bruto is None:
        return "Bloco"
    if bruto.get("tipo") == mt.CONJUNTO:
        return str(bruto.get("nome"))
    bloco = mb.POR_CHAVE.get(str(bruto.get("tipo")))
    return bloco.nome if bloco else "Bloco"


def _inspetor_geral(
    p: Parte, grafo: mt.Grafo, base: mt.Montagem, alvo: str | None, u: Unidades
) -> None:
    _topo_do_inspetor(
        "Montagem",
        "Valores da montagem",
        "Clique num bloco ou numa ligação para ver só o dele. Dois cliques num número do cartão "
        "também mudam o valor. Campo vazio fica como letra.",
    )
    com_opcoes = [no for no in grafo.nos if mb.POR_CHAVE[no.tipo].opcoes]
    if base.grandezas or com_opcoes:
        _titulo_de_secao("Parâmetros editáveis")
    _campos(p, base.grandezas, alvo, u)
    _opcoes_dos_blocos(p, com_opcoes)


def _formulas_do_bloco(base: mt.Montagem, no: mt.No, resposta: mt.Resposta | None) -> None:
    bloco = mb.POR_CHAVE[no.tipo]
    saidas = base.saidas.get(no.id, {})
    for porta in mb.portas_de(no.tipo, dict(no.opcoes))[1]:
        valor = saidas.get(porta.chave)
        if isinstance(valor, sp.Expr):
            st.latex(f"{porta.rotulo.replace('·', ' ')} = {sp.latex(valor)}")
        elif isinstance(valor, Estado):
            if bloco.grupo == mb.GRUPO_SECAO:
                for rotulo, expressao in valor.secao.propriedades():
                    st.latex(f"{rotulo} = {sp.latex(expressao)}")
            for t in valor.tensoes:
                if not t.nula:
                    st.caption(t.ponto)
                    st.latex(
                        f"\\sigma = {sp.latex(mt.limpar(t.sx))},\\quad "
                        f"\\tau = {sp.latex(mt.limpar(t.tau))}"
                    )
        elif isinstance(valor, list):
            for condicao in valor:
                st.caption(condicao.nome)
                sinal = "=" if condicao.igualdade else "\\le"
                st.latex(
                    f"{condicao.letra} = "
                    f"{sp.latex(mt.limpar(condicao.esquerda, condicao.positiva))} "
                    f"{sinal} {sp.latex(condicao.direita)}"
                )


def _conferidos(pares: Sequence[tuple[str, bool]]) -> str:
    return "".join(
        f'<div class="mi-ok"><b>✓</b>{_e(rotulo)}</div>'
        if certo
        else f'<div class="mi-nao"><b>✕</b>{_e(rotulo)}</div>'
        for rotulo, certo in pares
    )


def _mudar_formula(p: Parte, id_: str, **mudancas: str) -> None:
    estado = st.session_state
    no = _no_do_tipo(p, id_, mb.FORMULA)
    if no is None:
        return
    opcoes = no.setdefault("opcoes", {})
    opcoes.update(mudancas)
    opcoes["sistema"] = p.sistema.chave
    no["portas"] = mb.portas_para_a_tela(mb.FORMULA, opcoes)
    _trocar_grafo(p, mc.tirar_fios_soltos(estado[p.k("grafo")], id_.split("/")[:-1]))
    estado[p.k("modelo_atual")] = None


def _ao_digitar_formula(p: Parte, id_: str, campo: str) -> None:
    _mudar_formula(p, id_, texto=str(st.session_state.get(campo) or ""))


def _ao_escolher_letra(p: Parte, id_: str, letra: str, campo: str) -> None:
    estado = st.session_state
    no = _no_do_tipo(p, id_, mb.FORMULA)
    if no is None:
        return
    dimensoes = mf.dimensoes_das_letras((no.get("opcoes") or {}).get("dimensoes"))
    dimensoes[letra] = estado[campo]
    _mudar_formula(p, id_, dimensoes=json.dumps(dimensoes, sort_keys=True))


def _ao_escolher_saida(p: Parte, id_: str, campo: str) -> None:
    _mudar_formula(p, id_, saida=st.session_state[campo])


def _inspetor_da_formula(p: Parte, no: mt.No) -> None:
    estado = st.session_state
    opcoes = dict(no.opcoes)
    texto = opcoes.get("texto", "").strip()
    campo = f"{p.prefixo}_formula_{no.id}"
    estado[campo] = texto
    _titulo_de_secao("Sua fórmula")
    st.text_input(
        "Fórmula",
        key=campo,
        on_change=_ao_digitar_formula,
        args=(p, no.id, campo),
        placeholder="M = q*L^2/8",
        help=_AJUDA_DA_FORMULA,
    )
    if not texto:
        return
    try:
        formula = mf.ler(texto)
    except mf.ErroDeFormula:
        return  # a mensagem já aparece no fim do inspetor, com os erros do bloco
    sistema = p.sistema.chave
    dimensoes = mf.dimensoes_das_letras(opcoes.get("dimensoes"))
    novas = [letra for letra in formula.letras if mf.e_letra_nova(letra, sistema)]
    if novas:
        _titulo_de_secao("Letras novas")
    for letra in novas:
        chave = f"{p.prefixo}_letra_{no.id}_{letra}"
        estado[chave] = mf.grandeza_da_letra(letra, sistema, dimensoes).dimensao
        st.selectbox(
            f"O que é {letra}",
            g.dimensoes_do_sistema(sistema),
            key=chave,
            format_func=g.ROTULOS_DAS_DIMENSOES.__getitem__,
            on_change=_ao_escolher_letra,
            args=(p, no.id, letra, chave),
            help="Diz a unidade da letra. Com isso o programa confere se a fórmula fecha.",
        )
    if formula.tem_valor and (not formula.nome or mf.e_letra_nova(formula.nome, sistema)):
        possiveis = mf.dimensoes_possiveis(formula, sistema, dimensoes)
        if len(possiveis) > 1:
            chave = f"{p.prefixo}_saida_{no.id}"
            estado[chave] = mf.dimensao_da_saida(formula, sistema, dimensoes, opcoes.get("saida"))
            st.selectbox(
                "O resultado é",
                possiveis,
                key=chave,
                format_func=g.ROTULOS_DAS_DIMENSOES.__getitem__,
                on_change=_ao_escolher_saida,
                args=(p, no.id, chave),
                help="Só liga em bolinha da mesma grandeza. Medida e altura têm a mesma unidade.",
            )
    problemas = mf.problemas_de_unidade(formula, sistema, dimensoes)
    _titulo_de_secao("Verificação automática")
    st.html(_conferidos([("As unidades fecham", not problemas)]))
    for problema in problemas:
        st.caption(problema)


def _rotulo_da_peca(nome: str) -> str:
    return f"{nome} · K {_numero(fl.PECAS[nome])}"


def _ao_editar_pecas(p: Parte, id_: str, chave: str) -> None:
    estado = st.session_state
    no = _no_do_tipo(p, id_, "perda_local")
    if no is None:
        return
    atuais = fl.ler_pecas((no.get("opcoes") or {}).get("pecas"))
    nomes = list(fl.PECAS)
    linhas = [{"Peça": _rotulo_da_peca(nome), "Qtd": atuais.get(nome, 0)} for nome in nomes]
    novas = _com_edicoes(linhas, estado[chave])[: len(nomes)]
    pecas = {
        nome: int(x.get("Qtd") or 0)
        for nome, x in zip(nomes, novas, strict=False)
        if (x.get("Qtd") or 0) > 0
    }
    no.setdefault("opcoes", {})["pecas"] = json.dumps(pecas, ensure_ascii=False, sort_keys=True)
    estado[p.k("versao")] += 1
    estado[p.k("modelo_atual")] = None


def _pecas_do_bloco(p: Parte, no: mt.No) -> None:
    atuais = fl.ler_pecas(dict(no.opcoes).get("pecas"))
    quadro = pd.DataFrame(
        [{"Peça": _rotulo_da_peca(nome), "Qtd": atuais.get(nome, 0)} for nome in fl.PECAS]
    )
    chave = f"{p.prefixo}_pecas_{no.id}"
    _titulo_de_secao("Peças da linha")
    st.data_editor(
        quadro,
        key=chave,
        hide_index=True,
        disabled=("Peça",),
        width="stretch",
        on_change=_ao_editar_pecas,
        args=(p, no.id, chave),
        column_config={
            "Peça": st.column_config.TextColumn(width=185),
            "Qtd": st.column_config.NumberColumn(
                width=48,
                min_value=0,
                max_value=99,
                step=1,
                help="Quantas peças iguais há neste trecho.",
            ),
        },
    )
    st.caption("A soma vai para K_L. K de peça aberta, valor típico: varia com o fabricante.")


def _ao_editar_pontos(p: Parte, id_: str, chave: str, titulo: str, fator: float) -> None:
    estado = st.session_state
    no = _no_do_tipo(p, id_, "curva_bomba")
    if no is None:
        return
    atuais = fl.ler_pontos((no.get("opcoes") or {}).get("pontos"))
    linhas = [{titulo: q / fator, "H (m)": h} for q, h in atuais]
    pontos = [
        [float(x[titulo]) * fator, float(x["H (m)"])]
        for x in _com_edicoes(linhas, estado[chave])
        if x.get(titulo) is not None and x.get("H (m)") is not None
    ]
    no.setdefault("opcoes", {})["pontos"] = json.dumps(pontos)
    estado[p.k("versao")] += 1
    estado[p.k("modelo_atual")] = None


def _pontos_da_bomba(p: Parte, no: mt.No, u: Unidades) -> None:
    fator = u.fator(g.VAZAO)
    titulo = f"Q ({u.rotulo(g.VAZAO)})"
    pontos = fl.ler_pontos(dict(no.opcoes).get("pontos"))
    quadro = pd.DataFrame(
        [{titulo: q / fator, "H (m)": h} for q, h in pontos],
        columns=[titulo, "H (m)"],
        dtype=float,
    )
    chave = f"{p.prefixo}_pontos_{no.id}_{titulo}"
    _titulo_de_secao("Pontos do catálogo da bomba")
    st.data_editor(
        quadro,
        key=chave,
        hide_index=True,
        num_rows="dynamic",
        width="stretch",
        on_change=_ao_editar_pontos,
        args=(p, no.id, chave, titulo, fator),
        column_config={
            titulo: st.column_config.NumberColumn(min_value=0.0, help="Vazão do ponto."),
            "H (m)": st.column_config.NumberColumn(min_value=0.0, help="Altura nessa vazão."),
        },
    )
    st.caption("Com dois pontos ou mais, H_0 e a_b saem da curva. Sem pontos, digite os dois.")


def _ligacoes_do_bloco(p: Parte, dados: Mapping[str, Any], id_: str) -> None:
    *caminho, local = id_.split("/")
    atual = mc.nivel(dict(dados), caminho)
    por_id = {n.get("id"): n for n in atual["nos"]}
    entram = [f for f in atual["fios"] if f["para"] == local]
    saem = [f for f in atual["fios"] if f["de"] == local]
    if not entram and not saem:
        return
    pares = [("Recebe de", _nome_do_no(por_id.get(f["de"]))) for f in entram]
    pares += [("Envia para", _nome_do_no(por_id.get(f["para"]))) for f in saem]
    _titulo_de_secao("Ligações")
    st.html(_linhas(list(dict.fromkeys(pares))))
    if saem:
        st.button(
            "Inspecionar conexão de saída",
            key=f"{p.prefixo}_ver_saida_{id_}",
            on_click=_selecionar,
            args=(p, {"tipo": "fio", "caminho": caminho, **saem[0]}),
            help="Seleciona a ligação que sai deste bloco e mostra o que passa nela.",
            width="stretch",
        )


def _uso_do_bloco(no: mt.No, resposta: mt.Resposta | None) -> None:
    if resposta is None:
        return
    linhas = [
        linha
        for linha in resposta.conferencia_adotada or resposta.conferencia
        if linha.no == no.id and not linha.igualdade
    ]
    if linhas:
        _titulo_de_secao("Utilização")
        st.html(_linhas([(x.nome, f"{_numero(x.uso * 100.0)} %") for x in linhas]))


def _inspetor_bloco(
    p: Parte,
    no: mt.No,
    dados: Mapping[str, Any],
    base: mt.Montagem,
    resposta: mt.Resposta | None,
    alvo: str | None,
    u: Unidades,
    diagnosticos: Sequence[rg.Diagnostico],
) -> None:
    bloco = mb.POR_CHAVE[no.tipo]
    if no.tipo == mb.RESULTADO:
        _topo_do_inspetor("Decisão", bloco.nome, bloco.dica)
        _inspetor_resultado(resposta, u)
        return
    chip = dict(no.opcoes).get("texto", "") if no.tipo == mb.FORMULA else bloco.formula
    _topo_do_inspetor("Módulo", bloco.nome, bloco.dica, chip)
    if no.tipo == mb.REFERENCIA:
        _inspetor_referencia(p, no, u, diagnosticos)
        return
    if no.tipo == mb.FORMULA:
        _inspetor_da_formula(p, no)
    proprias = dict(base.letras_do_bloco).get(no.id, ())
    letras = [item for item in base.grandezas if item.chave in proprias]
    if letras or bloco.opcoes:
        _titulo_de_secao("Parâmetros editáveis")
    if letras:
        _campos(p, letras, alvo, u)
    _opcoes_dos_blocos(p, [no] if bloco.opcoes else [])
    if no.tipo == "perda_local":
        _pecas_do_bloco(p, no)
    elif no.tipo == "curva_bomba":
        _pontos_da_bomba(p, no, u)
    elif no.tipo == me.TIPO:
        eixo_ui.ajuda_no_inspetor()
    _uso_do_bloco(no, resposta)
    _ligacoes_do_bloco(p, dados, no.id)
    with st.expander("Fórmula, hipóteses e detalhes", icon=":material/functions:"):
        _formulas_do_bloco(base, no, resposta)
    erro = dict(base.erros).get(no.id)
    if erro:
        st.warning(erro, icon=":material/warning:")


def _quem_manda(resposta: mt.Resposta) -> str:
    """Quem decide, e por quanto: a resposta sem isso não diz o que mudar."""
    manda = resposta.manda
    if manda is None:
        return ""
    nome = manda.condicao.nome
    texto = f"{nome} é quem decide: nessa medida ela chega ao limite."
    outras = sorted(
        (x for x in resposta.conferencia if x.nome != nome and not x.igualdade),
        key=lambda x: x.uso,
        reverse=True,
    )
    if outras:
        texto += (
            f" A seguinte é {outras[0].nome}, com {_numero(outras[0].uso * 100.0)} % do limite. "
            f"Para mudar a resposta, é em {nome} que se mexe."
        )
    return texto


def _inspetor_resultado(resposta: mt.Resposta | None, u: Unidades) -> None:
    if resposta is None:
        st.info("Ligue um critério neste bloco.", icon=":material/info:")
        return
    pares = [("Resposta", rg.texto_da_resposta(resposta, u))]
    adotadas = resposta.conferencia_adotada
    if adotadas and resposta.adotado is not None:
        pior = max(x.uso for x in adotadas)
        pares.append(("Adotado", _com_unidade(resposta.adotado, resposta.alvo, u)))
        pares.append(("Utilização", f"{_numero(pior * 100.0)} %"))
        pares.append(("Situação", "Não atende" if pior > 1.0 + 1e-9 else "Atende"))
    pares.append(("Natureza", "Pré-dimensionamento"))
    _titulo_de_secao("Resultado e dados")
    st.html(_linhas(pares))
    explicacao = _quem_manda(resposta)
    if explicacao:
        _titulo_de_secao("Quem manda")
        st.html(f'<div class="mi-sub">{_e(explicacao)}</div>')
    linhas = sorted(resposta.conferencia, key=lambda linha: linha.uso, reverse=True)
    if len(linhas) > 1:
        _titulo_de_secao("Uso de cada condição")
        st.html(_linhas([(x.nome, f"{_numero(x.uso * 100.0)} %") for x in linhas]))


def _inspetor_conjunto(
    p: Parte,
    bruto: dict[str, Any],
    id_: str,
    base: mt.Montagem,
    alvo: str | None,
    u: Unidades,
) -> None:
    estado = st.session_state
    conteudo = mc.blocos_de_dentro(bruto)
    _topo_do_inspetor(
        "Conjunto",
        str(bruto.get("nome")),
        "Vários blocos num só. Edite os valores aqui, sem abrir o conjunto.",
        f"{len(conteudo)} blocos",
    )
    partes = id_.split("/")
    caminho, id_local = partes[:-1], partes[-1]
    chave_nome = f"{p.prefixo}_nome_{id_}"
    estado[chave_nome] = bruto.get("nome", "")

    def renomear() -> None:
        _trocar_grafo(p, mc.renomear(estado[p.k("grafo")], id_local, estado[chave_nome], caminho))

    _titulo_de_secao("Parâmetros editáveis")
    st.text_input(
        "Nome do conjunto",
        key=chave_nome,
        on_change=renomear,
        help="O nome que aparece no bloco e na biblioteca.",
    )
    proprias: list[str] = []
    for chave, letras in base.letras_do_bloco:
        if chave.startswith(f"{id_}/"):
            proprias.extend(letras)
    letras = [item for item in base.grandezas if item.chave in proprias]
    if letras:
        _campos(p, letras, alvo, u)
    _titulo_de_secao("Conteúdo do conjunto")
    st.html(f'<div class="mi-sub">{_e(" · ".join(conteudo))}</div>')
    _titulo_de_secao("Entradas e saídas")
    _portas_publicas(p, bruto, id_local, caminho)
    if st.button(
        "Desfazer o conjunto",
        key=f"{p.prefixo}_desfazer_{id_}",
        help="Põe os blocos de volta na prancheta.",
        width="stretch",
    ):
        _trocar_grafo(p, mc.desagrupar(estado[p.k("grafo")], id_local, caminho))
        estado[p.k("selecao")] = None
        st.rerun()
    if st.button(
        "Salvar na biblioteca",
        key=f"{p.prefixo}_guardar_{id_}",
        help="Guarda o conjunto em Meus conjuntos, para usar em outras montagens.",
        width="stretch",
    ):
        try:
            mc.salvar(str(bruto.get("nome")), p.dominio, bruto)
        except mc.ErroDeConjunto as erro:
            st.warning(str(erro), icon=":material/warning:")
        else:
            st.success(armazenamento.texto_de_confirmacao(), icon=":material/check_circle:")
            st.rerun()


def _portas_publicas(
    p: Parte, bruto: Mapping[str, Any], id_local: str, caminho: Sequence[str]
) -> None:
    estado = st.session_state
    entradas, saidas = mc.candidatas(bruto)
    nomes = {str(n["id"]): n for n in bruto["grafo"]["nos"]}

    def rotulo(item: Mapping[str, str]) -> str:
        no = nomes[item["no"]]
        bloco = mb.POR_CHAVE.get(str(no.get("tipo")))
        return f"{bloco.nome if bloco else no.get('nome')}: {item['rotulo']}"

    op_e = {f"{i['no']}|{i['porta']}": rotulo(i) for i in entradas}
    op_s = {f"{i['no']}|{i['porta']}": rotulo(i) for i in saidas}
    chave_e = f"{p.prefixo}_pub_e_{id_local}"
    chave_s = f"{p.prefixo}_pub_s_{id_local}"
    estado[chave_e] = [
        f"{x['no']}|{x['porta']}"
        for x in bruto["portas"]["entradas"]
        if f"{x['no']}|{x['porta']}" in op_e
    ]
    estado[chave_s] = [
        f"{x['no']}|{x['porta']}"
        for x in bruto["portas"]["saidas"]
        if f"{x['no']}|{x['porta']}" in op_s
    ]

    def aplicar() -> None:
        pares = [tuple(x.split("|", 1)) for x in estado[chave_e]]
        saem = [tuple(x.split("|", 1)) for x in estado[chave_s]]
        _trocar_grafo(p, mc.definir_portas(estado[p.k("grafo")], id_local, pares, saem, caminho))

    st.multiselect(
        "Entradas públicas",
        list(op_e),
        key=chave_e,
        format_func=lambda c: op_e[c],
        on_change=aplicar,
        help="O que pode ser ligado por fora do conjunto.",
    )
    st.multiselect(
        "Saídas públicas",
        list(op_s),
        key=chave_s,
        format_func=lambda c: op_s[c],
        on_change=aplicar,
        help="O que sai do conjunto para os outros blocos.",
    )


def _dados_do_fio(dados_fio: mt.Transportado, u: Unidades) -> str:
    """Uma coluna vira linhas de rótulo e valor. Mais de uma, tabela."""

    def com_unidade(numero: float | None, dimensao: str) -> str:
        if numero is None:
            return "—"
        return f"{_numero(numero / u.fator(dimensao))} {u.rotulo(dimensao)}".strip()

    texto = _linhas([(r, com_unidade(n, d)) for r, n, d in dados_fio.esforcos])
    if len(dados_fio.colunas) == 1:
        titulo, dimensao = dados_fio.colunas[0]
        return texto + _linhas(
            [(rotulo or titulo, com_unidade(ns[0], dimensao)) for rotulo, ns in dados_fio.linhas]
        )
    if not dados_fio.linhas:
        return texto
    cabeca = "<th></th>"
    for titulo, dimensao in dados_fio.colunas:
        rotulo = u.rotulo(dimensao)
        cabeca += f"<th>{_e(f'{titulo} ({rotulo})' if rotulo else titulo)}</th>"
    corpo = ""
    for rotulo, numeros in dados_fio.linhas:
        corpo += f"<tr><td>{_e(rotulo)}</td>"
        for (_, dimensao), numero in zip(dados_fio.colunas, numeros, strict=True):
            valor = "—" if numero is None else _numero(numero / u.fator(dimensao))
            corpo += f"<td>{_e(valor)}</td>"
        corpo += "</tr>"
    return f'{texto}<table class="mi-tabela"><tr>{cabeca}</tr>{corpo}</table>'


def _ao_inserir_no_fio(p: Parte, selecao: Mapping[str, Any], campo: str) -> None:
    estado = st.session_state
    caminho = list(selecao.get("caminho") or ())
    try:
        novo, id_novo = mc.inserir_no_fio(estado[p.k("grafo")], selecao, estado[campo], caminho)
    except mc.ErroDeConjunto as erro:
        estado[p.k("erro_conjunto")] = str(erro)
        return
    estado[p.k("erro_conjunto")] = ""
    _trocar_grafo(p, novo)
    estado[p.k("modelo_atual")] = None
    _selecionar(p, {"tipo": "no", "id": "/".join([*caminho, id_novo])})


def _ao_tirar_fio(p: Parte, selecao: Mapping[str, Any]) -> None:
    estado = st.session_state
    caminho = list(selecao.get("caminho") or ())
    _trocar_grafo(p, mc.tirar_fio(estado[p.k("grafo")], selecao, caminho))
    estado[p.k("modelo_atual")] = None
    _selecionar(p, None)


def _acoes_do_fio(p: Parte, selecao: Mapping[str, Any]) -> None:
    estado = st.session_state
    caminho = list(selecao.get("caminho") or ())
    todas = mc.compativeis(estado[p.k("grafo")], selecao, p.dominio, caminho)
    fora = mus.blocos_escondidos(estado[p.k("grafo")], todas)
    chaves = [chave for chave in todas if chave not in fora]
    if len(fora) == 1:
        st.caption(
            "1 bloco que cabe nesta ligação não serve nesta montagem e fica de fora. "
            '"Mostrar todos", na biblioteca, traz ele de volta.'
        )
    elif fora:
        st.caption(
            f"{len(fora)} blocos que cabem nesta ligação não servem nesta montagem e ficam de "
            'fora. "Mostrar todos", na biblioteca, traz eles de volta.'
        )
    if chaves:
        campo = p.k("inserir_bloco")
        if estado.get(campo) not in chaves:
            estado[campo] = chaves[0]
        st.selectbox(
            "Bloco compatível",
            chaves,
            key=campo,
            format_func=lambda c: mb.POR_CHAVE[c].nome,
            help="Só aparecem os blocos que recebem e devolvem o que passa nesta ligação.",
        )
        st.button(
            "Inserir bloco nesta ligação",
            key=p.k("inserir"),
            type="primary",
            on_click=_ao_inserir_no_fio,
            args=(p, dict(selecao), campo),
            help="A ligação vira origem → novo bloco → destino, e o resto fica onde está.",
            width="stretch",
        )
    st.button(
        "Desfazer esta ligação",
        key=p.k("tirar_fio"),
        on_click=_ao_tirar_fio,
        args=(p, dict(selecao)),
        help="Apaga só este fio. Ctrl+Z na prancheta traz de volta.",
        width="stretch",
    )


def _inspetor_fio(
    p: Parte,
    selecao: Mapping[str, Any],
    dados: Mapping[str, Any],
    base: mt.Montagem,
    resposta: mt.Resposta | None,
    u: Unidades,
) -> None:
    caminho = list(selecao.get("caminho") or ())
    atual = mc.nivel(dict(dados), caminho)
    por_id = {n.get("id"): n for n in atual["nos"]}
    no_id, porta = mt.resolver_saida(dados, selecao)
    valor = base.saidas.get(no_id, {}).get(porta)
    bloco = next((n for n in base.grafo.nos if n.id == no_id), None)
    definicao = (
        next(
            (x for x in mb.portas_de(bloco.tipo, dict(bloco.opcoes))[1] if x.chave == porta),
            None,
        )
        if bloco
        else None
    )
    dimensao = dict(bloco.opcoes).get("dimensao") if bloco and bloco.tipo == mb.REFERENCIA else None
    dimensao = dimensao or (definicao.dimensao if definicao else None)
    dados_fio = mt.transportado(valor, _numeros_da_conta(p, resposta), dimensao)
    _topo_do_inspetor(
        "Conexão",
        f"{_nome_do_no(por_id.get(selecao.get('de')))} → "
        f"{_nome_do_no(por_id.get(selecao.get('para')))}",
        f"Saída {definicao.rotulo}" if definicao else "",
        dados_fio.objeto if dados_fio is not None else "Condições",
    )
    _titulo_de_secao("Dados transportados")
    if dados_fio is None:
        usos = {x.nome: x.uso for x in resposta.conferencia} if resposta is not None else {}
        pares = [
            (c.nome, f"{_numero(usos[c.nome] * 100.0)} %" if c.nome in usos else "—")
            for c in valor or ()
        ]
        st.html(_linhas(pares) or '<div class="mi-sub">Leva as condições até o resultado.</div>')
    else:
        texto = _dados_do_fio(dados_fio, u)
        vazio = '<div class="mi-sub">Ponha um esforço ou um trecho para ter o que levar.</div>'
        st.html(texto or vazio)
    _titulo_de_secao("Verificação automática")
    st.html(_conferidos(mc.conferir_fio(dict(dados), selecao, caminho)))
    _acoes_do_fio(p, selecao)
    if definicao is not None:
        with st.expander("Por que esta conexão é diferente?", icon=":material/help:"):
            st.caption(_PORQUE_DO_FIO[definicao.tipo])


def _ao_escolher_fonte(p: Parte, no_id: str, chave: str, unidade: str | None, u: Unidades) -> None:
    estado = st.session_state
    no = rg.por_id(estado[p.k("grafo")]["nos"], no_id)
    if no is None:
        return
    fontes = {
        f"{f.registro_id}|{f.campo}": f
        for f in rg.fontes_do_projeto(projeto_ativo_persistente(), p.dominio, u)
    }
    fonte = fontes.get(estado.get(chave))
    if fonte is None:
        return
    dimensao, fator = None, None
    if fonte.dimensao is None:
        tabela = rg.unidades_conhecidas(u)
        dimensao, fator = tabela.get(estado.get(unidade or "") or "", (None, None))
    no["opcoes"] = rg.opcoes_da_fonte(fonte, dimensao, fator)
    estado[p.k("versao")] += 1
    estado[p.k("modelo_atual")] = None


def _inspetor_referencia(
    p: Parte, no: mt.No, u: Unidades, diagnosticos: Sequence[rg.Diagnostico]
) -> None:
    estado = st.session_state
    projeto = projeto_ativo_persistente()
    fontes = rg.fontes_do_projeto(projeto, p.dominio, u)
    if not fontes:
        st.info(
            "O projeto ativo ainda não tem cálculo registrado com resultado numérico.",
            icon=":material/info:",
        )
        return
    por_chave = {f"{f.registro_id}|{f.campo}": f for f in fontes}
    opcoes = dict(no.opcoes)
    atual = f"{opcoes.get('registro')}|{opcoes.get('campo')}"
    chave = f"{p.prefixo}_ref_{no.id}"
    unidade = f"{p.prefixo}_refu_{no.id}"
    estado[chave] = atual if atual in por_chave else next(iter(por_chave))
    st.selectbox(
        "Resultado",
        list(por_chave),
        key=chave,
        format_func=lambda c: (
            f"{por_chave[c].registro_titulo}: {por_chave[c].rotulo} = {_numero(por_chave[c].valor)}"
        ),
        on_change=_ao_escolher_fonte,
        args=(p, no.id, chave, unidade, u),
        help="Cada resultado aponta para o registro pelo id e pela assinatura, e não pelo nome.",
    )
    fonte = por_chave[estado[chave]]
    if fonte.dimensao is None:
        tabela = rg.unidades_conhecidas(u)
        st.selectbox(
            "Unidade deste resultado",
            list(tabela),
            key=unidade,
            on_change=_ao_escolher_fonte,
            args=(p, no.id, chave, unidade, u),
            help="O registro não diz a unidade. Ela decide em qual porta o fio pode ligar.",
        )
    if not opcoes.get("registro"):
        st.button(
            "Usar este resultado",
            key=f"{p.prefixo}_usar_{no.id}",
            on_click=_ao_escolher_fonte,
            args=(p, no.id, chave, unidade, u),
            help="Guarda o valor e a assinatura do registro neste bloco.",
            width="stretch",
        )
    diagnostico = next((d for d in diagnosticos if d.no == no.id), None)
    if diagnostico is not None:
        icone = (
            ":material/check_circle:" if diagnostico.situacao == rg.EM_DIA else ":material/warning:"
        )
        (st.caption if diagnostico.situacao == rg.EM_DIA else st.warning)(
            diagnostico.mensagem, **({} if diagnostico.situacao == rg.EM_DIA else {"icon": icone})
        )
        if diagnostico.situacao == rg.DESATUALIZADA and diagnostico.fonte is not None:
            st.button(
                "Atualizar a referência",
                key=f"{p.prefixo}_atualizar_{no.id}",
                on_click=_ao_escolher_fonte,
                args=(p, no.id, chave, unidade, u),
                help="Passa a usar o valor novo do registro.",
                width="stretch",
            )


def _inspetor(
    p: Parte,
    dados: Mapping[str, Any],
    grafo: mt.Grafo,
    base: mt.Montagem,
    resposta: mt.Resposta | None,
    alvo: str | None,
    u: Unidades,
    diagnosticos: Sequence[rg.Diagnostico],
) -> None:
    selecao = st.session_state.get(p.k("selecao"))
    if selecao and selecao.get("tipo") == "fio":
        if mc.fio_existe(dict(dados), selecao, list(selecao.get("caminho") or ())):
            _inspetor_fio(p, selecao, dados, base, resposta, u)
            return
    if selecao and selecao.get("tipo") == "no":
        id_ = str(selecao.get("id"))
        bruto = rg.por_id(dados["nos"], id_)
        if bruto is not None and bruto.get("tipo") == mt.CONJUNTO:
            _inspetor_conjunto(p, dict(bruto), id_, base, alvo, u)
            return
        no = next((n for n in grafo.nos if n.id == id_), None)
        if no is not None:
            _inspetor_bloco(p, no, dados, base, resposta, alvo, u, diagnosticos)
            return
    _inspetor_geral(p, grafo, base, alvo, u)


# ---------------------------------------------------------------------------
# Resposta
# ---------------------------------------------------------------------------


def _ao_escolher_alvo(p: Parte) -> None:
    estado = st.session_state
    estado[p.k("alvo")] = estado[p.k("alvo_escolha")]
    estado[p.k("adotado")] = None
    estado[p.k("revisao")] += 1


def _ao_digitar_adotado(p: Parte, campo: str, fator: float) -> None:
    estado = st.session_state
    if not _da_rodada_atual(p, campo):
        return
    valor = estado.get(campo)
    estado[p.k("adotado")] = None if valor is None else float(valor) * fator


def _escolher_alvo(p: Parte, montagem: mt.Montagem, alvo: str, u: Unidades) -> None:
    estado = st.session_state
    por_chave = {item.chave: item for item in _opcoes_de_alvo(montagem)}
    estado[p.k("alvo_escolha")] = alvo
    esquerda, direita = st.columns([2, 1])
    esquerda.selectbox(
        "Deixar em função de",
        list(por_chave),
        key=p.k("alvo_escolha"),
        on_change=_ao_escolher_alvo,
        args=(p,),
        format_func=lambda c: f"{por_chave[c].texto}: {por_chave[c].nome}",
        help="A letra que vai ficar sozinha de um lado da equação: a medida, a carga ou o material.",
    )
    grandeza = por_chave[alvo]
    fator = u.fator(grandeza.dimensao)
    rotulo = u.rotulo(grandeza.dimensao)
    campo = f"{p.prefixo}_adotado_{estado[p.k('revisao')]}"
    guardado = estado.get(p.k("adotado"))
    if campo not in estado:
        estado[campo] = _para_o_campo(guardado, fator)
    direita.number_input(
        f"Valor adotado ({rotulo})" if rotulo else "Valor adotado",
        value=None,
        format="%g",
        step=None,
        key=campo,
        on_change=_ao_digitar_adotado,
        args=(p, campo, fator),
        placeholder="opcional",
        help="A medida que você vai usar de verdade: mostra o uso de cada condição com ela.",
    )


def _botao_rastrear(p: Parte, grafo: mt.Grafo) -> None:
    no = next((n for n in grafo.nos if n.tipo == mb.RESULTADO), None)
    if no is not None:
        st.button(
            "Rastrear este resultado",
            key=p.k("rastrear"),
            icon=":material/route:",
            on_click=_selecionar,
            args=(p, {"tipo": "no", "id": no.id}),
            help="Acende na prancheta o caminho de quem decide, e o inspetor explica o porquê.",
        )


def _numeros_do_caso_na_formula(resposta: mt.Resposta, u: Unidades) -> None:
    """Na fórmula de um caso a mais, os números próprios dele já entraram: diz quais."""
    conta = resposta.montagem
    if conta is None or resposta.manda is None or not conta.casos:
        return
    caso = resposta.manda.condicao.caso
    proprios = dict(conta.casos).get(caso)
    if not proprios:
        return
    textos = [
        f"{grandeza.texto} = {_com_unidade(valor, grandeza, u)}"
        for chave, valor in proprios
        if (grandeza := conta.grandeza(chave)) is not None
    ]
    st.caption(f"Na fórmula já entraram os números de {caso}: {', '.join(textos)}.")


def _resposta(p: Parte, grafo: mt.Grafo, resposta: mt.Resposta, u: Unidades) -> None:
    letra = _letra(resposta.alvo)
    if resposta.valor is not None and resposta.manda is not None:
        st.success(
            f"**{rg.texto_da_resposta(resposta, u)}**. Quem manda: {resposta.manda.condicao.nome}.",
            icon=":material/check_circle:",
        )
        item = resposta.manda
        if item.formula is not None:
            st.latex(f"{letra} = {item.formula.latex}")
            _numeros_do_caso_na_formula(resposta, u)
        else:
            st.caption(
                "Esta equação não tem forma fechada simples: o número veio da conta numérica."
            )
            st.latex(item.equacao)
        _botao_rastrear(p, grafo)
        return
    nomes = ", ".join(item.texto for item in resposta.faltam)
    if nomes:
        st.info(f"Fórmula em letras. Para sair o número, preencha {nomes}.", icon=":material/info:")
    for item in resposta.isoladas:
        if item.independente:
            continue
        st.markdown(f"**{item.condicao.nome}**")
        if item.formula is not None:
            st.latex(f"{letra} = {item.formula.latex}")
            if item.com_numeros:
                st.latex(f"{letra} = {item.com_numeros}")
        else:
            st.caption("Sem forma fechada simples. Preencha os valores para achar o número.")
            st.latex(item.equacao)
    if resposta.faltam and any(i.com_numeros for i in resposta.isoladas):
        st.caption(p.sistema.aviso_da_base)


def _grafico_da_bomba(resposta: mt.Resposta, valores: Mapping[str, float], u: Unidades) -> None:
    linhas = mt.curvas_da_bomba(resposta, valores)
    if not linhas or resposta.valor is None:
        return
    fator = u.fator(g.VAZAO)
    eixo = f"Q ({u.rotulo(g.VAZAO)})"
    quadro = pd.DataFrame(
        [
            {eixo: q / fator, "Curva": nome, "H (m)": h}
            for q, sistema, bomba in linhas
            for nome, h in (("Sistema", sistema), ("Bomba", bomba))
        ]
    )
    altura = next((x.esquerda for x in resposta.conferencia if x.igualdade), None)
    _titulo_da_pagina("Ponto de operação")
    curvas = (
        alt.Chart(quadro)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X(f"{eixo}:Q", title=eixo),
            y=alt.Y("H (m):Q", title="H (m)"),
            color=alt.Color("Curva:N", legend=alt.Legend(orient="bottom", title=None)),
            tooltip=[
                alt.Tooltip(f"{eixo}:Q", format=".3f"),
                alt.Tooltip("H (m):Q", format=".2f"),
                "Curva:N",
            ],
        )
    )
    camadas = curvas
    if altura is not None:
        ponto = pd.DataFrame([{eixo: resposta.valor / fator, "H (m)": altura}])
        camadas = curvas + alt.Chart(ponto).mark_point(
            size=120, filled=True, color="#172033"
        ).encode(x=f"{eixo}:Q", y="H (m):Q")
        st.caption(
            f"A bomba entrega {_com_unidade(resposta.valor, g.VAZAO_Q, u)} com "
            f"{_numero(altura)} m de altura."
        )
    st.altair_chart(camadas.properties(height=300, autosize=SO_NA_LARGURA), width="stretch")


def _quadro(resposta: mt.Resposta, u: Unidades) -> None:
    linhas = []
    conferidas = {linha.nome: linha for linha in resposta.conferencia}
    adotadas = {linha.nome: linha for linha in resposta.conferencia_adotada}
    for item in resposta.isoladas:
        nome = item.condicao.nome
        conferida = conferidas.get(nome)
        pede = "não depende" if item.independente else "—"
        if item.valor is not None:
            texto = _com_unidade(item.valor, resposta.alvo, u)
            pede = f"{resposta.alvo.texto} {_sinal(item.lado)} {texto}"
        linha: dict[str, Any] = {
            "Condição": nome,
            "Pede": pede,
            "Atua": _numero(conferida.esquerda) if conferida else "—",
            "Limite": _numero(conferida.direita) if conferida else "—",
            "Uso (%)": round(conferida.uso * 100.0, 1) if conferida else None,
        }
        if adotadas:
            adotada = adotadas.get(nome)
            linha["Uso no adotado (%)"] = round(adotada.uso * 100.0, 1) if adotada else None
        linha["Manda"] = "●" if resposta.manda is not None and item is resposta.manda else ""
        linhas.append(linha)
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    st.caption(
        "Atua e Limite são os dois lados de cada condição, com a resposta no lugar da letra "
        f"pedida. {u.sistema.aviso_da_base}"
    )
    if adotadas:
        pior = max(resposta.conferencia_adotada, key=lambda linha: linha.uso)
        texto = _com_unidade(resposta.adotado or 0.0, resposta.alvo, u)
        if pior.uso > 1.0 + 1e-9:
            st.error(
                f"Com {resposta.alvo.texto} = {texto}, {pior.nome} não passa: uso de "
                f"{_numero(pior.uso * 100.0)} %.",
                icon=":material/error:",
            )
        else:
            st.caption(
                f"Com {resposta.alvo.texto} = {texto}, o maior uso é {_numero(pior.uso * 100.0)} %, "
                f"em {pior.nome}."
            )


def _anotar_mudanca(p: Parte, resposta: mt.Resposta, u: Unidades) -> None:
    """Diz o que mudou de uma conta para a outra, e por causa de quê."""
    estado = st.session_state
    atual = {
        "alvo": resposta.alvo.chave,
        "valor": resposta.valor,
        "valores": dict(resposta.valores_usados),
    }
    anterior = estado.get(p.k("ultima"))
    estado[p.k("ultima")] = atual
    if anterior is None or anterior == atual:
        return
    if anterior["alvo"] != atual["alvo"] or not anterior["valor"] or not atual["valor"]:
        estado[p.k("mudanca")] = ""
        return
    mudaram = []
    montagem = resposta.montagem
    for chave in sorted(set(anterior["valores"]) | set(atual["valores"])):
        antes, depois = anterior["valores"].get(chave), atual["valores"].get(chave)
        grandeza = montagem.grandeza(chave) if montagem else None
        if antes != depois and grandeza is not None and antes is not None and depois is not None:
            mudaram.append(
                f"{grandeza.texto} foi de {_com_unidade(antes, grandeza, u)} para "
                f"{_com_unidade(depois, grandeza, u)}"
            )
    if abs(atual["valor"] - anterior["valor"]) <= 1e-9 * abs(anterior["valor"]):
        estado[p.k("mudanca")] = ""
        return
    variacao = (atual["valor"] / anterior["valor"] - 1.0) * 100.0
    sinal = "+" if variacao >= 0 else ""
    texto = (
        f"{resposta.alvo.texto}: {_com_unidade(anterior['valor'], resposta.alvo, u)} → "
        f"{_com_unidade(atual['valor'], resposta.alvo, u)} ({sinal}{_numero(variacao)} %)"
    )
    if mudaram:
        texto += ", porque " + "; ".join(mudaram)
    estado[p.k("mudanca")] = texto + "."


def _variacao_em_texto(fracao: float | None) -> str:
    if fracao is None:
        return "—"
    numero = fracao * 100.0
    if abs(numero) < 0.05:
        return "0 %"
    return f"{'+' if numero > 0 else '−'}{abs(numero):.1f} %".replace(".", ",")


def _pesos(p: Parte, resposta: mt.Resposta) -> list[ms.Peso]:
    """A conta é refeita duas vezes por letra: guarda até a montagem ou um número mudar."""
    estado = st.session_state
    conta = resposta.montagem
    chave = (
        hash(conta.grafo) if conta is not None else 0,
        resposta.alvo.chave,
        tuple(sorted(resposta.valores_usados.items())),
    )
    guardado = estado.get(p.k("pesos"))
    if guardado is not None and guardado[0] == chave:
        return list(guardado[1])
    lista = ms.pesos(resposta)
    estado[p.k("pesos")] = (chave, tuple(lista))
    return lista


def _o_que_mais_pesa(p: Parte, resposta: mt.Resposta, u: Unidades) -> None:
    """Cada número sobe e desce 10 %, e a conta inteira roda de novo."""
    if resposta.valor is None or resposta.faltam:
        return
    lista = _pesos(p, resposta)
    pesam = [peso for peso in lista if not peso.quase_nada]
    if not lista:
        return
    alvo = resposta.alvo.texto
    _titulo_da_pagina("O que mais pesa")
    if pesam:
        primeiro = pesam[0]
        st.markdown(
            f"Pesa mais **{primeiro.grandeza.texto}** ({primeiro.grandeza.nome.lower()}): 10 % a "
            f"mais muda {alvo} em **{_variacao_em_texto(primeiro.sobe)}**."
        )
        linhas = [
            {
                "Letra": f"{peso.grandeza.texto}: {peso.grandeza.nome}",
                "Valor": _com_unidade(peso.valor, peso.grandeza, u),
                f"{alvo} com +10 %": _variacao_em_texto(peso.sobe),
                f"{alvo} com −10 %": _variacao_em_texto(peso.desce),
                "Passa a mandar": peso.manda_depois or "",
            }
            for peso in pesam
        ]
        quadro = pd.DataFrame(linhas)
        if not any(linha["Passa a mandar"] for linha in linhas):
            quadro = quadro.drop(columns="Passa a mandar")
        st.dataframe(quadro, hide_index=True, width="stretch")
    fracos = [peso.grandeza.texto for peso in lista if peso.quase_nada]
    texto = (
        "Cada número sobe e desce 10 %, um de cada vez, e a conta roda de novo. Assim aparece "
        "também quando outra condição passa a mandar."
    )
    if fracos:
        texto += f" Quase não mexem na resposta: {', '.join(fracos)}."
    st.caption(texto)


_CURVAS_NO_GRAFICO = 8


def _grafico_de_uso(resposta: mt.Resposta, valores: Mapping[str, float], u: Unidades) -> None:
    linhas = mt.curvas(resposta, valores)
    if not linhas:
        return
    perto = sorted(resposta.conferencia, key=lambda linha: linha.uso, reverse=True)
    if len(perto) > _CURVAS_NO_GRAFICO:
        # O eixo com trechos tem dezenas de condições: com todas, o gráfico vira um novelo.
        mostradas = {linha.nome for linha in perto[:_CURVAS_NO_GRAFICO]}
        linhas = [linha for linha in linhas if linha[0] in mostradas]
        st.caption(
            f"O gráfico mostra as {_CURVAS_NO_GRAFICO} condições mais perto do limite. As outras "
            "estão no quadro de condições."
        )
    fator = u.fator(resposta.alvo.dimensao)
    rotulo = u.rotulo(resposta.alvo.dimensao)
    eixo = f"{resposta.alvo.texto} ({rotulo})" if rotulo else resposta.alvo.texto
    quadro = pd.DataFrame([{"Condição": n, eixo: x / fator, "Uso": uso} for n, x, uso in linhas])
    grafico = (
        alt.Chart(quadro)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X(f"{eixo}:Q", scale=alt.Scale(zero=False), title=eixo),
            y=alt.Y("Uso:Q", title="Uso do limite (1 é o limite)"),
            color=alt.Color(
                "Condição:N", legend=alt.Legend(orient="bottom", title=None, columns=2)
            ),
        )
    )
    limite = alt.Chart(pd.DataFrame({"y": [1.0]})).mark_rule(strokeDash=[5, 4]).encode(y="y:Q")
    st.altair_chart(
        (grafico + limite).properties(height=300, autosize=SO_NA_LARGURA), width="stretch"
    )


def _grafico_de_varredura(
    p: Parte,
    montagem: mt.Montagem,
    resposta: mt.Resposta,
    valores: Mapping[str, float],
    u: Unidades,
) -> None:
    outras = [
        item
        for item in montagem.grandezas
        if item.chave != resposta.alvo.chave
        and item.chave in montagem.essenciais
        and valores.get(item.chave)
    ]
    if not outras:
        return
    por_chave = {item.chave: item for item in outras}
    escolha = st.selectbox(
        "Ver como a resposta muda com",
        [_NAO_VARRE, *por_chave],
        key=p.k("varrer"),
        format_func=lambda c: (
            c if c == _NAO_VARRE else f"{por_chave[c].texto}: {por_chave[c].nome}"
        ),
        help="Varre a letra de metade até o dobro do valor preenchido e refaz a conta.",
    )
    if escolha == _NAO_VARRE:
        return
    linhas = mt.varrer(montagem, resposta.alvo.chave, valores, escolha)
    if not linhas:
        st.info("Não saiu resposta nessa faixa.", icon=":material/info:")
        return
    outra = por_chave[escolha]
    fator_x = u.fator(outra.dimensao)
    fator_y = u.fator(resposta.alvo.dimensao)
    titulo_x = f"{outra.texto} ({u.rotulo(outra.dimensao)})"
    titulo_y = f"{resposta.alvo.texto} ({u.rotulo(resposta.alvo.dimensao)})"
    quadro = pd.DataFrame([{titulo_x: x / fator_x, titulo_y: y / fator_y} for x, y in linhas])
    st.altair_chart(
        alt.Chart(quadro)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X(f"{titulo_x}:Q", scale=alt.Scale(zero=False), title=titulo_x),
            y=alt.Y(f"{titulo_y}:Q", scale=alt.Scale(zero=False), title=titulo_y),
        )
        .properties(height=280),
        width="stretch",
    )


def _arredondar(valor: float) -> float:
    return float(f"{valor:.3g}")


def _campos_da_faixa(p: Parte, grandeza: Grandeza, centro: float, u: Unidades) -> bs.Faixa:
    """De, até e passo de uma incógnita, na unidade da tela. A busca recebe na base."""
    estado = st.session_state
    fator = u.fator(grandeza.dimensao)
    rotulo = u.rotulo(grandeza.dimensao)
    sufixo = f" ({rotulo})" if rotulo else ""
    de_padrao = _arredondar(centro / 4.0 / fator)
    ate_padrao = _arredondar(centro * 3.0 / fator)
    passo_padrao = _arredondar((ate_padrao - de_padrao) / _DIVISOES)
    revisao = estado[p.k("revisao")]
    colunas = st.columns(3)
    de = colunas[0].number_input(
        f"{grandeza.texto}: de{sufixo}",
        value=de_padrao,
        format="%g",
        step=None,
        key=f"{p.prefixo}_de_{revisao}_{grandeza.chave}",
        help="O menor valor que a busca testa.",
    )
    ate = colunas[1].number_input(
        f"{grandeza.texto}: até{sufixo}",
        value=ate_padrao,
        format="%g",
        step=None,
        key=f"{p.prefixo}_ate_{revisao}_{grandeza.chave}",
        help="O maior valor que a busca testa.",
    )
    passo = colunas[2].number_input(
        f"{grandeza.texto}: passo{sufixo}",
        value=passo_padrao,
        format="%g",
        step=None,
        key=f"{p.prefixo}_passo_{revisao}_{grandeza.chave}",
        help="A distância entre dois valores da grade. Use a medida comercial, como 5 mm.",
    )
    return bs.Faixa(grandeza.chave, de * fator, ate * fator, passo * fator)


def _texto_do_candidato(candidato: bs.Candidato, montagem: mt.Montagem, u: Unidades) -> str:
    partes = []
    for chave, valor in candidato.valores:
        grandeza = montagem.grandeza(chave)
        if grandeza is not None:
            partes.append(f"{grandeza.texto} = {_com_unidade(valor, grandeza, u)}")
    return " · ".join(partes)


def _mapa_da_busca(busca: bs.Busca, montagem: mt.Montagem, u: Unidades) -> None:
    """Uso em cor: verde passa, vermelho não passa, e a fronteira é o limite."""
    if not busca.mapa or busca.convergido is None:
        return
    primeira = montagem.grandeza(busca.faixas[0].chave)
    if primeira is None:
        return
    fator_x = u.fator(primeira.dimensao)
    rotulo_x = u.rotulo(primeira.dimensao)
    titulo_x = f"{primeira.texto} ({rotulo_x})" if rotulo_x else primeira.texto
    if len(busca.faixas) == 1:
        quadro = pd.DataFrame(
            [{titulo_x: x / fator_x, "Uso": min(uso, 3.0)} for x, uso in busca.mapa]
        )
        grafico = (
            alt.Chart(quadro)
            .mark_line(strokeWidth=2)
            .encode(
                x=alt.X(f"{titulo_x}:Q", title=titulo_x),
                y=alt.Y("Uso:Q", title="Uso do limite (1 é o limite)"),
            )
        )
        limite = alt.Chart(pd.DataFrame({"y": [1.0]})).mark_rule(strokeDash=[5, 4]).encode(y="y:Q")
        st.altair_chart((grafico + limite).properties(height=280), width="stretch")
        return
    segunda = montagem.grandeza(busca.faixas[1].chave)
    if segunda is None:
        return
    fator_y = u.fator(segunda.dimensao)
    rotulo_y = u.rotulo(segunda.dimensao)
    titulo_y = f"{segunda.texto} ({rotulo_y})" if rotulo_y else segunda.texto
    xs = sorted({linha[0] for linha in busca.mapa})
    ys = sorted({linha[1] for linha in busca.mapa})
    dx = (xs[1] - xs[0]) / fator_x if len(xs) > 1 else 1.0
    dy = (ys[1] - ys[0]) / fator_y if len(ys) > 1 else 1.0
    quadro = pd.DataFrame(
        [
            {
                "x": x / fator_x - dx / 2.0,
                "x2": x / fator_x + dx / 2.0,
                "y": y / fator_y - dy / 2.0,
                "y2": y / fator_y + dy / 2.0,
                "Uso": uso,
            }
            for x, y, uso in busca.mapa
        ]
    )
    mapa = (
        alt.Chart(quadro)
        .mark_rect()
        .encode(
            x=alt.X("x:Q", title=titulo_x, scale=alt.Scale(zero=False, nice=False)),
            x2="x2:Q",
            y=alt.Y("y:Q", title=titulo_y, scale=alt.Scale(zero=False, nice=False)),
            y2="y2:Q",
            color=alt.Color(
                "Uso:Q",
                title="Uso",
                scale=alt.Scale(
                    domain=[0.0, 1.0, 2.0],
                    range=["#16836f", "#e8eaee", "#c2415d"],
                    clamp=True,
                ),
            ),
            tooltip=[alt.Tooltip("Uso:Q", format=".2f")],
        )
    )
    final = busca.convergido
    ponto = (
        alt.Chart(
            pd.DataFrame(
                [
                    {
                        "x": final.valor(busca.faixas[0].chave) / fator_x,
                        "y": final.valor(busca.faixas[1].chave) / fator_y,
                    }
                ]
            )
        )
        .mark_point(shape="cross", size=220, filled=True, color="#172033")
        .encode(x="x:Q", y="y:Q")
    )
    st.altair_chart((mapa + ponto).properties(height=340), width="stretch")
    if len(busca.faixas) > 2:
        terceira = montagem.grandeza(busca.faixas[2].chave)
        if terceira is not None:
            valor = final.valor(terceira.chave)
            st.caption(f"Mapa com {terceira.texto} = {_com_unidade(valor, terceira, u)}.")


def _quadro_da_grade(busca: bs.Busca, montagem: mt.Montagem, u: Unidades) -> None:
    linhas = []
    for candidato in busca.melhores_da_grade:
        linha: dict[str, Any] = {}
        for chave, valor in candidato.valores:
            grandeza = montagem.grandeza(chave)
            if grandeza is not None:
                rotulo = u.rotulo(grandeza.dimensao)
                titulo = f"{grandeza.texto} ({rotulo})" if rotulo else grandeza.texto
                linha[titulo] = round(valor / u.fator(grandeza.dimensao), 4)
        linha["Uso (%)"] = round(candidato.uso * 100.0, 1)
        if candidato.area is not None:
            linha["Área (mm²)"] = round(candidato.area, 1)
        linha["Manda"] = candidato.manda
        linhas.append(linha)
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")


def _busca_em_faixas(
    p: Parte, montagem: mt.Montagem, alvo: str, resposta: mt.Resposta | None, u: Unidades
) -> None:
    estado = st.session_state
    ligada = st.toggle(
        "Procurar em faixas, com várias incógnitas",
        key=p.k("busca_ligada"),
        help="Deixa até três letras em aberto: o programa testa as faixas e aperta até convergir.",
    )
    if not ligada:
        return
    por_chave = {item.chave: item for item in _opcoes_de_alvo(montagem)}
    letras = p.k("busca_letras")
    if letras not in estado or not set(estado[letras]) <= set(por_chave):
        estado[letras] = [alvo]
    escolhidas = st.multiselect(
        "Incógnitas",
        list(por_chave),
        key=letras,
        max_selections=_MAX_INCOGNITAS,
        format_func=lambda c: f"{por_chave[c].texto}: {por_chave[c].nome}",
        help="Até três letras. As outras usam os valores preenchidos acima.",
    )
    if not escolhidas:
        st.info("Escolha ao menos uma incógnita.", icon=":material/info:")
        return
    faixas = []
    for chave in escolhidas:
        grandeza = por_chave[chave]
        centro = estado[p.k("valores")].get(chave)
        if centro is None and resposta is not None and chave == alvo:
            centro = resposta.valor
        if not centro:
            centro = _CENTRO_DA_FAIXA.get(grandeza.dimensao, 1.0)
        faixas.append(_campos_da_faixa(p, grandeza, float(centro), u))
    lista = bs.objetivos(montagem, escolhidas)
    rotulos = {o.rotulo: o for o in lista}
    objetivo = p.k("busca_objetivo")
    if estado.get(objetivo) not in rotulos:
        estado[objetivo] = lista[0].rotulo
    escolha = st.selectbox(
        "Procurar",
        list(rotulos),
        key=objetivo,
        help="Com mais incógnitas que condições há infinitas respostas: aqui se diz qual delas.",
    )
    valores = {
        k: v for k, v in estado[p.k("valores")].items() if k not in escolhidas and v is not None
    }
    try:
        busca = bs.procurar(montagem, faixas, rotulos[escolha], valores)
    except bs.ErroDeBusca as erro:
        st.warning(str(erro), icon=":material/warning:")
        return
    testadas = f"{busca.testadas:,}".replace(",", ".")
    aprovadas = f"{busca.aprovadas:,}".replace(",", ".")
    st.caption(f"Testou {testadas} combinações na grade, e {aprovadas} passaram.")
    final = busca.convergido
    if final is not None:
        area = f" Área: {_numero(final.area)} mm²." if final.area else ""
        st.success(
            f"**Ponto de convergência: {_texto_do_candidato(final, montagem, u)}**. Uso de "
            f"{_numero(final.uso * 100.0)} %, e manda {final.manda}.{area}",
            icon=":material/check_circle:",
        )
    for chave in busca.na_borda:
        st.warning(
            f"{por_chave[chave].texto} encostou na borda da faixa: ampliando a faixa, a resposta "
            "pode melhorar.",
            icon=":material/warning:",
        )
    for alerta in busca.alertas:
        st.warning(alerta, icon=":material/warning:")
    if busca.melhores_da_grade:
        st.markdown("**Melhores da grade**, com o passo que você pediu")
        _quadro_da_grade(busca, montagem, u)
    _mapa_da_busca(busca, montagem, u)
    if busca.rodadas:
        with st.expander("Como convergiu", icon=":material/timeline:"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Rodada": r.numero,
                            "Largura da busca (%)": round(r.meia_largura * 100.0, 5),
                            "Uso (%)": round(r.uso * 100.0, 2),
                            "Área (mm²)": None if r.area is None else round(r.area, 2),
                        }
                        for r in busca.rodadas
                    ]
                ),
                hide_index=True,
                width="stretch",
            )


def _ao_usar_do_catalogo(
    p: Parte, campo: str, pecas: Mapping[str, cat.Peca], alvo: str | None
) -> None:
    estado = st.session_state
    peca = pecas.get(estado.get(campo) or "")
    if peca is None:
        return
    for chave, valor in peca.valores:
        if chave == alvo:
            estado[p.k("adotado")] = valor
        else:
            estado[p.k("valores")][chave] = valor
            estado[p.k("origens")][chave] = f"Catálogo: {peca.nome}"
    estado[p.k("revisao")] += 1


def _quadro_do_catalogo(escolha: cat.Escolha) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Peça": linha.peca.nome,
                "Massa (kg/m)": linha.peca.massa,
                "Uso (%)": round(linha.uso * 100.0, 1),
                "Manda": linha.manda,
                "Situação": "Passa" if linha.passa else "Não passa",
            }
            for linha in escolha.linhas[:_LINHAS_DO_CATALOGO]
        ]
    )


def _escolher_do_catalogo(p: Parte, montagem: mt.Montagem, alvo: str | None) -> None:
    fontes = cat.fontes(montagem)
    if not fontes:
        return
    estado = st.session_state
    ligada = st.toggle(
        "Escolher do catálogo",
        key=p.k("catalogo_ligado"),
        help="Testa cada perfil, barra ou tubo comercial e diz o mais leve que passa.",
    )
    if not ligada:
        return
    por_no = {f.no: f for f in fontes}
    no_escolhido = p.k("catalogo_no")
    if estado.get(no_escolhido) not in por_no:
        estado[no_escolhido] = fontes[0].no
    if len(fontes) > 1:
        st.selectbox(
            "Qual bloco",
            list(por_no),
            key=no_escolhido,
            format_func=lambda id_: f"{por_no[id_].rotulo} ({id_})",
            help="O bloco cuja medida vem do catálogo.",
        )
    fonte = por_no[estado[no_escolhido]]
    campo_familias = p.k(f"catalogo_familias_{fonte.no}")
    if campo_familias not in estado:
        estado[campo_familias] = list(fonte.familias)
    familias = fonte.familias
    if len(familias) > 1:
        familias = tuple(
            st.multiselect(
                "Famílias",
                list(fonte.familias),
                key=campo_familias,
                help="Tire as famílias que não servem para esta obra.",
            )
        )
    try:
        escolha = cat.testar(montagem, fonte, estado[p.k("valores")], familias)
    except cat.ErroDoCatalogo as erro:
        st.info(str(erro), icon=":material/info:")
        return
    st.caption(f"Testou {escolha.testadas} peças, e {escolha.aprovadas} passaram.")
    melhor = escolha.melhor
    if melhor is None:
        pior = escolha.linhas[0]
        st.warning(
            f"Nenhuma peça passa. A que chega mais perto é {pior.peca.nome}, com uso de "
            f"{_numero(pior.uso * 100.0)} %.",
            icon=":material/warning:",
        )
    else:
        peso = f" Pesa {_numero(melhor.peca.massa)} kg/m." if melhor.peca.massa else ""
        st.success(
            f"**A mais leve que passa: {melhor.peca.nome}**. Uso de "
            f"{_numero(melhor.uso * 100.0)} %, e manda {melhor.manda}.{peso}",
            icon=":material/check_circle:",
        )
    st.dataframe(_quadro_do_catalogo(escolha), hide_index=True, width="stretch")
    boas = {linha.peca.nome: linha.peca for linha in escolha.linhas if linha.passa}
    if boas:
        campo = p.k("catalogo_peca")
        if estado.get(campo) not in boas:
            estado[campo] = next(iter(boas))
        esquerda, direita = st.columns([3, 1], vertical_alignment="bottom")
        esquerda.selectbox(
            "Peça para usar",
            list(boas),
            key=campo,
            help="Vem na ordem da mais leve para a mais pesada.",
        )
        direita.button(
            "Usar esta peça",
            key=p.k("catalogo_usar"),
            on_click=_ao_usar_do_catalogo,
            args=(p, campo, boas, alvo),
            help="Preenche as medidas com as da peça. Voltar desfaz.",
            width="stretch",
        )


# ---------------------------------------------------------------------------
# Comparar duas montagens
# ---------------------------------------------------------------------------


def _guardar_como_a(p: Parte) -> None:
    st.session_state[p.k("comparar_a")] = {
        "foto": _instantaneo(p),
        "hora": time.strftime("%H:%M"),
    }


def _voltar_para_a(p: Parte) -> None:
    """Põe A na prancheta. Entra no histórico como qualquer mudança: Ctrl+Z desfaz."""
    estado = st.session_state
    a = estado.get(p.k("comparar_a"))
    if not a:
        return
    _restaurar(p, a["foto"], estado.get(p.k("versao"), 0))
    estado[p.k("ajuste")] = estado.get(p.k("ajuste"), 0) + 1
    estado[p.k("selecao")] = None


def _esquecer_a(p: Parte) -> None:
    st.session_state.pop(p.k("comparar_a"), None)
    st.session_state.pop(p.k("comparar_a_conta"), None)


def _conta_da_foto(p: Parte, foto: Mapping[str, Any]) -> tuple[mt.Montagem, mt.Resposta | None]:
    """A conta de A, guardada enquanto A não muda: a página roda a cada clique."""
    estado = st.session_state
    marca = json.dumps(foto, sort_keys=True, default=str)
    guardada = estado.get(p.k("comparar_a_conta"))
    if guardada and guardada[0] == marca:
        return guardada[1], guardada[2]
    base = mt.montar(mt.grafo_de_dados(foto["grafo"]))
    resposta = None
    alvo = foto.get("alvo")
    if alvo and base.condicoes and alvo in {x.chave for x in _opcoes_de_alvo(base)}:
        try:
            conta = base
            caso_base, casos = mcs.para_a_conta(foto.get("casos"))
            if casos:
                conta, _ = mt.com_casos(base, foto["valores"], alvo, caso_base, casos)
            resposta = mt.isolar(conta, alvo, foto["valores"], foto.get("adotado"))
        except ValueError:
            resposta = None
    estado[p.k("comparar_a_conta")] = (marca, base, resposta)
    return base, resposta


def _variacao(antes: float | None, depois: float | None) -> str:
    if antes is None or depois is None or antes == 0.0:
        return ""
    porcento = (depois / antes - 1.0) * 100.0
    if abs(porcento) < 0.05:
        return "igual"
    return f"{'+' if porcento > 0 else ''}{_numero(porcento)} %"


def _usos(resposta: mt.Resposta | None) -> dict[str, float]:
    if resposta is None:
        return {}
    linhas = resposta.conferencia_adotada or resposta.conferencia
    return {x.nome: x.uso for x in linhas if not x.igualdade}


def _area_da_secao(base: mt.Montagem, numeros: Mapping[sp.Symbol, sp.Float]) -> float | None:
    return mt.numero_de(base.area, numeros) if base.area is not None else None


def _texto_da_area(area: float | None, u: Unidades) -> str:
    if area is None:
        return "—"
    return f"{_numero(area / u.fator(g.AREA))} {u.rotulo(g.AREA)}".strip()


def _nomes_dos_blocos(dados: Mapping[str, Any]) -> Counter[str]:
    return Counter(
        _nome_do_no(no) for no in mh.blocos(dados).values() if no.get("tipo") != mt.CONJUNTO
    )


def _linhas_da_comparacao(
    a: tuple[mt.Montagem, mt.Resposta | None, Mapping[str, Any]],
    b: tuple[mt.Montagem, mt.Resposta | None, Mapping[str, Any]],
    u: Unidades,
) -> list[dict[str, str]]:
    """A × agora: a resposta, quem manda, o uso de cada condição, a área e o que mudou."""
    (base_a, resp_a, foto_a), (base_b, resp_b, foto_b) = a, b
    linhas: list[dict[str, str]] = []

    def linha(rotulo: str, de_a: str, de_b: str, diferenca: str = "") -> None:
        linhas.append({"": rotulo, "A": de_a, "Agora": de_b, "Diferença": diferenca})

    def resposta(r: mt.Resposta | None) -> str:
        return rg.texto_da_resposta(r, u) if r is not None else "sem resposta"

    mesma_letra = resp_a is not None and resp_b is not None and resp_a.alvo == resp_b.alvo
    linha(
        "Resposta",
        resposta(resp_a),
        resposta(resp_b),
        _variacao(resp_a.valor, resp_b.valor) if mesma_letra and resp_a and resp_b else "",
    )
    manda_a = resp_a.manda.condicao.nome if resp_a and resp_a.manda else "—"
    manda_b = resp_b.manda.condicao.nome if resp_b and resp_b.manda else "—"
    linha("Quem manda", manda_a, manda_b)
    usos_a, usos_b = _usos(resp_a), _usos(resp_b)
    for nome in dict.fromkeys([*usos_b, *usos_a]):
        uso_a, uso_b = usos_a.get(nome), usos_b.get(nome)
        diferenca = ""
        if uso_a is not None and uso_b is not None and abs(uso_b - uso_a) >= 5e-4:
            pontos = (uso_b - uso_a) * 100.0
            diferenca = f"{'+' if pontos > 0 else ''}{_numero(pontos)} p.p."
        linha(
            f"Uso: {nome}",
            "—" if uso_a is None else f"{_numero(uso_a * 100.0)} %",
            "—" if uso_b is None else f"{_numero(uso_b * 100.0)} %",
            diferenca,
        )
    area_a = _area_da_secao(base_a, _numeros_de(foto_a["valores"], resp_a))
    area_b = _area_da_secao(base_b, _numeros_de(foto_b["valores"], resp_b))
    if area_a is not None or area_b is not None:
        linha(
            "Área da seção",
            _texto_da_area(area_a, u),
            _texto_da_area(area_b, u),
            _variacao(area_a, area_b),
        )
    pedidas = {foto_a.get("alvo"), foto_b.get("alvo")}
    grandezas = {x.chave: x for x in (*base_a.grandezas, *base_b.grandezas)}
    for chave, grandeza in grandezas.items():
        if chave in pedidas:
            continue
        de_a, de_b = foto_a["valores"].get(chave), foto_b["valores"].get(chave)
        presente_a, presente_b = base_a.grandeza(chave), base_b.grandeza(chave)
        if presente_a and presente_b and de_a == de_b:
            continue
        linha(
            grandeza.texto,
            _com_unidade(de_a, grandeza, u) if presente_a and de_a is not None else "—",
            _com_unidade(de_b, grandeza, u) if presente_b and de_b is not None else "—",
            _variacao(de_a, de_b) if presente_a and presente_b else "",
        )
    nomes_a, nomes_b = _nomes_dos_blocos(foto_a["grafo"]), _nomes_dos_blocos(foto_b["grafo"])
    so_a, so_b = nomes_a - nomes_b, nomes_b - nomes_a
    if so_a:
        linha("Blocos só em A", ", ".join(sorted(so_a.elements())), "—")
    if so_b:
        linha("Blocos só na de agora", "—", ", ".join(sorted(so_b.elements())))
    return linhas


def _comparar(p: Parte, base: mt.Montagem, resposta: mt.Resposta | None, u: Unidades) -> None:
    estado = st.session_state
    _titulo_da_pagina("Comparar duas montagens")
    a = estado.get(p.k("comparar_a"))
    if not a:
        st.caption(
            "Guarde a montagem de agora como A, mude o que quiser na prancheta, e veja as duas "
            "lado a lado: "
            + (
                "aço ou alumínio, uma seção ou outra, com cortante ou sem."
                if p.dominio == mb.SOLIDOS
                else "um diâmetro ou outro, água ou óleo, com as perdas localizadas ou sem."
            )
        )
        st.button(
            "Guardar como A",
            key=p.k("guardar_a"),
            on_click=_guardar_como_a,
            args=(p,),
            icon=":material/bookmark_add:",
            help="Guarda os blocos e os números de agora. Depois é só mudar e comparar.",
        )
        return
    agora = _instantaneo(p)
    base_a, resposta_a = _conta_da_foto(p, a["foto"])
    linhas = _linhas_da_comparacao((base_a, resposta_a, a["foto"]), (base, resposta, agora), u)
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    if a["foto"] == agora:
        st.caption(
            f"A foi guardada às {a['hora']} e ainda é igual à de agora: mude algo na prancheta."
        )
    else:
        st.caption(f"A foi guardada às {a['hora']}. A coluna Agora acompanha a prancheta.")
    colunas = st.columns(3)
    colunas[0].button(
        "Trocar A pela de agora",
        key=p.k("trocar_a"),
        on_click=_guardar_como_a,
        args=(p,),
        help="Guarda a montagem de agora no lugar de A.",
        width="stretch",
    )
    colunas[1].button(
        "Voltar para A",
        key=p.k("voltar_a"),
        on_click=_voltar_para_a,
        args=(p,),
        help="Põe A de volta na prancheta. Ctrl+Z na prancheta desfaz.",
        width="stretch",
    )
    colunas[2].button(
        "Esquecer A",
        key=p.k("esquecer_a"),
        on_click=_esquecer_a,
        args=(p,),
        help="Tira a comparação da página.",
        width="stretch",
    )


# ---------------------------------------------------------------------------
# Levar para outras análises
# ---------------------------------------------------------------------------


def _quem_manda_no(resposta: mt.Resposta | None) -> str | None:
    return resposta.manda.condicao.no if resposta is not None and resposta.manda else None


def _com_numero(resposta: mt.Resposta | None) -> bool:
    return resposta is not None and resposta.valor is not None and not resposta.faltam


def _valores_do_ponto(ponto: rp.PontoDaSecao) -> dict[str, float]:
    return {"sigma_x": ponto.sigma_x, "sigma_y": ponto.sigma_y, "tau_xy": ponto.tau_xy}


def _valores_da_fadiga(fadiga: rp.Fadiga) -> dict[str, float]:
    valores = {"sigma_a": fadiga.sigma_a, "sigma_m": fadiga.sigma_m}
    if fadiga.d is not None:
        valores["d"] = fadiga.d
    return valores


def _atualizar_repasses(p: Parte, base: mt.Montagem, resposta: mt.Resposta | None) -> None:
    """O que foi levado a outra análise, refeito com a montagem de agora: lá o aviso compara."""
    if p.dominio != mb.SOLIDOS or not rpm.repasses():
        return
    numeros = _numeros_da_conta(p, resposta) if _com_numero(resposta) else {}

    def calcular(destino: str, repasse: Mapping[str, Any]) -> tuple[dict[str, float] | None, str]:
        if not numeros:
            return None, "a conta ficou sem número"
        if destino == rpm.FADIGA:
            fadiga = rp.fadiga(base, numeros)
            if fadiga is None:
                return None, "o bloco Fadiga de eixo não está mais ligado"
            return _valores_da_fadiga(fadiga), ""
        nome = str(repasse.get("ponto") or "")
        achados = rp.pontos(base, numeros, _quem_manda_no(resposta))
        ponto = next((x for x in achados if x.nome == nome), None)
        if ponto is None:
            return None, f"o ponto {nome} não está mais na seção"
        return _valores_do_ponto(ponto), ""

    rpm.atualizar(p.prefixo, calcular)


def _levar_para_outras_analises(
    p: Parte, base: mt.Montagem, resposta: mt.Resposta, registro: Mapping[str, Any] | None
) -> None:
    """O ponto escolhido vai à Análise estática e ao Círculo de Mohr; a fadiga, à Análise de fadiga."""
    if p.dominio != mb.SOLIDOS:
        return
    _titulo_da_pagina("Levar para outras análises")
    if not _com_numero(resposta):
        st.caption("Com todos os valores preenchidos, as tensões vão para as outras análises.")
        return
    numeros = _numeros_da_conta(p, resposta)
    pontos = rp.pontos(base, numeros, _quem_manda_no(resposta))
    fadiga = rp.fadiga(base, numeros)
    if not pontos and fadiga is None:
        st.caption("Sem uma seção ligada a um critério, não há tensão para levar.")
        return
    estado = st.session_state
    ponto: rp.PontoDaSecao | None = None
    if pontos:
        por_nome = {x.nome: x for x in pontos}
        chave = p.k("ponto_levado")
        if estado.get(chave) not in por_nome:
            estado[chave] = max(pontos, key=lambda x: x.von_mises).nome
        # Só o nome na lista: o Streamlit não renova o rótulo da opção já escolhida, e um número
        # no rótulo ficaria velho depois de mudar a montagem. Os números vão na linha de baixo.
        nome = st.selectbox(
            "Ponto da seção",
            list(por_nome),
            key=chave,
            help="Começa no de maior von Mises. Vão σx, σy e τxy dele, com a resposta no lugar "
            "da letra pedida.",
        )
        ponto = por_nome[nome]
        st.caption(
            f"σx = {_numero(ponto.sigma_x)} MPa · σy = {_numero(ponto.sigma_y)} MPa · "
            f"τxy = {_numero(ponto.tau_xy)} MPa · von Mises = {_numero(ponto.von_mises)} MPa"
        )
    colunas = st.columns(3)
    vai_estatica = colunas[0].button(
        "Análise estática",
        icon=":material/analytics:",
        key=p.k("levar_estatica"),
        disabled=ponto is None,
        width="stretch",
        help="Leva σx, σy e τxy do ponto. Lá entram o material e o fator de segurança.",
    )
    vai_mohr = colunas[1].button(
        "Círculo de Mohr",
        icon=":material/donut_large:",
        key=p.k("levar_mohr"),
        disabled=ponto is None,
        width="stretch",
        help="Leva o estado plano do ponto: tensões principais e cisalhamento máximo.",
    )
    vai_fadiga = colunas[2].button(
        "Análise de fadiga",
        icon=":material/cycle:",
        key=p.k("levar_fadiga"),
        disabled=fadiga is None,
        width="stretch",
        help=(
            "Leva σa' e σm' do bloco Fadiga de eixo e o d da seção redonda."
            if fadiga is not None
            else "Ponha o bloco Fadiga de eixo: é ele que separa a parte alternada da média."
        ),
    )
    if fadiga is not None:
        st.caption(
            "Na fadiga, σa' e σm' vão como o Montador calculou, já com K_f e K_fs. Lá o entalhe "
            "fica em Sem entalhe, para não contar duas vezes, e o carregamento em Flexão, de fator "
            "1, como no von Mises das parcelas."
            + (
                ""
                if fadiga.d is not None
                else " A seção não é redonda: informe o d equivalente lá."
            )
        )
    origem_id = id_registro_existente(dict(registro)) if registro is not None else None
    if origem_id is None:
        st.caption(
            ":material/link_off: A montagem ainda não foi registrada no projeto: os números vão, "
            "mas sem uma origem rastreável. Registre em Salvar, abrir e registrar."
        )
    else:
        st.caption(":material/link: Vai junto a origem: o registro desta montagem no projeto.")
    st.caption(
        "Se a montagem mudar depois do envio, a página que recebeu avisa e traz os números novos."
    )
    titulo = _titulo_do_registro(p)
    if ponto is not None and (vai_estatica or vai_mohr):
        destino = rpm.ESTATICA if vai_estatica else rpm.MOHR
        rpm.enviar(
            destino,
            _valores_do_ponto(ponto),
            f"{titulo} · {ponto.nome}",
            origem_id,
            parte=p.prefixo,
            ponto=ponto.nome,
        )
    if fadiga is not None and vai_fadiga:
        rpm.enviar(
            rpm.FADIGA,
            _valores_da_fadiga(fadiga),
            f"{titulo} · fadiga",
            origem_id,
            parte=p.prefixo,
            ponto="fadiga",
        )


def _passo_a_passo(resposta: mt.Resposta) -> None:
    letra = _letra(resposta.alvo)
    for item in resposta.isoladas:
        c = item.condicao
        st.markdown(f"**{c.nome}**")
        for rotulo, tensao in c.tensoes:
            if tensao != 0:
                st.latex(f"{rotulo} = {sp.latex(mt.limpar(tensao, c.positiva))}")
        sinal = "=" if c.igualdade else "\\le"
        st.latex(f"{c.letra} = {item.tensao} {sinal} {sp.latex(c.direita)}")
        if item.independente:
            st.caption(f"Essa condição não tem {resposta.alvo.texto}.")
        elif item.formula is not None:
            st.latex(f"{letra} = {item.formula.latex}")
            with st.popover("Fórmula em texto", icon=":material/content_copy:"):
                st.code(str(item.formula.expressao), language=None)
        else:
            st.caption("Sem forma fechada simples: a raiz vem da conta numérica.")


def _de_onde_veio(p: Parte, base: mt.Montagem, u: Unidades) -> None:
    """O rastreio campo a campo: cada valor, a procedência e quem usa."""
    origens = st.session_state[p.k("origens")]
    valores = st.session_state[p.k("valores")]
    usos: dict[str, list[str]] = {}
    tipos = {no.id: mb.POR_CHAVE[no.tipo].nome for no in base.grafo.nos}
    for id_, letras in base.letras_do_bloco:
        for letra in letras:
            usos.setdefault(letra, []).append(tipos.get(id_, id_))
    linhas = []
    for item in base.grandezas:
        valor = valores.get(item.chave)
        linhas.append(
            {
                "Letra": item.texto,
                "Grandeza": item.nome,
                "Valor": "—" if valor is None else _com_unidade(valor, item, u),
                "De onde veio": origens.get(item.chave, "—") if valor is not None else "—",
                "Blocos que usam": ", ".join(dict.fromkeys(usos.get(item.chave, []))),
            }
        )
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")


def _ao_enviar_arquivo(p: Parte, campo: str) -> None:
    estado = st.session_state
    arquivo = estado.get(campo)
    if arquivo is None:
        return
    try:
        doc = rg.ler_documento(arquivo.getvalue(), p.dominio, p.sistema)
    except rg.ErroDeArquivo as erro:
        estado[p.k("erro_arquivo")] = str(erro)
        return
    estado[p.k("erro_arquivo")] = ""
    _abrir_documento(p, doc)


def _ao_abrir_do_projeto(p: Parte, campo: str) -> None:
    estado = st.session_state
    montagens = rg.montagens_do_projeto(projeto_ativo_persistente(), p.modulo_id)
    registro = next((r for r in montagens if r.get("id") == estado.get(campo)), None)
    if registro is None:
        return
    try:
        doc = rg.ler_documento(json.dumps(registro["montagem"]), p.dominio, p.sistema)
    except rg.ErroDeArquivo as erro:
        estado[p.k("erro_arquivo")] = str(erro)
        return
    _abrir_documento(p, doc)


def _documentos(
    p: Parte,
    titulo: str,
    dados: Mapping[str, Any],
    resposta: mt.Resposta,
    u: Unidades,
    faces: Mapping[str, Mapping[str, str]],
    hipoteses: Sequence[str],
) -> None:
    """O Word e o Excel só são gerados no clique, como nas outras páginas."""
    estado = st.session_state
    valores = dict(estado[p.k("valores")])
    origens = dict(estado[p.k("origens")])
    conta = resposta.montagem
    if conta is None or resposta.valor is None or resposta.faltam:
        st.caption("Com todos os valores preenchidos, dá para baixar em Word e em Excel.")
        return

    def word() -> bytes:
        return mw.gerar_word(
            titulo,
            dados,
            resposta,
            u,
            valores,
            origens,
            faces,
            rg.texto_da_resposta(resposta, u),
            hipoteses,
            projeto_ativo_persistente(),
        )

    def excel() -> bytes:
        return mp.gerar_planilha(titulo, conta, resposta, u, origens)

    st.download_button(
        "Baixar em Word",
        data=word,
        file_name="montagem.docx",
        mime=_MIME_WORD,
        on_click="ignore",
        icon=":material/description:",
        key=p.k("baixar_word"),
        help="Os blocos, os dados, as fórmulas, o resultado e o que não passou.",
    )
    st.download_button(
        "Baixar em Excel",
        data=excel,
        file_name="montagem.xlsx",
        mime=_MIME_EXCEL,
        on_click="ignore",
        icon=":material/table_chart:",
        key=p.k("baixar_excel"),
        help="A planilha tem fórmulas vivas: mudou um dado, a conta acompanha.",
    )


def _titulo_do_registro(p: Parte) -> str:
    """O título do cálculo, com o do modelo quando ninguém escreveu um."""
    estado = st.session_state
    if not estado.get(p.k("titulo")):
        estado[p.k("titulo")] = estado.get(p.k("modelo_atual")) or p.titulo
    return str(estado[p.k("titulo")])


def _registro(
    p: Parte,
    doc: Mapping[str, Any],
    base: mt.Montagem,
    resposta: mt.Resposta | None,
    u: Unidades,
) -> dict[str, Any] | None:
    """O registro técnico desta montagem. Sai uma vez por rodada: registrar e levar usam o mesmo."""
    if resposta is None or resposta.valor is None:
        return None
    return rg.registro_tecnico(
        modulo=p.titulo,
        modulo_id=p.modulo_id,
        dominio=p.dominio,
        titulo=_titulo_do_registro(p),
        resposta=resposta,
        montagem=resposta.montagem or base,
        doc=doc,
        u=u,
    )


def _salvar_e_abrir(
    p: Parte,
    doc: Mapping[str, Any],
    resposta: mt.Resposta | None,
    u: Unidades,
    dados: Mapping[str, Any],
    faces: Mapping[str, Mapping[str, str]],
    hipoteses: Sequence[str],
    registro: Mapping[str, Any] | None,
) -> None:
    estado = st.session_state
    st.caption(armazenamento.frase_de_persistencia())
    erro = estado.get(p.k("erro_arquivo"))
    if erro:
        st.error(erro, icon=":material/error:")
    esquerda, direita = st.columns(2, gap="large")
    with esquerda:
        st.markdown("**Registrar no projeto**")
        _titulo_do_registro(p)
        titulo = st.text_input(
            "Título do cálculo",
            key=p.k("titulo"),
            help="O nome que aparece no memorial e na lista de registros.",
        )
        if registro is None:
            st.caption(
                "Complete a conta para registrar: resultado sem número não entra no projeto."
            )
        elif botao_registrar_calculo(dict(registro), key=p.k("registrar")):
            estado[p.k("salvo")] = rg.assinatura(doc)
        montagens = rg.montagens_do_projeto(projeto_ativo_persistente(), p.modulo_id)
        if montagens:
            rotulos = {
                r["id"]: f"{r.get('titulo')} · {r.get('criado_em', '')[:10]}" for r in montagens
            }
            campo = p.k("abrir_registro")
            st.selectbox(
                "Montagens deste projeto",
                list(rotulos),
                key=campo,
                format_func=lambda c: rotulos[c],
                help="As montagens já registradas no projeto ativo.",
            )
            st.button(
                "Abrir esta montagem",
                key=p.k("abrir_do_projeto"),
                on_click=_ao_abrir_do_projeto,
                args=(p, campo),
                help="Troca a prancheta por essa montagem. O botão Voltar desfaz.",
            )
    with direita:
        st.markdown("**Arquivo**")
        st.download_button(
            "Baixar a montagem",
            data=rg.em_json(doc),
            file_name="montagem.json",
            mime="application/json",
            key=p.k("baixar"),
            help="Um arquivo com os blocos e os valores, para guardar fora do programa.",
        )
        if resposta is not None:
            _documentos(p, titulo, dados, resposta, u, faces, hipoteses)
        campo = f"{p.prefixo}_arquivo_{estado[p.k('revisao')]}"
        st.file_uploader(
            "Abrir arquivo de montagem",
            type=["json"],
            key=campo,
            on_change=_ao_enviar_arquivo,
            args=(p, campo),
            help="Abre uma montagem baixada antes. O botão Voltar desfaz.",
        )


# ---------------------------------------------------------------------------
# Casos de carga
# ---------------------------------------------------------------------------

#: As letras que costumam mudar de um caso para outro: o que é carga.
_DIMENSOES_DE_CARGA = (g.FORCA, g.MOMENTO, g.PRESSAO, g.POTENCIA)


def _casos_atuais(p: Parte) -> dict[str, Any]:
    return mcs.normalizar(st.session_state.get(p.k("casos"))) or mcs.vazio()


def _gravar_casos(p: Parte, casos: Mapping[str, Any]) -> None:
    estado = st.session_state
    estado[p.k("casos")] = mcs.normalizar(casos)
    estado[p.k("casos_rev")] = estado.get(p.k("casos_rev"), 0) + 1


def _ao_ligar_casos(p: Parte, letras: list[str], valores: dict[str, float]) -> None:
    estado = st.session_state
    casos = _casos_atuais(p)
    casos["ligado"] = bool(estado.get(p.k("casos_ligado")))
    if casos["ligado"] and not casos["lista"]:
        casos["letras"] = casos["letras"] or letras
        casos["lista"] = [
            {
                "nome": "Caso 2",
                "valores": {k: v for k, v in valores.items() if k in casos["letras"]},
            }
        ]
    _gravar_casos(p, casos)


def _ao_mudar_nome_do_caso_base(p: Parte) -> None:
    casos = _casos_atuais(p)
    casos["base"] = str(st.session_state.get(p.k("casos_base")) or "")
    _gravar_casos(p, casos)


def _ao_escolher_letras_dos_casos(p: Parte) -> None:
    casos = _casos_atuais(p)
    casos["letras"] = list(st.session_state.get(p.k("casos_letras")) or ())
    _gravar_casos(p, casos)


def _linhas_dos_casos(
    casos: Mapping[str, Any], colunas: Sequence[tuple[str, str, float]]
) -> list[dict[str, Any]]:
    return [
        {
            "Caso": item["nome"],
            **{
                rotulo: (item["valores"][chave] / fator if chave in item["valores"] else None)
                for rotulo, chave, fator in colunas
            },
        }
        for item in casos["lista"]
    ]


def _ao_editar_casos(p: Parte, chave: str, colunas: list[tuple[str, str, float]]) -> None:
    estado = st.session_state
    casos = _casos_atuais(p)
    novas = _com_edicoes(_linhas_dos_casos(casos, colunas), estado.get(chave) or {})
    lista = []
    for i, linha in enumerate(novas[: mcs.MAXIMO_DE_CASOS]):
        valores = {}
        for rotulo, letra, fator in colunas:
            valor = linha.get(rotulo)
            if (
                isinstance(valor, (int, float))
                and not isinstance(valor, bool)
                and math.isfinite(valor)
            ):
                valores[letra] = float(valor) * fator
        nome = str(linha.get("Caso") or "").strip() or f"Caso {i + 2}"
        lista.append({"nome": nome, "valores": valores})
    casos["lista"] = lista
    _gravar_casos(p, casos)


def _casos_de_carga(
    p: Parte,
    base: mt.Montagem,
    alvo: str | None,
    resposta: mt.Resposta,
    u: Unidades,
    avisos: Sequence[str],
) -> None:
    """Partida e regime, cheio e vazio: a mesma peça com cargas diferentes, e manda o pior."""
    estado = st.session_state
    _titulo_da_pagina("Casos de carga")
    casos = _casos_atuais(p)
    opcoes = {item.chave: item for item in base.grandezas if item.chave != alvo}
    valores = {k: v for k, v in estado[p.k("valores")].items() if v is not None and k in opcoes}
    padrao = [k for k, item in opcoes.items() if item.dimensao in _DIMENSOES_DE_CARGA]
    estado[p.k("casos_ligado")] = casos["ligado"]
    st.toggle(
        "Mais de um caso de carga",
        key=p.k("casos_ligado"),
        on_change=_ao_ligar_casos,
        args=(p, padrao, valores),
        help=(
            "A mesma peça com cargas diferentes, como partida e regime. Cada caso muda só as letras "
            "escolhidas, e a resposta sai do pior caso."
        ),
    )
    if not casos["ligado"]:
        return
    esquerda, direita = st.columns([1, 2], gap="medium")
    estado[p.k("casos_base")] = casos["base"]
    esquerda.text_input(
        "Nome do caso do inspetor",
        key=p.k("casos_base"),
        on_change=_ao_mudar_nome_do_caso_base,
        args=(p,),
        max_chars=mcs.TAMANHO_DO_NOME,
        help="Os valores do inspetor são o primeiro caso. Dê um nome a ele, como Regime.",
    )
    estado[p.k("casos_letras")] = [k for k in casos["letras"] if k in opcoes]
    direita.multiselect(
        "Letras que mudam de um caso para outro",
        list(opcoes),
        key=p.k("casos_letras"),
        on_change=_ao_escolher_letras_dos_casos,
        args=(p,),
        format_func=lambda c: f"{opcoes[c].texto}: {opcoes[c].nome}",
        help="Quase sempre os esforços. A letra pedida não muda: ela é a resposta.",
    )
    colunas = [
        (
            f"{opcoes[k].texto} ({u.rotulo(opcoes[k].dimensao)})"
            if u.rotulo(opcoes[k].dimensao)
            else opcoes[k].texto,
            k,
            u.fator(opcoes[k].dimensao),
        )
        for k in estado[p.k("casos_letras")]
    ]
    if not colunas:
        st.info("Escolha ao menos uma letra que muda.", icon=":material/info:")
        return
    chave = f"{p.prefixo}_casos_tabela_{estado.get(p.k('casos_rev'), 0)}"
    st.data_editor(
        pd.DataFrame(_linhas_dos_casos(casos, colunas), columns=["Caso", *(c[0] for c in colunas)]),
        key=chave,
        on_change=_ao_editar_casos,
        args=(p, chave, colunas),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "Caso": st.column_config.TextColumn("Caso", max_chars=mcs.TAMANHO_DO_NOME),
            **{
                rotulo: st.column_config.NumberColumn(rotulo, format="%.6g")
                for rotulo, _, _ in colunas
            },
        },
    )
    st.caption(
        f"Uma linha por caso, além de “{casos['base']}”, que usa os valores do inspetor. Célula "
        f"vazia vale o número de “{casos['base']}”. Até {mcs.MAXIMO_DE_CASOS} casos."
    )
    for aviso in avisos:
        st.warning(aviso, icon=":material/warning:")
    por_caso = mcs.resposta_de_cada_caso(resposta)
    if not por_caso or resposta.valor is None:
        return
    quem = resposta.manda.condicao.caso if resposta.manda is not None else ""
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Caso": nome,
                    "Pede": (
                        f"{resposta.alvo.texto} {_sinal(item.lado)} "
                        f"{_com_unidade(item.valor, resposta.alvo, u)}"
                        if item is not None and item.valor is not None
                        else "—"
                    ),
                    "Quem manda no caso": (
                        item.condicao.nome.removeprefix(f"{nome}: ") if item is not None else "—"
                    ),
                    "Manda": "●" if nome == quem else "",
                }
                for nome, item in por_caso
            ]
        ),
        hide_index=True,
        width="stretch",
    )


def tela_do_montador(p: Parte) -> None:
    st.html(_ESTILO)
    _iniciar(p)
    _secao_que_voltou(p)
    aviso_da_secao = st.session_state.pop(p.k("aviso_secao"), "")
    if aviso_da_secao:
        st.toast(aviso_da_secao, icon=":material/draw:")
    _cabecalho(p)
    _como_usar(p)
    estado = st.session_state
    u = Unidades(p.sistema, tuple(estado[p.k("unidades")]))
    dados = estado[p.k("grafo")]
    grafo = mt.grafo_de_dados(dados)
    base = mt.montar(grafo)
    # Nesta ordem, e sem nada na tela no meio: o número segue o bloco, a cópia recebe os números do
    # original, as letras novas ganham o padrão, e só então a montagem entra no histórico.
    _acompanhar_os_blocos(p, base)
    _preencher_copias(p, base)
    _sincronizar_valores(p, base)
    alvo = _alvo(p, base)
    _registrar_historia(p)
    _contar_o_que_andou(p, base, u)
    estado[p.k("campos")] = {item.chave: item.dimensao for item in base.grandezas}
    resposta: mt.Resposta | None = None
    falha = ""
    conta = base
    avisos_dos_casos: tuple[str, ...] = ()
    if alvo is not None and base.condicoes and p.dominio == mb.SOLIDOS:
        caso_base, casos = mcs.para_a_conta(estado.get(p.k("casos")))
        if casos:
            conta, avisos_dos_casos = mt.com_casos(
                base, estado[p.k("valores")], alvo, caso_base, casos
            )
    if alvo is not None and base.condicoes:
        try:
            with st.spinner("Fazendo a conta…"):
                resposta = mt.isolar(
                    conta, alvo, estado[p.k("valores")], estado.get(p.k("adotado"))
                )
        except ValueError as erro:
            falha = str(erro)
        except (ArithmeticError, RecursionError, TypeError, LookupError, AttributeError) as erro:
            if dg.levantar_erros():
                raise
            registrar_falha(f"{p.titulo} › Resposta", erro)
            falha = (
                "O programa não conseguiu fechar esta conta com os valores e as ligações de agora. "
                "Confira os números (zero, negativo ou muito fora de escala) e a letra pedida "
                f"(ref. {dg.referencia_da_falha(erro)})."
            )
    _atualizar_repasses(p, base, resposta)  # antes de qualquer saída da página
    projeto = projeto_ativo_persistente()
    diagnosticos = rg.conferir_referencias(grafo, projeto, p.dominio, u)
    doc = rg.documento(
        p.dominio,
        dados,
        estado[p.k("valores")],
        estado[p.k("origens")],
        alvo,
        estado.get(p.k("adotado")),
        estado[p.k("unidades")],
        estado.get(p.k("casos")),
    )
    registro = _registro(p, doc, base, resposta, u)
    salvo = estado.get(p.k("salvo")) == rg.assinatura(doc)
    padroes_em_uso = [
        item.texto
        for item in base.grandezas
        if estado[p.k("origens")].get(item.chave) == _PADRAO_DO_PROGRAMA
        and estado[p.k("valores")].get(item.chave) is not None
        and item.chave != alvo
    ]
    copiados = [
        item.texto
        for item in base.grandezas
        if mh.copiada(estado[p.k("origens")].get(item.chave))
        and estado[p.k("valores")].get(item.chave) is not None
        and item.chave != alvo
    ]
    erros = dict(base.erros)
    for diagnostico in diagnosticos:
        if diagnostico.situacao != rg.EM_DIA:
            erros[diagnostico.no] = diagnostico.mensagem
    faces, luzes = _faces(
        grafo,
        dados,
        base,
        resposta,
        estado[p.k("valores")],
        alvo,
        u,
        _numeros_da_conta(p, resposta),
    )
    marcas = {
        "erros": erros,
        "faces": faces,
        "luzes": luzes,
        "situacao": _situacao(
            grafo, base, resposta, falha, diagnosticos, padroes_em_uso, salvo, copiados
        ),
        "rastro": _rastro(grafo, resposta),
        "campos": _campos_do_cartao(base, estado[p.k("valores")], estado[p.k("origens")], alvo, u),
    }
    catalogo = [*mb.catalogo_para_tela(p.dominio), *mc.catalogo_de_conjuntos(p.dominio)]
    escondidos = mus.escondidos(dados, catalogo)
    historico = estado[p.k("historico")]
    prancha, lateral = st.columns([2.7, 1], gap="small")
    with prancha:
        prancheta_de_blocos(
            {
                "catalogo": catalogo,
                "escondidos": escondidos,
                "grafo": dados,
                "versao": estado[p.k("versao")],
                "ajustar": estado[p.k("ajuste")],
                "marcas": marcas,
                "selecionar": estado.pop(p.k("pedido"), None),
                "historia": {
                    "desfazer": bool(historico["passado"]),
                    "refazer": bool(historico["futuro"]),
                    "aviso": estado.get(p.k("aviso_historia")),
                },
                "recebido": estado.get(p.k("comandos"), 0),
                "colagens": list(estado.get(p.k("colagens")) or ()),
            },
            key=p.k("prancheta"),
            ao_editar=lambda: _ao_editar(p),
            ao_selecionar=lambda: _ao_selecionar(p),
            ao_comandar=lambda: _ao_comandar(p),
        )
    with lateral, st.container(key=p.k("inspetor"), height=_ALTURA_DA_PRANCHETA, border=True):
        _resposta_no_inspetor(resposta, falha, base, u)
        _inspetor(p, dados, grafo, base, resposta, alvo, u, diagnosticos)

    erro_conjunto = estado.get(p.k("erro_conjunto"))
    if erro_conjunto:
        st.warning(erro_conjunto, icon=":material/warning:")
    for alerta in base.alertas:
        st.warning(alerta, icon=":material/warning:")
    if falha:
        st.error(falha, icon=":material/error:")
    eixo_ui.editores_dos_eixos(p, grafo, base, resposta, u)
    if not base.condicoes or alvo is None:
        if not base.erros and not grafo.nos:
            st.info(
                "Comece por um bloco da biblioteca, ponha um critério e o bloco Em função de.",
                icon=":material/info:",
            )
        for _, erro in base.erros:
            st.warning(erro, icon=":material/warning:")
        return

    _titulo_da_pagina("Resposta")
    _escolher_alvo(p, base, alvo, u)
    if resposta is None:
        return
    for problema in resposta.invalidos:
        st.error(problema, icon=":material/error:")
    _anotar_mudanca(p, resposta, u)
    if estado.get(p.k("mudanca")):
        st.caption(estado[p.k("mudanca")])
    _resposta(p, grafo, resposta, u)
    for alerta in resposta.alertas:
        st.warning(alerta, icon=":material/warning:")
    for diagnostico in diagnosticos:
        if diagnostico.situacao != rg.EM_DIA:
            st.warning(diagnostico.mensagem, icon=":material/warning:")
    if resposta.materiais:
        st.caption("Materiais do cadastro que servem: " + "; ".join(resposta.materiais) + ".")
    if p.dominio == mb.SOLIDOS:
        with _parte(p, "Casos de carga"):
            _casos_de_carga(p, base, alvo, resposta, u, avisos_dos_casos)
    _titulo_da_pagina("Condições")
    with _parte(p, "Condições"):
        _quadro(resposta, u)
    valores = {k: v for k, v in estado[p.k("valores")].items() if v is not None}
    with _parte(p, "Ponto de operação"):
        _grafico_da_bomba(resposta, valores, u)
    with _parte(p, "Procurar em faixas"):
        _busca_em_faixas(p, conta, alvo, resposta, u)
    with _parte(p, "Escolher do catálogo"):
        _escolher_do_catalogo(p, conta, alvo)
    with _parte(p, "O que mais pesa"), st.spinner("Vendo o que mais pesa…"):
        _o_que_mais_pesa(p, resposta, u)
    if resposta.valor is not None and resposta.sentido != mt.IGUAL:
        _titulo_da_pagina("Em volta da resposta")
        with _parte(p, "Em volta da resposta"):
            _grafico_de_uso(resposta, valores, u)
            _grafico_de_varredura(p, resposta.montagem or base, resposta, valores, u)
    with _parte(p, "Comparar duas montagens"):
        _comparar(p, base, resposta, u)
    with _parte(p, "Levar para outras análises"):
        _levar_para_outras_analises(p, base, resposta, registro)
    with st.expander("Passo a passo", icon=":material/list_alt:"), _parte(p, "Passo a passo"):
        _passo_a_passo(resposta)
    with (
        st.expander("De onde veio cada valor", icon=":material/account_tree:"),
        _parte(p, "De onde veio cada valor"),
    ):
        _de_onde_veio(p, base, u)
    hipoteses = [
        "Pré-dimensionamento: não substitui a verificação por norma.",
        *base.hipoteses,
    ]
    if p.dominio == mb.SOLIDOS:
        hipoteses.insert(
            1,
            "O critério roda em cada ponto da seção, com os esforços que existem ali: fibra, linha "
            "neutra e junção. Material elástico e linear, sem plasticidade nem tensão residual.",
        )
    else:
        hipoteses.insert(
            1,
            "Escoamento permanente e incompressível, com a linha em série e a mesma vazão em todos "
            "os trechos. Propriedades dos fluidos e rugosidades são valores típicos de tabela.",
        )
    with (
        st.expander("Salvar, abrir e registrar", icon=":material/save:"),
        _parte(p, "Salvar, abrir e registrar"),
    ):
        _salvar_e_abrir(p, doc, resposta, u, dados, faces, hipoteses, registro)
    fronteira_modelo(hipoteses, titulo="Hipóteses desta conta")
