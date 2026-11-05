// Geometria das partes da seção, sem tela: tests/test_editor_numerico_js.py roda tudo no Node.
// Mudar uma medida digitada mantém a seção inteira: quem está encostado continua encostado.

const TOLERANCIA = 1e-6

function cantos(p) {
  if (p.forma === "poli") return p.pontos
  const a = ((p.giro || 0) * Math.PI) / 180
  const c = Math.cos(a)
  const s = Math.sin(a)
  return [
    [-p.b / 2, -p.h / 2],
    [p.b / 2, -p.h / 2],
    [p.b / 2, p.h / 2],
    [-p.b / 2, p.h / 2],
  ].map(([dx, dy]) => [p.x + dx * c - dy * s, p.y + dx * s + dy * c])
}

function caixa(p) {
  if (p.forma === "circ") return [p.x - p.b / 2, p.y - p.b / 2, p.x + p.b / 2, p.y + p.b / 2]
  const lista = cantos(p)
  const xs = lista.map((v) => v[0])
  const ys = lista.map((v) => v[1])
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]
}

function caixaDe(partes) {
  const c = partes.map(caixa)
  return [
    Math.min(...c.map((v) => v[0])),
    Math.min(...c.map((v) => v[1])),
    Math.max(...c.map((v) => v[2])),
    Math.max(...c.map((v) => v[3])),
  ]
}

function mover(p, dx, dy) {
  p.x += dx
  p.y += dy
  if (p.forma === "poli") p.pontos = p.pontos.map(([x, y]) => [x + dx, y + dy])
}

const chapaReta = (p) => p.forma === "ret" && !p.giro && !p.furo

// Índices das colunas de caixa(): ao longo da medida e na direção transversal.
const EIXOS = {
  b: { ini: 0, fim: 2, lado0: 1, lado1: 3, passo: (d) => [d, 0] },
  h: { ini: 1, fim: 3, lado0: 0, lado1: 2, passo: (d) => [0, d] },
}

function seCobrem(a, b, e) {
  return Math.min(a[e.lado1], b[e.lado1]) - Math.max(a[e.lado0], b[e.lado0]) > TOLERANCIA
}

// Quem encosta na borda de `inicio`, e quem encosta nesses, seguindo a mesma direção.
function encostadas(partes, caixas, inicio, e, paraFrente) {
  const achadas = new Set()
  const fila = [inicio]
  while (fila.length) {
    const k = fila.pop()
    const borda = caixas[k][paraFrente ? e.fim : e.ini]
    partes.forEach((p, j) => {
      if (j === inicio || achadas.has(j) || !chapaReta(p)) return
      const face = caixas[j][paraFrente ? e.ini : e.fim]
      if (Math.abs(face - borda) < TOLERANCIA && seCobrem(caixas[k], caixas[j], e)) {
        achadas.add(j)
        fila.push(j)
      }
    })
  }
  return achadas
}

// Furo e círculo dentro de uma chapa que andou vão junto com ela.
function moverOQueEstaDentro(partes, caixas, andou, dx, dy) {
  partes.forEach((p, j) => {
    if (chapaReta(p) || andou.has(j)) return
    const [x, y] = [(caixas[j][0] + caixas[j][2]) / 2, (caixas[j][1] + caixas[j][3]) / 2]
    const dentro = [...andou].some((k) => {
      const c = caixas[k]
      return x > c[0] && x < c[2] && y > c[1] && y < c[3]
    })
    if (dentro) mover(p, dx, dy)
  })
}

