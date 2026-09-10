import pandas as pd
import streamlit as st

from components.ui import cabecalho_pagina


def mostrar_tabela_campos(linhas: list[list[str]]) -> None:
    st.dataframe(
        pd.DataFrame(linhas, columns=["Campo", "Preencha com", "De onde obter"]),
        hide_index=True,
    )


def mostrar_exemplo(linhas: list[list[str]], observacao: str | None = None) -> None:
    with st.container(border=True):
        st.badge(
            "Exemplo prático",
            icon=":material/science:",
            color="violet",
        )
        st.subheader("Valores para reproduzir")
        st.dataframe(
            pd.DataFrame(linhas, columns=["Entrada", "Valor do exemplo"]),
            hide_index=True,
        )
        if observacao:
            st.caption(observacao)


def link_modulo(destino: str, rotulo: str) -> None:
    st.page_link(
        destino,
        label=rotulo,
        icon=":material/arrow_forward:",
        icon_position="right",
        width="stretch",
    )


st.set_page_config(
    page_title="Guia geral",
    page_icon=":material/help:",
    layout="wide",
)

cabecalho_pagina(
    "Guia geral do Mecânica Toolkit",
    "Coleta de dados • preenchimento • exemplos práticos • interpretação dos resultados",
    categoria="Ajuda",
    icone=":material/help:",
    cor="green",
)
st.info(
    "Se for sua primeira vez, comece por **Comece aqui**. Depois selecione o "
    "módulo que deseja usar.",
    icon=":material/route:",
)

opcoes = [
    "Comece aqui",
    "Projetos permanentes",
    "Casos de carga",
    "Central de validação",
    "Central de relatórios",
    "Materiais técnicos",
    "Assistente de projeto",
    "Conversor de unidades",
    "Análise estática",
    "Vigas e eixos",
    "Flambagem de colunas",
    "Análise de fadiga",
    "Assistente de cargas",
    "Círculo de Mohr",
    "Análise de sensibilidade",
    "Projeto de parafusos",
    "Normas técnicas",
    "Estruturas de aço",
]
solicitado = st.query_params.get("modulo", "Comece aqui")
if solicitado not in opcoes:
    solicitado = "Comece aqui"
with st.container(border=True):
    st.badge("Navegação do guia", icon=":material/menu_book:", color="blue")
    modulo = st.selectbox(
        "O que você quer aprender?",
        opcoes,
        index=opcoes.index(solicitado),
        key="guia_modulo",
    )


if modulo == "Comece aqui":
    st.header("Escolha o caminho pelos dados que você possui")
    caminhos = pd.DataFrame(
        [
            [
                "Quero guardar dados, cálculos e revisões entre sessões",
                "Projetos permanentes",
                "Criar a base rastreável do trabalho",
            ],
            [
                "Tenho operação, partida, parada, teste ou emergência",
                "Casos de carga",
                "Criar combinações e identificar o cenário governante",
            ],
            [
                "Preciso localizar bloqueios e pendências de emissão",
                "Central de validação",
                "Tratar a fila consolidada do projeto",
            ],
            [
                "Preciso emitir um memorial Word ou PDF",
                "Central de relatórios",
                "Selecionar seções e registros da revisão ativa",
            ],
            [
                "Não sei qual análise usar",
                "Assistente de projeto",
                "Montar a sequência e o checklist",
            ],
            [
                "Dados em unidades diferentes das telas",
                "Conversor de unidades",
                "Converter antes de preencher os campos",
            ],
            [
                "Forças, momentos, torque, pressão e dimensões",
                "Assistente de cargas",
                "Obter σx, σy e τxy",
            ],
            [
                "σx, σy e τxy em um ponto",
                "Análise estática",
                "Verificar von Mises e segurança",
            ],
            [
                "Tensor 2D/3D de uma simulação",
                "Círculo de Mohr",
                "Transformar o plano e achar tensões principais",
            ],
            [
                "Peça esbelta sob compressão (coluna, escora, tirante invertido)",
                "Flambagem de colunas",
                "Obter esbeltez e a carga crítica de Euler/Johnson",
            ],
            [
                "Carga ou tensão máxima e mínima de um ciclo",
                "Análise de fadiga",
                "Obter tensão média, alternada e vida",
            ],
            [
                "Desenho da junta, parafusos e cargas de serviço",
                "Projeto de parafusos",
                "Conferir aperto, separação, atrito e chapa",
            ],
            [
                "Geometria, apoios e ações de uma estrutura",
                "Estruturas de aço",
                "Verificar barras, ligações e análise 2D",
            ],
            [
                "Contrato, norma citada ou PDFs técnicos",
                "Normas técnicas",
                "Localizar referências e conferir o texto por página",
            ],
        ],
        columns=["O que você tem", "Comece em", "Objetivo imediato"],
    )
    st.dataframe(caminhos, hide_index=True)

    coleta, unidades = st.columns(2)
    with coleta:
        with st.container(border=True, height="stretch"):
            st.subheader("Como coletar os dados")
            st.markdown(
                """
                1. Desenhe a peça ou estrutura e marque os apoios.
                2. Faça um diagrama de corpo livre.
                3. Separe cada caso de carga: peso, uso, vento, torque e pressão.
                4. Identifique a seção e o ponto onde a tensão será avaliada.
                5. Meça a geometria no desenho, CAD ou peça.
                6. Obtenha o material no certificado, norma ou fabricante.
                """
            )
    with unidades:
        with st.container(border=True, height="stretch"):
            st.subheader("Unidades mais usadas")
            st.markdown(
                r"""
                - $1\ \mathrm{MPa}=1\ \mathrm{N/mm^2}$
                - $1\ \mathrm{kN}=1\,000\ \mathrm{N}$
                - $1\ \mathrm{N\,m}=1\,000\ \mathrm{N\,mm}$
                - $1\ \mathrm{kN\,m}=10^6\ \mathrm{N\,mm}$
                - $1\ \mathrm{GPa}=1\,000\ \mathrm{MPa}$

                Sempre siga a unidade escrita no rótulo do campo.
                """
            )

    st.subheader("Fontes usuais")
    fontes = pd.DataFrame(
        [
            ["Carga", "Diagrama de corpo livre, memorial estrutural ou equipamento"],
            ["Dimensão", "Desenho técnico, CAD, catálogo ou medição"],
            ["Sy/Fy e Sut/Fu", "Certificado do material, norma ou fabricante"],
            ["Tensor de tensão", "Mesmo ponto e mesmo incremento da simulação"],
            ["Apoio e comprimento", "Modelo estrutural e detalhe construtivo"],
            ["Coeficientes", "Norma aplicável e condição real de fabricação/montagem"],
        ],
        columns=["Dado", "Fonte recomendada"],
    )
    st.dataframe(fontes, hide_index=True)

    with st.expander("Glossário rápido", icon=":material/dictionary:"):
        st.markdown(
            """
            - **σ:** tensão normal; positiva em tração e negativa em compressão.
            - **τ:** tensão de cisalhamento.
            - **Sy ou Fy:** limite de escoamento.
            - **Sut ou Fu:** resistência última à tração.
            - **E e G:** módulos de elasticidade longitudinal e transversal.
            - **N, V e M:** esforço normal, cortante e momento fletor.
            - **T:** torque.
            - **Utilização:** demanda dividida pela resistência; até 1 não excede
              a capacidade calculada.
            - **Fator de segurança:** resistência dividida pela demanda; deve ser
              comparado com a meta adotada no projeto.
            """
        )

    st.warning(
        "Nunca junte o maior valor de uma componente com outra componente obtida "
        "em um ponto ou caso de carga diferente.",
        icon=":material/pin_drop:",
    )


