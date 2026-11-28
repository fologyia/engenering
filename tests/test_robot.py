from __future__ import annotations

from dataclasses import replace
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from openpyxl import Workbook, load_workbook

from core import esforcos_modelo as em
from core import exportacao_cargas as ex
from core import load_combinations as comb
from core import plano_de_cargas as pc
from core import reacoes_nas_bases as rb
from core import robot
from core import tratamento_do_modelo as tm
from core import verificacao_barras as vb
from core import verificacao_modulo as vm
from core.project_store import obter_projeto_ativo, salvar_projeto
from tests.apoio_paginas import abrir

EXPORTACAO_ROBOT = Path(__file__).parent / "fixtures" / "robot_2027"
ARQUIVOS_ROBOT = ("nos", "barras", "casos", "combinacoes", "esforcos_5p", "reacoes")


def test_exportacao_nativa_robot_2027_com_cinco_pontos():
    """Pórtico 3D com PP, SC, ELU = 1,25 PP + 1,5 SC e ELS = PP + SC."""
    tabelas = {}
    for tipo, nome in zip(robot.ESQUEMAS, ARQUIVOS_ROBOT, strict=True):
        arquivo = EXPORTACAO_ROBOT / f"{nome}.txt"
        (tabela,) = robot.ler_tabelas(arquivo.name, arquivo.read_bytes())
        tabelas[tipo] = robot.Selecao(tabela, 1, robot.colunas_sugeridas(tipo, tabela.linhas[0]))
    modelo = robot.importar(tabelas, robot.Unidades(), "Pórtico calculado no Robot 2027", "A")
    dados = robot.dados_do_modelo(modelo)
    assert len(modelo["barras"]) == 3
    assert modelo["casos"]["3"]["definicao"] == "1*1.25+2*1.50"
    assert [p.elemento for p in dados.casos["1"].membros["1"]] == ["0", "0.25", "0.5", "0.75", "1"]
    plano = pc.PlanoDeCargas((pc.nova_acao("PP"), pc.nova_acao("SC")))
    estados = [comb.ELU_NORMAL, comb.ELS_RARA]
    direto = robot.preparar_combinacoes(modelo, dados, plano, estados)
    assert direto.resultados["1"][0][2] == (-39.87, 0, 4.26, -7.51, 0, 0)
    toolkit = robot.preparar_combinacoes(_ajustar(modelo), dados, plano, estados)
    lista_toolkit = pc.combinacoes(plano, estados)
    fatores_equivalentes = ({"PP": 1.25, "SC": 1.5}, {"PP": 1, "SC": 1})
    nomes_equivalentes = {
        ex.nome_da_combinacao(c, len(lista_toolkit))
        for c in lista_toolkit
        if c.fatores in fatores_equivalentes
    }
    assert len(toolkit.nomes) > len(nomes_equivalentes) == 2  # O plano inclui o PP favorável.
    for barra, vetores in direto.resultados.items():
        equivalentes = [v for v in toolkit.resultados[barra] if v[0] in nomes_equivalentes]
        for (_, posicao, valor), (_, posicao_calculada, calculado) in zip(
            vetores,
            equivalentes,
            strict=True,
        ):
            assert posicao == posicao_calculada
            assert valor == pytest.approx(calculado, abs=0.02)  # TXT do Robot arredondado a 0,01
    quadro = rb.montar_do_robot(modelo)
    assert quadro.acao("Nó 1", "1").forca_kN == (1, 0, -9.38)
    assert quadro.acao("Nó 4", "1").forca_kN == (1, 0, -0.62)
    assert not quadro.faltam


