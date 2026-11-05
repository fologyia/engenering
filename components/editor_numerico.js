// A caixinha de digitar medida, igual nas três pranchetas. O Python junta este arquivo na frente do
// JS de cada uma. Além do número, ela aceita conta (300/2), unidade (1,5 m), valor relativo (+10,
// *1,2) e as setas do teclado. O que se lê aqui é conta pura: tests/test_editor_numerico_js.py roda
// tudo no Node, sem navegador.

const EN_FAMILIAS = [
  { mm: 1, cm: 10, dm: 100, m: 1000, pol: 25.4, in: 25.4, '"': 25.4, pe: 304.8, ft: 304.8 },
  { n: 1, kn: 1000, mn: 1e6, kgf: 9.80665, tf: 9806.65, lbf: 4.4482216 },
  {
    "n·m": 1,
    nm: 1,
    "n.m": 1,
    "kn·m": 1000,
    knm: 1000,
    "kn.m": 1000,
    "n·mm": 0.001,
    nmm: 0.001,
    "n.mm": 0.001,
    "kgf·m": 9.80665,
    kgfm: 9.80665,
  },
  { mpa: 1, kpa: 0.001, pa: 1e-6, gpa: 1000, bar: 0.1, psi: 0.00689476 },
  { "mm²": 1, mm2: 1, "cm²": 100, cm2: 100, "m²": 1e6, m2: 1e6 },
  { w: 0.001, kw: 1, cv: 0.73549875, hp: 0.7457 },
  { g: 0.001, kg: 1, t: 1000 },
]

const enTexto = (v) => String(Math.round(v * 1e6) / 1e6).replace(".", ",")

function enFator(digitada, doCampo) {
  const [a, b] = [digitada.toLowerCase(), doCampo.toLowerCase()]
  if (a === b) return 1
  for (const familia of EN_FAMILIAS) {
    if (a in familia && b in familia) return familia[a] / familia[b]
  }
  return null
}

// Soma, produto e parênteses, sem eval: o texto vem do usuário.
function enCalcular(s) {
  let i = 0
  const pular = () => {
    while (s[i] === " ") i += 1
  }
  const fator = () => {
    pular()
    if (s[i] === "-") {
      i += 1
      return -fator()
    }
    if (s[i] === "+") {
      i += 1
      return fator()
    }
    if (s[i] === "(") {
      i += 1
      const v = soma()
      pular()
      if (s[i] !== ")") throw new Error("parêntese")
      i += 1
      return v
    }
    const achado = /^(\d+\.?\d*|\.\d+)/.exec(s.slice(i))
    if (!achado) throw new Error("número")
    i += achado[0].length
    return Number(achado[0])
  }
  const termo = () => {
    let v = fator()
    for (;;) {
      pular()
      if (s[i] === "*") {
        i += 1
        v *= fator()
      } else if (s[i] === "/") {
        i += 1
        const d = fator()
        if (d === 0) throw new Error("divisão")
        v /= d
      } else {
        return v
      }
    }
  }
  function soma() {
    let v = termo()
    for (;;) {
      pular()
      if (s[i] === "+") {
        i += 1
        v += termo()
      } else if (s[i] === "-") {
        i += 1
        v -= termo()
      } else {
        return v
      }
    }
  }
  const v = soma()
  pular()
  if (i !== s.length) throw new Error("sobrou texto")
  return v
}