elif modulo == "Projetos permanentes":
    st.header("Sistema permanente de projetos industriais")
    st.write(
        "Use esta área como a pasta-mestre do trabalho. O projeto fica salvo em banco local "
        "mesmo depois de fechar o navegador, e cada cálculo pode ser registrado nele."
    )
    mostrar_tabela_campos(
        [
            ["Nome e código", "Identificação única do trabalho", "Ordem de serviço, contrato ou padrão interno"],
            ["Unidade, área e TAG", "Local e sistema físico", "Cadastro de ativos, fluxograma ou desenho"],
            ["Objetivo", "O que deve ser verificado e decidido", "Escopo aprovado pelo solicitante"],
            ["Base dos carregamentos", "Casos, combinações e condições", "Memorial de processo, operação, modelo ou DCL"],
            ["Critérios de aceitação", "Limites de tensão, utilização, flecha, vida etc.", "Norma, especificação ou requisito do cliente"],
            ["Escopo físico", "Equipamentos, linhas, estruturas e pontos", "Lista de TAGs e desenhos controlados"],
            ["Matriz normativa", "Código, edição, aplicação e fonte", "Contrato, legislação e análise de aplicabilidade"],
        ]
    )
    st.subheader("Sequência recomendada")
    st.markdown(
        """
        1. Clique em **Novo projeto** e preencha a identificação mínima.
        2. Em **Dados e base**, registre objetivo, documentos, condições de operação e critérios.
        3. Em **Escopo físico**, cadastre cada TAG ou ponto analisado.
        4. Estruture operação, partida, parada, teste e exceções em **Casos de carga**.
        5. Em **Normas**, registre a edição e marque *Conferida* somente após abrir o documento-fonte.
        6. Execute os módulos e clique em **Registrar no projeto ativo**.
        7. Mantenha responsáveis, prazos e evidências em **Checklist**.
        8. Crie uma **revisão controlada** antes de uma emissão ou mudança relevante.
        9. Exporte o arquivo JSON como cópia transportável do projeto.
        """
    )
    mostrar_exemplo(
        [
            ["Nome", "Adequação do transportador CV-204"],
            ["Código", "PRJ-2026-014"],
            ["Unidade / área", "Planta Sul / Expedição"],
            ["TAG", "CV-204"],
            ["Objetivo", "Verificar estrutura para aumento de capacidade de 80 para 110 t/h"],
            ["Base dos carregamentos", "Peso próprio + material + partida + bloqueio do chute"],
            ["Critério", "Utilização ≤ 1,0 e flecha conforme especificação do cliente"],
        ],
        "Depois de salvar, abra Estruturas de aço ou outro módulo aplicável e registre cada resultado no mesmo projeto.",
    )
    st.warning(
        "Salvamentos comuns atualizam os dados atuais. A revisão controlada cria um marco histórico. "
        "Restaurar um marco não apaga a história: cria uma nova revisão a partir dele."
    )
    link_modulo("app_pages/gestao_projetos.py", "Abrir projetos permanentes")


elif modulo == "Casos de carga":
    st.header("Casos, combinações e envelopes de carga")
    st.write(
        "Esta central organiza as condições físicas antes do cálculo de tensões ou da análise estrutural. "
        "Cada caso guarda um vetor completo; cada combinação registra exatamente quais fatores foram usados."
    )
    mostrar_tabela_campos(
        [
            ["Código e nome", "Identificação única do cenário", "Lista de cargas, DCL ou memorial de processo"],
            ["Condição", "Operação, partida, parada, teste, emergência etc.", "Filosofia operacional e análise de risco"],
            ["Natureza", "Permanente, variável, térmica, pressão, ambiental etc.", "Origem física da ação"],
            ["TAG", "Equipamento, linha, suporte ou estrutura afetada", "Cadastro do projeto e desenhos"],
            ["Fx, Fy, Fz", "Forças com sinais nos eixos comuns", "DCL, relatório de processo ou modelo"],
            ["Mx, My, Mz", "Momentos simultâneos do mesmo cenário", "Ponto de referência declarado"],
            ["Pressão e ΔT", "Pressão relativa e variação térmica", "Folha de dados e casos operacionais"],
            ["Origem / referência", "Documento, revisão e método de obtenção", "Fonte controlada do projeto"],
        ]
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Defina um sistema de eixos e um ponto comum para os momentos.
        2. Cadastre cada cenário físico em uma linha, mantendo juntas as ações simultâneas.
        3. Salve os casos antes de criar combinações.
        4. Crie uma combinação, selecione os casos e informe cada fator explicitamente.
        5. Repita para operação, resistência, serviço, teste e condições excepcionais aplicáveis.
        6. No envelope, confira o mínimo, o máximo e a combinação governante de cada componente.
        7. Abra o vetor completo governante antes de transferir esforços para outra análise.
        8. Registre o envelope no projeto para que o contrato, a validação e o memorial o rastreiem.
        """
    )
    mostrar_exemplo(
        [
            ["LC-01", "Peso operacional: Fy = -100 kN; Mx = 12 kN·m"],
            ["LC-02", "Expansão térmica: Fx = 30 kN; Mx = -5 kN·m; ΔT = 80 °C"],
            ["COMB-OP", "1,0×LC-01 + 1,0×LC-02"],
            ["COMB-TESTE", "1,3×LC-01"],
            ["Envelope Fy", "-130 kN, governado por COMB-TESTE"],
            ["Envelope Fx", "+30 kN, governado por COMB-OP"],
        ],
        "Os valores de Fy e Fx são governados por combinações diferentes; eles não formam automaticamente um único vetor simultâneo.",
    )
    st.warning(
        "O aplicativo não define fatores normativos. Confirme-os na norma, especificação, contrato ou base de projeto aplicável."
    )
    link_modulo("app_pages/casos_carga.py", "Abrir casos e combinações de carga")


elif modulo == "Central de validação":
    st.header("Central de validação e prontidão documental")
    st.write(
        "A central reúne o que está incompleto ou incompatível. Ela lê o projeto inteiro, "
        "não apenas o módulo aberto, e transforma os problemas em uma fila priorizada."
    )
    st.dataframe(
        pd.DataFrame(
            [
                ["Bloqueio", "Impede tratar o projeto como pronto", "Matriz normativa vazia, utilização > 1 ou checklist crítico aberto"],
                ["Pendência", "Precisa ser preenchida ou concluída", "Conclusão ausente ou referência ainda não conferida"],
                ["Atenção", "Exige julgamento e registro da decisão", "Material sem fonte ou cadeia de aprovação incompleta"],
                ["Informação", "Orienta a leitura", "Avisos metodológicos e de escopo"],
            ],
            columns=["Severidade", "Significado", "Exemplo"],
        ),
        hide_index=True,
    )
    st.subheader("Como tratar um achado")
    st.markdown(
        """
        1. Filtre por **Bloqueio** para começar pelo que impede a emissão.
        2. Abra o achado e leia detalhe, módulo e ação recomendada.
        3. Se a solução exigir trabalho, converta o achado em item do checklist.
        4. Defina responsável, prazo e evidência na Gestão de projetos.
        5. Corrija a origem: base de projeto, norma, registro técnico ou escopo físico.
        6. Volte à central e confirme que o achado desapareceu ou mudou de severidade.
        """
    )
    mostrar_exemplo(
        [
            ["Achado", "EST-07: utilização da barra = 1,12"],
            ["Severidade", "Bloqueio"],
            ["Ação", "Rever perfil, travamento, carregamento ou modelo"],
            ["Responsável", "Engenharia estrutural"],
            ["Evidência de fechamento", "MC-204 Rev. 02 com utilização = 0,84"],
        ],
        "O achado só deve ser encerrado quando a correção e a evidência estiverem registradas.",
    )
    st.info(
        "O índice documental mede preenchimento e rastreabilidade. Não é percentual de segurança, "
        "certificação normativa nem aprovação automática."
    )
    link_modulo("app_pages/central_validacao.py", "Abrir central de validação")


elif modulo == "Central de relatórios":
    st.header("Central modular de relatórios")
    st.write(
        "A central gera Word e PDF a partir da mesma revisão do projeto. Você escolhe o perfil, "
        "as seções, a ordem dos capítulos e os registros técnicos que entram na emissão."
    )
    st.dataframe(
        pd.DataFrame(
            [
                ["Resumo executivo", "Decisão rápida e situação geral", "Escopo, itens, normas, validação e conclusão"],
                ["Memorial industrial completo", "Revisão técnica e arquivo do projeto", "Todas as seções, cargas, registros e apêndices"],
                ["Dossiê de validação", "Tratamento de lacunas e liberação", "Base, normas, cálculos, achados e checklist"],
                ["Memorial de cálculos", "Verificação detalhada", "Plano, materiais, capítulos, sensibilidade e conclusão"],
            ],
            columns=["Perfil", "Uso", "Conteúdo sugerido"],
        ),
        hide_index=True,
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Abra a revisão correta do projeto permanente.
        2. Escolha o perfil e ajuste as seções.
        3. Marque os registros aplicáveis, defina a ordem e trate as lacunas de integridade.
        4. Preencha código, revisão, situação, elaborador, verificador e aprovador.
        5. Confira o sumário, a integridade, a prontidão e o hash do snapshot.
        6. Gere os dois formatos. Use o Word na revisão e o PDF na distribuição controlada.
        7. Se algum dado mudar, crie a revisão adequada e gere os arquivos novamente.
        """
    )
    mostrar_exemplo(
        [
            ["Perfil", "Memorial industrial completo"],
            ["Documento", "MC-CV204-001"],
            ["Revisão", "02"],
            ["Situação", "Para verificação"],
            ["Registros", "Casos de carga; combinações; análise 2D; verificação das barras"],
            ["Formatos", "DOCX para comentários + PDF para protocolo"],
        ],
        "O relatório preserva a conclusão de cada registro e lista os achados da Central de Validação.",
    )
    st.warning(
        "Gerar o documento não aprova o projeto. Antes da emissão, confira fontes, cálculos, "
        "edições normativas, pendências e assinaturas."
    )
    link_modulo("app_pages/central_relatorios.py", "Abrir central de relatórios")


