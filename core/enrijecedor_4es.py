"""Critérios geométricos do enrijecedor de chapa de extremidade 4ES.

AISC 358-16, seção 6.8, expressões 6.8-9 e 6.8-10. Este módulo não é, por si,
o dimensionamento da ligação 4ES e não valida soldas ou pré-qualificação sísmica.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core import bolted_connection as bc
from core.verificacao import Verificacao


@dataclass(frozen=True)
class EntradaEnrijecedor:
    espessura_alma_viga: float
    fy_viga: float
    fy_enrijecedor: float
    espessura_enrijecedor: float
    altura: float
    modulo_elasticidade: float = 200000.0


def verificar(e: EntradaEnrijecedor) -> tuple[Verificacao, ...]:
    """Duas condições do enrijecedor, em mm e MPa, e alerta das partes ausentes."""
    valores = (
        e.espessura_alma_viga,
        e.fy_viga,
        e.fy_enrijecedor,
        e.espessura_enrijecedor,
        e.altura,
        e.modulo_elasticidade,
    )
    if not all(math.isfinite(v) and v > 0 for v in valores):
        raise ValueError("Todas as dimensões e propriedades devem ser finitas e positivas.")
    esp_min = e.espessura_alma_viga * e.fy_viga / e.fy_enrijecedor
    limite = 0.56 * math.sqrt(e.modulo_elasticidade / e.fy_enrijecedor)
    return (
        Verificacao(
            "Espessura do enrijecedor",
            esp_min,
            e.espessura_enrijecedor,
            "mm",
            "AISC 358-16 6.8-9",
            "t_s ≥ t_bw f_yb / f_ys",
            tipo="limite",
        ),
        Verificacao(
            "Esbeltez do enrijecedor",
            e.altura / e.espessura_enrijecedor,
            limite,
            "—",
            "AISC 358-16 6.8-10",
            "h_st/t_s ≤ 0,56 √(E/f_ys)",
            tipo="limite",
        ),
        Verificacao(
            "Verificações não incluídas",
            None,
            None,
            "—",
            "AISC 358-16 6.7.4 e 6.8",
            "Geometria completa, soldas do enrijecedor e demais estados-limites da ligação 4ES ainda não são verificados.",
            status="ALERTA",
            tipo="limite",
        ),
    )


@dataclass(frozen=True)
class Chapa4ES:
    largura: float
    gabarito: float
    distancia_externa: float
    distancia_interna: float
    borda: float
    altura_viga: float
    espessura_mesa: float
    espessura: float
    fy_chapa: float
    momento_solicitante: float


def verificar_chapa(e: Chapa4ES) -> Verificacao:
    """Plastificação da chapa pela Tabela 6.3 da AISC 358-22, com LRFD φ=0,90.

    Não verifica tração e alavanca nos parafusos, soldas, pilar nem requisitos de
    pré-qualificação. h1 é o braço da fileira externa e h2 o da fileira interna.
    """
    numeros = (
        e.largura,
        e.gabarito,
        e.distancia_externa,
        e.distancia_interna,
        e.borda,
        e.altura_viga,
        e.espessura_mesa,
        e.espessura,
        e.fy_chapa,
        e.momento_solicitante,
    )
    if not all(math.isfinite(x) and x > 0 for x in numeros):
        raise ValueError("Medidas, tensão e momento devem ser finitos e positivos.")
    if e.gabarito >= e.largura:
        raise ValueError("O gabarito deve ser menor que a largura da chapa.")
    h1 = e.altura_viga - e.espessura_mesa / 2 + e.distancia_externa
    h2 = e.altura_viga - 1.5 * e.espessura_mesa - e.distancia_interna
    if h2 <= (e.altura_viga - e.espessura_mesa) / 2 or e.espessura_mesa * 2 >= e.altura_viga:
        raise ValueError("A fileira interna ou a espessura da mesa é incompatível com a viga.")
    s = 0.5 * math.sqrt(e.largura * e.gabarito)
    pfi = min(e.distancia_interna, s)
    if e.borda <= s:
        termo_externo = 1 / e.distancia_externa + 1 / (2 * e.borda)
        extensao = e.borda
        caso = "1: d_e ≤ s"
    else:
        termo_externo = 1 / e.distancia_externa + 1 / s
        extensao = s
        caso = "2: d_e > s"
    yp = e.largura / 2 * (h2 * (1 / pfi + 1 / s) + h1 * termo_externo) + 2 / e.gabarito * (
        h2 * (pfi + s) + h1 * (extensao + e.distancia_externa)
    )
    resistencia = 0.9 * e.fy_chapa * e.espessura**2 * yp / 1e6
    return Verificacao(
        "Chapa: plastificação 4ES (LRFD)",
        e.momento_solicitante,
        resistencia,
        "kN·m",
        "AISC 358-22 Tabela 6.3; AISC 360 LRFD",
        f"φ·f_y·t_p²·Y_p, φ = 0,90; Y_p = {yp:.1f} mm; s = {s:.1f} mm; caso {caso}; p_fi limitado a s",
    )


def verificar_parafusos(
    e: Chapa4ES, diametro: str, grau: str, cortante: float, rosca_no_plano: bool = True
) -> tuple[Verificacao, ...]:
    """Tração nas duas fileiras e corte em quatro parafusos comprimidos, AISC LRFD.

    A hipótese de quatro parafusos do lado comprimido precisa ser confirmada no
    detalhamento. A chapa grossa limita alavanca; não verifica contato ou interação.
    """
    chapa = verificar_chapa(e)
    if diametro not in bc.PARAFUSOS or grau not in ("A325", "A490"):
        raise ValueError("Escolha um diâmetro conhecido e grau A325 ou A490.")
    if not math.isfinite(cortante) or cortante < 0:
        raise ValueError("O cortante deve ser finito e não negativo.")
    db = bc.dados_parafuso(diametro)["d_b"]
    ft = bc.resist_tracao_parafuso(db, grau, "AISC360_LRFD")
    fv = bc.resist_corte(db, grau, "AISC360_LRFD", rosca_no_plano, 1)
    h1 = e.altura_viga - e.espessura_mesa / 2 + e.distancia_externa
    h2 = e.altura_viga - 1.5 * e.espessura_mesa - e.distancia_interna
    momento_bolts = 2 * ft * (h1 + h2) / 1000
    return (
        Verificacao(
            "Parafusos tracionados sem alavanca (LRFD)",
            e.momento_solicitante,
            momento_bolts,
            "kN·m",
            "AISC 358-22 6.7-3; AISC 360 J3",
            "2·φF_nt·A_b·(h1+h2); válida com chapa suficientemente rígida",
        ),
        Verificacao(
            "Chapa: requisito para limitar alavanca",
            1.11 * e.momento_solicitante,
            chapa.resistente,
            "kN·m",
            "AISC 358-22 6.7-5",
            "1,11·M_solicitante ≤ φ·f_y·t_p²·Y_p; verificação para dimensionamento da chapa",
        ),
        Verificacao(
            "Corte: quatro parafusos comprimidos (LRFD)",
            cortante,
            4 * fv,
            "kN",
            "AISC 358-22 6.7-11; AISC 360 J3",
            "4·φF_nv·A_b; confirmar quatro parafusos no lado comprimido",
        ),
        Verificacao(
            "Detalhamento e contato dos parafusos",
            None,
            None,
            "—",
            "AISC 358-22 6.7-12",
            "Confirmar posição e quatro parafusos comprimidos; contato, bordas e demais estados-limites não estão verificados.",
            status="ALERTA",
            tipo="limite",
        ),
    )


def verificar_comprimento(altura: float, comprimento: float) -> Verificacao:
    """Comprimento mínimo do reforço da extremidade segundo AISC 358-22 6.6-1.

    A conferência dos trechos planos e recorte das soldas é adicional e não está incluída.
    """
    if not all(math.isfinite(x) and x > 0 for x in (altura, comprimento)):
        raise ValueError("Altura e comprimento devem ser finitos e positivos.")
    minimo = altura / math.tan(math.radians(30))
    return Verificacao(
        "Enrijecedor: comprimento mínimo",
        minimo,
        comprimento,
        "mm",
        "AISC 358-22 6.6-1",
        "L_st ≥ h_st/tan(30°); conferir trechos planos e recorte",
        tipo="limite",
    )


def verificar_pilar_sem_continuidade(entrada) -> tuple[Verificacao, ...]:
    """Reutiliza o grupo Pilar do modelo de quatro parafusos tracionados.

    Válido aqui para viga em um lado, pilar sem enrijecedores de continuidade,
    sem chapas adicionais na alma, solda de mesa de penetração total e forças na
    mesa do pilar. Não devolve linhas da chapa de extremidade 4E nem as soldas dela.
    As resistências retornadas usam os coeficientes NBR do modelo existente.
    """
    from core import ligacao_rigida as lr

    if entrada.enrijecedores or entrada.reforco_alma or entrada.outro_lado:
        raise ValueError("Este estudo cobre apenas pilar sem reforços e viga de um lado.")
    if entrada.solda_mesa != lr.PENETRACAO:
        raise ValueError("O modelo parcial pressupõe solda de penetração total na mesa da viga.")
    erros = lr.validar(entrada)
    if erros:
        raise ValueError(" ".join(erros))
    resultado = lr.calcular(entrada)
    return tuple(next(grupo.linhas for grupo in resultado.grupos if grupo.nome == "Pilar"))


def verificar_contato_chapa_simetrica(
    e: Chapa4ES, diametro: str, fu_chapa: float, cortante: float
) -> Verificacao:
    """Contato dos quatro furos comprimidos em chapa estendida simetricamente.

    Considera duas fileiras com a mesma disposição da zona tracionada; o sentido
    do cortante é tomado para a borda comprimida. Não cobre o contato no pilar.
    """
    verificar_chapa(e)
    if diametro not in bc.PARAFUSOS:
        raise ValueError("Diâmetro de parafuso desconhecido.")
    if not math.isfinite(fu_chapa) or fu_chapa <= 0 or not math.isfinite(cortante) or cortante < 0:
        raise ValueError("A resistência do aço deve ser positiva e o cortante não negativo.")
    dados = bc.dados_parafuso(diametro)
    db, dh = dados["d_b"], dados["d_h"]
    livre_exterior = e.borda - dh / 2
    livre_interior = e.distancia_externa + e.espessura_mesa + e.distancia_interna - dh
    if min(livre_exterior, livre_interior) <= 0:
        raise ValueError("Os furos comprimidos se sobrepõem ou ultrapassam a borda da chapa.")
    externo = bc.resist_contato(db, e.espessura, fu_chapa, livre_exterior, "AISC360_LRFD")
    interno = bc.resist_contato(db, e.espessura, fu_chapa, livre_interior, "AISC360_LRFD")
    return Verificacao(
        "Chapa: contato nos furos comprimidos (LRFD)",
        cortante,
        2 * (externo + interno),
        "kN",
        "AISC 358-22 6.7-12; AISC 360 J3.10",
        f"2 furos externos e 2 internos; comprimentos livres {livre_exterior:.1f} e {livre_interior:.1f} mm; chapa simétrica",
    )


def verificar_contato_pilar(
    e: Chapa4ES,
    diametro: str,
    esp_mesa: float,
    fu_pilar: float,
    borda_pilar: float,
    cortante: float,
) -> Verificacao:
    """Contato nas quatro posições comprimidas, com distância real ao extremo do pilar.

    A força de corte é considerada na direção do extremo informado. O estudo usa a
    fileira externa e a interna do lado comprimido com o mesmo passo da tração.
    """
    verificar_chapa(e)
    valores = (esp_mesa, fu_pilar, borda_pilar, cortante)
    if (
        not all(math.isfinite(x) for x in valores)
        or min(esp_mesa, fu_pilar, borda_pilar) <= 0
        or cortante < 0
    ):
        raise ValueError(
            "Informe espessura, resistência e borda positivas e cortante não negativo."
        )
    if diametro not in bc.PARAFUSOS:
        raise ValueError("Diâmetro de parafuso desconhecido.")
    dados = bc.dados_parafuso(diametro)
    db, dh = dados["d_b"], dados["d_h"]
    externo_livre = borda_pilar - dh / 2
    interno_livre = e.distancia_externa + e.espessura_mesa + e.distancia_interna - dh
    if min(externo_livre, interno_livre) <= 0:
        raise ValueError("Os furos comprimidos se sobrepõem ou ficam fora da mesa do pilar.")
    externo = bc.resist_contato(db, esp_mesa, fu_pilar, externo_livre, "AISC360_LRFD")
    interno = bc.resist_contato(db, esp_mesa, fu_pilar, interno_livre, "AISC360_LRFD")
    return Verificacao(
        "Pilar: contato nos furos comprimidos (LRFD)",
        cortante,
        2 * (externo + interno),
        "kN",
        "AISC 358-22 6.7-12; AISC 360 J3.10",
        f"2 furos externos e 2 internos; comprimentos livres {externo_livre:.1f} e {interno_livre:.1f} mm; corte em direção ao extremo informado",
    )


def verificar_soldas_viga(entrada) -> tuple[Verificacao, ...]:
    """Verifica soldas viga–chapa pelo núcleo NBR da ligação de quatro parafusos.

    Considera penetração total nas mesas e filetes dos dois lados da alma. A solda
    enrijecedor–chapa não é verificada aqui; procedimento e compatibilidade também não.
    """
    from core import ligacao_rigida as lr

    if entrada.solda_mesa != lr.PENETRACAO:
        raise ValueError("Este estudo pressupõe penetração total nas mesas da viga.")
    erros = lr.validar(entrada)
    if erros:
        raise ValueError(" ".join(erros))
    resultado = lr.calcular(entrada)
    linhas = next(
        grupo.linhas for grupo in resultado.grupos if grupo.nome == "Soldas da viga na chapa"
    )
    alerta = Verificacao(
        "Soldas do enrijecedor e procedimento",
        None,
        None,
        "—",
        "AISC 358-22 6.6.6 e 6.7",
        "Não verifica as soldas do enrijecedor, compatibilidade do consumível, detalhes de acesso ou qualificação do procedimento.",
        status="ALERTA",
        tipo="limite",
    )
    return (*linhas, alerta)
