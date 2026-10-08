"""Ligação de contraventamento (chapa de nó, UFM + AISC 360-16) contra o Exemplo 5.1 do DG29.

Os dados do guia estão em polegadas, kips e ksi; o teste converte para o SI do programa. As
resistências do guia (LRFD e ASD) são reproduzidas dentro de arredondamento de tabela.
"""

from __future__ import annotations

import json
import math

import pytest

from core import contraventamento_chapa as ch
from core import contraventamento_ligacao as lig
from core import contraventamento_registro as reg
from core import contraventamento_ufm as ufm
from core.verificacao import status_geral

KIP = 4.448222
POL = 25.4
KSI = 6.894757


def _perfis() -> tuple[ch.PerfilDoNo, ch.PerfilDoNo]:
    viga = ch.PerfilDoNo(
        "W21x83",
        21.4 * POL,
        0.515 * POL,
        0.835 * POL,
        8.36 * POL,
        1.34 * POL,
        50 * KSI,
        196 * POL**3,
        1830 * POL**4,
        65 * KSI,
    )
    coluna = ch.PerfilDoNo(
        "W14x90",
        14.0 * POL,
        0.440 * POL,
        0.710 * POL,
        14.5 * POL,
        1.0 * POL,
        50 * KSI,
        157 * POL**3,
        999 * POL**4,
        65 * KSI,
    )
    return viga, coluna


def exemplo_5_1(metodo: str = ch.METODO_LRFD, **troca) -> lig.EntradaLigacao:
    """Exemplo 5.1 do DG29: contraventamento de 840 kips (LRFD) / 560 kips (ASD), tanθ = 1,08."""
    viga, coluna = _perfis()
    f = 1.0 if metodo == ch.METODO_LRFD else 560 / 840
    dados = dict(
        perfil_viga=viga,
        perfil_coluna=coluna,
        metodo=metodo,
        P_tracao_kN=840 * f * KIP,
        P_compressao_kN=840 * f * KIP,
        theta_graus=math.degrees(math.atan(1.08)),
        reacao_viga_kN=50 * f * KIP,
        transferencia_kN=100 * f * KIP,
        t_chapa_mm=1.0 * POL,
        Fy_chapa_MPa=50 * KSI,
        Fu_chapa_MPa=65 * KSI,
        lh_mm=32.25 * POL,
        corte_h_mm=0.75 * POL,
        lv_mm=24.0 * POL,
        corte_v_mm=0.0,
        t_chapa_de_topo_mm=1.0 * POL,
        designacao_do_parafuso='7/8"',
        grau_do_parafuso="A325",
        rosca_no_plano=False,
        planos_de_corte=2,
        fileiras=2,
        por_fileira=7,
        passo_mm=3 * POL,
        gabarito_mm=3 * POL,
        extremidade_mm=1.5 * POL,
        comprimento_de_flambagem_mm=9.76 * POL,
        K_flambagem=0.5,
        trecho_whitmore_na_alma_mm=4.7 * POL,
        perna_na_viga_mm=7 / 16 * POL,
        perna_na_coluna_mm=7 / 16 * POL,
    )
    dados.update(troca)
    return lig.EntradaLigacao(**dados)


def _linha(r: lig.ResultadoLigacao, trecho: str):
    achadas = [v for v in r.verificacoes if trecho in v.nome]
    assert len(achadas) == 1, (trecho, [v.nome for v in r.verificacoes])
    return achadas[0]


@pytest.fixture(scope="module")
def lrfd() -> lig.ResultadoLigacao:
    return lig.calcular_ligacao(exemplo_5_1())


@pytest.fixture(scope="module")
def asd() -> lig.ResultadoLigacao:
    return lig.calcular_ligacao(exemplo_5_1(ch.METODO_ASD))


@pytest.mark.parametrize(
    ("trecho", "solicitante", "resistente"),
    [
        ("Parafusos do contraventamento", 840.0, 855.3),
        ("escoamento da seção de Whitmore", 840.0, 967.7),
        ("cisalhamento de bloco", 840.0, 858.2),
        ("flambagem da seção de Whitmore", 840.0, 967.7),
    ],
)
def test_chapa_e_parafusos_do_exemplo_5_1_lrfd(lrfd, trecho, solicitante, resistente):
    v = _linha(lrfd, trecho)
    assert v.status == "OK"
    assert v.solicitante / KIP == pytest.approx(solicitante, rel=0.002)
    assert v.resistente / KIP == pytest.approx(resistente, rel=0.01)


