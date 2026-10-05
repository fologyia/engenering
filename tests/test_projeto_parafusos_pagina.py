"""A página Projeto de parafusos, exercitada pela interface (AppTest).

Confere na tela os resultados do critério de aceite — caso real da emenda de perfis U pela
NBR 8800:2008 e os exemplos do AISC Design Guide 29 — e as correções do modo mecânico:
grade retangular, serviço × cálculo, excentricidade da cortante e a tabela de diagnóstico
com solicitante, resistente, aproveitamento, status, fórmula e item da norma.
"""

from __future__ import annotations

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from core import bolt_design as parafusos
from core import bolted_connection as bc
from core.verificacao import COLUNAS_TABELA

PAGINA = "app_pages/projeto_parafusos.py"
ESTRUTURAL = "Ligação estrutural de aço"
KIP = bc.KIP_KN


def abrir(banco_isolado, **estado) -> AppTest:
    teste = AppTest.from_file("app.py", default_timeout=180)
    teste.run()
    teste.switch_page(PAGINA)
    for chave, valor in estado.items():
        teste.session_state[chave] = valor
    teste.run()
    assert not teste.exception, [str(e.value) for e in teste.exception]
    return teste


def estrutural(banco_isolado, **estado) -> AppTest:
    return abrir(banco_isolado, **{"parafuso_modo": ESTRUTURAL, **estado})


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


def metrica(teste: AppTest, rotulo: str) -> str:
    return next(m.value for m in teste.metric if m.label == rotulo)


# ------------------------------------------------------------------ modo estrutural, caso real
def test_modo_estrutural_mostra_as_oito_colunas_e_o_caso_real(banco_isolado):
    t = estrutural(banco_isolado)
    assert tuple(tabela(t).columns) == COLUNAS_TABELA
    assert metrica(t, "Parafuso crítico (ELU)") == "32.65 kN"
    assert metrica(t, "Parafuso crítico (serviço)") == "23.32 kN"
    critico = linha(t, "Parafuso crítico")
    assert critico["Resistente"] == pytest.approx(79.47, rel=0.002)
    assert critico["Aproveitamento"] == pytest.approx(41, abs=0.5)
    assert critico["Status"] == "OK"
    desliz = linha(t, "Deslizamento")
    assert desliz["Resistente"] == pytest.approx(28.16, rel=0.002)
    assert desliz["Aproveitamento"] == pytest.approx(83, abs=0.5)
    assert linha(t, "Distância máxima à borda")["Status"] == "NÃO OK"


def test_momento_polar_na_tela(banco_isolado):
    t = estrutural(banco_isolado)
    assert any("J = 9.800 mm²" in c.value for c in t.caption)


def test_m16_reprova_no_deslizamento(banco_isolado):
    t = estrutural(banco_isolado, ligest_designacao="M16")
    desliz = linha(t, "Deslizamento")
    assert desliz["Resistente"] == pytest.approx(14.56, rel=0.002)
    assert desliz["Aproveitamento"] == pytest.approx(160, abs=1)
    assert desliz["Status"] == "NÃO OK"


def test_borda_de_60_mm_passa_e_o_menor_parafuso_e_o_m22(banco_isolado):
    t = estrutural(banco_isolado, ligest_e=60.0)
    assert linha(t, "Distância máxima à borda")["Status"] == "OK"
    # Com e = 60 mm a excentricidade padrão de emenda cai para a = e + s/2 = 95 mm
    # (e não 105), então R_max (serviço) = 21,76 kN e o M20 (F_f = 22,72 kN) já passa.
    assert metrica(t, "Menor parafuso que atende") == "M20"


def test_borda_de_70_mm_nenhum_parafuso_resolve(banco_isolado):
    t = estrutural(banco_isolado)
    assert metrica(t, "Menor parafuso que atende") == "nenhum com esta geometria"


