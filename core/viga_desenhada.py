"""A viga desenhada na prancheta de Vigas e eixos: o desenho vira o modelo em texto e o resultado
volta ao desenho.

O desenho (o que a prancheta ``components/prancheta_viga`` manda e recebe) é um dicionário::

    {"L": 6.0,
     "apoios": [{"nome": "A", "tipo": "Pino", "x": 0.0, "kv": None, "kr": None}, ...],
     "rotulas": [{"nome": "R1", "x": 3.0}, ...],
     "cargas": [{"nome": "P1", "tipo": "Força", "x": 3.0, "x2": None, "valor": -20.0,
                 "valor2": None, "caso": "", "e": None}, ...]}

Unidades do modelo em texto (:mod:`core.beam_script`): posições em m, forças em kN, momentos e
torques em kN·m, distribuídas em kN/m, kv em N/mm, kr em N·mm/rad. Sinais: força e distribuída
positivas para cima, momento positivo anti-horário, axial e torque positivos no sentido de +x.

O desenho só descreve a barra, os apoios e as cargas; a seção, o material e o peso próprio vêm dos
campos da página, e :func:`linhas_do_desenho` dá as linhas que o interpretador lê — o mesmo
caminho do modo texto, com as mesmas validações.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from core import beam_analysis as vb
from core import beam_script as escrita

PINO = "Pino"
ROLETE = "Rolete"
ENGASTE = "Engaste"
DESLIZANTE = "Deslizante"
TRAVA = "Trava axial"
MOLA = "Mola"
FORCA = "Força"
MOMENTO = "Momento"
DISTRIBUIDA = "Distribuída"
AXIAL = "Axial"
AXIAL_DIST = "Axial distribuída"
TORQUE = "Torque"
APOIOS = (PINO, ROLETE, ENGASTE, DESLIZANTE, TRAVA, MOLA)
CARGAS = (FORCA, MOMENTO, DISTRIBUIDA, AXIAL, AXIAL_DIST, TORQUE)
COM_TRECHO = (DISTRIBUIDA, AXIAL_DIST)

#: O tipo do desenho → o tipo do modelo em texto.
TIPO_NO_TEXTO = {
    PINO: "pino",
    ROLETE: "rolete",
    ENGASTE: "engaste",
    DESLIZANTE: "deslizante",
    TRAVA: "trava_axial",
    MOLA: "mola",
}
#: O tipo do modelo (core.beam_model) → o tipo do desenho.
TIPO_NO_DESENHO = {
    "pino": PINO,
    "rolete": ROLETE,
    "engaste": ENGASTE,
    "engaste deslizante": DESLIZANTE,
    "apoio horizontal": TRAVA,
    "mola": MOLA,
}
_COMANDO = {FORCA: "P", MOMENTO: "M", DISTRIBUIDA: "q", AXIAL: "N", AXIAL_DIST: "qn", TORQUE: "T"}
#: O começo do nome de cada carga nova (o mesmo da prancheta).
PREFIXO = {FORCA: "P", MOMENTO: "M", DISTRIBUIDA: "q", AXIAL: "N", AXIAL_DIST: "n", TORQUE: "T"}


def _num(valor: Any, padrao: float = 0.0) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return padrao
    return numero if math.isfinite(numero) else padrao


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def exemplo() -> dict[str, Any]:
    """A viga do começo: biapoiada de 6 m com 15 kN/m e 20 kN no meio, para baixo."""
    return {
        "L": 6.0,
        "apoios": [
            {"nome": "A", "tipo": PINO, "x": 0.0, "kv": None, "kr": None},
            {"nome": "B", "tipo": ROLETE, "x": 6.0, "kv": None, "kr": None},
        ],
        "rotulas": [],
        "cargas": [
            {"nome": "q1", "tipo": DISTRIBUIDA, "x": 0.0, "x2": 6.0, "valor": -15.0,
             "valor2": -15.0, "caso": "", "e": None},
            {"nome": "P1", "tipo": FORCA, "x": 3.0, "x2": None, "valor": -20.0, "valor2": None,
             "caso": "", "e": None},
        ],
    }  # fmt: skip


def vazio(comprimento_m: float = 6.0) -> dict[str, Any]:
    return {"L": comprimento_m, "apoios": [], "rotulas": [], "cargas": []}


def normalizar(dados: Mapping[str, Any] | None) -> dict[str, Any]:
    """O desenho com as chaves todas, números finitos e tipos conhecidos (o que veio estragado
    da sessão ou de um arquivo velho some, em vez de derrubar a página)."""
    dados = dados if isinstance(dados, Mapping) else {}
    comprimento = max(_num(dados.get("L"), 6.0), 1e-3)
    apoios = []
    for a in dados.get("apoios") or []:
        if not isinstance(a, Mapping) or a.get("tipo") not in APOIOS:
            continue
        apoios.append(
            {
                "nome": _texto(a.get("nome")) or "?",
                "tipo": a["tipo"],
                "x": _num(a.get("x")),
                "kv": None if a.get("kv") in (None, "") else _num(a.get("kv")),
                "kr": None if a.get("kr") in (None, "") else _num(a.get("kr")),
            }
        )
    rotulas = [
        {"nome": _texto(r.get("nome")) or "R", "x": _num(r.get("x"))}
        for r in dados.get("rotulas") or []
        if isinstance(r, Mapping)
    ]
    cargas = []
    for c in dados.get("cargas") or []:
        if not isinstance(c, Mapping) or c.get("tipo") not in CARGAS:
            continue
        trecho = c["tipo"] in COM_TRECHO
        valor = _num(c.get("valor"))
        cargas.append(
            {
                "nome": _texto(c.get("nome")) or "?",
                "tipo": c["tipo"],
                "x": _num(c.get("x")),
                "x2": _num(c.get("x2"), comprimento) if trecho else None,
                "valor": valor,
                "valor2": _num(c.get("valor2"), valor) if trecho else None,
                "caso": _texto(c.get("caso")),
                "e": _num(c.get("e"))
                if c["tipo"] == AXIAL and c.get("e") not in (None, "")
                else None,
            }
        )
    return {"L": comprimento, "apoios": apoios, "rotulas": rotulas, "cargas": cargas}


def _caso(c: Mapping[str, Any]) -> str:
    caso = _texto(c.get("caso"))
    if not caso or caso == vb.CASO_PADRAO:
        return ""
    return f" caso={escrita._campo_de_texto(caso)}"


def linhas_do_desenho(dados: Mapping[str, Any]) -> list[str]:
    """As linhas do modelo em texto: a barra, os apoios, as rótulas e as cargas."""
    d = normalizar(dados)
    num = escrita.formatar_numero
    linhas = [f"viga {num(d['L'])}"]
    for a in d["apoios"]:
        extras = ""
        if a["tipo"] == MOLA:
            if a["kv"]:
                extras += f" kv={num(a['kv'])}"
            if a["kr"]:
                extras += f" kr={num(a['kr'])}"
        linhas.append(f"apoio {num(a['x'])} {TIPO_NO_TEXTO[a['tipo']]}{extras}")
    for r in d["rotulas"]:
        linhas.append(f"rotula {num(r['x'])}")
    for c in d["cargas"]:
        comando = _COMANDO[c["tipo"]]
        if c["tipo"] in COM_TRECHO:
            x1, x2 = sorted((c["x"], c["x2"]))
            final = "" if c["valor2"] == c["valor"] else f" {num(c['valor2'])}"
            linhas.append(f"{comando} {num(x1)} {num(x2)} {num(c['valor'])}{final}{_caso(c)}")
        else:
            extra = f" e={num(c['e'])}" if c["tipo"] == AXIAL and c.get("e") else ""
            linhas.append(f"{comando} {num(c['x'])} {num(c['valor'])}{extra}{_caso(c)}")
    return linhas


def _caso_do_modelo(carga: Any) -> str:
    caso = str(getattr(carga, "caso", "") or "")
    return "" if caso == vb.CASO_PADRAO else caso


def desenho_do_modelo(viga: vb.Viga) -> dict[str, Any]:
    """O desenho de um modelo já interpretado (os exemplos e o modelo em texto vão à prancheta)."""
    letras = [chr(65 + k) for k in range(26)]
    apoios = [
        {
            "nome": a.rotulo or letras[k % 26],
            "tipo": TIPO_NO_DESENHO.get(a.tipo, PINO),
            "x": a.x_mm / 1000.0,
            "kv": a.rigidez_vertical_N_mm or None,
            "kr": a.rigidez_rotacional_Nmm_rad or None,
        }
        for k, a in enumerate(viga.apoios)
        if a.tipo in TIPO_NO_DESENHO
    ]
    rotulas = [{"nome": f"R{k + 1}", "x": r.x_mm / 1000.0} for k, r in enumerate(viga.rotulas)]
    cargas: list[dict[str, Any]] = []

    def pontual(tipo: str, x_mm: float, valor: float, carga: Any) -> None:
        cargas.append(
            {
                "nome": f"{PREFIXO[tipo]}{sum(1 for c in cargas if c['tipo'] == tipo) + 1}",
                "tipo": tipo,
                "x": x_mm / 1000.0,
                "x2": None,
                "valor": valor,
                "valor2": None,
                "caso": _caso_do_modelo(carga),
                "e": 0.0 if tipo == AXIAL else None,
            }
        )

    def trecho(tipo: str, x1: float, x2: float, w1: float, w2: float, carga: Any) -> None:
        cargas.append(
            {
                "nome": f"{PREFIXO[tipo]}{sum(1 for c in cargas if c['tipo'] == tipo) + 1}",
                "tipo": tipo,
                "x": x1 / 1000.0,
                "x2": x2 / 1000.0,
                "valor": w1,
                "valor2": w2,
                "caso": _caso_do_modelo(carga),
                "e": None,
            }
        )

    for p in viga.cargas_pontuais:
        pontual(FORCA, p.x_mm, p.fy_N / 1000.0, p)
    for m in viga.momentos:
        pontual(MOMENTO, m.x_mm, m.mz_Nmm / 1e6, m)
    for q in viga.cargas_distribuidas:
        trecho(DISTRIBUIDA, q.x_inicial_mm, q.x_final_mm, q.w_inicial_N_mm, q.w_final, q)
    for n in viga.cargas_axiais:
        pontual(AXIAL, n.x_mm, n.fx_N / 1000.0, n)
    for a in viga.cargas_axiais_distribuidas:
        trecho(AXIAL_DIST, a.x_inicial_mm, a.x_final_mm, a.a_inicial_N_mm, a.a_final, a)
    for t in viga.torques:
        pontual(TORQUE, t.x_mm, t.t_Nmm / 1e6, t)
    return normalizar(
        {"L": viga.comprimento_mm / 1000.0, "apoios": apoios, "rotulas": rotulas, "cargas": cargas}
    )


def problemas(dados: Mapping[str, Any]) -> list[str]:
    """O que impede a conta antes de ir ao interpretador, em linguagem simples."""
    d = normalizar(dados)
    saida = []
    if not d["apoios"]:
        saida.append("Ponha ao menos um apoio na barra (Pino, Rolete ou Engaste).")
    for a in d["apoios"]:
        if a["tipo"] == MOLA and not (a["kv"] or a["kr"]):
            saida.append(f"A mola {a['nome']} precisa da rigidez kv ou kr.")
    for c in d["cargas"]:
        if c["tipo"] in COM_TRECHO and abs(c["x2"] - c["x"]) < 1e-9:
            saida.append(f"A carga {c['nome']} começa e termina no mesmo ponto.")
    return saida


def _kn(valor_N: float, casas: int = 2) -> str:
    return f"{valor_N / 1000.0:.{casas}f}".replace(".", ",").replace("-0,00", "0,00")


def marcas(resultado: vb.ResultadoViga, dados: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """As reações de cada apoio para a prancheta desenhar (kN e kN·m, como as cargas), com o nome
    do apoio do desenho (o que está no mesmo x)."""
    apoios = normalizar(dados)["apoios"] if dados is not None else []
    reacoes = []
    for r in resultado.reacoes:
        fy, fx, mz, mt = r.fy_N, r.fx_N, r.mz_Nmm, r.mt_Nmm
        x = r.x_mm / 1000.0
        nome = next((a["nome"] for a in apoios if abs(a["x"] - x) < 1e-6), "") or "R"
        reacoes.append(
            {
                "x": x,
                "fy": fy / 1000.0 if abs(fy) >= 0.5 else 0.0,
                "fx": fx / 1000.0 if abs(fx) >= 0.5 else 0.0,
                "mz": mz / 1e6 if abs(mz) >= 500.0 else 0.0,
                "texto_fy": f"{nome}: {_kn(abs(fy))} kN",
                "texto_fx": f"{_kn(abs(fx))} kN",
                "texto_mz": f"{_kn(abs(mz) / 1000.0)} kN·m",
                "texto_t": f"T = {_kn(mt / 1000.0)} kN·m" if abs(mt) >= 500.0 else "",
                "ruim": False,
            }
        )
    return {"reacoes": reacoes, "erro": ""}


def marcas_de_erro(mensagem: str) -> dict[str, Any]:
    return {"reacoes": [], "erro": mensagem}
