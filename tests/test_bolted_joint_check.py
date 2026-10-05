"""Critérios de aceite da ligação parafusada estrutural, pelas funções do próprio app.

Os mesmos valores esperados de ``test_bolted_connection.py`` (módulo de fórmulas), agora
passando por ``verificar_ligacao`` — a função que a página chama. Fontes: AISC Design
Guide 29 (págs. 157–159 e 185–186) e o caso real da planilha validada (emenda de perfis U,
t = 5,08 mm, A36, 2 × 2 parafusos, e = s = g = 70 mm, 32 kN característico, γ_f = 1,4).
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from core import bolted_connection as bc
from core import bolted_joint_check as chk
from core.verificacao import (
    COLUNAS_TABELA,
    csv_verificacoes,
    linhas_para_registro,
    tabela_verificacoes,
)

KIP = bc.KIP_KN


def perto(a: float, b: float, rel: float = 0.01) -> bool:
    return abs(a - b) <= rel * abs(b)


def linha(resultado: chk.ResultadoLigacao, trecho: str) -> bc.Verificacao:
    achadas = [v for v in resultado.verificacoes if trecho in v.nome]
    assert len(achadas) == 1, f"{trecho!r}: {[v.nome for v in resultado.verificacoes]}"
    return achadas[0]


def tem_linha(resultado: chk.ResultadoLigacao, trecho: str) -> bool:
    return any(trecho in v.nome for v in resultado.verificacoes)


# ------------------------------------------------------------------ caso real, NBR 8800:2008
def cortante_excentrica(**mudancas) -> chk.EntradaLigacao:
    base = dict(designacao="M22", V=32.0, excentricidade_mm=105.0)
    base.update(mudancas)
    return chk.EntradaLigacao(**base)


def test_excentricidade_padrao_de_emenda():
    assert chk.excentricidade_emenda(70.0, 70.0, 2) == 105.0
    assert chk.excentricidade_emenda(70.0, 70.0, 3) == 140.0


def test_forca_no_parafuso_critico_elu_e_servico():
    r = chk.verificar_ligacao(cortante_excentrica())
    assert perto(r.forcas["J_mm2"], 9800, 1e-6)
    assert perto(r.forcas["R_max_ELU_kN"], 32.65, 0.002)
    assert perto(r.forcas["R_max_ELS_kN"], 23.32, 0.002)
    assert perto(r.forcas["V_Sd_kN"], 44.8, 1e-9) and perto(r.forcas["M_Sd_kNm"], 4.704, 1e-9)


def test_m22_resistencia_por_parafuso_41_por_cento():
    v = linha(chk.verificar_ligacao(cortante_excentrica()), "Parafuso crítico")
    assert perto(v.resistente, 79.47, 0.002) and perto(v.solicitante, 32.65, 0.002)
    assert perto(v.aproveitamento, 0.41, 0.01) and v.status == "OK"


def test_m22_corte_e_contato_separados():
    r = chk.verificar_ligacao(cortante_excentrica())
    assert perto(r.resistencias["F_v_Rd_kN"], 92.9, 0.002)
    assert perto(r.resistencias["F_c_Rd_critico_kN"], 79.5, 0.002)


def test_m22_deslizamento_83_por_cento():
    v = linha(chk.verificar_ligacao(cortante_excentrica()), "Deslizamento")
    assert perto(v.resistente, 28.16, 0.002) and perto(v.solicitante, 23.32, 0.002)
    assert perto(v.aproveitamento, 0.83, 0.01) and v.status == "OK"


def test_m16_deslizamento_160_por_cento_nao_ok():
    v = linha(chk.verificar_ligacao(cortante_excentrica(designacao="M16")), "Deslizamento")
    assert perto(v.resistente, 14.56, 0.002)
    assert perto(v.aproveitamento, 1.60, 0.01) and v.status == "NÃO OK"


def test_borda_70_mm_reprova_e_60_mm_passa():
    nome = "Distância máxima à borda (na direção da força)"
    assert linha(chk.verificar_ligacao(cortante_excentrica()), nome).status == "NÃO OK"
    r60 = chk.verificar_ligacao(cortante_excentrica(e=60.0))
    assert linha(r60, nome).status == "OK"


def axial_m16(**mudancas) -> chk.EntradaLigacao:
    base = dict(
        designacao="M16",
        N=44.8,
        valores_sao_de_calculo=True,
        A_g=1542.0,
        e_c=13.0,
        peca_por_esbeltez=True,
    )
    base.update(mudancas)
    return chk.EntradaLigacao(**base)


def test_axial_m16_grupo_soma_por_furo():
    r = chk.verificar_ligacao(axial_m16())
    v = linha(r, "Grupo de parafusos")
    assert perto(v.resistente, 196.6, 0.002) and perto(v.solicitante, 44.8, 1e-9)
    assert perto(r.resistencias["F_v_Rd_kN"], 49.15, 0.002)
    assert perto(r.resistencias["F_c_Rd_interno_kN"], 57.80, 0.002)


def test_peca_u6_tracao_e_colapso_por_rasgamento():
    r = chk.verificar_ligacao(axial_m16())
    assert perto(linha(r, "Tração da peça").resistente, 323.0, 0.002)
    assert perto(linha(r, "Colapso por rasgamento").resistente, 233.3, 0.002)
    assert perto(r.intermediarios["C_t"], 1 - 13 / 70, 1e-9)


def test_regra_dos_75_por_cento_anglo_nao_ok():
    r = chk.verificar_ligacao(axial_m16())
    v = linha(r, "75%")
    assert v.status == "NÃO OK"
    assert perto(v.solicitante, 242.3, 0.002) and perto(v.resistente, 196.6, 0.002)
    assert r.status_geral == "NÃO OK"


def test_regra_dos_75_nao_se_aplica_sem_o_marcador():
    r = chk.verificar_ligacao(axial_m16(peca_por_esbeltez=False))
    assert not tem_linha(r, "75%")


def test_servico_do_deslizamento_vem_do_caracteristico():
    # N_Sd = 44,8 de cálculo → 32 kN característicos → 8 kN por parafuso em serviço
    r = chk.verificar_ligacao(axial_m16())
    assert perto(linha(r, "Deslizamento").solicitante, 8.0, 1e-9)
    ref = chk.verificar_ligacao(axial_m16(N=32.0, valores_sao_de_calculo=False))
    assert perto(ref.forcas["N_Sd_kN"], 44.8, 1e-9)
    assert perto(linha(ref, "Deslizamento").solicitante, 8.0, 1e-9)


def test_torque_e_so_referencia_de_instalacao():
    r = chk.verificar_ligacao(cortante_excentrica())
    v = linha(r, "torque")
    assert v.status == "INFO" and v.aproveitamento is None
    assert perto(r.torque_referencia_Nm, 0.20 * 176 * 1000 * 22.0 / 1000, 1e-9)


# ------------------------------------------------------------------ DG29 pelas funções do app
def dg29(designacao: str, d_h_mm: float | None, g: float = 70.3) -> chk.EntradaLigacao:
    return chk.EntradaLigacao(
        norma="AISC360_LRFD",
        designacao=designacao,
        d_h_mm=d_h_mm,
        N=100.0,
        valores_sao_de_calculo=True,
        t=9.525,
        n_lin=2,
        n_col=5,
        s=76.2,
        g=g,
        e=31.75,
        ligacao_por_atrito=False,
        A_g=None,
    )


def test_dg29_1_pol_pelo_app():
    r = chk.verificar_ligacao(dg29('1"', 27.0))
    assert perto(r.resistencias["F_v_Rd_kN"] / KIP, 31.8)
    assert perto(r.resistencias["F_c_Rd_interno_kN"] / KIP, 38.0)
    assert perto(r.resistencias["F_c_Rd_extremidade_kN"] / KIP, 14.1)
    assert perto(r.resistencias["R_grupo_axial_kN"] / KIP, 283.0)
    assert perto(r.resistencias["F_r_Rd_kN"] / KIP, 187.0)
    assert perto(linha(r, "Grupo de parafusos").resistente / KIP, 283.0)


def test_dg29_7_8_pelo_app():
    r = chk.verificar_ligacao(dg29('7/8"', None))
    assert perto(r.resistencias["F_v_Rd_kN"] / KIP, 24.3)
    assert perto(r.resistencias["F_c_Rd_interno_kN"] / KIP, 34.3)
    assert perto(r.resistencias["F_c_Rd_extremidade_kN"] / KIP, 15.3)


def test_furo_do_aisc_360_10_difere_da_tabela_do_360_16():
    tabela = chk.verificar_ligacao(dg29('1"', None))
    assert not perto(tabela.resistencias["F_c_Rd_interno_kN"] / KIP, 38.0, 0.01)


# ------------------------------------------------------------------ casos sinalizados, nunca silenciosos
def test_lf_nao_positivo_e_sinalizado():
    r = chk.verificar_ligacao(cortante_excentrica(e=10.0))
    v = linha(r, "ℓ_f > 0")
    assert v.status == "NÃO OK" and "ℓ_f ≤ 0" in v.formula
    assert linha(r, "Parafuso crítico").status == "NÃO OK"


def test_n_col_1_deixa_ct_indefinido_com_alerta():
    r = chk.verificar_ligacao(axial_m16(n_col=1, n_lin=2, peca_por_esbeltez=False))
    v = linha(r, "Tração da peça")
    assert v.status == "ALERTA" and "C_t indefinido" in v.formula
    assert "N_t_Rd_kN" not in r.resistencias


def test_a307_em_ligacao_por_atrito_nao_ok():
    r = chk.verificar_ligacao(cortante_excentrica(grau="A307"))
    v = linha(r, "Deslizamento")
    assert v.status == "NÃO OK" and "protensão" in v.formula
    assert r.torque_referencia_Nm is None


@pytest.mark.parametrize("norma", ["AISC360_LRFD", "RCSC2004"])
def test_superficie_sem_mu_na_norma_e_sinalizada(norma):
    r = chk.verificar_ligacao(cortante_excentrica(norma=norma))
    v = linha(r, "Deslizamento")
    assert v.status == "NÃO OK" and "sem μ" in v.formula


def test_rcsc_nao_cobre_a307():
    r = chk.verificar_ligacao(cortante_excentrica(norma="RCSC2004", grau="A307"))
    assert r.status_geral == "NÃO OK"
    assert "não cobre A307" in r.verificacoes[0].formula


def test_um_parafuso_nao_resiste_a_momento():
    r = chk.verificar_ligacao(cortante_excentrica(n_lin=1, n_col=1))
    assert linha(r, "Momento no grupo").status == "NÃO OK"


def test_sem_atrito_marca_alerta_e_nao_calcula_deslizamento():
    r = chk.verificar_ligacao(cortante_excentrica(ligacao_por_atrito=False))
    assert not tem_linha(r, "Deslizamento")
    assert linha(r, "sem atrito").status == "ALERTA"


def test_condicoes_fora_do_escopo_viram_alerta():
    r = chk.verificar_ligacao(
        cortante_excentrica(e=60.0, fora_do_escopo=("fadiga", "furo_alargado"))
    )
    avisos = [v for v in r.verificacoes if "fora do escopo" in v.nome]
    assert len(avisos) == 2 and all(v.status == "ALERTA" for v in avisos)
    assert r.status_geral == "ALERTA"


def test_sem_esforco_so_verifica_disposicoes():
    r = chk.verificar_ligacao(chk.EntradaLigacao(e=60.0))
    assert linha(r, "Esforços da ligação").status == "INFO"
    assert not tem_linha(r, "Parafuso crítico") and not tem_linha(r, "Grupo de parafusos")


def test_tracao_da_peca_sem_dados_e_alerta_e_regra_75_sem_dados_tambem():
    r = chk.verificar_ligacao(axial_m16(A_g=None, e_c=None))
    assert linha(r, "Tração da peça").status == "ALERTA"
    assert linha(r, "75%").status == "ALERTA"


def test_coordenadas_livres_equivalem_a_grade():
    grade = chk.verificar_ligacao(cortante_excentrica(e=60.0))
    livres = chk.verificar_ligacao(
        cortante_excentrica(
            e=60.0,
            coordenadas=tuple((float(x), float(y)) for x, y in bc.grade_retangular(2, 2, 70, 70)),
        )
    )
    assert perto(livres.forcas["R_max_ELU_kN"], grade.forcas["R_max_ELU_kN"], 1e-9)
    assert perto(
        linha(livres, "Parafuso crítico").resistente, linha(grade, "Parafuso crítico").resistente
    )


def test_entradas_invalidas_levantam_erro():
    for mudanca in (
        {"norma": "XYZ"},
        {"designacao": "M99"},
        {"t": 0.0},
        {"gama_f": 0.9},
        {"n_planos": 0},
        {"d_h_mm": 5.0},
        {"N": math.nan},
    ):
        with pytest.raises(ValueError):
            chk.verificar_ligacao(cortante_excentrica(**mudanca))


# ------------------------------------------------------------------ resumo, varreduras e tabelas
def test_resumo_aponta_a_verificacao_governante():
    r = chk.verificar_ligacao(cortante_excentrica())
    assert r.status_geral == "NÃO OK"
    assert "borda" in r.governante and perto(r.aproveitamento_max, 70.0 / 60.96, 1e-6)


def test_menor_parafuso_que_atende_na_emenda_com_borda_de_60_mm():
    entrada = cortante_excentrica(e=60.0)
    varredura = chk.testar_todos_parafusos(entrada)
    assert [x["d_b_mm"] for x in varredura] == sorted(x["d_b_mm"] for x in varredura)
    assert len(varredura) == len(bc.PARAFUSOS)
    assert chk.menor_parafuso_que_atende(entrada) == "M22"
    reprovados = {x["designacao"] for x in varredura if not x["atende"]}
    assert {"M16", "M20"} <= reprovados  # não passam no deslizamento


def test_comparar_normas_traz_as_quatro():
    tabela = chk.comparar_normas(cortante_excentrica(e=60.0, superficie="classe_B_jateada"))
    assert [x["norma"] for x in tabela] == list(bc.NORMAS)
    assert all(x["status"] in ("OK", "ALERTA", "NÃO OK") for x in tabela)
    nbr08 = tabela[0]
    assert perto(nbr08["F_v_Rd_kN"], 92.9, 0.002) and nbr08["erro"] == ""
    assert tabela[1]["F_v_Rd_kN"] > nbr08["F_v_Rd_kN"]  # projeto 2024: α_v 0,45 e f_ub 830


def test_comparar_normas_mostra_o_erro_em_vez_de_esconder():
    tabela = chk.comparar_normas(cortante_excentrica(grau="A307", e=60.0, ligacao_por_atrito=False))
    rcsc = tabela[3]
    assert rcsc["status"] == "NÃO OK"


def test_tabela_tem_as_oito_colunas_e_status_validos():
    r = chk.verificar_ligacao(axial_m16())
    tabela = tabela_verificacoes(r.verificacoes)
    assert len(tabela) == len(r.verificacoes) > 8
    for linha_ in tabela:
        assert tuple(linha_) == COLUNAS_TABELA
        assert linha_["Status"] in {"OK", "NÃO OK", "ALERTA", "N/A", "INFO"}
        assert linha_["Referência"] and linha_["Verificação"]
    registro = linhas_para_registro(r.verificacoes)
    assert len(registro[0]) == 8 and all(x["referência"] for x in registro)


def test_resistencia_negativa_reprova_em_vez_de_passar():
    v = bc.Verificacao("x", 10.0, -5.0, "kN", "ref")
    assert v.status == "NÃO OK" and math.isinf(v.aproveitamento)


def test_entrada_e_imutavel_e_a_varredura_nao_a_altera():
    entrada = cortante_excentrica(e=60.0)
    chk.testar_todos_parafusos(entrada)
    assert entrada == replace(entrada)
    assert entrada.designacao == "M22"


# ------------------------------------------------------------------ CSV, registro e memorial
def test_csv_tem_as_oito_colunas_e_as_grandezas():
    import csv
    import io

    r = chk.verificar_ligacao(cortante_excentrica())
    texto = csv_verificacoes(r.verificacoes).decode("utf-8-sig")
    linhas = list(csv.reader(io.StringIO(texto)))
    assert linhas[0] == [
        "Verificação",
        "Solicitante",
        "Resistente",
        "Unidade",
        "Aproveitamento (%)",
        "Status",
        "Fórmula",
        "Referência",
    ]
    assert len(linhas) == len(r.verificacoes) + 1
    critico = next(x for x in linhas if x[0].startswith("Parafuso crítico"))
    assert critico[1] == "32.653" and critico[2] == "79.474" and critico[5] == "OK"
    assert all(x[6] and x[7] for x in linhas[1:])  # fórmula e referência nunca vazias


def test_registro_traz_a_tabela_a_utilizacao_e_resiste_ao_hash_com_infinito():
    entrada = cortante_excentrica(e=10.0)  # ℓ_f ≤ 0 → aproveitamento infinito
    resultado = chk.verificar_ligacao(entrada)
    registro = chk.registro_ligacao(entrada, resultado, None)
    assert registro["status"] == "Não atende" and registro["hash_calculo"]
    assert registro["modulo_id"] == "projeto_parafusos"
    tabela_registro = registro["resultados"]["verificações"]
    assert len(tabela_registro) == len(resultado.verificacoes)
    assert any(x["aproveitamento_pct"] == "∞" for x in tabela_registro)
    assert "utilizacao_maxima" not in registro["resultados"]  # infinito não vira número
    ok = chk.registro_ligacao(
        cortante_excentrica(e=60.0),
        chk.verificar_ligacao(cortante_excentrica(e=60.0)),
        "M20",
    )
    assert ok["status"] == "Atende" and 0 < ok["resultados"]["utilizacao_maxima"] <= 1
    assert ok["resultados"]["menor_parafuso_que_atende"] == "M20"


def test_memorial_word_e_pdf_imprimem_a_tabela_de_verificacoes():
    from io import BytesIO

    from docx import Document
    from pypdf import PdfReader

    from core.project_report import (
        gerar_relatorio_industrial_pdf,
        gerar_relatorio_industrial_word,
        montar_modelo_relatorio,
    )
    from core.technical_records import normalizar_registro_tecnico
    from tests.test_project_validation import _projeto_documentado

    entrada = cortante_excentrica()
    resultado = chk.verificar_ligacao(entrada)
    projeto = _projeto_documentado()
    projeto["registros_tecnicos"] = [
        normalizar_registro_tecnico(chk.registro_ligacao(entrada, resultado, None))
    ]

    modelo = montar_modelo_relatorio(projeto, secoes_incluidas=["registros"])
    tabelas = [t for s in modelo["secoes"] for t in s.get("tabelas", [])]
    verificacoes = next(t for t in tabelas if "Verificações" in t["legenda"])
    assert verificacoes["cabecalhos"] == [
        "Verificação",
        "Solicitante",
        "Resistente",
        "Unidade",
        "Aproveitamento [%]",
        "Status",
        "Fórmula",
        "Referência",
    ]
    assert len(verificacoes["linhas"]) == len(resultado.verificacoes)

    pdf = gerar_relatorio_industrial_pdf(projeto, secoes_incluidas=["registros"])
    texto_pdf = "\n".join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    for trecho in ("Deslizamento", "Aproveitamento", "NBR 6.3.4.4", "Fórmula", "NÃO OK"):
        assert trecho in texto_pdf

    word = Document(
        BytesIO(gerar_relatorio_industrial_word(projeto, secoes_incluidas=["registros"]))
    )
    textos_word = " ".join(c.text for t in word.tables for linha in t.rows for c in linha.cells)
    assert "Deslizamento (ELS" in textos_word and "NBR 6.3.4.4" in textos_word
