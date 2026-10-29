"""Casos de aceite dos cálculos, conferidos ao vivo na Central de validação.

Cada caso é um número que o cálculo tem de reproduzir (conta à mão, exemplo de norma ou pedido do
usuário), com a tolerância e a fonte. A Central de validação roda todos a cada abertura — a versão
web não roda pytest —, e ``tests/test_casos_de_aceite.py`` roda os mesmos no CI.

Sem Streamlit.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any

from core import bolted_connection as bc
from core import bolted_joint_check as chk

NBR_2025 = "NBR8800_2024"  # o código interno da NBR 8800:2025
FONTE_PARAFUSOS = "Casos A a E do pedido do usuário (28/10/2026), conferidos à mão"


@dataclass(frozen=True)
class CasoDeAceite:
    modulo: str
    caso: str
    grandeza: str
    esperado: float
    calcular: Callable[[], float]
    tolerancia: float = 0.005  # relativa
    fonte: str = FONTE_PARAFUSOS


@dataclass(frozen=True)
class ResultadoDoCaso:
    caso: CasoDeAceite
    obtido: float | None
    erro: str = ""

    @property
    def diferenca(self) -> float | None:
        if self.obtido is None or self.caso.esperado == 0:
            return None
        return self.obtido / self.caso.esperado - 1

    @property
    def passou(self) -> bool:
        return self.diferenca is not None and abs(self.diferenca) <= self.caso.tolerancia


def _caso_a() -> chk.ResultadoLigacao:
    return chk.verificar_ligacao(
        chk.EntradaLigacao(
            norma=NBR_2025,
            designacao="M16",
            grau="A325",
            t=6.35,
            aco="ASTM A36",
            e=35.0,
            s=60.0,
            g=60.0,
            n_lin=1,
            n_col=2,
            N=5.0,
            V=15.0,
            gama_f=1.4,
            superficie="galvanizada_sem_tratamento",
        )
    )


FONTE_M22 = "Caso M22 do usuário (memorial de 28/10/2026), conferido à mão"


def _caso_m22(**mudancas: Any) -> chk.ResultadoLigacao:
    """M22 A325, A36, t = 6,35, 2 planos, 1 × 2, s = 60, e = 35, N = 0,2, V = 17, γ_f = 1,4."""
    base = chk.EntradaLigacao(
        norma=NBR_2025,
        N=0.2,
        V=17.0,
        gama_f=1.4,
        designacao="M22",
        grau="A325",
        n_planos=2,
        t=6.35,
        aco="ASTM A36",
        n_lin=1,
        n_col=2,
        s=60.0,
        e=35.0,
        deformacao_limitada=False,
        superficie="galvanizada_sem_tratamento",
        A_g=548.0,
        e_c=13.0,
        chapa_largura=108.0,
        chapa_furos=1,
        peca_por_esbeltez=True,
    )
    return chk.verificar_ligacao(replace(base, **mudancas))


def _alavanca(f_u: float) -> float:
    return bc.alavanca_2025(
        a=35, b=35, p=60, d_b=16, d_f=18, t=6.35, f_u=f_u, F_t0_Sd=2.5, F_t_Rd=92.7
    ).t_rigida_mm


def _chapa() -> bc.ChapaDeLigacao:
    return bc.chapa_de_ligacao(70, 6.35, 1, 18, 250, 400, NBR_2025)


def casos() -> tuple[CasoDeAceite, ...]:
    P = "Projeto de parafusos"
    F_t_Rd = lambda: bc.resist_tracao_parafuso(16, "A325", NBR_2025)  # noqa: E731
    F_v_Rd = lambda: bc.resist_corte(16, "A325", NBR_2025)  # noqa: E731
    return (
        CasoDeAceite(
            P,
            "A — M16 A325, 1×2, A36",
            "F_v,Rd (kN)",
            55.6,
            lambda: _caso_a().resistencias["F_v_Rd_kN"],
        ),
        CasoDeAceite(
            P,
            "A — M16 A325, 1×2, A36",
            "F_c,Rd, ℓ_f = 26 mm (kN)",
            58.7,
            lambda: _caso_a().resistencias["F_c_Rd_critico_kN"],
        ),
        CasoDeAceite(
            P,
            "A — M16 A325, 1×2, A36",
            "Parafuso crítico ELU (kN)",
            11.07,
            lambda: _caso_a().forcas["R_max_ELU_kN"],
        ),
        CasoDeAceite(
            P,
            "A — M16 A325, 1×2, A36",
            "Parafuso crítico ELS (kN)",
            7.91,
            lambda: _caso_a().forcas["R_max_ELS_kN"],
        ),
        CasoDeAceite(
            P,
            "A — M16 A325, 1×2, A36",
            "F_f,Rk (kN)",
            14.56,
            lambda: _caso_a().resistencias["F_f_Rk_kN"],
        ),
        CasoDeAceite(P, "B — tração M16 A325", "A_b (mm²)", 201.06, lambda: bc.area_bruta(16)),
        CasoDeAceite(P, "B — tração M16 A325", "A_be (mm²)", 150.80, lambda: bc.area_efetiva(16)),
        CasoDeAceite(P, "B — tração M16 A325", "F_t,Rd (kN)", 92.7, F_t_Rd),
        CasoDeAceite(
            P,
            "B — tração M16 A325",
            "Interação (1 kN; 15 kN)",
            0.073,
            lambda: bc.interacao_tracao_corte(1.0, F_t_Rd(), 15.0, F_v_Rd()),
            0.01,
        ),
        CasoDeAceite(
            P,
            "B — tração M16 A325",
            "Limite da Tab. 12 (kN)",
            95.1,
            lambda: bc.limite_tracao_tabela(16, "A325", NBR_2025, True, 15.0),
        ),
        CasoDeAceite(P, "C — placa rígida", "t_mín com f_u 400 (mm)", 3.52, lambda: _alavanca(400)),
        CasoDeAceite(P, "C — placa rígida", "t_mín com f_u 250 (mm)", 4.45, lambda: _alavanca(250)),
        CasoDeAceite(
            P,
            "D — deslizamento",
            "F_f,Rd ELU, F_t,Sd = 1 kN (kN)",
            16.97,
            lambda: bc.resist_deslizamento(91, 0.20, NBR_2025, nivel="elu", F_t=1.0, gama_e=1.20),
        ),
        CasoDeAceite(
            P,
            "D — deslizamento",
            "F_f,Rk ELS, F_t,Sk = 0,7 kN (kN)",
            14.42,
            lambda: bc.resist_deslizamento(91, 0.20, NBR_2025, F_t=0.7),
        ),
        CasoDeAceite(P, "E — chapa de ligação 70 × 6,35", "A_g (mm²)", 444.5, lambda: _chapa().A_g),
        CasoDeAceite(P, "E — chapa de ligação 70 × 6,35", "A_n (mm²)", 317.5, lambda: _chapa().A_n),
        CasoDeAceite(
            P,
            "E — chapa de ligação 70 × 6,35",
            "0,85·A_g (mm²)",
            377.8,
            lambda: 0.85 * _chapa().A_g,
        ),
        CasoDeAceite(
            P,
            "E — chapa de ligação 70 × 6,35",
            "Escoamento (kN)",
            101.0,
            lambda: _chapa().escoamento_kN,
        ),
        CasoDeAceite(
            P,
            "E — chapa de ligação 70 × 6,35",
            "Ruptura com A_n (kN)",
            94.1,
            lambda: _chapa().ruptura_kN,
        ),
        CasoDeAceite(
            P,
            "M22 — 2 planos, 1×2, A36",
            "F_v,Rd (kN)",
            210.3,
            lambda: _caso_m22().resistencias["F_v_Rd_kN"],
            fonte=FONTE_M22,
        ),
        CasoDeAceite(
            P,
            "M22 — 2 planos, 1×2, A36",
            "F_c,Rd, deformação não limitada (kN)",
            64.91,
            lambda: _caso_m22().resistencias["F_c_Rd_critico_kN"],
            fonte=FONTE_M22,
        ),
        CasoDeAceite(
            P,
            "M22 — 2 planos, 1×2, A36",
            "F_c,Rd, deformação limitada (kN)",
            51.93,
            lambda: _caso_m22(deformacao_limitada=True).resistencias["F_c_Rd_critico_kN"],
            fonte=FONTE_M22,
        ),
        CasoDeAceite(
            P,
            "M22 — 2 planos, 1×2, A36",
            "F_f,Rk com 1 plano (kN)",
            28.16,
            lambda: _caso_m22(n_planos=1).resistencias["F_f_Rk_kN"],
            fonte=FONTE_M22,
        ),
        CasoDeAceite(
            P,
            "M22 — 2 planos, 1×2, A36",
            "Regra dos 75%: R_lig (kN)",
            112.64,
            lambda: _caso_m22().resistencias["R_ligacao_anglo_kN"],
            fonte=FONTE_M22,
        ),
        *_casos_de_solda(),
    )


FONTE_SOLDA = "Exercícios de solda enviados pelo usuário (29/10/2026): o valor da apostila"
FONTE_SOLDA_NORMA = (
    "Exercícios de solda (29/10/2026) refeitos pela NBR 8800:2025, conferidos à mão: a apostila "
    "usa o metal-base pela face de fusão (0,60·d_w·L·f_y/γ_a1), que a Tabela 9 não pede no filete"
)


def _grandeza(r: Any, nome: str) -> float:
    """O valor resistente (ou adotado) de uma linha do resultado da ligação, pelo começo do nome."""
    linha = next(v for v in r.verificacoes if v.nome.startswith(nome))
    return float(linha.resistente if linha.resistente is not None else linha.solicitante)


def _casos_de_solda() -> tuple[CasoDeAceite, ...]:
    from core import ligacoes as lg
    from core import ligacoes_soldadas as ls
    from core import soldas as sd

    S = "Ligações soldadas"
    ex1 = ls.EntradaBarraSoldada(
        peca=ls.PECA_CHAPA, largura_mm=50.0, t_peca_mm=9.525, duas_pecas=True, t_no_mm=12.7,
        perna_mm=8.0, n_t_sd_kN=40.0, com_apoio=False,
    )  # fmt: skip
    ex3 = ls.EntradaChapaNoApoio(
        modo=ls.MODO_VERIFICAR, tipo_solda=ls.TIPO_TOTAL, intermitente=False, n_sd_kN=100.0
    )
    filete = lambda perna: 10 * sd.resistencia_filete_por_mm(perna, 485.0, 1.35)  # noqa: E731
    return (
        CasoDeAceite(
            S,
            "1 — duas talas sobrepostas",
            "Filete de 8 mm, E70 (kN/cm)",
            12.192,
            lambda: filete(8.0),
            fonte=FONTE_SOLDA,
        ),  # fmt: skip
        CasoDeAceite(
            S,
            "1 — duas talas sobrepostas",
            "Filete adotado (mm), com cobrimento ≥ 5·t",
            50.0,
            lambda: lg.calcular(ex1).grandezas["l_dorso_mm"],
            fonte=FONTE_SOLDA_NORMA,
        ),  # fmt: skip
        CasoDeAceite(
            S,
            "2 — filete intermitente",
            "Segmento adotado (mm)",
            40.0,
            lambda: lg.calcular(ls.EntradaChapaNoApoio()).grandezas["segmento_mm"],
            fonte=FONTE_SOLDA,
        ),  # fmt: skip
        CasoDeAceite(
            S,
            "3 — penetração total",
            "F_Rd = A_MB·f_y/γ_a1 (kN)",
            288.636,
            lambda: _grandeza(lg.calcular(ex3), "Penetração total: tração"),
            fonte=FONTE_SOLDA,
        ),  # fmt: skip
        CasoDeAceite(
            S,
            "4 — cantoneira na chapa de nó",
            "Solda pelo metal da solda, 4 mm (mm)",
            164.04,
            lambda: 100.0 / (filete(4.0) / 10),
            fonte=FONTE_SOLDA,
        ),  # fmt: skip
        CasoDeAceite(
            S,
            "4 — cantoneira na chapa de nó",
            "Largura mínima da chapa de nó (mm)",
            55.0,
            lambda: lg.calcular(ls.EntradaBarraSoldada()).grandezas["largura_minima_no_mm"],
            fonte=FONTE_SOLDA,
        ),  # fmt: skip
        CasoDeAceite(
            S,
            "4 — cantoneira na chapa de nó",
            "Filete do dorso adotado (mm)",
            120.0,
            lambda: lg.calcular(ls.EntradaBarraSoldada()).grandezas["l_dorso_mm"],
            fonte=FONTE_SOLDA_NORMA,
        ),  # fmt: skip
        CasoDeAceite(
            S,
            "4 — cantoneira na chapa de nó",
            "Filete da borda adotado (mm)",
            50.0,
            lambda: lg.calcular(ls.EntradaBarraSoldada()).grandezas["l_borda_mm"],
            fonte=FONTE_SOLDA_NORMA,
        ),  # fmt: skip
        CasoDeAceite(
            S,
            "4 — chapa de nó no pilar",
            "Solda adotada de cada lado (mm)",
            50.0,
            lambda: lg.calcular(ls.EntradaBarraSoldada()).grandezas["l_apoio_mm"],
            fonte=FONTE_SOLDA_NORMA,
        ),  # fmt: skip
    )


def rodar(lista: Sequence[CasoDeAceite] | None = None) -> list[ResultadoDoCaso]:
    """Calcula cada caso; uma falha vira o erro do caso, sem derrubar os outros."""
    saida = []
    for caso in lista if lista is not None else casos():
        try:
            saida.append(ResultadoDoCaso(caso, float(caso.calcular())))
        except Exception as erro:  # o caso que quebra aparece como reprovado, com o motivo
            saida.append(ResultadoDoCaso(caso, None, f"{type(erro).__name__}: {erro}"))
    return saida


COLUNAS = ("Módulo", "Caso", "Grandeza", "Esperado", "Obtido", "Diferença (%)", "Passou")


def linhas(resultados: Sequence[ResultadoDoCaso]) -> list[list[object]]:
    return [
        [
            r.caso.modulo,
            r.caso.caso,
            r.caso.grandeza,
            r.caso.esperado,
            r.obtido,
            None if r.diferenca is None else 100 * r.diferenca,
            "sim" if r.passou else f"NÃO{(' — ' + r.erro) if r.erro else ''}",
        ]
        for r in resultados
    ]
