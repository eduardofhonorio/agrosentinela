import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine, ComposedChart,
} from 'recharts'
import { api, num, moeda, dataCurta, diaSemana, hojeISO, COR } from '../api'
import { Alerta, Kpi, Dica, Legenda, Carregando, Erro } from '../components/comuns'

const TIPO_OP = { IRRIGACAO: 'Irrigação', PULVERIZACAO: 'Pulverização', ADUBACAO: 'Adubação', COLHEITA: 'Colheita', PLANTIO: 'Plantio' }
const eixo = { stroke: COR.eixo, fontSize: 11, tickLine: false, axisLine: false }

export default function Talhao({ talhaoId, setTalhaoId, irPara }) {
  const [lista, setLista] = useState([])
  const [d, setD] = useState(null)
  const [erro, setErro] = useState(null)

  useEffect(() => {
    api.get('/api/talhoes').then((l) => {
      setLista(l)
      if (!talhaoId && l.length) setTalhaoId(l[0].talhao_key)
    }).catch((e) => setErro(e.message))
  }, [])

  useEffect(() => {
    if (!talhaoId) return
    setD(null)
    api.get(`/api/talhoes/${talhaoId}`).then(setD).catch((e) => setErro(e.message))
  }, [talhaoId])

  if (erro) return <Erro erro={erro} onIntegrar={() => irPara('integracao')} />

  const hoje = hojeISO()
  const serie = (d?.serie || []).map((r) => ({ ...r, dia: r.data.slice(0, 10) }))
  const atual = serie.find((r) => r.dia === hoje) || serie.filter((r) => !r.is_previsao).slice(-1)[0]
  const previsao = serie.filter((r) => r.is_previsao)
  const t = d?.talhao

  return (
    <>
      <div className="topo">
        <div>
          <h1>{t ? `${t.codigo} · ${t.nome}` : 'Talhões'}</h1>
          {t && <p>{t.cultura} · {num(t.area_ha, 1)} ha · {t.irrigado ? 'irrigado' : 'sequeiro'} · {t.propriedade} ({t.produtor}) · {t.cidade}/{t.uf}</p>}
        </div>
        <div className="topo-acoes">
          <select className="btn" value={talhaoId || ''} onChange={(e) => setTalhaoId(Number(e.target.value))}>
            {lista.map((l) => <option key={l.talhao_key} value={l.talhao_key}>{l.codigo} · {l.nome}</option>)}
          </select>
        </div>
      </div>

      {!d ? <Carregando /> : (
        <>
          <div className="kpis">
            <Kpi rotulo="Água disponível no solo" valor={`${num(atual?.agua_disponivel_pct, 0)}%`}
              detalhe={`${num(atual?.armazenamento_mm, 0)} de ${num(t.cad_mm, 0)} mm (CAD)`} />
            <Kpi rotulo="Chuva 30 dias" valor={`${num(d.resumo.chuva_30d, 0)} mm`} detalhe={`consumo da cultura (ETc): ${num(d.resumo.etc_30d, 0)} mm`} />
            <Kpi rotulo="Irrigação 30 dias" valor={`${num(d.resumo.irrigacao_30d, 0)} mm`} detalhe="lançada no ERP (MySQL)" />
            <Kpi rotulo="Mínima prevista (7d)" valor={`${num(d.resumo.temp_min_prev_7d, 1)} °C`} detalhe={`limite de geada: ${num(t.temp_geada, 1)} °C`} />
            <Kpi rotulo="Graus-dia (30 dias)" valor={num(d.resumo.graus_dia_30d, 0)} detalhe="acúmulo térmico da cultura" />
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-titulo"><div><h2>Próximos 7 dias</h2><p>previsão Open-Meteo + regras agronômicas</p></div></div>
            <div className="previsao">
              {previsao.map((p) => (
                <div className="dia" key={p.dia} style={p.risco_geada !== 'BAIXO' ? { borderColor: COR.critical } : {}}>
                  <b>{diaSemana(p.dia)} {dataCurta(p.dia)}</b>
                  <div className="temp">{num(p.temp_max, 0)}° / {num(p.temp_min, 0)}°</div>
                  <div>🌧️ {num(p.chuva_consolidada, 1)} mm{p.prob_chuva != null && ` · ${num(p.prob_chuva, 0)}%`}</div>
                  <div>💨 {num(p.vento_max_kmh, 0)} km/h</div>
                  {p.risco_geada !== 'BAIXO' && <span className="tag">❄️ geada: {p.risco_geada.toLowerCase()}</span>}
                  {p.risco_doenca !== 'BAIXO' && <span className="tag">🍂 doença: {p.risco_doenca.toLowerCase()}</span>}
                  {p.janela_pulverizacao && <span className="tag">🧪 apto pulverizar</span>}
                </div>
              ))}
            </div>
          </div>

          <div className="grid g2">
            <div className="card">
              <div className="card-titulo"><div><h2>Temperatura (°C)</h2><p>30 dias observados + 7 de previsão · linha tracejada = hoje</p></div></div>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={serie} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
                  <CartesianGrid stroke={COR.grid} vertical={false} />
                  <XAxis dataKey="dia" tickFormatter={dataCurta} {...eixo} minTickGap={24} />
                  <YAxis {...eixo} domain={[(min) => Math.floor(Math.min(min, t.temp_geada - 2)), 'auto']} allowDecimals={false} />
                  <Tooltip content={<Dica unidade=" °C" />} />
                  <ReferenceLine x={hoje} stroke={COR.eixo} strokeDasharray="4 4" />
                  <ReferenceLine y={t.temp_geada} stroke={COR.critical} strokeDasharray="6 4"
                    label={{ value: `limite geada ${num(t.temp_geada, 0)} °C`, position: 'insideBottomRight', fill: COR.critical, fontSize: 11 }} />
                  <Line dataKey="temp_max" name="Máxima" stroke={COR.s2} strokeWidth={2} dot={false} activeDot={{ r: 5, stroke: '#fff', strokeWidth: 2 }} />
                  <Line dataKey="temp_min" name="Mínima" stroke={COR.s1} strokeWidth={2} dot={false} activeDot={{ r: 5, stroke: '#fff', strokeWidth: 2 }} />
                </LineChart>
              </ResponsiveContainer>
              <Legenda itens={[{ nome: 'Máxima', cor: COR.s2, linha: true }, { nome: 'Mínima', cor: COR.s1, linha: true }, { nome: 'Limite de geada da cultura', cor: COR.critical, linha: true }]} />
            </div>

            <div className="card">
              <div className="card-titulo"><div><h2>Chuva x consumo da cultura (mm/dia)</h2><p>pluviômetro da fazenda (SQLite) prevalece sobre a estimativa da API</p></div></div>
              <ResponsiveContainer width="100%" height={250}>
                <ComposedChart data={serie} margin={{ top: 8, right: 12, left: -16, bottom: 0 }} barGap={2}>
                  <CartesianGrid stroke={COR.grid} vertical={false} />
                  <XAxis dataKey="dia" tickFormatter={dataCurta} {...eixo} minTickGap={24} />
                  <YAxis {...eixo} />
                  <Tooltip content={<Dica unidade=" mm" />} />
                  <ReferenceLine x={hoje} stroke={COR.eixo} strokeDasharray="4 4" />
                  <Bar dataKey="chuva_api" name="Chuva (API)" fill={COR.s1} radius={[4, 4, 0, 0]} maxBarSize={8} />
                  <Bar dataKey="chuva_pluviometro" name="Chuva (pluviômetro)" fill={COR.s3} radius={[4, 4, 0, 0]} maxBarSize={8} />
                  <Line dataKey="etc_mm" name="Consumo da cultura (ETc)" stroke={COR.s2} strokeWidth={2} dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
              <Legenda itens={[{ nome: 'Chuva - API Open-Meteo', cor: COR.s1 }, { nome: 'Chuva - pluviômetro', cor: COR.s3 }, { nome: 'Consumo da cultura (ETc)', cor: COR.s2, linha: true }]} />
            </div>

            <div className="card">
              <div className="card-titulo"><div><h2>Água disponível no solo (%)</h2><p>balanço hídrico: chuva efetiva + irrigação − ETc · abaixo de 50% = estresse</p></div></div>
              <ResponsiveContainer width="100%" height={230}>
                <AreaChart data={serie} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
                  <CartesianGrid stroke={COR.grid} vertical={false} />
                  <XAxis dataKey="dia" tickFormatter={dataCurta} {...eixo} minTickGap={24} />
                  <YAxis {...eixo} domain={[0, 100]} />
                  <Tooltip content={<Dica unidade="%" />} />
                  <ReferenceLine x={hoje} stroke={COR.eixo} strokeDasharray="4 4" />
                  <ReferenceLine y={50} stroke={COR.critical} strokeDasharray="6 4"
                    label={{ value: 'limite de estresse', position: 'insideBottomRight', fill: COR.critical, fontSize: 11 }} />
                  <Area dataKey="agua_disponivel_pct" name="Água disponível" stroke={COR.s1} strokeWidth={2} fill={COR.s1} fillOpacity={0.15} />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            <div className="card">
              <div className="card-titulo"><div><h2>Pragas - caderno de campo</h2><p>nível de infestação (0-5) após limpeza dos dados · nível 3 = controle</p></div></div>
              {d.pragas.length ? (
                <ResponsiveContainer width="100%" height={230}>
                  <BarChart data={d.pragas.map((p) => ({ ...p, dia: p.data.slice(0, 10) }))} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
                    <CartesianGrid stroke={COR.grid} vertical={false} />
                    <XAxis dataKey="dia" tickFormatter={dataCurta} {...eixo} />
                    <YAxis {...eixo} domain={[0, 5]} ticks={[0, 1, 2, 3, 4, 5]} />
                    <Tooltip content={({ active, payload }) => active && payload?.length ? (
                      <div className="tooltip"><b>{dataCurta(payload[0].payload.dia)}</b>
                        <div><span>{payload[0].payload.praga}</span><span>nível {payload[0].value}</span></div>
                        <div><span>{payload[0].payload.tecnico}</span></div></div>) : null} />
                    <ReferenceLine y={3} stroke={COR.critical} strokeDasharray="6 4" />
                    <Bar dataKey="nivel" name="Nível" fill={COR.s4} radius={[4, 4, 0, 0]} maxBarSize={18} />
                  </BarChart>
                </ResponsiveContainer>
              ) : <div className="vazio">Sem observações.</div>}
            </div>
          </div>

          <div className="grid g2" style={{ marginTop: 16 }}>
            <div className="card">
              <div className="card-titulo"><div><h2>Alertas deste talhão</h2></div></div>
              <div className="lista-alertas">
                {d.alertas.map((a) => <Alerta key={a._id} a={a} mostrarTalhao={false} />)}
                {!d.alertas.length && <div className="vazio">Nenhum alerta. 🌤️</div>}
              </div>
            </div>
            <div className="card">
              <div className="card-titulo"><div><h2>Operações recentes (ERP)</h2><p>{d.operacoes.length} lançamentos em 90 dias</p></div></div>
              <div className="tabela-wrap" style={{ maxHeight: 420, overflow: 'auto' }}>
                <table>
                  <thead><tr><th>Data</th><th>Tipo</th><th>Descrição</th><th className="num">Qtd.</th><th className="num">Custo</th></tr></thead>
                  <tbody>
                    {d.operacoes.slice(0, 40).map((o, i) => (
                      <tr key={i}><td>{dataCurta(o.data)}</td><td>{TIPO_OP[o.tipo] || o.tipo}</td><td>{o.descricao}</td>
                        <td className="num">{num(o.quantidade, 0)} {o.unidade}</td><td className="num">{moeda(o.custo)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  )
}
