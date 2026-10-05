"""A página Flambagem de colunas, exercitada pela interface (AppTest).

Reproduz na tela os casos de aceite do pedido de robustecimento — barra circular Ø50, HSS8×8×1/2
do AISC Design Guide 29, U idealizado, interação biaxial, esbeltez 201 e U laminado de 4,5 mm —
e confere o que a página promete: todos os eixos e modos numa rodada, três normas, bloqueios que
viram linhas NÃO OK, seção genérica que nunca fica OK sem confirmação, mão-francesa com alerta de
cisalhamento, tabela de oito colunas, CSV, comparação de normas e registro no projeto.
"""

from __future__ import annotations

import re

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from components import column_ui as ui
from core import column_buckling as cb
from core import column_design as cd
from core import section_catalog as catalogo
from core.project_store import obter_projeto_ativo
from core.verificacao import COLUNAS_TABELA

PAGINA = "app_pages/flambagem_colunas.py"
KSI, INCH, KIP = 6.894757, 25.4, 4.448222


def abrir(banco_isolado, **estado) -> AppTest:
    teste = AppTest.from_file("app.py", default_timeout=180)
    teste.run()
    teste.switch_page(PAGINA)
    for chave, valor in estado.items():
        teste.session_state[chave] = valor
    teste.run()
    assert not teste.exception, [str(e.value) for e in teste.exception]
    return teste


def tabela(teste: AppTest) -> pd.DataFrame:
    """Tabela de verificações como a tela a mostra (números em texto; “—” = sem valor)."""
    achadas = [d.value for d in teste.dataframe if "Verificação" in d.value.columns]
    assert achadas, "a tabela de verificações não apareceu"
    df = achadas[0].copy()
    for coluna in ("Solicitante", "Resistente", "Aproveitamento"):
        df[coluna] = pd.to_numeric(df[coluna].replace("—", None), errors="coerce")
    return df


def linha(teste: AppTest, trecho: str) -> pd.Series:
    df = tabela(teste)
    achadas = df[df["Verificação"].str.contains(trecho, regex=False)]
    assert len(achadas) == 1, (trecho, list(df["Verificação"]))
    return achadas.iloc[0]


def tem_linha(teste: AppTest, trecho: str) -> bool:
    return bool(tabela(teste)["Verificação"].str.contains(trecho, regex=False).any())


def metrica(teste: AppTest, rotulo: str) -> str:
    return next(m.value for m in teste.metric if m.label == rotulo)


def tem_metrica(teste: AppTest, rotulo: str) -> bool:
    return any(m.label == rotulo for m in teste.metric)


def numero(texto: str) -> float:
    return float(texto.split()[0].rstrip("%"))


def selo(teste: AppTest) -> str:
    """Status geral do selo (``st.badge`` chega ao AppTest como markdown ``:cor-badge[...]``)."""
    for m in teste.markdown:
        achado = re.search(r"badge\[.*Status geral: (.+?)\]$", m.value)
        if achado:
            return achado.group(1)
    raise AssertionError("o selo do status geral não apareceu")


# ------------------------------------------------------------------ casos de aceite
def test_barra_circular_50_com_os_padroes_da_pagina(banco_isolado):
    t = abrir(banco_isolado)
    assert tuple(tabela(t).columns) == COLUNAS_TABELA
    assert metrica(t, "N_c,Rd") == "120.71 kN"
    assert metrica(t, "N_Sd") == "72.00 kN"  # 1,40·30 + 1,50·20
    assert metrica(t, "Aproveitamento máximo") == "60%"
    assert metrica(t, "λx = Kx·Lx/rx") == "160.0" and metrica(t, "λy = Ky·Ly/ry") == "160.0"
    assert metrica(t, "N_e adotado") == "151.4 kN" and metrica(t, "χ") == "0.270"
    assert selo(t) == "OK"
    limite = linha(t, "Esbeltez limite")
    assert limite["Solicitante"] == pytest.approx(160.0) and limite["Status"] == "OK"
    assert any("N_Sd = 1.40 × 30.0 + 1.50 × 20.0 = **72.00 kN**" in c.value for c in t.caption)


