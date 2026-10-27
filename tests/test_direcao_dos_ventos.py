"""Direção de cada caso de vento no estudo do SolidWorks contra o plano: o programa diz para onde o
caso empurrou e com que caso do plano ele bate (o caso do usuário em 24/10: W90 com sentido
trocado, W180 e W270 com a direção um do outro)."""

from __future__ import annotations

import pytest

from core import esforcos_modelo as em
from core import plano_de_cargas as pc

#: O plano do teste01: vento em X 1,82 kN, em Y (planta) 2,18 kN.
FORCAS = {"W0": ("+X", 1.82), "W90": ("+Y", 2.18), "W180": ("−X", 1.82), "W270": ("−Y", 2.18)}


def plano() -> pc.PlanoDeCargas:
    p = pc.PlanoDeCargas()
    for codigo, (direcao, valor) in FORCAS.items():
        sinal = -1.0 if direcao.startswith("−") else 1.0
        p = pc.com_acao(
            p,
            pc.nova_acao(
                codigo, cargas=[pc.CargaDoModelo("Viga", sinal * valor, "kN", direcao, "", 1)]
            ),
        )
    return p


def dados(reacoes: dict[str, tuple[float, float, float]]) -> em.EsforcosDoModelo:
    """Reações (kN) nos eixos do modelo, Y para cima."""
    return em.EsforcosDoModelo(
        casos={
            c: em.CasoImportado(c, "", "", "", "", {}, reacoes=em.Reacoes(modelo=r))
            for c, r in reacoes.items()
        },
        eixo_vertical="Y",
    )


#: O estudo do usuário: W0 +X; W90 +Z; W180 −Z com 1,82; W270 −X com 2,18 (reação = −força).
DO_USUARIO = {
    "W0": (-1.82, 0.0, 0.0),
    "W90": (0.0, 0.0, -2.18),
    "W180": (0.0, 0.0, 1.82),
    "W270": (2.18, 0.0, 0.0),
}


def _textos(itens: list[pc.ItemDeConferencia]) -> dict[str, str]:
    return {i.texto.split(":", 1)[0]: i.texto for i in itens}


def test_sentido_no_modelo_com_o_y_para_cima():
    assert em.sentido_no_modelo((1.0, 0.0), "Y") == "+X"
    assert em.sentido_no_modelo((0.0, 1.0), "Y") == "−Z"  # o +Y da planta é o −Z
    assert em.sentido_no_modelo((0.0, -1.0), "Z") == "−Y"
    assert em.sentido_no_modelo((1.0, 1.0), "Y") == "+X −Z"


def test_o_caso_do_usuario_cada_vento_diz_o_que_aconteceu():
    textos = _textos(em.conferir_reacoes(dados(DO_USUARIO), plano()))
    assert textos["W0"].startswith("W0: as reações equilibram")
    assert "W90 empurra para +Z" in textos["W90"] and "sentido está trocado" in textos["W90"]
    w180 = textos["W180"]
    assert "W180 empurra para −Z com 1,82 kN" in w180
    assert "direção do W90 do programa, com o valor do próprio W180" in w180
    assert "o W180 do programa empurra para −X" in w180
    assert "direção do W180 do programa, com o valor do próprio W270" in textos["W270"]
    resumo = textos["Ventos — no seu estudo"]
    assert "W180 → −Z (1,82 kN)" in resumo and "W180 → −X (1,82 kN)" in resumo
    assert "Não dá para só renomear" in resumo


def test_nomes_trocados_com_direcao_e_valor_de_outro_caso():
    """O W90 do estudo com a força do W180 do programa (−X, 1,82 kN): é o W180 com outro nome."""
    texto = em.diagnostico_do_vento("W90", (-1.82, 0.0), plano(), "Y")
    assert "é exatamente o W180 do programa" in texto and "nomes dos casos estão trocados" in texto
    so_nomes = {"W0": (1.82, 0.0, 0.0), "W180": (-1.82, 0.0, 0.0)}  # W0 e W180 trocados
    resumo = em.resumo_dos_ventos(dados(so_nomes), plano())
    assert resumo is not None and "renomeie os casos" in resumo.texto


def test_direcao_certa_com_outro_valor_e_tudo_certo():
    texto = em.diagnostico_do_vento("W0", (1.0, 0.0), plano(), "Y")
    assert "na direção certa" in texto and "falta ou sobra carga" in texto
    certo = {
        c: (-v[0], 0.0, v[1])
        for c, v in {
            "W0": (1.82, 0.0),
            "W90": (0.0, 2.18),
            "W180": (-1.82, 0.0),
            "W270": (0.0, -2.18),
        }.items()
    }
    # reação = −força; com Y para cima, a força +Y da planta é −Z no modelo (reação +Z).
    assert em.resumo_dos_ventos(dados(certo), plano()) is None


def test_peso_proprio_mostra_o_aco_sem_as_ligacoes():
    p = pc.com_fator_peso_proprio(pc.com_acao(pc.PlanoDeCargas(), pc.nova_acao("PP")), 1.07)
    itens = em.conferir_reacoes(
        dados({"PP": (0.0, 3.137, 0.0)}), p, peso_conferido_no_esqueleto=True
    )
    texto = next(i.texto for i in itens if i.texto.startswith("PP: peso do modelo"))
    assert "(320 kg; 299 kg de aço sem os 7 % de ligações)" in texto
    assert pytest.approx(3.137 / 9.81 / 1.07 * 1000, abs=1) == 299
