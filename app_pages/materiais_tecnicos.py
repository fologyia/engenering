"""Biblioteca de materiais com proveniência e confiança explícitas."""

from __future__ import annotations

from datetime import date
import math

import pandas as pd
import streamlit as st

from components.project_tools import sincronizar_projeto_ativo
from components.ui import cabecalho_pagina
from core.materials_registry import (
    PROPRIEDADES,
    TIPOS_ORIGEM,
    avaliar_material,
    criar_material_projeto,
    listar_catalogo_referencia,
    material_com_avaliacao,
    resumir_fonte,
    verificar_temperatura,
)
from core.project_store import obter_projeto_ativo, salvar_projeto


@st.cache_data(show_spinner=False)
def _catalogo() -> list[dict]:
    return listar_catalogo_referencia()


def _fmt_numero(valor, casas: int = 3) -> str:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(numero):
        return "—"
    return f"{numero:.{casas}g}".replace(".", ",")


def _linha_material(material: dict) -> dict:
    props = material.get("propriedades", {})
    avaliacao = avaliar_material(material)
    return {
        "Material": material.get("nome"),
        "Família": material.get("familia"),
        "Condição": material.get("condicao"),
        "Sut (MPa)": props.get("Sut_MPa"),
        "Sy (MPa)": props.get("Sy_MPa"),
        "E (GPa)": props.get("E_GPa"),
        "Origem": material.get("origem_tipo"),
        "Confiança": avaliacao["nivel"],
        "Rastreabilidade (%)": avaliacao["indice_rastreabilidade"],
    }

st.set_page_config(
    page_title="Materiais técnicos",
    page_icon=":material/science:",
    layout="wide",
)

cabecalho_pagina(
    "Materiais técnicos",
    "Separe valores preliminares de propriedades efetivamente rastreadas ao lote, produto e condição de serviço.",
    categoria="DADOS DE ENGENHARIA",
    icone=":material/science:",
    cor="teal",
    ajuda_modulo="Materiais técnicos",
    acoes=(("app_pages/central_validacao.py", "Validação", ":material/fact_check:"),),
)

sincronizar_projeto_ativo()
projeto = obter_projeto_ativo()
catalogo = _catalogo()
materiais_projeto = [material_com_avaliacao(item) for item in (projeto or {}).get("materiais_projeto", [])]

st.info(
    "O catálogo é orientativo. Um material só ganha confiança quando a propriedade está ligada à forma do produto, "
    "condição de fornecimento, fonte controlada e conferência responsável.",
    icon=":material/policy:",
)

modo = st.segmented_control(
    "Área de trabalho",
    ["Catálogo de referência", "Biblioteca do projeto", "Comparar"],
    default="Biblioteca do projeto" if projeto else "Catálogo de referência",
    selection_mode="single",
) or "Catálogo de referência"

if modo == "Catálogo de referência":
    f1, f2 = st.columns([2, 1])
    busca = f1.text_input("Buscar material", placeholder="A36, 4140, alumínio, inox...")
    familias = sorted({item["familia"] for item in catalogo})
    familia = f2.selectbox("Família", ["Todas", *familias])
    filtrados = [
        item for item in catalogo
        if (not busca or busca.casefold() in item["nome"].casefold())
        and (familia == "Todas" or item["familia"] == familia)
    ]
    st.dataframe(pd.DataFrame([_linha_material(item) for item in filtrados]), hide_index=True, width="stretch")
    st.caption(
        "Sut e Sy reproduzem a base orientativa já existente no aplicativo. Campos ausentes não são estimados. "
        "Use a biblioteca do projeto para registrar evidência e condições reais."
    )

