"""Vento viga a viga no contraventamento de estruturas abertas: as faixas de influência, a soma
que fecha, os níveis e a planta do esqueleto, a excentricidade real da resultante e as ações de
vento caso a caso no cálculo do contraventamento."""

from __future__ import annotations

import json

import pytest

from core import contraventamento_estrutura_registro as reg
from core import contraventamento_plataforma as cp
from core import contraventamento_vento_barras as cvb
from core import guarda_corpo_do_modelo as gm
from core import leitura_do_modelo as ld
from core import vento_estrutura_aberta as va
from core import vento_por_barras as vpb
from tests.test_guarda_corpo_do_modelo import LINHA, barra, plataforma

PARAMETROS = va.ParametrosVento()


def _ve(corpos=None, cotas=(LINHA,), *, elementos=(), equipamentos=(), direcoes=None):
    g = ld.GeometriaDoModelo(corpos=tuple(corpos or plataforma()), arquivo="plataforma.csv")
    gcs = gm.elementos_ao_vento(gm.bordas_do_piso(g, "Y").marcados(), "Y")
    entrada = cvb.entrada_pelo_esqueleto(
        g,
        "Y",
        PARAMETROS,
        cotas_m=cotas,
        guarda_corpos=[*gcs, *elementos],
        equipamentos=equipamentos,
        **({"direcoes": direcoes} if direcoes else {}),
    )
    r = vpb.calcular(entrada)
    return cvb.vento_nos_niveis(r, cotas, eixo_vertical="Y", arquivo=g.arquivo)


# ------------------------------------------------------------------ faixas
def test_faixas_e_reparte_pela_altura():
    f = cvb.faixas((3.0, 6.0))
    assert f == ((1.5, 4.5), (4.5, float("inf")))
    base, niveis = cvb.reparte(0.0, 6.0, f)  # pilar do chão ao topo
    assert base == pytest.approx(0.25) and niveis == pytest.approx([0.5, 0.25])
    assert cvb.reparte(3.0, 3.0, f) == (0.0, [1.0, 0.0])  # viga do primeiro piso
    assert cvb.reparte(1.0, 1.0, f) == (1.0, [0.0, 0.0])  # baldrame: direto à fundação
    assert cvb.reparte(7.0, 9.0, f) == (0.0, [0.0, 1.0])  # acima do topo: vai para o último


def test_a_soma_dos_niveis_e_da_base_fecha_com_o_vento_de_cada_direcao():
    ve = _ve()
    assert {c.codigo for c in ve.casos} == {f"W{a}" for a in vpb.DIRECOES_COM_DIAGONAIS}
    for c in ve.casos:
        d = ve.resultado.direcao(c.angulo)
        assert c.total_kN("X") == pytest.approx(d.fx_kN)
        assert c.total_kN("Y") == pytest.approx(d.fy_kN)
        assert c.cortantes_kN("X")[0] == pytest.approx(sum(c.fx_kN))
    w0, w90 = ve.caso(0), ve.caso(90)
    assert w0.fx_kN[0] > 0 and w0.fx_base_kN > 0 and w0.fy_kN[0] == pytest.approx(0, abs=1e-9)
    assert w90.fy_kN[0] > 0 and ve.caso(45).fx_kN[0] > 0 and ve.caso(45).fy_kN[0] > 0


def test_dois_pisos_o_cortante_de_baixo_soma_o_de_cima():
    corpos = plataforma()
    corpos += [barra("Meio z0", (0, LINHA / 2, 0), (6, LINHA / 2, 0))]
    ve = _ve(corpos, cotas=(LINHA / 2, LINHA))
    c = ve.caso(0)
    assert c.cortantes_kN("X") == pytest.approx((c.fx_kN[0] + c.fx_kN[1], c.fx_kN[1]))


# ------------------------------------------------------------------ níveis e planta
def test_niveis_do_esqueleto_e_aviso_de_cotas_que_nao_batem():
    assert _ve().niveis_do_esqueleto_m == (round(LINHA, 2),)
    assert not any("cotas" in a for a in _ve().avisos)
    errado = _ve(cotas=(3.0,))
    assert any(
        "vigas do esqueleto estão nas cotas 3,89 m" in a and "3,00" in a for a in errado.avisos
    )
    assert not cvb.cotas_batem(errado.niveis_do_esqueleto_m, (3.0,))
    assert cvb.cotas_batem((3.89,), (3.95,))


def test_planta_dos_pisos_e_aviso_de_medidas():
    ve = _ve()
    assert ve.planta_m == pytest.approx((6.0, 4.0))  # X × Y (Z do modelo vira −Y da planta)
    assert cvb.avisos_da_planta(ve, 6.0, 4.0) == []
    assert "trocadas" in cvb.avisos_da_planta(ve, 4.0, 6.0)[0]
    assert "não bate" in cvb.avisos_da_planta(ve, 12.0, 6.0)[0]


# ------------------------------------------------------------------ excentricidade
def test_estrutura_simetrica_tem_a_resultante_no_centro():
    ve = _ve()
    assert ve.excentricidade_real["X"] == pytest.approx(0, abs=1e-6)
    assert ve.excentricidade_real["Y"] == pytest.approx(0, abs=1e-6)


