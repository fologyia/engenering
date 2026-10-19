"""Qual momento do Simulation é o do eixo forte: pela seção (a direção 1 do Simulation na aresta
reta mais longa — medida pela macro v6 ou tirada do catálogo) e pelas tensões (o módulo
resistente S = M/σ que o próprio Simulation usou). No modelo real do usuário, a regra antiga (o
momento que domina) trocava o eixo dos pilares W 200 × 31,3: o M₁ dominava no PP, mas é o fraco."""

from __future__ import annotations

import pytest

from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import section_catalog as sc

VIGA = "Viga-1(Viga[1])"


def corpo(alma=(0.0, 1.0, 0.0), direcao_1=None, folga=30.0, secao=(313.0, 102.0)):
    return ld.CorpoDoModelo(
        "Viga[1]", "W<1>", "W 310 x 32,7", (0.0, 0.0, 0.0), (4.0, 0.0, 0.0), 4.0,
        forma=ld.FORMA_BARRA, secao_mm=secao, direcao_secao=alma, direcao_1=direcao_1,
        folga_da_direcao_1_mm=folga if direcao_1 else None,
    )  # fmt: skip


# ------------------------------------------------------------------ pela seção
@pytest.mark.parametrize(
    ("perfil", "esperado"),
    [
        ("W 310 x 32,7", em.EIXO_M2),  # alma bem mais alta que a mesa: a direção 1 é a alma
        ('U 8" x 17,10', em.EIXO_M2),  # costas do U: a altura toda
        ("W 200 x 46,1 (H)", em.EIXO_M1),  # H: a mesa (203) passa a alma reta (181)
    ],
)
def test_pelo_catalogo(perfil, esperado):
    assert ld.eixo_forte_pela_secao(perfil) == (esperado, ld.EIXO_PELO_PERFIL)


def test_sem_duvida_so_com_a_macro():
    # W 200 × 35,9: alma reta ≈ mesa (o raio decide) — o catálogo não diz; a macro v6 diz.
    assert ld.eixo_forte_pela_secao("W 200 x 35,9 (H)") is None
    na_alma = ld.CorpoDoModelo(
        "P", "W", "W", (0, 0, 0), (0, 3, 0), 3.0, forma=ld.FORMA_BARRA, secao_mm=(201.0, 165.0),
        direcao_secao=(1.0, 0.0, 0.0), direcao_1=(-1.0, 0.0, 0.0), folga_da_direcao_1_mm=12.0,
    )  # fmt: skip
    assert ld.eixo_forte_pela_secao("W 200 x 35,9 (H)", na_alma) == (
        em.EIXO_M2,
        ld.EIXO_PELA_MACRO,
    )
    na_mesa = ld.CorpoDoModelo(
        "P", "W", "W", (0, 0, 0), (0, 3, 0), 3.0, forma=ld.FORMA_BARRA, secao_mm=(201.0, 165.0),
        direcao_secao=(1.0, 0.0, 0.0), direcao_1=(0.0, 0.0, 1.0), folga_da_direcao_1_mm=12.0,
    )  # fmt: skip
    assert ld.eixo_forte_pela_secao("W 200 x 35,9 (H)", na_mesa) == (
        em.EIXO_M1,
        ld.EIXO_PELA_MACRO,
    )


def test_cantoneira_tubo_e_fora_do_catalogo_nao_dizem():
    assert ld.eixo_forte_pela_secao('L 2 1/2" × 1/4"') is None
    assert ld.eixo_forte_pela_secao("") is None
    assert ld.eixo_forte_pela_secao("AL T SECTION 2.50 x 2.50 x 1.77") is None


def dados(m1=3.0, m2=1.0, eixo=em.EIXO_M1):
    """Uma viga em que o M₁ domina (a regra antiga escolheria o M₁)."""
    pontos = tuple(
        em.PontoDeEsforco(str(i + 1), fim, 0.0, 1.0, 0.5, m1, m2, 0.0)
        for i in range(2)
        for fim in ("1", "2")
    )
    return em.EsforcosDoModelo(
        casos={"PP": em.CasoImportado("PP", "PP", "pp.csv", "", "x", {VIGA: pontos})},
        membros={VIGA: em.ConfiguracaoDoMembro(perfil="W 310 x 32,7", tipo="Viga",
                                               eixo_forte=eixo)},
        eixo_vertical="Y",
    )  # fmt: skip


