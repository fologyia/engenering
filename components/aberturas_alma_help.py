"""Textos dos "?" da página Aberturas na alma, em linguagem simples."""

AJUDA: dict[str, str] = {
    "sec_viga": "A viga biapoiada com a carga uniforme de cálculo (já majorada) e o perfil dela.",
    "familia": "De onde vem o perfil: catálogo W/HP, I laminado ou soldado.",
    "perfil": "A bitola da viga.",
    "d": "Altura total do perfil soldado, em mm.",
    "bf": "Largura das mesas do perfil soldado, em mm.",
    "tf": "Espessura das mesas do perfil soldado, em mm.",
    "tw": "Espessura da alma do perfil soldado, em mm.",
    "aco": "Aço da viga.",
    "gama_a1": "Coeficiente de ponderação da resistência (γ_a1). Combinação normal: 1,10.",
    "L": "Vão da viga, de apoio a apoio, em mm.",
    "q": "Carga uniforme de cálculo na viga, em kN/m (já majorada).",
    "Lb": (
        "Comprimento sem travamento lateral da mesa comprimida, em mm, para a flexão da viga "
        "inteira. Use 0 quando a mesa está travada (piso, laje)."
    ),
    "sec_aberturas": (
        "Os furos na alma. Uma linha por abertura: forma, medidas, onde fica ao longo da viga e "
        "quanto o centro sai da meia altura."
    ),
    "tabela_aberturas": (
        "Forma: circular ou retangular. Largura ou D: o diâmetro do furo redondo ou o "
        "comprimento do furo retangular ao longo da viga, em mm. Altura: só no retangular, em mm. "
        "Centro a partir do apoio: do apoio esquerdo ao centro do furo, em mm. Excentricidade: "
        "quanto o centro do furo fica acima (+) ou abaixo (−) da meia altura, em mm."
    ),
}
