"""Leitura e gravação da base técnica e do plano de cargas do projeto ativo, para as páginas.

As páginas de cálculo usam :func:`base_ativa` para começar com os valores do projeto (vento do
local, critério do cliente, sobrecarga) e :func:`legenda_da_base` para dizer de onde eles vieram.
As que geram ações gravam no plano com :func:`gravar_acoes_no_plano`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

import streamlit as st

from components.project_tools import registrar_gravacao_vista, tratar_conflito_de_gravacao
from core import base_tecnica as bt
from core import plano_de_cargas as pc
from core.project_store import obter_projeto_ativo, salvar_projeto


def base_ativa() -> bt.BaseTecnica | None:
    """A base técnica do projeto ativo, ou ``None`` (sem projeto ou sem base)."""
    return bt.base_do_projeto(obter_projeto_ativo())


def plano_ativo() -> pc.PlanoDeCargas:
    return pc.plano_do_projeto(obter_projeto_ativo())


def legenda_da_base(base: bt.BaseTecnica | None) -> None:
    """Uma linha dizendo de onde vêm os valores iniciais da página (e os conflitos da base)."""
    if base is None:
        st.caption(
            ":material/info: O projeto ativo não tem base técnica: os campos começam com valores "
            "usuais. Preencha a página **Base técnica do projeto** para que esta e as demais "
            "páginas comecem com o vento do local e o critério do cliente."
        )
        return
    st.caption(
        f":material/fact_check: Valores iniciais da base técnica do projeto — {base.rotulo_cliente}: "
        f"{bt.texto_do_vento(base)}."
    )
    for aviso in bt.avisos(base):
        st.warning(aviso, icon=":material/balance:")


def botao_recarregar_da_base(chaves: Iterable[str], *, key: str, ajuda: str) -> None:
    """Botão que descarta o que foi digitado nestes campos e volta aos valores da base."""
    if st.button(
        "Voltar aos valores da base técnica",
        icon=":material/restart_alt:",
        key=key,
        help=ajuda,
    ):
        for chave in chaves:
            st.session_state.pop(chave, None)
        st.rerun()


def gravar_campo_do_projeto(campo: str, valor: Any, motivo: str) -> bool:
    """Grava ``projeto[campo] = valor`` no projeto ativo (lido na hora, para não perder nada)."""
    projeto = obter_projeto_ativo()
    if projeto is None:
        st.warning(
            "Nenhum projeto ativo: abra ou crie um em **Projetos permanentes**.",
            icon=":material/folder_off:",
        )
        return False
    projeto[campo] = valor
    with tratar_conflito_de_gravacao():
        salvo = salvar_projeto(projeto, motivo=motivo)
    registrar_gravacao_vista(salvo)
    return True


def gravar_base(base: bt.BaseTecnica) -> bool:
    return gravar_campo_do_projeto(
        "base_tecnica", bt.para_dicionario(base), "Base técnica do projeto atualizada"
    )


def gravar_plano(plano: pc.PlanoDeCargas, motivo: str) -> bool:
    return gravar_campo_do_projeto("plano_de_cargas", pc.para_dicionario(plano), motivo)


ETAPAS: tuple[tuple[str, str, str, str], ...] = (
    (
        "1. Base técnica",
        "app_pages/base_tecnica.py",
        ":material/tune:",
        "Critério do cliente, vento do local, limites",
    ),
    (
        "2. Ações",
        "app_pages/vento_estrutura_aberta.py",
        ":material/air:",
        "Vento, pesos e sobrecargas gerados nas páginas",
    ),
    (
        "3. Plano de cargas",
        "app_pages/plano_cargas.py",
        ":material/table_chart:",
        "Ações com código padrão e combinações",
    ),
    (
        "4. Verificações",
        "app_pages/contraventamento_estrutura.py",
        ":material/fact_check:",
        "Barras, contraventamento, ligações",
    ),
    (
        "5. Memorial",
        "app_pages/central_relatorios.py",
        ":material/description:",
        "Word e PDF com o que foi registrado",
    ),
)


def situacao_das_etapas(projeto: Any) -> list[tuple[bool, str]]:
    """Para cada etapa: (feita?, texto curto) a partir do documento do projeto."""
    if not projeto:
        return [(False, "sem projeto ativo")] * len(ETAPAS)
    base = bt.base_do_projeto(projeto)
    plano = pc.plano_do_projeto(projeto)
    geradas = [a for a in plano.acoes if a.origem != "Informada"]
    registros = [r for r in projeto.get("registros_tecnicos", []) if isinstance(r, dict)]
    verificacoes = [r for r in registros if (r.get("resultados") or {}).get("verificações")]
    return [
        (base is not None, base.rotulo_cliente if base else "não preenchida"),
        (bool(geradas), f"{len(geradas)} gerada(s)" if geradas else "nenhuma gerada"),
        (bool(plano.acoes), f"{len(plano.acoes)} ação(ões)" if plano.acoes else "vazio"),
        (bool(verificacoes), f"{len(verificacoes)} verificado(s)"),
        (bool(registros), f"{len(registros)} registro(s)"),
    ]


def mapa_do_projeto(ajuda: str) -> None:
    """As cinco etapas do projeto, com o que o projeto ativo já tem e o atalho para cada uma."""
    projeto = obter_projeto_ativo()
    situacoes = situacao_das_etapas(projeto)
    with st.container(border=True):
        st.subheader("Caminho do projeto", help=ajuda)
        colunas = st.columns(len(ETAPAS))
        for coluna, (titulo, pagina, icone, descricao), (feita, texto) in zip(
            colunas, ETAPAS, situacoes, strict=True
        ):
            with coluna:
                st.markdown(f"**{titulo}**")
                st.caption(descricao)
                st.badge(
                    texto,
                    icon=":material/check_circle:"
                    if feita
                    else ":material/radio_button_unchecked:",
                    color="green" if feita else "gray",
                )
                st.page_link(pagina, label="Abrir", icon=icone)


def gravar_acoes_no_plano(acoes: Sequence[pc.Acao], *, origem: str) -> bool:
    """Inclui ou substitui as ações no plano do projeto ativo."""
    plano = plano_ativo()
    for acao in acoes:
        plano = pc.com_acao(plano, acao)
    codigos = ", ".join(a.codigo for a in acoes)
    return gravar_plano(plano, f"Plano de cargas: {codigos} de {origem}")
