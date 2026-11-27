"""Esquemas conceituais para páginas que ainda não possuem desenho próprio."""

from components.figuras import mostrar_figura

# São exemplos fixos para identificação visual, não a geometria calculada pelo formulário.
_CROQUIS = {
    "aberturas_alma": (
        "Abertura na alma",
        '<rect x="80" y="65" width="400" height="120" fill="#dbeafe" stroke="#334155" stroke-width="4"/><path d="M80 65H480 M80 185H480" stroke="#334155" stroke-width="10"/><circle cx="280" cy="125" r="35" fill="white" stroke="#2563eb" stroke-width="4"/>',
        "Viga de aço",
        "Abertura",
    ),
    "contencao_lateral": (
        "Contenção lateral",
        '<path d="M70 125H490" stroke="#334155" stroke-width="18"/><path d="M180 65V185 M380 65V185" stroke="#2563eb" stroke-width="7"/><path d="M150 65h60 M350 65h60 M150 185h60 M350 185h60" stroke="#2563eb" stroke-width="4"/>',
        "Barra",
        "Travamentos laterais",
    ),
    "forcas_localizadas": (
        "Força localizada na alma",
        '<path d="M80 65H480 M80 185H480" stroke="#334155" stroke-width="10"/><path d="M80 65H480V185H80Z" fill="#dbeafe" stroke="#334155" stroke-width="3"/><path d="M280 12V55 M270 43l10 12 10-12" fill="none" stroke="#dc2626" stroke-width="5"/>',
        "Viga",
        "Força concentrada",
    ),
    "incendio": (
        "Estrutura em incêndio",
        '<path d="M120 65H440 M120 185H440 M280 65V185" stroke="#334155" stroke-width="12"/><path d="M230 210q-30-30 0-55-5 25 15 28 0-30 25-45-6 30 15 45 10-12 8-24 30 36 3 51" fill="#fed7aa" stroke="#ea580c" stroke-width="4"/>',
        "Perfil de aço",
        "Aquecimento",
    ),
    "fadiga_estrutural": (
        "Fadiga estrutural",
        '<path d="M70 195V45 M70 195H490" stroke="#334155" stroke-width="3"/><path d="M80 120 C105 40 125 40 150 120 S195 200 220 120 265 40 290 120 335 200 360 120 405 40 430 120 465 190 490 120" fill="none" stroke="#2563eb" stroke-width="5"/>',
        "Tensão",
        "Ciclos de carregamento",
    ),
    "ligacao_rigida": (
        "Ligação rígida viga–pilar",
        '<path d="M170 30V220 M210 30V220 M170 45H210 M170 205H210" stroke="#334155" stroke-width="7"/><path d="M210 85H470 M210 165H470 M210 125H470" stroke="#334155" stroke-width="7"/><path d="M220 75V175" stroke="#2563eb" stroke-width="8"/><g fill="#2563eb"><circle cx="235" cy="92" r="5"/><circle cx="235" cy="155" r="5"/></g>',
        "Pilar",
        "Viga e ligação",
    ),
    "monovia": (
        "Viga de monovia",
        '<path d="M70 55H490 M70 110H490 M280 55V110" stroke="#334155" stroke-width="8"/><circle cx="245" cy="122" r="12" fill="white" stroke="#2563eb" stroke-width="5"/><circle cx="315" cy="122" r="12" fill="white" stroke="#2563eb" stroke-width="5"/><path d="M230 138H330V155H230Z M280 155V195q0 18 18 18" fill="none" stroke="#2563eb" stroke-width="5"/>',
        "Viga",
        "Trole e talha",
    ),
    "nos_tubulares": (
        "Nó de treliça tubular",
        '<path d="M80 150H480V185H80Z" fill="#dbeafe" stroke="#334155" stroke-width="4"/><path d="M150 40L250 150 M410 40L310 150" stroke="#2563eb" stroke-width="22"/><path d="M150 40L250 150 M410 40L310 150" stroke="#dbeafe" stroke-width="13"/>',
        "Banzo",
        "Diagonais soldadas",
    ),
    "tercas": (
        "Terça em perfil U enrijecido",
        '<path d="M180 70V45H125V195H180V170" fill="none" stroke="#2563eb" stroke-width="7" stroke-linejoin="round"/><path d="M270 155L450 80 M280 175L460 100 M270 155V175 M450 80V100" fill="none" stroke="#334155" stroke-width="6"/>',
        "Seção U enrijecida",
        "Terça na cobertura",
    ),
    "viga_mista": (
        "Viga mista de aço e concreto",
        '<rect x="80" y="45" width="400" height="55" fill="#e2e8f0" stroke="#64748b" stroke-width="3"/><path d="M140 120H420 M140 205H420 M280 120V205" stroke="#334155" stroke-width="10"/><path d="M200 100V120 M280 100V120 M360 100V120" stroke="#2563eb" stroke-width="6"/>',
        "Laje de concreto",
        "Viga e conectores",
    ),
}


def mostrar_croqui_de_referencia(chave: str) -> None:
    """Exibe um esquema fixo, identificado como ilustração sem escala."""
    titulo, desenho, legenda1, legenda2 = _CROQUIS[chave]
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 260">'
        '<rect width="560" height="260" rx="12" fill="#f8fafc"/>'
        f"{desenho}"
        f'<text x="20" y="240" font-family="sans-serif" font-size="15" fill="#334155">{legenda1} · {legenda2}</text>'
        "</svg>"
    )
    mostrar_figura(svg, f"{titulo} — esquema ilustrativo, sem escala.", largura=560)
