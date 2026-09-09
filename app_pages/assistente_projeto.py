import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))

from components import load_models as catalogo
from components.project_tools import contexto_sessao_projeto
from components.ui import cabecalho_pagina
from core import project_assistant as projetos
from core import unit_converter as unidades
from core.project_store import criar_item, criar_projeto, salvar_projeto


st.set_page_config(
    page_title="Assistente de projeto",
    page_icon=":material/route:",
    layout="wide",
)

st.session_state.setdefault("projeto_assistente_etapa", 1)
st.session_state.setdefault("projeto_ativo", None)

ITENS_CHECKLIST = [
    "Diagrama de corpo livre",
    "Geometria e ponto crítico",
    "Material confirmado",
    "Casos de carga",
    "Fator ou critério de projeto",
    "Norma aplicável",
]


def definir_etapa(etapa: int) -> None:
    st.session_state["projeto_assistente_etapa"] = max(1, min(4, etapa))


def reiniciar_roteiro() -> None:
    for chave in list(st.session_state):
        if chave.startswith("projeto_") and chave != "projeto_ativo":
            del st.session_state[chave]
    st.session_state["projeto_assistente_etapa"] = 1


def valor_convertido(chave: str, categoria: str, destino: str) -> float:
    valor = float(st.session_state.get(f"{chave}_valor", 0.0))
    origem = st.session_state.get(f"{chave}_unidade", destino)
    return unidades.converter(valor, categoria, origem, destino)


def coletar_entradas(
    rota: projetos.RotaProjeto,
) -> tuple[dict[str, object], dict[str, object]]:
    """Converte as entradas do roteiro sem alterar o módulo de destino."""
    if rota.chave in {"estatica", "mohr"}:
        origem = st.session_state.get("projeto_tensao_unidade", "MPa")
        valores = {
            "sigma_x": unidades.converter(
                st.session_state.get("projeto_sigma_x", 0.0),
                "Tensão e pressão",
                origem,
                "MPa",
            ),
            "sigma_y": unidades.converter(
                st.session_state.get("projeto_sigma_y", 0.0),
                "Tensão e pressão",
                origem,
                "MPa",
            ),
            "tau_xy": unidades.converter(
                st.session_state.get("projeto_tau_xy", 0.0),
                "Tensão e pressão",
                origem,
                "MPa",
            ),
        }
        resumo = {
            "σx (MPa)": valores["sigma_x"],
            "σy (MPa)": valores["sigma_y"],
            "τxy (MPa)": valores["tau_xy"],
        }
        return valores, resumo

    if rota.chave == "fadiga":
        origem = st.session_state.get("projeto_ciclo_unidade", "MPa")
        minima = unidades.converter(
            st.session_state.get("projeto_sigma_min", 0.0),
            "Tensão e pressão",
            origem,
            "MPa",
        )
        maxima = unidades.converter(
            st.session_state.get("projeto_sigma_max", 0.0),
            "Tensão e pressão",
            origem,
            "MPa",
        )
        media, alternada = projetos.calcular_tensoes_ciclo(minima, maxima)
        media_aplicada = max(0.0, media)
        valores = {
            "minima": minima,
            "maxima": maxima,
            "media": media,
            "media_aplicada": media_aplicada,
            "alternada": alternada,
        }
        resumo = {
            "σmín (MPa)": minima,
            "σmáx (MPa)": maxima,
            "σm calculada (MPa)": media,
            "σm aplicada (MPa)": media_aplicada,
            "σa (MPa)": alternada,
        }
        return valores, resumo

    if rota.chave == "parafusos":
        forca_origem = st.session_state.get(
            "projeto_parafuso_forca_unidade", "kN"
        )
        momento_origem = st.session_state.get(
            "projeto_parafuso_momento_unidade", "N·m"
        )
        valores = {
            "rosca": st.session_state.get("projeto_parafuso_rosca", "M10"),
            "numero": int(st.session_state.get("projeto_parafuso_numero", 4)),
            "axial": unidades.converter(
                st.session_state.get("projeto_parafuso_axial", 0.0),
                "Força",
                forca_origem,
                "kN",
            ),
            "cortante": unidades.converter(
                st.session_state.get("projeto_parafuso_cortante", 0.0),
                "Força",
                forca_origem,
                "kN",
            ),
            "momento": unidades.converter(
                st.session_state.get("projeto_parafuso_momento", 0.0),
                "Momento e torque",
                momento_origem,
                "N·m",
            ),
            "torque": unidades.converter(
                st.session_state.get("projeto_parafuso_torque", 0.0),
                "Momento e torque",
                momento_origem,
                "N·m",
            ),
        }
        resumo = {
            "Rosca": valores["rosca"],
            "Número de parafusos": valores["numero"],
            "P (kN)": valores["axial"],
            "V (kN)": valores["cortante"],
            "M (N·m)": valores["momento"],
            "T (N·m)": valores["torque"],
        }
        return valores, resumo

    if rota.chave == "aco":
        forca_origem = st.session_state.get("projeto_aco_forca_unidade", "kN")
        momento_origem = st.session_state.get(
            "projeto_aco_momento_unidade", "kN·m"
        )
        valores = {
            "nd": abs(
                unidades.converter(
                    st.session_state.get("projeto_aco_axial", 0.0),
                    "Força",
                    forca_origem,
                    "kN",
                )
            ),
            "vd": abs(
                unidades.converter(
                    st.session_state.get("projeto_aco_cortante", 0.0),
                    "Força",
                    forca_origem,
                    "kN",
                )
            ),
            "momento": abs(
                unidades.converter(
                    st.session_state.get("projeto_aco_momento", 0.0),
                    "Momento e torque",
                    momento_origem,
                    "kN·m",
                )
            ),
            "comprimento": valor_convertido(
                "projeto_aco_comprimento", "Comprimento", "m"
            ),
        }
        resumo = {
            "|Nd| (kN)": valores["nd"],
            "|Vd| (kN)": valores["vd"],
            "|Mdx| (kN·m)": valores["momento"],
            "L (m)": valores["comprimento"],
        }
        return valores, resumo

    modelo = catalogo.resolver_chave(
        st.session_state.get("projeto_modelo_carga")
    )
    return {"modelo": modelo}, {"Modelo inicial": modelo}


