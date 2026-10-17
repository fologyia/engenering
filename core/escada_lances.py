"""Escada com lances e patamares: a geometria de cada lance e o esquemático em vista lateral.

Parte do resultado da página do degrau (:mod:`core.degrau_escada`: espelho ``h``, piso ``b`` e a
divisão automática em lances) e acrescenta os **patamares que o projeto pedir**, cada um com a sua
altura, comprimento e largura e com o sentido do lance seguinte (segue em frente ou volta, como na
escada em U). Sem patamares informados, vale a divisão automática do degrau (lances o mais iguais
possível, patamar com o comprimento informado na página).

Espelho igual em toda a escada (passo regular) é o padrão: a altura pedida de cada patamar vai para
o múltiplo de ``h`` mais próximo e a tabela mostra a diferença. Sem o ajuste, cada lance tem o seu
espelho (o desnível dele dividido pelo número de espelhos mais próximo do alvo) e o seu piso pela
fórmula de Blondel, com um alerta de passo irregular.

Convenção da geometria de um lance de ``n`` espelhos: os degraus em grade são ``n − 1`` (o último
espelho chega ao patamar ou ao piso de chegada); a **projeção** do lance, do primeiro espelho à
borda do patamar, é ``(n − 1)·b``; a **linha dos bocéis** (por onde corre a longarina) vai do piso
de partida, um piso antes do primeiro espelho, até a borda do patamar: ``n·b`` na horizontal e
``n·h`` na vertical, com inclinação ``α = atan(h/b)``.

Sem Streamlit.
"""

from __future__ import annotations

import io
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from PIL import Image, ImageDraw

from core import degrau_escada as de
from core.beam_charts import ImagemDiagrama, _fonte

_ESC = 2


@dataclass(frozen=True)
class PatamarInformado:
    """Um patamar pedido: nível do piso (a partir do piso de partida), comprimento e largura."""

    altura_mm: float
    comprimento_mm: float
    largura_mm: float | None = None  # vazio = largura da escada
    volta: bool = False  # o lance seguinte volta no sentido contrário (escada em U)


@dataclass(frozen=True)
class Lance:
    numero: int
    nivel_inicial_mm: float
    nivel_final_mm: float
    n_espelhos: int
    h_mm: float
    b_mm: float
    largura_mm: float
    x_pe_mm: float  # pé da linha dos bocéis (no nível inicial), na vista lateral
    sentido: int  # +1: para a direita na vista lateral; −1: para a esquerda

    @property
    def altura_mm(self) -> float:
        return self.nivel_final_mm - self.nivel_inicial_mm

    @property
    def n_degraus(self) -> int:
        return self.n_espelhos - 1

    @property
    def projecao_mm(self) -> float:
        """Do primeiro espelho à borda do patamar: ``(n − 1)·b``."""
        return self.n_degraus * self.b_mm

    @property
    def vao_longarina_mm(self) -> float:
        """Projeção horizontal da linha dos bocéis, do piso de partida ao patamar: ``n·b``."""
        return self.n_espelhos * self.b_mm

    @property
    def alfa_graus(self) -> float:
        return math.degrees(math.atan2(self.h_mm, self.b_mm))

    @property
    def comprimento_inclinado_mm(self) -> float:
        return math.hypot(self.altura_mm, self.vao_longarina_mm)

    @property
    def x_topo_mm(self) -> float:
        return self.x_pe_mm + self.sentido * self.vao_longarina_mm


@dataclass(frozen=True)
class Patamar:
    numero: int
    nivel_mm: float
    nivel_pedido_mm: float
    comprimento_mm: float
    largura_mm: float
    x_inicio_mm: float  # borda de chegada do lance de baixo
    sentido: int  # para onde o patamar se estende a partir da borda
    volta: bool

    @property
    def x_fim_mm(self) -> float:
        return self.x_inicio_mm + self.sentido * self.comprimento_mm


