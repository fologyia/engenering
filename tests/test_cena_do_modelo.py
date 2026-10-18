"""A cena 3D montada com o que o projeto tem: seções do catálogo, nomes (corpo × Simulation ×
plano), cor por tipo, perfil e resultado, cargas do plano, apoios e reações das bases."""

from __future__ import annotations

import pytest

from core import cena_3d as c3
from core import cena_do_modelo as cm
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import vento_estrutura_aberta as va
from tests.test_guarda_corpo_do_modelo import LINHA, plataforma


def geometria() -> ld.GeometriaDoModelo:
    return ld.GeometriaDoModelo(corpos=tuple(plataforma()))


# ------------------------------------------------------------------ seções
@pytest.mark.parametrize(
    ("perfil", "forma"),
    [
        ("W 200 x 35,9 (H)", c3.FORMA_I),
        ('U 8" x 17,10', c3.FORMA_U),
        ('L 2 1/2" × 1/4"', c3.FORMA_L),
        ("TC ideal Ø48.3×3", c3.FORMA_TUBO_CIRCULAR),
        ("TR ideal 50×30×2", c3.FORMA_TUBO_RETANGULAR),
    ],
)
def test_secao_sai_do_catalogo(perfil, forma):
    s = cm.secao_do_perfil(perfil)
    assert s.forma == forma and s.d > 0 and s.b > 0


def test_secao_sem_perfil_usa_as_medidas_da_macro():
    s = cm.secao_do_perfil("", (210.0, 134.0))
    assert s.forma == c3.FORMA_CHEIA and s.d == pytest.approx(0.21) and s.b == pytest.approx(0.134)
    assert cm.secao_do_perfil("perfil que não existe", None).d == pytest.approx(0.1)


# ------------------------------------------------------------------ nomes
def test_elemento_do_plano_acha_o_corpo_de_todo_jeito():
    corpos = cm._corpos(geometria())
    nomes = cm.Nomes({"Borda z0": "Viga-3"})
    for texto in ("Borda z0", "Borda z0 (Viga-3)", "Viga-3", "Viga-3(Borda z0)"):
        assert nomes.corpo_do_elemento(texto, corpos) == "Borda z0", texto
    assert nomes.corpo_do_elemento("Pórtico P1 (posição 0,00 m)", corpos) == ""


# ------------------------------------------------------------------ cor
def test_cor_por_tipo_por_perfil_por_valor_e_esconder_um_tipo():
    g = geometria()
    barras, legenda, escala = cm.barras_da_cena(g, "Y")
    assert escala is None and {t for _, t in legenda} >= {"pilar", "viga"}
    assert all(b.secao is not None for b in barras)
    pilares = [b for b in barras if b.grupo == ld.TIPO_PILAR]
    assert pilares and all(b.cor == cm.CORES_POR_TIPO[ld.TIPO_PILAR] for b in pilares)
    por_perfil, legenda_perfil, _ = cm.barras_da_cena(g, "Y", cor_por=cm.COR_POR_PERFIL)
    assert [t for _, t in legenda_perfil] == ['U 8" x 17,10']  # o modelo de teste é todo em U
    assert len({b.cor for b in por_perfil}) == 1
    valores = cm.ValoresPorBarra({"Borda z0": 2.0, "Borda x0": 1.0}, "kN/m", "teste")
    barras_v, _, escala_v = cm.barras_da_cena(g, "Y", cor_por=cm.COR_POR_VENTO, valores=valores)
    assert escala_v is not None and escala_v.maximo == 2.0
    cor = {b.nome: b.cor for b in barras_v}
    assert cor["Borda z0"] != cor["Borda x0"] and cor["Interna x3"] == "#cfd5dc"
    sem_pilar, _, _ = cm.barras_da_cena(g, "Y", ocultos=[ld.TIPO_PILAR])
    assert not [b for b in sem_pilar if b.grupo == ld.TIPO_PILAR]


def test_cor_pelo_vento_calcula_barra_a_barra():
    v = cm.valores_do_vento(geometria(), "Y", va.ParametrosVento(v0_m_s=35.0), 0)
    assert v.unidade == "kN/m" and max(v.valores.values()) > 0


# ------------------------------------------------------------------ cargas do plano
def test_cargas_do_caso_vao_para_as_barras_e_o_resto_fica_listado():
    plano = pc.com_acao(
        pc.PlanoDeCargas(),
        pc.nova_acao(
            "PE",
            cargas=[
                pc.CargaDoModelo("Borda z0 (Viga-3)", 0.4, "kN/m", "Z (vertical)", comprimento_m=6),
                pc.CargaDoModelo("Viga-3(Borda z0)", 1.0, "kN", "Z (vertical)"),
                pc.CargaDoModelo("Borda x0", 0.5, "kN/m", "+X", comprimento_m=4),
                pc.CargaDoModelo("Piso", 5.0, "kN/m²", "Z (vertical)"),
                pc.CargaDoModelo("Pórtico P1", 3.0, "kN", "+X"),
            ],
        ),
    )
    nomes = cm.Nomes({"Borda z0": "Viga-3"})
    c = cm.cargas_do_caso(plano, "PE", geometria(), "Y", nomes)
    assert len(c.distribuidas) == 2 and len(c.setas) == 1 and len(c.nao_localizadas) == 2
    assert c.total_kN == pytest.approx((0.5 * 4, 0.0, -(0.4 * 6 + 1.0)))
    assert c.setas[0].vetor == (0.0, 0.0, -1.0)  # positivo para baixo
    assert any(d.rotulo for d in c.distribuidas)
    assert cm.cargas_do_caso(plano, "SC", geometria(), "Y", nomes).distribuidas == ()


