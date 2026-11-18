// Prancheta do circuito fechado: tubos desenhados e as peças em cima deles (bomba, fonte de calor,
// dry cooler, chiller, válvula, filtro, tanque) e o vaso de expansão num ponto. A planta vai em
// metros, com o Y para cima. O desenho vai para o Python; o Python devolve as marcas do resultado
// (vazão, sentido, temperatura e pressão) e as mudanças feitas no painel ao lado ou nas tabelas.

const ESTADOS = new WeakMap()
const NS = "http://www.w3.org/2000/svg"
const GRADES = [0.25, 0.5, 1, 2, 5, 10, 20, 50]
const RAIO_NO = 7 // px
const PERTO = 12 // px
const LETRAS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
const PECAS = ["bomba", "fonte", "dry_cooler", "chiller", "valvula", "filtro", "tanque"]
const NOMES = {
  tubo: "Tubo",
  bomba: "Bomba",
  fonte: "Fonte de calor",
  dry_cooler: "Dry cooler",
  chiller: "Chiller",
  valvula: "Válvula",
  filtro: "Filtro",
  tanque: "Tanque",
}
//: Dados de partida de cada peça nova (valores de exemplo: o painel ao lado troca pelos do catálogo).
const PADROES = {
  bomba: { h0_m: 30, qmax_m3h: 40, rendimento: 0.6, npsh_requerido_m: 3, ligada: true },
  fonte: { potencia_kW: 50, massa_kg: 200, calor_especifico_massa: 500, volume_L: 15, dp_kPa: 25, q_nominal_m3h: 8, t_maxima: 45 },
  dry_cooler: {
    q_catalogo_kW: 80, t_entrada_catalogo: 40, t_ar_catalogo: 30, vazao_liquido_catalogo_m3h: 12,
    vazao_ar_catalogo_m3h: 36000, potencia_ventilador_kW: 2.2, volume_L: 40, dp_kPa: 35, q_nominal_m3h: 12,
    controle: "sempre", t_ajuste: 30,
  },
  chiller: { capacidade_kW: 50, t_ajuste: 12, cop: 3.2, volume_L: 50, dp_kPa: 40, q_nominal_m3h: 10 },
  valvula: { k_local: 5 },
  filtro: { dp_kPa: 8, q_nominal_m3h: 12, volume_L: 5 },
  tanque: { volume_L: 500, ua_W_K: 0 },
}
const DICAS = {
  mover: "Clique num ponto, num tubo ou numa peça para ver e mudar os dados ao lado. Arraste um ponto para mover; arraste o fundo para andar.",
  tubo: "Clique num ponto e no seguinte; no vazio, o ponto nasce ali. Volte ao primeiro ponto para fechar o circuito. Esc termina.",
  vaso: "Clique num ponto (ou em cima de um tubo) para pôr o vaso de expansão ali. Clique de novo para tirar.",
  peca: "Clique em cima de um tubo para pôr a peça ali: o tubo se divide e a peça fica no meio.",
}

// ---------------------------------------------------------------- contas puras (testadas no Node)

function copiar(v) {
  return JSON.parse(JSON.stringify(v))
}

function proximoId(lista, prefixo) {
  let maior = 0
  for (const item of lista) {
    const n = Number(String(item.id).slice(prefixo.length))
    if (String(item.id).startsWith(prefixo) && Number.isFinite(n)) maior = Math.max(maior, n)
  }
  return `${prefixo}${maior + 1}`
}

// Nomes: pontos A, B, …; tubos 1, 2, …; peças "Bomba 1", "Dry cooler 2"…
function proximoNome(usados, tipo) {
  const ja = new Set(usados)
  if (tipo === "no") {
    for (const letra of LETRAS) if (!ja.has(letra)) return letra
    for (let i = 27; ; i++) if (!ja.has(`P${i}`)) return `P${i}`
  }
  if (tipo === "tubo") {
    for (let i = 1; ; i++) if (!ja.has(String(i))) return String(i)
  }
  for (let i = 1; ; i++) if (!ja.has(`${NOMES[tipo]} ${i}`)) return `${NOMES[tipo]} ${i}`
}