elif modulo == "Materiais técnicos":
    st.header("Materiais com confiança e proveniência")
    st.write(
        "A página separa o catálogo orientativo da biblioteca do projeto. O primeiro ajuda a estimar; "
        "a segunda registra o que realmente sustenta o cálculo."
    )
    st.dataframe(
        pd.DataFrame(
            [
                ["Referência", "Valor típico ou literatura", "Não liberar cálculo final"],
                ["Condicional", "Parte da origem está documentada", "Completar lacunas e aplicabilidade"],
                ["Rastreável", "Norma, fabricante ou documento controlado", "Conferir condição e produto"],
                ["Confirmado", "Certificado do lote ou ensaio conferido", "Ainda requer aprovação de engenharia"],
            ],
            columns=["Nível", "Evidência típica", "Uso recomendado"],
        ),
        hide_index=True,
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Abra o projeto correto e identifique o item/TAG.
        2. Use o catálogo apenas para iniciar ou cadastre manualmente a designação exata.
        3. Informe condição, forma do produto, espessura/faixa dimensional e lote quando houver.
        4. Transcreva somente as propriedades presentes na fonte aplicável.
        5. Registre emissor, documento, edição, página/cláusula, data e quem conferiu.
        6. Explique por que a fonte se aplica à temperatura e ao produto real.
        7. Vincule o material aos componentes do escopo e trate as pendências da Central de Validação.
        """
    )
    mostrar_exemplo(
        [
            ["TAG", "SK-101"],
            ["Material", "Chapa de aço estrutural, condição conforme compra"],
            ["Produto", "Chapa 12,5 mm"],
            ["Origem", "Certificado do lote / MTR"],
            ["Documento", "MTR-45821, lote HN24017"],
            ["Aplicabilidade", "Mesma corrida, espessura e condição do item instalado"],
        ],
        "Não copie propriedades de outro lote. Se a temperatura de projeto estiver fora da faixa cadastrada, trate a propriedade como pendente.",
    )
    link_modulo("app_pages/materiais_tecnicos.py", "Abrir materiais técnicos")


elif modulo == "Análise de sensibilidade":
    st.header("Sensibilidade e incerteza")
    st.write(
        "Use esta análise depois que o modelo determinístico estiver funcionando. Ela responde duas perguntas: "
        "qual entrada governa e qual a chance de o resultado cruzar o limite informado?"
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Escolha um modelo industrial ou carregue um registro estático/fadiga do projeto.
        2. Confira os valores nominais e as unidades.
        3. Informe a incerteza de cada entrada. Na Normal, o percentual é 1σ; na Uniforme e Triangular, é meia faixa.
        4. Defina a variação OAT para a leitura local, normalmente ±5% a ±15%.
        5. Informe o critério: saída menor ou igual ao limite, ou maior ou igual ao limite.
        6. Execute e leia o ranking, a elasticidade, a curva, P05–P95 e o risco de não atendimento.
        7. Registre o resultado no projeto para incluí-lo automaticamente no memorial.
        """
    )
    mostrar_exemplo(
        [
            ["Modelo", "Flecha de viga biapoiada"],
            ["q / L / E / I", "5 kN/m / 4.000 mm / 200 GPa / 80.000.000 mm⁴"],
            ["Incertezas", "q ±10%; L ±2%; E ±5%; I ±8%"],
            ["Critério", "flecha ≤ 13,3 mm"],
            ["Amostras", "3.000, semente 42"],
        ],
        "Como a flecha varia com L⁴, o vão tende a apresentar elasticidade próxima de 4 e merece controle dimensional cuidadoso.",
    )
    st.warning("Distribuições escolhidas sem base metrológica ou histórica podem produzir uma precisão apenas aparente.")
    link_modulo("app_pages/analise_sensibilidade.py", "Abrir análise de sensibilidade")


elif modulo == "Assistente de projeto":
    st.header("Assistente de projeto em quatro etapas")
    st.markdown(
        """
        Use esta tela quando o problema ainda está desorganizado ou quando você
        não sabe qual módulo deve abrir primeiro. O assistente registra o projeto
        na sessão, recomenda uma sequência e transfere entradas compatíveis.
        """
    )
    mostrar_tabela_campos(
        [
            ["Nome e descrição", "Componente e função", "Desenho, ordem de serviço ou escopo"],
            ["Objetivo", "O que deseja calcular ou verificar", "Pergunta de engenharia do projeto"],
            ["Dados disponíveis", "Cargas, tensões, ciclo, junta ou estrutura", "Medição, CAD, cálculo ou simulação"],
            ["Regime", "Estático, variável/cíclico ou desconhecido", "Histórico de operação"],
            ["Checklist", "Itens já conferidos", "DCL, material, casos de carga e norma"],
        ]
    )
    st.subheader("Como usar")
    st.markdown(
        """
        1. Dê um nome ao projeto e descreva a função do componente.
        2. Escolha o objetivo e indique quais dados já possui.
        3. Preencha os valores iniciais na unidade em que foram obtidos.
        4. Confira a sequência, o checklist e a prévia dos valores convertidos.
        5. Ative o projeto, abra o módulo e complete os detalhes específicos.
        6. Use a Visão geral para retomar o projeto durante a mesma sessão.
        """
    )
    mostrar_exemplo(
        [
            ["Nome", "Suporte da bomba"],
            ["Componente", "Peça, barra, eixo ou viga"],
            ["Objetivo", "Verificar resistência estática"],
            ["Dados disponíveis", "Forças, momentos e dimensões"],
            ["Regime", "Estático"],
            ["Modelo inicial", "Viga de seção retangular"],
        ],
        "A rota será Assistente de cargas → Análise estática. Primeiro obtenha "
        "σx, σy e τxy; depois compare von Mises com a resistência do material.",
    )
    st.info(
        "O projeto ativo aparece nos cabeçalhos. Ele dura durante a sessão atual "
        "do navegador; ainda não é um arquivo salvo em disco.",
        icon=":material/folder_open:",
    )
    link_modulo("app_pages/assistente_projeto.py", "Abrir assistente de projeto")


