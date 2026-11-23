// Prancheta do esboço: desenha como um CAD paramétrico. A cota segura o valor, as restrições
// prendem a forma, e o que ainda está livre aparece em azul. Tudo roda aqui (solver.js); o Python só
// recebe o esboço pronto ao fim de cada gesto, para as contas da seção. O estado fica preso ao
// parentElement, porque o Streamlit chama esta função de novo a cada rodada.

// Os ícones da barra, no estilo dos CADs: traço fino num quadro 24 × 24. Desenhados aqui.
const ES_ICONES = {
  desfazer: '<path d="M9 14 4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/>',
  refazer: '<path d="m15 14 5-5-5-5"/><path d="M20 9H9a5 5 0 0 0 0 10h3"/>',
  selecionar: '<path d="M6 4l12 7-5.5 1.5L15 19l-2.2 1-2.6-6.4L6 17z"/>',
  linha: '<path d="M5 19 19 5"/><circle cx="5" cy="19" r="1.9"/><circle cx="19" cy="5" r="1.9"/>',
  retangulo: '<rect x="4" y="6" width="16" height="12" rx="0.5"/><circle cx="4" cy="18" r="1.7"/><circle cx="20" cy="6" r="1.7"/>',
  retangulo_centro: '<rect x="4" y="6" width="16" height="12" rx="0.5"/><path d="M4 6l16 12" stroke-dasharray="2 2"/><circle cx="12" cy="12" r="1.7"/>',
  circulo: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="1.4"/><path d="M12 12h8" stroke-dasharray="2 2"/>',
  arco: '<path d="M4 17A9 9 0 0 1 20 17"/><circle cx="4" cy="17" r="1.7"/><circle cx="20" cy="17" r="1.7"/><circle cx="12" cy="8.5" r="1.7"/>',
  arco_tangente: '<path d="M3 18h7"/><path d="M10 18a6 6 0 0 0 6-6V5"/><circle cx="3" cy="18" r="1.6"/><circle cx="16" cy="5" r="1.6"/>',
  ponto: '<circle cx="12" cy="12" r="3" fill="currentColor"/>',
  construcao: '<path d="M4 20 20 4" stroke-dasharray="3 3"/><circle cx="4" cy="20" r="1.6"/><circle cx="20" cy="4" r="1.6"/>',
  cota: '<path d="M4 7v10M20 7v10"/><path d="M4 12h16"/><path d="m7 9.5-3 2.5 3 2.5M17 9.5l3 2.5-3 2.5"/>',
  coincidente: '<circle cx="12" cy="12" r="5.5"/><circle cx="12" cy="12" r="1.8" fill="currentColor"/>',
  horizontal: '<path d="M4 12h16"/><path d="M4 8v8M20 8v8"/>',
  vertical: '<path d="M12 4v16"/><path d="M8 4h8M8 20h8"/>',
  paralela: '<path d="M6 19 14 5M11 19l8-14"/>',
  perpendicular: '<path d="M5 19h14M12 19V5"/><path d="M12 15h4v4"/>',
  tangente: '<circle cx="12" cy="14" r="6"/><path d="M3 8h18"/>',
  igual: '<path d="M5 9h14M5 15h14"/>',
  ponto_medio: '<path d="M4 18 20 6"/><path d="m12 9 3 3-3 3-3-3z" fill="currentColor"/>',
  concentrico: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/>',
  simetrico: '<path d="M12 3v18" stroke-dasharray="2.5 2.5"/><circle cx="6" cy="12" r="2"/><circle cx="18" cy="12" r="2"/>',
  fixo: '<rect x="6" y="11" width="12" height="9" rx="1.5"/><path d="M9 11V8a3 3 0 0 1 6 0v3"/>',
  enquadrar: '<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/><rect x="9" y="9" width="6" height="6"/>',
  tela: '<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/><path d="M4 4l5 5M20 4l-5 5M20 20l-5-5M4 20l5-5"/>',
  sair_da_tela: '<path d="M9 4v5H4M20 9h-5V4M15 20v-5h5M4 15h5v5"/>',
  seta: '<path d="m2 4 3 3 3-3"/>',
  aparar: '<circle cx="6" cy="7" r="2.6"/><circle cx="6" cy="17" r="2.6"/><path d="M8.2 8.4 20 17M8.2 15.6 20 7"/>',
  estender: '<path d="M4 16h10" /><path d="M14 16h3" stroke-dasharray="1.5 2"/><path d="M20 6v14"/><path d="m15 13 3 3-3 3"/>',
  dividir: '<path d="M4 18 10.5 11.5M13.5 8.5 20 2"/><circle cx="12" cy="10" r="1.8"/><circle cx="4" cy="18" r="1.4"/>',
  filete: '<path d="M5 20V12a7 7 0 0 1 7-7h8"/><path d="M5 5h3M5 5v3" stroke-dasharray="1.5 1.5"/>',
  chanfro: '<path d="M5 20v-9l6-6h9"/><path d="M5 5h3M5 5v3" stroke-dasharray="1.5 1.5"/>',
  deslocar: '<path d="M4 18V8a4 4 0 0 1 4-4h12"/><path d="M8 20v-9a3 3 0 0 1 3-3h9" stroke-dasharray="2.5 2"/>',
  espelhar: '<path d="M12 3v18" stroke-dasharray="2.5 2"/><path d="M9 7 4 17h5zM15 7l5 10h-5z"/>',
  padrao_linear: '<circle cx="5" cy="12" r="2.4"/><circle cx="12" cy="12" r="2.4"/><circle cx="19" cy="12" r="2.4"/><path d="M5 18h14" stroke-dasharray="1.5 2"/>',
  padrao_circular: '<circle cx="12" cy="12" r="7" stroke-dasharray="1.5 2"/><circle cx="12" cy="5" r="2"/><circle cx="18" cy="15.5" r="2"/><circle cx="6" cy="15.5" r="2"/>',
  rasgo: '<path d="M8 7h8a5 5 0 0 1 0 10H8A5 5 0 0 1 8 7z"/><path d="M8 12h8" stroke-dasharray="1.5 2"/><circle cx="8" cy="12" r="1.3"/><circle cx="16" cy="12" r="1.3"/>',
  poligono: '<path d="M12 3.5 19.4 7.8v8.4L12 20.5 4.6 16.2V7.8z"/><circle cx="12" cy="12" r="1.3"/><path d="M12 12l7.4-4.2" stroke-dasharray="1.5 2"/>',
  transformar: '<path d="M12 3v9M12 3 9.5 5.5M12 3l2.5 2.5M3 12h9M3 12l2.5-2.5M3 12l2.5 2.5"/><path d="M14.5 20.5a6.5 6.5 0 0 0 6-6"/><path d="m20.5 14.5-2.2 1.4M20.5 14.5l1.2 2.3"/>',
  medir: '<path d="M3 16 16 3l5 5L8 21z"/><path d="M7.5 11.5l2 2M10.5 8.5l2 2M13.5 5.5l2 2"/>',
  unir: '<path d="M4 4h10v6h6v10H10v-6H4z"/><path d="M10 10h4v4h-4z" stroke-dasharray="1.5 1.5"/>',
  analise: '<circle cx="12" cy="12" r="6.5"/><path d="M12 2.5v5M12 16.5v5M2.5 12h5M16.5 12h5"/><circle cx="12" cy="12" r="1.6" fill="currentColor"/>',
}
const esIcone = (nome) => `<svg class="icone" viewBox="0 0 24 24" aria-hidden="true">${ES_ICONES[nome] ?? ""}</svg>`
const ES_GRUPOS = {
  ret: ["retangulo", "retangulo_centro"],
  arco: ["arco", "arco_tangente"],
  forma: ["rasgo", "poligono"],
  aparar: ["aparar", "estender", "dividir"],
  canto: ["filete", "chanfro"],
  deslocar: ["deslocar", "transformar"],
  padrao: ["padrao_linear", "padrao_circular"],
  cota: ["cota", "medir"],
}
// As ferramentas que editam o que já está desenhado (e não desenham curva nova do zero).
const ES_EDICAO = new Set([
  "aparar",
  "estender",
  "dividir",
  "filete",
  "chanfro",
  "deslocar",
  "transformar",
  "espelhar",
  "padrao_linear",
  "padrao_circular",
])
// As que escolhem itens (como a cota) em vez de desenhar.
const ES_ESCOLHA = new Set(["cota", "medir", "analise"])

const ES_ESTADOS = new WeakMap()
const ES_PERTO_PX = 7
const ES_ENCAIXE_PX = 11
const ES_INFERE_GRAUS = 3
const ES_INFERE_PERTO_PX = 120 // paralela e perpendicular só com linha a até isso do traço
const ES_ARRASTO_PX = 3
const ES_DUPLO_MS = 450
const ES_TEMPO_DO_AVISO_MS = 5000

const esCopiar = (v) => JSON.parse(JSON.stringify(v))
const esNum = (v, casas = 4) => (Number.isFinite(v) ? String(Number(v.toFixed(casas))).replace(".", ",") : "—")
const esNumConta = (v) => String(Number(v.toFixed(6)))
const esVazio = () => ({ pontos: { O: [0, 0] }, curvas: [], restricoes: [], cotas: [], variaveis: [] })

const ES_DICAS = {
  selecionar:
    "Clique para escolher (Shift junta). Arraste um ponto ou curva: o desenho se acomoda. Arraste no vazio para pegar vários. Duplo clique numa cota muda a medida.",
  linha: "Clique ponto a ponto. Digite um número para dar o comprimento. Clique no primeiro ponto para fechar; Esc termina.",
  retangulo: "Clique um canto e depois o canto oposto.",
  retangulo_centro: "Clique o centro e depois um canto.",
  circulo: "Clique o centro e depois a borda. Digite um número para dar o diâmetro.",
  arco: "Clique o início, o fim e depois um ponto do arco.",
  arco_tangente: "Comece na ponta de uma linha ou de um arco: o arco sai tangente a ela.",
  ponto: "Clique onde o ponto fica.",
  cota: "Clique uma curva (comprimento, diâmetro, raio), ou dois pontos ou curvas, e depois onde a cota fica.",
  aparar: "Clique no trecho que sai: ele some até os cortes com as outras curvas. Para juntar dois contornos que se cruzam, apare os dois lados.",
  estender: "Clique perto da ponta da linha: ela anda até a primeira curva no caminho.",
  dividir: "Clique onde a curva se parte em duas.",
  filete: "Clique no canto de duas linhas. O raio fica na faixa de baixo (aceita letra).",
  chanfro: "Clique no canto de duas linhas. A distância fica na faixa de baixo (aceita letra).",
  deslocar: "Clique nas curvas (uma fila ligada) e depois no vazio, do lado em que a cópia fica.",
  espelhar: "Clique nas curvas que vão ser espelhadas e depois, com elas escolhidas, na linha do espelho (Shift junta curvas sem espelhar).",
  padrao_linear: "Clique nas curvas que se repetem e depois em Criar, na faixa de baixo.",
  padrao_circular: "Clique nas curvas que se repetem e depois no ponto do centro.",
  rasgo: "Clique o centro de uma ponta, o centro da outra e depois a largura.",
  poligono: "Clique o centro e depois um vértice. O número de lados fica na faixa de baixo.",
  transformar:
    "Clique nas curvas que vão andar (ou escolha antes), ponha quanto andam e giram na faixa de baixo e clique em Aplicar. Ctrl+C e Ctrl+V copiam e colam onde o mouse estiver.",
  medir: "Clique uma curva, ou dois pontos ou curvas: a medida aparece sem virar cota.",
  analise:
    "Clique num canto, na borda de um furo ou numa linha: o ponto ganha um nome (A, B…) e fica preso ali. No Montador, as tensões também são conferidas nele. Clique num ponto que já existe para trocar o nome.",
}
const ES_SINAIS = {
  horizontal: "H",
  vertical: "V",
  paralela: "∥",
  perpendicular: "⊥",
  tangente: "T",
  igual: "=",
  na_curva: "•",
  ponto_medio: "M",
  fixo: "F",
  coincidente: "J",
  concentrico: "◎",
  simetrico: "S",
}
const ES_NOMES_DAS_RESTRICOES = {
  coincidente: "Juntos",
  horizontal: "Horizontal",
  vertical: "Vertical",
  paralela: "Paralelas",
  perpendicular: "Perpendiculares",
  tangente: "Tangentes",
  igual: "Iguais",
  ponto_medio: "No meio",
  concentrico: "Mesmo centro",
  simetrico: "Simétricos",
  fixo: "Fixo",
  na_curva: "Ponto na curva",
}
const ES_PEDE = {
  coincidente: "dois pontos, ou um ponto e uma curva",
  horizontal: "uma linha, ou dois pontos",
  vertical: "uma linha, ou dois pontos",
  paralela: "duas linhas",
  perpendicular: "duas linhas",
  tangente: "uma linha e um arco ou círculo, ou dois arcos",
  igual: "duas linhas, ou dois círculos e arcos",
  ponto_medio: "um ponto e uma linha",
  concentrico: "dois círculos ou arcos",
  simetrico: "dois pontos e a linha do espelho",
  fixo: "um ponto",
}

const ES_TITULOS = {
  retangulo: "Retângulo pelo canto (R): um canto e o canto oposto.",
  retangulo_centro: "Retângulo pelo centro (Shift+R): o centro e um canto.",
  arco: "Arco por 3 pontos (A): início, fim e um ponto do arco.",
  arco_tangente: "Arco tangente (T): comece na ponta de uma linha ou de um arco; ele sai tangente a ela.",
  aparar: "Aparar (X): clique no trecho que sai; ele vai até os cortes com as outras curvas.",
  estender: "Estender (W): clique perto da ponta da linha; ela anda até a primeira curva no caminho.",
  dividir: "Dividir: clique onde a curva se parte em duas.",
  filete: "Filete (G): clique no canto de duas linhas. O raio fica na faixa de baixo, e aceita letra.",
  chanfro: "Chanfro: clique no canto de duas linhas. A distância fica na faixa de baixo, e aceita letra.",
  padrao_linear: "Padrão em fila: escolha as curvas, ponha a quantidade e o passo (aceita letra) e clique em Criar.",
  padrao_circular: "Padrão em círculo: escolha as curvas e clique no ponto do centro.",
  rasgo: "Rasgo (oblongo): o centro de uma ponta, o da outra e a largura. Sai com as tangentes e os raios iguais.",
  poligono: "Polígono regular: o centro e um vértice. Os lados ficam na faixa de baixo.",
  deslocar: "Deslocar, offset (O): escolha as curvas e clique do lado da cópia. A distância fica na faixa de baixo, e aceita letra (espessura t).",
  transformar: "Mover e girar: escolha as curvas, ponha o deslocamento e o giro na faixa de baixo e clique em Aplicar (com ou sem cópia).",
  cota: "Cota (D): uma curva, ou dois pontos ou curvas, e depois onde a cota fica. A medida aceita número, letra ou conta: 25, d, 2*d, L/2-10.",
  medir: "Medir: clique uma curva, ou dois pontos ou curvas. Mostra a medida sem criar cota.",
}

