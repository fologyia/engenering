"""Verificação completa de uma ligação parafusada estrutural (sem Streamlit).

Orquestra as funções de ``core.bolted_connection`` na sequência do projeto:

1. esforços de cálculo (ELU) e de serviço (característicos);
2. força no parafuso mais carregado (grupo excêntrico elástico) ou soma por furo;
3. resistência por parafuso: min(corte, contato/rasgamento);
4. tração nos parafusos (do grupo para cada parafuso), interação tração + corte e alavanca;
5. deslizamento: serviço (furo-padrão) ou ELU (furo alargado/alongado), com a tração;
6. peça: tração com C_t, colapso por rasgamento e chapa de ligação (gusset);
7. tipo de furo, disposições construtivas e critério Anglo;
8. resumo: aproveitamento máximo, verificação governante e status geral.

Cada versão da NBR usa as regras dela (nada de misturar coeficientes): a 2008 com o texto
conferido; a 2025 (código interno ``NBR8800_2024``) com as tabelas conferidas nas fotos da norma
e, onde o texto não foi visto, com o que o usuário mandou — marcado "a confirmar".

Nada aqui "conserta" uma entrada em silêncio: ℓ_f ≤ 0, n_col = 1 (C_t indefinido),
A307 em ligação por atrito, superfície sem μ na norma, grupo sem rigidez ao momento
e condições fora do escopo viram linhas visíveis da tabela de verificações.

Unidades: comprimento em mm, tensão em MPa, força em kN, momento em kN·m.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
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

#: A designação de cada norma — a única fonte: título, campo Norma, referências das linhas e
#: lista de referências do memorial saem daqui (a chave interna NBR8800_2024 é a edição de 2025,
#: confirmada pelo usuário em 28/10/2026).
NORMAS_ROTULOS = {
    "NBR8800_2008": "ABNT NBR 8800:2008",
    "NBR8800_2024": "ABNT NBR 8800:2025",
    "AISC360_LRFD": "AISC 360 (LRFD)",
    "RCSC2004": "RCSC 2004 (LRFD)",
}


def _nbr_curta(norma: str) -> str:
    """A designação central sem o "ABNT " ("NBR 8800:2025"), para a referência de cada linha."""
    return NORMAS_ROTULOS[norma].removeprefix("ABNT ")


SUPERFICIES_ROTULOS = {
    "galvanizada_sem_tratamento": "Galvanizada a fogo, sem tratamento (padrão Anglo)",
    "classe_C_galv_escovada": "Classe C — galvanizada escovada",
    "classe_A_laminada_limpa": "Classe A — laminada limpa",
    "classe_B_jateada": "Classe B — jateada",
}

#: Condições que esta etapa NÃO verifica. Quem marca uma delas recebe um ALERTA na tabela.
FORA_DO_ESCOPO = {
    "fadiga": "Fadiga da ligação (NBR 8800, Anexo H)",
    "formado_a_frio": "Perfis formados a frio (NBR 14762)",
}

#: Nota de versão na página (não vai para o registro nem para o memorial).
NOTA_DA_VERSAO = (
    "Norma de referência: ABNT NBR 8800:2025, a versão vigente. A NBR 8800:2008 continua na lista "
    "para comparação; cada versão usa as próprias tabelas e coeficientes."
)
#: Aço da parte ligada digitado (f_y e f_u) em vez do catálogo.
ACO_INFORMADO = "Informado (f_y e f_u)"

AVISOS_FIXOS = (
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
    # Tração nos parafusos — do GRUPO, perpendicular ao plano da ligação (kN; característica ou de
    # cálculo como N e V). M_t (kN·m) é o momento fora do plano: traciona os parafusos de y maior.
    N_t: float = 0.0
    M_t: float = 0.0
    interacao_por_tabela: bool = False  # alternativa da NBR (Tab. 11 na 2008; 12 na 2025)
    # Furo
    tipo_furo: str = bc.FURO_PADRAO
    # Efeito de alavanca (chapa tracionada pelos parafusos)
    alavanca: bool = False
    alav_a: float = 0.0  # mm: do parafuso à borda da chapa
    alav_b: float = 0.0  # mm: do parafuso à face da alma/solda
    alav_p: float = 0.0  # mm: largura tributária de um parafuso (p_ext ou p_int)
    alav_d_f: float | None = None  # mm: furo na direção de p; None = o furo
    alav_t: float | None = None  # mm: espessura da chapa fletida; None = t
    alav_plastico: bool = True  # NBR 2008, 6.3.5.2: a) plástico (−33 %) ou b) elástico (−25 %)
    F_t_com_alavanca: float | None = None  # kN, por parafuso, de cálculo (opcional)
    # Chapa de ligação (gusset) tracionada pela força N
    chapa_largura: float | None = None
    chapa_t: float | None = None  # None = t
    chapa_furos: int | None = None  # furos na seção líquida; None = n_lin
    # Aço digitado (aco = ACO_INFORMADO)
    f_y: float | None = None
    f_u: float | None = None


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
    #: As equações do método que valem para esta ligação, com os coeficientes escolhidos e os
    #: valores substituídos (o memorial as imprime; nada de equação que não se aplica).
    equacoes: tuple[str, ...] = ()


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
    if entrada.aco == ACO_INFORMADO:
        if entrada.f_y is None or entrada.f_u is None:
            raise ValueError("Informe f_y e f_u do aço.")
        if not (math.isfinite(entrada.f_y) and math.isfinite(entrada.f_u)) or entrada.f_y <= 0:
            raise ValueError("f_y e f_u devem ser números maiores que zero.")
        if entrada.f_u <= entrada.f_y:
            raise ValueError(
                f"f_u ({entrada.f_u:g} MPa) não pode ser menor ou igual a f_y ({entrada.f_y:g} MPa): "
                "a ruptura vem sempre acima do escoamento. Confira o aço — o ASTM A36, por exemplo, "
                "tem f_y = 250 e f_u = 400 MPa."
            )
    elif entrada.aco not in bc.ACOS:
        raise ValueError(f"Aço desconhecido: {entrada.aco}.")
    if entrada.tipo_furo not in bc.TIPOS_DE_FURO:
        raise ValueError(f"Tipo de furo desconhecido: {entrada.tipo_furo}.")
    for nome, valor in (("N_t", entrada.N_t), ("M_t", entrada.M_t)):
        if not math.isfinite(valor):
            raise ValueError(f"{nome} deve ser um número finito.")
    if entrada.N_t < 0:
        raise ValueError(
            "N_t é a tração do grupo (≥ 0): compressão perpendicular ao plano não carrega os "
            "parafusos (vai por contato entre as chapas)."
        )
    if entrada.alavanca:
        for nome, valor in (("a", entrada.alav_a), ("b", entrada.alav_b), ("p", entrada.alav_p)):
            if not math.isfinite(valor) or valor <= 0:
                raise ValueError(f"Alavanca: {nome} deve ser maior que zero.")
    if entrada.chapa_largura is not None and not entrada.chapa_largura > 0:
        raise ValueError("A largura da chapa de ligação deve ser maior que zero.")
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
    # O furo pela tabela da versão da norma (a 2008 tem furos menores) e pelo tipo; o furo
    # informado vale para o furo-padrão. d_h: ao longo da força (x); d_hy: atravessando-a (y).
    if entrada.tipo_furo == bc.FURO_PADRAO and entrada.d_h_mm is not None:
        d_h = d_hy = entrada.d_h_mm
    else:
        d_h = bc.furo_na_direcao_da_forca(entrada.designacao, entrada.tipo_furo, norma)
        d_hy = bc.furo_atravessando_a_forca(entrada.designacao, entrada.tipo_furo, norma)
    if entrada.aco == ACO_INFORMADO:
        assert entrada.f_y is not None and entrada.f_u is not None
        f_y, f_u = entrada.f_y, entrada.f_u
    else:
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
    if entrada.valores_sao_de_calculo:
        N_t_Sd, M_t_Sd = entrada.N_t, entrada.M_t
        N_t_k, M_t_k = N_t_Sd / gama, M_t_Sd / gama
    else:
        N_t_k, M_t_k = entrada.N_t, entrada.M_t
        N_t_Sd, M_t_Sd = gama * N_t_k, gama * M_t_k
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
    lf_y = bc.lf_entre_furos(passo_y, d_hy) if passo_y is not None else None
    lf_v = bc.lf_borda(entrada.e_v, d_hy) if entrada.e_v is not None else None
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
    perp = entrada.tipo_furo == bc.FURO_MUITO_TRANSVERSAL  # 1,0/2,0 (6.3.3.3 b)
    Fc_ext = bc.resist_contato(d_b, t, f_u, lf_borda, norma, entrada.deformacao_limitada, perp)
    Fc_int = (
        bc.resist_contato(d_b, t, f_u, lf_x, norma, entrada.deformacao_limitada, perp)
        if lf_x is not None
        else None
    )
    Fc_min = bc.resist_contato(d_b, t, f_u, lf_min, norma, entrada.deformacao_limitada, perp)
    R_bolt = min(Fv, Fc_min)
    # O texto da equação sai dos mesmos coeficientes que o cálculo usou.
    k1, k2 = bc.coeficientes_contato(entrada.deformacao_limitada, perp)
    contato_txt = _equacao_contato(norma, k1, k2, lf_min, d_b, t, f_u, Fc_min)
    equacoes: list[str] = [
        _equacao_corte(entrada, d_b, Fv),
        f"Contato e rasgamento ({_motivo_do_contato(entrada)}; ℓ_f crítico = {lf_min:.1f} mm, "
        f"t da parte mais fina): {contato_txt} "
        f"({_ref(norma, '6.3.3.3', '6.3.3.3', 'AISC J3.10')})",
    ]
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
    if V_Sd != 0 or M_Sd != 0:
        equacoes.append(
            "Grupo excêntrico (método elástico): F_x,i = N/n − M·y_i/J; F_y,i = V/n + M·x_i/J; "
            f"J = Σ(x_i² + y_i²) = {elu['J']:.0f} mm²; parafuso crítico R_max = "
            f"{elu['R_max']:.2f} kN (ELU) e {els['R_max']:.2f} kN (serviço)"
        )

    # Tração em cada parafuso (de cálculo e característica) e o efeito de alavanca.
    tem_tracao = N_t_Sd > 0 or M_t_Sd != 0
    ft_elu = bc.tracao_nos_parafusos(coords, N_t_Sd, M_t_Sd) if tem_tracao else [0.0] * len(coords)
    ft_els = bc.tracao_nos_parafusos(coords, N_t_k, M_t_k) if tem_tracao else [0.0] * len(coords)
    F_t_Rd: float | None = None
    fator_alavanca = 1.0
    if tem_tracao:
        F_t_Rd = bc.resist_tracao_parafuso(d_b, entrada.grau, norma)
        resistencias["F_t_Rd_kN"] = F_t_Rd
        intermediarios["A_b_mm2"] = bc.area_bruta(d_b)
        if bc._nbr(norma):
            intermediarios["A_be_mm2"] = bc.area_efetiva(d_b)
        F_t0 = max(ft_elu)
        forcas["N_t_Sd_kN"] = N_t_Sd
        forcas["M_t_Sd_kNm"] = M_t_Sd
        forcas["F_t0_Sd_kN"] = F_t0
        if entrada.alavanca and F_t0 > 0:
            F_t_Rd, fator_alavanca = _alavanca(
                entrada, linhas, intermediarios, d_b, d_h, f_y, f_u, F_t0, F_t_Rd
            )
        forcas["F_t_Sd_kN"] = F_t0 * fator_alavanca
        forcas["F_t_Sk_kN"] = max(ft_els) * fator_alavanca
        _tracao_e_interacao(
            entrada,
            linhas,
            intermediarios,
            d_b,
            Fv,
            F_t_Rd,
            [f * fator_alavanca for f in ft_elu],
            [r for _, _, r in elu["forcas"]],
        )

    sem_esforco = N_Sd == 0 and V_Sd == 0 and M_Sd == 0 and not tem_tracao
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
    elif N_Sd == 0 and V_Sd == 0 and M_Sd == 0:
        pass  # só tração: as linhas da tração e da interação já estão na tabela
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
                f"R_max (ELU, elástico) ≤ mín(F_v,Rd = {Fv:.2f}; F_c,Rd = {Fc_min:.2f}) = "
                f"{R_bolt:.2f} kN; F_c,Rd com {_motivo_do_contato(entrada)}: {contato_txt}; "
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
            resistencias["F_Tb_kN"] = F_Tb
            intermediarios["mu"] = mu
            _deslizamento(
                entrada,
                linhas,
                resistencias,
                F_Tb,
                mu,
                elu["R_max"],
                els["R_max"],
                forcas.get("F_t_Sd_kN", 0.0),
                forcas.get("F_t_Sk_kN", 0.0),
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
    F_r: float | None = None
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
            A_n = bc.area_liquida(entrada.A_g, n_lin, d_hy, t, norma)
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
            entrada.e, entrada.s, entrada.g, n_lin, n_col, t, d_h, norma, d_h_tracao=d_hy
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
    if V_Sd != 0 and entrada.A_g is not None:
        linhas.append(
            _linha(
                "Peça — cisalhamento pela força V (a confirmar)",
                None,
                None,
                "kN",
                _ref(norma, "6.5.5", "6.5.5", "AISC J4.2"),
                f"V_Sd = {abs(V_Sd):.2f} kN atravessa a peça, mas a seção dela que resiste a V "
                "(comprimento × espessura, com os furos) não foi informada: escoamento "
                "0,60·A_gv·f_y/γ_a1 e ruptura 0,60·A_nv·f_u/γ_a2 da peça ficam a confirmar. A "
                "tração da peça e o colapso por rasgamento acima usam só N.",
                "ALERTA",
            )
        )

    # --- Chapa de ligação (gusset): tração por N e cisalhamento por V ---
    if entrada.chapa_largura is not None:
        _chapa_de_ligacao(
            entrada,
            linhas,
            resistencias,
            intermediarios,
            N_Sd,
            V_Sd,
            d_hy,
            f_y,
            f_u,
            n_lin if grid else 1,
        )

    # --- Tipo de furo: ligação permitida e borda mínima com incremento ---
    if entrada.tipo_furo != bc.FURO_PADRAO:
        _furo_alargado_ou_alongado(entrada, linhas, d_b, e_min)

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
    # Capacidade da ligação para a regra dos 75%: a menor entre corte × n, contato × n (o parafuso
    # crítico, conservador), colapso por rasgamento, chapa de ligação e deslizamento × n.
    componentes: list[tuple[str, float]] = [
        (f"corte {n}·F_v,Rd", n * Fv),
        (f"contato {n}·F_c,Rd", n * Fc_min),
    ]
    if F_r is not None:
        componentes.append(("colapso por rasgamento", F_r))
    if "chapa_escoamento_kN" in resistencias:
        componentes.append(("chapa de ligação (escoamento)", resistencias["chapa_escoamento_kN"]))
        componentes.append(("chapa de ligação (ruptura)", resistencias["chapa_ruptura_kN"]))
    for chave, nome in (("F_f_Rk_kN", "F_f,Rk"), ("F_f_Rd_kN", "F_f,Rd")):
        if chave in resistencias:
            componentes.append((f"deslizamento {n}·{nome}", n * resistencias[chave]))
    regra_calculavel = tracao_peca and grid and N_t_Rd is not None
    R_lig_tracao = min(valor for _, valor in componentes) if regra_calculavel else None
    if entrada.peca_por_esbeltez and R_lig_tracao is not None:
        resistencias["R_ligacao_anglo_kN"] = R_lig_tracao
        equacoes.append(
            "Regra dos 75% (Anglo 9.1, peça por esbeltez ou sem esforço indicado): R_lig = mín(corte "
            "× n; contato × n; colapso por rasgamento; chapa de ligação; deslizamento × n) ≥ "
            "máx(0,75·N_t,Rd; 3 tf)"
        )
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
            componentes,
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
        tuple(equacoes),
    )


def _ref(norma: str, nbr_2008: str, nbr_2025: str, aisc: str) -> str:
    """O item da norma escolhida (cada versão com o seu)."""
    if norma == "NBR8800_2008":
        return f"{_nbr_curta(norma)}, {nbr_2008}"
    if norma == "NBR8800_2024":
        return f"{_nbr_curta(norma)}, {nbr_2025}"
    return aisc


def _t_minimo(t_mm: float) -> str:
    """A espessura mínima que a força exige; abaixo de 1 mm o número não informa nada."""
    if t_mm < 1.0:
        return "t mínimo desprezível para esta carga (< 1 mm)"
    return f"t mínimo = {t_mm:.2f} mm"


def _equacao_corte(entrada: EntradaLigacao, d_b: float, Fv: float) -> str:
    """F_v,Rd com o coeficiente da rosca e os valores substituídos."""
    norma, n_s = entrada.norma, entrada.n_planos
    A_b = bc.area_bruta(d_b)
    na_rosca = entrada.rosca_no_plano or entrada.grau == "A307"
    rosca = "rosca no plano de corte" if na_rosca else "rosca fora do plano de corte"
    if bc._nbr(norma):
        alfa = bc._P[norma]["alfa_N" if na_rosca else "alfa_X"]
        f_ub = bc.fub(entrada.grau, d_b, norma)
        g_a2 = bc._P[norma]["g_a2"]
        return (
            f"Corte ({rosca}): F_v,Rd = n_s·α_v·A_b·f_ub/γ_a2 = {n_s}·{alfa:g}·{A_b:.1f}·"
            f"{f_ub:g}/{g_a2:g} = {Fv:.2f} kN ({_ref(norma, '6.3.3.2', '6.3.3.2', '')})"
        )
    grau = bc.GRAUS[entrada.grau]
    if norma == "AISC360_LRFD":
        F_n, nome, ref = grau.Fnv_AISC[0 if na_rosca else 1], "F_nv", "AISC J3.6"
    else:
        assert grau.Fn_RCSC is not None
        F_n, nome, ref = grau.Fn_RCSC[0 if na_rosca else 1], "F_n", "RCSC 5.1"
    return f"Corte ({rosca}): φ·{nome}·A_b·n_s = 0,75·{F_n:g}·{A_b:.1f}·{n_s} = {Fv:.2f} kN ({ref})"


def _equacao_contato(
    norma: str,
    k1: float,
    k2: float,
    l_f: float,
    d_b: float,
    t: float,
    f_u: float,
    Fc: float,
) -> str:
    """F_c,Rd com os coeficientes que o cálculo usou (1,2/2,4; 1,5/3,0; 1,0/2,0), substituídos."""
    rasg = k1 * l_f * t * f_u / 1000
    esmag = k2 * d_b * t * f_u / 1000
    k1_txt, k2_txt = f"{k1:.1f}".replace(".", ","), f"{k2:.1f}".replace(".", ",")
    if bc._nbr(norma):
        g_a2 = bc._P[norma]["g_a2"]
        return (
            f"F_c,Rd = mín({k1_txt}·ℓ_f·t·f_u; {k2_txt}·d_b·t·f_u)/γ_a2 = mín({k1:.1f}·{l_f:.1f}·"
            f"{t:g}·{f_u:g}; {k2:.1f}·{d_b:g}·{t:g}·{f_u:g})/{g_a2:g} = mín({rasg / g_a2:.2f}; "
            f"{esmag / g_a2:.2f}) = {Fc:.2f} kN"
        )
    return (
        f"φ·R_n = 0,75·mín({k1_txt}·ℓ_f·t·F_u; {k2_txt}·d_b·t·F_u) = 0,75·mín({k1:.1f}·{l_f:.1f}·"
        f"{t:g}·{f_u:g}; {k2:.1f}·{d_b:g}·{t:g}·{f_u:g}) = {Fc:.2f} kN"
    )


def _motivo_do_contato(entrada: EntradaLigacao) -> str:
    if entrada.tipo_furo == bc.FURO_MUITO_TRANSVERSAL:
        return "furo muito alongado perpendicular à força"
    if entrada.deformacao_limitada:
        return "deformação do furo limitada"
    return "deformação do furo não limitada"


def _alavanca(
    entrada: EntradaLigacao,
    linhas: list[Verificacao],
    intermediarios: dict[str, float],
    d_b: float,
    d_h: float,
    f_y: float,
    f_u: float,
    F_t0: float,
    F_t_Rd: float,
) -> tuple[float, float]:
    """As linhas do efeito de alavanca; devolve (F_t,Rd a usar, fator da tração com alavanca)."""
    norma = entrada.norma
    t_placa = entrada.alav_t if entrada.alav_t is not None else entrada.t
    if norma == "NBR8800_2008":
        r = bc.alavanca_2008(
            a=entrada.alav_a,
            b=entrada.alav_b,
            p=entrada.alav_p,
            t=t_placa,
            f_y=f_y,
            F_t_Sd=F_t0,
            F_t_Rd=F_t_Rd,
            plastico=entrada.alav_plastico,
        )
        intermediarios["t_alavanca_req_mm"] = r.t_requerida_mm
        linhas.append(
            _linha(
                "Alavanca — espessura da chapa fletida",
                r.t_requerida_mm,
                t_placa,
                "mm",
                r.metodo,
                f"M_Sd = F_t,Sd·b na largura p; t ≥ √({'4' if entrada.alav_plastico else '6'}·"
                f"F_t,Sd·b·γ_a1/(p·f_y)) = √({'4' if entrada.alav_plastico else '6'}·"
                f"{F_t0 * 1000:.0f}·{entrada.alav_b:g}·1,10/({entrada.alav_p:g}·{f_y:g})) = "
                f"{r.t_requerida_mm:.2f} mm; tração resistente dos parafusos reduzida em "
                f"{'33' if entrada.alav_plastico else '25'} %",
            )
        )
        if r.aviso:
            linhas.append(
                _linha("Alavanca — a ≥ b", entrada.alav_b, entrada.alav_a, "mm", r.metodo, r.aviso)
            )
        assert r.F_t_Rd_reduzida_kN is not None
        intermediarios["F_t_Rd_com_alavanca_kN"] = r.F_t_Rd_reduzida_kN
        return r.F_t_Rd_reduzida_kN, 1.0
    if norma != "NBR8800_2024":
        linhas.append(
            _linha(
                "Efeito de alavanca",
                None,
                None,
                "—",
                "AISC Manual, Parte 9",
                "Nesta etapa a alavanca segue a NBR 8800 (escolha a 2025 ou a 2008).",
                "ALERTA",
            )
        )
        return F_t_Rd, 1.0
    d_f = entrada.alav_d_f if entrada.alav_d_f is not None else d_h
    r = bc.alavanca_2025(
        a=entrada.alav_a,
        b=entrada.alav_b,
        p=entrada.alav_p,
        d_b=d_b,
        d_f=d_f,
        t=t_placa,
        f_u=f_u,
        F_t0_Sd=F_t0,
        F_t_Rd=F_t_Rd,
    )
    intermediarios["t_rigida_mm"] = r.t_rigida_mm
    ref = _ref(norma, "6.3.5", "6.3.5 (a confirmar)", "")
    linhas.append(
        _linha(
            "Alavanca — placa rígida (t para não haver alavanca)",
            r.t_rigida_mm,
            t_placa,
            "mm",
            ref,
            f"t_rígida = √[4·(b − 0,5·d_b)·F_t,0,Sd·γ_a1/(p·f_u)] = √[4·({entrada.alav_b:g} − "
            f"{0.5 * d_b:g})·{F_t0 * 1000:.0f}·1,10/({entrada.alav_p:g}·{f_u:g})] = "
            f"{r.t_rigida_mm:.2f} mm"
            + ("" if r.rigida else " — t menor: há alavanca; vale a verificação da placa flexível"),
            "OK" if r.rigida else "INFO",
        )
    )
    if r.beta is not None and r.beta < 0:
        linhas.append(_linha("Alavanca — parafuso", F_t0, F_t_Rd, "kN", ref, r.aviso, "NÃO OK"))
        return F_t_Rd, 1.0
    if r.rigida:
        return F_t_Rd, 1.0
    assert r.alfa is not None and r.delta is not None and r.beta is not None
    intermediarios.update(alavanca_beta=r.beta, alavanca_alfa=r.alfa, alavanca_delta=r.delta)
    linhas.append(
        _linha(
            "Alavanca — placa flexível (com alavanca)",
            r.t_requerida_mm,
            t_placa,
            "mm",
            ref,
            f"δ = 1 − d_f/p = {r.delta:.3f}; β = {r.beta:.3f}; α = {r.alfa:.3f}; a de cálculo = "
            f"{r.a_calculo_mm:g} mm (≤ 1,25·b); t_req = t_rígida/√(1 + δ·α) = "
            f"{r.t_requerida_mm:.2f} mm",
        )
    )
    if entrada.F_t_com_alavanca is None:
        linhas.append(
            _linha(
                "Tração no parafuso com alavanca",
                None,
                None,
                "kN",
                ref,
                "A placa é flexível: a tração no parafuso cresce com a alavanca. Informe a força "
                "por parafuso com alavanca (F_t,Sd) — a tração e a interação abaixo usaram a força "
                f"sem alavanca, F_t,0,Sd = {F_t0:.2f} kN.",
                "ALERTA",
            )
        )
        return F_t_Rd, 1.0
    if entrada.F_t_com_alavanca < F_t0:
        raise ValueError(
            f"A tração com alavanca ({entrada.F_t_com_alavanca:g} kN) não pode ser menor que a "
            f"tração sem alavanca F_t,0,Sd ({F_t0:.2f} kN): a alavanca só aumenta a força no "
            "parafuso."
        )
    return F_t_Rd, entrada.F_t_com_alavanca / F_t0


def _tracao_e_interacao(
    entrada: EntradaLigacao,
    linhas: list[Verificacao],
    intermediarios: dict[str, float],
    d_b: float,
    Fv: float,
    F_t_Rd: float,
    tracoes: Sequence[float],
    cortes: Sequence[float],
) -> None:
    """Tração do parafuso mais tracionado e a interação tração + corte, parafuso a parafuso."""
    norma = entrada.norma
    i_t = max(range(len(tracoes)), key=lambda i: tracoes[i])
    linhas.append(
        _linha(
            "Tração no parafuso (por parafuso)",
            tracoes[i_t],
            F_t_Rd,
            "kN",
            _ref(norma, "6.3.3.1", "6.3.3.1", "AISC J3.6 / RCSC 5.1"),
            f"F_t,Rd = A_be·f_ub/γ_a2 = 0,75·{bc.area_bruta(d_b):.1f} mm²·f_ub/γ_a2 = "
            f"{F_t_Rd:.1f} kN; F_t,Sd do parafuso mais tracionado = {tracoes[i_t]:.2f} kN "
            "(a tração do grupo dividida pelos parafusos, com o momento fora do plano)"
            if bc._nbr(norma)
            else f"φ·F_nt·A_b = {F_t_Rd:.1f} kN; F_t do parafuso mais tracionado = {tracoes[i_t]:.2f} kN",
        )
    )
    if not any(cortes):
        return
    if norma == "AISC360_LRFD":
        grau = bc.GRAUS[entrada.grau]
        F_nv = grau.Fnv_AISC[0 if entrada.rosca_no_plano or entrada.grau == "A307" else 1]
        A_b = bc.area_bruta(d_b)
        pior = max(
            range(len(tracoes)),
            key=lambda i: (
                tracoes[i]
                / (
                    0.75
                    * bc.tracao_reduzida_aisc(
                        grau.Fnt_AISC, F_nv, cortes[i] * 1000 / (A_b * entrada.n_planos)
                    )
                    * A_b
                    / 1000
                )
            ),
        )
        F_nt_r = bc.tracao_reduzida_aisc(
            grau.Fnt_AISC, F_nv, cortes[pior] * 1000 / (A_b * entrada.n_planos)
        )
        linhas.append(
            _linha(
                "Tração + corte (interação)",
                tracoes[pior],
                0.75 * F_nt_r * A_b / 1000,
                "kN",
                "AISC J3.7",
                f"F'_nt = 1,3·F_nt − F_nt/(φ·F_nv)·f_rv ≤ F_nt = {F_nt_r:.0f} MPa; "
                f"φ·F'_nt·A_b no parafuso crítico",
            )
        )
        return
    razoes = [
        bc.interacao_tracao_corte(ft, F_t_Rd, fv, Fv)
        for ft, fv in zip(tracoes, cortes, strict=True)
    ]
    i = max(range(len(razoes)), key=lambda k: razoes[k])
    intermediarios["interacao_tracao_corte"] = razoes[i]
    intermediarios["interacao_F_t_Sd_kN"] = tracoes[i]
    intermediarios["interacao_F_v_Sd_kN"] = cortes[i]
    intermediarios["interacao_F_t_Rd_kN"] = F_t_Rd
    linhas.append(
        _linha(
            "Tração + corte (interação, por parafuso)",
            razoes[i],
            1.0,
            "—",
            _ref(norma, "6.3.3.4", "6.3.3.4", "RCSC 5.2"),
            f"(F_t,Sd/F_t,Rd)² + (F_v,Sd/F_v,Rd)² = ({tracoes[i]:.2f}/{F_t_Rd:.1f})² + "
            f"({cortes[i]:.2f}/{Fv:.1f})² = {razoes[i]:.3f} no parafuso crítico",
        )
    )
    if bc._nbr(norma):
        limites = [
            bc.limite_tracao_tabela(d_b, entrada.grau, norma, entrada.rosca_no_plano, fv)
            for fv in cortes
        ]
        j = min(range(len(limites)), key=lambda k: limites[k] - tracoes[k])
        k = bc.coeficiente_tabela_interacao(entrada.grau, entrada.rosca_no_plano)
        tabela = bc.TABELA_INTERACAO[norma]
        # O limite da tabela vai para o memorial mesmo sem a opção marcada (só informa).
        intermediarios["limite_tabela_kN"] = limites[j]
        intermediarios["limite_tabela_coef"] = k
        intermediarios["limite_tabela_F_v_Sd_kN"] = cortes[j]
        intermediarios["limite_tabela_F_t_Sd_kN"] = tracoes[j]
    if entrada.interacao_por_tabela and bc._nbr(norma):
        linhas.append(
            _linha(
                f"Tração com corte ({tabela}, alternativa)",
                tracoes[j],
                limites[j],
                "kN",
                _ref(norma, "6.3.3.4 e Tabela 11", "6.3.3.4 e Tabela 12", ""),
                f"F_t,Sd ≤ f_ub·A_b/γ_a2 − {k:g}·F_v,Sd = {limites[j] + k * cortes[j]:.1f} − "
                f"{k:g}·{cortes[j]:.2f} = {limites[j]:.1f} kN (usa A_b, não A_be); as verificações "
                "isoladas de tração e de corte continuam valendo",
            )
        )


def _deslizamento(
    entrada: EntradaLigacao,
    linhas: list[Verificacao],
    resistencias: dict[str, float],
    F_Tb: float,
    mu: float,
    R_elu: float,
    R_els: float,
    F_t_Sd: float,
    F_t_Sk: float,
) -> None:
    """Deslizamento: serviço (furo-padrão ou alongado transversal) ou ELU (alargado/alongado),
    cada versão com os seus fatores, e a redução pela tração no parafuso."""
    norma, tipo = entrada.norma, entrada.tipo_furo
    n_s = entrada.n_planos
    elu = bc.deslizamento_e_elu(tipo, norma) if bc._nbr(norma) else tipo != bc.FURO_PADRAO
    if norma == "NBR8800_2008":
        fator, nome_fator = bc.fator_de_furo_2008(tipo), "C_h"
        if entrada.C_e != 1.0:
            linhas.append(
                _linha(
                    "C_e na NBR 8800:2008",
                    None,
                    None,
                    "—",
                    _ref(norma, "6.3.4.3", "", ""),
                    "A 2008 não tem o fator C_e (chapas de enchimento): usa o fator de furo C_h "
                    f"= {fator:g}. O C_e informado ({entrada.C_e:g}) foi ignorado.",
                    "INFO",
                )
            )
    else:
        fator, nome_fator = entrada.C_e, "C_e"
    if not elu:
        F_f = bc.resist_deslizamento(
            F_Tb, mu, norma, n_s=n_s, C_e=fator, nivel="servico", F_t=F_t_Sk
        )
        resistencias["F_f_Rk_kN"] = F_f
        linhas.append(
            _linha(
                "Deslizamento (ELS, força de serviço)",
                R_els,
                F_f,
                "kN",
                _ref(norma, "6.3.4.4", "6.3.4.4", "RCSC 5.4.2"),
                f"F_f,Rk = 0,80·μ·{nome_fator}·F_Tb·n_s·(1 − F_t,Sk/(0,80·F_Tb)) = 0,80·{mu:g}·"
                f"{fator:g}·{F_Tb:g}·{n_s}·(1 − {F_t_Sk:.2f}/{0.8 * F_Tb:.1f}); "
                f"R_max (ELS) = {R_els:.2f} kN",
            )
        )
        return
    if bc._nbr(norma):
        gama_e = bc.gama_e_deslizamento(tipo, norma)
        F_f = bc.resist_deslizamento(
            F_Tb, mu, norma, n_s=n_s, C_e=fator, nivel="elu", F_t=F_t_Sd, gama_e=gama_e
        )
        formula = (
            f"F_f,Rd = 1,13·μ·{nome_fator}·F_Tb·n_s/γ_e·(1 − F_t,Sd/(1,13·F_Tb)) = 1,13·{mu:g}·"
            f"{fator:g}·{F_Tb:g}·{n_s}/{gama_e:.2f}·(1 − {F_t_Sd:.2f}/{1.13 * F_Tb:.1f})"
        )
    else:
        fi = bc.fi_deslizamento_aisc(tipo)
        F_f = fi * bc.resist_deslizamento(
            F_Tb, mu, norma, n_s=n_s, C_e=fator, nivel="elu", F_t=F_t_Sd
        )
        formula = f"φ·μ·1,13·h_f·T_b·n_s·(1 − T_u/(1,13·T_b)), φ = {fi:.2f} pelo tipo de furo"
    resistencias["F_f_Rd_kN"] = F_f
    linhas.append(
        _linha(
            "Deslizamento (ELU, furo alargado ou alongado)",
            R_elu,
            F_f,
            "kN",
            _ref(norma, "6.3.4.3", "6.3.4.3 e Tabela 13 (a confirmar)", "AISC J3.8"),
            formula + f"; R_max (ELU) = {R_elu:.2f} kN",
        )
    )


def _chapa_de_ligacao(
    entrada: EntradaLigacao,
    linhas: list[Verificacao],
    resistencias: dict[str, float],
    intermediarios: dict[str, float],
    N_Sd: float,
    V_Sd: float,
    d_hy: float,
    f_y: float,
    f_u: float,
    furos_padrao: int,
) -> None:
    """Chapa de ligação: tração por N (6.5.3) e cisalhamento por V (6.5.5) na seção transversal
    informada (largura × t, com os furos da seção), cada esforço verificado separado."""
    norma = entrada.norma
    assert entrada.chapa_largura is not None
    t_c = entrada.chapa_t if entrada.chapa_t is not None else entrada.t
    n_furos = entrada.chapa_furos if entrada.chapa_furos is not None else furos_padrao
    folga = bc._P[norma]["folga"]
    c = bc.chapa_de_ligacao(entrada.chapa_largura, t_c, n_furos, d_hy, f_y, f_u, norma, N_Sd)
    resistencias.update(chapa_escoamento_kN=c.escoamento_kN, chapa_ruptura_kN=c.ruptura_kN)
    intermediarios.update(chapa_A_g_mm2=c.A_g, chapa_A_n_mm2=c.A_n, chapa_A_e_mm2=c.A_e)
    ref = _ref(norma, "6.5.3", "6.5.3", "AISC J4.1")
    if N_Sd == 0:
        linhas.append(
            _linha(
                "Chapa de ligação tracionada",
                None,
                None,
                "kN",
                ref,
                "Sem força N na ligação: a chapa de ligação não está tracionada.",
                "INFO",
            )
        )
    else:
        linhas.append(
            _linha(
                "Chapa de ligação — escoamento da seção bruta",
                abs(N_Sd),
                c.escoamento_kN,
                "kN",
                ref,
                f"A_g·f_y/γ_a1; A_g = {entrada.chapa_largura:g} × {t_c:g} = {c.A_g:.1f} mm²; "
                + _t_minimo(c.t_min_escoamento_mm),
            )
        )
        governa = "A_n" if c.A_n <= 0.85 * c.A_g else "0,85·A_g"
        linhas.append(
            _linha(
                "Chapa de ligação — ruptura da seção líquida",
                abs(N_Sd),
                c.ruptura_kN,
                "kN",
                ref,
                f"A_e·f_u/γ_a2 com A_e = mín(A_n; 0,85·A_g) = mín({c.A_n:.1f}; {0.85 * c.A_g:.1f}) = "
                f"{c.A_e:.1f} mm² (governa {governa}); A_n = A_g − {n_furos}·({d_hy:g} + "
                f"{folga:g})·{t_c:g}; {_t_minimo(c.t_min_ruptura_mm)}; C_t não se aplica à chapa "
                "de ligação",
            )
        )
    if V_Sd == 0:
        return
    v = bc.chapa_ao_cisalhamento(entrada.chapa_largura, t_c, n_furos, d_hy, f_y, f_u, norma)
    resistencias.update(
        chapa_cisalhamento_escoamento_kN=v.escoamento_kN,
        chapa_cisalhamento_ruptura_kN=v.ruptura_kN,
    )
    intermediarios.update(chapa_A_gv_mm2=v.A_gv, chapa_A_nv_mm2=v.A_nv)
    ref_v = _ref(norma, "6.5.5", "6.5.5", "AISC J4.2")
    if bc._nbr(norma):
        separado = (
            f"a {_nbr_curta(norma)}, 6.5.5, não traz interação com a tração: N e V verificados "
            "separadamente"
        )
    else:
        separado = "a AISC J4.2 não traz interação com a J4.1: N e V verificados separadamente"
    secao = (
        f"seção de cisalhamento = a seção transversal da chapa informada (b = "
        f"{entrada.chapa_largura:g} mm, {n_furos} furo{'s' if n_furos != 1 else ''}), a mesma da "
        "tração, ao longo da qual V atua; outra seção — a confirmar com a geometria"
    )
    fator_esc = "/γ_a1" if bc._nbr(norma) else "·φ (φ = 1,00)"
    fator_rup = "/γ_a2" if bc._nbr(norma) else "·φ (φ = 0,75)"
    linhas.append(
        _linha(
            "Chapa de ligação — escoamento por cisalhamento (V)",
            abs(V_Sd),
            v.escoamento_kN,
            "kN",
            ref_v,
            f"0,60·A_gv·f_y{fator_esc}; A_gv = {entrada.chapa_largura:g} × {t_c:g} = "
            f"{v.A_gv:.1f} mm²; {secao}; {separado}",
        )
    )
    linhas.append(
        _linha(
            "Chapa de ligação — ruptura por cisalhamento (V)",
            abs(V_Sd),
            v.ruptura_kN,
            "kN",
            ref_v,
            f"0,60·A_nv·f_u{fator_rup}; A_nv = A_gv − {n_furos}·({d_hy:g} + {folga:g})·{t_c:g} = "
            f"{v.A_nv:.1f} mm²",
        )
    )


def _furo_alargado_ou_alongado(
    entrada: EntradaLigacao, linhas: list[Verificacao], d_b: float, e_min: float
) -> None:
    norma, tipo = entrada.norma, entrada.tipo_furo
    permitido, motivo = bc.furo_permitido(tipo, entrada.ligacao_por_atrito)
    linhas.append(
        _linha(
            "Tipo de furo × tipo de ligação",
            None,
            None,
            "—",
            _ref(norma, "6.3.6.2 e Tabela 13", "Tabela 15 (a confirmar)", "AISC J3.2"),
            f"{bc.ROTULOS_DE_FURO[tipo]}, ligação "
            f"{'por atrito' if entrada.ligacao_por_atrito else 'por contato'}: {motivo}.",
            "OK" if permitido else "NÃO OK",
        )
    )
    if norma != "NBR8800_2008":
        linhas.append(
            _linha(
                "Borda mínima com furo alargado ou alongado",
                None,
                None,
                "mm",
                _ref(norma, "", "Tabela 17 (a confirmar)", "AISC J3.4 e Tab. J3.5"),
                "O incremento da distância mínima à borda para este furo não foi aplicado: "
                f"confira na tabela da norma (a da {_nbr_curta('NBR8800_2024')} ainda não foi "
                "conferida).",
                "ALERTA",
            )
        )
        return
    for nome, distancia, perpendicular in (
        ("na direção da força", entrada.e, True),
        ("vertical", entrada.e_v, False),
    ):
        if distancia is None:
            continue
        acrescimo = bc.incremento_de_borda_2008(d_b, tipo, perpendicular)
        linhas.append(
            _linha(
                f"Borda mínima com furo {bc.ROTULOS_DE_FURO[tipo].lower()} ({nome})",
                e_min + acrescimo,
                distancia,
                "mm",
                _ref(norma, "6.3.11.2", "", ""),
                f"e_mín + β·d_b = {e_min:g} + {acrescimo:.1f} mm",
            )
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
    equacoes: tuple[str, ...] = (),
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
        equacoes=equacoes,
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
            F_t_Rd_kN=resultado.resistencias.get("F_t_Rd_kN"),
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
    "NBR8800_2008": (
        f"{NORMAS_ROTULOS['NBR8800_2008']}, itens 5.2, 6.3, 6.5.3, 6.5.5 e 6.5.6; "
        "Tabelas 14, 16, 19 e A.3."
    ),
    "NBR8800_2024": (
        f"{NORMAS_ROTULOS['NBR8800_2024']}, itens 5.2, 6.3, 6.5 e 6.8; Tabelas 3, 14, 16, 19 e A.3."
    ),
    "AISC360_LRFD": "ANSI/AISC 360, capítulos D, J3 e J4 (LRFD), e AISC Design Guide 29.",
    "RCSC2004": "RCSC Specification for Structural Joints Using ASTM A325 or A490 Bolts (2004), §5 e §8.",
}

#: Casas decimais das colunas Solicitante e Resistente do memorial desta ligação (uniformes).
CASAS_DECIMAIS_DO_MEMORIAL = 2


def _nome_curto_norma(norma: str) -> str:
    return NORMAS_ROTULOS[norma].split(" (")[0]


def _num(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def tabela_da_tracao(entrada: EntradaLigacao, resultado: ResultadoLigacao) -> dict[str, Any] | None:
    """A seção "Tração, interação e efeito de alavanca" do memorial; ``None`` sem tração no
    parafuso (F_t,Sd = 0): o memorial só a mostra quando a tração existe."""
    from core.memorial_verificacoes import decimal_ptbr

    F_t_Sd = resultado.forcas.get("F_t_Sd_kN", 0.0)
    F_t_Rd = resultado.resistencias.get("F_t_Rd_kN")
    if not F_t_Sd > 0 or F_t_Rd is None:
        return None
    norma = entrada.norma
    nbr = bc._nbr(norma)
    im = resultado.intermediarios
    d_b = bc.dados_parafuso(entrada.designacao)["d_b"]
    A_b = im.get("A_b_mm2", bc.area_bruta(d_b))
    linhas: list[list[str]] = [
        ["Área bruta do parafuso A_b", _num(A_b), "mm²", f"π·d_b²/4 = π·{d_b:g}²/4"],
    ]
    if nbr:
        A_be = im.get("A_be_mm2", bc.area_efetiva(d_b))
        f_ub = bc.fub(entrada.grau, d_b, norma)
        g_a2 = bc._P[norma]["g_a2"]
        linhas.append(
            [
                "Área efetiva à tração A_be",
                _num(A_be),
                "mm²",
                f"A_be = 0,75·A_b = 0,75·{A_b:.2f} ({_ref(norma, '6.3.2.2', '6.3.2.2', '')})",
            ]
        )
        linhas.append(
            [
                "Tração resistente F_t,Rd",
                _num(F_t_Rd),
                "kN",
                f"F_t,Rd = A_be·f_ub/γ_a2 = {A_be:.2f}·{f_ub:g}/{g_a2:g} "
                f"({_ref(norma, '6.3.3.1', '6.3.3.1', '')})",
            ]
        )
    else:
        linhas.append(
            [
                "Tração resistente φ·R_n",
                _num(F_t_Rd),
                "kN",
                f"0,75·F_nt·A_b = 0,75·{bc.GRAUS[entrada.grau].Fnt_AISC:g}·{A_b:.2f} "
                "(AISC J3.6 / RCSC 5.1)",
            ]
        )
    if "F_t_Rd_com_alavanca_kN" in im:
        linhas.append(
            [
                "Tração resistente com alavanca",
                _num(im["F_t_Rd_com_alavanca_kN"]),
                "kN",
                f"F_t,Rd reduzida pela alavanca ({_ref(norma, '6.3.5.2', '', '')})",
            ]
        )
    linhas.append(
        [
            "Tração no parafuso mais tracionado F_t,Sd",
            _num(F_t_Sd),
            "kN",
            f"N_t,Sd = {resultado.forcas.get('N_t_Sd_kN', 0.0):.2f} kN e M_t,Sd = "
            f"{resultado.forcas.get('M_t_Sd_kNm', 0.0):.2f} kN·m distribuídos pelos parafusos "
            "(eixo neutro no centro do grupo)"
            + (
                f"; com alavanca (F_t,0,Sd = {resultado.forcas.get('F_t0_Sd_kN', 0.0):.2f} kN)"
                if F_t_Sd > resultado.forcas.get("F_t0_Sd_kN", F_t_Sd) + 1e-9
                else ""
            ),
        ]
    )
    if "interacao_tracao_corte" in im:
        linhas.append(
            [
                "Interação tração + corte",
                _num(im["interacao_tracao_corte"], 3),
                "—",
                f"(F_t,Sd/F_t,Rd)² + (F_v,Sd/F_v,Rd)² = ({im['interacao_F_t_Sd_kN']:.2f}/"
                f"{im.get('interacao_F_t_Rd_kN', F_t_Rd):.2f})² + ({im['interacao_F_v_Sd_kN']:.2f}/"
                f"{resultado.resistencias['F_v_Rd_kN']:.2f})² ≤ 1,0 no parafuso crítico "
                f"({_ref(norma, '6.3.3.4', '6.3.3.4', 'RCSC 5.2')})",
            ]
        )
    elif nbr:
        linhas.append(
            ["Interação tração + corte", "-", "—", "Sem corte no parafuso: não se aplica."]
        )
    else:
        linhas.append(
            [
                "Interação tração + corte",
                "-",
                "—",
                "AISC J3.7: F'_nt reduzido, na tabela de verificações.",
            ]
        )
    if "limite_tabela_kN" in im:
        k = im["limite_tabela_coef"]
        tabela = bc.TABELA_INTERACAO[norma]
        usada = "usada como verificação" if entrada.interacao_por_tabela else "só informativa"
        linhas.append(
            [
                f"Limite da {tabela} (alternativa)",
                _num(im["limite_tabela_kN"]),
                "kN",
                f"f_ub·A_b/γ_a2 − {k:g}·F_v,Sd = {im['limite_tabela_kN'] + k * im['limite_tabela_F_v_Sd_kN']:.2f}"
                f" − {k:g}·{im['limite_tabela_F_v_Sd_kN']:.2f}, com F_t,Sd = "
                f"{im['limite_tabela_F_t_Sd_kN']:.2f} kN ({usada}; "
                f"{_ref(norma, '6.3.3.4 e Tabela 11', '6.3.3.4 e Tabela 12', '')})",
            ]
        )
    if "t_rigida_mm" in im:
        t_placa = entrada.alav_t if entrada.alav_t is not None else entrada.t
        linhas.append(
            [
                "Placa rígida: t mínimo (sem alavanca)",
                _num(im["t_rigida_mm"]),
                "mm",
                f"√[4·(b − 0,5·d_b)·F_t,0,Sd·γ_a1/(p·f_u)] com a = {entrada.alav_a:g}, b = "
                f"{entrada.alav_b:g}, p = {entrada.alav_p:g} mm; t da placa = {t_placa:g} mm "
                f"({_ref(norma, '6.3.5', '6.3.5 (a confirmar)', '')})",
            ]
        )
    elif "t_alavanca_req_mm" in im:
        linhas.append(
            [
                "Chapa fletida: t requerido",
                _num(im["t_alavanca_req_mm"]),
                "mm",
                f"M = F_t,Sd·b na largura p ({_ref(norma, '6.3.5.2', '', '')})",
            ]
        )
    else:
        linhas.append(
            [
                "Efeito de alavanca",
                "-",
                "-",
                "Não verificado: a geometria da chapa fletida (a, b, p) não foi informada.",
            ]
        )
    return {
        "subtitulo": "Tração, interação e efeito de alavanca",
        "legenda": "Valores da tração no parafuso (aparecem só quando há F_t,Sd > 0).",
        "cabecalhos": ["Grandeza", "Valor", "Un.", "Cálculo e referência"],
        "linhas": [[a, b, c, decimal_ptbr(d)] for a, b, c, d in linhas],
        "larguras": [2600, 1000, 560, 5200],
        "fonte": 7.2,
    }


def _premissas(entrada: EntradaLigacao, resultado: ResultadoLigacao) -> list[str]:
    premissas = [
        "Tração do grupo distribuída pelos parafusos com o eixo neutro no centro do grupo; "
        "fadiga fora do escopo.",
        "Torque de aperto é estimativa; instalar por rotação da porca, chave calibrada ou "
        "indicador de tração.",
        "t = espessura da parte ligada mais fina (nunca a soma).",
    ]
    if resultado.forcas.get("V_Sd_kN", 0.0) != 0:
        if entrada.chapa_largura is None:
            premissas.append(
                "Verificações da peça e do gusset consideram apenas N; V transversal não é "
                "verificado na chapa (largura da chapa de ligação não informada)."
            )
        else:
            premissas.append(
                "Cisalhamento por V verificado na seção transversal da chapa de ligação informada "
                "(largura × espessura, com os furos), separado da tração por N."
            )
    return premissas


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
        "tracao_parafuso_critico_ELU_kN": resultado.forcas.get("F_t_Sd_kN"),
        "tracao_resistente_F_t_Rd_kN": resultado.resistencias.get("F_t_Rd_kN"),
        "torque_estimado_Nm": resultado.torque_referencia_Nm,
        "verificações": linhas_para_registro(resultado.verificacoes),
        "casas_decimais_da_tabela": CASAS_DECIMAIS_DO_MEMORIAL,
    }
    tracao = tabela_da_tracao(entrada, resultado)
    if tracao is not None:
        resultados["tabelas_memorial"] = [tracao]
    if pior is not None and math.isfinite(pior):
        resultados["utilizacao_maxima"] = pior
    resultados = {chave: valor for chave, valor in resultados.items() if valor is not None}

    alertas = [
        f"{v.nome}: {v.formula}" for v in resultado.verificacoes if v.status in ("NÃO OK", "ALERTA")
    ]

    grade = entrada.coordenadas is None
    entradas: dict[str, Any] = {
        "modo": "Ligação estrutural de aço",
        # A designação da tabela central (a mesma do título e das referências), não o código.
        "norma": NORMAS_ROTULOS[entrada.norma],
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
        # Passo e gabarito só com mais de uma coluna/linha: numa linha só, g não existe.
        "passo_s_mm": entrada.s if grade and entrada.n_col > 1 else None,
        "gabarito_g_mm": entrada.g if grade and entrada.n_lin > 1 else None,
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
        "tipo_de_furo": bc.ROTULOS_DE_FURO[entrada.tipo_furo],
        "N_t_grupo_kN": entrada.N_t or None,
        "M_t_fora_do_plano_kNm": entrada.M_t or None,
        "interacao_pela_tabela": entrada.interacao_por_tabela or None,
        "alavanca_a_b_p_mm": [entrada.alav_a, entrada.alav_b, entrada.alav_p]
        if entrada.alavanca
        else None,
        "F_t_com_alavanca_kN": entrada.F_t_com_alavanca,
        "chapa_de_ligacao_largura_mm": entrada.chapa_largura,
        "chapa_de_ligacao_t_mm": entrada.chapa_t,
        "chapa_de_ligacao_furos": entrada.chapa_furos
        if entrada.chapa_largura is not None
        else None,
        "f_y_MPa": entrada.f_y if entrada.aco == ACO_INFORMADO else None,
        "f_u_MPa": entrada.f_u if entrada.aco == ACO_INFORMADO else None,
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
            "rasgamento, tração e interação com o corte, alavanca, deslizamento, peça tracionada, "
            "chapa de ligação, disposições construtivas e critério Anglo."
        ),
        entradas=entradas,
        resultados=resultados,
        metodo=(
            "Grupo de parafusos pelo método elástico (Kulak, Fisher & Struik, cap. 13), "
            "conservador frente ao centro instantâneo de rotação; resistências pela "
            f"{NORMAS_ROTULOS[entrada.norma]}, com o item em cada linha da tabela de "
            "verificações. O cálculo é conferido por testes automáticos com os exemplos do AISC "
            "Design Guide 29 (págs. 157–159 e 185–186) e por casos conferidos à mão."
        ),
        equacoes=list(resultado.equacoes),
        criterios=[
            "ELU: força de cálculo (γ_f·F_k) ≤ resistência de cálculo.",
            "Deslizamento: força de serviço (característica) ≤ F_f,Rk.",
            "Disposições: NBR 6.3.7 a 6.3.12 (Tab. 16) e AISC J3.3 a J3.5.",
            "Anglo AA-BR-DPST-DR-0001, item 9.1.",
        ],
        premissas=_premissas(entrada, resultado),
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


def memorial_da_ligacao(
    entrada: EntradaLigacao,
    resultado: ResultadoLigacao,
    menor_parafuso: str | None,
    *,
    projeto: Mapping[str, Any] | None = None,
    formato: str = "word",
) -> bytes:
    """O memorial só desta ligação, em Word ou PDF, no padrão do memorial do projeto.

    Com o projeto ativo, a capa e o controle levam os dados dele; sem projeto, ficam
    "[a preencher]". Entra só o registro desta ligação (os outros cálculos do projeto não).
    """
    import importlib

    from core.technical_records import normalizar_registro_tecnico

    # O gerador do memorial ainda está fora da lista do mypy (adoção gradual): importado pelo nome
    # para não arrastar os módulos dele para a verificação deste.
    relatorio = importlib.import_module("core.project_report")
    registro = normalizar_registro_tecnico(registro_ligacao(entrada, resultado, menor_parafuso))
    base: dict[str, Any] = dict(projeto) if projeto else {"nome": "Ligação parafusada"}
    base["registros_tecnicos"] = [registro]
    nome = (
        "gerar_relatorio_industrial_pdf" if formato == "pdf" else "gerar_relatorio_industrial_word"
    )
    conteudo: bytes = getattr(relatorio, nome)(base, secoes_incluidas=["registros"])
    return conteudo