elif modulo == "Conversor de unidades":
    st.header("Conversor global de unidades")
    st.markdown(
        """
        O conversor reúne comprimento, área, volume, força, tensão/pressão,
        momento/torque, carga distribuída, massa, densidade, temperatura,
        ângulo, rotação, velocidade, potência e energia.
        """
    )
    mostrar_tabela_campos(
        [
            ["Grandeza", "Tipo físico do dado", "Rótulo, desenho ou ficha técnica"],
            ["Valor", "Número recebido da fonte", "Medição ou relatório"],
            ["Unidade de origem", "Unidade usada pela fonte", "Cabeçalho da tabela ou instrumento"],
            ["Unidade de destino", "Unidade indicada no campo do app", "Rótulo do módulo de cálculo"],
        ]
    )
    st.subheader("Como usar")
    st.markdown(
        """
        1. Selecione a grandeza antes das unidades.
        2. Digite o valor e escolha origem e destino.
        3. Copie o resultado completo, preservando o sinal.
        4. Use **Trocar** para conferir a conversão de volta.
        5. Consulte a tabela de equivalências para detectar erro de escala.
        6. A tela mostra até seis algarismos significativos, mantendo a precisão interna.
        """
    )
    mostrar_exemplo(
        [
            ["Grandeza", "Tensão e pressão"],
            ["Valor", "10"],
            ["Origem", "ksi"],
            ["Destino", "MPa"],
            ["Resultado", "68,9476 MPa"],
        ],
        "Esse resultado pode ser usado em um campo de tensão ou resistência em MPa.",
    )
    st.warning(
        "Não confunda kg com kgf. Massa e força são grandezas diferentes. "
        "Lembre também que 1 N/mm² = 1 MPa e 1 N/mm = 1 kN/m.",
        icon=":material/warning:",
    )
    link_modulo("app_pages/conversor_unidades.py", "Abrir conversor de unidades")


