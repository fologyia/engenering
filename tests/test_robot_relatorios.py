from __future__ import annotations

from dataclasses import replace
from io import BytesIO
from zipfile import ZipFile

import pytest
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from core import aberturas_alma as ab
from core import load_combinations as comb
from core import memorial_anglo as ma
from core import plano_de_cargas as pc
from core import project_report as pr
from core import reacoes_nas_bases as rb
from core import robot
from core import robot_integracao as ri
from core.project_store import obter_projeto_ativo, registrar_calculo_tecnico, salvar_projeto
from tests.apoio_paginas import abrir
from tests.test_robot import ARQUIVOS_ROBOT, EXPORTACAO_ROBOT, _ajustar, _modelo


def _selecao(esquema, tabela):
    return robot.Selecao(tabela, 1, robot.colunas_sugeridas(esquema, tabela.linhas[0]))


@pytest.mark.parametrize("extensao", ["htm", "rtf"])
def test_notas_reais_do_robot_equivalem_ao_txt(extensao):
    doc = EXPORTACAO_ROBOT / f"relatorio.{extensao}"
    extraidas = robot.ler_tabelas(doc.name, doc.read_bytes())
    tabelas = {e: _selecao(e, t) for e, t in zip(robot.ESQUEMAS, extraidas, strict=True)}
    txt = {
        e: _selecao(e, robot.ler_tabelas(a.name, a.read_bytes())[0])
        for e, n in zip(robot.ESQUEMAS, ARQUIVOS_ROBOT, strict=True)
        for a in (EXPORTACAO_ROBOT / f"{n}.txt",)
    }
    modelo = robot.importar(tabelas, robot.Unidades(), "Pórtico", "A")
    base = robot.importar(txt, robot.Unidades(), "Pórtico", "A")
    for chave in ("nos", "barras", "casos"):
        assert modelo[chave] == base[chave]
    assert rb.linhas(rb.montar_do_robot(modelo)) == rb.linhas(rb.montar_do_robot(base))
    dados = robot.dados_do_modelo(modelo)
    comparavel = robot.dados_do_modelo(base)
    assert {k: v.membros for k, v in dados.casos.items()} == {
        k: v.membros for k, v in comparavel.casos.items()
    }


def test_rohtml_reune_colunas_e_rejeita_resultados_de_testes_por_conteudo():
    original = EXPORTACAO_ROBOT / "esforcos.htm"
    (tabela,) = robot.ler_tabelas("report.html", original.read_bytes())
    assert len(tabela.linhas[0]) == 7
    assert tabela.linhas[-1][0].endswith("4 (C)")
    for nome, conteudo in [
        ("qualquer.xml", b'<robot generator="Robot 7"><suite name="Teste"/></robot>'),
        ("qualquer.html", b'<meta name="generator" content="Robot Framework 7">'),
    ]:
        with pytest.raises(robot.ImportacaoRobotInvalida, match="Robot Framework"):
            robot.ler_tabelas(nome, conteudo)


def test_relatorio_parcial_e_cabecalho_repetido():
    html = """<table><tr><th>Nó</th><th>X (m)</th><th>Y (m)</th><th>Z (m)</th></tr>
        <tr><td>1</td><td>0</td><td>0</td><td>0</td></tr>
        <tr><th>Nó</th><th>X (m)</th><th>Y (m)</th><th>Z (m)</th></tr>
        <tr><td>2</td><td>0</td><td>0</td><td>3</td></table>"""
    (tabela,) = robot.ler_tabelas("parcial.html", html.encode())
    s = _selecao("Nós", tabela)
    assert len(list(s.registros())) == 2
    with pytest.raises(robot.ImportacaoRobotInvalida, match="tabela de barras"):
        robot.importar({"Nós": s}, robot.Unidades(), "Pórtico", "A")


def test_previa_reaproveita_mapeamento_e_pede_escolha_entre_fontes_divergentes():
    tela = AppTest.from_string("""
from components.robot_ui import _selecionar_tabelas
from core.robot import Tabela
colunas = ('ID antigo', 'X (m)', 'Y (m)', 'Z (m)')
tab1 = Tabela('Revisão A.html', 'a', (colunas, ('1', '0', '0', '0')))
tab2 = Tabela('Revisão B.rtf', 'b', (colunas, ('1', '0', '1', '0')))
perfil = {'Nós': {'cabecalho': [s.casefold() for s in colunas],
                 'colunas': {'Nó': 0, 'X': 1, 'Y': 2, 'Z': 3}}}
_selecionar_tabelas([tab1, tab2], 'fontes', perfil)
""").run()
    assert tela.selectbox(key="fontes_Nós").value is None
    assert any("conteúdo ou colunas diferentes" in a.value for a in tela.warning)
    tela.selectbox(key="fontes_Nós").set_value(1).run()
    assert tela.selectbox(key="fontes_Nós_1_1_Nó").value == 0


def _plano():
    return pc.PlanoDeCargas((pc.nova_acao("PP"), pc.nova_acao("SC")))


