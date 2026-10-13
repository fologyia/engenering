"""Cada página do programa precisa abrir sem exceção — sem e com projeto ativo.

Existe para pegar uma classe de regressão que só aparece na interface: uma
função ou coluna que some quando um módulo do núcleo é substituído por
outro. Foi assim que `estruturas_aco` quebrou ao trocar o catálogo de
perfis — a página lia uma coluna que o substituto não tinha, e nenhum teste
de unidade percebeu.

As páginas rodam através de `st.navigation`, e não isoladamente, porque
`st.page_link` precisa desse contexto: sem ele **toda** página do projeto
falharia, e o teste não diria nada sobre o código.

Os dois estados são deliberados. Antes, o teste abria as páginas com o banco
de trabalho do usuário: na máquina de quem tem um projeto ativo, cada página
renderizava o cabeçalho do projeto, a sequência sugerida e o botão de
registro; no CI, com o banco vazio, nada disso rodava — os dois ambientes
testavam caminhos diferentes e nenhum cobria os dois. Agora o banco é sempre
temporário (ver ``conftest.py``): vazio num caso, com um projeto cheio no
outro.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")

PAGINAS = sorted(f"app_pages/{caminho.name}" for caminho in (RAIZ / "app_pages").glob("*.py"))
COMPONENTES = sorted(f"components/{caminho.name}" for caminho in (RAIZ / "components").glob("*.py"))

# Cores aceitas por ``st.badge`` no Streamlit 1.59 (``"rainbow"`` só vale em cabeçalhos e texto).
CORES_DE_SELO = {"red", "orange", "yellow", "blue", "green", "violet", "gray", "grey", "primary"}


def _abrir(pagina: str) -> AppTest:
    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    teste.switch_page(pagina)
    teste.run()
    return teste


def test_ha_paginas_para_verificar():
    # Se a descoberta parar de encontrar páginas, os testes passariam vazios.
    assert len(PAGINAS) > 10


def test_aplicacao_abre(banco_isolado):
    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    assert not teste.exception, f"app.py não abriu: {[e.value for e in teste.exception]}"


@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_abre_sem_projeto(banco_isolado, pagina):
    teste = _abrir(pagina)
    assert not teste.exception, f"{pagina}: {[str(e.value) for e in teste.exception]}"


@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_abre_com_projeto_ativo(banco_com_projeto, pagina):
    teste = _abrir(pagina)
    assert not teste.exception, f"{pagina}: {[str(e.value) for e in teste.exception]}"


#: Campos dos módulos novos gravados fora do formato: projeto antigo, editado à mão ou corrompido.
CAMPOS_CORROMPIDOS = {
    "plano_de_cargas": {
        "acoes": [{"codigo": "PP", "cargas": "x"}, 7, {"cargas": [{"valor": "?"}]}]
    },
    "base_tecnica": {"criterio": 5, "v0": "abc", "s3": [], "tipo_de_estrutura": {"x": 1}},
    "esforcos_do_modelo": {
        "casos": {"PP": {"membros": {"V1": [[1, 2, "a"], "x"]}, "reacoes": {"modelo": [1, "b"]}}},
        "membros": [1, 2],
        "parametros": "nada",
        "eixo_vertical": "W",
        "norma": "inventada",
        "placa": {"espessura_mm": "grossa", "diametro": 9},
    },
    "lista_de_material": {"itens": [{"quantidade": "muitas"}, 3], "acrescimo_pct": "x"},
    "cargas_do_esqueleto": {
        "eixos_x_m": ["a", 3],
        "niveis": [{"cota_m": "alto", "vigas_paralelas_a": "Q"}, 4],
        "escadas": [{"nivel": 9, "borda": "?"}],
        "equipamentos": "nenhum",
    },
    "geometria_do_modelo": {"corpos": [["a", None, 3], "lixo", [1] * 12], "arquivo": 7},
    "registros_tecnicos": [
        5,
        "texto",
        {"modulo_id": 3, "titulo": None},
        {"modulo_id": "viga_de_piso", "resultados": "x", "entradas": [1, 2], "status": 7},
    ],
}


@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_abre_com_dados_do_projeto_corrompidos(banco_com_projeto, pagina):
    """Os testes levantam as falhas (conftest): aqui nenhuma página pode quebrar com dado estranho."""
    from core.project_store import obter_projeto_ativo, salvar_projeto

    projeto = obter_projeto_ativo()
    projeto.update(CAMPOS_CORROMPIDOS)
    salvar_projeto(projeto, motivo="teste de dados corrompidos")
    teste = _abrir(pagina)
    assert not teste.exception, f"{pagina}: {[str(e.value) for e in teste.exception]}"


def _cores_literais_de_selos(caminho: Path) -> list[tuple[int, str]]:
    """Cores escritas como texto em ``cabecalho_pagina(cor=...)`` e ``st.badge(color=...)``."""
    argumento_da_chamada = {"cabecalho_pagina": "cor", "badge": "color"}
    achadas: list[tuple[int, str]] = []
    for no in ast.walk(ast.parse(caminho.read_text(encoding="utf-8"))):
        if not isinstance(no, ast.Call):
            continue
        funcao = no.func
        nome = funcao.attr if isinstance(funcao, ast.Attribute) else getattr(funcao, "id", "")
        argumento = argumento_da_chamada.get(nome)
        for palavra in no.keywords:
            valor = palavra.value
            if (
                argumento is not None
                and palavra.arg == argumento
                and isinstance(valor, ast.Constant)
                and isinstance(valor.value, str)
            ):
                achadas.append((valor.lineno, valor.value))
    return achadas


@pytest.mark.parametrize("arquivo", [*PAGINAS, *COMPONENTES])
def test_selos_usam_so_cores_que_o_streamlit_conhece(arquivo):
    """``st.badge`` com cor desconhecida não dá erro: a tela mostra o texto cru ``:teal-badge[...]``.

    Foi o que aconteceu em Materiais técnicos, e nenhum teste de abertura de página percebe.
    """
    invalidas = [
        f"linha {linha}: {cor!r}"
        for linha, cor in _cores_literais_de_selos(RAIZ / arquivo)
        if cor not in CORES_DE_SELO
    ]
    assert not invalidas, f"{arquivo}: cor de selo desconhecida em {invalidas}"


def test_o_detector_de_cor_de_selo_pega_a_cor_errada(tmp_path):
    """Sem isto o teste acima passaria vazio se o detector parasse de enxergar as chamadas."""
    amostra = tmp_path / "amostra.py"
    amostra.write_text(
        "cabecalho_pagina('T', 'S', categoria='C', icone='i', cor='teal')\n"
        "st.badge('x', color='violet')\n"
        "st.badge('y', color=variavel)\n"
        "st.metric('z', 1, color='teal')\n",
        encoding="utf-8",
    )
    assert _cores_literais_de_selos(amostra) == [(1, "teal"), (2, "violet")]


class TestCompatibilidadeDosCatalogos:
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
        assert set(embutido.columns) - set(completo.columns) == set()
        assert len(completo) >= len(embutido)

    @pytest.mark.parametrize("funcao", ["carregar_materiais", "listar_nomes", "obter_material"])
    def test_catalogo_de_materiais_cobre_a_api_da_base(self, funcao):
        from core import material_catalog, materials

        assert hasattr(material_catalog, funcao)
        base = materials.carregar_materiais()
        completo = material_catalog.carregar_materiais()
        assert set(base.columns) - set(completo.columns) == set()
        assert len(completo) >= len(base)

    def test_material_da_base_mantem_as_chaves_esperadas(self):
        from core import material_catalog, materials

        nome = materials.listar_nomes()[0]
        original = materials.obter_material(nome)
        pelo_catalogo = material_catalog.obter_material(nome)
        assert set(original) - set(pelo_catalogo) == set()
