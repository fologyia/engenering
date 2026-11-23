// Edição do esboço como num CAD: aparar, estender, dividir, filete, chanfro, deslocar (offset),
// espelhar e padrões. Funções puras: recebem o esboço (sem mexer nele) e devolvem { esboco } com a
// cópia mudada, ou { erro } com o motivo. A prancheta só chama e manda o resultado ao solver.
//
// Quem é cortado ganha ponto novo no corte, preso à curva que cortou ("ponto na curva"); se já
// existe um ponto ali, ele é reaproveitado. É assim que dois contornos que se cruzam viram um só:
// apara-se um lado, depois o outro, e os cortes passam a ser pontas comuns.

const ED_DOIS_PI = 2 * Math.PI

const edCopiar = (v) => JSON.parse(JSON.stringify(v))

function edNovoId(prefixo, ids) {
  let maior = 0
  for (const id of ids) {
    const m = new RegExp(`^${prefixo}(\\d+)$`).exec(id)
    if (m) maior = Math.max(maior, Number(m[1]))
  }
  return `${prefixo}${maior + 1}`
}
const edIdPonto = (esb) => edNovoId("p", Object.keys(esb.pontos))
const edIdCurva = (esb) => edNovoId("c", esb.curvas.map((c) => c.id))
const edIdRestricao = (esb) => edNovoId("r", esb.restricoes.map((r) => r.id))
const edIdCota = (esb) => edNovoId("d", esb.cotas.map((c) => c.id))

function edTamanho(esb) {
  const xs = []
  const ys = []
  for (const [x, y] of Object.values(esb.pontos)) {
    xs.push(x)
    ys.push(y)
  }
  const d = Math.hypot(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys))
  return d > 1e-9 ? d : 100
}

function edAngAnti(de, para) {
  let d = (para - de) % ED_DOIS_PI
  if (d < 0) d += ED_DOIS_PI
  return d
}

// A curva com números: reta de a a b; arco de centro c, raio r, de ta varrendo sw anti-horário.
function edGeo(esb, c) {
  if (c.tipo === "linha") return { tipo: "linha", a: esb.pontos[c.pontos[0]], b: esb.pontos[c.pontos[1]] }
  const [cx, cy] = esb.pontos[c.pontos[0]]
  if (c.tipo === "circulo") return { tipo: "circulo", c: [cx, cy], r: c.raio, ta: 0, sw: ED_DOIS_PI }
  const [ax, ay] = esb.pontos[c.pontos[1]]
  const [bx, by] = esb.pontos[c.pontos[2]]
  const ta = Math.atan2(ay - cy, ax - cx)
  return {
    tipo: "arco",
    c: [cx, cy],
    r: Math.hypot(ax - cx, ay - cy),
    ta,
    sw: edAngAnti(ta, Math.atan2(by - cy, bx - cx)),
  }
}

// Parâmetro do ponto na curva: na reta, t (0 em a, 1 em b); no arco e no círculo, o ângulo andado
// desde o começo, de 0 a 2π.
function edParam(g, x, y) {
  if (g.tipo === "linha") {
    const dx = g.b[0] - g.a[0]
    const dy = g.b[1] - g.a[1]
    return ((x - g.a[0]) * dx + (y - g.a[1]) * dy) / (dx * dx + dy * dy || 1)
  }
  return edAngAnti(g.ta, Math.atan2(y - g.c[1], x - g.c[0]))
}
function edNoParam(g, t) {
  if (g.tipo === "linha") return [g.a[0] + t * (g.b[0] - g.a[0]), g.a[1] + t * (g.b[1] - g.a[1])]
  return [g.c[0] + g.r * Math.cos(g.ta + t), g.c[1] + g.r * Math.sin(g.ta + t)]
}
function edDentro(g, t, folga = 1e-9) {
  if (g.tipo === "linha") return t >= -folga && t <= 1 + folga
  if (g.tipo === "circulo") return true
  return t <= g.sw + folga || t >= ED_DOIS_PI - folga
}

// Onde as curvas se encontram, com a reta sem fim e o círculo inteiro: quem chama filtra.
function edEncontros(g1, g2) {
  if (g1.tipo !== "linha" && g2.tipo === "linha") return edEncontros(g2, g1)
  if (g1.tipo === "linha" && g2.tipo === "linha") {
    const d1 = [g1.b[0] - g1.a[0], g1.b[1] - g1.a[1]]
    const d2 = [g2.b[0] - g2.a[0], g2.b[1] - g2.a[1]]
    const den = d1[0] * d2[1] - d1[1] * d2[0]
    if (Math.abs(den) < 1e-12 * Math.hypot(...d1) * Math.hypot(...d2)) return []
    const t = ((g2.a[0] - g1.a[0]) * d2[1] - (g2.a[1] - g1.a[1]) * d2[0]) / den
    return [[g1.a[0] + t * d1[0], g1.a[1] + t * d1[1]]]
  }
  if (g1.tipo === "linha") {
    const d = [g1.b[0] - g1.a[0], g1.b[1] - g1.a[1]]
    const f = [g1.a[0] - g2.c[0], g1.a[1] - g2.c[1]]
    const a = d[0] * d[0] + d[1] * d[1]
    const b = 2 * (f[0] * d[0] + f[1] * d[1])
    const c = f[0] * f[0] + f[1] * f[1] - g2.r * g2.r
    const disc = b * b - 4 * a * c
    if (disc < -1e-12 * b * b) return []
    const raiz = Math.sqrt(Math.max(disc, 0))
    const ts = raiz < 1e-12 * Math.abs(b) ? [-b / (2 * a)] : [(-b - raiz) / (2 * a), (-b + raiz) / (2 * a)]
    return ts.map((t) => [g1.a[0] + t * d[0], g1.a[1] + t * d[1]])
  }
  const dx = g2.c[0] - g1.c[0]
  const dy = g2.c[1] - g1.c[1]
  const d = Math.hypot(dx, dy)
  if (d < 1e-12 || d > g1.r + g2.r + 1e-9 * (g1.r + g2.r) || d < Math.abs(g1.r - g2.r) - 1e-9 * (g1.r + g2.r)) return []
  const a = (g1.r * g1.r - g2.r * g2.r + d * d) / (2 * d)
  const h = Math.sqrt(Math.max(g1.r * g1.r - a * a, 0))
  const mx = g1.c[0] + (a * dx) / d
  const my = g1.c[1] + (a * dy) / d
  if (h < 1e-12 * g1.r) return [[mx, my]]
  return [
    [mx - (h * dy) / d, my + (h * dx) / d],
    [mx + (h * dy) / d, my - (h * dx) / d],
  ]
}

// Os cortes de uma curva pelas outras: { t, x, y, cortador }, só os que caem nas duas curvas.
function edCortes(esb, alvo) {
  const g = edGeo(esb, alvo)
  const saida = []
  for (const outra of esb.curvas) {
    if (outra.id === alvo.id) continue
    const h = edGeo(esb, outra)
    for (const [x, y] of edEncontros(g, h)) {
      const t = edParam(g, x, y)
      if (!edDentro(g, t, 1e-9) || !edDentro(h, edParam(h, x, y), 1e-9)) continue
      saida.push({ t: g.tipo === "linha" ? t : t % ED_DOIS_PI, x, y, cortador: outra.id })
    }
  }
  return saida
}

// O ponto que já existe ali, ou um novo. `naCurva`: a curva em que o novo fica preso.
function edPontoEm(esb, x, y, naCurva = null) {
  const tol = 1e-7 * edTamanho(esb)
  for (const [pid, [px, py]] of Object.entries(esb.pontos)) {
    if (Math.hypot(px - x, py - y) <= tol) return pid
  }
  const pid = edIdPonto(esb)
  esb.pontos[pid] = [x, y]
  if (naCurva) {
    const c = esb.curvas.find((k) => k.id === naCurva)
    if (c && !c.pontos.includes(pid)) esb.restricoes.push({ id: edIdRestricao(esb), tipo: "na_curva", pontos: [pid], curvas: [naCurva] })
  }
  return pid
}

