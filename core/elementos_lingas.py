"""Linga de corrente para içamento pela ABNT NBR 15516-2:2013, Anexo A, sem Streamlit.

A carga máxima de trabalho (CMT) marcada na etiqueta vem da NBR 15516-1 ou da NBR ISO 8539. Este
caso aplica as reduções do uso, todas lidas no texto da norma (PDF da pasta de normas, 14/11/2026):

* A.1.1.2.1, Tabela A.1: temperatura (grau 4: 100 % até 300 °C, 75 % até 400 °C, 50 % até 475 °C;
  grau 8: 100 % até 200 °C, 90 % até 300 °C, 75 % até 400 °C; acima, não permissível);
* A.1.1.2.2.2: grau 4 em condição ácida trabalha com no máximo 50 % da CMT; o grau 8 não deve ser
  usado em ácido (A.1.1.2.2.1);
* A.1.3.3 e Figura A.1: ângulo com a vertical nunca acima de 60°; abaixo de 15° evitar
  (desequilíbrio); o ângulo fica dentro da faixa marcada na linga;
* A.1.3.4 b): método-forca, CMT no máximo 80 % da marcada; olhal com diâmetro menor que três
  passos da corrente, CMT reduzida em 50 %;
* A.1.3.5: carregamento simétrico só com as quatro condições a) a d); senão, metade da CMT;
* A.1.3.7, Tabela A.2: menos pernas que o total (2 pernas usando 1: 1/2; 3 ou 4 usando 2: 2/3;
  usando 1: 1/3);
* A.1.3.8: a CMT, depois de tudo isso, igual ou maior que a massa içada.

A força em cada perna (F = m·g/(n·cos β), a da Figura A.1) sai só como informação: a CMT da etiqueta
já leva o número de pernas e o ângulo.
"""

from __future__ import annotations

import math

from core.elementos_base import (
    Campo,
    Caso,
    Metrica,
    Resultado,
    Tabela,
    Valores,
    exigir,
    informativo,
    limite,
    recomendacao,
)

GRUPO = "Içamento"
G = 9.80665
NBR = "ABNT NBR 15516-2:2013"

PERNAS = ("1 perna", "2 pernas", "3 pernas", "4 pernas")
GRAUS = ("Grau 8", "Grau 4")
FAIXAS = ("0° a 45°", "45° a 60°")
RETA = "Perna reta (terminal direto na carga)"
FORCA = "Método-forca (corrente passa e engancha na própria perna)"
CESTA = "Método-cesta (corrente passa e volta ao anel)"
METODOS = (RETA, FORCA, CESTA)

#: Tabela A.1: (temperatura máxima da faixa em °C, fração da CMT); None = não permissível.
TEMPERATURA = {
    "Grau 4": ((200.0, 1.00), (300.0, 1.00), (400.0, 0.75), (475.0, 0.50)),
    "Grau 8": ((200.0, 1.00), (300.0, 0.90), (400.0, 0.75)),
}

#: Tabela A.2: (pernas da linga, pernas usadas) → fator sobre a CMT marcada. A tabela trata três e
#: quatro pernas na mesma linha, com a mesma CMT marcada: quatro pernas usando três não reduz.
MENOS_PERNAS = {(2, 1): 1 / 2, (3, 2): 2 / 3, (4, 2): 2 / 3, (3, 1): 1 / 3, (4, 1): 1 / 3}


def fator_de_temperatura(grau: str, temperatura: float) -> float | None:
    """Tabela A.1; ``None`` acima da última faixa (não permissível)."""
    exigir(temperatura >= -40.0, "Abaixo de −40 °C, a norma manda consultar o fabricante.")
    for maxima, fator in TEMPERATURA[grau]:
        if temperatura <= maxima:
            return fator
    return None


