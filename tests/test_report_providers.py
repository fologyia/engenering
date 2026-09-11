"""Testes dos provedores de seção do memorial.

`report_plugins` é o ponto de extensão que permite um módulo novo entrar no
memorial sem alterar o orquestrador — e até agora não tinha teste próprio.
O caso central aqui é o de ponta a ponta: uma viga calculada de verdade,
registrada no projeto, precisa chegar ao memorial com a seção que a governou
e com a combinação que a produziu.
"""

import io
import unittest

from core import beam_analysis as vb
from core import beam_script as bs
from core.project_report import SECOES_RELATORIO, montar_modelo_relatorio
from core.report_plugins import (
    ProvedorSecaoRelatorio,
    listar_provedores,
    registrar_provedor,
    titulos_secoes_extensao,
)
from core.technical_modules import obter_modulo
from core.technical_records import criar_registro_tecnico


def projeto_minimo(*registros) -> dict:
    return {
        "nome": "Projeto de teste",
        "codigo": "PT-1",
        "objetivo": "Verificar a integração do memorial",
        "descricao": "Projeto usado apenas nos testes",
        "registros_tecnicos": list(registros),
    }


def registro_de_viga(script: str, *, titulo="Viga do mezanino", com_envoltoria=False):
    """Registra uma viga calculada de verdade, não um dicionário inventado."""
    viga = bs.interpretar(script)
    resultado = vb.analisar_viga(viga)
    verificacao = vb.verificar_flecha(resultado)
    extremos = resultado.extremos

    resultados = {
        "reacoes": vb.resumo_reacoes(resultado),
        "cortante_maximo_kN": extremos["cortante"].valor / 1_000.0,
        "cortante_maximo_x_m": extremos["cortante"].x_mm / 1_000.0,
        "momento_maximo_kNm": extremos["momento"].valor / 1e6,
        "momento_maximo_x_m": extremos["momento"].x_mm / 1_000.0,
        "normal_maximo_kN": extremos["normal"].valor / 1_000.0,
        "torque_maximo_kNm": extremos["torque"].valor / 1e6,
        "flecha_maxima_mm": extremos["flecha"].valor,
        "flecha_maxima_x_m": extremos["flecha"].x_mm / 1_000.0,
        "tensao_normal_extrema_MPa": extremos["tensao_normal"].valor,
        "von_mises_maximo_MPa": extremos["von_mises"].valor,
        "fator_seguranca_escoamento": resultado.fator_seguranca_escoamento,
        "fator_seguranca_minimo": 1.5,
        "flecha_admissivel_mm": verificacao["flecha_admissivel_mm"],
        "criterio_flecha": verificacao["criterio"],
        "grau_hiperestaticidade": resultado.grau_hiperestaticidade,
        "fator_carga_critica": resultado.fator_carga_critica,
        "fator_carga_critica_transversal": resultado.fator_carga_critica_transversal,
        "segunda_ordem": resultado.segunda_ordem,
    }
    if com_envoltoria:
        envoltoria = vb.analisar_envoltoria(viga, bs.combinacoes_do_script(script))
        resultados["envoltoria_governantes"] = vb.resumo_governantes(envoltoria)
        resultados["envoltoria_combinacoes"] = [
            {"nome": item.nome, "fatores": item.fatores}
            for item in envoltoria.combinacoes
        ]

    return criar_registro_tecnico(
        modulo="Vigas e eixos",
        modulo_id="vigas_eixos",
        titulo=titulo,
        status="Atende",
        resumo="Análise linear de barra reta",
        entradas={
            "script_modelo": script,
            "comprimento_mm": viga.comprimento_mm,
            "secao": {"nome": viga.secao.nome},
            "material": {"nome": viga.material.nome, "fonte": viga.material.fonte},
            "apoios": [
                {"x_mm": apoio.x_mm, "tipo": apoio.tipo} for apoio in viga.apoios
            ],
        },
        resultados=resultados,
        conclusao="Verificação concluída",
    )