// Altura: a base fica, o topo sobe e leva quem está em cima. Largura: cresce do centro, para não
// tirar a seção de simetria, e empurra quem está dos lados. A irmã (a outra alma de um caixão)
// acompanha quando ficaria solta da peça que andou.
function dimensionarParte(partes, i, eixo, novo) {
  const p = partes[i]
  if (!(novo > 0)) return
  if (p.forma === "circ") {
    p.b = novo
    p.h = novo
    return
  }
  if (p.forma !== "ret" || p.giro || p.furo) {
    p[eixo] = novo
    return
  }
  const caixas = partes.map(caixa)
  const e = EIXOS[eixo]
  const delta = novo - p[eixo]
  const altura = eixo === "h"
  const adiante = encostadas(partes, caixas, i, e, true)
  const atras = altura ? new Set() : encostadas(partes, caixas, i, e, false)
  const [frente, tras] = altura ? [delta, 0] : [delta / 2, -delta / 2]

  const irmas = []
  partes.forEach((q, j) => {
    if (j === i || adiante.has(j) || atras.has(j) || !chapaReta(q)) return
    const mesma =
      Math.abs(caixas[j][e.ini] - caixas[i][e.ini]) < TOLERANCIA &&
      Math.abs(caixas[j][e.fim] - caixas[i][e.fim]) < TOLERANCIA
    if (!mesma) return
    const toca = [...adiante].some(
      (k) =>
        Math.abs(caixas[k][e.ini] - caixas[j][e.fim]) < TOLERANCIA &&
        seCobrem(caixas[k], caixas[j], e),
    )
    if (toca) irmas.push(j)
  })

  const crescer = (q) => {
    q[eixo] = novo
    if (altura) mover(q, 0, delta / 2)
  }
  crescer(p)
  irmas.forEach((j) => crescer(partes[j]))
  adiante.forEach((j) => mover(partes[j], ...e.passo(frente)))
  atras.forEach((j) => mover(partes[j], ...e.passo(tras)))
  moverOQueEstaDentro(partes, caixas, adiante, ...e.passo(frente))
  moverOQueEstaDentro(partes, caixas, atras, ...e.passo(tras))
}

// Largura ou altura total. Cresce quem vai de ponta a ponta (as mesas de um I); sem ninguém assim,
// quem cruza o meio (a alma). Os outros andam para fora e continuam encostados. Sem chapa nenhuma
// para crescer, como num tubo redondo, a seção inteira muda de escala.
function esticarConjunto(partes, eixo, novo) {
  if (!partes.length || !(novo > 0)) return
  const e = EIXOS[eixo]
  const c = caixaDe(partes)
  const [lo, hi] = [c[e.ini], c[e.fim]]
  const total = hi - lo
  if (total <= 0) return
  const delta = novo - total
  const meio = (lo + hi) / 2
  const caixas = partes.map(caixa)
  const retas = partes.map((p, j) => (chapaReta(p) ? j : -1)).filter((j) => j >= 0)
  const inteiras = retas.filter(
    (j) =>
      Math.abs(caixas[j][e.ini] - lo) < TOLERANCIA && Math.abs(caixas[j][e.fim] - hi) < TOLERANCIA,
  )
  const noMeio = retas.filter(
    (j) => caixas[j][e.ini] < meio - TOLERANCIA && caixas[j][e.fim] > meio + TOLERANCIA,
  )
  const crescem = new Set(inteiras.length ? inteiras : noMeio)
  if (!crescem.size) {
    const k = novo / total
    const [cx, cy] = [(c[0] + c[2]) / 2, (c[1] + c[3]) / 2]
    partes.forEach((p) => {
      if (p.forma === "poli") {
        p.pontos = p.pontos.map(([x, y]) => [cx + (x - cx) * k, cy + (y - cy) * k])
        return
      }
      p.x = cx + (p.x - cx) * k
      p.y = cy + (p.y - cy) * k
      p.b *= k
      p.h *= k
    })
    return
  }
  partes.forEach((p, j) => {
    if (crescem.has(j)) {
      p[eixo] += delta
      return
    }
    const centro = (caixas[j][e.ini] + caixas[j][e.fim]) / 2
    if (centro > meio + TOLERANCIA) mover(p, ...e.passo(delta / 2))
    else if (centro < meio - TOLERANCIA) mover(p, ...e.passo(-delta / 2))
  })
}
