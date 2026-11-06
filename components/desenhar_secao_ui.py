"""Tela de Desenhar seção: modelos, prancheta, propriedades e o caminho até os outros cálculos.

As partes moram em ``st.session_state`` e três lugares as alteram: a prancheta, os modelos prontos e
a tabela. Os três entram por callback, antes de o script rodar, e a prancheta recebe o mesmo desenho
na mesma rodada. ``versao`` conta as alterações: a prancheta ignora um desenho mais velho que o dela.
"""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from components.assistente_cargas_ui import (
    abrir_caso_preenchido,
    enviar_para_mohr,
    tabela_de_verificacoes,
)
from components.figuras import mostrar_figura
from components.prancheta_ui import prancheta
from components.project_tools import (
    botao_registrar_calculo,
    construir_registro_tecnico,
)
from components.robustez import secao_protegida
from core import secao_desenhada as sd
from core import secao_relatorio as sr
from core import section_catalog as catalogo
from core.desenho_estatica import figura_de_tensoes
from core.elementos_base import Resultado, dados_do_registro
from core.elementos_vigas import CATALOGO
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

_ROTULOS = {modelo.nome: modelo for modelo in sd.MODELOS}

DESTINOS = (
    ("viga_reacoes", "Viga: reações e flecha", ":material/linear_scale:", False),
    ("flexao_secao", "Flexão desta seção", ":material/compress:", False),
    ("coluna_simples", "Coluna", ":material/vertical_align_center:", False),
    ("perfil_nbr8800", "Perfil pela norma", ":material/verified:", True),
)
PAGINAS = (
    ("app_pages/flambagem_colunas.py", "Flambagem de colunas", ":material/vertical_align_center:"),
    ("app_pages/vigas_eixos.py", "Vigas e eixos", ":material/linear_scale:"),
    ("app_pages/estruturas_aco.py", "Estruturas de aço", ":material/domain:"),
    ("app_pages/catalogo_perfis.py", "Catálogo de perfis", ":material/view_in_ar:"),
)


def _partes() -> list[dict[str, Any]]:
    return st.session_state[PARTES]


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
    _trocar_partes(sd.partes_de_lista(item.desenho), ajustar=True)


def _salvar(nome: str, analise: sd.Analise) -> str:
    """Grava no catálogo. Devolve a mensagem de erro, ou texto vazio."""
    existente = catalogo.listar_cadastrados().get(nome)
    if existente is not None and not existente.editavel:
        return f"{nome} já é um perfil de referência do catálogo: escolha outro nome."
    try:
        dados = sd.perfil_da_secao(nome, analise)
        catalogo.salvar_perfil(dados, desenho=tuple(p.como_dicionario() for p in analise.partes))
    except (sd.ErroDeSecao, catalogo.ErroDeCatalogo) as erro:
        return str(erro)
    st.session_state[SALVA] = (nome, _impressao(_partes()))
    return ""


def _usar(destino: str, so_perfil: bool, nome: str, analise: sd.Analise) -> None:
    erro = _salvar(nome, analise)
    if erro:
        st.session_state[AVISO] = erro
        return
    valores = {"perfil": nome} if so_perfil else {"tipo_secao": CATALOGO, "perfil": nome}
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
        em_dia = bool(salva) and salva == (nome, _impressao(_partes()))
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
                    else "Salva no catálogo e abre o caso do Assistente de cargas com esta seção."
                ),
            )
        if em_dia:
            st.caption(f"**{nome}** já está na lista de perfis destas páginas:")
            with st.container(horizontal=True):
                for pagina, rotulo, icone in PAGINAS:
                    st.page_link(pagina, label=rotulo, icon=icone)


def _tabela() -> None:
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
    linhas = tuple(sr.linha_da_parte(p) for p in _partes())
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


def tela() -> None:
    _iniciar()
    if st.session_state.pop(IR_PARA, False):
        st.switch_page("app_pages/assistente_cargas.py")
    with secao_protegida("Modelos"):
        _inicio_do_desenho()
    with st.container():
        aviso = st.session_state.pop(AVISO, "")
        if aviso:
            st.warning(aviso, icon=":material/info:")

    analise: sd.Analise | None = None
    falha = ""
    try:
        if _partes():
            analise = _analisar(_impressao(_partes()))
    except sd.ErroDeSecao as erro:
        falha = str(erro)

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
        if analise is None:
            if falha:
                st.error(falha, icon=":material/error:")
            else:
                st.info(
                    "Desenhe uma chapa ou escolha um modelo: as propriedades aparecem aqui.",
                    icon=":material/draw:",
                )
        else:
            forma = sd.reconhecer(analise.partes)
            with secao_protegida("Propriedades"):
                _quadro(analise, forma)
            with secao_protegida("Uso"):
                _uso(analise, forma)

    abas = st.tabs(["Partes", "Todas as propriedades", "Tensões na seção", "Memorial"])
    with abas[0], secao_protegida("Partes"):
        _tabela()
    if analise is None:
        return
    with abas[1], secao_protegida("Propriedades da seção"):
        _propriedades(analise)
    with abas[2], secao_protegida("Tensões"):
        _tensoes(analise, _impressao(_partes()))
    with abas[3], secao_protegida("Memorial"):
        _registro(analise)