const ED_DIRECAO = new Set(["horizontal", "vertical", "paralela", "perpendicular"])

// A reta partida em duas: a segunda fica na mesma reta da primeira (que guarda o id).
function edSegundaReta(esb, original, pontos) {
  const nova = { id: edIdCurva(esb), tipo: "linha", pontos }
  if (original.construcao) nova.construcao = true
  esb.curvas.push(nova)
  let comDirecao = false
  for (const r of [...esb.restricoes]) {
    if (!ED_DIRECAO.has(r.tipo) || !(r.curvas ?? []).includes(original.id)) continue
    comDirecao = true
    if (r.tipo === "horizontal" || r.tipo === "vertical") r.curvas = [...r.curvas, nova.id]
    else esb.restricoes.push({ ...edCopiar(r), id: edIdRestricao(esb), curvas: r.curvas.map((c) => (c === original.id ? nova.id : c)) })
  }
  const [p, q] = pontos
  esb.restricoes.push({ id: edIdRestricao(esb), tipo: "na_curva", pontos: [p], curvas: [original.id] })
  if (!comDirecao) esb.restricoes.push({ id: edIdRestricao(esb), tipo: "na_curva", pontos: [q], curvas: [original.id] })
  return nova.id
}

function edLimpar(esb, soltos = []) {
  const curvas = new Set(esb.curvas.map((c) => c.id))
  const tudo = (lista, conjunto) => (lista ?? []).every((x) => conjunto.has(x))
  let pontos = new Set(Object.keys(esb.pontos))
  const valida = (r) => {
    if (!tudo(r.curvas, curvas) || !tudo(r.pontos, pontos)) return false
    if (r.tipo === "na_curva" || r.tipo === "ponto_medio") {
      const c = esb.curvas.find((x) => x.id === r.curvas[0])
      if (c && c.pontos.includes(r.pontos[0])) return false
    }
    return true
  }
  esb.restricoes = esb.restricoes.filter(valida)
  esb.cotas = esb.cotas.filter((c) => tudo(c.curvas, curvas) && tudo(c.pontos, pontos))
  for (const p of soltos) {
    if (p === "O" || !(p in esb.pontos)) continue
    const usado =
      esb.curvas.some((c) => c.pontos.includes(p)) ||
      esb.restricoes.some((r) => (r.pontos ?? []).includes(p)) ||
      esb.cotas.some((c) => (c.pontos ?? []).includes(p))
    if (!usado) delete esb.pontos[p]
  }
  pontos = new Set(Object.keys(esb.pontos))
  esb.restricoes = esb.restricoes.filter(valida)
  const vistas = new Set()
  esb.restricoes = esb.restricoes.filter((r) => {
    const chave = JSON.stringify([r.tipo, r.pontos ?? [], r.curvas ?? []])
    if (vistas.has(chave)) return false
    vistas.add(chave)
    return true
  })
  return esb
}

// ---- aparar, estender, dividir ------------------------------------------------------------------

// Tira o trecho da curva entre os dois cortes em volta do clique (x, y).
function edAparar(esboco, cid, x, y) {
  const esb = edCopiar(esboco)
  const c = esb.curvas.find((k) => k.id === cid)
  if (!c) return { erro: "Essa curva não existe." }
  const g = edGeo(esb, c)
  const tc = edParam(g, x, y)
  const cortes = edCortes(esb, c)
  if (c.tipo === "circulo") {
    const angulos = [...new Map(cortes.map((k) => [Math.round(k.t * 1e9), k])).values()].sort((a, b) => a.t - b.t)
    if (angulos.length < 2) {
      esb.curvas = esb.curvas.filter((k) => k.id !== cid)
      return { esboco: edLimpar(esb, c.pontos) }
    }
    let i = angulos.findIndex((k) => k.t > tc)
    if (i < 0) i = 0
    const fim = angulos[(i - 1 + angulos.length) % angulos.length] // o corte antes do clique
    const comeco = angulos[i] // o corte depois do clique
    const pa = edPontoEm(esb, comeco.x, comeco.y, comeco.cortador)
    const pb = edPontoEm(esb, fim.x, fim.y, fim.cortador)
    c.tipo = "arco"
    c.pontos = [c.pontos[0], pa, pb]
    delete c.raio
    return { esboco: edLimpar(esb) }
  }
  const limite = c.tipo === "linha" ? 1 : g.sw
  const dentro = cortes.filter((k) => k.t > 1e-9 * limite && k.t < limite * (1 - 1e-9))
  const antes = dentro.filter((k) => k.t < tc).sort((a, b) => b.t - a.t)[0]
  const depois = dentro.filter((k) => k.t > tc).sort((a, b) => a.t - b.t)[0]
  const [ini, fim] = c.tipo === "linha" ? c.pontos : c.pontos.slice(1)
  if (!antes && !depois) {
    esb.curvas = esb.curvas.filter((k) => k.id !== cid)
    return { esboco: edLimpar(esb, c.pontos) }
  }
  const soltos = []
  const pAntes = antes ? edPontoEm(esb, antes.x, antes.y, antes.cortador) : null
  const pDepois = depois ? edPontoEm(esb, depois.x, depois.y, depois.cortador) : null
  if (c.tipo === "linha") {
    if (pAntes && pDepois) {
      c.pontos = [ini, pAntes]
      edSegundaReta(esb, c, [pDepois, fim])
    } else if (pAntes) {
      c.pontos = [ini, pAntes]
      soltos.push(fim)
    } else {
      c.pontos = [pDepois, fim]
      soltos.push(ini)
    }
  } else {
    const centro = c.pontos[0]
    if (pAntes && pDepois) {
      c.pontos = [centro, ini, pAntes]
      const nova = { id: edIdCurva(esb), tipo: "arco", pontos: [centro, pDepois, fim] }
      if (c.construcao) nova.construcao = true
      esb.curvas.push(nova)
    } else if (pAntes) {
      c.pontos = [centro, ini, pAntes]
      soltos.push(fim)
    } else {
      c.pontos = [centro, pDepois, fim]
      soltos.push(ini)
    }
  }
  return { esboco: edLimpar(esb, soltos) }
}

// Leva a ponta da reta mais perto do clique até a primeira curva no caminho.
function edEstender(esboco, cid, x, y) {
  const esb = edCopiar(esboco)
  const c = esb.curvas.find((k) => k.id === cid)
  if (!c || c.tipo !== "linha") return { erro: "Estender: escolha uma linha, perto da ponta que vai andar." }
  const g = edGeo(esb, c)
  const t = edParam(g, x, y)
  const lado = t >= 0.5 ? 1 : 0
  const ponta = c.pontos[lado]
  const ligadas = esb.curvas.filter((k) => k.id !== cid && k.pontos.includes(ponta))
  if (ligadas.length) return { erro: "Essa ponta está ligada a outra curva: separe antes de estender." }
  let melhor = null
  for (const outra of esb.curvas) {
    if (outra.id === cid) continue
    const h = edGeo(esb, outra)
    for (const [px, py] of edEncontros(g, h)) {
      const tp = edParam(g, px, py)
      const alem = lado === 1 ? tp > 1 + 1e-9 : tp < -1e-9
      if (!alem || !edDentro(h, edParam(h, px, py))) continue
      const dist = Math.abs(lado === 1 ? tp - 1 : tp)
      if (!melhor || dist < melhor.dist) melhor = { dist, x: px, y: py, curva: outra.id }
    }
  }
  if (!melhor) return { erro: "Não há curva no caminho dessa ponta." }
  const existente = edPontoEm(edCopiar(esb), melhor.x, melhor.y)
  if (existente in esb.pontos && existente !== ponta) {
    c.pontos[lado] = existente
    return { esboco: edLimpar(esb, [ponta]) }
  }
  esb.pontos[ponta] = [melhor.x, melhor.y]
  const alvo = esb.curvas.find((k) => k.id === melhor.curva)
  if (!alvo.pontos.includes(ponta)) {
    esb.restricoes.push({ id: edIdRestricao(esb), tipo: "na_curva", pontos: [ponta], curvas: [melhor.curva] })
  }
  return { esboco: edLimpar(esb) }
}

