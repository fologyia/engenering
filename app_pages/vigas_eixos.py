import math
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))

from components.project_tools import (
    botao_registrar_calculo,
    construir_registro_tecnico,
    id_registro_existente,
)
from components.ui import cabecalho_pagina, comparador_cenarios, fronteira_modelo
from core import beam_analysis as vigas
from core import beam_script as escrita
from core import materials as materiais_base
from core import steel_sections as secoes
from core.materials_registry import avaliar_material
from core.project_criteria import normalizar_criterios_projeto
from core.project_store import obter_projeto_ativo

st.set_page_config(
    page_title="Vigas e eixos",
    page_icon=":material/linear_scale:",
    layout="wide",
)

CHAVE_SCRIPT = "vigas_script"
CHAVE_RESULTADO = "vigas_resultado"

CORES = {
    "normal": "#0f766e",
    "cortante": "#2563eb",
    "momento": "#dc2626",
    "flecha": "#7c3aed",
    "torque": "#ea580c",
    "tensao": "#0891b2",
}

FORMAS_APOIO = {
    "pino": "triangle-up",
    "rolete": "circle",
    "engaste": "square",
    "engaste deslizante": "diamond",
    "apoio horizontal": "cross",
    "mola": "triangle-down",
    "livre": "stroke",
}

TIPOS_CARGA = (
    "Força pontual (kN)",
    "Momento concentrado (kN·m)",
    "Distribuída (kN/m)",
    "Carga axial (kN)",
    "Axial distribuída (kN/m)",
    "Torque (kN·m)",
)


def numero(valor: float, casas: int = 2) -> str:
    if valor is None or (isinstance(valor, float) and not math.isfinite(valor)):
        return "∞"
    return f"{valor:,.{casas}f}".replace(",", " ")


def fator_seguranca_minimo_do_projeto() -> float:
    """Meta de fator de segurança vinda dos critérios do projeto ativo.

    Sem projeto aberto cai no mesmo 1,5 que é o padrão de
    ``core.project_criteria`` — o número não muda, mas deixa de estar
    chumbado em dois lugares diferentes do programa.
    """
    projeto = obter_projeto_ativo()
    criterios = normalizar_criterios_projeto((projeto or {}).get("criterios_projeto"))
    return float(criterios["seguranca"]["fator_seguranca_minimo"])


def enviar_para_mohr(estado, *, origem_id: str | None) -> None:
    """Mesmo contrato usado pelo assistente de cargas."""
    st.session_state["mohr_assistente_2d"] = {
        "sigma_x": estado.sigma_x,
        "sigma_y": estado.sigma_y,
        "tau_xy": estado.tau_xy,
        "descricao": estado.descricao,
        "origem_registro_id": origem_id,
    }
    st.session_state["mohr_tipo_estado"] = "Estado plano (2D)"
    st.session_state["mohr_2d_exemplo"] = "assistente"
    for chave in (
        "mohr_2d_sigma_x_assistente",
        "mohr_2d_sigma_y_assistente",
        "mohr_2d_tau_xy_assistente",
        "mohr_2d_theta_assistente",
    ):
        st.session_state.pop(chave, None)
    st.switch_page("app_pages/circulo_mohr.py")


def enviar_para_estatica(estado, *, origem_id: str | None) -> None:
    st.session_state["estatica_sigma_x"] = estado.sigma_x
    st.session_state["estatica_sigma_y"] = estado.sigma_y
    st.session_state["estatica_tau_xy"] = estado.tau_xy
    st.session_state["estatica_origem_registro_id"] = origem_id
    st.switch_page("app_pages/analise_estatica.py")


def enviar_para_fadiga(amplitudes: dict) -> None:
    st.session_state["fadiga_sigma_alternada_nominal"] = float(
        amplitudes["sigma_alternada_MPa"]
    )
    st.session_state["fadiga_sigma_media"] = float(amplitudes["sigma_media_MPa"])
    st.switch_page("app_pages/analise_fadiga.py")


cabecalho_pagina(
    "Vigas e eixos",
    "Cortante • momento fletor • linha elástica • torção • cargas combinadas",
    categoria="Análises",
    icone=":material/linear_scale:",
    cor="blue",
    ajuda_modulo="Vigas e eixos",
    acoes=(
        ("app_pages/assistente_cargas.py", "Assistente de cargas", ":material/manufacturing:"),
        ("app_pages/estruturas_aco.py", "Estruturas de aço", ":material/domain:"),
    ),
    modulo_id="vigas_eixos",
)
st.caption(
    "Barra reta com qualquer combinação de apoios, rótulas internas e cargas — "
    "inclusive isostática e hiperestática. O modelo é descrito por **texto e "
    "números** (ou por formulário) e resolvido por rigidez direta com elementos "
    "de Euler-Bernoulli; dentro de cada trecho, V(x), M(x) e a linha elástica "
    "saem de integração analítica, não de interpolação."
)

st.session_state.setdefault(CHAVE_SCRIPT, escrita.EXEMPLOS["Viga biapoiada com carga distribuída"])

projeto_ativo = obter_projeto_ativo()
materiais_projeto = list((projeto_ativo or {}).get("materiais_projeto", []))


# ---------------------------------------------------------------------------
# 1. Entrada do modelo
# ---------------------------------------------------------------------------

