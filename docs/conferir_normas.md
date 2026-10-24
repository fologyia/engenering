# Checklist "conferir" — rastreabilidade de valores normativos em `core/`

## Propósito

Este arquivo cataloga, uma a uma, as 43 ocorrências da palavra "conferir" encontradas em
`core/` (`grep -in "conferir" core/`), para que nenhum valor normativo digitado "de memória"
fique invisível como dívida técnica antes de emitir documentos de projeto.

**Leitura importante do levantamento (2026-10-22):** a varredura confirmou 43 ocorrências em
21 arquivos, porém a grande maioria é o uso comum do verbo "conferir" em textos de interface,
docstrings e nomes de funções de consistência (`conferir_peso_proprio`, `conferir_coerencia`…),
e não marcadores de valores normativos. Os únicos blocos de valores "de memória" existentes no
código (`CONFERIDOS_NBR8800_2008` em `core/bolted_connection.py` e `core/column_buckling.py`)
**já foram conferidos no texto da norma em 2026-10-17** e estão marcados como certos — por isso
não entram neste checklist. Ainda assim, cada ocorrência foi catalogada abaixo: onde o contexto
(±30 linhas) fixa um valor numérico ou uma referência normativa, ele está explícito na entrada.

## Como atualizar o status

Ao conferir um item na norma física (ou decidir que não se aplica):

- `situacao`: `pendente` → `confirmado`, `ajustado` (valor mudou após a conferência) ou
  `nao_se_aplica` (nota metodológica ou texto de UI).
- `confirmado_em`: data da conferência (AAAA-MM-DD) ou motivo do `nao_se_aplica`.
- `responsavel`: quem conferiu.

Quando um valor for ajustado, atualize também o teste correspondente em
`tests/test_conferir_normas.py` (ele aponta os cálculos afetados). IDs são sequenciais
(CONF-001…) na ordem de arquivo e linha.

---

## core/beam_analysis.py

### CONF-001 — core/beam_analysis.py:2643
- Trecho: `def conferir_equilibrio(resultado: ResultadoViga) -> dict[str, float]:`
- Valor fixado: nenhum valor normativo — controle numérico do próprio solver (resíduo de
  equilíbrio ΣF/ΣM, com momento P–Δ da configuração deformada).
- Referência: — (método interno).
- situacao: pendente
- confirmado_em:
- responsavel:

## core/cena_do_modelo.py

### CONF-002 — core/cena_do_modelo.py:666
- Trecho: `conferencia = ds.conferir_horizontais(...)`
- Valor fixado: nenhum — chamada da conferência gráfica das reações horizontais na cena 3D.
- Referência: — (delega a `core/direcoes_da_secao.py`).
- situacao: pendente
- confirmado_em:
- responsavel:

## core/contraventamento_do_esqueleto.py

### CONF-003 — core/contraventamento_do_esqueleto.py:396
- Trecho: `def conferir_com_a_pagina(`
- Valor fixado: tolerância de comparação página × esqueleto `abs(a − b) > max(0.10, 5 %)` nas
  dimensões L_x × L_y (método interno `longe`).
- Referência: — (critério interno, não normativo).
- situacao: pendente
- confirmado_em:
- responsavel:

## core/contraventamento_vento_barras.py

### CONF-004 — core/contraventamento_vento_barras.py:418
- Trecho: `"O esqueleto não tem vigas deitadas para conferir as cotas dos pisos: ..."`
- Valor fixado: nenhum — aviso de método (sem vigas deitadas, o vento vai aos pisos pelas cotas
  informadas). Comparação de cotas em `cotas_batem` (tolerância `DIFERENCA_DE_COTA_M`).
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

## core/degrau_registro.py

### CONF-005 — core/degrau_registro.py:52
- Trecho: `"Conferir os desenhos-padrão Anglo AA-BR-DPST-ES-0001 a 0004 (Anglo 8.4 e 10.2)."`
  (em `AVISOS_FIXOS`).
- Valor fixado: referências aos desenhos-padrão Anglo AA-BR-DPST-ES-0001 a 0004. A entrada
  seguinte do mesmo tuple fixa a **carga de 2,5 kN do degrau isolado (NBR 6120:2019, Tabela 10,
  nota t; mesma regra do item 2.2.1.7 da edição de 1980)** — coberta pelo teste
  `tests/test_conferir_normas.py`.
