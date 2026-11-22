"""Tela de Desenhar seção: esboço ou desenho simples, propriedades e o caminho até as contas.

Dois modos. No esboço (o padrão), a seção sai de um esboço paramétrico, como num CAD: cotas que
seguram a medida, restrições, letras nas cotas e o teste de até onde cada letra pode ir. O desenho
simples é a prancheta antiga, de chapas, círculos e polígonos, com os modelos e os perfis do
catálogo. Os dois entregam a mesma coisa às contas: a lista de partes.

As partes moram em ``st.session_state`` e três lugares as alteram: a prancheta, os modelos prontos e
a tabela. Os três entram por callback, antes de o script rodar, e a prancheta recebe o mesmo desenho
na mesma rodada. ``versao`` conta as alterações: a prancheta ignora um desenho mais velho que o dela.
"""

from __future__ import annotations

import json
import math
from typing import Any

import numpy as np
import streamlit as st

from components import volta_da_secao as vs
from components.assistente_cargas_ui import (
    abrir_caso_preenchido,
    enviar_para_mohr,
    tabela_de_verificacoes,
)
from components.esboco_ui import prancheta_do_esboco
from components.figuras import mostrar_figura
from components.prancheta_ui import prancheta
from components.project_tools import (
    botao_registrar_calculo,
    construir_registro_tecnico,
)
from components.robustez import secao_protegida
from core import esboco as eb
from core import esboco_regioes as er
from core import esboco_secao as es
from core import secao_desenhada as sd
from core import secao_relatorio as sr
from core import section_catalog as catalogo
from core.desenho_estatica import figura_de_tensoes
from core.elementos_base import Resultado, dados_do_registro
from core.elementos_vigas import DESENHADA
from core.elementos_word import gerar_word_do_caso
from core.load_to_stress import EstadoPlanoCalculado
from core.medidas_comerciais import CHAPAS
from core.project_store import obter_projeto_ativo

PARTES = "secao_partes"
COTAS = "secao_cotas"
VERSAO = "secao_versao"
AJUSTE = "secao_ajuste"
MODELO = "secao_modelo"
REVISAO_TABELA = "secao_tabela_rev"
BASE_TABELA = "secao_tabela_base"
ERRO_MODELO = "secao_erro_modelo"
ERRO_TABELA = "secao_erro_tabela"
NOME = "secao_nome"
SALVA = "secao_salva"
IR_PARA = "secao_ir_para"
AVISO = "secao_aviso"
CHAVE_PRANCHETA = "secao_prancheta"
MODELO_INICIAL = "I"
MODULO = "Desenhar seção"
MODULO_ID = "desenhar_secao"

MODO = "secao_modo"
MODO_ESBOCO = "Esboço com cotas"
MODO_SIMPLES = "Desenho simples"
MODOS = (MODO_ESBOCO, MODO_SIMPLES)
ESBOCO = "secao_esboco"
VERSAO_ESBOCO = "secao_esboco_versao"
AJUSTE_ESBOCO = "secao_esboco_ajuste"
PARTES_ESBOCO = "secao_esboco_partes"
PROBLEMAS = "secao_esboco_problemas"
CHAVE_ESBOCO = "secao_esboco_prancheta"
_VOLTA_VISTA = "secao_volta_vista"
CONFIGURACOES = "secao_configuracoes"
REGRAS = "secao_regras"
AVISO_DO_TESTE = "secao_aviso_do_teste"

_ROTULOS = {modelo.nome: modelo for modelo in sd.MODELOS}

DESTINOS = (
    ("viga_reacoes", "Reações e diagramas de viga", ":material/linear_scale:", False),
    ("flexao_secao", "Flexão e cisalhamento na seção", ":material/compress:", False),
    ("coluna_simples", "Flambagem de coluna", ":material/vertical_align_center:", False),
    ("perfil_nbr8800", "Momento resistente de perfil de aço", ":material/verified:", True),
)
PAGINAS = (
    ("app_pages/flambagem_colunas.py", "Flambagem de colunas", ":material/vertical_align_center:"),
    ("app_pages/vigas_eixos.py", "Vigas e eixos", ":material/linear_scale:"),
    ("app_pages/estruturas_aco.py", "Barras, treliças e pórticos", ":material/domain:"),
    ("app_pages/catalogo_perfis.py", "Catálogo de perfis", ":material/view_in_ar:"),
)


def _partes() -> list[dict[str, Any]]:
    """As partes do desenho simples."""
    return st.session_state[PARTES]


def _no_esboco() -> bool:
    return st.session_state.get(MODO) != MODO_SIMPLES


def _partes_ativas() -> list[dict[str, Any]]:
    """As partes que vão para as contas: as do esboço, ou as do desenho simples."""
    return st.session_state.get(PARTES_ESBOCO, []) if _no_esboco() else _partes()


def _esboco_vazio() -> dict[str, Any]:
    return eb.Esboco({eb.ORIGEM: (0.0, 0.0)}).como_dicionario()


def _trocar_esboco(esboco: dict[str, Any], *, ajustar: bool = True) -> None:
    """O Python troca o esboço por fora (abrir, limpar, converter): a versão passa a do navegador."""
    estado = st.session_state
    estado[ESBOCO] = esboco
    estado[VERSAO_ESBOCO] = estado.get(VERSAO_ESBOCO, 0) + 1_000_000
    if ajustar:
        estado[AJUSTE_ESBOCO] = estado.get(AJUSTE_ESBOCO, 0) + 1
    _derivar_partes(esboco)


def _derivar_partes(esboco: dict[str, Any]) -> None:
    """As partes e os problemas que saem do esboço, como o navegador acabou de deixar."""
    estado = st.session_state
    partes: list[dict[str, Any]] = []
    problemas: list[dict[str, Any]] = []
    try:
        lido = eb.esboco_de_dicionario(esboco)
        regioes = er.Regioes(eb.Sistema(lido))
        for problema in regioes.problemas:
            if problema.tipo == "vazio" and not lido.curvas:
                continue
            problemas.append({"mensagem": problema.mensagem, "onde": problema.onde})
        if regioes.ok:
            partes = [p.como_dicionario() for p in regioes.partes(regioes.q_base)]
    except (eb.ErroDeEsboco, er.ErroDeRegiao, sd.ErroDeSecao, ValueError) as erro:
        problemas.append({"mensagem": str(erro), "onde": None})
    estado[PARTES_ESBOCO] = partes
    estado[PROBLEMAS] = problemas


def _ao_editar_no_esboco() -> None:
    evento = getattr(st.session_state.get(CHAVE_ESBOCO), "edicao", None)
    if not evento or not isinstance(evento.get("esboco"), dict):
        return
    st.session_state[ESBOCO] = evento["esboco"]
    st.session_state[VERSAO_ESBOCO] = int(evento.get("versao", 0))
    _derivar_partes(evento["esboco"])


