import { useEffect, useState } from 'react'
import { api } from './api.js'

const pct = (v) => `${(v * 100).toFixed(1)}%`

export default function HistoryView() {
  const [items, setItems] = useState([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    api
      .history()
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoaded(true))
  }, [])

  return (
    <div className="main" style={{ gridTemplateColumns: '1fr' }}>
      <div className="panel">
        <h3>Pick history (this session)</h3>
        {loaded && items.length === 0 && (
          <div className="empty-state">
            <div className="big">◷</div>
            <h2>No analyses yet</h2>
            <p>
              Every analysis you run is logged here with its target odds,
              recommended pick, estimated probability, value margin and
              confidence so you can track the engine over time.
            </p>
          </div>
        )}
        {items.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Match</th>
                <th>Target</th>
                <th>Pick</th>
                <th>Odds</th>
                <th>Prob.</th>
                <th>Value</th>
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {items.map((h) => (
                <tr key={h.id}>
                  <td className="hint">{new Date(h.created_at).toLocaleString()}</td>
                  <td>
                    <b>{h.match}</b>
                    <div className="hint">{h.league}</div>
                  </td>
                  <td className="mono">{h.target_odds.toFixed(2)}</td>
                  <td>
                    <b>{h.selection}</b>
                    <div className="hint">{h.market}</div>
                  </td>
                  <td className="mono">
                    {h.odds.toFixed(2)}
                    <div className="hint">{h.bookmaker}</div>
                  </td>
                  <td className="mono">{pct(h.probability)}</td>
                  <td>
                    <span className={`pill ${h.value_margin_pct >= 0 ? 'green' : 'red'}`}>
                      {h.value_margin_pct >= 0 ? '+' : ''}
                      {h.value_margin_pct.toFixed(1)}%
                    </span>
                  </td>
                  <td>
                    <span className={`pill ${h.confidence >= 65 ? 'green' : h.confidence >= 50 ? 'amber' : 'red'}`}>
                      {h.confidence_label}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
