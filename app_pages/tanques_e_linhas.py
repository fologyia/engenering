"""Tanques e linhas no tempo: o nível, a temperatura e a vazão andando, em animação.

Quatro abas: nível do tanque, temperatura do tanque, partida da linha e água quente chegando num
tubo frio. As contas estão em ``core.tanque_no_tempo`` e ``core.linha_no_tempo``; a cena do tocador
e o registro em ``core.fluidos_cenas``.
"""

from __future__ import annotations

import numpy as np
import streamlit as st

from components.animacao_ui import tocador
from components.project_tools import botao_registrar_calculo
from components.robustez import secao_protegida
from components.tanques_e_linhas_help import AJUDA
from components.ui import cabecalho_pagina, configurar_pagina
from components.verification_table import mostrar_tabela_verificacoes
from core import calor_no_tempo as ct
from core import fluidos_cenas as fc
from core import linha_no_tempo as ln
from core import montador_fluidos as fl
from core import tanque_no_tempo as tq
from core.animacao import tempo_em_texto, unidade_de_tempo

ICONE = ":material/water_full:"
configurar_pagina("Tanques e linhas no tempo", ICONE)
cabecalho_pagina(
    "Tanques e linhas no tempo",
    "Veja o que acontece com o tempo passando: um tanque enchendo, esvaziando ou esquentando, a "
    "água acelerando quando a válvula abre ou a bomba liga, e a água quente chegando num tubo "
    "frio. Tudo em animação, com as curvas no tempo ao lado.",
    categoria="Mecânica",
    icone=ICONE,
    modulo_id=fc.MODULO_ID,
)
st.page_link(
    "app_pages/montador_fluidos.py",
    label="Ir para o Montador de fluidos (regime permanente, NPSH e golpe de aríete)",
    icon=":material/water_drop:",
)

AUTOMATICO = "Automático"
INFORMADO = "Informar o tempo"
UNIDADES = {"s": 1.0, "min": 60.0, "h": 3600.0}
FORMAS = {
    "Cilíndrico vertical": tq.VERTICAL,
    "Retangular": tq.RETANGULAR,
    "Cilíndrico horizontal": tq.HORIZONTAL,
}
SAIDAS = {
    "Orifício no fundo": tq.ORIFICIO,
    "Tubo saindo do fundo": tq.TUBO,
    "Bomba de vazão fixa": tq.BOMBA,
    "Nenhuma (só enche)": tq.SEM_SAIDA,
    "Tubo para outro tanque (vasos comunicantes)": "vasos",
}
AQUECIMENTOS = {
    "Resistência (potência fixa)": tq.POTENCIA,
    "Serpentina ou camisa": tq.SERPENTINA,
    "Nenhum": tq.NENHUM,
}
EVENTOS = {"Abrir a válvula": ln.VALVULA, "Ligar a bomba": ln.BOMBA}
AGUA_COOLPROP = "Água (CoolProp)"
INFORMAR = "Informar"
_N = tq._n


def _mostrar_erros(erros: list[str]) -> None:
    for erro in erros:
        st.error(erro, icon=":material/error:")


def _numero(rotulo: str, chave: str, valor: float, ajuda: str, **opcoes: object) -> float:
    lugar = opcoes.pop("lugar", st)
    return float(
        lugar.number_input(
            rotulo, value=valor, key=chave, help=ajuda, persist_state="session", **opcoes
        )  # type: ignore[attr-defined]
    )


def _duracao(prefixo: str, colunas: list) -> float | None:  # noqa: ANN001
    modo = colunas[0].radio(
        "Duração", [AUTOMATICO, INFORMADO], key=f"{prefixo}_modo", help=AJUDA["duracao_modo"]
    )
    if modo == AUTOMATICO:
        return None
    valor = colunas[1].number_input(
        "Tempo", min_value=0.001, value=30.0, step=5.0, format="%.4g", key=f"{prefixo}_dur",
        persist_state="session", help=AJUDA["duracao"],
    )  # fmt: skip
    unidade = colunas[2].selectbox(
        "Unidade", list(UNIDADES), index=1, key=f"{prefixo}_dur_u", persist_state="session",
        help=AJUDA["duracao_unidade"],
    )  # fmt: skip
    return float(valor) * UNIDADES[unidade]


def _fluido(prefixo: str, lugar) -> tuple[float, float]:  # noqa: ANN001
    nome = lugar.selectbox(
        "Líquido", [*fl.FLUIDOS_TIPICOS], index=0, key=f"{prefixo}_fluido", persist_state="session",
        help=AJUDA["fluido"],
    )  # fmt: skip
    rho, mu, _ = fl.FLUIDOS_TIPICOS[nome]
    return float(rho), float(mu)


