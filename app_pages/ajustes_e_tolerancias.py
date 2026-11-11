"""Ajustes e tolerâncias: furo e eixo pela NBR 6158, o aperto de um ajuste prensado e a escolha."""

from __future__ import annotations

from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from components.assistente_cargas_ui import resposta, tabela_de_verificacoes
from components.edicao_de_tabela import com_edicoes
from components.project_tools import botao_registrar_calculo
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina, fronteira_modelo
from core import ajustes_e_tolerancias as at
from core import cadeia_de_cotas as cc
from core.elementos_base import Campo, Resultado
from core.memorial_verificacoes import decimal_ptbr

configurar_pagina(at.MODULO_TITULO, ":material/settings_input_component:")
cabecalho_pagina(
    at.MODULO_TITULO,
    "Furo e eixo pela NBR 6158: os limites de cada um, a folga ou a interferência, o aperto de "
    "um ajuste prensado e qual ajuste escolher para o torque.",
    categoria="Mecânica",
    icone=":material/settings_input_component:",
    modulo_id=at.MODULO_ID,
)

estado = st.session_state
RECOMENDADO = "Ajuste recomendado"
CLASSES = "Escolher as classes"
D = "aj_d"
MODO = "aj_modo"
NOME = "aj_recomendado"
FURO_LETRA, FURO_GRAU = "aj_furo_letra", "aj_furo_grau"
EIXO_LETRA, EIXO_GRAU = "aj_eixo_letra", "aj_eixo_grau"
CONSIDERAR = "aj_considerar_aperto"

for chave, padrao in (
    (D, 50.0),
    (MODO, RECOMENDADO),
    (NOME, "H7/s6"),
    (FURO_LETRA, "H"),
    (FURO_GRAU, 7),
    (EIXO_LETRA, "s"),
    (EIXO_GRAU, 6),
    (CONSIDERAR, True),
):
    estado.setdefault(chave, padrao)


def _chave_do_aperto(campo: Campo) -> str:
    return f"aj_ap_{campo.chave}"


def _usar(nome: str) -> None:
    """Botão "Usar este ajuste": a escolha volta para a aba Ajuste."""
    estado[MODO] = RECOMENDADO
    estado[NOME] = nome


def _entrada() -> at.Ajuste | None:
    esquerda, direita = st.columns([1, 2], gap="large")
    with esquerda:
        st.number_input(
            "Diâmetro nominal (mm)",
            min_value=0.1,
            max_value=at.DIMENSAO_MAXIMA,
            step=1.0,
            key=D,
            help="A medida do encaixe, a mesma para o furo e para o eixo. A norma aqui vai até 500 mm.",
        )
        st.radio(
            "Como escolher",
            (RECOMENDADO, CLASSES),
            key=MODO,
            horizontal=True,
            help="Um dos ajustes preferidos da norma, ou a classe do furo e a do eixo à mão.",
        )
    with direita:
        if estado[MODO] == RECOMENDADO:
            st.selectbox(
                "Ajuste",
                [a.nome for a in at.RECOMENDADOS],
                key=NOME,
                format_func=lambda nome: f"{nome} — {at.POR_NOME[nome].uso}",
                help="Furo-base (H no furo) é o mais comum: o furo sai com a ferramenta padrão.",
            )
        else:
            colunas = st.columns(4)
            colunas[0].selectbox(
                "Furo: letra",
                at.LETRAS_DE_FURO,
                key=FURO_LETRA,
                help="A posição do campo do furo. H começa na medida nominal.",
            )
            colunas[1].selectbox(
                "Furo: grau IT",
                at.GRAUS,
                key=FURO_GRAU,
                help="Quanto menor o grau, mais apertada a tolerância. Furo usinado: IT7 ou IT8.",
            )
            colunas[2].selectbox(
                "Eixo: letra",
                at.LETRAS_DE_EIXO,
                key=EIXO_LETRA,
                help="A posição do campo do eixo. De a até h, folga; de p em diante, interferência.",
            )
            colunas[3].selectbox(
                "Eixo: grau IT",
                at.GRAUS,
                key=EIXO_GRAU,
                help="Eixo retificado: IT5 ou IT6. Torneado fino: IT7.",
            )
    try:
        if estado[MODO] == RECOMENDADO:
            return at.ajuste_pelo_nome(float(estado[D]), str(estado[NOME]))
        return at.ajuste(
            float(estado[D]),
            f"{estado[FURO_LETRA]}{estado[FURO_GRAU]}",
            f"{estado[EIXO_LETRA]}{estado[EIXO_GRAU]}",
        )
    except at.ErroDeAjuste as erro:
        st.warning(str(erro), icon=":material/warning:")
        return None


