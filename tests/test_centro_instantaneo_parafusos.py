"""Grupo de parafusos excêntrico pelo centro instantâneo de rotação (AISC Manual, Parte 7).

Conferido com o exemplo da Tabela 7-8 do AISC Manual (2 linhas de 6 parafusos, gabarito 5,5 in,
passo 3 in, carga vertical a 16 in: C = 3,55) e com a verificação da IDEA StatiCa "Bracket plate
connections (AISC)", que tem o mesmo grupo dos dois lados da coluna e chega a 172,6 kips pelo
cálculo tradicional: 2 × 3,55 × 24,3 kips (7/8" A325-N, corte simples).
"""

from __future__ import annotations

import json
import math

import pytest

from core import bolted_connection as bc
from core import bolted_joint_check as chk
from core.record_charts import imagens_do_registro

POL = 25.4


def grade_em_polegadas(linhas: int, por_linha: int, gabarito: float, passo: float):
    return [(i * gabarito * POL, k * passo * POL) for i in range(linhas) for k in range(por_linha)]


def test_exemplo_da_tabela_7_8_do_aisc():
    coords = grade_em_polegadas(2, 6, 5.5, 3.0)
    grupo = bc.grupo_pelo_centro_instantaneo(
        coords, V=1.0, N=0.0, M=16 * POL / 1000, r_parafuso=1.0
    )
    assert grupo.convergiu and not grupo.concentrico
    assert grupo.C == pytest.approx(3.55, abs=0.01)
    # IDEA StatiCa (cálculo tradicional): dois grupos iguais, 7/8" A325-N, φr_n = 24,3 kips.
    assert 2 * grupo.C * 24.3 == pytest.approx(172.6, abs=0.5)
    # O centro fica do lado oposto à carga, na altura do centro do grupo.
    assert grupo.x_mm < 0 and grupo.y_mm == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize("linhas,por_linha", [(1, 2), (1, 4), (2, 3), (3, 3), (2, 6)])
@pytest.mark.parametrize("excentricidade", [50.0, 150.0, 400.0])
@pytest.mark.parametrize("angulo", [0.0, 30.0, 75.0])
def test_centro_instantaneo_aguenta_pelo_menos_o_do_elastico(
    linhas, por_linha, excentricidade, angulo
):
    coords = grade_em_polegadas(linhas, por_linha, 3.0, 3.0)
    p = 10.0
    N, V = p * math.sin(math.radians(angulo)), p * math.cos(math.radians(angulo))
    M = p * excentricidade / 1000
    r = 20.0
    grupo = bc.grupo_pelo_centro_instantaneo(coords, V=V, N=N, M=M, r_parafuso=r)
    elastico = bc.grupo_excentrico_elastico(coords, V=V, N=N, M=M)
    assert grupo.convergiu
    # Na curva do AISC o parafuso mais afastado chega a R(Δ_máx) = 0,98·R_ult, não a R_ult: com
    # todos os parafusos à mesma distância (2 parafusos, carga perto do centro) o centro
    # instantâneo fica até 1,8 % abaixo do elástico; com mais parafusos, acima.
    assert grupo.fator >= r / elastico["R_max"] * bc.forca_relativa_no_parafuso(1.0) * (1 - 1e-9)
    assert grupo.C is not None and grupo.C <= len(coords) + 1e-9


ARRANJOS = {
    "1x2": [(0.0, 0.0), (0.0, 76.0)],
    "1x5": [(0.0, 76.0 * k) for k in range(5)],
    "2x6": [(70.0 * i, 76.0 * k) for i in range(2) for k in range(6)],
    "livre": [(0.0, 0.0), (90.0, 10.0), (40.0, 120.0), (150.0, 160.0), (-30.0, 200.0)],
}