with st.container(border=True):
    st.subheader("1. Modelo da barra")
    modo = st.segmented_control(
        "Como você prefere informar o modelo?",
        ["Texto (script)", "Formulário"],
        default="Texto (script)",
        required=True,
        width="stretch",
        key="vigas_modo_entrada",
        persist_state="session",
    )

    if modo == "Texto (script)":
        colunas_exemplo = st.columns([3, 1])
        exemplo = colunas_exemplo[0].selectbox(
            "Carregar um exemplo pronto",
            list(escrita.EXEMPLOS),
            key="vigas_exemplo",
            persist_state="session",
        )
        if colunas_exemplo[1].button(
            "Carregar exemplo",
            icon=":material/download:",
            width="stretch",
            key="vigas_carregar_exemplo",
        ):
            st.session_state[CHAVE_SCRIPT] = escrita.EXEMPLOS[exemplo]
            st.session_state.pop(CHAVE_RESULTADO, None)
            st.rerun()

        st.text_area(
            "Modelo (uma instrução por linha)",
            height=260,
            key=CHAVE_SCRIPT,
            help="Tudo depois de # é comentário. Veja a tabela de comandos abaixo.",
        )
        with st.expander("Comandos aceitos e unidades", icon=":material/menu_book:"):
            st.markdown(escrita.AJUDA_SINTAXE)
            st.caption(
                "Dica: `secao perfil <nome>` aceita qualquer perfil do catálogo — "
                f"por exemplo `{list(secoes.CATALOGO_PERFIS)[10]}`."
            )
            if materiais_projeto:
                nomes = ", ".join(
                    f"`{item.get('nome')}`" for item in materiais_projeto[:6]
                )
                st.caption(
                    "Materiais qualificados deste projeto (use "
                    f"`material projeto <nome>` para rastreabilidade): {nomes}."
                )
            else:
                st.caption(
                    "Este projeto ainda não tem materiais qualificados. Use "
                    "`material catalogo <nome>` para a base do programa, ou "
                    "cadastre em Materiais técnicos para o cálculo ficar "
                    "vinculado ao certificado."
                )
        combinacoes_projeto = list((projeto_ativo or {}).get("combinacoes_carga", []))
        casos_projeto = list((projeto_ativo or {}).get("casos_carga", []))
        if combinacoes_projeto:
            linhas_projeto = escrita.linhas_de_combinacoes_do_projeto(
                casos_projeto, combinacoes_projeto
            )
            with st.container(border=True):
                st.caption(
                    f"O projeto ativo tem {len(linhas_projeto)} combinação(ões) de "
                    "carga. Importe-as para envelopar a barra — depois marque cada "
                    "carga com `caso=<nome do caso>` para elas terem efeito."
                )
                st.code("\n".join(linhas_projeto), language="text")
                if st.button(
                    "Acrescentar as combinações do projeto ao modelo",
                    icon=":material/playlist_add:",
                    width="stretch",
                    key="vigas_importar_combinacoes",
                ):
                    atual = st.session_state[CHAVE_SCRIPT].rstrip()
                    faltantes = [
                        linha for linha in linhas_projeto if linha not in atual
                    ]
                    if faltantes:
                        st.session_state[CHAVE_SCRIPT] = (
                            atual + "\n\n" + "\n".join(faltantes) + "\n"
                        )
                        st.session_state.pop(CHAVE_RESULTADO, None)
                        st.rerun()
                    else:
                        st.info(
                            "As combinações do projeto já estão no modelo.",
                            icon=":material/check:",
                        )

        texto_modelo = st.session_state[CHAVE_SCRIPT]

    else:
        colunas_geometria = st.columns(2)
        comprimento_m = colunas_geometria[0].number_input(
            "Comprimento total L (m)",
            min_value=0.01,
            value=6.0,
            step=0.5,
            key="vigas_form_comprimento",
            persist_state="session",
        )
        nome_modelo = colunas_geometria[1].text_input(
            "Nome do modelo",
            value="Viga",
            key="vigas_form_nome",
            persist_state="session",
        )

        st.markdown("**Seção transversal**")
        tipo_secao = st.segmented_control(
            "Tipo de seção",
            [
                "Retangular",
                "Circular maciça",
                "Tubo circular",
                "Tubo retangular",
                "Perfil I soldado",
                "Perfil do catálogo",
            ],
            default="Retangular",
            required=True,
            width="stretch",
            key="vigas_form_tipo_secao",
            persist_state="session",
        )
        erro_secao = None
        try:
            if tipo_secao == "Retangular":
                colunas = st.columns(2)
                base = colunas[0].number_input(
                    "Base b (mm)", min_value=0.1, value=100.0, step=5.0,
                    key="vigas_form_ret_b", persist_state="session",
                )
                altura = colunas[1].number_input(
                    "Altura h (mm)", min_value=0.1, value=200.0, step=5.0,
                    key="vigas_form_ret_h", persist_state="session",
                )
                secao = vigas.secao_retangular(base, altura)
            elif tipo_secao == "Circular maciça":
                diametro = st.number_input(
                    "Diâmetro d (mm)", min_value=0.1, value=60.0, step=2.0,
                    key="vigas_form_circ_d", persist_state="session",
                )
                secao = vigas.secao_circular_macica(diametro)
            elif tipo_secao == "Tubo circular":
                colunas = st.columns(2)
                de = colunas[0].number_input(
                    "Diâmetro externo (mm)", min_value=0.1, value=60.3, step=1.0,
                    key="vigas_form_tubo_de", persist_state="session",
                )
                di = colunas[1].number_input(
                    "Diâmetro interno (mm)", min_value=0.0, value=54.3, step=1.0,
                    key="vigas_form_tubo_di", persist_state="session",
                )
                secao = vigas.secao_tubo_circular(de, di)
            elif tipo_secao == "Tubo retangular":
                colunas = st.columns(3)
                largura = colunas[0].number_input(
                    "Largura (mm)", min_value=0.1, value=100.0, step=5.0,
                    key="vigas_form_tr_b", persist_state="session",
                )
                altura = colunas[1].number_input(
                    "Altura (mm)", min_value=0.1, value=200.0, step=5.0,
                    key="vigas_form_tr_h", persist_state="session",
                )
                espessura = colunas[2].number_input(
                    "Espessura (mm)", min_value=0.1, value=6.0, step=0.5,
                    key="vigas_form_tr_t", persist_state="session",
                )
                secao = vigas.secao_tubo_retangular(largura, altura, espessura)
            elif tipo_secao == "Perfil I soldado":
                colunas = st.columns(4)
                altura = colunas[0].number_input(
                    "Altura h (mm)", min_value=1.0, value=300.0, step=10.0,
                    key="vigas_form_i_h", persist_state="session",
                )
                mesa = colunas[1].number_input(
                    "Largura da mesa (mm)", min_value=1.0, value=150.0, step=5.0,
                    key="vigas_form_i_bf", persist_state="session",
                )
                alma = colunas[2].number_input(
                    "Espessura da alma (mm)", min_value=0.1, value=8.0, step=0.5,
                    key="vigas_form_i_tw", persist_state="session",
                )
                espessura_mesa = colunas[3].number_input(
                    "Espessura da mesa (mm)", min_value=0.1, value=12.0, step=0.5,
                    key="vigas_form_i_tf", persist_state="session",
                )
                secao = vigas.secao_i_simetrica(altura, mesa, alma, espessura_mesa)
            else:
                colunas = st.columns([3, 1])
                nome_perfil = colunas[0].selectbox(
                    "Perfil do catálogo",
                    list(secoes.CATALOGO_PERFIS),
                    key="vigas_form_perfil", persist_state="session",
                )
                eixo = colunas[1].selectbox(
                    "Eixo de flexão", ["x", "y"],
                    key="vigas_form_eixo", persist_state="session",
                )
                secao = vigas.secao_de_perfil_catalogo(
                    secoes.obter_perfil(nome_perfil), eixo=eixo
                )
        except ValueError as erro:
            erro_secao = str(erro)
            secao = None

        if erro_secao:
            st.error(f"Seção inválida: {erro_secao}", icon=":material/error:")
            st.stop()
        st.caption(
            f":material/info: {secao.descricao} · A = {numero(secao.area_mm2, 0)} mm² · "
            f"I = {secao.inercia_mm4:.4g} mm⁴ · W = {secao.modulo_resistencia_inferior_mm3:.4g} mm³ · "
            f"J = {secao.constante_torcao_mm4:.4g} mm⁴"
        )

        st.markdown("**Material**")
        # A mesma escolha das outras páginas de cálculo: material qualificado
        # do projeto (rastreável), catálogo orientativo ou valores próprios.
        opcoes_material = {"manual": "— valores informados manualmente —"}
        for item in materiais_projeto:
            opcoes_material[f"projeto::{item['nome']}"] = (
                f"Projeto · {item.get('nome')} · {avaliar_material(item)['nivel']}"
            )
        try:
            for nome_catalogo in materiais_base.listar_nomes():
                opcoes_material[f"catalogo::{nome_catalogo}"] = (
                    f"Catálogo orientativo · {nome_catalogo}"
                )
        except (FileNotFoundError, ValueError) as erro:
            st.warning(
                f"Base de materiais indisponível: {erro}", icon=":material/warning:"
            )
        if st.session_state.get("vigas_form_material") not in opcoes_material:
            st.session_state["vigas_form_material"] = "manual"
        escolha_material = st.selectbox(
            "Material",
            list(opcoes_material),
            format_func=lambda valor: opcoes_material[valor],
            key="vigas_form_material",
            persist_state="session",
            help=(
                "Um material do projeto leva o vínculo de rastreabilidade para o "
                "registro; o catálogo é orientativo."
            ),
        )

        linha_material = ""
        e_padrao, g_padrao, sy_padrao, densidade_padrao = escrita._MATERIAIS_PRONTOS["aco"]
        if escolha_material.startswith("projeto::"):
            linha_material = f"material projeto {escolha_material.split('::', 1)[1]}"
        elif escolha_material.startswith("catalogo::"):
            linha_material = f"material catalogo {escolha_material.split('::', 1)[1]}"

        if linha_material:
            # Deixa o próprio interpretador resolver o material: assim o modo
            # formulário e o modo texto não podem discordar sobre Sy.
            try:
                previa = escrita.interpretar(
                    f"viga 1\nsecao circular 10\napoio 0 pino\n{linha_material}",
                    materiais_projeto=materiais_projeto,
                )
            except escrita.ErroDeScript as erro:
                st.error(str(erro), icon=":material/error:")
                st.stop()
            material_previa = previa.material
            densidade_padrao = material_previa.densidade_kg_m3
            colunas_material = st.columns(3)
            colunas_material[0].metric(
                "E", f"{material_previa.modulo_elasticidade_MPa / 1_000.0:.4g} GPa", border=True
            )
            colunas_material[1].metric(
                "G", f"{material_previa.modulo_cisalhamento_MPa / 1_000.0:.4g} GPa", border=True
            )
            colunas_material[2].metric(
                "Sy",
                "—" if not material_previa.escoamento_MPa else f"{material_previa.escoamento_MPa:.4g} MPa",
                border=True,
            )
            st.caption(f":material/verified: {material_previa.fonte}")
        else:
            colunas_material = st.columns(3)
            modulo_e = colunas_material[0].number_input(
                "E (GPa)", min_value=0.1, value=float(e_padrao), step=5.0,
                key="vigas_form_E", persist_state="session",
            )
            modulo_g = colunas_material[1].number_input(
                "G (GPa)", min_value=0.1, value=float(g_padrao), step=1.0,
                key="vigas_form_G", persist_state="session",
            )
            escoamento = colunas_material[2].number_input(
                "Sy (MPa)", min_value=0.0, value=float(sy_padrao), step=10.0,
                key="vigas_form_Sy", persist_state="session",
                help="Zero deixa o fator de segurança em branco.",
            )
            linha_material = (
                f"material E={modulo_e:g} G={modulo_g:g} densidade={densidade_padrao:g}"
                + (f" Sy={escoamento:g}" if escoamento > 0 else "")
            )

        peso_proprio = st.checkbox(
            "Somar o peso próprio da barra",
            value=False,
            key="vigas_form_peso", persist_state="session",
            help=f"Densidade considerada: {densidade_padrao:.0f} kg/m³.",
        )

        st.markdown(
            "**Apoios** — veja a Tabela 12.1: rolete e pino têm M = 0; o engaste "
            "trava também a rotação. `kv` e `kr` só valem para o tipo **mola** "
            "(apoio elástico) e devem ficar vazios nos demais."
        )
        apoios_padrao = pd.DataFrame(
            [
                {"x (m)": 0.0, "tipo": "pino", "kv (N/mm)": None, "kr (N·mm/rad)": None},
                {
                    "x (m)": float(comprimento_m),
                    "tipo": "rolete",
                    "kv (N/mm)": None,
                    "kr (N·mm/rad)": None,
                },
            ]
        )
        apoios_editados = st.data_editor(
            apoios_padrao,
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key="vigas_form_apoios",
            column_config={
                "x (m)": st.column_config.NumberColumn(format="%.4f", required=True),
                "tipo": st.column_config.SelectboxColumn(
                    options=["pino", "rolete", "engaste", "deslizante", "trava_axial", "mola"],
                    required=True,
                ),
                "kv (N/mm)": st.column_config.NumberColumn(
                    format="%.4g", min_value=0.0, help="Rigidez vertical do apoio elástico."
                ),
                "kr (N·mm/rad)": st.column_config.NumberColumn(
                    format="%.4g", min_value=0.0, help="Rigidez rotacional do apoio elástico."
                ),
            },
        )

        st.markdown("**Rótulas internas** (opcional) — articulação que zera o momento fletor.")
        rotulas_editadas = st.data_editor(
            pd.DataFrame({"x (m)": pd.Series(dtype="float")}),
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key="vigas_form_rotulas",
            column_config={"x (m)": st.column_config.NumberColumn(format="%.4f")},
        )

        st.markdown(
            "**Cargas** — `x2` e `valor 2` só são usados por cargas distribuídas "
            "(deixe `valor 2` vazio para carga uniforme). Positivo é **para cima**; "
            "para uma carga de gravidade use valor negativo."
        )
        cargas_padrao = pd.DataFrame(
            [
                {
                    "tipo": "Distribuída (kN/m)",
                    "x ou x1 (m)": 0.0,
                    "x2 (m)": float(comprimento_m),
                    "valor": -15.0,
                    "valor 2": None,
                },
                {
                    "tipo": "Força pontual (kN)",
                    "x ou x1 (m)": float(comprimento_m) / 2,
                    "x2 (m)": None,
                    "valor": -20.0,
                    "valor 2": None,
                },
            ]
        )
        cargas_editadas = st.data_editor(
            cargas_padrao,
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key="vigas_form_cargas",
            column_config={
                "tipo": st.column_config.SelectboxColumn(options=list(TIPOS_CARGA), required=True),
                "x ou x1 (m)": st.column_config.NumberColumn(format="%.4f", required=True),
                "x2 (m)": st.column_config.NumberColumn(format="%.4f"),
                "valor": st.column_config.NumberColumn(format="%.4f", required=True),
                "valor 2": st.column_config.NumberColumn(format="%.4f"),
            },
        )

        # O formulário é convertido para o mesmo script do modo texto: assim os
        # dois modos compartilham exatamente o mesmo parser e as mesmas
        # validações, em vez de manterem dois caminhos que podem divergir.
        linhas_script = [
            f"nome {nome_modelo or 'Viga'}",
            f"viga {comprimento_m:g}",
            (
                f"secao manual A={secao.area_mm2:.17g} I={secao.inercia_mm4:.17g} "
                f"c_sup={secao.c_superior_mm:.17g} c_inf={secao.c_inferior_mm:.17g} "
                f"Q={secao.momento_estatico_mm3:.17g} t={secao.espessura_cisalhamento_mm:.17g} "
                f"J={secao.constante_torcao_mm4:.17g} Wt={secao.modulo_torcao_mm3:.17g} "
                f"Av={secao.area_cisalhamento_mm2:.17g}   # {secao.nome}"
            ),
            linha_material,
        ]
        for _, linha in apoios_editados.dropna(subset=["x (m)", "tipo"]).iterrows():
            rigidezes = ""
            for coluna, rotulo in (("kv (N/mm)", "kv"), ("kr (N·mm/rad)", "kr")):
                valor = linha.get(coluna)
                if not pd.isna(valor) and float(valor) > 0:
                    rigidezes += f" {rotulo}={float(valor):g}"
            linhas_script.append(
                f"apoio {float(linha['x (m)']):g} {linha['tipo']}{rigidezes}"
            )
        for _, linha in rotulas_editadas.dropna(subset=["x (m)"]).iterrows():
            linhas_script.append(f"rotula {float(linha['x (m)']):g}")
        prefixos = {
            "Força pontual (kN)": "P",
            "Momento concentrado (kN·m)": "M",
            "Distribuída (kN/m)": "q",
            "Carga axial (kN)": "N",
            "Axial distribuída (kN/m)": "qn",
            "Torque (kN·m)": "T",
        }
        for _, linha in cargas_editadas.dropna(subset=["tipo", "x ou x1 (m)", "valor"]).iterrows():
            comando = prefixos[str(linha["tipo"])]
            x1 = float(linha["x ou x1 (m)"])
            valor = float(linha["valor"])
            if comando in {"q", "qn"}:
                x2 = linha["x2 (m)"]
                if pd.isna(x2):
                    st.error(
                        f"A carga distribuída em x = {x1:g} m precisa de um `x2 (m)`.",
                        icon=":material/error:",
                    )
                    st.stop()
                valor2 = linha["valor 2"]
                sufixo = "" if pd.isna(valor2) else f" {float(valor2):g}"
                linhas_script.append(f"{comando} {x1:g} {float(x2):g} {valor:g}{sufixo}")
            else:
                linhas_script.append(f"{comando} {x1:g} {valor:g}")
        if peso_proprio:
            linhas_script.append("peso_proprio")
        texto_modelo = "\n".join(linhas_script)

        with st.expander("Modelo equivalente em texto (copie para reaproveitar)", icon=":material/code:"):
            st.code(texto_modelo, language="text")

