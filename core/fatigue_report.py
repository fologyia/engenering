"""Geração do memorial de cálculo da análise de fadiga em PDF."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import datetime
from html import escape
from io import BytesIO
from typing import Any


def _texto(valor: Any) -> str:
    """Converte valores para texto seguro nos parágrafos do ReportLab."""
    substituicoes = {
        "—": "-",
        "–": "-",
        "×": "x",
        "·": "*",
        "≤": "<=",
        "≥": ">=",
        "∞": "infinito",
        "σ": "sigma",
        "τ": "tau",
        "⁸": "8",
        "³": "3",
    }
    resultado = str(valor)
    for origem, destino in substituicoes.items():
        resultado = resultado.replace(origem, destino)
    return escape(resultado)


def _numero(valor: float | None, casas: int = 3) -> str:
    if valor is None:
        return "Não calculado"
    if math.isinf(valor):
        return "Infinito"
    return f"{valor:.{casas}f}".replace(".", ",")


def _status_projeto(dados: Mapping[str, Any]) -> tuple[str, str]:
    fatores = [
        dados.get("n_goodman"),
        dados.get("n_soderberg"),
        dados.get("n_escoamento"),
    ]
    validos = [float(valor) for valor in fatores if valor is not None]
    if not validos:
        return "RESULTADO INCONCLUSIVO", "#805B10"
    menor = min(validos)
    if menor < 1.0:
        return "NÃO ATENDE - há fator de segurança menor que 1,0", "#A52A2A"
    if menor < 1.5:
        return "ATENÇÃO - menor fator de segurança entre 1,0 e 1,5", "#805B10"
    return "ATENDE - fatores de segurança calculados >= 1,5", "#1D6B45"


def gerar_memorial_fadiga_pdf(
    dados: Mapping[str, Any],
    linhas_resumo: Sequence[Mapping[str, Any]],
) -> bytes:
    """Gera um PDF A4 completo e retorna seu conteúdo em bytes."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            KeepTogether,
            LongTable,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as erro:
        raise RuntimeError(
            "A exportação em PDF requer o pacote reportlab. "
            "Instale as dependências de requirements.txt."
        ) from erro

    azul = colors.HexColor("#16324F")
    azul_claro = colors.HexColor("#EAF2F8")
    cinza = colors.HexColor("#5F6B76")
    cinza_claro = colors.HexColor("#F4F6F8")
    borda = colors.HexColor("#C9D4DE")
    branco = colors.white

    memoria = BytesIO()
    documento = SimpleDocTemplate(
        memoria,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Memorial de cálculo - análise de fadiga",
        author=str(dados.get("responsavel") or "Mecânica Toolkit"),
        subject="Fatores de Marin, Goodman, Soderberg e curva S-N",
    )

    estilos_base = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloMemorial",
        parent=estilos_base["Title"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=23,
        textColor=azul,
        alignment=TA_LEFT,
        spaceAfter=5 * mm,
    )
    subtitulo = ParagraphStyle(
        "SubtituloMemorial",
        parent=estilos_base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=cinza,
        spaceAfter=4 * mm,
    )
    secao = ParagraphStyle(
        "SecaoMemorial",
        parent=estilos_base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=azul,
        spaceBefore=4 * mm,
        spaceAfter=2.5 * mm,
    )
    corpo = ParagraphStyle(
        "CorpoMemorial",
        parent=estilos_base["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#26323D"),
        spaceAfter=1.8 * mm,
    )
    formula = ParagraphStyle(
        "FormulaMemorial",
        parent=corpo,
        fontName="Courier",
        fontSize=8,
        leading=11,
        leftIndent=4 * mm,
        rightIndent=4 * mm,
        borderColor=borda,
        borderWidth=0.5,
        borderPadding=5,
        backColor=cinza_claro,
        spaceAfter=2 * mm,
    )
    pequeno = ParagraphStyle(
        "PequenoMemorial",
        parent=corpo,
        fontSize=6.7,
        leading=8.2,
        spaceAfter=0,
    )
    central = ParagraphStyle(
        "CentralMemorial",
        parent=corpo,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        spaceAfter=0,
    )
    status_texto = ParagraphStyle(
        "StatusMemorial",
        parent=central,
        textColor=branco,
    )
    pequeno_cabecalho = ParagraphStyle(
        "PequenoCabecalhoMemorial",
        parent=pequeno,
        fontName="Helvetica-Bold",
        textColor=branco,
    )

    gerado_em = datetime.now().astimezone().strftime("%d/%m/%Y às %H:%M")
    historia: list[Any] = []
    historia.append(Paragraph("Memorial de cálculo - análise de fadiga", titulo))
    historia.append(
        Paragraph(
            "Relatório gerado pelo Mecânica Toolkit com fatores de Marin, "
            "verificações de Goodman e Soderberg e estimativa de vida S-N.",
            subtitulo,
        )
    )

    identificacao = [
        ["Projeto", _texto(dados.get("projeto") or "Não informado")],
        ["Responsável", _texto(dados.get("responsavel") or "Não informado")],
        ["Referência", _texto(dados.get("fonte") or "Não informada")],
        ["Emissão", gerado_em],
    ]
    tabela_identificacao = Table(
        [[Paragraph(f"<b>{linha[0]}</b>", corpo), Paragraph(linha[1], corpo)] for linha in identificacao],
        colWidths=[34 * mm, 140 * mm],
    )
    tabela_identificacao.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), azul_claro),
                ("BOX", (0, 0), (-1, -1), 0.6, borda),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, borda),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    historia.append(tabela_identificacao)
    historia.append(Spacer(1, 4 * mm))

    texto_status, cor_status = _status_projeto(dados)
    status = Table(
        [[Paragraph(_texto(texto_status), status_texto)]],
        colWidths=[174 * mm],
    )
    status.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(cor_status)),
                ("TEXTCOLOR", (0, 0), (-1, -1), branco),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(cor_status)),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    historia.append(status)
    historia.append(Spacer(1, 4 * mm))

    cards = [
        ["Se corrigido", f"{_numero(dados.get('Se'), 1)} MPa"],
        ["Goodman", _numero(dados.get("n_goodman"), 2)],
        ["Soderberg", _numero(dados.get("n_soderberg"), 2)],
        ["Vida estimada", _texto(dados.get("resultado_vida") or "Não calculada")],
    ]
    tabela_cards = Table(
        [
            [Paragraph(f"<b>{_texto(card[0])}</b><br/>{_texto(card[1])}", central) for card in cards]
        ],
        colWidths=[43.5 * mm] * 4,
    )
    tabela_cards.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), azul_claro),
                ("BOX", (0, 0), (-1, -1), 0.6, borda),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, borda),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    historia.append(tabela_cards)

    historia.append(Paragraph("1. Dados de entrada", secao))
    historia.append(
        Paragraph(
            f"Material: <b>{_texto(dados.get('material'))}</b>. "
            f"Sut = <b>{_numero(dados.get('Sut'), 1)} MPa</b>; "
            f"Sy = <b>{_numero(dados.get('Sy'), 1)} MPa</b>; "
            f"carregamento = <b>{_texto(dados.get('tipo_carga'))}</b>; "
            f"diâmetro equivalente = <b>{_numero(dados.get('diametro_mm'), 2)} mm</b>.",
            corpo,
        )
    )
    historia.append(
        Paragraph(
            f"Tensões usadas: sigma_a,nom = {_numero(dados.get('sigma_a_nom'), 2)} MPa; "
            f"sigma_a = {_numero(dados.get('sigma_a'), 2)} MPa; "
            f"sigma_m = {_numero(dados.get('sigma_m'), 2)} MPa. "
            f"Tratamento de entalhe: {_texto(dados.get('modo_entalhe'))}.",
            corpo,
        )
    )

    historia.append(Paragraph("2. Correção de temperatura", secao))
    historia.append(
        Paragraph(
            f"Entrada: <b>{_numero(dados.get('temperatura_entrada'), 2)} "
            f"{_texto(dados.get('unidade_temperatura'))}</b>. Conversão: "
            f"<b>{_numero(dados.get('temperatura_c'), 2)} °C = "
            f"{_numero(dados.get('temperatura_f'), 2)} °F</b>.",
            corpo,
        )
    )
    if dados.get("modelo") == "norton":
        temperatura_f = float(dados.get("temperatura_f", 0.0))
        if temperatura_f <= 450.0:
            memoria_temperatura = (
                f"T_F = {temperatura_f:.2f} °F <= 450 °F  ->  Ctemp = 1,000"
            )
        else:
            ctemp = float(dados.get("Ctemp", 0.0))
            memoria_temperatura = (
                f"Ctemp = 1 - 0,0058 * ({temperatura_f:.2f} - 450) "
                f"= {ctemp:.3f}"
            )
        historia.append(Paragraph(_texto(memoria_temperatura), formula))
        historia.append(
            Paragraph(
                "A correlação de Norton usa graus Fahrenheit e é limitada a "
                "550 °F (287,78 °C).",
                corpo,
            )
        )
    else:
        historia.append(
            Paragraph(
                f"O modelo de Shigley usa a temperatura em °C. "
                f"Fator calculado: Ctemp = {_numero(dados.get('Ctemp'), 3)}.",
                formula,
            )
        )

    historia.append(Paragraph("3. Fatores de Marin", secao))
    fatores = dados.get("fatores", {})
    memoria_marin = (
        "Se = Se' * Ccarreg * Ctamanho * Csuperf * Ctemp * Cconf\n"
        f"Se = {_numero(dados.get('Se_linha'), 2)} * "
        f"{_numero(fatores.get('Carregamento'), 4)} * "
        f"{_numero(fatores.get('Tamanho'), 4)} * "
        f"{_numero(fatores.get('Superfície'), 4)} * "
        f"{_numero(fatores.get('Temperatura'), 4)} * "
        f"{_numero(fatores.get('Confiabilidade'), 4)}\n"
        f"Se = {_numero(dados.get('Se'), 2)} MPa"
    )
    historia.append(Paragraph(_texto(memoria_marin).replace("\n", "<br/>"), formula))

    historia.append(Paragraph("4. Critérios de segurança", secao))
    historia.append(
        Paragraph(
            _texto(
                f"Goodman: 1/nG = sigma_a/Se + sigma_m/Sut  ->  "
                f"nG = {_numero(dados.get('n_goodman'), 3)}"
            ),
            formula,
        )
    )
    historia.append(
        Paragraph(
            _texto(
                f"Soderberg: 1/nS = sigma_a/Se + sigma_m/Sy  ->  "
                f"nS = {_numero(dados.get('n_soderberg'), 3)}"
            ),
            formula,
        )
    )
    historia.append(
        Paragraph(
            _texto(
                f"Escoamento no 1º ciclo: ny = Sy/(sigma_a + sigma_m)  ->  "
                f"ny = {_numero(dados.get('n_escoamento'), 3)}"
            ),
            formula,
        )
    )

    historia.append(Paragraph("5. Estimativa de vida S-N", secao))
    historia.append(
        Paragraph(
            _texto(
                f"Amplitude equivalente de Goodman: sigma_a,eq = "
                f"{_numero(dados.get('sigma_a_eq'), 2)} MPa. "
                f"Resistência em 10^3 ciclos: Sm = {_numero(dados.get('Sm'), 2)} MPa. "
                f"Resultado: {dados.get('resultado_vida')}."
            ),
            corpo,
        )
    )

    historia.append(PageBreak())
    historia.append(Paragraph("6. Quadro completo de entradas e resultados", secao))
    cabecalho = ["Grupo", "Grandeza", "Símbolo", "Valor", "Unid.", "Observação"]
    linhas_tabela: list[list[Any]] = [
        [Paragraph(_texto(item), pequeno_cabecalho) for item in cabecalho]
    ]
    for linha in linhas_resumo:
        linhas_tabela.append(
            [
                Paragraph(_texto(linha.get("Grupo", "")), pequeno),
                Paragraph(_texto(linha.get("Grandeza", "")), pequeno),
                Paragraph(_texto(linha.get("Símbolo", "")), pequeno),
                Paragraph(_texto(linha.get("Valor", "")), pequeno),
                Paragraph(_texto(linha.get("Unidade", "")), pequeno),
                Paragraph(_texto(linha.get("Observação", "")), pequeno),
            ]
        )
    tabela_resumo = LongTable(
        linhas_tabela,
        colWidths=[18 * mm, 47 * mm, 17 * mm, 27 * mm, 17 * mm, 48 * mm],
        repeatRows=1,
    )
    tabela_resumo.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), azul),
                ("TEXTCOLOR", (0, 0), (-1, 0), branco),
                ("BOX", (0, 0), (-1, -1), 0.5, borda),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, borda),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [branco, cinza_claro]),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    historia.append(tabela_resumo)

    notas = KeepTogether(
        [
            Paragraph("7. Hipóteses e limitações", secao),
            Paragraph(
                "Os resultados são estimativas de engenharia baseadas nas entradas "
                "informadas e nas correlações indicadas. Verifique unidades, origem "
                "das propriedades, concentração de tensões, ambiente, histórico de "
                "carregamento e requisitos normativos antes da liberação do projeto.",
                corpo,
            ),
            Paragraph(
                "Para aplicações críticas, valide a curva S-N e os fatores de Marin "
                "com dados experimentais do material e da condição real de fabricação.",
                corpo,
            ),
        ]
    )
    historia.append(Spacer(1, 4 * mm))
    historia.append(notas)

    def rodape(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(borda)
        canvas.setLineWidth(0.4)
        canvas.line(16 * mm, 13 * mm, 194 * mm, 13 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(cinza)
        canvas.drawString(16 * mm, 8.5 * mm, "Mecânica Toolkit - memorial de fadiga")
        canvas.drawRightString(
            194 * mm,
            8.5 * mm,
            f"Página {doc.page}",
        )
        canvas.restoreState()

    documento.build(historia, onFirstPage=rodape, onLaterPages=rodape)
    return memoria.getvalue()
