"""Textos de ajuda ("?") da página Pilares do modelo, em linguagem simples."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    "sec_como": (
        "O programa olha o esqueleto do modelo e acha, em cada pilar, as alturas em que outra barra "
        "encosta nele. A barra que chega na direção da alma trava L_x; a que chega na direção da "
        "mesa trava L_y. O que o arquivo não diz é como o pé está preso: isso você escolhe aqui."
    ),
    "base": (
        "Como o pé do pilar está preso no apoio do modelo. Rotulada (pino) é a favor da segurança: "
        "o trecho de baixo fica com K = 1,0. Engastada só vale se a placa de base e os chumbadores "
        "seguram mesmo o giro: o trecho de baixo fica com K = 0,8 (0,7 no teórico). Pilar em "
        "balanço, sem nada no topo, precisa da base engastada."
    ),
    "recomendado": (
        "Ligado, usa os valores recomendados da Tabela E.1 da NBR 8800 (0,65; 0,8; 1,2; 2,1), que "
        "consideram que o engaste nunca é perfeito. Desligado, usa os teóricos (0,5; 0,7; 1,0; "
        "2,0). O recomendado é o mais seguro."
    ),
    "estados": (
        "As combinações últimas do plano de cargas que entram na verificação. As de serviço não "
        "entram: elas são para a flecha."
    ),
    "sec_resultado": (
        "Cada pilar com os travamentos do esqueleto, o K·L do trecho que governa em cada eixo e o "
        "pior caso de todas as combinações em todos os pontos do pilar."
    ),
    "res_pilares": "Quantos pilares o modelo tem: pelo tipo na tabela das barras ou, sem ele, por estar em pé no esqueleto.",
    "res_atendem": "Pilares que passam em todas as verificações.",
    "res_nao": "Pilares que não passam em alguma verificação: veja o cálculo de cada um logo abaixo.",
    "res_pendentes": "Pilares sem perfil, fora do esqueleto ou que não ficam de pé com a base escolhida: a coluna O que governa diz o motivo.",
    "res_pior": "O maior aproveitamento entre todos os pilares.",
    "csv": "A tabela dos pilares em CSV, para abrir no Excel.",
    "sec_detalhe": (
        "O cálculo de um pilar: onde ele é travado, os trechos de cada eixo com o K de cada um e "
        "a tabela de verificação, igual à da página Flambagem de colunas."
    ),
    "pilar": "Escolha o pilar para ver o cálculo dele. Abre no que tem o maior aproveitamento.",
    "ver_desenho": "Mostra o pilar em pé, nas duas vistas, com os travamentos nas alturas lidas do modelo.",
    "registrar": (
        "Grava a verificação de todos os pilares no projeto ativo. Ela vai para o memorial, com a "
        "tabela dos pilares."
    ),
}