- Referência: Anglo AA-BR-DPST-DR-0001 (8.4, 10.2); ABNT NBR 6120:2019 Tabela 10.
- situacao: pendente
- confirmado_em:
- responsavel:

## core/direcoes_da_secao.py

### CONF-006 — core/direcoes_da_secao.py:461
- Trecho: `def conferir_horizontais(`
- Valor fixado: nenhum valor numérico — compara a soma das reações horizontais desenhadas com a
  do arquivo de reações (planta), só quando todos os pilares têm direção definida.
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-007 — core/direcoes_da_secao.py:468
- Trecho: `todos os pilares têm a direção; vazio quando não dá para conferir."""`
- Valor fixado: nenhum — docstring da função acima.
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

## core/esforcos_modelo.py

### CONF-008 — core/esforcos_modelo.py:266
- Trecho: `"modelo, para conferir e preencher. Aqui entram os resultados de cada caso: ..."`
- Valor fixado: nenhum — mensagem de erro orientando o envio do arquivo certo (resultados, não
  gerenciador de casos).
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-009 — core/esforcos_modelo.py:1105
- Trecho: `def conferir_peso_proprio(`
- Valor fixado: reação do caso PP contra o peso da estrutura, com `TOLERANCIA_PESO = 0,05`,
  `COEFICIENTES_USUAIS = (1,25; 1,30; 1,35; 1,40; 1,50)` (γ aparente a ± 2 %), e a dica da razão
  ~10× citando **gravidade 9,81 m/s² e densidade do aço 7 850 kg/m³** — coberto por testes.
- Referência: gravidade 9,81 m/s²; densidade do aço 7 850 kg/m³ (valores usuais de projeto).
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-010 — core/esforcos_modelo.py:1147
- Trecho: `def conferir_reacoes(`
- Valor fixado: `REACAO_NULA_kN = 1e-3` (abaixo disso a soma das reações é zero: modelo sem
  fixação) — coberto por teste da constante.
- Referência: — (limiar interno de consistência).
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-011 — core/esforcos_modelo.py:1168
- Trecho: `"conferir o equilíbrio.",`
- Valor fixado: nenhum — texto do aviso de reação faltante por caso.
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-012 — core/esforcos_modelo.py:1299
- Trecho: `" Monte a Lista de material para conferir com o peso da estrutura."`
- Valor fixado: nenhum — orientação de uso (peso da Lista de material como referência do PP).
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-013 — core/esforcos_modelo.py:1308
- Trecho: `conferir_peso_proprio(`
- Valor fixado: nenhum — chamada da conferência PP dentro de `conferir_reacoes`.
- Referência: — (ver CONF-009).
- situacao: pendente
- confirmado_em:
- responsavel:

## core/exportacao_cargas.py

### CONF-014 — core/exportacao_cargas.py:721
- Trecho: `"arquivo na página Plano de cargas (Conferir e preencher): o programa liga cada carga do "`
- Valor fixado: nenhum novo — instrução de exportação; o contexto (linhas 710–716) cita a
  **gravidade −9,81 m/s²** com convenção de sinal e plano de referência do SolidWorks.
- Referência: gravidade 9,81 m/s² (convenção de sinal do SolidWorks).
- situacao: pendente
- confirmado_em:
- responsavel:

## core/guarda_corpo_do_modelo.py

### CONF-015 — core/guarda_corpo_do_modelo.py:24
- Trecho: `Tudo é sugestão para o engenheiro conferir (desmarcar o lado da parede, o portão…).`
- Valor fixado: nenhum — nota metodológica. O contexto fixa o critério geométrico de acesso da
  escada: duas longarinas paralelas a **0,5–2,0 m** uma da outra.
- Referência: — (critério geométrico interno).
- situacao: pendente
- confirmado_em:
- responsavel:

## core/leitura_do_modelo.py

### CONF-016 — core/leitura_do_modelo.py:2222
- Trecho: `def conferir_tensoes(`
- Valor fixado: nenhum valor numérico — as tensões do SolidWorks são só referência; a
  verificação normativa é pelos esforços (inclui conferência do módulo resistente usado pelo
  Simulation contra o W do perfil).
