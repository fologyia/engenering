"""Calor no tempo: a temperatura andando por dentro de uma peça, em animação.

Duas abas: parede, cilindro ou esfera (uma dimensão, conferida com a solução exata em série) e a
seção desenhada (duas dimensões). As contas estão em ``core.calor_no_tempo`` e
``core.calor_na_secao``; a cena do tocador e o registro em ``core.calor_cenas``.
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from components.animacao_ui import tocador
from components.calor_no_tempo_help import AJUDA
from components.desenhar_secao_ui import PARTES as PARTES_DESENHADAS
from components.project_tools import botao_registrar_calculo
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from components.verification_table import mostrar_tabela_verificacoes
from core import calor_cenas as cc
from core import calor_na_secao as cs
from core import calor_no_tempo as ct
from core import secao_desenhada as sd
from core.animacao import UnidadeDeTempo, tempo_em_texto, unidade_de_tempo

ICONE = ":material/local_fire_department:"
configurar_pagina("Calor no tempo", ICONE)
cabecalho_pagina(
    "Calor no tempo",
    "Como a temperatura anda por dentro de uma peça quando ela vai para um forno, um banho ou o "
    "ar: a peça muda de cor numa animação, com as curvas no tempo ao lado. Parede, tubo, "
    "cilindro, esfera ou a seção desenhada.",
    categoria="Mecânica",
    icone=ICONE,
    modulo_id=cc.MODULO_ID,
)

INFORMAR = "Informar"
FORMAS = {"Parede plana": ct.PAREDE, "Cilindro ou tubo": ct.CILINDRO, "Esfera": ct.ESFERA}
CONDICOES = {
    "Ar ou líquido em volta (convecção)": ct.CONVECCAO,
    "Temperatura fixa na face": ct.TEMPERATURA,
    "Fluxo de calor que entra": ct.FLUXO,
    "Isolada": ct.ISOLADA,
}
MODO_AUTOMATICO = "Até quase estabilizar"
MODO_INFORMADO = "Informar o tempo"
UNIDADES = {"s": 1.0, "min": 60.0, "h": 3600.0}
SECAO_DESENHADA = "A seção desenhada na página Desenhar seção"
_N = ct._n


def _material(prefixo: str) -> ct.Material:
    nomes = [*ct.MATERIAIS, INFORMAR]
    colunas = st.columns(4)
    nome = colunas[0].selectbox(
        "Material", nomes, index=0, key=f"{prefixo}_material", persist_state="session",
        help=AJUDA["material"],
    )  # fmt: skip
    if nome != INFORMAR:
        m = ct.MATERIAIS[nome]
        colunas[1].caption(
            f"k = {_N(m.condutividade, 2)} W/(m·K)\n\nρ = {_N(m.massa_especifica, 0)} kg/m³\n\n"
            f"c_p = {_N(m.calor_especifico, 0)} J/(kg·K)"
        )
        colunas[2].caption(f"α = {_N(m.difusividade * 1e6, 3)} mm²/s\n\nFonte: Incropera, 300 K")
        return m
    k = colunas[1].number_input(
        "k (W/(m·K))", min_value=1e-4, value=60.5, format="%.4g", key=f"{prefixo}_k",
        help=AJUDA["k"],
    )  # fmt: skip
    rho = colunas[2].number_input(
        "ρ (kg/m³)", min_value=1e-3, value=7854.0, format="%.6g", key=f"{prefixo}_rho",
        help=AJUDA["rho"],
    )  # fmt: skip
    cp = colunas[3].number_input(
        "c_p (J/(kg·K))", min_value=1e-3, value=434.0, format="%.6g", key=f"{prefixo}_cp",
        help=AJUDA["cp"],
    )  # fmt: skip
    return ct.Material("Material informado", float(k), float(rho), float(cp), fonte="informado")


def _face(prefixo: str, titulo: str, padrao: str, h: float, t_fluido: float) -> ct.Face:
    st.markdown(f"**{titulo}**")
    rotulos = list(CONDICOES)
    rotulo = st.selectbox(
        "O que encosta", rotulos, index=rotulos.index(padrao), key=f"{prefixo}_tipo",
        persist_state="session", help=AJUDA["face_tipo"],
    )  # fmt: skip
    tipo = CONDICOES[rotulo]
    colunas = st.columns(2)
    if tipo == ct.CONVECCAO:
        valor_h = colunas[0].number_input(
            "h (W/(m²·K))", min_value=0.01, value=h, step=10.0, format="%.4g",
            key=f"{prefixo}_h", persist_state="session", help=AJUDA["h"],
        )  # fmt: skip
        valor_t = colunas[1].number_input(
            "Temperatura do fluido (°C)", min_value=-273.0, value=t_fluido, step=5.0,
            key=f"{prefixo}_tf", persist_state="session", help=AJUDA["t_fluido"],
        )  # fmt: skip
        return ct.Face(ct.CONVECCAO, h=float(valor_h), t_fluido=float(valor_t))
    if tipo == ct.TEMPERATURA:
        valor = colunas[0].number_input(
            "Temperatura da face (°C)", min_value=-273.0, value=t_fluido, step=5.0,
            key=f"{prefixo}_tfix", persist_state="session", help=AJUDA["t_fixa"],
        )  # fmt: skip
        return ct.Face(ct.TEMPERATURA, t_fixa=float(valor))
    if tipo == ct.FLUXO:
        valor = colunas[0].number_input(
            "Fluxo (W/m²)", value=5000.0, step=500.0, format="%.6g", key=f"{prefixo}_q",
            persist_state="session", help=AJUDA["fluxo"],
        )  # fmt: skip
        return ct.Face(ct.FLUXO, fluxo=float(valor))
    return ct.Face(ct.ISOLADA)


def _tempo(prefixo: str) -> tuple[float | None, float | None]:
    """Duração (None = automática) e temperatura que se quer alcançar (None = sem pergunta)."""
    colunas = st.columns([1.3, 1, 0.7, 1.1])
    modo = colunas[0].radio(
        "Duração", [MODO_AUTOMATICO, MODO_INFORMADO], key=f"{prefixo}_modo",
        help=AJUDA["duracao_modo"],
    )  # fmt: skip
    duracao = None
    if modo == MODO_INFORMADO:
        valor = colunas[1].number_input(
            "Tempo", min_value=0.001, value=30.0, step=5.0, format="%.4g", key=f"{prefixo}_dur",
            persist_state="session", help=AJUDA["duracao"],
        )  # fmt: skip
        unidade = colunas[2].selectbox(
            "Unidade", list(UNIDADES), index=1, key=f"{prefixo}_dur_u", persist_state="session",
            help=AJUDA["duracao_unidade"],
        )  # fmt: skip
        duracao = float(valor) * UNIDADES[unidade]
    alvo = colunas[3].number_input(
        "Temperatura a alcançar (°C)", value=None, step=5.0, placeholder="sem pergunta",
        key=f"{prefixo}_alvo", help=AJUDA["alvo"],
    )  # fmt: skip
    return duracao, (None if alvo is None else float(alvo))


def _marcos_na_tela(m: ct.Marcos, u: UnidadeDeTempo) -> None:
    """Segunda linha de métricas: estabiliza, equaliza e a maior diferença dentro da peça."""
    linha = st.columns(4)
    linha[0].metric(
        "Estabiliza em",
        "depois do tempo mostrado" if m.estabiliza is None else tempo_em_texto(m.estabiliza, u),
        help=AJUDA["res_estabiliza"],
    )
    if m.equaliza is not None:
        valor = tempo_em_texto(m.equaliza, u)
    elif m.gradiente_de_regime is not None and not m.equaliza_no_regime:
        valor = f"não: fica {_N(m.gradiente_de_regime, 1)} °C"
    else:
        valor = "depois do tempo mostrado"
    linha[1].metric("Equaliza em", valor, help=AJUDA["res_equaliza"])
    linha[2].metric(
        "Maior diferença dentro",
        f"{_N(m.maior_diferenca, 1)} °C aos {tempo_em_texto(m.quando_maior, u)}",
        help=AJUDA["res_diferenca"],
    )


@st.cache_data(show_spinner=False, max_entries=6)
def _calcular_peca(peca: ct.Peca, duracao: float | None) -> ct.ResultadoDoCalor:
    return ct.calcular(peca, duracao)


@st.cache_data(show_spinner=False, max_entries=6)
def _calcular_secao(
    partes_json: str,
    material: ct.Material,
    t_inicial: float,
    fora: ct.Face,
    furos: ct.Face,
    duracao: float | None,
) -> cs.ResultadoDaSecao:
    partes = sd.partes_de_lista(json.loads(partes_json))
    return cs.calcular(partes, material, t_inicial, fora, furos, duracao)


def _mostrar_erros(erros: list[str]) -> None:
    for erro in erros:
        st.error(erro, icon=":material/error:")


# =============================================================================================
# Aba 1: parede, cilindro, esfera
# =============================================================================================
def aba_da_peca() -> None:
    with st.container(border=True), secao_protegida("Peça e material"):
        st.subheader("Peça e material", help=AJUDA["sec_peca"])
        colunas = st.columns(4)
        rotulo_forma = colunas[0].selectbox(
            "Forma", list(FORMAS), index=1, key="cnt_forma", persist_state="session",
            help=AJUDA["forma"],
        )  # fmt: skip
        forma = FORMAS[rotulo_forma]
        espessura = diametro = interno = 0.0
        if forma == ct.PAREDE:
            espessura = colunas[1].number_input(
                "Espessura (mm)", min_value=0.01, value=50.0, step=5.0, format="%.4g",
                key="cnt_esp", persist_state="session", help=AJUDA["espessura"],
            )  # fmt: skip
        else:
            diametro = colunas[1].number_input(
                "Diâmetro de fora (mm)", min_value=0.01, value=100.0, step=5.0, format="%.4g",
                key="cnt_d", persist_state="session", help=AJUDA["diametro"],
            )  # fmt: skip
            interno = colunas[2].number_input(
                "Diâmetro de dentro (mm)", min_value=0.0, value=0.0, step=5.0, format="%.4g",
                key="cnt_di", persist_state="session", help=AJUDA["diametro_interno"],
            )  # fmt: skip
        t_inicial = colunas[3].number_input(
            "Temperatura inicial (°C)", min_value=-273.0, value=20.0, step=5.0, key="cnt_t0",
            persist_state="session", help=AJUDA["t_inicial"],
        )  # fmt: skip
        material = _material("cnt")

    macica = forma != ct.PAREDE and interno <= 0
    with st.container(border=True), secao_protegida("O que acontece em cada face"):
        st.subheader("O que acontece em cada face", help=AJUDA["sec_faces"])
        convecao = "Ar ou líquido em volta (convecção)"
        if forma == ct.PAREDE:
            lados = st.columns(2)
            with lados[0]:
                face_a = _face("cnt_fa", "Face da esquerda", convecao, 500.0, 200.0)
            with lados[1]:
                face_b = _face("cnt_fb", "Face da direita", convecao, 10.0, 20.0)
        elif macica:
            face_a = ct.Face(ct.ISOLADA)
            face_b = _face("cnt_fb", "Superfície de fora", convecao, 500.0, 150.0)
        else:
            lados = st.columns(2)
            with lados[0]:
                face_a = _face("cnt_fa", "Face de dentro", convecao, 1000.0, 150.0)
            with lados[1]:
                face_b = _face("cnt_fb", "Face de fora", convecao, 10.0, 20.0)

    nomes = ct.nomes_dos_pontos(forma, macica)
    with st.container(border=True), secao_protegida("Tempo e pergunta"):
        st.subheader("Tempo e pergunta", help=AJUDA["sec_tempo"])
        duracao, alvo = _tempo("cnt")
        nome_ponto, prazo = None, None
        if alvo is not None:
            colunas = st.columns([1.3, 1, 0.7, 1.1])
            nome_ponto = colunas[0].selectbox(
                "Ponto que precisa chegar", nomes, index=0, key="cnt_ponto",
                help=AJUDA["ponto"],
            )  # fmt: skip
            valor_prazo = colunas[1].number_input(
                "Prazo (opcional)", min_value=0.0, value=None, step=5.0, placeholder="sem prazo",
                key="cnt_prazo", help=AJUDA["prazo"],
            )  # fmt: skip
            unidade_prazo = colunas[2].selectbox(
                "Unidade", list(UNIDADES), index=1, key="cnt_prazo_u",
                help=AJUDA["duracao_unidade"],
            )  # fmt: skip
            if valor_prazo is not None and valor_prazo > 0:
                prazo = float(valor_prazo) * UNIDADES[unidade_prazo]

    peca = ct.Peca(
        forma=forma,
        material=material,
        t_inicial=float(t_inicial),
        face_a=face_a,
        face_b=face_b,
        espessura_mm=float(espessura),
        diametro_mm=float(diametro),
        diametro_interno_mm=float(interno),
    )
    with st.container(border=True), secao_protegida("Resultado da peça"):
        st.subheader("A peça no tempo", help=AJUDA["sec_resultado"])
        erros = ct.problemas(peca)
        if erros:
            _mostrar_erros(erros)
            return
        try:
            r = _calcular_peca(peca, duracao)
        except ct.ErroDoCalor as erro:
            _mostrar_erros([str(erro)])
            return
        u = unidade_de_tempo(r.duracao)
        ponto = r.ponto(nome_ponto) if nome_ponto else None
        metricas = st.columns(4)
        metricas[0].metric(
            "Tempo mostrado", tempo_em_texto(r.duracao, u), help=AJUDA["res_duracao"]
        )
        metricas[1].metric(
            "Constante de tempo",
            "—" if r.tau is None else tempo_em_texto(r.tau, unidade_de_tempo(r.tau)),
            help=AJUDA["res_tau"],
        )
        if ponto is not None and alvo is not None:
            t = r.tempo_para(ponto, alvo)
            metricas[2].metric(
                f"{ponto.nome} a {_N(alvo, 1)} °C",
                "não chega" if t is None else tempo_em_texto(t, u),
                help=AJUDA["res_alvo"],
            )
        else:
            centro = r.pontos[0] if macica else r.pontos[1]
            metricas[2].metric(
                f"{centro.nome} no fim",
                f"{_N(float(r.temperaturas[-1, centro.indice]), 1)} °C",
                help=AJUDA["res_final"],
            )
        unidade_calor = {"J/m²": "kJ/m²", "J/m": "kJ/m", "J": "kJ"}[peca.unidade_de_calor]
        metricas[3].metric(
            "Calor que entrou",
            f"{_N(float(r.energia()[-1]) / 1000.0, 1)} {unidade_calor}",
            help=AJUDA["res_calor"],
        )
        _marcos_na_tela(ct.marcos(r), u)
        for aviso in r.avisos:
            st.warning(aviso, icon=":material/warning:")
        if r.biot is not None:
            if r.uniforme:
                st.info(
                    f"Bi = {_N(r.biot, 3)}, abaixo de 0,1: a peça esquenta praticamente por igual "
                    "(as cores quase não mudam de dentro para fora).",
                    icon=":material/info:",
                )
            else:
                st.caption(f"Número de Biot: Bi = {_N(r.biot, 3)}.", help=AJUDA["res_biot"])
        if ponto is not None and alvo is not None and r.tempo_para(ponto, alvo) is None:
            ultimo = float(r.serie(ponto)[-1])
            final = None if r.permanente is None else float(r.permanente[ponto.indice])
            texto = (
                f"{ponto.nome} não chega a {_N(alvo, 1)} °C no tempo mostrado: termina em "
                f"{_N(ultimo, 1)} °C."
            )
            if final is not None and r.automatica:
                texto += f" Em regime permanente ele para em {_N(final, 1)} °C."
            st.warning(texto, icon=":material/warning:")
        tocador(cc.cena_da_peca(r, alvo, ponto), key="cnt_tocador")
        verificacoes = cc.verificacoes_da_peca(r, alvo, ponto, prazo)
        if verificacoes:
            mostrar_tabela_verificacoes(verificacoes)
        conferencias = ct.conferencias(r)
        if conferencias:
            with st.expander("Conferência com a solução exata"):
                st.caption(AJUDA["conferencia"])
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Instante": tempo_em_texto(c.tempo, u),
                                "Ponto": c.ponto,
                                "Calculado (°C)": _N(c.calculado, 3),
                                "Exato (°C)": _N(c.exato, 3),
                                "Diferença (°C)": _N(c.diferenca, 3),
                            }
                            for c in conferencias
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                )
        with st.expander("Hipóteses da conta"):
            for linha in ct.hipoteses(r):
                st.markdown(f"- {linha}")
        st.subheader("Registrar no projeto", help=AJUDA["registrar"])
        botao_registrar_calculo(
            cc.registro_da_peca(r, alvo=alvo, ponto=ponto, prazo=prazo),
            key="registrar_calor_peca",
            rotulo="Registrar no projeto ativo",
        )


# =============================================================================================
# Aba 2: seção desenhada
# =============================================================================================
def _partes_da_secao() -> tuple[list[sd.Parte], str, list[str]]:
    modelos = {m.nome: m for m in sd.MODELOS}
    opcoes = list(modelos)
    desenhadas = st.session_state.get(PARTES_DESENHADAS)
    if isinstance(desenhadas, list) and desenhadas:
        opcoes.insert(0, SECAO_DESENHADA)
    padrao = "Tubo redondo" if "Tubo redondo" in opcoes else opcoes[0]
    colunas = st.columns([1.4, 3])
    escolha = colunas[0].selectbox(
        "Seção", opcoes, index=opcoes.index(padrao), key="cns_origem", help=AJUDA["origem"]
    )
    if escolha == SECAO_DESENHADA:
        try:
            return sd.partes_de_lista(desenhadas or []), "desenhada", []
        except (sd.ErroDeSecao, TypeError, ValueError) as erro:
            return [], "desenhada", [str(erro)]
    modelo = modelos[escolha]
    medidas: dict[str, float] = {}
    with colunas[1]:
        caixas = st.columns(min(4, len(modelo.medidas)))
        for k, medida in enumerate(modelo.medidas):
            medidas[medida.chave] = float(
                caixas[k % len(caixas)].number_input(
                    f"{medida.rotulo} (mm)",
                    min_value=0.0,
                    value=float(medida.padrao),
                    step=1.0,
                    format="%.4g",
                    key=f"cns_m_{modelo.id}_{medida.chave}",
                    help=medida.ajuda,
                )
            )
    try:
        partes = sd.partes_do_modelo(modelo.id, medidas)
    except sd.ErroDeSecao as erro:
        return [], modelo.nome, [str(erro)]
    texto = " × ".join(_N(v, 1) for v in medidas.values())
    return partes, f"{modelo.nome} {texto} mm", []


def aba_da_secao() -> None:
    with st.container(border=True), secao_protegida("Seção e material"):
        st.subheader("Seção e material", help=AJUDA["sec_secao"])
        partes, nome, erros_secao = _partes_da_secao()
        t_inicial = st.number_input(
            "Temperatura inicial (°C)", min_value=-273.0, value=20.0, step=5.0, key="cns_t0",
            persist_state="session", help=AJUDA["t_inicial"],
        )  # fmt: skip
        material = _material("cns")
    if erros_secao or not partes:
        _mostrar_erros(erros_secao or ["Desenhe ou escolha uma seção."])
        return
    try:
        grade = cs.montar_grade(partes)
    except ct.ErroDoCalor as erro:
        _mostrar_erros([str(erro)])
        return
    with st.container(border=True), secao_protegida("O que acontece nos contornos"):
        st.subheader("O que acontece nos contornos", help=AJUDA["sec_contornos"])
        convecao = "Ar ou líquido em volta (convecção)"
        lados = st.columns(2)
        with lados[0]:
            fora = _face("cns_fora", "Contorno de fora", convecao, 10.0, 20.0)
        furos = ct.Face(ct.ISOLADA)
        with lados[1]:
            if grade.tem_furo:
                furos = _face("cns_furo", "Contorno dos furos", convecao, 1000.0, 150.0)
            else:
                st.caption("A seção não tem furo: só o contorno de fora troca calor.")
    with st.container(border=True), secao_protegida("Tempo e pergunta da seção"):
        st.subheader("Tempo e pergunta", help=AJUDA["sec_tempo"])
        duracao, alvo = _tempo("cns")
    with st.container(border=True), secao_protegida("Resultado da seção"):
        st.subheader("A seção no tempo", help=AJUDA["sec_resultado"])
        erros = cs.problemas(material, fora, furos, grade)
        if erros:
            _mostrar_erros(erros)
            return
        partes_json = json.dumps([p.como_dicionario() for p in partes], sort_keys=True)
        try:
            r = _calcular_secao(partes_json, material, float(t_inicial), fora, furos, duracao)
        except ct.ErroDoCalor as erro:
            _mostrar_erros([str(erro)])
            return
        u = unidade_de_tempo(r.duracao)
        metricas = st.columns(4)
        metricas[0].metric(
            "Tempo mostrado", tempo_em_texto(r.duracao, u), help=AJUDA["res_duracao"]
        )
        metricas[1].metric(
            "Ponto mais quente no fim", f"{_N(float(r.maxima[-1]), 1)} °C", help=AJUDA["res_quente"]
        )
        metricas[2].metric(
            "Média no fim", f"{_N(float(r.media[-1]), 1)} °C", help=AJUDA["res_media"]
        )
        if alvo is not None:
            qual = "max" if r.t_inicial > alvo else "min"
            t = r.tempo_para(qual, alvo)
            metricas[3].metric(
                f"Seção inteira a {_N(alvo, 1)} °C",
                "não chega" if t is None else tempo_em_texto(t, u),
                help=AJUDA["res_alvo_secao"],
            )
        else:
            metricas[3].metric(
                "Ponto mais frio no fim", f"{_N(float(r.minima[-1]), 1)} °C", help=AJUDA["res_frio"]
            )
        _marcos_na_tela(cs.marcos(r), u)
        for aviso in r.avisos:
            st.warning(aviso, icon=":material/warning:")
        identificador = (
            f"secao-{hash((partes_json, material, t_inicial, fora, furos, duracao)) & 0xFFFFFFFF:x}"
        )
        tocador(cc.cena_da_secao(r, partes, alvo, identificador=identificador), key="cns_tocador")
        st.caption(
            f"Grade de {int(grade.ativa.sum())} células; área {_N(grade.area_mm2, 1)} mm², "
            f"contorno de fora {_N(grade.contorno_fora_mm, 1)} mm"
            + (
                f", contorno dos furos {_N(grade.contorno_furos_mm, 1)} mm."
                if grade.tem_furo
                else "."
            )
        )
        with st.expander("Hipóteses da conta"):
            for linha in cs.hipoteses(r):
                st.markdown(f"- {linha}")
        st.subheader("Registrar no projeto", help=AJUDA["registrar"])
        botao_registrar_calculo(
            cc.registro_da_secao(r, nome, alvo=alvo),
            key="registrar_calor_secao",
            rotulo="Registrar no projeto ativo",
        )


aba_peca, aba_secao = st.tabs(["Parede, tubo, cilindro ou esfera", "Seção desenhada"])
with aba_peca:
    aba_da_peca()
with aba_secao:
    aba_da_secao()