def test_hss_8x8x1_2_do_design_guide_29(banco_isolado):
    espessura = 0.465 * INCH
    area, raio = 13.5 * INCH**2, 3.04 * INCH
    t = abrir(
        banco_isolado,
        col_norma="AISC360_16_LRFD",
        col_tipo_secao=ui.SEC_GENERICA,
        col_gen_A=area,
        col_gen_Ix=area * raio**2,
        col_gen_Iy=area * raio**2,
        col_gen_torcao=False,
        col_gen_npar=1,
        col_par_tipo_1="AA · grupo 1 — parede de tubo retangular",
        col_par_b_1=14.2 * espessura,
        col_par_t_1=espessura,
        col_par_n_1=4,
        col_confirma=True,
        col_fy_manual=46 * KSI,
        col_E=29_000 * KSI,
        col_L=24 * 12 * INCH,
        col_modo_carga=ui.MODO_CALCULO,
        col_nsd=1000.0,
    )
    resistencia = numero(metrica(t, "N_c,Rd"))
    assert resistencia / KIP == pytest.approx(306.0, rel=5e-3)
    assert resistencia == pytest.approx(1361.0, rel=5e-3)
    assert metrica(t, "A_ef/A_g") == "1.000"  # b/t = 14,2 < 1,40·√(E/F_y)
    assert metrica(t, "Fator φ") == "0.90" and not tem_metrica(t, "Fator 1/γ_a1")
    assert selo(t) == "OK"


def test_u_idealizado_a36_mostra_todos_os_modos(banco_isolado):
    t = abrir(
        banco_isolado,
        col_tipo_secao=ui.SEC_U,
        col_mesmo_L=False,
        col_Lx=3000.0,
        col_Ly=1500.0,
        col_kz_ativar=True,
        col_Kz=1.0,
        col_Lz=3000.0,
    )
    assert numero(metrica(t, "N_e adotado")) == pytest.approx(308.4, rel=1e-3)
    assert numero(metrica(t, "N_c,Rd")) == pytest.approx(207.3, rel=1e-3)
    assert linha(t, "N_e flexo-torção xz")["Resistente"] == pytest.approx(457.4, rel=1e-3)
    for trecho in ("N_ex", "N_ey", "N_ez", "N_e adotado"):
        assert tem_linha(t, trecho), trecho
    assert any("governa" in m.proto.help and "flexão y" in m.proto.help for m in t.metric)


def test_interacao_biaxial_na_tela_reprova_o_que_eixo_a_eixo_aprovaria(banco_isolado):
    base = dict(
        col_tipo_secao=ui.SEC_GENERICA,
        col_gen_A=5_000.0,
        col_gen_Ix=1e8,
        col_gen_Iy=1e8,
        col_gen_torcao=False,
        col_confirma=True,
        col_L=1000.0,
        col_modo_carga=ui.MODO_CALCULO,
        col_mrd_x_ativar=True,
        col_mrd_x=100.0,
        col_mrd_y_ativar=True,
        col_mrd_y=100.0,
    )
    n_rd = numero(metrica(abrir(banco_isolado, **base, col_nsd=0.0), "N_c,Rd"))
    comum = dict(base, col_nsd=round(0.3 * n_rd, 2))
    so_x = abrir(banco_isolado, **comum, col_Mx=50.0)
    so_y = abrir(banco_isolado, **comum, col_My=40.0)
    juntos = abrir(banco_isolado, **comum, col_Mx=50.0, col_My=40.0)
    assert numero(metrica(so_x, "Índice de interação")) < 0.75
    assert numero(metrica(so_y, "Índice de interação")) < 0.66
    assert numero(metrica(juntos, "Índice de interação")) == pytest.approx(1.10, rel=3e-3)
    assert linha(juntos, "Interação")["Status"] == "NÃO OK" and selo(juntos) == "NÃO OK"
    assert "Interação" in next(
        m.value for m in juntos.markdown if m.value.startswith("**Verificação que governa")
    )