elif modulo == "Análise estática":
    st.header("Análise estática")
    st.markdown(
        "Use quando você já conhece as componentes **σx, σy e τxy no mesmo "
        "ponto** e quer comparar o estado de tensão com o material."
    )
    mostrar_tabela_campos(
        [
            ["σx", "Tensão normal na direção x, em MPa", "Assistente, fórmula ou simulação"],
            ["σy", "Tensão normal na direção y, em MPa", "Assistente, fórmula ou simulação"],
            ["τxy", "Cisalhamento no plano xy, em MPa", "Torção, cortante ou simulação"],
            ["Sy", "Limite de escoamento, em MPa", "Certificado ou base do material"],
            ["Sut", "Resistência à ruptura, em MPa", "Certificado ou base do material"],
        ]
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Selecione um material ou escolha entrada manual.
        2. Informe as três tensões usando a mesma convenção de eixos.
        3. Informe Sy e Sut e clique em **Calcular análise**.
        4. Leia von Mises e o fator contra escoamento.
        5. Use as tensões principais para entender tração e compressão extremas.
        """
    )
    mostrar_exemplo(
        [
            ["σx", "100 MPa"],
            ["σy", "20 MPa"],
            ["τxy", "30 MPa"],
            ["Sy", "250 MPa"],
            ["Sut", "400 MPa"],
        ],
        "Resultado esperado: σ1 = 110 MPa, σ2 = 10 MPa, von Mises ≈ "
        "105,36 MPa e fator contra escoamento ≈ 2,37.",
    )
    with st.container(border=True):
        st.subheader("Como interpretar")
        st.markdown(
            """
            - **von Mises < Sy:** o escoamento não é previsto pelo modelo.
            - **Fator < 1:** a resistência informada foi excedida.
            - **Fator entre 1 e a meta:** resiste nominalmente, mas a margem pode
              ser insuficiente.
            - O gráfico de utilização mostra quanto de Sy e Sut foi consumido.
            """
        )
    st.warning(
        "A análise não adiciona concentração de tensão, impacto, flambagem, "
        "temperatura ou fadiga automaticamente.",
        icon=":material/warning:",
    )
    link_modulo("app_pages/analise_estatica.py", "Abrir a análise estática")


elif modulo == "Vigas e eixos":
    st.header("Vigas e eixos")
    st.markdown(
        "Use para uma **barra reta** (viga, eixo, mão-francesa, tirante fletido) "
        "quando você quer os diagramas de **cortante V(x)**, **momento fletor "
        "M(x)**, a **linha elástica** (flecha) e, se houver, **torção** e "
        "**carga axial** agindo juntas — o caso de *cargas combinadas*."
    )
    st.info(
        "O modelo é digitado, não desenhado: cada linha é um comando com "
        "números. Isso torna o modelo fácil de revisar, copiar entre projetos e "
        "colar num memorial — e o mesmo texto é gerado automaticamente quando "
        "você prefere preencher pelo formulário.",
        icon=":material/keyboard:",
    )

    st.subheader("Os apoios da Tabela 12.1")
    st.dataframe(
        pd.DataFrame(
            [
                ["Rolete", "rolete", "Δ = 0, M = 0", "Impede só o deslocamento vertical"],
                ["Pino", "pino", "Δ = 0, M = 0", "Impede vertical e horizontal"],
                ["Extremidade fixa", "engaste", "Δ = 0, θ = 0", "Impede deslocamento e rotação"],
                ["Extremidade livre", "(não declare nada)", "V = 0, M = 0", "Ponta em balanço"],
                ["Pino / articulação interna", "rotula", "M = 0", "Transmite V e N, libera o giro"],
                ["Engaste deslizante", "deslizante", "θ = 0, V = 0", "Guiado: gira travado, desliza livre"],
                ["Apoio elástico", "mola kv=… kr=…", "F = −k·Δ", "Recua sob carga, em vez de travar"],
            ],
            columns=["Situação", "Como escrever", "O que vale no ponto", "O que o apoio impede"],
        ),
        hide_index=True,
    )
    st.caption(
        "A extremidade livre não precisa de comando: tudo que você não declara "
        "como apoio já é livre."
    )

    st.subheader("Como preencher")
    mostrar_tabela_campos(
        [
            ["`viga L`", "Comprimento total em metros", "Desenho ou medição"],
            ["`secao ...`", "Geometria da seção em mm, ou um perfil do catálogo", "Desenho da peça"],
            ["`material ...`", "Atalho (aco, aluminio…) ou E, G e Sy próprios", "Certificado do material"],
            ["`apoio x tipo`", "Posição em metros e tipo do apoio", "Projeto / condição de montagem"],
            ["`P x valor`", "Força concentrada em kN (negativo = para baixo)", "Casos de carga"],
            ["`q x1 x2 w1 [w2]`", "Distribuída em kN/m; com w2 vira trapezoidal", "Peso, pressão, empuxo"],
            ["`M x valor`", "Momento concentrado em kN·m", "Excentricidade, engaste vizinho"],
            ["`N x valor`", "Carga axial em kN (positivo = tração)", "Tirante, coluna-viga"],
            ["`T x valor`", "Torque em kN·m", "Engrenagem, polia, acoplamento"],
        ]
    )
    st.markdown(
        "Se preferir digitar só a intensidade, escreva o sentido no fim da "
        "linha: `P 3 20 baixo` é o mesmo que `P 3 -20`. Vale também "
        "`compressao` para carga axial."
    )

    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Escolha um exemplo pronto parecido com o seu caso — é mais rápido do
           que começar do zero.
        2. Ajuste o comprimento, a seção e o material.
        3. Coloque os apoios: **duas** restrições verticais (ou um engaste)
           deixam a viga estável. Apoios a mais tornam a viga hiperestática, e
           o programa resolve assim mesmo.
        4. Lance as cargas. Positivo é para cima, então cargas de gravidade são
           negativas (ou use o sufixo `baixo`).
        5. Clique em **Calcular diagramas** e leia as abas: cortante e momento,
           linha elástica, normal e torção, tensões.
        6. Confira as **reações** e o resíduo de equilíbrio (deve ser ~0).
        """
    )

    mostrar_exemplo(
        [
            ["Comprimento", "6 m"],
            ["Seção", "Perfil W ideal 200×200×8×12 do catálogo"],
            ["Material", "aço (E = 200 GPa, Sy = 250 MPa)"],
            ["Apoios", "pino em x = 0 e rolete em x = 6 m"],
            ["Carga distribuída", "15 kN/m para baixo em todo o vão"],
            ["Carga pontual", "20 kN para baixo em x = 3 m"],
        ],
        "Resultado esperado: reações de 55 kN em cada apoio, V máx = 55 kN nos "
        "apoios, M máx = 97,5 kN·m no meio do vão, flecha máxima de 37,21 mm "
        "para baixo (também no meio) e von Mises de 211,5 MPa, com fator de "
        "segurança 1,18 contra o escoamento. A flecha não passa em L/350 "
        "(17,14 mm admissíveis) — é um caso em que a resistência atende, mas o "
        "deslocamento não.",
    )

    with st.container(border=True):
        st.subheader("Como interpretar cada diagrama")
        st.markdown(
            """
            - **Cortante V(x):** salta exatamente no ponto de cada carga
              concentrada; o salto vale a própria carga. Onde `V = 0`, o momento
              é máximo ou mínimo.
            - **Momento M(x):** positivo comprime a fibra de cima. Num apoio de
              extremidade sem engaste, `M = 0`; numa rótula interna, também.
            - **Linha elástica:** é a flecha real em mm, negativa para baixo.
              Compare com o critério `L/350` (ou o que o seu projeto exigir) —
              resistência e deslocamento são verificações separadas.
            - **Normal N(x):** positivo traciona. Somado à flexão, é o que
              caracteriza a *carga combinada*.
            - **Torque T(x) e giro φ:** constantes entre dois torques aplicados.
            - **von Mises:** avaliado na fibra superior, na inferior e na linha
              neutra; o gráfico mostra o pior dos três. Por isso a flexão máxima
              e o cisalhamento máximo normalmente **não** ocorrem no mesmo
              ponto da seção.
            """
        )

    with st.container(border=True):
        st.subheader("Vários cenários de carga na mesma barra")
        st.markdown(
            """
            Quando a mesma viga precisa ser verificada sob combinações
            diferentes, marque cada carga com o caso a que ela pertence e
            declare as combinações:

            ```text
            q 0 8 12 baixo                 # sem caso=, logo Permanente
            q 0 8 20 baixo caso=Sobrecarga
            q 0 8 8 cima   caso=Vento

            combinacao ELU_gravidade Permanente=1.4 Sobrecarga=1.5
            combinacao ELU_vento     Permanente=1.0 Vento=1.4
            ```

            O programa resolve a barra **uma vez por combinação** e abre a aba
            **Envoltória**, com a faixa que as cargas podem produzir em cada
            seção e uma tabela dizendo qual combinação governa cada grandeza —
            que quase nunca é a mesma para todas.

            Dois cuidados:

            - um caso que **não** aparece na combinação entra com fator zero;
            - as demais abas continuam mostrando a barra **sem** fatores, como
              você escreveu. Os valores de projeto são os da envoltória.

            Se o projeto ativo já tem combinações cadastradas em *Casos e
            combinações de carga*, o botão acima do editor as importa prontas.
            """
        )

    with st.container(border=True):
        st.subheader("Levar a seção adiante")
        st.markdown(
            """
            Depois de calcular, a seção **7** manda a seção escolhida direto
            para outro módulo, sem você anotar e redigitar número nenhum:

            - **Círculo de Mohr** e **Análise estática** recebem σx e τxy da
              seção — por padrão a mais solicitada, mas você pode escolher a de
              momento máximo, de cortante máximo ou uma posição qualquer.
            - **Análise de fadiga** recebe σa e σm. Marque *"a barra gira"* se
              for eixo de transmissão: aí a flexão vira tensão totalmente
              alternada. Numa viga fixa o momento é estático e não há ciclo —
              o programa não inventa um.
            - Se você já registrou a análise no projeto, o módulo de destino
              guarda de onde os valores vieram, e a Central de Validação avisa
              se a viga mudar depois.
            """
        )

    with st.container(border=True):
        st.subheader("Erros comuns")
        st.markdown(
            """
            - **Carga para cima sem querer:** o sinal positivo é para cima. Se a
              flecha deu positiva, provavelmente falta o sinal ou o sufixo
              `baixo`.
            - **"O modelo é instável":** faltam apoios. Um rolete sozinho não
              segura a viga; use pino + rolete, ou um engaste.
            - **Rótula deixando um trecho solto:** cada trecho entre rótulas
              precisa de apoio suficiente, senão vira mecanismo.
            - **Unidade trocada:** posições em metros, seção em milímetros. Um
              `viga 6000` cria uma viga de 6 km.
            """
        )

    st.warning(
        "O modelo é linear e de Euler-Bernoulli: não amplifica a flecha pela "
        "compressão (efeito P–Δ), não verifica flambagem, não inclui deformação "
        "por cisalhamento (relevante quando L/h < 10) nem concentração de "
        "tensão em entalhes e rasgos de chaveta.",
        icon=":material/warning:",
    )
    link_modulo("app_pages/vigas_eixos.py", "Abrir vigas e eixos")


