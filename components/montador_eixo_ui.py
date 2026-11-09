"""As tabelas e o desenho do eixo com trechos, logo abaixo da prancheta do Montador.

O bloco guarda as duas tabelas nas opções dele, na base (mm e kg). Aqui elas aparecem na unidade da
tela, e cada edição volta para o bloco, refaz as bolinhas das forças e tira os fios que ficaram sem
bolinha. O inspetor é estreito para sete colunas: por isso as tabelas ficam aqui embaixo.
"""

from __future__ import annotations

import base64
import html
import json
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd
import streamlit as st
import sympy as sp

from components.edicao_de_tabela import com_edicoes
from components.figuras import largura_do_png
from core import desenho_do_eixo as de
from core import elementos_eixos as ee
from core import montador as mt
from core import montador_blocos as mb
from core import montador_conjuntos as mc
from core import montador_eixo as me
from core import montador_grandezas as g
from core import montador_registro as rg
from core.montador_grandezas import Unidades
from core.montador_modelos import Parte

_TRECHO = "Trecho"
_RELACAO = "Diâmetro / d"
_ENTALHE = "Entalhe"
_RAIO = "Raio do canto no fim / d"
_ELEMENTO = "Elemento"
_FUNCAO = "Função"
_VERTICAL = "Força vertical"
_HORIZONTAL = "Força horizontal"
_TORQUE = "Torque"
_AXIAL = "Força axial"
_BINARIO = "Binário da axial"
_MASSA = "Massa (kg)"
_INCLINACAO = "Conferir inclinação"


def _numero(valor: float, casas: int = 3) -> str:
    texto = f"{valor:.{casas}g}" if abs(valor) < 1e5 else f"{valor:,.0f}".replace(",", " ")
    return texto.replace(".", ",")


def _comprimento(u: Unidades) -> str:
    return f"Comprimento ({u.rotulo(g.COMPRIMENTO)})"


def _posicao(u: Unidades) -> str:
    return f"Posição x ({u.rotulo(g.COMPRIMENTO)})"


def _raio_axial(u: Unidades) -> str:
    return f"Raio da axial ({u.rotulo(g.MEDIDA)})"


def _linhas_dos_trechos(arranjo: me.Arranjo, u: Unidades) -> list[dict[str, Any]]:
    fator = u.fator(g.COMPRIMENTO)
    return [
        {
            _TRECHO: t.nome,
            _comprimento(u): t.comprimento / fator,
            _RELACAO: t.relacao,
            _ENTALHE: t.entalhe,
            _RAIO: t.raio,
        }
        for t in arranjo.trechos
    ]


def _linhas_dos_elementos(arranjo: me.Arranjo, u: Unidades) -> list[dict[str, Any]]:
    fator, fator_m = u.fator(g.COMPRIMENTO), u.fator(g.MEDIDA)
    return [
        {
            _ELEMENTO: e.nome,
            _posicao(u): e.x / fator,
            _FUNCAO: e.funcao,
            _VERTICAL: e.vertical,
            _HORIZONTAL: e.horizontal,
            _TORQUE: e.torque,
            _AXIAL: e.axial,
            _raio_axial(u): e.raio / fator_m,
            _BINARIO: e.binario,
            _MASSA: e.massa,
            _INCLINACAO: e.engrenagem,
        }
        for e in arranjo.elementos
    ]


def _valor(linha: Mapping[str, Any], coluna: str, fator: float = 1.0, padrao: float = 0.0) -> float:
    bruto = linha.get(coluna)
    try:
        return float(bruto) * fator if bruto is not None else padrao
    except (TypeError, ValueError):
        return padrao


def _trechos_guardados(linhas: Sequence[Mapping[str, Any]], u: Unidades) -> list[dict[str, Any]]:
    fator = u.fator(g.COMPRIMENTO)
    return [
        {
            "nome": str(linha.get(_TRECHO) or f"Trecho {i}"),
            "comprimento": _valor(linha, _comprimento(u), fator),
            "relacao": _valor(linha, _RELACAO, padrao=1.0),
            "entalhe": linha.get(_ENTALHE) or me.LISO,
            "raio": _valor(linha, _RAIO, padrao=0.02),
        }
        for i, linha in enumerate(linhas, start=1)
    ]