analisar = st.button(
    "Calcular diagramas",
    type="primary",
    icon=":material/calculate:",
    width="stretch",
    key="vigas_calcular",
)

if analisar:
    try:
        modelo = escrita.interpretar(
            texto_modelo, materiais_projeto=materiais_projeto
        )
        resultado = vigas.analisar_viga(modelo)
        combinacoes = escrita.combinacoes_do_script(texto_modelo)
        envoltoria = (
            vigas.analisar_envoltoria(modelo, combinacoes) if combinacoes else None
        )
    except escrita.ErroDeScript as erro:
        st.session_state.pop(CHAVE_RESULTADO, None)
        st.error(str(erro), icon=":material/error:")
    except ValueError as erro:
        st.session_state.pop(CHAVE_RESULTADO, None)
        st.error(f"Não foi possível resolver o modelo: {erro}", icon=":material/error:")
    else:
        # Guardado na sessão para sobreviver ao rerun disparado pelos botões de
        # registro e de comparação de cenários.
        st.session_state[CHAVE_RESULTADO] = {
            "script": texto_modelo,
            "resultado": resultado,
            "envoltoria": envoltoria,
        }

guardado = st.session_state.get(CHAVE_RESULTADO)
if not guardado:
    st.info(
        "Descreva a barra acima e clique em **Calcular diagramas**.",
        icon=":material/keyboard_double_arrow_up:",
    )
    st.stop()

