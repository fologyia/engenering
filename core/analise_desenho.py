"""Análise sobre o desenho: marcas num desenho, cada uma ligada a uma análise do Montador.

O desenho entra como fundo (imagem, PDF ou DXF). Cada marca fica num ponto dele e escolhe um modelo
do Montador de fórmulas (pino, chapa com furo, eixo, chaveta...), com os números daquela parte. A conta
é a do Montador, sem cópia: ``montar`` + ``isolar``. Com o valor da letra principal preenchido, a marca
confere (passou ou não, com o uso de cada condição); sem ele, diz até onde a letra pode ir.

Sem Streamlit.
"""

from __future__ import annotations

import base64
import io
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from core import montador as mt
from core import montador_grandezas as g
from core import montador_modelos as mm

#: Os modelos que uma marca pode usar: primeiro os de pinos e chapas, depois as outras peças.
_PRIMEIROS = ("Pino: força máxima", "Pino: diâmetro mínimo", "Chapa com furo: espessura mínima")
ANALISES: tuple[str, ...] = (
    *_PRIMEIROS,
    *(m.nome for m in mm.MODELOS if m.nome not in _PRIMEIROS and m.nome != "Fórmula própria"),
)
UNIDADES = g.unidades_padrao(g.SISTEMA_SOLIDOS)
#: Acima disso a imagem de fundo é reduzida: pesa no navegador e não ajuda a marcar.
LADO_MAXIMO_DA_IMAGEM = 2000

PASSOU = "passou"
NAO_PASSOU = "não passou"
LIMITE = "limite"  # sem o valor da letra principal: a marca diz até onde ela vai
FALTA = "falta"
ERRO = "erro"


class ErroDeDesenho(ValueError):
    """O arquivo não é um desenho que se possa pôr de fundo."""


@dataclass
class Marca:
    """Uma parte do desenho com a sua análise. ``x`` e ``y`` no desenho (mm, quando há escala)."""

    id: str
    x: float
    y: float
    nome: str = ""
    analise: str = ANALISES[0]
    valores: dict[str, float] = field(default_factory=dict)  # na base do sistema
    alvo: str = ""
    conferir: bool = True  # com o valor do alvo: passou ou não. Sem: até onde vai

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "nome": self.nome,
            "analise": self.analise,
            "valores": dict(self.valores),
            "alvo": self.alvo,
            "conferir": self.conferir,
        }


def marca_de_dicionario(dados: Mapping[str, Any]) -> Marca:
    analise = str(dados.get("analise") or ANALISES[0])
    if analise not in ANALISES:
        analise = ANALISES[0]
    valores = {
        str(k): float(v)
        for k, v in (dados.get("valores") or {}).items()
        if isinstance(v, (int, float)) and math.isfinite(float(v))
    }
    return Marca(
        id=str(dados["id"]),
        x=float(dados.get("x", 0.0)),
        y=float(dados.get("y", 0.0)),
        nome=str(dados.get("nome") or ""),
        analise=analise,
        valores=valores,
        alvo=str(dados.get("alvo") or ""),
        conferir=bool(dados.get("conferir", True)),
    )


def modelo_da_analise(analise: str) -> mm.Modelo:
    return mm.POR_NOME[analise]


def montagem_da_analise(analise: str) -> mt.Montagem:
    return mt.montar(mt.grafo_de_dados(modelo_da_analise(analise).grafo()))


def _redondo(valor: float, sentido: str | None) -> float:
    """Três algarismos, para o lado seguro: o máximo para baixo, o mínimo para cima."""
    if valor <= 0 or not math.isfinite(valor):
        return valor
    escala = 10 ** (math.floor(math.log10(valor)) - 2)
    passos = valor / escala
    if sentido == "máximo":
        passos = math.floor(passos + 1e-9)
    elif sentido == "mínimo":
        passos = math.ceil(passos - 1e-9)
    else:
        passos = round(passos)
    return float(f"{passos * escala:.6g}")


