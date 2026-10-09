"""Placas de base dos pilares do modelo: Design Guide 1 com os esforços combinados da base."""

from __future__ import annotations

import json
import math

import pytest

from components.figuras_estrutura import svg_placa_de_base
from core import esforcos_modelo as em
from core import placa_base_pilares as pb
from core.project_report import montar_modelo_relatorio
from core.project_store import novo_projeto_documento
from core.technical_records import avaliar_contrato_registro
from tests.test_esforcos_modelo import PILAR, plano_do_portico
from tests.test_quadro_fundacoes import PILAR_2, portico


def _do(resultados, pilar=PILAR):
    return next(r for r in resultados if r.pilar == pilar)


def _linha(r, nome):
    return next(x for x in r.linhas if x.nome == nome)


def test_placa_padrao_do_portico_confere_com_a_conta_a_mao():
    """W 200 x 35,9 com 52,6 kN e 22,9 kN·m na base: momento grande (DG1 3.4)."""
    r = _do(
        pb.verificar_placas(portico(PILAR, PILAR_2), plano_do_portico(), pb.ParametrosDaPlaca())
    )
    assert r.n == pytest.approx(52.6, abs=0.05) and abs(r.m) == pytest.approx(22.9, abs=0.05)
    # À mão: f_p,máx = 0,65·0,85·25 = 13,81 MPa; q = 4144 N/mm; e = M/P; f = 350/2 − 50 = 125 mm;
    # Y = (f + N/2) − √[(f + N/2)² − 2P(e + f)/q]; m = (350 − 0,95·201)/2 = 79,5 mm.
    q = 0.65 * 0.85 * 25 * 300
    p, e = r.n * 1e3, abs(r.m) * 1e6 / (r.n * 1e3)
    y = 300 - math.sqrt(300**2 - 2 * p * (e + 125) / q)
    m = (350 - 0.95 * 201) / 2
    t_req = math.sqrt(4 * (q / 300) * y * (m - y / 2) / (0.9 * 250))
    assert r.espessura_requerida_mm == pytest.approx(t_req, rel=1e-3)
    assert r.utilizacao == pytest.approx((t_req / 19) ** 2, rel=1e-3)
    assert r.status == "NÃO OK" and r.modo == "Espessura da placa (flexão)"
    tracao = (q * y - p) / 2  # 2 chumbadores no lado tracionado
    resistencia = 0.75 * 0.75 * 400 * math.pi * 19.05**2 / 4
    assert _linha(r, "Chumbador: tração").aproveitamento == pytest.approx(
        tracao / resistencia, rel=1e-3
    )


def test_contato_no_momento_grande_nao_aparece_como_100_por_cento():
    r = _do(pb.verificar_placas(portico(PILAR), plano_do_portico(), pb.ParametrosDaPlaca()))
    contato = _linha(r, "Pressão de contato no concreto")
    assert contato.tipo == "informativo" and "momento grande" in contato.formula
    grossa = _do(
        pb.verificar_placas(
            portico(PILAR), plano_do_portico(), pb.ParametrosDaPlaca(espessura_mm=25.0)
        )
    )
    assert grossa.status == "OK" and grossa.utilizacao == pytest.approx(
        (grossa.espessura_requerida_mm / 25) ** 2, rel=1e-6
    )


def test_exigencias_anglo_da_placa_e_do_chumbador():
    fina = pb.ParametrosDaPlaca(espessura_mm=12.5)
    linhas = {v.nome: v for v in pb.verificacoes_anglo(fina)}
    assert linhas["Anglo: espessura mínima da placa de base"].status == "NÃO OK"
    leve = {
        v.nome: v
        for v in pb.verificacoes_anglo(pb.ParametrosDaPlaca(espessura_mm=12.5, elemento_leve=True))
    }
    assert leve["Anglo: espessura mínima da placa de base"].status == "OK"
    assert linhas["Anglo: diâmetro mínimo do chumbador"].status == "OK"
    furo = linhas['Anglo: furo, arruela e grout do chumbador de 3/4"']
    assert furo.status == "INFO" and "furo na placa 33 mm" in furo.formula
    assert "espessura 9,5 mm" in furo.formula
    r = _do(
        pb.verificar_placas(
            portico(PILAR), plano_do_portico(), pb.ParametrosDaPlaca(espessura_mm=40.0), anglo=True
        )
    )
    assert r.status == "OK" and any(x.nome.startswith("Anglo:") for x in r.linhas)


def test_placa_pequena_para_o_momento_reprova_e_geometria_ruim_fica_pendente():
    pequena = pb.ParametrosDaPlaca(comprimento_mm=220, largura_mm=170, fck_MPa=10)
    r = _do(pb.verificar_placas(portico(PILAR), plano_do_portico(), pequena))
    assert r.status == "NÃO OK" and r.utilizacao is None
    assert "Placa insuficiente" in r.linhas[0].formula
    estreita = _do(
        pb.verificar_placas(
            portico(PILAR), plano_do_portico(), pb.ParametrosDaPlaca(largura_mm=150)
        )
    )
    assert estreita.status == pb.STATUS_PENDENTE and "maior que a seção" in estreita.motivo


