"""A montagem em Excel, com fórmulas vivas: muda um dado na planilha, e a conta acompanha.

Cada letra vira uma célula com nome (``v_S_y``), e cada condição vira uma linha com os dois lados e o
uso. Quem está sendo pedido entra como valor adotado, que a pessoa pode mudar. Fator de atrito não tem
fórmula direta em Excel: na planilha ele vai por Swamee-Jain, que fica a cerca de 1 % de Colebrook, e
a planilha avisa. A tradução é feita aqui, peça por peça, porque em Excel −x^2 é (−x)², ao contrário
da matemática: todo número negativo vai entre parênteses.

Sem Streamlit.
"""

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence
from typing import Any

import sympy as sp
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.workbook.defined_name import DefinedName

from core import montador as mt
from core import montador_grandezas as g
from core.montador_funcoes import (
    DA_BIBLIOTECA,
    MATERIAIS_DE_FADIGA,
    TABELADAS,
    AtritoDarcy,
    CargaEquivalenteXY,
    CargaEstatica,
    FatorSuperficie,
    FatorTamanho,
    LimiteBase,
    ResistenciaEmVida,
    SensibilidadeNeuber,
    TensaoCritica,
)
from core.montador_grandezas import Unidades

_ABA = "Calculo"
_PREFIXO = "v_"
_CABECALHO = PatternFill("solid", fgColor="24577A")
_ENTRADA = PatternFill("solid", fgColor="FFF3C4")
_BRANCO = Font(bold=True, color="FFFFFF")
_NEGRITO = Font(bold=True)
_AVISO_DO_ATRITO = (
    "O fator de atrito na planilha vai por Swamee-Jain, a cerca de 1 % de Colebrook, que é o que o "
    "programa usa: a conta da planilha pode diferir um pouco do programa."
)
_AVISO_DA_COOLPROP = (
    "As propriedades do fluido vêm da CoolProp, que o Excel não tem: na planilha ficam com o valor "
    "calculado pelo programa, na temperatura e na pressão da conta."
)
_AVISO_DO_KT = (
    "K_t de ressalto, as medidas da chaveta da DIN 6885, a interferência da NBR 6158 e o X e Y do "
    "rolamento vêm de curva ou de tabela: na planilha ficam com o valor calculado pelo programa."
)


class SemFormula(ValueError):
    """Esta parte não tem tradução para Excel."""


def nome_da_celula(chave: str) -> str:
    """Com prefixo: em Excel, R, C e nomes como K1 não servem para nomear uma célula."""
    return _PREFIXO + "".join(letra if letra.isalnum() else "_" for letra in chave)


def _numero(valor: sp.Expr) -> str:
    numero = float(valor)
    texto = str(int(numero)) if numero == int(numero) and abs(numero) < 1e15 else repr(numero)
    return f"({texto})" if numero < 0.0 else texto


def em_excel(expressao: sp.Expr) -> str:
    """A conta em sintaxe de Excel. Levanta ``SemFormula`` no que não tem tradução."""
    if expressao.is_Symbol:
        return nome_da_celula(expressao.name)
    if expressao == sp.pi:
        return "PI()"
    if expressao.is_Atom:
        return _numero(expressao)
    if expressao.is_Add:
        return "(" + "+".join(em_excel(a) for a in expressao.args) + ")"
    if expressao.is_Mul:
        return "(" + "*".join(em_excel(a) for a in expressao.args) + ")"
    if expressao.is_Pow:
        base, expoente = expressao.base, expressao.exp
        if expoente == sp.Rational(1, 2):
            return f"SQRT({em_excel(base)})"
        return f"({em_excel(base)})^({em_excel(expoente)})"
    return _funcao(expressao)