def _tabelas(*, deslocar_posicao: bool = False, reacao_completa: bool = True):
    registros = {
        "Nós": "Nó;X [mm];Y [mm];Z [mm]\n1;0;0;0\n2;0;0;3000\n3;50;0;0\n",
        "Barras": "Bar;Start node;End node;Section;Material;Gamma;Strong axis\n"
        "10;1;2;W 200 x 19,3;ASTM A572 Gr 50;0;y\n",
        "Casos": "Caso;Nome;Análise;Natureza\n1;PP;Estática linear;permanente\n"
        "2;SC;Estática linear;variável\n",
        "Combinações": "Caso;Nome;Análise;Estado-limite;Caso base;Fator\n"
        "3;Teste ELU;Estática de segunda ordem;ELU normal;1;1,25\n"
        "3;Teste ELU;Estática de segunda ordem;ELU normal;2;1,5\n"
        "4;Teste ELS;Estática linear;ELS rara;1;1\n"
        "4;Teste ELS;Estática linear;ELS rara;2;1\n",
        "Esforços": "Barra;Caso;Posição [%];FX [N];FY [N];FZ [N];MX [N.mm];MY [N.mm];MZ [N.mm]\n",
        "Reações": "Node;Case;FX [kN];FY [kN];FZ [kN];MX [kN.m];MY [kN.m];MZ [kN.m]\n"
        "1;1;2;0;10;0;3;0\n3;1;0;0;0;0;0;0\n"
        "1;2;4;0;20;0;6;0\n"
        "1;3;8,5;0;42,5;0;12,75;0\n",
    }
    if reacao_completa:
        registros["Reações"] += "3;2;0;0;0;0;0;0\n"
    for codigo, fator in ((1, 1), (2, 2), (3, 4.25), (4, 3)):
        meio = 60 if codigo == 2 and deslocar_posicao else 50
        for posicao in (100, 0, meio):
            valores = [
                10000 * fator,
                1000 * fator,
                2000 * fator,
                300000 * fator,
                4000000 * fator,
                -5000000 * fator,
            ]
            bruto = ";".join(str(x).replace(".", ",") for x in valores)
            registros["Esforços"] += f"10;{codigo};{posicao};{bruto}\n"

    tabelas = {}
    for tipo, conteudo in registros.items():
        (tabela,) = robot.ler_tabelas(f"{tipo}.txt", conteudo.encode())
        tabelas[tipo] = robot.Selecao(tabela, 1, robot.colunas_sugeridas(tipo, tabela.linhas[0]))
    return tabelas


def _modelo(**kwargs):
    return robot.importar(_tabelas(**kwargs), robot.Unidades(), "Pórtico", "A")


def _ajustar(modelo, *, origem=robot.TOOLKIT):
    return robot.atualizar_casos(
        modelo,
        {
            "1": {"codigo_plano": "PP"},
            "2": {"codigo_plano": "SC"},
        },
        origem,
    )


def test_valores_do_robot_mantem_vetor_e_segunda_ordem():
    modelo = _modelo()
    dados = robot.dados_do_modelo(modelo)
    preparo = robot.preparar_combinacoes(
        modelo,
        dados,
        pc.PlanoDeCargas(),
        (comb.ELU_NORMAL, comb.ELS_RARA),
    )
    vetores, metodo, _ = em.combinados_do_membro("10", preparo)
    assert vetores[0] == ("Robot 3 · Teste ELU", "x/L = 0", (-42.5, 4.25, 8.5, 17.0, -21.25, 1.275))
    assert "Robot" in metodo
    assert vetores[2][1] == "x/L = 1"
    assert preparo.segunda_ordem == {"Robot 3 · Teste ELU"}
    triplas = vb._triplas(vetores, em.EIXO_M1, 1.5, preparo.segunda_ordem)
    assert triplas[0].n == -42.5
    assert triplas[3].n == -45
    assert dados.membros["10"].eixo_forte == em.EIXO_M1


def test_toolkit_reusa_fatores_do_plano_e_exige_posicoes_e_casos_iguais():
    plano = pc.PlanoDeCargas((pc.nova_acao("PP"), pc.nova_acao("SC")))
    estados = (comb.ELU_NORMAL,)
    modelo = _ajustar(_modelo())
    dados = robot.dados_do_modelo(modelo)
    preparo = robot.preparar_combinacoes(modelo, dados, plano, estados)
    c = pc.combinacoes(plano, estados)[0]
    assert preparo.resultados["10"][0][2][0] == pytest.approx(
        -10 * c.fatores["PP"] - 20 * c.fatores["SC"]
    )
    for alterado, mensagem in [
        (_modelo(), "Vincule os casos"),
        (_ajustar(_modelo(deslocar_posicao=True)), "posições ou lados do corte"),
        (
            robot.atualizar_casos(modelo, {"1": {"analise": robot.SEGUNDA_ORDEM}}, robot.TOOLKIT),
            "exige análise linear",
        ),
    ]:
        alterado = {**alterado, "origem_combinacoes": robot.TOOLKIT}
        with pytest.raises(robot.ImportacaoRobotInvalida, match=mensagem):
            robot.preparar_combinacoes(alterado, robot.dados_do_modelo(alterado), plano, estados)


