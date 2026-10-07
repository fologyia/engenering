"""Textos dos “?” (dicas) da página Vento nas estruturas, em linguagem simples.

Ficam num módulo só para a página e os testes falarem do mesmo jeito e para um teste garantir que
nenhum campo fique sem explicação. Aceitam Markdown (negrito e listas). Cada texto diz, na ordem:
o que é, como preencher e — quando existir — a simplificação que o programa adota.
"""

from __future__ import annotations

AJUDA: dict[str, str] = {
    # ------------------------------------------------------------------ seções
    "sec_1": (
        "O vento do **local** da obra: a velocidade que o mapa da norma dá para a cidade, o tipo de "
        "terreno em volta e a importância da construção. Com isso o programa calcula a velocidade "
        "característica **V_k** e a pressão dinâmica **q** (a pressão que o vento faria numa "
        "parede perpendicular a ele).\n\n"
        "**Simplificação:** o programa usa um único V₀ para todas as direções, como a norma manda "
        "quando não há estudo específico."
    ),
    "sec_2": (
        "A forma da construção: o tamanho da planta, a altura do beiral e o telhado. A norma só "
        "traz coeficientes para edificações **retangulares em planta, de arestas vivas**, com a "
        "cumeeira paralela ao lado maior.\n\n"
        "**Simplificação:** marquises, sheds, lanternins, galpões geminados e telhados curvos não "
        "estão aqui; para eles a norma tem outras tabelas ou pede estudo específico."
    ),
    "sec_3": (
        "O que decide a **pressão interna** (o ar que entra pelas aberturas e empurra as paredes "
        "e o telhado por dentro), a vizinhança e o tipo de vento. Estes campos mudam as "
        "pressões, mas costumam ter menos peso do que V₀ e a geometria."
    ),
    "sec_res": (
        "Os resultados mudam sozinhos quando você troca um dado. Use as abas: pressões por "
        "zona, vedações e fixações, forças globais, pórtico e a tabela de verificações para "
        "registrar no projeto."
    ),
    # ------------------------------------------------------------------ 1. vento no local
    "v0": (
        "**Velocidade básica do vento (V₀)**: a rajada de 3 segundos, a 10 m de altura, em campo "
        "aberto, que se repete em média uma vez a cada 50 anos. Vem do **mapa de isopletas** da "
        "NBR 6123 (Figura 1): ache o local da obra e leia o valor da linha mais próxima (de 5 em "
        "5 m/s). O programa não sabe a cidade; o valor é um dado do projeto."
    ),
    "relevo": (
        "Como é o terreno em volta, para o fator topográfico **S₁**:\n\n"
        "- **Plano ou fracamente acidentado**: S₁ = 1,0. É o caso comum.\n"
        "- **Vale profundo protegido** de ventos de qualquer direção: S₁ = 0,9.\n"
        "- **Topo de talude ou morro**: o vento acelera ao subir; S₁ vem da fórmula do item 5.2 e "
        "pode passar de 1,5.\n\n"
        "Na dúvida, use plano."
    ),
    "talude_theta": (
        "Inclinação média do talude ou da encosta do morro, em graus. Até 3° o relevo conta como "
        "plano; entre 3° e 6° e entre 17° e 45° a norma manda interpolar, e o programa faz isso."
    ),
    "talude_z": (
        "Altura do ponto estudado acima do terreno, em metros, no topo do talude ou morro. "
        "Quanto mais alto o ponto em relação ao desnível (z/d), menor o acréscimo de S₁."
    ),
    "talude_d": "Diferença de nível entre a base e o topo do talude ou morro, em metros.",
    "categoria": (
        "**Rugosidade do terreno** (S₂): quanto mais obstáculos em volta, mais o vento perde "
        "velocidade perto do chão.\n\n"
        "- **I**: superfície lisa e extensa — mar calmo, lago, rio.\n"
        "- **II**: campo aberto, quase sem obstáculos (≤ 1 m) — fazenda, aeroporto, zona costeira "
        "plana.\n"
        "- **III**: obstáculos baixos e esparsos (≈ 3 m) — sítios, subúrbio afastado.\n"
        "- **IV**: obstáculos numerosos e pouco espaçados (≈ 10 m) — zona industrial, cidade "
        "pequena, subúrbio denso.\n"
        "- **V**: obstáculos grandes e altos (≥ 25 m) — centro de grande cidade, floresta de "
        "árvores altas.\n\n"
        "A norma olha o terreno **a barlavento** (de onde o vento vem). Na dúvida entre duas, "
        "escolha a de numeração menor: dá mais vento e fica a favor da segurança."
    ),
    "grupo": (
        "**Importância da construção** (S₃, Tabela 4): quanto pior a consequência de a estrutura "
        "falhar, maior o S₃.\n\n"
        "- **1** (1,11): hospitais, quartéis de bombeiros, pontes, estruturas com produtos "
        "inflamáveis ou tóxicos.\n"
        "- **2** (1,06): locais com muita gente (mais de 300 pessoas, escolas, ginásios).\n"
        "- **3** (1,00): residências, hotéis, comércio e **indústrias** — o caso comum.\n"
        "- **4** (0,95): depósitos e silos sem ocupação humana nem circulação no entorno.\n"
        "- **5** (0,83): obras temporárias não reutilizáveis ou construção (até 2 anos)."
    ),
    "s3_estat": (
        "Calcula S₃ pela **probabilidade e vida útil** que você escolher (Anexo B), em vez de usar "
        "o valor do grupo. Serve para uma vida útil diferente de 50 anos ou outro nível de "
        "segurança. A norma **proíbe** um S₃ menor que o do grupo; se o resultado ficar abaixo, o "
        "programa usa o do grupo e avisa."
    ),
    "pm": (
        "Probabilidade de o vento de projeto ser excedido pelo menos uma vez na vida útil. A "
        "referência da norma é **0,63** (63 %) para 50 anos."
    ),
    "ma": "Vida útil da construção, em anos. A referência da norma é **50 anos**.",
    "classe": (
        "A classe diz quanto tempo a rajada de projeto dura e depende do **tamanho** da superfície "
        "que o vento atinge — a maior dimensão entre a largura e a altura:\n\n"
        "- **A**: até 20 m (rajada de 3 s) — também vale para telhas, painéis e fixações.\n"
        "- **B**: de 20 a 50 m (5 s).\n"
        "- **C**: acima de 50 m (10 s).\n\n"
        "**Automática** aplica a regra em cada direção do vento (a 0° o vento bate na largura; a "
        "90°, no comprimento); acima de 80 m o programa usa o Anexo A. Imponha uma classe só se "
        "o seu critério mandar."
    ),
    "ref_altura": (
        "Altura em que S₂ é calculado. A norma recomenda o **topo da edificação**: o vento que "
        "bate nas faces é desviado para baixo e aumenta a pressão em toda a altura. Escolha o "
        "beiral só para comparar."
    ),
    "vedacao_092": (
        "A nota da Tabela 4 permite usar **0,92 × S₃** só no projeto das **vedações** (telhas, "
        "vidros, painéis de vedação). Deixe desligado para ficar a favor da segurança; ligue se "
        "o seu critério aceitar a redução."
    ),
    # ------------------------------------------------------------------ 2. edificação
    "cobertura": (
        "Forma do telhado:\n\n"
        "- **Plana**: laje ou telhado sem inclinação.\n"
        "- **Duas águas**: a cumeeira divide o telhado ao meio, no sentido do comprimento.\n"
        "- **Uma água**: um lado mais alto que o outro (o programa põe o lado alto na parede "
        "y = 0).\n\n"
        "A norma só traz coeficientes para a **cumeeira paralela ao lado maior** da planta."
    ),
    "theta": (
        "Inclinação do telhado em **graus** (θ). Conversão de declividade: 10 % ≈ 5,7°; 15 % ≈ "
        "8,5°; 20 % ≈ 11,3°; 30 % ≈ 16,7°. Em telhado plano o campo fica desligado (θ = 0)."
    ),
    "a": (
        "**Comprimento** da edificação ao longo da cumeeira, em metros — o lado **maior** da "
        "planta (a). É a direção em que os pórticos se repetem. Tem que ser maior ou igual à "
        "largura."
    ),
    "b": (
        "**Largura** da edificação, em metros — o lado menor da planta (b), que é o **vão** do "
        "pórtico, de pilar a pilar."
    ),
    "h": (
        "Altura do chão até o **beiral**, em metros: o ponto onde o telhado encontra a parede. "
        "Não é a altura da cumeeira: ela o programa calcula pela inclinação."
    ),
    "beiral": (
        "Quanto o telhado avança para fora da parede, em metros (o balanço do beiral). A norma "
        "admite até **0,1 × b** (Detalhe I da Tabela 7); acima disso os coeficientes não valem. "
        "Deixe 0 se não houver."
    ),
    "espacamento": (
        "Distância entre dois pórticos vizinhos, em metros. A carga do vento por metro de pórtico "
        "é a pressão vezes esse espaçamento. O pórtico da **extremidade** recebe só metade."
    ),
    "periodo": (
        "Período fundamental T₁ da estrutura, em segundos (o tempo de uma oscilação completa). "
        "Se não souber, deixe **0** e o programa estima pela expressão da norma para edifícios de "
        "aço soldado (T₁ = 0,29·√h − 0,4). **Acima de 1 s** a norma manda calcular o efeito "
        "dinâmico do vento (Seção 9), e o programa avisa."
    ),
    # ------------------------------------------------------------------ 3. pressão interna etc.
    "permeabilidade": (
        "O ar que passa pelas frestas, janelas e portas cria uma **pressão dentro** da "
        "construção (c_pi). Ela soma ou subtrai da pressão de fora:\n\n"
        "- **Quatro faces igualmente permeáveis**: o caso comum de galpão com janelas e frestas. "
        "A norma manda testar c_pi = −0,3 e c_pi = 0 e usar o pior.\n"
        "- **Duas faces opostas permeáveis**: c_pi = +0,2 quando o vento bate numa delas e −0,3 "
        "quando bate numa face impermeável.\n"
        "- **Estanque**: janelas fixas e paredes sem abertura — c_pi = −0,2 ou 0.\n"
        "- **Informar**: digite os valores (por exemplo de uma abertura dominante).\n\n"
        "Cada valor vira um caso de carga separado."
    ),
    "cpis": (
        "Digite um ou mais valores de **c_pi** separados por ponto e vírgula, por exemplo "
        "**−0,3; 0,2**. Positivo é pressão interna (empurra as paredes para fora); negativo é "
        "sucção. Cada valor vira um caso de carga, nas duas direções do vento."
    ),
    "ad_posicao": (
        "Uma **abertura dominante** (um portão grande aberto, por exemplo) é uma abertura de área "
        "igual ou maior que a soma de todas as outras. Diga onde ela está em relação ao vento: "
        "a **barlavento** (de frente para ele), a **sotavento** (de costas) ou numa face "
        "**paralela** ao vento, dentro ou fora da zona de altas sucções."
    ),
    "ad_razao": (
        "Razão entre a área da abertura dominante e a soma das áreas das demais aberturas das "
        "faces sob sucção externa. Quanto maior, mais intensa a pressão interna. A norma dá "
        "valores para 1, 1,5, 2, 3 e 6 (a barlavento) e entre 0,25 e 3 (face paralela); entre "
        "eles o programa interpola."
    ),
    "ad_ce": (
        "Coeficiente de forma **C_e** da face ou do ponto onde está a abertura (Tabela 6): a "
        "norma manda adotar esse valor como c_pi quando a abertura é a sotavento ou numa face "
        "paralela fora da zona de altas sucções."
    ),
    "ad_usar": (
        "Copia o c_pi calculado para o campo “Informar c_pi” e passa a usar valores informados "
        "nas duas direções do vento."
    ),
    "vizinhanca": (
        "Ligue se há uma edificação alta, ou da mesma altura, **muito perto**: ela canaliza o "
        "vento entre as duas e aumenta as forças em até 30 % (fator de vizinhança f_v, item "
        "6.4). A norma só dá o fator para duas edificações altas vizinhas; para outras "
        "situações peça um estudo específico."
    ),
    "s_viz": (
        "Afastamento **s** entre os planos das faces que ficam de frente uma para a outra, em "
        "metros. Quanto menor, maior o efeito: até s/d* = 1 o fator é 1,3 e a partir de 3 vale 1,0."
    ),
    "alta_turb": (
        "O vento de **alta turbulência** (grandes cidades, edifícios cercados de outros mais "
        "altos) diminui a sucção na parede de sotavento (× 2/3) e o arrasto (Figura 5). A norma "
        "só permite se a vizinhança for densa e alta o bastante (item 6.1.3.1); o programa "
        "confere e, se a condição não for atendida, **não aplica** a redução e avisa."
    ),
    "h_viz": (
        "Altura média das edificações vizinhas **a barlavento**, em metros. A edificação não "
        "pode ter mais que o dobro dessa altura."
    ),
    "ext_viz": (
        "Até que distância a barlavento essas vizinhas se estendem, em metros. A norma exige "
        "500 m (edificação até 40 m de altura), 1 000 m (até 55 m), 2 000 m (até 70 m) ou "
        "3 000 m (até 80 m)."
    ),
    "ct": (
        "Rugosidade da superfície para a **força de atrito** do vento que corre ao longo de "
        "telhados e paredes compridos (item 6.1.5): 0,01 para superfície sem nervuras "
        "transversais ao vento; 0,02 com ondulações; 0,04 com nervuras retangulares. A força só "
        "existe quando o comprimento passa de 4 vezes a altura (ou a largura)."
    ),
    # ------------------------------------------------------------------ resultados
    "res_status": (
        "**OK**: o cálculo está dentro do campo de aplicação da norma. **ALERTA**: algum limite "
        "foi ultrapassado (a/b, h/b, inclinação, período, esbeltez) e o resultado pede "
        "conferência. O vento não tem “aprovado ou reprovado”: o que se verifica aqui é se as "
        "tabelas valem para a sua construção."
    ),
    "res_vk": (
        "**V_k = V₀ · S₁ · S₂ · S₃**: a velocidade característica do vento sobre a estrutura "
        "nesta direção, já com o relevo, a rugosidade, a altura e a importância."
    ),
    "res_q": (
        "**q = 0,613 · V_k²**: a pressão dinâmica, em kN/m². Multiplicada pelo coeficiente "
        "aerodinâmico de cada zona e pela área, dá a força do vento."
    ),
    "res_qved": (
        "Pressão dinâmica para **telhas, painéis e fixações**: sempre classe A (rajada de 3 s), "
        "no topo da edificação."
    ),
    "res_caso": (
        "Cada caso é uma direção do vento (0° = ao longo do comprimento, contra a empena; 90° = "
        "ao longo da largura, contra a parede longa) com um valor de c_pi."
    ),
    "res_zonas": (
        "Cada zona tem um **C_e** (coeficiente de forma externo). **Δp = q · (f_v · C_e − c_pi)** é a "
        "pressão que atua na superfície: **positiva empurra para dentro** (parede de barlavento), "
        "**negativa puxa para fora** (sucção em telhados e paredes laterais). A força é Δp "
        "vezes a área da zona."
    ),
    "res_vedacoes": (
        "Pressão para dimensionar **telhas, painéis, terças, travessas e fixações**. Usa q da "
        "classe A e, nas faixas de altas sucções (arestas e cantos), o **c_pe médio**, que é "
        "mais severo que o C_e das zonas comuns."
    ),
    "res_globais": (
        "Resultantes sobre a edificação inteira. A **força de arrasto F_a = q · C_a · A_e** vem do "
        "gráfico da norma; a **soma das zonas** vem das tabelas de C_e. Para o contraventamento "
        "e a fundação use o **maior** dos dois."
    ),
    "res_torcao": (
        "A força de arrasto não passa pelo centro da planta: a norma manda considerar uma "
        "**excentricidade** de 7,5 % do lado (15 % com vizinhança), o que gera um momento de "
        "torção M_t = F_a · e."
    ),
    "res_portico": (
        "Cargas por metro num pórtico transversal, **normais** ao pilar ou à água do telhado: "
        "positivo é pressão (empurra para dentro), negativo é sucção. A 0° as zonas mudam ao "
        "longo do comprimento, por isso há uma linha por faixa a partir da empena de barlavento."
    ),
    "res_verificacoes": (
        "Verificações de **aplicabilidade** das tabelas e do regime estático, e os valores de "
        "apoio do cálculo (V_k, q, C_a, forças). É esta tabela que vai para o memorial."
    ),
    # ------------------------------------------------------------------ pórtico
    "p_modo": (
        "Como informar a seção dos pilares e das águas: escolhendo um **perfil do catálogo** "
        "(área e inércia vêm do perfil, em torno do eixo forte) ou digitando **A e I**."
    ),
    "p_perfil_pilar": "Perfil dos pilares. Usa a área e o momento de inércia I_x do catálogo.",
    "p_area_pilar": "Área da seção dos pilares, em cm².",
    "p_inercia_pilar": "Momento de inércia dos pilares no plano do pórtico, em cm⁴.",
    "p_perfil_rafter": "Perfil das águas do telhado (vigas do pórtico). Usa A e I_x do catálogo.",
    "p_area_rafter": "Área da seção das águas, em cm².",
    "p_inercia_rafter": "Momento de inércia das águas no plano do pórtico, em cm⁴.",
    "p_modulo_e": "Módulo de elasticidade do aço: **200 000 MPa** (NBR 8800).",
    "p_bases": (
        "Como as bases dos pilares estão presas à fundação: **engastadas** (não giram) ou "
        "**rotuladas** (giram livres). Muda muito os momentos e o deslocamento."
    ),
    "p_caso": (
        "Escolha qual combinação de direção do vento, c_pi e faixa resolver. Para achar a pior, "
        "olhe o maior momento e a maior reação entre os casos."
    ),
    "p_limite": (
        "Limite do deslocamento horizontal do topo dos pilares como fração da altura (H/…). A "
        "tabela de deslocamentos máximos da NBR 8800 (Tabela B.1 do Projeto 2024) dá **H/300** "
        "para galpões e edificações de um pavimento e **H/400** para as de dois ou mais "
        "pavimentos; o vento entra com o valor característico, sem majorar. Em galpão com "
        "parede de alvenaria, limite também o deslocamento para que a fissura na base da parede "
        "não passe de 1,5 mm (B.3.4). Critérios de cliente podem ser mais rígidos."
    ),
    "res_p_desloc": (
        "Maior deslocamento horizontal de um nó do pórtico sob o vento **característico** (sem "
        "majorar). Compare com o limite H/…; o deslocamento vertical do meio do vão aparece "
        "quando a sucção levanta o telhado."
    ),
    "res_p_reacoes": (
        "Forças que as bases exercem sobre o pórtico (Rh horizontal, Rv vertical, M momento), em "
        "kN e kN·m, nos eixos da tela (y para a direita, z para cima). Reação vertical negativa "
        "é o chumbador **segurando** o pórtico contra o levantamento."
    ),
    "res_p_esforcos": (
        "Esforços nas pontas de cada elemento (N normal, V cortante, M momento), do pilar da "
        "esquerda ao da direita. O momento máximo do vão pode ser maior que os das pontas."
    ),
    # ------------------------------------------------------------------ arquivos e registro
    "btn_csv_zonas": "Baixa a tabela de pressões por zona do caso escolhido, em CSV (abre no Excel).",
    "btn_csv_vedacoes": "Baixa a tabela de pressões de projeto das vedações, em CSV (abre no Excel).",
    "btn_csv_portico": "Baixa as cargas por metro do pórtico, de todos os casos, em CSV (abre no Excel).",
    "btn_csv_verificacoes": "Baixa a tabela de verificações e valores de apoio, em CSV (abre no Excel).",
    "reg_registrar": (
        "Grava este cálculo no projeto ativo: dados de entrada, tabelas de pressões, vedações e "
        "cargas do pórtico. O memorial mostra o resultado, o que passou, o que não passou e as "
        "tabelas."
    ),
}
