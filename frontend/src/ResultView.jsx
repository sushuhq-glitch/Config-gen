import {
  Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'

const confClass = (label) =>
  ({ 'Very High': 'conf-very-high', High: 'conf-high', Medium: 'conf-medium', Low: 'conf-low' }[label] ||
    'conf-medium')

const pct = (v) => `${(v * 100).toFixed(1)}%`

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div
      style={{
        background: 'var(--bg-elevated)', border: '1px solid var(--border)',
        borderRadius: 8, padding: '8px 12px', fontSize: 12,
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: 4 }}>{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey}>
          {p.name}: <b>{typeof p.value === 'number' ? `${p.value.toFixed(1)}%` : p.value}</b>
        </div>
      ))}
    </div>
  )
}

export default function ResultView({ result, lastUpdated }) {
  const best = result.best
  const pick = best.pick
  const sim = best.simulation

  const outcomeData = [
    { name: 'Home win', value: sim.home_win * 100 },
    { name: 'Draw', value: sim.draw * 100 },
    { name: 'Away win', value: sim.away_win * 100 },
    { name: 'Over 2.5', value: sim.over_25 * 100 },
    { name: 'BTTS', value: sim.btts * 100 },
  ]
  const outcomeColors = ['#34d399', '#fbbf24', '#f87171', '#22d3ee', '#818cf8']

  const modelData = best.model_breakdown.map((m) => ({
    name: m.model.replace(' (Dixon-Coles)', '').replace(' (MLP)', ''),
    Home: m.probabilities['1x2_home'] * 100,
    Draw: m.probabilities['1x2_draw'] * 100,
    Away: m.probabilities['1x2_away'] * 100,
  }))

  const scoreData = sim.top_correct_scores.map(([score, p]) => ({
    name: score,
    value: p * 100,
  }))

  return (
    <>
      {/* ------------------------------------------------ hero pick card */}
      <div className="pick-hero">
        <div className="pick-header">
          <div>
            <div className="pick-match">
              {best.league} · {best.match_label} ·{' '}
              {new Date(best.kickoff_utc).toLocaleString()}
            </div>
            <div className="pick-title">{pick.selection}</div>
            <div className="pick-market">
              {pick.market} — best price {pick.offered_odds.toFixed(2)} @ {pick.bookmaker}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <span className={`conf-badge ${confClass(pick.confidence_label)}`}>
              ● {pick.confidence_label} confidence · {pick.confidence.toFixed(0)}/100
            </span>
            {lastUpdated && (
              <div className="live-note" style={{ justifyContent: 'flex-end', marginTop: 8 }}>
                <div className="status-dot" /> live · updated{' '}
                {lastUpdated.toLocaleTimeString()}
              </div>
            )}
          </div>
        </div>

        <div className="metrics">
          <div className="metric">
            <div className="label">Success probability</div>
            <div className="value accent">{pct(pick.estimated_probability)}</div>
            <div className="prob-bar">
              <div style={{ width: `${pick.estimated_probability * 100}%` }} />
            </div>
          </div>
          <div className="metric">
            <div className="label">Offered / Fair odds</div>
            <div className="value">
              {pick.offered_odds.toFixed(2)}
              <span style={{ fontSize: 13, color: 'var(--text-dim)' }}>
                {' '}/ {pick.fair_odds.toFixed(2)}
              </span>
            </div>
            <div className="sub">target was {best.target_odds.toFixed(2)}</div>
          </div>
          <div className="metric">
            <div className="label">Value margin</div>
            <div className={`value ${pick.value_margin_pct >= 0 ? 'green' : 'red'}`}>
              {pick.value_margin_pct >= 0 ? '+' : ''}
              {pick.value_margin_pct.toFixed(1)}%
            </div>
            <div className="sub">expected value vs fair price</div>
          </div>
          <div className="metric">
            <div className="label">Model agreement</div>
            <div className="value">{pct(pick.model_agreement)}</div>
            <div className="sub">across 6 model families</div>
          </div>
          <div className="metric">
            <div className="label">Kelly stake</div>
            <div className="value">{(pick.kelly_fraction * 100).toFixed(1)}%</div>
            <div className="sub">of bankroll (capped 25%)</div>
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------ reasoning */}
      <div className="panel">
        <h3>Why this pick</h3>
        <ul className="reasoning-list">
          {best.reasoning.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </div>

      {/* ------------------------------------------------------- factors */}
      <div className="grid-2">
        <div className="panel">
          <h3>Favorable factors</h3>
          {best.favorable_factors.length === 0 && (
            <p className="hint">No strong favorable factors detected.</p>
          )}
          {best.favorable_factors.map((f, i) => (
            <div key={i} className="factor fav">
              <div className="dot" />
              <div>
                <div className="name">{f.factor}</div>
                <div className="evidence">{f.evidence}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="panel">
          <h3>Risk factors</h3>
          {best.risk_factors.length === 0 && (
            <p className="hint">No major risk factors detected.</p>
          )}
          {best.risk_factors.map((f, i) => (
            <div key={i} className="factor risk">
              <div className="dot" />
              <div>
                <div className="name">{f.factor}</div>
                <div className="evidence">{f.evidence}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* -------------------------------------------------------- charts */}
      <div className="grid-2">
        <div className="panel">
          <h3>Monte Carlo outcome probabilities ({sim.runs.toLocaleString()} runs)</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={outcomeData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="name" tick={{ fill: 'var(--text-dim)', fontSize: 12 }} />
              <YAxis tick={{ fill: 'var(--text-dim)', fontSize: 12 }} unit="%" />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="value" name="Probability" radius={[6, 6, 0, 0]}>
                {outcomeData.map((_, i) => (
                  <Cell key={i} fill={outcomeColors[i]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="hint">
            Adjusted expected goals: {sim.home_expected_goals.toFixed(2)} –{' '}
            {sim.away_expected_goals.toFixed(2)} · avg {sim.avg_goals.toFixed(2)} goals,{' '}
            {sim.avg_corners.toFixed(1)} corners, {sim.avg_cards.toFixed(1)} cards per match.
          </p>
        </div>

        <div className="panel">
          <h3>Model breakdown (1X2)</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={modelData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="name"
                tick={{ fill: 'var(--text-dim)', fontSize: 10 }}
                interval={0}
                angle={-14}
                textAnchor="end"
                height={48}
              />
              <YAxis tick={{ fill: 'var(--text-dim)', fontSize: 12 }} unit="%" />
              <Tooltip content={<ChartTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="Home" stackId="a" fill="#34d399" />
              <Bar dataKey="Draw" stackId="a" fill="#fbbf24" />
              <Bar dataKey="Away" stackId="a" fill="#f87171" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h3>Most likely exact scores</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={scoreData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="name" tick={{ fill: 'var(--text-dim)', fontSize: 12 }} />
              <YAxis tick={{ fill: 'var(--text-dim)', fontSize: 12 }} unit="%" />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="value" name="Probability" fill="#22d3ee" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="panel">
          <h3>Alternative markets on this match</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Selection</th>
                <th>Odds</th>
                <th>Prob.</th>
                <th>Value</th>
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {best.alternatives.map((a, i) => (
                <tr key={i}>
                  <td>
                    <b>{a.selection}</b>
                    <div className="hint">{a.market}</div>
                  </td>
                  <td className="mono">{a.offered_odds.toFixed(2)}</td>
                  <td className="mono">{pct(a.estimated_probability)}</td>
                  <td>
                    <span className={`pill ${a.value_margin_pct >= 0 ? 'green' : 'red'}`}>
                      {a.value_margin_pct >= 0 ? '+' : ''}
                      {a.value_margin_pct.toFixed(1)}%
                    </span>
                  </td>
                  <td>
                    <span className={`pill ${a.confidence >= 65 ? 'green' : a.confidence >= 50 ? 'amber' : 'red'}`}>
                      {a.confidence_label}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ----------------------------------------------- data used */}
      <div className="panel">
        <h3>Key statistics used</h3>
        <div className="stats-grid">
          {Object.entries(best.stats_used).map(([k, v]) => (
            <div key={k} className="stat-item">
              <div className="k">{k}</div>
              <div className="v">{v}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ------------------------------------------- other matches */}
      {result.other_matches?.length > 0 && (
        <div className="panel">
          <h3>Best picks on other scanned matches</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Match</th>
                <th>Pick</th>
                <th>Odds</th>
                <th>Prob.</th>
                <th>Value</th>
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {result.other_matches.map((m, i) => (
                <tr key={i}>
                  <td>
                    <b>{m.match}</b>
                    <div className="hint">
                      {m.league} · {new Date(m.kickoff_utc).toLocaleString()}
                    </div>
                  </td>
                  <td>
                    <b>{m.selection}</b>
                    <div className="hint">{m.market}</div>
                  </td>
                  <td className="mono">{m.odds.toFixed(2)}</td>
                  <td className="mono">{pct(m.probability)}</td>
                  <td>
                    <span className={`pill ${m.value_margin_pct >= 0 ? 'green' : 'red'}`}>
                      {m.value_margin_pct >= 0 ? '+' : ''}
                      {m.value_margin_pct.toFixed(1)}%
                    </span>
                  </td>
                  <td>
                    <span className={`pill ${m.confidence >= 65 ? 'green' : m.confidence >= 50 ? 'amber' : 'red'}`}>
                      {m.confidence_label}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="disclaimer">{best.disclaimer}</div>
    </>
  )
}
