"""Estudo de uma medida na tela: o gráfico, os valores prontos para usar e o que mais pesa.

O painel só roda quando está aberto, e cada estudo fica guardado pelos dados que o geraram: abrir de
novo com os mesmos números não refaz a conta. A guarda é uma ``lru_cache`` deste módulo, e não o
``st.cache_data``: um estudo guardado em disco sobreviveria à atualização do código com a classe
velha, e foi isso que já derrubou o painel na versão web.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from core import cotas_dos_desenhos as cd
from core import elementos_catalogo as cat
from core import estudo_da_medida as ed
from core.cotas_dos_desenhos import CotaViva
from core.elementos_base import Caso

CHAVE_ABERTO = "assistente_estudo_aberto"
APROVEITAMENTO = "Aproveitamento"
#: Acima disto a curva sai do gráfico: perto de uma seção nula o aproveitamento vai ao infinito.
_TOPO_DO_GRAFICO = 300.0

AoUsar = Callable[[Caso, CotaViva, float, str], None]


@dataclass(frozen=True)
class _Tinta:
    """Cores do gráfico. A ordem das curvas é fixa: seis primeiras da paleta validada."""

    curvas: tuple[str, ...]
    texto: str
    limite: str
    neutro: str


_CLARO = _Tinta(
    ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"),
    "#172033",
    "#b4233c",
    "#64748b",
)
_ESCURO = _Tinta(
    ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300"),
    "#f0efec",
    "#e66767",
    "#94a3b8",
)


def _tinta() -> _Tinta:
    return _ESCURO if st.context.theme.type == "dark" else _CLARO


def assinatura(valores: Mapping[str, Any]) -> str:
    return json.dumps(valores, sort_keys=True, default=str, ensure_ascii=False)


@lru_cache(maxsize=96)
def _estudo_guardado(
    caso_id: str, texto: str, identidade: str, de: float | None, ate: float | None
) -> ed.Estudo | None:
    caso = cat.CASOS[caso_id]
    valores = json.loads(texto)
    medidas = cd.medidas_do_caso(caso, valores)
    medida = next((m for m in medidas if m.identidade == identidade), None)
    return None if medida is None else ed.estudar(caso, valores, medida, de, ate)


@lru_cache(maxsize=96)
def _diagnostico_guardado(caso_id: str, texto: str) -> ed.Diagnostico:
    caso = cat.CASOS[caso_id]
    valores = json.loads(texto)
    return ed.diagnosticar(caso, valores, cd.cotas_do_caso(caso, valores))


@lru_cache(maxsize=32)
def _pesos_guardados(caso_id: str, texto: str) -> tuple[ed.Peso, ...]:
    return tuple(ed.pesos(cat.CASOS[caso_id], json.loads(texto)))


def estudo_de(
    caso: Caso,
    valores: Mapping[str, Any],
    medida: CotaViva,
    de: float | None = None,
    ate: float | None = None,
) -> ed.Estudo | None:
    return _estudo_guardado(caso.id, assinatura(valores), medida.identidade, de, ate)


def diagnostico_de(caso: Caso, valores: Mapping[str, Any]) -> ed.Diagnostico:
    return _diagnostico_guardado(caso.id, assinatura(valores))


def _chave_da_medida(caso: Caso) -> str:
    return f"assistente_estudo_medida::{caso.id}"


def escolher_medida(caso: Caso, medida: CotaViva, *, abrir: bool = False) -> None:
    """Deixa o painel nesta medida. Vem do desenho: quem clicou lá não precisa escolher de novo."""
    st.session_state[_chave_da_medida(caso)] = medida.identidade
    if abrir:
        st.session_state[CHAVE_ABERTO] = True


def _nome(medida: CotaViva) -> str:
    if medida.no_desenho and medida.letra != medida.nome:
        return f"{medida.letra}: {medida.nome}"
    return medida.nome


def _sem_escolha_velha(chave: str, opcoes: Any) -> None:
    """Uma escolha que saiu da lista derruba a seleção: a lista muda com os campos à vista."""
    if chave in st.session_state and st.session_state[chave] not in opcoes:
        del st.session_state[chave]


# ---------------------------------------------------------------------------
# Gráfico
# ---------------------------------------------------------------------------


def _janela(estudo: ed.Estudo, escolhida: bool) -> tuple[float, float]:
    """A parte da faixa que interessa: o valor de agora e os limites, com folga dos dois lados."""
    if escolhida:
        return estudo.de, estudo.ate
    marcas = [estudo.medida.valor, *(opcao.valor for opcao in estudo.opcoes)]
    menor, maior = min(marcas), max(marcas)
    folga = 0.4 * (maior - menor) + 0.35 * max(abs(menor), abs(maior))
    if not folga:
        return estudo.de, estudo.ate
    return max(estudo.de, menor - folga), min(estudo.ate, maior + folga)


def curvas_do_grafico(
    estudo: ed.Estudo, olhar: str, inicio: float, fim: float
) -> list[tuple[float, float, str]]:
    pontos = [p for p in estudo.pontos if inicio <= p.valor <= fim]
    linhas: list[tuple[float, float, str]] = []
    if olhar == APROVEITAMENTO:
        for nome in estudo.criterios_que_governam():
            for ponto in pontos:
                valor = ponto.criterios.get(nome)
                if valor is not None and math.isfinite(valor):
                    linhas.append((ponto.valor, valor * 100.0, nome))
        return linhas
    for ponto in pontos:
        metrica = ponto.metricas.get(olhar)
        if metrica is not None:
            linhas.append((ponto.valor, metrica[0], olhar))
    return linhas


def _rotulo_do_eixo_y(estudo: ed.Estudo, olhar: str) -> str:
    if olhar == APROVEITAMENTO:
        return "Aproveitamento (%)"
    unidade = next((p.metricas[olhar][1] for p in estudo.pontos if olhar in p.metricas), "")
    return f"{olhar} ({unidade})" if unidade else olhar


def _marcas_de_opcao(estudo: ed.Estudo, inicio: float, fim: float) -> list[dict[str, Any]]:
    return [
        {"x": o.valor, "y": o.aproveitamento * 100.0, "texto": cd.numero(o.valor)}
        for o in estudo.opcoes
        if o.aproveitamento is not None and inicio <= o.valor <= fim
    ]


def _grafico(estudo: ed.Estudo, olhar: str, escolhida: bool) -> None:
    inicio, fim = _janela(estudo, escolhida)
    linhas = curvas_do_grafico(estudo, olhar, inicio, fim)
    if not linhas:
        st.caption("Sem número para mostrar nesta faixa.")
        return
    tinta = _tinta()
    tabela = pd.DataFrame(linhas, columns=["x", "y", "Curva"])
    nomes = list(dict.fromkeys(tabela["Curva"]))
    medida = estudo.medida
    titulo_x = f"{medida.letra} ({medida.unidade})" if medida.unidade else medida.letra
    eixo_x = alt.X("x:Q", title=titulo_x, scale=alt.Scale(domain=[inicio, fim], nice=False))
    do_aproveitamento = olhar == APROVEITAMENTO
    escala_y = alt.Scale()
    if do_aproveitamento:
        topo = min(_TOPO_DO_GRAFICO, max(120.0, float(tabela["y"].max()) * 1.05))
        escala_y = alt.Scale(domain=[0.0, topo], nice=False)
    eixo_y = alt.Y("y:Q", title=_rotulo_do_eixo_y(estudo, olhar), scale=escala_y)
    base = alt.Chart(tabela).encode(x=eixo_x, y=eixo_y, detail="Curva:N")
    if len(nomes) > 1:
        cor = alt.Color(
            "Curva:N",
            scale=alt.Scale(domain=nomes, range=list(tinta.curvas[: len(nomes)])),
            # Uma por linha: o nome de um critério é longo, e lado a lado ele sairia cortado.
            legend=alt.Legend(title=None, orient="bottom", columns=1, labelLimit=460),
        )
        linha = base.mark_line(strokeWidth=2, clip=True).encode(color=cor)
    else:
        linha = base.mark_line(strokeWidth=2, clip=True, color=tinta.curvas[0])
    camadas: list[Any] = [linha]
    if do_aproveitamento:
        cem = alt.Chart(pd.DataFrame({"x": [fim], "y": [100.0], "texto": ["Limite: 100 %"]}))
        camadas.append(cem.mark_rule(color=tinta.limite, strokeDash=[5, 4]).encode(y="y:Q"))
        camadas.append(
            cem.mark_text(align="right", dx=-4, dy=-8, color=tinta.texto, fontSize=12).encode(
                x="x:Q", y="y:Q", text="texto:N"
            )
        )
    agora = pd.DataFrame({"x": [medida.valor], "texto": [f"Agora: {cd.numero(medida.valor)}"]})
    if inicio <= medida.valor <= fim:
        regua = alt.Chart(agora)
        camadas.append(regua.mark_rule(color=tinta.neutro, strokeDash=[2, 3]).encode(x="x:Q"))
        camadas.append(
            regua.mark_text(align="left", dx=5, y=8, color=tinta.texto, fontSize=12).encode(
                x="x:Q", text="texto:N"
            )
        )
    marcas = _marcas_de_opcao(estudo, inicio, fim) if do_aproveitamento else []
    if marcas:
        pontos = alt.Chart(pd.DataFrame(marcas)).encode(
            x="x:Q", y=alt.Y("y:Q", scale=escala_y), text="texto:N"
        )
        camadas.append(pontos.mark_point(filled=True, size=70, color=tinta.texto, clip=True))
        camadas.append(
            pontos.mark_text(dy=-12, fontSize=12, fontWeight=600, color=tinta.texto, clip=True)
        )
    camadas.append(
        base.mark_circle(opacity=0, size=500, clip=True).encode(
            tooltip=[
                alt.Tooltip("Curva:N", title="Curva"),
                alt.Tooltip("x:Q", title=titulo_x, format=".4g"),
                alt.Tooltip("y:Q", title=_rotulo_do_eixo_y(estudo, olhar), format=".4g"),
            ]
        )
    )
    st.altair_chart(alt.layer(*camadas).properties(height=300), width="stretch")


# ---------------------------------------------------------------------------
# Respostas
# ---------------------------------------------------------------------------


def _faixa_do_resumo(estudo: ed.Estudo) -> None:
    resumo = estudo.resumo()
    agora = ed.texto_do_aproveitamento(estudo.atual)
    if agora:
        resumo += f" Agora, com {estudo.texto_do_valor(estudo.medida.valor)}: {agora}."
    trava = estudo.quem_trava()
    if trava:
        resumo += f"  \nQuem trava: {trava}."
    if not estudo.tem_criterio:
        st.info(resumo, icon=":material/info:")
    elif estudo.util is None:
        st.error(resumo, icon=":material/cancel:")
    elif estudo.atual_passa:
        st.success(resumo, icon=":material/check_circle:")
    else:
        st.warning(resumo, icon=":material/warning:")


def _opcoes(caso: Caso, estudo: ed.Estudo, ao_usar: AoUsar) -> None:
    st.markdown("**Valores prontos para usar**")
    if not estudo.opcoes:
        st.caption("Nenhum limite apareceu nesta faixa. Mude o De e o Até para olhar mais longe.")
        return
    for posicao, opcao in enumerate(estudo.opcoes):
        texto = estudo.texto_do_valor(opcao.valor)
        aproveitamento = ed.texto_do_aproveitamento(opcao)
        detalhe = f"**{texto}**" + (f" · {aproveitamento}" if aproveitamento else "")
        with st.container(border=True):
            esquerda, direita = st.columns([5, 2], vertical_alignment="center")
            esquerda.markdown(f"{opcao.rotulo}  \n{detalhe}", help=opcao.ajuda or None)
            direita.button(
                "Usar",
                key=f"assistente_estudo_usar::{caso.id}::{posicao}",
                on_click=ao_usar,
                args=(caso, estudo.medida, opcao.valor, opcao.rotulo),
                disabled=opcao.valor == estudo.medida.valor,
                help=f"Passa {_nome(estudo.medida)} para {texto}. O botão Desfazer volta.",
            )


def _o_que_mais_pesa(caso: Caso, valores: Mapping[str, Any]) -> None:
    achados = _pesos_guardados(caso.id, assinatura(valores))
    if not achados:
        return
    st.markdown("**O que mais pesa no aproveitamento**")
    maior = max(abs(p.peso) for p in achados) or 1.0
    linhas = [
        {
            "Medida": _nome(p.medida),
            "Agora": f"{cd.numero(p.medida.valor)} {p.medida.unidade}".rstrip(),
            "Tipo": "Geometria" if p.de_geometria else "Carga ou material",
            "Peso": abs(p.peso),
            "O que ajuda": p.texto_do_efeito(),
        }
        for p in achados
    ]
    st.dataframe(
        pd.DataFrame(linhas),
        hide_index=True,
        width="stretch",
        column_config={
            "Peso": st.column_config.ProgressColumn(
                "Peso",
                help=(
                    "Quantos por cento o aproveitamento muda para cada 1 % na medida. "
                    "Peso 2 quer dizer que 1 % a mais na medida muda 2 % no aproveitamento."
                ),
                format="%.2f",
                min_value=0.0,
                max_value=float(maior),
            )
        },
    )
    st.caption(
        "Vale em volta dos números de agora: uma medida com peso zero é a que não governa hoje, "
        "e pode passar a governar se outra mudar."
    )


def _conteudo(
    caso: Caso, valores: Mapping[str, Any], medidas: list[CotaViva], ao_usar: AoUsar
) -> None:
    por_id = {medida.identidade: medida for medida in medidas}
    chave = _chave_da_medida(caso)
    _sem_escolha_velha(chave, por_id)
    manda = diagnostico_de(caso, valores).manda
    if chave not in st.session_state and manda is not None:
        # Começa onde dá para mexer: a primeira da lista costuma ser a carga, que vem dada.
        st.session_state[chave] = manda.medida.identidade
    colunas = st.columns([4, 3, 2, 2], vertical_alignment="bottom")
    identidade = colunas[0].selectbox(
        "Medida",
        list(por_id),
        format_func=lambda item: _nome(por_id[item]),
        key=chave,
        help="O número que vai variar. Os outros dados ficam como estão.",
    )
    medida = por_id[identidade]
    de = colunas[2].number_input(
        "De",
        value=None,
        placeholder="auto",
        format="%g",
        key=f"assistente_estudo_de::{caso.id}::{identidade}",
        help="Onde o estudo começa. Vazio: um oitavo do valor de agora.",
    )
    ate = colunas[3].number_input(
        "Até",
        value=None,
        placeholder="auto",
        format="%g",
        key=f"assistente_estudo_ate::{caso.id}::{identidade}",
        help="Onde o estudo termina. Vazio: oito vezes o valor de agora.",
    )
    if de is not None and ate is not None and de >= ate:
        colunas[1].warning("O De precisa ser menor que o Até.", icon=":material/warning:")
        return
    with st.spinner("Rodando o cálculo em vários valores..."):
        estudo = estudo_de(caso, valores, medida, de, ate)
    if estudo is None:
        return
    metricas = list(dict.fromkeys(nome for p in estudo.pontos for nome in p.metricas))
    opcoes = [APROVEITAMENTO, *metricas] if estudo.tem_criterio else metricas
    chave_olhar = f"assistente_estudo_olhar::{caso.id}"
    _sem_escolha_velha(chave_olhar, opcoes)
    if not opcoes:
        _faixa_do_resumo(estudo)
        return
    olhar = colunas[1].selectbox(
        "Olhar para",
        opcoes,
        key=chave_olhar,
        help="O que o gráfico mostra enquanto a medida varia.",
    )
    _faixa_do_resumo(estudo)
    grafico, prontos = st.columns([3, 2], gap="medium")
    with grafico:
        _grafico(estudo, olhar, de is not None or ate is not None)
    with prontos:
        _opcoes(caso, estudo, ao_usar)
    _o_que_mais_pesa(caso, valores)


def painel_de_estudo(caso: Caso, valores: Mapping[str, Any], ao_usar: AoUsar) -> None:
    medidas = cd.medidas_do_caso(caso, valores)
    if not medidas:
        return
    painel = st.expander(
        "Estudar uma medida",
        icon=":material/query_stats:",
        key=CHAVE_ABERTO,
        on_change="rerun",
    )
    if not painel.open:
        return
    with painel:
        _conteudo(caso, valores, medidas, ao_usar)
