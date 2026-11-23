"""Textos dos "?" da página Forças localizadas na alma, em linguagem simples."""

AJUDA: dict[str, str] = {
    "sec_perfil": (
        "O perfil I ou H que recebe a força e o aço dele. Use o catálogo (W e HP com o raio de "
        "concordância da tabela da Gerdau, ou I laminado) ou informe um perfil soldado."
    ),
    "familia": (
        "De onde vem o perfil. W e HP: catálogo da Gerdau, com o raio mesa–alma. I laminado: "
        "abas inclinadas, sem o raio no catálogo (o programa usa k = t_f, a favor da segurança). "
        "Soldado: você informa as chapas."
    ),
    "perfil": "A bitola do catálogo. Ex.: W 410 x 46,1.",
    "d": "Altura total do perfil soldado, de face externa a face externa das mesas, em mm.",
    "bf": "Largura das mesas do perfil soldado, em mm.",
    "tf": "Espessura de cada mesa do perfil soldado, em mm.",
    "tw": "Espessura da alma do perfil soldado, em mm.",
    "filete": (
        "Perna do filete que une a mesa à alma no perfil soldado, em mm. Entra na medida k "
        "(t_f + perna) do escoamento local da alma. Sem filete (solda de penetração), use 0."
    ),
    "aco": "Aço do perfil (f_y e f_u da NBR 8800, Anexo A). Ex.: ASTM A572 Gr 50, f_y = 345 MPa.",
    "gama_a1": (
        "Coeficiente de ponderação da resistência ao escoamento e à instabilidade (γ_a1). Na "
        "combinação normal vale 1,10 (NBR 8800, Tabela 3)."
    ),
    "gama_a2": (
        "Coeficiente de ponderação da resistência à ruptura (γ_a2), usado no esmagamento e na "
        "ruptura do enrijecedor. Na combinação normal vale 1,35."
    ),
    "sec_forcas": (
        "As forças que chegam na mesa, centradas na alma: reação de apoio, pé de equipamento, "
        "viga que apoia por cima ou por baixo, mesa de viga ligada ao pilar. Uma linha por força, "
        "com o valor de cálculo (já majorado)."
    ),
    "tabela_forcas": (
        "Cada linha é uma força. Tipo: compressão (empurra a mesa contra a alma, como a reação "
        "de apoio), tração (puxa a mesa, como um tirante pendurado) ou par de forças opostas nas "
        "duas mesas na mesma seção (pilar com vigas dos dois lados). ℓn: comprimento de apoio ao "
        "longo da viga. Largura: medida da força na direção da largura da mesa. Distância à "
        "ponta: da força até a extremidade mais próxima da barra (reação de apoio = 0). Mesa "
        "comprimida: marque quando a força cai na mesa que a flexão comprime. M_Sd: momento na "
        "seção da força."
    ),
    "comprimento_destravado": (
        "ℓ da 5.7.5: o maior comprimento sem travamento lateral que envolve a seção da força, "
        "olhando as duas mesas, em mm. Só importa para a flambagem lateral da alma."
    ),
    "rotacao_impedida": (
        "A mesa carregada está impedida de girar? Ex.: laje, piso ou viga que chega e prende a "
        "mesa. Ligado usa a 5.7.5.2 a); desligado, a 5.7.5.2 b), mais severa."
    ),
    "deslocamento_lateral_impedido": (
        "Ligue quando o deslocamento lateral relativo entre as duas mesas está impedido na seção "
        "da força (travamento nas duas mesas ou enrijecedor de altura total). Nesse caso a "
        "flambagem lateral da alma (5.7.5) não precisa ser verificada."
    ),
    "extremidade_livre": (
        "Ligue quando o apoio ou a extremidade da viga não tem nada que impeça o giro em torno do "
        "eixo da viga e a alma não está ligada a outra viga ou pilar. A 5.7.8 exige enrijecedores "
        "em toda a altura nesse caso."
    ),
    "sec_enrijecedor": (
        "Os enrijecedores transversais colocados na seção da força quando a alma ou a mesa não "
        "resistem sozinhas. As medidas valem para todas as forças que precisarem deles."
    ),
    "usar_enrijecedor": (
        "Ligue para verificar enrijecedores nas seções em que alguma verificação da alma ou da "
        "mesa não passa. Desligado, o programa só diz que eles são necessários e sugere medidas."
    ),
    "bs": (
        "Largura de cada enrijecedor, da face da alma até a borda livre, em mm. A 5.7.9.5 pede "
        "b_s + t_w/2 ≥ b_f/3."
    ),
    "ts": "Espessura de cada enrijecedor, em mm. A 5.7.9.5 pede t_s ≥ t_f/2 e t_s ≥ b_s/16.",
    "dois_lados": "Ligado: um enrijecedor de cada lado da alma (o par). Desligado: só de um lado.",
    "posicao": (
        "Onde fica o enrijecedor. Na extremidade da viga (apoio), a faixa de alma que trabalha "
        "junto é de 12·t_w; numa seção interna, de 25·t_w (5.7.9.4)."
    ),
    "corte": (
        "Recorte no canto do enrijecedor para livrar o raio ou o filete mesa–alma, em mm. Tira "
        "área de contato e comprimento de solda."
    ),
    "ajustado": (
        "Ligado: a ponta do enrijecedor é ajustada (usinada) para encostar na mesa carregada, e "
        "o programa verifica o esmagamento (6.6.2). Desligado: o enrijecedor é soldado à mesa e "
        "o programa verifica essa solda."
    ),
    "aco_enrijecedor": "Aço da chapa do enrijecedor.",
    "perna_alma": "Perna do filete que une o enrijecedor à alma, dos dois lados do enrijecedor, em mm.",
    "perna_mesa": "Perna do filete que une o enrijecedor à mesa carregada, em mm.",
    "eletrodo": "Classe do eletrodo (resistência do metal da solda, f_w). E70: 485 MPa.",
    "altura_total": (
        "Ligado: o enrijecedor vai de uma mesa à outra (exigido quando a flambagem lateral ou a "
        "instabilidade da alma não passam, 5.7.9.3). Desligado: até 3/4 da altura da alma."
    ),
}
