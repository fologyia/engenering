// Prancheta da rede de tubos: a planta da rede, em metros, com o Y para cima.
// O desenho manda os nós e os tubos ao Python; o Python devolve as marcas do resultado
// (vazão, velocidade e pressão) e as mudanças feitas no painel ao lado ou nas tabelas.

const ESTADOS = new WeakMap()
const NS = "http://www.w3.org/2000/svg"
const GRADES = [0.5, 1, 2, 5, 10, 20, 50, 100]
const RAIO_NO = 9 // px
const PERTO = 12 // px: clique a esta distância pega o nó ou o tubo
const LETRAS = "ABCDEFGHIJKLMNOPQSTUVWXYZ" // sem o R, que é dos reservatórios
const DICAS = {
  mover: "Clique num nó ou num tubo para ver e mudar os dados ao lado. Arraste um nó para mover; arraste o fundo para andar.",
  reservatorio: "Clique onde fica o reservatório ou a caixa d'água.",
  no: "Clique onde a água é consumida. Em cima de um tubo, o nó divide o tubo em dois.",
  tubo: "Clique no nó de onde o tubo sai e no nó onde ele chega. No vazio, o nó nasce ali. Esc termina.",
}

// ---------------------------------------------------------------- contas puras (testadas no Node)

function copiar(v) {
  return JSON.parse(JSON.stringify(v))
}

// O próximo nome livre: R1, R2… nos reservatórios; A, B, …, Z, depois N27…; 1, 2… nos tubos.
function proximoNome(usados, tipo) {
  const ja = new Set(usados)
  if (tipo === "reservatorio") {
    for (let i = 1; ; i++) if (!ja.has(`R${i}`)) return `R${i}`
  }
  if (tipo === "consumo") {
    for (const letra of LETRAS) if (!ja.has(letra)) return letra
    for (let i = 27; ; i++) if (!ja.has(`N${i}`)) return `N${i}`
  }
  for (let i = 1; ; i++) if (!ja.has(String(i))) return String(i)
}

function proximoId(lista, prefixo) {
  let maior = 0
  for (const item of lista) {
    const n = Number(String(item.id).slice(prefixo.length))
    if (String(item.id).startsWith(prefixo) && Number.isFinite(n)) maior = Math.max(maior, n)
  }
  return `${prefixo}${maior + 1}`
}

// Distância (em unidades do desenho) de p ao segmento a–b, e onde ele cai no segmento (0 a 1).
function distanciaAoSegmento(p, a, b) {
  const dx = b[0] - a[0]
  const dy = b[1] - a[1]
  const l2 = dx * dx + dy * dy
  const t = l2 > 0 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2)) : 0
  const x = a[0] + t * dx
  const y = a[1] + t * dy
  return { d: Math.hypot(p[0] - x, p[1] - y), t }
}

function noPorId(dados, id) {
  return dados.nos.find((n) => n.id === id)
}

function comprimentoDesenhado(dados, trecho) {
  const a = noPorId(dados, trecho.de)
  const b = noPorId(dados, trecho.para)
  return a && b ? Math.hypot(b.x - a.x, b.y - a.y) : 0
}

// Um nó novo de consumo no meio do tubo: o tubo vira dois, cada um com os dados do original.
// O comprimento real informado, se havia, se divide na mesma proporção do desenho.
function dividirTrecho(dados, idTrecho, ponto) {
  const novo = copiar(dados)
  const i = novo.trechos.findIndex((t) => t.id === idTrecho)
  if (i < 0) return { dados: novo, no: null }
  const t = novo.trechos[i]
  const a = noPorId(novo, t.de)
  const b = noPorId(novo, t.para)
  const { t: frac } = distanciaAoSegmento(ponto, [a.x, a.y], [b.x, b.y])
  const no = {
    id: proximoId(novo.nos, "n"),
    nome: proximoNome(novo.nos.map((n) => n.nome), "consumo"),
    tipo: "consumo",
    x: a.x + frac * (b.x - a.x),
    y: a.y + frac * (b.y - a.y),
    cota: (Number(a.cota) || 0) + frac * ((Number(b.cota) || 0) - (Number(a.cota) || 0)),
    nivel: null,
    retirada: 0,
  }
  novo.nos.push(no)
  const segundo = { ...copiar(t), id: proximoId(novo.trechos, "t"), de: no.id, para: t.para }
  segundo.nome = proximoNome(novo.trechos.map((x) => x.nome), "tubo")
  if (t.comprimento != null) {
    segundo.comprimento = t.comprimento * (1 - frac)
    t.comprimento = t.comprimento * frac
  }
  segundo.bomba = 0 // a bomba fica num só dos dois
  t.para = no.id
  novo.trechos.splice(i + 1, 0, segundo)
  return { dados: novo, no: no.id }
}