elif modulo == "Flambagem de colunas":
    st.header("Flambagem de colunas")
    st.markdown(
        "Use para uma **peça esbelta sob compressão** (coluna, escora, haste "
        "de cilindro, montante comprimido) — a tensão σ = F/A sozinha não "
        "avisa quando a peça vai flambar antes de escoar."
    )
    mostrar_tabela_campos(
        [
            ["Seção", "Geometria da peça (retangular, circular, tubo, perfil ou A/r direto)", "Desenho ou catálogo do perfil"],
            ["L", "Comprimento real da coluna, em mm", "Desenho ou montagem"],
            ["Condição de apoio", "K teórico do caso mais próximo do apoio real", "Croqui de fixação nas extremidades"],
            ["E", "Módulo de elasticidade do material, em MPa", "Certificado ou catálogo"],
            ["Sy", "Limite de escoamento, em MPa", "Certificado ou base do material"],
            ["P", "Força de compressão atuante, em kN (só magnitude)", "Assistente de cargas ou análise do equipamento"],
        ]
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Escolha o tipo de seção e informe suas dimensões (ou perfil de catálogo).
        2. Informe o comprimento real e a condição de apoio mais próxima da real.
        3. Informe E, Sy e a força de compressão atuante.
        4. Compare a esbeltez governante com a esbeltez de transição.
        5. Leia o regime (Euler ou Johnson) e a carga admissível.
        """
    )
    mostrar_exemplo(
        [
            ["Seção", "Circular maciça, d = 50 mm"],
            ["L", "2000 mm"],
            ["Condição de apoio", "Biapoiada (pino-pino), K = 1,0"],
            ["E", "200000 MPa"],
            ["Sy", "250 MPa"],
            ["P", "50 kN"],
        ],
        "Resultado esperado: λ ≈ 160 (maior que λ de transição ≈ 125,7, "
        "portanto regime de Euler); Pcr ≈ 151,4 kN; com fator de segurança "
        "2,0 a carga admissível é ≈ 75,7 kN — utilização de 66% para os 50 kN "
        "aplicados.",
    )
    with st.container(border=True):
        st.subheader("Como interpretar")
        st.markdown(
            """
            - **λ ≥ λ de transição:** regime de **Euler** — coluna longa,
              carga crítica cai com o quadrado do comprimento destravado.
            - **λ < λ de transição:** regime de **Johnson** — coluna curta ou
              intermediária, Euler sozinho superestimaria a resistência.
            - **Eixo governante:** o de maior esbeltez — geralmente o eixo
              mais "fraco" (menor raio de giração) ou com maior K·L.
            - **Utilização > 100%:** a carga admissível (crítica ÷ fator de
              segurança escolhido) foi excedida.
            - Dobrar o comprimento destravado L divide a carga crítica de
              Euler por 4 — é a variável mais sensível deste cálculo.
            """
        )
    st.warning(
        "Este é o modelo elementar de Euler/Johnson: compressão centrada, "
        "coluna prismática, sem imperfeições, excentricidade, flambagem "
        "local/torcional ou efeitos de 2ª ordem. Para perfis de aço conforme "
        "norma (NBR 8800/AISC), use Estruturas de aço.",
        icon=":material/warning:",
    )
    link_modulo("app_pages/flambagem_colunas.py", "Abrir Flambagem de colunas")


elif modulo == "Análise de fadiga":
    st.header("Análise de fadiga")
    st.markdown(
        "Use quando a solicitação se repete. Mesmo tensões abaixo de Sy podem "
        "causar falha após muitos ciclos."
    )
    mostrar_tabela_campos(
        [
            ["Sut e Sy", "Resistências do material, em MPa", "Certificado ou base"],
            ["Tipo de carga", "Flexão, axial ou torção", "Funcionamento da peça"],
            ["Tamanho", "Diâmetro ou geometria resistente, em mm", "Desenho/CAD"],
            ["Acabamento", "Retificado, usinado, laminado ou forjado", "Processo"],
            ["Temperatura", "Temperatura da peça em °C ou °F", "Condição de serviço"],
            ["Confiabilidade", "Probabilidade de sobrevivência desejada", "Critério do projeto"],
            ["σa e σm", "Tensão alternada e média, em MPa", "Ciclo máximo e mínimo"],
        ]
    )
    st.markdown(
        r"""
        Se você possui as tensões extremas do ciclo:

        $$
        \sigma_a=\frac{\sigma_{\max}-\sigma_{\min}}{2},\qquad
        \sigma_m=\frac{\sigma_{\max}+\sigma_{\min}}{2}
        $$
        """
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Escolha a referência dos fatores de Marin.
        2. Preencha material, carregamento, tamanho, acabamento, temperatura e
           confiabilidade.
        3. Confira o limite corrigido Se.
        4. Informe o entalhe e a tensão alternada nominal.
        5. Informe a tensão média e leia Goodman, Soderberg e a curva S–N.
        6. Preencha identificação, componente, referência, meta de segurança, vida requerida e aprovações; baixe o memorial editável em Word ou o PDF para impressão.
        """
    )
    mostrar_exemplo(
        [
            ["Material", "Aço, Sut = 600 MPa e Sy = 400 MPa"],
            ["Carregamento", "Flexão"],
            ["Diâmetro", "20 mm"],
            ["Acabamento", "Usinado ou estirado a frio"],
            ["Temperatura", "20 °C (equivalente a 68 °F)"],
            ["Confiabilidade", "90%"],
            ["Tensão máxima", "180 MPa"],
            ["Tensão mínima", "20 MPa"],
            ["Tensão alternada σa", "80 MPa"],
            ["Tensão média σm", "100 MPa"],
        ],
        "Use Kt = 1 no primeiro teste, caso a seção não tenha entalhe. Depois "
        "substitua pelo valor obtido para a geometria real.",
    )
    with st.container(border=True):
        st.subheader("Como interpretar")
        st.markdown(
            """
            - **Se:** limite de resistência corrigido para a peça real.
            - **Goodman:** usa Sut e costuma ser menos conservador.
            - **Soderberg:** usa Sy e costuma ser mais conservador.
            - **n > 1:** o ponto está abaixo da fronteira do critério, mas a meta
              real pode exigir margem maior.
            - **Vida finita:** é uma estimativa da curva S–N, não uma garantia.
            """
        )
    st.info(
        "No modelo Norton, a Equação 6.7f é expressa em °F. Selecione °F para "
        "digitar diretamente os valores do livro. Exemplo: 500 °F = 260 °C "
        "e produz Ctemp = 0,710."
    )
    with st.container(border=True):
        st.markdown("**Memorial padronizado em Word**")
        st.markdown(
            "Preencha projeto, componente, referência, metas, responsáveis e situação. "
            "O DOCX começa com um resumo executivo básico e depois apresenta a memória "
            "completa, critérios de aceitação, pendências, checklist, aprovações e integração "
            "com as demais partes do projeto."
        )
    st.warning(
        "Não use a tensão máxima como σa. Calcule separadamente a parcela média "
        "e a alternada do mesmo ciclo.",
        icon=":material/warning:",
    )
    link_modulo("app_pages/analise_fadiga.py", "Abrir a análise de fadiga")


