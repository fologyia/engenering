"""Textos de ajuda ("?") da página Nomes das barras, em linguagem simples."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    "sec_esqueleto": (
        "O esqueleto é o arquivo …_esqueleto.csv que a macro exportar_lista_de_corte grava ao lado "
        "da peça: cada corpo com a posição, a forma (barra, chapa ou bloco), as medidas e o item da "
        "lista de corte. É dele que a página tira a grade, os níveis e o papel de cada peça."
    ),
    "arquivo_esqueleto": (
        "Arraste o …_esqueleto.csv que a macro exportar_lista_de_corte grava na pasta da peça. "
        "Mudou o modelo no SolidWorks? Rode a macro de novo e envie o arquivo novo."
    ),
    "btn_gravar_esqueleto": (
        "Guarda o esqueleto no projeto: esta página, Cargas do esqueleto e Esforços do modelo "
        "passam a usar o mesmo arquivo."
    ),
    "btn_macro_lista": (
        "A macro exportar_lista_de_corte.bas (versão 7): grava a lista de corte e o esqueleto, "
        "agora com a coluna PERFIL. Na primeira vez: Ferramentas › Macro › Nova…, cole o texto e "
        "tecle F5."
    ),
    "sec_leitura": (
        "Como o programa enxerga o modelo antes dos nomes: a grade de eixos sai dos pés dos "
        "pilares, os níveis das vigas em nível e das chapas de piso, e o papel de cada peça da "
        "posição dela (ou do nome, quando o nome já diz)."
    ),
    "eixo_vertical": (
        "O eixo que aponta para cima no modelo. No SolidWorks é o Y, a não ser que a peça tenha "
        "sido desenhada com o Z para cima. Errado, os pilares viram vigas e a grade sai torta."
    ),
    "refazer": (
        "Desligado (o normal), o nome que já está no padrão e diz o papel certo fica como está: "
        "rodar a página de novo não troca o que não mudou. Ligue só se a grade mudou (um pilar novo "
        "desloca as letras e os números) e você quer que os nomes acompanhem — os estudos do "
        "Simulation vão precisar de malha nova."
    ),
    "res_corpos": "Quantos corpos o esqueleto tem: barras, chapas e peças curtas.",
    "res_no_padrao": (
        "Quantos corpos já têm um nome que diz o papel: no padrão (P-A1, V-N1-01) ou com a palavra "
        "por extenso (W200x31,3 - Pilar). Nesses o programa já não depende da posição."
    ),
    "res_mudam": "Quantos corpos ganham um nome novo com o arquivo desta página.",
    "res_contradizem": (
        "Corpos cujo nome atual diz um papel que a geometria não deixa (um pilar deitado, uma viga "
        "em pé, uma chapa chamada de barra): o programa segue a posição e avisa."
    ),
    "nivel_planta": (
        "O nível que a planta mostra, com o nome de cada peça. Os pilares aparecem em todos os "
        "níveis. Todos: a planta inteira, sem os nomes das barras."
    ),
    "sec_tabela": (
        "Uma linha por corpo do esqueleto: o papel que o programa entendeu, o nome novo e por quê. "
        "Troque o papel onde ele estiver errado; o nome se refaz sozinho. O nome só identifica: o "
        "que vale para o cálculo é o prefixo (P, V, LG, C…)."
    ),
    "tabela": (
        "Papel: escolha na lista (P pilar, V viga, LG longarina, DG degrau, C contraventamento, MF "
        "mão-francesa, GC guarda-corpo, PS piso, PT patamar, ES lance de escada, CH chapa sem "
        "carga, PC outra peça). Nome à mão: só se quiser outro nome — ele tem de começar com o "
        "prefixo do papel e um hífen. Trocar: desmarque para o corpo ficar com o nome de hoje."
    ),
    "btn_sugestoes": "Desfaz as escolhas da tabela (papéis, nomes à mão, quem não troca) e volta ao que o programa sugere.",
    "sec_perfis": (
        "O PERFIL de cada item da lista de corte: a peça da obra, dita por quem projeta. A macro o "
        "grava como uma propriedade nova do item, ao lado da DESCRIÇÃO — o desenho e a tabela da "
        "lista de corte não mudam. Com ele, o programa não precisa adivinhar o perfil pelo nome da "
        'biblioteca (C8x13.75 é qual U 8"?) nem pela área desenhada.'
    ),
    "tabela_perfis": (
        "Perfil a gravar: vem preenchido onde a descrição e o desenho dizem o mesmo perfil. Onde "
        "ficou vazio, há dúvida (veja De onde): escolha o perfil que vai ser comprado. Vazio não "
        "grava nada; num item que já tinha PERFIL, vazio apaga."
    ),
    "sec_levar": (
        "O arquivo de nomes e a macro que o aplica no SolidWorks. A macro confere cada corpo pela "
        "geometria antes de trocar, mostra o que vai fazer e só troca com a sua confirmação."
    ),
    "btn_arquivo": (
        "O …_nomes.csv: cada corpo que muda de nome (o nome de hoje, o novo e onde o corpo está) e "
        "o PERFIL de cada item. Salve-o na pasta da peça, ao lado do .SLDPRT (ou deixe em "
        "Downloads). Baixar também guarda as trocas no projeto: um estudo rodado antes da troca "
        "continua achando cada corpo."
    ),
    "btn_macro": (
        "A macro renomear_corpos.bas. Na primeira vez: no SolidWorks, com a peça aberta, "
        "Ferramentas › Macro › Nova…, dê um nome, cole o texto inteiro e tecle F5. Das outras "
        "vezes: Ferramentas › Macro › Executar…"
    ),
    "sec_depois": (
        "Depois de rodar a macro: envie o relatório que ela grava (…_nomes_aplicados.csv) para o "
        "projeto saber o que de fato trocou, gere o esqueleto de novo e, se o plano de cargas cita "
        "corpos pelo nome antigo, passe-o para os nomes novos."
    ),
    "arquivo_relatorio": (
        "O …_nomes_aplicados.csv que a macro grava ao lado da peça: cada corpo, o nome antigo, o "
        "novo e se trocou ou foi pulado (com o motivo)."
    ),
    "res_renomeados": "Corpos que a macro renomeou (pelo nome de antes, conferido pela geometria).",
    "res_pela_geometria": (
        "Corpos que a macro achou só pela geometria: o nome de antes já não existia na peça (o "
        "modelo mudou depois do esqueleto). Confira esses na árvore do SolidWorks."
    ),
    "res_pulados": "Corpos que ficaram com o nome de antes: o motivo de cada um está na tabela logo abaixo.",
    "btn_guardar_relatorio": (
        "Guarda no projeto as trocas que a macro fez: Esforços do modelo, Cargas do esqueleto e o "
        "3D passam a casar os nomes antigos dos estudos com os novos do esqueleto."
    ),
    "btn_plano": (
        "Troca, no plano de cargas, o nome antigo pelo novo nas linhas que citam um corpo (as "
        "cargas do esqueleto, por exemplo). Só as trocas que a macro confirmou ou que o esqueleto "
        "novo já mostra entram."
    ),
}