@pytest.mark.parametrize("nome", list(ARRANJOS))
def test_busca_fecha_de_carga_quase_centrada_a_muito_excentrica(nome):
    """Com pouca excentricidade o resíduo some longe do grupo sem haver equilíbrio: a busca não
    pode correr para lá. Quase centrada (até 5 % do raio do grupo), vale o elástico."""
    coords = ARRANJOS[nome]
    for e in (0.1, 1.0, 5.0, 20.0, 150.0, 2000.0):
        for angulo in range(0, 360, 30):
            N, V = 10 * math.cos(math.radians(angulo)), 10 * math.sin(math.radians(angulo))
            M = 10 * e / 1000 * (1 if angulo % 60 else -1)
            grupo = bc.grupo_pelo_centro_instantaneo(coords, V=V, N=N, M=M, r_parafuso=20.0)
            elastico = bc.grupo_excentrico_elastico(coords, V=V, N=N, M=M)
            assert grupo.convergiu, (e, angulo)
            assert grupo.fator >= 20.0 / elastico["R_max"] * bc.forca_relativa_no_parafuso(1.0) * (
                1 - 1e-6
            ), (e, angulo)


def test_carga_quase_centrada_na_ligacao_fica_no_elastico_sem_alerta():
    coords = ARRANJOS["2x6"]
    # N pela linha dos parafusos com 1 mm de excentricidade: a busca não fecha, vale o elástico.
    grupo = bc.grupo_pelo_centro_instantaneo(coords, V=0.0, N=10.0, M=0.01, r_parafuso=20.0)
    assert grupo.pelo_elastico and grupo.convergiu
    entrada = chk.EntradaLigacao(
        designacao="M22", coordenadas=tuple(coords), N=10.0, M=0.01, e=40.0,
        metodo_grupo=chk.METODO_CENTRO_INSTANTANEO,
    )  # fmt: skip
    nomes = [v.nome for v in chk.verificar_ligacao(entrada).verificacoes]
    assert "Parafuso crítico — min(corte; contato/rasgamento)" in nomes
    assert "Centro instantâneo de rotação" not in nomes


def test_carga_pelo_centro_vale_todos_os_parafusos():
    coords = grade_em_polegadas(2, 3, 3.0, 3.0)
    grupo = bc.grupo_pelo_centro_instantaneo(coords, V=30.0, N=40.0, M=0.0, r_parafuso=20.0)
    assert grupo.concentrico and grupo.C == 6
    assert grupo.fator == pytest.approx(6 * 20.0 / 50.0)


def test_so_momento_gira_em_torno_do_centro_do_grupo():
    coords = grade_em_polegadas(2, 2, 3.0, 3.0)  # quatro parafusos no mesmo raio
    r = 20.0
    grupo = bc.grupo_pelo_centro_instantaneo(coords, V=0.0, N=0.0, M=2.0, r_parafuso=r)
    rho = math.hypot(1.5 * POL, 1.5 * POL)
    m_rd = 4 * r * bc.forca_relativa_no_parafuso(1.0) * rho / 1000
    assert grupo.C is None and grupo.convergiu
    assert (grupo.x_mm, grupo.y_mm) == pytest.approx((0.0, 0.0), abs=1e-6)
    assert grupo.fator * 2.0 == pytest.approx(m_rd, rel=1e-6)


def test_carga_muito_afastada_tende_ao_momento_puro():
    coords = grade_em_polegadas(2, 6, 5.5, 3.0)
    puro = bc.grupo_pelo_centro_instantaneo(coords, V=0.0, N=0.0, M=1.0, r_parafuso=1.0)
    m_rd = puro.fator * 1.0  # kN·m
    e = 50_000.0  # mm
    longe = bc.grupo_pelo_centro_instantaneo(coords, V=1.0, N=0.0, M=e / 1000, r_parafuso=1.0)
    assert longe.C * e / 1000 == pytest.approx(m_rd, rel=0.01)


def test_lei_de_crawford_e_kulak():
    assert bc.forca_relativa_no_parafuso(0.0) == 0.0
    assert bc.forca_relativa_no_parafuso(1.0) == pytest.approx((1 - math.exp(-3.4)) ** 0.55)
    assert bc.DELTA_MAX_MM == pytest.approx(8.636)


def test_um_parafuso_nao_resiste_a_momento():
    grupo = bc.grupo_pelo_centro_instantaneo([(0.0, 0.0)], V=1.0, N=0.0, M=0.1, r_parafuso=10.0)
    assert grupo.fator == 0.0