def _elementos_guardados(linhas: Sequence[Mapping[str, Any]], u: Unidades) -> list[dict[str, Any]]:
    fator, fator_m = u.fator(g.COMPRIMENTO), u.fator(g.MEDIDA)
    return [
        {
            "nome": str(linha.get(_ELEMENTO) or f"Elemento {i}"),
            "x": _valor(linha, _posicao(u), fator),
            "funcao": linha.get(_FUNCAO) or me.CARGA,
            "vertical": linha.get(_VERTICAL) or me.NENHUMA,
            "horizontal": linha.get(_HORIZONTAL) or me.NENHUMA,
            "torque": linha.get(_TORQUE) or me.NENHUMA,
            "axial": bool(linha.get(_AXIAL)),
            "raio": _valor(linha, _raio_axial(u), fator_m),
            "binario": linha.get(_BINARIO) or me.MAIS,
            "massa": _valor(linha, _MASSA),
            "engrenagem": bool(linha.get(_INCLINACAO)),
        }
        for i, linha in enumerate(linhas, start=1)
    ]


def _revisao(p: Parte, no_id: str) -> str:
    return p.k(f"eixo_rev_{no_id}")


def _ao_editar(p: Parte, no_id: str, chave: str, campo: str) -> None:
    """A tabela editada volta para o bloco, na base, e as bolinhas das forças se refazem."""
    estado = st.session_state
    no = rg.por_id(estado[p.k("grafo")]["nos"], no_id)
    if no is None or no.get("tipo") != me.TIPO:
        return  # o bloco saiu ou virou outro desde que a tabela foi desenhada
    u = Unidades(p.sistema, tuple(estado[p.k("unidades")]))
    opcoes = no.setdefault("opcoes", {})
    arranjo = me.ler_arranjo(opcoes)
    if campo == "trechos":
        linhas = com_edicoes(_linhas_dos_trechos(arranjo, u), estado[chave])
        opcoes["trechos"] = json.dumps(_trechos_guardados(linhas, u), ensure_ascii=False)
        opcoes.setdefault(
            "elementos", json.dumps([dict(x) for x in me.ELEMENTOS_PADRAO], ensure_ascii=False)
        )
    else:
        linhas = com_edicoes(_linhas_dos_elementos(arranjo, u), estado[chave])
        opcoes["elementos"] = json.dumps(_elementos_guardados(linhas, u), ensure_ascii=False)
        opcoes.setdefault(
            "trechos", json.dumps([dict(x) for x in me.TRECHOS_PADRAO], ensure_ascii=False)
        )
    no["portas"] = mb.portas_para_a_tela(me.TIPO, opcoes)
    caminho = no_id.split("/")[:-1]
    estado[p.k("grafo")] = mc.tirar_fios_soltos(estado[p.k("grafo")], caminho)
    estado[p.k("versao")] = estado.get(p.k("versao"), 0) + 1
    estado[p.k("modelo_atual")] = None
    estado[_revisao(p, no_id)] = estado.get(_revisao(p, no_id), 0) + 1


def _tabela_dos_trechos(p: Parte, no: mt.No, arranjo: me.Arranjo, u: Unidades) -> None:
    chave = f"{p.prefixo}_eixo_trechos_{no.id}_{st.session_state.get(_revisao(p, no.id), 0)}"
    st.markdown("**Trechos, da esquerda para a direita**")
    st.data_editor(
        pd.DataFrame(_linhas_dos_trechos(arranjo, u)),
        key=chave,
        hide_index=True,
        num_rows="dynamic",
        width="stretch",
        on_change=_ao_editar,
        args=(p, no.id, chave, "trechos"),
        column_config={
            _TRECHO: st.column_config.TextColumn(help="Um nome para achar o trecho nas condições."),
            _comprimento(u): st.column_config.NumberColumn(
                min_value=0.0, help="Comprimento do trecho ao longo do eixo."
            ),
            _RELACAO: st.column_config.NumberColumn(
                min_value=0.05,
                step=0.05,
                help="O diâmetro do trecho dividido por d. 1 é o próprio d; 1,2 é 20 % mais grosso.",
            ),
            _ENTALHE: st.column_config.SelectboxColumn(
                options=list(me.ENTALHES_DO_TRECHO),
                help="O que enfraquece este trecho à fadiga. O ressalto entre trechos entra sozinho.",
            ),
            _RAIO: st.column_config.NumberColumn(
                min_value=0.0,
                step=0.005,
                format="%.3f",
                help="r/d do canto entre este trecho e o próximo, pelo diâmetro menor. Canto vivo de "
                "rolamento: 0,02. Bem arredondado: 0,1.",
            ),
        },
    )