function distanciaAoSegmento(p, a, b) {
  const dx = b[0] - a[0]
  const dy = b[1] - a[1]
  const l2 = dx * dx + dy * dy
  const t = l2 > 0 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2)) : 0
  return { d: Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy)), t }
}

function noPorId(dados, id) {
  return dados.nos.find((n) => n.id === id)
}

function comprimentoDesenhado(dados, trecho) {
  const a = noPorId(dados, trecho.de)
  const b = noPorId(dados, trecho.para)
  return a && b ? Math.hypot(b.x - a.x, b.y - a.y) : 0
}

function novoPonto(dados, x, y, cota) {
  return { id: proximoId(dados.nos, "n"), nome: proximoNome(dados.nos.map((n) => n.nome), "no"), x, y, cota: cota ?? 0 }
}

// Divide o tubo num ponto novo (fração 0 a 1 do de para o para); o comprimento real, se informado,
// se divide na mesma proporção. Devolve os dados novos e os ids do ponto e dos dois tubos.
function dividirTubo(dados, idTrecho, frac) {
  const novo = copiar(dados)
  const i = novo.trechos.findIndex((t) => t.id === idTrecho)
  if (i < 0) return { dados: novo, no: null }
  const t = novo.trechos[i]
  const a = noPorId(novo, t.de)
  const b = noPorId(novo, t.para)
  const f = Math.max(0, Math.min(1, frac))
  const cota = (Number(a.cota) || 0) + f * ((Number(b.cota) || 0) - (Number(a.cota) || 0))
  const no = novoPonto(novo, a.x + f * (b.x - a.x), a.y + f * (b.y - a.y), cota)
  novo.nos.push(no)
  const segundo = { ...copiar(t), id: proximoId(novo.trechos, "t"), de: no.id, para: t.para }
  segundo.nome = t.tipo === "tubo" ? proximoNome(novo.trechos.map((x) => x.nome), "tubo") : t.nome
  if (t.comprimento != null && t.comprimento !== "") {
    segundo.comprimento = t.comprimento * (1 - f)
    t.comprimento = t.comprimento * f
  }
  t.para = no.id
  novo.trechos.splice(i + 1, 0, segundo)
  return { dados: novo, no: no.id, antes: t.id, depois: segundo.id }
}

// Põe uma peça em cima do tubo, no ponto clicado: o tubo vira tubo – peça – tubo. A peça ocupa
// "tamanho" metros do desenho (ou o tubo inteiro, se ele for curto) e herda o diâmetro do tubo.
function inserirPeca(dados, idTrecho, ponto, tipo, tamanho) {
  const t = dados.trechos.find((x) => x.id === idTrecho)
  if (!t || t.tipo !== "tubo") return { dados: copiar(dados), peca: null }
  const a = noPorId(dados, t.de)
  const b = noPorId(dados, t.para)
  const l = Math.hypot(b.x - a.x, b.y - a.y)
  const nome = proximoNome(dados.trechos.map((x) => x.nome), tipo)
  const dadosDaPeca = { ...copiar(PADROES[tipo] ?? {}), tipo, nome, diametro_mm: t.diametro_mm ?? 52.5 }
  if (l <= tamanho * 1.5) {
    // tubo curto: ele mesmo vira a peça
    const novo = copiar(dados)
    const alvo = novo.trechos.find((x) => x.id === idTrecho)
    const id = alvo.id
    const de = alvo.de
    const para = alvo.para
    for (const k of Object.keys(alvo)) delete alvo[k]
    Object.assign(alvo, { id, de, para, ...dadosDaPeca })
    return { dados: novo, peca: id }
  }
  const { t: frac } = distanciaAoSegmento(ponto, [a.x, a.y], [b.x, b.y])
  const meio = Math.max(tamanho / l, Math.min(1 - tamanho / l, frac))
  const f1 = meio - tamanho / (2 * l)
  const f2 = meio + tamanho / (2 * l)
  const primeiro = dividirTubo(dados, idTrecho, f1)
  // o segundo corte, no tubo que sobrou depois do primeiro corte
  const restante = (f2 - f1) / (1 - f1)
  const segundo = dividirTubo(primeiro.dados, primeiro.depois, restante)
  const novo = segundo.dados
  const peca = novo.trechos.find((x) => x.id === segundo.antes)
  const id = peca.id
  const de = peca.de
  const para = peca.para
  for (const k of Object.keys(peca)) delete peca[k]
  Object.assign(peca, { id, de, para, ...dadosDaPeca })
  return { dados: novo, peca: id }
}

