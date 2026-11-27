"""Croquis conceituais de referência; não representam os dados do formulário."""

from components.figuras import mostrar_figura

# Elementos de desenho em coordenadas SVG. As legendas distinguem os componentes físicos.
_PERFIL = '<path d="M135 90h370v14H135z M135 196h370v14H135z" class="aco"/><path d="M145 104h350v92H145z" class="alma"/>'
_FLECHA = '<path d="M320 28v51" class="forca" marker-end="url(#seta)"/><text x="333" y="50" class="carga">F</text>'
_CROQUIS = {
    "aberturas_alma": (
        "Abertura na alma",
        _PERFIL
        + '<circle cx="320" cy="150" r="32" fill="white" stroke="#345b72" stroke-width="3"/><path d="M320 115v70 M285 150h70" class="eixo"/><path d="M360 150h80v-30" class="chamada"/><text x="445" y="119">abertura</text><text x="150" y="236">vista lateral da viga</text>',
    ),
    "forcas_localizadas": (
        "Força localizada na alma",
        _PERFIL
        + _FLECHA
        + '<path d="M280 83h80v7h-80z" fill="#bf8b43"/><path d="M380 150h70v-25" class="chamada"/><text x="454" y="124">alma</text><text x="150" y="236">força transmitida pela mesa</text>',
    ),
    "contencao_lateral": (
        "Contenção lateral",
        '<path d="M115 132h410v35H115z" class="alma"/><path d="M115 132h410 M115 167h410" class="linha"/><path d="M215 70v62 M425 70v62" class="azul"/><path d="M185 70h60 M395 70h60" class="linha"/><path d="M185 70l-10-12 M200 70l-10-12 M215 70l-10-12 M230 70l-10-12 M395 70l-10-12 M410 70l-10-12 M425 70l-10-12 M440 70l-10-12" class="fina"/><text x="153" y="51">travamento</text><text x="382" y="51">travamento</text><text x="260" y="200">barra comprimida</text><path d="M215 222h210" class="cota" marker-start="url(#seta)" marker-end="url(#seta)"/><text x="299" y="244">L<tspan baseline-shift="sub" font-size="12">b</tspan></text>',
    ),
    "nos_tubulares": (
        "Nó de treliça tubular",
        '<path d="M100 165h440v42H100z" class="alma"/><path d="M170 45l112 120h-32L146 55z M470 45L358 165h32L494 55z" class="alma"/><path d="M235 164h52 M353 164h52" stroke="#bb7834" stroke-width="5"/><path d="M335 188h100v35" class="chamada"/><text x="441" y="228">banzo</text><path d="M203 92H100v-30" class="chamada"/><text x="35" y="55">diagonal</text><text x="272" y="145" class="nota">soldas</text>',
    ),
    "monovia": (
        "Viga de monovia",
        '<path d="M100 55h440v12H100z M100 122h440v12H100z" class="aco"/><path d="M100 67h440v55H100z" class="alma"/><circle cx="280" cy="145" r="11" class="roda"/><circle cx="360" cy="145" r="11" class="roda"/><path d="M265 156h110v22H265z" class="aco"/><rect x="298" y="178" width="44" height="28" rx="4" class="alma"/><path d="M320 206v14q0 15 15 15q12 0 12-12" class="azul"/><path d="M405 165h80v24" class="chamada"/><text x="490" y="195">trole</text><text x="102" y="36">viga · vista lateral</text>',
    ),
    "tercas": (
        "Terça em perfil U enrijecido",
        '<path d="M235 78V55h-85v155h85v-23" fill="none" stroke="#345b72" stroke-width="7" stroke-linejoin="round"/><path d="M150 228h85 M150 219v17 M235 219v17 M118 55v155 M110 55h17 M110 210h17" class="cota"/><text x="184" y="249">b<tspan baseline-shift="sub" font-size="12">f</tspan></text><text x="91" y="138">b<tspan baseline-shift="sub" font-size="12">w</tspan></text><path d="M245 66h75v-20" class="chamada"/><text x="326" y="50">enrijecedor</text><text x="365" y="130">Seção Ue</text><text x="365" y="155" class="nota">perfil formado a frio</text>',
    ),
    "viga_mista": (
        "Viga mista de aço e concreto",
        '<rect x="90" y="60" width="460" height="54" class="concreto"/><path d="M145 124h350v12H145z M145 208h350v12H145z" class="aco"/><path d="M145 136h350v72H145z" class="alma"/><path d="M220 124V94 M320 124V94 M420 124V94" class="pino"/><path d="M212 94h16 M312 94h16 M412 94h16" class="pino"/><path d="M450 80h80v-36" class="chamada"/><text x="535" y="42">laje</text><path d="M322 106h95v-40" class="chamada"/><text x="422" y="64">conector</text><text x="150" y="243">viga de aço · vista lateral</text>',
    ),
    "ligacao_rigida": (
        "Ligação rígida viga–pilar",
        '<path d="M126 36h26v190h-26z M212 36h26v190h-26z M152 46h60v170h-60z" class="alma"/><path d="M252 92h280v14H252z M252 170h280v14H252z" class="aco"/><path d="M252 106h280v64H252z" class="alma"/><path d="M238 76h14v124h-14z" fill="#e6bf89" stroke="#8b5e2e" stroke-width="2"/><circle cx="270" cy="114" r="5" class="parafuso"/><circle cx="270" cy="161" r="5" class="parafuso"/><text x="135" y="250">pilar</text><text x="416" y="213">viga</text><path d="M248 80h75v-35" class="chamada"/><text x="329" y="48">chapa de extremidade</text>',
    ),
    "incendio": (
        "Estrutura em incêndio",
        '<path d="M220 55h200v18H220z M220 192h200v18H220z M310 73h20v119h-20z" class="aco"/><path d="M125 115h55 M125 145h55 M125 175h55 M515 115h-55 M515 145h-55 M515 175h-55" class="forca" marker-end="url(#seta)"/><text x="40" y="94" class="carga">calor</text><text x="515" y="94" class="carga">calor</text><text x="235" y="241">seção de aço exposta ao calor</text>',
    ),
    "fadiga_estrutural": (
        "Fadiga estrutural",
        '<path d="M95 205V45 M95 205h440" class="linha" marker-end="url(#seta)"/><path d="M100 125 C125 50 145 50 170 125 S215 200 240 125 285 50 310 125 355 200 380 125 425 50 450 125 495 200 520 125" fill="none" stroke="#2b6c8e" stroke-width="3"/><path d="M100 72h420 M100 178h420" class="eixo"/><path d="M548 72v106" class="cota" marker-start="url(#seta)" marker-end="url(#seta)"/><text x="555" y="129">Δσ</text><text x="48" y="55">tensão</text><text x="460" y="235">tempo</text><text x="115" y="64" class="nota">máxima</text><text x="115" y="194" class="nota">mínima</text>',
    ),
}


