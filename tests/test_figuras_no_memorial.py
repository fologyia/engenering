"""Figuras das páginas no memorial: o registro guarda o que é preciso e o memorial desenha de novo.

* desenho 2D pronto (``figuras_2d``): contraventamento (planta e elevações) e viga de piso;
* ligação parafusada refeita pela entrada (``figura_parafusos``), conferindo o aproveitamento;
* seção e coluna em pé (``figura_coluna``): Flambagem de colunas e Pilares do modelo;
* figuras dos casos do Cálculo de peças e da Desenhar seção (``figuras_do_caso``), refeitas com os
  valores gravados e conferidas pelo resumo;
* o esquema do modelo antes dos diagramas em Vigas e eixos.
"""

from __future__ import annotations

import io
import json
import xml.etree.ElementTree as ET
from dataclasses import replace

import pytest
from docx import Document
from PIL import Image
from pypdf import PdfReader

from components.cena_3d_svg import svg_da_cena
from core import bolted_joint_check as chk
from core import cena_3d as c3
from core import cena_3d_png
from core import column_buckling as cb
from core import contraventamento_estrutura_registro as cer
from core import contraventamento_plataforma as cp
from core import desenho_contraventamento as dcv
from core import desenho_da_coluna as dc
from core import elementos_base as eb
from core import elementos_catalogo as cat
from core import perfis_compostos as pc
from core import secao_relatorio as sr
from core import section_catalog as sc
from core import viga_de_piso as vp
from core.project_report import (
    gerar_relatorio_industrial_pdf,
    gerar_relatorio_industrial_word,
    montar_modelo_relatorio,
)
from core.record_charts import CHAVES_DE_FIGURA, imagens_do_registro
from core.technical_records import normalizar_registro_tecnico

SVG = "{http://www.w3.org/2000/svg}"


def do_banco(registro: dict) -> dict:
    """O registro como volta do banco (JSON)."""
    return json.loads(json.dumps(registro))


def textos_do_svg(svg: str) -> str:
    raiz = ET.fromstring(svg)
    assert raiz.tag == f"{SVG}svg"
    return " ".join("".join(t.itertext()) for t in raiz.iter(f"{SVG}text"))


def png_valido(dados: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(dados)) as imagem:
        assert imagem.format == "PNG"
        return imagem.size


# ------------------------------------------------------------------ desenho 2D gravado
def desenho_de_teste() -> c3.Desenho2D:
    return c3.Desenho2D(
        300.0,
        200.0,
        (
            c3.Poligono2D(((10, 10), (60, 10), (60, 40)), "#ffffff", "#000000", 1.2, 0.8),
            c3.Linha2D((0, 0), (100, 100), "#1f6feb", 2.0, "6 5", 0.9),
            c3.Seta2D((10, 150), (90, 150), "#d4760a", 2.6, 10.0, True),
            c3.Etiqueta2D(150, 100, "L = 6,00 m", "#6b7280", 11.0, "bold", False, "start", -90),
            c3.circulo((200, 50), 11.0),
        ),
        "Título",
        "Subtítulo",
        legenda=(("#1f6feb", "tração"),),
    )


def test_desenho_2d_vai_e_volta_do_registro():
    original = desenho_de_teste()
    gravado = do_banco(c3.desenho_para_dicionario(original, legenda="Legenda da figura."))
    lido = c3.desenho_de_dicionario(gravado)
    assert lido is not None
    assert (lido.largura, lido.altura, lido.titulo, lido.subtitulo) == (300, 200, "Título",
                                                                        "Subtítulo")  # fmt: skip
    assert lido.legenda == original.legenda
    assert [type(i) for i in lido.itens] == [type(i) for i in original.itens]
    etiqueta = lido.itens[3]
    assert isinstance(etiqueta, c3.Etiqueta2D)
    assert (etiqueta.ancora, etiqueta.giro, etiqueta.peso) == ("start", -90, "bold")
    assert gravado["legenda"] == "Legenda da figura."