def test_fundacoes_mantem_apoios_proximos_e_apenas_casos_simples():
    modelo = _ajustar(_modelo(reacao_completa=False))
    quadro = rb.montar_do_robot(modelo)
    assert quadro.casos == ("1", "2")
    assert [p.rotulo for p in quadro.pes] == ["Nó 1", "Nó 3"]
    assert quadro.acao("Nó 1", "1").forca_kN == (-2, 0, -10)
    assert quadro.acao("Nó 1", "1").momento_kNm == (0, -3, 0)
    assert quadro.acao("Nó 3", "2") is None
    assert "faltam reações nos nós 3" in quadro.faltam[0]
    livro = load_workbook(BytesIO(rb.xlsx(quadro)))
    assert "PRELIMINAR" in livro["Leia-me"]["A1"].value
    assert livro["Reações por pé"]["A3"].value == "Nó 1"
    assert livro["Casos"]["B2"].value == "PP"


def test_arquivo_xlsx_tsv_e_erro_identifica_linha():
    xlsx = Workbook()
    xlsx.active.title = "Nodes"
    xlsx.active.append(["Node", "X [mm]", "Y [mm]", "Z [mm]"])
    xlsx.active.append([1, 0, 0, 0])
    xlsx.active.append([2, 0, 0, 3000])
    xlsx.active.append([3, 50, 0, 0])
    arquivo = BytesIO()
    xlsx.save(arquivo)
    (tabela,) = robot.ler_tabelas("Robot.xlsx", arquivo.getvalue())
    tabelas = _tabelas()
    tabelas["Nós"] = robot.Selecao(tabela, 1, robot.colunas_sugeridas("Nós", tabela.linhas[0]))
    (barras,) = robot.ler_tabelas(
        "barras.tsv",
        "Bar\tStart\tEnd\tSection\tMaterial\n10\t1\t8\tIPE 200\tS235\n".encode("utf-16"),
    )
    tabelas["Barras"] = robot.Selecao(
        barras, 1, robot.colunas_sugeridas("Barras", barras.linhas[0])
    )
    with pytest.raises(robot.ImportacaoRobotInvalida, match="barras.tsv, linha 2.*nó ausente"):
        robot.importar(tabelas, robot.Unidades(decimal_virgula=False), "Teste", "A")


def test_reenvio_preserva_os_ajustes_e_isola_origens():
    modelo = _ajustar(_modelo())
    novo = robot.importar(_tabelas(), robot.Unidades(), "Pórtico", "A", anterior=modelo)
    assert novo == modelo
    legado = em.EsforcosDoModelo(casos={"PP": em.CasoImportado("PP", "", "", "", "", {})})
    projeto = {
        robot.CAMPO: modelo,
        robot.CAMPO_ORIGEM: robot.ROBOT,
        "esforcos_do_modelo": em.para_dicionario(legado),
    }
    assert not tm.do_projeto(projeto).dados.casos
    assert rb.do_projeto(projeto).casos == ("1", "2")
    assert "PP" in tm.do_projeto({**projeto, robot.CAMPO_ORIGEM: robot.SOLIDWORKS}).dados.casos


def test_memorial_identifica_origem_e_revisao_do_relatorio():
    modelo = {
        **_modelo(),
        "relatorio": {"codigo": "CALC-RSA-01", "titulo": "Relatório Robot", "revisao": "B"},
    }
    dados = robot.dados_do_modelo(modelo)
    dados = replace(dados, membros={"10": replace(dados.membros["10"], lx_m=3.0, ly_m=3.0)})
    plano = pc.PlanoDeCargas()
    estados = [comb.ELU_NORMAL]
    preparo = robot.preparar_combinacoes(modelo, dados, plano, estados)
    resultados, _ = vb.verificar_barras(dados, plano, estados, preparo=preparo)
    assert resultados[0].combinacao == "Robot 3 · Teste ELU"
    registro = vb.registro_das_barras(
        resultados,
        dados,
        estados,
        contexto=robot.contexto(modelo),
        preparo=preparo,
    )
    assert "SolidWorks" not in registro["metodo"]
    with ZipFile(BytesIO(vm.memorial(registro))) as zipado:
        documento = zipado.read("word/document.xml").decode("utf-8")
    assert "CALC-RSA-01" in documento
    assert "Combinações calculadas no Robot" in documento


