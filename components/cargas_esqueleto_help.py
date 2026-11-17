"""Textos dos “?” da página Cargas do esqueleto, em linguagem simples (um teste exige cada um)."""

from __future__ import annotations

from core.cargas_esqueleto import PISO_TIPICO

AJUDA: dict[str, str] = {
    "sec_eixos": (
        "A planta da estrutura pelos eixos, como no desenho: as linhas em X levam números (1, 2, "
        "3…) e as em Y, letras (A, B…). Em cada cruzamento há um pilar; em cada eixo, uma viga."
    ),
    "eixos_x": (
        "Posição dos eixos 1, 2, 3… ao longo de X, em metros, separadas por ponto e vírgula. "
        "Ex.: 0; 6; 12 para dois vãos de 6 m."
    ),
    "eixos_y": (
        "Posição dos eixos A, B, C… ao longo de Y, em metros, separadas por ponto e vírgula. "
        "Ex.: 0; 3 para um vão de 3 m."
    ),
    "niveis": (
        "Um nível por linha. Vigas paralelas a: a direção das vigas em que o piso apoia (o piso "
        "vence o vão na outra direção). Vão máximo do piso: o maior vão que a grade ou a chapa "
        "aguenta — o programa põe vigas secundárias até chegar nele. GC: as bordas com "
        f"guarda-corpo (X− é o lado do eixo 1, Y− o do eixo A). Piso usual: {PISO_TIPICO}."
    ),
    "sec_fora_do_modelo": (
        "Tudo o que existe na obra mas não está no esqueleto do SolidWorks. O programa transforma "
        "cada coisa em carga nas barras, no caso certo."
    ),
    "guarda_corpo": (
        "Peso do guarda-corpo com o rodapé, por metro (tubular usual: 0,15 a 0,30 kN/m). Vai nas "
        "vigas das bordas marcadas. A força horizontal de 1 kN/m no topo é verificação do próprio "
        "guarda-corpo, não carga do esqueleto."
    ),
    "acrescimo": (
        "Ligações, chapas, enrijecedores e parafusos não estão no esqueleto. O acréscimo (5 a 10 % "
        "é o usual) multiplica a gravidade do caso PP no SolidWorks."
    ),
    "temperatura": (
        "Liga os casos de temperatura de ±10 °C nas barras (critério Anglo 5.8). Vem ligado quando "
        "a base técnica usa o critério Anglo."
    ),
    "escadas": (
        "Uma escada por linha. Ela chega no nível dado, numa borda e num trecho dessa borda entre "
        "eixos (1 = o primeiro). O apoio de cima leva metade do peso e da sobrecarga, em duas "
        "forças (as longarinas); o de baixo vai à fundação. Sobrecarga Anglo de escadas: 3 kN/m²."
    ),
    "equipamentos": (
        "Um equipamento por linha: peso vazio (caso EQ), conteúdo em operação (EO) e o impacto "
        "(IM) em % do peso em operação — Anglo 5.3: 20 % em máquinas rotativas, 100 % vertical e "
        "25 % horizontal em vibratórios. As forças saem iguais em cada apoio; Local diz onde estão."
    ),
    "tubulacoes": (
        "Tubulação, bandeja de cabos ou outra carga por metro apoiada ao longo de um eixo, num "
        "nível. Caso PE para o peso vazio; EO para o conteúdo em operação."
    ),
    "sec_cargas": (
        "As cargas que cada barra do esqueleto recebe, caso a caso, características (sem "
        "coeficiente). A conferência mostra que a soma bate com o que entrou."
    ),
    "res_casos": "A resultante de cada caso (kN): tudo o que o caso coloca no esqueleto.",
    "nivel_desenho": "O nível mostrado na planta.",
    "caso_desenho": "O caso cujas cargas aparecem na planta e na tabela.",
    "res_desenho": (
        "A planta do nível: vigas com carga do caso em laranja, com o valor em kN/m; secundárias "
        "mais finas; guarda-corpo tracejado; a seta azul é o vão do piso."
    ),
    "res_barras": (
        "Cada barra com a carga distribuída do caso (kN/m, para baixo) e de onde ela vem: piso × "
        "largura de influência, guarda-corpo, tubulação. É o valor a aplicar na barra."
    ),
    "res_forcas": "Forças concentradas do caso: escadas e equipamentos, em cada apoio.",
    "res_conferencia": (
        "Para cada item, o que entrou (área × carga, perímetro × carga, pesos) e o que foi aplicado "
        "nas barras. Tudo precisa conferir."
    ),
    "sec_enviar": (
        "Grava os dados no projeto e manda as cargas para o Plano de cargas, de onde sai a "
        "planilha para o SolidWorks."
    ),
    "btn_gravar": "Grava só os dados desta página no projeto ativo.",
    "btn_tirar_grade": (
        "Tira do plano de cargas as linhas que a grade de eixos desta página mandou antes (barras "
        '"N1 · eixo A…" que o seu modelo não tem). As outras cargas das mesmas ações ficam.'
    ),
    "btn_enviar": (
        "Grava os dados e substitui no Plano de cargas os casos que esta página gera (PE, SC, EQ, "
        "EO, IM e a temperatura), além de pôr o acréscimo de ligações na gravidade do PP."
    ),
    "btn_csv": "As cargas de todos os casos em CSV (abre no Excel).",
    "sec_modelo": (
        "O …_esqueleto.csv da macro do SolidWorks: as barras e as chapas do seu modelo. Com ele, a "
        "página lê sozinha o que é piso, patamar e escada, acha as vigas que apoiam cada chapa e "
        "monta a carga de cada viga. Sem ele, a página trabalha pela grade de eixos."
    ),
    "sec_entendeu": (
        "A leitura que o programa fez do esqueleto: quantos pilares, vigas e diagonais, os níveis "
        "de piso (pela altura das chapas) e o tipo de cada chapa. Confira aqui e no desenho 3D; o "
        "que estiver errado se corrige na tabela."
    ),
    "res_barras_modelo": (
        "Pela posição de cada barra: em pé é pilar, deitada e alinhada é viga, inclinada é "
        "diagonal. A barra inclinada que apoia um lance de escada é longarina."
    ),
    "res_niveis": (
        "Os níveis são as alturas das chapas em nível, medidas do ponto mais baixo do modelo. As "
        "chapas inclinadas são lances de escada e ficam entre os níveis."
    ),
    "res_chapas": (
        "Uma linha por chapa de piso do esqueleto. Tipo: piso, patamar, escada ou sem carga (a "
        "chapa que não é piso). SC: a sobrecarga dela, na projeção horizontal. Peso informado: "
        "só vale quando o peso do piso é informado. Apoio: dois sentidos (a carga vai para a viga "
        "mais perto, nos quatro lados) ou um sentido (só as vigas de uma direção apoiam, como na "
        "grade de piso)."
    ),
    "peso_do_piso": (
        "De onde sai o peso do piso no caso PE. Pelo volume: o peso de aço de cada chapa do "
        "modelo. Informado: o valor da coluna Peso informado (use para grade de piso ou outro "
        "material). Já está no PP: quando a gravidade do seu estudo já pega as chapas, para não "
        "somar duas vezes."
    ),
    "so_no_trecho": (
        "Quando a chapa cobre só uma parte da viga. Desligado: a carga sai uniforme na viga "
        "inteira, com o mesmo total. Ligado: a carga sai só no trecho coberto, com o começo e o "
        "fim medidos da ponta inicial da viga; o momento fica mais certo, mas no SolidWorks a "
        "carga precisa ser aplicada só nesse trecho."
    ),
    "outros_casos": (
        "Para um caso que não é PE nem SC (por exemplo, uma sobrecarga de manutenção): o valor "
        "em kN/m² vai em todas as chapas com carga, pelas mesmas vigas."
    ),
    "sec_3d": (
        "O esqueleto como o programa o leu, para conferir antes de enviar. Se uma viga de piso "
        "aparece sem carga ou uma chapa com o tipo errado, corrija na tabela acima ou no modelo."
    ),
    "cor_3d": (
        "O que é cada peça: pilares, vigas com piso, diagonais e o tipo de cada chapa. Área que "
        "cada viga recebe: a chapa pintada com a cor da viga que leva aquela parte. Carga do "
        "caso: as vigas coloridas pela carga em kN/m, com as setas."
    ),
    "vista_3d": "De onde olhar o modelo: em perspectiva, de cima, de frente ou de lado.",
    "giro_3d": "Gira o modelo em torno do eixo vertical, em graus.",
    "caso_3d": "O caso cujas cargas aparecem nas vigas.",
    "sec_vigas": (
        "A carga que cada viga do modelo recebe do piso, caso a caso, já em kN/m para aplicar no "
        "Simulation. O guarda-corpo entra no envio, mas tem a tabela dele na seção 3."
    ),
    "res_vigas_modelo": (
        "A carga de cada viga no caso: kN/m na viga inteira ou só no trecho (coluna Onde), o "
        "total, o trecho em que a chapa encosta e de que chapas vem. Aplique no Simulation no "
        "estudo do caso, com o valor característico."
    ),
    "res_conferencia_modelo": (
        "O que as chapas mandam em cada caso contra o que chegou às vigas: os dois têm de ser "
        "iguais. Chapa sem viga embaixo fica fora dos dois lados."
    ),
    "sec_enviar_tudo": (
        "Um envio só: as cargas do piso, o peso do guarda-corpo, o acréscimo das ligações no peso "
        "próprio e a temperatura. A tabela mostra antes o que muda em cada caso do plano."
    ),
    "res_muda": (
        "Cada caso do plano que o envio altera: o total em kN antes e depois, quantas linhas e o "
        "motivo. O que foi lançado à mão no plano não aparece porque não muda."
    ),
    "tirar_grade": (
        "O plano ainda tem cargas de um envio antigo pela grade de eixos, em barras que o modelo "
        "não tem. Ligado, elas saem neste envio: assim a carga não fica em dobro."
    ),
    "btn_enviar_tudo": (
        "Grava as escolhas desta página e atualiza o Plano de cargas com o que a tabela mostra. "
        "Só as linhas do piso e do guarda-corpo são trocadas."
    ),
    "btn_gravar_escolhas": (
        "Grava as escolhas (tipos, cargas e guarda-corpo) sem mexer no Plano de cargas. O vento "
        "barra a barra já passa a usar o guarda-corpo marcado."
    ),
    "btn_abrir_plano": (
        "Vai para o Plano de cargas para ver as linhas que acabaram de chegar: cada viga, o valor "
        "em kN/m e o trecho carregado."
    ),
    "usar_grade": (
        "Abre a forma pela grade de eixos, a que não usa o modelo. Com o esqueleto no projeto, "
        "ela só serve se a grade for a mesma planta do modelo."
    ),
    "arquivo_esqueleto": (
        "O …_esqueleto.csv que a macro do SolidWorks grava na pasta da peça. A macro v5 grava "
        "também o contorno de cada chapa (recortes e aberturas); com a v4, só as chapas "
        "retangulares recebem a carga."
    ),
    "btn_gravar_esqueleto": (
        "Grava o esqueleto no projeto ativo; ele também serve na página Esforços do modelo."
    ),
    "btn_macro_modelo": (
        "Baixa a macro do SolidWorks. Com a peça soldada aberta: Ferramentas › Macro › Nova, cole "
        "o texto e tecle F5. Ela grava a lista de corte e o esqueleto na pasta da peça."
    ),
    "res_modelo": (
        "A área de chapa que recebeu carga (projeção horizontal), quantas vigas a recebem e o "
        "total de cada caso nas vigas."
    ),
    "caso_modelo": "Qual caso mostrar na tabela das vigas.",
    "btn_csv_modelo": "As cargas de todas as vigas, caso a caso, em CSV (abre no Excel).",
    "reg_registrar": (
        "Grava o cálculo no projeto ativo: o memorial ganha o capítulo das ações sobre o esqueleto."
    ),
}
