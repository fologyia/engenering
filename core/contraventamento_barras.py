"""Verificação das diagonais de contraventamento pela NBR 8800 (Projeto de revisão de 2024).

Três famílias, as usuais em plataformas e estruturas abertas:

* **cantoneira simples** ligada por uma aba (parafusos numa linha ou solda longitudinal):
  tração (5.2: escoamento da seção bruta e ruptura da seção líquida efetiva, ``A_e = C_t·A_n`` com
  ``C_t = 1 − e_c/ℓ_c ≥ A_c/A_g``, 5.2.5-c), compressão pelo comprimento equivalente de 5.3.5.4
  (``N_ex = π²·E·I_x1/L_x1,eq²``, com ``Q`` das abas — grupo 3 do Anexo F) e, na ligação
  parafusada, corte e pressão de contato dos parafusos (6.3.3.2 e 6.3.3.3) e colapso por
  rasgamento da aba (6.5.6);
* **tubo** do catálogo (circular ou retangular) com chapa de nó concêntrica soldada num rasgo:
  tração com ``C_t = [1 + (e_c/ℓ_c)^3,2]^−10`` (5.2.5-e) e área líquida descontando o rasgo,
  compressão pela NBR 8800 (5.3, ``χ``, ``Q``) e a solda de filete (6.2.5);
* **barra redonda** (tirante) rosqueada: ``F_t,Rd = 0,75·A_b·f_ub/γ_a2 ≤ A_b·f_y/γ_a1`` (6.3.3.1).
  Não trabalha à compressão.

Esbeltez: tração ≤ 300 (recomendação de 5.2.8.1, dispensada para tirantes pré-tensionados) e
compressão ≤ 200 (5.3.4.1); na cantoneira, ``L_x1,eq/r_x1 ≤ 200`` (5.3.5.4.1-d).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core import bolted_connection as bc
from core import cantoneiras as ct
from core import nbr8800
from core import section_catalog as sc
from core import steel_sections as ss
from core.verificacao import Verificacao

NORMA = "NBR8800_2024"
REF = "NBR 8800:2024"
E_MPA = 200_000.0
G_MPA = 77_000.0
GAMMA_A1 = nbr8800.GAMMA_A1
GAMMA_A2 = nbr8800.GAMMA_A2
GAMMA_W2 = 1.35  # solda (metal da solda), Tabela 3
FW_E70_MPA = 485.0  # resistência à tração do metal da solda E70XX

FAMILIA_CANTONEIRA = "Cantoneira simples"
FAMILIA_TUBO = "Tubo (catálogo)"
FAMILIA_BARRA_REDONDA = "Barra redonda (tirante rosqueado)"
FAMILIAS = (FAMILIA_CANTONEIRA, FAMILIA_TUBO, FAMILIA_BARRA_REDONDA)

LIGACAO_PARAFUSADA = "parafusada"
LIGACAO_SOLDADA = "soldada"
LIGACOES = (LIGACAO_PARAFUSADA, LIGACAO_SOLDADA)

ACOS = dict(bc.ACOS)
FOLGA_DO_RASGO_MM = 2.0  # rasgo do tubo: espessura da chapa + 2 mm


class DiagonalInvalida(ValueError):
    """Dado que a verificação não aceita; a mensagem diz o que corrigir."""


@dataclass(frozen=True)
class Diagonal:
    """A barra do contraventamento e a sua ligação na chapa de nó."""

    familia: str = FAMILIA_CANTONEIRA
    perfil: str = 'L 2 1/2" × 1/4"'
    aco: str = "ASTM A36"
    ligacao: str = LIGACAO_PARAFUSADA
    parafuso: str = '5/8"'
    grau: str = "A325"
    rosca_no_plano: bool = True
    n_parafusos: int = 3  # numa linha, na direção da força
    passo_mm: float = 50.0
    borda_mm: float = 30.0  # do último furo à ponta da barra
    gabarito_mm: float = 0.0  # dorso da cantoneira à linha de furação; 0 = usual (~0,55·b)
    comprimento_solda_mm: float = 120.0
    perna_solda_mm: float = 5.0
    t_chapa_no_mm: float = 9.5
    aco_chapa_no: str = "ASTM A36"


def perfis_da_familia(familia: str) -> list[str]:
    """Nomes que a família aceita (cantoneiras da série; tubos e barras do catálogo)."""
    if familia == FAMILIA_CANTONEIRA:
        return list(ct.CATALOGO_CANTONEIRAS)
    catalogo = sc.listar_perfis()
    if familia == FAMILIA_TUBO:
        return [n for n, p in catalogo.items() if ss.e_tubo_circular(p) or ss.e_tubo_retangular(p)]
    if familia == FAMILIA_BARRA_REDONDA:
        return [n for n, p in catalogo.items() if "barra circular" in p.familia.casefold()]
    raise DiagonalInvalida(f"Família de diagonal desconhecida: {familia!r}.")


def largura_vista_mm(d: Diagonal) -> float:
    """Largura da barra vista pelo vento (para a área exposta da estrutura)."""
    if d.familia == FAMILIA_CANTONEIRA:
        return ct.obter_cantoneira(d.perfil).b_mm
    perfil = sc.obter_perfil(d.perfil)
    return max(perfil.altura_mm, perfil.largura_mm)


def area_bruta_mm2(d: Diagonal) -> float:
    if d.familia == FAMILIA_CANTONEIRA:
        return ct.obter_cantoneira(d.perfil).area_mm2
    return sc.obter_perfil(d.perfil).area_mm2


def validar(d: Diagonal) -> list[str]:
    erros: list[str] = []
    if d.familia not in FAMILIAS:
        return [f"Família de diagonal desconhecida: {d.familia!r}."]
    if d.perfil not in perfis_da_familia(d.familia):
        erros.append(f"O perfil {d.perfil!r} não pertence à família {d.familia}.")
    if d.aco not in ACOS or d.aco_chapa_no not in ACOS:
        erros.append("Aço desconhecido.")
    if d.ligacao not in LIGACOES:
        erros.append(f"Ligação desconhecida: {d.ligacao!r}.")
    if d.familia == FAMILIA_CANTONEIRA and d.ligacao == LIGACAO_PARAFUSADA:
        if d.parafuso not in bc.PARAFUSOS:
            erros.append(f"Parafuso desconhecido: {d.parafuso!r}.")
        if d.grau not in bc.GRAUS:
            erros.append(f"Grau de parafuso desconhecido: {d.grau!r}.")
        if d.n_parafusos < 2:
            erros.append(
                "A cantoneira precisa de ao menos 2 parafusos na direção da força (5.3.5.4.1-b e "
                "o C_t de 5.2.5-c)."
            )
        if not (d.passo_mm > 0 and d.borda_mm > 0):
            erros.append("O passo e a distância à borda precisam ser maiores que zero.")
    if (d.familia == FAMILIA_TUBO or d.ligacao == LIGACAO_SOLDADA) and not (
        d.comprimento_solda_mm > 0 and d.perna_solda_mm > 0
    ):
        erros.append("A solda precisa de comprimento e perna maiores que zero.")
    if d.familia == FAMILIA_TUBO and d.ligacao != LIGACAO_SOLDADA:
        erros.append("O tubo é ligado por chapa de nó soldada num rasgo: escolha ligação soldada.")
    if not d.t_chapa_no_mm > 0:
        erros.append("A espessura da chapa de nó precisa ser maior que zero.")
    return erros


# ---------------------------------------------------------------------------------------------
# Linhas de verificação
# ---------------------------------------------------------------------------------------------
def _linha(
    nome: str, solicitante: float, resistente: float, unidade: str, formula: str, ref: str
) -> Verificacao:
    return Verificacao(nome, solicitante, resistente, unidade, f"{REF} {ref}", formula)


def _limite(nome: str, valor: float, limite: float, formula: str, ref: str) -> Verificacao:
    return Verificacao(nome, valor, limite, "-", f"{REF} {ref}", formula, tipo="limite")


def _info(nome: str, texto: str, ref: str, status: str = "INFO") -> Verificacao:
    return Verificacao(
        nome, None, None, "-", f"{REF} {ref}", texto, status=status, tipo="informativo"
    )


def _n(valor: float, casas: int = 1) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


@dataclass(frozen=True)
class ResultadoDiagonal:
    verificacoes: tuple[Verificacao, ...]
    resistencia_tracao_kN: float | None
    resistencia_compressao_kN: float | None


def verificar_diagonal(
    d: Diagonal,
    prefixo: str,
    *,
    comprimento_mm: float,
    comprimento_destravado_mm: float,
    tracao_kN: float,
    compressao_kN: float,
) -> ResultadoDiagonal:
    """Tração, compressão, esbeltez e ligação da diagonal (forças de cálculo, em kN).

    ``comprimento_destravado_mm`` é o comprimento entre pontos travados (a metade da diagonal num X
    ligado no cruzamento). ``prefixo`` vai no começo do nome de cada linha (andar e direção).
    """
    erros = validar(d)
    if erros:
        raise DiagonalInvalida(" ".join(erros))
    fy, fu = ACOS[d.aco]
    linhas: list[Verificacao] = []
    nt_rd: float | None = None
    nc_rd: float | None = None
    lb = comprimento_destravado_mm

    if d.familia == FAMILIA_CANTONEIRA:
        cant = ct.obter_cantoneira(d.perfil)
        nt_rd = _tracao_cantoneira(d, cant, fy, fu, prefixo, tracao_kN, linhas)
        if tracao_kN > 0:
            linhas.append(
                _limite(
                    f"{prefixo}: esbeltez da diagonal tracionada",
                    lb / cant.r_z_mm,
                    nbr8800.ESBELTEZ_MAXIMA_TRACAO,
                    f"L/r_min = {_n(lb, 0)}/{_n(cant.r_z_mm, 1)} ≤ 300 (recomendação)",
                    "5.2.8.1",
                )
            )
        if compressao_kN > 0:
            nc_rd = _compressao_cantoneira(d, cant, fy, prefixo, lb, compressao_kN, linhas)
        if d.ligacao == LIGACAO_PARAFUSADA:
            _parafusos_cantoneira(d, cant, fy, fu, prefixo, max(tracao_kN, compressao_kN), linhas)
        else:
            _solda(d, prefixo, max(tracao_kN, compressao_kN), linhas, numero_de_cordoes=2)
    elif d.familia == FAMILIA_TUBO:
        perfil = sc.obter_perfil(d.perfil)
        nt_rd = _tracao_tubo(d, perfil, fy, fu, prefixo, tracao_kN, linhas)
        raio = min(perfil.rx_mm, perfil.ry_mm)
        if tracao_kN > 0:
            linhas.append(
                _limite(
                    f"{prefixo}: esbeltez da diagonal tracionada",
                    lb / raio,
                    nbr8800.ESBELTEZ_MAXIMA_TRACAO,
                    f"L/r_min = {_n(lb, 0)}/{_n(raio, 1)} ≤ 300 (recomendação)",
                    "5.2.8.1",
                )
            )
        if compressao_kN > 0:
            resultado = nbr8800.verificar_compressao(
                perfil, fy, E_MPA, G_MPA, lb, 1.0, 1.0, compressao_kN * 1e3
            )
            nc_rd = resultado.resistencia_N / 1e3
            linhas.append(
                _linha(
                    f"{prefixo}: compressão da diagonal",
                    compressao_kN,
                    nc_rd,
                    "kN",
                    f"N_c,Rd = χ·Q·A_g·f_y/γ_a1 = {_n(resultado.chi, 3)}·{_n(resultado.fator_q, 3)}·"
                    f"{_n(perfil.area_mm2, 0)}·{_n(fy, 0)}/1,10 (λ₀ = {_n(resultado.lambda_0, 2)})",
                    "5.3.2",
                )
            )
            linhas.append(
                _limite(
                    f"{prefixo}: esbeltez da diagonal comprimida",
                    max(resultado.esbeltez_x, resultado.esbeltez_y),
                    nbr8800.ESBELTEZ_MAXIMA_COMPRESSAO,
                    "K·L/r ≤ 200",
                    "5.3.4.1",
                )
            )
        _solda(d, prefixo, max(tracao_kN, compressao_kN), linhas, numero_de_cordoes=4)
        _parede_do_tubo(d, perfil, fy, prefixo, max(tracao_kN, compressao_kN), linhas)
    else:
        perfil = sc.obter_perfil(d.perfil)
        db = perfil.altura_mm
        ab = math.pi * db**2 / 4.0
        rosca = 0.75 * ab * fu / GAMMA_A2 / 1e3
        corpo = ab * fy / GAMMA_A1 / 1e3
        nt_rd = min(rosca, corpo)
        if tracao_kN > 0:
            linhas.append(
                _linha(
                    f"{prefixo}: tração do tirante (rosca)",
                    tracao_kN,
                    nt_rd,
                    "kN",
                    f"F_t,Rd = mín(0,75·A_b·f_u/γ_a2 = {_n(rosca)}; A_b·f_y/γ_a1 = {_n(corpo)}) kN, "
                    f"A_b = {_n(ab, 0)} mm²",
                    "6.3.3.1",
                )
            )
            linhas.append(
                _info(
                    f"{prefixo}: esbeltez do tirante",
                    "Tirante de barra redonda: o limite L/r ≤ 300 é dispensado se for montado com "
                    "pré-tensão (esticador). Especifique a pré-tensão no desenho.",
                    "5.2.8.1",
                    status="ALERTA",
                )
            )
        if compressao_kN > 0:
            nc_rd = 0.0
            linhas.append(
                Verificacao(
                    f"{prefixo}: compressão do tirante",
                    compressao_kN,
                    0.0,
                    "kN",
                    f"{REF} 5.3",
                    "Barra redonda não trabalha à compressão: use contraventamento em X só "
                    "tração, ou outra família de barra.",
                    status="NÃO OK",
                    aproveitamento=math.inf,
                )
            )
    return ResultadoDiagonal(tuple(linhas), nt_rd, nc_rd)


def _tracao_cantoneira(
    d: Diagonal,
    cant: ct.Cantoneira,
    fy: float,
    fu: float,
    prefixo: str,
    tracao_kN: float,
    linhas: list[Verificacao],
) -> float:
    ag = cant.area_mm2
    if d.ligacao == LIGACAO_PARAFUSADA:
        dh = bc.PARAFUSOS[d.parafuso][1]
        an = ag - (dh + 2.0) * cant.t_mm
        lc = (d.n_parafusos - 1) * d.passo_mm
        origem_an = f"A_n = A_g − (d_h + 2)·t = {_n(ag, 0)} − ({_n(dh)} + 2)·{_n(cant.t_mm, 2)}"
    else:
        an = ag
        lc = d.comprimento_solda_mm
        origem_an = "A_n = A_g (solda longitudinal)"
    ct_calc = 1.0 - cant.x_barra_mm / lc
    ct_min = cant.area_aba_mm2 / ag
    coef = min(1.0, max(ct_calc, ct_min))
    escoamento = ag * fy / GAMMA_A1 / 1e3
    ruptura = coef * an * fu / GAMMA_A2 / 1e3
    resistencia = min(escoamento, ruptura)
    if tracao_kN > 0:
        linhas.append(
            _linha(
                f"{prefixo}: tração da diagonal",
                tracao_kN,
                resistencia,
                "kN",
                f"N_t,Rd = mín(A_g·f_y/γ_a1 = {_n(escoamento)}; C_t·A_n·f_u/γ_a2 = {_n(ruptura)}) "
                f"kN; {origem_an}; C_t = máx(1 − e_c/ℓ_c = 1 − {_n(cant.x_barra_mm)}/{_n(lc, 0)}; "
                f"A_c/A_g = {_n(ct_min, 3)}) = {_n(coef, 3)}",
                "5.2.2, 5.2.4 e 5.2.5-c",
            )
        )
    return resistencia


def _compressao_cantoneira(
    d: Diagonal,
    cant: ct.Cantoneira,
    fy: float,
    prefixo: str,
    lb: float,
    compressao_kN: float,
    linhas: list[Verificacao],
) -> float:
    rx1 = cant.r_x_mm
    lx1 = lb
    razao = lx1 / rx1
    if razao <= 80.0:
        leq = 72.0 * rx1 + 0.75 * lx1
        texto_leq = f"L_x1/r_x1 = {_n(razao)} ≤ 80: L_eq = 72·r_x1 + 0,75·L_x1"
    else:
        leq = 32.0 * rx1 + 1.25 * lx1
        texto_leq = f"L_x1/r_x1 = {_n(razao)} > 80: L_eq = 32·r_x1 + 1,25·L_x1"
    ne = math.pi**2 * E_MPA * cant.i_x_mm4 / leq**2
    limite_bt = 0.71 * math.sqrt(E_MPA / fy)
    q = nbr8800._qs_grupo(cant.b_sobre_t, fy, E_MPA, "3")
    lambda_0 = math.sqrt(q * cant.area_mm2 * fy / ne)
    chi = nbr8800.fator_chi(lambda_0)
    resistencia = chi * q * cant.area_mm2 * fy / GAMMA_A1 / 1e3
    linhas.append(
        _linha(
            f"{prefixo}: compressão da diagonal",
            compressao_kN,
            resistencia,
            "kN",
            f"{texto_leq} = {_n(leq, 0)} mm; N_ex = π²·E·I_x1/L_eq² = {_n(ne / 1e3)} kN; "
            f"Q = {_n(q, 3)}; λ₀ = {_n(lambda_0, 3)}; χ = {_n(chi, 3)}; N_c,Rd = χ·Q·A_g·f_y/γ_a1",
            "5.3.2 e 5.3.5.4",
        )
    )
    linhas.append(
        _limite(
            f"{prefixo}: esbeltez equivalente da cantoneira",
            leq / rx1,
            200.0,
            f"L_x1,eq/r_x1 = {_n(leq, 0)}/{_n(rx1, 1)} ≤ 200",
            "5.3.5.4.1-d",
        )
    )
    if cant.b_sobre_t > limite_bt:
        linhas.append(
            _info(
                f"{prefixo}: b/t da cantoneira",
                f"b/t = {_n(cant.b_sobre_t)} > 0,71·√(E/f_y) = {_n(limite_bt)}: a norma pede "
                "também a flambagem por flexo-torção (5.3.5.4.4). Prefira uma aba mais espessa.",
                "5.3.5.4.4",
                status="ALERTA",
            )
        )
    return resistencia


def _parafusos_cantoneira(
    d: Diagonal,
    cant: ct.Cantoneira,
    fy: float,
    fu: float,
    prefixo: str,
    forca_kN: float,
    linhas: list[Verificacao],
) -> None:
    db, dh, emin, _, _ = bc.PARAFUSOS[d.parafuso]
    fu_chapa = ACOS[d.aco_chapa_no][1]
    fv = bc.resist_corte(db, d.grau, NORMA, rosca_no_plano=d.rosca_no_plano, n_planos=1)
    contato_ext = min(
        bc.resist_contato(db, cant.t_mm, fu, bc.lf_borda(d.borda_mm, dh), NORMA),
        bc.resist_contato(db, d.t_chapa_no_mm, fu_chapa, None, NORMA),
    )
    contato_int = min(
        bc.resist_contato(db, cant.t_mm, fu, bc.lf_entre_furos(d.passo_mm, dh), NORMA),
        bc.resist_contato(db, d.t_chapa_no_mm, fu_chapa, None, NORMA),
    )
    grupo = bc.resist_grupo_axial(1, d.n_parafusos, fv, contato_ext, contato_int)
    linhas.append(
        _linha(
            f"{prefixo}: parafusos da diagonal (corte × contato)",
            forca_kN,
            grupo,
            "kN",
            f"{d.n_parafusos} × {d.parafuso} {d.grau}, 1 plano de corte: F_v,Rd = {_n(fv)} kN; "
            f"contato no extremo {_n(contato_ext)} kN e nos internos {_n(contato_int)} kN "
            f"(aba t = {_n(cant.t_mm, 2)} mm e chapa t = {_n(d.t_chapa_no_mm)} mm)",
            "6.3.3.2 e 6.3.3.3",
        )
    )
    g = d.gabarito_mm or ct.gabarito_usual_mm(cant.b_mm)
    dhl = dh + 2.0
    comprimento = d.borda_mm + (d.n_parafusos - 1) * d.passo_mm
    agv = comprimento * cant.t_mm
    anv = (comprimento - (d.n_parafusos - 0.5) * dhl) * cant.t_mm
    ant = (cant.b_mm - g - 0.5 * dhl) * cant.t_mm
    if ant <= 0:
        linhas.append(
            _info(
                f"{prefixo}: colapso por rasgamento da aba",
                f"Gabarito {_n(g, 0)} mm não deixa aba livre além do furo: revise o gabarito.",
                "6.5.6",
                status="NÃO OK",
            )
        )
    else:
        bloco = bc.resist_colapso_rasgamento(agv, anv, ant, fy, fu, NORMA, C_ts=1.0)
        linhas.append(
            _linha(
                f"{prefixo}: colapso por rasgamento da aba",
                forca_kN,
                bloco,
                "kN",
                f"A_gv = {_n(agv, 0)}, A_nv = {_n(anv, 0)}, A_nt = {_n(ant, 0)} mm² (gabarito "
                f"{_n(g, 0)} mm); F_r,Rd = (0,6·f_u·A_nv + f_u·A_nt)/γ_a2 ≤ "
                "(0,6·f_y·A_gv + f_u·A_nt)/γ_a2",
                "6.5.6",
            )
        )
    linhas.append(
        _limite(
            f"{prefixo}: espaçamento dos furos",
            2.7 * db,
            d.passo_mm,
            f"passo {_n(d.passo_mm, 0)} mm ≥ 2,7·d_b = {_n(2.7 * db, 0)} mm (de preferência 3·d_b)",
            "6.3.9",
        )
    )
    linhas.append(
        _limite(
            f"{prefixo}: distância do furo à borda",
            float(emin),
            d.borda_mm,
            f"borda {_n(d.borda_mm, 0)} mm ≥ mínima {emin} mm (Tabela 16)",
            "6.3.11",
        )
    )


def _tracao_tubo(
    d: Diagonal,
    perfil: ss.PerfilAco,
    fy: float,
    fu: float,
    prefixo: str,
    tracao_kN: float,
    linhas: list[Verificacao],
) -> float:
    ag = perfil.area_mm2
    t = perfil.espessura_alma_mm
    an = ag - 2.0 * t * (d.t_chapa_no_mm + FOLGA_DO_RASGO_MM)
    lc = d.comprimento_solda_mm
    if ss.e_tubo_circular(perfil):
        ec = perfil.altura_mm / math.pi
        origem = "e_c = D/π"
    else:
        h, b = perfil.altura_mm, perfil.largura_mm
        ec = max((h**2 + 2 * h * b), (b**2 + 2 * h * b)) / (4.0 * (h + b))
        origem = "e_c = (h² + 2hb)/[4(h + b)] (maior das duas orientações)"
    coef = (1.0 + (ec / lc) ** 3.2) ** -10.0
    escoamento = ag * fy / GAMMA_A1 / 1e3
    ruptura = coef * an * fu / GAMMA_A2 / 1e3
    resistencia = min(escoamento, ruptura)
    if tracao_kN > 0:
        linhas.append(
            _linha(
                f"{prefixo}: tração da diagonal",
                tracao_kN,
                resistencia,
                "kN",
                f"N_t,Rd = mín(A_g·f_y/γ_a1 = {_n(escoamento)}; C_t·A_n·f_u/γ_a2 = {_n(ruptura)}) "
                f"kN; A_n = A_g − 2·t·(t_chapa + 2) = {_n(an, 0)} mm²; {origem} = {_n(ec)} mm; "
                f"C_t = [1 + (e_c/ℓ_c)^3,2]^−10 = {_n(coef, 3)} (ℓ_c = {_n(lc, 0)} mm)",
                "5.2.2 e 5.2.5-e",
            )
        )
    return resistencia


def _solda(
    d: Diagonal, prefixo: str, forca_kN: float, linhas: list[Verificacao], *, numero_de_cordoes: int
) -> None:
    aw = 0.707 * d.perna_solda_mm * d.comprimento_solda_mm * numero_de_cordoes
    resistencia = 0.60 * FW_E70_MPA * aw / GAMMA_W2 / 1e3
    linhas.append(
        _linha(
            f"{prefixo}: solda da diagonal na chapa de nó",
            forca_kN,
            resistencia,
            "kN",
            f"{numero_de_cordoes} cordões de {_n(d.comprimento_solda_mm, 0)} mm, perna "
            f"{_n(d.perna_solda_mm)} mm (E70): F_w,Rd = 0,60·f_w·A_w/γ_w2, A_w = 0,707·a·ℓ",
            "6.2.5",
        )
    )


def _parede_do_tubo(
    d: Diagonal,
    perfil: ss.PerfilAco,
    fy: float,
    prefixo: str,
    forca_kN: float,
    linhas: list[Verificacao],
) -> None:
    area = 4.0 * d.comprimento_solda_mm * perfil.espessura_alma_mm
    resistencia = 0.60 * fy * area / GAMMA_A1 / 1e3
    linhas.append(
        _linha(
            f"{prefixo}: cisalhamento da parede do tubo junto à solda",
            forca_kN,
            resistencia,
            "kN",
            f"0,60·f_y·A/γ_a1 com A = 4·ℓ_c·t = {_n(area, 0)} mm²",
            "6.2.5 (metal-base)",
        )
    )
