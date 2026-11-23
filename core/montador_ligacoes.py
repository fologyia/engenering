"""Pinos e chapas no Montador: o pino ao corte e a chapa com furo, em letras.

As contas são as do Cálculo de peças (``core/elementos_pinos.py``, ``calcular_pinos``, e
``core/elementos_estatica.py``, ``calcular_chapa``), escritas em letras: o Montador e o Cálculo de
peças têm de dar o mesmo número (os testes conferem). O momento no pino sai do equilíbrio das chapas
alternadas, que não tem forma fechada para qualquer número de planos: entra como a função
``BracoDoPino`` (M/V), que cresce na mesma proporção da força.

Os blocos entram no catálogo por ``montador_blocos.registrar``, como os de peças do eixo.
"""

from __future__ import annotations

from typing import Any

import sympy as sp

from core import montador_blocos as mb
from core import montador_grandezas as g
from core.montador_blocos import (
    CONDICAO,
    GRUPO_LIGACOES,
    MATERIAL,
    VALOR,
    Bloco,
    Condicao,
    Contexto,
    Opcao,
    Porta,
)
from core.montador_funcoes import BracoDoPino
from core.montador_grandezas import FORCA, MEDIDA, PURO, TENSAO, Grandeza
from core.montador_secoes import Validade

_FATOR_CORTE = sp.Rational(577, 1000)  # 1/√3, como no Cálculo de peças

F_LIGACAO = Grandeza(
    "F_lig",
    "F_lig",
    "Força na ligação",
    FORCA,
    "A força total que a ligação passa adiante, somando todos os pinos.",
    zero_ok=True,
)
N_PINOS = Grandeza(
    "n_pi",
    "n_pi",
    "Número de pinos",
    PURO,
    "Quantos pinos dividem a força, por igual.",
    1.0,
    minimo=1.0,
)
D_PINO = Grandeza("d_p", "d_p", "Diâmetro do pino", MEDIDA, "O diâmetro do pino, igual ao do furo.")
T_PONTA = Grandeza(
    "t_a",
    "t_a",
    "Espessura das chapas das pontas",
    MEDIDA,
    "As duas chapas de fora, a que encosta na cabeça e a do outro lado.",
)
T_DENTRO = Grandeza(
    "t_b",
    "t_b",
    "Espessura das chapas de dentro",
    MEDIDA,
    "As chapas entre dois planos de corte. Em corte simples não há.",
)
FOLGA = Grandeza(
    "c_f",
    "c_f",
    "Folga entre as chapas",
    MEDIDA,
    "O vão entre uma chapa e a próxima, ao longo do pino. Folga grande aumenta a flexão.",
    0.0,
    zero_ok=True,
)
LARGURA_CHAPA = Grandeza(
    "w_c",
    "w_c",
    "Largura da chapa",
    MEDIDA,
    "A largura da chapa na seção do furo, de borda a borda.",
)
BORDA = Grandeza(
    "e_c",
    "e_c",
    "Distância do furo à borda",
    MEDIDA,
    "Do centro do furo até a borda da chapa, na direção da força.",
)
SY_CHAPA = Grandeza(
    "S_y_c",
    "S_y,c",
    "Escoamento da chapa",
    TENSAO,
    "Aço ASTM A36: 250 MPa. ASTM A572 grau 50: 345 MPa.",
)
T_CHAPA = Grandeza("t_c", "t_c", "Espessura da chapa", MEDIDA, "A espessura da chapa furada.")
D_FURO = Grandeza("d_f", "d_f", "Diâmetro do furo", MEDIDA, "O diâmetro de cada furo da seção.")
N_FUROS = Grandeza(
    "n_f",
    "n_f",
    "Furos na mesma seção",
    PURO,
    "Quantos furos cortam a mesma seção transversal da chapa.",
    1.0,
    minimo=1.0,
)

_ENTRA_FORCA = Porta("F_lig", "F", VALOR, g.FORCA)
_ENTRA_D = Porta("d_p", "d", VALOR, g.MEDIDA)
_MATERIAL = Porta("material", "Material", MATERIAL)
_SAI_CONDICAO = Porta("condicao", "Condição", CONDICAO)

PLANOS = tuple(str(n) for n in range(1, 7))
_OPCAO_PLANOS = Opcao(
    "planos",
    "Planos de corte",
    "Corte simples é 1 plano (duas chapas); corte duplo, 2 (garfo com a chapa no meio). Cada plano "
    "leva a mesma parte da força, e a chapa de dentro soma dois planos.",
    PLANOS,
    "2",
)


def _escoamento(c: Contexto) -> sp.Expr:
    material = c.material()
    return material.sy if material else c.letra(g.SY, fixa=True)