@st.cache_data(show_spinner=False, max_entries=6)
def _nivel(tanque: tq.Tanque, duracao: float | None) -> tq.ResultadoDoNivel:
    return tq.calcular_nivel(tanque, duracao)


@st.cache_data(show_spinner=False, max_entries=6)
def _vasos(vasos: tq.Vasos, duracao: float | None) -> tq.ResultadoDosVasos:
    return tq.calcular_vasos(vasos, duracao)


@st.cache_data(show_spinner=False, max_entries=6)
def _termico(tanque: tq.TanqueTermico, duracao: float | None) -> tq.ResultadoTermico:
    return tq.calcular_termico(tanque, duracao)


@st.cache_data(show_spinner=False, max_entries=6)
def _partida(linha: ln.Linha, duracao: float | None) -> ln.ResultadoDaPartida:
    return ln.calcular_partida(linha, duracao)


@st.cache_data(show_spinner=False, max_entries=6)
def _tubo(tubo: ln.TuboAquecendo, duracao: float | None) -> ln.ResultadoDoTubo:
    return ln.calcular_tubo(tubo, duracao)


# =============================================================================================
# Nível
# =============================================================================================
def aba_do_nivel() -> None:
    with st.container(border=True), secao_protegida("Tanque"):
        st.subheader("Tanque", help=AJUDA["sec_tanque"])
        c = st.columns(5)
        forma = FORMAS[
            c[0].selectbox(
                "Forma", list(FORMAS), key="tqn_forma", persist_state="session", help=AJUDA["forma"]
            )
        ]
        altura = diametro = comprimento = largura = 0.0
        if forma != tq.HORIZONTAL:
            altura = _numero(
                "Altura (m)", "tqn_h", 3.0, AJUDA["altura"], min_value=0.01, step=0.5, lugar=c[1]
            )
        if forma in (tq.VERTICAL, tq.HORIZONTAL):
            diametro = _numero(
                "Diâmetro (m)",
                "tqn_d",
                2.0,
                AJUDA["diametro"],
                min_value=0.01,
                step=0.5,
                lugar=c[2],
            )
        if forma in (tq.RETANGULAR, tq.HORIZONTAL):
            comprimento = _numero(
                "Comprimento (m)",
                "tqn_c",
                3.0,
                AJUDA["comprimento"],
                min_value=0.01,
                step=0.5,
                lugar=c[2 if forma == tq.RETANGULAR else 1],
            )
        if forma == tq.RETANGULAR:
            largura = _numero(
                "Largura (m)", "tqn_l", 2.0, AJUDA["largura"], min_value=0.01, step=0.5, lugar=c[3]
            )
        nivel = _numero(
            "Nível inicial (m)",
            "tqn_h0",
            2.5,
            AJUDA["nivel_inicial"],
            min_value=0.0,
            step=0.1,
            lugar=c[4],
        )
        entrada = _numero(
            "Entrada (L/s)", "tqn_qe", 0.0, AJUDA["entrada"], min_value=0.0, step=0.5, lugar=c[4]
        )
    with st.container(border=True), secao_protegida("Saída"):
        st.subheader("Saída", help=AJUDA["sec_saida"])
        c = st.columns(5)
        tipo = SAIDAS[
            c[0].selectbox(
                "Saída", list(SAIDAS), key="tqn_saida", persist_state="session", help=AJUDA["saida"]
            )
        ]
        saida = tq.Saida(tipo)
        if tipo == tq.ORIFICIO:
            saida = tq.Saida(
                tipo,
                diametro_mm=_numero(
                    "Diâmetro do furo (mm)",
                    "tqn_do",
                    50.0,
                    AJUDA["d_saida"],
                    min_value=0.1,
                    step=5.0,
                    lugar=c[1],
                ),
                cd=_numero(
                    "C_d",
                    "tqn_cd",
                    tq.CD_ORIFICIO,
                    AJUDA["cd"],
                    min_value=0.01,
                    max_value=1.0,
                    step=0.01,
                    lugar=c[2],
                ),
            )
        elif tipo in (tq.TUBO, "vasos"):
            rho, mu = _fluido("tqn", c[4])
            material = c[2].selectbox(
                "Material",
                list(fl.RUGOSIDADES),
                key="tqn_mat",
                persist_state="session",
                help=AJUDA["material_tubo"],
            )
            saida = tq.Saida(
                tipo,
                diametro_mm=_numero(
                    "Diâmetro interno (mm)",
                    "tqn_dt",
                    50.0,
                    AJUDA["d_saida"],
                    min_value=0.1,
                    step=5.0,
                    lugar=c[1],
                ),
                comprimento_m=_numero(
                    "Comprimento (m)",
                    "tqn_lt",
                    10.0,
                    AJUDA["l_tubo"],
                    min_value=0.01,
                    step=1.0,
                    lugar=c[1],
                ),
                rugosidade_mm=fl.RUGOSIDADES[material] * 1000.0,
                k_local=_numero(
                    "ΣK das peças",
                    "tqn_k",
                    0.5,
                    AJUDA["k_tubo"],
                    min_value=0.0,
                    step=0.1,
                    lugar=c[3],
                ),
                desnivel_m=0.0
                if tipo == "vasos"
                else _numero(
                    "Ponta abaixo do fundo (m)",
                    "tqn_z",
                    1.0,
                    AJUDA["desnivel"],
                    step=0.5,
                    lugar=c[3],
                ),
                massa_especifica=rho,
                viscosidade=mu,
            )
        elif tipo == tq.BOMBA:
            saida = tq.Saida(
                tipo,
                vazao_bomba_L_s=_numero(
                    "Vazão da bomba (L/s)",
                    "tqn_qb",
                    5.0,
                    AJUDA["q_bomba"],
                    min_value=0.0,
                    step=0.5,
                    lugar=c[1],
                ),
            )
    segundo: tq.Tanque | None = None
    cota_2 = 0.0
    if tipo == "vasos":
        with st.container(border=True), secao_protegida("Tanque 2"):
            st.subheader("Tanque 2 (cilíndrico vertical)", help=AJUDA["sec_tanque2"])
            c = st.columns(4)
            d2 = _numero(
                "Diâmetro (m)", "tqn_d2", 1.5, AJUDA["d2"], min_value=0.01, step=0.5, lugar=c[0]
            )
            h2 = _numero(
                "Altura (m)", "tqn_h2", 3.0, AJUDA["h2"], min_value=0.01, step=0.5, lugar=c[1]
            )
            n2 = _numero(
                "Nível inicial (m)",
                "tqn_n2",
                0.3,
                AJUDA["nivel2"],
                min_value=0.0,
                step=0.1,
                lugar=c[2],
            )
            cota_2 = _numero(
                "Fundo acima do fundo do 1 (m)", "tqn_z2", 0.0, AJUDA["cota2"], step=0.5, lugar=c[3]
            )
            segundo = tq.Tanque(tq.VERTICAL, h2, d2, nivel_inicial_m=n2)
    with st.container(border=True), secao_protegida("Tempo e pergunta do nível"):
        st.subheader("Tempo e pergunta", help=AJUDA["sec_tempo"])
        c = st.columns([1.3, 1, 0.7, 1.1])
        duracao = _duracao("tqn", c)
        alvo = c[3].number_input(
            "Nível a alcançar (m)",
            value=None,
            min_value=0.0,
            step=0.1,
            placeholder="sem pergunta",
            key="tqn_alvo",
            help=AJUDA["alvo_nivel"],
        )
    if segundo is not None:
        primeiro = tq.Tanque(forma, altura, diametro, comprimento, largura, nivel, entrada)
        with st.container(border=True), secao_protegida("Resultado dos vasos"):
            st.subheader("Os dois tanques no tempo", help=AJUDA["sec_resultado"])
            _resultado_dos_vasos(tq.Vasos(primeiro, segundo, cota_2, saida), duracao)
        return
    tanque = tq.Tanque(forma, altura, diametro, comprimento, largura, nivel, entrada, saida)
    with st.container(border=True), secao_protegida("Resultado do nível"):
        st.subheader("O tanque no tempo", help=AJUDA["sec_resultado"])
        erros = tq.problemas_do_nivel(tanque)
        if erros:
            _mostrar_erros(erros)
            return
        try:
            r = _nivel(tanque, duracao)
        except tq.ErroDoTanque as erro:
            _mostrar_erros([str(erro)])
            return
        u = unidade_de_tempo(r.duracao)
        m = st.columns(4)
        rotulo = {"vazio": "Esvazia em", "cheio": "Transborda em", "estavel": "Estabiliza em"}.get(
            r.evento, "Tempo mostrado"
        )
        m[0].metric(rotulo, tempo_em_texto(r.duracao, u), help=AJUDA["res_tempo"])
        m[1].metric(
            "Nível no fim", f"{_N(float(r.niveis[-1]), 3)} m", help=AJUDA["res_nivel_final"]
        )
        m[2].metric(
            "Nível de equilíbrio",
            "—" if r.nivel_de_equilibrio is None else f"{_N(r.nivel_de_equilibrio, 3)} m",
            help=AJUDA["res_equilibrio"],
        )
        if alvo is not None:
            ta = r.tempo_para(float(alvo))
            m[3].metric(
                f"Nível a {_N(float(alvo), 2)} m",
                "não chega" if ta is None else tempo_em_texto(ta, u),
                help=AJUDA["res_alvo_nivel"],
            )
        else:
            m[3].metric(
                "Maior saída", f"{_N(float(r.saida.max()), 2)} L/s", help=AJUDA["res_saida_max"]
            )
        for aviso in r.avisos:
            st.warning(aviso, icon=":material/warning:")
        tocador(fc.cena_do_nivel(r, None if alvo is None else float(alvo)), key="tqn_tocador")
        with st.expander("Hipóteses da conta"):
            for linha in tq.hipoteses_do_nivel(r):
                st.markdown(f"- {linha}")
        st.subheader("Registrar no projeto", help=AJUDA["registrar"])
        botao_registrar_calculo(
            fc.registro_do_nivel(r, None if alvo is None else float(alvo)),
            key="registrar_tanque_nivel",
            rotulo="Registrar no projeto ativo",
        )