elif modulo == "Assistente de cargas":
    st.header("Assistente de cargas e geometrias")
    st.markdown(
        "Use quando você conhece **cargas e dimensões**, mas ainda não possui as "
        "componentes de tensão."
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Escolha a geometria que melhor representa a peça.
        2. Informe dimensões e carregamentos nas unidades mostradas.
        3. Escolha o ponto ou o lado da flexão.
        4. Confira σx, σy e τxy.
        5. Leia as hipóteses do modelo.
        6. Use **Enviar para o Círculo de Mohr** para continuar.
        """
    )
    mostrar_exemplo(
        [
            ["Modelo", "Eixo circular maciço"],
            ["Diâmetro d", "30 mm"],
            ["Força axial F", "10 kN de tração"],
            ["Momento fletor |M|", "500 N·m"],
            ["Torque T", "300 N·m"],
            ["Ponto na flexão", "Lado tracionado"],
        ],
        "Saída aproximada: σx = 202,78 MPa, σy = 0 MPa e τxy = 56,59 MPa.",
    )
    with st.container(border=True):
        st.subheader("Como escolher o ponto")
        st.markdown(
            """
            - Na flexão, confira os lados tracionado e comprimido.
            - Em uma viga retangular, a tensão normal é maior nas fibras externas
              e o cisalhamento é maior próximo do centroide.
            - Em eixos, a torção é avaliada na superfície externa.
            - Em vasos, evite regiões próximas de bocais, soldas e tampas quando
              usar as fórmulas simples de membrana.
            """
        )
    st.warning(
        "Os modelos simples não incluem automaticamente furos, chavetas, soldas, "
        "contato ou outros concentradores de tensão.",
        icon=":material/warning:",
    )
    link_modulo("app_pages/assistente_cargas.py", "Abrir o assistente de cargas")


elif modulo == "Círculo de Mohr":
    st.header("Círculo de Mohr e transformação de tensões")
    st.markdown(
        "Use para descobrir as tensões em um plano inclinado, as tensões "
        "principais e o cisalhamento máximo no ponto."
    )
    mostrar_tabela_campos(
        [
            ["σx, σy e τxy", "Componentes do estado plano, em MPa", "Assistente, fórmula ou simulação"],
            ["θ", "Rotação física do eixo x para x'", "Orientação do plano desejado"],
            ["σz, τxz e τyz", "Componentes adicionais do estado 3D", "Tensor da simulação"],
            ["nx, ny e nz", "Normal do plano 3D", "Geometria ou CAD"],
        ]
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Use 2D somente quando σz, τxz e τyz forem desprezíveis.
        2. Informe todas as componentes no mesmo ponto e caso de carga.
        3. Em 2D, mova θ para girar o plano.
        4. Em 3D, informe a normal do plano por componentes ou ângulos.
        5. Leia σ1, σ2, σ3, τmáx e as componentes no plano escolhido.
        6. Selecione o material para comparar critérios de falha.
        """
    )
    mostrar_exemplo(
        [
            ["Tipo", "Estado plano 2D"],
            ["σx", "100 MPa"],
            ["σy", "20 MPa"],
            ["τxy", "30 MPa"],
            ["θ", "30° anti-horário"],
        ],
        "Resultado esperado: σ1 = 110 MPa, σ2 = 10 MPa, τmáx = 50 MPa, "
        "σx' ≈ 105,98 MPa e τx'y' ≈ −19,64 MPa.",
    )
    with st.container(border=True):
        st.subheader("Como copiar de elementos finitos")
        st.dataframe(
            pd.DataFrame(
                [
                    ["Sxx", "σx"],
                    ["Syy", "σy"],
                    ["Szz", "σz"],
                    ["Sxy", "τxy"],
                    ["Sxz", "τxz"],
                    ["Syz", "τyz"],
                ],
                columns=["Resultado da simulação", "Campo no programa"],
            ),
            hide_index=True,
        )
        st.caption(
            "Confirme sistema de coordenadas, unidade, posição, passo de carga e "
            "se o valor é nodal, elementar ou do ponto de integração."
        )
    with st.container(border=True):
        st.subheader("Como interpretar")
        st.markdown(
            """
            - **Tensões principais:** atuam em planos onde o cisalhamento é zero.
            - **Raio do círculo:** cisalhamento máximo do par representado.
            - **von Mises:** não muda quando os eixos são girados.
            - **σn e |τ|:** tração normal e cisalhante no plano 3D escolhido.
            - No círculo, o deslocamento angular tem o dobro do ângulo físico e
              sentido oposto pela convenção adotada.
            """
        )
    link_modulo("app_pages/circulo_mohr.py", "Abrir o Círculo de Mohr")


elif modulo == "Projeto de parafusos":
    st.header("Projeto de juntas parafusadas")
    st.markdown(
        "Use para uma junta pré-carregada com parafusos igualmente espaçados "
        "em um círculo."
    )
    mostrar_tabela_campos(
        [
            ["Rosca e classe", "Designação e classe do parafuso", "Desenho e certificado"],
            ["Número e círculo", "Quantidade e diâmetro entre parafusos opostos", "Desenho da junta"],
            ["K e incerteza", "Relação torque–pré-carga e dispersão", "Ensaio ou processo"],
            ["P, V, M e T", "Cargas de serviço da junta", "Análise do equipamento"],
            ["Atrito", "Coeficiente e número de interfaces", "Tratamento superficial/ensaio"],
            ["Chapa", "Espessura, furo, borda e resistências", "Detalhe e certificado"],
        ]
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Selecione rosca, classe, número e círculo de parafusos.
        2. Defina o processo de aperto e a pré-carga.
        3. Informe as cargas totais de serviço.
        4. Preencha atrito e geometria da chapa.
        5. Leia o torque especificado e o parafuso crítico.
        6. Confira prova, escoamento, ruptura, separação, deslizamento e chapa.
        7. Ative fadiga quando as cargas variarem.
        """
    )
    mostrar_exemplo(
        [
            ["Rosca e classe", "M12, classe 8.8"],
            ["Número / círculo", "4 parafusos / 100 mm"],
            ["Instalação", "Torque lubrificado"],
            ["Pré-carga / prova", "0,70"],
            ["K / incerteza / perda", "0,18 / ±25% / 5%"],
            ["Rigidez C", "0,25"],
            ["Carga axial P", "40 kN"],
            ["Cortante V", "20 kN"],
            ["Momento e torque no grupo", "0 N·m / 0 N·m"],
            ["Atrito / interfaces", "0,40 / 2"],
            ["Chapa", "t = 10 mm, furo = 13 mm, borda = 24 mm"],
            ["Limites da chapa", "250 MPa"],
            ["Fator mínimo desejado", "1,00"],
        ],
        "Resultados aproximados: torque nominal = 73,93 N·m; fator de prova "
        "= 1,08; separação = 3,25; deslizamento = 2,70. Use dados reais do "
        "processo de aperto antes de liberar o projeto.",
    )
    with st.container(border=True):
        st.subheader("Como interpretar")
        st.markdown(
            """
            - **Pré-carga mínima:** caso desfavorável para separação e atrito.
            - **Pré-carga máxima:** caso desfavorável para prova/escoamento.
            - **Parafuso crítico:** recebe a maior combinação distribuída.
            - **Separação < 1:** a compressão da junta pode ser perdida.
            - **Deslizamento < 1:** o atrito disponível é insuficiente.
            - **Esmagamento/rasgamento:** conferem a chapa junto ao furo e à borda.
            """
        )
    st.warning(
        "O torque depende fortemente do atrito. Para juntas críticas, use ensaio "
        "torque–pré-carga e procedimento de montagem controlado.",
        icon=":material/warning:",
    )
    link_modulo("app_pages/projeto_parafusos.py", "Abrir o projeto de parafusos")


elif modulo == "Normas técnicas":
    st.header("Biblioteca de normas técnicas")
    st.markdown(
        "Use esta página para descobrir quais famílias normativas devem ser "
        "conferidas e para pesquisar os PDFs que você mantém localmente."
    )
    mostrar_tabela_campos(
        [
            ["Pasta monitorada", "Pasta padrão ou outro caminho local", "Local onde você guarda PDFs licenciados"],
            ["Segmento", "Área do projeto", "Escopo, contrato e tipo de equipamento"],
            ["Edição", "Ano, emenda e errata", "Capa, catálogo oficial e especificação do cliente"],
            ["Busca", "Termos técnicos específicos", "Item que precisa ser confirmado no projeto"],
        ]
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Abra **Catálogo por segmento** e identifique as famílias relacionadas ao projeto.
        2. Copie seus PDFs para `normas_pdf` ou configure outra pasta local.
        3. Use nomes com organismo, código, ano e edição.
        4. Em **Meus PDFs**, selecione e indexe um arquivo para conferir metadados e OCR.
        5. Em **Pesquisar nos PDFs**, indexe a biblioteca e procure o requisito.
        6. Registre no memorial o arquivo, a edição, o item, a página e a decisão tomada.
        """
    )
    mostrar_exemplo(
        [
            ["Situação", "Verificação de uma viga de aço soldada"],
            ["Segmentos", "Estruturas de aço e ações; Soldagem e fabricação"],
            ["Referências iniciais", "ABNT NBR 8800 e código de soldagem contratual"],
            ["Nome do arquivo", "ABNT_NBR_8800_ANO_estruturas_aco.pdf"],
            ["Pesquisa", "flambagem lateral com torção"],
            ["Registro", "arquivo + página PDF + item normativo + hipótese"],
        ],
        "O catálogo sugere onde começar; a decisão final vem do escopo e do texto "
        "da edição exigida no projeto.",
    )
    with st.container(border=True):
        st.subheader("Como interpretar os diagnósticos")
        st.markdown(
            """
            - **Não identificada:** renomeie o PDF com o código ou confira a ficha manualmente.
            - **Cobertura baixa:** o arquivo provavelmente precisa de OCR.
            - **Duplicidade:** podem existir edições diferentes da mesma norma.
            - **Página PDF:** é a posição física e pode divergir do número impresso.
            - **Resultado de busca:** é apenas um trecho; leia definições, exceções e notas.
            """
        )
    st.warning(
        "Não misture coeficientes de normas diferentes e não use um resumo do catálogo "
        "como critério de aceitação.",
        icon=":material/warning:",
    )
    link_modulo("app_pages/normas_tecnicas.py", "Abrir normas técnicas")