resultado: vigas.ResultadoViga = guardado["resultado"]
envoltoria = guardado.get("envoltoria")
modelo: vigas.Viga = resultado.viga
secao = modelo.secao
material = modelo.material
comprimento_m = modelo.comprimento_mm / 1_000.0

for aviso in resultado.avisos:
    st.info(aviso, icon=":material/info:")


# ---------------------------------------------------------------------------
# 2. Esquema do modelo
# ---------------------------------------------------------------------------

with st.container(border=True):
    st.subheader("2. Esquema do modelo")
    camadas = [
        alt.Chart(pd.DataFrame({"x": [0.0, comprimento_m], "y": [0.0, 0.0]}))
        .mark_line(color="#334155", strokeWidth=4)
        .encode(x=alt.X("x:Q", title="x (m)"), y=alt.Y("y:Q", title="", axis=None))
    ]

    apoios_df = pd.DataFrame(
        [
            {
                "x": reacao.x_mm / 1_000.0,
                "y": 0.0,
                "Apoio": reacao.tipo,
                "Reação Fy (kN)": reacao.fy_N / 1_000.0,
            }
            for reacao in resultado.reacoes
        ]
    )
    camadas.append(
        alt.Chart(apoios_df)
        .mark_point(size=260, filled=True, opacity=0.95, yOffset=12)
        .encode(
            x="x:Q",
            y="y:Q",
            shape=alt.Shape(
                "Apoio:N",
                scale=alt.Scale(
                    domain=list(FORMAS_APOIO), range=list(FORMAS_APOIO.values())
                ),
                legend=alt.Legend(title="Apoio"),
            ),
            color=alt.value("#0f172a"),
            tooltip=["Apoio", "x:Q", "Reação Fy (kN)"],
        )
    )

    if modelo.rotulas:
        rotulas_df = pd.DataFrame(
            [{"x": r.x_mm / 1_000.0, "y": 0.0, "Elemento": "Rótula"} for r in modelo.rotulas]
        )
        camadas.append(
            alt.Chart(rotulas_df)
            .mark_point(size=140, shape="circle", filled=False, strokeWidth=3, color="#b91c1c")
            .encode(x="x:Q", y="y:Q", tooltip=["Elemento", "x:Q"])
        )

    if modelo.cargas_distribuidas:
        faixas = []
        for indice, carga in enumerate(modelo.cargas_distribuidas):
            faixas.append(
                {
                    "x": carga.x_inicial_mm / 1_000.0,
                    "y": carga.w_inicial_N_mm,
                    "carga": f"q{indice + 1}",
                    "ordem": 0,
                }
            )
            faixas.append(
                {
                    "x": carga.x_final_mm / 1_000.0,
                    "y": carga.w_final,
                    "carga": f"q{indice + 1}",
                    "ordem": 1,
                }
            )
        camadas.append(
            alt.Chart(pd.DataFrame(faixas))
            .mark_area(opacity=0.28, color="#2563eb", line={"color": "#2563eb"})
            .encode(
                x="x:Q",
                y=alt.Y("y:Q", title=""),
                detail="carga:N",
                order="ordem:O",
                tooltip=[alt.Tooltip("y:Q", title="q (N/mm)"), "x:Q"],
            )
        )

    marcadores = []
    for carga in modelo.cargas_pontuais:
        marcadores.append(
            {"x": carga.x_mm / 1_000.0, "rotulo": f"P = {carga.fy_N / 1_000.0:g} kN", "Tipo": "Força"}
        )
    for momento in modelo.momentos:
        marcadores.append(
            {"x": momento.x_mm / 1_000.0, "rotulo": f"M = {momento.mz_Nmm / 1e6:g} kN·m", "Tipo": "Momento"}
        )
    for torque in modelo.torques:
        marcadores.append(
            {"x": torque.x_mm / 1_000.0, "rotulo": f"T = {torque.t_Nmm / 1e6:g} kN·m", "Tipo": "Torque"}
        )
    for carga in modelo.cargas_axiais:
        marcadores.append(
            {"x": carga.x_mm / 1_000.0, "rotulo": f"N = {carga.fx_N / 1_000.0:g} kN", "Tipo": "Axial"}
        )
    if marcadores:
        marcadores_df = pd.DataFrame(marcadores)
        camadas.append(
            alt.Chart(marcadores_df)
            .mark_point(size=180, shape="triangle-down", filled=True, yOffset=-14)
            .encode(
                x="x:Q",
                y=alt.value(0),
                color=alt.Color("Tipo:N", legend=alt.Legend(title="Carga")),
                tooltip=["Tipo", "rotulo", "x:Q"],
            )
        )
        camadas.append(
            alt.Chart(marcadores_df)
            .mark_text(dy=-30, fontSize=11, color="#334155")
            .encode(x="x:Q", y=alt.value(0), text="rotulo:N")
        )

    st.altair_chart(
        alt.layer(*camadas).resolve_scale(y="independent", color="independent").properties(height=200)
    )
    detalhes = st.columns(4)
    detalhes[0].metric("Comprimento", f"{comprimento_m:g} m", border=True)
    detalhes[1].metric("Seção", secao.nome, border=True, help=secao.descricao)
    detalhes[2].metric(
        "Grau de hiperestaticidade",
        f"{resultado.grau_hiperestaticidade}",
        border=True,
        help="0 = isostática; maior que 0 = hiperestática (resolvida por rigidez direta).",
    )
    detalhes[3].metric(
        "E · I",
        f"{material.modulo_elasticidade_MPa * secao.inercia_mm4:.4g} N·mm²",
        border=True,
    )
    if material.fonte:
        icone = ":material/verified:" if material.material_id else ":material/info:"
        st.caption(f"{icone} Material: {material.fonte}")
    if not material.material_id and materiais_projeto:
        st.caption(
            ":material/link_off: Este cálculo não está vinculado a um material "
            "qualificado do projeto. Use `material projeto <nome>` para que o "
            "registro aponte para o certificado."
        )


# ---------------------------------------------------------------------------
# 3. Reações e extremos
# ---------------------------------------------------------------------------

extremos = resultado.extremos
meta_fator_seguranca = fator_seguranca_minimo_do_projeto()

if envoltoria is not None:
    # Sem este aviso, é fácil registrar como verificação de projeto um fator
    # de segurança calculado sobre as cargas sem fator de combinação.
    nome_governante, extremo_governante = envoltoria.governante("momento")
    st.warning(
        "Este modelo declara combinações de carga. **As seções 3 a 6 abaixo "
        "usam as cargas como escritas, sem fatores de combinação** — são os "
        "valores característicos. Os valores de projeto estão na aba "
        f"**Envoltória**: o momento governante é {extremo_governante.valor / 1e6:.2f} "
        f"kN·m, pela combinação {nome_governante}.",
        icon=":material/rule:",
    )

