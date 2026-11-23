// O solver do esboço no navegador. É o mesmo de core/esboco.py, equação por equação e na mesma
// ordem, com os mesmos números: o desenho que a prancheta mostra é o que o Montador vai refazer.
// Incógnitas: x e y de cada ponto e o raio de cada círculo. Newton com o passo de menor norma,
// Δ = −Jᵀ(JJᵀ + μI)⁻¹F, e derivada numérica por diferença central.

const ES_ORIGEM = "O"
const ES_MAX_ITERACOES = 30
const ES_MAX_CORTES = 10
const ES_PASSO_DA_CONTINUACAO = 0.25
const ES_MAX_PASSOS = 40
const ES_TOLERANCIA = 1e-9
const ES_DERIVADA = 1e-6
const ES_AMORTECIMENTO = 1e-10
const ES_PASSO_MAXIMO = 0.5
const ES_PERDIDO = 1e3
const ES_ANGULO_DE_ESCALA = 15

const esHyp = (dx, dy) => Math.sqrt(dx * dx + dy * dy)
// Distância do ponto à reta AB, positiva à esquerda de quem vai de A para B.
const esDistSinal = (px, py, ax, ay, bx, by) => {
  const dx = bx - ax
  const dy = by - ay
  return (dx * (py - ay) - dy * (px - ax)) / esHyp(dx, dy)
}
const esGirar = (a) => a - 2 * Math.PI * Math.round(a / (2 * Math.PI))
const esAnguloEntre = (v) => {
  const d1x = v[2] - v[0]
  const d1y = v[3] - v[1]
  const d2x = v[6] - v[4]
  const d2y = v[7] - v[5]
  return Math.atan2(d1x * d2y - d1y * d2x, d1x * d2x + d1y * d2y)
}

function esTamanho(esboco) {
  const xs = []
  const ys = []
  for (const [x, y] of Object.values(esboco.pontos)) {
    xs.push(x)
    ys.push(y)
  }
  for (const c of esboco.curvas) {
    if (c.tipo === "circulo") {
      const [cx, cy] = esboco.pontos[c.pontos[0]]
      xs.push(cx - c.raio, cx + c.raio)
      ys.push(cy - c.raio, cy + c.raio)
    }
  }
  const d = Math.hypot(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys))
  return d > 1e-9 ? d : 100
}

function esValores(esboco) {
  const v = {}
  for (const item of esboco.variaveis ?? []) v[item.nome] = item.valor
  return v
}

// O sistema: colunas, valores de partida e as equações {origem, colunas, f(v, a), conta, angulo}.
function esSistema(esboco) {
  if (!esboco.pontos[ES_ORIGEM]) esboco.pontos[ES_ORIGEM] = [0, 0]
  const colunas = new Map()
  const raios = new Map()
  const q0 = []
  // A origem vai primeiro, como no Python (o dicionário de lá começa por ela).
  const ids = [ES_ORIGEM, ...Object.keys(esboco.pontos).filter((p) => p !== ES_ORIGEM)]
  for (const pid of ids) {
    colunas.set(pid, q0.length)
    q0.push(esboco.pontos[pid][0], esboco.pontos[pid][1])
  }
  for (const c of esboco.curvas) {
    if (c.tipo === "circulo") {
      raios.set(c.id, q0.length)
      q0.push(c.raio)
    }
  }
  const s = {
    esboco,
    ids,
    colunas,
    raios,
    q0: Float64Array.from(q0),
    n: q0.length,
    tamanho: esTamanho(esboco),
    equacoes: [],
    porId: new Map(esboco.curvas.map((c) => [c.id, c])),
  }
  esMontar(s)
  s.m = s.equacoes.length
  return s
}

function esPonto(s, pid) {
  const i = s.colunas.get(pid)
  if (i === undefined) throw new Error(`O ponto ${pid} não existe.`)
  return [i, i + 1]
}
function esLinha(s, cid) {
  const c = s.porId.get(cid)
  if (!c || c.tipo !== "linha") throw new Error(`${cid} precisa ser uma linha.`)
  return [...esPonto(s, c.pontos[0]), ...esPonto(s, c.pontos[1])]
}
// Colunas e o raio: (cx, cy, r) no círculo, (cx, cy, ax, ay) no arco.
function esCircular(s, cid) {
  const c = s.porId.get(cid)
  if (c?.tipo === "circulo") {
    return { colunas: [...esPonto(s, c.pontos[0]), s.raios.get(cid)], raio: (v, o) => v[o + 2] }
  }
  if (c?.tipo === "arco") {
    return {
      colunas: [...esPonto(s, c.pontos[0]), ...esPonto(s, c.pontos[1])],
      raio: (v, o) => esHyp(v[o + 2] - v[o], v[o + 3] - v[o + 1]),
    }
  }
  throw new Error(`${cid} precisa ser círculo ou arco.`)
}
function esJuntar(s, origem, colunas, f, extra = {}) {
  s.equacoes.push({ origem, colunas, f, conta: null, angulo: false, ...extra })
}

