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
    "sec_adicionar": (
        "Inclua uma ação à mão (pesos, equipamentos, ponte rolante, impacto). O vento chega das "
        "páginas de vento com um clique. Uma ação com código que já existe é substituída."
    ),
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
    "res_combinacoes": (
        "Combinações numeradas, com os fatores de cada ação: use o número como nome do caso "
        "combinado no modelo. Ações do mesmo grupo (vento) nunca entram juntas."
    ),
    "res_anglo": (
        "As combinações mínimas do critério Anglo (5.9) e os códigos que o plano ainda não tem. "
        "PRV, HT, HL e MO só existem se houver ponte rolante ou monovia."
    ),
    "res_exportar": (
        "CSV com ponto e vírgula e vírgula decimal (abre no Excel): as ações, as cargas para o "
        "modelo e as combinações com os fatores."
    ),
    "btn_csv_acoes": "Ações com categoria, γ e ψ.",
    "btn_csv_cargas": "Cargas para lançar no SolidWorks ou no Robot (valores característicos).",
    "btn_csv_comb": "Combinações numeradas com o fator de cada ação.",
}