def _resultado_dos_vasos(vasos: tq.Vasos, duracao: float | None) -> None:
    erros = tq.problemas_dos_vasos(vasos)
    if erros:
        _mostrar_erros(erros)
        return
    try:
        r = _vasos(vasos, duracao)
    except tq.ErroDoTanque as erro:
        _mostrar_erros([str(erro)])
        return
    u = unidade_de_tempo(r.duracao)
    m = st.columns(4)
    m[0].metric(
        "Equaliza em",
        tempo_em_texto(r.duracao, u) if r.evento == "equalizou" else "não equaliza",
        help=AJUDA["res_equaliza"],
    )
    m[1].metric(
        "Nível igual (cota)",
        "—" if r.superficie_de_equilibrio is None else f"{_N(r.superficie_de_equilibrio, 3)} m",
        help=AJUDA["res_nivel_igual"],
    )
    m[2].metric(
        "Diferença no começo",
        f"{_N(abs(float(r.diferenca[0])), 3)} m",
        help=AJUDA["res_diferenca0"],
    )
    m[3].metric(
        "Maior vazão", f"{_N(float(np.max(np.abs(r.vazao))), 2)} L/s", help=AJUDA["res_vazao_max"]
    )
    for aviso in r.avisos:
        st.warning(aviso, icon=":material/warning:")
    tocador(fc.cena_dos_vasos(r), key="tqn_vasos_tocador")
    with st.expander("Hipóteses da conta"):
        for linha in tq.hipoteses_dos_vasos(r):
            st.markdown(f"- {linha}")
    st.subheader("Registrar no projeto", help=AJUDA["registrar"])
    botao_registrar_calculo(
        fc.registro_dos_vasos(r), key="registrar_vasos", rotulo="Registrar no projeto ativo"
    )


