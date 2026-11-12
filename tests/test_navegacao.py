"""O menu: um lugar só, coerente com as páginas, os módulos e o guia."""

from __future__ import annotations

from pathlib import Path

from core import navegacao as nv
from core.technical_modules import listar_modulos

RAIZ = Path(__file__).resolve().parent.parent


def test_toda_pagina_esta_no_menu_uma_vez_e_existe():
    caminhos = [item.pagina for item in nv.todos_os_itens()]
    assert len(caminhos) == len(set(caminhos))
    arquivos = {p.relative_to(RAIZ).as_posix() for p in (RAIZ / "app_pages").glob("*.py")}
    assert set(caminhos) == arquivos


def test_modulos_tecnicos_seguem_o_menu():
    for modulo in listar_modulos():
        grupo = nv.grupo_da_pagina(modulo.pagina)
        assert grupo is not None and grupo.nome == modulo.grupo_navegacao, modulo.id
        item = next(i for i in grupo.itens if i.pagina == modulo.pagina)
        assert item.titulo == modulo.titulo, modulo.id


def test_grupos_na_ordem_do_trabalho_e_com_descricao():
    nomes = [g.nome for g in nv.MENU]
    assert nomes[:8] == [
        "Projeto",
        "Cargas e vento",
        "Modelo SolidWorks",
        "Estrutura metálica",
        "Entrega",
        "Mecânica",
        "Seções e materiais",
        "Referências e ajuda",
    ]
    assert all(g.descricao and g.itens for g in nv.MENU)
    assert all(len(i.tarefa) <= 90 for i in nv.todos_os_itens())
    icones = [i.icone for i in nv.todos_os_itens()]
    assert len(set(icones)) >= len(icones) - 4  # quase todos distintos
    assert nv.grupo_da_pagina("degrau_escada").nome == "Estrutura metálica"
    assert nv.item_da_pagina("app_pages/degrau_escada.py").secao == nv.BARRAS
    assert nv.grupo_da_pagina("desenhar_secao").nome == "Seções e materiais"
    assert nv.grupo_da_pagina("app_pages/inicio.py") is None


def test_submenus_ficam_juntos_e_nao_se_repetem():
    for grupo in nv.MENU:
        nomes = [secao for secao, _ in grupo.secoes()]
        assert len(nomes) == len(set(nomes)), grupo.nome
        # Ou o grupo inteiro tem submenus, ou nenhum item tem.
        assert all(nomes) or nomes == [""], grupo.nome
    estrutura = next(g for g in nv.MENU if g.nome == "Estrutura metálica")
    assert [s for s, _ in estrutura.secoes()] == [nv.BARRAS, nv.LIGACOES]
    mecanica = next(g for g in nv.MENU if g.nome == "Mecânica")
    assert [s for s, _ in mecanica.secoes()] == [nv.PECAS, nv.TENSOES, nv.FLUIDOS, nv.TERMICA]


def test_nomes_antigos_nao_sao_nome_de_outra_pagina():
    titulos = {i.titulo for i in nv.todos_os_itens()}
    for item in nv.todos_os_itens():
        for antigo in item.outros_nomes:
            assert antigo not in titulos, (item.titulo, antigo)


def _app():
    from streamlit.testing.v1 import AppTest

    t = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180)
    t.run()
    return t


def test_menu_lateral_mostra_os_submenus_e_a_busca_acha_o_nome_antigo():
    t = _app()
    t.switch_page("app_pages/degrau_escada.py").run()
    assert not t.exception
    html = " ".join(e.proto.body for e in t.get("html"))
    assert 'class="menu-secao">Barras e vigas<' in html
    assert 'class="menu-secao">Ligações e bases<' in html
    busca = t.selectbox(key="menu_busca")
    assert any("Cálculo de peças" in o and "Assistente de cargas" in o for o in busca.options)


def test_titulo_da_pagina_vem_do_menu():
    t = _app()
    t.switch_page("app_pages/estruturas_aco.py").run()
    assert not t.exception
    assert [x.value for x in t.title][:1] == ["Barras, treliças e pórticos"]
    t.switch_page("app_pages/projeto_parafusos.py").run()
    assert [x.value for x in t.title][:1] == ["Projeto de parafusos"]
