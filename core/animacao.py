"""Cena de uma animação no tempo, pronta para o tocador (components/animacao).

O cálculo acontece todo aqui, em Python: a cena leva os instantes, os valores de cada canal em cada
instante e as formas do desenho. O navegador só toca. Os valores vão como Float32 (e a grade de
calor como Uint8 por quadro) em base64, para uma seção com dez mil células caber em pouco mais de
um megabyte.

Unidades: o desenho está em coordenadas próprias (metro, milímetro ou esquema, com o Y para cima);
cada escala diz a sua unidade; o tempo está em segundos e ``unidade_tempo`` diz como mostrar.
"""

from __future__ import annotations

import base64
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

#: Quadros que a animação guarda. Mais que isso não melhora o que se vê e pesa no navegador.
QUADROS = 151
#: Valores de grade que a cena aceita somados em todos os quadros (Uint8): cerca de 2 MB.
LIMITE_DA_GRADE = 2_000_000

CALOR = "calor"
AGUA = "agua"
CINZA = "cinza"
MAPAS = (CALOR, AGUA, CINZA)
Numeros = Sequence[float] | np.ndarray


@dataclass(frozen=True, slots=True)
class UnidadeDeTempo:
    rotulo: str
    fator: float  # segundos por unidade
    casas: int


def unidade_de_tempo(duracao_s: float) -> UnidadeDeTempo:
    """A unidade que deixa a duração com números confortáveis de ler."""
    d = abs(float(duracao_s))
    if d <= 180:
        return UnidadeDeTempo("s", 1.0, 2 if d < 10 else 1)
    if d <= 3 * 3600:
        return UnidadeDeTempo("min", 60.0, 2 if d < 600 else 1)
    if d <= 3 * 86400:
        return UnidadeDeTempo("h", 3600.0, 2 if d < 36000 else 1)
    return UnidadeDeTempo("dias", 86400.0, 2)


def tempo_em_texto(t_s: float, unidade: UnidadeDeTempo | None = None) -> str:
    u = unidade or unidade_de_tempo(t_s)
    texto = f"{t_s / u.fator:.{u.casas}f}".replace(".", ",")
    return f"{texto} {u.rotulo}"


def tempos_dos_quadros(t_final: float, quadros: int = QUADROS) -> np.ndarray:
    return np.linspace(0.0, float(t_final), int(quadros))


def reamostrar(tempos: np.ndarray, valores: np.ndarray, novos: np.ndarray) -> np.ndarray:
    """Valores de cada coluna (ou de uma série só) nos instantes novos, por interpolação linear.

    ``valores`` tem os instantes na primeira dimensão.
    """
    t = np.asarray(tempos, dtype=float)
    v = np.asarray(valores, dtype=float)
    if v.ndim == 1:
        return np.interp(novos, t, v)
    plano = v.reshape(len(t), -1)
    saida = np.empty((len(novos), plano.shape[1]))
    for k in range(plano.shape[1]):
        saida[:, k] = np.interp(novos, t, plano[:, k])
    return saida.reshape((len(novos), *v.shape[1:]))


def _b64(matriz: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(matriz).tobytes()).decode("ascii")


def _lista(pontos: Sequence[Sequence[float]]) -> list[list[float]]:
    return [[round(float(x), 6), round(float(y), 6)] for x, y in pontos]