SCRIPT_SIMPLES = """
viga 6
secao retangular 150 300
material catalogo ASTM A36 aço estrutural
apoio 0 pino
apoio 6 rolete
q 0 6 15 baixo
"""

SCRIPT_COMBINADO = """
viga 8
secao retangular 200 500
material catalogo ASTM A572 grau 50
apoio 0 pino
apoio 8 rolete
q 0 8 12 baixo
q 0 8 20 baixo caso=Sobrecarga
combinacao ELU Permanente=1.4 Sobrecarga=1.5
combinacao ELS Permanente=1.0 Sobrecarga=1.0
"""


class RegistroDeProvedoresTests(unittest.TestCase):
    def test_provedor_de_vigas_esta_registrado_apos_os_registros(self):
        ids = [item.id for item in listar_provedores(apos="registros")]
        self.assertIn("vigas_eixos", ids)

    def test_titulo_entra_no_catalogo_de_secoes(self):
        self.assertIn("vigas_eixos", titulos_secoes_extensao())
        self.assertIn("vigas_eixos", SECOES_RELATORIO)

    def test_contrato_do_modulo_aponta_para_o_provedor(self):
        # O campo existe para ligar módulo e seção do memorial; se ele
        # apontasse para um provedor inexistente, ninguém perceberia.
        modulo = obter_modulo("vigas_eixos")
        self.assertEqual(modulo.provedor_relatorio, "vigas_eixos")
        self.assertIn(modulo.provedor_relatorio, titulos_secoes_extensao())

    def test_provedor_duplicado_e_recusado(self):
        with self.assertRaises(ValueError):
            registrar_provedor(
                ProvedorSecaoRelatorio(
                    id="vigas_eixos",
                    titulo="Duplicado",
                    apos="registros",
                    ordem=1,
                    construir=lambda projeto, contexto: {},
                )
            )