@dataclass(frozen=True)
class EscadaComPatamares:
    H_mm: float
    largura_mm: float
    enquadramento: str
    lances: tuple[Lance, ...]
    patamares: tuple[Patamar, ...]
    automatica: bool
    ajustada_ao_espelho: bool
    verificacoes: tuple[de.VerificacaoDegrau, ...]
    avisos: tuple[str, ...] = field(default_factory=tuple)

    @property
    def espelhos_iguais(self) -> bool:
        return max(ln.h_mm for ln in self.lances) - min(ln.h_mm for ln in self.lances) < 0.5

    @property
    def extensao_mm(self) -> tuple[float, float]:
        xs = [x for ln in self.lances for x in (ln.x_pe_mm, ln.x_topo_mm)]
        xs += [x for p in self.patamares for x in (p.x_inicio_mm, p.x_fim_mm)]
        return min(xs), max(xs)


def _n(valor: float, casas: int = 0) -> str:
    return de.numero_pt(valor, casas)


def _espelhos_do_lance(
    desnivel: float, e: de.EntradaDegrau, numero: int
) -> tuple[int, float, float]:
    """Espelhos, h e b de um lance com o seu próprio desnível (sem o ajuste ao espelho comum)."""
    try:
        faixa = de.faixa_espelho(desnivel, e.h_alvo_mm, e.enquadramento, e.espelho_fechado)
        n = de.escolher_n(faixa, None)
    except de.EntradaInvalida as erro:
        raise de.EntradaInvalida(f"Lance {numero}: {erro}") from erro
    h = desnivel / n
    b = de.piso_b(h, e.enquadramento, e.espelho_fechado, e.b_imposto_mm)
    if not b > 0:
        raise de.EntradaInvalida(
            f"Lance {numero}: o piso b resultou em {_n(b, 1)} mm com h = {_n(h, 1)} mm."
        )
    return n, h, b