# =============================================================================================
# Temperatura
# =============================================================================================
def aba_da_temperatura() -> None:
    with st.container(border=True), secao_protegida("Tanque e líquido"):
        st.subheader("Tanque e líquido", help=AJUDA["sec_termico"])
        c = st.columns(4)
        volume = _numero(
            "Volume de líquido (m³)",
            "tqt_v",
            2.0,
            AJUDA["volume"],
            min_value=0.0001,
            step=0.5,
            lugar=c[0],
        )
        liquido = c[1].selectbox(
            "Líquido",
            [AGUA_COOLPROP, INFORMAR],
            key="tqt_liq",
            persist_state="session",
            help=AJUDA["liquido"],
        )
        t0 = _numero(
            "Temperatura inicial (°C)", "tqt_t0", 20.0, AJUDA["t_inicial"], step=5.0, lugar=c[3]
        )
        agua = liquido == AGUA_COOLPROP
        if agua:
            rho, cp = tq.propriedades_da_agua(min(max(t0, 0.5), 99.0))
            c[2].caption(
                f"ρ = {_N(rho, 1)} kg/m³\n\nc_p = {_N(cp, 0)} J/(kg·K)\n\na {_N(t0, 1)} °C, 1 atm"
            )
        else:
            rho = _numero("ρ (kg/m³)", "tqt_rho", 870.0, AJUDA["rho"], min_value=0.01, lugar=c[2])
            cp = _numero(
                "c_p (J/(kg·K))", "tqt_cp", 2000.0, AJUDA["cp_liquido"], min_value=0.01, lugar=c[2]
            )
    with st.container(border=True), secao_protegida("Aquecimento, perda e vazão"):
        st.subheader("Aquecimento, perda e vazão", help=AJUDA["sec_termico"])
        c = st.columns(4)
        tipo = AQUECIMENTOS[
            c[0].selectbox(
                "Aquecimento",
                list(AQUECIMENTOS),
                key="tqt_aq",
                persist_state="session",
                help=AJUDA["aquecimento"],
            )
        ]
        potencia, ua_s, t_s = 0.0, 0.0, 0.0
        if tipo == tq.POTENCIA:
            potencia = _numero(
                "Potência (kW)", "tqt_p", 30.0, AJUDA["potencia"], step=1.0, lugar=c[0]
            )
        elif tipo == tq.SERPENTINA:
            ua_s = _numero(
                "UA da serpentina (W/K)",
                "tqt_uas",
                800.0,
                AJUDA["ua_serpentina"],
                min_value=0.0,
                step=50.0,
                lugar=c[0],
            )
            t_s = _numero(
                "Temperatura do vapor (°C)",
                "tqt_ts",
                120.0,
                AJUDA["t_serpentina"],
                step=5.0,
                lugar=c[0],
            )
        termostato = None
        if tipo != tq.NENHUM:
            termostato = c[3].number_input(
                "Termostato (°C)", value=60.0, step=5.0, placeholder="sem termostato", key="tqt_set",
                help=AJUDA["termostato"],
            )  # fmt: skip
        ua_p = _numero(
            "UA da parede (W/K)",
            "tqt_uap",
            30.0,
            AJUDA["ua_perda"],
            min_value=0.0,
            step=5.0,
            lugar=c[1],
        )
        t_amb = _numero(
            "Temperatura do ar (°C)", "tqt_ta", 20.0, AJUDA["t_ambiente"], step=5.0, lugar=c[1]
        )
        vazao = _numero(
            "Vazão que passa (kg/s)",
            "tqt_m",
            0.0,
            AJUDA["vazao_termica"],
            min_value=0.0,
            step=0.05,
            format="%.4g",
            lugar=c[2],
        )
        t_e = _numero(
            "Temperatura de entrada (°C)", "tqt_te", 20.0, AJUDA["t_entrada"], step=5.0, lugar=c[2]
        )
    with st.container(border=True), secao_protegida("Tempo e pergunta da temperatura"):
        st.subheader("Tempo e pergunta", help=AJUDA["sec_tempo"])
        c = st.columns([1.3, 1, 0.7, 1.1])
        duracao = _duracao("tqt", c)
        alvo = c[3].number_input(
            "Temperatura a alcançar (°C)",
            value=None,
            step=5.0,
            placeholder="sem pergunta",
            key="tqt_alvo",
            help=AJUDA["alvo_temperatura"],
        )
    tanque = tq.TanqueTermico(
        volume,
        rho,
        cp,
        t0,
        tipo,
        potencia,
        ua_s,
        t_s,
        ua_p,
        t_amb,
        vazao,
        t_e,
        agua=agua,
        termostato=None if termostato is None else float(termostato),
    )
    with st.container(border=True), secao_protegida("Resultado da temperatura"):
        st.subheader("O tanque no tempo", help=AJUDA["sec_resultado"])
        erros = tq.problemas_termicos(tanque)
        if erros:
            _mostrar_erros(erros)
            return
        try:
            r = _termico(tanque, duracao)
        except tq.ErroDoTanque as erro:
            _mostrar_erros([str(erro)])
            return
        u = unidade_de_tempo(r.duracao)
        m = st.columns(5)
        estabiliza = r.tempo_para_estabilizar
        m[4].metric(
            "Estabiliza em",
            "depois do tempo mostrado" if estabiliza is None else tempo_em_texto(estabiliza, u),
            help=AJUDA["res_estabiliza_tanque"],
        )
        m[0].metric(
            "Temperatura no fim",
            f"{_N(float(r.temperaturas[-1]), 1)} °C",
            help=AJUDA["res_t_final"],
        )
        if r.tempo_do_termostato is not None and tanque.termostato is not None:
            m[1].metric(
                "Termostato segura em",
                f"{_N(tanque.termostato, 1)} °C",
                help=AJUDA["res_t_equilibrio"],
            )
        else:
            m[1].metric(
                "Equilíbrio",
                "—" if r.t_equilibrio is None else f"{_N(r.t_equilibrio, 1)} °C",
                help=AJUDA["res_t_equilibrio"],
            )
        m[2].metric(
            "Constante de tempo",
            "—" if r.tau is None else tempo_em_texto(r.tau),
            help=AJUDA["res_tau"],
        )
        if alvo is not None:
            ta = r.tempo_para(float(alvo))
            m[3].metric(
                f"Líquido a {_N(float(alvo), 1)} °C",
                "não chega" if ta is None else tempo_em_texto(ta, u),
                help=AJUDA["res_alvo_temperatura"],
            )
        for aviso in r.avisos:
            st.warning(aviso, icon=":material/warning:")
        tocador(fc.cena_termica(r, None if alvo is None else float(alvo)), key="tqt_tocador")
        with st.expander("Hipóteses da conta"):
            for linha in tq.hipoteses_termicas(r):
                st.markdown(f"- {linha}")
        st.subheader("Registrar no projeto", help=AJUDA["registrar"])
        botao_registrar_calculo(
            fc.registro_termico(r, None if alvo is None else float(alvo)),
            key="registrar_tanque_termico",
            rotulo="Registrar no projeto ativo",
        )


