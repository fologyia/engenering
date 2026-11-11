"""O Montador de fórmulas leva números a outras análises, e a que recebeu avisa se ele mudar depois.

Cada envio fica na sessão, por destino, com os números que foram e os de agora: a cada rodada o
Montador refaz os números do mesmo ponto (``atualizar``). A página que recebeu compara (``aviso``) e
só avisa enquanto ainda mostra o que o Montador mandou: se outra página mandou depois, ou se a pessoa
mudou os números lá, aquele envio não vale mais.

As chaves de cada página são as mesmas que o Cálculo de peças e Vigas e eixos já usam.
"""

from __future__ import annotations

import json
import math
import uuid
from collections.abc import Callable, Mapping
from typing import Any

import streamlit as st

CHAVE = "montador_repasses"
ORIGEM = "Montador de fórmulas"
ESTATICA = "estatica"
MOHR = "mohr"
FADIGA = "fadiga"
PAGINAS = {
    ESTATICA: ("Análise estática", "app_pages/analise_estatica.py"),
    MOHR: ("Círculo de Mohr", "app_pages/circulo_mohr.py"),
    FADIGA: ("Análise de fadiga", "app_pages/analise_fadiga.py"),
}
_ROTULOS = {
    "sigma_x": ("σx", "MPa"),
    "sigma_y": ("σy", "MPa"),
    "tau_xy": ("τxy", "MPa"),
    "sigma_a": ("σa", "MPa"),
    "sigma_m": ("σm", "MPa"),
    "d": ("d", "mm"),
}
_CAMPOS_DO_MOHR = {
    "sigma_x": "mohr_2d_sigma_x_assistente",
    "sigma_y": "mohr_2d_sigma_y_assistente",
    "tau_xy": "mohr_2d_tau_xy_assistente",
}
_GIRO_DO_MOHR = "mohr_2d_theta_assistente"
_NA_ESTATICA = {
    "sigma_x": "estatica_sigma_x",
    "sigma_y": "estatica_sigma_y",
    "tau_xy": "estatica_tau_xy",
}
_NA_FADIGA = {"sigma_a": "fadiga_sigma_alternada_nominal", "sigma_m": "fadiga_sigma_media"}
#: O diâmetro que a Análise de fadiga aceita em flexão, em cada referência dos fatores de Marin.
_DIAMETROS_DA_FADIGA = {"norton": (0.1, 10_000.0), "shigley": (2.79, 254.0)}


def _numero(valor: float) -> str:
    return f"{valor:.4g}".replace(".", ",")


def _perto(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is None and b is None
    try:
        return math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=1e-6)
    except (TypeError, ValueError):
        return False


