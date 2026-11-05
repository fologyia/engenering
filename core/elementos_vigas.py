"""Vigas e flexão, do jeito simples: esquema, cargas e seção, e saem reações, momentos e flecha.

Nada de conta nova aqui: o motor é o mesmo da página Vigas e eixos (:mod:`core.beam_solver`), e a
verificação de perfil é a mesma das barras do modelo (:mod:`core.verificacao_barras`), com a norma
escolhida. O que estes casos fazem é reduzir a entrada ao que se usa todo dia e responder na hora.

Convenção da tela: carga positiva para baixo, momento positivo anti-horário e, nas reações, positivo
para cima. O motor usa positivo para cima nas cargas: a conversão fica em :func:`viga_do_caso`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from core import beam_model as bm
from core import beam_sections as bs
from core import section_catalog as sc
from core import verificacao_barras as vb
from core.beam_charts import COR_CORTANTE, COR_FLECHA, COR_MOMENTO
from core.beam_diagrams import conferir_equilibrio
from core.beam_solver import analisar_viga
from core.desenho_estatica import figura_da_viga_compacta
from core.elementos_base import (
    Campo,
    Caso,
    Coluna,
    Envio,
    Figura,
    Grafico,
    Metrica,
    Ponto,
    Resultado,
    Tabela,
    Valores,
    exigir,
    informativo,
    limite,
)
from core.steel_sections import PerfilAco, familia_do_perfil

GRUPO = "Vigas e flexão"

SHIGLEY_3 = "Shigley, Elementos de Máquinas, cap. 3 e 4"
NBR_8800_FLECHA = "ABNT NBR 8800, Anexo C, Tabela C.1"
NBR_8800 = "ABNT NBR 8800:2025, 5.4 e 5.5"
HIBBELER = "Hibbeler, Resistência dos Materiais"

CATALOGO = "Perfil do catálogo"
RETANGULAR = "Retangular"
CIRCULAR = "Circular maciça"
TUBO_CIRCULAR = "Tubo circular"
TUBO_RETANGULAR = "Tubo retangular"
INFORMAR = "Informar as propriedades"
TIPOS_DE_SECAO = (CATALOGO, RETANGULAR, CIRCULAR, TUBO_CIRCULAR, TUBO_RETANGULAR, INFORMAR)
EIXO_FORTE = "Eixo forte (x)"
EIXO_FRACO = "Eixo fraco (y)"

BIAPOIADA = "Biapoiada"
BALANCO_ESQ = "Em balanço, engastada à esquerda"
BALANCO_DIR = "Em balanço, engastada à direita"
ENGASTADA_APOIADA = "Engastada à esquerda e apoiada à direita"
BIENGASTADA = "Engastada nas duas pontas"
COM_BALANCOS = "Dois apoios, com balanços"
DOIS_VAOS = "Contínua de 2 vãos"
TRES_VAOS = "Contínua de 3 vãos"
ESQUEMAS = (
    BIAPOIADA,
    BALANCO_ESQ,
    BALANCO_DIR,
    ENGASTADA_APOIADA,
    BIENGASTADA,
    COM_BALANCOS,
    DOIS_VAOS,
    TRES_VAOS,
)

CONCENTRADA = "Concentrada"
DISTRIBUIDA = "Distribuída"
MOMENTO = "Momento"
TIPOS_DE_CARGA = (CONCENTRADA, DISTRIBUIDA, MOMENTO)

LIMITES_DE_FLECHA = (150, 180, 200, 250, 300, 350, 400, 500, 800, 1000)

_FAMILIAS_ABERTAS = frozenset({"w", "hp", "i", "u", "c", "t"})


def nomes_dos_perfis() -> tuple[str, ...]:
    return tuple(sc.listar_perfis())


# ---------------------------------------------------------------------------
# Seção escolhida
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecaoDoCaso:
    """A seção da flexão e o que a flambagem precisa: a menor inércia, em qualquer eixo."""

    viga: bs.SecaoViga
    nome: str
    i_min_mm4: float
    perfil: PerfilAco | None = None
    eixo: str = "x"

    @property
    def area_mm2(self) -> float:
        return self.viga.area_mm2

    @property
    def r_min_mm(self) -> float:
        return math.sqrt(self.i_min_mm4 / self.viga.area_mm2)

    @property
    def w_mm3(self) -> float:
        return min(
            self.viga.modulo_resistencia_superior_mm3, self.viga.modulo_resistencia_inferior_mm3
        )


def secao_do_caso(v: Valores) -> SecaoDoCaso:
    tipo = v["tipo_secao"]
    if tipo == CATALOGO:
        perfil = sc.obter_perfil(str(v["perfil"]))
        eixo = "y" if v.get("eixo") == EIXO_FRACO else "x"
        return SecaoDoCaso(
            bs.secao_de_perfil_catalogo(perfil, eixo=eixo),
            perfil.nome,
            min(perfil.ix_mm4, perfil.iy_mm4),
            perfil,
            eixo,
        )
    if tipo == INFORMAR:
        area, inercia, modulo = float(v["a_mm2"]), float(v["i_mm4"]), float(v["w_mm3"])
        c = inercia / modulo
        secao = bs.SecaoViga(
            nome="Seção informada",
            area_mm2=area,
            inercia_mm4=inercia,
            c_superior_mm=c,
            c_inferior_mm=c,
            momento_estatico_mm3=0.0,
            espessura_cisalhamento_mm=0.0,
            constante_torcao_mm4=0.0,
            modulo_torcao_mm3=0.0,
            area_cisalhamento_mm2=area,
        )
        return SecaoDoCaso(secao, "Seção informada", inercia)
    if tipo == RETANGULAR:
        b, h = float(v["b_mm"]), float(v["h_mm"])
        secao = bs.secao_retangular(b, h)
        return SecaoDoCaso(secao, f"Retangular {b:g} × {h:g} mm", min(b * h**3, h * b**3) / 12.0)
    if tipo == CIRCULAR:
        d = float(v["d_mm"])
        secao = bs.secao_circular_macica(d)
        return SecaoDoCaso(secao, f"Circular Ø{d:g} mm", secao.inercia_mm4)
    if tipo == TUBO_CIRCULAR:
        d, t = float(v["d_mm"]), float(v["t_mm"])
        exigir(2.0 * t < d, "A espessura do tubo precisa ser menor que o raio.")
        secao = bs.secao_tubo_circular(d, d - 2.0 * t)
        return SecaoDoCaso(secao, f"Tubo Ø{d:g} × {t:g} mm", secao.inercia_mm4)
    b, h, t = float(v["b_mm"]), float(v["h_mm"]), float(v["t_mm"])
    exigir(2.0 * t < min(b, h), "A espessura do tubo precisa ser menor que a metade do lado.")
    secao = bs.secao_tubo_retangular(b, h, t)
    transversal = h * b**3 / 12.0 - (h - 2.0 * t) * (b - 2.0 * t) ** 3 / 12.0
    return SecaoDoCaso(secao, f"Tubo {b:g} × {h:g} × {t:g} mm", min(secao.inercia_mm4, transversal))


def campos_de_secao(
    *, com_eixo: bool = True, perfil_padrao: str = "W 250 x 28,4"
) -> tuple[Campo, ...]:
    secao = "Seção"
    campos = [
        Campo(
            "tipo_secao",
            "Tipo de seção",
            "Escolha um perfil do catálogo ou informe as medidas. Em Informar as propriedades, "
            "use os valores de uma seção montada, por exemplo.",
            CATALOGO,
            opcoes=TIPOS_DE_SECAO,
            secao=secao,
        ),
        Campo(
            "perfil",
            "Perfil",
            "Lista do catálogo de perfis. Digite parte do nome para filtrar.",
            perfil_padrao,
            secao=secao,
            quando=("tipo_secao", (CATALOGO,)),
            opcoes_de=nomes_dos_perfis,
        ),
    ]
    if com_eixo:
        campos.append(
            Campo(
                "eixo",
                "Flexão em torno de",
                "Eixo forte: a alma do perfil fica em pé. Eixo fraco: o perfil fica deitado.",
                EIXO_FORTE,
                opcoes=(EIXO_FORTE, EIXO_FRACO),
                secao=secao,
                quando=("tipo_secao", (CATALOGO,)),
            )
        )
    campos += [
        Campo(
            "b_mm",
            "Largura b",
            "Largura da seção, na horizontal.",
            50.0,
            "mm",
            minimo=0.1,
            passo=5.0,
            secao=secao,
            quando=("tipo_secao", (RETANGULAR, TUBO_RETANGULAR)),
        ),
        Campo(
            "h_mm",
            "Altura h",
            "Altura da seção, na direção da carga.",
            100.0,
            "mm",
            minimo=0.1,
            passo=5.0,
            secao=secao,
            quando=("tipo_secao", (RETANGULAR, TUBO_RETANGULAR)),
        ),
        Campo(
            "d_mm",
            "Diâmetro externo",
            "Diâmetro externo da barra ou do tubo.",
            60.0,
            "mm",
            minimo=0.1,
            passo=5.0,
            secao=secao,
            quando=("tipo_secao", (CIRCULAR, TUBO_CIRCULAR)),
        ),
        Campo(
            "t_mm",
            "Espessura da parede",
            "Espessura da parede do tubo.",
            5.0,
            "mm",
            minimo=0.1,
            passo=0.5,
            secao=secao,
            quando=("tipo_secao", (TUBO_CIRCULAR, TUBO_RETANGULAR)),
        ),
        Campo(
            "a_mm2",
            "Área A",
            "Área da seção transversal.",
            3000.0,
            "mm²",
            minimo=0.1,
            passo=100.0,
            secao=secao,
            quando=("tipo_secao", (INFORMAR,)),
        ),
        Campo(
            "i_mm4",
            "Momento de inércia I",
            "Inércia em torno do eixo da flexão, em mm⁴. 1 cm⁴ são 10 000 mm⁴.",
            4.0e7,
            "mm⁴",
            minimo=1.0,
            passo=1.0e6,
            secao=secao,
            quando=("tipo_secao", (INFORMAR,)),
        ),
        Campo(
            "w_mm3",
            "Módulo de resistência W",
            "I dividido pela distância do centro até a fibra mais afastada, em mm³. 1 cm³ são "
            "1 000 mm³.",
            3.0e5,
            "mm³",
            minimo=1.0,
            passo=1.0e4,
            secao=secao,
            quando=("tipo_secao", (INFORMAR,)),
        ),
    ]
    return tuple(campos)


def campos_de_material(
    secao: str = "Material e limites", *, fs_padrao: float = 1.5
) -> tuple[Campo, ...]:
    return (
        Campo(
            "sy_MPa",
            "Escoamento do material",
            "Limite de escoamento. ASTM A36: 250 MPa. ASTM A572 Gr 50: 345 MPa.",
            250.0,
            "MPa",
            minimo=1.0,
            passo=10.0,
            secao=secao,
        ),
        Campo(
            "e_GPa",
            "Módulo de elasticidade E",
            "Aço: 200 GPa. Alumínio: 70 GPa. Ferro fundido: de 100 a 150 GPa.",
            200.0,
            "GPa",
            minimo=0.5,
            maximo=1000.0,
            passo=5.0,
            secao=secao,
        ),
        Campo(
            "fs",
            "Fator de segurança",
            "A tensão admissível é o escoamento dividido por este fator. Comece com 1,5.",
            fs_padrao,
            minimo=1.0,
            maximo=6.0,
            passo=0.1,
            secao=secao,
        ),
    )


# ---------------------------------------------------------------------------
# Viga: reações, momentos e flecha
# ---------------------------------------------------------------------------


def apoios_do_esquema(v: Valores, comprimento_mm: float) -> tuple[bm.Apoio, ...]:
    esquema = v["esquema"]
    a = float(v.get("a_m", 0.0)) * 1000.0
    b = float(v.get("b_m", 0.0)) * 1000.0
    if esquema == BIAPOIADA:
        return (bm.Apoio(0.0, "pino"), bm.Apoio(comprimento_mm, "rolete"))
    if esquema == BALANCO_ESQ:
        return (bm.Apoio(0.0, "engaste"),)
    if esquema == BALANCO_DIR:
        return (bm.Apoio(comprimento_mm, "engaste"),)
    if esquema == ENGASTADA_APOIADA:
        return (bm.Apoio(0.0, "engaste"), bm.Apoio(comprimento_mm, "rolete"))
    if esquema == BIENGASTADA:
        return (bm.Apoio(0.0, "engaste"), bm.Apoio(comprimento_mm, "engaste"))
    if esquema == COM_BALANCOS:
        exigir(
            0.0 <= a < b <= comprimento_mm, "Os apoios precisam estar na ordem e dentro da viga."
        )
        return (bm.Apoio(a, "pino"), bm.Apoio(b, "rolete"))
    if esquema == DOIS_VAOS:
        exigir(0.0 < a < comprimento_mm, "O apoio do meio precisa estar dentro da viga.")
        return (
            bm.Apoio(0.0, "pino"),
            bm.Apoio(a, "rolete"),
            bm.Apoio(comprimento_mm, "rolete"),
        )
    exigir(
        0.0 < a < b < comprimento_mm, "Os apoios do meio precisam estar na ordem e dentro da viga."
    )
    return (
        bm.Apoio(0.0, "pino"),
        bm.Apoio(a, "rolete"),
        bm.Apoio(b, "rolete"),
        bm.Apoio(comprimento_mm, "rolete"),
    )


def viga_do_caso(v: Valores, secao: bs.SecaoViga) -> bm.Viga:
    comprimento = float(v["l_m"]) * 1000.0
    pontuais: list[bm.CargaPontual] = []
    distribuidas: list[bm.CargaDistribuida] = []
    momentos: list[bm.MomentoConcentrado] = []
    for numero, linha in enumerate(v["cargas"], start=1):
        tipo = linha["tipo"]
        inicio = float(linha["x1_m"]) * 1000.0
        valor = float(linha["valor"])
        exigir(
            0.0 <= inicio <= comprimento,
            f"Carga da linha {numero}: a posição está fora da viga, que tem "
            f"{comprimento / 1000:g} m.",
        )
        if tipo == CONCENTRADA:
            pontuais.append(bm.CargaPontual(inicio, -valor * 1000.0))
        elif tipo == MOMENTO:
            momentos.append(bm.MomentoConcentrado(inicio, valor * 1e6))
        else:
            fim = comprimento if linha["x2_m"] is None else float(linha["x2_m"]) * 1000.0
            exigir(
                inicio < fim <= comprimento,
                f"Carga da linha {numero}: o fim precisa vir depois do início, dentro da viga.",
            )
            final = None if linha["valor2"] is None else -float(linha["valor2"])
            distribuidas.append(bm.CargaDistribuida(inicio, fim, -valor, final))
    e_mpa = float(v["e_GPa"]) * 1000.0
    return bm.Viga(
        comprimento_mm=comprimento,
        secao=secao,
        material=bm.MaterialViga(
            "Material", e_mpa, e_mpa / 2.6, float(v["sy_MPa"]), float(v["densidade_kg_m3"])
        ),
        apoios=apoios_do_esquema(v, comprimento),
        cargas_pontuais=tuple(pontuais),
        cargas_distribuidas=tuple(distribuidas),
        momentos=tuple(momentos),
        considerar_peso_proprio=bool(v["peso_proprio"]),
        nome="Viga",
    )


@dataclass(frozen=True)
class TrechoDeFlecha:
    nome: str
    referencia_mm: float
    flecha_mm: float
    x_mm: float

    @property
    def razao(self) -> float:
        return self.flecha_mm / self.referencia_mm


def flechas_por_trecho(viga: bm.Viga, pontos: tuple[bm.PontoDiagrama, ...]) -> list[TrechoDeFlecha]:
    """Flecha de cada vão e de cada balanço. No balanço, L é o dobro do comprimento (NBR 8800 C.1)."""
    posicoes = sorted({a.x_mm for a in viga.apoios})
    comprimento = viga.comprimento_mm
    trechos: list[tuple[str, float, float, float]] = []
    if posicoes[0] > 1e-6:
        trechos.append(("Balanço à esquerda", 0.0, posicoes[0], 2.0 * posicoes[0]))
    for numero, (inicio, fim) in enumerate(zip(posicoes, posicoes[1:], strict=False), start=1):
        trechos.append((f"Vão {numero}", inicio, fim, fim - inicio))
    if posicoes[-1] < comprimento - 1e-6:
        balanco = comprimento - posicoes[-1]
        trechos.append(("Balanço à direita", posicoes[-1], comprimento, 2.0 * balanco))
    resultado = []
    for nome, inicio, fim, referencia in trechos:
        dentro = [p for p in pontos if inicio - 1e-6 <= p.x_mm <= fim + 1e-6]
        maior = max(dentro, key=lambda p: abs(p.deslocamento_mm))
        resultado.append(TrechoDeFlecha(nome, referencia, abs(maior.deslocamento_mm), maior.x_mm))
    return resultado


def _serie(pontos: tuple[bm.PontoDiagrama, ...], atributo: str, escala: float, nome: str) -> Any:
    return tuple((p.x_mm / 1000.0, getattr(p, atributo) * escala, nome) for p in pontos)


def _destaques(serie: tuple[tuple[float, float, str], ...], unidade: str) -> tuple[Any, ...]:
    """O maior e o menor de cada diagrama, com o valor escrito ao lado do ponto."""
    if not serie:
        return ()
    maior = max(serie, key=lambda p: p[1])
    menor = min(serie, key=lambda p: p[1])
    saida = []
    for ponto in (maior, menor) if abs(maior[1] - menor[1]) > 1e-9 else (maior,):
        if abs(ponto[1]) > 1e-9:
            saida.append((ponto[0], ponto[1], f"{ponto[1]:.2f} {unidade}".replace(".", ",")))
    return tuple(saida)


def _perfis_que_atendem(
    secao: SecaoDoCaso,
    momento_nmm: float,
    cortante_n: float,
    admissivel: float,
    *,
    normal_n: float = 0.0,
    razao_de_flecha: float | None = None,
    limite_razao: float = 1.0,
) -> tuple[dict[str, object], ...]:
    """Perfis mais leves da família que atendem a flexão, o cortante e a flecha.

    Com EI constante, M e V não mudam com o perfil e a flecha cai com a inércia, então basta
    reescalar: não é preciso resolver a viga de novo. O peso próprio é o do perfil escolhido.
    """
    perfil = secao.perfil
    if perfil is None:
        return ()
    familia = familia_do_perfil(perfil)
    inercia_atual = secao.viga.inercia_mm4
    candidatos = sorted(
        (p for p in sc.listar_perfis().values() if familia_do_perfil(p) == familia),
        key=lambda p: p.massa_kg_m,
    )
    linhas: list[dict[str, object]] = []
    for outro in candidatos:
        try:
            sec = bs.secao_de_perfil_catalogo(outro, eixo=secao.eixo)
        except ValueError:
            continue
        modulo = min(sec.modulo_resistencia_superior_mm3, sec.modulo_resistencia_inferior_mm3)
        sigma = momento_nmm / modulo + abs(normal_n) / sec.area_mm2
        tau = cortante_n / sec.area_cisalhamento_mm2 if sec.area_cisalhamento_mm2 > 0 else 0.0
        razao = 0.0
        if razao_de_flecha is not None:
            razao = razao_de_flecha * inercia_atual / sec.inercia_mm4
        if sigma > admissivel or tau > 0.577 * admissivel or razao > limite_razao:
            continue
        linha: dict[str, object] = {
            "Perfil": outro.nome,
            "Massa (kg/m)": outro.massa_kg_m,
            "Tensão (MPa)": sigma,
        }
        if razao_de_flecha is not None:
            linha["Flecha (fração do limite)"] = razao / limite_razao
        linhas.append(linha)
        if len(linhas) == 5:
            break
    return tuple(linhas)


def calcular_viga(v: Valores) -> Resultado:
    secao = secao_do_caso(v)
    viga = viga_do_caso(v, secao.viga)
    exigir(
        bool(viga.cargas_pontuais or viga.cargas_distribuidas or viga.momentos)
        or viga.considerar_peso_proprio,
        "Informe ao menos uma carga na tabela de cargas.",
    )
    resultado = analisar_viga(viga)
    sy = float(v["sy_MPa"])
    fs = float(v["fs"])
    admissivel = sy / fs
    divisor = int(str(v["limite_flecha"]).removeprefix("L/"))

    momento = max(abs(p.momento_Nmm) for p in resultado.pontos)
    cortante = max(abs(p.cortante_N) for p in resultado.pontos)
    sigma = max(
        max(abs(p.tensao_flexao_superior_MPa), abs(p.tensao_flexao_inferior_MPa))
        for p in resultado.pontos
    )
    tau = max(abs(p.tensao_cisalhamento_MPa) for p in resultado.pontos)
    von_mises = resultado.von_mises_maximo_MPa
    flechas = flechas_por_trecho(viga, resultado.pontos)
    pior = max(flechas, key=lambda t: t.razao)
    limite_flecha = pior.referencia_mm / divisor
    balanco = "Balanço" in pior.nome
    balanco_texto = "o dobro do balanço" if balanco else "o vão"

    verificacoes = [
        limite(
            "Flexão: tensão normal máxima",
            sigma,
            admissivel,
            "MPa",
            f"σ = M/W; limite S_y/FS = {sy:.0f}/{fs:.2f}",
            SHIGLEY_3,
        ),
        limite(
            "Cortante: tensão máxima",
            tau,
            0.577 * admissivel,
            "MPa",
            "τ = V·Q/(I·t) ou V/A_v; limite 0.577·S_y/FS",
            SHIGLEY_3,
        ),
        limite(
            "Tensão combinada no ponto crítico",
            von_mises,
            admissivel,
            "MPa",
            "von Mises com a tensão normal e o cortante do mesmo ponto",
            SHIGLEY_3,
        ),
        limite(
            f"Flecha: {pior.nome.lower()}",
            pior.flecha_mm,
            limite_flecha,
            "mm",
            f"δ ≤ L/{divisor}, com L = {balanco_texto} = {pior.referencia_mm:.0f} mm",
            NBR_8800_FLECHA,
        ),
    ]
    equilibrio = conferir_equilibrio(resultado)
    verificacoes.append(
        informativo(
            "Soma das forças menos as reações",
            round(abs(equilibrio["residuo_fy_N"]) / 1000.0, 6),
            "kN",
            "Deve ser zero: confere que as reações equilibram as cargas",
            HIBBELER,
        )
    )

    letras = "ABCDEF"
    linhas_reacoes = []
    metricas: list[Metrica] = []
    for letra, reacao in zip(letras, resultado.reacoes, strict=False):
        forca = reacao.fy_N / 1000.0
        linhas_reacoes.append(
            {
                "Apoio": letra,
                "Posição (m)": reacao.x_mm / 1000.0,
                "Tipo": reacao.tipo,
                "Vertical, para cima (kN)": forca,
                "Momento (kN·m)": reacao.mz_Nmm / 1e6,
            }
        )
        if len(metricas) < 2:
            metricas.append(Metrica(f"Reação em {letra}", forca, "kN"))
    metricas += [
        Metrica("Momento máximo", momento / 1e6, "kN·m"),
        Metrica("Cortante máximo", cortante / 1000.0, "kN"),
        Metrica("Flecha máxima", pior.flecha_mm, "mm"),
        Metrica("Tensão máxima", sigma, "MPa", 1),
    ]

    pontos = resultado.pontos
    v_kn = _serie(pontos, "cortante_N", 1e-3, "Cortante")
    m_knm = _serie(pontos, "momento_Nmm", 1e-6, "Momento")
    d_mm = _serie(pontos, "deslocamento_mm", 1.0, "Flecha")
    graficos = (
        Grafico(
            "Cortante V",
            "Posição x (m)",
            "V (kN)",
            v_kn,
            area=True,
            cor=COR_CORTANTE,
            destaques=_destaques(v_kn, "kN"),
        ),
        Grafico(
            "Momento fletor M",
            "Posição x (m)",
            "M (kN·m)",
            m_knm,
            area=True,
            cor=COR_MOMENTO,
            destaques=_destaques(m_knm, "kN·m"),
        ),
        Grafico(
            "Flecha",
            "Posição x (m)",
            "δ (mm)",
            d_mm,
            area=True,
            cor=COR_FLECHA,
            destaques=_destaques(d_mm, "mm"),
        ),
    )

    tabelas = [
        Tabela("Reações nos apoios", tuple(linhas_reacoes), "Positivo para cima."),
        Tabela(
            "Flecha em cada trecho",
            tuple(
                {
                    "Trecho": t.nome,
                    "Flecha (mm)": t.flecha_mm,
                    "Posição (m)": t.x_mm / 1000.0,
                    "Limite (mm)": t.referencia_mm / divisor,
                }
                for t in flechas
            ),
            f"Limite L/{divisor}. Em balanço, L é o dobro do comprimento do balanço.",
        ),
    ]
    alternativas = _perfis_que_atendem(
        secao,
        momento,
        cortante,
        admissivel,
        razao_de_flecha=pior.razao,
        limite_razao=1.0 / divisor,
    )
    if alternativas:
        tabelas.append(
            Tabela(
                "Perfis mais leves da mesma família que atendem",
                alternativas,
                "Pela tensão, pelo cortante e pela flecha desta viga. Não inclui a flambagem "
                "lateral.",
            )
        )

    alertas = list(resultado.avisos)
    familia = familia_do_perfil(secao.perfil) if secao.perfil else ""
    if familia in _FAMILIAS_ABERTAS and secao.eixo == "x":
        alertas.append(
            "Perfil aberto fletido no eixo forte pode flambar de lado antes de escoar. A conta "
            "acima não vê isso: sem travamento lateral, confira no caso Perfil de aço."
        )
    envios: list[Envio] = []
    if secao.perfil is not None:
        envios.append(
            Envio(
                "perfil_nbr8800",
                "Verificar este perfil pela NBR 8800",
                {
                    "perfil": secao.perfil.nome,
                    "mx_kNm": momento / 1e6 if secao.eixo == "x" else 0.0,
                    "my_kNm": momento / 1e6 if secao.eixo == "y" else 0.0,
                    "v_kN": cortante / 1000.0,
                    "lb_m": float(v["l_m"]),
                    "lx_m": float(v["l_m"]),
                    "ly_m": float(v["l_m"]),
                },
            )
        )
    imagem = figura_da_viga_compacta(
        viga, [(r.x_mm, r.fy_N / 1000.0, r.mz_Nmm / 1e6) for r in resultado.reacoes]
    )
    return Resultado(
        resumo=(
            f"Momento máximo de {momento / 1e6:.2f} kN·m, cortante de {cortante / 1000:.2f} kN e "
            f"flecha de {pior.flecha_mm:.2f} mm, com {secao.nome}."
        ),
        metricas=tuple(metricas),
        verificacoes=tuple(verificacoes),
        tabelas=tuple(tabelas),
        graficos=graficos,
        figuras=(
            Figura("Esquema da viga", imagem.png, "Esquema da viga, na escala do comprimento."),
        ),
        alertas=tuple(alertas),
        hipoteses=(
            "Viga reta, de seção constante, com carga no plano da flexão e pequenas deformações.",
            "As forças são as de serviço, sem majorar: a segurança vem do fator FS. Para a norma "
            "de estruturas, use os esforços de cálculo no caso Perfil de aço.",
            "Flecha com a inércia da seção, sem a parcela do cortante.",
            "Carga positiva para baixo e momento positivo anti-horário.",
        ),
        referencias=(SHIGLEY_3, HIBBELER, NBR_8800_FLECHA),
        envios=tuple(envios),
    )


CAMPOS_VIGA: tuple[Campo, ...] = (
    Campo(
        "esquema",
        "Como a viga está apoiada",
        "Rolete deixa a viga deslizar e girar, pino só deixa girar e engaste não deixa nada. O "
        "desenho ao lado mostra o que foi escolhido.",
        BIAPOIADA,
        opcoes=ESQUEMAS,
        secao="Viga",
    ),
    Campo(
        "l_m",
        "Comprimento total",
        "Da ponta esquerda à ponta direita da viga, com os balanços.",
        6.0,
        "m",
        minimo=0.01,
        passo=0.5,
        secao="Viga",
    ),
    Campo(
        "a_m",
        "Posição do primeiro apoio",
        "Distância da ponta esquerda até o apoio. Na contínua, é o primeiro apoio interno.",
        1.0,
        "m",
        minimo=0.0,
        passo=0.25,
        secao="Viga",
        quando=("esquema", (COM_BALANCOS, DOIS_VAOS, TRES_VAOS)),
    ),
    Campo(
        "b_m",
        "Posição do segundo apoio",
        "Distância da ponta esquerda até o apoio. Na contínua de 3 vãos, é o segundo apoio "
        "interno.",
        5.0,
        "m",
        minimo=0.0,
        passo=0.25,
        secao="Viga",
        quando=("esquema", (COM_BALANCOS, TRES_VAOS)),
    ),
    Campo(
        "cargas",
        "Cargas",
        "Uma linha por carga, positiva para baixo, em kN, em kN/m na distribuída e em kN·m no "
        "momento, que é positivo anti-horário. Na distribuída, fim vazio vai até a ponta da viga "
        "e valor final vazio é carga uniforme.",
        (
            {"tipo": DISTRIBUIDA, "x1_m": 0.0, "x2_m": None, "valor": 5.0, "valor2": None},
            {"tipo": CONCENTRADA, "x1_m": 3.0, "x2_m": None, "valor": 10.0, "valor2": None},
        ),
        secao="Cargas",
        colunas=(
            Coluna(
                "tipo",
                "Tipo",
                "Força concentrada, carga distribuída ou momento.",
                CONCENTRADA,
                opcoes=TIPOS_DE_CARGA,
            ),
            Coluna(
                "x1_m",
                "Início",
                "Posição da carga, medida da ponta esquerda.",
                0.0,
                "m",
                minimo=0.0,
            ),
            Coluna(
                "x2_m",
                "Fim",
                "Só para distribuída. Vazio vai até a ponta da viga.",
                None,
                "m",
                minimo=0.0,
                opcional=True,
            ),
            Coluna(
                "valor",
                "Valor",
                "Em kN na concentrada, em kN/m na distribuída e em kN·m no momento.",
                10.0,
            ),
            Coluna(
                "valor2",
                "Valor final",
                "Só para distribuída que varia. Vazio é uniforme.",
                None,
                opcional=True,
            ),
        ),
    ),
    Campo(
        "peso_proprio",
        "Somar o peso próprio",
        "Acrescenta o peso da seção como carga distribuída ao longo da viga.",
        False,
        secao="Cargas",
    ),
    Campo(
        "densidade_kg_m3",
        "Densidade do material",
        "Aço: 7 850 kg/m³. Alumínio: 2 700 kg/m³.",
        7850.0,
        "kg/m³",
        minimo=1.0,
        passo=50.0,
        secao="Cargas",
        quando=("peso_proprio", (True,)),
    ),
    *campos_de_secao(),
    *campos_de_material(),
    Campo(
        "limite_flecha",
        "Limite de flecha",
        "L/350 é o usual em viga de piso, L/250 em viga de cobertura e L/500 sobre pilares. Em "
        "máquina, costuma ser bem mais rígido.",
        "L/350",
        opcoes=tuple(f"L/{divisor}" for divisor in LIMITES_DE_FLECHA),
        secao="Material e limites",
    ),
)


# ---------------------------------------------------------------------------
# Flexão de uma seção
# ---------------------------------------------------------------------------


def calcular_flexao(v: Valores) -> Resultado:
    secao = secao_do_caso(v)
    momento = float(v["m_kNm"]) * 1e6
    normal = float(v["n_kN"]) * 1000.0
    cortante = abs(float(v["v_kN"])) * 1000.0
    sy = float(v["sy_MPa"])
    fs = float(v["fs"])
    viga = secao.viga
    area = viga.area_mm2
    admissivel = sy / fs
    media = normal / area
    # Momento positivo traciona a fibra de baixo, como na viga biapoiada.
    sigma_sup = media - momento / viga.modulo_resistencia_superior_mm3
    sigma_inf = media + momento / viga.modulo_resistencia_inferior_mm3
    if viga.momento_estatico_mm3 > 0 and viga.espessura_cisalhamento_mm > 0:
        tau = (
            cortante
            * viga.momento_estatico_mm3
            / (viga.inercia_mm4 * viga.espessura_cisalhamento_mm)
        )
        formula_tau = "τ = V·Q/(I·t)"
    else:
        tau = cortante / viga.area_cisalhamento_mm2
        formula_tau = "τ = V/A_v"
    maior = max(abs(sigma_sup), abs(sigma_inf))
    exigir(abs(media) < admissivel, "Só a força axial já passa da tensão admissível.")
    w_necessario = abs(momento) / (admissivel - abs(media))
    alternativas = _perfis_que_atendem(secao, abs(momento), cortante, admissivel, normal_n=normal)
    tabelas: tuple[Tabela, ...] = ()
    if alternativas:
        tabelas = (
            Tabela(
                "Perfis mais leves da mesma família que atendem",
                alternativas,
                "Pela tensão e pelo cortante. Não inclui a flambagem lateral.",
            ),
        )
    alertas: list[str] = []
    if secao.perfil is not None and familia_do_perfil(secao.perfil) in _FAMILIAS_ABERTAS:
        alertas.append(
            "Perfil aberto: esta é a conta de tensão, que não vê a flambagem lateral nem a local. "
            "Sem travamento, use o caso Perfil de aço."
        )
    envios: tuple[Envio, ...] = ()
    if secao.perfil is not None:
        envios = (
            Envio(
                "perfil_nbr8800",
                "Verificar este perfil pela NBR 8800",
                {
                    "perfil": secao.perfil.nome,
                    "mx_kNm": abs(float(v["m_kNm"])) if secao.eixo == "x" else 0.0,
                    "my_kNm": abs(float(v["m_kNm"])) if secao.eixo == "y" else 0.0,
                    "v_kN": cortante / 1000.0,
                    "n_kN": normal / 1000.0,
                },
            ),
        )
    return Resultado(
        resumo=(
            f"Maior tensão normal de {maior:.1f} MPa, com {secao.nome}. O limite é "
            f"{admissivel:.1f} MPa."
        ),
        metricas=(
            Metrica("Tensão na fibra de cima", sigma_sup, "MPa", 1),
            Metrica("Tensão na fibra de baixo", sigma_inf, "MPa", 1),
            Metrica("Cortante máximo", tau, "MPa", 1),
            Metrica("W da seção", secao.w_mm3 / 1000.0, "cm³", 1),
            Metrica("W necessário", w_necessario / 1000.0, "cm³", 1),
        ),
        verificacoes=(
            limite(
                "Tensão normal",
                maior,
                admissivel,
                "MPa",
                f"σ = N/A ± M/W; limite S_y/FS = {sy:.0f}/{fs:.2f}",
                SHIGLEY_3,
            ),
            limite(
                "Tensão de cisalhamento",
                tau,
                0.577 * admissivel,
                "MPa",
                f"{formula_tau}; limite 0.577·S_y/FS",
                SHIGLEY_3,
            ),
        ),
        pontos=(
            Ponto("Fibra de cima", sigma_sup),
            Ponto("Fibra de baixo", sigma_inf),
            Ponto("Centro da seção", media, tau_xy=tau),
        ),
        tabelas=tabelas,
        alertas=tuple(alertas),
        hipoteses=(
            "Flexão no plano do eixo escolhido, com seção constante e material elástico.",
            "Momento positivo traciona a fibra de baixo.",
            "A tensão normal cresce em linha reta a partir do centro da seção.",
            "Forças de serviço, sem majorar: a segurança vem do fator FS.",
        ),
        referencias=(SHIGLEY_3, HIBBELER),
        envios=envios,
    )


CAMPOS_FLEXAO: tuple[Campo, ...] = (
    Campo(
        "m_kNm",
        "Momento fletor M",
        "Momento na seção. Positivo traciona a fibra de baixo.",
        30.0,
        "kN·m",
        passo=5.0,
        secao="Esforços",
    ),
    Campo(
        "v_kN",
        "Cortante V",
        "Força cortante na seção.",
        20.0,
        "kN",
        passo=5.0,
        secao="Esforços",
    ),
    Campo(
        "n_kN",
        "Força axial N",
        "Positiva para tração e negativa para compressão.",
        0.0,
        "kN",
        passo=5.0,
        secao="Esforços",
    ),
    *campos_de_secao(),
    *campos_de_material(),
)


# ---------------------------------------------------------------------------
# Perfil de aço pela norma
# ---------------------------------------------------------------------------

NORMAS = {
    "ABNT NBR 8800:2025": "NBR8800_2024",
    "ABNT NBR 8800:2008": "NBR8800_2008",
    "AISC 360-16 (LRFD)": "AISC360_16_LRFD",
}


def _esforcos(v: Valores) -> vb.EsforcoNoPonto:
    return vb.EsforcoNoPonto(
        "Cálculo",
        "Seção",
        float(v["n_kN"]),
        float(v["mx_kNm"]),
        float(v["v_kN"]),
        m_fraco=float(v["my_kNm"]),
    )


def _verificar(v: Valores, perfil: str) -> vb.ResultadoDaBarra:
    return vb.verificar_barra_com_esforcos(
        "Barra",
        perfil,
        str(v["aco"]),
        (_esforcos(v),),
        lx_m=float(v["lx_m"]),
        ly_m=float(v["ly_m"]),
        lb_m=float(v["lb_m"]),
        cb=float(v["cb"]),
        norma=NORMAS[str(v["norma"])],
    )


def _mais_leves(v: Valores, atual: PerfilAco) -> tuple[dict[str, object], ...]:
    familia = familia_do_perfil(atual)
    candidatos = sorted(
        (p for p in sc.listar_perfis().values() if familia_do_perfil(p) == familia),
        key=lambda p: p.massa_kg_m,
    )
    linhas: list[dict[str, object]] = []
    for perfil in candidatos:
        try:
            resultado = _verificar(v, perfil.nome)
        except ValueError:
            continue
        if resultado.status != "OK" or resultado.aproveitamento is None:
            continue
        linhas.append(
            {
                "Perfil": perfil.nome,
                "Massa (kg/m)": perfil.massa_kg_m,
                "Aproveitamento (%)": resultado.aproveitamento * 100.0,
                "O que governa": resultado.governante,
            }
        )
        if len(linhas) == 5:
            break
    return tuple(linhas)


def calcular_perfil(v: Valores) -> Resultado:
    nome = str(v["perfil"])
    perfil = sc.obter_perfil(nome)
    resultado = _verificar(v, nome)
    principais = tuple(
        linha
        for linha in resultado.linhas
        if linha.status != "INFO"
        or linha.nome.startswith("Mx,Rd")
        or linha.nome.startswith("My,Rd")
    )
    detalhes = tuple(
        {
            "Grandeza": linha.nome,
            "Valor": linha.resistente if linha.resistente is not None else linha.solicitante,
            "Unidade": linha.unidade,
            "Cálculo": linha.formula,
        }
        for linha in resultado.linhas
        if linha.status == "INFO" and linha not in principais
    )
    alertas: list[str] = []
    if any("governa: FLT" in linha.formula for linha in resultado.linhas):
        alertas.append(
            "A flexão está limitada pela flambagem lateral com torção. Antes de trocar o perfil, "
            "veja se dá para travar a mesa comprimida: diminuir Lb aumenta o momento resistente."
        )
    if resultado.status == vb.STATUS_PENDENTE:
        resumo = f"Sem verificação automática para {nome}: {resultado.motivo}"
    elif resultado.aproveitamento is None:
        resumo = f"{nome}: sem esforços para verificar."
    else:
        resumo = (
            f"{nome}: aproveitamento de {resultado.aproveitamento * 100:.0f} %. Governa: "
            f"{resultado.governante}."
            if math.isfinite(resultado.aproveitamento)
            else f"{nome}: a norma não tem rotina de M_Rd para esta forma, e a flexão não pode ser "
            "aceita por aqui. Use as tensões da seção ou uma forma com rotina (I, U, T, tubos)."
        )
    metricas = [Metrica("Massa", perfil.massa_kg_m, "kg/m", 1)]
    if resultado.mx_rd is not None:
        metricas.insert(0, Metrica("Mx,Rd", resultado.mx_rd, "kN·m"))
    if resultado.my_rd is not None:
        metricas.insert(1, Metrica("My,Rd", resultado.my_rd, "kN·m"))
    if resultado.n_rd is not None:
        metricas.append(Metrica("N resistente", resultado.n_rd, "kN", 1))
    if resultado.aproveitamento is not None:
        metricas.append(Metrica("Aproveitamento", resultado.aproveitamento * 100.0, "%", 0))

    tabelas = [Tabela("Valores intermediários", detalhes)] if detalhes else []
    leves = _mais_leves(v, perfil)
    if leves:
        tabelas.insert(
            0,
            Tabela(
                "Perfis mais leves da mesma família que atendem",
                leves,
                "Mesmos esforços, comprimentos e aço.",
            ),
        )
    return Resultado(
        resumo=resumo,
        metricas=tuple(metricas),
        verificacoes=principais,
        tabelas=tuple(tabelas),
        alertas=tuple(alertas),
        hipoteses=(
            "Os esforços digitados já são de cálculo: já vêm com os coeficientes das combinações "
            "de ações.",
            "Momento fletor resistente pelo menor entre flambagem lateral com torção, flambagem "
            "local da mesa e flambagem local da alma.",
            "Barra de seção constante. Sem ligação e sem furo: a seção líquida e a ligação são "
            "de outras páginas.",
        ),
        referencias=(str(v["norma"]), NBR_8800),
    )


CAMPOS_PERFIL: tuple[Campo, ...] = (
    Campo(
        "perfil",
        "Perfil",
        "Lista do catálogo de perfis. Digite parte do nome para filtrar.",
        "W 250 x 28,4",
        secao="Perfil e norma",
        opcoes_de=nomes_dos_perfis,
    ),
    Campo(
        "aco",
        "Aço",
        "Aço do perfil. Perfis W laminados costumam ser ASTM A572 Gr 50.",
        "ASTM A572 Gr 50",
        opcoes=tuple(vb.ACOS),
        secao="Perfil e norma",
    ),
    Campo(
        "norma",
        "Norma",
        "A ABNT NBR 8800:2025 é a vigente. As outras servem para comparar ou para obra antiga.",
        "ABNT NBR 8800:2025",
        opcoes=tuple(NORMAS),
        secao="Perfil e norma",
    ),
    Campo(
        "mx_kNm",
        "Momento no eixo forte Mx",
        "Momento de cálculo em torno do eixo forte, já com os coeficientes.",
        40.0,
        "kN·m",
        passo=5.0,
        secao="Esforços de cálculo",
    ),
    Campo(
        "my_kNm",
        "Momento no eixo fraco My",
        "Momento de cálculo em torno do eixo fraco, já com os coeficientes.",
        0.0,
        "kN·m",
        passo=1.0,
        secao="Esforços de cálculo",
    ),
    Campo(
        "v_kN",
        "Cortante V",
        "Cortante de cálculo no plano da alma.",
        30.0,
        "kN",
        passo=5.0,
        secao="Esforços de cálculo",
    ),
    Campo(
        "n_kN",
        "Força axial N",
        "Positiva para tração e negativa para compressão.",
        0.0,
        "kN",
        passo=5.0,
        secao="Esforços de cálculo",
    ),
    Campo(
        "lb_m",
        "Distância entre travamentos laterais Lb",
        "Trecho da mesa comprimida sem nada que a segure de lado. Laje apoiada na mesa trava a "
        "viga inteira: use um valor pequeno.",
        3.0,
        "m",
        minimo=0.01,
        passo=0.5,
        secao="Comprimentos",
    ),
    Campo(
        "cb",
        "Fator Cb",
        "Considera a forma do diagrama de momento. Sem cálculo, use 1,0, que é a favor da "
        "segurança.",
        1.0,
        minimo=1.0,
        maximo=3.0,
        passo=0.1,
        secao="Comprimentos",
    ),
    Campo(
        "lx_m",
        "Comprimento de flambagem em x",
        "K·L no eixo forte. Só entra quando há força axial de compressão.",
        3.0,
        "m",
        minimo=0.01,
        passo=0.5,
        secao="Comprimentos",
    ),
    Campo(
        "ly_m",
        "Comprimento de flambagem em y",
        "K·L no eixo fraco. Só entra quando há força axial de compressão.",
        3.0,
        "m",
        minimo=0.01,
        passo=0.5,
        secao="Comprimentos",
    ),
)

CASOS: tuple[Caso, ...] = (
    Caso(
        "viga_reacoes",
        "Viga: reações e momentos",
        GRUPO,
        "Escolha os apoios, as cargas e a seção. Saem os diagramas e a verificação.",
        "Biapoiada, em balanço, engastada ou contínua, com quantas cargas quiser. Mostra as "
        "reações, os diagramas, a flecha e os perfis mais leves que atendem.",
        CAMPOS_VIGA,
        calcular_viga,
        r"\sigma=\frac{M}{W},\quad \tau=\frac{V\,Q}{I\,t},\quad \delta\le\frac{L}{n}",
    ),
    Caso(
        "flexao_secao",
        "Flexão de uma seção",
        GRUPO,
        "Com o momento na mão: tensões, W necessário e os perfis que atendem.",
        "Quando o momento já é conhecido. Mostra a tensão nas fibras e o módulo W necessário, e "
        "segue para o Círculo de Mohr.",
        CAMPOS_FLEXAO,
        calcular_flexao,
        r"\sigma=\frac{N}{A}\pm\frac{M}{W},\quad W_{nec}=\frac{M}{S_y/FS-|N|/A}",
    ),
    Caso(
        "perfil_nbr8800",
        "Perfil de aço pela norma",
        GRUPO,
        "Momento resistente com flambagem lateral e local, pela norma.",
        "Verificação completa de um perfil do catálogo com os esforços de cálculo: flexão nos "
        "dois eixos, cortante, força axial e a interação entre eles.",
        CAMPOS_PERFIL,
        calcular_perfil,
        r"\frac{N_{Sd}}{N_{Rd}}+\frac{8}{9}\left(\frac{M_{x,Sd}}{M_{x,Rd}}"
        r"+\frac{M_{y,Sd}}{M_{y,Rd}}\right)\le 1",
    ),
)
