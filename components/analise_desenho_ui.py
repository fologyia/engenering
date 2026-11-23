"""Tela da Análise sobre o desenho: o desenho de fundo, as marcas e a análise de cada uma.

O desenho entra por arquivo (imagem, PDF ou DXF) ou colado na prancheta (Ctrl+V). Cada marca é uma
parte do desenho, ligada a um modelo do Montador de fórmulas; a conta é a do Montador
(``core.analise_desenho.calcular``), e a etiqueta da marca volta com o resultado. "Abrir no
Montador" leva a marca para lá, com os mesmos números.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from components import montador_ui
from core import analise_desenho as ad
from core.montador_modelos import PARTE_SOLIDOS

_PASTA = Path(__file__).parent / "prancheta_analise"
_NOME = "mecanica_toolkit_analise_desenho"

FUNDO = "ad_fundo"
MARCAS = "ad_marcas"
ESCALA = "ad_escala"
SELECIONADA = "ad_selecionada"
VERSAO = "ad_versao"
AJUSTE = "ad_ajuste"
REVISOES = "ad_revisoes"
ARQUIVO = "ad_arquivo"
PAGINA = "ad_pagina"
PAGINAS = "ad_paginas"
ERRO = "ad_erro"
CHAVE = "ad_prancheta"
CONFERIR = "Conferir a medida"
LIMITE = "Achar o limite"
_ICONES = {
    ad.PASSOU: ":material/check_circle:",
    ad.NAO_PASSOU: ":material/cancel:",
    ad.LIMITE: ":material/straighten:",
    ad.FALTA: ":material/pending:",
    ad.ERRO: ":material/error:",
}


def _registrar() -> Any:
    return st.components.v2.component(
        _NOME,
        html=(_PASTA / "analise.html").read_text(encoding="utf-8"),
        css=(_PASTA / "analise.css").read_text(encoding="utf-8"),
        js=(_PASTA / "analise.js").read_text(encoding="utf-8"),
    )


_PRANCHETA = _registrar()


def _prancheta(dados: dict[str, Any]) -> Any:
    global _PRANCHETA
    try:
        return _PRANCHETA(
            data=dados, key=CHAVE, on_edicao_change=_ao_editar, on_colar_change=_ao_colar
        )
    except ValueError as erro:
        if "is not registered" not in str(erro):
            raise
        _PRANCHETA = _registrar()
        return _PRANCHETA(
            data=dados, key=CHAVE, on_edicao_change=_ao_editar, on_colar_change=_ao_colar
        )


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------


def _iniciar() -> None:
    estado = st.session_state
    estado.setdefault(FUNDO, None)
    estado.setdefault(MARCAS, [])
    estado.setdefault(ESCALA, None)
    estado.setdefault(SELECIONADA, None)
    estado.setdefault(VERSAO, 0)
    estado.setdefault(AJUSTE, 0)
    estado.setdefault(REVISOES, {})
    estado.setdefault(ERRO, "")


def _marcas() -> list[ad.Marca]:
    return [ad.marca_de_dicionario(m) for m in st.session_state[MARCAS]]


def _guardar(marcas: list[ad.Marca]) -> None:
    st.session_state[MARCAS] = [m.como_dicionario() for m in marcas]


def _trocar_fundo(fundo: ad.Fundo) -> None:
    estado = st.session_state
    estado[FUNDO] = fundo.como_dicionario()
    estado[ESCALA] = 1.0 if fundo.tipo == "dxf" else None
    estado[AJUSTE] += 1
    estado[VERSAO] += 1_000_000  # a escala nova vai para a prancheta


def _ao_escolher_arquivo() -> None:
    estado = st.session_state
    estado[ERRO] = ""
    arquivo = estado.get(ARQUIVO)
    if arquivo is None:
        return
    dados = arquivo.getvalue()
    try:
        if arquivo.name.lower().endswith(".pdf"):
            estado[PAGINAS] = ad.paginas_do_pdf(dados)
            estado[PAGINA] = 1
        else:
            estado[PAGINAS] = 0
        _trocar_fundo(ad.fundo_do_arquivo(arquivo.name, dados, int(estado.get(PAGINA) or 1)))
    except ad.ErroDeDesenho as erro:
        estado[ERRO] = str(erro)


def _ao_trocar_pagina() -> None:
    estado = st.session_state
    arquivo = estado.get(ARQUIVO)
    if arquivo is None:
        return
    try:
        _trocar_fundo(ad.fundo_de_pdf(arquivo.name, arquivo.getvalue(), int(estado[PAGINA])))
    except ad.ErroDeDesenho as erro:
        estado[ERRO] = str(erro)


def _ao_colar() -> None:
    evento = getattr(st.session_state.get(CHAVE), "colar", None)
    if not isinstance(evento, dict) or not isinstance(evento.get("imagem"), str):
        return
    try:
        _trocar_fundo(ad.fundo_colado(evento["imagem"]))
        st.session_state[ERRO] = ""
    except ad.ErroDeDesenho as erro:
        st.session_state[ERRO] = str(erro)


def _ao_editar() -> None:
    """A prancheta mandou as marcas como estão: posições, novas, apagadas, a escolhida e a escala."""
    evento = getattr(st.session_state.get(CHAVE), "edicao", None)
    if not isinstance(evento, dict):
        return
    estado = st.session_state
    atuais = {m.id: m for m in _marcas()}
    novas: list[ad.Marca] = []
    for bruta in evento.get("marcas") or []:
        id_ = str(bruta.get("id"))
        x, y = float(bruta.get("x", 0.0)), float(bruta.get("y", 0.0))
        marca = atuais.get(id_) or ad.marca_nova(id_, x, y)
        marca.x, marca.y = x, y
        novas.append(marca)
    _guardar(novas)
    estado[SELECIONADA] = evento.get("selecionada")
    escala = evento.get("escala")
    estado[ESCALA] = float(escala) if isinstance(escala, (int, float)) and escala > 0 else None
    estado[VERSAO] = int(evento.get("versao", estado[VERSAO]))


def _mudar(id_: str, mudanca: Any) -> None:
    marcas = _marcas()
    for marca in marcas:
        if marca.id == id_:
            mudanca(marca)
    _guardar(marcas)


def _revisao(id_: str) -> int:
    return int(st.session_state[REVISOES].get(id_, 0))


def _ao_trocar_analise(id_: str) -> None:
    analise = st.session_state.get(f"ad_{id_}_{_revisao(id_)}_analise")
    if analise not in ad.ANALISES:
        return
    marcas = [ad.trocar_analise(m, analise) if m.id == id_ else m for m in _marcas()]
    _guardar(marcas)
    st.session_state[REVISOES] = {**st.session_state[REVISOES], id_: _revisao(id_) + 1}


def _ao_mudar_nome(id_: str) -> None:
    nome = str(st.session_state.get(f"ad_{id_}_nome") or "").strip()

    def mudar(marca: ad.Marca) -> None:
        marca.nome = nome

    _mudar(id_, mudar)


def _ao_mudar_modo(id_: str) -> None:
    modo = st.session_state.get(f"ad_{id_}_{_revisao(id_)}_modo")

    def mudar(marca: ad.Marca) -> None:
        marca.conferir = modo != LIMITE

    _mudar(id_, mudar)


def _ao_mudar_valor(id_: str, chave: str, dimensao: str) -> None:
    valor = st.session_state.get(f"ad_{id_}_{_revisao(id_)}_{chave}")

    def mudar(marca: ad.Marca) -> None:
        if valor is None:
            marca.valores.pop(chave, None)
        else:
            marca.valores[chave] = ad.UNIDADES.para_base(dimensao, float(valor))

    _mudar(id_, mudar)


def _apagar(id_: str) -> None:
    _guardar([m for m in _marcas() if m.id != id_])
    st.session_state[SELECIONADA] = None
    st.session_state[VERSAO] += 1_000_000


def _apagar_tudo() -> None:
    _guardar([])
    st.session_state[SELECIONADA] = None
    st.session_state[VERSAO] += 1_000_000


def _abrir_no_montador(id_: str) -> None:
    marca = next(m for m in _marcas() if m.id == id_)
    adotado = marca.valores.get(marca.alvo) if marca.conferir else None
    valores = {k: v for k, v in marca.valores.items() if k != marca.alvo}
    montador_ui.abrir_com_valores(PARTE_SOLIDOS, marca.analise, valores, marca.alvo, adotado)
    st.session_state["ad_ir_ao_montador"] = True


@st.cache_data(max_entries=256, show_spinner=False)
def _resultado(impressao: str) -> ad.ResultadoDaMarca:
    return ad.calcular(ad.marca_de_dicionario(json.loads(impressao)))


def _resultado_da(marca: ad.Marca) -> ad.ResultadoDaMarca:
    return _resultado(json.dumps(marca.como_dicionario(), sort_keys=True))


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------


def _rotulo(numero: int, marca: ad.Marca, resultado: ad.ResultadoDaMarca) -> str:
    nome = marca.nome or marca.analise.split(":")[0]
    return f"{numero} · {nome} — {resultado.resumo}"


def _entrada() -> None:
    colunas = st.columns([3, 1, 1], vertical_alignment="bottom")
    colunas[0].file_uploader(
        "Desenho",
        type=["png", "jpg", "jpeg", "pdf", "dxf", "dwg"],
        key=ARQUIVO,
        on_change=_ao_escolher_arquivo,
        help=(
            "Imagem (PNG, JPG), PDF (uma página de cada vez) ou DXF (já vem em mm). Também dá para "
            "colar um print: clique na prancheta e use Ctrl+V."
        ),
    )
    paginas = int(st.session_state.get(PAGINAS) or 0)
    if paginas > 1:
        colunas[1].number_input(
            "Página do PDF",
            min_value=1,
            max_value=paginas,
            step=1,
            key=PAGINA,
            on_change=_ao_trocar_pagina,
            help="Qual página do PDF vai de fundo.",
        )
    colunas[2].button(
        "Apagar as marcas",
        icon=":material/delete:",
        on_click=_apagar_tudo,
        disabled=not st.session_state[MARCAS],
        key="ad_apagar_tudo",
        width="stretch",
        help="Tira todas as marcas do desenho (o desenho fica).",
    )
    if st.session_state.get(ERRO):
        st.error(st.session_state[ERRO], icon=":material/error:")


def _campos(marca: ad.Marca) -> None:
    montagem = ad.montagem_da_analise(marca.analise)
    rev = _revisao(marca.id)
    grandezas = [g for g in montagem.grandezas if g.chave != marca.alvo or marca.conferir]
    colunas = st.columns(4)
    for indice, grandeza in enumerate(grandezas):
        valor = marca.valores.get(grandeza.chave)
        rotulo = ad.UNIDADES.rotulo(grandeza.dimensao)
        principal = grandeza.chave == marca.alvo
        colunas[indice % 4].number_input(
            f"{grandeza.texto}" + (f" ({rotulo})" if rotulo else "") + (" ◀" if principal else ""),
            value=None
            if valor is None
            else float(f"{ad.UNIDADES.da_base(grandeza.dimensao, valor):.10g}"),
            format="%g",
            key=f"ad_{marca.id}_{rev}_{grandeza.chave}",
            on_change=_ao_mudar_valor,
            args=(marca.id, grandeza.chave, grandeza.dimensao),
            help=(
                f"{grandeza.nome}. {grandeza.ajuda}"
                + (" É a medida que esta marca confere." if principal else "")
            ),
        )


def _painel(numero: int, marca: ad.Marca, resultado: ad.ResultadoDaMarca) -> None:
    rev = _revisao(marca.id)
    aberto = st.session_state.get(SELECIONADA) == marca.id
    with st.expander(
        _rotulo(numero, marca, resultado), icon=_ICONES.get(resultado.situacao), expanded=aberto
    ):
        linha = st.columns([2, 3, 2], vertical_alignment="bottom")
        linha[0].text_input(
            "Nome da parte",
            value=marca.nome,
            key=f"ad_{marca.id}_nome",
            on_change=_ao_mudar_nome,
            args=(marca.id,),
            placeholder="pino da articulação, olhal...",
            help="Como esta parte aparece na etiqueta do desenho e no memorial.",
        )
        linha[1].selectbox(
            "Análise do Montador",
            ad.ANALISES,
            index=ad.ANALISES.index(marca.analise),
            key=f"ad_{marca.id}_{rev}_analise",
            on_change=_ao_trocar_analise,
            args=(marca.id,),
            help=(
                "O modelo do Montador de fórmulas que vale para esta parte. Trocar recomeça com os "
                "números de exemplo dele."
            ),
        )
        linha[2].segmented_control(
            "O que fazer",
            (CONFERIR, LIMITE),
            default=CONFERIR if marca.conferir else LIMITE,
            key=f"ad_{marca.id}_{rev}_modo",
            on_change=_ao_mudar_modo,
            args=(marca.id,),
            help=(
                "Conferir: com a medida (◀) preenchida, diz se passa e quanto usa. Achar o limite: "
                "deixa a medida livre e diz até onde ela pode ir."
            ),
        )
        _campos(marca)
        mostrar = {
            ad.PASSOU: st.success,
            ad.NAO_PASSOU: st.error,
            ad.LIMITE: st.info,
        }.get(resultado.situacao, st.warning)
        mostrar(resultado.texto, icon=_ICONES.get(resultado.situacao))
        if resultado.linhas:
            st.dataframe(
                [
                    {
                        "Condição": linha.nome,
                        "Solicitação": ad.numero(linha.solicitacao, 4),
                        "Limite": ad.numero(linha.limite, 4),
                        "Uso (%)": round(linha.uso * 100.0, 1),
                    }
                    for linha in sorted(resultado.linhas, key=lambda x: -x.uso)
                ],
                hide_index=True,
                width="stretch",
            )
        for alerta in resultado.alertas:
            st.warning(alerta, icon=":material/warning:")
        botoes = st.columns(2)
        botoes[0].button(
            "Abrir no Montador",
            icon=":material/function:",
            key=f"ad_{marca.id}_montador",
            on_click=_abrir_no_montador,
            args=(marca.id,),
            width="stretch",
            help="Leva esta análise ao Montador de fórmulas, com os mesmos números.",
        )
        botoes[1].button(
            "Apagar esta marca",
            icon=":material/delete:",
            key=f"ad_{marca.id}_apagar",
            on_click=_apagar,
            args=(marca.id,),
            width="stretch",
            help="Tira a marca do desenho.",
        )


def tela() -> None:
    _iniciar()
    if st.session_state.pop("ad_ir_ao_montador", False):
        st.switch_page("app_pages/montador_formulas.py")
    _entrada()
    marcas = _marcas()
    resultados = [_resultado_da(m) for m in marcas]
    _prancheta(
        {
            "fundo": st.session_state[FUNDO],
            "escala": st.session_state[ESCALA],
            "marcas": [
                {
                    "id": m.id,
                    "x": m.x,
                    "y": m.y,
                    "numero": i + 1,
                    "rotulo": _rotulo(i + 1, m, r),
                    "situacao": r.situacao,
                }
                for i, (m, r) in enumerate(zip(marcas, resultados, strict=True))
            ],
            "selecionada": st.session_state[SELECIONADA],
            "versao": st.session_state[VERSAO],
            "ajustar": st.session_state[AJUSTE],
        }
    )
    if not marcas:
        st.info(
            "Use Marcar (M) e clique em cada parte do desenho que vai ser analisada: um pino, uma "
            "chapa, um eixo. A análise de cada marca aparece aqui, com o resultado no desenho.",
            icon=":material/ads_click:",
        )
        return
    resumo = {s: sum(r.situacao == s for r in resultados) for s in (ad.PASSOU, ad.NAO_PASSOU)}
    st.markdown(
        f"**{len(marcas)} {'marca' if len(marcas) == 1 else 'marcas'}** · "
        f"{resumo[ad.PASSOU]} passou · {resumo[ad.NAO_PASSOU]} não passou"
    )
    for numero, (marca, resultado) in enumerate(zip(marcas, resultados, strict=True), start=1):
        _painel(numero, marca, resultado)
    st.download_button(
        "Gerar o Word",
        data=lambda: ad.word_da_analise(
            st.session_state[FUNDO], marcas, resultados, st.session_state[ESCALA]
        ),
        file_name="analise_sobre_o_desenho.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        icon=":material/description:",
        on_click="ignore",
        key="ad_word",
        help="O desenho com as marcas numeradas e a conta de cada uma.",
    )
