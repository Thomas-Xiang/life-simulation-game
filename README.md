```markdown
# Life Atlas v2: State Chapters

A complete Vue + FastAPI life simulation game. Pick your path, balance your finances across 50 US states + DC, and see where life takes you.

---

## 🚀 Getting Started

### Prerequisites
* **Python:** 3.12+
* **Node.js:** 22.12+ (with `npm`)
* **OS:** macOS, Linux, or WSL

### Running the App
Extract the files into a **new directory**, navigate into `life-atlas-states`, and run:

```bash
bash ./start.sh

```

1. Open **`http://localhost:5173`** in your browser once Vite is ready. *(Internet required on first launch to install dependencies)*.
2. Press **`Ctrl+C`** in your terminal to safely stop both servers.

> **Note:** Closing the browser tab will **not** stop the backend servers. Port conflicts on `5173` or `8000` will not be force-killed automatically.

---

## ✨ What’s New in v2

* **Life Milestones:** Make choices at ages 18, post-training, 30, 40, 50, 60, and 65. Linked questions build continuous narrative chapters.
* **Autoplay:** Automatic simulation playback begins after confirming your final decision in a chapter.
* **Interactive Tile Map:** 50 states + DC featuring clickable tiles, relocation lines, and localized salary/cost scenarios (e.g., CA tech & NY finance boosts).
* **Deep Financial Engine:** Tracks cash, assets, mortgages, student/other debt, income, expenses, and family support.
* **Real Estate & Life Pathing:** College transfers, medical residency paths, home purchases with cash/income gates, and location-based family housing.
* **Compact Dashboard:** Desktop-optimized layout with inner-scrolling cards, tabbed journals/ledgers, and responsive fallback for mobile screens.
* **End-Game Features:** National survival curves, run exports, and a moderated memorial wall for past runs.

---

## ⚠️ Financial & Game Model Disclaimer

> **All financial data in this game is fictional.**

* **Synthetic Data:** Wages, state cost multipliers, taxes, tuition, housing prices, and interest rates are **simplified game parameters**, not real-world statistics or financial advice.
* **Simplified Rules:**
* Uses a flat 22% tax deduction across all states.
* Retirement income is capped at a flat $18,000/yr.
* Home values do not appreciate; market inflation and stock returns are not modeled.
* Cash support from family ends automatically at age 26.



### Mortality Data Provenance

* Mortality rates use the **SSA 2023 Period Life Table** (`backend/data/mortality.json`) applied uniformly across all states.
* Gender assignment is set to a neutral 50/50 baseline assumption.

---

## 💾 Saves & Data Storage

* Data is saved locally in `backend/var/states-v2.db` and browser local storage (`life-atlas-v2`).
* **v1 saves are NOT compatible.** Do not overwrite your old database.
* To use a custom database path:
```bash
export LIFE_ATLAS_V2_DB_PATH=/absolute/path/states-v2.db

```


* **Privacy Note:** Saved runs are bound to your browser token. Do not include sensitive personal details in public memorial posts.

---

## 🛠️ Customization & Developer Guide

### Key Project Files

| File | Purpose |
| --- | --- |
| `backend/app/simulation.py` | Milestones, tuition, salaries, debt, and housing logic |
| `backend/data/states.json` | 51 state economic profiles and map coordinates |
| `backend/data/mortality.json` | SSA mortality probability data |
| `frontend/src/useLife.js` | Autoplay controls, simulation pause/resume, API states |
| `frontend/src/App.vue` | Dashboard, options, preview UI |

### Running Tests

```bash
# Backend pytest
cd backend && .venv/bin/python -m pytest tests -q && cd ..

# Launcher script unit tests
backend/.venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v

# Frontend build check
cd frontend && npm run build

```

---

## 🛡️ Moderation & Deployment

### Memorial Moderation CLI

Manage public memorial messages from the `backend/` directory:

```bash
python -m tools.moderate                     # List pending memorials
python -m tools.moderate --approve <ID>       # Approve a post
python -m tools.moderate --reject <ID>        # Reject a post

```

### Production Checklist

This project is configured for **local development**. Before hosting publicly:

1. Enable HTTPS and configure a reverse proxy (e.g., Nginx/Caddy).
2. Set up durable SQLite database backups and rate limiting.
3. Require authentication for administrative tools.
4. Run with a single backend worker (required for current in-memory rate limiting).
5. **Never** expose the Vite dev server directly to the public web.
