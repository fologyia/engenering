from core.project_validation import _ha_grandeza_informada, chave_estavel_achado, item_para_achado


def test_vinculo_nao_depende_da_posicao_do_achado():
    achado = {
        "id": "VAL-0001",
        "categoria": "Base de projeto",
        "modulo": "Projeto",
        "titulo": "Sem carregamentos",
    }
    chave = chave_estavel_achado(achado)
    item = {"origem_validacao": chave, "categoria": achado["categoria"], "item": achado["titulo"]}
    alterado = dict(achado, id="VAL-0042")
    assert chave_estavel_achado(alterado) == chave
    assert item_para_achado([item], alterado) == item


def test_vinculo_legado_confere_titulo_e_categoria_em_vez_do_numero():
    legado = {"origem_validacao": "VAL-0001", "categoria": "Base", "item": "Sem cargas"}
    mesmo = {"id": "VAL-0099", "categoria": "Base", "modulo": "Projeto", "titulo": "Sem cargas"}
    outro = dict(mesmo, id="VAL-0001", titulo="Sem desenho")
    assert item_para_achado([legado], mesmo) == legado
    assert item_para_achado([legado], outro) is None


def test_linhas_de_molde_sem_valor_nao_contam_como_dado_informado():
    assert not _ha_grandeza_informada({"grandezas": [{"grandeza": "Resistência", "valor": ""}]})
    assert _ha_grandeza_informada({"grandezas": [{"grandeza": "Força", "valor": 0}]})


def test_achados_de_registros_homonimos_tem_vinculos_distintos():
    primeiro = {
        "categoria": "Resultado técnico",
        "modulo": "Análise",
        "titulo": "Ligação: resultado não atende",
        "origem": "registro:primeiro",
    }
    segundo = dict(primeiro, origem="registro:segundo")
    assert chave_estavel_achado(primeiro) != chave_estavel_achado(segundo)
    legado = {
        "origem_validacao": "VAL-0001",
        "categoria": primeiro["categoria"],
        "item": primeiro["titulo"],
    }
    assert item_para_achado([legado], primeiro, achados=[primeiro, segundo]) is None
