// Prancheta do equilíbrio: a peça, os apoios e as cargas nas unidades da tela, com y para cima.
// O Python é o dono das contas: aqui só nasce o desenho, que vai para lá a cada gesto terminado, e
// as reações voltam em `marcas`. O estado fica preso ao parentElement, porque o Streamlit chama esta
// função de novo a cada rodada.

const ESTADOS = new WeakMap()
const IMA_PX = 10
const ALCA_PX = 6
const TOQUE_PX = 11
const SETA_PX = 66

const PINO = "Pino"
const ROLETE = "Rolete"
const SIMPLES = "Apoio simples"
const ATRITO = "Apoio com atrito"
const ENGASTE = "Engaste"
const GUIA = "Guia"
const CABO = "Cabo"
const BIELA = "Biela"
const FORCA = "Força"
const MOMENTO = "Momento"
const DISTRIBUIDA = "Distribuída"
const PESO = "Peso"
const APOIOS = [PINO, ROLETE, SIMPLES, ATRITO, ENGASTE, GUIA, CABO, BIELA]
const CARGAS = [FORCA, MOMENTO, DISTRIBUIDA, PESO]
const GRADES = {
  mm: [1, 5, 10, 25, 50, 100],
  cm: [0.5, 1, 2, 5, 10],
  m: [0.01, 0.05, 0.1, 0.25, 0.5, 1],
}
const DICA = {
  mover: "Arraste apoios e cargas. Alça laranja muda a ponta ou a direção. Ctrl + rodinha aproxima.",
  trecho: "Clique em cada ponto da peça. Duplo clique ou Enter termina.",
  [PINO]: "Clique na peça: o pino segura as duas direções e deixa girar.",
  [ROLETE]: "Clique na peça: o rolete segura uma direção, para os dois lados.",
  [SIMPLES]: "Clique na peça: o apoio simples só empurra.",
  [ATRITO]: "Clique na peça: empurra e segura de lado até o limite do atrito.",
  [ENGASTE]: "Clique na peça: o engaste segura tudo, inclusive o giro.",
  [GUIA]: "Clique na peça: a guia deixa correr e segura o lado e o giro.",
  [CABO]: "Arraste da peça até o ponto onde o cabo prende.",
  [BIELA]: "Arraste da peça até o ponto onde a haste prende.",
  [FORCA]: "Clique na peça para uma força para baixo, ou arraste no sentido da força.",
  [MOMENTO]: "Clique no ponto do momento.",
  [DISTRIBUIDA]: "Clique num trecho para carregar ele inteiro, ou arraste do início ao fim.",
  [PESO]: "Clique no centro de gravidade.",
  corte: "Clique na peça onde você quer N, V e M.",
}

const copiar = (v) => JSON.parse(JSON.stringify(v))
const arred = (v) => Math.round(v * 10000) / 10000
const texto = (v) => String(arred(v)).replace(".", ",")
const lerNumero = (s) => Number(String(s).trim().replace(",", "."))
const rad = (g) => (g * Math.PI) / 180
const grau = (r) => (r * 180) / Math.PI
const direcao = (g) => [Math.cos(rad(g)), Math.sin(rad(g))]
const temPonta = (a) => a.tipo === CABO || a.tipo === BIELA

function dirApoio(a) {
  if (temPonta(a) && a.x2 !== null && a.x2 !== undefined) {
    const d = Math.hypot(a.x2 - a.x, a.y2 - a.y) || 1
    return [(a.x2 - a.x) / d, (a.y2 - a.y) / d]
  }
  return direcao(a.angulo)
}

function pertoDoTrecho(x, y, t) {
  const dx = t.x2 - t.x1
  const dy = t.y2 - t.y1
  const l2 = dx * dx + dy * dy || 1
  const s = Math.min(Math.max(((x - t.x1) * dx + (y - t.y1) * dy) / l2, 0), 1)
  const qx = t.x1 + s * dx
  const qy = t.y1 + s * dy
  return { d: Math.hypot(x - qx, y - qy), s, qx, qy }
}

