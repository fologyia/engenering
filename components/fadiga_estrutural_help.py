"""Textos dos "?" da página Fadiga da estrutura, em linguagem simples."""

AJUDA: dict[str, str] = {
    "sec_ciclos": (
        "Quantas vezes a carga que varia (talha, peneira, britador, transportador, tráfego) vai e "
        "volta durante a vida útil da estrutura. Com menos de 20 000 ciclos a fadiga não precisa "
        "ser verificada (NBR 8800, H.2.6)."
    ),
    "aco": (
        "Aço da peça. Ele não muda a resistência à fadiga (que depende do detalhe), só o limite "
        "de tensão em que o Anexo H vale (0,66·f_y)."
    ),
    "ciclos_por_dia": "Ciclos de carga por dia. Ex.: uma talha que faz 20 içamentos por hora em 10 h = 200.",
    "dias_por_ano": "Dias de operação por ano.",
    "anos": "Vida útil considerada, em anos.",
    "ciclos_informados": (
        "Se você já sabe o número total de ciclos da vida útil, informe aqui (substitui a conta "
        "ao lado). Use 0 para calcular pelos ciclos por dia."
    ),
    "res_ciclos": "Número total de ciclos N usado nas verificações.",
    "sec_detalhes": (
        "Cada linha é um ponto da estrutura onde pode nascer uma trinca: o tipo de detalhe (caso "
        "da Tabela H.1, que dá a categoria) e as tensões máxima e mínima ali."
    ),
    "tabela_detalhes": (
        "Detalhe: o nome do ponto. Caso da Tabela H.1: o tipo de detalhe e a categoria entre "
        "colchetes (A é o melhor, E' o pior; F é o cisalhamento na solda, G o parafuso). σ máx e "
        "σ mín: tensões no ponto na combinação frequente (cargas permanentes + variáveis sem "
        "majorar), tração positiva, por análise elástica, sem fator de concentração de tensões. "
        "t_p, 2a e w: só para os casos 5.6 e 5.7 com trinca na raiz (espessura da chapa, parte "
        "não soldada da raiz e perna do filete), em mm."
    ),
}
