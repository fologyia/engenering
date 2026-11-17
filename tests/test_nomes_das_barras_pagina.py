"""A página Nomes das barras pela interface (AppTest)."""

from __future__ import annotations

import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

from components.nomes_das_barras_help import AJUDA
from core import leitura_do_modelo as ld
from core import nomes_das_barras as nb
from core import papel_pelo_nome as pn
from core import plano_de_cargas as pc
from core.project_store import obter_projeto_ativo, salvar_projeto
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo
from tests.test_nomes_das_barras import plataforma

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/nomes_das_barras.py"


def abrir(**estado) -> AppTest:
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page(PAGINA)
    for chave, valor in estado.items():
        t.session_state[chave] = valor
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    return t


def com_esqueleto(**mais) -> dict:
    projeto = obter_projeto_ativo()
    projeto["geometria_do_modelo"] = ld.para_dicionario(plataforma())
    projeto.update(mais)
    salvar_projeto(projeto, motivo="teste: esqueleto da plataforma")
    return obter_projeto_ativo()


def tabela(t: AppTest, coluna: str):
    return next(d.value for d in t.dataframe if coluna in d.value.columns)


def test_todo_texto_de_ajuda_e_usado():
    usadas = set(
        re.findall(r'AJUDA\["([A-Za-z_0-9]+)"\]', (RAIZ / PAGINA).read_text(encoding="utf-8"))
    )
    assert usadas == set(AJUDA)
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and 15 < len(texto) <= 900, chave


def test_sem_projeto_pede_um(banco_isolado):
    t = abrir()
    assert any("Nenhum projeto ativo" in i.value for i in t.info)


def test_sem_esqueleto_oferece_a_macro_da_lista_de_corte(banco_com_projeto):
    t = abrir()
    rotulos = [b.proto.label for b in t.get("download_button")]
    assert rotulos == [f"Macro da lista de corte ({ld.VERSAO_ATUAL_DA_MACRO})"]
    assert any("Sem o esqueleto do modelo" in c.value for c in t.caption)


def test_pagina_com_o_esqueleto_e_ajuda_em_tudo(banco_com_projeto):
    com_esqueleto()
    t = abrir()
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
    metricas = {m.label: m.value for m in t.metric}
    assert metricas["Corpos"] == "19"
    assert metricas["Já dizem o papel"] == "2"  # "Diagonal sobe" e "Diagonal desce"
    assert metricas["Mudam de nome"] == "19" and metricas["Nome contradiz a posição"] == "0"
    nomes = tabela(t, "Corpo no SolidWorks").set_index("Corpo no SolidWorks")["Nome"]
    assert nomes["Aparar/Estender12[2]"] == "P-A1" and nomes["Chapa1"] == "PS-N1-01"
    perfis = tabela(t, "Perfil a gravar")
    assert set(perfis["Item"]) == {"W8x31<1>", "C8x13.75<2>", "C6<3>", "L<4>"}
    rotulos = [b.proto.label for b in t.get("download_button")]
    assert "Arquivo de nomes (plataforma_nomes.csv)" in rotulos
    assert "Macro renomear_corpos.bas" in rotulos
    assert len(t.get("image")) == 1  # a planta
    assert any("cada nome é único" in s.value for s in t.success)


def test_papel_escolhido_refaz_o_nome(banco_com_projeto):
    projeto = com_esqueleto()
    escolhas = nb.Escolhas(eixo_vertical="Y", papeis={"Membro estrutural3[1]": "C"})
    t = abrir(nb_escolhas=(str(projeto.get("id") or ""), escolhas))
    linhas = tabela(t, "Corpo no SolidWorks").set_index("Corpo no SolidWorks")
    assert linhas.loc["Membro estrutural3[1]", "Nome"] == "C-N1-01"
    assert linhas.loc["Membro estrutural3[1]", "Papel"] == pn.CONTRAVENTAMENTO.rotulo
    assert any(b.proto.label == "Voltar às sugestões do programa" for b in t.button)


def test_nome_repetido_barra_o_arquivo(banco_com_projeto):
    projeto = com_esqueleto()
    escolhas = nb.Escolhas(
        eixo_vertical="Y",
        a_mao={"Membro estrutural3[1]": "V-N1-X", "Canal c C8X13.75(1)[1]": "V-N1-X"},
    )
    t = abrir(nb_escolhas=(str(projeto.get("id") or ""), escolhas))
    assert any("“V-N1-X” para 2 corpos" in e.value for e in t.error)
    rotulos = [b.proto.label for b in t.get("download_button")]
    assert not any(r.startswith("Arquivo de nomes") for r in rotulos)
    assert "Macro renomear_corpos.bas" in rotulos  # a macro continua disponível


def test_plano_de_cargas_passa_aos_nomes_novos(banco_com_projeto):
    g = plataforma()
    troca = pn.Renomeacao(
        "Canal c C8X13.75(1)[1]", "V-N1-B1-B2", (2.5, 3.0, 0.0), 5.0, "2026-11-17", True
    )
    plano = pc.com_acao(
        pc.PlanoDeCargas(),
        pc.nova_acao("SC", cargas=[pc.CargaDoModelo("Canal c C8X13.75(1)[1]", 3.0, "kN/m")]),
    )
    com_esqueleto(
        plano_de_cargas=pc.para_dicionario(plano),
        **nb.campos_do_projeto({}, nb.Escolhas(), (troca,)),
    )
    assert ld.geometria_do_projeto(obter_projeto_ativo()).renomeacoes == (troca,)
    t = abrir()
    assert any("1 linha(s) do plano de cargas" in i.value for i in t.info)
    assert any("1 troca(s) de nome guardadas" in c.value for c in t.caption)
    t.button(key="nb_plano").click().run()
    assert not t.exception
    novo = pc.plano_do_projeto(obter_projeto_ativo())
    assert [c.elemento for c in novo.acao("SC").cargas] == ["V-N1-B1-B2"]
    assert any("com os nomes novos" in s.value for s in t.success)
    assert g.corpo("Canal c C8X13.75(1)[1]") is not None