function esCriar(raiz) {
  const caixa = raiz.querySelector(".es")
  const svg = raiz.querySelector("svg")
  const area = raiz.querySelector(".es-area")
  const caixaSituacao = raiz.querySelector("[data-situacao]")
  const caixaLetras = raiz.querySelector("[data-letras]")
  const caixaSelecao = raiz.querySelector("[data-selecao]")
  const caixaOpcoes = raiz.querySelector("[data-opcoes]")
  const infoXY = raiz.querySelector('[data-i="xy"]')
  const infoDica = raiz.querySelector('[data-i="dica"]')
  const chaveSinais = raiz.querySelector('[data-c="sinais"]')
  const chaveGrade = raiz.querySelector('[data-c="grade"]')
  const seletorPasso = raiz.querySelector('[data-c="passo"]')

  const e = {
    enviar: null,
    versao: -1,
    verAjuste: null,
    esboco: esVazio(),
    sistema: null,
    graus: null,
    vista: { cx: 0, cy: 0, esc: 3 },
    ferramenta: "selecionar",
    sel: new Set(),
    perto: null,
    gesto: null,
    desenho: null,
    picks: [],
    mouse: null,
    encaixe: null,
    passado: [],
    futuro: [],
    mensagem: null,
    construcao: false,
    problemas: [],
    marcas: null,
    espaco: false,
    abrirNoSoltar: null, // a cota cuja caixinha abre quando o botão do mouse sobe
    renomearNoSoltar: null, // o ponto de análise cujo nome abre quando o botão do mouse sobe
    ultimaAnalise: null, // para o duplo clique que troca o nome
    ultimaCota: null,
    ultimaCurva: null, // para o duplo clique que escolhe o contorno inteiro
    cotaEditando: null, // a cota da caixinha aberta: Tab vai para a próxima
    recorte: null, // o que Ctrl+C guardou
    medida: null, // o que a ferramenta Medir achou: { base, texto }
    conflito: null, // a mudança que não fechou: { tentativa, origens }
    // Os campos das ferramentas de edição: texto, para aceitar letra e conta.
    opcoes: {
      raio: "5",
      chanfro: "5",
      distancia: "3",
      quantos: "4",
      passo: "20",
      direcao: "h",
      quantosCirc: "6",
      angulo: "360",
      lados: "6",
      dx: "0",
      dy: "0",
      giro: "90",
      copiar: false,
      centroGiro: "meio",
    },
  }

  // ---- vista ------------------------------------------------------------------------------------
  const tela = () => {
    const r = svg.getBoundingClientRect()
    return { w: r.width || 800, h: r.height || 600 }
  }
  const px = (x, y) => {
    const { w, h } = tela()
    return [w / 2 + (x - e.vista.cx) * e.vista.esc, h / 2 - (y - e.vista.cy) * e.vista.esc]
  }
  const doPx = (u, v) => {
    const { w, h } = tela()
    return [e.vista.cx + (u - w / 2) / e.vista.esc, e.vista.cy - (v - h / 2) / e.vista.esc]
  }
  const doMouse = (ev) => {
    const r = svg.getBoundingClientRect()
    return [ev.clientX - r.left, ev.clientY - r.top]
  }
  const P = (id) => e.esboco.pontos[id]
  const curva = (id) => e.esboco.curvas.find((c) => c.id === id)

  function enquadrar() {
    const xs = []
    const ys = []
    for (const [x, y] of Object.values(e.esboco.pontos)) {
      xs.push(x)
      ys.push(y)
    }
    for (const c of e.esboco.curvas) {
      if (c.tipo === "circulo") {
        const [cx, cy] = P(c.pontos[0])
        xs.push(cx - c.raio, cx + c.raio)
        ys.push(cy - c.raio, cy + c.raio)
      } else if (c.tipo === "arco") {
        const a = esArcoInfo(e.esboco, c)
        xs.push(a.cx - a.r, a.cx + a.r)
        ys.push(a.cy - a.r, a.cy + a.r)
      }
    }
    const { w, h } = tela()
    const largura = Math.max(Math.max(...xs) - Math.min(...xs), 1)
    const altura = Math.max(Math.max(...ys) - Math.min(...ys), 1)
    if (xs.length <= 1) {
      e.vista = { cx: 0, cy: 0, esc: 3 }
    } else {
      e.vista.esc = Math.min((w * 0.8) / largura, (h * 0.8) / altura, 40)
      e.vista.cx = (Math.max(...xs) + Math.min(...xs)) / 2
      e.vista.cy = (Math.max(...ys) + Math.min(...ys)) / 2
    }
    desenhar()
  }

  // ---- ids e cópias -----------------------------------------------------------------------------
  function novoId(prefixo, ids) {
    let maior = 0
    for (const id of ids) {
      const m = new RegExp(`^${prefixo}(\\d+)$`).exec(id)
      if (m) maior = Math.max(maior, Number(m[1]))
    }
    return `${prefixo}${maior + 1}`
  }
  const idPonto = (esb) => novoId("p", Object.keys(esb.pontos))
  const idCurva = (esb) => novoId("c", esb.curvas.map((c) => c.id))
  const idRestricao = (esb) => novoId("r", esb.restricoes.map((r) => r.id))
  const idCota = (esb) => novoId("d", esb.cotas.map((c) => c.id))

  function atualizarSistema() {
    try {
      e.sistema = esSistema(esCopiar(e.esboco))
      e.graus = esGraus(e.sistema, e.sistema.q0)
    } catch (erro) {
      e.sistema = null
      e.graus = null
      avisar(erro.message, "ruim")
    }
  }

  function avisar(texto, tipo = "aviso") {
    e.mensagem = texto ? { texto, tipo } : null
    // Também em cima do desenho, por uns segundos: a faixa de baixo fica fora da vista.
    const caixaAviso = raiz.querySelector("[data-aviso]")
    if (!caixaAviso) return
    clearTimeout(e.tempoDoAviso)
    if (!texto) {
      caixaAviso.hidden = true
      return
    }
    caixaAviso.textContent = texto
    caixaAviso.classList.toggle("ruim", tipo === "ruim")
    caixaAviso.hidden = false
    e.tempoDoAviso = setTimeout(() => {
      caixaAviso.hidden = true
    }, ES_TEMPO_DO_AVISO_MS)
  }

  // ---- histórico e envio ------------------------------------------------------------------------
  function guardar(foto = JSON.stringify(e.esboco)) {
    e.passado.push(foto)
    if (e.passado.length > 200) e.passado.shift()
    e.futuro = []
  }
  function desfazer() {
    if (!e.passado.length) return
    e.conflito = null
    e.futuro.push(JSON.stringify(e.esboco))
    e.esboco = JSON.parse(e.passado.pop())
    depoisDeMudar()
  }
  function refazer() {
    if (!e.futuro.length) return
    e.passado.push(JSON.stringify(e.esboco))
    e.esboco = JSON.parse(e.futuro.pop())
    depoisDeMudar()
  }
  function depoisDeMudar() {
    e.conflito = null
    edReatarAnalises(e.esboco) // o lugar de cada ponto de análise, para a próxima edição
    e.sel = new Set([...e.sel].filter(existe))
    atualizarSistema()
    enviar()
  }
  function enviar() {
    e.versao += 1
    e.enviar?.("edicao", { esboco: esCopiar(e.esboco), versao: e.versao })
    montarPainel()
    desenhar()
  }
  function existe(chave) {
    const [tipo, id] = [chave[0], chave.slice(2)]
    if (tipo === "p") return id in e.esboco.pontos
    if (tipo === "c") return e.esboco.curvas.some((c) => c.id === id)
    if (tipo === "r") return e.esboco.restricoes.some((r) => r.id === id)
    if (tipo === "d") return e.esboco.cotas.some((c) => c.id === id)
    if (tipo === "a") return (e.esboco.analises ?? []).some((a) => a.id === id)
    return false
  }

  // Tenta o esboço novo: resolve a partir do desenho de agora. Devolve o motivo, ou "" se entrou.
  function tentar(novo, { guardarAntes = true } = {}) {
    edReatarAnalises(novo)
    let s
    try {
      s = esSistema(esCopiar(novo))
    } catch (erro) {
      return erro.message
    }
    const r = esResolver(s, {}, { alvosIniciais: esAlvosAtuais(s, s.q0) })
    // Fechar encolhendo uma curva até sumir (deitada e em pé na mesma linha, por exemplo) não vale:
    // é a conta achando a única saída degenerada. Vira conflito, com quem prende a curva.
    const sumiram = r.convergiu ? curvasQueSumiram(novo, esComQ(s, r.q)) : []
    if (sumiram.length) {
      const tocam = (x) =>
        (x.curvas ?? []).some((c) => sumiram.includes(c)) ||
        (x.pontos ?? []).some((p) => novo.curvas.some((c) => sumiram.includes(c.id) && c.pontos.includes(p)))
      const origens = [...novo.restricoes.filter(tocam), ...novo.cotas.filter((c) => !c.referencia && tocam(c))].map((x) => x.id)
      e.conflito = origens.length ? { tentativa: esCopiar(novo), origens } : null
      setTimeout(() => {
        montarPainel()
        desenhar()
      }, 0)
      const nomes = origens.slice(0, 3).map((id) => descrever(novo, id))
      return `Assim uma curva some (fica com tamanho zero)${nomes.length ? `: ${nomes.join(", ")} brigam` : ""}. Apague uma restrição ou deixe uma cota só medindo.`
    }
    if (!r.convergiu) {
      const conflitos = esConflitos(s, r.q)
      // Quem briga fica marcado no desenho, com o jeito de sair: apagar a restrição ou deixar a cota
      // só medindo. A mudança tentada fica guardada para ser refeita sem quem briga.
      const origens = conflitos.filter((id) => novo.restricoes.some((x) => x.id === id) || novo.cotas.some((x) => x.id === id && !x.referencia))
      e.conflito = origens.length ? { tentativa: esCopiar(novo), origens } : null
      setTimeout(() => {
        montarPainel()
        desenhar()
      }, 0)
      return mensagemDeConflito(novo, conflitos)
    }
    e.conflito = null
    if (guardarAntes) guardar()
    e.esboco = esComQ(s, r.q)
    depoisDeMudar()
    return ""
  }
  // Refaz a mudança que não fechou, sem quem brigava: a cota vira referência ou a restrição sai.
  function resolverConflito(id, como) {
    const c = e.conflito
    if (!c) return
    const novo = esCopiar(c.tentativa)
    if (como === "referencia") {
      const cota = novo.cotas.find((x) => x.id === id)
      if (cota) cota.referencia = true
    } else novo.restricoes = novo.restricoes.filter((x) => x.id !== id)
    editor.fechar()
    const erro = tentar(novo)
    avisar(erro, "ruim")
  }
  // As curvas de aço que tinham tamanho em `antes` e ficaram com tamanho zero em `depois`.
  function curvasQueSumiram(antes, depois) {
    const tam = esTamanho(antes)
    const tamanhoDe = (esb, c) => {
      if (c.tipo === "circulo") return c.raio
      const [a, b] = (c.tipo === "linha" ? c.pontos : c.pontos.slice(0, 2)).map((p) => esb.pontos[p])
      return a && b ? Math.hypot(b[0] - a[0], b[1] - a[1]) : 1
    }
    const porId = new Map(antes.curvas.map((c) => [c.id, c]))
    return depois.curvas
      .filter((c) => {
        const velha = porId.get(c.id)
        return velha && tamanhoDe(depois, c) < 1e-6 * tam && tamanhoDe(antes, velha) >= 1e-6 * tam
      })
      .map((c) => c.id)
  }
  function grausDe(esb) {
    try {
      const s = esSistema(esCopiar(esb))
      return esGraus(s, s.q0).livres
    } catch {
      return null
    }
  }
  function descrever(esb, origem) {
    const r = esb.restricoes.find((x) => x.id === origem)
    if (r) return `“${ES_NOMES_DAS_RESTRICOES[r.tipo] ?? r.tipo}”`
    const c = esb.cotas.find((x) => x.id === origem)
    if (c) return `a cota ${c.expressao.replace(".", ",")}`
    return "o arco"
  }
  function mensagemDeConflito(esb, conflitos) {
    const nomes = conflitos.filter((c) => c !== "origem").slice(0, 3).map((c) => descrever(esb, c))
    if (!nomes.length) return "Assim o esboço não fecha."
    return `Não cabe: ${nomes.join(", ")} brigam com o que já está preso. Mude uma medida ou apague uma restrição.`
  }

  // ---- geometria --------------------------------------------------------------------------------
  function pontoNoArco(info, ang) {
    let d = (ang - info.ta) % (2 * Math.PI)
    if (d < 0) d += 2 * Math.PI
    return d <= info.sw + 1e-9
  }
  // Distância na tela, em px, do mouse (u, v) até a curva.
  function distCurvaPx(c, u, v) {
    if (c.tipo === "linha") {
      const [ax, ay] = px(...P(c.pontos[0]))
      const [bx, by] = px(...P(c.pontos[1]))
      const dx = bx - ax
      const dy = by - ay
      const l2 = dx * dx + dy * dy || 1
      const t = Math.min(Math.max(((u - ax) * dx + (v - ay) * dy) / l2, 0), 1)
      return Math.hypot(u - ax - t * dx, v - ay - t * dy)
    }
    const [x, y] = doPx(u, v)
    if (c.tipo === "circulo") {
      const [cx, cy] = P(c.pontos[0])
      return Math.abs(Math.hypot(x - cx, y - cy) - c.raio) * e.vista.esc
    }
    const info = esArcoInfo(e.esboco, c)
    if (pontoNoArco(info, Math.atan2(y - info.cy, x - info.cx))) {
      return Math.abs(Math.hypot(x - info.cx, y - info.cy) - info.r) * e.vista.esc
    }
    const [ax, ay] = px(...P(c.pontos[1]))
    const [bx, by] = px(...P(c.pontos[2]))
    return Math.min(Math.hypot(u - ax, v - ay), Math.hypot(u - bx, v - by))
  }
  // O ponto da curva mais perto de (x, y), no mundo.
  function projetar(c, x, y) {
    if (c.tipo === "linha") {
      const [ax, ay] = P(c.pontos[0])
      const [bx, by] = P(c.pontos[1])
      const dx = bx - ax
      const dy = by - ay
      const t = Math.min(Math.max(((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy || 1), 0), 1)
      return [ax + t * dx, ay + t * dy]
    }
    const [cx, cy] = c.tipo === "circulo" ? P(c.pontos[0]) : P(c.pontos[0])
    const r = c.tipo === "circulo" ? c.raio : esArcoInfo(e.esboco, c).r
    const a = Math.atan2(y - cy, x - cx)
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)]
  }
  function meioDaCurva(c) {
    if (c.tipo === "linha") {
      const [ax, ay] = P(c.pontos[0])
      const [bx, by] = P(c.pontos[1])
      return [(ax + bx) / 2, (ay + by) / 2]
    }
    if (c.tipo === "circulo") {
      const [cx, cy] = P(c.pontos[0])
      return [cx + c.raio * Math.cos(Math.PI / 4), cy + c.raio * Math.sin(Math.PI / 4)]
    }
    const info = esArcoInfo(e.esboco, c)
    const a = info.ta + info.sw / 2
    return [info.cx + info.r * Math.cos(a), info.cy + info.r * Math.sin(a)]
  }
  const usado = (pid) =>
    e.esboco.curvas.some((c) => c.pontos.includes(pid)) ||
    e.esboco.restricoes.some((r) => (r.pontos ?? []).includes(pid)) ||
    e.esboco.cotas.some((c) => (c.pontos ?? []).includes(pid))

  // O que está debaixo do mouse: ponto, curva (ou nada). Pontos primeiro.
  function oQueTemAqui(u, v, fora = new Set()) {
    let melhor = null
    let dist = ES_PERTO_PX
    for (const [pid, [x, y]] of Object.entries(e.esboco.pontos)) {
      if (fora.has(`p:${pid}`)) continue
      const [a, b] = px(x, y)
      const d = Math.hypot(a - u, b - v)
      if (d <= dist) {
        dist = d
        melhor = `p:${pid}`
      }
    }
    if (melhor) return melhor
    dist = ES_PERTO_PX
    for (const c of e.esboco.curvas) {
      if (fora.has(`c:${c.id}`)) continue
      const d = distCurvaPx(c, u, v)
      if (d <= dist) {
        dist = d
        melhor = `c:${c.id}`
      }
    }
    return melhor
  }

  // Encaixe ao desenhar: ponto que existe, meio de linha, sobre a curva, alinhado com outro ponto,
  // grade. Devolve { x, y, ponto?, meio?, curva?, guiaX?, guiaY? }.
  function encaixar(u, v, fora = new Set()) {
    let [x, y] = doPx(u, v)
    let melhor = null
    let dist = ES_ENCAIXE_PX
    for (const [pid, [a, b]] of Object.entries(e.esboco.pontos)) {
      if (fora.has(pid)) continue
      const [pu, pv] = px(a, b)
      const d = Math.hypot(pu - u, pv - v)
      if (d < dist) {
        dist = d
        melhor = { x: a, y: b, ponto: pid }
      }
    }
    if (melhor) return melhor
    for (const c of e.esboco.curvas) {
      if (c.tipo !== "linha" || c.pontos.some((p) => fora.has(p))) continue
      const [mx, my] = meioDaCurva(c)
      const [pu, pv] = px(mx, my)
      const d = Math.hypot(pu - u, pv - v)
      if (d < dist) {
        dist = d
        melhor = { x: mx, y: my, meio: c.id }
      }
    }
    if (melhor) return melhor
    dist = ES_PERTO_PX
    for (const c of e.esboco.curvas) {
      if (c.pontos.some((p) => fora.has(p))) continue
      const d = distCurvaPx(c, u, v)
      if (d < dist) {
        dist = d
        const [a, b] = projetar(c, x, y)
        melhor = { x: a, y: b, curva: c.id }
      }
    }
    if (melhor) return melhor
    const saida = { x, y }
    if (chaveGrade.checked) {
      const passo = Number(seletorPasso.value)
      saida.x = Math.round(x / passo) * passo
      saida.y = Math.round(y / passo) * passo
    }
    let melhorX = ES_ENCAIXE_PX
    let melhorY = ES_ENCAIXE_PX
    for (const [pid, [a, b]] of Object.entries(e.esboco.pontos)) {
      if (fora.has(pid)) continue
      const [pu, pv] = px(a, b)
      if (Math.abs(pu - u) < melhorX) {
        melhorX = Math.abs(pu - u)
        saida.x = a
        saida.guiaX = pid
      }
      if (Math.abs(pv - v) < melhorY) {
        melhorY = Math.abs(pv - v)
        saida.y = b
        saida.guiaY = pid
      }
    }
    return saida
  }

  // O ponto do encaixe dentro de `esb`: o que já existe, ou um novo preso onde caiu.
  function pontoDoEncaixe(esb, enc) {
    if (enc.ponto) return enc.ponto
    const pid = idPonto(esb)
    esb.pontos[pid] = [enc.x, enc.y]
    if (enc.meio) {
      esb.restricoes.push({ id: idRestricao(esb), tipo: "ponto_medio", pontos: [pid], curvas: [enc.meio] })
    } else if (enc.curva) {
      esb.restricoes.push({ id: idRestricao(esb), tipo: "na_curva", pontos: [pid], curvas: [enc.curva] })
    }
    return pid
  }
  function novaCurva(esb, tipo, pontos, extra = {}) {
    const c = { id: idCurva(esb), tipo, pontos, ...extra }
    if (e.construcao) c.construcao = true
    esb.curvas.push(c)
    return c.id
  }
  function novaRestricao(esb, tipo, campos) {
    const r = { id: idRestricao(esb), tipo, ...campos }
    esb.restricoes.push(r)
    return r.id
  }

  // ---- desenhar à mão ---------------------------------------------------------------------------
  // A direção que a linha nova "quer" ter, como no CAD: deitada, em pé, tangente ao arco de onde
  // sai, perpendicular à linha de onde sai, ou paralela ou perpendicular a outra linha do desenho.
  // Devolve { dir: [dx, dy] unitário, restricao, com } (com = a curva de referência), ou null.
  function direcaoInferida(de, x, y) {
    const [x0, y0] = P(de)
    const dx = x - x0
    const dy = y - y0
    const l = Math.hypot(dx, dy)
    if (l * e.vista.esc < 10) return null
    const ang = Math.atan2(dy, dx)
    const graus = (Math.abs(ang) * 180) / Math.PI
    if (graus < ES_INFERE_GRAUS || graus > 180 - ES_INFERE_GRAUS) return { dir: [Math.sign(dx) || 1, 0], restricao: "horizontal" }
    if (Math.abs(graus - 90) < ES_INFERE_GRAUS) return { dir: [0, Math.sign(dy) || 1], restricao: "vertical" }
    const perto = (alvo) => {
      // a diferença de ângulo entre a direção do mouse e a reta `alvo` (sem sentido), em graus
      let d = Math.abs(((ang - alvo) % Math.PI) + Math.PI) % Math.PI
      d = Math.min(d, Math.PI - d)
      return (d * 180) / Math.PI
    }
    const naReta = (alvo) => {
      const u = [Math.cos(alvo), Math.sin(alvo)]
      const s = dx * u[0] + dy * u[1] >= 0 ? 1 : -1
      return [s * u[0], s * u[1]]
    }
    const candidatos = []
    // Saindo da ponta de um arco: a tangente dele ali. Saindo da ponta de uma linha: a perpendicular.
    for (const c of e.esboco.curvas) {
      if (c.construcao || c.tipo === "circulo" || !esPontas(c).includes(de)) continue
      if (c.tipo === "arco") {
        const [cx, cy] = P(c.pontos[0])
        const alvo = Math.atan2(y0 - cy, x0 - cx) + Math.PI / 2
        candidatos.push({ alvo, restricao: "tangente", com: c.id, peso: 0 })
      } else {
        const [a, b] = c.pontos.map(P)
        const alvo = Math.atan2(b[1] - a[1], b[0] - a[0]) + Math.PI / 2
        candidatos.push({ alvo, restricao: "perpendicular", com: c.id, peso: 0 })
      }
    }
    // As outras linhas: paralela ou perpendicular, só as de perto do traço (como num CAD, a linha
    // do outro lado do desenho não prende nada). As mais perto ganham no empate.
    const ateLinha = (a, b, p) => {
      const ux = b[0] - a[0]
      const uy = b[1] - a[1]
      const t = Math.min(Math.max(((p[0] - a[0]) * ux + (p[1] - a[1]) * uy) / (ux * ux + uy * uy || 1), 0), 1)
      return Math.hypot(a[0] + t * ux - p[0], a[1] + t * uy - p[1]) * e.vista.esc
    }
    for (const c of e.esboco.curvas) {
      if (c.tipo !== "linha" || c.pontos.includes(de)) continue
      const [a, b] = c.pontos.map(P)
      const base = Math.atan2(b[1] - a[1], b[0] - a[0])
      const horizontal = Math.abs(Math.sin(base)) < 1e-9 || Math.abs(Math.cos(base)) < 1e-9
      if (horizontal) continue // deitada e em pé já foram vistas
      const longe = Math.min(ateLinha(a, b, [x0, y0]), ateLinha(a, b, [x, y]))
      if (longe > ES_INFERE_PERTO_PX) continue
      candidatos.push({ alvo: base, restricao: "paralela", com: c.id, peso: longe })
      candidatos.push({ alvo: base + Math.PI / 2, restricao: "perpendicular", com: c.id, peso: longe })
    }
    let melhor = null
    for (const k of candidatos) {
      const d = perto(k.alvo)
      if (d >= ES_INFERE_GRAUS) continue
      if (!melhor || d + k.peso * 0.01 < melhor.d + melhor.peso * 0.01) melhor = { ...k, d }
    }
    if (!melhor) return null
    return { dir: naReta(melhor.alvo), restricao: melhor.restricao, com: melhor.com }
  }
  function inferirDirecao(de, enc) {
    if (enc.ponto) return { enc, restricao: null }
    const inferida = direcaoInferida(de, enc.x, enc.y)
    if (!inferida) return { enc, restricao: null }
    const [x0, y0] = P(de)
    const L = (enc.x - x0) * inferida.dir[0] + (enc.y - y0) * inferida.dir[1]
    const certo = { ...enc, x: x0 + L * inferida.dir[0], y: y0 + L * inferida.dir[1], curva: undefined, meio: undefined }
    return { enc: certo, restricao: inferida.restricao, com: inferida.com ?? null }
  }
  // A restrição inferida na linha nova `cid` (que vai de `de` até a ponta).
  function prenderInferida(novo, cid, restricao, com) {
    if (!restricao) return
    if (!com) return novaRestricao(novo, restricao, { curvas: [cid] })
    if (restricao === "tangente") {
      const arco = novo.curvas.find((c) => c.id === com)
      const linha = novo.curvas.find((c) => c.id === cid)
      const [cx, cy] = novo.pontos[arco.pontos[0]]
      const [a, b] = linha.pontos.map((p) => novo.pontos[p])
      const lado = esDistSinal(cx, cy, a[0], a[1], b[0], b[1]) >= 0 ? 1 : -1
      return novaRestricao(novo, "tangente", { curvas: [cid, com], valores: [lado] })
    }
    return novaRestricao(novo, restricao, { curvas: [com, cid] })
  }

  function cliqueDeDesenho(u, v) {
    const f = e.ferramenta
    const d = e.desenho
    if (f === "ponto") {
      const enc = encaixar(u, v)
      if (enc.ponto) return
      const novo = esCopiar(e.esboco)
      pontoDoEncaixe(novo, enc)
      tentarOuAvisar(novo)
      return
    }
    if (f === "linha") {
      if (!d) {
        const novo = esCopiar(e.esboco)
        const enc = encaixar(u, v)
        const pid = pontoDoEncaixe(novo, enc)
        if (!enc.ponto) {
          const erro = tentar(novo)
          if (erro) return avisar(erro, "ruim")
        }
        e.desenho = { tipo: "linha", de: pid, primeiro: pid }
        return
      }
      const novo = esCopiar(e.esboco)
      const bruto = encaixar(u, v, new Set([d.de]))
      const { enc, restricao, com } = inferirDirecao(d.de, bruto)
      const ate = pontoDoEncaixe(novo, enc)
      if (ate === d.de) return
      const cid = novaCurva(novo, "linha", [d.de, ate])
      prenderInferida(novo, cid, restricao, com)
      const erro = tentar(novo)
      if (erro) return avisar(erro, "ruim")
      if (ate === d.primeiro || (enc.ponto && enc.ponto !== d.de && ehPonta(ate, cid))) {
        e.desenho = null
        return
      }
      e.desenho = { ...d, de: ate }
      return
    }
    if (f === "circulo") {
      if (!d) {
        e.desenho = { tipo: "circulo", centro: encaixar(u, v) }
        return
      }
      const [x, y] = doPx(u, v)
      const r = Math.hypot(x - d.centro.x, y - d.centro.y)
      if (r * e.vista.esc < 3) return
      const novo = esCopiar(e.esboco)
      const c = pontoDoEncaixe(novo, d.centro)
      novaCurva(novo, "circulo", [c], { raio: r })
      e.desenho = null
      tentarOuAvisar(novo)
      return
    }
    if (f === "rasgo") {
      if (!d) {
        e.desenho = { tipo: "rasgo", a: encaixar(u, v) }
        return
      }
      if (!d.b) {
        const b = encaixar(u, v)
        if (Math.hypot(b.x - d.a.x, b.y - d.a.y) * e.vista.esc < 3) return
        e.desenho = { ...d, b }
        return
      }
      const r = larguraDoRasgo(d, doPx(u, v))
      if (r * e.vista.esc < 2) return avisar("Afaste o mouse da linha dos centros para dar a largura.", "aviso")
      e.desenho = null
      aplicarEdicao(edRasgo(e.esboco, [d.a.x, d.a.y], [d.b.x, d.b.y], r))
      return
    }
    if (f === "poligono") {
      if (!d) {
        e.desenho = { tipo: "poligono", centro: encaixar(u, v) }
        return
      }
      const fim = encaixar(u, v)
      if (Math.hypot(fim.x - d.centro.x, fim.y - d.centro.y) * e.vista.esc < 3) return
      e.desenho = null
      const lados = String(e.opcoes.lados).replace(",", ".")
      aplicarEdicao(edPoligono(e.esboco, [d.centro.x, d.centro.y], [fim.x, fim.y], lados))
      return
    }
    if (f === "retangulo" || f === "retangulo_centro") {
      if (!d) {
        e.desenho = { tipo: f, a: encaixar(u, v) }
        return
      }
      const b = encaixar(u, v)
      const novo = esCopiar(e.esboco)
      montarRetangulo(novo, d.a, b, f === "retangulo_centro")
      e.desenho = null
      tentarOuAvisar(novo)
      return
    }
    if (f === "arco") {
      if (!d) {
        e.desenho = { tipo: "arco", a: encaixar(u, v) }
        return
      }
      if (!d.b) {
        e.desenho = { ...d, b: encaixar(u, v) }
        return
      }
      const [mx, my] = doPx(u, v)
      const circ = circuloPor3(d.a, d.b, { x: mx, y: my })
      if (!circ) return avisar("Os três pontos estão alinhados: o arco não existe.", "ruim")
      const novo = esCopiar(e.esboco)
      const pa = pontoDoEncaixe(novo, d.a)
      const pb = pontoDoEncaixe(novo, d.b)
      const pc = idPonto(novo)
      novo.pontos[pc] = [circ.cx, circ.cy]
      const ta = Math.atan2(d.a.y - circ.cy, d.a.x - circ.cx)
      const info = { ta, sw: angAnti(ta, Math.atan2(d.b.y - circ.cy, d.b.x - circ.cx)) }
      const passa = pontoNoArco(info, Math.atan2(my - circ.cy, mx - circ.cx))
      novaCurva(novo, "arco", passa ? [pc, pa, pb] : [pc, pb, pa])
      e.desenho = null
      tentarOuAvisar(novo)
      return
    }
    if (f === "arco_tangente") {
      if (!d) {
        const enc = encaixar(u, v)
        const saida = enc.ponto ? direcaoDeSaida(enc.ponto) : null
        if (!saida) return avisar("Comece na ponta de uma linha ou de um arco.", "aviso")
        e.desenho = { tipo: "arco_tangente", de: enc.ponto, ...saida }
        return
      }
      const fim = encaixar(u, v, new Set([d.de]))
      const arco = arcoTangente(d, fim)
      if (!arco) return
      const novo = esCopiar(e.esboco)
      const pfim = pontoDoEncaixe(novo, fim)
      const pc = idPonto(novo)
      novo.pontos[pc] = [arco.cx, arco.cy]
      const cid = novaCurva(novo, "arco", arco.esquerda ? [pc, d.de, pfim] : [pc, pfim, d.de])
      const base = novo.curvas.find((c) => c.id === d.curva)
      const valores =
        base.tipo === "linha"
          ? [Math.sign(esDistSinal(arco.cx, arco.cy, ...P(base.pontos[0]), ...P(base.pontos[1]))) || 1]
          : []
      const campos = { curvas: [d.curva, cid] }
      if (valores.length) campos.valores = valores
      else {
        const ib = esArcoInfo(e.esboco, base)
        const dist = Math.hypot(ib.cx - arco.cx, ib.cy - arco.cy)
        campos.modo = Math.abs(dist - ib.r - arco.r) <= Math.abs(dist - Math.abs(ib.r - arco.r)) ? "externa" : "interna"
        campos.valores = [ib.r >= arco.r ? 1 : -1]
      }
      novaRestricao(novo, "tangente", campos)
      const erro = tentar(novo)
      if (erro) return avisar(erro, "ruim")
      const saida = direcaoDeSaida(pfim, cid)
      e.desenho = saida ? { tipo: "arco_tangente", de: pfim, ...saida } : null
    }
  }
  function tentarOuAvisar(novo) {
    const erro = tentar(novo)
    avisar(erro, "ruim")
  }
  function ehPonta(pid, menos) {
    return e.esboco.curvas.some((c) => c.id !== menos && c.tipo !== "circulo" && esPontas(c).includes(pid))
  }
  const angAnti = (de, para) => {
    let d = (para - de) % (2 * Math.PI)
    if (d < 0) d += 2 * Math.PI
    return d
  }
  function circuloPor3(a, b, c) {
    const d = 2 * (a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y))
    if (Math.abs(d) < 1e-12) return null
    const a2 = a.x * a.x + a.y * a.y
    const b2 = b.x * b.x + b.y * b.y
    const c2 = c.x * c.x + c.y * c.y
    const cx = (a2 * (b.y - c.y) + b2 * (c.y - a.y) + c2 * (a.y - b.y)) / d
    const cy = (a2 * (c.x - b.x) + b2 * (a.x - c.x) + c2 * (b.x - a.x)) / d
    return { cx, cy, r: Math.hypot(a.x - cx, a.y - cy) }
  }
  // A direção em que a curva sai do ponto, para o arco tangente continuar dela.
  function direcaoDeSaida(pid, so = null) {
    const donas = e.esboco.curvas.filter(
      (c) => !c.construcao && c.tipo !== "circulo" && esPontas(c).includes(pid) && (!so || c.id === so),
    )
    if (donas.length !== 1) return null
    const c = donas[0]
    const [x, y] = P(pid)
    if (c.tipo === "linha") {
      const outro = c.pontos[0] === pid ? c.pontos[1] : c.pontos[0]
      const [ox, oy] = P(outro)
      const l = Math.hypot(x - ox, y - oy) || 1
      return { curva: c.id, tx: (x - ox) / l, ty: (y - oy) / l }
    }
    const info = esArcoInfo(e.esboco, c)
    const rx = (x - info.cx) / info.r
    const ry = (y - info.cy) / info.r
    const sinal = c.pontos[2] === pid ? 1 : -1 // no fim, segue anti-horário; no início, volta
    return { curva: c.id, tx: -ry * sinal, ty: rx * sinal }
  }
  function arcoTangente(d, fim) {
    const [x0, y0] = P(d.de)
    const dx = fim.x - x0
    const dy = fim.y - y0
    const h = dx * -d.ty + dy * d.tx // componente para a esquerda da direção de saída
    if (Math.abs(h) * e.vista.esc < 2) return null
    const r = (dx * dx + dy * dy) / (2 * h)
    return { cx: x0 - d.ty * r, cy: y0 + d.tx * r, r: Math.abs(r), esquerda: h > 0 }
  }
  // A meia largura do rasgo: a distância do mouse à linha dos dois centros.
  function larguraDoRasgo(d, mouse) {
    const l = Math.hypot(d.b.x - d.a.x, d.b.y - d.a.y)
    if (!(l > 0)) return 0
    return Math.abs(esDistSinal(mouse[0], mouse[1], d.a.x, d.a.y, d.b.x, d.b.y))
  }
  function contornoDoRasgo(a, b, r) {
    const l = Math.hypot(b.x - a.x, b.y - a.y)
    if (!(l > 0)) return ""
    const n = [(-(b.y - a.y) / l) * r, ((b.x - a.x) / l) * r]
    const [p1, p2, p3, p4] = [
      [a.x + n[0], a.y + n[1]],
      [b.x + n[0], b.y + n[1]],
      [b.x - n[0], b.y - n[1]],
      [a.x - n[0], a.y - n[1]],
    ].map((p) => px(...p))
    const R = r * e.vista.esc
    return `M${p1.join(" ")}L${p2.join(" ")}A${R} ${R} 0 0 1 ${p3.join(" ")}L${p4.join(" ")}A${R} ${R} 0 0 1 ${p1.join(" ")}Z`
  }
  function montarRetangulo(esb, a, b, pelo_centro) {
    let canto1
    let canto2
    if (pelo_centro) {
      canto1 = { x: 2 * a.x - b.x, y: 2 * a.y - b.y }
      canto2 = b
    } else {
      canto1 = a
      canto2 = b
    }
    const p1 = pelo_centro ? pontoDoEncaixe(esb, { x: canto1.x, y: canto1.y }) : pontoDoEncaixe(esb, canto1)
    const p3 = pontoDoEncaixe(esb, canto2)
    const [x1, y1] = esb.pontos[p1]
    const [x3, y3] = esb.pontos[p3]
    const p2 = idPonto(esb)
    esb.pontos[p2] = [x3, y1]
    const p4 = idPonto(esb)
    esb.pontos[p4] = [x1, y3]
    const l1 = novaCurva(esb, "linha", [p1, p2])
    const l2 = novaCurva(esb, "linha", [p2, p3])
    const l3 = novaCurva(esb, "linha", [p3, p4])
    const l4 = novaCurva(esb, "linha", [p4, p1])
    novaRestricao(esb, "horizontal", { curvas: [l1, l3] })
    novaRestricao(esb, "vertical", { curvas: [l2, l4] })
    if (pelo_centro) {
      const diag = idCurva(esb)
      esb.curvas.push({ id: diag, tipo: "linha", pontos: [p1, p3], construcao: true })
      const centro = pontoDoEncaixe(esb, a)
      novaRestricao(esb, "ponto_medio", { pontos: [centro], curvas: [diag] })
    }
  }

  // ---- cotas ------------------------------------------------------------------------------------
  function pontosDaCota(c) {
    if (c.centro) return [c.pontos[0], "CG"]
    if (c.pontos?.length >= 2) return c.pontos.slice(0, 2)
    return curva(c.curvas[0]).pontos.slice(0, 2)
  }
  // O centro de gravidade vem do Python (a seção de agora); "CG" é ele nas cotas que vão até ele.
  const centroXY = () => (e.marcas && Number.isFinite(e.marcas.xc) ? [e.marcas.xc, e.marcas.yc] : null)
  const PC = (id) => {
    if (id !== "CG") return P(id)
    const xy = centroXY()
    if (!xy) throw new Error("O centro de gravidade ainda não foi calculado.")
    return xy
  }
  // Na cota e no Medir, o centro de gravidade também se escolhe: na frente das curvas, atrás dos pontos.
  function comCentro(chave, u, v) {
    if (chave?.startsWith("p:")) return chave
    return pertoDoCentro(u, v) ? "g:CG" : chave
  }
  function pertoDoCentro(u, v) {
    const xy = centroXY()
    if (!xy) return false
    const [a, b] = px(...xy)
    return Math.hypot(a - u, b - v) <= ES_PERTO_PX + 2
  }
  function raioDe(c) {
    return c.tipo === "circulo" ? c.raio : esArcoInfo(e.esboco, c).r
  }
  function anguloDe(l1, l2) {
    const v = [...P(l1.pontos[0]), ...P(l1.pontos[1]), ...P(l2.pontos[0]), ...P(l2.pontos[1])]
    return esAnguloEntre(v)
  }
  function medida(c) {
    if (c.tipo === "distancia") {
      const [a, b] = pontosDaCota(c).map(PC)
      if (c.centro && c.modo === "h") return Math.abs(b[0] - a[0])
      if (c.centro && c.modo === "v") return Math.abs(b[1] - a[1])
      if (c.modo === "h") return (c.sinal || 1) * (b[0] - a[0])
      if (c.modo === "v") return (c.sinal || 1) * (b[1] - a[1])
      return Math.hypot(b[0] - a[0], b[1] - a[1])
    }
    if (c.tipo === "ponto_linha") {
      const l = curva(c.curvas[0])
      return (c.sinal || 1) * esDistSinal(...P(c.pontos[0]), ...P(l.pontos[0]), ...P(l.pontos[1]))
    }
    if (c.tipo === "diametro") return 2 * raioDe(curva(c.curvas[0]))
    if (c.tipo === "raio") return raioDe(curva(c.curvas[0]))
    if (c.tipo === "angulo") {
      return ((c.sinal || 1) * anguloDe(curva(c.curvas[0]), curva(c.curvas[1])) * 180) / Math.PI
    }
    return NaN
  }
  function nomeDaCota(c) {
    if (c.tipo === "distancia") {
      if (c.modo === "h") return "Distância horizontal"
      if (c.modo === "v") return "Distância vertical"
      return c.pontos?.length >= 2 ? "Distância" : "Comprimento"
    }
    return { ponto_linha: "Distância à linha", diametro: "Diâmetro", raio: "Raio", angulo: "Ângulo" }[c.tipo]
  }
  function ehNumero(expressao) {
    try {
      const no = lerConta(expressao)
      return letrasDaConta(no).size === 0
    } catch {
      return false
    }
  }
  function rotuloDaCota(c) {
    const valor = medida(c)
    const prefixo = c.tipo === "diametro" ? "Ø" : c.tipo === "raio" ? "R" : ""
    const fim = c.tipo === "angulo" ? "°" : ""
    if (c.referencia && c.nome) return `(${c.nome} = ${prefixo}${esNum(valor, 2)}${fim})`
    if (c.referencia) return `(${prefixo}${esNum(valor, 2)}${fim})`
    if (ehNumero(c.expressao)) return `${prefixo}${esNum(valor, 3)}${fim}`
    const separa = prefixo ? " " : "" // "R r = 5": o R da cota não gruda na letra
    return `${prefixo}${separa}${c.expressao.replace(/\./g, ",")} = ${esNum(valor, 3)}${fim}`
  }

  // O que a cota mede pelos itens escolhidos, ou null se não serve.
  function cotaDosPicks(picks) {
    if (picks.includes("g:CG")) {
      // Até o centro de gravidade: de um ponto, ou do centro de um furo. Só mede.
      if (picks.length !== 2) return null
      const outro = picks.find((p) => p !== "g:CG")
      if (outro.startsWith("p:")) return { tipo: "distancia", pontos: [outro.slice(2)], centro: true }
      const k = curva(outro.slice(2))
      if (k && k.tipo !== "linha") return { tipo: "distancia", pontos: [k.pontos[0]], centro: true }
      return null
    }
    const pontos = picks.filter((p) => p.startsWith("p:")).map((p) => p.slice(2))
    const curvas = picks.filter((p) => p.startsWith("c:")).map((p) => curva(p.slice(2)))
    const centro = (c) => c.pontos[0]
    if (picks.length === 1 && curvas.length === 1) {
      const c = curvas[0]
      if (c.tipo === "circulo") return { tipo: "diametro", curvas: [c.id] }
      if (c.tipo === "arco") return { tipo: "raio", curvas: [c.id] }
      return { tipo: "distancia", curvas: [c.id], pontos: [...c.pontos] }
    }
    if (picks.length !== 2) return null
    if (pontos.length === 2) return { tipo: "distancia", pontos }
    const linhas = curvas.filter((c) => c.tipo === "linha")
    const redondas = curvas.filter((c) => c.tipo !== "linha")
    if (pontos.length === 1 && linhas.length === 1) return { tipo: "ponto_linha", pontos, curvas: [linhas[0].id] }
    if (pontos.length === 1 && redondas.length === 1) return { tipo: "distancia", pontos: [pontos[0], centro(redondas[0])] }
    if (linhas.length === 2) {
      const ang = anguloDe(linhas[0], linhas[1])
      if (Math.abs(Math.sin(ang)) < 1e-6) {
        return { tipo: "ponto_linha", pontos: [linhas[1].pontos[0]], curvas: [linhas[0].id] }
      }
      return { tipo: "angulo", curvas: [linhas[0].id, linhas[1].id] }
    }
    if (linhas.length === 1 && redondas.length === 1) {
      return { tipo: "ponto_linha", pontos: [centro(redondas[0])], curvas: [linhas[0].id] }
    }
    if (redondas.length === 2) return { tipo: "distancia", pontos: [centro(redondas[0]), centro(redondas[1])] }
    return null
  }
  // O lugar escolhe: em cima ou embaixo, horizontal; ao lado, vertical; na diagonal, direta.
  function modoPeloLugar(a, b, lugar) {
    const [x0, x1] = [Math.min(a[0], b[0]), Math.max(a[0], b[0])]
    const [y0, y1] = [Math.min(a[1], b[1]), Math.max(a[1], b[1])]
    const dentroX = lugar[0] >= x0 && lugar[0] <= x1
    const dentroY = lugar[1] >= y0 && lugar[1] <= y1
    if (Math.abs(a[1] - b[1]) < 1e-9) return "h"
    if (Math.abs(a[0] - b[0]) < 1e-9) return "v"
    if (dentroX && !dentroY) return "h"
    if (dentroY && !dentroX) return "v"
    return "d"
  }
  function cotaCompleta(base, lugar) {
    const c = { ...base, lugar }
    if (c.tipo === "distancia") {
      const [a, b] = pontosDaCota(c).map(PC)
      c.modo = modoPeloLugar(a, b, lugar)
      if (c.modo === "h") c.sinal = b[0] - a[0] >= 0 ? 1 : -1
      if (c.modo === "v") c.sinal = b[1] - a[1] >= 0 ? 1 : -1
    } else if (c.tipo === "ponto_linha") {
      const l = curva(c.curvas[0])
      c.sinal = esDistSinal(...P(c.pontos[0]), ...P(l.pontos[0]), ...P(l.pontos[1])) >= 0 ? 1 : -1
    } else if (c.tipo === "angulo") {
      c.sinal = anguloDe(curva(c.curvas[0]), curva(c.curvas[1])) >= 0 ? 1 : -1
    }
    c.modo = c.modo ?? "d"
    c.sinal = c.sinal ?? 1
    return c
  }
  function porCota(lugar) {
    const base = cotaDosPicks(e.picks)
    if (!base) return
    const novo = esCopiar(e.esboco)
    const c = { id: idCota(novo), expressao: "0", ...cotaCompleta(base, lugar) }
    c.expressao = esNumConta(medida(c))
    if (c.tipo === "distancia" && c.pontos?.length >= 2 && c.pontos[0] === c.pontos[1]) return
    const antes = grausDe(e.esboco)
    novo.cotas.push(c)
    const depois = grausDe(novo)
    let aviso = ""
    if (c.centro) {
      c.referencia = true
      aviso = "A cota até o centro de gravidade só mede. Clique nela duas vezes e em Dar nome: no Montador, ela vira uma medida que sai do desenho."
    } else if (antes !== null && depois !== null && depois >= antes) {
      c.referencia = true
      aviso = "Essa medida já estava presa pelo resto do desenho: ficou como cota de referência, entre parênteses (só mede)."
    }
    guardar()
    e.esboco = novo
    e.picks = []
    depoisDeMudar()
    avisar(aviso, "aviso")
    montarPainel()
    if (!c.referencia) e.abrirNoSoltar = c.id
  }

  function lerCotaDigitada(texto, c) {
    return lerMedida(texto, medida(c), c.tipo === "angulo")
  }
  // O que se digitou numa medida: número (com conta e unidade, como na caixinha) ou conta com letras.
  function lerMedida(texto, atual, angulo = false) {
    const numero = lerValorDigitado(texto, atual, angulo ? "°" : "mm")
    if (!numero.erro) {
      if (!(numero.valor > 0) && !angulo) return { erro: "A medida precisa ser maior que zero." }
      return { valor: { expressao: esNumConta(numero.valor) } }
    }
    let no
    try {
      no = lerConta(texto)
    } catch (erro) {
      return { erro: erro.message }
    }
    const conhecidas = new Set(e.esboco.variaveis.map((v) => v.nome))
    const novas = [...letrasDaConta(no)].filter((l) => !conhecidas.has(l))
    for (const l of novas) if (!nomeValido(l)) return { erro: `“${l}” não serve de letra.` }
    if (novas.length > 1) return { erro: `Crie uma letra de cada vez: ${novas.join(", ")} são novas.` }
    return { valor: { expressao: String(texto).trim().replace(/,/g, "."), novas } }
  }
  function aplicarCota(id, lido) {
    const novo = esCopiar(e.esboco)
    const c = novo.cotas.find((x) => x.id === id)
    const tipoDaLetra = c.tipo === "angulo" ? "angulo" : "comprimento"
    const no = lerConta(lido.expressao)
    for (const l of letrasDaConta(no)) {
      const v = novo.variaveis.find((x) => x.nome === l)
      if (v && (v.tipo ?? "comprimento") !== tipoDaLetra) {
        return `A letra ${l} já é ${v.tipo === "angulo" ? "um ângulo" : "um comprimento"}: use outra.`
      }
    }
    for (const l of lido.novas ?? []) {
      const valores = esValores(novo)
      const v = valorDaLetraNova(no, l, valores, medida(c))
      if (!(v > 0) && tipoDaLetra === "comprimento") return `A letra ${l} sairia com ${esNum(v)}: use outra conta.`
      // Seis casas: o que sobra é a tolerância do solver, não medida.
      novo.variaveis.push({ nome: l, valor: Number(v.toFixed(6)), tipo: tipoDaLetra })
    }
    const valor = avaliarConta(no, esValores(novo))
    if (!Number.isFinite(valor)) return "A conta não dá um número com as letras de agora."
    if (!(valor > 0) && c.tipo !== "angulo") return "A medida precisa dar mais que zero."
    c.expressao = lido.expressao
    c.referencia = false
    delete c.nome // a cota que prende não leva nome: o nome é da medida que só mede
    const erro = tentar(novo)
    if (!erro) avisar("")
    return erro
  }
  function editarCota(id) {
    const c = e.esboco.cotas.find((x) => x.id === id)
    const alvo = svg.querySelector(`[data-cota="${id}"] text`)
    if (!c || !alvo) return
    e.cotaEditando = id
    const acoes = []
    if (!c.centro) {
      acoes.push({
        rotulo: c.referencia ? "Prender" : "Só medir",
        titulo: c.referencia
          ? "A cota passa a prender a medida"
          : "Vira cota de referência: mostra a medida e não prende nada",
        ao: () => {
          const novo = esCopiar(e.esboco)
          const alvoCota = novo.cotas.find((x) => x.id === id)
          alvoCota.referencia = !alvoCota.referencia
          if (!alvoCota.referencia) {
            alvoCota.expressao = esNumConta(medida(alvoCota))
            delete alvoCota.nome // o nome é só da cota que mede
          }
          editor.fechar()
          tentarOuAvisar(novo)
        },
      })
    }
    if (c.referencia && c.tipo !== "angulo") {
      acoes.push({
        rotulo: c.nome ? "Trocar nome" : "Dar nome",
        titulo: "Com nome, a medida vai ao Montador: o bloco Medida do desenho lê o valor dela, que muda junto com as letras",
        ao: () => {
          editor.fechar()
          setTimeout(() => nomearCota(id), 0)
        },
      })
    }
    acoes.push({ rotulo: "Apagar", titulo: "Tira a cota do desenho", ao: () => (editor.fechar(), apagar(new Set([`d:${id}`]))) })
    editor.abrir(alvo, {
      valor: medida(c),
      unidade: c.tipo === "angulo" ? "°" : "mm",
      nome: c.nome ? `${nomeDaCota(c)}: ${c.nome}` : c.centro ? `${nomeDaCota(c)} até o centro de gravidade` : nomeDaCota(c),
      texto: c.referencia ? esNumConta(medida(c)).replace(".", ",") : c.expressao.replace(/\./g, ","),
      dica: c.centro ? "Esta cota só mede: o centro de gravidade sai da seção." : "Número, letra ou conta: 25, d, 2*d, L/2-10",
      selecionarTudo: true,
      ler: (texto) =>
        c.centro && texto.trim() !== esNumConta(medida(c)).replace(".", ",")
          ? { erro: "A cota até o centro de gravidade só mede: ela não prende a medida." }
          : lerCotaDigitada(texto, c),
      // A medida com nome não vira cota que prende só por um Enter: para isso há o Prender.
      aplicar: (lido) => (c.centro || (c.nome && lido.expressao === esNumConta(medida(c))) ? "" : aplicarCota(id, lido)),
      acoes,
    })
  }
  // O nome da cota de referência: no Montador, a medida que sai do desenho (o braço e, por exemplo).
  function nomearCota(id) {
    const c = e.esboco.cotas.find((x) => x.id === id)
    const alvo = svg.querySelector(`[data-cota="${id}"] text`)
    if (!c || !alvo) return
    editor.abrir(alvo, {
      valor: 0,
      unidade: "",
      nome: "Nome da medida",
      texto: c.nome ?? "",
      dica: "Letra ou nome sem espaço: e, braco, d_furo. Vazio tira o nome.",
      selecionarTudo: true,
      ler: (texto) => ({ valor: String(texto).trim() }),
      aplicar: (nome) => {
        if (nome && !nomeValido(nome)) return "O nome começa por letra, sem espaço: e, braco, d_furo."
        if (nome && e.esboco.variaveis.some((v) => v.nome === nome)) return `${nome} já é uma letra das cotas: use outro nome.`
        if (nome && e.esboco.cotas.some((x) => x.id !== id && x.nome === nome)) return `Outra medida já se chama ${nome}.`
        const novo = esCopiar(e.esboco)
        const alvoCota = novo.cotas.find((x) => x.id === id)
        if (nome) alvoCota.nome = nome
        else delete alvoCota.nome
        return tentar(novo)
      },
    })
  }

  // ---- restrições -------------------------------------------------------------------------------
  function juntarPontos(esb, manter, tirar) {
    if (tirar === "O") [manter, tirar] = ["O", manter]
    if (manter === tirar) return
    const trocar = (lista) => (lista ?? []).map((p) => (p === tirar ? manter : p))
    for (const c of esb.curvas) c.pontos = trocar(c.pontos)
    for (const r of esb.restricoes) if (r.pontos) r.pontos = trocar(r.pontos)
    for (const c of esb.cotas) if (c.pontos) c.pontos = trocar(c.pontos)
    delete esb.pontos[tirar]
    esb.curvas = esb.curvas.filter((c) => new Set(c.pontos).size === c.pontos.length)
    limparReferencias(esb)
  }
  function limparReferencias(esb) {
    const curvas = new Set(esb.curvas.map((c) => c.id))
    const ok = (lista, conjunto) => (lista ?? []).every((x) => conjunto.has(x))
    const pontos = new Set(Object.keys(esb.pontos))
    esb.restricoes = esb.restricoes.filter((r) => {
      if (!ok(r.curvas, curvas) || !ok(r.pontos, pontos)) return false
      if ((r.tipo === "coincidente" || r.tipo === "concentrico") && new Set(r.pontos ?? []).size < 2 && r.tipo === "coincidente") return false
      if (r.tipo === "na_curva" || r.tipo === "ponto_medio") {
        const c = esb.curvas.find((x) => x.id === r.curvas[0])
        if (c && c.pontos.includes(r.pontos[0])) return false
      }
      return true
    })
    esb.cotas = esb.cotas.filter((c) => {
      if (!ok(c.curvas, curvas) || !ok(c.pontos, pontos)) return false
      return !(c.pontos?.length === 2 && c.pontos[0] === c.pontos[1])
    })
    const vistas = new Set()
    esb.restricoes = esb.restricoes.filter((r) => {
      const chave = JSON.stringify([r.tipo, r.pontos ?? [], r.curvas ?? []])
      if (vistas.has(chave)) return false
      vistas.add(chave)
      return true
    })
    edReatarAnalises(esb)
  }

  // As curvas ligadas a `cid` pelas pontas (o contorno, ou a fila aberta), da mesma espécie:
  // aço com aço, construção com construção.
  function contornoDe(cid) {
    const inicio = curva(cid)
    if (!inicio) return []
    const mesma = (c) => Boolean(c.construcao) === Boolean(inicio.construcao)
    const pontas = (c) => (c.tipo === "circulo" ? [] : esPontas(c))
    const vistas = new Set([cid])
    const fila = [inicio]
    while (fila.length) {
      const atual = fila.pop()
      for (const p of pontas(atual)) {
        for (const c of e.esboco.curvas) {
          if (vistas.has(c.id) || !mesma(c) || !pontas(c).includes(p)) continue
          vistas.add(c.id)
          fila.push(c)
        }
      }
    }
    return [...vistas]
  }
  function escolhidos(lista = [...e.sel]) {
    const pontos = lista.filter((k) => k.startsWith("p:")).map((k) => k.slice(2))
    const curvas = lista.filter((k) => k.startsWith("c:")).map((k) => curva(k.slice(2))).filter(Boolean)
    return {
      pontos,
      curvas,
      linhas: curvas.filter((c) => c.tipo === "linha"),
      redondas: curvas.filter((c) => c.tipo !== "linha"),
      total: lista.filter((k) => k[0] === "p" || k[0] === "c").length,
    }
  }
  // Monta a restrição pela escolha. Devolve o esboço novo, null (falta escolher) ou uma mensagem.
  function montarRestricao(tipo, lista) {
    const { pontos, curvas, linhas, redondas, total } = escolhidos(lista)
    const novo = esCopiar(e.esboco)
    if (tipo === "coincidente") {
      if (pontos.length >= 2 && total === pontos.length) {
        const manter = pontos.includes("O") ? "O" : pontos[0]
        for (const p of pontos) if (p !== manter) juntarPontos(novo, manter, p)
        return novo
      }
      if (pontos.length === 1 && curvas.length === 1 && total === 2) {
        if (curvas[0].pontos.includes(pontos[0])) return "O ponto já é dessa curva."
        novaRestricao(novo, "na_curva", { pontos, curvas: [curvas[0].id] })
        return novo
      }
      return null
    }
    if (tipo === "horizontal" || tipo === "vertical") {
      if (linhas.length && total === linhas.length) {
        novaRestricao(novo, tipo, { curvas: linhas.map((c) => c.id) })
        return novo
      }
      if (pontos.length === 2 && total === 2) {
        novaRestricao(novo, tipo, { pontos })
        return novo
      }
      return null
    }
    if (tipo === "paralela" || tipo === "perpendicular") {
      const precisa = tipo === "perpendicular" ? linhas.length === 2 : linhas.length >= 2
      if (precisa && total === linhas.length) {
        novaRestricao(novo, tipo, { curvas: linhas.map((c) => c.id) })
        return novo
      }
      return null
    }
    if (tipo === "igual") {
      if ((linhas.length >= 2 && total === linhas.length) || (redondas.length >= 2 && total === redondas.length)) {
        novaRestricao(novo, tipo, { curvas: curvas.map((c) => c.id) })
        return novo
      }
      return null
    }
    if (tipo === "tangente") {
      if (total !== 2) return null
      if (linhas.length === 1 && redondas.length === 1) {
        const l = linhas[0]
        const [cx, cy] = P(redondas[0].pontos[0])
        const lado = esDistSinal(cx, cy, ...P(l.pontos[0]), ...P(l.pontos[1])) >= 0 ? 1 : -1
        novaRestricao(novo, tipo, { curvas: [l.id, redondas[0].id], valores: [lado] })
        return novo
      }
      if (redondas.length === 2) {
        const [a, b] = redondas
        const [ax, ay] = P(a.pontos[0])
        const [bx, by] = P(b.pontos[0])
        const d = Math.hypot(bx - ax, by - ay)
        const ra = raioDe(a)
        const rb = raioDe(b)
        const modo = Math.abs(d - ra - rb) <= Math.abs(d - Math.abs(ra - rb)) ? "externa" : "interna"
        novaRestricao(novo, tipo, { curvas: [a.id, b.id], modo, valores: [ra >= rb ? 1 : -1] })
        return novo
      }
      return null
    }
    if (tipo === "ponto_medio") {
      if (pontos.length === 1 && linhas.length === 1 && total === 2) {
        if (linhas[0].pontos.includes(pontos[0])) return "O ponto é uma ponta da linha."
        novaRestricao(novo, tipo, { pontos, curvas: [linhas[0].id] })
        return novo
      }
      return null
    }
    if (tipo === "concentrico") {
      if (redondas.length >= 2 && total === redondas.length) {
        const centros = redondas.map((c) => c.pontos[0])
        const manter = centros.includes("O") ? "O" : centros[0]
        for (const p of centros) if (p !== manter) juntarPontos(novo, manter, p)
        return novo
      }
      return null
    }
    if (tipo === "simetrico") {
      if (pontos.length === 2 && linhas.length === 1 && total === 3) {
        novaRestricao(novo, tipo, { pontos, curvas: [linhas[0].id] })
        return novo
      }
      return null
    }
    if (tipo === "fixo") {
      if (pontos.length >= 1 && total === pontos.length) {
        for (const p of pontos) novaRestricao(novo, tipo, { pontos: [p], valores: [...P(p)] })
        return novo
      }
      return null
    }
    return null
  }
  function aplicarRestricao(tipo, lista) {
    const novo = montarRestricao(tipo, lista)
    if (novo === null) return false
    if (typeof novo === "string") {
      avisar(novo, "aviso")
      return true
    }
    const antes = grausDe(e.esboco)
    const erro = tentar(novo)
    if (erro) {
      avisar(erro, "ruim")
      return true
    }
    const depois = e.graus?.livres ?? null
    if (antes !== null && depois !== null && depois >= antes && tipo !== "coincidente" && tipo !== "concentrico") {
      e.esboco = JSON.parse(e.passado.pop())
      depoisDeMudar()
      avisar("Isso já estava garantido pelo resto do desenho.", "aviso")
      return true
    }
    avisar("")
    return true
  }
  function botaoDeRestricao(tipo) {
    if (aplicarRestricao(tipo, [...e.sel])) {
      montarPainel()
      desenhar()
      return
    }
    trocarFerramenta(`r:${tipo}`)
    e.picks = []
    avisar(`${ES_NOMES_DAS_RESTRICOES[tipo]}: escolha ${ES_PEDE[tipo]}.`, "aviso")
    montarPainel()
  }

  // ---- apagar e construção ----------------------------------------------------------------------
  function apagar(lista = e.sel) {
    if (!lista.size) return
    const novo = esCopiar(e.esboco)
    const tirarPontos = new Set()
    const tirarCurvas = new Set()
    for (const k of lista) {
      const id = k.slice(2)
      if (k[0] === "p" && id !== "O") tirarPontos.add(id)
      if (k[0] === "c") tirarCurvas.add(id)
      if (k[0] === "r") novo.restricoes = novo.restricoes.filter((r) => r.id !== id)
      if (k[0] === "d") novo.cotas = novo.cotas.filter((c) => c.id !== id)
      if (k[0] === "a") novo.analises = (novo.analises ?? []).filter((a) => a.id !== id)
    }
    const soltos = new Set()
    novo.curvas = novo.curvas.filter((c) => {
      const sai = tirarCurvas.has(c.id) || c.pontos.some((p) => tirarPontos.has(p))
      if (sai) for (const p of c.pontos) soltos.add(p)
      return !sai
    })
    for (const p of tirarPontos) delete novo.pontos[p]
    limparReferencias(novo)
    for (const p of soltos) {
      if (p === "O" || !(p in novo.pontos)) continue
      const usa =
        novo.curvas.some((c) => c.pontos.includes(p)) ||
        novo.restricoes.some((r) => (r.pontos ?? []).includes(p)) ||
        novo.cotas.some((c) => (c.pontos ?? []).includes(p))
      if (!usa) delete novo.pontos[p]
    }
    limparReferencias(novo)
    e.sel.clear()
    const erro = tentar(novo)
    avisar(erro, "ruim")
  }
  function alternarConstrucao() {
    const { curvas } = escolhidos()
    if (!curvas.length) {
      e.construcao = !e.construcao
      raiz.querySelector('[data-a="construcao"]').classList.toggle("ativo", e.construcao)
      return
    }
    const novo = esCopiar(e.esboco)
    for (const c of novo.curvas) {
      if (curvas.some((x) => x.id === c.id)) {
        if (c.construcao) delete c.construcao
        else c.construcao = true
      }
    }
    tentarOuAvisar(novo)
  }

  // ---- letras -----------------------------------------------------------------------------------
  function usosDaLetra(nome) {
    return e.esboco.cotas.filter((c) => {
      try {
        return !c.referencia && letrasDaConta(lerConta(c.expressao)).has(nome)
      } catch {
        return false
      }
    }).length
  }
  function mudarLetra(nome, texto) {
    const v = e.esboco.variaveis.find((x) => x.nome === nome)
    if (!v) return
    const lido = lerValorDigitado(texto, v.valor, v.tipo === "angulo" ? "°" : "mm")
    if (lido.erro) return avisar(lido.erro, "ruim")
    const novo = esCopiar(e.esboco)
    novo.variaveis.find((x) => x.nome === nome).valor = lido.valor
    for (const c of novo.cotas) {
      if (c.referencia) continue
      // Só as cotas que usam a letra: uma distância de 0 que já estava lá (o furo na altura da
      // origem) não tem nada a ver com a letra mudada.
      const conta = lerConta(c.expressao)
      if (!letrasDaConta(conta).has(nome)) continue
      const valor = avaliarConta(conta, esValores(novo))
      if (!(valor > 0) && c.tipo !== "angulo") return avisar(`Com ${nome} = ${esNum(lido.valor)}, uma cota fica sem medida.`, "ruim")
    }
    const erro = tentar(novo)
    avisar(erro ? `${nome} = ${esNum(lido.valor)}: ${erro}` : "", "ruim")
    if (erro) montarPainel()
  }
  function novaLetra(nome, texto) {
    nome = String(nome ?? "").trim()
    if (!nomeValido(nome)) return avisar("A letra começa por letra, sem espaço: d, b1, t_f.", "ruim")
    if (e.esboco.variaveis.some((v) => v.nome === nome)) return avisar(`A letra ${nome} já existe.`, "ruim")
    const lido = lerValorDigitado(texto || "10", 10, "mm")
    if (lido.erro) return avisar(lido.erro, "ruim")
    guardar()
    e.esboco.variaveis.push({ nome, valor: lido.valor, tipo: "comprimento" })
    avisar(`Letra ${nome} criada. Use numa cota: clique na medida e digite ${nome}.`, "aviso")
    depoisDeMudar()
  }
  function tirarLetra(nome) {
    if (usosDaLetra(nome)) return avisar(`A letra ${nome} está numa cota: troque a cota antes.`, "ruim")
    guardar()
    e.esboco.variaveis = e.esboco.variaveis.filter((v) => v.nome !== nome)
    depoisDeMudar()
  }


  // ---- edição: aparar, estender, dividir, filete, chanfro, deslocar, espelhar, padrões -----------
  // O texto de um campo (raio, distância, passo) vira conta; letra nova nasce com `padrao`.
  function contaDoCampo(texto, padrao) {
    const numero = lerValorDigitado(texto, padrao, "mm")
    if (!numero.erro) return { expressao: esNumConta(numero.valor), novas: [] }
    let no
    try {
      no = lerConta(texto)
    } catch (erro) {
      return { erro: erro.message }
    }
    const conhecidas = new Set(e.esboco.variaveis.map((v) => v.nome))
    const novas = [...letrasDaConta(no)].filter((l) => !conhecidas.has(l))
    for (const l of novas) if (!nomeValido(l)) return { erro: `“${l}” não serve de letra.` }
    if (novas.length > 1) return { erro: `Crie uma letra de cada vez: ${novas.join(", ")} são novas.` }
    return { expressao: String(texto).trim().replace(/,/g, "."), novas: novas.map((nome) => ({ nome, valor: padrao })) }
  }
  function comCampo(texto, padrao) {
    const conta = contaDoCampo(texto, padrao)
    if (conta.erro) return conta
    const novo = esCopiar(e.esboco)
    for (const v of conta.novas) novo.variaveis.push({ nome: v.nome, valor: v.valor, tipo: "comprimento" })
    return { novo, expressao: conta.expressao, valores: esValores(novo) }
  }
  function aplicarEdicao(resultado, aposSucesso = null) {
    if (resultado.erro) return avisar(resultado.erro, "ruim")
    const erro = tentar(resultado.esboco)
    if (erro) return avisar(erro, "ruim")
    avisar("")
    e.picks = []
    aposSucesso?.(resultado)
  }
  const curvasEscolhidas = () => {
    const lista = e.picks.length ? e.picks : [...e.sel]
    return lista.filter((k) => k.startsWith("c:")).map((k) => k.slice(2))
  }
  function alternarPick(chave) {
    const i = e.picks.indexOf(chave)
    if (i >= 0) e.picks.splice(i, 1)
    else e.picks.push(chave)
  }
  function pontoNoMouse(u, v) {
    let melhor = null
    let dist = ES_PERTO_PX
    for (const [pid, [x, y]] of Object.entries(e.esboco.pontos)) {
      const [a, b] = px(x, y)
      const d = Math.hypot(a - u, b - v)
      if (d <= dist) {
        dist = d
        melhor = pid
      }
    }
    return melhor
  }
  function curvaNoMouse(u, v) {
    let melhor = null
    let dist = ES_PERTO_PX
    for (const c of e.esboco.curvas) {
      const d = distCurvaPx(c, u, v)
      if (d <= dist) {
        dist = d
        melhor = c.id
      }
    }
    return melhor
  }
  function cliqueDeEdicao(u, v, mundo, ev) {
    const f = e.ferramenta
    // Aqui a curva vale mais que o ponto: clicar perto da ponta de uma linha ainda é clicar nela.
    const curvaAqui = curvaNoMouse(u, v)
    const pontoAqui = pontoNoMouse(u, v)
    if (f === "aparar" || f === "estender" || f === "dividir") {
      if (!curvaAqui) return avisar("Clique numa curva.", "aviso")
      const op = { aparar: edAparar, estender: edEstender, dividir: edDividir }[f]
      return aplicarEdicao(op(e.esboco, curvaAqui, mundo[0], mundo[1]))
    }
    if (f === "filete" || f === "chanfro") {
      const canto = pontoAqui ?? null
      if (!canto) return avisar("Clique no canto (o ponto onde as duas linhas se encontram).", "aviso")
      const texto = f === "filete" ? e.opcoes.raio : e.opcoes.chanfro
      const campo = comCampo(texto, 5)
      if (campo.erro) return avisar(campo.erro, "ruim")
      const op = f === "filete" ? edFilete : edChanfro
      return aplicarEdicao(op(campo.novo, canto, campo.expressao, campo.valores))
    }
    if (f === "deslocar") {
      if (curvaAqui) return alternarPick(`c:${curvaAqui}`)
      const ids = curvasEscolhidas()
      if (!ids.length) return avisar("Clique antes nas curvas que vão ser deslocadas.", "aviso")
      const campo = comCampo(e.opcoes.distancia, 3)
      if (campo.erro) return avisar(campo.erro, "ruim")
      return aplicarEdicao(edDeslocar(campo.novo, ids, mundo, campo.expressao, campo.valores))
    }
    if (f === "espelhar") {
      const ids = curvasEscolhidas()
      const linha = curvaAqui && curva(curvaAqui)?.tipo === "linha"
      if (linha && ids.length && !ev.shiftKey && !ids.includes(curvaAqui)) {
        return aplicarEdicao(edEspelhar(e.esboco, ids, curvaAqui))
      }
      if (curvaAqui) return alternarPick(`c:${curvaAqui}`)
      return avisar("Clique nas curvas e depois na linha do espelho.", "aviso")
    }
    if (f === "padrao_linear" || f === "transformar") {
      if (curvaAqui) return alternarPick(`c:${curvaAqui}`)
      return
    }
    if (f === "padrao_circular") {
      if (pontoAqui && curvasEscolhidas().length) {
        return aplicarEdicao(edPadraoCircular(e.esboco, curvasEscolhidas(), pontoAqui, e.opcoes.quantosCirc, e.opcoes.angulo))
      }
      if (curvaAqui) return alternarPick(`c:${curvaAqui}`)
      return avisar("Clique nas curvas e depois no ponto do centro.", "aviso")
    }
  }
  function criarPadraoLinear() {
    const ids = curvasEscolhidas()
    if (!ids.length) return avisar("Escolha as curvas que se repetem.", "aviso")
    const campo = comCampo(e.opcoes.passo, 20)
    if (campo.erro) return avisar(campo.erro, "ruim")
    aplicarEdicao(edPadraoLinear(campo.novo, ids, e.opcoes.quantos, campo.expressao, e.opcoes.direcao, campo.valores))
    montarPainel()
    desenhar()
  }
  const escolherCurvas = (ids) => {
    e.sel = new Set(ids.map((id) => `c:${id}`))
  }
  // Mover e girar com números: o que estiver preso por cota volta ao lugar (o solver manda).
  function aplicarTransformar() {
    const ids = curvasEscolhidas()
    if (!ids.length) return avisar("Escolha as curvas que vão andar.", "aviso")
    const lidos = [
      lerValorDigitado(e.opcoes.dx, 0, "mm"),
      lerValorDigitado(e.opcoes.dy, 0, "mm"),
      lerValorDigitado(e.opcoes.giro, 0, "°"),
    ]
    const ruim = lidos.find((l) => l.erro)
    if (ruim) return avisar(ruim.erro, "ruim")
    const [dx, dy, giro] = lidos.map((l) => l.valor)
    const centro = e.opcoes.centroGiro === "origem" ? [0, 0] : edCentroDe(e.esboco, ids)
    const antes = esCopiar(e.esboco.pontos)
    const copiar = Boolean(e.opcoes.copiar)
    aplicarEdicao(edTransformar(e.esboco, ids, dx, dy, giro, centro, copiar), (r) => {
      escolherCurvas(r.novas)
      e.picks = [...e.sel]
      if (copiar) return
      const andou = edPontosDe(e.esboco, ids).some((p) => {
        const [x0, y0] = antes[p] ?? [NaN, NaN]
        const [x1, y1] = e.esboco.pontos[p]
        return Math.hypot(x1 - x0, y1 - y0) > 1e-6 * edTamanho(e.esboco)
      })
      if (!andou) avisar("Nada andou: as cotas e restrições seguram essas curvas no lugar. Use a cópia, ou solte uma cota.", "aviso")
    })
    montarPainel()
    desenhar()
  }
  function copiarEscolha() {
    const ids = escolhidos().curvas.map((c) => c.id)
    if (!ids.length) return avisar("Escolha as curvas que vão ser copiadas.", "aviso")
    e.recorte = edRecorte(e.esboco, ids)
    avisar(`${ids.length} ${ids.length === 1 ? "curva copiada" : "curvas copiadas"}: Ctrl+V cola onde o mouse estiver.`, "aviso")
  }
  function colarRecorte() {
    if (!e.recorte) return avisar("Nada copiado ainda: escolha curvas e use Ctrl+C.", "aviso")
    const meio = edCentroDe(e.recorte, e.recorte.curvas.map((c) => c.id))
    const para = e.mouse ?? [meio[0] + 0.1 * edTamanho(e.esboco), meio[1]]
    const levar = ([x, y]) => [x + para[0] - meio[0], y + para[1] - meio[1]]
    aplicarEdicao(edColar(e.esboco, e.recorte, levar), (r) => escolherCurvas(r.novas))
    montarPainel()
    desenhar()
  }
  function unirContornos() {
    const ids = escolhidos().curvas.map((c) => c.id)
    const cotasAntes = e.esboco.cotas.length
    aplicarEdicao(edUnir(e.esboco, ids.length ? ids : null), (r) => {
      escolherCurvas(r.novas)
      const perdidas = cotasAntes - e.esboco.cotas.length
      avisar(
        perdidas > 0
          ? `Contornos unidos. ${perdidas} ${perdidas === 1 ? "cota era" : "cotas eram"} de trechos que saíram: refaça no contorno novo.`
          : "Contornos unidos num só.",
        "aviso",
      )
    })
  }

  // ---- medir: a medida sem virar cota -----------------------------------------------------------
  // ---- pontos de análise ------------------------------------------------------------------------
  function analiseNoMouse(u, v) {
    let melhor = null
    let dist = ES_PERTO_PX + 2
    for (const a of e.esboco.analises ?? []) {
      const xy = edPosicaoDaAnalise(e.esboco, a)
      if (!xy) continue
      const [pu, pv] = px(...xy)
      const d = Math.hypot(pu - u, pv - v)
      if (d <= dist) {
        dist = d
        melhor = a.id
      }
    }
    return melhor
  }
  // Clique da ferramenta: no ponto que já existe, troca o nome; no desenho, cria um. Devolve o id do
  // ponto cujo nome abre ao soltar o botão.
  function marcarAnalise(u, v) {
    const existente = analiseNoMouse(u, v)
    if (existente) return existente
    const [x, y] = doPx(u, v)
    const r = edNovaAnalise(e.esboco, x, y, ES_PERTO_PX / e.vista.esc)
    if (r.erro) {
      avisar(r.erro, "aviso")
      return null
    }
    const erro = tentar(r.esboco)
    if (erro) {
      avisar(erro, "ruim")
      return null
    }
    avisar("")
    return r.id
  }
  function renomearAnalise(id) {
    const a = (e.esboco.analises ?? []).find((x) => x.id === id)
    const alvo = svg.querySelector(`[data-analise="${id}"] text`)
    if (!a || !alvo) return
    editor.abrir(alvo, {
      valor: 0,
      unidade: "",
      nome: "Nome do ponto de análise",
      texto: a.nome,
      dica: "Até 20 letras ou números: A, B1, solda 1. No Montador, vira “von Mises no ponto A”.",
      selecionarTudo: true,
      ler: (texto) => (String(texto).trim() ? { valor: String(texto).trim() } : { erro: "Dê um nome ao ponto." }),
      aplicar: (nome) => {
        if (nome === a.nome) return ""
        const r = edRenomearAnalise(e.esboco, id, nome)
        return r.erro ?? tentar(r.esboco)
      },
      acoes: [{ rotulo: "Apagar", titulo: "Tira o ponto de análise", ao: () => (editor.fechar(), apagar(new Set([`a:${id}`]))) }],
    })
  }
  function svgDasAnalises() {
    return (e.esboco.analises ?? [])
      .map((a) => {
        const xy = edPosicaoDaAnalise(e.esboco, a)
        if (!xy) return ""
        const [u, v] = px(...xy)
        const classes = ["analise"]
        if (e.sel.has(`a:${a.id}`)) classes.push("sel")
        if (e.perto === `a:${a.id}`) classes.push("perto")
        return `<g class="${classes.join(" ")}" data-analise="${a.id}"><title>Ponto de análise ${esc(a.nome)}: no Montador, as tensões também são conferidas aqui. Duplo clique troca o nome.</title><path d="M${u} ${v - 7}L${u + 7} ${v}L${u} ${v + 7}L${u - 7} ${v}Z"/><circle cx="${u}" cy="${v}" r="1.8"/><text x="${u + 9}" y="${v - 8}">${esc(a.nome)}</text></g>`
      })
      .join("")
  }

  function medirPicks() {
    const base = cotaDosPicks(e.picks)
    e.medida = null
    if (!base) return
    let lugar = null
    let a = null
    let b = null
    if (base.tipo === "distancia") [a, b] = pontosDaCota(base).map(PC)
    else if (base.tipo === "ponto_linha") {
      const l = curva(base.curvas[0])
      b = P(base.pontos[0])
      const [la, lb] = l.pontos.map(P)
      const dx = lb[0] - la[0]
      const dy = lb[1] - la[1]
      const t = ((b[0] - la[0]) * dx + (b[1] - la[1]) * dy) / (dx * dx + dy * dy || 1)
      a = [la[0] + t * dx, la[1] + t * dy]
    }
    if (a && b) {
      const l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1
      const o = 14 / e.vista.esc
      lugar = [(a[0] + b[0]) / 2 - ((b[1] - a[1]) / l) * o, (a[1] + b[1]) / 2 + ((b[0] - a[0]) / l) * o]
    }
    const c = cotaCompleta(base, lugar ?? [0, 0])
    if (!lugar) c.lugar = null
    const valor = medida(c)
    let rotulo = esNum(valor, 3)
    let texto = ""
    if (base.tipo === "distancia" && base.curvas?.length) {
      const ang = (Math.atan2(b[1] - a[1], b[0] - a[0]) * 180) / Math.PI
      texto = `Comprimento ${esNum(valor, 3)} mm · ângulo com o eixo x ${esNum(((ang % 180) + 180) % 180, 2)}°`
    } else if (base.tipo === "distancia") {
      const d = Math.hypot(b[0] - a[0], b[1] - a[1])
      rotulo = esNum(d, 3)
      texto = `Distância ${esNum(d, 3)} mm · na horizontal ${esNum(Math.abs(b[0] - a[0]), 3)} · na vertical ${esNum(Math.abs(b[1] - a[1]), 3)}`
    } else if (base.tipo === "ponto_linha") {
      rotulo = esNum(Math.abs(valor), 3)
      texto = `Distância à linha ${esNum(Math.abs(valor), 3)} mm`
    } else if (base.tipo === "diametro") {
      rotulo = `Ø${esNum(valor, 3)}`
      texto = `Diâmetro ${esNum(valor, 3)} mm · raio ${esNum(valor / 2, 3)} · perímetro ${esNum(Math.PI * valor, 3)}`
    } else if (base.tipo === "raio") {
      const info = esArcoInfo(e.esboco, curva(base.curvas[0]))
      rotulo = `R${esNum(valor, 3)}`
      texto = `Raio ${esNum(valor, 3)} mm · arco de ${esNum((info.sw * 180) / Math.PI, 2)}° · comprimento ${esNum(info.r * info.sw, 3)}`
    } else if (base.tipo === "angulo") {
      rotulo = `${esNum(Math.abs(valor), 2)}°`
      texto = `Ângulo ${esNum(Math.abs(valor), 2)}° (o outro lado: ${esNum(180 - Math.abs(valor), 2)}°)`
    }
    e.medida = { base, lugar, rotulo, texto }
    avisar(`Medida: ${texto}`, "aviso")
  }

  // ---- conflito: quem briga, e o jeito de sair --------------------------------------------------
  function conflitoNoPainel() {
    const c = e.conflito
    if (!c) return ""
    const itens = c.origens.map((id) => {
      const cota = c.tentativa.cotas.find((x) => x.id === id)
      if (cota) {
        const nome = `${nomeDaCota(cota)} ${cota.expressao.replace(/\./g, ",")}`
        return `<button type="button" data-conflito="${esc(id)}" data-como="referencia" title="A cota passa a só medir (entre parênteses) e a mudança entra">${esc(nome)}: só medir</button>`
      }
      const r = c.tentativa.restricoes.find((x) => x.id === id)
      const nome = ES_NOMES_DAS_RESTRICOES[r?.tipo] ?? r?.tipo ?? id
      return `<button type="button" data-conflito="${esc(id)}" data-como="apagar" title="A restrição sai e a mudança entra">Apagar “${esc(nome)}”</button>`
    })
    return `<span class="es-conflito"><b>Brigam (em vermelho):</b> ${itens.join("")}<button type="button" data-conflito-fechar title="Deixa como estava">Deixar como estava</button></span>`
  }
  // Os campos da ferramenta, na faixa de baixo.
  function montarOpcoes() {
    const f = e.ferramenta
    const campos = {
      filete: [["raio", "Raio", "Número, letra ou conta: 5, r, t/2"]],
      chanfro: [["chanfro", "Distância", "Número, letra ou conta: 5, c"]],
      deslocar: [["distancia", "Distância", "Número, letra ou conta: 3, t (a espessura)"]],
      padrao_linear: [
        ["quantos", "Quantidade", "Quantas cópias no total, contando a original"],
        ["passo", "Passo", "Distância entre duas cópias: número, letra ou conta"],
      ],
      padrao_circular: [
        ["quantosCirc", "Quantidade", "Quantas no total, contando a original"],
        ["angulo", "Ângulo total (°)", "360 espalha numa volta inteira"],
      ],
      poligono: [["lados", "Lados", "De 3 a 24"]],
      transformar: [
        ["dx", "Anda em x", "Quanto anda na horizontal, em mm (negativo vai para a esquerda)"],
        ["dy", "Anda em y", "Quanto anda na vertical, em mm (negativo desce)"],
        ["giro", "Gira (°)", "Graus no sentido anti-horário (negativo, horário)"],
      ],
    }[f]
    if (!campos) {
      caixaOpcoes.hidden = true
      caixaOpcoes.innerHTML = ""
      return
    }
    const foco = raiz.getRootNode().activeElement
    if (foco && caixaOpcoes.contains(foco) && caixaOpcoes.dataset.f === f) return
    caixaOpcoes.dataset.f = f
    caixaOpcoes.hidden = false
    let html = campos
      .map(([chave, rotulo, titulo]) => `<label title="${esc(titulo)}">${rotulo} <input data-opcao="${chave}" value="${esc(e.opcoes[chave])}"></label>`)
      .join("")
    if (f === "padrao_linear") {
      html += `<label>Direção <select data-opcao="direcao"><option value="h"${e.opcoes.direcao === "h" ? " selected" : ""}>Deitada (x)</option><option value="v"${e.opcoes.direcao === "v" ? " selected" : ""}>Em pé (y)</option></select></label>`
      html += `<button type="button" data-criar-padrao>Criar</button>`
    }
    if (f === "transformar") {
      html += `<label title="Gira em volta do meio das curvas escolhidas, ou da origem">Em volta de <select data-opcao="centroGiro"><option value="meio"${e.opcoes.centroGiro === "meio" ? " selected" : ""}>meio da escolha</option><option value="origem"${e.opcoes.centroGiro === "origem" ? " selected" : ""}>origem</option></select></label>`
      html += `<label title="O original fica, e a cópia vai"><input type="checkbox" data-copiar${e.opcoes.copiar ? " checked" : ""}> Cópia</label>`
      html += `<button type="button" data-aplicar-transformar>Aplicar</button>`
    }
    const n = curvasEscolhidas().length
    if (["deslocar", "transformar", "espelhar", "padrao_linear", "padrao_circular"].includes(f)) {
      html += `<span class="es-ajuda">${n ? `${n} ${n === 1 ? "curva escolhida" : "curvas escolhidas"}` : "nenhuma curva escolhida"}</span>`
    }
    caixaOpcoes.innerHTML = html
    caixaOpcoes.querySelectorAll("[data-opcao]").forEach((campo) => {
      campo.addEventListener("keydown", (ev) => ev.stopPropagation())
      campo.addEventListener("change", () => {
        e.opcoes[campo.dataset.opcao] = campo.value
      })
      campo.addEventListener("input", () => {
        e.opcoes[campo.dataset.opcao] = campo.value
      })
    })
    caixaOpcoes.querySelector("[data-criar-padrao]")?.addEventListener("click", criarPadraoLinear)
    caixaOpcoes.querySelector("[data-aplicar-transformar]")?.addEventListener("click", aplicarTransformar)
    caixaOpcoes.querySelector("[data-copiar]")?.addEventListener("change", (ev) => {
      e.opcoes.copiar = ev.target.checked
    })
  }

  // ---- painel -----------------------------------------------------------------------------------
  function montarPainel() {
    const g = e.graus
    // Situação: o chip do quanto falta prender, e as mensagens.
    const partes = []
    if (!g) partes.push(`<span class="es-chip ruim">Não calculado</span>`)
    else if (g.definido) {
      partes.push(`<span class="es-chip definido" title="Tudo preso por cotas e restrições">Totalmente definido</span>`)
    } else {
      partes.push(
        `<span class="es-chip livre" title="O que está em azul ainda pode andar. Prenda com cotas e restrições, ou deixe: no teste do desenho, o que está solto pode se mexer.">${g.livres} ${g.livres === 1 ? "grau livre" : "graus livres"}</span>`,
      )
    }
    if (e.mensagem?.texto) partes.push(`<span class="es-msg ${e.mensagem.tipo}">${esc(e.mensagem.texto)}</span>`)
    partes.push(conflitoNoPainel())
    for (const p of e.problemas ?? []) partes.push(`<span class="es-msg ruim">${esc(p.mensagem)}</span>`)
    caixaSituacao.innerHTML = partes.join("")
    caixaSituacao.querySelectorAll("[data-conflito]").forEach((b) =>
      b.addEventListener("click", () => {
        resolverConflito(b.dataset.conflito, b.dataset.como)
        svg.focus({ preventScroll: true })
      }),
    )
    caixaSituacao.querySelector("[data-conflito-fechar]")?.addEventListener("click", () => {
      e.conflito = null
      avisar("")
      montarPainel()
      desenhar()
      svg.focus({ preventScroll: true })
    })
    montarLetras()
    // O que está escolhido, e com o que dá para prender.
    const sel = escolhidos()
    let texto = ""
    if (sel.total) {
      const itens = []
      if (sel.pontos.length) itens.push(`${sel.pontos.length} ${sel.pontos.length === 1 ? "ponto" : "pontos"}`)
      if (sel.linhas.length) itens.push(`${sel.linhas.length} ${sel.linhas.length === 1 ? "linha" : "linhas"}`)
      if (sel.redondas.length) itens.push(`${sel.redondas.length} ${sel.redondas.length === 1 ? "arco ou círculo" : "arcos ou círculos"}`)
      const servem = Object.keys(ES_PEDE).filter((t) => {
        const r = montarRestricao(t, [...e.sel])
        return r !== null && typeof r !== "string"
      })
      texto = `Escolhido: ${itens.join(", ")}.`
      if (servem.length) texto += ` Pode prender com: ${servem.map((t) => ES_NOMES_DAS_RESTRICOES[t]).join(", ")}.`
      texto += " Delete apaga."
    }
    caixaSelecao.textContent = texto
    montarOpcoes()
    raiz.querySelectorAll("[data-r]").forEach((b) => b.classList.toggle("ativo", e.ferramenta === `r:${b.dataset.r}`))
  }
  function montarLetras() {
    // Quem está digitando numa letra não pode perder o campo no meio.
    const foco = raiz.getRootNode().activeElement
    if (foco && caixaLetras.contains(foco)) return
    const chips = e.esboco.variaveis
      .map((v) => {
        const usos = usosDaLetra(v.nome)
        const titulo = usos ? `Usada em ${usos} ${usos === 1 ? "cota" : "cotas"}` : "Ainda em nenhuma cota"
        return `<span class="es-letra" title="${titulo}"><b>${esc(v.nome)}</b>
          <input data-letra="${esc(v.nome)}" value="${esNum(v.valor, 6)}" aria-label="Valor de ${esc(v.nome)}">
          ${v.tipo === "angulo" ? "°" : "mm"}
          <button type="button" data-tirar="${esc(v.nome)}" title="Apagar a letra" ${usos ? "disabled" : ""}>×</button></span>`
      })
      .join("")
    const medidas = e.esboco.cotas
      .filter((c) => c.referencia && c.nome)
      .map((c) => {
        let valor = "—"
        try {
          valor = esNum(medida(c), 3)
        } catch {
          // a cota até o centro de gravidade, antes de o Python mandar o centro
        }
        return `<span class="es-letra es-medida" title="Medida do desenho: no Montador, o bloco Medida do desenho lê este valor, que muda com as letras"><b>${esc(c.nome)}</b> = ${valor} mm</span>`
      })
      .join("")
    const pontos = (e.esboco.analises ?? []).map((a) => esc(a.nome)).join(", ")
    caixaLetras.innerHTML = `<span class="es-rotulo">Letras</span>${chips || '<span class="es-ajuda">nenhuma</span>'}
      <span class="es-nova"><input data-nova-nome placeholder="letra" aria-label="Nome da letra nova"><input data-nova-valor placeholder="valor" aria-label="Valor da letra nova"><button type="button" data-nova title="Criar a letra">+</button></span>
      <span class="es-ajuda">Numa cota, digite a letra (d) ou uma conta (2*d): no Montador, ela vira a incógnita.</span>
      ${medidas ? `<span class="es-rotulo">Medidas</span>${medidas}` : ""}
      ${pontos ? `<span class="es-rotulo">Pontos de análise</span><span class="es-ajuda">${pontos}</span>` : ""}`
    caixaLetras.querySelectorAll("[data-letra]").forEach((campo) => {
      campo.addEventListener("keydown", (ev) => {
        ev.stopPropagation()
        if (ev.key === "Enter") campo.blur()
      })
      campo.addEventListener("change", () => mudarLetra(campo.dataset.letra, campo.value))
    })
    caixaLetras.querySelectorAll("[data-tirar]").forEach((b) => b.addEventListener("click", () => tirarLetra(b.dataset.tirar)))
    const nome = caixaLetras.querySelector("[data-nova-nome]")
    const valor = caixaLetras.querySelector("[data-nova-valor]")
    const criar = () => novaLetra(nome.value, valor.value)
    caixaLetras.querySelector("[data-nova]").addEventListener("click", criar)
    for (const campo of [nome, valor]) {
      campo.addEventListener("keydown", (ev) => {
        ev.stopPropagation()
        if (ev.key === "Enter") criar()
      })
    }
  }
  const esc = (t) =>
    String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c])

  // ---- desenho na tela --------------------------------------------------------------------------
  function grade() {
    const { w, h } = tela()
    const passos = [0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000]
    const passo = passos.find((p) => p * e.vista.esc >= 28) ?? 5000
    const [x0, y1] = doPx(0, 0)
    const [x1, y0] = doPx(w, h)
    const linhas = []
    for (let x = Math.ceil(x0 / passo) * passo; x <= x1; x += passo) {
      const [u] = px(x, 0)
      linhas.push(`<line class="${Math.abs(x) < 1e-9 ? "grade-eixo" : "grade-fina"}" x1="${u}" y1="0" x2="${u}" y2="${h}"/>`)
    }
    for (let y = Math.ceil(y0 / passo) * passo; y <= y1; y += passo) {
      const [, v] = px(0, y)
      linhas.push(`<line class="${Math.abs(y) < 1e-9 ? "grade-eixo" : "grade-fina"}" x1="0" y1="${v}" x2="${w}" y2="${v}"/>`)
    }
    return linhas.join("")
  }
  function svgDaCurva(c, classe) {
    if (c.tipo === "linha") {
      const [ax, ay] = px(...P(c.pontos[0]))
      const [bx, by] = px(...P(c.pontos[1]))
      return `<line class="${classe}" x1="${ax}" y1="${ay}" x2="${bx}" y2="${by}"/>`
    }
    if (c.tipo === "circulo") {
      const [cx, cy] = px(...P(c.pontos[0]))
      return `<circle class="${classe}" cx="${cx}" cy="${cy}" r="${c.raio * e.vista.esc}"/>`
    }
    const info = esArcoInfo(e.esboco, c)
    const [ax, ay] = px(...P(c.pontos[1]))
    const [bx, by] = px(...P(c.pontos[2]))
    const r = info.r * e.vista.esc
    // Anti-horário no mundo é anti-horário na tela, que no SVG (y para baixo) é varre = 0.
    return `<path class="${classe}" d="M${ax} ${ay}A${r} ${r} 0 ${info.sw > Math.PI ? 1 : 0} 0 ${bx} ${by}"/>`
  }
  function seta(x, y, ang) {
    const a = 8
    const b = 3.2
    const p1 = [x - a * Math.cos(ang) + b * Math.sin(ang), y - a * Math.sin(ang) - b * Math.cos(ang)]
    const p2 = [x - a * Math.cos(ang) - b * Math.sin(ang), y - a * Math.sin(ang) + b * Math.cos(ang)]
    return `<path class="seta" d="M${x} ${y}L${p1[0]} ${p1[1]}L${p2[0]} ${p2[1]}Z"/>`
  }
  function linhaDeCota(a, b) {
    const ang = Math.atan2(b[1] - a[1], b[0] - a[0])
    return `<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}"/>${seta(b[0], b[1], ang)}${seta(a[0], a[1], ang + Math.PI)}`
  }
  function svgDaCota(c) {
    let corpo = ""
    let texto = [0, 0]
    const lugar = c.lugar ?? null
    if (c.tipo === "distancia" || c.tipo === "ponto_linha") {
      let a
      let b
      if (c.tipo === "distancia") {
        ;[a, b] = pontosDaCota(c).map(PC)
      } else {
        const l = curva(c.curvas[0])
        const [ax, ay] = P(l.pontos[0])
        const [bx, by] = P(l.pontos[1])
        const [x, y] = P(c.pontos[0])
        const dx = bx - ax
        const dy = by - ay
        const t = ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy || 1)
        a = [ax + t * dx, ay + t * dy]
        b = [x, y]
      }
      const modo = c.tipo === "distancia" ? c.modo : "d"
      const L = lugar ?? [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 10 / e.vista.esc]
      let a2
      let b2
      if (modo === "h") {
        a2 = [a[0], L[1]]
        b2 = [b[0], L[1]]
      } else if (modo === "v") {
        a2 = [L[0], a[1]]
        b2 = [L[0], b[1]]
      } else {
        const l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1
        const n = [-(b[1] - a[1]) / l, (b[0] - a[0]) / l]
        const o = (L[0] - a[0]) * n[0] + (L[1] - a[1]) * n[1]
        a2 = [a[0] + o * n[0], a[1] + o * n[1]]
        b2 = [b[0] + o * n[0], b[1] + o * n[1]]
      }
      const [pa, pa2, pb, pb2] = [a, a2, b, b2].map((p) => px(...p))
      corpo = `<line x1="${pa[0]}" y1="${pa[1]}" x2="${pa2[0]}" y2="${pa2[1]}" opacity="0.5"/><line x1="${pb[0]}" y1="${pb[1]}" x2="${pb2[0]}" y2="${pb2[1]}" opacity="0.5"/>${linhaDeCota(pa2, pb2)}`
      texto = [(pa2[0] + pb2[0]) / 2, (pa2[1] + pb2[1]) / 2 - 5]
    } else if (c.tipo === "diametro" || c.tipo === "raio") {
      const k = curva(c.curvas[0])
      const [cx, cy] = P(k.pontos[0])
      const r = raioDe(k)
      const L = lugar ?? [cx + r * 1.3, cy + r * 0.6]
      let ux = L[0] - cx
      let uy = L[1] - cy
      const l = Math.hypot(ux, uy) || 1
      ux /= l
      uy /= l
      const borda = px(cx + r * ux, cy + r * uy)
      const oposta = c.tipo === "diametro" ? px(cx - r * ux, cy - r * uy) : px(cx, cy)
      const ponta = px(...L)
      corpo = `${linhaDeCota(oposta, borda)}<line x1="${borda[0]}" y1="${borda[1]}" x2="${ponta[0]}" y2="${ponta[1]}"/>`
      texto = [ponta[0] + 4, ponta[1] - 4]
    } else if (c.tipo === "angulo") {
      const l1 = curva(c.curvas[0])
      const l2 = curva(c.curvas[1])
      const [a1, b1, a2, b2] = [l1.pontos[0], l1.pontos[1], l2.pontos[0], l2.pontos[1]].map(P)
      const d1 = [b1[0] - a1[0], b1[1] - a1[1]]
      const d2 = [b2[0] - a2[0], b2[1] - a2[1]]
      const den = d1[0] * d2[1] - d1[1] * d2[0]
      let X = a1
      if (Math.abs(den) > 1e-12) {
        const t = ((a2[0] - a1[0]) * d2[1] - (a2[1] - a1[1]) * d2[0]) / den
        X = [a1[0] + t * d1[0], a1[1] + t * d1[1]]
      }
      const L = lugar ?? [X[0] + 20 / e.vista.esc, X[1] + 20 / e.vista.esc]
      const R = Math.max(Math.hypot(L[0] - X[0], L[1] - X[1]), 4 / e.vista.esc)
      const t0 = Math.atan2(d1[1], d1[0])
      const theta = esAnguloEntre([...a1, ...b1, ...a2, ...b2])
      const pontos = []
      for (let i = 0; i <= 24; i += 1) {
        const t = t0 + (theta * i) / 24
        pontos.push(px(X[0] + R * Math.cos(t), X[1] + R * Math.sin(t)))
      }
      corpo = `<path d="M${pontos.map((p) => p.join(" ")).join("L")}"/>`
      const meio = px(X[0] + R * Math.cos(t0 + theta / 2), X[1] + R * Math.sin(t0 + theta / 2))
      texto = [meio[0] + 4, meio[1] - 4]
      if (lugar) texto = px(...L)
    }
    const classes = ["cota"]
    if (c.medida) classes.push("medida")
    else if (c.referencia) classes.push(c.nome ? "referencia medida-nomeada" : "referencia")
    else if (!ehNumero(c.expressao)) classes.push("letra")
    if (e.sel.has(`d:${c.id}`)) classes.push("sel")
    if (e.conflito?.origens.includes(c.id)) classes.push("conflito")
    const ancora = c.tipo === "diametro" || c.tipo === "raio" ? "start" : "middle"
    const rotulo = c.medida ? e.medida.rotulo : rotuloDaCota(c)
    return `<g class="${classes.join(" ")}" data-cota="${c.id}">${corpo}<text x="${texto[0]}" y="${texto[1]}" text-anchor="${ancora}">${esc(rotulo)}</text></g>`
  }
  function sinaisDasRestricoes() {
    const contagem = new Map()
    const saida = []
    const lugar = (chave, base, normal) => {
      const n = contagem.get(chave) ?? 0
      contagem.set(chave, n + 1)
      return [base[0] + normal[0] * 14 + n * 15, base[1] + normal[1] * 14]
    }
    for (const r of e.esboco.restricoes) {
      const sinal = ES_SINAIS[r.tipo]
      if (!sinal) continue
      const lugares = []
      if (r.curvas?.length && r.tipo !== "na_curva" && r.tipo !== "ponto_medio" && r.tipo !== "simetrico") {
        for (const cid of r.curvas) {
          const c = curva(cid)
          if (!c) continue
          const m = px(...meioDaCurva(c))
          let normal = [0.7, -0.7]
          if (c.tipo === "linha") {
            const [ax, ay] = px(...P(c.pontos[0]))
            const [bx, by] = px(...P(c.pontos[1]))
            const l = Math.hypot(bx - ax, by - ay) || 1
            normal = [-(by - ay) / l, (bx - ax) / l]
          }
          lugares.push(lugar(`c:${cid}`, m, normal))
        }
      } else {
        for (const pid of r.pontos ?? []) {
          const p = P(pid)
          if (p) lugares.push(lugar(`p:${pid}`, px(...p), [0.75, -0.75]))
        }
      }
      const sel = (e.sel.has(`r:${r.id}`) ? " sel" : "") + (e.conflito?.origens.includes(r.id) ? " conflito" : "")
      for (const [x, y] of lugares) {
        saida.push(
          `<g class="sinal${sel}" data-sinal="${r.id}"><title>${ES_NOMES_DAS_RESTRICOES[r.tipo] ?? r.tipo}</title><rect x="${x - 6.5}" y="${y - 6.5}" width="13" height="13" rx="3"/><text x="${x}" y="${y + 3.5}" text-anchor="middle">${sinal}</text></g>`,
        )
      }
    }
    return saida.join("")
  }
  function previa() {
    const d = e.desenho
    const m = e.mouse
    if (!m) return ""
    const partes = []
    const enc = e.encaixe
    if (enc) {
      const [u, v] = px(enc.x, enc.y)
      if (enc.ponto || enc.meio || enc.curva) partes.push(`<circle class="encaixe" cx="${u}" cy="${v}" r="6"/>`)
      if (enc.guiaX) {
        const [gu, gv] = px(...P(enc.guiaX))
        partes.push(`<line class="guia" x1="${gu}" y1="${gv}" x2="${u}" y2="${v}"/>`)
      }
      if (enc.guiaY) {
        const [gu, gv] = px(...P(enc.guiaY))
        partes.push(`<line class="guia" x1="${gu}" y1="${gv}" x2="${u}" y2="${v}"/>`)
      }
    }
    if (!d) return partes.join("")
    const alvo = enc ?? { x: m[0], y: m[1] }
    if (d.tipo === "linha") {
      const { enc: certo, restricao, com } = inferirDirecao(d.de, alvo)
      const [a, b] = px(...P(d.de))
      const [u, v] = px(certo.x, certo.y)
      partes.push(`<line class="previa" x1="${a}" y1="${b}" x2="${u}" y2="${v}"/>`)
      const l = Math.hypot(certo.x - P(d.de)[0], certo.y - P(d.de)[1])
      partes.push(`<text x="${u + 10}" y="${v - 10}" font-size="11" fill="currentColor">${esNum(l, 2)}</text>`)
      // A inferência aparece: a curva de referência acesa e o sinal ao lado do mouse.
      if (restricao) {
        const referencia = com ? curva(com) : null
        if (referencia) partes.push(svgDaCurva(referencia, "inferida"))
        partes.push(
          `<g class="sinal inferido"><rect x="${u + 8}" y="${v + 4}" width="15" height="15" rx="3"/><text x="${u + 15.5}" y="${v + 15}" text-anchor="middle">${ES_SINAIS[restricao]}</text></g>`,
        )
      }
    } else if (d.tipo === "rasgo") {
      const [a, b] = px(d.a.x, d.a.y)
      if (!d.b) {
        const [u, v] = px(alvo.x, alvo.y)
        partes.push(`<line class="previa" x1="${a}" y1="${b}" x2="${u}" y2="${v}"/>`)
      } else {
        const r = larguraDoRasgo(d, m)
        const contorno = r > 0 ? contornoDoRasgo(d.a, d.b, r) : ""
        if (contorno) partes.push(`<path class="previa" d="${contorno}"/>`)
        partes.push(`<text x="${px(...m)[0] + 10}" y="${px(...m)[1] - 10}" font-size="11" fill="currentColor">largura ${esNum(2 * r, 2)}</text>`)
      }
    } else if (d.tipo === "poligono") {
      const n = Math.round(Number(String(e.opcoes.lados).replace(",", ".")))
      if (n >= 3 && n <= 24) {
        const r = Math.hypot(alvo.x - d.centro.x, alvo.y - d.centro.y)
        const a0 = Math.atan2(alvo.y - d.centro.y, alvo.x - d.centro.x)
        const vertices = Array.from({ length: n }, (_, k) =>
          px(d.centro.x + r * Math.cos(a0 + (2 * Math.PI * k) / n), d.centro.y + r * Math.sin(a0 + (2 * Math.PI * k) / n)),
        )
        partes.push(`<path class="previa" d="M${vertices.map((p) => p.join(" ")).join("L")}Z"/>`)
      }
    } else if (d.tipo === "circulo") {
      const [cx, cy] = px(d.centro.x, d.centro.y)
      const r = Math.hypot(m[0] - d.centro.x, m[1] - d.centro.y)
      partes.push(`<circle class="previa" cx="${cx}" cy="${cy}" r="${r * e.vista.esc}"/>`)
      partes.push(`<text x="${cx + r * e.vista.esc + 6}" y="${cy - 6}" font-size="11" fill="currentColor">Ø ${esNum(2 * r, 2)}</text>`)
    } else if (d.tipo === "retangulo" || d.tipo === "retangulo_centro") {
      const a = d.tipo === "retangulo_centro" ? { x: 2 * d.a.x - alvo.x, y: 2 * d.a.y - alvo.y } : d.a
      const [u0, v0] = px(a.x, a.y)
      const [u1, v1] = px(alvo.x, alvo.y)
      partes.push(
        `<rect class="previa" x="${Math.min(u0, u1)}" y="${Math.min(v0, v1)}" width="${Math.abs(u1 - u0)}" height="${Math.abs(v1 - v0)}"/>`,
      )
      partes.push(
        `<text x="${Math.max(u0, u1) + 6}" y="${Math.min(v0, v1) - 6}" font-size="11" fill="currentColor">${esNum(Math.abs(alvo.x - a.x), 2)} × ${esNum(Math.abs(alvo.y - a.y), 2)}</text>`,
      )
    } else if (d.tipo === "arco") {
      if (!d.b) {
        const [a, b] = px(d.a.x, d.a.y)
        const [u, v] = px(alvo.x, alvo.y)
        partes.push(`<line class="previa" x1="${a}" y1="${b}" x2="${u}" y2="${v}"/>`)
      } else {
        const circ = circuloPor3(d.a, d.b, { x: m[0], y: m[1] })
        if (circ) {
          const ta = Math.atan2(d.a.y - circ.cy, d.a.x - circ.cx)
          const info = { ta, sw: angAnti(ta, Math.atan2(d.b.y - circ.cy, d.b.x - circ.cx)) }
          const passa = pontoNoArco(info, Math.atan2(m[1] - circ.cy, m[0] - circ.cx))
          const [ini, fim] = passa ? [d.a, d.b] : [d.b, d.a]
          const sw = passa ? info.sw : 2 * Math.PI - info.sw
          const [u0, v0] = px(ini.x, ini.y)
          const [u1, v1] = px(fim.x, fim.y)
          const r = circ.r * e.vista.esc
          partes.push(`<path class="previa" d="M${u0} ${v0}A${r} ${r} 0 ${sw > Math.PI ? 1 : 0} 0 ${u1} ${v1}"/>`)
        }
      }
    } else if (d.tipo === "arco_tangente") {
      const arco = arcoTangente(d, alvo)
      if (arco) {
        const [u0, v0] = px(...P(d.de))
        const [u1, v1] = px(alvo.x, alvo.y)
        const r = arco.r * e.vista.esc
        const ta = Math.atan2(P(d.de)[1] - arco.cy, P(d.de)[0] - arco.cx)
        const tb = Math.atan2(alvo.y - arco.cy, alvo.x - arco.cx)
        const sw = arco.esquerda ? angAnti(ta, tb) : angAnti(tb, ta)
        partes.push(
          `<path class="previa" d="M${u0} ${v0}A${r} ${r} 0 ${sw > Math.PI ? 1 : 0} ${arco.esquerda ? 0 : 1} ${u1} ${v1}"/>`,
        )
      }
    }
    return partes.join("")
  }
  function desenhar() {
    const { w, h } = tela()
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`)
    svg.classList.toggle("selecionar", e.ferramenta === "selecionar")
    const g = e.graus
    const partes = [grade()]
    const aco = esCaminhoDoAco(e.esboco, px)
    if (aco) partes.push(`<path class="aco" d="${aco}"/>`)
    for (const c of e.esboco.curvas) {
      const classes = ["curva"]
      if (c.construcao) classes.push("construcao")
      else classes.push(g && !g.curvasLivres.has(c.id) ? "definida" : "livre")
      if (e.sel.has(`c:${c.id}`) || e.picks.includes(`c:${c.id}`)) classes.push("sel")
      if (e.perto === `c:${c.id}`) classes.push("perto")
      partes.push(svgDaCurva(c, classes.join(" ")))
    }
    if (chaveSinais.checked) partes.push(sinaisDasRestricoes())
    for (const c of e.esboco.cotas) {
      if (c.oculta) continue
      try {
        partes.push(svgDaCota(c))
      } catch {
        // uma cota de algo que acabou de sumir: a próxima rodada já limpa
      }
    }
    for (const [pid, [x, y]] of Object.entries(e.esboco.pontos)) {
      const [u, v] = px(x, y)
      if (pid === "O") {
        partes.push(`<circle class="ponto origem" cx="${u}" cy="${v}" r="5"/><circle class="ponto definido" cx="${u}" cy="${v}" r="1.6"/>`)
        continue
      }
      const classes = ["ponto", g && !g.pontosLivres.has(pid) ? "definido" : "livre"]
      const sel = e.sel.has(`p:${pid}`) || e.picks.includes(`p:${pid}`)
      if (sel) classes.push("sel")
      const r = sel || e.perto === `p:${pid}` ? 4.5 : 3
      partes.push(`<circle class="${classes.join(" ")}" cx="${u}" cy="${v}" r="${r}"/>`)
    }
    partes.push(svgDasAnalises())
    const { soltas, bifurcacoes } = esContornos(e.esboco)
    for (const pid of [...soltas, ...bifurcacoes]) {
      const [u, v] = px(...P(pid))
      partes.push(`<circle class="problema" cx="${u}" cy="${v}" r="8"><title>Contorno aberto ou com três curvas aqui</title></circle>`)
    }
    for (const p of e.problemas ?? []) {
      if (!p.onde) continue
      const [u, v] = px(p.onde[0], p.onde[1])
      partes.push(`<circle class="problema" cx="${u}" cy="${v}" r="10"><title>${esc(p.mensagem)}</title></circle>`)
    }
    if (e.marcas && Number.isFinite(e.marcas.xc)) {
      const [u, v] = px(e.marcas.xc, e.marcas.yc)
      partes.push(
        `<g class="centro${e.perto === "g:CG" || e.picks.includes("g:CG") ? " perto" : ""}"><title>Centro de gravidade${e.ferramenta === "cota" ? ": clique para cotar até ele (a cota só mede)" : ""}</title><circle cx="${u}" cy="${v}" r="5"/><line x1="${u - 8}" y1="${v}" x2="${u + 8}" y2="${v}"/><line x1="${u}" y1="${v - 8}" x2="${u}" y2="${v + 8}"/></g>`,
      )
    }
    if (e.gesto?.tipo === "janela" && e.gesto.ativo) {
      const [u0, v0] = e.gesto.inicio
      const [u1, v1] = e.gesto.atual
      const cruza = u1 < u0 ? " cruza" : ""
      partes.push(
        `<rect class="janela${cruza}" x="${Math.min(u0, u1)}" y="${Math.min(v0, v1)}" width="${Math.abs(u1 - u0)}" height="${Math.abs(v1 - v0)}"/>`,
      )
    }
    if (e.gesto?.tipo === "arrastar" && e.gesto.alvo) {
      const [u, v] = px(e.gesto.alvo.x, e.gesto.alvo.y)
      const titulo = e.gesto.alvo.ponto ? "Solte para juntar os pontos" : "Solte para prender o ponto na curva"
      partes.push(`<g class="juntar"><title>${titulo}</title><circle cx="${u}" cy="${v}" r="9"/><circle cx="${u}" cy="${v}" r="3.5"/></g>`)
    }
    if (e.ferramenta === "cota" && e.picks.length && e.mouse) {
      const base = cotaDosPicks(e.picks)
      if (base) {
        try {
          partes.push(svgDaCota({ id: "_", expressao: "0", ...cotaCompleta(base, e.mouse) }))
        } catch {
          // escolha que não dá cota
        }
      }
    }
    if (e.ferramenta === "medir" && e.medida) {
      try {
        partes.push(svgDaCota({ id: "_", expressao: "0", medida: true, ...cotaCompleta(e.medida.base, e.medida.lugar) }))
      } catch {
        // o que foi medido sumiu
      }
    }
    partes.push(previa())
    svg.innerHTML = partes.join("")
    arrumarCotas()
    if (e.mouse) infoXY.textContent = `x ${esNum(e.mouse[0], 2)}   y ${esNum(e.mouse[1], 2)} mm`
  }
  // Os textos das cotas não se cobrem: o que bate em outro desce (ou sobe) até ficar livre. Só na
  // tela: o lugar guardado da cota não muda.
  function arrumarCotas() {
    const textos = [...svg.querySelectorAll("[data-cota] text")]
    if (textos.length < 2) return
    const caixas = []
    const bate = (a, b) => a.x < b.x + b.w + 2 && b.x < a.x + a.w + 2 && a.y < b.y + b.h + 1 && b.y < a.y + a.h + 1
    for (const t of textos) {
      let b
      try {
        b = t.getBBox()
      } catch {
        return // fora da tela (aba escondida): fica como está
      }
      if (!(b.width > 0)) continue
      const y0 = Number(t.getAttribute("y"))
      const base = { x: b.x, y: b.y, w: b.width, h: b.height }
      let caixa = base
      // desce uma linha, sobe uma, desce duas, sobe duas...
      for (let k = 1; k <= 12 && caixas.some((o) => bate(caixa, o)); k += 1) {
        const passo = (k % 2 === 1 ? 1 : -1) * Math.ceil(k / 2) * (base.h + 2)
        caixa = { ...base, y: base.y + passo }
        t.setAttribute("y", String(y0 + passo))
      }
      caixas.push(caixa)
    }
  }

  // ---- ferramentas ------------------------------------------------------------------------------
  function fecharMenus() {
    raiz.querySelectorAll(".es-menu").forEach((m) => {
      m.hidden = true
    })
  }
  function trocarFerramenta(nome) {
    e.ferramenta = nome
    e.desenho = null
    e.picks = []
    e.encaixe = null
    e.medida = null
    infoDica.textContent = nome.startsWith("r:") ? `Escolha ${ES_PEDE[nome.slice(2)]}. Esc cancela.` : ES_DICAS[nome] ?? ""
    for (const [grupo, variantes] of Object.entries(ES_GRUPOS)) {
      if (!variantes.includes(nome)) continue
      const principal = raiz.querySelector(`[data-grupo="${grupo}"] [data-principal]`)
      const item = raiz.querySelector(`[data-menu="${grupo}"] [data-f="${nome}"]`)
      principal.dataset.f = nome
      principal.innerHTML = esIcone(nome)
      principal.title = ES_TITULOS[nome] ?? principal.title
      if (item) principal.setAttribute("aria-label", item.textContent.trim())
    }
    fecharMenus()
    // Quem entra numa edição com curvas já escolhidas fica com elas.
    if (ES_EDICAO.has(nome)) e.picks = [...e.sel].filter((k) => k.startsWith("c:"))
    raiz.querySelectorAll("[data-f]").forEach((b) => b.classList.toggle("ativo", b.dataset.f === nome))
    raiz.querySelectorAll("[data-r]").forEach((b) => b.classList.toggle("ativo", nome === `r:${b.dataset.r}`))
    if (e.sistema !== undefined) montarPainel()
    desenhar()
  }
  function digitarMedida(tecla) {
    // Enquanto desenha a linha ou o círculo, o número digitado vira a cota.
    const d = e.desenho
    if (!d || !(d.tipo === "linha" || d.tipo === "circulo") || !e.mouse) return false
    const ancora = document.createElement("span")
    ancora.style.position = "absolute"
    const m = px(...e.mouse)
    ancora.style.left = `${m[0]}px`
    ancora.style.top = `${m[1]}px`
    area.append(ancora)
    const linha = d.tipo === "linha"
    const mouse = [...e.mouse]
    const atual = linha
      ? Math.hypot(mouse[0] - P(d.de)[0], mouse[1] - P(d.de)[1])
      : 2 * Math.hypot(mouse[0] - d.centro.x, mouse[1] - d.centro.y)
    editor.abrir(ancora, {
      valor: atual,
      unidade: "mm",
      nome: linha ? "Comprimento da linha" : "Diâmetro do círculo",
      texto: tecla,
      dica: "Número, letra ou conta: 50, d, 2*d",
      ler: (texto) => {
        const n = lerValorDigitado(texto, atual, "mm")
        if (!n.erro) return n.valor > 0 ? { valor: { expressao: esNumConta(n.valor), valor: n.valor } } : { erro: "A medida precisa ser maior que zero." }
        const r = lerMedida(texto, atual)
        if (r.erro) return r
        const no = lerConta(r.valor.expressao)
        const valores = esValores(e.esboco)
        let valor
        try {
          if (r.valor.novas?.length) valores[r.valor.novas[0]] = atual
          valor = avaliarConta(no, valores)
        } catch (erro) {
          return { erro: erro.message }
        }
        return valor > 0 ? { valor: { ...r.valor, valor } } : { erro: "A conta precisa dar mais que zero." }
      },
      aplicar: (lido) => (linha ? linhaDigitada(d, mouse, lido) : circuloDigitado(d, lido)),
    })
    setTimeout(() => ancora.remove(), 0)
    return true
  }
  function comLetrasNovas(novo, lido, alvo) {
    for (const l of lido.novas ?? []) novo.variaveis.push({ nome: l, valor: Number(alvo.toFixed(6)), tipo: "comprimento" })
  }
  function linhaDigitada(d, mouse, lido) {
    const [x0, y0] = P(d.de)
    let dx = mouse[0] - x0
    let dy = mouse[1] - y0
    const l = Math.hypot(dx, dy) || 1
    dx /= l
    dy /= l
    const inferida = direcaoInferida(d.de, mouse[0], mouse[1])
    if (inferida) [dx, dy] = inferida.dir
    const novo = esCopiar(e.esboco)
    comLetrasNovas(novo, lido, lido.valor)
    const pid = idPonto(novo)
    novo.pontos[pid] = [x0 + dx * lido.valor, y0 + dy * lido.valor]
    const cid = novaCurva(novo, "linha", [d.de, pid])
    prenderInferida(novo, cid, inferida?.restricao, inferida?.com)
    novo.cotas.push({ id: idCota(novo), tipo: "distancia", curvas: [cid], pontos: [d.de, pid], modo: "d", sinal: 1, expressao: lido.expressao, lugar: null })
    const erro = tentar(novo)
    if (!erro) e.desenho = { ...d, de: pid }
    return erro
  }
  function circuloDigitado(d, lido) {
    const novo = esCopiar(e.esboco)
    comLetrasNovas(novo, lido, lido.valor)
    const c = pontoDoEncaixe(novo, d.centro)
    const cid = novaCurva(novo, "circulo", [c], { raio: lido.valor / 2 })
    novo.cotas.push({ id: idCota(novo), tipo: "diametro", curvas: [cid], modo: "d", sinal: 1, expressao: lido.expressao, lugar: null })
    const erro = tentar(novo)
    if (!erro) e.desenho = null
    return erro
  }

  // ---- mouse ------------------------------------------------------------------------------------
  function dentroDaJanela(chave, r, cruzando) {
    const pontosDe = (k) => {
      const id = k.slice(2)
      if (k[0] === "p") return [P(id)]
      const c = curva(id)
      if (!c) return []
      if (c.tipo === "linha") {
        const [a, b] = c.pontos.map(P)
        return Array.from({ length: 9 }, (_, i) => [a[0] + ((b[0] - a[0]) * i) / 8, a[1] + ((b[1] - a[1]) * i) / 8])
      }
      const info = c.tipo === "circulo" ? { cx: P(c.pontos[0])[0], cy: P(c.pontos[0])[1], r: c.raio, ta: 0, sw: 2 * Math.PI } : esArcoInfo(e.esboco, c)
      return Array.from({ length: 17 }, (_, i) => {
        const t = info.ta + (info.sw * i) / 16
        return [info.cx + info.r * Math.cos(t), info.cy + info.r * Math.sin(t)]
      })
    }
    const pontos = pontosDe(chave).map((p) => px(...p))
    const dentro = (p) => p[0] >= r[0] && p[0] <= r[2] && p[1] >= r[1] && p[1] <= r[3]
    return cruzando ? pontos.some(dentro) : pontos.length > 0 && pontos.every(dentro)
  }
  // Onde o ponto `pid` arrastado cairia: outro ponto (que não seja vizinho dele numa curva, senão a
  // curva sumiria) ou uma curva que não é dele. { ponto, x, y } ou { curva, x, y }, ou null.
  function alvoDoSoltar(u, v, pid) {
    const donas = e.esboco.curvas.filter((c) => c.pontos.includes(pid))
    const vizinhos = new Set(donas.flatMap((c) => c.pontos))
    let melhor = null
    let dist = ES_ENCAIXE_PX
    for (const [q, [x, y]] of Object.entries(e.esboco.pontos)) {
      if (q === pid || vizinhos.has(q)) continue
      const [a, b] = px(x, y)
      const d = Math.hypot(a - u, b - v)
      if (d < dist) {
        dist = d
        melhor = { ponto: q, x, y }
      }
    }
    if (melhor) return melhor
    dist = ES_PERTO_PX
    const ja = (cid) => e.esboco.restricoes.some((r) => r.tipo === "na_curva" && r.pontos?.[0] === pid && r.curvas?.[0] === cid)
    for (const c of e.esboco.curvas) {
      if (donas.includes(c) || ja(c.id)) continue
      const d = distCurvaPx(c, u, v)
      if (d < dist) {
        dist = d
        const [x, y] = projetar(c, ...doPx(u, v))
        melhor = { curva: c.id, x, y }
      }
    }
    return melhor
  }
  // Junta o ponto solto no alvo. Devolve falso se não fechou (o arrasto fica como estava).
  function juntarAoSoltar(pid, alvo) {
    const novo = esCopiar(e.esboco)
    if (alvo.ponto) {
      novo.pontos[pid] = [...novo.pontos[alvo.ponto]]
      juntarPontos(novo, alvo.ponto, pid)
    } else {
      novo.pontos[pid] = [alvo.x, alvo.y]
      novaRestricao(novo, "na_curva", { pontos: [pid], curvas: [alvo.curva] })
    }
    const erro = tentar(novo, { guardarAntes: false })
    if (erro) {
      avisar(`Não deu para juntar: ${erro}`, "ruim")
      return false
    }
    avisar(alvo.ponto ? "Os dois pontos viraram um só." : "O ponto ficou preso na curva.", "aviso")
    return true
  }
  function colunasDoArrasto(chave, inicio) {
    const id = chave.slice(2)
    const s = e.sistema
    const lista = []
    const mover = (pid) => {
      if (pid === "O") return
      const i = s.colunas.get(pid)
      lista.push({ coluna: i, base: s.q0[i], eixo: 0 }, { coluna: i + 1, base: s.q0[i + 1], eixo: 1 })
    }
    if (chave[0] === "p") mover(id)
    else {
      const c = curva(id)
      if (c.tipo === "circulo") {
        const [cx, cy] = P(c.pontos[0])
        const longe = Math.hypot(inicio[0] - cx, inicio[1] - cy)
        return [{ coluna: s.raios.get(c.id), raio: true, centro: [cx, cy], base: c.raio, longe }]
      }
      for (const p of c.pontos) mover(p)
    }
    return lista
  }
  // A captura pode falhar (clique sintético, ponteiro que já saiu): o gesto continua sem ela.
  const capturar = (ev) => {
    try {
      svg.setPointerCapture(ev.pointerId)
    } catch {
      // sem captura, o arrasto só segue enquanto o mouse está na prancheta
    }
  }
  const soltar = (ev) => {
    try {
      if (svg.hasPointerCapture?.(ev.pointerId)) svg.releasePointerCapture(ev.pointerId)
    } catch {
      // nada a soltar
    }
  }
  svg.addEventListener("pointerdown", (ev) => {
    // Sem rolar: com a prancheta meio fora da tela, o foco rolaria a página, e o ponto lido depois
    // cairia longe de onde o mouse clicou.
    const [u, v] = doMouse(ev)
    svg.focus({ preventScroll: true })
    const mundo = doPx(u, v)
    if (ev.button === 1 || ev.button === 2 || e.espaco) {
      e.gesto = { tipo: "pan", inicio: [u, v], vista: { ...e.vista } }
      capturar(ev)
      ev.preventDefault()
      return
    }
    if (ev.button !== 0) return
    const cotaAlvo = ev.target.closest?.("[data-cota]")
    const sinalAlvo = ev.target.closest?.("[data-sinal]")
    // Duplo clique numa cota, em qualquer ferramenta: a caixinha abre ao soltar o botão. O dblclick
    // do navegador não serve: o desenho é refeito no primeiro clique, e o texto clicado já é outro.
    if (cotaAlvo && cotaAlvo.dataset.cota !== "_") {
      const id = cotaAlvo.dataset.cota
      const agora = performance.now()
      if (e.ultimaCota?.id === id && agora - e.ultimaCota.t < ES_DUPLO_MS) {
        e.ultimaCota = null
        e.abrirNoSoltar = id
        if (e.ferramenta !== "selecionar") return
      } else e.ultimaCota = { id, t: agora }
    }
    if (e.ferramenta === "analise") {
      e.renomearNoSoltar = marcarAnalise(u, v)
      montarPainel()
      desenhar()
      return
    }
    if (e.ferramenta === "selecionar") {
      const analise = analiseNoMouse(u, v)
      if (analise) {
        // Um clique escolhe (Delete apaga); duplo clique troca o nome.
        const agora = performance.now()
        if (e.ultimaAnalise?.id === analise && agora - e.ultimaAnalise.t < ES_DUPLO_MS) {
          e.ultimaAnalise = null
          e.renomearNoSoltar = analise
        } else e.ultimaAnalise = { id: analise, t: agora }
        if (!ev.shiftKey) e.sel.clear()
        e.sel.add(`a:${analise}`)
        montarPainel()
        desenhar()
        return
      }
      if (cotaAlvo && cotaAlvo.dataset.cota !== "_") {
        const chave = `d:${cotaAlvo.dataset.cota}`
        if (!ev.shiftKey) e.sel.clear()
        e.sel.add(chave)
        e.gesto = { tipo: "mover_cota", id: cotaAlvo.dataset.cota, inicio: [u, v], moveu: false, foto: JSON.stringify(e.esboco) }
        capturar(ev)
        montarPainel()
        desenhar()
        return
      }
      if (sinalAlvo) {
        const chave = `r:${sinalAlvo.dataset.sinal}`
        if (!ev.shiftKey) e.sel.clear()
        e.sel.has(chave) && ev.shiftKey ? e.sel.delete(chave) : e.sel.add(chave)
        montarPainel()
        desenhar()
        return
      }
      const chave = oQueTemAqui(u, v)
      // Duplo clique numa curva: escolhe o contorno inteiro (as curvas ligadas pelas pontas).
      if (chave?.startsWith("c:")) {
        const agora = performance.now()
        if (e.ultimaCurva?.chave === chave && agora - e.ultimaCurva.t < ES_DUPLO_MS) {
          e.ultimaCurva = null
          const ligadas = contornoDe(chave.slice(2)).map((id) => `c:${id}`)
          if (ev.shiftKey || ev.ctrlKey) for (const k of ligadas) e.sel.add(k)
          else e.sel = new Set(ligadas)
          montarPainel()
          desenhar()
          return
        }
        e.ultimaCurva = { chave, t: agora }
      }
      if (chave) {
        if (ev.shiftKey || ev.ctrlKey) e.sel.has(chave) ? e.sel.delete(chave) : e.sel.add(chave)
        else if (!e.sel.has(chave)) e.sel = new Set([chave])
        e.gesto = {
          tipo: "arrastar",
          chave,
          inicio: [u, v],
          mundo,
          moveu: false,
          foto: JSON.stringify(e.esboco),
          colunas: e.sistema ? colunasDoArrasto(chave, mundo) : [],
          q: e.sistema ? Float64Array.from(e.sistema.q0) : null,
        }
        capturar(ev)
        montarPainel()
        desenhar()
        return
      }
      if (!ev.shiftKey) e.sel.clear()
      e.gesto = { tipo: "janela", inicio: [u, v], atual: [u, v], ativo: false }
      capturar(ev)
      montarPainel()
      desenhar()
      return
    }
    if (e.ferramenta === "medir") {
      const chave = comCentro(oQueTemAqui(u, v), u, v)
      if (!chave) {
        e.picks = []
        e.medida = null
        avisar("")
      } else {
        // Terceiro clique (ou um par que não se mede) começa de novo.
        if (e.picks.length >= 2 || (e.picks.length === 1 && e.picks[0] !== chave && !cotaDosPicks([...e.picks, chave]))) e.picks = []
        if (!e.picks.includes(chave)) e.picks.push(chave)
        medirPicks()
      }
      montarPainel()
      desenhar()
      return
    }
    if (e.ferramenta === "cota" || e.ferramenta.startsWith("r:")) {
      const chave = e.ferramenta === "cota" ? comCentro(oQueTemAqui(u, v), u, v) : oQueTemAqui(u, v)
      if (e.ferramenta === "cota") {
        if (chave) {
          if (!e.picks.includes(chave)) e.picks.push(chave)
          if (e.picks.length > 2) e.picks = [chave]
          if (!cotaDosPicks(e.picks) && e.picks.length === 2) e.picks = [chave]
        } else if (e.picks.length && cotaDosPicks(e.picks)) {
          porCota(mundo)
        }
        desenhar()
        return
      }
      if (chave && !e.picks.includes(chave)) e.picks.push(chave)
      const tipo = e.ferramenta.slice(2)
      if (aplicarRestricao(tipo, e.picks)) {
        e.picks = []
        montarPainel()
      }
      desenhar()
      return
    }
    if (ES_EDICAO.has(e.ferramenta)) {
      cliqueDeEdicao(u, v, mundo, ev)
      montarPainel()
      desenhar()
      return
    }
    cliqueDeDesenho(u, v)
    montarPainel()
    desenhar()
  })
  svg.addEventListener("pointermove", (ev) => {
    const [u, v] = doMouse(ev)
    e.mouse = doPx(u, v)
    const gesto = e.gesto
    if (gesto?.tipo === "pan") {
      e.vista.cx = gesto.vista.cx - (u - gesto.inicio[0]) / e.vista.esc
      e.vista.cy = gesto.vista.cy + (v - gesto.inicio[1]) / e.vista.esc
      desenhar()
      return
    }
    if (gesto?.tipo === "janela") {
      gesto.atual = [u, v]
      gesto.ativo = Math.hypot(u - gesto.inicio[0], v - gesto.inicio[1]) > ES_ARRASTO_PX
      desenhar()
      return
    }
    if (gesto?.tipo === "mover_cota") {
      if (Math.hypot(u - gesto.inicio[0], v - gesto.inicio[1]) > ES_ARRASTO_PX) gesto.moveu = true
      if (gesto.moveu) {
        const c = e.esboco.cotas.find((x) => x.id === gesto.id)
        if (c) c.lugar = doPx(u, v)
        desenhar()
      }
      return
    }
    if (gesto?.tipo === "arrastar") {
      if (!gesto.moveu && Math.hypot(u - gesto.inicio[0], v - gesto.inicio[1]) <= ES_ARRASTO_PX) return
      gesto.moveu = true
      if (!e.sistema || !gesto.colunas.length) return
      const [x, y] = doPx(u, v)
      const dx = x - gesto.mundo[0]
      const dy = y - gesto.mundo[1]
      const alvos = gesto.colunas.map((c) => {
        if (c.raio) return { coluna: c.coluna, valor: Math.max(c.base + Math.hypot(x - c.centro[0], y - c.centro[1]) - c.longe, 1e-3) }
        return { coluna: c.coluna, valor: c.base + (c.eixo === 0 ? dx : dy) }
      })
      gesto.q = esArrastar(e.sistema, gesto.q, alvos)
      e.esboco = esComQ(e.sistema, gesto.q)
      // Ponto arrastado até outro ponto ou curva: ao soltar, junta (ou fica preso na curva).
      gesto.alvo = gesto.chave.startsWith("p:") ? alvoDoSoltar(u, v, gesto.chave.slice(2)) : null
      desenhar()
      return
    }
    if (e.ferramenta === "selecionar" || ES_ESCOLHA.has(e.ferramenta) || e.ferramenta.startsWith("r:") || ES_EDICAO.has(e.ferramenta)) {
      const antes = e.perto
      const analise = e.ferramenta === "selecionar" || e.ferramenta === "analise" ? analiseNoMouse(u, v) : null
      const ate = e.ferramenta === "cota" || e.ferramenta === "medir"
      e.perto = analise ? `a:${analise}` : ate ? comCentro(oQueTemAqui(u, v), u, v) : oQueTemAqui(u, v)
      e.encaixe = null
      if (antes !== e.perto || e.ferramenta === "cota") desenhar()
      else if (e.mouse) infoXY.textContent = `x ${esNum(e.mouse[0], 2)}   y ${esNum(e.mouse[1], 2)} mm`
      return
    }
    const fora = new Set(e.desenho?.de ? [e.desenho.de] : [])
    e.encaixe = encaixar(u, v, fora)
    desenhar()
  })
  svg.addEventListener("pointerup", (ev) => {
    const gesto = e.gesto
    e.gesto = null
    if (e.abrirNoSoltar) {
      const id = e.abrirNoSoltar
      e.abrirNoSoltar = null
      // Depois do clique inteiro: o foco já parou na prancheta e não volta a sair da caixinha.
      setTimeout(() => editarCota(id), 0)
    }
    if (e.renomearNoSoltar) {
      const id = e.renomearNoSoltar
      e.renomearNoSoltar = null
      setTimeout(() => renomearAnalise(id), 0)
    }
    if (!gesto) return
    soltar(ev)
    if (gesto.tipo === "janela") {
      if (gesto.ativo) {
        const [u0, v0] = gesto.inicio
        const [u1, v1] = gesto.atual
        const r = [Math.min(u0, u1), Math.min(v0, v1), Math.max(u0, u1), Math.max(v0, v1)]
        const cruzando = u1 < u0
        const chaves = [
          ...Object.keys(e.esboco.pontos).filter((p) => p !== "O").map((p) => `p:${p}`),
          ...e.esboco.curvas.map((c) => `c:${c.id}`),
        ]
        for (const k of chaves) if (dentroDaJanela(k, r, cruzando)) e.sel.add(k)
      }
      montarPainel()
      desenhar()
      return
    }
    if (gesto.tipo === "mover_cota" && gesto.moveu) {
      guardar(gesto.foto)
      enviar()
      return
    }
    if (gesto.tipo === "arrastar" && gesto.moveu) {
      guardar(gesto.foto)
      if (gesto.alvo && juntarAoSoltar(gesto.chave.slice(2), gesto.alvo)) return
      depoisDeMudar()
    }
  })
  svg.addEventListener("dblclick", () => {
    if (e.desenho) {
      e.desenho = null
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
      const fator = Math.exp(-ev.deltaY * 0.0015)
      e.vista.esc = Math.min(Math.max(e.vista.esc * fator, 0.01), 500)
      const [x2, y2] = doPx(u, v)
      e.vista.cx += x - x2
      e.vista.cy += y - y2
      desenhar()
    },
    { passive: false },
  )
  svg.addEventListener("pointerleave", () => {
    e.mouse = null
    e.perto = null
    desenhar()
  })

  // ---- teclado ----------------------------------------------------------------------------------
  svg.addEventListener("keydown", (ev) => {
    const tecla = ev.key.toLowerCase()
    const ctrl = ev.ctrlKey || ev.metaKey
    if (ev.key === " ") {
      e.espaco = true
      ev.preventDefault()
      return
    }
    if (ctrl && tecla === "z" && !ev.shiftKey) desfazer()
    else if (ctrl && (tecla === "y" || (tecla === "z" && ev.shiftKey))) refazer()
    else if (ctrl && tecla === "c") copiarEscolha()
    else if (ctrl && tecla === "v") colarRecorte()
    else if (ev.key === "Escape") {
      if (e.conflito) e.conflito = null
      else if (e.desenho || e.picks.length) {
        e.desenho = null
        e.picks = []
        e.medida = null
      } else if (e.ferramenta !== "selecionar") trocarFerramenta("selecionar")
      else e.sel.clear()
      avisar("")
      montarPainel()
      desenhar()
    } else if (ev.key === "Delete" || ev.key === "Backspace") apagar()
    else if (ev.key === "Enter" && e.sel.size === 1 && [...e.sel][0].startsWith("d:")) {
      editarCota([...e.sel][0].slice(2))
    } else if (ev.key === "Enter" && e.sel.size === 1 && [...e.sel][0].startsWith("a:")) {
      renomearAnalise([...e.sel][0].slice(2))
    }
    else if (!ctrl && /^[0-9.,]$/.test(ev.key) && digitarMedida(ev.key)) {
      // abriu a caixinha com o número
    } else if (!ctrl && !ev.altKey) {
      const ferramentas = { l: "linha", c: "circulo", a: "arco", t: "arco_tangente", p: "ponto", d: "cota", x: "aparar", w: "estender", g: "filete", o: "deslocar", s: "espelhar", k: "analise" }
      const restricoes = { h: "horizontal", v: "vertical", i: "coincidente", e: "igual", m: "ponto_medio" }
      if (tecla === "r") trocarFerramenta(ev.shiftKey ? "retangulo_centro" : "retangulo")
      else if (ferramentas[tecla]) trocarFerramenta(ferramentas[tecla])
      else if (restricoes[tecla]) botaoDeRestricao(restricoes[tecla])
      else if (tecla === "u") {
        unirContornos()
        montarPainel()
        desenhar()
      } else if (tecla === "q") alternarConstrucao()
      else if (tecla === "f") enquadrar()
      else return
    } else return
    ev.preventDefault()
  })
  svg.addEventListener("keyup", (ev) => {
    if (ev.key === " ") e.espaco = false
  })

  // ---- botões -----------------------------------------------------------------------------------
  // Tab confirma a medida e passa para a próxima cota (Shift+Tab, para a anterior), como num CAD.
  function cotaVizinha(id, paraTras) {
    const lista = e.esboco.cotas.filter((c) => !c.oculta).map((c) => c.id)
    if (!lista.length) return null
    const i = lista.indexOf(id)
    const n = lista.length
    return lista[(((i < 0 ? 0 : i + (paraTras ? -1 : 1)) % n) + n) % n]
  }
  function tabNaCota(paraTras) {
    const id = e.cotaEditando
    if (!id) return
    if (!editor.confirmar()) return // a medida não serve: a caixinha fica, com o motivo
    const seguinte = cotaVizinha(id, paraTras)
    if (seguinte) setTimeout(() => editarCota(seguinte), 0)
  }
  const editor = criarEditorVivo(area, {
    depoisDoTeclado: () => svg.focus({ preventScroll: true }),
    aoTab: (paraTras) => tabNaCota(paraTras),
    aoFechar: () => {
      e.cotaEditando = null
    },
  })
  // Os ícones entram nos botões; o título vira o nome lido por leitor de tela.
  raiz.querySelectorAll("[data-icone]").forEach((b) => {
    const rotulo = b.textContent.trim()
    if (rotulo) b.insertAdjacentHTML("afterbegin", esIcone(b.dataset.icone))
    else b.innerHTML = esIcone(b.dataset.icone)
    if (!rotulo && b.title) b.setAttribute("aria-label", b.title.split(":")[0].split(" (")[0])
  })
  raiz.querySelectorAll(".es-seta").forEach((b) => {
    b.innerHTML = `<svg viewBox="0 0 10 10" aria-hidden="true">${ES_ICONES.seta}</svg>`
    b.addEventListener("click", (ev) => {
      ev.stopPropagation()
      const menu = raiz.querySelector(`[data-menu="${b.dataset.abre}"]`)
      const abrir = menu.hidden
      fecharMenus()
      menu.hidden = !abrir
    })
  })
  caixa.addEventListener("pointerdown", (ev) => {
    if (!ev.target.closest?.(".es-grupo")) fecharMenus()
  })
  // Depois de um botão, as teclas voltam para o desenho (L, R, D... seguem funcionando).
  const focarDesenho = () => svg.focus({ preventScroll: true })
  raiz.querySelectorAll("[data-f]").forEach((b) =>
    b.addEventListener("click", () => {
      trocarFerramenta(b.dataset.f)
      focarDesenho()
    }),
  )
  raiz.querySelectorAll("[data-r]").forEach((b) =>
    b.addEventListener("click", () => {
      fecharMenus()
      botaoDeRestricao(b.dataset.r)
      focarDesenho()
    }),
  )
  const acoes = {
    desfazer,
    refazer,
    enquadrar,
    construcao: alternarConstrucao,
    unir: () => {
      fecharMenus()
      unirContornos()
    },
    tela: () => {
      if (document.fullscreenElement) document.exitFullscreen?.()
      else caixa.requestFullscreen?.()
    },
  }
  raiz.querySelectorAll("[data-a]").forEach((b) =>
    b.addEventListener("click", () => {
      acoes[b.dataset.a]()
      montarPainel()
      desenhar()
      if (b.dataset.a !== "tela") focarDesenho()
    }),
  )
  chaveSinais.addEventListener("change", () => desenhar())
  document.addEventListener("fullscreenchange", () => {
    const botao = raiz.querySelector('[data-a="tela"]')
    const cheia = Boolean(document.fullscreenElement)
    botao.innerHTML = esIcone(cheia ? "sair_da_tela" : "tela")
    botao.title = cheia ? "Sair da tela cheia (Esc)" : "Tela cheia (Esc sai)"
    setTimeout(() => desenhar(), 0)
  })

  // ---- Python → aqui ----------------------------------------------------------------------------
  e.receber = (dados) => {
    if (dados.esboco && dados.versao > e.versao) {
      if (e.versao >= 0) guardar()
      const novo = esCopiar(dados.esboco)
      novo.pontos = novo.pontos ?? {}
      novo.pontos.O = [0, 0]
      for (const chave of ["curvas", "restricoes", "cotas", "variaveis"]) novo[chave] = novo[chave] ?? []
      e.esboco = novo
      e.sel = new Set([...e.sel].filter(existe))
      atualizarSistema()
    }
    if (dados.versao > e.versao) e.versao = dados.versao
    if (!e.sistema) atualizarSistema()
    e.problemas = dados.problemas ?? []
    e.marcas = dados.marcas ?? null
    if (e.verAjuste !== dados.ajustar) {
      e.verAjuste = dados.ajustar
      setTimeout(() => enquadrar(), 0)
    }
    montarPainel()
    desenhar()
  }

  trocarFerramenta("selecionar")
  new ResizeObserver(() => desenhar()).observe(svg)
  // Para depurar no console: o estado da prancheta fica no elemento dela.
  caixa.estadoDoEsboco = e
  return e
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  let estado = ES_ESTADOS.get(parentElement)
  if (!estado) {
    estado = esCriar(parentElement)
    ES_ESTADOS.set(parentElement, estado)
  }
  estado.enviar = setTriggerValue
  estado.receber(data ?? {})
}