@pytest.mark.parametrize("estragado", [None, [], {"largura": 0, "altura": 10}, {"altura": 5}])
def test_desenho_estragado_volta_none(estragado):
    assert c3.desenho_de_dicionario(estragado) is None


def test_item_estragado_fica_de_fora_sem_derrubar_o_resto():
    gravado = do_banco(c3.desenho_para_dicionario(desenho_de_teste()))
    gravado["itens"] += [
        ["l", "x", [1, 2]],
        ["?"],
        7,
        ["e", "a", 0, "t", "#000", 1, "n", 0, "m", 0],
    ]
    lido = c3.desenho_de_dicionario(gravado)
    assert lido is not None and len(lido.itens) == 5


def test_texto_girado_e_ancora_no_svg_e_no_png():
    desenho = desenho_de_teste()
    svg = svg_da_cena(desenho)
    assert 'transform="rotate(-90.0 150.0 100.0)"' in svg
    assert 'text-anchor="start"' in svg
    assert png_valido(cena_3d_png.png_da_cena(desenho)) == (600, 400)


# ------------------------------------------------------------------ contraventamento
@pytest.fixture(scope="module")
def contraventamento() -> cp.ResultadoContraventamento:
    return cp.calcular(replace(cp.EntradaContraventamento(), cotas_m=(3.0, 6.0)))


def test_planta_e_elevacao_na_pagina_sao_svg_com_as_forcas(contraventamento):
    r = contraventamento
    planta = textos_do_svg(svg_da_cena(dcv.planta(r.entrada)))
    assert "Vento X" in planta and "Vento Y" in planta and "L_x = 12,00 m" in planta
    for direcao in cp.DIRECOES:
        andares = r.andares_da_direcao(direcao)
        escrito = textos_do_svg(svg_da_cena(dcv.elevacao_da_linha(r.entrada, andares, direcao)))
        for andar in andares:
            assert f"+{andar.tracao_kN:.1f}".replace(".", ",") in escrito
            assert f"V{andar.andar} = {andar.forca_na_linha_kN:.1f}".replace(".", ",") in escrito


@pytest.mark.parametrize("tipo", list(cp.TIPOS))
def test_elevacao_de_cada_tipo_de_contraventamento(contraventamento, tipo):
    e = contraventamento.entrada
    e = replace(e, contraventamento_x=replace(e.contraventamento_x, tipo=tipo))
    r = cp.calcular(e)
    desenho = dcv.elevacao_da_linha(e, r.andares_da_direcao("X"), "X")
    assert png_valido(cena_3d_png.png_da_cena(desenho))[0] > 0


def test_registro_do_contraventamento_leva_a_planta_e_as_elevacoes(contraventamento):
    registro = do_banco(cer.registro_contraventamento(contraventamento))
    imagens, aviso = imagens_do_registro(registro, {})
    assert aviso == ""
    assert [i["titulo"] for i in imagens] == [
        "Planta — linhas contraventadas",
        "Elevação da linha mais carregada — direção X",
        "Elevação da linha mais carregada — direção Y",
    ]
    assert all(png_valido(i["png"]) == (i["largura_px"], i["altura_px"]) for i in imagens)


# ------------------------------------------------------------------ viga de piso
def test_viga_de_piso_mostra_a_concentrada_so_quando_existe():
    com = vp.calcular(vp.EntradaVigaDePiso(concentrada_kN=10.0))
    sem = vp.calcular(vp.EntradaVigaDePiso())
    assert "P = 10,0 kN" in textos_do_svg(svg_da_cena(vp.esquema_da_viga(com)))
    assert "P = " not in textos_do_svg(svg_da_cena(vp.esquema_da_viga(sem)))


