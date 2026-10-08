"""Relatório em PDF do degrau de escada em grade: resumo, verificações, memorial e catálogo.

Gera, com o reportlab, o documento que a página oferece para baixar: o quadro-resumo, a tabela das
38 verificações com o item da norma em cada uma, a geometria da escada, o memorial do modelo
adotado, os 64 modelos do catálogo, o texto da requisição e os avisos fixos. Sem Streamlit; usa a
fonte TrueType com acentos e símbolos que :mod:`core.pdf_fonts` encontrar.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from html import escape
from io import BytesIO
from typing import Any

from core import degrau_escada as de
from core import degrau_registro as reg
from core.pdf_fonts import fonte_pdf, texto_para_fonte

_COR_STATUS = {
    "OK": "#D9F2E3",
    "NÃO OK": "#F8D4D4",
    "ALERTA": "#FCEBC4",
    "INFO": "#D8E8F8",
    "N/A": "#E6E9ED",
}


def reg_n(valor: float, casas: int = 2) -> str:
    """Número em pt-BR sem zeros inúteis (a mesma formatação das tabelas do registro)."""
    return de.numero_pt(valor, casas)


def _data_texto(valor: Any) -> str:
    if isinstance(valor, (date, datetime)):
        return valor.strftime("%d/%m/%Y")
    return str(valor or "").strip()


def gerar_pdf_degrau(
    r: de.ResultadoEscada, identificacao: Mapping[str, Any] | None = None
) -> bytes:
    """PDF (A4 em paisagem) do cálculo. ``identificacao``: obra, tag, responsavel e data."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            KeepTogether,
            LongTable,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            TableStyle,
        )
    except ImportError as erro:
        raise RuntimeError("A exportação PDF requer reportlab.") from erro

    ident = dict(identificacao or {})
    fonte = fonte_pdf()
    azul = colors.HexColor("#16324F")
    azul_medio = colors.HexColor("#24577A")
    azul_claro = colors.HexColor("#EAF2F8")
    cinza = colors.HexColor("#5F6B76")
    borda = colors.HexColor("#C9D4DE")
    texto_corpo = colors.HexColor("#26323D")

    def t(texto: Any) -> str:
        """Texto seguro para o Paragraph: escapado e adaptado à fonte."""
        return escape(texto_para_fonte(str(texto), fonte))

    base = getSampleStyleSheet()
    estilo = {
        "titulo": ParagraphStyle(
            "DegrauTitulo",
            parent=base["Title"],
            fontName=fonte.negrito,
            fontSize=16,
            leading=19,
            textColor=azul,
            alignment=TA_LEFT,
            spaceAfter=2 * mm,
        ),
        "subtitulo": ParagraphStyle(
            "DegrauSubtitulo",
            parent=base["Normal"],
            fontName=fonte.regular,
            fontSize=8.5,
            leading=11,
            textColor=cinza,
            spaceAfter=3 * mm,
        ),
        "h1": ParagraphStyle(
            "DegrauH1",
            parent=base["Heading1"],
            fontName=fonte.negrito,
            fontSize=11,
            leading=14,
            textColor=azul,
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
            keepWithNext=True,
        ),
        "corpo": ParagraphStyle(
            "DegrauCorpo",
            parent=base["Normal"],
            fontName=fonte.regular,
            fontSize=8.2,
            leading=10.6,
            textColor=texto_corpo,
            spaceAfter=1.2 * mm,
        ),
        "legenda": ParagraphStyle(
            "DegrauLegenda",
            parent=base["Normal"],
            fontName=fonte.regular,
            fontSize=7.2,
            leading=9,
            textColor=cinza,
            spaceAfter=1.5 * mm,
        ),
        "celula": ParagraphStyle(
            "DegrauCelula",
            parent=base["Normal"],
            fontName=fonte.regular,
            fontSize=6.7,
            leading=8.2,
            textColor=texto_corpo,
        ),
        "celula_negrito": ParagraphStyle(
            "DegrauCelulaNegrito",
            parent=base["Normal"],
            fontName=fonte.negrito,
            fontSize=6.7,
            leading=8.2,
            textColor=colors.white,
        ),
        "codigo": ParagraphStyle(
            "DegrauCodigo",
            parent=base["Normal"],
            fontName=fonte.regular,
            fontSize=8.2,
            leading=11,
            textColor=texto_corpo,
            backColor=azul_claro,
            borderPadding=(4, 4, 4, 4),
            spaceAfter=2 * mm,
        ),
    }

    def paragrafo(texto: Any, nome: str = "corpo") -> Paragraph:
        return Paragraph(t(texto), estilo[nome])

    def tabela(
        cabecalhos: Sequence[str],
        linhas: Sequence[Sequence[Any]],
        larguras_mm: Sequence[float],
        *,
        status_coluna: int | None = None,
        destacar_linha: int | None = None,
    ) -> LongTable:
        dados: list[list[Any]] = [[paragrafo(c, "celula_negrito") for c in cabecalhos]]
        for linha in linhas:
            dados.append([paragrafo(c, "celula") for c in linha])
        tab = LongTable(dados, colWidths=[w * mm for w in larguras_mm], repeatRows=1)
        comandos: list[tuple[Any, ...]] = [
            ("BACKGROUND", (0, 0), (-1, 0), azul_medio),
            ("GRID", (0, 0), (-1, -1), 0.25, borda),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2.2),
            ("TOPPADDING", (0, 0), (-1, -1), 1.6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
        ]
        if status_coluna is not None:
            for numero, linha in enumerate(linhas, start=1):
                cor = _COR_STATUS.get(str(linha[status_coluna]))
                if cor:
                    comandos.append(
                        (
                            "BACKGROUND",
                            (status_coluna, numero),
                            (status_coluna, numero),
                            colors.HexColor(cor),
                        )
                    )
        if destacar_linha is not None:
            comandos.append(
                (
                    "BACKGROUND",
                    (0, destacar_linha + 1),
                    (-1, destacar_linha + 1),
                    colors.HexColor("#FFF3C4"),
                )
            )
        tab.setStyle(TableStyle(comandos))
        return tab

    # ------------------------------------------------------------------ conteúdo
    e, g, ln, a = r.entrada, r.geometria, r.lances, r.adotado
    historia: list[Any] = [
        paragrafo("Degrau de escada em grade de piso eletrofundida", "titulo"),
        paragrafo(
            f"Catálogo Selmec “Degraus” (DS) · NR-12 Anexo III · NR-22 · Critério Anglo "
            f"AA-BR-DPST-DR-0001 Rev.1 · NBR 8800:2008 · NBR 6120 · ISO 14122-3 — modelo adotado "
            f"{a.modelo.nome}",
            "subtitulo",
        ),
    ]
    identificacao_linhas = [
        ["Obra", ident.get("obra") or "-", "TAG", ident.get("tag") or "-"],
        [
            "Responsável",
            ident.get("responsavel") or "-",
            "Data",
            _data_texto(ident.get("data")) or "-",
        ],
        ["Enquadramento", de.ENQUADRAMENTOS[e.enquadramento], "Uso (Anglo 10.2)", de.USOS[e.uso]],
    ]
    historia.append(
        tabela(["Dado", "Valor", "Dado", "Valor"], identificacao_linhas, [32, 90, 32, 89])
    )

    historia.append(paragrafo("Quadro-resumo", "h1"))
    contagem = de.texto_da_contagem(r.contagem)
    resumo = [
        ["Modelo adotado", f"{a.modelo.nome} — {r.selecao.mensagem}"],
        [
            "Espelho × piso",
            f"{reg_n(g.h_mm)} × {reg_n(g.b_mm)} mm (2h + b = {reg_n(g.blondel_mm)} mm; "
            f"α = {reg_n(g.alfa_graus)}°)",
        ],
        [
            "Profundidade × comprimento",
            f"C = {reg_n(g.C_mm)} × L = {reg_n(e.L_mm)} mm (F = {g.F_mm} mm; r = {reg_n(g.r_mm)} mm)",
        ],
        [
            "Espelhos e degraus",
            f"{g.n} espelhos; {ln.n_degraus_grade} degraus em grade; {ln.texto}",
        ],
        ["Aproveitamento máximo", f"{reg_n(100 * r.aproveitamento_maximo, 1)} %"],
        [
            "Peso",
            f"{reg_n(r.peso_unitario_kg)} kg por degrau; {reg_n(r.peso_total_kg, 1)} kg no total "
            f"({ln.n_degraus_grade} degraus)",
        ],
        ["Situação da geometria", g.faixa.mensagem],
        ["Status geral", f"{r.status} — {contagem}"],
    ]
    historia.append(tabela(["Item", "Resultado"], resumo, [55, 188]))
    for aviso in r.avisos:
        historia.append(Spacer(1, 1.5 * mm))
        historia.append(paragrafo(f"Aviso: {aviso}"))

    historia.append(paragrafo("1. Verificações (38) com o item da norma", "h1"))
    historia.append(
        paragrafo(
            "Valor: o que atua (resistência) ou o valor adotado (limites). Limite: a resistência ou "
            "o que a norma exige; nas faixas, a faixa vem na observação. Aproveitamento só nas "
            "verificações de resistência.",
            "legenda",
        )
    )
    tabela_v = reg.tabela_de_verificacoes(r)
    historia.append(
        tabela(
            list(reg.COLUNAS_VERIFICACAO),
            [
                [
                    linha["Verificação"],
                    linha["Norma/item"],
                    linha["Valor"],
                    linha["Limite"],
                    "—"
                    if linha["Aproveitamento (%)"] is None
                    else f"{linha['Aproveitamento (%)']:.1f}".replace(".", ","),
                    linha["Status"],
                    linha["Observação"],
                ]
                for linha in tabela_v
            ],
            [58, 40, 21, 21, 15, 14, 74],
            status_coluna=5,
        )
    )

    historia.append(paragrafo("2. Geometria da escada", "h1"))
    historia.append(
        tabela(
            ["Grandeza", "Valor", "Un.", "Cálculo"],
            reg.linhas_da_geometria(r),
            [60, 40, 12, 131],
        )
    )

    historia.append(paragrafo(f"3. Memorial do modelo adotado ({a.modelo.nome})", "h1"))
    historia.append(
        tabela(
            ["Grandeza", "Valor", "Un.", "Cálculo"],
            reg.linhas_do_dimensionamento(r),
            [60, 40, 12, 131],
        )
    )

    historia.append(paragrafo("4. Os 64 modelos do catálogo", "h1"))
    historia.append(
        paragrafo(
            "u = aproveitamento de cada verificação do degrau (flexão distribuída e concentrada, "
            "cisalhamento, flecha distribuída e flecha ISO). Atende: u máx ≤ 1, L dentro do máximo "
            "recomendado, L ≥ 500 mm e t ≥ 2,00 mm. O modelo adotado está em destaque.",
            "legenda",
        )
    )
    linhas_modelos = []
    destaque = None
    for indice, x in enumerate(r.tabela_modelos):
        if x.modelo.nome == a.modelo.nome:
            destaque = indice
        linhas_modelos.append(
            [
                x.modelo.nome,
                f"{x.modelo.h_b_mm} x {de.numero_pt_fixo(x.modelo.t_b_mm)}",
                x.modelo.L_max_mm,
                x.n_bb,
                x.n_ef,
                reg_n(x.lam, 1),
                reg_n(x.MRd_kNm, 4),
                reg_n(x.peso_degrau_kg, 3),
                reg_n(x.u_flex_d, 3),
                reg_n(x.u_flex_c, 3),
                reg_n(x.u_cis, 3),
                reg_n(x.u_fl_d, 3),
                reg_n(x.u_fl_i, 3),
                reg_n(x.u_max, 3),
                "SIM" if x.atende else "NÃO",
                "SIM" if x.na_preferencia else "NÃO",
            ]
        )
    historia.append(
        tabela(
            [
                "Modelo",
                "Barra h x t (mm)",
                "L máx (mm)",
                "n_bb",
                "n_ef",
                "λ",
                "M_Rd (kN·m)",
                "Peso (kg)",
                "u flex. dist.",
                "u flex. conc.",
                "u cis.",
                "u flecha dist.",
                "u flecha ISO",
                "u máx",
                "Atende",
                "Na pref.",
            ],
            linhas_modelos,
            [22, 19, 14, 10, 10, 12, 17, 15, 15, 15, 12, 15, 15, 13, 12, 12],
            destacar_linha=destaque,
        )
    )

    historia.append(paragrafo("5. Texto para a requisição de compra", "h1"))
    historia.append(
        KeepTogether(
            [
                Paragraph(t(r.especificacao), estilo["codigo"]),
                paragrafo(
                    f"Peso unitário {reg_n(r.peso_unitario_kg)} kg; peso total "
                    f"{reg_n(r.peso_total_kg, 1)} kg ({ln.n_degraus_grade} degraus). Estimativa.",
                    "legenda",
                ),
            ]
        )
    )

    historia.append(paragrafo("6. Conflitos entre normas, avisos e limites do cálculo", "h1"))
    historia.append(paragrafo("Conflitos entre normas", "corpo"))
    for item in reg.CONFLITOS_ENTRE_NORMAS:
        historia.append(paragrafo(f"• {item}"))
    historia.append(paragrafo("Avisos", "corpo"))
    for item in reg.AVISOS_FIXOS:
        historia.append(paragrafo(f"• {item}"))
    historia.append(paragrafo("Esta página não faz", "corpo"))
    for item in reg.NAO_FAZ:
        historia.append(paragrafo(f"• {item}"))
    historia.append(paragrafo("Referências", "corpo"))
    for item in reg.REFERENCIAS:
        historia.append(paragrafo(f"• {item}", "legenda"))

    # ------------------------------------------------------------------ documento
    memoria = BytesIO()
    titulo_doc = f"Degrau de escada em grade — {a.modelo.nome}"

    def rodape(canvas: Any, documento: Any) -> None:
        canvas.saveState()
        canvas.setFont(fonte.regular, 7)
        canvas.setFillColor(cinza)
        canvas.drawString(12 * mm, 7 * mm, texto_para_fonte(titulo_doc, fonte))
        canvas.drawRightString(
            landscape(A4)[0] - 12 * mm,
            7 * mm,
            texto_para_fonte(f"Mecânica Toolkit · página {documento.page}", fonte),
        )
        canvas.restoreState()

    documento = SimpleDocTemplate(
        memoria,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=13 * mm,
        title=titulo_doc,
        author=str(ident.get("responsavel") or "Mecânica Toolkit"),
        subject="Degrau de escada em grade eletrofundida: verificação e seleção do modelo",
    )
    documento.build(historia, onFirstPage=rodape, onLaterPages=rodape)
    return memoria.getvalue()