def montar_escada(
    r: de.ResultadoEscada,
    patamares: Sequence[PatamarInformado] = (),
    *,
    ajustar_ao_espelho: bool = True,
    lances_em_u: bool = False,
) -> EscadaComPatamares:
    """Os lances e patamares da escada, posicionados na vista lateral, e as verificações deles.

    Sem ``patamares``, a divisão automática do degrau (``r.lances``); ``lances_em_u`` faz cada lance
    voltar no sentido contrário. Levanta :class:`de.EntradaInvalida` com o que corrigir.
    """
    e, g = r.entrada, r.geometria
    H, largura = e.H_mm, e.L_mm
    avisos: list[str] = []
    pedidos = sorted(patamares, key=lambda p: p.altura_mm)
    automatica = not pedidos
    # (nível pedido, nível adotado, comprimento, largura, volta) de cada patamar
    niveis: list[tuple[float, float, float, float, bool]] = []
    if automatica:
        ln = r.lances
        com_k = ln.n_lances if ln.k == ln.k_min else g.n - ln.n_lances * ln.k_min
        acumulado = 0
        for i in range(ln.n_lances - 1):
            acumulado += ln.k if i < com_k else ln.k_min
            nivel = acumulado * g.h_mm
            niveis.append((nivel, nivel, e.patamar_mm, largura, lances_em_u))
    else:
        for p in pedidos:
            if not 0 < p.altura_mm < H:
                raise de.EntradaInvalida(
                    f"O patamar a {_n(p.altura_mm)} mm está fora da escada (0 < altura < "
                    f"H = {_n(H)} mm)."
                )
            if p.comprimento_mm <= 0:
                raise de.EntradaInvalida(
                    f"O patamar a {_n(p.altura_mm)} mm precisa de comprimento maior que zero."
                )
            if p.largura_mm is not None and p.largura_mm <= 0:
                raise de.EntradaInvalida(
                    f"O patamar a {_n(p.altura_mm)} mm precisa de largura maior que zero."
                )
            nivel = p.altura_mm
            if ajustar_ao_espelho:
                nivel = round(p.altura_mm / g.h_mm) * g.h_mm
                if not 0 < nivel < H - 0.5 * g.h_mm:
                    raise de.EntradaInvalida(
                        f"O patamar a {_n(p.altura_mm)} mm fica a menos de um espelho "
                        f"({_n(g.h_mm, 1)} mm) do piso de partida ou da chegada: retire-o ou mude "
                        "a altura."
                    )
            niveis.append((p.altura_mm, nivel, p.comprimento_mm, p.largura_mm or largura, p.volta))
        adotados = [nv[1] for nv in niveis]
        if len({round(x, 3) for x in adotados}) != len(adotados):
            raise de.EntradaInvalida(
                "Dois patamares ficaram no mesmo nível"
                + (" depois do ajuste ao espelho" if ajustar_ao_espelho else "")
                + ": afaste as alturas de pelo menos um espelho."
            )

    limites = [0.0, *(nv[1] for nv in niveis), H]
    lances: list[Lance] = []
    patamares_saida: list[Patamar] = []
    x_pe, sentido = 0.0, 1
    for i in range(len(limites) - 1):
        desnivel = limites[i + 1] - limites[i]
        if automatica or ajustar_ao_espelho:
            n = max(int(round(desnivel / g.h_mm)), 1)
            h, b = desnivel / n, g.b_mm
        else:
            n, h, b = _espelhos_do_lance(desnivel, e, i + 1)
        if n < 2:
            avisos.append(
                f"Lance {i + 1} com um espelho só ({_n(h, 1)} mm): não tem degrau em grade nem "
                "longarina; confira se o patamar não deveria ser o piso de chegada."
            )
        largura_lance = largura
        lance = Lance(i + 1, limites[i], limites[i + 1], n, h, b, largura_lance, x_pe, sentido)
        lances.append(lance)
        if i < len(niveis):
            pedido, nivel, comprimento, larg_pat, volta = niveis[i]
            borda = lance.x_topo_mm
            patamares_saida.append(
                Patamar(i + 1, nivel, pedido, comprimento, larg_pat, borda, sentido, volta)
            )
            if volta:  # escada em U: o próximo lance sai da mesma borda, no sentido contrário
                sentido = -sentido
                x_pe = borda - sentido * b
            else:
                primeiro_espelho = borda + sentido * comprimento
                x_pe = primeiro_espelho - sentido * b
    verificacoes = _verificacoes(r, lances, patamares_saida, ajustar_ao_espelho or automatica)
    return EscadaComPatamares(
        H_mm=H,
        largura_mm=largura,
        enquadramento=e.enquadramento,
        lances=tuple(lances),
        patamares=tuple(patamares_saida),
        automatica=automatica,
        ajustada_ao_espelho=ajustar_ao_espelho or automatica,
        verificacoes=tuple(verificacoes),
        avisos=tuple(avisos),
    )


def _linha(
    nome: str,
    referencia: str,
    texto: str,
    *,
    valor: float | None = None,
    limite: float | None = None,
    minimo: bool = False,
    status: str | None = None,
    tipo: str = "limite",
) -> de.VerificacaoDegrau:
    """Linha no formato das verificações do degrau (Valor e Limite em mm)."""
    if status is None:
        assert valor is not None and limite is not None
        passa = valor >= limite - de.TOL_MM if minimo else valor <= limite + de.TOL_MM
        status = "OK" if passa else "NÃO OK"
    if limite is None:
        solicitante, resistente = None, valor
    elif minimo:
        solicitante, resistente = limite, valor
    else:
        solicitante, resistente = valor, limite
    return de.VerificacaoDegrau(
        nome=nome,
        solicitante=solicitante,
        resistente=resistente,
        unidade="mm" if valor is not None else "—",
        referencia=referencia,
        formula=texto,
        status=status,
        tipo=tipo,
        valor=valor,
        limite=limite,
    )


#: Linhas do degrau que a divisão automática em lances produz e que a escada com patamares
#: informados substitui (ver :func:`aplicar_na_escada`).
SUBSTITUIDAS = (
    "Altura do lance maior ≤ altura máxima por lance",
    "Espelhos e lances uniformes",
    "Patamar intermediário ≥ 600 mm",
)


