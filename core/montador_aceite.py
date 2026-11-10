"""Casos de aceite do Montador: exemplos resolvidos em livro, refeitos com os blocos.

Cada caso monta a mesma conta na prancheta e compara com o número impresso na fonte. A Central de
validação roda todos a cada abertura, e o CI também. Os dados estão nas unidades do livro e são
convertidos aqui, na mesma linha, para dar para conferir com o exemplo aberto ao lado.

Sem Streamlit.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any

import sympy as sp

from core import elementos_eixos as ee
from core import elementos_mancais as em
from core import elementos_molas_atrito as ema
from core import elementos_transmissao as et
from core import montador as mt
from core import montador_blocos as mb
from core import montador_eixo as me
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
    ligar: tuple[tuple[str, str, str, str], ...] = (),
    extras: tuple[tuple[str, str], ...] = (),
) -> mt.Resposta:
    """Monta a fila de blocos e isola a letra pedida, com os padrões da própria montagem.

    ``extras`` e ``ligar`` acrescentam blocos e fios fora da fila, como a condição de um bloco que
    também tem valores.
    """
    modelo = Modelo("caso", "", alvo, dict(valores), tipos, extras, ligar, dict(opcoes or {}))
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


# ---------------------------------------------------------------------------
# Peças do eixo: o mesmo caso pelo Montador e pelo Assistente de cargas
# ---------------------------------------------------------------------------

_PECAS = "Montador: peças do eixo"
_DO_ASSISTENTE = "A mesma peça calculada pelo Assistente de cargas (core/elementos_*.py)"
_ENGRENAGEM_DO_CASO: dict[str, Any] = {
    "potencia_kW": 15.0,
    "rotacao_rpm": 1450.0,
    "modulo_mm": 3.0,
    "z1": 20,
    "z2": 60,
    "angulo_pressao": 20.0,
    "angulo_helice": 15.0,
    "largura_mm": 40.0,
    "ko": 1.25,
    "km": 1.3,
    "fs": 1.5,
    "processo": "Fresado",
    "e_GPa": 205.0,
    "poisson": 0.3,
    "grau": "Grau 1",
    "dureza_HB": 250.0,
}


def _metrica(resultado: object, rotulo: str) -> float:
    return float(next(m.valor for m in resultado.metricas if m.rotulo == rotulo))  # type: ignore[attr-defined]


def _forca_radial_do_assistente() -> float:
    return _metrica(et.calcular_engrenagem(_ENGRENAGEM_DO_CASO), "Força radial F_r") * 1000.0


def _forca_radial_no_montador() -> float:
    base = mt.montar(
        mt.grafo_de_dados({"nos": [{"id": "e", "tipo": "engrenagem", "opcoes": {}}], "fios": []})
    )
    primitivo = 3.0 * 20 / math.cos(math.radians(15.0))
    numeros = {
        sp.Symbol(k, positive=True): sp.Float(v)
        for k, v in {
            "P": 15e6,
            "n_rot": 1450.0,
            "d_g": primitivo,
            "phi_n": math.radians(20.0),
            "psi": math.radians(15.0),
        }.items()
    }
    return float(base.saidas["e"]["F_r"].subs(numeros))


def _par_do_assistente() -> float:
    """A largura em que o dente do Assistente chega ao limite: Lewis cai com b, e o contato com √b."""
    largura = _ENGRENAGEM_DO_CASO["largura_mm"]
    pedidas = []
    for v in et.calcular_engrenagem(_ENGRENAGEM_DO_CASO).verificacoes:
        if v.solicitante is None or v.resistente is None:
            continue
        uso = float(v.solicitante) / float(v.resistente)
        if "Lewis" in v.nome:
            pedidas.append(largura * uso)
        elif "contato" in v.nome:
            pedidas.append(largura * uso**2)
    return max(pedidas)


def _par_no_montador() -> float:
    caso = _ENGRENAGEM_DO_CASO
    return _valor(
        resolver(
            ("par_engrenagens", _R),
            "b_g",
            {
                "P": caso["potencia_kW"] * 1e6,
                "n_rot": caso["rotacao_rpm"],
                "m_n": caso["modulo_mm"],
                "z_1": float(caso["z1"]),
                "z_2": float(caso["z2"]),
                "phi_n": math.radians(caso["angulo_pressao"]),
                "psi": math.radians(caso["angulo_helice"]),
                "K_o": caso["ko"],
                "K_m": caso["km"],
                "n": caso["fs"],
                "E": caso["e_GPa"] * 1000.0,
                "nu_g": caso["poisson"],
                "HB": caso["dureza_HB"],
            },
            {"n1": {"processo": caso["processo"], "grau": caso["grau"]}},
            ligar=(("n1", "condicao", "n2", "condicoes"),),
        )
    )


_CONICA_DO_CASO = {
    "torque_Nm": 200.0,
    "modulo_mm": 4.0,
    "z1": 18,
    "z2": 36,
    "largura_mm": 24.0,
    "angulo_pressao": 20.0,
}


def _conica_no_montador() -> float:
    base = mt.montar(
        mt.grafo_de_dados(
            {
                "nos": [
                    {"id": "c", "tipo": "engrenagem_conica", "opcoes": {"torque": "Pelo torque T"}}
                ],
                "fios": [],
            }
        )
    )
    numeros = {
        sp.Symbol(k, positive=True): sp.Float(v)
        for k, v in {
            "T": 200e3,
            "m_c": 4.0,
            "z_c1": 18.0,
            "z_c2": 36.0,
            "b_c": 24.0,
            "phi_n": math.radians(20.0),
        }.items()
    }
    return float(base.saidas["c"]["F_r"].subs(numeros))


_CHAVETA_DO_CASO = {
    "d_mm": 50.0,
    "torque_Nm": 600.0,
    "fator_servico": 1.25,
    "comprimento_mm": 80.0,
    "fs": 2.0,
    "pontas": "Arredondadas",
    "quantidade": 1,
    "dimensoes": "DIN 6885",
    "sy_chaveta_MPa": 350.0,
    "sy_eixo_MPa": 420.0,
    "sy_cubo_MPa": 310.0,
}


def _chaveta_no_montador() -> float:
    return _valor(
        resolver(
            ("chaveta", _R),
            "L_ch",
            {
                "T": 600e3,
                "d": 50.0,
                "S_y_ch": 350.0,
                "S_y": 420.0,
                "S_y_cubo": 310.0,
                "n": 2.0,
                "K_s": 1.25,
            },
        )
    )


_AJUSTE_DO_CASO = {
    "d_mm": 80.0,
    "d_furo_mm": 0.0,
    "D_cubo_mm": 140.0,
    "L_mm": 80.0,
    "e_eixo_GPa": 200.0,
    "e_cubo_GPa": 200.0,
    "nu_eixo": 0.3,
    "nu_cubo": 0.3,
    "atrito": 0.12,
    "fs": 1.5,
    "torque_Nm": 800.0,
    "fator_servico": 1.25,
    "axial_kN": 0.0,
    "sy_cubo_MPa": 310.0,
    "sy_eixo_MPa": 420.0,
    "ajuste": "H7/s6 (forte)",
    "rz_eixo_um": 4.0,
    "rz_cubo_um": 6.3,
    "alfa_um_mK": 11.5,
    "atrito_prensa": 0.1,
    "temperatura_max": 250.0,
    "delta_min_um": 0.0,
    "delta_max_um": 0.0,
}


def _ajuste_do_assistente() -> float:
    """O comprimento em que a capacidade por atrito do Assistente fica igual a n vezes o torque."""
    por_comprimento = _metrica(ee.calcular_ajuste(_AJUSTE_DO_CASO), "Força axial por atrito") * 1e3
    return 1.5 * (2.0 * 800e3 * 1.25 / 80.0) / (por_comprimento / 80.0)


def _ajuste_no_montador() -> float:
    return _valor(
        resolver(
            ("cubo_prensado", _R),
            "L_aj",
            {
                "T": 800e3,
                "d": 80.0,
                "D_cubo": 140.0,
                "E": 200000.0,
                "S_y": 420.0,
                "S_y_cubo": 310.0,
                "n": 1.5,
                "F_ac": 0.0,
            },
        )
    )


_ROLAMENTO_DO_CASO = {
    "tipo": "Esferas, sulco profundo",
    "regime": "Carga constante",
    "fr_kN": 5.0,
    "fa_kN": 1.0,
    "rotacao_rpm": 300.0,
    "c_kN": 62.0,
    "c0_kN": 44.0,
    "fator_aplicacao": 1.2,
    "confiabilidade": "90 %",
    "estado": "2",
    "criterio_vida": "Informar em horas",
    "vida_h": 20000.0,
    "s0_minimo": 1.5,
    "x": 0.56,
    "y": 1.5,
    "fr_min_kN": 1.0,
}


def _rolamento_no_montador() -> float:
    resposta = resolver(
        ("rolamento", _R),
        "C_din",
        {
            "F_rm": 5000.0,
            "F_am": 1000.0,
            "n_rot": 300.0,
            "C_0": 44000.0,
            "L_h": 20000 * 3600.0,
            "f_ap": 1.2,
        },
    )
    return _valor(resposta) / 1000.0


_TRECHO_UNICO = [{"nome": "Eixo", "comprimento": 300.0, "relacao": 1.0, "entalhe": ee.ENTALHE_LISO}]
_ELEMENTOS_DO_CASO = [
    {"nome": "Mancal A", "x": 20.0, "funcao": me.MANCAL_A},
    {
        "nome": "Engrenagem",
        "x": 100.0,
        "funcao": me.CARGA,
        "vertical": me.MAIS,
        "horizontal": me.MAIS,
        "torque": me.SAI,
    },
    {"nome": "Mancal B", "x": 280.0, "funcao": me.MANCAL_B},
    {"nome": "Acoplamento", "x": 300.0, "funcao": me.CARGA, "torque": me.ENTRA},
]


def _eixo_de_um_diametro(**opcoes: str) -> mt.Resposta:
    return resolver(
        (me.TIPO, _R),
        "d",
        {
            "F_v1": 5000.0,
            "F_h1": 2000.0,
            "T_e1": 300e3,
            "S_y": 420.0,
            "S_ut": 690.0,
            "E": 200000.0,
            "n": 2.0,
        },
        {
            "n1": {
                "trechos": json.dumps(_TRECHO_UNICO),
                "elementos": json.dumps(_ELEMENTOS_DO_CASO),
                "critica": me.NAO_CONFERIR,
                **opcoes,
            }
        },
    )


def _goodman_do_assistente() -> float:
    momento = math.hypot(5000.0, 2000.0) * (280.0 - 100.0) / 260.0 * 80.0
    return ee.diametro_goodman(
        2.0, 2.0 * momento, math.sqrt(3.0) * 300e3, 690.0, "usinado_ou_estirado_a_frio", 50, 20.0
    )


def _inclinacao_do_assistente() -> float:
    """O d em que a inclinação do Assistente no mancal A dá 0,001 rad: cai com d⁴."""
    valores: dict[str, object] = {
        "xa_mm": 20.0,
        "xb_mm": 280.0,
        "d_mm": 40.0,
        "e_GPa": 200.0,
        "poisson": 0.3,
        "rotacao_rpm": 0.0,
        "densidade_kg_m3": 7850.0,
        "mancal_axial": "A",
        "mancal_a": "Esferas de sulco profundo",
        "mancal_b": "Esferas de sulco profundo",
        "flecha_adm_mm": 1.0,
        "torcao_adm": 1.0,
    }
    for i in (1, 2, 3, 4):
        valores |= {
            f"f{i}_ativa": False,
            f"f{i}_x_mm": 0.0,
            f"f{i}_fy_kN": 0.0,
            f"f{i}_fz_kN": 0.0,
            f"f{i}_fx_kN": 0.0,
            f"f{i}_raio_mm": 0.0,
            f"f{i}_torque_Nm": 0.0,
            f"f{i}_massa_kg": 0.0,
        }
    valores |= {
        "f1_ativa": True,
        "f1_x_mm": 100.0,
        "f1_fy_kN": 5.0,
        "f1_fz_kN": 2.0,
        "f1_torque_Nm": 300.0,
        "f2_ativa": True,
        "f2_x_mm": 300.0,
        "f2_torque_Nm": -300.0,
    }
    resultado = ee.calcular_eixo_transmissao(valores)
    giro = next(v.solicitante for v in resultado.verificacoes if v.nome == "Inclinação no mancal A")
    return 40.0 * (float(giro or 0.0) / 0.001) ** 0.25


_FUSO_DO_CASO: dict[str, Any] = {
    "forca_kN": 20.0,
    "rotacao_rpm": 60.0,
    "rosca": ema.ROSCA_TRAPEZOIDAL,
    "d_mm": 40.0,
    "passo_mm": 7.0,
    "entradas": 1,
    "filetes": 8.0,
    "atrito": 0.15,
    "atrito_colar": 0.01,
    "d_colar_mm": 60.0,
    "sy_MPa": 420.0,
    "sy_porca_MPa": 200.0,
    "p_adm_MPa": 11.0,
    "fs": 2.0,
    "comprimento_mm": 800.0,
    "k": 1.0,
    "e_GPa": 205.0,
    "fs_flambagem": 3.0,
}


def _fuso_do_assistente() -> float:
    """A maior carga do Tr 40×7 no Assistente: a que leva a pior verificação a 100 %."""

    def pior(forca_kN: float) -> float:
        r = ema.calcular_fuso({**_FUSO_DO_CASO, "forca_kN": forca_kN})
        return max(v.aproveitamento or 0.0 for v in r.verificacoes)

    baixo, alto = 1.0, 1000.0
    for _ in range(80):
        meio = (baixo + alto) / 2
        baixo, alto = (meio, alto) if pior(meio) < 1.0 else (baixo, meio)
    return (baixo + alto) / 2 * 1000.0


def _fuso_no_montador() -> float:
    return _valor(
        resolver(
            (_R,),
            "F_fu",
            {
                "d_fu": 40.0,
                "p_fu": 7.0,
                "S_y": 420.0,
                "S_y_porca": 200.0,
                "p_adm": 11.0,
                "n": 2.0,
                "L_fu": 800.0,
                "E": 205000.0,
                "n_fl": 3.0,
            },
            ligar=(("f1", "condicao", "n1", "condicoes"),),
            extras=(("f1", "fuso"),),
        )
    )


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
        CasoDeAceite(
            _PECAS,
            "Engrenagem helicoidal",
            "F_r (N)",
            _forca_radial_do_assistente(),
            _forca_radial_no_montador,
            1e-9,
            _DO_ASSISTENTE,
        ),
        CasoDeAceite(
            _PECAS,
            "Par helicoidal, Lewis e contato",
            "b mínimo (mm)",
            _par_do_assistente(),
            _par_no_montador,
            1e-6,
            _DO_ASSISTENTE,
        ),
        CasoDeAceite(
            _PECAS,
            "Engrenagem cônica, eixos a 90°",
            "F_r no pinhão (N)",
            _metrica(et.calcular_conica(_CONICA_DO_CASO), "Força radial no pinhão") * 1000.0,
            _conica_no_montador,
            1e-9,
            _DO_ASSISTENTE,
        ),
        CasoDeAceite(
            _PECAS,
            "Chaveta DIN 6885, d = 50 mm",
            "L mínimo (mm)",
            _metrica(ee.calcular_chaveta(_CHAVETA_DO_CASO), "Comprimento mínimo"),
            _chaveta_no_montador,
            1e-6,
            _DO_ASSISTENTE,
        ),
        CasoDeAceite(
            _PECAS,
            "Cubo prensado H7/s6, d = 80 mm",
            "L do ajuste (mm)",
            _ajuste_do_assistente(),
            _ajuste_no_montador,
            1e-6,
            _DO_ASSISTENTE,
        ),
        CasoDeAceite(
            _PECAS,
            "Rolamento de esferas, 20 mil horas",
            "C (kN)",
            _metrica(em.calcular_rolamento(_ROLAMENTO_DO_CASO), "C necessário"),
            _rolamento_no_montador,
            1e-6,
            _DO_ASSISTENTE,
        ),
        CasoDeAceite(
            _PECAS,
            "Eixo com trechos, DE-Goodman",
            "d (mm)",
            _goodman_do_assistente(),
            lambda: _valor(
                _eixo_de_um_diametro(mancal_a=me.NAO_CONFERIR, mancal_b=me.NAO_CONFERIR)
            ),
            1e-6,
            _DO_ASSISTENTE,
        ),
        CasoDeAceite(
            _PECAS,
            "Eixo com trechos, inclinação no mancal",
            "d (mm)",
            _inclinacao_do_assistente(),
            lambda: _valor(_eixo_de_um_diametro()),
            0.001,
            _DO_ASSISTENTE,
        ),
        CasoDeAceite(
            _PECAS,
            "Fuso Tr 40×7, carga máxima",
            "F (N)",
            _fuso_do_assistente(),
            _fuso_no_montador,
            1e-6,
            _DO_ASSISTENTE,
        ),
    )
