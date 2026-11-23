"""Textos dos "?" da página Viga de monovia, em linguagem simples."""

AJUDA: dict[str, str] = {
    "sec_perfil": "O perfil I ou H da viga em que a talha corre (pela mesa de baixo) e o aço dele.",
    "familia": (
        "De onde vem o perfil: W e HP da Gerdau (com o raio de concordância), I laminado (sem o "
        "raio no catálogo) ou perfil soldado informado por você."
    ),
    "perfil": "A bitola do catálogo. Ex.: W 310 x 38,7.",
    "d": "Altura total do perfil soldado, em mm.",
    "bf": "Largura das mesas do perfil soldado, em mm. A roda da talha corre na mesa de baixo.",
    "tf": "Espessura das mesas do perfil soldado, em mm. É ela que dobra sob a roda.",
    "tw": "Espessura da alma do perfil soldado, em mm.",
    "filete": "Perna do filete mesa–alma do perfil soldado, em mm (entra em m e em k).",
    "aco": "Aço da viga. Ex.: ASTM A572 Gr 50, f_y = 345 MPa.",
    "gama_a1": "Coeficiente de ponderação da resistência (γ_a1). Na combinação normal, 1,10.",
    "sec_viga": "Como a viga está apoiada, o vão e o travamento lateral da mesa comprimida.",
    "sistema": (
        "Biapoiada: a viga vai de um apoio a outro e a talha passa no meio. Balanço: a viga sai "
        "do último apoio e a talha chega até a ponta. **Simplificação:** o balanço é tratado como "
        "engastado no apoio; se o trecho de trás girar, a flecha real fica maior."
    ),
    "L": "Vão entre apoios (ou comprimento do balanço), em mm.",
    "Lb": (
        "Comprimento sem travamento lateral da mesa comprimida, em mm. Sem travamentos no meio, "
        "é o próprio vão."
    ),
    "sec_talha": (
        "Os dados da talha que correm na viga: a carga que ela levanta, o peso dela e do trole, "
        "as rodas e onde a roda pisa na mesa."
    ),
    "capacidade": "Carga içada nominal (capacidade da talha), em kN. Ex.: 2 t ≈ 19,6 kN.",
    "peso_talha": "Peso próprio da talha com o trole (as partes que se movem), em kN.",
    "eixos": "Número de eixos do trole: 2 é o comum (4 rodas).",
    "rodas_por_eixo": "Rodas em cada eixo: 2, uma de cada lado da alma.",
    "entre_eixos": "Distância entre os dois eixos do trole, ao longo da viga, em mm.",
    "n_roda": (
        "Distância do ponto de contato da roda até a borda da mesa, em mm (o n da EN 1993-6). "
        "Quanto mais perto da borda, mais a mesa dobra. Veja no catálogo do fabricante da talha."
    ),
    "sec_cargas": (
        "Os acréscimos dinâmicos e os coeficientes de ponderação. Os valores de partida são os "
        "do critério Anglo para monovias."
    ),
    "impacto_carga": (
        "Acréscimo dinâmico na carga içada, em fração. Critério Anglo 5.4: 0,20 (+20 %)."
    ),
    "impacto_moveis": (
        "Acréscimo dinâmico no peso da talha e do trole, em fração. Critério Anglo 5.4: 0,10."
    ),
    "lateral": (
        "Força lateral total na mesa de baixo, como fração de (carga içada + talha). Padrão 0,10 "
        "(10 %), como a força transversal das pontes rolantes."
    ),
    "gama_g": "Coeficiente de ponderação do peso próprio da viga. NBR 8800, Tabela 1: 1,25.",
    "gama_q": "Coeficiente de ponderação da talha e da carga içada (ação variável): 1,50.",
    "sec_limites": "Os limites de flecha e a condição da ponta da viga junto da roda.",
    "flecha_vertical": (
        "Divisor do limite de flecha vertical: L/500 pelo critério Anglo para monovias (sem o "
        "impacto). No balanço, L é o dobro do balanço."
    ),
    "flecha_horizontal": "Divisor do limite de flecha horizontal: L/400 pelo critério Anglo.",
    "ponta_sem_enrijecedor": (
        "Ligue quando a roda chega até a ponta livre da viga sem chapa de enrijecimento. O "
        "comprimento de mesa que trabalha cai para 2·(m + n) e a mesa resiste bem menos."
    ),
    "sec_apoio": (
        "Como a viga se apoia: pendurada pela mesa de cima (tirante ou chapa, a mesa é puxada) ou "
        "apoiada pela mesa de baixo. O programa verifica a mesa e a alma ali (NBR 8800, 5.7)."
    ),
    "apoio": "Pendurada: a força traciona a alma. Apoiada: a força comprime a alma.",
    "ln_apoio": "Comprimento da chapa de apoio ou de suspensão ao longo da viga, em mm.",
    "largura_apoio": "Largura da chapa de apoio no sentido da largura da mesa, em mm.",
    "sec_esforcos": (
        "Os esforços que a talha na posição mais desfavorável produz, já majorados, e a reação "
        "de serviço que vai para o apoio."
    ),
    "res_momento": "Momento fletor vertical de cálculo máximo, com o peso próprio da viga.",
    "res_cortante": "Força cortante de cálculo máxima (talha junto ao apoio).",
    "res_roda": "Carga de cálculo de uma roda, com impacto: é a que dobra a mesa de baixo.",
    "res_reacao": "Reação de serviço (sem impacto e sem majorar) no apoio mais carregado.",
}
