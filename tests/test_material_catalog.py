"""Testes do cadastro de materiais metálicos.

Duas coisas precisam ficar travadas aqui. A primeira é a validação: um Sy
digitado errado não gera erro, gera um dimensionamento errado. A segunda é a
**procedência** — um critério de projeto diz qual designação é permitida em
cada aplicação, mas não tabela propriedades mecânicas; atribuir a ele um
valor de Sy seria criar uma referência que o documento não dá.
"""

import json
import pathlib
import tempfile
import unittest
from unittest import mock

from core import material_catalog as catalogo
from core import materials as base_csv

MATERIAL_VALIDO = {
    "nome": "ASTM A992 (teste)",
    "categoria": "aco",
    "Sy_MPa": 345.0,
    "Sut_MPa": 450.0,
    "origem_propriedades": "ASTM A992/A992M — mínimos especificados",
    "aplicacoes": ["Perfis laminados"],
}


class ArquivoIsolado:
    """Redireciona o catálogo do usuário para um arquivo temporário."""

    def __enter__(self):
        self._dir = tempfile.TemporaryDirectory()
        self.caminho = pathlib.Path(self._dir.name) / "materiais_usuario.json"
        self._patch = mock.patch.object(catalogo, "ARQUIVO_USUARIO", self.caminho)
        self._patch.start()
        return self.caminho

    def __exit__(self, *_):
        self._patch.stop()
        self._dir.cleanup()
        return False


class ValidacaoTests(unittest.TestCase):
    def test_material_valido_e_aceito(self):
        material = catalogo.material_de_dicionario(MATERIAL_VALIDO)
        self.assertEqual(material.nome, "ASTM A992 (teste)")
        self.assertAlmostEqual(material.sy_MPa, 345.0)
        self.assertEqual(material.aplicacoes, ("Perfis laminados",))

    def test_designacao_vazia_e_recusada(self):
        with self.assertRaises(catalogo.ErroDeMaterial):
            catalogo.material_de_dicionario({**MATERIAL_VALIDO, "nome": "  "})

    def test_escoamento_maior_que_ruptura_e_recusado(self):
        with self.assertRaises(catalogo.ErroDeMaterial) as contexto:
            catalogo.material_de_dicionario(
                {**MATERIAL_VALIDO, "Sy_MPa": 600.0, "Sut_MPa": 450.0}
            )
        self.assertIn("não pode ser maior", str(contexto.exception))

    def test_categoria_desconhecida_e_recusada(self):
        with self.assertRaises(catalogo.ErroDeMaterial) as contexto:
            catalogo.material_de_dicionario({**MATERIAL_VALIDO, "categoria": "madeira"})
        self.assertIn("Categoria", str(contexto.exception))

    def test_sut_zero_e_recusado(self):
        with self.assertRaises(catalogo.ErroDeMaterial):
            catalogo.material_de_dicionario({**MATERIAL_VALIDO, "Sut_MPa": 0.0})

    def test_sy_zero_e_aceito_para_material_fragil(self):
        # Ferro fundido cinzento rompe sem patamar de escoamento: Sy zero é o
        # dado correto, não a ausência dele.
        material = catalogo.material_de_dicionario(
            {**MATERIAL_VALIDO, "nome": "FC 200", "Sy_MPa": 0.0, "Sut_MPa": 200.0}
        )
        self.assertTrue(material.sem_escoamento_definido)
        self.assertEqual(material.relacao_sy_sut, 0.0)

    def test_aplicacoes_aceitam_texto_separado(self):
        material = catalogo.material_de_dicionario(
            {**MATERIAL_VALIDO, "aplicacoes": "Perfis laminados; Tirantes"}
        )
        self.assertEqual(material.aplicacoes, ("Perfis laminados", "Tirantes"))

    def test_valor_nao_numerico_traz_o_campo_na_mensagem(self):
        with self.assertRaises(catalogo.ErroDeMaterial) as contexto:
            catalogo.material_de_dicionario({**MATERIAL_VALIDO, "Sy_MPa": "forte"})
        self.assertIn("Limite de escoamento", str(contexto.exception))