function esMontar(s) {
  const e = s.esboco
  const t = s.tamanho
  const o = esPonto(s, ES_ORIGEM)
  esJuntar(s, "origem", [o[0]], (v) => v[0])
  esJuntar(s, "origem", [o[1]], (v) => v[0])
  for (const c of e.curvas) {
    if (c.tipo !== "arco") continue
    const cols = c.pontos.flatMap((p) => esPonto(s, p))
    esJuntar(s, c.id, cols, (v) => esHyp(v[2] - v[0], v[3] - v[1]) - esHyp(v[4] - v[0], v[5] - v[1]))
  }
  for (const r of e.restricoes ?? []) esRestricao(s, r, t)
  for (const cota of e.cotas ?? []) if (!cota.referencia) esCota(s, cota)
}

function esRestricao(s, r, t) {
  const tipo = r.tipo
  const curvas = r.curvas ?? []
  const pontos = r.pontos ?? []
  if (tipo === "horizontal" || tipo === "vertical") {
    for (const cid of curvas) {
      const cols = esLinha(s, cid)
      if (tipo === "horizontal") esJuntar(s, r.id, cols, (v) => v[3] - v[1])
      else esJuntar(s, r.id, cols, (v) => v[2] - v[0])
    }
    if (!curvas.length && pontos.length === 2) {
      const cols = [...esPonto(s, pontos[0]), ...esPonto(s, pontos[1])]
      const k = tipo === "horizontal" ? 1 : 0
      esJuntar(s, r.id, cols, (v) => v[2 + k] - v[k])
    }
  } else if (tipo === "coincidente" || tipo === "concentrico") {
    const centros = tipo === "concentrico" ? curvas.map((c) => s.porId.get(c).pontos[0]) : pontos
    for (const outro of centros.slice(1)) {
      const cols = [...esPonto(s, centros[0]), ...esPonto(s, outro)]
      esJuntar(s, r.id, cols, (v) => v[2] - v[0])
      esJuntar(s, r.id, cols, (v) => v[3] - v[1])
    }
  } else if (tipo === "na_curva") {
    const p = esPonto(s, pontos[0])
    const c = s.porId.get(curvas[0])
    if (c.tipo === "linha") {
      esJuntar(s, r.id, [...p, ...esLinha(s, c.id)], (v) => esDistSinal(v[0], v[1], v[2], v[3], v[4], v[5]))
    } else {
      const { colunas, raio } = esCircular(s, c.id)
      esJuntar(s, r.id, [...p, ...colunas], (v) => esHyp(v[0] - v[2], v[1] - v[3]) - raio(v, 2))
    }
  } else if (tipo === "ponto_medio") {
    const cols = [...esPonto(s, pontos[0]), ...esLinha(s, curvas[0])]
    esJuntar(s, r.id, cols, (v) => v[0] - (v[2] + v[4]) / 2)
    esJuntar(s, r.id, cols, (v) => v[1] - (v[3] + v[5]) / 2)
  } else if (tipo === "fixo") {
    const [x0, y0] = r.valores?.length ? [r.valores[0], r.valores[1] ?? 0] : s.esboco.pontos[pontos[0]]
    const p = esPonto(s, pontos[0])
    esJuntar(s, r.id, [p[0]], (v) => v[0] - x0)
    esJuntar(s, r.id, [p[1]], (v) => v[0] - y0)
  } else if (tipo === "paralela" || tipo === "perpendicular") {
    const base = esLinha(s, curvas[0])
    for (const outra of curvas.slice(1)) {
      const cols = [...base, ...esLinha(s, outra)]
      const paralela = tipo === "paralela"
      esJuntar(s, r.id, cols, (v) => {
        const d1x = v[2] - v[0]
        const d1y = v[3] - v[1]
        const d2x = v[6] - v[4]
        const d2y = v[7] - v[5]
        const topo = paralela ? d1x * d2y - d1y * d2x : d1x * d2x + d1y * d2y
        return (t * topo) / (esHyp(d1x, d1y) * esHyp(d2x, d2y))
      })
    }
  } else if (tipo === "igual") {
    const primeira = s.porId.get(curvas[0])
    for (const cid of curvas.slice(1)) {
      const outra = s.porId.get(cid)
      if (primeira.tipo === "linha" && outra.tipo === "linha") {
        const cols = [...esLinha(s, primeira.id), ...esLinha(s, cid)]
        esJuntar(s, r.id, cols, (v) => esHyp(v[2] - v[0], v[3] - v[1]) - esHyp(v[6] - v[4], v[7] - v[5]))
      } else if (primeira.tipo !== "linha" && outra.tipo !== "linha") {
        const a = esCircular(s, primeira.id)
        const b = esCircular(s, cid)
        const n1 = a.colunas.length
        esJuntar(s, r.id, [...a.colunas, ...b.colunas], (v) => a.raio(v, 0) - b.raio(v, n1))
      } else throw new Error("Iguais: duas linhas, ou dois círculos e arcos.")
    }
  } else if (tipo === "tangente") {
    esTangente(s, r)
  } else if (tipo === "simetrico") {
    const cols = [...esPonto(s, pontos[0]), ...esPonto(s, pontos[1]), ...esLinha(s, curvas[0])]
    esJuntar(s, r.id, cols, (v) => esDistSinal((v[0] + v[2]) / 2, (v[1] + v[3]) / 2, v[4], v[5], v[6], v[7]))
    esJuntar(s, r.id, cols, (v) => {
      const dx = v[6] - v[4]
      const dy = v[7] - v[5]
      return ((v[2] - v[0]) * dx + (v[3] - v[1]) * dy) / esHyp(dx, dy)
    })
  }
}

