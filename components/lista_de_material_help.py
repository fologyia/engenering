"""Textos dos “?” da página Lista de material, em linguagem simples (um teste exige cada um)."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    "sec_importar": (
        "Traga a lista de corte do SolidWorks em vez de digitar: o programa acha as colunas de "
        "quantidade, descrição e comprimento pelo nome e reconhece os perfis pela descrição."
    ),
    "arquivo": (
        "A lista de corte do SolidWorks em CSV ou Excel: o CSV que a macro desta seção gera ou o "
        "da tabela de lista de corte de um desenho (botão direito na tabela › Salvar como › CSV)."
    ),
    "btn_macro": (
        "Baixa a macro que exporta a lista de corte da peça aberta para CSV, sem desenho nem "
        "tabela. Abra o arquivo no Bloco de Notas, copie tudo e, no SolidWorks, use Ferramentas › "
        "Macro › Nova (dê um nome e salve), apague o texto do editor, cole e tecle F5. O CSV sai "
        "na pasta da peça; das próximas vezes, Ferramentas › Macro › Executar."
    ),
    "unidade": (
        "Unidade dos comprimentos que vêm sem unidade no arquivo. O SolidWorks costuma exportar em "
        "milímetros; se a célula disser mm, m, in ou ft, vale o que está escrito."
    ),
    "btn_acrescentar": "Junta as linhas lidas às que a lista já tem.",
    "btn_substituir": "Troca a lista inteira pelas linhas lidas do arquivo.",
    "sec_itens": (
        "Uma linha por item: perfil (quantidade × comprimento), chapa (comprimento × largura × "
        "espessura), grade ou piso (área × kg/m²) ou outro item (kg por unidade). Edite direto na "
        "tabela, acrescente ou apague linhas e grave."
    ),
    "acrescimo": (
        "Porcentagem somada à massa para as ligações, parafusos e soldas que a lista não traz "
        "(5 a 10 % é o usual em estruturas parafusadas)."
    ),
    "barra": (
        "Comprimento da barra comercial (6 ou 12 m) para estimar quantas barras comprar de cada "
        "perfil."
    ),
    "btn_gravar": "Grava a tabela, o acréscimo e a barra comercial no projeto ativo.",
    "btn_placas": (
        "Acrescenta a placa de base de cada pilar, com as medidas gravadas em Esforços do modelo "
        "(seção 9). Se já houver, troca pela placa atual."
    ),
    "sec_resumo": "Massa, peso e área de pintura da lista, com o acréscimo das ligações.",
    "res_massa": "Massa dos itens mais o acréscimo das ligações, parafusos e soldas.",
    "res_peso": "A massa total em peso (kN), para o orçamento de frete e montagem.",
    "res_pintura": (
        "Superfície a pintar: o contorno do perfil vezes o comprimento e as duas faces das chapas. "
        "Grades vêm galvanizadas e não entram."
    ),
    "res_pendentes": "Itens sem massa por falta de dado (comprimento, medidas ou kg/m).",
    "sec_perfis": (
        "Cada perfil com o comprimento total, a massa e as barras comerciais (estimativa sem "
        "otimização de corte nem perdas)."
    ),
    "sec_chapas": "As chapas agrupadas por espessura: peças, área e massa.",
    "sec_conferencia": (
        "Compara o peso da lista (sem o acréscimo) com a reação vertical do caso PP importado em "
        "Esforços do modelo. Diferença grande quer dizer barra faltando no modelo ou na lista."
    ),
    "sec_exportar": "A lista para o orçamento: Excel com o resumo, os itens, os perfis e as chapas.",
    "btn_xlsx": "A lista em Excel: resumo, itens, resumo por perfil e por espessura de chapa.",
    "btn_csv": "Os itens em CSV (abre no Excel).",
}