class SecaoDeVigasTests(unittest.TestCase):
    def secao(self, projeto) -> dict:
        modelo = montar_modelo_relatorio(projeto)
        for secao in modelo["secoes"]:
            if "Vigas e eixos" in secao.get("titulo", ""):
                return secao
        self.fail("seção de vigas ausente do memorial")

    def test_projeto_sem_vigas_gera_secao_vazia_sem_quebrar(self):
        secao = self.secao(projeto_minimo())
        self.assertIn("0 análise(s)", " ".join(secao["paragrafos"]))
        for tabela in secao["tabelas"]:
            self.assertTrue(tabela["linhas"])

    def test_barra_comprimida_ganha_tabela_de_estabilidade(self):
        # Perfil I fletido em x e comprimido: a carga crítica fora do plano
        # (Iy) é a que manda, e o memorial precisa mostrar as duas.
        comprimida = (
            "viga 6\nsecao perfil_i 300 150 8 12\nmaterial aco\napoio 0 pino\n"
            "apoio 6 rolete\nq 0 6 5 baixo\nN 6 50 compressao"
        )
        secao = self.secao(projeto_minimo(registro_de_viga(comprimida)))
        tabela = next(t for t in secao["tabelas"] if "Estabilidade" in t["legenda"])
        linha = tabela["linhas"][0]
        self.assertEqual(linha[0], "Viga do mezanino")
        self.assertLess(float(linha[2].replace(".", "").replace(",", ".")), float(linha[1].replace(".", "").replace(",", ".")))
        self.assertIn(linha[4], {"Folgada", "Sensível à segunda ordem", "Compressão acima da carga crítica"})

    def test_barra_sem_compressao_nao_tem_tabela_de_estabilidade(self):
        secao = self.secao(projeto_minimo(registro_de_viga(SCRIPT_SIMPLES)))
        self.assertFalse(any("Estabilidade" in t["legenda"] for t in secao["tabelas"]))

    def test_viga_registrada_aparece_com_a_secao_governante(self):
        secao = self.secao(projeto_minimo(registro_de_viga(SCRIPT_SIMPLES)))
        texto = str(secao)
        self.assertIn("Viga do mezanino", texto)
        self.assertIn("Retangular", texto)
        # M = wL²/8 = 15 × 6² / 8 = 67,5 kN·m, no meio do vão.
        self.assertIn("67,5", texto)
        self.assertIn("x = 3", texto)

    def test_reacoes_entram_na_tabela(self):
        secao = self.secao(projeto_minimo(registro_de_viga(SCRIPT_SIMPLES)))
        tabela = next(t for t in secao["tabelas"] if "Reações" in t["legenda"])
        self.assertEqual(len(tabela["linhas"]), 2)
        # wL/2 = 45 kN em cada apoio.
        self.assertTrue(any("45" in str(celula) for celula in tabela["linhas"][0]))

    def test_material_rastreavel_chega_ao_memorial(self):
        secao = self.secao(projeto_minimo(registro_de_viga(SCRIPT_SIMPLES)))
        self.assertIn("Catálogo orientativo", str(secao))

    def test_criterio_de_flecha_aparece_com_a_situacao(self):
        secao = self.secao(projeto_minimo(registro_de_viga(SCRIPT_SIMPLES)))
        tabela = next(t for t in secao["tabelas"] if "Verificação" in t["legenda"])
        celula = tabela["linhas"][0][-1]
        self.assertIn("L/350", celula)
        self.assertIn(celula.splitlines()[-1], {"Atende", "Excedida"})

    def test_envoltoria_vira_tabela_de_combinacoes_governantes(self):
        secao = self.secao(
            projeto_minimo(registro_de_viga(SCRIPT_COMBINADO, com_envoltoria=True))
        )
        tabela = next(t for t in secao["tabelas"] if "Envoltória" in t["legenda"])
        self.assertTrue(any("ELU" in str(linha) for linha in tabela["linhas"]))
        self.assertIn("governa cada grandeza", " ".join(secao["paragrafos"]))

    def test_sem_combinacoes_a_tabela_de_envoltoria_nao_aparece(self):
        secao = self.secao(projeto_minimo(registro_de_viga(SCRIPT_SIMPLES)))
        self.assertFalse(any("Envoltória" in t["legenda"] for t in secao["tabelas"]))

    def test_varias_barras_sao_listadas_juntas(self):
        secao = self.secao(
            projeto_minimo(
                registro_de_viga(SCRIPT_SIMPLES, titulo="Viga A"),
                registro_de_viga(SCRIPT_COMBINADO, titulo="Viga B", com_envoltoria=True),
            )
        )
        tabela = next(t for t in secao["tabelas"] if "Barras analisadas" in t["legenda"])
        self.assertEqual(len(tabela["linhas"]), 2)
        self.assertIn("2 análise(s)", " ".join(secao["paragrafos"]))

    def test_registro_de_outro_modulo_e_ignorado(self):
        alheio = criar_registro_tecnico(
            modulo="Análise estática",
            modulo_id="analise_estatica",
            titulo="Estado plano",
            status="Atende",
            resumo="",
            entradas={},
            resultados={"von_mises_MPa": 100.0},
        )
        secao = self.secao(projeto_minimo(alheio, registro_de_viga(SCRIPT_SIMPLES)))
        self.assertIn("1 análise(s)", " ".join(secao["paragrafos"]))
        self.assertNotIn("Estado plano", str(secao))

    def test_registro_incompleto_nao_derruba_o_memorial(self):
        # Registros antigos ou truncados precisam degradar para "não
        # informado" em vez de impedir a emissão do memorial inteiro.
        truncado = criar_registro_tecnico(
            modulo="Vigas e eixos",
            modulo_id="vigas_eixos",
            titulo="Registro antigo",
            status="Calculado",
            resumo="",
            entradas={},
            resultados={},
        )
        secao = self.secao(projeto_minimo(truncado))
        self.assertIn("Registro antigo", str(secao))
        self.assertIn("Não informado", str(secao))

    def test_nota_declara_os_limites_do_modelo(self):
        secao = self.secao(projeto_minimo(registro_de_viga(SCRIPT_SIMPLES)))
        self.assertIn("P–Δ", secao["nota"])
        self.assertIn("flambagem", secao["nota"])


