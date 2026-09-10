"""Cada página do programa precisa abrir sem exceção.

Existe para pegar uma classe de regressão que só aparece na interface: uma
função ou coluna que some quando um módulo do núcleo é substituído por
outro. Foi assim que `estruturas_aco` quebrou ao trocar o catálogo de
perfis — a página lia uma coluna que o substituto não tinha, e nenhum teste
de unidade percebeu.

As páginas rodam através de `st.navigation`, e não isoladamente, porque
`st.page_link` precisa desse contexto: sem ele **toda** página do projeto
falharia, e o teste não diria nada sobre o código.
"""

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")

PAGINAS = sorted(
    f"app_pages/{caminho.name}" for caminho in (RAIZ / "app_pages").glob("*.py")
)


class PaginasTests(unittest.TestCase):
    def test_ha_paginas_para_verificar(self):
        # Se a descoberta parar de encontrar páginas, o teste passaria vazio.
        self.assertGreater(len(PAGINAS), 10)

    def test_aplicacao_abre(self):
        teste = AppTest.from_file(APP, default_timeout=180)
        teste.run()
        self.assertFalse(
            teste.exception,
            msg=f"app.py não abriu: {[e.value for e in teste.exception]}",
        )

    def test_todas_as_paginas_abrem_sem_excecao(self):
        for pagina in PAGINAS:
            with self.subTest(pagina=pagina):
                teste = AppTest.from_file(APP, default_timeout=180)
                teste.run()
                teste.switch_page(pagina)
                teste.run()
                self.assertFalse(
                    teste.exception,
                    msg=f"{pagina}: {[str(e.value) for e in teste.exception]}",
                )


class CompatibilidadeDosCatalogosTests(unittest.TestCase):
    """Os catálogos novos precisam substituir os módulos que eles envolvem.

    As páginas de cálculo passaram a importar `section_catalog` e
    `material_catalog` no lugar de `steel_sections` e `materials`. Se a
    substituição perder uma função ou uma coluna, a página quebra em tempo de
    execução — e é isto que estes testes impedem.
    """

    def test_catalogo_de_perfis_cobre_a_api_embutida(self):
        from core import section_catalog, steel_sections

        embutido = steel_sections.catalogo_dataframe()
        completo = section_catalog.catalogo_dataframe()
        self.assertEqual(set(embutido.columns) - set(completo.columns), set())
        self.assertGreaterEqual(len(completo), len(embutido))

    def test_catalogo_de_materiais_cobre_a_api_da_base(self):
        from core import material_catalog, materials

        for funcao in ("carregar_materiais", "listar_nomes", "obter_material"):
            with self.subTest(funcao=funcao):
                self.assertTrue(hasattr(material_catalog, funcao))

        base = materials.carregar_materiais()
        completo = material_catalog.carregar_materiais()
        self.assertEqual(set(base.columns) - set(completo.columns), set())
        self.assertGreaterEqual(len(completo), len(base))

    def test_material_da_base_mantem_as_chaves_esperadas(self):
        from core import material_catalog, materials

        nome = materials.listar_nomes()[0]
        original = materials.obter_material(nome)
        pelo_catalogo = material_catalog.obter_material(nome)
        self.assertEqual(set(original) - set(pelo_catalogo), set())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