def _iguais(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    return set(a) == set(b) and all(_perto(a[k], b[k]) for k in a)


def _marca(valores: Mapping[str, Any] | None) -> str:
    if valores is None:
        return "sem número"
    return json.dumps({k: round(float(v), 6) for k, v in valores.items()}, sort_keys=True)


def repasses() -> dict[str, dict[str, Any]]:
    estado = st.session_state
    if not isinstance(estado.get(CHAVE), dict):
        estado[CHAVE] = {}
    return estado[CHAVE]


def aplicar(
    destino: str,
    valores: Mapping[str, float],
    descricao: str,
    origem_id: str | None,
    repasse_id: str,
) -> None:
    """Põe os números nas chaves da página de destino, sem trocar de página."""
    estado = st.session_state
    if destino == MOHR:
        estado["mohr_assistente_2d"] = {
            "sigma_x": float(valores["sigma_x"]),
            "sigma_y": float(valores["sigma_y"]),
            "tau_xy": float(valores["tau_xy"]),
            "descricao": descricao,
            "origem_registro_id": origem_id,
            "origem": ORIGEM,
            "repasse_id": repasse_id,
        }
        estado["mohr_tipo_estado"] = "Estado plano (2D)"
        estado["mohr_2d_exemplo"] = "assistente"
        # O número vai direto no campo. Só apagar o campo bastava ao chegar de outra página; com
        # a página aberta, o navegador continuava mostrando o número velho, e o devolvia no
        # clique seguinte.
        for nome, chave in _CAMPOS_DO_MOHR.items():
            estado[chave] = float(valores[nome])
    elif destino == ESTATICA:
        for nome, chave in _NA_ESTATICA.items():
            estado[chave] = float(valores[nome])
        estado["estatica_origem_registro_id"] = origem_id
    elif destino == FADIGA:
        for nome, chave in _NA_FADIGA.items():
            estado[chave] = float(valores[nome])
        # σa' e σm' já vêm com K_f: o entalhe não pode contar de novo. E o von Mises das parcelas
        # é o caso do fator de carregamento 1, que na página é o de flexão.
        estado["modo_entalhe"] = "Sem entalhe"
        estado["fadiga_tipo_carregamento"] = "flexao"
        d = valores.get("d")
        for modelo, (minimo, maximo) in _DIAMETROS_DA_FADIGA.items():
            if d is not None and minimo <= d <= maximo:
                estado[f"modo_diametro_{modelo}_flexao"] = "Informar d equivalente"
                estado[f"diametro_{modelo}_flexao"] = float(d)


def enviar(
    destino: str,
    valores: Mapping[str, float],
    descricao: str,
    origem_id: str | None,
    *,
    parte: str,
    ponto: str,
) -> None:
    """Guarda o envio, põe os números no destino e abre a página. Só no corpo, fora de callback."""
    repasse_id = uuid.uuid4().hex
    repasses()[destino] = {
        "id": repasse_id,
        "parte": parte,
        "ponto": ponto,
        "valores": dict(valores),
        "atual": dict(valores),
        "motivo": "",
        "descricao": descricao,
        "origem_id": origem_id,
        "dispensado": None,
    }
    aplicar(destino, valores, descricao, origem_id, repasse_id)
    if destino == MOHR:
        st.session_state.pop(_GIRO_DO_MOHR, None)  # estado novo começa no giro padrão
    st.switch_page(PAGINAS[destino][1])


def atualizar(
    parte: str,
    calcular: Callable[[str, Mapping[str, Any]], tuple[dict[str, float] | None, str]],
) -> None:
    """No Montador, a cada rodada: os números de agora de cada envio desta parte, ou o motivo."""
    for destino, repasse in repasses().items():
        if repasse.get("parte") == parte:
            repasse["atual"], repasse["motivo"] = calcular(destino, repasse)


def _ainda_aqui(destino: str, repasse: Mapping[str, Any]) -> bool:
    """A página ainda mostra o que o Montador mandou?"""
    estado = st.session_state
    if destino == MOHR:
        enviado = estado.get("mohr_assistente_2d") or {}
        return enviado.get("repasse_id") == repasse.get("id")
    campos = _NA_ESTATICA if destino == ESTATICA else _NA_FADIGA
    valores = repasse.get("valores") or {}
    return all(_perto(estado.get(chave), valores.get(nome)) for nome, chave in campos.items())


def _trazer(destino: str) -> None:
    repasse = repasses().get(destino)
    if not repasse or repasse.get("atual") is None:
        return
    repasse["valores"] = dict(repasse["atual"])
    repasse["dispensado"] = None
    aplicar(
        destino, repasse["valores"], repasse["descricao"], repasse.get("origem_id"), repasse["id"]
    )


def _manter(destino: str, marca: str) -> None:
    repasse = repasses().get(destino)
    if repasse:
        repasse["dispensado"] = marca


def mudancas(antes: Mapping[str, float], depois: Mapping[str, float]) -> list[str]:
    """σx foi de 120 para 135 MPa, e assim por diante: só o que mudou."""
    textos = []
    for nome, (rotulo, unidade) in _ROTULOS.items():
        a, b = antes.get(nome), depois.get(nome)
        if (a is None and b is None) or _perto(a, b):
            continue
        de = "—" if a is None else _numero(a)
        para = "—" if b is None else _numero(b)
        textos.append(f"{rotulo} foi de {de} para {para} {unidade}")
    return textos


def aviso(destino: str) -> None:
    """Na página que recebeu: avisa se o Montador mudou depois do envio, e oferece os números novos."""
    repasse = (st.session_state.get(CHAVE) or {}).get(destino)
    if not isinstance(repasse, Mapping) or not _ainda_aqui(destino, repasse):
        return
    atual = repasse.get("atual")
    if atual is not None and _iguais(atual, repasse.get("valores") or {}):
        return
    marca = _marca(atual)
    if repasse.get("dispensado") == marca:
        return
    if atual is None:
        motivo = repasse.get("motivo") or "a conta ficou sem número"
        texto = f"Estes números vieram do {ORIGEM}, e lá a montagem mudou: {motivo}."
    else:
        texto = (
            f"A montagem do {ORIGEM} mudou depois do envio: "
            + "; ".join(mudancas(repasse.get("valores") or {}, atual))
            + "."
        )
    st.warning(texto, icon=":material/sync_problem:")
    esquerda, direita = st.columns(2)
    esquerda.button(
        "Trazer os números novos",
        key=f"montador_trazer_{destino}",
        on_click=_trazer,
        args=(destino,),
        disabled=atual is None,
        icon=":material/sync:",
        help="Põe aqui os números de agora do Montador. A origem continua a mesma.",
        width="stretch",
    )
    direita.button(
        "Manter os de antes",
        key=f"montador_manter_{destino}",
        on_click=_manter,
        args=(destino, marca),
        help="Fica com os números do envio. O aviso volta se o Montador mudar de novo.",
        width="stretch",
    )
