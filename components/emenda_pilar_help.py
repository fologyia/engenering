"""Textos dos "?" da página Emenda de pilar, em linguagem simples."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    # seções
    "sec_perfis": (
        "Os dois trechos de pilar que a emenda une e os aços. O pilar inferior pode ser diferente do "
        "superior: a diferença de altura vira enchimento nas mesas e a de alma, enchimento na alma."
    ),
    "sec_parafusos": (
        "Os parafusos das talas. A mesa trabalha em corte simples (uma tala por fora) e a alma em "
        "corte duplo (uma tala de cada lado)."
    ),
    "sec_tipo": (
        "Com as extremidades usinadas e em contato, a compressão passa direto de um pilar para o "
        "outro e as talas só levam tração e cortante. Sem contato, toda a compressão passa pelas "
        "talas e pelos parafusos."
    ),
    "sec_pilar": (
        "Dados para estimar a resistência do pilar à compressão (N_c,Rd) e para o esforço mínimo da "
        "NBR 8800 6.1.6.2, que toda emenda precisa resistir mesmo que a análise dê menos."
    ),
    "sec_esforcos": (
        "Os esforços de cálculo (já majorados) na altura da emenda, um caso por linha. N positivo é "
        "compressão e negativo é tração. Acrescente linhas para mais casos."
    ),
    "sec_mesa": (
        "Uma tala externa em cada mesa. As fileiras são contadas de UM lado da emenda; o outro lado "
        "é igual. e_p vai do último furo à ponta da tala e e_c do primeiro furo à ponta do pilar."
    ),
    "sec_alma": (
        "Duas talas iguais na alma, uma de cada lado. As colunas de parafusos ficam lado a lado na "
        "horizontal e as fileiras em cima umas das outras, contadas de um lado da emenda."
    ),
    "sec_resumo": "O que sai do cálculo: as peças, os parafusos e a utilização que governa.",
    "sec_casos": (
        "As forças em cada caso, incluindo o caso mínimo da NBR 6.1.6.2 quando ele entra. F_f,t é a "
        "mesa mais tracionada (negativo = comprimida) e R_w o parafuso mais solicitado da alma."
    ),
    "sec_mesa_res": "As verificações da tala da mesa, dos parafusos da mesa e da mesa do pilar.",
    "sec_alma_res": "As verificações das talas da alma e dos parafusos da alma.",
    "sec_disposicoes": (
        "Regras de projeto e de boa prática. VERIFICAR não reprova a resistência, mas pede revisão "
        "do detalhe antes de liberar o desenho."
    ),
    "sec_desenho": "Vista da mesa e vista da alma, sem escala de fabricação, com as cotas principais.",
    "sec_exportar": "Baixe as entradas, os esforços e as verificações para conferir ou arquivar.",
    # perfis e materiais
    "perfil_superior": "Perfil do trecho de cima. A lista traz os W e HP 200 da Gerdau.",
    "perfil_inferior": (
        "Perfil do trecho de baixo. Se for mais alto que o de cima, as mesas recebem chapas de "
        "enchimento com metade da diferença de altura."
    ),
    "aco_perfis": "Aço dos pilares (critério Anglo, item 12). Define f_y e f_u da mesa e da alma.",
    "aco_talas": "Aço das talas. Define f_y e f_u das talas da mesa e da alma.",
    "E": "Módulo de elasticidade do aço. 200 000 MPa para aço estrutural.",
    "gama_a1": (
        "Coeficiente de ponderação do escoamento (NBR 8800, Tabela 3). 1,10 nas combinações normais."
    ),
    "gama_a2": (
        "Coeficiente de ponderação da ruptura, dos parafusos e do contato (NBR 8800, Tabela 3). "
        "1,35 nas combinações normais."
    ),
    # parafusos
    "diametro": "Diâmetro nominal do parafuso. O furo-padrão e a borda mínima saem das Tabelas 14 e 16.",
    "grau": "Grau do parafuso (ASTM F3125). A325: f_ub = 830 MPa; A490: f_ub = 1040 MPa.",
    "rosca": (
        "Marque se a rosca pode ficar no plano de corte (tipo N). O critério Anglo (9.1) manda "
        "admitir rosca incluída. Com rosca fora, a resistência ao corte sobe (0,56 em vez de 0,45)."
    ),
    "deslizamento": (
        "Verifica a ligação por atrito em serviço. É obrigatório quando os esforços invertem de "
        "sinal (Anglo 9.1; NBR 6.1.11). Pede parafusos protendidos."
    ),
    "superficie": "Preparo das superfícies em contato. Define o coeficiente de atrito μ (6.3.4.3).",
    "fator_servico": (
        "Quanto da força de cálculo atua em serviço. **Simplificação:** usa-se 0,70 × a força de "
        "cálculo em vez de rodar a combinação de serviço (NBR 6.3.4.4)."
    ),
    # tipo de emenda
    "contato": (
        "Marque se as pontas dos pilares são usinadas e ficam encostadas (NBR 6.1.6.1 e 12.3.5). "
        "A compressão passa pelo contato e é verificada na verificação 12."
    ),
    "gap": (
        "Folga entre as pontas dos pilares. Com contato, no máximo 2 mm; entre 2 e 6,3 mm, preencher "
        "com calços de aço (NBR 12.3.5)."
    ),
    # pilar
    "Lx": "Comprimento de flambagem do pilar em torno do eixo de maior inércia (x), em mm.",
    "Kx": "Coeficiente de flambagem em x. 1,0 para pilar biarticulado.",
    "Ly": "Comprimento de flambagem em torno do eixo de menor inércia (y), em mm.",
    "Ky": "Coeficiente de flambagem em y. 1,0 para pilar biarticulado.",
    "a": (
        "Altura da emenda acima do apoio inferior do trecho, em mm. Usada na situação b do esforço "
        "mínimo: a força transversal no vão gera momento e cortante na cota da emenda."
    ),
    "usar_nc": (
        "Ligue para informar o N_c,Rd do pilar (por exemplo, da página Flambagem de colunas). "
        "Desligado, o programa estima pela curva da NBR 5.3 sem flambagem local."
    ),
    "nc_rd": "Força axial resistente de cálculo do pilar superior, em kN.",
    "criterio": (
        "Esforço mínimo da NBR 6.1.6.2: a = tração de 50 % de N_c,Rd; b = força transversal de 2 % "
        "de N_c,Rd no meio do vão. O padrão usa a menos severa das duas, como a norma permite."
    ),
    "distribuicao": (
        "Como a força axial se divide. Por área: cada mesa leva b_f·t_f/A e a alma o resto. N/2 nas "
        "mesas: metade em cada mesa e nada na alma (SCI P207 5.2.2), mais conservador para as talas "
        "das mesas."
    ),
    "casos": (
        "N em kN (+ compressão, − tração), M_x e M_y em kN·m e V em kN, na cota da emenda. M_y entra "
        "quando há flexão no eixo fraco ou a ação de escora da compressão (SCI P207 5.2.2)."
    ),
    # talas das mesas
    "bp": "Largura da tala da mesa, em mm. Não pode passar da largura da mesa do pilar.",
    "tp": "Espessura da tala da mesa, em mm. Mínimo de 8 mm (Anglo 8.8).",
    "nl": "Quantas linhas de parafusos na largura da mesa (normalmente 2, uma de cada lado da alma).",
    "nr": "Quantas fileiras de parafusos de UM lado da emenda.",
    "g": "Gabarito: distância entre as linhas de parafusos na largura, em mm.",
    "s": "Passo: distância entre fileiras, na altura do pilar, em mm.",
    "ep": "Do centro do último furo à ponta da tala, em mm.",
    "ec": "Do centro do primeiro furo à ponta do pilar (a linha da emenda), em mm.",
    # talas da alma
    "bw": "Largura horizontal de cada tala da alma, em mm. Cabe na parte reta da alma (d').",
    "twp": "Espessura de cada tala da alma, em mm. Mínimo de 8 mm (Anglo 8.8).",
    "nc": "Quantas colunas de parafusos lado a lado na horizontal.",
    "m": "Quantas fileiras de parafusos de UM lado da emenda, na vertical.",
    "sh": "Espaçamento horizontal entre colunas de parafusos, em mm.",
    "sv": "Espaçamento vertical entre fileiras, em mm.",
    "ewv": "Do centro do último furo à ponta da tala da alma, em mm.",
    "ewc": "Do centro do primeiro furo à ponta do pilar, na alma, em mm.",
    # resultados
    "res_situacao": (
        "ATENDE quando todas as verificações de resistência passam. As disposições a VERIFICAR "
        "aparecem à parte e não mudam este resultado."
    ),
    "res_utilizacao": "A maior razão solicitante/resistente entre as verificações de resistência.",
    "res_parafusos": "Total de parafusos da emenda: 2·(2·n_b + n_bw), contando os dois lados.",
    "res_nc": "N_c,Rd usado no esforço mínimo: o informado ou o estimado pela NBR 5.3.",
    "res_minimo": "Qual situação da NBR 6.1.6.2 entrou como caso mínimo (a, b ou nenhuma).",
    "res_avisos": "Avisos do cálculo e o que ele não cobre.",
    "res_notas": "Notas para o desenho de fabricação e montagem quando a emenda é por contato.",
    "btn_csv": "Entradas, esforços e verificações num arquivo CSV (separador ;).",
    "btn_xlsx": "Entradas, esforços e verificações num Excel, em três abas.",
    # famílias, U e talas internas
    "familia": (
        "W e HP: todos os perfis W e HP do catálogo Gerdau. U: os perfis U laminados. Os dois "
        "trechos precisam ser da mesma família."
    ),
    "raio_u": (
        "Raio de concordância entre a mesa e a alma do U, em mm (catálogo do fabricante). O "
        "catálogo do programa não traz esse raio; com 0, a folga junto ao raio e a largura útil "
        "da alma ficam a VERIFICAR."
    ),
    "x1_u": (
        "No U, distância do dorso da alma até a primeira linha de furos da mesa, em mm (o "
        "gabarito de furação). A tala externa da mesa encosta no dorso."
    ),
    "sec_internas": (
        "Talas internas: além da tala externa, chapas por dentro da mesa (duas no W, uma de cada "
        "lado da alma; uma no U), encostadas na ponta da mesa e com o mesmo comprimento da "
        "externa. Os parafusos da mesa passam a trabalhar em corte duplo. **Simplificação:** a "
        "força da mesa se divide entre a externa e as internas pela área de cada uma."
    ),
    "talas_internas": "Ligue para acrescentar as talas internas nas mesas (corte duplo).",
    "bi": (
        "Largura de cada tala interna, em mm. Precisa caber entre a ponta da mesa e o raio junto "
        "à alma."
    ),
    "ti": "Espessura de cada tala interna, em mm. Mínimo de 8 mm (Anglo 8.8).",
    # modelo do SolidWorks
    "sec_do_modelo": (
        "Traz uma emenda do modelo gravado no projeto (Esforços do modelo): os perfis e o aço da "
        "tabela das barras, K·L_x e K·L_y pelos travamentos do esqueleto, o N_c,Rd do pilar de "
        "cima pela Flambagem de colunas e os esforços de cálculo de cada combinação no ponto da "
        "emenda. Tudo continua editável."
    ),
    "emenda_do_modelo": (
        "As emendas achadas no esqueleto (onde dois pilares em pé se encontram; com perfis "
        "diferentes, é a troca de perfil) e as informadas em Esforços do modelo."
    ),
    "estados": "Os estados-limite últimos cujas combinações viram os casos da emenda.",
    "base": (
        "Como o pé do pilar preso ao apoio do modelo trabalha, para o K dos trechos (o arquivo "
        "do SolidWorks não diz)."
    ),
    "btn_trazer": (
        "Preenche os perfis, o aço, o pilar e a tabela de esforços com os valores da emenda. As "
        "talas, o parafuso e o tipo de emenda ficam como estão."
    ),
    "vao_b": (
        "Vão da barra biapoiada da situação b de 6.1.6.2, em mm: o trecho entre os travamentos "
        "que contém a emenda. Com 0, vale L_x. Vem do esqueleto quando a emenda é trazida do "
        "modelo."
    ),
    "sec_sugerir": (
        "Monta as talas pelas regras de detalhamento desta página para os perfis, o parafuso e os "
        "esforços acima. Se a emenda não atende, sobe as fileiras e depois a espessura das talas. "
        "Não troca o parafuso: isso fica com quem projeta."
    ),
    "btn_sugerir": (
        "Preenche as talas da mesa e da alma (largura, espessura, linhas, fileiras, passos e "
        "bordas). Confira o resultado e ajuste à mão se quiser."
    ),
    "sec_todas": (
        "Verifica de uma vez todas as emendas do modelo, cada uma com os esforços dela e as talas "
        "sugeridas, usando o parafuso, os aços das talas e o tipo de emenda desta página."
    ),
    "verificar_todas": "Ligue para verificar todas as emendas do modelo (pode levar alguns segundos).",
    # memorial e registro
    "sec_memorial": (
        "O memorial só desta emenda. O Word é um trecho para colar no documento oficial (sem capa "
        "nem numeração fixa); o PDF segue o padrão do memorial do projeto."
    ),
    "btn_memorial_word": (
        "Trecho em Word: normas, dados, esforços por caso, desenhos, hipóteses, as verificações "
        "que se aplicam, o resumo do que passou e do que não passou, e a conclusão."
    ),
    "btn_memorial_pdf": "O mesmo conteúdo em PDF, no padrão do memorial do projeto.",
    "reg_registrar": (
        "Grava a emenda no projeto ativo. Ela entra no Memorial de cálculo do projeto, no capítulo "
        "das ligações, com os desenhos e as verificações."
    ),
}
