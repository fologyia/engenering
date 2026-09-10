from core.load_cases import (
    calcular_combinacao,
    calcular_envelope,
    criar_caso_carga,
    criar_combinacao_carga,
)
from core.project_report import montar_modelo_relatorio
from core.project_store import criar_projeto, duplicar_projeto, salvar_projeto
from core.project_validation import validar_projeto
from core.technical_modules import listar_modulos, resolver_modulo
from core.technical_records import (
    avaliar_contrato_registro,
    criar_registro_tecnico,
)
from tests.test_project_validation import _projeto_documentado


def _casos():
    permanente = criar_caso_carga(
        caso_id="LC-1",
        codigo="LC-1",
        nome="Peso operacional",
        condicao="Operação normal",
        natureza="Permanente",
        tag="SK-1",
        origem="Lista de cargas",
        referencia="LC-001 Rev. 2",
        cargas={"Fy_kN": -100.0, "Mx_kNm": 12.0},
    )
    termico = criar_caso_carga(
        caso_id="LC-2",
        codigo="LC-2",
        nome="Expansão térmica",
        condicao="Operação normal",
        natureza="Térmica",
        tag="SK-1",
        origem="Modelo de flexibilidade",
        referencia="MF-001",
        cargas={"Fx_kN": 30.0, "Mx_kNm": -5.0, "delta_temperatura_C": 80.0},
    )
    return [permanente, termico]


def test_combinacao_preserva_sinais_e_vetor_simultaneo():
    casos = _casos()
    combinacao = criar_combinacao_carga(
        combinacao_id="COMB-1",
        nome="Operação",
        fatores={"LC-1": 1.0, "LC-2": 0.5},
    )
    resultado = calcular_combinacao(casos, combinacao)
    assert resultado["vetor"]["Fy_kN"] == -100.0
    assert resultado["vetor"]["Fx_kN"] == 15.0
    assert resultado["vetor"]["Mx_kNm"] == 9.5
    assert len(resultado["parcelas"]) == 2


def test_envelope_identifica_cenario_governante_por_componente():
    casos = _casos()
    combinacoes = [
        criar_combinacao_carga(nome="Operação", fatores={"LC-1": 1.0, "LC-2": 1.0}),
        criar_combinacao_carga(nome="Teste", fatores={"LC-1": 1.3}),
    ]
    envelope = calcular_envelope(casos, combinacoes)
    assert envelope["total_cenarios"] == 2
    assert envelope["componentes"]["Fy_kN"]["valor_governante"] == -130.0
    assert envelope["componentes"]["Fy_kN"]["cenario_governante"] == "Teste"
    assert envelope["componentes"]["Fx_kN"]["cenario_governante"] == "Operação"


def test_combinacao_rejeita_referencia_inexistente():
    combinacao = criar_combinacao_carga(nome="Inválida", fatores={"AUSENTE": 1.0})
    try:
        calcular_combinacao(_casos(), combinacao)
    except ValueError as erro:
        assert "inexistentes" in str(erro)
    else:
        raise AssertionError("A referência inválida deveria impedir o cálculo.")


def test_registro_tecnico_resolve_modulo_assina_e_detecta_alteracao():
    registro = criar_registro_tecnico(
        modulo="Análise estática",
        titulo="Ponto P1",
        status="Atende",
        resumo="Verificação",
        entradas={"sigma_x_MPa": 80.0},
        resultados={"fator_seguranca": 2.0},
        metodo="von Mises",
        conclusao="Atende.",
    )
    assert registro["modulo_id"] == "analise_estatica"
    assert len(registro["hash_calculo"]) == 64
    assert avaliar_contrato_registro(registro)["valido"]
    registro["resultados"]["fator_seguranca"] = 1.0
    assert not avaliar_contrato_registro(registro)["assinatura_valida"]


def test_catalogo_de_modulos_governa_grupos_de_navegacao():
    analises = listar_modulos(grupo="Análises técnicas")
    assert [item.id for item in analises] == [
        "analise_estatica",
        "flambagem_colunas",
        "analise_fadiga",
        "vigas_eixos",
        "assistente_cargas",
        "circulo_mohr",
        "analise_sensibilidade",
    ]
    assert resolver_modulo("Casos de carga").id == "casos_carga"
    assert resolver_modulo("Linha elástica").id == "vigas_eixos"


def test_relatorio_e_validacao_consumem_extensao_de_carregamentos():
    projeto = _projeto_documentado()
    projeto["casos_carga"] = _casos()
    projeto["combinacoes_carga"] = [
        criar_combinacao_carga(nome="Operação", fatores={"LC-1": 1.0, "LC-2": 1.0})
    ]
    modelo = montar_modelo_relatorio(projeto)
    assert any("Casos, combinações e envelopes" in secao["titulo"] for secao in modelo["secoes"])
    assert any("Casos de carga permanentes" in tabela.get("legenda", "") for secao in modelo["secoes"] for tabela in secao.get("tabelas", []))
    validacao = validar_projeto(projeto)
    assert not any(
        item["categoria"] == "Carregamentos" and item["severidade"] == "Bloqueio"
        for item in validacao["achados"]
    )


def test_duplicacao_remapeia_casos_fatores_e_vinculos(tmp_path):
    banco = tmp_path / "projetos.sqlite3"
    projeto = criar_projeto("Projeto com cargas", codigo="PC-1", caminho_banco=banco)
    projeto["casos_carga"] = _casos()
    projeto["combinacoes_carga"] = [
        criar_combinacao_carga(combinacao_id="COMB-1", nome="Operação", fatores={"LC-1": 1.0, "LC-2": 1.0})
    ]
    projeto = salvar_projeto(projeto, caminho_banco=banco)
    copia = duplicar_projeto(projeto["id"], caminho_banco=banco)
    ids_origem = {item["id"] for item in projeto["casos_carga"]}
    ids_copia = {item["id"] for item in copia["casos_carga"]}
    assert ids_origem.isdisjoint(ids_copia)
    assert set(copia["combinacoes_carga"][0]["fatores"]) == ids_copia

