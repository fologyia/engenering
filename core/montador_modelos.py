"""Desenhos prontos do montador de fórmulas: blocos, fios, a letra pedida e números de exemplo."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from core import montador_blocos as mb

_LARGURA = 202
_ALTURA = 124


def organizar(nos: list[dict[str, Any]], fios: list[dict[str, Any]]) -> None:
    """Põe cada bloco na coluna da sua distância até o começo. O mesmo que a prancheta faz."""
    coluna = {no["id"]: 0 for no in nos}
    for _ in nos:
        for fio in fios:
            if fio["de"] in coluna and fio["para"] in coluna:
                coluna[fio["para"]] = max(coluna[fio["para"]], coluna[fio["de"]] + 1)
    linhas: dict[int, int] = {}
    for no in nos:
        c = coluna[no["id"]]
        no["x"] = 30 + c * _LARGURA
        no["y"] = 30 + linhas.get(c, 0) * _ALTURA
        linhas[c] = linhas.get(c, 0) + 1


def _fio(de: str, saida: str, para: str, entrada: str) -> dict[str, str]:
    return {"de": de, "saida": saida, "para": para, "entrada": entrada}


def _fila(*tipos: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Blocos em fila: cada um entrega a seção ao próximo, e o último critério ao resultado."""
    nos: list[dict[str, Any]] = [
        {"id": f"n{i + 1}", "tipo": tipo, "opcoes": {}} for i, tipo in enumerate(tipos)
    ]
    fios = []
    for a, b in zip(nos, nos[1:], strict=False):
        saida = mb.POR_CHAVE[a["tipo"]].saidas[0]
        entrada = mb.POR_CHAVE[b["tipo"]].entradas[0]
        fios.append(_fio(a["id"], saida.chave, b["id"], entrada.chave))
    return nos, fios


@dataclass(frozen=True)
class Modelo:
    nome: str
    dica: str
    alvo: str
    valores: Mapping[str, float]  # na base N, mm, MPa
    tipos: tuple[str, ...]
    extras: tuple[tuple[str, ...], ...] = ()  # blocos fora da fila: id, tipo
    fios: tuple[tuple[str, str, str, str], ...] = ()
    opcoes: Mapping[str, Mapping[str, str]] = field(default_factory=dict)

    def grafo(self) -> dict[str, list[dict[str, Any]]]:
        nos, fios = _fila(*self.tipos)
        for id_, tipo in self.extras:
            nos.append({"id": id_, "tipo": tipo, "opcoes": {}})
        fios += [_fio(*fio) for fio in self.fios]
        for no in nos:
            no["opcoes"] = dict(self.opcoes.get(no["id"], {}))
        organizar(nos, fios)
        return {"nos": nos, "fios": fios}


_R = mb.RESULTADO

