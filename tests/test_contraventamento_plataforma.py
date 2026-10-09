"""Contraventamento de estruturas abertas: ações, combinações, B₂, forças nas diagonais e registro.

As contas de referência seguem as equações da NBR 8800 (Projeto de 2024): 4.8.7.2 (combinações),
4.10.7.1 (força nocional de 0,3 %), Anexo C (B₂ com R_s = 1) e Tabela B.1 (deslocamentos).
"""

from __future__ import annotations

import json
import math
from dataclasses import replace

import pytest

from core import cantoneiras as ct
from core import contraventamento_barras as cb
from core import contraventamento_estrutura_registro as reg
from core import contraventamento_plataforma as cp
from core import load_combinations as comb
from core import vento_estrutura_aberta as va
from core.project_report import (
    gerar_relatorio_industrial_pdf,
    gerar_relatorio_industrial_word,
    montar_modelo_relatorio,
)
from core.project_store import novo_projeto_documento
from core.technical_records import avaliar_contrato_registro, identificar_peca_registro


def entrada(**troca) -> cp.EntradaContraventamento:
    return replace(cp.EntradaContraventamento(), **troca)


@pytest.fixture(scope="module")
def padrao() -> cp.ResultadoContraventamento:
    return cp.calcular(cp.EntradaContraventamento())


def _andar(r, direcao, andar=1):
    return next(a for a in r.andares if a.direcao == direcao and a.andar == andar)


# ------------------------------------------------------------------ ações
def test_acoes_tem_as_categorias_e_o_vento_num_grupo_exclusivo(padrao):
    nomes = {a.nome: a for a in padrao.acoes}
    assert set(nomes) == {
        "Estrutura",
        "Piso",
        "Sobrecarga",
        "Vento +X",
        "Vento −X",
        "Vento +Y",
        "Vento −Y",
    }
    assert {a.grupo for a in padrao.acoes if a.nome.startswith("Vento")} == {"Vento"}
    assert nomes["Estrutura"].gamma == 1.25 and nomes["Piso"].gamma == 1.35
    assert nomes["Sobrecarga"].psi0 == 0.7 and nomes["Vento +X"].gamma == 1.4
    # Força nocional: 0,3 % do peso acima do andar, reversível.
    area = 12.0 * 6.0
    assert nomes["Estrutura"].valor("V_X_1") == pytest.approx(0.003 * 0.60 * area)
    assert "V_X_1" in nomes["Estrutura"].efeitos_reversiveis
    assert nomes["Sobrecarga"].valor("P_1") == pytest.approx(5.0 * area)


def test_cortante_de_calculo_e_a_envoltoria_com_a_nocional(padrao):
    area = 12.0 * 6.0
    vento_x = padrao.vento.x.cortantes_dos_andares_kN[0]
    nocional = 0.003 * area * (1.25 * 0.60 + 1.35 * 0.45)
    # Vento principal (1,4) e sobrecarga acompanhante (1,5 × 0,7) só pela nocional dela.
    vento_principal = 1.4 * vento_x + nocional + 1.5 * 0.7 * 0.003 * 5.0 * area
    sobrecarga_principal = 1.4 * 0.6 * vento_x + nocional + 1.5 * 0.003 * 5.0 * area
    a = _andar(padrao, "X")
    assert abs(a.cortante_elu.valor) == pytest.approx(max(vento_principal, sobrecarga_principal))
    assert a.cortante_elu.acao_principal == "Vento +X"


def test_b2_do_andar_confere_com_o_anexo_c(padrao):
    a = _andar(padrao, "Y")
    area = 12.0 * 6.0
    n_sd = area * (1.25 * 0.60 + 1.35 * 0.45 + 1.5 * 5.0)
    c = ct.obter_cantoneira(cb.Diagonal().perfil)
    painel, h = 6000.0, 4000.0  # Y: painel = 6 m (um vão)
    comprimento = math.hypot(painel, h)
    k = 2 * 1 * 1 * 200_000 * c.area_mm2 * (painel / comprimento) ** 2 / comprimento / 1e3
    assert a.gravidade_elu.valor == pytest.approx(n_sd)
    assert a.rigidez_kN_mm == pytest.approx(k)
    assert a.b2 == pytest.approx(1 / (1 - n_sd / (k * h)))
    assert a.deslocabilidade == "pequena" and a.amplificacao == 1.0


def test_forca_na_diagonal_em_x_so_tracao(padrao):
    a = _andar(padrao, "X")
    cos = 6000.0 / math.hypot(6000.0, 4000.0)
    esperado = (0.5 + 0.075) * abs(a.cortante_elu.valor) / cos
    assert a.tracao_kN == pytest.approx(esperado)
    assert a.compressao_kN == 0.0
    assert a.theta_vertical_graus == pytest.approx(math.degrees(math.atan(6.0 / 4.0)))


def test_deslocamento_do_topo_e_limite_h300_com_um_piso(padrao):
    a = _andar(padrao, "X")
    k_linha = a.rigidez_kN_mm / 2
    esperado = 0.575 * abs(a.cortante_servico.valor) / k_linha
    assert a.deslocamento_mm == pytest.approx(esperado)
    linha = next(v for v in padrao.verificacoes if v.nome == "X: deslocamento horizontal do topo")
    assert linha.resistente == pytest.approx(4000.0 / 300.0)
    assert a.cortante_servico.estado_limite == comb.ELS_RARA


