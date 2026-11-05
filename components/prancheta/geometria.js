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

// ---------------------------------------------------------------------------
// Pontos de encaixe e cotas de um ponto a outro
// ---------------------------------------------------------------------------

// Uma âncora aponta para um ponto de uma parte, e não para coordenadas: a cota acompanha a peça.
// t: "v" canto ou vértice, "m" meio de lado, "c" centro.
function ancorasDaParte(p, i) {
  const lista = []
  if (p.forma === "circ") {
    lista.push({ i, t: "c", k: 0, x: p.x, y: p.y })
    ;[[1, 0], [0, 1], [-1, 0], [0, -1]].forEach(([sx, sy], k) => {
      lista.push({ i, t: "v", k, x: p.x + (sx * p.b) / 2, y: p.y + (sy * p.b) / 2 })
    })
    return lista
  }
  const anel = cantos(p)
  anel.forEach(([x, y], k) => {
    const [u, w] = anel[(k + 1) % anel.length]
    lista.push({ i, t: "v", k, x, y })
    lista.push({ i, t: "m", k, x: (x + u) / 2, y: (y + w) / 2 })
  })
  if (p.forma === "ret") lista.push({ i, t: "c", k: 0, x: p.x, y: p.y })
  return lista
}

function pontoDaAncora(partes, a) {
  const p = partes[a.i]
  if (!p) return null
  const achada = ancorasDaParte(p, a.i).find((q) => q.t === a.t && q.k === a.k)
  return achada ? [achada.x, achada.y] : null
}

const mesmaAncora = (a, b) => a.i === b.i && a.t === b.t && a.k === b.k

const cotasValidas = (partes, cotas) =>
  cotas.filter((c) => pontoDaAncora(partes, c.a) && pontoDaAncora(partes, c.b))

function direcaoDaCota(A, B, modo) {
  const [dx, dy] = [B[0] - A[0], B[1] - A[1]]
  if (modo === "h") return [dx < 0 ? -1 : 1, 0]
  if (modo === "v") return [0, dy < 0 ? -1 : 1]
  const d = Math.hypot(dx, dy)
  return d ? [dx / d, dy / d] : [1, 0]
}

function medidaEntre(A, B, modo) {
  if (modo === "h") return Math.abs(B[0] - A[0])
  if (modo === "v") return Math.abs(B[1] - A[1])
  return Math.hypot(B[0] - A[0], B[1] - A[1])
}

// O lugar do mouse escolhe o tipo, como num CAD: em cima ou embaixo dos dois pontos mede a distância
// horizontal; ao lado deles, a vertical; na diagonal, a distância direta.
function modoDaCota(A, B, M) {
  const [dx, dy] = [Math.abs(B[0] - A[0]), Math.abs(B[1] - A[1])]
  if (dx < TOLERANCIA) return "v"
  if (dy < TOLERANCIA) return "h"
  const dentroX = M[0] >= Math.min(A[0], B[0]) && M[0] <= Math.max(A[0], B[0])
  const dentroY = M[1] >= Math.min(A[1], B[1]) && M[1] <= Math.max(A[1], B[1])
  if (dentroX && !dentroY) return "h"
  if (dentroY && !dentroX) return "v"
  return "a"
}

function folgaDaCota(A, B, modo, M) {
  if (modo === "h") return M[1] - (A[1] + B[1]) / 2
  if (modo === "v") return M[0] - (A[0] + B[0]) / 2
  const [ux, uy] = direcaoDaCota(A, B, "a")
  return (M[0] - A[0]) * -uy + (M[1] - A[1]) * ux
}

function linhaDaCota(A, B, modo, folga) {
  if (modo === "h") {
    const y = (A[1] + B[1]) / 2 + folga
    return [[A[0], y], [B[0], y]]
  }
  if (modo === "v") {
    const x = (A[0] + B[0]) / 2 + folga
    return [[x, A[1]], [x, B[1]]]
  }
  const [ux, uy] = direcaoDaCota(A, B, "a")
  const [nx, ny] = [-uy * folga, ux * folga]
  return [[A[0] + nx, A[1] + ny], [B[0] + nx, B[1] + ny]]
}

// ---------------------------------------------------------------------------
// Polígono
// ---------------------------------------------------------------------------

function areaComSinal(pontos) {
  let soma = 0
  pontos.forEach(([x, y], k) => {
    const [u, w] = pontos[(k + 1) % pontos.length]
    soma += x * w - u * y
  })
  return soma / 2
}