def test_paginas_exibem_modelo_robot_ativo(banco_com_projeto):
    projeto = obter_projeto_ativo()
    salvar_projeto(
        {**projeto, robot.CAMPO: _modelo(), robot.CAMPO_ORIGEM: robot.ROBOT}, motivo="Robot"
    )
    pagina = abrir("app_pages/esforcos_modelo.py")
    assert any("Pórtico · revisão A" in h.value for h in pagina.subheader)
    assert any("Combinação" in d.value.columns for d in pagina.dataframe)
    fundacoes = abrir("app_pages/reacoes_nas_bases.py")
    assert any("Pé" in d.value.columns for d in fundacoes.dataframe)


def test_cadastro_guiado_importa_registra_e_leva_ao_memorial(banco_com_projeto):
    projeto = obter_projeto_ativo()
    secao = f"jornada_secao_{projeto['id']}"
    pagina = abrir("app_pages/gestao_projetos.py", **{secao: "Cálculos"})
    importar = next(
        p.proto for p in pagina.get("page_link") if p.proto.label == "Importar do Robot"
    )
    assert importar.query_string == "fonte=robot"
    pagina.query_params["fonte"] = "robot"
    pagina.switch_page("app_pages/esforcos_modelo.py").run()
    assert pagina.radio(key=f"modelo_fonte_{projeto['id']}").value == robot.ROBOT
    chave = f"robot_{projeto['id']}"
    for tipo, nome in zip(robot.ESQUEMAS, ARQUIVOS_ROBOT, strict=True):
        texto = (EXPORTACAO_ROBOT / f"{nome}.txt").read_text(encoding="utf-8")
        pagina.text_area(key=f"{chave}_colar_{tipo}").set_value(texto)
    pagina.run()
    pagina.text_input(key=f"{chave}_nome").set_value("Pórtico 2027")
    pagina.text_input(key=f"{chave}_revisao").set_value("A")
    pagina.checkbox(key=f"{chave}_confirmado").check()
    next(b for b in pagina.button if b.label == "Conferir tabelas").click().run()
    assert any("FX global (kN)" in d.value.columns for d in pagina.dataframe)
    assert not robot.ativo(obter_projeto_ativo())
    next(b for b in pagina.button if b.label == "Salvar remessa e ativar Robot").click().run()
    salvo = obter_projeto_ativo()
    assert robot.ativo(salvo)
    assert len(salvo[robot.CAMPO]["barras"]) == 3
    next(b for b in pagina.button if b.label == "Conferir tabelas").click().run()
    assert next(b for b in pagina.button if b.label == "Salvar remessa e ativar Robot").disabled

    pagina.session_state[secao] = "Cálculos"
    pagina.switch_page("app_pages/gestao_projetos.py").run()
    assert any("Pórtico 2027 · revisão A" in c.value for c in pagina.caption)
    assert any(p.proto.label == "Reações nas bases" for p in pagina.get("page_link"))

    pagina.switch_page("app_pages/reacoes_nas_bases.py").run()
    pagina.button(key=f"robot_registrar_fundacoes_{projeto['id']}").click().run()
    assert not pagina.exception

    pagina.session_state[secao] = "Entrega"
    pagina.switch_page("app_pages/gestao_projetos.py").run()
    assert any(p.proto.label == "Preparar memorial" for p in pagina.get("page_link"))
    pagina.switch_page("app_pages/central_relatorios.py").run()
    assert not pagina.exception
    quadro = next(d.value for d in pagina.dataframe if "Grupos identificados" in d.value.columns)
    assert {"Verificação das barras", "Placas de base", "Fundações"} <= set(quadro["Etapa"])
    assert "Pilares" not in quadro["Etapa"].values
    assert quadro.set_index("Etapa").loc["Fundações", "Grupos identificados"].startswith("1 grupo")
