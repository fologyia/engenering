"""Sequenciamento sugerido e a fiação do motor de dependências no registro."""

from core import module_sequencing as seq
from core.materials_registry import criar_material_projeto
from core.project_store import criar_projeto, obter_projeto, registrar_calculo_tecnico, salvar_projeto


def _registro_estatico(*, materiais_ids=()):
    return {
        "modulo": "Análise estática",
        "modulo_id": "analise_estatica",
        "titulo": "Verificação do estado plano de tensões",
        "status": "Atende",
        "resumo": "teste",
        "entradas": {"sigma_x_MPa": 100.0, "Sy_MPa": 250.0},
        "resultados": {"von_mises_MPa": 100.0},
        "materiais_ids": list(materiais_ids),
    }


def _material():
    return criar_material_projeto(
        nome="Aço genérico",
        familia="Aço carbono",
        condicao="Como recebido",
        forma_produto="Barra",
        propriedades={"Sy_MPa": 250.0, "Sut_MPa": 400.0},
        origem_tipo="Ficha técnica do fabricante",
        fonte="Fabricante X",
    )


def test_modulo_fora_de_qualquer_fluxo_nao_mostra_sequencia():
    assert seq.montar_sequencia(None, "materiais_tecnicos") is None
    assert seq.montar_sequencia(None, "central_validacao") is None


def test_sem_projeto_mostra_fluxo_completo_sem_bloquear_caso_especifico():
    etapas = seq.montar_sequencia(None, "analise_estatica")
    assert etapas is not None
    situacoes = {etapa.modulo_id: etapa.situacao for etapa in etapas}
    assert situacoes["analise_estatica"] == "atual"
    assert situacoes["casos_carga"] == "pendente"
    # Um "caso específico" (entrar direto na análise) nunca vira bloqueio:
    # só existem passos "atual" ou "pendente" quando não há projeto.
    assert all(etapa.situacao in ("atual", "pendente") for etapa in etapas)


def test_registro_sem_dependencias_conta_como_concluida(tmp_path):
    banco = tmp_path / "projetos.sqlite3"
    projeto = criar_projeto("Projeto teste", caminho_banco=banco)
    registrar_calculo_tecnico(projeto["id"], _registro_estatico(), caminho_banco=banco)

    projeto_atual = obter_projeto(projeto["id"], caminho_banco=banco)
    etapas = seq.montar_sequencia(projeto_atual, "analise_fadiga")
    situacoes = {etapa.modulo_id: etapa.situacao for etapa in etapas}
    assert situacoes["analise_estatica"] == "concluida"
    assert situacoes["analise_fadiga"] == "atual"


def test_material_alterado_sem_recalcular_marca_atencao(tmp_path):
    banco = tmp_path / "projetos.sqlite3"
    projeto = criar_projeto("Projeto teste", caminho_banco=banco)
    material = _material()
    projeto["materiais_projeto"].append(material)
    projeto = salvar_projeto(projeto, caminho_banco=banco)

    registrar_calculo_tecnico(
        projeto["id"],
        _registro_estatico(materiais_ids=[material["id"]]),
        caminho_banco=banco,
    )
    projeto_atual = obter_projeto(projeto["id"], caminho_banco=banco)
    situacoes_antes = {
        etapa.modulo_id: etapa.situacao
        for etapa in seq.montar_sequencia(projeto_atual, "circulo_mohr")
    }
    assert situacoes_antes["analise_estatica"] == "concluida"

    # O material muda depois do cálculo, sem que ninguém refaça a análise.
    projeto_atual["materiais_projeto"][0]["propriedades"]["Sy_MPa"] = 300.0
    projeto_mutado = salvar_projeto(projeto_atual, caminho_banco=banco)

    situacoes_depois = {
        etapa.modulo_id: etapa.situacao
        for etapa in seq.montar_sequencia(projeto_mutado, "circulo_mohr")
    }
    assert situacoes_depois["analise_estatica"] == "atencao"
