"""As duas partes do Montador e os desenhos prontos de cada uma: blocos, fios e números de exemplo."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from core import elementos_eixos as ee
from core import montador_blocos as mb
from core import montador_conjuntos as mc
from core import (
    montador_eixo,  # noqa: F401  (registra o eixo com trechos)
    montador_pecas,  # noqa: F401  (registra os blocos de peça)
    montador_processos,  # noqa: F401  (registra a ponte entre térmico e fluidos)
    montador_termico,  # noqa: F401  (registra os blocos do térmico)
)
from core import montador_grandezas as g

_LARGURA = 202
_ALTURA = 124


def organizar(nos: list[dict[str, Any]], fios: list[dict[str, Any]]) -> None:
    """Põe cada bloco na coluna da sua distância até o começo. O mesmo que a prancheta faz.

    O fio que volta para o começo de um laço (o Circuito do térmico) não conta: com ele, as colunas
    cresceriam a cada volta.
    """
    coluna = {no["id"]: 0 for no in nos}
    inicios = {no["id"] for no in nos if no["tipo"] in mb.INICIO_DE_LACO}
    for _ in nos:
        for fio in fios:
            if fio["para"] in inicios:
                continue
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
        saida = mb.portas_de(a["tipo"], {})[1][0]
        entrada = mb.portas_de(b["tipo"], {})[0][0]
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
            if no["tipo"] == mb.FORMULA or no["tipo"] in mb.PORTAS_VARIAVEIS:
                no["portas"] = mb.portas_para_a_tela(no["tipo"], no["opcoes"])
        organizar(nos, fios)
        dados = {"nos": nos, "fios": fios}
        if self.conjunto is not None:
            ids, nome = self.conjunto
            dados = mc.agrupar(dados, ids, nome)
            organizar(dados["nos"], dados["fios"])
        return dados


_R = mb.RESULTADO
#: Uma engrenagem de 15 kW a 1450 rpm, com primitivo de 80 mm: os modelos de peça partem dela.
_ENGRENAGEM = {"P": 15e6, "n_rot": 1450.0, "d_g": 80.0}
_ACO_DO_EIXO = {"S_y": 420.0, "S_ut": 690.0, "E": 200000.0, "G": 80000.0}
_DICA_DA_FORMULA = "Digite a conta no inspetor: as letras viram bolinhas e a unidade é conferida."

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
    Modelo(
        "Eixo em fadiga, com Marin e entalhe",
        "S_e pelos fatores de Marin, K_f do ressalto e o escoamento no primeiro ciclo.",
        "d",
        {
            "M_x": 2e5,
            "T": 1.5e5,
            "S_y": 420.0,
            "S_ut": 690.0,
            "D_r": 60.0,
            "r_e": 3.0,
            "n": 2.0,
        },
        ("circular", "flexao", "torcao", "goodman", _R),
        (("m1", "material"), ("m2", "limite_fadiga"), ("m3", "entalhe")),
        (
            ("m1", "saida", "n4", "material"),
            ("m1", "saida", "m2", "material"),
            ("m1", "saida", "m3", "material"),
            ("m2", "se", "n4", "se"),
            ("m3", "kf", "n4", "kf"),
            ("m3", "kfs", "n4", "kfs"),
        ),
        {
            "n4": {"esforcos": mb.EIXO_GIRANDO},
            "m2": {"confiabilidade": "90 %"},
            "m3": {"entalhe": ee.ENTALHE_RESSALTO},
        },
    ),
    Modelo(
        "Eixo com engrenagem",
        "A engrenagem dá F_r e F_t, cada uma num plano, e o eixo sai por fadiga com o rasgo.",
        "d",
        {**_ENGRENAGEM, **_ACO_DO_EIXO, "a_m": 100.0, "L": 300.0, "n": 2.0},
        ("circular", "flexao", "flexao_y", "torcao", "goodman", _R),
        (
            ("e1", "engrenagem"),
            ("v1", "biapoiada_fora"),
            ("v2", "biapoiada_fora"),
            ("m1", "material"),
            ("m2", "limite_fadiga"),
            ("m3", "entalhe"),
        ),
        (
            ("e1", "F_r", "v1", "F"),
            ("e1", "F_t", "v2", "F"),
            ("v1", "M", "n2", "valor"),
            ("v2", "M", "n3", "valor"),
            ("e1", "T", "n4", "valor"),
            ("m1", "saida", "n5", "material"),
            ("m1", "saida", "m2", "material"),
            ("m1", "saida", "m3", "material"),
            ("m2", "se", "n5", "se"),
            ("m3", "kf", "n5", "kf"),
            ("m3", "kfs", "n5", "kfs"),
        ),
        {
            "n5": {"esforcos": mb.EIXO_GIRANDO},
            "m2": {"confiabilidade": "90 %"},
            "m3": {"entalhe": ee.ENTALHE_CHAVETA},
        },
    ),
    Modelo(
        "Rigidez do eixo",
        "Inclinação no mancal, com os dois planos da engrenagem, e rotação crítica com a peça.",
        "d",
        {**_ENGRENAGEM, **_ACO_DO_EIXO, "a_m": 100.0, "L": 300.0, "m_p": 3e-3},
        ("circular", "inclinacao", _R),
        (
            ("e1", "engrenagem"),
            ("v1", "biapoiada_fora"),
            ("v2", "biapoiada_fora"),
            ("m1", "material"),
            ("c1", "rotacao_critica"),
        ),
        (
            ("e1", "F_r", "v1", "F"),
            ("e1", "F_t", "v2", "F"),
            ("v1", "giro", "n2", "giro"),
            ("v2", "giro", "n2", "giro_2"),
            ("m1", "saida", "n2", "material"),
            ("n1", "saida", "c1", "entrada"),
            ("m1", "saida", "c1", "material"),
            ("c1", "condicao", "n3", "condicoes"),
        ),
        {"c1": {"massas": "Eixo e uma peça entre os mancais"}},
    ),
    Modelo(
        "Polia em balanço",
        "A polia fora dos mancais: o momento maior fica no mancal, e a reação passa da força.",
        "d",
        {
            "P": 7.5e6,
            "n_rot": 1750.0,
            "d_pol": 120.0,
            "c_b": 80.0,
            "L": 250.0,
            "S_y": 420.0,
            "n": 2.0,
        },
        ("circular", "flexao", "torcao", "von_mises", _R),
        (("p1", "polia"), ("v1", "biapoiada_balanco")),
        (
            ("p1", "F", "v1", "F"),
            ("v1", "M", "n2", "valor"),
            ("p1", "T", "n3", "valor"),
        ),
    ),
    Modelo(
        "Par de engrenagens: módulo do dente",
        "Lewis no pinhão e na coroa e contato no flanco: o menor módulo para essa largura.",
        "m_n",
        {
            "P": 15e6,
            "n_rot": 1450.0,
            "z_1": 25.0,
            "z_2": 76.0,
            "b_g": 50.0,
            "E": 205000.0,
            "n": 1.5,
        },
        (_R,),
        (("p1", "par_engrenagens"),),
        (("p1", "condicao", "n1", "condicoes"),),
    ),
    Modelo(
        "Pinhão cônico em balanço",
        "As forças da cônica no eixo com trechos: a axial vai ao mancal A, com o binário no raio "
        "médio r_m que a cônica mostra.",
        "d",
        {
            **_ACO_DO_EIXO,
            "P": 7.5e6,
            "n_rot": 1450.0,
            "m_c": 4.0,
            "z_c1": 18.0,
            "z_c2": 36.0,
            "b_c": 24.0,
            "n": 1.5,
        },
        ("eixo_trechos", _R),
        (("c1", "engrenagem_conica"), ("m1", "material")),
        (
            ("c1", "F_r", "n1", "v1"),
            ("c1", "F_t", "n1", "h1"),
            ("c1", "T", "n1", "t1"),
            ("c1", "F_a", "n1", "a1"),
            ("m1", "saida", "n1", "material"),
        ),
        {
            "n1": {
                "trechos": '[{"nome": "Assento do pinhão", "comprimento": 40.0, "relacao": 1.0, "entalhe": "Rasgo de chaveta (fresa de topo)", "raio": 0.05}, {"nome": "Assento do mancal A", "comprimento": 25.0, "relacao": 1.2, "entalhe": "Eixo liso", "raio": 0.03}, {"nome": "Corpo", "comprimento": 105.0, "relacao": 1.4, "entalhe": "Eixo liso", "raio": 0.03}, {"nome": "Assento do mancal B", "comprimento": 25.0, "relacao": 1.2, "entalhe": "Eixo liso", "raio": 0.03}, {"nome": "Ponta do acoplamento", "comprimento": 40.0, "relacao": 1.0, "entalhe": "Rasgo de chaveta (fresa de topo)", "raio": 0.02}]',
                "elementos": '[{"nome": "Pinhão cônico", "x": 20.0, "funcao": "Carga", "vertical": "+", "horizontal": "+", "torque": "Sai", "axial": true, "raio": 30.63, "binario": "+", "massa": 1.5, "engrenagem": false}, {"nome": "Mancal A", "x": 52.5, "funcao": "Mancal A"}, {"nome": "Mancal B", "x": 182.5, "funcao": "Mancal B"}, {"nome": "Acoplamento", "x": 215.0, "funcao": "Carga", "torque": "Entra", "massa": 1.0}]',
            }
        },
    ),
    Modelo(
        "Chaveta: comprimento mínimo",
        "O torque da potência passa pela chaveta da DIN 6885 do diâmetro do eixo.",
        "L_ch",
        {"P": 15e6, "n_rot": 1450.0, "d": 40.0, "S_y": 420.0, "S_y_cubo": 250.0, "n": 2.0},
        ("chaveta", _R),
        (("p1", "potencia"),),
        (("p1", "T", "n1", "T"),),
    ),
    Modelo(
        "Fuso: diâmetro mínimo",
        "Tr com passo de 7 mm levantando 20 kN: corpo, filetes, porca e flambagem do fuso.",
        "d_fu",
        {
            "F_fu": 20e3,
            "p_fu": 7.0,
            "S_y": 420.0,
            "S_y_porca": 200.0,
            "n": 2.0,
            "L_fu": 800.0,
            "E": 205000.0,
        },
        (_R,),
        (("f1", "fuso"),),
        (("f1", "condicao", "n1", "condicoes"),),
    ),
    Modelo(
        "Cubo prensado: comprimento do ajuste",
        "Quanto do cubo precisa ficar apertado no eixo para segurar o torque sem chaveta.",
        "L_aj",
        {
            "T": 4e5,
            "d": 60.0,
            "D_cubo": 110.0,
            "S_y": 420.0,
            "S_y_cubo": 300.0,
            "E": 200000.0,
            "n": 1.5,
            "F_ac": 0.0,
        },
        ("cubo_prensado", _R),
    ),
    Modelo(
        "Rolamento: capacidade C",
        "A reação do mancal vai para o rolamento, e a vida em horas dá o C do catálogo.",
        "C_din",
        {"F": 5000.0, "a_m": 100.0, "L": 300.0, "n_rot": 1450.0, "C_0": 20000.0},
        ("rolamento", _R),
        (("v1", "biapoiada_fora"),),
        (("v1", "R", "n1", "R"),),
    ),
    Modelo(
        "Eixo com trechos",
        "O eixo inteiro: ombros, rasgos, mancais e a engrenagem, com a seção que quebra primeiro.",
        "d",
        {**_ENGRENAGEM, **_ACO_DO_EIXO, "n": 1.5},
        ("eixo_trechos", _R),
        (("e1", "engrenagem"), ("m1", "material")),
        (
            ("e1", "F_r", "n1", "v1"),
            ("e1", "F_t", "n1", "h1"),
            ("e1", "T", "n1", "t1"),
            ("m1", "saida", "n1", "material"),
        ),
    ),
    Modelo(
        "Fórmula própria",
        _DICA_DA_FORMULA,
        "d",
        {"M_x": 5e5, "S_y": 250.0, "n": 2.0},
        (_R,),
        (("n2", mb.FORMULA),),
        (("n2", "condicao", "n1", "condicoes"),),
        {"n2": {"texto": "32*M_x/(pi*d^3) <= S_y/n", "sistema": g.SISTEMA_SOLIDOS.chave}},
    ),
)

_LINHA = {"D": 0.1, "L": 100.0}
_BOMBA = {"D": 0.1, "L": 200.0, "K_L": 8.0, "H_est": 15.0, "Delta_p": 0.0}
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
        "Fórmula própria",
        _DICA_DA_FORMULA,
        "V",
        {"H_d": 5.0},
        (_R,),
        (("n2", mb.FORMULA),),
        (("n2", "condicao", "n1", "condicoes"),),
        {"n2": {"texto": "V^2/(2*g) <= H_d", "sistema": g.SISTEMA_FLUIDOS.chave}},
    ),
    Modelo(
        "Ponto de operação da bomba",
        "Onde a curva da bomba cruza a do sistema: a vazão que a bomba entrega de verdade.",
        "Q",
        {**_BOMBA, "H_0": 40.0, "a_b": 400000.0},
        ("fluido", "trecho", "perda_local", "curva_bomba", _R),
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


_LIQUIDO_NO_CONDENSADOR = "Sai líquido saturado (condensador)"
_VAPOR_NO_EVAPORADOR = "Sai vapor saturado (evaporador)"
#: Ciclo Rankine ideal de Çengel e Boles, Exemplo 10-1: 3 MPa e 350 °C na turbina, 75 kPa no
#: condensador. O livro dá 26,0 % de rendimento.
_RANKINE = {
    "m_c": 1.0,
    "p_b": 3e6,
    "eta_b": 1.0,
    "T_s": 623.15,
    "Dp_tc": 0.0,
    "p_tb": 75e3,
    "eta_tb": 1.0,
    "Dp_tc_2": 0.0,
}
#: Refrigeração ideal com R134a de Çengel e Boles, Exemplo 11-1: 0,14 e 0,8 MPa, 0,05 kg/s. O livro
#: dá COP de 3,97.
_REFRIGERACAO = {"m_c": 0.05, "p_c": 8e5, "eta_c": 1.0, "Dp_tc": 0.0, "p_vl": 1.4e5, "Dp_tc_2": 0.0}
MODELOS_TERMICOS: tuple[Modelo, ...] = (
    Modelo(
        "Aquecer água: vazão pelo calor",
        "Quanta água um aquecedor de 200 kW leva de 20 °C a 60 °C.",
        "mdot",
        {"T": 293.15, "p": 3e5, "T_s": 333.15, "Dp_tc": 0.0, "Q_ped": 200e3},
        (),
        (("e1", "estado"), ("q1", "troca_de_calor"), ("c1", "calor_pedido"), ("r1", _R)),
        (
            ("e1", "saida", "q1", "entrada"),
            ("q1", "calor", "c1", "calores"),
            ("c1", "condicao", "r1", "condicoes"),
        ),
        {"e1": {"fluido": "Água"}},
    ),
    Modelo(
        "Compressor de ar: pressão máxima",
        "Até que pressão o ar sai do compressor abaixo de 200 °C.",
        "p_c",
        {"T": 298.15, "p": 1e5, "mdot": 1.0, "eta_c": 0.8, "T_max": 473.15},
        (),
        (("e1", "estado"), ("k1", "compressor"), ("t1", "temperatura_maxima"), ("r1", _R)),
        (
            ("e1", "saida", "k1", "entrada"),
            ("k1", "saida", "t1", "entrada"),
            ("t1", "condicao", "r1", "condicoes"),
        ),
        {"e1": {"fluido": "Ar seco"}},
    ),
    Modelo(
        "Turbina a vapor: pressão de saída",
        "A menor pressão de saída com o vapor ainda seco o bastante para as palhetas.",
        "p_tb",
        {"T": 623.15, "p": 3e6, "mdot": 1.0, "eta_tb": 0.85, "x_min": 0.88},
        (),
        (("e1", "estado"), ("t1", "turbina"), ("x1", "titulo_minimo"), ("r1", _R)),
        (
            ("e1", "saida", "t1", "entrada"),
            ("t1", "saida", "x1", "entrada"),
            ("x1", "condicao", "r1", "condicoes"),
        ),
        {"e1": {"fluido": "Água"}},
    ),
    Modelo(
        "Misturar água quente e fria",
        "Quanta água fria baixa 1 kg/s de água a 80 °C para no máximo 45 °C.",
        "mdot_2",
        {"T": 353.15, "p": 3e5, "mdot": 1.0, "T_2": 288.15, "p_2": 3e5, "T_max": 318.15},
        (),
        (
            ("e1", "estado"),
            ("e2", "estado"),
            ("m1", "misturador"),
            ("t1", "temperatura_maxima"),
            ("r1", _R),
        ),
        (
            ("e1", "saida", "m1", "a"),
            ("e2", "saida", "m1", "b"),
            ("m1", "saida", "t1", "entrada"),
            ("t1", "condicao", "r1", "condicoes"),
        ),
        {"e1": {"fluido": "Água"}, "e2": {"fluido": "Água"}},
    ),
    Modelo(
        "Ciclo Rankine simples",
        "Bomba, caldeira, turbina e condensador em laço: o rendimento térmico do ciclo.",
        "eta_t",
        _RANKINE,
        (),
        (
            ("c1", "circuito"),
            ("b1", "bomba_termica"),
            ("q1", "troca_de_calor"),
            ("t1", "turbina"),
            ("q2", "troca_de_calor"),
            ("n1", "rendimento_ciclo"),
            ("r1", _R),
        ),
        (
            ("c1", "saida", "b1", "entrada"),
            ("b1", "saida", "q1", "entrada"),
            ("q1", "saida", "t1", "entrada"),
            ("t1", "saida", "q2", "entrada"),
            ("q2", "saida", "c1", "entrada"),
            ("t1", "potencia", "n1", "produzidos"),
            ("b1", "potencia", "n1", "consumidos"),
            ("q1", "calor", "n1", "recebidos"),
            ("n1", "condicao", "r1", "condicoes"),
        ),
        {"c1": {"fluido": "Água"}, "q2": {"saida": _LIQUIDO_NO_CONDENSADOR}},
    ),
    Modelo(
        "Refrigeração por compressão (R134a)",
        "Compressor, condensador, válvula e evaporador em laço: o COP do ciclo.",
        "COP",
        _REFRIGERACAO,
        (),
        (
            ("c1", "circuito"),
            ("k1", "compressor"),
            ("q1", "troca_de_calor"),
            ("v1", "valvula"),
            ("q2", "troca_de_calor"),
            ("n1", "cop"),
            ("r1", _R),
        ),
        (
            ("c1", "saida", "k1", "entrada"),
            ("k1", "saida", "q1", "entrada"),
            ("q1", "saida", "v1", "entrada"),
            ("v1", "saida", "q2", "entrada"),
            ("q2", "saida", "c1", "entrada"),
            ("q2", "calor", "n1", "uteis"),
            ("k1", "potencia", "n1", "consumidos"),
            ("n1", "condicao", "r1", "condicoes"),
        ),
        {
            "c1": {"fluido": "R134a"},
            "q1": {"saida": _LIQUIDO_NO_CONDENSADOR},
            "q2": {"saida": _VAPOR_NO_EVAPORADOR},
        },
    ),
    Modelo(
        "Fórmula própria",
        _DICA_DA_FORMULA,
        "Q_c",
        {"mdot": 2.0, "c_p": 4180.0, "dT": 15.0},
        (_R,),
        (("n2", mb.FORMULA),),
        (("n2", "condicao", "n1", "condicoes"),),
        {"n2": {"texto": "Q_c = mdot*c_p*dT", "sistema": g.SISTEMA_TERMICO.chave}},
    ),
)


MODELOS_DE_PROCESSOS: tuple[Modelo, ...] = (
    Modelo(
        "Resfriar com água: vazão e diâmetro do tubo",
        "200 kW tirados com água de 30 °C a 40 °C: o calor dá a vazão, e a velocidade dá o tubo.",
        "D",
        {
            "T": 303.15,
            "p": 3e5,
            "T_s": 313.15,
            "Dp_tc": 0.0,
            "Q_ped": 200e3,
            "L": 150.0,
            "V_adm": 2.0,
        },
        (),
        (
            ("e1", "estado"),
            ("q1", "troca_de_calor"),
            ("c1", "calor_pedido"),
            ("l1", "linha_da_corrente"),
            ("t1", "trecho"),
            ("v1", "velocidade"),
            ("r1", _R),
        ),
        (
            ("e1", "saida", "q1", "entrada"),
            ("q1", "calor", "c1", "calores"),
            ("e1", "saida", "l1", "entrada"),
            ("l1", "saida", "t1", "entrada"),
            ("t1", "saida", "v1", "entrada"),
            ("c1", "condicao", "r1", "condicoes"),
            ("v1", "condicao", "r1", "condicoes"),
        ),
        {"e1": {"fluido": "Água"}},
    ),
    Modelo(
        "Bomba de água quente: altura de sucção",
        "Até que altura a bomba aspira água a 80 °C sem cavitar, com a pressão de vapor do estado.",
        "z_s",
        {
            "T": 353.15,
            "p": 101325.0,
            "mdot": 5.0,
            "D": 0.08,
            "L": 6.0,
            "K_L": 3.0,
            "NPSH_r": 3.0,
        },
        (),
        (
            ("e1", "estado"),
            ("l1", "linha_da_corrente"),
            ("t1", "trecho"),
            ("k1", "perda_local"),
            ("n1", "npsh"),
            ("r1", _R),
        ),
        (
            ("e1", "saida", "l1", "entrada"),
            ("l1", "saida", "t1", "entrada"),
            ("t1", "saida", "k1", "entrada"),
            ("k1", "saida", "n1", "entrada"),
            ("n1", "condicao", "r1", "condicoes"),
        ),
        {"e1": {"fluido": "Água"}},
    ),
    Modelo(
        "Da bomba à caldeira: pressão que a bomba precisa",
        "A pressão na saída da bomba para a água chegar à caldeira com 3 MPa, depois do tubo.",
        "p_b",
        {
            "p": 75e3,
            "mdot": 2.0,
            "eta_b": 0.75,
            "D": 0.04,
            "L": 80.0,
            "K_L": 6.0,
            "Delta_z": 15.0,
            "p_inf": 3e6,
        },
        (),
        (
            ("e1", "estado"),
            ("b1", "bomba_termica"),
            ("l1", "linha_da_corrente"),
            ("t1", "trecho"),
            ("k1", "perda_local"),
            ("d1", "corrente_depois_da_linha"),
            ("p1", "pressao_minima"),
            ("r1", _R),
        ),
        (
            ("e1", "saida", "b1", "entrada"),
            ("b1", "saida", "l1", "entrada"),
            ("l1", "saida", "t1", "entrada"),
            ("t1", "saida", "k1", "entrada"),
            ("b1", "saida", "d1", "entrada"),
            ("k1", "saida", "d1", "linha"),
            ("d1", "saida", "p1", "entrada"),
            ("p1", "condicao", "r1", "condicoes"),
        ),
        {"e1": {"fluido": "Água", "como": "Líquido saturado, pela pressão"}},
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
    #: Os tipos de fio que podem fechar um laço na prancheta, como a corrente de um ciclo.
    lacos: tuple[str, ...] = ()

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
    "o Montador de fluidos",
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
    "o Montador de fórmulas",
)

PARTE_TERMICA = Parte(
    "mte",
    mb.TERMICO,
    "Montador térmico",
    "Ligue o estado do fluido, os equipamentos e a verificação, e escolha em função do que a "
    "equação deve ficar.",
    "montador_termico",
    g.SISTEMA_TERMICO,
    MODELOS_TERMICOS,
    "app_pages/montador_fluidos.py",
    "o Montador de fluidos",
    lacos=(mb.CORRENTE,),
)

PARTE_PROCESSOS = Parte(
    "mpr",
    mb.PROCESSOS,
    "Montador de processos",
    "Fluidos e térmico no mesmo desenho: o estado do fluido vira a linha, e a perda do tubo volta "
    "para a corrente.",
    "montador_processos",
    g.SISTEMA_PROCESSOS,
    MODELOS_DE_PROCESSOS,
    "app_pages/montador_termico.py",
    "o Montador térmico",
    lacos=(mb.CORRENTE,),
)

POR_NOME = {modelo.nome: modelo for modelo in MODELOS}
MODELO_INICIAL = MODELOS[0]
