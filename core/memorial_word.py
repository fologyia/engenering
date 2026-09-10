"""Memoriais de cálculo editáveis em Word com estrutura reutilizável."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import datetime
from io import BytesIO
from typing import Any

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor, Twips

CONTENT_WIDTH_DXA = 9360
TABLE_INDENT_DXA = 120
CELL_MARGINS_DXA = {"top": 80, "bottom": 80, "start": 120, "end": 120}
NAVY = "0B2545"
BLUE = "2E74B5"
DARK_BLUE = "1F4D78"
MUTED = "5F6B76"
BORDER = "C9D4DE"
HEADER_FILL = "F2F4F7"
BLUE_FILL = "E8EEF5"
NOTE_FILL = "F4F6F9"
WHITE = "FFFFFF"
RISK = "9B1C1C"
CAUTION = "7A5A00"
POSITIVE = "1F3A5F"


def _texto(valor: Any, padrao: str = "Não informado") -> str:
    if valor is None or str(valor).strip() == "":
        return padrao
    return str(valor).replace("—", "-").replace("–", "-")


def _numero(valor: float | None, casas: int = 3) -> str:
    if valor is None:
        return "Não calculado"
    if math.isinf(valor):
        return "Infinito"
    return f"{valor:.{casas}f}".replace(".", ",")

def _inteiro(valor: float | None) -> str:
    if valor is None:
        return "Não informado"
    return f"{float(valor):,.0f}".replace(",", ".")


def _status_calculo(dados: Mapping[str, Any]) -> tuple[str, str, str]:
    fatores = {
        "Goodman": dados.get("n_goodman"),
        "Soderberg": dados.get("n_soderberg"),
        "Escoamento no primeiro ciclo": dados.get("n_escoamento"),
    }
    validos = {
        nome: float(valor)
        for nome, valor in fatores.items()
        if valor is not None and math.isfinite(float(valor))
    }
    if not validos:
        return "INCONCLUSIVO", CAUTION, "Não há critérios suficientes para concluir."

    meta = max(float(dados.get("fator_seguranca_minimo", 1.0) or 1.0), 0.01)
    criterio, menor = min(validos.items(), key=lambda item: item[1])
    if menor < meta:
        return (
            "NÃO ATENDE",
            RISK,
            f"{criterio} governa com n = {_numero(menor, 2)}, abaixo da meta n ≥ {_numero(meta, 2)}.",
        )

    vida_requerida = max(float(dados.get("vida_requerida_ciclos", 0.0) or 0.0), 0.0)
    if vida_requerida > 0 and not bool(dados.get("vida_infinita", False)):
        ciclos = dados.get("ciclos_estimados")
        if ciclos is None or not math.isfinite(float(ciclos)):
            return (
                "INCONCLUSIVO",
                CAUTION,
                "A vida mínima foi definida, mas a vida estimada não pôde ser determinada.",
            )
        if float(ciclos) < vida_requerida:
            return (
                "NÃO ATENDE",
                RISK,
                f"A vida estimada de {_inteiro(float(ciclos))} ciclos é inferior aos "
                f"{_inteiro(vida_requerida)} ciclos requeridos.",
            )

    if vida_requerida <= 0:
        return (
            "ATENDE COM PENDÊNCIA",
            CAUTION,
            f"Os fatores atendem à meta n ≥ {_numero(meta, 2)}, mas a vida mínima requerida não foi informada.",
        )

    return (
        "ATENDE",
        POSITIVE,
        f"Os fatores atendem à meta n ≥ {_numero(meta, 2)} e a vida calculada atende ao requisito informado.",
    )

def _set_run_font(
    run,
    *,
    name: str = "Calibri",
    size: float | None = None,
    color: str | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
) -> None:
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    if size is not None:
        run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic


def _configure_style(style, *, size: float, color: str, bold: bool = False) -> None:
    style.font.name = "Calibri"
    style._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Calibri")
    style._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Calibri")
    style.font.size = Pt(size)
    style.font.color.rgb = RGBColor.from_string(color)
    style.font.bold = bold
    lang = style._element.get_or_add_rPr().find(qn("w:lang"))
    if lang is None:
        lang = OxmlElement("w:lang")
        style._element.get_or_add_rPr().append(lang)
    lang.set(qn("w:val"), "pt-BR")


def _configure_styles(document: Document) -> None:
    styles = document.styles
    normal = styles["Normal"]
    _configure_style(normal, size=11, color="26323D")
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.10

    title = styles["Title"]
    _configure_style(title, size=24, color=NAVY, bold=True)
    title.paragraph_format.space_before = Pt(0)
    title.paragraph_format.space_after = Pt(4)
    title.paragraph_format.keep_with_next = True

    subtitle = styles["Subtitle"]
    _configure_style(subtitle, size=12.5, color=MUTED)
    subtitle.paragraph_format.space_before = Pt(0)
    subtitle.paragraph_format.space_after = Pt(14)
    subtitle.paragraph_format.keep_with_next = True

    heading_tokens = {
        "Heading 1": (16, BLUE, 16, 8),
        "Heading 2": (13, BLUE, 12, 6),
        "Heading 3": (12, DARK_BLUE, 8, 4),
    }
    for nome, (size, color, before, after) in heading_tokens.items():
        style = styles[nome]
        _configure_style(style, size=size, color=color, bold=True)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.keep_together = True

    custom_styles = {
        "Memorial Kicker": (9.5, BLUE, True),
        "Memorial Formula": (10.5, NAVY, False),
        "Memorial Note": (9.5, "26323D", False),
        "Memorial Caption": (8.5, MUTED, False),
        "Memorial Table": (8.5, "26323D", False),
    }
    for nome, (size, color, bold) in custom_styles.items():
        if nome not in styles:
            styles.add_style(nome, WD_STYLE_TYPE.PARAGRAPH)
        style = styles[nome]
        _configure_style(style, size=size, color=color, bold=bold)
        style.paragraph_format.space_before = Pt(0)
        style.paragraph_format.space_after = Pt(4)
        style.paragraph_format.line_spacing = 1.05
    styles["Memorial Formula"].paragraph_format.left_indent = Inches(0.08)
    styles["Memorial Formula"].paragraph_format.right_indent = Inches(0.08)
    styles["Memorial Formula"].paragraph_format.keep_together = True
    styles["Memorial Kicker"].paragraph_format.space_after = Pt(2)


def _ensure_child(parent, tag: str):
    child = parent.find(qn(tag))
    if child is None:
        child = OxmlElement(tag)
        parent.append(child)
    return child


def _set_width(parent, tag: str, width_dxa: int) -> None:
    width = _ensure_child(parent, tag)
    width.set(qn("w:type"), "dxa")
    width.set(qn("w:w"), str(int(width_dxa)))


def _set_cell_margins(cell, margins: Mapping[str, int] = CELL_MARGINS_DXA) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = _ensure_child(tc_pr, "w:tcMar")
    for side in ("top", "bottom", "start", "end"):
        margin = _ensure_child(tc_mar, f"w:{side}")
        margin.set(qn("w:w"), str(int(margins[side])))
        margin.set(qn("w:type"), "dxa")


def _apply_table_geometry(
    table,
    widths_dxa: Sequence[int],
    *,
    indent_dxa: int = TABLE_INDENT_DXA,
    margins: Mapping[str, int] = CELL_MARGINS_DXA,
) -> None:
    widths = [int(width) for width in widths_dxa]
    if not widths or sum(widths) != CONTENT_WIDTH_DXA:
        raise ValueError("As larguras da tabela devem totalizar 9360 DXA.")
    if any(width <= 0 for width in widths):
        raise ValueError("As larguras das colunas devem ser positivas.")

    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl_pr = table._tbl.tblPr
    _set_width(tbl_pr, "w:tblW", CONTENT_WIDTH_DXA)
    tbl_ind = _ensure_child(tbl_pr, "w:tblInd")
    tbl_ind.set(qn("w:type"), "dxa")
    tbl_ind.set(qn("w:w"), str(indent_dxa))
    layout = _ensure_child(tbl_pr, "w:tblLayout")
    layout.set(qn("w:type"), "fixed")

    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)

    for col_idx, width in enumerate(widths):
        table.columns[col_idx].width = Twips(width)
    for row in table.rows:
        if len(row.cells) != len(widths):
            raise ValueError("Tabelas com células mescladas não são suportadas pelo padrão.")
        row.height = None
        tr_pr = row._tr.get_or_add_trPr()
        if tr_pr.find(qn("w:cantSplit")) is None:
            tr_pr.append(OxmlElement("w:cantSplit"))
        for col_idx, cell in enumerate(row.cells):
            width = widths[col_idx]
            cell.width = Twips(width)
            _set_width(cell._tc.get_or_add_tcPr(), "w:tcW", width)
            _set_cell_margins(cell, margins)


def _set_table_borders(table, color: str = BORDER, size: int = 4) -> None:
    tbl_borders = _ensure_child(table._tbl.tblPr, "w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = _ensure_child(tbl_borders, f"w:{edge}")
        tag.set(qn("w:val"), "single")
        tag.set(qn("w:sz"), str(size))
        tag.set(qn("w:space"), "0")
        tag.set(qn("w:color"), color)


def _remove_table_borders(table) -> None:
    tbl_borders = _ensure_child(table._tbl.tblPr, "w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = _ensure_child(tbl_borders, f"w:{edge}")
        tag.set(qn("w:val"), "nil")


def _shade_cell(cell, fill: str) -> None:
    shd = _ensure_child(cell._tc.get_or_add_tcPr(), "w:shd")
    shd.set(qn("w:fill"), fill)


def _repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    header = _ensure_child(tr_pr, "w:tblHeader")
    header.set(qn("w:val"), "true")


def _write_cell(
    cell,
    value: Any,
    *,
    bold: bool = False,
    color: str = "26323D",
    size: float = 8.5,
    align=WD_ALIGN_PARAGRAPH.LEFT,
) -> None:
    cell.text = ""
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    paragraph = cell.paragraphs[0]
    paragraph.alignment = align
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1.05
    run = paragraph.add_run(_texto(value, "-"))
    _set_run_font(run, size=size, color=color, bold=bold)


def _add_data_table(
    document: Document,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    widths_dxa: Sequence[int],
    *,
    font_size: float = 8.5,
    header_fill: str = HEADER_FILL,
    zebra: bool = True,
) -> Any:
    table = document.add_table(rows=1, cols=len(headers))
    _apply_table_geometry(table, widths_dxa)
    _set_table_borders(table)
    _repeat_header(table.rows[0])
    for idx, header in enumerate(headers):
        _shade_cell(table.rows[0].cells[idx], header_fill)
        _write_cell(table.rows[0].cells[idx], header, bold=True, color=NAVY, size=font_size)
        # Mantém o cabeçalho junto da primeira linha de dados. Sem esta
        # propriedade, o Word pode deixar somente o cabeçalho no rodapé de
        # uma página e começar os dados na página seguinte.
        table.rows[0].cells[idx].paragraphs[0].paragraph_format.keep_with_next = True
    for row_idx, values in enumerate(rows):
        row = table.add_row()
        for col_idx, value in enumerate(values):
            if zebra and row_idx % 2 == 1:
                _shade_cell(row.cells[col_idx], "FAFBFC")
            _write_cell(row.cells[col_idx], value, size=font_size)
    _apply_table_geometry(table, widths_dxa)
    document.add_paragraph().paragraph_format.space_after = Pt(0)
    return table

def _next_numbering_id(numbering, tag: str, attr: str) -> int:
    values = []
    for node in numbering.findall(qn(tag)):
        value = node.get(qn(attr))
        if value is not None:
            values.append(int(value))
    return max(values, default=0) + 1


def _create_numbering(document: Document, *, numbered: bool) -> int:
    numbering = document.part.numbering_part.element
    abstract_id = _next_numbering_id(numbering, "w:abstractNum", "w:abstractNumId")
    num_id = _next_numbering_id(numbering, "w:num", "w:numId")

    abstract = OxmlElement("w:abstractNum")
    abstract.set(qn("w:abstractNumId"), str(abstract_id))
    multi = OxmlElement("w:multiLevelType")
    multi.set(qn("w:val"), "singleLevel")
    abstract.append(multi)
    level = OxmlElement("w:lvl")
    level.set(qn("w:ilvl"), "0")
    start = OxmlElement("w:start")
    start.set(qn("w:val"), "1")
    level.append(start)
    num_fmt = OxmlElement("w:numFmt")
    num_fmt.set(qn("w:val"), "decimal" if numbered else "bullet")
    level.append(num_fmt)
    lvl_text = OxmlElement("w:lvlText")
    # O Word espera o marcador privado da fonte Symbol. Usar U+2022 com essa
    # fonte pode ser reinterpretado como uma lista decimal durante a renderização.
    lvl_text.set(qn("w:val"), "%1." if numbered else "\uf0b7")
    level.append(lvl_text)
    lvl_jc = OxmlElement("w:lvlJc")
    lvl_jc.set(qn("w:val"), "left")
    level.append(lvl_jc)
    p_pr = OxmlElement("w:pPr")
    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "num")
    tab.set(qn("w:pos"), "720")
    tabs.append(tab)
    p_pr.append(tabs)
    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), "720")
    ind.set(qn("w:hanging"), "360")
    p_pr.append(ind)
    level.append(p_pr)
    if not numbered:
        r_pr = OxmlElement("w:rPr")
        fonts = OxmlElement("w:rFonts")
        fonts.set(qn("w:ascii"), "Symbol")
        fonts.set(qn("w:hAnsi"), "Symbol")
        r_pr.append(fonts)
        level.append(r_pr)
    abstract.append(level)
    # A ordem do schema exige todos os abstractNum antes dos elementos num.
    # Se o abstract for anexado após os num nativos do template, o Word
    # ignora a definição e pode exibir marcadores como números sequenciais.
    first_num = numbering.find(qn("w:num"))
    if first_num is None:
        numbering.append(abstract)
    else:
        numbering.insert(numbering.index(first_num), abstract)

    num = OxmlElement("w:num")
    num.set(qn("w:numId"), str(num_id))
    abstract_ref = OxmlElement("w:abstractNumId")
    abstract_ref.set(qn("w:val"), str(abstract_id))
    num.append(abstract_ref)
    numbering.append(num)
    return num_id


def _add_list_item(document: Document, text: str, num_id: int) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(8)
    paragraph.paragraph_format.line_spacing = 1.167
    num_pr = _ensure_child(paragraph._p.get_or_add_pPr(), "w:numPr")
    ilvl = _ensure_child(num_pr, "w:ilvl")
    ilvl.set(qn("w:val"), "0")
    num_id_node = _ensure_child(num_pr, "w:numId")
    num_id_node.set(qn("w:val"), str(num_id))
    run = paragraph.add_run(text)
    _set_run_font(run, size=11, color="26323D")


def _paragraph_box(paragraph, fill: str, border: str = BORDER) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    shd = _ensure_child(p_pr, "w:shd")
    shd.set(qn("w:fill"), fill)
    p_borders = _ensure_child(p_pr, "w:pBdr")
    for edge in ("top", "left", "bottom", "right"):
        item = _ensure_child(p_borders, f"w:{edge}")
        item.set(qn("w:val"), "single")
        item.set(qn("w:sz"), "4")
        item.set(qn("w:space"), "3")
        item.set(qn("w:color"), border)


def _add_formula(document: Document, formula: str) -> None:
    paragraph = document.add_paragraph(style="Memorial Formula")
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _paragraph_box(paragraph, NOTE_FILL)
    run = paragraph.add_run(formula)
    _set_run_font(run, name="Cambria Math", size=10.5, color=NAVY)


def _add_note(document: Document, text: str, *, fill: str = NOTE_FILL) -> None:
    paragraph = document.add_paragraph(style="Memorial Note")
    _paragraph_box(paragraph, fill)
    label = paragraph.add_run("Nota técnica. ")
    _set_run_font(label, size=9.5, color=NAVY, bold=True)
    body = paragraph.add_run(text)
    _set_run_font(body, size=9.5, color="26323D")


def _append_field(paragraph, instruction: str, fallback: str = "1") -> None:
    begin_run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    begin_run._r.append(begin)
    instr_run = paragraph.add_run()
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {instruction} "
    instr_run._r.append(instr)
    separate_run = paragraph.add_run()
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    separate_run._r.append(separate)
    value_run = paragraph.add_run(fallback)
    _set_run_font(value_run, size=8, color=MUTED)
    end_run = paragraph.add_run()
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    end_run._r.append(end)


def _set_header_footer(document: Document, metadata: Mapping[str, Any]) -> None:
    section = document.sections[0]
    zero_margins = {"top": 0, "bottom": 0, "start": 0, "end": 0}

    header = section.header
    header.paragraphs[0].paragraph_format.space_after = Pt(0)
    header_table = header.add_table(rows=1, cols=2, width=Inches(6.5))
    _apply_table_geometry(
        header_table,
        [5600, 3760],
        indent_dxa=0,
        margins=zero_margins,
    )
    _remove_table_borders(header_table)
    _write_cell(
        header_table.cell(0, 0),
        "MECÂNICA TOOLKIT | MEMORIAL DE CÁLCULO",
        bold=True,
        color=NAVY,
        size=8,
    )
    _write_cell(
        header_table.cell(0, 1),
        f"{_texto(metadata.get('codigo'), 'MC-000')} | REV. {_texto(metadata.get('revisao'), '00')}",
        color=MUTED,
        size=8,
        align=WD_ALIGN_PARAGRAPH.RIGHT,
    )

    footer = section.footer
    footer.paragraphs[0].paragraph_format.space_after = Pt(0)
    footer_table = footer.add_table(rows=1, cols=2, width=Inches(6.5))
    _apply_table_geometry(
        footer_table,
        [6000, 3360],
        indent_dxa=0,
        margins=zero_margins,
    )
    _remove_table_borders(footer_table)
    _write_cell(
        footer_table.cell(0, 0),
        "Documento editável - conferir código, revisão e aprovações antes da emissão.",
        color=MUTED,
        size=7.5,
    )
    page_paragraph = footer_table.cell(0, 1).paragraphs[0]
    page_paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    page_paragraph.paragraph_format.space_after = Pt(0)
    run = page_paragraph.add_run("Página ")
    _set_run_font(run, size=8, color=MUTED)
    _append_field(page_paragraph, "PAGE")
    run = page_paragraph.add_run(" de ")
    _set_run_font(run, size=8, color=MUTED)
    _append_field(page_paragraph, "NUMPAGES")


def _add_masthead(
    document: Document,
    metadata: Mapping[str, Any],
    status_text: str,
    status_color: str,
    status_detail: str,
    resumo: Sequence[Mapping[str, Any]],
) -> None:
    kicker = document.add_paragraph(style="Memorial Kicker")
    kicker.add_run("RELATÓRIO TÉCNICO PADRONIZADO")
    document.add_paragraph(_texto(metadata.get("titulo"), "Memorial de cálculo"), style="Title")
    document.add_paragraph(
        _texto(metadata.get("subtitulo"), "Memória de cálculo e verificação de engenharia"),
        style="Subtitle",
    )

    metadata_rows = [
        ["Projeto", metadata.get("projeto"), "Cliente", metadata.get("cliente")],
        ["Documento", metadata.get("codigo"), "Revisão", metadata.get("revisao")],
        ["Elaborado por", metadata.get("responsavel"), "Verificado por", metadata.get("verificador")],
        ["Situação", metadata.get("situacao"), "Emissão", metadata.get("emissao")],
    ]
    if metadata.get("snapshot_hash"):
        metadata_rows.append(
            ["Snapshot", str(metadata.get("snapshot_hash"))[:16] + "…", "Aprovado por", metadata.get("aprovador")]
        )
    table = document.add_table(rows=0, cols=4)
    for values in metadata_rows:
        row = table.add_row()
        for col_idx, value in enumerate(values):
            label = col_idx in (0, 2)
            if label:
                _shade_cell(row.cells[col_idx], BLUE_FILL)
            _write_cell(
                row.cells[col_idx],
                value,
                bold=label,
                color=NAVY if label else "26323D",
                size=8.5,
            )
    _apply_table_geometry(table, [1300, 3380, 1100, 3580])
    _set_table_borders(table)
    document.add_paragraph().paragraph_format.space_after = Pt(0)

    status_table = document.add_table(rows=1, cols=1)
    cell = status_table.cell(0, 0)
    _shade_cell(cell, status_color)
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_after = Pt(0)
    status_run = paragraph.add_run(f"{status_text} - {status_detail}")
    _set_run_font(status_run, size=9.5, color=WHITE, bold=True)
    _apply_table_geometry(status_table, [CONTENT_WIDTH_DXA])
    _set_table_borders(status_table, color=status_color, size=6)
    document.add_paragraph().paragraph_format.space_after = Pt(0)

    cards = list(resumo)[:4]
    while len(cards) < 4:
        cards.append({"rotulo": "Campo reservado", "valor": "A preencher"})
    cards_table = document.add_table(rows=1, cols=4)
    for idx, card in enumerate(cards):
        _shade_cell(cards_table.cell(0, idx), BLUE_FILL)
        cell = cards_table.cell(0, idx)
        cell.text = ""
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_after = Pt(0)
        label = paragraph.add_run(f"{_texto(card.get('rotulo'))}\n")
        _set_run_font(label, size=8, color=MUTED, bold=True)
        value = paragraph.add_run(_texto(card.get("valor")))
        _set_run_font(value, size=11, color=NAVY, bold=True)
    _apply_table_geometry(cards_table, [2340, 2340, 2340, 2340])
    _set_table_borders(cards_table)


def _add_executive_summary(
    document: Document,
    resumo_executivo: Mapping[str, Any],
    status: tuple[str, str, str],
) -> None:
    document.add_heading("1. Resumo executivo", level=1)
    document.add_paragraph(
        "Esta seção apresenta somente o essencial para uma leitura rápida. "
        "As premissas, equações, substituições e verificações completas começam na seção 3."
    )

    lead = document.add_paragraph(style="Memorial Note")
    _paragraph_box(lead, BLUE_FILL, border=BLUE)
    label = lead.add_run("Resultado geral. ")
    _set_run_font(label, size=10, color=NAVY, bold=True)
    value = lead.add_run(f"{status[0]}. {status[2]}")
    _set_run_font(value, size=10, color="26323D")

    rows = []
    for item in resumo_executivo.get("linhas", []):
        if isinstance(item, Mapping):
            rows.append([item.get("item"), item.get("valor"), item.get("leitura")])
        else:
            values = list(item)
            rows.append((values + ["", "", ""])[:3])
    _add_data_table(
        document,
        ["Item essencial", "Valor", "Leitura rápida"],
        rows,
        [2100, 3100, 4160],
        font_size=8.4,
    )
    document.add_paragraph(
        "Decisão de uso: consulte a conclusão, as pendências e o checklist antes de aprovar "
        "ou liberar o componente."
    )

def _add_revision_control(document: Document, metadata: Mapping[str, Any]) -> None:
    document.add_heading("2. Controle do documento", level=1)
    intro = document.add_paragraph(
        "Este bloco deve ser mantido em todas as disciplinas para garantir rastreabilidade, "
        "revisão técnica e emissão controlada do memorial."
    )
    intro.paragraph_format.keep_with_next = True
    rows = [
        [
            metadata.get("revisao"),
            metadata.get("emissao"),
            "Emissão automática do memorial de cálculo",
            metadata.get("responsavel"),
            metadata.get("verificador"),
        ]
    ]
    _add_data_table(
        document,
        ["Rev.", "Data", "Descrição", "Elaborado", "Verificado"],
        rows,
        [800, 1300, 3460, 1900, 1900],
        font_size=8.3,
    )


def _add_image(document: Document, imagem: Mapping[str, Any]) -> None:
    """Insere um PNG já renderizado, centralizado, com a legenda embaixo.

    A largura é fixada em polegadas em vez de deixar o Word escalar pelo DPI
    da imagem: assim o gráfico ocupa a mesma faixa útil das tabelas,
    qualquer que seja a resolução com que ele foi desenhado.
    """
    conteudo = imagem.get("png")
    if not conteudo:
        return
    paragrafo = document.add_paragraph()
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragrafo.add_run().add_picture(
        BytesIO(conteudo), width=Inches(float(imagem.get("largura_pol", 6.3)))
    )
    if imagem.get("legenda"):
        legenda = document.add_paragraph(style="Memorial Caption")
        legenda.alignment = WD_ALIGN_PARAGRAPH.CENTER
        legenda.add_run(_texto(imagem["legenda"]))


def _render_section(document: Document, section: Mapping[str, Any], bullet_id: int) -> None:
    if section.get("page_break_before"):
        document.add_page_break()
    document.add_heading(_texto(section.get("titulo")), level=int(section.get("nivel", 1)))
    for paragraph_text in section.get("paragrafos", []):
        document.add_paragraph(_texto(paragraph_text))
    if section.get("nota"):
        _add_note(document, _texto(section["nota"]))
    for item in section.get("bullets", []):
        _add_list_item(document, _texto(item), bullet_id)
    passos = list(section.get("passos", []))
    if passos:
        # Cada sequência representa um procedimento independente e deve
        # reiniciar em 1, mesmo quando outra lista numerada já apareceu.
        number_id = _create_numbering(document, numbered=True)
        for item in passos:
            _add_list_item(document, _texto(item), number_id)
    for formula in section.get("formulas", []):
        _add_formula(document, _texto(formula))
    for imagem in section.get("imagens", []):
        _add_image(document, imagem)
    for table_spec in section.get("tabelas", []):
        if table_spec.get("legenda"):
            caption = document.add_paragraph(style="Memorial Caption")
            caption.add_run(_texto(table_spec["legenda"]))
        _add_data_table(
            document,
            table_spec["cabecalhos"],
            table_spec["linhas"],
            table_spec["larguras"],
            font_size=float(table_spec.get("fonte", 8.5)),
            header_fill=table_spec.get("preenchimento", HEADER_FILL),
            zebra=bool(table_spec.get("zebra", True)),
        )


def gerar_memorial_word_padrao(
    *,
    metadata: Mapping[str, Any],
    resumo: Sequence[Mapping[str, Any]],
    resumo_executivo: Mapping[str, Any],
    status: tuple[str, str, str],
    secoes: Sequence[Mapping[str, Any]],
    quadro_dados: Sequence[Mapping[str, Any]],
    partes_complementares: Sequence[Sequence[Any]],
) -> bytes:
    """Gera um DOCX padronizado; outros módulos podem reutilizar este esquema."""
    document = Document()
    section = document.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1.0)
    section.right_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.0)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)
    # Força o mesmo cabeçalho em páginas pares, ímpares e na primeira página.
    # Algumas instalações do Word preservam a opção global de pares/ímpares,
    # o que fazia o cabeçalho desaparecer em páginas alternadas.
    document.settings.odd_and_even_pages_header_footer = False
    section.different_first_page_header_footer = False
    _configure_styles(document)
    _set_header_footer(document, metadata)
    bullet_id = _create_numbering(document, numbered=False)

    props = document.core_properties
    props.title = _texto(metadata.get("titulo"), "Memorial de cálculo")
    props.subject = _texto(metadata.get("subtitulo"), "Memória de cálculo")
    props.author = _texto(metadata.get("responsavel"), "Mecânica Toolkit")
    props.keywords = "memorial de cálculo; engenharia mecânica; verificação; revisão"
    props.comments = "Documento gerado pelo Mecânica Toolkit em estrutura editável e padronizada."

    _add_masthead(document, metadata, status[0], status[1], status[2], resumo)
    _add_executive_summary(document, resumo_executivo, status)
    _add_revision_control(document, metadata)
    for section_spec in secoes:
        _render_section(document, section_spec, bullet_id)

    numero_integracao = _texto(metadata.get("numero_integracao"), "11")
    numero_aprovacoes = _texto(metadata.get("numero_aprovacoes"), "12")
    document.add_heading(f"{numero_integracao}. Integração com outras partes do projeto", level=1)
    document.add_paragraph(
        "Use este registro para incorporar outras verificações ao mesmo memorial. "
        "Cada disciplina deve conservar código, revisão, responsável e conclusão próprios."
    )
    _add_data_table(
        document,
        ["Parte / módulo", "Documento", "Rev.", "Situação", "Responsável", "Observações"],
        partes_complementares,
        [1700, 1700, 700, 1400, 1600, 2260],
        font_size=8.0,
    )

    document.add_heading(f"{numero_aprovacoes}. Aprovações", level=1)
    approvals = [
        ["Elaboração", metadata.get("responsavel"), "", "Data: ____/____/________"],
        ["Verificação", metadata.get("verificador"), "", "Data: ____/____/________"],
        ["Aprovação", metadata.get("aprovador"), "", "Data: ____/____/________"],
    ]
    _add_data_table(
        document,
        ["Função", "Nome", "Assinatura", "Data"],
        approvals,
        [1500, 2300, 3260, 2300],
        font_size=8.5,
        zebra=False,
    )

    document.add_page_break()
    document.add_heading("Apêndice A - Quadro completo de entradas e resultados", level=1)
    document.add_paragraph(
        "Registro consolidado dos valores efetivamente usados. Campos manuais devem ser "
        "rastreáveis ao desenho, certificado, ensaio, norma ou hipótese de projeto."
    )
    appendix_rows = [
        [
            linha.get("Grupo", ""),
            linha.get("Grandeza", ""),
            linha.get("Símbolo", ""),
            linha.get("Valor", ""),
            linha.get("Unidade", ""),
            linha.get("Observação", ""),
        ]
        for linha in quadro_dados
    ]
    _add_data_table(
        document,
        ["Grupo", "Grandeza", "Símbolo", "Valor", "Unid.", "Observação"],
        appendix_rows,
        [1000, 2500, 900, 1300, 900, 2760],
        font_size=7.3,
    )

    document.add_heading("Apêndice B - Estrutura mínima para novas partes", level=1)
    document.add_paragraph(
        "Ao acrescentar outra disciplina, mantenha a sequência abaixo para preservar o padrão:"
    )
    appendix_number_id = _create_numbering(document, numbered=True)
    for item in (
        "Objetivo e escopo da parte adicionada.",
        "Referências, normas e propriedades adotadas.",
        "Premissas, unidades, combinações e limitações.",
        "Dados de entrada com origem rastreável.",
        "Equações, substituições numéricas e resultados intermediários.",
        "Critérios de aceitação, conclusão e recomendações.",
        "Responsável, verificador, código e revisão da parte.",
    ):
        _add_list_item(document, item, appendix_number_id)

    memoria = BytesIO()
    document.save(memoria)
    return memoria.getvalue()

def gerar_memorial_fadiga_word(
    dados: Mapping[str, Any],
    linhas_resumo: Sequence[Mapping[str, Any]],
) -> bytes:
    """Preenche o padrão corporativo com a memória da análise de fadiga."""
    status = _status_calculo(dados)
    fatores = dados.get("fatores", {})
    sut = float(dados.get("Sut", 0.0))
    sy = float(dados.get("Sy", 0.0))
    se_linha = float(dados.get("Se_linha", 0.0))
    se = float(dados.get("Se", 0.0))
    sigma_a_nom = float(dados.get("sigma_a_nom", 0.0))
    sigma_a = float(dados.get("sigma_a", 0.0))
    sigma_m = float(dados.get("sigma_m", 0.0))
    sigma_eq = float(dados.get("sigma_a_eq", math.inf))
    n_goodman = dados.get("n_goodman")
    n_soderberg = dados.get("n_soderberg")
    n_escoamento = dados.get("n_escoamento")
    ctemp = float(dados.get("Ctemp", 1.0))
    temp_c = float(dados.get("temperatura_c", 20.0))
    temp_f = float(dados.get("temperatura_f", 68.0))
    produto_marin = math.prod(float(valor) for valor in fatores.values())
    meta_fs = max(float(dados.get("fator_seguranca_minimo", 1.0) or 1.0), 0.01)
    vida_requerida = max(float(dados.get("vida_requerida_ciclos", 0.0) or 0.0), 0.0)
    ciclos_estimados = dados.get("ciclos_estimados")
    vida_infinita = bool(dados.get("vida_infinita", False))
    componente = _texto(dados.get("componente_analisado"), "Ponto crítico informado")
    referencia_projeto = _texto(dados.get("referencia_projeto"), "Não informada")
    fatores_validos = {
        "Goodman": n_goodman,
        "Soderberg": n_soderberg,
        "Escoamento no primeiro ciclo": n_escoamento,
    }
    fatores_validos = {
        nome: float(valor)
        for nome, valor in fatores_validos.items()
        if valor is not None and math.isfinite(float(valor))
    }
    criterio_governante, menor_n = (
        min(fatores_validos.items(), key=lambda item: item[1])
        if fatores_validos
        else ("Não calculado", None)
    )

    emission = _texto(dados.get("emissao"), datetime.now().strftime("%d/%m/%Y"))
    metadata = {
        "titulo": "Memorial de cálculo - análise de fadiga",
        "subtitulo": "Fatores de Marin, Goodman, Soderberg e estimativa de vida S-N",
        "projeto": dados.get("projeto"),
        "cliente": dados.get("cliente"),
        "codigo": dados.get("codigo_documento"),
        "revisao": dados.get("revisao"),
        "responsavel": dados.get("responsavel"),
        "verificador": dados.get("verificador"),
        "aprovador": dados.get("aprovador"),
        "situacao": dados.get("situacao_documento"),
        "emissao": emission,
    }
    resumo = [
        {"rotulo": "Resultado", "valor": status[0]},
        {"rotulo": "Se corrigido", "valor": f"{_numero(se, 1)} MPa"},
        {
            "rotulo": "Menor n / meta",
            "valor": f"{_numero(menor_n, 2)} / {_numero(meta_fs, 2)}",
        },
        {"rotulo": "Vida estimada", "valor": dados.get("resultado_vida")},
    ]
    requisito_vida_texto = (
        f"Requisito: {_inteiro(vida_requerida)} ciclos"
        if vida_requerida > 0
        else "Requisito de vida não informado"
    )
    resumo_executivo = {
        "linhas": [
            [
                "Componente e escopo",
                componente,
                f"Avaliação de fadiga sob {_texto(dados.get('tipo_carga')).lower()}.",
            ],
            [
                "Material",
                _texto(dados.get("material")),
                f"Sut = {_numero(sut, 1)} MPa; Sy = {_numero(sy, 1)} MPa.",
            ],
            [
                "Condição principal",
                f"T = {_numero(temp_c, 1)} °C; σa = {_numero(sigma_a, 1)} MPa; "
                f"σm = {_numero(sigma_m, 1)} MPa",
                "Valores adotados no ponto crítico.",
            ],
            [
                "Critério governante",
                f"{criterio_governante}: n = {_numero(menor_n, 2)}",
                f"Meta do projeto: n ≥ {_numero(meta_fs, 2)}.",
            ],
            [
                "Vida",
                _texto(dados.get("resultado_vida")),
                requisito_vida_texto,
            ],
            [
                "Referência do projeto",
                referencia_projeto,
                "Norma, especificação ou desenho que controla a aprovação.",
            ],
        ]
    }

    entrada_rows = []
    grupos_entrada = {"Material", "Condição", "Entalhe", "Tensões"}
    for linha in linhas_resumo:
        if linha.get("Grupo") in grupos_entrada:
            entrada_rows.append(
                [
                    linha.get("Grandeza"),
                    linha.get("Símbolo"),
                    linha.get("Valor"),
                    linha.get("Unidade"),
                    linha.get("Observação"),
                ]
            )

    if dados.get("modelo") == "norton":
        if temp_f <= 450.0:
            formula_temperatura = (
                f"T_F = {_numero(temp_f, 2)} °F <= 450 °F  =>  Ctemp = 1,000"
            )
        else:
            formula_temperatura = (
                f"Ctemp = 1 - 0,0058 x ({_numero(temp_f, 2)} - 450) "
                f"= {_numero(ctemp, 3)}"
            )
        texto_temperatura = (
            "Norton utiliza a temperatura em graus Fahrenheit, com correlação "
            "limitada a 550 °F (287,78 °C)."
        )
    else:
        formula_temperatura = (
            f"Shigley: kd(T = {_numero(temp_c, 2)} °C) = {_numero(ctemp, 3)}"
        )
        texto_temperatura = (
            "Shigley utiliza a temperatura em graus Celsius; para temperaturas elevadas, "
            "as propriedades mecânicas devem corresponder à condição de serviço."
        )

    marin_values = [
        fatores.get("Carregamento"),
        fatores.get("Tamanho"),
        fatores.get("Superfície"),
        fatores.get("Temperatura"),
        fatores.get("Confiabilidade"),
    ]
    marin_substitution = " x ".join(_numero(float(value), 4) for value in marin_values)

    if dados.get("modo_entalhe") == "Usar Kf com q":
        notch_formula = (
            f"Kf = 1 + q(Kt - 1) = 1 + {_numero(dados.get('q'), 2)}"
            f"({_numero(dados.get('Kt'), 3)} - 1) = {_numero(dados.get('fator_entalhe'), 3)}"
        )
    elif dados.get("modo_entalhe") == "Usar Kt diretamente":
        notch_formula = f"Fator aplicado = Kt = {_numero(dados.get('Kt'), 3)}"
    else:
        notch_formula = "Sem entalhe: fator aplicado = 1,000"

    goodman_formula = (
        f"1/nG = σa/Se + σm/Sut = {_numero(sigma_a, 2)}/{_numero(se, 2)} + "
        f"{_numero(sigma_m, 2)}/{_numero(sut, 2)}  =>  nG = {_numero(n_goodman, 3)}"
    )
    soderberg_formula = (
        f"1/nS = σa/Se + σm/Sy = {_numero(sigma_a, 2)}/{_numero(se, 2)} + "
        f"{_numero(sigma_m, 2)}/{_numero(sy, 2)}  =>  nS = {_numero(n_soderberg, 3)}"
        if n_soderberg is not None
        else "Soderberg não calculado: Sy não foi informado em domínio válido."
    )
    yield_formula = (
        f"ny = Sy/(σa + σm) = {_numero(sy, 2)}/"
        f"({_numero(sigma_a, 2)} + {_numero(sigma_m, 2)}) = {_numero(n_escoamento, 3)}"
        if n_escoamento is not None
        else "Verificação de escoamento não calculada."
    )
    life_formula = (
        f"σa,eq = σa/(1 - σm/Sut) = {_numero(sigma_a, 2)}/"
        f"(1 - {_numero(sigma_m, 2)}/{_numero(sut, 2)}) = {_numero(sigma_eq, 2)} MPa"
    )

    if vida_requerida <= 0:
        referencia_vida = "Requisito não informado"
        interpretacao_vida = "Pendente definir requisito"
    else:
        referencia_vida = f"N ≥ {_inteiro(vida_requerida)} ciclos"
        vida_atende = vida_infinita or (
            ciclos_estimados is not None
            and math.isfinite(float(ciclos_estimados))
            and float(ciclos_estimados) >= vida_requerida
        )
        interpretacao_vida = "Atende" if vida_atende else "Não atende"

    resultado_rows = [
        [
            "Goodman modificado",
            _numero(n_goodman, 3),
            f"n ≥ {_numero(meta_fs, 2)}",
            "Atende" if n_goodman is not None and n_goodman >= meta_fs else "Não atende",
        ],
        [
            "Soderberg",
            _numero(n_soderberg, 3),
            f"n ≥ {_numero(meta_fs, 2)}",
            "Atende" if n_soderberg is not None and n_soderberg >= meta_fs else "Não atende",
        ],
        [
            "Escoamento no 1º ciclo",
            _numero(n_escoamento, 3),
            f"n ≥ {_numero(meta_fs, 2)}",
            "Atende" if n_escoamento is not None and n_escoamento >= meta_fs else "Não atende",
        ],
        [
            "Vida S-N",
            _texto(dados.get("resultado_vida")),
            referencia_vida,
            interpretacao_vida,
        ],
    ]

    observacao_projeto = _texto(dados.get("observacoes_memorial"), "")
    scope_paragraphs = [
        "Este memorial registra a avaliação de fadiga do ponto crítico informado, "
        "incluindo correções de Marin, efeito da tensão média, verificação de escoamento "
        "e estimativa de vida pelo método tensão-vida.",
        "O documento é editável e foi estruturado para receber outras partes do projeto "
        "sem alterar a identificação, o controle de revisão e a hierarquia técnica.",
    ]
    if observacao_projeto:
        scope_paragraphs.append(f"Observação do projeto: {observacao_projeto}")

    referencia_informada = bool(str(dados.get("referencia_projeto") or "").strip())
    vida_informada = vida_requerida > 0
    pendencias_rows = [
        [
            "Norma, especificação ou desenho",
            referencia_projeto,
            "Definida" if referencia_informada else "Pendente",
            "Confirmar a base contratual antes da emissão final.",
        ],
        [
            "Material e propriedades",
            f"{_texto(dados.get('material'))}; Sut = {_numero(sut, 1)} MPa; Sy = {_numero(sy, 1)} MPa",
            "Verificar",
            "Rastrear os valores ao certificado, norma ou ensaio.",
        ],
        [
            "Geometria e ponto crítico",
            f"{componente}; d equivalente = {_numero(dados.get('diametro_mm'), 2)} mm",
            "Verificar",
            "Conferir desenho, seção resistente e posição das tensões.",
        ],
        [
            "Entalhe",
            f"{_texto(dados.get('modo_entalhe'))}; fator = {_numero(dados.get('fator_entalhe'), 3)}",
            "Verificar",
            "Confirmar Kt, q ou Kf para o raio e acabamento reais.",
        ],
        [
            "Vida mínima requerida",
            _inteiro(vida_requerida) + " ciclos" if vida_informada else "Não informada",
            "Definida" if vida_informada else "Pendente",
            "Comparar com o requisito funcional e a política de inspeção.",
        ],
        [
            "Ambiente e histórico de carga",
            "Corrosão, temperatura variável e dano acumulado não incluídos automaticamente",
            "Avaliar aplicabilidade",
            "Adicionar fatores, espectro ou regra de dano quando necessários.",
        ],
    ]

    sections = [
        {
            "titulo": "3. Objetivo e escopo",
            "paragrafos": scope_paragraphs,
            "nota": "A conclusão é válida somente para os dados, critérios e limitações registrados neste memorial.",
        },
        {
            "titulo": "4. Referências e sequência de cálculo",
            "paragrafos": [
                f"Referência de cálculo ativa: {_texto(dados.get('fonte'))}.",
                f"Referência do projeto: {referencia_projeto}.",
                "As equações são aplicadas em unidades SI: MPa, mm e °C, com conversão explícita para °F quando exigida por Norton.",
            ],
            "passos": [
                "Validar material, unidades, geometria, carregamento e ponto crítico.",
                "Estabelecer a resistência de fadiga de referência do material.",
                "Aplicar os fatores de Marin, incluindo a correção de temperatura.",
                "Aplicar o tratamento de concentração de tensões ou justificar sua ausência.",
                "Calcular Goodman, Soderberg e escoamento no primeiro ciclo.",
                "Estimar a vida S-N com a correção da tensão média.",
                "Comparar os resultados com as metas do projeto e registrar pendências.",
            ],
        },
        {
            "titulo": "5. Premissas, domínio e limitações",
            "bullets": [
                "Carregamento proporcional e tensão média de tração no ponto crítico.",
                "Modelo tensão-vida destinado principalmente à fadiga de alto ciclo.",
                "Correlações de tamanho, superfície e temperatura fundamentadas principalmente em aços.",
                "Efeitos de corrosão, tensões residuais, dano acumulado variável, fluência e mecânica da fratura não são incluídos automaticamente.",
                "As propriedades Sut e Sy devem representar o material, o tratamento e a temperatura real de operação.",
                "Curvas S-N e fatores experimentais do fabricante ou da norma têm preferência sobre estimativas gerais.",
            ],
        },
        {
            "titulo": "6. Dados de entrada e rastreabilidade",
            "paragrafos": [
                "A tabela a seguir reúne os dados de material, condição, entalhe e tensões usados na análise. A origem de cada entrada deve permanecer identificável."
            ],
            "tabelas": [
                {
                    "legenda": "Tabela 1 - Entradas efetivamente usadas no cálculo.",
                    "cabecalhos": ["Grandeza", "Símbolo", "Valor", "Unid.", "Origem / observação"],
                    "linhas": entrada_rows,
                    "larguras": [2500, 900, 1400, 900, 3660],
                    "fonte": 7.8,
                }
            ],
        },
        {
            "titulo": "7. Memória de cálculo",
            "paragrafos": [
                "A partir deste ponto o documento apresenta o raciocínio completo, com equações, substituições numéricas e resultados intermediários."
            ],
        },
        {
            "titulo": "7.1 Resistência de fadiga de referência",
            "nivel": 2,
            "formulas": [f"Se' = {_numero(se_linha, 2)} MPa"],
        },
        {
            "titulo": "7.2 Correção de temperatura",
            "nivel": 2,
            "paragrafos": [
                f"Temperatura informada: {_numero(dados.get('temperatura_entrada'), 2)} {_texto(dados.get('unidade_temperatura'))}. "
                f"Equivalência usada: {_numero(temp_c, 2)} °C = {_numero(temp_f, 2)} °F.",
                texto_temperatura,
            ],
            "formulas": [formula_temperatura],
        },
        {
            "titulo": "7.3 Equação de Marin",
            "nivel": 2,
            "formulas": [
                "Se = Se' x Ccarreg x Ctamanho x Csuperf x Ctemp x Cconf",
                f"Se = {_numero(se_linha, 2)} x {marin_substitution} = {_numero(se, 2)} MPa",
                f"Produto dos fatores = {_numero(produto_marin, 4)}",
            ],
        },
        {
            "titulo": "7.4 Entalhe e tensões efetivas",
            "nivel": 2,
            "formulas": [
                notch_formula,
                f"σa = fator x σa,nom = {_numero(dados.get('fator_entalhe'), 3)} x {_numero(sigma_a_nom, 2)} = {_numero(sigma_a, 2)} MPa",
                f"σm = {_numero(sigma_m, 2)} MPa",
            ],
        },
        {
            "titulo": "7.5 Critérios de segurança",
            "nivel": 2,
            "formulas": [goodman_formula, soderberg_formula, yield_formula],
        },
        {
            "titulo": "7.6 Estimativa de vida S-N",
            "nivel": 2,
            "paragrafos": [
                f"Resistência estimada em 10³ ciclos: Sm = {_numero(dados.get('Sm'), 2)} MPa. "
                f"Resultado do modelo: {_texto(dados.get('resultado_vida'))}."
            ],
            "formulas": [life_formula],
            "nota": "A vida calculada é uma estimativa. Dados S-N experimentais e o espectro real de carregamento devem prevalecer em projeto crítico.",
        },
        {
            "titulo": "8. Resultados e critérios de aceitação",
            "tabelas": [
                {
                    "legenda": "Tabela 2 - Síntese das verificações.",
                    "cabecalhos": ["Critério", "Resultado", "Referência de aceitação", "Interpretação"],
                    "linhas": resultado_rows,
                    "larguras": [2300, 1500, 2400, 3160],
                    "fonte": 8.2,
                }
            ],
            "nota": (
                f"A meta adotada é n ≥ {_numero(meta_fs, 2)}. "
                + (
                    f"A vida mínima adotada é {_inteiro(vida_requerida)} ciclos."
                    if vida_informada
                    else "A vida mínima requerida não foi informada e permanece como pendência."
                )
            ),
        },
        {
            "titulo": "9. Conclusão e recomendações",
            "paragrafos": [
                f"Conclusão automática: {status[0]}. {status[2]}",
                f"Critério governante: {criterio_governante}, n = {_numero(menor_n, 3)}, para meta n ≥ {_numero(meta_fs, 2)}.",
                f"Limite corrigido adotado: Se = {_numero(se, 2)} MPa. "
                f"Amplitude equivalente de Goodman: {_numero(sigma_eq, 2)} MPa.",
            ],
            "bullets": [
                "Confirmar a origem das propriedades mecânicas e da curva S-N.",
                "Confirmar Kt, q ou Kf com a geometria, acabamento e raio reais.",
                "Comparar a vida estimada com o número de ciclos requerido e com a política de inspeção.",
                "Reavaliar a seção, o acabamento ou o material quando o fator de segurança ficar abaixo da meta.",
                "Submeter o memorial à verificação independente antes da emissão final.",
            ],
        },
        {
            "titulo": "10. Hipóteses, pendências e ações",
            "paragrafos": [
                "Este registro separa resultados calculados de confirmações documentais ou avaliações adicionais necessárias à liberação."
            ],
            "tabelas": [
                {
                    "legenda": "Tabela 3 - Registro de pendências e ações de verificação.",
                    "cabecalhos": ["Item", "Base adotada", "Situação", "Ação antes da emissão"],
                    "linhas": pendencias_rows,
                    "larguras": [2000, 2800, 1500, 3060],
                    "fonte": 7.7,
                }
            ],
        },
        {
            "titulo": "10.1 Checklist de verificação antes da emissão",
            "nivel": 2,
            "bullets": [
                "Entradas, unidades e conversões conferidas por pessoa diferente do elaborador.",
                "Material, tratamento, temperatura e propriedades rastreados à fonte aplicável.",
                "Carregamentos, combinações e ponto crítico compatíveis com o modelo estrutural.",
                "Concentrações de tensão e acabamento compatíveis com a geometria fabricada.",
                "Metas de fator de segurança e vida aprovadas pelo responsável do projeto.",
                "Pendências da Tabela 3 encerradas ou formalmente aceitas.",
                "Código, revisão, responsáveis e situação do documento atualizados.",
            ],
        },
    ]

    quadro_completo = list(linhas_resumo) + [
        {
            "Grupo": "Critérios",
            "Grandeza": "Fator de segurança mínimo",
            "Símbolo": "nmin",
            "Valor": _numero(meta_fs, 2),
            "Unidade": "-",
            "Observação": "Meta informada para a aceitação do projeto",
        },
        {
            "Grupo": "Critérios",
            "Grandeza": "Vida mínima requerida",
            "Símbolo": "Nreq",
            "Valor": _inteiro(vida_requerida) if vida_informada else "Não informada",
            "Unidade": "ciclos" if vida_informada else "-",
            "Observação": "Requisito funcional ou contratual",
        },
        {
            "Grupo": "Rastreabilidade",
            "Grandeza": "Componente ou ponto crítico",
            "Símbolo": "-",
            "Valor": componente,
            "Unidade": "-",
            "Observação": "Escopo físico da análise",
        },
        {
            "Grupo": "Rastreabilidade",
            "Grandeza": "Norma, especificação ou desenho",
            "Símbolo": "-",
            "Valor": referencia_projeto,
            "Unidade": "-",
            "Observação": "Base de aprovação do projeto",
        },
    ]

    complement_parts = [
        ["Análise de fadiga", metadata["codigo"], metadata["revisao"], "Incluída", metadata["responsavel"], status[0]],
        ["Análise estática", "A preencher", "-", "Não incluída", "A preencher", "Anexar resultados e conclusão"],
        ["Círculo de Mohr", "A preencher", "-", "Não incluído", "A preencher", "Anexar estado e transformações"],
        ["Assistente de cargas", "A preencher", "-", "Não incluído", "A preencher", "Rastrear cargas até as tensões"],
        ["Projeto de parafusos", "A preencher", "-", "Não incluído", "A preencher", "Anexar junta e verificações"],
        ["Estruturas de aço", "A preencher", "-", "Não incluída", "A preencher", "Anexar barras, ligações e combinações"],
    ]

    return gerar_memorial_word_padrao(
        metadata=metadata,
        resumo=resumo,
        resumo_executivo=resumo_executivo,
        status=status,
        secoes=sections,
        quadro_dados=quadro_completo,
        partes_complementares=complement_parts,
    )