def _verificacoes(
    r: de.ResultadoEscada,
    lances: Sequence[Lance],
    patamares: Sequence[Patamar],
    ajustada: bool,
) -> list[de.VerificacaoDegrau]:
    e = r.entrada
    nr22 = e.enquadramento == de.NR22
    ce = e.espelho_fechado
    ref_lance = (
        "NR-22 22.10.1.1 b)"
        if nr22
        else ("NR-12 Anexo III 12 e)" if ce else "NR-12 Anexo III 11 e)")
    )
    ref_uniforme = (
        "NR-22 22.10.1 e)" if nr22 else ("NR-12 Anexo III 12 c)" if ce else "NR-12 Anexo III 11 c)")
    )
    ref_patamar = "NR-22 22.9.3" if nr22 else "NR-12 Anexo III 11 e)"
    maximo = r.lances.altura_max_legal_mm
    linhas: list[de.VerificacaoDegrau] = []
    for ln in lances:
        linhas.append(
            _linha(
                f"Lance {ln.numero}: altura ≤ {_n(maximo)} mm",
                ref_lance,
                f"{ln.n_espelhos} espelhos × {_n(ln.h_mm, 1)} = {_n(ln.altura_mm)} mm; "
                f"b = {_n(ln.b_mm)} mm; α = {_n(ln.alfa_graus, 1)}°",
                valor=ln.altura_mm,
                limite=maximo,
            )
        )
    hs = sorted({round(ln.h_mm, 1) for ln in lances})
    ns = sorted({ln.n_espelhos for ln in lances})
    espelhos_iguais = hs[-1] - hs[0] < 0.5
    if len(lances) > 1:
        if espelhos_iguais and len(ns) == 1:
            texto, status = f"{len(lances)} lances de {ns[0]} espelhos de {_n(hs[0], 1)} mm", "OK"
        elif espelhos_iguais:
            texto = (
                f"espelhos iguais ({_n(hs[0], 1)} mm), mas lances com "
                + ", ".join(str(ln.n_espelhos) for ln in lances)
                + " espelhos"
            )
            status = "ALERTA"
        else:
            texto = (
                "espelhos de "
                + ", ".join(_n(x, 1) for x in hs)
                + " mm: ajuste a altura dos patamares a múltiplos do espelho"
            )
            status = "ALERTA"
        linhas.append(_linha("Espelhos e lances uniformes", ref_uniforme, texto, status=status))
    for p in patamares:
        linhas.append(
            _linha(
                f"Patamar {p.numero}: comprimento ≥ {_n(de.K['pat_min'])} mm",
                ref_patamar,
                f"patamar a +{_n(p.nivel_mm)} mm: {_n(p.comprimento_mm)} × {_n(p.largura_mm)} mm "
                "(comprimento × largura)",
                valor=p.comprimento_mm,
                limite=de.K["pat_min"],
                minimo=True,
            )
        )
        if p.largura_mm + de.TOL_MM < e.L_mm:
            linhas.append(
                _linha(
                    f"Patamar {p.numero}: largura ≥ largura da escada",
                    "passagem contínua",
                    f"o patamar ({_n(p.largura_mm)} mm) estreita a passagem da escada "
                    f"({_n(e.L_mm)} mm)",
                    valor=p.largura_mm,
                    limite=e.L_mm,
                    minimo=True,
                )
            )
    if ajustada:
        movidos = [p for p in patamares if abs(p.nivel_mm - p.nivel_pedido_mm) > 0.5]
        if movidos:
            linhas.append(
                _linha(
                    "Altura dos patamares ajustada ao espelho",
                    "passo regular",
                    "; ".join(
                        f"patamar {p.numero}: pedido {_n(p.nivel_pedido_mm)} → {_n(p.nivel_mm)} mm"
                        for p in movidos
                    ),
                    status="INFO",
                    tipo="informativo",
                )
            )
    return linhas


