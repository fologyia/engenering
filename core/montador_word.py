"""O Word do Montador: os blocos, os dados, as fórmulas, o resultado e o que não passou.

Sem Streamlit. Segue o molde dos outros documentos do programa (:mod:`core.word_documento`). O desenho
dos blocos sai com Pillow, das mesmas posições da prancheta. As fórmulas vão como equação de verdade
do Word (OMML), e não como imagem: dá para editar e copiar no próprio documento. A tradução é feita
aqui, peça por peça, a partir da conta da sympy.
"""

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence
from typing import Any
from xml.sax.saxutils import escape

import sympy as sp
from docx.oxml import parse_xml
from PIL import Image, ImageDraw

from core import montador as mt
from core import montador_blocos as mb
from core.beam_charts import _fonte
from core.montador_funcoes import (
    AlturaDaChaveta,
    AtritoDarcy,
    CargaEquivalenteEsferas,
    CargaEquivalenteXY,
    CargaEstatica,
    FatorLewis,
    FatorSuperficie,
    FatorTamanho,
    InterferenciaMaxima,
    InterferenciaMinima,
    KtRessalto,
    LarguraDaChaveta,
    LimiteBase,
    RasgoDaChaveta,
    ResistenciaEmVida,
    SensibilidadeNeuber,
)
from core.montador_grandezas import Unidades
from core.word_documento import DocumentoWord

_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_LARGURA = 176
_ALTURA = 92
_MARGEM = 40
_ESCALA = 2
_AZUL = "#0B6BCB"
_CORES_DO_TOPO = {
    "g-secao": _AZUL,
    "g-resultado": _AZUL,
    "g-conjunto": _AZUL,
    "g-esforco": "#0B5F45",
    "g-origem": "#7A5316",
    "g-material": "#7A5316",
    "g-criterio": "#39404D",
}
_GREGAS = {
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "Delta": "Δ",
    "varepsilon": "ε",
    "eta": "η",
    "theta": "θ",
    "lambda": "λ",
    "mu": "μ",
    "nu": "ν",
    "rho": "ρ",
    "sigma": "σ",
    "tau": "τ",
    "phi": "φ",
    "omega": "ω",
}
_FUNCOES_DO_MONTADOR: tuple[tuple[type[sp.Function], str, str], ...] = (
    (LimiteBase, "S", "e'"),
    (FatorSuperficie, "k", "a"),
    (FatorTamanho, "k", "b"),
    (SensibilidadeNeuber, "q", ""),
    (KtRessalto, "K", "t"),
    (ResistenciaEmVida, "S", "f"),
    (AtritoDarcy, "f", ""),
    (LarguraDaChaveta, "b", "ch"),
    (AlturaDaChaveta, "h", "ch"),
    (RasgoDaChaveta, "t", "1"),
    (InterferenciaMinima, "δ", "mín"),
    (InterferenciaMaxima, "δ", "máx"),
    (CargaEquivalenteEsferas, "P", ""),
    (CargaEquivalenteXY, "P", ""),
    (CargaEstatica, "P", "0"),
    (FatorLewis, "Y", ""),
)
_NOMES_DE_FUNCAO = {
    sp.sin: "sen",
    sp.cos: "cos",
    sp.tan: "tg",
    sp.asin: "arcsen",
    sp.acos: "arccos",
    sp.atan: "arctg",
    sp.exp: "exp",
    sp.log: "ln",
}


# ---------------------------------------------------------------------------
# Equação do Word
# ---------------------------------------------------------------------------


def _texto(texto: str) -> str:
    return f'<m:r><m:t xml:space="preserve">{escape(texto)}</m:t></m:r>'


def _fracao(a: str, b: str) -> str:
    return f"<m:f><m:num>{a}</m:num><m:den>{b}</m:den></m:f>"


def _potencia(a: str, b: str) -> str:
    return f"<m:sSup><m:e>{a}</m:e><m:sup>{b}</m:sup></m:sSup>"


def _indice(a: str, b: str) -> str:
    return f"<m:sSub><m:e>{a}</m:e><m:sub>{b}</m:sub></m:sSub>"


def _parenteses(a: str) -> str:
    return f"<m:d><m:e>{a}</m:e></m:d>"


def _raiz(a: str, ordem: int) -> str:
    if ordem == 2:
        return f'<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/><m:e>{a}</m:e></m:rad>'
    return f"<m:rad><m:deg>{_texto(str(ordem))}</m:deg><m:e>{a}</m:e></m:rad>"