def marca_nova(id_: str, x: float, y: float, analise: str = ANALISES[0]) -> Marca:
    """A marca já vem com os números de exemplo do modelo (e os que os blocos sugerem), mostrando
    até onde a letra principal vai. O valor dela já fica preenchido, arredondado para o lado
    seguro, para quem quiser conferir uma medida."""
    modelo = modelo_da_analise(analise)
    montagem = montagem_da_analise(analise)
    alvo = modelo.alvo
    # Como na página do Montador: o padrão de cada letra, o que os blocos sugerem e o exemplo.
    valores = {
        gr.chave: gr.padrao
        for gr in montagem.grandezas
        if gr.padrao is not None and gr.chave != alvo
    }
    valores.update(dict(montagem.padroes))
    valores.update(dict(modelo.valores))
    if alvo not in valores:
        try:
            resposta = mt.isolar(montagem, alvo, valores)
        except mt.ErroDeMontagem:
            resposta = None
        if resposta is not None and resposta.valor is not None and math.isfinite(resposta.valor):
            valores[alvo] = _redondo(resposta.valor, resposta.sentido)
    return Marca(id_, x, y, analise=analise, valores=valores, alvo=alvo, conferir=False)


def trocar_analise(marca: Marca, analise: str) -> Marca:
    nova = marca_nova(marca.id, marca.x, marca.y, analise)
    nova.nome = marca.nome
    return nova


@dataclass(frozen=True)
class LinhaDaMarca:
    nome: str
    solicitacao: float
    limite: float
    uso: float


@dataclass(frozen=True)
class ResultadoDaMarca:
    situacao: str  # PASSOU, NAO_PASSOU, LIMITE, FALTA ou ERRO
    resumo: str  # o que vai na etiqueta do desenho
    texto: str  # a frase completa, embaixo
    uso: float | None = None  # o maior uso, quando confere
    manda: str = ""  # a condição que manda
    linhas: tuple[LinhaDaMarca, ...] = ()
    alertas: tuple[str, ...] = ()
    hipoteses: tuple[str, ...] = ()


def numero(valor: float, casas: int = 3) -> str:
    """Número com vírgula, sem zeros sobrando: 25,2 e não 25.200."""
    if not math.isfinite(valor):
        return "—"
    texto = f"{valor:.{casas}g}" if abs(valor) < 1e5 else f"{valor:,.0f}".replace(",", "§")
    return texto.replace(".", ",").replace("§", ".")


def texto_da_letra(montagem: mt.Montagem, chave: str, valor: float) -> str:
    grandeza = montagem.grandeza(chave)
    if grandeza is None:
        return numero(valor)
    rotulo = UNIDADES.rotulo(grandeza.dimensao)
    no_campo = UNIDADES.da_base(grandeza.dimensao, valor)
    return f"{numero(no_campo)} {rotulo}".strip()


def calcular(marca: Marca) -> ResultadoDaMarca:
    """A conta do Montador para a marca."""
    try:
        montagem = montagem_da_analise(marca.analise)
    except (mt.ErroDeMontagem, KeyError) as erro:
        return ResultadoDaMarca(ERRO, "erro", str(erro))
    alvo = montagem.grandeza(marca.alvo)
    if alvo is None:
        return ResultadoDaMarca(ERRO, "erro", f"{marca.alvo} não é letra desta análise.")
    adotado = marca.valores.get(marca.alvo) if marca.conferir else None
    valores = {k: v for k, v in marca.valores.items() if k != marca.alvo}
    try:
        resposta = mt.isolar(montagem, marca.alvo, valores, adotado=adotado)
    except mt.ErroDeMontagem as erro:
        return ResultadoDaMarca(ERRO, "erro", str(erro))
    hipoteses = tuple(montagem.hipoteses)
    alertas = tuple(resposta.alertas)
    if resposta.faltam:
        nomes = ", ".join(f.texto for f in resposta.faltam)
        return ResultadoDaMarca(
            FALTA, "faltam números", f"Faltam números para a conta: {nomes}.", alertas=alertas
        )
    manda = resposta.manda.condicao.nome if resposta.manda is not None else ""
    if adotado is not None and resposta.conferencia_adotada:
        linhas = tuple(
            LinhaDaMarca(linha.nome, linha.esquerda, linha.direita, linha.uso)
            for linha in resposta.conferencia_adotada
            if not linha.igualdade
        )
        pior = max(linhas, key=lambda linha: linha.uso)
        passou = pior.uso <= 1.0 + 1e-9
        situacao = PASSOU if passou else NAO_PASSOU
        resumo = f"{'passou' if passou else 'não passou'} · {numero(pior.uso * 100, 3)} %"
        texto = (
            f"Com {alvo.texto} = {texto_da_letra(montagem, marca.alvo, adotado)}, o maior uso é "
            f"{numero(pior.uso * 100, 3)} %, em {pior.nome.lower()}."
        )
        if resposta.valor is not None and math.isfinite(resposta.valor):
            sentido = {"máximo": "até", "mínimo": "a partir de"}.get(resposta.sentido or "", "em")
            texto += f" {alvo.texto} vai {sentido} {texto_da_letra(montagem, marca.alvo, resposta.valor)}."
        return ResultadoDaMarca(
            situacao, resumo, texto, pior.uso, pior.nome, linhas, alertas, hipoteses
        )
    if resposta.valor is None or not math.isfinite(resposta.valor):
        return ResultadoDaMarca(
            ERRO,
            "sem resposta",
            "A conta não chegou a um valor com esses números.",
            alertas=alertas,
        )
    sinal = {"máximo": "≤", "mínimo": "≥"}.get(resposta.sentido or "", "=")
    valor = texto_da_letra(montagem, marca.alvo, resposta.valor)
    return ResultadoDaMarca(
        LIMITE,
        f"{alvo.texto} {sinal} {valor}",
        f"{alvo.nome}: {alvo.texto} {sinal} {valor}"
        + (f", e quem manda é {manda.lower()}." if manda else "."),
        manda=manda,
        alertas=alertas,
        hipoteses=hipoteses,
    )


