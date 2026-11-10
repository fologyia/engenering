"""Montador: o fuso (parafuso de potência), conferido contra o fuso do Assistente de cargas."""

from __future__ import annotations

import pytest
import sympy as sp

from core import elementos_molas_atrito as ema
from core import montador as mt
from core import montador_aceite as ma
from core import montador_blocos as mb
from core import montador_modelos as mm
from core import montador_pecas as mp
from core import montador_uso as mu

VALORES = {
    "F_fu": 20000.0,
    "d_fu": 40.0,
    "p_fu": 7.0,
    "z_fu": 1.0,
    "mu_r": 0.15,
    "mu_c": 0.01,
    "d_c": 60.0,
    "n_fi": 8.0,
    "S_y": 420.0,
    "S_y_porca": 200.0,
    "p_adm": 11.0,
    "n": 2.0,
    "L_fu": 800.0,
    "K_fu": 1.0,
    "E": 205000.0,
    "n_fl": 3.0,
}


def montagem(**opcoes: str) -> mt.Montagem:
    dados = {
        "nos": [
            {"id": "f1", "tipo": "fuso", "opcoes": opcoes},
            {"id": "n1", "tipo": mb.RESULTADO, "opcoes": {}},
        ],
        "fios": [{"de": "f1", "saida": "condicao", "para": "n1", "entrada": "condicoes"}],
    }
    return mt.montar(mt.grafo_de_dados(dados))


def numeros(m: mt.Montagem, **trocas: float) -> dict[str, tuple[float, float]]:
    subs = {sp.Symbol(k, positive=True): v for k, v in {**VALORES, **trocas}.items()}
    return {
        c.nome: (float(c.esquerda.subs(subs).evalf()), float(c.direita.subs(subs).evalf()))
        for c in m.condicoes
    }


@pytest.mark.parametrize("forca_kN", [5.0, 20.0, 60.0])
@pytest.mark.parametrize("comprimento", [150.0, 800.0, 2500.0])  # Johnson e Euler
def test_cada_verificacao_igual_a_do_assistente(forca_kN, comprimento):
    m = montagem()
    assert not m.erros
    obtido = numeros(m, F_fu=forca_kN * 1000, L_fu=comprimento)
    r = ema.calcular_fuso({**ma._FUSO_DO_CASO, "forca_kN": forca_kN, "comprimento_mm": comprimento})
    nomes = {
        "von Mises no corpo": "von Mises no corpo do fuso",
        "Pressão nos filetes": "Pressão nos filetes",
        "Flexão no filete do fuso": "Flexão no filete do fuso",
        "Corte nos filetes do fuso": "Corte nos filetes do fuso",
        "Corte nos filetes da porca": "Corte nos filetes da porca",
    }
    for v in r.verificacoes:
        if v.nome in nomes:
            esquerda, direita = obtido[nomes[v.nome]]
            assert esquerda == pytest.approx(v.solicitante, rel=1e-9), v.nome
            assert direita == pytest.approx(v.resistente, rel=1e-9), v.nome
        elif v.nome == "Flambagem do fuso":
            esquerda, direita = obtido["Flambagem do fuso"]
            assert direita / (esquerda / 3.0) == pytest.approx(v.resistente, rel=1e-9)


def test_torque_de_subida_e_o_do_assistente():
    sobe, _ = ema.torques_do_fuso(20000.0, 36.5, 7.0, 0.15, 15.0)
    contexto = mb.Contexto(1, {}, {})
    saida = mp._fuso(contexto)
    subs = {sp.Symbol(k, positive=True): v for k, v in VALORES.items()}
    assert float(saida["T"].subs(subs)) == pytest.approx(sobe + 20000.0 * 0.01 * 60.0 / 2)
    sem_colar = mp._fuso(mb.Contexto(1, {"colar": mp.SEM_COLAR}, {}))
    assert float(sem_colar["T"].subs(subs)) == pytest.approx(sobe)


def test_opcoes_tiram_e_poem_condicoes():
    assert "Flambagem do fuso" in numeros(montagem())
    assert "Flambagem do fuso" not in numeros(montagem(flambagem=mp.SO_TRACIONADO))
    exigindo = numeros(montagem(trava=mp.EXIGIR_TRAVA))
    avanco, limite = exigindo["Autotravamento da rosca"]
    assert avanco == 7.0 and limite > avanco  # Tr 40×7 com μ = 0,15 trava sozinho
    quadrada = numeros(montagem(rosca=ema.ROSCA_QUADRADA, trava=mp.EXIGIR_TRAVA))
    assert quadrada["Autotravamento da rosca"][1] < limite  # sem o ângulo, menos atrito


def test_rosca_que_nao_trava_avisa():
    m = montagem()
    r = mt.isolar(m, "d_fu", {**{k: v for k, v in VALORES.items() if k != "d_fu"}, "z_fu": 4.0})
    assert r.valor is not None
    textos = " ".join(r.alertas)
    assert "não é autotravante" in textos


def test_modelo_pronto_e_caso_de_aceite():
    modelo = next(m for m in mm.MODELOS if m.nome == "Fuso: diâmetro mínimo")
    base = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    valores = {**{i.chave: i.padrao for i in base.grandezas if i.padrao is not None}}
    resposta = mt.isolar(base, modelo.alvo, {**valores, **modelo.valores})
    assert resposta.valor == pytest.approx(31.936, abs=1e-3)
    caso = next(c for c in ma.casos() if c.caso.startswith("Fuso"))
    assert caso.calcular() == pytest.approx(caso.esperado, rel=1e-9)


def test_fuso_e_peca_de_eixo_na_biblioteca():
    catalogo = mb.catalogo_para_tela(mb.SOLIDOS)
    assert "fuso" in {b["chave"] for b in catalogo}
    fora = mu.escondidos({"nos": [{"tipo": "perfil_i"}]}, catalogo)
    assert "fuso" in fora
    fora = mu.escondidos({"nos": [{"tipo": "fuso"}]}, catalogo)
    assert "flambagem" in fora  # a flambagem do fuso já está dentro do bloco
