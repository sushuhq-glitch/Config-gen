# BetEdge Pro — Piattaforma di Analisi per Scommesse Sportive

Piattaforma professionale, scalabile e modulare che analizza eventi sportivi (calcio, con architettura pronta per altri sport) e individua **la scommessa con la probabilità di successo più alta compatibile con la quota richiesta dall'utente**, motivando ogni scelta con dati concreti.

> **Avvertenza**: le stime sono probabilistiche, mai certezze. Il sistema mostra sempre il livello di confidenza, i fattori di rischio e i limiti delle previsioni. Gioca responsabilmente. 18+.

## Come funziona

L'utente inserisce sport, campionato, partita (opzionale), data e **quota desiderata** (es. 1.30, 1.50, 2.00, 3.50). Il motore:

1. **Feature engineering** (`backend/app/analysis/features.py`) — converte il contesto della partita in aspettative di gol aggiustate (xG) applicando un modello fattoriale trasparente: forma (ultime 5/10/20), xG/xGA, rendimento casa/trasferta, infortuni e squalifiche pesati per importanza del giocatore, stanchezza/turnover/impegni europei, motivazioni, matchup tattici (pressing vs squadre in difficoltà sotto pressione, contropiede vs linea alta, palle inattive), meteo, viaggio, scontri diretti, arbitro. Ogni aggiustamento produce un `FactorImpact` con evidenza numerica mostrata all'utente.
2. **Ensemble ML** (`backend/app/ml/ensemble.py`) — sei famiglie di modelli: Random Forest, Gradient Boosting, XGBoost, LightGBM, rete neurale (MLP) e modello Bayesiano Poisson stile Dixon-Coles (CatBoost opzionale). Le probabilità vengono combinate con media pesata; la dispersione tra modelli diventa il segnale di "model agreement" usato nel punteggio di confidenza.
3. **Simulazione Monte Carlo** (`backend/app/simulation/monte_carlo.py`) — **100.000 partite virtuali** per fixture con processo di Poisson bivariato correlato, più processi correlati per corner e cartellini (profilo arbitro + posta in gioco). Produce probabilità per 1X2, doppia chance, over/under 1.5/2.5/3.5, BTTS, draw no bet, gol squadra, handicap asiatico, corner, cartellini e risultati esatti.
4. **Selezione della giocata** (`backend/app/markets/selector.py`) — confronta le probabilità stimate con le quote di 8 bookmaker, filtra i mercati compatibili con la quota richiesta e sceglie quello con la **probabilità di successo più alta** (non semplicemente la quota più vicina). Calcola value margin, quota fair, frazione di Kelly, movimenti di quota sospetti e un punteggio di confidenza composito.

### Output per ogni raccomandazione

Tipo di scommessa, quota e bookmaker, probabilità stimata, livello di affidabilità (Very High/High/Medium/Low), margine di valore (value bet), motivazione dettagliata in linguaggio naturale, fattori favorevoli e di rischio con evidenze, statistiche utilizzate, breakdown per modello ML, distribuzione dei risultati esatti, confronto con mercati alternativi e con le altre partite scansionate.

## Architettura

```
backend/
  app/
    core/         # configurazione + schemi Pydantic condivisi
    providers/    # layer dati: interfaccia astratta, provider demo deterministico,
                  # adapter API-Football (attivo con BETEDGE_API_FOOTBALL_KEY)
    analysis/     # feature engineering + modello fattoriale spiegabile
    ml/           # ensemble ML (RF, GB, XGBoost, LightGBM, MLP, Bayesian Poisson)
    simulation/   # Monte Carlo 100k run per partita
    markets/      # value bet, confidenza, selezione della giocata migliore
    api/          # REST API FastAPI
frontend/         # dashboard React (Vite + Recharts), tema chiaro/scuro, responsive
```

### Fonti dati

Il layer `providers` è vendor-neutral: qualsiasi fonte (API-Football, Football-Data, Understat, Sportradar, StatsBomb, Opta) si integra implementando `DataProvider`. Senza credenziali il sistema usa il provider demo, che genera dati deterministici e internamente coerenti (incluse quote multi-bookmaker con margine realistico 2-7%), rendendo l'intera pipeline testabile. Con `BETEDGE_API_FOOTBALL_KEY` impostata si attiva l'adapter API-Football.

### Aggiornamento in tempo reale

Il frontend interroga `/api/fixtures/{id}/live` ogni 45 secondi: la pipeline completa (quote, formazioni, meteo) viene rieseguita e probabilità/suggerimenti si aggiornano automaticamente. Quando le formazioni non sono ufficiali il sistema lo segnala esplicitamente tra i fattori di rischio.

## Avvio

```bash
# Backend (Python 3.11+)
cd backend
pip install -r requirements.txt
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# al primo avvio l'ensemble ML viene addestrato (~30-40s)

# Frontend (Node 18+) — build servita direttamente dal backend
cd frontend
npm install
npm run build        # produce backend/static/, poi apri http://localhost:8000

# In alternativa, sviluppo con hot reload:
npm run dev          # http://localhost:5173 (proxy verso :8000)
```

## API principali

| Endpoint | Descrizione |
| --- | --- |
| `POST /api/analyze` | `{sport, league_id?, fixture_id?, date?, target_odds}` → migliore giocata motivata + alternative |
| `GET /api/fixtures?league_id=&date=&q=` | ricerca partite per campionato/data/squadra |
| `GET /api/fixtures/{id}/context` | contesto completo (forma, rosa, tattica, H2H, arbitro, meteo...) |
| `GET /api/fixtures/{id}/odds` | board quote multi-bookmaker con movimenti e CLV |
| `GET /api/fixtures/{id}/live` | ricalcolo in tempo reale della raccomandazione |
| `GET /api/history` | storico pronostici della sessione |

## Configurazione (variabili d'ambiente, prefisso `BETEDGE_`)

| Variabile | Default | Uso |
| --- | --- | --- |
| `BETEDGE_API_FOOTBALL_KEY` | — | attiva il provider API-Football |
| `BETEDGE_SIMULATION_RUNS` | `100000` | partite virtuali per fixture |
| `BETEDGE_ML_TRAINING_SAMPLES` | `12000` | corpus di addestramento dell'ensemble |
| `BETEDGE_ODDS_TOLERANCE` | `0.22` | distanza relativa massima dalla quota richiesta |

## Limiti dichiarati

- I modelli ML sono addestrati su un corpus generato dallo stesso processo generativo assunto dal motore; collegando risultati storici reali basta sostituire `_training_corpus` in `ml/ensemble.py`.
- Lo storico pronostici è in-memory (sostituire con un DB per la produzione).
- Nessuna previsione è garantita: il sistema espone sempre probabilità, incertezza tra modelli e fattori di rischio.
