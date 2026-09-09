from core.project_dependencies import preparar_registro_dependencias, sincronizar_estados_dependencias
from core.project_store import criar_item, novo_projeto_documento
from core.project_validation import validar_projeto
from core.materials_registry import listar_catalogo_referencia


def _projeto_documentado():
    projeto = novo_projeto_documento("Adequação do pipe rack", codigo="PR-204")
    projeto.update(
        {
            "cliente": "Operação",
            "unidade_industrial": "Planta A",
            "area": "Processo",
            "tag_equipamento": "PR-204",
            "objetivo": "Verificar a nova condição de carregamento.",
            "responsavel": "Eng. A",
            "verificador": "Eng. B",
            "aprovador": "Eng. C",
        }
    )
    projeto["base_projeto"] = {
        "referencias_desenho": "DE-204 Rev. 3",
        "base_carregamentos": "LC-204 Rev. 1",
        "condicoes_operacao": "Operação contínua a 80 °C",
        "criterio_aceitacao": "Utilização <= 1,0",
        "vida_requerida": "20 anos",
        "limitacoes": "Sem avaliação sísmica",
    }
    projeto["componentes"] = [
        criar_item(
            tag="PR-204",
            descricao="Pipe rack",
            material="ASTM A36",
            fonte_material="Certificado e especificação",
        )
    ]
    projeto["normas"] = [
        criar_item(
            codigo="ABNT NBR 8800",
            edicao="2024",
            escopo="Barras e ligações",
            obrigatoria=True,
            conferida=True,
            fonte="PDF controlado",
        )
    ]
    projeto["registros_tecnicos"] = [
        criar_item(
            modulo="Estruturas de aço",
            titulo="Barra B12",
            status="Atende",
            resumo="Verificação ELU e ELS",
            entradas={"Nd_kN": 120.0},
            resultados={"utilizacao_maxima": 0.82},
            premissas=["Análise linear"],
            alertas=[],
            referencias=["MC-204"],
            conclusao="Atende aos critérios informados.",
        )
    ]
    projeto["checklist"] = [
        criar_item(item="Revisão independente", estado="Concluído", critico=True)
    ]
    return projeto


def test_validacao_identifica_projeto_documentado_sem_bloqueios():
    resultado = validar_projeto(_projeto_documentado())
    assert resultado["contagens"]["Bloqueio"] == 0
    assert resultado["indice_documental"] >= 95
    assert resultado["prontidao"] in {"Pronto para revisão", "Pronto com ressalvas"}


def test_validacao_detecta_utilizacao_e_checklist_critico():
    projeto = _projeto_documentado()
    projeto["registros_tecnicos"][0]["resultados"]["utilizacao_maxima"] = 1.12
    projeto["checklist"][0]["estado"] = "Aberto"
    resultado = validar_projeto(projeto)
    titulos = {item["titulo"] for item in resultado["achados"] if item["severidade"] == "Bloqueio"}
    assert any("utilização superior" in titulo for titulo in titulos)
    assert any("Checklist aberto" in titulo for titulo in titulos)
    assert resultado["prontidao"] == "Não pronto para emissão"


def test_validacao_nao_chama_indice_de_conformidade():
    resultado = validar_projeto(_projeto_documentado())
    assert "Não representa certificação" in resultado["aviso"]


def test_validacao_bloqueia_material_orientativo_vinculado_e_risco_alto():
    projeto = _projeto_documentado()
    material = listar_catalogo_referencia()[0]
    material["id"] = "MAT-REF"
    material["vinculacoes"] = [projeto["componentes"][0]["id"]]
    projeto["materiais_projeto"] = [material]
    projeto["componentes"][0]["material_id"] = "MAT-REF"
    projeto["registros_tecnicos"].append(
        criar_item(
            modulo="Análise de sensibilidade",
            titulo="Risco da capacidade",
            status="Atenção",
            resumo="Monte Carlo",
            metodo="1000 amostras",
            entradas={"demanda": 80},
            resultados={"probabilidade_nao_atendimento_pct": 25.0},
            premissas=["Independência"],
            referencias=["MC-204"],
            conclusao="Risco elevado.",
        )
    )
    resultado = validar_projeto(projeto)
    bloqueios = [item["titulo"] for item in resultado["achados"] if item["severidade"] == "Bloqueio"]
    assert any("dado orientativo vinculado" in titulo for titulo in bloqueios)
    assert any("risco probabilístico relevante" in titulo for titulo in bloqueios)


def test_validacao_sinaliza_calculo_com_material_alterado_depois_do_registro():
    projeto = _projeto_documentado()
    projeto["materiais_projeto"] = [
        {"id": "MAT-1", "nome": "Aço A36", "propriedades": {"Sy_MPa": 250.0}}
    ]
    registro_base = {
        "modulo": "Análise estática",
        "modulo_id": "analise_estatica",
        "titulo": "Verificação do ponto crítico",
        "status": "Atende",
        "resumo": "x",
        "entradas": {"sigma_x_MPa": 100.0},
        "resultados": {"von_mises_MPa": 100.0},
        "materiais_ids": ["MAT-1"],
    }
    projeto["registros_tecnicos"].append(
        preparar_registro_dependencias(projeto, registro_base)
    )

    # Recém-criado, o registro está em dia: nenhum achado de rastreabilidade.
    projeto_sincronizado = sincronizar_estados_dependencias(projeto)
    resultado_antes = validar_projeto(projeto_sincronizado)
    assert not any(
        item["categoria"] == "Rastreabilidade de cálculo" for item in resultado_antes["achados"]
    )

    # O material muda depois, sem que ninguém refaça o cálculo.
    projeto_sincronizado["materiais_projeto"][0]["propriedades"]["Sy_MPa"] = 300.0
    resultado_depois = validar_projeto(projeto_sincronizado)
    achados = [
        item for item in resultado_depois["achados"] if item["categoria"] == "Rastreabilidade de cálculo"
    ]
    assert achados
    assert achados[0]["severidade"] == "Atenção"
    assert achados[0]["modulo"] == "Análise estática"