elif modo == "Biblioteca do projeto":
    if projeto is None:
        st.warning("Abra um projeto permanente para cadastrar materiais rastreáveis.")
        st.page_link("app_pages/gestao_projetos.py", label="Abrir Gestão de projetos", icon=":material/folder_managed:")
        st.stop()

    c1, c2, c3 = st.columns(3)
    c1.metric("Materiais no projeto", len(materiais_projeto))
    c2.metric("Confirmados / rastreáveis", sum(item["avaliacao"]["nivel"] in {"Confirmado", "Rastreável"} for item in materiais_projeto))
    c3.metric("Vinculados ao escopo", sum(bool(item.get("vinculacoes")) for item in materiais_projeto))

    if materiais_projeto:
        st.dataframe(pd.DataFrame([_linha_material(item) for item in materiais_projeto]), hide_index=True, width="stretch")

    st.subheader("Cadastrar ou qualificar um material")
    opcoes_base = {"Cadastro manual": None, **{item["nome"]: item for item in catalogo}}
    base_nome = st.selectbox(
        "Partir de",
        list(opcoes_base),
        help="Ao partir do catálogo, os valores continuam orientativos até você registrar uma fonte aplicável.",
    )
    base = opcoes_base[base_nome] or {}
    props_base = base.get("propriedades", {})

    with st.form("novo_material_projeto", clear_on_submit=False):
        a, b = st.columns(2)
        nome = a.text_input("Designação do material *", value=base.get("nome", ""))
        familia = b.text_input("Família", value=base.get("familia", ""))
        a, b, c = st.columns(3)
        condicao = a.text_input("Condição / tratamento *", value=base.get("condicao", ""))
        forma = b.text_input("Forma e faixa dimensional *", value="" if base else "")
        lote = c.text_input("Lote / corrida / heat number")

        st.markdown("##### Propriedades adotadas")
        p1, p2, p3, p4 = st.columns(4)
        sut = p1.number_input("Sut (MPa)", min_value=0.0, value=props_base.get("Sut_MPa"), step=1.0)
        sy = p2.number_input("Sy (MPa)", min_value=0.0, value=props_base.get("Sy_MPa"), step=1.0)
        e_gpa = p3.number_input("E (GPa)", min_value=0.0, value=props_base.get("E_GPa"), step=1.0)
        nu = p4.number_input("Poisson ν", min_value=-0.99, max_value=0.499, value=props_base.get("nu"), step=0.01)
        p1, p2, p3 = st.columns(3)
        densidade = p1.number_input("Densidade (kg/m³)", min_value=0.0, value=props_base.get("densidade_kg_m3"), step=10.0)
        tmin = p2.number_input("Temperatura mínima qualificada (°C)", value=props_base.get("temperatura_min_C"), step=5.0)
        tmax = p3.number_input("Temperatura máxima qualificada (°C)", value=props_base.get("temperatura_max_C"), step=5.0)

        st.markdown("##### Proveniência e conferência")
        s1, s2 = st.columns(2)
        origem = s1.selectbox("Tipo de origem *", TIPOS_ORIGEM, index=5 if base else 2)
        fonte = s2.text_input("Emissor / fonte *", value=base.get("fonte", "") if base else "")
        s1, s2, s3 = st.columns(3)
        documento = s1.text_input("Documento / certificado *")
        edicao = s2.text_input("Edição / revisão")
        pagina = s3.text_input("Página / cláusula / tabela")
        s1, s2 = st.columns(2)
        responsavel = s1.text_input("Conferido por *", value=projeto.get("responsavel", ""))
        data_verificacao = s2.date_input("Data da conferência", value=date.today(), format="DD/MM/YYYY")
        aplicabilidade = st.text_area(
            "Aplicabilidade ao projeto *",
            placeholder="Ex.: chapa de 12,5 mm, condição normalizada, temperatura de projeto 80 °C, TAG V-101.",
        )
        observacoes = st.text_area("Observações e restrições", value=base.get("observacoes", "") if base else "")
        enviar = st.form_submit_button("Salvar material no projeto", type="primary", icon=":material/save:")

    if enviar:
        try:
            novo = criar_material_projeto(
                nome=nome,
                familia=familia,
                condicao=condicao,
                forma_produto=forma,
                lote=lote,
                propriedades={
                    "Sut_MPa": sut,
                    "Sy_MPa": sy,
                    "E_GPa": e_gpa,
                    "nu": nu,
                    "densidade_kg_m3": densidade,
                    "temperatura_min_C": tmin,
                    "temperatura_max_C": tmax,
                },
                origem_tipo=origem,
                fonte=fonte,
                documento=documento,
                edicao=edicao,
                pagina_clausula=pagina,
                data_verificacao=data_verificacao.isoformat(),
                responsavel_verificacao=responsavel,
                aplicabilidade=aplicabilidade,
                observacoes=observacoes,
            )
        except ValueError as erro:
            st.error(str(erro))
        else:
            projeto["materiais_projeto"].append(novo)
            salvar_projeto(projeto, motivo=f"Material {novo['nome']} cadastrado")
            st.success(
                f"Material salvo como {novo['avaliacao']['nivel']} "
                f"({novo['avaliacao']['indice_rastreabilidade']}% de rastreabilidade)."
            )
            st.rerun()

    if materiais_projeto:
        st.subheader("Inspecionar, conferir faixa e vincular")
        mapa = {item["id"]: f"{item['nome']} · {item['avaliacao']['nivel']}" for item in materiais_projeto}
        material_id = st.selectbox("Material do projeto", list(mapa), format_func=lambda valor: mapa[valor])
        material = next(item for item in materiais_projeto if item["id"] == material_id)
        avaliacao = material["avaliacao"]
        m1, m2 = st.columns([1, 2])
        m1.metric("Nível", avaliacao["nivel"], f"{avaliacao['indice_rastreabilidade']}%")
        with m2:
            st.write(f"**Fonte:** {resumir_fonte(material)}")
            st.caption(avaliacao["aviso"])
        if avaliacao["pendencias"]:
            with st.expander("Pendências de rastreabilidade"):
                for pendencia in avaliacao["pendencias"]:
                    st.write(f"- {pendencia}")

        t1, t2 = st.columns([1, 2])
        temperatura = t1.number_input("Checar temperatura de serviço (°C)", value=None, step=5.0)
        if temperatura is not None:
            faixa = verificar_temperatura(material, temperatura)
            t2.info(f"**{faixa['status']}:** {faixa['mensagem']}")

        componentes = projeto.get("componentes", [])
        if componentes:
            opcoes_componentes = {
                item["id"]: f"{item.get('tag') or 'SEM TAG'} · {item.get('descricao') or 'sem descrição'}"
                for item in componentes
            }
            vinculacoes = st.multiselect(
                "Itens do escopo que usam este material",
                list(opcoes_componentes),
                default=[item for item in material.get("vinculacoes", []) if item in opcoes_componentes],
                format_func=lambda valor: opcoes_componentes[valor],
            )
            if st.button("Salvar vínculos", icon=":material/link:"):
                material["vinculacoes"] = vinculacoes
                for item in projeto["componentes"]:
                    if item.get("id") in vinculacoes:
                        item["material_id"] = material["id"]
                        item["material"] = material["nome"]
                        item["fonte_material"] = resumir_fonte(material)
                    elif item.get("material_id") == material["id"]:
                        item.pop("material_id", None)
                projeto["materiais_projeto"] = [
                    material if item.get("id") == material["id"] else item
                    for item in projeto["materiais_projeto"]
                ]
                salvar_projeto(projeto, motivo=f"Vínculos do material {material['nome']} atualizados")
                st.success("Vínculos atualizados no escopo físico e no memorial.")
                st.rerun()

        confirmar_exclusao = st.checkbox("Confirmo a remoção deste cadastro do projeto.")
        if st.button("Remover cadastro", disabled=not confirmar_exclusao, icon=":material/delete:"):
            projeto["materiais_projeto"] = [item for item in projeto["materiais_projeto"] if item.get("id") != material_id]
            for componente in projeto.get("componentes", []):
                if componente.get("material_id") == material_id:
                    componente.pop("material_id", None)
            salvar_projeto(projeto, motivo=f"Material {material['nome']} removido")
            st.success("Cadastro removido. O histórico permanece disponível nas revisões controladas já criadas.")
            st.rerun()