def calcular_linga(v: Valores) -> Resultado:
    massa = float(v["massa_t"])
    cmt = float(v["cmt_t"])
    total = int(str(v["pernas"]).split()[0])
    usadas = int(v["pernas_usadas"]) if total > 1 else 1
    exigir(1 <= usadas <= total, "As pernas usadas não podem passar das pernas da linga.")
    grau = str(v["grau"])
    metodo = str(v["metodo"])

    fatores: list[tuple[str, float, str]] = []

    def aplicar(motivo: str, fator: float, item: str) -> None:
        fatores.append((motivo, fator, item))

    temperatura = float(v["temperatura_C"])
    fator_t = fator_de_temperatura(grau, temperatura)
    if fator_t is None:
        limite_grau = TEMPERATURA[grau][-1][0]
        raise ValueError(
            f"{grau} acima de {limite_grau:.0f} °C não é permissível (NBR 15516-2, Tabela A.1): "
            "tire a linga de serviço."
        )
    if fator_t < 1.0:
        aplicar(f"Temperatura de {temperatura:g} °C", fator_t, "A.1.1.2.1, Tabela A.1")
    alertas: list[str] = []
    if bool(v["acido"]):
        if grau == "Grau 4":
            aplicar("Condição ácida (grau 4)", 0.5, "A.1.1.2.2.2 a)")
            alertas.append(
                "Grau 4 em ácido: lave a linga em água limpa logo depois do uso e peça a "
                "inspeção diária por pessoa qualificada (A.1.1.2.2.2 b e c)."
            )
        else:
            raise ValueError(
                "Linga de grau 8 não deve ser usada imersa em ácido nem exposta a vapores ácidos "
                "(NBR 15516-2, A.1.1.2.2.1). Use grau 4 com a CMT reduzida ou consulte o fabricante."
            )
    if usadas < total and (total, usadas) in MENOS_PERNAS:
        aplicar(
            f"{usadas} de {total} pernas em uso",
            MENOS_PERNAS[(total, usadas)],
            "A.1.3.7, Tabela A.2",
        )
    if metodo == FORCA:
        aplicar("Método-forca", 0.8, "A.1.3.4 b)")
    if metodo != RETA and bool(v["olhal_pequeno"]):
        aplicar("Olhal menor que 3 passos da corrente", 0.5, "A.1.3.4")

    linhas = []
    beta_max = beta_min = 0.0
    if usadas > 1:
        beta_max = float(v["beta_max"])
        beta_min = float(v["beta_min"])
        exigir(beta_min <= beta_max, "O menor ângulo não pode passar do maior.")
        faixa_sup = 45.0 if str(v["faixa"]) == FAIXAS[0] else 60.0
        linhas.append(
            limite(
                "Ângulo das pernas com a vertical",
                beta_max,
                min(60.0, faixa_sup),
                "°",
                f"β ≤ {faixa_sup:.0f}° da faixa marcada na linga e nunca acima de 60°",
                f"{NBR}, A.1.3.3 e Figura A.1",
            )
        )
        linhas.append(
            recomendacao(
                "Ângulo mínimo com a vertical",
                15.0,
                beta_min,
                "°",
                "evitar β < 15°: risco de desequilíbrio de carga bem maior",
                f"{NBR}, A.1.3.3",
            )
        )
    # A.1.3.5: simetria (a condição a, carga < 80 % da CMT, entra no fim, com a CMT já reduzida)
    simetrico = True
    motivos_assimetria = []
    if usadas > 1:
        if beta_max < 15.0:
            simetrico = False
            motivos_assimetria.append("todos os ângulos abaixo de 15°")
        if beta_max - beta_min > 15.0:
            simetrico = False
            motivos_assimetria.append("ângulos com a vertical a mais de 15° um do outro")
        if usadas > 2 and not bool(v["plano_ok"]):
            simetrico = False
            motivos_assimetria.append("ângulos no plano a mais de 15° um do outro")
    parcial = cmt * math.prod(fator for _, fator, _ in fatores)
    if usadas > 1 and massa >= 0.8 * parcial:
        simetrico = False
        motivos_assimetria.append("carga de 80 % da CMT ou mais")
    if not simetrico:
        aplicar("Carregamento assimétrico (" + "; ".join(motivos_assimetria) + ")", 0.5, "A.1.3.5")

    cmt_ajustada = cmt * math.prod(fator for _, fator, _ in fatores)

    peso_kN = massa * G
    if usadas > 1:
        cos_b = math.cos(math.radians(beta_max))
        por_perna = peso_kN / (usadas * cos_b)
        duas = peso_kN / (2 * cos_b)
    else:
        por_perna = duas = peso_kN

    verificacoes = [
        limite(
            "Massa içada contra a CMT ajustada",
            massa,
            cmt_ajustada,
            "t",
            f"CMT marcada {cmt:g} t × fatores = {cmt_ajustada:.2f} t",
            f"{NBR}, A.1.3.8",
        ),
        *linhas,
        informativo(
            "Força em cada perna, dividida por igual",
            por_perna,
            "kN",
            f"F = m·g/(n·cos β), n = {usadas}, β = {beta_max:g}°",
            f"{NBR}, Figura A.1",
        ),
    ]
    if usadas > 2:
        verificacoes.append(
            informativo(
                "Força por perna com só duas trabalhando",
                duas,
                "kN",
                "carga rígida: a maior parte pode ir para duas pernas",
                f"{NBR}, A.1.3.5 e Figura A.5",
            )
        )
    if metodo == CESTA and usadas == 1:
        alertas.append(
            "Método-cesta com uma perna só: a corrente precisa passar pela carga alinhada e acima "
            "do centro de gravidade (A.1.3.4 c)."
        )
    if usadas > 1 and beta_max > 30.0 and metodo != RETA:
        alertas.append(
            "Com ganchos ou laços envolvendo caixas e tambores, convém o ângulo das pernas não "
            "passar de 30° com a vertical: o componente horizontal cresce rápido (A.1.3.3)."
        )
    return Resultado(
        resumo=(
            f"CMT ajustada de {cmt_ajustada:.2f} t para {massa:g} t de carga "
            f"({massa / cmt_ajustada * 100:.0f} %)."
            if cmt_ajustada > 0
            else "CMT ajustada nula."
        ),
        metricas=(
            Metrica("CMT ajustada", cmt_ajustada, "t", 2),
            Metrica("Aproveitamento", massa / cmt_ajustada * 100, "%", 0),
            Metrica("Força por perna", por_perna, "kN", 1),
            Metrica("Fator total sobre a marcada", cmt_ajustada / cmt, "", 3),
        ),
        verificacoes=tuple(verificacoes),
        tabelas=(
            Tabela(
                "Reduções aplicadas à CMT marcada",
                tuple(
                    {"Redução": motivo, "Fator": fator, "Item da norma": item}
                    for motivo, fator, item in fatores
                )
                or ({"Redução": "Nenhuma", "Fator": 1.0, "Item da norma": "—"},),
            ),
        ),
        alertas=tuple(alertas),
        hipoteses=(
            "A CMT marcada é a da etiqueta, pela NBR 15516-1 ou NBR ISO 8539, para o número de "
            "pernas e a faixa de ângulo da linga.",
            "As reduções se multiplicam; a da assimetria entra quando falta qualquer condição de "
            "A.1.3.5.",
            "Içamento sem choque: arranque e frenagem bruscos aumentam a força na corrente "
            "(A.1.3.4) e pedem as Ações de içamento.",
            "Massa da carga conhecida (A.1.3.2) e pontos de fixação acima do centro de gravidade "
            "(A.1.3.3).",
        ),
        referencias=(f"{NBR}, Anexo A",),
    )