def _simbolo(nome: str) -> str:
    base, _, indice = nome.partition("_")
    base = _GREGAS.get(base, base)
    if not indice:
        return _texto(base)
    return _indice(_texto(base), _texto(indice.replace("_", " ")))


def _numero_da_conta(valor: sp.Expr) -> str:
    numero = float(valor)
    if numero == int(numero) and abs(numero) < 1e7:
        return str(int(numero))
    return f"{numero:.5g}".replace(".", ",")


def _com_parenteses(e: sp.Expr) -> str:
    return _parenteses(em_omml(e)) if e.is_Add or e.is_Mul else em_omml(e)


def _soma(e: sp.Expr) -> str:
    partes = []
    for i, termo in enumerate(sp.Add.make_args(e)):
        negativo = termo.could_extract_minus_sign()
        corpo = em_omml(-termo if negativo else termo)
        if i == 0:
            partes.append((_texto("−") if negativo else "") + corpo)
        else:
            partes.append(_texto(" − " if negativo else " + ") + corpo)
    return "".join(partes)


def _produto(e: sp.Expr) -> str:
    numerador, denominador = sp.fraction(e)
    if denominador != 1:
        return _fracao(em_omml(numerador), em_omml(denominador))
    if e.could_extract_minus_sign():
        return _texto("−") + em_omml(-e)
    pedacos = [
        _parenteses(em_omml(fator)) if fator.is_Add else em_omml(fator)
        for fator in sp.Mul.make_args(e)
    ]
    return _texto("·").join(pedacos)


def _elevado(e: sp.Expr) -> str:
    base, expoente = e.base, e.exp
    if expoente.is_Rational and expoente < 0:
        return _fracao(_texto("1"), em_omml(base**-expoente))
    if expoente.is_Rational and expoente.q > 1:
        dentro = base if expoente.p == 1 else base**expoente.p
        return _raiz(em_omml(dentro), int(expoente.q))
    return _potencia(_com_parenteses(base), em_omml(expoente))


def _funcao(e: sp.Expr) -> str:
    for classe, letra, indice in _FUNCOES_DO_MONTADOR:
        if isinstance(e, classe):
            return _indice(_texto(letra), _texto(indice)) if indice else _texto(letra)
    if isinstance(e, sp.Abs):
        return _texto("|") + em_omml(e.args[0]) + _texto("|")
    for classe, nome in _NOMES_DE_FUNCAO.items():
        if isinstance(e, classe):
            return _texto(nome) + _parenteses(em_omml(e.args[0]))
    return _texto(str(e))


def em_omml(e: sp.Expr) -> str:
    """A conta como equação do Word, sem o elemento de fora."""
    e = sp.sympify(e)
    if e.is_Symbol:
        return _simbolo(e.name)
    if e == sp.pi:
        return _texto("π")
    if e.is_number and not e.is_Mul and not e.is_Add and not e.is_Pow:
        return _texto(_numero_da_conta(e))
    if e.is_Add:
        return _soma(e)
    if e.is_Mul:
        return _produto(e)
    if e.is_Pow:
        return _elevado(e)
    return _funcao(e)


def _equacao(documento: DocumentoWord, partes: str) -> None:
    paragrafo = documento.doc.add_paragraph()
    paragrafo._p.append(parse_xml(f'<m:oMath xmlns:m="{_M}">{partes}</m:oMath>'))


# ---------------------------------------------------------------------------
# Desenho dos blocos
# ---------------------------------------------------------------------------


def _numero(valor: float | None, casas: int = 4) -> str:
    if valor is None:
        return "—"
    if 1e4 <= abs(valor) < 1e12:
        return f"{valor:,.0f}".replace(",", ".")
    return f"{valor:.{casas}g}".replace(".", ",")


def _com_unidade(valor: float, dimensao: str, u: Unidades) -> str:
    return f"{_numero(valor / u.fator(dimensao))} {u.rotulo(dimensao)}".strip()


def _nome_do_no(no: Mapping[str, Any]) -> tuple[str, str, str]:
    """Nome, categoria e cor do bloco."""
    if no.get("tipo") == mt.CONJUNTO:
        return str(no.get("nome")), "CONJUNTO", _CORES_DO_TOPO["g-conjunto"]
    bloco = mb.POR_CHAVE.get(str(no.get("tipo")))
    if bloco is None:
        return str(no.get("tipo")), "", _AZUL
    classe = mb.CLASSE_DO_GRUPO.get(bloco.grupo, "g-secao")
    return bloco.nome, mb.CATEGORIA_DO_GRUPO.get(bloco.grupo, ""), _CORES_DO_TOPO[classe]