def mostrar_croqui_de_referencia(chave: str) -> None:
    """Mostra uma referência conceitual fixa, sem escala."""
    titulo, desenho = _CROQUIS[chave]
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 270">
    <defs><marker id="seta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#b75b34"/></marker></defs>
    <style>text{{font:16px Arial,sans-serif;fill:#314a59}} .nota{{font-size:13px;fill:#647b88}} .carga{{fill:#ad542f;font-weight:bold}} .aco{{fill:#647f90;stroke:#334e5e;stroke-width:2}} .alma{{fill:#d7e4e9;stroke:#476576;stroke-width:2}} .concreto{{fill:#e5e0d8;stroke:#8e8981;stroke-width:2}} .linha{{fill:none;stroke:#344e5e;stroke-width:2}} .fina,.chamada{{fill:none;stroke:#6c8591;stroke-width:1.5}} .azul{{fill:none;stroke:#2b6c8e;stroke-width:5}} .eixo{{fill:none;stroke:#96acb5;stroke-width:1;stroke-dasharray:7 5}} .forca{{fill:none;stroke:#b75b34;stroke-width:3}} .cota{{fill:none;stroke:#b75b34;stroke-width:1.5}} .pino{{fill:none;stroke:#a66d35;stroke-width:5}} .roda{{fill:#fff;stroke:#345b72;stroke-width:4}} .parafuso{{fill:#637f8d;stroke:#fff;stroke-width:1}}</style>
    <rect width="640" height="270" fill="#fff"/>{desenho}</svg>"""
    mostrar_figura(svg, f"{titulo} — esquema ilustrativo, sem escala.", largura=640)
