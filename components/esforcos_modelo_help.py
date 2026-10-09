"""Textos dos “?” da página Esforços do modelo, em linguagem simples (um teste exige cada um)."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    "sec_arquivos": (
        "No SolidWorks Simulation, com o estudo resolvido, clique com o botão direito em "
        "Resultados: “Listar forças da viga” (todas as vigas) e “Listar forças resultantes” "
        "(força de reação, modelo inteiro). Salve cada lista como CSV e envie aqui. Um estudo por "
        "caso de carga, com o código no nome (PP, SC, W0…)."
    ),
    "arquivos": (
        "Pode enviar vários de uma vez: forças da viga e reações de cada estudo. O programa "
        "reconhece o tipo, lê o nome do estudo e sugere o caso."
    ),
    "eixo_vertical": (
        "O eixo vertical do modelo: no SolidWorks costuma ser o Y. Serve para separar a reação "
        "vertical da horizontal na conferência."
    ),
    "res_arquivos": (
        "O que foi reconhecido em cada arquivo. Confira a coluna Caso: é o código do plano de "
        "cargas a que o estudo corresponde (as reações vão para o mesmo caso das forças da viga)."
    ),
    "btn_gravar_arquivos": (
        "Grava os esforços no projeto ativo. Um caso que já existe é substituído pelo novo."
    ),
    "sec_casos": "Os estudos do SolidWorks já importados, um por caso de carga do plano.",
    "caso_remover": "Qual caso tirar do projeto (por exemplo, para importar de novo).",
    "btn_remover": "Tira o caso escolhido do projeto.",
    "sec_conferencia": (
        "O modelo recebeu a carga certa? Para cada caso: num caso só de cargas verticais, as "
        "reações horizontais precisam dar quase zero; as forças concentradas do plano precisam "
        "bater com as reações; numa carga por área, a reação dividida pela carga dá a área "
        "carregada, para você comparar com o piso."
    ),
    "res_tensao": (
        "A maior tensão de von Mises do arquivo “Listar tensão”. É só uma referência: as "
        "verificações da NBR 8800 usam os esforços das barras, não a tensão."
    ),
    "sec_barras": (
        "Uma linha por barra do modelo. Escolha o perfil (o programa já preenche quando o nome "
        "do SolidWorks diz qual é), o tipo (pilar, viga, diagonal…) e qual momento é o do eixo "
        "forte. Fica gravado no projeto."
    ),
    "btn_gravar_barras": "Grava a tabela das barras no projeto ativo.",
    "sec_envoltoria": (
        "Para cada barra, o pior de todas as combinações do plano de cargas, ponto a ponto: a "
        "maior compressão, a maior tração, o maior momento forte (com o N da mesma combinação e "
        "ponto), o maior momento fraco, cortante e torque. Valores de cálculo, em kN e kN·m."
    ),
    "estados": (
        "Estados-limite das combinações: ELU normal para as verificações de resistência; os ELS "
        "servem para conferir esforços de serviço."
    ),
    "filtro_tipo": "Mostra só as barras de um tipo (o da tabela das barras).",
    "btn_csv": "A tabela do pior caso de cada barra em CSV (abre no Excel).",
    "sec_parametros": (
        "O que vale para todas as barras de um tipo: aço, comprimentos de flambagem K·L em torno "
        "do eixo forte (Lx) e do fraco (Ly), comprimento destravado Lb para a flambagem lateral, "
        "Cb e o B₂ da segunda ordem global. Uma barra pode ter os seus na tabela das barras."
    ),
    "norma": (
        "Norma da verificação: o Projeto de revisão da NBR 8800 (2024), a NBR 8800:2008 ou o AISC "
        "360-16. É o mesmo motor da página Flambagem de colunas."
    ),
    "btn_gravar_parametros": "Grava a norma e os parâmetros por tipo no projeto ativo.",
    "sec_verificacao": (
        "Cada barra verificada pela NBR 8800 com os esforços de todas as combinações ELU em "
        "todos os pontos: compressão (todos os modos de flambagem), flexão (FLT, FLM, FLA), "
        "interação N + Mx + My, cortante e esbeltez. Sem perfil ou sem comprimentos, a barra fica "
        "sem dados."
    ),
    "res_resumo": (
        "Quantas barras atendem, quantas não atendem, quantas faltam dados (perfil ou "
        "comprimentos) e o maior aproveitamento (solicitante ÷ resistente)."
    ),
    "barra_detalhe": (
        "Mostra a tabela completa da verificação de uma barra, na combinação e no ponto que a "
        "governam (começa pela mais solicitada)."
    ),
    "btn_csv_verificacao": "A verificação de todas as barras em CSV (abre no Excel).",
    "sec_fundacoes": (
        "As cargas na base de cada pilar (as barras marcadas como Pilar), caso a caso, sem "
        "combinar nem majorar — como pede o critério Anglo (5.9): quem projeta a fundação faz as "
        "combinações dela. A soma das bases é conferida contra a reação total do modelo."
    ),
    "res_fundacoes": (
        "Quantos pilares entram no quadro, a maior compressão na base e a maior tração "
        "(arrancamento), entre todos os casos."
    ),
    "ver_quadro": (
        "Compressão por pilar: uma linha por pilar e uma coluna por caso. Quadro completo: N, "
        "cortantes, momentos e torção de cada pilar em cada caso."
    ),
    "btn_xlsx_quadro": "O quadro em Excel, com a nota do critério Anglo e a convenção de sinais.",
    "btn_csv_quadro": "O quadro completo em CSV (abre no Excel).",
    "reg_quadro": (
        "Grava o quadro no projeto ativo: o memorial ganha o capítulo com a compressão por "
        "pilar e o quadro completo."
    ),
    "reg_registrar": (
        "Grava a verificação no projeto ativo: o memorial ganha o capítulo com o resultado, as "
        "barras que passaram e, no fim, as que não passaram."
    ),
}
