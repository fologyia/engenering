"""Placas de base dos pilares do modelo: AISC Design Guide 1 com os esforços combinados da base.

Para cada pilar do quadro das fundações (:mod:`core.quadro_fundacoes`), os esforços da base de cada
caso são combinados com os fatores ELU do plano de cargas; em cada combinação a placa e os
chumbadores são verificados por :func:`core.base_plate.verificar_placa_base` (pressão de contato,
flexão da placa, tração e cisalhamento nos chumbadores e a interação) e vale a combinação de maior
utilização. O Design Guide 1 trata o momento em torno de **um** eixo: o do eixo forte do pilar
(tabela das barras); um momento relevante no eixo fraco vira aviso.

Critério Anglo AA-BR-DPST-DR-0001: espessura mínima da placa de base (8.8: 16 mm; 12,5 mm em
elementos leves), diâmetro mínimo do chumbador (8.8: 5/8") e, para o diâmetro escolhido, o furo na
placa, a arruela e o grout mínimo (8.7, Tabela de chumbadores).

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core import base_plate as bp
from core import criterio_anglo as ca
from core import esforcos_modelo as em
from core import plano_de_cargas as pc
from core import quadro_fundacoes as qf
from core import section_catalog as sc
from core.contraventamento_barras import ACOS
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    linhas_para_registro,
    numero_json,
    status_geral,
)

STATUS_PENDENTE = "PENDENTE"
DIAMETROS_MM: dict[str, float] = {
    '5/8"': 15.875,
    '3/4"': 19.05,
    '7/8"': 22.225,
    '1"': 25.4,
    '1 1/4"': 31.75,
    '1 1/2"': 38.1,
    '1 3/4"': 44.45,
    '2"': 50.8,
}
#: Aço do chumbador → F_u (MPa).
ACOS_CHUMBADOR: dict[str, float] = {
    "ASTM F1554 Gr 36 / A36": 400.0,
    "ASTM F1554 Gr 55": 517.0,
    "ASTM F1554 Gr 105": 862.0,
    "SAE 1020": 380.0,
}


@dataclass(frozen=True)
class ParametrosDaPlaca:
    """A placa padrão dos pilares (N na direção do eixo forte, paralela à alma)."""

    comprimento_mm: float = 350.0  # N
    largura_mm: float = 300.0  # B
    espessura_mm: float = 19.0
    aco: str = "ASTM A36"
    fck_MPa: float = 25.0
    razao_a2_a1: float = 1.0
    chumbadores: int = 4
    lado_tracionado: int = 2
    diametro: str = '3/4"'
    aco_chumbador: str = "ASTM F1554 Gr 36 / A36"
    distancia_mm: float | None = None  # do centro da placa à linha tracionada; vazio = N/2 − 50
    elemento_leve: bool = False  # Anglo 8.8: placa mínima de 12,5 mm em vez de 16 mm


def para_dicionario(p: ParametrosDaPlaca) -> dict[str, Any]:
    return dict(p.__dict__)


def de_dicionario(dados: Mapping[str, Any] | None) -> ParametrosDaPlaca:
    """Lê a placa gravada no projeto; valor estranho volta ao padrão campo a campo."""
    padrao = ParametrosDaPlaca()
    if not isinstance(dados, Mapping):
        return padrao
    valores: dict[str, Any] = {}
    for campo, valor_padrao in padrao.__dict__.items():
        valor = dados.get(campo, valor_padrao)
        try:
            if campo == "distancia_mm":
                valores[campo] = None if valor in (None, "", 0) else float(valor)
            elif isinstance(valor_padrao, bool):
                valores[campo] = bool(valor)
            elif isinstance(valor_padrao, int):
                valores[campo] = int(valor)
            elif isinstance(valor_padrao, float):
                valores[campo] = float(valor)
            else:
                valores[campo] = str(valor)
        except (TypeError, ValueError):
            valores[campo] = valor_padrao
    escolhas: dict[str, Mapping[str, object]] = {
        "diametro": DIAMETROS_MM,
        "aco": ACOS,
        "aco_chumbador": ACOS_CHUMBADOR,
    }
    for campo, opcoes in escolhas.items():
        if valores[campo] not in opcoes:
            valores[campo] = getattr(padrao, campo)
    return ParametrosDaPlaca(**valores)


def placa_do_modelo(dados: em.EsforcosDoModelo) -> ParametrosDaPlaca:
    return de_dicionario(dados.placa)


def validar(p: ParametrosDaPlaca) -> list[str]:
    erros = []
    if min(p.comprimento_mm, p.largura_mm, p.espessura_mm, p.fck_MPa, p.razao_a2_a1) <= 0:
        erros.append("Dimensões, espessura, f_ck e A₂/A₁ precisam ser positivos.")
    if p.chumbadores < 1 or not 1 <= p.lado_tracionado <= p.chumbadores:
        erros.append("Chumbadores: total ≥ do lado tracionado ≥ 1.")
    if p.distancia_mm is not None and p.distancia_mm >= p.comprimento_mm / 2:
        erros.append("A distância dos chumbadores tracionados precisa ser menor que N/2.")
    return erros


@dataclass(frozen=True)
class ResultadoDaPlaca:
    pilar: str
    perfil: str
    status: str
    utilizacao: float | None
    combinacao: str = ""
    n: float = 0.0  # compressão positiva
    m: float = 0.0  # eixo forte
    m_fraco: float = 0.0
    v: float = 0.0
    modo: str = ""
    espessura_requerida_mm: float | None = None
    motivo: str = ""
    linhas: tuple[Verificacao, ...] = ()


def _n(valor: float, casas: int = 1) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _g(valor: float) -> str:
    return f"{valor:g}".replace(".", ",")


def verificacoes_anglo(p: ParametrosDaPlaca) -> list[Verificacao]:
    minimo_placa = ca.ESPESSURAS_MINIMAS_MM[
        "Placas de base de elementos leves" if p.elemento_leve else "Placas de base"
    ]
    minimo_ch = ca.DIAMETROS_MINIMOS_MM["Chumbadores convencionais"]
    furo, furo_arruela, t_arruela, lado_arruela, grout = ca.CHUMBADORES[p.diametro]
    return [
        Verificacao(
            "Anglo: espessura mínima da placa de base",
            minimo_placa,
            p.espessura_mm,
            "mm",
            ca.item("8.8"),
            f"mínimo {_n(minimo_placa)} mm"
            + (" (elemento leve)" if p.elemento_leve else "")
            + f"; adotada {_n(p.espessura_mm)} mm",
            tipo="limite",
        ),
        Verificacao(
            "Anglo: diâmetro mínimo do chumbador",
            minimo_ch,
            DIAMETROS_MM[p.diametro],
            "mm",
            ca.item("8.8"),
            f'mínimo 5/8"; adotado {p.diametro}',
            tipo="limite",
        ),
        Verificacao(
            f"Anglo: furo, arruela e grout do chumbador de {p.diametro}",
            None,
            None,
            "mm",
            ca.item("8.7"),
            f"furo na placa {_g(furo)} mm; arruela quadrada {_g(lado_arruela)} mm, espessura "
            f"{_g(t_arruela)} mm, furo {_g(furo_arruela)} mm (não soldada na placa); grout mínimo "
            f"{_g(grout)} mm",
            status="INFO",
            tipo="informativo",
        ),
    ]


def momento_grande(r: bp.ResultadoPlacaBase) -> bool:
    """DG1 3.4: o contato trabalha em f_p,máx no comprimento Y por construção (não é 100 % de uso)."""
    return "3.4" in r.caso


def _linhas_da_placa(r: bp.ResultadoPlacaBase) -> list[Verificacao]:
    excentricidade = (
        "" if math.isinf(r.excentricidade_mm) else f"; e = {_n(r.excentricidade_mm)} mm"
    )
    if momento_grande(r):
        contato = Verificacao(
            "Pressão de contato no concreto",
            r.pressao_atuante_MPa,
            r.pressao_maxima_MPa,
            "MPa",
            "AISC DG1 3.4; AISC J8",
            f"momento grande: o concreto trabalha em f_p,máx num comprimento Y = "
            f"{_n(r.comprimento_contato_mm)} mm{excentricidade} e o resto vai para os chumbadores; "
            "a placa atende ao contato se Y existir",
            status="OK",
            tipo="informativo",
        )
    else:
        contato = Verificacao(
            "Pressão de contato no concreto",
            r.pressao_atuante_MPa,
            r.pressao_maxima_MPa,
            "MPa",
            "AISC DG1; AISC J8",
            f"f_p,máx = φ_c·0,85·f_ck·√(A₂/A₁); {r.caso}; comprimento de contato Y = "
            f"{_n(r.comprimento_contato_mm)} mm{excentricidade}",
        )
    linhas = [
        contato,
        Verificacao(
            "Espessura da placa (flexão)",
            r.espessura_requerida_mm,
            r.espessura_adotada_mm,
            "mm",
            "AISC DG1 3.1 a 3.4",
            f"t_req = máx(apoio {_n(r.espessura_requerida_apoio_mm)}; tração "
            f"{_n(r.espessura_requerida_tracao_mm)}) mm; m = {_n(r.m_mm)} mm, n = {_n(r.n_mm)} mm; "
            "utilização = (t_req/t)², o momento resistente cresce com t²",
            status="OK" if r.utilizacao_placa <= 1.0 + 1e-9 else "NÃO OK",
            aproveitamento=r.utilizacao_placa,
        ),
    ]
    if r.tracao_por_chumbador_N > 0:
        linhas.append(
            Verificacao(
                "Chumbador: tração",
                r.tracao_por_chumbador_N / 1e3,
                r.resistencia_tracao_chumbador_N / 1e3,
                "kN",
                "AISC J3.6",
                "φ·0,75·F_u·A_b por chumbador do lado tracionado",
            )
        )
    if r.cisalhamento_por_chumbador_N > 0:
        linhas.append(
            Verificacao(
                "Chumbador: cisalhamento",
                r.cisalhamento_por_chumbador_N / 1e3,
                r.resistencia_cisalhamento_chumbador_N / 1e3,
                "kN",
                "AISC J3.6",
                "φ·0,45·F_u·A_b (rosca no plano de corte), dividido por todos os chumbadores",
            )
        )
    if r.cisalhamento_por_chumbador_N > 0 and r.tracao_por_chumbador_N > 0:
        linhas.append(
            Verificacao(
                "Chumbador: tração + cisalhamento",
                r.utilizacao_interacao_chumbador,
                1.0,
                "—",
                "AISC J3.7",
                "interação da tração com o cisalhamento",
            )
        )
    for aviso in r.avisos:
        linhas.append(
            Verificacao(
                "Aviso do Design Guide 1",
                None,
                None,
                "—",
                "AISC DG1",
                aviso,
                status="INFO",
                tipo="informativo",
            )
        )
    return linhas


def _utilizacao(linhas: Sequence[Verificacao]) -> tuple[float, str]:
    """A maior utilização das linhas de resistência e o nome da que governa."""
    decisivas = [x for x in linhas if x.tipo == "resistencia" and x.aproveitamento is not None]
    if not decisivas:
        return 0.0, ""
    pior = max(decisivas, key=lambda x: x.aproveitamento or 0.0)
    return pior.aproveitamento or 0.0, pior.nome


def _cargas_combinadas(
    pilar: qf.PilarDoQuadro, preparo: em.PreparoDasCombinacoes
) -> list[tuple[str, float, float, float, float]]:
    """(combinação, N, M forte, M fraco, V) com os fatores ELU, compressão positiva."""
    por_caso = {c.caso: c for c in pilar.cargas}
    forte_e_m2 = pilar.eixo_forte == em.EIXO_M2
    saida = []
    for nome, fatores in zip(preparo.nomes, preparo.fatores, strict=True):
        n = v1 = v2 = m1 = m2 = 0.0
        for caso, f in zip(preparo.importados, fatores, strict=True):
            c = por_caso.get(caso)
            if c is None or f == 0:
                continue
            n += f * c.n
            v1 += f * c.v1
            v2 += f * c.v2
            m1 += f * c.m1
            m2 += f * c.m2
        forte, fraco = (m2, m1) if forte_e_m2 else (m1, m2)
        saida.append((nome, n, forte, fraco, math.hypot(v1, v2)))
    return saida


def verificar_placas(
    dados: em.EsforcosDoModelo,
    plano: pc.PlanoDeCargas,
    placa: ParametrosDaPlaca,
    *,
    anglo: bool = False,
    estados: Sequence[str] = ("ELU normal",),
) -> list[ResultadoDaPlaca]:
    from core.verificacao_barras import estados_ultimos

    quadro = qf.montar_quadro(dados)
    preparo = em.preparar_combinacoes(dados, plano, estados_ultimos(estados))
    resultados: list[ResultadoDaPlaca] = []
    for pilar in quadro.pilares:
        if pilar.base is None:
            resultados.append(
                ResultadoDaPlaca(
                    pilar.pilar, pilar.perfil, STATUS_PENDENTE, None, motivo=pilar.origem_da_base
                )
            )
            continue
        if not pilar.perfil or pilar.perfil not in sc.listar_perfis():
            resultados.append(
                ResultadoDaPlaca(
                    pilar.pilar,
                    pilar.perfil,
                    STATUS_PENDENTE,
                    None,
                    motivo="escolha o perfil do pilar na tabela das barras",
                )
            )
            continue
        if preparo is None:
            resultados.append(
                ResultadoDaPlaca(
                    pilar.pilar,
                    pilar.perfil,
                    STATUS_PENDENTE,
                    None,
                    motivo="nenhum caso do plano de cargas foi importado",
                )
            )
            continue
        perfil = sc.obter_perfil(pilar.perfil)
        combinados = _cargas_combinadas(pilar, preparo)
        pior: tuple[float, str, tuple[str, float, float, float, float], list[Verificacao]] | None
        pior = None
        erro = ""
        insuficiente: tuple[str, float, float, float, float] | None = None
        for combinado in combinados:
            nome, n, m, fraco, v = combinado
            try:
                r = bp.verificar_placa_base(
                    profundidade_coluna_mm=perfil.altura_mm,
                    largura_mesa_mm=perfil.largura_mm,
                    espessura_mesa_mm=perfil.espessura_mesa_mm,
                    comprimento_placa_mm=placa.comprimento_mm,
                    largura_placa_mm=placa.largura_mm,
                    espessura_placa_mm=placa.espessura_mm,
                    fy_placa_MPa=ACOS[placa.aco][0],
                    fck_MPa=placa.fck_MPa,
                    razao_areas_a2_a1=placa.razao_a2_a1,
                    forca_axial_N=n * 1e3,
                    momento_Nmm=m * 1e6,
                    cortante_N=v * 1e3,
                    numero_chumbadores=placa.chumbadores,
                    chumbadores_lado_tracionado=placa.lado_tracionado,
                    diametro_chumbador_mm=DIAMETROS_MM[placa.diametro],
                    fu_chumbador_MPa=ACOS_CHUMBADOR[placa.aco_chumbador],
                    distancia_chumbador_mm=placa.distancia_mm,
                )
            except ValueError as e:
                if str(e).startswith("Placa insuficiente"):
                    insuficiente = combinado
                    erro = str(e)
                    break
                erro = str(e)  # geometria (placa menor que o pilar, chumbador fora da placa)
                break
            linhas_r = _linhas_da_placa(r)
            utilizacao_r, modo_r = _utilizacao(linhas_r)
            if pior is None or utilizacao_r > pior[0]:
                pior = (utilizacao_r, modo_r, combinado, linhas_r)
        if insuficiente is not None:
            nome, n, m, fraco, v = insuficiente
            linha = Verificacao(
                "Pressão de contato no concreto",
                None,
                None,
                "—",
                "AISC DG1 3.4",
                f"{nome}: {erro}",
                status="NÃO OK",
            )
            resultados.append(
                ResultadoDaPlaca(
                    pilar.pilar,
                    pilar.perfil,
                    "NÃO OK",
                    None,
                    nome,
                    n,
                    m,
                    fraco,
                    v,
                    "placa pequena para o momento",
                    linhas=(linha, *(verificacoes_anglo(placa) if anglo else ())),
                )
            )
            continue
        if pior is None:
            resultados.append(
                ResultadoDaPlaca(
                    pilar.pilar,
                    pilar.perfil,
                    STATUS_PENDENTE,
                    None,
                    motivo=erro or "sem combinações",
                )
            )
            continue
        utilizacao, modo, (nome, n, m, fraco, v), linhas = pior
        espessura = next(
            (x.solicitante for x in linhas if x.nome == "Espessura da placa (flexão)"), None
        )
        maior_fraco = max(abs(c[3]) for c in combinados)
        maior_forte = max(abs(c[2]) for c in combinados)
        if maior_fraco > 0.5 and maior_fraco > 0.1 * maior_forte:
            linhas.append(
                Verificacao(
                    "Momento no eixo fraco do pilar",
                    None,
                    maior_fraco,
                    "kN·m",
                    "AISC DG1",
                    f"até {_n(maior_fraco, 2)} kN·m em torno do eixo fraco (o eixo forte chega a "
                    f"{_n(maior_forte, 2)} kN·m): o Design Guide 1 trata um eixo só — confira a placa "
                    "na flexão oblíqua",
                    status="ALERTA",
                    tipo="informativo",
                )
            )
        if not perfil.familia.startswith(("W", "I", "HP")):
            linhas.append(
                Verificacao(
                    "Perfil do pilar",
                    None,
                    None,
                    "—",
                    "AISC DG1",
                    f"{perfil.familia}: o Design Guide 1 foi escrito para seção I — confira",
                    status="ALERTA",
                    tipo="informativo",
                )
            )
        if anglo:
            linhas += verificacoes_anglo(placa)
        resultados.append(
            ResultadoDaPlaca(
                pilar.pilar,
                pilar.perfil,
                status_geral(linhas),
                utilizacao,
                nome,
                n,
                m,
                fraco,
                v,
                modo,
                espessura,
                linhas=tuple(linhas),
            )
        )
    return resultados


COLUNAS = (
    "Pilar",
    "Perfil",
    "Situação",
    "Utilização (%)",
    "Combinação",
    "N (kN, compressão +)",
    "M eixo forte (kN·m)",
    "V (kN)",
    "Governa",
    "Espessura necessária (mm)",
)


def linhas_da_tabela(resultados: Sequence[ResultadoDaPlaca]) -> list[list[object]]:
    return [
        [
            r.pilar,
            r.perfil or "—",
            r.status,
            "" if r.utilizacao is None else 100 * r.utilizacao,
            r.combinacao,
            "" if r.status == STATUS_PENDENTE else r.n,
            "" if r.status == STATUS_PENDENTE else r.m,
            "" if r.status == STATUS_PENDENTE else r.v,
            r.modo or r.motivo,
            "" if r.espessura_requerida_mm is None else r.espessura_requerida_mm,
        ]
        for r in resultados
    ]


def csv_das_placas(resultados: Sequence[ResultadoDaPlaca]) -> bytes:
    return pc._csv(COLUNAS, linhas_da_tabela(resultados))


def _texto_do_pilar(r: ResultadoDaPlaca) -> str:
    texto = (
        f"{r.combinacao}: N = {_n(r.n, 2)} kN; M = {_n(r.m, 2)} kN·m; V = {_n(r.v, 2)} kN; "
        f"governa: {r.modo}"
    )
    if r.espessura_requerida_mm is not None:
        texto += f"; espessura necessária {_n(r.espessura_requerida_mm)} mm"
    reprovadas = [x.nome for x in r.linhas if x.status == "NÃO OK"]
    if reprovadas:
        texto += "; não atende: " + ", ".join(reprovadas)
    return texto


def registro_das_placas(
    resultados: Sequence[ResultadoDaPlaca],
    placa: ParametrosDaPlaca,
    *,
    anglo: bool = False,
    contexto: Mapping[str, Any] | None = None,
    responsavel: str = "",
) -> dict[str, Any]:
    linhas = []
    for r in resultados:
        if r.status == STATUS_PENDENTE:
            linhas.append(Verificacao(f"{r.pilar}", None, None, "—", "—", r.motivo, status="N/A"))
        else:
            linhas.append(
                Verificacao(
                    f"{r.pilar} — placa {placa.comprimento_mm:g} × {placa.largura_mm:g} × "
                    f"{placa.espessura_mm:g} mm",
                    r.utilizacao,
                    1.0,
                    "—",
                    "AISC Design Guide 1" + ("; Anglo 8.7 e 8.8" if anglo else ""),
                    _texto_do_pilar(r),
                    status=r.status,
                    aproveitamento=r.utilizacao,
                )
            )
    geral = status_geral(linhas)
    verificadas = [r for r in resultados if r.utilizacao is not None]
    pior = max(verificadas, key=lambda r: r.utilizacao or 0.0, default=None)
    destaque = (
        f"Placa {placa.comprimento_mm:g} × {placa.largura_mm:g} × {placa.espessura_mm:g} mm "
        f"({placa.aco}) com {placa.chumbadores} chumbadores de {placa.diametro}, concreto f_ck "
        f"{placa.fck_MPa:g} MPa, em {len(resultados)} pilar(es)."
        + (
            f" Maior utilização: {_n(100 * (pior.utilizacao or 0.0))} % no {pior.pilar} "
            f"({pior.combinacao}, {pior.modo})."
            if pior is not None
            else ""
        )
    )
    entradas: dict[str, Any] = {
        "placa_N_mm": placa.comprimento_mm,
        "placa_B_mm": placa.largura_mm,
        "espessura_da_placa_mm": placa.espessura_mm,
        "aco_da_placa": placa.aco,
        "fck_MPa": placa.fck_MPa,
        "A2_A1": placa.razao_a2_a1,
        "chumbadores": placa.chumbadores,
        "chumbadores_do_lado_tracionado": placa.lado_tracionado,
        "diametro_do_chumbador": placa.diametro,
        "aco_do_chumbador": placa.aco_chumbador,
        "pilares": len(resultados),
    }
    entradas.update(dict(contexto or {}))
    return criar_registro_tecnico(
        modulo="Esforços do modelo",
        modulo_id="esforcos_modelo",
        titulo=f"Placas de base dos pilares — {len(resultados)} pilar(es)",
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=destaque,
        entradas=entradas,
        resultados={
            "status_geral": geral,
            "verificações": linhas_para_registro(linhas),
            "utilizacao_maxima": None if pior is None else numero_json(pior.utilizacao or 0.0, 4),
            "destaque_memorial": destaque,
        },
        metodo=(
            "Esforços da base de cada pilar (forças das vigas do SolidWorks) combinados com os "
            "fatores ELU do plano de cargas; placa e chumbadores pelo AISC Design Guide 1 em cada "
            "combinação, valendo a de maior utilização."
        ),
        premissas=[
            "Momento em torno do eixo forte do pilar (o Design Guide 1 trata um eixo).",
            "Ancoragem no concreto (cone, fendilhamento) e o bloco de fundação ficam à parte.",
        ],
        referencias=["AISC Design Guide 1 (2ª ed.); AISC 360-16 J3 e J8."]
        + ([f"{ca.REFERENCIA}: 8.7 e 8.8."] if anglo else []),
        conclusao=destaque,
        responsavel=responsavel,
    )