// Vale também encostar e sobrepor: dois lados que dividem a mesma linha estragam a seção tanto quanto
// um cruzamento em X, e só um teste de sinal não veria isso.
function ladosSeTocam(a, b, c, d) {
  const lado = (p, q, r) => (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
  const sobre = (p, q, r) =>
    Math.abs(lado(p, q, r)) <= TOLERANCIA &&
    r[0] >= Math.min(p[0], q[0]) - TOLERANCIA &&
    r[0] <= Math.max(p[0], q[0]) + TOLERANCIA &&
    r[1] >= Math.min(p[1], q[1]) - TOLERANCIA &&
    r[1] <= Math.max(p[1], q[1]) + TOLERANCIA
  const opostos = (u, v) => (u > TOLERANCIA && v < -TOLERANCIA) || (u < -TOLERANCIA && v > TOLERANCIA)
  if (opostos(lado(c, d, a), lado(c, d, b)) && opostos(lado(a, b, c), lado(a, b, d))) return true
  return sobre(c, d, a) || sobre(c, d, b) || sobre(a, b, c) || sobre(a, b, d)
}

// Devolve o motivo, ou vazio. O Python descarta o polígono sem área, e ele sumiria do desenho.
function problemaDoPoligono(pontos) {
  const n = pontos.length
  if (n < 3) return "O polígono precisa de ao menos 3 pontos."
  for (let k = 0; k < n; k += 1) {
    const [a, b] = [pontos[k], pontos[(k + 1) % n]]
    if (Math.hypot(b[0] - a[0], b[1] - a[1]) < TOLERANCIA) return "Dois pontos ficariam no mesmo lugar."
  }
  if (Math.abs(areaComSinal(pontos)) < TOLERANCIA) return "O polígono ficaria sem área."
  for (let k = 0; k < n; k += 1) {
    for (let j = k + 2; j < n; j += 1) {
      if (k === 0 && j === n - 1) continue
      if (ladosSeTocam(pontos[k], pontos[k + 1], pontos[j], pontos[(j + 1) % n])) {
        return "O contorno cruzaria a si mesmo."
      }
    }
  }
  return ""
}

// Anda pelo contorno a partir do ponto e leva junto o trecho ligado que está além dele. Mover só o
// ponto entortaria o perfil: num T, subir a alma tem de levar a mesa inteira, e num U, subir uma aba
// não pode levar a outra, que fica depois de um trecho que desce.
function esticarContorno(pontos, sementes, d, u, fixos) {
  const n = pontos.length
  const alcance = (k) => pontos[k][0] * u[0] + pontos[k][1] * u[1]
  const limite = Math.min(...sementes.map(alcance)) - TOLERANCIA
  const andam = new Set(sementes)
  for (const inicio of sementes) {
    for (const passo of [1, -1]) {
      let k = inicio
      for (let c = 0; c < n; c += 1) {
        k = (k + passo + n) % n
        if (fixos.has(k) || alcance(k) < limite) break
        andam.add(k)
      }
    }
  }
  andam.forEach((k) => {
    pontos[k] = [pontos[k][0] + d[0], pontos[k][1] + d[1]]
  })
}

const verticesDaAncora = (a, n) => (a.t === "m" ? [a.k, (a.k + 1) % n] : [a.k])

function ajustarNaChapa(p, c, A, B, novo) {
  if (p.giro) return "Chapa girada: mude pelo painel de medidas."
  const dx = Math.abs(B[0] - A[0])
  const dy = Math.abs(B[1] - A[1])
  const eixo = c.modo === "h" || (c.modo === "a" && dy < TOLERANCIA) ? "b" : "h"
  const reta = c.modo !== "a" || dx < TOLERANCIA || dy < TOLERANCIA
  if (!reta || Math.abs((eixo === "b" ? dx : dy) - p[eixo]) > TOLERANCIA) {
    return "Na chapa, escolha dois pontos de lados opostos, na mesma direção."
  }
  const [ini, sinal] = eixo === "b" ? [A[0], Math.sign(B[0] - A[0])] : [A[1], Math.sign(B[1] - A[1])]
  p[eixo] = novo
  if (eixo === "b") p.x = ini + (sinal * novo) / 2
  else p.y = ini + (sinal * novo) / 2
  return ""
}

// Muda a medida deixando o primeiro ponto no lugar. Devolve o motivo se não der. Quem chama passa uma
// cópia: um polígono que falhou no meio não pode ficar pela metade.
function ajustarCota(partes, c, novo) {
  if (!(novo > 0)) return "A medida precisa ser maior que zero."
  const A = pontoDaAncora(partes, c.a)
  const B = pontoDaAncora(partes, c.b)
  if (!A || !B) return "Esta cota perdeu um dos pontos."
  const u = direcaoDaCota(A, B, c.modo)
  const delta = novo - medidaEntre(A, B, c.modo)
  const d = [u[0] * delta, u[1] * delta]
  if (c.a.i !== c.b.i) {
    const [ga, gb] = [partes[c.a.i].grupo, partes[c.b.i].grupo]
    if (gb && ga === gb) return "Os dois pontos são do mesmo perfil: mude pelas medidas da chapa."
    partes.forEach((p, j) => {
      if (j === c.b.i || (gb && p.grupo === gb)) mover(p, d[0], d[1])
    })
    return ""
  }
  const p = partes[c.b.i]
  if (p.forma === "circ") {
    const k = novo / medidaEntre(A, B, c.modo)
    p.b *= k
    p.h = p.b
    return ""
  }
  if (p.forma === "ret") return ajustarNaChapa(p, c, A, B, novo)
  const n = p.pontos.length
  esticarContorno(p.pontos, verticesDaAncora(c.b, n), d, u, new Set(verticesDaAncora(c.a, n)))
  return problemaDoPoligono(p.pontos)
}

// A ponta da esquerda fica, ou a de baixo: o lado cresce para a direita e para cima, como a chapa.
function cotaDoLado(partes, i, k, trocar = false) {
  const pontos = partes[i].pontos
  const j = (k + 1) % pontos.length
  const [a, b] = [pontos[k], pontos[j]]
  const antes = a[0] < b[0] - TOLERANCIA || (Math.abs(a[0] - b[0]) <= TOLERANCIA && a[1] <= b[1])
  const [fica, anda] = antes !== trocar ? [k, j] : [j, k]
  return { a: { i, t: "v", k: fica }, b: { i, t: "v", k: anda }, modo: "a", folga: 0 }
}

function anguloEntre(A, B) {
  const graus = (Math.atan2(B[1] - A[1], B[0] - A[0]) * 180) / Math.PI
  return Math.round(((graus + 360) % 360) * 1e6) / 1e6
}

function girarLado(partes, c, graus) {
  const A = pontoDaAncora(partes, c.a)
  const B = pontoDaAncora(partes, c.b)
  const p = partes[c.b.i]
  const r = Math.hypot(B[0] - A[0], B[1] - A[1])
  const a = (graus * Math.PI) / 180
  p.pontos[c.b.k] = [A[0] + r * Math.cos(a), A[1] + r * Math.sin(a)]
  return problemaDoPoligono(p.pontos)
}

function inserirVertice(partes, cotas, i, k, ponto) {
  partes[i].pontos.splice(k + 1, 0, ponto)
  const subir = (a) => (a.i === i && a.t !== "c" && a.k > k ? { ...a, k: a.k + 1 } : a)
  return cotas.map((c) => ({ ...c, a: subir(c.a), b: subir(c.b) }))
}

// Cota presa ao ponto que saiu vai junto com ele.
function apagarVertice(partes, cotas, i, k) {
  const pontos = partes[i].pontos
  const anterior = (k - 1 + pontos.length) % pontos.length
  pontos.splice(k, 1)
  const perdida = (a) =>
    a.i === i && ((a.t === "v" && a.k === k) || (a.t === "m" && (a.k === k || a.k === anterior)))
  const descer = (a) => (a.i === i && a.t !== "c" && a.k > k ? { ...a, k: a.k - 1 } : a)
  return cotas
    .filter((c) => !perdida(c.a) && !perdida(c.b))
    .map((c) => ({ ...c, a: descer(c.a), b: descer(c.b) }))
}

function cotasSemPartes(cotas, apagadas) {
  const novo = (a) => ({ ...a, i: a.i - [...apagadas].filter((j) => j < a.i).length })
  return cotas
    .filter((c) => !apagadas.has(c.a.i) && !apagadas.has(c.b.i))
    .map((c) => ({ ...c, a: novo(c.a), b: novo(c.b) }))
}

function travarAngulo([x0, y0], [x, y], passo = 45) {
  const r = Math.hypot(x - x0, y - y0)
  if (!r) return [x, y]
  const a = ((Math.round(((Math.atan2(y - y0, x - x0) * 180) / Math.PI) / passo) * passo) * Math.PI) / 180
  return [
    Math.round((x0 + r * Math.cos(a)) * 1e6) / 1e6,
    Math.round((y0 + r * Math.sin(a)) * 1e6) / 1e6,
  ]
}

// O próximo ponto por digitação: 100 na direção do mouse, 100<45 em ângulo, @50;20 em x e y.
function lerProximoPonto(texto, ultimo, mouse) {
  const s = String(texto ?? "").trim()
  if (s.startsWith("@")) {
    const resto = s.slice(1)
    const partes = (resto.includes(";") ? resto.split(";") : resto.split(",")).map((v) => v.trim())
    if (partes.length !== 2) return { erro: "Escreva @x;y, por exemplo @50;20." }
    const [dx, dy] = partes.map((v) => lerValorDigitado(v, 0, "mm"))
    if (dx.erro || dy.erro) return { erro: dx.erro || dy.erro }
    return { valor: [ultimo[0] + dx.valor, ultimo[1] + dy.valor] }
  }
  if (s.includes("<")) {
    const [comprimento, angulo] = s.split("<")
    const r = lerValorDigitado(comprimento, 0, "mm")
    const g = lerValorDigitado(angulo, 0, "°")
    if (r.erro || g.erro) return { erro: "Escreva comprimento<ângulo, por exemplo 100<45." }
    const a = (g.valor * Math.PI) / 180
    return { valor: [ultimo[0] + r.valor * Math.cos(a), ultimo[1] + r.valor * Math.sin(a)] }
  }
  const r = lerValorDigitado(s, 0, "mm")
  if (r.erro) return r
  const [dx, dy] = [mouse[0] - ultimo[0], mouse[1] - ultimo[1]]
  const d = Math.hypot(dx, dy)
  if (!d) return { erro: "Mova o mouse para a direção do próximo ponto." }
  return { valor: [ultimo[0] + (dx / d) * r.valor, ultimo[1] + (dy / d) * r.valor] }
}