MODELOS: tuple[Modelo, ...] = (
    Modelo(
        "Base conhecida: achar a altura",
        "Seção retangular com flexão e cortante, isolando h.",
        "h",
        {"b": 50.0, "M_x": 2e6, "V_y": 1e4, "S_y": 250.0, "n": 1.5},
        ("retangular", "flexao", "cortante", "von_mises", _R),
    ),
    Modelo(
        "Eixo com flexão e torção",
        "A fórmula clássica do diâmetro por von Mises.",
        "d",
        {"M_x": 5e5, "T": 3e5, "S_y": 350.0, "n": 2.0},
        ("circular", "flexao", "torcao", "von_mises", _R),
    ),
    Modelo(
        "Cortante e torção",
        "Seção retangular: os dois somam na linha neutra.",
        "h",
        {"b": 30.0, "V_y": 5e3, "T": 2e5, "S_y": 250.0, "n": 1.5},
        ("retangular", "cortante", "torcao", "von_mises", _R),
    ),
    Modelo(
        "Momento que a seção aguenta",
        "A mesma conta do eixo, deixando em função do momento.",
        "M_x",
        {"d": 40.0, "T": 3e5, "S_y": 350.0, "n": 2.0},
        ("circular", "flexao", "torcao", "von_mises", _R),
    ),
    Modelo(
        "Força máxima num braço",
        "Força com braço em XX, somando a cortante dela: acha a maior força.",
        "F_xx",
        {"b": 40.0, "h": 80.0, "d_xx": 500.0, "S_y": 250.0, "n": 1.5},
        ("retangular", "flexao", "von_mises", _R),
        opcoes={"n2": {"entrada": mb.FORCA_COM_CORTANTE}},
    ),
    Modelo(
        "Distância máxima de uma força",
        "A mesma conta, deixando em função do braço.",
        "d_xx",
        {"b": 40.0, "h": 80.0, "F_xx": 5e3, "S_y": 250.0, "n": 1.5},
        ("retangular", "flexao", "von_mises", _R),
        opcoes={"n2": {"entrada": mb.FORCA_COM_CORTANTE}},
    ),
    Modelo(
        "Flexão em XX e YY",
        "Flexão oblíqua: o canto da seção soma os dois momentos.",
        "M_y",
        {"b": 50.0, "h": 100.0, "M_x": 5e6, "S_y": 250.0, "n": 1.5},
        ("retangular", "flexao", "flexao_y", "von_mises", _R),
    ),
    Modelo(
        "Eixo com momento em XX e YY",
        "Na seção redonda os momentos se compõem: √(M_x² + M_y²).",
        "d",
        {"M_x": 5e5, "M_y": 3e5, "T": 2e5, "S_y": 350.0, "n": 2.0},
        ("circular", "flexao", "flexao_y", "torcao", "von_mises", _R),
    ),
    Modelo(
        "Viga: resistência e flecha",
        "Biapoiada com carga no meio. Mostra se manda a tensão ou a flecha.",
        "h",
        {"b": 50.0, "F": 1e4, "L": 3000.0, "S_y": 250.0, "n": 1.5, "r_delta": 300.0},
        ("retangular", "flexao", "cortante", "von_mises", _R),
        (("n6", "biapoiada_central"), ("n7", "flecha")),
        (
            ("n6", "M", "n2", "valor"),
            ("n6", "V", "n3", "valor"),
            ("n1", "saida", "n7", "entrada"),
            ("n6", "flecha", "n7", "flecha"),
            ("n7", "condicao", "n5", "condicoes"),
        ),
    ),
    Modelo(
        "Eixo pela potência",
        "O torque vem da potência e da rotação, e entra o giro por torção.",
        "d",
        {"P": 1e7, "n_rot": 1500.0, "S_y": 350.0, "n": 2.0, "L": 500.0, "phi_adm": 0.00873},
        ("circular", "torcao", "von_mises", _R),
        (("n5", "potencia"), ("n6", "giro")),
        (
            ("n5", "T", "n2", "valor"),
            ("n1", "saida", "n6", "entrada"),
            ("n5", "T", "n6", "valor"),
            ("n6", "condicao", "n4", "condicoes"),
        ),
    ),
    Modelo(
        "Eixo em fadiga",
        "DE-Goodman, com momento alternado e torque constante.",
        "d",
        {
            "M_a": 1.4e5,
            "M_m": 1e-6,
            "T_a": 1e-6,
            "T_m": 1.2e5,
            "S_e": 195.0,
            "S_ut": 735.0,
            "K_f": 1.7,
            "K_fs": 1.5,
            "n": 1.5,
        },
        ("circular", "goodman", _R),
    ),
    Modelo(
        "Coluna em compressão",
        "Flambagem de Euler na inércia fraca.",
        "d",
        {"N": 2e4, "L": 2000.0, "n": 2.0},
        ("circular", "flambagem", _R),
    ),
    Modelo(
        "Tubo sob pressão",
        "Parede fina com estado biaxial, isolando a pressão.",
        "p",
        {"d": 100.0, "t": 2.0, "S_y": 250.0, "n": 2.0},
        ("tubo_parede", "pressao_interna", "von_mises", _R),
    ),
)

POR_NOME = {modelo.nome: modelo for modelo in MODELOS}
MODELO_INICIAL = MODELOS[0]