# ------------------------------------------------------------------ na verificação da ligação
def excentrica(**mudancas) -> chk.EntradaLigacao:
    base = dict(designacao="M22", V=60.0, excentricidade_mm=150.0, n_lin=3, n_col=2)
    base.update(mudancas)
    return chk.EntradaLigacao(**base)


def test_ligacao_pelo_centro_instantaneo_aproveita_mais_o_grupo():
    elastico = chk.verificar_ligacao(excentrica())
    instantaneo = chk.verificar_ligacao(excentrica(metodo_grupo=chk.METODO_CENTRO_INSTANTANEO))
    nomes = {v.nome: v for v in instantaneo.verificacoes}
    linha = nomes["Grupo pelo centro instantâneo — min(corte; contato/rasgamento)"]
    referencia = nomes["Parafuso crítico pelo método elástico (referência)"]
    assert referencia.status == "INFO" and referencia.aproveitamento is None
    da_elastica = next(
        v for v in elastico.verificacoes if v.nome.startswith("Parafuso crítico — min")
    )
    assert linha.aproveitamento < da_elastica.aproveitamento
    assert "C·r" in linha.formula and "centro instantâneo a (" in linha.formula
    assert instantaneo.forcas["C_centro_instantaneo"] > 0
    assert any("AISC Manual, Parte 7" in eq for eq in instantaneo.equacoes)
    # O deslizamento continua pelo elástico: a força de serviço é a mesma nos dois métodos.
    assert instantaneo.forcas["R_max_ELS_kN"] == elastico.forcas["R_max_ELS_kN"]


def test_sem_momento_o_metodo_nao_muda_nada():
    sem_momento = excentrica(excentricidade_mm=None, V=60.0, N=20.0)
    a = chk.verificar_ligacao(sem_momento)
    b = chk.verificar_ligacao(
        chk.EntradaLigacao(
            **{
                **chk.entrada_para_dicionario(sem_momento),
                "metodo_grupo": chk.METODO_CENTRO_INSTANTANEO,
            }
        )  # fmt: skip
    )
    assert [v.nome for v in a.verificacoes] == [v.nome for v in b.verificacoes]


def test_metodo_desconhecido_e_recusado():
    with pytest.raises(ValueError, match="Método do grupo"):
        chk.verificar_ligacao(excentrica(metodo_grupo="Outro"))


def test_registro_e_memorial_com_o_centro_instantaneo():
    entrada = excentrica(metodo_grupo=chk.METODO_CENTRO_INSTANTANEO)
    resultado = chk.verificar_ligacao(entrada)
    registro = json.loads(json.dumps(chk.registro_ligacao(entrada, resultado, None)))
    assert registro["entradas"]["metodo_do_grupo"] == chk.METODO_CENTRO_INSTANTANEO
    assert "centro instantâneo de rotação (AISC Manual, Parte 7" in registro["metodo"]
    assert any("Tabelas 7-6 a 7-13" in ref for ref in registro["referencias"])
    assert any("pelo centro instantâneo" in p for p in registro["premissas"])
    imagens, aviso = imagens_do_registro(registro, {})
    assert aviso == "" and len(imagens) == 1
    # A entrada gravada traz o método; registros antigos (sem ele) ficam no elástico.
    gravada = registro["resultados"]["figura_parafusos"]["entrada"]
    assert chk.entrada_de_dicionario(gravada).metodo_grupo == chk.METODO_CENTRO_INSTANTANEO
    antiga = {k: v for k, v in gravada.items() if k != "metodo_grupo"}
    assert chk.entrada_de_dicionario(antiga).metodo_grupo == chk.METODO_ELASTICO


def test_registro_elastico_nao_muda():
    entrada = excentrica()
    registro = chk.registro_ligacao(entrada, chk.verificar_ligacao(entrada), None)
    assert "metodo_do_grupo" not in registro["entradas"]
    assert registro["metodo"].startswith("Grupo de parafusos pelo método elástico")