with st.container(border=True):
    st.subheader("3. Reações de apoio")
    st.dataframe(pd.DataFrame(vigas.resumo_reacoes(resultado)), hide_index=True, width="stretch")
    residuos = vigas.conferir_equilibrio(resultado)
    st.caption(
        "Conferência de equilíbrio global (deve ser ~0): "
        f"ΣFy = {residuos['residuo_fy_N']:.3e} N · "
        f"ΣFx = {residuos['residuo_fx_N']:.3e} N · "
        f"ΣM = {residuos['residuo_mz_Nmm']:.3e} N·mm · "
        f"ΣT = {residuos['residuo_mt_Nmm']:.3e} N·mm"
    )

with st.container(border=True):
    st.subheader("4. Valores extremos")
    primeira = st.columns(4)
    primeira[0].metric(
        "Cortante máximo |V|",
        f"{numero(extremos['cortante'].valor / 1_000.0)} kN",
        border=True,
        help=f"Em x = {extremos['cortante'].x_mm / 1_000.0:.3f} m.",
    )
    primeira[1].metric(
        "Momento máximo |M|",
        f"{numero(extremos['momento'].valor / 1e6)} kN·m",
        border=True,
        help=f"Em x = {extremos['momento'].x_mm / 1_000.0:.3f} m.",
    )
    primeira[2].metric(
        "Flecha máxima",
        f"{numero(extremos['flecha'].valor, 3)} mm",
        border=True,
        help=(
            f"Em x = {extremos['flecha'].x_mm / 1_000.0:.3f} m. "
            "Negativo é para baixo."
        ),
    )
    primeira[3].metric(
        "Rotação máxima",
        f"{numero(extremos['rotacao'].valor * 1_000.0, 3)} mrad",
        border=True,
        help=f"Em x = {extremos['rotacao'].x_mm / 1_000.0:.3f} m.",
    )

    segunda = st.columns(4)
    segunda[0].metric(
        "Normal máximo |N|",
        f"{numero(extremos['normal'].valor / 1_000.0)} kN",
        border=True,
        help="Positivo traciona a seção.",
    )
    segunda[1].metric(
        "Torque máximo |T|",
        f"{numero(extremos['torque'].valor / 1e6, 3)} kN·m",
        border=True,
        help=f"Giro máximo: {math.degrees(extremos['giro_torcao'].valor):.4f}°.",
    )
    segunda[2].metric(
        "Tensão normal extrema",
        f"{numero(extremos['tensao_normal'].valor)} MPa",
        border=True,
        help="Axial + flexão, na fibra mais solicitada.",
    )
    segunda[3].metric(
        "von Mises máximo",
        f"{numero(extremos['von_mises'].valor)} MPa",
        border=True,
        help=f"Em x = {extremos['von_mises'].x_mm / 1_000.0:.3f} m.",
    )

    if resultado.fator_carga_critica is not None:
        colunas_estabilidade = st.columns(2)
        colunas_estabilidade[0].metric(
            "Fator de carga crítica",
            f"{resultado.fator_carga_critica:.2f}",
            border=True,
            help=(
                "Multiplicador das cargas **axiais** que levaria o modelo à "
                "flambagem elástica. Um fator 3,2 significa que a compressão "
                "poderia triplicar antes da instabilidade."
            ),
        )
        colunas_estabilidade[1].metric(
            "Efeito P–Δ",
            "Incluído" if resultado.segunda_ordem else "Não incluído",
            border=True,
            help=(
                "Escreva `segunda_ordem` no modelo para a compressão amplificar "
                "a flecha e o momento."
            ),
        )

    terceira = st.columns(3)
    terceira[0].metric(
        "τ de cisalhamento (V)",
        f"{numero(extremos['tensao_cisalhamento'].valor)} MPa",
        border=True,
    )
    terceira[1].metric(
        "τ de torção (T)",
        f"{numero(extremos['tensao_torcao'].valor)} MPa",
        border=True,
    )
    terceira[2].metric(
        "Tresca máximo",
        f"{numero(extremos['tresca'].valor)} MPa",
        border=True,
    )

    if material.escoamento_MPa and resultado.fator_seguranca_escoamento is not None:
        fator = resultado.fator_seguranca_escoamento
        mensagem = (
            f"Fator de segurança ao escoamento (von Mises, Sy = {material.escoamento_MPa:g} MPa): "
            f"**{'∞' if math.isinf(fator) else f'{fator:.2f}'}** "
            f"para a meta n ≥ {meta_fator_seguranca:.2f} dos critérios do projeto."
        )
        if fator < 1.0:
            st.error(mensagem + " A tensão equivalente excede o escoamento.", icon=":material/error:")
        elif fator < meta_fator_seguranca:
            st.warning(
                mensagem + " Abaixo da meta — margem pequena frente às incertezas do modelo.",
                icon=":material/warning:",
            )
        else:
            st.success(mensagem, icon=":material/check_circle:")


# ---------------------------------------------------------------------------
# 5. Diagramas
# ---------------------------------------------------------------------------

tabela = pd.DataFrame(vigas.tabela_diagramas(resultado))
tabela["ordem"] = range(len(tabela))


def diagrama(coluna: str, titulo: str, cor: str, *, inverter: bool = False, altura: int = 210):
    base = alt.Chart(tabela).encode(
        x=alt.X("x (m):Q", title="x (m)", scale=alt.Scale(nice=False, domainMin=0)),
        order=alt.Order("ordem:Q"),
    )
    escala = alt.Scale(zero=True, reverse=inverter)
    eixo_y = alt.Y(f"{coluna}:Q", title=titulo, scale=escala)
    area = base.mark_area(opacity=0.22, color=cor).encode(y=eixo_y)
    linha = base.mark_line(color=cor, strokeWidth=2).encode(y=eixo_y)
    zero = (
        alt.Chart(pd.DataFrame({"zero": [0.0]}))
        .mark_rule(color="#94a3b8", strokeDash=[4, 4])
        .encode(y=alt.Y("zero:Q", scale=escala))
    )
    tooltip = base.mark_rule(opacity=0).encode(
        y=eixo_y,
        tooltip=[
            alt.Tooltip("x (m):Q", format=".4f"),
            alt.Tooltip(f"{coluna}:Q", format=".4f"),
        ],
    )
    return (area + linha + zero + tooltip).properties(height=altura).interactive()


