"""Os desenhos acrescentados aos módulos (pedido de 30/10/2026: "imagens bem feitas em todos os
módulos separados, tirando o de fadiga").

Projeto de parafusos (planta e corte), Reações nas bases (planta dos pés), Lista de material
(quadro de massa), Vigas e eixos (esquema do modelo) e os elementos de tensão (Análise estática,
Círculo de Mohr e Assistente de cargas).
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from core import beam_analysis as vb
from core import bolted_joint_check as chk
from core import desenho_da_viga as dv
from core import desenho_lista_material as dl
from core import desenho_parafusos as dp
from core import desenho_reacoes as dr
from core import desenho_tensoes as dt
from core import lista_de_material as lm
from core import reacoes_nas_bases as rb


def _png(desenho) -> Image.Image:
    imagem = Image.open(io.BytesIO(desenho.png))
    assert imagem.format == "PNG" and imagem.size == (2 * desenho.largura_px, 2 * desenho.altura_px)
    return imagem


# ------------------------------------------------------------------ parafusos
@pytest.mark.parametrize(
    "entrada",
    [
        chk.EntradaLigacao(V=50, N=20, M=1.5, n_lin=3, n_col=2),
        chk.EntradaLigacao(N=120, n_lin=2, n_col=3, n_planos=2, designacao="M16", e_v=40.0),
        chk.EntradaLigacao(
            V=30, M=2.0, coordenadas=((0, 0), (80, 0), (40, 60), (0, 120), (80, 120))
        ),
        chk.EntradaLigacao(V=10, n_lin=1, n_col=1),
    ],
)
def test_ligacao_parafusada_tem_planta_e_corte(entrada):
    r = chk.verificar_ligacao(entrada)
    desenho = dp.figura_parafusos(r)
    assert desenho is not None
    _png(desenho)
    mais_carregado = max(range(len(r.forcas_parafusos)), key=lambda i: r.forcas_parafusos[i][2])
    assert f"nº {mais_carregado + 1}" in desenho.legenda


# ------------------------------------------------------------------ reações nas bases
def _reacoes(com_posicao: bool = True) -> rb.ReacoesNasBases:
    pes, acoes = [], []
    for k, (x, z) in enumerate(((0.0, 0.0), (4.0, 0.0), (0.0, 3.0), (4.0, 3.0)), start=1):
        rotulo = f"A{k}"
        pes.append(rb.Pe(rotulo, (x, 0.0, z) if com_posicao else None, pilar=f"P{k}"))
        acoes.append(
            rb.AcaoNoPe(rotulo, "PP", (0.0, -20.0 * k, 0.0), (0.0, 0.0, 0.0), rb.FONTE_APOIO)
        )
        acoes.append(
            rb.AcaoNoPe(rotulo, "W0", (4.0, 6.0 * (-1) ** k, 0.0), (0.3, 0.0, 0.1), rb.FONTE_APOIO)
        )
    return rb.ReacoesNasBases(tuple(pes), tuple(acoes), ("PP", "W0"), eixo_vertical="Y")


@pytest.mark.parametrize("caso", ["PP", "W0", "SC"])
def test_planta_das_reacoes(caso):
    desenho = dr.figura_das_reacoes(_reacoes(), caso)
    assert desenho is not None and caso in desenho.titulo
    _png(desenho)


def test_sem_posicao_dos_pes_nao_ha_planta():
    assert dr.figura_das_reacoes(_reacoes(com_posicao=False), "PP") is None


def test_casos_diferentes_dao_plantas_diferentes():
    r = _reacoes()
    assert dr.figura_das_reacoes(r, "PP").png != dr.figura_das_reacoes(r, "W0").png


# ------------------------------------------------------------------ lista de material
def _resumo(n_perfis: int = 3) -> lm.ResumoDaLista:
    perfis = ["W 250 x 32,7", "W 200 x 15", 'L 2" × 1/4"', "W 150 x 13", "W 310 x 21"]
    itens = [
        lm.ItemDaLista(f"P{k}", lm.TIPO_PERFIL, perfis[k % len(perfis)], 2 + k, 3.0 + k)
        for k in range(n_perfis)
    ]
    itens.append(lm.ItemDaLista("C1", lm.TIPO_CHAPA, "Chapa de base", 4, 0.35, 350, 19.0))
    return lm.resumir(lm.com_itens(lm.ListaDeMaterial(), itens))


def test_quadro_de_massa():
    desenho = dl.figura_da_massa(_resumo())
    assert desenho is not None
    _png(desenho)


def test_lista_vazia_nao_tem_quadro():
    assert dl.figura_da_massa(lm.resumir(lm.ListaDeMaterial())) is None


def test_mais_de_doze_linhas_viram_outros():
    linhas = [dl.Linha(f"Perfil {k}", 100.0 - k) for k in range(20)]
    dobradas = dl._dobrar(linhas)
    assert len(dobradas) == dl.MAXIMO_DE_LINHAS
    assert dobradas[-1].rotulo == "Outros (9)"
    assert sum(x.massa_kg for x in dobradas) == pytest.approx(sum(x.massa_kg for x in linhas))
    assert [x.massa_kg for x in dobradas[:-1]] == sorted(
        (x.massa_kg for x in dobradas[:-1]), reverse=True
    )


@pytest.mark.parametrize(
    ("maximo", "passo"), [(785.0, 200.0), (73.0, 20.0), (9.0, 2.0), (1.2, 0.5)]
)
def test_passo_da_grade(maximo, passo):
    assert dl._passo_bonito(maximo) == pytest.approx(passo)


# ------------------------------------------------------------------ vigas e eixos
MATERIAL = vb.MaterialViga("Aço", 200_000.0, 77_000.0, 345.0)


@pytest.mark.parametrize("tipo", ["pino", "rolete", "engaste", "engaste deslizante", "apoio horizontal", "mola"])  # fmt: skip
def test_cada_tipo_de_apoio_desenhado(tipo):
    extras = {"rigidez_vertical_N_mm": 500.0} if tipo == "mola" else {}
    viga = vb.Viga(
        3000.0, vb.secao_retangular(100, 200), MATERIAL,
        apoios=(vb.Apoio(0.0, tipo, **extras), vb.Apoio(3000.0, "pino")),
        cargas_pontuais=(vb.CargaPontual(1500.0, -10_000.0),),
    )  # fmt: skip
    _png(dv.figura_da_viga(viga))


def test_todas_as_cargas_desenhadas():
    viga = vb.Viga(
        6000.0, vb.secao_retangular(150, 400), MATERIAL,
        apoios=(vb.Apoio(0.0, "pino", rotulo="A"), vb.Apoio(4500.0, "rolete", rotulo="B")),
        rotulas=(vb.Rotula(3000.0),),
        cargas_distribuidas=(
            vb.CargaDistribuida(0.0, 4500.0, -12.0),
            vb.CargaDistribuida(4500.0, 6000.0, -6.0, -15.0, caso="Sobrecarga"),
            vb.CargaDistribuida(1000.0, 2000.0, 4.0, caso="Vento"),
        ),
        cargas_pontuais=(vb.CargaPontual(2000.0, -25_000.0), vb.CargaPontual(5000.0, 8_000.0)),
        momentos=(vb.MomentoConcentrado(3000.0, 5e6), vb.MomentoConcentrado(1000.0, -2e6)),
        cargas_axiais=(vb.CargaAxial(6000.0, 15_000.0), vb.CargaAxial(0.0, -5_000.0), vb.CargaAxial(2500.0, 3_000.0)),  # fmt: skip
        torques=(vb.Torque(1000.0, 2e6), vb.Torque(4000.0, -1e6)),
        nome="Viga V1",
    )  # fmt: skip
    desenho = dv.figura_da_viga(viga)
    _png(desenho)
    assert "Viga V1" in desenho.titulo and "2 apoio(s)" in desenho.legenda


@pytest.mark.parametrize(
    ("valor", "texto"), [(1.5, "1,5"), (12.0, "12"), (0.25, "0,25"), (-0.0, "0")]
)
def test_numero_da_viga(valor, texto):
    assert dv._n(valor) == texto


# ------------------------------------------------------------------ elementos de tensão
def test_elementos_principal_e_de_cisalhamento_maximo():
    lista = dt.elementos(80.0, -40.0, 30.0, 25.0)
    assert [e.titulo for e in lista] == [
        "Nos eixos x e y", "Girado 25,0°", "Direções principais", "Cisalhamento máximo",
    ]  # fmt: skip
    principal, cisalhamento = lista[2], lista[3]
    assert principal.tau == 0.0
    assert principal.sigma_x == pytest.approx(20.0 + (60.0**2 + 30.0**2) ** 0.5)
    assert cisalhamento.sigma_x == cisalhamento.sigma_y == pytest.approx(20.0)
    assert cisalhamento.tau == pytest.approx((60.0**2 + 30.0**2) ** 0.5)
    for e in lista[2:]:
        assert -90.0 < e.angulo_graus <= 90.0


def test_sem_giro_sao_tres_elementos():
    assert len(dt.elementos(50.0, 0.0, 0.0)) == 3


@pytest.mark.parametrize(("angulo", "esperado"), [(148.3, -31.7), (-90.0, 90.0), (45.0, 45.0), (270.0, 90.0)])  # fmt: skip
def test_angulo_do_elemento_fica_entre_menos_90_e_90(angulo, esperado):
    assert dt._no_intervalo(angulo) == pytest.approx(esperado)


@pytest.mark.parametrize("estado", [(80.0, -40.0, 30.0, 25.0), (0.0, 0.0, 0.0, 0.0), (-50.0, -50.0, 0.0, 0.0)])  # fmt: skip
def test_figura_dos_elementos(estado):
    _png(dt.figura_dos_elementos(*estado))