else:
    todos = catalogo + materiais_projeto
    mapa = {item["id"]: f"{item['nome']} · {'Projeto' if item.get('origem_registro') == 'projeto' else 'Referência'}" for item in todos}
    escolhidos = st.multiselect("Selecione até três materiais", list(mapa), max_selections=3, format_func=lambda valor: mapa[valor])
    selecionados = [next(item for item in todos if item["id"] == valor) for valor in escolhidos]
    if selecionados:
        linhas = []
        for chave, (rotulo, unidade) in PROPRIEDADES.items():
            linha = {"Propriedade": f"{rotulo} ({unidade})"}
            for item in selecionados:
                linha[item["nome"]] = _fmt_numero(item.get("propriedades", {}).get(chave))
            linhas.append(linha)
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Material": item["nome"],
                        "Condição": item.get("condicao"),
                        "Forma": item.get("forma_produto"),
                        "Origem": item.get("origem_tipo"),
                        "Fonte": resumir_fonte(item),
                        "Confiança": avaliar_material(item)["nivel"],
                        "Índice (%)": avaliar_material(item)["indice_rastreabilidade"],
                    }
                    for item in selecionados
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        st.warning("A comparação ajuda na triagem; não substitui critérios de seleção, soldabilidade, corrosão, fabricação e requisitos normativos.")
    else:
        st.info("Escolha materiais do catálogo e, quando houver projeto ativo, da biblioteca rastreada.")
