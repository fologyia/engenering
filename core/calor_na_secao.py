"""Calor no tempo na seção desenhada (duas dimensões): uma barra comprida, de seção constante.

A seção vem das partes do "Desenhar seção" (:mod:`core.secao_desenhada`, medidas em mm). Começa a
uma temperatura só e, no instante zero, o contorno de fora e o contorno dos furos passam a ter cada
um a sua condição: convecção (h, T∞), temperatura fixa, fluxo de calor que entra ou isolado.

Método: volumes finitos numa grade de células (célula com metade ou mais de material conta como
material). As faces das células que dão para fora formam degraus; num contorno curvo ou inclinado os
degraus somam mais que o contorno de verdade (no círculo, 4/π vezes): cada face de degrau é reduzida
por 1/(|n_x| + |n_y|), com a normal tirada da fração de material das células, e a área total e a
massa ficam as da seção de verdade. No tempo, Crank–Nicolson com partida implícita, como na conta de
uma dimensão (:mod:`core.calor_no_tempo`).

Conferência (nos testes): retângulo com convecção em volta = produto das soluções exatas das duas
paredes (Incropera, seção 5.8); círculo com Bi pequeno = capacitância concentrada; tubo em regime
permanente = resistências em série.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
from scipy import sparse
from scipy.sparse import linalg as splinalg

from core import secao_desenhada as sd
from core.calor_no_tempo import (
    CONDICOES,
    CONVECCAO,
    ESTABILIZADO,
    FLUXO,
    ISOLADA,
    TEMPERATURA,
    ErroDoCalor,
    Face,
    Marcos,
    Material,
    marcos_da_serie,
    primeiro_cruzamento,
)

#: Células com material, no máximo. A conta fica em poucos segundos e a animação, leve.
LIMITE_DE_CELULAS = 9000
QUADROS = 121
PASSOS = 600  # múltiplo de QUADROS − 1


@dataclass(frozen=True)
class GradeDaSecao:
    xs: np.ndarray  # linhas da grade, mm
    ys: np.ndarray
    ativa: np.ndarray  # (nx, ny): célula com material
    fracao: np.ndarray  # (nx, ny): fração de material de cada célula
    area_mm2: float  # área de verdade (pela fração)
    contorno_fora_mm: float  # comprimento de verdade (degraus corrigidos)
    contorno_furos_mm: float
    # faces de contorno: célula (índice na lista de ativas), comprimento corrigido (mm),
    # distância do centro da célula à face (mm) e se dá para um furo
    face_celula: np.ndarray
    face_comprimento: np.ndarray
    face_distancia: np.ndarray
    face_furo: np.ndarray

    @property
    def indices_ativos(self) -> np.ndarray:
        """Índice i·ny + j de cada célula com material, na ordem das incógnitas."""
        i, j = np.nonzero(self.ativa)
        return i * self.ativa.shape[1] + j

    @property
    def tem_furo(self) -> bool:
        return bool(np.any(self.face_furo))


def _cortes(partes: Sequence[sd.Parte], caixa: tuple[float, float, float, float]):  # noqa: ANN202
    x0, y0, x1, y1 = caixa
    cortes_x, cortes_y = {x0, x1}, {y0, y1}
    for parte in partes:
        a, b, c, d = parte.caixa()
        for valor, conjunto, (lo, hi) in (
            (a, cortes_x, (x0, x1)),
            (c, cortes_x, (x0, x1)),
            (b, cortes_y, (y0, y1)),
            (d, cortes_y, (y0, y1)),
        ):
            if lo < valor < hi:
                conjunto.add(valor)
        if parte.forma == sd.POLI:
            for px, py in parte.pontos:
                if x0 < px < x1:
                    cortes_x.add(px)
                if y0 < py < y1:
                    cortes_y.add(py)
    return cortes_x, cortes_y


def _grade(partes: Sequence[sd.Parte], passo: float, tamanho: float, caixa):  # noqa: ANN001, ANN202
    cortes_x, cortes_y = _cortes(partes, caixa)
    xs = sd._linhas(cortes_x, passo, 2, tamanho)
    ys = sd._linhas(cortes_y, passo, 2, tamanho)
    fracao = sd._ocupacao(partes, xs, ys, 4).mean(axis=(2, 3))
    return xs, ys, fracao


def _regioes_vazias(ativa: np.ndarray) -> np.ndarray:
    """0 = material, 1 = fora, 2 = furo (vazio cercado de material)."""
    nx, ny = ativa.shape
    rotulo = np.where(ativa, 0, 2).astype(np.int8)
    pilha = [(i, j) for i in range(nx) for j in (0, ny - 1) if not ativa[i, j]]
    pilha += [(i, j) for j in range(ny) for i in (0, nx - 1) if not ativa[i, j]]
    for i, j in pilha:
        rotulo[i, j] = 1
    while pilha:
        i, j = pilha.pop()
        for k, m in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if 0 <= k < nx and 0 <= m < ny and rotulo[k, m] == 2:
                rotulo[k, m] = 1
                pilha.append((k, m))
    return rotulo


def _material_em(partes: Sequence[sd.Parte], x: np.ndarray, y: np.ndarray) -> np.ndarray:
    dentro = np.zeros(np.broadcast(x, y).shape, dtype=bool)
    for parte in partes:
        if not parte.furo:
            dentro |= parte.contem(x, y)
    for parte in partes:
        if parte.furo:
            dentro &= ~parte.contem(x, y)
    return dentro


def _amostras_da_borda(parte: sd.Parte, passo: float) -> tuple[np.ndarray, ...]:
    """Pontos do contorno de uma parte curva ou inclinada: posição, normal para o lado vazio e
    o comprimento que cada ponto representa."""
    if parte.forma == sd.CIRC:
        raio = parte.b / 2.0
        quantos = max(96, math.ceil(2.0 * math.pi * raio / passo * 8))
        angulo = (np.arange(quantos) + 0.5) * 2.0 * math.pi / quantos
        nx, ny = np.cos(angulo), np.sin(angulo)
        mx, my = parte.x + raio * nx, parte.y + raio * ny
        ds = np.full(quantos, 2.0 * math.pi * raio / quantos)
    else:
        cantos = np.array(parte.cantos, dtype=float)
        x, y = cantos[:, 0], cantos[:, 1]
        if 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)) < 0:
            cantos = cantos[::-1]  # anti-horário: a normal de fora fica à direita do caminho
        pedacos = []
        for a, b in zip(cantos, np.roll(cantos, -1, axis=0), strict=True):
            comprimento = float(np.hypot(*(b - a)))
            if comprimento <= 0:
                continue
            quantos = max(4, math.ceil(comprimento / passo * 8))
            t = (np.arange(quantos) + 0.5) / quantos
            d = (b - a) / comprimento
            pedacos.append(
                (
                    a[0] + t * (b[0] - a[0]),
                    a[1] + t * (b[1] - a[1]),
                    np.full(quantos, d[1]),
                    np.full(quantos, -d[0]),
                    np.full(quantos, comprimento / quantos),
                )
            )
        mx, my, nx, ny, ds = (np.concatenate(c) for c in zip(*pedacos, strict=True))
    if parte.furo:
        nx, ny = -nx, -ny  # num furo, o lado vazio é o de dentro
    return mx, my, nx, ny, ds


def _bordas_retas(partes: Sequence[sd.Parte]) -> list[tuple[int, float, float, float]]:
    """Arestas das partes alinhadas com os eixos: (eixo da normal, posição, início, fim).

    Essas arestas caem em linhas da grade, e as faces das células sobre elas são exatas."""
    arestas: list[tuple[int, float, float, float]] = []
    for parte in partes:
        if parte.forma == sd.CIRC or not parte.reta:
            continue
        cantos = parte.cantos
        for a, b in zip(cantos, [*cantos[1:], cantos[0]], strict=True):
            if abs(a[0] - b[0]) < 1e-9:
                arestas.append((0, a[0], min(a[1], b[1]), max(a[1], b[1])))
            elif abs(a[1] - b[1]) < 1e-9:
                arestas.append((1, a[1], min(a[0], b[0]), max(a[0], b[0])))
    return arestas


def montar_grade(partes: Sequence[sd.Parte], *, limite: int = LIMITE_DE_CELULAS) -> GradeDaSecao:
    cheias = [p for p in partes if not p.furo]
    if not cheias:
        raise ErroDoCalor("Desenhe ao menos uma parte cheia: só furo não forma uma seção.")
    caixa = sd.caixa_das_partes(cheias)
    x0, y0, x1, y1 = caixa
    tamanho = max(x1 - x0, y1 - y0)
    if not tamanho > 0:
        raise ErroDoCalor("A seção não tem tamanho: confira as medidas.")
    passo = tamanho / 60.0
    xs, ys, fracao = _grade(partes, passo, tamanho, caixa)
    area = float((fracao * np.outer(np.diff(xs), np.diff(ys))).sum())
    if area <= 0:
        raise ErroDoCalor("Os furos tiraram toda a seção.")
    # parede fina pede célula menor: ao menos 3 células na espessura média (2·A/perímetro)
    ativa = fracao >= 0.5
    degraus = (
        np.abs(np.diff(np.pad(ativa, 1).astype(int), axis=0)).sum()
        + np.abs(np.diff(np.pad(ativa, 1).astype(int), axis=1)).sum()
    )
    espessura = 2.0 * area / max(float(degraus) * passo * math.pi / 4.0, 1e-12)
    if espessura / 3.0 < passo:
        for _ in range(8):
            novo = min(passo, max(espessura / 3.0, tamanho / 260.0))
            xs, ys, fracao = _grade(partes, novo, tamanho, caixa)
            if int((fracao >= 0.5).sum()) <= limite:
                break
            espessura *= 1.25  # grade grande demais: células um pouco maiores
    ativa = fracao >= 0.5
    if int(ativa.sum()) > limite:
        fator = math.sqrt(ativa.sum() / limite)
        xs, ys, fracao = _grade(partes, tamanho / 60.0 * fator, tamanho, caixa)
        ativa = fracao >= 0.5
    if not ativa.any():
        raise ErroDoCalor("A seção é fina demais para a grade: aumente as espessuras.")
    return _faces(partes, xs, ys, ativa, fracao)


def _faces(
    partes: Sequence[sd.Parte],
    xs: np.ndarray,
    ys: np.ndarray,
    ativa: np.ndarray,
    fracao: np.ndarray,
) -> GradeDaSecao:
    nx, ny = ativa.shape
    dx, dy = np.diff(xs), np.diff(ys)
    rotulo = _regioes_vazias(ativa)
    numero = -np.ones((nx, ny), dtype=np.int64)
    numero[ativa] = np.arange(int(ativa.sum()))
    cx = (xs[:-1] + xs[1:]) / 2.0
    cy = (ys[:-1] + ys[1:]) / 2.0
    gx = np.gradient(fracao, cx, axis=0) if nx > 1 else np.zeros_like(fracao)
    gy = np.gradient(fracao, cy, axis=1) if ny > 1 else np.zeros_like(fracao)
    tamanho = max(xs[-1] - xs[0], ys[-1] - ys[0])
    tol = tamanho * 1e-7
    retas = _bordas_retas(partes)

    celulas, comprimentos, distancias, furos, exatas = [], [], [], [], []
    for eixo in (0, 1):
        for sentido in (-1, 1):
            ii = np.broadcast_to(np.arange(nx)[:, None] + (sentido if eixo == 0 else 0), (nx, ny))
            jj = np.broadcast_to(np.arange(ny)[None, :] + (sentido if eixo == 1 else 0), (nx, ny))
            fora_da_grade = (ii < 0) | (ii >= nx) | (jj < 0) | (jj >= ny)
            vi, vj = np.clip(ii, 0, nx - 1), np.clip(jj, 0, ny - 1)
            exposta = ativa & (fora_da_grade | ~ativa[vi, vj])
            i, j = np.nonzero(exposta)
            if not len(i):
                continue
            dentro = ~fora_da_grade[i, j]
            ni, nj = vi[i, j], vj[i, j]
            if eixo == 0:
                posicao = xs[i + (1 if sentido > 0 else 0)]
                inicio, fim, lado, normal = ys[j], ys[j + 1], dy[j], dx[i]
            else:
                posicao = ys[j + (1 if sentido > 0 else 0)]
                inicio, fim, lado, normal = xs[i], xs[i + 1], dx[i], dy[j]
            exata = np.zeros(len(i), dtype=bool)
            for eixo_a, pos_a, ini_a, fim_a in retas:
                if eixo_a == eixo:
                    exata |= (
                        (np.abs(posicao - pos_a) < tol)
                        & (inicio >= ini_a - tol)
                        & (fim <= fim_a + tol)
                    )
            # normal na face: média dos gradientes da fração dos dois lados
            gxf = gx[i, j] + np.where(dentro, gx[ni, nj], 0.0)
            gyf = gy[i, j] + np.where(dentro, gy[ni, nj], 0.0)
            soma = np.abs(gxf) + np.abs(gyf)
            fator = np.where(
                ~exata & (soma > 0), np.hypot(gxf, gyf) / np.maximum(soma, 1e-300), 1.0
            )
            celulas.append(numero[i, j])
            comprimentos.append(lado * fator)
            distancias.append(normal / 2.0)
            furos.append(dentro & (rotulo[ni, nj] == 2))
            exatas.append(exata)
    face_celula = np.concatenate(celulas)
    face_comp = np.concatenate(comprimentos)
    face_dist = np.concatenate(distancias)
    face_furo = np.concatenate(furos)
    face_exata = np.concatenate(exatas)

    # Comprimento de verdade das bordas curvas ou inclinadas, pelos pontos do contorno de cada
    # parte que separam material de vazio; o lado vazio diz se é o contorno de fora ou de um furo.
    passo = float(min(dx.min(), dy.min()))
    eps = tamanho * 1e-6
    curvo = {False: 0.0, True: 0.0}
    for parte in partes:
        if parte.forma != sd.CIRC and parte.reta:
            continue
        mx, my, nxs, nys, ds = _amostras_da_borda(parte, passo)
        cheio = _material_em(partes, mx - eps * nxs, my - eps * nys)
        vazio = ~_material_em(partes, mx + eps * nxs, my + eps * nys)
        borda = cheio & vazio
        if not borda.any():
            continue
        qx = mx[borda] + eps * nxs[borda]
        qy = my[borda] + eps * nys[borda]
        ci = np.clip(np.searchsorted(xs, qx) - 1, 0, nx - 1)
        cj = np.clip(np.searchsorted(ys, qy) - 1, 0, ny - 1)
        fora = (qx < xs[0]) | (qx > xs[-1]) | (qy < ys[0]) | (qy > ys[-1])
        regiao = _regiao_vizinha(rotulo, ci, cj, nxs[borda], nys[borda])
        no_furo = ~fora & (regiao == 2)
        curvo[True] += float(ds[borda][no_furo].sum())
        curvo[False] += float(ds[borda][~no_furo].sum())
    for furo in (False, True):
        mascara = (face_furo == furo) & ~face_exata
        total = float(face_comp[mascara].sum())
        if total > 0 and curvo[furo] > 0:
            face_comp = np.where(mascara, face_comp * (curvo[furo] / total), face_comp)
    area = float((fracao * np.outer(dx, dy)).sum())
    return GradeDaSecao(
        xs=xs,
        ys=ys,
        ativa=ativa,
        fracao=fracao,
        area_mm2=area,
        contorno_fora_mm=float(face_comp[~face_furo].sum()),
        contorno_furos_mm=float(face_comp[face_furo].sum()),
        face_celula=face_celula,
        face_comprimento=face_comp,
        face_distancia=face_dist,
        face_furo=face_furo,
    )


def _regiao_vizinha(
    rotulo: np.ndarray, ci: np.ndarray, cj: np.ndarray, nx: np.ndarray, ny: np.ndarray
) -> np.ndarray:
    """Região vazia (1 fora, 2 furo) da célula do ponto; se a célula conta como material, a da
    vizinha na direção da normal."""
    n_x, n_y = rotulo.shape
    regiao = rotulo[ci, cj].astype(int)
    passo_i = np.where(np.abs(nx) >= np.abs(ny), np.sign(nx), 0).astype(int)
    passo_j = np.where(np.abs(nx) < np.abs(ny), np.sign(ny), 0).astype(int)
    for _ in range(3):
        falta = regiao == 0
        if not falta.any():
            break
        ci = np.where(falta, np.clip(ci + passo_i, 0, n_x - 1), ci)
        cj = np.where(falta, np.clip(cj + passo_j, 0, n_y - 1), cj)
        regiao = np.where(falta, rotulo[ci, cj], regiao)
    return np.where(regiao == 0, 1, regiao)


# ---------------------------------------------------------------------------------------------
# Conta
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ResultadoDaSecao:
    grade: GradeDaSecao
    material: Material
    t_inicial: float
    fora: Face
    furos: Face
    tempos: np.ndarray  # todos os passos, s
    maxima: np.ndarray  # por passo, °C
    minima: np.ndarray
    media: np.ndarray  # média pela massa
    tempos_dos_quadros: np.ndarray
    quadros: np.ndarray  # quadros × células ativas, °C
    permanente: np.ndarray | None
    tau: float | None
    duracao: float
    automatica: bool
    avisos: tuple[str, ...] = field(default_factory=tuple)
    desvio: np.ndarray | None = None  # por passo: maior distância de uma célula ao regime (°C)
    calor_fora: np.ndarray | None = None  # por passo: calor que entra pelo contorno de fora (W/m)
    calor_furos: np.ndarray | None = None  # por passo: calor que entra pelos furos (W/m)

    def tempo_para(self, qual: str, alvo: float) -> float | None:
        serie = {"max": self.maxima, "min": self.minima, "media": self.media}[qual]
        return primeiro_cruzamento(self.tempos, serie, alvo)


def problemas(material: Material, fora: Face, furos: Face, grade: GradeDaSecao | None) -> list[str]:
    erros: list[str] = []
    for valor, rotulo in (
        (material.condutividade, "a condutividade k"),
        (material.massa_especifica, "a massa específica ρ"),
        (material.calor_especifico, "o calor específico c_p"),
    ):
        if not (math.isfinite(valor) and valor > 0):
            erros.append(f"Informe {rotulo} do material, maior que zero.")
    faces = [("contorno de fora", fora)]
    if grade is not None and grade.tem_furo:
        faces.append(("contorno dos furos", furos))
    for nome, face in faces:
        if face.tipo not in CONDICOES:
            erros.append(f"Escolha o que acontece no {nome}.")
        elif face.tipo == CONVECCAO and not face.h > 0:
            erros.append(f"No {nome}, informe o coeficiente h, maior que zero.")
    return erros


def calcular(
    partes: Sequence[sd.Parte],
    material: Material,
    t_inicial: float,
    fora: Face,
    furos: Face = Face(ISOLADA),
    duracao: float | None = None,
    *,
    grade: GradeDaSecao | None = None,
    passos: int = PASSOS,
    quadros: int = QUADROS,
) -> ResultadoDaSecao:
    g = grade if grade is not None else montar_grade(partes)
    erros = problemas(material, fora, furos, g)
    if erros:
        raise ErroDoCalor(" ".join(erros))
    n = int(g.ativa.sum())
    dx, dy = np.diff(g.xs) / 1000.0, np.diff(g.ys) / 1000.0
    i, j = np.nonzero(g.ativa)
    area_celula = dx[i] * dy[j]
    # massa da seção de verdade: as células com material carregam a área medida pela fração
    area_celula *= (g.area_mm2 / 1e6) / area_celula.sum()
    capacidade = material.massa_especifica * material.calor_especifico * area_celula  # J/(K·m)
    k = material.condutividade
    numero = -np.ones(g.ativa.shape, dtype=np.int64)
    numero[g.ativa] = np.arange(n)
    linhas, colunas, valores = [], [], []
    for eixo in (0, 1):
        a = g.ativa[:-1, :] & g.ativa[1:, :] if eixo == 0 else g.ativa[:, :-1] & g.ativa[:, 1:]
        ia, ja = np.nonzero(a)
        ib, jb = (ia + 1, ja) if eixo == 0 else (ia, ja + 1)
        if eixo == 0:
            distancia = (dx[ia] + dx[ib]) / 2.0
            lado = dy[ja]
        else:
            distancia = (dy[ja] + dy[jb]) / 2.0
            lado = dx[ia]
        cond = k * lado / distancia  # W/(K·m)
        na, nb = numero[ia, ja], numero[ib, jb]
        linhas += [na, nb, na, nb]
        colunas += [nb, na, na, nb]
        valores += [-cond, -cond, cond, cond]
    diagonal_extra = np.zeros(n)
    fonte = np.zeros(n)
    # o que cada contorno troca: células, condutância e temperatura de fora, mais o fluxo fixo
    trocas: list[tuple[np.ndarray, np.ndarray, float, float]] = []
    for face, mascara in ((fora, ~g.face_furo), (furos, g.face_furo)):
        cel = g.face_celula[mascara]
        comp = g.face_comprimento[mascara] / 1000.0
        dist = g.face_distancia[mascara] / 1000.0
        cond = np.zeros(len(cel))
        referencia = 0.0
        fluxo = 0.0
        if face.tipo == CONVECCAO and mascara.any():
            cond = comp / (dist / k + 1.0 / face.h)
            referencia = face.t_fluido
        elif face.tipo == TEMPERATURA and mascara.any():
            cond = comp * k / dist
            referencia = face.t_fixa
        elif face.tipo == FLUXO and mascara.any():
            fluxo = float(face.fluxo * comp.sum())
            np.add.at(fonte, cel, face.fluxo * comp)
        if cond.any():
            np.add.at(diagonal_extra, cel, cond)
            np.add.at(fonte, cel, cond * referencia)
        trocas.append((cel, cond, referencia, fluxo))
    rigidez = sparse.coo_matrix(
        (np.concatenate(valores), (np.concatenate(linhas), np.concatenate(colunas))), shape=(n, n)
    ).tocsc() + sparse.diags(diagonal_extra, format="csc")
    estabiliza = bool(np.any(diagonal_extra > 0))
    permanente = splinalg.spsolve(rigidez, fonte) if estabiliza else None
    tau = None
    if estabiliza:
        massa = sparse.diags(capacidade, format="csc")
        try:
            menor = splinalg.eigsh(
                rigidez, k=1, M=massa, sigma=0, which="LM", return_eigenvectors=False
            )
            tau = 1.0 / float(menor[0]) if menor[0] > 0 else None
        except (splinalg.ArpackNoConvergence, RuntimeError):
            tau = None
    avisos: list[str] = []
    automatica = duracao is None
    if duracao is None:
        if tau is not None:
            duracao = math.log(1.0 / (1.0 - ESTABILIZADO)) * tau
        else:
            espessura = (
                2.0 * g.area_mm2 / max(g.contorno_fora_mm + g.contorno_furos_mm, 1e-9) / 1000.0
            )
            duracao = 2.0 * espessura**2 / material.difusividade
            avisos.append(
                "Sem convecção nem temperatura fixa em nenhum contorno, a seção não chega a um "
                "regime permanente. A duração mostrada é a de 2·e²/α, com e = 2·A/perímetro."
            )
    if not (math.isfinite(duracao) and duracao > 0):
        raise ErroDoCalor("Informe uma duração maior que zero.")
    passo_quadro = max(1, passos // (quadros - 1))
    passos = passo_quadro * (quadros - 1)
    dt = duracao / passos
    matriz_c = sparse.diags(capacidade / dt, format="csc")
    implicito = splinalg.splu((matriz_c + rigidez).tocsc())
    crank = splinalg.splu((matriz_c + 0.5 * rigidez).tocsc())
    t = np.full(n, float(t_inicial))
    peso = capacidade / capacidade.sum()
    maxima, minima, media = np.empty(passos + 1), np.empty(passos + 1), np.empty(passos + 1)
    desvio = np.empty(passos + 1)
    calores = np.empty((2, passos + 1))
    guardados = np.empty((quadros, n))
    maxima[0] = minima[0] = media[0] = t_inicial

    def anotar(i: int, atual: np.ndarray) -> None:
        if permanente is not None:
            desvio[i] = float(np.max(np.abs(atual - permanente)))
        for lado, (cel, cond, referencia, fluxo) in enumerate(trocas):
            calores[lado, i] = float(cond @ (referencia - atual[cel])) + fluxo

    anotar(0, t)
    guardados[0] = t
    for passo in range(1, passos + 1):
        if passo <= 4:
            t = implicito.solve(capacidade / dt * t + fonte)
        else:
            t = crank.solve(capacidade / dt * t - 0.5 * (rigidez @ t) + fonte)
        maxima[passo], minima[passo] = float(t.max()), float(t.min())
        media[passo] = float(peso @ t)
        anotar(passo, t)
        if passo % passo_quadro == 0:
            guardados[passo // passo_quadro] = t
    if not np.all(np.isfinite(guardados)):
        raise ErroDoCalor("A conta deu um valor que não é número: confira os dados.")
    tempos = np.linspace(0.0, duracao, passos + 1)
    return ResultadoDaSecao(
        grade=g,
        material=material,
        t_inicial=float(t_inicial),
        fora=fora,
        furos=furos,
        tempos=tempos,
        maxima=maxima,
        minima=minima,
        media=media,
        tempos_dos_quadros=tempos[::passo_quadro],
        quadros=guardados,
        permanente=permanente,
        tau=tau,
        duracao=float(duracao),
        automatica=automatica,
        avisos=tuple(avisos),
        desvio=desvio if permanente is not None else None,
        calor_fora=calores[0],
        calor_furos=calores[1],
    )


def marcos(r: ResultadoDaSecao) -> Marcos:
    """Estabiliza, equaliza e a maior diferença dentro da seção (como na conta de uma dimensão)."""
    final = r.quadros[-1]
    return marcos_da_serie(r.tempos, r.maxima, r.minima, r.desvio, r.permanente, r.t_inicial, final)


def hipoteses(r: ResultadoDaSecao) -> list[str]:
    g = r.grade
    return [
        "Barra comprida de seção constante: o calor corre só no plano da seção, sem perda pelas "
        "pontas.",
        "Propriedades do material constantes, sem geração de calor dentro e sem mudança de fase; a "
        "seção começa toda a uma temperatura só e as condições dos contornos mudam no instante "
        "zero e ficam constantes depois.",
        f"Volumes finitos numa grade de {int(g.ativa.sum())} células; contorno em degraus de "
        "célula, com cada degrau reduzido pela inclinação do contorno de verdade (área e "
        "perímetro da seção conservados).",
        "Convecção com h constante: o h vem de tabela ou de correlação feita fora desta conta.",
    ]