- Referência: ABNT NBR 8800 (verificação pelos esforços: flambagem, FLT, interação).
- situacao: pendente
- confirmado_em:
- responsavel:

## core/ligacoes.py

### CONF-017 — core/ligacoes.py:1138
- Trecho: `"barra comprimida: informe a força axial resistente da barra para conferir",`
- Valor fixado: regra **"Ligação ≥ 50 % da força axial resistente da barra"** (item de
  verificação com status ALERTA quando a força não é informada).
- Referência: ABNT NBR 14762, item 10.1 a).
- situacao: pendente
- confirmado_em:
- responsavel:

## core/lista_de_material.py

### CONF-018 — core/lista_de_material.py:1
- Trecho: `"""Lista de material e peso da estrutura: para o orçamento e para conferir o peso próprio do modelo.`
- Valor fixado: nenhum novo — docstring do módulo; o módulo fixa `DENSIDADE_ACO = 7850 kg/m³` e
  `G = 9,80665 m/s²` (linhas 36–37).
- Referência: densidade do aço 7 850 kg/m³; gravidade 9,80665 m/s².
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-019 — core/lista_de_material.py:350
- Trecho: `def conferir_com_o_modelo(`
- Valor fixado: `fator_peso_proprio: float = 1,0` (ligações não modeladas entram multiplicando a
  gravidade) e peso = massa × G / 1e3.
- Referência: — (ver CONF-018).
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-020 — core/lista_de_material.py:363
- Trecho: `f"Para conferir com o modelo, importe em Esforços do modelo o caso {caso} com o "`
- Valor fixado: nenhum — mensagem orientativa.
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-021 — core/lista_de_material.py:381
- Trecho: `return [em.conferir_peso_proprio(vertical, peso * fator_peso_proprio, origem)]`
- Valor fixado: nenhum novo — delega a conferência PP (ver CONF-009).
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-022 — core/lista_de_material.py:684
- Trecho: `def _conferir_secoes(`
- Valor fixado: tolerâncias da conferência de seção: **3 %** (peças de corte reto, área exata),
  **15 %** (cortes inclinados) e **± 2 %** para adoção de perfil da mesma família com a mesma área.
- Referência: catálogo de perfis (Gerdau) usado como referência de área.
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-023 — core/lista_de_material.py:913
- Trecho: `adotados, divergentes = _conferir_secoes(itens, secoes)`
- Valor fixado: nenhum — chamada da conferência de seções (ver CONF-022).
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

## core/material_catalog.py

### CONF-024 — core/material_catalog.py:192
- Trecho: `def conferir_coerencia(material: MaterialCadastrado) -> list[str]:`
- Valor fixado: faixa de coerência **Sy/Sut entre 0,30 e 0,95** para aços (avisos de digitação;
  o piso 0,30 acomoda inoxidável austenítico recozido ~0,36) e aviso para **Sut > 2 000 MPa** —
  coberto por testes.
- Referência: — (faixa usual de projeto, não normativa).
- situacao: pendente
- confirmado_em:
- responsavel:

## core/memorial_verificacoes.py

### CONF-025 — core/memorial_verificacoes.py:15
- Trecho: `e o que o módulo manda conferir antes de emitir — ...`
- Valor fixado: nenhum — docstring do capítulo de verificações do memorial.
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-026 — core/memorial_verificacoes.py:19
- Trecho: `o mesmo roteiro — resultado, dados de entrada, método, tabelas do módulo e o que conferir —, ...`
- Valor fixado: nenhum — docstring (roteiro do capítulo).
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-027 — core/memorial_verificacoes.py:1061
- Trecho: `"""O fim do capítulo: o que não passou, o que pede atenção e o que o módulo manda conferir."""`
- Valor fixado: nenhum — docstring.
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-028 — core/memorial_verificacoes.py:1131
- Trecho: `blocos.append({"tipo": "subtitulo", "texto": "Conferir antes de emitir", ...})`
- Valor fixado: nenhum — rótulo de seção do memorial.
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-029 — core/memorial_verificacoes.py:1247
- Trecho: `legíveis, o método e as tabelas do módulo, e fecha com o que o módulo manda conferir.`
- Valor fixado: nenhum — docstring.
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-030 — core/memorial_verificacoes.py:1292
- Trecho: `blocos.append({"tipo": "subtitulo", "texto": "Conferir antes de emitir", ...})`
- Valor fixado: nenhum — rótulo de seção do memorial.
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