def _faixa(a: at.Ajuste) -> None:
    texto = at.resumo(a)
    if a.tipo == at.COM_FOLGA:
        st.success(texto, icon=":material/swap_horiz:")
    elif a.tipo == at.COM_INTERFERENCIA:
        st.info(texto, icon=":material/compress:")
    else:
        st.warning(
            texto
            + " Pode sair com folga ou com interferência, conforme as peças que se encontrarem.",
            icon=":material/help:",
        )


def _grafico(a: at.Ajuste) -> None:
    quadro = pd.DataFrame(
        [
            {
                "Peça": f"Furo {a.furo.classe.nome}",
                "De": a.furo.inferior,
                "Até": a.furo.superior,
                "Tipo": "Furo",
            },
            {
                "Peça": f"Eixo {a.eixo.classe.nome}",
                "De": a.eixo.inferior,
                "Até": a.eixo.superior,
                "Tipo": "Eixo",
            },
        ]
    )
    barras = (
        alt.Chart(quadro)
        .mark_bar(size=46, cornerRadius=3)
        .encode(
            x=alt.X(
                "Peça:N",
                title=None,
                axis=alt.Axis(labelAngle=0),
                sort=list(quadro["Peça"]),  # o furo primeiro, como se lê o ajuste
            ),
            y=alt.Y("De:Q", title="Afastamento da medida nominal (µm)"),
            y2="Até:Q",
            color=alt.Color(
                "Tipo:N",
                scale=alt.Scale(domain=["Furo", "Eixo"], range=["#2a78b5", "#d9822b"]),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[
                alt.Tooltip("Peça:N"),
                alt.Tooltip("Até:Q", title="Superior (µm)"),
                alt.Tooltip("De:Q", title="Inferior (µm)"),
            ],
        )
    )
    zero = (
        alt.Chart(pd.DataFrame({"y": [0.0]}))
        .mark_rule(strokeDash=[5, 4], color="#7a7a7a")
        .encode(y="y:Q")
    )
    st.altair_chart((zero + barras).properties(height=260), width="stretch")
    st.caption(
        f"A linha tracejada é a medida nominal, Ø{at.numero(a.d)} mm. Onde a barra do eixo passa da "
        "do furo há interferência; onde fica abaixo, folga."
    )


def _como_saiu(a: at.Ajuste) -> None:
    linhas = []
    for peca, z in (("Furo", a.furo), ("Eixo", a.eixo)):
        it = at.tolerancia(z.classe.grau, a.d)
        linhas.append(
            f"- **{peca} {z.classe.nome}:** IT{z.classe.grau} = {at.numero(it, 1)} µm na faixa de "
            f"{at.numero(at.faixa(a.d)[0])} a {at.numero(at.faixa(a.d)[1])} mm (Tabela 1). "
            f"Afastamentos {at.numero(z.superior, 1)} e {at.numero(z.inferior, 1)} µm "
            f"({'Tabela 3' if peca == 'Furo' else 'Tabela 2'})."
        )
    linhas.append(
        f"- **Folga máxima** = afastamento superior do furo − inferior do eixo = "
        f"{at.numero(a.folga_maxima, 1)} µm."
    )
    linhas.append(
        f"- **Folga mínima** = afastamento inferior do furo − superior do eixo = "
        f"{at.numero(a.folga_minima, 1)} µm. Negativo quer dizer interferência."
    )
    st.markdown("\n".join(linhas))


def _aba_ajuste(a: at.Ajuste) -> None:
    _faixa(a)
    colunas = st.columns(4)
    colunas[0].metric("Tipo", a.tipo, help="Com folga, incerto ou com interferência.")
    if a.tipo == at.COM_INTERFERENCIA:
        colunas[1].metric(
            "Interferência mínima",
            f"{at.numero(a.interferencia_minima, 1)} µm",
            help="Furo no máximo e eixo no mínimo: o menor aperto possível.",
        )
        colunas[2].metric(
            "Interferência máxima",
            f"{at.numero(a.interferencia_maxima, 1)} µm",
            help="Furo no mínimo e eixo no máximo: o maior aperto possível.",
        )
    else:
        colunas[1].metric(
            "Folga mínima",
            f"{at.numero(a.folga_minima, 1)} µm",
            help="Furo no mínimo e eixo no máximo. Negativo quer dizer interferência.",
        )
        colunas[2].metric(
            "Folga máxima",
            f"{at.numero(a.folga_maxima, 1)} µm",
            help="Furo no máximo e eixo no mínimo.",
        )
    colunas[3].metric("Sistema", a.sistema, help="Furo-base: H no furo. Eixo-base: h no eixo.")
    st.dataframe(pd.DataFrame(at.linhas_das_zonas(a)), hide_index=True, width="stretch")
    st.markdown("**No desenho**")
    st.code(f"{at.cota_do_desenho(a.furo)}\n{at.cota_do_desenho(a.eixo)}", language=None)
    _grafico(a)
    with st.expander("Como saiu cada número", icon=":material/list_alt:"):
        _como_saiu(a)


def _campo_do_aperto(campo: Campo) -> None:
    chave = _chave_do_aperto(campo)
    estado.setdefault(chave, float(campo.padrao))  # type: ignore[arg-type]
    st.number_input(
        campo.rotulo_completo,
        min_value=campo.minimo,
        max_value=campo.maximo,
        step=campo.passo,
        key=chave,
        help=campo.ajuda,
    )


def _valores_do_aperto() -> dict[str, Any]:
    return {
        campo.chave: estado.get(_chave_do_aperto(campo), campo.padrao)
        for campo in at.CAMPOS_DO_APERTO
    }


def _aba_aperto(a: at.Ajuste) -> Resultado | None:
    if a.tipo != at.COM_INTERFERENCIA:
        st.info(
            f"O ajuste {a.nome} é {a.tipo.lower()}: ele não tem interferência garantida, e o atrito "
            "não segura nada. Para transmitir torque pelo aperto, escolha um ajuste com "
            "interferência, ou veja a aba Escolher o ajuste.",
            icon=":material/info:",
        )
        return None
    secoes: dict[str, list[Campo]] = {}
    for campo in at.CAMPOS_DO_APERTO:
        nome = "Rugosidade" if campo.secao == "Ajuste" else (campo.secao or "Dados")
        secoes.setdefault(nome, []).append(campo)
    colunas = st.columns(3, gap="medium")
    for i, (secao, campos) in enumerate(secoes.items()):
        with colunas[i % 3]:
            st.markdown(f"**{secao}**")
            for campo in campos:
                _campo_do_aperto(campo)
    try:
        r = at.aperto(a, _valores_do_aperto())
    except ValueError as erro:
        st.warning(str(erro), icon=":material/warning:")
        return None
    resposta(r, por_linha=4)
    tabela_de_verificacoes(r)
    with st.expander("Hipóteses do aperto", icon=":material/rule:"):
        st.markdown("\n".join(f"- {decimal_ptbr(h)}" for h in r.hipoteses))
    return r


def _sim_nao(valor: bool | None) -> str:
    return "—" if valor is None else ("Sim" if valor else "Não")


def _faixa_do_ajuste(a: at.Ajuste) -> str:
    if a.tipo == at.COM_FOLGA:
        return f"folga de {at.numero(a.folga_minima, 1)} a {at.numero(a.folga_maxima, 1)}"
    if a.tipo == at.COM_INTERFERENCIA:
        return (
            f"interferência de {at.numero(a.interferencia_minima, 1)} a "
            f"{at.numero(a.interferencia_maxima, 1)}"
        )
    return (
        f"de {at.numero(a.interferencia_maxima, 1)} de interferência a "
        f"{at.numero(a.folga_maxima, 1)} de folga"
    )


def _aba_escolher(a: at.Ajuste) -> None:
    st.toggle(
        "Conferir o aperto com os dados da aba Aperto e montagem",
        key=CONSIDERAR,
        help="Com isto ligado, cada ajuste com interferência é testado no torque e no escoamento.",
    )
    valores = _valores_do_aperto() if estado[CONSIDERAR] else None
    escolhas = at.escolher(a.d, valores)
    if not escolhas:
        st.info("Nenhum ajuste recomendado existe nesta medida.", icon=":material/info:")
        return
    quadro = pd.DataFrame(
        [
            {
                "Ajuste": e.ajuste.nome,
                "Tipo": e.ajuste.tipo,
                "Faixa (µm)": _faixa_do_ajuste(e.ajuste),
                "Segura": _sim_nao(e.transmite),
                "Escoa": _sim_nao(e.escoa),
                "Aquecer (°C)": "—" if e.aquecimento is None else at.numero(e.aquecimento, 0),
                "Uso": e.uso,
            }
            for e in escolhas
        ]
    )
    if valores is None:
        quadro = quadro.drop(columns=["Segura", "Escoa", "Aquecer (°C)"])
    st.dataframe(
        quadro,
        hide_index=True,
        width="stretch",
        height=35 * (len(quadro) + 1) + 3,  # todas as linhas, sem rolar dentro da tabela
        column_config={
            "Ajuste": st.column_config.TextColumn(width="small"),
            "Tipo": st.column_config.TextColumn(width="medium"),
            "Faixa (µm)": st.column_config.TextColumn(width="medium"),
            "Segura": st.column_config.TextColumn(
                width="small", help="Segura o torque e a força axial pelo atrito, com o fator."
            ),
            "Escoa": st.column_config.TextColumn(
                width="small", help="O furo do cubo ou o eixo escoa com a maior interferência."
            ),
            "Aquecer (°C)": st.column_config.TextColumn(
                width="medium", help="Quanto aquecer o cubo para montar a quente."
            ),
            "Uso": st.column_config.TextColumn(width="large"),
        },
    )
    if valores is None:
        return
    melhor = at.melhor_que_segura(escolhas)
    if melhor is None:
        st.warning(
            "Nenhum ajuste recomendado segura o torque sem escoar o cubo ou o eixo. Aumente o "
            "comprimento do ajuste ou o diâmetro do cubo, ou use chaveta.",
            icon=":material/warning:",
        )
        return
    st.success(
        f"O mais leve que segura o torque sem escoar: **{melhor.ajuste.nome}** "
        f"({_faixa_do_ajuste(melhor.ajuste)} µm). Menos aperto é montagem mais fácil.",
        icon=":material/check_circle:",
    )
    st.button(
        f"Usar {melhor.ajuste.nome}",
        key="aj_usar_melhor",
        on_click=_usar,
        args=(melhor.ajuste.nome,),
        help="Leva este ajuste para as abas Ajuste e Aperto e montagem.",
    )


# ---------------------------------------------------------------------------------------------
# Cadeia de cotas
# ---------------------------------------------------------------------------------------------

CADEIA = "aj_cadeia"
CADEIA_REV = "aj_cadeia_rev"
FOLGA_MIN, FOLGA_MAX = "aj_cadeia_min", "aj_cadeia_max"
estado.setdefault(CADEIA, [dict(linha) for linha in cc.EXEMPLO])
estado.setdefault(FOLGA_MIN, 0.05)
estado.setdefault(FOLGA_MAX, None)


def _ao_editar_cadeia(chave: str) -> None:
    estado[CADEIA] = cc.da_tela(
        com_edicoes(cc.para_a_tela(estado[CADEIA]), estado.get(chave) or {})
    )
    estado[CADEIA_REV] = estado.get(CADEIA_REV, 0) + 1


def _voltar_ao_exemplo_da_cadeia() -> None:
    estado[CADEIA] = [dict(linha) for linha in cc.EXEMPLO]
    estado[CADEIA_REV] = estado.get(CADEIA_REV, 0) + 1


def _mm(valor: float) -> str:
    return f"{at.numero(valor, 3)} mm"


def _aba_cadeia() -> cc.Cadeia | None:
    st.markdown(
        "Ponha as medidas em fila. A que **aumenta** a folga (a largura do alojamento) e as que a "
        "**diminuem** (rolamentos, espaçadores, anéis). Com uma **classe ISO** (h11, js9…), os "
        "afastamentos saem da NBR 6158; sem ela, valem os afastamentos da linha."
    )
    chave = f"aj_cadeia_tabela_{estado.get(CADEIA_REV, 0)}"
    st.data_editor(
        pd.DataFrame(cc.para_a_tela(estado[CADEIA]), columns=list(cc.COLUNAS_DA_TELA.values())),
        key=chave,
        on_change=_ao_editar_cadeia,
        args=(chave,),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "Elo": st.column_config.TextColumn(width="medium"),
            "Sentido": st.column_config.SelectboxColumn(
                options=list(cc.SENTIDOS), required=True, width="medium"
            ),
            "Nominal (mm)": st.column_config.NumberColumn(format="%.3f", min_value=0.0),
            "Classe ISO": st.column_config.TextColumn(
                help="Opcional: a classe da NBR 6158 (h11, H8, js9…). Vazia, valem os afastamentos."
            ),
            "Afast. superior (mm)": st.column_config.NumberColumn(format="%.3f"),
            "Afast. inferior (mm)": st.column_config.NumberColumn(format="%.3f"),
        },
    )
    colunas = st.columns([1, 1, 1])
    colunas[0].number_input(
        "Folga mínima exigida (mm)",
        value=None,
        step=0.01,
        format="%.3f",
        key=FOLGA_MIN,
        help="A menor folga que a montagem aceita. Negativa quer dizer aperto. Vazio: sem limite.",
    )
    colunas[1].number_input(
        "Folga máxima aceita (mm)",
        value=None,
        step=0.01,
        format="%.3f",
        key=FOLGA_MAX,
        help="A maior folga que a montagem aceita (folga axial do eixo, por exemplo). Vazio: sem limite.",
    )
    colunas[2].button(
        "Voltar ao exemplo",
        on_click=_voltar_ao_exemplo_da_cadeia,
        key="aj_cadeia_exemplo",
        help="Volta a tabela ao exemplo da caixa com dois rolamentos e um espaçador.",
    )
    try:
        cadeia = cc.montar(estado[CADEIA], estado.get(FOLGA_MIN), estado.get(FOLGA_MAX))
    except cc.ErroDaCadeia as erro:
        st.warning(str(erro), icon=":material/warning:")
        return None
    metricas = st.columns(3)
    metricas[0].metric(
        "Folga nominal",
        _mm(cadeia.nominal),
        help="Só as medidas nominais, com o sentido de cada uma.",
    )
    metricas[1].metric(
        "Pior caso",
        f"{at.numero(cadeia.pior_minima, 3)} a {at.numero(cadeia.pior_maxima, 3)} mm",
        help="Todas as peças no limite que mais atrapalha ao mesmo tempo. Sempre fica dentro.",
    )
    metricas[2].metric(
        "Estatístico (±3σ)",
        f"{at.numero(cadeia.estatistica_minima, 3)} a {at.numero(cadeia.estatistica_maxima, 3)} mm",
        help="99,73 % das montagens, com cada tolerância = ±3σ. Vale para fabricação em série.",
    )
    _resultado_da_cadeia(cadeia)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Elo": c.elo.nome,
                    "Sentido": "+" if c.elo.sinal > 0 else "−",
                    "Medida (mm)": f"{at.numero(c.elo.nominal, 3)} "
                    f"({at.numero(c.elo.superior, 3)} / {at.numero(c.elo.inferior, 3)})"
                    + (f" {c.elo.classe}" if c.elo.classe else ""),
                    "Tolerância (mm)": at.numero(c.elo.tolerancia, 3),
                    "Peso no pior caso": f"{at.numero(100 * c.no_pior_caso, 1)} %",
                    "Peso na variação": f"{at.numero(100 * c.na_variancia, 1)} %",
                }
                for c in cadeia.contribuicoes
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    primeiro = cadeia.contribuicoes[0]
    if primeiro.na_variancia > 0:
        st.caption(
            f"Quem mais pesa é **{primeiro.elo.nome}**, com {at.numero(100 * primeiro.na_variancia, 0)} % "
            "da variação: apertar a tolerância dela é o que mais estreita a folga."
        )
    return cadeia


