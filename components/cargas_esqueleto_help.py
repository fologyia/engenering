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
    "btn_enviar": (
        "Grava os dados e substitui no Plano de cargas os casos que esta página gera (PE, SC, EQ, "
        "EO, IM e a temperatura), além de pôr o acréscimo de ligações na gravidade do PP."
    ),
    "btn_csv": "As cargas de todos os casos em CSV (abre no Excel).",
    "sec_modelo": (
        "Com o esqueleto da macro do SolidWorks, a carga do piso (sobrecarga e outras cargas por "
        "área) vai direto para as vigas do seu modelo: cada pedaço de chapa vai para a viga mais "
        "perto que a apoia (área de influência). O resultado é a carga em kN/m de cada viga, caso a "
        "caso, para aplicar no Simulation — e a conferência das reações passa a fechar."
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
    "cargas_por_area": (
        "Cada caso com carga por área (kN/m²), na projeção horizontal — como a NBR 6120 dá a "
        "sobrecarga. Vêm do plano de cargas (ou da base técnica); mude aqui se quiser. O peso das "
        "chapas não entra: ele já está no modelo (gravidade do PP)."
    ),
    "res_chapas": (
        "As chapas de piso do esqueleto (até 60° com a horizontal: piso, patamar, escada). "
        "Desmarque a que não recebe a carga. “Medida por”: contorno (macro v5, com recortes) ou "
        "retângulo (chapa que enche a caixa)."
    ),
    "res_modelo": (
        "A área de chapa que recebeu carga (projeção horizontal), quantas vigas a recebem e o "
        "total de cada caso nas vigas."
    ),
    "caso_modelo": "Qual caso mostrar na tabela das vigas.",
    "res_vigas_modelo": (
        "A carga de cada viga no caso: kN/m uniforme na viga inteira (o total dividido pelo "
        "comprimento), o total, o trecho em que a chapa encosta e de que chapas vem. Aplique no "
        "Simulation no estudo do caso, com o valor característico."
    ),
    "btn_enviar_modelo": (
        "Grava no plano de cargas, para cada caso, uma carga distribuída por viga (substitui as "
        "linhas do caso). A conferência das reações da página Esforços do modelo passa a "
        "comparar com elas."
    ),
    "btn_csv_modelo": "As cargas de todas as vigas, caso a caso, em CSV (abre no Excel).",
    "reg_registrar": (
        "Grava o cálculo no projeto ativo: o memorial ganha o capítulo das ações sobre o esqueleto."
    ),
}
