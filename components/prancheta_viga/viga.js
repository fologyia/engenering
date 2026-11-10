// Prancheta da viga (Vigas e eixos): a barra reta de 0 a L, os apoios, as rótulas e as cargas ao
// longo de x, no mesmo jeito da prancheta do equilíbrio (clique para pôr, arraste, painel do item,
// medidas que se digitam no desenho, Ctrl+Z). O Python é o dono das contas: o desenho vai para lá a
// cada gesto terminado e as reações voltam em `marcas`. Unidades do modelo em texto: m, kN, kN·m,
// kN/m; positivo para cima (força), anti-horário (momento) e no sentido de +x (axial e torque).

const ESTADOS = new WeakMap()
const IMA_PX = 10
const ALCA_PX = 6
const TOQUE_PX = 11
const SETA_PX = 84

const PINO = "Pino"
const ROLETE = "Rolete"
const ENGASTE = "Engaste"
const DESLIZANTE = "Deslizante"
const TRAVA = "Trava axial"
const MOLA = "Mola"
const ROTULA = "Rótula"
const FORCA = "Força"
const MOMENTO = "Momento"
const DISTRIBUIDA = "Distribuída"
const AXIAL = "Axial"
const AXIAL_DIST = "Axial distribuída"
const TORQUE = "Torque"
const APOIOS = [PINO, ROLETE, ENGASTE, DESLIZANTE, TRAVA, MOLA]
const CARGAS = [FORCA, MOMENTO, DISTRIBUIDA, AXIAL, AXIAL_DIST, TORQUE]
const COM_TRECHO = [DISTRIBUIDA, AXIAL_DIST]
const UNIDADE = { [FORCA]: "kN", [MOMENTO]: "kN·m", [DISTRIBUIDA]: "kN/m", [AXIAL]: "kN", [AXIAL_DIST]: "kN/m", [TORQUE]: "kN·m" }
const PREFIXO = { [FORCA]: "P", [MOMENTO]: "M", [DISTRIBUIDA]: "q", [AXIAL]: "N", [AXIAL_DIST]: "n", [TORQUE]: "T" }
const PADRAO = { [FORCA]: -10, [MOMENTO]: 5, [DISTRIBUIDA]: -5, [AXIAL]: 10, [AXIAL_DIST]: 2, [TORQUE]: 1 }
const GRADES = [0.01, 0.05, 0.1, 0.25, 0.5, 1]
const DICA = {
  mover: "Clique num item para os valores. Arraste apoios, cargas e a ponta da barra. Clique numa medida para mudar.",
  [PINO]: "Clique na barra: o pino segura na vertical e na horizontal.",
  [ROLETE]: "Clique na barra: o rolete segura só na vertical.",
  [ENGASTE]: "Clique na barra (de costume, numa ponta): o engaste segura tudo.",
  [DESLIZANTE]: "Clique na barra: trava o giro e a horizontal e deixa correr na vertical.",
  [TRAVA]: "Clique na barra: segura só na direção da barra.",
  [MOLA]: "Clique na barra e dê a rigidez kv (N/mm) e, se houver, kr (N·mm/rad).",
  [ROTULA]: "Clique na barra onde fica a articulação.",
  [FORCA]: "Clique na barra para uma força para baixo, ou arraste para cima ou para baixo.",
  [MOMENTO]: "Clique no ponto do momento.",
  [DISTRIBUIDA]: "Clique na barra para carregar ela inteira, ou arraste do início ao fim.",
  [AXIAL]: "Clique no ponto: a força puxa para +x (troque o sentido no painel).",
  [AXIAL_DIST]: "Clique na barra para ela inteira, ou arraste do início ao fim.",
  [TORQUE]: "Clique no ponto do torque.",
}

const copiar = (v) => JSON.parse(JSON.stringify(v))
const arred = (v) => Math.round(v * 10000) / 10000
const texto = (v) => String(arred(v)).replace(".", ",")

// ---- funções puras (testadas no Node)
function nomeLivre(lista, gerar) {
  const usados = new Set(lista.map((v) => v.nome))
  for (let k = 0; ; k += 1) {
    const nome = gerar(k)
    if (!usados.has(nome)) return nome
  }
}
const letra = (k) => String.fromCharCode(65 + (k % 26)) + (k < 26 ? "" : String(Math.floor(k / 26)))

function pontosDaBarra(d) {
  const lista = [0, d.L]
  for (const a of d.apoios) lista.push(a.x)
  for (const r of d.rotulas) lista.push(r.x)
  for (const c of d.cargas) {
    lista.push(c.x)
    if (COM_TRECHO.includes(c.tipo) && c.x2 !== null && c.x2 !== undefined) lista.push(c.x2)
  }
  return [...new Set(lista.map(arred))].sort((a, b) => a - b)
}

// Mudar uma distância empurra tudo o que está depois dela, a ponta da barra inclusive.
function esticar(d, limite, delta) {
  const mexe = (o, k) => {
    if (o[k] !== null && o[k] !== undefined && o[k] >= limite - 1e-9) o[k] = arred(o[k] + delta)
  }
  if (d.L >= limite - 1e-9) d.L = arred(d.L + delta)
  for (const a of d.apoios) mexe(a, "x")
  for (const r of d.rotulas) mexe(r, "x")
  for (const c of d.cargas) {
    mexe(c, "x")
    if ("x2" in c) mexe(c, "x2")
  }
  return d
}

// A ponta da barra: o que estava nela vai junto; o que sobra fora da barra volta para dentro.
function novoComprimento(d, L) {
  const antes = d.L
  const segue = (v) => (Math.abs(v - antes) < 1e-9 ? L : Math.min(v, L))
  d.L = arred(L)
  for (const a of d.apoios) a.x = arred(segue(a.x))
  for (const r of d.rotulas) r.x = arred(segue(r.x))
  for (const c of d.cargas) {
    c.x = arred(segue(c.x))
    if (c.x2 !== null && c.x2 !== undefined) c.x2 = arred(segue(c.x2))
  }
  return d
}