def test_pilar_sem_perfil_ou_sem_base_fica_pendente():
    dados = em.com_membros(
        portico(PILAR), {PILAR_2: em.ConfiguracaoDoMembro("", "Pilar", base=em.BASE_INICIO)}
    )
    resultados = pb.verificar_placas(dados, plano_do_portico(), pb.ParametrosDaPlaca())
    assert _do(resultados, PILAR_2).status == pb.STATUS_PENDENTE
    assert "perfil" in _do(resultados, PILAR_2).motivo
    iguais = (
        em.PontoDeEsforco("1", "1", -50.0, 0, 0, 0, 0, 0),
        em.PontoDeEsforco("1", "2", -50.0, 0, 0, 0, 0, 0),
    )
    ambiguo = em.EsforcosDoModelo(
        casos={"PP": em.CasoImportado("PP", "", "", "", "", {"P1": iguais})},
        membros={"P1": em.ConfiguracaoDoMembro("W 200 x 35,9 (H)", "Pilar")},
    )
    r = pb.verificar_placas(ambiguo, plano_do_portico(), pb.ParametrosDaPlaca())[0]
    assert r.status == pb.STATUS_PENDENTE and "escolha a base" in r.motivo


def test_momento_no_eixo_fraco_vira_alerta():
    pontos = (
        em.PontoDeEsforco("1", "1", -40.0, 1.0, 1.0, 6.0, 8.0, 0.0),
        em.PontoDeEsforco("1", "2", -38.0, 1.0, 1.0, 0.0, 0.0, 0.0),
    )
    dados = em.EsforcosDoModelo(
        casos={"PP": em.CasoImportado("PP", "", "", "", "", {"P1": pontos})},
        membros={"P1": em.ConfiguracaoDoMembro("W 200 x 35,9 (H)", "Pilar", base=em.BASE_INICIO)},
    )
    r = pb.verificar_placas(dados, plano_do_portico(), pb.ParametrosDaPlaca(espessura_mm=31.5))[0]
    alerta = _linha(r, "Momento no eixo fraco do pilar")
    assert alerta.status == "ALERTA" and r.status == "ALERTA"


def test_placa_vai_e_volta_pelo_projeto_e_valor_estranho_volta_ao_padrao():
    placa = pb.ParametrosDaPlaca(espessura_mm=22.4, diametro='1"', distancia_mm=120.0)
    dados = em.com_placa(portico(PILAR), pb.para_dicionario(placa))
    volta = em.de_dicionario(json.loads(json.dumps(em.para_dicionario(dados))))
    assert pb.placa_do_modelo(volta) == placa
    estranho = pb.de_dicionario({"espessura_mm": "abc", "diametro": "9 polegadas", "aco": "?"})
    assert estranho == pb.ParametrosDaPlaca()
    assert pb.placa_do_modelo(em.EsforcosDoModelo()) == pb.ParametrosDaPlaca()
    assert pb.validar(pb.ParametrosDaPlaca(lado_tracionado=5))
    assert pb.validar(pb.ParametrosDaPlaca(distancia_mm=200.0))
    assert not pb.validar(pb.ParametrosDaPlaca())


def test_csv_registro_e_memorial():
    placa = pb.ParametrosDaPlaca(espessura_mm=25.0)
    resultados = pb.verificar_placas(portico(PILAR, PILAR_2), plano_do_portico(), placa, anglo=True)
    texto = pb.csv_das_placas(resultados).decode("utf-8-sig")
    assert texto.splitlines()[0].split(";") == list(pb.COLUNAS)
    registro = pb.registro_das_placas(resultados, placa, anglo=True)
    assert avaliar_contrato_registro(registro)["valido"]
    json.dumps(registro)
    assert registro["status"] == "Atende"
    assert "Placa 350 × 300 × 25 mm" in registro["resultados"]["destaque_memorial"]
    projeto = novo_projeto_documento("Plataforma", codigo="MC-01")
    projeto["registros_tecnicos"] = [registro]
    capitulo = next(s for s in montar_modelo_relatorio(projeto)["secoes"] if "blocos" in s)
    assert capitulo["blocos"][0]["rotulo"] == "Resultado: ATENDE."
    assert PILAR in json.dumps(capitulo, ensure_ascii=False)


def test_desenho_da_placa_tem_os_chumbadores():
    svg = svg_placa_de_base(
        comprimento_mm=350,
        largura_mm=300,
        altura_perfil_mm=201,
        largura_mesa_mm=165,
        espessura_mesa_mm=10.2,
        espessura_alma_mm=6.2,
        chumbadores=6,
        distancia_mm=125,
        furo_mm=33,
        arruela_mm=50,
    )
    assert svg.startswith("<svg") and svg.count("<circle") == 2 * 6
    assert "N = 350 mm" in svg and "B = 300 mm" in svg and "f = 125 mm" in svg