def _resultado_da_cadeia(cadeia: cc.Cadeia) -> None:
    if cadeia.pior_caso_atende is None:
        st.info(
            "Informe a folga mínima ou a máxima para o programa dizer se a cadeia atende.",
            icon=":material/info:",
        )
        return
    abaixo, acima = cadeia.fora_abaixo(), cadeia.fora_acima()
    fora = (abaixo or 0.0) + (acima or 0.0)
    if cadeia.pior_caso_atende:
        st.success(
            "Atende no pior caso: toda montagem fica dentro da folga exigida.",
            icon=":material/check_circle:",
        )
    elif cadeia.estatistico_atende:
        st.warning(
            "Não atende no pior caso, mas atende no estatístico: em série, cerca de "
            f"{at.numero(100 * fora, 3)} % das montagens sairiam da folga exigida. Para poucas "
            "peças, aperte as tolerâncias.",
            icon=":material/warning:",
        )
    else:
        st.error(
            f"Não atende: cerca de {at.numero(100 * fora, 2)} % das montagens sairiam da folga "
            "exigida. Aperte a tolerância de quem mais pesa, ou mude uma medida nominal.",
            icon=":material/error:",
        )


with secao_protegida(at.MODULO_TITULO):
    aba_furo_eixo, aba_cadeia = st.tabs(["Furo e eixo", "Cadeia de cotas"])
    with aba_furo_eixo:
        ajuste_escolhido = _entrada()
        if ajuste_escolhido is not None:
            aba_ajuste, aba_aperto, aba_escolher = st.tabs(
                ["Ajuste", "Aperto e montagem", "Escolher o ajuste"]
            )
            aperto_calculado: Resultado | None = None
            with aba_ajuste:
                _aba_ajuste(ajuste_escolhido)
            with aba_aperto:
                aperto_calculado = _aba_aperto(ajuste_escolhido)
            with aba_escolher:
                _aba_escolher(ajuste_escolhido)
            st.divider()
            botao_registrar_calculo(
                at.registro(
                    ajuste_escolhido,
                    aperto_calculado,
                    _valores_do_aperto() if aperto_calculado is not None else None,
                ),
                key="aj_registrar",
            )
    with aba_cadeia:
        cadeia_montada = _aba_cadeia()
        if cadeia_montada is not None:
            st.divider()
            botao_registrar_calculo(cc.registro(cadeia_montada), key="aj_cadeia_registrar")

fronteira_modelo(
    [
        "Tolerâncias e afastamentos da NBR 6158 (ISO 286-1), de 0 a 500 mm, com as peças a 20 °C.",
        "Letras de uso raro (cd, ef, fg, j, v a zc) ficaram de fora.",
        "O aperto é o mesmo cálculo de Lamé da página Cálculo de peças: cilindros longos, regime elástico, "
        "sem força centrífuga.",
        "Cadeia de cotas estatística: medidas independentes, cada tolerância = ±3σ de um processo "
        "centrado. Para poucas peças, vale o pior caso.",
    ],
    titulo="Hipóteses desta página",
)
