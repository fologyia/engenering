"""Marco 4 na Análise sobre o desenho: a marca só com nota, a medida pegada no desenho e o esboço
salvo como fundo, com as medidas da marca ligadas a ele e a busca pela letra do esboço."""

from __future__ import annotations

import io
from pathlib import Path
from unittest import mock

import pytest
from streamlit.testing.v1 import AppTest

from core import analise_desenho as ad
from core import elementos_vigas as ev
from core import esboco as eb
from core import esboco_secao as es
from core import secao_desenhada as sd
from core import section_catalog as catalogo
from tests.test_esboco import chapa_com_furos

APP = str(Path(__file__).resolve().parent.parent / "app.py")
SECAO = "Chapa de ligação"
F = 142.2e3  # N
T = 10.0  # mm
SU, N = 400.0, 1.67


@pytest.fixture
def catalogo_vazio(tmp_path):
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        ev._analisar_desenho.cache_clear()
        yield tmp_path / "perfis.json"
        ev._analisar_desenho.cache_clear()


def _chapa() -> dict:
    """Chapa 100 × 40 com dois furos de Ø d; a largura de cima é a medida com nome w."""
    dados = chapa_com_furos(h=40.0)
    dados["cotas"].append(
        {
            "id": "d20",
            "tipo": "distancia",
            "curvas": ["l3"],
            "pontos": ["p3", "p4"],
            "expressao": "100",
            "referencia": True,
            "nome": "w",
        }
    )
    return dados


def _salvar(nome: str = SECAO, dados: dict | None = None) -> None:
    dados = dados or _chapa()
    modelo = es.Modelo(eb.esboco_de_dicionario(dados))
    partes = modelo.regioes.partes(modelo.sistema.q0[None, :])
    catalogo.salvar_perfil(
        sd.perfil_da_secao(nome, sd.analisar(partes)),
        desenho=tuple(p.como_dicionario() for p in partes),
        esboco=dados,
    )


def _marca_da_chapa() -> ad.Marca:
    marca = ad.marca_nova("m1", 0.0, 0.0, "Chapa com furo: espessura mínima")
    marca.conferir = True
    marca.valores.update({"F_lig": F, "t_c": T, "n_f": 2.0, "S_ut": SU, "n": N})
    marca.ligacoes = {"d_f": "d", "w_c": "w"}
    return marca


# ---------------------------------------------------------------------------
# Só nota
# ---------------------------------------------------------------------------


def test_marca_so_com_nota_nao_faz_conta_e_vai_ao_word():
    from docx import Document

    nota = ad.marca_nova("m1", 5.0, 5.0, ad.NOTA)
    nota.nota = "Apoia na viga V-3 e passa a força ao pino de baixo, sem solda."
    resultado = ad.calcular(nota)
    assert resultado.situacao == ad.ANOTACAO and resultado.uso is None
    assert resultado.resumo.endswith("…") and len(resultado.resumo) <= 40
    pino = ad.marca_nova("m2", 50.0, 50.0, "Pino: força máxima")
    trocada = ad.trocar_analise(nota, "Pino: força máxima")
    assert trocada.nota == nota.nota  # o texto fica, para voltar
    marcas = [nota, pino]
    bruto = ad.word_da_analise(None, marcas, [ad.calcular(m) for m in marcas])
    texto = " ".join(p.text for p in Document(io.BytesIO(bruto)).paragraphs)
    assert "Nota: Apoia na viga V-3" in texto and "1 só com nota" in texto
    assert ad.marca_de_dicionario(nota.como_dicionario()).nota == nota.nota


# ---------------------------------------------------------------------------
# O esboço de fundo
# ---------------------------------------------------------------------------


def test_esboco_salvo_vira_fundo_com_as_letras_e_as_medidas(catalogo_vazio):
    _salvar()
    assert SECAO in ad.esbocos_salvos()
    fundo = ad.fundo_de_esboco(SECAO)
    assert fundo.tipo == "esboco" and fundo.secao == SECAO
    assert sorted(c["tipo"] for c in fundo.curvas) == ["circulo"] * 2 + ["linha"] * 4
    medidas = {m["nome"]: m for m in fundo.medidas}
    assert medidas["d"]["letra"] and medidas["d"]["valor"] == pytest.approx(10.0)
    assert not medidas["w"]["letra"] and medidas["w"]["valor"] == pytest.approx(100.0)
    maior = ad.fundo_de_esboco(SECAO, {"d": 16.0})
    raios = sorted(c["r"] for c in maior.curvas if c["tipo"] == "circulo")
    assert raios == pytest.approx([8.0, 8.0])
    with pytest.raises(ad.ErroDeDesenho, match="não existe"):
        ad.fundo_de_esboco(SECAO, {"d": 45.0})  # o furo passa da altura da chapa


def test_marca_le_as_medidas_ligadas_ao_esboco(catalogo_vazio):
    _salvar()
    fundo = ad.fundo_de_esboco(SECAO, {"d": 12.0}).como_dicionario()
    efetiva = ad.valores_da_marca(_marca_da_chapa(), fundo)
    assert efetiva.valores["d_f"] == pytest.approx(12.0)
    assert efetiva.valores["w_c"] == pytest.approx(100.0)
    resultado = ad.calcular(efetiva)
    rede = F / ((100.0 - 2 * 12.0) * T)
    ruptura = next(l for l in resultado.linhas if l.nome == "Ruptura da seção com furos")
    assert ruptura.solicitacao == pytest.approx(rede, rel=1e-9)
    # Sem esboço de fundo, a marca fica com os números dela.
    assert ad.valores_da_marca(_marca_da_chapa(), None).valores.get("d_f") == pytest.approx(22.0)


