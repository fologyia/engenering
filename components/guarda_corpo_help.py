"""Ajuda ("?") do guarda-corpo nas bordas do piso, em linguagem simples."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    "sec_guarda_corpo": (
        "O programa olha o contorno de cada chapa de piso do esqueleto: onde não há outro piso do "
        "lado de fora é borda livre, e o guarda-corpo vai parafusado na viga que fica embaixo "
        "dela. Onde o lance da escada encosta no piso é o acesso (sem guarda-corpo). Confira e "
        "desmarque o que não tiver guarda-corpo (lado de parede, portão)."
    ),
    "res_metodo": (
        "Pelas chapas do piso: o contorno de verdade (recortes, aberturas, escada). Pelas vigas: "
        "sem chapas no esqueleto, a viga sem paralela de um dos lados é de borda — confira mais."
    ),
    "res_comprimento": "Soma dos trechos marcados, que vão receber o peso do guarda-corpo.",
    "res_acesso": "Trechos de borda onde a escada chega (por onde se passa): sem guarda-corpo.",
    "res_sem_viga": (
        "Borda livre sem viga embaixo no esqueleto: o guarda-corpo dali precisa de apoio no "
        "modelo (ou a borda é uma parede). Não recebe carga."
    ),
    "res_desenho": (
        "A planta vista de cima: azul é guarda-corpo (com os montantes), tracejado na escada, "
        "laranja o acesso, vermelho a borda sem viga e cinza o que você desmarcou."
    ),
    "tabela": (
        "Um trecho por linha: a viga que apoia, o comprimento e por que o programa achou isso. "
        "Desmarque “Tem guarda-corpo” onde não tiver; marque se ele achou acesso e não "
        "for. Trecho sem viga não recebe carga, mesmo marcado."
    ),
    "peso": (
        "Peso do guarda-corpo por metro, com rodapé, montantes e fixação. Industrial: uns 40 kg/m "
        "≈ 0,40 kN/m. Vai no caso PE (elementos construtivos)."
    ),
    "altura": (
        "Altura do guarda-corpo, para o vento: 1,10 m pela NR-12; o critério Anglo pede 1,30 m."
    ),
    "phi": (
        "Parte cheia da área do guarda-corpo, para o vento: com rodapé, uns 0,30 (corrimão, "
        "travessa intermediária, rodapé e montantes)."
    ),
    "res_pesos": (
        "Por viga: o comprimento com guarda-corpo, o peso total e a carga distribuída na viga "
        "inteira (total ÷ comprimento da viga), como o piso."
    ),
    "btn_enviar": (
        "Grava a sua escolha no projeto e põe o peso do guarda-corpo nas vigas de borda, no caso "
        "PE do plano de cargas. As outras linhas do PE (o piso) ficam; um envio anterior do "
        "guarda-corpo é trocado."
    ),
    "opcao_longarinas": (
        "Ligado: onde duas longarinas saem da borda para fora do piso, o programa abre o acesso da "
        "escada (sem guarda-corpo). Desligue se ele achar acesso onde não tem. O acesso que vem das "
        "chapas (lance encostado no piso) continua."
    ),
    "opcao_lances": (
        "Ligado: os lados dos lances de escada (nas longarinas) entram com guarda-corpo. Desligado: "
        "aparecem na tabela, desmarcados."
    ),
    "tabela_a_mao": (
        "Para o que o programa não achou ou achou errado: a viga, de quantos metros até quantos ao "
        "longo dela (vazio = a viga inteira, medido do início dela no SolidWorks) e o tipo. "
        "Guarda-corpo à mão entra no lugar do que ele achou naquela parte; acesso ou portão tira o "
        "guarda-corpo dali."
    ),
    "btn_gravar": (
        "Só grava a escolha (trechos, altura e φ) no projeto: o vento barra a barra usa estes "
        "guarda-corpos."
    ),
}
