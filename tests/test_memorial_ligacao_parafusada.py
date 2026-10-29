"""Memorial da ligação parafusada (página Projeto de parafusos) — correções de 28/10/2026.

O caso real do usuário (M22 A325, A36, t = 6,35 mm, 2 planos de corte, 1 linha × 2 colunas,
s = 60, e = 35, N = 0,2 kN, V = 17 kN, γ_f = 1,4, galvanizado, por atrito), reconstruído pelos
números do memorial dele, e os casos B, C e D do pedido anterior rodados pela ligação inteira até
o memorial: nome da norma único, equação do contato com os coeficientes usados, item de norma com
ponto, casas decimais uniformes, cisalhamento da chapa por V, regra dos 75% da Anglo e a seção da
tração.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterator
from dataclasses import replace
from typing import Any

import pytest
from pypdf import PdfReader

from core import bolted_connection as bc
from core import bolted_joint_check as chk
from core import memorial_verificacoes as mv
from core.project_report import _valor
from core.technical_records import normalizar_registro_tecnico

NBR_2025 = "NBR8800_2024"  # chave interna da NBR 8800:2025

M22 = chk.EntradaLigacao(
    norma=NBR_2025,
    N=0.2,
    V=17.0,
    gama_f=1.4,
    designacao="M22",
    grau="A325",
    rosca_no_plano=True,
    n_planos=2,
    t=6.35,
    aco="ASTM A36",
    n_lin=1,
    n_col=2,
    s=60.0,
    e=35.0,
    deformacao_limitada=False,
    superficie="galvanizada_sem_tratamento",
    ligacao_por_atrito=True,
    A_g=548.0,
    e_c=13.0,
    chapa_largura=108.0,
    chapa_furos=1,
)

# Casos B, C e D do pedido anterior, agora pela ligação inteira (M16 A325, 1 × 2, A36).
_M16 = dict(
    norma=NBR_2025,
    designacao="M16",
    grau="A325",
    t=6.35,
    aco="ASTM A36",
    n_lin=1,
    n_col=2,
    s=60.0,
    e=35.0,
    superficie="galvanizada_sem_tratamento",
)
#: B — F_t,Sd = 1 kN e F_v,Sd = 15 kN por parafuso (de cálculo).
CASO_B = chk.EntradaLigacao(
    **_M16, V=30.0, N_t=2.0, valores_sao_de_calculo=True, interacao_por_tabela=True
)
#: C — placa rígida: a = b = 35, p = 60, d_f = 18, t = 6,35, F_t,0,Sd = 2,5 kN por parafuso.
CASO_C = chk.EntradaLigacao(
    **_M16,
    N_t=5.0,
    valores_sao_de_calculo=True,
    alavanca=True,
    alav_a=35.0,
    alav_b=35.0,
    alav_p=60.0,
    alav_d_f=18.0,
)
#: D — deslizamento no ELU (furo alargado), F_t,Sd = 1 kN por parafuso.
CASO_D = chk.EntradaLigacao(
    **_M16, V=20.0, N_t=2.0, valores_sao_de_calculo=True, tipo_furo=bc.FURO_ALARGADO
)


def perto(a: float | None, b: float, rel: float = 0.005) -> bool:
    return a is not None and abs(a - b) <= rel * abs(b)


def linha(resultado: chk.ResultadoLigacao, trecho: str) -> Any:
    return next(v for v in resultado.verificacoes if trecho in v.nome)


def registro(entrada: chk.EntradaLigacao) -> dict[str, Any]:
    resultado = chk.verificar_ligacao(entrada)
    return normalizar_registro_tecnico(chk.registro_ligacao(entrada, resultado, None))


def capitulo(entrada: chk.EntradaLigacao) -> dict[str, Any]:
    reg = registro(entrada)
    linhas = mv.extrair_linhas(reg)
    assert linhas is not None
    return mv.capitulo_de_verificacoes(
        reg, linhas, titulo="3.1 Ligação", nivel=2, peca="-", formatar=_valor, rotular=str
    )


def _textos(no: Any) -> Iterator[str]:
    if isinstance(no, str):
        yield no
    elif isinstance(no, dict):
        for valor in no.values():
            yield from _textos(valor)
    elif isinstance(no, (list, tuple)):
        for item in no:
            yield from _textos(item)


def texto(entrada: chk.EntradaLigacao) -> str:
    return "\n".join(_textos(capitulo(entrada)))


def tabelas(cap: dict[str, Any]) -> list[dict[str, Any]]:
    return [b for b in cap["blocos"] if b["tipo"] == "tabela"]


def pares(entrada: chk.EntradaLigacao) -> dict[str, str]:
    return dict(mv.pares_de_entrada(registro(entrada), _valor, str))


# ------------------------------------------------------------------ caso M22: valores mantidos
def test_m22_valores_do_memorial_permanecem():
    r = chk.verificar_ligacao(M22)
    assert perto(r.resistencias["F_v_Rd_kN"], 210.3, 0.001)
    assert perto(r.resistencias["F_c_Rd_critico_kN"], 64.91, 0.0005)
    assert perto(r.forcas["R_max_ELU_kN"], 11.901, 0.0005)
    assert perto(r.resistencias["F_f_Rk_kN"], 56.32, 0.0005)
    assert perto(r.resistencias["N_t_Rd_kN"], 88.871, 0.0005)
    assert perto(r.resistencias["F_r_Rd_kN"], 126.44, 0.0005)
    assert perto(r.resistencias["chapa_escoamento_kN"], 155.86, 0.0005)
    assert perto(r.resistencias["chapa_ruptura_kN"], 154.28, 0.0005)


def test_m22_um_plano_de_corte():
    r = chk.verificar_ligacao(replace(M22, n_planos=1))
    assert perto(r.resistencias["F_v_Rd_kN"], 105.2, 0.001)
    assert perto(r.resistencias["F_f_Rk_kN"], 28.16, 0.0005)


# ------------------------------------------------------------------ A.2 equação do contato
@pytest.mark.parametrize(
    ("limitada", "esperado", "k1", "k2"),
    [(False, 64.91, "1,5", "3,0"), (True, 51.93, "1,2", "2,4")],
)
def test_contato_e_texto_da_equacao_com_os_coeficientes_usados(limitada, esperado, k1, k2):
    entrada = replace(M22, deformacao_limitada=limitada)
    r = chk.verificar_ligacao(entrada)
    # M22, ℓ_f = 35 − 24/2 = 23 mm, t = 6,35, f_u = 400, γ_a2 = 1,35.
    assert perto(r.resistencias["F_c_Rd_critico_kN"], esperado, 0.0005)
    assert perto(bc.resist_contato(22, 6.35, 400, 23.0, NBR_2025, limitada), esperado, 0.0005)
    cheio = texto(entrada)
    simbolica = f"mín({k1}·ℓ_f·t·f_u; {k2}·d_b·t·f_u)/γ_a2"
    substituida = f"mín({k1}·23,0·6,35·400; {k2}·22·6,35·400)/1,35"
    assert simbolica in cheio and substituida in cheio
    assert f"= {esperado:.2f} kN".replace(".", ",") in cheio
    outra = "1,2·ℓ_f" if not limitada else "1,5·ℓ_f"
    assert outra not in cheio
    motivo = "deformação do furo limitada" if limitada else "deformação do furo não limitada"
    assert motivo in cheio


# ------------------------------------------------------------------ A.1 nome da norma
def test_nome_da_norma_unico_no_memorial():
    reg = registro(M22)
    cheio = texto(M22)
    assert pares(M22)["Norma"] == "ABNT NBR 8800:2025"
    assert "ABNT NBR 8800:2025" in reg["titulo"]
    assert reg["referencias"][0].startswith("ABNT NBR 8800:2025")
    assert "2024" not in cheio and "Projeto de revisão" not in cheio
    for v in chk.verificar_ligacao(M22).verificacoes:
        assert "2024" not in v.referencia


def test_nome_da_norma_2008_tambem_vem_da_tabela_central():
    entrada = replace(M22, norma="NBR8800_2008")
    assert pares(entrada)["Norma"] == chk.NORMAS_ROTULOS["NBR8800_2008"]
    assert "2025" not in texto(entrada)


# ------------------------------------------------------------------ A.5 formatação
def test_item_de_norma_com_ponto():
    cheio = texto(M22)
    assert "AISC J3.3 a J3.5" in cheio
    assert not re.search(r"J\d,\d|RCSC \d,\d|NBR \d,\d", cheio)
    assert mv.decimal_ptbr("(AISC J3.6 / RCSC 5.1); NBR 5.2 e 6.5.6 = 1.35") == (
        "(AISC J3.6 / RCSC 5.1); NBR 5.2 e 6.5.6 = 1,35"
    )


def test_casas_decimais_uniformes_nas_colunas():
    cap = capitulo(M22)
    verificacoes = [t for t in tabelas(cap) if t["cabecalhos"][1] == "Solicitante"]
    assert verificacoes
    for tabela in verificacoes:
        for celulas in tabela["linhas"]:
            for celula in celulas[1:3]:
                assert celula == "-" or re.fullmatch(r"\d+,\d\d", celula), celula
    passou = verificacoes[0]["linhas"]
    resistentes = {celulas[0]: celulas[2] for celulas in passou}
    assert resistentes["Parafuso crítico — min(corte; contato/rasgamento)"] == "64,91"
    assert resistentes["Deslizamento (ELS, força de serviço)"] == "56,32"


def test_t_minimo_desprezivel_nao_mostra_0_01():
    cheio = texto(M22)
    assert "t mínimo = 0,01" not in cheio
    assert "t mínimo desprezível para esta carga" in cheio


# ------------------------------------------------------------------ B.6 cisalhamento da chapa
def test_chapa_ao_cisalhamento_por_v():
    r = chk.verificar_ligacao(M22)
    esc = linha(r, "escoamento por cisalhamento")
    rup = linha(r, "ruptura por cisalhamento")
    # 0,60·(108·6,35)·250/1,10 e 0,60·(108 − 26)·6,35·400/1,35
    assert perto(esc.resistente, 0.60 * 685.8 * 250 / 1.10 / 1000, 1e-6)
    assert perto(rup.resistente, 0.60 * 520.7 * 400 / 1.35 / 1000, 1e-6)
    assert perto(esc.solicitante, 23.8, 1e-9) and esc.status == "OK"
    assert "verificados separadamente" in esc.formula
    assert "6.5.5 (a confirmar)" in esc.referencia


def test_chapa_ao_cisalhamento_na_2008_cita_o_item_conferido():
    r = chk.verificar_ligacao(replace(M22, norma="NBR8800_2008"))
    esc = linha(r, "escoamento por cisalhamento")
    assert esc.referencia == "NBR 8800:2008, 6.5.5"
    assert "não traz interação com a tração" in esc.formula


def test_peca_ao_cisalhamento_fica_a_confirmar():
    r = chk.verificar_ligacao(M22)
    v = linha(r, "Peça — cisalhamento")
    assert v.status == "ALERTA" and "a confirmar" in v.formula


def test_sem_chapa_o_memorial_declara_que_v_nao_foi_verificado():
    reg = registro(replace(M22, chapa_largura=None, chapa_furos=None))
    assert any("V transversal não é verificado na chapa" in p for p in reg["premissas"])


# ------------------------------------------------------------------ B.7 regra dos 75% (Anglo)
def test_regra_dos_75_no_m22_passa_pelo_menor_componente():
    entrada = replace(M22, peca_por_esbeltez=True)
    v = linha(chk.verificar_ligacao(entrada), "75%")
    assert v.status == "OK"
    assert perto(v.solicitante, 0.75 * 88.871, 0.0005)  # 66,7 kN
    assert perto(v.resistente, 2 * 56.32, 0.0005)  # deslizamento × n = 112,6 kN governa
    for parcela in (
        "deslizamento 2·F_f,Rk = 112.64",
        "colapso por rasgamento = 126.44",
        "contato 2·F_c,Rd = 129.82",
    ):
        assert parcela in v.formula
    assert "esbeltez ou sem esforço indicado" in v.formula
    rotulo = next(r for chave, r, _ in mv._ENTRADAS_PARAFUSOS if chave == "peca_por_esbeltez")
    assert pares(entrada)[rotulo] == "Sim"


def test_marcador_dos_75_aparece_nos_dados_mesmo_desligado():
    rotulos = {rotulo: valor for rotulo, valor in pares(M22).items() if "75%" in rotulo}
    assert list(rotulos.values()) == ["Não"]


# ------------------------------------------------------------------ B.8 tração (casos B, C, D)
def test_m22_sem_tracao_nao_tem_secao_nem_equacoes_da_tracao():
    cheio = texto(M22)
    assert "Tração, interação e efeito de alavanca" not in cheio
    assert "F_t,Rd" not in cheio and "1,13·μ" not in cheio


def _secao_da_tracao(entrada: chk.EntradaLigacao) -> dict[str, list[str]]:
    cap = capitulo(entrada)
    blocos = cap["blocos"]
    i = next(
        k
        for k, b in enumerate(blocos)
        if b["tipo"] == "subtitulo" and b["texto"] == "Tração, interação e efeito de alavanca"
    )
    assert blocos[i + 1]["tipo"] == "tabela"
    return {celulas[0]: celulas for celulas in blocos[i + 1]["linhas"]}


def test_caso_b_tracao_interacao_e_tabela_12():
    r = chk.verificar_ligacao(CASO_B)
    assert perto(r.resistencias["F_t_Rd_kN"], 92.7, 0.005)
    assert perto(r.intermediarios["interacao_tracao_corte"], 0.073, 0.01)
    secao = _secao_da_tracao(CASO_B)
    assert secao["Área bruta do parafuso A_b"][1] == "201,06"
    assert secao["Área efetiva à tração A_be"][1] == "150,80"
    assert secao["Tração resistente F_t,Rd"][1] == "92,71"
    assert secao["Interação tração + corte"][1] == "0,073"
    # 830·201,06/1,35 − 1,9·15 = 123,62 − 28,50 = 95,12 kN (o "95,1" do caso B).
    assert secao["Limite da Tabela 12 (alternativa)"][1] == "95,12"
    assert "Tabela 12" in secao["Limite da Tabela 12 (alternativa)"][3]
    assert "Não verificado" in secao["Efeito de alavanca"][3]
    # A seção já traz F_t,Sd e F_t,Rd: nada de repeti-los em "Outros resultados".
    assert "Outros resultados registrados." not in texto(CASO_B)


def test_caso_c_placa_rigida():
    r = chk.verificar_ligacao(CASO_C)
    assert perto(r.intermediarios["t_rigida_mm"], 3.52, 0.005)
    assert linha(r, "placa rígida").status == "OK"
    secao = _secao_da_tracao(CASO_C)
    assert secao["Placa rígida: t mínimo (sem alavanca)"][1] == "3,52"
    assert "Sem corte no parafuso" in secao["Interação tração + corte"][3]


def test_caso_d_deslizamento_no_elu():
    r = chk.verificar_ligacao(CASO_D)
    assert perto(r.resistencias["F_f_Rd_kN"], 16.97, 0.005)
    assert "1,13·μ" in linha(r, "Deslizamento (ELU").formula
    assert "Tração resistente F_t,Rd" in _secao_da_tracao(CASO_D)


def test_caso_d_servico_com_tracao_caracteristica():
    # F_t,Sk = 0,7 kN por parafuso: N_t característico de 1,4 kN em dois parafusos.
    r = chk.verificar_ligacao(chk.EntradaLigacao(**_M16, V=10.0, N_t=1.4))
    assert perto(r.resistencias["F_f_Rk_kN"], 14.42, 0.005)


# ------------------------------------------------------------------ C.10 e o PDF da página
def test_metodo_sem_planilha_sem_nome_e_versao():
    reg = registro(M22)
    assert "planilha" not in reg["metodo"].casefold()
    assert "Design Guide 29" in reg["metodo"]


@pytest.mark.parametrize("entrada", [M22, CASO_B], ids=["M22", "caso B"])
def test_pdf_da_pagina(entrada):
    resultado = chk.verificar_ligacao(entrada)
    pdf = chk.memorial_da_ligacao(entrada, resultado, None, formato="pdf")
    cheio = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
    assert "ABNT NBR 8800:2025" in cheio and "Projeto de revisão" not in cheio
    assert "planilha de referência" not in cheio
    tem_tracao = entrada is CASO_B
    assert ("Tração, interação e efeito de alavanca" in cheio) is tem_tracao