def _pino(c: Contexto) -> dict[str, Any]:
    planos = int(c.opcoes.get("planos", "2"))
    forca = c.letra(F_LIGACAO, "F_lig")
    pinos = c.letra(N_PINOS, fixa=True)
    d = c.letra(D_PINO, "d_p")
    a = c.letra(T_PONTA)
    b = c.letra(T_DENTRO) if planos > 1 else a  # em corte simples não há chapa de dentro
    folga = c.letra(FOLGA, fixa=True)
    w = c.letra(LARGURA_CHAPA)
    e = c.letra(BORDA)
    sy = _escoamento(c)
    sy_chapa = c.letra(SY_CHAPA, fixa=True)
    n = c.letra(g.FS, fixa=True)

    v = forca / (pinos * planos)  # um plano de um pino
    area = sp.pi * d**2 / 4
    modulo = sp.pi * d**3 / 32
    tau_max = sp.Rational(4, 3) * v / area
    sigma = v * BracoDoPino(planos, a, b, folga) / modulo
    lim_sigma = sy / n
    lim_tau = _FATOR_CORTE * sy / n
    contato = sy_chapa / n
    corte_na_chapa = _FATOR_CORTE * sy_chapa / n
    feitas = (
        Validade(w - d, "A largura da chapa deve ser maior que o diâmetro do furo."),
        Validade(
            e - d / 2, "O furo precisa ficar dentro da chapa: a distância à borda passa de d/2."
        ),
    )
    condicoes = [
        Condicao("Cisalhamento no pino", "Pino", tau_max, lim_tau, "\\tau_{máx}", validade=feitas),
        Condicao("Flexão no pino", "Pino", sigma, lim_sigma, "\\sigma_{p}", validade=feitas),
        Condicao(
            "Flexão com cortante",
            "Pino",
            (sigma / lim_sigma) ** 2 + (v / area / lim_tau) ** 2,
            sp.S.One,
            "\\left(\\frac{\\sigma}{\\sigma_{adm}}\\right)^2+\\left(\\frac{\\tau_{méd}}{\\tau_{adm}}\\right)^2",
            validade=feitas,
        ),
        Condicao(
            "Esmagamento na chapa da ponta",
            "Chapa",
            v / (d * a),
            contato,
            "p_{a}",
            validade=feitas,
        ),
    ]
    # A chapa de dentro leva dois planos; na ponta, um. O rasgamento e a seção líquida valem na que
    # tem mais tensão, e cada uma vira uma condição: a de maior uso manda.
    chapas = [("ponta", v, a)] + ([("de dentro", 2 * v, b)] if planos > 1 else [])
    if planos > 1:
        condicoes.append(
            Condicao(
                "Esmagamento na chapa de dentro",
                "Chapa",
                2 * v / (d * b),
                contato,
                "p_{b}",
                validade=feitas,
            )
        )
    for nome, f, t in chapas:
        condicoes += [
            Condicao(
                f"Rasgamento até a borda, chapa {'da ' if nome == 'ponta' else ''}{nome}",
                "Chapa",
                f / (2 * t * (e - d / 2)),
                corte_na_chapa,
                "\\tau_{r}",
                validade=feitas,
            ),
            Condicao(
                f"Seção líquida, chapa {'da ' if nome == 'ponta' else ''}{nome}",
                "Chapa",
                f / ((w - d) * t),
                contato,
                "\\sigma_{liq}",
                validade=feitas,
            ),
        ]
    c.hipoteses += [
        "A força se divide por igual entre os pinos e, em cada pino, entre os planos de corte.",
        "Cada chapa empurra o pino por igual na própria espessura; o momento sai do equilíbrio das "
        "chapas alternadas (com número ímpar de planos, o binário fica metade em cada ponta).",
        "Pino maciço, com o furo do diâmetro dele. Corte a 0,577·S_y. Carga estática.",
    ]
    if planos % 2 == 1:
        c.alertas.append(
            "Com número ímpar de planos, as forças das chapas formam um binário e o pino tende a "
            "girar. Use cabeça e porca, ou um número par de planos."
        )
    return {"condicao": condicoes}


def _chapa_furo(c: Contexto) -> dict[str, Any]:
    forca = c.letra(F_LIGACAO, "F_lig")
    w = c.letra(LARGURA_CHAPA)
    t = c.letra(T_CHAPA)
    d = c.letra(D_FURO)
    furos = c.letra(N_FUROS, fixa=True)
    material = c.material()
    sy = material.sy if material else c.letra(g.SY, fixa=True)
    su = material.sut if material else c.letra(g.SUT, fixa=True)
    n = c.letra(g.FS, fixa=True)
    feitas = (
        Validade(w - furos * d, "Os furos somados precisam ser menores que a largura da chapa."),
        Validade(su - sy, "A ruptura não pode ser menor que o escoamento."),
    )
    c.hipoteses += [
        "Chapa plana sob tração uniforme, com os furos na mesma seção transversal.",
        "Sob carga estática, em material dúctil, vale a tensão média da seção: o pico na borda do "
        "furo (K_t) só governa em fadiga ou em material frágil.",
        "O esmagamento pelo pino e o rasgamento da borda estão no bloco Pino ao corte.",
    ]
    return {
        "condicao": [
            Condicao(
                "Escoamento da seção bruta",
                "Chapa",
                forca / (w * t),
                sy / n,
                "\\sigma_{bruta}",
                validade=feitas,
            ),
            Condicao(
                "Ruptura da seção com furos",
                "Chapa",
                forca / ((w - furos * d) * t),
                su / n,
                "\\sigma_{liq}",
                validade=feitas,
            ),
        ]
    }


BLOCOS_LIGACOES: tuple[Bloco, ...] = (
    Bloco(
        "pino",
        "Pino ao corte",
        GRUPO_LIGACOES,
        "Pino ou eixo de articulação entre chapas: corte, flexão do pino, esmagamento, rasgamento "
        "até a borda e seção líquida das chapas.",
        "V = F/(n_pi·planos)",
        (_ENTRA_FORCA, _ENTRA_D, _MATERIAL),
        (_SAI_CONDICAO,),
        _pino,
        (_OPCAO_PLANOS,),
        numerar=True,
    ),
    Bloco(
        "chapa_furo",
        "Chapa com furo",
        GRUPO_LIGACOES,
        "Chapa tracionada com furos na mesma seção: escoamento da seção bruta e ruptura da seção "
        "com furos.",
        "σ = F/((w − n·d)·t)",
        (_ENTRA_FORCA, _MATERIAL),
        (_SAI_CONDICAO,),
        _chapa_furo,
        numerar=True,
    ),
)

mb.registrar(BLOCOS_LIGACOES)
