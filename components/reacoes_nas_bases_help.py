"""Textos de ajuda (o "?") da página Reações nas bases, em linguagem simples."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    "sec_resumo": (
        "O que vai para quem projeta a fundação: em cada pé da estrutura, em cada caso de carga "
        "(PP, PE, SC, ventos…), as três forças e os três momentos que a estrutura faz na fundação. "
        "São valores característicos, sem combinar nem majorar (critério Anglo, item 5.9): o "
        "engenheiro civil faz as combinações dele."
    ),
    "res_pes": (
        "Os pés da estrutura: os apoios do modelo (pela macro) ou, sem ela, a base de cada pilar. "
        "Cada pé tem um nome (A1, A2…) pela posição: primeiro pelo X, depois pela outra direção "
        "horizontal. A locação está na tabela e no Excel."
    ),
    "res_casos": (
        "Os casos de carga importados em Esforços do modelo, na ordem do plano de cargas. Cada um "
        "sai separado, para o engenheiro civil combinar."
    ),
    "res_macro": (
        "Quantos valores (pé × caso) vieram da reação em cada apoio, lida do SolidWorks pela macro "
        "exportar_casos_de_carga (os -apoios.csv). É o número exato do modelo: o preferido."
    ),
    "res_pilar": (
        "Quantos valores vieram da força na base de cada pilar (Listar forças da viga), levada aos "
        "eixos do modelo pela direção da seção do pilar. Vale quando só o pilar chega no apoio. É "
        "usada no caso sem o -apoios.csv (ou com o arquivo de outra rodada)."
    ),
    "sec_reacoes": (
        "Uma linha por pé e caso: Fx, Fy e Fz (kN) e Mx, My e Mz (kN·m) que a estrutura faz na "
        "fundação — a reação com o sinal trocado. N é a compressão (positiva; negativa é "
        "arrancamento), H a força horizontal resultante. A última coluna diz de onde veio o número."
    ),
    "eixos": (
        "Eixos da fundação: X e Y na planta e Z para cima, como o engenheiro civil costuma usar — o "
        "X é o do SolidWorks e o Y é o −Z do SolidWorks (a vista Superior com o Y para cima). Eixos "
        "do SolidWorks: os do modelo, com o Y para cima. Os valores são os mesmos; só muda o nome "
        "do eixo."
    ),
    "btn_excel": (
        "Baixa a planilha para o engenheiro civil: Leia-me (convenção, conferência e pendências), "
        "Casos (natureza e coeficientes de cada caso, para combinar), Locação dos pés, Reações por "
        "pé (todos os pés e casos, com filtro) e Resumo por pé (o maior de cada um). Com pendência "
        "para corrigir, o título sai como PRELIMINAR."
    ),
}