def test_combinacao_frequente_reduz_o_deslocamento():
    rara = cp.calcular(entrada())
    freq = cp.calcular(entrada(combinacao_de_servico=comb.ELS_FREQUENTE))
    assert freq.deslocamento_topo_mm["X"] == pytest.approx(0.3 * rara.deslocamento_topo_mm["X"])


def test_dois_pisos_usam_h400_e_h500_e_acumulam():
    r = cp.calcular(entrada(cotas_m=(3.0, 6.0)))
    nomes = [v.nome for v in r.verificacoes]
    assert "X, andar 1: deslocamento entre pisos" in nomes
    topo = next(v for v in r.verificacoes if v.nome == "Y: deslocamento horizontal do topo")
    assert topo.resistente == pytest.approx(6000.0 / 400.0)
    a1, a2 = _andar(r, "X", 1), _andar(r, "X", 2)
    assert abs(a1.cortante_elu.valor) > abs(a2.cortante_elu.valor)
    assert a1.forca_no_pilar_kN > a2.forca_no_pilar_kN


@pytest.mark.parametrize(
    ("tipo", "ativas", "compressao"),
    [
        (cp.TIPO_X_TRACAO, 1, False),
        (cp.TIPO_X_TRACAO_COMPRESSAO, 2, True),
        (cp.TIPO_DIAGONAL_SIMPLES, 1, True),
        (cp.TIPO_V_INVERTIDO, 2, True),
    ],
)
def test_tipos_de_contraventamento(tipo, ativas, compressao):
    sistema = cp.SistemaDeContraventamento(tipo=tipo)
    r = cp.calcular(entrada(contraventamento_x=sistema))
    a = _andar(r, "X")
    projecao = 3000.0 if tipo == cp.TIPO_V_INVERTIDO else 6000.0
    cos = projecao / math.hypot(projecao, 4000.0)
    assert a.tracao_kN == pytest.approx(a.forca_na_linha_kN / (ativas * cos))
    assert (a.compressao_kN > 0) is compressao
    if compressao:
        assert any(
            "compressão da diagonal" in v.nome for v in r.verificacoes if v.nome.startswith("X")
        )


def test_x_ligado_no_cruzamento_trava_no_meio():
    solto = cp.calcular(entrada(ligadas_no_cruzamento=False))
    travado = cp.calcular(entrada())
    esbeltez = "X, andar 1: esbeltez da diagonal tracionada"
    valor_solto = next(v.solicitante for v in solto.verificacoes if v.nome == esbeltez)
    valor_travado = next(v.solicitante for v in travado.verificacoes if v.nome == esbeltez)
    assert valor_solto == pytest.approx(2 * valor_travado)


def test_forca_horizontal_entra_nos_andares_abaixo_do_nivel():
    forca = cp.ForcaHorizontal("Correia", "Y", 2, 30.0)
    sem = cp.calcular(entrada(cotas_m=(3.0, 6.0)))
    com = cp.calcular(
        entrada(cotas_m=(3.0, 6.0), cargas=replace(cp.Cargas(), forcas_horizontais=(forca,)))
    )
    acao = next(a for a in com.acoes if a.nome == "Correia")
    assert acao.valor("V_Y_1") == 30.0 and acao.valor("V_Y_2") == 30.0
    assert abs(_andar(com, "Y", 2).cortante_elu.valor) > abs(_andar(sem, "Y", 2).cortante_elu.valor)
    assert _andar(com, "X", 1).cortante_elu.valor == pytest.approx(
        _andar(sem, "X", 1).cortante_elu.valor
    )


def test_acao_excepcional_governa_quando_e_maior():
    impacto = cp.ForcaHorizontal(
        "Impacto", "X", 1, 300.0, categoria="Ação excepcional (impacto, explosão, incêndio)"
    )
    r = cp.calcular(entrada(cargas=replace(cp.Cargas(), forcas_horizontais=(impacto,))))
    a = _andar(r, "X")
    assert a.cortante_elu.estado_limite == comb.ELU_EXCEPCIONAL
    assert abs(a.cortante_elu.valor) > 300.0


def test_equipamento_entra_no_peso_e_no_vento():
    tanque = va.Equipamento("Vaso", 1, va.FORMA_CILINDRO, 1.5, 1.5, 3.0, peso_kN=120.0)
    sem = cp.calcular(entrada())
    com = cp.calcular(entrada(equipamentos=(tanque,)))
    acao = next(a for a in com.acoes if a.nome == "Equipamentos")
    assert acao.valor("P_1") == 120.0 and acao.gamma == 1.25
    assert com.vento.x.total_kN > sem.vento.x.total_kN


