// Desenho do caso com as medidas vivas: clica na medida, digita e confirma, ali mesmo.
// O Python monta o desenho e guarda os valores. Aqui só existe a caixinha de digitação, que manda
// o número para lá. Enter confirma, Esc desiste e Tab vai para a medida seguinte.

const ESTADOS = new WeakMap()
const SVG_NS = "http://www.w3.org/2000/svg"
const FOLGA = 1.6

const texto = (v) => String(Math.round(v * 1e6) / 1e6).replace(".", ",")
const ler = (s) => Number(String(s).trim().replace(",", "."))

// Afasta as caixas que se encostam e devolve quem saiu do quadro para dentro. O número cresce
// conforme o que se digita, e nenhuma posição fixa no desenho daria conta. Texto que não é medida
// entra como `fixo`: as medidas desviam dele.
function desencontrar(caixas, q) {
  const folga = 1.2
  const lado = (c) => ({ x0: c.x + c.dx, y0: c.y + c.dy, x1: c.x + c.dx + c.w, y1: c.y + c.dy + c.h })
  const quanto = (a, b) => (a.fixo ? 0 : b.fixo ? 1 : 0.5)
  for (let passo = 0; passo < 80; passo += 1) {
    let mexeu = false
    for (let i = 0; i < caixas.length; i += 1) {
      for (let j = i + 1; j < caixas.length; j += 1) {
        const [a, b] = [caixas[i], caixas[j]]
        if (a.fixo && b.fixo) continue
        const [p, r] = [lado(a), lado(b)]
        const sx = Math.min(p.x1, r.x1) - Math.max(p.x0, r.x0) + folga
        const sy = Math.min(p.y1, r.y1) - Math.max(p.y0, r.y0) + folga
        if (sx <= 0 || sy <= 0) continue
        mexeu = true
        const eixo = sy <= sx ? "dy" : "dx"
        const dist = eixo === "dy" ? sy : sx
        const centro = eixo === "dy" ? p.y0 + p.y1 - r.y0 - r.y1 : p.x0 + p.x1 - r.x0 - r.x1
        const sinal = centro <= 0 ? 1 : -1
        a[eixo] -= sinal * dist * quanto(a, b)
        b[eixo] += sinal * dist * quanto(b, a)
      }
    }
    for (const c of caixas) {
      if (c.fixo) continue
      c.dx = Math.min(Math.max(c.dx, q.x - c.x), q.x + q.width - c.x - c.w)
      c.dy = Math.min(Math.max(c.dy, q.y - c.y), q.y + q.height - c.y - c.h)
    }
    if (!mexeu) break
  }
  return caixas
}

function criar(raiz) {
  const moldura = raiz.querySelector(".moldura")
  const desenho = raiz.querySelector(".desenho")
  const editor = raiz.querySelector(".editor")
  const entrada = raiz.querySelector("input")
  const unidade = raiz.querySelector(".un")
  const nome = raiz.querySelector(".nome")

  const e = { enviar: null, svg: null, cotas: [], aberta: null, proxima: null, n: 0 }

  function marcar() {
    desenho.querySelectorAll("tspan[data-cota]").forEach((t) => {
      const b = t.getBBox()
      const r = document.createElementNS(SVG_NS, "rect")
      r.setAttribute("class", "pilula")
      r.setAttribute("x", b.x - FOLGA)
      r.setAttribute("y", b.y - FOLGA / 2)
      r.setAttribute("width", b.width + 2 * FOLGA)
      r.setAttribute("height", b.height + FOLGA)
      r.setAttribute("rx", 2.5)
      r.setAttribute("tabindex", "0")
      r.setAttribute("role", "button")
      r.dataset.cota = t.dataset.cota
      const c = e.cotas[Number(t.dataset.cota)]
      const dica = document.createElementNS(SVG_NS, "title")
      dica.textContent = `${c.nome}: clique para mudar`
      r.append(dica)
      r.setAttribute("aria-label", `${c.nome}: ${t.textContent}`)
      t.parentNode.parentNode.insertBefore(r, t.parentNode)
    })
    const svg = desenho.querySelector("svg")
    if (!svg) return
    const textos = [...svg.querySelectorAll("text")]
    const caixas = textos.map((t) => {
      const b = t.getBBox()
      return {
        t,
        x: b.x - FOLGA,
        y: b.y - FOLGA / 2,
        w: b.width + 2 * FOLGA,
        h: b.height + FOLGA,
        dx: 0,
        dy: 0,
        fixo: !t.classList.contains("cota"),
      }
    })
    desencontrar(caixas, svg.viewBox.baseVal)
    for (const c of caixas) {
      if (c.fixo || (!c.dx && !c.dy)) continue
      const mover = `translate(${c.dx} ${c.dy})`
      c.t.setAttribute("transform", mover)
      c.t.querySelectorAll("tspan[data-cota]").forEach((s) => {
        pilula(s.dataset.cota)?.setAttribute("transform", mover)
      })
    }
  }

  function pilula(indice) {
    return desenho.querySelector(`rect[data-cota="${indice}"]`)
  }

  function abrir(indice) {
    const alvo = pilula(indice)
    const c = e.cotas[indice]
    if (!alvo || !c) return
    desenho.querySelector(".aberta")?.classList.remove("aberta")
    alvo.classList.add("aberta")
    e.aberta = indice
    entrada.value = texto(c.valor)
    unidade.textContent = c.unidade
    nome.textContent = c.nome
    nome.classList.remove("ruim")
    editor.hidden = false
    const m = moldura.getBoundingClientRect()
    const r = alvo.getBoundingClientRect()
    const largura = editor.offsetWidth
    const altura = editor.offsetHeight
    const x = Math.min(Math.max(r.left - m.left - 6, 4), m.width - largura - 4)
    const abaixo = r.bottom - m.top + 4
    const y = abaixo + altura > m.height ? r.top - m.top - altura - 4 : abaixo
    editor.style.left = `${x}px`
    editor.style.top = `${Math.max(y, 4)}px`
    entrada.focus()
    entrada.select()
  }

  function fechar() {
    desenho.querySelector(".aberta")?.classList.remove("aberta")
    editor.hidden = true
    e.aberta = null
  }

  function motivo(c, v) {
    if (!Number.isFinite(v) || entrada.value.trim() === "") return "Digite um número."
    if (c.minimo !== null && v < c.minimo) return `O mínimo é ${texto(c.minimo)} ${c.unidade}`
    if (c.maximo !== null && v > c.maximo) return `O máximo é ${texto(c.maximo)} ${c.unidade}`
    if (c.inteiro && !Number.isInteger(v)) return "Aqui vale só número inteiro."
    return ""
  }

  // Devolve falso se o valor não serve: a caixinha fica aberta, com o motivo.
  function confirmar(seguinte) {
    const indice = e.aberta
    if (indice === null) return true
    const c = e.cotas[indice]
    const v = ler(entrada.value)
    const erro = motivo(c, v)
    if (erro) {
      nome.textContent = erro
      nome.classList.add("ruim")
      return false
    }
    fechar()
    if (v === c.valor) {
      if (seguinte !== null) abrir(seguinte)
      return true
    }
    e.proxima = seguinte
    e.n += 1
    e.enviar?.("edicao", { indice, valor: v, n: e.n })
    return true
  }

  const depois = (indice, passo) => {
    const lista = [...desenho.querySelectorAll("rect[data-cota]")].map((r) => Number(r.dataset.cota))
    const k = lista.indexOf(indice)
    return lista[(k + passo + lista.length) % lista.length]
  }

  desenho.addEventListener("click", (ev) => {
    const alvo = ev.target.closest?.("rect[data-cota]")
    if (alvo) {
      if (confirmar(null)) abrir(Number(alvo.dataset.cota))
    } else if (e.aberta !== null) {
      confirmar(null)
    }
  })
  desenho.addEventListener("keydown", (ev) => {
    const alvo = ev.target.closest?.("rect[data-cota]")
    if (alvo && (ev.key === "Enter" || ev.key === " ")) {
      ev.preventDefault()
      abrir(Number(alvo.dataset.cota))
    }
  })
  entrada.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") {
      ev.preventDefault()
      confirmar(null)
    } else if (ev.key === "Escape") {
      ev.preventDefault()
      fechar()
    } else if (ev.key === "Tab") {
      ev.preventDefault()
      confirmar(depois(e.aberta, ev.shiftKey ? -1 : 1))
    }
  })
  entrada.addEventListener("blur", () => {
    // O clique em outra medida já confirma: aqui fica só o clique fora do desenho.
    setTimeout(() => {
      if (e.aberta !== null && !raiz.contains(raiz.getRootNode().activeElement)) confirmar(null)
    }, 120)
  })

  e.receber = (dados) => {
    e.cotas = dados.cotas ?? []
    if (dados.svg !== e.svg) {
      fechar()
      e.svg = dados.svg
      desenho.innerHTML = dados.svg ?? ""
      marcar()
    }
    if (e.proxima !== null) {
      const indice = e.proxima
      e.proxima = null
      abrir(indice)
    }
  }
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
