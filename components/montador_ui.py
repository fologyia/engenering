"""Tela do Montador de fórmulas: a prancheta de blocos, os valores e a fórmula isolada.

O desenho mora em ``st.session_state`` e entra por callback, antes de o script rodar: assim a resposta
já sai do desenho que acabou de chegar e vai na mesma rodada para o bloco "Em função de". Os valores
ficam guardados na base N, mm e MPa, e os campos só mostram na unidade da tela: trocar a unidade não
muda a conta. ``REVISAO`` renova os campos quando os números mudam por fora deles.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st
import sympy as sp

from components.figuras import SO_NA_LARGURA
from components.prancheta_blocos_ui import prancheta_de_blocos
from components.ui import fronteira_modelo
from core import montador as mt
from core import montador_blocos as mb
from core import montador_grandezas as g
from core import montador_modelos as mm
from core.montador_grandezas import Grandeza, Unidades

GRAFO = "mf_grafo"
VERSAO = "mf_versao"
AJUSTE = "mf_ajuste"
VALORES = "mf_valores"
PADROES = "mf_padroes"
ALVO = "mf_alvo"
REVISAO = "mf_revisao"
MODELO = "mf_modelo"
MODELO_ATUAL = "mf_modelo_atual"
PRANCHETA = "mf_prancheta"
UNIDADE_MEDIDA = "mf_u_medida"
UNIDADE_COMPRIMENTO = "mf_u_comprimento"
UNIDADE_FORCA = "mf_u_forca"
UNIDADE_MOMENTO = "mf_u_momento"
UNIDADES_ATUAIS = "mf_unidades"
CHAVE_ALVO = "mf_alvo_escolha"
VARRER = "mf_varrer"
_NAO_VARRE = "Nenhuma"


def _aplicar(modelo: mm.Modelo) -> None:
    estado = st.session_state
    estado[GRAFO] = modelo.grafo()
    estado[VERSAO] = estado.get(VERSAO, 0) + 1
    estado[AJUSTE] = estado.get(AJUSTE, 0) + 1
    estado[VALORES] = dict(modelo.valores)
    estado[PADROES] = {}
    estado[ALVO] = modelo.alvo
    estado[REVISAO] = estado.get(REVISAO, 0) + 1
    estado[MODELO_ATUAL] = modelo.nome


def _iniciar() -> None:
    estado = st.session_state
    if GRAFO in estado:
        return
    estado[UNIDADES_ATUAIS] = ("mm", "m", "kN", "kN·m")
    _aplicar(mm.MODELO_INICIAL)


def _ao_escolher_modelo() -> None:
    modelo = mm.POR_NOME.get(st.session_state.get(MODELO) or "")
    if modelo is not None:
        _aplicar(modelo)


def _ao_editar() -> None:
    evento = getattr(st.session_state.get(PRANCHETA), "edicao", None)
    if not evento or not isinstance(evento.get("grafo"), Mapping):
        return
    estado = st.session_state
    estado[GRAFO] = dict(evento["grafo"])
    estado[VERSAO] = int(evento.get("versao", 0))
    estado[MODELO_ATUAL] = None


def _limpar() -> None:
    estado = st.session_state
    estado[GRAFO] = {"nos": [], "fios": []}
    estado[VERSAO] += 1
    estado[AJUSTE] += 1
    estado[MODELO_ATUAL] = None
    estado[VALORES] = {}
    estado[PADROES] = {}
    estado[ALVO] = None
    estado[REVISAO] += 1


def _ao_trocar_unidade() -> None:
    estado = st.session_state
    estado[UNIDADES_ATUAIS] = (
        estado[UNIDADE_MEDIDA],
        estado[UNIDADE_COMPRIMENTO],
        estado[UNIDADE_FORCA],
        estado[UNIDADE_MOMENTO],
    )
    estado[REVISAO] += 1


def _cabecalho() -> None:
    estado = st.session_state
    # O Streamlit apaga o estado do seletor que não foi desenhado: quem manda são as chaves atuais.
    (
        estado[UNIDADE_MEDIDA],
        estado[UNIDADE_COMPRIMENTO],
        estado[UNIDADE_FORCA],
        estado[UNIDADE_MOMENTO],
    ) = estado[UNIDADES_ATUAIS]
    estado[MODELO] = estado[MODELO_ATUAL]
    colunas = st.columns([3.4, 1, 1, 1, 1.2, 1.3], vertical_alignment="bottom")
    colunas[0].selectbox(
        "Começar de um modelo",
        [modelo.nome for modelo in mm.MODELOS],
        index=None,
        placeholder="Montagem minha, sem modelo",
        key=MODELO,
        on_change=_ao_escolher_modelo,
        format_func=lambda nome: f"{nome}: {mm.POR_NOME[nome].dica}",
        help="Abre os blocos prontos com números de exemplo. Depois é só mudar por cima.",
    )
    colunas[1].selectbox(
        "Seção",
        tuple(g.MEDIDAS),
        key=UNIDADE_MEDIDA,
        on_change=_ao_trocar_unidade,
        help="Unidade das medidas da seção. Trocar converte os números.",
    )
    colunas[2].selectbox(
        "Comprimento",
        tuple(g.MEDIDAS),
        key=UNIDADE_COMPRIMENTO,
        on_change=_ao_trocar_unidade,
        help="Unidade dos comprimentos da peça: vão, coluna, trecho de eixo e braço da força.",
    )
    colunas[3].selectbox(
        "Força",
        tuple(g.FORCAS),
        key=UNIDADE_FORCA,
        on_change=_ao_trocar_unidade,
        help="Unidade das forças. Trocar converte os números.",
    )
    colunas[4].selectbox(
        "Momento",
        tuple(g.MOMENTOS),
        key=UNIDADE_MOMENTO,
        on_change=_ao_trocar_unidade,
        help="Unidade dos momentos e torques. Trocar converte os números.",
    )
    colunas[5].button(
        "Limpar",
        key="mf_limpar",
        icon=":material/delete:",
        on_click=_limpar,
        help="Apaga os blocos para começar do zero.",
        width="stretch",
    )


def _numero(valor: float) -> str:
    if valor == 0.0 or not math.isfinite(valor):
        return "0"
    return f"{valor:.4g}".replace(".", ",")


def _com_unidade(valor: float, grandeza: Grandeza, u: Unidades) -> str:
    rotulo = u.rotulo(grandeza.dimensao)
    numero = _numero(valor / u.fator(grandeza.dimensao))
    return f"{numero} {rotulo}".strip()


def _sincronizar_valores(montagem: mt.Montagem) -> None:
    """Letra nova chega com o padrão dela, e trocar o material atualiza S_y."""
    estado = st.session_state
    valores, conhecidos = estado[VALORES], estado[PADROES]
    mudou = False
    for grandeza in montagem.grandezas:
        if grandeza.chave not in valores and grandeza.padrao is not None:
            valores[grandeza.chave] = grandeza.padrao
            mudou = True
    for chave, padrao in montagem.padroes:
        if conhecidos.get(chave) != padrao:
            conhecidos[chave] = padrao
            valores[chave] = padrao
            mudou = True
    if mudou:
        estado[REVISAO] += 1


def _alvo(montagem: mt.Montagem) -> str | None:
    """A letra pedida. Sem escolha, a primeira medida sem valor: é o que costuma faltar."""
    estado = st.session_state
    opcoes = [item for item in montagem.grandezas if item.chave in montagem.essenciais]
    if not opcoes:
        return None
    if estado.get(ALVO) in {item.chave for item in opcoes}:
        return estado[ALVO]
    valores = estado[VALORES]
    sem_valor = [item for item in opcoes if valores.get(item.chave) is None]
    medidas = [item for item in sem_valor if item.dimensao == g.MEDIDA]
    escolhida = (medidas or sem_valor or opcoes)[0]
    estado[ALVO] = escolhida.chave
    return escolhida.chave


def _faces(grafo: mt.Grafo) -> dict[str, str]:
    """A fórmula escrita no bloco, quando ela muda com a escolha: M = F·d na flexão."""
    faces = {}
    for no in grafo.nos:
        face = mb.POR_CHAVE[no.tipo].face
        if face is not None:
            faces[no.id] = face(dict(no.opcoes))
    return faces


def _marcas(
    grafo: mt.Grafo, montagem: mt.Montagem, resposta: mt.Resposta | None, u: Unidades
) -> dict[str, Any]:
    texto = ""
    if resposta is not None:
        letra = resposta.alvo.texto
        texto = f"{letra} = ?"
        if resposta.valor is not None:
            sinal = "≥" if resposta.sentido == mt.MINIMO else "≤"
            texto = f"{letra} {sinal} {_com_unidade(resposta.valor, resposta.alvo, u)}"
    return {"erros": dict(montagem.erros), "resposta": texto, "faces": _faces(grafo)}


def _opcoes_dos_blocos(grafo: mt.Grafo) -> None:
    """A lista de cada bloco que tem escolha, como a seção desenhada e o material."""
    estado = st.session_state
    itens = [(no, opcao) for no in grafo.nos for opcao in mb.POR_CHAVE[no.tipo].opcoes]
    if not itens:
        return
    colunas = st.columns(min(len(itens), 3))
    for k, (no, opcao) in enumerate(itens):
        escolhas = opcao.lista()
        atual = dict(no.opcoes).get(opcao.chave, opcao.padrao)
        chave = f"mf_op_{no.id}_{opcao.chave}"
        estado[chave] = atual if atual in escolhas else opcao.padrao
        colunas[k % len(colunas)].selectbox(
            f"{mb.POR_CHAVE[no.tipo].nome}: {opcao.rotulo.lower()}",
            escolhas,
            key=chave,
            on_change=_ao_mudar_opcao,
            args=(no.id, opcao.chave, chave),
            help=opcao.ajuda,
        )


def _ao_mudar_opcao(no_id: str, opcao: str, chave: str) -> None:
    estado = st.session_state
    for no in estado[GRAFO]["nos"]:
        if no["id"] == no_id:
            no.setdefault("opcoes", {})[opcao] = estado[chave]
    estado[VERSAO] += 1
    estado[MODELO_ATUAL] = None


def _ao_escolher_alvo() -> None:
    st.session_state[ALVO] = st.session_state[CHAVE_ALVO]


def _ao_digitar(chave: str, grandeza: Grandeza, fator: float) -> None:
    estado = st.session_state
    valor = estado.get(f"mf_v_{estado[REVISAO]}_{chave}")
    if valor is None:
        estado[VALORES].pop(chave, None)
    else:
        estado[VALORES][chave] = float(valor) * fator


def _escolher_alvo(montagem: mt.Montagem, alvo: str, u: Unidades) -> None:
    opcoes = [item for item in montagem.grandezas if item.chave in montagem.essenciais]
    por_chave = {item.chave: item for item in opcoes}
    st.session_state[CHAVE_ALVO] = alvo
    st.selectbox(
        "Deixar em função de",
        list(por_chave),
        key=CHAVE_ALVO,
        on_change=_ao_escolher_alvo,
        format_func=lambda c: f"{por_chave[c].texto}: {por_chave[c].nome}",
        help="A letra que vai ficar sozinha de um lado da equação: a medida, a carga ou o material.",
    )


def _campos_de_valores(montagem: mt.Montagem, alvo: str, u: Unidades) -> None:
    estado = st.session_state
    st.caption("Deixe vazio para a letra ficar na fórmula.")
    letras = [item for item in montagem.grandezas if item.chave != alvo]
    colunas = st.columns(2)
    for k, grandeza in enumerate(letras):
        fator = u.fator(grandeza.dimensao)
        guardado = estado[VALORES].get(grandeza.chave)
        rotulo = u.rotulo(grandeza.dimensao)
        titulo = f"{grandeza.texto}: {grandeza.nome}" + (f" ({rotulo})" if rotulo else "")
        chave = f"mf_v_{estado[REVISAO]}_{grandeza.chave}"
        if chave not in estado:
            estado[chave] = None if guardado is None else guardado / fator
        # value=None é o que deixa o campo ser esvaziado: o número entra pelo session_state.
        colunas[k % 2].number_input(
            titulo,
            value=None,
            format="%g",
            step=None,
            key=chave,
            on_change=_ao_digitar,
            args=(grandeza.chave, grandeza, fator),
            placeholder="fica como letra",
            help=grandeza.ajuda,
        )


def _resposta(resposta: mt.Resposta, u: Unidades) -> None:
    letra = sp_letra(resposta.alvo)
    if resposta.valor is not None and resposta.manda is not None:
        sinal = "≥" if resposta.sentido == mt.MINIMO else "≤"
        texto = _com_unidade(resposta.valor, resposta.alvo, u)
        st.success(
            f"**{resposta.alvo.texto} {sinal} {texto}**. Quem manda: {resposta.manda.condicao.nome}.",
            icon=":material/check_circle:",
        )
        item = resposta.manda
        if item.formula is not None:
            st.latex(f"{letra} = {item.formula.latex}")
        else:
            st.caption(
                "Esta equação não tem forma fechada simples: o número veio da conta numérica."
            )
            st.latex(item.equacao)
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
        st.caption(
            "Com números, a fórmula está na base: forças em N, medidas em mm, tensões em MPa."
        )


def sp_letra(grandeza: Grandeza) -> str:
    return sp.latex(grandeza.simbolo)


def _quadro(resposta: mt.Resposta, u: Unidades) -> None:
    linhas = []
    conferidas = {linha.nome: linha for linha in resposta.conferencia}
    for item in resposta.isoladas:
        nome = item.condicao.nome
        conferida = conferidas.get(nome)
        pede = "não depende" if item.independente else "—"
        if item.valor is not None:
            sinal = "≥" if item.lado == mt.MINIMO else "≤"
            pede = f"{resposta.alvo.texto} {sinal} {_com_unidade(item.valor, resposta.alvo, u)}"
        linhas.append(
            {
                "Condição": nome,
                "Pede": pede,
                "Valor": round(conferida.esquerda, 4) if conferida else None,
                "Limite": round(conferida.direita, 4) if conferida else None,
                "Uso (%)": round(conferida.uso * 100.0, 1) if conferida else None,
                "Manda": "●" if resposta.manda is not None and item is resposta.manda else "",
            }
        )
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")


def _grafico_de_uso(resposta: mt.Resposta, valores: Mapping[str, float], u: Unidades) -> None:
    linhas = mt.curvas(resposta, valores)
    if not linhas:
        return
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
    montagem: mt.Montagem, resposta: mt.Resposta, valores: Mapping[str, float], u: Unidades
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
        key=VARRER,
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


def _passo_a_passo(resposta: mt.Resposta) -> None:
    letra = sp_letra(resposta.alvo)
    for item in resposta.isoladas:
        c = item.condicao
        st.markdown(f"**{c.nome}**")
        for rotulo, tensao in c.tensoes:
            if tensao != 0:
                st.latex(f"{rotulo} = {sp.latex(mt.limpar(tensao, c.positiva))}")
        st.latex(f"{c.letra} = {item.tensao} \\le {sp.latex(c.direita)}")
        if item.independente:
            st.caption(f"Essa condição não tem {resposta.alvo.texto}.")
        elif item.formula is not None:
            st.latex(f"{letra} = {item.formula.latex}")
            with st.popover("Fórmula em texto", icon=":material/content_copy:"):
                st.code(str(item.formula.expressao), language=None)
        else:
            st.caption("Sem forma fechada simples: a raiz vem da conta numérica.")


def tela_do_montador() -> None:
    _iniciar()
    _cabecalho()
    estado = st.session_state
    u = Unidades(*estado[UNIDADES_ATUAIS])
    grafo = mt.grafo_de_dados(estado[GRAFO])
    montagem = mt.montar(grafo)
    _sincronizar_valores(montagem)
    alvo = _alvo(montagem)
    resposta: mt.Resposta | None = None
    falha = ""
    if alvo is not None and montagem.condicoes:
        try:
            resposta = mt.isolar(montagem, alvo, estado[VALORES])
        except (ValueError, ZeroDivisionError, OverflowError, TypeError) as erro:
            falha = str(erro)

    prancheta_de_blocos(
        {
            "catalogo": mb.catalogo_para_tela(),
            "grafo": estado[GRAFO],
            "versao": estado[VERSAO],
            "ajustar": estado[AJUSTE],
            "marcas": _marcas(grafo, montagem, resposta, u),
        },
        key=PRANCHETA,
        ao_editar=_ao_editar,
    )
    _opcoes_dos_blocos(grafo)
    for _, erro in montagem.erros:
        st.warning(erro, icon=":material/warning:")
    if falha:
        st.error(falha, icon=":material/error:")
    for alerta in montagem.alertas:
        st.warning(alerta, icon=":material/warning:")
    if not montagem.condicoes or alvo is None:
        if not montagem.erros:
            st.info(
                "Comece por uma seção, ponha os esforços, um critério e o bloco Em função de.",
                icon=":material/info:",
            )
        return

    esquerda, direita = st.columns(2, gap="large")
    with esquerda:
        st.markdown("**Valores**")
        _escolher_alvo(montagem, alvo, u)
        _campos_de_valores(montagem, alvo, u)
    with direita:
        st.markdown("**Resposta**")
        if resposta is not None:
            _resposta(resposta, u)
            for alerta in resposta.alertas:
                st.warning(alerta, icon=":material/warning:")
            if resposta.materiais:
                st.caption(
                    "Materiais do cadastro que servem: " + "; ".join(resposta.materiais) + "."
                )
    if resposta is None:
        return
    st.markdown("**Condições**")
    _quadro(resposta, u)
    if resposta.valor is not None:
        st.markdown("**Em volta da resposta**")
        _grafico_de_uso(resposta, estado[VALORES], u)
        _grafico_de_varredura(montagem, resposta, estado[VALORES], u)
    with st.expander("Passo a passo", icon=":material/list_alt:"):
        _passo_a_passo(resposta)
    hipoteses = [
        "O critério roda em cada ponto da seção, com os esforços que existem ali: fibra, linha "
        "neutra e junção.",
        "Material elástico e linear, sem plasticidade nem tensão residual.",
        *montagem.hipoteses,
    ]
    fronteira_modelo(hipoteses, titulo="Hipóteses desta conta")