// Apagar: o ponto leva junto o que chega nele; o tubo some; a peça vira tubo de novo (o circuito
// continua fechado).
function apagar(dados, sel) {
  const novo = copiar(dados)
  if (!sel) return novo
  if (sel.tipo === "no") {
    novo.nos = novo.nos.filter((n) => n.id !== sel.id)
    novo.trechos = novo.trechos.filter((t) => t.de !== sel.id && t.para !== sel.id)
  } else if (sel.tipo === "trecho") {
    const t = novo.trechos.find((x) => x.id === sel.id)
    if (t && t.tipo !== "tubo") {
      const { id, de, para, diametro_mm: d } = t
      for (const k of Object.keys(t)) delete t[k]
      Object.assign(t, { id, de, para, tipo: "tubo", nome: proximoNome(novo.trechos.map((x) => x.nome), "tubo"), diametro_mm: d ?? 52.5, material: "Aço comercial", k_local: 0 })
    } else {
      novo.trechos = novo.trechos.filter((x) => x.id !== sel.id)
    }
  }
  return novo
}

function inverter(dados, idTrecho) {
  const novo = copiar(dados)
  const t = novo.trechos.find((x) => x.id === idTrecho)
  if (t) [t.de, t.para] = [t.para, t.de]
  return novo
}

