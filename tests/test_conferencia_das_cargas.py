"""Onde e como as cargas entraram no estudo (pedido de 24/11/2026, modelo es_v2 do usuário):

1. ventos todos ao contrário do plano, ditos numa frase (o "Inverter direção" no gerenciador);
3. o CSV do gerenciador de casos de carga explica a diferença de cada caso (valor, "Por item");
5. as setas de cada vento, plano × estudo, sobre a planta;
6. onde a resultante atua (altura do vento, centro dos pesos), pelo equilíbrio nos pés.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from core import apoios_do_modelo as am
from core import cargas_aplicadas as ca
from core import centro_das_cargas as cc
from core import diagnostico_do_modelo as dm
from core import esforcos_modelo as em
from core import gerenciador_solidworks as gs
from core import plano_de_cargas as pc
from core import setas_do_vento as sv
from core import tratamento_do_modelo as tm
from tests import portico_3d_teste01 as t
from tests.test_nucleo_esforcos_ponta_a_ponta import _achado, _titulos, diagnostico, montar

VENTOS = ("W0", "W90", "W180", "W270")


def invertidos(fator: float = -1.0) -> dict[str, str]:
    return {c: f"{fator}*{c}" for c in VENTOS}


# ------------------------------------------------------------------ 1. ventos ao contrário
def test_todos_os_ventos_ao_contrario_viram_uma_frase():
    trocar = invertidos(-0.7)  # sentido trocado e menos carga: não é só troca de nomes
    dados, apoios, geometria = montar(forcas=trocar, reacoes=trocar, apoios_de=trocar)
    assert len(em.ventos_ao_contrario(dados, t.plano())) == 4
    d = diagnostico(dados, apoios, geometria)
    achado = _achado(d, "Ventos no sentido contrário ao do plano")
    assert "Os 4 ventos do seu estudo empurram no sentido contrário" in achado.problema
    assert "o valor também difere" in achado.problema
    assert any("Inverter direção" in p for p in achado.passos)
    assert any("W0 → +X" in p for p in achado.passos)
    assert "Ventos em direção diferente da do plano" not in _titulos(d)
    assert not achado.acao  # sem troca de nomes possível
    resumo = em.resumo_dos_ventos(dados, t.plano())
    assert resumo is not None and "Todos os ventos empurram no sentido contrário" in resumo.texto
    assert "direção de um vento e o valor de outro" not in resumo.texto


def test_ao_contrario_com_os_mesmos_valores_oferece_trocar_os_nomes():
    trocar = invertidos()
    dados, apoios, geometria = montar(forcas=trocar, reacoes=trocar, apoios_de=trocar)
    achado = _achado(
        diagnostico(dados, apoios, geometria), "Ventos no sentido contrário ao do plano"
    )
    assert "só o sentido está trocado" in achado.problema
    assert achado.acao == dm.ACAO_TROCAR_NOMES
    # O tratamento automático troca os nomes e diz por quê.
    tratado = tm.tratar(dados, apoios, t.plano(), geometria)
    texto = next(x.texto for x in tratado.tratamentos if x.codigo == tm.T_VENTOS)
    assert "Inverter direção" in texto


def test_um_vento_so_ao_contrario_nao_e_o_engano_de_todos():
    trocar = {"W0": "-1*W0"}
    dados, _, _ = montar(forcas=trocar, reacoes=trocar, apoios_de=trocar)
    assert em.ventos_ao_contrario(dados, t.plano()) == []


# ------------------------------------------------------------------ 3. o gerenciador
GERENCIADOR = "\r\n".join(
    [
        "Tipo de carga,3,3,3,4,1",
        "Nome da carga:,PE,PE-2,W0,Gravidade-1,SC",
        "Valor de:,Normal ao plano,Normal ao plano,Normal ao plano,Normal ao plano,"
        "Valor da pressão",
        "Valores originais/iniciais:,1700 N,360 N,2550 N,-10.5 m/s^2,5000 N/m^2",
        "PP,Suprimir,Suprimir,Suprimir,-10.5,Suprimir",
        "PE,1700,360,Suprimir,Suprimir,Suprimir",
        "W0,Suprimir,Suprimir,2550,Suprimir,Suprimir",
        "SC,Suprimir,Suprimir,Suprimir,Suprimir,5000",
    ]
).encode("cp1252")


def _caso(codigo: str, reacao_kN: tuple[float, float, float]) -> em.CasoImportado:
    return em.CasoImportado(codigo, "e", "a", "t", codigo, {}, em.Reacoes(reacao_kN))


def _plano_do_usuario() -> pc.PlanoDeCargas:
    p = pc.PlanoDeCargas()
    p = pc.com_acao(p, pc.nova_acao("PP"))
    p = pc.com_acao(p, pc.nova_acao("PE", cargas=[pc.CargaDoModelo("Viga", 2.29, "kN", "Z")]))
    p = pc.com_acao(p, pc.nova_acao("W0", cargas=[pc.CargaDoModelo("Topo", 3.52, "kN", "+X")]))
    return pc.com_acao(
        p, pc.nova_acao("SC", cargas=[pc.CargaDoModelo("Piso", 5.0, "kN/m²", "Z (vertical)")])
    )


@pytest.mark.parametrize(
    ("forcas", "reacao", "vezes"),
    [
        ((1.7, 0.36), 3.14, (1, 4)),  # o PE do usuário
        ((2.55,), 2.55, (1,)),
        ((2.55,), 7.65, (3,)),
        ((2.55,), 3.52, None),
        ((), 1.0, None),
    ],
)
def test_quantas_vezes_cada_forca_entrou(forcas, reacao, vezes):
    assert ca.vezes_de_cada_forca(forcas, reacao) == vezes


def test_o_gerenciador_explica_cada_caso():
    arquivo = gs.ler(GERENCIADOR)
    dados = em.EsforcosDoModelo(
        casos={
            "PE": _caso("PE", (0.0, 3.14, 0.0)),  # Y para cima: a reação do peso para cima
            "W0": _caso("W0", (2.55, 0.0, 0.0)),  # a carga empurrou −X
            "SC": _caso("SC", (0.0, 9.196, 0.0)),
        }
    )
    linhas = {linha.caso: linha for linha in ca.conferir(arquivo, dados, _plano_do_usuario())}
    pe = linhas["PE"]
    assert "“PE-2” (360 N) entrou 4 vezes" in pe.explicacao and "Por item" in pe.explicacao
    assert pe.reacao_kN == pytest.approx(3.14) and pe.plano_kN == pytest.approx(2.29)
    assert pe.nivel == pc.NIVEL_ATENCAO
    w0 = linhas["W0"]
    assert "sentido CONTRÁRIO" in w0.explicacao
    assert "cada força entrou uma vez" in w0.explicacao
    assert "não é o do plano (3,52 kN)" in w0.explicacao
    sc = linhas["SC"]
    assert "1,84 m² carregados" in sc.explicacao
    assert "Sem o arquivo de reações" in linhas["PP"].explicacao  # no plano, não importado
    assert pe.como_linha()["Caso"] == "PE"


def test_gerenciador_gravado_no_projeto_ida_e_volta():
    projeto = {ca.CAMPO_DO_PROJETO: ca.para_dicionario("gerenciador.csv", GERENCIADOR)}
    nome, arquivo = ca.do_projeto(projeto)  # type: ignore[misc]
    assert nome == "gerenciador.csv" and len(arquivo.casos) == 4
    assert ca.do_projeto({ca.CAMPO_DO_PROJETO: {"conteudo": "lixo"}}) is None
    assert ca.do_projeto(None) is None


def test_caso_t_menos_do_gerenciador_e_o_t_menos_do_plano():
    assert ca.codigo_do_caso("T-", ["T+", "T−"]) == "T−"
    assert ca.codigo_do_caso("W90", ["W0", "W90"]) == "W90"


# ------------------------------------------------------------------ 5. as setas
def test_setas_do_vento_mostram_plano_e_estudo():
    trocar = invertidos()
    dados, _, geometria = montar(forcas=trocar, reacoes=trocar, apoios_de=trocar)
    desenho = sv.svg(dados, t.plano(), geometria)
    assert desenho is not None and desenho.startswith("<svg")
    for caso in VENTOS:
        assert f">{caso} — ao contrário<" in desenho
    assert desenho.count(sv.COR_PLANO) >= 4 and desenho.count(sv.COR_ESTUDO) >= 4
    assert "o que o estudo aplicou" in desenho
    sem_vento = em.EsforcosDoModelo()
    assert sv.svg(sem_vento, t.plano(), geometria) is None


# ------------------------------------------------------------------ 6. onde a carga atua
def _plano_localizado(*, vento_nos_pilares: bool) -> pc.PlanoDeCargas:
    """O vento do teste01 (1,82 kN em X) nas barras do esqueleto: no contorno do topo (onde o
    estudo aplica) ou ao longo dos pilares (a meia altura)."""
    p = t.plano()
    if vento_nos_pilares:
        cargas = [
            pc.CargaDoModelo(f"Pilar[{k}]", 1.82 / 4 / 2.0, "kN/m", "+X") for k in range(1, 5)
        ]
    else:
        cargas = [pc.CargaDoModelo(f"Contorno[{k}]", 1.82 / 2 / 1.0, "kN/m", "+X") for k in (2, 4)]
    acoes = tuple(pc.nova_acao("W0", cargas=cargas) if a.codigo == "W0" else a for a in p.acoes)
    return pc.PlanoDeCargas(acoes=acoes, fator_peso_proprio=p.fator_peso_proprio)


def test_vento_na_altura_do_plano():
    dados, apoios, geometria = montar()
    centros = {
        c.codigo: c
        for c in cc.comparar(dados, _plano_localizado(vento_nos_pilares=False), apoios, geometria)
    }
    w0 = centros["W0"]
    assert w0.tipo == cc.TIPO_HORIZONTAL and w0.nivel == pc.NIVEL_OK
    assert w0.plano[0] == pytest.approx(2.0, abs=0.01)
    assert w0.estudo[0] == pytest.approx(2.0, abs=0.05)


def test_vento_aplicado_so_no_topo_quando_o_plano_distribui_na_altura():
    """O caso do usuário: no estudo a resultante do vento atua a 2,86 m (as vigas do N3)."""
    dados, apoios, geometria = montar()
    centros = {
        c.codigo: c
        for c in cc.comparar(dados, _plano_localizado(vento_nos_pilares=True), apoios, geometria)
    }
    w0 = centros["W0"]
    assert w0.nivel == pc.NIVEL_ATENCAO
    assert w0.plano[0] == pytest.approx(1.0, abs=0.01)
    assert "mais alta" in w0.texto


def test_carga_vertical_no_centro_do_plano():
    dados, apoios, geometria = montar()
    p = t.plano()
    # A SC do teste01 no contorno inteiro (1,5 kN/m nos quatro lados): centro no meio da planta.
    sc = pc.nova_acao(
        "SC",
        cargas=[
            pc.CargaDoModelo(f"Contorno[{k}]", 1.5, "kN/m", "Z (vertical)") for k in range(1, 5)
        ],
    )
    plano = pc.PlanoDeCargas(
        acoes=tuple(sc if a.codigo == "SC" else a for a in p.acoes),
        fator_peso_proprio=p.fator_peso_proprio,
    )
    centros = {c.codigo: c for c in cc.comparar(dados, plano, apoios, geometria)}
    assert centros["SC"].tipo == cc.TIPO_VERTICAL and centros["SC"].nivel == pc.NIVEL_OK
    assert centros["SC"].plano == pytest.approx((0.75, 0.5), abs=0.01)
    assert centros["SC"].estudo == pytest.approx((0.75, 0.5), abs=0.02)
    # Só no lado do contorno 1 no plano: o centro do estudo (no meio) fica longe.
    so_um_lado = pc.nova_acao(
        "SC", cargas=[pc.CargaDoModelo("Contorno[1]", 5.0, "kN/m", "Z (vertical)")]
    )
    plano = pc.PlanoDeCargas(
        acoes=tuple(so_um_lado if a.codigo == "SC" else a for a in p.acoes),
        fator_peso_proprio=p.fator_peso_proprio,
    )
    centro = {c.codigo: c for c in cc.comparar(dados, plano, apoios, geometria)}["SC"]
    assert centro.nivel == pc.NIVEL_ATENCAO and "outro lugar" in centro.texto


def test_sem_posicao_dos_pes_ou_carga_fora_das_barras_fica_de_fora():
    dados, apoios, geometria = montar()
    assert "W0" not in {c.codigo for c in cc.comparar(dados, t.plano(), apoios, geometria)}
    sem_apoios = am.ApoiosDoModelo()
    assert (
        cc.comparar(dados, _plano_localizado(vento_nos_pilares=True), sem_apoios, geometria) == []
    )


# ------------------------------------------------------------------ a página
def test_pagina_mostra_onde_e_como_as_cargas_entraram(banco_com_projeto):
    from pathlib import Path

    from core.project_store import obter_projeto_ativo, salvar_projeto

    trocar = invertidos()
    dados, apoios, geometria = montar(forcas=trocar, reacoes=trocar, apoios_de=trocar)
    projeto = obter_projeto_ativo()
    projeto["plano_de_cargas"] = pc.para_dicionario(_plano_localizado(vento_nos_pilares=True))
    projeto["esforcos_do_modelo"] = em.para_dicionario(dados)
    projeto["apoios_do_modelo"] = am.para_dicionario(apoios)
    from core import leitura_do_modelo as ld

    projeto["geometria_do_modelo"] = ld.para_dicionario(geometria)
    projeto[ca.CAMPO_DO_PROJETO] = ca.para_dicionario("gerenciador.csv", GERENCIADOR)
    salvar_projeto(projeto, motivo="teste")
    app = str(Path(__file__).resolve().parent.parent / "app.py")
    at = AppTest.from_file(app, default_timeout=180)
    at.run()
    at.switch_page("app_pages/esforcos_modelo.py")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert "Onde e como as cargas entraram" in [s.value for s in at.subheader]
    assert any("O que o gerenciador aplicou" in m.value for m in at.markdown)
    assert any("O que explica" in d.value.columns for d in at.dataframe)