def formatar_valor_resumo(valor: object) -> str:
    if isinstance(valor, float):
        return f"{valor:,.4f}".rstrip("0").rstrip(".").replace(
            ",", "X"
        ).replace(".", ",").replace("X", ".")
    return str(valor)


def preparar_modulo(rota: projetos.RotaProjeto) -> None:
    nome = st.session_state.get("projeto_nome", "").strip()
    if not nome:
        raise ValueError("Informe um nome para o projeto antes de continuar.")

    valores, resumo = coletar_entradas(rota)

    if rota.chave == "estatica":
        st.session_state["estatica_sigma_x"] = valores["sigma_x"]
        st.session_state["estatica_sigma_y"] = valores["sigma_y"]
        st.session_state["estatica_tau_xy"] = valores["tau_xy"]

    elif rota.chave == "mohr":
        st.session_state["mohr_assistente_2d"] = {
            "sigma_x": valores["sigma_x"],
            "sigma_y": valores["sigma_y"],
            "tau_xy": valores["tau_xy"],
            "descricao": f"projeto guiado — {nome}",
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

    elif rota.chave == "fadiga":
        st.session_state["fadiga_sigma_alternada_nominal"] = valores["alternada"]
        st.session_state["fadiga_sigma_media"] = valores["media_aplicada"]

    elif rota.chave == "parafusos":
        st.session_state["parafuso_rosca"] = valores["rosca"]
        st.session_state["parafuso_numero"] = valores["numero"]
        st.session_state["parafuso_carga_axial"] = valores["axial"]
        st.session_state["parafuso_carga_cortante"] = valores["cortante"]
        st.session_state["parafuso_momento"] = valores["momento"]
        st.session_state["parafuso_torque_grupo"] = valores["torque"]

    elif rota.chave == "aco":
        st.session_state["estrutura_aco_modulo"] = "2. Barras"
        st.session_state["estrutura_nd_kN"] = valores["nd"]
        st.session_state["estrutura_mdx_kNm"] = valores["momento"]
        st.session_state["estrutura_vd_kN"] = valores["vd"]
        st.session_state["estrutura_comprimento_m"] = valores["comprimento"]

    else:
        st.session_state["assistente_geometria"] = valores["modelo"]

    conferidos = list(st.session_state.get("projeto_verificacoes", []))
    sequencia = projetos.sequencia_recomendada(
        st.session_state.get("projeto_objetivo", projetos.OBJETIVOS[0]),
        st.session_state.get("projeto_dados", projetos.DADOS_DISPONIVEIS[0]),
        st.session_state.get("projeto_componente"),
    )
    permanente = criar_projeto(
        nome,
        descricao=st.session_state.get("projeto_descricao", "").strip(),
        tag_equipamento=st.session_state.get("projeto_componente", ""),
    )
    permanente["objetivo"] = st.session_state.get("projeto_objetivo", "")
    permanente["regime_operacao"] = st.session_state.get("projeto_regime", "")
    permanente["processo"] = st.session_state.get("projeto_dados", "")
    permanente["base_projeto"]["base_carregamentos"] = (
        f"Entradas iniciais transferidas pelo Assistente de projeto: {resumo}"
    )
    componente = st.session_state.get("projeto_componente", "")
    if componente:
        permanente["componentes"].append(
            criar_item(
                tag=componente,
                descricao=st.session_state.get("projeto_descricao", "") or componente,
                servico="Definido no roteiro inicial",
                material="",
                fonte_material="",
                desenho="",
                criticidade="",
            )
        )
    permanente["checklist"] = [
        criar_item(
            item=item,
            categoria="Roteiro inicial",
            responsavel="",
            prazo="",
            estado="Concluído" if item in conferidos else "Aberto",
            evidencia="Informado no Assistente de projeto" if item in conferidos else "",
            critico=item in {"Casos de carga", "Norma aplicável"},
        )
        for item in ITENS_CHECKLIST
    ]
    permanente = salvar_projeto(
        permanente,
        motivo=f"Roteiro inicial criado para {rota.titulo}",
    )
    contexto = contexto_sessao_projeto(permanente)
    contexto.update(
        {
            "componente": componente,
            "dados": st.session_state.get("projeto_dados", ""),
            "regime": st.session_state.get("projeto_regime", ""),
            "rota": rota.titulo,
            "pagina": rota.pagina,
            "sequencia": sequencia,
            "entradas": resumo,
            "verificacoes": conferidos,
            "pendencias": [item for item in ITENS_CHECKLIST if item not in conferidos],
        }
    )
    st.session_state["projeto_ativo"] = contexto
    st.switch_page(rota.pagina)

cabecalho_pagina(
    "Assistente de projeto",
    "Organize o problema, descubra o fluxo correto e leve os dados iniciais ao módulo.",
    categoria="Ferramentas",
    icone=":material/route:",
    cor="violet",
    ajuda_modulo="Assistente de projeto",
    acoes=(
        (
            "app_pages/conversor_unidades.py",
            "Conversor",
            ":material/swap_horiz:",
        ),
    ),
    mostrar_ferramentas=False,
)

if (
    st.session_state.get("projeto_ativo")
    or st.session_state["projeto_assistente_etapa"] > 1
):
    with st.container(horizontal=True, horizontal_alignment="right"):
        st.button(
            "Novo roteiro",
            icon=":material/restart_alt:",
            help="Limpa o roteiro atual e inicia outro projeto.",
            on_click=reiniciar_roteiro,
        )

etapa = int(st.session_state["projeto_assistente_etapa"])
nomes_etapas = ["Definição", "Objetivo", "Dados", "Plano"]
st.progress(etapa / 4, text=f"Etapa {etapa} de 4 — {nomes_etapas[etapa - 1]}")

with st.container(horizontal=True, horizontal_alignment="distribute"):
    for indice, nome_etapa in enumerate(nomes_etapas, start=1):
        cor = "green" if indice < etapa else "blue" if indice == etapa else "gray"
        icone = ":material/check:" if indice < etapa else ":material/circle:"
        st.badge(f"{indice}. {nome_etapa}", color=cor, icon=icone)

pode_continuar = True

if etapa == 1:
    with st.container(border=True):
        st.subheader("Defina o projeto")
        nome_projeto = st.text_input(
            "Nome do projeto",
            placeholder="Ex.: eixo do redutor, suporte da bomba, mezanino",
            key="projeto_nome",
            persist_state="session",
        )
        st.text_area(
            "Descrição curta",
            placeholder="O que a peça faz e em que condição trabalha?",
            key="projeto_descricao",
            persist_state="session",
        )
        st.selectbox(
            "Componente ou sistema",
            projetos.COMPONENTES,
            key="projeto_componente",
            persist_state="session",
        )
        if nome_projeto.strip():
            st.caption(
                "O nome identifica o projeto ativo nos demais módulos. Você "
                "poderá revisar o roteiro depois."
            )
        else:
            pode_continuar = False
            st.caption("Informe um nome para liberar a próxima etapa.")

elif etapa == 2:
    with st.container(border=True):
        st.subheader("Escolha o objetivo e o ponto de partida")
        st.selectbox(
            "O que você quer descobrir?",
            projetos.OBJETIVOS,
            key="projeto_objetivo",
            persist_state="session",
        )
        st.selectbox(
            "Quais dados você já possui?",
            projetos.DADOS_DISPONIVEIS,
            key="projeto_dados",
            persist_state="session",
        )
        st.segmented_control(
            "Regime de carregamento",
            ["Estático", "Variável/cíclico", "Ainda não sei"],
            default="Estático",
            required=True,
            width="stretch",
            key="projeto_regime",
            persist_state="session",
        )

        objetivo = st.session_state.get("projeto_objetivo", projetos.OBJETIVOS[0])
        dados = st.session_state.get(
            "projeto_dados", projetos.DADOS_DISPONIVEIS[0]
        )
        rota = projetos.recomendar_rota(
        objetivo, dados, st.session_state.get("projeto_componente")
    )
        st.info(
            f"Primeira rota sugerida: **{rota.titulo}**. "
            f"Entrada: {rota.entrada}; saída: {rota.saida}.",
            icon=rota.icone,
        )

elif etapa == 3:
    objetivo = st.session_state.get("projeto_objetivo", projetos.OBJETIVOS[0])
    dados = st.session_state.get(
        "projeto_dados", projetos.DADOS_DISPONIVEIS[0]
    )
    rota = projetos.recomendar_rota(
        objetivo, dados, st.session_state.get("projeto_componente")
    )

    with st.container(border=True):
        st.subheader(f"Dados iniciais para {rota.titulo.lower()}")
        st.caption(
            "Preencha o que já sabe. Esses campos não substituem a revisão "
            "completa das entradas no módulo de cálculo."
        )

        if rota.chave in {"estatica", "mohr"}:
            unidade_tensao = st.selectbox(
                "Unidade das tensões",
                ["MPa", "ksi", "psi", "kPa"],
                key="projeto_tensao_unidade",
                persist_state="session",
            )
            tensoes = st.columns(3)
            tensoes[0].number_input(
                f"σx ({unidade_tensao})",
                value=80.0,
                key="projeto_sigma_x",
                persist_state="session",
            )
            tensoes[1].number_input(
                f"σy ({unidade_tensao})",
                value=-20.0,
                key="projeto_sigma_y",
                persist_state="session",
            )
            tensoes[2].number_input(
                f"τxy ({unidade_tensao})",
                value=35.0,
                key="projeto_tau_xy",
                persist_state="session",
            )

        elif rota.chave == "fadiga":
            unidade_ciclo = st.selectbox(
                "Unidade das tensões do ciclo",
                ["MPa", "ksi", "psi", "kPa"],
                key="projeto_ciclo_unidade",
                persist_state="session",
            )
            ciclo = st.columns(2)
            minima = ciclo[0].number_input(
                f"Tensão mínima ({unidade_ciclo})",
                value=20.0,
                key="projeto_sigma_min",
                persist_state="session",
            )
            maxima = ciclo[1].number_input(
                f"Tensão máxima ({unidade_ciclo})",
                value=180.0,
                key="projeto_sigma_max",
                persist_state="session",
            )
            minima_mpa = unidades.converter(
                minima, "Tensão e pressão", unidade_ciclo, "MPa"
            )
            maxima_mpa = unidades.converter(
                maxima, "Tensão e pressão", unidade_ciclo, "MPa"
            )
            if maxima_mpa >= minima_mpa:
                media, alternada = projetos.calcular_tensoes_ciclo(
                    minima_mpa, maxima_mpa
                )
                with st.container(horizontal=True):
                    st.metric("σm calculada", f"{media:.2f} MPa", border=True)
                    st.metric("σa calculada", f"{alternada:.2f} MPa", border=True)
            else:
                pode_continuar = False
                st.error("A tensão máxima não pode ser menor que a mínima.")

        elif rota.chave == "parafusos":
            junta = st.columns(2)
            junta[0].selectbox(
                "Rosca inicial",
                ["M6", "M8", "M10", "M12", "M16", "M20", "M24", "M30", "M36"],
                index=2,
                key="projeto_parafuso_rosca",
                persist_state="session",
            )
            junta[1].number_input(
                "Número de parafusos",
                min_value=1,
                value=4,
                step=1,
                key="projeto_parafuso_numero",
                persist_state="session",
            )
            forca_unidade = st.selectbox(
                "Unidade das forças",
                ["kN", "N", "kgf", "lbf"],
                key="projeto_parafuso_forca_unidade",
                persist_state="session",
            )
            cargas = st.columns(2)
            cargas[0].number_input(
                f"Carga axial total ({forca_unidade})",
                value=40.0,
                key="projeto_parafuso_axial",
                persist_state="session",
            )
            cargas[1].number_input(
                f"Força cortante total ({forca_unidade})",
                value=20.0,
                key="projeto_parafuso_cortante",
                persist_state="session",
            )
            momento_unidade = st.selectbox(
                "Unidade de momentos e torques",
                ["N·m", "kN·m", "N·mm", "lbf·ft"],
                key="projeto_parafuso_momento_unidade",
                persist_state="session",
            )
            momentos = st.columns(2)
            momentos[0].number_input(
                f"Momento de tombamento ({momento_unidade})",
                value=0.0,
                key="projeto_parafuso_momento",
                persist_state="session",
            )
            momentos[1].number_input(
                f"Torque no grupo ({momento_unidade})",
                value=0.0,
                key="projeto_parafuso_torque",
                persist_state="session",
            )

        elif rota.chave == "aco":
            forca_unidade = st.selectbox(
                "Unidade dos esforços de força",
                ["kN", "N", "kgf", "kip"],
                key="projeto_aco_forca_unidade",
                persist_state="session",
            )
            esforcos = st.columns(2)
            esforcos[0].number_input(
                f"|Força axial| ({forca_unidade})",
                min_value=0.0,
                value=100.0,
                key="projeto_aco_axial",
                persist_state="session",
            )
            esforcos[1].number_input(
                f"|Força cortante| ({forca_unidade})",
                min_value=0.0,
                value=20.0,
                key="projeto_aco_cortante",
                persist_state="session",
            )
            momento_unidade = st.selectbox(
                "Unidade do momento",
                ["kN·m", "N·m", "N·mm", "lbf·ft"],
                key="projeto_aco_momento_unidade",
                persist_state="session",
            )
            st.number_input(
                f"|Momento fletor| ({momento_unidade})",
                min_value=0.0,
                value=20.0,
                key="projeto_aco_momento",
                persist_state="session",
            )
            comprimento = st.columns(2)
            comprimento[0].number_input(
                "Comprimento",
                min_value=0.001,
                value=3.0,
                key="projeto_aco_comprimento_valor",
                persist_state="session",
            )
            comprimento[1].selectbox(
                "Unidade do comprimento",
                ["m", "mm", "cm", "ft"],
                key="projeto_aco_comprimento_unidade",
                persist_state="session",
            )

        else:
            st.selectbox(
                "Modelo que mais se aproxima do componente",
                list(catalogo.CATALOGO),
                format_func=lambda chave: (
                    f"{catalogo.CATALOGO[chave].grupo} · {chave}"
                ),
                key="projeto_modelo_carga",
                persist_state="session",
            )
            st.info(
                "O módulo abrirá no modelo selecionado. Nele, complete cargas, "
                "dimensões e o ponto crítico.",
                icon=":material/manufacturing:",
            )

        st.pills(
            "Itens já conferidos",
            ITENS_CHECKLIST,
            selection_mode="multi",
            key="projeto_verificacoes",
            persist_state="session",
        )

else:
    objetivo = st.session_state.get("projeto_objetivo", projetos.OBJETIVOS[0])
    dados = st.session_state.get(
        "projeto_dados", projetos.DADOS_DISPONIVEIS[0]
    )
    rota = projetos.recomendar_rota(
        objetivo, dados, st.session_state.get("projeto_componente")
    )
    sequencia = projetos.sequencia_recomendada(
        objetivo, dados, st.session_state.get("projeto_componente")
    )

    with st.container(border=True):
        st.badge("Plano recomendado", icon=":material/route:", color="green")
        st.subheader(st.session_state.get("projeto_nome") or "Projeto sem nome")
        descricao = st.session_state.get("projeto_descricao", "").strip()
        if descricao:
            st.caption(descricao)
        st.markdown(
            f"**Objetivo:** {objetivo}  \n"
            f"**Dados disponíveis:** {dados}  \n"
            f"**Regime:** {st.session_state.get('projeto_regime', 'Não informado')}"
        )
        st.info(
            f"Comece por **{rota.titulo}**. O módulo recebe {rota.entrada} "
            f"e entrega {rota.saida}.",
            icon=rota.icone,
        )

        st.subheader("Sequência de trabalho")
        linhas_fluxo = []
        for ordem, chave_rota in enumerate(sequencia, start=1):
            item = projetos.ROTAS[chave_rota]
            linhas_fluxo.append(
                {
                    "Etapa": ordem,
                    "Módulo": item.titulo,
                    "Resultado esperado": item.saida,
                }
            )
        st.dataframe(pd.DataFrame(linhas_fluxo), hide_index=True)

        conferidos = set(st.session_state.get("projeto_verificacoes", []))
        pendentes = [item for item in ITENS_CHECKLIST if item not in conferidos]
        with st.container(horizontal=True):
            st.metric("Módulos na rota", len(sequencia), border=True)
            st.metric("Itens conferidos", len(conferidos), border=True)
            st.metric("Pendências", len(pendentes), border=True)

        entradas_validas = True
        try:
            _, resumo_entradas = coletar_entradas(rota)
        except ValueError as erro:
            entradas_validas = False
            resumo_entradas = {}
            st.error(str(erro), icon=":material/error:")

        if resumo_entradas:
            st.subheader("Entradas que serão transferidas")
            st.dataframe(
                pd.DataFrame(
                    {
                        "Entrada": list(resumo_entradas),
                        "Valor preparado": [
                            formatar_valor_resumo(valor)
                            for valor in resumo_entradas.values()
                        ],
                    }
                ),
                hide_index=True,
            )
            st.caption(
                "Os valores acima já estão nas unidades esperadas pelo módulo. "
                "Revise as demais propriedades e hipóteses depois de abrir a análise."
            )

        if pendentes:
            st.warning(
                "**Antes de concluir um projeto real, ainda confira:** "
                + ", ".join(pendentes)
                + ".",
                icon=":material/pending_actions:",
            )
        else:
            st.success(
                "Checklist inicial completo. Revise também as hipóteses mostradas "
                "pelo módulo de cálculo.",
                icon=":material/check_circle:",
            )

        if st.button(
            f"Ativar projeto e abrir {rota.titulo.lower()}",
            type="primary",
            icon=":material/arrow_forward:",
            icon_position="right",
            width="stretch",
            disabled=not entradas_validas,
        ):
            try:
                preparar_modulo(rota)
            except ValueError as erro:
                st.error(str(erro), icon=":material/error:")

with st.container(horizontal=True, horizontal_alignment="distribute"):
    st.button(
        "Voltar",
        icon=":material/arrow_back:",
        disabled=etapa == 1,
        on_click=definir_etapa,
        args=(etapa - 1,),
    )
    if etapa < 4:
        st.button(
            "Continuar",
            type="primary",
            icon=":material/arrow_forward:",
            icon_position="right",
            on_click=definir_etapa,
            args=(etapa + 1,),
            disabled=not pode_continuar,
        )