def test_axial_m16_peca_u6_e_regra_dos_75(banco_isolado):
    t = estrutural(
        banco_isolado,
        ligest_designacao="M16",
        ligest_V=0.0,
        ligest_N=44.8,
        ligest_ja_majorado=True,
        ligest_momento_g="Sem momento",
        ligest_Ag=1542.0,
        ligest_ec=13.0,
        ligest_esbeltez=True,
    )
    assert linha(t, "Grupo de parafusos")["Resistente"] == pytest.approx(196.6, rel=0.002)
    assert linha(t, "Tração da peça")["Resistente"] == pytest.approx(323.0, rel=0.002)
    assert linha(t, "Colapso por rasgamento")["Resistente"] == pytest.approx(233.3, rel=0.002)
    regra = linha(t, "75%")
    assert regra["Solicitante"] == pytest.approx(242.3, rel=0.002)
    assert regra["Resistente"] == pytest.approx(196.6, rel=0.002)
    assert regra["Status"] == "NÃO OK"


def test_dg29_na_tela(banco_isolado):
    t = estrutural(
        banco_isolado,
        ligest_norma="AISC360_LRFD",
        ligest_designacao='1"',
        **{'ligest_dh_1"': 27.0},
        ligest_t=9.525,
        ligest_n_lin=2,
        ligest_n_col=5,
        ligest_s=76.2,
        ligest_g=70.3,
        ligest_e=31.75,
        ligest_atrito=False,
        ligest_N=100.0,
        ligest_V=0.0,
        ligest_ja_majorado=True,
        ligest_momento_g="Sem momento",
    )
    assert linha(t, "Grupo de parafusos")["Resistente"] / KIP == pytest.approx(283, rel=0.01)
    assert linha(t, "Colapso por rasgamento")["Resistente"] / KIP == pytest.approx(187, rel=0.01)


def test_botoes_comparar_normas_e_testar_todos(banco_isolado):
    t = estrutural(banco_isolado, ligest_e=60.0)
    t.button(key="ligest_btn_comparar").click().run()
    t.button(key="ligest_btn_testar").click().run()
    assert not t.exception
    comparacao = next(d.value for d in t.dataframe if "Norma" in d.value.columns)
    assert len(comparacao) == 4
    varredura = next(
        d.value
        for d in t.dataframe
        if "Parafuso" in d.value.columns and "d_b (mm)" in d.value.columns
    )
    assert len(varredura) == len(bc.PARAFUSOS)
    assert any("M20" in s.value for s in t.success)


def test_condicao_fora_do_escopo_vira_alerta_na_tabela(banco_isolado):
    t = estrutural(banco_isolado, ligest_e=60.0, ligest_fora_escopo=["fadiga"])
    assert linha(t, "fora do escopo")["Status"] == "ALERTA"


def test_pega_menor_que_t_e_erro(banco_isolado):
    t = abrir(banco_isolado, parafuso_modo=ESTRUTURAL, ligest_pega=2.0)
    assert any("pega" in e.value for e in t.error)


def test_coordenadas_livres_abrem_sem_erro(banco_isolado):
    t = estrutural(banco_isolado, ligest_geometria="Coordenadas livres", ligest_e_livre=60.0)
    assert linha(t, "Parafuso crítico")["Status"] == "OK"


# ------------------------------------------------------------------ modo mecânico, correções 1, 2, 3, 4 e 10
def test_modo_mecanico_e_o_padrao_e_traz_o_rotulo_fixo(banco_isolado):
    t = abrir(banco_isolado)
    assert t.session_state["parafuso_modo"] == "Junta mecânica (NASA/ISO)"
    assert any("não substitui a verificação por norma estrutural" in w.value for w in t.warning)