def test_registro_da_viga_de_piso_leva_o_esquema():
    r = vp.calcular(vp.EntradaVigaDePiso(concentrada_kN=10.0))
    imagens, aviso = imagens_do_registro(do_banco(vp.registro_viga(r)), {})
    assert aviso == "" and [i["titulo"] for i in imagens] == ["Viga de piso biapoiada"]


# ------------------------------------------------------------------ parafusos
def ligacao() -> tuple[chk.EntradaLigacao, chk.ResultadoLigacao]:
    entrada = chk.EntradaLigacao(N=50.0, V=80.0, M=5.0, n_lin=3, n_col=2)
    return entrada, chk.verificar_ligacao(entrada)


def test_entrada_da_ligacao_vai_e_volta_igual():
    coordenadas = chk.EntradaLigacao(coordenadas=((0.0, 0.0), (70.0, 0.0), (0.0, 80.0)),
                                     fora_do_escopo=("fadiga",))  # fmt: skip
    for entrada in (ligacao()[0], coordenadas):
        gravada = chk.entrada_para_dicionario(entrada)
        assert gravada is not None
        assert chk.entrada_de_dicionario(do_banco(gravada)) == entrada


def test_entrada_com_campo_desconhecido_ou_infinito():
    assert chk.entrada_para_dicionario(chk.EntradaLigacao(N=float("inf"))) is None
    gravada = {**chk.entrada_para_dicionario(ligacao()[0]), "campo_de_outra_versao": 1}
    assert chk.entrada_de_dicionario(gravada) == ligacao()[0]


def test_registro_dos_parafusos_leva_a_planta_e_o_corte():
    entrada, resultado = ligacao()
    imagens, aviso = imagens_do_registro(
        do_banco(chk.registro_ligacao(entrada, resultado, None)), {}
    )
    assert aviso == "" and len(imagens) == 1
    assert imagens[0]["titulo"] == "Ligação parafusada — 6 × M22 A325"


def test_ligacao_que_mudou_desde_o_registro_fica_sem_figura():
    entrada, resultado = ligacao()
    registro = do_banco(chk.registro_ligacao(entrada, resultado, None))
    registro["resultados"]["utilizacao_maxima"] *= 0.5
    imagens, aviso = imagens_do_registro(registro, {})
    assert imagens == [] and "registre a ligação de novo" in aviso


# ------------------------------------------------------------------ coluna em pé
def coluna_composta() -> dc.ColunaEmPe:
    secao = pc.duas_cantoneiras(pc.cantoneira(76.2, 76.2, 6.35), pc.ARRANJO_2L_CRUZ, 8.0)
    return dc.ColunaEmPe(secao, 3000.0, 3000.0, 3000.0, 1.0, 1.0, "Biapoiada (pino-pino)",
                         "Biapoiada (pino-pino)", espacadores_mm=(1000.0, 2000.0))  # fmt: skip


def coluna_com_mao_francesa() -> dc.ColunaEmPe:
    secao = cb.secao_de_perfil(sc.listar_perfis()["W 250 x 32,7"])
    return dc.ColunaEmPe(
        secao, 4000.0, 4000.0, 2000.0, 1.0, 1.0, "Biapoiada (pino-pino)", "Biapoiada (pino-pino)",
        dc.MaoFrancesaNoDesenho(20.0, 45.0, 3000.0, "x", 120.0), travas_y_mm=(2000.0,),
    )  # fmt: skip


@pytest.mark.parametrize("fabrica", [coluna_composta, coluna_com_mao_francesa])
def test_coluna_vai_e_volta_do_registro(fabrica):
    coluna = fabrica()
    gravada = dc.coluna_para_o_registro(coluna, giro_da_secao=30.0)
    assert gravada is not None
    lida, giro, com_secao = dc.coluna_do_registro(do_banco(gravada))
    assert lida == coluna and giro == 30.0 and com_secao
    assert dc.figura_da_coluna(lida).png == dc.figura_da_coluna(coluna).png


