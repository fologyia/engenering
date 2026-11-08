// Prancheta de blocos do Montador. Aqui só nasce o desenho: blocos, fios e conjuntos. Ele vai para o
// Python a cada gesto terminado, e os avisos de cada bloco voltam em `marcas`. O catálogo também vem
// de lá, e por isso um bloco novo em core/montador_blocos.py aparece aqui sem mudar este arquivo.
// A tela é redesenhada inteira a cada mudança: o SVG não guarda estado, quem guarda é `e`.
// O histórico do Ctrl+Z mora no Python, junto com os valores: assim um Ctrl+Z só desfaz na ordem em
// que tudo foi feito, fio ou número. Os pedidos vão numerados e em fila (veja `comandar`).
// A caixinha de digitar número é a de editor_numerico.js, que o Python junta na frente deste arquivo.

const ESTADOS = new WeakMap()
const LARGURA = 176
const FAIXA = 24 // a faixa de cima, com a categoria do bloco
const PORTA_Y = 50
const PORTA_PASSO = 22
const FOLGA_X = 40
const FOLGA_Y = 30
const MARGEM_X = 46 // cabe o nome da bolinha ao lado do bloco da ponta
const TOQUE_PORTA = 13
const LETRAS_POR_LINHA = 26
const LETRAS_DO_DESTAQUE = 24
const LETRAS_DO_NOME = 21 // acima disso o nome aperta para caber na largura do cartão
const ESCALA_LEGIVEL = 0.85 // abaixo disso o texto dos blocos fica difícil de ler
const CONJUNTO = "conjunto"
const RESULTADO = "resultado"
const REFERENCIA = "referencia"
const FILA = ["secao", "linha"] // o fio que passa de bloco em bloco
const VALOR = "valor"
const CONDICAO = "condicao"
const MATERIAL = "material"
const DICA = "Clique num bloco da biblioteca para pôr na fila. Arraste de uma bolinha a outra para ligar."
const AJUDA = "Clique para pôr na fila. Selecione uma ligação para inserir no meio dela."
const AJUDA_FIO = "Ligação selecionada. Passe o cursor sobre uma opção para ver como fica."
const SEPARADOR = " · "
const DICA_DO_EDITOR = "Vale conta e unidade: 300/2, 1,5 m, +10. Vazio vira letra."
const ESPERA_DO_REENVIO = 1500 // sem resposta nesse tempo, o pedido vai de novo
const REENVIOS = 3
const ESPERA_MAXIMA = 4000 // depois disso a prancheta volta a aceitar gestos, com ou sem resposta

const copiar = (v) => JSON.parse(JSON.stringify(v))
const escapar = (t) =>
  String(t).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
const semAcento = (t) => String(t).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()

const cortar = (texto, limite) => (texto.length > limite ? `${texto.slice(0, limite - 1)}…` : texto)

function quebrar(texto, limite) {
  // Duas linhas no máximo: o bloco não cresce com o texto. Só quebra entre um item e outro.
  if (!texto) return []
  const meio = texto.includes(" · ") ? " · " : " "
  const linhas = [""]
  for (const pedaco of texto.split(meio)) {
    const atual = linhas[linhas.length - 1]
    const junto = atual ? `${atual}${meio}${pedaco}` : pedaco
    if (junto.length <= limite || !atual) linhas[linhas.length - 1] = junto
    else if (linhas.length < 2) linhas.push(pedaco)
    else {
      linhas[1] = `${linhas[1]} …`
      break
    }
  }
  return linhas.map((l) => cortar(l, limite))
}

function canonico(v) {
  if (Array.isArray(v)) return `[${v.map(canonico).join(",")}]`
  if (v && typeof v === "object") {
    return `{${Object.keys(v).sort().map((k) => `${JSON.stringify(k)}:${canonico(v[k])}`).join(",")}}`
  }
  return JSON.stringify(v ?? null)
}

// As mesmas duas linhas de `quebrar`, sem perder de quem é cada pedaço: o pedaço com chave é um
// número do bloco, e vira campo na prancheta. `mais` diz que sobrou pedaço fora do cartão.
function quebrarPedacos(pedacos, limite) {
  if (!pedacos?.length) return []
  const largura = (itens) => itens.reduce((n, p, i) => n + p.t.length + (i ? SEPARADOR.length : 0), 0)
  const linhas = [{ itens: [], mais: false }]
  for (const pedaco of pedacos) {
    const atual = linhas[linhas.length - 1]
    const junto = largura(atual.itens) + (atual.itens.length ? SEPARADOR.length : 0) + pedaco.t.length
    if (junto <= limite || !atual.itens.length) atual.itens.push({ ...pedaco })
    else if (linhas.length < 2) linhas.push({ itens: [{ ...pedaco }], mais: false })
    else {
      atual.mais = true
      break
    }
  }
  // Pedaço comprido é cortado no fim, como em `cortar`, e continua sendo o mesmo número.
  for (const linha of linhas) {
    let sobra = limite - (linha.mais ? 2 : 0)
    const cabem = []
    for (const [i, p] of linha.itens.entries()) {
      const espaco = sobra - (i ? SEPARADOR.length : 0)
      if (espaco < 2) {
        linha.mais = true
        break
      }
      if (p.t.length > espaco) p.t = `${p.t.slice(0, espaco - 1)}…`
      cabem.push(p)
      sobra = espaco - p.t.length
    }
    linha.itens = cabem
  }
  return linhas
}

// O número na caixinha sem perder casas: 0,0000001 não pode virar 0 só por abrir e fechar.
function textoParaEditar(v) {
  if (v === null || v === undefined || !Number.isFinite(v)) return ""
  if (v === 0) return "0"
  let s = String(Number(v.toPrecision(12)))
  if (/e/i.test(s)) {
    const casas = Math.min(20, Math.max(0, 11 - Math.floor(Math.log10(Math.abs(v)))))
    s = v.toFixed(casas).replace(/\.?0+$/, "")
  }
  return s.replace(".", ",")
}

function mesmoNumero(a, b) {
  if (a === null || a === undefined || b === null || b === undefined) return (a ?? null) === (b ?? null)
  return Math.abs(a - b) <= 1e-9 * Math.max(Math.abs(a), Math.abs(b))
}

// O que se digita no cartão. `campo` é o que o Python mandou da letra: v (na unidade da tela) e u.
// Vazio devolve a letra à fórmula, como no inspetor. A unidade do próprio campo pode vir junto.
function lerDoCartao(texto, campo) {
  let s = String(texto ?? "").trim()
  if (!s) return { valor: null }
  const unidade = campo.u ?? ""
  if (unidade && s.toLowerCase().endsWith(unidade.toLowerCase())) s = s.slice(0, s.length - unidade.length).trim()
  if (!s) return { erro: "Digite um número." }
  const semNumero = campo.v === null || campo.v === undefined
  if (semNumero && /^[+*/]/.test(s)) return { erro: "Esta letra ainda não tem número: digite o valor." }
  return lerValorDigitado(s, campo.v ?? 0, unidade)
}

