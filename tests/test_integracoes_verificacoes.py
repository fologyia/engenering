"""As verificações complementares integradas nas páginas que já existiam.

- Roteiro do projeto: aba "Verificações complementares" com a triagem pelo projeto;
- Flambagem de colunas: travamentos exigidos (4.12.2) e o caminho para a Contenção lateral;
- (Vigas de piso: em tests/test_viga_de_piso.py.)
"""

from __future__ import annotations

import pytest

from core import contencao_lateral as cl
from core import verificacoes_do_projeto as vdp
from tests import apoio_paginas as ap


def _projeto(**extra) -> dict:
    return {"nome": "Teste", "registros_tecnicos": [], **extra}


def test_sem_projeto_tudo_fica_quando_houver():
    lista = vdp.sugestoes(None)
    assert [s.situacao for s in lista] == [vdp.SE_HOUVER] * len(vdp.VERIFICACOES)
    assert {s.verificacao.pagina for s in lista} == {v.pagina for v in vdp.VERIFICACOES}


def test_cada_verificacao_aponta_para_uma_pagina_que_existe():
    for v in vdp.VERIFICACOES:
        assert (ap.RAIZ / v.pagina).exists(), v.pagina


def test_plano_com_monovia_indica_monovia_e_fadiga():
    projeto = _projeto(plano_de_cargas={"acoes": [{"codigo": "MO"}, {"codigo": "EQ"}]})
    por_id = {s.verificacao.modulo_id: s for s in vdp.sugestoes(projeto)}
    assert por_id["monovia"].situacao == vdp.INDICADA
    assert "monovia" in por_id["fadiga_estrutural"].motivo
    assert por_id["forcas_localizadas"].situacao == vdp.INDICADA
    assert por_id["incendio"].situacao == vdp.SE_HOUVER


def test_lista_de_material_com_tubo_e_perfil_dobrado():
    projeto = _projeto(
        lista_de_material={"itens": [{"descricao": "TC ideal Ø60,3×3"},
                                     {"descricao": "Ue 200x75x20x2,65"},
                                     {"descricao": "Cantoneira 2x3/16"}]}
    )  # fmt: skip
    por_id = {s.verificacao.modulo_id: s for s in vdp.sugestoes(projeto)}
    assert por_id["nos_tubulares"].situacao == vdp.INDICADA
    assert por_id["tercas_formadas_a_frio"].situacao == vdp.INDICADA


def test_registros_vigentes_contam_e_os_superados_nao():
    projeto = _projeto(
        registros_tecnicos=[
            {"modulo_id": "monovia"},
            {"modulo_id": "incendio", "superado_em": "2026-01-01"},
            {"modulo_id": "flambagem_colunas"},
        ]
    )
    por_id = {s.verificacao.modulo_id: s for s in vdp.sugestoes(projeto)}
    assert por_id["monovia"].situacao == vdp.REGISTRADA and por_id["monovia"].registros == 1
    assert por_id["incendio"].situacao == vdp.SE_HOUVER
    assert por_id["contencao_lateral"].situacao == vdp.INDICADA
    assert vdp.resumo(list(por_id.values()))[vdp.REGISTRADA] == 1


@pytest.mark.parametrize("ruim", [None, {"plano_de_cargas": "x", "lista_de_material": [1]},
                                  {"registros_tecnicos": "x"}])  # fmt: skip
def test_dados_estragados_nao_quebram(ruim):
    assert len(vdp.sugestoes(ruim)) == len(vdp.VERIFICACOES)


def test_aba_do_roteiro(banco_com_projeto):
    t = ap.abrir("app_pages/roteiro_projeto.py")
    assert [a.label for a in t.tabs] == ["Passo a passo", "Verificações complementares"]
    assert any("Verificações complementares de estrutura metálica" == s.value for s in t.subheader)
    assert not ap.sem_ajuda(t), ap.sem_ajuda(t)


def test_coluna_mostra_o_travamento_exigido_e_leva_a_contencao(banco_isolado):
    t = ap.abrir("app_pages/flambagem_colunas.py", col_trav_ativar=True)
    assert "Travamentos que a coluna exige (NBR 8800 4.12)" in [s.value for s in t.subheader]
    n_sd = t.session_state["col_nsd"] if "col_nsd" in t.session_state else None
    t.button(key="col_ir_contencao").click().run()
    assert not t.exception
    assert t.session_state["cl_caso"] == cl.PILAR
    assert t.number_input(key="cl_N_Sd").value == pytest.approx(t.session_state["cl_N_Sd"])
    assert t.session_state["cl_L_b"] > 0 and t.session_state["cl_n"] >= 1
    assert not t.warning or all("Session State" not in w.value for w in t.warning)
    if n_sd is not None:
        assert t.session_state["cl_N_Sd"] > 0
