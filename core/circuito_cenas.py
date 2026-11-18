"""Circuito fechado: verificações, marcas no desenho, a cena do tocador e o registro no projeto."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from core import circuito as ci
from core import circuito_termico as cte
from core import figuras_no_tempo as fnt
from core.animacao import CALOR, Cena, tempo_em_texto, unidade_de_tempo
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    linhas_para_registro,
    numero_json,
    status_geral,
)

MODULO_ID = "circuito_fechado"
MODULO_TITULO = "Circuito fechado"
_N = ci._n
_REFERENCIAS = [
    "Incropera, F. P. et al. Fundamentos de Transferência de Calor e de Massa, 6ª ed. (cap. 11: "
    "ε-NTU, eq. 11.33 de fluxo cruzado).",
    "ASHRAE Handbook — HVAC Systems and Equipment (sistemas hidrônicos: vaso de expansão).",
    "Darcy-Weisbach e Colebrook; Newton nas vazões e cargas (Todini e Pilati, 1988).",
]
_COR_DOS_SIMBOLOS = {
    "fonte": "#fdd0b1",
    "dry_cooler": "#cde2fb",
    "chiller": "#9ec5f4",
    "tanque": "#b7d3f6",
}


@dataclass(frozen=True)
class Resultado:
    circuito: ci.Circuito
    hidraulica: ci.Hidraulica
    regime: cte.Regime
    tempo: cte.NoTempo | None
    condicoes: cte.Condicoes
    verificacoes: tuple[Verificacao, ...]

    @property
    def status(self) -> str:
        return status_geral(list(self.verificacoes))


def _p_vaso_no_regime(
    c: ci.Circuito, regime: cte.Regime, cond: cte.Condicoes
) -> cte.EstadoDoVaso | None:
    vaso = c.vaso
    if vaso is None or vaso.vaso is None:
        return None
    temps = np.array([regime.saidas.get(e.id, cond.t_inicial) for e in c.elementos])
    vols = np.array([e.volume_m3 for e in c.elementos])
    tabela = cte.tabela_de_massa_especifica(
        c.fluido, min(float(temps.min()), cond.t_inicial), max(float(temps.max()), cond.t_inicial)
    )
    dil = float(cte.dilatacao(vols, temps, cond.t_inicial, tabela))
    return cte.estado_do_vaso(vaso.vaso, dil)


def verificacoes(
    c: ci.Circuito,
    h: ci.Hidraulica,
    regime: cte.Regime,
    tempo: cte.NoTempo | None,
    cond: cte.Condicoes,
) -> list[Verificacao]:
    linhas: list[Verificacao] = []
    vaso = c.vaso
    assert vaso is not None and vaso.vaso is not None
    quente = _p_vaso_no_regime(c, regime, cond)
    p_vaso_frio = vaso.vaso.enchimento_bar
    p_vaso_quente = quente.pressao_bar if quente is not None else p_vaso_frio
    if tempo is not None and tempo.vaso:
        p_vaso_quente = max(p_vaso_quente, max(s.pressao_bar for s in tempo.vaso))
        p_vaso_min = min(p_vaso_frio, min(s.pressao_bar for s in tempo.vaso))
    else:
        p_vaso_min = min(p_vaso_frio, p_vaso_quente)
    prop = ci.propriedades(c.fluido, cond.t_inicial)
    # pressões: a hidráulica na pressão de enchimento, deslocada pela pressão do vaso
    for n in c.nos:
        if n.id not in h.pressoes:
            continue
        p_min = h.pressao_bar(n.id) - p_vaso_frio + p_vaso_min
        linhas.append(
            Verificacao(
                f"Pressão mínima no ponto {n.nome}",
                cond.pressao_minima_bar,
                p_min,
                "bar",
                "Pressão manométrica com o circuito frio e quente: abaixo da atmosférica entra ar",
                f"p = {_N(p_min)} bar ≥ {_N(cond.pressao_minima_bar)} bar",
                status="NÃO OK" if p_min < cond.pressao_minima_bar else "OK",
                tipo="limite",
            )
        )
    linhas.append(
        Verificacao(
            "Pressão máxima no vaso de expansão",
            p_vaso_quente,
            vaso.vaso.maxima_bar,
            "bar",
            "Com a dilatação do fluido aquecido, abaixo da válvula de segurança",
            f"p = {_N(p_vaso_quente)} bar ≤ {_N(vaso.vaso.maxima_bar)} bar",
            tipo="limite",
        )
    )
    if quente is not None:
        dilatacao = quente.dilatacao_L
        if tempo is not None and tempo.vaso:
            dilatacao = max(dilatacao, max(s.dilatacao_L for s in tempo.vaso))
        minimo = cte.volume_minimo_do_vaso(vaso.vaso, dilatacao)
        linhas.append(
            Verificacao(
                "Volume do vaso de expansão",
                minimo,
                vaso.vaso.volume_L,
                "L",
                "ASHRAE, vaso de membrana: V ≥ ΔV·p_máx·p_ench/(p₀·(p_máx − p_ench))",
                f"dilatação {_N(dilatacao, 2)} L → vaso mínimo {_N(minimo, 1)} L",
                tipo="resistencia",
            )
        )
    for e in c.elementos:
        q = abs(h.vazoes[e.id])
        if e.tipo == ci.TUBO and q > 0:
            v = q / e.area
            linhas.append(
                Verificacao(
                    f"Velocidade no tubo {e.nome}",
                    v,
                    cond.velocidade_maxima,
                    "m/s",
                    "Velocidade máxima: ruído, erosão e golpe de aríete",
                    f"v = Q/A = {_N(v)} m/s",
                    tipo="limite",
                )
            )
        if e.tipo == ci.BOMBA and e.ligada and e.npsh_requerido_m > 0:
            entrada = e.de if h.vazoes[e.id] >= 0 else e.para
            t_suc = regime.temperaturas.get(entrada, cond.t_inicial)
            pp = ci.propriedades(c.fluido, t_suc)
            p_abs = (h.pressao_bar(entrada) - p_vaso_frio + p_vaso_min) * 1e5 + ci.ATMOSFERA
            npsh = (p_abs - pp.pressao_de_vapor) / (pp.massa_especifica * ci.GRAVIDADE)
            linhas.append(
                Verificacao(
                    f"NPSH da {e.nome}",
                    e.npsh_requerido_m,
                    npsh,
                    "m",
                    "NPSH disponível na sucção maior que o pedido pela bomba",
                    f"NPSH disp. = (p_abs − p_v)/(ρ·g) = {_N(npsh, 1)} m ≥ {_N(e.npsh_requerido_m, 1)} m",
                    status="NÃO OK" if npsh < e.npsh_requerido_m else "OK",
                    tipo="limite",
                )
            )
        if e.tipo == ci.FONTE and e.id in regime.saidas:
            t = regime.saidas[e.id]
            pico = t
            if tempo is not None:
                pico = max(t, float(np.max(tempo.saidas[e.id])))
            linhas.append(
                Verificacao(
                    f"Temperatura na saída da {e.nome}",
                    pico,
                    e.t_maxima,
                    "°C",
                    "A maior temperatura do fluido na saída, em regime e na partida",
                    f"regime {_N(t, 1)} °C; pico {_N(pico, 1)} °C ≤ {_N(e.t_maxima, 1)} °C",
                    tipo="limite",
                )
            )
        if e.tipo == ci.CHILLER and e.id in regime.saidas and e.nome in regime.chiller_no_limite:
            linhas.append(
                Verificacao(
                    f"Capacidade do {e.nome}",
                    None,
                    None,
                    "",
                    "O chiller segura a temperatura ajustada",
                    f"na capacidade máxima, a saída fica em {_N(regime.saidas[e.id], 1)} °C, acima do ajuste",
                    status="ALERTA",
                    tipo="limite",
                )
            )
        if e.tipo == ci.DRY_COOLER and e.controle != ci.SEMPRE and e.id in regime.saidas:
            if (
                regime.rotacoes.get(e.id, 1.0) >= 1.0 - 1e-9
                and regime.saidas[e.id] > e.t_ajuste + 0.05
            ):
                linhas.append(
                    Verificacao(
                        f"Ajuste do {e.nome}",
                        None,
                        None,
                        "",
                        "O dry cooler segura a temperatura ajustada",
                        f"com o ventilador em 100 % a saída fica em {_N(regime.saidas[e.id], 1)} °C, acima de {_N(e.t_ajuste, 1)} °C",
                        status="ALERTA",
                        tipo="limite",
                    )
                )
    _ = prop
    return linhas


def calcular(
    c: ci.Circuito, cond: cte.Condicoes, duracao: float | None = None, *, no_tempo: bool = True
) -> Resultado:
    h = ci.resolver_hidraulica(c, cond.t_ar + 5.0)
    regime = cte.regime_permanente(c, h, cond.t_ar)
    tempo = cte.simular(c, h, cond, duracao) if no_tempo else None
    return Resultado(c, h, regime, tempo, cond, tuple(verificacoes(c, h, regime, tempo, cond)))


# ---------------------------------------------------------------------------------------------
# Marcas na prancheta
# ---------------------------------------------------------------------------------------------
def _cor_da_temperatura(t: float, lo: float, hi: float) -> str:
    r, g, b = fnt.cor_do_calor((t - lo) / (hi - lo) if hi > lo else 0.5)
    return f"rgb({r},{g},{b})"


def marcas_para_o_desenho(r: Resultado) -> dict[str, Any]:
    h, regime = r.hidraulica, r.regime
    ruins = {v.nome for v in r.verificacoes if v.status == "NÃO OK"}
    temps = list(regime.saidas.values()) + list(regime.entradas.values())
    lo, hi = (min(temps), max(temps)) if temps else (0.0, 1.0)
    marcas: dict[str, Any] = {"nos": {}, "trechos": {}}
    for e in r.circuito.elementos:
        q = h.vazoes[e.id]
        # textos curtos: o detalhe está no painel ao lado e nas tabelas
        if e.tipo in (ci.FONTE, ci.DRY_COOLER, ci.CHILLER) and e.id in regime.saidas:
            partes = [f"{_N(abs(regime.calores[e.id]) / 1000.0, 1)} kW", f"sai {_N(regime.saidas[e.id], 1)} °C"]
        else:
            partes = [f"{_N(abs(q) * 3600.0, 1)} m³/h"]
        ruim = any(e.nome in nome for nome in ruins)
        marcas["trechos"][e.id] = {
            "texto": " · ".join(partes),
            "sentido": -1 if q < 0 else 1,
            "ruim": ruim,
            "cor": _cor_da_temperatura(regime.saidas[e.id], lo, hi)
            if e.id in regime.saidas
            else None,
        }
    for n in r.circuito.nos:
        if n.id not in h.pressoes:
            continue
        t = regime.temperaturas.get(n.id)
        texto = f"{_N(h.pressao_bar(n.id), 2)} bar"
        _ = t
        marcas["nos"][n.id] = {"texto": texto, "ruim": f"Pressão mínima no ponto {n.nome}" in ruins}
    return marcas


# ---------------------------------------------------------------------------------------------
# Cena do tocador
# ---------------------------------------------------------------------------------------------
def _retangulo_girado(
    cx: float, cy: float, ux: float, uy: float, comprimento: float, largura: float
) -> list[tuple[float, float]]:
    nx, ny = -uy, ux
    a, b = comprimento / 2.0, largura / 2.0
    return [(cx - ux * a - nx * b, cy - uy * a - ny * b), (cx + ux * a - nx * b, cy + uy * a - ny * b),
            (cx + ux * a + nx * b, cy + uy * a + ny * b), (cx - ux * a + nx * b, cy - uy * a + ny * b)]  # fmt: skip


def cena_do_circuito(r: Resultado) -> dict[str, Any]:
    c, h, t = r.circuito, r.hidraulica, r.tempo
    assert t is not None
    pos = {n.id: (n.x, n.y) for n in c.nos}
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    extensao = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    cena = Cena(
        t.tempos, id=f"circuito-{hash((c, r.condicoes, t.duracao)) & 0xFFFFFFFF:x}", altura=460
    )
    lo, hi = float(np.min(t.quadros)), float(np.max(t.quadros))
    esc = cena.escala("Temperatura", "°C", lo, hi, cores=CALOR, casas=1)
    canais = cena.canais(t.quadros)
    v_max = (
        max(
            (abs(q) / e.area for e in c.elementos for q in [h.vazoes[e.id]] if e.tipo == ci.TUBO),
            default=1.0,
        )
        or 1.0
    )
    tamanho_peca = 0.06 * extensao
    for k, e in enumerate(c.elementos):
        a, b = pos[e.de], pos[e.para]
        dx, dy = b[0] - a[0], b[1] - a[1]
        lado = math.hypot(dx, dy) or 1e-9
        ux, uy = dx / lado, dy / lado
        celulas = [i for i, el in enumerate(t.celulas.elemento) if el == k]
        if e.tipo == ci.TUBO:
            for i in celulas:
                f = float(t.celulas.posicao[i])
                n_cel = len(celulas)
                f0, f1 = max(0.0, f - 0.5 / n_cel - 0.002), min(1.0, f + 0.5 / n_cel + 0.002)
                cena.linha(
                    [(a[0] + dx * f0, a[1] + dy * f0), (a[0] + dx * f1, a[1] + dy * f1)],
                    largura=9,
                    escala=esc,
                    canal=canais[i],
                    nome=f"Tubo {e.nome}",
                    ponta="butt",
                )
            q = h.vazoes[e.id]
            if abs(q) > 1e-9:
                canal_v = cena.canal(np.full(len(t.tempos), q / e.area))
                cena.linha(
                    [a, b],
                    largura=0.1,
                    cor="#ffffff",
                    setas=True,
                    fluxo=canal_v,
                    fluxo_ref=v_max,
                    espaco_setas=60,
                    cor_setas="#ffffff",
                    contorno_setas="#0d366b",
                )
        else:
            cena.linha([a, b], largura=4, cor="#475569", ponta="butt")
            cx, cy = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
            canal = canais[celulas[0]] if celulas else None
            if e.tipo == ci.BOMBA:
                cena.circulo(
                    cx,
                    cy,
                    raio_px=13,
                    escala=esc,
                    canal=canal,
                    contorno="texto",
                    espessura=2.0,
                    nome=e.nome,
                )
                sentido = 1.0 if h.vazoes[e.id] >= 0 else -1.0
                s = 0.45 * tamanho_peca
                cena.poligono([(cx - ux * s * 0.5 - uy * s * 0.5, cy - uy * s * 0.5 + ux * s * 0.5), (cx + ux * s * 0.7, cy + uy * s * 0.7),
                               (cx - ux * s * 0.5 + uy * s * 0.5, cy - uy * s * 0.5 - ux * s * 0.5)] if sentido > 0 else
                              [(cx + ux * s * 0.5 - uy * s * 0.5, cy + uy * s * 0.5 + ux * s * 0.5), (cx - ux * s * 0.7, cy - uy * s * 0.7),
                               (cx + ux * s * 0.5 + uy * s * 0.5, cy + uy * s * 0.5 - ux * s * 0.5)], cor="#1e293b")  # fmt: skip
            else:
                forma = _retangulo_girado(cx, cy, ux, uy, 1.6 * tamanho_peca, 0.95 * tamanho_peca)
                if canal is not None:
                    cena.poligono(
                        forma, escala=esc, canal=canal, contorno="texto", espessura=1.8, nome=e.nome
                    )
                else:
                    cena.poligono(
                        forma,
                        cor=_COR_DOS_SIMBOLOS.get(e.tipo, "#ffffff"),
                        contorno="texto",
                        espessura=1.8,
                    )
            nx, ny = -uy, ux
            if ny < 0 or (abs(ny) < 1e-9 and nx < 0):
                nx, ny = -nx, -ny
            texto_x, texto_y = cx + nx * 0.9 * tamanho_peca, cy + ny * 0.9 * tamanho_peca
            cena.texto(texto_x, texto_y, e.nome, tamanho=11, negrito=True, base="bottom")
            if e.id in t.calores:
                cena.texto(
                    texto_x,
                    texto_y,
                    "{} kW",
                    canal=cena.canal(t.calores[e.id] / 1000.0),
                    casas=1,
                    tamanho=11,
                    modulo=True,
                    base="top",
                    dy=2,
                )
            if e.id in t.rotacoes and e.controle != ci.SEMPRE:
                cena.texto(
                    texto_x,
                    texto_y,
                    "ventilador {} %",
                    canal=cena.canal(t.rotacoes[e.id] * 100.0),
                    casas=0,
                    tamanho=10,
                    base="top",
                    dy=16,
                )
    for j, n in enumerate(c.nos):
        x, y = pos[n.id]
        if n.id in t.nos:
            k = t.nos.index(n.id)
            cena.circulo(
                x,
                y,
                raio_px=4,
                escala=esc,
                canal=cena.canal(t.temperaturas_dos_nos[:, k]),
                contorno="texto",
                espessura=1.0,
                nome=f"Ponto {n.nome}",
            )
        if n.vaso is not None:
            s = 0.05 * extensao
            cena.linha([(x, y), (x, y + 0.6 * s)], largura=2, cor="#1e293b")
            cena.retangulo(
                x - 0.4 * s,
                y + 0.6 * s,
                x + 0.4 * s,
                y + 1.8 * s,
                cor="#fef3c7",
                contorno="texto",
                espessura=1.5,
            )
            if t.vaso:
                k_p = cena.canal(np.array([s_.pressao_bar for s_ in t.vaso]))
                cena.texto(
                    x + 0.55 * s,
                    y + 1.2 * s,
                    "vaso {} bar",
                    canal=k_p,
                    casas=2,
                    ancora="start",
                    tamanho=11,
                    negrito=True,
                )
        _ = j
    folga = 0.14 * extensao
    cena.vista = (min(xs) - folga, min(ys) - folga, max(xs) + folga, max(ys) + folga)
    # gráficos
    u = unidade_de_tempo(t.duracao)
    _ = u
    fontes = [e for e in c.elementos if e.tipo == ci.FONTE]
    series = [(f"Saída da {e.nome}", cena.canal(t.saidas[e.id])) for e in fontes][:5]
    for e in c.elementos:
        if e.tipo in (ci.DRY_COOLER, ci.CHILLER) and len(series) < 7:
            series.append((f"Saída do {e.nome}", cena.canal(t.saidas[e.id])))
    limites = [(f"máx. {e.nome}", e.t_maxima) for e in fontes][:2]
    cena.grafico_no_tempo(
        "Temperaturas do circuito",
        "°C",
        series,
        limites=limites,
        marcos=[("estabiliza", t.estabiliza)],
    )
    calores = [
        (e.nome, cena.canal(t.calores[e.id] / 1000.0)) for e in c.elementos if e.id in t.calores
    ][:7]
    cena.grafico_no_tempo(
        "Calor (positivo: entra no fluido)",
        "kW",
        calores,
        casas=1,
        marcos=[("estabiliza", t.estabiliza)],
    )
    if t.vaso:
        vaso = c.vaso
        assert vaso is not None and vaso.vaso is not None
        cena.grafico_no_tempo(
            "Pressão no vaso de expansão",
            "bar",
            [("Vaso", cena.canal(np.array([s.pressao_bar for s in t.vaso])))],
            casas=2,
            limites=[("máxima", vaso.vaso.maxima_bar)],
        )
    rotacoes = [
        (e.nome, cena.canal(t.rotacoes[e.id] * 100.0))
        for e in c.elementos
        if e.id in t.rotacoes and e.controle != ci.SEMPRE
    ]
    if rotacoes:
        cena.grafico_no_tempo(
            "Rotação dos ventiladores", "%", rotacoes, casas=0, faixa=(0.0, 105.0)
        )
    cena.nota = (
        "O tubo tem a cor da temperatura do fluido; as setas brancas andam no sentido da água. "
        "Passe o mouse nas peças e nos tubos para ler a temperatura."
    )
    return cena.como_dados()


# ---------------------------------------------------------------------------------------------
# Tabelas e registro
# ---------------------------------------------------------------------------------------------
COLUNAS_ELEMENTOS = (
    "Elemento",
    "Tipo",
    "Vazão (m³/h)",
    "Velocidade (m/s)",
    "Entrada (°C)",
    "Saída (°C)",
    "Calor (kW)",
    "Perda (kPa)",
)
COLUNAS_PONTOS = ("Ponto", "Cota (m)", "Pressão (bar)", "Temperatura (°C)")


def linhas_dos_elementos(r: Resultado) -> list[list[str]]:
    c, h, regime = r.circuito, r.hidraulica, r.regime
    p = ci.propriedades(c.fluido, r.condicoes.t_ar + 5.0)
    linhas = []
    for e in c.elementos:
        q = h.vazoes[e.id]
        perda = ci.perda(e, q, p)[0] * p.massa_especifica * ci.GRAVIDADE / 1000.0
        linhas.append(
            [
                e.nome,
                ci.NOMES.get(e.tipo, e.tipo),
                _N(abs(q) * 3600.0, 2),
                _N(abs(q) / e.area, 2),
                "—" if e.id not in regime.entradas else _N(regime.entradas[e.id], 1),
                "—" if e.id not in regime.saidas else _N(regime.saidas[e.id], 1),
                "—"
                if e.id not in regime.calores or abs(regime.calores[e.id]) < 1
                else _N(regime.calores[e.id] / 1000.0, 2),
                _N(abs(perda), 1) if e.tipo != ci.BOMBA else "—",
            ]
        )
    return linhas


def linhas_dos_pontos(r: Resultado) -> list[list[str]]:
    linhas = []
    for n in r.circuito.nos:
        if n.id not in r.hidraulica.pressoes:
            continue
        t = r.regime.temperaturas.get(n.id)
        linhas.append(
            [
                n.nome + (" (vaso)" if n.vaso else ""),
                _N(n.cota, 2),
                _N(r.hidraulica.pressao_bar(n.id), 2),
                "—" if t is None else _N(t, 1),
            ]
        )
    return linhas


def registro(r: Resultado) -> dict[str, Any]:
    c, t = r.circuito, r.tempo
    fontes = sum(e.potencia_kW for e in c.elementos if e.tipo == ci.FONTE)
    piores = [e for e in c.elementos if e.tipo == ci.FONTE and e.id in r.regime.saidas]
    destaque = (
        f"Circuito fechado com {c.fluido.lower()}, {_N(c.volume_m3 * 1000.0, 0)} L, {len(c.elementos)} elementos e "
        f"{_N(fontes, 1)} kW nas fontes, com o ar a {_N(r.condicoes.t_ar, 1)} °C."
    )
    if piores:
        quente = max(piores, key=lambda e: r.regime.saidas[e.id])
        destaque += f" Em regime, a saída mais quente é a da {quente.nome}, a {_N(r.regime.saidas[quente.id], 1)} °C."
    figuras: list[dict[str, Any]] = []
    if t is not None:
        u = unidade_de_tempo(t.duracao)
        x = tuple(t.tempos / u.fator)
        if t.estabiliza is not None:
            destaque += f" Da partida a frio, estabiliza em {tempo_em_texto(t.estabiliza, u)}."
        series = [
            fnt.Serie(f"Saída da {e.nome}", x, tuple(t.saidas[e.id]))
            for e in c.elementos
            if e.tipo == ci.FONTE
        ][:5]
        series += [
            fnt.Serie(f"Saída do {e.nome}", x, tuple(t.saidas[e.id]))
            for e in c.elementos
            if e.tipo in (ci.DRY_COOLER, ci.CHILLER)
        ][:2]
        figuras.append(
            fnt.linhas_para_o_registro(
                "Temperaturas do circuito",
                "Temperatura do fluido na saída das peças, da partida a frio.",
                f"tempo ({u.rotulo})",
                "°C",
                series,
                [(f"máx. {e.nome}", e.t_maxima) for e in c.elementos if e.tipo == ci.FONTE][:2],
                [("estabiliza", None if t.estabiliza is None else t.estabiliza / u.fator)],
            )  # fmt: skip
        )
        if t.vaso:
            figuras.append(
                fnt.linhas_para_o_registro(
                    "Pressão no vaso de expansão",
                    "Pressão manométrica no vaso com a dilatação do fluido.",
                    f"tempo ({u.rotulo})",
                    "bar",
                    [fnt.Serie("Vaso", x, tuple(s.pressao_bar for s in t.vaso))],
                )  # fmt: skip
            )
    geral = r.status
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=f"Circuito fechado — {len(c.elementos)} elementos",
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=destaque,
        entradas={
            "fluido": c.fluido,
            "volume_L": numero_json(c.volume_m3 * 1000.0, 2),
            "temperatura_do_ar_C": numero_json(r.condicoes.t_ar, 3),
            "temperatura_inicial_C": numero_json(r.condicoes.t_inicial, 3),
            "elementos": [
                {"nome": e.nome, "tipo": e.tipo, "de": c.no(e.de).nome, "para": c.no(e.para).nome}
                for e in c.elementos
            ],
        },
        resultados={
            "status_geral": geral,
            "destaque_memorial": destaque,
            "verificações": linhas_para_registro(list(r.verificacoes)),
            "tabelas_memorial": [
                {
                    "legenda": "Elementos do circuito: vazão, temperaturas, calor e perda de carga.",
                    "cabecalhos": list(COLUNAS_ELEMENTOS),
                    "linhas": linhas_dos_elementos(r),
                    "fonte": 7.0,
                },
                {
                    "legenda": "Pontos do circuito: pressão e temperatura.",
                    "cabecalhos": list(COLUNAS_PONTOS),
                    "linhas": linhas_dos_pontos(r),
                    "fonte": 8.0,
                },
            ],
            fnt.CHAVE: figuras,
        },
        metodo=(
            "Hidráulica: energia em cada elemento e continuidade em cada ponto, por Newton (como o "
            "EPANET), com a pressão fixa no vaso de expansão. Térmica: cada elemento leva a "
            "temperatura da entrada à da saída (dry cooler pelo ε-NTU de fluxo cruzado com o UA do "
            "catálogo; chiller até a capacidade), com mistura nos pontos; no tempo, o fluido "
            "atravessa células nos tubos e volumes bem misturados nas peças."
        ),
        premissas=premissas(r),
        referencias=_REFERENCIAS,
        conclusao=destaque,
    )


def premissas(r: Resultado) -> list[str]:
    return [
        "Fluido incompressível na hidráulica, com as propriedades da CoolProp numa temperatura "
        "média; a vazão estabiliza em segundos e, na conta térmica, já está estabilizada.",
        "Perda das peças pelo catálogo (Δp ∝ Q²); bomba pela curva de dois pontos (H₀ e Q_máx).",
        "Dry cooler: UA tirado do ponto do catálogo; com o ventilador mais lento, C_ar ∝ rotação e "
        "UA ∝ rotação^0,6 (lado do ar governa). Ventilador parado: o dry cooler não troca.",
        "Controle ideal: o ventilador proporcional e o chiller acham na hora o que segura a "
        "temperatura ajustada; o liga e desliga tem 1 K de histerese para cada lado.",
        "Peças e tanque bem misturados; a massa da fonte de calor esquenta junto com o fluido.",
        "Vaso de expansão com o ar a temperatura constante (p·V constante); a dilatação dos tubos "
        "fica de fora, a favor da segurança. A pressão de vapor é a da água.",
    ]
