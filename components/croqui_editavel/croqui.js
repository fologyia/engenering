// Desenho do caso com as medidas vivas: clica na medida, digita e confirma, ali mesmo.
// O Python monta o desenho e guarda os valores. A caixinha é a de editor_numerico.js, e o número
// digitado vai para lá. Enter confirma, Esc desiste e Tab vai para a medida seguinte.
// Achar o limite é conta do Python: o pedido vai, e a resposta volta para a caixinha aberta.

const ESTADOS = new WeakMap()
const SVG_NS = "http://www.w3.org/2000/svg"
const FOLGA = 1.6


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

// O estudo fica depois das duas colunas, e pode estar longe da tela. Espera o painel abrir aqui, e não
// na volta do Python: os dados do desenho não mudam com este clique, e o componente nem seria chamado.
function rolarAteOEstudo(tentativas = 30) {
  const alvo = document.querySelector(".st-key-assistente_estudo_aberto")
  if (!alvo?.querySelector("details[open]")) {
    if (tentativas > 0) setTimeout(() => rolarAteOEstudo(tentativas - 1), 100)
    return
  }
  const pagina = alvo.closest('[data-testid="stMain"]')
  // A folga é o cabeçalho fixo da página, que cobriria o título do painel.
  pagina?.scrollTo({ top: pagina.scrollTop + alvo.getBoundingClientRect().top - 70, behavior: "smooth" })
}

function criar(raiz) {
  const moldura = raiz.querySelector(".moldura")
  const desenho = raiz.querySelector(".desenho")

  const e = {
    enviar: null,
    svg: null,
    cotas: [],
    aberta: null,
    proxima: null,
    n: 0,
    estudavel: false,
    estudo: null,
    manda: null,
  }
  const editor = criarEditorVivo(moldura, {
    saiDaArea: true,
    aoFechar() {
      desenho.querySelector(".aberta")?.classList.remove("aberta")
      e.aberta = null
    },
    aoTab(voltar) {
      editor.confirmar(depois(e.aberta, voltar ? -1 : 1))
    },
  })

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

  function destacar() {
    desenho.querySelector("rect.manda")?.classList.remove("manda")
    if (e.manda !== null) pilula(e.manda)?.classList.add("manda")
  }

  function pedir(acao, indice) {
    e.n += 1
    e.enviar?.("edicao", { acao, indice, n: e.n })
  }

  function acoesDe(indice) {
    if (!e.estudavel) return []
    return [
      {
        rotulo: "Achar o limite",
        titulo: "Procura o menor e o maior valor que passam",
        ao(botao) {
          // A resposta destes mesmos números já está à vista: um novo pedido não mudaria nada.
          if (e.estudo?.indice === indice) return
          botao.disabled = true
          pedir("limite", indice)
        },
      },
      {
        rotulo: "Ver gráfico",
        titulo: "Abre o estudo desta medida, com o gráfico, logo abaixo da página",
        ao() {
          editor.fechar()
          pedir("grafico", indice)
          rolarAteOEstudo()
        },
      },
    ]
  }

  function motivo(c, v) {
    if (c.minimo !== null && v < c.minimo) return `O mínimo é ${enTexto(c.minimo)} ${c.unidade}`
    if (c.maximo !== null && v > c.maximo) return `O máximo é ${enTexto(c.maximo)} ${c.unidade}`
    if (c.inteiro && !Number.isInteger(v)) return "Aqui vale só número inteiro."
    return ""
  }

  function abrir(indice) {
    const alvo = pilula(indice)
    const c = e.cotas[indice]
    if (!alvo || !c) return
    desenho.querySelector(".aberta")?.classList.remove("aberta")
    alvo.classList.add("aberta")
    e.aberta = indice
    editor.abrir(alvo, {
      valor: c.valor,
      unidade: c.unidade,
      nome: c.nome,
      passo: c.passo,
      comerciais: c.comerciais,
      serie: c.serie,
      acoes: acoesDe(indice),
      resposta: e.estudo?.indice === indice ? e.estudo : null,
      semMudanca(seguinte) {
        if (seguinte !== null) abrir(seguinte)
      },
      aplicar(v, seguinte) {
        const erro = motivo(c, v)
        if (erro) return erro
        e.proxima = seguinte
        e.n += 1
        e.enviar?.("edicao", { indice, valor: v, n: e.n })
        return ""
      },
    })
  }

  const depois = (indice, passo) => {
    const lista = [...desenho.querySelectorAll("rect[data-cota]")].map((r) => Number(r.dataset.cota))
    const k = lista.indexOf(indice)
    return lista[(k + passo + lista.length) % lista.length]
  }

  desenho.addEventListener("click", (ev) => {
    const alvo = ev.target.closest?.("rect[data-cota]")
    if (alvo) {
      if (editor.confirmar()) abrir(Number(alvo.dataset.cota))
    } else if (editor.aberto()) {
      editor.confirmar()
    }
  })
  desenho.addEventListener("keydown", (ev) => {
    const alvo = ev.target.closest?.("rect[data-cota]")
    if (alvo && (ev.key === "Enter" || ev.key === " ")) {
      ev.preventDefault()
      abrir(Number(alvo.dataset.cota))
    }
  })

  e.receber = (dados) => {
    e.cotas = dados.cotas ?? []
    e.estudavel = Boolean(dados.estudavel)
    e.manda = dados.manda ?? null
    e.estudo = dados.estudo ?? null
    if (dados.svg !== e.svg) {
      editor.fechar()
      e.svg = dados.svg
      desenho.innerHTML = dados.svg ?? ""
      marcar()
    }
    destacar()
    if (e.estudo && e.estudo.indice === e.aberta) editor.mostrarResposta(e.estudo)
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