# =============================================================================================
# Partida da linha
# =============================================================================================
def aba_da_partida() -> None:
    with st.container(border=True), secao_protegida("Linha"):
        st.subheader("Linha", help=AJUDA["sec_linha"])
        c = st.columns(5)
        comprimento = _numero(
            "Comprimento (m)",
            "lnp_l",
            500.0,
            AJUDA["l_linha"],
            min_value=0.01,
            step=10.0,
            lugar=c[0],
        )
        diametro = _numero(
            "Diâmetro interno (mm)",
            "lnp_d",
            102.3,
            AJUDA["d_linha"],
            min_value=0.1,
            step=5.0,
            lugar=c[1],
        )
        material = c[2].selectbox(
            "Material",
            list(fl.RUGOSIDADES),
            key="lnp_mat",
            persist_state="session",
            help=AJUDA["material_linha"],
        )
        k_local = _numero(
            "ΣK das peças", "lnp_k", 2.0, AJUDA["k_linha"], min_value=0.0, step=0.5, lugar=c[3]
        )
        desnivel = _numero(
            "Desnível (m)", "lnp_z", 20.0, AJUDA["desnivel_linha"], step=1.0, lugar=c[4]
        )
        c = st.columns(5)
        rho, mu = _fluido("lnp", c[0])
        evento = EVENTOS[
            c[1].selectbox(
                "No instante zero",
                list(EVENTOS),
                key="lnp_evento",
                persist_state="session",
                help=AJUDA["evento"],
            )
        ]
        t_manobra = _numero(
            "Tempo da manobra (s)",
            "lnp_tm",
            10.0,
            AJUDA["t_manobra"],
            min_value=0.0,
            step=1.0,
            lugar=c[2],
        )
        k_valvula = _numero(
            "K da válvula aberta",
            "lnp_kv",
            0.17,
            AJUDA["k_valvula"],
            min_value=0.0,
            step=0.1,
            lugar=c[3],
        )
        celeridade = _numero(
            "Velocidade da onda (m/s)",
            "lnp_a",
            1000.0,
            AJUDA["celeridade"],
            min_value=1.0,
            step=50.0,
            lugar=c[4],
        )
        com_bomba = st.toggle(
            "Bomba na linha",
            value=evento == ln.BOMBA,
            key=f"lnp_bomba_{evento}",
            help=AJUDA["bomba"],
        )
        h0 = qmax = 0.0
        if com_bomba:
            c = st.columns(5)
            h0 = _numero(
                "Altura com vazão zero (m)",
                "lnp_h0",
                40.0,
                AJUDA["h0"],
                min_value=0.0,
                step=5.0,
                lugar=c[0],
            )
            qmax = _numero(
                "Vazão com altura zero (L/s)",
                "lnp_qm",
                30.0,
                AJUDA["qmax"],
                min_value=0.0,
                step=5.0,
                lugar=c[1],
            )
    with st.container(border=True), secao_protegida("Tempo da partida"):
        st.subheader("Tempo", help=AJUDA["sec_tempo"])
        duracao = _duracao("lnp", st.columns([1.3, 1, 0.7, 1.1]))
    linha = ln.Linha(
        comprimento, diametro, fl.RUGOSIDADES[material] * 1000.0, k_local, desnivel, rho, mu,
        evento, t_manobra, k_valvula, h0, qmax, celeridade,
    )  # fmt: skip
    with st.container(border=True), secao_protegida("Resultado da partida"):
        st.subheader("A linha no tempo", help=AJUDA["sec_resultado"])
        erros = ln.problemas_da_partida(linha)
        if erros:
            _mostrar_erros(erros)
            return
        try:
            r = _partida(linha, duracao)
        except ln.ErroDaLinha as erro:
            _mostrar_erros([str(erro)])
            return
        u = unidade_de_tempo(r.duracao)
        t95, t99 = r.tempo_para(0.95), r.tempo_para(0.99)
        m = st.columns(4)
        m[0].metric("Vazão de regime", f"{_N(r.vazao_final, 2)} L/s", help=AJUDA["res_q_final"])
        m[1].metric(
            "Chega a 95 %", "—" if t95 is None else tempo_em_texto(t95, u), help=AJUDA["res_t95"]
        )
        m[2].metric(
            "Chega a 99 %", "—" if t99 is None else tempo_em_texto(t99, u), help=AJUDA["res_t99"]
        )
        m[3].metric("Ida e volta da onda", f"{_N(r.tempo_da_onda, 2)} s", help=AJUDA["res_onda"])
        for aviso in r.avisos:
            st.warning(aviso, icon=":material/warning:")
        tocador(fc.cena_da_partida(r), key="lnp_tocador")
        with st.expander("Hipóteses da conta"):
            for item in ln.hipoteses_da_partida(r):
                st.markdown(f"- {item}")
        st.subheader("Registrar no projeto", help=AJUDA["registrar"])
        botao_registrar_calculo(
            fc.registro_da_partida(r),
            key="registrar_partida_linha",
            rotulo="Registrar no projeto ativo",
        )