class CoerenciaTests(unittest.TestCase):
    def material(self, **extras):
        return catalogo.material_de_dicionario({**MATERIAL_VALIDO, **extras})

    def test_aco_estrutural_tipico_nao_gera_aviso(self):
        self.assertEqual(catalogo.conferir_coerencia(self.material()), [])

    def test_inox_austenitico_recozido_nao_e_acusado(self):
        # Sy/Sut ~ 0,36 é o valor real do 304L recozido; uma faixa mais
        # estreita acusaria material correto como erro de digitação.
        material = self.material(Sy_MPa=170.0, Sut_MPa=480.0)
        self.assertEqual(catalogo.conferir_coerencia(material), [])

    def test_relacao_absurda_e_apontada(self):
        avisos = catalogo.conferir_coerencia(self.material(Sy_MPa=20.0, Sut_MPa=450.0))
        self.assertTrue(any("Sy/Sut" in aviso for aviso in avisos))

    def test_unidade_em_psi_e_apontada(self):
        avisos = catalogo.conferir_coerencia(
            self.material(Sy_MPa=50_000.0, Sut_MPa=65_000.0)
        )
        self.assertTrue(any("MPa e não psi" in aviso for aviso in avisos))

    def test_material_fragil_avisa_que_sy_nao_se_aplica(self):
        avisos = catalogo.conferir_coerencia(
            self.material(Sy_MPa=0.0, Sut_MPa=200.0)
        )
        self.assertTrue(any("escoamento" in aviso for aviso in avisos))

    def test_propriedades_sem_procedencia_sao_apontadas(self):
        avisos = catalogo.conferir_coerencia(self.material(origem_propriedades=""))
        self.assertTrue(any("de onde vieram" in aviso for aviso in avisos))


class CadastroTests(unittest.TestCase):
    def setUp(self):
        self.contexto = ArquivoIsolado()
        self.arquivo = self.contexto.__enter__()

    def tearDown(self):
        self.contexto.__exit__()

    def test_salvar_e_listar(self):
        catalogo.salvar_material(MATERIAL_VALIDO)
        self.assertIn("ASTM A992 (teste)", catalogo.listar_nomes())

    def test_material_do_usuario_e_editavel(self):
        catalogo.salvar_material(MATERIAL_VALIDO)
        self.assertTrue(catalogo.obter("ASTM A992 (teste)").editavel)

    def test_material_da_base_nao_e_editavel(self):
        item = catalogo.obter("ASTM A36 aço estrutural")
        self.assertFalse(item.editavel)
        self.assertEqual(item.origem, catalogo.ORIGEM_BASE)

    def test_salvar_duas_vezes_atualiza_em_vez_de_duplicar(self):
        catalogo.salvar_material(MATERIAL_VALIDO)
        catalogo.salvar_material({**MATERIAL_VALIDO, "Sy_MPa": 350.0})
        documento = json.loads(self.arquivo.read_text(encoding="utf-8"))
        nomes = [item["nome"] for item in documento["materiais"]]
        self.assertEqual(nomes.count("ASTM A992 (teste)"), 1)
        self.assertAlmostEqual(catalogo.obter("ASTM A992 (teste)").sy_MPa, 350.0)

    def test_material_do_usuario_sobrepoe_o_de_criterio(self):
        catalogo.salvar_material({**MATERIAL_VALIDO, "nome": "ASTM A36", "Sy_MPa": 260.0})
        item = catalogo.obter("ASTM A36")
        self.assertTrue(item.editavel)
        self.assertAlmostEqual(item.sy_MPa, 260.0)

    def test_remover_material_do_usuario(self):
        catalogo.salvar_material(MATERIAL_VALIDO)
        catalogo.remover_material("ASTM A992 (teste)")
        self.assertNotIn("ASTM A992 (teste)", catalogo.listar_nomes())

    def test_remover_material_de_criterio_e_recusado_com_alternativa(self):
        with self.assertRaises(catalogo.ErroDeMaterial) as contexto:
            catalogo.remover_material("ASTM A572 Gr. 50")
        mensagem = str(contexto.exception)
        self.assertIn("não pode ser excluído", mensagem)
        self.assertIn("sobrepor", mensagem)

    def test_remover_inexistente_e_recusado(self):
        with self.assertRaises(catalogo.ErroDeMaterial):
            catalogo.remover_material("Aço que não existe")

    def test_obter_inexistente_sugere_parecidos(self):
        with self.assertRaises(catalogo.ErroDeMaterial) as contexto:
            catalogo.obter("A572")
        self.assertIn("ASTM A572 Gr. 50", str(contexto.exception))

    def test_gravacao_e_atomica(self):
        catalogo.salvar_material(MATERIAL_VALIDO)
        self.assertTrue(self.arquivo.exists())
        self.assertFalse(self.arquivo.with_suffix(".json.tmp").exists())

    def test_lote_e_aceito_parcialmente(self):
        aceitos, rejeitados = catalogo.importar_lote(
            [
                {**MATERIAL_VALIDO, "nome": "Bom 1"},
                {**MATERIAL_VALIDO, "nome": "Ruim", "Sy_MPa": 900.0},
                {**MATERIAL_VALIDO, "nome": "Bom 2"},
            ],
            origem="Tabela",
        )
        self.assertEqual(sorted(aceitos), ["Bom 1", "Bom 2"])
        self.assertEqual(len(rejeitados), 1)
        self.assertEqual(rejeitados[0][0], "Ruim")


