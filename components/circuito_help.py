"""Textos de ajuda ("?") da página Circuito fechado, em linguagem simples."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    # ------------------------------------------------------------------ condições
    "sec_condicoes": (
        "O fluido do circuito e as condições de projeto. O ar vale para o dry cooler e para os "
        "tubos que perdem calor."
    ),
    "fluido": (
        "Água ou mistura com glicol (anticongelante), com as propriedades da CoolProp. O glicol "
        "deixa o fluido mais viscoso e com menos calor específico: a bomba e o dry cooler sentem."
    ),
    "t_ar": "Temperatura do ar de projeto: a do dia mais quente em que o circuito precisa dar conta.",
    "t_inicial": (
        "Temperatura do circuito quando ele é cheio e parte (o fluido frio). É dela que a "
        "dilatação no vaso de expansão é contada."
    ),
    "p_min": (
        "A menor pressão manométrica aceita em qualquer ponto. Abaixo de zero (da atmosférica) "
        "entra ar pelas juntas e purgadores; muitos projetos pedem uma folga acima disso."
    ),
    "v_max": "A maior velocidade aceita nos tubos. Acima de 2 a 3 m/s a água faz barulho e desgasta.",
    # ------------------------------------------------------------------ desenho
    "sec_desenho": (
        "Desenhe o circuito visto de cima, em metros. Tubo: clique num ponto e no seguinte; no "
        "vazio o ponto nasce ali; volte ao primeiro ponto para fechar a volta. Peças: escolha a "
        "peça e clique em cima de um tubo; ela entra no meio do tubo. Vaso: clique num ponto. "
        "Ramais em paralelo: desenhe outro tubo saindo de um ponto e chegando a outro. A bomba "
        "empurra no sentido em que o tubo foi desenhado; ⇄ inverte."
    ),
    "sel_nada": (
        "Clique num ponto, num tubo ou numa peça do desenho para ver e mudar os dados dele aqui."
    ),
    "exemplo": "Volta ao exemplo: duas máquinas em paralelo resfriadas por um dry cooler.",
    "limpar": "Apaga o desenho inteiro para começar do zero.",
    # ------------------------------------------------------------------ campos do selecionado
    "c_nome": "Nome que aparece no desenho, nas tabelas e no memorial.",
    "c_cota": "Altura do ponto em relação a uma referência (o piso, por exemplo): muda a pressão.",
    "c_vaso_volume_L": "Volume total do vaso de expansão (nominal do catálogo).",
    "c_vaso_precarga_bar": (
        "Pressão do ar do vaso antes de encher o circuito (vem de fábrica, ajustável). Fica abaixo "
        "da pressão de enchimento."
    ),
    "c_vaso_enchimento_bar": "Pressão no ponto do vaso com o circuito cheio e frio.",
    "c_vaso_maxima_bar": (
        "A maior pressão aceita no vaso com o fluido quente: a da válvula de segurança menos uma "
        "folga."
    ),
    "c_diametro_mm": "Diâmetro interno do tubo (ou da ligação da peça).",
    "c_material": "Material do tubo: dá a rugosidade da parede.",
    "c_comprimento": (
        "Comprimento de verdade, quando o desenho está fora de escala ou o tubo sobe e desce. "
        "Vazio: vale o comprimento desenhado."
    ),
    "c_k_local": "Soma dos K das curvas, tês e registros do tubo (ou o K da válvula).",
    "c_perde_calor": "Marque se o tubo troca calor com o ar em volta (sem isolamento ou com pouco).",
    "c_isolamento_mm": "Espessura do isolamento. Zero: tubo nu.",
    "c_k_isolamento": "Condutividade do isolamento. Lã de rocha, espuma: cerca de 0,035 a 0,045 W/(m·K).",
    "c_h_externo": "h do ar em volta do tubo. Ar parado: 5 a 10 W/(m²·K).",
    "c_h0_m": "Altura da bomba com a vazão zero (shutoff), da curva do fabricante.",
    "c_qmax_m3h": "Vazão em que a altura da bomba cai a zero, prolongando a curva do fabricante.",
    "c_rendimento": "Rendimento da bomba no ponto de trabalho (0 a 1), para a potência no eixo.",
    "c_npsh_requerido_m": "NPSH pedido pela bomba no catálogo. Zero: não confere o NPSH.",
    "c_ligada": "Desligada, a bomba fica com a retenção fechada: a água não passa por ela.",
    "c_dp_kPa": "Perda de carga da peça do catálogo, na vazão do catálogo.",
    "c_q_nominal_m3h": "Vazão em que vale a perda de carga do catálogo.",
    "c_volume_L": "Volume de fluido dentro da peça (dá inércia térmica e entra na dilatação).",
    "c_potencia_kW": "Calor que o equipamento põe no fluido (o que precisa ser tirado).",
    "c_massa_kg": (
        "Massa do equipamento que esquenta junto com o fluido (molde, carcaça, trocador): dá "
        "inércia, a partida fica mais lenta."
    ),
    "c_calor_especifico_massa": "Calor específico da massa do equipamento. Aço: cerca de 470 J/(kg·K).",
    "c_t_maxima": "A maior temperatura aceita do fluido na saída do equipamento.",
    "c_q_catalogo_kW": "Capacidade do dry cooler no ponto do catálogo (com o ventilador em 100 %).",
    "c_t_entrada_catalogo": "Temperatura do líquido entrando no dry cooler, no ponto do catálogo.",
    "c_t_ar_catalogo": "Temperatura do ar entrando no dry cooler, no ponto do catálogo.",
    "c_vazao_liquido_catalogo_m3h": "Vazão de líquido no ponto do catálogo.",
    "c_vazao_ar_catalogo_m3h": "Vazão de ar dos ventiladores no ponto do catálogo.",
    "c_potencia_ventilador_kW": "Potência elétrica dos ventiladores em 100 %.",
    "c_controle": (
        "Sempre ligado: o ventilador fica em 100 %. Liga e desliga: liga 1 K acima do ajuste e "
        "desliga 1 K abaixo. Proporcional: a rotação muda para a saída ficar no ajuste."
    ),
    "c_t_ajuste": (
        "Temperatura de saída que o controle segura (no dry cooler, pelo ventilador; no chiller, "
        "pela capacidade)."
    ),
    "c_capacidade_kW": "Capacidade de frio do chiller do catálogo, na condição de trabalho.",
    "c_cop": "COP do chiller do catálogo (frio produzido por energia elétrica).",
    "c_ua_W_K": "UA da parede do tanque para o ar (área × U). Zero: tanque isolado.",
    # ------------------------------------------------------------------ tabelas e tempo
    "sec_tabelas": "Para completar o que o desenho não deu: cota dos pontos e dados dos tubos.",
    "sec_tempo": (
        "Como o circuito se comporta desde a partida, com tudo frio: a fonte esquenta, o dry "
        "cooler e o chiller entram e o vaso recebe a dilatação. Pode variar o ar e a carga ao "
        "longo do dia."
    ),
    "duracao_modo": (
        "Automático: o bastante para o circuito estabilizar (ou 24 h, com o dia variando). "
        "Informar: o tempo que você escolher."
    ),
    "duracao": "Tempo mostrado, a partir da partida.",
    "dia": (
        "Marque para variar, hora a hora, a temperatura do ar e a carga das fontes (1 é a potência "
        "informada em cada fonte)."
    ),
    "perfil": "Temperatura do ar e multiplicador da carga em cada hora do dia.",
    # ------------------------------------------------------------------ resultado
    "sec_resultado": (
        "A conta do circuito inteiro: vazão em cada ramal, pressão em cada ponto, temperaturas em "
        "regime e as verificações. O que não passa aparece em vermelho no desenho."
    ),
    "res_vazao": "Vazão que a bomba manda, no ponto em que a curva dela encontra as perdas do circuito.",
    "res_fonte": "A maior temperatura do fluido na saída das fontes, em regime permanente.",
    "res_vaso": "Pressão no vaso com o fluido aquecido (a maior da partida).",
    "res_estabiliza": "Quando, da partida a frio, todas as temperaturas ficam a 1 % do fim.",
    "registrar": "Grava o circuito no projeto ativo, com as tabelas, as verificações e as curvas.",
}