@pytest.mark.parametrize(("esbeltez", "status"), [(199.0, "OK"), (200.0, "OK"), (201.0, "NÃO OK")])
def test_limite_de_esbeltez_da_anglo_na_tela(banco_isolado, esbeltez, status):
    t = abrir(banco_isolado, col_circ_d=20.0, col_L=esbeltez * 5.0, col_ng=0.1, col_nq=0.0)
    assert linha(t, "Esbeltez limite")["Status"] == status
    assert selo(t) == status


def test_u_laminado_de_4_5_mm_reprova_na_espessura_minima(banco_isolado):
    t = abrir(banco_isolado, col_tipo_secao=ui.SEC_U, col_U_tw=4.5)
    espessura = linha(t, "Espessura mínima")
    assert espessura["Status"] == "NÃO OK" and "laminado L/U" in espessura["Verificação"]
    assert espessura["Referência"] == "Anglo 8.8"
    assert selo(t) == "NÃO OK"
    ok = abrir(banco_isolado, col_tipo_secao=ui.SEC_U, col_U_tw=5.08)
    assert linha(ok, "Espessura mínima")["Status"] == "OK"


# ------------------------------------------------------------------ bloqueios e alertas
def test_tubo_circular_muito_fino_bloqueia_e_nao_estima(banco_isolado):
    t = abrir(banco_isolado, col_tipo_secao=ui.SEC_TUBO_C, col_tc_D=200.0, col_tc_t=0.5)
    assert any("D/t > 0,45" in e.value for e in t.error)
    assert selo(t) == "NÃO OK"
    assert not tem_metrica(t, "N_c,Rd") and not tem_linha(t, "Compressão axial")
    assert (tabela(t)["Status"] == "NÃO OK").any()


def test_geometria_impossivel_vira_erro_de_campo(banco_isolado):
    t = abrir(banco_isolado, col_tipo_secao=ui.SEC_TUBO_C, col_tc_D=20.0, col_tc_t=12.0)
    assert any("metade do diâmetro" in e.value for e in t.error)
    assert not tem_metrica(t, "N_c,Rd")


def test_secao_sem_paredes_nunca_fica_ok_sem_confirmacao(banco_isolado):
    t = abrir(banco_isolado, col_tipo_secao=ui.SEC_DIRETA)
    assert selo(t) == "ALERTA"
    assert linha(t, "Flambagem local não verificada")["Status"] == "ALERTA"
    assert linha(t, "Torção e flexo-torção não verificadas")["Status"] == "ALERTA"
    confirmada = abrir(banco_isolado, col_tipo_secao=ui.SEC_DIRETA, col_confirma=True)
    assert selo(confirmada) == "OK"
    assert linha(confirmada, "confirmado")["Status"] == "INFO"


def test_tubo_nao_compacto_na_flexao_pede_mrd_informado(banco_isolado):
    estado = dict(col_tipo_secao=ui.SEC_TUBO_C, col_tc_D=200.0, col_tc_t=2.5, col_Mx=2.0)
    t = abrir(banco_isolado, **estado)
    assert linha(t, "Flexão em x não calculada")["Status"] == "NÃO OK"
    assert not tem_metrica(t, "Índice de interação")
    liberado = abrir(banco_isolado, **estado, col_mrd_x_ativar=True, col_mrd_x=30.0)
    assert linha(liberado, "informado pelo usuário")["Resistente"] == pytest.approx(30.0)
    assert tem_metrica(liberado, "Índice de interação")


def test_nsd_acima_de_ne_bloqueia_o_b1(banco_isolado):
    t = abrir(banco_isolado, col_modo_carga=ui.MODO_CALCULO, col_nsd=200.0, col_Mx=1.0)
    assert linha(t, "Amplificação B₁ em x")["Status"] == "NÃO OK"
    assert any("N_Sd1 ≥ N_e" in e.value for e in t.error)


