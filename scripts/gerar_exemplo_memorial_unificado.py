"""Gera um memorial de demonstração sem alterar o banco permanente do usuário."""

from __future__ import annotations

from pathlib import Path

from core.load_cases import calcular_envelope, criar_caso_carga, criar_combinacao_carga
from core.materials_registry import criar_material_projeto, resumir_fonte
from core.project_report import gerar_relatorio_industrial_pdf, gerar_relatorio_industrial_word
from core.project_store import criar_item, novo_projeto_documento
from core.sensitivity import analisar_monte_carlo, analisar_oat
from core.technical_records import criar_registro_tecnico

RAIZ = Path(__file__).resolve().parents[1]


def montar_exemplo() -> dict:
    projeto = novo_projeto_documento("Reforço do suporte industrial SK-101", codigo="MC-SK101-001")
    projeto["id"] = "00000000-0000-4000-8000-000000000101"
    projeto.update(
        {
            "cliente": "Unidade industrial de demonstração",
            "unidade_industrial": "Planta A",
            "area": "Utilidades",
            "tag_equipamento": "SK-101",
            "descricao": "Verificação do suporte após aumento da carga permanente da linha.",
            "objetivo": "Demonstrar o memorial unificado, incluindo rastreabilidade de material e análise de sensibilidade.",
            "processo": "Suporte de tubulação",
            "regime_operacao": "Contínuo, 80 °C",
            "responsavel": "Engenheiro responsável",
            "verificador": "Engenheiro verificador",
            "aprovador": "Gestor de engenharia",
        }
    )
    projeto["base_projeto"] = {
        "referencias_desenho": "DE-SK101-004 Rev. 2; levantamento dimensional LD-17",
        "base_carregamentos": "LC-SK101-003 Rev. 1; peso operacional e reação da linha",
        "condicoes_operacao": "Operação contínua a 80 °C; ambiente interno não corrosivo",
        "criterio_aceitacao": "n ≥ 1,50; utilização ≤ 1,00; risco probabilístico de não atendimento ≤ 5%",
        "vida_requerida": "20 anos",
        "limitacoes": "Sem avaliação sísmica; soldas e ancoragens permanecem em memorial complementar",
    }
    componente = criar_item(
        tag="SK-101",
        descricao="Chapa principal do suporte",
        servico="Transferência de carga da linha para a estrutura",
        material="",
        fonte_material="",
        desenho="DE-SK101-004 Rev. 2",
        criticidade="Alta",
    )
    componente["id"] = "00000000-0000-4000-8000-000000000102"
    projeto["componentes"] = [componente]
    material = criar_material_projeto(
        nome="Aço estrutural do lote HN-24017",
        familia="Aço carbono estrutural",
        condicao="Laminado; condição registrada no certificado",
        forma_produto="Chapa 12,5 mm",
        lote="HN-24017",
        propriedades={
            "Sut_MPa": 430.0,
            "Sy_MPa": 285.0,
            "E_GPa": 200.0,
            "nu": 0.30,
            "densidade_kg_m3": 7850.0,
            "temperatura_min_C": -20.0,
            "temperatura_max_C": 120.0,
        },
        origem_tipo="Certificado do lote / MTR",
        fonte="Usina de demonstração",
        documento="MTR-45821",
        edicao="Rev. 0",
        pagina_clausula="p. 2, propriedades mecânicas",
        data_verificacao="2026-08-14",
        responsavel_verificacao="Engenheiro responsável",
        aplicabilidade="Mesma corrida, espessura e condição da chapa identificada no SK-101.",
        vinculacoes=[componente["id"]],
    )
    material["id"] = "00000000-0000-4000-8000-000000000103"
    projeto["materiais_projeto"] = [material]
    componente.update(
        {
            "material_id": material["id"],
            "material": material["nome"],
            "fonte_material": resumir_fonte(material),
        }
    )
    caso_operacional = criar_caso_carga(
        caso_id="00000000-0000-4000-8000-000000000107",
        codigo="LC-01",
        nome="Peso e reação operacional da linha",
        condicao="Operação normal",
        natureza="Permanente",
        tag="SK-101",
        origem="Lista de cargas do processo",
        referencia="LC-SK101-003 Rev. 1",
        cargas={"Fy_kN": -100.0, "Mx_kNm": 12.0},
    )
    caso_termico = criar_caso_carga(
        caso_id="00000000-0000-4000-8000-000000000108",
        codigo="LC-02",
        nome="Reação de expansão térmica",
        condicao="Operação normal",
        natureza="Térmica",
        tag="SK-101",
        origem="Modelo de flexibilidade da linha",
        referencia="MF-L101-005 Rev. 0",
        cargas={"Fx_kN": 30.0, "Mx_kNm": -5.0, "delta_temperatura_C": 80.0},
    )
    combinacao_operacao = criar_combinacao_carga(
        combinacao_id="00000000-0000-4000-8000-000000000109",
        nome="COMB-OP · operação simultânea",
        tipo="Operacional",
        descricao="Fatores de demonstração; conferir na base controlada do projeto real.",
        fatores={caso_operacional["id"]: 1.0, caso_termico["id"]: 1.0},
    )
    combinacao_teste = criar_combinacao_carga(
        combinacao_id="00000000-0000-4000-8000-000000000110",
        nome="COMB-TESTE · carga vertical",
        tipo="Teste",
        descricao="Fator de demonstração aplicado ao peso operacional.",
        fatores={caso_operacional["id"]: 1.3},
    )
    projeto["casos_carga"] = [caso_operacional, caso_termico]
    projeto["combinacoes_carga"] = [combinacao_operacao, combinacao_teste]
    envelope_cargas = calcular_envelope(
        projeto["casos_carga"], projeto["combinacoes_carga"]
    )
    projeto["normas"] = [
        criar_item(
            codigo="Especificação estrutural do projeto",
            edicao="Rev. 3",
            escopo="Critérios de resistência, fabricação e inspeção do suporte",
            obrigatoria=True,
            conferida=True,
            fonte="PDF controlado ESP-EST-001-R3.pdf",
        )
    ]

    registro_cargas = criar_registro_tecnico(
        modulo="Casos de carga",
        modulo_id="casos_carga",
        titulo="Envelope dos carregamentos do SK-101",
        status="Calculado",
        resumo="Combinações vetoriais de operação e teste com governante por componente.",
        metodo="Soma algébrica componente a componente com fatores explícitos.",
        metodo_versao="1.0",
        equacoes=["R_j = Σ(γ_i · R_ij)"],
        criterios=["Não combinar máximos independentes como simultâneos."],
        entradas={
            "casos": [caso_operacional["codigo"], caso_termico["codigo"]],
            "combinacoes": [combinacao_operacao["nome"], combinacao_teste["nome"]],
        },
        resultados={
            "total_cenarios_envelope": envelope_cargas["total_cenarios"],
            **{
                f"{chave.rsplit('_', 1)[0]}_envelope_{chave.rsplit('_', 1)[1]}": (
                    f"{item['valor_governante']:.6g} {item['unidade']} | "
                    f"{item['cenario_governante']}"
                )
                for chave, item in envelope_cargas["componentes"].items()
            },
        },
        premissas=[
            "Eixos e ponto de referência comuns.",
            "Fatores usados apenas para demonstração.",
            envelope_cargas["aviso"],
        ],
        alertas=[],
        referencias=["LC-SK101-003 Rev. 1", "MF-L101-005 Rev. 0"],
        conclusao="O envelope preserva o cenário governante de cada componente.",
        responsavel="Engenheiro responsável",
        casos_carga_ids=[caso_operacional["id"], caso_termico["id"]],
        componentes_ids=[componente["id"]],
    )
    registro_cargas["id"] = "00000000-0000-4000-8000-000000000111"

    estatico = criar_registro_tecnico(
        modulo="Análise estática",
        titulo="Estado plano de tensões na seção crítica P1",
        status="Atende",
        resumo="Verificação de von Mises para o caso de carga operacional governante.",
        metodo="Estado plano de tensões e critério de von Mises para material dúctil.",
        equacoes=["σvm = √(σx² − σxσy + σy² + 3τxy²)", "n = Sy / σvm"],
        criterios=["n ≥ 1,50"],
        entradas={
            "sigma_x_MPa": 120.0,
            "sigma_y_MPa": 30.0,
            "tau_xy_MPa": 25.0,
            "Sy_MPa": 285.0,
            "material_id": material["id"],
        },
        resultados={
            "von_mises_MPa": 125.797,
            "fator_seguranca": 2.266,
            "fator_seguranca_minimo": 1.5,
            "utilizacao_maxima": 0.4414,
        },
        premissas=["Tensões extraídas no ponto P1 do caso operacional governante.", "Comportamento elástico linear e material isotrópico."],
        alertas=[],
        referencias=["DE-SK101-004 Rev. 2", "LC-SK101-003 Rev. 1", "MTR-45821"],
        conclusao="O ponto P1 atende ao critério informado, com n = 2,266.",
        responsavel="Engenheiro responsável",
        casos_carga_ids=[caso_operacional["id"], caso_termico["id"]],
        componentes_ids=[componente["id"]],
        materiais_ids=[material["id"]],
    )
    estatico["id"] = "00000000-0000-4000-8000-000000000104"

    entradas_sens = {"sigma_x_MPa": 120.0, "sigma_y_MPa": 30.0, "tau_xy_MPa": 25.0, "Sy_MPa": 285.0}
    configuracao = {
        "sigma_x_MPa": {"incerteza_percentual": 8.0, "distribuicao": "Uniforme"},
        "sigma_y_MPa": {"incerteza_percentual": 8.0, "distribuicao": "Uniforme"},
        "tau_xy_MPa": {"incerteza_percentual": 10.0, "distribuicao": "Uniforme"},
        "Sy_MPa": {"incerteza_percentual": 5.0, "distribuicao": "Normal"},
    }
    oat = analisar_oat("seguranca_vm", entradas_sens, variacao_percentual=10.0)
    mc = analisar_monte_carlo(
        "seguranca_vm",
        entradas_sens,
        configuracao,
        amostras=3_000,
        semente=42,
        criterio={"ativo": True, "operador": ">=", "limite": 1.5},
    )
    governante = oat["ranking"][0]
    sensibilidade = criar_registro_tecnico(
        modulo="Análise de sensibilidade",
        titulo="Robustez do fator de segurança em P1",
        status="Atende",
        resumo="OAT local e Monte Carlo sobre tensões e limite de escoamento.",
        metodo="OAT ±10%; 3.000 amostras Monte Carlo; semente 42; entradas independentes.",
        equacoes=["n = Sy / σvm"],
        criterios=["n ≥ 1,50; probabilidade de não atendimento ≤ 5%"],
        incertezas=configuracao,
        entradas={**entradas_sens, "incertezas": configuracao, "registro_origem": estatico["id"]},
        resultados={
            "saida_nominal": oat["saida_nominal"],
            "unidade_saida": "-",
            "variavel_governante": governante["variavel"],
            "impacto_governante_pct": governante["impacto_percentual"],
            "p05": mc["p05"],
            "p50": mc["p50"],
            "p95": mc["p95"],
            "probabilidade_nao_atendimento_pct": mc["probabilidade_nao_atendimento_pct"],
            "ranking_sensibilidade": [
                {chave: item[chave] for chave in ("variavel", "impacto_percentual", "elasticidade", "direcao_critica")}
                for item in oat["ranking"]
            ],
            "correlacoes_spearman": mc["correlacoes_spearman"],
        },
        premissas=["Faixas definidas para demonstração; substituir por dados metrológicos e históricos do projeto real.", "Entradas tratadas como independentes."],
        alertas=[],
        referencias=["Registro estático P1", "Plano de incertezas PI-SK101-001"],
        conclusao=(
            f"{governante['variavel']} governa localmente; risco estimado de não atendimento = "
            f"{mc['probabilidade_nao_atendimento_pct']:.2f}% para o critério n ≥ 1,50."
        ),
        responsavel="Engenheiro responsável",
        casos_carga_ids=[caso_operacional["id"], caso_termico["id"]],
        componentes_ids=[componente["id"]],
        materiais_ids=[material["id"]],
    )
    sensibilidade["id"] = "00000000-0000-4000-8000-000000000105"
    projeto["registros_tecnicos"] = [registro_cargas, estatico, sensibilidade]
    checklist = criar_item(
            item="Conferência independente das entradas e da origem do material",
            categoria="Emissão",
            responsavel="Engenheiro verificador",
            prazo="Antes da emissão",
            estado="Concluído",
            evidencia="LV-SK101-002",
            critico=True,
        )
    checklist["id"] = "00000000-0000-4000-8000-000000000106"
    projeto["checklist"] = [checklist]
    return projeto


