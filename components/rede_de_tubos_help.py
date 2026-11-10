"""Textos de ajuda ("?") da página Rede de tubos, em linguagem simples."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    "sec_fluido": (
        "O fluido e os limites que a rede precisa atender. A pressão sai em metros de coluna do "
        "próprio fluido (m.c.a. quando é água) e também em kPa."
    ),
    "fluido": "O fluido que corre na rede. Informar serve para outro fluido ou outra temperatura.",
    "rho": "Massa específica do fluido. Água a 20 °C: 998 kg/m³.",
    "mu": "Viscosidade dinâmica do fluido. Água a 20 °C: 1,0 mPa·s, ou seja, 0,0010 Pa·s.",
    "p_min": (
        "A menor pressão aceita em cada nó com a rede em uso. Em rede de abastecimento de água, o "
        "usual é 10 m.c.a. (100 kPa); em processo, a pressão que o equipamento pede."
    ),
    "p_max": (
        "A maior pressão aceita nos nós. Vale a maior entre a estática (rede parada, com o nível "
        "do reservatório mais alto) e a dinâmica. Em rede de abastecimento, o usual é 40 m.c.a. "
        "(400 kPa). Zero desliga a conferência."
    ),
    "v_max": (
        "A maior velocidade aceita nos tubos. Acima de 2 a 3 m/s a água faz barulho, desgasta o "
        "tubo e o golpe de aríete fica forte."
    ),
    "v_min": (
        "Abaixo desta velocidade o programa avisa: água parada deposita sujeira. Zero desliga o "
        "aviso."
    ),
    "sec_desenho": (
        "A rede vista de cima, em metros. Reservatório: clique onde ele fica. Nó: clique onde a "
        "água é consumida; em cima de um tubo, o nó divide o tubo. Tubo: clique num nó e no "
        "seguinte. Selecionar: clique num nó ou num tubo para mudar os dados dele ao lado; "
        "arraste um nó para mover. Delete apaga, Ctrl+Z desfaz. Com a conta feita, o desenho "
        "mostra a vazão, a velocidade e a pressão, e o que não passa fica em vermelho."
    ),
    "sel_nada": (
        "Clique num nó ou num tubo do desenho para ver e mudar os dados dele aqui: cota, nível, "
        "vazão retirada, diâmetro, material, comprimento real, peças e bomba."
    ),
    "exemplo": "Volta o desenho ao exemplo de duas malhas com dois reservatórios.",
    "limpar": "Apaga o desenho inteiro para começar uma rede do zero. Ctrl+Z na prancheta volta.",
    "sec_tabelas": (
        "Os mesmos nós e tubos do desenho, para completar o que ele não dá: cotas, vazões, "
        "diâmetros, materiais e o comprimento real. Para criar ou apagar um nó ou um tubo, use o "
        "desenho."
    ),
    "no_nome": "O nome do nó, que aparece no desenho e nos resultados.",
    "no_tipo": "Reservatório (ou caixa d'água) tem o nível da água fixo; consumo tem a vazão que sai.",
    "no_cota": "A altura do terreno ou do tubo naquele ponto. A pressão é a carga menos a cota.",
    "no_nivel": "Só no reservatório: a altura do nível da água. Vazio, vale a cota.",
    "no_retirada": (
        "A vazão consumida no nó. Negativa é água que entra na rede ali. No reservatório não vale: "
        "ele manda o que a rede pede."
    ),
    "tr_nome": "O nome do tubo.",
    "tr_de": "O nó onde o tubo começa, como foi desenhado.",
    "tr_para": "O nó onde o tubo termina, como foi desenhado.",
    "tr_desenhado": "O comprimento do tubo no desenho, entre os dois nós.",
    "tr_comprimento": (
        "Vazio, vale o comprimento do desenho. Preencha quando o desenho é um esquema fora de "
        "escala ou quando o tubo sobe, desce ou dá voltas que a planta não mostra."
    ),
    "tr_diametro": "O diâmetro interno, em milímetros. Aço Sch 40 DN 100: 102,3 mm.",
    "tr_material": "Dá a rugosidade do tubo novo. Outro usa a rugosidade da tabela.",
    "tr_rugosidade": "Só vale com o material Outro: a rugosidade absoluta, em milímetros.",
    "tr_k": "A soma dos K das curvas, tês e registros do tubo. Zero se não houver peças.",
    "tr_bomba": (
        "A altura que uma bomba no tubo dá, em metros, no sentido em que o tubo foi desenhado. "
        "Zero se não houver bomba."
    ),
    "sec_resultado": (
        "A vazão e a velocidade de cada tubo e a pressão de cada nó, com a rede inteira resolvida "
        "de uma vez. Em cada malha, a soma das perdas fecha em zero."
    ),
    "res_consumo": "Soma das vazões retiradas nos nós de consumo.",
    "res_pressao": "A menor pressão entre os nós de consumo.",
    "res_velocidade": "A maior velocidade entre os tubos.",
    "res_malhas": (
        "O maior erro ao somar as perdas em volta de uma malha. Zero quer dizer que a conta "
        "fechou: é a condição de Hardy Cross."
    ),
    "csv": "Os resultados dos nós e dos tubos em CSV, para abrir no Excel.",
    "registrar": "Grava a rede e os resultados no projeto ativo. Vai para o memorial.",
}
