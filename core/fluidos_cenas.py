"""Cenas, figuras e registro de tanques e linhas no tempo (página Tanques e linhas no tempo).

As contas estão em :mod:`core.tanque_no_tempo` e :mod:`core.linha_no_tempo`; aqui viram a cena do
tocador (:mod:`core.animacao`), as figuras do memorial (:mod:`core.figuras_no_tempo`) e o registro.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np

from core import figuras_no_tempo as fnt
from core import linha_no_tempo as ln
from core import tanque_no_tempo as tq
from core.animacao import (
    AGUA,
    CALOR,
    Cena,
    tempo_em_texto,
    tempos_dos_quadros,
    unidade_de_tempo,
)
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    linhas_para_registro,
    numero_json,
    status_geral,
)

MODULO_ID = "tanques_e_linhas"
MODULO_TITULO = "Tanques e linhas no tempo"
_AGUA = "#3987e5"
_N = tq._n
_REF_FLUIDOS = (
    "Çengel, Y. A.; Cimbala, J. M. Mecânica dos Fluidos: Fundamentos e Aplicações. McGraw-Hill "
    "(cap. 5: energia e Torricelli; cap. 8: escoamento em tubos)."
)
_REF_TRANSIENTE = "Wylie, E. B.; Streeter, V. L. Fluid Transients in Systems. Prentice Hall, 1993 (cap. 2: coluna rígida)."
_REF_CALOR = (
    "Incropera, F. P. et al. Fundamentos de Transferência de Calor e de Massa, 6ª ed. LTC, 2008 "
    "(cap. 3 e 8)."
)


_TUBO = "#256abf"  # tubo cheio de água
_PAREDE = "#334155"  # paredes e símbolos
_JATO = "#6da7ec"
_COR_SETAS = "#ffffff"
_CONTORNO_SETAS = "#0d366b"
_COR_CALOR = "#de5524"
NOTA_FLUIDOS = "Setas brancas: o sentido da água, andando com ela (mais rápidas, mais vazão)."


def _passo_da_regua(altura: float) -> float:
    for passo in (0.1, 0.2, 0.25, 0.5, 1.0, 2.0, 2.5, 5.0, 10.0, 20.0, 50.0):
        if altura / passo <= 6:
            return passo
    return 100.0


def _regua(cena: Cena, x: float, altura: float, escala: float) -> None:
    """Régua de nível ao lado do tanque, do fundo ao topo."""
    passo = _passo_da_regua(altura)
    valor = 0.0
    while valor <= altura + 1e-9:
        cena.linha([(x - 0.035 * escala, valor), (x, valor)], largura=1.2, cor=_PAREDE)
        cena.texto(
            x - 0.05 * escala,
            valor,
            f"{_N(valor, 2 if passo < 1 else 1)} m",
            ancora="end",
            tamanho=10,
        )
        valor += passo


def _bomba(cena: Cena, x: float, y: float, tamanho: float, *, sentido: int = 1) -> None:
    """Símbolo de bomba: círculo com o triângulo apontando o sentido do escoamento."""
    cena.circulo(x, y, raio_px=14, cor="#ffffff", contorno=_PAREDE, espessura=2.0, nome="Bomba")
    s = sentido * tamanho
    cena.poligono(
        [(x - 0.45 * s, y - 0.5 * tamanho), (x + 0.6 * s, y), (x - 0.45 * s, y + 0.5 * tamanho)],
        cor=_PAREDE,
    )


def _valvula(cena: Cena, x: float, y: float, tamanho: float) -> None:
    """Símbolo de válvula: dois triângulos ponta com ponta."""
    m = tamanho
    cena.poligono(
        [(x - m, y - 0.6 * m), (x, y), (x - m, y + 0.6 * m)],
        cor="#ffffff",
        contorno=_PAREDE,
        espessura=1.8,
    )
    cena.poligono(
        [(x + m, y - 0.6 * m), (x, y), (x + m, y + 0.6 * m)],
        cor="#ffffff",
        contorno=_PAREDE,
        espessura=1.8,
    )
    cena.linha([(x, y), (x, y + 1.3 * m)], largura=2, cor=_PAREDE)
    cena.linha([(x - 0.6 * m, y + 1.3 * m), (x + 0.6 * m, y + 1.3 * m)], largura=2.5, cor=_PAREDE)


def _id(*partes: Any) -> str:
    return f"{partes[0]}-{hash(tuple(repr(p) for p in partes)) & 0xFFFFFFFF:x}"


def _serie_no_tempo(nome: str, tempos: np.ndarray, valores: np.ndarray, u: Any) -> fnt.Serie:
    amostra = np.linspace(0.0, float(tempos[-1]), 121)
    return fnt.Serie(nome, tuple(amostra / u.fator), tuple(np.interp(amostra, tempos, valores)))


def _registro(
    titulo: str,
    destaque: str,
    entradas: dict[str, Any],
    tabela: dict[str, Any],
    figuras: list[dict[str, Any]],
    metodo: str,
    premissas: Sequence[str],
    referencias: Sequence[str],
    verificacoes: Sequence[Verificacao] = (),
    responsavel: str = "",
) -> dict[str, Any]:
    geral = status_geral(list(verificacoes)) if verificacoes else "OK"
    resultados: dict[str, Any] = {
        "status_geral": geral,
        "destaque_memorial": destaque,
        "tabelas_memorial": [tabela],
        fnt.CHAVE: figuras,
    }
    if verificacoes:
        resultados["verificações"] = linhas_para_registro(list(verificacoes))
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=titulo,
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=destaque,
        entradas=entradas,
        resultados=resultados,
        metodo=metodo,
        premissas=list(premissas),
        referencias=list(referencias),
        conclusao=destaque,
        responsavel=responsavel,
    )


def _tabela(
    legenda: str,
    cabecalhos: list[str],
    tempos: np.ndarray,
    colunas: Sequence[tuple[np.ndarray, int]],
) -> dict[str, Any]:
    u = unidade_de_tempo(float(tempos[-1]))
    linhas = []
    for i in np.linspace(0, len(tempos) - 1, 11).round().astype(int):
        linhas.append(
            [tempo_em_texto(float(tempos[i]), u), *[_N(float(v[i]), casas) for v, casas in colunas]]
        )
    return {"legenda": legenda, "cabecalhos": cabecalhos, "linhas": linhas, "fonte": 8.0}


# =============================================================================================
# Tanque: nível
# =============================================================================================
def _caixa_do_tanque(t: tq.Tanque) -> tuple[float, float]:
    """Largura e altura do tanque visto de lado (m)."""
    if t.forma == tq.VERTICAL:
        return t.diametro_m, t.altura_m
    if t.forma == tq.RETANGULAR:
        return t.comprimento_m, t.altura_m
    return t.comprimento_m, t.diametro_m


_EVENTOS_DO_NIVEL = {"vazio": "esvazia", "cheio": "transborda", "estavel": "estabiliza"}


def _desenhar_tanque(
    cena: Cena,
    t: tq.Tanque,
    x0: float,
    y0: float,
    k_nivel: int,
    escala: float,
    *,
    regua: bool = True,
) -> tuple[float, float]:
    largura, altura = _caixa_do_tanque(t)
    cena.nivel((x0, y0, x0 + largura, y0 + altura), k_nivel, cor=_AGUA)
    if t.forma == tq.HORIZONTAL:
        cena.retangulo(
            x0, y0, x0 + largura, y0 + altura, vazio=True, contorno=_PAREDE, espessura=3.0
        )
    else:
        borda = y0 + altura * 1.06
        cena.linha(
            [(x0, borda), (x0, y0), (x0 + largura, y0), (x0 + largura, borda)],
            largura=4,
            cor=_PAREDE,
            ponta="butt",
        )
    if regua:
        _regua(cena, x0, altura, escala)
    return largura, altura


def cena_do_nivel(r: tq.ResultadoDoNivel, alvo: float | None = None) -> dict[str, Any]:
    t = r.tanque
    tempos = tempos_dos_quadros(r.duracao)
    niveis = np.interp(tempos, r.tempos, r.niveis)
    saida = np.interp(tempos, r.tempos, r.saida)
    cena = Cena(tempos, id=_id("nivel", t, r.duracao), altura=400)
    largura, altura = _caixa_do_tanque(t)
    escala = max(largura, altura)
    k_nivel = cena.canal(niveis)
    k_saida = cena.canal(saida)
    k_entrada = cena.canal(np.full(len(tempos), t.entrada_L_s))
    referencia = max(float(np.max(saida, initial=0.0)), t.entrada_L_s, 1e-9)
    if t.entrada_L_s > 0:
        x = 0.3 * largura
        # o jato vai até o fundo, atrás da água: só aparece a parte acima da superfície
        cena.linha([(x, altura * 1.03), (x, 0.0)], largura=5, cor=_JATO)
    _desenhar_tanque(cena, t, 0.0, 0.0, k_nivel, escala)
    if t.entrada_L_s > 0:
        x = 0.3 * largura
        y = altura + 0.22 * escala
        cena.linha(
            [(x - 0.5 * escala, y), (x, y), (x, altura * 1.03)],
            largura=9,
            cor=_TUBO,
            setas=True,
            fluxo=k_entrada,
            fluxo_ref=referencia,
            espaco_setas=60,
            cor_setas=_COR_SETAS,
            contorno_setas=_CONTORNO_SETAS,
        )
        cena.texto(x - 0.52 * escala, y, "entra {} L/s", canal=k_entrada, casas=2, ancora="end")
    s = t.saida
    if s.tipo != tq.SEM_SAIDA:
        xs = 0.82 * largura
        nome = {
            tq.ORIFICIO: f"orifício Ø {_N(s.diametro_mm, 0)} mm",
            tq.TUBO: f"tubo Ø {_N(s.diametro_mm, 0)} mm",
            tq.BOMBA: "bomba",
        }[s.tipo]
        if s.tipo == tq.ORIFICIO:
            cena.linha([(xs, 0.0), (xs, -0.07 * escala)], largura=7, cor=_PAREDE, ponta="butt")
            cena.linha(
                [(xs, -0.07 * escala), (xs, -0.45 * escala)],
                largura=5,
                cor=_JATO,
                setas=True,
                fluxo=k_saida,
                fluxo_ref=referencia,
                espaco_setas=45,
                visivel=k_saida,
                cor_setas=_COR_SETAS,
                contorno_setas=_CONTORNO_SETAS,
            )
            cena.texto(
                xs + 0.06 * escala,
                -0.2 * escala,
                f"{nome}: sai {{}} L/s",
                canal=k_saida,
                casas=2,
                ancora="start",
            )
        else:
            queda = 0.0 if s.tipo != tq.TUBO else min(max(s.desnivel_m, 0.0), 0.7 * escala)
            pontos = [(xs, 0.0), (xs, -0.1 * escala), (largura + 0.45 * escala, -0.1 * escala)]
            if queda > 0:
                pontos.append((largura + 0.45 * escala, -0.1 * escala - queda))
            cena.linha(
                pontos,
                largura=9,
                cor=_TUBO,
                setas=True,
                fluxo=k_saida,
                fluxo_ref=referencia,
                espaco_setas=60,
                cor_setas=_COR_SETAS,
                contorno_setas=_CONTORNO_SETAS,
            )
            if s.tipo == tq.BOMBA:
                _bomba(cena, largura + 0.2 * escala, -0.1 * escala, 0.05 * escala)
            ponta = pontos[-1]
            cena.linha(
                [ponta, (ponta[0], ponta[1] - 0.2 * escala)], largura=4, cor=_JATO, visivel=k_saida
            )
            cena.texto(
                largura + 0.5 * escala,
                -0.1 * escala,
                f"{nome}: sai {{}} L/s",
                canal=k_saida,
                casas=2,
                ancora="start",
            )
            if queda > 0:
                cena.cota(
                    (largura + 0.45 * escala, -0.1 * escala),
                    (largura + 0.45 * escala, -0.1 * escala - queda),
                    f"{_N(s.desnivel_m, 2)} m",
                    desloc=-18,
                )
    # o nível escrito acima do tanque: dentro dele o texto bateria na superfície da água
    cena.texto(
        largura * 0.5,
        altura * 1.06 + (0.3 * escala if t.entrada_L_s > 0 else 0.0),
        "nível h = {} m",
        canal=k_nivel,
        casas=3,
        negrito=True,
        tamanho=13,
        base="bottom",
        dy=-4,
    )
    if r.nivel_de_equilibrio is not None and 0 < r.nivel_de_equilibrio < altura:
        cena.linha(
            [(0, r.nivel_de_equilibrio), (largura, r.nivel_de_equilibrio)],
            largura=1.5,
            cor="#0d366b",
            tracejado=True,
        )
        cena.texto(
            largura + 0.03 * escala,
            r.nivel_de_equilibrio,
            f"equilíbrio {_N(r.nivel_de_equilibrio, 3)} m",
            ancora="start",
            tamanho=10,
        )
    if alvo is not None and 0 < alvo < altura:
        cena.linha([(0, alvo), (largura, alvo)], largura=1.5, cor="#475569", tracejado=True)
        cena.texto(
            largura + 0.03 * escala, alvo, f"alvo {_N(alvo, 2)} m", ancora="start", tamanho=10
        )
    baixo = -0.52 * escala - (
        0.0 if s.tipo != tq.TUBO else min(max(s.desnivel_m, 0.0), 0.7 * escala)
    )
    topo = altura * 1.06 + (0.3 * escala if t.entrada_L_s > 0 else 0.0) + 0.12 * escala
    direita = largura + (1.25 if s.tipo != tq.SEM_SAIDA else 0.35) * escala
    esquerda = -(0.75 if t.entrada_L_s > 0 else 0.4) * escala
    cena.vista = (esquerda, baixo, direita, topo)
    limites = [("topo do tanque", altura)]
    if alvo is not None:
        limites.append(("alvo", alvo))
    marcos = [(_EVENTOS_DO_NIVEL.get(r.evento, ""), r.duracao if r.evento else None)]
    if alvo is not None:
        marcos.append(("chega ao alvo", r.tempo_para(alvo)))
    cena.grafico_no_tempo(
        "Nível no tanque", "m", [("Nível", k_nivel)], casas=3, limites=limites, marcos=marcos
    )
    cena.grafico_no_tempo(
        "Vazões", "L/s", [("Entrada", k_entrada), ("Saída", k_saida)], casas=2, marcos=marcos[:1]
    )
    cena.nota = NOTA_FLUIDOS
    return cena.como_dados()


def cena_dos_vasos(r: tq.ResultadoDosVasos) -> dict[str, Any]:
    v = r.vasos
    tempos = tempos_dos_quadros(r.duracao)
    h1 = np.interp(tempos, r.tempos, r.niveis_1)
    h2 = np.interp(tempos, r.tempos, r.niveis_2)
    q = np.interp(tempos, r.tempos, r.vazao)
    cena = Cena(tempos, id=_id("vasos", v, r.duracao), altura=380)
    l1, a1 = _caixa_do_tanque(v.tanque_1)
    l2, a2 = _caixa_do_tanque(v.tanque_2)
    escala = max(l1 + l2, a1, a2 + abs(v.cota_fundo_2))
    vao = 0.45 * escala
    x2 = l1 + vao
    z2 = v.cota_fundo_2
    k1, k2, kq = cena.canal(h1), cena.canal(h2), cena.canal(q)
    k_d = cena.canal(h1 - (z2 + h2))
    _desenhar_tanque(cena, v.tanque_1, 0.0, 0.0, k1, escala)
    _desenhar_tanque(cena, v.tanque_2, x2, z2, k2, escala, regua=False)
    baixo = min(0.0, z2) - 0.12 * escala
    pontos = [(0.8 * l1, 0.0), (0.8 * l1, baixo), (x2 + 0.2 * l2, baixo), (x2 + 0.2 * l2, z2)]
    referencia = max(float(np.max(np.abs(q))), 1e-9)
    cena.linha(
        pontos,
        largura=9,
        cor=_TUBO,
        setas=True,
        fluxo=kq,
        fluxo_ref=referencia,
        espaco_setas=55,
        cor_setas=_COR_SETAS,
        contorno_setas=_CONTORNO_SETAS,
    )
    cena.texto(
        (0.8 * l1 + x2 + 0.2 * l2) / 2,
        baixo,
        "{} L/s",
        canal=kq,
        casas=2,
        modulo=True,
        dy=-16,
        negrito=True,
    )
    cena.texto(0.5 * l1, 0.5 * a1, "h₁ = {} m", canal=k1, casas=3, negrito=True)
    cena.texto(x2 + 0.5 * l2, z2 + 0.5 * a2, "h₂ = {} m", canal=k2, casas=3, negrito=True)
    cena.texto(
        0.5 * (l1 + x2),
        max(a1, z2 + a2) + 0.18 * escala,
        "diferença entre as superfícies: {} m",
        canal=k_d,
        casas=3,
        modulo=True,
    )
    if r.superficie_de_equilibrio is not None:
        z = r.superficie_de_equilibrio
        cena.linha([(0, z), (x2 + l2, z)], largura=1.5, cor="#0d366b", tracejado=True)
        cena.texto(
            x2 + l2 + 0.03 * escala, z, f"nível igual: {_N(z, 3)} m", ancora="start", tamanho=10
        )
    cena.texto(0.5 * l1, a1 * 1.07, "tanque 1", base="bottom", tamanho=11)
    cena.texto(x2 + 0.5 * l2, z2 + a2 * 1.07, "tanque 2", base="bottom", tamanho=11)
    cena.vista = (
        -0.75 * escala,
        baixo - 0.25 * escala,
        x2 + l2 + 0.95 * escala,
        max(a1, z2 + a2) + 0.32 * escala,
    )
    nome = {
        "equalizou": "equaliza",
        "vazio_1": "tanque 1 esvazia",
        "vazio_2": "tanque 2 esvazia",
        "cheio_1": "tanque 1 transborda",
        "cheio_2": "tanque 2 transborda",
    }
    marcos = [(nome.get(r.evento, ""), r.duracao if r.evento else None)]
    superficies = [("Tanque 1", k1), ("Tanque 2", cena.canal(z2 + h2))]
    limites = (
        [("nível igual", r.superficie_de_equilibrio)]
        if r.superficie_de_equilibrio is not None
        else []
    )
    cena.grafico_no_tempo(
        "Superfície da água (do fundo do tanque 1)",
        "m",
        superficies,
        casas=3,
        limites=limites,
        marcos=marcos,
    )
    cena.grafico_no_tempo(
        "Vazão do tanque 1 para o 2", "L/s", [("Vazão", kq)], casas=2, marcos=marcos
    )
    cena.nota = NOTA_FLUIDOS + " Vazão negativa: a água volta do tanque 2 para o 1."
    return cena.como_dados()


def registro_do_nivel(r: tq.ResultadoDoNivel, alvo: float | None = None) -> dict[str, Any]:
    t = r.tanque
    u = unidade_de_tempo(r.duracao)
    forma = {
        tq.VERTICAL: "cilíndrico vertical",
        tq.RETANGULAR: "retangular",
        tq.HORIZONTAL: "cilíndrico horizontal",
    }[t.forma]
    destaque = f"Tanque {forma}, nível de {_N(t.nivel_inicial_m, 2)} m"
    if r.evento == "vazio":
        destaque += f": esvazia em {tempo_em_texto(r.duracao, u)}."
    elif r.evento == "cheio":
        destaque += f": enche até o topo em {tempo_em_texto(r.duracao, u)}."
    elif r.evento == "estavel" and r.nivel_de_equilibrio is not None:
        destaque += f": estabiliza em {_N(r.nivel_de_equilibrio, 3)} m (entrada igual à saída)."
    else:
        destaque += f": {_N(float(r.niveis[-1]), 3)} m depois de {tempo_em_texto(r.duracao, u)}."
    if alvo is not None:
        ta = r.tempo_para(alvo)
        destaque += (
            f" O nível chega a {_N(alvo, 2)} m em {tempo_em_texto(ta, u)}."
            if ta is not None
            else f" O nível não chega a {_N(alvo, 2)} m."
        )
    figuras = [
        fnt.linhas_para_o_registro(
            "Nível no tanque",
            "Nível do líquido no tempo.",
            f"tempo ({u.rotulo})",
            "m",
            [_serie_no_tempo("Nível", r.tempos, r.niveis, u)],
            [("alvo", alvo)] if alvo is not None else [],
        ),  # fmt: skip
        fnt.linhas_para_o_registro(
            "Vazões do tanque",
            "Vazão de entrada e de saída no tempo.",
            f"tempo ({u.rotulo})",
            "L/s",
            [
                _serie_no_tempo("Entrada", r.tempos, r.entrada, u),
                _serie_no_tempo("Saída", r.tempos, r.saida, u),
            ],
        ),  # fmt: skip
    ]
    s = t.saida
    entradas = {
        "forma": t.forma,
        "altura_m": numero_json(t.altura_util, 4),
        "diametro_m": numero_json(t.diametro_m, 4),
        "comprimento_m": numero_json(t.comprimento_m, 4),
        "largura_m": numero_json(t.largura_m, 4),
        "nivel_inicial_m": numero_json(t.nivel_inicial_m, 4),
        "entrada_L_s": numero_json(t.entrada_L_s, 4),
        "saida": s.tipo,
        "diametro_saida_mm": numero_json(s.diametro_mm, 3),
        "cd": numero_json(s.cd, 3),
        "comprimento_tubo_m": numero_json(s.comprimento_m, 3),
        "desnivel_m": numero_json(s.desnivel_m, 3),
        "vazao_bomba_L_s": numero_json(s.vazao_bomba_L_s, 3),
    }
    return _registro(
        f"Tanque no tempo — nível ({forma})",
        destaque,
        entradas,
        _tabela(
            "Nível e vazões ao longo do tempo.",
            ["Instante", "Nível (m)", "Saída (L/s)"],
            r.tempos,
            [(r.niveis, 3), (r.saida, 2)],
        ),
        figuras,
        "Balanço de volume no tanque, dV/dt = Q_e − Q_s(h), integrado no tempo (Runge-Kutta com "
        "controle de erro), com a saída em regime quase permanente a cada nível.",
        tq.hipoteses_do_nivel(r),
        [_REF_FLUIDOS],
    )


# =============================================================================================
# Tanque: temperatura
# =============================================================================================
def cena_termica(r: tq.ResultadoTermico, alvo: float | None = None) -> dict[str, Any]:
    t = r.tanque
    tempos = tempos_dos_quadros(r.duracao)
    temps = np.interp(tempos, r.tempos, r.temperaturas)
    valores = [temps, [t.t_inicial]]
    if t.aquecimento == tq.SERPENTINA:
        valores.append([t.t_serpentina])
    if t.vazao_kg_s > 0:
        valores.append([t.t_entrada])
    tudo = np.concatenate([np.ravel(np.asarray(v, dtype=float)) for v in valores])
    cena = Cena(tempos, id=_id("termico", t, r.duracao), altura=360)
    esc = cena.escala(
        "Temperatura", "°C", float(tudo.min()), float(tudo.max()), cores=CALOR, casas=1
    )
    k_t = cena.canal(temps)
    aquecimento = np.interp(tempos, r.tempos, r.calor_aquecimento)
    perda = np.interp(tempos, r.tempos, r.calor_perda)
    vazao = np.interp(tempos, r.tempos, r.calor_vazao)
    # cada seta com a sua escala: a perda costuma ser bem menor que o aquecimento e sumiria
    ref_aquecimento = max(float(np.max(np.abs(aquecimento))), 1e-9)
    ref_perda = max(float(np.max(np.abs(perda))), 1e-9)
    k_aq, k_perda = cena.canal(aquecimento), cena.canal(perda)
    largura, altura = 1.0, 1.2
    cena.nivel(
        (0.0, 0.0, largura, altura),
        cena.canal(np.full(len(tempos), altura * 0.9)),
        escala=esc,
        canal_cor=k_t,
    )
    cena.retangulo(0.0, 0.0, largura, altura, vazio=True, contorno=_PAREDE, espessura=3.0)
    # agitador: motor em cima, eixo e pás
    cena.retangulo(
        0.42, altura + 0.02, 0.58, altura + 0.16, cor="#94a3b8", contorno=_PAREDE, espessura=1.5
    )
    cena.linha([(0.5, altura + 0.02), (0.5, 0.58)], largura=3, cor=_PAREDE)
    cena.linha([(0.36, 0.58), (0.64, 0.58)], largura=7, cor=_PAREDE, ponta="butt")
    cena.texto(0.6, altura + 0.09, "agitador", ancora="start", tamanho=10)
    zigue = [(0.12 + 0.76 * k / 14, 0.1 + (0.07 if k % 2 else 0.0)) for k in range(15)]
    if t.aquecimento == tq.SERPENTINA:
        cena.linha(
            zigue, largura=4, escala=esc, canal=cena.canal(t.t_serpentina), nome="Serpentina"
        )
        nome = f"serpentina a {_N(t.t_serpentina, 1)} °C · UA {_N(t.ua_serpentina, 0)} W/K"
    elif t.aquecimento == tq.POTENCIA:
        cena.linha(zigue, largura=3, cor="#b93a13")
        nome = f"resistência de {_N(t.potencia_kW, 1)} kW"
    else:
        nome = ""
    if t.aquecimento != tq.NENHUM:
        for k, x in enumerate((0.25, 0.5, 0.75)):
            cena.seta(
                x,
                0.2,
                0.0,
                1.0,
                comprimento=0.22,
                canal=k_aq,
                ref=ref_aquecimento,
                cor=_COR_CALOR,
                rotulo="{} kW" if k == 1 else "",
                casas=2,
            )
        cena.texto(0.5, -0.05, nome, base="top", tamanho=11)
    if t.ua_perda > 0:
        for k, (x, nx) in enumerate(((0.0, -1.0), (largura, 1.0))):
            for y in (0.45, 0.8):
                cena.seta(
                    x,
                    y,
                    nx,
                    0.0,
                    comprimento=0.3,
                    canal=k_perda,
                    ref=ref_perda,
                    cor=_COR_CALOR,
                    rotulo="{} kW" if (k == 1 and y == 0.8) else "",
                    casas=2,
                )
        cena.texto(
            largura + 0.05,
            1.0,
            f"perda para o ar a {_N(t.t_ambiente, 1)} °C",
            ancora="start",
            base="bottom",
            tamanho=10,
        )
    cena.texto(0.5, 0.88, "T = {} °C", canal=k_t, casas=1, negrito=True, tamanho=14)
    if t.termostato is not None and t.aquecimento != tq.NENHUM:
        cena.texto(
            0.5, altura + 0.2, f"termostato: {_N(t.termostato, 1)} °C", base="bottom", tamanho=11
        )
    if t.vazao_kg_s > 0:
        k_v = cena.canal(np.full(len(tempos), t.vazao_kg_s))
        cena.linha(
            [(-0.5, 1.0), (0.0, 1.0)],
            largura=8,
            escala=esc,
            canal=cena.canal(t.t_entrada),
            setas=True,
            fluxo=k_v,
            fluxo_ref=t.vazao_kg_s,
            espaco_setas=40,
            cor_setas=_COR_SETAS,
            contorno_setas=_CONTORNO_SETAS,
        )
        cena.texto(-0.52, 1.0, f"entra a {_N(t.t_entrada, 1)} °C", ancora="end", tamanho=11)
        cena.linha(
            [(largura, 0.3), (largura + 0.5, 0.3)],
            largura=8,
            escala=esc,
            canal=k_t,
            setas=True,
            fluxo=k_v,
            fluxo_ref=t.vazao_kg_s,
            espaco_setas=40,
            cor_setas=_COR_SETAS,
            contorno_setas=_CONTORNO_SETAS,
        )
        cena.texto(largura + 0.52, 0.3, "sai a {} °C", canal=k_t, ancora="start", tamanho=11)
    lado = 1.05 if t.vazao_kg_s > 0 else 0.5
    cena.vista = (-lado, -0.2, largura + max(lado, 0.75 if t.ua_perda > 0 else 0.0), altura + 0.3)
    limites = [("alvo", alvo)] if alvo is not None else []
    if t.termostato is not None and t.aquecimento != tq.NENHUM:
        limites.append(("termostato", t.termostato))
    estabiliza = "termostato segura" if r.tempo_do_termostato is not None else "estabiliza"
    marcos = [(estabiliza, r.tempo_para_estabilizar)]
    if alvo is not None:
        marcos.append(("chega ao alvo", r.tempo_para(alvo)))
    cena.grafico_no_tempo(
        "Temperatura no tanque", "°C", [("Líquido", k_t)], limites=limites, marcos=marcos
    )
    calores = [("Aquecimento", k_aq)]
    if t.ua_perda > 0:
        calores.append(("Perda para o ar", k_perda))
    if t.vazao_kg_s > 0:
        calores.append(("Levado pela vazão", cena.canal(vazao)))
    cena.grafico_no_tempo("Calor", "kW", calores, casas=2, marcos=marcos[:1])
    cena.nota = "Setas laranja: o calor entrando pelo aquecimento e saindo pela parede (o tamanho acompanha a potência)."
    return cena.como_dados()


def registro_termico(r: tq.ResultadoTermico, alvo: float | None = None) -> dict[str, Any]:
    t = r.tanque
    u = unidade_de_tempo(r.duracao)
    destaque = (
        f"Tanque de {_N(t.volume_m3, 2)} m³ de líquido, de {_N(t.t_inicial, 1)} °C: chega a "
        f"{_N(float(r.temperaturas[-1]), 1)} °C em {tempo_em_texto(r.duracao, u)}."
    )
    if r.tempo_do_termostato is not None and t.termostato is not None:
        destaque += (
            f" O termostato segura o líquido em {_N(t.termostato, 1)} °C a partir de "
            f"{tempo_em_texto(r.tempo_do_termostato, u)}."
        )
    elif r.t_equilibrio is not None:
        destaque += f" Equilíbrio em {_N(r.t_equilibrio, 1)} °C, com constante de tempo de {tempo_em_texto(r.tau or 0.0)}."
    if alvo is not None:
        ta = r.tempo_para(alvo)
        destaque += (
            f" O líquido chega a {_N(alvo, 1)} °C em {tempo_em_texto(ta, u)}."
            if ta is not None
            else f" O líquido não chega a {_N(alvo, 1)} °C."
        )
    figuras = [
        fnt.linhas_para_o_registro(
            "Temperatura no tanque",
            "Temperatura do líquido no tempo.",
            f"tempo ({u.rotulo})",
            "°C",
            [_serie_no_tempo("Líquido", r.tempos, r.temperaturas, u)],
            [("alvo", alvo)] if alvo is not None else [],
        ),  # fmt: skip
    ]
    entradas = {
        "volume_m3": numero_json(t.volume_m3, 4),
        "massa_especifica_kg_m3": numero_json(t.massa_especifica, 4),
        "calor_especifico_J_kgK": numero_json(t.calor_especifico, 4),
        "temperatura_inicial_C": numero_json(t.t_inicial, 3),
        "aquecimento": t.aquecimento,
        "potencia_kW": numero_json(t.potencia_kW, 4),
        "ua_serpentina_W_K": numero_json(t.ua_serpentina, 4),
        "temperatura_serpentina_C": numero_json(t.t_serpentina, 3),
        "ua_perda_W_K": numero_json(t.ua_perda, 4),
        "temperatura_ambiente_C": numero_json(t.t_ambiente, 3),
        "vazao_kg_s": numero_json(t.vazao_kg_s, 5),
        "temperatura_entrada_C": numero_json(t.t_entrada, 3),
        "termostato_C": None if t.termostato is None else numero_json(t.termostato, 3),
    }
    return _registro(
        "Tanque no tempo — temperatura",
        destaque,
        entradas,
        _tabela(
            "Temperatura e calor ao longo do tempo.",
            ["Instante", "Temperatura (°C)", "Aquecimento (kW)"],
            r.tempos,
            [(r.temperaturas, 1), (r.calor_aquecimento, 2)],
        ),
        figuras,
        "Balanço de energia do tanque bem misturado, m·c·dT/dt = P + UA_s·(T_s − T) + ṁ·c·(T_e − T) "
        "− UA_p·(T − T_amb), com solução exata em exponencial.",
        tq.hipoteses_termicas(r),
        [_REF_CALOR],
    )


# =============================================================================================
# Partida da linha
# =============================================================================================
def cena_da_partida(r: ln.ResultadoDaPartida) -> dict[str, Any]:
    linha = r.linha
    tempos = tempos_dos_quadros(r.duracao)
    vazoes = np.interp(tempos, r.tempos, r.vazoes)
    velocidades = np.interp(tempos, r.tempos, r.velocidades)
    manobra = np.interp(tempos, r.tempos, r.manobra)
    cena = Cena(tempos, id=_id("partida", linha, r.duracao), altura=330)
    v_max = max(float(velocidades.max()), 1e-9)
    esc = cena.escala("Velocidade", "m/s", 0.0, v_max, cores=AGUA, casas=2)
    k_q, k_v, k_m = cena.canal(vazoes), cena.canal(velocidades), cena.canal(manobra)
    queda = 1.0 if linha.desnivel_m >= 0 else -1.0
    superficie = 2.1
    cena.retangulo(0.0, 1.0, 1.4, superficie, cor=_AGUA)
    cena.linha(
        [(0.0, 2.55), (0.0, 1.0), (1.4, 1.0), (1.4, 2.55)], largura=4, cor=_PAREDE, ponta="butt"
    )
    cena.linha([(0.0, superficie), (1.4, superficie)], largura=1.5, cor="#0d366b")
    cena.texto(0.7, 2.62, "reservatório (nível fixo)", base="bottom", tamanho=11)
    saida_y = 1.2 - queda * 1.0
    pontos = [(1.4, 1.2), (2.4, 1.2), (5.4, saida_y), (7.0, saida_y)]
    cena.linha(
        pontos,
        largura=11,
        escala=esc,
        canal=k_v,
        nome="Tubo",
        setas=True,
        fluxo=k_v,
        fluxo_ref=v_max,
        espaco_setas=55,
        cor_setas=_COR_SETAS,
        contorno_setas=_CONTORNO_SETAS,
    )
    cena.linha(
        [(7.0, saida_y), (7.0, saida_y - 0.55)],
        largura=5,
        cor=_JATO,
        setas=True,
        fluxo=k_v,
        fluxo_ref=v_max,
        espaco_setas=30,
        visivel=k_q,
        cor_setas=_COR_SETAS,
        contorno_setas=_CONTORNO_SETAS,
    )
    if linha.tem_bomba:
        _bomba(cena, 2.0, 1.2, 0.13)
        texto = "bomba: rotação {} %" if linha.evento == ln.BOMBA else "bomba"
        cena.texto(
            2.0,
            1.55,
            texto,
            canal=k_m if linha.evento == ln.BOMBA else None,
            casas=0,
            tamanho=11,
            base="bottom",
        )
    _valvula(cena, 6.2, saida_y, 0.16)
    texto = "válvula {} % aberta" if linha.evento == ln.VALVULA else "válvula aberta"
    cena.texto(
        6.2,
        saida_y + 0.42,
        texto,
        canal=k_m if linha.evento == ln.VALVULA else None,
        casas=0,
        tamanho=11,
        base="bottom",
    )
    cena.texto(7.15, saida_y - 0.2, "Q = {} L/s", canal=k_q, casas=2, ancora="start", negrito=True)
    cena.texto(7.15, saida_y - 0.45, "v = {} m/s", canal=k_v, casas=2, ancora="start")
    cena.cota(
        (8.9, superficie),
        (8.9, saida_y),
        f"Δz = {_N(linha.desnivel_m, 2)} m",
        desloc=0,
    )
    cena.linha([(1.4, superficie), (9.7, superficie)], largura=1, cor="#94a3b8", tracejado=True)
    cena.texto(
        4.0,
        min(1.2, saida_y) - 0.5,
        f"L = {_N(linha.comprimento_m, 1)} m · D = {_N(linha.diametro_mm, 1)} mm (esquema fora de escala)",
        tamanho=11,
    )
    cena.vista = (-0.7, min(1.2, saida_y) - 0.85, 10.3, 2.85)
    t95, t99 = r.tempo_para(0.95), r.tempo_para(0.99)
    marcos = [
        ("fim da manobra", linha.tempo_manobra_s if linha.tempo_manobra_s > 0 else None),
        ("95 %", t95),
        ("estabiliza (99 %)", t99),
    ]
    cena.grafico_no_tempo(
        "Vazão na linha",
        "L/s",
        [("Vazão", k_q)],
        casas=2,
        limites=[("regime permanente", r.vazao_final)],
        marcos=marcos,
    )
    nome = "Abertura da válvula" if linha.evento == ln.VALVULA else "Rotação da bomba"
    cena.grafico_no_tempo(nome, "%", [(nome, k_m)], casas=0, faixa=(0.0, 105.0), marcos=marcos[:1])
    cena.nota = "A cor do tubo é a velocidade da água; as setas brancas andam com ela."
    return cena.como_dados()


def registro_da_partida(r: ln.ResultadoDaPartida) -> dict[str, Any]:
    linha = r.linha
    u = unidade_de_tempo(r.duracao)
    t95, t99 = r.tempo_para(0.95), r.tempo_para(0.99)
    manobra = "abertura da válvula" if linha.evento == ln.VALVULA else "partida da bomba"
    destaque = (
        f"Linha de {_N(linha.comprimento_m, 1)} m e {_N(linha.diametro_mm, 1)} mm, {manobra} em "
        f"{_N(linha.tempo_manobra_s, 1)} s: a vazão chega a 95 % do regime permanente "
        f"({_N(r.vazao_final, 2)} L/s) em {tempo_em_texto(t95, u) if t95 is not None else '—'} e a "
        f"99 % em {tempo_em_texto(t99, u) if t99 is not None else '—'}."
    )
    figuras = [
        fnt.linhas_para_o_registro(
            "Vazão na partida",
            "Vazão na linha no tempo, até o regime permanente.",
            f"tempo ({u.rotulo})",
            "L/s",
            [_serie_no_tempo("Vazão", r.tempos, r.vazoes, u)],
            [("regime permanente", r.vazao_final)],
        ),  # fmt: skip
    ]
    entradas = {
        "comprimento_m": numero_json(linha.comprimento_m, 4),
        "diametro_mm": numero_json(linha.diametro_mm, 4),
        "rugosidade_mm": numero_json(linha.rugosidade_mm, 5),
        "k_local": numero_json(linha.k_local, 4),
        "desnivel_m": numero_json(linha.desnivel_m, 4),
        "massa_especifica_kg_m3": numero_json(linha.massa_especifica, 4),
        "viscosidade_Pa_s": numero_json(linha.viscosidade, 8),
        "manobra": linha.evento,
        "tempo_manobra_s": numero_json(linha.tempo_manobra_s, 3),
        "k_valvula": numero_json(linha.k_valvula, 4),
        "bomba_h0_m": numero_json(linha.bomba_h0_m, 4),
        "bomba_qmax_L_s": numero_json(linha.bomba_qmax_L_s, 4),
        "celeridade_m_s": numero_json(linha.celeridade_m_s, 2),
    }
    return _registro(
        f"Partida da linha — {manobra}",
        destaque,
        entradas,
        _tabela(
            "Vazão e velocidade na partida.",
            ["Instante", "Vazão (L/s)", "Velocidade (m/s)"],
            r.tempos,
            [(r.vazoes, 2), (r.velocidades, 3)],
        ),
        figuras,
        "Coluna rígida: (L/(g·A))·dQ/dt = Δz + H_b − (1 + f·L/D + ΣK + K_v)·Q·|Q|/(2·g·A²), "
        "integrada no tempo, com f de Darcy (Colebrook) a cada velocidade.",
        ln.hipoteses_da_partida(r),
        [_REF_TRANSIENTE, _REF_FLUIDOS],
    )


# =============================================================================================
# Água quente chegando
# =============================================================================================
def _faixas(valores: np.ndarray, n: int) -> np.ndarray:
    """Média de ``n`` faixas iguais ao longo das células (quadros × células → quadros × n)."""
    quadros, celulas = valores.shape
    bordas = np.linspace(0, celulas, n + 1).round().astype(int)
    return np.stack(
        [valores[:, a:b].mean(axis=1) for a, b in zip(bordas[:-1], bordas[1:], strict=True)], axis=1
    )


def perfil_permanente(r: ln.ResultadoDoTubo) -> np.ndarray:
    tubo = r.tubo
    rho, _, cp, _ = ln.propriedades_da_agua(0.5 * (tubo.t_entrada + tubo.t_inicial))
    massa = rho * tubo.vazao_L_s / 1000.0
    r_total = 1.0 / (r.h_interno * math.pi * tubo.diametro_mm / 1000.0) + ln.resistencia_de_fora(
        tubo
    )
    return tubo.t_ambiente + (tubo.t_entrada - tubo.t_ambiente) * np.exp(
        -r.x / (massa * cp * r_total)
    )


def cena_do_tubo(r: ln.ResultadoDoTubo, alvo: float | None = None) -> dict[str, Any]:
    tubo = r.tubo
    tempos = r.tempos
    cena = Cena(tempos, id=_id("tubo", tubo, r.duracao), altura=270)
    lo = min(tubo.t_inicial, tubo.t_entrada, tubo.t_ambiente)
    hi = max(tubo.t_inicial, tubo.t_entrada, tubo.t_ambiente)
    esc = cena.escala("Temperatura", "°C", lo, hi, cores=CALOR, casas=1)
    n = 60
    fluido = _faixas(r.fluido, n)
    parede = _faixas(r.parede, n)
    k_f = cena.canais(fluido)
    k_w = cena.canais(parede)
    comprimento = 10.0
    passo = comprimento / n
    for i in range(n):
        x0, x1 = i * passo, (i + 1) * passo + (0.01 if i < n - 1 else 0.0)
        cena.retangulo(x0, 0.20, x1, 1.24, escala=esc, canal=k_f[i], nome="Água")
        cena.retangulo(x0, 1.24, x1, 1.44, escala=esc, canal=k_w[i], nome="Parede")
        cena.retangulo(x0, 0.0, x1, 0.20, escala=esc, canal=k_w[i], nome="Parede")
    topo, fundo = 1.44, 0.0
    if tubo.isolamento_mm > 0:
        cena.retangulo(
            0.0,
            1.44,
            comprimento,
            1.72,
            cor="#f1f5f9",
            hachura=True,
            contorno=_PAREDE,
            espessura=0.8,
        )
        cena.retangulo(
            0.0,
            -0.28,
            comprimento,
            0.0,
            cor="#f1f5f9",
            hachura=True,
            contorno=_PAREDE,
            espessura=0.8,
        )
        topo, fundo = 1.72, -0.28
        cena.texto(
            comprimento * 0.02,
            0.79,
            f"isolamento {_N(tubo.isolamento_mm, 0)} mm",
            ancora="start",
            tamanho=9,
        )
    cena.retangulo(0.0, 0.0, comprimento, 1.44, vazio=True, contorno="texto", espessura=1.2)
    k_vel = cena.canal(np.full(len(tempos), r.velocidade))
    cena.linha(
        [(0.0, 0.72), (comprimento, 0.72)],
        largura=0.1,
        cor="#ffffff",
        setas=True,
        fluxo=k_vel,
        fluxo_ref=r.velocidade,
        espaco_setas=70,
        cor_setas=_COR_SETAS,
        contorno_setas=_CONTORNO_SETAS,
    )
    # o calor que a parede perde para o ar, em alguns pontos ao longo do tubo
    perdas = (r.parede - tubo.t_ambiente) / ln.resistencia_de_fora(tubo)  # quadros × células, W/m
    referencia = max(float(np.max(np.abs(perdas))), 1e-9)
    colunas = perdas.shape[1]
    for k, f in enumerate((0.22, 0.36, 0.5, 0.64, 0.78)):
        canal = cena.canal(perdas[:, min(int(f * colunas), colunas - 1)])
        cena.seta(
            f * comprimento, topo, 0.0, 1.0, comprimento=0.4, canal=canal, ref=referencia, cor=_COR_CALOR,
            largura=2.5, rotulo="perde {} W/m" if k == 2 else "", casas=1,
        )  # fmt: skip
    saida = np.interp(tempos, r.tempos_saida, r.saida)
    k_s = cena.canal(saida)
    cena.texto(
        0.0,
        topo + 0.12,
        f"entra a {_N(tubo.t_entrada, 1)} °C",
        ancora="start",
        base="bottom",
        tamanho=11,
    )
    cena.texto(
        comprimento,
        topo + 0.12,
        "sai a {} °C",
        canal=k_s,
        ancora="end",
        base="bottom",
        tamanho=12,
        negrito=True,
    )
    cena.cota(
        (0.0, fundo - 0.42),
        (comprimento, fundo - 0.42),
        f"L = {_N(tubo.comprimento_m, 1)} m · D = {_N(tubo.diametro_mm, 1)} mm · v = {_N(r.velocidade, 2)} m/s (fora de escala)",
    )
    cena.vista = (-0.4, fundo - 0.62, comprimento + 0.4, topo + 1.05)
    limites = [("entrada", tubo.t_entrada)]
    if alvo is not None:
        limites.append(("alvo", alvo))
    marcos = [
        ("trânsito L/v", tubo.comprimento_m / r.velocidade),
        ("estabiliza", r.tempo_para_estabilizar()),
    ]
    if alvo is not None:
        marcos.append(("chega ao alvo", r.tempo_para(alvo)))
    cena.grafico_no_tempo(
        "Temperatura na saída", "°C", [("Saída", k_s)], limites=limites, marcos=marcos
    )
    pontos = 120
    x = (np.arange(pontos) + 0.5) * tubo.comprimento_m / pontos
    cena.grafico_de_perfil(
        "Temperatura ao longo do tubo",
        "°C",
        x,
        cena.canais(_faixas(r.fluido, pontos)),
        rotulo_x="distância da entrada (m)",
        rotulo_curto="x (m)",
        nome="Água",
        outras=[("Parede", cena.canais(_faixas(r.parede, pontos)))],
        fixas=[("Regime permanente", np.interp(x, r.x, perfil_permanente(r)))],
        faixa=(lo - 0.04 * (hi - lo), hi + 0.04 * (hi - lo)),
    )
    cena.nota = "Faixa do meio: a água; de cima e de baixo: a parede. Setas brancas: a água andando; laranja: o calor que a parede perde."
    return cena.como_dados()


def verificacoes_do_tubo(
    r: ln.ResultadoDoTubo, alvo: float | None, prazo: float | None
) -> list[Verificacao]:
    if alvo is None or prazo is None or prazo <= 0:
        return []
    t = r.tempo_para(alvo)
    u = unidade_de_tempo(r.duracao)
    return [
        Verificacao(
            f"Água na saída a {_N(alvo, 1)} °C",
            None if t is None else t / u.fator,
            prazo / u.fator,
            u.rotulo,
            "Tempo para a saída chegar à temperatura pedida, dentro do prazo",
            "não chega no tempo calculado" if t is None else f"t = {tempo_em_texto(t, u)}",
            status="OK" if t is not None and t <= prazo else "NÃO OK",
            tipo="limite",
        )
    ]


def registro_do_tubo(
    r: ln.ResultadoDoTubo, alvo: float | None = None, prazo: float | None = None
) -> dict[str, Any]:
    tubo = r.tubo
    u = unidade_de_tempo(r.duracao)
    destaque = (
        f"Tubo de {_N(tubo.comprimento_m, 1)} m e {_N(tubo.diametro_mm, 1)} mm, a {_N(tubo.t_inicial, 1)} °C, "
        f"recebendo água a {_N(tubo.t_entrada, 1)} °C com {_N(tubo.vazao_L_s, 3)} L/s: em regime "
        f"permanente a saída fica a {_N(r.saida_permanente, 1)} °C, perdendo {_N(r.perda_permanente_W, 0)} W."
    )
    if alvo is not None:
        t = r.tempo_para(alvo)
        destaque += (
            f" A saída chega a {_N(alvo, 1)} °C em {tempo_em_texto(t, u)}, depois de sair "
            f"{_N(r.volume_ate(alvo) or 0.0, 1)} L de água."
            if t is not None
            else f" A saída não chega a {_N(alvo, 1)} °C."
        )
    verificacoes = verificacoes_do_tubo(r, alvo, prazo)
    figuras = [
        fnt.linhas_para_o_registro(
            "Temperatura na saída do tubo",
            "Temperatura da água na saída no tempo.",
            f"tempo ({u.rotulo})",
            "°C",
            [_serie_no_tempo("Saída", r.tempos_saida, r.saida, u)],
            [("alvo", alvo)] if alvo is not None else [],
        ),  # fmt: skip
    ]
    entradas = {
        "comprimento_m": numero_json(tubo.comprimento_m, 4),
        "diametro_mm": numero_json(tubo.diametro_mm, 4),
        "parede_mm": numero_json(tubo.parede_mm, 4),
        "material_parede": tubo.material.nome,
        "isolamento_mm": numero_json(tubo.isolamento_mm, 4),
        "k_isolamento_W_mK": numero_json(tubo.k_isolamento, 5),
        "h_externo_W_m2K": numero_json(tubo.h_externo, 4),
        "temperatura_ambiente_C": numero_json(tubo.t_ambiente, 3),
        "vazao_L_s": numero_json(tubo.vazao_L_s, 5),
        "temperatura_inicial_C": numero_json(tubo.t_inicial, 3),
        "temperatura_entrada_C": numero_json(tubo.t_entrada, 3),
    }
    return _registro(
        "Água quente chegando no tubo",
        destaque,
        entradas,
        _tabela(
            "Temperatura da água na saída.",
            ["Instante", "Saída (°C)"],
            r.tempos_saida,
            [(r.saida, 1)],
        ),
        figuras,
        "Transporte da água pela velocidade média e troca de calor com a parede (película de "
        "dentro) e da parede para o ar (isolamento e película de fora), com a capacidade de calor "
        "da parede; transporte exato célula a célula e troca resolvida exata em cada passo.",
        ln.hipoteses_do_tubo(r),
        [_REF_CALOR],
        verificacoes,
    )


def registro_dos_vasos(r: tq.ResultadoDosVasos) -> dict[str, Any]:
    v = r.vasos
    u = unidade_de_tempo(r.duracao)
    d0 = float(r.diferenca[0])
    if r.evento == "equalizou":
        destaque = (
            f"Dois tanques ligados por um tubo de {_N(v.ligacao.diametro_mm, 1)} mm e "
            f"{_N(v.ligacao.comprimento_m, 1)} m, com {_N(abs(d0), 3)} m de diferença entre as "
            f"superfícies: os níveis ficam iguais (a 1 mm) em {tempo_em_texto(r.duracao, u)}"
        )
        if r.superficie_de_equilibrio is not None:
            destaque += f", na cota {_N(r.superficie_de_equilibrio, 3)} m."
        else:
            destaque += "."
    else:
        destaque = (
            f"Dois tanques ligados, com {_N(abs(d0), 3)} m de diferença entre as superfícies: "
            + (" ".join(r.avisos) or f"situação depois de {tempo_em_texto(r.duracao, u)}.")
        )
    superficie_2 = v.cota_fundo_2 + r.niveis_2
    marcos = [("equaliza", r.duracao / u.fator)] if r.evento == "equalizou" else []
    figuras = [
        fnt.linhas_para_o_registro(
            "Superfície da água nos dois tanques",
            "Cota da água de cada tanque no tempo, medida do fundo do tanque 1.",
            f"tempo ({u.rotulo})",
            "m",
            [
                _serie_no_tempo("Tanque 1", r.tempos, r.niveis_1, u),
                _serie_no_tempo("Tanque 2", r.tempos, superficie_2, u),
            ],
            [("nível igual", r.superficie_de_equilibrio)]
            if r.superficie_de_equilibrio is not None
            else [],
            marcos,
        ),
    ]
    entradas = {
        "tanque_1": {
            "forma": v.tanque_1.forma,
            "nivel_inicial_m": numero_json(v.tanque_1.nivel_inicial_m, 4),
        },
        "tanque_2": {
            "forma": v.tanque_2.forma,
            "nivel_inicial_m": numero_json(v.tanque_2.nivel_inicial_m, 4),
        },
        "cota_fundo_2_m": numero_json(v.cota_fundo_2, 4),
        "diametro_ligacao_mm": numero_json(v.ligacao.diametro_mm, 3),
        "comprimento_ligacao_m": numero_json(v.ligacao.comprimento_m, 3),
        "k_ligacao": numero_json(v.ligacao.k_local, 3),
    }
    return _registro(
        "Tanques no tempo — vasos comunicantes",
        destaque,
        entradas,
        _tabela(
            "Níveis e vazão entre os tanques.",
            ["Instante", "Nível 1 (m)", "Nível 2 (m)", "Vazão 1→2 (L/s)"],
            r.tempos,
            [(r.niveis_1, 3), (r.niveis_2, 3), (r.vazao, 2)],
        ),
        figuras,
        "Balanço de volume nos dois tanques, com a vazão do tubo de ligação pela energia "
        "(Darcy-Weisbach, peças e saída) a cada desnível, integrado no tempo.",
        tq.hipoteses_dos_vasos(r),
        [_REF_FLUIDOS],
    )
