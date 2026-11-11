"""Tela do Cálculo de peças: o painel de entrada e a tela de cada caso.

A tela não conhece nenhum caso: tudo sai de :mod:`core.elementos_catalogo`. O campo já vem com a
ajuda, e o resultado já vem com as verificações, os pontos de tensão e os envios para outros casos.

São dois estados. Sem caso aberto, o painel mostra as perguntas mais comuns e todos os casos por
área e grupo. Com um caso aberto, os dados ficam à esquerda e a resposta à direita, na mesma altura:
mudou um número, o desenho e o resultado mudam do lado.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from functools import partial
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from components import estudo_da_medida_ui as estudo_ui
from components import load_models as modelos_de_secao
from components.croqui_editavel_ui import croqui_editavel
from components.elementos_croquis import CROQUIS, CROQUIS_VIVOS, svg_do_croqui
from components.figuras import mostrar_figura
from components.project_tools import (
    botao_registrar_calculo,
    construir_registro_tecnico,
    id_registro_existente,
)
from components.robustez import secao_protegida
from components.ui import fronteira_modelo
from core import cotas_dos_desenhos as cd
from core import elementos_catalogo as cat
from core import elementos_vigas as ev
from core import load_to_stress as cargas
from core import material_catalog as mat
from core import memorial_verificacoes as mv
from core import secao_desenhada as sd
from core import section_catalog as catalogo
from core.desenho_tensoes import figura_dos_elementos
from core.elementos_base import (
    Campo,
    Caso,
    Coluna,
    Grafico,
    Metrica,
    Ponto,
    Resultado,
    calcular_caso,
    dados_do_registro,
    ordenar_por_severidade,
)
from core.elementos_word import gerar_word_do_caso
from core.project_store import obter_projeto_ativo
from core.verificacao import tabela_verificacoes

MODULO = "Cálculo de peças"
MODULO_ID = "assistente_cargas"
_SEM_MATERIAL = "— preencher à mão —"
#: Campos que o material do catálogo preenche, e de qual propriedade.
_CAMPOS_DE_MATERIAL = {
    "sy_MPa": "sy_MPa",
    "fy_MPa": "sy_MPa",
    "sut_MPa": "sut_MPa",
    "fu_MPa": "sut_MPa",
    "sigma_r_MPa": "sut_MPa",
}


OUTRAS_PAGINAS = (
    (
        "app_pages/projeto_parafusos.py",
        "Juntas parafusadas completas",
        ":material/build:",
    ),
    ("app_pages/ligacoes_estruturais.py", "Soldas e ligações", ":material/link:"),
    ("app_pages/analise_fadiga.py", "Fadiga, com curva S-N", ":material/cycle:"),
    ("app_pages/vigas_eixos.py", "Vigas e eixos sem limite de apoios", ":material/linear_scale:"),
    ("app_pages/flambagem_colunas.py", "Flambagem de colunas", ":material/architecture:"),
    ("app_pages/estruturas_aco.py", "Barras, treliças e pórticos", ":material/domain:"),
)
RECENTES = 6
#: Onde a página Desenhar seção guarda a seção aberta.
PARTES_DA_SECAO_ABERTA = "secao_partes"
NOME_DA_SECAO_ABERTA = "secao_nome"


def chave_do_campo(caso_id: str, campo: str) -> str:
    return f"assistente::{caso_id}::{campo}"


def _croqui(caso: Caso, valores: Mapping[str, Any] | None = None) -> str | None:
    vivo = CROQUIS_VIVOS.get(caso.id)
    if vivo is not None and valores is not None:
        return svg_do_croqui(caso.titulo, vivo(valores))
    if caso.id in CROQUIS:
        return svg_do_croqui(caso.titulo, CROQUIS[caso.id])
    modelo = modelos_de_secao.CATALOGO.get(caso.id)
    return modelos_de_secao.montar_svg(modelo) if modelo else None


# ---------------------------------------------------------------------------
# Navegação
# ---------------------------------------------------------------------------


def _escolher(caso_id: str) -> None:
    st.session_state["assistente_geometria"] = caso_id
    recentes = [i for i in st.session_state.get("assistente_recentes", []) if i != caso_id]
    st.session_state["assistente_recentes"] = [caso_id, *recentes][:RECENTES]


def _voltar_ao_painel() -> None:
    st.session_state["assistente_geometria"] = None


def _ao_trocar_modelo() -> None:
    escolha = st.session_state.get("assistente_modelo")
    if escolha:
        _escolher(escolha)


def _ao_buscar() -> None:
    escolha = st.session_state.get("assistente_busca")
    if escolha:
        _escolher(escolha)
    st.session_state["assistente_busca"] = None


def caso_aberto() -> Caso | None:
    """``assistente_geometria`` é a chave canônica, a que o Assistente de projeto grava.

    Sem caso, ou com um rótulo que não existe mais, a página mostra o painel.
    """
    bruto = st.session_state.get("assistente_geometria")
    if not cat.existe(bruto):
        st.session_state["assistente_geometria"] = None
        return None
    ativo = cat.resolver(bruto)
    st.session_state["assistente_geometria"] = ativo
    return cat.CASOS[ativo]


def _busca() -> None:
    st.selectbox(
        "Procurar um caso",
        list(cat.CASOS),
        index=None,
        format_func=lambda i: f"{cat.CASOS[i].titulo} · {cat.CASOS[i].grupo}",
        placeholder="Digite: parafuso, rosca, viga, flexão, chaveta, rolamento, gancho...",
        help="Digite parte do nome e escolha. O caso abre na hora.",
        key="assistente_busca",
        on_change=_ao_buscar,
    )


def _botao_do_caso(caso_id: str, *, prefixo: str = "abrir") -> None:
    caso = cat.CASOS[caso_id]
    st.button(
        caso.titulo,
        key=f"{prefixo}::{caso_id}",
        type="tertiary",
        icon=":material/chevron_right:",
        help=caso.resumo,
        on_click=_escolher,
        args=(caso_id,),
    )


# ---------------------------------------------------------------------------
# Painel
# ---------------------------------------------------------------------------


def _atalhos() -> None:
    st.subheader("O que você precisa verificar?")
    por_linha = 3
    for inicio in range(0, len(cat.ATALHOS), por_linha):
        colunas = st.columns(por_linha)
        for coluna, atalho in zip(colunas, cat.ATALHOS[inicio : inicio + por_linha], strict=False):
            with coluna, st.container(border=True, height="stretch"):
                desenho, texto = st.columns([2, 3], vertical_alignment="center")
                svg = _croqui(cat.CASOS[atalho.caso])
                if svg:
                    desenho.image(svg, width="stretch")
                with texto:
                    st.markdown(f"**{atalho.pergunta}**")
                    st.caption(atalho.detalhe)
                st.space("stretch")
                st.button(
                    "Abrir",
                    key=f"atalho::{atalho.caso}",
                    icon=atalho.icone,
                    width="stretch",
                    help=cat.CASOS[atalho.caso].titulo,
                    on_click=_escolher,
                    args=(atalho.caso,),
                )


def _recentes() -> None:
    ids = [i for i in st.session_state.get("assistente_recentes", []) if i in cat.CASOS]
    if not ids:
        return
    st.markdown("**Abertos nesta sessão**")
    with st.container(horizontal=True):
        for caso_id in ids:
            st.button(
                cat.CASOS[caso_id].titulo,
                key=f"recente::{caso_id}",
                icon=":material/history:",
                on_click=_escolher,
                args=(caso_id,),
                help=cat.CASOS[caso_id].resumo,
            )


def _cartao_do_grupo(grupo: str, ids: list[str]) -> None:
    info = cat.info_do_grupo(grupo)
    with st.container(border=True, height="stretch"):
        st.markdown(f"#### {info.icone} {grupo} :blue-badge[{len(ids)}]")
        st.caption(info.descricao)
        for caso_id in ids:
            _botao_do_caso(caso_id)


def _area(area: str) -> None:
    st.caption(cat.AREAS_INFO[area].descricao)
    grupos = list(cat.GRUPOS[area].items())
    # Quatro por linha quando a conta fecha, para a grade não terminar com um buraco.
    por_linha = 4 if len(grupos) % 4 == 0 else 3
    for inicio in range(0, len(grupos), por_linha):
        colunas = st.columns(por_linha)
        for coluna, (grupo, ids) in zip(colunas, grupos[inicio : inicio + por_linha], strict=False):
            with coluna:
                _cartao_do_grupo(grupo, ids)


def painel() -> None:
    """A entrada da página: a busca, as perguntas mais comuns e todos os casos por área."""
    _busca()
    _recentes()
    _atalhos()
    st.page_link(
        "app_pages/desenhar_secao.py",
        label="A seção não está no catálogo? Desenhe e use em qualquer caso",
        icon=":material/draw:",
    )
    st.subheader("Todos os casos")
    abas = st.tabs(
        [
            f"{cat.AREAS_INFO[area].icone} {area} ({sum(map(len, cat.GRUPOS[area].values()))})"
            for area in cat.AREAS
        ]
    )
    for aba, area in zip(abas, cat.AREAS, strict=True):
        with aba:
            _area(area)
    with st.expander("Comparar todos os casos em uma tabela", icon=":material/table_rows:"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Área": cat.area_do_caso(item.id),
                        "Grupo": item.grupo,
                        "Caso": item.titulo,
                        "Quando usar": item.resumo,
                    }
                    for item in cat.CASOS.values()
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    with st.container(border=True):
        st.markdown("**Páginas com o cálculo mais completo**")
        st.caption("Quando o caso simples não basta, estes assuntos têm página própria.")
        with st.container(horizontal=True):
            for pagina, rotulo, icone in OUTRAS_PAGINAS:
                st.page_link(pagina, label=rotulo, icon=icone)


# ---------------------------------------------------------------------------
# Cabeça da tela do caso
# ---------------------------------------------------------------------------


def barra_de_navegacao(caso: Caso) -> None:
    area = cat.area_do_caso(caso.id)
    with st.container(horizontal=True, vertical_alignment="center"):
        st.button(
            "Voltar ao painel",
            key="assistente_voltar",
            icon=":material/grid_view:",
            help="Volta para o painel com todos os casos. Os valores digitados ficam guardados.",
            on_click=_voltar_ao_painel,
        )
        st.caption(f"{area} › {caso.grupo}")
    ids = cat.GRUPOS[area][caso.grupo]
    if len(ids) > 1:
        st.session_state["assistente_modelo"] = caso.id
        st.pills(
            "Outros casos deste grupo",
            ids,
            format_func=lambda i: cat.CASOS[i].titulo,
            selection_mode="single",
            required=True,
            label_visibility="collapsed",
            help="Troque de caso sem voltar ao painel.",
            key="assistente_modelo",
            on_change=_ao_trocar_modelo,
        )
    st.subheader(caso.titulo)
    st.caption(caso.descricao)


def _desenho_do_caso(caso: Caso, resultado: Resultado | None) -> None:
    """O desenho feito com os números do cálculo. O croqui fica nos dados, com as medidas."""
    if resultado is not None and resultado.figuras:
        figura = resultado.figuras[0]
        mostrar_figura(figura)
    if caso.formula:
        st.latex(caso.formula)


# ---------------------------------------------------------------------------
# Medidas no desenho
# ---------------------------------------------------------------------------


def _valores_da_sessao(caso: Caso) -> dict[str, Any]:
    """O que vale agora, antes de os campos serem desenhados. Tabela: as últimas linhas."""
    valores: dict[str, Any] = caso.padroes()
    for campo in caso.campos:
        chave = chave_do_campo(caso.id, campo.chave)
        if campo.e_tabela:
            valores[campo.chave] = st.session_state.get(f"{chave}::ultimas", campo.padrao)
        elif chave in st.session_state:
            valores[campo.chave] = st.session_state[chave]
    return valores


def _gravar_na_tabela(caso: Caso, alvo: cd.Celula, valor: float) -> None:
    """A tabela renasce das linhas novas: a edição dela vale sobre uma base que ficou parada."""
    campo = next(c for c in caso.campos if c.chave == alvo.campo)
    chave = chave_do_campo(caso.id, alvo.campo)
    linhas = [dict(linha) for linha in st.session_state.get(f"{chave}::ultimas", campo.padrao)]
    linhas[alvo.linha][alvo.coluna] = valor
    st.session_state[f"{chave}::ultimas"] = linhas
    st.session_state.pop(chave, None)
    st.session_state.pop(f"{chave}::base", None)


def _ao_editar_cota(caso: Caso, chave_do_desenho: str) -> None:
    evento = getattr(st.session_state.get(chave_do_desenho), "edicao", None)
    if not evento:
        return
    cotas = cd.cotas_do_caso(caso, _valores_da_sessao(caso))
    indice = int(evento.get("indice", -1))
    if not 0 <= indice < len(cotas):
        return
    cota = cotas[indice]
    acao = evento.get("acao")
    if acao == "limite":
        _achar_limite(caso, chave_do_desenho, cota)
    elif acao == "grafico":
        estudo_ui.escolher_medida(caso, cota, abrir=True)
    else:
        st.session_state[f"{chave_do_desenho}::aviso"] = _mudar_medida(
            caso, cota, evento.get("valor")
        )


def _mudar_medida(caso: Caso, cota: cd.CotaViva, digitado: Any, origem: str = "") -> str:
    """Grava a medida com o antes e o depois, e devolve o motivo se o valor não servir."""
    valor, motivo = cd.valor_aceito(cota, digitado)
    if valor is None:
        return motivo
    pilha = st.session_state.setdefault(f"assistente_pilha::{caso.id}", [])
    pilha.append((cota.alvo, cota.letra, cota.valor, cota.unidade))
    del pilha[:-30]
    texto = f"{cota.letra}: {cd.numero(cota.valor)} → {cd.numero(valor)} {cota.unidade}".rstrip()
    _anotar_mudanca(caso, f"{texto} ({origem.lower()})" if origem else texto)
    _gravar_cota(caso, cota.alvo, valor)
    return ""


def _usar_valor(caso: Caso, cota: cd.CotaViva, valor: float, origem: str) -> None:
    """Um valor pronto do estudo vale como uma medida digitada: entra no Desfazer."""
    aviso = _mudar_medida(caso, cota, valor, origem)
    st.session_state[f"assistente_croqui::{caso.id}::aviso"] = aviso


def _achar_limite(caso: Caso, chave_do_desenho: str, cota: cd.CotaViva) -> None:
    """Guarda a resposta com os dados que a geraram: mudou um número, ela deixa de valer."""
    valores = _valores_da_sessao(caso)
    estudo = estudo_ui.estudo_de(caso, valores, cota)
    if estudo is None:
        return
    st.session_state[f"{chave_do_desenho}::limite"] = (
        estudo_ui.assinatura(valores),
        {**estudo.para_a_caixinha(), "indice": cota.indice},
    )
    estudo_ui.escolher_medida(caso, cota)


def _gravar_cota(caso: Caso, alvo: cd.Alvo, valor: float) -> None:
    if isinstance(alvo, cd.Celula):
        _gravar_na_tabela(caso, alvo, valor)
    else:
        st.session_state[chave_do_campo(caso.id, alvo)] = valor


def _anotar_mudanca(caso: Caso, texto: str) -> None:
    """Guarda as métricas de agora: a próxima rodada mostra o antes e o depois."""
    st.session_state[f"assistente_mudou::{caso.id}"] = (
        texto,
        st.session_state.get(f"assistente_metricas::{caso.id}", {}),
    )


def _desfazer_cota(caso: Caso) -> None:
    pilha = st.session_state.get(f"assistente_pilha::{caso.id}")
    if not pilha:
        return
    alvo, letra, valor, unidade = pilha.pop()
    _anotar_mudanca(caso, f"Desfeito: {letra} volta a {cd.numero(valor)} {unidade}".rstrip())
    _gravar_cota(caso, alvo, valor)


def _voltar_ao_exemplo(caso: Caso) -> None:
    for campo in caso.campos:
        chave = chave_do_campo(caso.id, campo.chave)
        for nome in (chave, f"{chave}::base", f"{chave}::ultimas"):
            st.session_state.pop(nome, None)
    for nome in ("material", "pilha", "mudou"):
        st.session_state.pop(f"assistente_{nome}::{caso.id}", None)
    st.session_state.pop(f"assistente_croqui::{caso.id}::limite", None)


def _o_que_mudou(caso: Caso, resultado: Resultado) -> None:
    """Depois de mexer numa medida: quanto o resultado andou, sem precisar comparar de cabeça."""
    anotado = st.session_state.get(f"assistente_mudou::{caso.id}")
    if not anotado:
        return
    texto, antes = anotado
    partes = [mudanca.texto() for mudanca in cd.mudancas(antes, resultado.metricas)]
    corpo = " · ".join(partes) if partes else "O resultado não mudou."
    st.info(f"**{texto}**  \n{corpo}", icon=":material/compare_arrows:")


def _desenho_com_medidas(caso: Caso) -> frozenset[str]:
    """Desenha o caso e diz quais campos já estão nele, para a lista ficar mais curta."""
    chave = f"assistente_croqui::{caso.id}"
    valores = _valores_da_sessao(caso)
    svg = _croqui(caso, valores)
    cotas = cd.cotas_do_caso(caso, valores)
    diagnostico = estudo_ui.diagnostico_de(caso, valores)
    if svg and cotas:
        limite = st.session_state.get(f"{chave}::limite")
        vale = limite is not None and limite[0] == estudo_ui.assinatura(valores)
        croqui_editavel(
            {
                "svg": cd.desenho_com_cotas(svg, cotas),
                "cotas": [cota.como_dicionario() for cota in cotas],
                "estudavel": bool(diagnostico.avaliacao.criterios),
                "manda": diagnostico.manda.medida.indice if diagnostico.manda else None,
                "estudo": limite[1] if vale else None,
            },
            key=chave,
            ao_editar=partial(_ao_editar_cota, caso, chave),
        )
    elif svg:
        mostrar_figura(svg, largura=520)
    aviso = st.session_state.get(f"{chave}::aviso")
    if aviso:
        st.warning(aviso, icon=":material/warning:")
    if svg and diagnostico.texto():
        st.caption(diagnostico.texto())
    with st.container(horizontal=True, vertical_alignment="center"):
        if cotas:
            st.caption("Clique numa medida para mudar. Enter confirma e Tab vai para a próxima.")
        if st.session_state.get(f"assistente_pilha::{caso.id}"):
            st.button(
                "Desfazer",
                key=f"assistente_desfazer::{caso.id}",
                icon=":material/undo:",
                on_click=_desfazer_cota,
                args=(caso,),
                help="Desfaz a última medida mudada no desenho.",
            )
        st.button(
            "Voltar ao exemplo",
            key=f"assistente_exemplo::{caso.id}",
            icon=":material/restart_alt:",
            on_click=_voltar_ao_exemplo,
            args=(caso,),
            help="Volta todos os dados deste caso aos números do exemplo.",
        )
    return frozenset(c.alvo for c in cotas if isinstance(c.alvo, str))


# ---------------------------------------------------------------------------
# Formulário
# ---------------------------------------------------------------------------


def _aplicar_material(caso: Caso) -> None:
    nome = st.session_state.get(f"assistente_material::{caso.id}")
    if not nome or nome == _SEM_MATERIAL:
        return
    dados = mat.obter_material(nome)
    for campo in caso.campos:
        origem = _CAMPOS_DE_MATERIAL.get(campo.chave)
        if origem == "sy_MPa" and float(dados["Sy_MPa"]) > 0:
            st.session_state[chave_do_campo(caso.id, campo.chave)] = float(dados["Sy_MPa"])
        elif origem == "sut_MPa" and float(dados["Sut_MPa"]) > 0:
            st.session_state[chave_do_campo(caso.id, campo.chave)] = float(dados["Sut_MPa"])


def _seletor_de_material(caso: Caso) -> None:
    if not any(campo.chave in _CAMPOS_DE_MATERIAL for campo in caso.campos):
        return
    try:
        nomes = mat.listar_nomes()
    except (FileNotFoundError, ValueError):
        return
    st.selectbox(
        "Preencher pelo material do catálogo",
        [_SEM_MATERIAL, *nomes],
        help=(
            "Copia a resistência do catálogo para os campos de material. São valores de "
            "referência: confirme no certificado antes de emitir o memorial."
        ),
        key=f"assistente_material::{caso.id}",
        on_change=_aplicar_material,
        args=(caso,),
    )


def _widget(caso: Caso, campo: Any) -> Any:
    chave = chave_do_campo(caso.id, campo.chave)
    rotulo = campo.rotulo_completo
    if isinstance(campo.padrao, bool):
        return st.toggle(
            rotulo, value=campo.padrao, help=campo.ajuda, key=chave, persist_state="session"
        )
    if isinstance(campo.padrao, str):
        opcoes = campo.lista_de_opcoes
        return st.selectbox(
            rotulo,
            opcoes,
            index=opcoes.index(campo.padrao) if campo.padrao in opcoes else 0,
            help=campo.ajuda,
            key=chave,
            persist_state="session",
        )
    inteiro = isinstance(campo.padrao, int)
    tipo = int if inteiro else float
    return st.number_input(
        rotulo,
        min_value=None if campo.minimo is None else tipo(campo.minimo),
        max_value=None if campo.maximo is None else tipo(campo.maximo),
        value=tipo(campo.padrao),
        step=tipo(campo.passo) if campo.passo else None,
        format="%d" if inteiro else "%g",
        help=campo.ajuda,
        key=chave,
        persist_state="session",
    )


def coluna_da_tabela(coluna: Coluna) -> Any:
    rotulo = coluna.rotulo_completo
    if coluna.opcoes:
        return st.column_config.SelectboxColumn(
            rotulo,
            options=list(coluna.opcoes),
            default=coluna.padrao,
            required=not coluna.opcional,
            help=coluna.ajuda,
            width="small",
        )
    if isinstance(coluna.padrao, str):
        return st.column_config.TextColumn(
            rotulo, help=coluna.ajuda, required=not coluna.opcional, width="small"
        )
    return st.column_config.NumberColumn(
        rotulo,
        width="small",
        min_value=coluna.minimo,
        max_value=coluna.maximo,
        default=None if coluna.opcional else coluna.padrao,
        format="%g",
        required=not coluna.opcional,
        help=coluna.ajuda,
    )


def quadro_da_tabela(campo: Campo, linhas: Any) -> pd.DataFrame:
    """As linhas com todas as colunas e o tipo certo: coluna toda vazia não pode virar texto."""
    quadro = pd.DataFrame(list(linhas), columns=[coluna.chave for coluna in campo.colunas])
    for coluna in campo.colunas:
        if not coluna.opcoes and not isinstance(coluna.padrao, str):
            quadro[coluna.chave] = pd.to_numeric(quadro[coluna.chave], errors="coerce").astype(
                "float64"
            )
    return quadro


def _tabela(caso: Caso, campo: Campo) -> list[dict[str, Any]]:
    """Campo em forma de tabela, com linhas que o usuário acrescenta e tira.

    A tabela guarda as edições como diferenças em relação à base, e por isso a base precisa ficar
    parada enquanto ela está na tela. Ao voltar de outro caso, a tabela renasce das últimas linhas.
    """
    chave = chave_do_campo(caso.id, campo.chave)
    base = f"{chave}::base"
    ultimas = f"{chave}::ultimas"
    if chave not in st.session_state or base not in st.session_state:
        linhas = st.session_state.get(ultimas, campo.padrao)
        st.session_state[base] = quadro_da_tabela(campo, linhas)
    if campo.rotulo != campo.secao:
        st.markdown(f"**{campo.rotulo_completo}**")
    st.caption(campo.ajuda)
    editado = st.data_editor(
        st.session_state[base],
        key=chave,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        placeholder="—",
        column_config={coluna.chave: coluna_da_tabela(coluna) for coluna in campo.colunas},
    )
    registros: list[dict[str, Any]] = editado.to_dict("records")
    st.session_state[ultimas] = registros
    return registros


def _lista_de_medidas(caso: Caso, no_desenho: frozenset[str], valores: dict[str, Any]) -> None:
    """As medidas do desenho também em campos, para quem prefere uma lista."""
    with st.expander("Medidas do desenho em lista", icon=":material/format_list_numbered:"):
        colunas: Any = None
        posicao = 0
        for campo in caso.campos:
            if campo.chave not in no_desenho:
                continue
            if colunas is None or posicao % 2 == 0:
                colunas = st.columns(2)
            with colunas[posicao % 2]:
                valores[campo.chave] = _widget(caso, campo)
            posicao += 1


def _trazer_secao(caso: Caso) -> None:
    """Salva a seção aberta na Desenhar seção e a escolhe neste caso, sem sair da página."""
    aviso = f"assistente_trazer::{caso.id}::aviso"
    st.session_state.pop(aviso, None)
    nome = str(st.session_state.get(NOME_DA_SECAO_ABERTA) or "").strip() or "Seção desenhada"
    existente = catalogo.listar_cadastrados().get(nome)
    if existente is not None and not existente.editavel:
        st.session_state[aviso] = (
            f"{nome} já é um perfil de referência do catálogo. Dê outro nome à seção em Desenhar "
            "seção."
        )
        return
    try:
        analise = sd.analisar(sd.partes_de_lista(st.session_state[PARTES_DA_SECAO_ABERTA]))
        catalogo.salvar_perfil(
            sd.perfil_da_secao(nome, analise),
            desenho=tuple(parte.como_dicionario() for parte in analise.partes),
        )
    except (sd.ErroDeSecao, catalogo.ErroDeCatalogo) as erro:
        st.session_state[aviso] = str(erro)
        return
    st.session_state[chave_do_campo(caso.id, "desenho")] = nome


def _importar_secao(caso: Caso) -> None:
    """A ponte com a prancheta: só aparece quando a seção do caso é uma seção desenhada."""
    with st.container(horizontal=True):
        if st.session_state.get(PARTES_DA_SECAO_ABERTA):
            st.button(
                "Trazer a seção aberta",
                key=f"assistente_trazer::{caso.id}",
                icon=":material/download:",
                on_click=_trazer_secao,
                args=(caso,),
                help="Salva a seção aberta na página Desenhar seção e a escolhe aqui.",
            )
        st.page_link(
            "app_pages/desenhar_secao.py",
            label="Abrir Desenhar seção",
            icon=":material/draw:",
            help="Desenhe ou altere a seção. Ela volta para cá pela lista de seções salvas.",
        )
    aviso = st.session_state.get(f"assistente_trazer::{caso.id}::aviso")
    if aviso:
        st.warning(aviso, icon=":material/warning:")


def formulario(caso: Caso, no_desenho: frozenset[str] = frozenset()) -> dict[str, Any]:
    """Os campos por seção, em duas colunas. Tabela ocupa a largura toda. Escondido fica no padrão.

    O que já está no desenho sai das seções e vai para uma lista recolhida, depois delas.
    """
    _seletor_de_material(caso)
    # Da sessão: um campo pode depender de outro que agora é desenhado mais adiante.
    valores: dict[str, Any] = _valores_da_sessao(caso)
    secoes: dict[str, list[Campo]] = {}
    for campo in caso.campos:
        if campo.chave not in no_desenho:
            secoes.setdefault(campo.secao, []).append(campo)
    for secao, campos in secoes.items():
        if not any(campo.visivel(valores) for campo in campos):
            continue
        with st.container(border=True):
            if secao and not (len(campos) == 1 and campos[0].rotulo == secao):
                st.markdown(f"**{secao}**")
            colunas: Any = None
            posicao = 0
            for campo in campos:
                if not campo.visivel(valores):
                    continue
                if campo.e_tabela:
                    valores[campo.chave] = _tabela(caso, campo)
                    colunas, posicao = None, 0
                    continue
                if colunas is None or posicao % 2 == 0:
                    colunas = st.columns(2)
                with colunas[posicao % 2]:
                    valores[campo.chave] = _widget(caso, campo)
                posicao += 1
            if valores.get("tipo_secao") == ev.DESENHADA and secao == "Seção":
                _importar_secao(caso)
    if no_desenho:
        _lista_de_medidas(caso, no_desenho, valores)
    return valores


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------


def _numero(valor: float, casas: int = 2) -> str:
    if math.isinf(valor):
        return "∞"
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", " ").replace(".", ",")


def _metrica(metrica: Metrica) -> None:
    """Número de destaque em cartão. O ``st.metric`` corta o texto em coluna estreita."""
    valor = metrica.valor
    texto = valor if isinstance(valor, str) else _numero(float(valor), metrica.casas)
    with st.container(border=True, height="stretch"):
        st.caption(metrica.rotulo)
        st.markdown(f"#### {texto} {metrica.unidade}".strip())


def _faixa_de_status(resultado: Resultado) -> None:
    texto = mv.decimal_ptbr(resultado.resumo)
    if resultado.status == "NÃO OK":
        st.error(texto, icon=":material/cancel:")
    elif resultado.status == "ALERTA":
        st.warning(texto, icon=":material/warning:")
    elif resultado.status == "OK":
        st.success(texto, icon=":material/check_circle:")
    else:
        st.info(texto, icon=":material/info:")


def _celula(valor: float | None, sufixo: str = "", *, casas: int | None = None) -> str:
    if valor is None or math.isnan(valor):
        return "—"
    if math.isinf(valor):
        return "∞"
    return f"{cd.numero(round(valor, casas) if casas is not None else valor)}{sufixo}"


def tabela_de_verificacoes(resultado: Resultado) -> None:
    if not resultado.verificacoes:
        return
    st.markdown("**Verificações**")
    linhas = tabela_verificacoes(ordenar_por_severidade(resultado.verificacoes))
    for linha in linhas:
        linha["Fórmula"] = mv.decimal_ptbr(linha["Fórmula"])
    # Texto, e não número: célula numérica vazia aparece como "None", e nem o Styler muda isso.
    for linha in linhas:
        linha["Solicitante"] = _celula(linha["Solicitante"])
        linha["Resistente"] = _celula(linha["Resistente"])
        linha["Aproveitamento"] = _celula(linha["Aproveitamento"], " %", casas=0)
    st.dataframe(
        pd.DataFrame(linhas),
        hide_index=True,
        width="stretch",
        column_config={"Resistente": "Limite"},
    )


def _grafico(grafico: Grafico) -> None:
    """Diagrama com o valor ao passar o mouse. A ordem dos pontos é a da peça, por causa dos saltos.

    ``order`` fica só na linha: numa área, ele faz de cada ponto uma marca separada, sem preenchimento.
    """
    tabela = pd.DataFrame(grafico.pontos, columns=["x", "y", "Curva"])
    tabela["ordem"] = range(len(tabela))
    varias = tabela["Curva"].nunique() > 1
    eixo_y = alt.Y("y:Q", title=grafico.rotulo_y, stack=None)
    base = alt.Chart(tabela).encode(
        x=alt.X(
            "x:Q",
            title=grafico.rotulo_x,
            scale=alt.Scale(nice=False),
            axis=alt.Axis(tickCount=8, labelFlush=False),
        ),
    )
    cor = grafico.cor or "#0B6E99"
    if varias:
        linha = base.mark_line(strokeWidth=2).encode(
            y=eixo_y,
            color=alt.Color("Curva:N", legend=alt.Legend(title=None, orient="top")),
            order="ordem:Q",
        )
    else:
        linha = base.mark_line(strokeWidth=2, color=cor).encode(y=eixo_y, order="ordem:Q")
    camadas = [linha]
    if grafico.area and not varias:
        camadas.insert(0, base.mark_area(opacity=0.18, color=cor).encode(y=eixo_y))
    if grafico.area:
        camadas.append(
            alt.Chart(pd.DataFrame({"zero": [0.0]}))
            .mark_rule(color="#94A3B8", strokeDash=[4, 4])
            .encode(y="zero:Q")
        )
    if grafico.destaques:
        destaques = pd.DataFrame(grafico.destaques, columns=["x", "y", "texto"])
        camadas.append(
            alt.Chart(destaques)
            .mark_point(filled=True, size=45, color=cor)
            .encode(x="x:Q", y="y:Q")
        )
        camadas.append(
            alt.Chart(destaques)
            .mark_text(dy=-11, fontSize=12, fontWeight=600, color="#172033")
            .encode(x="x:Q", y="y:Q", text="texto:N")
        )
    camadas.append(
        base.mark_circle(opacity=0, size=500).encode(
            y=eixo_y,
            tooltip=[
                alt.Tooltip("Curva:N", title="Curva"),
                alt.Tooltip("x:Q", title=grafico.rotulo_x, format=".3f"),
                alt.Tooltip("y:Q", title=grafico.rotulo_y, format=".3f"),
            ],
        )
    )
    titulo = alt.TitleParams(grafico.titulo, anchor="start", fontWeight=600)
    st.altair_chart(alt.layer(*camadas).properties(title=titulo, height=240), width="stretch")


def _pontos(resultado: Resultado) -> None:
    if not resultado.pontos:
        return
    st.markdown("**Tensões nos pontos avaliados**")
    critico = resultado.ponto_critico
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Ponto": p.nome,
                    "σx (MPa)": p.sigma_x,
                    "σy (MPa)": p.sigma_y,
                    "σz (MPa)": p.sigma_z,
                    "τxy (MPa)": p.tau_xy,
                    "von Mises (MPa)": p.von_mises,
                    "Crítico": "◀" if p is critico else "",
                }
                for p in resultado.pontos
            ]
        ),
        hide_index=True,
        width="stretch",
        column_config={
            coluna: st.column_config.NumberColumn(format="%.2f")
            for coluna in ("σx (MPa)", "σy (MPa)", "σz (MPa)", "τxy (MPa)", "von Mises (MPa)")
        },
    )
    if critico:
        figura = figura_dos_elementos(critico.sigma_x, critico.sigma_y, critico.tau_xy)
        mostrar_figura(figura, f"{critico.nome}. {figura.legenda}")


def abrir_caso_preenchido(destino: str, novos: dict[str, Any]) -> None:
    """Deixa o caso ``destino`` aberto, com estes valores nos campos."""
    alvo = cat.CASOS[destino]
    campos = {campo.chave: campo for campo in alvo.campos}
    for chave, valor in novos.items():
        campo = campos[chave]
        if not isinstance(campo.padrao, (bool, str)):
            valor = type(campo.padrao)(valor)
            if campo.minimo is not None:
                valor = max(valor, type(campo.padrao)(campo.minimo))
            if campo.maximo is not None:
                valor = min(valor, type(campo.padrao)(campo.maximo))
        st.session_state[chave_do_campo(destino, chave)] = valor
    _escolher(destino)


def _envios(resultado: Resultado) -> None:
    if not resultado.envios:
        return
    st.markdown("**Próximo passo**")
    colunas = st.columns(min(len(resultado.envios), 3))
    for indice, envio in enumerate(resultado.envios):
        colunas[indice % 3].button(
            envio.rotulo,
            icon=":material/arrow_forward:",
            width="stretch",
            key=f"assistente_envio_{indice}",
            on_click=abrir_caso_preenchido,
            args=(envio.destino, dict(envio.valores)),
            help=f"Abre o caso {cat.CASOS[envio.destino].titulo} já preenchido com estes valores.",
        )


def _estado_do_ponto(caso: Caso, ponto: Ponto) -> cargas.EstadoPlanoCalculado:
    return cargas.EstadoPlanoCalculado(
        ponto.sigma_x, ponto.sigma_y, ponto.tau_xy, f"{caso.titulo}: {ponto.nome}", ()
    )


def enviar_para_mohr(estado: cargas.EstadoPlanoCalculado, origem_id: str | None) -> None:
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


def _enviar_para_estatica(estado: cargas.EstadoPlanoCalculado, origem_id: str | None) -> None:
    st.session_state["estatica_sigma_x"] = estado.sigma_x
    st.session_state["estatica_sigma_y"] = estado.sigma_y
    st.session_state["estatica_tau_xy"] = estado.tau_xy
    st.session_state["estatica_origem_registro_id"] = origem_id
    st.switch_page("app_pages/analise_estatica.py")


def _destinos(caso: Caso, resultado: Resultado, origem_id: str | None) -> None:
    if not resultado.pontos and resultado.fadiga is None:
        return
    st.markdown("**Levar para outras análises**")
    if origem_id is None:
        st.caption(
            ":material/link_off: Este estado ainda não foi registrado no projeto. O repasse leva "
            "os valores, mas não uma origem rastreável."
        )
    critico = resultado.ponto_critico
    colunas = st.columns(3)
    if critico:
        if abs(critico.sigma_z) > 1e-9:
            st.caption(
                "O ponto crítico tem as três tensões. As outras análises recebem σx, σy e τxy; "
                "o von Mises completo é o desta página."
            )
        estado = _estado_do_ponto(caso, critico)
        if colunas[0].button(
            "Análise estática",
            icon=":material/analytics:",
            width="stretch",
            help="Leva o ponto crítico para a Análise estática.",
        ):
            _enviar_para_estatica(estado, origem_id)
        if colunas[1].button(
            "Círculo de Mohr",
            icon=":material/donut_large:",
            width="stretch",
            help="Leva o ponto crítico para o Círculo de Mohr.",
        ):
            enviar_para_mohr(estado, origem_id)
    if resultado.fadiga is not None and colunas[2].button(
        "Análise de fadiga",
        icon=":material/cycle:",
        width="stretch",
        help="Leva as tensões alternada e média nominais para a Análise de fadiga.",
    ):
        st.session_state["fadiga_sigma_alternada_nominal"] = resultado.fadiga[0]
        st.session_state["fadiga_sigma_media"] = resultado.fadiga[1]
        st.switch_page("app_pages/analise_fadiga.py")


def _registro(caso: Caso, valores: dict[str, Any], resultado: Resultado) -> dict[str, Any]:
    return construir_registro_tecnico(
        **dados_do_registro(caso, valores, resultado, modulo=MODULO, modulo_id=MODULO_ID)
    )


def _word(caso: Caso, valores: dict[str, Any], resultado: Resultado) -> None:
    projeto = obter_projeto_ativo()

    def gerar() -> bytes:
        return gerar_word_do_caso(caso, valores, resultado, projeto=projeto)

    st.download_button(
        "Gerar o Word deste caso",
        data=gerar,
        file_name=f"assistente_{caso.id[:30].replace(' ', '_')}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        icon=":material/description:",
        on_click="ignore",
        key=f"assistente_word_{caso.id}",
        help="Baixa um Word editável com os dados, as verificações e as hipóteses deste caso.",
    )


def _tabela_de_resultado(tabela: Any) -> None:
    st.markdown(f"**{tabela.titulo}**")
    quadro = pd.DataFrame(list(tabela.linhas))
    for coluna in quadro.select_dtypes("number").columns:
        if quadro[coluna].isna().any():  # vazia em coluna numérica apareceria como "None"
            quadro[coluna] = quadro[coluna].map(_celula)
    st.dataframe(
        quadro,
        hide_index=True,
        width="stretch",
        column_config={
            coluna: st.column_config.NumberColumn(format="%.4g")
            for coluna in quadro.select_dtypes("float").columns
        },
    )
    if tabela.legenda:
        st.caption(tabela.legenda)


def resposta(resultado: Resultado, *, por_linha: int = 2) -> None:
    """A resposta curta, ao lado dos dados: passou ou não, e os números que importam."""
    _faixa_de_status(resultado)
    for inicio in range(0, len(resultado.metricas), por_linha):
        colunas = st.columns(por_linha)
        fim = inicio + por_linha
        for coluna, metrica in zip(colunas, resultado.metricas[inicio:fim], strict=False):
            with coluna:
                _metrica(metrica)
    for texto in resultado.alertas:
        st.warning(mv.decimal_ptbr(texto), icon=":material/warning:")


def detalhes(caso: Caso, valores: dict[str, Any], resultado: Resultado) -> None:
    """O resto do resultado, na largura toda da página."""
    tabela_de_verificacoes(resultado)
    for grafico in resultado.graficos:
        with secao_protegida(f"Gráfico: {grafico.titulo}"):
            _grafico(grafico)
    for tabela in resultado.tabelas:
        _tabela_de_resultado(tabela)
    if len(resultado.figuras) > 1:
        colunas = st.columns(2)
        for coluna, figura in zip(colunas, resultado.figuras[1:], strict=False):
            mostrar_figura(figura, alvo=coluna)
    with secao_protegida("Pontos de tensão"):
        _pontos(resultado)

    with st.expander("Hipóteses e referências", icon=":material/fact_check:"):
        for hipotese in resultado.hipoteses:
            st.markdown(f"- {hipotese}")
        st.caption("Referências: " + "; ".join(resultado.referencias))

    fronteira_modelo(
        [
            "Soldas, contato real, tensões residuais e efeitos térmicos que o caso não cita.",
            "Peças e condições fora das hipóteses listadas acima.",
            "A confirmação das propriedades do material no certificado.",
        ]
    )
    _envios(resultado)
    with secao_protegida("Registro"):
        registro = _registro(caso, valores, resultado)
        botao_registrar_calculo(
            registro,
            key=f"registrar_cargas_{caso.id}",
            rotulo="Registrar no projeto",
            tipo="secondary",
        )
        _word(caso, valores, resultado)
        _destinos(caso, resultado, id_registro_existente(registro))


def tela_do_caso(caso: Caso) -> None:
    """Dados à esquerda e resposta à direita. Dado inválido vira mensagem no lugar da resposta."""
    if caso.id == "equilibrio_peca":
        # Este caso se preenche desenhando. A tela dele reaproveita as peças desta aqui.
        from components.equilibrio_ui import tela_do_equilibrio

        tela_do_equilibrio(caso)
        return
    barra_de_navegacao(caso)
    esquerda, direita = st.columns(2, gap="large")
    with esquerda:
        st.markdown("##### Dados")
        no_desenho = _desenho_com_medidas(caso)
        valores = formulario(caso, no_desenho)
    resultado: Resultado | None = None
    erro = ""
    try:
        resultado = calcular_caso(caso, valores)
    except (ValueError, ZeroDivisionError, OverflowError) as falha:
        erro = str(falha)
    with direita:
        st.markdown("##### Resposta")
        if erro:
            st.error(erro, icon=":material/error:")
        with st.container(border=True):
            _desenho_do_caso(caso, resultado)
        if resultado is not None:
            _o_que_mudou(caso, resultado)
            resposta(resultado)
    # Fora do resultado: com dado inválido, é justamente o estudo que mostra um valor que serve.
    with secao_protegida("Estudo da medida"):
        estudo_ui.painel_de_estudo(caso, valores, _usar_valor)
    if resultado is not None:
        detalhes(caso, valores, resultado)
        st.session_state[f"assistente_metricas::{caso.id}"] = cd.metricas_numericas(
            resultado.metricas
        )
