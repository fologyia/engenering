"""Textos dos “?” da página Esforços do modelo, em linguagem simples (um teste exige cada um)."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    "sec_arquivos": (
        "No SolidWorks Simulation, com o estudo resolvido, clique com o botão direito em "
        "Resultados: “Listar forças da viga” (todas as vigas) e “Listar forças resultantes” "
        "(força de reação, modelo inteiro). Salve cada lista como CSV e envie aqui. Um estudo por "
        "caso de carga, com o código no nome (PP, SC, W0…). Com o gerenciador de casos de carga, "
        "a macro abaixo grava os dois arquivos de todos os casos de uma vez."
    ),
    "btn_macro_casos": (
        "Baixa a macro que tira os resultados do gerenciador de casos de carga. Na primeira vez, no "
        "editor de macros do SolidWorks: Ferramentas → Referências → marque “SOLIDWORKS Simulation "
        "<ano> type library”. Depois de Executar no gerenciador, com a aba Vista de resultados "
        "aberta: Ferramentas → Macro → Executar. Ela grava, na pasta da peça, as reações de cada "
        "caso, a reação em cada apoio, as fixações e o quadro dos sensores (sensores não são "
        "necessários). Para sair também as forças das vigas, antes de rodar selecione as vigas na "
        "árvore do estudo do Simulation (a primeira, Shift + a última); se não sair, use o “Listar "
        "forças da viga” de cada caso, com o código no nome do arquivo. Envie tudo aqui, junto."
    ),
    "arquivos": (
        "Pode enviar vários de uma vez: forças da viga e reações de cada estudo, e o "
        "…_esqueleto.csv da macro do SolidWorks. O programa reconhece cada arquivo, lê o nome do "
        "estudo e sugere o caso; o esqueleto diz onde fica cada barra (pilar, viga, "
        "contraventamento), o comprimento e o perfil. O “Listar tensões da viga”, junto com as "
        "forças do mesmo estudo, mostra a maior tensão e confere a seção que o Simulation usou "
        "em cada barra (não vai para o projeto)."
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
    "sec_leitura": (
        "O programa olha o modelo como um engenheiro olharia: onde está cada barra (pelo "
        "esqueleto), como ela trabalha (só força normal, flexão, compressão crescendo com o peso), "
        "se alguma ponta ficou solta, se a malha é grossa, se dois estudos deram o mesmo "
        "resultado, se o estudo do PP ficou com outra carga ou se a gravidade foi esquecida em "
        "outro caso. Leia os avisos de cima para baixo: os vermelhos invalidam a análise."
    ),
    "res_leitura": (
        "Quantas barras o programa reconheceu como pilar, viga ou contraventamento (pela posição "
        "no esqueleto ou, sem ele, pela inclinação que o peso próprio mostra no estudo PP) e "
        "quantas têm uma ponta sem esforço nenhum — quase sempre uma junta que faltou no "
        "SolidWorks."
    ),
    "btn_macro_esqueleto": (
        "Baixa a macro do SolidWorks. Com a peça soldada aberta: Ferramentas → Macro → Executar. "
        "Ela grava a lista de corte (vai na página Lista de material) e o …_esqueleto.csv "
        "(envie aqui no passo 1)."
    ),
    "btn_aplicar_sugestoes": (
        "Preenche a tabela das barras com o que o programa entendeu: tipo, perfil (só se estiver "
        "no catálogo), eixo forte e os comprimentos de flambagem pelos travamentos do esqueleto "
        "(onde outras barras se ligam a cada uma, em cada direção; K = 1, balanço K = 2,1). Só "
        "preenche o que está vazio — com uma exceção: o eixo forte tirado da seção (macro v6 ou "
        "perfil) troca o da tabela, porque não é escolha, é qual momento do Simulation é o do "
        "eixo forte. A chapa de piso presa à mesa superior não entra no Lb sugerido: confira a "
        "fixação antes de reduzir."
    ),
    "fundacoes_no_modelo": (
        "Para dar a força e o momento do pilar nos eixos do SolidWorks, o programa precisa saber "
        "para que lado a seção do pilar está virada no Simulation: a linha pela macro v6 e o "
        "sentido por um caso de vento viga a viga (carga em cada pilar), importado aqui."
    ),
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
    "sec_diagnostico": (
        "O programa confere todos os arquivos juntos — o plano de cargas, as reações, as forças, os "
        "apoios e a leitura do modelo — e diz aqui, antes da verificação, o que está errado e como "
        "corrigir, do mais grave ao menos. Os que têm botão se corrigem no próprio programa.\n\n"
        "O erro mais comum é salvar as forças com outro caso carregado no gerenciador. Por isso o "
        "programa confere cada arquivo de forças contra a reação do mesmo caso: a soma vertical, a "
        "reação no pé de cada pilar (arquivos de apoios da macro), para que lado o vento empurra "
        "(o lado comprimido, com o esqueleto) e a cortante dos pilares. Quando os números são de "
        "outro caso, ele diz qual."
    ),
    "res_diagnostico": (
        "Para corrigir: o resultado está errado até corrigir. Para conferir: pode estar errado. "
        "Conferem: o que já bate."
    ),
    "btn_diag_grade": (
        "Tira do plano de cargas as linhas da grade de exemplo (barras “N1 · eixo A…” que o seu "
        "modelo não tem). As outras cargas ficam."
    ),
    "btn_diag_nomes": (
        "Troca o nome dos casos importados (forças, reações e apoios) para o do caso do programa que "
        "tem a mesma direção e o mesmo valor. O SolidWorks não muda: renomeie lá também para as "
        "próximas vezes."
    ),
    "sec_apoios": (
        "A reação em cada apoio do modelo, direto do SolidWorks (arquivos -apoios.csv da macro, "
        "um por caso): a força e o momento que cada apoio põe na fundação, por caso, sem combinar "
        "nem majorar — o que se manda ao engenheiro da fundação. Vale para qualquer apoio (pé de "
        "pilar, pé de escada), não só para as barras marcadas como Pilar."
    ),
    "res_apoios_comportamento": (
        "Como cada apoio trabalhou no modelo: com momento em algum caso, engastado; sem momento, "
        "articulado. Confira com a fixação que você pôs no SolidWorks e com a base que vai ser "
        "construída (placa com chumbadores fora da linha do pilar = engaste)."
    ),
    "btn_xlsx_apoios": "O quadro por apoio em Excel, com a aba do comportamento de cada apoio.",
    "btn_csv_apoios": "O quadro por apoio em CSV (abre no Excel).",
    "reg_quadro": (
        "Grava o quadro no projeto ativo: o memorial ganha o capítulo com a compressão por "
        "pilar e o quadro completo."
    ),
    "sec_placas": (
        "A placa de base e os chumbadores de cada pilar (concreto pela NBR 8800 6.6.5; placa e "
        "chumbadores pelo Design Guide 1 do AISC): os esforços "
        "da base (os mesmos do quadro das fundações) são combinados com os fatores do plano de "
        "cargas e vale a combinação que mais exige. Uma placa padrão para todos os pilares."
    ),
    "placa_n": (
        "Comprimento N da placa (mm), na direção da alma do pilar — a direção em que o momento do "
        "eixo forte comprime um lado e puxa os chumbadores do outro."
    ),
    "placa_b": "Largura B da placa (mm), na direção das mesas. Precisa ser ao menos a largura da mesa.",
    "placa_t": (
        "Espessura da placa (mm). O critério Anglo pede no mínimo 16 mm (12,5 mm em elementos "
        "leves)."
    ),
    "placa_aco": "Aço da placa: dá o f_y da flexão da placa.",
    "placa_fck": "Resistência do concreto (ou do graute) sob a placa, em MPa.",
    "placa_a2a1": (
        "A₂/A₁: área do topo do bloco ÷ área da placa. 1,0 se a placa cobre o bloco inteiro; "
        "maior aumenta a pressão admissível (no máximo o dobro, limite do AISC)."
    ),
    "placa_chumbadores": "Quantos chumbadores a placa tem no total (metade em cada linha).",
    "placa_lado": "Quantos chumbadores ficam na linha tracionada — os que seguram o momento.",
    "placa_diametro": (
        'Diâmetro do chumbador. O critério Anglo pede no mínimo 5/8" e dá, para cada diâmetro, o '
        "furo na placa, a arruela e o graute mínimo (item 8.7)."
    ),
    "placa_aco_chumbador": "Aço do chumbador: dá o f_u da tração e do cisalhamento.",
    "placa_f": (
        "Distância do centro da placa à linha dos chumbadores tracionados (mm). Zero = N/2 − 50 mm."
    ),
    "placa_leve": "Ligue para elemento leve (escada, passarela): a placa mínima Anglo cai para 12,5 mm.",
    "btn_gravar_placa": "Grava a placa no projeto e verifica todos os pilares com ela.",
    "placa_anglo": (
        "Liga as exigências do critério Anglo: espessura mínima da placa, diâmetro mínimo do "
        "chumbador e o furo, a arruela e o graute do item 8.7. Vem da base técnica."
    ),
    "res_placas": (
        "Utilização da placa mais exigida (flexão da placa, contato no concreto ou chumbadores) "
        "e quantos pilares atendem."
    ),
    "res_desenho_placa": (
        "A placa em planta, em escala: o pilar, os chumbadores, os furos e as arruelas (tracejadas)."
    ),
    "placa_detalhe": "Mostra a verificação completa da placa de um pilar, na combinação que governa.",
    "btn_csv_placas": "A verificação das placas de todos os pilares em CSV (abre no Excel).",
    "reg_placas": (
        "Grava a verificação das placas no projeto ativo: o memorial ganha o capítulo com o "
        "resultado de cada pilar."
    ),
    "reg_registrar": (
        "Grava a verificação no projeto ativo: o memorial ganha o capítulo com o resultado, as "
        "barras que passaram e, no fim, as que não passaram."
    ),
}