// Parte a curva em duas no ponto do clique.
function edDividir(esboco, cid, x, y) {
  const esb = edCopiar(esboco)
  const c = esb.curvas.find((k) => k.id === cid)
  if (!c) return { erro: "Essa curva não existe." }
  if (c.tipo === "circulo") return { erro: "O círculo não tem pontas: use Aparar entre dois cortes." }
  const g = edGeo(esb, c)
  let t = edParam(g, x, y)
  if (c.tipo === "linha") t = Math.min(Math.max(t, 0.02), 0.98)
  else t = Math.min(Math.max(t, 0.02 * g.sw), 0.98 * g.sw)
  const [px, py] = edNoParam(g, t)
  const p = edPontoEm(esb, px, py)
  if (c.tipo === "linha") {
    const [ini, fim] = c.pontos
    c.pontos = [ini, p]
    edSegundaReta(esb, c, [p, fim])
  } else {
    const [centro, ini, fim] = c.pontos
    c.pontos = [centro, ini, p]
    esb.curvas.push({ id: edIdCurva(esb), tipo: "arco", pontos: [centro, p, fim], ...(c.construcao ? { construcao: true } : {}) })
  }
  return { esboco: edLimpar(esb) }
}

// ---- cantos: filete e chanfro -------------------------------------------------------------------

function edCanto(esb, pid) {
  const linhas = esb.curvas.filter((c) => c.tipo === "linha" && !c.construcao && c.pontos.includes(pid))
  if (linhas.length !== 2) return { erro: "Escolha um canto onde duas linhas se encontram." }
  const P = esb.pontos[pid]
  const outra = (l) => esb.pontos[l.pontos[0] === pid ? l.pontos[1] : l.pontos[0]]
  const [A, B] = linhas.map(outra)
  const la = Math.hypot(A[0] - P[0], A[1] - P[1])
  const lb = Math.hypot(B[0] - P[0], B[1] - P[1])
  const u1 = [(A[0] - P[0]) / la, (A[1] - P[1]) / la]
  const u2 = [(B[0] - P[0]) / lb, (B[1] - P[1]) / lb]
  const cos = Math.min(Math.max(u1[0] * u2[0] + u1[1] * u2[1], -1), 1)
  const alfa = Math.acos(cos)
  if (alfa < 1e-3 || Math.PI - alfa < 1e-3) return { erro: "As duas linhas estão alinhadas: não há canto." }
  return { linhas, P, u1, u2, la, lb, alfa }
}
function edTrocarPonta(linha, de, para) {
  linha.pontos = linha.pontos.map((p) => (p === de ? para : p))
}
// O canto vira um "canto virtual": continua nas duas retas, para as cotas que apontavam para ele.
function edCantoVirtual(esb, pid, linhas) {
  const usado =
    pid === "O" ||
    esb.restricoes.some((r) => (r.pontos ?? []).includes(pid)) ||
    esb.cotas.some((c) => (c.pontos ?? []).includes(pid)) ||
    esb.curvas.some((c) => c.pontos.includes(pid))
  if (!usado) {
    delete esb.pontos[pid]
    return
  }
  for (const l of linhas) esb.restricoes.push({ id: edIdRestricao(esb), tipo: "na_curva", pontos: [pid], curvas: [l.id] })
}

function edFilete(esboco, pid, expressao, valores) {
  const esb = edCopiar(esboco)
  const canto = edCanto(esb, pid)
  if (canto.erro) return canto
  const { linhas, P, u1, u2, la, lb, alfa } = canto
  const r = avaliarConta(lerConta(expressao), valores)
  if (!(r > 0)) return { erro: "O raio precisa ser maior que zero." }
  const fi = alfa / 2
  const d = r / Math.tan(fi)
  if (d >= Math.min(la, lb)) return { erro: `O raio ${String(r).replace(".", ",")} não cabe nesse canto: as linhas são curtas.` }
  const bis = [u1[0] + u2[0], u1[1] + u2[1]]
  const lbis = Math.hypot(...bis)
  const C = [P[0] + ((r / Math.sin(fi)) * bis[0]) / lbis, P[1] + ((r / Math.sin(fi)) * bis[1]) / lbis]
  const T1 = [P[0] + d * u1[0], P[1] + d * u1[1]]
  const T2 = [P[0] + d * u2[0], P[1] + d * u2[1]]
  const p1 = edIdPonto(esb)
  esb.pontos[p1] = T1
  const p2 = edIdPonto(esb)
  esb.pontos[p2] = T2
  const pc = edIdPonto(esb)
  esb.pontos[pc] = C
  edTrocarPonta(linhas[0], pid, p1)
  edTrocarPonta(linhas[1], pid, p2)
  const anti = (T1[0] - C[0]) * (T2[1] - C[1]) - (T1[1] - C[1]) * (T2[0] - C[0]) > 0
  const arco = { id: edIdCurva(esb), tipo: "arco", pontos: anti ? [pc, p1, p2] : [pc, p2, p1] }
  esb.curvas.push(arco)
  for (const l of linhas) {
    const [a, b] = l.pontos.map((p) => esb.pontos[p])
    const lado = esDistSinal(C[0], C[1], a[0], a[1], b[0], b[1]) >= 0 ? 1 : -1
    esb.restricoes.push({ id: edIdRestricao(esb), tipo: "tangente", curvas: [l.id, arco.id], valores: [lado] })
  }
  esb.cotas.push({ id: edIdCota(esb), tipo: "raio", curvas: [arco.id], modo: "d", sinal: 1, expressao, lugar: null })
  edCantoVirtual(esb, pid, linhas)
  return { esboco: edLimpar(esb) }
}

function edChanfro(esboco, pid, expressao, valores) {
  const esb = edCopiar(esboco)
  const canto = edCanto(esb, pid)
  if (canto.erro) return canto
  const { linhas, P, u1, u2, la, lb } = canto
  const d = avaliarConta(lerConta(expressao), valores)
  if (!(d > 0)) return { erro: "A distância precisa ser maior que zero." }
  if (d >= Math.min(la, lb)) return { erro: "O chanfro não cabe nesse canto: as linhas são curtas." }
  const p1 = edIdPonto(esb)
  esb.pontos[p1] = [P[0] + d * u1[0], P[1] + d * u1[1]]
  const p2 = edIdPonto(esb)
  esb.pontos[p2] = [P[0] + d * u2[0], P[1] + d * u2[1]]
  edTrocarPonta(linhas[0], pid, p1)
  edTrocarPonta(linhas[1], pid, p2)
  esb.curvas.push({ id: edIdCurva(esb), tipo: "linha", pontos: [p1, p2] })
  // O canto continua como referência das duas medidas do chanfro.
  for (const l of linhas) esb.restricoes.push({ id: edIdRestricao(esb), tipo: "na_curva", pontos: [pid], curvas: [l.id] })
  for (const p of [p1, p2]) {
    esb.cotas.push({ id: edIdCota(esb), tipo: "distancia", pontos: [pid, p], modo: "d", sinal: 1, expressao, lugar: null })
  }
  return { esboco: edLimpar(esb) }
}

// ---- deslocar (offset) --------------------------------------------------------------------------