def test_flambagem_registrada_leva_a_secao_e_a_coluna_em_pe():
    coluna = coluna_com_mao_francesa()
    entrada = cb.EntradaColuna(
        secao=coluna.secao, fy_MPa=345.0, norma="NBR8800_2008", Lx_mm=4000.0, Ly_mm=2000.0,
        N_Sd_kN=300.0, Mx_kNm=40.0, My_kNm=3.0, razao_m1_m2_x=0.0,
    )  # fmt: skip
    resultado = cb.verificar_coluna(entrada)
    sem = do_banco(cb.registro_coluna(entrada, resultado))
    com = do_banco(
        cb.registro_coluna(
            entrada, resultado,
            figura_da_coluna=dc.coluna_para_o_registro(coluna, giro_da_secao=90.0),
        )
    )  # fmt: skip
    imagens_sem, _ = imagens_do_registro(sem, {})
    imagens, aviso = imagens_do_registro(com, {})
    assert aviso == "" and len(imagens) == len(imagens_sem) + 2
    titulos = [i["titulo"] for i in imagens]
    assert "Seção da coluna — W 250 x 32,7" in titulos and "Coluna em pé — W 250 x 32,7" in titulos
    assert any("girado 90°" in i["legenda"] for i in imagens)


def test_coluna_estragada_omite_as_figuras_com_o_motivo():
    registro = {"modulo_id": "flambagem_colunas", "resultados": {"figura_coluna": {"secao": 1}}}
    imagens, aviso = imagens_do_registro(registro, {})
    assert imagens == [] and aviso.startswith("Gráfico omitido")


# ------------------------------------------------------------------ casos do Cálculo de peças
def casos_com_figura() -> list[eb.Caso]:
    casos = []
    for caso in cat.CASOS.values():
        try:
            resultado = caso.calcular(caso.padroes())
        except ValueError:
            continue
        if resultado.figuras:
            casos.append(caso)
    return casos


@pytest.mark.parametrize("caso", casos_com_figura(), ids=lambda c: c.id)
def test_figuras_do_caso_entram_no_memorial(caso):
    valores = caso.padroes()
    resultado = caso.calcular(valores)
    dados = do_banco(eb.dados_do_registro(caso, valores, resultado, modulo="Cálculo de peças",
                                          modulo_id="assistente_cargas"))  # fmt: skip
    imagens, aviso = imagens_do_registro(dados, {})
    assert aviso == ""
    assert [i["titulo"] for i in imagens] == [f.titulo for f in resultado.figuras]
    assert all(png_valido(i["png"]) == (i["largura_px"], i["altura_px"]) for i in imagens)


def test_caso_sem_figura_nao_grava_os_valores():
    caso = next(c for c in cat.CASOS.values() if not c.calcular(c.padroes()).figuras)
    dados = eb.dados_do_registro(caso, caso.padroes(), caso.calcular(caso.padroes()),
                                 modulo="Cálculo de peças", modulo_id="assistente_cargas")  # fmt: skip
    assert eb.CHAVE_FIGURAS_DO_CASO not in dados["resultados"]


def test_caso_que_mudou_desde_o_registro_fica_sem_figura():
    caso = casos_com_figura()[0]
    valores = caso.padroes()
    dados = do_banco(eb.dados_do_registro(caso, valores, caso.calcular(valores),
                                          modulo="Cálculo de peças",
                                          modulo_id="assistente_cargas"))  # fmt: skip
    dados["resultados"][eb.CHAVE_FIGURAS_DO_CASO]["resumo"] = "outro resultado"
    imagens, aviso = imagens_do_registro(dados, {})
    assert imagens == [] and "registre o cálculo de novo" in aviso


def test_caso_que_nao_existe_mais_fica_sem_figura():
    dados = {"resultados": {eb.CHAVE_FIGURAS_DO_CASO: {"caso": "caso_apagado", "valores": {}}}}
    assert imagens_do_registro(dados, {}) == ([], "")