def test_mecanico_diagnostico_tem_as_oito_colunas_preenchidas(banco_isolado):
    t = abrir(banco_isolado)
    df = tabela(t)
    assert tuple(df.columns) == COLUNAS_TABELA
    assert len(df) >= 7
    com_numero = df[df["Status"] != "N/A"]
    assert com_numero["Solicitante"].notna().all() and com_numero["Resistente"].notna().all()
    assert (df["Referência"].str.len() > 0).all() and (df["Fórmula"].str.len() > 0).all()
    assert set(df["Status"]) <= {"OK", "NÃO OK", "ALERTA", "INFO", "N/A"}


def test_mecanico_grade_retangular_usa_as_coordenadas_da_grade(banco_isolado):
    t = abrir(
        banco_isolado,
        parafuso_padrao="Grade retangular",
        parafuso_grade_linhas=2,
        parafuso_grade_colunas=2,
        parafuso_grade_passo=70.0,
        parafuso_grade_gabarito=70.0,
        parafuso_modo_torque="Excentricidade da cortante (T = V·a)",
        parafuso_excentricidade_cortante=105.0,
        parafuso_carga_axial=0.0,
        parafuso_carga_cortante=32.0,
    )
    distribuicao = next(d.value for d in t.dataframe if "x (mm)" in d.value.columns)
    assert sorted(distribuicao["x (mm)"]) == [0.0, 0.0, 70.0, 70.0]
    assert any("T = V·a = 3360.0 N·m" in c.value for c in t.caption)
    # o mesmo cálculo direto, sem a interface
    grupo = parafusos.distribuir_cargas_grupo(
        list(bc.grade_retangular(2, 2, 70.0, 70.0)),
        carga_cortante_N=32_000.0,
        torque_grupo_Nmm=32.0 * 105.0 * 1000.0,
    )
    maior = max(r for r in distribuicao["Cisalhamento resultante (kN)"])
    assert maior == pytest.approx(grupo.maior_cisalhamento_N / 1000.0, rel=1e-9)


def test_mecanico_valores_majorados_voltam_ao_servico(banco_isolado):
    t = abrir(
        banco_isolado,
        parafuso_natureza_cargas="Já majorados (cálculo)",
        parafuso_gama_f=1.4,
        parafuso_carga_axial=0.0,
        parafuso_carga_cortante=44.8,
    )
    assert any("V = 32.00 kN" in c.value for c in t.caption)


def test_mecanico_pega_menor_que_t_e_erro(banco_isolado):
    t = abrir(banco_isolado, parafuso_espessura_chapa=10.0, parafuso_pega=5.0)
    assert any("pega" in e.value for e in t.error)


# ------------------------------------------------------------------ “?” em todos os campos
TIPOS_COM_AJUDA = (
    "number_input",
    "selectbox",
    "toggle",
    "button_group",
    "button",
    "download_button",
    "metric",
    "subheader",
    "badge",
)
# Único título sem “?”: ele próprio já é o convite para abrir o Guia.
ISENTOS_DE_AJUDA = {("subheader", "Precisa de ajuda para preencher ou interpretar?")}


def _ajuda_de(elemento) -> str | None:
    proto = getattr(elemento, "proto", None)
    for campo in ("help", "tooltip"):
        for origem in (elemento, proto):
            texto = getattr(origem, campo, None)
            if texto:
                return str(texto)
    return None


def _rotulo_de(elemento) -> str:
    proto = getattr(elemento, "proto", None)
    for origem in (elemento, proto):
        for campo in ("label", "body"):
            texto = getattr(origem, campo, None)
            if texto:
                return str(texto)
    return repr(elemento)[:60]


def sem_ajuda(teste: AppTest) -> set[tuple[str, str]]:
    faltam = set()
    for tipo in TIPOS_COM_AJUDA:
        for elemento in teste.get(tipo):
            if not _ajuda_de(elemento):
                faltam.add((tipo, _rotulo_de(elemento)))
    return faltam - ISENTOS_DE_AJUDA


