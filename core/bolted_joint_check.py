"""Verificação completa de uma ligação parafusada estrutural (sem Streamlit).

Orquestra as funções de ``core.bolted_connection`` na sequência do projeto:

1. esforços de cálculo (ELU) e de serviço (característicos);
2. força no parafuso mais carregado (grupo excêntrico elástico) ou soma por furo;
3. resistência por parafuso: min(corte, contato/rasgamento);
4. deslizamento em serviço (ligação por atrito);
5. peça: tração com C_t e colapso por rasgamento;
6. disposições construtivas e critério Anglo;
7. resumo: aproveitamento máximo, verificação governante e status geral.

Nada aqui "conserta" uma entrada em silêncio: ℓ_f ≤ 0, n_col = 1 (C_t indefinido),
A307 em ligação por atrito, superfície sem μ na norma, grupo sem rigidez ao momento
e condições fora do escopo viram linhas visíveis da tabela de verificações.

Unidades: comprimento em mm, tensão em MPa, força em kN, momento em kN·m.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from core import bolted_connection as bc
from core.bolt_design import torque_para_pre_carga
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    formatar_percentual,
    linhas_para_registro,
    status_geral,
)

NORMAS_ROTULOS = {
    "NBR8800_2008": "ABNT NBR 8800:2008",
    "NBR8800_2024": "Projeto NBR 8800:2024",
    "AISC360_LRFD": "AISC 360 (LRFD)",
    "RCSC2004": "RCSC 2004 (LRFD)",
}

SUPERFICIES_ROTULOS = {
    "galvanizada_sem_tratamento": "Galvanizada a fogo, sem tratamento (padrão Anglo)",
    "classe_C_galv_escovada": "Classe C — galvanizada escovada",
    "classe_A_laminada_limpa": "Classe A — laminada limpa",
    "classe_B_jateada": "Classe B — jateada",
}

#: Condições que esta etapa NÃO verifica. Quem marca uma delas recebe um ALERTA na tabela.
FORA_DO_ESCOPO = {
    "tracao_parafuso": "Tração nos parafusos (efeito de alavanca e interação tração + corte — NBR 6.3.3.4 e 6.3.5)",
    "furo_alargado": "Furos alargados ou alongados (deslizamento passa a ser ELU — NBR 6.3.4.3)",
    "fadiga": "Fadiga da ligação (NBR 8800, Anexo H)",
    "formado_a_frio": "Perfis formados a frio (NBR 14762)",
}

AVISOS_FIXOS = (
    "Valores da NBR 8800:2008 trazidos de memória no módulo de referência estão marcados "
    "“CONFERIR” (ver lista abaixo) e precisam ser confirmados na norma antes de emitir o documento.",
    "O torque de aperto é só uma estimativa (T ≈ K·F_Tb·d). A instalação deve ser por rotação "
    "da porca, chave calibrada ou indicador direto de tração.",
    "O grupo excêntrico usa o método elástico, que é conservador frente ao centro instantâneo de rotação.",
)


@dataclass(frozen=True)
class EntradaLigacao:
    """Dados da ligação. Esforços em kN / kN·m, geometria em mm, tensões em MPa."""

    norma: str = "NBR8800_2008"
    # Esforços no centro do grupo. N atua ao longo das linhas (x); V é transversal (y).
    N: float = 0.0
    V: float = 0.0
    M: float = 0.0
    excentricidade_mm: float | None = None  # se informada, M = V·a e o campo M é ignorado
    gama_f: float = 1.4
    valores_sao_de_calculo: bool = False
    # Parafuso
    designacao: str = "M22"
    grau: str = "A325"
    d_h_mm: float | None = None  # furo; None usa o furo-padrão da tabela (AISC 360-16 / NBR)
    rosca_no_plano: bool = True
    n_planos: int = 1
    # Partes ligadas
    t: float = 5.08
    aco: str = "ASTM A36"
    pega: float | None = None
    # Geometria (grade) ou coordenadas livres (mm, relativas a qualquer origem)
    n_lin: int = 2
    n_col: int = 2
    s: float = 70.0
    g: float = 70.0
    e: float = 70.0
    e_v: float | None = None
    coordenadas: tuple[tuple[float, float], ...] | None = None
    # Opções
    deformacao_limitada: bool = True
    superficie: str = "galvanizada_sem_tratamento"
    ligacao_por_atrito: bool = True
    C_e: float = 1.0
    patinavel_sem_pintura: bool = False
    # Peça tracionada (opcional): sem A_g e e_c a tração da peça não é calculável
    A_g: float | None = None
    e_c: float | None = None
    # Critério Anglo
    ligacao_principal: bool = True
    revestimento: str = "galvanizado_fogo"
    peca_por_esbeltez: bool = False
    # Referência de instalação (estimativa)
    K_torque: float = 0.20
    fora_do_escopo: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResultadoLigacao:
    entrada: EntradaLigacao
    verificacoes: tuple[Verificacao, ...]
    status_geral: str
    aproveitamento_max: float | None
    governante: str
    forcas: dict[str, float]
    resistencias: dict[str, float]
    intermediarios: dict[str, float]
    torque_referencia_Nm: float | None
    coordenadas: tuple[tuple[float, float], ...] = field(default_factory=tuple)
    forcas_parafusos: tuple[tuple[float, float, float], ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------------------------
def excentricidade_emenda(e: float, s: float, n_col: int) -> float:
    """Excentricidade padrão de emenda por sobreposição: a = e + (n_col − 1)·s/2."""
    return e + (n_col - 1) * s / 2.0


def distancia_minima_entre_furos(coords: Sequence[tuple[float, float]]) -> float | None:
    """Menor distância centro a centro entre dois parafusos (None com menos de dois)."""
    menor: float | None = None
    for i, (xi, yi) in enumerate(coords):
        for xj, yj in coords[i + 1 :]:
            d = math.hypot(xi - xj, yi - yj)
            if menor is None or d < menor:
                menor = d
    return menor


def _aproveitamento_governante(
    verificacoes: Sequence[Verificacao],
) -> tuple[float | None, str]:
    com_valor = [v for v in verificacoes if v.aproveitamento is not None]
    if not com_valor:
        return None, "—"
    pior = max(com_valor, key=lambda v: v.aproveitamento if v.aproveitamento is not None else 0.0)
    return pior.aproveitamento, pior.nome


def _validar(entrada: EntradaLigacao) -> None:
    if entrada.norma not in bc.NORMAS:
        raise ValueError(f"Norma inválida: {entrada.norma}.")
    if entrada.designacao not in bc.PARAFUSOS:
        raise ValueError(f"Parafuso desconhecido: {entrada.designacao}.")
    if entrada.grau not in bc.GRAUS:
        raise ValueError(f"Grau desconhecido: {entrada.grau}.")
    if entrada.aco not in bc.ACOS:
        raise ValueError(f"Aço desconhecido: {entrada.aco}.")
    if entrada.superficie not in bc.SUPERFICIES:
        raise ValueError(f"Superfície desconhecida: {entrada.superficie}.")
    for nome, valor in (("N", entrada.N), ("V", entrada.V), ("M", entrada.M)):
        if not math.isfinite(valor):
            raise ValueError(f"{nome} deve ser um número finito.")
    if not math.isfinite(entrada.gama_f) or entrada.gama_f < 1.0:
        raise ValueError("γ_f deve ser finito e ≥ 1,0.")
    for nome, valor in (("t", entrada.t), ("e", entrada.e), ("C_e", entrada.C_e)):
        if not math.isfinite(valor) or valor <= 0:
            raise ValueError(f"{nome} deve ser maior que zero.")
    if entrada.d_h_mm is not None and not (
        math.isfinite(entrada.d_h_mm) and entrada.d_h_mm >= bc.PARAFUSOS[entrada.designacao][0]
    ):
        raise ValueError("O furo d_h não pode ser menor que o diâmetro do parafuso.")
    if entrada.n_planos < 1:
        raise ValueError("O número de planos de corte deve ser ≥ 1.")
    if entrada.coordenadas is None:
        if entrada.n_lin < 1 or entrada.n_col < 1:
            raise ValueError("n_lin e n_col devem ser ≥ 1.")
        if entrada.n_col > 1 and not entrada.s > 0:
            raise ValueError("s deve ser maior que zero com mais de uma coluna.")
        if entrada.n_lin > 1 and not entrada.g > 0:
            raise ValueError("g deve ser maior que zero com mais de uma linha.")
    elif len(entrada.coordenadas) < 1:
        raise ValueError("Informe ao menos um parafuso nas coordenadas.")
    if entrada.excentricidade_mm is not None and not math.isfinite(entrada.excentricidade_mm):
        raise ValueError("A excentricidade a deve ser finita.")
    if entrada.A_g is not None and entrada.A_g <= 0:
        raise ValueError("A_g da peça deve ser maior que zero.")


def _linha(
    nome: str,
    solicitante: float | None,
    resistente: float | None,
    unidade: str,
    referencia: str,
    formula: str = "",
    status: str = "",
) -> Verificacao:
    return Verificacao(nome, solicitante, resistente, unidade, referencia, formula, status)


# ---------------------------------------------------------------------------------------------
# Verificação completa
# ---------------------------------------------------------------------------------------------
def verificar_ligacao(entrada: EntradaLigacao) -> ResultadoLigacao:
    """Executa a sequência de verificações e devolve a tabela completa."""
    _validar(entrada)
    norma = entrada.norma
    p = bc.dados_parafuso(entrada.designacao)
    d_b, e_min = p["d_b"], p["e_min"]
    d_h = entrada.d_h_mm if entrada.d_h_mm is not None else p["d_h"]
    f_y, f_u = bc.ACOS[entrada.aco]
    t = entrada.t
    grid = entrada.coordenadas is None
    linhas: list[Verificacao] = []

    if norma == "RCSC2004" and entrada.grau == "A307":
        linhas.append(
            _linha(
                "Grau do parafuso na norma escolhida",
                None,
                None,
                "—",
                "RCSC 2004 (escopo)",
                "A RCSC 2004 não cobre A307; escolha A325/A490 ou outra norma.",
                "NÃO OK",
            )
        )
        return _fechar(entrada, linhas, {}, {}, {}, (), (), None)

    # --- 1. Esforços: ELU (cálculo) e serviço (característico) ---
    gama = entrada.gama_f
    if entrada.valores_sao_de_calculo:
        N_Sd, V_Sd, M_in_Sd = entrada.N, entrada.V, entrada.M
        N_k, V_k, M_in_k = N_Sd / gama, V_Sd / gama, M_in_Sd / gama
    else:
        N_k, V_k, M_in_k = entrada.N, entrada.V, entrada.M
        N_Sd, V_Sd, M_in_Sd = gama * N_k, gama * V_k, gama * M_in_k
    a_mm = entrada.excentricidade_mm
    if a_mm is not None:
        M_Sd = V_Sd * a_mm / 1000.0
        M_k = V_k * a_mm / 1000.0
    else:
        M_Sd, M_k = M_in_Sd, M_in_k

    # --- 2. Geometria ---
    if grid:
        coords = bc.grade_retangular(entrada.n_lin, entrada.n_col, entrada.s, entrada.g)
        n_lin, n_col = entrada.n_lin, entrada.n_col
        passo_x = entrada.s if n_col > 1 else None
        passo_y = entrada.g if n_lin > 1 else None
    else:
        assert entrada.coordenadas is not None
        coords = list(entrada.coordenadas)
        n_lin = n_col = 0
        passo_x = distancia_minima_entre_furos(coords)
        passo_y = None
    n = len(coords)

    lf_borda = bc.lf_borda(entrada.e, d_h)
    lf_x = bc.lf_entre_furos(passo_x, d_h) if passo_x is not None else None
    lf_y = bc.lf_entre_furos(passo_y, d_h) if passo_y is not None else None
    lf_v = bc.lf_borda(entrada.e_v, d_h) if entrada.e_v is not None else None
    lfs = {
        "borda e": lf_borda,
        "entre furos s": lf_x,
        "entre furos g": lf_y,
        "borda vertical e_v": lf_v,
    }
    existentes = {nome: v for nome, v in lfs.items() if v is not None}
    lf_min = min(existentes.values())
    invalidos = [f"{nome} = {v:.1f} mm" for nome, v in existentes.items() if v <= 0]
    linhas.append(
        _linha(
            "Distância livre do furo ℓ_f > 0",
            None,
            None,
            "mm",
            "NBR 6.3.3.3 / AISC J3.10",
            ("ℓ_f ≤ 0: " + "; ".join(invalidos) + " — furo rompe a borda ou furos se sobrepõem.")
            if invalidos
            else "ℓ_f mínimo = "
            + f"{lf_min:.1f} mm ("
            + ", ".join(f"{nome}: {v:.1f}" for nome, v in existentes.items())
            + ")",
            "NÃO OK" if invalidos else "OK",
        )
    )

    # --- 3. Resistências por parafuso ---
    Fv = bc.resist_corte(d_b, entrada.grau, norma, entrada.rosca_no_plano, entrada.n_planos)
    Fc_ext = bc.resist_contato(d_b, t, f_u, lf_borda, norma, entrada.deformacao_limitada)
    Fc_int = (
        bc.resist_contato(d_b, t, f_u, lf_x, norma, entrada.deformacao_limitada)
        if lf_x is not None
        else None
    )
    Fc_min = bc.resist_contato(d_b, t, f_u, lf_min, norma, entrada.deformacao_limitada)
    R_bolt = min(Fv, Fc_min)
    intermediarios: dict[str, float] = {}
    resistencias: dict[str, float] = {
        "F_v_Rd_kN": Fv,
        "F_c_Rd_extremidade_kN": Fc_ext,
        "F_c_Rd_critico_kN": Fc_min,
        "R_parafuso_kN": R_bolt,
    }
    if Fc_int is not None:
        resistencias["F_c_Rd_interno_kN"] = Fc_int

    # --- 4. Força no parafuso crítico (ELU e serviço) ---
    elu = bc.grupo_excentrico_elastico(coords, V=V_Sd, N=N_Sd, M=M_Sd)
    els = bc.grupo_excentrico_elastico(coords, V=V_k, N=N_k, M=M_k)
    forcas: dict[str, float] = {
        "N_Sd_kN": N_Sd,
        "V_Sd_kN": V_Sd,
        "M_Sd_kNm": M_Sd,
        "N_k_kN": N_k,
        "V_k_kN": V_k,
        "M_k_kNm": M_k,
        "J_mm2": elu["J"],
        "R_max_ELU_kN": elu["R_max"],
        "R_max_ELS_kN": els["R_max"],
    }
    if a_mm is not None:
        forcas["excentricidade_mm"] = a_mm

    sem_esforco = N_Sd == 0 and V_Sd == 0 and M_Sd == 0
    if sem_esforco:
        linhas.append(
            _linha(
                "Esforços da ligação",
                None,
                None,
                "kN",
                "—",
                "Nenhum esforço informado: só disposições construtivas e critérios foram verificados.",
                "INFO",
            )
        )
    elif elu["J"] == 0 and M_Sd != 0:
        linhas.append(
            _linha(
                "Momento no grupo",
                abs(M_Sd),
                0.0,
                "kN·m",
                "Kulak et al., cap. 13",
                "Grupo de um parafuso (J = 0) não resiste a momento; adicione parafusos.",
                "NÃO OK",
            )
        )
    elif grid and V_Sd == 0 and M_Sd == 0:
        R_grupo = bc.resist_grupo_axial(n_lin, n_col, Fv, Fc_ext, Fc_int)
        resistencias["R_grupo_axial_kN"] = R_grupo
        linhas.append(
            _linha(
                "Grupo de parafusos — força axial centrada (soma por furo)",
                abs(N_Sd),
                R_grupo,
                "kN",
                "NBR 6.3.3.3 / AISC J3.6 / DG29",
                f"Σ min(F_v,Rd; F_c,Rd) por furo = {n_lin}·min({Fv:.1f}; {Fc_ext:.1f})"
                + (
                    f" + {n_lin * (n_col - 1)}·min({Fv:.1f}; {Fc_int:.1f})"
                    if Fc_int is not None and n_col > 1
                    else ""
                ),
            )
        )
    else:
        linhas.append(
            _linha(
                "Parafuso crítico — min(corte; contato/rasgamento)",
                elu["R_max"],
                R_bolt,
                "kN",
                "NBR 6.3.3.2 e 6.3.3.3 / AISC J3.6 e J3.10",
                f"R_max (ELU, elástico) ≤ min(F_v,Rd = {Fv:.1f}; F_c,Rd = {Fc_min:.1f}); "
                f"J = {elu['J']:.0f} mm²",
            )
        )

    # --- 5. Deslizamento ---
    F_Tb: float | None = None
    protendivel = bc.GRAUS[entrada.grau].protendivel
    if entrada.ligacao_por_atrito:
        mu = bc.mu_superficie(entrada.superficie, norma)
        if not protendivel:
            linhas.append(
                _linha(
                    "Deslizamento (ELS)",
                    None,
                    None,
                    "kN",
                    "NBR 6.3.4 / Anglo 9.1",
                    f"{entrada.grau} não admite protensão: não pode ser usado em ligação por atrito.",
                    "NÃO OK",
                )
            )
        elif mu is None:
            linhas.append(
                _linha(
                    "Deslizamento (ELS)",
                    None,
                    None,
                    "kN",
                    "RCSC 5.4 / AISC J3.8",
                    f"Superfície “{SUPERFICIES_ROTULOS[entrada.superficie]}” sem μ definido em "
                    f"{NORMAS_ROTULOS[norma]}: exige ensaio de deslizamento ou outra superfície.",
                    "NÃO OK",
                )
            )
        else:
            F_Tb = bc.protensao_minima(entrada.designacao, entrada.grau)
            F_f = bc.resist_deslizamento(
                F_Tb, mu, norma, n_s=entrada.n_planos, C_e=entrada.C_e, nivel="servico"
            )
            resistencias["F_Tb_kN"] = F_Tb
            resistencias["F_f_Rk_kN"] = F_f
            intermediarios["mu"] = mu
            linhas.append(
                _linha(
                    "Deslizamento (ELS, força de serviço)",
                    els["R_max"],
                    F_f,
                    "kN",
                    "NBR 6.3.4.4 / RCSC 5.4.2",
                    f"F_f,Rk = 0,80·μ·C_e·F_Tb·n_s = 0,80·{mu:g}·{entrada.C_e:g}·{F_Tb:g}·{entrada.n_planos}"
                    f"; R_max (ELS) = {els['R_max']:.2f} kN",
                )
            )
    else:
        linhas.append(
            _linha(
                "Ligação sem atrito (contato)",
                None,
                None,
                "—",
                "Anglo 9.1",
                "O deslizamento não foi verificado. A ligação por atrito é obrigatória com inversão "
                "de esforço, vibração ou deslizamento indesejável.",
                "ALERTA",
            )
        )

    # --- 6. Peça: tração, shear lag e colapso por rasgamento ---
    N_t_Rd: float | None = None
    R_lig_tracao: float | None = None
    tracao_peca = abs(N_Sd) > 0 or entrada.peca_por_esbeltez
    if tracao_peca and not grid:
        linhas.append(
            _linha(
                "Peça tracionada e colapso por rasgamento",
                None,
                None,
                "kN",
                "NBR 5.2 e 6.5.6",
                "Dependem da grade de parafusos; com coordenadas livres não são calculados.",
                "ALERTA",
            )
        )
    elif tracao_peca:
        if entrada.A_g is None or entrada.e_c is None:
            linhas.append(
                _linha(
                    "Tração da peça (N_t,Rd)",
                    None,
                    None,
                    "kN",
                    "NBR 5.2.2 e 5.2.5",
                    "Informe A_g e e_c da peça para calcular escoamento da seção bruta e ruptura "
                    "da seção líquida com C_t.",
                    "ALERTA",
                )
            )
        else:
            A_n = bc.area_liquida(entrada.A_g, n_lin, d_h, t, norma)
            l_c = (n_col - 1) * entrada.s
            C_t = bc.coef_Ct(entrada.e_c, l_c, norma)
            if A_n <= 0:
                linhas.append(
                    _linha(
                        "Tração da peça (N_t,Rd)",
                        abs(N_Sd),
                        0.0,
                        "kN",
                        "NBR 5.2.2",
                        f"A_n = {A_n:.0f} mm² ≤ 0: os furos consomem a seção da peça.",
                        "NÃO OK",
                    )
                )
            elif C_t is None:
                esc = bc.resist_tracao_barra(entrada.A_g, A_n, None, f_y, f_u, norma)
                linhas.append(
                    _linha(
                        "Tração da peça (N_t,Rd)",
                        abs(N_Sd),
                        None,
                        "kN",
                        "NBR 5.2.5",
                        "C_t indefinido (n_col = 1 → ℓ_c = 0): a ruptura da seção líquida não foi "
                        f"verificada; só o escoamento da seção bruta ({esc:.1f} kN) foi calculado.",
                        "ALERTA",
                    )
                )
            else:
                N_t_Rd = bc.resist_tracao_barra(entrada.A_g, A_n, C_t, f_y, f_u, norma)
                resistencias["N_t_Rd_kN"] = N_t_Rd
                intermediarios["C_t"] = C_t
                intermediarios["A_n_mm2"] = A_n
                linhas.append(
                    _linha(
                        "Tração da peça (N_t,Rd)",
                        abs(N_Sd),
                        N_t_Rd,
                        "kN",
                        "NBR 5.2.2 e 5.2.5 / AISC D2",
                        f"min(A_g·f_y/γ_a1; C_t·A_n·f_u/γ_a2); A_n = {A_n:.0f} mm², "
                        f"C_t = 1 − {entrada.e_c:g}/{l_c:g} = {C_t:.3f}",
                    )
                )
        A_gv, A_nv, A_nt = bc.areas_bloco_central(
            entrada.e, entrada.s, entrada.g, n_lin, n_col, t, d_h, norma
        )
        F_r = bc.resist_colapso_rasgamento(A_gv, A_nv, A_nt, f_y, f_u, norma)
        resistencias["F_r_Rd_kN"] = F_r
        nota_nt = "; n_lin = 1: sem plano de tração (A_nt = 0)" if n_lin == 1 else ""
        linhas.append(
            _linha(
                "Colapso por rasgamento",
                abs(N_Sd),
                F_r,
                "kN",
                "NBR 6.5.6 / AISC J4.3",
                "min(0,6·f_u·A_nv + C_ts·f_u·A_nt; 0,6·f_y·A_gv + C_ts·f_u·A_nt)/γ_a2; "
                f"A_gv = {A_gv:.0f}, A_nv = {A_nv:.0f}, A_nt = {A_nt:.0f} mm²{nota_nt}",
            )
        )
        R_grupo_axial = bc.resist_grupo_axial(n_lin, n_col, Fv, Fc_ext, Fc_int)
        resistencias.setdefault("R_grupo_axial_kN", R_grupo_axial)
        R_lig_tracao = min(R_grupo_axial, F_r)

    # --- 7. Disposições construtivas ---
    espacamentos = [x for x in (passo_x, passo_y) if x is not None]
    linhas.extend(
        bc.disposicoes_construtivas(
            d_b,
            d_h,
            e_min,
            t,
            entrada.e,
            espacamentos[0] if espacamentos else 0.0,
            espacamentos[1] if len(espacamentos) > 1 else None,
            entrada.e_v,
            entrada.pega,
            entrada.patinavel_sem_pintura,
            protendido=entrada.ligacao_por_atrito and protendivel,
        )
    )

    # --- 8. Critério Anglo ---
    linhas.extend(
        bc.criterio_anglo(
            n,
            entrada.grau,
            d_b,
            entrada.ligacao_principal,
            entrada.revestimento,
            entrada.peca_por_esbeltez,
            R_lig_tracao,
            N_t_Rd,
        )
    )

    # --- 9. Fora do escopo ---
    for chave in entrada.fora_do_escopo:
        linhas.append(
            _linha(
                "Condição fora do escopo desta verificação",
                None,
                None,
                "—",
                "Escopo da etapa",
                FORA_DO_ESCOPO.get(chave, chave) + " — não é verificada aqui.",
                "ALERTA",
            )
        )

    torque = None
    if F_Tb is not None:
        torque = torque_para_pre_carga(F_Tb * 1000.0, d_b, entrada.K_torque)
        linhas.append(
            _linha(
                "Referência de instalação — torque estimado",
                None,
                None,
                "N·m",
                "NBR 6.8.4 / RCSC §8",
                f"T ≈ K·F_Tb·d = {entrada.K_torque:g}·{F_Tb:g} kN·{d_b:g} mm = {torque:.0f} N·m. "
                "Estimativa: aperte por rotação da porca, chave calibrada ou indicador de tração.",
                "INFO",
            )
        )

    forcas_parafusos = tuple((fx, fy, r) for fx, fy, r in elu["forcas"])
    return _fechar(
        entrada,
        linhas,
        forcas,
        resistencias,
        intermediarios,
        tuple(coords),
        forcas_parafusos,
        torque,
    )


def _fechar(
    entrada: EntradaLigacao,
    linhas: Sequence[Verificacao],
    forcas: dict[str, float],
    resistencias: dict[str, float],
    intermediarios: dict[str, float],
    coords: tuple[tuple[float, float], ...],
    forcas_parafusos: tuple[tuple[float, float, float], ...],
    torque: float | None,
) -> ResultadoLigacao:
    aproveitamento, governante = _aproveitamento_governante(linhas)
    return ResultadoLigacao(
        entrada=entrada,
        verificacoes=tuple(linhas),
        status_geral=status_geral(linhas),
        aproveitamento_max=aproveitamento,
        governante=governante,
        forcas=forcas,
        resistencias=resistencias,
        intermediarios=intermediarios,
        torque_referencia_Nm=torque,
        coordenadas=coords,
        forcas_parafusos=forcas_parafusos,
    )


# ---------------------------------------------------------------------------------------------
# Varreduras
# ---------------------------------------------------------------------------------------------
def testar_todos_parafusos(entrada: EntradaLigacao) -> list[dict[str, Any]]:
    """Roda a verificação completa para cada parafuso da tabela, do menor para o maior d_b.

    ``atende`` = nenhum NÃO OK (ALERTA ainda é lido e fica visível no status).
    """
    saida: list[dict[str, Any]] = []
    for designacao in sorted(bc.PARAFUSOS, key=lambda nome: bc.PARAFUSOS[nome][0]):
        # O furo informado vale só para o parafuso escolhido; os demais usam a tabela.
        resultado = verificar_ligacao(replace(entrada, designacao=designacao, d_h_mm=None))
        saida.append(
            {
                "designacao": designacao,
                "d_b_mm": bc.PARAFUSOS[designacao][0],
                "status": resultado.status_geral,
                "aproveitamento_max": resultado.aproveitamento_max,
                "governante": resultado.governante,
                "atende": resultado.status_geral in ("OK", "ALERTA"),
            }
        )
    return saida


def menor_parafuso_que_atende(entrada: EntradaLigacao) -> str | None:
    for linha in testar_todos_parafusos(entrada):
        if linha["atende"]:
            return str(linha["designacao"])
    return None


def comparar_normas(entrada: EntradaLigacao) -> list[dict[str, Any]]:
    """Mesma ligação nas 4 normas. Uma norma que não cobre o caso aparece como erro, não some."""
    saida: list[dict[str, Any]] = []
    for norma in bc.NORMAS:
        linha: dict[str, Any] = {"norma": norma, "rotulo": NORMAS_ROTULOS[norma]}
        try:
            resultado = verificar_ligacao(replace(entrada, norma=norma))
        except ValueError as erro:
            linha.update(status="NÃO OK", erro=str(erro))
            saida.append(linha)
            continue
        linha.update(
            status=resultado.status_geral,
            aproveitamento_max=resultado.aproveitamento_max,
            governante=resultado.governante,
            F_v_Rd_kN=resultado.resistencias.get("F_v_Rd_kN"),
            F_c_Rd_kN=resultado.resistencias.get("F_c_Rd_critico_kN"),
            F_f_Rk_kN=resultado.resistencias.get("F_f_Rk_kN"),
            erro="",
        )
        saida.append(linha)
    return saida


# ---------------------------------------------------------------------------------------------
# Registro técnico (entra no memorial Word/PDF com a tabela completa de verificações)
# ---------------------------------------------------------------------------------------------
REFERENCIAS_NORMA = {
    "NBR8800_2008": "ABNT NBR 8800:2008, itens 5.2, 6.3 e 6.5.6; Tabelas 14, 16, 19 e A.3.",
    "NBR8800_2024": "Projeto de revisão ABNT NBR 8800 (maio/2024, Rev6): itens 5.2, 6.3, 6.5.6 e 6.8; Tabelas 14, 16, 19 e A.3.",
    "AISC360_LRFD": "ANSI/AISC 360, capítulos D, J3 e J4 (LRFD), e AISC Design Guide 29.",
    "RCSC2004": "RCSC Specification for Structural Joints Using ASTM A325 or A490 Bolts (2004), §5 e §8.",
}


def _nome_curto_norma(norma: str) -> str:
    return NORMAS_ROTULOS[norma].split(" (")[0]


def registro_ligacao(
    entrada: EntradaLigacao, resultado: ResultadoLigacao, menor_parafuso: str | None
) -> dict[str, Any]:
    """Registro técnico do módulo Projeto de parafusos para uma ligação estrutural.

    ``resultados["verificacoes"]`` é a tabela de oito colunas; o memorial a imprime como tabela.
    ``utilizacao_maxima`` é a chave que a Central de validação lê (acima de 1,0, bloqueia).
    """
    pior = resultado.aproveitamento_max
    resultados: dict[str, Any] = {
        "status_geral": resultado.status_geral,
        "verificacao_governante": resultado.governante,
        "menor_parafuso_que_atende": menor_parafuso or "nenhum com esta geometria",
        "forca_parafuso_critico_ELU_kN": resultado.forcas.get("R_max_ELU_kN"),
        "forca_parafuso_critico_ELS_kN": resultado.forcas.get("R_max_ELS_kN"),
        "momento_polar_J_mm2": resultado.forcas.get("J_mm2"),
        "torque_estimado_Nm": resultado.torque_referencia_Nm,
        "verificações": linhas_para_registro(resultado.verificacoes),
    }
    if pior is not None and math.isfinite(pior):
        resultados["utilizacao_maxima"] = pior
    resultados = {chave: valor for chave, valor in resultados.items() if valor is not None}

    alertas = [
        f"{v.nome}: {v.formula}" for v in resultado.verificacoes if v.status in ("NÃO OK", "ALERTA")
    ]
    if entrada.norma == "NBR8800_2008":
        alertas.append(
            "Conferir na NBR 8800:2008 antes de emitir: " + " ".join(bc.CONFERIR_NBR8800_2008)
        )

    grade = entrada.coordenadas is None
    entradas: dict[str, Any] = {
        "modo": "Ligação estrutural de aço",
        "norma": entrada.norma,
        "parafuso": entrada.designacao,
        "grau": entrada.grau,
        "furo_dh_mm": entrada.d_h_mm,
        "rosca_no_plano_corte": entrada.rosca_no_plano,
        "planos_de_corte": entrada.n_planos,
        "espessura_mais_fina_t_mm": entrada.t,
        "pega_mm": entrada.pega,
        "aco": entrada.aco,
        "n_lin": entrada.n_lin if grade else None,
        "n_col": entrada.n_col if grade else None,
        "passo_s_mm": entrada.s if grade else None,
        "gabarito_g_mm": entrada.g if grade else None,
        "coordenadas_mm": None if grade else [list(par) for par in entrada.coordenadas or ()],
        "borda_e_mm": entrada.e,
        "borda_vertical_ev_mm": entrada.e_v,
        "N_kN": entrada.N,
        "V_kN": entrada.V,
        "M_kNm": entrada.M,
        "excentricidade_a_mm": entrada.excentricidade_mm,
        "gama_f": entrada.gama_f,
        "valores_ja_de_calculo": entrada.valores_sao_de_calculo,
        "superficie": entrada.superficie,
        "ligacao_por_atrito": entrada.ligacao_por_atrito,
        "Ce": entrada.C_e,
        "deformacao_do_furo_limitada": entrada.deformacao_limitada,
        "A_g_peca_mm2": entrada.A_g,
        "e_c_peca_mm": entrada.e_c,
        "ligacao_principal_anglo": entrada.ligacao_principal,
        "revestimento": entrada.revestimento,
        "peca_por_esbeltez": entrada.peca_por_esbeltez,
        "fora_do_escopo_marcado": [FORA_DO_ESCOPO[c] for c in entrada.fora_do_escopo] or None,
    }
    entradas = {chave: valor for chave, valor in entradas.items() if valor is not None}

    return criar_registro_tecnico(
        modulo="Projeto de parafusos",
        modulo_id="projeto_parafusos",
        titulo=(
            f"Ligação parafusada — {entrada.designacao} {entrada.grau} "
            f"({_nome_curto_norma(entrada.norma)})"
        ),
        status=STATUS_REGISTRO[resultado.status_geral],
        resumo=(
            "Verificação de ligação parafusada estrutural: esforços no grupo, corte, contato e "
            "rasgamento, deslizamento, peça tracionada, disposições construtivas e critério Anglo."
        ),
        entradas=entradas,
        resultados=resultados,
        metodo=(
            "Funções de cálculo de core.bolted_connection (validadas contra o AISC Design Guide 29 "
            "e a planilha de referência) orquestradas em core.bolted_joint_check; grupo excêntrico "
            "pelo método elástico."
        ),
        equacoes=[
            "Corte: F_v,Rd = α_v·A_b·f_ub/γ_a2 (NBR 6.3.3.2) ou φ·F_nv·A_b (AISC J3.6 / RCSC 5.1)",
            "Contato e rasgamento: F_c,Rd = min(1,2·ℓ_f·t·f_u; 2,4·d_b·t·f_u)/γ_a2, "
            "ℓ_f medido a partir do furo, t da parte mais fina",
            "Grupo excêntrico: F_x,i = N/n − M·y_i/J; F_y,i = V/n + M·x_i/J; J = Σ(x_i² + y_i²)",
            "Deslizamento (serviço): F_f,Rk = 0,80·μ·C_e·F_Tb·n_s·(1 − F_t,Sk/(0,80·F_Tb))",
            "Tração da peça: N_t,Rd = min(A_g·f_y/γ_a1; C_t·A_n·f_u/γ_a2), C_t = 1 − e_c/ℓ_c",
            "Colapso por rasgamento: min(0,6·f_u·A_nv + C_ts·f_u·A_nt; "
            "0,6·f_y·A_gv + C_ts·f_u·A_nt)/γ_a2",
        ],
        criterios=[
            "ELU: força de cálculo (γ_f·F_k) ≤ resistência de cálculo.",
            "Deslizamento: força de serviço (característica) ≤ F_f,Rk.",
            "Disposições: NBR 6.3.7 a 6.3.12 (Tab. 16) e AISC J3.3 a J3.5.",
            "Anglo AA-BR-DPST-DR-0001, item 9.1.",
        ],
        premissas=[
            "Furo-padrão; tração nos parafusos, alavanca e fadiga fora do escopo.",
            "Torque de aperto é estimativa; instalar por rotação da porca, chave calibrada ou "
            "indicador de tração.",
            "t = espessura da parte ligada mais fina (nunca a soma).",
        ],
        alertas=alertas,
        referencias=[
            REFERENCIAS_NORMA[entrada.norma],
            "Anglo American — Critério de Projeto Estruturas Metálicas AA-BR-DPST-DR-0001, item 9.1.",
            "Kulak, Fisher & Struik — Guide to Design Criteria for Bolted and Riveted Joints, cap. 13.",
        ],
        conclusao=(
            f"Status geral {resultado.status_geral}; aproveitamento máximo "
            f"{formatar_percentual(pior)} em «{resultado.governante}»."
        ),
    )
