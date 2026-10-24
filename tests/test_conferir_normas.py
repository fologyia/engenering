"""Trava os valores fixados pelos marcadores "conferir" de core/.

Cada marcador catalogado em docs/conferir_normas.md que fixa um valor numérico ou um
comportamento acessível por código tem um teste aqui: se o valor mudar (por exemplo, após
ser confirmado na norma física), o teste aponta exatamente os cálculos e memoriais afetados.
Marcadores que são apenas notas metodológicas ou textos de interface ficam só no checklist.
"""

from __future__ import annotations

from core import degrau_registro as dr
from core import esforcos_modelo as em
from core import material_catalog as mc
from core import plano_de_cargas as pc
from core import section_catalog as sc
from core.steel_sections import PerfilAco

# --- CONF-009/CONF-010 (core/esforcos_modelo.py): peso próprio e reações ---


def test_coeficientes_usuais_estao_travados():
    assert em.COEFICIENTES_USUAIS == (1.25, 1.30, 1.35, 1.40, 1.50)
    assert em.TOLERANCIA_PESO == 0.05
    assert em.coeficiente_aparente(1.35) == 1.35
    assert em.coeficiente_aparente(2.0) is None


def test_reacao_nula_esta_travada():
    assert em.REACAO_NULA_kN == 1e-3


def test_conferir_peso_proprio_ok_quando_reacao_bate_com_peso():
    item = em.conferir_peso_proprio(100.0, 100.0)
    assert item.nivel == pc.NIVEL_OK


def test_conferir_peso_proprio_denuncia_estudo_majorado():
    item = em.conferir_peso_proprio(135.0, 100.0)
    assert item.nivel == pc.NIVEL_ERRO
    assert "γ ≈ 1,35" in item.texto


def test_conferir_peso_proprio_razao_dez_cita_gravidade_e_densidade():
    item = em.conferir_peso_proprio(1000.0, 100.0)
    assert item.nivel == pc.NIVEL_ERRO
    assert "9,81" in item.texto
    assert "7 850" in item.texto


def test_conferir_peso_proprio_modelo_mais_leve_gera_atencao():
    item = em.conferir_peso_proprio(50.0, 100.0)
    assert item.nivel == pc.NIVEL_ATENCAO


# --- CONF-005 (core/degrau_registro.py): avisos fixos do degrau ---


def test_avisos_fixos_travam_desenhos_anglo_e_carga_nbr6120():
    assert any("AA-BR-DPST-ES-0001 a 0004" in aviso for aviso in dr.AVISOS_FIXOS)
    carga = next(a for a in dr.AVISOS_FIXOS if "NBR 6120:2019" in a)
    assert "2,5 kN" in carga
    assert "Tabela 10" in carga
    assert "2.2.1.7" in carga


# --- CONF-024 (core/material_catalog.py): coerência de material ---


def _material(sy: float, sut: float) -> mc.MaterialCadastrado:
    return mc.MaterialCadastrado(
        nome="Aço teste",
        categoria="aco",
        sy_MPa=sy,
        sut_MPa=sut,
        origem="teste",
        editavel=True,
        origem_propriedades="norma",
    )


def test_conferir_coerencia_material_faixa_sy_sut():
    assert mc.conferir_coerencia(_material(250.0, 400.0)) == []
    fora = mc.conferir_coerencia(_material(30.0, 400.0))
    assert any("0,30 a 0,95" in aviso for aviso in fora)


def test_conferir_coerencia_material_sut_muito_alto():
    avisos = mc.conferir_coerencia(_material(250.0, 3000.0))
    assert any("MPa" in aviso and "psi" in aviso for aviso in avisos)


# --- CONF-043 (core/section_catalog.py): coerência de perfil ---


def _perfil(area: float = 1000.0, massa: float = 7.85) -> PerfilAco:
    return PerfilAco(
        nome="TEST-100",
        familia="teste",
        area_mm2=area,
        ix_mm4=100_000.0,
        iy_mm4=50_000.0,
        zx_mm3=1_500.0,
        zy_mm3=800.0,
        j_mm4=1_000.0,
        cw_mm6=1e8,
        altura_mm=100.0,
        largura_mm=100.0,
        espessura_alma_mm=5.0,
        espessura_mesa_mm=5.0,
        area_cisalhamento_mm2=500.0,
        massa_kg_m=massa,
        descricao="perfil de teste",
    )


def test_conferir_coerencia_perfil_z_sobre_w_fora_da_faixa():
    # W_x = I_x / (h/2) = 2 000 mm³; Z_x/W_x = 0,75 (fora de 1,0 a 1,8)
    avisos = sc.conferir_coerencia(_perfil())
    assert any("1,0 a 1,8" in aviso for aviso in avisos)


def test_conferir_coerencia_perfil_massa_12_pct():
    # massa esperada = 1000 mm² × 7850 kg/m³ = 7,85 kg/m; 20 % acima dispara o aviso
    avisos = sc.conferir_coerencia(_perfil(massa=10.0))
    assert any("12%" in aviso for aviso in avisos)
    dentro = sc.conferir_coerencia(_perfil(massa=8.0))
    assert not any("12%" in aviso for aviso in dentro)


# --- CONF-035 (core/plano_de_cargas.py): consistência do plano ---


def test_conferir_plano_vazio_erro():
    itens = pc.conferir_plano(pc.PlanoDeCargas())
    assert len(itens) == 1
    assert itens[0].nivel == pc.NIVEL_ERRO


def test_conferir_plano_temperatura_num_sentido_so_cita_anglo():
    plano = pc.com_acao(pc.PlanoDeCargas(), pc.nova_acao("T+"))
    itens = pc.conferir_plano(plano)
    assert any("±10 °C" in item.texto and "5.8" in item.texto for item in itens)
