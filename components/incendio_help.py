"""Textos dos "?" da página Estrutura em situação de incêndio, em linguagem simples."""

AJUDA: dict[str, str] = {
    "sec_elemento": "A barra verificada: pilar, tirante ou viga em perfil I ou H.",
    "elemento": (
        "Pilar: compressão com flambagem. Tirante: tração. Viga: momento fletor com a "
        "flambagem lateral com torção."
    ),
    "familia": "De onde vem o perfil: catálogo W/HP, I laminado ou soldado.",
    "perfil": "A bitola do perfil.",
    "d": "Altura total do perfil soldado, em mm.",
    "bf": "Largura das mesas do perfil soldado, em mm.",
    "tf": "Espessura das mesas do perfil soldado, em mm.",
    "tw": "Espessura da alma do perfil soldado, em mm.",
    "aco": "Aço do perfil (a resistência a quente é a de 20 °C vezes k_y,θ).",
    "L": (
        "Pilar: comprimento entre travamentos, em mm (com K, dá o comprimento de flambagem). Viga: "
        "comprimento destravado da mesa comprimida, em mm."
    ),
    "K": "Coeficiente de flambagem do pilar (o mesmo da temperatura ambiente).",
    "Cb": "Fator C_b do diagrama de momento da viga. Na dúvida, 1,0.",
    "viga_hiperestatica": (
        "Ligue para verificar a viga contínua nos apoios: a temperatura menor ali permite κ₂ = 1,15."
    ),
    "sec_fogo": (
        "O tempo de incêndio que a peça precisa aguentar (TRRF) e quanto do perfil fica exposto ao "
        "fogo."
    ),
    "trrf": (
        "Tempo requerido de resistência ao fogo, em minutos, pela NBR 14432 (depende da ocupação "
        "e da altura da edificação). Ex.: 30, 60, 90 ou 120."
    ),
    "exposicao": (
        "Como o fogo envolve o perfil: contorno (proteção projetada que acompanha a forma) ou "
        "caixão (placa em volta), com 4 lados ou 3 (mesa de cima encostada na laje). Muda o "
        "perímetro aquecido e, na viga, o fator κ₁."
    ),
    "temperatura_informada": (
        "Se você já tem a temperatura do aço (de ensaio ou da tabela do fabricante da proteção), "
        "informe em °C; use 0 para o programa calcular pela curva-padrão."
    ),
    "sec_protecao": "O material de proteção contra fogo, se houver.",
    "protecao": (
        "Tipo de proteção. Os valores de condutividade, massa específica e calor específico são "
        "típicos: confira no catálogo do fabricante e ajuste nos campos."
    ),
    "tm": "Espessura da proteção, em mm.",
    "lambda_m": "Condutividade térmica da proteção, em W/m·°C.",
    "rho_m": "Massa específica da proteção, em kg/m³.",
    "c_m": "Calor específico da proteção, em J/kg·°C.",
    "sec_esforcos": (
        "Os esforços característicos (sem majorar) na barra. No incêndio a combinação é "
        "excepcional: só uma parte da sobrecarga entra (fator ψ)."
    ),
    "G_k": "Esforço característico das cargas permanentes: kN (pilar, tirante) ou kN·m (viga).",
    "Q_k": "Esforço característico da sobrecarga de uso: kN ou kN·m.",
    "gama_g": "Coeficiente das permanentes no incêndio (NBR 14323, Tabela 3). Ex.: 1,10 a 1,20.",
    "ocupacao": "O uso do local, que dá o fator ψ da sobrecarga na combinação de incêndio.",
    "res_temperatura": "Temperatura do aço ao fim do TRRF, pela curva-padrão e pela proteção.",
    "res_ky": "Fração da resistência ao escoamento que resta nessa temperatura (k_y,θ).",
    "res_massividade": "Fator de massividade u/A: quanto mais alto, mais rápido o perfil esquenta.",
    "sec_grafico": "Temperatura dos gases (curva-padrão) e do aço ao longo do tempo.",
}