function criar(raiz) {
  const svg = raiz.querySelector("svg")
  const painel = raiz.querySelector("[data-painel]")
  const infoXY = raiz.querySelector('[data-i="xy"]')
  const infoDica = raiz.querySelector('[data-i="dica"]')
  const seletorGrade = raiz.querySelector('[data-c="grade"]')

  const e = {
    enviar: null,
    dados: { trechos: [], apoios: [], cargas: [], cortes: [] },
    versao: -1,
    verAjuste: null,
    marcas: null,
    u: { c: "m", f: "kN", m: "kN·m", q: "kN/m" },
    ferramenta: "mover",
    sel: null,
    grade: 0.1,
    vista: { cx: 0, cy: 0, esc: 100 },
    gesto: null,
    cadeia: null,
    pendente: null,
    ponteiro: null,
    ima: null,
    passado: [],
    futuro: [],
    ultimo: {},
    focar: false,
  }

  const tela = () => {
    const r = svg.getBoundingClientRect()
    return { w: r.width || 800, h: r.height || 540 }
  }
  const px = (x, y) => {
    const { w, h } = tela()
    return [w / 2 + (x - e.vista.cx) * e.vista.esc, h / 2 - (y - e.vista.cy) * e.vista.esc]
  }
  const mundo = (ev) => {
    const r = svg.getBoundingClientRect()
    const { w, h } = tela()
    return [
      e.vista.cx + (ev.clientX - r.left - w / 2) / e.vista.esc,
      e.vista.cy - (ev.clientY - r.top - h / 2) / e.vista.esc,
    ]
  }
  const noPonteiro = (ev) => {
    const r = svg.getBoundingClientRect()
    return [ev.clientX - r.left, ev.clientY - r.top]
  }
  const naGrade = (v) => arred(Math.round(v / e.grade) * e.grade)
  const item = () => (e.sel ? e.dados[e.sel.lista][e.sel.i] : null)

  // ---- ímã: pontas e cantos, depois o eixo da peça, depois a grade
  function pontosDoIma(fora) {
    const lista = []
    e.dados.trechos.forEach((t, i) => {
      if (fora?.lista === "trechos" && fora.i === i) return
      lista.push([t.x1, t.y1], [t.x2, t.y2], [(t.x1 + t.x2) / 2, (t.y1 + t.y2) / 2])
    })
    for (const nome of ["apoios", "cargas"]) {
      e.dados[nome].forEach((a, i) => {
        if (fora?.lista === nome && fora.i === i) return
        lista.push([a.x, a.y])
        if (a.tipo === DISTRIBUIDA) lista.push([a.x2, a.y2])
      })
    }
    return lista
  }
  function iman(x, y, fora = null) {
    const limite = IMA_PX / e.vista.esc
    let melhor = null
    let dist = limite
    for (const [a, b] of pontosDoIma(fora)) {
      const d = Math.hypot(a - x, b - y)
      if (d < dist) {
        dist = d
        melhor = [arred(a), arred(b)]
      }
    }
    if (melhor) {
      e.ima = melhor
      return { p: melhor, peca: true, trecho: null }
    }
    let achado = null
    dist = limite
    e.dados.trechos.forEach((t, i) => {
      if (fora?.lista === "trechos" && fora.i === i) return
      const k = pertoDoTrecho(x, y, t)
      if (k.d < dist) {
        dist = k.d
        achado = { t, ...k }
      }
    })
    if (achado) {
      const { t } = achado
      const l = Math.hypot(t.x2 - t.x1, t.y2 - t.y1) || 1
      const s = Math.min(Math.max((Math.round((achado.s * l) / e.grade) * e.grade) / l, 0), 1)
      const p = [arred(t.x1 + s * (t.x2 - t.x1)), arred(t.y1 + s * (t.y2 - t.y1))]
      e.ima = p
      return { p, peca: true, trecho: t }
    }
    e.ima = null
    return { p: [naGrade(x), naGrade(y)], peca: false, trecho: null }
  }
  function trechoEm(x, y) {
    const limite = (TOQUE_PX * 1.2) / e.vista.esc
    let melhor = null
    let dist = limite
    for (const t of e.dados.trechos) {
      const k = pertoDoTrecho(x, y, t)
      if (k.d < dist) {
        dist = k.d
        melhor = t
      }
    }
    return melhor
  }
  const anguloDoTrecho = (t) => (t ? grau(Math.atan2(t.y2 - t.y1, t.x2 - t.x1)) : 0)

  // ---- histórico e envio
  function guardar() {
    e.passado.push(copiar(e.dados))
    if (e.passado.length > 60) e.passado.shift()
    e.futuro = []
  }
  function enviar() {
    e.versao += 1
    e.enviar?.("edicao", { dados: copiar(e.dados), versao: e.versao })
    montarPainel()
    desenhar()
  }

  const acoes = {
    desfazer() {
      if (!e.passado.length) return
      e.futuro.push(copiar(e.dados))
      e.dados = e.passado.pop()
      e.sel = null
      enviar()
    },
    refazer() {
      if (!e.futuro.length) return
      e.passado.push(copiar(e.dados))
      e.dados = e.futuro.pop()
      e.sel = null
      enviar()
    },
    ajustar() {
      ajustarVista()
      desenhar()
    },
    maisPerto() {
      aproximar(1.3, e.vista.cx, e.vista.cy)
    },
    maisLonge() {
      aproximar(1 / 1.3, e.vista.cx, e.vista.cy)
    },
    apagar() {
      if (!e.sel) return
      guardar()
      e.dados[e.sel.lista].splice(e.sel.i, 1)
      e.sel = null
      enviar()
    },
  }

  // ---- nomes e valores novos
  function nomeLivre(lista, gerar) {
    const usados = new Set(lista.map((v) => v.nome))
    for (let k = 0; ; k += 1) {
      const nome = gerar(k)
      if (!usados.has(nome)) return nome
    }
  }
  const letra = (k) => String.fromCharCode(65 + (k % 26)) + (k < 26 ? "" : String(Math.floor(k / 26)))
  function valorNovo(tipo) {
    if (e.ultimo[tipo] !== undefined) return e.ultimo[tipo]
    const base = { N: 1000, kN: 10, kgf: 100 }[e.u.f]
    if (tipo === FORCA) return base
    if (tipo === MOMENTO) return base / 2
    if (tipo === DISTRIBUIDA) return base / 5 / { mm: 1000, cm: 100, m: 1 }[e.u.c]
    return 100
  }
  function anguloNovoDoApoio(tipo, x, y) {
    if (tipo !== ENGASTE) return 90
    for (const t of e.dados.trechos) {
      if (Math.hypot(t.x1 - x, t.y1 - y) < 1e-9) return arred(grau(Math.atan2(t.y2 - y, t.x2 - x)))
      if (Math.hypot(t.x2 - x, t.y2 - y) < 1e-9) return arred(grau(Math.atan2(t.y1 - y, t.x1 - x)))
    }
    return 90
  }
  function criarApoio(tipo, x, y, ponta = null) {
    guardar()
    e.dados.apoios.push({
      nome: nomeLivre(e.dados.apoios, letra),
      tipo,
      x,
      y,
      angulo: ponta ? arred(grau(Math.atan2(ponta[1] - y, ponta[0] - x))) : anguloNovoDoApoio(tipo, x, y),
      x2: ponta ? ponta[0] : null,
      y2: ponta ? ponta[1] : null,
      mu: tipo === ATRITO ? 0.3 : null,
    })
    selecionar("apoios", e.dados.apoios.length - 1)
  }
  function criarCarga(tipo, x, y, extra = {}) {
    guardar()
    const prefixo = { [FORCA]: "F", [MOMENTO]: "M", [DISTRIBUIDA]: "q", [PESO]: "P" }[tipo]
    const valor = valorNovo(tipo)
    e.dados.cargas.push({
      nome: nomeLivre(e.dados.cargas, (k) => `${prefixo}${k + 1}`),
      tipo,
      x,
      y,
      valor,
      angulo: -90,
      x2: null,
      y2: null,
      valor2: tipo === DISTRIBUIDA ? valor : null,
      ...extra,
    })
    selecionar("cargas", e.dados.cargas.length - 1)
  }
  function selecionar(lista, i) {
    e.sel = { lista, i }
    e.focar = true
    trocarFerramenta("mover")
    enviar()
  }
  function terminarCadeia() {
    const lista = e.cadeia
    e.cadeia = null
    e.ponteiro = null
    if (lista && lista.length > 1) {
      guardar()
      for (let i = 1; i < lista.length; i += 1) {
        const [a, b] = lista[i - 1]
        const [c, d] = lista[i]
        if (a !== c || b !== d) e.dados.trechos.push({ x1: a, y1: b, x2: c, y2: d })
      }
      e.sel = null
      trocarFerramenta("mover")
      enviar()
      return
    }
    desenhar()
  }

  // ---- painel do item selecionado
  function campo(rotulo, valor, aplicar, dica, foco = false) {
    const r = document.createElement("label")
    r.className = "campo"
    r.title = dica
    r.append(rotulo)
    const entrada = document.createElement("input")
    entrada.type = "text"
    entrada.inputMode = "decimal"
    entrada.value = valor === null || valor === undefined ? "" : texto(valor)
    if (foco) entrada.dataset.foco = "1"
    entrada.addEventListener("change", () => {
      const n = lerNumero(entrada.value)
      if (!Number.isFinite(n) || entrada.value.trim() === "") {
        entrada.value = valor === null || valor === undefined ? "" : texto(valor)
        return
      }
      guardar()
      aplicar(n)
      enviar()
    })
    entrada.addEventListener("keydown", (ev) => {
      ev.stopPropagation()
      if (ev.key === "Enter") entrada.blur()
    })
    r.append(entrada)
    return r
  }
  function nomeDoItem(it) {
    const r = document.createElement("label")
    r.className = "campo"
    r.title = "Nome no desenho e nas tabelas"
    r.append("Nome")
    const entrada = document.createElement("input")
    entrada.type = "text"
    entrada.value = it.nome ?? ""
    entrada.style.width = "44px"
    entrada.addEventListener("change", () => {
      const v = entrada.value.trim()
      if (!v) {
        entrada.value = it.nome
        return
      }
      guardar()
      it.nome = v
      enviar()
    })
    entrada.addEventListener("keydown", (ev) => ev.stopPropagation())
    r.append(entrada)
    return r
  }
  function setas(rotulo, aplicar, dica) {
    const r = document.createElement("div")
    r.className = "bloco"
    r.title = dica
    for (const [txt, g] of [["↑", 90], ["→", 0], ["↓", -90], ["←", 180]]) {
      const b = document.createElement("button")
      b.type = "button"
      b.textContent = txt
      b.setAttribute("aria-label", `${rotulo} ${txt}`)
      b.addEventListener("click", () => {
        guardar()
        aplicar(g)
        enviar()
      })
      r.append(b)
    }
    return r
  }
  function botaoApagar() {
    const b = document.createElement("button")
    b.type = "button"
    b.textContent = "Apagar"
    b.title = "Apagar (Delete)"
    b.className = "solto perigo"
    b.addEventListener("click", () => acoes.apagar())
    return b
  }
  function escolhaDeTipo(it, tipos, depois) {
    const s = document.createElement("select")
    s.title = "Tipo"
    for (const t of tipos) {
      const o = document.createElement("option")
      o.textContent = t
      o.selected = t === it.tipo
      s.append(o)
    }
    s.addEventListener("change", () => {
      guardar()
      it.tipo = s.value
      depois()
      enviar()
    })
    return s
  }
  function pontaPadrao(a) {
    const [cx, cy] = direcao(a.angulo)
    const l = 80 / e.vista.esc
    a.x2 = arred(a.x + cx * l)
    a.y2 = arred(a.y + cy * l)
  }
  function painelDoApoio(a) {
    const un = e.u.c
    painel.append(
      escolhaDeTipo(a, APOIOS, () => {
        if (temPonta(a)) pontaPadrao(a)
        else a.x2 = a.y2 = null
        if (a.tipo === ATRITO) a.mu = a.mu ?? 0.3
      }),
      nomeDoItem(a),
      campo("x", a.x, (v) => { a.x = v }, `Posição em x (${un})`),
      campo("y", a.y, (v) => { a.y = v }, `Posição em y (${un})`),
    )
    if (temPonta(a)) {
      painel.append(
        campo("x₂", a.x2, (v) => { a.x2 = v }, `Outra ponta em x (${un})`),
        campo("y₂", a.y2, (v) => { a.y2 = v }, `Outra ponta em y (${un})`),
      )
    } else if (a.tipo !== PINO) {
      painel.append(
        campo("Empurra para (°)", a.angulo, (v) => { a.angulo = v }, "Direção da reação: 90° para cima"),
        setas("Empurra para", (g) => { a.angulo = g }, "Para onde o apoio empurra a peça"),
      )
    }
    if (a.tipo === ATRITO) {
      painel.append(campo("μ", a.mu, (v) => { if (v >= 0) a.mu = v }, "Coeficiente de atrito", true))
    }
  }
  function painelDaForca(c) {
    const [cx, cy] = direcao(c.angulo)
    const f = e.u.f
    painel.append(
      nomeDoItem(c),
      campo(`F (${f})`, c.valor, (v) => {
        c.valor = v
        e.ultimo[FORCA] = v
      }, "Módulo da força", true),
      campo("Ângulo (°)", c.angulo, (v) => { c.angulo = v }, "Para onde a força aponta: −90° para baixo"),
      setas("Força para", (g) => { c.angulo = g }, "Sentido da força"),
      campo(`Fx`, c.valor * cx, (v) => {
        const fy = c.valor * cy
        c.valor = arred(Math.hypot(v, fy))
        c.angulo = arred(grau(Math.atan2(fy, v)))
      }, `Parte horizontal (${f})`),
      campo(`Fy`, c.valor * cy, (v) => {
        const fx = c.valor * cx
        c.valor = arred(Math.hypot(fx, v))
        c.angulo = arred(grau(Math.atan2(v, fx)))
      }, `Parte vertical (${f})`),
      campo("x", c.x, (v) => { c.x = v }, `Posição em x (${e.u.c})`),
      campo("y", c.y, (v) => { c.y = v }, `Posição em y (${e.u.c})`),
    )
  }
  function painelDaCarga(c) {
    const un = e.u.c
    if (c.tipo === FORCA) {
      painelDaForca(c)
    } else if (c.tipo === MOMENTO) {
      painel.append(
        nomeDoItem(c),
        campo(`M (${e.u.m})`, c.valor, (v) => {
          c.valor = v
          e.ultimo[MOMENTO] = v
        }, "Positivo é anti-horário", true),
      )
      const inverter = document.createElement("button")
      inverter.type = "button"
      inverter.className = "solto"
      inverter.textContent = c.valor >= 0 ? "↺ anti-horário" : "↻ horário"
      inverter.title = "Inverter o sentido"
      inverter.addEventListener("click", () => {
        guardar()
        c.valor = -c.valor
        enviar()
      })
      painel.append(
        inverter,
        campo("x", c.x, (v) => { c.x = v }, `Posição em x (${un})`),
        campo("y", c.y, (v) => { c.y = v }, `Posição em y (${un})`),
      )
    } else if (c.tipo === PESO) {
      painel.append(
        nomeDoItem(c),
        campo("Massa (kg)", c.valor, (v) => {
          if (v < 0) return
          c.valor = v
          e.ultimo[PESO] = v
        }, "O peso sai da massa vezes g", true),
        campo("x", c.x, (v) => { c.x = v }, `Centro de gravidade em x (${un})`),
        campo("y", c.y, (v) => { c.y = v }, `Centro de gravidade em y (${un})`),
      )
    } else {
      painel.append(
        nomeDoItem(c),
        campo(`Início (${e.u.q})`, c.valor, (v) => {
          if (c.valor2 === c.valor) c.valor2 = v
          c.valor = v
          e.ultimo[DISTRIBUIDA] = v
        }, "Carga por comprimento no início", true),
        campo("Fim", c.valor2, (v) => { c.valor2 = v }, "Carga por comprimento no fim"),
        setas("Carga para", (g) => { c.angulo = g }, "Sentido da carga"),
        campo("x₁", c.x, (v) => { c.x = v }, `Início em x (${un})`),
        campo("y₁", c.y, (v) => { c.y = v }, `Início em y (${un})`),
        campo("x₂", c.x2, (v) => { c.x2 = v }, `Fim em x (${un})`),
        campo("y₂", c.y2, (v) => { c.y2 = v }, `Fim em y (${un})`),
      )
    }
  }
  function painelDoTrecho(t) {
    const un = e.u.c
    const l = Math.hypot(t.x2 - t.x1, t.y2 - t.y1)
    const a = grau(Math.atan2(t.y2 - t.y1, t.x2 - t.x1))
    const fim = (x, y) => {
      arrastarPonta(t.x2, t.y2, x, y)
    }
    painel.append(
      campo(`Comprimento (${un})`, l, (v) => {
        if (v <= 0) return
        const [cx, cy] = direcao(a)
        fim(arred(t.x1 + v * cx), arred(t.y1 + v * cy))
      }, "Muda a ponta final e o que estiver preso nela", true),
      campo("Ângulo (°)", a, (v) => {
        const [cx, cy] = direcao(v)
        fim(arred(t.x1 + l * cx), arred(t.y1 + l * cy))
      }, "Direção do trecho"),
      campo("x₁", t.x1, (v) => { t.x1 = v }, `Início em x (${un})`),
      campo("y₁", t.y1, (v) => { t.y1 = v }, `Início em y (${un})`),
      campo("x₂", t.x2, (v) => fim(v, t.y2), `Fim em x (${un})`),
      campo("y₂", t.y2, (v) => fim(t.x2, v), `Fim em y (${un})`),
    )
  }
  function painelDoCorte(c) {
    const un = e.u.c
    painel.append(
      nomeDoItem(c),
      campo("x", c.x, (v) => { c.x = v }, `Posição em x (${un})`),
      campo("y", c.y, (v) => { c.y = v }, `Posição em y (${un})`),
      campo("Barra a (°)", c.angulo, (v) => { c.angulo = v }, "Direção da barra neste ponto"),
    )
  }
  function montarPainel() {
    painel.replaceChildren()
    const it = item()
    if (!it) {
      const dica = document.createElement("span")
      dica.className = "apagado"
      const vazio = !e.dados.trechos.length && !e.dados.apoios.length && !e.dados.cargas.length
      dica.textContent = vazio
        ? "Escolha um modelo acima ou clique em Desenhar peça e marque os pontos aqui embaixo."
        : "Clique em um apoio, carga ou trecho para digitar os valores. Tudo gruda na peça sozinho."
      painel.append(dica)
      return
    }
    const titulo = document.createElement("span")
    titulo.className = "titulo"
    titulo.textContent = e.sel.lista === "trechos" ? "Trecho" : e.sel.lista === "cortes" ? "Seção" : it.tipo
    if (e.sel.lista !== "apoios") painel.append(titulo)
    if (e.sel.lista === "apoios") painelDoApoio(it)
    else if (e.sel.lista === "cargas") painelDaCarga(it)
    else if (e.sel.lista === "trechos") painelDoTrecho(it)
    else painelDoCorte(it)
    painel.append(botaoApagar())
    if (e.focar) {
      e.focar = false
      const alvo = painel.querySelector('[data-foco="1"]')
      alvo?.focus()
      alvo?.select()
    }
  }

  // ---- vista
  function aproximar(fator, x, y) {
    const esc = Math.min(Math.max(e.vista.esc * fator, 0.001), 20000)
    const k = e.vista.esc / esc
    e.vista = { cx: x + (e.vista.cx - x) * k, cy: y + (e.vista.cy - y) * k, esc }
    desenhar()
  }
  function pontosDoDesenho() {
    const lista = []
    for (const t of e.dados.trechos) lista.push([t.x1, t.y1], [t.x2, t.y2])
    for (const a of e.dados.apoios) {
      lista.push([a.x, a.y])
      if (temPonta(a) && a.x2 !== null) lista.push([a.x2, a.y2])
    }
    for (const c of e.dados.cargas) {
      lista.push([c.x, c.y])
      if (c.tipo === DISTRIBUIDA) lista.push([c.x2, c.y2])
    }
    return lista
  }
  function ajustarVista() {
    const { w, h } = tela()
    const lista = pontosDoDesenho()
    if (!lista.length) {
      const base = { mm: 1000, cm: 100, m: 4 }[e.u.c]
      e.vista = { cx: base / 2, cy: base / 4, esc: Math.min(w, h) / (base * 1.2) }
      return
    }
    const xs = lista.map((p) => p[0])
    const ys = lista.map((p) => p[1])
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
    const lx = Math.max(x1 - x0, 1e-6)
    const ly = Math.max(y1 - y0, 1e-6)
    const maior = Math.max(lx, ly)
    e.vista = {
      cx: (x0 + x1) / 2,
      cy: (y0 + y1) / 2,
      esc: Math.min((w - 260) / Math.max(lx, maior * 0.2), (h - 230) / Math.max(ly, maior * 0.2)),
    }
  }

  // ---- desenho
  function seta(a, b, cls, ponta = 10) {
    const dx = b[0] - a[0]
    const dy = b[1] - a[1]
    const l = Math.hypot(dx, dy) || 1
    const [ux, uy] = [dx / l, dy / l]
    const base = [b[0] - ux * ponta, b[1] - uy * ponta]
    const m = ponta * 0.45
    return `<line class="${cls}" x1="${a[0]}" y1="${a[1]}" x2="${base[0]}" y2="${base[1]}"/>
      <polygon class="${cls}-p" points="${b.join(",")} ${base[0] - uy * m},${base[1] + ux * m} ${base[0] + uy * m},${base[1] - ux * m}"/>`
  }
  function arco(p, valor, cls, raio = 22) {
    const positivo = valor >= 0
    const [x0, y0] = [p[0] + raio * Math.cos(rad(40)), p[1] + raio * Math.sin(rad(40))]
    const [x1, y1] = [p[0] + raio * Math.cos(rad(-50)), p[1] + raio * Math.sin(rad(-50))]
    const fim = positivo ? [x0, y0] : [x1, y1]
    const dir = positivo ? rad(40 + 90) : rad(-50 - 90)
    const antes = [fim[0] - Math.cos(dir) * 9, fim[1] - Math.sin(dir) * 9]
    return `<path class="${cls}" d="M ${x1} ${y1} A ${raio} ${raio} 0 1 1 ${x0} ${y0}"/>${seta(antes, fim, cls, 8)}`
  }
  function simbolo(a) {
    const [x, y] = px(a.x, a.y)
    const [cx, cy] = dirApoio(a)
    const giro = 90 - grau(Math.atan2(cy, cx))
    const hachura = (y0, x0 = -20, x1 = 20) => {
      let s = `<line class="ap" x1="${x0}" y1="${y0}" x2="${x1}" y2="${y0}"/>`
      for (let k = x0 + 4; k <= x1; k += 8) s += `<line class="ap-f" x1="${k}" y1="${y0}" x2="${k - 6}" y2="${y0 + 7}"/>`
      return s
    }
    let s = ""
    if (a.tipo === PINO) {
      s = `<polygon class="ap-c" points="0,0 -13,22 13,22"/>${hachura(22)}<circle class="ap-c" r="4"/>`
    } else if (a.tipo === ROLETE) {
      s = `<polygon class="ap-c" points="0,0 -13,20 13,20"/><circle class="ap-c" cx="-8" cy="25" r="4.5"/><circle class="ap-c" cx="8" cy="25" r="4.5"/>${hachura(30)}<circle class="ap-c" r="4"/>`
    } else if (a.tipo === SIMPLES) {
      s = `${hachura(7, -24, 24)}<line class="ap" x1="0" y1="0" x2="0" y2="7"/>`
    } else if (a.tipo === ATRITO) {
      s = `${hachura(7, -24, 24)}<line class="ap" x1="0" y1="0" x2="0" y2="7"/><text class="ap-t" x="30" y="12">μ</text>`
    } else if (a.tipo === ENGASTE) {
      s = hachura(0, -26, 26).replaceAll('class="ap"', 'class="ap-g"')
    } else if (a.tipo === GUIA) {
      s = `<line class="ap" x1="-24" y1="-9" x2="24" y2="-9"/><line class="ap" x1="-24" y1="9" x2="24" y2="9"/><rect class="ap-c" x="-7" y="-7" width="14" height="14"/>`
    }
    return `<g transform="translate(${x} ${y}) rotate(${giro})">${s}</g>`
  }
  function barraDePonta(a) {
    const p = px(a.x, a.y)
    const [cx, cy] = dirApoio(a)
    const fim = a.x2 !== null && a.x2 !== undefined ? px(a.x2, a.y2) : [p[0] + cx * 80, p[1] - cy * 80]
    const giro = 90 - grau(Math.atan2(-cy, -cx))
    return `<line class="${a.tipo === CABO ? "cabo" : "biela"}" x1="${p[0]}" y1="${p[1]}" x2="${fim[0]}" y2="${fim[1]}"/>
      <g transform="translate(${fim[0]} ${fim[1]}) rotate(${giro})"><polygon class="ap-c" points="0,0 -10,16 10,16"/></g>
      <circle class="ap-c" cx="${p[0]}" cy="${p[1]}" r="4"/>`
  }
  function desenhoDaDistribuida(c, marcado) {
    const [ux, uy] = direcao(c.angulo)
    const maior = Math.max(Math.abs(c.valor), Math.abs(c.valor2 ?? c.valor), 1e-12)
    const topo = []
    let s = ""
    const n = 8
    for (let k = 0; k <= n; k += 1) {
      const q = k / n
      const w = c.valor + ((c.valor2 ?? c.valor) - c.valor) * q
      const pp = px(c.x + (c.x2 - c.x) * q, c.y + (c.y2 - c.y) * q)
      const l = (Math.abs(w) / maior) * 44
      const sinal = w >= 0 ? 1 : -1
      const cauda = [pp[0] - sinal * ux * l, pp[1] + sinal * uy * l]
      topo.push(cauda)
      if (l > 8) s += seta(cauda, pp, marcado ? "carga sel" : "carga", 7)
    }
    s += `<polyline class="carga-l" points="${topo.map((v) => v.join(",")).join(" ")}"/>`
    const meio = topo[Math.floor(topo.length / 2)]
    const fim = c.valor2 ?? c.valor
    const rotulo = fim === c.valor ? `${c.nome} = ${texto(c.valor)} ${e.u.q}` : `${c.nome} = ${texto(c.valor)} a ${texto(fim)} ${e.u.q}`
    s += `<text class="carga-t" x="${meio[0] - ux * 14}" y="${meio[1] + uy * 14 + 4}" text-anchor="middle">${rotulo}</text>`
    return s
  }
  function desenhoDaCarga(c, marcado) {
    const p = px(c.x, c.y)
    const cls = marcado ? "carga sel" : "carga"
    if (c.tipo === DISTRIBUIDA) return desenhoDaDistribuida(c, marcado)
    if (c.tipo === MOMENTO) {
      return `${arco(p, c.valor, cls)}<text class="carga-t" x="${p[0]}" y="${p[1] - 30}" text-anchor="middle">${c.nome} = ${texto(Math.abs(c.valor))} ${e.u.m}</text>`
    }
    const [ux, uy] = c.tipo === PESO ? [0, -1] : direcao(c.angulo)
    const sinal = c.tipo === FORCA && c.valor < 0 ? -1 : 1
    const cauda = [p[0] - sinal * ux * SETA_PX, p[1] + sinal * uy * SETA_PX]
    const un = c.tipo === PESO ? "kg" : e.u.f
    const extra = c.tipo === PESO ? `<circle class="carga-g" cx="${p[0]}" cy="${p[1]}" r="5"/>` : ""
    const folga = 8 + 38 * Math.abs(ux) // texto largo na seta deitada
    const [tx, ty] = [cauda[0] - sinal * ux * folga, cauda[1] + sinal * uy * 8 + (uy < 0 ? -4 : 12)]
    return `${seta(cauda, p, cls)}${extra}<text class="carga-t" x="${tx}" y="${ty}" text-anchor="middle">${c.nome} = ${texto(c.valor)} ${un}</text>`
  }
  function desenhoDaReacao(r) {
    const p = px(r.x, r.y)
    const m = Math.hypot(r.fx, r.fy)
    const cls = r.ruim ? "ruim" : "reacao"
    let s = ""
    if (m > 0) {
      const [ux, uy] = [r.fx / m, r.fy / m]
      const longe = [p[0] + ux * 60, p[1] - uy * 60]
      const perto = [p[0] - ux * 60, p[1] + uy * 60]
      const [a, b] = r.puxa ? [p, longe] : [perto, p]
      const fora = r.puxa ? longe : perto
      const [tx, ty] = [fora[0] + (fora[0] - p[0]) * 0.2, fora[1] + (fora[1] - p[1]) * 0.25 + 4]
      s += `${seta(a, b, cls, 11)}<text class="${cls}-t" x="${tx}" y="${ty}" text-anchor="middle">${r.texto}</text>`
    }
    if (Math.abs(r.m) > 0) {
      s += `${arco(p, r.m, cls, 32)}<text class="${cls}-t" x="${p[0] + 40}" y="${p[1] - 26}">${r.texto_m}</text>`
    }
    return s
  }
  function cotas() {
    const xs = new Set()
    const pts = pontosDoDesenho()
    if (pts.length < 2) return ""
    for (const a of e.dados.apoios) xs.add(arred(a.x))
    for (const c of e.dados.cargas) {
      xs.add(arred(c.x))
      if (c.tipo === DISTRIBUIDA) xs.add(arred(c.x2))
    }
    for (const t of e.dados.trechos) xs.add(arred(t.x1)).add(arred(t.x2))
    const lista = [...xs].sort((a, b) => a - b)
    const base = Math.min(...pts.map((p) => p[1]))
    const yy = px(0, base)[1] + 72
    let s = ""
    for (let i = 1; i < lista.length; i += 1) {
      const a = px(lista[i - 1], 0)[0]
      const b = px(lista[i], 0)[0]
      if (b - a < 2) continue
      s += `<line class="cota" x1="${a}" y1="${yy}" x2="${b}" y2="${yy}"/><line class="cota" x1="${a}" y1="${yy - 4}" x2="${a}" y2="${yy + 4}"/><line class="cota" x1="${b}" y1="${yy - 4}" x2="${b}" y2="${yy + 4}"/>`
      if (b - a > 34) s += `<text class="cota-t" x="${(a + b) / 2}" y="${yy + 15}" text-anchor="middle">${texto(lista[i] - lista[i - 1])}</text>`
    }
    return s
  }
  function desenhar() {
    const { w, h } = tela()
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`)
    const esc = e.vista.esc
    const base = 10 ** Math.floor(Math.log10(14 / esc))
    const passo = [1, 2, 5, 10].map((k) => k * base).find((p) => p * esc >= 14)
    const grosso = passo * 5
    let s = ""
    const vis = {
      x0: e.vista.cx - w / 2 / esc,
      x1: e.vista.cx + w / 2 / esc,
      y0: e.vista.cy - h / 2 / esc,
      y1: e.vista.cy + h / 2 / esc,
    }
    const classe = (v) =>
      Math.abs(v) < passo / 100 ? "g-eixo" : Math.abs(v / grosso - Math.round(v / grosso)) < 1e-6 ? "g-maior" : "g-menor"
    for (let v = Math.ceil(vis.x0 / passo) * passo; v <= vis.x1; v += passo) {
      const [x] = px(v, 0)
      s += `<line class="${classe(v)}" x1="${x}" y1="0" x2="${x}" y2="${h}"/>`
    }
    for (let v = Math.ceil(vis.y0 / passo) * passo; v <= vis.y1; v += passo) {
      const [, y] = px(0, v)
      s += `<line class="${classe(v)}" x1="0" y1="${y}" x2="${w}" y2="${y}"/>`
    }
    const marcado = (lista, i) => e.sel?.lista === lista && e.sel.i === i
    e.dados.trechos.forEach((t, i) => {
      const [a, b] = [px(t.x1, t.y1), px(t.x2, t.y2)]
      s += `<line class="peca${marcado("trechos", i) ? " sel" : ""}" x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}"/>`
    })
    s += cotas()
    e.dados.apoios.forEach((a, i) => {
      s += temPonta(a) ? barraDePonta(a) : simbolo(a)
      const p = px(a.x, a.y)
      s += `<text class="nome${marcado("apoios", i) ? " sel-t" : ""}" x="${p[0] + 13}" y="${p[1] - 11}">${a.nome}</text>`
    })
    e.dados.cargas.forEach((c, i) => {
      s += desenhoDaCarga(c, marcado("cargas", i))
    })
    e.dados.cortes.forEach((c, i) => {
      const p = px(c.x, c.y)
      const [tx, ty] = direcao(c.angulo)
      const [nx, ny] = [-ty, tx]
      const a = [p[0] + nx * 28, p[1] - ny * 28]
      const b = [p[0] - nx * 28, p[1] + ny * 28]
      const valores = !e.gesto && e.marcas?.cortes?.[i]
      s += `<line class="corte${marcado("cortes", i) ? " sel" : ""}" x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}"/>
        <text class="corte-t" x="${a[0]}" y="${a[1] - 7}" text-anchor="middle">${c.nome}${valores ? `: ${valores}` : ""}</text>`
    })
    if (e.marcas && !e.gesto) {
      for (const r of e.marcas.reacoes ?? []) s += desenhoDaReacao(r)
      const mov = e.marcas.movimento
      if (mov) {
        s += `<text class="ruim-t forte" x="${w / 2}" y="24" text-anchor="middle">A peça não fica parada: ${mov.texto}</text>`
        if (mov.giro) {
          const c = px(mov.x, mov.y)
          s += `<circle class="ruim" cx="${c[0]}" cy="${c[1]}" r="9"/><circle class="ruim" cx="${c[0]}" cy="${c[1]}" r="2"/>`
        }
      }
    }
    if (e.gesto?.rascunho) s += e.gesto.rascunho
    if (e.cadeia?.length) {
      const pts = [...e.cadeia, e.ponteiro].filter(Boolean)
      s += `<polyline class="rascunho" points="${pts.map(([x, y]) => px(x, y).join(",")).join(" ")}"/>`
      e.cadeia.forEach(([x, y]) => {
        const [a, b] = px(x, y)
        s += `<circle class="alca" cx="${a}" cy="${b}" r="4"/>`
      })
    }
    if (e.pendente) {
      const p = px(...e.pendente)
      const f = e.ponteiro ? px(...e.ponteiro) : p
      s += `<line class="rascunho" x1="${p[0]}" y1="${p[1]}" x2="${f[0]}" y2="${f[1]}"/>`
    }
    if (e.ima) {
      const [a, b] = px(...e.ima)
      s += `<circle class="ima" cx="${a}" cy="${b}" r="7"/>`
    }
    for (const a of alcas()) s += `<circle class="alca" cx="${a.px[0]}" cy="${a.px[1]}" r="${ALCA_PX}"/>`
    if (!pontosDoDesenho().length && !e.cadeia && !e.gesto) {
      s += `<text class="vazia-t" x="${w / 2}" y="${h / 2}" text-anchor="middle">Clique em Desenhar peça, ou escolha um modelo pronto</text>`
    }
    svg.innerHTML = s
    svg.classList.toggle("desenho", e.ferramenta !== "mover")
  }

  // ---- alças do item selecionado
  function alcas() {
    const it = item()
    if (!it || e.ferramenta !== "mover") return []
    if (e.sel.lista === "trechos") {
      return [
        { tipo: "v1", px: px(it.x1, it.y1) },
        { tipo: "v2", px: px(it.x2, it.y2) },
      ]
    }
    if (e.sel.lista === "apoios") {
      if (temPonta(it)) return it.x2 === null ? [] : [{ tipo: "ponta", px: px(it.x2, it.y2) }]
      if (it.tipo === PINO) return []
      const [cx, cy] = direcao(it.angulo)
      const p = px(it.x, it.y)
      return [{ tipo: "giro", px: [p[0] + cx * 46, p[1] - cy * 46], sinal: 1 }]
    }
    if (e.sel.lista === "cargas") {
      if (it.tipo === FORCA) {
        const [cx, cy] = direcao(it.angulo)
        const p = px(it.x, it.y)
        const k = it.valor < 0 ? -1 : 1
        return [{ tipo: "giro", px: [p[0] - k * cx * SETA_PX, p[1] + k * cy * SETA_PX], sinal: -k }]
      }
      if (it.tipo === DISTRIBUIDA) {
        return [
          { tipo: "ini", px: px(it.x, it.y) },
          { tipo: "fim", px: px(it.x2, it.y2) },
        ]
      }
    }
    return []
  }
  function alcaEm(ev) {
    const [mx, my] = noPonteiro(ev)
    return alcas().find((a) => Math.hypot(a.px[0] - mx, a.px[1] - my) <= ALCA_PX + 5)
  }
  function itemEm(ev) {
    const [mx, my] = noPonteiro(ev)
    const pertoPx = (p) => Math.hypot(p[0] - mx, p[1] - my)
    const noSegmento = (a, b) => {
      const k = pertoDoTrecho(mx, my, { x1: a[0], y1: a[1], x2: b[0], y2: b[1] })
      return k.d
    }
    // A carga distribuída é uma faixa larga: fica por último, para não cobrir o que está nela.
    for (let i = e.dados.cargas.length - 1; i >= 0; i -= 1) {
      const c = e.dados.cargas[i]
      const p = px(c.x, c.y)
      if (c.tipo === DISTRIBUIDA) continue
      if (c.tipo === MOMENTO) {
        if (pertoPx(p) < 28) return { lista: "cargas", i }
      } else {
        const [ux, uy] = c.tipo === PESO ? [0, -1] : direcao(c.angulo)
        const k = c.tipo === FORCA && c.valor < 0 ? -1 : 1
        if (noSegmento([p[0] - k * ux * SETA_PX, p[1] + k * uy * SETA_PX], p) < TOQUE_PX) {
          return { lista: "cargas", i }
        }
      }
    }
    for (let i = e.dados.apoios.length - 1; i >= 0; i -= 1) {
      const a = e.dados.apoios[i]
      const p = px(a.x, a.y)
      if (pertoPx(p) < 18) return { lista: "apoios", i }
      if (temPonta(a) && a.x2 !== null && noSegmento(p, px(a.x2, a.y2)) < TOQUE_PX) {
        return { lista: "apoios", i }
      }
    }
    for (let i = e.dados.cortes.length - 1; i >= 0; i -= 1) {
      const c = e.dados.cortes[i]
      if (pertoPx(px(c.x, c.y)) < 22) return { lista: "cortes", i }
    }
    for (let i = e.dados.trechos.length - 1; i >= 0; i -= 1) {
      const t = e.dados.trechos[i]
      if (noSegmento(px(t.x1, t.y1), px(t.x2, t.y2)) < TOQUE_PX) return { lista: "trechos", i }
    }
    for (let i = e.dados.cargas.length - 1; i >= 0; i -= 1) {
      const c = e.dados.cargas[i]
      if (c.tipo !== DISTRIBUIDA) continue
      const [ux, uy] = direcao(c.angulo)
      const [p, q] = [px(c.x, c.y), px(c.x2, c.y2)]
      const sobe = [-ux * 30, uy * 30]
      if (noSegmento([p[0] + sobe[0], p[1] + sobe[1]], [q[0] + sobe[0], q[1] + sobe[1]]) < 26) {
        return { lista: "cargas", i }
      }
    }
    return null
  }

  // Ponta de trecho arrastada: o que estava preso nela vai junto, senão a peça rasga.
  function arrastarPonta(x0, y0, x1, y1) {
    const igual = (a, b) => Math.abs(a - x0) < 1e-9 && Math.abs(b - y0) < 1e-9
    for (const t of e.dados.trechos) {
      if (igual(t.x1, t.y1)) [t.x1, t.y1] = [x1, y1]
      if (igual(t.x2, t.y2)) [t.x2, t.y2] = [x1, y1]
    }
    for (const nome of ["apoios", "cargas", "cortes"]) {
      for (const v of e.dados[nome]) {
        if (igual(v.x, v.y)) [v.x, v.y] = [x1, y1]
        if (v.tipo === DISTRIBUIDA && igual(v.x2, v.y2)) [v.x2, v.y2] = [x1, y1]
      }
    }
  }
  function moverItem(it, base, dx, dy) {
    it.x = arred(base.x + dx)
    it.y = arred(base.y + dy)
    if (it.tipo === DISTRIBUIDA) {
      it.x2 = arred(base.x2 + dx)
      it.y2 = arred(base.y2 + dy)
    }
  }

  // ---- ponteiro
  function terminarPendente(fim) {
    const [x, y] = e.pendente
    const tipo = e.ferramenta
    e.pendente = null
    e.ponteiro = null
    if (Math.hypot(fim[0] - x, fim[1] - y) > 0) criarApoio(tipo, x, y, fim)
    else desenhar()
  }
  function finalizarNovo(g, moveu) {
    const tipo = e.ferramenta
    const ini = g.ini
    const fim = g.fim ?? ini
    if (tipo === CABO || tipo === BIELA) {
      if (moveu) criarApoio(tipo, ini.p[0], ini.p[1], fim.p)
      else {
        e.pendente = ini.p
        desenhar()
      }
    } else if (APOIOS.includes(tipo)) {
      criarApoio(tipo, ini.p[0], ini.p[1])
    } else if (tipo === FORCA) {
      if (!moveu) {
        criarCarga(FORCA, ini.p[0], ini.p[1])
        return
      }
      const angulo = arred(grau(Math.atan2(fim.p[1] - ini.p[1], fim.p[0] - ini.p[0])))
      const ponto = ini.peca && !fim.peca ? ini.p : fim.p
      criarCarga(FORCA, ponto[0], ponto[1], { angulo: Math.round(angulo * 10) / 10 })
    } else if (tipo === MOMENTO || tipo === PESO) {
      criarCarga(tipo, ini.p[0], ini.p[1])
    } else if (tipo === DISTRIBUIDA) {
      if (moveu && (fim.p[0] !== ini.p[0] || fim.p[1] !== ini.p[1])) {
        criarCarga(tipo, ini.p[0], ini.p[1], { x2: fim.p[0], y2: fim.p[1] })
        return
      }
      const t = trechoEm(...ini.bruto)
      if (t) criarCarga(tipo, t.x1, t.y1, { x2: t.x2, y2: t.y2 })
      else desenhar()
    } else if (tipo === "corte") {
      const t = ini.trecho ?? trechoEm(...ini.bruto)
      guardar()
      e.dados.cortes.push({
        nome: nomeLivre(e.dados.cortes, (k) => `S${k + 1}`),
        x: ini.p[0],
        y: ini.p[1],
        angulo: arred(anguloDoTrecho(t)),
      })
      selecionar("cortes", e.dados.cortes.length - 1)
    }
  }
  function rascunhoDoNovo(g) {
    const tipo = e.ferramenta
    const [a, b] = [px(...g.ini.p), px(...g.fim.p)]
    if (tipo === FORCA) return seta(a, b, "carga", 10)
    if (tipo === DISTRIBUIDA || tipo === CABO || tipo === BIELA) {
      return `<line class="rascunho" x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}"/>`
    }
    return ""
  }

  svg.addEventListener("pointerdown", (ev) => {
    svg.focus({ preventScroll: true })
    svg.setPointerCapture(ev.pointerId)
    const [x, y] = mundo(ev)
    if (ev.button === 1) {
      e.gesto = { tipo: "pan", inicio: [ev.clientX, ev.clientY], vista: { ...e.vista } }
      return
    }
    if (e.pendente) {
      terminarPendente(iman(x, y).p)
      return
    }
    if (e.ferramenta === "trecho") {
      const { p } = iman(x, y)
      const ultimo = e.cadeia?.at(-1)
      if (ultimo && ultimo[0] === p[0] && ultimo[1] === p[1]) {
        terminarCadeia()
        return
      }
      e.cadeia = [...(e.cadeia || []), p]
      desenhar()
      return
    }
    if (e.ferramenta !== "mover") {
      e.gesto = {
        tipo: "novo",
        ini: { ...iman(x, y), bruto: [x, y] },
        fim: null,
        tela: [ev.clientX, ev.clientY],
      }
      return
    }
    const alca = alcaEm(ev)
    if (alca) {
      e.gesto = { tipo: "alca", alca, guardado: false, base: copiar(item()) }
      return
    }
    const alvo = itemEm(ev)
    if (!alvo) {
      e.sel = null
      e.gesto = { tipo: "pan", inicio: [ev.clientX, ev.clientY], vista: { ...e.vista } }
      montarPainel()
      desenhar()
      return
    }
    e.sel = alvo
    const it = item()
    if (alvo.lista === "trechos") {
      // Arrastar o trecho soltaria a peça dos apoios e das cargas. A forma muda pelas alças.
      e.gesto = { tipo: "pan", inicio: [ev.clientX, ev.clientY], vista: { ...e.vista } }
    } else {
      e.gesto = { tipo: "mover", inicio: [x, y], ref: [it.x, it.y], base: copiar(it), guardado: false }
    }
    montarPainel()
    desenhar()
  })

  svg.addEventListener("pointermove", (ev) => {
    const [x, y] = mundo(ev)
    infoXY.textContent = `x ${texto(x)} · y ${texto(y)} ${e.u.c}`
    const g = e.gesto
    if (e.cadeia || e.pendente) {
      e.ponteiro = iman(x, y).p
      desenhar()
      return
    }
    if (!g) {
      if (e.ferramenta !== "mover") {
        iman(x, y)
        desenhar()
      }
      return
    }
    if (g.tipo === "pan") {
      e.vista.cx = g.vista.cx - (ev.clientX - g.inicio[0]) / e.vista.esc
      e.vista.cy = g.vista.cy + (ev.clientY - g.inicio[1]) / e.vista.esc
      desenhar()
      return
    }
    if (g.tipo === "novo") {
      g.fim = iman(x, y)
      g.moveu = g.moveu || Math.hypot(ev.clientX - g.tela[0], ev.clientY - g.tela[1]) > 6
      g.rascunho = g.moveu ? rascunhoDoNovo(g) : ""
      desenhar()
      return
    }
    if (g.tipo === "mover") {
      const alvo = iman(g.ref[0] + x - g.inicio[0], g.ref[1] + y - g.inicio[1], e.sel)
      const [dx, dy] = [alvo.p[0] - g.ref[0], alvo.p[1] - g.ref[1]]
      if (!dx && !dy && !g.moveu) return
      if (!g.guardado) {
        guardar()
        g.guardado = true
      }
      g.moveu = true
      const it = item()
      moverItem(it, g.base, dx, dy)
      if (e.sel.lista === "cortes" && alvo.trecho) it.angulo = arred(anguloDoTrecho(alvo.trecho))
      desenhar()
      return
    }
    if (g.tipo === "alca") {
      if (!g.guardado) {
        guardar()
        g.guardado = true
      }
      const it = item()
      const { tipo, sinal } = g.alca
      if (tipo === "giro") {
        const a = grau(Math.atan2(sinal * (y - it.y), sinal * (x - it.x)))
        it.angulo = Math.round(a / 5) * 5
      } else if (tipo === "ponta") {
        ;[it.x2, it.y2] = iman(x, y, e.sel).p
      } else if (tipo === "ini") {
        ;[it.x, it.y] = iman(x, y, e.sel).p
      } else if (tipo === "fim") {
        ;[it.x2, it.y2] = iman(x, y, e.sel).p
      } else {
        const [ax, ay] = tipo === "v1" ? [it.x1, it.y1] : [it.x2, it.y2]
        const p = iman(x, y, e.sel).p
        arrastarPonta(ax, ay, p[0], p[1])
      }
      g.moveu = true
      desenhar()
    }
  })

  svg.addEventListener("pointerup", () => {
    const g = e.gesto
    e.gesto = null
    if (e.ferramenta === "mover") e.ima = null
    if (!g) {
      desenhar()
      return
    }
    if (g.tipo === "novo") {
      finalizarNovo(g, Boolean(g.moveu))
      return
    }
    if ((g.tipo === "mover" || g.tipo === "alca") && g.moveu) {
      enviar()
      return
    }
    desenhar()
  })

  svg.addEventListener("dblclick", () => {
    if (e.cadeia) terminarCadeia()
  })

  svg.addEventListener(
    "wheel",
    (ev) => {
      // Só com Ctrl: a resposta fica abaixo da prancheta, e a rodinha precisa descer a página.
      if (!ev.ctrlKey && !ev.metaKey) return
      ev.preventDefault()
      const [x, y] = mundo(ev)
      aproximar(ev.deltaY < 0 ? 1.15 : 1 / 1.15, x, y)
    },
    { passive: false },
  )

  svg.addEventListener("keydown", (ev) => {
    const ctrl = ev.ctrlKey || ev.metaKey
    const tecla = ev.key.toLowerCase()
    const direita = { arrowleft: [-1, 0], arrowright: [1, 0], arrowup: [0, 1], arrowdown: [0, -1] }[tecla]
    if (ctrl && tecla === "z") acoes.desfazer()
    else if (ctrl && tecla === "y") acoes.refazer()
    else if (tecla === "delete" || tecla === "backspace") acoes.apagar()
    else if (tecla === "escape") {
      e.cadeia = null
      e.pendente = null
      e.sel = null
      trocarFerramenta("mover")
      montarPainel()
    } else if (tecla === "enter" && e.cadeia) terminarCadeia()
    else if (direita && item() && e.sel.lista !== "trechos") {
      guardar()
      const it = item()
      moverItem(it, copiar(it), direita[0] * e.grade, direita[1] * e.grade)
      enviar()
    } else if (!ctrl && tecla === "v") trocarFerramenta("mover")
    else return
    ev.preventDefault()
  })

  function trocarFerramenta(nome) {
    if (e.cadeia?.length > 1 && nome !== "trecho") terminarCadeia()
    e.ferramenta = nome
    e.cadeia = null
    e.pendente = null
    e.ima = null
    infoDica.textContent = DICA[nome] ?? ""
    raiz.querySelectorAll("[data-f]").forEach((b) => {
      b.classList.toggle("ativo", b.dataset.f === nome)
    })
    desenhar()
  }
  raiz.querySelectorAll("[data-f]").forEach((b) => {
    b.addEventListener("click", () => trocarFerramenta(b.dataset.f))
  })
  raiz.querySelectorAll("[data-a]").forEach((b) => {
    b.addEventListener("click", () => acoes[b.dataset.a]())
  })
  seletorGrade.addEventListener("change", () => {
    e.grade = Number(seletorGrade.value)
  })

  function montarGrades(extensao) {
    const opcoes = GRADES[e.u.c] ?? GRADES.m
    const ideal = extensao > 0 ? extensao / 40 : opcoes[2]
    e.grade = opcoes.reduce((a, b) => (Math.abs(b - ideal) < Math.abs(a - ideal) ? b : a))
    seletorGrade.replaceChildren(
      ...opcoes.map((v) => {
        const o = document.createElement("option")
        o.value = String(v)
        o.textContent = `${texto(v)} ${e.u.c}`
        o.selected = v === e.grade
        return o
      }),
    )
  }

  e.receber = (dados) => {
    const novos = dados.dados ?? e.dados
    const u = dados.unidades ?? e.u
    const trocouUnidade = u.c !== e.u.c
    if (trocouUnidade) infoXY.textContent = ""
    let mudou = trocouUnidade || !painel.childElementCount
    e.u = u
    if (dados.versao >= e.versao) {
      if (JSON.stringify(novos) !== JSON.stringify(e.dados)) {
        if (e.versao >= 0) guardar()
        e.dados = copiar(novos)
        if (e.sel && e.sel.i >= e.dados[e.sel.lista].length) e.sel = null
        mudou = true
      }
      e.versao = dados.versao
    }
    e.marcas = dados.marcas ?? null
    if (e.verAjuste !== dados.ajustar || trocouUnidade) {
      e.verAjuste = dados.ajustar
      ajustarVista()
      const lista = pontosDoDesenho()
      const xs = lista.map((p) => p[0])
      const ys = lista.map((p) => p[1])
      const extensao = lista.length
        ? Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys))
        : 0
      montarGrades(extensao)
    }
    // Refazer o painel a cada rodada tiraria o foco de quem acabou de criar uma carga e vai digitar.
    if (mudou) montarPainel()
    desenhar()
  }

  trocarFerramenta("mover")
  new ResizeObserver(() => desenhar()).observe(svg)
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
