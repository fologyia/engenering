"""Digitaliza os gráficos de arrasto (Figuras 4 e 5) da ABNT NBR 6123:2023 e gera ``core/vento_arrasto_dados.py``.

Os gráficos são imagens raster dentro do PDF da norma (não há vetores). O procedimento é:

1. extrai as imagens do PDF (PyMuPDF);
2. separa as isolinhas das linhas finas da grade e dos algarismos (traço com pelo menos 3 pixels
   de espessura nas duas direções);
3. associa cada isolinha ao seu nível pela ordem em que elas aparecem da esquerda para a direita
   (a numeração impressa no gráfico confirma a ordem);
4. lê o valor de Ca em cada cruzamento da grade do próprio gráfico, interpolando entre as duas
   isolinhas que enquadram o ponto pelo menor segmento (raios em 16 direções);
5. nos poucos cruzamentos sem isolinha dos dois lados (cantos do gráfico), extrapola em linha reta
   no logaritmo da abscissa, a partir dos dois cruzamentos vizinhos da mesma linha.

O resultado é uma tabela de Ca por (h/ℓ₁, ℓ₁/ℓ₂) com incerteza de leitura da ordem de ±0,03.
Os eixos do gráfico são logarítmicos; as posições da grade foram conferidas com os rótulos.

Uso (precisa de PyMuPDF e Pillow; só é preciso rodar de novo se a norma mudar)::

    python scripts/digitalizar_arrasto_nbr6123.py "C:/caminho/NBR6123-2023.pdf"
"""

from __future__ import annotations

import collections
import io
import math
import sys
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "core" / "vento_arrasto_dados.py"

# ----------------------------------------------------------------------------- imagens da norma
PAGINA_FIGURA_4 = 40  # duas imagens empilhadas: parte de cima e parte de baixo do gráfico
XREF_FIGURA_4 = (452, 453)
XREF_FIGURA_5 = 464  # na página 41

# Isolinhas, da esquerda para a direita (ordem de nível decrescente em qualquer linha da grade).
NIVEIS_FIGURA_4 = (2.2, 2.1, 2.0, 1.9, 1.8, 1.7, 1.6, 1.5, 1.4, 1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7)
NIVEIS_FIGURA_5 = (1.6, 1.5, 1.4, 1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7)

# Valores da grade que a tabela publicada usa.
COLUNAS_L1_SOBRE_L2 = (
    4.0,
    3.5,
    3.0,
    2.5,
    2.0,
    1.5,
    1.0,
    0.9,
    0.8,
    0.7,
    0.6,
    0.5,
    0.4,
    0.3,
    0.25,
    0.2,
)
LINHAS_H_SOBRE_L1_FIG4 = (
    0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0, 30.0, 40.0,
)  # fmt: skip
LINHAS_H_SOBRE_L1_FIG5 = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0)


def _imagem(doc: pymupdf.Document, xref: int) -> np.ndarray:
    pix = pymupdf.Pixmap(doc, xref)
    if pix.n - pix.alpha >= 4:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    return np.array(Image.open(io.BytesIO(pix.tobytes("png"))).convert("L"))


def _comprimentos(mascara: np.ndarray) -> np.ndarray:
    """Comprimento da sequência horizontal de pixels escuros a que cada pixel pertence."""
    saida = np.zeros(mascara.shape, dtype=np.int32)
    for y in range(mascara.shape[0]):
        linha = mascara[y]
        x = 0
        while x < linha.size:
            if linha[x]:
                inicio = x
                while x < linha.size and linha[x]:
                    x += 1
                saida[y, inicio:x] = x - inicio
            else:
                x += 1
    return saida


def _traco_grosso(escuro: np.ndarray) -> np.ndarray:
    return escuro & (_comprimentos(escuro) >= 3) & (_comprimentos(escuro.T).T >= 3)


def _componentes(mascara: np.ndarray) -> tuple[np.ndarray, dict[int, int]]:
    altura, largura = mascara.shape
    rotulos = np.zeros((altura, largura), dtype=np.int32)
    tamanhos: dict[int, int] = {}
    proximo = 0
    for y in range(altura):
        for x in range(largura):
            if mascara[y, x] and rotulos[y, x] == 0:
                proximo += 1
                fila = collections.deque([(y, x)])
                rotulos[y, x] = proximo
                contagem = 0
                while fila:
                    cy, cx = fila.popleft()
                    contagem += 1
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if (
                                0 <= ny < altura
                                and 0 <= nx < largura
                                and mascara[ny, nx]
                                and rotulos[ny, nx] == 0
                            ):
                                rotulos[ny, nx] = proximo
                                fila.append((ny, nx))
                tamanhos[proximo] = contagem
    return rotulos, tamanhos