def _trazer_do_simples() -> None:
    try:
        esboco = eb.esboco_das_partes(sd.partes_de_lista(_partes()))
    except sd.ErroDeSecao as erro:
        st.session_state[AVISO] = str(erro)
        return
    _trocar_esboco(esboco.como_dicionario())
    st.session_state[AVISO] = (
        "O desenho simples virou esboço: as medidas ainda não são cotas. Ponha cotas e restrições "
        "para prender a forma. Partes que se sobrepunham precisam virar um contorno só."
    )


def _trocar_partes(
    novas: list[sd.Parte],
    *,
    ajustar: bool = False,
    tabela: bool = True,
    versao: int | None = None,
    cotas: list[dict[str, Any]] | None = None,
) -> None:
    """``cotas`` só fica de fora quando a seção é outra: uma cota aponta para pontos de uma parte."""
    estado = st.session_state
    estado[PARTES] = [parte.como_dicionario() for parte in novas]
    estado[COTAS] = [] if cotas is None else cotas
    estado[VERSAO] = estado[VERSAO] + 1 if versao is None else versao
    if ajustar:
        estado[AJUSTE] += 1
    if tabela:  # base nova na tabela: a edição guardada nela valia para a base antiga
        estado[REVISAO_TABELA] += 1
        estado[BASE_TABELA] = [sr.linha_da_parte(p) for p in estado[PARTES]]


def _medidas(modelo: sd.Modelo) -> dict[str, float]:
    return {
        m.chave: float(st.session_state.get(f"secao_m_{modelo.id}_{m.chave}", m.padrao))
        for m in modelo.medidas
    }


def _aplicar_modelo() -> None:
    rotulo = st.session_state.get(MODELO)
    st.session_state[ERRO_MODELO] = ""
    if rotulo not in _ROTULOS:
        return
    modelo = _ROTULOS[rotulo]
    try:
        _trocar_partes(sd.partes_do_modelo(modelo.id, _medidas(modelo)), ajustar=True)
    except sd.ErroDeSecao as erro:
        st.session_state[ERRO_MODELO] = str(erro)


def _iniciar() -> None:
    estado = st.session_state
    if ESBOCO not in estado:
        estado[MODO] = estado.get(MODO) or MODO_ESBOCO
        estado[ESBOCO] = _esboco_vazio()
        estado[VERSAO_ESBOCO] = 0
        estado[AJUSTE_ESBOCO] = 0
        estado[PARTES_ESBOCO] = []
        estado[PROBLEMAS] = []
    if PARTES in estado:
        return
    estado[VERSAO] = 0
    estado[AJUSTE] = 0
    estado[REVISAO_TABELA] = 0
    estado[ERRO_TABELA] = ""
    estado[ERRO_MODELO] = ""
    estado[MODELO] = MODELO_INICIAL
    modelo = _ROTULOS[MODELO_INICIAL]
    _trocar_partes(sd.partes_do_modelo(modelo.id, _medidas(modelo)), ajustar=True)


def _ao_editar_na_prancheta() -> None:
    evento = getattr(st.session_state.get(CHAVE_PRANCHETA), "edicao", None)
    if not evento:
        return
    validas: list[sd.Parte] = []
    for bruta in evento.get("partes", []):
        try:
            validas.append(sd.parte_de_dicionario(bruta))
        except sd.ErroDeSecao:
            continue  # um gesto que não formou parte (polígono sem área) não derruba o desenho
    # O modelo deixa de mandar: mudar uma medida agora apagaria o que foi feito à mão.
    st.session_state[MODELO] = None
    _trocar_partes(validas, versao=int(evento.get("versao", 0)), cotas=evento.get("cotas") or [])


def _ao_editar_tabela() -> None:
    estado = st.session_state
    chave = f"secao_tabela_{estado[REVISAO_TABELA]}"
    mudancas = estado.get(chave) or {}
    linhas = [dict(linha) for linha in estado[BASE_TABELA]]
    for indice, campos in mudancas.get("edited_rows", {}).items():
        linhas[int(indice)].update(campos)
    apagadas = {int(i) for i in mudancas.get("deleted_rows", [])}
    linhas = [linha for i, linha in enumerate(linhas) if i not in apagadas]
    for nova in mudancas.get("added_rows", []):
        linhas.append({"forma": sr.FORMA_ROTULO[sd.RET], "tipo": sr.CHEIO, **nova})
    estado[ERRO_TABELA] = ""
    try:
        partes = sd.partes_de_lista(sr.parte_da_linha(linha) for linha in linhas)
    except (sd.ErroDeSecao, ValueError, TypeError) as erro:
        estado[ERRO_TABELA] = str(erro)
        return
    estado[MODELO] = None
    _trocar_partes(partes, tabela=False, cotas=estado.get(COTAS, []))


def _limpar() -> None:
    if _no_esboco():
        _trocar_esboco(_esboco_vazio())
        return
    st.session_state[MODELO] = None
    _trocar_partes([], ajustar=True)


def _por_perfil() -> None:
    nome = st.session_state.get("secao_add_perfil")
    lado = st.session_state.get("secao_add_lado") or sd.LADOS[0]
    if not nome:
        return
    perfil = catalogo.obter_perfil(nome)
    atuais = sd.partes_de_lista(_partes())
    grupo = max((p.grupo for p in atuais), default=0) + 1
    try:
        novas = sd.encostar(sd.partes_do_perfil(perfil, grupo=grupo), atuais, lado)
    except sd.ErroDeSecao as erro:
        st.session_state[AVISO] = str(erro)
        return
    st.session_state[MODELO] = None
    _trocar_partes([*atuais, *novas], ajustar=True, cotas=st.session_state.get(COTAS, []))
    area = sd.analisar(novas).prop.area
    diferenca = (1.0 - area / perfil.area_mm2) * 100.0
    if abs(diferenca) >= 0.5:
        st.session_state[AVISO] = (
            f"{nome} entrou como chapas, com {abs(diferenca):.1f} % "
            f"{'menos' if diferenca > 0 else 'mais'} de área que o catálogo: os raios de "
            "concordância do laminado não entram no desenho."
        )


def _abrir_salva() -> None:
    nome = st.session_state.get("secao_abrir")
    if not nome:
        return
    item = catalogo.obter(nome)
    st.session_state[MODELO] = None
    st.session_state[NOME] = nome
    if item.esboco:
        st.session_state[MODO] = MODO_ESBOCO
        esboco = dict(item.esboco)
        st.session_state[CONFIGURACOES] = list(esboco.pop("configuracoes", None) or [])
        st.session_state.pop(REGRAS, None)
        _trocar_esboco(esboco)
        return
    st.session_state[MODO] = MODO_SIMPLES
    _trocar_partes(sd.partes_de_lista(item.desenho), ajustar=True)


def _salvar(nome: str, analise: sd.Analise) -> str:
    """Grava no catálogo. Devolve a mensagem de erro, ou texto vazio."""
    existente = catalogo.listar_cadastrados().get(nome)
    if existente is not None and not existente.editavel:
        return f"{nome} já é um perfil de referência do catálogo: escolha outro nome."
    try:
        dados = sd.perfil_da_secao(nome, analise)
        catalogo.salvar_perfil(
            dados,
            desenho=tuple(p.como_dicionario() for p in analise.partes),
            esboco=_esboco_para_salvar() if _no_esboco() else None,
        )
    except (sd.ErroDeSecao, catalogo.ErroDeCatalogo) as erro:
        return str(erro)
    st.session_state[SALVA] = (nome, _impressao(_partes_ativas()))
    return ""