## core/memorial_word.py

### CONF-031 — core/memorial_word.py:558
- Trecho: `"Documento editável - conferir código, revisão e aprovações antes da emissão.",`
- Valor fixado: nenhum — nota de rodapé do documento Word.
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

## core/navegacao.py

### CONF-032 — core/navegacao.py:185
- Trecho: `"Dimensionar ou conferir uma junta parafusada",`
- Valor fixado: nenhum — legenda de navegação (menu da junta parafusada).
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-033 — core/navegacao.py:211
- Trecho: `"Conferir as pendências do projeto e gerar o memorial em Word ou PDF.",`
- Valor fixado: nenhum — legenda de navegação.
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-034 — core/navegacao.py:217
- Trecho: `"Conferir pendências e preparar a liberação do projeto",`
- Valor fixado: nenhum — legenda de navegação.
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

## core/plano_de_cargas.py

### CONF-035 — core/plano_de_cargas.py:647
- Trecho: `def conferir_plano(plano: PlanoDeCargas, *, anglo: bool = False) -> list[ItemDeConferencia]:`
- Valor fixado: regras de consistência do plano — vento exige os quatro sentidos
  **W0/W90/W180/W270**; temperatura exige os dois sentidos **T+ e T− (±10 °C, critério Anglo
  5.8)** — coberto por testes.
- Referência: Critério Anglo AA-BR-DPST-DR-0001, item 5.8 (ΔT ± 10 °C).
- situacao: pendente
- confirmado_em:
- responsavel:

## core/project_assistant.py

### CONF-036 — core/project_assistant.py:121
- Trecho: `"Dimensionar ou conferir uma junta parafusada",`
- Valor fixado: nenhum — objetivo do assistente de projeto (mesmo texto de CONF-032).
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

## core/quadro_fundacoes.py

### CONF-037 — core/quadro_fundacoes.py:117
- Trecho: `return QuadroDeFundacoes(tuple(pilares), casos, tuple(_conferir(dados, pilares)))`
- Valor fixado: nenhum — montagem do quadro com itens de conferência.
- Referência: — (ver CONF-038).
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-038 — core/quadro_fundacoes.py:120
- Trecho: `def _conferir(`
- Valor fixado: tolerância da soma das normais nas bases contra a reação vertical do modelo:
  **diferença ≤ max(2 % de |N_vertical|, 0,1 kN)**.
- Referência: — (critério interno de equilíbrio).
- situacao: pendente
- confirmado_em:
- responsavel:

## core/roteiro.py

### CONF-039 — core/roteiro.py:4
- Trecho: `que arquivo sai, e o que conferir antes de seguir. A situação de cada passo sai do documento do`
- Valor fixado: nenhum — docstring do roteiro do projeto com o SolidWorks.
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-040 — core/roteiro.py:44
- Trecho: `conferir: str`
- Valor fixado: nenhum — campo do dataclass `Passo` (o que conferir antes de seguir).
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-041 — core/roteiro.py:173
- Trecho: `"Importar e conferir as reações",`
- Valor fixado: nenhum — título do passo 9 do roteiro.
- Referência: — .
- situacao: pendente
- confirmado_em:
- responsavel:

### CONF-042 — core/roteiro.py:290
- Trecho: `for i in pc.conferir_plano(plano, anglo=bool(base and base.anglo))`
- Valor fixado: nenhum novo — o roteiro reusa `conferir_plano` (ver CONF-035).
- Referência: — (ver CONF-035).
- situacao: pendente
- confirmado_em:
- responsavel:

## core/section_catalog.py

### CONF-043 — core/section_catalog.py:132
- Trecho: `def conferir_coerencia(perfil: PerfilAco) -> list[str]:`
- Valor fixado: avisos de coerência interna do catálogo — **Z/W entre 1,0 e 1,8** (perfis
  metálicos), **massa esperada = área × 7 850 kg/m³ com tolerância de 12 %**, e aviso de Iy > Ix
  (eixos trocados) — coberto por testes.
- Referência: densidade do aço 7 850 kg/m³.
- situacao: pendente
- confirmado_em:
- responsavel:
