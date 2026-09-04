"""Calculo do diametro equivalente pelo metodo da area A0,95sigma.

As dimensoes de entrada sao em mm e as areas retornadas sao em mm².
As expressoes correspondem a secoes em flexao nao rotativa, exceto o
circulo rotativo, que e a referencia usada para definir o equivalente.
"""
import math

_AREA_REFERENCIA_CILINDRO_ROTATIVO = 0.0766


def _positivo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor <= 0:
        raise ValueError(f"{nome} deve ser finito e maior que zero.")
    return valor


def area_95_circulo_rotativo(d_mm: float) -> float:
    """Area acima de 95% da tensao em uma barra circular rotativa."""
    d_mm = _positivo("d_mm", d_mm)
    return _AREA_REFERENCIA_CILINDRO_ROTATIVO * d_mm**2


def diametro_equivalente_por_area_95(area_95_mm2: float) -> float:
    """Diametro da barra rotativa equivalente a uma area A0,95sigma."""
    area_95_mm2 = _positivo("area_95_mm2", area_95_mm2)
    return math.sqrt(area_95_mm2 / _AREA_REFERENCIA_CILINDRO_ROTATIVO)


def area_95_circulo_nao_rotativo(d_mm: float) -> float:
    """Area A0,95sigma de uma secao circular em flexao nao rotativa."""
    d_mm = _positivo("d_mm", d_mm)
    return 0.01046 * d_mm**2


def area_95_retangulo(h_mm: float, b_mm: float) -> float:
    """Area A0,95sigma de um retangulo de altura h e largura b."""
    return 0.05 * _positivo("h_mm", h_mm) * _positivo("b_mm", b_mm)


def area_95_perfil_i(a_mm: float, b_mm: float, tf_mm: float, eixo: str) -> float:
    """Area A0,95sigma de um perfil I; requer tf > 0,025 a."""
    a_mm = _positivo("a_mm", a_mm)
    b_mm = _positivo("b_mm", b_mm)
    tf_mm = _positivo("tf_mm", tf_mm)
    if tf_mm <= 0.025 * a_mm:
        raise ValueError("Para o perfil I, use tf > 0,025 a.")
    if eixo == "eixo 1-1":
        return 0.10 * a_mm * tf_mm
    if eixo == "eixo 2-2":
        return 0.05 * b_mm * a_mm
    raise ValueError("Eixo do perfil I deve ser 'eixo 1-1' ou 'eixo 2-2'.")


def area_95_perfil_canal(
    a_mm: float, b_mm: float, tf_mm: float, x_mm: float, eixo: str
) -> float:
    """Area A0,95sigma de um perfil canal conforme a orientacao do eixo."""
    a_mm = _positivo("a_mm", a_mm)
    b_mm = _positivo("b_mm", b_mm)
    tf_mm = _positivo("tf_mm", tf_mm)
    x_mm = float(x_mm)
    if not math.isfinite(x_mm) or x_mm < 0 or x_mm > b_mm:
        raise ValueError("Para o perfil canal, x deve estar entre 0 e b.")
    if eixo == "eixo 1-1":
        return 0.05 * a_mm * b_mm
    if eixo == "eixo 2-2":
        return 0.052 * x_mm * a_mm + 0.10 * tf_mm * (b_mm - x_mm)
    raise ValueError("Eixo do perfil canal deve ser 'eixo 1-1' ou 'eixo 2-2'.")


def desenho_svg(tipo: str) -> str:
    """Retorna um esquema SVG compacto das geometrias da tabela de Shigley."""
    inicio = '<svg xmlns="http://www.w3.org/2000/svg" width="360" height="220" viewBox="0 0 360 220"><style>text{font-family:Arial,sans-serif;fill:#263238;font-size:15px}.l{stroke:#334e5c;stroke-width:3;fill:none}.a{stroke:#e05a47;stroke-width:2;fill:none;stroke-dasharray:5 4}.f{fill:#dbe9ef;stroke:#334e5c;stroke-width:3}</style>'
    fim = '</svg>'
    if tipo == "Circulo rotativo":
        corpo = '<circle class="f" cx="155" cy="105" r="67"/><line class="a" x1="88" y1="105" x2="222" y2="105"/><text x="148" y="96">d</text><text x="58" y="200">barra circular em flexao rotativa</text>'
    elif tipo == "Circulo nao rotativo":
        corpo = '<circle class="f" cx="155" cy="105" r="67"/><line class="a" x1="91" y1="105" x2="219" y2="105"/><line class="a" x1="123" y1="46" x2="123" y2="164"/><line class="a" x1="187" y1="46" x2="187" y2="164"/><text x="148" y="96">d</text><text x="72" y="200">faixa A0,95sigma em flexao nao rotativa</text>'
    elif tipo == "Retangulo":
        corpo = '<rect class="f" x="95" y="42" width="150" height="125"/><line class="a" x1="95" y1="28" x2="245" y2="28"/><text x="166" y="22">b</text><line class="a" x1="266" y1="42" x2="266" y2="167"/><text x="274" y="108">h</text><text x="106" y="200">secao retangular</text>'
    elif tipo == "Perfil I":
        corpo = '<path class="f" d="M75 42H245V69H180V141H245V168H75V141H140V69H75Z"/><line class="a" x1="75" y1="28" x2="245" y2="28"/><text x="157" y="22">a</text><line class="a" x1="267" y1="42" x2="267" y2="168"/><text x="275" y="110">b</text><line class="a" x1="54" y1="42" x2="54" y2="69"/><text x="27" y="60">tf</text><text x="128" y="200">perfil I</text>'
    elif tipo == "Perfil canal":
        corpo = '<path class="f" d="M85 42H235V68H118V142H235V168H85Z"/><line class="a" x1="85" y1="28" x2="235" y2="28"/><text x="156" y="22">a</text><line class="a" x1="257" y1="42" x2="257" y2="168"/><text x="266" y="110">b</text><line class="a" x1="64" y1="42" x2="64" y2="68"/><text x="35" y="60">tf</text><line class="a" x1="118" y1="181" x2="235" y2="181"/><text x="172" y="198">x</text><text x="128" y="215">perfil canal</text>'
    else:
        corpo = '<rect class="f" x="88" y="55" width="160" height="95" rx="8"/><text x="128" y="107">A0,95sigma</text><text x="83" y="190">area informada manualmente</text>'
    return inicio + corpo + fim