# ------------------------------------------------------------------ apoios e reações
def _esforcos(momento: float) -> em.EsforcosDoModelo:
    def pontos(n_base: float) -> tuple[em.PontoDeEsforco, ...]:
        return (
            em.PontoDeEsforco("1", "Fim1", n_base, 0.3, 0.4, momento, 0.0, 0.0),
            em.PontoDeEsforco("1", "Fim2", n_base * 0.8, 0.3, 0.4, 0.0, 0.0, 0.0),
        )

    membros = {f"Viga-{i}(Pilar {i})": pontos(-10.0 * i) for i in (1, 2, 3, 4)}
    caso = em.CasoImportado("PP", "Estudo", "pp.csv", "", "", membros)
    return em.EsforcosDoModelo(
        casos={"PP": caso},
        membros={m: em.ConfiguracaoDoMembro(tipo="Pilar") for m in membros},
    )


@pytest.mark.parametrize(("momento", "tipo"), [(0.0, c3.APOIO_ARTICULADO), (2.0, c3.APOIO_ENGASTE)])
def test_reacoes_nas_bases_e_tipo_do_apoio(momento, tipo):
    g = geometria()
    dados = _esforcos(momento)
    nomes = cm.Nomes.do_projeto(g, dados)
    a = cm.apoios_e_reacoes(g, "Y", dados, nomes, "PP")
    assert len(a.apoios) == 4 and {x.tipo for x in a.apoios} == {tipo}
    assert len(a.reacoes) == 4 and a.soma_vertical_kN == pytest.approx(100.0)
    assert all(r.reacao and r.vetor[2] > 0 for r in a.reacoes)
    assert all(abs(r.ponto[2]) < 1e-9 for r in a.reacoes)  # no pé dos pilares (Y = 0 no modelo)
    assert all("H 0,5 kN" in r.rotulo for r in a.reacoes)


def test_sem_esforcos_os_apoios_saem_do_chao_sem_tipo():
    g = geometria()
    a = cm.apoios_e_reacoes(g, "Y", None, cm.Nomes({}), "")
    assert len(a.apoios) == 4 and {x.tipo for x in a.apoios} == {c3.APOIO_DESCONHECIDO}
    assert not a.reacoes and any("sem o tipo" in t for t in a.avisos)


def test_pilar_que_nao_chega_no_chao_vira_aviso():
    g = geometria()
    dados = _esforcos(0.0)
    membros = dict(dados.membros)
    membros["Viga-9(Borda z0)"] = em.ConfiguracaoDoMembro(tipo="Pilar")
    casos = {"PP": em.CasoImportado("PP", "", "", "", "", {
        **dados.casos["PP"].membros,
        "Viga-9(Borda z0)": (em.PontoDeEsforco("9", "Fim1", -1.0, 0, 0, 0, 0, 0),
                             em.PontoDeEsforco("9", "Fim2", -2.0, 0, 0, 0, 0, 0)),
    })}  # fmt: skip
    dados = em.EsforcosDoModelo(casos=casos, membros=membros)
    a = cm.apoios_e_reacoes(g, "Y", dados, cm.Nomes.do_projeto(g, dados), "PP")
    assert any("Borda z0" in t and "acima do chão" in t for t in a.avisos)


# ------------------------------------------------------------------ a cena inteira
def test_cena_completa_projeta_sem_aviso_de_geometria():
    g = geometria()
    barras, legenda, escala = cm.barras_da_cena(g, "Y")
    degraus, paineis = cm.chapas_da_cena(g, "Y")
    assert not degraus  # o modelo de teste não tem lance
    from core import guarda_corpo_do_modelo as gm

    b = gm.bordas_do_piso(g, "Y")
    gc_barras, gc_paineis = cm.guarda_corpos_da_cena(b.marcados(), "Y", 1.1)
    assert len(gc_paineis) == 4 and gc_barras
    cena = c3.Cena(barras=tuple(barras + gc_barras), paineis=tuple(paineis + gc_paineis),
                   legenda=tuple(legenda))  # fmt: skip
    d = c3.projetar(cena)
    assert not d.avisos and d.poligonos > 100
    assert min(p[1] for i in d.itens if isinstance(i, c3.Poligono2D) for p in i.pontos) >= 0
    assert LINHA > 0