# =============================================================================================
# Água quente chegando
# =============================================================================================
def aba_do_tubo() -> None:
    with st.container(border=True), secao_protegida("Tubo"):
        st.subheader("Tubo", help=AJUDA["sec_tubo"])
        c = st.columns(5)
        comprimento = _numero(
            "Comprimento (m)",
            "lnt_l",
            30.0,
            AJUDA["l_tubo_quente"],
            min_value=0.01,
            step=5.0,
            lugar=c[0],
        )
        diametro = _numero(
            "Diâmetro interno (mm)",
            "lnt_d",
            26.6,
            AJUDA["d_tubo_quente"],
            min_value=0.1,
            step=1.0,
            lugar=c[1],
        )
        parede = _numero(
            "Parede (mm)", "lnt_e", 2.9, AJUDA["parede"], min_value=0.01, step=0.5, lugar=c[2]
        )
        nome = c[3].selectbox(
            "Material da parede",
            list(ct.MATERIAIS),
            key="lnt_mat",
            persist_state="session",
            help=AJUDA["material_parede"],
        )
        vazao = _numero(
            "Vazão (L/s)",
            "lnt_q",
            0.1,
            AJUDA["vazao_tubo"],
            min_value=0.0001,
            step=0.05,
            format="%.4g",
            lugar=c[4],
        )
        c = st.columns(5)
        isolamento = _numero(
            "Isolamento (mm)",
            "lnt_iso",
            0.0,
            AJUDA["isolamento"],
            min_value=0.0,
            step=5.0,
            lugar=c[0],
        )
        k_iso = _numero(
            "k do isolamento (W/(m·K))",
            "lnt_kiso",
            0.04,
            AJUDA["k_isolamento"],
            min_value=0.001,
            step=0.005,
            format="%.4g",
            lugar=c[1],
        )
        h_ext = _numero(
            "h de fora (W/(m²·K))",
            "lnt_h",
            10.0,
            AJUDA["h_externo"],
            min_value=0.01,
            step=1.0,
            lugar=c[2],
        )
        t_amb = _numero(
            "Temperatura do ar (°C)", "lnt_ta", 20.0, AJUDA["t_ambiente_tubo"], step=5.0, lugar=c[3]
        )
        c = st.columns(5)
        t0 = _numero(
            "Tubo e água parada (°C)", "lnt_t0", 20.0, AJUDA["t_inicial_tubo"], step=5.0, lugar=c[0]
        )
        t_e = _numero(
            "Água que entra (°C)", "lnt_te", 60.0, AJUDA["t_entrada_tubo"], step=5.0, lugar=c[1]
        )
    with st.container(border=True), secao_protegida("Tempo e pergunta do tubo"):
        st.subheader("Tempo e pergunta", help=AJUDA["sec_tempo"])
        c = st.columns([1.3, 1, 0.7, 1.1])
        duracao = _duracao("lnt", c)
        alvo = c[3].number_input(
            "Temperatura na saída (°C)",
            value=None,
            step=5.0,
            placeholder="sem pergunta",
            key="lnt_alvo",
            help=AJUDA["alvo_tubo"],
        )
        prazo = None
        if alvo is not None:
            c = st.columns([1.3, 1, 0.7, 1.1])
            valor = c[1].number_input(
                "Prazo (opcional)",
                value=None,
                min_value=0.0,
                step=5.0,
                placeholder="sem prazo",
                key="lnt_prazo",
                help=AJUDA["prazo_tubo"],
            )
            unidade = c[2].selectbox(
                "Unidade", list(UNIDADES), index=1, key="lnt_prazo_u", help=AJUDA["duracao_unidade"]
            )
            if valor is not None and valor > 0:
                prazo = float(valor) * UNIDADES[unidade]
    tubo = ln.TuboAquecendo(
        comprimento,
        diametro,
        parede,
        ct.MATERIAIS[nome],
        isolamento,
        k_iso,
        h_ext,
        t_amb,
        vazao,
        t0,
        t_e,
    )
    with st.container(border=True), secao_protegida("Resultado do tubo"):
        st.subheader("O tubo no tempo", help=AJUDA["sec_resultado"])
        erros = ln.problemas_do_tubo(tubo)
        if erros:
            _mostrar_erros(erros)
            return
        try:
            r = _tubo(tubo, duracao)
        except ln.ErroDaLinha as erro:
            _mostrar_erros([str(erro)])
            return
        u = unidade_de_tempo(r.duracao)
        m = st.columns(5)
        estabiliza = r.tempo_para_estabilizar()
        m[4].metric(
            "Saída estabiliza em",
            "depois do tempo mostrado" if estabiliza is None else tempo_em_texto(estabiliza, u),
            help=AJUDA["res_estabiliza_tubo"],
        )
        m[0].metric(
            "Água atravessa em",
            tempo_em_texto(comprimento / r.velocidade),
            help=AJUDA["res_transito"],
        )
        m[1].metric(
            "Saída em regime", f"{_N(r.saida_permanente, 1)} °C", help=AJUDA["res_permanente"]
        )
        if alvo is not None:
            ta = r.tempo_para(float(alvo))
            m[2].metric(
                f"Saída a {_N(float(alvo), 1)} °C",
                "não chega" if ta is None else tempo_em_texto(ta, u),
                help=AJUDA["res_alvo_tubo"],
            )
            volume = r.volume_ate(float(alvo))
            m[3].metric(
                "Água que sai antes",
                "—" if volume is None else f"{_N(volume, 1)} L",
                help=AJUDA["res_volume"],
            )
            if ta is None and float(alvo) > r.saida_permanente and t_e > t0:
                st.warning(
                    f"A saída não chega a {_N(float(alvo), 1)} °C nem em regime permanente: a perda "
                    f"pelo caminho a deixa em {_N(r.saida_permanente, 1)} °C. Isolar o tubo ou "
                    "aumentar a vazão resolve.",
                    icon=":material/warning:",
                )
        for aviso in r.avisos:
            st.warning(aviso, icon=":material/warning:")
        tocador(fc.cena_do_tubo(r, None if alvo is None else float(alvo)), key="lnt_tocador")
        verificacoes = fc.verificacoes_do_tubo(r, None if alvo is None else float(alvo), prazo)
        if verificacoes:
            mostrar_tabela_verificacoes(verificacoes)
        with st.expander("Hipóteses da conta"):
            for item in ln.hipoteses_do_tubo(r):
                st.markdown(f"- {item}")
        st.subheader("Registrar no projeto", help=AJUDA["registrar"])
        botao_registrar_calculo(
            fc.registro_do_tubo(r, None if alvo is None else float(alvo), prazo),
            key="registrar_tubo_aquecendo",
            rotulo="Registrar no projeto ativo",
        )


abas = st.tabs(["Tanque: nível", "Tanque: temperatura", "Partida da linha", "Água quente chegando"])
with abas[0]:
    aba_do_nivel()
with abas[1]:
    aba_da_temperatura()
with abas[2]:
    aba_da_partida()
with abas[3]:
    aba_do_tubo()