else:
    st.header("Estruturas de aço")
    st.markdown(
        "A página reúne cinco ferramentas. Escolha abaixo a parte que deseja "
        "aprender; todas são de análise ou pré-dimensionamento."
    )
    parte = st.segmented_control(
        "Parte do módulo",
        ["Perfis", "Barras", "Combinações", "Ligações", "Análise 2D"],
        default="Perfis",
        required=True,
        width="stretch",
        key="guia_aco_parte",
    )

    if parte == "Perfis":
        st.subheader("1. Catálogo de perfis")
        st.markdown(
            """
            Use para consultar área, massa, inércias, módulos resistentes e raios
            de giração. Filtre a família e escolha um perfil para inspecionar.
            """
        )
        mostrar_exemplo(
            [
                ["Família", "Perfil I idealizado"],
                ["Perfil", "I ideal 200×100×5,5×8"],
            ],
            "Valores aproximados: área = 26,12 cm², massa = 20,50 kg/m, "
            "Ix = 1.760,93 cm⁴, Sx = 176,09 cm³ e ry = 2,26 cm.",
        )
        st.warning(
            "Os perfis são idealizações geométricas. Confirme propriedades e "
            "tolerâncias no catálogo comercial do fabricante.",
            icon=":material/warning:",
        )

    elif parte == "Barras":
        st.subheader("2. Verificação de barras")
        st.markdown(
            """
            Selecione o perfil e informe esforços já combinados. Para compressão,
            obtenha L e K das condições de apoio; para flexão, informe o comprimento
            destravado Lb. Q, Cv e Cb dependem da seção e do carregamento.
            """
        )
        mostrar_exemplo(
            [
                ["Perfil", "I ideal 200×100×5,5×8"],
                ["Material", "Fy = 250 MPa, Fu = 400 MPa, E = 200 GPa, G = 77 GPa"],
                ["Solicitação", "Compressão"],
                ["Nd / Mdx / Mdy / Vd", "100 kN / 20 kN·m / 0 / 20 kN"],
                ["L / Kx / Ky / Lb", "3 m / 1,0 / 1,0 / 3 m"],
                ["Q / Cv / Cb", "1,0 / 1,0 / 1,0"],
                ["Flecha", "Biapoiada, q = 5 kN/m e limite L/300"],
            ],
            "Resultado aproximado: resistência à compressão = 231,22 kN, "
            "interação N–M = 0,899 e flecha = 1,50 mm para limite de 10 mm.",
        )
        st.caption(
            "Utilização até 1 significa apenas que a demanda não excedeu a "
            "resistência calculada com os coeficientes informados."
        )

    elif parte == "Combinações":
        st.subheader("3. Combinações de ações")
        st.markdown(
            """
            Cada linha representa uma ação característica. Informe N, V e M com
            sinal, classifique-a como permanente ou variável e preencha γ e ψ
            conforme a norma e a situação de projeto.
            """
        )
        mostrar_exemplo(
            [
                ["G permanente", "N = 50 kN, V = 10 kN, M = 20 kN·m, γ = 1,40"],
                ["Q variável", "N = 30 kN, V = 5 kN, M = 15 kN·m, γ = 1,40, ψ0 = 0,70"],
                ["W+ variável", "V = 20 kN, M = 40 kN·m, γ = 1,40, ψ0 = 0,60"],
                ["W− variável", "V = −20 kN, M = −40 kN·m, γ = 1,40, ψ0 = 0,60"],
            ],
            "A tabela padrão já contém este exemplo. O envelope resulta em "
            "|N| = 112,0 kN, |V| = 30,1 kN e |M| = 65,1 kN·m.",
        )
        st.warning(
            "Os máximos de N, V e M podem pertencer a combinações diferentes. "
            "Não os trate como simultâneos sem conferir a linha correspondente.",
            icon=":material/warning:",
        )

    elif parte == "Ligações":
        st.subheader("4. Ligações estruturais")
        st.markdown(
            """
            Escolha entre parafusos, chapa/bloco e solda. Os esforços devem vir
            das combinações de cálculo na ligação, e as áreas líquidas devem ser
            calculadas a partir do detalhe dos furos.
            """
        )
        mostrar_exemplo(
            [
                ["Verificação", "Parafusos"],
                ["Rosca / classe / quantidade", "M20 / 8.8 / 4"],
                ["Planos de corte", "1"],
                ["Vd / Td", "100 kN / 20 kN"],
                ["Chapa", "t = 10 mm, Fu = 400 MPa, Lc = 30 mm"],
                ["Pré-tensão / atrito / interfaces", "50 kN / 0,30 / 1"],
            ],
            "Confira todos os fatores e a interação quadrática. Para uma junta "
            "mecânica completa, abra também Projeto de parafusos.",
        )
        st.caption(
            "Em soldas, informe a perna e o comprimento efetivo total. Em bloco "
            "de cisalhamento, use áreas brutas e líquidas obtidas do desenho."
        )

    else:
        st.subheader("5. Análise estrutural 2D")
        st.markdown(
            """
            - **Nó:** ponto com coordenadas, vínculos e cargas.
            - **Elemento:** barra que liga o nó i ao nó j.
            - **Treliça:** transmite somente esforço axial.
            - **Pórtico:** transmite esforço normal, cortante e momento.

            Comece pelo exemplo carregado na tela. Confira IDs e vínculos e clique
            em **Analisar estrutura**.
            """
        )
        mostrar_exemplo(
            [
                ["Modelo", "Treliça 2D padrão"],
                ["Nós", "(0,0), (4,0) e (2,3) m"],
                ["Apoios", "Nó 1 fixo em x/y; nó 2 fixo em y"],
                ["Carga", "Fy = −100 kN no nó 3"],
                ["Elementos", "1–2, 1–3 e 2–3"],
                ["Perfil / E", "I ideal 200×100×5,5×8 / 200 GPa"],
            ],
            "Este exemplo já está preenchido. Após analisar, confira primeiro "
            "reações e equilíbrio; depois leia deslocamentos e esforços axiais.",
        )
        st.warning(
            "O solver é linear e de primeira ordem. Não considera P–Δ, "
            "imperfeições, flambagem, plasticidade ou ligações semirrígidas.",
            icon=":material/warning:",
        )

    link_modulo("app_pages/estruturas_aco.py", "Abrir estruturas de aço")


st.caption(
    "Guia de uso do programa. Para projeto executivo, confirme propriedades, "
    "coeficientes, combinações e critérios na norma aplicável."
)
