"""Ajuda ("?") da página Sensores do modelo, em linguagem simples."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    "sec_quadro": (
        "O quadro que a Vista de resultados do gerenciador de casos de carga mostra: cada sensor "
        "(coluna) em cada caso e em cada combinação (linha). A macro exportar_casos_de_carga grava "
        "esse quadro como <estudo>-gerenciador-resultados.csv, junto com as forças e as reações."
    ),
    "arquivo": (
        "O <estudo>-gerenciador-resultados.csv que a macro grava na pasta da peça. Também entra "
        "pela página Esforços do modelo, junto com os outros arquivos da macro."
    ),
    "btn_gravar": (
        "Guarda no projeto o quadro e o que você ajustou (o que cada sensor mede, a unidade, o f_y "
        "e os limites). Assim a página abre pronta da próxima vez."
    ),
    "res_sensores": "Quantas colunas (sensores) o quadro tem.",
    "res_casos": "Quantos casos primários (PP, SC, W0…) vieram, sem combinar.",
    "res_combinacoes": "Quantas combinações (C01-ELU, C49-ELSR…) vieram do gerenciador.",
    "res_fora": (
        "Combinações que deram exatamente o mesmo número de outras, em todos os sensores, tendo "
        "coeficientes diferentes: não são resultado e ficam fora da verificação."
    ),
    "btn_csv": (
        "O quadro organizado para o Excel: cada linha com o estado-limite, os valores na unidade "
        "de cálculo e a observação (repetido, igual a outra…)."
    ),
    "sec_sensores": (
        "O arquivo traz só o nome de cada sensor, sem dizer o que ele mede nem a unidade. O "
        "programa sugere pelo nome; confira com o que você criou no SolidWorks."
    ),
    "col_mede": (
        "Tensão = a de von Mises ou a do limite superior (axial + flexão) das vigas, verificada ao "
        "escoamento. Componente = uma parte da tensão (axial, flexão, cisalhamento), só mostrada. "
        "Deslocamento, fator de segurança, força e momento como no sensor."
    ),
    "col_unidade": (
        "A unidade escolhida ao criar o sensor no SolidWorks (Tensão: quase sempre N/mm² = MPa; "
        "deslocamento: mm). O programa converte para MPa, mm, kN e kN·m."
    ),
    "fy_automatico": (
        "O fator de segurança do SolidWorks é f_y/σ de cada ponto. Onde o FS mínimo cai no ponto "
        "da tensão máxima, σ·FS dá o f_y do aço: o programa usa esse valor (o menor que aparece). "
        "Desligue para digitar o f_y."
    ),
    "fy": "O limite de escoamento do aço da estrutura, em MPa (ASTM A36: 250; A572 Gr 50: 345).",
    "limite": (
        "Com que limite comparar este deslocamento nas combinações de serviço: um item das "
        "Tabelas 3 e 4 do critério Anglo (vigas de piso L/350, colunas H/400…), um L/x seu ou um "
        "valor em mm. O sensor é o maior deslocamento de onde ele foi posto: para a flecha de uma "
        "viga, ponha o sensor no meio do vão dela."
    ),
    "comprimento": (
        "O vão L da viga (ou a altura H da coluna, ou h entre pisos), em metros: o limite é esse "
        "comprimento dividido pelo número da tabela."
    ),
    "divisor": "O x de L/x: 350 dá L/350.",
    "maximo_mm": "O deslocamento máximo admitido, em mm.",
    "sec_conferencia": (
        "O quadro conferido contra o plano de cargas: casos e combinações que faltam, linhas com "
        "o mesmo resultado e combinações que não fecham com os coeficientes. Vermelho tira linhas "
        "da verificação; amarelo pede correção no SolidWorks ou no plano."
    ),
    "sec_resultados": (
        "Nas combinações últimas (ELU), o escoamento pela tensão do modelo e pelo fator de "
        "segurança; nas de serviço (ELS), o deslocamento de cada sensor contra o limite escolhido."
    ),
    "res_status": "O pior resultado das verificações: Atenção se o quadro está incompleto.",
    "res_aproveitamento": "A maior razão solicitante/resistente entre as verificações com limite.",
    "res_tensao": "A maior tensão nas combinações ELU (sem as que ficaram fora) e a combinação.",
    "res_fs": "O menor fator de segurança nas combinações ELU e a combinação.",
    "res_deslocamento": "O maior deslocamento nas combinações de serviço (ELS) e a combinação.",
    "sec_registrar": (
        "Grava no projeto ativo o capítulo do memorial: as verificações, o resumo de cada sensor, "
        "as combinações que governam, o quadro completo e o gráfico."
    ),
}