def aplicar_na_escada(r: de.ResultadoEscada, esc: EscadaComPatamares) -> de.ResultadoEscada:
    """O resultado do degrau com as verificações de lance e patamar da escada real.

    Com a divisão automática nada muda (as linhas do degrau já são dessa escada). Com patamares
    informados, as linhas da divisão automática (altura do lance maior, lances uniformes e
    patamar) dão lugar às de cada lance e patamar informados, na mesma posição.
    """
    if esc.automatica:
        return r
    linhas: list[de.VerificacaoDegrau] = []
    inseridas = False
    for v in r.verificacoes:
        if v.nome in SUBSTITUIDAS:
            if not inseridas:
                linhas.extend(esc.verificacoes)
                inseridas = True
            continue
        linhas.append(v)
    if not inseridas:
        linhas.extend(esc.verificacoes)
    return replace(r, verificacoes=tuple(linhas))


def texto_dos_lances(esc: EscadaComPatamares) -> str:
    """Resumo da divisão: "3 lances (8, 13 e 9 espelhos de 180 mm) e 2 patamares"."""
    ns = [str(ln.n_espelhos) for ln in esc.lances]
    lista = ns[0] if len(ns) == 1 else ", ".join(ns[:-1]) + " e " + ns[-1]
    hs = sorted({round(ln.h_mm, 1) for ln in esc.lances})
    espelho = f"{_n(hs[0], 1)} mm" if hs[-1] - hs[0] < 0.5 else "espelhos diferentes"
    texto = f"{len(esc.lances)} lance(s) ({lista} espelhos; {espelho})"
    if esc.patamares:
        texto += f" e {len(esc.patamares)} patamar(es)"
        if any(p.volta for p in esc.patamares):
            texto += ", em U"
    return texto


# ---------------------------------------------------------------------------------------------
# Tabelas
# ---------------------------------------------------------------------------------------------
CABECALHO_LANCES = [
    "Lance",
    "Níveis (mm)",
    "Espelhos",
    "h (mm)",
    "b (mm)",
    "α (°)",
    "Projeção (mm)",
    "Largura (mm)",
]
CABECALHO_PATAMARES = ["Patamar", "Nível (mm)", "Comprimento (mm)", "Largura (mm)", "Depois dele"]


def linhas_dos_lances(esc: EscadaComPatamares) -> list[list[str]]:
    return [
        [
            str(ln.numero),
            f"+{_n(ln.nivel_inicial_mm)} → +{_n(ln.nivel_final_mm)}",
            str(ln.n_espelhos),
            _n(ln.h_mm, 1),
            _n(ln.b_mm),
            _n(ln.alfa_graus, 1),
            _n(ln.projecao_mm),
            _n(ln.largura_mm),
        ]
        for ln in esc.lances
    ]


def linhas_dos_patamares(esc: EscadaComPatamares) -> list[list[str]]:
    return [
        [
            str(p.numero),
            f"+{_n(p.nivel_mm)}"
            + (
                f" (pedido +{_n(p.nivel_pedido_mm)})"
                if abs(p.nivel_mm - p.nivel_pedido_mm) > 0.5
                else ""
            ),
            _n(p.comprimento_mm),
            _n(p.largura_mm),
            "o lance volta (U)" if p.volta else "segue em frente",
        ]
        for p in esc.patamares
    ]


# ---------------------------------------------------------------------------------------------
# Gravação (para o memorial redesenhar o esquemático)
# ---------------------------------------------------------------------------------------------
def para_dicionario(esc: EscadaComPatamares) -> dict[str, Any]:
    return {
        "H_mm": esc.H_mm,
        "largura_mm": esc.largura_mm,
        "lances": [
            {
                "numero": ln.numero,
                "nivel_inicial_mm": ln.nivel_inicial_mm,
                "nivel_final_mm": ln.nivel_final_mm,
                "n_espelhos": ln.n_espelhos,
                "h_mm": ln.h_mm,
                "b_mm": ln.b_mm,
                "largura_mm": ln.largura_mm,
                "x_pe_mm": ln.x_pe_mm,
                "sentido": ln.sentido,
            }
            for ln in esc.lances
        ],
        "patamares": [
            {
                "numero": p.numero,
                "nivel_mm": p.nivel_mm,
                "nivel_pedido_mm": p.nivel_pedido_mm,
                "comprimento_mm": p.comprimento_mm,
                "largura_mm": p.largura_mm,
                "x_inicio_mm": p.x_inicio_mm,
                "sentido": p.sentido,
                "volta": p.volta,
            }
            for p in esc.patamares
        ],
    }


