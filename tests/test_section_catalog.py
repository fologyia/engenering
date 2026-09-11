"""Testes do cadastro de perfis.

O catálogo alimenta cálculos de engenharia: um perfil com propriedade errada
não gera erro, gera um dimensionamento errado. Por isso o foco aqui é a
validação de entrada, a procedência de cada perfil e o que acontece quando o
arquivo do usuário está ausente ou corrompido.
"""

import json
import unittest
from unittest import mock

from core import section_catalog as catalogo
from core.steel_sections import CATALOGO_PERFIS

PERFIL_VALIDO = {
    "nome": "W teste 200 x 20",
    "familia": "W (mesa larga)",
    "area_mm2": 2_550.0,
    "ix_mm4": 1.66e7,
    "iy_mm4": 1.15e6,
    "zx_mm3": 1.9e5,
    "zy_mm3": 3.6e4,
    "j_mm4": 6.0e4,
    "cw_mm6": 1.1e10,
    "altura_mm": 203.0,
    "largura_mm": 102.0,
    "espessura_alma_mm": 5.8,
    "espessura_mesa_mm": 6.5,
    "area_cisalhamento_mm2": 1_177.0,
    "massa_kg_m": 20.0,
    "descricao": "Perfil usado nos testes",
}


class ArquivoTemporario:
    """Redireciona o catálogo do usuário para um arquivo isolado."""

    def __init__(self, tmp_path):
        self.caminho = tmp_path / "perfis_usuario.json"

    def __enter__(self):
        self._patch = mock.patch.object(catalogo, "ARQUIVO_USUARIO", self.caminho)
        self._patch.start()
        return self.caminho

    def __exit__(self, *_excecao):
        self._patch.stop()
        return False


class ValidacaoTests(unittest.TestCase):
    def test_perfil_valido_e_aceito(self):
        perfil = catalogo.perfil_de_dicionario(PERFIL_VALIDO)
        self.assertEqual(perfil.nome, "W teste 200 x 20")
        self.assertAlmostEqual(perfil.area_mm2, 2_550.0)

    def test_nome_vazio_e_recusado(self):
        with self.assertRaises(catalogo.ErroDeCatalogo) as contexto:
            catalogo.perfil_de_dicionario({**PERFIL_VALIDO, "nome": "   "})
        self.assertIn("nome", str(contexto.exception))

    def test_dimensao_nao_positiva_e_recusada(self):
        for campo in ("area_mm2", "ix_mm4", "altura_mm", "espessura_alma_mm"):
            with self.subTest(campo=campo):
                with self.assertRaises(catalogo.ErroDeCatalogo):
                    catalogo.perfil_de_dicionario({**PERFIL_VALIDO, campo: 0.0})

    def test_texto_no_lugar_de_numero_traz_o_campo_na_mensagem(self):
        with self.assertRaises(catalogo.ErroDeCatalogo) as contexto:
            catalogo.perfil_de_dicionario({**PERFIL_VALIDO, "ix_mm4": "muito"})
        self.assertIn("Momento de inércia Ix", str(contexto.exception))

    def test_mesas_maiores_que_a_altura_sao_recusadas(self):
        with self.assertRaises(catalogo.ErroDeCatalogo) as contexto:
            catalogo.perfil_de_dicionario(
                {**PERFIL_VALIDO, "espessura_mesa_mm": 110.0}
            )
        self.assertIn("mesas", str(contexto.exception).lower())

    def test_campos_opcionais_podem_ser_zero(self):
        perfil = catalogo.perfil_de_dicionario(
            {**PERFIL_VALIDO, "cw_mm6": 0.0, "j_mm4": 0.0, "massa_kg_m": 0.0}
        )
        self.assertEqual(perfil.cw_mm6, 0.0)


