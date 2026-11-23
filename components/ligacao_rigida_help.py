"""Textos dos "?" da página Ligação rígida viga–pilar, em linguagem simples."""

AJUDA: dict[str, str] = {
    "sec_perfis": (
        "A viga que chega e o pilar que a recebe pela mesa. A viga é soldada a uma chapa "
        "(chapa de extremidade) que é parafusada na mesa do pilar."
    ),
    "familia_viga": "De onde vem o perfil da viga: catálogo W/HP, I laminado ou soldado.",
    "perfil_viga": "A bitola da viga. Ex.: W 410 x 46,1.",
    "familia_pilar": "De onde vem o perfil do pilar: catálogo W/HP, I laminado ou soldado.",
    "perfil_pilar": "A bitola do pilar. Ex.: HP 310 x 79,0 (H).",
    "d": "Altura total do perfil soldado, em mm.",
    "bf": "Largura das mesas do perfil soldado, em mm.",
    "tf": "Espessura das mesas do perfil soldado, em mm.",
    "tw": "Espessura da alma do perfil soldado, em mm.",
    "filete": "Perna do filete mesa–alma do perfil soldado, em mm.",
    "aco_viga": "Aço da viga.",
    "aco_pilar": "Aço do pilar.",
    "aco_chapa": "Aço da chapa de extremidade e dos enrijecedores. Ex.: ASTM A36.",
    "gama_a1": "Coeficiente de ponderação do escoamento (γ_a1). Combinação normal: 1,10.",
    "gama_a2": "Coeficiente de ponderação da ruptura (γ_a2). Combinação normal: 1,35.",
    "sec_esforcos": (
        "Os esforços de cálculo na face do pilar (já majorados). O momento traciona a mesa de "
        "cima da viga, onde ficam os quatro parafusos de fora e de dentro."
    ),
    "M": "Momento fletor de cálculo da viga na face do pilar, em kN·m.",
    "V": "Força cortante de cálculo da viga na ligação, em kN.",
    "N_pilar": (
        "Força normal de compressão de cálculo no pilar, em kN. Acima de 40 % da força de "
        "escoamento, ela reduz a resistência do painel de alma (5.7.7)."
    ),
    "V_pilar": (
        "Cortante de cálculo no pilar junto da ligação, em kN. Ele alivia o painel de alma; na "
        "dúvida, deixe 0 (a favor da segurança)."
    ),
    "outro_lado": "Ligue se chega outra viga do outro lado do pilar, na mesma altura.",
    "M2": (
        "Momento da viga do outro lado, em kN·m. Positivo quando ele também traciona a mesa de "
        "cima (cargas de gravidade nas duas vigas): o painel recebe só a diferença |M₁ − M₂|, e "
        "as duas mesas de baixo empurram a alma dos dois lados."
    ),
    "topo_do_pilar": (
        "Ligue quando a ligação fica no topo do pilar (a menos da altura do pilar até a ponta): "
        "a alma resiste menos (5.7.3 b) e 5.7.4 b))."
    ),
    "sec_parafusos": (
        "Os parafusos e a chapa de extremidade estendida: dois parafusos acima e dois abaixo da "
        "mesa tracionada da viga, em duas colunas afastadas de g."
    ),
    "diametro": "Diâmetro dos parafusos.",
    "grau": "Material dos parafusos (ASTM F3125 A325 ou A490).",
    "rosca_no_plano": (
        "Ligado: a rosca fica no plano de corte (o caso comum, a favor da segurança). Afeta só a "
        "resistência ao corte."
    ),
    "bp": "Largura da chapa de extremidade, em mm. Normalmente entre b_f da viga e b_f + 25 mm.",
    "tp": "Espessura da chapa de extremidade, em mm. Chapa grossa evita o efeito de alavanca.",
    "g": "Gabarito: distância horizontal entre as duas colunas de parafusos, em mm.",
    "pfo": "Distância da face de fora da mesa tracionada até a fileira de fora, em mm.",
    "pfi": "Distância da face de dentro da mesa tracionada até a fileira de dentro, em mm.",
    "de": "Distância da fileira de fora até a borda da chapa, em mm.",
    "simetrica": (
        "Ligado: a chapa estende-se também do lado comprimido, com os mesmos parafusos (serve "
        "para momento nos dois sentidos, como no vento)."
    ),
    "parafusos_comprimidos": (
        "Quantos parafusos ficam do lado comprimido e levam o cortante. Os tracionados não "
        "contam para o cortante."
    ),
    "sec_soldas": "As soldas que unem a viga à chapa de extremidade.",
    "solda_mesa": (
        "Penetração total: a solda tem a resistência da mesa (o usual em ligação de momento). "
        "Filete: um filete de cada lado da mesa, verificado para a força da mesa."
    ),
    "perna_mesa": "Perna dos filetes da mesa, em mm (só quando a solda da mesa é de filete).",
    "perna_alma": "Perna dos filetes da alma (um de cada lado), em mm.",
    "eletrodo": "Classe do eletrodo. E70: f_w = 485 MPa.",
    "sec_reforcos": (
        "Reforços do pilar quando a mesa ou a alma não resistem: enrijecedores de continuidade "
        "alinhados às mesas da viga e chapas de reforço coladas na alma."
    ),
    "enrijecedores": (
        "Ligue para colocar enrijecedores de continuidade (um de cada lado da alma do pilar, na "
        "altura de cada mesa da viga). Eles aumentam a resistência da mesa do pilar e levam a "
        "força que a alma não aguenta."
    ),
    "ts": "Espessura de cada enrijecedor de continuidade, em mm. Pelo menos metade de t_f da viga.",
    "bs": "Largura de cada enrijecedor, da alma até a borda, em mm.",
    "corte": "Recorte no canto do enrijecedor, para livrar o raio do pilar, em mm.",
    "reforco_alma": (
        "Espessura de cada chapa de reforço da alma do pilar (uma de cada lado), em mm. Use 0 "
        "sem chapa. Ela só entra no cisalhamento do painel de alma (5.7.7.2)."
    ),
}