def test_grande_deslocabilidade_reprova():
    fraca = cp.SistemaDeContraventamento(
        diagonal=cb.Diagonal(familia=cb.FAMILIA_BARRA_REDONDA, perfil="Barra circular Ø12.5")
    )
    r = cp.calcular(
        entrada(
            contraventamento_x=fraca,
            contraventamento_y=fraca,
            cargas=replace(cp.Cargas(), sobrecarga_kN_m2=80.0),
        )
    )
    linhas = [v for v in r.verificacoes if "deslocabilidade" in v.nome or "estabilidade" in v.nome]
    assert any(v.status == "NÃO OK" for v in linhas)
    assert r.status == "NÃO OK"


def test_tirante_fora_do_x_so_tracao_e_erro():
    sistema = cp.SistemaDeContraventamento(
        tipo=cp.TIPO_DIAGONAL_SIMPLES,
        diagonal=cb.Diagonal(familia=cb.FAMILIA_BARRA_REDONDA, perfil="Barra circular Ø19"),
    )
    erros = cp.validar_entrada(entrada(contraventamento_y=sistema))
    assert any("só serve para X só tração" in e for e in erros)
    with pytest.raises(cp.ContraventamentoInvalido):
        cp.calcular(entrada(contraventamento_y=sistema))


def test_uma_linha_so_avisa_da_torcao():
    r = cp.calcular(entrada(contraventamento_x=cp.SistemaDeContraventamento(linhas=1)))
    assert any("torção" in a for a in r.avisos)
    assert _andar(r, "X").fracao_da_linha == 1.0


def test_fracao_da_linha_mais_carregada():
    assert cp._fracao_da_linha_mais_carregada(2, 0.075) == pytest.approx(0.575)
    assert cp._fracao_da_linha_mais_carregada(3, 0.0) == pytest.approx(1 / 3)
    assert cp._fracao_da_linha_mais_carregada(3, 0.1) == pytest.approx(1 / 3 + 0.1 * 0.5 / 0.5)


def test_forcas_para_a_ligacao(padrao):
    f = cp.forcas_para_ligacao(padrao)
    gov = padrao.diagonal_governante()
    assert (f.direcao, f.andar) == (gov.direcao, gov.andar)
    assert f.tracao_kN == pytest.approx(gov.tracao_kN)
    assert 0 < f.theta_vertical_graus < 90


# ------------------------------------------------------------------ registro e memorial
def test_registro_cumpre_o_contrato_e_e_serializavel(padrao):
    r = reg.registro_contraventamento(padrao, contexto={"tag": "PL-1"}, responsavel="Ana")
    assert avaliar_contrato_registro(r)["valido"]
    assert r["modulo_id"] == "contraventamento_estrutura"
    assert "PL-1" in r["titulo"]
    assert len(r["resultados"]["tabelas_memorial"]) == 4
    assert r["resultados"]["forcas_para_a_ligacao"]["direcao"] in ("X", "Y")
    json.dumps(r)


def test_memorial_word_e_pdf_trazem_o_contraventamento(padrao):
    projeto = novo_projeto_documento("Plataforma", codigo="PL-01")
    projeto.update({"objetivo": "Contraventar.", "responsavel": "A", "verificador": "B"})
    projeto["registros_tecnicos"] = [
        identificar_peca_registro(reg.registro_contraventamento(padrao), peca="Plataforma P1")
    ]
    modelo = montar_modelo_relatorio(projeto)
    capitulo = next(s for s in modelo["secoes"] if "blocos" in s)
    legendas = " ".join(b["legenda"] for b in capitulo["blocos"] if b.get("tipo") == "tabela")
    assert "Forças do vento por nível" in legendas and "Andares" in legendas
    assert not [
        b
        for b in capitulo["blocos"]
        if b.get("tipo") == "tabela" and "Outros resultados" in b["legenda"]
    ]
    from io import BytesIO

    from docx import Document
    from pypdf import PdfReader

    word = "\n".join(
        p.text for p in Document(BytesIO(gerar_relatorio_industrial_word(projeto))).paragraphs
    )
    pdf = "\n".join(
        p.extract_text() or ""
        for p in PdfReader(BytesIO(gerar_relatorio_industrial_pdf(projeto))).pages
    )
    for texto in (word, pdf):
        assert "Contraventamento de estruturas abertas" in texto
        for proibido in ("Não informado", "bloqueio", "Snapshot", "Apêndice"):
            assert proibido not in texto


def test_media_deslocabilidade_amplifica_com_80_porcento_da_rigidez():
    fraca = cp.SistemaDeContraventamento(
        diagonal=cb.Diagonal(familia=cb.FAMILIA_BARRA_REDONDA, perfil="Barra circular Ø12.5")
    )
    r = cp.calcular(
        entrada(
            contraventamento_x=fraca,
            contraventamento_y=fraca,
            cargas=replace(cp.Cargas(), sobrecarga_kN_m2=40.0),
        )
    )
    a = _andar(r, "X")
    assert a.deslocabilidade == "média"
    n_sd = a.gravidade_elu.valor
    assert a.amplificacao == pytest.approx(1 / (1 - n_sd / (0.8 * a.rigidez_kN_mm * a.altura_mm)))
    assert a.forca_na_linha_kN == pytest.approx(0.575 * abs(a.cortante_elu.valor) * a.amplificacao)
