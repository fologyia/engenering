"""Textos dos “?” das páginas Base técnica do projeto e Plano de cargas, em linguagem simples."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    # ------------------------------------------------------------------ base técnica
    "sec_mapa": (
        "O caminho do projeto no programa: 1) base técnica; 2) as ações que cada página gera; 3) o "
        "plano de cargas com as combinações; 4) as verificações; 5) o memorial. As marcas dizem o "
        "que o projeto ativo já tem."
    ),
    "sec_cliente": (
        "O critério de projeto do cliente que vale além das normas. Com o da Anglo American, as "
        "páginas passam a começar com o vento de Conceição do Mato Dentro, os limites de "
        "deslocamento da Tabela 4 e as exigências de ligações, espessuras e diâmetros mínimos."
    ),
    "cliente": (
        "**Somente as normas**: NBR 6123, NBR 8800 e as demais, sem critério de cliente. "
        "**Anglo American AA-BR-DPST-DR-0001 Rev. 1**: o critério de estruturas metálicas do "
        "Sistema Minas-Rio."
    ),
    "sec_local": (
        "O vento do local, preenchido uma vez: as páginas de vento e de contraventamento começam "
        "com estes valores. A pressão dinâmica sai de q = 0,613·(V₀·S₁·S₂·S₃)²."
    ),
    "local": "Município ou unidade (só para identificar; o vento sai dos campos abaixo).",
    "v0": "Velocidade básica V₀ do mapa de isopletas da NBR 6123 (m/s). Anglo 5.6: 35 m/s.",
    "s1": "Fator topográfico S₁: 1,0 em terreno plano; 0,9 em vale; acima de 1 em morro. Anglo: 1,0.",
    "categoria": (
        "Rugosidade do terreno (NBR 6123, 5.3): II campo aberto; III obstáculos baixos e esparsos; "
        "IV zona industrial ou urbana densa; V cidade grande. O critério Anglo pede avaliar em "
        "cada edificação."
    ),
    "s3": (
        "Fator estatístico S₃ (NBR 6123:2023, Tabela 4): grupo 3 = indústrias (1,00); grupo 4 = "
        "sem ocupação humana (0,95). O critério Anglo fixa 0,95 — veja o aviso de conflito."
    ),
    "s3_cliente": "Valor de S₃ que o critério do cliente manda usar.",
    "sec_estrutura": (
        "O tipo de estrutura define o limite do deslocamento horizontal sob vento; a sobrecarga "
        "de referência entra no plano de cargas e nas páginas que pedem sobrecarga."
    ),
    "tipo": (
        "Plataforma de equipamentos: H/400 (Anglo, Tabela 4). Pipe rack: H/250. Estrutura com "
        "cobertura: H/400 com vento. Pelas regras só da NBR: H/300 com um pavimento; H/400 e "
        "h/500 com dois ou mais."
    ),
    "sobrecarga_local": (
        "O tipo de área na Tabela 2 do critério Anglo (sobrecargas mínimas), ou "
        "“Informada pelo projeto” para digitar o valor."
    ),
    "sobrecarga": "Sobrecarga de uso em kN/m², quando informada pelo projeto.",
    "agressividade": (
        "Categoria de corrosividade atmosférica (NBR 8800 Anexo N e ISO 12944-2): C1 muito "
        "baixa a C5/CX muito alta. Define proteção e eventual sobre-espessura (Anglo 6.1 e 6.2)."
    ),
    "vida_util": "Vida útil de projeto em anos (Anglo 4.4: o projeto deve indicar).",
    "observacoes": "Anotações da base técnica (sai no registro do projeto).",
    "btn_salvar": "Grava a base técnica no projeto ativo; as páginas passam a usá-la.",
    "res_q": "Pressão dinâmica a 10 m de altura com os valores acima (para conferência).",
    "res_limite": "Limite do deslocamento horizontal do topo sob vento para o tipo escolhido.",
    "res_sobrecarga": "Sobrecarga de referência que as páginas vão usar.",
    "res_figura_limite": (
        "O deslocamento horizontal do topo sob o vento (δ) não pode passar do limite do tipo de "
        "estrutura escolhido: H dividido pelo número da tabela, e o máximo em mm quando houver."
    ),
    "res_grafico_q": (
        "Como a pressão dinâmica q cresce com a altura no terreno da base (S₂ da NBR 6123:2023). "
        "As classes dependem da maior dimensão da superfície que recebe o vento."
    ),
    "sec_consulta": (
        "O critério Anglo AA-BR-DPST-DR-0001 Rev. 1 em tabelas, com o item de cada valor, para "
        "consultar sem abrir o PDF."
    ),
    "vib_ne": "Frequência própria da estrutura de apoio (Hz), do modelo ou do SolidWorks Simulation.",
    "vib_nm": "Frequência de operação do equipamento (Hz) = rotação (rpm) ÷ 60.",
    "vib_rpm": "Rotação do equipamento (rpm), para as amplitudes admissíveis A_v ≤ 240/n e A_h ≤ 300/n.",
    "res_vib": "Faixa em que a relação Ne/Nm cai (5.7) e o coeficiente dinâmico.",
    # ------------------------------------------------------------------ plano de cargas
    "sec_plano": (
        "As ações do projeto com código padrão, a origem de cada uma e as cargas que vão para o "
        "modelo. Valores característicos: as combinações saem daqui com os coeficientes da NBR 8800."
    ),
    "sec_conferencia": (
        "O que falta ou não fecha antes de exportar: peso próprio, sobrecarga, vento nas quatro "
        "direções, temperatura nos dois sentidos, ação sem carga para o modelo, unidade trocada, "
        "carga sem direção e, com o critério Anglo, as combinações mínimas (5.9)."
    ),
    "sec_adicionar": (
        "Inclua uma ação à mão (pesos, equipamentos, ponte rolante, impacto) ou escolha um código "
        "que já está no plano para editá-lo: os campos trazem o que está gravado. O vento chega "
        "das páginas de vento com um clique."
    ),
    "btn_editar": "Abre esta ação no formulário abaixo para corrigir cargas, nome ou categoria.",
    "codigo": (
        "PP peso próprio; PE permanentes de elementos (piso, guarda-corpo, tubulação); EQ "
        "equipamento vazio; EO conteúdo em operação; SC sobrecarga; W0/W90/W180/W270 vento; "
        "T+/T− temperatura; PRV/HT/HL ponte rolante; MO monovia; IM impacto; EX excepcional."
    ),
    "nome": "Nome da ação (vazio usa o nome padrão do código).",
    "categoria_nbr": "Categoria da NBR 8800 (Tabelas 1 e 2): define γ, γ favorável e ψ0, ψ1, ψ2.",
    "descricao": "O que a ação representa e de onde vêm os valores.",
    "cargas_tabela": (
        "Uma linha por carga que vai para o modelo: elemento (pórtico, viga, nó), valor, unidade "
        "e direção. Pode ficar vazia se você só quer a ação nas combinações."
    ),
    "btn_adicionar": "Grava a ação no plano de cargas do projeto ativo.",
    "btn_sobrecarga": "Inclui a ação SC com a sobrecarga da base técnica, em todos os pisos.",
    "btn_temperatura": "Inclui T+ e T− (±10 °C, Anglo 5.8) num grupo exclusivo.",
    "btn_remover": "Tira esta ação do plano de cargas.",
    "estados": (
        "ELU normal; especial ou de construção; excepcional (precisa de ação EX); ELS rara "
        "(danos irreversíveis), frequente (reversíveis) e quase permanente (aspecto)."
    ),
    "ver_como": (
        "Matriz: uma linha por combinação e uma coluna por ação, com o fator γ·ψ (o mesmo "
        "arranjo do gerenciador de casos de carga do SolidWorks). Expressões: a soma por extenso."
    ),
    "res_combinacoes": (
        "Combinações numeradas, com os fatores de cada ação: use o número como nome do caso "
        "combinado no modelo. Ações do mesmo grupo (vento) nunca entram juntas."
    ),
    "res_anglo": (
        "As combinações mínimas do critério Anglo (5.9) e os códigos que o plano ainda não tem. "
        "PRV, HT, HL e MO só existem se houver ponte rolante ou monovia."
    ),
    "sec_modelo": (
        "Tudo o que vai para o modelo, nas unidades e nos eixos do programa de destino: as "
        "cargas de cada caso com F_x, F_y e F_z já com sinal e o comando equivalente no "
        "SolidWorks e no Robot, e as combinações. A planilha Excel traz também um passo a passo."
    ),
    "unidades_destino": (
        "N e mm para o SolidWorks no sistema MMGS; N e m para o SolidWorks no SI; kN e m para o "
        "Robot, o SAP2000 e o Ftool. A conversão vale para força, carga por metro, por área e "
        "momento; a temperatura fica em °C."
    ),
    "eixos_destino": (
        "No SolidWorks a vertical costuma ser o eixo Y (o Y da planta vira −Z); no Robot e no "
        "SAP2000, o Z. As componentes F_x, F_y e F_z saem já nos eixos escolhidos."
    ),
    "res_convencao": (
        "Para que lado sopra cada vento (W0 = +X, W90 = +Y, W180 = −X, W270 = −Y), qual é o eixo "
        "vertical e como os eixos do plano viram os do SolidWorks."
    ),
    "res_previa": (
        "Uma linha por carga: o caso (código), o tipo (força, carga por metro, por área, "
        "temperatura, gravidade), onde aplicar, o valor convertido, as componentes e o comando "
        "do SolidWorks. O PP sem cargas vira a gravidade do modelo."
    ),
    "btn_xlsx": (
        "Planilha com as abas Leia-me (passo a passo no SolidWorks, no Robot e em outros "
        "programas), Ações, Cargas, Combinações (matriz) e Combinações (lista)."
    ),
    "btn_csv_acoes": "Ações com categoria, γ e ψ.",
    "btn_csv_cargas": "Cargas de cada caso nas unidades e eixos escolhidos, com F_x, F_y e F_z.",
    "btn_csv_matriz": "Uma linha por combinação e uma coluna por ação, com o fator.",
    "btn_csv_lista": (
        "Uma linha por ação de cada combinação (combinação, caso, fator): o formato que SAP2000, "
        "ETABS e STAAD importam."
    ),
}
