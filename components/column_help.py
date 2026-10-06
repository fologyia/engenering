"""Textos dos “?” (dicas) da página Flambagem de colunas, em linguagem simples.

Ficam num módulo só para a página e os testes falarem do mesmo jeito e para um teste garantir que
nenhum campo fique sem explicação. Aceitam Markdown (negrito e listas). Cada texto diz, na ordem:
o que é, como preencher e — quando existir — a simplificação que o programa adota.
"""

from __future__ import annotations

from core.column_design import ESPESSURA_MIN_ANGLO


def _mm(valor: float) -> str:
    """Espessura mínima com vírgula decimal, como no texto da Anglo."""
    return f"{valor:g}".replace(".", ",")


AJUDA: dict[str, str] = {
    # ------------------------------------------------------------------ seções
    "sec_1": (
        "Escolha a norma e o aço. Não sabe qual norma usar? Comece pela **NBR 8800:2008** e use "
        "**Comparar normas**, nos resultados, para ver a mesma coluna nas outras duas."
    ),
    "sec_2": (
        "Descreva a seção transversal da coluna: um perfil de catálogo, uma forma simples "
        "(barra, tubo, I ou U por dimensões) ou, se não houver outro jeito, as propriedades "
        "diretamente.\n\n"
        "**Simplificação:** tubo retangular com cantos vivos (o raio de dobra é ignorado); os "
        "perfis de catálogo usam as propriedades da tabela, não a geometria idealizada."
    ),
    "sec_3": (
        "A coluna pode se curvar de dois jeitos: em torno de **x** (o eixo forte) e em torno de "
        "**y** (o eixo fraco). Cada um tem o seu comprimento destravado e a sua condição de apoio "
        "— o programa verifica os dois de uma vez e o pior governa.\n\n"
        "**Simplificação:** o K da Tabela E.1 vale para pórticos de pré-projeto. Na análise direta "
        "(Projeto 2024 e AISC) o comprimento efetivo é o real (K = 1) e a estrutura é analisada "
        "com imperfeições — isso é feito na análise da estrutura, não aqui."
    ),
    "sec_4": (
        "Informe os esforços **de cálculo** (já majorados) que chegam à coluna: a força de "
        "compressão e os momentos em torno de x e y.\n\n"
        "**Simplificação:** os momentos são de **1ª ordem**. O efeito local da compressão sobre "
        "a flexão (B₁) é calculado aqui; o efeito global do pórtico (B₂) vem da análise da "
        "estrutura."
    ),
    "sec_5": (
        "Use só se uma mão-francesa (escora inclinada) descarrega uma força na coluna. A parte "
        "horizontal flete a coluna e a vertical comprime. O momento calculado é somado ao do eixo "
        "que ela flete."
    ),
    "sec_6": (
        "Exigências do critério de projeto da Anglo American (AA-BR-DPST-DR-0001): esbeltez "
        "máxima de 200 na compressão (item 8.3) e espessura mínima das partes (item 8.8). "
        "A esbeltez é sempre verificada; a espessura do perfil da coluna entra sozinha quando ele "
        "é um I ou U."
    ),
    # ------------------------------------------------------------------ 1. norma e material
    "norma": (
        "Define as regras (fórmulas e coeficientes) da verificação. As três calculam do mesmo "
        "jeito a flambagem global, mas diferem na flambagem local e nos coeficientes:\n\n"
        "- **NBR 8800:2008**: a vigente. Flambagem local pelo fator Q; resistência dividida por "
        "γ_a1 = 1,10.\n"
        "- **Projeto NBR 8800:2024**: a revisão. Flambagem local pela área efetiva A_ef.\n"
        "- **AISC 360-16**: norma americana. A_ef e resistência multiplicada por φ = 0,90."
    ),
    "material": (
        "Escolha um aço do projeto ou do catálogo só para preencher a resistência f_y. "
        "**Entrada manual** deixa você digitar o valor."
    ),
    "fy": (
        "Resistência ao escoamento do aço (f_y). Ex.: **ASTM A36 = 250 MPa**; ASTM A572 "
        "grau 50 = 345 MPa. Está no certificado do material ou na ficha do aço."
    ),
    "E": (
        "Módulo de elasticidade: a rigidez do aço. Para o aço estrutural vale "
        "**200 000 MPa** (NBR 8800, 4.5.2.9). Só mude para outro material."
    ),
    "G": (
        "Módulo de cisalhamento: a rigidez do aço à torção. Para o aço vale **77 000 MPa** "
        "(NBR 8800, 4.5.2.9). Entra na torção e na flambagem lateral."
    ),
    "m_resistencia": (
        "Fator que reduz a resistência por segurança: **1/γ_a1 = 1/1,10** nas normas brasileiras "
        "(Tabela 3, escoamento e instabilidade) e **φ = 0,90** no AISC."
    ),
    # ------------------------------------------------------------------ 2. seção
    "tipo_secao": (
        "Como você vai descrever a seção:\n\n"
        "- **Perfil de aço (catálogo)**: escolhe um perfil da tabela (W, HP, I, U, T, tubos, "
        "barras). É o caminho mais seguro.\n"
        "- **Circular / retangular maciça, tubo, I ou U**: digita só as dimensões.\n"
        "- **Área e raio de giração**: só para a flambagem por flexão; a norma não pode ser "
        "aplicada por completo (veja o aviso).\n"
        "- **Seção genérica**: você informa todas as propriedades e as paredes."
    ),
    "perfil": (
        "Perfil da tabela do programa. As propriedades (área, inércias, J, C_w, W e Z) vêm da "
        "tabela, não da geometria idealizada."
    ),
    "soldado": (
        "Marque se o perfil I ou U é **soldado** (chapas soldadas), não laminado. Muda o tipo da "
        "mesa na flambagem local (Tabela 4) e a espessura mínima da Anglo (8.8)."
    ),
    "dim_d_circ": "Diâmetro da barra circular maciça, em mm.",
    "dim_b_ret": "Dimensão da barra retangular maciça ao longo de **x**, em mm (a largura).",
    "dim_h_ret": (
        "Dimensão da barra retangular maciça ao longo de **y**, em mm (a altura). Se for maior "
        "que a largura, o eixo x é o forte."
    ),
    "dim_D_tubo": "Diâmetro externo do tubo circular, em mm.",
    "dim_t_tubo": (
        "Espessura da parede do tubo, em mm. Tubo muito fino (D/t > 0,45·E/f_y) flamba "
        "localmente antes de qualquer cálculo: a norma não cobre e o programa bloqueia."
    ),
    "dim_B_tr": "Largura externa do tubo retangular (ao longo de x), em mm.",
    "dim_H_tr": "Altura externa do tubo retangular (ao longo de y), em mm.",
    "dim_t_tr": (
        "Espessura da parede do tubo retangular, em mm.\n\n"
        "**Simplificação:** cantos vivos; a largura plana da parede é o lado menos 3·t "
        "(AISC B4.1b)."
    ),
    "dim_d_perfil": "Altura total do perfil (de fora a fora das mesas), em mm.",
    "dim_bf": "Largura da mesa, em mm.",
    "dim_tf": "Espessura da mesa, em mm.",
    "dim_tw": "Espessura da alma, em mm.",
    "direta_A": "Área da seção transversal, em mm².",
    "direta_rx": (
        "Raio de giração em torno de x, em mm: √(I/A). Quanto maior, menos esbelta a coluna."
    ),
    "direta_mesmo_raio": (
        "Marque se a seção tem o mesmo raio de giração nos dois eixos (barra circular, "
        "tubo, perfil quadrado). Desmarque para informar ry."
    ),
    "direta_ry": "Raio de giração em torno de y, em mm.",
    "direta_cx": (
        "Distância do centroide à fibra mais afastada, no eixo x (meia altura numa seção "
        "simétrica). Só serve para a flexão; **0 = não informado**."
    ),
    "direta_cy": (
        "Distância do centroide à fibra mais afastada, no eixo y (meia largura numa seção "
        "simétrica). Só serve para a flexão; **0 = não informado**."
    ),
    "gen_nome": "Nome da seção, só para identificar nos resultados e no memorial.",
    "gen_A": "Área da seção transversal, em mm².",
    "gen_Ix": "Momento de inércia em torno do eixo x (o forte), em mm⁴.",
    "gen_Iy": "Momento de inércia em torno do eixo y (o fraco), em mm⁴.",
    "gen_J": "Constante de torção de Saint-Venant, em mm⁴. **0 = não informada.**",
    "gen_Cw": "Constante de empenamento, em mm⁶. **0 = não informada** (seções fechadas e maciças).",
    "gen_x0": (
        "Posição do centro de cisalhamento em relação ao centroide, no eixo x, em mm. "
        "Zero se a seção é simétrica em relação a y."
    ),
    "gen_y0": (
        "Posição do centro de cisalhamento em relação ao centroide, no eixo y, em mm. "
        "Zero se a seção é simétrica em relação a x."
    ),
    "gen_Wx": (
        "Módulo de resistência elástico em x (I/c), em mm³. **0 = não informado.** Sem W e Z a "
        "flexão só pode ser verificada com o M_Rd informado por você."
    ),
    "gen_Wy": "Módulo de resistência elástico em y, em mm³. **0 = não informado.**",
    "gen_Zx": "Módulo de resistência plástico em x, em mm³. **0 = não informado.**",
    "gen_Zy": "Módulo de resistência plástico em y, em mm³. **0 = não informado.**",
    "gen_torcao": (
        "Marque se a torção ou a flexo-torção pode governar nesta seção (perfil aberto de "
        "parede fina, como U, T, cantoneira). Desmarque para seções fechadas e maciças, em "
        "que a torção não governa."
    ),
    "paredes": (
        "As “paredes” (chapas) da seção, para a **flambagem local**. Cada linha é um tipo de "
        "parede:\n\n"
        "- **Tipo**: AL = livre numa borda (mesa, aba); AA = apoiada nas duas (alma, parede de "
        "tubo).\n"
        "- **Grupo** (Tabela 4): 1 parede de tubo retangular, 2 alma, 3 aba de cantoneira, "
        "4 mesa laminada, 5 mesa soldada, 6 talão de T.\n"
        "- **b** e **t**: largura e espessura, em mm. **n**: quantas iguais existem.\n"
        "- **k_c**: só no grupo 5, entre 0,35 e 0,76."
    ),
    "par_quantidade": (
        "Quantos tipos diferentes de parede a seção tem (por exemplo, mesa e alma = 2). "
        "**0 = sem paredes informadas**: a flambagem local não é verificada e o resultado fica "
        "em ALERTA, a menos que você confirme que a seção é compacta."
    ),
    "par_tipo": (
        "O tipo e o grupo da parede na Tabela 4, que definem o limite b/t:\n\n"
        "- **AA** (apoiada nas duas bordas): grupo 1 parede de tubo retangular, 2 alma.\n"
        "- **AL** (uma borda livre): grupo 3 aba de cantoneira, 4 mesa laminada, "
        "5 mesa soldada, 6 talão de T."
    ),
    "par_b": (
        "Largura da parte plana da parede, em mm. Mesa de I: metade da largura (a borda livre "
        "é a ponta). Alma: altura entre as mesas."
    ),
    "par_t": "Espessura da parede, em mm.",
    "par_n": "Quantas paredes iguais existem (ex.: 4 meias-mesas num perfil I).",
    "par_kc": (
        "Coeficiente k_c da mesa de perfil soldado, entre 0,35 e 0,76: "
        "4/√(h/t_w), com h/t_w da alma."
    ),
    "confirma_compacta": (
        "Sem as paredes e as constantes de torção, o programa não consegue verificar a "
        "flambagem local nem a torção desta seção. Marque **só se você já conferiu, fora do "
        "programa,** que a seção é compacta e que a torção não governa. Sem a marca, o "
        "resultado fica em **ALERTA** — nunca em OK."
    ),
    "m_area": "Área da seção transversal.",
    "m_rx": "Raio de giração em torno de x: √(I_x/A).",
    "m_ry": "Raio de giração em torno de y: √(I_y/A).",
    "m_J": "Constante de torção de Saint-Venant.",
    # ------------------------------------------------------------------ 3. comprimentos e apoio
    "L_total": (
        "Altura real da coluna, de apoio a apoio. É o comprimento usado no efeito local da "
        "compressão sobre a flexão (B₁, com K = 1) e o limite da altura da mão-francesa."
    ),
    "mesmo_L": (
        "Ligado: o comprimento destravado é o comprimento total nos dois eixos. Desligue se "
        "há travamento lateral em um dos planos (ex.: viga que trava só o eixo fraco) e "
        "informe cada comprimento."
    ),
    "Lx": (
        "Distância entre os pontos que impedem a coluna de se curvar **em torno de x** (o eixo "
        "forte, perpendicular à alma de um I ou U). Ex.: do piso até a viga que trava a coluna "
        "nesse plano."
    ),
    "Ly": (
        "Distância entre os pontos que impedem a coluna de se curvar **em torno de y** (o eixo "
        "fraco, paralelo à alma). Costuma ser o menor trecho entre contraventamentos laterais "
        "ou mãos-francesas."
    ),
    "apoio_x": (
        "Como as pontas da coluna estão presas no plano da flexão em torno de x. **Biapoiada** "
        "= pontas livres para girar (K = 1); **engastada** = ponta que não gira; **em balanço** "
        "= um lado livre. A tabela dá o fator K de cada caso (Tabela E.1). Escolha "
        "“Informar K” para digitar o valor."
    ),
    "apoio_y": (
        "Como as pontas da coluna estão presas no plano da flexão em torno de y. É o mesmo "
        "raciocínio de x, mas o plano costuma ser outro: a mão-francesa e o contraventamento "
        "mudam o apoio. Escolha “Informar K” para digitar o valor."
    ),
    "k_recomendado": (
        "Ligações reais nunca são um engaste ou um pino perfeitos. A Tabela E.1 recomenda, para "
        "projeto, K maior que o teórico nos casos com engaste: 0,65 em vez de 0,50, 0,80 em "
        "vez de 0,70, 1,2 em vez de 1,0 e 2,1 em vez de 2,0. Ligado = usa o recomendado."
    ),
    "Kx_manual": (
        "Fator de comprimento efetivo K para a flexão em torno de x. K·L é o comprimento da "
        "“meia onda” em que a coluna realmente flamba. 1,0 = biapoiada."
    ),
    "Ky_manual": "Fator de comprimento efetivo K para a flexão em torno de y.",
    "kz_ativar": (
        "A coluna também pode **girar em torno do próprio eixo** (torção). Sem travamento "
        "contra esse giro, o programa usa o maior comprimento efetivo de flexão. Ligue se a "
        "ligação ou um travamento impede o giro de forma diferente e informe K_z e L_z."
    ),
    "Kz": "Fator K da torção: 1,0 = as duas pontas impedem o giro mas deixam o empenamento livre.",
    "Lz": "Distância entre os pontos que impedem o giro da coluna em torno do próprio eixo, em mm.",
    # ------------------------------------------------------------------ 4. esforços
    "modo_carga": (
        "**Cargas características**: você informa o peso próprio e a sobrecarga e o programa "
        "majora (γ_g·N_g + γ_q·N_q).\n\n"
        "**N_Sd já de cálculo**: você traz o valor das combinações de ações (NBR 8681)."
    ),
    "ng": "Carga permanente (peso próprio e fixas) que a coluna recebe, **sem majorar**, em kN.",
    "cat_g": (
        "Define o coeficiente γ_g que multiplica a carga permanente (Tabela 1). Estrutura "
        "metálica com peso conhecido: 1,25. Incerteza maior (equipamentos, adições no local): "
        "1,40 ou 1,50."
    ),
    "nq": "Carga variável (sobrecarga, equipamentos, vento) que a coluna recebe, **sem majorar**, em kN.",
    "cat_q": (
        "Define o coeficiente γ_q que multiplica a carga variável (Tabela 1). Sobrecarga em "
        "geral: 1,50. Vento: 1,40."
    ),
    "nsd": (
        "Força de compressão de cálculo N_Sd, em kN, **já majorada** pelas combinações de "
        "ações (NBR 8681 / NBR 8800, 4.7)."
    ),
    "Mx": (
        "Momento fletor de cálculo em torno de **x**, de 1ª ordem, em kN·m, além do que a "
        "excentricidade e a mão-francesa geram. Pode deixar 0."
    ),
    "My": (
        "Momento fletor de cálculo em torno de **y**, de 1ª ordem, em kN·m, além do que a "
        "excentricidade e a mão-francesa geram. Pode deixar 0."
    ),
    "ex": (
        "Excentricidade da força em relação ao centroide, no plano que flete **x**, em mm. "
        "Gera um momento M = N_Sd·e que entra na interação. 0 = força no centro."
    ),
    "ey": (
        "Excentricidade da força em relação ao centroide, no plano que flete **y**, em mm. "
        "Gera um momento M = N_Sd·e que entra na interação. 0 = força no centro."
    ),
    "diagrama_x": (
        "A forma do diagrama de momento em x muda o coeficiente C_m do efeito B₁:\n\n"
        "- **Não informado**: C_m = 1,0, que é conservador.\n"
        "- **Momentos nas pontas**: informe M₁/M₂ e C_m = 0,6 − 0,4·M₁/M₂.\n"
        "- **Força transversal entre os apoios** (carga distribuída ou pontual na barra): "
        "C_m = 1,0."
    ),
    "diagrama_y": (
        "A forma do diagrama de momento em y muda o coeficiente C_m do efeito B₁. Mesmas "
        "opções de x: não informado (C_m = 1,0), momentos nas pontas (informe M₁/M₂) ou força "
        "transversal entre os apoios (C_m = 1,0)."
    ),
    "razao_x": (
        "M₁/M₂ em x: M₁ é o **menor** e M₂ o **maior** dos momentos nas pontas (em módulo). "
        "**Positivo** quando os momentos giram a barra em sentidos opostos (curvatura reversa, "
        "mais favorável); **negativo** quando giram no mesmo sentido (curvatura simples)."
    ),
    "razao_y": (
        "M₁/M₂ em y: M₁ é o **menor** e M₂ o **maior** dos momentos nas pontas (em módulo). "
        "Positivo = curvatura reversa; negativo = curvatura simples."
    ),
    "Lb": (
        "Distância entre os pontos em que a **mesa comprimida** é impedida de se deslocar para "
        "o lado (flambagem lateral com torção, FLT), na flexão em torno de x. **0 = igual ao "
        "comprimento destravado de y.**"
    ),
    "cb_modo": (
        "C_b corrige a flambagem lateral quando o momento não é igual ao longo da barra. "
        "Informe o valor (1,0 = momento constante, conservador) ou deixe o programa calcular "
        "pelos momentos em quatro pontos do trecho."
    ),
    "cb": (
        "Fator C_b da flambagem lateral. 1,0 é o caso de momento constante e é conservador. "
        "Vai até 3,0. **Em perfil U pela NBR 2008, o programa usa 1,0.**"
    ),
    "cb_Mmax": "Maior momento (em módulo) no trecho entre travamentos, em kN·m.",
    "cb_MA": "Momento (em módulo) a **¼** do trecho entre travamentos, em kN·m.",
    "cb_MB": "Momento (em módulo) no **meio** do trecho entre travamentos, em kN·m.",
    "cb_MC": "Momento (em módulo) a **¾** do trecho entre travamentos, em kN·m.",
    "mrd_x_ativar": (
        "Use quando o programa não tem rotina de momento resistente para a seção (tubo "
        "não compacto, T, seção genérica). Você calcula M_Rd fora do programa e informa; o "
        "programa o usa na interação e deixa isso registrado."
    ),
    "mrd_x": "Momento resistente de cálculo M_x,Rd calculado por você, em kN·m.",
    "mrd_y_ativar": (
        "Use quando o programa não tem rotina de momento resistente em y para a seção. Você "
        "calcula M_Rd fora do programa e informa; o programa o usa na interação e deixa isso "
        "registrado."
    ),
    "mrd_y": "Momento resistente de cálculo M_y,Rd calculado por você, em kN·m.",
    # ------------------------------------------------------------------ 5. mão-francesa
    "mf_incluir": (
        "Liga a mão-francesa nesta verificação. Sem ela, o momento da escora **não** entra nos "
        "cálculos. O cisalhamento (5.4.3) não é verificado aqui e o programa avisa."
    ),
    "mf_forca": (
        "Força axial na barra da mão-francesa (compressão ou tração), vinda da reação da viga "
        "ou do console que ela suporta, em kN."
    ),
    "mf_gamma": "Majoração da força. Se ela já veio majorada das combinações, escolha γ = 1,00.",
    "mf_angulo": (
        "Ângulo entre a barra da mão-francesa e o eixo da coluna: 45° é o usual. "
        "H = F·sen θ (flete) e V = F·cos θ (comprime)."
    ),
    "mf_altura": (
        "Distância da base da coluna ao ponto onde a mão-francesa é ligada. É o braço da "
        "componente horizontal."
    ),
    "mf_vinculo": (
        "Como a coluna está presa no plano da mão-francesa. Define como a força horizontal H "
        "vira momento: **engaste na base** (M = H·a), **pino-pino** (M = H·a·(L − a)/L) ou "
        "engaste com o topo apoiado."
    ),
    "mf_eixo": (
        "Eixo da coluna que a mão-francesa flete. Mão-francesa no plano da alma de um I flete "
        "o eixo forte, x."
    ),
    "mf_exc": (
        "Distância do eixo da coluna à face onde a mão-francesa chega (meia altura do perfil, "
        "por padrão). A força vertical V vezes essa distância é somada ao momento. 0 se a força "
        "passa pelo eixo."
    ),
    "mf_somar_v": (
        "Marque só se o N_Sd acima **ainda não inclui** a reação vertical V que a "
        "mão-francesa traz para a coluna."
    ),
    "mf_metrica": "Valor calculado a partir da força, do ângulo e do vínculo informados.",
    # ------------------------------------------------------------------ 6. critério Anglo
    "anglo_chapa": (
        "Espessura de uma chapa de ligação ou enrijecedor ligado a esta coluna, em mm. "
        f"A Anglo (8.8) exige mínimo de {_mm(ESPESSURA_MIN_ANGLO['chapa_ligacao_enrijecedor'])} mm. "
        "**0 = não verificar.**"
    ),
    "anglo_cantoneira": (
        "Espessura de uma cantoneira ligada a esta coluna, em mm. A Anglo (8.8) exige mínimo "
        f"de {_mm(ESPESSURA_MIN_ANGLO['cantoneira'])} mm. **0 = não verificar.**"
    ),
    "anglo_placa": (
        "Espessura da placa de base desta coluna, em mm. A Anglo (8.8) exige mínimo de "
        f"{_mm(ESPESSURA_MIN_ANGLO['placa_base'])} mm. **0 = não verificar.**"
    ),
    "anglo_espessura_auto": (
        "A espessura mínima do perfil da coluna é verificada sozinha: o menor entre a mesa e a "
        "alma contra o mínimo da Anglo para perfil laminado ou soldado."
    ),
    # ------------------------------------------------------------------ resultados
    "res_resumo": "Visão geral: se a coluna atende, quanto da capacidade ela usa e o que governa.",
    "res_status": (
        "**OK**: todas as verificações passam. **NÃO OK**: alguma reprova ou foi bloqueada. "
        "**ALERTA**: nada reprova, mas ficou algo que o programa não consegue conferir e que "
        "você precisa revisar."
    ),
    "res_aproveitamento": (
        "Maior relação entre o esforço atuante e a resistência, entre as verificações de "
        "resistência. Acima de 100% a coluna não atende."
    ),
    "res_nc": "Resistência de cálculo à compressão axial: o quanto a coluna aguenta de força.",
    "res_nsd": "Força de compressão de cálculo que atua na coluna (mais V da mão-francesa, se somada).",
    "res_lx": "Índice de esbeltez λ = K·L/r para a flexão em torno de x. Quanto maior, mais fácil flambar.",
    "res_ly": "Índice de esbeltez λ = K·L/r para a flexão em torno de y. O limite é 200 (Anglo 8.3).",
    "res_ne": (
        "Força crítica elástica de flambagem N_e: a menor entre a flexão em x, a flexão em y, "
        "a torção e a flexo-torção. O modo que a produziu está no “?” abaixo do valor."
    ),
    "res_chi": (
        "Fator χ de redução por flambagem global (0 a 1): quanto menor, mais a esbeltez derruba "
        "a resistência."
    ),
    "res_q": (
        "**NBR 2008**: fator Q = Q_s·Q_a, que reduz a resistência quando as paredes são "
        "esbeltas. **Projeto 2024 e AISC**: A_ef/A_g, a fração da área que trabalha. "
        "1,0 = sem flambagem local."
    ),
    "res_b1": (
        "Fator B₁ (≥ 1) que amplifica o momento porque a compressão aumenta a flexão ao longo "
        "da barra (efeito P-δ local). Quanto mais perto de N_e, maior."
    ),
    "res_mrd": (
        "Momento resistente de cálculo: o menor entre flambagem lateral (FLT), da mesa (FLM) e "
        "da alma (FLA), limitado a 1,5·W·f_y. Quando o valor foi informado por você, aparece "
        "“(informado)”."
    ),
    "res_interacao": (
        "Equação única de interação N + Mx + My: N/N_Rd + 8/9·(Mx/MxRd + My/MyRd) ≤ 1,0 (e "
        "N/(2·N_Rd) + Mx/MxRd + My/MyRd se N/N_Rd < 0,2). Os dois momentos entram **na mesma** "
        "conta, não em duas separadas."
    ),
    "res_tabela": (
        "Cada linha é uma verificação, do esforço aos limites da norma. Passe o mouse no "
        "título de cada coluna para saber o que ela mostra. Linhas “INFO” só apresentam valores "
        "intermediários."
    ),
    "res_regras": (
        "As regras de cálculo desta verificação, à vista: como o efeito B₁ é calculado, em que a "
        "flambagem lateral difere entre as três normas e as espessuras mínimas da Anglo (8.8)."
    ),
    "res_paredes": (
        "Cada parede da seção com sua esbeltez b/t e o limite da Tabela 4. Se b/t passa do "
        "limite, a parede é **esbelta** e flamba localmente: a resistência é reduzida."
    ),
    "btn_csv": "Baixa a tabela de verificações em um arquivo CSV para abrir no Excel.",
    "btn_comparar": (
        "Mostra a mesma coluna nas três normas lado a lado. Uma norma que bloqueia o "
        "cálculo aparece com o motivo, não some."
    ),
    "reg_registrar": (
        "Grava esta verificação no projeto ativo e a leva ao memorial, com a tabela completa."
    ),
    "reg_comparar": "Guarda este cenário para comparar com outros (outro perfil, outro comprimento).",
}
