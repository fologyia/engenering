"""Textos de ajuda ("?") da página Calor no tempo, em linguagem simples."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    # ------------------------------------------------------------------ peça
    "sec_peca": (
        "A peça e o material. A peça começa toda a uma temperatura só; no instante zero ela é "
        "posta num forno, num banho, ao ar ou encostada em algo quente ou frio, e a conta mostra "
        "como a temperatura anda por dentro até quase estabilizar."
    ),
    "forma": (
        "Parede plana: chapa larga, porta de forno, laje, parede de tanque (o calor só atravessa "
        "a espessura). Cilindro: eixo, barra redonda ou tubo comprido (com diâmetro de dentro). "
        "Esfera: bola maciça ou oca."
    ),
    "espessura": "Espessura da parede, de uma face à outra.",
    "diametro": "Diâmetro de fora da peça.",
    "diametro_interno": (
        "Diâmetro do furo de dentro. Zero é peça maciça; maior que zero é tubo (ou esfera oca), "
        "e aí a face de dentro também tem a sua condição."
    ),
    "material": (
        "Propriedades a 300 K do Incropera (Tab. A.1 e A.3). Informar serve para outro material: "
        "k, ρ e c_p saem do catálogo do fabricante ou de tabela."
    ),
    "k": "Condutividade térmica: quanto o material conduz calor. Aço carbono: cerca de 60 W/(m·K).",
    "rho": "Massa específica do material. Aço: cerca de 7850 kg/m³.",
    "cp": "Calor específico: quanta energia 1 kg pede para subir 1 °C. Aço: cerca de 434 J/(kg·K).",
    "t_inicial": "Temperatura da peça inteira antes de começar (no instante zero).",
    # ------------------------------------------------------------------ faces
    "sec_faces": (
        "O que encosta em cada face a partir do instante zero. Convecção é o caso mais comum: ar "
        "ou líquido em volta, com o coeficiente h e a temperatura do fluido."
    ),
    "face_tipo": (
        "Ar ou líquido em volta: troca calor por convecção (h e temperatura do fluido). "
        "Temperatura fixa: a face fica na temperatura dada, como encostada em vapor condensando "
        "ou em gelo derretendo. Fluxo de calor: entra uma potência por área, como uma resistência "
        "colada. Isolada: não passa calor."
    ),
    "h": (
        "Coeficiente de convecção. Valores típicos (Incropera, Tab. 1.1): ar parado 2 a 25; ar "
        "soprado 25 a 250; líquido parado 50 a 1000; líquido em movimento 100 a 20 000; água "
        "fervendo ou vapor condensando 2500 a 100 000 W/(m²·K). Radiação, se importa, entra "
        "somada no h."
    ),
    "t_fluido": "Temperatura do ar ou do líquido longe da face.",
    "t_fixa": "A temperatura em que a face fica do instante zero em diante.",
    "fluxo": (
        "Potência por área que entra pela face. Negativo é calor saindo. Uma resistência de "
        "1 kW numa face de 0,1 m² dá 10 000 W/m²."
    ),
    # ------------------------------------------------------------------ tempo
    "sec_tempo": (
        "Quanto tempo mostrar e, se quiser, a temperatura que um ponto precisa alcançar: a conta "
        "diz em quanto tempo ele chega lá."
    ),
    "duracao_modo": (
        "Até quase estabilizar: a conta vai até um pouco depois de a peça inteira ficar a 1 % "
        "do regime permanente. Informar: o tempo que você escolher."
    ),
    "duracao": "Tempo total mostrado, a partir do instante zero.",
    "duracao_unidade": "Unidade do tempo informado.",
    "alvo": (
        "Temperatura que se quer alcançar num ponto, como o centro de um eixo no forno ou a face "
        "de uma peça esfriando. Vazio: sem pergunta."
    ),
    "ponto": "O ponto da peça que precisa chegar à temperatura pedida.",
    "prazo": (
        "Tempo máximo aceito para o ponto chegar à temperatura pedida. Com o prazo, o resultado "
        "vira uma verificação: atende ou não atende. Vazio: só mostra o tempo."
    ),
    # ------------------------------------------------------------------ resultado
    "sec_resultado": (
        "A animação mostra a peça mudando de cor e as curvas andando juntas. Tocar põe o tempo "
        "para correr; a barra leva a qualquer instante; passe o mouse para ler os valores."
    ),
    "res_duracao": (
        "Tempo mostrado na animação. No automático, vai um pouco além de a peça estabilizar."
    ),
    "res_estabiliza": (
        "Quando a peça inteira chega a 1 % do regime permanente (do quanto a temperatura muda do "
        "começo ao fim): dali em diante quase nada muda."
    ),
    "res_equaliza": (
        "Quando a temperatura fica por igual dentro da peça: a diferença entre o ponto mais quente "
        "e o mais frio cai a 1 % do salto e não volta a subir. Só existe quando o regime "
        "permanente é por igual (o mesmo fluido ou a mesma temperatura em todas as faces)."
    ),
    "res_diferenca": (
        "A maior diferença de temperatura dentro da peça e quando ela acontece. É o que dá a "
        "tensão térmica (choque térmico): quanto maior, maior a tensão."
    ),
    "res_tau": (
        "Constante de tempo: o tempo em que a peça faz cerca de 63 % do caminho que falta até o "
        "regime permanente (o modo mais lento dela)."
    ),
    "res_final": "Temperatura no fim do tempo mostrado, em cada ponto.",
    "res_biot": (
        "Número de Biot: a resistência ao calor de dentro da peça dividida pela da película de "
        "fora. Abaixo de 0,1 a peça esquenta praticamente por igual."
    ),
    "res_alvo": "Em quanto tempo o ponto escolhido chega à temperatura pedida.",
    "res_calor": "Calor que entrou na peça (negativo: saiu) do instante zero até o fim.",
    "conferencia": (
        "Nos casos dos livros (parede, cilindro ou esfera com convecção ou temperatura fixa na "
        "face), a mesma peça tem solução exata em série. A tabela compara as duas."
    ),
    "registrar": (
        "Grava o cálculo no projeto ativo, com as curvas e o perfil em alguns instantes para o "
        "memorial (o Word e o PDF não animam)."
    ),
    # ------------------------------------------------------------------ seção desenhada
    "sec_secao": (
        "Uma barra comprida de seção constante: o calor corre no plano da seção. Escolha um "
        "modelo pronto ou use a seção desenhada na página Desenhar seção."
    ),
    "origem": (
        "Modelo pronto com as medidas ao lado, ou a seção que está desenhada agora na página "
        "Desenhar seção (com furos, chapas e o que mais tiver)."
    ),
    "sec_contornos": (
        "O que encosta na seção a partir do instante zero: uma condição no contorno de fora e "
        "outra no contorno dos furos (quando a seção tem furo), como o fluido quente que passa "
        "por dentro de um tubo."
    ),
    "res_quente": "A maior temperatura da seção no fim do tempo mostrado.",
    "res_media": "Temperatura média da seção (pela massa) no fim do tempo mostrado.",
    "res_frio": "A menor temperatura da seção no fim do tempo mostrado.",
    "res_alvo_secao": (
        "Em quanto tempo a seção inteira passa da temperatura pedida: aquecendo, o ponto mais "
        "frio chega lá; esfriando, o ponto mais quente."
    ),
}