def test_comparacao_por_fatores_e_pontos_exatos():
    modelo = _ajustar(_modelo(deslocar_posicao=True), origem=robot.ROBOT)
    casos = modelo["casos"]
    casos["3"]["componentes"] = ri.ler_fatores("1:1,25; 2:1,5", casos)
    casos["3"]["analise"] = robot.LINEAR
    dados = robot.dados_do_modelo(modelo)
    c = ri.comparar(modelo, dados, _plano(), [comb.ELU_NORMAL])
    assert c.pares == (("3", "C01-ELU"),)
    assert c.pontos == 2
    assert c.sem_ponto == 2
    assert {p[-1] for p in c.pontos_sem_par} == {"x/L = 0.5", "x/L = 0.6"}
    assert c.sem_par == ("Toolkit C02-ELU",)
    assert not c.divergencias
    ponto, *resto = dados.casos["3"].membros["10"]
    casos_em = {
        **dados.casos,
        "3": replace(
            dados.casos["3"],
            membros={
                "10": (replace(ponto, n=ponto.n - 5), *resto),
            },
        ),
    }
    diferente = ri.comparar(modelo, replace(dados, casos=casos_em), _plano(), [comb.ELU_NORMAL])
    assert len(diferente.divergencias) == 1
    assert diferente.maior[7] == -5


def test_posicao_ausente_e_segunda_ordem_e_rotacao_da_placa():
    modelo = _modelo()
    dados = robot.dados_do_modelo(modelo)
    parametros = {
        dados.membros["10"].tipo: replace(
            dados.parametros_do_tipo(dados.membros["10"].tipo),
            b2=2.0,
        )
    }
    dados = replace(dados, parametros=parametros)
    (elu,) = ri.selecionar(modelo, dados, _plano(), "10", "0.5", "", comb.ELU_NORMAL)
    (els,) = ri.selecionar(modelo, dados, _plano(), "10", "0.5", "", comb.ELS_RARA)
    assert elu.vetor[0] == -42.5 and elu.b2 == 1.0
    assert els.vetor[0] == -60.0 and els.b2 == 2.0
    with pytest.raises(robot.ImportacaoRobotInvalida, match="0.25"):
        ri.selecionar(modelo, dados, _plano(), "10", "0.25", "", comb.ELU_NORMAL)
    placa = ri.placa_com_reacao((1, 2, 10, 3, 4, 5), 90)
    assert placa["n_sd_kN"] == 10
    assert placa["vx_kN"] == pytest.approx(-2)
    assert placa["vy_kN"] == pytest.approx(1)
    assert placa["m_sd_kNm"] == pytest.approx(3)
    assert placa["mz_kNm"] == -5


def test_corte_no_apoio_exclusivo_concorda_com_reacao_e_barra_invertida():
    modelo = _modelo()
    (forca,) = ri.selecionar(
        robot.modelo_do_projeto({robot.CAMPO: modelo}),
        robot.dados_do_modelo(modelo),
        _plano(),
        "10",
        "0",
        "",
        comb.ELU_NORMAL,
    )
    valores = forca.vetor
    em_pe = ri.placa_com_corte(valores, "0", "Momento 1")
    n, vy, vz, my, mz, t = valores
    # Ao inverter x local, inverte-se também y local e a face que chega à placa.
    invertida = ri.placa_com_corte((n, vy, -vz, my, -mz, t), "1", "Momento 1")
    assert em_pe == invertida
    # Para x da placa = +z local, adota-se x global = x placa neste exemplo.
    exemplo = ri.placa_com_reacao(
        (
            -em_pe["vx_kN"],
            -em_pe["vy_kN"],
            em_pe["n_sd_kN"],
            em_pe["m_sd_y_kNm"],
            -em_pe["m_sd_kNm"],
            -em_pe["mz_kNm"],
        ),
        0,
    )
    assert exemplo == em_pe


def test_abertura_usa_combinacao_simultanea_em_vez_de_somar_extremos():
    e = ab.EntradaAberturas()
    dados = ab.EsforcosImportados(
        ((ab.EsforcoNaAbertura("Flexão", -50, 1), ab.EsforcoNaAbertura("Cortante", 1, -45)),)
        * len(e.aberturas),
        55,
        47,
        46,
    )
    r = ab.calcular(ab.com(e, esforcos=dados))
    for grupo in r.grupos:
        for linha in grupo.linhas:
            if linha.nome == "Esforços no centro da abertura":
                assert linha.referencia in {"Flexão", "Cortante"}
                assert not ("50,00" in linha.formula and "45,00" in linha.formula)


def _salvar_modelo_ativo(*, compartilhado=False):
    projeto = obter_projeto_ativo()
    modelo = _modelo()
    if compartilhado:
        modelo["barras"]["11"] = {"nos": [1, 3], "secao": "W 200", "material": "ASTM A36"}
    return salvar_projeto(
        {
            **projeto,
            robot.CAMPO: modelo,
            robot.CAMPO_ORIGEM: robot.ROBOT,
            "plano_de_cargas": pc.para_dicionario(_plano()),
        },
        motivo="Amostra Robot",
    )