class CompatibilidadeComABaseTests(unittest.TestCase):
    def test_todos_os_materiais_do_csv_entram_no_catalogo(self):
        # Uma validação estrita demais já apagou o ferro fundido cinzento em
        # silêncio; este teste impede que volte a acontecer.
        do_csv = set(base_csv.listar_nomes())
        no_catalogo = set(catalogo.listar_nomes())
        self.assertEqual(do_csv - no_catalogo, set())

    def test_ferro_fundido_cinzento_sobrevive(self):
        item = catalogo.obter("Ferro fundido cinzento classe 30")
        self.assertTrue(item.sem_escoamento_definido)
        self.assertGreater(item.sut_MPa, 0.0)

    def test_dicionario_e_compativel_com_a_base(self):
        dados = catalogo.obter_material("ASTM A36 aço estrutural")
        for chave in ("nome", "Sy_MPa", "Sut_MPa", "observacao", "nivel_confianca"):
            self.assertIn(chave, dados)
        self.assertIn("aviso_rastreabilidade", dados)


class CriterioDeProjetoTests(unittest.TestCase):
    def test_catalogo_do_criterio_esta_distribuido(self):
        arquivos = [c.name for c in catalogo.catalogos_de_criterio()]
        self.assertIn("materiais_ref_anglo.json", arquivos)

    def test_criterio_e_identificado_nos_materiais(self):
        item = catalogo.obter("ASTM A572 Gr. 50")
        self.assertIn("AA-BR-DPST-DR-0001", item.criterio)
        self.assertFalse(item.editavel)

    def test_propriedades_sao_atribuidas_a_norma_e_nao_ao_criterio(self):
        # O critério especifica a designação; quem dá Sy e Sut é a norma. Se
        # a atribuição se perdesse, o memorial citaria a fonte errada.
        item = catalogo.obter("ASTM A572 Gr. 50")
        self.assertIn("ASTM A572", item.origem_propriedades)
        self.assertNotIn("AA-BR", item.origem_propriedades)

    def test_valores_sem_minimo_normativo_sao_declarados(self):
        # SAE 1020 e A108 não têm mínimo especificado: o catálogo precisa
        # dizer isso, em vez de apresentar um típico como se fosse norma.
        for nome in ("SAE 1020", "ASTM A108 Gr. 1020"):
            with self.subTest(material=nome):
                item = catalogo.obter(nome)
                self.assertIn("típico", item.origem_propriedades.lower())

    def test_aplicacao_filtra_os_materiais_permitidos(self):
        permitidos = {m.nome for m in catalogo.materiais_para("Perfis laminados")}
        self.assertEqual(permitidos, {"ASTM A36", "ASTM A572 Gr. 50"})

    def test_aplicacao_de_parafuso_traz_so_os_de_alta_resistencia(self):
        permitidos = {
            m.nome
            for m in catalogo.materiais_para(
                "Parafusos de alta resistencia em ligacoes principais"
            )
        }
        self.assertEqual(permitidos, {"ASTM F3125 Gr. A325", "ASTM F3125 Gr. A490"})

    def test_protecao_exigida_acompanha_o_material(self):
        self.assertIn("Galvaniz", catalogo.obter("ASTM F3125 Gr. A325").protecao)
        # O critério não admite galvanização a fogo para o A490.
        self.assertNotIn("fogo", catalogo.obter("ASTM F3125 Gr. A490").protecao)

    def test_aplicacoes_disponiveis_vem_do_criterio(self):
        aplicacoes = catalogo.aplicacoes_disponiveis()
        self.assertIn("Perfis laminados", aplicacoes)
        self.assertIn("Tirantes", aplicacoes)

    def test_materiais_do_criterio_sao_coerentes(self):
        for nome, item in catalogo.listar_cadastrados().items():
            if not item.criterio:
                continue
            with self.subTest(material=nome):
                self.assertLessEqual(item.sy_MPa, item.sut_MPa)
                self.assertGreater(item.sut_MPa, 0.0)
                self.assertTrue(item.origem_propriedades)


