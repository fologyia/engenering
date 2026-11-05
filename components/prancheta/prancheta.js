// Prancheta da seção: desenha, move e dimensiona as partes em mm, com y para cima.
// O Python é o dono das contas: aqui só nasce o desenho, que vai para lá a cada gesto terminado
// (nunca durante o arrasto). Toda a escuta fica em elementos da própria prancheta, e o estado fica
// preso ao parentElement, porque o Streamlit chama esta função de novo a cada rodada.

const ESTADOS = new WeakMap()
const IMA_PX = 9
const ALCA_PX = 6
const ENCAIXE_PX = 13
const DICAS = {
  poli: "Clique os pontos, ou digite: 100 (na direção do mouse), 100<45 (ângulo), @50;20 (x;y). Shift trava o ângulo. Enter fecha, Backspace volta um ponto.",
  cota: "Clique no ponto que fica, no ponto que anda e no lugar da cota. O lugar escolhe: em cima, horizontal; ao lado, vertical; na diagonal, direta.",
}
const NOME_DO_ENCAIXE = { v: "Ponto", m: "Meio do lado", c: "Centro" }

const copiar = (v) => JSON.parse(JSON.stringify(v))
const arred = (v) => Math.round(v * 1000) / 1000
const texto = (v) => String(arred(v)).replace(".", ",")

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
  const caixaOrto = raiz.querySelector('[data-c="orto"]')

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
    cotas: [],
    novaCota: null,
    mouse: null,
    encaixe: null,
    orto: false,
    vertice: null,
    realce: null,
    pontaTrocada: false,
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
  function encaixeEm(x, y, fora = new Set()) {
    const [mx, my] = px(x, y)
    let melhor = null
    let distancia = ENCAIXE_PX
    e.partes.forEach((p, i) => {
      if (fora.has(i)) return
      for (const a of ancorasDaParte(p, i)) {
        const [u, v] = px(a.x, a.y)
        const d = Math.hypot(u - mx, v - my)
        if (d < distancia) {
          distancia = d
          melhor = a
        }
      }
    })
    return melhor
  }
  function ponto(x, y, fora = new Set()) {
    e.encaixe = encaixeEm(x, y, fora)
    if (e.encaixe) {
      e.guias = { x: null, y: null }
      return [e.encaixe.x, e.encaixe.y]
    }
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
  const foto = () => ({ partes: copiar(e.partes), cotas: copiar(e.cotas) })
  function guardar() {
    e.passado.push(foto())
    if (e.passado.length > 60) e.passado.shift()
    e.futuro = []
  }
  function voltarA(guardada) {
    e.partes = guardada.partes
    e.cotas = guardada.cotas
    e.sel.clear()
    e.vertice = null
    enviar()
  }
  function enviar() {
    e.versao += 1
    e.enviar?.("edicao", { partes: copiar(e.partes), cotas: copiar(e.cotas), versao: e.versao })
    montarPainel()
    desenhar()
  }
  function verticeAtual() {
    if (e.vertice === null || e.sel.size !== 1) return null
    const p = selecionadas()[0]
    return p?.forma === "poli" && e.vertice < p.pontos.length ? e.vertice : null
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
      e.futuro.push(foto())
      voltarA(e.passado.pop())
    },
    refazer() {
      if (!e.futuro.length) return
      e.passado.push(foto())
      voltarA(e.futuro.pop())
    },
    ajustar() {
      ajustarVista()
      desenhar()
    },
    apagar() {
      if (!e.sel.size) return
      guardar()
      e.cotas = cotasSemPartes(e.cotas, e.sel)
      e.partes = e.partes.filter((_, i) => !e.sel.has(i))
      e.sel.clear()
      enviar()
    },
    apagarPonto() {
      const k = verticeAtual()
      if (k === null) return
      const i = [...e.sel][0]
      if (e.partes[i].pontos.length <= 3) {
        infoDica.textContent = "O polígono precisa de ao menos 3 pontos."
        return
      }
      const copia = copiar(e.partes)
      const cotas = apagarVertice(copia, e.cotas, i, k)
      const erro = problemaDoPoligono(copia[i].pontos)
      if (erro) {
        infoDica.textContent = erro
        return
      }
      guardar()
      e.partes = copia
      e.cotas = cotas
      e.vertice = null
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
      const lido = lerValorDigitado(entrada.value, valor, "mm")
      if (lido.erro) {
        entrada.value = texto(valor)
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
      const k = verticeAtual()
      if (k !== null) {
        const [vx, vy] = p.pontos[k]
        titulo.textContent = `Ponto ${k + 1}`
        // Só o que é do ponto. Com os botões da parte o painel cresceria, e a prancheta desceria
        // embaixo do mouse logo depois do clique.
        painel.append(
          campo("x", vx, (v) => { p.pontos[k] = [v, p.pontos[k][1]] }, "Posição do ponto em x (mm)"),
          campo("y", vy, (v) => { p.pontos[k] = [p.pontos[k][0], v] }, "Posição do ponto em y (mm)"),
          botao("Apagar ponto", "apagarPonto", "Tira este ponto do polígono (Delete)", "perigo"),
        )
        return
      }
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
            dimensionarParte(e.partes, [...e.sel][0], "b", v)
          }, "Largura ou diâmetro (mm). O que está encostado continua encostado."),
        )
        if (p.forma === "ret") {
          painel.append(
            campo("h", p.h, (v) => {
              dimensionarParte(e.partes, [...e.sel][0], "h", v)
            }, "Altura (mm). O que está encostado continua encostado."),
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
  function cotaH(x0, x1, y, rotulo, editar) {
    const [a, b] = [px(x0, y), px(x1, y)]
    const yy = a[1]
    return `<line class="cota" x1="${a[0]}" y1="${yy}" x2="${b[0]}" y2="${yy}"/>
      <line class="cota" x1="${a[0]}" y1="${yy - 5}" x2="${a[0]}" y2="${yy + 5}"/>
      <line class="cota" x1="${b[0]}" y1="${yy - 5}" x2="${b[0]}" y2="${yy + 5}"/>
      <text class="cota-txt editavel" data-editar="${editar}" x="${(a[0] + b[0]) / 2}" y="${yy + 16}" text-anchor="middle">${rotulo}</text>`
  }
  function cotaV(x, y0, y1, rotulo, editar) {
    const [a, b] = [px(x, y0), px(x, y1)]
    const xx = a[0]
    const my = (a[1] + b[1]) / 2
    return `<line class="cota" x1="${xx}" y1="${a[1]}" x2="${xx}" y2="${b[1]}"/>
      <line class="cota" x1="${xx - 5}" y1="${a[1]}" x2="${xx + 5}" y2="${a[1]}"/>
      <line class="cota" x1="${xx - 5}" y1="${b[1]}" x2="${xx + 5}" y2="${b[1]}"/>
      <text class="cota-txt editavel" data-editar="${editar}" x="${xx - 8}" y="${my + 4}" text-anchor="end">${rotulo}</text>`
  }
  // ---- cotas de um ponto a outro e medidas do polígono
  function desenhoDaCota(A, B, modo, folga, rotulo, editar = "") {
    const [P, Q] = linhaDaCota(A, B, modo, folga).map(([x, y]) => px(x, y))
    const [a, b] = [px(...A), px(...B)]
    const tamanho = Math.hypot(Q[0] - P[0], Q[1] - P[1]) || 1
    const [ux, uy] = [(Q[0] - P[0]) / tamanho, (Q[1] - P[1]) / tamanho]
    const traco = ([x, y]) =>
      `<line class="cota-ponto" x1="${x - (ux + uy) * 5}" y1="${y - (uy - ux) * 5}" x2="${x + (ux + uy) * 5}" y2="${y + (uy - ux) * 5}"/>`
    const [mx, my] = [(P[0] + Q[0]) / 2, (P[1] + Q[1]) / 2]
    const atributos = editar ? `class="cota-txt editavel" data-editar="${editar}"` : 'class="cota-txt"'
    const legenda =
      Math.abs(ux) < 0.01
        ? `<text ${atributos} x="${mx - 7}" y="${my + 4}" text-anchor="end">${rotulo}</text>`
        : `<text ${atributos} x="${mx}" y="${my - 6}" text-anchor="middle">${rotulo}</text>`
    return `<line class="cota" x1="${a[0]}" y1="${a[1]}" x2="${P[0]}" y2="${P[1]}"/>
      <line class="cota" x1="${b[0]}" y1="${b[1]}" x2="${Q[0]}" y2="${Q[1]}"/>
      <line class="cota-ponto" x1="${P[0]}" y1="${P[1]}" x2="${Q[0]}" y2="${Q[1]}"/>
      ${traco(P)}${traco(Q)}${legenda}`
  }
  function cotasDoUsuario() {
    return e.cotas
      .map((c, n) => {
        const A = pontoDaAncora(e.partes, c.a)
        const B = pontoDaAncora(e.partes, c.b)
        if (!A || !B) return ""
        return desenhoDaCota(A, B, c.modo, c.folga, texto(medidaEntre(A, B, c.modo)), `cota:${n}`)
      })
      .join("")
  }
  function ladosDoPoligono() {
    if (e.ferramenta !== "mover" || e.sel.size !== 1) return ""
    const p = selecionadas()[0]
    if (p?.forma !== "poli") return ""
    const sinal = areaComSinal(p.pontos) >= 0 ? 1 : -1
    const afasta = 15 / e.vista.esc
    return p.pontos
      .map((a, k) => {
        const b = p.pontos[(k + 1) % p.pontos.length]
        const [dx, dy] = [b[0] - a[0], b[1] - a[1]]
        const L = Math.hypot(dx, dy)
        // Lado curto não recebe rótulo: a medida taparia a peça. Ele se edita pelo ponto.
        if (L * e.vista.esc < 34) return ""
        const [nx, ny] = [(sinal * dy) / L, (-sinal * dx) / L]
        const [x, y] = px((a[0] + b[0]) / 2 + nx * afasta, (a[1] + b[1]) / 2 + ny * afasta)
        return `<text class="cota-txt editavel" data-editar="lado:${k}" x="${x}" y="${y + 4}" text-anchor="middle">${texto(L)}</text>`
      })
      .join("")
  }
  function desenhoDoEncaixe() {
    if (!e.encaixe) return ""
    const [x, y] = px(e.encaixe.x, e.encaixe.y)
    if (e.encaixe.t === "m") {
      return `<polygon class="encaixe" points="${x},${y - 7} ${x + 7},${y + 5} ${x - 7},${y + 5}"/>`
    }
    if (e.encaixe.t === "c") return `<circle class="encaixe" cx="${x}" cy="${y}" r="7"/>`
    return `<rect class="encaixe" x="${x - 6}" y="${y - 6}" width="12" height="12"/>`
  }
  function desenhoDaNovaCota() {
    const nova = e.novaCota
    if (!nova) return ""
    const A = pontoDaAncora(e.partes, nova.a)
    if (!A) return ""
    const [ax, ay] = px(...A)
    let s = `<circle class="ponta-fixa" cx="${ax}" cy="${ay}" r="5"/>`
    if (!nova.b) {
      if (e.mouse) {
        const [mx, my] = px(...e.mouse)
        s += `<line class="guia" x1="${ax}" y1="${ay}" x2="${mx}" y2="${my}"/>`
      }
      return s
    }
    const B = pontoDaAncora(e.partes, nova.b)
    if (!B) return s
    const M = e.mouse ?? B
    const modo = modoDaCota(A, B, M)
    const [bx, by] = px(...B)
    s += `<circle class="ponta-movel" cx="${bx}" cy="${by}" r="5"/>`
    return s + desenhoDaCota(A, B, modo, folgaDaCota(A, B, modo, M), texto(medidaEntre(A, B, modo)))
  }
  function desenhoDoRealce() {
    if (!e.realce) return ""
    const [[ax, ay], [bx, by]] = [px(...e.realce.fica), px(...e.realce.anda)]
    return `<circle class="ponta-fixa" cx="${ax}" cy="${ay}" r="6"/><circle class="ponta-movel" cx="${bx}" cy="${by}" r="6"/>`
  }
  function medidaDoTrecho() {
    const ultimo = e.polilinha?.at(-1)
    if (!ultimo || !e.ponteiro) return ""
    const L = medidaEntre(ultimo, e.ponteiro, "a")
    if (!L) return ""
    const [x, y] = px(...e.ponteiro)
    return `<text class="medida-viva" x="${x + 14}" y="${y - 12}">${texto(L)} mm · ${texto(anguloEntre(ultimo, e.ponteiro))}°</text>`
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
      s += cotaH(c[0], c[2], c[1] - 26 / esc, `${texto(c[2] - c[0])} mm`, "total:b")
      s += cotaV(c[0] - 26 / esc, c[1], c[3], `${texto(c[3] - c[1])} mm`, "total:h")
      if (e.sel.size === 1) {
        const p = selecionadas()[0]
        if (p?.forma === "ret" && !p.giro) {
          const k = caixa(p)
          s += cotaH(k[0], k[2], k[3] + 26 / esc, `b ${texto(p.b)}`, "parte:b")
          s += cotaV(k[2] + 8 / esc + 34 / esc, k[1], k[3], `h ${texto(p.h)}`, "parte:h")
        } else if (p?.forma === "circ") {
          const k = caixa(p)
          s += cotaH(k[0], k[2], k[3] + 26 / esc, `Ø ${texto(p.b)}`, "parte:b")
        }
      }
    }

    s += cotasDoUsuario()
    s += ladosDoPoligono()

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
      s += medidaDoTrecho()
    }
    if (e.guias.x !== null) {
      const [x] = px(e.guias.x, 0)
      s += `<line class="guia" x1="${x}" y1="0" x2="${x}" y2="${h}"/>`
    }
    if (e.guias.y !== null) {
      const [, y] = px(0, e.guias.y)
      s += `<line class="guia" x1="0" y1="${y}" x2="${w}" y2="${y}"/>`
    }
    const escolhida = verticeAtual()
    for (const a of alcas()) {
      if (a.tipo === "meio") {
        s += `<circle class="alca-meio" cx="${a.px[0]}" cy="${a.px[1]}" r="4"/>`
      } else {
        const classe = a.tipo === "vertice" && a.k === escolhida ? "alca escolhida" : "alca"
        s += `<circle class="${classe}" cx="${a.px[0]}" cy="${a.px[1]}" r="${ALCA_PX}"/>`
      }
    }
    s += desenhoDoRealce()
    s += desenhoDaNovaCota()
    s += desenhoDoEncaixe()
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
      // Os pontos vêm antes: num lado curto, o meio cai perto deles e não pode roubar o clique.
      const meios = p.pontos.map((v, k) => {
        const u = p.pontos[(k + 1) % p.pontos.length]
        return { tipo: "meio", k, px: px((v[0] + u[0]) / 2, (v[1] + u[1]) / 2) }
      })
      return [...p.pontos.map((v, k) => ({ tipo: "vertice", k, px: px(v[0], v[1]) })), ...meios]
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
    if (lista?.length >= 3) {
      const erro = problemaDoPoligono(lista)
      if (erro) {
        // Continua desenhando: Backspace volta um ponto, e o trabalho não se perde.
        infoDica.textContent = `${erro} Backspace volta um ponto.`
        return
      }
    }
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
    // Primeira peça: os lados só mostram a medida se a peça tiver tamanho na tela.
    if (e.partes.length === 1) ajustarVista()
    enviar()
  }

  function pontoDoPoligono(x, y, shift) {
    const alvo = ponto(x, y)
    const ultimo = e.polilinha?.at(-1)
    if (!ultimo || e.encaixe || shift === e.orto) return alvo
    e.guias = { x: null, y: null }
    return travarAngulo(ultimo, alvo)
  }
  function acrescentarPonto(novo) {
    e.polilinha = [...(e.polilinha || []), novo]
    e.ponteiro = null
    desenhar()
    mostrarDica()
  }
  function mostrarDica() {
    infoDica.textContent = DICAS[e.ferramenta] ?? ""
  }
  function dentroDaVista() {
    const { w, h } = tela()
    // A folga é o lugar das medidas, que ficam do lado de fora da peça.
    return e.partes.flatMap((p) => cantos(p)).every(([x, y]) => {
      const [a, b] = px(x, y)
      return a >= 40 && a <= w - 40 && b >= 40 && b <= h - 40
    })
  }

  // ---- medidas editadas no próprio desenho
  const editor = criarEditorVivo(raiz.querySelector(".area"), {
    aoFechar() {
      if (!e.realce) return
      e.realce = null
      desenhar()
    },
    depoisDoTeclado() {
      svg.focus({ preventScroll: true })
    },
  })
  const noDesenho = (chave) => svg.querySelector(`[data-editar="${chave}"]`)

  // Muda numa cópia: se o polígono não servir, o desenho fica como estava.
  function aplicarCota(cota, valor) {
    const copia = copiar(e.partes)
    const erro = ajustarCota(copia, cota, valor)
    if (erro) return erro
    guardar()
    e.partes = copia
    if (!dentroDaVista()) ajustarVista()
    enviar()
    return ""
  }
  function realcar(cota) {
    e.realce = { fica: pontoDaAncora(e.partes, cota.a), anda: pontoDaAncora(e.partes, cota.b) }
    desenhar()
  }
  function abrirLado(k) {
    const i = [...e.sel][0]
    const cota = cotaDoLado(e.partes, i, k, e.pontaTrocada)
    const [A, B] = [pontoDaAncora(e.partes, cota.a), pontoDaAncora(e.partes, cota.b)]
    realcar(cota)
    const digitado = editor.aberto() ? editor.texto() : undefined
    editor.abrir(noDesenho(`lado:${k}`), {
      valor: medidaEntre(A, B, "a"),
      texto: digitado,
      unidade: "mm",
      passo: e.grade,
      nome: `Lado do polígono. O ponto azul fica e o laranja anda, levando o que está além dele.`,
      acoes: [
        {
          rotulo: "Mover a outra ponta",
          titulo: "Troca o ponto que fica pelo que anda",
          ao() {
            e.pontaTrocada = !e.pontaTrocada
            abrirLado(k)
          },
        },
        {
          rotulo: `Ângulo ${texto(anguloEntre(A, B))}°`,
          titulo: "Gira o lado em volta do ponto que fica",
          ao: () => abrirAngulo(k),
        },
      ],
      aplicar: (v) => aplicarCota(cota, v),
    })
  }
  function abrirAngulo(k) {
    const cota = cotaDoLado(e.partes, [...e.sel][0], k, e.pontaTrocada)
    realcar(cota)
    editor.abrir(noDesenho(`lado:${k}`), {
      valor: anguloEntre(pontoDaAncora(e.partes, cota.a), pontoDaAncora(e.partes, cota.b)),
      unidade: "°",
      passo: 5,
      nome: "Ângulo do lado: 0° para a direita, 90° para cima.",
      dica: "Gira o lado em volta do ponto azul.",
      aplicar(v) {
        const copia = copiar(e.partes)
        const erro = girarLado(copia, cota, v)
        if (erro) return erro
        guardar()
        e.partes = copia
        enviar()
        return ""
      },
    })
  }
  function abrirCota(n) {
    const cota = e.cotas[n]
    if (!cota) return
    const [A, B] = [pontoDaAncora(e.partes, cota.a), pontoDaAncora(e.partes, cota.b)]
    realcar(cota)
    const nomes = { h: "Distância horizontal", v: "Distância vertical", a: "Distância direta" }
    const digitado = editor.aberto() ? editor.texto() : undefined
    editor.abrir(noDesenho(`cota:${n}`), {
      valor: medidaEntre(A, B, cota.modo),
      texto: digitado,
      unidade: "mm",
      passo: e.grade,
      nome: `${nomes[cota.modo]}. O ponto azul fica e o laranja anda.`,
      acoes: [
        {
          rotulo: "Mover a outra ponta",
          titulo: "Troca o ponto que fica pelo que anda",
          ao() {
            e.cotas[n] = { ...cota, a: cota.b, b: cota.a }
            abrirCota(n)
          },
        },
        {
          rotulo: "Apagar cota",
          titulo: "Tira a cota. A peça fica como está.",
          ao() {
            editor.fechar()
            guardar()
            e.cotas.splice(n, 1)
            enviar()
          },
        },
      ],
      aplicar: (v) => aplicarCota(cota, v),
    })
  }
  function abrirProximoPonto(inicial) {
    const ultimo = e.polilinha.at(-1)
    const [a, b] = px(...ultimo)
    const alvo = {
      getBoundingClientRect() {
        const r = svg.getBoundingClientRect()
        const [x, y] = [r.left + a, r.top + b]
        return { left: x, right: x, top: y, bottom: y }
      },
    }
    editor.abrir(alvo, {
      valor: 0,
      texto: inicial,
      unidade: "mm",
      nome: "Próximo ponto",
      dica: "100 na direção do mouse · 100<45 · @50;20",
      ler: (s) => lerProximoPonto(s, ultimo, e.mouse ?? ultimo),
      aplicar(novo) {
        acrescentarPonto(novo)
        return ""
      },
    })
  }

  function abrirEdicao(chave) {
    const [tipo, eixo] = chave.split(":")
    if (tipo === "lado") {
      e.pontaTrocada = false
      abrirLado(Number(eixo))
      return
    }
    if (tipo === "cota") {
      abrirCota(Number(eixo))
      return
    }
    const el = noDesenho(chave)
    if (tipo === "parte") {
      const i = [...e.sel][0]
      const p = e.partes[i]
      const circulo = p.forma === "circ"
      // A espessura é o lado menor: ninguém compra chapa pela largura.
      const espessura = p.forma === "ret" && p[eixo] <= Math.min(p.b, p.h)
      editor.abrir(el, {
        valor: p[eixo],
        unidade: "mm",
        passo: e.grade,
        comerciais: espessura ? e.chapas : [],
        serie: "Chapas de aço",
        nome: circulo ? "Diâmetro" : eixo === "b" ? "Largura da chapa" : "Altura da chapa",
        aplicar(v) {
          if (v <= 0) return "A medida precisa ser maior que zero."
          guardar()
          dimensionarParte(e.partes, i, eixo, v)
          ajustarVista()
          enviar()
          return ""
        },
      })
      return
    }
    const c = caixaDe(e.partes.filter((p) => !p.furo))
    editor.abrir(el, {
      valor: eixo === "b" ? c[2] - c[0] : c[3] - c[1],
      unidade: "mm",
      passo: e.grade,
      nome: eixo === "b" ? "Largura total da seção" : "Altura total da seção",
      aplicar(v) {
        if (v <= 0) return "A medida precisa ser maior que zero."
        guardar()
        esticarConjunto(e.partes, eixo, v)
        ajustarVista()
        enviar()
        return ""
      },
    })
  }

  svg.addEventListener("pointerdown", (ev) => {
    // Com a caixinha aberta, o clique só confirma: senão o valor e o clique virariam dois pontos.
    if (editor.aberto()) {
      if (!editor.confirmar()) editor.fechar()
      return
    }
    svg.focus({ preventScroll: true })
    svg.setPointerCapture(ev.pointerId)
    const [x, y] = mundo(ev)
    const medida = ev.target.closest?.("[data-editar]")
    const cotaLivre = e.ferramenta === "cota" && !e.novaCota && medida?.dataset.editar.startsWith("cota:")
    if (medida && ev.button === 0 && (e.ferramenta === "mover" || cotaLivre)) {
      e.gesto = { tipo: "texto", chave: medida.dataset.editar }
      return
    }
    if (ev.button === 1) {
      e.gesto = { tipo: "pan", inicio: [ev.clientX, ev.clientY], vista: { ...e.vista } }
      return
    }
    if (e.ferramenta === "cota") {
      const nova = e.novaCota
      if (nova?.b) {
        const A = pontoDaAncora(e.partes, nova.a)
        const B = pontoDaAncora(e.partes, nova.b)
        const modo = modoDaCota(A, B, [x, y])
        guardar()
        e.cotas.push({ a: nova.a, b: nova.b, modo, folga: folgaDaCota(A, B, modo, [x, y]) })
        e.novaCota = null
        e.encaixe = null
        e.gesto = { tipo: "texto", chave: `cota:${e.cotas.length - 1}` }
        enviar()
        return
      }
      const achada = encaixeEm(x, y)
      if (!achada) {
        infoDica.textContent = "Chegue perto de um ponto da peça: ele fica marcado em verde."
        return
      }
      const { i, t, k } = achada
      if (!nova) e.novaCota = { a: { i, t, k }, b: null }
      else if (!mesmaAncora(nova.a, achada)) nova.b = { i, t, k }
      desenhar()
      return
    }
    if (e.ferramenta === "poli") {
      const [a, b] = pontoDoPoligono(x, y, ev.shiftKey)
      if (e.polilinha?.length > 2) {
        const [p0, q0] = px(...e.polilinha[0])
        const [p1, q1] = px(a, b)
        if (Math.hypot(p0 - p1, q0 - q1) < 12) {
          fecharPoligono()
          return
        }
      }
      acrescentarPonto([a, b])
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
    e.vertice = null
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
    e.mouse = [x, y]
    if (e.ferramenta === "cota") {
      e.encaixe = encaixeEm(x, y)
      desenhar()
      return
    }
    if (e.polilinha) {
      e.ponteiro = pontoDoPoligono(x, y, ev.shiftKey)
      desenhar()
      return
    }
    if (e.ferramenta === "poli") {
      e.encaixe = encaixeEm(x, y)
      infoDica.textContent = e.encaixe ? NOME_DO_ENCAIXE[e.encaixe.t] : DICAS.poli
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
      if (g.alca.tipo === "meio") {
        e.cotas = inserirVertice(e.partes, e.cotas, g.i, g.alca.k, [a, b])
        g.alca = { tipo: "vertice", k: g.alca.k + 1 }
        e.vertice = g.alca.k
      } else if (g.alca.tipo === "raio") {
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
    if (e.ferramenta === "mover") e.encaixe = null
    mostrarDica()
    if (!g) {
      desenhar()
      return
    }
    if (g.tipo === "texto") {
      abrirEdicao(g.chave) // aqui e não no pointerdown: o clique daria o foco de volta à prancheta
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
    if (g.tipo === "alca" && g.moveu) {
      const erro = e.partes[g.i].forma === "poli" ? problemaDoPoligono(e.partes[g.i].pontos) : ""
      if (erro) {
        const guardada = e.passado.pop()
        e.partes = guardada.partes
        e.cotas = guardada.cotas
        e.vertice = null
        infoDica.textContent = `${erro} O ponto voltou.`
      }
      // Um ponto solto fora da prancheta não teria mais como ser alcançado.
      if (!dentroDaVista()) ajustarVista()
      enviar()
      return
    }
    if (g.tipo === "mover" && g.moveu) {
      enviar()
      return
    }
    if (g.tipo === "alca" && g.alca.tipo === "meio") {
      const p = e.partes[g.i]
      const [a, b] = [p.pontos[g.alca.k], p.pontos[(g.alca.k + 1) % p.pontos.length]]
      guardar()
      e.cotas = inserirVertice(e.partes, e.cotas, g.i, g.alca.k, [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2])
      e.vertice = g.alca.k + 1
      enviar()
      return
    }
    if (g.tipo === "alca" && g.alca.tipo === "vertice") {
      e.vertice = g.alca.k
      montarPainel()
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
    else if (e.ferramenta === "poli" && e.polilinha?.length && /^[0-9@.,+-]$/.test(ev.key)) {
      abrirProximoPonto(ev.key)
    } else if (tecla === "backspace" && e.polilinha?.length) {
      e.polilinha = e.polilinha.slice(0, -1)
      if (!e.polilinha.length) e.polilinha = null
      desenhar()
    } else if (tecla === "delete" || tecla === "backspace") {
      if (verticeAtual() !== null) acoes.apagarPonto()
      else acoes.apagar()
    } else if (tecla === "escape" && e.novaCota) {
      e.novaCota = null
      desenhar()
    } else if (tecla === "escape") {
      e.polilinha = null
      e.vertice = null
      e.sel.clear()
      trocarFerramenta("mover")
      montarPainel()
    } else if (tecla === "enter" && e.polilinha) fecharPoligono()
    else if (seta && e.sel.size) {
      guardar()
      selecionadas().forEach((p) => mover(p, seta[0] * e.grade, seta[1] * e.grade))
      enviar()
    } else if (!ctrl && "vrcpd".includes(tecla)) {
      trocarFerramenta({ v: "mover", r: "ret", c: "circ", p: "poli", d: "cota" }[tecla])
    } else if (!ctrl && tecla === "f") {
      caixaFuro.checked = !caixaFuro.checked
    } else if (!ctrl && tecla === "o") {
      caixaOrto.checked = !caixaOrto.checked
      e.orto = caixaOrto.checked
    } else return
    ev.preventDefault()
  })

  function trocarFerramenta(nome) {
    e.ferramenta = nome
    e.polilinha = null
    e.ponteiro = null
    e.novaCota = null
    e.encaixe = null
    mostrarDica()
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
  caixaOrto.addEventListener("change", () => {
    e.orto = caixaOrto.checked
  })

  e.receber = (dados) => {
    const novas = dados.partes ?? []
    if (dados.versao >= e.versao) {
      if (JSON.stringify(novas) !== JSON.stringify(e.partes)) {
        if (e.versao >= 0) guardar()
        e.partes = copiar(novas)
        e.sel = new Set([...e.sel].filter((i) => i < e.partes.length))
      }
      // O dono das partes é o Python: tabela, modelo e arquivo trocam a seção por fora daqui.
      e.cotas = cotasValidas(e.partes, dados.cotas ?? [])
      e.versao = dados.versao
    }
    e.marcas = dados.marcas ?? null
    e.chapas = dados.chapas ?? []
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
