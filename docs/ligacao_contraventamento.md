# Ligação de contraventamento — escopo, fórmulas e conferências

A página **Ligação de contraventamento** dimensiona a **chapa de nó** de um contraventamento vertical
que chega ao canto formado por uma viga e uma coluna. Divide a força da barra entre a chapa, a viga e
a coluna pelo **Método das Forças Uniformes** (UFM) do *Design Guide 29* do AISC (Muir e Thornton,
2014) e fecha o conjunto com as verificações do **ANSI/AISC 360-16**, em LRFD (φ·R_n) ou ASD (R_n/Ω).
Os estados-limites e os coeficientes são os do AISC, não os da NBR 8800. O núcleo não depende do
Streamlit.

| Arquivo | O que faz |
| --- | --- |
| `core/contraventamento_ufm.py` | forças nas interfaces (caso geral e casos especiais 1, 2 e 3), α̅ e β̅ ideais, distorção |
| `core/contraventamento_chapa.py` | estados-limites: parafusos, Whitmore, bloco de cisalhamento, flambagem, soldas, alma e mesa |
| `core/contraventamento_ligacao.py` | orquestra tudo e fecha a tabela de verificações (`calcular_ligacao`) |
| `core/contraventamento_registro.py` | registro no projeto, tabelas do memorial, texto de destaque |
| `components/contraventamento_ui.py`, `contraventamento_help.py` | interface e textos dos "?" |
| `app_pages/ligacao_contraventamento.py` | a página |

## O que faz e o que não faz

**Faz:** distribui a força P do contraventamento (tração e/ou compressão) entre a chapa–viga, a
chapa–coluna e a ligação viga–coluna; calcula os α̅ e β̅ ideais (sem momento nas interfaces) e o
momento que sobra quando a geometria real difere; verifica os parafusos da barra (cisalhamento ×
contato), a seção de Whitmore (escoamento e flambagem), o bloco de cisalhamento, as interfaces da
chapa (cisalhamento, tração e interação), as soldas (perna necessária × adotada × mínima) e a alma e
a mesa da viga e da coluna (escoamento local, enrugamento, flexão local da mesa e cisalhamento).
Inclui as forças de distorção do pórtico (DG29 4.4), se pedidas.

**Não faz:** a barra do contraventamento; a chapa de topo parafusada na coluna e na viga (parafusos
tracionados, alavanca — Exemplo 5.1 do guia); ligações em treliça, chevron e base de coluna
(Exemplos 5.9 a 5.12); resistência sísmica (Capítulo 6). O programa não vê o desenho: Whitmore,
comprimento livre da chapa, folgas e distâncias mínimas precisam ser conferidos.

## Forças (UFM)

* Equilíbrio sem momento nas interfaces: `α̅ − β̅·tanθ = e_b·tanθ − e_c` (Eq. 4-1).
* `r = √((α̅ + e_c)² + (β̅ + e_b)²)`; `H_b = α̅·P/r`; `V_b = e_b·P/r`; `V_c = β̅·P/r`; `H_c = e_c·P/r`.
* Momentos quando a geometria real difere: `M_b = V_b·(α − α̅)` (Eq. 4-2); `M_c = H_c·(β − β̅)`
  (Eq. 4-3).
* Ligação viga–coluna: `V = V_b + reação da viga`; axial `= H_c + H′` (transferência). Com distorção,
  `T = H_c − H_D + A` (guia, p. 71).
* **Caso especial 1** (ponto de trabalho no canto da chapa): excentricidade `e`, `M = P·e`, divisão
  entre viga e coluna por `η = Z_b / (Z_b + 2 Z_c)` e forças `H′`, `V′` somadas às do UFM (Eq. 4-5
  a 4-8).
* **Caso especial 2:** tira `ΔV_b` (ou todo o `V_b`) da ligação viga–coluna e leva à chapa.
* **Caso especial 3:** chapa só na viga (`α̅ = e_b·tanθ − e_c`, β̅ = 0); avisa se `θ` é menor que 55°.

## Verificações (AISC 360-16)

Parafusos J3.6 e J3.10 (menor entre cisalhamento e contato, com `ℓ_c = e − d_h/2` no da extremidade e
`s − d_h` nos internos); Whitmore: largura `g + 2·L·tan30°`, escoamento J4.1 e flambagem E3 (`K`,
comprimento livre); bloco de cisalhamento J4.3; interfaces da chapa: cisalhamento J4.2, tração
`N + 2M/l` e interação `(M/M_n)² + (N/N_n)² + (V/V_n)⁴ ≤ 1`; solda de filete J2.4 com o fator
`1 + 0,50·sen^1,5 θ`, fator de ductilidade 1,25 e perna mínima da Tabela J2.4; alma e mesa J10.1 a
J10.3 e cisalhamento da alma J10.6.

## Conferência contra o guia

`tests/test_contraventamento_ufm.py` reproduz os Exemplos 5.1 a 5.4 do DG29 (forças das interfaces,
α̅, β̅, momentos e os casos especiais). `tests/test_contraventamento_ligacao.py` reproduz as
resistências do Exemplo 5.1 em LRFD e em ASD (parafusos 855 kips, Whitmore 968 kips, bloco de
cisalhamento 858 kips, soldas 9,8 mm e 8,8 mm necessários). Diferenças deliberadas: a **flambagem da
chapa** usa a área efetiva de Whitmore (conservador: o guia usa uma área de 20,9 in² que não é
reproduzível pelos dados publicados) e as unidades são convertidas (1 kip = 4,448222 kN).

## Registro e memorial

O registro leva as entradas, as verificações (`resultados.verificações`), a tabela das **forças nas
interfaces** (como a Tabela 5-1 do guia) e a da **geometria do nó**. O memorial traz o resultado, o
que passou e, no fim, o que não passou; os campos vazios ficam como `[a preencher]`.

## Pendências

* Ler a força do contraventamento direto do registro do módulo **Vento nas estruturas**
  (`P = H / sen θ`; hoje é um atalho de cálculo na página).
* Chapa de topo parafusada (Exemplo 5.1 completo) e as demais configurações do Capítulo 5.