// As curvas escolhidas em fila, pelas pontas comuns: [{ curva, sentido }], e se fecha.
function edCorrente(esb, ids) {
  const curvas = ids.map((id) => esb.curvas.find((c) => c.id === id)).filter(Boolean)
  if (curvas.length === 1 && curvas[0].tipo === "circulo") return { itens: [{ curva: curvas[0], sentido: 1 }], fechada: true }
  if (curvas.some((c) => c.tipo === "circulo")) return { erro: "Círculo só se desloca sozinho." }
  const pontas = (c) => (c.tipo === "linha" ? c.pontos : c.pontos.slice(1))
  const grau = new Map()
  for (const c of curvas) for (const p of pontas(c)) grau.set(p, (grau.get(p) ?? 0) + 1)
  if ([...grau.values()].some((n) => n > 2)) return { erro: "As curvas escolhidas se dividem: escolha uma fila só." }
  const soltas = [...grau.entries()].filter(([, n]) => n === 1).map(([p]) => p)
  if (soltas.length !== 0 && soltas.length !== 2) return { erro: "As curvas escolhidas não formam uma fila ligada." }
  let atual = soltas[0] ?? pontas(curvas[0])[0]
  const restantes = [...curvas]
  const itens = []
  while (restantes.length) {
    const i = restantes.findIndex((c) => pontas(c).includes(atual))
    if (i < 0) return { erro: "As curvas escolhidas não formam uma fila ligada." }
    const c = restantes.splice(i, 1)[0]
    const [a, b] = pontas(c)
    const sentido = a === atual ? 1 : -1
    itens.push({ curva: c, sentido })
    atual = sentido === 1 ? b : a
  }
  return { itens, fechada: soltas.length === 0 }
}

function edDeslocar(esboco, ids, clique, expressao, valores) {
  const esb = edCopiar(esboco)
  const corrente = edCorrente(esb, ids)
  if (corrente.erro) return corrente
  const t = avaliarConta(lerConta(expressao), valores)
  if (!(t > 0)) return { erro: "A distância precisa ser maior que zero." }
  const { itens, fechada } = corrente
  // O lado: o do clique, em relação ao primeiro trecho no sentido da fila.
  const primeiro = itens[0]
  const g0 = edGeo(esb, primeiro.curva)
  let s
  if (g0.tipo === "linha") {
    const [a, b] = primeiro.sentido === 1 ? [g0.a, g0.b] : [g0.b, g0.a]
    s = esDistSinal(clique[0], clique[1], a[0], a[1], b[0], b[1]) >= 0 ? 1 : -1
  } else {
    const fora = Math.hypot(clique[0] - g0.c[0], clique[1] - g0.c[1]) > g0.r
    // Andando anti-horário, a esquerda é o centro: fora é a direita.
    const anti = g0.tipo === "circulo" || primeiro.sentido === 1
    s = fora === anti ? -1 : 1
  }
  // Cada trecho deslocado: a reta paralela, ou o arco concêntrico com outro raio.
  const novos = itens.map(({ curva, sentido }) => {
    const g = edGeo(esb, curva)
    if (g.tipo === "linha") {
      const [a, b] = sentido === 1 ? [g.a, g.b] : [g.b, g.a]
      const l = Math.hypot(b[0] - a[0], b[1] - a[1])
      const n = [(-(b[1] - a[1]) / l) * s * t, ((b[0] - a[0]) / l) * s * t]
      return { tipo: "linha", a: [a[0] + n[0], a[1] + n[1]], b: [b[0] + n[0], b[1] + n[1]], curva, sentido }
    }
    const anti = g.tipo === "circulo" || sentido === 1
    const r = g.r + (anti ? -s * t : s * t)
    if (!(r > 0)) return { erro: true }
    const ini = sentido === 1 ? g.ta : g.ta + g.sw
    const fim = sentido === 1 ? g.ta + g.sw : g.ta
    const ponto = (ang) => [g.c[0] + r * Math.cos(ang), g.c[1] + r * Math.sin(ang)]
    return { tipo: g.tipo, c: g.c, r, a: ponto(ini), b: ponto(fim), curva, sentido }
  })
  if (novos.some((n) => n.erro)) return { erro: "A distância é maior que o raio de um arco: o arco deslocado some." }
  // Os cantos: onde os trechos vizinhos deslocados se encontram (ou a ponta deslocada, se tangentes).
  const juntas = []
  const n = novos.length
  for (let i = 0; i < n; i += 1) {
    if (!fechada && i === 0) juntas.push(novos[0].a)
    if (i === n - 1 && !fechada) {
      juntas.push(novos[i].b)
      break
    }
    const atual = novos[i]
    const prox = novos[(i + 1) % n]
    const fimAtual = atual.b
    const inicioProx = prox.a
    if (Math.hypot(fimAtual[0] - inicioProx[0], fimAtual[1] - inicioProx[1]) < 1e-9 * edTamanho(esb)) {
      juntas.push(fimAtual)
      continue
    }
    const g1 = atual.tipo === "linha" ? atual : { tipo: "circulo", c: atual.c, r: atual.r, ta: 0, sw: ED_DOIS_PI }
    const g2 = prox.tipo === "linha" ? prox : { tipo: "circulo", c: prox.c, r: prox.r, ta: 0, sw: ED_DOIS_PI }
    const encontros = edEncontros(g1, g2)
    if (!encontros.length) return { erro: "Os trechos deslocados não se encontram: diminua a distância." }
    encontros.sort(
      (p, q) => Math.hypot(p[0] - fimAtual[0], p[1] - fimAtual[1]) - Math.hypot(q[0] - fimAtual[0], q[1] - fimAtual[1]),
    )
    juntas.push(encontros[0])
  }
  if (fechada && novos.length === 1 && novos[0].tipo === "circulo") {
    const k = novos[0]
    const id = edIdCurva(esb)
    esb.curvas.push({ id, tipo: "circulo", pontos: [k.curva.pontos[0]], raio: k.r })
    const cota = esb.cotas.find((c) => !c.referencia && (c.curvas ?? [])[0] === k.curva.id && (c.tipo === "diametro" || c.tipo === "raio"))
    if (cota) {
      const sinal = k.r > edGeo(esb, k.curva).r ? "+" : "-"
      const meio = cota.tipo === "raio" ? `(${cota.expressao})` : `(${cota.expressao})/2`
      esb.cotas.push({ id: edIdCota(esb), tipo: "raio", curvas: [id], modo: "d", sinal: 1, expressao: `${meio} ${sinal} (${expressao})`, lugar: null })
    }
    return { esboco: edLimpar(esb), novas: [id] }
  }
  // Os pontos dos cantos novos e as curvas novas.
  const pontos = juntas.map(([x, y]) => {
    const pid = edIdPonto(esb)
    esb.pontos[pid] = [x, y]
    return pid
  })
  const criadas = []
  novos.forEach((k, i) => {
    const pa = pontos[i]
    const pb = pontos[fechada ? (i + 1) % n : i + 1]
    const id = edIdCurva(esb)
    criadas.push(id)
    if (k.tipo === "linha") {
      esb.curvas.push({ id, tipo: "linha", pontos: k.sentido === 1 ? [pa, pb] : [pb, pa] })
      esb.restricoes.push({ id: edIdRestricao(esb), tipo: "paralela", curvas: [k.curva.id, id] })
      const [a, b] = k.curva.pontos.map((p) => esb.pontos[p])
      const [x, y] = esb.pontos[pa]
      const sinal = esDistSinal(x, y, a[0], a[1], b[0], b[1]) >= 0 ? 1 : -1
      esb.cotas.push({ id: edIdCota(esb), tipo: "ponto_linha", pontos: [pa], curvas: [k.curva.id], modo: "d", sinal, expressao, lugar: null })
      return
    }
    const centro = k.curva.pontos[0]
    esb.curvas.push({ id, tipo: "arco", pontos: k.sentido === 1 ? [centro, pa, pb] : [centro, pb, pa] })
    const cota = esb.cotas.find((c) => !c.referencia && (c.curvas ?? [])[0] === k.curva.id && (c.tipo === "diametro" || c.tipo === "raio"))
    if (cota) {
      const sinal = k.r > edGeo(esb, k.curva).r ? "+" : "-"
      const meio = cota.tipo === "raio" ? `(${cota.expressao})` : `(${cota.expressao})/2`
      esb.cotas.push({ id: edIdCota(esb), tipo: "raio", curvas: [id], modo: "d", sinal: 1, expressao: `${meio} ${sinal} (${expressao})`, lugar: null })
    }
  })
  // Arco sem cota: preso pela tangência às retas deslocadas vizinhas, como o original.
  novos.forEach((k, i) => {
    if (k.tipo === "linha") return
    if (esb.cotas.some((c) => (c.curvas ?? [])[0] === criadas[i])) return
    for (const j of [i - 1, i + 1]) {
      const v = fechada ? (j + n) % n : j
      if (v < 0 || v >= n || novos[v].tipo !== "linha") continue
      const tangentes = esb.restricoes.some(
        (r) => r.tipo === "tangente" && r.curvas.includes(k.curva.id) && r.curvas.includes(novos[v].curva.id),
      )
      if (!tangentes) continue
      const linha = esb.curvas.find((c) => c.id === criadas[v])
      const [a, b] = linha.pontos.map((p) => esb.pontos[p])
      const lado = esDistSinal(k.c[0], k.c[1], a[0], a[1], b[0], b[1]) >= 0 ? 1 : -1
      esb.restricoes.push({ id: edIdRestricao(esb), tipo: "tangente", curvas: [criadas[v], criadas[i]], valores: [lado] })
    }
  })
  return { esboco: edLimpar(esb), novas: criadas }
}