function esTangente(s, r) {
  let c1 = s.porId.get(r.curvas[0])
  let c2 = s.porId.get(r.curvas[1])
  if (c1.tipo === "linha" && c2.tipo === "linha") throw new Error("Tangente: uma linha e um círculo, ou dois círculos.")
  if (c1.tipo !== "linha" && c2.tipo === "linha") [c1, c2] = [c2, c1]
  const q = s.q0
  if (c1.tipo === "linha") {
    const linha = esLinha(s, c1.id)
    const { colunas, raio } = esCircular(s, c2.id)
    const comum = c2.tipo === "arco" ? c1.pontos.slice(0, 2).findIndex((p) => c2.pontos.slice(1).includes(p)) : -1
    if (comum >= 0) {
      // Ponta comum: o raio até ela fica de pé sobre a reta (igual ao Python, core/esboco.py).
      const k = 2 * comum
      esJuntar(s, r.id, [...linha, ...colunas], (v) => {
        const dx = v[2] - v[0]
        const dy = v[3] - v[1]
        return ((v[k] - v[4]) * dx + (v[k + 1] - v[5]) * dy) / esHyp(dx, dy)
      })
      return
    }
    let lado = r.valores?.length ? r.valores[0] : null
    if (lado === null) {
      const d = esDistSinal(q[colunas[0]], q[colunas[1]], ...linha.map((i) => q[i]))
      lado = d >= 0 ? 1 : -1
    }
    esJuntar(s, r.id, [...linha, ...colunas], (v) => lado * esDistSinal(v[4], v[5], v[0], v[1], v[2], v[3]) - raio(v, 4))
    return
  }
  const a = esCircular(s, c1.id)
  const b = esCircular(s, c2.id)
  const n1 = a.colunas.length
  const v0 = [...a.colunas, ...b.colunas].map((i) => q[i])
  const distancia = esHyp(v0[n1] - v0[0], v0[n1 + 1] - v0[1])
  const ra = a.raio(v0, 0)
  const rb = b.raio(v0, n1)
  const modo =
    r.modo || (Math.abs(distancia - ra - rb) <= Math.abs(distancia - Math.abs(ra - rb)) ? "externa" : "interna")
  const sinal = r.valores?.length ? r.valores[0] : ra >= rb ? 1 : -1
  esJuntar(s, r.id, [...a.colunas, ...b.colunas], (v) => {
    const d = esHyp(v[n1] - v[0], v[n1 + 1] - v[1])
    if (modo === "externa") return d - a.raio(v, 0) - b.raio(v, n1)
    return d - sinal * (a.raio(v, 0) - b.raio(v, n1))
  })
}