def test_forcas_nas_interfaces_do_exemplo_5_1(lrfd):
    f = lrfd.forcas
    assert f.viga_cisalhamento_kN / KIP == pytest.approx(440.4, rel=0.005)
    assert f.coluna_cisalhamento_kN / KIP == pytest.approx(301.7, rel=0.005)
    assert f.coluna_normal_kN / KIP == pytest.approx(176.0, rel=0.005)
    assert f.vc_cisalhamento_kN / KIP == pytest.approx(319.0, rel=0.005)
    assert lrfd.alfa_real_mm / POL == pytest.approx(17.5, abs=0.01)
    assert lrfd.beta_real_mm / POL == pytest.approx(12.0, abs=0.01)


def test_soldas_do_exemplo_5_1(lrfd):
    viga = _linha(lrfd, "Solda chapa–viga: perna necessária")
    coluna = _linha(lrfd, "Solda chapa–coluna: perna necessária")
    assert viga.solicitante == pytest.approx(9.83, abs=0.1)
    assert coluna.solicitante == pytest.approx(8.80, abs=0.1)
    assert viga.status == coluna.status == "OK"


def test_lrfd_e_asd_dao_o_mesmo_aproveitamento(lrfd, asd):
    """As forças do ASD são as do LRFD × 560/840 e as resistências, as do LRFD × (Ω·φ)^-1."""
    assert asd.aproveitamento_maximo == pytest.approx(lrfd.aproveitamento_maximo, rel=0.02)
    assert [v.status for v in asd.verificacoes] == [v.status for v in lrfd.verificacoes]
    assert _linha(asd, "Parafusos do contraventamento").resistente / KIP == pytest.approx(
        570.2, rel=0.01
    )


def test_o_exemplo_fecha_e_so_alerta_a_mesa_da_coluna(lrfd):
    assert lrfd.aproveitamento_maximo < 1.0
    nao_ok = [v.nome for v in lrfd.verificacoes if v.status == "NÃO OK"]
    assert not nao_ok
    assert [v.nome for v in lrfd.verificacoes if v.status == "ALERTA"] == [
        "Mesa da coluna: flexão local sob a normal H_c (tração)"
    ]
    assert status_geral(list(lrfd.verificacoes)) == "ALERTA"


def test_chapa_fina_reprova_em_todos_os_estados_limites_da_chapa():
    r = lig.calcular_ligacao(exemplo_5_1(t_chapa_mm=6.0))
    assert status_geral(list(r.verificacoes)) == "NÃO OK"
    assert _linha(r, "escoamento da seção de Whitmore").status == "NÃO OK"
    assert r.aproveitamento_maximo > 1.0


def test_solda_pequena_reprova():
    r = lig.calcular_ligacao(exemplo_5_1(perna_na_viga_mm=3.0))
    assert _linha(r, "Solda chapa–viga: perna necessária").status == "NÃO OK"


def test_parafusos_a_mais_aliviam_o_grupo():
    pouco = lig.calcular_ligacao(exemplo_5_1(por_fileira=5))
    muito = lig.calcular_ligacao(exemplo_5_1(por_fileira=9))
    grupo = "Parafusos do contraventamento"
    assert _linha(muito, grupo).aproveitamento < _linha(pouco, grupo).aproveitamento


def test_so_tracao_nao_verifica_flambagem():
    r = lig.calcular_ligacao(exemplo_5_1(P_compressao_kN=0.0))
    assert not [v for v in r.verificacoes if "flambagem da seção de Whitmore" in v.nome]


def test_caso_especial_3_nao_tem_linhas_da_coluna():
    r = lig.calcular_ligacao(
        exemplo_5_1(caso=ufm.CASO_3, theta_graus=60.0, lv_mm=0.0, corte_v_mm=0.0)
    )
    assert not [
        v for v in r.verificacoes if v.nome.startswith(("Chapa–coluna", "Solda chapa–coluna"))
    ]
    assert r.solda_coluna is None