def test_a_secao_vence_o_momento_que_domina_e_corrige_a_tabela():
    g = ld.GeometriaDoModelo(corpos=(corpo(),))
    d = dados()
    (lb,) = ld.ler_barras(d, g)
    assert (lb.eixo_forte, lb.origem_do_eixo) == (em.EIXO_M2, ld.EIXO_PELO_PERFIL)
    achados = ld.diagnosticar(d, pc.PlanoDeCargas(), g, [lb])
    trocado = next(a for a in achados if a.titulo == "Eixo forte trocado")
    assert trocado.nivel == pc.NIVEL_ERRO and trocado.barras == (VIGA,)
    corrigido, mudaram = ld.aplicar_sugestoes(d, [lb])
    assert mudaram == 1 and corrigido.membros[VIGA].eixo_forte == em.EIXO_M2
    assert not [a for a in ld.diagnosticar(corrigido, pc.PlanoDeCargas(), g)
                if a.titulo == "Eixo forte trocado"]  # fmt: skip


def test_sem_a_secao_fica_a_regra_antiga_e_nao_troca_a_escolha():
    d = em.EsforcosDoModelo(
        casos=dados().casos,
        membros={VIGA: em.ConfiguracaoDoMembro(perfil="", tipo="Viga", eixo_forte=em.EIXO_M2)},
        eixo_vertical="Y",
    )
    (lb,) = ld.ler_barras(d)
    assert (lb.eixo_forte, lb.origem_do_eixo) == (em.EIXO_M1, ld.EIXO_PELO_MOMENTO)
    corrigido, _ = ld.aplicar_sugestoes(d, [lb])
    assert corrigido.membros[VIGA].eixo_forte == em.EIXO_M2  # tipo já escolhido: não mexe


# ------------------------------------------------------------------ pelas tensões
def arquivos(eixo_forte_real=em.EIXO_M2):
    """Forças e tensões do mesmo estudo: σ = M/S com o S do perfil em cada direção."""
    p = sc.obter_perfil("W 310 x 32,7")
    s_forte, s_fraco = p.sx_mm3, p.sy_mm3
    s1, s2 = (s_fraco, s_forte) if eixo_forte_real == em.EIXO_M2 else (s_forte, s_fraco)
    forcas, tensoes = [], []
    for i in range(3):
        for fim in ("1", "2"):
            m1, m2 = 1.0 + i, 4.0 + i
            forcas.append(em.PontoDeEsforco(str(i + 1), fim, 0.0, 1.0, 0.5, m1, m2, 0.0))
            tensoes.append(em.TensaoDaViga(str(i + 1), fim, 0.0, m1 * 1e6 / s1, m2 * 1e6 / s2,
                                           0.0, 0.0))  # fmt: skip
    f = em.ArquivoLido(em.TIPO_VIGAS, "f.csv", "Estudo", "", "a", {VIGA: tuple(forcas)})
    t = em.ArquivoLido(em.TIPO_TENSOES_VIGA, "t.csv", "Estudo", "", "b",
                       tensoes_da_viga={VIGA: tuple(tensoes)})  # fmt: skip
    return f, t


def test_s_do_simulation_mostra_o_eixo_trocado():
    f, t = arquivos(em.EIXO_M2)
    errado = em.com_membros(dados(), {VIGA: em.ConfiguracaoDoMembro(
        perfil="W 310 x 32,7", tipo="Viga", eixo_forte=em.EIXO_M1)})  # fmt: skip
    achados = ld.conferir_tensoes([f, t], errado)
    trocado = next(a for a in achados if "eixo forte trocado" in a.titulo)
    assert trocado.nivel == pc.NIVEL_ERRO and "o forte é o Momento 2" in trocado.texto
    certo = em.com_membros(errado, {VIGA: em.ConfiguracaoDoMembro(
        perfil="W 310 x 32,7", tipo="Viga", eixo_forte=em.EIXO_M2)})  # fmt: skip
    titulos = [a.titulo for a in ld.conferir_tensoes([f, t], certo)]
    assert "Estudo: eixo forte confere pelas tensões" in titulos
    assert not [x for x in titulos if "módulo resistente" in x]


def test_modulo_do_simulation_diferente_do_perfil():
    f, t = arquivos(em.EIXO_M2)
    outro = em.com_membros(dados(), {VIGA: em.ConfiguracaoDoMembro(
        perfil="W 310 x 52,0", tipo="Viga", eixo_forte=em.EIXO_M2)})  # fmt: skip
    titulos = [a.titulo for a in ld.conferir_tensoes([f, t], outro)]
    assert "Estudo: módulo resistente do Simulation diferente do perfil" in titulos
