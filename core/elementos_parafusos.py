"""Parafusos e roscas sob cargas estáticas: força axial, arrancamento, torque de aperto e grupos.

A pergunta destes casos é direta: o parafuso e a rosca aguentam a força? Para a junta estrutural
com norma, chapa, furo e fadiga, o caminho é a página Projeto de parafusos. Aqui as roscas e as
classes são as mesmas de :mod:`core.bolt_design`.

* Parafuso com pré-carga: Shigley, cap. 8 (constante de rigidez C, carga de prova e separação), com
  as duas pontas da dispersão do aperto: o parafuso se confere na maior pré-carga, a separação na
  menor, e o fator de segurança vai só na carga externa (SAND2008-0371, item 3).
* Rigidez da junta: ajuste de Wileman, Choudury e Green, conferido contra o tronco de cone de
  Shigley; se os dois se afastam, o caso avisa.
* Arrancamento da rosca: áreas de cisalhamento do Machinery's Handbook (SAND2008-0371, item 8), nas
  dimensões de mínimo material das tolerâncias 6g e 6H, pelas fórmulas da ISO 965-1.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace

from core import bolt_design as bd
from core.desenho_estatica import figura_do_grupo_de_parafusos
from core.elementos_base import (
    Campo,
    Caso,
    Coluna,
    Envio,
    Figura,
    Grafico,
    Metrica,
    Resultado,
    Tabela,
    Valores,
    exigir,
    informativo,
    limite,
    recomendacao,
    recomendacao_minima,
)

GRUPO = "Parafusos e roscas"

SHIGLEY_8 = "Shigley, Elementos de Máquinas, cap. 8"
SANDIA = "Brown, Morrow, Durbin e Baca, Guideline for Bolted Joint Design, SAND2008-0371 (2008)"
MACHINERY = "Machinery's Handbook, em SAND2008-0371, item 8"
ISO_898 = "ISO 898-1, propriedades mecânicas"
ISO_965 = "ISO 965-1, tolerâncias de rosca métrica"
WILEMAN = "Wileman, Choudury e Green, ASME J. Mech. Design, 1991"

TAN_30 = math.tan(math.radians(30.0))

#: K da relação T = K·F·d (Shigley, Tabela 8-15). Sem dado da rosca, vale 0,20.
CONDICOES = {
    "Condição desconhecida (K = 0,20)": 0.20,
    "Preto, sem revestimento (K = 0,30)": 0.30,
    "Zincado (K = 0,20)": 0.20,
    "Lubrificado (K = 0,18)": 0.18,
    "Cadmiado (K = 0,16)": 0.16,
}
#: Dispersão da pré-carga pelo jeito de apertar (SAND2008-0371, Tabela 3).
APERTOS = {
    "Torquímetro, rosca sem lubrificar (±35 %)": 0.35,
    "Torquímetro, rosca cadmiada (±30 %)": 0.30,
    "Torquímetro, rosca lubrificada (±25 %)": 0.25,
    "Chave computadorizada (±15 %)": 0.15,
    "Arruela indicadora de carga (±10 %)": 0.10,
    "Medição do alongamento (±5 %)": 0.05,
}
#: Peças da junta: E (GPa) e as constantes A e B do ajuste de Wileman.
JUNTAS = {
    "Aço": (207.0, 0.78715, 0.62873),
    "Alumínio": (71.0, 0.79670, 0.63816),
    "Cobre": (119.0, 0.79568, 0.63553),
    "Ferro fundido cinzento": (100.0, 0.77871, 0.61616),
}
#: Regra prática de engrenamento, em diâmetros. Quem manda é a conta: a regra é a segunda opinião.
REGRA_DE_ENGRENAMENTO = {
    "Aço": 1.0,
    "Ferro fundido": 1.5,
    "Alumínio, latão ou bronze": 1.5,
}
SEM_PRE_CARGA = "Sem pré-carga controlada"
COM_PRE_CARGA = "Com pré-carga controlada"
ROSCAS = tuple(bd.ROSCAS_METRICAS)
CLASSES = tuple(bd.CLASSES_PARAFUSO)
ROSCAS_GROSSAS = tuple(nome for nome in bd.ROSCAS_METRICAS if "×" not in nome)


# ---------------------------------------------------------------------------
# Rosca
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DimensoesRosca:
    """Diâmetros básicos (ISO 724) e as dimensões de mínimo material em 6g/6H, em mm."""

    d: float
    passo: float
    d2: float  # flancos
    d3: float  # fundo do parafuso
    d1_interno: float  # menor diâmetro da rosca interna
    d_min: float  # maior diâmetro do parafuso, no mínimo material
    d2_min: float
    d2_interno_max: float
    d1_interno_max: float

    @property
    def diametro_de_tensao(self) -> float:
        """Média dos diâmetros de flanco e de fundo, o usado na torção do corpo roscado."""
        return (self.d2 + self.d3) / 2.0


def dimensoes_da_rosca(rosca: bd.RoscaMetrica) -> DimensoesRosca:
    """Tolerâncias pelas fórmulas da ISO 965-1, em micrômetros, com o diâmetro nominal da rosca.

    A norma usa a média geométrica da faixa de diâmetros em ``d^0,1``; com o diâmetro nominal a
    tolerância sai até 2 % maior, a favor da segurança.
    """
    d, p = rosca.diametro_mm, rosca.passo_mm
    d2 = d - 0.649519 * p
    d3 = d - 1.226869 * p
    d1_interno = d - 1.082532 * p
    afastamento_g = 15.0 + 11.0 * p
    td = 180.0 * p ** (2.0 / 3.0) - 3.15 / math.sqrt(p)
    td2 = 90.0 * p**0.4 * d**0.1
    td2_interno = 1.32 * td2
    td1_interno = 230.0 * p**0.7 if p >= 1.0 else 433.0 * p - 190.0 * p**1.22
    return DimensoesRosca(
        d=d,
        passo=p,
        d2=d2,
        d3=d3,
        d1_interno=d1_interno,
        d_min=d - (afastamento_g + td) / 1000.0,
        d2_min=d2 - (afastamento_g + td2) / 1000.0,
        d2_interno_max=d2 + td2_interno / 1000.0,
        d1_interno_max=d1_interno + td1_interno / 1000.0,
    )


def area_de_arrancamento_do_parafuso(r: DimensoesRosca) -> float:
    """Área de cisalhamento dos filetes do parafuso por milímetro engrenado (Eq. 39)."""
    return math.pi * r.d1_interno_max * (0.5 + (r.d2_min - r.d1_interno_max) * TAN_30 / r.passo)


def area_de_arrancamento_da_peca(r: DimensoesRosca) -> float:
    """Área de cisalhamento dos filetes da peça por milímetro engrenado (Eq. 40)."""
    return math.pi * r.d_min * (0.5 + (r.d_min - r.d2_interno_max) * TAN_30 / r.passo)


def engrenamento_minimo(rosca: bd.RoscaMetrica, sut_parafuso: float, sut_peca: float) -> float:
    """Engrenamento para o parafuso romper antes da rosca (SAND2008-0371, Eq. 34 e 38).

    A área de cisalhamento precisa ser o dobro da área de tração, porque a tensão de ruptura ao
    cisalhamento se toma como a metade da de tração. Com a peça mais fraca, cresce na razão J.
    """
    r = dimensoes_da_rosca(rosca)
    por_mm_parafuso = area_de_arrancamento_do_parafuso(r)
    por_mm_peca = area_de_arrancamento_da_peca(r)
    base = 2.0 * rosca.area_tracao_mm2 / por_mm_parafuso
    razao_j = por_mm_parafuso * sut_parafuso / (por_mm_peca * sut_peca)
    return base * max(1.0, razao_j)


# ---------------------------------------------------------------------------
# Rigidez da junta
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RigidezDaJunta:
    k_parafuso: float
    k_pecas: float
    k_pecas_cone: float
    c: float


def rigidez_da_junta(
    rosca: bd.RoscaMetrica,
    aperto_mm: float,
    rosca_no_aperto_mm: float,
    material: str,
    e_parafuso_mpa: float = 207_000.0,
) -> RigidezDaJunta:
    """Rigidez do parafuso (Shigley 8-17) e das peças (Wileman, conferida no tronco de cone)."""
    d = rosca.diametro_mm
    area_lisa = math.pi * d**2 / 4.0
    area_rosca = rosca.area_tracao_mm2
    liso = aperto_mm - rosca_no_aperto_mm
    k_b = (
        area_lisa
        * area_rosca
        * e_parafuso_mpa
        / (area_lisa * rosca_no_aperto_mm + area_rosca * liso)
    )
    e_gpa, a, b = JUNTAS[material]
    e_pecas = e_gpa * 1000.0
    k_m = e_pecas * d * a * math.exp(b * d / aperto_mm)
    razao = 5.0 * (0.5774 * aperto_mm + 0.5 * d) / (0.5774 * aperto_mm + 2.5 * d)
    k_cone = 0.5774 * math.pi * e_pecas * d / (2.0 * math.log(razao))
    return RigidezDaJunta(k_b, k_m, k_cone, k_b / (k_b + k_m))


def capacidade_com_pre_carga(
    prova: float, fracao: float, dispersao: float, c: float, fs: float
) -> tuple[float, str]:
    """Maior carga externa por parafuso e o que a limita: a prova ou a separação."""
    maxima = fracao * prova * (1.0 + dispersao)
    minima = fracao * prova * (1.0 - dispersao)
    pela_prova = max(0.0, prova - maxima) / (c * fs)
    pela_separacao = minima / ((1.0 - c) * fs)
    if pela_prova <= pela_separacao:
        return pela_prova, "carga de prova"
    return pela_separacao, "separação da junta"


def _rosca_e_classe(v: Valores) -> tuple[bd.RoscaMetrica, bd.ClasseParafuso]:
    rosca = bd.obter_rosca(str(v["rosca"]))
    return rosca, bd.obter_classe(str(v["classe"]), rosca.diametro_mm)


# ---------------------------------------------------------------------------
# Parafuso sob força axial
# ---------------------------------------------------------------------------


def _linhas_de_roscas(
    classe_nome: str,
    capacidade_de: dict[str, tuple[float, str]],
    carga_por_parafuso: float,
    n: int,
) -> tuple[dict[str, object], ...]:
    linhas: list[dict[str, object]] = []
    for nome, (capacidade, governa) in capacidade_de.items():
        rosca = bd.ROSCAS_METRICAS[nome]
        classe = bd.obter_classe(classe_nome, rosca.diametro_mm)
        linhas.append(
            {
                "Rosca": nome,
                "At (mm²)": rosca.area_tracao_mm2,
                "Carga de prova (kN)": classe.resistencia_prova_MPa
                * rosca.area_tracao_mm2
                / 1000.0,
                "Aguenta por parafuso (kN)": capacidade / 1000.0,
                "Aguenta o conjunto (kN)": capacidade * n / 1000.0,
                "Limitado por": governa,
                "Atende": "Sim" if capacidade >= carga_por_parafuso else "Não",
            }
        )
    return tuple(linhas)


def calcular_parafuso_axial(v: Valores) -> Resultado:
    rosca, classe = _rosca_e_classe(v)
    n = int(v["n"])
    forca = float(v["forca_kN"]) * 1000.0
    fs = float(v["fs"])
    area = rosca.area_tracao_mm2
    prova = classe.resistencia_prova_MPa * area
    ruptura = classe.ruptura_min_MPa * area
    por_parafuso = forca / n
    com_pre_carga = v["aperto"] == COM_PRE_CARGA

    capacidades: dict[str, tuple[float, str]] = {}
    verificacoes = []
    alertas: list[str] = []
    graficos: tuple[Grafico, ...] = ()
    metricas: list[Metrica] = []
    envios: list[Envio] = []

    if com_pre_carga:
        aperto = float(v["aperto_mm"])
        na_rosca = float(v["rosca_aperto_mm"])
        exigir(aperto >= 0.5 * rosca.diametro_mm, "O aperto deve ser de pelo menos meio diâmetro.")
        exigir(na_rosca <= aperto, "A rosca dentro do aperto não pode passar do próprio aperto.")
        fracao = float(v["fracao"])
        dispersao = APERTOS[str(v["metodo"])]
        k = CONDICOES[str(v["condicao"])]
        material = str(v["material_junta"])
        junta = rigidez_da_junta(rosca, aperto, na_rosca, material)
        c = junta.c
        nominal = fracao * prova
        maxima = nominal * (1.0 + dispersao)
        minima = nominal * (1.0 - dispersao)
        torque_nm = k * nominal * rosca.diametro_mm / 1000.0
        forca_no_parafuso = maxima + c * por_parafuso
        capacidade, governa = capacidade_com_pre_carga(prova, fracao, dispersao, c, fs)
        verificacoes.extend(
            [
                limite(
                    "Parafuso: maior pré-carga mais a carga",
                    (maxima + c * fs * por_parafuso) / 1000.0,
                    prova / 1000.0,
                    "kN",
                    f"F_i,max + C·FS·P = {maxima / 1000:.1f} + {c:.3f}·{fs:.2f}·"
                    f"{por_parafuso / 1000:.2f}; limite S_p·A_t",
                    f"{SHIGLEY_8}, Eq. 8-28; {ISO_898}",
                ),
                limite(
                    "Separação da junta com a menor pré-carga",
                    (1.0 - c) * fs * por_parafuso / 1000.0,
                    minima / 1000.0,
                    "kN",
                    f"(1 − C)·FS·P ≤ F_i,min = {minima / 1000:.1f} kN",
                    f"{SHIGLEY_8}, Eq. 8-30",
                ),
                informativo(
                    "Força no parafuso em serviço, na maior pré-carga",
                    forca_no_parafuso / 1000.0,
                    "kN",
                    f"F_b = F_i,max + C·P, com C = {c:.3f}",
                    SHIGLEY_8,
                ),
            ]
        )
        if abs(junta.k_pecas - junta.k_pecas_cone) > 0.20 * junta.k_pecas_cone:
            alertas.append(
                "As duas formas de estimar a rigidez das peças diferem mais de 20 %: "
                f"{junta.k_pecas / 1000:.0f} kN/mm pelo ajuste e "
                f"{junta.k_pecas_cone / 1000:.0f} kN/mm pelo cone. Para aperto muito curto ou "
                "muito longo, confira o valor de C por ensaio ou por um modelo da junta."
            )
        if rosca.diametro_mm * 1.5 > aperto:
            alertas.append(
                "Aperto curto: o parafuso alonga pouco, e uma pequena acomodação das superfícies "
                "tira boa parte da pré-carga. Prefira um aperto maior, com luva ou arruelas."
            )
        for nome in ROSCAS_GROSSAS:
            try:
                outra = bd.ROSCAS_METRICAS[nome]
                outra_classe = bd.obter_classe(str(v["classe"]), outra.diametro_mm)
                outra_junta = rigidez_da_junta(outra, aperto, na_rosca, material)
            except ValueError:
                continue
            capacidades[nome] = capacidade_com_pre_carga(
                outra_classe.resistencia_prova_MPa * outra.area_tracao_mm2,
                fracao,
                dispersao,
                outra_junta.c,
                fs,
            )
        separa = nominal / (1.0 - c)
        ate = max(1.4 * separa, 1.5 * fs * por_parafuso, 1.0)
        passos = [ate * i / 80.0 for i in range(81)]
        curvas = [
            (p / 1000.0, (nominal + c * p if p < separa else p) / 1000.0, "Força no parafuso")
            for p in passos
        ] + [
            (p / 1000.0, max(0.0, nominal - (1.0 - c) * p) / 1000.0, "Aperto nas peças")
            for p in passos
        ]
        graficos = (
            Grafico(
                "O que cada parte recebe quando a carga externa cresce",
                "Carga externa por parafuso (kN)",
                "Força (kN)",
                tuple(curvas),
            ),
        )
        metricas = [
            Metrica("Carga por parafuso", por_parafuso / 1000.0, "kN"),
            Metrica("O conjunto aguenta", capacidade * n / 1000.0, "kN", 1),
            Metrica("Pré-carga", nominal / 1000.0, "kN", 1),
            Metrica("Torque de aperto", torque_nm, "N·m", 1),
            Metrica("Rigidez C", c, "", 3),
        ]
        envios.append(
            Envio(
                "torque_aperto",
                "Detalhar o torque de aperto",
                {
                    "rosca": str(v["rosca"]),
                    "classe": str(v["classe"]),
                    "fracao": fracao,
                    "condicao": str(v["condicao"]),
                    "metodo": str(v["metodo"]),
                },
            )
        )
        forca_na_rosca = forca_no_parafuso
    else:
        c = 1.0
        capacidade = prova / fs
        governa = "carga de prova"
        verificacoes.append(
            limite(
                "Tração no parafuso",
                fs * por_parafuso / 1000.0,
                prova / 1000.0,
                "kN",
                f"FS·P ≤ S_p·A_t = {classe.resistencia_prova_MPa:.0f}·{area:.1f}",
                ISO_898,
            )
        )
        verificacoes.append(
            informativo(
                "Tensão na rosca",
                por_parafuso / area,
                "MPa",
                f"σ = P/A_t = {por_parafuso / 1000:.2f} kN/{area:.1f} mm²",
                ISO_898,
            )
        )
        for nome in ROSCAS_GROSSAS:
            outra = bd.ROSCAS_METRICAS[nome]
            try:
                outra_classe = bd.obter_classe(str(v["classe"]), outra.diametro_mm)
            except ValueError:
                continue
            capacidades[nome] = (
                outra_classe.resistencia_prova_MPa * outra.area_tracao_mm2 / fs,
                "carga de prova",
            )
        metricas = [
            Metrica("Carga por parafuso", por_parafuso / 1000.0, "kN"),
            Metrica("O conjunto aguenta", capacidade * n / 1000.0, "kN", 1),
            Metrica("Tensão na rosca", por_parafuso / area, "MPa", 0),
            Metrica("Carga de prova", prova / 1000.0, "kN", 1),
        ]
        forca_na_rosca = por_parafuso

    envios.insert(
        0,
        Envio(
            "rosca_arrancamento",
            "Conferir o arrancamento da rosca",
            {
                "rosca": str(v["rosca"]),
                "classe": str(v["classe"]),
                "forca_kN": forca_na_rosca / 1000.0,
            },
        ),
    )
    atendem = [nome for nome, (cap, _) in capacidades.items() if cap >= por_parafuso]
    if por_parafuso > capacidade:
        resumo = (
            f"A {v['rosca']} não aguenta: cada parafuso recebe {por_parafuso / 1000:.1f} kN e "
            f"o limite é {capacidade / 1000:.1f} kN."
        )
        if atendem:
            resumo += f" A menor rosca que atende é a {atendem[0]}."
    else:
        resumo = (
            f"A {v['rosca']} aguenta: cada parafuso recebe {por_parafuso / 1000:.1f} kN, e o "
            f"limite é {capacidade / 1000:.1f} kN por parafuso, dado pela {governa}."
        )

    hipoteses = [
        "Carga estática, na direção do eixo do parafuso, igual em todos os parafusos.",
        "Peças e parafuso trabalham no regime elástico.",
        "Para carga repetida ou impacto, use a Análise de fadiga ou a página Projeto de parafusos.",
    ]
    if com_pre_carga:
        hipoteses += [
            "O fator de segurança vai só na carga externa, e as duas pontas da dispersão do "
            "aperto já cobrem a incerteza da pré-carga.",
            "Rigidez das peças para arruela com 1,5 d; todas as peças do mesmo material.",
            "Rosca de porca e parafuso com a mesma resistência de catálogo: a capacidade da rosca "
            "se confere no caso Arrancamento da rosca.",
        ]
    else:
        hipoteses.append(
            "Sem pré-carga, a carga inteira passa pelo parafuso. Vale para tirante, pino roscado "
            "e barra roscada."
        )
    return Resultado(
        resumo=resumo,
        metricas=tuple(metricas),
        verificacoes=tuple(verificacoes),
        tabelas=(
            Tabela(
                "Qual rosca atende, na mesma classe",
                _linhas_de_roscas(str(v["classe"]), capacidades, por_parafuso, n),
                f"Roscas grossas, com os mesmos dados. Ruptura da rosca escolhida: "
                f"{ruptura / 1000:.1f} kN.",
            ),
        ),
        graficos=graficos,
        alertas=tuple(alertas),
        hipoteses=tuple(hipoteses),
        referencias=(SHIGLEY_8, SANDIA, ISO_898, WILEMAN),
        envios=tuple(envios),
    )


def _campos_da_rosca(padrao: str = "M12", classe: str = "8.8") -> tuple[Campo, Campo]:
    return (
        Campo(
            "rosca",
            "Rosca",
            "Rosca métrica ISO. Sem o passo escrito, é a rosca grossa. Fina: M12 × 1,5.",
            padrao,
            opcoes=ROSCAS,
            secao="Parafuso",
        ),
        Campo(
            "classe",
            "Classe de resistência",
            "Marcada na cabeça do parafuso. A 8.8 tem 800 MPa de ruptura e 80 % disso de "
            "escoamento.",
            classe,
            opcoes=CLASSES,
            secao="Parafuso",
        ),
    )


def _campo_fs(padrao: float = 1.5) -> Campo:
    return Campo(
        "fs",
        "Fator de segurança",
        "Multiplica a carga antes de comparar com o limite. Comece com 1,5 para carga bem "
        "conhecida, e com 2 ou mais quando a carga for incerta ou a falha for grave.",
        padrao,
        minimo=1.0,
        maximo=6.0,
        passo=0.1,
        secao="Cargas",
    )


_CAMPO_CONDICAO = Campo(
    "condicao",
    "Condição da rosca",
    "Acabamento e lubrificação mudam muito o quanto do torque vira força. Sem certeza, use a "
    "condição desconhecida.",
    "Condição desconhecida (K = 0,20)",
    opcoes=tuple(CONDICOES),
    secao="Aperto",
)
_CAMPO_METODO = Campo(
    "metodo",
    "Como se aperta",
    "Quanto mais direto o controle, menor a diferença entre a pré-carga pedida e a real.",
    "Torquímetro, rosca lubrificada (±25 %)",
    opcoes=tuple(APERTOS),
    secao="Aperto",
)
_CAMPO_FRACAO = Campo(
    "fracao",
    "Pré-carga como fração da carga de prova",
    "Com torquímetro, a dispersão pede de 0,55 a 0,65. Com controle direto da pré-carga, a "
    "prática é 0,75 para parafuso que será desmontado e 0,90 para união permanente.",
    0.60,
    minimo=0.05,
    maximo=1.0,
    passo=0.05,
    secao="Aperto",
)

_SO_COM_PRE_CARGA = ("aperto", (COM_PRE_CARGA,))

CAMPOS_PARAFUSO_AXIAL: tuple[Campo, ...] = (
    *_campos_da_rosca(),
    Campo(
        "n",
        "Quantidade de parafusos",
        "Parafusos que dividem a força por igual. Se a divisão não for igual, use o caso Grupo "
        "de parafusos.",
        4,
        minimo=1,
        maximo=200,
        passo=1,
        secao="Cargas",
    ),
    Campo(
        "forca_kN",
        "Força axial total",
        "Força externa que tenta abrir a junta ou puxar os parafusos, somando todos.",
        40.0,
        "kN",
        minimo=0.0,
        passo=5.0,
        secao="Cargas",
    ),
    _campo_fs(),
    Campo(
        "aperto",
        "Tipo de aperto",
        "Com pré-carga, as peças ficam prensadas e o parafuso recebe só parte da carga externa. "
        "Sem pré-carga, como num tirante, o parafuso recebe tudo.",
        COM_PRE_CARGA,
        opcoes=(COM_PRE_CARGA, SEM_PRE_CARGA),
        secao="Aperto",
    ),
    Campo(
        "aperto_mm",
        "Aperto (espessura das peças presas)",
        "Soma das espessuras entre a cabeça e a porca ou o início da rosca da peça.",
        40.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Aperto",
        quando=_SO_COM_PRE_CARGA,
    ),
    Campo(
        "rosca_aperto_mm",
        "Parte roscada dentro do aperto",
        "Comprimento de rosca que fica entre as peças. Parafuso todo roscado: igual ao aperto.",
        15.0,
        "mm",
        minimo=0.0,
        passo=1.0,
        secao="Aperto",
        quando=_SO_COM_PRE_CARGA,
    ),
    Campo(
        "material_junta",
        "Material das peças presas",
        "Peça mais macia cede mais, e o parafuso recebe uma parte maior da carga.",
        "Aço",
        opcoes=tuple(JUNTAS),
        secao="Aperto",
        quando=_SO_COM_PRE_CARGA,
    ),
    replace(_CAMPO_FRACAO, quando=_SO_COM_PRE_CARGA),
    replace(_CAMPO_METODO, quando=_SO_COM_PRE_CARGA),
    replace(_CAMPO_CONDICAO, quando=_SO_COM_PRE_CARGA),
)


# ---------------------------------------------------------------------------
# Arrancamento da rosca
# ---------------------------------------------------------------------------


def calcular_rosca(v: Valores) -> Resultado:
    rosca, classe = _rosca_e_classe(v)
    le = float(v["le_mm"])
    sut_peca = float(v["sut_MPa"])
    forca = float(v["forca_kN"]) * 1000.0
    fs = float(v["fs"])
    tipo = str(v["peca"])
    r = dimensoes_da_rosca(rosca)
    area = rosca.area_tracao_mm2
    sut = classe.ruptura_min_MPa

    a_parafuso = area_de_arrancamento_do_parafuso(r)
    a_peca = area_de_arrancamento_da_peca(r)
    arranca_parafuso = 0.5 * sut * a_parafuso * le
    arranca_peca = 0.5 * sut_peca * a_peca * le
    rompe = sut * area
    le_minimo = engrenamento_minimo(rosca, sut, sut_peca)
    le_regra = REGRA_DE_ENGRENAMENTO[tipo] * rosca.diametro_mm
    filetes = le / rosca.passo_mm

    modos = {
        "o parafuso rompe": rompe,
        "a rosca da peça arranca": arranca_peca,
        "a rosca do parafuso arranca": arranca_parafuso,
    }
    primeiro = min(modos, key=lambda nome: modos[nome])
    capacidade = modos[primeiro]

    verificacoes = [
        limite(
            "Arrancamento da rosca da peça",
            fs * forca / 1000.0,
            arranca_peca / 1000.0,
            "kN",
            f"0.5·S_u,peça·A_n = 0.5·{sut_peca:.0f}·{a_peca:.1f}·{le:.1f}",
            f"{MACHINERY}, Eq. 40",
        ),
        limite(
            "Arrancamento da rosca do parafuso",
            fs * forca / 1000.0,
            arranca_parafuso / 1000.0,
            "kN",
            f"0.5·S_u·A_s = 0.5·{sut:.0f}·{a_parafuso:.1f}·{le:.1f}",
            f"{MACHINERY}, Eq. 39",
        ),
        limite(
            "Ruptura do parafuso",
            fs * forca / 1000.0,
            rompe / 1000.0,
            "kN",
            f"S_u·A_t = {sut:.0f}·{area:.1f}",
            ISO_898,
        ),
        recomendacao_minima(
            "Engrenamento para o parafuso romper antes da rosca",
            le,
            le_minimo,
            "mm",
            "L_e,min = 2·A_t/a_s·max(1; J)",
            f"{MACHINERY}, Eq. 34 e 38",
        ),
        recomendacao_minima(
            f"Regra prática: {tipo.lower()}",
            le,
            le_regra,
            "mm",
            f"L_e ≥ {REGRA_DE_ENGRENAMENTO[tipo]:.1f}·d",
            "Prática usual de projeto",
        ),
    ]
    alertas: list[str] = []
    if le > 3.0 * rosca.diametro_mm:
        alertas.append(
            "A carga se concentra nos primeiros filetes. Engrenar mais de três diâmetros quase "
            "não aumenta a resistência real: a conta acima fica otimista."
        )
    if filetes < 3.0:
        alertas.append(
            f"Só {filetes:.1f} filetes engrenados. Com tão poucos, a conta de cisalhamento deixa "
            "de representar a rosca: engrene mais."
        )
    if arranca_peca < rompe:
        resumo_extra = (
            f"Para o parafuso romper antes de a rosca arrancar, engrene {le_minimo:.1f} mm."
        )
    else:
        resumo_extra = "O parafuso rompe antes de a rosca arrancar, que é o modo desejado."

    linhas = []
    for nome_classe in CLASSES:
        try:
            outra = bd.obter_classe(nome_classe, rosca.diametro_mm)
        except ValueError:
            continue
        minimo_mm = engrenamento_minimo(rosca, outra.ruptura_min_MPa, sut_peca)
        linhas.append(
            {
                "Classe": nome_classe,
                "Ruptura do parafuso (kN)": outra.ruptura_min_MPa * area / 1000.0,
                "Engrenamento mínimo (mm)": minimo_mm,
                "Em diâmetros": minimo_mm / rosca.diametro_mm,
            }
        )
    ate = max(1.5 * le_minimo, 1.2 * le)
    comprimentos = [ate * i / 40.0 for i in range(41)]
    curvas = (
        [(x, 0.5 * sut_peca * a_peca * x / 1000.0, "Rosca da peça") for x in comprimentos]
        + [(x, 0.5 * sut * a_parafuso * x / 1000.0, "Rosca do parafuso") for x in comprimentos]
        + [(x, rompe / 1000.0, "Ruptura do parafuso") for x in comprimentos]
    )

    return Resultado(
        resumo=(
            f"Com {le:.1f} mm engrenados, {primeiro} primeiro, com {capacidade / 1000:.1f} kN. "
            f"{resumo_extra}"
        ),
        metricas=(
            Metrica("Rosca da peça arranca com", arranca_peca / 1000.0, "kN", 1),
            Metrica("Parafuso rompe com", rompe / 1000.0, "kN", 1),
            Metrica("Engrenamento mínimo", le_minimo, "mm", 1),
            Metrica("Filetes engrenados", filetes, "", 1),
        ),
        verificacoes=tuple(verificacoes),
        tabelas=(
            Tabela(
                "Engrenamento mínimo por classe, nesta rosca e neste material",
                tuple(linhas),
                "Comprimento para o parafuso romper antes da rosca da peça.",
            ),
        ),
        graficos=(
            Grafico(
                "Resistência conforme o comprimento engrenado",
                "Comprimento engrenado (mm)",
                "Força (kN)",
                tuple(curvas),
            ),
        ),
        alertas=tuple(alertas),
        hipoteses=(
            "Ruptura ao cisalhamento tomada como a metade da ruptura à tração, a favor da "
            "segurança em aço e em ferro fundido.",
            "Dimensões de mínimo material das tolerâncias 6g no parafuso e 6H na peça.",
            "Comprimento engrenado efetivo: sem o chanfro de entrada e sem o fim da rosca, onde o "
            "filete não está completo.",
            "Peça com parede grossa em volta da rosca. Porca fina dilata e perde resistência, e "
            "esta conta não vê isso.",
            "Porca padronizada de classe igual ou maior que a do parafuso não precisa desta "
            "conta: ela já é feita para o parafuso romper antes.",
        ),
        referencias=(MACHINERY, SANDIA, ISO_965, ISO_898),
    )


CAMPOS_ROSCA: tuple[Campo, ...] = (
    *_campos_da_rosca(),
    Campo(
        "le_mm",
        "Comprimento engrenado",
        "Trecho em que os dois filetes estão completos. Tire o chanfro do furo e o fim da rosca "
        "do parafuso.",
        18.0,
        "mm",
        minimo=0.5,
        passo=1.0,
        secao="Rosca na peça",
    ),
    Campo(
        "peca",
        "Material da peça roscada",
        "Usado na regra prática de engrenamento. A conta de resistência usa o campo abaixo.",
        "Aço",
        opcoes=tuple(REGRA_DE_ENGRENAMENTO),
        secao="Rosca na peça",
    ),
    Campo(
        "sut_MPa",
        "Ruptura da peça roscada",
        "Limite de resistência à tração do material da peça. ASTM A36: 400 MPa. Alumínio 6061-T6: "
        "cerca de 290 MPa. Ferro fundido cinzento: de 150 a 300 MPa.",
        400.0,
        "MPa",
        minimo=20.0,
        passo=10.0,
        secao="Rosca na peça",
    ),
    Campo(
        "forca_kN",
        "Força no parafuso",
        "Maior força axial em um parafuso, já com a pré-carga se houver.",
        20.0,
        "kN",
        minimo=0.0,
        passo=1.0,
        secao="Cargas",
    ),
    _campo_fs(),
)


# ---------------------------------------------------------------------------
# Torque de aperto
# ---------------------------------------------------------------------------

TENHO_FORCA = "Da pré-carga para o torque"
TENHO_TORQUE = "Do torque para a pré-carga"


def calcular_torque(v: Valores) -> Resultado:
    rosca, classe = _rosca_e_classe(v)
    k = CONDICOES[str(v["condicao"])]
    dispersao = APERTOS[str(v["metodo"])]
    area = rosca.area_tracao_mm2
    d = rosca.diametro_mm
    prova = classe.resistencia_prova_MPa * area
    if v["sentido"] == TENHO_FORCA:
        pre_carga = float(v["fracao"]) * prova
        torque = k * pre_carga * d / 1000.0
    else:
        torque = float(v["torque_Nm"])
        pre_carga = torque * 1000.0 / (k * d)
    maxima = pre_carga * (1.0 + dispersao)
    minima = pre_carga * (1.0 - dispersao)

    r = dimensoes_da_rosca(rosca)
    d_s = r.diametro_de_tensao
    sigma = maxima / area
    # Na rosca passa cerca de metade do torque; a outra metade fica sob a cabeça.
    torque_na_rosca = 0.5 * torque * (1.0 + dispersao) * 1000.0
    tau = 16.0 * torque_na_rosca / (math.pi * d_s**3)
    equivalente = math.hypot(sigma, math.sqrt(3.0) * tau)
    limite_equivalente = 0.90 * classe.escoamento_min_MPa

    linhas = []
    for nome in CLASSES:
        try:
            outra = bd.obter_classe(nome, d)
        except ValueError:
            continue
        forca = float(v["fracao"]) * outra.resistencia_prova_MPa * area
        linhas.append(
            {
                "Classe": nome,
                "Carga de prova (kN)": outra.resistencia_prova_MPa * area / 1000.0,
                "Pré-carga (kN)": forca / 1000.0,
                "Torque (N·m)": k * forca * d / 1000.0,
            }
        )

    return Resultado(
        resumo=(
            f"Torque de {torque:.1f} N·m para {pre_carga / 1000:.1f} kN de pré-carga na "
            f"{v['rosca']}. A pré-carga real fica entre {minima / 1000:.1f} e "
            f"{maxima / 1000:.1f} kN."
        ),
        metricas=(
            Metrica("Torque de aperto", torque, "N·m", 1),
            Metrica("Pré-carga", pre_carga / 1000.0, "kN", 1),
            Metrica("Fração da carga de prova", pre_carga / prova * 100.0, "%", 0),
            Metrica("Tensão no aperto", equivalente, "MPa", 0),
        ),
        verificacoes=(
            limite(
                "Maior pré-carga contra a carga de prova",
                maxima / 1000.0,
                prova / 1000.0,
                "kN",
                f"F_i,max = F_i·(1 + {dispersao:.2f}); limite S_p·A_t",
                ISO_898,
            ),
            recomendacao(
                "Tensão combinada durante o aperto",
                equivalente,
                limite_equivalente,
                "MPa",
                f"√(σ² + 3τ²), σ = {sigma:.0f}, τ = {tau:.0f}; limite 0.90·S_y",
                f"{SHIGLEY_8}; prática da VDI 2230",
            ),
            informativo(
                "Fator de aperto",
                k,
                "",
                "T = K·F·d",
                f"{SHIGLEY_8}, Eq. 8-27 e Tabela 8-15",
            ),
        ),
        tabelas=(
            Tabela(
                "Torque por classe, nesta rosca",
                tuple(linhas),
                "Mesma fração da carga de prova e mesma condição de rosca.",
            ),
        ),
        hipoteses=(
            "T = K·F·d é uma média: o atrito real muda de lote para lote. Para aperto crítico, "
            "meça a pré-carga pelo alongamento.",
            "Cerca de metade do torque se perde sob a cabeça e o restante vai para a rosca, "
            "de onde sai a torção do corpo do parafuso durante o aperto.",
            "A torção do aperto se alivia depois de solta a ferramenta, e por isso entra só na "
            "conferência do aperto.",
        ),
        referencias=(SHIGLEY_8, SANDIA, ISO_898),
    )


CAMPOS_TORQUE: tuple[Campo, ...] = (
    *_campos_da_rosca(),
    Campo(
        "sentido",
        "O que você tem",
        "Escolha se quer achar o torque a partir da força ou conferir um torque que já é usado.",
        TENHO_FORCA,
        opcoes=(TENHO_FORCA, TENHO_TORQUE),
        secao="Aperto",
    ),
    _CAMPO_FRACAO,
    Campo(
        "torque_Nm",
        "Torque aplicado",
        "Torque marcado no torquímetro.",
        80.0,
        "N·m",
        minimo=0.1,
        passo=5.0,
        secao="Aperto",
        quando=("sentido", (TENHO_TORQUE,)),
    ),
    _CAMPO_CONDICAO,
    _CAMPO_METODO,
)


# ---------------------------------------------------------------------------
# Grupo de parafusos
# ---------------------------------------------------------------------------

CIRCULO = "Círculo de furação"
FILAS = "Filas e colunas"
LIVRE = "Coordenadas livres"


def coordenadas_do_grupo(v: Valores) -> list[tuple[float, float]]:
    """Posição dos parafusos em relação ao centro do grupo, em mm."""
    arranjo = v["arranjo"]
    if arranjo == CIRCULO:
        return list(bd.coordenadas_circulares(int(v["n_circulo"]), float(v["dc_mm"]) / 2.0))
    if arranjo == FILAS:
        linhas, colunas = int(v["filas"]), int(v["colunas"])
        sx, sy = float(v["sx_mm"]), float(v["sy_mm"])
        return [
            ((j - (colunas - 1) / 2.0) * sx, (i - (linhas - 1) / 2.0) * sy)
            for i in range(linhas)
            for j in range(colunas)
        ]
    pontos = [(float(p["x_mm"]), float(p["y_mm"])) for p in v["coordenadas"]]
    exigir(len(pontos) >= 1, "Informe ao menos um parafuso na tabela de coordenadas.")
    xc = sum(x for x, _ in pontos) / len(pontos)
    yc = sum(y for _, y in pontos) / len(pontos)
    return [(x - xc, y - yc) for x, y in pontos]


def forcas_no_grupo(
    pontos: Sequence[tuple[float, float]],
    n_kN: float,
    mx_kNm: float,
    my_kNm: float,
    vx_kN: float,
    vy_kN: float,
    t_kNm: float,
) -> list[tuple[float, float]]:
    """(Tração, cortante) de cada parafuso, em kN: distribuição linear a partir do centroide.

    Mx positivo traciona o lado +y e My positivo traciona o lado +x.
    """
    n = len(pontos)
    soma_x2 = sum(x * x for x, _ in pontos)
    soma_y2 = sum(y * y for _, y in pontos)
    soma_r2 = soma_x2 + soma_y2
    exigir(
        abs(mx_kNm) < 1e-12 or soma_y2 > 1e-9,
        "Com os parafusos numa linha só, sobre o eixo x, o grupo não resiste ao momento Mx.",
    )
    exigir(
        abs(my_kNm) < 1e-12 or soma_x2 > 1e-9,
        "Com os parafusos numa linha só, sobre o eixo y, o grupo não resiste ao momento My.",
    )
    exigir(
        abs(t_kNm) < 1e-12 or soma_r2 > 1e-9,
        "Um parafuso só, no centro, não resiste ao torque no plano da junta.",
    )
    forcas: list[tuple[float, float]] = []
    for x, y in pontos:
        tracao = n_kN / n
        if soma_y2 > 1e-9:
            tracao += mx_kNm * 1000.0 * y / soma_y2
        if soma_x2 > 1e-9:
            tracao += my_kNm * 1000.0 * x / soma_x2
        cortante_x = vx_kN / n
        cortante_y = vy_kN / n
        if soma_r2 > 1e-9:
            cortante_x -= t_kNm * 1000.0 * y / soma_r2
            cortante_y += t_kNm * 1000.0 * x / soma_r2
        forcas.append((tracao, math.hypot(cortante_x, cortante_y)))
    return forcas


def calcular_grupo(v: Valores) -> Resultado:
    rosca, classe = _rosca_e_classe(v)
    fs = float(v["fs"])
    pontos = coordenadas_do_grupo(v)
    forcas = forcas_no_grupo(
        pontos,
        float(v["n_kN"]),
        float(v["mx_kNm"]),
        float(v["my_kNm"]),
        float(v["vx_kN"]),
        float(v["vy_kN"]),
        float(v["t_kNm"]),
    )
    area = rosca.area_tracao_mm2
    area_corte = area if v["rosca_no_corte"] else math.pi * rosca.diametro_mm**2 / 4.0
    sp = classe.resistencia_prova_MPa

    linhas = []
    pior_indice = 0
    pior_equivalente = -1.0
    for i, ((x, y), (tracao, cortante)) in enumerate(zip(pontos, forcas, strict=True), start=1):
        sigma = max(tracao, 0.0) * 1000.0 / area
        tau = cortante * 1000.0 / area_corte
        equivalente = math.hypot(sigma, math.sqrt(3.0) * tau)
        if equivalente > pior_equivalente:
            pior_equivalente = equivalente
            pior_indice = i
        linhas.append(
            {
                "Parafuso": i,
                "x (mm)": x,
                "y (mm)": y,
                "Tração (kN)": tracao,
                "Cortante (kN)": cortante,
                "Tensão combinada (MPa)": equivalente,
            }
        )
    maior_tracao = max(0.0, max(t for t, _ in forcas))
    maior_cortante = max(c for _, c in forcas)
    prova_kN = sp * area / 1000.0
    corte_kN = 0.577 * sp * area_corte / 1000.0

    verificacoes = [
        limite(
            "Parafuso mais tracionado",
            fs * maior_tracao,
            prova_kN,
            "kN",
            f"FS·F ≤ S_p·A_t = {sp:.0f}·{area:.1f}",
            ISO_898,
        ),
        limite(
            "Parafuso mais cortado",
            fs * maior_cortante,
            corte_kN,
            "kN",
            f"FS·V ≤ 0.577·S_p·A = 0.577·{sp:.0f}·{area_corte:.1f}",
            f"{SHIGLEY_8}, von Mises",
        ),
        limite(
            "Tração e cortante juntos, no parafuso crítico",
            fs * pior_equivalente,
            sp,
            "MPa",
            f"FS·√(σ² + 3τ²), parafuso {pior_indice}",
            f"{SHIGLEY_8}, von Mises",
        ),
    ]
    alertas: list[str] = []
    if any(t < -1e-9 for t, _ in forcas):
        alertas.append(
            "Há parafusos com tração negativa: esse lado da junta está comprimido. A conta só "
            "vale se a pré-carga mantiver a junta fechada. Sem pré-carga, a linha que gira sai do "
            "centro do grupo, e o caso certo é a página Placas de base ou Projeto de parafusos."
        )
    figura = figura_do_grupo_de_parafusos(pontos, [t for t, _ in forcas], rosca.designacao)
    return Resultado(
        resumo=(
            f"Parafuso mais carregado: {maior_tracao:.2f} kN de tração e {maior_cortante:.2f} kN "
            f"de cortante, em {len(pontos)} parafusos {rosca.designacao}."
        ),
        metricas=(
            Metrica("Maior tração", maior_tracao, "kN"),
            Metrica("Maior cortante", maior_cortante, "kN"),
            Metrica("Tensão combinada", pior_equivalente, "MPa", 0),
            Metrica("Parafusos", float(len(pontos)), "", 0),
        ),
        verificacoes=tuple(verificacoes),
        tabelas=(Tabela("Força em cada parafuso", tuple(linhas)),),
        figuras=(
            Figura(
                "Grupo de parafusos",
                figura.png,
                "Parafusos numerados e a tração de cada um. Vermelho puxa, azul comprime.",
            ),
        ),
        alertas=tuple(alertas),
        hipoteses=(
            "Placa rígida: a tração varia em linha reta a partir do centroide do grupo.",
            "Vale para junta que continua fechada, o que pede pré-carga.",
            "Todos os parafusos têm a mesma rosca e a mesma área.",
            "O cortante se divide por igual entre os parafusos, e o torque cresce com a distância "
            "ao centro. Quando a junta trabalha por atrito, o cortante nem chega aos parafusos.",
        ),
        referencias=(SHIGLEY_8, ISO_898),
        envios=(
            Envio(
                "parafuso_axial",
                "Verificar o mais tracionado com pré-carga",
                {
                    "rosca": str(v["rosca"]),
                    "classe": str(v["classe"]),
                    "n": 1,
                    "forca_kN": maior_tracao,
                },
            ),
        ),
    )


_SO_CIRCULO = ("arranjo", (CIRCULO,))
_SO_FILAS = ("arranjo", (FILAS,))

CAMPOS_GRUPO: tuple[Campo, ...] = (
    *_campos_da_rosca("M16"),
    Campo(
        "rosca_no_corte",
        "Rosca no plano de corte",
        "Ligado quando a parte roscada passa pela junta entre as peças. A área de corte fica "
        "menor.",
        True,
        secao="Parafuso",
    ),
    Campo(
        "arranjo",
        "Como os parafusos estão",
        "Escolha o desenho do grupo. Em coordenadas livres, o programa acha o centro sozinho.",
        CIRCULO,
        opcoes=(CIRCULO, FILAS, LIVRE),
        secao="Posição dos parafusos",
    ),
    Campo(
        "n_circulo",
        "Quantidade no círculo",
        "Parafusos igualmente espaçados no círculo de furação.",
        8,
        minimo=1,
        maximo=72,
        passo=1,
        secao="Posição dos parafusos",
        quando=_SO_CIRCULO,
    ),
    Campo(
        "dc_mm",
        "Diâmetro do círculo de furação",
        "Diâmetro que passa pelo centro dos furos.",
        300.0,
        "mm",
        minimo=1.0,
        passo=10.0,
        secao="Posição dos parafusos",
        quando=_SO_CIRCULO,
    ),
    Campo(
        "filas",
        "Filas (na direção y)",
        "Quantidade de filas de parafusos.",
        2,
        minimo=1,
        maximo=40,
        passo=1,
        secao="Posição dos parafusos",
        quando=_SO_FILAS,
    ),
    Campo(
        "colunas",
        "Colunas (na direção x)",
        "Quantidade de parafusos em cada fila.",
        3,
        minimo=1,
        maximo=40,
        passo=1,
        secao="Posição dos parafusos",
        quando=_SO_FILAS,
    ),
    Campo(
        "sx_mm",
        "Espaçamento em x",
        "Distância entre colunas, de centro a centro.",
        100.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Posição dos parafusos",
        quando=_SO_FILAS,
    ),
    Campo(
        "sy_mm",
        "Espaçamento em y",
        "Distância entre filas, de centro a centro.",
        150.0,
        "mm",
        minimo=1.0,
        passo=5.0,
        secao="Posição dos parafusos",
        quando=_SO_FILAS,
    ),
    Campo(
        "coordenadas",
        "Coordenadas dos parafusos",
        "Uma linha para cada parafuso. A origem pode estar em qualquer lugar.",
        (
            {"x_mm": 0.0, "y_mm": 0.0},
            {"x_mm": 200.0, "y_mm": 0.0},
            {"x_mm": 200.0, "y_mm": 150.0},
            {"x_mm": 0.0, "y_mm": 150.0},
        ),
        secao="Posição dos parafusos",
        quando=("arranjo", (LIVRE,)),
        colunas=(
            Coluna("x_mm", "x", "Posição em x do centro do parafuso.", 0.0, "mm"),
            Coluna("y_mm", "y", "Posição em y do centro do parafuso.", 0.0, "mm"),
        ),
    ),
    Campo(
        "n_kN",
        "Força axial total",
        "Positiva puxa os parafusos, negativa comprime a junta.",
        80.0,
        "kN",
        passo=5.0,
        secao="Cargas",
    ),
    Campo(
        "mx_kNm",
        "Momento Mx",
        "Momento em torno do eixo x. Positivo traciona os parafusos do lado +y.",
        5.0,
        "kN·m",
        passo=1.0,
        secao="Cargas",
    ),
    Campo(
        "my_kNm",
        "Momento My",
        "Momento em torno do eixo y. Positivo traciona os parafusos do lado +x.",
        0.0,
        "kN·m",
        passo=1.0,
        secao="Cargas",
    ),
    Campo(
        "vx_kN",
        "Cortante em x",
        "Força no plano da junta, na direção x.",
        20.0,
        "kN",
        passo=5.0,
        secao="Cargas",
    ),
    Campo(
        "vy_kN",
        "Cortante em y",
        "Força no plano da junta, na direção y.",
        0.0,
        "kN",
        passo=5.0,
        secao="Cargas",
    ),
    Campo(
        "t_kNm",
        "Torque no plano da junta",
        "Momento em torno do eixo perpendicular à junta. Positivo é anti-horário.",
        0.0,
        "kN·m",
        passo=1.0,
        secao="Cargas",
    ),
    _campo_fs(),
)


CASOS: tuple[Caso, ...] = (
    Caso(
        "parafuso_axial",
        "Parafuso sob força axial",
        GRUPO,
        "O parafuso aguenta? Com ou sem pré-carga, e qual rosca atende.",
        "Informe a rosca, a classe, a força e o aperto. O programa diz quanto o conjunto aguenta, "
        "o que limita, o torque de aperto e qual a menor rosca que atende.",
        CAMPOS_PARAFUSO_AXIAL,
        calcular_parafuso_axial,
        r"F_b=F_i+C\,P,\quad C=\frac{k_b}{k_b+k_m},\quad F_b\le S_p A_t",
    ),
    Caso(
        "rosca_arrancamento",
        "Arrancamento da rosca",
        GRUPO,
        "A rosca da peça aguenta? Quanto engrenar para o parafuso romper antes.",
        "Rosca aberta em chapa, bloco ou fundido. Mostra quem cede primeiro e o comprimento "
        "engrenado mínimo para cada classe de parafuso.",
        CAMPOS_ROSCA,
        calcular_rosca,
        r"A_s=\pi D_1 L_e\left[\frac12+\frac{(d_2-D_1)\tan30^\circ}{P}\right],\quad "
        r"F=\frac{S_u}{2}\,A_s",
    ),
    Caso(
        "torque_aperto",
        "Torque de aperto",
        GRUPO,
        "Do torque para a pré-carga e da pré-carga para o torque.",
        "Quanto apertar, a faixa real da pré-carga conforme o método e a tabela por classe.",
        CAMPOS_TORQUE,
        calcular_torque,
        r"T=K\,F\,d,\quad F_{i,max}=F_i(1+\Gamma),\quad F_{i,min}=F_i(1-\Gamma)",
    ),
    Caso(
        "grupo_parafusos",
        "Grupo de parafusos",
        GRUPO,
        "Força axial, momento, cortante e torque divididos entre os parafusos.",
        "Flange, base ou placa com vários parafusos. Mostra a força em cada um e confere o mais "
        "carregado.",
        CAMPOS_GRUPO,
        calcular_grupo,
        r"F_i=\frac{N}{n}+\frac{M_x\,y_i}{\sum y^2}+\frac{M_y\,x_i}{\sum x^2},\quad "
        r"\sigma_{eq}=\sqrt{\sigma^2+3\tau^2}",
    ),
)
