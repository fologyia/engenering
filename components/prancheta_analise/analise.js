// Prancheta da análise sobre o desenho: o desenho de fundo (imagem ou DXF) e as marcas numeradas.
// Cada marca é uma parte do desenho com a sua análise do Montador; a conta é no Python, e a etiqueta
// volta com o resultado (verde passou, vermelho não passou, azul até onde vai, cinza falta número).
//
// Coordenadas do mundo com y para baixo: na imagem, pixels da imagem; no DXF, mm com o y virado.
// A escala diz quantos mm vale uma unidade do mundo (no DXF é 1). O estado fica preso ao
// parentElement, porque o Streamlit chama esta função de novo a cada rodada.

const PA_ESTADOS = new WeakMap()
const PA_PERTO_PX = 12
const PA_ARRASTO_PX = 3
const PA_TEMPO_DO_AVISO_MS = 4000
const PA_LADO_DO_PRINT = 2000
const PA_DICAS = {
  mover: "Arraste uma marca para trocar de lugar; no vazio, arraste para andar. Roda do mouse aproxima. Delete apaga a marca escolhida. Ctrl+V cola um print.",
  marcar: "Clique na parte do desenho que vai ser analisada: a marca nasce ali, e a análise dela fica embaixo.",
  escala: "Clique nas duas pontas de uma medida que você sabe quanto vale.",
  medir: "Clique em dois pontos: a distância aparece (real, se a escala já estiver posta).",
}
// O fundo de curvas (DXF ou esboço salvo) já vem em mm, com y para cima.
const paDeCurvas = (f) => f?.tipo === "dxf" || f?.tipo === "esboco"
const paNum = (v, casas = 3) => (Number.isFinite(v) ? String(Number(v.toPrecision(casas))).replace(".", ",") : "—")
const paEsc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c])