def geometria_do_dicionario(
    dados: Mapping[str, Any],
) -> tuple[float, tuple[Lance, ...], tuple[Patamar, ...]]:
    """O que o esquemático precisa, lido do registro gravado."""
    lances = tuple(
        Lance(
            int(x["numero"]),
            float(x["nivel_inicial_mm"]),
            float(x["nivel_final_mm"]),
            int(x["n_espelhos"]),
            float(x["h_mm"]),
            float(x["b_mm"]),
            float(x["largura_mm"]),
            float(x["x_pe_mm"]),
            int(x["sentido"]),
        )
        for x in dados["lances"]
    )
    patamares = tuple(
        Patamar(
            int(x["numero"]),
            float(x["nivel_mm"]),
            float(x["nivel_pedido_mm"]),
            float(x["comprimento_mm"]),
            float(x["largura_mm"]),
            float(x["x_inicio_mm"]),
            int(x["sentido"]),
            bool(x["volta"]),
        )
        for x in dados.get("patamares", [])
    )
    return float(dados["H_mm"]), lances, patamares


# ---------------------------------------------------------------------------------------------
# Esquemático (vista lateral)
# ---------------------------------------------------------------------------------------------
_CORES_LANCES = ("#1d4ed8", "#0f766e", "#b45309", "#7c3aed", "#be123c")
_LINHA = "#1e293b"
_FRACO = "#94a3b8"
_TEXTO = "#0f172a"
_TEXTO_FRACO = "#64748b"
_FUNDO = "#ffffff"