def _isolinhas(imagem: np.ndarray, quadro: tuple[int, int, int, int], n_niveis: int):
    """Máscara das isolinhas, com o nível de cada uma (ordem da esquerda para a direita)."""
    x0, x1, y0, y1 = quadro
    escuro = imagem < 140
    recorte = np.zeros_like(escuro)
    recorte[y0 : y1 + 1, x0 : x1 + 1] = True
    grosso = _traco_grosso(escuro) & recorte
    rotulos, tamanhos = _componentes(grosso)
    # As isolinhas são os n componentes mais compridos (os algarismos são fragmentos curtos).
    candidatos = sorted(tamanhos, key=lambda k: -tamanhos[k])[:n_niveis]

    def extremo_superior(k: int) -> tuple[int, float]:
        ys, xs = np.nonzero(rotulos == k)
        topo = int(ys.min())
        return topo, float(xs[ys == topo].mean())

    # Da esquerda para a direita = do maior para o menor Ca: as isolinhas terminam no alto do
    # gráfico em ordem crescente de abscissa e, as mais baixas, em ordem crescente de altura.
    ordenados = sorted(candidatos, key=extremo_superior)
    return rotulos, ordenados


def _nivel_por_pixel(rotulos: np.ndarray, ordenados: list[int], niveis: tuple[float, ...]):
    mapa = np.full(rotulos.shape, np.nan)
    for componente, nivel in zip(ordenados, niveis, strict=True):
        mapa[rotulos == componente] = nivel
    return mapa


# ----------------------------------------------------------------------------- interpolação
class _Raios:
    def __init__(self, nivel: np.ndarray, quadro: tuple[int, int, int, int]):
        self.nivel = nivel
        self.quadro = quadro

    def _acerto(self, x: float, y: float, dx: float, dy: float):
        x0, x1, y0, y1 = self.quadro
        distancia = 0.0
        while distancia < 900.0:
            distancia += 0.5
            px, py = x + dx * distancia, y + dy * distancia
            if not (x0 - 0.5 <= px <= x1 + 0.5 and y0 - 0.5 <= py <= y1 + 0.5):
                return None
            ix, iy = int(round(px)), int(round(py))
            valor = self.nivel[iy, ix]
            if not math.isnan(valor):
                return float(valor), distancia
        return None

    def valor(self, x: float, y: float, direcoes: int = 16) -> tuple[float, bool]:
        """(valor, enquadrado). ``enquadrado`` é falso quando só um lado tem isolinha."""
        ix, iy = int(round(x)), int(round(y))
        for raio in (0, 1, 2):
            janela = self.nivel[
                max(iy - raio, 0) : iy + raio + 1, max(ix - raio, 0) : ix + raio + 1
            ]
            if np.isfinite(janela).any():
                return float(np.nanmean(janela)), True
        melhores = []
        mais_proximo = None
        for k in range(direcoes):
            angulo = math.pi * k / direcoes
            dx, dy = math.cos(angulo), math.sin(angulo)
            a, b = self._acerto(x, y, dx, dy), self._acerto(x, y, -dx, -dy)
            for acerto in (a, b):
                if acerto and (mais_proximo is None or acerto[1] < mais_proximo[1]):
                    mais_proximo = acerto
            if a and b and abs(a[0] - b[0]) > 1e-9:
                comprimento = a[1] + b[1]
                melhores.append((comprimento, a[0] + (b[0] - a[0]) * a[1] / comprimento))
        if melhores:
            return min(melhores)[1], True
        return (mais_proximo[0] if mais_proximo else math.nan), False


def _extrapolar(
    linha: list[float], enquadrado: list[bool], abscissas: tuple[float, ...]
) -> list[float]:
    """Preenche os cruzamentos sem isolinha dos dois lados, em linha reta no ln(ℓ1/ℓ2)."""
    saida = list(linha)
    bons = [i for i, ok in enumerate(enquadrado) if ok]
    if len(bons) < 2:
        return saida
    for i, ok in enumerate(enquadrado):
        if ok:
            continue
        if i < bons[0]:
            a, b = bons[0], bons[1]
        elif i > bons[-1]:
            a, b = bons[-1], bons[-2]
        else:  # buraco entre dois cruzamentos enquadrados: interpola
            a = max(j for j in bons if j < i)
            b = min(j for j in bons if j > i)
        xa, xb, xi = (math.log(abscissas[j]) for j in (a, b, i))
        inclinacao = (linha[b] - linha[a]) / (xb - xa)
        saida[i] = linha[a] + inclinacao * (xi - xa)
    return saida