function esCota(s, cota) {
  const conta = lerConta(cota.expressao)
  const q = s.q0
  if (cota.tipo === "distancia") {
    let ids = cota.pontos ?? []
    if (ids.length < 2 && cota.curvas?.length) ids = s.porId.get(cota.curvas[0]).pontos.slice(0, 2)
    const cols = [...esPonto(s, ids[0]), ...esPonto(s, ids[1])]
    if (cota.modo === "h" || cota.modo === "v") {
      const k = cota.modo === "h" ? 0 : 1
      const sinal = cota.sinal || (q[cols[2 + k]] - q[cols[k]] >= 0 ? 1 : -1)
      esJuntar(s, cota.id, cols, (v, a) => v[2 + k] - v[k] - sinal * a, { conta })
    } else {
      esJuntar(s, cota.id, cols, (v, a) => esHyp(v[2] - v[0], v[3] - v[1]) - a, { conta })
    }
  } else if (cota.tipo === "ponto_linha") {
    const cols = [...esPonto(s, cota.pontos[0]), ...esLinha(s, cota.curvas[0])]
    const d0 = esDistSinal(...cols.map((i) => q[i]))
    const sinal = cota.sinal || (d0 >= 0 ? 1 : -1)
    esJuntar(s, cota.id, cols, (v, a) => sinal * esDistSinal(v[0], v[1], v[2], v[3], v[4], v[5]) - a, { conta })
  } else if (cota.tipo === "diametro" || cota.tipo === "raio") {
    const { colunas, raio } = esCircular(s, cota.curvas[0])
    const fator = cota.tipo === "diametro" ? 2 : 1
    esJuntar(s, cota.id, colunas, (v, a) => fator * raio(v, 0) - a, { conta })
  } else if (cota.tipo === "angulo") {
    const cols = [...esLinha(s, cota.curvas[0]), ...esLinha(s, cota.curvas[1])]
    const t = s.tamanho
    const a0 = esAnguloEntre(cols.map((i) => q[i]))
    const sinal = cota.sinal || (a0 >= 0 ? 1 : -1)
    esJuntar(s, cota.id, cols, (v, a) => t * esGirar(esAnguloEntre(v) - (sinal * a * Math.PI) / 180), {
      conta,
      angulo: true,
    })
  }
}

// ---- contas -------------------------------------------------------------------------------------

function esAlvos(s, valores) {
  return s.equacoes.map((eq) => (eq.conta ? avaliarConta(eq.conta, valores) : 0))
}
function esResiduos(s, q, alvos) {
  return s.equacoes.map((eq, i) => eq.f(eq.colunas.map((c) => q[c]), alvos[i]))
}
function esJacobiano(s, q, alvos) {
  const h = ES_DERIVADA * s.tamanho
  return s.equacoes.map((eq, i) => {
    const linha = new Float64Array(s.n)
    const v = eq.colunas.map((c) => q[c])
    eq.colunas.forEach((coluna, j) => {
      const mais = v.slice()
      const menos = v.slice()
      mais[j] += h
      menos[j] -= h
      linha[coluna] += (eq.f(mais, alvos[i]) - eq.f(menos, alvos[i])) / (2 * h)
    })
    return linha
  })
}
const esMaxAbs = (f) => f.reduce((m, v) => (Number.isFinite(v) ? Math.max(m, Math.abs(v)) : Infinity), 0)
const esNorma = (f) => Math.sqrt(f.reduce((m, v) => m + v * v, 0))

// Eliminação de Gauss com pivô parcial. A é m×m (lista de linhas), b é m.
function esResolverLinear(A, b) {
  const m = b.length
  const M = A.map((linha, i) => [...linha, b[i]])
  for (let c = 0; c < m; c += 1) {
    let pivo = c
    for (let r = c + 1; r < m; r += 1) if (Math.abs(M[r][c]) > Math.abs(M[pivo][c])) pivo = r
    if (M[pivo][c] === 0) return null
    ;[M[c], M[pivo]] = [M[pivo], M[c]]
    for (let r = c + 1; r < m; r += 1) {
      const fator = M[r][c] / M[c][c]
      if (fator === 0) continue
      for (let k = c; k <= m; k += 1) M[r][k] -= fator * M[c][k]
    }
  }
  const x = new Array(m).fill(0)
  for (let r = m - 1; r >= 0; r -= 1) {
    let soma = M[r][m]
    for (let k = r + 1; k < m; k += 1) soma -= M[r][k] * x[k]
    x[r] = soma / M[r][r]
  }
  return x
}