// Apagar um nó leva junto os tubos dele; apagar um tubo deixa os nós.
function apagar(dados, sel) {
  const novo = copiar(dados)
  if (!sel) return novo
  if (sel.tipo === "no") {
    novo.nos = novo.nos.filter((n) => n.id !== sel.id)
    novo.trechos = novo.trechos.filter((t) => t.de !== sel.id && t.para !== sel.id)
  } else if (sel.tipo === "trecho") {
    novo.trechos = novo.trechos.filter((t) => t.id !== sel.id)
  }
  return novo
}

function jaLigados(dados, a, b) {
  return dados.trechos.some((t) => (t.de === a && t.para === b) || (t.de === b && t.para === a))
}

function grudar(v, passo) {
  return Math.round(v / passo) * passo
}

function texto(v) {
  const r = Math.round(v * 100) / 100
  return String(r).replace(".", ",")
}

// ---------------------------------------------------------------- a prancheta

function criar(raiz) {
  const svg = raiz.querySelector("svg")
  const infoXY = raiz.querySelector('[data-i="xy"]')
  const infoDica = raiz.querySelector('[data-i="dica"]')
  const seletorGrade = raiz.querySelector('[data-c="grade"]')
  const e = {
    enviar: null,
    dados: { nos: [], trechos: [] },
    versao: -1,
    verAjuste: null,
    marcas: null,
    vista: { x: 0, y: 0, esc: 1 }, // canto de cima à esquerda (m) e px por metro
    ferramenta: "mover",
    sel: null,
    pendente: null, // o nó de onde sai o tubo que está sendo desenhado
    cursor: null, // m
    gesto: null,
    historia: [],
    futuro: [],
    grade: 1,
    selEnviada: "null",
  }

  const largura = () => svg.clientWidth || 800
  const altura = () => svg.clientHeight || 470
  const tela = (x, y) => [(x - e.vista.x) * e.vista.esc, (e.vista.y - y) * e.vista.esc]
  const metro = (px, py) => [e.vista.x + px / e.vista.esc, e.vista.y - py / e.vista.esc]

  function el(nome, atributos = {}, pai = svg) {
    const no = document.createElementNS(NS, nome)
    for (const [k, v] of Object.entries(atributos)) no.setAttribute(k, v)
    pai.appendChild(no)
    return no
  }

  function ponteiro(ev) {
    const r = svg.getBoundingClientRect()
    return [ev.clientX - r.left, ev.clientY - r.top]
  }

  // ---- o que está debaixo do cursor
  function noEm(px, py) {
    let melhor = null
    let menor = PERTO
    for (const n of e.dados.nos) {
      const [x, y] = tela(n.x, n.y)
      const d = Math.hypot(px - x, py - y)
      if (d <= menor) {
        menor = d
        melhor = n
      }
    }
    return melhor
  }
  function trechoEm(px, py) {
    let melhor = null
    let menor = PERTO * 0.7
    for (const t of e.dados.trechos) {
      const a = noPorId(e.dados, t.de)
      const b = noPorId(e.dados, t.para)
      if (!a || !b) continue
      const { d } = distanciaAoSegmento([px, py], tela(a.x, a.y), tela(b.x, b.y))
      if (d <= menor) {
        menor = d
        melhor = t
      }
    }
    return melhor
  }
  function pontoGrudado(px, py) {
    const [x, y] = metro(px, py)
    return [grudar(x, e.grade), grudar(y, e.grade)]
  }

  // ---- história local: Ctrl+Z e Ctrl+Y
  function guardar() {
    e.historia.push(copiar(e.dados))
    if (e.historia.length > 100) e.historia.shift()
    e.futuro = []
  }
  function mudar(novos) {
    guardar()
    e.dados = novos
    enviar()
  }
  function enviar() {
    e.versao += 1
    e.enviar?.("edicao", { dados: copiar(e.dados), versao: e.versao })
    desenhar()
  }
  function selecionar(sel) {
    e.sel = sel
    const texto_ = JSON.stringify(sel)
    if (texto_ !== e.selEnviada) {
      e.selEnviada = texto_
      e.enviar?.("selecao", sel ? { ...sel, n: Date.now() } : null)
    }
    desenhar()
  }

  // ---- criar
  function novoNo(tipo, x, y) {
    const usados = e.dados.nos.map((n) => n.nome)
    return {
      id: proximoId(e.dados.nos, "n"),
      nome: proximoNome(usados, tipo),
      tipo,
      x,
      y,
      cota: 0,
      nivel: tipo === "reservatorio" ? 20 : null,
      retirada: tipo === "reservatorio" ? null : 0,
    }
  }
  function novoTrecho(de, para) {
    // O tubo novo copia o diâmetro e o material do último desenhado.
    const ultimo = e.dados.trechos[e.dados.trechos.length - 1]
    return {
      id: proximoId(e.dados.trechos, "t"),
      nome: proximoNome(e.dados.trechos.map((t) => t.nome), "tubo"),
      de,
      para,
      comprimento: null,
      diametro: ultimo?.diametro ?? 100,
      material: ultimo?.material ?? "Aço comercial",
      rugosidade: ultimo?.rugosidade ?? null,
      k: 0,
      bomba: 0,
    }
  }

  function aoClicar(px, py, ev) {
    const f = e.ferramenta
    const no = noEm(px, py)
    if (f === "mover") {
      if (no) return selecionar({ tipo: "no", id: no.id })
      const t = trechoEm(px, py)
      return selecionar(t ? { tipo: "trecho", id: t.id } : null)
    }
    if (f === "reservatorio" || f === "no") {
      if (no) return selecionar({ tipo: "no", id: no.id })
      const t = f === "no" ? trechoEm(px, py) : null
      if (t) {
        const { dados, no: id } = dividirTrecho(e.dados, t.id, metro(px, py))
        mudar(dados)
        return selecionar({ tipo: "no", id })
      }
      const [x, y] = pontoGrudado(px, py)
      const novo = novoNo(f === "no" ? "consumo" : "reservatorio", x, y)
      const dados = copiar(e.dados)
      dados.nos.push(novo)
      mudar(dados)
      return selecionar({ tipo: "no", id: novo.id })
    }
    if (f === "tubo") {
      const dados = copiar(e.dados)
      let alvo = no
      if (!alvo) {
        const [x, y] = pontoGrudado(px, py)
        alvo = novoNo("consumo", x, y)
        dados.nos.push(alvo)
      }
      if (e.pendente && e.pendente !== alvo.id && !jaLigados(dados, e.pendente, alvo.id)) {
        const antes = e.dados
        e.dados = dados // o nome e o id do tubo novo olham para os dados já com o nó
        const tubo = novoTrecho(e.pendente, alvo.id)
        e.dados = antes
        dados.trechos.push(tubo)
        e.pendente = alvo.id
        mudar(dados)
        return selecionar({ tipo: "trecho", id: tubo.id })
      }
      e.pendente = alvo.id
      if (dados.nos.length !== e.dados.nos.length) mudar(dados)
      return selecionar({ tipo: "no", id: alvo.id })
    }
    if (ev) ev.preventDefault()
  }

  // ---- gestos
  svg.addEventListener("pointerdown", (ev) => {
    svg.focus({ preventScroll: true })
    const [px, py] = ponteiro(ev)
    svg.setPointerCapture(ev.pointerId)
    const no = e.ferramenta === "mover" ? noEm(px, py) : null
    if (ev.button === 1 || (e.ferramenta === "mover" && !no && !trechoEm(px, py))) {
      e.gesto = { tipo: "andar", px, py, x: e.vista.x, y: e.vista.y, moveu: false }
      return
    }
    if (no) {
      e.gesto = { tipo: "arrastar", id: no.id, px, py, x: no.x, y: no.y, moveu: false }
      selecionar({ tipo: "no", id: no.id })
      return
    }
    e.gesto = { tipo: "clique", px, py }
  })
  svg.addEventListener("pointermove", (ev) => {
    const [px, py] = ponteiro(ev)
    e.cursor = metro(px, py)
    const [gx, gy] = pontoGrudado(px, py)
    infoXY.textContent = `x = ${texto(gx)} m · y = ${texto(gy)} m`
    const g = e.gesto
    if (g?.tipo === "andar") {
      if (Math.hypot(px - g.px, py - g.py) > 3) g.moveu = true
      e.vista.x = g.x - (px - g.px) / e.vista.esc
      e.vista.y = g.y + (py - g.py) / e.vista.esc
      svg.classList.add("andando")
    } else if (g?.tipo === "arrastar") {
      if (!g.moveu && Math.hypot(px - g.px, py - g.py) < 4) return
      if (!g.moveu) guardar()
      g.moveu = true
      const no = noPorId(e.dados, g.id)
      if (no) {
        no.x = gx
        no.y = gy
      }
    }
    desenhar()
  })
  svg.addEventListener("pointerup", (ev) => {
    const [px, py] = ponteiro(ev)
    const g = e.gesto
    e.gesto = null
    svg.classList.remove("andando")
    if (!g) return
    if (g.tipo === "arrastar" && g.moveu) enviar()
    else if (g.tipo === "andar" && !g.moveu) selecionar(null)
    else if (g.tipo === "clique") aoClicar(px, py, ev)
  })
  svg.addEventListener("dblclick", () => {
    e.pendente = null
    desenhar()
  })
  svg.addEventListener("contextmenu", (ev) => {
    ev.preventDefault()
    e.pendente = null
    desenhar()
  })
  svg.addEventListener(
    "wheel",
    (ev) => {
      ev.preventDefault()
      const [px, py] = ponteiro(ev)
      zoom(ev.deltaY < 0 ? 1.2 : 1 / 1.2, px, py)
    },
    { passive: false },
  )
  svg.addEventListener("keydown", (ev) => {
    const ctrl = ev.ctrlKey || ev.metaKey
    if (ctrl && ev.key.toLowerCase() === "z") {
      ev.preventDefault()
      return acoes.desfazer()
    }
    if (ctrl && ev.key.toLowerCase() === "y") {
      ev.preventDefault()
      return acoes.refazer()
    }
    if (ev.key === "Delete" || ev.key === "Backspace") {
      ev.preventDefault()
      return acoes.apagar()
    }
    if (ev.key === "Escape") {
      e.pendente = null
      if (e.ferramenta === "mover") selecionar(null)
      else trocarFerramenta("mover")
      return
    }
    const atalho = { v: "mover", r: "reservatorio", n: "no", t: "tubo" }[ev.key.toLowerCase()]
    if (atalho && !ctrl) trocarFerramenta(atalho)
  })

  function zoom(fator, px = largura() / 2, py = altura() / 2) {
    const [x, y] = metro(px, py)
    e.vista.esc = Math.max(0.01, Math.min(2000, e.vista.esc * fator))
    e.vista.x = x - px / e.vista.esc
    e.vista.y = y + py / e.vista.esc
    desenhar()
  }
  function ajustarVista() {
    const nos = e.dados.nos
    if (!nos.length) {
      e.vista = { x: -15, y: 25, esc: largura() / 60 }
      return
    }
    const xs = nos.map((n) => n.x)
    const ys = nos.map((n) => n.y)
    const w = Math.max(Math.max(...xs) - Math.min(...xs), 1)
    const h = Math.max(Math.max(...ys) - Math.min(...ys), 1)
    const esc = Math.min((largura() - 320) / w, (altura() - 140) / h)
    e.vista.esc = Math.max(0.01, Math.min(esc, 200))
    e.vista.x = (Math.min(...xs) + Math.max(...xs)) / 2 - largura() / 2 / e.vista.esc
    e.vista.y = (Math.min(...ys) + Math.max(...ys)) / 2 + altura() / 2 / e.vista.esc
  }
  // A grade sugerida: uns 40 px entre linhas na vista de agora.
  function gradeSugerida() {
    const alvo = 40 / e.vista.esc
    return GRADES.find((g) => g >= alvo) ?? GRADES[GRADES.length - 1]
  }

  const acoes = {
    apagar() {
      if (!e.sel) return
      mudar(apagar(e.dados, e.sel))
      selecionar(null)
    },
    desfazer() {
      if (!e.historia.length) return
      e.futuro.push(copiar(e.dados))
      e.dados = e.historia.pop()
      e.pendente = null
      enviar()
    },
    refazer() {
      if (!e.futuro.length) return
      e.historia.push(copiar(e.dados))
      e.dados = e.futuro.pop()
      enviar()
    },
    maisLonge: () => zoom(1 / 1.3),
    maisPerto: () => zoom(1.3),
    ajustar() {
      ajustarVista()
      desenhar()
    },
  }
  raiz.querySelectorAll("[data-a]").forEach((b) => b.addEventListener("click", () => acoes[b.dataset.a]()))
  raiz.querySelectorAll("[data-f]").forEach((b) =>
    b.addEventListener("click", () => {
      trocarFerramenta(b.dataset.f)
      svg.focus({ preventScroll: true })
    }),
  )
  function trocarFerramenta(f) {
    e.ferramenta = f
    e.pendente = null
    raiz.querySelectorAll("[data-f]").forEach((b) => b.classList.toggle("ativo", b.dataset.f === f))
    svg.setAttribute("class", `f-${f}`)
    infoDica.textContent = DICAS[f]
    desenhar()
  }
  seletorGrade.replaceChildren(
    ...GRADES.map((g) => {
      const o = document.createElement("option")
      o.value = String(g)
      o.textContent = `${texto(g)} m`
      return o
    }),
  )
  seletorGrade.addEventListener("change", () => {
    e.grade = Number(seletorGrade.value)
    desenhar()
  })

  // ---- desenho
  function desenhar() {
    while (svg.firstChild) svg.removeChild(svg.firstChild)
    const w = largura()
    const h = altura()
    el("rect", { x: 0, y: 0, width: w, height: h, fill: "#ffffff" })
    // grade
    const passo = e.grade
    if (passo * e.vista.esc >= 8) {
      const [x0, y1] = metro(0, 0)
      const [x1, y0] = metro(w, h)
      for (let x = Math.ceil(x0 / passo) * passo; x <= x1; x += passo) {
        const [px] = tela(x, 0)
        const forte = Math.abs(grudar(x, passo * 5) - x) < passo / 100
        el("line", { x1: px, y1: 0, x2: px, y2: h, class: forte ? "grelha forte" : "grelha" })
      }
      for (let y = Math.ceil(y0 / passo) * passo; y <= y1; y += passo) {
        const [, py] = tela(0, y)
        const forte = Math.abs(grudar(y, passo * 5) - y) < passo / 100
        el("line", { x1: 0, y1: py, x2: w, y2: py, class: forte ? "grelha forte" : "grelha" })
      }
    }
    const marcas = e.marcas ?? { nos: {}, trechos: {} }
    // tubos
    for (const t of e.dados.trechos) {
      const a = noPorId(e.dados, t.de)
      const b = noPorId(e.dados, t.para)
      if (!a || !b) continue
      let [x1, y1] = tela(a.x, a.y)
      let [x2, y2] = tela(b.x, b.y)
      const m = marcas.trechos?.[t.id]
      const sel = e.sel?.tipo === "trecho" && e.sel.id === t.id
      const espessura = 2 + 4 * Math.min((Number(t.diametro) || 100) / 300, 1)
      const classe = `tubo${m?.ruim ? " ruim" : ""}${sel ? " sel" : ""}`
      el("line", { x1, y1, x2, y2, class: classe, "stroke-width": espessura })
      if (m?.sentido === -1) [x1, y1, x2, y2] = [x2, y2, x1, y1]
      const mx = (x1 + x2) / 2
      const my = (y1 + y2) / 2
      const l = Math.hypot(x2 - x1, y2 - y1) || 1
      const ux = (x2 - x1) / l
      const uy = (y2 - y1) / l
      if (m) {
        // a seta no sentido da água
        const p = `${mx + 7 * ux},${my + 7 * uy} ${mx - 6 * ux - 5 * uy},${my - 6 * uy + 5 * ux} ${mx - 6 * ux + 5 * uy},${my - 6 * uy - 5 * ux}`
        el("polygon", { points: p, class: `seta${m.ruim ? " ruim" : ""}` })
      }
      let nx = -uy
      let ny = ux
      if (Math.abs(uy) < 0.5 ? ny < 0 : nx < 0) {
        nx = -nx
        ny = -ny
      }
      const ancora = nx > 0.3 ? "start" : nx < -0.3 ? "end" : "middle"
      const rotulo = m ? `${t.nome}: ${m.texto}` : `${t.nome} · ${texto(Number(t.diametro) || 0)} mm`
      const txt = el("text", {
        x: mx + 10 * nx,
        y: my + 16 * ny + 4,
        "text-anchor": ancora,
        class: `rot${m?.ruim ? " ruim" : ""}`,
      })
      txt.textContent = rotulo
      el("line", { x1, y1, x2, y2, class: "alvo" })
    }
    // o tubo que está nascendo
    if (e.ferramenta === "tubo" && e.pendente && e.cursor) {
      const a = noPorId(e.dados, e.pendente)
      if (a) {
        const [x1, y1] = tela(a.x, a.y)
        const [gx, gy] = [grudar(e.cursor[0], e.grade), grudar(e.cursor[1], e.grade)]
        const [x2, y2] = tela(gx, gy)
        el("line", { x1, y1, x2, y2, class: "previa" })
      }
    }
    // nós
    for (const n of e.dados.nos) {
      const [x, y] = tela(n.x, n.y)
      const m = marcas.nos?.[n.id]
      const sel = e.sel?.tipo === "no" && e.sel.id === n.id
      if (n.tipo === "reservatorio") {
        el("rect", { x: x - 15, y: y - 12, width: 30, height: 24, rx: 3, class: `res${sel ? " sel" : ""}` })
        el("rect", { x: x - 13, y: y - 2, width: 26, height: 12, class: "agua" })
      } else {
        el("circle", { cx: x, cy: y, r: RAIO_NO, class: `no${m?.ruim ? " ruim" : ""}${sel ? " sel" : ""}` })
      }
      const nome = el("text", { x, y: y - 17, "text-anchor": "middle", class: `rot nome${m?.ruim ? " ruim" : ""}` })
      nome.textContent = m ? `${n.nome} · ${m.texto}` : n.nome
    }
    // onde o próximo ponto vai cair
    if (e.ferramenta !== "mover" && e.cursor && !e.gesto) {
      const [gx, gy] = [grudar(e.cursor[0], e.grade), grudar(e.cursor[1], e.grade)]
      const [x, y] = tela(gx, gy)
      el("circle", { cx: x, cy: y, r: 6, class: "fantasma" })
    }
  }

  e.receber = (dados) => {
    const novos = dados.dados ?? e.dados
    if (dados.versao >= e.versao) {
      if (JSON.stringify(novos) !== JSON.stringify(e.dados)) {
        if (e.versao >= 0) guardar()
        e.dados = copiar(novos)
        if (e.sel?.tipo === "no" && !noPorId(e.dados, e.sel.id)) e.sel = null
        if (e.sel?.tipo === "trecho" && !e.dados.trechos.some((t) => t.id === e.sel.id)) e.sel = null
      }
      e.versao = dados.versao
    }
    e.marcas = dados.marcas ?? null
    if (e.verAjuste !== dados.ajustar) {
      e.verAjuste = dados.ajustar
      // Sem tamanho ainda, a escala sairia quase zero: enquadra quando o painel tiver medida.
      if (svg.clientWidth) enquadrar()
      else e.enquadrarAoMedir = true
    }
    desenhar()
  }

  function enquadrar() {
    ajustarVista()
    e.grade = gradeSugerida()
    seletorGrade.value = String(e.grade)
  }

  trocarFerramenta("mover")
  new ResizeObserver(() => {
    if (e.enquadrarAoMedir && svg.clientWidth) {
      e.enquadrarAoMedir = false
      enquadrar()
    }
    desenhar()
  }).observe(svg)
  return e
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  let estado = ESTADOS.get(parentElement)
  if (!estado) {
    estado = criar(parentElement)
    ESTADOS.set(parentElement, estado)
  }
  estado.enviar = setTriggerValue
  estado.receber(data ?? {})
}