class CoerenciaTests(unittest.TestCase):
    def test_perfil_consistente_nao_gera_aviso(self):
        perfil = catalogo.perfil_de_dicionario(PERFIL_VALIDO)
        self.assertEqual(catalogo.conferir_coerencia(perfil), [])

    def test_eixos_trocados_sao_apontados(self):
        trocado = {**PERFIL_VALIDO, "ix_mm4": 1.15e6, "iy_mm4": 1.66e7}
        avisos = catalogo.conferir_coerencia(catalogo.perfil_de_dicionario(trocado))
        self.assertTrue(any("eixos" in aviso for aviso in avisos))

    def test_massa_incoerente_com_a_area_e_apontada(self):
        # 2 550 mm² de aço pesam ~20 kg/m; 50 kg/m denuncia vírgula errada.
        avisos = catalogo.conferir_coerencia(
            catalogo.perfil_de_dicionario({**PERFIL_VALIDO, "massa_kg_m": 50.0})
        )
        self.assertTrue(any("massa" in aviso for aviso in avisos))

    def test_area_de_cisalhamento_maior_que_a_total_e_apontada(self):
        avisos = catalogo.conferir_coerencia(
            catalogo.perfil_de_dicionario(
                {**PERFIL_VALIDO, "area_cisalhamento_mm2": 9_999.0}
            )
        )
        self.assertTrue(any("cisalhamento" in aviso for aviso in avisos))

    def test_modulo_plastico_absurdo_e_apontado(self):
        avisos = catalogo.conferir_coerencia(
            catalogo.perfil_de_dicionario({**PERFIL_VALIDO, "zx_mm3": 9.0e5})
        )
        self.assertTrue(any("Zx/Wx" in aviso for aviso in avisos))


class CadastroTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._dir = tempfile.TemporaryDirectory()
        self.contexto = ArquivoTemporario(__import__("pathlib").Path(self._dir.name))
        self.arquivo = self.contexto.__enter__()

    def tearDown(self):
        self.contexto.__exit__()
        self._dir.cleanup()

    def test_salvar_e_listar(self):
        catalogo.salvar_perfil(PERFIL_VALIDO)
        completo = catalogo.listar_perfis()
        self.assertIn("W teste 200 x 20", completo)
        self.assertAlmostEqual(completo["W teste 200 x 20"].ix_mm4, 1.66e7)

    def test_perfil_do_usuario_e_editavel(self):
        catalogo.salvar_perfil(PERFIL_VALIDO)
        self.assertTrue(catalogo.obter("W teste 200 x 20").editavel)

    def test_perfil_embutido_nao_e_editavel(self):
        nome = next(iter(CATALOGO_PERFIS))
        item = catalogo.obter(nome)
        self.assertFalse(item.editavel)
        self.assertEqual(item.origem, catalogo.ORIGEM_EMBUTIDO)

    def test_salvar_duas_vezes_atualiza_em_vez_de_duplicar(self):
        catalogo.salvar_perfil(PERFIL_VALIDO)
        catalogo.salvar_perfil({**PERFIL_VALIDO, "massa_kg_m": 21.0})
        documento = json.loads(self.arquivo.read_text(encoding="utf-8"))
        nomes = [item["nome"] for item in documento["perfis"]]
        self.assertEqual(nomes.count("W teste 200 x 20"), 1)
        self.assertAlmostEqual(
            catalogo.obter("W teste 200 x 20").perfil.massa_kg_m, 21.0
        )

    def test_perfil_do_usuario_sobrepoe_o_embutido(self):
        # Cadastrar com o nome de um perfil existente é corrigir aquele valor
        # para o uso do projeto, não um erro.
        nome = next(iter(CATALOGO_PERFIS))
        original = CATALOGO_PERFIS[nome].ix_mm4
        catalogo.salvar_perfil({**PERFIL_VALIDO, "nome": nome})
        item = catalogo.obter(nome)
        self.assertTrue(item.editavel)
        self.assertNotAlmostEqual(item.perfil.ix_mm4, original)

    def test_remover_perfil_do_usuario(self):
        catalogo.salvar_perfil(PERFIL_VALIDO)
        catalogo.remover_perfil("W teste 200 x 20")
        self.assertNotIn("W teste 200 x 20", catalogo.listar_perfis())

    def test_remover_perfil_embutido_e_recusado_com_alternativa(self):
        nome = next(iter(CATALOGO_PERFIS))
        with self.assertRaises(catalogo.ErroDeCatalogo) as contexto:
            catalogo.remover_perfil(nome)
        mensagem = str(contexto.exception)
        self.assertIn("não pode ser excluído", mensagem)
        self.assertIn("sobrepor", mensagem)

    def test_remover_inexistente_e_recusado(self):
        with self.assertRaises(catalogo.ErroDeCatalogo):
            catalogo.remover_perfil("Perfil que não existe")

    def test_obter_inexistente_sugere_parecidos(self):
        catalogo.salvar_perfil(PERFIL_VALIDO)
        with self.assertRaises(catalogo.ErroDeCatalogo) as contexto:
            catalogo.obter("W teste")
        self.assertIn("W teste 200 x 20", str(contexto.exception))

    def test_gravacao_e_atomica(self):
        # A troca do arquivo temporário evita catálogo truncado se o programa
        # for encerrado durante a gravação.
        catalogo.salvar_perfil(PERFIL_VALIDO)
        self.assertTrue(self.arquivo.exists())
        self.assertFalse(self.arquivo.with_suffix(".json.tmp").exists())