function criar(raiz) {
  const svg = raiz.querySelector(".miolo > svg") // o botão de duplicar também tem um svg, o ícone
  const lista = raiz.querySelector("[data-lista]")
  const busca = raiz.querySelector("[data-busca]")
  const biblioteca = raiz.querySelector("[data-biblioteca]")
  const trilha = raiz.querySelector("[data-trilha]")
  const dica = raiz.querySelector("[data-dica]")
  const ajuda = raiz.querySelector("[data-ajuda]")
  const conta = raiz.querySelector("[data-conta]")
  const zoom = raiz.querySelector("[data-zoom]")
  const titulo = raiz.querySelector("[data-titulo]")
  const detalhe = raiz.querySelector("[data-detalhe]")
  const luz = raiz.querySelector("[data-luz]")
  const miolo = raiz.querySelector(".miolo")
  const botaoAgrupar = raiz.querySelector('[data-a="agrupar"]')
  const botaoDuplicar = raiz.querySelector('[data-a="duplicar"]')
  const botaoDesfazer = raiz.querySelector('[data-a="desfazer"]')
  const botaoRefazer = raiz.querySelector('[data-a="refazer"]')
  dica.textContent = DICA

  const e = {
    enviar: null,
    catalogo: {},
    ordem: [],
    assinatura: "",
    raiz: { nos: [], fios: [] },
    caminho: [],
    versao: -1,
    verAjuste: null,
    marcas: {},
    vista: { x: 0, y: 0, esc: 1 },
    sel: null,
    multi: new Set(),
    topo: null,
    gesto: null,
    pendente: null,
    realce: null,
    fantasma: null,
    fila: [], // pedidos ao Python ainda sem confirmação
    n: 0,
    versaoDoPython: -1,
    ultimoSoPosicao: false,
    colados: {}, // senha da colagem → cópia: original, até o Python dizer que viu
    copiado: null,
    historia: {},
    esperando: 0, // quando um Ctrl+Z saiu, e a conta ainda não voltou
    esperandoAcao: "",
    avisoVisto: null,
    avisoAntes: 0,
    mudando: new Map(), // letra digitada no cartão → número do pedido
    ultimoToque: null,
    editando: null,
    proxima: null,
    vigia: null,
    reenvios: 0,
    filtro: "",
    abertos: null,
    selecionarVisto: -1,
    ultimaSelecao: "null",
    ajustarAoMedir: false,
    quebrarAoMedir: false,
  }

  const nivel = () => {
    let atual = e.raiz
    for (const id of e.caminho) {
      const no = atual.nos.find((n) => n.id === id)
      if (!no?.grafo) return atual
      atual = no.grafo
    }
    return atual
  }
  const prefixo = () => (e.caminho.length ? `${e.caminho.join("/")}/` : "")
  const noPorId = (id) => nivel().nos.find((n) => n.id === id)
  const tipoDe = (no) => e.catalogo[no.tipo]
  function portas(no) {
    // Conjunto e fórmula própria têm as bolinhas no próprio bloco, e não no catálogo.
    if (no.portas || no.tipo === CONJUNTO) {
      return { entradas: no.portas?.entradas ?? [], saidas: no.portas?.saidas ?? [] }
    }
    const b = tipoDe(no)
    if (!b) return { entradas: [], saidas: [] }
    if (no.tipo === REFERENCIA) {
      const dimensao = no.opcoes?.dimensao ?? null
      return { entradas: b.entradas, saidas: b.saidas.map((p) => ({ ...p, dimensao })) }
    }
    return b
  }
  const nomeDe = (no) => (no.tipo === CONJUNTO ? no.nome : tipoDe(no)?.nome ?? no.tipo)
  const classeDe = (no) => (no.tipo === CONJUNTO ? "g-conjunto" : tipoDe(no)?.classe ?? "g-secao")
  const conhecido = (no) => no.tipo === CONJUNTO || Boolean(tipoDe(no))
  function erroDe(no) {
    const chave = prefixo() + no.id
    const erros = e.marcas.erros ?? {}
    if (erros[chave]) return erros[chave]
    const dentro = Object.keys(erros).find((k) => k.startsWith(`${chave}/`))
    return dentro ? erros[dentro] : ""
  }
  function conteudo(no) {
    const face = e.marcas.faces?.[prefixo() + no.id] ?? {}
    const forte = cortar(face.b ?? "", LETRAS_DO_DESTAQUE)
    // Sem número para mudar, o texto quebra como sempre quebrou: por palavra, se for uma frase só.
    if (face.p?.some(([, c]) => c)) {
      const pedacos = face.p.map(([t, c]) => ({ t: String(t), c: c || "" }))
      const copia = pedacos.some((p) => p.c && e.marcas.campos?.[p.c]?.copia)
      return { linhas: quebrarPedacos(pedacos, LETRAS_POR_LINHA), forte, copia }
    }
    const texto = face.a ?? (no.tipo === CONJUNTO ? "" : tipoDe(no)?.formula ?? "")
    const linhas = quebrar(texto, LETRAS_POR_LINHA).map((t) => ({ itens: [{ t, c: "" }], mais: false }))
    return { linhas, forte, copia: false }
  }
  const altura = (no) => {
    const p = portas(no)
    const { linhas, forte } = conteudo(no)
    const texto = 58 + linhas.length * 13 + (forte ? 15 : 0) + (no.tipo === CONJUNTO ? 22 : 0)
    const bolinhas = PORTA_Y + Math.max(p.entradas.length, p.saidas.length) * PORTA_PASSO
    return Math.max(86, texto, bolinhas) + (erroDe(no) ? 15 : 0)
  }
  const portaXY = (no, lado, i) => [
    no.x + (lado === "e" ? 0 : LARGURA),
    no.y + PORTA_Y + PORTA_PASSO * (i + 0.5),
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

  function pedidoDeEdicao(soPosicao, extra = {}) {
    const pedido = { grafo: copiar(e.raiz), versao: e.versao, so_posicao: soPosicao, ...extra }
    if (Object.keys(e.colados).length) pedido.colados = copiar(e.colados)
    return pedido
  }
  function enviar(soPosicao = false) {
    e.versao += 1
    e.ultimoSoPosicao = soPosicao
    e.enviar?.("edicao", pedidoDeEdicao(soPosicao))
    vigiar()
    avisarSelecao()
    desenhar()
    montarLista()
  }
  // Duas rodadas pedidas juntas viram uma só no Streamlit, e a de antes se perde. Cada pedido leva
  // por isso os de antes ainda sem confirmação, e o Python só faz o que tiver número novo.
  function comandar(item) {
    e.n += 1
    e.fila.push({ ...item, n: e.n })
    e.enviar?.("comando", { lista: copiar(e.fila) })
    vigiar()
    return e.n
  }
  // O que ficou sem resposta vai de novo: o gesto que se perdeu numa rodada juntada com outra.
  function vigiar() {
    clearTimeout(e.vigia)
    const atrasado = e.versao > e.versaoDoPython || e.fila.length || Object.keys(e.colados).length
    if (!atrasado) {
      e.reenvios = 0
      return
    }
    if (e.reenvios >= REENVIOS) return
    e.vigia = setTimeout(() => {
      e.reenvios += 1
      const atras = e.versao > e.versaoDoPython
      if (atras || Object.keys(e.colados).length) {
        // Só a colagem sem resposta: o desenho já é o do Python, e não troca a conta.
        e.enviar?.("edicao", pedidoDeEdicao(atras ? e.ultimoSoPosicao : true))
      }
      if (e.fila.length) e.enviar?.("comando", { lista: copiar(e.fila) })
      vigiar()
    }, ESPERA_DO_REENVIO)
  }
  // Enquanto o Ctrl+Z não volta, um gesto novo sairia do desenho de antes e brigaria com ele.
  const ocupado = () => Boolean(e.esperando) && performance.now() - e.esperando < ESPERA_MAXIMA
  function avisarOcupado() {
    dica.textContent = "Espere um instante: a conta do Ctrl+Z ainda está voltando."
  }
  function avisarSelecao() {
    let valor = { tipo: "nada" }
    if (e.sel?.no) valor = { tipo: "no", id: prefixo() + e.sel.no }
    else if (e.sel?.fio !== undefined) {
      const f = nivel().fios[e.sel.fio]
      if (f) valor = { tipo: "fio", caminho: [...e.caminho], ...f }
    }
    const texto = JSON.stringify(valor)
    if (texto === e.ultimaSelecao) return
    e.ultimaSelecao = texto
    e.enviar?.("selecao", valor)
  }
  function selecionar(sel) {
    e.sel = sel
    avisarSelecao()
    montarLista()
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
      for (const f of nivel().fios) if (f.de === atual) fila.push(f.para)
    }
    return false
  }
  function ligar(de, saida, para, entrada) {
    const n = nivel()
    if (de === para || alcanca(para, de)) return false
    const s = portas(noPorId(de)).saidas.find((p) => p.chave === saida)
    const ent = portas(noPorId(para)).entradas.find((p) => p.chave === entrada)
    if (!s || !ent || !liga(s, ent)) return false
    if (!ent.varias) n.fios = n.fios.filter((f) => !(f.para === para && f.entrada === entrada))
    if (!n.fios.some((f) => f.de === de && f.saida === saida && f.para === para && f.entrada === entrada)) {
      n.fios.push({ de, saida, para, entrada })
    }
    return true
  }
  const temFioDeSaida = (no, chave) => nivel().fios.some((f) => f.de === no.id && f.saida === chave)
  const temFioDeEntrada = (no, chave) => nivel().fios.some((f) => f.para === no.id && f.entrada === chave)
  const daFila = (p) => FILA.includes(p.tipo)

  // ---- ligação automática: quem só clica na biblioteca já sai com a fila montada
  function fimDaFila(fora) {
    const nos = [...nivel().nos].reverse().filter((n) => !fora.has(n.id))
    const livre = nos.find((n) => {
      const s = portas(n).saidas.find(daFila)
      return s && !temFioDeSaida(n, s.chave)
    })
    return livre ?? nos.find((n) => portas(n).saidas.some(daFila))
  }
  function encaixarNaFila(entra, entrada, sai, saida, fora) {
    // Esforço novo entra antes de quem lê a fila: fica Seção → esforços → critério.
    const consumidor = [...nivel().nos].reverse().find((n) => {
      if (fora.has(n.id)) return false
      const p = portas(n)
      const ent = p.entradas.find(daFila)
      return ent && !p.saidas.some(daFila) && temFioDeEntrada(n, ent.chave)
    })
    if (!consumidor) return false
    const chave = portas(consumidor).entradas.find(daFila).chave
    const fio = nivel().fios.find((f) => f.para === consumidor.id && f.entrada === chave)
    if (!ligar(fio.de, fio.saida, entra.id, entrada.chave)) return false
    return ligar(sai.id, saida.chave, consumidor.id, chave)
  }
  // Vale para um bloco só e para os que chegam juntos numa colagem: o grupo entra na fila como um
  // bloco, pelo primeiro que ainda não recebe e pelo último que ainda não entrega.
  function ligarGrupo(grupo) {
    const ids = new Set(grupo.map((n) => n.id))
    const livreNaEntrada = (n) => {
      const x = portas(n).entradas.find(daFila)
      return x && !temFioDeEntrada(n, x.chave)
    }
    const livreNaSaida = (n) => {
      const x = portas(n).saidas.find(daFila)
      return x && !temFioDeSaida(n, x.chave)
    }
    const entra = grupo.find(livreNaEntrada)
    const sai = [...grupo].reverse().find(livreNaSaida)
    const entradaDaFila = entra ? portas(entra).entradas.find(daFila) : null
    const saidaDaFila = sai ? portas(sai).saidas.find(daFila) : null
    if (!(entradaDaFila && saidaDaFila && encaixarNaFila(entra, entradaDaFila, sai, saidaDaFila, ids)) && entradaDaFila) {
      const fim = fimDaFila(ids)
      if (fim) ligar(fim.id, portas(fim).saidas.find(daFila).chave, entra.id, entradaDaFila.chave)
    }
    if (saidaDaFila && !temFioDeSaida(sai, saidaDaFila.chave)) {
      const livre = nivel().nos.find(
        (n) => !ids.has(n.id) && portas(n).entradas.some((x) => daFila(x) && x.tipo === saidaDaFila.tipo && !temFioDeEntrada(n, x.chave)),
      )
      if (livre) {
        const ent = portas(livre).entradas.find((x) => daFila(x) && !temFioDeEntrada(livre, x.chave))
        ligar(sai.id, saidaDaFila.chave, livre.id, ent.chave)
      }
    }
    for (const no of grupo) ligarOutros(no)
  }
  function ligarOutros(no) {
    const p = portas(no)
    for (const ent of p.entradas) {
      if (ent.tipo === VALOR && !temFioDeEntrada(no, ent.chave)) {
        const achado = [...nivel().nos].reverse().find(
          (n) => n !== no && portas(n).saidas.some((x) => mesmaLetra(x, ent) && !temFioDeSaida(n, x.chave)),
        )
        if (achado) {
          const s = portas(achado).saidas.find((x) => mesmaLetra(x, ent) && !temFioDeSaida(achado, x.chave))
          ligar(achado.id, s.chave, no.id, ent.chave)
        }
      }
      if (ent.tipo === MATERIAL && !temFioDeEntrada(no, ent.chave)) {
        // O mesmo material alimenta todos: não se repete material por verificação.
        const fonte = [...nivel().nos].reverse().find((n) => n !== no && portas(n).saidas.some((x) => x.tipo === MATERIAL))
        if (fonte) ligar(fonte.id, portas(fonte).saidas.find((x) => x.tipo === MATERIAL).chave, no.id, ent.chave)
      }
      if (ent.tipo === CONDICAO) {
        for (const n of nivel().nos) {
          const s = portas(n).saidas.find((x) => x.tipo === CONDICAO)
          if (s && !temFioDeSaida(n, s.chave)) ligar(n.id, s.chave, no.id, ent.chave)
        }
      }
    }
    for (const s of p.saidas) {
      if (s.tipo === CONDICAO) {
        const fim = nivel().nos.find((n) => portas(n).entradas.some((x) => x.tipo === CONDICAO))
        if (fim) ligar(no.id, s.chave, fim.id, portas(fim).entradas.find((x) => x.tipo === CONDICAO).chave)
      }
      if (s.tipo === MATERIAL) {
        for (const n of nivel().nos) {
          const ent = portas(n).entradas.find((x) => x.tipo === MATERIAL && !temFioDeEntrada(n, x.chave))
          if (ent && n !== no) ligar(no.id, s.chave, n.id, ent.chave)
        }
      }
      if (s.tipo === VALOR) {
        const n = [...nivel().nos].reverse().find(
          (x) => x !== no && portas(x).entradas.some((a) => mesmaLetra(s, a) && !temFioDeEntrada(x, a.chave)),
        )
        if (n) {
          const ent = portas(n).entradas.find((a) => mesmaLetra(s, a) && !temFioDeEntrada(n, a.chave))
          ligar(no.id, s.chave, n.id, ent.chave)
        }
      }
    }
  }

  // ---- blocos
  function idNovo() {
    const nos = nivel().nos
    let k = nos.length + 1
    while (nos.some((n) => n.id === `n${k}`)) k += 1
    return `n${k}`
  }
  function sobrepoe(x, y, h) {
    return nivel().nos.some(
      (n) => x < n.x + LARGURA + 16 && x + LARGURA + 16 > n.x && y < n.y + altura(n) + 12 && y + h + 12 > n.y,
    )
  }
  function lugarLivre(no) {
    const r = svg.getBoundingClientRect()
    const limite = Math.max((r.width - e.vista.x) / e.vista.esc - LARGURA - 16, 40)
    const h = altura(no)
    const nos = nivel().nos
    const ultimo = nos.at(-1)
    let x = ultimo ? ultimo.x + LARGURA + FOLGA_X : 30
    let y = ultimo ? ultimo.y : 30
    if (x > limite) {
      x = 30
      y = Math.max(...nos.map((n) => n.y + altura(n))) + FOLGA_Y
    }
    while (sobrepoe(x, y, h)) y += 40
    return [x, y]
  }
  function criarNo(chave) {
    const b = e.catalogo[chave]
    const no = { id: idNovo(), tipo: chave, x: 0, y: 0, opcoes: {} }
    if (b.conjunto) {
      no.tipo = CONJUNTO
      no.nome = b.conjunto.nome
      no.grafo = copiar(b.conjunto.grafo)
      no.portas = copiar(b.conjunto.portas)
    }
    return no
  }
  function acrescentar(chave) {
    if (ocupado()) {
      avisarOcupado()
      return
    }
    if (chave === RESULTADO && nivel().nos.some((n) => n.tipo === chave)) {
      dica.textContent = "A prancheta já tem o bloco Em função de."
      return
    }
    const no = criarNo(chave)
    ;[no.x, no.y] = lugarLivre(no)
    nivel().nos.push(no)
    ligarGrupo([no])
    e.sel = { no: no.id }
    dica.textContent = e.catalogo[chave].dica
    enviar()
  }
  function fioSelecionado() {
    return e.sel?.fio !== undefined ? nivel().fios[e.sel.fio] : null
  }
  function compativeis(fio) {
    const s = portas(noPorId(fio.de)).saidas.find((p) => p.chave === fio.saida)
    const ent = portas(noPorId(fio.para)).entradas.find((p) => p.chave === fio.entrada)
    if (!s || !ent) return []
    return e.ordem.filter((chave) => {
      const b = e.catalogo[chave]
      return b.entradas.some((p) => liga(s, p)) && b.saidas.some((p) => liga(p, ent))
    })
  }
  function inserirNoFio(fio, chave) {
    // A ligação vira origem → novo → destino, e o resto do desenho não anda.
    const b = e.catalogo[chave]
    const n = nivel()
    const s = portas(noPorId(fio.de)).saidas.find((p) => p.chave === fio.saida)
    const ent = portas(noPorId(fio.para)).entradas.find((p) => p.chave === fio.entrada)
    const entrada = b.entradas.find((p) => liga(s, p))
    const saida = b.saidas.find((p) => liga(p, ent))
    if (!entrada || !saida) return
    if (ocupado()) {
      avisarOcupado()
      return
    }
    const no = criarNo(chave)
    const ponta = pontaDoFio(fio)
    no.x = Math.round((ponta.a[0] + ponta.b[0]) / 2 - LARGURA / 2)
    no.y = Math.round((ponta.a[1] + ponta.b[1]) / 2 - altura(no) / 2)
    while (sobrepoe(no.x, no.y, altura(no))) no.y += 40
    n.nos.push(no)
    n.fios = n.fios.filter((f) => f !== fio)
    ligar(fio.de, fio.saida, no.id, entrada.chave)
    ligar(no.id, saida.chave, fio.para, fio.entrada)
    e.sel = { no: no.id }
    e.fantasma = null
    dica.textContent = b.dica
    enviar()
  }
  function apagar() {
    const n = nivel()
    if (ocupado()) {
      avisarOcupado()
      return
    }
    if (e.multi.size) {
      n.fios = n.fios.filter((f) => !e.multi.has(f.de) && !e.multi.has(f.para))
      n.nos = n.nos.filter((x) => !e.multi.has(x.id))
      e.multi.clear()
      e.sel = null
      enviar()
      return
    }
    if (!e.sel) return
    if (e.sel.no) {
      const id = e.sel.no
      const no = noPorId(id)
      const ent = no ? portas(no).entradas.find(daFila) : null
      const sai = no ? portas(no).saidas.find(daFila) : null
      const entra = ent ? n.fios.find((f) => f.para === id && f.entrada === ent.chave) : null
      const saem = sai ? n.fios.filter((f) => f.de === id && f.saida === sai.chave) : []
      n.fios = n.fios.filter((f) => f.de !== id && f.para !== id)
      n.nos = n.nos.filter((x) => x.id !== id)
      // Tirar um esforço do meio não pode quebrar a fila.
      if (entra) for (const f of saem) ligar(entra.de, entra.saida, f.para, f.entrada)
    } else if (e.sel.fio !== undefined) {
      n.fios.splice(e.sel.fio, 1)
    }
    e.sel = null
    enviar()
  }
  function organizar() {
    const n = nivel()
    const coluna = Object.fromEntries(n.nos.map((x) => [x.id, 0]))
    for (let k = 0; k < n.nos.length; k += 1) {
      for (const f of n.fios) coluna[f.para] = Math.max(coluna[f.para], coluna[f.de] + 1)
    }
    // Fila comprida quebra em linhas, para o texto dos blocos não encolher até sumir.
    const largura = svg.getBoundingClientRect().width || 800
    const porLinha = Math.max(2, Math.floor((largura / ESCALA_LEGIVEL - 2 * MARGEM_X + FOLGA_X) / (LARGURA + FOLGA_X)))
    const alturas = {}
    let topo = 30
    const ultima = n.nos.length ? Math.floor(Math.max(...Object.values(coluna)) / porLinha) : 0
    for (let linha = 0; linha <= ultima; linha += 1) {
      let fundo = topo
      for (const x of n.nos) {
        if (Math.floor(coluna[x.id] / porLinha) !== linha) continue
        const c = coluna[x.id] % porLinha
        x.x = 30 + c * (LARGURA + FOLGA_X)
        x.y = alturas[`${linha}:${c}`] ?? topo
        alturas[`${linha}:${c}`] = x.y + altura(x) + FOLGA_Y
        fundo = Math.max(fundo, alturas[`${linha}:${c}`])
      }
      topo = fundo
    }
  }
  function caberNaLargura() {
    // Modelo novo numa prancheta estreita: a fila quebra em linhas em vez de encolher.
    const nos = nivel().nos
    if (!nos.length) return
    const xs = nos.map((n) => n.x)
    const largura = Math.max(...xs) - Math.min(...xs) + LARGURA + 2 * MARGEM_X
    if (largura * ESCALA_LEGIVEL <= svg.getBoundingClientRect().width) return
    organizar()
    e.versao += 1
    e.ultimoSoPosicao = true
    // `automatico`: o Python junta esta arrumação com a mudança de antes, e não abre um passo só
    // para ela no Ctrl+Z.
    e.enviar?.("edicao", pedidoDeEdicao(true, { automatico: true }))
    vigiar()
  }
  function algumVisivel() {
    const r = svg.getBoundingClientRect()
    const esc = e.vista.esc
    return nivel().nos.some((n) => {
      const x = n.x * esc + e.vista.x
      const y = n.y * esc + e.vista.y
      return x + LARGURA * esc > 0 && x < r.width && y + altura(n) * esc > 0 && y < r.height
    })
  }
  function ajustarVista(quebrarFila = false) {
    const r = svg.getBoundingClientRect()
    const w = r.width
    const h = r.height
    if (w < 120 || h < 120) {
      e.ajustarAoMedir = true // ainda sem tamanho: o ResizeObserver chama de novo
      e.quebrarAoMedir = e.quebrarAoMedir || quebrarFila
      return
    }
    e.ajustarAoMedir = false
    if (quebrarFila || e.quebrarAoMedir) {
      e.quebrarAoMedir = false
      caberNaLargura()
    }
    const nos = nivel().nos
    if (!nos.length) {
      e.vista = { x: 0, y: 0, esc: 1 }
      return
    }
    const xs = nos.map((n) => n.x)
    const ys = nos.map((n) => n.y)
    const x0 = Math.min(...xs) - MARGEM_X
    const y0 = Math.min(...ys) - 26
    const x1 = Math.max(...xs) + LARGURA + MARGEM_X
    const y1 = Math.max(...nos.map((n) => n.y + altura(n))) + 26
    const esc = Math.max(0.35, Math.min(1.1, Math.min(w / (x1 - x0), h / (y1 - y0))))
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
  function abrirConjunto(id) {
    e.caminho.push(id)
    e.sel = null
    e.multi.clear()
    ajustarVista()
    montarTrilha()
    avisarSelecao()
    montarLista()
    desenhar()
  }
  function voltarPara(k) {
    e.caminho = e.caminho.slice(0, k)
    e.sel = null
    e.multi.clear()
    ajustarVista()
    montarTrilha()
    avisarSelecao()
    montarLista()
    desenhar()
  }

  // ---- copiar e colar: a cópia nasce com os números do original, e o Python marca de onde vieram
  function copiarSelecao() {
    const ids = e.multi.size ? [...e.multi] : e.sel?.no ? [e.sel.no] : []
    const nos = nivel().nos.filter((n) => ids.includes(n.id) && conhecido(n) && n.tipo !== RESULTADO)
    if (!nos.length) {
      dica.textContent = ids.length
        ? "O bloco Em função de não se copia: a prancheta tem um só."
        : "Selecione um bloco para copiar."
      return false
    }
    const escolhidos = new Set(nos.map((n) => n.id))
    const naFila = (f) => {
      const destino = noPorId(f.para)
      const porta = destino ? portas(destino).entradas.find((p) => p.chave === f.entrada) : null
      return porta ? daFila(porta) : false
    }
    // Vão junto os fios de dentro e os que trazem número ou material de fora. A fila não: a cópia
    // entra nela como um bloco novo, depois do original.
    e.copiado = {
      prefixo: prefixo(),
      nos: copiar(nos),
      fios: copiar(nivel().fios.filter((f) => escolhidos.has(f.para) && (escolhidos.has(f.de) || !naFila(f)))),
    }
    dica.textContent =
      nos.length > 1
        ? `${nos.length} blocos copiados. Ctrl+V cola com os mesmos números.`
        : "Bloco copiado. Ctrl+V cola com os mesmos números."
    return true
  }
  function colar() {
    if (ocupado()) {
      avisarOcupado()
      return
    }
    const c = e.copiado
    if (!c) {
      dica.textContent = "Copie um bloco antes: selecione e aperte Ctrl+C."
      return
    }
    const n = nivel()
    const ids = new Map()
    const criados = []
    for (const original of c.nos) {
      const no = copiar(original)
      no.id = idNovo()
      ids.set(original.id, no.id)
      n.nos.push(no)
      criados.push(no)
    }
    // Logo abaixo do original, descendo até achar lugar sem cobrir outro bloco.
    const novos = new Set(criados.map((x) => x.id))
    const bate = (a) =>
      n.nos.some(
        (b) =>
          !novos.has(b.id) && a.x < b.x + LARGURA + 16 && a.x + LARGURA + 16 > b.x && a.y < b.y + altura(b) + 12 && a.y + altura(a) + 12 > b.y,
      )
    const lugares = criados.map((x) => [x.x, x.y])
    const topo = Math.min(...criados.map((x) => x.y))
    const passo = Math.max(...criados.map((x) => x.y + altura(x))) - topo + FOLGA_Y
    for (let k = 1; k <= 8; k += 1) {
      criados.forEach((x, i) => {
        x.y = lugares[i][1] + passo * k
      })
      if (!criados.some(bate)) break
    }
    const mesmoNivel = c.prefixo === prefixo()
    for (const f of c.fios) {
      const para = ids.get(f.para)
      const de = ids.get(f.de) ?? (mesmoNivel && noPorId(f.de) ? f.de : null)
      if (para && de) ligar(de, f.saida, para, f.entrada)
    }
    ligarGrupo(criados)
    e.multi.clear()
    if (criados.length === 1) e.sel = { no: criados[0].id }
    else {
      e.sel = null
      for (const x of criados) e.multi.add(x.id)
    }
    // A senha é a versão que vai com este desenho: única, e o Python devolve quando já preencheu.
    e.colados[String(e.versao + 1)] = Object.fromEntries(
      criados.map((x, i) => [prefixo() + x.id, c.prefixo + c.nos[i].id]),
    )
    dica.textContent = "Colado com os números do original: mude só o que for diferente."
    enviar()
  }
  function andarNaHistoria(acao) {
    if (editor.aberto()) editor.fechar() // quem aperta Ctrl+Z com a caixinha aberta desiste do número
    e.esperando = performance.now()
    e.esperandoAcao = acao
    e.avisoAntes = e.avisoVisto ?? 0
    dica.textContent = acao === "desfazer" ? "Desfazendo: a conta já volta." : "Refazendo: a conta já volta."
    comandar({ acao, versao: e.versao, grafo: copiar(e.raiz) })
    atualizarBotoes()
  }
  function atualizarBotoes() {
    const h = e.historia ?? {}
    botaoDesfazer.disabled = !h.desfazer && e.versao <= e.versaoDoPython && !e.fila.length
    botaoRefazer.disabled = !h.refazer && !e.fila.some((x) => x.acao === "desfazer")
  }

  const acoes = {
    desfazer() {
      andarNaHistoria("desfazer")
    },
    refazer() {
      andarNaHistoria("refazer")
    },
    duplicar() {
      if (copiarSelecao()) colar()
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
      if (ocupado()) {
        avisarOcupado()
        return
      }
      organizar()
      ajustarVista()
      enviar(true)
    },
    biblioteca() {
      biblioteca.classList.toggle("fechada")
      desenhar()
    },
    agrupar() {
      if (e.multi.size < 2) return
      if (ocupado()) {
        avisarOcupado()
        return
      }
      comandar({ acao: "agrupar", ids: [...e.multi], caminho: [...e.caminho], versao: e.versao })
      e.multi.clear()
      e.sel = null
      desenhar()
    },
  }

  // ---- desenho
  function curva(a, b) {
    const d = Math.max(36, Math.abs(b[0] - a[0]) / 2)
    return [a, [a[0] + d, a[1]], [b[0] - d, b[1]], b]
  }
  function caminhoPeloCorredor(a, b, y) {
    // O fio que volta para a esquerda não cruza os blocos: desce pelo vão entre as linhas.
    const r = 9
    const x1 = a[0] + 17
    const x2 = b[0] - 17
    const s1 = y >= a[1] ? 1 : -1
    const s2 = b[1] >= y ? 1 : -1
    return `M ${a[0]} ${a[1]} H ${x1 - r} Q ${x1} ${a[1]} ${x1} ${a[1] + s1 * r} V ${y - s1 * r} Q ${x1} ${y} ${x1 - r} ${y} H ${x2 + r} Q ${x2} ${y} ${x2} ${y + s2 * r} V ${b[1] - s2 * r} Q ${x2} ${b[1]} ${x2 + r} ${b[1]} H ${b[0]}`
  }
  function caminho(a, b, corredor = null) {
    if (corredor !== null) return caminhoPeloCorredor(a, b, corredor)
    const [p0, p1, p2, p3] = curva(a, b)
    return `M ${p0[0]} ${p0[1]} C ${p1[0]} ${p1[1]}, ${p2[0]} ${p2[1]}, ${p3[0]} ${p3[1]}`
  }
  function naCurva(a, b, t) {
    const [p0, p1, p2, p3] = curva(a, b)
    const u = 1 - t
    return [0, 1].map(
      (k) => u * u * u * p0[k] + 3 * u * u * t * p1[k] + 3 * u * t * t * p2[k] + t * t * t * p3[k],
    )
  }
  function pontoLivre({ a, b, corredor }) {
    // Rótulo e botão do fio procuram um trecho sem bloco em cima.
    if (corredor !== null) return [(a[0] + b[0]) / 2, corredor]
    for (const t of [0.5, 0.42, 0.58, 0.34, 0.66, 0.26, 0.74]) {
      const [x, y] = naCurva(a, b, t)
      const tapado = nivel().nos.some(
        (n) => x > n.x - 22 && x < n.x + LARGURA + 22 && y > n.y - 16 && y < n.y + altura(n) + 16,
      )
      if (!tapado) return [x, y]
    }
    return naCurva(a, b, 0.5)
  }
  function pontaDoFio(f) {
    const de = noPorId(f.de)
    const para = noPorId(f.para)
    if (!de || !para) return null
    const saidas = portas(de).saidas
    const entradas = portas(para).entradas
    const i = saidas.findIndex((p) => p.chave === f.saida)
    const j = entradas.findIndex((p) => p.chave === f.entrada)
    if (i < 0 || j < 0) return null
    const a = portaXY(de, "s", i)
    const b = portaXY(para, "e", j)
    const volta = b[0] < a[0] + 30
    return {
      a,
      b,
      tipo: saidas[i].tipo,
      rotulo: saidas[i].rotulo,
      corredor: volta ? corredorEntre(de, para) + ((nivel().fios.indexOf(f) % 3) - 1) * 5 : null,
    }
  }
  function corredorEntre(de, para) {
    const fundoDe = de.y + altura(de)
    const fundoPara = para.y + altura(para)
    if (para.y > fundoDe) return (fundoDe + para.y) / 2
    if (de.y > fundoPara) return (fundoPara + de.y) / 2
    return Math.max(fundoDe, fundoPara) + 14 // na mesma linha: passa por baixo dos dois
  }
  function compativel(lado, porta, no) {
    const p = e.gesto?.tipo === "fio" ? e.gesto : e.pendente
    if (!p) return null
    if (p.lado === lado || p.no === no.id) return false
    const origem = noPorId(p.no)
    const outro = p.lado === "s"
      ? portas(origem).saidas.find((x) => x.chave === p.chave)
      : portas(origem).entradas.find((x) => x.chave === p.chave)
    if (!outro) return false
    return lado === "e" ? liga(outro, porta) : liga(porta, outro)
  }
  function ligados() {
    // Selecionar um bloco destaca de onde ele vem e para onde vai. O resultado destaca o rastro.
    const rastro = e.marcas.rastro ?? []
    const n = nivel()
    if (e.sel?.no && noPorId(e.sel.no)?.tipo === RESULTADO && rastro.length) {
      const pre = prefixo()
      const ids = new Set([e.sel.no])
      for (const id of rastro) {
        if (id.startsWith(pre)) ids.add(id.slice(pre.length).split("/")[0])
      }
      return ids
    }
    if (!e.sel?.no) return null
    const ids = new Set([e.sel.no])
    for (const passo of ["de", "para"]) {
      const contra = passo === "de" ? "para" : "de"
      const fila = [e.sel.no]
      while (fila.length) {
        const atual = fila.pop()
        for (const f of n.fios) {
          if (f[contra] === atual && !ids.has(f[passo])) {
            ids.add(f[passo])
            fila.push(f[passo])
          }
        }
      }
    }
    return ids
  }
  function nomeNoCartao(no) {
    const nome = cortar(nomeDe(no), 34)
    const aperto = nome.length > LETRAS_DO_NOME ? ` textLength="${LARGURA - 24}" lengthAdjust="spacingAndGlyphs"` : ""
    return `<text class="nome" x="${no.x + 12}" y="${no.y + 43}"${aperto}>${escapar(nome)}</text>`
  }
  function desenharPorta(no, lado, p, i) {
    const [x, y] = portaXY(no, lado, i)
    const estado = compativel(lado, p, no)
    const extra = estado === false ? " apagada" : estado === true ? " pode" : ""
    const tx = lado === "e" ? x - 12 : x + 12
    const ancora = lado === "e" ? "end" : "start"
    return `<circle class="porta t-${p.tipo}${extra}" data-porta="${lado}:${no.id}:${p.chave}" cx="${x}" cy="${y}" r="7.5"><title>${escapar(p.rotulo)}</title></circle>
      <text class="rotulo" x="${tx}" y="${y + 3.5}" text-anchor="${ancora}">${escapar(p.rotulo)}</text>`
  }
  // O número de cada letra vira um pedaço clicável. A letra pedida não: o valor dela sai da conta.
  function pedacosDaLinha(linha) {
    const campos = e.marcas.campos ?? {}
    let s = ""
    linha.itens.forEach((p, i) => {
      if (i) s += escapar(SEPARADOR)
      const campo = p.c ? campos[p.c] : null
      if (!campo || campo.alvo) {
        s += escapar(p.t)
        return
      }
      const classes = ["editavel", campo.copia ? "copiado" : "", e.mudando.has(p.c) ? "pendente" : ""]
      const titulo = campo.copia
        ? `${campo.t}: copiado de ${campo.copia}. Dois cliques para mudar.`
        : `${campo.t}: dois cliques para mudar.`
      s += `<tspan class="${classes.filter(Boolean).join(" ")}" data-chave="${escapar(p.c)}">${escapar(p.t)}<title>${escapar(titulo)}</title></tspan>`
    })
    if (linha.mais) s += " …"
    return s
  }
  function desenharBloco(no, destaque) {
    const p = portas(no)
    const h = altura(no)
    const chave = prefixo() + no.id
    const erro = erroDe(no)
    const sel = e.sel?.no === no.id || e.multi.has(no.id)
    const fraco = destaque && !destaque.has(no.id)
    const { linhas, forte, copia } = conteudo(no)
    const classe = classeDe(no)
    const categoria = no.tipo === CONJUNTO ? "CONJUNTO REUTILIZÁVEL" : tipoDe(no)?.categoria ?? ""
    const luzDoBloco = erro ? "erro" : e.marcas.luzes?.[chave] ?? e.marcas.situacao?.nivel ?? "falta"
    const x = no.x
    const y = no.y
    let s = `<g class="no${sel ? " sel" : ""}${erro ? " errado" : ""}${fraco ? " fraco" : ""}${no.tipo === RESULTADO ? " decisao" : ""}" data-no="${no.id}">`
    if (sel) s += `<rect class="halo" x="${x - 2}" y="${y - 2}" width="${LARGURA + 4}" height="${h + 4}" rx="11"/>`
    s += `<rect class="corpo" x="${x}" y="${y}" width="${LARGURA}" height="${h}" rx="9"/>
      <path class="topo ${classe}" d="M ${x + 0.6} ${y + 9} q 0 -8.4 8.4 -8.4 h ${LARGURA - 18} q 8.4 0 8.4 8.4"/>
      <text class="categoria" x="${x + 12}" y="${y + 16}">${escapar(categoria)}</text>
      <circle class="luz-no ${luzDoBloco}" cx="${x + LARGURA - 13}" cy="${y + 12.5}" r="3.6"/>
      <text class="fecha" data-fecha="${no.id}" x="${x + LARGURA - 30}" y="${y + 17}">×<title>Apagar este bloco</title></text>
      <line class="divisa" x1="${x}" y1="${y + FAIXA}" x2="${x + LARGURA}" y2="${y + FAIXA}"/>
      ${nomeNoCartao(no)}`
    let linhaY = y + 58
    for (const linha of linhas) {
      s += `<text class="linha" x="${x + 12}" y="${linhaY}">${pedacosDaLinha(linha)}</text>`
      linhaY += 13
    }
    if (copia) {
      // Pendurado na borda de cima, para não brigar com o texto do cartão.
      s += `<g class="selo-copia"><rect x="${x + LARGURA - 66}" y="${y - 8}" width="46" height="14" rx="4"/><text x="${x + LARGURA - 43}" y="${y + 2.4}" text-anchor="middle">CÓPIA</text><title>Números copiados de outro bloco. Dois cliques num número mudam o valor; Enter na caixinha confirma o que já está certo.</title></g>`
    }
    if (forte) {
      s += `<text class="destaque" x="${x + 12}" y="${linhaY + 2}">${escapar(forte)}</text>`
      linhaY += 15
    }
    if (no.tipo === CONJUNTO) {
      const quantos = no.grafo?.nos?.length ?? 0
      s += `<g class="pilula" data-abrir="${no.id}"><rect x="${x + 12}" y="${linhaY - 4}" width="${LARGURA - 24}" height="16" rx="4"/><text x="${x + LARGURA / 2}" y="${linhaY + 7}" text-anchor="middle">${quantos} BLOCOS · ABRIR O CONJUNTO</text><title>Abrir o conjunto</title></g>`
    }
    p.entradas.forEach((x_, i) => { s += desenharPorta(no, "e", x_, i) })
    p.saidas.forEach((x_, i) => { s += desenharPorta(no, "s", x_, i) })
    if (erro) {
      const curto = erro.length > 32 ? `${erro.slice(0, 31)}…` : erro
      s += `<text class="erro" x="${x + 12}" y="${y + h - 7}">${escapar(curto)}<title>${escapar(erro)}</title></text>`
    }
    return `${s}<title>${escapar(erro || tipoDe(no)?.dica || nomeDe(no))}</title></g>`
  }
  function desenharFantasma(fio) {
    const b = e.catalogo[e.fantasma]
    const ponta = pontaDoFio(fio)
    if (!b || !ponta) return ""
    const h = 92
    const x = (ponta.a[0] + ponta.b[0]) / 2 - LARGURA / 2
    const y = (ponta.a[1] + ponta.b[1]) / 2 - h / 2
    const entrada = [x, y + PORTA_Y + PORTA_PASSO / 2]
    const saida = [x + LARGURA, y + PORTA_Y + PORTA_PASSO / 2]
    return `<g class="fantasma">
      <path class="fio solto t-${ponta.tipo}" d="${caminho(ponta.a, entrada)}"/>
      <path class="fio solto t-${ponta.tipo}" d="${caminho(saida, ponta.b)}"/>
      <rect class="corpo" x="${x}" y="${y}" width="${LARGURA}" height="${h}" rx="9"/>
      <text class="categoria" x="${x + 12}" y="${y + 16}">PRÉVIA</text>
      <text class="nome" x="${x + 12}" y="${y + 43}">${escapar(b.nome)}</text>
      <text class="linha" x="${x + 12}" y="${y + 58}">${escapar(b.formula)}</text>
    </g>`
  }
  function desenhar() {
    const n = nivel()
    const destaque = ligados()
    let s = ""
    n.fios.forEach((f, i) => {
      const p = pontaDoFio(f)
      if (!p) return
      const d = caminho(p.a, p.b, p.corredor)
      const marcado = e.sel?.fio === i
      const aceso = marcado || (destaque && destaque.has(f.de) && destaque.has(f.para))
      const fraco = destaque && !aceso
      s += `<path class="fio t-${p.tipo}${aceso ? " ativo" : ""}${fraco ? " fraco" : ""}" d="${d}"/><path class="toque" data-fio="${i}" d="${d}"/>`
      if (aceso) {
        const [x, y] = p.b
        s += `<polygon class="seta t-${p.tipo}" points="${x - 15},${y - 6} ${x - 15},${y + 6} ${x - 6},${y}"/>`
      }
    })
    const ordem = e.topo ? [...n.nos.filter((x) => x.id !== e.topo), ...n.nos.filter((x) => x.id === e.topo)] : n.nos
    for (const no of ordem) if (conhecido(no)) s += desenharBloco(no, destaque)
    const ativo = e.sel?.fio !== undefined ? e.sel.fio : e.realce
    if (ativo !== null && ativo !== undefined && n.fios[ativo]) {
      const p = pontaDoFio(n.fios[ativo])
      if (p) {
        const [x, y] = pontoLivre(p)
        const rotulo = escapar(p.rotulo)
        const largura = Math.max(38, rotulo.length * 6.2 + 14)
        // No vão entre as linhas não cabe em cima: o nome vai ao lado do botão.
        const cx = p.corredor !== null ? x + 15 + largura / 2 : x
        const cy = p.corredor !== null ? y - 9.5 : y - 36
        s += `<g class="chip"><rect x="${cx - largura / 2}" y="${cy}" width="${largura}" height="19" rx="5"/><text x="${cx}" y="${cy + 13.5}" text-anchor="middle">${rotulo}</text></g>
          <g class="mais" data-mais="${ativo}"><circle cx="${x}" cy="${y}" r="11"/><text x="${x}" y="${y + 5.5}" text-anchor="middle">+</text><title>Inserir um bloco nesta ligação</title></g>`
      }
    }
    const fio = fioSelecionado()
    if (fio && e.fantasma) s += desenharFantasma(fio)
    const g = e.gesto
    svg.classList.toggle("ligando", g?.tipo === "fio" || Boolean(e.pendente))
    if (g?.tipo === "fio" && g.ponta) {
      const no = noPorId(g.no)
      const lista = g.lado === "s" ? portas(no).saidas : portas(no).entradas
      const i = lista.findIndex((p) => p.chave === g.chave)
      const base = portaXY(no, g.lado, i)
      const d = g.lado === "s" ? caminho(base, g.ponta) : caminho(g.ponta, base)
      s += `<path class="fio solto t-${lista[i].tipo}" d="${d}"/>`
    }
    svg.innerHTML = `<g transform="translate(${e.vista.x} ${e.vista.y}) scale(${e.vista.esc})">${s}</g>`
    const passo = 22 * e.vista.esc
    svg.style.backgroundSize = `${passo}px ${passo}px`
    svg.style.backgroundPosition = `${e.vista.x}px ${e.vista.y}px`
    zoom.textContent = `${Math.round(e.vista.esc * 100)}%`
    botaoAgrupar.hidden = e.multi.size < 2
    const umBloco = noPorId(e.sel?.no)
    botaoDuplicar.disabled = !(e.multi.size || (umBloco && umBloco.tipo !== RESULTADO))
  }

  // ---- o número no próprio cartão
  const editor = criarEditorVivo(miolo, {
    aoFechar() {
      e.editando = null
    },
    aoTab(voltar) {
      editor.confirmar(vizinhaDoCampo(voltar ? -1 : 1))
    },
    depoisDoTeclado() {
      svg.focus({ preventScroll: true })
    },
  })
  const entradaDoEditor = miolo.querySelector(".editor input")
  function camposDoBloco(id) {
    return [...svg.querySelectorAll("[data-no] [data-chave]")]
      .filter((t) => t.closest("[data-no]").dataset.no === id)
  }
  function elementoDoCampo(id, chave) {
    return camposDoBloco(id).find((t) => t.dataset.chave === chave) ?? null
  }
  function vizinhaDoCampo(passo) {
    const atual = e.editando
    if (!atual) return null
    const lista = [...new Set(camposDoBloco(atual.no).map((t) => t.dataset.chave))]
    if (lista.length < 2) return null
    const k = lista.indexOf(atual.chave)
    return { no: atual.no, chave: lista[(k + passo + lista.length) % lista.length] }
  }
  function editarLetra(id, chave) {
    const campo = e.marcas.campos?.[chave]
    const alvo = elementoDoCampo(id, chave)
    if (!campo || !alvo || campo.alvo) return false
    if (editor.aberto() && !editor.confirmar()) return false
    e.editando = { no: id, chave }
    editor.abrir(alvo, {
      valor: campo.v ?? 0,
      texto: textoParaEditar(campo.v),
      unidade: campo.u ?? "",
      nome: campo.copia ? `${campo.t}: ${campo.n}. Copiado de ${campo.copia}: Enter confirma.` : `${campo.t}: ${campo.n}`,
      dica: DICA_DO_EDITOR,
      ler: (texto) => lerDoCartao(texto, campo),
      aplicar(v, seguinte) {
        const antes = campo.v ?? null
        if (mesmoNumero(v, antes)) {
          // Enter sem mudar nada num número copiado quer dizer que ele está certo.
          if (campo.copia && antes !== null) {
            comandar({ acao: "valor", chave, valor: antes, unidade: campo.u ?? "", conferir: true })
          }
          if (seguinte) setTimeout(() => editarLetra(seguinte.no, seguinte.chave), 0)
          return ""
        }
        e.proxima = seguinte
        e.mudando.set(chave, comandar({ acao: "valor", chave, valor: v, unidade: campo.u ?? "" }))
        desenhar()
        return ""
      },
    })
    entradaDoEditor?.select() // digitar já troca o número inteiro
    return true
  }
  function primeiraLetra(id) {
    return camposDoBloco(id)[0]?.dataset.chave ?? null
  }

  // ---- ponteiro
  function portaEm(ev) {
    const alvo = ev.target?.closest?.("[data-porta]")
    if (alvo) {
      const [lado, no, chave] = alvo.dataset.porta.split(":")
      return { lado, no, chave }
    }
    // Bolinha é pequena: vale a mais perto dentro do alcance.
    const [x, y] = mundo(ev)
    const alcance = TOQUE_PORTA / e.vista.esc
    for (const no of nivel().nos) {
      if (!conhecido(no)) continue
      const p = portas(no)
      for (const [lado, itens] of [["e", p.entradas], ["s", p.saidas]]) {
        for (let i = 0; i < itens.length; i += 1) {
          const [px, py] = portaXY(no, lado, i)
          if (Math.hypot(px - x, py - y) < alcance) return { lado, no: no.id, chave: itens[i].chave }
        }
      }
    }
    return null
  }
  function concluir(a, b) {
    if (!a || !b || a.lado === b.lado) return false
    const [saida, entrada] = a.lado === "s" ? [a, b] : [b, a]
    if (!ligar(saida.no, saida.chave, entrada.no, entrada.chave)) {
      dica.textContent = "Essas duas bolinhas não ligam: as grandezas são diferentes, ou o fio fecharia um laço."
      return false
    }
    enviar()
    return true
  }

  // O contorno de foco é para quem chega pelo teclado: com o mouse ele só atrapalha.
  svg.addEventListener("keyup", (ev) => {
    if (ev.key === "Tab") svg.classList.add("teclado")
  })
  svg.addEventListener("blur", () => svg.classList.remove("teclado"))
  svg.addEventListener("pointerdown", (ev) => {
    svg.classList.remove("teclado")
    svg.focus({ preventScroll: true })
    try {
      svg.setPointerCapture(ev.pointerId)
    } catch {
      // ponteiro sintético não captura, e o gesto segue pelos eventos do próprio svg
    }
    if (ocupado()) {
      // Até a conta do Ctrl+Z voltar, a prancheta só deixa andar pela vista.
      avisarOcupado()
      e.gesto = { tipo: "pan", inicio: [ev.clientX, ev.clientY], vista: { ...e.vista } }
      svg.classList.add("puxando")
      return
    }
    const duplo = segundoToque(ev)
    if (duplo?.chave) {
      // Sem o padrão do toque, o navegador poria o foco de volta na prancheta e a caixinha fecharia.
      ev.preventDefault()
      e.gesto = null
      editarLetra(duplo.no, duplo.chave)
      return
    }
    if (duplo && noPorId(duplo.no)?.tipo === CONJUNTO) {
      ev.preventDefault()
      e.gesto = null
      abrirConjunto(duplo.no)
      return
    }
    const fecha = ev.target.closest?.("[data-fecha]")
    if (fecha) {
      e.multi.clear()
      e.sel = { no: fecha.dataset.fecha }
      apagar()
      return
    }
    const abrir = ev.target.closest?.("[data-abrir]")
    if (abrir) {
      abrirConjunto(abrir.dataset.abrir)
      return
    }
    const mais = ev.target.closest?.("[data-mais]")
    if (mais) {
      selecionar({ fio: Number(mais.dataset.mais) })
      biblioteca.classList.remove("fechada")
      busca.focus()
      dica.textContent = "Escolha um bloco compatível para inserir nesta ligação."
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
        const n = nivel()
        const f = n.fios.findIndex((x) => x.para === porta.no && x.entrada === porta.chave)
        const varias = portas(noPorId(porta.no)).entradas.find((p) => p.chave === porta.chave)?.varias
        if (f >= 0 && !varias) {
          const [antigo] = n.fios.splice(f, 1)
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
      e.multi.clear()
      dica.textContent = "Ligação selecionada: use + para inserir um bloco, ou Delete para apagar."
      selecionar({ fio: Number(fio.dataset.fio) })
      return
    }
    const alvo = ev.target.closest?.("[data-no]")
    if (alvo) {
      const no = noPorId(alvo.dataset.no)
      if (ev.shiftKey) {
        if (e.multi.has(no.id)) e.multi.delete(no.id)
        else e.multi.add(no.id)
        if (e.sel?.no && !e.multi.has(e.sel.no)) e.multi.add(e.sel.no)
        e.sel = null
        dica.textContent = "Shift + clique marca vários blocos: depois use Agrupar."
        avisarSelecao()
        desenhar()
        return
      }
      e.multi.clear()
      e.topo = no.id
      dica.textContent = tipoDe(no)?.dica ?? "Conjunto: abra para ver os blocos de dentro."
      if (e.sel?.no !== no.id) selecionar({ no: no.id })
      e.gesto = { tipo: "mover", no, base: [no.x, no.y], inicio: mundo(ev), moveu: false }
      svg.classList.add("puxando")
      desenhar()
      return
    }
    e.multi.clear()
    dica.textContent = DICA
    e.gesto = { tipo: "pan", inicio: [ev.clientX, ev.clientY], vista: { ...e.vista } }
    svg.classList.add("puxando")
    if (e.sel) selecionar(null)
    else desenhar()
  })
  // Dois toques são contados aqui, e não pelo dblclick: o primeiro toque redesenha o bloco, o
  // elemento tocado some, e o navegador não manda nem o click nem o dblclick.
  function segundoToque(ev) {
    const bloco = ev.target.closest?.("[data-no]")
    const numero = ev.target.closest?.("[data-chave]")
    const marca = bloco ? `${bloco.dataset.no}|${numero?.dataset.chave ?? ""}` : null
    const antes = e.ultimoToque
    const agora = performance.now()
    e.ultimoToque = marca ? { marca, t: agora, x: ev.clientX, y: ev.clientY } : null
    if (!marca || antes?.marca !== marca || agora - antes.t > 450) return null
    if (Math.hypot(ev.clientX - antes.x, ev.clientY - antes.y) > 8) return null
    e.ultimoToque = null
    return { no: bloco.dataset.no, chave: numero?.dataset.chave ?? null }
  }
  svg.addEventListener("pointermove", (ev) => {
    const g = e.gesto
    if (!g) {
      const toque = ev.target.closest?.("[data-fio], [data-mais]")
      const novo = toque ? Number(toque.dataset.fio ?? toque.dataset.mais) : null
      if (novo !== e.realce) {
        e.realce = novo
        desenhar()
      }
      return
    }
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
        g.moveu = true
        g.no = noPorId(g.no.id)
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
      enviar(true)
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
    if (editor.aberto()) editor.confirmar() // a caixinha não acompanha o zoom
    const [x, y] = noPonteiro(ev)
    aproximar(ev.deltaY < 0 ? 1.1 : 1 / 1.1, x, y)
  }, { passive: false })
  function vizinho(dx, dy) {
    // Setas andam para o bloco mais perto naquela direção: dá para percorrer sem mouse.
    const nos = nivel().nos.filter(conhecido)
    if (!nos.length) return
    const atual = noPorId(e.sel?.no) ?? nos[0]
    if (!e.sel?.no) {
      selecionar({ no: atual.id })
      return
    }
    let melhor = null
    let menor = Infinity
    for (const n of nos) {
      if (n === atual) continue
      const [a, b] = [n.x - atual.x, n.y - atual.y]
      const frente = a * dx + b * dy
      if (frente <= 0) continue
      const custo = frente + 3 * Math.abs(a * dy - b * dx)
      if (custo < menor) {
        menor = custo
        melhor = n
      }
    }
    if (melhor) selecionar({ no: melhor.id })
  }
  svg.addEventListener("keydown", (ev) => {
    const ctrl = ev.ctrlKey || ev.metaKey
    const setas = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }
    if (ev.key === "Delete" || ev.key === "Backspace") {
      ev.preventDefault()
      apagar()
    } else if (setas[ev.key]) {
      ev.preventDefault()
      vizinho(...setas[ev.key])
    } else if (ev.key === "Enter" || ev.key === "F2") {
      // Enter abre o conjunto; nos outros blocos, Enter e F2 abrem o primeiro número do cartão.
      const no = noPorId(e.sel?.no)
      const letra = no && !ocupado() ? primeiraLetra(no.id) : null
      if (ev.key === "Enter" && no?.tipo === CONJUNTO) abrirConjunto(no.id)
      else if (letra) {
        ev.preventDefault()
        editarLetra(no.id, letra)
      } else if (ev.key === "Enter" && e.sel?.fio !== undefined) {
        biblioteca.classList.remove("fechada")
        busca.focus()
      }
    } else if (ev.key === "Escape") {
      if (e.pendente || e.sel || e.multi.size) {
        e.pendente = null
        e.multi.clear()
        selecionar(null)
      } else if (e.caminho.length) {
        voltarPara(e.caminho.length - 1)
      }
    } else if (ctrl && ev.key.toLowerCase() === "z") {
      ev.preventDefault()
      acoes.desfazer()
    } else if (ctrl && ev.key.toLowerCase() === "y") {
      ev.preventDefault()
      acoes.refazer()
    } else if (ctrl && ev.key.toLowerCase() === "c") {
      ev.preventDefault()
      copiarSelecao()
    } else if (ctrl && ev.key.toLowerCase() === "v") {
      ev.preventDefault()
      colar()
    }
  })
  raiz.querySelectorAll("[data-a]").forEach((b) => {
    b.addEventListener("click", () => acoes[b.dataset.a]())
  })
  busca.addEventListener("input", () => {
    e.filtro = semAcento(busca.value.trim())
    montarLista()
  })
  busca.addEventListener("keydown", (ev) => {
    ev.stopPropagation()
    if (ev.key === "Enter") lista.querySelector(".item")?.click()
    if (ev.key === "Escape") {
      busca.value = ""
      e.filtro = ""
      montarLista()
      svg.focus({ preventScroll: true })
    }
  })

  // ---- biblioteca
  function itemDaLista(chave, aoClicar, previa) {
    const b = e.catalogo[chave]
    const botao = document.createElement("button")
    botao.type = "button"
    botao.className = "item"
    botao.title = b.dica
    const nome = document.createElement("strong")
    nome.textContent = b.nome
    const formula = document.createElement("span")
    formula.textContent = b.formula
    botao.append(nome, formula)
    if (previa) {
      const selo = document.createElement("em")
      selo.textContent = "✓ COMPATÍVEL"
      botao.append(selo)
      for (const [evento, valor] of [["mouseenter", chave], ["focus", chave], ["mouseleave", null], ["blur", null]]) {
        botao.addEventListener(evento, () => {
          e.fantasma = valor
          desenhar()
        })
      }
    }
    botao.addEventListener("click", aoClicar)
    return botao
  }
  function grupoDaLista(nome, chaves, aberto, aoAlternar) {
    const caixa = document.createElement("details")
    caixa.open = aberto
    const titulo_ = document.createElement("summary")
    titulo_.textContent = `${nome} (${chaves.length})`
    caixa.append(titulo_)
    for (const chave of chaves) caixa.append(itemDaLista(chave, () => acrescentar(chave), false))
    caixa.addEventListener("toggle", () => aoAlternar?.(caixa.open))
    return caixa
  }
  function montarLista() {
    const fio = fioSelecionado()
    const achou = (chave) => {
      if (!e.filtro) return true
      const b = e.catalogo[chave]
      return semAcento(`${b.nome} ${b.dica} ${b.formula} ${b.grupo}`).includes(e.filtro)
    }
    const partes = []
    if (fio) {
      const boas = compativeis(fio).filter(achou)
      conta.textContent = `${boas.length} compatíve${boas.length === 1 ? "l" : "is"}`
      ajuda.textContent = boas.length ? AJUDA_FIO : "Nenhum bloco cabe nesta ligação."
      for (const chave of boas) {
        partes.push(itemDaLista(chave, () => inserirNoFio(fio, chave), true))
      }
      const resto = e.ordem.filter((c) => !boas.includes(c) && achou(c))
      if (resto.length) partes.push(grupoDaLista("Outros blocos", resto, false))
    } else {
      conta.textContent = ""
      ajuda.textContent = AJUDA
      const grupos = new Map()
      for (const chave of e.ordem) {
        if (!achou(chave)) continue
        const grupo = e.catalogo[chave].grupo
        if (!grupos.has(grupo)) grupos.set(grupo, [])
        grupos.get(grupo).push(chave)
      }
      if (e.abertos === null) e.abertos = new Set([...grupos.keys()].slice(0, 2))
      for (const [nome, chaves] of grupos) {
        const aberto = Boolean(e.filtro) || e.abertos.has(nome)
        partes.push(
          grupoDaLista(nome, chaves, aberto, (agora) => {
            if (e.filtro) return
            if (agora) e.abertos.add(nome)
            else e.abertos.delete(nome)
          }),
        )
      }
      if (!grupos.size) {
        const vazio = document.createElement("p")
        vazio.className = "lista-titulo"
        vazio.textContent = "Nenhum bloco com esse nome."
        partes.push(vazio)
      }
    }
    lista.replaceChildren(...partes)
  }
  function montarTrilha() {
    const pedacos = []
    const inicio = document.createElement("button")
    inicio.type = "button"
    inicio.textContent = "Montagem"
    inicio.addEventListener("click", () => voltarPara(0))
    pedacos.push(inicio)
    let atual = e.raiz
    e.caminho.forEach((id, k) => {
      const no = atual.nos.find((n) => n.id === id)
      atual = no?.grafo ?? atual
      const seta = document.createElement("span")
      seta.textContent = "›"
      const botao = document.createElement("button")
      botao.type = "button"
      botao.textContent = no?.nome ?? id
      botao.addEventListener("click", () => voltarPara(k + 1))
      pedacos.push(seta, botao)
    })
    trilha.replaceChildren(...pedacos)
    trilha.hidden = !e.caminho.length
  }
  function mostrarSituacao() {
    const s = e.marcas.situacao ?? { nivel: "falta", titulo: "Monte os blocos", detalhe: "" }
    luz.className = `luz ${s.nivel}`
    titulo.textContent = s.titulo
    titulo.title = s.titulo
    detalhe.textContent = s.detalhe
    detalhe.title = s.detalhe
  }

  e.receber = (dados) => {
    const catalogo = dados.catalogo ?? []
    const assinatura = canonico(catalogo)
    let refazerLista = false
    if (assinatura !== e.assinatura) {
      e.assinatura = assinatura
      e.catalogo = Object.fromEntries(catalogo.map((b) => [b.chave, b]))
      e.ordem = catalogo.map((b) => b.chave)
      refazerLista = true
    }
    const novo = dados.grafo ?? { nos: [], fios: [] }
    if (dados.versao >= e.versao) {
      if (canonico(novo) !== canonico(e.raiz)) {
        e.raiz = copiar(novo)
        let atual = e.raiz
        const valido = []
        for (const id of e.caminho) {
          const no = atual.nos.find((n) => n.id === id)
          if (!no?.grafo) break
          valido.push(id)
          atual = no.grafo
        }
        e.caminho = valido
        if (e.sel?.no && !noPorId(e.sel.no)) e.sel = null
        if (e.sel?.fio !== undefined && !nivel().fios[e.sel.fio]) e.sel = null
        for (const id of [...e.multi]) if (!noPorId(id)) e.multi.delete(id)
        montarTrilha()
        refazerLista = true
      }
      e.versao = dados.versao
    }
    e.marcas = dados.marcas ?? {}
    mostrarSituacao()
    if (receberConfirmacoes(dados) && !algumVisivel()) ajustarVista() // o Ctrl+Z trouxe blocos de fora da vista
    const pedido = dados.selecionar
    if (pedido && pedido.n !== e.selecionarVisto) {
      // A tela em Python também escolhe: inserir pelo inspetor seleciona o bloco novo.
      e.selecionarVisto = pedido.n
      e.caminho = pedido.caminho ?? []
      e.multi.clear()
      montarTrilha()
      if (pedido.no) e.sel = noPorId(pedido.no) ? { no: pedido.no } : null
      else if (pedido.fio) {
        const i = nivel().fios.findIndex(
          (f) => f.de === pedido.fio.de && f.saida === pedido.fio.saida && f.para === pedido.fio.para && f.entrada === pedido.fio.entrada,
        )
        e.sel = i >= 0 ? { fio: i } : null
      } else e.sel = null
      e.ultimaSelecao = "?"
      refazerLista = true
    }
    if (e.verAjuste !== dados.ajustar) {
      // Outra montagem inteira: o que estava selecionado era da anterior.
      e.verAjuste = dados.ajustar
      e.caminho = []
      e.sel = null
      e.multi.clear()
      e.ultimaSelecao = '{"tipo":"nada"}'
      montarTrilha()
      ajustarVista(true)
    }
    if (refazerLista) montarLista()
    desenhar()
    // A caixinha aberta num número que sumiu fecha; o Tab depois de mudar um número abre o seguinte.
    if (e.editando && editor.aberto() && !elementoDoCampo(e.editando.no, e.editando.chave)) editor.fechar()
    if (e.proxima && !editor.aberto()) {
      const { no, chave } = e.proxima
      e.proxima = null
      editarLetra(no, chave)
    }
  }

  // O que o Python já fez: os pedidos confirmados saem da fila, e o Ctrl+Z diz o que desfez.
  // Devolve se um Ctrl+Z acabou de voltar.
  function receberConfirmacoes(dados) {
    if (Number.isInteger(dados.versao)) e.versaoDoPython = dados.versao
    const recebido = Number.isInteger(dados.recebido) ? dados.recebido : 0
    e.n = Math.max(e.n, recebido)
    e.fila = e.fila.filter((x) => x.n > recebido)
    for (const [chave, n] of [...e.mudando]) if (n <= recebido) e.mudando.delete(chave)
    for (const senha of dados.colagens ?? []) delete e.colados[senha]
    e.historia = dados.historia ?? {}
    const aviso = e.historia.aviso ?? null
    const numero = aviso?.n ?? 0
    if (e.avisoVisto === null) e.avisoVisto = numero // o que já havia ao abrir a página não é novidade
    const voltou = Boolean(e.esperando) && !e.fila.some((x) => x.acao === "desfazer" || x.acao === "refazer")
    if (voltou) {
      e.esperando = 0
      if (aviso && numero !== e.avisoAntes) dica.textContent = aviso.texto
      else dica.textContent = e.esperandoAcao === "desfazer" ? "Não há o que desfazer." : "Não há o que refazer."
      e.avisoVisto = numero
    } else if (aviso && numero !== e.avisoVisto) {
      e.avisoVisto = numero
      dica.textContent = aviso.texto
    }
    atualizarBotoes()
    vigiar()
    return voltou
  }

  new ResizeObserver(() => {
    if (e.ajustarAoMedir) ajustarVista()
    desenhar()
  }).observe(svg)
  montarTrilha()
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
