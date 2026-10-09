import pandas as pd
import streamlit as st

from components.ui import cabecalho_pagina, configurar_pagina


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


def entrada_padrao_das_estruturas_abertas():
    """A entrada que as páginas de estruturas abertas abrem: perfis padrão do catálogo.

    O exemplo do guia precisa dar o mesmo número que a página mostra sem mexer em nada.
    """
    from components.contraventamento_estrutura_ui import PILAR_PADRAO, VIGA_PADRAO
    from core import contraventamento_plataforma as cp
    from core import section_catalog as sc

    pilar, viga = sc.obter_perfil(PILAR_PADRAO), sc.obter_perfil(VIGA_PADRAO)
    return cp.EntradaContraventamento(
        largura_pilar_m=max(pilar.altura_mm, pilar.largura_mm) / 1e3,
        altura_viga_m=viga.altura_mm / 1e3,
    )


def link_modulo(destino: str, rotulo: str) -> None:
    st.page_link(
        destino,
        label=rotulo,
        icon=":material/arrow_forward:",
        icon_position="right",
        width="stretch",
    )


configurar_pagina("Guia geral", ":material/help:")

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
    "Painel industrial",
    "Projetos permanentes",
    "Base técnica do projeto",
    "Plano de cargas",
    "Esforços do modelo",
    "Lista de material",
    "Casos de carga",
    "Central de validação",
    "Central de relatórios",
    "Materiais técnicos",
    "Assistente de projeto",
    "Conversor de unidades",
    "Análise estática",
    "Vigas e eixos",
    "Vento nas estruturas",
    "Flambagem de colunas",
    "Análise de fadiga",
    "Assistente de cargas",
    "Círculo de Mohr",
    "Análise de sensibilidade",
    "Projeto de parafusos",
    "Degrau de escada em grade",
    "Vigas de piso",
    "Vento em estruturas abertas",
    "Contraventamento de estruturas abertas",
    "Ligação de contraventamento",
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
    with st.container(border=True):
        st.badge("Projeto de estrutura metálica", icon=":material/route:", color="violet")
        st.subheader("O caminho em cinco etapas")
        st.markdown(
            """
            1. **Base técnica do projeto** — uma vez por projeto: critério do cliente (por exemplo
               o da Anglo American), V₀, S₁, terreno, S₃, tipo de estrutura e sobrecarga.
            2. **Ações** — cada página gera as suas: o vento em **Vento em estruturas abertas**
               (forças por nível, por pórtico e em cada nó), os pesos e a sobrecarga.
            3. **Plano de cargas** — as ações com código padrão (PP, SC, W0, W90…), as cargas para
               lançar no modelo (SolidWorks, Robot) e as combinações ELU e ELS numeradas.
            4. **Verificações** — os **Esforços do modelo** importados do SolidWorks (o pior
               caso de cada barra), contraventamento, ligação, barras, parafusos, degraus; cada
               cálculo registrado no projeto.
            5. **Memorial** — a Central de relatórios monta o Word e o PDF com o que foi
               registrado.
            """
        )
        st.caption(
            "A página inicial e as páginas das etapas mostram o caminho com o que o projeto ativo "
            "já tem."
        )
    st.header("Escolha o caminho pelos dados que você possui")
    caminhos = pd.DataFrame(
        [
            [
                "Tenho vários projetos e quero saber o que está travado ou vencido",
                "Painel industrial",
                "Ler a carteira inteira e escolher por onde atacar",
            ],
            [
                "Quero guardar dados, cálculos e revisões entre sessões",
                "Projetos permanentes",
                "Criar a base rastreável do trabalho",
            ],
            [
                "Projeto novo de estrutura metálica, com ou sem critério do cliente",
                "Base técnica do projeto",
                "Fixar vento do local, critério do cliente, limites e sobrecarga uma vez",
            ],
            [
                "Tenho as ações do projeto e vou montar o modelo",
                "Plano de cargas",
                "Ações com código padrão, cargas para o modelo e combinações numeradas",
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
                "Galpão ou edifício: preciso das forças do vento (paredes, telhado, pórtico)",
                "Vento nas estruturas",
                "Obter pressões por zona, vedações, forças globais e cargas do pórtico (NBR 6123:2023)",
            ],
            [
                "Peça esbelta sob compressão (coluna, escora, tirante invertido)",
                "Flambagem de colunas",
                "Verificar N_c,Rd = χ·Q·A_g·f_y/γ_a1 e a interação N + M pela NBR 8800",
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
                "Escada industrial em grade de piso eletrofundida (degrau Selmec)",
                "Degrau de escada em grade",
                "Espelho, piso, lances, modelo do catálogo e 38 verificações NR-12, NR-22 e Anglo",
            ],
            [
                "Plataforma ou pipe rack aberto: preciso só das forças do vento para o modelo",
                "Vento em estruturas abertas",
                "Força por nível, por pórtico e em cada nó, com desenho e CSV",
            ],
            [
                "Plataforma, mezanino ou pipe rack sem fechamento a contraventar",
                "Contraventamento de estruturas abertas",
                "Vento nos reticulados, combinações, B₂, diagonais e deslocamentos",
            ],
            [
                "Contraventamento vertical chegando ao canto viga–coluna por chapa de nó",
                "Ligação de contraventamento",
                "Forças nas interfaces pelo Método das Forças Uniformes e verificações do AISC 360-16",
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


elif modulo == "Painel industrial":
    st.header("Painel da carteira de projetos")
    st.write(
        "O painel lê todos os projetos do banco local e resume cada um numa linha comparável: "
        "situação, prontidão, bloqueios, pendências, avanço do checklist, prazos vencidos e "
        "cálculos desatualizados. É a pergunta inversa da página de projetos — não *o que falta "
        "neste projeto*, mas *quais projetos precisam de mim hoje*."
    )
    mostrar_tabela_campos(
        [
            [
                "Com bloqueio",
                "Projetos com ao menos um bloqueio na validação",
                "Regras da Central de validação",
            ],
            [
                "Prazos vencidos",
                "Itens de checklist abertos com prazo anterior a hoje",
                "Prazo gravado como data no checklist",
            ],
            [
                "Cálculos desatualizados",
                "Registros cujas fontes (material, caso de carga, critério, origem) mudaram",
                "Grafo de dependências dos registros",
            ],
            ["Parado (dias)", "Dias desde o último salvamento", "Linha do tempo do projeto"],
        ]
    )
    st.subheader("Como usar")
    st.markdown(
        """
        1. Leia o bloco **Atenção imediata**: são os projetos com resultado que não atende, bloqueio, prazo vencido ou cálculo desatualizado.
        2. Filtre por situação ou cliente e use a busca por código, TAG ou responsável.
        3. Em **Prazos vencidos e da semana**, cobre os responsáveis — a tabela junta todos os projetos.
        4. Escolha um projeto em **Próximos passos** para ver a ordem de trabalho sugerida e abri-lo como ativo.
        5. Baixe a carteira em CSV para reuniões de acompanhamento.
        """
    )
    st.info(
        "Índice documental e prontidão medem preenchimento e rastreabilidade no aplicativo. "
        "Não certificam conformidade nem substituem a aprovação de engenharia."
    )
    link_modulo("app_pages/painel_industrial.py", "Abrir painel industrial")


elif modulo == "Projetos permanentes":
    st.header("Sistema permanente de projetos industriais")
    st.write(
        "Use esta área como a pasta-mestre do trabalho. O projeto fica salvo em banco local "
        "mesmo depois de fechar o navegador, e cada cálculo pode ser registrado nele. Na versão web "
        "(Streamlit Cloud) o disco do servidor é apagado quando o aplicativo reinicia: baixe a "
        "carteira ao terminar ou ligue o espelho no GitHub (Painel industrial → Dados e backup)."
    )
    mostrar_tabela_campos(
        [
            [
                "Nome e código",
                "Identificação única do trabalho",
                "Ordem de serviço, contrato ou padrão interno",
            ],
            [
                "Unidade, área e TAG",
                "Local e sistema físico",
                "Cadastro de ativos, fluxograma ou desenho",
            ],
            [
                "Objetivo",
                "O que deve ser verificado e decidido",
                "Escopo aprovado pelo solicitante",
            ],
            [
                "Base dos carregamentos",
                "Casos, combinações e condições",
                "Memorial de processo, operação, modelo ou DCL",
            ],
            [
                "Critérios de aceitação",
                "Limites de tensão, utilização, flecha, vida etc.",
                "Norma, especificação ou requisito do cliente",
            ],
            [
                "Critérios técnicos",
                "n mínimo, utilização máxima, risco, temperatura, vida, norma principal e fatores",
                "Aba Critérios — é contra isso que a validação cobra os cálculos",
            ],
            [
                "Escopo físico",
                "Equipamentos, linhas, estruturas e pontos",
                "Lista de TAGs e desenhos controlados",
            ],
            [
                "Documentos de entrada",
                "Código, revisão, emitente e situação de cada documento recebido",
                "Lista de documentos do cliente ou do projeto",
            ],
            [
                "Matriz normativa",
                "Código, edição, aplicação e fonte",
                "Contrato, legislação e análise de aplicabilidade",
            ],
        ]
    )
    st.subheader("Sequência recomendada")
    st.markdown(
        """
        1. Clique em **Novo projeto**, escolha o **tipo** (define o modelo de checklist) e preencha a identificação mínima.
        2. Em **Dados e base**, registre objetivo, documentos, condições de operação e critérios.
        3. Em **Critérios**, defina fator de segurança mínimo, utilização máxima, norma principal e referência dos fatores — sem isso, vale o padrão do programa.
        4. Em **Escopo físico**, cadastre cada TAG ou ponto analisado; em **Documentos**, a lista controlada com revisão e situação.
        5. Estruture operação, partida, parada, teste e exceções em **Casos de carga**.
        6. Em **Normas**, registre a edição e marque *Conferida* somente após abrir o documento-fonte.
        7. Execute os módulos e clique em **Registrar no projeto ativo**. Um cálculo refeito supera o antigo em **Registros técnicos**, sem apagá-lo.
        8. Mantenha responsáveis, prazos (como data) e evidências em **Checklist**. O tipo do projeto semeia a lista com um modelo (estrutura, vaso, transportador, eixo ou genérico); outros modelos podem ser acrescentados depois, sem duplicar. O programa avisa o que venceu.
        9. Em **Fluxo e revisões**, avance a situação (elaboração → verificação → emitido); cada passagem confere o que falta. Crie uma **revisão controlada** antes de uma emissão e compare revisões para ver o que mudou.
        10. Exporte o arquivo JSON como cópia transportável do projeto.
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
        "Salvamentos comuns atualizam os dados atuais e ficam na linha do tempo. A revisão controlada cria um marco histórico. "
        "Restaurar um marco não apaga a história: cria uma nova revisão a partir dele.",
        icon=":material/warning:",
    )
    st.subheader("Fluxo de situação")
    st.dataframe(
        pd.DataFrame(
            [
                [
                    "Em elaboração → Em verificação",
                    "Verificador definido e ao menos um registro técnico vigente",
                    "Bloqueios abertos só avisam",
                ],
                [
                    "Em verificação → Emitido",
                    "Aprovador e verificador definidos, zero bloqueios, nenhum cálculo desatualizado",
                    "Cria revisão controlada",
                ],
                [
                    "Emitido → Em elaboração",
                    "Sempre permitida",
                    "Cria revisão controlada (a emitida continua restaurável)",
                ],
                [
                    "Qualquer → Suspenso / Arquivado",
                    "Sempre permitida",
                    "Registre o motivo na linha do tempo",
                ],
            ],
            columns=["Passagem", "O que exige", "Efeito"],
        ),
        hide_index=True,
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
            [
                "Código e nome",
                "Identificação única do cenário",
                "Lista de cargas, DCL ou memorial de processo",
            ],
            [
                "Condição",
                "Operação, partida, parada, teste, emergência etc.",
                "Filosofia operacional e análise de risco",
            ],
            [
                "Natureza",
                "Permanente, variável, térmica, pressão, ambiental etc.",
                "Origem física da ação",
            ],
            [
                "TAG",
                "Equipamento, linha, suporte ou estrutura afetada",
                "Cadastro do projeto e desenhos",
            ],
            [
                "Fx, Fy, Fz",
                "Forças com sinais nos eixos comuns",
                "DCL, relatório de processo ou modelo",
            ],
            [
                "Mx, My, Mz",
                "Momentos simultâneos do mesmo cenário",
                "Ponto de referência declarado",
            ],
            [
                "Pressão e ΔT",
                "Pressão relativa e variação térmica",
                "Folha de dados e casos operacionais",
            ],
            [
                "Origem / referência",
                "Documento, revisão e método de obtenção",
                "Fonte controlada do projeto",
            ],
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
        8. Registre o envelope no projeto para que o contrato e a validação o rastreiem (o memorial não reproduz casos e combinações).
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
        "O aplicativo não define fatores normativos. Confirme-os na norma, especificação, contrato ou base de projeto aplicável.",
        icon=":material/warning:",
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
                [
                    "Bloqueio",
                    "Impede tratar o projeto como pronto",
                    "Matriz normativa vazia, utilização > 1 ou checklist crítico aberto",
                ],
                [
                    "Pendência",
                    "Precisa ser preenchida ou concluída",
                    "Conclusão ausente ou referência ainda não conferida",
                ],
                [
                    "Atenção",
                    "Exige julgamento e registro da decisão",
                    "Material sem fonte ou cadeia de aprovação incompleta",
                ],
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
    st.header("Central de relatórios: o memorial de cálculo")
    st.write(
        "A central gera Word e PDF a partir da mesma revisão do projeto. Os cálculos "
        "registrados entram completos — entradas, equações, resultados, figuras, premissas "
        "e conclusão — e o que o programa não sabe fica marcado com “[a preencher]”, para "
        "completar no Word. Na flambagem de colunas e nas ligações parafusadas, cada análise "
        "abre com o resultado, lista o que passou e termina com o que não passou; um projeto "
        "pode ter quantas análises quiser, e a conclusão reúne o que não passou em todas. "
        "Você escolhe o perfil, as seções, a ordem dos capítulos e os registros que entram "
        "na emissão."
    )
    st.dataframe(
        pd.DataFrame(
            [
                [
                    "Memorial industrial completo",
                    "Revisão técnica e arquivo do projeto",
                    "Escopo, base, peças, materiais, quadro-resumo, memória de cálculo, "
                    "sensibilidade e conclusão",
                ],
                [
                    "Memorial de cálculos",
                    "Verificação detalhada",
                    "Escopo, base, quadro-resumo, memória de cálculo, vigas, sensibilidade "
                    "e conclusão",
                ],
                [
                    "Resumo executivo",
                    "Leitura rápida",
                    "Escopo, peças, materiais, quadro-resumo dos cálculos e conclusão",
                ],
                [
                    "Para incluir em outro documento",
                    "Capítulos que entram num memorial maior",
                    "Quadro-resumo, memória de cálculo e conclusão, sem capa, resumo "
                    "executivo, controle de revisões nem aprovações",
                ],
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
        3. Marque os cálculos aplicáveis e defina a ordem dos capítulos.
        4. Preencha código, revisão, situação, elaborador, verificador e aprovador.
        5. Confira o sumário planejado e gere os dois formatos.
        6. Complete no Word o que saiu como “[a preencher]” (Ctrl+F encontra tudo), revise e assine.
        7. Se algum dado mudar, crie a revisão adequada e gere os arquivos novamente.
        """
    )
    mostrar_exemplo(
        [
            ["Perfil", "Memorial industrial completo"],
            ["Documento", "MC-CV204-001"],
            ["Revisão", "02"],
            ["Situação", "Para verificação"],
            ["Cálculos", "Análise estática; flambagem da coluna; verificação das barras"],
            ["Formatos", "DOCX para completar e comentar + PDF para protocolo"],
        ],
        "O memorial preserva a conclusão de cada cálculo e deixa a conclusão geral para o responsável.",
    )
    st.warning(
        "Gerar o documento não aprova o projeto. Antes da emissão, confira fontes, cálculos, "
        "edições normativas e assinaturas.",
        icon=":material/warning:",
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
                [
                    "Condicional",
                    "Parte da origem está documentada",
                    "Completar lacunas e aplicabilidade",
                ],
                [
                    "Rastreável",
                    "Norma, fabricante ou documento controlado",
                    "Conferir condição e produto",
                ],
                [
                    "Confirmado",
                    "Certificado do lote ou ensaio conferido",
                    "Ainda requer aprovação de engenharia",
                ],
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
    st.warning(
        "Distribuições escolhidas sem base metrológica ou histórica podem produzir uma precisão apenas aparente.",
        icon=":material/warning:",
    )
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
            [
                "Dados disponíveis",
                "Cargas, tensões, ciclo, junta ou estrutura",
                "Medição, CAD, cálculo ou simulação",
            ],
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
            [
                "Unidade de destino",
                "Unidade indicada no campo do app",
                "Rótulo do módulo de cálculo",
            ],
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
                [
                    "Engaste deslizante",
                    "deslizante",
                    "θ = 0, V = 0",
                    "Guiado: gira travado, desliza livre",
                ],
                [
                    "Apoio elástico",
                    "mola kv=… kr=…",
                    "F = −k·Δ",
                    "Recua sob carga, em vez de travar",
                ],
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
            [
                "`secao ...`",
                "Geometria da seção em mm, ou um perfil do catálogo",
                "Desenho da peça",
            ],
            [
                "`material ...`",
                "Atalho (aco, aluminio…) ou E, G e Sy próprios",
                "Certificado do material",
            ],
            [
                "`apoio x tipo`",
                "Posição em metros e tipo do apoio",
                "Projeto / condição de montagem",
            ],
            ["`P x valor`", "Força concentrada em kN (negativo = para baixo)", "Casos de carga"],
            [
                "`q x1 x2 w1 [w2]`",
                "Distribuída em kN/m; com w2 vira trapezoidal",
                "Peso, pressão, empuxo",
            ],
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
            ["Seção", "Perfil W 200 x 46,1 (H) do catálogo"],
            ["Material", "aço (E = 200 GPa, Sy = 250 MPa)"],
            ["Apoios", "pino em x = 0 e rolete em x = 6 m"],
            ["Carga distribuída", "15 kN/m para baixo em todo o vão"],
            ["Carga pontual", "20 kN para baixo em x = 3 m"],
        ],
        "Resultado esperado: reações de 55 kN em cada apoio, V máx = 55 kN nos "
        "apoios, M máx = 97,5 kN·m no meio do vão, flecha máxima de 37,76 mm "
        "para baixo (também no meio) e von Mises de 217,8 MPa, com fator de "
        "segurança 1,15 contra o escoamento. A flecha não passa em L/350 "
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


elif modulo == "Vento nas estruturas":
    from core import vento_edificio as _ve
    from core import vento_portico as _vp

    st.header("Vento nas estruturas")
    st.markdown(
        "Use para o vento numa **edificação de planta retangular** — galpão, edifício, "
        "plataforma fechada — pela **NBR 6123:2023**: a pressão dinâmica do local, o "
        "coeficiente de forma **C_e de cada zona** das paredes e do telhado, a pressão "
        "interna, as pressões de projeto das **telhas e fixações**, a força de arrasto, a "
        "torção e as **cargas por metro de um pórtico transversal**, com a solução do pórtico. "
        "Para uma peça isolada (barra, perfil, painel de plataforma), use a calculadora de "
        "vento de Estruturas de aço."
    )
    mostrar_tabela_campos(
        [
            [
                "V₀",
                "Velocidade básica do vento, em m/s: a rajada de 3 s, a 10 m, que se repete a cada 50 anos",
                "Mapa de isopletas da NBR 6123 (Figura 1), pelo local da obra",
            ],
            [
                "Relevo (S₁), rugosidade (S₂), grupo (S₃)",
                "Plano, vale protegido ou topo de talude/morro; categoria I a V do terreno a barlavento; grupo 1 a 5 de importância",
                "Implantação da obra; ocupação (indústria e comércio = grupo 3)",
            ],
            [
                "Classe e altura de referência",
                "Automática pela maior dimensão da superfície que o vento enfrenta em cada direção; S₂ no topo da edificação",
                "Desenho do galpão; recomendação do item 5.3.3",
            ],
            [
                "Cobertura, θ, a, b, h",
                "Plana, duas águas ou uma água; inclinação em graus; comprimento ao longo da cumeeira (a ≥ b), largura (vão) e altura do beiral",
                "Desenho arquitetônico ou de formas",
            ],
            [
                "Espaçamento dos pórticos e T₁",
                "Distância entre pórticos (carga por metro) e período fundamental (0 = estimar; acima de 1 s a norma pede análise dinâmica)",
                "Projeto estrutural; análise modal",
            ],
            [
                "Permeabilidade (c_pi)",
                "Quatro faces permeáveis, duas faces opostas, estanque, valores informados ou abertura dominante",
                "Portões, janelas e frestas da edificação",
            ],
            [
                "Vizinhança e alta turbulência",
                "Afastamento da edificação alta vizinha (f_v até 1,3); vizinhança densa e alta a barlavento (sotavento × 2/3 e C_a da Figura 5)",
                "Implantação; item 6.1.3.1",
            ],
            [
                "Seção do pórtico",
                "Perfil do catálogo ou A e I, módulo de elasticidade, bases engastadas ou rotuladas e o limite de deslocamento H/…",
                "Pré-dimensionamento do pórtico",
            ],
        ]
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Informe o **local**: V₀, relevo, a categoria do terreno e o grupo. Se a vida útil ou
           o nível de segurança forem outros, ligue o **S₃ do Anexo B**.
        2. Descreva a **edificação**: tipo de cobertura, inclinação, `a` (ao longo da cumeeira,
           o lado maior), `b` (o vão), altura do beiral e espaçamento dos pórticos.
        3. Escolha a **permeabilidade**. Com portão grande aberto use o assistente de **abertura
           dominante**: ele calcula o c_pi da norma e o copia para os valores informados.
        4. Leia o **Resumo** (V_k e q de cada direção, q das vedações) e a aba **Pressões por zona**:
           o desenho mostra onde fica cada zona; Δp positiva empurra a superfície para dentro,
           negativa puxa para fora.
        5. Em **Vedações e fixações** estão as pressões de projeto de telhas, painéis, terças e
           travessas — nas arestas e cantos vale o c_pe médio, bem mais severo.
        6. **Forças globais** traz o arrasto (gráfico da norma), a soma das zonas, a torção e o
           atrito. Para contraventamento e fundação use o maior dos dois resultados.
        7. **Pórtico transversal** dá a carga por metro de cada elemento e resolve o pórtico com a
           seção que você informar. Resolva os casos e fique com o pior.
        8. Confira a tabela de **verificações** (se as tabelas valem para a sua construção) e
           **registre** no projeto: o memorial leva as tabelas inteiras.
        """
    )
    _exemplo = _ve.calcular_edificacao(
        _ve.EntradaEdificio(
            v0_m_s=40.0,
            comprimento_a_m=60.0,
            largura_b_m=30.0,
            altura_h_m=8.0,
            cobertura=_ve.COBERTURA_DUAS_AGUAS,
            theta_graus=10.0,
            categoria="III",
            grupo_s3=3,
            espacamento_porticos_m=6.0,
        )
    )
    _casos_exemplo = _vp.casos_do_portico(_exemplo)
    _caso_90 = next(c for c in _casos_exemplo if c.alpha == 90 and c.cpi.valor == -0.3)

    def _pt(valor: float, casas: int = 2) -> str:
        return f"{valor:.{casas}f}".replace(".", ",")

    mostrar_exemplo(
        [
            ["Local", "V₀ = 40 m/s, terreno plano, categoria III, grupo 3 (indústria)"],
            [
                "Edificação",
                "Galpão de 60 × 30 m, beiral a 8 m, duas águas a 10°; pórticos a cada 6 m",
            ],
            ["Pressão interna", "Quatro faces permeáveis: c_pi = −0,3 e c_pi = 0"],
        ],
        "Resultado esperado: a 0° o vento enfrenta 30 m (classe B) — V_k = "
        f"{_pt(_exemplo.vento_por_alpha[0].vk_m_s)} m/s e q = "
        f"{_pt(_exemplo.vento_por_alpha[0].q_kN_m2, 3)} kN/m²; a 90° enfrenta 60 m (classe C) — "
        f"V_k = {_pt(_exemplo.vento_por_alpha[90].vk_m_s)} m/s e q = "
        f"{_pt(_exemplo.vento_por_alpha[90].q_kN_m2, 3)} kN/m². Nas vedações (classe A) "
        f"q = {_pt(_exemplo.vento_vedacoes.q_kN_m2, 3)} kN/m². A parede de barlavento recebe "
        "C_e = +0,7 e, com c_pi = −0,3, Δp = q·(0,7 + 0,3); a água de barlavento a 90° leva "
        f"C_e = {_pt(_exemplo.coef_telhado.efi_90)}. No pórtico, a 90° e c_pi = −0,3, o pilar de "
        f"barlavento recebe {_pt(_caso_90.carga('pilar_esquerdo').carga_kN_m)} kN/m (pressão) e "
        f"a água de barlavento {_pt(_caso_90.carga('agua_esquerda').carga_kN_m)} kN/m (sucção).",
    )
    with st.container(border=True):
        st.subheader("Como interpretar")
        st.markdown(
            """
            - **q (pressão dinâmica):** 0,613·V_k² em kN/m²; multiplicada pelo coeficiente da zona
              e pela área, dá a força. Cada direção tem a sua classe e, portanto, a sua q.
            - **C_e e Δp:** C_e é o coeficiente de forma externo de cada zona (Tabelas 6 a 8);
              Δp = q·(f_v·C_e − c_pi) é a pressão líquida. **Positiva empurra para dentro**
              (parede de barlavento); **negativa puxa para fora** (sucção no telhado e nas
              paredes laterais).
            - **c_pe médio:** vale só nas faixas de altas sucções (arestas e cantos), para telhas,
              terças, travessas e fixações — nunca para a estrutura principal.
            - **Dois casos de c_pi:** a norma manda considerar o mais nocivo; −0,3 costuma governar
              a parede de barlavento e 0 (ou +0,2) o levantamento do telhado.
            - **Arrasto e soma das zonas:** são duas leituras da força horizontal (o gráfico da
              Figura 4/5 e as tabelas de C_e); não são iguais. Use o **maior** na estabilidade
              global.
            - **C_a lido do gráfico:** a norma só dá o gráfico; o programa o digitalizou, com
              incerteza de ±0,03. Fora dele (h/ℓ₁ < 0,5) vale o contorno e há aviso.
            - **Pórtico:** cargas **características**; o vento entra nas combinações com γ_q = 1,4 e
              ψ₀ = 0,6 (NBR 8800). A 0° as zonas mudam ao longo do comprimento: use a faixa onde
              está o pórtico, contada da empena de barlavento.
            - **Verificações em ALERTA:** a/b > 4, h/b > 6, inclinação fora das tabelas, balanço do
              beiral acima de 0,1·b, T₁ > 1 s (efeito dinâmico) ou h/b ≥ 6 (vórtices) — o resultado
              pede estudo específico ou conferência.
            """
        )
    st.warning(
        "O programa cobre edificações retangulares de arestas vivas com cobertura plana, de uma ou "
        "de duas águas. Telhados múltiplos, de calha central, curvos, coberturas isoladas, muros, "
        "reticulados, torres, cilindros, pontes e os efeitos dinâmicos têm outras regras na "
        "NBR 6123 e não estão aqui. Confira V₀ no mapa de isopletas.",
        icon=":material/warning:",
    )
    link_modulo("app_pages/vento_nbr6123.py", "Abrir Vento nas estruturas")


elif modulo == "Flambagem de colunas":
    st.header("Flambagem de colunas")
    st.markdown(
        "Use para uma **peça esbelta sob compressão** (coluna, escora, montante "
        "comprimido, coluna que recebe uma mão-francesa) — a tensão σ = F/A "
        "sozinha não avisa quando a peça vai flambar antes de escoar. Uma única "
        "rodada verifica a **barra inteira**: os dois eixos, todos os modos de "
        "flambagem, a flambagem local, a flexão em x e em y e a interação "
        "**N + M_x + M_y numa equação só**, pela **NBR 8800:2008**, pelo **Projeto "
        "NBR 8800:2024** ou pelo **AISC 360-16**, mais o critério da Anglo."
    )
    mostrar_tabela_campos(
        [
            [
                "Norma",
                "NBR 8800:2008 (fator Q), Projeto NBR 8800:2024 (área efetiva A_ef) ou AISC 360-16 (A_ef e φ = 0,90). “Comparar normas” mostra as três lado a lado",
                "Contrato ou critério do projeto",
            ],
            [
                "Seção",
                "Perfil de catálogo, barra, tubo, I ou U por dimensões, só A e r, ou seção genérica (propriedades e paredes)",
                "Desenho ou catálogo do perfil",
            ],
            [
                "L, L_x, L_y",
                "Comprimento total da coluna e os comprimentos destravados de cada eixo (desligue “Mesmo comprimento destravado” quando o travamento difere por plano), em mm",
                "Desenho ou montagem; travamentos laterais",
            ],
            [
                "Condição de apoio, K_x, K_y, K_z, L_z",
                "K da Tabela E.1 de cada plano — teórico ou recomendado para projeto — ou K informado; K_z e L_z só se a torção tem travamento próprio",
                "Croqui de fixação nas extremidades",
            ],
            [
                "E, G, f_y",
                "Módulos de elasticidade e de cisalhamento, em MPa (aço: 200 000 e 77 000), e a resistência ao escoamento",
                "NBR 8800 4.5.2.9; certificado do material",
            ],
            [
                "N_g, N_q ou N_Sd",
                "Cargas características permanente e variável (majoradas por γ_g e γ_q da Tabela 1) ou N_Sd já de cálculo, em kN",
                "Casos de carga / Assistente de cargas",
            ],
            [
                "M_x,Sd, M_y,Sd, e_x, e_y",
                "Momentos de cálculo de 1ª ordem (kN·m) e/ou excentricidades da força (mm), um para cada eixo",
                "Análise da estrutura; detalhe da ligação",
            ],
            [
                "Diagrama de momentos (C_m)",
                "Não informado (C_m = 1,0, conservador), momentos nas pontas (M₁/M₂) ou força transversal entre os apoios",
                "Diagrama de momentos da barra",
            ],
            [
                "L_b e C_b",
                "Comprimento destravado da mesa comprimida e fator de modificação da FLT (informado ou pelo diagrama de quatro pontos)",
                "Travamentos da mesa comprimida",
            ],
            [
                "M_Rd informado",
                "Momento resistente calculado fora do programa, quando a seção não tem rotina (tubo não compacto, T, genérica)",
                "Catálogo do fabricante ou cálculo próprio",
            ],
            [
                "Mão-francesa: F, θ, a, vínculo, eixo",
                "Força na barra inclinada (kN), ângulo com a coluna (45° usual), altura do nó medida da base, vínculo da coluna e o eixo que ela flete — o programa decompõe em H e V e soma o momento",
                "Reação da viga/console que a mão-francesa apoia",
            ],
            [
                "Paredes e confirmação",
                "Só na seção genérica: tipo, grupo, b, t e quantidade das paredes (flambagem local) e a confirmação de que a seção é compacta e a torção não governa",
                "Tabela 4 da norma; cálculo próprio",
            ],
        ]
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Escolha a **norma** e o aço (f_y). Na dúvida, comece pela NBR 8800:2008.
        2. Descreva a **seção**. Perfil de catálogo é o caminho mais seguro: as
           propriedades vêm da tabela. “Área e raio de giração” e “Seção genérica”
           deixam o resultado em **ALERTA** até as paredes serem informadas ou a
           seção ser confirmada como compacta.
        3. Informe o **comprimento total** e, se o travamento difere por plano,
           desligue “Mesmo comprimento destravado” e informe L_x e L_y. Escolha a
           condição de apoio de cada eixo — deixe o K recomendado ligado, salvo se a
           ligação for de fato ideal.
        4. Informe os **esforços de cálculo**: N_Sd (ou as cargas características),
           M_x,Sd e M_y,Sd, as excentricidades e, para o efeito B₁, a forma do
           diagrama de momentos de cada eixo.
        5. Com **mão-francesa**, ligue o bloco 5: F, θ, a, o vínculo e o eixo geram
           o momento sozinhos (M = H·a no engaste, H·a·(L−a)/L na biapoiada) e ele
           é somado ao do eixo que ela flete.
        6. Leia o **Resumo** (status, aproveitamento máximo, N_c,Rd, N_e, χ, Q ou
           A_ef/A_g, B₁ e interação) e a **tabela de verificações**: cada linha tem
           solicitante, resistente, aproveitamento, status, fórmula e item da norma.
        7. Use **Comparar normas**, baixe o CSV e **registre** no projeto — o
           memorial leva a tabela inteira.
        """
    )
    mostrar_exemplo(
        [
            ["Norma", "NBR 8800:2008"],
            ["Seção", "Barra circular maciça, d = 50 mm"],
            ["L / apoio", "2000 mm / Biapoiada (pino-pino), K = 1,0 nos dois eixos"],
            ["E / f_y", "200000 MPa / 250 MPa"],
            ["N_g / N_q", "30 kN (γ_g = 1,40) / 20 kN (γ_q = 1,50) → N_Sd = 72 kN"],
        ],
        "Resultado esperado: λ = 160 (dentro do limite 200 da Anglo, item 8.3); "
        "N_e = 151,4 kN; λ_0 = 1,80 > 1,5, portanto χ = 0,877/λ_0² = 0,270; Q = 1,0 "
        "(seção maciça); N_c,Rd = 120,71 kN — aproveitamento de 60 % para "
        "N_Sd = 72 kN. Repare que a norma dá 80 % da carga de Euler mesmo na "
        "coluna longa: é o efeito das imperfeições e tensões residuais.",
    )
    mostrar_exemplo(
        [
            ["Norma / aço", "AISC 360-16; f_y = 46 ksi (317 MPa); E = 29 000 ksi (199 948 MPa)"],
            ["Seção", "Genérica, HSS8×8×1/2: A = 13,5 in² (8 710 mm²); r = 3,04 in (77,2 mm)"],
            [
                "Propriedades",
                "I_x = I_y = A·r²; sem torção; confirmar “compacta e torção não governa”",
            ],
            ["Parede", "AA, grupo 1: b = 14,2·t = 167,7 mm, t = 0,465 in (11,81 mm), quantidade 4"],
            ["L / apoio", "24 ft (7 315 mm); K = 1,0"],
        ],
        "Resultado esperado: N_c,Rd = 1 361 kN (φP_n = 306 kips do AISC Design Guide 29); "
        "A_ef/A_g = 1,0, porque b/t = 14,2 fica abaixo de 1,40·√(E/F_y).",
    )
    with st.container(border=True):
        st.subheader("Como interpretar")
        st.markdown(
            """
            - **Status geral:** OK quando nada reprova; NÃO OK quando alguma
              verificação reprova **ou foi bloqueada**; ALERTA quando nada reprova
              mas ficou algo que o programa não consegue conferir.
            - **Linhas NÃO OK de bloqueio:** tubo circular com D/t > 0,45·E/f_y,
              alma esbelta ou tubo não compacto na flexão, N_Sd ≥ N_e no B₁ e seção
              sem Z não são estimados — o programa mostra o motivo em vez de
              corrigir a entrada em silêncio.
            - **N_e (Anexo E):** a menor força de flambagem elástica entre flexão
              em x, flexão em y, torção (N_ez) e o modo acoplado das seções
              monossimétricas (U, T). Perfis abertos podem torcer antes de fletir.
            - **Q (NBR 2008) e A_ef (Projeto 2024 e AISC):** a flambagem local
              reduz a área que trabalha quando alguma parede (mesa, alma, tubo) é
              esbelta. A tabela “Paredes da seção” mostra b/t e o limite de cada uma.
            - **λ_0 e χ:** χ = 0,658^(λ_0²) até λ_0 = 1,5 e 0,877/λ_0² acima — já
              inclui imperfeições e tensões residuais.
            - **B₁ e C_m (Anexo D):** B₁ = C_m/(1 − N_Sd/N_e) amplifica o momento de
              1ª ordem; N_e usa o **comprimento real** da barra no plano de flexão
              (K = 1). Sem M₁/M₂ informado, C_m = 1,0 (conservador).
            - **Interação (5.5.1.2):** N/N_Rd + 8/9·(M_x/M_x,Rd + M_y/M_y,Rd) ≤ 1,0
              (ou N/(2N_Rd) + … quando N/N_Rd < 0,2), com os **dois momentos na
              mesma equação**. Verificar cada eixo separado aprova colunas que a
              norma reprova.
            - **Critério Anglo:** λ ≤ 200 na compressão (8.3) e espessura mínima das
              partes (8.8). A espessura do I ou U da coluna é conferida sozinha.
            - **Mão-francesa:** H = F·sen θ flete a coluna com braço a; V = F·cos θ
              comprime (marque “Somar V a N_Sd” só se a reação ainda não estiver em
              N_Sd). O cisalhamento (5.4.3) não é verificado aqui: o programa avisa.
            - **Norma 2008 “CONFERIR”:** Q_s e Q_a, a Tabela E.1 de K, o λ_p dos
              tubos na flexão e a forma da FLT foram trazidos de memória; confirme
              na norma antes de emitir.
            """
        )
    st.warning(
        "Verificação de barra isolada: os efeitos globais de 2ª ordem (B_2, "
        "deslocabilidade), as cargas nocionais e as ligações pertencem à análise "
        "da estrutura — módulo Estruturas de aço (pórtico 2D, placa de base). "
        "Cantoneira simples, barras compostas, perfis formados a frio, fadiga e "
        "cisalhamento também ficam de fora.",
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
            [
                "σx, σy e τxy",
                "Componentes do estado plano, em MPa",
                "Assistente, fórmula ou simulação",
            ],
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
        "A página tem **dois modos**, escolhidos no topo. **Junta mecânica (NASA/ISO)** é um "
        "pré-dimensionamento de junta pré-carregada (círculo, grade retangular ou coordenadas "
        "livres) e **não substitui a norma estrutural**. **Ligação estrutural de aço** verifica "
        "a ligação pela NBR 8800, AISC 360, RCSC ou critério Anglo (veja a seção ao final)."
    )
    mostrar_tabela_campos(
        [
            ["Rosca e classe", "Designação e classe do parafuso", "Desenho e certificado"],
            [
                "Padrão",
                "Círculo (n e diâmetro), grade (n_lin, n_col, s, g) ou coordenadas",
                "Desenho da junta",
            ],
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
    st.divider()
    st.subheader("Modo “Ligação estrutural de aço”")
    st.markdown(
        "Verifica corte, contato e rasgamento, deslizamento, peça tracionada, disposições "
        "construtivas e o critério Anglo AA-BR-DPST-DR-0001 (item 9.1). Von Mises e torque "
        "**não** são critérios de aprovação aqui; o torque é só referência de instalação."
    )
    mostrar_tabela_campos(
        [
            [
                "Norma",
                "NBR 8800:2008, Projeto 2024, AISC 360 LRFD ou RCSC 2004",
                "Contrato / cliente",
            ],
            ["Parafuso e grau", "Designação (M16, M22, 7/8″…), A325, A490 ou A307", "Projeto"],
            [
                "t da parte mais fina",
                "Espessura da chapa mais fina — nunca a soma",
                "Detalhe das partes ligadas",
            ],
            ["Geometria", "n_lin, n_col, s, g, e (e e_v, se houver borda vertical)", "Desenho"],
            [
                "N, V e M (ou a)",
                "Esforços característicos no centro do grupo; M = V·a numa emenda",
                "Análise estrutural",
            ],
            [
                "γ_f",
                "Fator que majora os característicos para o ELU (ou valores já de cálculo)",
                "NBR 8681",
            ],
            [
                "Superfície e atrito",
                "Define μ; ligação por atrito é obrigatória na Anglo com inversão",
                "Critério",
            ],
            [
                "A_g e e_c da peça",
                "Opcional: tração da peça com C_t e regra dos 75%",
                "Catálogo do perfil",
            ],
        ]
    )
    st.markdown(
        """
        **Passo a passo:** (1) escolha a norma e o parafuso; (2) informe t, o aço e a geometria;
        (3) informe os esforços **característicos** — o ELU usa γ_f·F_k e o deslizamento usa F_k;
        (4) confira superfície, atrito e condições fora do escopo; (5) leia a tabela
        *Verificação · Solicitante · Resistente · Unidade · Aproveitamento · Status · Fórmula ·
        Referência*; (6) use **Comparar normas** e **Testar todos os parafusos** para decidir; (7)
        registre o resultado — a tabela inteira vai para o memorial em Word e PDF.
        """
    )
    mostrar_exemplo(
        [
            ["Norma / aço", "NBR 8800:2008 / ASTM A36"],
            ["Parafuso", "M22, A325, rosca no plano, 1 plano de corte"],
            ["Partes ligadas", "t = 5,08 mm (alma do U); pega opcional"],
            ["Geometria", "Grade 2 × 2, e = s = g = 70 mm"],
            ["Esforços", "V_k = 32 kN, N = 0, emenda por sobreposição (a = 105 mm), γ_f = 1,4"],
            ["Superfície", "Galvanizada a fogo sem tratamento (μ = 0,20), ligação por atrito"],
        ],
        "Resultados: J = 9.800 mm²; parafuso crítico = 32,65 kN (ELU) e 23,32 kN (serviço); "
        "resistência por parafuso = min(92,9; 79,5) = 79,5 kN → 41%; deslizamento = "
        "0,80·0,20·176 = 28,16 kN → 83%; borda de 70 mm NÃO OK (12t = 60,96 mm). Com M16 o "
        "deslizamento passa a 160% (NÃO OK).",
    )
    with st.container(border=True):
        st.subheader("Como interpretar")
        st.markdown(
            """
            - **Status:** OK, NÃO OK, ALERTA (atende com ressalva ou não pôde ser calculado),
              INFO (informação) e N/A (não se aplica).
            - **Aproveitamento:** solicitante ÷ resistente. Acima de 100% é NÃO OK.
            - **Distâncias e espaçamentos:** “solicitante” é o valor exigido e “resistente” o adotado.
            - **ℓ_f ≤ 0, C_t indefinido (n_col = 1), A307 por atrito e superfície sem μ:**
              aparecem como linhas da tabela — o programa não corrige a entrada em silêncio.
            - **Fora do escopo:** tração com alavanca, furos alargados/alongados, fadiga e perfis
              formados a frio. Marque o que se aplica e a tabela ganha um ALERTA.
            """
        )
    st.warning(
        "Alguns valores da NBR 8800:2008 "
        "(μ = 0,35 nas classes A e C, f_ub do A325 e C_t ≤ 0,90) estão marcados “CONFERIR” até "
        "serem confirmados na norma. O grupo excêntrico usa o método elástico (conservador).",
        icon=":material/warning:",
    )
    link_modulo("app_pages/projeto_parafusos.py", "Abrir o projeto de parafusos")


elif modulo == "Degrau de escada em grade":
    from core import degrau_escada as _de

    st.header("Degrau de escada em grade")
    st.markdown(
        "Use para o **degrau de uma escada industrial em grade de piso eletrofundida** do "
        "catálogo Selmec “Degraus” (DS): o programa define o espelho, o piso e a profundidade, "
        "divide a escada em lances, avalia os **64 modelos** e adota o mais leve que atende; "
        "dimensiona o degrau (flexão com flambagem lateral, cisalhamento, flechas, reações e "
        "parafusos A307) e fecha em **38 verificações** com o item da norma em cada uma — "
        "NR-12 (Anexo III), NR-22, Critério Anglo, NBR 8800, NBR 6120 e ISO 14122-3. Não "
        "dimensiona a longarina, o patamar nem o guarda-corpo (só confere as medidas dele)."
    )
    mostrar_tabela_campos(
        [
            [
                "Enquadramento e espelho fechado",
                "NR-12 (acesso a máquina) ou NR-22 (demais acessos da mineração); grade vazada é "
                "escada sem espelho, e com espelho fechado vale o item 12 da NR-12",
                "Quem manda no acesso: contrato, projeto da planta, NR aplicável",
            ],
            [
                "Desnível H e espelho alvo",
                "Altura de piso a piso em mm e o espelho que você gostaria (o programa respeita a "
                "faixa da norma e o número inteiro de espelhos)",
                "Levantamento ou projeto de arquitetura/processo",
            ],
            [
                "Impor n, b ou C",
                "Fixa o número de espelhos, o piso ou a profundidade no lugar do automático; "
                "vazio = automático",
                "Só quando o desenho ou o cliente já definiu; as verificações acusam o efeito",
            ],
            [
                "Comprimento L e redução da largura útil",
                "Vão entre chapas laterais (500 a 1.500 mm) e quanto o corrimão tira da passagem",
                "Desenho da escada e do guarda-corpo",
            ],
            [
                "Uso (Anglo 10.2)",
                "Geral, permanência constante (rota de emergência) ou cabine; define a largura "
                "mínima",
                "Critério Anglo",
            ],
            [
                "Malha, barras de ligação e modelo",
                "Preferência de família (A, B, C, F) e de barra de ligação (100 ou 50 mm), ou o "
                "modelo escolhido à mão",
                "Catálogo Selmec; o Anglo cita a grade GS-A4",
            ],
            [
                "Material, acabamento e parafuso",
                'ASTM A36 galvanizado (padrão) ou inox passivado; parafuso A307 de 5/8" (padrão) '
                'ou 1/2"',
                "Critério Anglo 4.5 e 8.8",
            ],
            [
                "Cargas e coeficientes",
                "q = 3,00 kN/m², P = 2,50 kN, P_ISO = 1,50 kN, γ e limites de flecha",
                "Anglo Tab. 2 e 3, NBR 6120, ISO 14122-3, NBR 8800",
            ],
        ]
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Escolha o **enquadramento** e diga se o degrau tem espelho fechado.
        2. Informe o **desnível H** e o comprimento **L**; deixe n, b e C em automático.
        3. Leia o **Quadro-resumo**: modelo adotado, espelho × piso (com 2h + b e α), C × L (com
           F e r), lances e degraus, aproveitamento máximo, peso e o **nível** em que a altura
           do espelho foi resolvida.
        4. Na aba **Verificações** veja as 38 linhas; ligue “só o que merece atenção” para ver
           apenas NÃO OK, ALERTA e N/A.
        5. A aba **Os 64 modelos** mostra por que o adotado foi escolhido e os outros não.
        6. Copie o **texto da requisição** e baixe o CSV ou o PDF; **registre** no projeto para
           o memorial levar as 38 verificações e as tabelas.
        """
    )
    _exemplo = _de.calcular_escada(_de.EntradaDegrau())

    def _pt(valor: float, casas: int = 2) -> str:
        return _de.numero_pt(valor, casas)

    mostrar_exemplo(
        [
            ["Enquadramento", "NR-12, degrau sem espelho, uso geral"],
            ["Escada", "H = 3.600 mm; espelho alvo 175 mm; L = 800 mm; patamar de 900 mm"],
            [
                "Degrau",
                'Malha A, barras de ligação a cada 100 mm, ASTM A36 galvanizado, parafuso 5/8"',
            ],
        ],
        f"Resultado esperado: {_exemplo.geometria.n} espelhos de "
        f"{_pt(_exemplo.geometria.h_mm, 0)} mm e piso de {_pt(_exemplo.geometria.b_mm, 0)} mm "
        f"(2h + b = {_pt(_exemplo.geometria.blondel_mm, 0)} mm; α = "
        f"{_pt(_exemplo.geometria.alfa_graus, 1)}°), C = {_pt(_exemplo.geometria.C_mm, 0)} mm e F = "
        f"{_exemplo.geometria.F_mm} mm, em {_exemplo.lances.texto} e "
        f"{_exemplo.lances.n_degraus_grade} degraus. Modelo adotado: "
        f"{_exemplo.adotado.modelo.nome}, com M_Rd = {_pt(_exemplo.adotado.MRd_kNm, 3)} kN·m por "
        f"barra; a carga concentrada de 2,5 kN governa, com "
        f"{_pt(100 * _exemplo.adotado.u_flex_c, 0)} % de aproveitamento. "
        f"Verificações: {_de.texto_da_contagem(_exemplo.contagem)} — os dois ALERTAS são o furo "
        'do catálogo (para parafuso de 5/8" é preciso furo oblongo especial) e o guarda-corpo '
        "de 1.200 mm contra os 1.300 mm do Anglo.",
    )
    with st.container(border=True):
        st.subheader("Como interpretar")
        st.markdown(
            """
            - **Nível 1 a 4:** em que faixa de espelho a escada coube — 1 atende norma, Anglo e
              catálogo; 2 atende norma e Anglo, mas o degrau passa de 300 mm; 3 só a norma (o
              Anglo manda prevalecer a lei, item 3.1); 4 nenhuma.
            - **ALERTA:** atende com ressalva ou há conflito entre normas (aparecem sempre no
              bloco “Conflitos entre normas”). **NÃO OK** reprova. Linhas informativas (INFO) não
              entram na contagem.
            - **Atende (tabela dos 64):** aproveitamento ≤ 1 **e** L dentro da largura
              recomendada do catálogo. O catálogo não diz com que carga as larguras foram
              definidas, por isso o programa exige as duas coisas.
            - **Carga concentrada:** é ela que costuma governar a flexão (P = 2,5 kN junto ao
              bocel, sobre poucas barras); não se soma à distribuída.
            - **Peso:** é estimativa (a barra de ligação tem lado adotado).
            """
        )
    st.warning(
        "Fora do escopo: longarina, patamar e ligações da longarina; guarda-corpo (só as "
        "dimensões são conferidas); pressão de contato do parafuso na chapa lateral (o catálogo "
        "não informa a espessura). O item da NBR 6120 da carga de 2,5 kN deve ser conferido na "
        "edição 2019, e o inox está fora do escopo da NBR 8800.",
        icon=":material/warning:",
    )
    link_modulo("app_pages/degrau_escada.py", "Abrir Degrau de escada em grade")


elif modulo == "Base técnica do projeto":
    from core import base_tecnica as _bt
    from core import criterio_anglo as _ca

    st.header("Base técnica do projeto")
    st.markdown(
        "O que se preenche **uma vez por projeto** e as demais páginas leem: o **critério do "
        "cliente** (somente as normas, ou o critério da Anglo American "
        f"{_ca.CODIGO} Rev. {_ca.REVISAO}), o **vento do local** (V₀, S₁, categoria do terreno e "
        "S₃), o **tipo de estrutura** que define o limite do deslocamento horizontal, a "
        "**sobrecarga** de referência, a classe de agressividade e a vida útil. As páginas de vento, "
        "contraventamento, ligação e estruturas de aço começam com esses valores e mostram de onde "
        "vieram; um botão volta aos valores da base quando algo foi digitado."
    )
    mostrar_tabela_campos(
        [
            ["Critério do cliente", "Nenhum ou Anglo American", "Contrato e critérios de projeto"],
            [
                "V₀",
                "Velocidade básica do mapa de isopletas",
                "NBR 6123:2023, Figura 1, ou o cliente",
            ],
            ["S₁ e terreno", "Relevo e categoria de rugosidade", "Visita, imagens de satélite"],
            [
                "S₃",
                "Grupo da Tabela 4 ou o valor do cliente",
                "NBR 6123:2023 ou critério do cliente",
            ],
            ["Tipo de estrutura", "Plataforma, pipe rack, cobertura ou edificação NBR", "Arranjo"],
            [
                "Sobrecarga",
                "Local da Tabela 2 do critério Anglo ou valor informado",
                "Cliente, NBR 6120",
            ],
        ]
    )
    _base = _bt.base_do_cliente(_bt.CLIENTE_ANGLO)
    _limite = _bt.limite_do_topo(_base, 1)
    mostrar_exemplo(
        [
            ["Critério", "Anglo American"],
            ["Vento", _bt.texto_do_vento(_base)],
            ["Tipo de estrutura", _base.tipo_de_estrutura],
            [
                "Sobrecarga",
                f"{_base.sobrecarga_local}: {_bt.numero(_base.sobrecarga_kN_m2, 1)} kN/m²",
            ],
        ],
        f"Resultado esperado: limite do topo H/{_limite.divisor:.0f} ({_limite.referencia}) — "
        f"{_bt.numero(_limite.limite_mm(6000.0), 1)} mm numa estrutura de 6 m; e o aviso de "
        "conflito do S₃.",
    )
    with st.container(border=True):
        st.subheader("Como interpretar")
        st.markdown(
            """
            - **Conflitos:** o critério Anglo fixa S₃ = 0,95, que na NBR 6123:2023 é o grupo 4
              (sem ocupação humana); indústrias ficam no grupo 3 (S₃ = 1,00). O programa usa o valor
              do cliente e mostra o aviso — confirme com o cliente qual vale.
            - **Consulta do critério:** a página traz as tabelas do critério Anglo (sobrecargas,
              deslocamentos, mínimos, chumbadores, ligações, combinações, vibração, escadas e
              materiais) com o número do item.
            - **Sem projeto ativo** nada é gravado: abra ou crie um em Projetos permanentes.
            """
        )
    link_modulo("app_pages/base_tecnica.py", "Abrir Base técnica do projeto")


elif modulo == "Plano de cargas":
    from core import load_combinations as _comb
    from core import plano_de_cargas as _pc
    from core.memorial_verificacoes import decimal_ptbr as _decimal

    st.header("Plano de cargas")
    st.markdown(
        "Reúne as **ações do projeto com código padrão** (PP, PE, EQ, EO, SC, W0, W90, W180, W270, "
        "T+, T−, PRV, HT, HL, MO, IM, EX), de onde cada uma veio, as **cargas para lançar no "
        "modelo** (SolidWorks, Robot) e as **combinações** ELU e ELS numeradas pelas Tabelas 1 e 2 "
        "da NBR 8800. O vento nas quatro direções forma um grupo exclusivo (nunca atuam juntas). "
        "O modelo recebe os valores **característicos**; as combinações saem daqui."
    )
    mostrar_tabela_campos(
        [
            ["Vento", "Botão “Enviar ao plano de cargas” nas páginas de vento", "Gerado"],
            ["Sobrecarga", "Botão “Incluir a sobrecarga da base técnica”", "Base técnica"],
            ["Temperatura", "Botão “Incluir temperatura ±10 °C”", "Critério Anglo 5.8"],
            [
                "Pesos e demais",
                "Formulário “Adicionar ou editar uma ação”",
                "Modelo, folhas de dados",
            ],
            [
                "Programa de destino",
                "Unidades (N e mm, N e m, kN e m) e eixo vertical (Y no SolidWorks, Z no Robot)",
                "O modelo",
            ],
        ]
    )
    from components.figuras_estrutura import svg_convencao_de_eixos as _figura_eixos
    from core import exportacao_cargas as _ex

    st.subheader("Convenção de eixos e sinais")
    st.image(_figura_eixos(_ex.EIXO_Y_PARA_CIMA), width="stretch")
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Leia a **Conferência do plano** no topo: ela diz o que falta (peso próprio,
           sobrecarga, vento nas quatro direções, temperatura nos dois sentidos) e o que não
           fecha (unidade trocada, carga sem direção).
        2. Inclua ou **edite** as ações: escolha o código (os que já estão no plano vêm marcados)
           e os campos trazem o que está gravado.
        3. Confira as **combinações** na matriz de fatores (laranja = majorada; azul = até 1).
        4. Em **Exportar para o modelo**, escolha as unidades e o eixo vertical do programa e
           baixe a **planilha Excel**: abas Leia-me, Ações, Cargas, Combinações e lista.
        5. No SolidWorks, crie um caso primário por código (o PP é a gravidade), aplique as
           cargas da aba Cargas e monte as combinações da aba Combinações.
        """
    )
    _plano = _pc.PlanoDeCargas((), "")
    for _codigo in ("PP", "PE", "SC", "W0", "W90", "W180", "W270"):
        _plano = _pc.com_acao(_plano, _pc.nova_acao(_codigo))
    _lista = _pc.combinacoes(_plano, _comb.ESTADOS_PADRAO)
    _elu = [c for c in _lista if c.estado_limite == _comb.ELU_NORMAL]
    mostrar_exemplo(
        [
            ["Ações", "PP, PE, SC e o vento W0, W90, W180 e W270"],
            ["Estados-limite", ", ".join(_comb.ESTADOS_PADRAO)],
        ],
        f"Resultado esperado: {len(_lista)} combinações, {len(_elu)} delas ELU normais — por "
        f"exemplo, nº {_elu[0].numero}: {_decimal(_elu[0].expressao)}.",
    )
    with st.container(border=True):
        st.subheader("Como interpretar")
        st.markdown(
            """
            - **Um código por ação:** enviar o vento de novo substitui W0 a W270 — o plano não
              acumula cópias.
            - **Combinações numeradas:** C01-ELU, C02-ELU… servem de nome do caso combinado no
              modelo; ELSR, ELSF e ELSQ são as de serviço rara, frequente e quase permanente.
            - **Componentes com sinal:** F_x, F_y e F_z já saem nos eixos do programa escolhido;
              Z (vertical) com valor positivo é para baixo, e no SolidWorks (Y para cima) o Y da
              planta vira −Z.
            - **Critério Anglo (5.9):** com a base técnica da Anglo, a página mostra quais das
              combinações mínimas do cliente já podem ser formadas e quais ações faltam.
            - O plano **não entra no memorial** (o memorial é o molde dos cálculos): use os CSV
              como anexo ou para o modelo.
            """
        )
    link_modulo("app_pages/plano_cargas.py", "Abrir Plano de cargas")


elif modulo == "Esforços do modelo":
    st.header("Esforços do modelo")
    st.markdown(
        "Em vez de digitar N, V e M barra por barra, importe os resultados do **SolidWorks "
        "Simulation**. O programa lê as forças de todas as vigas, **confere se o modelo recebeu as "
        "cargas do plano** e combina os casos com os fatores do Plano de cargas, **ponto a ponto** "
        "ao longo de cada barra, para achar o pior de cada uma."
    )
    mostrar_tabela_campos(
        [
            [
                "Forças da viga",
                "Resultados › botão direito › Listar forças da viga (todas as vigas) › Salvar CSV",
                "Um estudo por caso",
            ],
            [
                "Reações",
                "Resultados › Listar forças resultantes › Força de reação, modelo inteiro › CSV",
                "O mesmo estudo",
            ],
            [
                "Caso de carga",
                "Nome do estudo = código do plano (PP, SC, W0…): o programa lê do arquivo",
                "Plano de cargas",
            ],
            [
                "Barras",
                "Perfil (vem do nome quando o SolidWorks diz qual é), tipo e eixo forte",
                "Lista de material",
            ],
        ]
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. No SolidWorks, rode **um estudo por caso de carga**, com o código no nome do estudo,
           aplicando as cargas da planilha do Plano de cargas **características, sem
           coeficiente** — nunca majore no SolidWorks: os coeficientes estão nas combinações do
           programa. O estudo PP leva **só a gravidade**. Duplique o estudo PP para os outros
           casos (excluindo a gravidade) para manter a **mesma malha** em todos (os esforços são
           combinados elemento a elemento).
        2. Em cada estudo, salve **Listar forças da viga** e **Listar forças resultantes**.
        3. Envie os arquivos de uma vez, confira o caso de cada um e grave.
        4. Leia a **conferência das reações**: num caso só vertical, a reação horizontal precisa
           dar quase zero; as forças concentradas do plano precisam bater com as reações; o PP
           precisa dar o peso da estrutura (com a **Lista de material** montada). Reações γ vezes
           a carga (1,25; 1,4; 1,5…) denunciam estudo majorado: refaça com as cargas
           características.
        5. Preencha a **tabela das barras** (perfil, tipo, eixo forte) e veja o **pior caso de cada
           barra**.
        6. Em **Parâmetros da verificação**, informe por tipo de barra o aço, os comprimentos de
           flambagem Lx e Ly, o Lb, o Cb e o B₂ (da página Contraventamento).
        7. Leia a **Verificação das barras** (atendem, não atendem, sem dados), abra o cálculo
           completo de qualquer barra e **registre** no projeto: o memorial ganha o capítulo.
        8. Marque os **pilares** (tipo Pilar) e veja o **quadro de cargas para as fundações**:
           a base de cada pilar, caso a caso, sem combinar nem majorar (critério Anglo 5.9), com
           Excel, CSV e registro.
        9. Em **Placas de base dos pilares**, informe a placa padrão (N, B, espessura, f_ck e os
           chumbadores) e grave: o programa combina os esforços da base de cada pilar e verifica
           a placa e os chumbadores pelo Design Guide 1 do AISC, com as exigências da Anglo
           (placa ≥ 16 mm, chumbador ≥ 5/8" e o furo, a arruela e o graute do item 8.7).
        """
    )
    mostrar_exemplo(
        [
            ["Estrutura", "2 pilares W 200 × 35,9 de 4 m e viga W 310 × 32,7 de 6 m"],
            ["Casos", "PP 1,5 kN/m, SC 10 kN/m na viga, W0 e W180 com 8 kN no topo"],
        ],
        "Resultado esperado: pilar com −52,6 kN e 36,8 kN·m no topo (C03, vento para −X); "
        "viga com 45,1 kN·m no meio do vão (C01). Reações: SC soma 60,0 kN na vertical e W0, "
        "8,0 kN na horizontal.",
    )
    with st.container(border=True):
        st.subheader("Como interpretar")
        st.markdown(
            """
            - **Sinal:** tração positiva. O SolidWorks dá as forças nas pontas de cada elemento,
              com sinais opostos; o programa as converte em esforço interno.
            - **Ponto a ponto:** a mesma combinação é somada no mesmo ponto em todos os casos.
              Com malhas diferentes, o programa combina pela ordem ou pela soma dos máximos (a
              favor da segurança) e avisa.
            - **N junto:** o esforço normal na combinação e no ponto do maior momento forte,
              para a interação N + M.
            - **Segunda ordem:** o estudo estático é de primeira ordem; a verificação multiplica
              os esforços pelo B₂ do tipo de barra (a favor da segurança).
            - **Verificação:** o mesmo motor da página Flambagem de colunas, nos pontos mais
              críticos de cada barra; barras sem perfil ou sem comprimentos ficam "sem dados".
            - **Placa de base:** com momento grande (excentricidade além do limite do Design
              Guide 1), o concreto trabalha na pressão máxima num trecho Y e os chumbadores do
              outro lado seguram o resto — por isso o contato aparece como informação, e quem
              governa costuma ser a espessura da placa ou a tração nos chumbadores. A ancoragem
              no concreto (cone, comprimento) e o bloco ficam para o projeto da fundação.
            """
        )
    link_modulo("app_pages/esforcos_modelo.py", "Abrir Esforços do modelo")


elif modulo == "Lista de material":
    from core import lista_de_material as _lm

    st.header("Lista de material")
    st.markdown(
        "A lista dos perfis, chapas e demais itens da estrutura, com a **massa**, o **peso**, a "
        "**área de pintura** e as **barras comerciais** de cada perfil — para o orçamento — e a "
        "**conferência do peso próprio do modelo**: o peso da lista contra a reação vertical do "
        "caso PP importado do SolidWorks."
    )
    mostrar_tabela_campos(
        [
            [
                "Lista de corte",
                "CSV gerado pela macro da página (direto da peça) ou salvo da tabela de "
                "lista de corte de um desenho",
                "SolidWorks",
            ],
            [
                "Perfil",
                "Nome do catálogo (W 200 x 35,9 (H)), do SolidWorks (W8X31, C8X13.75, L2X2X1/4) "
                "ou as medidas (TUBO QUADRADO 50 X 50 X 3)",
                "Lista de corte / desenho",
            ],
            [
                "Chapa",
                "Comprimento, largura e espessura de cada peça",
                "Desenho de detalhe",
            ],
            [
                "Grade, outros",
                "Grade: área e kg/m² do fabricante; outros: kg por unidade",
                "Catálogo do fornecedor",
            ],
            [
                "Acréscimo",
                "Ligações, parafusos e soldas que a lista não traz (5 a 10 %)",
                "Prática da empresa",
            ],
        ]
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Baixe na página a **Macro do SolidWorks** e, com a peça aberta, use Ferramentas ›
           Macro › **Nova** (dê um nome e salve), apague o texto do editor, cole o da macro e
           tecle **F5**: ela lê a lista de corte direto da árvore da peça e salva o CSV na pasta
           da peça. Das próximas vezes, Ferramentas › Macro › **Executar**. (Também serve o CSV
           da tabela de lista de corte de um desenho; o Excel antigo, .xls, não é lido.)
        2. Envie o arquivo, confira as linhas lidas e use **Acrescentar** ou **Substituir**.
        3. Complete na tabela o que faltou (largura das chapas, kg/m de perfil fora do catálogo)
           e acrescente o que não está no modelo (grades, guarda-corpos, chumbadores).
        4. Use **Incluir as placas de base** para trazer a placa de cada pilar verificada em
           Esforços do modelo.
        5. Grave, confira o resumo e a **conferência com o peso próprio do modelo** e exporte o
           Excel para o orçamento.
        """
    )
    _lista = _lm.ListaDeMaterial(
        itens=(
            _lm.ItemDaLista("P1", _lm.TIPO_PERFIL, "W 200 x 35,9 (H)", 2, 4.0),
            _lm.ItemDaLista("V1", _lm.TIPO_PERFIL, "W 310 x 32,7", 1, 6.0),
            _lm.ItemDaLista("PB", _lm.TIPO_CHAPA, "Placa de base", 2, 0.35, 300.0, 19.0),
        )
    )
    _res = _lm.resumir(_lista)

    def _virgula(valor: float, casas: int = 1) -> str:
        return f"{valor:,.{casas}f}".replace(",", " ").replace(".", ",")

    mostrar_exemplo(
        [
            ["Pilares", "2 × W 200 × 35,9 com 4,0 m"],
            ["Viga", "1 × W 310 × 32,7 com 6,0 m"],
            ["Placas de base", "2 × 350 × 300 × 19 mm"],
            ["Acréscimo", "5 % de ligações, parafusos e soldas"],
        ],
        f"Resultado esperado: {_virgula(_res.massa_itens_kg)} kg de itens, "
        f"{_virgula(_res.massa_total_kg)} kg com o acréscimo ({_virgula(_res.peso_total_kN, 2)} "
        f"kN) e {_virgula(_res.area_pintura_m2)} m² de pintura; 1 barra de 12 m de cada perfil.",
    )
    with st.container(border=True):
        st.subheader("Como interpretar")
        st.markdown(
            """
            - **Massa:** perfil = kg/m do catálogo × comprimento; chapa = volume × 7 850 kg/m³.
            - **Pintura:** o contorno do perfil (faces de dentro e de fora das mesas e da alma)
              vezes o comprimento, mais as duas faces das chapas. Grades não entram.
            - **Barras comerciais:** o comprimento total dividido pela barra, arredondado para
              cima — sem otimização de corte nem perdas.
            - **Conferência:** o peso dos itens sem o acréscimo contra a reação vertical do caso
              PP; diferença acima de 5 % quer dizer barra faltando no modelo ou na lista, ou outras
              cargas no caso PP.
            - A lista é ferramenta de orçamento: não vai para o memorial.
            """
        )
    link_modulo("app_pages/lista_de_material.py", "Abrir Lista de material")


elif modulo == "Vigas de piso":
    from dataclasses import replace as _replace

    from core import viga_de_piso as _vp

    st.header("Vigas de piso")
    st.markdown(
        "A viga que apoia a grade (ou a chapa) da plataforma, **biapoiada**. A página monta as "
        "combinações da NBR 8800 com o peso próprio, o piso e a sobrecarga, verifica a **flexão** "
        "(com a flambagem lateral e local), o **cortante** e a **flecha**, dá a **reação** para "
        "dimensionar a ligação e procura o **perfil mais leve** da mesma família que atende."
    )
    mostrar_tabela_campos(
        [
            [
                "Perfil e aço",
                "W, U, I ou HP do catálogo; ASTM A572 Gr 50 é o usual",
                "Lista de material / desenho",
            ],
            [
                "Tipo",
                "Principal (recebe outras vigas ou apoia nos pilares) ou secundária (só a grade)",
                "Planta da plataforma",
            ],
            [
                "Vão e faixa",
                "Distância entre apoios e a largura de piso que a viga carrega",
                "Planta da plataforma",
            ],
            [
                "Travamento",
                "Se a grade trava a mesa comprimida, o espaçamento entre os pontos travados",
                "Detalhe de fixação da grade",
            ],
            [
                "Cargas",
                "Piso (grade 0,3 a 0,5 kN/m²), sobrecarga, carga linear extra e equipamento no meio",
                "Base técnica / fornecedor",
            ],
            [
                "Critério",
                "Anglo: flecha L/350 ou L/300, espessura mínima 4,8 mm, ligação ≥ 75 % (9.1)",
                "Base técnica do projeto",
            ],
        ]
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Escolha o perfil, o aço e se a viga é principal ou secundária.
        2. Informe o vão e a largura de influência (em geral a distância entre vigas vizinhas).
        3. Ligue **Mesa travada pela grade** só se a fixação da grade travar de fato a mesa
           comprimida; senão a flambagem lateral usa o vão inteiro.
        4. Preencha as cargas características: o programa soma o peso próprio do perfil e monta as
           combinações.
        5. Leia o status, o aproveitamento e a tabela; se houver um perfil mais leve que atende,
           use **Adotar**.
        6. **Registre** no projeto: o memorial ganha o capítulo da viga.
        """
    )

    def _virgula(valor: float) -> str:
        return f"{valor:.1f}".replace(".", ",")

    _e = _vp.EntradaVigaDePiso()
    _r = _vp.calcular(_e)
    _leve = _vp.perfil_mais_leve(_replace(_e, anglo=True))
    mostrar_exemplo(
        [
            ["Perfil", f"{_e.perfil}, {_e.aco}, viga principal"],
            ["Vão e faixa", "4,0 m; 1,0 m de largura de influência, mesa sem travamento"],
            ["Cargas", "piso 0,45 kN/m²; sobrecarga 5,0 kN/m²"],
        ],
        f"Resultado esperado: M_Sd = {_virgula(_r.momento_sd_kNm)} kN·m e M_Rd = "
        f"{_virgula(_r.momento_rd_kNm)} kN·m ({100 * _r.aproveitamento_maximo:.0f} %), flecha "
        f"de {_virgula(_r.flecha_mm)} mm (L/{_e.vao_m * 1000 / _r.flecha_mm:.0f}). Ligando o "
        "critério Anglo, a alma de 4,3 mm fica abaixo dos 4,8 mm do item 8.8 e o mais leve que "
        f"atende passa a ser o {_leve[0] if _leve else '—'}.",
    )
    with st.container(border=True):
        st.subheader("Como interpretar")
        st.markdown(
            """
            - **Flexão:** M_Sd no meio do vão contra M_Rd, o menor entre flambagem lateral (FLT,
              com o C_b da carga), flambagem local da mesa (FLM) e da alma (FLA).
            - **Flecha:** com todas as cargas características; o critério Anglo pede L/350 nas
              principais e L/300 nas secundárias, a NBR 8800 pede L/350 (Anexo C).
            - **Reação:** a característica e a de cálculo; com o critério Anglo, a ligação precisa
              resistir ao menos a 75 % da carga uniforme que a viga suporta (item 9.1).
            - **Frequência:** só informativa; abaixo de uns 3 Hz o piso tende a vibrar ao andar.
            """
        )
    link_modulo("app_pages/viga_de_piso.py", "Abrir Vigas de piso")


elif modulo == "Vento em estruturas abertas":
    from core import contraventamento_plataforma as _cp
    from core import vento_estrutura_aberta as _va
    from core.base_tecnica import numero as _numero_pt

    def _n(valor: float) -> str:
        return _numero_pt(valor, 1)

    st.header("Vento em estruturas abertas")
    st.markdown(
        "Use quando você precisa **só das forças do vento** de uma plataforma, mezanino ou pipe "
        "rack sem fechamento — para anotar no relatório e lançar no modelo. Os pórticos são "
        "**reticulados** (NBR 6123:2023, capítulo 8): C_a pelo índice de área exposta φ "
        "(Figura 12), proteção η dos pórticos de trás (Figura 14), mais guarda-corpos e "
        "equipamentos. Saem a força **por nível**, **por pórtico**, **em cada nó** pilar–viga e a "
        "**carga por metro** nas barras, com desenho e CSV. Os campos são os mesmos da página "
        "Contraventamento de estruturas abertas: o que se digita numa aparece na outra."
    )
    mostrar_tabela_campos(
        [
            ["Planta e pisos", "L_x, L_y, cotas e vãos", "Desenho de arranjo"],
            ["Pilares e vigas", "Largura do pilar vista pelo vento e altura da viga", "Perfis"],
            ["Guarda-corpo", "Altura e índice de área exposta", "Detalhe do guarda-corpo"],
            ["Vento", "V₀, S₁, terreno e S₃ (vêm da base técnica)", "NBR 6123:2023 ou cliente"],
            ["Equipamentos", "Vasos (cilindro) e caixas, com cota e dimensões", "Folhas de dados"],
        ]
    )
    _entrada = entrada_padrao_das_estruturas_abertas()
    _r = _va.calcular_vento_aberto(_cp.geometria_do_vento(_entrada), _entrada.vento)
    mostrar_exemplo(
        [
            ["Planta", "12 × 6 m, um piso a 4 m, 2 vãos em X e 1 em Y, guarda-corpo"],
            ["Vento", "V₀ = 35 m/s, S₁ = 1,0, terreno III, grupo 3"],
        ],
        f"Resultado esperado: {_n(_r.x.total_kN)} kN em X e {_n(_r.y.total_kN)} kN em Y; "
        f"momento na base {_n(_r.x.momento_na_base_kNm)} kN·m em X.",
    )
    with st.container(border=True):
        st.subheader("Como interpretar")
        st.markdown(
            """
            - **Forças nos nós:** o que lançar como carga nodal — a força de cada pórtico em cada
              nível dividida pelos pilares; a soma bate com o total da direção.
            - **Cargas nas barras:** alternativa em kN/m para pilares, vigas e guarda-corpos; as
              diagonais ficam de fora (já estão nas forças nos nós).
            - **Enviar ao plano de cargas** grava W0, W90, W180 e W270 com as forças nos nós.
            - **Registrar** leva as três tabelas (níveis, pórticos e nós) ao memorial.
            """
        )
    st.warning(
        "Fora do escopo: vento oblíquo, efeitos dinâmicos (capítulo 9) e coberturas isoladas — "
        "use o módulo Vento nas estruturas para edificações fechadas e coberturas.",
        icon=":material/warning:",
    )
    link_modulo("app_pages/vento_estrutura_aberta.py", "Abrir Vento em estruturas abertas")


elif modulo == "Contraventamento de estruturas abertas":
    from core import contraventamento_plataforma as _cp

    st.header("Contraventamento de estruturas abertas")
    st.markdown(
        "Use para o **contraventamento vertical** de plataformas, mezaninos, pipe racks e outras "
        "estruturas **sem fechamento**. Com a planta, os pisos, as cargas e o vento do local, o "
        "programa calcula o vento nos pórticos como **reticulados** (NBR 6123:2023, capítulo 8 — "
        "C_a da Figura 12 e proteção η da Figura 14), nos guarda-corpos e nos equipamentos; monta "
        "as **combinações** ELU e ELS com as forças nocionais de 0,3 %; avalia a segunda ordem "
        "(**B₂**); leva o cortante de cada andar às diagonais e verifica barra (cantoneira, tubo ou "
        "tirante), parafusos, solda e deslocamentos pela NBR 8800. A chapa de nó segue para a "
        "página Ligação de contraventamento com um clique."
    )
    mostrar_tabela_campos(
        [
            [
                "Planta, pisos e vãos",
                "L_x, L_y, número de pisos e altura do andar (ou as cotas), vãos em X e em Y",
                "Desenho de arranjo",
            ],
            [
                "Pilares e vigas",
                "Perfis do catálogo: o vento enxerga a maior medida do pilar e a altura da viga",
                "Lista de material ou pré-dimensionamento",
            ],
            [
                "Cargas por piso",
                "Peso da estrutura e do piso (kN/m²), sobrecarga (kN/m²), equipamentos e outras "
                "forças horizontais",
                "Critério do cliente, NBR 6120, folhas de dados dos equipamentos",
            ],
            [
                "Vento",
                "V₀ (isopletas), S₁, categoria do terreno e grupo de S₃",
                "NBR 6123:2023",
            ],
            [
                "Contraventamento",
                "Tipo (X só tração, X tração e compressão, diagonal simples, V invertido), linhas e "
                "painéis por direção, barra e ligação",
                "Desenho do contraventamento",
            ],
        ]
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        1. Informe a **planta** e os **pisos**; escolha os perfis dos pilares e das vigas.
        2. Confira as **cargas** por m²; em "Equipamentos, outras forças horizontais e
           categorias", acrescente vasos, painéis e forças de operação.
        3. Informe o **vento** do local.
        4. Escolha o **contraventamento** e a barra (o padrão é X só tração com cantoneira).
        5. Leia o quadro-resumo; na aba **Combinações e andares** veja a combinação que governa
           cada andar; na aba **Ligação**, leve as forças para a chapa de nó.
        6. **Registre** no projeto para o memorial trazer o vento, as ações, os andares e as
           verificações.
        """
    )
    _ex = _cp.calcular(entrada_padrao_das_estruturas_abertas())
    _gov = _ex.diagonal_governante()
    mostrar_exemplo(
        [
            ["Planta", "12 × 6 m, um piso a 4 m, 2 vãos em X e 1 em Y, guarda-corpo"],
            ["Cargas", "estrutura 0,60, piso 0,45 e sobrecarga 5,0 kN/m²"],
            ["Vento", "V₀ = 35 m/s, terreno III, grupo 3"],
            ["Contraventamento", 'X só tração, 2 linhas × 1 painel, L 2 1/2" × 1/4" A36'],
        ],
        f"Resultado esperado: vento de {_ex.vento.x.total_kN:.1f} kN em X e "
        f"{_ex.vento.y.total_kN:.1f} kN em Y; diagonal mais solicitada em {_gov.direcao} com "
        f"N_t = {_gov.tracao_kN:.1f} kN ({_gov.cortante_elu.expressao}); B₂ = {_gov.b2:.3f} "
        f"(pequena deslocabilidade); aproveitamento máximo de {100 * _ex.aproveitamento_maximo:.0f} %.".replace(
            ".", ","
        ),
    )
    with st.container(border=True):
        st.subheader("Como interpretar")
        st.markdown(
            """
            - **Força nocional:** 0,3 % do peso de cada piso, sempre a favor da segurança, em todas
              as combinações — é a imperfeição da estrutura (4.10.7.1).
            - **Combinação governante:** a envoltória rigorosa tira a variável que alivia e usa
              γ = 1,0 na permanente que alivia; o vento está num grupo exclusivo (+X, −X, +Y, −Y).
            - **B₂:** até 1,10, pequena deslocabilidade; até 1,40, média (forças amplificadas com
              80 % da rigidez); acima, grande — aumente as diagonais.
            - **X só tração:** a diagonal comprimida é desprezada; por isso a esbeltez da
              tracionada (L/r ≤ 300) importa — o tirante dispensa o limite se tiver pré-tensão.
            """
        )
    st.warning(
        "Fora do escopo: pilares, vigas e bases (o programa dá o acréscimo de força nos pilares do "
        "painel), o contraventamento horizontal do piso (grade não é diafragma), efeitos "
        "dinâmicos e sismo. As barras circulares usam o C_a de faces planas (a favor da segurança).",
        icon=":material/warning:",
    )
    link_modulo(
        "app_pages/contraventamento_estrutura.py", "Abrir Contraventamento de estruturas abertas"
    )


elif modulo == "Ligação de contraventamento":
    from components.contraventamento_ui import PERFIS_PADRAO as _perfis_cv
    from core import contraventamento_chapa as _ch
    from core import contraventamento_ligacao as _lig

    st.header("Ligação de contraventamento")
    st.markdown(
        "Use para a **chapa de nó** de um contraventamento vertical que chega ao canto formado "
        "por uma viga e uma coluna: o programa divide a força da barra entre a chapa, a viga e a "
        "coluna pelo **Método das Forças Uniformes** (Design Guide 29 do AISC, caso geral e casos "
        "especiais 1, 2 e 3) e verifica os parafusos da barra, a seção de Whitmore, o bloco de "
        "cisalhamento, a flambagem da chapa, as soldas e a alma da viga e da coluna, em LRFD ou "
        "ASD, com o item do AISC 360-16 em cada linha. Não verifica a barra do contraventamento "
        "nem a chapa de topo parafusada."
    )
    mostrar_tabela_campos(
        [
            [
                "Força P e ângulo θ",
                "Tração e/ou compressão da barra (kN, de cálculo) e o ângulo dela com a vertical; "
                "o atalho H / sen θ converte a força horizontal do vento em força na barra",
                "Módulo Vento nas estruturas e análise do pórtico",
            ],
            [
                "Viga e coluna",
                "d, t_w, t_f, b_f, k, Z_x e I_x do perfil e o aço (ou um perfil do catálogo do "
                "programa, de seção idealizada); chapa na mesa ou na alma da coluna",
                "Catálogo do fabricante do perfil",
            ],
            [
                "Caso e ajuste do método",
                "Geral, ponto de trabalho no canto (1), menos cisalhamento na viga–coluna (2) ou "
                "chapa só na viga (3); e qual medida o programa ajusta (α, β ou o binário)",
                "Arranjo do nó no desenho",
            ],
            [
                "Chapa e parafusos",
                "Espessura e aço da chapa, comprimentos l_h e l_v com os cortes, parafuso, grau, "
                "fileiras, passo, gabarito e extremidade",
                "Desenho da ligação",
            ],
            [
                "Whitmore e flambagem",
                "Comprimento livre da chapa, K e o trecho da seção de Whitmore que cai na alma",
                "Desenho em escala (o programa não vê a geometria)",
            ],
            [
                "Soldas e distorção",
                "Eletrodo, pernas na viga e na coluna e, se quiser, as forças de distorção do "
                "pórtico (área da barra e comprimentos b e c)",
                "Procedimento de soldagem e DG29 seção 4.4",
            ],
        ]
    )
    st.subheader("Passo a passo")
    st.markdown(
        """
        0. Escolha o **modo**: no **simplificado** você informa a força, o ângulo, a viga, a
           coluna e o parafuso, e o programa dimensiona a chapa (parafusos, espessura,
           comprimentos sem momento nas interfaces e soldas); no **completo**, você informa tudo.
        1. Escolha **LRFD** ou **ASD** e informe a força **P** e o ângulo **θ** com a vertical.
        2. Informe a **viga** e a **coluna** (medidas do perfil) e o **caso** do método.
        3. Dê as dimensões da **chapa**, os **parafusos** e as **soldas**.
        4. Leia o **quadro-resumo** e, na aba **Verificações**, cada estado-limite com a norma;
           na aba **Forças e geometria** veja as forças em cada interface e o α̅ e o β̅ ideais.
        5. Se α real e α̅ ideal diferem, há momento nas interfaces: ajuste l_h, l_v ou os
           cortes até os dois coincidirem.
        6. **Registre** no projeto para o memorial levar as verificações e as tabelas.
        """
    )
    _d = _perfis_cv["viga"]
    _c = _perfis_cv["coluna"]
    _viga = _ch.PerfilDoNo(
        _d[0], _d[1], _d[2], _d[3], _d[4], _d[5], 345.0, _d[6] * 1e3, _d[7] * 1e4, 450.0
    )
    _col = _ch.PerfilDoNo(
        _c[0], _c[1], _c[2], _c[3], _c[4], _c[5], 345.0, _c[6] * 1e3, _c[7] * 1e4, 450.0
    )
    _ex = _lig.calcular_ligacao(
        _lig.EntradaLigacao(
            perfil_viga=_viga,
            perfil_coluna=_col,
            t_chapa_mm=25.0,
            lh_mm=800.0,
            lv_mm=600.0,
            perna_na_viga_mm=10.0,
            perna_na_coluna_mm=10.0,
        )
    )
    mostrar_exemplo(
        [
            ["Barra", "P = 800 kN em tração e em compressão, a 45° da vertical, LRFD"],
            ["Perfis", "Viga W 530 × 85 e coluna W 360 × 91 em ASTM A992"],
            [
                "Chapa e parafusos",
                'Chapa de 25 mm em A572 Gr 50, l_h = 800 mm, l_v = 600 mm; 2 × 5 parafusos A325 de 7/8"',
            ],
        ],
        f"Resultado esperado: α̅ = {_ex.forcas.alfa_ideal_mm:.0f} mm e β̅ = "
        f"{_ex.forcas.beta_ideal_mm:.0f} mm; chapa–viga com cisalhante de "
        f"{_ex.forcas.viga_cisalhamento_kN:.0f} kN e normal de {_ex.forcas.viga_normal_kN:.0f} kN; "
        f"aproveitamento máximo de {100 * _ex.aproveitamento_maximo:.0f} % em "
        f"{len(_ex.verificacoes)} linhas.",
    )
    with st.container(border=True):
        st.subheader("Como interpretar")
        st.markdown(
            """
            - **α̅ e β̅ ideais:** posições em que a resultante passa pelo centro das soldas e as
              interfaces ficam sem momento (Eq. 4-1). Se a geometria real diferir, o momento
              aparece na tabela das interfaces.
            - **Caso especial 3:** só para barra muito “deitada” (θ perto de 60° ou mais).
            - **Contraventamento reversível:** as forças das interfaces valem para tração e
              compressão; a compressão acrescenta a flambagem da chapa.
            - **Mesa da coluna (ALERTA):** a flexão local da mesa pede análise própria quando a
              normal H_c é grande; o programa avisa e não aprova sozinho.
            """
        )
    st.warning(
        "Fora do escopo: a barra do contraventamento, a chapa de topo parafusada na coluna e na "
        "viga, ligações em treliça, chevron e base de coluna, e a resistência sísmica. O "
        "programa não vê o desenho: Whitmore, folgas e distâncias mínimas precisam ser "
        "conferidos. Estados-limites e coeficientes são os do AISC 360-16, não os da NBR 8800.",
        icon=":material/warning:",
    )
    link_modulo("app_pages/ligacao_contraventamento.py", "Abrir Ligação de contraventamento")


elif modulo == "Normas técnicas":
    st.header("Biblioteca de normas técnicas")
    st.markdown(
        "Use esta página para descobrir quais famílias normativas devem ser "
        "conferidas e para pesquisar os PDFs que você mantém localmente."
    )
    mostrar_tabela_campos(
        [
            [
                "Pasta monitorada",
                "Pasta padrão ou outro caminho local",
                "Local onde você guarda PDFs licenciados",
            ],
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
                ["Família", "Perfil I duplamente simétrico (bitola real Gerdau)"],
                ["Perfil", 'I 6" x 22,00'],
            ],
            "Valores da tabela do fabricante: área = 27,97 cm², massa = 22,00 kg/m, "
            "Ix = 1.003,00 cm⁴, Sx = 131,63 cm³ e ry = 1,74 cm.",
        )
        st.caption(
            "Os perfis I, U, T, W e HP vêm da tabela de bitolas do fabricante "
            "(Gerdau); os demais (C enrijecido, tubos, barras) continuam "
            "geométricos idealizados. Confirme sempre no catálogo comercial "
            "vigente antes de usar em projeto."
        )

    elif parte == "Barras":
        st.subheader("2. Verificação de barras (NBR 8800)")
        st.markdown(
            """
            Selecione o perfil e informe os esforços **de cálculo** (já combinados):
            N_Sd, M_x,Sd, M_y,Sd e V_Sd. O programa faz o caminho da NBR 8800:
            N_c,Rd = χ·Q·A_g·f_y/γ_a1 (5.3, com λ₀ e a curva única de χ, Q pelo
            Anexo F), M_Rd pelos estados-limites FLT, FLM e FLA (Anexo G), V_Rd
            (5.4.3), interação N–M (5.5.1.2) e esbeltez λ ≤ 200. Para compressão,
            obtenha L e K das condições de apoio; para flexão, o comprimento
            destravado L_b e C_b do diagrama de momentos.
            """
        )
        mostrar_exemplo(
            [
                ["Perfil", 'I 6" x 22,00'],
                ["Material", "f_y = 250 MPa, f_u = 400 MPa, E = 200 GPa, G = 77 GPa"],
                ["N_Sd / M_x,Sd / M_y,Sd / V_Sd", "−100 kN / 20 kN·m / 0 / 20 kN"],
                ["L / K_x / K_y / L_b / C_b", "3 m / 1,0 / 1,0 / 3 m / 1,0"],
            ],
            "Resultado: N_c,Rd = 148,5 kN (χ = 0,234, flambagem em y, λ_y = 172), "
            "M_x,Rd = 26,7 kN·m governado pela FLT em regime inelástico, "
            "V_Rd = 181,0 kN e interação N_Sd/N_Rd + 8/9·M_Sd/M_Rd = 1,34 — "
            "não atende: a barra precisa de travamento lateral ou de perfil maior.",
        )
        st.caption(
            "Utilização até 1 significa apenas que a solicitação de cálculo não "
            "excedeu a resistência de cálculo; os coeficientes γ_a1 = 1,10 e "
            "γ_a2 = 1,35 são os da norma."
        )

    elif parte == "Combinações":
        st.subheader("3. Combinações de ações (NBR 8681 / NBR 8800)")
        st.markdown(
            """
            Cada linha representa uma ação característica. Informe N, V e M com
            sinal e escolha a **categoria** da ação: os coeficientes γ_f e ψ₀, ψ₁,
            ψ₂ das Tabelas 1 e 2 da NBR 8800 entram sozinhos — inclusive a
            combinação com as permanentes favoráveis (γ_g = 1,0), que governa
            vento de sucção e tombamento. A categoria personalizada aceita γ e ψ
            próprios. Saem as combinações ELU normais e as ELS rara, frequente
            e quase permanente.
            """
        )
        mostrar_exemplo(
            [
                [
                    "PP — peso próprio metálico",
                    "N = 50 kN, V = 10 kN, M = 20 kN·m → γ_g = 1,25 / 1,0",
                ],
                [
                    "Piso — elementos industrializados",
                    "N = 10 kN, V = 2 kN, M = 4 kN·m → γ_g = 1,35 / 1,0",
                ],
                [
                    "SC — sobrecarga de uso",
                    "N = 30 kN, V = 5 kN, M = 15 kN·m → γ_q = 1,50, ψ₀ = 0,7",
                ],
                ["W+ / W− — vento", "V = ±20 kN, M = ±40 kN·m → γ_q = 1,40, ψ₀ = 0,6"],
            ],
            "A tabela padrão já contém este exemplo. Abaixo dela, as abas de "
            "**ações de plataforma** calculam o vento pela NBR 6123 "
            "(V_k = V₀·S₁·S₂·S₃, q = 0,613·V_k², w = C_f·q·d), os esforços do "
            "guarda-corpo no montante (H = q·s, M = q·s·h), o impacto de "
            "equipamentos e a conformidade de acessos da NR-12 (guarda-corpo, "
            "rodapé, travessas, largura, Blondel e patamares).",
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
        st.markdown(
            """
            **Placa de base** (AISC Design Guide 1): informe o perfil da coluna,
            N × B × t_p, f_y, f_ck e A₂/A₁ do pedestal, os esforços P (+ compressão),
            M e V na base e os chumbadores (quantidade, lado tracionado, diâmetro,
            f_u e distância f). O programa classifica o caso — compressão centrada,
            momento pequeno (Y = N − 2e) ou grande (tração nos chumbadores) e
            arrancamento — e devolve f_p, Y, a espessura requerida pelo apoio e
            pela tração, a tração e o cisalhamento por chumbador e a interação
            J3.7. A ancoragem no concreto (cone, fendilhamento) e a fundação ficam
            fora e são avisadas.
            """
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
                ["Perfil / E", 'I 4" x 11,46 / 200 GPa'],
            ],
            "Este exemplo já está preenchido. Após analisar, confira primeiro "
            "reações e equilíbrio; depois leia deslocamentos e esforços axiais.",
        )
        st.markdown(
            """
            No **pórtico**, ative a análise de segunda ordem (P–Δ pela rigidez
            geométrica iterada) e a carga nocional de 0,3 % das cargas
            gravitacionais (imperfeições, NBR 8800 4.9.7.1.1). O programa devolve
            o fator de carga crítica global, Δ₁ e Δ₂, a classificação da
            deslocabilidade por Δ₂/Δ₁ (pequena ≤ 1,1; média ≤ 1,4; grande), o
            coeficiente B₂ e o deslocamento horizontal contra H/400 (ou outro
            divisor). Na média deslocabilidade, repita com a rigidez a 80 %.
            """
        )
        st.warning(
            "A treliça é sempre de primeira ordem. O pórtico não considera "
            "plasticidade nem ligações semirrígidas, e a flambagem de cada "
            "barra continua sendo verificada no módulo 2 (NBR 8800).",
            icon=":material/warning:",
        )

    link_modulo("app_pages/estruturas_aco.py", "Abrir estruturas de aço")


st.caption(
    "Guia de uso do programa. Para projeto executivo, confirme propriedades, "
    "coeficientes, combinações e critérios na norma aplicável."
)
