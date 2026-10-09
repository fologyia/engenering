"""Interface da página Vento nas estruturas.

Só desenha a interface: todo cálculo está em ``core.vento_edificio`` (a edificação), em
``core.vento_portico`` (cargas e solução do pórtico) e em ``core.vento_registro`` (o registro do
projeto). A página recalcula a cada interação e mostra, abaixo dos formulários, as pressões por
zona, as vedações, as forças globais, o pórtico e a tabela de verificações.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from components.base_tecnica_ui import base_ativa, botao_recarregar_da_base, legenda_da_base
from components.project_tools import botao_registrar_calculo
from components.ui import fronteira_modelo
from components.verification_table import COR_BADGE, mostrar_tabela_verificacoes
from components.wind_figures import svg_planta
from components.wind_help import AJUDA
from core import base_tecnica as bt
from core import section_catalog as catalogo_perfis
from core import vento_coeficientes as coef
from core import vento_edificio as ve
from core import vento_nbr6123 as v6123
from core import vento_portico as vp
from core import vento_registro as registro_vento
from core.verificacao import csv_verificacoes, status_geral

RELEVO_PLANO = "plano"
RELEVO_VALE = "vale"
RELEVO_TALUDE = "talude"
ROTULOS_RELEVO = {
    RELEVO_PLANO: "Plano (S₁ = 1,0)",
    RELEVO_VALE: "Vale protegido (S₁ = 0,9)",
    RELEVO_TALUDE: "Talude ou morro (5.2)",
}
CLASSE_AUTOMATICA = "auto"
ROTULOS_CLASSE = {
    CLASSE_AUTOMATICA: "Automática (por direção)",
    "A": "A — até 20 m (3 s)",
    "B": "B — 20 a 50 m (5 s)",
    "C": "C — acima de 50 m (10 s)",
}
ROTULOS_ALTURA_REFERENCIA = {
    ve.REFERENCIA_ALTURA_TOPO: "Topo da edificação",
    ve.REFERENCIA_ALTURA_BEIRAL: "Beiral (altura h)",
}
ROTULOS_COBERTURA = {
    ve.COBERTURA_PLANA: "Plana",
    ve.COBERTURA_DUAS_AGUAS: "Duas águas",
    ve.COBERTURA_UMA_AGUA: "Uma água",
}
PERMEABILIDADE_INFORMADA = "informado"
ROTULOS_PERMEABILIDADE = {
    **coef.CENARIOS_PERMEABILIDADE,
}
POSICOES_ABERTURA = {
    "barlavento": "Abertura dominante a barlavento (de frente para o vento)",
    "sotavento": "Abertura dominante a sotavento (de costas para o vento)",
    "paralela": "Abertura dominante em face paralela ao vento, fora da zona de altas sucções",
    "paralela_alta_succao": "Abertura dominante em face paralela, na zona de altas sucções",
}
BASES_ENGASTADAS = "Engastadas"
BASES_ROTULADAS = "Rotuladas"
PERFIL_INFORMAR = "— informar A e I —"
E_ACO_MPA = 200_000.0


def _numero(
    rotulo: str,
    chave: str,
    valor: float,
    ajuda: str,
    *,
    minimo: float | None = 0.001,
    maximo: float | None = None,
    passo: float | None = None,
    formato: str | None = None,
    desligado: bool = False,
    alvo: Any = st,
) -> float:
    """``number_input`` com a persistência da sessão e o “?” sempre presentes."""
    return float(
        alvo.number_input(
            rotulo,
            min_value=minimo,
            max_value=maximo,
            value=float(valor),
            step=passo,
            format=formato,
            key=chave,
            persist_state="session",
            help=ajuda,
            disabled=desligado,
        )
    )


def _pt(valor: float, casas: int = 2) -> str:
    return v6123.numero_ptbr(valor, casas)


def _manter_opcao_valida(chave: str, opcoes: list[str]) -> None:
    """Descarta a escolha guardada que deixou de existir (o conjunto de casos mudou)."""
    if st.session_state.get(chave) not in opcoes:
        st.session_state.pop(chave, None)


# ---------------------------------------------------------------------------
# 1. Vento no local
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DadosLocal:
    v0_m_s: float
    relevo: str
    s1: float
    categoria: str
    grupo: int
    s3: float | None
    pm: float | None
    ma: float | None
    classe: str | None
    referencia_altura: str
    vedacoes_com_092: bool
    avisos: tuple[str, ...]


CHAVES_DA_BASE = ("vt_v0", "vt_relevo", "vt_categoria", "vt_grupo", "vt_s3_cliente")


def _relevo_da_base(s1: float) -> str:
    if abs(s1 - 0.9) < 1e-9:
        return RELEVO_VALE
    return RELEVO_PLANO


def formulario_local() -> DadosLocal:
    """Vento no local — começando com o V₀, S₁, terreno e S₃ da base técnica do projeto."""
    avisos: list[str] = []
    base = base_ativa()
    vento_base = base.vento if base else bt.VentoDoLocal()
    s3_cliente = (
        vento_base.s3_cliente
        if base is not None and vento_base.grupo_s3 == bt.S3_DO_CLIENTE
        else None
    )
    grupo_base = int(vento_base.grupo_s3) if vento_base.grupo_s3.isdigit() else 3
    relevos = list(ROTULOS_RELEVO)
    categorias = list(v6123.CATEGORIAS_RUGOSIDADE)
    grupos = list(v6123.GRUPOS_S3)
    with st.container(border=True):
        st.subheader("1. Vento no local", help=AJUDA["sec_1"])
        legenda_da_base(base)
        if base is not None and abs(vento_base.s1 - 1.0) > 1e-9 and abs(vento_base.s1 - 0.9) > 1e-9:
            st.caption(
                f"A base técnica tem S₁ = {_pt(vento_base.s1)}: escolha o relevo (talude ou morro) "
                "aqui e confira."
            )
        linha = st.columns(4)
        v0 = _numero(
            "Velocidade básica V₀ (m/s)",
            "vt_v0",
            vento_base.v0_m_s,
            AJUDA["v0"],
            minimo=10.0,
            maximo=80.0,
            passo=1.0,
            formato="%.1f",
            alvo=linha[0],
        )
        relevo = linha[1].selectbox(
            "Relevo (S₁)",
            relevos,
            index=relevos.index(_relevo_da_base(vento_base.s1)),
            format_func=lambda item: ROTULOS_RELEVO[item],
            key="vt_relevo",
            persist_state="session",
            help=AJUDA["relevo"],
        )
        categoria = linha[2].selectbox(
            "Rugosidade do terreno (S₂)",
            categorias,
            index=categorias.index(vento_base.categoria)
            if vento_base.categoria in categorias
            else 2,
            format_func=lambda item: f"Categoria {item}",
            key="vt_categoria",
            persist_state="session",
            help=AJUDA["categoria"],
        )
        grupo = linha[3].selectbox(
            "Grupo da edificação (S₃)",
            grupos,
            index=grupos.index(grupo_base) if grupo_base in grupos else 2,
            format_func=lambda item: f"Grupo {item} — S₃ = {_pt(v6123.GRUPOS_S3[item][0])}",
            key="vt_grupo",
            persist_state="session",
            help=AJUDA["grupo"],
        )
        if relevo == RELEVO_TALUDE:
            colunas_t = st.columns(3)
            theta_t = _numero(
                "Inclinação média do talude θ (°)",
                "vt_theta_t",
                10.0,
                AJUDA["talude_theta"],
                minimo=0.0,
                maximo=90.0,
                passo=1.0,
                alvo=colunas_t[0],
            )
            z_t = _numero(
                "Altura z do ponto acima do terreno (m)",
                "vt_z_t",
                5.0,
                AJUDA["talude_z"],
                minimo=0.0,
                passo=1.0,
                alvo=colunas_t[1],
            )
            d_t = _numero(
                "Desnível d do talude ou morro (m)",
                "vt_d_t",
                30.0,
                AJUDA["talude_d"],
                minimo=0.1,
                passo=1.0,
                alvo=colunas_t[2],
            )
            try:
                s1 = v6123.fator_s1("talude", inclinacao_graus=theta_t, z_m=z_t, d_m=d_t)
            except ValueError as erro:
                st.error(f"Relevo: {erro}", icon=":material/error:")
                st.stop()
        else:
            s1 = v6123.fator_s1(relevo)
        linha2 = st.columns(3)
        classe = linha2[0].selectbox(
            "Classe da superfície frontal (S₂)",
            list(ROTULOS_CLASSE),
            format_func=lambda item: ROTULOS_CLASSE[item],
            key="vt_classe",
            persist_state="session",
            help=AJUDA["classe"],
        )
        referencia = linha2[1].selectbox(
            "Altura de referência para S₂",
            list(ve.REFERENCIAS_DE_ALTURA),
            format_func=lambda item: ROTULOS_ALTURA_REFERENCIA[item],
            key="vt_ref_altura",
            persist_state="session",
            help=AJUDA["ref_altura"],
        )
        vedacao = linha2[2].toggle(
            "Vedações com 0,92·S₃",
            key="vt_vedacao_092",
            value=False,
            help=AJUDA["vedacao_092"],
        )
        usar_cliente = False
        if s3_cliente is not None:
            usar_cliente = bool(
                st.toggle(
                    f"Usar o S₃ = {_pt(s3_cliente)} do critério do cliente",
                    value=True,
                    key="vt_s3_cliente",
                    persist_state="session",
                    help=AJUDA["s3_cliente"],
                )
            )
        estatistico = (
            False
            if usar_cliente
            else st.toggle(
                "Calcular S₃ por probabilidade e vida útil (Anexo B)",
                key="vt_s3_estat",
                value=False,
                help=AJUDA["s3_estat"],
            )
        )
        pm = ma = None
        s3: float | None = s3_cliente if usar_cliente else None
        if usar_cliente:
            st.caption(
                f"S₃ = {_pt(s3_cliente or 0.0)} do {base.rotulo_cliente if base else 'cliente'}, "
                f"no lugar do S₃ do grupo {grupo}: confirme o conflito acima com o cliente."
            )
        if base is not None:
            botao_recarregar_da_base(
                CHAVES_DA_BASE, key="vt_recarregar_base", ajuda=AJUDA["btn_recarregar_base"]
            )
        if estatistico:
            colunas_s3 = st.columns(2)
            pm = _numero(
                "Probabilidade P_m",
                "vt_pm",
                0.63,
                AJUDA["pm"],
                minimo=0.01,
                maximo=0.99,
                passo=0.01,
                alvo=colunas_s3[0],
            )
            ma = _numero(
                "Vida útil m_a (anos)",
                "vt_ma",
                50.0,
                AJUDA["ma"],
                minimo=1.0,
                maximo=500.0,
                passo=5.0,
                alvo=colunas_s3[1],
            )
            s3, aviso = v6123.fator_s3_do_projeto(int(grupo), pm, ma)
            if aviso:
                avisos.append(aviso)
            st.caption(
                f"S₃ do Anexo B com P_m = {_pt(pm)} e m_a = {_pt(ma, 0)} anos: "
                f"**{_pt(s3, 3)}** (mínimo do grupo {grupo}: {_pt(v6123.fator_s3(int(grupo)))})."
            )
    for aviso in avisos:
        st.warning(aviso, icon=":material/warning:")
    return DadosLocal(
        v0,
        relevo,
        s1,
        categoria,
        int(grupo),
        s3,
        pm,
        ma,
        None if classe == CLASSE_AUTOMATICA else classe,
        referencia,
        vedacao,
        tuple(avisos),
    )


# ---------------------------------------------------------------------------
# 2. Edificação
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DadosEdificio:
    cobertura: str
    theta: float
    a: float
    b: float
    h: float
    beiral: float
    espacamento: float
    periodo: float | None


def formulario_edificio() -> DadosEdificio:
    with st.container(border=True):
        st.subheader("2. Edificação", help=AJUDA["sec_2"])
        linha = st.columns(4)
        cobertura = linha[0].selectbox(
            "Cobertura",
            list(ve.COBERTURAS),
            index=1,
            format_func=lambda item: ROTULOS_COBERTURA[item],
            key="vt_cobertura",
            persist_state="session",
            help=AJUDA["cobertura"],
        )
        plana = cobertura == ve.COBERTURA_PLANA
        theta = _numero(
            "Inclinação do telhado θ (°)",
            "vt_theta",
            10.0,
            AJUDA["theta"],
            minimo=0.0,
            maximo=89.0,
            passo=1.0,
            desligado=plana,
            alvo=linha[1],
        )
        a = _numero(
            "Comprimento a, ao longo da cumeeira (m)",
            "vt_a",
            60.0,
            AJUDA["a"],
            passo=1.0,
            alvo=linha[2],
        )
        b = _numero("Largura b, o vão (m)", "vt_b", 30.0, AJUDA["b"], passo=1.0, alvo=linha[3])
        linha2 = st.columns(4)
        h = _numero("Altura h do beiral (m)", "vt_h", 8.0, AJUDA["h"], passo=0.5, alvo=linha2[0])
        beiral = _numero(
            "Balanço do beiral (m)",
            "vt_beiral",
            0.0,
            AJUDA["beiral"],
            minimo=0.0,
            passo=0.1,
            alvo=linha2[1],
        )
        espacamento = _numero(
            "Espaçamento dos pórticos (m)",
            "vt_espacamento",
            6.0,
            AJUDA["espacamento"],
            passo=0.5,
            alvo=linha2[2],
        )
        periodo = _numero(
            "Período fundamental T₁ (s) — 0 estima",
            "vt_periodo",
            0.0,
            AJUDA["periodo"],
            minimo=0.0,
            passo=0.1,
            alvo=linha2[3],
        )
    return DadosEdificio(
        cobertura,
        0.0 if plana else theta,
        a,
        b,
        h,
        beiral,
        espacamento,
        periodo if periodo > 0 else None,
    )


# ---------------------------------------------------------------------------
# 3. Pressão interna, vizinhança e turbulência
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DadosAmbiente:
    cenario: str
    cpis: tuple[float, ...] | None
    alta_turbulencia: bool
    altura_media_vizinhanca_m: float
    extensao_vizinhanca_m: float
    com_vizinhanca: bool
    afastamento_m: float | None
    ct: float


def _usar_cpi_do_assistente() -> None:
    """Callback do botão: copia o c_pi do assistente para o campo de valores informados."""
    valor = st.session_state.get("_vt_cpi_do_assistente")
    if valor is None:
        return
    st.session_state["vt_cpis"] = _pt(float(valor), 2)
    st.session_state["vt_permeabilidade"] = PERMEABILIDADE_INFORMADA


def _assistente_de_abertura_dominante() -> None:
    with st.expander("Tenho uma abertura dominante (portão, janelão)", icon=":material/garage:"):
        posicao = st.selectbox(
            "Onde está a abertura dominante",
            list(POSICOES_ABERTURA),
            format_func=lambda item: POSICOES_ABERTURA[item],
            key="vt_ad_posicao",
            persist_state="session",
            help=AJUDA["ad_posicao"],
        )
        precisa_razao = posicao in ("barlavento", "paralela_alta_succao")
        razao = ce_zona = None
        if precisa_razao:
            razao = _numero(
                "Área da abertura dominante ÷ área das demais",
                "vt_ad_razao",
                2.0,
                AJUDA["ad_razao"],
                minimo=0.1,
                passo=0.25,
            )
        else:
            ce_zona = _numero(
                "C_e da zona da abertura",
                "vt_ad_ce",
                -0.4,
                AJUDA["ad_ce"],
                minimo=-3.0,
                maximo=2.0,
                passo=0.1,
            )
        try:
            sugestao = coef.cpi_abertura_dominante(
                posicao, razao_aberturas=razao, ce_da_zona=ce_zona
            )
        except ValueError as erro:
            st.error(str(erro), icon=":material/error:")
            return
        st.session_state["_vt_cpi_do_assistente"] = sugestao.valor
        st.caption(f"{sugestao.rotulo} — {sugestao.referencia}.")
        st.button(
            "Usar este c_pi nos casos de carga",
            key="vt_ad_usar",
            icon=":material/check:",
            on_click=_usar_cpi_do_assistente,
            help=AJUDA["ad_usar"],
        )


def formulario_ambiente(edificio: DadosEdificio) -> DadosAmbiente:
    with st.container(border=True):
        st.subheader("3. Pressão interna, vizinhança e turbulência", help=AJUDA["sec_3"])
        cenario = st.selectbox(
            "Permeabilidade das paredes (pressão interna c_pi)",
            list(ROTULOS_PERMEABILIDADE),
            format_func=lambda item: ROTULOS_PERMEABILIDADE[item],
            key="vt_permeabilidade",
            persist_state="session",
            help=AJUDA["permeabilidade"],
        )
        cpis: tuple[float, ...] | None = None
        if cenario == PERMEABILIDADE_INFORMADA:
            texto = st.text_input(
                "Valores de c_pi (separe por ponto e vírgula)",
                value="-0,3; 0,2",
                key="vt_cpis",
                help=AJUDA["cpis"],
            )
            try:
                cpis = coef.interpretar_cpis(texto)
            except ValueError as erro:
                st.error(str(erro), icon=":material/error:")
                st.stop()
        _assistente_de_abertura_dominante()
        linha = st.columns(3)
        vizinhanca = linha[0].toggle(
            "Há edificação alta muito próxima (vizinhança)",
            key="vt_vizinhanca",
            value=False,
            help=AJUDA["vizinhanca"],
        )
        afastamento = None
        if vizinhanca:
            afastamento = _numero(
                "Afastamento s entre as faces (m)",
                "vt_s_viz",
                10.0,
                AJUDA["s_viz"],
                minimo=0.0,
                passo=1.0,
                alvo=linha[1],
            )
        superficie = linha[2].selectbox(
            "Rugosidade da superfície (força de atrito)",
            list(coef.COEFICIENTES_ATRITO),
            format_func=lambda nome: f"C_t = {_pt(coef.COEFICIENTES_ATRITO[nome])} — {nome}",
            key="vt_ct",
            persist_state="session",
            help=AJUDA["ct"],
        )
        ct = coef.COEFICIENTES_ATRITO[superficie]
        alta = st.toggle(
            "Tratar como vento de alta turbulência",
            key="vt_alta_turb",
            value=False,
            help=AJUDA["alta_turb"],
        )
        altura_viz = extensao = 0.0
        if alta:
            colunas_a = st.columns(2)
            altura_viz = _numero(
                "Altura média das vizinhas a barlavento (m)",
                "vt_h_viz",
                max(edificio.h, 10.0),
                AJUDA["h_viz"],
                passo=1.0,
                alvo=colunas_a[0],
            )
            extensao = _numero(
                "Extensão dessas vizinhas a barlavento (m)",
                "vt_ext_viz",
                500.0,
                AJUDA["ext_viz"],
                passo=100.0,
                alvo=colunas_a[1],
            )
    return DadosAmbiente(
        cenario, cpis, alta, altura_viz, extensao, vizinhanca, afastamento, float(ct)
    )


# ---------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------


def _entrada_do_calculo(
    local: DadosLocal, edificio: DadosEdificio, ambiente: DadosAmbiente
) -> ve.EntradaEdificio:
    return ve.EntradaEdificio(
        v0_m_s=local.v0_m_s,
        comprimento_a_m=edificio.a,
        largura_b_m=edificio.b,
        altura_h_m=edificio.h,
        cobertura=edificio.cobertura,
        theta_graus=edificio.theta,
        s1=local.s1,
        categoria=local.categoria,
        grupo_s3=local.grupo,
        s3=local.s3,
        classe=local.classe,
        referencia_altura=local.referencia_altura,
        vedacoes_com_092=local.vedacoes_com_092,
        cenario_permeabilidade=(
            "quatro_faces" if ambiente.cenario == PERMEABILIDADE_INFORMADA else ambiente.cenario
        ),
        cpis_informados=ambiente.cpis if ambiente.cenario == PERMEABILIDADE_INFORMADA else None,
        alta_turbulencia=ambiente.alta_turbulencia,
        altura_media_vizinhanca_m=ambiente.altura_media_vizinhanca_m,
        extensao_vizinhanca_m=ambiente.extensao_vizinhanca_m,
        com_vizinhanca=ambiente.com_vizinhanca,
        afastamento_vizinha_m=ambiente.afastamento_m,
        ct_atrito=ambiente.ct,
        espacamento_porticos_m=edificio.espacamento,
        beiral_m=edificio.beiral,
        periodo_fundamental_s=edificio.periodo,
    )


def _csv(tabela: pd.DataFrame) -> bytes:
    return tabela.to_csv(index=False, lineterminator="\r\n").encode("utf-8-sig")


def _resumo(resultado: ve.ResultadoEdificio) -> None:
    geral = status_geral(list(resultado.verificacoes))
    with st.container(border=True):
        st.subheader("Resumo do vento", help=AJUDA["sec_res"])
        st.badge(
            f"Campo de aplicação da norma: {geral}",
            color=COR_BADGE[geral],
            icon=":material/verified:" if geral == "OK" else ":material/rule:",
            help=AJUDA["res_status"],
        )
        with st.container(horizontal=True):
            for alpha in (0, 90):
                vento = resultado.vento_por_alpha[alpha]
                st.metric(
                    f"V_k a {alpha}° (classe {resultado.classe_por_alpha[alpha]})",
                    f"{vento.vk_m_s:.2f} m/s",
                    border=True,
                    help=AJUDA["res_vk"],
                )
                st.metric(
                    f"q a {alpha}°",
                    f"{vento.q_kN_m2:.3f} kN/m²",
                    border=True,
                    help=AJUDA["res_q"],
                )
            st.metric(
                "q das vedações",
                f"{resultado.vento_vedacoes.q_kN_m2:.3f} kN/m²",
                border=True,
                help=AJUDA["res_qved"],
            )
        g = resultado.geometria
        st.caption(
            f"Altura do topo: {_pt(g.h_topo_m)} m · x = {_pt(g.x_m)} m (zonas de altas sucções) · "
            f"y = {_pt(g.y_telhado_m)} m · S₂ calculado a {_pt(resultado.vento_por_alpha[0].altura_m)} m."
        )


def _aba_pressoes(resultado: ve.ResultadoEdificio) -> None:
    casos = {caso.nome: caso for caso in resultado.casos}
    _manter_opcao_valida("vt_res_caso", list(casos))
    escolha = st.selectbox(
        "Caso de vento",
        list(casos),
        key="vt_res_caso",
        help=AJUDA["res_caso"],
    )
    caso = casos[escolha]
    st.subheader("Pressões por zona", help=AJUDA["res_zonas"])
    st.image(svg_planta(resultado, caso.alpha), width="stretch")
    tabela = pd.DataFrame(ve.tabela_de_pressoes(caso))
    st.dataframe(
        tabela,
        hide_index=True,
        width="stretch",
        column_config={
            "Zona": st.column_config.TextColumn(width="medium"),
            "Onde": st.column_config.TextColumn(width="medium"),
            "C_e": st.column_config.NumberColumn(format="%.2f"),
            "Área (m²)": st.column_config.NumberColumn(format="%.1f"),
            "q·C_e (kN/m²)": st.column_config.NumberColumn(format="%.3f"),
            "Δp = q·(C_e − c_pi) (kN/m²)": st.column_config.NumberColumn(format="%.3f"),
            "Força (kN)": st.column_config.NumberColumn(format="%.1f"),
        },
    )
    st.download_button(
        "Baixar as pressões deste caso em CSV",
        data=_csv(tabela),
        file_name="vento_pressoes_por_zona.csv",
        mime="text/csv",
        icon=":material/download:",
        key="vt_baixar_zonas",
        help=AJUDA["btn_csv_zonas"],
    )
    st.caption(
        f"Resultante horizontal: F_x = {_pt(caso.fx_kN, 1)} kN, F_y = {_pt(caso.fy_kN, 1)} kN · "
        f"empuxo vertical no telhado: {_pt(caso.fz_telhado_kN, 1)} kN (positivo = para cima)."
    )


def _aba_vedacoes(resultado: ve.ResultadoEdificio) -> None:
    st.subheader("Vedações, terças, travessas e fixações", help=AJUDA["res_vedacoes"])
    cpis = sorted({c for linha in resultado.vedacoes for c, _p in linha.liquida_por_cpi})
    linhas = []
    for linha in resultado.vedacoes:
        por_cpi = dict(linha.liquida_por_cpi)
        registro: dict[str, object] = {
            "Zona": linha.zona,
            "Onde": linha.descricao,
            "Coeficiente": f"{linha.fonte_cpe} = {_pt(linha.cpe)}",
            "q·C (kN/m²)": linha.pressao_externa_kN_m2,
        }
        for cpi in cpis:
            registro[f"Δp, c_pi = {_pt(cpi)} (kN/m²)"] = por_cpi.get(cpi)
        registro["Mais desfavorável (kN/m²)"] = linha.mais_desfavoravel_kN_m2
        linhas.append(registro)
    tabela = pd.DataFrame(linhas)
    st.dataframe(tabela, hide_index=True, width="stretch")
    st.download_button(
        "Baixar as pressões das vedações em CSV",
        data=_csv(tabela),
        file_name="vento_vedacoes.csv",
        mime="text/csv",
        icon=":material/download:",
        key="vt_baixar_vedacoes",
        help=AJUDA["btn_csv_vedacoes"],
    )
    st.caption(
        f"q das vedações = {_pt(resultado.vento_vedacoes.q_kN_m2, 3)} kN/m² (classe A, topo). "
        "Δp negativa puxa a telha para cima; positiva a empurra para baixo. Para a fixação use a "
        "pior das linhas da zona onde ela está."
    )


def _aba_globais(resultado: ve.ResultadoEdificio) -> None:
    st.subheader("Forças globais e torção", help=AJUDA["res_globais"])
    linhas = []
    for alpha, r in resultado.arrasto.items():
        casos = resultado.casos_do_angulo(alpha)
        linhas.append(
            {
                "Vento": f"{alpha}°",
                "Classe": r.classe,
                "q (kN/m²)": r.q_kN_m2,
                "C_a": r.ca.valor,
                "A_e = ℓ₁·h (m²)": r.area_frontal_m2,
                "F_a = q·C_a·A_e·f_v (kN)": r.forca_kN,
                "Soma das zonas (kN)": r.soma_das_zonas_kN,
                "Empuxo máx. no telhado (kN)": max(c.fz_telhado_kN for c in casos),
                "Excentricidade e (m)": r.excentricidade_m,
                "M_t = F_a·e (kN·m)": r.torsor_kNm,
                "Atrito F_t (kN)": r.atrito.total_kN,
            }
        )
    st.dataframe(
        pd.DataFrame(linhas),
        hide_index=True,
        width="stretch",
        column_config={
            "q (kN/m²)": st.column_config.NumberColumn(format="%.3f"),
            "C_a": st.column_config.NumberColumn(format="%.2f"),
            "A_e = ℓ₁·h (m²)": st.column_config.NumberColumn(format="%.1f"),
            "F_a = q·C_a·A_e·f_v (kN)": st.column_config.NumberColumn(format="%.1f"),
            "Soma das zonas (kN)": st.column_config.NumberColumn(format="%.1f"),
            "Empuxo máx. no telhado (kN)": st.column_config.NumberColumn(format="%.1f"),
            "Excentricidade e (m)": st.column_config.NumberColumn(format="%.2f"),
            "M_t = F_a·e (kN·m)": st.column_config.NumberColumn(format="%.1f"),
            "Atrito F_t (kN)": st.column_config.NumberColumn(format="%.1f"),
        },
    )
    st.subheader("Torção e excentricidade", help=AJUDA["res_torcao"], divider=False)
    st.caption(
        "A 0°, o vento bate na largura b e a força F_a age com excentricidade e_b; a 90°, bate no "
        "comprimento a, com e_a (6.1.4). C_a vem da Figura 4 (ou da 5, em alta turbulência), lida "
        "no gráfico com incerteza de ±0,03; fora do gráfico (h/ℓ₁ < 0,5) vale o contorno."
    )


@dataclass(frozen=True)
class DadosSolucao:
    solucao: vp.SolucaoPortico | None
    descricao_bases: str
    descricao_pilar: str
    descricao_rafter: str


def _secao(
    prefixo: str,
    rotulo: str,
    padrao_a_cm2: float,
    padrao_i_cm4: float,
    ajudas: tuple[str, str, str],
    modulo_e_mpa: float,
) -> tuple[vp.SecaoDoElemento, str]:
    """Seção de um grupo de elementos: perfil do catálogo ou A e I digitados."""
    ajuda_perfil, ajuda_area, ajuda_inercia = ajudas
    perfis = catalogo_perfis.listar_perfis()
    nomes = [PERFIL_INFORMAR, *sorted(perfis)]
    modo = st.selectbox(
        f"{rotulo}: perfil",
        nomes,
        key=f"vt_p_perfil_{prefixo}",
        persist_state="session",
        help=ajuda_perfil,
    )
    if modo == PERFIL_INFORMAR:
        colunas = st.columns(2)
        area = _numero(
            f"{rotulo}: área A (cm²)",
            f"vt_p_area_{prefixo}",
            padrao_a_cm2,
            ajuda_area,
            passo=5.0,
            alvo=colunas[0],
        )
        inercia = _numero(
            f"{rotulo}: inércia I (cm⁴)",
            f"vt_p_inercia_{prefixo}",
            padrao_i_cm4,
            ajuda_inercia,
            passo=500.0,
            alvo=colunas[1],
        )
        return (
            vp.SecaoDoElemento(area * 100.0, inercia * 1e4, modulo_e_mpa),
            f"A = {_pt(area, 1)} cm²; I = {_pt(inercia, 0)} cm⁴",
        )
    perfil = perfis[modo]
    st.caption(
        f"{modo}: A = {_pt(perfil.area_mm2 / 100.0, 1)} cm²; I_x = {_pt(perfil.ix_mm4 / 1e4, 0)} cm⁴."
    )
    return vp.SecaoDoElemento(perfil.area_mm2, perfil.ix_mm4, modulo_e_mpa), modo


def _aba_portico(resultado: ve.ResultadoEdificio) -> tuple[list[vp.CasoPortico], DadosSolucao]:
    casos = vp.casos_do_portico(resultado)
    st.subheader("Cargas no pórtico transversal", help=AJUDA["res_portico"])
    compacta = pd.DataFrame(vp.tabela_compacta_do_portico(casos))
    st.dataframe(
        compacta,
        hide_index=True,
        width="stretch",
        column_config={
            "Caso": st.column_config.TextColumn(width="large"),
            **{
                f"{vp.ROTULOS_CURTOS_MEMBROS[id_]} (kN/m)": st.column_config.NumberColumn(
                    format="%.2f"
                )
                for id_ in vp.MEMBROS
            },
        },
    )
    st.download_button(
        "Baixar as cargas do pórtico em CSV",
        data=_csv(pd.DataFrame(vp.tabela_do_portico(casos))),
        file_name="vento_cargas_do_portico.csv",
        mime="text/csv",
        icon=":material/download:",
        key="vt_baixar_portico",
        help=AJUDA["btn_csv_portico"],
    )
    st.caption(
        f"Espaçamento {_pt(resultado.entrada.espacamento_porticos_m)} m. No pórtico de "
        "extremidade (empena) use a metade. As cargas são **características** (sem majorar); "
        "o vento entra nas combinações com γ_q = 1,4 (NBR 8800)."
    )
    st.subheader("Solução rápida do pórtico", divider=True, help=AJUDA["p_modo"])
    st.caption(
        "Resolve o pórtico plano (4 barras, 5 nós) só com o vento do caso escolhido, pelo "
        "solver 2D do programa. Peso próprio e sobrecarga ficam nas combinações."
    )
    opcoes = st.columns([2, 1, 1, 1])
    modulo_e = _numero(
        "Módulo de elasticidade E (MPa)",
        "vt_p_modulo_e",
        E_ACO_MPA,
        AJUDA["p_modulo_e"],
        passo=1000.0,
        alvo=opcoes[3],
    )
    colunas = st.columns(2)
    with colunas[0]:
        pilar, desc_pilar = _secao(
            "pilar",
            "Pilares",
            60.0,
            8000.0,
            (AJUDA["p_perfil_pilar"], AJUDA["p_area_pilar"], AJUDA["p_inercia_pilar"]),
            modulo_e,
        )
    with colunas[1]:
        rafter, desc_rafter = _secao(
            "rafter",
            "Águas do telhado",
            45.0,
            6000.0,
            (AJUDA["p_perfil_rafter"], AJUDA["p_area_rafter"], AJUDA["p_inercia_rafter"]),
            modulo_e,
        )
    bases = opcoes[1].radio(
        "Bases dos pilares",
        [BASES_ENGASTADAS, BASES_ROTULADAS],
        horizontal=True,
        key="vt_p_bases",
        help=AJUDA["p_bases"],
    )
    por_rotulo = {_rotulo_caso(c): c for c in casos}
    _manter_opcao_valida("vt_p_caso", list(por_rotulo))
    escolhido = opcoes[0].selectbox(
        "Caso a resolver",
        list(por_rotulo),
        key="vt_p_caso",
        help=AJUDA["p_caso"],
    )
    limite = _numero(
        "Limite do deslocamento H/…",
        "vt_p_limite",
        300.0,
        AJUDA["p_limite"],
        minimo=50.0,
        maximo=2000.0,
        passo=50.0,
        alvo=opcoes[2],
    )
    geometria = vp.geometria_do_portico(resultado.geometria)
    try:
        solucao = vp.resolver_portico(
            geometria,
            por_rotulo[escolhido],
            pilar=pilar,
            rafter=rafter,
            bases_engastadas=bases == BASES_ENGASTADAS,
        )
    except ValueError as erro:
        st.error(f"Não foi possível resolver o pórtico: {erro}", icon=":material/error:")
        return casos, DadosSolucao(None, bases, desc_pilar, desc_rafter)
    altura = resultado.geometria.h_parede_y0_m * 1000.0
    desloc = solucao.deslocamento_horizontal_max_mm
    with st.container(horizontal=True):
        st.metric(
            "Deslocamento horizontal máximo",
            f"{desloc:.1f} mm",
            border=True,
            help=AJUDA["res_p_desloc"],
        )
        st.metric(
            "H ÷ deslocamento",
            "—" if desloc <= 0 else f"{altura / desloc:.0f}",
            border=True,
            help=AJUDA["res_p_desloc"],
        )
        st.metric(
            "Deslocamento vertical máximo",
            f"{solucao.deslocamento_vertical_max_mm:.1f} mm",
            border=True,
            help=AJUDA["res_p_desloc"],
        )
    if desloc > 0:
        if altura / desloc >= limite:
            st.caption(
                f":material/check_circle: H/Δ = {altura / desloc:.0f} ≥ {limite:.0f}: o "
                "deslocamento horizontal fica dentro do limite informado (vento característico)."
            )
        else:
            st.warning(
                f"H/Δ = {altura / desloc:.0f} < {limite:.0f}: o deslocamento horizontal passa do "
                "limite informado. Enrijeça o pórtico (perfis maiores, bases engastadas) ou "
                "revise o limite do projeto.",
                icon=":material/warning:",
            )
    st.markdown("**Reações nas bases**", help=AJUDA["res_p_reacoes"])
    st.dataframe(pd.DataFrame(solucao.reacoes), hide_index=True, width="stretch")
    st.markdown("**Esforços nas pontas dos elementos**", help=AJUDA["res_p_esforcos"])
    st.dataframe(pd.DataFrame(solucao.esforcos), hide_index=True, width="stretch")
    for aviso in solucao.avisos:
        st.warning(aviso, icon=":material/warning:")
    return casos, DadosSolucao(solucao, bases, desc_pilar, desc_rafter)


def _rotulo_caso(caso: vp.CasoPortico) -> str:
    faixa = (
        ""
        if caso.faixa_x_m is None
        else f" · de {_pt(caso.faixa_x_m[0], 1)} a {_pt(caso.faixa_x_m[1], 1)} m da empena"
    )
    return f"{caso.nome}{faixa}"


def _aba_verificacoes(
    resultado: ve.ResultadoEdificio,
    casos_portico: list[vp.CasoPortico],
    solucao: DadosSolucao,
    local: DadosLocal,
) -> None:
    st.subheader("Verificações e valores de apoio", help=AJUDA["res_verificacoes"])
    mostrar_tabela_verificacoes(list(resultado.verificacoes))
    st.download_button(
        "Baixar verificações em CSV",
        data=csv_verificacoes(list(resultado.verificacoes)),
        file_name="vento_verificacoes.csv",
        mime="text/csv",
        icon=":material/download:",
        width="stretch",
        key="vt_baixar_verificacoes",
        help=AJUDA["btn_csv_verificacoes"],
    )
    with st.expander("Memória de cálculo", icon=":material/functions:"):
        for linha in resultado.memoria:
            st.markdown(f"- {linha}")
    for aviso in resultado.avisos:
        st.warning(aviso, icon=":material/warning:")
    fronteira_modelo(
        [
            "Edificações de planta não retangular, com lanternins, marquises, sheds, galpões "
            "geminados (telhados múltiplos), telhados curvos ou cobertura isolada: a norma tem "
            "outras tabelas (Tabelas 9 a 12, 15 a 25) que não estão aqui.",
            "Efeitos dinâmicos (resposta flutuante, desprendimento de vórtices) e estruturas com "
            "T₁ > 1 s: apenas sinalizados.",
            "Vizinhança só pelo fator f_v da norma para duas edificações altas; túnel de vento "
            "e estudos de topografia complexa não são cobertos.",
            "O pórtico é plano e linear; cargas de peso próprio, sobrecarga e as combinações da "
            "NBR 8800 ficam em Casos e combinações de carga e em Estruturas de aço.",
        ]
    )
    contexto: dict[str, Any] = {
        "relevo": ROTULOS_RELEVO[local.relevo],
        "probabilidade_pm": local.pm,
        "vida_util_anos": local.ma,
    }
    if solucao.solucao is not None:
        contexto.update(
            {
                "portico_bases": solucao.descricao_bases,
                "portico_pilar": solucao.descricao_pilar,
                "portico_rafter": solucao.descricao_rafter,
            }
        )
    registro = registro_vento.registro_edificacao(
        resultado,
        casos_do_portico=casos_portico,
        solucao=solucao.solucao,
        contexto=contexto,
    )
    with st.container(border=True):
        st.subheader("Registrar no projeto", help=AJUDA["reg_registrar"])
        botao_registrar_calculo(
            registro,
            key="registrar_vento_nbr6123",
            rotulo="Registrar o vento no projeto ativo",
        )


def mostrar_vento_nas_estruturas() -> None:
    """Desenha a página: entradas, resultados e registro."""
    local = formulario_local()
    edificio = formulario_edificio()
    ambiente = formulario_ambiente(edificio)
    try:
        resultado = ve.calcular_edificacao(_entrada_do_calculo(local, edificio, ambiente))
    except ValueError as erro:
        st.error(f"Não foi possível calcular: {erro}", icon=":material/error:")
        st.stop()
    st.header("Resultados")
    _resumo(resultado)
    aba_pressoes, aba_vedacoes, aba_globais, aba_portico, aba_verificacoes = st.tabs(
        [
            "Pressões por zona",
            "Vedações e fixações",
            "Forças globais",
            "Pórtico transversal",
            "Verificações e registro",
        ]
    )
    with aba_pressoes:
        _aba_pressoes(resultado)
    with aba_vedacoes:
        _aba_vedacoes(resultado)
    with aba_globais:
        _aba_globais(resultado)
    with aba_portico:
        casos_portico, solucao = _aba_portico(resultado)
    with aba_verificacoes:
        _aba_verificacoes(resultado, casos_portico, solucao, local)
    st.caption(
        "Forças do vento em edificações pela NBR 6123:2023. O programa calcula e o engenheiro "
        "responsável decide: confira V₀ no mapa de isopletas, a categoria do terreno e as "
        "hipóteses de pressão interna antes de usar os valores."
    )