def _funcao(e: sp.Expr) -> str:
    a = [em_excel(x) for x in e.args]
    simples = {
        sp.sin: "SIN",
        sp.cos: "COS",
        sp.tan: "TAN",
        sp.asin: "ASIN",
        sp.acos: "ACOS",
        sp.atan: "ATAN",
        sp.exp: "EXP",
        sp.log: "LN",
        sp.Abs: "ABS",
    }
    for classe, nome in simples.items():
        if isinstance(e, classe):
            return f"{nome}({a[0]})"
    if isinstance(e, sp.Min):
        return f"MIN({','.join(a)})"
    if isinstance(e, sp.Max):
        return f"MAX({','.join(a)})"
    if isinstance(e, AtritoDarcy):
        re, relativa = a
        turbulento = f"0.25/(LOG10({relativa}/3.7+5.74/({re})^0.9))^2"
        return f"IF({re}<2300,64/({re}),{turbulento})"
    if isinstance(e, LimiteBase):
        return _limite_base(a[0], int(e.args[1]))
    if isinstance(e, FatorSuperficie):
        return f"MIN(1,{a[1]}*({a[0]})^{a[2]})"
    if isinstance(e, FatorTamanho):
        d = a[0]
        return f"IF({d}<2.79,1,IF({d}<=51,1.24*({d})^(-0.107),1.51*(MIN({d},254))^(-0.157)))"
    if isinstance(e, SensibilidadeNeuber):
        return _neuber(a[0], a[1], bool(e.args[2]))
    if isinstance(e, ResistenciaEmVida):
        s, se, n = a
        return f"({s})*(({n})/1000)^(LOG10(({se})/({s}))/3)"
    if isinstance(e, CargaEquivalenteXY):
        radial, axial, x, y = a
        return f"MAX({radial},{x}*{radial}+{y}*{axial})"
    if isinstance(e, CargaEstatica):
        radial, axial = a
        return f"MAX({radial},0.6*{radial}+0.5*{axial})"
    if isinstance(e, TensaoCritica):
        # Euler acima da esbeltez de transição π·√(2E/S_y); Johnson abaixo.
        esbeltez, sy, modulo = a
        euler = f"PI()^2*{modulo}/({esbeltez})^2"
        johnson = f"{sy}*(1-{sy}*({esbeltez})^2/(4*PI()^2*{modulo}))"
        return f"IF({esbeltez}>=PI()*SQRT(2*{modulo}/{sy}),{euler},{johnson})"
    if isinstance(e, TABELADAS):
        raise SemFormula(type(e).__name__)
    raise SemFormula(type(e).__name__)


def _limite_base(sut: str, indice: int) -> str:
    material = MATERIAIS_DE_FADIGA[indice]
    fator, teto, limite = {
        "aco": (0.5, 700.0, 1400.0),
        "ferro_fundido": (0.4, 160.0, 400.0),
        "aluminio": (0.4, 130.0, 330.0),
        "cobre": (0.4, 100.0, 280.0),
    }[material]
    return f"IF({sut}<{limite},{fator}*{sut},{teto})"


def _neuber(sut: str, raio: str, torcao: bool) -> str:
    s = f"(MAX(50,MIN(250,({sut})/6.895)))"
    if torcao:
        raiz = f"(0.190-2.51E-3*{s}+1.35E-5*{s}^2-2.67E-8*{s}^3)"
    else:
        raiz = f"(0.246-3.08E-3*{s}+1.51E-5*{s}^2-2.67E-8*{s}^3)"
    return f"1/(1+{raiz}/SQRT(({raio})/25.4))"


def _com_numeros_no_que_falta(expressao: sp.Expr, numeros: Mapping[sp.Symbol, sp.Float]) -> sp.Expr:
    """O que vem de curva, de tabela ou da CoolProp não tem fórmula no Excel: entra o valor que o
    programa calculou."""
    return expressao.replace(
        lambda e: isinstance(e, (*TABELADAS, *DA_BIBLIOTECA)),
        lambda e: sp.Float(float(sp.N(e.subs(numeros)))),
    )


def _titulos(aba: Any, linha: int, titulos: Sequence[str]) -> None:
    for coluna, titulo in enumerate(titulos, start=1):
        celula = aba.cell(linha, coluna, titulo)
        celula.fill = _CABECALHO
        celula.font = _BRANCO


