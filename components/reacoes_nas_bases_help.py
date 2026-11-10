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
    "caso_desenho": (
        "O caso de carga que aparece na planta: cada pé no seu lugar, com a força vertical N "
        "(círculo azul de compressão ou vermelho de arrancamento, com a área crescendo com N), a "
        "horizontal H como seta e o momento, quando há. São as ações da estrutura na fundação, "
        "características e sem combinar, nos eixos da fundação."
    ),
    "eixos": (
        "Eixos da fundação: X e Y na planta e Z para cima, como o engenheiro civil costuma usar — o "
        "X é o do SolidWorks e o Y é o −Z do SolidWorks (a vista Superior com o Y para cima). Eixos "
        "do SolidWorks: os do modelo, com o Y para cima. Os valores são os mesmos; só muda o nome "
        "do eixo."
    ),
    "sec_eixos": (
        "O sistema de coordenadas das tabelas, desenhado para o engenheiro civil: os eixos do "
        "SolidWorks e os da fundação lado a lado, a planta (Z saindo da tela, ⊙) e a frente (Y "
        "entrando na tela, ⊗), e a diferença entre a ação na fundação e a reação no apoio. Na outra "
        "aba, o modelo em 3D com o nome de cada pé (A1, A2…), o mesmo das tabelas."
    ),
    "btn_png_eixos": (
        "Baixa o desenho do sistema de coordenadas em PNG, para mandar junto ou pôr num relatório."
    ),
    "btn_png_projeto": (
        "Baixa o modelo em 3D com o nome de cada pé em PNG (o mesmo que vai na aba Desenhos do "
        "Excel)."
    ),
    "tab_acao": (
        "A força e o momento que a estrutura faz na fundação, em cada pé e caso: é a carga para "
        "projetar a fundação. Fz negativa é para baixo (compressão); N = −Fz."
    ),
    "tab_reacao": (
        "A força e o momento que o apoio faz na estrutura: é o que o SolidWorks mostra em Força de "
        "reação. É a ação com o sinal trocado — os mesmos números, ao contrário."
    ),
    "reg_reacoes": (
        "Grava no projeto a ação de cada pé caso a caso, a reação do apoio, a locação, o resumo, o "
        "sistema de coordenadas e o projeto com os pés: é o que entra no memorial (Central de "
        "relatórios)."
    ),
    "btn_excel": (
        "Baixa a planilha para o engenheiro civil: Leia-me (convenção, conferência e pendências), "
        "Casos (natureza e coeficientes de cada caso, para combinar), Locação dos pés, Reações por "
        "pé (a ação na fundação e a reação no apoio lado a lado, cada uma com o título, com "
        "filtro), Resumo por pé (o maior de cada um) e Desenhos (o sistema de coordenadas, o "
        "projeto com os pés e a planta de cada caso). Com pendência para corrigir, o título sai "
        "como PRELIMINAR."
    ),
}
