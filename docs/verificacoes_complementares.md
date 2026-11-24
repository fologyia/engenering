# Verificações complementares de estrutura metálica

Dez páginas novas no grupo **Estrutura metálica** cobrem as verificações que aparecem em quase todo
projeto industrial e que o programa ainda não fazia. Todas seguem o mesmo molde:

- núcleo puro em `core/` (sem Streamlit), com as contas e o item da norma em cada linha;
- página em `app_pages/` com "?" de ajuda em linguagem simples em todos os campos
  (`components/*_help.py`), feita com `components/pagina_padrao.py`;
- resultado em grupos de linhas (`core/verificacao_modulo.py`): situação, maior aproveitamento e a
  verificação que governa;
- memorial separado (trecho em Word para colar no documento oficial, ou PDF) e registro no projeto,
  que leva o cálculo ao Memorial de cálculo do projeto;
- capítulo no Guia geral (`components/guia_verificacoes.py`) com o exemplo dos valores de partida.

Os perfis I e H (W/HP com o raio de concordância da tabela da Gerdau, I laminado ou soldado) vêm de
`core/perfil_i.py`.

## As páginas

| Página | Arquivo do núcleo | Base normativa | O que verifica |
|---|---|---|---|
| Forças localizadas na alma | `core/forcas_localizadas.py` | NBR 8800:2025, 5.7 | Flexão local da mesa, escoamento local, enrugamento, flambagem lateral e instabilidade da alma; enrijecedores (5.7.9): proporções, barra comprimida com 12·t_w ou 25·t_w de alma, esmagamento, tração e soldas |
| Viga de monovia | `core/monovia.py` | NBR 8800:2025; EN 1993-6, 6.7; critério Anglo | Impacto, força lateral, flexão vertical (FLT) e lateral só na mesa de baixo, cortante, flexão local da mesa sob as rodas (l_eff da Tabela 6.2), tensões locais combinadas (alerta), flechas L/500 e L/400, mesa no apoio |
| Contenção lateral (travamentos) | `core/contencao_lateral.py` | NBR 8800:2025, 4.12 | F_br e S_br de pilares e vigas (translação); M_br, S_T, S_sec e S_Tb da contenção de torção nodal e contínua; barra de travamento inclinada com a ligação em série |
| Viga mista | `core/viga_mista.py` | NBR 8800:2025, Anexo L | Largura efetiva, conector (pino com cabeça), momento plástico (casos a, b, c), grau mínimo de interação, cortante no perfil, construção não escorada, flecha com I efetivo e fluência (α_E × 3), espaçamento e diâmetro dos conectores |
| Aberturas na alma | `core/aberturas_alma.py` | NBR 8800:2025, Anexo F; AISC Design Guide 2 | Dispensa de F.3 (furos circulares); fora dela, M_m, V_m, interação cúbica e limites de proporção do guia |
| Terças e travessas | `core/tercas.py` | NBR 14762:2010 | Seção efetiva (MSE, k_ℓ da Tabela 13), FLT entre linhas de corrente, distorcional (Tabela 14 ou M_dist informado), sucção pelo Anexo F (fator R), cortante, interação, flexão oblíqua, flechas da Tabela A.1 |
| Ligação rígida viga–pilar | `core/ligacao_rigida.py` | NBR 8800:2025; AISC 358-16 cap. 6; AISC DG 4 e 16 | Chapa de extremidade estendida 4E: parafusos, Y_p, chapa grossa, extensão da chapa, corte e contato, soldas, Y_c da mesa do pilar, alma e painel de alma do pilar, enrijecedores de continuidade, disposições |
| Nós de treliça tubular | `core/nos_tubulares.py` | EN 1993-1-8, cap. 7 (NBR 16239) | Nós T, Y, X e K/N com afastamento em tubo circular (Tabela 7.2) e retangular (Tabela 7.11), com a faixa de validade (Tabelas 7.1 e 7.8) |
| Fadiga da estrutura | `core/fadiga_estrutural.py` | NBR 8800:2025, Anexo H | Faixa admissível por categoria (A a G, C' e C''), dispensas de H.2.5 e H.2.6, limite de H.2.2 |
| Estrutura em incêndio | `core/incendio.py` | NBR 14323; NBR 14432; ISO 834 | Temperatura do aço com e sem proteção, k_y,θ e k_E,θ, tração, compressão (χ_fi) e flexão de viga (FLT) na combinação de incêndio |

O grupo Estrutura metálica ganhou o submenu **Fadiga e incêndio**. No memorial do projeto, as
vigas entram em "Vigas, eixos e pisos", as ligações em "Ligações" e fadiga e incêndio numa etapa
própria.

## Simplificações e o que fica fora

- **Forças localizadas:** a barra comprimida do enrijecedor (5.7.9.4) é verificada para a força
  total da seção; esmagamento, tração e soldas, para a diferença entre a força e a resistência da
  alma. I laminado sem raio no catálogo usa k = t_f (a favor da segurança).
- **Monovia:** balanço tratado como engastado; a força lateral é resistida só pela mesa de baixo;
  a tensão combinada local + global é alerta (a NBR não tem essa verificação). Fadiga da monovia
  na página de fadiga.
- **Ligação rígida:** só a 4E sem nervura e com chapa grossa (sem efeito de alavanca, que o
  programa avisa quando a chapa não é grossa); a viga em si é verificada à parte.
- **Contenção lateral:** a barra de travamento é verificada com K = 1 e Q = 1.
- **Viga mista:** biapoiada, carga uniforme, perfil duplamente simétrico; armadura de costura
  (L.1.3.4) e fissuração (L.5) ficam com o projeto da laje.
- **Aberturas na alma:** aberturas sem reforço em viga de aço biapoiada com carga uniforme; γ_a1 da
  NBR no lugar de φ = 0,90 do guia.
- **Terças:** U enrijecido biapoiado; C_w estimado sem os enrijecedores de borda (a favor da
  segurança); a flambagem distorcional sem dispensa pela Tabela 14 pede M_dist de uma análise de
  estabilidade elástica (faixas finitas) — sem ele, a linha fica "a verificar".
- **Nós tubulares:** só forças axiais nas diagonais, nós planos, sem sobreposição; fora da faixa de
  validade o nó não é aceito; γ_a1 = 1,10 no lugar de γ_M5.
- **Incêndio:** temperatura uniforme, elemento interno; propriedades de proteção típicas (a
  conferir com o fabricante); viga só com momento fletor (perfil compacto); na FLT entre λ_p e λ_r,
  k_y,θ aplicado à interpolação entre M_pl e M_r.

## Testes

Um arquivo por página (`tests/test_<modulo>.py`) com as contas de mão, os casos de borda, o
registro e o memorial, os textos de ajuda e a página aberta pelo AppTest (todo campo com "?").
`tests/test_guia_verificacoes.py` confere os capítulos do guia e que o exemplo dá o número que a
página mostra. O apoio comum fica em `tests/apoio_paginas.py`.

## Integração com as páginas que já existiam

- **Vigas de piso** — seção "3b. Apoio e equipamento na mesa": quando a viga se apoia pela mesa de
  baixo, a reação é verificada pela 5.7 (escoamento local e enrugamento da alma); o equipamento no
  meio do vão também (com a flambagem lateral da alma, pelo trecho sem travamento e pela opção "a
  grade impede a mesa de girar"). Se não passar, a linha "enrijecedores necessários" sugere a
  medida. Núcleo: `core/viga_de_piso.forcas_na_alma`, que usa `core/forcas_localizadas.verificar_forcas`.
- **Flambagem de colunas** — com os travamentos informados, a seção "Travamentos que a coluna
  exige (NBR 8800 4.12)" mostra F_br e S_br de cada eixo, e o botão "Verificar a barra de
  travamento" abre a Contenção lateral com N_Sd, o maior trecho e o número de travamentos.
- **Roteiro do projeto** — aba nova "Verificações complementares": lê o plano de cargas (monovia,
  ponte rolante, impacto, equipamentos), a lista de material (tubos, perfis dobrados) e os registros
  (vigas, pilares) e mostra, para cada uma das dez verificações, se está registrada, se o projeto a
  indica (com o motivo) ou se vale só quando houver o caso (`core/verificacoes_do_projeto.py`). O
  passo 12 do roteiro cita as complementares.