// ---- espelhar e padrões -------------------------------------------------------------------------

function edPontosDe(esb, ids) {
  const pontos = []
  for (const id of ids) {
    const c = esb.curvas.find((k) => k.id === id)
    if (c) for (const p of c.pontos) if (!pontos.includes(p)) pontos.push(p)
  }
  return pontos
}
function edCopiarCurvas(esb, ids, mapa, inverterArcos) {
  const novas = []
  for (const id of ids) {
    const c = esb.curvas.find((k) => k.id === id)
    if (!c) continue
    const nova = { ...edCopiar(c), id: edIdCurva(esb), pontos: c.pontos.map((p) => mapa.get(p)) }
    if (c.tipo === "arco" && inverterArcos) nova.pontos = [nova.pontos[0], nova.pontos[2], nova.pontos[1]]
    esb.curvas.push(nova)
    novas.push([c, nova])
  }
  return novas
}

function edEspelhar(esboco, ids, linhaId) {
  const esb = edCopiar(esboco)
  const linha = esb.curvas.find((c) => c.id === linhaId)
  if (!linha || linha.tipo !== "linha") return { erro: "O espelho precisa ser uma linha." }
  const escolhidas = ids.filter((id) => id !== linhaId)
  if (!escolhidas.length) return { erro: "Escolha as curvas que vão ser espelhadas." }
  const [A, B] = linha.pontos.map((p) => esb.pontos[p])
  const dx = B[0] - A[0]
  const dy = B[1] - A[1]
  const l2 = dx * dx + dy * dy
  const tol = 1e-7 * edTamanho(esb)
  const mapa = new Map()
  for (const p of edPontosDe(esb, escolhidas)) {
    const [x, y] = esb.pontos[p]
    if (Math.abs(esDistSinal(x, y, A[0], A[1], B[0], B[1])) <= tol) {
      mapa.set(p, p) // no espelho: o ponto é dos dois lados
      continue
    }
    const t = ((x - A[0]) * dx + (y - A[1]) * dy) / l2
    const pe = [A[0] + t * dx, A[1] + t * dy]
    const novo = edIdPonto(esb)
    esb.pontos[novo] = [2 * pe[0] - x, 2 * pe[1] - y]
    mapa.set(p, novo)
    esb.restricoes.push({ id: edIdRestricao(esb), tipo: "simetrico", pontos: [p, novo], curvas: [linhaId] })
  }
  const novas = edCopiarCurvas(esb, escolhidas, mapa, true)
  for (const [c, nova] of novas) {
    if (c.tipo === "circulo") esb.restricoes.push({ id: edIdRestricao(esb), tipo: "igual", curvas: [c.id, nova.id] })
  }
  return { esboco: edLimpar(esb), novas: novas.map(([, n]) => n.id) }
}

function edPadraoLinear(esboco, ids, quantos, expressao, direcao, valores) {
  const esb = edCopiar(esboco)
  const n = Math.round(Number(quantos))
  if (!(n >= 2 && n <= 50)) return { erro: "A quantidade vai de 2 a 50." }
  if (!ids.length) return { erro: "Escolha as curvas que vão se repetir." }
  const passo = avaliarConta(lerConta(expressao), valores)
  if (!Number.isFinite(passo) || passo === 0) return { erro: "O passo precisa ser um número diferente de zero." }
  const deitado = direcao !== "v"
  const pontos = edPontosDe(esb, ids)
  let anteriores = new Map(pontos.map((p) => [p, p]))
  const criadas = []
  for (let k = 1; k < n; k += 1) {
    const mapa = new Map()
    for (const p of pontos) {
      const [x, y] = esb.pontos[p]
      const novo = edIdPonto(esb)
      esb.pontos[novo] = deitado ? [x + k * passo, y] : [x, y + k * passo]
      mapa.set(p, novo)
      const de = anteriores.get(p)
      esb.restricoes.push({ id: edIdRestricao(esb), tipo: deitado ? "horizontal" : "vertical", pontos: [de, novo] })
      esb.cotas.push({
        id: edIdCota(esb),
        tipo: "distancia",
        pontos: [de, novo],
        modo: deitado ? "h" : "v",
        sinal: passo >= 0 ? 1 : -1,
        expressao,
        lugar: null,
        oculta: !(k === 1 && p === pontos[0]),
      })
    }
    for (const [c, nova] of edCopiarCurvas(esb, ids, mapa, false)) {
      criadas.push(nova.id)
      if (c.tipo === "circulo") esb.restricoes.push({ id: edIdRestricao(esb), tipo: "igual", curvas: [c.id, nova.id] })
    }
    anteriores = mapa
  }
  return { esboco: edLimpar(esb), novas: criadas }
}

function edPadraoCircular(esboco, ids, centro, quantos, anguloTotal = 360) {
  const esb = edCopiar(esboco)
  const n = Math.round(Number(quantos))
  if (!(n >= 2 && n <= 72)) return { erro: "A quantidade vai de 2 a 72." }
  if (!ids.length) return { erro: "Escolha as curvas que vão se repetir." }
  if (!(centro in esb.pontos)) return { erro: "Escolha o ponto do centro." }
  const total = Number(anguloTotal)
  if (!(total > 0 && total <= 360)) return { erro: "O ângulo total vai de 0 a 360°." }
  const passo = total >= 360 - 1e-9 ? total / n : total / (n - 1)
  const [cx, cy] = esb.pontos[centro]
  const pontos = edPontosDe(esb, ids).filter((p) => p !== centro)
  const raios = new Map()
  for (const p of pontos) {
    const id = edIdCurva(esb)
    esb.curvas.push({ id, tipo: "linha", pontos: [centro, p], construcao: true })
    raios.set(p, id)
  }
  let anteriores = new Map(pontos.map((p) => [p, raios.get(p)]))
  const criadas = []
  for (let k = 1; k < n; k += 1) {
    const ang = (k * passo * Math.PI) / 180
    const mapa = new Map([[centro, centro]])
    const atuais = new Map()
    for (const p of pontos) {
      const [x, y] = esb.pontos[p]
      const dx = x - cx
      const dy = y - cy
      const novo = edIdPonto(esb)
      esb.pontos[novo] = [cx + dx * Math.cos(ang) - dy * Math.sin(ang), cy + dx * Math.sin(ang) + dy * Math.cos(ang)]
      mapa.set(p, novo)
      const raio = edIdCurva(esb)
      esb.curvas.push({ id: raio, tipo: "linha", pontos: [centro, novo], construcao: true })
      atuais.set(p, raio)
      esb.restricoes.push({ id: edIdRestricao(esb), tipo: "igual", curvas: [raios.get(p), raio] })
      const de = anteriores.get(p)
      const v = [...esb.pontos[esb.curvas.find((c) => c.id === de).pontos[1]], ...esb.pontos[novo]]
      const sinal = (v[0] - cx) * (v[3] - cy) - (v[1] - cy) * (v[2] - cx) >= 0 ? 1 : -1
      esb.cotas.push({
        id: edIdCota(esb),
        tipo: "angulo",
        curvas: [de, raio],
        modo: "d",
        sinal,
        expressao: String(Number(passo.toFixed(9))),
        lugar: null,
        oculta: !(k === 1 && p === pontos[0]),
      })
    }
    for (const [c, nova] of edCopiarCurvas(esb, ids, mapa, false)) {
      criadas.push(nova.id)
      if (c.tipo === "circulo") esb.restricoes.push({ id: edIdRestricao(esb), tipo: "igual", curvas: [c.id, nova.id] })
    }
    anteriores = atuais
  }
  return { esboco: edLimpar(esb), novas: criadas }
}

// ---- formas prontas: rasgo (oblongo) e polígono regular -------------------------------------------

// Rasgo de centro P1 a centro P2 e raio r: duas retas e dois meios círculos tangentes, de raios iguais.
function edRasgo(esboco, P1, P2, r) {
  const esb = edCopiar(esboco)
  const dx = P2[0] - P1[0]
  const dy = P2[1] - P1[1]
  const L = Math.hypot(dx, dy)
  if (!(L > 0) || !(r > 0)) return { erro: "O rasgo precisa de comprimento e de largura." }
  const n = [-dy / L, dx / L]
  const lado = (base, s) => [base[0] + s * r * n[0], base[1] + s * r * n[1]]
  const c1 = edPontoEm(esb, P1[0], P1[1])
  const c2 = edPontoEm(esb, P2[0], P2[1])
  const novo = (xy) => {
    const pid = edIdPonto(esb)
    esb.pontos[pid] = xy
    return pid
  }
  const a1 = novo(lado(P1, 1))
  const a2 = novo(lado(P2, 1))
  const b2 = novo(lado(P2, -1))
  const b1 = novo(lado(P1, -1))
  const curva = (tipo, pontos, extra = {}) => {
    const id = edIdCurva(esb)
    esb.curvas.push({ id, tipo, pontos, ...extra })
    return id
  }
  const topo = curva("linha", [a1, a2])
  const base = curva("linha", [b2, b1])
  const k2 = curva("arco", [c2, b2, a2])
  const k1 = curva("arco", [c1, a1, b1])
  curva("linha", [c1, c2], { construcao: true })
  for (const linha of [topo, base]) {
    const [p, q] = esb.curvas.find((c) => c.id === linha).pontos.map((pid) => esb.pontos[pid])
    for (const [arco, centro] of [
      [k1, P1],
      [k2, P2],
    ]) {
      const sinal = esDistSinal(centro[0], centro[1], p[0], p[1], q[0], q[1]) >= 0 ? 1 : -1
      esb.restricoes.push({ id: edIdRestricao(esb), tipo: "tangente", curvas: [linha, arco], valores: [sinal] })
    }
  }
  esb.restricoes.push({ id: edIdRestricao(esb), tipo: "igual", curvas: [k1, k2] })
  return { esboco: edLimpar(esb), novas: [topo, base, k1, k2] }
}

// Polígono regular de n lados no círculo de centro C que passa por V (o primeiro vértice).
function edPoligono(esboco, C, V, quantos) {
  const esb = edCopiar(esboco)
  const n = Math.round(Number(quantos))
  if (!(n >= 3 && n <= 24)) return { erro: "O polígono vai de 3 a 24 lados." }
  const r = Math.hypot(V[0] - C[0], V[1] - C[1])
  if (!(r > 0)) return { erro: "Afaste o vértice do centro." }
  const a0 = Math.atan2(V[1] - C[1], V[0] - C[0])
  const centro = edPontoEm(esb, C[0], C[1])
  const circulo = edIdCurva(esb)
  esb.curvas.push({ id: circulo, tipo: "circulo", pontos: [centro], raio: r, construcao: true })
  const vertices = []
  for (let k = 0; k < n; k += 1) {
    const a = a0 + (2 * Math.PI * k) / n
    const pid = edIdPonto(esb)
    esb.pontos[pid] = [C[0] + r * Math.cos(a), C[1] + r * Math.sin(a)]
    vertices.push(pid)
    esb.restricoes.push({ id: edIdRestricao(esb), tipo: "na_curva", pontos: [pid], curvas: [circulo] })
  }
  const lados = vertices.map((p, k) => {
    const id = edIdCurva(esb)
    esb.curvas.push({ id, tipo: "linha", pontos: [p, vertices[(k + 1) % n]] })
    return id
  })
  esb.restricoes.push({ id: edIdRestricao(esb), tipo: "igual", curvas: lados })
  return { esboco: edLimpar(esb), novas: lados }
}

// ---- copiar, colar, mover e girar ---------------------------------------------------------------

// O pedaço do esboço com as curvas escolhidas e o que só depende delas (restrições e cotas de dentro).
function edRecorte(esboco, ids) {
  const curvas = esboco.curvas.filter((c) => ids.includes(c.id))
  // A origem vai junto como ponto comum: a cópia de uma linha que sai da origem não fica presa nela.
  const pontos = new Set(curvas.flatMap((c) => c.pontos))
  const idsCurvas = new Set(curvas.map((c) => c.id))
  const dentro = (lista, conjunto) => (lista ?? []).every((x) => conjunto.has(x))
  const solta = (c) => (c.pontos ?? []).length + (c.curvas ?? []).length > 0
  return edCopiar({
    pontos: Object.fromEntries([...pontos].map((p) => [p, esboco.pontos[p]])),
    curvas,
    // Fixo não vai junto: a cópia presa no lugar do original nunca sairia de lá.
    restricoes: esboco.restricoes.filter(
      (r) => r.tipo !== "fixo" && solta(r) && dentro(r.curvas, idsCurvas) && dentro(r.pontos, pontos),
    ),
    cotas: esboco.cotas.filter((c) => solta(c) && dentro(c.curvas, idsCurvas) && dentro(c.pontos, pontos)),
  })
}

// Cola o recorte no esboço, cada ponto levado por `levar([x, y])`, com nomes novos.
function edColar(esboco, recorte, levar) {
  if (!recorte?.curvas?.length) return { erro: "Não há nada copiado." }
  const esb = edCopiar(esboco)
  const mapaP = new Map()
  const mapaC = new Map()
  for (const [pid, xy] of Object.entries(recorte.pontos)) {
    const novo = edIdPonto(esb)
    esb.pontos[novo] = levar(xy)
    mapaP.set(pid, novo)
  }
  const ponto = (p) => mapaP.get(p) ?? p
  for (const c of recorte.curvas) {
    const id = edIdCurva(esb)
    mapaC.set(c.id, id)
    esb.curvas.push({ ...edCopiar(c), id, pontos: c.pontos.map(ponto) })
  }
  const trocar = (x) => ({
    ...edCopiar(x),
    pontos: (x.pontos ?? []).map(ponto),
    curvas: (x.curvas ?? []).map((c) => mapaC.get(c)),
  })
  for (const r of recorte.restricoes) esb.restricoes.push({ ...trocar(r), id: edIdRestricao(esb) })
  for (const c of recorte.cotas) esb.cotas.push({ ...trocar(c), id: edIdCota(esb), lugar: c.lugar ? levar(c.lugar) : null })
  return { esboco: edLimpar(esb), novas: [...mapaC.values()] }
}

// Move e gira as curvas escolhidas: gira `graus` em volta de `centro`, depois desloca (dx, dy).
// Com `copiar`, o original fica e a cópia vai. Sem copiar, o que estiver preso por cota volta ao
// lugar: quem decide é o solver, como num CAD.
function edTransformar(esboco, ids, dx, dy, graus, centro, copiar) {
  if (!ids.length) return { erro: "Escolha as curvas que vão andar." }
  const ang = (Number(graus) * Math.PI) / 180
  const cos = Math.cos(ang)
  const sen = Math.sin(ang)
  if (![dx, dy, ang].every((v) => Number.isFinite(Number(v)))) return { erro: "Os números do movimento estão errados." }
  const levar = ([x, y]) => {
    const u = x - centro[0]
    const v = y - centro[1]
    return [centro[0] + u * cos - v * sen + Number(dx), centro[1] + u * sen + v * cos + Number(dy)]
  }
  if (copiar) {
    const colado = edColar(esboco, edRecorte(esboco, ids), levar)
    if (colado.erro) return colado
    edGirarDirecoes(colado.esboco, colado.novas, graus)
    return colado
  }
  const esb = edCopiar(esboco)
  const pontos = new Set(edPontosDe(esb, ids))
  pontos.delete("O")
  for (const p of pontos) esb.pontos[p] = levar(esb.pontos[p])
  const curvas = new Set(ids)
  for (const c of esb.cotas) {
    const vai = (c.pontos ?? []).every((p) => pontos.has(p)) && (c.curvas ?? []).every((k) => curvas.has(k))
    if (vai && c.lugar) c.lugar = levar(c.lugar)
  }
  edGirarDirecoes(esb, ids, graus)
  return { esboco: edLimpar(esb), novas: ids }
}

// Deitada e em pé depois do giro: de quarto em quarto de volta trocam entre si; noutro ângulo
// viram paralelas e perpendiculares entre as curvas que giraram (a forma fica, o giro também).
function edGirarDirecoes(esb, ids, graus) {
  const quartos = Number(graus) / 90
  const redondo = Math.abs(quartos - Math.round(quartos)) < 1e-9
  const volta = redondo ? ((Math.round(quartos) % 4) + 4) % 4 : null
  const giraram = new Set(ids)
  const pontos = new Set(edPontosDe(esb, ids))
  // As cotas na horizontal e na vertical também giram: de quarto em quarto trocam entre si (com o
  // sinal do lado novo); noutro ângulo viram cotas alinhadas, que medem o mesmo em qualquer giro.
  for (const c of esb.cotas) {
    if (c.tipo !== "distancia" || (c.modo !== "h" && c.modo !== "v")) continue
    const vai = (c.pontos ?? []).every((p) => pontos.has(p)) && (c.curvas ?? []).every((k) => giraram.has(k))
    if (!vai) continue
    if (volta === null) {
      c.modo = "d"
      c.sinal = 1
      continue
    }
    if (volta % 2 === 1) c.modo = c.modo === "h" ? "v" : "h"
    const nomes = (c.pontos ?? []).length >= 2 ? c.pontos : esb.curvas.find((k) => k.id === c.curvas[0]).pontos
    const [a, b] = nomes.slice(0, 2).map((p) => esb.pontos[p])
    const eixo = c.modo === "h" ? 0 : 1
    c.sinal = b[eixo] - a[eixo] >= 0 ? 1 : -1
  }
  if (redondo && volta % 2 === 0) return
  const grupos = { horizontal: [], vertical: [] }
  const ficam = []
  for (const r of esb.restricoes) {
    if (r.tipo !== "horizontal" && r.tipo !== "vertical") {
      ficam.push(r)
      continue
    }
    const outro = r.tipo === "horizontal" ? "vertical" : "horizontal"
    if (!(r.curvas ?? []).length) {
      const vai = (r.pontos ?? []).every((p) => pontos.has(p))
      if (!vai) ficam.push(r)
      else if (redondo) ficam.push({ ...r, tipo: outro })
      continue
    }
    const dentro = r.curvas.filter((c) => giraram.has(c))
    const fora = r.curvas.filter((c) => !giraram.has(c))
    if (fora.length) ficam.push({ ...r, curvas: fora })
    if (!dentro.length) continue
    if (redondo) ficam.push({ id: edIdRestricao({ restricoes: [...esb.restricoes, ...ficam] }), tipo: outro, curvas: dentro })
    else grupos[r.tipo].push(...dentro)
  }
  esb.restricoes = ficam
  const nova = (tipo, curvas) => esb.restricoes.push({ id: edIdRestricao(esb), tipo, curvas })
  const { horizontal: h, vertical: v } = grupos
  if (h.length > 1) nova("paralela", h)
  if (v.length > 1) nova("paralela", v)
  if (h.length && v.length) nova("perpendicular", [h[0], v[0]])
}

// O meio da caixa das curvas: o centro do giro quando ninguém escolhe outro.
function edCentroDe(esb, ids) {
  const xs = []
  const ys = []
  for (const c of esb.curvas.filter((k) => ids.includes(k.id))) {
    const g = edGeo(esb, c)
    if (g.tipo === "linha") {
      xs.push(g.a[0], g.b[0])
      ys.push(g.a[1], g.b[1])
    } else {
      xs.push(g.c[0] - g.r, g.c[0] + g.r)
      ys.push(g.c[1] - g.r, g.c[1] + g.r)
    }
  }
  if (!xs.length) return [0, 0]
  return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2]
}

// ---- unir contornos que se encostam ou se cruzam -------------------------------------------------

function edPoligonoDoLaco(esb, laco) {
  const porId = new Map(esb.curvas.map((c) => [c.id, c]))
  const pontos = []
  for (const { curva, sentido } of laco) {
    const g = edGeo(esb, porId.get(curva))
    if (g.tipo === "linha") {
      pontos.push(sentido === 1 ? g.a : g.b)
      continue
    }
    for (let i = 0; i < 48; i += 1) pontos.push(edNoParam(g, sentido === 1 ? (g.sw * i) / 48 : g.sw * (1 - i / 48)))
  }
  return pontos
}
function edDentroDoPoligono([x, y], poligono) {
  let dentro = false
  for (let i = 0, j = poligono.length - 1; i < poligono.length; j = i++) {
    const [xi, yi] = poligono[i]
    const [xj, yj] = poligono[j]
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) dentro = !dentro
  }
  return dentro
}