def _tabela_dos_elementos(p: Parte, no: mt.No, arranjo: me.Arranjo, u: Unidades) -> None:
    chave = f"{p.prefixo}_eixo_elementos_{no.id}_{st.session_state.get(_revisao(p, no.id), 0)}"
    st.markdown("**Mancais, engrenagens, polias e acoplamentos**")
    sentidos = list(me.SENTIDOS)
    st.data_editor(
        pd.DataFrame(_linhas_dos_elementos(arranjo, u)),
        key=chave,
        hide_index=True,
        num_rows="dynamic",
        width="stretch",
        on_change=_ao_editar,
        args=(p, no.id, chave, "elementos"),
        column_config={
            _ELEMENTO: st.column_config.TextColumn(
                help="O nome que aparece no desenho e nas letras."
            ),
            _posicao(u): st.column_config.NumberColumn(
                min_value=0.0, help="Distância da ponta esquerda do eixo até o meio da peça."
            ),
            _FUNCAO: st.column_config.SelectboxColumn(
                options=list(me.FUNCOES),
                help="Um mancal A e um mancal B, que são os apoios. O resto é carga.",
            ),
            _VERTICAL: st.column_config.SelectboxColumn(
                options=sentidos,
                help="Sentido da força no plano vertical: + para baixo, − para cima. A força vira "
                "uma letra F_v com bolinha no bloco.",
            ),
            _HORIZONTAL: st.column_config.SelectboxColumn(
                options=sentidos,
                help="Sentido da força no plano horizontal, a 90° do vertical. Vira a letra F_h.",
            ),
            _TORQUE: st.column_config.SelectboxColumn(
                options=list(me.TORQUES),
                help="Um elemento recebe o torque (Entra) e os outros o entregam (Sai). Cada saída "
                "vira a letra T_e.",
            ),
            _AXIAL: st.column_config.CheckboxColumn(
                help="Engrenagem helicoidal ou cônica: a força axial vai até o mancal que a segura."
            ),
            _raio_axial(u): st.column_config.NumberColumn(
                min_value=0.0, help="Raio onde a axial age, o primitivo: dá o binário F_a·r."
            ),
            _BINARIO: st.column_config.SelectboxColumn(
                options=[me.MAIS, me.MENOS],
                help="Sentido do binário F_a·r no plano vertical. Na dúvida, rode com os dois: o pior "
                "manda.",
            ),
            _MASSA: st.column_config.NumberColumn(
                min_value=0.0, help="Massa da peça presa no eixo, para a rotação crítica."
            ),
            _INCLINACAO: st.column_config.CheckboxColumn(
                help="Engrenagem reta: confere a inclinação ali, até 0,0005 rad."
            ),
        },
    )


def _figura_na_pagina(figura: Any) -> None:
    """O desenho vai dentro da página, e não pelo servidor de arquivos do Streamlit.

    A prancheta pede outra rodada logo depois de trocar o modelo. O Streamlit apagava a imagem da
    rodada interrompida, e quando a seguinte gerava o mesmo desenho, com o mesmo endereço, o
    navegador não buscava de novo: a figura ficava quebrada até a próxima mudança no eixo.
    """
    if not figura.png:
        return
    dados = base64.b64encode(figura.png).decode("ascii")
    st.html(
        f'<figure style="margin:0 auto;text-align:center;max-width:{largura_do_png(figura.png)}px">'
        f'<img src="data:image/png;base64,{dados}" alt="{html.escape(figura.titulo)}" '
        'style="width:100%;height:auto">'
        '<figcaption style="font-size:.85rem;opacity:.72;margin-top:.35rem;line-height:1.4">'
        f"{html.escape(figura.legenda)}</figcaption></figure>"
    )


def _chave_do_d(base: mt.Montagem, no: mt.No) -> str:
    return g.D.com_indice(dict(base.indices).get(no.id, 1)).chave


def _numeros(valores: Mapping[str, float | None]) -> dict[sp.Symbol, sp.Float]:
    return {sp.Symbol(k, positive=True): sp.Float(v) for k, v in valores.items() if v is not None}


