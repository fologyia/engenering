"""Tela da Análise sobre o desenho: o desenho de fundo, as marcas e a análise de cada uma.

O desenho entra por arquivo (imagem, PDF ou DXF), colado na prancheta (Ctrl+V) ou como um esboço
salvo da Desenhar seção. Cada marca é uma parte do desenho, ligada a um modelo do Montador de
fórmulas; a conta é a do Montador (``core.analise_desenho.calcular``), e a etiqueta da marca volta com
o resultado. "Abrir no Montador" leva a marca para lá, com os mesmos números.

As medidas de uma marca podem vir do desenho: o botão de régua ao lado do campo pede duas pontas (ou
a borda de um círculo) na prancheta. Com um esboço de fundo, o campo pode ficar ligado a uma letra
ou a uma medida com nome do esboço, e "Achar pelo esboço" varia a letra até a marca deixar de passar.
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
ESBOCO = "ad_esboco"  # a seção salva escolhida como fundo
LETRAS = "ad_esboco_letras"  # os valores de agora das letras dele
PEDIDO = "ad_pedido"  # o campo que espera uma medida do desenho
PEDIDOS = "ad_pedidos"
LIMITES = "ad_limites"  # o que "Achar pelo esboço" respondeu, por marca
CONFERIR = "Conferir a medida"
LIMITE = "Achar o limite"
DIGITADO = "digitado"
SEM_ESBOCO = "Nenhum"
_ICONES = {
    ad.PASSOU: ":material/check_circle:",
    ad.NAO_PASSOU: ":material/cancel:",
    ad.LIMITE: ":material/straighten:",
    ad.FALTA: ":material/pending:",
    ad.ERRO: ":material/error:",
    ad.ANOTACAO: ":material/sticky_note_2:",
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
    eventos = {
        "on_edicao_change": _ao_editar,
        "on_colar_change": _ao_colar,
        "on_medida_change": _ao_medir,
    }
    try:
        return _PRANCHETA(data=dados, key=CHAVE, **eventos)
    except ValueError as erro:
        if "is not registered" not in str(erro):
            raise
        _PRANCHETA = _registrar()
        return _PRANCHETA(data=dados, key=CHAVE, **eventos)


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
    estado.setdefault(LETRAS, {})
    estado.setdefault(PEDIDO, None)
    estado.setdefault(PEDIDOS, 0)
    estado.setdefault(LIMITES, {})


def _marcas() -> list[ad.Marca]:
    return [ad.marca_de_dicionario(m) for m in st.session_state[MARCAS]]


def _guardar(marcas: list[ad.Marca]) -> None:
    st.session_state[MARCAS] = [m.como_dicionario() for m in marcas]


def _fundo() -> dict[str, Any] | None:
    return st.session_state.get(FUNDO)


def _de_esboco() -> bool:
    fundo = _fundo()
    return bool(fundo and fundo.get("tipo") == "esboco")


def _medidas_do_fundo() -> dict[str, dict[str, Any]]:
    fundo = _fundo()
    if not fundo or fundo.get("tipo") != "esboco":
        return {}
    return {str(m["nome"]): m for m in fundo.get("medidas") or ()}


def _trocar_fundo(fundo: ad.Fundo) -> None:
    estado = st.session_state
    estado[FUNDO] = fundo.como_dicionario()
    estado[ESCALA] = 1.0 if fundo.tipo in ("dxf", "esboco") else None
    estado[AJUSTE] += 1
    estado[VERSAO] += 1_000_000  # a escala nova vai para a prancheta
    estado[PEDIDO] = None
    estado[LIMITES] = {}
    if fundo.tipo != "esboco":
        estado[ESBOCO] = SEM_ESBOCO


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


def _ao_escolher_esboco() -> None:
    estado = st.session_state
    estado[ERRO] = ""
    secao = estado.get(ESBOCO)
    if not secao or secao == SEM_ESBOCO:
        return
    try:
        fundo = ad.fundo_de_esboco(secao)
    except ad.ErroDeDesenho as erro:
        estado[ERRO] = str(erro)
        return
    letras = {str(m["nome"]): float(m["valor"]) for m in fundo.medidas if m["letra"]}
    estado[LETRAS] = letras
    for letra, valor in letras.items():
        estado[f"ad_letra_{letra}"] = valor
    _trocar_fundo(fundo)


def _redesenhar_esboco(letras: dict[str, float]) -> bool:
    """O esboço de fundo com as letras novas. Falso (e a mensagem) se ele não existe assim."""
    estado = st.session_state
    fundo = _fundo()
    if not fundo or fundo.get("tipo") != "esboco":
        return False
    try:
        novo = ad.fundo_de_esboco(str(fundo["secao"]), letras)
    except ad.ErroDeDesenho as erro:
        estado[ERRO] = str(erro)
        return False
    estado[ERRO] = ""
    estado[LETRAS] = dict(letras)
    estado[FUNDO] = novo.como_dicionario()
    estado[LIMITES] = {}
    return True


def _ao_mudar_letra(letra: str) -> None:
    estado = st.session_state
    valor = estado.get(f"ad_letra_{letra}")
    anterior = dict(estado[LETRAS])
    if valor is None or not valor > 0 or not _redesenhar_esboco({**anterior, letra: float(valor)}):
        estado[f"ad_letra_{letra}"] = anterior.get(letra)


def _usar_no_esboco(letra: str, valor: float) -> None:
    estado = st.session_state
    if _redesenhar_esboco({**estado[LETRAS], letra: valor}):
        estado[f"ad_letra_{letra}"] = valor


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


def _ao_medir() -> None:
    """A medida que a prancheta pegou para o campo que pediu (ou o pedido cancelado)."""
    estado = st.session_state
    evento = getattr(estado.get(CHAVE), "medida", None)
    pedido = estado.get(PEDIDO)
    estado[PEDIDO] = None
    if not isinstance(evento, dict) or evento.get("cancelar") or not pedido:
        return
    valor = evento.get("valor")
    if not isinstance(valor, (int, float)) or not valor > 0:
        return
    id_, chave = str(evento.get("id")), str(evento.get("chave"))

    def mudar(marca: ad.Marca) -> None:
        marca.valores[chave] = float(valor)
        marca.ligacoes.pop(chave, None)

    _mudar(id_, mudar)
    _nova_revisao(id_)  # o campo mostra o número novo


def _pedir_medida(id_: str, chave: str, texto: str) -> None:
    estado = st.session_state
    estado[PEDIDOS] += 1
    estado[PEDIDO] = {"n": estado[PEDIDOS], "id": id_, "chave": chave, "texto": texto}
    estado[SELECIONADA] = id_


def _mudar(id_: str, mudanca: Any) -> None:
    marcas = _marcas()
    for marca in marcas:
        if marca.id == id_:
            mudanca(marca)
    _guardar(marcas)


def _revisao(id_: str) -> int:
    return int(st.session_state[REVISOES].get(id_, 0))


def _nova_revisao(id_: str) -> None:
    st.session_state[REVISOES] = {**st.session_state[REVISOES], id_: _revisao(id_) + 1}


def _ao_trocar_analise(id_: str) -> None:
    analise = st.session_state.get(f"ad_{id_}_{_revisao(id_)}_analise")
    if analise not in ad.ANALISES:
        return
    marcas = [ad.trocar_analise(m, analise) if m.id == id_ else m for m in _marcas()]
    _guardar(marcas)
    st.session_state[LIMITES].pop(id_, None)
    _nova_revisao(id_)


def _ao_mudar_nome(id_: str) -> None:
    nome = str(st.session_state.get(f"ad_{id_}_nome") or "").strip()

    def mudar(marca: ad.Marca) -> None:
        marca.nome = nome

    _mudar(id_, mudar)


def _ao_mudar_nota(id_: str) -> None:
    nota = str(st.session_state.get(f"ad_{id_}_{_revisao(id_)}_nota") or "")

    def mudar(marca: ad.Marca) -> None:
        marca.nota = nota

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


def _ao_ligar(id_: str, chave: str) -> None:
    medida = st.session_state.get(f"ad_{id_}_{_revisao(id_)}_{chave}_lig")

    def mudar(marca: ad.Marca) -> None:
        if not medida or medida == DIGITADO:
            marca.ligacoes.pop(chave, None)
        else:
            marca.ligacoes[chave] = str(medida)

    _mudar(id_, mudar)
    st.session_state[LIMITES].pop(id_, None)


def _achar_pelo_esboco(id_: str) -> None:
    estado = st.session_state
    letra = estado.get(f"ad_{id_}_{_revisao(id_)}_letra_busca")
    marca = next((m for m in _marcas() if m.id == id_), None)
    fundo = _fundo()
    if marca is None or not letra or not fundo:
        return
    try:
        limite = ad.limite_pelo_esboco(marca, str(fundo["secao"]), estado[LETRAS], str(letra))
        resposta = {
            "letra": limite.letra,
            "valor": limite.valor,
            "sentido": limite.sentido,
            "texto": limite.texto,
        }
    except ad.ErroDeDesenho as erro:
        resposta = {"letra": str(letra), "valor": None, "sentido": "", "texto": str(erro)}
    estado[LIMITES] = {**estado[LIMITES], id_: resposta}


def _apagar(id_: str) -> None:
    _guardar([m for m in _marcas() if m.id != id_])
    st.session_state[SELECIONADA] = None
    st.session_state[VERSAO] += 1_000_000


def _apagar_tudo() -> None:
    _guardar([])
    st.session_state[SELECIONADA] = None
    st.session_state[VERSAO] += 1_000_000


def _abrir_no_montador(id_: str) -> None:
    marca = ad.valores_da_marca(next(m for m in _marcas() if m.id == id_), _fundo())
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
    nome = marca.nome or ("nota" if marca.analise == ad.NOTA else marca.analise.split(":")[0])
    return f"{numero} · {nome} — {resultado.resumo}"


def _entrada() -> None:
    estado = st.session_state
    colunas = st.columns([3, 2, 1, 1], vertical_alignment="bottom")
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
    salvos = ad.esbocos_salvos()
    estado.setdefault(ESBOCO, SEM_ESBOCO)
    if estado[ESBOCO] not in (SEM_ESBOCO, *salvos):
        estado[ESBOCO] = SEM_ESBOCO
    colunas[1].selectbox(
        "Ou um esboço salvo",
        (SEM_ESBOCO, *salvos),
        key=ESBOCO,
        on_change=_ao_escolher_esboco,
        help=(
            "Uma seção salva na Desenhar seção, com as cotas e as letras: as medidas da marca podem "
            "vir dele (o Ø do furo, a distância até a borda), e mudam junto com as letras."
        ),
    )
    paginas = int(estado.get(PAGINAS) or 0)
    if paginas > 1 and not _de_esboco():
        colunas[2].number_input(
            "Página do PDF",
            min_value=1,
            max_value=paginas,
            step=1,
            key=PAGINA,
            on_change=_ao_trocar_pagina,
            help="Qual página do PDF vai de fundo.",
        )
    colunas[3].button(
        "Apagar as marcas",
        icon=":material/delete:",
        on_click=_apagar_tudo,
        disabled=not estado[MARCAS],
        key="ad_apagar_tudo",
        width="stretch",
        help="Tira todas as marcas do desenho (o desenho fica).",
    )
    if estado.get(ERRO):
        st.error(estado[ERRO], icon=":material/error:")


def _letras_do_esboco() -> None:
    """As letras do esboço de fundo: mudar uma refaz o desenho e as medidas ligadas às marcas."""
    medidas = _medidas_do_fundo()
    letras = [m for m in medidas.values() if m["letra"]]
    com_nome = [m for m in medidas.values() if not m["letra"]]
    if not letras and not com_nome:
        st.caption("Este esboço não tem letras nem medidas com nome: as marcas usam os números.")
        return
    estado = st.session_state
    if letras:
        colunas = st.columns(min(max(len(letras), 1), 6))
        for i, m in enumerate(letras):
            chave = f"ad_letra_{m['nome']}"
            estado.setdefault(chave, float(m["valor"]))
            colunas[i % len(colunas)].number_input(
                f"{m['nome']} (mm)",
                min_value=0.0,
                format="%g",
                key=chave,
                on_change=_ao_mudar_letra,
                args=(str(m["nome"]),),
                help="Letra do esboço: mudar refaz o desenho, e as marcas ligadas a ela mudam junto.",
            )
    if com_nome:
        texto = ", ".join(f"{m['nome']} = {ad.numero(float(m['valor']), 4)} mm" for m in com_nome)
        st.caption(f"Medidas com nome do esboço (saem do desenho): {texto}.")


def _campos(numero: int, marca: ad.Marca, efetiva: ad.Marca) -> None:
    montagem = ad.montagem_da_analise(marca.analise)
    rev = _revisao(marca.id)
    fundo = _fundo()
    medidas = _medidas_do_fundo()
    pedido = st.session_state.get(PEDIDO)
    grandezas = [g for g in montagem.grandezas if g.chave != marca.alvo or marca.conferir]
    colunas = st.columns(4)
    for indice, grandeza in enumerate(grandezas):
        coluna = colunas[indice % 4]
        medivel = fundo is not None and grandeza.dimensao in ad.DE_COMPRIMENTO
        ligada = marca.ligacoes.get(grandeza.chave) if medidas else None
        valor = efetiva.valores.get(grandeza.chave)
        rotulo = ad.UNIDADES.rotulo(grandeza.dimensao)
        principal = grandeza.chave == marca.alvo
        campo, regua = (
            coluna.columns([4, 1], vertical_alignment="bottom") if medivel else (coluna, None)
        )
        mostrado = (
            None
            if valor is None
            else float(f"{ad.UNIDADES.da_base(grandeza.dimensao, valor):.10g}")
        )
        # Ligado, o número vem do esboço: o campo leva o valor no nome para mostrar o de agora.
        chave = f"ad_{marca.id}_{rev}_{grandeza.chave}" + (f"_lig{mostrado}" if ligada else "")
        campo.number_input(
            f"{grandeza.texto}" + (f" ({rotulo})" if rotulo else "") + (" ◀" if principal else ""),
            value=mostrado,
            format="%g",
            key=chave,
            disabled=bool(ligada),
            on_change=_ao_mudar_valor,
            args=(marca.id, grandeza.chave, grandeza.dimensao),
            help=(
                f"{grandeza.nome}. {grandeza.ajuda}"
                + (" É a medida que esta marca confere." if principal else "")
                + (f" Vem do esboço: {ligada}." if ligada else "")
            ),
        )
        if regua is not None:
            esperando = bool(
                pedido and pedido["id"] == marca.id and pedido["chave"] == grandeza.chave
            )
            regua.button(
                "",
                icon=":material/hourglass_top:" if esperando else ":material/straighten:",
                key=f"ad_{marca.id}_{grandeza.chave}_medir",
                on_click=_pedir_medida,
                args=(marca.id, grandeza.chave, f"{grandeza.texto} da marca {numero}"),
                disabled=bool(ligada),
                help=(
                    "Pegar no desenho: clique nas duas pontas na prancheta (no DXF ou no esboço, um "
                    "clique na borda de um círculo dá o diâmetro). Esc cancela."
                ),
            )
        if medivel and medidas:
            opcoes = (DIGITADO, *medidas)
            coluna.selectbox(
                f"{grandeza.texto} do esboço",
                opcoes,
                index=opcoes.index(ligada) if ligada in opcoes else 0,
                key=f"ad_{marca.id}_{rev}_{grandeza.chave}_lig",
                on_change=_ao_ligar,
                args=(marca.id, grandeza.chave),
                label_visibility="collapsed",
                help="Ligar este número a uma letra ou a uma medida com nome do esboço de fundo.",
            )


def _busca_pelo_esboco(marca: ad.Marca) -> None:
    """Varia uma letra do esboço (ligada à marca) e diz até onde ela vai com a marca passando."""
    medidas = _medidas_do_fundo()
    letras = sorted({m for m in marca.ligacoes.values() if medidas.get(m, {}).get("letra")})
    if not letras:
        return
    rev = _revisao(marca.id)
    linha = st.columns([2, 2, 3], vertical_alignment="bottom")
    linha[0].selectbox(
        "Letra do esboço",
        letras,
        key=f"ad_{marca.id}_{rev}_letra_busca",
        help="A letra que vai variar: o esboço é refeito com cada valor dela.",
    )
    linha[1].button(
        "Achar pelo esboço",
        icon=":material/manage_search:",
        key=f"ad_{marca.id}_achar",
        on_click=_achar_pelo_esboco,
        args=(marca.id,),
        width="stretch",
        help=(
            "Refaz o esboço com outros valores da letra (na faixa de teste dela) e acha até onde ela "
            "vai com a marca passando: o menor furo, a menor espessura..."
        ),
    )
    limite = st.session_state[LIMITES].get(marca.id)
    if not limite:
        return
    st.info(limite["texto"], icon=":material/manage_search:")
    if limite["valor"] is not None:
        seguro = ad.redondo(float(limite["valor"]), limite["sentido"])
        st.button(
            f"Usar {limite['letra']} = {ad.numero(seguro, 4)} mm no esboço",
            icon=":material/check:",
            key=f"ad_{marca.id}_usar",
            on_click=_usar_no_esboco,
            args=(limite["letra"], seguro),
            help="Põe o valor (arredondado para o lado seguro) na letra do esboço de fundo.",
        )


def _painel(
    numero: int, marca: ad.Marca, efetiva: ad.Marca, resultado: ad.ResultadoDaMarca
) -> None:
    rev = _revisao(marca.id)
    aberto = st.session_state.get(SELECIONADA) == marca.id
    nota = marca.analise == ad.NOTA
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
                "O modelo do Montador de fórmulas que vale para esta parte, ou só uma nota (apoia na "
                "viga, transmite a força). Trocar recomeça com os números de exemplo dele."
            ),
        )
        if nota:
            st.text_area(
                "Nota",
                value=marca.nota,
                key=f"ad_{marca.id}_{rev}_nota",
                on_change=_ao_mudar_nota,
                args=(marca.id,),
                placeholder="apoia na viga V-3; transmite a força ao pino de baixo...",
                help="Vai no desenho (resumida) e no memorial. Não entra em conta nenhuma.",
            )
        else:
            linha[2].segmented_control(
                "O que fazer",
                (CONFERIR, LIMITE),
                default=CONFERIR if marca.conferir else LIMITE,
                key=f"ad_{marca.id}_{rev}_modo",
                on_change=_ao_mudar_modo,
                args=(marca.id,),
                help=(
                    "Conferir: com a medida (◀) preenchida, diz se passa e quanto usa. Achar o "
                    "limite: deixa a medida livre e diz até onde ela pode ir."
                ),
            )
            _campos(numero, marca, efetiva)
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
                            "Condição": item.nome,
                            "Solicitação": ad.numero(item.solicitacao, 4),
                            "Limite": ad.numero(item.limite, 4),
                            "Uso (%)": round(item.uso * 100.0, 1),
                        }
                        for item in sorted(resultado.linhas, key=lambda x: -x.uso)
                    ],
                    hide_index=True,
                    width="stretch",
                )
            for alerta in resultado.alertas:
                st.warning(alerta, icon=":material/warning:")
            if _de_esboco():
                _busca_pelo_esboco(marca)
        botoes = st.columns(2)
        if not nota:
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
    fundo = _fundo()
    marcas = _marcas()
    efetivas = [ad.valores_da_marca(m, fundo) for m in marcas]
    resultados = [_resultado_da(m) for m in efetivas]
    _prancheta(
        {
            "fundo": fundo,
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
            "pedido": st.session_state[PEDIDO],
        }
    )
    if _de_esboco():
        _letras_do_esboco()
    if not marcas:
        st.info(
            "Use Marcar (M) e clique em cada parte do desenho que vai ser analisada: um pino, uma "
            "chapa, um eixo, ou só uma nota. No DXF e no esboço, a marca gruda no furo ou na linha "
            "mais perto. A análise de cada marca aparece aqui, com o resultado no desenho.",
            icon=":material/ads_click:",
        )
        return
    contagem = {
        s: sum(r.situacao == s for r in resultados) for s in (ad.PASSOU, ad.NAO_PASSOU, ad.ANOTACAO)
    }
    st.markdown(
        f"**{len(marcas)} {'marca' if len(marcas) == 1 else 'marcas'}** · "
        f"{contagem[ad.PASSOU]} passou · {contagem[ad.NAO_PASSOU]} não passou"
        + (f" · {contagem[ad.ANOTACAO]} só nota" if contagem[ad.ANOTACAO] else "")
    )
    for numero, (marca, efetiva, resultado) in enumerate(
        zip(marcas, efetivas, resultados, strict=True), start=1
    ):
        _painel(numero, marca, efetiva, resultado)
    st.download_button(
        "Gerar o Word",
        data=lambda: ad.word_da_analise(fundo, efetivas, resultados, st.session_state[ESCALA]),
        file_name="analise_sobre_o_desenho.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        icon=":material/description:",
        on_click="ignore",
        key="ad_word",
        help="O desenho com as marcas numeradas e a conta de cada uma.",
    )
