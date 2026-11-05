// Prancheta da seção: desenha, move e dimensiona as partes em mm, com y para cima.
// O Python é o dono das contas: aqui só nasce o desenho, que vai para lá a cada gesto terminado
// (nunca durante o arrasto). Toda a escuta fica em elementos da própria prancheta, e o estado fica
// preso ao parentElement, porque o Streamlit chama esta função de novo a cada rodada.

const ESTADOS = new WeakMap()
const IMA_PX = 9
const ALCA_PX = 6

const copiar = (v) => JSON.parse(JSON.stringify(v))
const arred = (v) => Math.round(v * 1000) / 1000
const texto = (v) => String(arred(v)).replace(".", ",")
const lerNumero = (s) => Number(String(s).trim().replace(",", "."))

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

function contem(p, x, y) {
  if (p.forma === "circ") return (x - p.x) ** 2 + (y - p.y) ** 2 <= (p.b / 2) ** 2
  const anel = cantos(p)
  let dentro = false
  for (let i = 0, j = anel.length - 1; i < anel.length; j = i++) {
    const [xi, yi] = anel[i]
    const [xj, yj] = anel[j]
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) dentro = !dentro
  }
  return dentro
}

function mover(p, dx, dy) {
  p.x += dx
  p.y += dy
  if (p.forma === "poli") p.pontos = p.pontos.map(([x, y]) => [x + dx, y + dy])
}