def test_painel_de_um_lado_desloca_a_resultante_e_a_linha_mais_carregada_soma():
    # Painel cheio de 2 m na face de barlavento do vento em X, só num canto (y de 0 a −1).
    painel = vpb.ElementoAoVento(
        "Painel", vpb.TIPO_PAINEL, (0.0, 0.0, LINHA), (0.0, -1.0, LINHA), altura_m=2.0
    )
    ve = _ve(elementos=(painel,))
    assert ve.excentricidade_real["X"] > 0.03
    e = cp.EntradaContraventamento(
        comprimento_x_m=6, largura_y_m=4, cotas_m=(LINHA,), vaos_x=1, vaos_y=1,
        vento_do_esqueleto=ve,
    )  # fmt: skip
    usada = cp.excentricidade_usada(e, "X")
    assert usada == pytest.approx(e.excentricidade + ve.excentricidade_real["X"])
    r = cp.calcular(e)
    andar = r.andares_da_direcao("X")[0]
    assert andar.fracao_da_linha == pytest.approx(0.5 + usada)
    assert any("Direção X: a resultante" in a for a in r.avisos)


# ------------------------------------------------------------------ contraventamento
@pytest.fixture(scope="module")
def calculo() -> cp.ResultadoContraventamento:
    e = cp.EntradaContraventamento(
        comprimento_x_m=6, largura_y_m=4, cotas_m=(LINHA,), vaos_x=1, vaos_y=1,
        vento_do_esqueleto=_ve(),
    )  # fmt: skip
    return cp.calcular(e)


def test_uma_acao_de_vento_por_direcao_no_grupo_exclusivo(calculo):
    ventos = [a for a in calculo.acoes if a.categoria.startswith("Vento")]
    assert [a.nome for a in ventos][:2] == ["Vento W0 (+X)", "Vento W45 (+X +Y)"]
    assert len(ventos) == 8 and {a.grupo for a in ventos} == {cp.GRUPO_VENTO}
    w45 = next(a for a in ventos if "W45" in a.nome)
    assert w45.valor("V_X_1") > 0 and w45.valor("V_Y_1") > 0
    ve = calculo.entrada.vento_do_esqueleto
    for d in cp.DIRECOES:
        maior = ve.maior_cortante_kN(d, 1)
        andar = calculo.andares_da_direcao(d)[0]
        assert abs(andar.cortante_elu.valor) >= 1.4 * maior - 1e-6  # γ_q do vento
    assert calculo.vento_por_barras and calculo.vento_total_kN("X") == ve.maior_total_kN("X")


def test_cotas_diferentes_das_do_vento_sao_erro():
    e = cp.EntradaContraventamento(cotas_m=(3.0, 6.0), vento_do_esqueleto=_ve())
    assert any("outras cotas" in m for m in cp.validar_entrada(e))


def test_equipamento_vai_ao_vento_do_nivel_dele():
    tanque = va.Equipamento("Tanque", 1, va.FORMA_CILINDRO, 1.5, 1.5, 2.0, 30.0)
    com, sem = _ve(equipamentos=(tanque,)), _ve()
    assert com.caso(0).fx_kN[0] > sem.caso(0).fx_kN[0] + 1.0
    assert any(el.elemento == "Tanque" for el in com.resultado.direcao(0).elementos)


def test_registro_no_vento_por_barras(calculo):
    registro = reg.registro_contraventamento(calculo)
    json.dumps(registro)
    assert "viga a viga" in registro["entradas"]["vento"]
    assert "viga a viga" in registro["metodo"] and "viga a viga" in registro["conclusao"]
    tabelas = registro["resultados"]["tabelas_memorial"]
    assert len(tabelas) == 4 and tabelas[0]["cabecalhos"][0] == "Caso"
    assert any(linha[1] == "base" for linha in tabelas[0]["linhas"])
    assert tabelas[1]["linhas"] and tabelas[1]["cabecalhos"][1] == "Plano"


def test_esqueleto_so_de_chapas_e_erro_claro():
    corpos = [c for c in plataforma() if c.forma == ld.FORMA_CHAPA]
    with pytest.raises(cvb.VentoDoEsqueletoInvalido, match="só chapas"):
        cvb.entrada_pelo_esqueleto(
            ld.GeometriaDoModelo(corpos=tuple(corpos)), "Y", PARAMETROS, cotas_m=(LINHA,)
        )


@pytest.mark.parametrize("cotas", [(), (0.0,), (4.0, 3.0)])
def test_cotas_invalidas(cotas):
    with pytest.raises(cvb.VentoDoEsqueletoInvalido):
        cvb.vento_nos_niveis(_ve().resultado, cotas)


def test_memorial_word_e_pdf_no_vento_viga_a_viga(calculo):
    from io import BytesIO

    from docx import Document
    from pypdf import PdfReader

    from core.project_report import (
        gerar_relatorio_industrial_pdf,
        gerar_relatorio_industrial_word,
        montar_modelo_relatorio,
    )
    from core.project_store import novo_projeto_documento
    from core.technical_records import avaliar_contrato_registro, identificar_peca_registro

    registro = reg.registro_contraventamento(calculo)
    assert avaliar_contrato_registro(registro)["valido"]
    projeto = novo_projeto_documento("Plataforma", codigo="PL-01")
    projeto.update({"objetivo": "Contraventar.", "responsavel": "A", "verificador": "B"})
    projeto["registros_tecnicos"] = [identificar_peca_registro(registro, peca="Plataforma P1")]
    capitulo = next(s for s in montar_modelo_relatorio(projeto)["secoes"] if "blocos" in s)
    legendas = " ".join(b["legenda"] for b in capitulo["blocos"] if b.get("tipo") == "tabela")
    assert "viga a viga" in legendas and "Planos de barras" in legendas
    word = "\n".join(
        p.text for p in Document(BytesIO(gerar_relatorio_industrial_word(projeto))).paragraphs
    )
    pdf = "\n".join(
        p.extract_text() or ""
        for p in PdfReader(BytesIO(gerar_relatorio_industrial_pdf(projeto))).pages
    )
    for texto in (word, pdf):
        assert "Contraventamento de estruturas abertas" in texto
        for proibido in ("Não informado", "bloqueio", "Snapshot", "Apêndice"):
            assert proibido not in texto