function noIma(x, pontos, raio) {
  let melhor = null
  for (const p of pontos) {
    const dist = Math.abs(p - x)
    if (dist <= raio && (melhor === null || dist < Math.abs(melhor - x))) melhor = p
  }
  return melhor
}

function criar(raiz) {
  const svg = raiz.querySelector("svg")
  const painel = raiz.querySelector("[data-painel]")
  const infoXY = raiz.querySelector('[data-i="xy"]')
  const infoDica = raiz.querySelector('[data-i="dica"]')
  const seletorGrade = raiz.querySelector('[data-c="grade"]')
  const editor = criarEditorVivo(raiz.querySelector(".area"))

  const e = {
    enviar: null,
    dados: { L: 6, apoios: [], rotulas: [], cargas: [] },
    versao: -1,
    verAjuste: null,
    marcas: null,
    ferramenta: "mover",
    sel: null,
    grade: 0.1,
    vista: { cx: 3, esc: 100 },
    gesto: null,
    ima: null,
    passado: [],
    futuro: [],
    ultimo: {},
    focar: false,
    cotasVivas: [],
  }

  const tela = () => {
    const r = svg.getBoundingClientRect()
    return { w: r.width || 800, h: r.height || 430 }
  }
  const yBarra = () => Math.round(tela().h * 0.4)
  const px = (x) => tela().w / 2 + (x - e.vista.cx) * e.vista.esc
  const mundo = (ev) => {
    const r = svg.getBoundingClientRect()
    return e.vista.cx + (ev.clientX - r.left - tela().w / 2) / e.vista.esc
  }
  const noPonteiro = (ev) => {
    const r = svg.getBoundingClientRect()
    return [ev.clientX - r.left, ev.clientY - r.top]
  }
  const naBarra = (x) => Math.min(Math.max(x, 0), e.dados.L)
  const item = () => (e.sel && e.sel.lista !== "viga" ? e.dados[e.sel.lista][e.sel.i] : null)

  function iman(x, fora = null) {
    const pontos = []
    const d = e.dados
    pontos.push(0, d.L)
    for (const [nome, lista] of [["apoios", d.apoios], ["rotulas", d.rotulas], ["cargas", d.cargas]]) {
      lista.forEach((v, i) => {
        if (fora && fora.lista === nome && fora.i === i) return
        pontos.push(v.x)
        if (v.x2 !== null && v.x2 !== undefined) pontos.push(v.x2)
      })
    }
    const perto = noIma(x, pontos, IMA_PX / e.vista.esc)
    if (perto !== null) {
      e.ima = perto
      return perto
    }
    e.ima = null
    return arred(naBarra(Math.round(x / e.grade) * e.grade))
  }

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
      aproximar(1.3, e.vista.cx)
    },
    maisLonge() {
      aproximar(1 / 1.3, e.vista.cx)
    },
    apagar() {
      if (!e.sel || e.sel.lista === "viga") return
      guardar()
      e.dados[e.sel.lista].splice(e.sel.i, 1)
      e.sel = null
      enviar()
    },
  }

  // ---- itens novos
  function valorNovo(tipo) {
    return e.ultimo[tipo] ?? PADRAO[tipo]
  }
  function criarApoio(tipo, x) {
    guardar()
    e.dados.apoios.push({
      nome: nomeLivre(e.dados.apoios, letra),
      tipo,
      x,
      kv: tipo === MOLA ? 1000 : null,
      kr: null,
    })
    selecionar("apoios", e.dados.apoios.length - 1)
  }
  function criarRotula(x) {
    guardar()
    e.dados.rotulas.push({ nome: nomeLivre(e.dados.rotulas, (k) => `R${k + 1}`), x })
    selecionar("rotulas", e.dados.rotulas.length - 1)
  }
  function criarCarga(tipo, x, extra = {}) {
    guardar()
    const valor = valorNovo(tipo)
    e.dados.cargas.push({
      nome: nomeLivre(e.dados.cargas, (k) => `${PREFIXO[tipo]}${k + 1}`),
      tipo,
      x,
      x2: COM_TRECHO.includes(tipo) ? e.dados.L : null,
      valor,
      valor2: COM_TRECHO.includes(tipo) ? valor : null,
      caso: "",
      e: tipo === AXIAL ? 0 : null,
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

  // ---- painel do item selecionado
  function campo(rotulo, valor, aplicar, dica, foco = false, largo = false) {
    const r = document.createElement("label")
    r.className = "campo"
    r.title = dica
    r.append(rotulo)
    const entrada = document.createElement("input")
    entrada.type = "text"
    entrada.inputMode = "decimal"
    entrada.value = valor === null || valor === undefined ? "" : texto(valor)
    if (largo) entrada.style.width = "84px"
    if (foco) entrada.dataset.foco = "1"
    entrada.addEventListener("change", () => {
      if (!entrada.value.trim()) {
        guardar()
        aplicar(null)
        enviar()
        return
      }
      const unidade = /\(([^)]+)\)\s*$/.exec(dica)?.[1] ?? ""
      const lido = lerValorDigitado(entrada.value, valor ?? 0, unidade)
      if (lido.erro) {
        entrada.value = valor === null || valor === undefined ? "" : texto(valor)
        return
      }
      guardar()
      aplicar(lido.valor)
      enviar()
    })
    entrada.addEventListener("keydown", (ev) => {
      ev.stopPropagation()
      if (ev.key === "Enter") entrada.blur()
    })
    r.append(entrada)
    return r
  }
  function campoDeTexto(rotulo, valor, aplicar, dica, largura = "44px") {
    const r = document.createElement("label")
    r.className = "campo"
    r.title = dica
    r.append(rotulo)
    const entrada = document.createElement("input")
    entrada.type = "text"
    entrada.value = valor ?? ""
    entrada.style.width = largura
    entrada.style.textAlign = "left"
    entrada.addEventListener("change", () => {
      guardar()
      aplicar(entrada.value.trim())
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
    return campoDeTexto("Nome", it.nome, (v) => { if (v) it.nome = v }, "Nome no desenho e nas tabelas")
  }
  function sentido(rotulo, opcoes, atual, aplicar, dica) {
    const r = document.createElement("div")
    r.className = "bloco"
    r.title = dica
    for (const [txt, sinal] of opcoes) {
      const b = document.createElement("button")
      b.type = "button"
      b.textContent = txt
      b.classList.toggle("ativo", sinal === atual)
      b.setAttribute("aria-label", `${rotulo} ${txt}`)
      b.addEventListener("click", () => {
        guardar()
        aplicar(sinal)
        enviar()
      })
      r.append(b)
    }
    return r
  }
  const sinalDe = (v) => ((v ?? 0) < 0 ? -1 : 1)
  function trocarSinal(c, sinal) {
    c.valor = sinal * Math.abs(c.valor)
    if (c.valor2 !== null && c.valor2 !== undefined) c.valor2 = sinal * Math.abs(c.valor2)
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
  const posicao = (it, chave = "x", rotulo = "x") =>
    campo(rotulo, it[chave], (v) => { if (v !== null) it[chave] = arred(naBarra(v)) }, "Posição ao longo da barra (m)")
  const caso = (c) =>
    campoDeTexto("Caso", c.caso, (v) => { c.caso = v }, "Ação a que a carga pertence (para as combinações). Vazio: Permanente.", "92px")
  function painelDoApoio(a) {
    painel.append(
      escolhaDeTipo(a, APOIOS, () => {
        if (a.tipo === MOLA) a.kv = a.kv ?? 1000
        else a.kv = a.kr = null
      }),
      nomeDoItem(a),
      posicao(a),
    )
    if (a.tipo === MOLA) {
      painel.append(
        campo("kv", a.kv, (v) => { a.kv = v === null || v < 0 ? null : v }, "Rigidez vertical da mola (N/mm)", true, true),
        campo("kr", a.kr, (v) => { a.kr = v === null || v < 0 ? null : v }, "Rigidez ao giro da mola (N·mm/rad)", false, true),
      )
    }
  }
  function painelDaCarga(c) {
    const un = UNIDADE[c.tipo]
    painel.append(nomeDoItem(c))
    if (c.tipo === FORCA || c.tipo === DISTRIBUIDA) {
      if (c.tipo === FORCA) {
        painel.append(campo(`F (${un})`, Math.abs(c.valor), (v) => {
          if (v === null) return
          c.valor = sinalDe(c.valor) * Math.abs(v)
          e.ultimo[c.tipo] = c.valor
        }, `Valor da força (${un})`, true))
      } else {
        painel.append(
          campo(`Início (${un})`, Math.abs(c.valor), (v) => {
            if (v === null) return
            const s = sinalDe(c.valor)
            if (c.valor2 === c.valor) c.valor2 = s * Math.abs(v)
            c.valor = s * Math.abs(v)
            e.ultimo[c.tipo] = c.valor
          }, `Carga por metro no início (${un})`, true),
          campo("Fim", Math.abs(c.valor2 ?? c.valor), (v) => {
            if (v === null) return
            c.valor2 = sinalDe(c.valor) * Math.abs(v)
          }, `Carga por metro no fim (${un})`),
        )
      }
      painel.append(sentido("Para", [["↓", -1], ["↑", 1]], sinalDe(c.valor), (s) => trocarSinal(c, s), "Sentido da carga"))
    } else if (c.tipo === MOMENTO || c.tipo === TORQUE) {
      painel.append(
        campo(`${c.tipo === MOMENTO ? "M" : "T"} (${un})`, Math.abs(c.valor), (v) => {
          if (v === null) return
          c.valor = sinalDe(c.valor) * Math.abs(v)
          e.ultimo[c.tipo] = c.valor
        }, `Valor (${un})`, true),
        c.tipo === MOMENTO
          ? sentido("Sentido", [["↺", 1], ["↻", -1]], sinalDe(c.valor), (s) => trocarSinal(c, s), "↺ anti-horário (positivo), ↻ horário")
          : sentido("Sentido", [["+x", 1], ["−x", -1]], sinalDe(c.valor), (s) => trocarSinal(c, s), "Pela regra da mão direita: +x é o polegar para a direita"),
      )
    } else {
      // axial e axial distribuída
      if (c.tipo === AXIAL) {
        painel.append(campo(`N (${un})`, Math.abs(c.valor), (v) => {
          if (v === null) return
          c.valor = sinalDe(c.valor) * Math.abs(v)
          e.ultimo[c.tipo] = c.valor
        }, `Valor da força na direção da barra (${un})`, true))
      } else {
        painel.append(
          campo(`Início (${un})`, Math.abs(c.valor), (v) => {
            if (v === null) return
            const s = sinalDe(c.valor)
            if (c.valor2 === c.valor) c.valor2 = s * Math.abs(v)
            c.valor = s * Math.abs(v)
            e.ultimo[c.tipo] = c.valor
          }, `Força por metro no início (${un})`, true),
          campo("Fim", Math.abs(c.valor2 ?? c.valor), (v) => {
            if (v === null) return
            c.valor2 = sinalDe(c.valor) * Math.abs(v)
          }, `Força por metro no fim (${un})`),
        )
      }
      painel.append(sentido("Para", [["→", 1], ["←", -1]], sinalDe(c.valor), (s) => trocarSinal(c, s), "Sentido na direção da barra"))
      if (c.tipo === AXIAL) {
        painel.append(campo("e", c.e, (v) => { c.e = v ?? 0 }, "Excentricidade acima do centroide: vira o momento −e·N (mm)"))
      }
    }
    if (COM_TRECHO.includes(c.tipo)) {
      painel.append(posicao(c, "x", "x₁"), posicao(c, "x2", "x₂"))
    } else {
      painel.append(posicao(c))
    }
    painel.append(caso(c))
  }
  function painelDaViga() {
    painel.append(
      campo("Comprimento L", e.dados.L, (v) => {
        if (v === null || v <= 0) return
        novoComprimento(e.dados, v)
        ajustarVista()
      }, "Comprimento total da barra (m)", true),
    )
  }
  function montarPainel() {
    painel.replaceChildren()
    if (e.sel?.lista === "viga") {
      const titulo = document.createElement("span")
      titulo.className = "titulo"
      titulo.textContent = "Barra"
      painel.append(titulo)
      painelDaViga()
      return
    }
    const it = item()
    if (!it) {
      const dica = document.createElement("span")
      dica.className = "apagado"
      dica.textContent = e.dados.apoios.length
        ? "Clique num apoio, carga, rótula ou na barra para digitar os valores. Tudo gruda na barra sozinho."
        : "Ponha os apoios: escolha Pino, Rolete ou Engaste acima e clique na barra."
      painel.append(dica)
      return
    }
    const titulo = document.createElement("span")
    titulo.className = "titulo"
    titulo.textContent = e.sel.lista === "rotulas" ? ROTULA : e.sel.lista === "cargas" ? it.tipo : ""
    if (titulo.textContent) painel.append(titulo)
    if (e.sel.lista === "apoios") painelDoApoio(it)
    else if (e.sel.lista === "cargas") painelDaCarga(it)
    else painel.append(nomeDoItem(it), posicao(it))
    painel.append(botaoApagar())
    if (e.focar) {
      e.focar = false
      const alvo = painel.querySelector('[data-foco="1"]')
      alvo?.focus()
      alvo?.select()
    }
  }

  // ---- valores e medidas editados no próprio desenho
  function descreverEdicao(tipo, k) {
    if (tipo === "cota") {
      const c = e.cotasVivas[k]
      const atual = c.b - c.a
      return {
        valor: atual,
        unidade: "m",
        reenquadrar: true,
        nome: "Distância",
        aplicar(v) {
          if (v <= 0) return "A distância precisa ser maior que zero."
          guardar()
          esticar(e.dados, c.b, v - atual)
          return ""
        },
      }
    }
    if (tipo === "L") {
      return {
        valor: e.dados.L,
        unidade: "m",
        reenquadrar: true,
        nome: "Comprimento da barra",
        aplicar(v) {
          if (v <= 0) return "O comprimento precisa ser maior que zero."
          guardar()
          novoComprimento(e.dados, v)
          return ""
        },
      }
    }
    const c = e.dados.cargas[k]
    return {
      valor: Math.abs(c.valor),
      unidade: UNIDADE[c.tipo],
      nome: `${c.nome}: ${c.tipo.toLowerCase()}`,
      aplicar(v) {
        guardar()
        const s = sinalDe(c.valor)
        if (c.valor2 === c.valor) c.valor2 = s * Math.abs(v)
        c.valor = s * Math.abs(v)
        e.ultimo[c.tipo] = c.valor
        return ""
      },
    }
  }
  function abrirEdicao(el) {
    const [tipo, indice] = el.dataset.editar.split(":")
    const d = descreverEdicao(tipo, Number(indice))
    editor.abrir(el, {
      ...d,
      passo: d.reenquadrar ? e.grade : null,
      aplicar(v) {
        const erro = d.aplicar(v)
        if (erro) return erro
        if (d.reenquadrar) ajustarVista()
        enviar()
        return ""
      },
    })
  }

  // ---- vista
  function aproximar(fator, x) {
    const esc = Math.min(Math.max(e.vista.esc * fator, 0.5), 50000)
    const k = e.vista.esc / esc
    e.vista = { cx: x + (e.vista.cx - x) * k, esc }
    desenhar()
  }
  function ajustarVista() {
    const { w } = tela()
    const L = Math.max(e.dados.L, 1e-6)
    e.vista = { cx: L / 2, esc: Math.max((w - 200) / L, 1) }
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
    const rad = (g) => (g * Math.PI) / 180
    const [x0, y0] = [p[0] + raio * Math.cos(rad(40)), p[1] + raio * Math.sin(rad(40))]
    const [x1, y1] = [p[0] + raio * Math.cos(rad(-50)), p[1] + raio * Math.sin(rad(-50))]
    const fim = positivo ? [x0, y0] : [x1, y1]
    const dir = positivo ? rad(40 + 90) : rad(-50 - 90)
    const antes = [fim[0] - Math.cos(dir) * 9, fim[1] - Math.sin(dir) * 9]
    return `<path class="${cls}" d="M ${x1} ${y1} A ${raio} ${raio} 0 1 1 ${x0} ${y0}"/>${seta(antes, fim, cls, 8)}`
  }
  function hachura(y0, x0 = -20, x1 = 20) {
    let s = `<line class="ap" x1="${x0}" y1="${y0}" x2="${x1}" y2="${y0}"/>`
    for (let k = x0 + 4; k <= x1; k += 8) s += `<line class="ap-f" x1="${k}" y1="${y0}" x2="${k - 6}" y2="${y0 + 7}"/>`
    return s
  }
  function simbolo(a) {
    const x = px(a.x)
    const y = yBarra()
    let s = ""
    if (a.tipo === PINO) {
      s = `<polygon class="ap-c" points="0,6 -13,28 13,28"/>${hachura(28)}<circle class="ap-c" cy="6" r="3.5"/>`
    } else if (a.tipo === ROLETE) {
      s = `<polygon class="ap-c" points="0,6 -13,24 13,24"/><circle class="ap-c" cx="-7" cy="29" r="4.5"/><circle class="ap-c" cx="7" cy="29" r="4.5"/>${hachura(34)}`
    } else if (a.tipo === ENGASTE) {
      // A parede do lado de fora da barra; no meio, dos dois lados.
      const lado = a.x <= 1e-9 ? -1 : a.x >= e.dados.L - 1e-9 ? 1 : 0
      const linhas = (k) => {
        let r = `<line class="ap-g" x1="0" y1="-26" x2="0" y2="26"/>`
        for (let v = -22; v <= 26; v += 8) r += `<line class="ap-f" x1="0" y1="${v}" x2="${k * 7}" y2="${v - 6}"/>`
        return r
      }
      s = lado === 0 ? linhas(-1) + linhas(1) : linhas(lado)
    } else if (a.tipo === DESLIZANTE) {
      s = `<rect class="ap-c" x="-7" y="-7" width="14" height="14"/><line class="ap" x1="-11" y1="-24" x2="-11" y2="24"/><line class="ap" x1="11" y1="-24" x2="11" y2="24"/>`
    } else if (a.tipo === TRAVA) {
      s = `<polygon class="ap-c" points="-6,0 -24,-11 -24,11"/><circle class="ap-c" cx="-29" cy="-6" r="4"/><circle class="ap-c" cx="-29" cy="6" r="4"/><line class="ap" x1="-34" y1="-16" x2="-34" y2="16"/>`
    } else if (a.tipo === MOLA) {
      let z = "M 0 6"
      for (let k = 0; k < 6; k += 1) z += ` L ${k % 2 ? -7 : 7} ${10 + k * 4}`
      z += " L 0 34"
      s = `<path class="mola" d="${z}"/>${hachura(34)}`
    }
    return `<g transform="translate(${x} ${y})">${s}</g>`
  }
  function desenhoDaDistribuida(c, marcado, i) {
    const y = yBarra()
    const axial = c.tipo === AXIAL_DIST
    const fim = c.valor2 ?? c.valor
    const maior = Math.max(Math.abs(c.valor), Math.abs(fim), 1e-12)
    const cls = axial ? (marcado ? "axial sel" : "axial") : marcado ? "carga sel" : "carga"
    let s = ""
    const n = Math.max(4, Math.min(16, Math.round((px(c.x2) - px(c.x)) / 34)))
    if (axial) {
      for (let k = 0; k < n; k += 1) {
        const q = (k + 0.5) / n
        const w = c.valor + (fim - c.valor) * q
        const xx = px(c.x + (c.x2 - c.x) * q)
        const l = 6 + (Math.abs(w) / maior) * 12
        const sinal = w >= 0 ? 1 : -1
        s += seta([xx - sinal * l, y - 16], [xx + sinal * l, y - 16], cls, 6)
      }
      const meio = px((c.x + c.x2) / 2)
      const rotulo = fim === c.valor ? `${c.nome} = ${texto(Math.abs(c.valor))} ${UNIDADE[c.tipo]}` : `${c.nome} = ${texto(Math.abs(c.valor))} a ${texto(Math.abs(fim))} ${UNIDADE[c.tipo]}`
      return s + `<text class="axial-t editavel" data-editar="carga:${i}" x="${meio}" y="${y - 30}" text-anchor="middle">${rotulo}</text>`
    }
    const topo = []
    for (let k = 0; k <= n; k += 1) {
      const q = k / n
      const w = c.valor + (fim - c.valor) * q
      const xx = px(c.x + (c.x2 - c.x) * q)
      const l = (Math.abs(w) / maior) * 44
      const ponta = w >= 0 ? [xx, y + 6] : [xx, y - 6]
      const cauda = w >= 0 ? [xx, y + 6 + l] : [xx, y - 6 - l]
      // para cima, as setas ficam embaixo da barra, empurrando
      topo.push(cauda)
      if (l > 8) s += w >= 0 ? seta(cauda, ponta, cls, 7) : seta(cauda, ponta, cls, 7)
    }
    s += `<polyline class="carga-l" points="${topo.map((v) => v.join(",")).join(" ")}"/>`
    const meio = topo[Math.floor(topo.length / 2)]
    const rotulo = fim === c.valor ? `${c.nome} = ${texto(Math.abs(c.valor))} ${UNIDADE[c.tipo]}` : `${c.nome} = ${texto(Math.abs(c.valor))} a ${texto(Math.abs(fim))} ${UNIDADE[c.tipo]}`
    const yt = c.valor >= 0 ? meio[1] + 16 : meio[1] - 8
    return s + `<text class="carga-t editavel" data-editar="carga:${i}" x="${meio[0]}" y="${yt}" text-anchor="middle">${rotulo}</text>`
  }
  function desenhoDaCarga(c, marcado, i) {
    if (COM_TRECHO.includes(c.tipo)) return desenhoDaDistribuida(c, marcado, i)
    const x = px(c.x)
    const y = yBarra()
    const un = UNIDADE[c.tipo]
    const rotulo = `${c.nome} = ${texto(Math.abs(c.valor))} ${un}`
    const casoTxt = c.caso ? `<text class="caso-t" x="${x}" y="${y - SETA_PX - 22}" text-anchor="middle">${c.caso}</text>` : ""
    if (c.tipo === FORCA) {
      const cls = marcado ? "carga sel" : "carga"
      const [a, b] = c.valor < 0 ? [[x, y - 6 - SETA_PX], [x, y - 6]] : [[x, y + 6 + SETA_PX], [x, y + 6]]
      const yt = c.valor < 0 ? y - SETA_PX - 10 : y + SETA_PX + 22
      return `${seta(a, b, cls)}<text class="carga-t editavel" data-editar="carga:${i}" x="${x}" y="${yt}" text-anchor="middle">${rotulo}</text>${casoTxt}`
    }
    if (c.tipo === MOMENTO) {
      const cls = marcado ? "carga sel" : "carga"
      return `${arco([x, y], c.valor, cls)}<text class="carga-t editavel" data-editar="carga:${i}" x="${x}" y="${y - 30}" text-anchor="middle">${rotulo}</text>${casoTxt}`
    }
    const cls = marcado ? "axial sel" : "axial"
    const s = sinalDe(c.valor)
    if (c.tipo === AXIAL) {
      const [a, b] = [[x - s * 54, y - 14], [x, y - 14]]
      return `${seta(a, b, cls)}<text class="axial-t editavel" data-editar="carga:${i}" x="${x - s * 27}" y="${y - 24}" text-anchor="middle">${rotulo}</text>${casoTxt}`
    }
    // torque: vetor de seta dupla na direção da barra
    const [a, b] = [[x, y - 22], [x + s * 48, y - 22]]
    const meio = [x + s * 38, y - 22]
    return `${seta(a, b, cls, 9)}${seta(a, meio, cls, 9)}<text class="axial-t editavel" data-editar="carga:${i}" x="${x + s * 24}" y="${y - 32}" text-anchor="middle">${rotulo}</text>${casoTxt}`
  }
  function desenhoDaReacao(r) {
    const x = px(r.x)
    const y = yBarra()
    const cls = r.ruim ? "ruim" : "reacao"
    let s = ""
    if (Math.abs(r.fy) > 0) {
      const [a, b] = r.fy > 0 ? [[x, y + 108], [x, y + 46]] : [[x, y + 46], [x, y + 108]]
      s += `${seta(a, b, cls, 11)}<text class="${cls}-t" x="${x}" y="${y + 124}" text-anchor="middle">${r.texto_fy}</text>`
    }
    if (Math.abs(r.fx) > 0) {
      const k = r.fx > 0 ? 1 : -1
      const [a, b] = [[x - k * 62, y + 62], [x - k * 8, y + 62]]
      s += `${seta(a, b, cls, 10)}<text class="${cls}-t" x="${x - k * 70}" y="${y + 66}" text-anchor="${k > 0 ? "end" : "start"}">${r.texto_fx}</text>`
    }
    if (Math.abs(r.mz) > 0) {
      s += `${arco([x, y], r.mz, cls, 34)}<text class="${cls}-t" x="${x + 40}" y="${y - 34}">${r.texto_mz}</text>`
    }
    if (r.texto_t) {
      s += `<text class="${cls}-t" x="${x}" y="${y + 140}" text-anchor="middle">${r.texto_t}</text>`
    }
    return s
  }
  function cotas() {
    e.cotasVivas = []
    const xs = pontosDaBarra(e.dados)
    const yy = yBarra() + 168
    let s = ""
    for (let i = 1; i < xs.length; i += 1) {
      const a = px(xs[i - 1])
      const b = px(xs[i])
      if (b - a < 2) continue
      s += `<line class="cota" x1="${a}" y1="${yy}" x2="${b}" y2="${yy}"/><line class="cota" x1="${a}" y1="${yy - 4}" x2="${a}" y2="${yy + 4}"/><line class="cota" x1="${b}" y1="${yy - 4}" x2="${b}" y2="${yy + 4}"/>`
      if (b - a > 30) {
        e.cotasVivas.push({ a: xs[i - 1], b: xs[i] })
        s += `<text class="cota-t editavel" data-editar="cota:${e.cotasVivas.length - 1}" x="${(a + b) / 2}" y="${yy + 15}" text-anchor="middle">${texto(xs[i] - xs[i - 1])}</text>`
      }
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
    const x0 = e.vista.cx - w / 2 / esc
    const x1 = e.vista.cx + w / 2 / esc
    for (let v = Math.ceil(x0 / passo) * passo; v <= x1; v += passo) {
      const cls = Math.abs(v) < passo / 100 ? "g-eixo" : Math.abs(v / grosso - Math.round(v / grosso)) < 1e-6 ? "g-maior" : "g-menor"
      const x = px(v)
      s += `<line class="${cls}" x1="${x}" y1="0" x2="${x}" y2="${h}"/>`
    }
    const y = yBarra()
    const marcado = (lista, i) => e.sel?.lista === lista && e.sel.i === i
    const [a, b] = [px(0), px(e.dados.L)]
    s += `<line class="peca${e.sel?.lista === "viga" ? " sel" : ""}" x1="${a}" y1="${y}" x2="${b}" y2="${y}"/>`
    s += `<text class="cota-t editavel" data-editar="L:0" x="${b + 12}" y="${y + 4}">L = ${texto(e.dados.L)} m</text>`
    s += cotas()
    e.dados.apoios.forEach((ap, i) => {
      s += simbolo(ap)
      s += `<text class="nome${marcado("apoios", i) ? " sel-t" : ""}" x="${px(ap.x) + 15}" y="${y + 22}">${ap.nome}</text>`
    })
    e.dados.rotulas.forEach((r, i) => {
      s += `<circle class="rotula${marcado("rotulas", i) ? " sel" : ""}" cx="${px(r.x)}" cy="${y}" r="6"/>`
      s += `<text class="nome${marcado("rotulas", i) ? " sel-t" : ""}" x="${px(r.x) + 8}" y="${y - 10}">${r.nome}</text>`
    })
    e.dados.cargas.forEach((c, i) => {
      s += desenhoDaCarga(c, marcado("cargas", i), i)
    })
    if (e.marcas && !e.gesto) {
      for (const r of e.marcas.reacoes ?? []) s += desenhoDaReacao(r)
      if (e.marcas.erro) {
        s += `<text class="ruim-t forte" x="${w / 2}" y="24" text-anchor="middle">${e.marcas.erro}</text>`
      }
    }
    if (e.gesto?.rascunho) s += e.gesto.rascunho
    if (e.ima !== null && e.ima !== undefined && e.ferramenta !== "mover") {
      s += `<circle class="ima" cx="${px(e.ima)}" cy="${y}" r="7"/>`
    }
    for (const al of alcas()) s += `<circle class="alca" cx="${al.px[0]}" cy="${al.px[1]}" r="${ALCA_PX}"/>`
    if (!e.dados.apoios.length && !e.gesto) {
      s += `<text class="vazia-t" x="${w / 2}" y="${y - 90}" text-anchor="middle">Ponha os apoios: escolha Pino, Rolete ou Engaste e clique na barra</text>`
    }
    svg.innerHTML = s
    svg.classList.toggle("desenho", e.ferramenta !== "mover")
  }

  // ---- alças do item selecionado
  function alcas() {
    if (e.ferramenta !== "mover" || !e.sel) return []
    const y = yBarra()
    if (e.sel.lista === "viga") return [{ tipo: "L", px: [px(e.dados.L), y] }]
    const it = item()
    if (it && e.sel.lista === "cargas" && COM_TRECHO.includes(it.tipo)) {
      return [
        { tipo: "ini", px: [px(it.x), y] },
        { tipo: "fim", px: [px(it.x2), y] },
      ]
    }
    return []
  }
  function alcaEm(ev) {
    const [mx, my] = noPonteiro(ev)
    return alcas().find((a) => Math.hypot(a.px[0] - mx, a.px[1] - my) <= ALCA_PX + 5)
  }
  function itemEm(ev) {
    const [mx, my] = noPonteiro(ev)
    const y = yBarra()
    // As cargas de ponto antes, a distribuída por último: ela é uma faixa larga.
    for (let i = e.dados.cargas.length - 1; i >= 0; i -= 1) {
      const c = e.dados.cargas[i]
      if (COM_TRECHO.includes(c.tipo)) continue
      const x = px(c.x)
      if (c.tipo === FORCA) {
        const [lo, hi] = c.valor < 0 ? [y - 6 - SETA_PX, y - 4] : [y + 4, y + 6 + SETA_PX]
        if (Math.abs(mx - x) < TOQUE_PX && my >= lo && my <= hi) return { lista: "cargas", i }
      } else if (c.tipo === MOMENTO) {
        if (Math.hypot(mx - x, my - y) < 28 && Math.hypot(mx - x, my - y) > 12) return { lista: "cargas", i }
      } else {
        const s = sinalDe(c.valor)
        const [xa, xb] = [Math.min(x, x + (c.tipo === AXIAL ? -s * 54 : s * 48)), Math.max(x, x + (c.tipo === AXIAL ? -s * 54 : s * 48))]
        const yy = c.tipo === AXIAL ? y - 14 : y - 22
        if (mx >= xa - 4 && mx <= xb + 4 && Math.abs(my - yy) < TOQUE_PX) return { lista: "cargas", i }
      }
    }
    for (let i = e.dados.rotulas.length - 1; i >= 0; i -= 1) {
      if (Math.hypot(mx - px(e.dados.rotulas[i].x), my - y) < 10) return { lista: "rotulas", i }
    }
    for (let i = e.dados.apoios.length - 1; i >= 0; i -= 1) {
      const a = e.dados.apoios[i]
      const x = px(a.x)
      const dentro = a.tipo === TRAVA ? mx >= x - 38 && mx <= x + 4 && Math.abs(my - y) < 18 : Math.abs(mx - x) < 18 && my >= y + 4 && my <= y + 40
      const parede = (a.tipo === ENGASTE || a.tipo === DESLIZANTE) && Math.abs(mx - x) < 14 && Math.abs(my - y) < 28
      if (dentro || parede) return { lista: "apoios", i }
    }
    for (let i = e.dados.cargas.length - 1; i >= 0; i -= 1) {
      const c = e.dados.cargas[i]
      if (!COM_TRECHO.includes(c.tipo)) continue
      const [xa, xb] = [Math.min(px(c.x), px(c.x2)), Math.max(px(c.x), px(c.x2))]
      if (mx < xa - 4 || mx > xb + 4) continue
      const faixa = c.tipo === AXIAL_DIST ? Math.abs(my - (y - 16)) < 12 : c.valor < 0 ? my >= y - 56 && my <= y - 6 : my >= y + 6 && my <= y + 56
      if (faixa) return { lista: "cargas", i }
    }
    if (mx >= px(0) - 6 && mx <= px(e.dados.L) + 6 && Math.abs(my - y) < TOQUE_PX) return { lista: "viga", i: 0 }
    return null
  }
  function moverItem(it, base, dx) {
    if (it.x2 !== null && it.x2 !== undefined && COM_TRECHO.includes(it.tipo)) {
      const largura = base.x2 - base.x
      const ini = Math.min(Math.max(base.x + dx, 0), e.dados.L - largura)
      it.x = arred(ini)
      it.x2 = arred(ini + largura)
      return
    }
    it.x = arred(naBarra(base.x + dx))
  }

  // ---- ponteiro
  function finalizarNovo(g) {
    const tipo = e.ferramenta
    const ini = g.ini
    const fim = g.fim ?? ini
    if (APOIOS.includes(tipo)) criarApoio(tipo, ini)
    else if (tipo === ROTULA) criarRotula(ini)
    else if (tipo === FORCA) {
      const sobe = g.moveu && g.dy < 0
      criarCarga(FORCA, ini, { valor: (sobe ? 1 : -1) * Math.abs(valorNovo(FORCA)) })
    } else if (COM_TRECHO.includes(tipo)) {
      if (g.moveu && fim !== ini) criarCarga(tipo, Math.min(ini, fim), { x2: Math.max(ini, fim) })
      else criarCarga(tipo, 0, { x2: e.dados.L })
    } else if (CARGAS.includes(tipo)) criarCarga(tipo, ini)
  }
  function rascunhoDoNovo(g) {
    const y = yBarra()
    const tipo = e.ferramenta
    if (tipo === FORCA) return g.dy < 0 ? seta([px(g.ini), y + 6 + SETA_PX], [px(g.ini), y + 6], "carga") : seta([px(g.ini), y - 6 - SETA_PX], [px(g.ini), y - 6], "carga")
    if (COM_TRECHO.includes(tipo)) return `<line class="rascunho" x1="${px(g.ini)}" y1="${y - 20}" x2="${px(g.fim)}" y2="${y - 20}"/>`
    return ""
  }

  svg.addEventListener("pointerdown", (ev) => {
    svg.focus({ preventScroll: true })
    svg.setPointerCapture(ev.pointerId)
    const x = mundo(ev)
    const valor = ev.target.closest?.("[data-editar]")
    if (valor && ev.button === 0 && e.ferramenta === "mover") {
      e.gesto = { tipo: "texto", el: valor }
      return
    }
    if (ev.button === 1) {
      e.gesto = { tipo: "pan", inicio: ev.clientX, vista: { ...e.vista } }
      return
    }
    if (e.ferramenta !== "mover") {
      const p = iman(x)
      e.gesto = { tipo: "novo", ini: p, fim: p, tela: [ev.clientX, ev.clientY], dy: 0 }
      return
    }
    const alca = alcaEm(ev)
    if (alca) {
      e.gesto = { tipo: "alca", alca, guardado: false }
      return
    }
    const alvo = itemEm(ev)
    if (!alvo) {
      e.sel = null
      e.gesto = { tipo: "pan", inicio: ev.clientX, vista: { ...e.vista } }
      montarPainel()
      desenhar()
      return
    }
    e.sel = alvo
    if (alvo.lista === "viga") {
      e.gesto = { tipo: "pan", inicio: ev.clientX, vista: { ...e.vista } }
    } else {
      const it = item()
      e.gesto = { tipo: "mover", inicio: x, ref: it.x, base: copiar(it), guardado: false }
    }
    montarPainel()
    desenhar()
  })

  svg.addEventListener("pointermove", (ev) => {
    const x = mundo(ev)
    infoXY.textContent = `x ${texto(x)} m`
    const g = e.gesto
    if (!g) {
      if (e.ferramenta !== "mover") {
        iman(x)
        desenhar()
      }
      return
    }
    if (g.tipo === "pan") {
      e.vista.cx = g.vista.cx - (ev.clientX - g.inicio) / e.vista.esc
      desenhar()
      return
    }
    if (g.tipo === "novo") {
      g.fim = iman(x)
      g.dy = ev.clientY - g.tela[1]
      g.moveu = g.moveu || Math.hypot(ev.clientX - g.tela[0], ev.clientY - g.tela[1]) > 6
      g.rascunho = g.moveu ? rascunhoDoNovo(g) : ""
      desenhar()
      return
    }
    if (g.tipo === "mover") {
      const alvo = iman(g.ref + x - g.inicio, e.sel)
      const dx = alvo - g.ref
      if (!dx && !g.moveu) return
      if (!g.guardado) {
        guardar()
        g.guardado = true
      }
      g.moveu = true
      moverItem(item(), g.base, dx)
      desenhar()
      return
    }
    if (g.tipo === "alca") {
      if (!g.guardado) {
        guardar()
        g.guardado = true
      }
      g.moveu = true
      if (g.alca.tipo === "L") {
        const L = Math.max(arred(Math.round(x / e.grade) * e.grade), e.grade)
        novoComprimento(e.dados, L)
      } else {
        const it = item()
        const p = iman(x, e.sel)
        if (g.alca.tipo === "ini") it.x = p
        else it.x2 = p
      }
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
    if (g.tipo === "texto") {
      abrirEdicao(g.el)
      return
    }
    if (g.tipo === "novo") {
      finalizarNovo(g)
      return
    }
    if (g.tipo === "alca" && g.moveu) {
      const it = item()
      if (it && it.x2 !== null && it.x2 !== undefined && it.x2 < it.x) [it.x, it.x2] = [it.x2, it.x]
      enviar()
      return
    }
    if (g.tipo === "mover" && g.moveu) {
      enviar()
      return
    }
    desenhar()
  })

  svg.addEventListener(
    "wheel",
    (ev) => {
      // Só com Ctrl: a resposta fica abaixo da prancheta, e a rodinha precisa descer a página.
      if (!ev.ctrlKey && !ev.metaKey) return
      ev.preventDefault()
      aproximar(ev.deltaY < 0 ? 1.15 : 1 / 1.15, mundo(ev))
    },
    { passive: false },
  )

  svg.addEventListener("keydown", (ev) => {
    const ctrl = ev.ctrlKey || ev.metaKey
    const tecla = ev.key.toLowerCase()
    const lado = { arrowleft: -1, arrowright: 1 }[tecla]
    if (ctrl && tecla === "z") acoes.desfazer()
    else if (ctrl && tecla === "y") acoes.refazer()
    else if (tecla === "delete" || tecla === "backspace") acoes.apagar()
    else if (tecla === "escape") {
      e.sel = null
      trocarFerramenta("mover")
      montarPainel()
    } else if (lado && item()) {
      guardar()
      const it = item()
      moverItem(it, copiar(it), lado * e.grade)
      enviar()
    } else if (!ctrl && tecla === "v") trocarFerramenta("mover")
    else return
    ev.preventDefault()
  })

  function trocarFerramenta(nome) {
    e.ferramenta = nome
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

  function montarGrades() {
    const ideal = e.dados.L > 0 ? e.dados.L / 40 : 0.1
    e.grade = GRADES.reduce((a, b) => (Math.abs(b - ideal) < Math.abs(a - ideal) ? b : a))
    seletorGrade.replaceChildren(
      ...GRADES.map((v) => {
        const o = document.createElement("option")
        o.value = String(v)
        o.textContent = `${texto(v)} m`
        o.selected = v === e.grade
        return o
      }),
    )
  }

  e.receber = (dados) => {
    const novos = dados.dados ?? e.dados
    let mudou = !painel.childElementCount
    if (dados.versao >= e.versao) {
      if (JSON.stringify(novos) !== JSON.stringify(e.dados)) {
        if (e.versao >= 0) guardar()
        e.dados = copiar(novos)
        if (e.sel && e.sel.lista !== "viga" && e.sel.i >= e.dados[e.sel.lista].length) e.sel = null
        mudou = true
      }
      e.versao = dados.versao
    }
    e.marcas = dados.marcas ?? null
    // Só com o svg já com largura: antes disso, o enquadramento sairia de uma tela de mentira.
    if (e.verAjuste !== dados.ajustar && svg.getBoundingClientRect().width > 0) {
      e.verAjuste = dados.ajustar
      ajustarVista()
      montarGrades()
    }
    if (mudou) montarPainel()
    desenhar()
  }

  trocarFerramenta("mover")
  new ResizeObserver(() => {
    if (e.verAjuste === null && svg.getBoundingClientRect().width > 0) {
      e.verAjuste = "primeiro"
      ajustarVista()
      montarGrades()
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
