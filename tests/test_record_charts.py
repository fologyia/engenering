"""Gráficos redesenhados para os capítulos dos registros no memorial."""

import math
from io import BytesIO

from docx import Document
from PIL import Image

from core.project_report import gerar_relatorio_industrial_word, montar_modelo_relatorio
from core.record_charts import imagens_do_registro, imagens_flambagem, imagens_mohr
from core.technical_records import criar_registro_tecnico, normalizar_registro_tecnico
from tests.test_project_validation import _projeto_documentado


def _png_valido(png: bytes) -> tuple[int, int]:
    imagem = Image.open(BytesIO(png))
    assert imagem.format == "PNG"
    return imagem.size


def test_mohr_2d_e_3d_geram_png():
    plano = imagens_mohr(
        {"sigma_x_MPa": 80, "sigma_y_MPa": -20, "tau_xy_MPa": 40, "theta_graus": 30},
        {"sigma_x_transformada_MPa": 89.6, "sigma_y_transformada_MPa": -29.6, "tau_transformada_MPa": -23.3, "von_mises_MPa": 121.2},
    )
    assert len(plano) == 1 and "plano" in plano[0].titulo
    assert _png_valido(plano[0].png) == (plano[0].largura_px, plano[0].altura_px)

    tridimensional = imagens_mohr({}, {"sigma_1_MPa": 120, "sigma_2_MPa": 40, "sigma_3_MPa": -30})
    assert len(tridimensional) == 1 and "tridimensional" in tridimensional[0].titulo
    _png_valido(tridimensional[0].png)

    assert imagens_mohr({"sigma_x_MPa": "abc"}, {}) == []


def test_flambagem_gera_png_e_ignora_registro_incompleto():
    transicao = math.sqrt(2 * math.pi**2 * 200000.0 / 250.0)
    completo = imagens_flambagem(
        {"modulo_elasticidade_MPa": 200000.0, "escoamento_MPa": 250.0, "area_mm2": 1963.5, "forca_solicitante_kN": 50.0},
        {"esbeltez_governante": 160.0, "esbeltez_transicao": transicao, "carga_critica_kN": 151.4, "fator_seguranca": 3.03},
    )
    assert len(completo) == 1
    _png_valido(completo[0].png)
    assert imagens_flambagem({"modulo_elasticidade_MPa": 200000.0}, {}) == []


def test_imagens_do_registro_despacha_por_modulo():
    projeto = _projeto_documentado()
    mohr = normalizar_registro_tecnico(criar_registro_tecnico(
        modulo="Círculo de Mohr", modulo_id="circulo_mohr", titulo="Mohr", status="Calculado", resumo="",
        entradas={"sigma_x_MPa": 50, "sigma_y_MPa": 10, "tau_xy_MPa": 20}, resultados={},
    ))
    imagens, aviso = imagens_do_registro(mohr, projeto)
    assert aviso == "" and len(imagens) == 1 and imagens[0]["png"].startswith(b"\x89PNG")

    sem_desenhista = normalizar_registro_tecnico(criar_registro_tecnico(
        modulo="Projeto de parafusos", modulo_id="projeto_parafusos", titulo="Junta", status="Atende", resumo="",
        entradas={}, resultados={},
    ))
    assert imagens_do_registro(sem_desenhista, projeto) == ([], "")


def test_memorial_embute_grafico_no_capitulo_do_registro():
    projeto = _projeto_documentado()
    projeto["registros_tecnicos"] = [normalizar_registro_tecnico(criar_registro_tecnico(
        modulo="Círculo de Mohr", modulo_id="circulo_mohr", titulo="Ponto A", status="Calculado", resumo="",
        entradas={"sigma_x_MPa": 50, "sigma_y_MPa": 10, "tau_xy_MPa": 20}, resultados={"von_mises_MPa": 55.7},
    ))]
    modelo = montar_modelo_relatorio(projeto, secoes_incluidas=["registros"])
    capitulo = next(item for item in modelo["secoes"] if item.get("nivel", 1) >= 2)
    assert len(capitulo["imagens"]) == 1

    documento = Document(BytesIO(gerar_relatorio_industrial_word(projeto, secoes_incluidas=["registros"])))
    assert len(documento.inline_shapes) >= 1