function paCriar(raiz) {
  const caixa = raiz.querySelector(".pa")
  const svg = raiz.querySelector("svg")
  const aviso = raiz.querySelector("[data-aviso]")
  const pergunta = raiz.querySelector("[data-pergunta]")
  const perguntaValor = raiz.querySelector("[data-pergunta-valor]")
  const dica = raiz.querySelector("[data-dica]")
  const textoEscala = raiz.querySelector("[data-escala]")
  const e = {
    enviar: null,
    versao: -1,
    verAjuste: null,
    fundo: null,
    escala: null, // mm por unidade do mundo
    marcas: [], // { id, x, y, numero, rotulo, situacao }
    selecionada: null,
    ferramenta: "mover",
    vista: { cx: 0, cy: 0, esc: 1 },
    gesto: null,
    cliques: [], // os pontos da escala ou da medida
    medida: null,
    mouse: null,
    alvo: null, // onde a marca (ou a ponta da medida) gruda, no fundo de curvas
    pedido: null, // o campo da marca que espera uma medida do desenho: { n, id, chave, texto }
    pedidoFeito: -1,
  }

  const tela = () => {
    const r = svg.getBoundingClientRect()
    return { w: r.width || 800, h: r.height || 560 }
  }
  const px = (x, y) => {
    const { w, h } = tela()
    return [w / 2 + (x - e.vista.cx) * e.vista.esc, h / 2 + (y - e.vista.cy) * e.vista.esc]
  }
  const doPx = (u, v) => {
    const { w, h } = tela()
    return [e.vista.cx + (u - w / 2) / e.vista.esc, e.vista.cy + (v - h / 2) / e.vista.esc]
  }
  const doMouse = (ev) => {
    const r = svg.getBoundingClientRect()
    return [ev.clientX - r.left, ev.clientY - r.top]
  }

  function avisar(texto) {
    clearTimeout(e.tempoDoAviso)
    aviso.hidden = !texto
    aviso.textContent = texto || ""
    if (texto) e.tempoDoAviso = setTimeout(() => (aviso.hidden = true), PA_TEMPO_DO_AVISO_MS)
  }

  // ---- o desenho de fundo -----------------------------------------------------------------------
  function caixaDoFundo() {
    const f = e.fundo
    if (!f) return null
    if (f.tipo === "imagem") return [0, 0, f.largura, f.altura]
    const xs = []
    const ys = []
    for (const c of f.curvas || []) {
      if (c.tipo === "linha") {
        xs.push(c.a[0], c.b[0])
        ys.push(-c.a[1], -c.b[1])
      } else {
        const r = c.r ?? Math.hypot(c.a[0] - c.c[0], c.a[1] - c.c[1])
        xs.push(c.c[0] - r, c.c[0] + r)
        ys.push(-c.c[1] - r, -c.c[1] + r)
      }
    }
    if (!xs.length) return null
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]
  }
  function enquadrar() {
    const { w, h } = tela()
    const caixas = []
    const fundo = caixaDoFundo()
    if (fundo) caixas.push(fundo)
    for (const m of e.marcas) caixas.push([m.x, m.y, m.x, m.y])
    if (!caixas.length) {
      e.vista = { cx: 0, cy: 0, esc: 1 }
      return desenhar()
    }
    const x0 = Math.min(...caixas.map((c) => c[0]))
    const y0 = Math.min(...caixas.map((c) => c[1]))
    const x1 = Math.max(...caixas.map((c) => c[2]))
    const y1 = Math.max(...caixas.map((c) => c[3]))
    const largura = Math.max(x1 - x0, 1)
    const altura = Math.max(y1 - y0, 1)
    e.vista = { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, esc: Math.min((w * 0.92) / largura, (h * 0.92) / altura) }
    desenhar()
  }
  function svgDoFundo() {
    const f = e.fundo
    if (!f) {
      const { w, h } = tela()
      return `<text class="vazio" x="${w / 2}" y="${h / 2}" text-anchor="middle">Solte um desenho acima, ou clique aqui e cole um print (Ctrl+V).</text>`
    }
    if (f.tipo === "imagem") {
      const [u0, v0] = px(0, 0)
      return `<image href="${f.imagem}" x="${u0}" y="${v0}" width="${f.largura * e.vista.esc}" height="${f.altura * e.vista.esc}" preserveAspectRatio="none"/>`
    }
    const partes = []
    for (const c of f.curvas || []) {
      if (c.tipo === "linha") {
        const [a, b] = [px(c.a[0], -c.a[1]), px(c.b[0], -c.b[1])]
        partes.push(`M${a[0]} ${a[1]}L${b[0]} ${b[1]}`)
      } else if (c.tipo === "circulo") {
        const [u, v] = px(c.c[0], -c.c[1])
        const r = c.r * e.vista.esc
        partes.push(`M${u - r} ${v}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`)
      } else {
        // Anti-horário no desenho (y para cima) fica horário na tela com y para baixo: varre = 0.
        const r = Math.hypot(c.a[0] - c.c[0], c.a[1] - c.c[1])
        const ta = Math.atan2(c.a[1] - c.c[1], c.a[0] - c.c[0])
        let sw = Math.atan2(c.b[1] - c.c[1], c.b[0] - c.c[0]) - ta
        while (sw < 0) sw += 2 * Math.PI
        const [a, b] = [px(c.a[0], -c.a[1]), px(c.b[0], -c.b[1])]
        const R = r * e.vista.esc
        partes.push(`M${a[0]} ${a[1]}A${R} ${R} 0 ${sw > Math.PI ? 1 : 0} 0 ${b[0]} ${b[1]}`)
      }
    }
    return `<path class="dxf" d="${partes.join("")}"/>`
  }

  // ---- grudar no desenho de curvas ---------------------------------------------------------------
  // No mundo da prancheta (y para baixo). Devolve { x, y, tipo, curva } ou null.
  function grudar(u, v) {
    if (!paDeCurvas(e.fundo)) return null
    const [x, y] = doPx(u, v)
    const tol = PA_PERTO_PX / e.vista.esc
    let melhor = null
    let dist = tol
    const olhar = (px_, py_, tipo, curva) => {
      const d = Math.hypot(px_ - x, py_ - y)
      if (d <= dist) {
        dist = d
        melhor = { x: px_, y: py_, tipo, curva }
      }
    }
    // Primeiro as pontas e os centros bem perto do clique.
    let furo = null
    for (const c of e.fundo.curvas || []) {
      if (c.tipo === "linha") {
        olhar(c.a[0], -c.a[1], "ponta", c)
        olhar(c.b[0], -c.b[1], "ponta", c)
        continue
      }
      const r = c.r ?? Math.hypot(c.a[0] - c.c[0], c.a[1] - c.c[1])
      olhar(c.c[0], -c.c[1], "centro", c)
      if (c.tipo === "arco") {
        olhar(c.a[0], -c.a[1], "ponta", c)
        olhar(c.b[0], -c.b[1], "ponta", c)
      }
      // Dentro do círculo, ou na borda dele: o centro, do menor que contém o clique.
      if (Math.hypot(c.c[0] - x, -c.c[1] - y) <= r + tol && (!furo || r < furo.r)) furo = { c, r }
    }
    if (melhor) return melhor
    if (furo) return { x: furo.c.c[0], y: -furo.c.c[1], tipo: "centro", curva: furo.c }
    for (const c of e.fundo.curvas || []) {
      if (c.tipo !== "linha") continue
      const [ax, ay, bx, by] = [c.a[0], -c.a[1], c.b[0], -c.b[1]]
      const dx = bx - ax
      const dy = by - ay
      const t = Math.min(Math.max(((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy || 1), 0), 1)
      olhar(ax + t * dx, ay + t * dy, "linha", c)
    }
    return melhor
  }
  // A borda de um círculo (ou arco) debaixo do mouse: um clique dá o diâmetro.
  function circuloNaBorda(u, v) {
    if (!paDeCurvas(e.fundo)) return null
    const [x, y] = doPx(u, v)
    const tol = PA_PERTO_PX / e.vista.esc
    let melhor = null
    let dist = tol
    for (const c of e.fundo.curvas || []) {
      if (c.tipo === "linha") continue
      const r = c.r ?? Math.hypot(c.a[0] - c.c[0], c.a[1] - c.c[1])
      const d = Math.abs(Math.hypot(c.c[0] - x, -c.c[1] - y) - r)
      if (d <= dist) {
        dist = d
        melhor = { c, r }
      }
    }
    return melhor
  }
  function svgDoAlvo() {
    if (!e.alvo) return ""
    const [u, v] = px(e.alvo.x, e.alvo.y)
    const titulo = { centro: "Centro do furo", ponta: "Ponta da linha", linha: "Na linha" }[e.alvo.tipo] || ""
    return `<g class="alvo"><title>${titulo}</title><circle cx="${u}" cy="${v}" r="8"/><circle cx="${u}" cy="${v}" r="2.5"/></g>`
  }

  // ---- medida pedida por um campo da marca ----------------------------------------------------------
  function terminarPedido(valor) {
    const pedido = e.pedido
    if (!pedido) return
    e.pedidoFeito = pedido.n
    e.pedido = null
    e.cliques = []
    e.medida = null
    e.enviar?.("medida", valor === null ? { n: pedido.n, cancelar: true } : { n: pedido.n, id: pedido.id, chave: pedido.chave, valor })
    trocarFerramenta("mover")
  }
  function cliqueDoPedido(u, v, mundo) {
    const borda = e.cliques.length ? null : circuloNaBorda(u, v)
    if (borda) {
      avisar(`Ø ${paNum(2 * borda.r, 4)} mm`)
      return terminarPedido(2 * borda.r)
    }
    const g = grudar(u, v)
    e.cliques.push(g ? [g.x, g.y] : mundo)
    if (e.cliques.length < 2) return desenhar()
    const [a, b] = e.cliques
    const d = Math.hypot(b[0] - a[0], b[1] - a[1])
    if (!e.escala) {
      e.cliques = []
      avisar("Ponha a escala antes (ferramenta Escala): sem ela não dá para medir em mm.")
      return desenhar()
    }
    avisar(`${paNum(d * e.escala, 4)} mm`)
    terminarPedido(d * e.escala)
  }

  // ---- marcas -----------------------------------------------------------------------------------
  const CLASSE = { passou: "passou", "não passou": "nao", limite: "limite", falta: "falta", erro: "falta", nota: "nota" }
  function svgDaMarca(m) {
    const [u, v] = px(m.x, m.y)
    const classes = ["marca", CLASSE[m.situacao] || "falta"]
    if (e.selecionada === m.id) classes.push("sel")
    const texto = m.rotulo || ""
    const largura = Math.max(7 * texto.length + 14, 40)
    const etiqueta = texto
      ? `<g class="etiqueta"><line x1="${u + 9}" y1="${v - 9}" x2="${u + 22}" y2="${v - 22}" stroke="currentColor" opacity="0.5"/><rect x="${u + 22}" y="${v - 38}" width="${largura}" height="22" rx="6"/><text x="${u + 29}" y="${v - 23}">${paEsc(texto)}</text></g>`
      : ""
    return `<g class="${classes.join(" ")}" data-marca="${paEsc(m.id)}"><circle cx="${u}" cy="${v}" r="11"/><text class="numero" x="${u}" y="${v + 4}" text-anchor="middle">${m.numero ?? ""}</text>${etiqueta}</g>`
  }
  function marcaNoMouse(u, v) {
    let melhor = null
    let dist = PA_PERTO_PX
    for (const m of e.marcas) {
      const [a, b] = px(m.x, m.y)
      const d = Math.hypot(a - u, b - v)
      if (d <= dist) {
        dist = d
        melhor = m
      }
    }
    return melhor
  }
  function novoId() {
    let maior = 0
    for (const m of e.marcas) {
      const n = Number(/^m(\d+)$/.exec(m.id)?.[1] ?? 0)
      maior = Math.max(maior, n)
    }
    return `m${maior + 1}`
  }
  function enviar() {
    e.versao += 1
    e.enviar?.("edicao", {
      versao: e.versao,
      marcas: e.marcas.map((m) => ({ id: m.id, x: m.x, y: m.y })),
      selecionada: e.selecionada,
      escala: e.escala,
    })
  }

  // ---- escala e medida --------------------------------------------------------------------------
  function svgDaMedida() {
    const pontos = e.medida ? [e.medida.a, e.medida.b] : e.cliques.length && e.mouse ? [e.cliques[0], e.mouse] : null
    if (!pontos) return ""
    const [a, b] = pontos.map((p) => px(...p))
    const d = Math.hypot(pontos[1][0] - pontos[0][0], pontos[1][1] - pontos[0][1])
    const real = e.escala ? `${paNum(d * e.escala, 4)} mm` : `${paNum(d, 4)} px (ponha a escala)`
    const texto = e.ferramenta === "escala" && !e.medida ? "" : real
    return `<g class="medida"><line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}"/><circle cx="${a[0]}" cy="${a[1]}" r="4"/><circle cx="${b[0]}" cy="${b[1]}" r="4"/><text x="${(a[0] + b[0]) / 2 + 8}" y="${(a[1] + b[1]) / 2 - 8}">${texto}</text></g>`
  }
  function perguntarEscala(a, b) {
    e.medida = { a, b }
    perguntaValor.value = ""
    pergunta.hidden = false
    setTimeout(() => perguntaValor.focus(), 0)
    desenhar()
  }
  function porEscala() {
    const texto = String(perguntaValor.value || "").trim().replace(",", ".")
    const valor = Number(texto)
    const { a, b } = e.medida || {}
    const d = a && b ? Math.hypot(b[0] - a[0], b[1] - a[1]) : 0
    if (!(valor > 0) || !(d > 0)) {
      avisar("Digite a medida em mm, maior que zero.")
      return
    }
    e.escala = valor / d
    pergunta.hidden = true
    e.medida = null
    avisar(`Escala posta: ${paNum(e.escala, 4)} mm por pixel da imagem.`)
    enviar()
    desenhar()
    svg.focus({ preventScroll: true })
  }
  raiz.querySelector("[data-pergunta-ok]").addEventListener("click", porEscala)
  raiz.querySelector("[data-pergunta-nao]").addEventListener("click", () => {
    pergunta.hidden = true
    e.medida = null
    desenhar()
    svg.focus({ preventScroll: true })
  })
  perguntaValor.addEventListener("keydown", (ev) => {
    ev.stopPropagation()
    if (ev.key === "Enter") porEscala()
    if (ev.key === "Escape") raiz.querySelector("[data-pergunta-nao]").click()
  })

  // ---- desenho na tela --------------------------------------------------------------------------
  function desenhar() {
    const { w, h } = tela()
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`)
    svg.classList.toggle("marcando", e.ferramenta === "marcar")
    svg.classList.toggle("medindo", e.ferramenta === "medir" || e.ferramenta === "escala")
    svg.innerHTML = svgDoFundo() + e.marcas.map(svgDaMarca).join("") + svgDaMedida() + svgDoAlvo()
    if (e.fundo?.tipo === "dxf") textoEscala.textContent = "DXF em mm"
    else if (e.fundo?.tipo === "esboco") textoEscala.textContent = "Esboço em mm"
    else textoEscala.textContent = e.escala ? `Escala: ${paNum(e.escala, 4)} mm por pixel` : e.fundo ? "Sem escala: use Escala para medir em mm" : ""
  }
  function trocarFerramenta(nome) {
    e.ferramenta = nome
    e.cliques = []
    e.medida = null
    e.alvo = null
    pergunta.hidden = true
    dica.textContent = PA_DICAS[nome] || ""
    if (nome === "pegar" && e.pedido) {
      dica.textContent = `Medindo ${e.pedido.texto}: clique nas duas pontas${paDeCurvas(e.fundo) ? " (num círculo, um clique na borda dá o diâmetro)" : ""}. Esc cancela.`
    }
    raiz.querySelectorAll("[data-f]").forEach((b) => b.classList.toggle("ativo", b.dataset.f === nome))
    desenhar()
  }

  // ---- mouse ------------------------------------------------------------------------------------
  svg.addEventListener("pointerdown", (ev) => {
    const [u, v] = doMouse(ev)
    svg.focus({ preventScroll: true })
    const mundo = doPx(u, v)
    if (ev.button === 1 || ev.button === 2) {
      e.gesto = { tipo: "andar", inicio: [u, v], vista: { ...e.vista } }
      return
    }
    if (ev.button !== 0) return
    if (e.ferramenta === "pegar" && e.pedido) {
      cliqueDoPedido(u, v, mundo)
      return
    }
    if (e.ferramenta === "marcar") {
      const g = grudar(u, v)
      const lugar = g ? [g.x, g.y] : mundo
      const m = { id: novoId(), x: lugar[0], y: lugar[1], numero: e.marcas.length + 1, rotulo: "", situacao: "falta" }
      e.marcas.push(m)
      e.selecionada = m.id
      enviar()
      desenhar()
      return
    }
    if (e.ferramenta === "escala" || e.ferramenta === "medir") {
      if (e.medida) {
        e.medida = null
        e.cliques = []
      }
      const g = grudar(u, v)
      e.cliques.push(g ? [g.x, g.y] : mundo)
      if (e.cliques.length === 2) {
        const [a, b] = e.cliques
        e.cliques = []
        if (e.ferramenta === "escala") perguntarEscala(a, b)
        else e.medida = { a, b }
      }
      desenhar()
      return
    }
    const alvo = marcaNoMouse(u, v)
    if (alvo) {
      e.selecionada = alvo.id
      e.gesto = { tipo: "marca", id: alvo.id, inicio: [u, v], mundo, base: [alvo.x, alvo.y], moveu: false }
    } else {
      e.gesto = { tipo: "andar", inicio: [u, v], vista: { ...e.vista }, clique: true }
    }
    try {
      svg.setPointerCapture(ev.pointerId)
    } catch {
      // clique sintético: segue sem captura
    }
    desenhar()
  })
  svg.addEventListener("pointermove", (ev) => {
    const [u, v] = doMouse(ev)
    e.mouse = doPx(u, v)
    const g = e.gesto
    if (g?.tipo === "andar") {
      if (Math.hypot(u - g.inicio[0], v - g.inicio[1]) > PA_ARRASTO_PX) g.clique = false
      e.vista.cx = g.vista.cx - (u - g.inicio[0]) / e.vista.esc
      e.vista.cy = g.vista.cy - (v - g.inicio[1]) / e.vista.esc
      desenhar()
      return
    }
    if (g?.tipo === "marca") {
      if (!g.moveu && Math.hypot(u - g.inicio[0], v - g.inicio[1]) <= PA_ARRASTO_PX) return
      g.moveu = true
      const m = e.marcas.find((x) => x.id === g.id)
      if (m) {
        const alvo = grudar(u, v)
        e.alvo = alvo
        m.x = alvo ? alvo.x : g.base[0] + (e.mouse[0] - g.mundo[0])
        m.y = alvo ? alvo.y : g.base[1] + (e.mouse[1] - g.mundo[1])
      }
      desenhar()
      return
    }
    if (["marcar", "medir", "escala", "pegar"].includes(e.ferramenta) && paDeCurvas(e.fundo)) {
      e.alvo = grudar(u, v)
      return desenhar()
    }
    if (e.cliques.length) desenhar()
  })
  svg.addEventListener("pointerup", (ev) => {
    const g = e.gesto
    e.gesto = null
    try {
      if (svg.hasPointerCapture?.(ev.pointerId)) svg.releasePointerCapture(ev.pointerId)
    } catch {
      // nada a soltar
    }
    if (!g) return
    e.alvo = null
    if (g.tipo === "marca") enviar() // mudou de lugar, ou só foi escolhida
    if (g.tipo === "andar" && g.clique && e.selecionada) {
      e.selecionada = null
      enviar()
      desenhar()
    }
  })
  svg.addEventListener("contextmenu", (ev) => ev.preventDefault())
  svg.addEventListener(
    "wheel",
    (ev) => {
      ev.preventDefault()
      const [u, v] = doMouse(ev)
      const [x, y] = doPx(u, v)
      e.vista.esc = Math.min(Math.max(e.vista.esc * Math.exp(-ev.deltaY * 0.0015), 1e-4), 1e4)
      const [x2, y2] = doPx(u, v)
      e.vista.cx += x - x2
      e.vista.cy += y - y2
      desenhar()
    },
    { passive: false },
  )
  svg.addEventListener("pointerleave", () => {
    e.mouse = null
    if (e.cliques.length) desenhar()
  })

  // ---- teclado e print colado -------------------------------------------------------------------
  svg.addEventListener("keydown", (ev) => {
    const tecla = ev.key.toLowerCase()
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return // Ctrl+V chega pelo evento de colar
    if (ev.key === "Escape" && e.pedido) terminarPedido(null)
    else if (ev.key === "Escape") trocarFerramenta("mover")
    else if ((ev.key === "Delete" || ev.key === "Backspace") && e.selecionada) {
      e.marcas = e.marcas.filter((m) => m.id !== e.selecionada)
      e.selecionada = null
      enviar()
      desenhar()
    } else if (tecla === "m") trocarFerramenta("marcar")
    else if (tecla === "e") trocarFerramenta("escala")
    else if (tecla === "d") trocarFerramenta("medir")
    else if (tecla === "f") enquadrar()
    else return
    ev.preventDefault()
  })
  function reduzir(url) {
    // O print grande pesa no caminho até o Python: chega já do tamanho que a prancheta usa.
    return new Promise((resolver) => {
      const imagem = new Image()
      imagem.onload = () => {
        const fator = Math.min(1, PA_LADO_DO_PRINT / Math.max(imagem.width, imagem.height))
        const canvas = document.createElement("canvas")
        canvas.width = Math.round(imagem.width * fator)
        canvas.height = Math.round(imagem.height * fator)
        canvas.getContext("2d").drawImage(imagem, 0, 0, canvas.width, canvas.height)
        resolver(canvas.toDataURL("image/jpeg", 0.85))
      }
      imagem.onerror = () => resolver(null)
      imagem.src = url
    })
  }
  function colar(ev) {
    const itens = [...(ev.clipboardData?.items || [])]
    const imagem = itens.find((i) => i.type.startsWith("image/"))
    if (!imagem) {
      avisar("O que está copiado não é uma imagem. Tire um print (Win+Shift+S) e cole aqui.")
      return
    }
    ev.preventDefault()
    const leitor = new FileReader()
    leitor.onload = async () => {
      const url = await reduzir(String(leitor.result))
      if (!url) return avisar("A imagem colada não abriu.")
      avisar("Print colado: agora marque as partes que vão ser analisadas.")
      e.enviar?.("colar", { imagem: url })
    }
    leitor.readAsDataURL(imagem.getAsFile())
  }
  svg.addEventListener("paste", colar)
  caixa.addEventListener("paste", (ev) => {
    if (ev.target !== svg) colar(ev)
  })

  // ---- botões -----------------------------------------------------------------------------------
  raiz.querySelectorAll("[data-f]").forEach((b) =>
    b.addEventListener("click", () => {
      if (e.pedido) terminarPedido(null) // outra ferramenta: a medida pedida fica para depois
      trocarFerramenta(b.dataset.f)
      svg.focus({ preventScroll: true })
    }),
  )
  raiz.querySelector('[data-a="enquadrar"]').addEventListener("click", () => {
    enquadrar()
    svg.focus({ preventScroll: true })
  })
  raiz.querySelector('[data-a="tela"]').addEventListener("click", () => {
    if (document.fullscreenElement) document.exitFullscreen?.()
    else caixa.requestFullscreen?.()
  })
  document.addEventListener("fullscreenchange", () => setTimeout(() => enquadrar(), 50))

  // ---- Python → aqui ----------------------------------------------------------------------------
  e.receber = (dados) => {
    const chave = (f) => (f ? `${f.tipo}|${f.nome}|${f.largura}|${f.altura}` : "")
    const fundoNovo = chave(dados.fundo) !== chave(e.fundo)
    e.fundo = dados.fundo ?? null
    if (dados.versao > e.versao) {
      e.versao = dados.versao
      e.escala = dados.escala ?? null
      e.marcas = (dados.marcas || []).map((m) => ({ ...m }))
      e.selecionada = dados.selecionada ?? null
    } else {
      // A mesma lista: só as etiquetas, que trazem o resultado da conta.
      const porId = new Map((dados.marcas || []).map((m) => [m.id, m]))
      for (const m of e.marcas) {
        const vinda = porId.get(m.id)
        if (vinda) Object.assign(m, { numero: vinda.numero, rotulo: vinda.rotulo, situacao: vinda.situacao })
      }
    }
    if (paDeCurvas(e.fundo)) e.escala = 1
    const pedido = dados.pedido ?? null
    if (pedido && pedido.n > e.pedidoFeito && (!e.pedido || e.pedido.n !== pedido.n)) {
      e.pedido = pedido
      trocarFerramenta("pegar")
      setTimeout(() => svg.focus({ preventScroll: true }), 0)
    } else if (!pedido && e.pedido) {
      e.pedido = null
      if (e.ferramenta === "pegar") trocarFerramenta("mover")
    }
    if (fundoNovo || e.verAjuste !== dados.ajustar) {
      e.verAjuste = dados.ajustar
      setTimeout(() => enquadrar(), 0)
    }
    desenhar()
  }

  trocarFerramenta("mover")
  new ResizeObserver(() => desenhar()).observe(svg)
  caixa.estadoDaAnalise = e
  return e
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  let estado = PA_ESTADOS.get(parentElement)
  if (!estado) {
    estado = paCriar(parentElement)
    PA_ESTADOS.set(parentElement, estado)
  }
  estado.enviar = setTriggerValue
  estado.receber(data ?? {})
}
