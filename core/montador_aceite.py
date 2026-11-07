"""Casos de aceite do Montador: exemplos resolvidos em livro, refeitos com os blocos.

Cada caso monta a mesma conta na prancheta e compara com o número impresso na fonte. A Central de
validação roda todos a cada abertura, e o CI também. Os dados estão nas unidades do livro e são
convertidos aqui, na mesma linha, para dar para conferir com o exemplo aberto ao lado.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from core import elementos_eixos as ee
from core import montador as mt
from core import montador_blocos as mb
from core import montador_fluidos as fl
from core.casos_de_aceite import CasoDeAceite
from core.montador_modelos import Modelo

_MAURER = "Maurer, Hydraulics and Water Resources: Examples Using R (livro aberto)"
_OMNI = "Exemplo de NPSH da Omni Calculator (conferido com a fórmula de NPSH disponível)"
_JOUKOWSKY = "Fórmula de Joukowsky, Δp = ρ·a·ΔV, com a = 1200 m/s e ΔV = 2 m/s"
_ASSISTENTE = "O mesmo eixo calculado por core/elementos_eixos.py, o do Assistente de cargas"
_MODULO = "Montador de fluidos"
_PES = 0.3048
_PES3 = _PES**3
_R = mb.RESULTADO
_DADOS_DO_FLUIDO = {"fluido": fl.INFORMAR}
_TUBO_INFORMADO = {"tubo": fl.RUGOSIDADE_INFORMADA}
#: Água a 20 °C do exemplo do livro: ν = 1,023·10⁻⁶ m²/s, com ρ = 1000 kg/m³.
_AGUA_DO_LIVRO = {"rho": 1000.0, "mu": 1.023e-3, "p_v": 2339.0, "g": 9.81}
_TUBO_DO_LIVRO = {"L": 100.0, "varepsilon": 4.6e-5}


def resolver(
    tipos: tuple[str, ...],
    alvo: str,
    valores: Mapping[str, float],
    opcoes: Mapping[str, Mapping[str, str]] | None = None,
) -> mt.Resposta:
    """Monta a fila de blocos e isola a letra pedida, com os padrões da própria montagem."""
    modelo = Modelo("caso", "", alvo, dict(valores), tipos, opcoes=dict(opcoes or {}))
    base = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    com_padroes = {
        **{i.chave: i.padrao for i in base.grandezas if i.padrao is not None},
        **dict(base.padroes),
        **valores,
    }
    return mt.isolar(base, alvo, com_padroes)


def _valor(resposta: mt.Resposta) -> float:
    if resposta.valor is None:
        raise ValueError(f"Sem resposta: faltam {[i.texto for i in resposta.faltam]}.")
    return resposta.valor


def _perda() -> float:
    return _valor(
        resolver(
            ("fluido", "trecho", "carga", _R),
            "H_d",
            {**_AGUA_DO_LIVRO, **_TUBO_DO_LIVRO, "Q": 0.416, "D": 0.5},
            {"n1": _DADOS_DO_FLUIDO, "n2": _TUBO_INFORMADO},
        )
    )


def _vazao() -> float:
    return _valor(
        resolver(
            ("fluido", "trecho", "carga", _R),
            "Q",
            {**_AGUA_DO_LIVRO, **_TUBO_DO_LIVRO, "D": 0.5, "H_d": 0.6},
            {"n1": _DADOS_DO_FLUIDO, "n2": _TUBO_INFORMADO},
        )
    )


def _diametro() -> float:
    return _valor(
        resolver(
            ("fluido", "trecho", "carga", _R),
            "D",
            {**_AGUA_DO_LIVRO, **_TUBO_DO_LIVRO, "Q": 0.416, "H_d": 0.6},
            {"n1": _DADOS_DO_FLUIDO, "n2": _TUBO_INFORMADO},
        )
    )


def _ponto_de_operacao() -> mt.Resposta:
    """Exemplos 7.1 a 7.3 do livro, em pés: h = 30 + 0,16·Q² contra h = 82,5 − 0,201·Q².

    O livro congela o atrito na curva do sistema, com o K = 0,160 impresso. Aqui o mesmo K entra pela
    perda localizada, num trecho de comprimento desprezível. Com Colebrook a cada vazão, como a
    prancheta faz normalmente, a vazão sobe cerca de 6 %, porque f cai quando Re sobe.
    """
    d = 20.0 / 12.0 * _PES
    area = math.pi * d**2 / 4.0
    k_do_sistema = 0.160 * _PES / _PES3**2  # m/(m³/s)²
    return resolver(
        ("fluido", "trecho", "perda_local", "curva_bomba", _R),
        "Q",
        {
            "rho": 1000.0,
            "mu": 1.0e-3,
            "p_v": 2339.0,
            "g": 9.81,
            "D": d,
            "L": 1e-9,
            "K_L": k_do_sistema * 2.0 * 9.81 * area**2,
            "H_est": 30.0 * _PES,
            "Delta_p": 0.0,
            "H_0": 82.5 * _PES,
            "a_b": 0.201 * _PES / _PES3**2,
        },
        {"n1": _DADOS_DO_FLUIDO},
    )


def _altura_de_operacao() -> float:
    resposta = _ponto_de_operacao()
    q = _valor(resposta)
    return (82.5 - 0.201 * (q / _PES3) ** 2) * _PES


def _lamina(declividade: float) -> float:
    return _valor(
        resolver(
            ("manning", _R),
            "y_c",
            {"Q": 8.0, "n_m": 0.013, "b_c": 3.0, "S_0": declividade},
        )
    )


def _forca_na_comporta() -> float:
    """Comporta radial do exemplo 3.3 com 6 m de água: a força horizontal é a da projeção plana."""
    return _valor(
        resolver(
            ("fluido", "forca_plana", _R),
            "F_R",
            {"h_c": 3.0, "A": 6.0, "g": 9.81},
        )
    )


def _npsh() -> float:
    """1 m de sucção e 1,7 m de perda, com água a 20 °C e 101,325 kPa."""
    velocidade = 1.0
    d = 0.1
    q = velocidade * math.pi * d**2 / 4.0
    perda_em_k = 1.7 * 2.0 * 9.81 / velocidade**2
    return _valor(
        resolver(
            ("fluido", "trecho", "perda_local", "npsh", _R),
            "NPSH_r",
            {
                "D": d,
                "L": 1e-9,
                "Q": q,
                "K_L": perda_em_k,
                "z_s": 1.0,
                "g": 9.81,
                "p_atm": 101325.0,
            },
        )
    )


def _golpe() -> float:
    return _valor(
        resolver(
            ("fluido", "golpe", _R),
            "Delta_p_g",
            {"rho": 1000.0, "mu": 1e-3, "g": 9.81, "a_c": 1200.0, "Delta_V": 2.0},
            {"n1": _DADOS_DO_FLUIDO},
        )
    )


def _eixo_do_assistente() -> float:
    """Eixo com flexão alternada e torque constante, com S_e pelos fatores de Marin."""
    momento, torque = 2e5, 1.5e5
    a = 2.0 * momento  # √[4·M_a²]: a raiz da eq. 7-8, sem entalhe
    b = 3.0**0.5 * torque
    return ee.diametro_goodman(2.0, a, b, 690.0, "usinado_ou_estirado_a_frio", 50, 20.0)


def _eixo_no_montador() -> float:
    modelo = Modelo(
        "caso",
        "",
        "d",
        {"M_x": 2e5, "T": 1.5e5, "n": 2.0, "S_ut": 690.0},
        ("circular", "flexao", "torcao", "goodman", _R),
        extras=(("m1", "limite_fadiga"),),
        fios=(("m1", "se", "n4", "se"),),
        opcoes={"n4": {"esforcos": mb.EIXO_GIRANDO}},
    )
    base = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    valores = {
        **{i.chave: i.padrao for i in base.grandezas if i.padrao is not None},
        **dict(base.padroes),
        **modelo.valores,
    }
    return _valor(mt.isolar(base, "d", valores))


def casos() -> tuple[CasoDeAceite, ...]:
    return (
        CasoDeAceite(_MODULO, "Exemplo 4.1", "h_f (m)", 0.61, _perda, 0.005, _MAURER),
        CasoDeAceite(_MODULO, "Seção 4.5.2", "Q (m³/s)", 0.413, _vazao, 0.005, _MAURER),
        CasoDeAceite(_MODULO, "Seção 4.6.2", "D (m)", 0.501, _diametro, 0.005, _MAURER),
        CasoDeAceite(
            _MODULO,
            "Exemplo 7.3",
            "Q (pés³/s)",
            12.051,
            lambda: _valor(_ponto_de_operacao()) / _PES3,
            0.01,
            _MAURER,
        ),
        CasoDeAceite(
            _MODULO,
            "Exemplo 7.3",
            "H (pés)",
            53.285,
            lambda: _altura_de_operacao() / _PES,
            0.01,
            _MAURER,
        ),
        CasoDeAceite(
            _MODULO,
            "Exemplo 5.10, S = 0,018",
            "y (m)",
            0.498,
            lambda: _lamina(0.018),
            0.005,
            _MAURER,
        ),
        CasoDeAceite(
            _MODULO,
            "Exemplo 5.10, S = 0,0015",
            "y (m)",
            1.180,
            lambda: _lamina(0.0015),
            0.005,
            _MAURER,
        ),
        CasoDeAceite(
            _MODULO, "Exemplo 3.3, h = 6 m", "F_h (N)", 176268.0, _forca_na_comporta, 0.001, _MAURER
        ),
        CasoDeAceite(_MODULO, "NPSH disponível", "NPSH (m)", 7.41, _npsh, 0.005, _OMNI),
        CasoDeAceite(_MODULO, "Golpe de aríete", "Δp (Pa)", 2.4e6, _golpe, 0.001, _JOUKOWSKY),
        CasoDeAceite(
            "Montador de fórmulas",
            "Eixo em DE-Goodman",
            "d (mm)",
            _eixo_do_assistente(),
            _eixo_no_montador,
            0.001,
            _ASSISTENTE,
        ),
    )
