"""Textos dos “?” da página Ligações estruturais, em linguagem simples (um teste exige cada um)."""

AJUDA: dict[str, str] = {
    "tipo": (
        "Qual ligação verificar: a chapa simples que liga uma viga em outra viga ou num pilar "
        "(NBR 8800), a ligação parafusada de um perfil dobrado de chapa fina (NBR 14762) ou um "
        "grupo de soldas de filete."
    ),
    "norma": (
        "Versão da NBR 8800. A de 2008 é a vigente; o Projeto de revisão de 2024 muda o "
        "coeficiente do corte do parafuso (0,45 e 0,56 em vez de 0,40 e 0,50)."
    ),
    # ------------------------------------------------------------------ chapa simples
    "sec_viga": "A viga que chega na ligação (a apoiada) e onde ela se apoia.",
    "perfil": "O perfil da viga apoiada; a alma dela recebe os parafusos.",
    "aco_viga": "O aço da viga apoiada.",
    "apoio": (
        "Onde a chapa é soldada: na alma de outra viga (viga–viga) ou no pilar, na mesa ou na "
        "alma (viga–pilar)."
    ),
    "t_apoio": (
        "Espessura da parte em que a chapa é soldada (alma da viga principal ou mesa/alma do "
        "pilar), em mm. Entra na perna mínima da solda e no cisalhamento junto à solda."
    ),
    "recorte": (
        "Ligue quando a mesa de cima da viga apoiada é cortada para encaixar na viga principal "
        "(as duas no mesmo nível). Aparecem o colapso por rasgamento e a flexão da alma recortada."
    ),
    "recorte_altura": "Altura do corte na ponta da viga, medida do topo da viga, em mm.",
    "recorte_comprimento": "Comprimento do corte ao longo da viga, a partir da ponta, em mm.",
    "sec_parafusos": "Os parafusos da chapa: diâmetro, grau, quantidade e posição dos furos.",
    "parafuso": "Diâmetro do parafuso; o furo-padrão e a distância mínima à borda vêm dele.",
    "grau": "Grau do parafuso: A325 (alta resistência), A490 ou A307 (comum).",
    "rosca": (
        "Ligado: a rosca fica no plano de corte (o mais comum e a favor da segurança). "
        "Desligado: só a parte lisa do corpo passa pelo plano de corte, e o parafuso resiste mais."
    ),
    "n_parafusos": "Quantos parafusos na linha vertical da chapa.",
    "passo": "Distância entre os centros de dois parafusos vizinhos, em mm (3 diâmetros é o usual).",
    "borda_vertical": "Do centro do furo de cima (e do de baixo) até a borda da chapa, em mm.",
    "a": (
        "Distância da solda (face do apoio) até a linha dos parafusos, em mm. Ela cria o momento "
        "V·a que os parafusos, a chapa e a solda precisam resistir."
    ),
    "borda_horizontal": "Do centro dos furos até a borda livre da chapa, em mm.",
    "borda_alma": "Do centro dos furos até a ponta da viga apoiada, em mm.",
    "topo_alma": (
        "Do centro do parafuso de cima até o topo da alma: o fundo do recorte, ou a face de "
        "baixo da mesa quando não há recorte, em mm."
    ),
    "sec_chapa": "A chapa de ligação e a solda dela no apoio.",
    "t_chapa": "Espessura da chapa de ligação, em mm.",
    "aco_chapa": "O aço da chapa de ligação.",
    "perna": "Tamanho da perna do filete de solda, em mm (os dois lados da chapa).",
    "eletrodo": "Classe do eletrodo: E70 (485 MPa) é o usual; E60 tem 415 MPa.",
    "sec_esforcos": "Os esforços de cálculo (já majorados, combinação ELU) que chegam na ligação.",
    "v_sd": "Força cortante de cálculo na ponta da viga (a reação ELU), em kN.",
    "n_sd": (
        "Força normal de cálculo na viga, em kN: positiva se puxa (tração), negativa se empurra. "
        "Deixe 0 se não houver."
    ),
    "anglo": "Acrescenta as exigências do critério Anglo American para parafusos (item 9.1).",
    # ------------------------------------------------------------------ perfil formado a frio
    "sec_perfil_frio": "O perfil dobrado ligado pela alma e a chapa em que ele se apoia.",
    "perfil_frio": (
        "O perfil dobrado do catálogo, ou “Informado à mão” para digitar espessura, área e x̄ "
        "(por exemplo um U simples que não está no catálogo)."
    ),
    "t_perfil": "Espessura da chapa do perfil, em mm.",
    "area_perfil": "Área da seção do perfil, em mm².",
    "x_perfil": (
        "x̄: distância do centroide do perfil até a face da alma que encosta na chapa, em mm. "
        "Quanto maior, menos eficiente é a ligação só pela alma (C_t menor)."
    ),
    "aco_perfil": "O aço do perfil (os da NBR 14762 Tabela 1, ou sem qualificação estrutural).",
    "t_chapa_frio": (
        "Espessura da chapa (ou cantoneira) que recebe o perfil, em mm. Acima de 4,75 mm ela é "
        "verificada pela NBR 8800."
    ),
    "aco_chapa_frio": "O aço da chapa que recebe o perfil.",
    "sec_parafusos_frio": "Os parafusos e a grade de furos na alma do perfil.",
    "especificacao": (
        "Especificação do parafuso (NBR 14762 Tabela 16). “Sem qualificação estrutural” usa no "
        "máximo 300 MPa de ruptura."
    ),
    "planos": "Quantos planos de corte cada parafuso atravessa: 1 (uma chapa) ou 2 (perfil entre duas chapas).",
    "n_linhas": "Quantas linhas de parafusos, lado a lado, na direção da barra.",
    "n_por_linha": "Quantos parafusos em cada linha, um atrás do outro na direção da barra.",
    "passo_frio": "Distância entre centros de parafusos na direção da barra, em mm.",
    "gabarito": "Distância entre as linhas de parafusos, em mm.",
    "borda_frio": "Do centro do último furo até a ponta do perfil, na direção da barra, em mm.",
    "borda_lateral": "Do centro do furo até a borda da alma (ou da dobra), na outra direção, em mm.",
    "n_sd_frio": "Força axial de cálculo na barra, em kN: positiva na tração, negativa na compressão.",
    "v_sd_frio": "Força de cálculo perpendicular à barra, no plano da ligação, em kN (0 se não houver).",
    "barra_axial": (
        "Ligue para barra de treliça ou contraventamento: a norma pede que a ligação resista a "
        "pelo menos 50 % da força axial que a barra resiste (NBR 14762 10.1)."
    ),
    "n_rd_barra": (
        "Força axial resistente de cálculo da barra, em kN, para a regra dos 50 %. Vazio: a "
        "tração calculada aqui (na compressão, informe a resistência à compressão da barra)."
    ),
    # ------------------------------------------------------------------ solda
    "sec_solda": "O desenho do grupo de filetes, a perna e as chapas soldadas.",
    "arranjo": "Como os filetes estão: um filete, dois paralelos ou o contorno de um retângulo.",
    "comprimento_solda": "Comprimento de cada filete vertical (na direção da força V), em mm.",
    "largura_solda": "Distância entre os filetes paralelos (ou largura do retângulo), em mm.",
    "perna_solda": "Tamanho da perna do filete, em mm.",
    "t1": "Espessura da chapa soldada (a solda corre na borda dela), em mm.",
    "t2": "Espessura da peça que recebe a solda, em mm.",
    "aco_solda": "O aço das chapas soldadas (o mais fraco dos dois).",
    "v_solda": "Força de cálculo ao longo dos filetes verticais, em kN.",
    "n_solda": "Força de cálculo perpendicular aos filetes verticais, no plano, em kN.",
    "m_solda": "Momento de cálculo no plano do grupo de solda (torção do grupo), em kN·m.",
    # ------------------------------------------------------------------ resultados
    "res_status": "OK: tudo passa. NÃO OK: alguma verificação reprova. ALERTA: ressalva para conferir.",
    "res_aproveitamento": "A maior razão solicitante ÷ resistente entre as verificações; até 100 % passa.",
    "res_governa": "A verificação com o maior aproveitamento: é ela que define a ligação.",
    "res_figura": "O desenho da ligação com as medidas informadas, para conferir antes de olhar os números.",
    "res_verificacoes": "Todas as verificações, com a norma e o item, os valores e a situação.",
    "btn_csv": "Baixa a tabela de verificações para abrir no Excel.",
    "reg_registrar": "Grava esta ligação no projeto ativo; ela entra no memorial com a figura e as verificações.",
}
