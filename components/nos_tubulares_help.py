"""Textos dos "?" da página Nós de treliça tubular, em linguagem simples."""

AJUDA: dict[str, str] = {
    "sec_no": (
        "O tipo de nó da treliça: as diagonais (montantes) soldadas direto na parede do banzo, "
        "sem chapa. Quem costuma falhar é a parede do banzo, não a solda."
    ),
    "forma": "Circular (CHS) ou retangular/quadrado (RHS). Banzo e diagonais da mesma forma.",
    "tipo": (
        "T ou Y: uma diagonal chega no banzo (T a 90°, Y inclinada). X: duas diagonais opostas, "
        "uma de cada lado do banzo, na mesma linha. K ou N: duas diagonais do mesmo lado, com um "
        "afastamento g entre elas (N quando uma delas é perpendicular)."
    ),
    "aco_banzo": "Aço do tubo do banzo. Ex.: VMB 350 (f_y = 350 MPa).",
    "aco_diagonais": "Aço dos tubos das diagonais.",
    "sec_banzo": "As medidas do banzo e os esforços nele junto do nó.",
    "b0": "Banzo: diâmetro externo (circular) ou largura da face onde as diagonais chegam (retangular), em mm.",
    "h0": "Banzo retangular: altura no plano da treliça, em mm.",
    "t0": "Espessura da parede do banzo, em mm.",
    "N0": (
        "Força normal de cálculo no banzo, do lado mais comprimido do nó, em kN (tração +, "
        "compressão −). Compressão no banzo reduz a resistência do nó (fatores k_p e k_n)."
    ),
    "M0": "Momento fletor de cálculo no banzo junto do nó, em kN·m (soma à compressão da parede).",
    "sec_diagonais": "As medidas, os ângulos e as forças de cálculo das diagonais.",
    "b1": "Diagonal 1: diâmetro (circular) ou largura (retangular), em mm.",
    "h1": "Diagonal 1 retangular: altura no plano da treliça, em mm.",
    "t1": "Diagonal 1: espessura da parede, em mm.",
    "theta1": "Ângulo entre a diagonal 1 e o banzo, em graus (90° = perpendicular). Mínimo 30°.",
    "N1": "Força axial de cálculo na diagonal 1, em kN (tração +, compressão −).",
    "b2": "Diagonal 2: diâmetro (circular) ou largura (retangular), em mm.",
    "h2": "Diagonal 2 retangular: altura no plano da treliça, em mm.",
    "t2": "Diagonal 2: espessura da parede, em mm.",
    "theta2": "Ângulo entre a diagonal 2 e o banzo, em graus.",
    "N2": "Força axial de cálculo na diagonal 2, em kN (tração +, compressão −).",
    "g": (
        "Afastamento: distância livre entre os pés das duas diagonais, medida na face do banzo, "
        "em mm. Precisa ser pelo menos t₁ + t₂ para dar para soldar."
    ),
    "gama": (
        "Coeficiente de ponderação da resistência do nó. A NBR 16239 usa γ_a1 = 1,10 nas "
        "expressões do EN 1993-1-8 (que usa γ_M5 = 1,0)."
    ),
}