def gerar_planilha(
    titulo: str,
    montagem: mt.Montagem,
    resposta: mt.Resposta,
    u: Unidades,
    origens: Mapping[str, str],
) -> bytes:
    """A planilha da montagem. Precisa de uma resposta com todos os valores preenchidos."""
    livro = Workbook()
    aba = livro.active
    aba.title = _ABA
    aba["A1"] = titulo
    aba["A1"].font = Font(bold=True, size=13)
    aba["A2"] = (
        "As células amarelas são os dados: mude na unidade da coluna C, e a conta acompanha. A "
        "coluna E traz o valor na base que as fórmulas usam."
    )
    linha = 4
    _titulos(aba, linha, ("Letra", "Grandeza", "Valor", "Unidade", "Na base", "De onde veio"))
    linha += 1
    # As letras do meio entram com o número que a conta achou: na planilha, são dados.
    valores = {**dict(resposta.do_meio), **dict(resposta.valores_usados)}
    alvo = resposta.alvo
    adotado = resposta.adotado if resposta.adotado is not None else resposta.valor
    if adotado is not None:
        valores[alvo.chave] = adotado
    conta = resposta.montagem or montagem
    usadas = {s.name for c in conta.condicoes for s in c.letras}
    for item in conta.grandezas:
        if item.chave not in usadas or item.chave not in valores:
            continue
        fator = u.fator(item.dimensao)
        deslocamento = u.deslocamento(item.dimensao)
        aba.cell(linha, 1, item.texto)
        aba.cell(linha, 2, item.nome)
        celula = aba.cell(linha, 3, u.da_base(item.dimensao, valores[item.chave]))
        celula.fill = _ENTRADA
        aba.cell(linha, 4, u.rotulo(item.dimensao))
        # °C para K soma depois de multiplicar: a planilha faz a mesma conta da tela.
        soma = f"+{deslocamento!r}" if deslocamento else ""
        aba.cell(linha, 5, f"=C{linha}*{fator!r}{soma}")
        origem = "Resposta do programa" if item.chave == alvo.chave else origens.get(item.chave, "")
        aba.cell(linha, 6, origem)
        nome = nome_da_celula(item.chave)
        livro.defined_names[nome] = DefinedName(nome, attr_text=f"'{_ABA}'!$E${linha}")
        linha += 1
    linha += 1
    aba.cell(linha, 1, "Condições").font = _NEGRITO
    linha += 1
    _titulos(aba, linha, ("Condição", "Esquerda", "Limite", "Uso", "Situação", ""))
    linha += 1
    numeros = {g.simbolo_de(k): sp.Float(v) for k, v in valores.items()}
    avisos: list[str] = []
    for item_condicao in conta.condicoes:
        esquerda = item_condicao.esquerda
        direita = item_condicao.direita
        if esquerda.has(AtritoDarcy) or direita.has(AtritoDarcy):
            avisos.append(_AVISO_DO_ATRITO)
        if esquerda.has(*TABELADAS) or direita.has(*TABELADAS):
            avisos.append(_AVISO_DO_KT)
        if esquerda.has(*DA_BIBLIOTECA) or direita.has(*DA_BIBLIOTECA):
            avisos.append(_AVISO_DA_COOLPROP)
        aba.cell(linha, 1, item_condicao.nome)
        aba.cell(linha, 2, "=" + em_excel(_com_numeros_no_que_falta(esquerda, numeros)))
        aba.cell(linha, 3, "=" + em_excel(_com_numeros_no_que_falta(direita, numeros)))
        aba.cell(linha, 4, f"=B{linha}/C{linha}").number_format = "0.0%"
        if item_condicao.igualdade:
            aba.cell(linha, 5, f'=IF(ABS(D{linha}-1)<=0.001,"Fecha","Não fecha")')
        else:
            aba.cell(linha, 5, f'=IF(D{linha}<=1,"Passa","Não passa")')
        linha += 1
    linha += 1
    aba.cell(linha, 1, f"{alvo.texto} é a letra pedida: o valor na tabela é o que saiu da conta.")
    if resposta.manda is not None and resposta.manda.formula is not None:
        linha += 1
        expressao = _com_numeros_no_que_falta(resposta.manda.formula.expressao, numeros)
        aba.cell(linha, 1, f"{alvo.texto} pela condição que manda (na base)")
        aba.cell(linha, 2, "=" + em_excel(expressao))
    for aviso in dict.fromkeys(avisos):
        linha += 1
        aba.cell(linha, 1, aviso)
    aba.column_dimensions["A"].width = 38
    aba.column_dimensions["B"].width = 30
    for coluna in "CDEF":
        aba.column_dimensions[coluna].width = 16
    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()
