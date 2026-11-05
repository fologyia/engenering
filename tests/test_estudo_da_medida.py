"""Estudo de uma medida: a faixa que passa, os valores prontos, as séries e a medida que manda.

Os casos de mentira têm a resposta conhecida de cabeça, e cobrem as formas de curva que um caso real
pode ter. Os casos de verdade entram para provar que todo valor sugerido passa no cálculo completo.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from streamlit.testing.v1 import AppTest

from components import assistente_cargas_ui as ui
from components import estudo_da_medida_ui as eu
from core import cotas_dos_desenhos as cd
from core import elementos_catalogo as cat
from core import estudo_da_medida as ed
from core import medidas_comerciais as mc
from core.base_de_pilar import ESPESSURAS_COMERCIAIS
from core.beam_charts import desenho_dispensado, so_a_conta
from core.contraventamento_dimensionamento import ESPESSURAS_MM
from core.elementos_base import (
    Campo,
    Caso,
    Coluna,
    Resultado,
    calcular_caso,
    faixa_recomendada,
    informativo,
    limite,
    recomendacao,
)
from core.ligacoes import PERNAS_COMERCIAIS

APP = str(Path(__file__).resolve().parent.parent / "app.py")
CASOS = sorted(cat.CASOS)


def _caso(funcao, padrao: float | int = 20.0, **campo) -> Caso:
    """Um caso de um número só, ``x``. ``funcao`` recebe o número e devolve as verificações."""
    return Caso(
        "de_mentira",
        "De mentira",
        "Testes",
        "",
        "",
        (Campo("x", "Medida x", "ajuda", padrao, unidade="mm", **campo),),
        lambda valores: Resultado("ok", verificacoes=tuple(funcao(valores["x"]))),
    )


def _criterio(aproveitamento: float, nome: str = "Critério"):
    return limite(nome, aproveitamento, 1.0, "", "", "")


def _estudo(funcao, padrao: float | int = 20.0, **campo) -> ed.Estudo:
    caso = _caso(funcao, padrao, **campo)
    valores = caso.padroes()
    return ed.estudar(caso, valores, cd.medidas_do_caso(caso, valores)[0])


def _valor(estudo: ed.Estudo, rotulo: str) -> float:
    return next(o.valor for o in estudo.opcoes if o.rotulo == rotulo)


# ---------------------------------------------------------------------------
# A faixa que passa
# ---------------------------------------------------------------------------


def test_limite_por_baixo():
    estudo = _estudo(lambda x: [_criterio(10.0 / x)])
    assert _valor(estudo, ed.MENOR) == pytest.approx(10.0)
    assert not any(o.rotulo == ed.MAIOR for o in estudo.opcoes)
    assert estudo.resumo() == "Passa a partir de 10 mm."


def test_limite_por_cima():
    estudo = _estudo(lambda x: [_criterio(x / 50.0)])
    assert _valor(estudo, ed.MAIOR) == pytest.approx(50.0)
    assert not any(o.rotulo == ed.MENOR for o in estudo.opcoes)
    assert estudo.resumo() == "Passa até 50 mm."


def test_janela_com_os_dois_lados():
    estudo = _estudo(lambda x: [_criterio(10.0 / x, "Fino"), _criterio(x / 40.0, "Grosso")])
    assert _valor(estudo, ed.MENOR) == pytest.approx(10.0)
    assert _valor(estudo, ed.MAIOR) == pytest.approx(40.0)
    assert estudo.resumo() == "Passa de 10 a 40 mm."
    assert estudo.quem_trava() == "Fino · Grosso"


def test_nao_passa_em_nada_diz_quem_trava():
    estudo = _estudo(lambda x: [_criterio(5.0, "Sempre ruim")])
    assert estudo.trechos == ()
    assert estudo.opcoes == ()
    assert estudo.resumo().startswith("Não passa em nenhum valor de 2,5 a 160 mm.")
    assert "Sempre ruim" in estudo.resumo()


def test_passa_em_tudo_nao_inventa_limite():
    estudo = _estudo(lambda x: [_criterio(0.1)])
    assert estudo.opcoes == ()
    assert estudo.resumo() == "Passa em toda a faixa estudada, de 2,5 a 160 mm."


def test_curva_com_dois_trechos_fica_com_o_do_valor_atual():
    """Nada garante que a curva suba sempre: a grade precisa achar cada troca."""

    def funcao(x):
        return [_criterio(0.5 if 5.0 <= x <= 30.0 or 60.0 <= x <= 90.0 else 2.0)]

    estudo = _estudo(funcao)
    assert len(estudo.trechos) == 2
    assert _valor(estudo, ed.MENOR) == pytest.approx(5.0, rel=1e-3)
    assert _valor(estudo, ed.MAIOR) == pytest.approx(30.0, rel=1e-3)
    assert "mais de um trecho" in estudo.resumo()


def test_valor_que_reprova_aponta_o_trecho_mais_perto():
    estudo = _estudo(lambda x: [_criterio(40.0 / x)])
    assert not estudo.atual.passa
    assert not estudo.util.contem(estudo.medida.valor)
    assert _valor(estudo, ed.MENOR) == pytest.approx(40.0)


def test_dado_recusado_nao_passa_e_o_motivo_aparece():
    def funcao(x):
        if x > 30.0:
            raise ValueError("O furo não cabe na chapa.")
        return [_criterio(0.5)]

    estudo = _estudo(funcao)
    assert _valor(estudo, ed.MAIOR) == pytest.approx(30.0, rel=1e-3)
    assert estudo.quem_trava() == "O furo não cabe na chapa."


def test_faixa_respeita_os_limites_do_campo():
    estudo = _estudo(lambda x: [_criterio(0.5)], minimo=15.0, maximo=25.0)
    assert (estudo.de, estudo.ate) == (15.0, 25.0)
    assert all(15.0 <= p.valor <= 25.0 for p in estudo.pontos)


def test_faixa_escolhida_pelo_usuario_vale():
    caso = _caso(lambda x: [_criterio(10.0 / x)])
    valores = caso.padroes()
    medida = cd.medidas_do_caso(caso, valores)[0]
    estudo = ed.estudar(caso, valores, medida, 12.0, 500.0)
    assert (estudo.de, estudo.ate) == (12.0, 500.0)
    assert estudo.opcoes == ()
    assert estudo.pontos[-1].valor == pytest.approx(500.0)


def test_medida_inteira_so_roda_inteiros():
    estudo = _estudo(lambda n: [_criterio(7.5 / n)], padrao=20)
    assert all(isinstance(p.valor, int) for p in estudo.pontos)
    assert _valor(estudo, ed.MENOR) == 8


@pytest.mark.parametrize("padrao", [0.0, -30.0])
def test_valor_zero_ou_negativo_tem_faixa(padrao):
    estudo = _estudo(lambda x: [_criterio(0.5)], padrao=padrao)
    assert estudo.de < estudo.ate
    assert len(estudo.pontos) > 10


def test_status_do_caso_sem_criterio():
    estudo = _estudo(lambda x: [informativo("Só para ver", x, "mm", "", "")])
    assert not estudo.tem_criterio
    assert estudo.opcoes == ()
    assert "não tem critério" in estudo.resumo()


# ---------------------------------------------------------------------------
# Recomendação não é critério
# ---------------------------------------------------------------------------


def test_marca_de_recomendacao():
    assert limite("a", 1.0, 2.0, "", "", "").obrigatoria
    assert not recomendacao("a", 1.0, 2.0, "", "", "").obrigatoria
    assert not faixa_recomendada("a", 1.0, 0.0, 2.0, "", "", "").obrigatoria


def test_recomendacao_fica_fora_dos_100_e_vira_opcao():
    def funcao(x):
        return [_criterio(10.0 / x), recomendacao("Boa prática", 15.0, x, "", "", "")]

    estudo = _estudo(funcao)
    assert _valor(estudo, ed.MENOR) == pytest.approx(10.0)
    assert _valor(estudo, ed.SEM_RESSALVA) == pytest.approx(15.0)
    assert all("Boa prática" not in p.criterios for p in estudo.pontos)


def test_acima_da_faixa_recomendada_aponta_para_baixo():
    """O valor limpo mais perto de quem passou da faixa está abaixo dele, e não no começo."""

    def funcao(x):
        return [_criterio(0.5), faixa_recomendada("L/d", x, 5.0, 10.0, "", "", "")]

    estudo = _estudo(funcao)
    assert not estudo.atual.sem_ressalva
    assert _valor(estudo, ed.SEM_RESSALVA) == pytest.approx(10.0)


def test_caso_sem_criterio_nao_chama_valor_recusado_de_limite():
    def funcao(x):
        if x > 30.0:
            raise ValueError("Não cabe.")
        return [informativo("Só para ver", x, "mm", "", "")]

    assert _estudo(funcao).opcoes == ()


def test_campo_numerico_vazio_nao_derruba_o_estudo():
    caso = _caso(lambda x: [_criterio(1.0 / x)])
    assert ed.avaliar(caso, {"x": None}).erro


def test_alerta_em_caso_so_de_recomendacao_nao_conta_como_passou():
    estudo = _estudo(lambda x: [recomendacao("Boa prática", 40.0, x, "", "", "")])
    assert estudo.atual.passa
    assert not estudo.atual_passa


def test_caso_so_de_recomendacao_separa_por_ela():
    estudo = _estudo(lambda x: [recomendacao("Boa prática", 15.0, x, "", "", "")])
    assert estudo.so_recomendacoes
    assert _valor(estudo, ed.MENOR) == pytest.approx(15.0)


# ---------------------------------------------------------------------------
# Número limpo, sempre do lado que passa
# ---------------------------------------------------------------------------


def test_limite_redondo_nao_sobe_sem_precisar():
    assert _valor(_estudo(lambda x: [_criterio(4.8 / x)], padrao=10.0), ed.MENOR) == 4.8


def test_arredonda_para_cima_quando_o_mais_proximo_reprova():
    estudo = _estudo(lambda x: [_criterio(7.3333 / x)], padrao=10.0)
    assert _valor(estudo, ed.MENOR) == 7.34


def test_arredonda_para_baixo_no_limite_de_cima():
    estudo = _estudo(lambda x: [_criterio(x / 166.67)], padrao=80.0)
    assert _valor(estudo, ed.MAIOR) == 166.0


def test_conta_de_mao_da_chapa_com_furo():
    caso = cat.CASOS["chapa_furo"]
    valores = caso.padroes()
    por_nome = {m.nome: m for m in cd.medidas_do_caso(caso, valores)}
    # F_lim = fy/FS · b·t = 250/1,5 · 100 · 10 = 166,67 kN
    assert _valor(
        ed.estudar(caso, valores, por_nome["Força de tração"]), ed.MAIOR
    ) == pytest.approx(166.0)
    # t_min = F·FS/(fy·b) = 80 000 · 1,5/(250 · 100) = 4,8 mm
    assert _valor(ed.estudar(caso, valores, por_nome["Espessura"]), ed.MENOR) == pytest.approx(4.8)
    # Duas contas dão o mesmo b_min: a bruta 48 e a líquida 18 + 30 = 48.
    assert _valor(
        ed.estudar(caso, valores, por_nome["Largura da chapa"]), ed.MENOR
    ) == pytest.approx(48.0)


# ---------------------------------------------------------------------------
# Séries comerciais
# ---------------------------------------------------------------------------

SERIES = sorted(
    {serie for campos in mc.SERIE_DO_CAMPO.values() for serie in campos.values()},
    key=lambda s: s.nome,
)


@pytest.mark.parametrize("serie", SERIES, ids=lambda s: s.nome)
def test_serie_em_ordem_e_com_fonte(serie):
    assert list(serie.valores) == sorted(set(serie.valores))
    assert serie.valores[0] > 0
    assert serie.fonte


def test_toda_serie_ligada_aponta_para_campo_de_verdade():
    for caso_id, campos in mc.SERIE_DO_CAMPO.items():
        caso = cat.CASOS[caso_id]
        chaves = {c.chave for c in caso.campos}
        colunas = {coluna.chave for campo in caso.campos for coluna in campo.colunas}
        for chave in campos:
            assert chave in chaves | colunas, (caso_id, chave)


def test_toda_espessura_em_mm_do_catalogo_tem_serie():
    """Campo novo de espessura sem série passaria sem ninguém notar."""
    # A parede sai de tubo, e o aperto é a soma de várias peças: nenhum dos dois é chapa de catálogo.
    de_fora = {"cilindro_hidraulico": {"parede_mm"}, "parafuso_axial": {"aperto_mm"}}
    for caso_id, caso in cat.CASOS.items():
        for campo in caso.campos:
            if campo.unidade != "mm" or "spessura" not in campo.rotulo:
                continue
            if campo.chave in de_fora.get(caso_id, ()):
                continue
            assert mc.serie_do_campo(caso_id, campo.chave), (caso_id, campo.chave)


def test_series_batem_com_as_tabelas_que_ja_existem_no_programa():
    assert set(ESPESSURAS_COMERCIAIS) <= set(mc.CHAPAS.valores)
    assert set(ESPESSURAS_MM) <= set(mc.CHAPAS.valores)
    assert mc.PERNAS_DE_SOLDA.valores == PERNAS_COMERCIAIS


def test_comercial_e_o_primeiro_da_serie_que_passa():
    caso = _caso(lambda x: [_criterio(7.0 / x)])
    valores = caso.padroes()
    medida = replace(cd.medidas_do_caso(caso, valores)[0], serie=mc.CHAPAS)
    estudo = ed.estudar(caso, valores, medida)
    assert _valor(estudo, ed.COMERCIAL) == 8.0


def test_comercial_vem_de_cima_quando_o_limite_e_maximo():
    caso = _caso(lambda x: [_criterio(x / 30.0)])
    valores = caso.padroes()
    medida = replace(cd.medidas_do_caso(caso, valores)[0], serie=mc.CHAPAS)
    assert _valor(ed.estudar(caso, valores, medida), ed.COMERCIAL) == 25.0


def test_comercial_pula_quem_nao_passa_de_verdade():
    """A curva tem um buraco bem no valor comercial: o estudo confere um a um."""

    def funcao(x):
        return [_criterio(2.0 if x == 8.0 else 7.0 / x)]

    caso = _caso(funcao)
    valores = caso.padroes()
    medida = replace(cd.medidas_do_caso(caso, valores)[0], serie=mc.CHAPAS)
    assert _valor(ed.estudar(caso, valores, medida), ed.COMERCIAL) == 9.5


def test_dicionario_da_cota_leva_a_serie():
    caso = cat.CASOS["placa_retangular"]
    cota = next(c for c in cd.cotas_do_caso(caso, caso.padroes()) if c.letra == "t")
    dados = cota.como_dicionario()
    assert dados["serie"] == "Chapas de aço"
    assert 12.5 in dados["comerciais"]
    outra = next(c for c in cd.cotas_do_caso(caso, caso.padroes()) if c.letra == "a")
    assert outra.como_dicionario()["comerciais"] == []


# ---------------------------------------------------------------------------
# Todos os casos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("caso_id", CASOS)
def test_todo_valor_sugerido_passa_no_calculo_completo(caso_id):
    """O estudo roda sem desenho. A prova é rodar o caso inteiro com o valor que ele sugeriu."""
    caso = cat.CASOS[caso_id]
    valores = caso.padroes()
    for medida in cd.medidas_do_caso(caso, valores):
        estudo = ed.estudar(caso, valores, medida, pontos=13)
        for opcao in estudo.opcoes:
            resultado = calcular_caso(caso, cd.com_valor(valores, medida.alvo, opcao.valor))
            if estudo.so_recomendacoes:
                assert resultado.status == "OK", (medida.nome, opcao)
            else:
                assert resultado.status != "NÃO OK", (medida.nome, opcao)
            assert opcao.status == resultado.status


@pytest.mark.parametrize("caso_id", CASOS)
def test_so_a_conta_nao_muda_nenhum_numero(caso_id):
    caso = cat.CASOS[caso_id]
    valores = caso.padroes()
    completo = calcular_caso(caso, valores)
    with so_a_conta():
        rapido = calcular_caso(caso, valores)
    assert rapido.metricas == completo.metricas
    assert rapido.status == completo.status
    assert [v.aproveitamento for v in rapido.verificacoes] == [
        v.aproveitamento for v in completo.verificacoes
    ]
    assert all(not figura.png for figura in rapido.figuras)
    assert all(figura.png for figura in completo.figuras)


def test_so_a_conta_termina_com_o_bloco_mesmo_com_erro():
    with pytest.raises(RuntimeError), so_a_conta():
        assert desenho_dispensado()
        raise RuntimeError
    assert not desenho_dispensado()


@pytest.mark.parametrize("caso_id", CASOS)
def test_diagnostico_e_pesos_funcionam_em_todo_caso(caso_id):
    caso = cat.CASOS[caso_id]
    valores = caso.padroes()
    cotas = cd.cotas_do_caso(caso, valores)
    diagnostico = ed.diagnosticar(caso, valores, cotas)
    if diagnostico.manda is not None:
        assert diagnostico.manda.medida in cotas
        assert ed.e_geometria(diagnostico.manda.medida)
    ed.pesos(caso, valores)


# ---------------------------------------------------------------------------
# A medida que manda
# ---------------------------------------------------------------------------


def _pesos_por_letra(caso_id: str) -> dict[str, ed.Peso]:
    caso = cat.CASOS[caso_id]
    return {p.medida.letra: p for p in ed.pesos(caso, caso.padroes())}


def test_peso_bate_com_a_potencia_da_formula():
    """Na placa, a tensão cai com t²: o peso da espessura é perto de −2."""
    pesos = _pesos_por_letra("placa_retangular")
    assert pesos["t"].peso == pytest.approx(-2.0, abs=0.05)
    assert pesos["t"].sentido == "Subir"
    assert pesos["t"].melhora == pytest.approx(0.97 / 1.1**2, abs=0.02)


def test_peso_da_carga_e_um_e_o_sentido_e_descer():
    pesos = _pesos_por_letra("chapa_furo")
    assert pesos["F"].peso == pytest.approx(1.0, abs=0.01)
    assert pesos["F"].sentido == "Descer"


def test_medida_que_nao_governa_nao_influi_agora():
    peso = _pesos_por_letra("chapa_furo")["d"]
    assert not peso.influi
    assert "Não muda" in peso.texto_do_efeito()


def test_destaque_sai_da_geometria_e_nao_da_carga():
    caso = cat.CASOS["chapa_furo"]
    valores = caso.padroes()
    diagnostico = ed.diagnosticar(caso, valores, cd.cotas_do_caso(caso, valores))
    assert diagnostico.manda.medida.letra == "b"
    assert diagnostico.texto() == (
        "Quem governa: Escoamento da seção bruta, 48 %. A medida que mais pesa, em laranja no "
        "desenho, é b: subir 10 % leva a 44 %."
    )


def test_medida_inteira_anda_de_inteiro_em_inteiro():
    peso = _pesos_por_letra("acoplamento")["n parafusos"]
    assert peso.medida.inteiro
    assert float(peso.andou).is_integer()
    assert "%" not in peso.texto_do_efeito().split(" leva")[0]


def test_diagnostico_sem_criterio_nao_escreve_nada():
    caso = cat.CASOS["secao_montada"]
    valores = caso.padroes()
    assert ed.diagnosticar(caso, valores, []).texto() == ""


def test_dado_invalido_nao_derruba_o_diagnostico():
    caso = _caso(lambda x: 1 / 0)
    diagnostico = ed.diagnosticar(caso, caso.padroes(), [])
    assert diagnostico.avaliacao.erro
    assert diagnostico.manda is None


# ---------------------------------------------------------------------------
# Medidas além das cotas
# ---------------------------------------------------------------------------


def test_medidas_comecam_pelas_cotas_com_os_mesmos_indices():
    caso = cat.CASOS["chapa_furo"]
    valores = caso.padroes()
    cotas = cd.cotas_do_caso(caso, valores)
    medidas = cd.medidas_do_caso(caso, valores)
    assert medidas[: len(cotas)] == cotas
    assert [m.indice for m in medidas] == list(range(len(medidas)))
    assert "t_mm" in {m.alvo for m in medidas[len(cotas) :]}


def test_medidas_nao_trazem_texto_chave_nem_campo_escondido():
    caso = cat.CASOS["chaveta"]
    valores = caso.padroes()
    chaves = {m.alvo for m in cd.medidas_do_caso(caso, valores) if isinstance(m.alvo, str)}
    assert "dimensoes" not in chaves
    escondidos = {c.chave for c in caso.campos if not c.visivel(valores)}
    assert not chaves & escondidos


def test_com_valor_nao_mexe_nos_dados_originais():
    alvo = cd.Celula("cargas", 0, "valor")
    valores = {"cargas": ({"valor": 1.0},), "x": 2.0}
    novos = cd.com_valor(valores, alvo, 5.0)
    assert novos["cargas"][0]["valor"] == 5.0
    assert valores["cargas"][0]["valor"] == 1.0
    assert cd.com_valor(valores, "x", 3.0)["x"] == 3.0
    assert valores["x"] == 2.0


def test_celula_de_tabela_e_estudada():
    caso = Caso(
        "de_tabela",
        "De tabela",
        "Testes",
        "",
        "",
        (
            Campo(
                "trechos",
                "Trechos",
                "ajuda",
                ({"l": 20.0},),
                colunas=(Coluna("l", "Comprimento", "ajuda", 20.0, unidade="mm"),),
            ),
        ),
        lambda v: Resultado("ok", verificacoes=(_criterio(10.0 / v["trechos"][0]["l"]),)),
    )
    estudo = ed.estudar(caso, caso.padroes(), _medida_de_celula())
    assert _valor(estudo, ed.MENOR) == pytest.approx(10.0)


def _medida_de_celula() -> cd.CotaViva:
    return cd.CotaViva(
        0, "L", "L", cd.Celula("trechos", 0, "l"), 20.0, "mm", "Comprimento", "", None, None, False
    )


def test_identidade_nao_depende_do_indice():
    assert _medida_de_celula().identidade == "trechos|0|l"
    caso = cat.CASOS["chapa_furo"]
    assert cd.cotas_do_caso(caso, caso.padroes())[0].identidade == "f_kN"


# ---------------------------------------------------------------------------
# Gráfico
# ---------------------------------------------------------------------------


def test_grafico_so_traz_quem_governou_e_tira_o_infinito():
    def funcao(x):
        return [
            _criterio(float("inf") if x < 5.0 else 10.0 / x, "Governa"),
            _criterio(0.001, "Nunca manda"),
        ]

    estudo = _estudo(funcao)
    linhas = eu.curvas_do_grafico(estudo, eu.APROVEITAMENTO, estudo.de, estudo.ate)
    assert {nome for _, _, nome in linhas} == {"Governa"}
    assert all(y < 1e9 for _, y, _ in linhas)


def test_grafico_de_metrica_de_caso_sem_criterio():
    caso = cat.CASOS["acoes_icamento"]
    valores = caso.padroes()
    medida = cd.cotas_do_caso(caso, valores)[0]
    estudo = ed.estudar(caso, valores, medida, pontos=9)
    nome = next(iter(estudo.pontos[0].metricas))
    linhas = eu.curvas_do_grafico(estudo, nome, estudo.de, estudo.ate)
    assert len(linhas) >= 9
    assert {curva for _, _, curva in linhas} == {nome}


def test_janela_do_grafico_abre_em_volta_do_que_interessa():
    estudo = _estudo(lambda x: [_criterio(10.0 / x)])
    inicio, fim = eu._janela(estudo, False)
    assert estudo.de <= inicio < 10.0 < 20.0 < fim <= estudo.ate
    assert eu._janela(estudo, True) == (estudo.de, estudo.ate)


# ---------------------------------------------------------------------------
# Na tela
# ---------------------------------------------------------------------------


def _abrir(caso_id: str, *, estudo: bool = False) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.session_state["assistente_geometria"] = caso_id
    if estudo:
        at.session_state[eu.CHAVE_ABERTO] = True
    at.switch_page("app_pages/assistente_cargas.py")
    return at.run()


def _editar(caso_id: str, estado: dict, **evento):
    caso = cat.CASOS[caso_id]
    chave = f"assistente_croqui::{caso_id}"
    estado[chave] = SimpleNamespace(edicao=evento)
    with (
        mock.patch.object(ui.st, "session_state", estado),
        mock.patch.object(eu.st, "session_state", estado),
    ):
        ui._ao_editar_cota(caso, chave)
    return chave


def _indice(caso_id: str, letra: str) -> int:
    caso = cat.CASOS[caso_id]
    return next(c.indice for c in cd.cotas_do_caso(caso, caso.padroes()) if c.letra == letra)


def test_painel_fechado_nao_roda_o_estudo():
    with mock.patch.object(ed, "estudar", side_effect=AssertionError("rodou fechado")):
        at = _abrir("chapa_furo")
    assert not at.exception
    assert not [b for b in at.button if str(b.key).startswith("assistente_estudo_usar")]


def test_painel_aberto_comeca_na_medida_que_manda():
    at = _abrir("chapa_furo", estudo=True)
    assert not at.exception
    assert at.selectbox(key="assistente_estudo_medida::chapa_furo").value == "b_mm"
    assert any("Passa a partir de 48 mm" in s.value for s in at.success)


def test_botao_usar_grava_e_entra_no_desfazer():
    at = _abrir("chapa_furo", estudo=True)
    chave = ui.chave_do_campo("chapa_furo", "b_mm")
    at.button(key="assistente_estudo_usar::chapa_furo::0").click().run()
    assert not at.exception
    assert at.session_state[chave] == 48.0
    assert any("(menor que passa)" in i.value for i in at.info)
    at.button(key="assistente_desfazer::chapa_furo").click().run()
    assert at.session_state[chave] == 100.0


def test_estudo_de_campo_fora_do_desenho_tambem_grava():
    at = _abrir("chapa_furo", estudo=True)
    at.selectbox(key="assistente_estudo_medida::chapa_furo").set_value("t_mm").run()
    assert not at.exception
    at.button(key="assistente_estudo_usar::chapa_furo::1").click().run()
    assert not at.exception
    assert at.session_state[ui.chave_do_campo("chapa_furo", "t_mm")] == 5.0


def test_faixa_ao_contrario_avisa_e_nao_quebra():
    at = _abrir("chapa_furo", estudo=True)
    at.number_input(key="assistente_estudo_de::chapa_furo::b_mm").set_value(500.0)
    at.number_input(key="assistente_estudo_ate::chapa_furo::b_mm").set_value(100.0).run()
    assert not at.exception
    assert any("menor que o Até" in w.value for w in at.warning)


@pytest.mark.parametrize(
    "caso_id", ["acoes_icamento", "barra_axial", "correia", "portico_simples", "trelica_plana"]
)
def test_painel_abre_em_casos_de_formas_diferentes(caso_id):
    at = _abrir(caso_id, estudo=True)
    assert not at.exception


def test_estudo_continua_de_pe_com_dado_invalido():
    """Dado errado é justamente quando o estudo ajuda a achar um valor que serve."""
    at = _abrir("chapa_furo", estudo=True)
    at.number_input(key=ui.chave_do_campo("chapa_furo", "b_mm")).set_value(10.0).run()
    assert not at.exception
    assert at.error
    assert at.selectbox(key="assistente_estudo_medida::chapa_furo").value == "b_mm"


def test_pedir_limite_guarda_a_resposta_para_a_caixinha():
    estado: dict = {}
    chave = _editar("chapa_furo", estado, acao="limite", indice=_indice("chapa_furo", "b"), n=1)
    assinatura, resposta = estado[f"{chave}::limite"]
    assert resposta["texto"] == "Passa a partir de 48 mm."
    assert resposta["indice"] == _indice("chapa_furo", "b")
    assert resposta["opcoes"][0]["texto"] == "48 mm · 100 %"
    assert estado["assistente_estudo_medida::chapa_furo"] == "b_mm"
    assert ui.chave_do_campo("chapa_furo", "b_mm") not in estado
    assert assinatura


def test_ver_grafico_abre_o_painel_na_medida():
    estado: dict = {}
    _editar("chapa_furo", estado, acao="grafico", indice=_indice("chapa_furo", "d"), n=1)
    assert estado[eu.CHAVE_ABERTO] is True
    assert estado["assistente_estudo_medida::chapa_furo"] == "d_mm"


def test_edicao_comum_continua_gravando():
    estado: dict = {}
    _editar("chapa_furo", estado, indice=_indice("chapa_furo", "b"), valor=150.0, n=1)
    assert estado[ui.chave_do_campo("chapa_furo", "b_mm")] == 150.0


def test_assinatura_muda_com_os_dados():
    assert eu.assinatura({"a": 1.0}) != eu.assinatura({"a": 2.0})
    assert eu.assinatura({"a": 1, "b": 2}) == eu.assinatura({"b": 2, "a": 1})