@pytest.mark.parametrize(
    "estado",
    [
        pytest.param({"parafuso_modo": ESTRUTURAL}, id="estrutural-padrao"),
        pytest.param(
            {
                "parafuso_modo": ESTRUTURAL,
                "ligest_tem_ev": True,
                "ligest_momento_g": "Excentricidade a informada",
                "ligest_Ag": 1542.0,
                "ligest_ec": 13.0,
                "ligest_esbeltez": True,
            },
            id="estrutural-borda-vertical-excentricidade-peca",
        ),
        pytest.param(
            {"parafuso_modo": ESTRUTURAL, "ligest_momento_g": "Momento M informado"},
            id="estrutural-momento",
        ),
        pytest.param(
            {"parafuso_modo": ESTRUTURAL, "ligest_geometria": "Coordenadas livres"},
            id="estrutural-coordenadas-livres",
        ),
        pytest.param({}, id="mecanico-padrao"),
        pytest.param(
            {
                "parafuso_padrao": "Grade retangular",
                "parafuso_natureza_cargas": "Já majorados (cálculo)",
                "parafuso_modo_torque": "Excentricidade da cortante (T = V·a)",
            },
            id="mecanico-grade-majorado-excentricidade",
        ),
        pytest.param(
            {"parafuso_padrao": "Coordenadas livres", "parafuso_analisar_fadiga": True},
            id="mecanico-coordenadas-fadiga",
        ),
    ],
)
def test_todo_campo_tem_interrogacao(banco_isolado, estado):
    t = abrir(banco_isolado, **estado)
    faltam = sem_ajuda(t)
    assert not faltam, f"campos sem “?”: {sorted(faltam)}"


def test_planos_de_corte_explicados_na_tela(banco_isolado):
    t = estrutural(banco_isolado)
    campo = next(n for n in t.number_input if n.label == "Planos de corte")
    assert "1 plano" in campo.help and "2 planos" in campo.help
    assert "Ex.: a alma de um perfil U" in campo.help


def test_simplificacoes_aparecem_nas_dicas(banco_isolado):
    t = estrutural(banco_isolado)
    furo = next(n for n in t.number_input if n.label == "Furo d_h (mm)")
    assert "Simplificação" in furo.help and "furo-padrão" in furo.help
    secao = next(s for s in t.subheader if s.value.startswith("3. Esforços"))
    assert "método elástico" in secao.help


def test_colunas_da_tabela_explicam_o_que_mostram(banco_isolado):
    import json

    from components.verification_table import AJUDA_COLUNAS

    t = estrutural(banco_isolado)
    tabela_el = next(d for d in t.dataframe if "Verificação" in d.value.columns)
    colunas = json.loads(tabela_el.proto.columns)
    for coluna, texto in AJUDA_COLUNAS.items():
        assert colunas[coluna]["help"] == texto, coluna


# ------------------------------------------------------------------ sem o aviso de “valor normativo”
def textos_da_tela(teste: AppTest) -> str:
    partes: list[str] = []

    def percorrer(no) -> None:
        # Elementos folha não têm `children`: o AppTest repassa o atributo ao proto.
        for filho in (getattr(no, "children", None) or {}).values():
            proto = getattr(filho, "proto", None)
            if proto is not None:
                partes.append(str(proto))
            percorrer(filho)

    percorrer(teste.main)
    partes += [d.value.to_csv() for d in teste.dataframe]
    return "\n".join(partes).lower()


@pytest.mark.parametrize("modo", [ESTRUTURAL, "Junta mecânica (NASA/ISO)"])
def test_tela_nao_diz_que_o_projeto_2024_nao_tem_valor_normativo(banco_isolado, modo):
    t = abrir(banco_isolado, parafuso_modo=modo, ligest_norma="NBR8800_2024")
    if modo == ESTRUTURAL:
        t.button(key="ligest_btn_comparar").click().run()  # abre a tabela das quatro normas
        assert any("Projeto NBR 8800:2024" in str(d.value.to_dict()) for d in t.dataframe)
    texto = textos_da_tela(t)
    for frase in ("valor normativo", "sem valor", "não tem valor"):
        assert frase not in texto, frase