// Devolve { q, erro }.
function esNewton(s, qInicial, alvos) {
  const q = Float64Array.from(qInicial)
  if (s.m === 0) return { q, erro: 0 }
  const tolerancia = ES_TOLERANCIA * s.tamanho
  const limite = ES_PASSO_MAXIMO * s.tamanho
  let f = esResiduos(s, q, alvos)
  for (let it = 0; it < ES_MAX_ITERACOES; it += 1) {
    const erro = esMaxAbs(f)
    if (!(erro > tolerancia)) break
    if (!Number.isFinite(erro)) break
    const J = esJacobiano(s, q, alvos)
    const m = s.m
    const JJt = Array.from({ length: m }, () => new Array(m).fill(0))
    for (let i = 0; i < m; i += 1) {
      for (let j = i; j < m; j += 1) {
        let soma = 0
        const a = J[i]
        const b = J[j]
        for (let k = 0; k < s.n; k += 1) soma += a[k] * b[k]
        JJt[i][j] = soma
        JJt[j][i] = soma
      }
    }
    let diagonal = 0
    for (let i = 0; i < m; i += 1) diagonal = Math.max(diagonal, JJt[i][i])
    const mu = ES_AMORTECIMENTO * (diagonal > 0 ? diagonal : 1)
    for (let i = 0; i < m; i += 1) JJt[i][i] += mu
    const y = esResolverLinear(JJt, f)
    if (!y) break
    const passo = new Float64Array(s.n)
    for (let i = 0; i < m; i += 1) {
      const linha = J[i]
      for (let k = 0; k < s.n; k += 1) passo[k] -= linha[k] * y[i]
    }
    let maior = 0
    for (const v of passo) maior = Math.max(maior, Math.abs(v))
    let t = maior > limite ? limite / maior : 1
    const norma = esNorma(f)
    let novaQ = q.map((v, k) => v + t * passo[k])
    let novaF = esResiduos(s, novaQ, alvos)
    for (let c = 0; c < ES_MAX_CORTES; c += 1) {
      if (esNorma(novaF) < norma) break
      t /= 2
      novaQ = q.map((v, k) => v + t * passo[k])
      novaF = esResiduos(s, novaQ, alvos)
    }
    if (!(esNorma(novaF) < norma)) break
    q.set(novaQ)
    f = novaF
  }
  return { q, erro: esMaxAbs(f) }
}

// O esboço com as letras em `valores`, partindo do desenho como está e levando as cotas aos poucos.
function esResolver(s, valores = {}, { qInicial = null, valoresIniciais = null, alvosIniciais = null } = {}) {
  const base = esValores(s.esboco)
  const alvos0 = alvosIniciais ?? esAlvos(s, { ...base, ...(valoresIniciais ?? {}) })
  const alvos1 = esAlvos(s, { ...base, ...valores })
  let { q } = esNewton(s, qInicial ?? s.q0, alvos0)
  let fracao = 0
  s.equacoes.forEach((eq, i) => {
    const escala = eq.angulo
      ? Math.max(Math.abs(alvos0[i]), ES_ANGULO_DE_ESCALA)
      : Math.max(Math.abs(alvos0[i]), 0.05 * s.tamanho)
    const v = Math.abs(alvos1[i] - alvos0[i]) / escala
    if (Number.isFinite(v)) fracao = Math.max(fracao, v)
  })
  const passos = Math.min(Math.max(Math.ceil(fracao / ES_PASSO_DA_CONTINUACAO), 1), ES_MAX_PASSOS)
  let erro = 0
  let perdido = false
  for (let p = 1; p <= passos; p += 1) {
    const t = Math.min(p / passos, 1)
    const alvos = alvos0.map((a, i) => a + t * (alvos1[i] - a))
    ;({ q, erro } = esNewton(s, q, alvos))
    // Quem se perde no caminho já não chega: para ali, como no Python.
    if (!(erro <= ES_TOLERANCIA * s.tamanho * ES_PERDIDO)) {
      perdido = true
      break
    }
  }
  return { q, erro, convergiu: !perdido && erro <= ES_TOLERANCIA * s.tamanho * 10 }
}