with st.container(border=True):
    st.subheader("5. Diagramas")
    inverter_momento = st.checkbox(
        "Desenhar o momento fletor do lado tracionado (convenção de estruturas)",
        value=False,
        key="vigas_inverter_momento",
        persist_state="session",
        help=(
            "Desmarcado: momento positivo para cima (convenção de mecânica). "
            "Marcado: eixo invertido, com o diagrama do lado da fibra tracionada."
        ),
    )

    nomes_abas = [
        "Cortante e momento",
        "Linha elástica",
        "Normal e torção",
        "Tensões",
        "Tabela",
    ]
    if envoltoria is not None:
        nomes_abas.insert(0, "Envoltória")
    abas_lista = st.tabs(nomes_abas)
    abas = abas_lista[1:] if envoltoria is not None else abas_lista

    if envoltoria is not None:
        with abas_lista[0]:
            st.markdown(
                "**Cada combinação foi resolvida separadamente.** A envoltória "
                "mostra a faixa que as cargas podem produzir em cada seção; a "
                "tabela abaixo diz qual combinação governa cada grandeza — que "
                "raramente é a mesma para todas."
            )
            resumo = pd.DataFrame(vigas.resumo_governantes(envoltoria))
            st.dataframe(
                resumo.style.format({"Valor": "{:.3f}", "x (m)": "{:.3f}"}),
                hide_index=True,
                width="stretch",
            )

            fatores_linhas = []
            for combinacao in envoltoria.combinacoes:
                linha = {"Combinação": combinacao.nome}
                for caso in vigas.casos_declarados(modelo):
                    linha[caso] = combinacao.fator(caso)
                fatores_linhas.append(linha)
            st.caption(
                "Fatores aplicados — um caso com fator zero não participa "
                "daquela combinação."
            )
            st.dataframe(pd.DataFrame(fatores_linhas), hide_index=True, width="stretch")

            tabela_env = pd.DataFrame(vigas.tabela_envoltoria(envoltoria))
            tabela_env["ordem"] = range(len(tabela_env))

            def faixa(coluna_max: str, coluna_min: str, titulo: str, cor: str):
                base = alt.Chart(tabela_env).encode(
                    x=alt.X("x (m):Q", title="x (m)", scale=alt.Scale(nice=False, domainMin=0)),
                    order=alt.Order("ordem:Q"),
                )
                area = base.mark_area(opacity=0.25, color=cor).encode(
                    y=alt.Y(f"{coluna_max}:Q", title=titulo),
                    y2=alt.Y2(f"{coluna_min}:Q"),
                )
                linha_max = base.mark_line(color=cor, strokeWidth=2).encode(
                    y=alt.Y(f"{coluna_max}:Q")
                )
                linha_min = base.mark_line(color=cor, strokeWidth=2, strokeDash=[4, 3]).encode(
                    y=alt.Y(f"{coluna_min}:Q")
                )
                zero = (
                    alt.Chart(pd.DataFrame({"zero": [0.0]}))
                    .mark_rule(color="#94a3b8", strokeDash=[4, 4])
                    .encode(y=alt.Y("zero:Q"))
                )
                return (area + linha_max + linha_min + zero).properties(height=220).interactive()

            st.altair_chart(
                faixa("V máx (kN)", "V mín (kN)", "Envoltória de cortante (kN)", CORES["cortante"])
            )
            st.altair_chart(
                faixa("M máx (kN·m)", "M mín (kN·m)", "Envoltória de momento (kN·m)", CORES["momento"])
            )
            st.altair_chart(
                faixa("Flecha máx (mm)", "Flecha mín (mm)", "Envoltória de flecha (mm)", CORES["flecha"])
            )
            st.caption(
                "Linha cheia: máximo; tracejada: mínimo. As demais abas mostram "
                "a barra **sem** fatores de combinação, como escrita no modelo."
            )
            st.download_button(
                "Baixar envoltória em CSV",
                data=tabela_env.drop(columns=["ordem"]).to_csv(index=False).encode("utf-8-sig"),
                file_name=f"envoltoria_{modelo.nome.replace(' ', '_').lower()}.csv",
                mime="text/csv",
                icon=":material/download:",
                width="stretch",
                key="vigas_baixar_envoltoria",
            )

    with abas[0]:
        st.altair_chart(diagrama("V (kN)", "Cortante V (kN)", CORES["cortante"], altura=230))
        st.altair_chart(
            diagrama(
                "M (kN·m)",
                "Momento fletor M (kN·m)",
                CORES["momento"],
                inverter=inverter_momento,
                altura=230,
            )
        )
        st.latex(r"\frac{dV}{dx}=w(x),\qquad \frac{dM}{dx}=V(x)")
        st.caption(
            "M positivo comprime a fibra superior. O diagrama salta nos pontos "
            "de carga concentrada (V) e de momento aplicado (M) — os dois valores "
            "de cada salto aparecem na aba **Tabela**."
        )

    with abas[1]:
        st.altair_chart(
            diagrama("Flecha (mm)", "Flecha v (mm) — linha elástica", CORES["flecha"], altura=260)
        )
        st.altair_chart(
            diagrama("Rotação (mrad)", "Rotação θ (mrad)", "#9333ea", altura=200)
        )
        st.latex(r"E\,I\,\frac{d^2 v}{dx^2}=M(x),\qquad \theta=\frac{dv}{dx}")
        st.caption(
            "Flecha negativa é deslocamento para baixo. A curva é a integração "
            "analítica de M(x)/EI em cada trecho, com as constantes vindas dos "
            "deslocamentos nodais — não é uma interpolação do gráfico."
        )
        # Guardado numa variável de módulo para o registro da seção 6 poder
        # gravar o critério: sem ele, a Central de Validação não tem como
        # verificar o estado limite de serviço desta barra.
        verificacao = vigas.verificar_flecha(
            resultado,
            limite_vao=float(
                st.number_input(
                    "Critério de flecha admissível: L / …",
                    min_value=50.0,
                    max_value=2_000.0,
                    value=350.0,
                    step=25.0,
                    key="vigas_limite_flecha",
                    persist_state="session",
                    help="L é a distância entre o primeiro e o último apoio.",
                )
            ),
        )
        colunas_flecha = st.columns(3)
        colunas_flecha[0].metric(
            # Em módulo: o critério de serviço compara magnitudes, enquanto o
            # painel de extremos acima mostra o sinal (negativo = para baixo).
            "Flecha máxima (módulo)",
            f"{numero(verificacao['flecha_mm'], 3)} mm",
            border=True,
        )
        colunas_flecha[1].metric(
            f"Admissível ({verificacao['criterio']})",
            f"{numero(verificacao['flecha_admissivel_mm'], 3)} mm",
            border=True,
            help=f"Vão considerado: {verificacao['vao_mm'] / 1_000.0:.3f} m.",
        )
        colunas_flecha[2].metric(
            "Utilização", f"{verificacao['utilizacao'] * 100:.0f}%", border=True
        )
        if verificacao["atende"]:
            st.success("A flecha atende ao critério informado.", icon=":material/check_circle:")
        else:
            st.warning(
                "A flecha excede o critério informado — aumente a inércia, reduza "
                "o vão ou reveja o critério.",
                icon=":material/warning:",
            )

    with abas[2]:
        st.altair_chart(diagrama("N (kN)", "Esforço normal N (kN)", CORES["normal"], altura=200))
        st.altair_chart(diagrama("T (kN·m)", "Torque T (kN·m)", CORES["torque"], altura=200))
        st.altair_chart(diagrama("Giro torção (°)", "Ângulo de torção φ (°)", "#c2410c", altura=200))
        st.latex(r"\sigma_{axial}=\frac{N}{A},\qquad \tau_{t}=\frac{T}{W_t},\qquad \varphi=\int\frac{T}{G\,J}\,dx")
        st.caption(
            "N positivo traciona. Em seções não circulares a tensão de torção usa "
            "o módulo de torção Wt (não T·c/J), e o empenamento não é considerado."
        )

    with abas[3]:
        st.altair_chart(
            diagrama("σ sup (MPa)", "Tensão normal na fibra superior (MPa)", CORES["tensao"], altura=200)
        )
        st.altair_chart(
            diagrama("σ inf (MPa)", "Tensão normal na fibra inferior (MPa)", "#0e7490", altura=200)
        )
        st.altair_chart(
            diagrama("von Mises (MPa)", "Tensão equivalente de von Mises (MPa)", "#be123c", altura=210)
        )
        st.latex(
            r"\sigma=\frac{N}{A}\pm\frac{M\,c}{I},\qquad "
            r"\tau=\frac{V\,Q}{I\,t}+\frac{T}{W_t},\qquad "
            r"\sigma_{VM}=\sqrt{\sigma^2+3\tau^2}"
        )
        st.caption(
            "von Mises é avaliado em três pontos de cada seção — fibra superior, "
            "fibra inferior e linha neutra — e o gráfico mostra o pior deles. "
            "É por isso que flexão e torção **não** somam no mesmo ponto: onde a "
            "flexão é máxima, o cisalhamento de V é nulo."
        )
        critico = max(resultado.pontos, key=lambda ponto: ponto.von_mises_MPa)
        sigma_critico, tau_critico = vigas.estado_no_ponto_critico(critico)
        st.info(
            f"Seção mais solicitada: x = {critico.x_mm / 1_000.0:.3f} m, no ponto "
            f"**{critico.ponto_critico.lower()}** — σ = {sigma_critico:.2f} MPa e "
            f"τ = {tau_critico:.2f} MPa, resultando em "
            f"σ_VM = {critico.von_mises_MPa:.2f} MPa.",
            icon=":material/target:",
        )

    with abas[4]:
        st.dataframe(
            tabela.drop(columns=["ordem"]),
            hide_index=True,
            width="stretch",
            height=420,
        )
        st.download_button(
            "Baixar diagramas em CSV",
            data=tabela.drop(columns=["ordem"]).to_csv(index=False).encode("utf-8-sig"),
            file_name=f"diagramas_{modelo.nome.replace(' ', '_').lower()}.csv",
            mime="text/csv",
            icon=":material/download:",
            width="stretch",
            key="vigas_baixar_csv",
        )


