"""Painel Streamlit para critérios de falha estática."""

from __future__ import annotations

import math
from typing import Iterable

import streamlit as st

from core import failure_criteria as falha
from core import materials as mat


ROTULOS_COMPORTAMENTO = {
    "ductil": "Dúctil",
    "fragil": "Frágil ou quase frágil",
}


def _formatar_fator(valor: float | None) -> str:
    if valor is None:
        return "Dados incompletos"
    return "∞" if math.isinf(valor) else f"{valor:.3f}"


def _mostrar_estado_seguranca(
    fator: float | None,
    criterio: str,
) -> None:
    if fator is None:
        st.warning(
            f"Não foi possível concluir a verificação por {criterio}. "
            "Preencha a propriedade solicitada.",
            icon=":material/warning:",
        )
    elif fator < 1.0:
        st.error(
            f"{criterio}: falha prevista para as propriedades informadas (n < 1).",
            icon=":material/error:",
        )
    elif fator < 1.5:
        st.warning(
            f"{criterio}: margem baixa (1 ≤ n < 1,5).",
            icon=":material/warning:",
        )
    else:
        st.success(
            f"{criterio}: estado abaixo do limite informado.",
            icon=":material/check_circle:",
        )


def mostrar_verificacao_material(
    tensoes_principais: Iterable[float],
    tensao_von_mises: float,
    prefixo: str,
) -> None:
    """Renderiza propriedades, fatores de segurança e diagnóstico."""
    principais = tuple(sorted((float(v) for v in tensoes_principais), reverse=True))
    sigma_1, _, sigma_3 = principais

    with st.container(border=True):
        st.subheader("Verificação do material")
        st.caption(
            "von Mises e Tresca usam o limite de escoamento Sy. Rankine compara "
            "as tensões principais com as resistências de tração e compressão."
        )

        fonte = st.segmented_control(
            "Origem das propriedades",
            ["Base local", "Entrada manual"],
            default="Base local",
            required=True,
            width="stretch",
            key=f"{prefixo}_fonte_propriedades",
        )

        dados = None
        if fonte == "Base local":
            try:
                nomes = mat.listar_nomes()
                escolha = st.selectbox(
                    "Material",
                    nomes,
                    key=f"{prefixo}_material",
                )
                dados = mat.obter_material(escolha)
            except (FileNotFoundError, ValueError) as erro:
                st.error(f"Não foi possível carregar a base: {erro}")
                return
            Sy = float(dados["Sy_MPa"])
            Sut = float(dados["Sut_MPa"])
            comportamento_padrao = (
                "fragil"
                if dados["categoria"] == "ferro_fundido" or Sy <= 0
                else "ductil"
            )
            st.caption(
                f"Base: Sy = {Sy:.1f} MPa | Sut = {Sut:.1f} MPa — "
                f"{dados['observacao']}"
            )
        else:
            comportamento_padrao = "ductil"
            propriedades = st.columns(2)
            with propriedades[0]:
                Sy = st.number_input(
                    "Sy — limite de escoamento (MPa)",
                    min_value=0.0,
                    value=250.0,
                    step=10.0,
                    key=f"{prefixo}_sy_manual",
                    help="Pode ser zero quando o material não possui escoamento definido.",
                )
            with propriedades[1]:
                Sut = st.number_input(
                    "Sut — resistência à tração (MPa)",
                    min_value=0.001,
                    value=400.0,
                    step=10.0,
                    key=f"{prefixo}_sut_manual",
                )

        comportamento = st.segmented_control(
            "Comportamento considerado",
            list(ROTULOS_COMPORTAMENTO),
            format_func=ROTULOS_COMPORTAMENTO.get,
            default=comportamento_padrao,
            required=True,
            width="stretch",
            key=(
                f"{prefixo}_comportamento_"
                f"{dados['nome'] if dados else 'manual'}"
            ),
        )

        precisa_compressao = sigma_3 < 0
        Suc = st.number_input(
            "Suc — resistência à compressão (MPa, 0 = não informada)",
            min_value=0.0,
            value=0.0,
            step=10.0,
            key=(
                f"{prefixo}_suc_"
                f"{dados['nome'] if dados else 'manual'}"
            ),
            help=(
                "Necessária para concluir Rankine quando existe tensão principal "
                "compressiva. Use valor de norma, ensaio ou certificado."
            ),
        )
        if precisa_compressao and Suc == 0:
            st.caption(
                "O estado possui σ3 compressiva. Informe Suc para completar Rankine."
            )

        if Sy > Sut and comportamento == "ductil":
            st.error(
                "Dados incompatíveis para este modelo: Sy não deve superar Sut."
            )
            return

        n_vm = (
            falha.fator_seguranca_von_mises(tensao_von_mises, Sy)
            if Sy > 0
            else None
        )
        n_tresca = (
            falha.fator_seguranca_tresca(principais, Sy)
            if Sy > 0
            else None
        )
        rankine = falha.fator_seguranca_rankine(
            principais,
            Sut_MPa=Sut,
            Suc_MPa=Suc if Suc > 0 else None,
        )

        st.markdown("**Fatores de segurança**")
        with st.container(horizontal=True):
            st.metric(
                "von Mises",
                _formatar_fator(n_vm),
                border=True,
                help="n = Sy / σVM",
            )
            st.metric(
                "Tresca",
                _formatar_fator(n_tresca),
                border=True,
                help="n = Sy / (σ1 − σ3)",
            )
            st.metric(
                "Rankine",
                _formatar_fator(rankine.fator_seguranca),
                border=True,
                help="Usa Sut em tração e Suc em compressão.",
            )

        if comportamento == "ductil":
            if Sy <= 0:
                st.warning(
                    "Este material não possui Sy válido na base. Informe "
                    "propriedades manuais ou use um critério para material frágil.",
                    icon=":material/warning:",
                )
            else:
                _mostrar_estado_seguranca(n_vm, "von Mises")
                st.caption(
                    f"Tresca fornece n = {_formatar_fator(n_tresca)} e costuma "
                    "ser mais conservador ou igual a von Mises."
                )
        else:
            _mostrar_estado_seguranca(
                rankine.fator_seguranca,
                f"Rankine — modo crítico: {rankine.modo_critico}",
            )
            st.caption(
                "Para materiais frágeis com resistências muito diferentes em "
                "tração e compressão, Rankine é uma referência simples; "
                "Coulomb–Mohr pode representar melhor essa assimetria."
            )

        with st.expander(
            "Detalhes da comparação",
            icon=":material/compare_arrows:",
        ):
            st.markdown(
                f"""
                - Tensão principal máxima: **σ1 = {sigma_1:.3f} MPa**
                - Tensão principal mínima: **σ3 = {sigma_3:.3f} MPa**
                - von Mises: **{tensao_von_mises:.3f} MPa**
                - Tresca equivalente: **{falha.tensao_equivalente_tresca(principais):.3f} MPa**
                - Rankine em tração: **n = {_formatar_fator(rankine.fator_tracao)}**
                - Rankine em compressão: **n = {_formatar_fator(rankine.fator_compressao)}**
                """
            )
            st.warning(
                "Os fatores usam propriedades típicas ou informadas pelo usuário. "
                "Eles não definem sozinhos um fator de projeto aceitável.",
                icon=":material/engineering:",
            )