def test_caso_especial_2_aceita_o_alivio_da_vertical():
    base = lig.calcular_ligacao(exemplo_5_1())
    aliviado = lig.calcular_ligacao(exemplo_5_1(caso=ufm.CASO_2, anular_Vb=True))
    assert aliviado.forcas.vc_cisalhamento_kN < base.forcas.vc_cisalhamento_kN


def test_distorcao_adiciona_forca_na_ligacao_viga_coluna():
    com = lig.calcular_ligacao(
        exemplo_5_1(
            considerar_distorcao=True,
            area_do_contraventamento_mm2=40.0 * POL**2,
            b_viga_mm=180.0 * POL,
            c_coluna_mm=75.0 * POL,
        )
    )
    assert com.distorcao is not None and com.distorcao.HD_kN > 0


@pytest.mark.parametrize(
    ("troca", "trecho"),
    [
        ({"P_tracao_kN": 0.0, "P_compressao_kN": 0.0}, "força"),
        ({"theta_graus": 90.0}, "θ"),
        ({"theta_graus": 0.0}, "θ"),
        ({"t_chapa_mm": 0.0}, "espessura"),
        ({"corte_h_mm": 40.0 * POL}, "corte"),
        ({"planos_de_corte": 3}, "plano"),
        ({"grau_do_parafuso": "A999"}, "Grau"),
        ({"designacao_do_parafuso": "9/9"}, "Parafuso"),
        ({"metodo": "XYZ"}, "Método"),
        ({"considerar_distorcao": True}, "distorção"),
    ],
)
def test_entrada_impossivel_vira_erro_claro(troca, trecho):
    erros = lig.validar_entrada(exemplo_5_1(**troca))
    assert erros and any(trecho.lower() in e.lower() for e in erros), erros
    with pytest.raises(ch.ChapaInvalida):
        lig.calcular_ligacao(exemplo_5_1(**troca))


# ------------------------------------------------------------------ registro
def test_registro_leva_entradas_verificacoes_e_tabelas(lrfd):
    registro = reg.registro_ligacao(
        lrfd, contexto={"tag": "LC-1", "obra": "Galpão 3"}, responsavel="Ana"
    )
    assert registro["modulo_id"] == "ligacao_contraventamento"
    assert registro["entradas"]["tag"] == "LC-1"
    assert registro["entradas"]["viga"] == "W21x83"
    assert registro["status"] == "Atenção"
    resultados = registro["resultados"]
    assert resultados["status_geral"] == "ALERTA"
    assert len(resultados["verificações"]) == len(lrfd.verificacoes)
    assert [t["cabecalhos"][0] for t in resultados["tabelas_memorial"]] == ["Interface", "Grandeza"]
    json.dumps(registro)  # serializável


def test_tabela_das_interfaces_traz_as_forcas_do_exemplo(lrfd):
    forcas = reg.tabelas_para_memorial(lrfd)[0]["linhas"]
    assert [linha[0] for linha in forcas] == [
        "Contraventamento–chapa",
        "Chapa–viga",
        "Chapa–coluna",
        "Viga–coluna",
    ]
    assert float(forcas[1][1].replace(",", ".")) == pytest.approx(
        lrfd.forcas.viga_cisalhamento_kN, abs=0.06
    )


def test_registro_do_caso_3_nao_inventa_coluna():
    r = lig.calcular_ligacao(
        exemplo_5_1(caso=ufm.CASO_3, theta_graus=60.0, lv_mm=0.0, corte_v_mm=0.0)
    )
    linhas = reg.tabelas_para_memorial(r)[0]["linhas"]
    assert "Chapa–coluna" not in [linha[0] for linha in linhas]
    entradas = reg.registro_ligacao(r)["entradas"]
    assert "lv_da_chapa_mm" not in entradas


def test_registro_avisa_o_que_ficou_fora_do_escopo(lrfd):
    alertas = " ".join(reg.registro_ligacao(lrfd)["alertas"])
    assert "Fora do escopo" in alertas and "hapa de topo" in alertas