class DiagramasNoMemorialTests(unittest.TestCase):
    def secao(self, projeto) -> dict:
        """Capítulo do registro da viga — é lá que os diagramas moram agora.

        Com o capítulo de registros ativo, a seção-provedora de vigas não
        repete os diagramas; ela só os desenha quando o memorial sai sem os
        registros (ver ``test_provedor_desenha_quando_nao_ha_capitulo``).
        """
        modelo = montar_modelo_relatorio(projeto)
        secoes = modelo["secoes"]
        inicio = next(
            indice for indice, s in enumerate(secoes) if "Registros técnicos" in s.get("titulo", "")
        )
        return next(s for s in secoes[inicio + 1 :] if "imagens" in s)

    def test_provedor_desenha_quando_nao_ha_capitulo(self):
        modelo = montar_modelo_relatorio(
            projeto_minimo(registro_de_viga(SCRIPT_SIMPLES)),
            secoes_incluidas=["vigas_eixos"],
        )
        secao = next(s for s in modelo["secoes"] if "Vigas e eixos" in s.get("titulo", ""))
        self.assertTrue(secao["imagens"])

    def test_provedor_nao_repete_os_diagramas_do_capitulo(self):
        modelo = montar_modelo_relatorio(projeto_minimo(registro_de_viga(SCRIPT_SIMPLES)))
        secao = next(s for s in modelo["secoes"] if "Vigas e eixos" in s.get("titulo", ""))
        self.assertEqual(secao["imagens"], [])
        self.assertTrue(any("capítulo do respectivo registro" in p for p in secao["paragrafos"]))

    def test_diagramas_entram_como_imagem(self):
        secao = self.secao(projeto_minimo(registro_de_viga(SCRIPT_SIMPLES)))
        imagens = secao["imagens"]
        titulos = [imagem["titulo"] for imagem in imagens]
        self.assertIn("Esforço cortante V (kN)", titulos)
        self.assertIn("Momento fletor M (kN·m)", titulos)
        self.assertIn("Linha elástica — flecha (mm)", titulos)
        for imagem in imagens:
            with self.subTest(imagem=imagem["titulo"]):
                # Assinatura PNG: 89 50 4E 47 0D 0A 1A 0A.
                self.assertEqual(
                    imagem["png"][:8],
                    bytes((137, 80, 78, 71, 13, 10, 26, 10)),
                )
                self.assertGreater(len(imagem["png"]), 1_000)
                self.assertIn("Viga do mezanino", imagem["legenda"])

    def test_diagramas_sem_esforco_nao_sao_desenhados(self):
        # Uma viga sem carga axial nem torque não deve gastar meia página com
        # dois diagramas retos no zero.
        titulos = [
            imagem["titulo"]
            for imagem in self.secao(projeto_minimo(registro_de_viga(SCRIPT_SIMPLES)))["imagens"]
        ]
        self.assertNotIn("Torque T (kN·m)", titulos)
        self.assertNotIn("Esforço normal N (kN)", titulos)

    def test_envoltoria_acrescenta_as_faixas(self):
        secao = self.secao(
            projeto_minimo(registro_de_viga(SCRIPT_COMBINADO, com_envoltoria=True))
        )
        titulos = [imagem["titulo"] for imagem in secao["imagens"]]
        self.assertIn("Envoltória de momento M (kN·m)", titulos)
        self.assertIn("Envoltória de flecha (mm)", titulos)

    def test_registro_sem_modelo_guardado_avisa_em_vez_de_quebrar(self):
        antigo = criar_registro_tecnico(
            modulo="Vigas e eixos",
            modulo_id="vigas_eixos",
            titulo="Registro sem modelo",
            status="Calculado",
            resumo="",
            entradas={},
            resultados={},
        )
        secao = self.secao(projeto_minimo(antigo))
        self.assertEqual(secao["imagens"], [])
        self.assertTrue(
            any("diagramas indisponíveis" in p for p in secao["paragrafos"])
        )

    def test_modelo_invalido_nao_derruba_o_memorial(self):
        quebrado = criar_registro_tecnico(
            modulo="Vigas e eixos",
            modulo_id="vigas_eixos",
            titulo="Modelo corrompido",
            status="Calculado",
            resumo="",
            entradas={"script_modelo": "viga 6\nlixo total"},
            resultados={},
        )
        secao = self.secao(projeto_minimo(quebrado))
        self.assertEqual(secao["imagens"], [])
        self.assertTrue(
            any("redesenhar os diagramas" in p for p in secao["paragrafos"])
        )

    def test_resultado_divergente_omite_o_grafico(self):
        # Se o modelo guardado não reproduz mais o número registrado, o
        # gráfico contradiria a tabela ao lado — melhor não desenhar.
        registro = registro_de_viga(SCRIPT_SIMPLES)
        registro["resultados"]["momento_maximo_kNm"] = 999.0
        secao = self.secao(projeto_minimo(registro))
        self.assertEqual(secao["imagens"], [])
        self.assertTrue(any("omitidos" in p for p in secao["paragrafos"]))

    def test_word_embute_as_imagens(self):
        from core.project_report import gerar_relatorio_industrial_word

        conteudo = gerar_relatorio_industrial_word(
            projeto_minimo(registro_de_viga(SCRIPT_SIMPLES))
        )
        # As partes de mídia do .docx são um zip; contar os PNGs embutidos.
        import zipfile

        with zipfile.ZipFile(io.BytesIO(conteudo)) as arquivo:
            midia = [
                nome
                for nome in arquivo.namelist()
                if nome.startswith("word/media/") and nome.endswith(".png")
            ]
        self.assertGreaterEqual(len(midia), 3)

    def test_pdf_embute_as_imagens(self):
        from core.project_report import gerar_relatorio_industrial_pdf

        conteudo = gerar_relatorio_industrial_pdf(
            projeto_minimo(registro_de_viga(SCRIPT_SIMPLES))
        )
        self.assertTrue(conteudo.startswith(b"%PDF"))
        self.assertIn(b"/Image", conteudo)