fronteira_modelo(
    [
        "Efeitos de segunda ordem só entram se você escrever `segunda_ordem` no modelo; sem isso a compressão não amplifica a flecha.",
        "Imperfeições geométricas iniciais e desaprumo — a segunda ordem parte da barra perfeitamente reta.",
        "Flambagem global, local ou lateral com torção — verifique em Flambagem de colunas e Estruturas de aço.",
        "Deformação por cisalhamento (viga de Timoshenko): em vigas curtas (L/h < 10) a flecha real é maior.",
        "Empenamento restringido na torção — só a torção uniforme de Saint-Venant é considerada.",
        "Concentração de tensão em furos, entalhes, mudanças de seção e rasgos de chaveta.",
        "Fadiga, fluência, impacto e temperatura — use o repasse abaixo para levar a seção ao módulo próprio.",
        "Ligações e apoios reais: o modelo trata engaste, pino e rolete como ideais.",
        "Os fatores de combinação são os que você declarar: o programa não atribui coeficiente normativo automaticamente.",
    ]
)


# ---------------------------------------------------------------------------
# 6. Registro e comparação
# ---------------------------------------------------------------------------

with st.container(border=True):
    st.subheader("6. Registrar no projeto")

    if material.escoamento_MPa and resultado.fator_seguranca_escoamento is not None:
        fator = resultado.fator_seguranca_escoamento
        status = (
            "Atende"
            if fator >= meta_fator_seguranca
            else "Atenção"
            if fator >= 1.0
            else "Não atende"
        )
    else:
        status = "Calculado"
        fator = None

    st.markdown("**Comparar cenários**")
    comparador_cenarios(
        escopo="vigas_eixos",
        resumo_entradas={
            "Seção": secao.nome,
            "L (m)": round(comprimento_m, 3),
            "Apoios": len(resultado.reacoes),
        },
        metricas={
            "V máx (kN)": f"{extremos['cortante'].valor / 1_000.0:.2f}",
            "M máx (kN·m)": f"{extremos['momento'].valor / 1e6:.2f}",
            "Flecha (mm)": f"{extremos['flecha'].valor:.3f}",
            "von Mises (MPa)": f"{extremos['von_mises'].valor:.1f}",
            "FS": "—" if fator is None else ("∞" if math.isinf(fator) else f"{fator:.2f}"),
        },
    )

    conclusao = (
        f"V máx = {extremos['cortante'].valor / 1_000.0:.2f} kN; "
        f"M máx = {extremos['momento'].valor / 1e6:.2f} kN·m em x = {extremos['momento'].x_mm / 1_000.0:.3f} m; "
        f"flecha máx = {extremos['flecha'].valor:.3f} mm em x = {extremos['flecha'].x_mm / 1_000.0:.3f} m; "
        f"σ_VM máx = {extremos['von_mises'].valor:.1f} MPa."
    )

    registro = construir_registro_tecnico(
        modulo="Vigas e eixos",
        modulo_id="vigas_eixos",
        titulo=f"{modelo.nome} — {secao.nome} ({comprimento_m:g} m)",
        status=status,
        resumo=(
            "Análise linear de barra reta com cortante, momento fletor, linha "
            "elástica, esforço normal e torção combinados."
            + (
                ""
                if envoltoria is None
                else f" Envoltória de {len(envoltoria.combinacoes)} combinação(ões) "
                "de carga, com a combinação governante de cada grandeza."
            )
        ),
        entradas={
            "script_modelo": guardado["script"],
            "comprimento_mm": modelo.comprimento_mm,
            "secao": {
                "nome": secao.nome,
                "descricao": secao.descricao,
                "area_mm2": secao.area_mm2,
                "inercia_mm4": secao.inercia_mm4,
                "c_superior_mm": secao.c_superior_mm,
                "c_inferior_mm": secao.c_inferior_mm,
                "constante_torcao_mm4": secao.constante_torcao_mm4,
                "modulo_torcao_mm3": secao.modulo_torcao_mm3,
            },
            "material": {
                "nome": material.nome,
                "modulo_elasticidade_MPa": material.modulo_elasticidade_MPa,
                "modulo_cisalhamento_MPa": material.modulo_cisalhamento_MPa,
                "escoamento_MPa": material.escoamento_MPa,
                "densidade_kg_m3": material.densidade_kg_m3,
                "fonte": material.fonte,
            },
            "apoios": [
                {"x_mm": apoio.x_mm, "tipo": apoio.tipo} for apoio in modelo.apoios
            ],
            "rotulas_mm": [rotula.x_mm for rotula in modelo.rotulas],
            "numero_cargas": (
                len(modelo.cargas_pontuais)
                + len(modelo.momentos)
                + len(modelo.cargas_distribuidas)
                + len(modelo.cargas_axiais)
                + len(modelo.cargas_axiais_distribuidas)
                + len(modelo.torques)
            ),
        },
        resultados={
            "reacoes": vigas.resumo_reacoes(resultado),
            "cortante_maximo_kN": extremos["cortante"].valor / 1_000.0,
            "cortante_maximo_x_m": extremos["cortante"].x_mm / 1_000.0,
            "momento_maximo_kNm": extremos["momento"].valor / 1e6,
            "momento_maximo_x_m": extremos["momento"].x_mm / 1_000.0,
            "normal_maximo_kN": extremos["normal"].valor / 1_000.0,
            "torque_maximo_kNm": extremos["torque"].valor / 1e6,
            "flecha_maxima_mm": extremos["flecha"].valor,
            "flecha_maxima_x_m": extremos["flecha"].x_mm / 1_000.0,
            "rotacao_maxima_rad": extremos["rotacao"].valor,
            "giro_torcao_maximo_rad": extremos["giro_torcao"].valor,
            "tensao_normal_extrema_MPa": extremos["tensao_normal"].valor,
            "tensao_cisalhamento_maxima_MPa": extremos["tensao_cisalhamento"].valor,
            "tensao_torcao_maxima_MPa": extremos["tensao_torcao"].valor,
            "von_mises_maximo_MPa": extremos["von_mises"].valor,
            "tresca_maximo_MPa": extremos["tresca"].valor,
            "fator_seguranca_escoamento": (
                None if fator is None or math.isinf(fator) else fator
            ),
            # O memorial usa esta meta para concluir "atende / não atende".
            "fator_seguranca_minimo": meta_fator_seguranca,
            "flecha_admissivel_mm": verificacao["flecha_admissivel_mm"],
            "criterio_flecha": verificacao["criterio"],
            "utilizacao_flecha": verificacao["utilizacao"],
            "grau_hiperestaticidade": resultado.grau_hiperestaticidade,
            "fator_carga_critica": resultado.fator_carga_critica,
            "segunda_ordem": resultado.segunda_ordem,
            **(
                {}
                if envoltoria is None
                else {
                    "envoltoria_combinacoes": [
                        {"nome": item.nome, "fatores": item.fatores}
                        for item in envoltoria.combinacoes
                    ],
                    "envoltoria_governantes": vigas.resumo_governantes(envoltoria),
                }
            ),
            "residuos_equilibrio": vigas.conferir_equilibrio(resultado),
        },
        metodo=(
            "Rigidez direta com elementos de Euler-Bernoulli (nós em toda "
            "descontinuidade de carga e apoio), esforço axial e torção de "
            "Saint-Venant desacoplados. Dentro de cada elemento V(x), M(x), "
            "θ(x) e v(x) vêm de integração analítica dos polinômios exatos; as "
            "rótulas internas são tratadas por duplicação do grau de liberdade "
            "de rotação."
        ),
        equacoes=[
            "dV/dx = w(x); dM/dx = V(x)",
            "E·I·v'' = M(x)",
            "σ = N/A ± M·c/I",
            "τ = V·Q/(I·t) + T/Wt",
            "σ_VM = √(σ² + 3τ²)",
        ],
        premissas=[
            "Análise linear elástica, pequenas deformações e seção constante ao longo da barra.",
            "Flexão em um único plano, em torno do eixo principal informado na seção.",
            "Apoios e engastes idealizados; rótulas internas transmitem V e N, mas não M.",
            "Torção uniforme de Saint-Venant, sem restrição ao empenamento.",
        ],
        alertas=(
            []
            if status in {"Atende", "Calculado"}
            else [f"Fator de segurança ao escoamento igual a {fator:.2f}."]
        )
        + list(resultado.avisos),
        referencias=[
            "Hibbeler — Resistência dos Materiais (diagramas V/M, linha elástica, cargas combinadas).",
            "Shigley — Mechanical Engineering Design (eixos sob flexão e torção).",
            "Confirmar critério de flecha admissível e condições reais de apoio do projeto.",
        ],
        conclusao=conclusao,
        materiais_ids=[material.material_id] if material.material_id else [],
    )
    botao_registrar_calculo(
        registro,
        key="registrar_vigas_eixos",
        rotulo="Registrar análise da barra no projeto ativo",
    )


