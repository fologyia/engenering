"""Testes da montagem de diagramas de viga como imagem (PNG) para o memorial."""

from io import BytesIO

from PIL import Image

from core import beam_analysis as vb
from core.beam_charts import (
    SerieDiagrama,
    imagens_do_resultado,
    renderizar_diagrama,
    series_da_envoltoria,
    series_do_resultado,
)
from tests.test_beam_analysis import viga_padrao
from tests.test_beam_envelope import viga_de_tres_casos


def _png_valido(png: bytes) -> tuple[int, int]:
    imagem = Image.open(BytesIO(png))
    assert imagem.format == "PNG"
    return imagem.size


def test_series_do_resultado_traz_cortante_momento_e_flecha_biapoiada():
    resultado = vb.analisar_viga(
        viga_padrao(cargas_pontuais=(vb.CargaPontual(3_000.0, -20_000.0),))
    )
    series = series_do_resultado(resultado)
    titulos = [serie.titulo for serie in series]
    assert any("cortante" in titulo.lower() for titulo in titulos)
    assert any("momento" in titulo.lower() for titulo in titulos)
    assert any("flecha" in titulo.lower() for titulo in titulos)
    # Só cortante, momento e flecha: normal e torque nulos não entram.
    assert len(series) == 3
    assert all(len(serie.pontos) == len(resultado.pontos) for serie in series)


def test_series_do_resultado_inclui_normal_quando_ha_carga_axial():
    resultado = vb.analisar_viga(
        viga_padrao(cargas_axiais=(vb.CargaAxial(6_000.0, 10_000.0),))
    )
    titulos = [serie.titulo for serie in series_do_resultado(resultado)]
    assert any("normal" in titulo.lower() for titulo in titulos)


def test_series_do_resultado_inclui_torque_quando_ha_torcao():
    resultado = vb.analisar_viga(
        viga_padrao(torques=(vb.Torque(3_000.0, 5_000_000.0),))
    )
    titulos = [serie.titulo for serie in series_do_resultado(resultado)]
    assert any("torque" in titulo.lower() for titulo in titulos)


def test_serie_de_cortante_usa_kn_e_escala_correta():
    resultado = vb.analisar_viga(
        viga_padrao(cargas_pontuais=(vb.CargaPontual(3_000.0, -20_000.0),))
    )
    serie_cortante = next(
        serie for serie in series_do_resultado(resultado) if "cortante" in serie.titulo.lower()
    )
    extremo_serie = max(serie_cortante.pontos, key=lambda ponto: abs(ponto[1]))
    ponto_extremo = max(resultado.pontos, key=lambda ponto: abs(ponto.cortante_N))
    assert abs(extremo_serie[1]) - abs(ponto_extremo.cortante_N / 1_000.0) < 1e-6


def test_renderizar_diagrama_gera_png_no_tamanho_pedido():
    serie = SerieDiagrama(
        titulo="Momento fletor M (kN·m)",
        unidade="kN·m",
        pontos=((0.0, 0.0), (3.0, -30.0), (6.0, 0.0)),
    )
    imagem = renderizar_diagrama(serie, largura_px=400, altura_px=150)
    assert imagem.largura_px == 400
    assert imagem.altura_px == 150
    assert _png_valido(imagem.png) == (400, 150)
    assert imagem.legenda == serie.titulo


def test_renderizar_diagrama_recusa_serie_vazia():
    serie = SerieDiagrama(titulo="Vazia", unidade="kN", pontos=())
    try:
        renderizar_diagrama(serie)
    except ValueError as erro:
        assert "vazia" in str(erro)
    else:
        raise AssertionError("Deveria recusar série sem pontos.")


def test_renderizar_diagrama_em_faixa_desenha_superior_e_inferior():
    serie = SerieDiagrama(
        titulo="Envoltória de momento M (kN·m)",
        unidade="kN·m",
        pontos=((0.0, 10.0), (6.0, 5.0)),
        pontos_inferiores=((0.0, -10.0), (6.0, -5.0)),
    )
    assert serie.e_faixa
    imagem = renderizar_diagrama(serie)
    _png_valido(imagem.png)


def test_series_da_envoltoria_traz_faixas_de_cortante_momento_e_flecha():
    combinacoes = [
        vb.CombinacaoCarga("ELU_gravidade", {"Permanente": 1.4, "Sobrecarga": 1.5}),
        vb.CombinacaoCarga("ELU_vento", {"Permanente": 1.0, "Vento": 1.4}),
    ]
    envoltoria = vb.analisar_envoltoria(viga_de_tres_casos(), combinacoes)
    series = series_da_envoltoria(envoltoria)
    assert len(series) == 3
    assert all(serie.e_faixa for serie in series)
    assert all(len(serie.pontos) == len(serie.pontos_inferiores) for serie in series)


def test_imagens_do_resultado_sem_envoltoria_gera_uma_imagem_por_serie():
    resultado = vb.analisar_viga(
        viga_padrao(cargas_pontuais=(vb.CargaPontual(3_000.0, -20_000.0),))
    )
    imagens = imagens_do_resultado(resultado)
    assert len(imagens) == len(series_do_resultado(resultado))
    for imagem in imagens:
        _png_valido(imagem.png)


def test_imagens_do_resultado_com_envoltoria_soma_as_series():
    viga = viga_de_tres_casos()
    combinacoes = [
        vb.CombinacaoCarga("ELU_gravidade", {"Permanente": 1.4, "Sobrecarga": 1.5}),
    ]
    resultado = vb.analisar_viga(viga)
    envoltoria = vb.analisar_envoltoria(viga, combinacoes)
    imagens = imagens_do_resultado(resultado, envoltoria=envoltoria)
    esperado = len(series_do_resultado(resultado)) + len(series_da_envoltoria(envoltoria))
    assert len(imagens) == esperado