@dataclass
class Cena:
    """Montador da cena: escalas, canais, formas e gráficos, nessa ordem de uso."""

    tempos: np.ndarray
    id: str = ""
    nota: str = ""
    altura: int | None = None
    _escalas: list[dict[str, Any]] = field(default_factory=list)
    _canais: list[np.ndarray] = field(default_factory=list)
    _formas: list[dict[str, Any]] = field(default_factory=list)
    _graficos: list[dict[str, Any]] = field(default_factory=list)
    _grade: dict[str, Any] | None = None
    vista: tuple[float, float, float, float] | None = None

    def __post_init__(self) -> None:
        self.tempos = np.asarray(self.tempos, dtype=float)
        if self.tempos.ndim != 1 or len(self.tempos) < 1:
            raise ValueError("A cena precisa de ao menos um instante.")
        if np.any(np.diff(self.tempos) < 0):
            raise ValueError("Os instantes da cena precisam estar em ordem crescente.")

    @property
    def quadros(self) -> int:
        return len(self.tempos)

    # ------------------------------------------------------------------ escalas e canais
    def escala(
        self,
        nome: str,
        unidade: str,
        minimo: float,
        maximo: float,
        *,
        cores: str = CALOR,
        casas: int = 1,
    ) -> int:
        if cores not in MAPAS:
            raise ValueError(f"Mapa de cores desconhecido: {cores}.")
        lo, hi = float(minimo), float(maximo)
        if not hi > lo:
            meio = lo
            folga = max(abs(meio) * 0.01, 1e-6)
            lo, hi = meio - folga, meio + folga
        self._escalas.append(
            {"nome": nome, "unidade": unidade, "min": lo, "max": hi, "cores": cores, "casas": casas}
        )
        return len(self._escalas) - 1

    def canal(self, valores: Sequence[float] | np.ndarray | float) -> int:
        """Um valor por quadro; um número só vira um canal constante."""
        v = np.asarray(valores, dtype=float)
        if v.ndim == 0:
            v = np.full(self.quadros, float(v))
        if v.shape != (self.quadros,):
            raise ValueError(f"O canal precisa de {self.quadros} valores, um por quadro.")
        self._canais.append(v)
        return len(self._canais) - 1

    def canais(self, matriz: np.ndarray) -> list[int]:
        """Uma coluna por canal (quadros × colunas)."""
        m = np.asarray(matriz, dtype=float)
        return [self.canal(m[:, k]) for k in range(m.shape[1])]

    # ------------------------------------------------------------------ formas
    def poligono(
        self,
        pontos: Sequence[Sequence[float]],
        *,
        escala: int | None = None,
        canal: int | None = None,
        cor: str | None = None,
        contorno: str | None = None,
        espessura: float | None = None,
        nome: str = "",
        vazio: bool = False,
        hachura: bool = False,
        visivel: int | None = None,
        atras: bool = False,
    ) -> None:
        """``hachura``: riscos a 45° por cima (isolamento, face isolada); ``visivel``: canal que,
        zerado, esconde a forma; ``atras``: desenhada antes da grade de calor (fundo)."""
        forma: dict[str, Any] = {"tipo": "poligono", "pontos": _lista(pontos)}
        self._valor_ou_cor(forma, escala, canal, cor)
        if atras:
            forma["atras"] = True
        if hachura:
            forma["hachura"] = True
        if visivel is not None:
            forma["visivel"] = visivel
        if contorno:
            forma["contorno"] = contorno
        if espessura is not None:
            forma["espessura"] = espessura
        if nome:
            forma["nome"] = nome
        if vazio:
            forma["vazio"] = True
        self._formas.append(forma)

    def retangulo(self, x0: float, y0: float, x1: float, y1: float, **opcoes: Any) -> None:
        self.poligono([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], **opcoes)

    def linha(
        self,
        pontos: Sequence[Sequence[float]],
        *,
        largura: float = 2.0,
        escala: int | None = None,
        canal: int | None = None,
        cor: str | None = None,
        fluxo: int | None = None,
        fluxo_ref: float | None = None,
        tracejado: bool = False,
        nome: str = "",
        traco: float | None = None,
        vao: float | None = None,
        setas: bool = False,
        sentido: int = 1,
        espaco_setas: float | None = None,
        cor_setas: str | None = None,
        contorno_setas: str | None = None,
        visivel: int | None = None,
        ponta: str | None = None,
    ) -> None:
        """``fluxo``: canal com a velocidade; os traços andam na proporção de ``|v| / fluxo_ref``.

        ``setas``: pontas de seta ao longo da linha no sentido do escoamento (o sinal do ``fluxo``
        vira o sentido; sem ``fluxo``, vale ``sentido``), andando junto com o fluido."""
        forma: dict[str, Any] = {"tipo": "linha", "pontos": _lista(pontos), "largura": largura}
        if setas:
            forma["setas"] = True
            forma["sentido"] = 1 if sentido >= 0 else -1
            if espaco_setas is not None:
                forma["espaco_setas"] = espaco_setas
            if cor_setas:
                forma["cor_setas"] = cor_setas
            if contorno_setas:
                forma["contorno_setas"] = contorno_setas
        if visivel is not None:
            forma["visivel"] = visivel
        if ponta:
            forma["ponta"] = ponta
        self._valor_ou_cor(forma, escala, canal, cor)
        if fluxo is not None:
            forma["fluxo"] = fluxo
            referencia = fluxo_ref
            if referencia is None:
                referencia = float(np.max(np.abs(self._canais[fluxo]), initial=0.0)) or 1.0
            forma["fluxo_ref"] = referencia
        if tracejado:
            forma["tracejado"] = True
        if nome:
            forma["nome"] = nome
        if traco is not None:
            forma["traco"] = traco
        if vao is not None:
            forma["vao"] = vao
        self._formas.append(forma)

    def nivel(
        self,
        caixa: tuple[float, float, float, float],
        canal_altura: int,
        *,
        cor: str | None = None,
        escala: int | None = None,
        canal_cor: int | None = None,
    ) -> None:
        """Líquido num recipiente: ``canal_altura`` é a altura do líquido, na unidade do desenho."""
        forma: dict[str, Any] = {
            "tipo": "nivel",
            "caixa": [float(v) for v in caixa],
            "canal_altura": canal_altura,
        }
        if canal_cor is not None and escala is not None:
            forma["canal_cor"] = canal_cor
            forma["escala"] = escala
        if cor:
            forma["cor"] = cor
        self._formas.append(forma)

    def circulo(
        self,
        x: float,
        y: float,
        *,
        raio_px: float = 6.0,
        escala: int | None = None,
        canal: int | None = None,
        cor: str | None = None,
        contorno: str | None = None,
        nome: str = "",
        vazio: bool = False,
        espessura: float | None = None,
    ) -> None:
        forma: dict[str, Any] = {
            "tipo": "circulo",
            "x": float(x),
            "y": float(y),
            "raio_px": raio_px,
        }
        self._valor_ou_cor(forma, escala, canal, cor)
        if vazio:
            forma["vazio"] = True
        if espessura is not None:
            forma["espessura"] = espessura
        if contorno:
            forma["contorno"] = contorno
        if nome:
            forma["nome"] = nome
        self._formas.append(forma)

    def texto(
        self,
        x: float,
        y: float,
        texto: str,
        *,
        canal: int | None = None,
        casas: int = 1,
        ancora: str = "center",
        base: str = "middle",
        tamanho: int = 12,
        negrito: bool = False,
        dx: float = 0.0,
        dy: float = 0.0,
        cor: str | None = None,
        modulo: bool = False,
        visivel: int | None = None,
    ) -> None:
        """Com ``canal``, o ``{}`` do texto vira o valor do canal no instante mostrado (``modulo``:
        sem o sinal)."""
        forma: dict[str, Any] = {
            "tipo": "texto",
            "x": float(x),
            "y": float(y),
            "texto": texto,
            "ancora": ancora,
            "base": base,
            "tamanho": tamanho,
        }
        if canal is not None:
            forma["canal"] = canal
            forma["casas"] = casas
        if negrito:
            forma["negrito"] = True
        if dx or dy:
            forma["dx"], forma["dy"] = dx, dy
        if cor:
            forma["cor"] = cor
        if modulo:
            forma["modulo"] = True
        if visivel is not None:
            forma["visivel"] = visivel
        self._formas.append(forma)

    def seta(
        self,
        x: float,
        y: float,
        nx: float,
        ny: float,
        *,
        comprimento: float,
        canal: int | None = None,
        ref: float | None = None,
        chega: bool = False,
        cor: str = "#de5524",
        largura: float = 3.0,
        rotulo: str = "",
        casas: int = 1,
        proporcional: bool = True,
        minimo_px: float = 16.0,
    ) -> None:
        """Seta de valor a partir de (x, y), estendida na direção (nx, ny) por ``comprimento``
        (unidade do desenho) quando o valor do ``canal`` chega a ``ref``. O sinal troca a ponta
        de lado; com ``chega``, o valor positivo chega em (x, y), como o calor que entra numa face.
        Some quando o valor fica abaixo de 3 % de ``ref``."""
        forma: dict[str, Any] = {
            "tipo": "seta",
            "x": float(x),
            "y": float(y),
            "nx": float(nx),
            "ny": float(ny),
            "comprimento": float(comprimento),
            "chega": chega,
            "cor": cor,
            "largura": largura,
            "proporcional": proporcional,
            "minimo_px": minimo_px,
        }
        if canal is not None:
            forma["canal"] = canal
            referencia = ref
            if referencia is None:
                referencia = float(np.max(np.abs(self._canais[canal]), initial=0.0)) or 1.0
            forma["ref"] = referencia
        if rotulo:
            forma["rotulo"] = rotulo
            forma["casas"] = casas
        self._formas.append(forma)

    def cota(
        self,
        de: Sequence[float],
        ate: Sequence[float],
        texto: str,
        *,
        desloc: float = 0.0,
    ) -> None:
        """Linha de medida de ``de`` a ``ate`` (unidade do desenho), afastada ``desloc`` px para a
        esquerda do sentido de → até."""
        self._formas.append(
            {
                "tipo": "cota",
                "de": [float(de[0]), float(de[1])],
                "ate": [float(ate[0]), float(ate[1])],
                "texto": texto,
                "desloc": float(desloc),
            }
        )

    def _valor_ou_cor(
        self, forma: dict[str, Any], escala: int | None, canal: int | None, cor: str | None
    ) -> None:
        if canal is not None:
            if escala is None:
                raise ValueError("Forma com canal precisa da escala de cores.")
            forma["canal"], forma["escala"] = canal, escala
        elif cor:
            forma["cor"] = cor

    # ------------------------------------------------------------------ grade
    def grade(
        self,
        xs: Numeros,
        ys: Numeros,
        ativas: np.ndarray,
        quadros: np.ndarray,
        escala: int,
        *,
        nome: str = "",
    ) -> None:
        """Células coloridas: ``ativas`` são os índices i·(ny) + j das células com material e
        ``quadros`` (quadros × células) os valores, que vão como 0 a 255 dentro da escala."""
        ativas = np.asarray(ativas, dtype=np.int32)
        valores = np.asarray(quadros, dtype=float)
        if valores.shape != (self.quadros, len(ativas)):
            raise ValueError("A grade precisa de um valor por quadro e por célula.")
        if valores.size > LIMITE_DA_GRADE:
            raise ValueError("A grade tem valores demais para a animação.")
        esc = self._escalas[escala]
        faixa = esc["max"] - esc["min"]
        q = np.clip(np.rint((valores - esc["min"]) / faixa * 255.0), 0, 255).astype(np.uint8)
        self._grade = {
            "xs": [round(float(x), 6) for x in xs],
            "ys": [round(float(y), 6) for y in ys],
            "celulas_b64": _b64(ativas.astype("<i4")),
            "quadros_b64": _b64(q),
            "escala": escala,
            "nome": nome,
        }

    # ------------------------------------------------------------------ gráficos
    def grafico_no_tempo(
        self,
        titulo: str,
        unidade: str,
        series: Sequence[tuple[str, int]],
        *,
        casas: int = 1,
        limites: Sequence[tuple[str, float]] = (),
        faixa: tuple[float, float] | None = None,
        marcos: Sequence[tuple[str, float | None]] = (),
    ) -> None:
        """Curvas de canais contra o tempo; um gráfico por unidade, nunca dois eixos.

        ``marcos``: instantes marcados com uma reta vertical e o nome (estabiliza, equaliza,
        chega ao alvo); os ``None`` ficam de fora."""
        grafico: dict[str, Any] = {
            "tipo": "tempo",
            "titulo": titulo,
            "unidade": unidade,
            "casas": casas,
            "series": [
                {"nome": nome, "canal": canal, "ordem": k} for k, (nome, canal) in enumerate(series)
            ],
        }
        if limites:
            grafico["limites"] = [{"nome": n, "valor": float(v)} for n, v in limites]
        if faixa is not None:
            grafico["faixa"] = {"min": float(faixa[0]), "max": float(faixa[1])}
        validos = [(n, float(t)) for n, t in marcos if t is not None and np.isfinite(t)]
        if validos:
            grafico["marcos"] = [{"nome": n, "tempo": t} for n, t in validos]
        self._graficos.append(grafico)

    def grafico_de_perfil(
        self,
        titulo: str,
        unidade: str,
        x: Numeros,
        canais: Sequence[int],
        *,
        rotulo_x: str,
        rotulo_curto: str = "x",
        nome: str = "Agora",
        outras: Sequence[tuple[str, Sequence[int]]] = (),
        fixas: Sequence[tuple[str, Numeros]] = (),
        faixa: tuple[float, float] | None = None,
        casas: int = 1,
    ) -> None:
        """Valor ao longo de uma medida no instante mostrado (um canal por ponto), com outras curvas
        que andam junto (``outras``) e curvas fixas tracejadas para comparar (o começo, o regime
        permanente)."""
        if len(x) != len(canais) or any(len(c) != len(x) for _, c in outras):
            raise ValueError("O perfil precisa de um canal por ponto.")
        series: list[dict[str, Any]] = [{"nome": nome, "canais": list(canais), "ordem": 0}]
        for rotulo, lista in outras:
            series.append({"nome": rotulo, "canais": list(lista), "ordem": len(series)})
        for k, (rotulo, valores) in enumerate(fixas, start=len(series)):
            series.append(
                {
                    "nome": rotulo,
                    "valores": [round(float(v), 6) for v in valores],
                    "ordem": k,
                    "tracejado": True,
                    "fraca": True,
                }
            )
        grafico: dict[str, Any] = {
            "tipo": "perfil",
            "titulo": titulo,
            "unidade": unidade,
            "x": [round(float(v), 6) for v in x],
            "rotulo_x": rotulo_x,
            "rotulo_curto": rotulo_curto,
            "casas": casas,
            "series": series,
        }
        if faixa is not None:
            grafico["faixa"] = {"min": float(faixa[0]), "max": float(faixa[1])}
        self._graficos.append(grafico)

    # ------------------------------------------------------------------ saída
    def como_dados(self) -> dict[str, Any]:
        if self.vista is None:
            raise ValueError("Defina a vista (a caixa do desenho) da cena.")
        n = len(self._canais)
        matriz = (
            np.stack(self._canais, axis=1).astype("<f4")
            if n
            else np.zeros((self.quadros, 0), dtype="<f4")
        )
        duracao = float(self.tempos[-1] - self.tempos[0])
        u = unidade_de_tempo(duracao)
        x0, y0, x1, y1 = self.vista
        dados: dict[str, Any] = {
            "id": self.id,
            "tempos": [float(t) for t in self.tempos],
            "unidade_tempo": {"rotulo": u.rotulo, "fator": u.fator, "casas": u.casas},
            "n_canais": n,
            "canais_b64": _b64(matriz),
            "escalas": list(self._escalas),
            "formas": list(self._formas),
            "graficos": list(self._graficos),
            "vista": {"x0": float(x0), "y0": float(y0), "x1": float(x1), "y1": float(y1)},
            "nota": self.nota,
        }
        if self._grade is not None:
            dados["grade"] = self._grade
        if self.altura:
            dados["altura"] = int(self.altura)
        return dados
