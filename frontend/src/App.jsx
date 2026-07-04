import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api.js'
import ResultView from './ResultView.jsx'
import HistoryView from './HistoryView.jsx'

const QUICK_ODDS = [1.3, 1.5, 1.8, 2.0, 2.5, 3.5]
const LIVE_REFRESH_MS = 45000

export default function App() {
  const [theme, setTheme] = useState(
    () => localStorage.getItem('betedge-theme') || 'dark',
  )
  const [tab, setTab] = useState('analyze')
  const [health, setHealth] = useState(null)

  const [leagues, setLeagues] = useState([])
  const [leagueId, setLeagueId] = useState('')
  const [date, setDate] = useState('')
  const [search, setSearch] = useState('')
  const [fixtures, setFixtures] = useState([])
  const [fixtureId, setFixtureId] = useState('')
  const [targetOdds, setTargetOdds] = useState('1.50')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)
  const liveTimer = useRef(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('betedge-theme', theme)
  }, [theme])

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
    api.leagues().then(setLeagues).catch(() => {})
  }, [])

  useEffect(() => {
    let cancelled = false
    api
      .fixtures({ league_id: leagueId, date, q: search })
      .then((fx) => { if (!cancelled) setFixtures(fx) })
      .catch(() => { if (!cancelled) setFixtures([]) })
    return () => { cancelled = true }
  }, [leagueId, date, search])

  const runAnalysis = useCallback(async () => {
    const odds = parseFloat(targetOdds)
    if (!odds || odds <= 1) {
      setError('Enter a valid target odds value greater than 1.00')
      return
    }
    setLoading(true)
    setError('')
    try {
      const payload = {
        sport: 'football',
        target_odds: odds,
        league_id: leagueId || null,
        fixture_id: fixtureId || null,
        date: date || null,
      }
      const res = await api.analyze(payload)
      setResult(res)
      setLastUpdated(new Date())
      setTab('analyze')
    } catch (e) {
      setError(e.message)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }, [targetOdds, leagueId, fixtureId, date])

  // Live re-analysis: poll the pipeline so odds/lineup/weather moves are
  // reflected without user action.
  useEffect(() => {
    clearInterval(liveTimer.current)
    if (!result?.best) return
    liveTimer.current = setInterval(async () => {
      try {
        const fresh = await api.liveRefresh(
          result.best.fixture_id,
          result.best.target_odds,
        )
        setResult((prev) => (prev ? { ...prev, best: fresh } : prev))
        setLastUpdated(new Date())
      } catch { /* keep previous state */ }
    }, LIVE_REFRESH_MS)
    return () => clearInterval(liveTimer.current)
  }, [result?.best?.fixture_id, result?.best?.target_odds])

  const selectedFixture = useMemo(
    () => fixtures.find((f) => f.id === fixtureId),
    [fixtures, fixtureId],
  )

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">BE</div>
          <div>
            <h1>BetEdge Pro</h1>
            <span>Sports Betting Intelligence Platform</span>
          </div>
        </div>
        <div className="tabs">
          <button
            className={`tab ${tab === 'analyze' ? 'active' : ''}`}
            onClick={() => setTab('analyze')}
          >
            Analysis
          </button>
          <button
            className={`tab ${tab === 'history' ? 'active' : ''}`}
            onClick={() => setTab('history')}
          >
            Pick History
          </button>
        </div>
        <div className="topbar-right">
          <div className="status-pill">
            <div className="status-dot" />
            {health ? `Engine online · ${health.provider} feed` : 'Connecting…'}
          </div>
          <button
            className="icon-btn"
            title="Toggle theme"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          >
            {theme === 'dark' ? '☀' : '☾'}
          </button>
        </div>
      </header>

      {tab === 'history' ? (
        <HistoryView />
      ) : (
        <div className="main">
          <aside>
            <div className="panel">
              <h3>Bet Finder</h3>

              <div className="field">
                <label>Sport</label>
                <select value="football" disabled>
                  <option value="football">Football (Soccer)</option>
                </select>
              </div>

              <div className="field">
                <label>League</label>
                <select
                  value={leagueId}
                  onChange={(e) => { setLeagueId(e.target.value); setFixtureId('') }}
                >
                  <option value="">All leagues</option>
                  {leagues.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name} ({l.country})
                    </option>
                  ))}
                </select>
              </div>

              <div className="field">
                <label>Date</label>
                <input
                  type="date"
                  value={date}
                  onChange={(e) => { setDate(e.target.value); setFixtureId('') }}
                />
              </div>

              <div className="field">
                <label>Search team</label>
                <input
                  type="text"
                  placeholder="e.g. Inter, Arsenal…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>

              <div className="field">
                <label>
                  Match ({fixtures.length} available
                  {fixtureId ? ', 1 selected' : ', optional — leave empty to scan all'})
                </label>
                <div className="fixture-list">
                  {fixtures.slice(0, 40).map((f) => (
                    <button
                      key={f.id}
                      className={`fixture-item ${f.id === fixtureId ? 'selected' : ''}`}
                      onClick={() => setFixtureId(f.id === fixtureId ? '' : f.id)}
                    >
                      <div className="teams">
                        {f.home_team} vs {f.away_team}
                      </div>
                      <div className="meta">
                        {f.league} · {new Date(f.kickoff_utc).toLocaleString()}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="field">
                <label>Target odds</label>
                <input
                  type="number"
                  step="0.05"
                  min="1.01"
                  value={targetOdds}
                  onChange={(e) => setTargetOdds(e.target.value)}
                />
                <div className="odds-quick">
                  {QUICK_ODDS.map((o) => (
                    <button
                      key={o}
                      className={`odds-chip ${parseFloat(targetOdds) === o ? 'selected' : ''}`}
                      onClick={() => setTargetOdds(o.toFixed(2))}
                    >
                      {o.toFixed(2)}
                    </button>
                  ))}
                </div>
              </div>

              <button className="analyze-btn" onClick={runAnalysis} disabled={loading}>
                {loading
                  ? 'Analyzing…'
                  : fixtureId
                    ? 'Analyze this match'
                    : 'Find best bet across matches'}
              </button>

              <p className="hint" style={{ marginTop: 12 }}>
                The engine scans every market on{' '}
                {fixtureId && selectedFixture
                  ? `${selectedFixture.home_team} vs ${selectedFixture.away_team}`
                  : 'all filtered fixtures'}{' '}
                and returns the selection with the highest estimated success
                probability compatible with your target odds — backed by 100,000
                Monte Carlo simulations and a 6-model ML ensemble.
              </p>
            </div>
          </aside>

          <section className="results">
            {error && <div className="error-box">{error}</div>}

            {loading && (
              <div className="panel spinner-wrap">
                <div className="spinner" />
                <div>
                  Running feature engineering, ML ensemble and 100,000 match
                  simulations{fixtureId ? '' : ' per fixture'}…
                </div>
              </div>
            )}

            {!loading && !result && !error && (
              <div className="panel empty-state">
                <div className="big">◎</div>
                <h2>Set your target odds and run the engine</h2>
                <p>
                  BetEdge Pro analyses form (last 5/10/20), xG, squad
                  availability, tactics, head-to-head history, venue splits,
                  motivation, referee profile, weather and market movements —
                  then simulates 100,000 virtual matches to find the most
                  reliable selection at your price point.
                </p>
              </div>
            )}

            {!loading && result && (
              <ResultView result={result} lastUpdated={lastUpdated} />
            )}
          </section>
        </div>
      )}

      <footer className="footer">
        Estimates are probabilistic and never guaranteed. Gambling involves
        risk: bet responsibly, set limits, and only stake what you can afford
        to lose. 18+ · BetEdge Pro is an analytical tool, not betting advice.
      </footer>
    </div>
  )
}