def _caminho_do_fio(
    a: tuple[float, float], b: tuple[float, float], fundo: float
) -> list[tuple[float, float]]:
    """Curva suave para a frente. Para trás, o fio desce pelo vão entre as linhas."""
    if b[0] < a[0] + 30.0:
        direita, esquerda = a[0] + 17.0, b[0] - 17.0
        return [a, (direita, a[1]), (direita, fundo), (esquerda, fundo), (esquerda, b[1]), b]
    meio = max(36.0, (b[0] - a[0]) / 2.0)
    p1, p2 = (a[0] + meio, a[1]), (b[0] - meio, b[1])
    pontos = []
    for i in range(33):
        t = i / 32.0
        u = 1.0 - t
        pontos.append(
            (
                u**3 * a[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * b[0],
                u**3 * a[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * b[1],
            )
        )
    return pontos


def figura_da_montagem(dados: Mapping[str, Any], faces: Mapping[str, Mapping[str, str]]) -> bytes:
    """Os blocos e os fios nas posições da prancheta, em PNG."""
    nos = [n for n in dados.get("nos") or () if isinstance(n, Mapping)]
    if not nos:
        return b""
    x0 = min(float(n.get("x", 0)) for n in nos) - _MARGEM
    y0 = min(float(n.get("y", 0)) for n in nos) - _MARGEM
    largura = max(float(n.get("x", 0)) for n in nos) - x0 + _LARGURA + _MARGEM
    altura = max(float(n.get("y", 0)) for n in nos) - y0 + _ALTURA + _MARGEM
    imagem = Image.new("RGB", (int(largura * _ESCALA), int(altura * _ESCALA)), "white")
    desenho = ImageDraw.Draw(imagem)

    def tela(x: float, y: float) -> tuple[float, float]:
        return (x - x0) * _ESCALA, (y - y0) * _ESCALA

    por_id = {str(n.get("id")): n for n in nos}
    for fio in dados.get("fios") or ():
        de, para = por_id.get(str(fio.get("de"))), por_id.get(str(fio.get("para")))
        if de is None or para is None:
            continue
        a = (float(de.get("x", 0)) + _LARGURA, float(de.get("y", 0)) + _ALTURA / 2.0)
        b = (float(para.get("x", 0)), float(para.get("y", 0)) + _ALTURA / 2.0)
        fundo = max(float(de.get("y", 0)), float(para.get("y", 0))) - 12.0
        if float(para.get("y", 0)) <= float(de.get("y", 0)):
            fundo = float(de.get("y", 0)) + _ALTURA + 14.0
        pontos = [tela(*p) for p in _caminho_do_fio(a, b, fundo)]
        desenho.line(pontos, fill="#64748B", width=2 * _ESCALA - 1)
    fonte_faixa, fonte_nome = _fonte(8 * _ESCALA), _fonte(13 * _ESCALA)
    fonte_linha = _fonte(9 * _ESCALA)
    for no in nos:
        x, y = float(no.get("x", 0)), float(no.get("y", 0))
        nome, categoria, cor = _nome_do_no(no)
        canto = tela(x, y)
        fim = tela(x + _LARGURA, y + _ALTURA)
        desenho.rounded_rectangle(
            (*canto, *fim), radius=9 * _ESCALA, fill="white", outline="#CBD5E1", width=_ESCALA
        )
        desenho.line((*tela(x + 7, y + 1), *tela(x + _LARGURA - 7, y + 1)), fill=cor, width=5)
        desenho.text(tela(x + 12, y + 8), categoria, fill="#475569", font=fonte_faixa)
        desenho.line((*tela(x, y + 24), *tela(x + _LARGURA, y + 24)), fill="#E2E8F0", width=2)
        desenho.text(tela(x + 12, y + 30), nome[:26], fill="#172033", font=fonte_nome)
        face = faces.get(str(no.get("id")), {})
        linha = y + 50.0
        for chave, cor_do_texto in (("a", "#334155"), ("b", _AZUL)):
            texto = str(face.get(chave) or "")
            if texto:
                curto = texto if len(texto) <= 30 else f"{texto[:29]}…"
                desenho.text(tela(x + 12, linha), curto, fill=cor_do_texto, font=fonte_linha)
                linha += 15.0
    saida = io.BytesIO()
    imagem.save(saida, format="PNG")
    return saida.getvalue()


# ---------------------------------------------------------------------------
# O documento
# ---------------------------------------------------------------------------


def _quadro_de_dados(
    montagem: mt.Montagem,
    valores: Mapping[str, float | None],
    origens: Mapping[str, str],
    alvo: str,
    u: Unidades,
) -> list[list[str]]:
    linhas = []
    for item in montagem.grandezas:
        if item.chave == alvo:
            continue
        valor = valores.get(item.chave)
        texto = "—" if valor is None else _com_unidade(valor, item.dimensao, u)
        linhas.append([item.texto, item.nome, texto, origens.get(item.chave, "—")])
    return linhas


def gerar_word(
    titulo: str,
    dados: Mapping[str, Any],
    resposta: mt.Resposta,
    u: Unidades,
    valores: Mapping[str, float | None],
    origens: Mapping[str, str],
    faces: Mapping[str, Mapping[str, str]],
    resumo: str,
    hipoteses: Sequence[str],
    projeto: Mapping[str, Any] | None = None,
) -> bytes:
    """O documento da conta aberta na tela. ``resumo`` é a frase da resposta, como h ≥ 37,95 mm."""
    documento = DocumentoWord()
    documento.titulo(titulo, 1)
    nome_do_projeto = (projeto or {}).get("nome") or (projeto or {}).get("titulo")
    if nome_do_projeto:
        documento.paragrafo(f"Projeto: {nome_do_projeto}")
    montagem = resposta.montagem
    alvo = resposta.alvo

    documento.titulo("Resultado", 2)
    documento.paragrafo(resumo, negrito=True)
    if resposta.manda is not None:
        documento.paragrafo(f"Quem manda: {resposta.manda.condicao.nome}.")
        forma = resposta.manda.formula
        if forma is not None:
            _equacao(documento, _simbolo(alvo.chave) + _texto(" = ") + em_omml(forma.expressao))

    figura = figura_da_montagem(dados, faces)
    if figura:
        documento.titulo("Montagem", 2)
        documento.figura(figura, "Os blocos da montagem e os fios entre eles.", largura_mm=240.0)

    if montagem is not None:
        documento.titulo("Dados", 2)
        documento.tabela(
            ("Letra", "Grandeza", "Valor", "De onde veio"),
            _quadro_de_dados(montagem, valores, origens, alvo.chave, u),
            (30.0, 90.0, 60.0, 93.0),
        )

    conferidas = resposta.conferencia_adotada or resposta.conferencia
    documento.titulo("Condições", 2)
    if resposta.conferencia_adotada and resposta.adotado is not None:
        texto = _com_unidade(resposta.adotado, alvo.dimensao, u)
        documento.paragrafo(f"Conferidas com o valor adotado: {alvo.texto} = {texto}.")
    documento.tabela(
        ("Condição", "Valor", "Limite", "Uso (%)", "Situação"),
        [
            [
                linha.nome,
                _numero(linha.esquerda),
                _numero(linha.direita),
                _numero(linha.uso * 100.0, 3),
                "Fecha" if linha.igualdade else "Passa" if linha.uso <= 1.0 + 1e-9 else "Não passa",
            ]
            for linha in conferidas
        ],
        (120.0, 40.0, 40.0, 33.0, 40.0),
    )

    documento.titulo("Passo a passo", 2)
    for item in resposta.isoladas:
        condicao = item.condicao
        documento.paragrafo(condicao.nome, negrito=True)
        sinal = " = " if condicao.igualdade else " ≤ "
        _equacao(
            documento,
            em_omml(mt.limpar(condicao.esquerda, condicao.positiva))
            + _texto(sinal)
            + em_omml(condicao.direita),
        )
        if item.independente:
            documento.paragrafo(f"Essa condição não tem {alvo.texto}.")
        elif item.formula is not None:
            _equacao(
                documento,
                _simbolo(alvo.chave) + _texto(" = ") + em_omml(item.formula.expressao),
            )
        else:
            documento.paragrafo("Sem forma fechada simples: a raiz veio da conta numérica.")

    documento.titulo("Hipóteses", 2)
    documento.itens(list(hipoteses))

    nao_passaram = [linha for linha in conferidas if not linha.igualdade and linha.uso > 1.0 + 1e-9]
    if nao_passaram:
        documento.titulo("O que não passou", 2)
        documento.itens([f"{x.nome}: uso de {_numero(x.uso * 100.0, 3)} %." for x in nao_passaram])
    return documento.bytes()
