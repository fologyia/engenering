"""Textos dos “?” (dicas) da página Degrau de escada em grade, em linguagem simples.

Ficam num módulo só para a página e os testes falarem do mesmo jeito e para um teste garantir que
nenhum campo fique sem explicação. Aceitam Markdown (negrito e listas). Cada texto diz, na ordem:
o que é, como preencher e — quando existir — a simplificação que o programa adota.
"""

from __future__ import annotations

AJUDA: dict[str, str] = {
    # ------------------------------------------------------------------ seções
    "sec_1": (
        "Dados do documento: obra, TAG do equipamento ou da escada, responsável e data. Não "
        "entram no cálculo; saem no relatório (PDF), no registro do projeto e no memorial."
    ),
    "sec_2": (
        "Qual norma manda no acesso e se o degrau tem espelho (a chapa vertical entre um degrau e "
        "o outro). Isso muda a **altura do espelho**, o **piso** e a **largura mínima** que o "
        "programa exige."
    ),
    "sec_3": (
        "A escada em si: o desnível a vencer e o tamanho do degrau. O programa escolhe sozinho o "
        "**número de espelhos**, o **piso** e a **profundidade** para cumprir a norma legal, o "
        "Critério Anglo e o limite do catálogo, **nesta ordem de prioridade**. Cada campo "
        "“impor…” deixa você fixar um valor no lugar do automático (e o programa mostra o que "
        "isso causa nas verificações, sem corrigir nada em silêncio)."
    ),
    "sec_4": (
        "O degrau de grade de piso eletrofundida do catálogo Selmec “Degraus” (DS): o programa "
        "avalia os **64 modelos** e adota o mais leve que atende ao cálculo e à largura "
        "recomendada pelo fabricante. Aqui você define a preferência (ou escolhe o modelo à mão), "
        "o material, o acabamento e a fixação."
    ),
    "sec_5": (
        "Cargas, coeficientes de segurança e limites de flecha. Os valores iniciais são os das "
        "normas citadas em cada campo; só mude por critério do projeto."
    ),
    "sec_6": (
        "O guarda-corpo **não é dimensionado** aqui: o programa só confere as medidas que você "
        "informa contra a NR-12, a NR-22 e o Critério Anglo."
    ),
    "sec_res": (
        "O resultado muda sozinho quando você troca um dado. Use as abas: tabela de verificações, "
        "memorial do modelo adotado, os 64 modelos do catálogo e o texto para a requisição de "
        "compra, com a exportação em CSV e PDF."
    ),
    # ------------------------------------------------------------------ 1. identificação
    "obra": "Nome da obra ou do projeto, só para identificar o relatório.",
    "tag": "TAG da escada ou do equipamento atendido (por exemplo, ESC-0101). Sai no título do registro.",
    "responsavel": "Quem responde pelo cálculo. Sai no relatório e no registro do projeto.",
    "data": "Data do cálculo, para o relatório.",
    # ------------------------------------------------------------------ 2. enquadramento
    "enquadramento": (
        "Qual norma legal vale para esta escada:\n\n"
        "- **NR-12 – acesso a máquina/equipamento**: escadas que levam a uma máquina ou "
        "equipamento seguem o Anexo III da NR-12.\n"
        "- **NR-22 – acesso a local de trabalho (mineração)**: os demais acessos da mineração "
        "seguem o item 22.10.1.1 da NR-22. Pela NR-22 (22.10.6), a escada de acesso a máquina ou "
        "equipamento continua sendo da NR-12."
    ),
    "espelho_fechado": (
        "O **espelho** é a chapa vertical entre dois degraus. Grade vazada (aberta) é escada "
        "**sem** espelho, e vale o item 11 do Anexo III da NR-12. Com espelho fechado vale o "
        "item 12, que pede espelho de 200 a 250 mm e piso de pelo menos 200 mm.\n\n"
        "**Simplificação:** na NR-22 o espelho fechado não muda as faixas."
    ),
    "uso": (
        "Define a **largura mínima** do Critério Anglo (item 10.2): 800 mm para uso geral, "
        "1.100 mm onde há permanência constante (rota de emergência) e 800 mm (até 3.700 mm de "
        "altura) ou 1.100 mm para cabine no 1º andar."
    ),
    # ------------------------------------------------------------------ 3. geometria
    "H": (
        "**Desnível total** a vencer, de piso acabado a piso acabado, em milímetros. Com ele o "
        "programa define o número de espelhos."
    ),
    "h_alvo": (
        "Altura de espelho que você gostaria de ter (em mm). O programa a usa como referência, "
        "mas respeita a faixa da norma e o número inteiro de espelhos. O Anglo aceita 160 a "
        "180 mm; o catálogo exige pelo menos 175 mm."
    ),
    "n_imposto": (
        "Se preencher, o número de espelhos passa a ser este (a altura do espelho vira "
        "desnível ÷ número). Vazio = automático (o programa escolhe). Se o valor imposto sair das faixas da "
        "norma, as verificações acusam."
    ),
    "b_imposto": (
        "**Piso b**: a parte horizontal em que se pisa, em mm. Vazio = o programa escolhe o menor "
        "múltiplo de 5 mm que cumpre Anglo (2h + b entre 630 e 640 mm) e a norma legal."
    ),
    "C_imposto": (
        "**Profundidade C** do degrau, em mm (a dimensão de uma chapa lateral à outra no sentido "
        "do passo). Vazio = automática. O catálogo vai de 175 a 300 mm."
    ),
    "C_padronizado": (
        "Ligado, a profundidade automática segue a série do catálogo (175, 200, 225, … 300 mm). "
        "Desligado, usa o menor múltiplo de 5 mm que cumpre a norma. C fora da série exige "
        "**confirmar a furação F** com o fabricante."
    ),
    "L": (
        "**Comprimento do degrau**: o vão livre entre as chapas laterais, em mm. O catálogo vai "
        "de 500 a 1.500 mm, e cada modelo tem um comprimento máximo recomendado."
    ),
    "reducao_largura": (
        "Quanto a **largura útil** (a passagem real da pessoa) fica menor que L por causa do "
        "corrimão ou de outro elemento que avança para dentro, em mm. A largura útil é o que "
        "se compara com o mínimo legal e com o do Anglo."
    ),
    "altura_max_lance": (
        "Altura máxima que um **lance** (trecho de escada entre patamares) pode vencer. Vazio = o "
        "limite legal: 3.000 mm na NR-12 e 3.600 mm na NR-22. Se impuser mais que o legal, a "
        "verificação continua comparando com o limite legal."
    ),
    "patamar": (
        "Comprimento do **patamar** intermediário (o piso plano entre dois lances), em mm. Só "
        "vale com mais de um lance; a norma pede pelo menos 600 mm."
    ),
    # ------------------------------------------------------------------ 4. degrau
    "selecao": (
        "**Automática**: o programa escolhe o modelo mais leve que atende. **Manual**: você "
        "escolhe o modelo e o programa só verifica (mesmo que ele não atenda)."
    ),
    "malha": (
        "Família da grade pelo passo das barras portantes: A = 30 mm, B = 25 mm, C = 35 mm, "
        "F = 41 mm. O Anglo cita a grade Selmec GS-A4 na Tabela 7, por isso o padrão é a "
        "malha A. “Qualquer” deixa o programa procurar em todas."
    ),
    "ligacao": (
        "Barras de ligação são as barras finas e perpendiculares que travam as portantes: tipo 4 "
        "a cada 100 mm e tipo 2 a cada 50 mm. Quanto mais próximas, menor o comprimento sem "
        "travamento (L_b) e maior a resistência à flambagem lateral."
    ),
    "modelo_manual": (
        "Modelo do catálogo (DS-malha e ligação-altura da barra/espessura). Vale só com a seleção "
        "manual. Exemplo: DS-A4-35/3 = malha A, ligação a cada 100 mm, barra de 35 mm de altura e "
        "3 mm de espessura."
    ),
    "superficie": (
        "**Serrilhada** é a superfície antiderrapante exigida pela NR-12, pela NR-22 e pelo "
        "Anglo. Lisa gera ALERTA."
    ),
    "xadrez": (
        "Se o bocel (a borda frontal do degrau) leva chapa xadrez. Só entra no texto da "
        "requisição.\n\n**Simplificação:** a chapa xadrez não ajuda na distribuição da carga "
        "(a favor da segurança)."
    ),
    "acabamento": (
        "Proteção contra corrosão. O Anglo (4.5, nota 2) pede **galvanização a fogo** para aço-"
        "carbono e **passivação** para inox; sem proteção reprova."
    ),
    "material": (
        "Aço da grade. O padrão do Anglo é o ASTM A36. Os inox AISI 304, 304L, 316 e 316L geram "
        "ALERTA (aprovação Anglo) e a NBR 8800 não os cobre: fy e E são indicativos."
    ),
    "lado_barra": (
        "Lado da barra quadrada torcida das barras de ligação, em mm. **É um valor adotado só "
        "para estimar o peso** (o catálogo não informa); não entra na resistência."
    ),
    "parafuso": (
        "Parafuso A307 galvanizado que prende o degrau à longarina. O Anglo (8.8) exige pelo "
        'menos 5/8". O furo do catálogo é para 1/2" (9/16" × 25 mm); para 5/8" é preciso pedir '
        'furo oblongo especial de 11/16" × 25 mm.'
    ),
    "n_parafusos": (
        "Quantos parafusos prendem cada chapa lateral. O Anglo (9.1) exige pelo menos 2. O "
        "cortante da reação é dividido por este número."
    ),
    # ------------------------------------------------------------------ 5. cargas
    "q": (
        "**Sobrecarga distribuída** sobre o degrau, em kN/m². Padrão 3,00 (Anglo 5.2, Tabela 2: "
        "escadas e passadiços)."
    ),
    "P": (
        "**Carga concentrada** no meio do vão, junto ao bocel, em kN (ELU). Padrão 2,50 (NBR "
        "6120, degraus isolados; o item 2.2.1.7 é da edição 1980, confira o da edição 2019). "
        "Não se soma à distribuída."
    ),
    "P_iso": (
        "Carga concentrada para a **flecha** pela ISO 14122-3 (4.7.1), em kN. Padrão 1,50 sobre "
        "uma área de 100 × 100 mm."
    ),
    "b_c": (
        "Largura sobre a qual a carga concentrada atua, em mm (a ISO usa 100 × 100 mm). Define "
        "quantas barras portantes a recebem: n_ef = ⌊b_c/p⌋ + 1.\n\n"
        "**Simplificação:** um modelo de grelha deu 4,0 a 4,9 barras efetivas na malha 30 e 3,0 a "
        "3,2 na malha 41; o valor adotado é igual ou menor (a favor da segurança)."
    ),
    "n_ef": (
        "Número de barras que recebem a carga concentrada. Vazio = automático (⌊b_c/p⌋ + 1, "
        "limitado ao número de barras do degrau)."
    ),
    "gamma_g": "Coeficiente da ação permanente (peso próprio). Padrão 1,25 (NBR 8800, Tabela 1: peso próprio de estrutura metálica).",
    "gamma_q": "Coeficiente da ação variável (sobrecarga e carga concentrada). Padrão 1,50 (NBR 8800, Tabela 1).",
    "gamma_a1": "Coeficiente de resistência do aço no escoamento (flexão e cisalhamento). Padrão 1,10 (NBR 8800).",
    "gamma_a2": "Coeficiente de resistência do parafuso (ruptura). Padrão 1,35 (NBR 8800).",
    "cb": (
        "**C_b**: fator do diagrama de momentos na flambagem lateral com torção (FLT). 1,00 é "
        "conservador (momento uniforme); valores maiores aumentam a resistência na faixa "
        "inelástica e elástica."
    ),
    "flecha_div": (
        "Limite de flecha da carga distribuída: o vão dividido por este número (L/300 no Anglo, "
        "Tabela 3, vigas de piso secundárias)."
    ),
    "flecha_iso_div": (
        "Limite de flecha sob a carga concentrada da ISO 14122-3: o vão dividido por este número "
        "(L/300)."
    ),
    "flecha_iso_max": (
        "Flecha máxima absoluta sob a carga concentrada da ISO, em mm (6,0 mm). O limite usado é "
        "o menor entre L/300 e este valor."
    ),
    # ------------------------------------------------------------------ 6. guarda-corpo
    "gc_sup": (
        "Altura do **travessão superior** do guarda-corpo, em mm. A NR-12 e a NR-22 pedem de "
        "1.100 a 1.200 mm; o Anglo pede pelo menos 1.300 mm (conflito, que o programa sinaliza)."
    ),
    "gc_int": "Altura do **travessão intermediário**, em mm: 700 mm (NR-12 7 e; NR-22 22.6.5 e), com tolerância de 0,5 mm.",
    "gc_rod": "Altura do **rodapé** (a chapa baixa que impede a queda de objetos), em mm: pelo menos 200 mm.",
    "gc_esp": "Espaçamento máximo entre barras do guarda-corpo, em mm: no máximo 150 mm (Anglo 10.2).",
    # ------------------------------------------------------------------ resultados
    "res_modelo": (
        "Modelo do catálogo Selmec adotado e como foi escolhido: o mais leve que atende ao "
        "cálculo e à largura recomendada, dentro da preferência; ou o que você escolheu."
    ),
    "res_espelho_piso": (
        "Altura do espelho (h) e do piso (b). A soma 2h + b é a **fórmula de Blondel** (o "
        "conforto do passo): 630 a 640 mm no Anglo; α é a inclinação da escada."
    ),
    "res_c_l": (
        "Profundidade (C) e comprimento (L) do degrau. F é a furação da chapa lateral do "
        "catálogo; r = C − b é a sobreposição de um degrau sobre o outro."
    ),
    "res_lances": (
        "Número de espelhos e de degraus em grade. Um **lance** é o trecho entre patamares; em "
        "cada lance o último espelho chega ao patamar, então há um degrau a menos que espelhos "
        "por lance."
    ),
    "res_aproveitamento": (
        "Maior razão solicitante ÷ resistente entre as verificações de resistência (flexão, "
        "cisalhamento, flechas e parafuso). Acima de 100 % reprova."
    ),
    "res_peso": (
        "Peso estimado de um degrau e do total. É estimativa: a barra de ligação tem lado adotado "
        "e o catálogo soma 20 % sobre a grade equivalente (nota 4)."
    ),
    "res_status": (
        "**OK**: nada reprovou nem pede ressalva. **ALERTA**: atende com ressalva ou há conflito "
        "entre normas. **NÃO OK**: pelo menos uma verificação reprova. A contagem não inclui as "
        "linhas informativas (INFO)."
    ),
    "res_situacao": (
        "Em que nível a altura do espelho foi resolvida: 1 atende norma, Anglo e catálogo; 2 "
        "atende norma e Anglo, mas o degrau passa de 300 mm; 3 só a norma (o Anglo fica de "
        "fora); 4 nenhuma faixa."
    ),
    "so_atencao": (
        "Esconde as linhas OK e INFO e deixa só o que reprova, o que tem ressalva ou conflito "
        "entre normas e o que não se aplica a este caso."
    ),
    "res_verificacoes": (
        "As 38 verificações, na ordem do cálculo. Cada linha traz a norma e o item, o valor e o "
        "limite, o aproveitamento (só nas de resistência) e o status."
    ),
    "res_memorial": (
        "As contas do modelo adotado, passo a passo: propriedades da barra, flambagem lateral "
        "(FLT), cargas, esforços, flechas, reação nas chapas laterais e parafuso."
    ),
    "res_geometria": (
        "Como a escada ficou: espelho, piso, profundidade, furação, lances, degraus, projeção "
        "horizontal e largura útil."
    ),
    "res_catalogo": (
        "Os 64 modelos do catálogo calculados com esta escada. **Atende** = aproveitamento ≤ 1 e "
        "L dentro do máximo recomendado; **Na preferência** = dentro da malha e da ligação "
        "escolhidas. O adotado fica destacado: é por esta tabela que se vê por que um modelo "
        "foi escolhido e outro não."
    ),
    "res_requisicao": (
        "Texto pronto para a requisição de compra (nota 1 do catálogo). Use o botão de copiar "
        "do canto do bloco."
    ),
    "res_exportar": "Baixe as verificações, os 64 modelos ou o relatório completo em PDF.",
    "res_conflitos": (
        "Pontos em que as normas se contradizem. O programa segue a norma legal (o Anglo, item "
        "3.1, manda prevalecer a lei) e mostra o conflito para registrar uma consulta técnica."
    ),
    "res_avisos": (
        "Limites do cálculo: o que o catálogo não informa e o que deve ser conferido antes de "
        "emitir o documento."
    ),
    "btn_csv_verificacoes": "Baixa a tabela das 38 verificações em CSV (abre no Excel).",
    "btn_csv_catalogo": "Baixa a tabela dos 64 modelos em CSV (abre no Excel).",
    "btn_pdf": (
        "Gera o relatório em PDF: resumo, verificações com o item da norma, memorial do modelo "
        "adotado, os 64 modelos, a requisição e os avisos."
    ),
    "reg_registrar": (
        "Grava este cálculo no projeto ativo, com as 38 verificações e as tabelas, para entrar "
        "no memorial da Central de relatórios."
    ),
    # ------------------------------------------------------------------ colunas das tabelas
    "col_verificacao": "Nome da verificação, com o número do item (1 a 38).",
    "col_norma": "Norma e item em que a verificação se baseia.",
    "col_valor": (
        "O valor deste projeto: o que atua, nas verificações de resistência; o valor adotado, "
        "nos limites."
    ),
    "col_limite": (
        "O que a norma exige ou o degrau suporta: a resistência, nas verificações de "
        "resistência; o limite (ou a faixa, na observação), nos demais."
    ),
    "col_aproveitamento": "Valor ÷ resistência, em %. Só as verificações de resistência têm; acima de 100 % reprova.",
    "col_status": "OK atende · NÃO OK reprova · ALERTA ressalva ou conflito · INFO informação · N/A não se aplica.",
    "col_observacao": "Como o valor foi calculado, com os números deste caso, e o que fazer quando não atende.",
}