def _usar(destino: str, so_perfil: bool, nome: str, analise: sd.Analise) -> None:
    erro = _salvar(nome, analise)
    if erro:
        st.session_state[AVISO] = erro
        return
    # A norma precisa do perfil; os outros casos aproveitam a forma real da seção.
    valores = {"perfil": nome} if so_perfil else {"tipo_secao": DESENHADA, "desenho": nome}
    abrir_caso_preenchido(destino, valores)
    st.session_state[IR_PARA] = True


def _impressao(partes: list[dict[str, Any]]) -> str:
    return json.dumps(partes, sort_keys=True)


@st.cache_data(max_entries=64, show_spinner=False)
def _analisar(impressao: str) -> sd.Analise:
    """Corpo mudado de propósito quando ``Analise`` muda: o cache antigo fica para trás."""
    partes = sd.partes_de_lista(json.loads(impressao))
    return sd.analisar(partes)


@st.cache_data(max_entries=32, show_spinner=False)
def _campos_de_cortante(impressao: str) -> sd.CamposDeCortante:
    return sd.campos_de_cortante(_analisar(impressao))


def _numero(valor: float, casas: int = 1) -> str:
    return f"{valor:,.{casas}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def _cartao(coluna: Any, rotulo: str, valor: str, unidade: str, ajuda: str) -> None:
    with coluna.container(border=True):
        st.caption(rotulo, help=ajuda)
        st.markdown(f"**{valor}** {unidade}")


# ---------------------------------------------------------------------------
# Blocos da tela
# ---------------------------------------------------------------------------


def _inicio_do_desenho() -> None:
    esquerda, direita = st.columns([2, 3], vertical_alignment="bottom")
    esquerda.selectbox(
        "Começar de um modelo",
        list(_ROTULOS),
        index=None,
        placeholder="Desenho à mão",
        key=MODELO,
        on_change=_aplicar_modelo,
        help=(
            "Escolha a forma e ajuste as medidas. Depois é só mexer na prancheta: a seção pode "
            "receber chapas, furos e outros perfis."
        ),
    )
    with direita, st.container(horizontal=True, horizontal_alignment="right"):
        with st.popover("Perfil do catálogo", icon=":material/add:"):
            st.selectbox(
                "Perfil",
                sorted(catalogo.listar_perfis()),
                index=None,
                placeholder="W 310, U 200, tubo…",
                key="secao_add_perfil",
                help="O perfil entra como chapas e encosta no desenho, centrado no lado escolhido.",
            )
            st.pills(
                "Onde encostar",
                sd.LADOS,
                default=sd.LADOS[0],
                key="secao_add_lado",
                help="Lado do desenho em que o perfil vai encostar.",
            )
            st.button(
                "Pôr no desenho",
                on_click=_por_perfil,
                icon=":material/add:",
                width="stretch",
                key="secao_add_botao",
                help="Junta o perfil ao que já está desenhado.",
            )
        salvas = sorted(n for n, i in catalogo.listar_cadastrados().items() if i.desenho)
        with st.popover("Abrir salva", icon=":material/folder_open:"):
            if salvas:
                st.selectbox(
                    "Seção salva",
                    salvas,
                    index=None,
                    key="secao_abrir",
                    on_change=_abrir_salva,
                    help="Volta à prancheta uma seção desenhada e salva no catálogo.",
                )
            else:
                st.caption("Nenhuma seção salva ainda.")
        st.button(
            "Limpar",
            on_click=_limpar,
            icon=":material/delete:",
            key="secao_limpar",
            help="Apaga o desenho. O botão de desfazer da prancheta traz de volta.",
        )

    # Sempre o mesmo número de blocos antes da prancheta: se um bloco some, o Streamlit monta a
    # prancheta de novo, e ela perde a seleção e o desfazer.
    with st.container():
        _medidas_do_modelo()


def _medidas_do_modelo() -> None:
    rotulo = st.session_state.get(MODELO)
    if rotulo in _ROTULOS:
        modelo = _ROTULOS[rotulo]
        colunas = st.columns(max(len(modelo.medidas), 4))
        for coluna, medida in zip(colunas, modelo.medidas, strict=False):
            coluna.number_input(
                f"{medida.rotulo} (mm)",
                value=medida.padrao,
                min_value=0.0,
                step=1.0,
                format="%g",
                key=f"secao_m_{modelo.id}_{medida.chave}",
                on_change=_aplicar_modelo,
                help=medida.ajuda,
            )
    if st.session_state.get(ERRO_MODELO):
        st.error(st.session_state[ERRO_MODELO], icon=":material/error:")


def _marcas(analise: sd.Analise | None) -> dict[str, Any] | None:
    if analise is None:
        return None
    p = analise.prop
    tamanho = max(p.largura, p.altura)
    return {
        "xc": p.xc,
        "yc": p.yc,
        "xs": p.xc + p.x_s,
        "ys": p.yc + p.y_s,
        "angulo": p.angulo,
        "girado": p.eixos_girados,
        "mostrar_cc": p.pedacos == 1 and float(abs(p.x_s) + abs(p.y_s)) > 0.01 * tamanho,
    }