def test_memorial_usa_revisao_do_calculo_e_propagacao_de_dependencias(banco_com_projeto):
    projeto = _salvar_modelo_ativo()
    modelo = robot.modelo_do_projeto(projeto)
    quadro = rb.montar_do_robot(modelo)
    fonte = ri.fonte(
        projeto, finalidade="apoios", origem="Casos simples do Robot", tipos=("Reações",)
    )
    novo = registrar_calculo_tecnico(
        projeto["id"], ri.registrar(rb.registro_das_reacoes(quadro), fonte)
    )
    registro = novo["registros_tecnicos"][-1]
    assert registro["estado_dependencias"]["status"] == "Atual"
    ids = [registro["id"]]
    word = pr.gerar_relatorio_industrial_word(novo, registros_ids=ids)
    pdf = pr.gerar_relatorio_industrial_pdf(novo, registros_ids=ids)
    anglo = ma.gerar_word_anglo(ma.montar_modelo_anglo(novo, registros_ids=ids))
    for dados in (word, anglo):
        with ZipFile(BytesIO(dados)) as z:
            texto = z.read("word/document.xml").decode()
        assert "Remessas do Autodesk Robot" in texto
        assert "Reações.txt" in texto
    texto = " ".join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    assert "Autodesk Robot" in texto
    outra = salvar_projeto({**novo, robot.CAMPO: {**modelo, "assinatura": "nova", "revisao": "B"}})
    antigo = outra["registros_tecnicos"][-1]
    assert antigo["estado_dependencias"]["status"] == "Desatualizado"
    assert antigo["entradas"]["revisao_modelo_robot"] == "A"


@pytest.mark.parametrize(
    ("pagina", "prefixo", "campo", "esperado"),
    [
        ("placa_de_base", "pb_robot", "pb_varias", "varias"),
        ("emenda_pilar", "emp_robot", None, None),
        ("ligacoes_estruturais", "lig_robot_chapa", "lig_v", 8.5),
        ("ligacao_rigida", "lr_robot", "lr_M", 17.0),
    ],
)
def test_transferencia_na_interface(banco_com_projeto, pagina, prefixo, campo, esperado):
    _salvar_modelo_ativo()
    tela = abrir(f"app_pages/{pagina}.py")
    tela.selectbox(key=f"{prefixo}_barra").set_value("10").run()
    if pagina.startswith("ligac"):
        tela.selectbox(key=f"{prefixo}_comb").set_value("Robot 3 · Teste ELU").run()
    tela.button(key=f"{prefixo}_aplicar").click().run()
    assert not tela.exception
    assert tela.session_state[f"{prefixo}_fonte_aplicada"][1]["barra"] == "10"
    if campo:
        assert tela.session_state[campo] == esperado


def test_placa_com_no_compartilhado_usa_a_barra(banco_com_projeto):
    _salvar_modelo_ativo(compartilhado=True)
    tela = abrir("app_pages/placa_de_base.py")
    tela.selectbox(key="pb_robot_barra").set_value("10").run()
    assert "pb_robot_usar_no" not in {c.key for c in tela.checkbox}
    tela.button(key="pb_robot_aplicar").click().run()
    fonte = tela.session_state["pb_robot_fonte_aplicada"][1]
    assert "Esforços" in fonte["documentos"]


def test_aberturas_aplica_secao_e_registra_origem(banco_com_projeto):
    _salvar_modelo_ativo()
    tela = abrir("app_pages/aberturas_alma.py")
    tela.number_input(key="ab_L").set_value(3000)
    geometria = {
        "edited_rows": {0: {"Centro a partir do apoio (mm)": 1500}},
        "added_rows": [],
        "deleted_rows": [1],
    }
    tela.session_state["ab_aberturas"] = geometria
    tela.selectbox(key="ab_robot_barra").set_value("10").run()
    tela.session_state["ab_aberturas"] = geometria
    tela.checkbox(key="ab_robot_confirmar").check().run()
    assert not tela.button(key="ab_robot_aplicar").disabled
    tela.session_state["ab_aberturas"] = geometria
    tela.button(key="ab_robot_aplicar").click().run()
    assert not tela.exception
    assert any("A verificação usa os esforços do Robot" in a.value for a in tela.success), [
        a.value for a in (*tela.warning, *tela.error, *tela.info)
    ]
    tela.session_state["ab_aberturas"] = geometria
    tela.button(key="ab_registrar").click().run()
    registro = obter_projeto_ativo()["registros_tecnicos"][-1]
    assert registro["entradas"]["barra_robot"] == "10"
    assert registro["entradas"]["revisao_modelo_robot"] == "A"
    assert any("x/L = 0.5" in str(v) for v in registro["resultados"]["tabelas_memorial"])
