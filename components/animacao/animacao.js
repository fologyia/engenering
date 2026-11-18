// Tocador de animações no tempo. O Python calcula todos os instantes de uma vez (core/animacao.py);
// aqui só se toca o resultado: nada volta ao Python e a página não roda de novo enquanto toca.
//
// A cena vem em coordenadas do desenho (Y para cima) e tem:
//   tempos        instantes de cada quadro, em segundos, em ordem crescente;
//   canais        valores de cada canal em cada quadro (Float32, base64, quadro × canal);
//   escalas       nome, unidade, faixa e mapa de cores de cada grandeza;
//   formas        polígonos, linhas (com traços que andam), níveis, círculos e textos;
//   grade         células coloridas (calor numa seção), em Uint8 por quadro;
//   graficos      curvas no tempo (canais) e perfis ao longo de uma medida (canais por ponto).

const ESTADOS = new WeakMap()
//: Mapas sequenciais de um matiz só, do claro ao escuro (o claro é o menor valor).
const MAPAS = {
  calor: ["#fff1e6", "#fdd0b1", "#f9a878", "#f07d45", "#de5524", "#b93a13", "#8a270c", "#5c1a08"],
  agua: ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
  cinza: ["#f1f5f9", "#cbd5e1", "#94a3b8", "#64748b", "#334155"],
}
// Ordem fixa das séries: a cor segue a série, nunca a posição dela no gráfico.
const SERIES_CLARO = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
const SERIES_ESCURO = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9", "#e66767"]
const DURACAO_1X = 10 // s: em 1× o tempo inteiro passa em 10 segundos
const MARGEM = 14 // px em volta do desenho
const ALTURA_GRAFICO = 170 // px

// ---------------------------------------------------------------- contas puras (testadas no Node)