def test_secao_desenhada_leva_o_desenho_da_secao():
    valores = {
        **sr.CASO.padroes(),
        "partes": [
            {
                "forma": "Retângulo",
                "tipo": sr.CHEIO,
                "x": 0.0,
                "y": 0.0,
                "b": 100.0,
                "h": 10.0,
                "giro": 0.0,
                "pontos": "",
            },
            {
                "forma": "Retângulo",
                "tipo": sr.CHEIO,
                "x": 0.0,
                "y": 55.0,
                "b": 10.0,
                "h": 100.0,
                "giro": 0.0,
                "pontos": "",
            },
        ],  # fmt: skip
    }
    resultado = sr.CASO.calcular(valores)
    dados = do_banco(eb.dados_do_registro(sr.CASO, valores, resultado, modulo="Desenhar seção",
                                          modulo_id="desenhar_secao"))  # fmt: skip
    imagens, aviso = imagens_do_registro(dados, {})
    assert aviso == "" and [i["titulo"] for i in imagens] == ["Seção"]


# ------------------------------------------------------------------ memorial de ponta a ponta
def test_memorial_word_e_pdf_com_as_figuras_novas(contraventamento):
    from tests.test_project_validation import _projeto_documentado

    entrada, resultado = ligacao()
    viga = vp.calcular(vp.EntradaVigaDePiso(concentrada_kN=10.0))
    projeto = _projeto_documentado()
    projeto["registros_tecnicos"] = [
        normalizar_registro_tecnico(registro)
        for registro in (
            cer.registro_contraventamento(contraventamento),
            vp.registro_viga(viga),
            chk.registro_ligacao(entrada, resultado, None),
        )
    ]
    modelo = montar_modelo_relatorio(projeto, secoes_incluidas=["registros"])
    blocos = [b for s in modelo["secoes"] for b in s.get("blocos", [])]
    assert sum(1 for b in blocos if b["tipo"] == "imagem") == 3 + 1 + 1
    texto_dos_blocos = json.dumps(blocos, ensure_ascii=False, default=str)
    for chave in CHAVES_DE_FIGURA:
        assert f'"{chave}"' not in texto_dos_blocos, chave

    word = Document(io.BytesIO(gerar_relatorio_industrial_word(projeto,
                                                               secoes_incluidas=["registros"])))  # fmt: skip
    assert len(word.inline_shapes) >= 5
    pdf = PdfReader(io.BytesIO(gerar_relatorio_industrial_pdf(projeto,
                                                              secoes_incluidas=["registros"])))  # fmt: skip
    assert sum(len(pagina.images) for pagina in pdf.pages) >= 5


def test_capitulo_antigo_nao_imprime_os_dados_das_figuras():
    """Registro sem verificações nem destaque cai no capítulo genérico: os dados gravados para
    redesenhar não podem virar texto."""
    from tests.test_project_validation import _projeto_documentado

    projeto = _projeto_documentado()
    gravado = c3.desenho_para_dicionario(desenho_de_teste(), legenda="Figura de teste.")
    projeto["registros_tecnicos"] = [
        normalizar_registro_tecnico(
            {
                "modulo": "Análise estática",
                "modulo_id": "analise_estatica",
                "titulo": "Peça qualquer",
                "status": "Calculado",
                "entradas": {"forca_kN": 10.0},
                "resultados": {"tensao_MPa": 50.0, "figuras_2d": [gravado]},
            }
        )
    ]
    modelo = montar_modelo_relatorio(projeto, secoes_incluidas=["registros"])
    texto = json.dumps(modelo["secoes"], ensure_ascii=False, default=str)
    assert "Tensao" in texto or "Tensão" in texto  # o resultado de verdade continua lá
    assert '"itens"' not in texto and "#1f6feb" not in texto and "Figuras 2d" not in texto