_MULTIPLAS = ("pernas", PERNAS[1:])

CAMPOS_LINGA: tuple[Campo, ...] = (
    Campo(
        "massa_t",
        "Massa da carga",
        "Massa a içar, com acessórios abaixo da linga. 1 t = 1000 kg.",
        3.0,
        "t",
        minimo=0.001,
        passo=0.1,
        secao="Carga e linga",
    ),
    Campo(
        "cmt_t",
        "CMT marcada na linga",
        "Carga máxima de trabalho da etiqueta, para o número de pernas e a faixa de ângulo.",
        6.7,
        "t",
        minimo=0.001,
        passo=0.1,
        secao="Carga e linga",
    ),
    Campo(
        "pernas",
        "Pernas da linga",
        "Quantas pernas a linga tem, usadas ou não.",
        PERNAS[1],
        opcoes=PERNAS,
        secao="Carga e linga",
    ),
    Campo(
        "pernas_usadas",
        "Pernas em uso",
        "Quantas pernas pegam a carga. Menos que o total reduz a CMT (Tabela A.2).",
        2,
        minimo=1,
        maximo=4,
        passo=1,
        secao="Carga e linga",
        quando=_MULTIPLAS,
    ),
    Campo(
        "grau",
        "Grau da corrente",
        "Grau 8 é o comum em linga de içamento. Grau 4 aceita ácido com redução.",
        GRAUS[0],
        opcoes=GRAUS,
        secao="Carga e linga",
    ),
    Campo(
        "faixa",
        "Faixa de ângulo da CMT marcada",
        "A faixa escrita na etiqueta junto da CMT.",
        FAIXAS[0],
        opcoes=FAIXAS,
        secao="Ângulos",
        quando=_MULTIPLAS,
    ),
    Campo(
        "beta_max",
        "Maior ângulo com a vertical β",
        "Ângulo entre a perna e a vertical, na perna mais aberta.",
        40.0,
        "°",
        minimo=0.0,
        maximo=89.0,
        passo=1.0,
        secao="Ângulos",
        quando=_MULTIPLAS,
    ),
    Campo(
        "beta_min",
        "Menor ângulo com a vertical",
        "Na perna mais fechada. Ângulos iguais deixam a carga simétrica.",
        35.0,
        "°",
        minimo=0.0,
        maximo=89.0,
        passo=1.0,
        secao="Ângulos",
        quando=_MULTIPLAS,
    ),
    Campo(
        "plano_ok",
        "Ângulos no plano dentro de 15° um do outro",
        "Só em 3 ou 4 pernas: vistos de cima, os pontos de fixação ficam igualmente espaçados "
        "em volta do centro de gravidade.",
        True,
        secao="Ângulos",
        quando=("pernas", PERNAS[2:]),
    ),
    Campo(
        "metodo",
        "Como a corrente pega a carga",
        "Perna reta: o terminal engata direto no ponto de içamento. Forca e cesta: a corrente "
        "passa por baixo ou através da carga.",
        RETA,
        opcoes=METODOS,
        secao="Uso",
    ),
    Campo(
        "olhal_pequeno",
        "Olhal menor que 3 vezes o passo da corrente",
        "Quando a corrente passa por um olhal de diâmetro menor que três passos: CMT pela metade.",
        False,
        secao="Uso",
        quando=("metodo", (FORCA, CESTA)),
    ),
    Campo(
        "temperatura_C",
        "Temperatura da corrente em serviço",
        "A maior que a corrente pode atingir. Até 200 °C não reduz nada.",
        20.0,
        "°C",
        minimo=-40.0,
        maximo=600.0,
        passo=10.0,
        secao="Uso",
    ),
    Campo(
        "acido",
        "Condição ácida",
        "Imersa em solução ácida ou exposta a vapores ácidos.",
        False,
        secao="Uso",
    ),
)

CASOS: tuple[Caso, ...] = (
    Caso(
        "linga_corrente",
        "Linga de corrente (NBR 15516-2)",
        GRUPO,
        "CMT da etiqueta reduzida pelo uso: ângulo, pernas, forca, assimetria e temperatura.",
        "Linga de corrente de uma a quatro pernas. Informe a massa, a CMT da etiqueta e como a "
        "linga vai trabalhar: sai a CMT ajustada pelas reduções do Anexo A da NBR 15516-2, a "
        "força em cada perna e o que a norma pede de cuidado.",
        CAMPOS_LINGA,
        calcular_linga,
        r"CMT_{aj}=CMT\prod f_i\ \ge\ m,\qquad F_{perna}=\frac{m\,g}{n\cos\beta}",
    ),
)
