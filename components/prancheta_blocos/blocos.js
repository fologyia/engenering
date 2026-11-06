// Prancheta de blocos do montador de fórmulas. Aqui só nasce o desenho: blocos e fios. Ele vai para o
// Python a cada gesto terminado, e os avisos de cada bloco voltam em `marcas`. O catálogo também vem
// de lá, e por isso um bloco novo em core/montador_blocos.py aparece aqui sem mudar este arquivo.

const ESTADOS = new WeakMap()
const LARGURA = 168
const CABECA = 26
const FORMULA = 22
const LINHA = 20
const FOLGA_X = 34
const FOLGA_Y = 34
const TOQUE_PORTA = 12
const SECAO = "secao"
const VALOR = "valor"
const CONDICAO = "condicao"
const DICA = "Clique num bloco acima para pôr na fila. Arraste de uma bolinha a outra para ligar."
const CLASSE_DO_GRUPO = {
  "Seção": "g-secao",
  "De onde vem o esforço": "g-origem",
  "Esforços": "g-esforco",
  "Material": "g-material",
  "Critério": "g-criterio",
  "Resultado": "g-resultado",
}

const copiar = (v) => JSON.parse(JSON.stringify(v))
const escapar = (t) =>
  String(t).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")

function criar(raiz) {
  const svg = raiz.querySelector("svg")
  const paleta = raiz.querySelector("[data-paleta]")
  const dica = raiz.querySelector("[data-dica]")
  dica.textContent = DICA

  const e = {
    enviar: null,
    catalogo: {},
    assinatura: "",
    nos: [],
    fios: [],
    versao: -1,
    verAjuste: null,
    marcas: {},
    vista: { x: 0, y: 0, esc: 1 },
    sel: null,
    gesto: null,
    pendente: null,
    passado: [],
    futuro: [],
  }

  const bloco = (no) => e.catalogo[no.tipo]
  const altura = (no) => {
    const b = bloco(no)
    const erro = e.marcas.erros?.[no.id] ? 18 : 0
    return CABECA + FORMULA + Math.max(b.entradas.length, b.saidas.length, 1) * LINHA + 8 + erro
  }
  const noPorId = (id) => e.nos.find((n) => n.id === id)
  const portaXY = (no, lado, i) => [
    no.x + (lado === "e" ? 0 : LARGURA),
    no.y + CABECA + FORMULA + LINHA * (i + 0.5),
  ]
  const noPonteiro = (ev) => {
    const r = svg.getBoundingClientRect()
    return [ev.clientX - r.left, ev.clientY - r.top]
  }
  const mundo = (ev) => {
    const [x, y] = noPonteiro(ev)
    return [(x - e.vista.x) / e.vista.esc, (y - e.vista.y) / e.vista.esc]
  }
  const liga = (s, ent) => s.tipo === ent.tipo && (s.dimensao ?? null) === (ent.dimensao ?? null)
  // Sozinho, só liga a mesma letra: M com M. T também é momento, e ligar errado seria pior que não ligar.
  const mesmaLetra = (s, ent) => liga(s, ent) && s.rotulo === ent.rotulo

  function guardar() {
    e.passado.push(copiar({ nos: e.nos, fios: e.fios }))
    if (e.passado.length > 60) e.passado.shift()
    e.futuro = []
  }
  function enviar() {
    e.versao += 1
    e.enviar?.("edicao", { grafo: copiar({ nos: e.nos, fios: e.fios }), versao: e.versao })
    desenhar()
  }

  // ---- fios
  function alcanca(de, ate) {
    const vistos = new Set()
    const fila = [de]
    while (fila.length) {
      const atual = fila.pop()
      if (atual === ate) return true
      if (vistos.has(atual)) continue
      vistos.add(atual)
      for (const f of e.fios) if (f.de === atual) fila.push(f.para)
    }
    return false
  }
  function ligar(de, saida, para, entrada) {
    if (de === para || alcanca(para, de)) return false
    const s = bloco(noPorId(de)).saidas.find((p) => p.chave === saida)
    const ent = bloco(noPorId(para)).entradas.find((p) => p.chave === entrada)
    if (!s || !ent || !liga(s, ent)) return false
    if (!ent.varias) e.fios = e.fios.filter((f) => !(f.para === para && f.entrada === entrada))
    if (!e.fios.some((f) => f.de === de && f.saida === saida && f.para === para && f.entrada === entrada)) {
      e.fios.push({ de, saida, para, entrada })
    }
    return true
  }
  const temFioDeSaida = (no, chave) => e.fios.some((f) => f.de === no.id && f.saida === chave)
  const temFioDeEntrada = (no, chave) => e.fios.some((f) => f.para === no.id && f.entrada === chave)

  // ---- ligação automática: quem só clica na paleta já sai com a fila montada
  function fimDaFila(fora) {
    const fim = [...e.nos].reverse().find((n) => {
      if (n === fora) return false
      const s = bloco(n).saidas.find((p) => p.tipo === SECAO)
      return s && !temFioDeSaida(n, s.chave)
    })
    return fim ?? [...e.nos].reverse().find((n) => n !== fora && bloco(n).saidas.some((p) => p.tipo === SECAO))
  }
  function encaixarNaFila(no, entrada, saida) {
    // Esforço novo entra antes do critério de tensão: a fila continua Seção → esforços → critério.
    const criterios = [...e.nos]
      .reverse()
      .filter((n) => n !== no && bloco(n).grupo === "Critério" && temFioDeEntrada(n, "entrada"))
    const criterio = criterios[0]
    if (!criterio) return false
    const fio = e.fios.find((f) => f.para === criterio.id && f.entrada === "entrada")
    const origem = fio.de
    const porta = fio.saida
    if (!ligar(origem, porta, no.id, entrada.chave)) return false
    return ligar(no.id, saida.chave, criterio.id, "entrada")
  }
  function ligarSozinho(no) {
    const b = bloco(no)
    const entradaDaSecao = b.entradas.find((p) => p.tipo === SECAO)
    const saidaDaSecao = b.saidas.find((p) => p.tipo === SECAO)
    if (entradaDaSecao && saidaDaSecao && b.grupo === "Esforços" && encaixarNaFila(no, entradaDaSecao, saidaDaSecao)) {
      // já está na fila
    } else if (entradaDaSecao) {
      const fim = fimDaFila(no)
      if (fim) ligar(fim.id, bloco(fim).saidas.find((p) => p.tipo === SECAO).chave, no.id, entradaDaSecao.chave)
    }
    if (saidaDaSecao && !temFioDeSaida(no, saidaDaSecao.chave)) {
      const livre = e.nos.find(
        (n) => n !== no && bloco(n).entradas.some((p) => p.tipo === SECAO && !temFioDeEntrada(n, p.chave)),
      )
      if (livre) ligar(no.id, saidaDaSecao.chave, livre.id, "entrada")
    }
    for (const ent of b.entradas) {
      if (ent.tipo === VALOR && !temFioDeEntrada(no, ent.chave)) {
        const achado = [...e.nos].reverse().find(
          (n) => n !== no && bloco(n).saidas.some((p) => mesmaLetra(p, ent) && !temFioDeSaida(n, p.chave)),
        )
        if (achado) {
          const s = bloco(achado).saidas.find((p) => mesmaLetra(p, ent) && !temFioDeSaida(achado, p.chave))
          ligar(achado.id, s.chave, no.id, ent.chave)
        }
      }
      if (ent.tipo === CONDICAO) {
        for (const n of e.nos) {
          const s = bloco(n).saidas.find((p) => p.tipo === CONDICAO)
          if (s && !temFioDeSaida(n, s.chave)) ligar(n.id, s.chave, no.id, ent.chave)
        }
      }
    }
    for (const s of b.saidas) {
      if (s.tipo === CONDICAO) {
        const fim = e.nos.find((n) => bloco(n).entradas.some((p) => p.tipo === CONDICAO))
        if (fim) ligar(no.id, s.chave, fim.id, "condicoes")
      }
      if (s.tipo === VALOR) {
        const n = [...e.nos].reverse().find(
          (x) => x !== no && bloco(x).entradas.some((p) => mesmaLetra(s, p) && !temFioDeEntrada(x, p.chave)),
        )
        if (n) {
          const ent = bloco(n).entradas.find((p) => mesmaLetra(s, p) && !temFioDeEntrada(n, p.chave))
          ligar(no.id, s.chave, n.id, ent.chave)
        }
      }
    }
  }

  // ---- blocos
  function idNovo() {
    let k = e.nos.length + 1
    while (noPorId(`n${k}`)) k += 1
    return `n${k}`
  }
  function sobrepoe(x, y, h) {
    return e.nos.some(
      (n) => x < n.x + LARGURA + 16 && x + LARGURA + 16 > n.x && y < n.y + altura(n) + 12 && y + h + 12 > n.y,
    )
  }
  function lugarLivre(no) {
    const r = svg.getBoundingClientRect()
    const limite = Math.max((r.width - e.vista.x) / e.vista.esc - LARGURA - 16, 40)
    const h = altura(no)
    const ultimo = e.nos.at(-1)
    let x = ultimo ? ultimo.x + LARGURA + FOLGA_X : 30
    let y = ultimo ? ultimo.y : 30
    if (x > limite) {
      x = 30
      y = Math.max(...e.nos.map((n) => n.y + altura(n))) + FOLGA_Y
    }
    while (sobrepoe(x, y, h)) y += 40
    return [x, y]
  }
  function acrescentar(tipo) {
    if (tipo === "resultado" && e.nos.some((n) => n.tipo === tipo)) {
      dica.textContent = "A prancheta já tem o bloco Em função de."
      return
    }
    guardar()
    const no = { id: idNovo(), tipo, x: 0, y: 0, opcoes: {} }
    ;[no.x, no.y] = lugarLivre(no)
    e.nos.push(no)
    ligarSozinho(no)
    e.sel = { no: no.id }
    dica.textContent = bloco(no).dica
    enviar()
  }
  function apagar() {
    if (!e.sel) return
    guardar()
    if (e.sel.no) {
      const id = e.sel.no
      const entra = e.fios.find((f) => f.para === id && f.entrada === "entrada")
      const sai = e.fios.filter((f) => f.de === id && f.saida === "saida")
      e.fios = e.fios.filter((f) => f.de !== id && f.para !== id)
      e.nos = e.nos.filter((n) => n.id !== id)
      // Tirar um esforço do meio não pode quebrar a fila.
      if (entra) for (const f of sai) ligar(entra.de, entra.saida, f.para, f.entrada)
    } else if (e.sel.fio !== undefined) {
      e.fios.splice(e.sel.fio, 1)
    }
    e.sel = null
    enviar()
  }
  function organizar() {
    const coluna = Object.fromEntries(e.nos.map((n) => [n.id, 0]))
    for (let k = 0; k < e.nos.length; k += 1) {
      for (const f of e.fios) coluna[f.para] = Math.max(coluna[f.para], coluna[f.de] + 1)
    }
    // Fila comprida quebra em linhas, para o texto dos blocos não encolher até sumir.
    const largura = svg.getBoundingClientRect().width || 800
    const porLinha = Math.max(2, Math.floor((largura / 0.85 - 60 + FOLGA_X) / (LARGURA + FOLGA_X)))
    const alturas = {}
    let topo = 30
    for (let linha = 0; linha <= Math.floor(Math.max(...Object.values(coluna)) / porLinha); linha += 1) {
      let fundo = topo
      for (const n of e.nos) {
        if (Math.floor(coluna[n.id] / porLinha) !== linha) continue
        const c = coluna[n.id] % porLinha
        n.x = 30 + c * (LARGURA + FOLGA_X)
        n.y = alturas[`${linha}:${c}`] ?? topo
        alturas[`${linha}:${c}`] = n.y + altura(n) + FOLGA_Y
        fundo = Math.max(fundo, alturas[`${linha}:${c}`])
      }
      topo = fundo
    }
  }
  function ajustarVista() {
    const r = svg.getBoundingClientRect()
    const w = r.width
    const h = r.height
    if (w < 120 || h < 120) {
      e.ajustarAoMedir = true // ainda sem tamanho: o ResizeObserver chama de novo
      return
    }
    e.ajustarAoMedir = false
    if (!e.nos.length) {
      e.vista = { x: 0, y: 0, esc: 1 }
      return
    }
    const xs = e.nos.map((n) => n.x)
    const ys = e.nos.map((n) => n.y)
    const x0 = Math.min(...xs) - 26
    const y0 = Math.min(...ys) - 26
    const x1 = Math.max(...xs) + LARGURA + 26
    const y1 = Math.max(...e.nos.map((n) => n.y + altura(n))) + 26
    const esc = Math.max(0.35, Math.min(1.15, Math.min(w / (x1 - x0), h / (y1 - y0))))
    e.vista = {
      esc,
      x: (w - (x1 - x0) * esc) / 2 - x0 * esc,
      y: (h - (y1 - y0) * esc) / 2 - y0 * esc,
    }
  }
  function aproximar(fator, cx, cy) {
    const esc = Math.min(2.5, Math.max(0.3, e.vista.esc * fator))
    const k = esc / e.vista.esc
    e.vista = { esc, x: cx - (cx - e.vista.x) * k, y: cy - (cy - e.vista.y) * k }
    desenhar()
  }

  const acoes = {
    desfazer() {
      if (!e.passado.length) return
      e.futuro.push(copiar({ nos: e.nos, fios: e.fios }))
      Object.assign(e, e.passado.pop())
      e.sel = null
      enviar()
    },
    refazer() {
      if (!e.futuro.length) return
      e.passado.push(copiar({ nos: e.nos, fios: e.fios }))
      Object.assign(e, e.futuro.pop())
      e.sel = null
      enviar()
    },
    mais() {
      const r = svg.getBoundingClientRect()
      aproximar(1.2, r.width / 2, r.height / 2)
    },
    menos() {
      const r = svg.getBoundingClientRect()
      aproximar(1 / 1.2, r.width / 2, r.height / 2)
    },
    ver() {
      ajustarVista()
      desenhar()
    },
    organizar() {
      guardar()
      organizar()
      ajustarVista()
      enviar()
    },
  }

  // ---- desenho
  function caminho(a, b) {
    const d = Math.max(36, Math.abs(b[0] - a[0]) / 2)
    return `M ${a[0]} ${a[1]} C ${a[0] + d} ${a[1]}, ${b[0] - d} ${b[1]}, ${b[0]} ${b[1]}`
  }
  function pontaDoFio(f) {
    const de = noPorId(f.de)
    const para = noPorId(f.para)
    if (!de || !para) return null
    const i = bloco(de).saidas.findIndex((p) => p.chave === f.saida)
    const j = bloco(para).entradas.findIndex((p) => p.chave === f.entrada)
    if (i < 0 || j < 0) return null
    return { a: portaXY(de, "s", i), b: portaXY(para, "e", j), tipo: bloco(de).saidas[i].tipo }
  }
  function compativel(lado, porta, no) {
    const p = e.gesto?.tipo === "fio" ? e.gesto : e.pendente
    if (!p) return null
    if (p.lado === lado || p.no === no.id) return false
    const outro = p.lado === "s"
      ? bloco(noPorId(p.no)).saidas.find((x) => x.chave === p.chave)
      : bloco(noPorId(p.no)).entradas.find((x) => x.chave === p.chave)
    return lado === "e" ? liga(outro, porta) : liga(porta, outro)
  }
  function desenharPorta(no, lado, p, i) {
    const [x, y] = portaXY(no, lado, i)
    const estado = compativel(lado, p, no)
    const extra = estado === false ? " apagada" : estado === true ? " pode" : ""
    const tx = lado === "e" ? x + 10 : x - 10
    const ancora = lado === "e" ? "start" : "end"
    return `<circle class="porta t-${p.tipo}${extra}" data-porta="${lado}:${no.id}:${p.chave}" cx="${x}" cy="${y}" r="6.5"/>
      <text class="rotulo" x="${tx}" y="${y + 4}" text-anchor="${ancora}">${escapar(p.rotulo)}</text>`
  }
  function desenharBloco(no) {
    const b = bloco(no)
    const h = altura(no)
    const grupo = CLASSE_DO_GRUPO[b.grupo] ?? "g-secao"
    const erro = e.marcas.erros?.[no.id]
    const sel = e.sel?.no === no.id
    const resposta = no.tipo === "resultado" ? e.marcas.resposta : ""
    let s = `<g class="no${sel ? " sel" : ""}${erro ? " errado" : ""}" data-no="${no.id}">
      <rect class="corpo" x="${no.x}" y="${no.y}" width="${LARGURA}" height="${h}" rx="8"/>
      <path class="cab ${grupo}" d="M ${no.x} ${no.y + CABECA} v ${-CABECA + 8} q 0 -8 8 -8 h ${LARGURA - 16} q 8 0 8 8 v ${CABECA - 8} z"/>
      <text class="nome" x="${no.x + 10}" y="${no.y + 17.5}">${escapar(b.nome)}</text>
      <text class="fecha" data-fecha="${no.id}" x="${no.x + LARGURA - 18}" y="${no.y + 18.5}">×</text>
      <text class="${resposta ? "resposta" : "formula"}" x="${no.x + 10}" y="${no.y + CABECA + 15}">${escapar(resposta || e.marcas.faces?.[no.id] || b.formula)}</text>`
    b.entradas.forEach((p, i) => { s += desenharPorta(no, "e", p, i) })
    b.saidas.forEach((p, i) => { s += desenharPorta(no, "s", p, i) })
    if (erro) {
      const texto = erro.length > 34 ? `${erro.slice(0, 33)}…` : erro
      s += `<text class="erro" x="${no.x + 10}" y="${no.y + h - 9}">${escapar(texto)}<title>${escapar(erro)}</title></text>`
    }
    return `${s}<title>${escapar(erro || b.dica)}</title></g>`
  }
  function desenhar() {
    let s = ""
    e.fios.forEach((f, i) => {
      const p = pontaDoFio(f)
      if (!p) return
      const d = caminho(p.a, p.b)
      s += `<path class="fio t-${p.tipo}${e.sel?.fio === i ? " sel" : ""}" d="${d}"/><path class="toque" data-fio="${i}" d="${d}"/>`
    })
    for (const no of e.nos) s += desenharBloco(no)
    const g = e.gesto
    if (g?.tipo === "fio" && g.ponta) {
      const no = noPorId(g.no)
      const lista = g.lado === "s" ? bloco(no).saidas : bloco(no).entradas
      const i = lista.findIndex((p) => p.chave === g.chave)
      const base = portaXY(no, g.lado, i)
      const d = g.lado === "s" ? caminho(base, g.ponta) : caminho(g.ponta, base)
      s += `<path class="fio solto t-${lista[i].tipo}" d="${d}"/>`
    }
    svg.innerHTML = `<g transform="translate(${e.vista.x} ${e.vista.y}) scale(${e.vista.esc})">${s}</g>`
  }

  // ---- ponteiro
  function portaEm(ev) {
    const alvo = ev.target.closest?.("[data-porta]")
    if (alvo) {
      const [lado, no, chave] = alvo.dataset.porta.split(":")
      return { lado, no, chave }
    }
    // Bolinha é pequena no celular: vale a mais perto dentro do alcance.
    const [x, y] = mundo(ev)
    const raio = TOQUE_PORTA / e.vista.esc
    for (const no of e.nos) {
      const b = bloco(no)
      for (const [lado, lista] of [["e", b.entradas], ["s", b.saidas]]) {
        for (let i = 0; i < lista.length; i += 1) {
          const [px, py] = portaXY(no, lado, i)
          if (Math.hypot(px - x, py - y) < raio) return { lado, no: no.id, chave: lista[i].chave }
        }
      }
    }
    return null
  }
  function concluir(a, b) {
    if (!a || !b || a.lado === b.lado) return false
    const [saida, entrada] = a.lado === "s" ? [a, b] : [b, a]
    guardar()
    if (!ligar(saida.no, saida.chave, entrada.no, entrada.chave)) {
      e.passado.pop()
      dica.textContent = "Essas duas bolinhas não ligam: as grandezas são diferentes, ou o fio fecharia um laço."
      return false
    }
    enviar()
    return true
  }

  svg.addEventListener("pointerdown", (ev) => {
    svg.focus({ preventScroll: true })
    try {
      svg.setPointerCapture(ev.pointerId)
    } catch {
      // ponteiro sintético não captura, e o gesto segue pelos eventos do próprio svg
    }
    const fecha = ev.target.closest?.("[data-fecha]")
    if (fecha) {
      e.sel = { no: fecha.dataset.fecha }
      apagar()
      return
    }
    const porta = portaEm(ev)
    if (porta) {
      if (e.pendente && concluir(e.pendente, porta)) {
        e.pendente = null
        return
      }
      e.pendente = null
      if (porta.lado === "e") {
        // Puxar uma entrada já ligada solta o fio da ponta: dá para mudar de lugar.
        const f = e.fios.findIndex((x) => x.para === porta.no && x.entrada === porta.chave)
        const varias = bloco(noPorId(porta.no)).entradas.find((p) => p.chave === porta.chave).varias
        if (f >= 0 && !varias) {
          guardar()
          const [antigo] = e.fios.splice(f, 1)
          e.gesto = { tipo: "fio", lado: "s", no: antigo.de, chave: antigo.saida, ponta: mundo(ev), soltou: true }
          desenhar()
          return
        }
      }
      e.gesto = { tipo: "fio", ...porta, ponta: null, inicio: [ev.clientX, ev.clientY] }
      desenhar()
      return
    }
    e.pendente = null
    const fio = ev.target.closest?.("[data-fio]")
    if (fio) {
      e.sel = { fio: Number(fio.dataset.fio) }
      dica.textContent = "Fio selecionado: Delete apaga."
      desenhar()
      return
    }
    const alvo = ev.target.closest?.("[data-no]")
    if (alvo) {
      const no = noPorId(alvo.dataset.no)
      e.sel = { no: no.id }
      dica.textContent = bloco(no).dica
      e.nos = [...e.nos.filter((n) => n !== no), no]
      e.gesto = { tipo: "mover", no, base: [no.x, no.y], inicio: mundo(ev), moveu: false }
      svg.classList.add("puxando")
      desenhar()
      return
    }
    e.sel = null
    dica.textContent = DICA
    e.gesto = { tipo: "pan", inicio: [ev.clientX, ev.clientY], vista: { ...e.vista } }
    svg.classList.add("puxando")
    desenhar()
  })
  svg.addEventListener("pointermove", (ev) => {
    const g = e.gesto
    if (!g) return
    if (g.tipo === "pan") {
      e.vista = {
        ...g.vista,
        x: g.vista.x + ev.clientX - g.inicio[0],
        y: g.vista.y + ev.clientY - g.inicio[1],
      }
    } else if (g.tipo === "mover") {
      const [x, y] = mundo(ev)
      const [dx, dy] = [x - g.inicio[0], y - g.inicio[1]]
      if (!g.moveu && Math.hypot(dx, dy) * e.vista.esc < 4) return
      if (!g.moveu) {
        guardar()
        g.moveu = true
      }
      g.no.x = Math.round(g.base[0] + dx)
      g.no.y = Math.round(g.base[1] + dy)
    } else if (g.tipo === "fio") {
      if (!g.ponta && g.inicio && Math.hypot(ev.clientX - g.inicio[0], ev.clientY - g.inicio[1]) < 5) return
      g.ponta = mundo(ev)
    }
    desenhar()
  })
  svg.addEventListener("pointerup", (ev) => {
    const g = e.gesto
    e.gesto = null
    svg.classList.remove("puxando")
    if (!g) return
    if (g.tipo === "mover" && g.moveu) {
      enviar()
      return
    }
    if (g.tipo === "fio") {
      const alvo = svg.getRootNode().elementFromPoint?.(ev.clientX, ev.clientY)
      const destino = portaEm({ target: alvo ?? ev.target, clientX: ev.clientX, clientY: ev.clientY })
      if (destino && destino.no !== g.no && concluir(g, destino)) return
      if (g.soltou) {
        enviar() // o fio puxado para o vazio fica apagado
        return
      }
      if (!g.ponta) {
        e.pendente = { lado: g.lado, no: g.no, chave: g.chave }
        dica.textContent = "Agora clique na outra bolinha."
      }
    }
    desenhar()
  })
  svg.addEventListener("wheel", (ev) => {
    if (!ev.ctrlKey) return
    ev.preventDefault()
    const [x, y] = noPonteiro(ev)
    aproximar(ev.deltaY < 0 ? 1.1 : 1 / 1.1, x, y)
  }, { passive: false })
  svg.addEventListener("keydown", (ev) => {
    const ctrl = ev.ctrlKey || ev.metaKey
    if (ev.key === "Delete" || ev.key === "Backspace") {
      ev.preventDefault()
      apagar()
    } else if (ev.key === "Escape") {
      e.pendente = null
      e.sel = null
      desenhar()
    } else if (ctrl && ev.key.toLowerCase() === "z") {
      ev.preventDefault()
      acoes.desfazer()
    } else if (ctrl && ev.key.toLowerCase() === "y") {
      ev.preventDefault()
      acoes.refazer()
    }
  })
  raiz.querySelectorAll("[data-a]").forEach((b) => {
    b.addEventListener("click", () => acoes[b.dataset.a]())
  })

  function montarPaleta(lista) {
    const grupos = new Map()
    for (const b of lista) {
      if (!grupos.has(b.grupo)) grupos.set(b.grupo, [])
      grupos.get(b.grupo).push(b)
    }
    paleta.replaceChildren(
      ...[...grupos].map(([nome, blocos]) => {
        const g = document.createElement("div")
        g.className = `grupo ${CLASSE_DO_GRUPO[nome] ?? ""}`
        const r = document.createElement("span")
        r.className = "rot"
        r.textContent = nome
        g.append(r)
        for (const b of blocos) {
          const botao = document.createElement("button")
          botao.type = "button"
          botao.textContent = b.nome
          botao.title = `${b.dica} ${b.formula}`
          botao.addEventListener("click", () => acrescentar(b.chave))
          g.append(botao)
        }
        return g
      }),
    )
  }

  e.receber = (dados) => {
    const lista = dados.catalogo ?? []
    const assinatura = JSON.stringify(lista.map((b) => b.chave))
    if (assinatura !== e.assinatura) {
      e.assinatura = assinatura
      e.catalogo = Object.fromEntries(lista.map((b) => [b.chave, b]))
      montarPaleta(lista)
    }
    const novo = dados.grafo ?? { nos: [], fios: [] }
    if (dados.versao >= e.versao) {
      const conhecidos = (novo.nos ?? []).filter((n) => e.catalogo[n.tipo])
      if (JSON.stringify({ nos: conhecidos, fios: novo.fios ?? [] }) !== JSON.stringify({ nos: e.nos, fios: e.fios })) {
        if (e.versao >= 0) guardar()
        e.nos = copiar(conhecidos)
        e.fios = copiar(novo.fios ?? [])
        e.sel = null
      }
      e.versao = dados.versao
    }
    e.marcas = dados.marcas ?? {}
    if (e.verAjuste !== dados.ajustar) {
      e.verAjuste = dados.ajustar
      ajustarVista()
    }
    desenhar()
  }

  new ResizeObserver(() => {
    if (e.ajustarAoMedir) ajustarVista()
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