def _quadro(analise: sd.Analise, forma: sd.Forma) -> None:
    p = analise.prop
    st.badge(
        forma.nome,
        icon=":material/verified:" if forma.familia != sd.FAMILIA_LIVRE else ":material/draw:",
        color="green" if forma.familia != sd.FAMILIA_LIVRE else "blue",
        help=(
            "A forma é reconhecida pelo desenho. Reconhecida, a seção usa as rotinas de norma da "
            "família; livre, usa só as propriedades calculadas aqui."
        ),
    )
    grade = [st.columns(2) for _ in range(4)]
    valores = (
        (
            "Área",
            _numero(p.area / 100, 2),
            "cm²",
            "Área da figura final, sem contar sobreposições.",
        ),
        ("Massa", _numero(p.massa(), 2), "kg/m", "Massa por metro, com aço de 7850 kg/m³."),
        ("Ix", _numero(p.ix / 1e4), "cm⁴", "Inércia em torno do eixo horizontal que passa por G."),
        ("Iy", _numero(p.iy / 1e4), "cm⁴", "Inércia em torno do eixo vertical que passa por G."),
        ("W em x", _numero(p.wx / 1e3), "cm³", "Módulo elástico da fibra mais afastada de G."),
        ("Z em x", _numero(p.zx / 1e3), "cm³", "Módulo plástico em torno do eixo horizontal."),
        ("J", _numero(p.j / 1e4, 2), "cm⁴", "Constante de torção de Saint-Venant."),
        ("r mínimo", _numero(p.r_min, 1), "mm", "Raio de giração do eixo principal mais fraco."),
    )
    for indice, (rotulo, valor, unidade, ajuda) in enumerate(valores):
        _cartao(grade[indice // 2][indice % 2], rotulo, valor, unidade, ajuda)
    for alerta in sd.alertas_da_secao(analise, forma):
        st.warning(alerta, icon=":material/warning:")


def _uso(analise: sd.Analise, forma: sd.Forma) -> None:
    p = analise.prop
    automatico = f"{forma.nome} {p.altura:g}×{p.largura:g}"
    with st.container(border=True):
        st.markdown("**Usar esta seção**")
        digitado = st.text_input(
            "Nome",
            key=NOME,
            placeholder=automatico,
            help="Nome com que a seção aparece nas listas de perfis do programa.",
        )
        nome = digitado.strip() or automatico
        salva = st.session_state.get(SALVA)
        em_dia = bool(salva) and salva == (nome, _impressao(_partes_ativas()))
        pode_usar = p.pedacos == 1
        if st.button(
            "Salva no catálogo" if em_dia else "Salvar no catálogo",
            type="primary",
            disabled=em_dia or not pode_usar,
            icon=":material/check:" if em_dia else ":material/save:",
            width="stretch",
            key="secao_salvar",
            help="Grava a seção no catálogo: ela passa a aparecer em todas as listas de perfis.",
        ):
            erro = _salvar(nome, analise)
            if erro:
                st.session_state[AVISO] = erro
            st.rerun()
        volta = vs.de_onde_veio()
        if volta is not None:
            st.button(
                f"Salvar e voltar ao {volta['rotulo']}",
                type="primary",
                icon=":material/keyboard_return:",
                width="stretch",
                key="secao_salvar_e_voltar",
                disabled=not pode_usar,
                on_click=_salvar_e_voltar,
                args=(nome, analise),
                help=(
                    f"Grava a seção no catálogo com este nome e volta ao {volta['rotulo']}, com a "
                    "seção já escolhida no bloco que a pediu."
                ),
            )
        colunas = st.columns(2)
        livre = forma.familia == sd.FAMILIA_LIVRE
        for indice, (destino, rotulo, icone, so_perfil) in enumerate(DESTINOS):
            sem_rotina = so_perfil and livre
            colunas[indice % 2].button(
                rotulo,
                icon=icone,
                width="stretch",
                disabled=not pode_usar or sem_rotina,
                key=f"secao_usar_{destino}",
                on_click=_usar,
                args=(destino, so_perfil, nome, analise),
                help=(
                    "A norma só tem rotina de M_Rd para I, U, T e tubos. Nesta forma, use as "
                    "tensões da aba abaixo ou a coluna."
                    if sem_rotina
                    else "Salva no catálogo e abre o caso do Cálculo de peças com esta seção."
                ),
            )
        if em_dia:
            st.caption(f"**{nome}** já está na lista de perfis destas páginas:")
            with st.container(horizontal=True):
                for pagina, rotulo, icone in PAGINAS:
                    st.page_link(pagina, label=rotulo, icon=icone)


def _tabela() -> None:
    if _no_esboco():
        st.caption(
            "As partes que saem do esboço: o contorno de aço e os furos. Para mudar, mexa no "
            "esboço, nas cotas ou nas letras."
        )
        st.dataframe(
            [sr.linha_da_parte(p) for p in _partes_ativas()], hide_index=True, width="stretch"
        )
        return
    st.caption(
        "Cada linha é uma parte. Medidas em mm, com x e y no centro da parte. No polígono, escreva "
        "os pontos assim: 0 0; 100 0; 100 50. Partes do mesmo grupo andam juntas na prancheta."
    )
    st.data_editor(
        st.session_state[BASE_TABELA],
        key=f"secao_tabela_{st.session_state[REVISAO_TABELA]}",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        placeholder="—",
        on_change=_ao_editar_tabela,
        column_config={
            "forma": st.column_config.SelectboxColumn(
                "Forma",
                options=list(sr.FORMA_DO_ROTULO),
                required=True,
                help="Retângulo, círculo ou polígono.",
            ),
            "tipo": st.column_config.SelectboxColumn(
                "Tipo",
                options=[sr.CHEIO, sr.FURO],
                required=True,
                help="Furo tira o aço de tudo o que estiver embaixo dele.",
            ),
            "x": st.column_config.NumberColumn("x (mm)", help="Centro da parte em x."),
            "y": st.column_config.NumberColumn("y (mm)", help="Centro da parte em y."),
            "b": st.column_config.NumberColumn("b ou Ø (mm)", help="Largura ou diâmetro."),
            "h": st.column_config.NumberColumn("h (mm)", help="Altura do retângulo."),
            "giro": st.column_config.NumberColumn("Giro (°)", help="Giro da chapa, anti-horário."),
            "pontos": st.column_config.TextColumn("Pontos", help="Só no polígono: x y; x y; x y."),
            "grupo": st.column_config.NumberColumn("Grupo", step=1, help="Zero = parte solta."),
        },
    )
    if st.session_state.get(ERRO_TABELA):
        st.error(st.session_state[ERRO_TABELA], icon=":material/error:")


def _propriedades(analise: sd.Analise) -> None:
    linhas = sr.linhas_de_propriedades(analise.prop, 7850.0)
    st.dataframe(
        [{**linha, "Valor": _numero(float(linha["Valor"]), 2)} for linha in linhas],
        hide_index=True,
        width="stretch",
        height=420,
    )
    st.caption(
        "Área, inércias e módulos saem da figura final. J, Cw e o centro de cisalhamento saem de "
        "elementos finitos sobre a função de empenamento. Conferidos contra soluções exatas: J com "
        "erro abaixo de 0,5 % em retângulos, barras e tubos."
    )


_MAPAS = {"σ normal": "sigma", "τ cisalhamento": "tau", "von Mises": "mises"}
_PELO_CC = "Centro de cisalhamento"
_PELO_CG = "Centro de gravidade"


def _esforcos_da_secao() -> dict[str, Any]:
    linha_1 = st.columns(4)
    n = linha_1[0].number_input(
        "N (kN)", value=0.0, step=10.0, key="secao_n", help="Força normal. Tração positiva."
    )
    mx = linha_1[1].number_input(
        "Mx (kN·m)", value=10.0, step=1.0, key="secao_mx", help="Momento em torno do eixo x."
    )
    my = linha_1[2].number_input(
        "My (kN·m)", value=0.0, step=1.0, key="secao_my", help="Momento em torno do eixo y."
    )
    t = linha_1[3].number_input(
        "T (kN·m)", value=0.0, step=0.1, key="secao_t", help="Momento de torção."
    )
    linha_2 = st.columns([2, 2, 3, 2, 2])
    vx = linha_2[0].number_input(
        "Vx (kN)",
        value=0.0,
        step=10.0,
        key="secao_vx",
        help="Cortante na horizontal, positivo para a direita.",
    )
    vy = linha_2[1].number_input(
        "Vy (kN)",
        value=0.0,
        step=10.0,
        key="secao_vy",
        help="Cortante na vertical, positivo para cima.",
    )
    pelo = linha_2[2].selectbox(
        "O cortante passa pelo",
        (_PELO_CC, _PELO_CG),
        key="secao_pelo",
        help=(
            "Carga que não passa pelo centro de cisalhamento torce a seção. Numa viga em U com a "
            "carga no meio, isso pode pesar mais que o próprio cortante."
        ),
    )
    fy = linha_2[3].number_input(
        "f_y (MPa)",
        value=250.0,
        min_value=1.0,
        step=10.0,
        key="secao_fy",
        help="Escoamento do aço.",
    )
    fs = linha_2[4].number_input(
        "FS",
        value=1.5,
        min_value=1.0,
        step=0.1,
        key="secao_fs",
        help="Fator de segurança sobre o escoamento, nas linhas de tensão.",
    )
    return {
        "n": n,
        "mx": mx,
        "my": my,
        "t": t,
        "vx": vx,
        "vy": vy,
        "pelo": pelo,
        "fy": fy,
        "fs": fs,
    }


def _ligacoes(analise: sd.Analise, mapa: sd.MapaDeTensoes) -> None:
    fluxos = sd.fluxos_nas_ligacoes(analise, mapa)
    if not fluxos:
        return
    st.markdown("**Cisalhamento nas ligações entre as chapas**")
    st.dataframe(
        [
            {
                "Ligação": f"Parte {f.parte_a + 1} com parte {f.parte_b + 1}",
                "Contato (mm)": _numero(f.comprimento),
                "q (kN/m)": _numero(f.q),
            }
            for f in fluxos
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "q é a força que a ligação precisa levar por metro de barra, e é com ela que se dimensiona a "
        "solda: num par de filetes, cada um leva a metade. A perna sai em Ligações soldadas."
    )


def _tensoes(analise: sd.Analise, impressao: str) -> None:
    st.caption(
        "Tração positiva. Mx positivo traciona a base e My positivo traciona a direita. "
        "Com eixos principais girados, a conta já é a da flexão oblíqua."
    )
    e = _esforcos_da_secao()
    vx, vy = e["vx"], e["vy"]
    campos = None
    if vx or vy:
        try:
            campos = _campos_de_cortante(impressao)
        except sd.ErroDeSecao as erro:
            st.warning(str(erro), icon=":material/warning:")
            vx = vy = 0.0
    mapa = sd.tensoes(
        analise,
        e["n"],
        e["mx"],
        e["my"],
        e["t"],
        vx,
        vy,
        campos=campos,
        pelo_centro_de_gravidade=e["pelo"] == _PELO_CG,
    )
    escolha = st.segmented_control(
        "Mapa",
        tuple(_MAPAS),
        default="σ normal",
        key="secao_mapa",
        help="Qual tensão pintar na seção.",
    )
    figura, resumo = st.columns([3, 2])
    desenho = figura_de_tensoes(analise, mapa, _MAPAS.get(escolha or "", "sigma"))
    mostrar_figura(desenho, alvo=figura)
    fs_real = e["fy"] / mapa.mises if mapa.mises > 0 else float("inf")
    _cartao(resumo, "Maior tração", _numero(mapa.sigma_max), "MPa", "Maior σ da seção.")
    _cartao(resumo, "Maior compressão", _numero(mapa.sigma_min), "MPa", "Menor σ da seção.")
    _cartao(
        resumo,
        "τ máximo",
        _numero(mapa.tau_max),
        "MPa",
        "Cortante e torção somados como vetores, ponto a ponto.",
    )
    _cartao(resumo, "τ só do cortante", _numero(mapa.tau_cortante), "MPa", "Sem a torção.")
    _cartao(resumo, "τ de torção", _numero(mapa.tau_torcao), "MPa", "T dividido por Wt.")
    _cartao(resumo, "von Mises", _numero(mapa.mises), "MPa", "Maior valor de √(σ² + 3τ²) na seção.")
    _cartao(resumo, "f_y ÷ von Mises", _numero(fs_real, 2), "", "Só a tensão, sem flambagem.")

    if mapa.torcao_extra:
        st.warning(
            f"Pelo centro de gravidade, o cortante soma {_numero(mapa.torcao_extra, 2)} kN·m de "
            "torção. A conta é de torção livre: com o empenamento impedido o valor real é outro. "
            "Se puder, leve a carga ao centro de cisalhamento.",
            icon=":material/warning:",
        )
    if mapa.erro_cortante > 0.03:
        st.warning(
            f"A integral das tensões ficou {mapa.erro_cortante * 100:.1f} % longe do cortante: a "
            "parede está fina demais para a malha, e o τ desta seção é uma estimativa.",
            icon=":material/warning:",
        )
    linhas, avisos = sr.verificacoes_de_tensao(analise, mapa, e["fy"], e["fs"], vx, vy)
    tabela_de_verificacoes(Resultado("", verificacoes=tuple(linhas)))
    for aviso in avisos:
        st.warning(aviso, icon=":material/warning:")
    if vx or vy or e["t"]:
        _ligacoes(analise, mapa)
    if mapa.mises > 0 and st.button(
        "Ver o ponto crítico no Círculo de Mohr",
        key="secao_mohr",
        icon=":material/donut_large:",
        help="Abre o Círculo de Mohr com σ e τ do ponto onde von Mises é maior.",
    ):
        x, y = mapa.ponto_mises
        enviar_para_mohr(
            EstadoPlanoCalculado(
                mapa.sigma_no_ponto,
                0.0,
                mapa.tau_no_ponto,
                f"Ponto crítico da seção desenhada (x = {_numero(x)} mm, y = {_numero(y)} mm)",
                (),
            ),
            None,
        )
    st.caption(
        "Tensão elástica, com o cortante pela flexão de Saint-Venant, calculado para a forma "
        "desenhada. Compressão pode flambar antes: verifique em Flambagem de colunas. Os cantos "
        "vivos reentrantes concentram tensão, e o valor aqui não inclui isso."
    )


def _registro(analise: sd.Analise) -> None:
    linhas = tuple(sr.linha_da_parte(p) for p in _partes_ativas())
    valores: dict[str, Any] = {"partes": linhas, "densidade_kg_m3": 7850.0}
    resultado = sr.resultado_da_secao(analise, 7850.0)
    registro = construir_registro_tecnico(
        **dados_do_registro(sr.CASO, valores, resultado, modulo=MODULO, modulo_id=MODULO_ID)
    )
    colunas = st.columns(3)
    with colunas[0]:
        botao_registrar_calculo(
            registro, key="secao_registrar", rotulo="Registrar no projeto", tipo="secondary"
        )
    with colunas[1]:
        projeto = obter_projeto_ativo()

        def gerar() -> bytes:
            return gerar_word_do_caso(sr.CASO, valores, resultado, projeto=projeto)

        st.download_button(
            "Gerar o Word",
            data=gerar,
            file_name="secao_desenhada.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            icon=":material/description:",
            on_click="ignore",
            width="stretch",
            key="secao_word",
            help="Word com o desenho e todas as propriedades.",
        )
    with colunas[2]:
        st.download_button(
            "Baixar o desenho",
            data=resultado.figuras[0].png,
            file_name="secao_desenhada.png",
            mime="image/png",
            icon=":material/image:",
            on_click="ignore",
            width="stretch",
            key="secao_png",
            help="Imagem da seção em escala, com as medidas e o centro de gravidade.",
        )


def _salvar_e_voltar(nome: str, analise: sd.Analise) -> None:
    erro = _salvar(nome, analise)
    if erro:
        st.session_state[AVISO] = erro
        return
    vs.marcar_volta(nome)


def _aviso_de_volta() -> None:
    """Quem veio de outra página (o Montador) vê para onde a seção vai e como voltar."""
    volta = vs.de_onde_veio()
    if volta is None:
        return
    marca = repr(sorted(volta.items()))
    if st.session_state.get(_VOLTA_VISTA) != marca:
        st.session_state[_VOLTA_VISTA] = marca
        st.session_state[MODO] = MODO_ESBOCO
    with st.container(border=True):
        colunas = st.columns([4, 1], vertical_alignment="center")
        colunas[0].info(
            f"Você veio do **{volta['rotulo']}**. Desenhe a seção, dê um nome e clique em "
            "**Salvar e voltar** (no quadro Usar esta seção): ela volta já escolhida no bloco que "
            "a pediu.",
            icon=":material/keyboard_return:",
        )
        colunas[1].button(
            "Voltar sem seção",
            icon=":material/undo:",
            key="secao_voltar_sem",
            on_click=vs.marcar_volta,
            args=(None,),
            width="stretch",
            help=f"Volta ao {volta['rotulo']} sem trazer seção nenhuma.",
        )


def tela() -> None:
    _iniciar()
    vs.trocar_se_marcado()
    if st.session_state.pop(IR_PARA, False):
        st.switch_page("app_pages/assistente_cargas.py")
    _aviso_de_volta()
    st.segmented_control(
        "Prancheta",
        MODOS,
        key=MODO,
        required=True,
        label_visibility="collapsed",
        help=(
            "Esboço com cotas: desenhe como num CAD, com cotas que seguram a medida, restrições e "
            "letras que o Montador de fórmulas testa. Desenho simples: a prancheta de chapas, com "
            "os modelos prontos e os perfis do catálogo."
        ),
    )
    with secao_protegida("Modelos"):
        if _no_esboco():
            _inicio_do_esboco()
        else:
            _inicio_do_desenho()
    with st.container():
        aviso = st.session_state.pop(AVISO, "")
        if aviso:
            st.warning(aviso, icon=":material/info:")

    analise: sd.Analise | None = None
    falha = ""
    try:
        if _partes_ativas():
            analise = _analisar(_impressao(_partes_ativas()))
    except sd.ErroDeSecao as erro:
        falha = str(erro)

    if _no_esboco():
        # O desenho sozinho na faixa, com a largura toda; o resto vem embaixo.
        prancheta_do_esboco(
            {
                "esboco": st.session_state[ESBOCO],
                "versao": st.session_state[VERSAO_ESBOCO],
                "ajustar": st.session_state[AJUSTE_ESBOCO],
                "problemas": st.session_state.get(PROBLEMAS, []),
                "marcas": _marcas(analise),
            },
            key=CHAVE_ESBOCO,
            ao_editar=_ao_editar_no_esboco,
        )
        propriedades, uso = st.columns([3, 2], gap="medium")
        with propriedades:
            _propriedades_ou_aviso(analise, falha)
        with uso:
            if analise is not None:
                with secao_protegida("Uso"):
                    _uso(analise, sd.reconhecer(analise.partes))
        with secao_protegida("Testar o desenho"):
            _teste_do_desenho()
    else:
        esquerda, direita = st.columns([5, 2], gap="medium")
        with esquerda:
            prancheta(
                {
                    "partes": _partes(),
                    "versao": st.session_state[VERSAO],
                    "ajustar": st.session_state[AJUSTE],
                    "marcas": _marcas(analise),
                    "chapas": list(CHAPAS.valores),
                    "cotas": st.session_state.get(COTAS, []),
                },
                key=CHAVE_PRANCHETA,
                ao_editar=_ao_editar_na_prancheta,
            )
        with direita:
            _propriedades_ou_aviso(analise, falha)
            if analise is not None:
                with secao_protegida("Uso"):
                    _uso(analise, sd.reconhecer(analise.partes))

    abas = st.tabs(["Partes", "Todas as propriedades", "Tensões na seção", "Memorial"])
    with abas[0], secao_protegida("Partes"):
        _tabela()
    if analise is None:
        return
    with abas[1], secao_protegida("Propriedades da seção"):
        _propriedades(analise)
    with abas[2], secao_protegida("Tensões"):
        _tensoes(analise, _impressao(_partes_ativas()))
    with abas[3], secao_protegida("Memorial"):
        _registro(analise)


def _propriedades_ou_aviso(analise: sd.Analise | None, falha: str) -> None:
    if analise is None:
        if falha:
            st.error(falha, icon=":material/error:")
        elif _no_esboco():
            st.info(
                "Desenhe um contorno fechado no esboço: Linha (L), Retângulo (R) ou Círculo (C). "
                "Contorno dentro de contorno vira furo. As propriedades aparecem aqui.",
                icon=":material/draw:",
            )
        else:
            st.info(
                "Desenhe uma chapa ou escolha um modelo: as propriedades aparecem aqui.",
                icon=":material/draw:",
            )
        return
    with secao_protegida("Propriedades"):
        _quadro(analise, sd.reconhecer(analise.partes))


def _inicio_do_esboco() -> None:
    with st.container(horizontal=True, horizontal_alignment="right"):
        salvas = sorted(n for n, i in catalogo.listar_cadastrados().items() if i.desenho)
        with st.popover("Abrir salva", icon=":material/folder_open:"):
            if salvas:
                st.selectbox(
                    "Seção salva",
                    salvas,
                    index=None,
                    key="secao_abrir",
                    on_change=_abrir_salva,
                    help="Volta uma seção salva no catálogo. Feita no esboço, volta com as cotas.",
                )
            else:
                st.caption("Nenhuma seção salva ainda.")
        st.button(
            "Trazer do desenho simples",
            on_click=_trazer_do_simples,
            icon=":material/move_down:",
            key="secao_trazer",
            disabled=not _partes(),
            help=(
                "As partes do desenho simples viram linhas e círculos do esboço, sem cotas. O que "
                "está no esboço agora é trocado (o desfazer da prancheta traz de volta)."
            ),
        )
        st.button(
            "Limpar",
            on_click=_limpar,
            icon=":material/delete:",
            key="secao_limpar_esboco",
            help="Apaga o esboço. O desfazer da prancheta traz de volta.",
        )


def _esboco_para_salvar() -> dict[str, Any]:
    """O esboço como está, com as configurações da tabela (que não passam pela prancheta)."""
    esboco = dict(st.session_state.get(ESBOCO) or {})
    configuracoes = st.session_state.get(CONFIGURACOES) or []
    if configuracoes:
        esboco["configuracoes"] = configuracoes
    return esboco


def _mudar_o_esboco(mudanca: Any) -> None:
    """O Python mexe nos dados do esboço (faixas, regras): a prancheta recebe e guarda junto."""
    esboco = json.loads(json.dumps(st.session_state.get(ESBOCO) or {}))
    mudanca(esboco)
    _trocar_esboco(esboco, ajustar=False)


def _mudar_faixa(letra: str) -> None:
    estado = st.session_state
    de, ate, passo = (
        estado.get(f"secao_faixa_{letra}_{campo}") for campo in ("de", "ate", "passo")
    )
    if de is None or ate is None or passo is None or not (ate > de) or not (passo > 0):
        estado[AVISO_DO_TESTE] = (
            f"Na faixa de {letra}, o até precisa passar do de, com passo acima de zero."
        )
        return

    def mudar(esboco: dict[str, Any]) -> None:
        for variavel in esboco.get("variaveis", []):
            if variavel.get("nome") == letra:
                variavel.update(de=float(de), ate=float(ate), passo=float(passo))

    _mudar_o_esboco(mudar)


def _aplicar_regras() -> None:
    estado = st.session_state
    linhas = [
        linha.strip() for linha in str(estado.get(REGRAS) or "").splitlines() if linha.strip()
    ]
    esboco = estado.get(ESBOCO) or {}
    letras = {v.get("nome") for v in esboco.get("variaveis", [])}
    for linha in linhas:
        try:
            regra = eb.ler_regra(linha)
        except eb.ErroDeEsboco as erro:
            estado[AVISO_DO_TESTE] = str(erro)
            return
        faltam = eb.letras_da_regra(regra) - letras - set(eb.MEDIDAS_DA_REGRA)
        if faltam:
            estado[AVISO_DO_TESTE] = (
                f"A regra “{linha}” usa {', '.join(sorted(faltam))}, que não é letra do esboço nem "
                f"medida ({', '.join(eb.MEDIDAS_DA_REGRA)})."
            )
            return

    def mudar(dados: dict[str, Any]) -> None:
        if linhas:
            dados["regras"] = linhas
        else:
            dados.pop("regras", None)

    _mudar_o_esboco(mudar)


@st.cache_resource(max_entries=16, show_spinner=False)
def _modelo_do_esboco(impressao: str) -> es.Modelo:
    """O esboço pronto para ser refeito com outras medidas (um por desenho diferente)."""
    return es.registrar(json.loads(impressao))[0]


@st.cache_data(max_entries=64, show_spinner=False)
def _faixas_das_letras(impressao: str) -> list[es.FaixaDaLetra]:
    modelo = _modelo_do_esboco(impressao)
    return [modelo.faixa(letra) for letra in modelo.letras]


_MEDIDAS_DA_VARREDURA = {
    "Área (mm²)": "area",
    "Ix (mm⁴)": "ix",
    "Iy (mm⁴)": "iy",
    "W em x (mm³)": "wx",
    "Parede mais fina (mm)": "parede",
}


@st.cache_data(max_entries=64, show_spinner=False)
def _varredura(impressao: str, letra: str, de: float, ate: float) -> dict[str, list[float]]:
    """As medidas da seção ao longo da letra, com as outras paradas. Onde o desenho não existe, nada."""
    modelo = _modelo_do_esboco(impressao)
    valores = np.linspace(de, ate, 61)
    numeros = modelo.numeros({letra: valores}, (es.AREA, es.IX, es.IY, es.FIBRA, es.FOLGA))
    existe = numeros[es.FOLGA] >= 0.0
    nada = np.full(valores.shape, np.nan)
    with np.errstate(all="ignore"):
        saida = {
            "valor": valores,
            "area": np.where(existe, numeros[es.AREA], nada),
            "ix": np.where(existe, numeros[es.IX], nada),
            "iy": np.where(existe, numeros[es.IY], nada),
            "wx": np.where(existe, numeros[es.IX] / numeros[es.FIBRA], nada),
            "parede": np.where(existe & np.isfinite(numeros[es.FOLGA]), numeros[es.FOLGA], nada),
        }
    return {chave: [float(v) for v in vetor] for chave, vetor in saida.items()}


def _teste_do_desenho() -> None:
    """O desenho testado pelas letras: até onde vai, varredura, regras e configurações."""
    if not _partes_ativas():
        return
    esboco = st.session_state.get(ESBOCO) or {}
    impressao = es.impressao(esboco)
    with st.container(border=True):
        st.markdown("**Testar o desenho**")
        aviso = st.session_state.pop(AVISO_DO_TESTE, "")
        if aviso:
            st.warning(aviso, icon=":material/warning:")
        try:
            modelo = _modelo_do_esboco(impressao)
        except (eb.ErroDeEsboco, er.ErroDeRegiao, sd.ErroDeSecao, ValueError) as erro:
            st.warning(str(erro), icon=":material/warning:")
            return
        agora = modelo.medir({}).avaliacao
        folga = float(agora.folga[0])
        if not bool(agora.valido[0]):
            st.error(
                f"O desenho de agora já não passa: {er.motivo_em_texto(agora.motivo[0])}.",
                icon=":material/error:",
            )
        elif math.isfinite(folga) and len(modelo.regioes.lacos) > 1:
            st.caption(
                f"Parede mais fina agora: **{_numero(folga, 2)} mm** (a menor distância entre "
                "contornos: do furo até a borda, ou de um furo a outro)."
            )
        if not modelo.graus.definido:
            st.caption(
                f"O esboço ainda tem {modelo.graus.livres} graus livres: no teste, o que está em "
                "azul pode andar junto. Prenda com cotas e restrições para o teste mexer só na "
                "letra."
            )
        abas = st.tabs(["Até onde vai", "Varredura", "Regras de projeto", "Configurações"])
        with abas[0]:
            _ate_onde_vai(modelo, impressao)
        with abas[1]:
            _aba_da_varredura(modelo, impressao)
        with abas[2]:
            _aba_das_regras(modelo, esboco)
        with abas[3]:
            _aba_das_configuracoes(modelo)


def _sem_letras() -> None:
    st.caption(
        "Ponha uma letra numa cota (duplo clique na medida, e digite d ou 2*d): aqui aparece até "
        "onde ela pode ir sem o desenho deixar de existir. Salva no catálogo, a seção leva a "
        "letra para o Montador de fórmulas como incógnita."
    )


def _ate_onde_vai(modelo: es.Modelo, impressao: str) -> None:
    if not modelo.letras:
        _sem_letras()
        return
    if not bool(modelo.medir({}).avaliacao.valido[0]):
        st.caption(
            "Com o desenho de agora fora, não há de onde partir: ajuste as letras ou as regras."
        )
        return
    for faixa in _faixas_das_letras(impressao):
        letra = faixa.letra
        st.markdown(
            f"**{letra}** = {faixa.valor:.4g} mm: ".replace(".", ",")
            + faixa.texto().split(": ", 1)[1]
        )
        de, ate, passo = modelo.faixa_de_teste(letra)
        colunas = st.columns(3)
        for coluna, campo, rotulo, valor, ajuda in (
            (colunas[0], "de", "de", de, "O menor valor do teste e da busca do Montador."),
            (colunas[1], "ate", "até", ate, "O maior valor do teste e da busca do Montador."),
            (colunas[2], "passo", "passo", passo, "A distância entre dois valores testados."),
        ):
            coluna.number_input(
                f"{letra}: {rotulo} (mm)",
                value=float(f"{valor:.4g}"),
                format="%g",
                step=None,
                key=f"secao_faixa_{letra}_{campo}",
                on_change=_mudar_faixa,
                args=(letra,),
                help=ajuda,
            )
    st.caption("A faixa vai junto com a seção salva: a busca em faixas do Montador começa por ela.")


def _aba_da_varredura(modelo: es.Modelo, impressao: str) -> None:
    if not modelo.letras:
        _sem_letras()
        return
    import altair as alt
    import pandas as pd

    colunas = st.columns(2)
    letra = colunas[0].selectbox(
        "Letra", modelo.letras, key="secao_varredura_letra", help="A letra que vai variar."
    )
    rotulo = colunas[1].selectbox(
        "Medida",
        list(_MEDIDAS_DA_VARREDURA),
        key="secao_varredura_medida",
        help="O que a curva mostra. Onde ela some, o desenho deixa de existir.",
    )
    de, ate, _ = modelo.faixa_de_teste(letra)
    dados = _varredura(impressao, letra, de, ate)
    tabela = pd.DataFrame({letra: dados["valor"], rotulo: dados[_MEDIDAS_DA_VARREDURA[rotulo]]})
    linha = (
        alt.Chart(tabela)
        .mark_line(point=True)
        .encode(
            x=alt.X(f"{letra}:Q", title=f"{letra} (mm)", scale=alt.Scale(zero=False)),
            y=alt.Y(f"{rotulo}:Q", title=rotulo, scale=alt.Scale(zero=False)),
            tooltip=[letra, rotulo],
        )
    )
    agora = (
        alt.Chart(pd.DataFrame({letra: [modelo.base[letra]]}))
        .mark_rule(strokeDash=[4, 4])
        .encode(x=f"{letra}:Q")
    )
    st.altair_chart((linha + agora).properties(height=260), width="stretch")
    st.caption(
        f"As outras letras ficam como estão; o tracejado é o {letra} de agora. Onde a curva "
        "some, a forma deixa de existir (furo na borda, regra de projeto furada)."
    )


def _aba_das_regras(modelo: es.Modelo, esboco: dict[str, Any]) -> None:
    if REGRAS not in st.session_state:
        st.session_state[REGRAS] = "\n".join(esboco.get("regras") or [])
    medidas = "; ".join(f"**{nome}**: {texto}" for nome, texto in eb.MEDIDAS_DA_REGRA.items())
    st.caption(
        "Uma regra por linha, com as letras e as medidas do desenho. O desenho que fura uma regra "
        "deixa de existir no teste e no Montador, como o furo que encosta na borda. "
        f"Medidas: {medidas}."
    )
    st.text_area(
        "Regras de projeto",
        key=REGRAS,
        placeholder="parede >= 1,5*d\nd <= 0,6*h",
        height=110,
        help="Exemplos: parede >= 1,5*d (a parede em volta do furo), area <= 2500, d <= 0,6*h.",
    )
    st.button(
        "Aplicar as regras",
        key="secao_aplicar_regras",
        on_click=_aplicar_regras,
        icon=":material/rule:",
        help="As regras passam a valer no teste e na seção salva.",
    )
    if modelo.regras:
        agora = modelo.medir({}).avaliacao
        valores = {
            **modelo.esboco.valores(),
            "parede": float(agora.folga[0]),
            "area": float(agora.exatas.area[0]),
            "largura": float(agora.exatas.x_max[0] - agora.exatas.x_min[0]),
            "altura": float(agora.exatas.y_max[0] - agora.exatas.y_min[0]),
        }
        for regra in modelo.regras:
            try:
                margem = float(eb.folga_da_regra(regra, valores))
            except eb.ErroDeEsboco:
                continue
            situacao = "vale agora" if margem >= 0 else "furada agora"
            st.markdown(f"- `{regra.texto}`: {situacao} (folga de {_numero(margem, 2)})")


def _aba_das_configuracoes(modelo: es.Modelo) -> None:
    if not modelo.letras:
        _sem_letras()
        return
    import pandas as pd

    letras = list(modelo.letras)
    padrao = [{"Nome": "Agora", **{letra: modelo.base[letra] for letra in letras}}]
    linhas = st.session_state.get(CONFIGURACOES) or padrao
    base = pd.DataFrame(
        [{coluna: linha.get(coluna) for coluna in ["Nome", *letras]} for linha in linhas]
    )
    st.caption(
        "Como a tabela de projeto de um CAD: cada linha é um jeito de pôr as letras. A conta de "
        "cada linha sai embaixo; a tabela vai junto com a seção salva."
    )
    editada = st.data_editor(
        base,
        key="secao_configuracoes_editor",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "Nome": st.column_config.TextColumn("Nome", help="Um nome para a configuração."),
            **{
                letra: st.column_config.NumberColumn(f"{letra} (mm)", help=f"O valor de {letra}.")
                for letra in letras
            },
        },
    )
    registros = [
        {chave: (None if pd.isna(valor) else valor) for chave, valor in linha.items()}
        for linha in editada.to_dict("records")
    ]
    if st.session_state.get(CONFIGURACOES) or registros != padrao:
        st.session_state[CONFIGURACOES] = registros  # só o que a pessoa mexeu vai junto da seção
    validas = [r for r in registros if all(isinstance(r.get(l), int | float) for l in letras)]
    if not validas:
        return
    vetores = {letra: np.array([float(r[letra]) for r in validas]) for letra in letras}
    numeros = modelo.numeros(vetores, (es.AREA, es.IX, es.IY, es.FIBRA, es.FOLGA))
    motivos = modelo.medir(vetores).avaliacao.motivo
    resultado = []
    for i, r in enumerate(validas):
        existe = numeros[es.FOLGA][i] >= 0.0
        resultado.append(
            {
                "Nome": r.get("Nome") or f"{i + 1}",
                **{letra: _numero(float(r[letra]), 2) for letra in letras},
                "Área (cm²)": _numero(numeros[es.AREA][i] / 100, 2) if existe else "—",
                "Ix (cm⁴)": _numero(numeros[es.IX][i] / 1e4, 2) if existe else "—",
                "Iy (cm⁴)": _numero(numeros[es.IY][i] / 1e4, 2) if existe else "—",
                "W em x (cm³)": (
                    _numero(numeros[es.IX][i] / numeros[es.FIBRA][i] / 1e3, 2) if existe else "—"
                ),
                "Parede (mm)": _numero(numeros[es.FOLGA][i], 2) if existe else "—",
                "Existe": "sim" if existe else er.motivo_em_texto(motivos[i]),
            }
        )
    st.dataframe(resultado, hide_index=True, width="stretch")