def test_perfil_formado_a_frio_do_catalogo_e_alertado(banco_isolado):
    t = abrir(
        banco_isolado,
        col_tipo_secao=ui.SEC_CATALOGO,
        col_perfil="C ideal 100×50×17×2.65",
        col_modo_carga=ui.MODO_CALCULO,
        col_nsd=5.0,
    )
    assert linha(t, "Seção fora do escopo")["Status"] == "ALERTA"
    assert selo(t) == "ALERTA"


# ------------------------------------------------------------------ normas
def test_catalogo_bate_com_o_nucleo_nas_tres_normas(banco_isolado):
    nome = "W 310 x 44,5"
    secao = cb.secao_de_perfil(catalogo.obter_perfil(nome))
    for norma in cb.NORMAS:
        t = abrir(
            banco_isolado,
            col_tipo_secao=ui.SEC_CATALOGO,
            col_perfil=nome,
            col_norma=norma,
            col_L=4000.0,
        )
        esperado = cb.verificar_coluna(
            cb.EntradaColuna(
                secao=secao, fy_MPa=250.0, norma=norma, Lx_mm=4000.0, Ly_mm=4000.0, N_Sd_kN=72.0
            )
        ).compressao
        assert esperado is not None
        assert numero(metrica(t, "N_c,Rd")) == pytest.approx(esperado["Nc_Rd"], abs=0.006)
        assert tem_metrica(t, "Q = Q_s·Q_a") == (norma == "NBR8800_2008")
        assert tem_metrica(t, "A_ef/A_g") == (norma != "NBR8800_2008")
        assert selo(t) == "OK"


def test_comparar_normas_mostra_as_tres(banco_isolado):
    t = abrir(banco_isolado, col_tipo_secao=ui.SEC_I, col_L=4000.0)
    assert t.button(key="col_btn_comparar").click().run() is not None
    comparacao = next(d.value for d in t.dataframe if "Norma" in d.value.columns)
    assert list(comparacao["Norma"]) == [cb.NORMAS_ROTULOS[n] for n in cb.NORMAS]
    assert set(comparacao["Status"]) <= {"OK", "NÃO OK", "ALERTA"}
    assert "—" not in set(comparacao["N_c,Rd (kN)"])


def test_regras_ficam_a_vista_abaixo_da_tabela(banco_isolado):
    t = abrir(banco_isolado)
    textos = [m.value for m in t.markdown]
    assert any("N_e é calculado com o comprimento real" in x for x in textos)
    assert any("Perfil soldado: 4,75 mm" in x and "Placa de base: 16 mm" in x for x in textos)
    flt = next(x for x in textos if "FLT na NBR 8800:2008" in x)
    assert "- **FLT na NBR 8800:2008" in flt and "- FLT no Projeto 2024" in flt
    outra = abrir(banco_isolado, col_norma="NBR8800_2024")
    flt_2024 = next(m.value for m in outra.markdown if "FLT no Projeto 2024" in m.value)
    assert "- **FLT no Projeto 2024" in flt_2024 and "- FLT na NBR 8800:2008" in flt_2024


def test_geometria_idealizada_avisa_em_i_e_u_por_dimensoes(banco_isolado):
    laminado = abrir(banco_isolado, col_tipo_secao=ui.SEC_U)
    assert any(
        "Geometria idealizada" in w.value and "catálogo" in w.value for w in laminado.warning
    )
    soldado = abrir(banco_isolado, col_tipo_secao=ui.SEC_U, col_soldado_U=True)
    assert not any("Geometria idealizada" in w.value for w in soldado.warning)
    assert any("Geometria idealizada" in c.value for c in soldado.caption)
    catalogo_ = abrir(banco_isolado, col_tipo_secao=ui.SEC_CATALOGO)
    assert not any("Geometria idealizada" in w.value for w in catalogo_.warning)


def test_k_diferente_de_1_avisa_nas_normas_de_analise_direta(banco_isolado):
    base = dict(col_tipo_secao=ui.SEC_I, col_apoio_x="Biengastada", col_apoio_y="Biengastada")

    def avisos_de_k(teste: AppTest) -> list[str]:
        return [w.value for w in teste.warning if "K ≠ 1,0" in w.value]

    assert not avisos_de_k(abrir(banco_isolado, **base))
    for norma in ("NBR8800_2024", "AISC360_16_LRFD"):
        achados = avisos_de_k(abrir(banco_isolado, **base, col_norma=norma))
        assert achados and "análise direta" in achados[0], norma


