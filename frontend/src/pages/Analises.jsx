import { useEffect, useState } from 'react'
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts'
import { api, num, moeda, COR } from '../api'
import { Dica, Legenda, Carregando, Erro } from '../components/comuns'

const eixo = { stroke: COR.eixo, fontSize: 11, tickLine: false, axisLine: false }
const semRotulo = (l) => l

export default function Analises({ irPara }) {
  const [d, setD] = useState(null)
  const [erro, setErro] = useState(null)
  useEffect(() => { api.get('/api/analises').then(setD).catch((e) => setErro(e.message)) }, [])
  if (erro) return <Erro erro={erro} onIntegrar={() => irPara('integracao')} />
  if (!d) return <Carregando />

  return (
    <>
      <div className="topo">
        <div>
          <h1>Análises do Data Warehouse</h1>
          <p>Consultas nas views do DuckDB (modelo estrela) que cruzam ERP, caderno de campo e clima</p>
        </div>
      </div>

      <div className="grid g2">
        <div className="card">
          <div className="card-titulo"><div><h2>Pluviômetro da fazenda x API (mm, 30 dias)</h2>
            <p>mesmos dias comparados · diferenças grandes indicam chuva localizada ou pluviômetro com problema</p></div></div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={d.pluviometro_vs_api} margin={{ top: 8, right: 12, left: -10, bottom: 0 }} barGap={2}>
              <CartesianGrid stroke={COR.grid} vertical={false} />
              <XAxis dataKey="codigo" {...eixo} />
              <YAxis {...eixo} />
              <Tooltip content={<Dica unidade=" mm" formatarRotulo={semRotulo} />} cursor={{ fill: '#0000000a' }} />
              <Bar dataKey="chuva_api" name="API Open-Meteo" fill={COR.s1} radius={[4, 4, 0, 0]} maxBarSize={22} />
              <Bar dataKey="chuva_pluviometro" name="Pluviômetro" fill={COR.s3} radius={[4, 4, 0, 0]} maxBarSize={22} />
            </BarChart>
          </ResponsiveContainer>
          <Legenda itens={[{ nome: 'API Open-Meteo', cor: COR.s1 }, { nome: 'Pluviômetro (caderno de campo)', cor: COR.s3 }]} />
          <div className="tabela-wrap" style={{ marginTop: 12 }}>
            <table>
              <thead><tr><th>Talhão</th><th>Cidade</th><th className="num">Dias</th><th className="num">Diferença</th></tr></thead>
              <tbody>{d.pluviometro_vs_api.map((r) => (
                <tr key={r.codigo}><td>{r.codigo} · {r.nome}</td><td>{r.cidade}</td><td className="num">{r.dias_comparados}</td>
                  <td className="num">{r.diferenca_pct > 0 ? '+' : ''}{num(r.diferenca_pct, 1)}%{Math.abs(r.diferenca_pct) > 40 ? ' ⚠️' : ''}</td></tr>))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <div className="card-titulo"><div><h2>Custo por hectare - 90 dias (R$/ha)</h2><p>operações do ERP (MySQL) por tipo</p></div></div>
          <ResponsiveContainer width="100%" height={330}>
            <BarChart data={d.custo_hectare} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={COR.grid} horizontal={false} />
              <XAxis type="number" {...eixo} />
              <YAxis type="category" dataKey="codigo" {...eixo} width={56} />
              <Tooltip content={<Dica unidade="" formatarRotulo={semRotulo} />} cursor={{ fill: '#0000000a' }} />
              <Bar dataKey="irrigacao" name="Irrigação" stackId="c" fill={COR.s1} stroke="#fcfcfb" strokeWidth={1} />
              <Bar dataKey="pulverizacao" name="Pulverização" stackId="c" fill={COR.s2} stroke="#fcfcfb" strokeWidth={1} />
              <Bar dataKey="adubacao" name="Adubação" stackId="c" fill={COR.s3} stroke="#fcfcfb" strokeWidth={1} />
              <Bar dataKey="plantio" name="Plantio" stackId="c" fill={COR.s4} stroke="#fcfcfb" strokeWidth={1} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <Legenda itens={[{ nome: 'Irrigação', cor: COR.s1 }, { nome: 'Pulverização', cor: COR.s2 }, { nome: 'Adubação', cor: COR.s3 }, { nome: 'Plantio', cor: COR.s4 }]} />
        </div>

        <div className="card">
          <div className="card-titulo"><div><h2>Chuva x consumo por município (30 dias)</h2><p>média dos talhões · dado consolidado</p></div></div>
          <div className="tabela-wrap">
            <table>
              <thead><tr><th>Município</th><th className="num">Chuva</th><th className="num">ETc</th><th>Saldo</th></tr></thead>
              <tbody>{d.chuva_municipio.map((r) => {
                const saldo = r.chuva_media_30d - r.etc_media_30d
                return (
                  <tr key={r.cidade}><td>{r.cidade}/{r.uf}</td><td className="num">{num(r.chuva_media_30d, 0)} mm</td>
                    <td className="num">{num(r.etc_media_30d, 0)} mm</td>
                    <td style={{ minWidth: 140 }}>
                      <span style={{ fontVariantNumeric: 'tabular-nums' }}>{saldo >= 0 ? '▲ +' : '▼ '}{num(saldo, 0)} mm</span>
                      <div className="barra" style={{ marginTop: 4 }}><div style={{ width: `${Math.min(100, Math.abs(saldo))}%`, background: saldo >= 0 ? COR.s1 : COR.s2 }} /></div>
                    </td></tr>)
              })}</tbody>
            </table>
          </div>
          <h3 style={{ margin: '18px 0 8px' }}>Balanço médio por cultura</h3>
          <table>
            <thead><tr><th>Cultura</th><th className="num">Água média no solo</th><th className="num">Chuva</th><th className="num">ETc</th></tr></thead>
            <tbody>{d.balanco_cultura.map((r) => (
              <tr key={r.cultura}><td>{r.cultura}</td><td className="num">{num(r.agua_media_pct, 0)}%</td><td className="num">{num(r.chuva_30d, 0)} mm</td><td className="num">{num(r.etc_30d, 0)} mm</td></tr>))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="card-titulo"><div><h2>Ranking de pragas (30 dias)</h2><p>caderno de campo após padronização dos nomes</p></div></div>
          <div className="tabela-wrap">
            <table>
              <thead><tr><th>Praga</th><th>Cultura</th><th className="num">Ocorr.</th><th className="num">Talhões</th><th>Nível médio</th></tr></thead>
              <tbody>{d.ranking_pragas.map((r) => (
                <tr key={r.praga + r.cultura}><td><b>{r.praga}</b></td><td>{r.cultura}</td><td className="num">{r.ocorrencias}</td><td className="num">{r.talhoes_afetados}</td>
                  <td style={{ minWidth: 130 }}>{num(r.nivel_medio, 1)} <small style={{ color: '#8a887f' }}>(máx {r.nivel_maximo})</small>
                    <div className="barra"><div style={{ width: `${r.nivel_medio / 5 * 100}%`, background: r.nivel_medio >= 3 ? COR.critical : COR.s4 }} /></div></td></tr>))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <p className="fontes" style={{ marginTop: 16 }}>Custos totais: {moeda(d.custo_hectare.reduce((s, r) => s + r.custo_total, 0))} em 90 dias.</p>
    </>
  )
}
