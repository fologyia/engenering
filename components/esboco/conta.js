// Contas das cotas: números, letras e + − × ÷ ^, sem eval. A mesma gramática de ler_conta em
// core/esboco.py: 2*d + 5, L/2, 2,5*b. O resultado é uma árvore que se avalia com as letras.

const ES_NOME = /^[A-Za-zÀ-ÖØ-öø-ÿ_][A-Za-zÀ-ÖØ-öø-ÿ0-9_]*/
const ES_NUMERO = /^(\d+(?:[.,]\d*)?(?:[eE][+-]?\d+)?|[.,]\d+(?:[eE][+-]?\d+)?)/
const ES_MAX_CARACTERES = 120

function esFichas(texto) {
  const fichas = []
  let i = 0
  while (i < texto.length) {
    const c = texto[i]
    if (/\s/.test(c)) {
      i += 1
      continue
    }
    if ("+-*/^()".includes(c)) {
      fichas.push(["op", c])
      i += 1
      continue
    }
    const resto = texto.slice(i)
    const numero = ES_NUMERO.exec(resto)
    if (numero) {
      fichas.push(["n", numero[0].replace(",", ".")])
      i += numero[0].length
      continue
    }
    const nome = ES_NOME.exec(resto)
    if (nome) {
      fichas.push(["v", nome[0]])
      i += nome[0].length
      continue
    }
    throw new Error(`Não entendi “${c}” na conta “${texto}”.`)
  }
  return fichas
}

function lerConta(textoBruto) {
  const texto = String(textoBruto ?? "").trim()
  if (texto.length > ES_MAX_CARACTERES) throw new Error(`A conta passa de ${ES_MAX_CARACTERES} caracteres.`)
  const fichas = esFichas(texto)
  if (!fichas.length) throw new Error("A conta está vazia.")
  let i = 0
  const olhar = () => fichas[i]
  const op = (...ops) => {
    const f = fichas[i]
    if (f && f[0] === "op" && ops.includes(f[1])) {
      i += 1
      return f[1]
    }
    return null
  }
  function soma() {
    let no = termo()
    let o
    while ((o = op("+", "-")) !== null) no = { t: o, f: [no, termo()] }
    return no
  }
  function termo() {
    let no = unario()
    let o
    while ((o = op("*", "/")) !== null) no = { t: o, f: [no, unario()] }
    return no
  }
  function unario() {
    if (op("-") !== null) return { t: "neg", f: [unario()] }
    if (op("+") !== null) return unario()
    return potencia()
  }
  function potencia() {
    const base = atomo()
    if (op("^") !== null) return { t: "^", f: [base, unario()] }
    return base
  }
  function atomo() {
    const f = olhar()
    if (!f) throw new Error(`A conta “${texto}” termina no meio.`)
    i += 1
    if (f[0] === "n") return { t: "n", v: Number(f[1]) }
    if (f[0] === "v") return f[1] === "pi" ? { t: "n", v: Math.PI } : { t: "v", nome: f[1] }
    if (f[1] === "(") {
      const no = soma()
      if (op(")") === null) throw new Error(`Falta fechar o parêntese em “${texto}”.`)
      return no
    }
    throw new Error(`“${f[1]}” fora do lugar na conta “${texto}”.`)
  }
  const no = soma()
  if (i < fichas.length) throw new Error(`Sobrou “${fichas[i][1]}” no fim da conta “${texto}”.`)
  return no
}

function letrasDaConta(no, saida = new Set()) {
  if (no.t === "v") saida.add(no.nome)
  for (const filho of no.f ?? []) letrasDaConta(filho, saida)
  return saida
}

function avaliarConta(no, valores) {
  if (no.t === "n") return no.v
  if (no.t === "v") {
    if (!(no.nome in valores)) throw new Error(`A letra ${no.nome} não tem valor.`)
    return valores[no.nome]
  }
  if (no.t === "neg") return -avaliarConta(no.f[0], valores)
  const a = avaliarConta(no.f[0], valores)
  const b = avaliarConta(no.f[1], valores)
  if (no.t === "+") return a + b
  if (no.t === "-") return a - b
  if (no.t === "*") return a * b
  if (no.t === "/") return b === 0 ? NaN : a / b
  return a ** b
}

const nomeValido = (nome) => ES_NOME.test(nome) && ES_NOME.exec(nome)[0] === nome && nome !== "pi"

// O valor que a letra nova precisa ter para a conta dar `alvo` com as outras letras como estão.
// Secante a partir do alvo: acerta direto as contas de primeiro grau (2*d, d+5, L/2).
function valorDaLetraNova(no, letra, valores, alvo) {
  const f = (v) => avaliarConta(no, { ...valores, [letra]: v }) - alvo
  let a = alvo || 1
  let b = a * 1.1 + 1e-3
  let fa = f(a)
  let fb = f(b)
  for (let k = 0; k < 40 && Number.isFinite(fa) && Number.isFinite(fb); k += 1) {
    if (Math.abs(fb) <= 1e-12 * Math.max(Math.abs(alvo), 1)) return b
    if (fb === fa) break
    const c = b - (fb * (b - a)) / (fb - fa)
    a = b
    fa = fb
    b = c
    fb = f(b)
  }
  return Number.isFinite(fb) && Math.abs(fb) <= 1e-9 * Math.max(Math.abs(alvo), 1) ? b : alvo
}
