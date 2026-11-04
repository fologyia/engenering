"""As 2 cantoneiras em T na página de contraventamento (pedido de 04/11/2026).

A compressão tem de dar o mesmo que a Flambagem de colunas; a tração, a solda e o rasgamento são o
dobro da cantoneira simples; os parafusos passam a trabalhar em corte duplo.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from core import bolted_connection as bc
from core import cantoneiras as ct
from core import column_buckling as cbk
from core import contraventamento_barras as cb
from core import contraventamento_do_esqueleto as ce
from core import contraventamento_plataforma as cp
from core import perfis_compostos as pc

PERFIL = 'L 2 1/2" × 1/4"'
SIMPLES = cb.Diagonal(perfil=PERFIL)
DUPLA = cb.Diagonal(familia=cb.FAMILIA_2_CANTONEIRAS, perfil=PERFIL)
L_MM = 3000.0


def verificar(
    d: cb.Diagonal, *, tracao: float = 0.0, compressao: float = 0.0, lb: float = L_MM, **kw
):
    return cb.verificar_diagonal(
        d, "X", comprimento_mm=2 * lb, comprimento_destravado_mm=lb, tracao_kN=tracao,
        compressao_kN=compressao, **kw,
    )  # fmt: skip


def linha(resultado: cb.ResultadoDiagonal, trecho: str):
    return next(v for v in resultado.verificacoes if trecho in v.nome)


def tem_linha(resultado: cb.ResultadoDiagonal, trecho: str) -> bool:
    return any(trecho in v.nome for v in resultado.verificacoes)


def test_familia_aceita_as_cantoneiras_da_serie():
    assert cb.perfis_da_familia(cb.FAMILIA_2_CANTONEIRAS) == list(ct.CATALOGO_CANTONEIRAS)
    assert cb.validar(DUPLA) == []


def test_o_esqueleto_continua_lendo_cantoneira_como_simples():
    assert ce._familia(PERFIL) == cb.FAMILIA_CANTONEIRA


def test_area_dobra_e_a_largura_vista_pelo_vento_nao_muda():
    assert cb.area_bruta_mm2(DUPLA) == pytest.approx(2 * cb.area_bruta_mm2(SIMPLES))
    assert cb.largura_vista_mm(DUPLA) == cb.largura_vista_mm(SIMPLES)


def test_o_afastamento_e_a_espessura_da_chapa_de_no():
    d = replace(DUPLA, t_chapa_no_mm=12.5)
    assert cb.secao_de_2_cantoneiras(d).dims["s"] == 12.5


@pytest.mark.parametrize(
    ("campos", "mensagem"),
    [
        ({"ligacao_dos_espacadores": "cola"}, "espaçador desconhecida"),
        ({"espacadores": -1}, "negativa"),
    ],
)
def test_dados_invalidos(campos, mensagem):
    with pytest.raises(cb.DiagonalInvalida, match=mensagem):
        verificar(replace(DUPLA, **campos), compressao=10.0)


# ------------------------------------------------------------------ tração e ligação
@pytest.mark.parametrize("ligacao", cb.LIGACOES)
def test_tracao_e_o_dobro_da_simples(ligacao):
    simples = verificar(replace(SIMPLES, ligacao=ligacao), tracao=10.0)
    dupla = verificar(replace(DUPLA, ligacao=ligacao), tracao=10.0)
    assert dupla.resistencia_tracao_kN == pytest.approx(2 * simples.resistencia_tracao_kN)


def test_solda_tem_quatro_cordoes():
    medidas = dict(ligacao=cb.LIGACAO_SOLDADA)
    simples = verificar(replace(SIMPLES, **medidas), tracao=10.0)
    dupla = verificar(replace(DUPLA, **medidas), tracao=10.0)
    assert dupla.resistencia_da_ligacao_kN == pytest.approx(2 * simples.resistencia_da_ligacao_kN)
    assert "4 cordões" in linha(dupla, "solda da diagonal").formula


def test_parafusos_em_corte_duplo_com_o_contato_da_chapa():
    d = replace(DUPLA, borda_mm=40.0, passo_mm=60.0)
    resultado = verificar(d, tracao=10.0)
    db = bc.PARAFUSOS[d.parafuso][0]
    dh = bc.PARAFUSOS[d.parafuso][1]
    cant = ct.obter_cantoneira(PERFIL)
    fv = bc.resist_corte(db, d.grau, cb.NORMA, rosca_no_plano=True, n_planos=2)
    chapa = bc.resist_contato(db, d.t_chapa_no_mm, 400.0, None, cb.NORMA)
    extremo = min(
        2 * bc.resist_contato(db, cant.t_mm, 400.0, bc.lf_borda(40.0, dh), cb.NORMA), chapa
    )
    interno = min(
        2 * bc.resist_contato(db, cant.t_mm, 400.0, bc.lf_entre_furos(60.0, dh), cb.NORMA), chapa
    )
    esperado = min(fv, extremo) + 2 * min(fv, interno)
    assert linha(resultado, "parafusos da diagonal").resistente == pytest.approx(esperado)
    assert "2 planos de corte" in linha(resultado, "parafusos da diagonal").formula
    assert "2 abas" in linha(resultado, "parafusos da diagonal").formula


def test_rasgamento_soma_as_duas_abas():
    simples = verificar(SIMPLES, tracao=10.0)
    dupla = verificar(DUPLA, tracao=10.0)
    rasgamento = "colapso por rasgamento"
    assert linha(dupla, rasgamento).resistente == pytest.approx(
        2 * linha(simples, rasgamento).resistente
    )


# ------------------------------------------------------------------ compressão
@pytest.mark.parametrize(
    ("ligacao", "lb"),
    [
        (pc.LIGACAO_APERTO_NORMAL, 3000.0),
        (pc.LIGACAO_RIGIDA, 3000.0),
        (pc.LIGACAO_APERTO_NORMAL, 1500.0),
    ],
)
def test_compressao_bate_com_a_flambagem_de_colunas(ligacao, lb):
    d = replace(DUPLA, ligacao_dos_espacadores=ligacao)
    resultado = verificar(d, compressao=20.0, lb=lb)
    coluna = cbk.verificar_coluna(
        cbk.EntradaColuna(
            secao=cb.secao_de_2_cantoneiras(d), fy_MPa=250.0, norma="NBR8800_2024", Lx_mm=lb,
            Ly_mm=lb, N_Sd_kN=20.0, ligacoes=pc.LigacoesDaComposta(lb, ligacao),
        )
    )  # fmt: skip
    assert resultado.resistencia_compressao_kN == pytest.approx(coluna.compressao["Nc_Rd"])


def test_compressao_e_maior_que_duas_simples_excentricas():
    simples = verificar(SIMPLES, compressao=10.0)
    dupla = verificar(DUPLA, compressao=10.0)
    assert dupla.resistencia_compressao_kN > 2 * simples.resistencia_compressao_kN


def test_espacadores_automaticos_atendem_o_limite():
    resultado = verificar(DUPLA, compressao=20.0)
    distancia = linha(resultado, "distância entre espaçadores")
    assert distancia.status == "OK" and distancia.solicitante <= distancia.resistente
    assert linha(resultado, "quantidade de espaçadores").status == "OK"
    assert "5.3.6.1" in distancia.referencia


def test_espacadores_de_menos_reprovam():
    r = verificar(replace(DUPLA, espacadores=1), compressao=20.0, lb=6000.0)
    assert linha(r, "distância entre espaçadores").status == "NÃO OK"
    assert linha(r, "quantidade de espaçadores").status == "NÃO OK"


def test_mais_espacadores_aumentam_a_forca_de_flambagem_em_y():
    poucos = verificar(replace(DUPLA, espacadores=3), compressao=20.0, lb=1500.0)
    muitos = verificar(replace(DUPLA, espacadores=9), compressao=20.0, lb=1500.0)
    assert muitos.resistencia_compressao_kN >= poucos.resistencia_compressao_kN
    assert "(ℓ/r_mín)²" in linha(poucos, "redução pelos espaçadores").formula


def test_pontas_sem_protensao_reprovam_na_compressao():
    r = verificar(replace(DUPLA, pontas_protendidas=False), compressao=20.0)
    assert linha(r, "ligações das pontas").status == "NÃO OK"
    assert "5.3.6.2" in linha(r, "ligações das pontas").referencia


def test_parafuso_a307_nao_se_protende():
    r = verificar(replace(DUPLA, grau="A307"), compressao=20.0)
    pontas = linha(r, "ligações das pontas")
    assert pontas.status == "NÃO OK" and "A307" in pontas.formula


def test_ponta_soldada_nao_pede_protensao():
    d = replace(DUPLA, ligacao=cb.LIGACAO_SOLDADA, pontas_protendidas=False)
    assert linha(verificar(d, compressao=20.0), "ligações das pontas").status == "OK"


# ------------------------------------------------------------------ só tração
def test_so_tracao_usa_o_limite_de_300_sem_minimo_de_espacadores():
    cant = ct.obter_cantoneira(PERFIL)
    r = verificar(DUPLA, tracao=20.0, lb=2000.0)
    assert 2000.0 / cant.r_z_mm < 300.0
    distancia = linha(r, "distância entre espaçadores")
    assert distancia.resistente == 300.0 and distancia.status == "OK"
    assert "0 espaçadores" in distancia.formula and "5.2.8.2" in distancia.referencia
    assert not tem_linha(r, "ligações das pontas")
    assert not tem_linha(r, "quantidade de espaçadores")


def test_so_tracao_comprida_pede_espacador():
    r_min = ct.obter_cantoneira(PERFIL).r_z_mm
    lb = 300.0 * r_min * 1.5
    assert pc.espacadores_na_tracao(lb, r_min) == 1
    assert pc.espacadores_na_tracao(300.0 * r_min, r_min) == 0
    r = verificar(replace(DUPLA, espacadores=0), tracao=20.0, lb=lb)
    assert linha(r, "distância entre espaçadores").status == "NÃO OK"
    assert linha(verificar(DUPLA, tracao=20.0, lb=lb), "distância entre espaçadores").status == "OK"


def test_cantoneira_simples_nao_ganha_linhas_de_espacador():
    r = verificar(SIMPLES, tracao=20.0, compressao=20.0)
    assert not tem_linha(r, "espaçadores")


def test_criterio_anglo_vale_para_as_2_cantoneiras():
    r = verificar(DUPLA, tracao=20.0, compressao=20.0, criterio_anglo=True)
    assert linha(r, "espessura mínima da cantoneira").status == "OK"
    assert tem_linha(r, "redução do comprimento da cantoneira")
    assert tem_linha(r, "diâmetro mínimo do parafuso")
    assert tem_linha(r, "capacidade mínima da ligação")


# ------------------------------------------------------------------ a estrutura inteira
def _entrada(diagonal: cb.Diagonal, tipo: str) -> cp.EntradaContraventamento:
    sistema = cp.SistemaDeContraventamento(tipo, diagonal, 2, 1)
    return replace(
        cp.EntradaContraventamento(), contraventamento_x=sistema, contraventamento_y=sistema
    )


@pytest.mark.parametrize(
    "tipo", [cp.TIPO_X_TRACAO, cp.TIPO_X_TRACAO_COMPRESSAO, cp.TIPO_DIAGONAL_SIMPLES]
)
def test_a_estrutura_inteira_calcula_com_2_cantoneiras(tipo):
    resultado = cp.calcular(_entrada(DUPLA, tipo))
    nomes = [v.nome for v in resultado.verificacoes]
    assert any("distância entre espaçadores" in nome for nome in nomes)


def test_2_cantoneiras_enrijecem_o_contraventamento():
    simples = cp.calcular(_entrada(SIMPLES, cp.TIPO_X_TRACAO_COMPRESSAO))
    dupla = cp.calcular(_entrada(DUPLA, cp.TIPO_X_TRACAO_COMPRESSAO))
    topo_simples = max(simples.deslocamento_topo_mm.values())
    topo_dupla = max(dupla.deslocamento_topo_mm.values())
    assert topo_dupla == pytest.approx(topo_simples / 2, rel=0.25)