def test_achar_pelo_esboco_da_o_maior_furo_da_conta_de_mao(catalogo_vazio):
    _salvar()
    limite = ad.limite_pelo_esboco(_marca_da_chapa(), SECAO, {}, "d")
    # Ruptura: F/((w − 2·d)·t) = S_u/n  →  d = (w − F·n/(t·S_u))/2.
    exato = (100.0 - F * N / (T * SU)) / 2
    assert limite.sentido == "máximo"
    assert limite.valor == pytest.approx(exato, rel=1e-5)
    assert "até" in limite.texto
    # Com força pequena, passa em toda a faixa; com grande, em nenhum valor.
    leve = _marca_da_chapa()
    leve.valores["F_lig"] = 50e3
    assert ad.limite_pelo_esboco(leve, SECAO, {}, "d").sentido == "toda a faixa"
    pesada = _marca_da_chapa()
    pesada.valores["F_lig"] = 400e3
    assert ad.limite_pelo_esboco(pesada, SECAO, {}, "d").sentido == "nenhum"


# ---------------------------------------------------------------------------
# A tela: pegar a medida, ligar, achar e usar no esboço
# ---------------------------------------------------------------------------


def _estado() -> dict:
    from components import analise_desenho_ui as ui

    estado: dict = {}
    with mock.patch.object(ui.st, "session_state", estado):
        ui._iniciar()
    return estado


def test_medida_pegada_no_desenho_vai_ao_campo_e_cancelar_nao_muda_nada():
    from components import analise_desenho_ui as ui

    estado = _estado()
    marca = ad.marca_nova("m1", 0.0, 0.0, "Pino: força máxima")
    estado[ui.MARCAS] = [marca.como_dicionario()]
    with mock.patch.object(ui.st, "session_state", estado):
        ui._pedir_medida("m1", "d_p", "d_p da marca 1")
        assert estado[ui.PEDIDO]["chave"] == "d_p" and estado[ui.PEDIDO]["n"] == 1
        estado[ui.CHAVE] = mock.Mock(medida={"n": 1, "cancelar": True})
        ui._ao_medir()
        assert estado[ui.PEDIDO] is None
        assert ui._marcas()[0].valores["d_p"] == pytest.approx(20.0)
        ui._pedir_medida("m1", "d_p", "d_p da marca 1")
        estado[ui.CHAVE] = mock.Mock(medida={"n": 2, "id": "m1", "chave": "d_p", "valor": 24.5})
        ui._ao_medir()
        assert ui._marcas()[0].valores["d_p"] == pytest.approx(24.5)
        assert estado[ui.REVISOES]["m1"] == 1  # o campo é refeito com o número novo


def test_tela_liga_acha_e_usa_o_valor_no_esboco(catalogo_vazio):
    from components import analise_desenho_ui as ui

    _salvar()
    estado = _estado()
    estado[ui.MARCAS] = [_marca_da_chapa().como_dicionario()]
    with mock.patch.object(ui.st, "session_state", estado):
        estado[ui.ESBOCO] = SECAO
        ui._ao_escolher_esboco()
        assert estado[ui.FUNDO]["tipo"] == "esboco" and estado[ui.LETRAS] == {"d": 10.0}
        assert estado["ad_letra_d"] == 10.0 and estado[ui.ESCALA] == 1.0
        rev = ui._revisao("m1")
        estado[f"ad_m1_{rev}_d_f_lig"] = ui.DIGITADO
        ui._ao_ligar("m1", "d_f")
        assert "d_f" not in ui._marcas()[0].ligacoes
        estado[f"ad_m1_{rev}_d_f_lig"] = "d"
        ui._ao_ligar("m1", "d_f")
        estado[f"ad_m1_{rev}_letra_busca"] = "d"
        ui._achar_pelo_esboco("m1")
        limite = estado[ui.LIMITES]["m1"]
        assert limite["sentido"] == "máximo" and limite["valor"] == pytest.approx(20.3158, rel=1e-4)
        seguro = ad.redondo(limite["valor"], limite["sentido"])
        assert seguro <= limite["valor"]
        ui._usar_no_esboco("d", seguro)
        assert estado[ui.LETRAS]["d"] == seguro and estado["ad_letra_d"] == seguro
        circulos = [c for c in estado[ui.FUNDO]["curvas"] if c["tipo"] == "circulo"]
        assert circulos[0]["r"] == pytest.approx(seguro / 2)
        # Letra que desfaz o desenho volta ao valor de antes, com a mensagem.
        estado["ad_letra_d"] = 60.0
        ui._ao_mudar_letra("d")
        assert estado["ad_letra_d"] == seguro and "não existe" in estado[ui.ERRO]


def test_pagina_com_esboco_de_fundo_mostra_as_letras_e_a_ligacao(catalogo_vazio):
    _salvar()
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page("app_pages/analise_sobre_desenho.py")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    at.selectbox(key="ad_esboco").set_value(SECAO).run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.number_input(key="ad_letra_d").value == pytest.approx(10.0)
    at.session_state["ad_marcas"] = [_marca_da_chapa().como_dicionario()]
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("Medidas com nome" in c.value and "w = 100" in c.value for c in at.caption)
    ligadas = [n for n in at.number_input if n.key and n.key.startswith("ad_m1_") and n.disabled]
    assert sorted(n.label.split(" ")[0] for n in ligadas) == ["d_f", "w_c"]
    assert {n.value for n in ligadas} == {10.0, 100.0}
    assert any(b.label == "Achar pelo esboço" for b in at.button)
