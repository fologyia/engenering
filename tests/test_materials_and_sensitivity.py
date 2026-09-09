import pytest

from core.materials_registry import (
    avaliar_material,
    criar_material_projeto,
    listar_catalogo_referencia,
    verificar_temperatura,
)
from core.sensitivity import analisar_monte_carlo, analisar_oat, sugerir_de_registro


def _material_certificado():
    return criar_material_projeto(
        nome="Aço do lote HN-24017",
        familia="Aço carbono",
        condicao="Normalizado",
        forma_produto="Chapa 12,5 mm",
        lote="HN-24017",
        propriedades={
            "Sut_MPa": 430.0,
            "Sy_MPa": 285.0,
            "E_GPa": 200.0,
            "nu": 0.3,
            "densidade_kg_m3": 7850.0,
            "temperatura_min_C": -20.0,
            "temperatura_max_C": 120.0,
        },
        origem_tipo="Certificado do lote / MTR",
        fonte="Usina ABC",
        documento="MTR-45821",
        edicao="Rev. 0",
        pagina_clausula="p. 2",
        data_verificacao="2026-08-14",
        responsavel_verificacao="Eng. A",
        aplicabilidade="Mesma corrida e espessura do item SK-101.",
    )


def test_catalogo_permanece_orientativo_e_material_certificado_e_rastreavel():
    catalogo = listar_catalogo_referencia()
    assert catalogo
    assert all(avaliar_material(item)["nivel"] == "Referência" for item in catalogo)

    material = _material_certificado()
    assert material["avaliacao"]["nivel"] == "Confirmado"
    assert material["avaliacao"]["indice_rastreabilidade"] >= 85
    assert verificar_temperatura(material, 80.0)["status"] == "Dentro da faixa"
    assert verificar_temperatura(material, 180.0)["status"] == "Fora da faixa"


def test_material_rejeita_propriedades_inconsistentes():
    with pytest.raises(ValueError, match="Sy não pode superar Sut"):
        criar_material_projeto(
            nome="Material inválido",
            familia="Aço",
            condicao="Teste",
            forma_produto="Chapa",
            propriedades={"Sut_MPa": 200.0, "Sy_MPa": 250.0},
            origem_tipo="Relatório de ensaio",
            fonte="Laboratório",
        )


def test_oat_identifica_expoente_quatro_do_vao():
    entradas = {
        "carga_kN_m": 5.0,
        "vao_mm": 4_000.0,
        "E_GPa": 200.0,
        "inercia_mm4": 80_000_000.0,
    }
    resultado = analisar_oat("flecha_viga", entradas, variacao_percentual=1.0)
    assert resultado["ranking"][0]["chave"] == "vao_mm"
    assert resultado["ranking"][0]["elasticidade"] == pytest.approx(4.0, rel=2e-3)


def test_monte_carlo_e_reproduzivel_e_calcula_probabilidade():
    entradas = {"demanda": 80.0, "capacidade": 100.0}
    configuracao = {
        "demanda": {"incerteza_percentual": 20.0, "distribuicao": "Uniforme"},
        "capacidade": {"incerteza_percentual": 10.0, "distribuicao": "Uniforme"},
    }
    kwargs = dict(
        amostras=1_000,
        semente=17,
        criterio={"ativo": True, "operador": "<=", "limite": 1.0},
    )
    primeiro = analisar_monte_carlo("utilizacao", entradas, configuracao, **kwargs)
    segundo = analisar_monte_carlo("utilizacao", entradas, configuracao, **kwargs)
    assert primeiro["p95"] == segundo["p95"]
    assert primeiro["probabilidade_nao_atendimento_pct"] == segundo["probabilidade_nao_atendimento_pct"]
    assert 0.0 <= primeiro["probabilidade_nao_atendimento_pct"] <= 100.0


def test_importacao_de_registro_estatico_preserva_entradas():
    sugestao = sugerir_de_registro(
        {
            "modulo": "Análise estática",
            "entradas": {"sigma_x_MPa": 100, "sigma_y_MPa": 10, "tau_xy_MPa": 20, "Sy_MPa": 250},
        }
    )
    assert sugestao["modelo_id"] == "seguranca_vm"
    assert sugestao["entradas"]["Sy_MPa"] == 250


def test_sugestao_prefere_modulo_id_ao_texto_do_titulo():
    sugestao = sugerir_de_registro(
        {
            "modulo": "Nome alterado depois da versão 1",
            "modulo_id": "analise_estatica",
            "entradas": {"sigma_x_MPa": 50, "sigma_y_MPa": 0, "tau_xy_MPa": 0, "Sy_MPa": 200},
        }
    )
    assert sugestao["modelo_id"] == "seguranca_vm"


def test_mohr_2d_sugere_modelo_de_seguranca_sem_sy():
    sugestao = sugerir_de_registro(
        {
            "modulo": "Círculo de Mohr",
            "modulo_id": "circulo_mohr",
            "entradas": {"sigma_x_MPa": 80, "sigma_y_MPa": -20, "tau_xy_MPa": 35, "theta_graus": 10},
        }
    )
    assert sugestao is not None
    assert sugestao["modelo_id"] == "seguranca_vm"
    assert "Sy_MPa" not in sugestao["entradas"]


def test_mohr_3d_nao_sugere_modelo_plano():
    sugestao = sugerir_de_registro(
        {
            "modulo": "Círculo de Mohr",
            "modulo_id": "circulo_mohr",
            "entradas": {
                "sigma_x_MPa": 80,
                "sigma_y_MPa": -20,
                "sigma_z_MPa": 10,
                "tau_xy_MPa": 35,
                "tau_xz_MPa": 0,
                "tau_yz_MPa": 0,
            },
        }
    )
    assert sugestao is None
