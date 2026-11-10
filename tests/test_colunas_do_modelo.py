"""Colunas do modelo: os pilares do SolidWorks com os travamentos lidos do esqueleto."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from components.colunas_do_modelo_help import AJUDA
from core import colunas_do_modelo as cdm
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import load_combinations as comb
from core import plano_de_cargas as pc
from core import travamentos_da_coluna as tc
from core import verificacao_barras as vb
from core.project_store import obter_projeto_ativo, salvar_projeto
from tests import portico_3d_teste01 as t
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo
from tests.test_nucleo_esforcos_ponta_a_ponta import montar

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/colunas_do_modelo.py"
ALMA_EM_X = (1.0, 0.0, 0.0)


def corpo(nome, inicio, fim, direcao=None, secao=(200.0, 200.0)):
    return ld.CorpoDoModelo(
        nome,
        "",
        "",
        tuple(float(v) for v in inicio),
        tuple(float(v) for v in fim),
        math.dist(inicio, fim),
        None,
        "BARRA",
        secao,
        direcao,
    )


def esqueleto(*corpos) -> ld.GeometriaDoModelo:
    return ld.GeometriaDoModelo(corpos=tuple(corpos))


def ler(g, nome="P", base=tc.PINO, **kw) -> cdm.PilarNoModelo:
    return cdm.ler_pilar(g, g.corpo(nome), "Y", base, **kw)


# ------------------------------------------------------------------ o pilar no esqueleto
def test_viga_no_meio_trava_so_o_eixo_da_direcao_dela():
    """Pilar de 4 m, alma em X: a viga em X a 2 m trava L_x; as do topo fazem o nó de cima."""
    g = esqueleto(
        corpo("P", (0, 0, 0), (0, 4, 0), ALMA_EM_X),
        corpo("VX meio", (0, 2, 0), (3, 2, 0)),
        corpo("VX topo", (0, 4, 0), (3, 4, 0)),
        corpo("VZ topo", (0, 4, 0), (0, 4, 3)),
    )
    pilar = ler(g)
    assert pilar.orientada and pilar.comprimento_mm == pytest.approx(4000.0)
    assert pilar.alturas("x") == (pytest.approx(2000.0),) and pilar.alturas("y") == ()
    assert (pilar.base, pilar.topo_x, pilar.topo_y) == (tc.PINO, tc.PINO, tc.PINO)
    assert pilar.travamentos[0].descricao == "VX meio"
    x, y = cdm.trechos_do_pilar(pilar)
    assert [t.kl_mm for t in x.trechos] == [pytest.approx(2000.0)] * 2
    assert y.governa.kl_mm == pytest.approx(4000.0)
    # A mesma viga, com a alma na outra direção, passa a travar L_y.
    girado = esqueleto(corpo("P", (0, 0, 0), (0, 4, 0), (0.0, 0.0, 1.0)), *g.corpos[1:])
    assert ler(girado).alturas("y") == (pytest.approx(2000.0),)


def test_pilar_desenhado_de_cima_para_baixo_mede_da_base():
    g = esqueleto(
        corpo("P", (0, 4, 0), (0, 0, 0), ALMA_EM_X),
        corpo("V", (0, 1, 0), (3, 1, 0)),
        corpo("VT", (0, 4, 0), (3, 4, 0)),
    )
    assert ler(g).alturas("x") == (pytest.approx(1000.0),)


def test_vigas_juntas_no_mesmo_no_viram_um_travamento():
    g = esqueleto(
        corpo("P", (0, 0, 0), (0, 4, 0), ALMA_EM_X),
        corpo("VX", (0, 2.0, 0), (3, 2.0, 0)),
        corpo("VZ", (0, 2.05, 0), (0, 2.05, 3)),
        corpo("VT", (0, 4, 0), (3, 4, 0)),
    )
    (trava,) = ler(g).travamentos
    assert trava.trava_x and trava.trava_y and trava.altura_mm == pytest.approx(2025.0)
    assert trava.descricao == "VX, VZ"


def test_base_engastada_no_apoio_e_poste_sobre_viga():
    g = esqueleto(
        corpo("P", (0, 0, 0), (0, 4, 0), ALMA_EM_X),
        corpo("VT", (0, 4, 0), (3, 4, 0)),
        corpo("Poste", (3, 4, 0), (3, 5, 0), ALMA_EM_X),
        corpo("V2", (3, 5, 0), (5, 5, 0)),
    )
    assert ler(g, base=tc.ENGASTE).base == tc.ENGASTE
    poste = ler(g, "Poste", base=tc.ENGASTE)
    assert poste.base == tc.PINO  # o pé está numa viga, não no apoio
    assert any("não está no apoio" in n for n in poste.notas)


def test_topo_solto_e_balanco_e_resto_de_esqueleto_nao_e():
    balanco = esqueleto(
        corpo("P", (0, 0, 0), (0, 4, 0), ALMA_EM_X),
        corpo("VX", (0, 2, 0), (3, 2, 0)),
        corpo("VZ", (0, 2, 0), (0, 2, 3)),
    )
    pilar = ler(balanco, base=tc.ENGASTE)
    assert (pilar.topo_x, pilar.topo_y) == (tc.LIVRE, tc.LIVRE)
    x, _ = cdm.trechos_do_pilar(pilar)
    assert x.governa.pela_coluna_inteira
    # Base rotulada com o topo solto: só fica de pé pelo travamento do meio (pino e topo livre).
    rotulado = ler(balanco, base=tc.PINO)
    x, _ = cdm.trechos_do_pilar(rotulado)
    assert x.governa.pela_coluna_inteira
    assert x.governa.kl_mm == pytest.approx(
        tc.comprimento_de_flambagem(4000.0, [2000.0], tc.PINO, tc.LIVRE)
    )
    # O esqueleto passa 0,30 m da viga do topo: o resto não é balanço.
    sobra = esqueleto(
        corpo("P", (0, 0, 0), (0, 4.3, 0), ALMA_EM_X),
        corpo("VX", (0, 4, 0), (3, 4, 0)),
        corpo("VZ", (0, 4, 0), (0, 4, 3)),
    )
    pilar = ler(sobra)
    assert (pilar.topo_x, pilar.topo_y) == (tc.PINO, tc.PINO)
    assert any("não é balanço" in n for n in pilar.notas)


def test_rotulada_e_solta_sem_travamento_nao_fica_de_pe():
    with pytest.raises(ValueError, match="não fica de pé"):
        tc.trechos_pelas_pontas("x", 4000.0, (), tc.PINO, tc.LIVRE)
    with pytest.raises(ValueError, match="base livre"):
        tc.trechos_pelas_pontas("x", 4000.0, (2000.0,), tc.LIVRE, tc.PINO)
    with pytest.raises(ValueError, match="desconhecida"):
        tc.trechos_pelas_pontas("x", 4000.0, (), "solda", tc.PINO)


@pytest.mark.parametrize(
    ("base", "topo", "apoio"),
    [
        (tc.PINO, tc.PINO, "Biapoiada (pino-pino)"),
        (tc.ENGASTE, tc.PINO, "Engastada-pino"),
        (tc.ENGASTE, tc.LIVRE, "Engastada-livre (em balanço)"),
    ],
)
def test_pelas_pontas_e_o_mesmo_que_pela_condicao_da_tabela(base, topo, apoio):
    for alturas in ((), (1500.0,), (1000.0, 2500.0)):
        a = tc.trechos_pelas_pontas("y", 4000.0, alturas, base, topo)
        b = tc.trechos_do_eixo("y", 4000.0, alturas, apoio, 1.0, True)
        assert a == b


# ------------------------------------------------------------------ o pórtico teste01
@pytest.fixture(scope="module")
def portico():
    dados, _, geometria = montar()
    return dados, geometria, t.plano()


def test_os_quatro_pilares_do_portico(portico):
    dados, geometria, plano = portico
    colunas, _ = cdm.verificar_colunas(dados, geometria, plano, [comb.ELU_NORMAL])
    assert len(colunas) == 4
    for c in colunas:
        assert c.status in ("OK", "ALERTA", "NÃO OK"), c.motivo
        assert c.perfil == t.PILAR and c.pilar is not None and c.pilar.orientada
        assert c.pilar.comprimento_mm == pytest.approx(2000.0)
        assert c.b2 == pytest.approx(1.10)
        # Sem barra no meio, um trecho só: base rotulada e topo no nó, K = 1.
        assert c.eixo_x.governa.kl_mm == pytest.approx(2000.0)
        assert c.eixo_y.governa.kl_mm == pytest.approx(2000.0)


def test_sem_travamento_e_a_mesma_conta_das_barras_do_modelo(portico):
    """Com um trecho só e K = 1, o pilar sai igual à verificação de Esforços do modelo."""
    dados, geometria, plano = portico
    colunas, _ = cdm.verificar_colunas(dados, geometria, plano, [comb.ELU_NORMAL])
    preparo = em.preparar_combinacoes(dados, plano, [comb.ELU_NORMAL])
    for c in colunas:
        combinados, _, _ = em.combinados_do_membro(c.barra, preparo)
        cfg = dados.membros[c.barra]
        direto = vb.verificar_com_comprimentos(
            c.barra,
            cfg,
            combinados,
            b2=1.10,
            aco=dados.parametros_do_tipo("Pilar").aco,
            norma=dados.norma,
            cb=1.0,
            lx_mm=2000.0,
            ly_mm=2000.0,
            lb_mm=2000.0,
        )
        assert c.aproveitamento == pytest.approx(direto.aproveitamento, rel=1e-9)


def test_base_engastada_diminui_o_aproveitamento(portico):
    dados, geometria, plano = portico
    rotulada, _ = cdm.verificar_colunas(dados, geometria, plano, [comb.ELU_NORMAL])
    engastada, _ = cdm.verificar_colunas(
        dados, geometria, plano, [comb.ELU_NORMAL], base=cdm.BASE_ENGASTADA
    )
    for r, e in zip(rotulada, engastada, strict=True):
        assert e.eixo_x.governa.k == pytest.approx(0.8)
        assert e.aproveitamento <= r.aproveitamento + 1e-12


def test_sem_orientacao_testa_as_duas_posicoes(portico):
    dados, geometria, plano = portico
    sem = ld.GeometriaDoModelo(
        corpos=tuple(
            ld.CorpoDoModelo(**{**c.__dict__, "direcao_secao": None}) for c in geometria.corpos
        )
    )
    colunas, _ = cdm.verificar_colunas(dados, sem, plano, [comb.ELU_NORMAL])
    assert all(c.posicao in (cdm.POSICAO_1, cdm.POSICAO_2) for c in colunas)


def test_pilar_sem_perfil_e_sem_esqueleto_fica_pendente(portico):
    dados, geometria, plano = portico
    barra = next(iter(cdm.pilares_do_modelo(dados, ld.ler_barras(dados, geometria, plano)))).barra
    sem_perfil = em.com_membros(dados, {barra: em.ConfiguracaoDoMembro(perfil="", tipo="Pilar")})
    leituras = [
        ld.LeituraDaBarra(**{**le.__dict__, "perfil_sugerido": ""})
        for le in ld.ler_barras(sem_perfil, geometria, plano)
    ]
    colunas, _ = cdm.verificar_colunas(
        sem_perfil, geometria, plano, [comb.ELU_NORMAL], leituras=leituras
    )
    pendente = next(c for c in colunas if c.barra == barra)
    assert pendente.status == cdm.STATUS_PENDENTE and "perfil" in pendente.motivo
    vazio, avisos = cdm.verificar_colunas(dados, geometria, pc.PlanoDeCargas(), [comb.ELU_NORMAL])
    assert vazio == [] and avisos


def test_tabela_csv_e_registro(portico):
    dados, geometria, plano = portico
    colunas, _ = cdm.verificar_colunas(dados, geometria, plano, [comb.ELU_NORMAL])
    linhas = cdm.linhas_da_tabela(colunas)
    assert len(linhas) == 4 and all(len(linha) == len(cdm.COLUNAS) for linha in linhas)
    assert cdm.csv_das_colunas(colunas).decode("utf-8-sig").startswith("Pilar;Perfil")
    registro = cdm.registro_das_colunas(
        colunas, dados, [comb.ELU_NORMAL], base=cdm.BASE_ROTULADA, recomendado=True
    )
    json.dumps(registro)
    assert registro["modulo_id"] == cdm.MODULO_ID
    assert "4 pilares do modelo" in registro["resultados"]["destaque_memorial"]


# ------------------------------------------------------------------ a página
def test_toda_ajuda_e_usada_e_termina_com_ponto():
    usadas = set(
        re.findall(r'AJUDA\["([A-Za-z_0-9]+)"\]', (RAIZ / PAGINA).read_text(encoding="utf-8"))
    )
    assert usadas == set(AJUDA)
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and texto[-1] in ".!:", chave


def abrir() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page(PAGINA)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def test_pagina_sem_modelo_aponta_para_esforcos_do_modelo(banco_com_projeto):
    at = abrir()
    assert any("Esforços do modelo" in i.value for i in at.info)


def test_pagina_com_o_portico(banco_com_projeto):
    dados, apoios, geometria = montar()
    projeto = obter_projeto_ativo()
    projeto["plano_de_cargas"] = pc.para_dicionario(t.plano())
    projeto["esforcos_do_modelo"] = em.para_dicionario(dados)
    projeto["geometria_do_modelo"] = ld.para_dicionario(geometria)
    salvar_projeto(projeto, motivo="teste")
    at = abrir()
    metricas = {m.label: m.value for m in at.metric}
    assert metricas["Pilares"] == "4" and metricas["Pendentes"] == "0"
    tabela = next(d.value for d in at.dataframe if "Travado em L_x (m)" in d.value.columns)
    assert len(tabela) == 4
    at.radio(key="cdm_base").set_value(cdm.BASE_ENGASTADA).run()
    assert not at.exception
    tabela = next(d.value for d in at.dataframe if "K·L_x (m)" in d.value.columns)
    assert set(tabela["K·L_x (m)"]) == {"1,60"}
    at.toggle(key="cdm_ver_desenho").set_value(True).run()
    assert not at.exception
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in at.get(tipo) if not _ajuda(e)
    }
    sem_ajuda -= {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