# ---------------------------------------------------------------------------
# 7. Levar a seção adiante
# ---------------------------------------------------------------------------

with st.container(border=True):
    st.subheader("7. Levar uma seção para o próximo módulo")
    st.caption(
        "A barra resolvida já contém σ e τ de cada seção. Em vez de anotar e "
        "redigitar esses números, escolha a seção e mande direto — o módulo de "
        "destino abre com os valores preenchidos e com o vínculo de origem."
    )

    notaveis = vigas.secoes_notaveis(resultado)
    escolha_secao = st.selectbox(
        "Seção a levar adiante",
        [*notaveis, "Posição escolhida"],
        key="vigas_secao_repasse",
        persist_state="session",
    )
    if escolha_secao == "Posição escolhida":
        x_repasse_m = st.number_input(
            "Posição x (m)",
            min_value=0.0,
            max_value=float(comprimento_m),
            value=float(extremos["von_mises"].x_mm / 1_000.0),
            step=0.05,
            key="vigas_x_repasse",
            persist_state="session",
        )
        x_repasse_mm = x_repasse_m * 1_000.0
    else:
        x_repasse_mm = notaveis[escolha_secao]
        st.caption(f"Posição correspondente: x = {x_repasse_mm / 1_000.0:.3f} m.")

    diagrama_secao = vigas.ponto_em(resultado, x_repasse_mm)
    estado_secao = vigas.estado_plano_da_secao(resultado, x_repasse_mm)

    esforcos_colunas = st.columns(4)
    esforcos_colunas[0].metric(
        "N na seção", f"{numero(diagrama_secao.normal_N / 1_000.0)} kN", border=True
    )
    esforcos_colunas[1].metric(
        "V na seção", f"{numero(diagrama_secao.cortante_N / 1_000.0)} kN", border=True
    )
    esforcos_colunas[2].metric(
        "M na seção", f"{numero(diagrama_secao.momento_Nmm / 1e6)} kN·m", border=True
    )
    esforcos_colunas[3].metric(
        "T na seção", f"{numero(diagrama_secao.torque_Nmm / 1e6, 3)} kN·m", border=True
    )

    tensoes_colunas = st.columns(3)
    tensoes_colunas[0].metric(
        "σx a repassar",
        f"{numero(estado_secao.sigma_x)} MPa",
        border=True,
        help=f"Ponto governante: {diagrama_secao.ponto_critico.lower()}.",
    )
    tensoes_colunas[1].metric(
        "τxy a repassar", f"{numero(estado_secao.tau_xy)} MPa", border=True
    )
    tensoes_colunas[2].metric(
        "von Mises na seção", f"{numero(diagrama_secao.von_mises_MPa)} MPa", border=True
    )

    origem_id = id_registro_existente(registro)
    if origem_id is None:
        st.caption(
            ":material/link_off: Esta análise ainda não foi registrada no projeto — "
            "o repasse leva os valores, mas não uma origem rastreável. Registre "
            "acima para que o próximo módulo saiba de onde eles vieram."
        )

    destino_mohr, destino_estatica = st.columns(2)
    with destino_mohr:
        if st.button(
            "Enviar para o Círculo de Mohr",
            type="primary",
            icon=":material/donut_large:",
            width="stretch",
            key="vigas_enviar_mohr",
        ):
            enviar_para_mohr(estado_secao, origem_id=origem_id)
    with destino_estatica:
        if st.button(
            "Enviar para a Análise estática",
            type="secondary",
            icon=":material/analytics:",
            width="stretch",
            key="vigas_enviar_estatica",
        ):
            enviar_para_estatica(estado_secao, origem_id=origem_id)

    st.divider()
    st.markdown("**Fadiga — só faz sentido se a barra girar ou a carga variar**")
    eixo_girante = st.checkbox(
        "A barra gira sob este momento (eixo de transmissão)",
        value=bool(modelo.torques),
        key="vigas_eixo_girante",
        persist_state="session",
        help=(
            "Num eixo girando, cada fibra passa por tração e compressão a cada "
            "volta: a flexão vira tensão totalmente alternada. Numa viga fixa o "
            "mesmo momento é estático e não gera ciclo."
        ),
    )
    amplitudes = vigas.amplitudes_de_fadiga(
        resultado, x_repasse_mm, eixo_girante=eixo_girante
    )
    colunas_fadiga = st.columns(3)
    colunas_fadiga[0].metric(
        "σa (alternada)", f"{numero(amplitudes['sigma_alternada_MPa'])} MPa", border=True
    )
    colunas_fadiga[1].metric(
        "σm (média)", f"{numero(amplitudes['sigma_media_MPa'])} MPa", border=True
    )
    colunas_fadiga[2].metric(
        "τ de torção", f"{numero(amplitudes['tensao_torcao_MPa'])} MPa", border=True,
        help="A torção estática entra na fadiga como tensão média de cisalhamento; leve-a em conta no módulo de destino.",
    )
    if amplitudes["sigma_alternada_MPa"] <= 0:
        st.caption(
            ":material/info: Sem parcela alternada nesta seção — a verificação "
            "de fadiga só faz sentido se a carga variar no tempo. Marque a opção "
            "acima se a barra girar, ou defina o ciclo direto no módulo de fadiga."
        )
    if st.button(
        "Enviar para a Análise de fadiga",
        type="secondary",
        icon=":material/cycle:",
        width="stretch",
        disabled=amplitudes["sigma_alternada_MPa"] <= 0,
        key="vigas_enviar_fadiga",
    ):
        enviar_para_fadiga(amplitudes)


with st.container(border=True):
    st.subheader("Precisa de ajuda para montar o modelo?")
    st.markdown(
        "O **Guia geral** traz a tabela de comandos, a leitura de cada diagrama "
        "e um exemplo completo resolvido passo a passo."
    )
    st.page_link(
        "app_pages/guia_geral.py",
        label="Abrir o guia de vigas e eixos",
        icon=":material/help:",
        query_params={"modulo": "Vigas e eixos"},
        width="stretch",
    )

st.caption(
    "Modelo linear de Euler-Bernoulli. Para dimensionamento normativo de perfis "
    "de aço use Estruturas de aço; para verificação de fadiga leve os esforços "
    "desta página ao módulo de fadiga."
)