function hexParaRgb(hex) {
  const h = String(hex).replace("#", "")
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

// Cor de uma fração (0 a 1) num mapa: interpolação entre as paradas.
function corNoMapa(nome, fracao) {
  const paradas = (MAPAS[nome] ?? MAPAS.calor).map(hexParaRgb)
  const f = Math.min(1, Math.max(0, Number.isFinite(fracao) ? fracao : 0))
  const pos = f * (paradas.length - 1)
  const i = Math.min(paradas.length - 2, Math.floor(pos))
  const resto = pos - i
  const a = paradas[i]
  const b = paradas[i + 1]
  return [0, 1, 2].map((k) => Math.round(a[k] + (b[k] - a[k]) * resto))
}

function rgbTexto(rgb) {
  return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`
}

function fracaoNaEscala(escala, valor) {
  const faixa = escala.max - escala.min
  return faixa > 0 ? (valor - escala.min) / faixa : 0.5
}

// Número em português: vírgula decimal e ponto de milhar.
function formatar(valor, casas = 2) {
  if (!Number.isFinite(valor)) return "—"
  const c = Math.max(0, Math.min(6, casas))
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: c, maximumFractionDigits: c })
}

function bytesDe(b64) {
  const bin = atob(b64 || "")
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return bytes
}

function decodificarF32(b64) {
  const bytes = bytesDe(b64)
  return new Float32Array(bytes.buffer, 0, Math.floor(bytes.length / 4))
}

function decodificarI32(b64) {
  const bytes = bytesDe(b64)
  return new Int32Array(bytes.buffer, 0, Math.floor(bytes.length / 4))
}

// Posição (fracionária) de um instante na lista de tempos: 2,5 = no meio do 2º e do 3º quadro.
function posicaoDoTempo(tempos, t) {
  const n = tempos.length
  if (n < 2 || t <= tempos[0]) return 0
  if (t >= tempos[n - 1]) return n - 1
  let a = 0
  let b = n - 1
  while (b - a > 1) {
    const m = (a + b) >> 1
    if (tempos[m] <= t) a = m
    else b = m
  }
  const passo = tempos[b] - tempos[a]
  return a + (passo > 0 ? (t - tempos[a]) / passo : 0)
}

// Valor de um canal numa posição fracionária, interpolado entre os dois quadros vizinhos.
function valorNoCanal(canais, nCanais, nQuadros, canal, pos) {
  if (canal == null || canal < 0 || canal >= nCanais || nQuadros < 1) return NaN
  const p = Math.min(nQuadros - 1, Math.max(0, pos))
  const i = Math.floor(p)
  const j = Math.min(nQuadros - 1, i + 1)
  const a = canais[i * nCanais + canal]
  const b = canais[j * nCanais + canal]
  return a + (b - a) * (p - i)
}

function tempoTexto(t, unidade) {
  const u = unidade ?? { rotulo: "s", fator: 1, casas: 1 }
  return `t = ${formatar(t / (u.fator || 1), u.casas ?? 1)} ${u.rotulo}`
}

// Marcas "redondas" de um eixo: 1, 2 ou 5 vezes uma potência de 10.
function marcasDoEixo(min, max, alvo = 5) {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return []
  if (max - min <= 0) return [min]
  const bruto = (max - min) / alvo
  const pot = Math.pow(10, Math.floor(Math.log10(bruto)))
  const passo = [1, 2, 5, 10].map((m) => m * pot).find((p) => p >= bruto) ?? 10 * pot
  const marcas = []
  for (let v = Math.ceil(min / passo - 1e-9) * passo; v <= max + passo * 1e-9; v += passo) {
    marcas.push(Math.abs(v) < passo * 1e-9 ? 0 : v)
  }
  return marcas
}

// Casas decimais que mostram o passo das marcas sem arredondar (0,25 pede duas).
function casasDoPasso(marcas) {
  if (marcas.length < 2) return 1
  const passo = Math.abs(marcas[1] - marcas[0])
  for (let c = 0; c < 4; c++) {
    const escalado = passo * Math.pow(10, c)
    if (Math.abs(escalado - Math.round(escalado)) < 1e-6 * Math.max(1, escalado)) return c
  }
  return 4
}

// Faixa do eixo y de um gráfico: a dos valores, com folga, ou a pedida.
function faixaDoEixo(valores, pedida) {
  if (pedida && Number.isFinite(pedida.min) && Number.isFinite(pedida.max) && pedida.max > pedida.min) {
    return [pedida.min, pedida.max]
  }
  let min = Infinity
  let max = -Infinity
  for (const v of valores) {
    if (Number.isFinite(v)) {
      min = Math.min(min, v)
      max = Math.max(max, v)
    }
  }
  if (!Number.isFinite(min)) return [0, 1]
  if (max - min < 1e-12 * Math.max(1, Math.abs(max))) {
    const folga = Math.abs(max) > 0 ? Math.abs(max) * 0.05 : 1
    return [min - folga, max + folga]
  }
  const folga = (max - min) * 0.06
  return [min - folga, max + folga]
}

function pontoNoPoligono(p, pontos) {
  let dentro = false
  for (let i = 0, j = pontos.length - 1; i < pontos.length; j = i++) {
    const [xi, yi] = pontos[i]
    const [xj, yj] = pontos[j]
    if (yi > p[1] !== yj > p[1] && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) dentro = !dentro
  }
  return dentro
}

function distanciaAoSegmento(p, a, b) {
  const dx = b[0] - a[0]
  const dy = b[1] - a[1]
  const l2 = dx * dx + dy * dy
  const t = l2 > 0 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2)) : 0
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))
}

function comprimentoDaLinha(pts) {
  let total = 0
  for (let i = 1; i < pts.length; i++) total += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
  return total
}

// Ponto a uma distância s do começo da linha, com a direção do trecho: [x, y, dx, dy].
function pontoNaLinha(pts, s) {
  let resto = Math.max(0, s)
  for (let i = 1; i < pts.length; i++) {
    const dx = pts[i][0] - pts[i - 1][0]
    const dy = pts[i][1] - pts[i - 1][1]
    const l = Math.hypot(dx, dy)
    if (l <= 0) continue
    if (resto <= l || i === pts.length - 1) {
      const t = Math.min(1, resto / l)
      return [pts[i - 1][0] + t * dx, pts[i - 1][1] + t * dy, dx / l, dy / l]
    }
    resto -= l
  }
  const ultimo = pts[pts.length - 1]
  return [ultimo[0], ultimo[1], 1, 0]
}

// Onde ficam as pontas de seta ao longo de uma linha de comprimento total (px): uma a cada
// "espaco", deslocadas pela fase (px andados), longe das duas pontas.
function posicoesDasSetas(total, espaco, fase, folga) {
  const saida = []
  if (!(total > 2 * folga) || !(espaco > 0)) return saida
  let s = ((fase % espaco) + espaco) % espaco
  for (; s < total; s += espaco) if (s >= folga && s <= total - folga) saida.push(s)
  return saida
}

// Escala e deslocamento que põem a caixa do desenho no quadro, com a mesma escala em x e y.
function enquadrar(vista, largura, altura, margem = MARGEM) {
  const dx = Math.max(1e-12, vista.x1 - vista.x0)
  const dy = Math.max(1e-12, vista.y1 - vista.y0)
  const escala = Math.min((largura - 2 * margem) / dx, (altura - 2 * margem) / dy)
  const ox = (largura - escala * dx) / 2 - escala * vista.x0
  const oy = (altura + escala * dy) / 2 + escala * vista.y0
  return { escala, ox, oy }
}

// Altura do quadro para a largura dada, pela proporção do desenho.
function alturaDoQuadro(vista, largura, pedida) {
  if (Number.isFinite(pedida) && pedida > 0) return pedida
  const dx = Math.max(1e-12, vista.x1 - vista.x0)
  const dy = Math.max(1e-12, vista.y1 - vista.y0)
  const util = Math.max(50, largura - 2 * MARGEM)
  return Math.round(Math.min(460, Math.max(150, (util * dy) / dx + 2 * MARGEM)))
}

// ---------------------------------------------------------------- o tocador

function criar(raiz) {
  const e = {
    cena: null,
    id: null,
    pos: 0,
    tocando: false,
    velocidade: 1,
    fase: 0, // deslocamento dos traços que andam, em px
    ultimo: null,
    mouse: null,
    graficos: [],
  }
  const $ = (sel) => raiz.querySelector(sel)
  // A raiz pode ser uma sombra (shadow root): estilo e medida saem da caixa de dentro.
  const caixa = raiz.querySelector(".an")
  const botaoTocar = $('[data-a="tocar"]')
  const botaoInicio = $('[data-a="inicio"]')
  const barra = $('[data-c="quadro"]')
  const seletorVel = $('[data-c="velocidade"]')
  const rotTempo = $('[data-i="tempo"]')
  const canvas = $('[data-v="cena"]')
  const dica = $('[data-i="dica"]')
  const caixaEscalas = $('[data-i="escalas"]')
  const caixaGraficos = $('[data-i="graficos"]')
  const nota = $('[data-i="nota"]')

  function cor(nome, reserva) {
    const v = getComputedStyle(caixa).getPropertyValue(nome).trim()
    return v || reserva
  }
  function escuro() {
    const fundo = cor("--st-background-color", "#ffffff")
    const m = fundo.match(/\d+(\.\d+)?/g)
    let rgb
    if (fundo.startsWith("#")) rgb = hexParaRgb(fundo)
    else if (m && m.length >= 3) rgb = m.slice(0, 3).map(Number)
    else return false
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2] < 110
  }
  function seriesCores() {
    return escuro() ? SERIES_ESCURO : SERIES_CLARO
  }

  const nQuadros = () => e.cena?.tempos.length ?? 0
  const tempoAtual = () => {
    const ts = e.cena?.tempos ?? [0]
    const i = Math.floor(e.pos)
    const j = Math.min(ts.length - 1, i + 1)
    return ts[i] + (ts[j] - ts[i]) * (e.pos - i)
  }
  const valor = (canal, pos = e.pos) => valorNoCanal(e.cena.canais, e.cena.nCanais, nQuadros(), canal, pos)

  function preparar(dados) {
    const tempos = Array.isArray(dados.tempos) ? dados.tempos.map(Number) : []
    const nCanais = Number(dados.n_canais) || 0
    const canais = dados.canais_b64 ? decodificarF32(dados.canais_b64) : new Float32Array(0)
    let grade = null
    if (dados.grade) {
      const g = dados.grade
      grade = {
        xs: g.xs,
        ys: g.ys,
        celulas: decodificarI32(g.celulas_b64),
        quadros: bytesDe(g.quadros_b64),
        escala: g.escala,
        nome: g.nome ?? "",
      }
    }
    return {
      tempos,
      nCanais,
      canais,
      escalas: dados.escalas ?? [],
      formas: dados.formas ?? [],
      grade,
      graficos: dados.graficos ?? [],
      vista: dados.vista ?? { x0: 0, y0: 0, x1: 1, y1: 1 },
      altura: Number(dados.altura) || null,
      unidadeTempo: dados.unidade_tempo ?? { rotulo: "s", fator: 1, casas: 1 },
      nota: dados.nota ?? "",
    }
  }

  // ------------------------------------------------------------ desenho da cena
  function medirCanvas(c, altura) {
    const dpr = window.devicePixelRatio || 1
    const largura = c.clientWidth || c.parentElement?.clientWidth || 600
    c.style.height = `${altura}px`
    c.width = Math.round(largura * dpr)
    c.height = Math.round(altura * dpr)
    const ctx = c.getContext("2d")
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    return { ctx, largura, altura }
  }

  function corDaForma(f, pos) {
    if (f.canal != null && f.escala != null && e.cena.escalas[f.escala]) {
      const esc = e.cena.escalas[f.escala]
      return rgbTexto(corNoMapa(esc.cores, fracaoNaEscala(esc, valor(f.canal, pos))))
    }
    if (f.cor === "fundo") return cor("--st-background-color", "#ffffff")
    return f.cor ?? cor("--st-text-color", "#1e293b")
  }

  function desenharCena() {
    const c = e.cena
    if (!c) return
    const largura = canvas.clientWidth || caixa.clientWidth || 600
    const altura = alturaDoQuadro(c.vista, largura, c.altura)
    const { ctx } = medirCanvas(canvas, altura)
    const tr = enquadrar(c.vista, largura, altura)
    e.transformacao = tr
    const tela = (x, y) => [tr.ox + tr.escala * x, tr.oy - tr.escala * y]
    const texto = cor("--st-text-color", "#1e293b")
    const fundo = cor("--st-background-color", "#ffffff")
    ctx.fillStyle = fundo
    ctx.fillRect(0, 0, largura, altura)

    // as formas "de fundo" (o fluido em volta, o fluido nos furos) vão antes da grade de calor
    const ordem = [...c.formas.filter((f) => f.atras), null, ...c.formas.filter((f) => !f.atras)]
    for (const f of ordem) {
      if (f === null) {
        if (c.grade) desenharGrade(ctx, tela)
        continue
      }
      if (f.visivel != null && !(Math.abs(valor(f.visivel)) > 1e-9)) continue
      if (f.tipo === "poligono" && Array.isArray(f.pontos) && f.pontos.length > 2) {
        ctx.beginPath()
        f.pontos.forEach(([x, y], i) => (i ? ctx.lineTo(...tela(x, y)) : ctx.moveTo(...tela(x, y))))
        ctx.closePath()
        if (f.vazio !== true) {
          ctx.fillStyle = corDaForma(f, e.pos)
          ctx.fill()
        }
        if (f.hachura) hachurar(ctx, f.pontos.map(([x, y]) => tela(x, y)), f.cor_hachura ?? texto)
        if (f.contorno) {
          ctx.beginPath()
          f.pontos.forEach(([x, y], i) => (i ? ctx.lineTo(...tela(x, y)) : ctx.moveTo(...tela(x, y))))
          ctx.closePath()
          ctx.strokeStyle = f.contorno === "texto" ? texto : f.contorno
          ctx.lineWidth = f.espessura ?? 1.2
          ctx.stroke()
        }
      } else if (f.tipo === "linha" && Array.isArray(f.pontos) && f.pontos.length > 1) {
        ctx.beginPath()
        f.pontos.forEach(([x, y], i) => (i ? ctx.lineTo(...tela(x, y)) : ctx.moveTo(...tela(x, y))))
        ctx.strokeStyle = corDaForma(f, e.pos)
        ctx.lineWidth = f.largura ?? 2
        ctx.lineCap = f.ponta ?? "round"
        ctx.lineJoin = "round"
        if (f.fluxo != null && !f.setas) {
          // Traços que andam com a velocidade: o sentido é o do sinal do canal.
          ctx.setLineDash([f.traco ?? 10, f.vao ?? 10])
          const v = valor(f.fluxo)
          const sentido = v < 0 ? -1 : 1
          ctx.lineDashOffset = -sentido * (e.fases?.[f.fluxo] ?? 0)
          if (Math.abs(v) < 1e-12) ctx.setLineDash([])
        } else if (f.tracejado) {
          ctx.setLineDash([6, 5])
        } else {
          ctx.setLineDash([])
        }
        ctx.stroke()
        ctx.setLineDash([])
        if (f.setas) setasNaLinha(ctx, f, tela, texto)
      } else if (f.tipo === "nivel" && Array.isArray(f.caixa)) {
        const [x0, y0, x1, y1] = f.caixa
        const h = Math.max(0, Math.min(y1 - y0, valor(f.canal_altura)))
        const [ax, ay] = tela(x0, y0)
        const [bx, by] = tela(x1, y0 + h)
        ctx.fillStyle = f.canal_cor != null ? corDaForma({ ...f, canal: f.canal_cor }, e.pos) : (f.cor ?? "#3987e5")
        ctx.fillRect(ax, by, bx - ax, ay - by)
        if (h > 0) {
          ctx.strokeStyle = f.cor_superficie ?? "rgba(13,54,107,0.75)"
          ctx.lineWidth = 1.5
          ctx.beginPath()
          ctx.moveTo(ax, by)
          ctx.lineTo(bx, by)
          ctx.stroke()
        }
      } else if (f.tipo === "circulo") {
        const [x, y] = tela(f.x, f.y)
        const r = f.raio_px ?? Math.max(2, (f.raio ?? 0) * tr.escala)
        ctx.beginPath()
        ctx.arc(x, y, r, 0, 2 * Math.PI)
        if (f.vazio !== true) {
          ctx.fillStyle = corDaForma(f, e.pos)
          ctx.fill()
        }
        if (f.contorno) {
          ctx.strokeStyle = f.contorno === "texto" ? texto : f.contorno
          ctx.lineWidth = f.espessura ?? 1.5
          ctx.stroke()
        }
      } else if (f.tipo === "seta") {
        seta(ctx, f, tela, tr, texto, fundo)
      } else if (f.tipo === "cota") {
        cota(ctx, f, tela, texto, fundo)
      } else if (f.tipo === "texto") {
        let t = String(f.texto ?? "")
        if (f.canal != null) t = t.replace("{}", formatar(f.modulo ? Math.abs(valor(f.canal)) : valor(f.canal), f.casas ?? 1))
        const [x, y] = tela(f.x, f.y)
        ctx.font = `${f.negrito ? "600 " : ""}${f.tamanho ?? 12}px ${cor("--st-font", "sans-serif")}`
        ctx.textAlign = f.ancora ?? "center"
        ctx.textBaseline = f.base ?? "middle"
        ctx.lineJoin = "round"
        ctx.lineWidth = 4
        ctx.strokeStyle = fundo
        ctx.strokeText(t, x + (f.dx ?? 0), y + (f.dy ?? 0))
        ctx.fillStyle = f.cor ?? texto
        ctx.fillText(t, x + (f.dx ?? 0), y + (f.dy ?? 0))
      }
    }
    desenharDica()
  }

  // Pontas de seta ao longo da linha, no sentido do escoamento; andam junto com o fluido.
  function setasNaLinha(ctx, f, tela, texto) {
    const pts = f.pontos.map(([x, y]) => tela(x, y))
    let sinal = f.sentido ?? 1
    let fase = (f.espaco_setas ?? 90) / 2
    if (f.fluxo != null) {
      const v = valor(f.fluxo)
      if (!(Math.abs(v) > 1e-12)) return
      if (v < 0) sinal = -sinal
      fase += sinal * (e.fases?.[f.fluxo] ?? 0)
    }
    const tam = f.tamanho_setas ?? Math.max(8, (f.largura ?? 2) * 1.4 + 5)
    ctx.fillStyle = f.cor_setas ?? texto
    for (const s of posicoesDasSetas(comprimentoDaLinha(pts), f.espaco_setas ?? 90, fase, tam)) {
      const [x, y, dx, dy] = pontoNaLinha(pts, s)
      const ux = dx * sinal
      const uy = dy * sinal
      ctx.beginPath()
      ctx.moveTo(x + ux * tam * 0.55, y + uy * tam * 0.55)
      ctx.lineTo(x - ux * tam * 0.45 - uy * tam * 0.45, y - uy * tam * 0.45 + ux * tam * 0.45)
      ctx.lineTo(x - ux * tam * 0.45 + uy * tam * 0.45, y - uy * tam * 0.45 - ux * tam * 0.45)
      ctx.closePath()
      ctx.fill()
      if (f.contorno_setas) {
        ctx.strokeStyle = f.contorno_setas
        ctx.lineWidth = 1.2
        ctx.stroke()
      }
    }
  }

  function pontaDeSeta(ctx, x, y, ux, uy, tam) {
    ctx.beginPath()
    ctx.moveTo(x, y)
    ctx.lineTo(x - ux * tam - uy * tam * 0.5, y - uy * tam + ux * tam * 0.5)
    ctx.lineTo(x - ux * tam + uy * tam * 0.5, y - uy * tam - ux * tam * 0.5)
    ctx.closePath()
    ctx.fill()
  }

  // Seta de valor (calor que entra ou sai, vazão): o comprimento acompanha o módulo e a ponta
  // troca de lado com o sinal. Com "chega", o valor positivo chega na base (calor entrando).
  function seta(ctx, f, tela, tr, texto, fundo) {
    const v = f.canal != null ? valor(f.canal) : 1
    const ref = f.ref ?? 1
    const fracao = Math.min(1, Math.abs(v) / (ref || 1))
    if (!(fracao >= (f.minimo ?? 0.03))) return
    const [bx, by] = tela(f.x, f.y)
    const n = Math.hypot(f.nx, f.ny) || 1
    const ux = f.nx / n
    const uy = -f.ny / n
    const comprimento = f.comprimento_px ?? (f.comprimento ?? 1) * tr.escala
    const l = Math.max(f.minimo_px ?? 16, (f.proporcional === false ? 1 : fracao) * comprimento)
    const fx = bx + ux * l
    const fy = by + uy * l
    const naBase = f.chega ? v >= 0 : v < 0
    const larg = f.largura ?? 3
    const tinta = f.cor ?? "#de5524"
    ctx.strokeStyle = tinta
    ctx.fillStyle = tinta
    ctx.lineWidth = larg
    ctx.lineCap = "butt"
    const tam = Math.max(7, larg * 2.6)
    const corpo = () => {
      ctx.beginPath()
      if (naBase) {
        ctx.moveTo(fx, fy)
        ctx.lineTo(bx + ux * tam * 0.8, by + uy * tam * 0.8)
      } else {
        ctx.moveTo(bx, by)
        ctx.lineTo(fx - ux * tam * 0.8, fy - uy * tam * 0.8)
      }
    }
    const ponta = () => (naBase ? pontaDeSeta(ctx, bx, by, -ux, -uy, tam) : pontaDeSeta(ctx, fx, fy, ux, uy, tam))
    // contorno claro em volta: a seta aparece sobre o fluido quente (escuro) e sobre o fundo
    ctx.strokeStyle = fundo
    ctx.fillStyle = fundo
    ctx.lineWidth = larg + 4
    corpo()
    ctx.stroke()
    ponta()
    ctx.lineWidth = 3
    ctx.stroke()
    ctx.strokeStyle = tinta
    ctx.fillStyle = tinta
    ctx.lineWidth = larg
    corpo()
    ctx.stroke()
    ponta()
    if (f.rotulo) {
      let t = String(f.rotulo)
      if (f.canal != null) t = t.replace("{}", formatar(Math.abs(v), f.casas ?? 1))
      ctx.font = `11px ${cor("--st-font", "sans-serif")}`
      ctx.textAlign = Math.abs(ux) < 0.3 ? "center" : ux > 0 ? "left" : "right"
      ctx.textBaseline = Math.abs(uy) < 0.3 ? "middle" : uy > 0 ? "top" : "bottom"
      ctx.lineJoin = "round"
      ctx.lineWidth = 4
      ctx.strokeStyle = fundo
      const tx = fx + ux * 6
      const ty = fy + uy * 6
      ctx.strokeText(t, tx, ty)
      ctx.fillStyle = texto
      ctx.fillText(t, tx, ty)
    }
  }

  // Cota: linha de medida com as duas pontas e o texto no meio, afastada da peça.
  function cota(ctx, f, tela, texto, fundo) {
    const [ax, ay] = tela(...f.de)
    const [bx, by] = tela(...f.ate)
    const l = Math.hypot(bx - ax, by - ay)
    if (!(l > 4)) return
    const px = -(by - ay) / l
    const py = (bx - ax) / l
    const d = f.desloc ?? 0
    const a = [ax + px * d, ay + py * d]
    const b = [bx + px * d, by + py * d]
    ctx.save()
    ctx.globalAlpha = 0.8
    ctx.strokeStyle = texto
    ctx.fillStyle = texto
    ctx.lineWidth = 1
    ctx.beginPath()
    if (d) {
      ctx.moveTo(ax, ay)
      ctx.lineTo(a[0] + px * 3 * Math.sign(d), a[1] + py * 3 * Math.sign(d))
      ctx.moveTo(bx, by)
      ctx.lineTo(b[0] + px * 3 * Math.sign(d), b[1] + py * 3 * Math.sign(d))
    }
    ctx.moveTo(...a)
    ctx.lineTo(...b)
    ctx.stroke()
    const ux = (bx - ax) / l
    const uy = (by - ay) / l
    pontaDeSeta(ctx, a[0], a[1], -ux, -uy, 6)
    pontaDeSeta(ctx, b[0], b[1], ux, uy, 6)
    let angulo = Math.atan2(uy, ux)
    if (angulo > Math.PI / 2 || angulo < -Math.PI / 2) angulo += Math.PI
    ctx.translate((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    ctx.rotate(angulo)
    ctx.font = `11px ${cor("--st-font", "sans-serif")}`
    ctx.textAlign = "center"
    ctx.textBaseline = "bottom"
    ctx.globalAlpha = 1
    ctx.lineJoin = "round"
    ctx.lineWidth = 4
    ctx.strokeStyle = fundo
    ctx.strokeText(String(f.texto ?? ""), 0, -2)
    ctx.fillText(String(f.texto ?? ""), 0, -2)
    ctx.restore()
  }

  // Hachura em 45° dentro do polígono (isolamento, parede, face isolada).
  function hachurar(ctx, pts, cor) {
    const xs = pts.map((p) => p[0])
    const ys = pts.map((p) => p[1])
    const x0 = Math.min(...xs)
    const x1 = Math.max(...xs)
    const y0 = Math.min(...ys)
    const y1 = Math.max(...ys)
    ctx.save()
    ctx.beginPath()
    pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)))
    ctx.closePath()
    ctx.clip()
    ctx.strokeStyle = cor
    ctx.globalAlpha = 0.45
    ctx.lineWidth = 1
    ctx.beginPath()
    for (let k = x0 - (y1 - y0); k < x1; k += 6) {
      ctx.moveTo(k, y1)
      ctx.lineTo(k + (y1 - y0), y0)
    }
    ctx.stroke()
    ctx.restore()
  }

  function desenharGrade(ctx, tela) {
    const g = e.cena.grade
    const esc = e.cena.escalas[g.escala]
    if (!esc) return
    const n = g.celulas.length
    const nq = nQuadros()
    if (!n || !nq) return
    const tabela = []
    for (let k = 0; k < 256; k++) tabela.push(rgbTexto(corNoMapa(esc.cores, k / 255)))
    const i0 = Math.floor(e.pos)
    const i1 = Math.min(nq - 1, i0 + 1)
    const resto = e.pos - i0
    const ny = g.ys.length - 1
    for (let k = 0; k < n; k++) {
      const indice = g.celulas[k]
      const i = Math.floor(indice / ny)
      const j = indice - i * ny
      const a = g.quadros[i0 * n + k]
      const b = g.quadros[i1 * n + k]
      const q = Math.round(a + (b - a) * resto)
      const [x0, y1] = tela(g.xs[i], g.ys[j + 1])
      const [x1, y0] = tela(g.xs[i + 1], g.ys[j])
      ctx.fillStyle = tabela[q]
      // meio pixel a mais de cada lado: sem fresta branca entre células vizinhas
      ctx.fillRect(x0 - 0.3, y1 - 0.3, x1 - x0 + 0.6, y0 - y1 + 0.6)
    }
  }

  // O que está debaixo do mouse: célula da grade, polígono, círculo ou linha com valor.
  function itemNoMouse() {
    const c = e.cena
    const tr = e.transformacao
    if (!c || !tr || !e.mouse) return null
    const p = [(e.mouse[0] - tr.ox) / tr.escala, (tr.oy - e.mouse[1]) / tr.escala]
    for (let k = c.formas.length - 1; k >= 0; k--) {
      const f = c.formas[k]
      if (f.canal == null || f.escala == null || !c.escalas[f.escala]) continue
      const esc = c.escalas[f.escala]
      let pega = false
      if (f.tipo === "poligono") pega = pontoNoPoligono(p, f.pontos)
      else if (f.tipo === "circulo") pega = Math.hypot(p[0] - f.x, p[1] - f.y) * tr.escala <= (f.raio_px ?? 6) + 4
      else if (f.tipo === "linha") {
        for (let i = 1; i < f.pontos.length && !pega; i++) {
          pega = distanciaAoSegmento(p, f.pontos[i - 1], f.pontos[i]) * tr.escala <= Math.max(6, (f.largura ?? 2) / 2 + 3)
        }
      }
      if (pega) {
        return `${f.nome ? `${f.nome}: ` : ""}${esc.nome} = ${formatar(valor(f.canal), esc.casas ?? 1)} ${esc.unidade}`
      }
    }
    const g = c.grade
    if (g) {
      const i = g.xs.findIndex((x, k) => k < g.xs.length - 1 && p[0] >= x && p[0] <= g.xs[k + 1])
      const j = g.ys.findIndex((y, k) => k < g.ys.length - 1 && p[1] >= y && p[1] <= g.ys[k + 1])
      if (i >= 0 && j >= 0) {
        const indice = i * (g.ys.length - 1) + j
        const k = g.celulas.indexOf(indice)
        if (k >= 0) {
          const esc = c.escalas[g.escala]
          const nq = nQuadros()
          const q = g.quadros[Math.round(Math.min(nq - 1, e.pos)) * g.celulas.length + k]
          const v = esc.min + (q / 255) * (esc.max - esc.min)
          return `${g.nome || esc.nome} ≈ ${formatar(v, esc.casas ?? 1)} ${esc.unidade}`
        }
      }
    }
    return null
  }

  function desenharDica() {
    const t = itemNoMouse()
    if (!t) {
      dica.hidden = true
      return
    }
    dica.hidden = false
    dica.textContent = t
    const largura = canvas.clientWidth
    const x = e.mouse[0] + 14
    dica.style.left = `${Math.min(x, largura - dica.offsetWidth - 6)}px`
    dica.style.top = `${Math.max(4, e.mouse[1] - 30)}px`
  }

  // ------------------------------------------------------------ escalas (legenda das cores)
  function montarEscalas() {
    caixaEscalas.replaceChildren()
    const usadas = new Set()
    for (const f of e.cena.formas) if (f.escala != null && (f.canal != null || f.canal_cor != null)) usadas.add(f.escala)
    if (e.cena.grade) usadas.add(e.cena.grade.escala)
    for (const k of [...usadas].sort((a, b) => a - b)) {
      const esc = e.cena.escalas[k]
      if (!esc) continue
      const paradas = (MAPAS[esc.cores] ?? MAPAS.calor).join(",")
      const item = document.createElement("span")
      item.className = "escala"
      const nome = document.createElement("span")
      nome.textContent = `${esc.nome} (${esc.unidade})`
      const min = document.createElement("span")
      min.textContent = formatar(esc.min, esc.casas ?? 1)
      const faixa = document.createElement("span")
      faixa.className = "faixa"
      faixa.style.background = `linear-gradient(90deg, ${paradas})`
      const max = document.createElement("span")
      max.textContent = formatar(esc.max, esc.casas ?? 1)
      item.append(nome, min, faixa, max)
      caixaEscalas.append(item)
    }
  }

  // ------------------------------------------------------------ gráficos
  function montarGraficos() {
    caixaGraficos.replaceChildren()
    e.graficos = []
    for (const g of e.cena.graficos) {
      const caixa = document.createElement("div")
      caixa.className = "grafico"
      const titulo = document.createElement("div")
      titulo.className = "titulo"
      titulo.textContent = g.titulo ?? ""
      const legenda = document.createElement("div")
      legenda.className = "legenda"
      const c = document.createElement("canvas")
      caixa.append(titulo, legenda, c)
      caixaGraficos.append(caixa)
      const item = { def: g, caixa, legenda, canvas: c, mouse: null }
      c.addEventListener("mousemove", (ev) => {
        const r = c.getBoundingClientRect()
        item.mouse = [ev.clientX - r.left, ev.clientY - r.top]
        desenharGrafico(item)
      })
      c.addEventListener("mouseleave", () => {
        item.mouse = null
        desenharGrafico(item)
      })
      c.addEventListener("click", (ev) => {
        if (g.tipo === "perfil" || !item.area) return
        const r = c.getBoundingClientRect()
        const x = ev.clientX - r.left
        const t = item.area.t0 + ((x - item.area.x0) / (item.area.x1 - item.area.x0)) * (item.area.t1 - item.area.t0)
        pausar()
        irPara(posicaoDoTempo(e.cena.tempos, t))
      })
      e.graficos.push(item)
    }
  }

  function valoresDaSerie(s) {
    const nq = nQuadros()
    const v = []
    for (let i = 0; i < nq; i++) v.push(valor(s.canal, i))
    return v
  }

  function desenharGrafico(item) {
    const g = item.def
    const { ctx, largura, altura } = medirCanvas(item.canvas, g.altura ?? ALTURA_GRAFICO)
    const texto = cor("--st-text-color", "#1e293b")
    const fundo = cor("--st-background-color", "#ffffff")
    const grade = escuro() ? "rgba(255,255,255,0.10)" : "rgba(15,23,42,0.08)"
    const cores = seriesCores()
    ctx.fillStyle = fundo
    ctx.fillRect(0, 0, largura, altura)
    const perfil = g.tipo === "perfil"
    const series = g.series ?? []
    // valores de cada série: no tempo (um por quadro) ou ao longo da medida (um por ponto)
    let xs
    let linhas
    if (perfil) {
      xs = g.x ?? []
      linhas = series.map((s) => (Array.isArray(s.valores) ? s.valores : (s.canais ?? []).map((k) => valor(k))))
    } else {
      xs = e.cena.tempos.map((t) => t / (e.cena.unidadeTempo.fator || 1))
      linhas = series.map((s) => valoresDaSerie(s))
    }
    const todos = perfil && g.faixa ? [] : linhas.flat()
    const [ymin, ymax] = faixaDoEixo(todos, g.faixa)
    const xmin = xs.length ? xs[0] : 0
    const xmax = xs.length ? xs[xs.length - 1] : 1
    const marcasY = marcasDoEixo(ymin, ymax, 4)
    const casasY = casasDoPasso(marcasY)
    ctx.font = `11px ${cor("--st-font", "sans-serif")}`
    const larguraRotulo = Math.max(...marcasY.map((m) => ctx.measureText(formatar(m, casasY)).width), 20)
    const area = { x0: larguraRotulo + 10, x1: largura - 10, y0: 8, y1: altura - 34 }
    item.area = { ...area, t0: xmin, t1: xmax }
    const px = (x) => area.x0 + ((x - xmin) / (xmax - xmin || 1)) * (area.x1 - area.x0)
    const py = (y) => area.y1 - ((y - ymin) / (ymax - ymin || 1)) * (area.y1 - area.y0)
    // grade e eixos, discretos
    ctx.strokeStyle = grade
    ctx.lineWidth = 1
    ctx.fillStyle = texto
    ctx.globalAlpha = 1
    ctx.textAlign = "right"
    ctx.textBaseline = "middle"
    for (const m of marcasY) {
      const y = py(m)
      if (y < area.y0 - 1 || y > area.y1 + 1) continue
      ctx.beginPath()
      ctx.moveTo(area.x0, y)
      ctx.lineTo(area.x1, y)
      ctx.stroke()
      ctx.globalAlpha = 0.75
      ctx.fillText(formatar(m, casasY), area.x0 - 5, y)
      ctx.globalAlpha = 1
    }
    const marcasX = marcasDoEixo(xmin, xmax, 5)
    const casasX = casasDoPasso(marcasX)
    ctx.textAlign = "center"
    ctx.textBaseline = "top"
    ctx.globalAlpha = 0.75
    for (const m of marcasX) {
      const x = px(m)
      if (x < area.x0 - 1 || x > area.x1 + 1) continue
      ctx.fillText(formatar(m, casasX), x, area.y1 + 4)
    }
    const rotuloX = perfil ? (g.rotulo_x ?? "") : `tempo (${e.cena.unidadeTempo.rotulo})`
    ctx.fillText(rotuloX, (area.x0 + area.x1) / 2, area.y1 + 18)
    ctx.globalAlpha = 1
    ctx.strokeStyle = texto
    ctx.globalAlpha = 0.35
    ctx.beginPath()
    ctx.moveTo(area.x0, area.y1)
    ctx.lineTo(area.x1, area.y1)
    ctx.stroke()
    ctx.globalAlpha = 1
    // as curvas
    ctx.save()
    ctx.beginPath()
    ctx.rect(area.x0, area.y0 - 2, area.x1 - area.x0, area.y1 - area.y0 + 4)
    ctx.clip()
    series.forEach((s, k) => {
      const v = linhas[k]
      ctx.strokeStyle = s.cor ?? cores[(s.ordem ?? k) % cores.length]
      ctx.lineWidth = 2
      ctx.setLineDash(s.tracejado ? [5, 4] : [])
      ctx.globalAlpha = s.fraca ? 0.6 : 1
      ctx.beginPath()
      let comecou = false
      v.forEach((y, i) => {
        if (!Number.isFinite(y) || i >= xs.length) return
        const p = [px(xs[i]), py(y)]
        if (comecou) ctx.lineTo(...p)
        else ctx.moveTo(...p)
        comecou = true
      })
      ctx.stroke()
    })
    ctx.setLineDash([])
    ctx.globalAlpha = 1
    // marcos no tempo (estabiliza, equaliza, chega ao alvo): retas verticais com o nome
    if (!perfil) {
      const fator = e.cena.unidadeTempo.fator || 1
      ;(g.marcos ?? []).forEach((m, k) => {
        const x = px(m.tempo / fator)
        if (!(x >= area.x0 - 1 && x <= area.x1 + 1)) return
        ctx.strokeStyle = texto
        ctx.globalAlpha = 0.45
        ctx.setLineDash([4, 3])
        ctx.beginPath()
        ctx.moveTo(x, area.y0)
        ctx.lineTo(x, area.y1)
        ctx.stroke()
        ctx.setLineDash([])
        ctx.globalAlpha = 0.9
        ctx.font = `10.5px ${cor("--st-font", "sans-serif")}`
        const direita = x > (area.x0 + area.x1) / 2
        ctx.textAlign = direita ? "right" : "left"
        ctx.textBaseline = "top"
        ctx.lineJoin = "round"
        ctx.lineWidth = 3
        ctx.strokeStyle = fundo
        const y = area.y0 + 2 + 12 * (k % 3)
        const t = `${m.nome}: ${formatar(m.tempo / fator, e.cena.unidadeTempo.casas ?? 1)} ${e.cena.unidadeTempo.rotulo}`
        ctx.strokeText(t, x + (direita ? -3 : 3), y)
        ctx.fillStyle = texto
        ctx.fillText(t, x + (direita ? -3 : 3), y)
        ctx.globalAlpha = 1
      })
    }
    // limites (retas horizontais pedidas, como a temperatura que se quer alcançar)
    for (const lim of g.limites ?? []) {
      const y = py(lim.valor)
      if (y < area.y0 || y > area.y1) continue
      ctx.strokeStyle = texto
      ctx.globalAlpha = 0.55
      ctx.setLineDash([3, 3])
      ctx.beginPath()
      ctx.moveTo(area.x0, y)
      ctx.lineTo(area.x1, y)
      ctx.stroke()
      ctx.setLineDash([])
      ctx.textAlign = "left"
      ctx.textBaseline = "bottom"
      ctx.fillStyle = texto
      ctx.fillText(lim.nome ?? "", area.x0 + 4, y - 2)
      ctx.globalAlpha = 1
    }
    ctx.restore()
    // cursor do instante mostrado (só nos gráficos no tempo)
    let leitura = null
    if (!perfil) {
      const x = px(tempoAtual() / (e.cena.unidadeTempo.fator || 1))
      ctx.strokeStyle = texto
      ctx.globalAlpha = 0.5
      ctx.beginPath()
      ctx.moveTo(x, area.y0)
      ctx.lineTo(x, area.y1)
      ctx.stroke()
      ctx.globalAlpha = 1
      series.forEach((s, k) => {
        const y = valor(s.canal)
        if (!Number.isFinite(y)) return
        ctx.beginPath()
        ctx.arc(x, py(y), 4, 0, 2 * Math.PI)
        ctx.fillStyle = s.cor ?? cores[(s.ordem ?? k) % cores.length]
        ctx.fill()
        ctx.strokeStyle = fundo
        ctx.lineWidth = 2
        ctx.stroke()
      })
      leitura = series.map((s) => valor(s.canal))
    } else {
      leitura = linhas.map((v) => (v.length ? v[v.length - 1] : NaN))
    }
    // passar o mouse: linha e valores naquele ponto
    if (item.mouse && item.mouse[0] >= area.x0 && item.mouse[0] <= area.x1) {
      const xv = xmin + ((item.mouse[0] - area.x0) / (area.x1 - area.x0)) * (xmax - xmin)
      ctx.strokeStyle = texto
      ctx.globalAlpha = 0.3
      ctx.setLineDash([2, 3])
      ctx.beginPath()
      ctx.moveTo(item.mouse[0], area.y0)
      ctx.lineTo(item.mouse[0], area.y1)
      ctx.stroke()
      ctx.setLineDash([])
      ctx.globalAlpha = 1
      const pos = posicaoDoTempo(xs, xv)
      leitura = linhas.map((v) => {
        const i = Math.floor(pos)
        const j = Math.min(v.length - 1, i + 1)
        return v[i] + (v[j] - v[i]) * (pos - i)
      })
      item.dicaX = xv
    } else {
      item.dicaX = null
    }
    // legenda com o valor lido (o instante mostrado, ou onde o mouse está)
    item.legenda.replaceChildren()
    const unidade = g.unidade ? ` ${g.unidade}` : ""
    if (item.dicaX != null) {
      const onde = document.createElement("span")
      onde.textContent = perfil
        ? `${g.rotulo_curto ?? "x"} = ${formatar(item.dicaX, casasX + 1)}:`
        : `${tempoTexto(item.dicaX * (e.cena.unidadeTempo.fator || 1), e.cena.unidadeTempo)}:`
      item.legenda.append(onde)
    }
    series.forEach((s, k) => {
      const span = document.createElement("span")
      const marca = document.createElement("i")
      marca.style.background = s.cor ?? cores[(s.ordem ?? k) % cores.length]
      if (s.tracejado) marca.style.opacity = "0.6"
      span.append(marca)
      const v = leitura?.[k]
      const mostrar = series.length > 1 || item.dicaX != null || !perfil
      span.append(`${s.nome}${mostrar && Number.isFinite(v) && !(perfil && item.dicaX == null) ? `: ${formatar(v, g.casas ?? 1)}${unidade}` : ""}`)
      item.legenda.append(span)
    })
  }

  // ------------------------------------------------------------ tocar
  function atualizarTela() {
    barra.value = String(Math.round(e.pos))
    rotTempo.textContent = tempoTexto(tempoAtual(), e.cena?.unidadeTempo)
    botaoTocar.textContent = e.tocando ? "❚❚ Pausar" : "▶ Tocar"
    desenharCena()
    for (const g of e.graficos) desenharGrafico(g)
  }

  function irPara(pos) {
    e.pos = Math.max(0, Math.min(nQuadros() - 1, pos))
    atualizarTela()
  }

  function pausar() {
    e.tocando = false
    e.ultimo = null
    atualizarTela()
  }

  function passo(agora) {
    if (!e.tocando || !e.cena) return
    if (e.ultimo == null) e.ultimo = agora
    const real = Math.min(0.1, (agora - e.ultimo) / 1000)
    e.ultimo = agora
    const ts = e.cena.tempos
    const total = ts[ts.length - 1] - ts[0]
    const t = tempoAtual() + (real * total * e.velocidade) / DURACAO_1X
    // os traços andam de acordo com a velocidade de cada canal, em relação à maior
    for (const f of e.cena.formas) {
      if (f.fluxo == null) continue
      const ref = Math.max(1e-12, f.fluxo_ref ?? 1)
      e.fases[f.fluxo] = ((e.fases[f.fluxo] ?? 0) + (real * 60 * Math.abs(valor(f.fluxo))) / ref) % 1e6
    }
    if (t >= ts[ts.length - 1]) {
      e.pos = nQuadros() - 1
      pausar()
      return
    }
    e.pos = posicaoDoTempo(ts, t)
    atualizarTela()
    requestAnimationFrame(passo)
  }

  function tocar() {
    if (!e.cena || nQuadros() < 2) return
    if (e.tocando) {
      pausar()
      return
    }
    if (e.pos >= nQuadros() - 1) e.pos = 0
    e.tocando = true
    e.ultimo = null
    atualizarTela()
    requestAnimationFrame(passo)
  }

  botaoTocar.addEventListener("click", tocar)
  botaoInicio.addEventListener("click", () => {
    pausar()
    irPara(0)
  })
  barra.addEventListener("input", () => {
    e.tocando = false
    irPara(Number(barra.value))
  })
  seletorVel.addEventListener("change", () => {
    e.velocidade = Number(seletorVel.value) || 1
  })
  canvas.addEventListener("keydown", (ev) => {
    if (ev.key === " ") {
      ev.preventDefault()
      tocar()
    } else if (ev.key === "ArrowRight") {
      pausar()
      irPara(Math.floor(e.pos) + 1)
    } else if (ev.key === "ArrowLeft") {
      pausar()
      irPara(Math.ceil(e.pos) - 1)
    }
  })
  canvas.addEventListener("mousemove", (ev) => {
    const r = canvas.getBoundingClientRect()
    e.mouse = [ev.clientX - r.left, ev.clientY - r.top]
    desenharDica()
  })
  canvas.addEventListener("mouseleave", () => {
    e.mouse = null
    dica.hidden = true
  })

  e.receber = (dados) => {
    const id = String(dados.id ?? "")
    const nova = preparar(dados)
    const mesma = id && id === e.id
    e.cena = nova
    e.id = id
    if (!mesma) {
      e.pos = 0
      e.tocando = false
      e.fases = {}
    } else {
      e.pos = Math.min(e.pos, nQuadros() - 1)
    }
    barra.max = String(Math.max(0, nQuadros() - 1))
    nota.textContent = nova.nota
    montarEscalas()
    montarGraficos()
    atualizarTela()
    if (dados.tocar_ao_abrir && !mesma) tocar()
  }

  new ResizeObserver(() => {
    if (e.cena) atualizarTela()
  }).observe(caixa)
  return e
}

export default function (component) {
  const { data, parentElement } = component
  let estado = ESTADOS.get(parentElement)
  if (!estado) {
    estado = criar(parentElement)
    ESTADOS.set(parentElement, estado)
  }
  estado.receber(data ?? {})
}