def test_escopo_cita_a_barra_tracionada(banco_isolado):
    t = abrir(banco_isolado)
    assert any("Barra tracionada" in w.value for w in t.warning)


# ------------------------------------------------------------------ mão-francesa, K, C_b
def test_mao_francesa_soma_o_momento_e_avisa_do_cisalhamento(banco_isolado):
    t = abrir(
        banco_isolado,
        col_tipo_secao=ui.SEC_I,
        col_L=3000.0,
        col_modo_carga=ui.MODO_CALCULO,
        col_nsd=100.0,
        col_mf_incluir=True,
        col_mf_gamma="Já é de cálculo (γ = 1,00)",
        col_mf_vinculo=cb.VINCULOS_MAO_FRANCESA[0],
        col_mf_eixo="x",
        col_mf_e_x=0.0,
    )
    esforcos = cb.esforcos_mao_francesa(20_000.0, 45.0, 800.0, 3_000.0, cb.VINCULOS_MAO_FRANCESA[0])
    assert metrica(t, "H = F·sen θ") == f"{esforcos.componente_horizontal_N / 1e3:.2f} kN"
    assert metrica(t, "M_x,Sd da mão-francesa") == f"{esforcos.momento_Nmm / 1e6:.3f} kN·m"
    assert numero(metrica(t, "M_x,Sd amplificado")) > esforcos.momento_Nmm / 1e6
    assert tem_metrica(t, "B₁ em x") and not tem_metrica(t, "B₁ em y")
    assert linha(t, "Cisalhamento")["Status"] == "ALERTA"
    assert tem_metrica(t, "Índice de interação")


def test_sem_mao_francesa_nao_ha_alerta_de_cisalhamento(banco_isolado):
    t = abrir(banco_isolado, col_tipo_secao=ui.SEC_I)
    assert not tem_linha(t, "Cisalhamento")


def test_k_recomendado_e_k_informado(banco_isolado):
    base = dict(col_tipo_secao=ui.SEC_I, col_L=3000.0)
    biengastada = abrir(banco_isolado, **base, col_apoio_x="Biengastada", col_apoio_y="Biengastada")
    assert any("K_x·L_x = 0.65 × 3000 = **1950 mm**" in c.value for c in biengastada.caption)
    teorica = abrir(
        banco_isolado,
        **base,
        col_apoio_x="Biengastada",
        col_apoio_y="Biengastada",
        col_k_recomendado=False,
    )
    assert any("K_x·L_x = 0.50 × 3000 = **1500 mm**" in c.value for c in teorica.caption)
    manual = abrir(banco_isolado, **base, col_apoio_y=ui.APOIO_MANUAL, col_ky_manual=2.0)
    assert any("K_y·L_y = 2.00 × 3000 = **6000 mm**" in c.value for c in manual.caption)
    assert numero(metrica(manual, "λy = Ky·Ly/ry")) > 2 * numero(metrica(teorica, "λy = Ky·Ly/ry"))


def test_flexao_mostra_flt_flm_fla_e_cb_pelo_diagrama(banco_isolado):
    t = abrir(
        banco_isolado,
        col_tipo_secao=ui.SEC_I,
        col_Mx=40.0,
        col_Lb=6000.0,
        col_cb_modo=ui.CB_DIAGRAMA,
        col_cb_Mmax=20.0,
        col_cb_MA=10.0,
        col_cb_MB=15.0,
        col_cb_MC=10.0,
    )
    for estado in ("FLT", "FLM", "FLA"):
        assert tem_linha(t, f"Mx,Rd — {estado}")
    assert tem_linha(t, "limite 1,5·W·f_y")
    assert tem_metrica(t, "M_x,Rd")
    formula_flt = linha(t, "Mx,Rd — FLT")["Fórmula"]
    cb_esperado = min(3.0, cd.fator_Cb(20.0, 10.0, 15.0, 10.0))
    assert f"Cb = {cb_esperado:.2f}" in formula_flt and "Lb = 6000 mm" in formula_flt


