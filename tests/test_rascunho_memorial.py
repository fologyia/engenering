from core.rascunho_memorial import sugerir_contexto


def test_sugestoes_usam_apenas_fontes_efetivamente_fornecidas():
    projeto = {
        "descricao": "Plataforma de acesso ao tanque.",
        "base_projeto": {"base_carregamentos": "Desenho D-01, revisão 2."},
    }
    registros = [{"titulo": "Viga V-01", "metodo": "Análise elástica.", "status": "Pendente"}]
    sugestoes = sugerir_contexto(projeto, registros)
    assert "Plataforma de acesso" in sugestoes["sistema"]
    assert "Desenho D-01" in sugestoes["acoes"]
    assert "Viga V-01: Análise elástica" in sugestoes["modelo"]
    assert "Pendente" in sugestoes["conclusao_geral"]
    assert "combinacoes" not in sugestoes
    assert "vinculos" not in sugestoes
    assert "atende" not in sugestoes["conclusao_geral"].lower()


def test_sugestoes_vazias_nao_fabricam_dados():
    assert sugerir_contexto({}, []) == {}