// Arrastar: os pontos pegos vão para onde o mouse está, e o resto se acomoda com o menor
// movimento. Se o lugar não cabe nas restrições, o desenho volta para o mais perto que cabe.
// `alvos` é uma lista { coluna, valor }.
function esArrastar(s, q, alvosDoArrasto) {
  const proposta = Float64Array.from(q)
  for (const { coluna, valor } of alvosDoArrasto) proposta[coluna] = valor
  const valores = esValores(s.esboco)
  const alvos = esAlvos(s, valores)
  const preso = {
    ...s,
    equacoes: [
      ...s.equacoes,
      ...alvosDoArrasto.map(({ coluna, valor }) => ({ origem: "arrasto", colunas: [coluna], f: (v) => v[0] - valor })),
    ],
  }
  preso.m = preso.equacoes.length
  const tentativa = esNewton(preso, proposta, [...alvos, ...alvosDoArrasto.map(() => 0)])
  if (tentativa.erro <= ES_TOLERANCIA * s.tamanho * 10) return tentativa.q
  const volta = esNewton(s, proposta, alvos)
  if (volta.erro <= ES_TOLERANCIA * s.tamanho * 10) return volta.q
  return Float64Array.from(q)
}

// Graus de liberdade: Gram-Schmidt nas linhas do jacobiano, na ordem das equações. Coordenada
// presa = o vetor dela cabe inteiro no espaço das linhas.
function esGraus(s, q) {
  const J = esJacobiano(s, q, esAlvos(s, esValores(s.esboco)))
  const base = []
  const redundantes = []
  J.forEach((linha, i) => {
    const v = Float64Array.from(linha)
    for (let passada = 0; passada < 2; passada += 1) {
      for (const b of base) {
        let p = 0
        for (let k = 0; k < s.n; k += 1) p += v[k] * b[k]
        for (let k = 0; k < s.n; k += 1) v[k] -= p * b[k]
      }
    }
    const norma = esNorma(v)
    if (norma <= 1e-7 * Math.max(esNorma(linha), 1e-300)) redundantes.push(i)
    else base.push(v.map((x) => x / norma))
  })
  const presa = new Float64Array(s.n)
  for (const b of base) for (let k = 0; k < s.n; k += 1) presa[k] += b[k] * b[k]
  const colunasLivres = new Set()
  presa.forEach((v, k) => {
    if (v < 1 - 1e-6) colunasLivres.add(k)
  })
  const pontosLivres = new Set()
  for (const [pid, i] of s.colunas) if (colunasLivres.has(i) || colunasLivres.has(i + 1)) pontosLivres.add(pid)
  const curvasLivres = new Set()
  for (const c of s.esboco.curvas) {
    if (c.pontos.some((p) => pontosLivres.has(p)) || colunasLivres.has(s.raios.get(c.id))) curvasLivres.add(c.id)
  }
  return {
    livres: s.n - base.length,
    colunasLivres,
    redundantes,
    pontosLivres,
    curvasLivres,
    definido: s.n - base.length === 0,
  }
}

// O esboço com os números de q.
function esComQ(s, q) {
  const e = s.esboco
  const pontos = {}
  for (const [pid, i] of s.colunas) pontos[pid] = [q[i], q[i + 1]]
  const curvas = e.curvas.map((c) => (s.raios.has(c.id) ? { ...c, raio: q[s.raios.get(c.id)] } : c))
  return { ...e, pontos, curvas }
}

// As restrições e cotas que ficaram sem fechar.
function esConflitos(s, q) {
  const f = esResiduos(s, q, esAlvos(s, esValores(s.esboco)))
  const tolerancia = ES_TOLERANCIA * s.tamanho * 10
  const saida = []
  f.forEach((v, i) => {
    const origem = s.equacoes[i].origem
    if (!(Math.abs(v) <= tolerancia) && !saida.includes(origem)) saida.push(origem)
  })
  return saida
}

// O que cada cota mede no desenho de agora: o ponto de partida quando uma medida muda na prancheta.
// As equações das cotas são de primeiro grau no alvo, então duas contas dão o valor que zera.
function esAlvosAtuais(s, q) {
  return s.equacoes.map((eq) => {
    if (!eq.conta) return 0
    const v = eq.colunas.map((c) => q[c])
    const f0 = eq.f(v, 0)
    const f1 = eq.f(v, 1)
    return f1 !== f0 ? -f0 / (f1 - f0) : 0
  })
}
