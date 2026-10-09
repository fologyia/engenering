"""Textos dos “?” da página Vigas de piso, em linguagem simples (um teste exige cada um)."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    "sec_perfil": "O perfil da viga, o aço e se ela é viga principal ou secundária do piso.",
    "perfil": (
        "Perfil do catálogo do programa (W, U, I…). O programa também procura o mais leve da mesma "
        "família que atende."
    ),
    "aco": "Aço do perfil: dá o f_y da flexão e do cortante.",
    "tipo": (
        "Principal: a que recebe outras vigas ou apoia nos pilares. Secundária: a que só recebe "
        "a grade. Muda o limite de flecha do critério Anglo (L/350 ou L/300)."
    ),
    "sec_geometria": "O vão da viga e a faixa de piso que ela carrega.",
    "vao": "Distância entre os apoios da viga (m). A viga é tratada como biapoiada.",
    "largura": (
        "Largura de influência (m): a faixa de piso que a viga carrega — em geral a distância "
        "entre vigas vizinhas."
    ),
    "travada": (
        "Ligue se a grade travar a mesa comprimida ao longo da viga (clipes de fixação). Então "
        "informe o espaçamento entre os pontos travados."
    ),
    "lb": "Distância entre os pontos que travam a mesa comprimida (m), para a flambagem lateral.",
    "sec_cargas": "As cargas do piso sobre a viga, características (sem coeficientes).",
    "pe": "Peso do piso (grade, chapa) e acessórios, em kN/m² (grade usual: 0,3 a 0,5 kN/m²).",
    "sc": "Sobrecarga de uso (kN/m²). Vem da base técnica do projeto quando existe.",
    "linear": "Carga permanente por metro na viga (guarda-corpo, tubulação apoiada), em kN/m.",
    "concentrada": (
        "Peso de um equipamento no meio do vão (kN), a posição mais desfavorável para momento e "
        "flecha."
    ),
    "sec_criterio": "Norma e critério do cliente da verificação.",
    "anglo": (
        "Liga as exigências do critério Anglo: flecha L/350 ou L/300 (Tabela 3), espessura mínima "
        "de 4,8 mm (8.8) e a capacidade mínima da ligação (9.1). Vem da base técnica."
    ),
    "norma": "Norma da flexão (FLT, FLM e FLA): Projeto NBR 8800:2024, NBR 8800:2008 ou AISC.",
    "res_status": "OK quando todas as verificações passam; NÃO OK se alguma reprova.",
    "res_aproveitamento": "A maior razão solicitante ÷ resistente (flexão, cortante ou flecha).",
    "res_momento": "Momento de cálculo no meio do vão e o momento resistente da viga.",
    "res_flecha": "Flecha com todas as cargas características e a relação vão/flecha.",
    "res_desenho": "A viga com as cargas, a deformada (exagerada), a flecha e as reações.",
    "res_verificacoes": (
        "Flexão (com a flambagem lateral e local), cortante, flechas e os valores de apoio: "
        "reação para a ligação e frequência natural."
    ),
    "res_mais_leve": (
        "O perfil mais leve da mesma família que passa em todas as verificações com estes "
        "dados. Use o botão para adotá-lo."
    ),
    "btn_adotar": "Troca o perfil da viga pelo mais leve que atende.",
    "btn_csv": "As verificações em CSV (abre no Excel).",
    "reg_registrar": "Grava a verificação da viga no projeto ativo: o memorial ganha o capítulo.",
}