# ------------------------------------------------------------------ outros tipos de seção
@pytest.mark.parametrize(
    "estado",
    [
        pytest.param({"col_tipo_secao": ui.SEC_CATALOGO}, id="catalogo"),
        pytest.param({"col_tipo_secao": ui.SEC_RET}, id="retangular-macica"),
        pytest.param({"col_tipo_secao": ui.SEC_TUBO_R}, id="tubo-retangular"),
        pytest.param({"col_tipo_secao": ui.SEC_I, "col_soldado_I": True}, id="i-soldado"),
    ],
)
def test_cada_tipo_de_secao_calcula(banco_isolado, estado):
    t = abrir(banco_isolado, **estado)
    assert tem_metrica(t, "N_c,Rd") and selo(t) in {"OK", "ALERTA", "NÃO OK"}


def test_secao_generica_com_mesa_soldada_pede_kc(banco_isolado):
    t = abrir(
        banco_isolado,
        col_tipo_secao=ui.SEC_GENERICA,
        col_gen_npar=2,
        col_par_tipo_1="AL · grupo 5 — mesa de perfil soldado",
        col_par_kc_1=0.45,
        col_par_tipo_2="AA · grupo 2 — alma",
        col_par_b_2=280.0,
        col_par_t_2=6.3,
        col_gen_torcao=False,
    )
    assert any(n.label == "k_c da parede 1" for n in t.number_input)
    parede = next(d.value for d in t.dataframe if "Grupo (Tabela 4)" in d.value.columns)
    assert list(parede["Grupo (Tabela 4)"]) == [5, 2]


def test_paredes_da_secao_aparecem_na_tela(banco_isolado):
    t = abrir(banco_isolado, col_tipo_secao=ui.SEC_I, col_L=3000.0)
    parede = next(d.value for d in t.dataframe if "Grupo (Tabela 4)" in d.value.columns)
    assert list(parede["Elemento"]) == ["mesa de perfil laminado", "alma"]
    assert list(parede["Tipo"]) == ["AL", "AA"]


# ------------------------------------------------------------------ CSV, registro, escopo
def test_csv_e_escopo(banco_isolado):
    t = abrir(banco_isolado)
    botao = next(b for b in t.get("download_button") if b.proto.label.startswith("Baixar"))
    assert botao.proto.help
    assert any("Cantoneira simples" in w.value for w in t.warning)  # fora do escopo, sempre visível


def test_norma_2008_lista_os_valores_a_conferir(banco_isolado):
    def itens_a_conferir(teste: AppTest) -> bool:
        return any("Tabela E.1 de K." in m.value for m in teste.markdown)

    assert itens_a_conferir(abrir(banco_isolado))
    assert not itens_a_conferir(abrir(banco_isolado, col_norma="AISC360_16_LRFD"))
    assert not itens_a_conferir(abrir(banco_isolado, col_norma="NBR8800_2024"))


def test_registrar_no_projeto_grava_a_tabela_inteira(banco_com_projeto):
    t = abrir(banco_com_projeto, col_tipo_secao=ui.SEC_I, col_Mx=20.0)
    t.button(key="registrar_flambagem_colunas").click().run()
    assert not t.exception, [str(e.value) for e in t.exception]
    projeto = obter_projeto_ativo()
    registros = [r for r in projeto["registros_tecnicos"] if r["modulo_id"] == "flambagem_colunas"]
    assert len(registros) == 1
    registro = registros[0]
    assert registro["resultados"]["status_geral"] in {"OK", "NÃO OK", "ALERTA"}
    assert len(registro["resultados"]["verificações"]) >= 15
    assert registro["entradas"]["condicao_apoio_x"] == "Biapoiada (pino-pino)"
    assert registro["entradas"]["norma"] == "NBR8800_2008"