def figura_esquematico(
    H_mm: float,
    lances: Sequence[Lance],
    patamares: Sequence[Patamar],
    *,
    titulo: str = "Esquemático da escada (vista lateral)",
    largura_px: int = 1000,
    altura_max_px: int = 640,
) -> ImagemDiagrama:
    """Vista lateral: degraus de cada lance, linha da longarina com o ângulo, patamares e níveis."""
    if not lances:
        raise ValueError("A escada não tem lances.")
    xs = [x for ln in lances for x in (ln.x_pe_mm, ln.x_topo_mm)]
    xs += [x for p in patamares for x in (p.x_inicio_mm, p.x_fim_mm)]
    chegada_borda = lances[-1].x_topo_mm
    chegada_fim = chegada_borda + lances[-1].sentido * 900.0
    xs += [chegada_fim, xs[0] - lances[0].sentido * 600.0]
    x_min, x_max = min(xs), max(xs)
    topo, base, lados = 70, 70, 120
    util_l = (largura_px - 2 * lados) * _ESC
    util_a = (altura_max_px - topo - base) * _ESC
    escala = min(util_l / max(x_max - x_min, 1.0), util_a / max(H_mm, 1.0))
    altura_px = max(int(H_mm * escala / _ESC) + topo + base, 300)
    esquerda = (largura_px * _ESC - (x_max - x_min) * escala) / 2
    chao = (altura_px - base) * _ESC

    def p(x: float, y: float) -> tuple[float, float]:
        return (esquerda + (x - x_min) * escala, chao - y * escala)

    imagem = Image.new("RGB", (largura_px * _ESC, altura_px * _ESC), _FUNDO)
    d = ImageDraw.Draw(imagem)
    fonte = _fonte(11 * _ESC)
    fonte_titulo = _fonte(16 * _ESC)
    caixas: list[tuple[float, float, float, float]] = []

    def escrever(centro: tuple[float, float], texto: str, cor: str = _TEXTO) -> None:
        caixa = d.textbbox(centro, texto, font=fonte, anchor="mm")
        for _ in range(6):
            if not any(
                not (caixa[2] < o[0] or o[2] < caixa[0] or caixa[3] < o[1] or o[3] < caixa[1])
                for o in caixas
            ):
                break
            centro = (centro[0], centro[1] - (caixa[3] - caixa[1]) - 4 * _ESC)
            caixa = d.textbbox(centro, texto, font=fonte, anchor="mm")
        caixas.append(caixa)
        d.rectangle([caixa[0] - 3, caixa[1] - 2, caixa[2] + 3, caixa[3] + 2], fill=_FUNDO)
        d.text(centro, texto, fill=cor, font=fonte, anchor="mm")

    # piso de partida, hachurado
    a, z = p(x_min, 0), p(x_max, 0)
    d.line([a, z], fill=_LINHA, width=2 * _ESC)
    for k in range(int((z[0] - a[0]) / (10 * _ESC)) + 1):
        x0 = a[0] + k * 10 * _ESC
        d.line([(x0, a[1]), (x0 - 7 * _ESC, a[1] + 7 * _ESC)], fill=_FRACO, width=_ESC)

    # lances: degraus e linha da longarina
    for ln in lances:
        cor = _CORES_LANCES[(ln.numero - 1) % len(_CORES_LANCES)]
        s = ln.sentido
        y0 = ln.nivel_inicial_mm
        perfil = [p(ln.x_pe_mm + s * ln.b_mm, y0)]
        for j in range(1, ln.n_espelhos + 1):
            x_esp = ln.x_pe_mm + s * j * ln.b_mm
            perfil.append(p(x_esp, y0 + j * ln.h_mm))
            if j < ln.n_espelhos:
                perfil.append(p(x_esp + s * ln.b_mm, y0 + j * ln.h_mm))
        d.line(perfil, fill=cor, width=2 * _ESC)
        pe, topo_ln = p(ln.x_pe_mm, y0), p(ln.x_topo_mm, ln.nivel_final_mm)
        # longarina: a linha dos bocéis, um pouco abaixo (só para não cobrir os degraus)
        desvio = 5 * _ESC
        d.line(
            [(pe[0], pe[1] + desvio), (topo_ln[0], topo_ln[1] + desvio)],
            fill=_FRACO,
            width=3 * _ESC,
        )
        # ângulo no pé
        raio = 34 * _ESC
        if s > 0:
            inicio, fim = -ln.alfa_graus, 0.0
        else:
            inicio, fim = 180.0, 180.0 + ln.alfa_graus
        d.arc(
            [pe[0] - raio, pe[1] - raio, pe[0] + raio, pe[1] + raio],
            inicio,
            fim,
            fill=cor,
            width=2 * _ESC,
        )
        meio_ang = math.radians((inicio + fim) / 2)
        escrever(
            (
                pe[0] + math.cos(meio_ang) * (raio + 30 * _ESC),
                pe[1] + math.sin(meio_ang) * (raio + 10 * _ESC),
            ),
            f"α = {_n(ln.alfa_graus, 1)}°",
            cor,
        )
        meio = p((ln.x_pe_mm + ln.x_topo_mm) / 2, (y0 + ln.nivel_final_mm) / 2)
        alfa = math.radians(ln.alfa_graus)
        fora = (-s * math.sin(alfa), -math.cos(alfa))  # do lado dos degraus, na tela
        escrever(
            (meio[0] + fora[0] * 60 * _ESC, meio[1] + fora[1] * 60 * _ESC),
            f"Lance {ln.numero}: {ln.n_espelhos} × {_n(ln.h_mm, 1)} mm, b = {_n(ln.b_mm)} mm",
            cor,
        )

    # patamares
    for pt in patamares:
        a, z = p(pt.x_inicio_mm, pt.nivel_mm), p(pt.x_fim_mm, pt.nivel_mm)
        d.line([a, z], fill=_LINHA, width=4 * _ESC)
        centro = ((a[0] + z[0]) / 2, a[1] - 14 * _ESC)
        escrever(centro, f"Patamar {pt.numero}: {_n(pt.comprimento_mm)} × {_n(pt.largura_mm)} mm")
    # chegada
    a, z = p(chegada_borda, H_mm), p(chegada_fim, H_mm)
    d.line([a, z], fill=_LINHA, width=4 * _ESC)
    for k in range(int(abs(z[0] - a[0]) / (10 * _ESC)) + 1):
        x0 = min(a[0], z[0]) + k * 10 * _ESC
        d.line([(x0, a[1]), (x0 - 7 * _ESC, a[1] + 7 * _ESC)], fill=_FRACO, width=_ESC)
    escrever(((a[0] + z[0]) / 2, a[1] - 14 * _ESC), "Chegada")

    # cotas de nível, à esquerda
    niveis = sorted({0.0, H_mm, *(pt.nivel_mm for pt in patamares)})
    x_cota = esquerda - 46 * _ESC
    for nivel in niveis:
        y = p(x_min, nivel)[1]
        d.line([(x_cota, y), (esquerda - 8 * _ESC, y)], fill=_FRACO, width=_ESC)
        d.polygon(
            [(x_cota, y), (x_cota - 6 * _ESC, y - 8 * _ESC), (x_cota + 6 * _ESC, y - 8 * _ESC)],
            outline=_TEXTO_FRACO,
            fill=_FUNDO,
        )
        d.text((x_cota - 10 * _ESC, y), f"+{_n(nivel)}", fill=_TEXTO, font=fonte, anchor="rm")
    # extensão horizontal da escada (lances e patamares), embaixo
    y_cota = chao + 34 * _ESC
    da_escada = [x for ln in lances for x in (ln.x_pe_mm, ln.x_topo_mm)]
    da_escada += [x for pt in patamares for x in (pt.x_inicio_mm, pt.x_fim_mm)]
    total = max(da_escada) - min(da_escada)
    pa, pb = p(min(da_escada), 0)[0], p(max(da_escada), 0)[0]
    d.line([(pa, y_cota), (pb, y_cota)], fill=_TEXTO_FRACO, width=_ESC)
    for x in (pa, pb):
        d.line([(x, y_cota - 6 * _ESC), (x, y_cota + 6 * _ESC)], fill=_TEXTO_FRACO, width=_ESC)
    d.text(
        ((pa + pb) / 2, y_cota + 12 * _ESC),
        f"{_n(total)} mm (da linha dos bocéis no piso à borda mais distante)",
        fill=_TEXTO_FRACO,
        font=fonte,
        anchor="mm",
    )
    d.text((18 * _ESC, 12 * _ESC), titulo, fill=_TEXTO, font=fonte_titulo)
    d.text(
        (18 * _ESC, 34 * _ESC),
        f"Desnível H = {_n(H_mm)} mm; cotas em mm. Linha cinza: longarina (linha dos bocéis).",
        fill=_TEXTO_FRACO,
        font=fonte,
    )
    final = imagem.resize((largura_px, altura_px), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    final.save(buffer, format="PNG", optimize=True)
    legenda = "Lances — " + "; ".join(
        f"{ln.numero}: {ln.n_espelhos} espelhos de {_n(ln.h_mm, 1)} mm, piso {_n(ln.b_mm)} mm, "
        f"α = {_n(ln.alfa_graus, 1)}°, de +{_n(ln.nivel_inicial_mm)} a +{_n(ln.nivel_final_mm)} mm"
        for ln in lances
    )
    if patamares:
        legenda += ". Patamares — " + "; ".join(
            f"{pt.numero}: +{_n(pt.nivel_mm)} mm, {_n(pt.comprimento_mm)} × {_n(pt.largura_mm)} mm"
            + (" (o lance seguinte volta)" if pt.volta else "")
            for pt in patamares
        )
    return ImagemDiagrama(titulo, legenda + ".", buffer.getvalue(), largura_px, altura_px)


def figura_da_escada(esc: EscadaComPatamares, **opcoes: Any) -> ImagemDiagrama:
    return figura_esquematico(esc.H_mm, esc.lances, esc.patamares, **opcoes)