# ---------------------------------------------------------------------------
# O desenho de fundo
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fundo:
    """O que a prancheta põe atrás das marcas. Imagem: ``imagem`` (data URL) com largura e altura
    em pixels. DXF: ``curvas`` em mm, e ``escala`` = 1 (o DXF já vem em mm)."""

    tipo: str  # "imagem" ou "dxf"
    nome: str
    imagem: str = ""
    largura: int = 0
    altura: int = 0
    curvas: tuple[Mapping[str, Any], ...] = ()

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "tipo": self.tipo,
            "nome": self.nome,
            "imagem": self.imagem,
            "largura": self.largura,
            "altura": self.altura,
            "curvas": [dict(c) for c in self.curvas],
        }


def _png_pequeno(imagem: Any) -> tuple[str, int, int]:
    from PIL import Image

    assert isinstance(imagem, Image.Image)
    imagem = imagem.convert("RGB")
    imagem.thumbnail((LADO_MAXIMO_DA_IMAGEM, LADO_MAXIMO_DA_IMAGEM))
    saida = io.BytesIO()
    imagem.save(saida, format="JPEG", quality=85)
    dados = base64.b64encode(saida.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{dados}", imagem.width, imagem.height


def fundo_de_imagem(nome: str, conteudo: bytes) -> Fundo:
    from PIL import Image, UnidentifiedImageError

    try:
        imagem = Image.open(io.BytesIO(conteudo))
        imagem.load()
    except (UnidentifiedImageError, OSError) as erro:
        raise ErroDeDesenho(f"{nome} não abriu como imagem: {erro}") from erro
    url, largura, altura = _png_pequeno(imagem)
    return Fundo("imagem", nome, url, largura, altura)


def paginas_do_pdf(conteudo: bytes) -> int:
    import pypdfium2 as pdfium

    try:
        documento = pdfium.PdfDocument(conteudo)
    except pdfium.PdfiumError as erro:
        raise ErroDeDesenho(f"O PDF não abriu: {erro}") from erro
    return len(documento)


def fundo_de_pdf(nome: str, conteudo: bytes, pagina: int = 1) -> Fundo:
    """A página do PDF vira imagem (a 150 dpi, para as cotas do desenho ficarem legíveis)."""
    import pypdfium2 as pdfium

    try:
        documento = pdfium.PdfDocument(conteudo)
        folha = documento[max(pagina, 1) - 1]
        imagem = folha.render(scale=150 / 72).to_pil()
    except (pdfium.PdfiumError, IndexError) as erro:
        raise ErroDeDesenho(f"A página {pagina} do PDF não abriu: {erro}") from erro
    url, largura, altura = _png_pequeno(imagem)
    return Fundo("imagem", f"{nome}, página {pagina}", url, largura, altura)


def fundo_de_dxf(nome: str, conteudo: bytes, camadas: Sequence[str] | None = None) -> Fundo:
    """As curvas do DXF em mm, na posição do arquivo (sem levar à origem)."""
    from core import esboco as eb
    from core import esboco_dxf as ed

    try:
        leitura = ed.ler_dxf(conteudo, usar=camadas, levar_para_origem=False)
    except ed.ErroDeDxf as erro:
        raise ErroDeDesenho(str(erro)) from erro
    pontos = leitura.esboco.pontos
    curvas: list[dict[str, Any]] = []
    for curva in leitura.esboco.curvas:
        if curva.tipo == eb.LINHA:
            a, b = (pontos[p] for p in curva.pontos)
            curvas.append({"tipo": "linha", "a": list(a), "b": list(b)})
        elif curva.tipo == eb.CIRCULO:
            curvas.append({"tipo": "circulo", "c": list(pontos[curva.pontos[0]]), "r": curva.raio})
        else:
            c, a, b = (pontos[p] for p in curva.pontos)
            curvas.append({"tipo": "arco", "c": list(c), "a": list(a), "b": list(b)})
    return Fundo("dxf", nome, curvas=tuple(curvas))


def fundo_do_arquivo(nome: str, conteudo: bytes, pagina: int = 1) -> Fundo:
    extensao = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
    if extensao == "pdf":
        return fundo_de_pdf(nome, conteudo, pagina)
    if extensao in ("dxf", "dwg"):
        return fundo_de_dxf(nome, conteudo)
    return fundo_de_imagem(nome, conteudo)


def fundo_colado(url: str) -> Fundo:
    """O print colado na prancheta (Ctrl+V): chega como data URL."""
    if not url.startswith("data:image/") or "," not in url:
        raise ErroDeDesenho("O que foi colado não é uma imagem.")
    dados = base64.b64decode(url.split(",", 1)[1])
    return fundo_de_imagem("print colado", dados)


# ---------------------------------------------------------------------------
# Memorial: o desenho com as marcas e a conta de cada uma
# ---------------------------------------------------------------------------

_CORES = {PASSOU: (43, 138, 62), NAO_PASSOU: (224, 49, 49), LIMITE: (28, 126, 214)}
_CINZA = (134, 142, 150)


def imagem_com_marcas(
    fundo: Mapping[str, Any] | None,
    marcas: Sequence[Marca],
    resultados: Sequence[ResultadoDaMarca],
) -> bytes:
    """PNG do desenho com as marcas numeradas, na cor do resultado de cada uma."""
    from PIL import Image, ImageDraw

    def para_px(x: float, y: float) -> tuple[float, float]:
        return x, y

    if fundo and fundo.get("tipo") == "imagem" and str(fundo.get("imagem", "")).startswith("data:"):
        dados = base64.b64decode(str(fundo["imagem"]).split(",", 1)[1])
        imagem = Image.open(io.BytesIO(dados)).convert("RGB")
    else:
        pontos: list[tuple[float, float]] = [(m.x, m.y) for m in marcas]
        curvas = list((fundo or {}).get("curvas") or [])
        for c in curvas:
            if c["tipo"] == "linha":
                pontos += [(c["a"][0], -c["a"][1]), (c["b"][0], -c["b"][1])]
            else:
                r = c.get("r") or math.hypot(c["a"][0] - c["c"][0], c["a"][1] - c["c"][1])
                pontos += [(c["c"][0] - r, -c["c"][1] - r), (c["c"][0] + r, -c["c"][1] + r)]
        if not pontos:
            pontos = [(0.0, 0.0), (100.0, 100.0)]
        x0, y0 = min(p[0] for p in pontos), min(p[1] for p in pontos)
        x1, y1 = max(p[0] for p in pontos), max(p[1] for p in pontos)
        largura_px = 1600
        escala = (largura_px - 160) / max(x1 - x0, y1 - y0, 1e-9)
        altura_px = int((y1 - y0) * escala + 160)

        def para_px(x: float, y: float) -> tuple[float, float]:  # noqa: F811
            return (x - x0) * escala + 80, (y - y0) * escala + 80

        imagem = Image.new("RGB", (largura_px, max(altura_px, 400)), "white")
        traco = ImageDraw.Draw(imagem)
        for c in curvas:
            if c["tipo"] == "linha":
                traco.line(
                    [para_px(c["a"][0], -c["a"][1]), para_px(c["b"][0], -c["b"][1])], "black", 2
                )
                continue
            r = c.get("r") or math.hypot(c["a"][0] - c["c"][0], c["a"][1] - c["c"][1])
            cx, cy = para_px(c["c"][0], -c["c"][1])
            caixa = [cx - r * escala, cy - r * escala, cx + r * escala, cy + r * escala]
            if c["tipo"] == "circulo":
                traco.ellipse(caixa, outline="black", width=2)
            else:
                # No desenho o arco é anti-horário; na imagem, com y para baixo, os ângulos trocam.
                ta = math.degrees(math.atan2(c["a"][1] - c["c"][1], c["a"][0] - c["c"][0]))
                tb = math.degrees(math.atan2(c["b"][1] - c["c"][1], c["b"][0] - c["c"][0]))
                traco.arc(caixa, -tb, -ta, "black", 2)
    traco = ImageDraw.Draw(imagem)
    lado = max(imagem.width, imagem.height)
    raio = max(10, lado // 90)
    for numero, (marca, resultado) in enumerate(zip(marcas, resultados, strict=True), start=1):
        x, y = para_px(marca.x, marca.y)
        cor = _CORES.get(resultado.situacao, _CINZA)
        traco.ellipse([x - raio, y - raio, x + raio, y + raio], fill=cor, outline="white", width=2)
        traco.text((x, y), str(numero), fill="white", anchor="mm", font_size=int(raio * 1.2))
        rotulo = f"{marca.nome or marca.analise.split(':')[0]} — {resultado.resumo}"
        traco.text(
            (x + raio + 6, y - raio - 4), rotulo, fill=cor, anchor="ls", font_size=int(raio * 1.1)
        )
    saida = io.BytesIO()
    imagem.save(saida, format="PNG")
    return saida.getvalue()


def word_da_analise(
    fundo: Mapping[str, Any] | None,
    marcas: Sequence[Marca],
    resultados: Sequence[ResultadoDaMarca],
    escala: float | None = None,
) -> bytes:
    """O memorial: o desenho com as marcas e, para cada uma, os números, as condições e o resultado."""
    from docx import Document
    from docx.shared import Cm

    documento = Document()
    documento.add_heading("Análise sobre o desenho", level=1)
    passou = sum(r.situacao == PASSOU for r in resultados)
    nao = sum(r.situacao == NAO_PASSOU for r in resultados)
    origem = (fundo or {}).get("nome") or "sem desenho de fundo"
    documento.add_paragraph(
        f"Desenho: {origem}. {len(marcas)} {'parte analisada' if len(marcas) == 1 else 'partes analisadas'}: "
        f"{passou} passou, {nao} não passou. Cada análise é um modelo do Montador de fórmulas."
        + (f" Escala do desenho: {numero(escala, 4)} mm por unidade." if escala else "")
    )
    documento.add_picture(io.BytesIO(imagem_com_marcas(fundo, marcas, resultados)), width=Cm(16))
    for indice, (marca, resultado) in enumerate(zip(marcas, resultados, strict=True), start=1):
        titulo = f"{indice} · {marca.nome}" if marca.nome else f"{indice} · {marca.analise}"
        documento.add_heading(titulo, level=2)
        documento.add_paragraph(f"Análise: {marca.analise}. {resultado.texto}")
        try:
            montagem = montagem_da_analise(marca.analise)
        except (mt.ErroDeMontagem, KeyError):
            continue
        tabela = documento.add_table(rows=1, cols=3)
        tabela.style = "Light Grid Accent 1"
        for celula, texto in zip(tabela.rows[0].cells, ("Letra", "Grandeza", "Valor"), strict=True):
            celula.text = texto
        for grandeza in montagem.grandezas:
            if grandeza.chave == marca.alvo and not marca.conferir:
                continue
            valor = marca.valores.get(grandeza.chave)
            linha = tabela.add_row().cells
            linha[0].text = grandeza.texto
            linha[1].text = grandeza.nome
            linha[2].text = (
                "—" if valor is None else texto_da_letra(montagem, grandeza.chave, valor)
            )
        if resultado.linhas:
            documento.add_paragraph("")
            condicoes = documento.add_table(rows=1, cols=4)
            condicoes.style = "Light Grid Accent 1"
            cabecalho = ("Condição", "Solicitação", "Limite", "Uso")
            for celula, texto in zip(condicoes.rows[0].cells, cabecalho, strict=True):
                celula.text = texto
            for item in sorted(resultado.linhas, key=lambda x: -x.uso):
                linha = condicoes.add_row().cells
                linha[0].text = item.nome
                linha[1].text = numero(item.solicitacao, 4)
                linha[2].text = numero(item.limite, 4)
                linha[3].text = f"{numero(item.uso * 100, 3)} %"
        for alerta in resultado.alertas:
            documento.add_paragraph(f"Atenção: {alerta}")
        if resultado.hipoteses:
            documento.add_paragraph("Hipóteses:")
            for hipotese in resultado.hipoteses:
                documento.add_paragraph(hipotese, style="List Bullet")
    saida = io.BytesIO()
    documento.save(saida)
    return saida.getvalue()
