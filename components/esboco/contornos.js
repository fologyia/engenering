// Os contornos fechados do esboço, para pintar o aço na hora (a conta de verdade é a do Python,
// core/esboco_regioes.py). Linhas e arcos que dividem pontas formam um contorno; o círculo é um
// contorno sozinho. Pintar com a regra par-ímpar dá o mesmo que lá: furo dentro de contorno.

function esArcoInfo(esboco, c) {
  const [cx, cy] = esboco.pontos[c.pontos[0]]
  const [ax, ay] = esboco.pontos[c.pontos[1]]
  const [bx, by] = esboco.pontos[c.pontos[2]]
  const r = Math.hypot(ax - cx, ay - cy)
  const ta = Math.atan2(ay - cy, ax - cx)
  const tb = Math.atan2(by - cy, bx - cx)
  let sw = (tb - ta) % (2 * Math.PI)
  if (sw < 0) sw += 2 * Math.PI
  return { cx, cy, r, ta, tb, sw }
}

const esPontas = (c) => (c.tipo === "linha" ? [c.pontos[0], c.pontos[1]] : [c.pontos[1], c.pontos[2]])

// { lacos: [[{curva, sentido}]], circulos: [id], soltas: [pid], bifurcacoes: [pid] }
function esContornos(esboco) {
  const abertas = esboco.curvas.filter((c) => !c.construcao && c.tipo !== "circulo")
  const circulos = esboco.curvas.filter((c) => !c.construcao && c.tipo === "circulo").map((c) => c.id)
  const vizinhos = new Map()
  for (const c of abertas) {
    const [a, b] = esPontas(c)
    if (!vizinhos.has(a)) vizinhos.set(a, [])
    if (!vizinhos.has(b)) vizinhos.set(b, [])
    vizinhos.get(a).push([c, 1])
    vizinhos.get(b).push([c, -1])
  }
  const soltas = []
  const bifurcacoes = []
  const ruins = new Set()
  for (const [no, lista] of vizinhos) {
    if (lista.length === 1) soltas.push(no)
    if (lista.length > 2) bifurcacoes.push(no)
    if (lista.length !== 2) ruins.add(no)
  }
  const usadas = new Set()
  const lacos = []
  for (const c of abertas) {
    if (usadas.has(c.id)) continue
    const [a, b] = esPontas(c)
    if (ruins.has(a) || ruins.has(b)) {
      usadas.add(c.id)
      continue
    }
    const laco = []
    let atual = c
    let sentido = 1
    let fechou = true
    for (let passos = 0; passos < abertas.length + 1; passos += 1) {
      usadas.add(atual.id)
      const [pa, pb] = esPontas(atual)
      const para = sentido === 1 ? pb : pa
      laco.push({ curva: atual.id, sentido })
      if (para === a) break
      if (ruins.has(para)) {
        fechou = false
        break
      }
      const seguinte = vizinhos.get(para).find(([outra]) => outra.id !== atual.id)
      if (!seguinte) {
        fechou = false
        break
      }
      ;[atual, sentido] = seguinte
    }
    if (fechou) lacos.push(laco)
  }
  return { lacos, circulos, soltas, bifurcacoes }
}

// O caminho SVG do aço: todos os contornos num caminho só, pintado par-ímpar.
function esCaminhoDoAco(esboco, px) {
  const { lacos, circulos } = esContornos(esboco)
  const porId = new Map(esboco.curvas.map((c) => [c.id, c]))
  const partes = []
  for (const laco of lacos) {
    let d = ""
    laco.forEach(({ curva, sentido }, i) => {
      const c = porId.get(curva)
      const [pa, pb] = esPontas(c)
      const de = sentido === 1 ? pa : pb
      const para = sentido === 1 ? pb : pa
      if (i === 0) {
        const [x, y] = px(...esboco.pontos[de])
        d += `M${x.toFixed(2)} ${y.toFixed(2)}`
      }
      const [x, y] = px(...esboco.pontos[para])
      if (c.tipo === "linha") d += `L${x.toFixed(2)} ${y.toFixed(2)}`
      else {
        const info = esArcoInfo(esboco, c)
        const [x0] = px(info.cx, info.cy)
        const [x1] = px(info.cx + info.r, info.cy)
        const r = Math.abs(x1 - x0)
        const grande = info.sw > Math.PI ? 1 : 0
        // No mundo o arco é anti-horário de a para b, e na tela continua anti-horário (o desenho não
        // é espelhado): no SVG, com y para baixo, isso é o sentido negativo, varre = 0.
        const varre = sentido === 1 ? 0 : 1
        d += `A${r.toFixed(2)} ${r.toFixed(2)} 0 ${grande} ${varre} ${x.toFixed(2)} ${y.toFixed(2)}`
      }
    })
    partes.push(`${d}Z`)
  }
  for (const id of circulos) {
    const c = porId.get(id)
    const [cx, cy] = esboco.pontos[c.pontos[0]]
    const [x, y] = px(cx, cy)
    const [x1] = px(cx + c.raio, cy)
    const r = Math.abs(x1 - x)
    partes.push(`M${(x - r).toFixed(2)} ${y.toFixed(2)}a${r.toFixed(2)} ${r.toFixed(2)} 0 1 0 ${(2 * r).toFixed(2)} 0a${r.toFixed(2)} ${r.toFixed(2)} 0 1 0 ${(-2 * r).toFixed(2)} 0Z`)
  }
  return partes.join("")
}
