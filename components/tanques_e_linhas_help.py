"""Textos de ajuda ("?") da página Tanques e linhas no tempo, em linguagem simples."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    # ------------------------------------------------------------------ nível
    "sec_tanque": (
        "O tanque e o nível de onde ele parte. A conta acompanha o nível subindo ou descendo até "
        "esvaziar, encher ou estabilizar (quando o que entra fica igual ao que sai)."
    ),
    "forma": (
        "Cilíndrico vertical: caixa d'água, tanque de processo em pé. Retangular: reservatório de "
        "concreto, caixa de chapa. Cilíndrico horizontal: tanque deitado (de diesel, por exemplo), "
        "em que a área do líquido muda com o nível."
    ),
    "altura": "Altura útil do tanque, do fundo até onde o líquido transborda.",
    "diametro": "Diâmetro interno do tanque.",
    "comprimento": "Comprimento interno do tanque.",
    "largura": "Largura interna do tanque.",
    "nivel_inicial": "Altura do líquido no instante zero, medida do fundo.",
    "entrada": "Vazão que entra o tempo todo, por cima. Zero: só esvazia.",
    "sec_saida": "Por onde o líquido sai: um furo no fundo, um tubo, uma bomba ou nada.",
    "saida": (
        "Orifício: furo de borda viva no fundo, com a vazão de Torricelli. Tubo: tubo saindo do "
        "fundo e descarregando livre, com atrito e peças. Bomba: tira uma vazão fixa. Nenhuma: o "
        "tanque só enche. Outro tanque: um tubo liga os fundos dos dois tanques e a água passa até "
        "os níveis ficarem iguais (vasos comunicantes)."
    ),
    "d_saida": "Diâmetro do furo ou diâmetro interno do tubo de saída.",
    "cd": "Coeficiente de descarga do orifício. Borda viva: 0,61 (Çengel e Cimbala, cap. 8).",
    "l_tubo": "Comprimento do tubo de saída.",
    "material_tubo": "Material do tubo de saída: dá a rugosidade da parede.",
    "k_tubo": (
        "Soma dos K das peças do tubo, com a entrada. Entrada de canto vivo: 0,5; curva 90° "
        "padrão: 0,75; registro de gaveta aberto: 0,17."
    ),
    "desnivel": (
        "Quanto a ponta do tubo fica abaixo do fundo do tanque. Esse desnível também empurra o "
        "líquido."
    ),
    "q_bomba": "Vazão que a bomba tira, constante.",
    "fluido": "O líquido do tanque: dá a densidade e a viscosidade usadas no atrito do tubo.",
    "sec_tempo": (
        "Quanto tempo mostrar e, se quiser, o nível ou a temperatura que se quer alcançar: a "
        "conta diz em quanto tempo chega lá."
    ),
    "duracao_modo": (
        "Automático: a conta para quando o tanque esvazia, enche, estabiliza (o nível a 0,5 % do "
        "equilíbrio) ou, na temperatura, chega a 99 % do caminho. Informar: o tempo que você "
        "escolher."
    ),
    "duracao": "Tempo total mostrado, a partir do instante zero.",
    "duracao_unidade": "Unidade do tempo informado.",
    "alvo_nivel": "Nível que se quer alcançar. Vazio: sem pergunta.",
    "res_tempo": "Tempo mostrado na animação; diz se o tanque esvaziou, encheu ou estabilizou.",
    "res_nivel_final": "Nível no fim do tempo mostrado.",
    "res_equilibrio": (
        "Nível em que a saída iguala a entrada. Com orifício ou tubo, o tanque tende a esse nível."
    ),
    "res_alvo_nivel": "Em quanto tempo o nível chega ao valor pedido.",
    "res_saida_max": "A maior vazão de saída no tempo mostrado.",
    "sec_tanque2": (
        "O segundo tanque, ligado ao primeiro por um tubo entre os fundos. A água passa do nível "
        "mais alto para o mais baixo até as duas superfícies ficarem na mesma cota."
    ),
    "d2": "Diâmetro interno do tanque 2.",
    "h2": "Altura útil do tanque 2.",
    "nivel2": "Altura da água no tanque 2 no instante zero, medida do fundo dele.",
    "cota2": (
        "Quanto o fundo do tanque 2 fica acima do fundo do tanque 1. Negativo: o tanque 2 fica "
        "mais baixo."
    ),
    "res_equaliza": (
        "Quando as duas superfícies ficam na mesma cota (a 1 mm): o tempo de equalização. Perto "
        "do fim a água anda devagar e o último milímetro levaria um tempo sem fim."
    ),
    "res_nivel_igual": (
        "A cota em que as duas superfícies se encontram, guardando o volume total de água "
        "(medida do fundo do tanque 1)."
    ),
    "res_diferenca0": "Diferença entre as duas superfícies no instante zero.",
    "res_vazao_max": "A maior vazão no tubo de ligação, que é a do começo.",
    # ------------------------------------------------------------------ temperatura
    "sec_termico": (
        "Um tanque bem misturado (com agitador ou circulação): o líquido tem a mesma temperatura "
        "em todo lugar. A conta mostra a temperatura subindo ou descendo até estabilizar."
    ),
    "volume": "Volume de líquido no tanque.",
    "liquido": (
        "Água: densidade e calor específico da CoolProp na temperatura inicial, e a conta para se "
        "a água chegar a 100 °C (ferve) ou a 0 °C (congela). Informar: outro líquido."
    ),
    "rho": "Massa específica do líquido.",
    "cp_liquido": "Calor específico do líquido. Água: cerca de 4180 J/(kg·K).",
    "t_inicial": "Temperatura do líquido no instante zero.",
    "aquecimento": (
        "Resistência: potência fixa (negativa é um resfriador de potência fixa). Serpentina ou "
        "camisa: vapor ou fluido a uma temperatura fixa, trocando calor pelo UA dela. Nenhum: só "
        "perda e vazão."
    ),
    "potencia": "Potência que a resistência põe no líquido.",
    "termostato": (
        "Temperatura em que o aquecimento deixa de esquentar e só repõe as perdas, como num "
        "aquecedor com termostato. Vazio: sem termostato, o aquecimento fica ligado o tempo todo."
    ),
    "ua_serpentina": (
        "UA da serpentina ou camisa: o coeficiente global U vezes a área de troca. Serpentina de "
        "vapor em água costuma ter U de algumas centenas a milhares de W/(m²·K): confira com o "
        "fabricante."
    ),
    "t_serpentina": "Temperatura do vapor ou do fluido na serpentina, constante.",
    "ua_perda": (
        "UA da parede do tanque para o ar: a área da parede vezes o U. Sem isolamento, ao ar "
        "parado, o U fica na faixa da convecção natural (2 a 25 W/(m²·K), Incropera Tab. 1.1) "
        "mais a radiação; com isolamento, U ≈ k/e do isolamento. Zero: tanque isolado."
    ),
    "t_ambiente": "Temperatura do ar em volta do tanque.",
    "vazao_termica": "Vazão que entra e sai ao mesmo tempo (o volume não muda). Zero: tanque fechado.",
    "t_entrada": "Temperatura do líquido que entra.",
    "alvo_temperatura": "Temperatura que se quer alcançar no tanque. Vazio: sem pergunta.",
    "res_t_final": "Temperatura no fim do tempo mostrado.",
    "res_t_equilibrio": "Temperatura em que o tanque estabiliza, se tudo ficar como está.",
    "res_tau": (
        "Constante de tempo: o tempo em que o tanque faz cerca de 63 % do caminho que falta até o "
        "equilíbrio."
    ),
    "res_alvo_temperatura": "Em quanto tempo o líquido chega à temperatura pedida.",
    "res_estabiliza_tanque": (
        "Quando o líquido chega a 1 % do equilíbrio (4,6 constantes de tempo), ou quando o "
        "termostato passa a segurar a temperatura."
    ),
    # ------------------------------------------------------------------ partida
    "sec_linha": (
        "Um reservatório alimenta um tubo que descarrega livre. No instante zero a válvula começa "
        "a abrir (ou a bomba começa a girar) e a coluna de água acelera até a vazão de regime."
    ),
    "l_linha": "Comprimento total do tubo.",
    "d_linha": "Diâmetro interno do tubo.",
    "material_linha": "Material do tubo: dá a rugosidade da parede.",
    "k_linha": "Soma dos K das peças do tubo (curvas, entrada, tês), sem a válvula que manobra.",
    "desnivel_linha": (
        "Quanto o nível do reservatório fica acima da saída do tubo. Negativo: a saída fica mais "
        "alta, e precisa de bomba."
    ),
    "evento": (
        "Abrir a válvula: a bomba (se houver) já está girando e a válvula abre em linha reta no "
        "tempo dado. Ligar a bomba: a válvula já está aberta e a bomba sobe a rotação em linha "
        "reta no tempo dado."
    ),
    "t_manobra": "Tempo de abertura da válvula ou de partida da bomba. Zero: instantâneo.",
    "k_valvula": "K da válvula toda aberta. Gaveta: 0,17; globo: cerca de 10; borboleta: 0,3 a 0,6.",
    "bomba": (
        "Bomba na linha, pela curva simplificada H = H₀ − (H₀/Q_máx²)·Q²: a altura com a vazão "
        "zero e a vazão com a altura zero, tiradas da curva do fabricante."
    ),
    "h0": "Altura da bomba com a vazão zero (shutoff), da curva do fabricante.",
    "qmax": "Vazão em que a altura da bomba chega a zero, prolongando a curva do fabricante.",
    "celeridade": (
        "Velocidade da onda de pressão no tubo, só para conferir se a conta sem onda vale. Água em "
        "aço: cerca de 1000 a 1300 m/s; em PVC: 300 a 500 m/s."
    ),
    "res_q_final": "Vazão depois que a manobra acaba e a coluna estabiliza.",
    "res_t95": "Tempo para a vazão chegar a 95 % da vazão de regime.",
    "res_t99": "Tempo para a vazão chegar a 99 % da vazão de regime.",
    "res_onda": (
        "Tempo de ida e volta da onda de pressão, 2·L/a. A conta sem onda vale quando a manobra é "
        "bem mais lenta que isso."
    ),
    # ------------------------------------------------------------------ água quente chegando
    "sec_tubo": (
        "Um tubo cheio de água parada, à temperatura do ambiente (ou outra). No instante zero "
        "começa a entrar água mais quente (ou mais fria): a frente anda com a água, e a parede do "
        "tubo rouba calor no caminho."
    ),
    "l_tubo_quente": "Comprimento do tubo, da entrada até a saída (o chuveiro, a torneira, o equipamento).",
    "d_tubo_quente": "Diâmetro interno do tubo.",
    "parede": "Espessura da parede do tubo.",
    "material_parede": "Material da parede: dá a massa e o calor específico que a parede guarda.",
    "isolamento": "Espessura do isolamento em volta do tubo. Zero: tubo sem isolamento.",
    "k_isolamento": (
        "Condutividade do isolamento. Lã de vidro ou de rocha e espuma elastomérica: cerca de "
        "0,035 a 0,045 W/(m·K): confira com o fabricante."
    ),
    "h_externo": "h do ar em volta do tubo. Ar parado: 5 a 10 W/(m²·K); ao vento, mais.",
    "t_ambiente_tubo": "Temperatura do ar em volta do tubo.",
    "vazao_tubo": "Vazão de água no tubo.",
    "t_inicial_tubo": "Temperatura do tubo e da água parada dentro dele, no instante zero.",
    "t_entrada_tubo": "Temperatura da água que passa a entrar no instante zero.",
    "alvo_tubo": "Temperatura que se quer na saída. Vazio: sem pergunta.",
    "prazo_tubo": (
        "Tempo máximo aceito para a saída chegar à temperatura pedida. Com o prazo, o resultado "
        "vira uma verificação."
    ),
    "res_transito": "Tempo que a água leva para atravessar o tubo, L/v, sem contar a parede.",
    "res_alvo_tubo": "Em quanto tempo a água na saída chega à temperatura pedida.",
    "res_volume": "Água que sai fria (abaixo da temperatura pedida) até a quente chegar.",
    "res_permanente": "Temperatura na saída quando tudo estabiliza, com a perda pelo caminho.",
    "res_estabiliza_tubo": (
        "Quando a água na saída chega a 1 % da temperatura de regime e não sai mais dali: a "
        "parede já esquentou e só a perda para o ar continua."
    ),
    # ------------------------------------------------------------------ comum
    "sec_resultado": (
        "A animação mostra o que acontece e as curvas andam juntas. Tocar põe o tempo para "
        "correr; a barra leva a qualquer instante; passe o mouse para ler os valores."
    ),
    "registrar": (
        "Grava o cálculo no projeto ativo, com as curvas para o memorial (o Word e o PDF não "
        "animam)."
    ),
}