// Junta num só os contornos escolhidos (ou todos) que se encostam ou se cruzam, como uma união: as
// curvas são partidas onde se encontram e sai o que ficou com aço dos dois lados (de dentro) ou
// repetido (a borda comum). Contorno solto dentro de outro continua furo.
function edUnir(esboco, ids = null) {
  const esb = edCopiar(esboco)
  const escolhidas = esb.curvas.filter((c) => !c.construcao && (!ids?.length || ids.includes(c.id)))
  const { lacos, circulos } = esContornos({ ...esb, curvas: escolhidas })
  const todos = [...lacos, ...circulos.map((id) => [{ curva: id, sentido: 1 }])]
  if (todos.length < 2) return { erro: "Unir pede dois ou mais contornos fechados que se encostam ou se cruzam." }
  const tamanho = edTamanho(esb)
  const tol = 1e-7 * tamanho
  const doLaco = new Map()
  todos.forEach((laco, i) => laco.forEach(({ curva }) => doLaco.set(curva, i)))
  const noLaco = new Set(doLaco.keys())
  const usadas = escolhidas.filter((c) => noLaco.has(c.id))
  const poligonos = todos.map((laco) => edPoligonoDoLaco(esb, laco))
  const grupos = todos.map((_, i) => i)
  const raiz = (i) => (grupos[i] === i ? i : (grupos[i] = raiz(grupos[i])))
  // Os cortes de cada curva: os encontros com as outras e as pontas das outras em cima dela.
  const cortes = new Map(usadas.map((c) => [c.id, []]))
  for (const c of usadas) {
    const g = edGeo(esb, c)
    for (const outra of usadas) {
      if (outra.id === c.id) continue
      const h = edGeo(esb, outra)
      const achados = []
      for (const [x, y] of edEncontros(g, h)) {
        if (edDentro(g, edParam(g, x, y), 1e-9) && edDentro(h, edParam(h, x, y), 1e-9)) achados.push([x, y])
      }
      for (const p of outra.tipo === "circulo" ? [] : esPontas(outra)) {
        const [x, y] = esb.pontos[p]
        const t = edParam(g, x, y)
        const [px, py] = edNoParam(g, t)
        if (edDentro(g, t, 1e-9) && Math.hypot(px - x, py - y) <= tol) achados.push([x, y])
      }
      for (const [x, y] of achados) {
        cortes.get(c.id).push(edParam(g, x, y))
        const [i, j] = [raiz(doLaco.get(c.id)), raiz(doLaco.get(outra.id))]
        if (i !== j) grupos[i] = j
      }
    }
  }
  if (new Set(todos.map((_, i) => raiz(i))).size === todos.length) {
    return { erro: "Esses contornos não se encostam nem se cruzam: não há o que unir." }
  }
  // Aço num ponto: dentro de um número ímpar de grupos (cada grupo é uma peça só).
  const temAco = (p) => {
    const dentro = new Map()
    poligonos.forEach((pol, i) => {
      if (edDentroDoPoligono(p, pol)) dentro.set(raiz(i), (dentro.get(raiz(i)) ?? 0) + 1)
    })
    // Num grupo, o ponto é do grupo se está dentro de algum contorno dele que não é furo de outro
    // do mesmo grupo: na prática, os contornos de um grupo se tocam por fora, então basta um.
    return dentro.size % 2 === 1
  }
  const pedacos = []
  const inteiros = new Set()
  // Contorno que não encosta em nenhum outro (um furo solto, uma chapa à parte) fica como está.
  const membros = new Map()
  todos.forEach((_, i) => membros.set(raiz(i), (membros.get(raiz(i)) ?? 0) + 1))
  for (const c of usadas) {
    if (membros.get(raiz(doLaco.get(c.id))) === 1) {
      inteiros.add(c.id)
      continue
    }
    const g = edGeo(esb, c)
    const limite = g.tipo === "linha" ? 1 : g.sw
    let ts = cortes.get(c.id).map((t) => (g.tipo === "circulo" ? ((t % ED_DOIS_PI) + ED_DOIS_PI) % ED_DOIS_PI : t))
    if (g.tipo !== "circulo") ts = ts.filter((t) => t > 1e-9 * limite && t < limite * (1 - 1e-9))
    ts = [...new Set(ts.map((t) => Math.round(t * 1e9) / 1e9))].sort((a, b) => a - b)
    let trechos
    if (g.tipo === "circulo") {
      if (!ts.length) {
        inteiros.add(c.id)
        continue
      }
      trechos = ts.map((t, i) => [t, i + 1 < ts.length ? ts[i + 1] : ts[0] + ED_DOIS_PI])
    } else {
      const marcas = [0, ...ts, limite]
      trechos = marcas.slice(0, -1).map((t, i) => [t, marcas[i + 1]])
    }
    for (const [t0, t1] of trechos) {
      const tm = (t0 + t1) / 2
      const meio = edNoParam(g, tm)
      const antes = edNoParam(g, tm - 1e-4 * (t1 - t0))
      const depois = edNoParam(g, tm + 1e-4 * (t1 - t0))
      const d = [depois[0] - antes[0], depois[1] - antes[1]]
      const l = Math.hypot(...d) || 1
      const eps = 1e-4 * tamanho
      const n = [(-d[1] / l) * eps, (d[0] / l) * eps]
      if (temAco([meio[0] + n[0], meio[1] + n[1]]) === temAco([meio[0] - n[0], meio[1] - n[1]])) continue
      if (pedacos.some((q) => Math.hypot(q.meio[0] - meio[0], q.meio[1] - meio[1]) <= 10 * tol)) continue
      pedacos.push({ curva: c, g, t0, t1, meio })
    }
  }
  const soltos = usadas.flatMap((c) => c.pontos)
  const tirar = new Set(usadas.filter((c) => !inteiros.has(c.id)).map((c) => c.id))
  esb.curvas = esb.curvas.filter((c) => !tirar.has(c.id))
  // O que falava das curvas que saem sai antes de nascerem as novas: elas podem herdar o mesmo nome
  // (c1, c2...), e uma restrição velha passaria a valer para a curva nova errada.
  const daQueSai = (x) => (x.curvas ?? []).some((c) => tirar.has(c))
  esb.restricoes = esb.restricoes.filter((r) => !daQueSai(r))
  esb.cotas = esb.cotas.filter((c) => !daQueSai(c))
  // Cada lugar ganha um ponto só: o da ponta que já estava ali (a origem só quando já era ela) ou
  // um novo. Os outros pontos do mesmo lugar passam para ele nas restrições e nas cotas.
  const lugares = []
  const trocados = new Map()
  const pontoDaUniao = (xy, preferido) => {
    const achado = lugares.find(([q]) => Math.hypot(q[0] - xy[0], q[1] - xy[1]) <= 10 * tol)
    if (achado) {
      if (preferido && preferido !== achado[1]) trocados.set(preferido, achado[1])
      return achado[1]
    }
    let pid = preferido
    if (!pid) {
      pid = soltos.find((p) => p !== "O" && Math.hypot(esb.pontos[p][0] - xy[0], esb.pontos[p][1] - xy[1]) <= 10 * tol)
    }
    if (!pid) {
      pid = edIdPonto(esb)
      esb.pontos[pid] = [...xy]
    }
    lugares.push([xy, pid])
    return pid
  }
  const pontaDe = (p, t) => {
    const [i, f] = p.g.tipo === "linha" ? p.curva.pontos : p.curva.tipo === "arco" ? p.curva.pontos.slice(1) : [null, null]
    const limite = p.g.tipo === "linha" ? 1 : p.g.sw
    if (Math.abs(t) <= 1e-9 * limite) return i
    if (Math.abs(t - limite) <= 1e-9 * limite) return f
    return null
  }
  const novas = []
  for (const p of pedacos) {
    const pa = pontoDaUniao(edNoParam(p.g, p.t0), pontaDe(p, p.t0))
    const pb = pontoDaUniao(edNoParam(p.g, p.t1), pontaDe(p, p.t1))
    if (pa === pb) continue
    const id = edIdCurva(esb)
    if (p.g.tipo === "linha") esb.curvas.push({ id, tipo: "linha", pontos: [pa, pb] })
    else esb.curvas.push({ id, tipo: "arco", pontos: [p.curva.pontos[0], pa, pb] })
    novas.push({ id, de: p.curva.id })
  }
  // As retas que eram deitadas ou em pé continuam assim.
  for (const r of esboco.restricoes) {
    if (r.tipo !== "horizontal" && r.tipo !== "vertical") continue
    const filhas = novas.filter((k) => (r.curvas ?? []).includes(k.de)).map((k) => k.id)
    if (filhas.length) esb.restricoes.push({ id: edIdRestricao(esb), tipo: r.tipo, curvas: filhas })
  }
  for (const x of [...esb.restricoes, ...esb.cotas]) {
    if (x.pontos) x.pontos = x.pontos.map((p) => trocados.get(p) ?? p)
  }
  esb.restricoes = esb.restricoes.filter((r) => r.tipo !== "coincidente" || new Set(r.pontos).size > 1)
  return { esboco: edLimpar(esb, soltos), novas: novas.map((k) => k.id) }
}