class ImportacaoTests(unittest.TestCase):
    def setUp(self):
        import pathlib
        import tempfile

        self._dir = tempfile.TemporaryDirectory()
        self.contexto = ArquivoTemporario(pathlib.Path(self._dir.name))
        self.contexto.__enter__()

    def tearDown(self):
        self.contexto.__exit__()
        self._dir.cleanup()

    def test_lote_valido_e_cadastrado(self):
        entradas = [
            {**PERFIL_VALIDO, "nome": f"W lote {indice}"} for indice in range(3)
        ]
        aceitos, rejeitados = catalogo.importar_lote(entradas, origem="Tabela X")
        self.assertEqual(len(aceitos), 3)
        self.assertEqual(rejeitados, [])
        self.assertEqual(catalogo.obter("W lote 0").origem, "Tabela X")

    def test_lote_e_aceito_parcialmente(self):
        # Perder trinta perfis bons por causa de uma linha ruim seria pior do
        # que importar os trinta e avisar sobre a linha.
        entradas = [
            {**PERFIL_VALIDO, "nome": "W bom"},
            {**PERFIL_VALIDO, "nome": "W ruim", "area_mm2": -5.0},
            {**PERFIL_VALIDO, "nome": "W bom 2"},
        ]
        aceitos, rejeitados = catalogo.importar_lote(entradas, origem="Tabela")
        self.assertEqual(sorted(aceitos), ["W bom", "W bom 2"])
        self.assertEqual(len(rejeitados), 1)
        self.assertEqual(rejeitados[0][0], "W ruim")
        self.assertIn("maior que zero", rejeitados[0][1])

    def test_lote_vazio_nao_quebra(self):
        aceitos, rejeitados = catalogo.importar_lote([], origem="Nada")
        self.assertEqual((aceitos, rejeitados), ([], []))


class ArquivoCorrompidoTests(unittest.TestCase):
    def setUp(self):
        import pathlib
        import tempfile

        self._dir = tempfile.TemporaryDirectory()
        self.pasta = pathlib.Path(self._dir.name)
        self.contexto = ArquivoTemporario(self.pasta)
        self.arquivo = self.contexto.__enter__()

    def tearDown(self):
        self.contexto.__exit__()
        self._dir.cleanup()

    def test_json_invalido_e_reportado(self):
        self.arquivo.write_text("{isto não é json", encoding="utf-8")
        with self.assertRaises(catalogo.ErroDeCatalogo) as contexto:
            catalogo.listar_perfis()
        self.assertIn("Não foi possível ler", str(contexto.exception))

    def test_formato_errado_e_reportado(self):
        self.arquivo.write_text('{"perfis": "não é lista"}', encoding="utf-8")
        with self.assertRaises(catalogo.ErroDeCatalogo):
            catalogo.listar_perfis()

    def test_perfil_corrompido_e_ignorado_sem_derrubar_o_catalogo(self):
        # Um registro ruim não pode impedir o programa de abrir.
        self.arquivo.write_text(
            json.dumps(
                {
                    "schema": catalogo.SCHEMA,
                    "perfis": [
                        {"nome": "quebrado", "area_mm2": -1},
                        PERFIL_VALIDO,
                    ],
                }
            ),
            encoding="utf-8",
        )
        completo = catalogo.listar_perfis()
        self.assertNotIn("quebrado", completo)
        self.assertIn("W teste 200 x 20", completo)

    def test_arquivo_ausente_devolve_so_os_embutidos(self):
        self.assertFalse(self.arquivo.exists())
        completo = catalogo.listar_perfis()
        self.assertGreaterEqual(len(completo), len(CATALOGO_PERFIS))


