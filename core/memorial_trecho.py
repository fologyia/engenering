"""Memorial separado: o trecho do cálculo de UMA peça, feito para colar no documento oficial.

Padrão de todos os memoriais separados do programa (o botão "Memorial …" de cada página). O
relatório geral (Central de relatórios) é outra coisa: o documento completo e conectado, com capa,
controle e aprovações. Aqui só vai o conteúdo técnico, num formato que se encaixa no documento de
quem cola:

* sem capa, controle de revisões, resumo executivo, quadro do projeto, aprovações, cabeçalho,
  rodapé ou quebra de seção;
* títulos **sem número**, nos estilos nativos ("Título 1, 2, 3"): o documento oficial numera pela
  lista dele e o sumário automático os encontra;
* legendas com **numeração automática** (campo SEQ "Figura" e "Tabela"), acima da ilustração, como
  pede a ABNT; elas se renumeram no destino e entram no índice de figuras e de tabelas;
* só estilos nativos (Normal, Legenda, Lista com marcadores, Tabela com grade), sem fonte nem cor
  próprias — colado com "usar estilos do destino", o trecho fica com a cara do documento oficial;
* A4 em retrato: tabelas até 16 cm, figuras até 15 cm;
* as contas como **equações do Word** (:mod:`core.equacao_word`), editáveis no destino.

:func:`trecho_de_registro` monta o trecho de qualquer registro técnico com tabela de verificações
na sequência de um memorial oficial: objetivo, normas e critérios, dados de entrada, esforços,
figuras, hipóteses, verificações (fórmula, números, resultado), resumo do que atende e do que não
atende, detalhamento, conclusão e símbolos.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Mapping, Sequence
from io import BytesIO
from typing import Any

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

from core import equacao_word as eq

LARGURA_UTIL_MM = 160.0  # A4 em retrato, margens de 30 mm (esquerda) e 20 mm (direita)
LARGURA_FIGURA_MM = 150.0
FUNDO_CABECALHO = "E7E6E6"  # cinza claro neutro, legível em preto e branco
#: A situação por extenso, para o texto ("— atende (56 %)").
SITUACAO_TEXTO = {
    "OK": "Atende",
    "NÃO OK": "Não atende",
    "ALERTA": "Atenção",
    "INFO": "Informativo",
    "N/A": "Não avaliado",
}
#: A situação nas tabelas, com símbolo: lê-se num relance e também impresso em preto e branco.
SITUACAO = {
    "OK": "✔ Atende",
    "NÃO OK": "✖ Não atende",
    "ALERTA": "⚠ Atenção",
    "INFO": "ⓘ Informativo",
    "N/A": "– Não avaliado",
}
#: Quadradinhos da barra de aproveitamento em texto (cada um, 10 %).
CASAS_DA_BARRA = 10


def barra_texto(percentual: float | None) -> str:
    """'■■■■■■■□□□' para 72 %: a barra de aproveitamento que sobrevive a colar como texto."""
    if percentual is None or percentual != percentual:
        return ""
    if percentual == float("inf"):
        return "■" * CASAS_DA_BARRA + " ▸"
    cheias = min(CASAS_DA_BARRA, max(0, round(percentual / (100 / CASAS_DA_BARRA))))
    barra = "■" * cheias + "□" * (CASAS_DA_BARRA - cheias)
    return barra + (" ▸" if percentual > 100.5 else "")


PRETO = RGBColor(0, 0, 0)


def _sombrear(celula: Any, cor: str) -> None:
    propriedades = celula._tc.get_or_add_tcPr()
    sombra = OxmlElement("w:shd")
    sombra.set(qn("w:val"), "clear")
    sombra.set(qn("w:color"), "auto")
    sombra.set(qn("w:fill"), cor)
    propriedades.append(sombra)


def _repetir_cabecalho(linha: Any) -> None:
    propriedades = linha._tr.get_or_add_trPr()
    marca = OxmlElement("w:tblHeader")
    marca.set(qn("w:val"), "true")
    propriedades.append(marca)


class Trecho:
    """Um trecho de memorial para colar em outro documento (ver o docstring do módulo)."""

    def __init__(self) -> None:
        self.doc = Document()
        secao = self.doc.sections[0]
        secao.page_width, secao.page_height = Mm(210), Mm(297)
        secao.left_margin, secao.right_margin = Mm(30), Mm(20)
        secao.top_margin, secao.bottom_margin = Mm(30), Mm(20)
        for nome in ("Heading 1", "Heading 2", "Heading 3", "Caption", "Title"):
            try:
                estilo = self.doc.styles[nome]
            except KeyError:
                continue
            estilo.font.color.rgb = PRETO  # neutro: no destino vale o estilo do documento oficial
        self.figuras = 0
        self.tabelas = 0
        self.equacoes = 0

    # ---------------------------------------------------------------- texto
    def titulo(self, texto: str, nivel: int = 1) -> None:
        self.doc.add_heading(texto, level=max(1, min(nivel, 4)))

    def paragrafo(self, texto: str, *, rotulo: str = "", italico: bool = False) -> Any:
        paragrafo = self.doc.add_paragraph()
        if rotulo:
            paragrafo.add_run(rotulo).bold = True
            paragrafo.add_run(" ")
        trecho = paragrafo.add_run(texto)
        trecho.italic = italico
        return paragrafo

    def itens(self, textos: Sequence[str], *, numerados: bool = False) -> None:
        estilo = "List Number" if numerados else "List Bullet"
        for texto in textos:
            if str(texto).strip():
                self.doc.add_paragraph(str(texto), style=estilo)

    def nota(self, texto: str) -> None:
        paragrafo = Trecho.paragrafo(self, texto, italico=True)
        for trecho in paragrafo.runs:
            trecho.font.size = Pt(9)

    def equacao(self, texto: str, *, maquina: bool = False, numerar: bool = True) -> None:
        """A conta como equação do Word, centrada, numa linha própria.

        O rótulo do começo e a referência do fim ficam em texto; várias contas separadas por ";"
        viram uma linha cada; as fórmulas só com símbolos ganham o número "(n)" à direita, num campo
        SEQ Equação que o documento oficial renumera; o valor calculado sai em caixa.
        """
        rotulo, equacoes, referencia = eq.preparar(texto, maquina=maquina)
        if rotulo:
            paragrafo = Trecho.paragrafo(self, rotulo, italico=True)
            paragrafo.paragraph_format.keep_with_next = True
        for equacao in equacoes:
            if numerar and equacao.simbolica:
                self._equacao_numerada(equacao)
            else:
                paragrafo = self.doc.add_paragraph()
                paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
                eq.acrescentar(paragrafo, equacao)
        if referencia:
            paragrafo = Trecho.paragrafo(self, f"({referencia})", italico=True)
            paragrafo.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            for corrida in paragrafo.runs:
                corrida.font.size = Pt(9)

    def _campo_seq(self, paragrafo: Any, tipo: str, numero: int) -> None:
        campo = OxmlElement("w:fldSimple")
        campo.set(qn("w:instr"), f" SEQ {tipo} \\* ARABIC ")
        corrida = OxmlElement("w:r")
        valor = OxmlElement("w:t")
        valor.text = str(numero)
        corrida.append(valor)
        campo.append(corrida)
        paragrafo._p.append(campo)

    def _equacao_numerada(self, equacao: eq.Equacao) -> None:
        """A equação centrada e o número à direita: tabela sem bordas de três colunas, o jeito que
        o Word guarda bem ao colar (o número é um campo SEQ Equação)."""
        self.equacoes += 1
        tabela = self.doc.add_table(rows=1, cols=3)  # sem estilo: sem bordas
        tabela.alignment = WD_TABLE_ALIGNMENT.CENTER
        larguras = (Mm(14), Mm(LARGURA_UTIL_MM - 28), Mm(14))
        for celula, largura in zip(tabela.rows[0].cells, larguras, strict=True):
            celula.width = largura
            celula.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        meio = tabela.rows[0].cells[1].paragraphs[0]
        meio.alignment = WD_ALIGN_PARAGRAPH.CENTER
        eq.acrescentar(meio, equacao)
        numero = tabela.rows[0].cells[2].paragraphs[0]
        numero.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        numero.add_run("(")
        self._campo_seq(numero, "Equação", self.equacoes)
        numero.add_run(")")

    def figura_do_diagrama(self, imagem: Any, largura_mm: float = LARGURA_FIGURA_MM) -> None:
        """Uma figura do programa (ImagemDiagrama): o título na legenda e a explicação embaixo."""
        if imagem is None or not getattr(imagem, "png", b""):
            return
        self.figura(imagem.png, imagem.titulo or imagem.legenda, largura_mm)
        if imagem.legenda and imagem.legenda != imagem.titulo:
            self.nota(limpar_texto(imagem.legenda))

    def grafico_das_verificacoes(self, verificacoes: Sequence[Any]) -> None:
        """O gráfico de aproveitamento de uma lista de :class:`core.verificacao.Verificacao`."""
        from core.graficos_memorial import grafico_das_verificacoes

        itens = [
            (v.nome, None if v.aproveitamento is None else 100 * v.aproveitamento, v.status)
            for v in verificacoes
        ]
        self.figura_do_diagrama(grafico_das_verificacoes(itens))

    # ---------------------------------------------------------------- legendas, tabelas, figuras
    def legenda(self, tipo: str, texto: str) -> None:
        """'Tabela 3 – texto' com o número num campo SEQ (o destino renumera)."""
        if tipo == "Figura":
            self.figuras += 1
            numero = self.figuras
        else:
            self.tabelas += 1
            numero = self.tabelas
        paragrafo = self.doc.add_paragraph(style="Caption")
        paragrafo.paragraph_format.keep_with_next = True
        paragrafo.add_run(f"{tipo} ")
        self._campo_seq(paragrafo, tipo, numero)
        # "Tabela 1 - Entradas…" que o módulo já numerou: o número é o do campo
        texto = _NUMERO_NA_LEGENDA.sub("", texto.strip()).rstrip(".")
        paragrafo.add_run(f" – {texto}")

    def tabela(
        self,
        cabecalhos: Sequence[str],
        linhas: Sequence[Sequence[Any]],
        *,
        legenda: str,
        larguras_mm: Sequence[float] | None = None,
        fonte: float = 9.0,
    ) -> None:
        if not linhas:
            return
        self.legenda("Tabela", legenda)
        n = len(cabecalhos)
        if larguras_mm is None:
            larguras_mm = [LARGURA_UTIL_MM / n] * n
        escala = min(1.0, LARGURA_UTIL_MM / sum(larguras_mm))
        larguras = [Mm(w * escala) for w in larguras_mm]
        tabela = self.doc.add_table(rows=1, cols=n)
        tabela.style = "Table Grid"
        tabela.alignment = WD_TABLE_ALIGNMENT.CENTER

        def escrever(celula: Any, texto: str, *, cabecalho: bool = False) -> None:
            celula.text = ""
            corrida = celula.paragraphs[0].add_run(texto)
            corrida.font.size = Pt(fonte)
            corrida.bold = cabecalho

        topo = tabela.rows[0]
        _repetir_cabecalho(topo)
        for celula, texto, largura in zip(topo.cells, cabecalhos, larguras, strict=True):
            escrever(celula, str(texto), cabecalho=True)
            _sombrear(celula, FUNDO_CABECALHO)
            celula.width = largura
        for linha in linhas:
            celulas = tabela.add_row().cells
            for celula, valor, largura in zip(celulas, linha, larguras, strict=True):
                escrever(celula, "-" if valor is None or valor == "" else str(valor))
                celula.width = largura
        self.doc.add_paragraph()

    def figura(self, png: bytes, legenda: str, largura_mm: float = LARGURA_FIGURA_MM) -> None:
        self.legenda("Figura", legenda)
        self.doc.add_picture(BytesIO(png), width=Mm(min(largura_mm, LARGURA_FIGURA_MM)))
        self.doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

    def bytes(self) -> bytes:
        memoria = BytesIO()
        self.doc.save(memoria)
        return memoria.getvalue()


# ============================================================================================
# Texto em linguagem de memorial
# ============================================================================================
_COMBINACAO = re.compile(r"^\[([^\]]+)\]\s*")
_NUMERO_NA_LEGENDA = re.compile(r"^(?:Tabela|Figura|Quadro)\s+\d+\s*[-–—:.]\s*", re.IGNORECASE)
_SENAO = re.compile(r"\s*(?:;\s*|\()(?:senão|caso contrário),[^;)]*\)?")


def separar_combinacao(texto: str) -> tuple[str, str]:
    """'[C16-ELU] fórmula' → ('C16-ELU', 'fórmula'); sem o prefixo, ('', texto)."""
    achou = _COMBINACAO.match(texto or "")
    if not achou:
        return "", texto or ""
    return achou.group(1), texto[achou.end() :]


def limpar_texto(texto: str) -> str:
    """O texto sem os conselhos de tela ("senão, aumente …"; "caso contrário, refazer …")."""
    return _SENAO.sub("", texto or "").strip()


def texto_de_memorial(texto: str) -> str:
    """O texto de um registro técnico limpo e com vírgula decimal (as fórmulas dos registros saem
    em notação de máquina; textos já em português, com ponto de milhar, usam :func:`limpar_texto`)."""
    from core.memorial_verificacoes import decimal_ptbr

    return decimal_ptbr(limpar_texto(texto))


def numero_pt(valor: Any, casas: int = 2) -> str:
    if valor is None or valor == "":
        return "-"
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, (int, float)):
        if valor != valor:  # NaN
            return "-"
        if valor in (float("inf"), float("-inf")):
            return "∞"
        texto = f"{valor:.{casas}f}".replace(".", ",")
        return texto
    return str(valor)


# ============================================================================================
# O trecho de um registro técnico
# ============================================================================================
def _lista(valor: Any) -> list[Any]:
    if isinstance(valor, Sequence) and not isinstance(valor, (str, bytes)):
        return list(valor)
    return []


def _casas_da_linha(linha: Any) -> int:
    """2 casas, mais quando o arredondamento esconderia a diferença que o status vê."""
    from core.verificacao import Verificacao, casas_coerentes

    try:
        s, r = float(linha.solicitante), float(linha.resistente)
    except (TypeError, ValueError):
        return 2
    return casas_coerentes(Verificacao("", s, r, linha.unidade or "", "", status=linha.status))


def _aproveitamento(linha: Any) -> str:
    a = linha.aproveitamento
    if a is None:
        return "-"
    if a == float("inf"):
        return "∞"
    casas = 0 if linha.status != "NÃO OK" or round(a) > 100 else 2
    return f"{a:.{casas}f} %".replace(".", ",")


def _linha_da_tabela(linha: Any) -> list[str]:
    casas = _casas_da_linha(linha)
    return [
        linha.nome,
        numero_pt(linha.solicitante, casas),
        numero_pt(linha.resistente, casas),
        linha.unidade or "-",
        _aproveitamento(linha),
        barra_texto(linha.aproveitamento),
        SITUACAO.get(linha.status, linha.status),
    ]


CABECALHOS_RESUMO = [
    "Verificação", "Solicitante", "Resistente", "Un.", "Aprov.", "0 a 100 %", "Situação",
]  # fmt: skip
LARGURAS_RESUMO = [45.0, 18.0, 18.0, 10.0, 14.0, 26.0, 29.0]


def _escrever_conta(t: Trecho, linha: Any, equacoes: Sequence[str]) -> None:
    """Uma verificação: o nome e a situação, o cálculo em texto, as equações e a referência."""
    combinacao, formula = separar_combinacao(linha.formula)
    situacao = SITUACAO_TEXTO.get(linha.status, linha.status)
    cabeca = linha.nome
    if linha.aproveitamento is not None and linha.status in ("OK", "NÃO OK", "ALERTA"):
        cabeca += f" — {situacao.lower()} ({_aproveitamento(linha)})"
    elif linha.status == "INFO":
        cabeca += " — informativo"
    else:
        cabeca += f" — {situacao.lower()}"
    if combinacao:
        cabeca += f"; combinação que governa: {combinacao}"
    paragrafo = t.paragrafo("", rotulo=cabeca)
    paragrafo.paragraph_format.keep_with_next = True
    for texto in equacoes:
        t.equacao(texto)
    if formula:
        t.paragrafo(texto_de_memorial(formula))
    if linha.referencia:
        t.paragrafo(linha.referencia, rotulo="Referência:")


def escrever_registro(
    t: Trecho,
    registro: Mapping[str, Any],
    *,
    imagens: Sequence[Mapping[str, Any]] = (),
    nivel: int = 1,
    figuras_por_verificacao: Mapping[str, Sequence[Any]] | None = None,
) -> None:
    """Escreve no trecho o memorial de um registro técnico com tabela de verificações.

    ``figuras_por_verificacao``: figuras de apoio (ImagemDiagrama) que entram logo depois da conta
    da verificação de mesmo nome — a pressão sob a placa junto da pressão de contato, por exemplo.
    """
    from core import memorial_verificacoes as mv
    from core.graficos_memorial import grafico_das_combinacoes, grafico_das_verificacoes

    # o gerador do relatório geral está fora da lista do mypy: importado pelo nome
    relatorio = importlib.import_module("core.project_report")
    _valor, _campo_legivel = relatorio._valor, relatorio._campo_legivel
    bruto = registro.get("resultados")
    resultados: Mapping[str, Any] = bruto if isinstance(bruto, Mapping) else {}
    linhas = mv.extrair_linhas(registro) or []
    equacoes_por_nome = _equacoes_por_nome(resultados)
    resumo = mv.resumir(linhas)
    titulo = str(registro.get("titulo_memorial") or registro.get("titulo") or "Cálculo")
    t.titulo(titulo, nivel)

    # 1. objetivo
    objetivo = str(resultados.get("objetivo") or registro.get("objetivo") or "").strip()
    if objetivo:
        t.paragrafo(texto_de_memorial(objetivo))

    # 2. normas e critérios
    referencias = [str(r) for r in _lista(registro.get("referencias")) if str(r).strip()]
    criterios = [str(r) for r in _lista(registro.get("criterios")) if str(r).strip()]
    if referencias or criterios:
        t.titulo("Normas e critérios", nivel + 1)
        # as normas como estão escritas ("6.2", "5.7"): número de item, nunca decimal
        t.itens([*referencias, *(texto_de_memorial(x) for x in criterios)])

    # 3. dados de entrada
    pares = mv.pares_de_entrada(registro, _valor, _campo_legivel)
    if pares:
        t.titulo("Materiais e dados de entrada", nivel + 1)
        t.tabela(
            ["Dado", "Valor"],
            [[rotulo, texto_de_memorial(str(valor))] for rotulo, valor in pares],
            legenda="Dados de entrada",
            larguras_mm=[60.0, 100.0],
        )

    # 4. esforços (combinações)
    combinacoes = [c for c in _lista(resultados.get("combinacoes")) if isinstance(c, Mapping)]
    if combinacoes:
        t.titulo("Esforços de cálculo", nivel + 1)
        cabecalhos = [k for k in combinacoes[0] if k != "Status"]

        def celula(chave: str, valor: Any) -> str:
            if chave == "Aproveitamento" and isinstance(valor, (int, float)):
                return f"{100 * valor:.0f} %"
            return numero_pt(valor) if isinstance(valor, float) else str(valor)

        t.tabela(
            [k.replace("Aproveitamento", "Aprov.") for k in cabecalhos],
            [[celula(k, c.get(k)) for k in cabecalhos] for c in combinacoes],
            legenda="Combinações de cálculo (ELU) e o resultado de cada uma",
            fonte=7.5,
        )
        if all(isinstance(c.get("Aproveitamento"), (int, float)) for c in combinacoes):
            governante = str(resultados.get("combinacao_governante") or "")
            t.figura_do_diagrama(
                grafico_das_combinacoes(
                    [
                        (
                            str(c.get("Combinação") or ""),
                            100 * float(c["Aproveitamento"]),
                            str(c.get("Governa") or ""),
                            str(c.get("Status") or ""),
                        )
                        for c in combinacoes
                    ],
                    governante,
                )
            )

    # 5. figuras
    if imagens:
        t.titulo("Desenho", nivel + 1)
        for imagem in imagens:
            png = imagem.get("png") or imagem.get("bytes")
            if isinstance(png, (bytes, bytearray)):
                largura = imagem.get("largura_pol")
                nome = str(imagem.get("titulo") or "").strip()
                legenda = str(imagem.get("legenda") or "").strip()
                t.figura(
                    bytes(png),
                    nome or legenda or titulo,
                    float(largura) * 25.4
                    if isinstance(largura, (int, float))
                    else LARGURA_FIGURA_MM,
                )
                if nome and legenda and legenda != nome:
                    t.nota(texto_de_memorial(legenda))

    # 6. hipóteses
    metodo = str(registro.get("metodo") or "").strip()
    premissas = [str(p) for p in _lista(registro.get("premissas")) if str(p).strip()]
    gerais = mv.equacoes_gerais(registro, linhas)  # as do método (corte, contato, grupo…)
    if metodo or premissas or gerais:
        t.titulo("Hipóteses de cálculo", nivel + 1)
        if metodo:
            t.paragrafo(texto_de_memorial(metodo))
        t.itens([texto_de_memorial(p) for p in premissas])
        if gerais:
            t.paragrafo("", rotulo="Equações do método:").paragraph_format.keep_with_next = True
            for texto in gerais:
                t.equacao(texto)

    # 7. verificações, por grupo
    if linhas:
        t.titulo("Verificações", nivel + 1)
        grupos = _grupos(resultados, linhas)
        for nome_grupo, do_grupo in grupos:
            if nome_grupo and len(grupos) > 1:
                t.titulo(nome_grupo, nivel + 2)
            for linha in do_grupo:
                _escrever_conta(t, linha, equacoes_por_nome.get(linha.nome, ()))
                for figura in (figuras_por_verificacao or {}).get(linha.nome, ()):
                    t.figura_do_diagrama(figura)

        # 8. resumo: o que atende e, por último, o que não atende
        t.titulo("Resumo das verificações", nivel + 1)
        t.paragrafo(texto_de_memorial(mv.texto_do_resultado({}, resumo, _valor)))
        t.figura_do_diagrama(
            grafico_das_verificacoes([(x.nome, x.aproveitamento, x.status) for x in linhas])
        )
        if resumo.passaram:
            t.tabela(
                CABECALHOS_RESUMO,
                [_linha_da_tabela(x) for x in resumo.passaram],
                legenda="Verificações que atendem (aproveitamento = solicitante ÷ resistente)",
                larguras_mm=LARGURAS_RESUMO,
            )
        problemas = [*resumo.reprovadas, *resumo.atencao, *resumo.nao_avaliadas]
        if problemas:
            t.tabela(
                CABECALHOS_RESUMO,
                [_linha_da_tabela(x) for x in problemas],
                legenda="Verificações que não atendem ou pedem atenção",
                larguras_mm=LARGURAS_RESUMO,
            )
        else:
            t.paragrafo("Todas as verificações com critério atendem.")

    # 9. detalhamento
    detalhamento = [d for d in _lista(resultados.get("detalhamento")) if _lista(d)]
    if detalhamento:
        t.titulo("Detalhamento construtivo", nivel + 1)
        t.tabela(
            ["Item", "Especificação"],
            [[str(d[0]), texto_de_memorial(str(d[1]))] for d in detalhamento],
            legenda="Detalhamento construtivo",
            larguras_mm=[38.0, 122.0],
        )

    # 10. conclusão
    conclusao = str(registro.get("conclusao") or resultados.get("destaque_memorial") or "").strip()
    if conclusao:
        t.titulo("Conclusão", nivel + 1)
        t.paragrafo(texto_de_memorial(conclusao))

    # 11. símbolos
    simbolos = [s for s in _lista(resultados.get("simbolos")) if _lista(s)]
    if simbolos:
        t.titulo("Símbolos", nivel + 1)
        t.tabela(
            ["Símbolo", "Significado"],
            [[str(s[0]), str(s[1])] for s in simbolos],
            legenda="Símbolos usados neste item",
            larguras_mm=[28.0, 132.0],
        )


def _equacoes_por_nome(resultados: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    saida: dict[str, tuple[str, ...]] = {}
    for item in _lista(resultados.get("verificações") or resultados.get("verificacoes")):
        if not isinstance(item, Mapping):
            continue
        equacoes = _lista(item.get("equações") or item.get("equacoes"))
        nome = str(item.get("verificação") or item.get("verificacao") or item.get("nome") or "")
        if nome and equacoes:
            saida[nome] = tuple(str(x) for x in equacoes)
    return saida


def _grupos(resultados: Mapping[str, Any], linhas: Sequence[Any]) -> list[tuple[str, list[Any]]]:
    """As verificações na ordem dos grupos que o módulo gravou; sem grupos, um só."""
    grupos = [g for g in _lista(resultados.get("grupos")) if isinstance(g, Mapping)]
    if not grupos:
        return [("", list(linhas))]
    restantes = list(linhas)
    saida: list[tuple[str, list[Any]]] = []
    for grupo in grupos:
        nomes = [str(n) for n in _lista(grupo.get("verificacoes"))]
        do_grupo = [x for x in restantes if x.nome in nomes]
        if do_grupo:
            saida.append((str(grupo.get("nome") or ""), do_grupo))
            restantes = [x for x in restantes if x not in do_grupo]
    if restantes:
        saida.append(("Outras verificações", restantes))
    return saida


def trecho_de_registro(
    registro: Mapping[str, Any],
    *,
    projeto: Mapping[str, Any] | None = None,
    imagens: Sequence[Mapping[str, Any]] | None = None,
    figuras_por_verificacao: Mapping[str, Sequence[Any]] | None = None,
) -> bytes:
    """O memorial separado (Word) de um registro técnico, pronto para colar no documento oficial."""
    if imagens is None:
        graficos = importlib.import_module("core.record_charts")  # fora da lista do mypy
        imagens, _ = graficos.imagens_do_registro(registro, projeto or {})
    t = Trecho()
    escrever_registro(t, registro, imagens=imagens, figuras_por_verificacao=figuras_por_verificacao)
    return t.bytes()


# ============================================================================================
# Seções genéricas do memorial (os blocos de core.memorial_blocos) como trecho
# ============================================================================================
def _celula(valor: Any) -> str:
    if isinstance(valor, (tuple, list)) and valor:
        principal = str(valor[0])
        detalhe = str(valor[1]) if len(valor) > 1 and valor[1] else ""
        return f"{principal}\n{detalhe}" if detalhe else principal
    return "-" if valor is None or valor == "" else str(valor)


def escrever_secoes(t: Trecho, secoes: Sequence[Mapping[str, Any]], *, nivel_base: int = 1) -> None:
    """As seções no formato do memorial (título, nível e blocos) escritas como trecho.

    O número que vem no título ("7.1 Equação de Marin") sai — o documento oficial numera —, as
    fórmulas viram equações do Word e as tabelas e figuras ganham legenda numerada.
    """
    from core.memorial_blocos import blocos_da_secao
    from core.word_documento import titulo_de_memorial

    for secao in secoes:
        nivel = int(secao.get("nivel", 1)) + nivel_base - 1
        t.titulo(titulo_de_memorial(str(secao.get("titulo") or "")), nivel)
        for bloco in blocos_da_secao(secao):
            tipo = bloco.get("tipo")
            if tipo == "paragrafo":
                t.paragrafo(limpar_texto(str(bloco.get("texto") or "")))
            elif tipo == "subtitulo":
                t.titulo(str(bloco.get("texto") or ""), nivel + 1)
            elif tipo == "destaque":
                t.paragrafo(
                    limpar_texto(str(bloco.get("texto") or "")),
                    rotulo=str(bloco.get("rotulo") or ""),
                )
            elif tipo == "nota":
                t.nota(limpar_texto(str(bloco.get("texto") or "")))
            elif tipo in ("bullets", "passos"):
                t.itens(
                    [limpar_texto(str(x)) for x in bloco.get("itens") or []],
                    numerados=tipo == "passos",
                )
            elif tipo == "formula":
                t.equacao(limpar_texto(str(bloco.get("texto") or "")))
            elif tipo == "imagem":
                png = bloco.get("png") or bloco.get("bytes")
                if isinstance(png, (bytes, bytearray)):
                    t.figura(
                        bytes(png), str(bloco.get("legenda") or bloco.get("titulo") or "Figura")
                    )
            elif tipo == "tabela":
                larguras: list[float] = list(bloco.get("larguras") or [])
                total = sum(larguras)
                t.tabela(
                    [str(c) for c in bloco.get("cabecalhos", [])],
                    [[_celula(v) for v in linha] for linha in bloco.get("linhas", [])],
                    legenda=str(bloco.get("legenda") or secao.get("titulo") or "Tabela"),
                    larguras_mm=[LARGURA_UTIL_MM * w / total for w in larguras] if total else None,
                    fonte=min(9.0, float(bloco.get("fonte", 9.0))),
                )


def trecho_de_secoes(titulo: str, secoes: Sequence[Mapping[str, Any]]) -> bytes:
    """O memorial separado de um cálculo descrito em seções (fadiga e afins)."""
    t = Trecho()
    t.titulo(titulo, 1)
    escrever_secoes(t, secoes, nivel_base=2)
    return t.bytes()