def _tabela(rotulos, ordenados, niveis, quadro, calibracao, linhas):
    mapa = _nivel_por_pixel(rotulos, ordenados, niveis)
    raios = _Raios(mapa, quadro)
    x_esq, kx, y_base, ky, h_base = calibracao
    tabela = []
    for h in linhas:
        y = y_base - ky * math.log(h / h_base)
        valores, ok = [], []
        for v in COLUNAS_L1_SOBRE_L2:
            x = x_esq + kx * math.log(4.0 / v)
            valor, enquadrado = raios.valor(x, y)
            valores.append(valor)
            ok.append(enquadrado)
        tabela.append(_extrapolar(valores, ok, COLUNAS_L1_SOBRE_L2))
    # Nos gráficos, C_a nunca diminui quando h/ℓ₁ cresce (as linhas vêm em ordem crescente de h):
    # a extrapolação das bordas pode errar por 0,01 para baixo; o máximo acumulado corrige isso.
    for i in range(1, len(tabela)):
        tabela[i] = [
            max(novo, antigo) for novo, antigo in zip(tabela[i], tabela[i - 1], strict=True)
        ]
    return tabela


def _formatar(nome: str, linhas: tuple[float, ...], tabela: list[list[float]]) -> str:
    corpo = ",\n".join(
        "    " + f"{h!r}: (" + ", ".join(f"{valor:.2f}" for valor in linha) + ")"
        for h, linha in zip(linhas, tabela, strict=True)
    )
    # fmt: off/on: o formatador não deve abrir cada tupla em uma linha por valor.
    return f"# fmt: off\n{nome}: dict[float, tuple[float, ...]] = {{\n{corpo},\n}}\n# fmt: on\n"


def main(caminho_pdf: str) -> None:
    doc = pymupdf.open(caminho_pdf)
    # Figura 4 (baixa turbulência): duas imagens empilhadas.
    topo, base = (_imagem(doc, xref) for xref in XREF_FIGURA_4)
    figura4 = np.vstack([topo, base])
    quadro4 = (132, 723, 21, 914)
    rotulos4, ord4 = _isolinhas(figura4, quadro4, len(NIVEIS_FIGURA_4))
    kx4 = (722.5 - 132.5) / math.log(4.0 / 0.2)
    ky4 = (914 - 64.5) / math.log(40.0 / 0.5)
    tabela4 = _tabela(
        rotulos4,
        ord4,
        NIVEIS_FIGURA_4,
        quadro4,
        (132.5, kx4, 914.0, ky4, 0.5),
        LINHAS_H_SOBRE_L1_FIG4,
    )
    # Figura 5 (alta turbulência).
    figura5 = _imagem(doc, XREF_FIGURA_5)
    quadro5 = (67, 731, 45, 602)
    rotulos5, ord5 = _isolinhas(figura5, quadro5, len(NIVEIS_FIGURA_5))
    kx5 = (730.5 - 67.5) / math.log(4.0 / 0.2)
    ky5 = (602 - 61.5) / math.log(6.0 / 0.5)
    tabela5 = _tabela(
        rotulos5,
        ord5,
        NIVEIS_FIGURA_5,
        quadro5,
        (67.5, kx5, 602.0, ky5, 0.5),
        LINHAS_H_SOBRE_L1_FIG5,
    )
    cabecalho = (
        '"""Coeficientes de arrasto Ca das Figuras 4 e 5 da ABNT NBR 6123:2023 (edificações paralelepipédicas).\n\n'
        "Gerado por ``scripts/digitalizar_arrasto_nbr6123.py`` a partir dos gráficos da norma — não editar\n"
        "à mão. Cada linha é um valor de h/ℓ₁ e cada coluna, um valor de ℓ₁/ℓ₂ (``COLUNAS_L1_SOBRE_L2``);\n"
        "os valores estão nos cruzamentos da grade do próprio gráfico. Incerteza de leitura: ±0,03.\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
    )
    corpo = (
        "# fmt: off\n"
        f"COLUNAS_L1_SOBRE_L2: tuple[float, ...] = {COLUNAS_L1_SOBRE_L2!r}\n"
        "# fmt: on\n\n"
        + _formatar("FIGURA_4_BAIXA_TURBULENCIA", LINHAS_H_SOBRE_L1_FIG4, tabela4)
        + "\n"
        + _formatar("FIGURA_5_ALTA_TURBULENCIA", LINHAS_H_SOBRE_L1_FIG5, tabela5)
    )
    DESTINO.write_text(cabecalho + corpo, encoding="utf-8")
    print("gravado", DESTINO)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "Downloads" / "NBR6123-2023.pdf"))
