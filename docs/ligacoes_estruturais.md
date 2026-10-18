# Ligações estruturais

Página **Ligações estruturais** (`app_pages/ligacoes_estruturais.py`), núcleo em `core/ligacoes.py`.
Os esforços entram **de cálculo** (combinação ELU) — por exemplo a reação da viga de piso ou da
longarina. Unidades: mm, MPa, kN e kN·m. Os coeficientes foram conferidos no texto da NBR 8800:2008
e da NBR 14762:2010; o Projeto de revisão da NBR 8800 (2024) muda só o coeficiente do corte do
parafuso (0,45/0,56), via `core/bolted_connection.py`.

## 1. Chapa simples (viga–viga e viga–pilar) — NBR 8800

Chapa soldada no apoio (alma da viga principal, mesa ou alma do pilar) com dois filetes e parafusada
na alma da viga apoiada, numa linha vertical; mesa superior recortada ou não.

| Verificação | Fórmula | Item |
|---|---|---|
| Parafuso mais solicitado | grupo elástico com V, N e M = V·a; F_Rd = mín(F_v,Rd; F_c,Rd chapa; F_c,Rd alma) | 6.3.3.2, 6.3.3.3 |
| Chapa: escoamento e ruptura por cisalhamento | 0,60·f_y·A_g/γ_a1; 0,60·f_u·A_nv/γ_a2 | 6.5.5 |
| Chapa: colapso por rasgamento | (0,60·f_u·A_nv + C_ts·f_u·A_nt)/γ_a2 ≤ (0,60·f_y·A_gv + C_ts·f_u·A_nt)/γ_a2 | 6.5.6 |
| Chapa: flexão | V·a ≤ f_y·t·h²/4/γ_a1 | 5.4.2 |
| Chapa: tração / compressão | mín(A_g·f_y/γ_a1; A_e·f_u/γ_a2), A_e = A_n ≤ 0,85·A_g / A_g·f_y/γ_a1 | 6.5.3, 6.5.4 |
| Alma da viga: cisalhamento | escoamento e ruptura na linha dos furos (altura recortada) | 6.5.5 |
| Alma recortada | colapso por rasgamento; flexão V·c com só a alma (a favor da segurança); faixa usual do recorte | 6.5.6; AISC Manual Parte 9 |
| Solda no apoio | método elástico com V, N e V·a; 0,60·f_w·(0,707·perna)/γ_w2 | Tabela 8 |
| Metal-base do apoio | 2 filetes na espessura do apoio ≤ 0,60·f_y·t/γ_a1 | 6.5.5 |
| Perna mínima, máxima e comprimento | Tabela 10; t ou t − 1,5 mm; ≥ 4·perna e 40 mm | 6.2.6.2 |
| Disposições | espaçamentos e distâncias às bordas (tipo "limite": não entram no aproveitamento) | 6.3.9 a 6.3.12 |
| Ductilidade | chapa ou alma ≤ d_b/2 + 1,6 mm (ALERTA) | AISC Manual Parte 10 |

A favor da segurança, o momento V·a entra nos parafusos **e** na solda, e a pressão de contato usa a
menor distância livre ℓ_f de cada parte em qualquer direção.

## 2. Perfil formado a frio parafusado — NBR 14762:2010

Perfil ligado pela alma a uma chapa, grade de parafusos com forças iguais (sem momento no grupo).

| Verificação | Fórmula | Item |
|---|---|---|
| Corte do parafuso | 0,4 (rosca no plano) ou 0,5·A_b·f_ub/1,35 por plano | 10.3.7 |
| Rasgamento | t·e·f_u/1,45 (e = borda ou passo, na direção da força) | 10.3.4 |
| Esmagamento | α_e·d·t·f_u/1,55, α_e = 0,183·t + 1,53 | 10.3.5 |
| Tração no perfil | mín(A·f_y/1,10; C_t·A_n·f_u/1,65), C_t = 1 − 1,2·x̄/L ∈ [0,4; 0,9] ou 2,5·d/g | 9.6.2 |
| Colapso por rasgamento | (0,6·A_gv·f_y + A_nt·f_u)/1,65 e (0,6·A_nv·f_u + A_nt·f_u)/1,65 | 10.4 |
| Espaçamentos | livre entre furos ≥ 2·d; livre à borda ≥ d | 10.3.3.1 |
| Regra dos 50 % | barra de treliça/contraventamento: ligação ≥ 0,5·N_Rd da barra | 10.1 a) |

Peça com mais de 4,75 mm segue a NBR 8800 (10.3.1). Furo-padrão d + 0,8 (d < 12,5 mm) ou d + 1,5 mm
(Tabela 15). Aços: Tabela 1 (ZAR, CF) e o limite de 180/300 MPa para aço sem qualificação (4.2);
parafusos: Tabela 16 e 300 MPa sem qualificação (4.4).

## 3. Grupo de soldas de filete

Um filete, dois paralelos ou o contorno de um retângulo, com V, N e momento no plano (método
elástico, por unidade de comprimento). Chapa mais fina acima de 4,75 mm: NBR 8800 Tabela 8 (metal da
solda) e 6.5.5 (metal-base). Até 4,75 mm: NBR 14762 10.2.3 (metal-base fino pela direção mais
desfavorável e, com t > 2,5 mm, 0,75·t_ef·f_w/1,65). Limites de perna e de comprimento da 6.2.6.2.

## Fora do programa

Ligação rígida (com momento), chapa de extremidade, enrijecedores, efeito de alavanca, parafusos
auto-atarraxantes e a verificação do apoio como um todo — casos específicos ficam com o projetista.