class LarguraDasTabelasTests(unittest.TestCase):
    def test_larguras_batem_com_a_largura_util_da_pagina(self):
        # Todas as tabelas do memorial somam 9360 twips; uma soma diferente
        # desalinha a coluna no Word em relação às demais seções.
        modelo = montar_modelo_relatorio(
            projeto_minimo(registro_de_viga(SCRIPT_COMBINADO, com_envoltoria=True))
        )
        for secao in modelo["secoes"]:
            for tabela in secao.get("tabelas", []):
                larguras = tabela.get("larguras")
                if not larguras:
                    continue
                with self.subTest(tabela=tabela.get("legenda")):
                    self.assertEqual(sum(larguras), 9_360)
                    self.assertEqual(len(larguras), len(tabela["cabecalhos"]))

    def test_cada_linha_tem_o_numero_de_colunas_do_cabecalho(self):
        modelo = montar_modelo_relatorio(
            projeto_minimo(registro_de_viga(SCRIPT_COMBINADO, com_envoltoria=True))
        )
        for secao in modelo["secoes"]:
            for tabela in secao.get("tabelas", []):
                esperado = len(tabela["cabecalhos"])
                for linha in tabela["linhas"]:
                    with self.subTest(tabela=tabela.get("legenda")):
                        self.assertEqual(len(linha), esperado)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
