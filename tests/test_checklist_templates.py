"""Modelos de checklist por tipo de projeto.

O que importa aqui: o catálogo embutido é íntegro, o modelo certo é
sugerido para cada tipo, os itens entram no projeto com o responsável do
papel certo e sem duplicar, e um arquivo do usuário pode sobrepor um modelo
sem quebrar os outros.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from core.checklist_templates import (
    ARQUIVO_MODELOS,
    PAPEIS,
    TIPO_PROJETO_PADRAO,
    ModeloChecklistErro,
    aplicar_modelo,
    instanciar_modelo,
    itens_ja_aplicados,
    listar_modelos,
    modelo_para_tipo,
    obter_modelo,
    tipos_de_projeto,
)
from core.project_store import criar_item, novo_projeto_documento


def projeto_base(**campos):
    projeto = novo_projeto_documento("Suporte", codigo="P-1", objetivo="x", **campos)
    projeto.update({"responsavel": "Eng. Ana", "verificador": "Eng. Bruno", "aprovador": ""})
    return projeto


def test_catalogo_embutido_e_integro():
    assert ARQUIVO_MODELOS.exists()
    modelos = listar_modelos(arquivo_usuario=ARQUIVO_MODELOS.with_name("inexistente.json"))
    ids = [modelo.id for modelo in modelos]
    assert len(ids) == len(set(ids))
    assert {"generico", "estrutura_metalica", "vaso_tanque", "transportador", "eixo_maquina"} <= set(ids)
    for modelo in modelos:
        assert modelo.itens, modelo.id
        assert not modelo.editavel
        for item in modelo.itens:
            assert item.item
            assert item.papel in (*PAPEIS, "")
        # Todo modelo fecha com verificação independente e aprovação, com os papéis certos.
        papeis = {item.chave: item.papel for item in modelo.itens}
        assert papeis.get("verificacao") == "verificador", modelo.id
        assert papeis.get("aprovacao") == "aprovador", modelo.id
        assert any(item.critico for item in modelo.itens)


def test_tipos_de_projeto_comecam_pelo_padrao_e_cobrem_os_modelos():
    tipos = tipos_de_projeto()
    assert tipos[0] == TIPO_PROJETO_PADRAO
    assert "Estrutura metálica" in tipos
    assert "Transportador de correia" in tipos
    assert len(tipos) == len(set(tipos))


def test_modelo_sugerido_por_tipo_com_generico_de_reserva():
    assert modelo_para_tipo("Estrutura metálica").id == "estrutura_metalica"
    assert modelo_para_tipo("estrutura METÁLICA").id == "estrutura_metalica"
    assert modelo_para_tipo("Vaso de pressão / tanque").id == "vaso_tanque"
    assert modelo_para_tipo("tipo que não existe").id == "generico"
    assert modelo_para_tipo("").id == "generico"
    assert obter_modelo("EIXO_MAQUINA").id == "eixo_maquina"
    assert obter_modelo("nada") is None


def test_instanciar_preenche_responsavel_pelo_papel_sem_inventar_nome():
    modelo = obter_modelo("generico")
    projeto = projeto_base()
    linhas = instanciar_modelo(modelo, projeto, hoje=date(2026, 9, 11))
    por_chave = {linha["origem_modelo"].split(":")[1]: linha for linha in linhas}
    assert por_chave["objetivo"]["responsavel"] == "Eng. Ana"
    assert por_chave["verificacao"]["responsavel"] == "Eng. Bruno"
    assert por_chave["aprovacao"]["responsavel"] == ""  # aprovador ainda não cadastrado
    assert all(linha["estado"] == "Aberto" for linha in linhas)
    assert all(linha["prazo"] == "" for linha in linhas)  # os modelos embutidos não fixam prazo
    assert por_chave["objetivo"]["critico"] is True
    assert len({linha["id"] for linha in linhas}) == len(linhas)


def test_aplicar_modelo_acrescenta_sem_duplicar_e_preserva_o_que_existia():
    modelo = obter_modelo("estrutura_metalica")
    projeto = projeto_base(tipo_projeto="Estrutura metálica")
    manual = criar_item(item="Item manual do projeto", estado="Concluído")
    # Um item digitado à mão com o MESMO texto de um item do modelo não é
    # repetido: o modelo reconhece pelo texto, não só pela origem.
    redigitado = criar_item(item=modelo.itens[0].item, estado="Aberto")
    projeto["checklist"] = [manual, redigitado]

    documento, novos, ignorados = aplicar_modelo(projeto, modelo)
    assert ignorados == [modelo.itens[0].chave]
    assert len(novos) == len(modelo.itens) - 1
    assert [item["id"] for item in documento["checklist"][:2]] == [manual["id"], redigitado["id"]]
    assert len(documento["checklist"]) == 2 + len(novos)
    # O projeto original não é mutado.
    assert len(projeto["checklist"]) == 2

    # Aplicar de novo não acrescenta nada.
    documento2, novos2, ignorados2 = aplicar_modelo(documento, modelo)
    assert novos2 == []
    assert len(ignorados2) == len(modelo.itens)
    assert len(documento2["checklist"]) == len(documento["checklist"])
    assert itens_ja_aplicados(documento2, modelo) == {item.chave for item in modelo.itens}


def test_dois_modelos_podem_coexistir_no_mesmo_projeto():
    projeto = projeto_base()
    documento, novos_a, _ = aplicar_modelo(projeto, obter_modelo("generico"))
    documento, novos_b, ignorados_b = aplicar_modelo(documento, obter_modelo("eixo_maquina"))
    # Os itens de texto idêntico (verificação e aprovação) não são repetidos.
    assert set(ignorados_b) == {"verificacao", "aprovacao"}
    assert len(documento["checklist"]) == len(novos_a) + len(novos_b)


def test_arquivo_do_usuario_sobrepoe_por_id_e_acrescenta(tmp_path):
    usuario = tmp_path / "modelos_checklist_usuario.json"
    usuario.write_text(
        json.dumps(
            {
                "modelos": [
                    {
                        "id": "generico",
                        "nome": "Genérico da empresa",
                        "tipo_projeto": "Projeto industrial",
                        "itens": [
                            {"chave": "a", "item": "Item da empresa", "papel": "responsavel", "prazo_dias": 7},
                            {"chave": "verificacao", "item": "Verificar", "papel": "verificador"},
                        ],
                    },
                    {
                        "id": "tubulacao",
                        "nome": "Tubulação",
                        "tipo_projeto": "Tubulação industrial",
                        "itens": [{"item": "Isométricos recebidos"}],
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    modelos = {modelo.id: modelo for modelo in listar_modelos(arquivo_usuario=usuario)}
    assert modelos["generico"].nome == "Genérico da empresa"
    assert modelos["generico"].editavel is True
    assert len(modelos["generico"].itens) == 2
    assert modelos["estrutura_metalica"].editavel is False
    assert modelos["tubulacao"].itens[0].chave == "item-1"
    assert "Tubulação industrial" in tipos_de_projeto(arquivo_usuario=usuario)
    assert modelo_para_tipo("Tubulação industrial", arquivo_usuario=usuario).id == "tubulacao"

    linhas = instanciar_modelo(modelos["generico"], projeto_base(), hoje=date(2026, 9, 11))
    assert linhas[0]["prazo"] == "2026-09-18"
    assert linhas[0]["responsavel"] == "Eng. Ana"


@pytest.mark.parametrize(
    "modelo",
    [
        {"id": "x", "nome": "X", "itens": [{"item": ""}]},
        {"id": "x", "nome": "X", "itens": [{"item": "a", "papel": "gerente"}]},
        {"id": "x", "nome": "X", "itens": [{"chave": "k", "item": "a"}, {"chave": "k", "item": "b"}]},
        {"id": "x", "nome": "X", "itens": [{"item": "a", "prazo_dias": "sete"}]},
        {"id": "", "nome": "X", "itens": []},
        {"id": "x", "nome": "X"},
    ],
)
def test_modelo_malformado_e_recusado_com_mensagem(tmp_path, modelo):
    usuario = tmp_path / "ruim.json"
    usuario.write_text(json.dumps({"modelos": [modelo]}), encoding="utf-8")
    with pytest.raises(ModeloChecklistErro):
        listar_modelos(arquivo_usuario=usuario)


def test_json_invalido_e_recusado(tmp_path):
    usuario = tmp_path / "ruim.json"
    usuario.write_text("{ não é json", encoding="utf-8")
    with pytest.raises(ModeloChecklistErro):
        listar_modelos(arquivo_usuario=usuario)


def test_tipo_de_projeto_entra_na_criacao():
    assert novo_projeto_documento("A", tipo_projeto="Estrutura metálica")["tipo_projeto"] == "Estrutura metálica"
    assert novo_projeto_documento("A", tipo_projeto="  ")["tipo_projeto"] == TIPO_PROJETO_PADRAO
