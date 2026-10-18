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
    assert nomes[:7] == [
        "Projeto",
        "Cargas e vento",
        "Modelo SolidWorks",
        "Barras e vigas",
        "Ligações e bases",
        "Escadas",
        "Entrega",
    ]
    assert all(g.descricao and g.itens for g in nv.MENU)
    assert all(len(i.tarefa) <= 90 for i in nv.todos_os_itens())
    icones = [i.icone for i in nv.todos_os_itens()]
    assert len(set(icones)) >= len(icones) - 4  # quase todos distintos
    assert nv.grupo_da_pagina("degrau_escada").nome == "Escadas"
    assert nv.grupo_da_pagina("app_pages/inicio.py") is None