// Devolve { valor } ou { erro }. `atual` é a base de +10, *2 e /2; `unidade` é a do campo.
function lerValorDigitado(texto, atual, unidade) {
  let s = String(texto ?? "").trim()
  if (!s) return { erro: "Digite um número." }
  s = s.includes(",") ? s.replace(/\./g, "").replace(/,/g, ".") : s
  s = s.replace(/[×xX](?=\s*[\d(.])/g, "*").replace(/÷/g, "/")
  let fator = 1
  const achada = /([a-zA-Zµ"²][a-zA-Zµ"²·.0-9]*)$/.exec(s)
  if (achada) {
    const digitada = achada[1]
    const f = unidade ? enFator(digitada, unidade) : null
    if (f === null) {
      return { erro: unidade ? `${digitada} não combina com ${unidade}.` : "Este campo não tem unidade." }
    }
    fator = f
    s = s.slice(0, achada.index).trim()
  }
  const relativo = s[0] === "+" || s[0] === "*" || s[0] === "/" ? s[0] : ""
  try {
    const v = enCalcular(relativo ? s.slice(1) : s)
    if (!Number.isFinite(v)) return { erro: "Digite um número." }
    let valor = v * fator
    if (relativo === "+") valor = atual + valor
    if (relativo === "*") valor = atual * v
    if (relativo === "/") {
      if (v === 0) return { erro: "Não dá para dividir por zero." }
      valor = atual / v
    }
    return { valor: Math.round(valor * 1e9) / 1e9 }
  } catch {
    return { erro: "Não entendi. Exemplos: 150, 300/2, 1,5 m, +10." }
  }
}

function passoDoValor(valor, passo) {
  if (passo) return passo
  return 10 ** (Math.floor(Math.log10(Math.abs(valor) || 1)) - 1)
}

// Os valores da série em volta do número: `n` abaixo, ele mesmo se existir e `n` acima.
function enVizinhos(serie, valor, n = 2) {
  const abaixo = serie.filter((v) => v < valor - 1e-9).slice(-n)
  const iguais = serie.filter((v) => Math.abs(v - valor) <= 1e-9)
  const acima = serie.filter((v) => v > valor + 1e-9).slice(0, n)
  return [...abaixo, ...iguais, ...acima]
}

// A caixinha. `d` descreve a medida: valor, unidade, nome, passo, aplicar(v, seguinte) e, se quiser,
// semMudanca(seguinte). aplicar devolve o motivo quando não aceita, e vazio quando aceita.
// Opcionais: `comerciais` e `serie` mostram os vizinhos que se compram; `acoes` são botões
// ({ rotulo, titulo, ao }); `resposta` ({ texto, opcoes }) é o que o Python achou para esta medida.
function criarEditorVivo(area, opcoes = {}) {
  const caixa = document.createElement("div")
  caixa.className = "editor"
  caixa.hidden = true
  caixa.innerHTML = `<div class="linha"><input type="text" aria-label="Novo valor"><span class="un"></span></div>
    <div class="nome"></div><div class="dica">Vale conta e unidade: 300/2, 1,5 m, +10</div>
    <div class="serie" hidden><div class="titulo"></div><div class="fichas"></div></div>
    <div class="acoes" hidden></div>
    <div class="resposta" hidden><div class="texto" role="status"></div><div class="fichas"></div></div>`
  area.append(caixa)
  const entrada = caixa.querySelector("input")
  const unidade = caixa.querySelector(".un")
  const nome = caixa.querySelector(".nome")
  const serie = caixa.querySelector(".serie")
  const fichasDaSerie = serie.querySelector(".fichas")
  const acoes = caixa.querySelector(".acoes")
  const resposta = caixa.querySelector(".resposta")
  let atual = null
  let alvoAtual = null

  function mostrarErro(texto) {
    nome.textContent = texto
    nome.classList.add("ruim")
  }
  function fechar() {
    caixa.hidden = true
    atual = null
    alvoAtual = null
    opcoes.aoFechar?.()
  }
  function ficha(valor, texto, titulo, marcada = false) {
    const b = document.createElement("button")
    b.type = "button"
    b.className = marcada ? "ficha igual" : "ficha"
    b.textContent = texto
    b.title = titulo
    b.addEventListener("click", () => {
      entrada.value = enTexto(valor)
      confirmar()
    })
    return b
  }
  // Acompanha o que se digita: quem escreve 7 numa chapa já vê o 6,3 e o 8.
  function desenharFichas() {
    const lista = atual?.comerciais ?? []
    serie.hidden = !lista.length
    if (!lista.length) return
    const lido = lerValorDigitado(entrada.value, atual.valor, atual.unidade)
    const base = lido.erro ? atual.valor : lido.valor
    serie.querySelector(".titulo").textContent = atual.serie
    fichasDaSerie.replaceChildren(
      ...enVizinhos(lista, base).map((v) =>
        ficha(v, enTexto(v), `Usar ${enTexto(v)} ${atual.unidade}`.trim(), Math.abs(v - base) <= 1e-9),
      ),
    )
  }
  function desenharAcoes(d) {
    const lista = d.acoes ?? []
    acoes.hidden = !lista.length
    acoes.replaceChildren(
      ...lista.map((a) => {
        const b = document.createElement("button")
        b.type = "button"
        b.className = "acao"
        b.textContent = a.rotulo
        b.title = a.titulo ?? ""
        b.addEventListener("click", () => a.ao(b))
        return b
      }),
    )
  }
  function mostrarResposta(r) {
    resposta.hidden = !r
    if (r) {
      resposta.querySelector(".texto").textContent = r.texto
      resposta.querySelector(".fichas").replaceChildren(
        ...(r.opcoes ?? []).map((o) => ficha(o.valor, o.texto, `${o.rotulo}: usar este valor`)),
      )
      acoes.querySelectorAll("button").forEach((b) => {
        b.disabled = false
      })
    }
    posicionar()
  }
  function posicionar() {
    if (!alvoAtual) return
    const m = area.getBoundingClientRect()
    const r = alvoAtual.getBoundingClientRect()
    const x = Math.min(Math.max(r.left - m.left - 8, 4), m.width - caixa.offsetWidth - 4)
    const abaixo = r.bottom - m.top + 5
    // No desenho de um caso a caixinha pode passar da moldura: subir cobriria a própria medida.
    const cabeAbaixo = opcoes.saiDaArea || abaixo + caixa.offsetHeight <= m.height
    const y = cabeAbaixo ? abaixo : r.top - m.top - caixa.offsetHeight - 5
    caixa.style.left = `${x}px`
    caixa.style.top = `${Math.max(y, 4)}px`
  }
  function abrir(alvo, d) {
    atual = d
    alvoAtual = alvo
    entrada.value = enTexto(d.valor)
    unidade.textContent = d.unidade
    nome.textContent = d.nome
    nome.classList.remove("ruim")
    desenharFichas()
    desenharAcoes(d)
    caixa.hidden = false
    mostrarResposta(d.resposta ?? null)
    entrada.focus()
    entrada.select()
  }
  // Devolve falso se o valor não serve: a caixinha fica aberta, com o motivo.
  function confirmar(seguinte = null) {
    const d = atual
    if (!d) return true
    const lido = lerValorDigitado(entrada.value, d.valor, d.unidade)
    if (lido.erro) {
      mostrarErro(lido.erro)
      return false
    }
    if (lido.valor === Math.round(d.valor * 1e9) / 1e9) {
      fechar()
      d.semMudanca?.(seguinte)
      return true
    }
    const erro = d.aplicar(lido.valor, seguinte)
    if (erro) {
      mostrarErro(erro)
      return false
    }
    fechar()
    return true
  }
  entrada.addEventListener("input", desenharFichas)
  // Sem isto, clicar numa ficha tira o foco do campo, e a saída do campo já confirmaria o texto.
  caixa.addEventListener("mousedown", (ev) => {
    if (ev.target.closest("button")) ev.preventDefault()
  })
  caixa.addEventListener("pointerdown", (ev) => ev.stopPropagation())
  entrada.addEventListener("keydown", (ev) => {
    ev.stopPropagation()
    if (ev.key === "Enter") {
      ev.preventDefault()
      confirmar()
    } else if (ev.key === "Escape") {
      ev.preventDefault()
      fechar()
    } else if (ev.key === "Tab" && opcoes.aoTab) {
      ev.preventDefault()
      opcoes.aoTab(ev.shiftKey)
    } else if ((ev.key === "ArrowUp" || ev.key === "ArrowDown") && atual) {
      const lido = lerValorDigitado(entrada.value, atual.valor, atual.unidade)
      if (lido.erro) return
      ev.preventDefault()
      const sinal = ev.key === "ArrowUp" ? 1 : -1
      const passo = passoDoValor(lido.valor, atual.passo) * (ev.shiftKey ? 10 : 1)
      entrada.value = enTexto(lido.valor + sinal * passo)
      desenharFichas()
    }
  })
  entrada.addEventListener("blur", () => {
    // Um instante depois: clicar em outra medida também tira o foco, e ela já confirma.
    setTimeout(() => {
      if (!atual || area.getRootNode().activeElement === entrada) return
      if (!confirmar()) fechar()
    }, 120)
  })
  return { abrir, fechar, confirmar, mostrarResposta, aberto: () => atual !== null }
}