function alternarVaso(dados, idNo) {
  const novo = copiar(dados)
  const tinha = novo.nos.find((n) => n.id === idNo)?.vaso
  for (const n of novo.nos) n.vaso = false
  const n = novo.nos.find((x) => x.id === idNo)
  if (n && !tinha) {
    n.vaso = true
    n.vaso_volume_L = n.vaso_volume_L ?? 35
    n.vaso_precarga_bar = n.vaso_precarga_bar ?? 1.0
    n.vaso_enchimento_bar = n.vaso_enchimento_bar ?? 1.5
    n.vaso_maxima_bar = n.vaso_maxima_bar ?? 3.0
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
  return String(Math.round(v * 100) / 100).replace(".", ",")
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
    vista: { x: 0, y: 0, esc: 1 },
    ferramenta: "mover",
    sel: null,
    pendente: null,
    cursor: null,
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
    let menor = PERTO
    for (const t of e.dados.trechos) {
      const a = noPorId(e.dados, t.de)
      const b = noPorId(e.dados, t.para)
      if (!a || !b) continue
      const { d } = distanciaAoSegmento([px, py], tela(a.x, a.y), tela(b.x, b.y))
      const folga = t.tipo === "tubo" ? 0 : 6 // a peça tem o símbolo maior
      if (d <= menor + folga) {
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
    const txt = JSON.stringify(sel)
    if (txt !== e.selEnviada) {
      e.selEnviada = txt
      e.enviar?.("selecao", sel ? { ...sel, n: Date.now() } : null)
    }
    desenhar()
  }
  function novoTubo(dados, de, para) {
    const ultimo = [...dados.trechos].reverse().find((t) => t.tipo === "tubo")
    return {
      id: proximoId(dados.trechos, "t"),
      nome: proximoNome(dados.trechos.map((t) => t.nome), "tubo"),
      tipo: "tubo",
      de,
      para,
      comprimento: null,
      diametro_mm: ultimo?.diametro_mm ?? 52.5,
      material: ultimo?.material ?? "Aço comercial",
      k_local: 0,
    }
  }

  function aoClicar(px, py) {
    const f = e.ferramenta
    const no = noEm(px, py)
    if (f === "mover") {
      if (no) return selecionar({ tipo: "no", id: no.id })
      const t = trechoEm(px, py)
      return selecionar(t ? { tipo: "trecho", id: t.id } : null)
    }
    if (f === "vaso") {
      if (no) {
        mudar(alternarVaso(e.dados, no.id))
        return selecionar({ tipo: "no", id: no.id })
      }
      const t = trechoEm(px, py)
      if (t) {
        const a = noPorId(e.dados, t.de)
        const b = noPorId(e.dados, t.para)
        const { t: frac } = distanciaAoSegmento(metro(px, py), [a.x, a.y], [b.x, b.y])
        const r = dividirTubo(e.dados, t.id, frac)
        mudar(alternarVaso(r.dados, r.no))
        return selecionar({ tipo: "no", id: r.no })
      }
      return
    }
    if (PECAS.includes(f)) {
      const t = trechoEm(px, py)
      if (!t || t.tipo !== "tubo") return
      const tamanho = Math.max(e.grade, 18 / e.vista.esc)
      const r = inserirPeca(e.dados, t.id, metro(px, py), f, tamanho)
      if (r.peca) {
        mudar(r.dados)
        return selecionar({ tipo: "trecho", id: r.peca })
      }
      return
    }
    if (f === "tubo") {
      const dados = copiar(e.dados)
      let alvo = no
      if (!alvo) {
        const [x, y] = pontoGrudado(px, py)
        alvo = novoPonto(dados, x, y)
        dados.nos.push(alvo)
      }
      if (e.pendente && e.pendente !== alvo.id && !jaLigados(dados, e.pendente, alvo.id)) {
        const tubo = novoTubo(dados, e.pendente, alvo.id)
        dados.trechos.push(tubo)
        e.pendente = alvo.id
        mudar(dados)
        return selecionar({ tipo: "trecho", id: tubo.id })
      }
      e.pendente = alvo.id
      if (dados.nos.length !== e.dados.nos.length) mudar(dados)
      return selecionar({ tipo: "no", id: alvo.id })
    }
  }

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
      e.gesto = { tipo: "arrastar", id: no.id, px, py, moveu: false }
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
    else if (g.tipo === "clique") aoClicar(px, py)
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
    const atalho = { v: "mover", t: "tubo", b: "bomba" }[ev.key.toLowerCase()]
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
      e.vista = { x: -5, y: 15, esc: largura() / 30 }
      return
    }
    const xs = nos.map((n) => n.x)
    const ys = nos.map((n) => n.y)
    const w = Math.max(Math.max(...xs) - Math.min(...xs), 1)
    const h = Math.max(Math.max(...ys) - Math.min(...ys), 1)
    // folga em volta para os rótulos: uma fração do quadro, que pode ser estreito
    const esc = Math.min((largura() * 0.78 - 40) / w, (altura() * 0.78 - 40) / h)
    e.vista.esc = Math.max(0.01, Math.min(esc, 300))
    e.vista.x = (Math.min(...xs) + Math.max(...xs)) / 2 - largura() / 2 / e.vista.esc
    e.vista.y = (Math.min(...ys) + Math.max(...ys)) / 2 + altura() / 2 / e.vista.esc
  }
  function gradeSugerida() {
    const alvo = 30 / e.vista.esc
    return GRADES.find((g) => g >= alvo) ?? GRADES[GRADES.length - 1]
  }

  const acoes = {
    apagar() {
      if (!e.sel) return
      const eraPeca = e.sel.tipo === "trecho" && e.dados.trechos.find((t) => t.id === e.sel.id)?.tipo !== "tubo"
      mudar(apagar(e.dados, e.sel))
      selecionar(eraPeca ? e.sel : null)
    },
    inverter() {
      if (e.sel?.tipo !== "trecho") return
      mudar(inverter(e.dados, e.sel.id))
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
    svg.setAttribute("class", `f-${PECAS.includes(f) ? "peca" : f}`)
    infoDica.textContent = DICAS[PECAS.includes(f) ? "peca" : f]
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

  // ---- símbolos das peças, no meio do trecho e girados com ele
  function simbolo(t, mx, my, ux, uy, sel, ruim) {
    const g = el("g", { transform: `translate(${mx},${my}) rotate(${(Math.atan2(uy, ux) * 180) / Math.PI})`, class: `peca${sel ? " sel" : ""}${ruim ? " ruim" : ""}` })
    if (t.tipo === "bomba") {
      el("circle", { cx: 0, cy: 0, r: 12, class: "corpo" }, g)
      el("polygon", { points: "-5,-7 8,0 -5,7", class: "miolo" }, g)
    } else if (t.tipo === "valvula") {
      el("polygon", { points: "-11,-8 0,0 -11,8", class: "corpo" }, g)
      el("polygon", { points: "11,-8 0,0 11,8", class: "corpo" }, g)
    } else if (t.tipo === "filtro") {
      el("polygon", { points: "0,-10 11,0 0,10 -11,0", class: "corpo" }, g)
      el("line", { x1: -7, y1: 0, x2: 7, y2: 0, class: "risco" }, g)
    } else if (t.tipo === "tanque") {
      el("rect", { x: -12, y: -15, width: 24, height: 30, rx: 6, class: "corpo agua" }, g)
    } else {
      const cores = { fonte: "quente", dry_cooler: "frio", chiller: "gelado" }
      el("rect", { x: -18, y: -11, width: 36, height: 22, rx: 3, class: `corpo ${cores[t.tipo] ?? ""}` }, g)
      if (t.tipo === "dry_cooler") {
        el("circle", { cx: 0, cy: 0, r: 7, class: "risco" }, g)
        el("line", { x1: -7, y1: 0, x2: 7, y2: 0, class: "risco" }, g)
        el("line", { x1: 0, y1: -7, x2: 0, y2: 7, class: "risco" }, g)
      } else {
        const sigla = el("text", { x: 0, y: 4, "text-anchor": "middle", class: "sigla" }, g)
        sigla.textContent = t.tipo === "fonte" ? "Q" : "CH"
      }
    }
  }

  function desenhar() {
    while (svg.firstChild) svg.removeChild(svg.firstChild)
    const w = largura()
    const h = altura()
    el("rect", { x: 0, y: 0, width: w, height: h, fill: "#ffffff" })
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
    for (const t of e.dados.trechos) {
      const a = noPorId(e.dados, t.de)
      const b = noPorId(e.dados, t.para)
      if (!a || !b) continue
      let [x1, y1] = tela(a.x, a.y)
      let [x2, y2] = tela(b.x, b.y)
      const m = marcas.trechos?.[t.id]
      const sel = e.sel?.tipo === "trecho" && e.sel.id === t.id
      const espessura = 2 + 4 * Math.min((Number(t.diametro_mm) || 50) / 200, 1)
      const atributos = { x1, y1, x2, y2, class: `tubo${m?.ruim ? " ruim" : ""}${sel ? " sel" : ""}`, "stroke-width": espessura }
      if (m?.cor && !m?.ruim && !sel) atributos.style = `stroke:${m.cor}`
      el("line", atributos)
      // sentido: o da água, se a conta já rodou; senão o do desenho (o da bomba)
      const sentido = m?.sentido ?? 1
      if (sentido === -1) [x1, y1, x2, y2] = [x2, y2, x1, y1]
      const mx = (x1 + x2) / 2
      const my = (y1 + y2) / 2
      const l = Math.hypot(x2 - x1, y2 - y1) || 1
      const ux = (x2 - x1) / l
      const uy = (y2 - y1) / l
      if (t.tipo === "tubo") {
        if (l > 40) {
          const p = `${mx + 7 * ux},${my + 7 * uy} ${mx - 6 * ux - 5 * uy},${my - 6 * uy + 5 * ux} ${mx - 6 * ux + 5 * uy},${my - 6 * uy - 5 * ux}`
          el("polygon", { points: p, class: `seta${m?.ruim ? " ruim" : ""}` })
        }
      } else {
        // a bomba aponta no sentido do desenho (é ela que empurra)
        const desenhoUx = t.tipo === "bomba" && sentido === -1 ? -ux : ux
        const desenhoUy = t.tipo === "bomba" && sentido === -1 ? -uy : uy
        simbolo(t, mx, my, desenhoUx, desenhoUy, sel, m?.ruim)
      }
      let nx = -uy
      let ny = ux
      if (Math.abs(uy) < 0.5 ? ny < 0 : nx < 0) {
        nx = -nx
        ny = -ny
      }
      const ancora = nx > 0.3 ? "start" : nx < -0.3 ? "end" : "middle"
      const afasta = t.tipo === "tubo" ? 12 : 22
      const rotulo = m ? `${t.nome}: ${m.texto}` : t.tipo === "tubo" ? `${t.nome} · ${texto(Number(t.diametro_mm) || 0)} mm` : t.nome
      // rótulo do tubo só se ele for longo na tela; o da peça sempre
      if ((t.tipo === "tubo" && l > 90) || t.tipo !== "tubo") {
        const txt = el("text", { x: mx + afasta * nx, y: my + (afasta + 4) * ny + 4, "text-anchor": ancora, class: `rot${m?.ruim ? " ruim" : ""}${t.tipo !== "tubo" ? " nome" : ""}` })
        txt.textContent = rotulo
      }
      el("line", { x1, y1, x2, y2, class: "alvo" })
    }
    if (e.ferramenta === "tubo" && e.pendente && e.cursor) {
      const a = noPorId(e.dados, e.pendente)
      if (a) {
        const [x1, y1] = tela(a.x, a.y)
        const [x2, y2] = tela(grudar(e.cursor[0], e.grade), grudar(e.cursor[1], e.grade))
        el("line", { x1, y1, x2, y2, class: "previa" })
      }
    }
    for (const n of e.dados.nos) {
      const [x, y] = tela(n.x, n.y)
      const m = marcas.nos?.[n.id]
      const sel = e.sel?.tipo === "no" && e.sel.id === n.id
      if (n.vaso) {
        el("line", { x1: x, y1: y, x2: x, y2: y - 16, class: "haste" })
        el("rect", { x: x - 9, y: y - 40, width: 18, height: 26, rx: 9, class: `vaso${sel ? " sel" : ""}` })
        const v = el("text", { x, y: y - 23, "text-anchor": "middle", class: "sigla" })
        v.textContent = "V"
      }
      el("circle", { cx: x, cy: y, r: RAIO_NO, class: `no${m?.ruim ? " ruim" : ""}${sel ? " sel" : ""}` })
      const nome = el("text", { x: x + 10, y: y + (n.vaso ? 16 : -10), class: `rot nome${m?.ruim ? " ruim" : ""}` })
      nome.textContent = m ? `${n.nome} · ${m.texto}` : n.nome
    }
    if (e.ferramenta !== "mover" && e.cursor && !e.gesto) {
      const [x, y] = tela(grudar(e.cursor[0], e.grade), grudar(e.cursor[1], e.grade))
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
