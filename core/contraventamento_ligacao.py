"""Ligação de contraventamento em canto por chapa de nó: forças pelo UFM e verificações do guia.

Junta o Método das Forças Uniformes (:mod:`core.contraventamento_ufm`) com os estados-limites da
chapa, dos parafusos, das soldas e da viga e da coluna (:mod:`core.contraventamento_chapa`) numa só
tabela de verificações, na ordem do Exemplo 5.1 do AISC Design Guide 29:

1. contraventamento–chapa: parafusos, seção de Whitmore (escoamento e flambagem) e bloco de cisalhamento;
2. forças nas interfaces (UFM) e na ligação viga–coluna;
3. chapa–viga: escoamento, interação, solda, escoamento local e enrugamento da alma;
4. chapa–coluna: escoamento, interação, solda, alma da coluna;
5. viga e coluna: cisalhamento da alma e, no caso especial 1, os momentos extras.

Escopo: chapa de nó **soldada** à viga e à coluna, em canto (ortogonal), com contraventamento
parafusado à chapa. A chapa de topo parafusada, a barra do contraventamento, o pórtico não
ortogonal, as treliças, o chevron e a base de coluna não estão aqui (Exemplos 5.9 a 5.12 do guia).
Módulo puro, em mm, kN e MPa.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from core import bolted_connection as bc
from core import contraventamento_chapa as ch
from core import contraventamento_ufm as ufm
from core.verificacao import Verificacao

REF_AISC = "AISC 360-16"
REF_DG29 = "AISC DG29"

#: Aços de chapas e perfis: ``(F_y, F_u)`` em MPa.
ACOS = {
    "ASTM A36": (250.0, 400.0),
    "ASTM A572 Gr 50": (345.0, 450.0),
    "ASTM A992": (345.0, 450.0),
    "ASTM A588": (345.0, 485.0),
}
GRAUS_DE_PARAFUSO = ("A325", "A490", "A307")


@dataclass(frozen=True)
class EntradaLigacao:
    """Todos os dados da ligação, em mm, kN e MPa (os padrões trazem um exemplo que fecha)."""

    perfil_viga: ch.PerfilDoNo
    perfil_coluna: ch.PerfilDoNo
    metodo: str = ch.METODO_LRFD
    # contraventamento
    P_tracao_kN: float = 800.0
    P_compressao_kN: float = 800.0
    theta_graus: float = 45.0
    # UFM
    caso: str = ufm.CASO_GERAL
    ajuste: str = ufm.AJUSTE_BETA
    ligacao_na_mesa_da_coluna: bool = True
    reacao_viga_kN: float = 0.0
    transferencia_kN: float = 0.0
    x_mm: float = 0.0
    y_mm: float = 0.0
    delta_Vb_kN: float = 0.0
    anular_Vb: bool = False
    # chapa de nó
    t_chapa_mm: float = 20.0
    Fy_chapa_MPa: float = 345.0
    Fu_chapa_MPa: float = 450.0
    lh_mm: float = 700.0
    corte_h_mm: float = 20.0
    lv_mm: float = 600.0
    corte_v_mm: float = 20.0
    t_chapa_de_topo_mm: float = 0.0
    # parafusos do contraventamento
    designacao_do_parafuso: str = '7/8"'
    grau_do_parafuso: str = "A325"
    rosca_no_plano: bool = False
    planos_de_corte: int = 2
    fileiras: int = 2
    por_fileira: int = 5
    passo_mm: float = 75.0
    gabarito_mm: float = 75.0
    extremidade_mm: float = 38.0
    t_barra_mm: float = 0.0
    Fu_barra_MPa: float = 0.0
    extremidade_barra_mm: float = 0.0
    # seção de Whitmore e flambagem
    comprimento_de_flambagem_mm: float = 0.0  # 0 = metade do comprimento do grupo
    K_flambagem: float = 0.50
    trecho_whitmore_na_alma_mm: float = 0.0
    # soldas
    FEXX_MPa: float = ch.ELETRODO_E70_MPA
    perna_na_viga_mm: float = 8.0
    perna_na_coluna_mm: float = 8.0
    fator_de_ductilidade: float = ch.FATOR_DE_DUCTILIDADE_DA_SOLDA
    # distorção do pórtico (opcional)
    considerar_distorcao: bool = False
    area_do_contraventamento_mm2: float = 0.0
    b_viga_mm: float = 0.0
    c_coluna_mm: float = 0.0


@dataclass(frozen=True)
class ResultadoLigacao:
    entrada: EntradaLigacao
    forcas: ufm.ResultadoUFM
    parafusos: ch.ResistenciaDoGrupo
    arranjo: ch.DisposicaoDosParafusos
    largura_de_whitmore_mm: float
    area_de_whitmore_mm2: float
    esbeltez_da_chapa: float
    bloco: ch.BlocoDeCisalhamento
    solda_viga: ch.SoldaNecessaria
    solda_coluna: ch.SoldaNecessaria | None
    distorcao: ufm.ForcasDeDistorcao | None
    alfa_real_mm: float
    beta_real_mm: float
    comprimento_da_solda_na_viga_mm: float
    comprimento_da_solda_na_coluna_mm: float
    numero_minimo_de_parafusos: float
    lh_ideal_mm: float
    verificacoes: tuple[Verificacao, ...]
    avisos: tuple[str, ...] = field(default_factory=tuple)

    @property
    def aproveitamento_maximo(self) -> float:
        valores = [
            v.aproveitamento
            for v in self.verificacoes
            if v.tipo == "resistencia"
            and v.aproveitamento is not None
            and math.isfinite(v.aproveitamento)
        ]
        return max(valores) if valores else 0.0


def _pt(valor: float, casas: int = 1) -> str:
    texto = f"{valor:.{casas}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto.replace(".", ",") or "0"


def validar_entrada(e: EntradaLigacao) -> list[str]:
    """Mensagens de dado impossível (lista vazia = pode calcular)."""
    erros: list[str] = []
    if e.metodo not in ch.METODOS:
        erros.append(f"Método desconhecido: {e.metodo!r}.")
    if (
        not (e.P_tracao_kN > 0 or e.P_compressao_kN > 0)
        or e.P_tracao_kN < 0
        or e.P_compressao_kN < 0
    ):
        erros.append(
            "Informe a força de tração e/ou de compressão do contraventamento (≥ 0, uma delas > 0)."
        )
    if not 0.0 < e.theta_graus < 90.0:
        erros.append("O ângulo θ do contraventamento com a vertical precisa estar entre 0° e 90°.")
    if e.caso not in ufm.CASOS:
        erros.append(f"Caso do UFM desconhecido: {e.caso!r}.")
    if e.ajuste not in ufm.AJUSTES:
        erros.append(f"Ajuste de α e β desconhecido: {e.ajuste!r}.")
    com_coluna = e.caso != ufm.CASO_3
    for nome, valor in (
        ("A espessura da chapa de nó", e.t_chapa_mm),
        ("O comprimento horizontal da chapa", e.lh_mm),
        ("O comprimento vertical da chapa", e.lv_mm if com_coluna else 1.0),
        ("O passo dos parafusos", e.passo_mm if e.por_fileira > 1 else 1.0),
        ("O gabarito entre fileiras", e.gabarito_mm if e.fileiras > 1 else 1.0),
        ("A extremidade dos parafusos", e.extremidade_mm),
        ("A resistência Fy da chapa", e.Fy_chapa_MPa),
        ("A resistência Fu da chapa", e.Fu_chapa_MPa),
        ("A perna da solda na viga", e.perna_na_viga_mm),
        ("A perna da solda na coluna", e.perna_na_coluna_mm if com_coluna else 1.0),
        ("O fator de ductilidade da solda", e.fator_de_ductilidade),
        ("O K de flambagem da chapa", e.K_flambagem),
    ):
        if not valor > 0:
            erros.append(f"{nome} precisa ser maior que zero.")
    if e.corte_h_mm < 0 or e.corte_v_mm < 0 or e.t_chapa_de_topo_mm < 0:
        erros.append("O corte da chapa e a espessura da chapa de topo não podem ser negativos.")
    if e.corte_h_mm >= e.lh_mm or (com_coluna and e.corte_v_mm >= e.lv_mm):
        erros.append("O corte da chapa precisa ser menor que o comprimento da chapa.")
    if e.fileiras < 1 or e.por_fileira < 1 or e.planos_de_corte not in (1, 2):
        erros.append(
            "O grupo precisa de ao menos uma fileira com um parafuso, em 1 ou 2 planos de corte."
        )
    if e.grau_do_parafuso not in GRAUS_DE_PARAFUSO:
        erros.append(f"Grau de parafuso desconhecido: {e.grau_do_parafuso!r}.")
    if e.designacao_do_parafuso not in bc.PARAFUSOS:
        erros.append(f"Parafuso desconhecido: {e.designacao_do_parafuso!r}.")
    if e.considerar_distorcao and not (
        e.area_do_contraventamento_mm2 > 0 and e.b_viga_mm > 0 and e.c_coluna_mm > 0
    ):
        erros.append(
            "Para a distorção do pórtico informe a área do contraventamento e os comprimentos b e c."
        )
    if e.caso == ufm.CASO_1 and not (e.perfil_viga.Zx_mm3 > 0 and e.perfil_coluna.Zx_mm3 > 0):
        erros.append("O caso especial 1 precisa do módulo plástico da viga e da coluna.")
    return erros


def _uso(
    nome: str, referencia: str, solicitante: float, resistente: float, unidade: str, texto: str
) -> Verificacao:
    razao = solicitante / resistente if resistente > 0 else math.inf
    return Verificacao(
        nome=nome,
        solicitante=solicitante,
        resistente=resistente,
        unidade=unidade,
        referencia=referencia,
        formula=texto,
        status="OK" if razao <= 1.0 + 1e-9 else "NÃO OK",
        aproveitamento=razao,
        tipo="resistencia",
    )


def _info(nome: str, valor: float | None, unidade: str, referencia: str, texto: str) -> Verificacao:
    return Verificacao(
        nome, None, valor, unidade, referencia, texto, status="INFO", tipo="informativo"
    )


def _limite(
    nome: str, referencia: str, atende: bool, texto: str, *, alerta: bool = False
) -> Verificacao:
    status = "OK" if atende else ("ALERTA" if alerta else "NÃO OK")
    return Verificacao(nome, None, None, "—", referencia, texto, status=status, tipo="limite")


def calcular_ligacao(e: EntradaLigacao) -> ResultadoLigacao:
    """Calcula as forças pelo UFM e fecha a tabela de verificações da ligação."""
    erros = validar_entrada(e)
    if erros:
        raise ch.ChapaInvalida(" ".join(erros))
    metodo = e.metodo
    viga, coluna = e.perfil_viga, e.perfil_coluna
    P = max(e.P_tracao_kN, e.P_compressao_kN)
    na_mesa = e.ligacao_na_mesa_da_coluna
    caso_3 = e.caso == ufm.CASO_3

    # ---- geometria real da chapa
    alfa_real = ufm.centroide_da_solda_na_viga(e.lh_mm, e.corte_h_mm, e.t_chapa_de_topo_mm)
    beta_real = 0.0 if caso_3 else ufm.centroide_da_solda_na_coluna(e.lv_mm, e.corte_v_mm)
    l_viga = e.lh_mm - e.corte_h_mm
    l_coluna = 0.0 if caso_3 else e.lv_mm - e.corte_v_mm

    # ---- forças pelo UFM
    forcas = ufm.distribuir_forcas(
        ufm.EntradaUFM(
            P_kN=P,
            theta_graus=e.theta_graus,
            eb_mm=viga.d_mm / 2.0,
            ec_mm=coluna.d_mm / 2.0 if na_mesa else 0.0,
            alfa_real_mm=alfa_real,
            beta_real_mm=beta_real,
            caso=e.caso,
            ajuste=e.ajuste,
            reacao_viga_kN=e.reacao_viga_kN,
            transferencia_kN=e.transferencia_kN,
            x_mm=e.x_mm,
            y_mm=e.y_mm,
            Zviga_mm3=viga.Zx_mm3,
            Zcoluna_mm3=coluna.Zx_mm3,
            delta_Vb_kN=e.delta_Vb_kN,
            anular_Vb=e.anular_Vb,
        )
    )
    avisos = list(forcas.avisos)
    distorcao: ufm.ForcasDeDistorcao | None = None
    axial_vc = forcas.vc_axial_kN
    if e.considerar_distorcao and not caso_3:
        distorcao = ufm.forcas_de_distorcao(
            P,
            e.area_do_contraventamento_mm2,
            viga.Ix_mm4,
            coluna.Ix_mm4,
            e.b_viga_mm,
            e.c_coluna_mm,
            forcas.beta_ideal_mm,
            forcas.alfa_ideal_mm,
            viga.d_mm / 2.0,
        )
        axial_vc = forcas.vc_axial_kN - distorcao.HD_kN  # T = H_c − H_D + A (guia p. 71)
        if not na_mesa:
            avisos.append(
                "Na ligação à alma da coluna a alma se distorce e não desenvolve forças de distorção "
                "(H_D = 0, DG29 4.2.6): desligue a distorção."
            )

    # ---- contraventamento–chapa
    arranjo = ch.DisposicaoDosParafusos(
        e.fileiras, e.por_fileira, e.passo_mm, e.gabarito_mm, e.extremidade_mm
    )
    grupo = ch.resistencia_do_grupo(
        bc.PARAFUSOS[e.designacao_do_parafuso][0],
        e.grau_do_parafuso,
        e.rosca_no_plano,
        e.planos_de_corte,
        arranjo,
        e.t_chapa_mm,
        e.Fu_chapa_MPa,
        metodo,
        designacao=e.designacao_do_parafuso,
        t_barra_mm=e.t_barra_mm,
        Fu_barra_MPa=e.Fu_barra_MPa,
        extremidade_barra_mm=e.extremidade_barra_mm,
    )
    d_furo = bc.PARAFUSOS[e.designacao_do_parafuso][1]
    lw = ch.largura_de_whitmore(arranjo)
    aw = ch.area_de_whitmore(lw, e.t_chapa_mm, e.trecho_whitmore_na_alma_mm, viga.tw_mm)
    comprimento_flamb = (
        e.comprimento_de_flambagem_mm
        if e.comprimento_de_flambagem_mm > 0
        else arranjo.comprimento_do_grupo_mm / 2.0
    )
    area_flamb = (
        aw  # a mesma área efetiva do escoamento: a mais desfavorável quando a seção entra na alma
    )
    pn_flamb, esbeltez, fcr = ch.compressao_da_chapa(
        area_flamb, e.t_chapa_mm, comprimento_flamb, e.K_flambagem, e.Fy_chapa_MPa
    )
    bloco = ch.bloco_de_cisalhamento_da_chapa(
        arranjo, e.t_chapa_mm, d_furo, e.Fy_chapa_MPa, e.Fu_chapa_MPa
    )
    n_min = ch.numero_minimo_de_parafusos(P, grupo.parafuso_interno_kN)
    unidade_p = "kN"
    base = "φ" if metodo == ch.METODO_LRFD else "R_n/Ω"

    linhas: list[Verificacao] = []
    linhas.append(
        _uso(
            "Parafusos do contraventamento (cisalhamento × contato)",
            f"{REF_AISC} J3.6 e J3.10; {REF_DG29} p. 50",
            P,
            grupo.grupo_kN,
            unidade_p,
            f"{arranjo.numero_de_parafusos} parafusos {e.designacao_do_parafuso} {e.grau_do_parafuso}: "
            f"interno {_pt(grupo.parafuso_interno_kN)} kN ({grupo.controle_interno}), extremo "
            f"{_pt(grupo.parafuso_extremo_kN)} kN ({grupo.controle_extremo}); N mín = {_pt(n_min)}",
        )
    )
    if e.P_tracao_kN > 0:
        pn_escoamento = ch.disponivel(e.Fy_chapa_MPa * aw / 1000.0, "escoamento_tracao", metodo)
        linhas.append(
            _uso(
                "Chapa de nó: escoamento da seção de Whitmore (tração)",
                f"{REF_AISC} J4.1(a); {REF_DG29} p. 51",
                e.P_tracao_kN,
                pn_escoamento,
                unidade_p,
                f"l_w = {_pt(lw)} mm; A_w = {_pt(aw)} mm²; {base}·F_y·A_w",
            )
        )
        linhas.append(
            _uso(
                "Chapa de nó: cisalhamento de bloco (tração)",
                f"{REF_AISC} J4.3 (J4-5); {REF_DG29} p. 48",
                e.P_tracao_kN,
                ch.disponivel(bloco.nominal_kN, "bloco_cisalhamento", metodo),
                unidade_p,
                f"A_gv = {_pt(bloco.Agv_mm2)}; A_nv = {_pt(bloco.Anv_mm2)}; A_nt = {_pt(bloco.Ant_mm2)} mm²; "
                f"R_n = {_pt(bloco.nominal_kN)} kN",
            )
        )
    if e.P_compressao_kN > 0:
        linhas.append(
            _uso(
                "Chapa de nó: flambagem da seção de Whitmore (compressão)",
                f"{REF_AISC} J4.4 e E3; {REF_DG29} p. 51",
                e.P_compressao_kN,
                ch.disponivel(pn_flamb, "compressao", metodo),
                unidade_p,
                f"K·L/r = {_pt(e.K_flambagem, 2)}·{_pt(comprimento_flamb)}/{_pt(e.t_chapa_mm / math.sqrt(12.0), 2)} = "
                f"{_pt(esbeltez)}; F_cr = {_pt(fcr)} MPa; A_g = {_pt(area_flamb)} mm²",
            )
        )
        if e.comprimento_de_flambagem_mm <= 0:
            avisos.append(
                "O comprimento livre da chapa na flambagem não foi informado: o programa usou metade do "
                "comprimento do grupo de parafusos. Meça no desenho (DG29 p. 51) e informe."
            )

    # ---- forças das interfaces (informativas)
    unidades_kNm = "kN·m"
    linhas.append(
        _info(
            "Forças pelo UFM: chapa–viga (cisalhante H_b; normal V_b)",
            forcas.viga_cisalhamento_kN,
            unidade_p,
            f"{REF_DG29} 4.2 (Eqs. 13-4 e 13-5 do Manual)",
            f"H_b = {_pt(forcas.viga_cisalhamento_kN)} kN; V_b = {_pt(forcas.viga_normal_kN)} kN; "
            f"M = {_pt(forcas.viga_momento_kNm, 2)} {unidades_kNm}; α̅ = {_pt(forcas.alfa_ideal_mm)} mm; r = {_pt(forcas.r_mm)} mm",
        )
    )
    if not caso_3:
        linhas.append(
            _info(
                "Forças pelo UFM: chapa–coluna (cisalhante V_c; normal H_c)",
                forcas.coluna_normal_kN,
                unidade_p,
                f"{REF_DG29} 4.2 (Eqs. 13-2 e 13-3 do Manual)",
                f"V_c = {_pt(forcas.coluna_cisalhamento_kN)} kN; H_c = {_pt(forcas.coluna_normal_kN)} kN; "
                f"M = {_pt(forcas.coluna_momento_kNm, 2)} {unidades_kNm}; β̅ = {_pt(forcas.beta_ideal_mm)} mm",
            )
        )
    texto_vc = (
        f"V = {_pt(forcas.vc_cisalhamento_kN)} kN (V_b + reação da viga); "
        f"T = {_pt(axial_vc)} kN (H_c + transferência"
        + (f" − H_D = {_pt(distorcao.HD_kN)}" if distorcao else "")
        + ")"
        + (f"; M = {_pt(forcas.vc_momento_kNm, 2)} kN·m (V_b·e_c)" if caso_3 else "")
    )
    linhas.append(
        _info(
            "Ligação viga–coluna: esforços de cálculo",
            forcas.vc_cisalhamento_kN,
            unidade_p,
            f"{REF_DG29} p. 69 e 70",
            texto_vc,
        )
    )

    # ---- chapa–viga
    h_b, v_b, m_b = forcas.viga_cisalhamento_kN, forcas.viga_normal_kN, forcas.viga_momento_kNmm
    n_equivalente = v_b + 2.0 * abs(m_b) / l_viga
    inter_b = ch.resistencia_da_interface(
        l_viga, e.t_chapa_mm, e.Fy_chapa_MPa, h_b, v_b, m_b, metodo
    )
    linhas.append(
        _uso(
            "Chapa–viga: escoamento por cisalhamento",
            f"{REF_AISC} J4.2(a); {REF_DG29} p. 56",
            abs(h_b),
            inter_b.cisalhamento_kN,
            unidade_p,
            f"{base}·0,60·F_y·t·l, l = {_pt(l_viga)} mm",
        )
    )
    linhas.append(
        _uso(
            "Chapa–viga: escoamento por tração/normal (N + 2M/l)",
            f"{REF_AISC} J4.1(a); {REF_DG29} p. 56 e 59",
            n_equivalente,
            inter_b.normal_kN,
            unidade_p,
            f"N_e = V_b + 2·M/l = {_pt(n_equivalente)} kN",
        )
    )
    linhas.append(
        _uso(
            "Chapa–viga: interação (M/M_n)² + (N/N_n)² + (V/V_n)⁴",
            f"Neal (1977); {REF_DG29} p. 56",
            inter_b.interacao,
            1.0,
            "—",
            f"M_n = {_pt(inter_b.flexao_kNmm / 1000.0, 2)} kN·m",
        )
    )
    sw_b = ch.solda_necessaria(
        v_b,
        h_b,
        m_b,
        l_viga,
        e.FEXX_MPa,
        metodo,
        min(e.t_chapa_mm, viga.tf_mm),
        e.fator_de_ductilidade,
    )
    linhas.append(
        _uso(
            "Solda chapa–viga: perna necessária × adotada",
            f"{REF_AISC} J2.4; {REF_DG29} p. 57 e 58",
            sw_b.perna_necessaria_mm,
            e.perna_na_viga_mm,
            "mm",
            f"f_pico = {_pt(sw_b.f_pico_kN_mm * 1000.0)} N/mm; f_méd = {_pt(sw_b.f_media_kN_mm * 1000.0)} N/mm; "
            f"projeto = máx(f_pico; {_pt(e.fator_de_ductilidade, 2)}·f_méd) = {_pt(sw_b.f_projeto_kN_mm * 1000.0)} N/mm; "
            f"θ = {_pt(sw_b.angulo_graus)}°; filete duplo",
        )
    )
    linhas.append(
        _limite(
            "Solda chapa–viga: perna mínima",
            f"{REF_AISC} Tabela J2.4",
            e.perna_na_viga_mm >= sw_b.perna_minima_mm - 1e-9,
            f"perna adotada {_pt(e.perna_na_viga_mm)} mm ≥ mínima {_pt(sw_b.perna_minima_mm)} mm "
            f"(parte mais fina: {_pt(min(e.t_chapa_mm, viga.tf_mm))} mm)",
        )
    )
    x_viga = max(alfa_real - e.t_chapa_de_topo_mm, 0.0)
    linhas.append(
        _uso(
            "Alma da viga: escoamento local sob a normal V_b",
            f"{REF_AISC} J10.2; {REF_DG29} p. 58",
            abs(v_b),
            ch.escoamento_local_da_alma(viga, l_viga, x_viga, metodo),
            unidade_p,
            f"força a {_pt(x_viga)} mm da ponta da viga ({'≤' if x_viga <= viga.d_mm else '>'} d = {_pt(viga.d_mm)} mm); l_b = {_pt(l_viga)} mm",
        )
    )
    linhas.append(
        _uso(
            "Alma da viga: enrugamento sob a normal V_b",
            f"{REF_AISC} J10.3; {REF_DG29} p. 59",
            abs(v_b),
            ch.enrugamento_da_alma(viga, l_viga, x_viga, metodo),
            unidade_p,
            f"l_b/d = {_pt(l_viga / viga.d_mm, 2)}; força {'≥' if x_viga >= viga.d_mm / 2 else '<'} d/2 da ponta",
        )
    )

    # ---- chapa–coluna
    solda_coluna: ch.SoldaNecessaria | None = None
    if not caso_3:
        h_c, v_c, m_c = (
            forcas.coluna_normal_kN,
            forcas.coluna_cisalhamento_kN,
            forcas.coluna_momento_kNmm,
        )
        inter_c = ch.resistencia_da_interface(
            l_coluna, e.t_chapa_mm, e.Fy_chapa_MPa, v_c, h_c, m_c, metodo
        )
        n_eq_c = abs(h_c) + 2.0 * abs(m_c) / l_coluna
        linhas.append(
            _uso(
                "Chapa–coluna: escoamento por cisalhamento",
                f"{REF_AISC} J4.2(a); {REF_DG29} p. 70",
                abs(v_c),
                inter_c.cisalhamento_kN,
                unidade_p,
                f"{base}·0,60·F_y·t·l, l = {_pt(l_coluna)} mm",
            )
        )
        linhas.append(
            _uso(
                "Chapa–coluna: escoamento por tração/normal (H_c)",
                f"{REF_AISC} J4.1(a); {REF_DG29} p. 70",
                n_eq_c,
                inter_c.normal_kN,
                unidade_p,
                f"N_e = H_c + 2·M/l = {_pt(n_eq_c)} kN",
            )
        )
        linhas.append(
            _uso(
                "Chapa–coluna: interação (M/M_n)² + (N/N_n)² + (V/V_n)⁴",
                f"Neal (1977); {REF_DG29} p. 56",
                inter_c.interacao,
                1.0,
                "—",
                "mesma expressão da interface com a viga",
            )
        )
        solda_coluna = ch.solda_necessaria(
            h_c,
            v_c,
            m_c,
            l_coluna,
            e.FEXX_MPa,
            metodo,
            min(e.t_chapa_mm, coluna.tf_mm if na_mesa else coluna.tw_mm),
            e.fator_de_ductilidade,
        )
        linhas.append(
            _uso(
                "Solda chapa–coluna: perna necessária × adotada",
                f"{REF_AISC} J2.4; {REF_DG29} p. 57 e 58",
                solda_coluna.perna_necessaria_mm,
                e.perna_na_coluna_mm,
                "mm",
                f"projeto = {_pt(solda_coluna.f_projeto_kN_mm * 1000.0)} N/mm; θ = {_pt(solda_coluna.angulo_graus)}°; filete duplo",
            )
        )
        linhas.append(
            _limite(
                "Solda chapa–coluna: perna mínima",
                f"{REF_AISC} Tabela J2.4",
                e.perna_na_coluna_mm >= solda_coluna.perna_minima_mm - 1e-9,
                f"perna adotada {_pt(e.perna_na_coluna_mm)} mm ≥ mínima {_pt(solda_coluna.perna_minima_mm)} mm",
            )
        )
        if na_mesa and h_c > 0:
            linhas.append(
                _uso(
                    "Alma da coluna: escoamento local sob a normal H_c",
                    f"{REF_AISC} J10.2",
                    abs(h_c),
                    ch.escoamento_local_da_alma(coluna, l_coluna, 10.0 * coluna.d_mm, metodo),
                    unidade_p,
                    f"l_b = {_pt(l_coluna)} mm; força longe da ponta da coluna",
                )
            )
            linhas.append(
                _uso(
                    "Alma da coluna: enrugamento sob a normal H_c",
                    f"{REF_AISC} J10.3",
                    abs(h_c),
                    ch.enrugamento_da_alma(coluna, l_coluna, 10.0 * coluna.d_mm, metodo),
                    unidade_p,
                    f"l_b/d = {_pt(l_coluna / coluna.d_mm, 2)}",
                )
            )
            linhas.append(
                _limite(
                    "Mesa da coluna: flexão local sob a normal H_c (tração)",
                    f"{REF_AISC} J10.1; {REF_DG29} p. 66 a 69",
                    False,
                    f"não verificada: H_c = {_pt(h_c)} kN atua como carga linear ao longo da mesa. A J10.1 "
                    f"({_pt(ch.flexao_local_da_mesa(coluna, metodo))} kN) vale para carga concentrada; confira por "
                    "linhas de escoamento (Manual Parte 9) ou use enrijecedores",
                    alerta=True,
                )
            )
            linhas.append(
                _uso(
                    "Alma da coluna: cisalhamento sob H_c",
                    f"{REF_AISC} J4.2(a); {REF_DG29} p. 78",
                    abs(h_c),
                    ch.cisalhamento_da_alma(coluna, metodo),
                    unidade_p,
                    f"{base}·0,60·F_y·d·t_w",
                )
            )

    # ---- viga e ligação viga–coluna
    linhas.append(
        _uso(
            "Viga: cisalhamento da alma sob V_b + reação",
            f"{REF_AISC} J4.2(a); {REF_DG29} p. 78",
            abs(forcas.vc_cisalhamento_kN),
            ch.cisalhamento_da_alma(viga, metodo),
            unidade_p,
            f"{base}·0,60·F_y·d·t_w; V = {_pt(forcas.vc_cisalhamento_kN)} kN",
        )
    )
    if e.caso == ufm.CASO_1:
        linhas.append(
            _uso(
                "Viga: momento extra η·M do caso especial 1",
                f"{REF_DG29} 4.2.2 (Eq. 4-8)",
                abs(forcas.momento_extra_viga_kNm),
                ch.momento_plastico_disponivel(viga, metodo) / 1000.0,
                "kN·m",
                f"η = {_pt(forcas.eta, 3)}; M = P·e = {_pt(forcas.M_excentrico_kNm, 2)} kN·m; η·M = "
                f"{_pt(forcas.momento_extra_viga_kNm, 2)} kN·m contra {base}·M_p",
            )
        )
        linhas.append(
            _uso(
                "Coluna: momento extra (1 − η)·M/2 do caso especial 1",
                f"{REF_DG29} 4.2.2 (Eq. 4-8)",
                abs(forcas.momento_extra_coluna_kNm),
                ch.momento_plastico_disponivel(coluna, metodo) / 1000.0,
                "kN·m",
                f"(1 − η)·M/2 = {_pt(forcas.momento_extra_coluna_kNm, 2)} kN·m contra {base}·M_p",
            )
        )
    if caso_3:
        linhas.append(
            _uso(
                "Ligação viga–coluna: momento V_b·e_c do caso especial 3",
                f"{REF_DG29} 4.2.4",
                abs(forcas.vc_momento_kNm),
                ch.momento_plastico_disponivel(viga, metodo) / 1000.0,
                "kN·m",
                f"M_bc = {_pt(forcas.vc_momento_kNm, 2)} kN·m contra {base}·M_p da viga (confira a ligação)",
            )
        )

    # ---- avisos de projeto
    lh_ideal = ufm.comprimento_horizontal_para_alfa(
        forcas.alfa_ideal_mm, e.t_chapa_de_topo_mm, e.corte_h_mm
    )
    if abs(e.lh_mm - lh_ideal) > 5.0 and e.ajuste == ufm.AJUSTE_BETA and e.caso != ufm.CASO_3:
        avisos.append(
            f"Para zerar o binário na interface chapa–viga, o comprimento horizontal da chapa seria "
            f"{_pt(lh_ideal)} mm (o informado é {_pt(e.lh_mm)} mm)."
        )
    if arranjo.numero_de_parafusos < math.ceil(n_min - 1e-9):
        avisos.append(f"O arranjo tem menos parafusos que o mínimo de {math.ceil(n_min - 1e-9)}.")
    avisos.append(
        "O desenho em escala da ligação (Whitmore, comprimento livre da chapa, folgas e distâncias "
        "mínimas dos parafusos) precisa ser conferido: o programa não vê a geometria."
    )
    return ResultadoLigacao(
        entrada=e,
        forcas=forcas,
        parafusos=grupo,
        arranjo=arranjo,
        largura_de_whitmore_mm=lw,
        area_de_whitmore_mm2=aw,
        esbeltez_da_chapa=esbeltez,
        bloco=bloco,
        solda_viga=sw_b,
        solda_coluna=solda_coluna,
        distorcao=distorcao,
        alfa_real_mm=alfa_real,
        beta_real_mm=beta_real,
        comprimento_da_solda_na_viga_mm=l_viga,
        comprimento_da_solda_na_coluna_mm=l_coluna,
        numero_minimo_de_parafusos=n_min,
        lh_ideal_mm=lh_ideal,
        verificacoes=tuple(linhas),
        avisos=tuple(avisos),
    )
