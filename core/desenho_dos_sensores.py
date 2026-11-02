"""O gráfico dos sensores do SolidWorks: cada sensor verificado, combinação a combinação, com o
limite — o mesmo desenho na página (SVG) e no memorial (PNG).

Um painel por sensor verificado (tensão e fator de segurança nas ELU, deslocamento nas ELS), uma
barra por combinação na ordem do quadro. A que governa sai escura e com o valor escrito; as que
ficaram fora da verificação (resultado repetido) saem em vermelho claro, para se ver que existem e
não contam. A linha tracejada é o limite (``f_y/γ_a1``, ``γ_a1`` ou o limite do deslocamento).

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core import cena_3d as c3

COR_ELU = "#4a78c2"
COR_ELS = "#2a9d8f"
COR_GOVERNA = "#1d3557"
COR_FORA = "#f4d4d4"
COR_FORA_CONTORNO = "#d98c8c"
COR_LIMITE = "#b3261e"
COR_GRADE = "#e3e6ea"
COR_EIXO = "#5b636e"
COR_TEXTO = "#1f2328"
COR_SUAVE = "#6b7280"

LARGURA = 1000.0
ALTURA_DO_PAINEL = 250.0
TOPO = 78.0
RODAPE = 46.0
X0, X1 = 78.0, 978.0
MAXIMO_DE_PAINEIS = 4


@dataclass(frozen=True)
class Painel:
    titulo: str
    unidade: str
    rotulos: tuple[str, ...]
    valores: tuple[float | None, ...]
    fora: tuple[bool, ...]
    limite: float | None = None
    rotulo_do_limite: str = ""
    menor_governa: bool = False  # fator de segurança: o menor é o pior
    grupo: str = "ELU"
    casas: int = 2

    @property
    def governa(self) -> int | None:
        validos = [
            (i, v)
            for i, (v, f) in enumerate(zip(self.valores, self.fora, strict=True))
            if v is not None and not f
        ]
        if not validos:
            return None
        escolha = min if self.menor_governa else max
        return escolha(validos, key=lambda par: par[1])[0]


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def paineis_da_analise(a: Any) -> list[Painel]:
    """Os painéis de :class:`core.sensores_do_modelo.AnaliseDosSensores` (import tardio)."""
    from core import sensores_do_modelo as sm

    q = a.quadro
    paineis: list[Painel] = []
    for k, s in enumerate(q.sensores):
        if s.grandeza not in (sm.TENSAO, sm.FATOR_DE_SEGURANCA, sm.DESLOCAMENTO):
            continue
        grupo = sm.GRUPO_ELS if s.grandeza == sm.DESLOCAMENTO else sm.GRUPO_ELU
        linhas = [linha for linha in q.combinacoes if a.tipos.get(linha.nome) == grupo]
        if not linhas:
            continue
        valores: list[float | None] = []
        for linha in linhas:
            v = q.valor(linha, k)
            valores.append(
                None if v is None else (v if s.grandeza == sm.FATOR_DE_SEGURANCA else abs(v))
            )
        if s.grandeza == sm.TENSAO:
            limite_tensao = a.fy_MPa / sm.GAMA_A1
            limite: float | None = limite_tensao
            rotulo = f"limite fy/γa1 = {_n(a.fy_MPa, 0)}/1,10 = {_n(limite_tensao)} MPa"
        elif s.grandeza == sm.FATOR_DE_SEGURANCA:
            limite, rotulo = sm.GAMA_A1, "limite γa1 = 1,10"
        else:
            limite = s.limite.limite_mm()
            rotulo = f"limite {_n(limite)} mm" if limite is not None else ""
        nome_do_grupo = (
            "combinações últimas (ELU)" if grupo == sm.GRUPO_ELU else "combinações de serviço (ELS)"
        )
        paineis.append(
            Painel(
                titulo=f"{s.nome} — {nome_do_grupo}",
                unidade=s.unidade_de_calculo,
                rotulos=tuple(linha.nome for linha in linhas),
                valores=tuple(valores),
                fora=tuple(linha.nome in a.fora for linha in linhas),
                limite=limite,
                rotulo_do_limite=rotulo,
                menor_governa=s.grandeza == sm.FATOR_DE_SEGURANCA,
                grupo=grupo,
                casas=sm.CASAS.get(s.grandeza, 2),
            )
        )
        if len(paineis) == MAXIMO_DE_PAINEIS:
            break
    return paineis


def _passo(maximo: float, alvo: int = 4) -> float:
    if maximo <= 0:
        return 1.0
    bruto = maximo / alvo
    potencia = 10 ** math.floor(math.log10(bruto))
    for m in (1, 2, 2.5, 5, 10):
        if m * potencia >= bruto:
            return m * potencia
    return 10 * potencia


def _curto(nome: str) -> str:
    """``C09-ELU`` → ``09`` (o grupo está no título do painel)."""
    return nome.split("-", 1)[0].lstrip("C") or nome


def desenho_dos_sensores(
    paineis: Sequence[Painel], *, titulo: str = "", subtitulo: str = ""
) -> c3.Desenho2D:
    paineis = list(paineis)[:MAXIMO_DE_PAINEIS]
    altura = TOPO + ALTURA_DO_PAINEL * max(len(paineis), 1) + RODAPE
    itens: list[c3.Poligono2D | c3.Linha2D | c3.Seta2D | c3.Etiqueta2D] = []
    for p_index, p in enumerate(paineis):
        y_topo = TOPO + ALTURA_DO_PAINEL * p_index
        y_base = y_topo + ALTURA_DO_PAINEL - 66.0
        y_util = y_topo + 52.0
        itens.append(
            c3.Etiqueta2D((X0 + X1) / 2, y_topo + 14, p.titulo, COR_TEXTO, 12.0, "bold", False)
        )
        validos = [v for v in p.valores if v is not None]
        maior = max([*validos, p.limite or 0.0, 1e-9])
        passo = _passo(maior * 1.08)
        topo_da_escala = passo * math.ceil(maior * 1.08 / passo)

        def y_de(
            v: float, base: float = y_base, util: float = y_util, escala: float = topo_da_escala
        ) -> float:
            return base - (base - util) * v / escala

        # grade e escala
        marca = 0.0
        while marca <= topo_da_escala + 1e-9:
            y = y_de(marca)
            itens.append(c3.Linha2D((X0, y), (X1, y), COR_GRADE, 0.8))
            texto = f"{marca:g}".replace(".", ",")
            itens.append(
                c3.Etiqueta2D(
                    X0 - 10 - c3.largura_do_texto(texto, 9.0) / 2,
                    y,
                    texto,
                    COR_SUAVE,
                    9.0,
                    "normal",
                    False,
                )
            )
            marca += passo
        if p.unidade:
            itens.append(
                c3.Etiqueta2D(X0 - 30, y_util - 18, p.unidade, COR_SUAVE, 9.0, "bold", False)
            )
        itens.append(c3.Linha2D((X0, y_base), (X1, y_base), COR_EIXO, 1.2))
        # barras
        n = len(p.valores)
        vaga = (X1 - X0) / max(n, 1)
        largura = max(2.0, min(24.0, vaga * 0.7))
        governa = p.governa
        a_cada = max(1, math.ceil(n / 36))
        cor = COR_ELS if p.grupo == "ELS" else COR_ELU
        for i, (rotulo, v, fora) in enumerate(zip(p.rotulos, p.valores, p.fora, strict=True)):
            xc = X0 + vaga * (i + 0.5)
            if v is not None and v > 0:
                y = y_de(v)
                pontos = (
                    (xc - largura / 2, y_base),
                    (xc + largura / 2, y_base),
                    (xc + largura / 2, y),
                    (xc - largura / 2, y),
                )
                if fora:
                    itens.append(c3.Poligono2D(pontos, COR_FORA, COR_FORA_CONTORNO, 0.9))
                else:
                    preenchimento = COR_GOVERNA if i == governa else cor
                    itens.append(c3.Poligono2D(pontos, preenchimento, preenchimento, 0.3))
            if i % a_cada == 0 or i == governa:
                peso = "bold" if i == governa else "normal"
                itens.append(
                    c3.Etiqueta2D(
                        xc,
                        y_base + 12,
                        _curto(rotulo),
                        COR_TEXTO if i == governa else COR_SUAVE,
                        8.0,
                        peso,
                        False,
                    )
                )
        if governa is not None:
            v = p.valores[governa]
            if v is not None:
                xc = X0 + vaga * (governa + 0.5)
                texto = f"{p.rotulos[governa]}: {_n(v, p.casas)}" + (
                    f" {p.unidade}" if p.unidade else ""
                )
                x_texto = min(
                    max(xc, X0 + c3.largura_do_texto(texto, 9.5) / 2 + 4),
                    X1 - c3.largura_do_texto(texto, 9.5) / 2 - 4,
                )
                itens.append(c3.Etiqueta2D(x_texto, y_de(v) - 12, texto, COR_GOVERNA, 9.5, "bold"))
        # limite
        if p.limite is not None and p.limite > 0:
            y = y_de(p.limite)
            itens.append(c3.Linha2D((X0, y), (X1, y), COR_LIMITE, 1.6, "7 5"))
            if p.rotulo_do_limite:
                # no canto de cima do painel, com um pedaço da linha: não cobre as barras
                texto = p.rotulo_do_limite
                largura_texto = c3.largura_do_texto(texto, 9.5)
                y_rotulo = y_topo + 32
                itens.append(
                    c3.Linha2D(
                        (X1 - largura_texto - 40, y_rotulo),
                        (X1 - largura_texto - 12, y_rotulo),
                        COR_LIMITE,
                        1.6,
                        "7 5",
                    )
                )
                itens.append(
                    c3.Etiqueta2D(
                        X1 - largura_texto / 2 - 4, y_rotulo, texto, COR_LIMITE, 9.5, "bold", False
                    )
                )
        fora_n = sum(p.fora)
        primeiro, ultimo = (p.rotulos[0], p.rotulos[-1]) if p.rotulos else ("", "")
        nota = f"{n} combinações ({primeiro} a {ultimo})" if n > 1 else f"{primeiro}"
        if fora_n:
            nota += f" · {fora_n} fora da verificação (resultado repetido)"
        itens.append(
            c3.Etiqueta2D((X0 + X1) / 2, y_base + 32, nota, COR_SUAVE, 9.5, "normal", False)
        )
    legenda = [
        (COR_ELU, "combinação ELU"),
        (COR_ELS, "combinação ELS"),
        (COR_GOVERNA, "a que governa"),
        (COR_LIMITE, "limite"),
    ]
    if any(any(p.fora) for p in paineis):
        legenda.append((COR_FORA_CONTORNO, "fora (resultado repetido)"))
    grupos = {p.grupo for p in paineis}
    if "ELS" not in grupos:
        legenda = [par for par in legenda if par[0] != COR_ELS]
    if "ELU" not in grupos:
        legenda = [par for par in legenda if par[0] != COR_ELU]
    return c3.Desenho2D(
        LARGURA,
        altura,
        tuple(itens),
        titulo or "Sensores do modelo, combinação a combinação",
        subtitulo
        or "Valores do gerenciador de casos de carga do SolidWorks; a linha tracejada é o limite.",
        legenda=tuple(legenda),
        vazio=not paineis,
    )


def paineis_para_o_registro(paineis: Sequence[Painel]) -> dict[str, Any]:
    return {
        "paineis": [
            {
                "titulo": p.titulo,
                "unidade": p.unidade,
                "rotulos": list(p.rotulos),
                "valores": [None if v is None else round(v, 6) for v in p.valores],
                "fora": list(p.fora),
                "limite": None if p.limite is None else round(p.limite, 6),
                "rotulo_do_limite": p.rotulo_do_limite,
                "menor_governa": p.menor_governa,
                "grupo": p.grupo,
                "casas": p.casas,
            }
            for p in paineis
        ]
    }


def _numero(valor: Any) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor) if math.isfinite(valor) else None


def paineis_do_registro(dados: Any) -> list[Painel]:
    """Os painéis gravados; painel fora do formato é ignorado (o memorial não cai por um gráfico)."""
    if not isinstance(dados, Mapping) or not isinstance(dados.get("paineis"), list):
        return []
    paineis: list[Painel] = []
    for item in dados["paineis"]:
        if not isinstance(item, Mapping):
            continue
        rotulos, valores, fora = item.get("rotulos"), item.get("valores"), item.get("fora")
        if not (isinstance(rotulos, list) and isinstance(valores, list) and rotulos):
            continue
        if len(rotulos) != len(valores):
            continue
        fora_lista = (
            fora if isinstance(fora, list) and len(fora) == len(rotulos) else [False] * len(rotulos)
        )
        casas = item.get("casas")
        paineis.append(
            Painel(
                titulo=str(item.get("titulo") or ""),
                unidade=str(item.get("unidade") or ""),
                rotulos=tuple(str(r) for r in rotulos),
                valores=tuple(_numero(v) for v in valores),
                fora=tuple(bool(f) for f in fora_lista),
                limite=_numero(item.get("limite")),
                rotulo_do_limite=str(item.get("rotulo_do_limite") or ""),
                menor_governa=bool(item.get("menor_governa")),
                grupo="ELS" if item.get("grupo") == "ELS" else "ELU",
                casas=int(casas) if isinstance(casas, int) and 0 <= casas <= 6 else 2,
            )
        )
    return paineis[:MAXIMO_DE_PAINEIS]
