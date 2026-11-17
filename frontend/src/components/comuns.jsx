import { ROTULO_SEV, ICONE_TIPO, dataCurta } from '../api'

export function Badge({ sev }) {
  return <span className={`badge sev-${sev}`}>{ROTULO_SEV[sev] || sev}</span>
}

export function Alerta({ a, mostrarTalhao = true, onAbrir }) {
  return (
    <div className={`alerta ${a.severidade}`}>
      <div className="alerta-topo">
        <span className="alerta-titulo">{ICONE_TIPO[a.tipo]} {a.titulo}</span>
        <Badge sev={a.severidade} />
      </div>
      {mostrarTalhao && (
        <div className="alerta-meta">
          <a href="#" onClick={(e) => { e.preventDefault(); onAbrir?.(a.talhao_id) }}>{a.talhao_codigo} · {a.talhao_nome}</a>
          {' '}· {a.cidade} · ref. {dataCurta(a.data_referencia)}
        </div>
      )}
      <div className="alerta-msg">{a.mensagem}</div>
      <div className="alerta-rec">{a.recomendacao}</div>
    </div>
  )
}

export function Kpi({ rotulo, valor, detalhe }) {
  return (
    <div className="kpi">
      <span>{rotulo}</span>
      <b>{valor}</b>
      {detalhe && <small>{detalhe}</small>}
    </div>
  )
}

// Tooltip padrão dos gráficos (texto sempre em tinta neutra; a cor só no marcador)
export function Dica({ active, payload, label, unidade = '', formatarRotulo = dataCurta }) {
  if (!active || !payload?.length) return null
  return (
    <div className="tooltip">
      <b>{formatarRotulo(label)}</b>
      {payload.filter((p) => p.value !== null && p.value !== undefined).map((p) => (
        <div key={p.dataKey}>
          <span><i style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 4, background: p.color, marginRight: 6 }} />{p.name}</span>
          <span>{Number(p.value).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}{unidade}</span>
        </div>
      ))}
    </div>
  )
}

export function Legenda({ itens }) {
  return (
    <div className="legenda">
      {itens.map((i) => (
        <span key={i.nome}><i className={i.linha ? 'linha' : ''} style={{ background: i.cor }} />{i.nome}</span>
      ))}
    </div>
  )
}

export function Carregando({ texto = 'Carregando...' }) {
  return <div className="vazio">{texto}</div>
}

export function Erro({ erro, onIntegrar }) {
  return (
    <div className="card vazio">
      <p>{erro}</p>
      {onIntegrar && <button className="btn btn-primario" onClick={onIntegrar}>Ir para Integração</button>}
    </div>
  )
}