def _secoes_na_tela(
    no: mt.No,
    arranjo: me.Arranjo,
    conferidas: Sequence[me.Conferida],
    resposta: mt.Resposta | None,
    numeros: Mapping[sp.Symbol, sp.Float],
    d: float | None,
    u: Unidades,
) -> None:
    usos: dict[str, dict[str, float]] = {}
    if resposta is not None:
        pontos = {i.condicao.nome: i.condicao for i in resposta.isoladas}
        for linha in resposta.conferencia_adotada or resposta.conferencia:
            condicao = pontos.get(linha.nome)
            if linha.no == no.id and condicao is not None and condicao.ponto:
                tipo = "Escoamento" if condicao.criterio == "Escoamento" else "Fadiga"
                usos.setdefault(condicao.ponto, {})[tipo] = linha.uso
    fator_c, fator_m = u.fator(g.COMPRIMENTO), u.fator(g.MEDIDA)
    fator_mom = u.fator(g.MOMENTO)
    linhas = []
    for item in conferidas:
        s = item.secao
        momento = mt.numero_de(item.momento, numeros)
        torque = mt.numero_de(item.torque, numeros)
        uso = usos.get(s.rotulo, {})
        linhas.append(
            {
                "Seção": s.rotulo,
                "Trecho": arranjo.trechos[s.trecho].nome,
                f"x ({u.rotulo(g.COMPRIMENTO)})": round(s.x / fator_c, 4),
                "Entalhe": s.descricao,
                "K_t flexão": round(item.kt[0], 2),
                f"d ({u.rotulo(g.MEDIDA)})": round(s.relacao * d / fator_m, 2) if d else None,
                f"M ({u.rotulo(g.MOMENTO)})": round(momento / fator_mom, 4)
                if momento is not None
                else None,
                f"T ({u.rotulo(g.MOMENTO)})": round(torque / fator_mom, 4)
                if torque is not None
                else None,
                "Uso à fadiga (%)": round(uso["Fadiga"] * 100, 1) if "Fadiga" in uso else None,
                "Uso ao escoamento (%)": round(uso["Escoamento"] * 100, 1)
                if "Escoamento" in uso
                else None,
            }
        )
    if linhas:
        st.markdown("**Seções conferidas**")
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
        st.caption(
            "Ombro do lado fino, onde o raio do canto concentra a tensão, e o entalhe de cada trecho "
            "nos pontos de carga. Entre dois pontos de carga o pior fica sempre num deles."
        )


def editores_dos_eixos(
    p: Parte,
    grafo: mt.Grafo,
    base: mt.Montagem,
    resposta: mt.Resposta | None,
    u: Unidades,
) -> None:
    """Uma parte da página para cada bloco de eixo com trechos da prancheta."""
    nos = [no for no in grafo.nos if no.tipo == me.TIPO]
    estado = st.session_state
    for numero, no in enumerate(nos, start=1):
        arranjo = me.ler_arranjo(dict(no.opcoes))
        titulo = "Eixo com trechos" if len(nos) == 1 else f"Eixo com trechos {numero}"
        st.html(f'<div class="mi-secao mi-pagina">{html.escape(titulo)}</div>')
        chave_d = _chave_do_d(base, no)
        valores = dict(estado[p.k("valores")])
        d: float | None = valores.get(chave_d)
        manda: str | None = None
        if resposta is not None and resposta.alvo.chave == chave_d:
            d = resposta.adotado or resposta.valor
        if d is not None:
            valores[chave_d] = d
        if (
            resposta is not None
            and resposta.manda is not None
            and resposta.manda.condicao.no == no.id
        ):
            manda = resposta.manda.condicao.ponto or None
        conferidas = tuple(base.saidas.get(no.id, {}).get("secoes", ()))
        figura = de.desenhar_eixo(
            arranjo,
            [c.secao for c in conferidas],
            d=d,
            manda=manda,
            comprimento=u.par(g.COMPRIMENTO),
            medida=u.par(g.MEDIDA),
        )
        _figura_na_pagina(figura)
        if (
            resposta is not None
            and resposta.manda is not None
            and resposta.manda.condicao.no == no.id
        ):
            st.caption(f"Neste eixo, quem manda é: {resposta.manda.condicao.nome}.")
        for problema in me.problemas(arranjo):
            st.warning(problema, icon=":material/warning:")
        _tabela_dos_trechos(p, no, arranjo, u)
        _tabela_dos_elementos(p, no, arranjo, u)
        st.caption(
            f"d ({chave_d}) é o diâmetro de referência: cada trecho tem d vezes a relação dele. As "
            "forças de cada elemento viram letras com bolinha no bloco; ligue nelas a engrenagem ou a "
            "polia, ou digite o valor."
        )
        _secoes_na_tela(no, arranjo, conferidas, resposta, _numeros(valores), d, u)


def ajuda_no_inspetor() -> None:
    st.caption(
        "As tabelas dos trechos e dos elementos e o desenho do eixo ficam logo abaixo da prancheta. "
        f"Entalhes do trecho: {', '.join(x.split(' (')[0].lower() for x in me.ENTALHES_DO_TRECHO)}; "
        f"o {ee.ENTALHE_RESSALTO.lower()} entre trechos entra sozinho."
    )