def main() -> None:
    projeto = montar_exemplo()
    pasta_docx = RAIZ / "output" / "docx"
    pasta_pdf = RAIZ / "output" / "pdf"
    pasta_docx.mkdir(parents=True, exist_ok=True)
    pasta_pdf.mkdir(parents=True, exist_ok=True)
    metadata = {
        "titulo": "Memorial unificado de cálculo industrial",
        "subtitulo": "Escopo, materiais, cálculos, sensibilidade, validação e aprovações",
        "codigo": "MC-SK101-001",
        "revisao": "00",
        "responsavel": projeto["responsavel"],
        "verificador": projeto["verificador"],
        "aprovador": projeto["aprovador"],
        "situacao": "Exemplo para revisão",
        "emissao": "14/08/2026",
    }
    ordem = [item["id"] for item in projeto["registros_tecnicos"]]
    (pasta_docx / "memorial_unificado_industrial_exemplo.docx").write_bytes(
        gerar_relatorio_industrial_word(projeto, registros_ids=ordem, metadata_extra=metadata)
    )
    (pasta_pdf / "memorial_unificado_industrial_exemplo.pdf").write_bytes(
        gerar_relatorio_industrial_pdf(projeto, registros_ids=ordem, metadata_extra=metadata)
    )


if __name__ == "__main__":
    main()
