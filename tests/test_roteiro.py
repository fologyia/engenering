"""Roteiro do projeto: os passos na ordem de sempre e a situação a partir do projeto ativo."""

from __future__ import annotations

from core import plano_de_cargas as pc
from core import roteiro as rt
from core.project_store import novo_projeto_documento


def test_passos_numerados_na_ordem_e_com_o_que_entra_e_sai():
    assert [p.numero for p in rt.PASSOS] == list(range(1, len(rt.PASSOS) + 1))
    assert [p.fase for p in rt.PASSOS] == sorted((p.fase for p in rt.PASSOS), key=rt.FASES.index)
    for p in rt.PASSOS:
        assert p.titulo and p.entra and p.sai and p.fazer and p.conferir
        assert (p.pagina is None) == (p.onde == rt.SOLIDWORKS)
    # Os arquivos de cada lado: a lista de corte e o esqueleto, o gerenciador, forças e reações.
    texto = " ".join(f"{p.entra} {p.sai}" for p in rt.PASSOS)
    for arquivo in ("_esqueleto.csv", "_lista_de_corte.csv", "-forcas.csv", "-reacoes.csv"):
        assert arquivo in texto


def test_sem_projeto_comeca_pelo_passo_1():
    situacoes = rt.situacoes(None)
    assert situacoes[0].feito is False and rt.proximo_passo(situacoes) == 1


def test_projeto_novo_continua_pela_base_tecnica():
    projeto = novo_projeto_documento("Plataforma", codigo="NTI-1")
    situacoes = rt.situacoes(projeto)
    assert len(situacoes) == len(rt.PASSOS)
    assert situacoes[0].feito is True and situacoes[1].feito is False
    assert rt.proximo_passo(situacoes) == 2
    # Os passos só no SolidWorks não têm rastro: nem feitos nem pendentes.
    assert situacoes[6].feito is None and situacoes[7].feito is None


def test_vento_no_plano_marca_o_passo_5():
    projeto = novo_projeto_documento("Plataforma", codigo="NTI-1")
    plano = pc.PlanoDeCargas()
    for acao in pc.acoes_de_vento("t", {"X": [pc.CargaDoModelo("P1", 1.0, "kN", "X")]}):
        plano = pc.com_acao(plano, acao)
    projeto["plano_de_cargas"] = pc.para_dicionario(plano)
    situacao = rt.situacoes(projeto)[4]
    assert situacao.feito is True and "W0" in situacao.texto