class ArquivoCorrompidoTests(unittest.TestCase):
    def setUp(self):
        self.contexto = ArquivoIsolado()
        self.arquivo = self.contexto.__enter__()

    def tearDown(self):
        self.contexto.__exit__()

    def test_json_invalido_e_reportado(self):
        self.arquivo.write_text("{isto não é json", encoding="utf-8")
        with self.assertRaises(catalogo.ErroDeMaterial):
            catalogo.listar_nomes()

    def test_registro_corrompido_e_ignorado_sem_derrubar_o_catalogo(self):
        self.arquivo.write_text(
            json.dumps(
                {
                    "schema": catalogo.SCHEMA,
                    "materiais": [
                        {"nome": "quebrado", "Sy_MPa": 900, "Sut_MPa": 100},
                        MATERIAL_VALIDO,
                    ],
                }
            ),
            encoding="utf-8",
        )
        nomes = catalogo.listar_nomes()
        self.assertNotIn("quebrado", nomes)
        self.assertIn("ASTM A992 (teste)", nomes)

    def test_arquivo_ausente_devolve_base_e_criterios(self):
        self.assertFalse(self.arquivo.exists())
        self.assertGreater(len(catalogo.listar_nomes()), len(base_csv.listar_nomes()))


class TabelaTests(unittest.TestCase):
    def test_dataframe_traz_procedencia_e_aplicacoes(self):
        tabela = catalogo.catalogo_dataframe()
        for coluna in ("origem", "editavel", "criterio", "aplicacoes"):
            self.assertIn(coluna, tabela.columns)
        self.assertEqual(len(tabela), len(catalogo.listar_nomes()))

    def test_resumo_conta_por_origem(self):
        resumo = catalogo.resumo_do_catalogo()
        self.assertEqual(sum(resumo.values()), len(catalogo.listar_nomes()))
        self.assertIn(catalogo.ORIGEM_BASE, resumo)

    def test_criterios_carregados_sao_listados(self):
        criterios = catalogo.criterios_carregados()
        self.assertTrue(any("AA-BR-DPST-DR-0001" in item for item in criterios))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
