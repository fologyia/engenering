"""As duas partes do Montador e os desenhos prontos de cada uma: blocos, fios e números de exemplo."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from core import montador_blocos as mb
from core import montador_conjuntos as mc
from core import montador_grandezas as g

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
    valores: Mapping[str, float]  # na base do sistema
    tipos: tuple[str, ...]
    extras: tuple[tuple[str, ...], ...] = ()  # blocos fora da fila: id, tipo
    fios: tuple[tuple[str, str, str, str], ...] = ()
    opcoes: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    conjunto: tuple[tuple[str, ...], str] | None = None  # ids e nome do conjunto

    def grafo(self) -> dict[str, list[dict[str, Any]]]:
        nos, fios = _fila(*self.tipos)
        for id_, tipo in self.extras:
            nos.append({"id": id_, "tipo": tipo, "opcoes": {}})
        fios += [_fio(*fio) for fio in self.fios]
        for no in nos:
            no["opcoes"] = dict(self.opcoes.get(no["id"], {}))
        organizar(nos, fios)
        dados = {"nos": nos, "fios": fios}
        if self.conjunto is not None:
            ids, nome = self.conjunto
            dados = mc.agrupar(dados, ids, nome)
            organizar(dados["nos"], dados["fios"])
        return dados


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
        "Eixo: estática e fadiga",
        "Um conjunto com a seção e os esforços alimenta von Mises e Goodman.",
        "d",
        {
            "M_x": 5e5,
            "M_y": 3e5,
            "T": 2e5,
            "S_y": 350.0,
            "S_ut": 655.0,
            "S_e": 180.0,
            "K_f": 1.0,
            "K_fs": 1.0,
            "n": 2.0,
        },
        ("circular", "flexao", "flexao_y", "torcao", "von_mises", _R),
        (("n7", "goodman"), ("n8", "material")),
        (
            ("n4", "saida", "n7", "entrada"),
            ("n8", "saida", "n5", "material"),
            ("n8", "saida", "n7", "material"),
            ("n7", "condicao", "n6", "condicoes"),
        ),
        opcoes={"n7": {"esforcos": mb.EIXO_GIRANDO}},
        conjunto=(("n1", "n2", "n3", "n4"), "Eixo solicitado"),
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
            "M_m": 0.0,
            "T_a": 0.0,
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

_LINHA = {"D": 0.1, "L": 100.0}
MODELOS_FLUIDOS: tuple[Modelo, ...] = (
    Modelo(
        "Vazão num tubo por gravidade",
        "Quanto passa num tubo com um desnível disponível.",
        "Q",
        {**_LINHA, "K_L": 2.5, "H_d": 5.0},
        ("fluido", "trecho", "perda_local", "carga", _R),
    ),
    Modelo(
        "Diâmetro mínimo do tubo",
        "O menor tubo que leva a vazão com a perda disponível.",
        "D",
        {"Q": 0.01, "L": 100.0, "K_L": 2.5, "H_d": 2.0},
        ("fluido", "trecho", "perda_local", "carga", _R),
    ),
    Modelo(
        "Potência da bomba",
        "Altura estática, perdas e rendimento.",
        "P_m",
        {"Q": 0.01, "D": 0.08, "L": 120.0, "K_L": 6.0, "H_est": 25.0, "Delta_p": 0.0},
        ("fluido", "trecho", "perda_local", "potencia_bomba", _R),
    ),
    Modelo(
        "Altura da bomba",
        "O que a bomba precisa entregar nessa vazão.",
        "H_b",
        {"Q": 0.01, "D": 0.08, "L": 120.0, "K_L": 6.0, "H_est": 25.0, "Delta_p": 0.0},
        ("fluido", "trecho", "perda_local", "altura_bomba", _R),
    ),
    Modelo(
        "Altura máxima de sucção",
        "NPSH: até onde a bomba pode ficar acima do líquido.",
        "z_s",
        {"Q": 0.01, "D": 0.1, "L": 5.0, "K_L": 1.5, "NPSH_r": 3.0},
        ("fluido", "trecho", "perda_local", "npsh", _R),
    ),
    Modelo(
        "Velocidade no tubo",
        "Diâmetro para a velocidade não passar do limite.",
        "D",
        {"Q": 0.01, "L": 10.0, "V_adm": 2.0},
        ("fluido", "trecho", "velocidade", _R),
    ),
    Modelo(
        "Pressão numa profundidade",
        "Fluido parado.",
        "p_h",
        {"p_0": 0.0, "h": 10.0},
        ("fluido", "coluna", _R),
    ),
    Modelo(
        "Força numa comporta",
        "Resultante numa superfície plana.",
        "F_R",
        {"h_c": 2.0, "A": 3.0},
        ("fluido", "forca_plana", _R),
    ),
    Modelo(
        "Empuxo",
        "Volume que sustenta uma carga.",
        "V_d",
        {"F_e": 1000.0},
        ("fluido", "empuxo", _R),
    ),
    Modelo(
        "Arrasto numa peça",
        "Força do vento ou da água sobre um corpo.",
        "F_D",
        {"C_D": 1.2, "A_f": 0.5, "V_r": 10.0},
        ("fluido", "arrasto", _R),
        opcoes={"n1": {"fluido": "Ar a 20 °C"}},
    ),
    Modelo(
        "Medidor de orifício",
        "Vazão pela queda de pressão.",
        "Q",
        {"C_d": 0.6, "D_o": 0.05, "D": 0.1, "Delta_p": 20000.0},
        ("fluido", "medidor", _R),
    ),
    Modelo(
        "Lâmina num canal",
        "Manning em canal retangular.",
        "y_c",
        {"Q": 3.0, "n_m": 0.013, "b_c": 2.0, "S_0": 0.001},
        ("manning", _R),
    ),
    Modelo(
        "Golpe de aríete",
        "Sobrepressão no fechamento rápido.",
        "Delta_p_g",
        {"a_c": 1000.0, "Delta_V": 2.0},
        ("fluido", "golpe", _R),
    ),
)


@dataclass(frozen=True)
class Parte:
    """Uma parte do Montador: mesmo motor, com seus blocos, unidades e modelos."""

    prefixo: str
    dominio: str
    titulo: str
    subtitulo: str
    modulo_id: str
    sistema: g.Sistema
    modelos: tuple[Modelo, ...]
    pagina_da_outra: str
    nome_da_outra: str

    def k(self, nome: str) -> str:
        return f"{self.prefixo}_{nome}"

    @property
    def por_nome(self) -> dict[str, Modelo]:
        return {m.nome: m for m in self.modelos}


PARTE_SOLIDOS = Parte(
    "mf",
    mb.SOLIDOS,
    "Montador de fórmulas",
    "Ligue a seção, os esforços e o critério, e escolha em função do que a equação deve ficar.",
    "montador_formulas",
    g.SISTEMA_SOLIDOS,
    MODELOS,
    "app_pages/montador_fluidos.py",
    "Mecânica dos fluidos",
)
PARTE_FLUIDOS = Parte(
    "mfl",
    mb.FLUIDOS,
    "Montador de fluidos",
    "Ligue o fluido, a tubulação e a verificação, e escolha em função do que a equação deve ficar.",
    "montador_fluidos",
    g.SISTEMA_FLUIDOS,
    MODELOS_FLUIDOS,
    "app_pages/montador_formulas.py",
    "Materiais, estática e fadiga",
)

POR_NOME = {modelo.nome: modelo for modelo in MODELOS}
MODELO_INICIAL = MODELOS[0]