function novaGrade(espacoMinimo, escala) {
  const passos = [0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
  return passos.find((p) => p * escala >= espacoMinimo) ?? 10000
}

function criar(raiz) {
  const svg = raiz.querySelector("svg")
  const painel = raiz.querySelector("[data-painel]")
  const infoXY = raiz.querySelector('[data-i="xy"]')
  const infoDica = raiz.querySelector('[data-i="dica"]')
  const caixaFuro = raiz.querySelector('[data-c="furo"]')
  const seletorGrade = raiz.querySelector('[data-c="grade"]')

  const e = {
    enviar: null,
    partes: [],
    versao: -1,
    verAjuste: null,
    marcas: null,
    ferramenta: "mover",
    sel: new Set(),
    grade: 5,
    vista: { cx: 0, cy: 0, esc: 1 },
    gesto: null,
    guias: { x: null, y: null },
    polilinha: null,
    ponteiro: null,
    passado: [],
    futuro: [],
  }

  const tela = () => {
    const r = svg.getBoundingClientRect()
    return { w: r.width || 800, h: r.height || 560 }
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
  const naGrade = (v) => arred(Math.round(v / e.grade) * e.grade)

  // ---- ímã: bordas e centros das outras partes, depois a grade
  function referencias(fora) {
    const xs = [0]
    const ys = [0]
    e.partes.forEach((p, i) => {
      if (fora.has(i)) return
      const c = caixa(p)
      xs.push(c[0], (c[0] + c[2]) / 2, c[2])
      ys.push(c[1], (c[1] + c[3]) / 2, c[3])
    })
    return { xs, ys }
  }
  function maisPerto(lista, valor) {
    let melhor = null
    let distancia = IMA_PX / e.vista.esc
    for (const v of lista) {
      const d = Math.abs(v - valor)
      if (d < distancia) {
        distancia = d
        melhor = v
      }
    }
    return melhor
  }
  function ponto(x, y, fora = new Set()) {
    const r = referencias(fora)
    const ix = maisPerto(r.xs, x)
    const iy = maisPerto(r.ys, y)
    e.guias = { x: ix, y: iy }
    return [ix ?? naGrade(x), iy ?? naGrade(y)]
  }
  function deslocar(base, dx, dy, fora) {
    const r = referencias(fora)
    const eixo = (lo, hi, d, lista) => {
      let melhor = null
      let dist = IMA_PX / e.vista.esc
      for (const v of [lo + d, (lo + hi) / 2 + d, hi + d]) {
        for (const a of lista) {
          const k = Math.abs(a - v)
          if (k < dist) {
            dist = k
            melhor = [a, a - v]
          }
        }
      }
      return melhor
    }
    const ax = eixo(base[0], base[2], dx, r.xs)
    const ay = eixo(base[1], base[3], dy, r.ys)
    e.guias = { x: ax ? ax[0] : null, y: ay ? ay[0] : null }
    return [
      ax ? dx + ax[1] : naGrade(base[0] + dx) - base[0],
      ay ? dy + ay[1] : naGrade(base[1] + dy) - base[1],
    ]
  }

  // ---- histórico e envio
  function guardar() {
    e.passado.push(copiar(e.partes))
    if (e.passado.length > 60) e.passado.shift()
    e.futuro = []
  }
  function enviar() {
    e.versao += 1
    e.enviar?.("edicao", { partes: copiar(e.partes), versao: e.versao })
    montarPainel()
    desenhar()
  }
  function grupoDe(i) {
    const g = e.partes[i].grupo
    if (!g) return [i]
    return e.partes.flatMap((p, k) => (p.grupo === g ? [k] : []))
  }
  function novoGrupo() {
    return Math.max(0, ...e.partes.map((p) => p.grupo || 0)) + 1
  }
  function selecionadas() {
    return [...e.sel].filter((i) => i < e.partes.length).map((i) => e.partes[i])
  }

  // ---- ações sobre a seleção
  const acoes = {
    desfazer() {
      if (!e.passado.length) return
      e.futuro.push(copiar(e.partes))
      e.partes = e.passado.pop()
      e.sel.clear()
      enviar()
    },
    refazer() {
      if (!e.futuro.length) return
      e.passado.push(copiar(e.partes))
      e.partes = e.futuro.pop()
      e.sel.clear()
      enviar()
    },
    ajustar() {
      ajustarVista()
      desenhar()
    },
    apagar() {
      if (!e.sel.size) return
      guardar()
      e.partes = e.partes.filter((_, i) => !e.sel.has(i))
      e.sel.clear()
      enviar()
    },
    duplicar() {
      if (!e.sel.size) return
      guardar()
      const lista = selecionadas().map(copiar)
      const c = caixaDe(lista)
      const g = lista.length > 1 ? novoGrupo() : 0
      const inicio = e.partes.length
      lista.forEach((p) => {
        p.grupo = g
        mover(p, c[2] - c[0], 0)
        e.partes.push(p)
      })
      e.sel = new Set(lista.map((_, k) => inicio + k))
      enviar()
    },
    espelhoX() {
      espelhar(0, false)
    },
    espelhoY() {
      espelhar(1, false)
    },
    copiaEspelhada() {
      espelhar(0, true)
    },
    girar() {
      if (!e.sel.size) return
      guardar()
      const lista = selecionadas()
      const c = caixaDe(lista)
      const cx = (c[0] + c[2]) / 2
      const cy = (c[1] + c[3]) / 2
      const gira = (x, y) => [cx - (y - cy), cy + (x - cx)]
      lista.forEach((p) => {
        if (p.forma === "poli") {
          p.pontos = p.pontos.map(([x, y]) => gira(x, y))
          return
        }
        ;[p.x, p.y] = gira(p.x, p.y)
        if (p.forma === "ret") {
          if (p.giro) p.giro = (p.giro + 90) % 180
          else [p.b, p.h] = [p.h, p.b]
        }
      })
      enviar()
    },
    trocarFuro() {
      if (!e.sel.size) return
      guardar()
      const valor = !selecionadas()[0].furo
      selecionadas().forEach((p) => {
        p.furo = valor
      })
      enviar()
    },
  }

  function espelhar(eixo, copia) {
    if (!e.sel.size) return
    guardar()
    const lista = copia ? selecionadas().map(copiar) : selecionadas()
    const c = caixaDe(lista)
    const linha = copia ? c[2] : (c[eixo] + c[eixo + 2]) / 2
    const reflete = (v) => 2 * linha - v
    lista.forEach((p) => {
      if (p.forma === "poli") {
        p.pontos = p.pontos.map((v) => (eixo === 0 ? [reflete(v[0]), v[1]] : [v[0], reflete(v[1])]))
      } else {
        if (eixo === 0) p.x = reflete(p.x)
        else p.y = reflete(p.y)
        if (p.giro) p.giro = (180 - p.giro) % 180
      }
    })
    if (copia) {
      const g = lista.length > 1 ? novoGrupo() : 0
      const inicio = e.partes.length
      lista.forEach((p) => {
        p.grupo = g
        e.partes.push(p)
      })
      e.sel = new Set(lista.map((_, k) => inicio + k))
    }
    enviar()
  }

  // ---- painel de medidas da seleção
  function campo(rotulo, valor, aplicar, dica) {
    const r = document.createElement("label")
    r.className = "campo"
    r.title = dica
    r.append(rotulo)
    const entrada = document.createElement("input")
    entrada.type = "text"
    entrada.inputMode = "decimal"
    entrada.value = texto(valor)
    entrada.addEventListener("change", () => {
      const n = lerNumero(entrada.value)
      if (!Number.isFinite(n)) {
        entrada.value = texto(valor)
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
  function botao(rotulo, acao, dica, classe = "") {
    const b = document.createElement("button")
    b.type = "button"
    b.textContent = rotulo
    b.title = dica
    b.className = `solto ${classe}`
    b.addEventListener("click", () => acoes[acao]())
    return b
  }
  function montarPainel() {
    painel.replaceChildren()
    const lista = selecionadas()
    if (!lista.length) {
      const dica = document.createElement("span")
      dica.className = "apagado"
      dica.textContent = e.partes.length
        ? "Clique numa parte para ver e digitar as medidas. Encostar é automático: as bordas têm ímã."
        : "Escolha um modelo acima ou clique em Chapa e arraste aqui embaixo."
      painel.append(dica)
      return
    }
    const titulo = document.createElement("span")
    titulo.className = "titulo"
    if (lista.length === 1) {
      const p = lista[0]
      titulo.textContent =
        p.forma === "circ" ? "Círculo" : p.forma === "poli" ? "Polígono" : "Chapa"
      painel.append(titulo)
      if (p.forma === "poli") {
        const c = caixa(p)
        painel.append(
          campo("x", (c[0] + c[2]) / 2, (v) => mover(p, v - (c[0] + c[2]) / 2, 0), "Centro em x (mm)"),
          campo("y", (c[1] + c[3]) / 2, (v) => mover(p, 0, v - (c[1] + c[3]) / 2), "Centro em y (mm)"),
        )
      } else {
        painel.append(
          campo("x", p.x, (v) => { p.x = v }, "Centro em x (mm)"),
          campo("y", p.y, (v) => { p.y = v }, "Centro em y (mm)"),
          campo(p.forma === "circ" ? "Ø" : "b", p.b, (v) => {
            if (v <= 0) return
            p.b = v
            if (p.forma === "circ") p.h = v
          }, "Largura ou diâmetro (mm)"),
        )
        if (p.forma === "ret") {
          painel.append(
            campo("h", p.h, (v) => { if (v > 0) p.h = v }, "Altura (mm)"),
            campo("giro", p.giro || 0, (v) => { p.giro = v }, "Giro em graus, anti-horário"),
          )
        }
      }
    } else {
      const c = caixaDe(lista)
      titulo.textContent = `${lista.length} partes`
      painel.append(
        titulo,
        campo("x", (c[0] + c[2]) / 2, (v) => {
          const d = v - (c[0] + c[2]) / 2
          lista.forEach((p) => mover(p, d, 0))
        }, "Centro do conjunto em x (mm)"),
        campo("y", (c[1] + c[3]) / 2, (v) => {
          const d = v - (c[1] + c[3]) / 2
          lista.forEach((p) => mover(p, 0, d))
        }, "Centro do conjunto em y (mm)"),
      )
    }
    painel.append(
      botao("Duplicar", "duplicar", "Cópia ao lado (Ctrl+D)"),
      botao("Cópia espelhada", "copiaEspelhada", "Cópia espelhada encostada à direita: 2 U, 2 cantoneiras"),
      botao("↔", "espelhoX", "Espelhar na horizontal"),
      botao("↕", "espelhoY", "Espelhar na vertical"),
      botao("⟳ 90°", "girar", "Girar 90°"),
      botao("Cheio/Furo", "trocarFuro", "Trocar entre cheio e furo"),
      botao("Apagar", "apagar", "Apagar (Delete)", "perigo"),
    )
  }

  // ---- vista
  function ajustarVista() {
    const { w, h } = tela()
    if (!e.partes.length) {
      e.vista = { cx: 0, cy: 0, esc: Math.min(w, h) / 500 }
      return
    }
    const c = caixaDe(e.partes)
    const largura = Math.max(c[2] - c[0], 1)
    const altura = Math.max(c[3] - c[1], 1)
    e.vista = {
      cx: (c[0] + c[2]) / 2,
      cy: (c[1] + c[3]) / 2,
      esc: Math.min((w - 150) / largura, (h - 130) / altura),
    }
  }

  // ---- desenho
  function formaSvg(p, classe) {
    if (p.forma === "circ") {
      const [x, y] = px(p.x, p.y)
      return `<circle class="${classe}" cx="${x}" cy="${y}" r="${(p.b / 2) * e.vista.esc}"/>`
    }
    const pts = cantos(p).map(([x, y]) => px(x, y).join(",")).join(" ")
    return `<polygon class="${classe}" points="${pts}"/>`
  }
  function cotaH(x0, x1, y, rotulo) {
    const [a, b] = [px(x0, y), px(x1, y)]
    const yy = a[1]
    return `<line class="cota" x1="${a[0]}" y1="${yy}" x2="${b[0]}" y2="${yy}"/>
      <line class="cota" x1="${a[0]}" y1="${yy - 5}" x2="${a[0]}" y2="${yy + 5}"/>
      <line class="cota" x1="${b[0]}" y1="${yy - 5}" x2="${b[0]}" y2="${yy + 5}"/>
      <text class="cota-txt" x="${(a[0] + b[0]) / 2}" y="${yy + 16}" text-anchor="middle">${rotulo}</text>`
  }
  function cotaV(x, y0, y1, rotulo) {
    const [a, b] = [px(x, y0), px(x, y1)]
    const xx = a[0]
    const my = (a[1] + b[1]) / 2
    return `<line class="cota" x1="${xx}" y1="${a[1]}" x2="${xx}" y2="${b[1]}"/>
      <line class="cota" x1="${xx - 5}" y1="${a[1]}" x2="${xx + 5}" y2="${a[1]}"/>
      <line class="cota" x1="${xx - 5}" y1="${b[1]}" x2="${xx + 5}" y2="${b[1]}"/>
      <text class="cota-txt" x="${xx - 8}" y="${my + 4}" text-anchor="end">${rotulo}</text>`
  }
  function desenhar() {
    const { w, h } = tela()
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`)
    const esc = e.vista.esc
    const passo = novaGrade(12, esc)
    const grosso = passo * 5
    let s = ""
    const vis = {
      x0: e.vista.cx - w / 2 / esc,
      x1: e.vista.cx + w / 2 / esc,
      y0: e.vista.cy - h / 2 / esc,
      y1: e.vista.cy + h / 2 / esc,
    }
    for (let v = Math.ceil(vis.x0 / passo) * passo; v <= vis.x1; v += passo) {
      const [x] = px(v, 0)
      const cls = Math.abs(v) < 1e-6 ? "g-eixo" : Math.abs(v / grosso - Math.round(v / grosso)) < 1e-6 ? "g-maior" : "g-menor"
      s += `<line class="${cls}" x1="${x}" y1="0" x2="${x}" y2="${h}"/>`
    }
    for (let v = Math.ceil(vis.y0 / passo) * passo; v <= vis.y1; v += passo) {
      const [, y] = px(0, v)
      const cls = Math.abs(v) < 1e-6 ? "g-eixo" : Math.abs(v / grosso - Math.round(v / grosso)) < 1e-6 ? "g-maior" : "g-menor"
      s += `<line class="${cls}" x1="0" y1="${y}" x2="${w}" y2="${y}"/>`
    }
    e.partes.forEach((p, i) => {
      if (!p.furo) s += formaSvg(p, `cheia${e.sel.has(i) ? " selecao" : ""}`)
    })
    e.partes.forEach((p, i) => {
      if (p.furo) s += formaSvg(p, `vazio${e.sel.has(i) ? " selecao" : ""}`)
    })

    const cheias = e.partes.filter((p) => !p.furo)
    if (cheias.length) {
      const c = caixaDe(cheias)
      s += cotaH(c[0], c[2], c[1] - 26 / esc, `${texto(c[2] - c[0])} mm`)
      s += cotaV(c[0] - 26 / esc, c[1], c[3], `${texto(c[3] - c[1])} mm`)
      if (e.sel.size === 1) {
        const p = selecionadas()[0]
        if (p?.forma === "ret" && !p.giro) {
          const k = caixa(p)
          s += cotaH(k[0], k[2], k[3] + 26 / esc, `b ${texto(p.b)}`)
          s += cotaV(k[2] + 8 / esc + 34 / esc, k[1], k[3], `h ${texto(p.h)}`)
        }
      }
    }

    if (e.marcas && !e.gesto) {
      const [gx, gy] = px(e.marcas.xc, e.marcas.yc)
      s += `<circle class="marca-g" cx="${gx}" cy="${gy}" r="6"/>
        <line class="marca-g" x1="${gx - 11}" y1="${gy}" x2="${gx + 11}" y2="${gy}"/>
        <line class="marca-g" x1="${gx}" y1="${gy - 11}" x2="${gx}" y2="${gy + 11}"/>
        <text class="txt-g" x="${gx + 10}" y="${gy - 9}">G</text>`
      if (e.marcas.mostrar_cc) {
        const [cx, cy] = px(e.marcas.xs, e.marcas.ys)
        s += `<rect class="marca-cc" x="${cx - 5}" y="${cy - 5}" width="10" height="10" transform="rotate(45 ${cx} ${cy})"/>
          <text class="txt-cc" x="${cx + 10}" y="${cy - 8}">CC</text>`
      }
      if (e.marcas.girado) {
        const a = (e.marcas.angulo * Math.PI) / 180
        const r = 1000
        s += `<line class="marca-g" stroke-dasharray="6 4" x1="${gx - r * Math.cos(a)}" y1="${gy + r * Math.sin(a)}" x2="${gx + r * Math.cos(a)}" y2="${gy - r * Math.sin(a)}"/>`
      }
    }

    if (e.gesto?.rascunho) s += e.gesto.rascunho
    if (e.polilinha) {
      const pts = [...e.polilinha, e.ponteiro].filter(Boolean)
      s += `<polyline class="rascunho" points="${pts.map(([x, y]) => px(x, y).join(",")).join(" ")}"/>`
      e.polilinha.forEach(([x, y]) => {
        const [a, b] = px(x, y)
        s += `<circle class="alca" cx="${a}" cy="${b}" r="4"/>`
      })
    }
    if (e.guias.x !== null) {
      const [x] = px(e.guias.x, 0)
      s += `<line class="guia" x1="${x}" y1="0" x2="${x}" y2="${h}"/>`
    }
    if (e.guias.y !== null) {
      const [, y] = px(0, e.guias.y)
      s += `<line class="guia" x1="0" y1="${y}" x2="${w}" y2="${y}"/>`
    }
    for (const a of alcas()) {
      s += `<circle class="alca" cx="${a.px[0]}" cy="${a.px[1]}" r="${ALCA_PX}"/>`
    }
    if (!e.partes.length && !e.polilinha && !e.gesto) {
      s += `<text class="vazia-txt" x="${w / 2}" y="${h / 2}" text-anchor="middle">Arraste aqui para desenhar a primeira chapa</text>`
    }
    svg.innerHTML = s
    svg.classList.toggle("desenho", e.ferramenta !== "mover")
  }

  // ---- alças da parte selecionada
  function alcas() {
    if (e.sel.size !== 1 || e.ferramenta !== "mover") return []
    const i = [...e.sel][0]
    const p = e.partes[i]
    if (!p) return []
    if (p.forma === "circ") return [{ tipo: "raio", px: px(p.x + p.b / 2, p.y) }]
    if (p.forma === "poli") {
      return p.pontos.map((v, k) => ({ tipo: "vertice", k, px: px(v[0], v[1]) }))
    }
    if (p.giro) return []
    const x0 = p.x - p.b / 2
    const x1 = p.x + p.b / 2
    const y0 = p.y - p.h / 2
    const y1 = p.y + p.h / 2
    const lista = []
    for (const [sx, x] of [[-1, x0], [0, p.x], [1, x1]]) {
      for (const [sy, y] of [[-1, y0], [0, p.y], [1, y1]]) {
        if (sx || sy) lista.push({ tipo: "lado", sx, sy, px: px(x, y) })
      }
    }
    return lista
  }
  function alcaEm(ev) {
    const r = svg.getBoundingClientRect()
    const mx = ev.clientX - r.left
    const my = ev.clientY - r.top
    return alcas().find((a) => Math.hypot(a.px[0] - mx, a.px[1] - my) <= ALCA_PX + 4)
  }
  function parteEm(x, y) {
    for (let i = e.partes.length - 1; i >= 0; i--) {
      if (e.partes[i].furo && contem(e.partes[i], x, y)) return i
    }
    for (let i = e.partes.length - 1; i >= 0; i--) {
      if (!e.partes[i].furo && contem(e.partes[i], x, y)) return i
    }
    return null
  }

  // ---- ponteiro
  function fecharPoligono() {
    const lista = e.polilinha
    e.polilinha = null
    e.ponteiro = null
    if (!lista || lista.length < 3) {
      desenhar()
      return
    }
    guardar()
    e.partes.push({
      forma: "poli",
      x: 0,
      y: 0,
      b: 0,
      h: 0,
      giro: 0,
      furo: caixaFuro.checked,
      pontos: lista,
      grupo: 0,
    })
    e.sel = new Set([e.partes.length - 1])
    trocarFerramenta("mover")
    enviar()
  }

  svg.addEventListener("pointerdown", (ev) => {
    svg.focus({ preventScroll: true })
    svg.setPointerCapture(ev.pointerId)
    const [x, y] = mundo(ev)
    if (ev.button === 1) {
      e.gesto = { tipo: "pan", inicio: [ev.clientX, ev.clientY], vista: { ...e.vista } }
      return
    }
    if (e.ferramenta === "poli") {
      const [a, b] = ponto(x, y)
      if (e.polilinha?.length > 2) {
        const [p0, q0] = px(...e.polilinha[0])
        const [p1, q1] = px(a, b)
        if (Math.hypot(p0 - p1, q0 - q1) < 12) {
          fecharPoligono()
          return
        }
      }
      e.polilinha = [...(e.polilinha || []), [a, b]]
      desenhar()
      return
    }
    if (e.ferramenta !== "mover") {
      e.gesto = { tipo: "novo", inicio: ponto(x, y), fim: null }
      return
    }
    const alca = alcaEm(ev)
    if (alca) {
      const i = [...e.sel][0]
      e.gesto = { tipo: "alca", alca, i, antes: copiar(e.partes[i]), guardado: false }
      return
    }
    const i = parteEm(x, y)
    if (i === null) {
      e.sel.clear()
      e.gesto = { tipo: "pan", inicio: [ev.clientX, ev.clientY], vista: { ...e.vista } }
      montarPainel()
      desenhar()
      return
    }
    const grupo = grupoDe(i)
    if (!e.sel.has(i)) {
      e.sel = new Set(grupo)
    } else if (e.sel.size > 1) {
      e.gesto = { sozinha: i }
    }
    const fora = new Set(e.sel)
    e.gesto = {
      ...e.gesto,
      tipo: "mover",
      inicio: [x, y],
      base: copiar(selecionadas()),
      caixa: caixaDe(selecionadas()),
      fora,
      guardado: false,
    }
    montarPainel()
    desenhar()
  })

  svg.addEventListener("pointermove", (ev) => {
    const [x, y] = mundo(ev)
    infoXY.textContent = `x ${texto(x)} · y ${texto(y)} mm`
    const g = e.gesto
    if (e.polilinha) {
      e.ponteiro = ponto(x, y)
      desenhar()
      return
    }
    if (!g) return
    if (g.tipo === "pan") {
      e.vista.cx = g.vista.cx - (ev.clientX - g.inicio[0]) / e.vista.esc
      e.vista.cy = g.vista.cy + (ev.clientY - g.inicio[1]) / e.vista.esc
      desenhar()
      return
    }
    if (g.tipo === "novo") {
      const fim = ponto(x, y)
      g.fim = fim
      const [x0, y0] = g.inicio
      if (e.ferramenta === "circ") {
        const raio = Math.hypot(fim[0] - x0, fim[1] - y0)
        g.medida = `Ø ${texto(2 * raio)}`
        g.rascunho = `<circle class="rascunho" cx="${px(x0, y0)[0]}" cy="${px(x0, y0)[1]}" r="${raio * e.vista.esc}"/>`
      } else {
        const [a, b] = [px(x0, y0), px(fim[0], fim[1])]
        g.medida = `${texto(Math.abs(fim[0] - x0))} × ${texto(Math.abs(fim[1] - y0))}`
        g.rascunho = `<rect class="rascunho" x="${Math.min(a[0], b[0])}" y="${Math.min(a[1], b[1])}" width="${Math.abs(a[0] - b[0])}" height="${Math.abs(a[1] - b[1])}"/>`
      }
      infoDica.textContent = g.medida
      desenhar()
      return
    }
    if (g.tipo === "mover") {
      const [dx, dy] = deslocar(g.caixa, x - g.inicio[0], y - g.inicio[1], g.fora)
      if (!dx && !dy) return
      if (!g.guardado) {
        guardar()
        g.guardado = true
      }
      g.moveu = true
      ;[...e.sel].forEach((i, k) => {
        e.partes[i] = copiar(g.base[k])
        mover(e.partes[i], dx, dy)
      })
      desenhar()
      return
    }
    if (g.tipo === "alca") {
      if (!g.guardado) {
        guardar()
        g.guardado = true
      }
      const p = e.partes[g.i]
      const fora = new Set([g.i])
      const [a, b] = ponto(x, y, fora)
      const antes = g.antes
      if (g.alca.tipo === "raio") {
        p.b = p.h = Math.max(2 * Math.hypot(a - p.x, b - p.y), 0.1)
      } else if (g.alca.tipo === "vertice") {
        p.pontos[g.alca.k] = [a, b]
      } else {
        const { sx, sy } = g.alca
        if (sx) {
          const fixo = antes.x - (sx * antes.b) / 2
          p.b = Math.max(Math.abs(a - fixo), 0.1)
          p.x = fixo + (sx * p.b) / 2
        }
        if (sy) {
          const fixo = antes.y - (sy * antes.h) / 2
          p.h = Math.max(Math.abs(b - fixo), 0.1)
          p.y = fixo + (sy * p.h) / 2
        }
      }
      g.moveu = true
      desenhar()
    }
  })

  svg.addEventListener("pointerup", () => {
    const g = e.gesto
    e.gesto = null
    e.guias = { x: null, y: null }
    infoDica.textContent = ""
    if (!g) {
      desenhar()
      return
    }
    if (g.tipo === "novo" && g.fim) {
      const [x0, y0] = g.inicio
      const [x1, y1] = g.fim
      if (e.ferramenta === "circ") {
        const d = 2 * Math.hypot(x1 - x0, y1 - y0)
        if (d > 0) {
          guardar()
          e.partes.push({ forma: "circ", x: x0, y: y0, b: d, h: d, giro: 0, furo: caixaFuro.checked, pontos: [], grupo: 0 })
          e.sel = new Set([e.partes.length - 1])
          trocarFerramenta("mover")
          enviar()
          return
        }
      } else if (x1 !== x0 && y1 !== y0) {
        guardar()
        e.partes.push({
          forma: "ret",
          x: (x0 + x1) / 2,
          y: (y0 + y1) / 2,
          b: Math.abs(x1 - x0),
          h: Math.abs(y1 - y0),
          giro: 0,
          furo: caixaFuro.checked,
          pontos: [],
          grupo: 0,
        })
        e.sel = new Set([e.partes.length - 1])
        trocarFerramenta("mover")
        enviar()
        return
      }
    }
    if (g.tipo === "mover" && !g.moveu && g.sozinha !== undefined) {
      e.sel = new Set([g.sozinha])
      montarPainel()
    }
    if ((g.tipo === "mover" || g.tipo === "alca") && g.moveu) {
      enviar()
      return
    }
    desenhar()
  })

  svg.addEventListener(
    "wheel",
    (ev) => {
      ev.preventDefault()
      const [x, y] = mundo(ev)
      const fator = ev.deltaY < 0 ? 1.15 : 1 / 1.15
      const esc = Math.min(Math.max(e.vista.esc * fator, 0.02), 200)
      const k = e.vista.esc / esc
      e.vista = { cx: x + (e.vista.cx - x) * k, cy: y + (e.vista.cy - y) * k, esc }
      desenhar()
    },
    { passive: false },
  )

  svg.addEventListener("keydown", (ev) => {
    const ctrl = ev.ctrlKey || ev.metaKey
    const tecla = ev.key.toLowerCase()
    const seta = { arrowleft: [-1, 0], arrowright: [1, 0], arrowup: [0, 1], arrowdown: [0, -1] }[tecla]
    if (ctrl && tecla === "z") acoes.desfazer()
    else if (ctrl && tecla === "y") acoes.refazer()
    else if (ctrl && tecla === "d") acoes.duplicar()
    else if (tecla === "delete" || tecla === "backspace") acoes.apagar()
    else if (tecla === "escape") {
      e.polilinha = null
      e.sel.clear()
      trocarFerramenta("mover")
      montarPainel()
    } else if (tecla === "enter" && e.polilinha) fecharPoligono()
    else if (seta && e.sel.size) {
      guardar()
      selecionadas().forEach((p) => mover(p, seta[0] * e.grade, seta[1] * e.grade))
      enviar()
    } else if (!ctrl && "vrcp".includes(tecla)) {
      trocarFerramenta({ v: "mover", r: "ret", c: "circ", p: "poli" }[tecla])
    } else if (!ctrl && tecla === "f") {
      caixaFuro.checked = !caixaFuro.checked
    } else return
    ev.preventDefault()
  })

  function trocarFerramenta(nome) {
    e.ferramenta = nome
    e.polilinha = null
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

  e.receber = (dados) => {
    const novas = dados.partes ?? []
    if (dados.versao >= e.versao) {
      if (JSON.stringify(novas) !== JSON.stringify(e.partes)) {
        if (e.versao >= 0) guardar()
        e.partes = copiar(novas)
        e.sel = new Set([...e.sel].filter((i) => i < e.partes.length))
      }
      e.versao = dados.versao
    }
    e.marcas = dados.marcas ?? null
    if (e.verAjuste !== dados.ajustar) {
      e.verAjuste = dados.ajustar
      ajustarVista()
    }
    montarPainel()
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