class CatalogoDeReferenciaTests(unittest.TestCase):
    def test_catalogo_gerdau_esta_distribuido(self):
        arquivos = [c.name for c in catalogo.catalogos_de_referencia()]
        self.assertIn("perfis_ref_gerdau.json", arquivos)

    def test_perfis_de_referencia_entram_no_catalogo(self):
        completo = catalogo.listar_cadastrados()
        gerdau = [
            nome for nome, item in completo.items() if "Gerdau" in item.origem
        ]
        self.assertGreater(len(gerdau), 50)

    def test_catalogo_cobre_as_bitolas_w_ate_610(self):
        import re

        alturas = set()
        for nome, item in catalogo.listar_cadastrados().items():
            if "Gerdau" not in item.origem or not nome.startswith(("W ", "HP ")):
                continue
            achado = re.search(r"^(?:W|HP)\s+(\d+)\s*x", nome)
            if achado:
                alturas.add(int(achado.group(1)))
        self.assertEqual(
            sorted(alturas), [150, 200, 250, 310, 360, 410, 460, 530, 610]
        )

    def test_catalogo_gerdau_cobre_i_u_e_t(self):
        completo = catalogo.listar_cadastrados()
        familias_gerdau = {
            item.perfil.familia
            for item in completo.values()
            if "Gerdau" in item.origem
        }
        self.assertIn("I duplamente simétrico", familias_gerdau)
        self.assertIn("U (canal laminado)", familias_gerdau)
        self.assertIn("T (perfil tê)", familias_gerdau)

    def test_perfil_de_referencia_nao_e_editavel(self):
        item = catalogo.obter("W 250 x 25,3")
        self.assertFalse(item.editavel)
        self.assertIn("Gerdau", item.origem)

    def test_valores_batem_com_a_tabela_do_fabricante(self):
        # Conferência pontual contra a tabela impressa: se a extração do PDF
        # regredir, isto acusa.
        perfil = catalogo.obter("W 250 x 25,3").perfil
        self.assertAlmostEqual(perfil.altura_mm, 257.0)
        self.assertAlmostEqual(perfil.largura_mm, 102.0)
        self.assertAlmostEqual(perfil.espessura_alma_mm, 6.1)
        self.assertAlmostEqual(perfil.espessura_mesa_mm, 8.4)
        self.assertAlmostEqual(perfil.area_mm2, 3_260.0, delta=1.0)
        self.assertAlmostEqual(perfil.ix_mm4, 3.473e7, delta=1e4)
        self.assertAlmostEqual(perfil.massa_kg_m, 25.3, places=2)

    def test_todos_os_perfis_de_referencia_sao_coerentes(self):
        for nome, item in catalogo.listar_cadastrados().items():
            if "Gerdau" not in item.origem:
                continue
            with self.subTest(perfil=nome):
                self.assertEqual(catalogo.conferir_coerencia(item.perfil), [])


class TabelaTests(unittest.TestCase):
    def test_dataframe_traz_a_procedencia(self):
        tabela = catalogo.catalogo_dataframe()
        self.assertIn("origem", tabela.columns)
        self.assertIn("editavel", tabela.columns)
        self.assertEqual(len(tabela), len(catalogo.listar_perfis()))

    def test_resumo_conta_por_origem(self):
        resumo = catalogo.resumo_do_catalogo()
        self.assertEqual(sum(resumo.values()), len(catalogo.listar_perfis()))
        self.assertIn(catalogo.ORIGEM_EMBUTIDO, resumo)


class IntegracaoComOsModulosTests(unittest.TestCase):
    def test_perfil_de_referencia_serve_a_uma_viga(self):
        from core import beam_analysis as vb
        from core import beam_script as bs

        viga = bs.interpretar(
            """
            viga 6
            secao perfil W 250 x 25,3
            material aco
            apoio 0 pino
            apoio 6 rolete
            q 0 6 15 baixo
            """
        )
        resultado = vb.analisar_viga(viga)
        # M = wL²/8 = 67,5 kN·m, independente do perfil.
        self.assertAlmostEqual(
            resultado.extremos["momento"].valor / 1e6, 67.5, places=6
        )
        self.assertAlmostEqual(viga.secao.inercia_mm4, 3.473e7, delta=1e4)

    def test_busca_parcial_encontra_o_perfil(self):
        from core import beam_script as bs

        viga = bs.interpretar(
            "viga 4\nsecao perfil HP 250 x 62,0\nmaterial aco\napoio 0 pino\napoio 4 rolete\n"
        )
        self.assertGreater(viga.secao.area_mm2, 7_000.0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
