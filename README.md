# Brokerhaus

Private hiring network for Egyptian securities brokerage firms (FRA-regulated).

A specialized platform where candidates describe what they actually do — by department and function — and HR teams from brokerage firms search and send private nominations. No CVs. No job posts. No public profiles.

## Features

- **Privacy-first hiring** — candidate identities hidden behind codes (e.g. `C-1042`)
- **17 brokerage departments** with 250+ functions mapped to real industry work
- **Match scoring** out of 100 (department + functions + seniority + experience + availability)
- **30-day nomination expiry** — no stale backlog
- **Two-state availability** — Available or Not Available (the second hides you completely)
- **Bilingual UI** (English / Egyptian Arabic) with localStorage persistence
- **Server-rendered** Flask + SQLite — no build step, deploys anywhere

## Quick start (local)

```bash
git clone <this-repo>
cd brokerhaus
pip install -r requirements.txt
python seed.py       # optional: load sample data
python app.py
```

Open http://localhost:5000

**Sample login credentials** (after running `seed.py` — password for all is `password123`):

Candidates:
- `ahmed.h@example.com` — Senior Equity Dealer
- `mona.k@example.com` — Back Office Manager
- `sara.a@example.com` — Equity Research Analyst
- `khaled.s@example.com` — Compliance Section Head
- + 2 more

Firms (HR side):
- `hr@pharos.com.eg`
- `hr@efghermes.com`

## Architecture

```
brokerhaus/
├── app.py              # Main Flask app, all routes
├── models.py           # SQLite schema + connection
├── auth.py             # Password hashing + sessions
├── matching.py         # Match scoring algorithm
├── seed.py             # Sample data loader
├── data/
│   └── catalog.py      # 17 departments + 250+ functions
├── templates/
│   ├── base.html
│   ├── landing.html
│   ├── signup.html
│   ├── login.html
│   ├── about.html
│   ├── error.html
│   ├── candidate/
│   │   ├── dashboard.html
│   │   └── profile.html
│   └── hr/
│       ├── dashboard.html
│       ├── search.html
│       └── nominations.html
└── static/
    ├── css/app.css
    └── js/app.js
```

## Database schema

- **users** — candidates and HR (email, password hash, role)
- **candidates** — extended profile (code, department, seniority, years, availability)
- **candidate_functions** — many-to-many (the actual matching surface)
- **firms** — HR firms (company name, verification)
- **nominations** — sent from firm → candidate (with 30-day expiry)
- **searches** — saved HR searches
- **sessions** — auth tokens

## Match scoring (100 points)

| Component | Points |
|-----------|--------|
| Department match | 20 |
| Required functions overlap | 35 |
| Seniority match | 15 |
| Total years experience | 15 |
| Function-specific years | 10 |
| Availability bonus | 5 |

## Deployment

### Render.com (recommended — free tier)

1. Push this repo to GitHub.
2. Create a new "Web Service" on Render, connect the GitHub repo.
3. Render auto-detects `render.yaml` and provisions everything (including the persistent disk for SQLite).
4. Done. Get your URL like `brokerhaus.onrender.com`.

The free tier sleeps after 15 min of inactivity (first request after sleep takes ~30s).

### Railway

```bash
railway init
railway up
```

Set `BROKERHAUS_DB=/data/brokerhaus.db` and attach a 1GB volume mounted at `/data`.

### PythonAnywhere (free tier)

1. Upload the project as a zip.
2. Create a new web app with manual Flask config; point WSGI to `app.app`.
3. Set up a virtualenv with `requirements.txt` installed.

### Docker

```bash
docker build -t brokerhaus .
docker run -p 8000:8000 -v $(pwd)/data:/app/data brokerhaus
```

## Environment variables

| Var | Default | Purpose |
|-----|---------|---------|
| `SECRET_KEY` | random | Flask session secret |
| `BROKERHAUS_DB` | `./brokerhaus.db` | SQLite path |
| `PORT` | 5000 | HTTP port |

## API surface (for future mobile/native clients)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/signup` | Create account |
| `POST` | `/api/login` | Sign in |
| `POST` | `/api/candidate/profile` | Update profile |
| `POST` | `/api/candidate/availability` | Toggle availability |
| `POST` | `/api/nomination/:id/respond` | Accept / decline |
| `POST` | `/api/search` | HR candidate search |
| `POST` | `/api/nominate` | HR sends nominations |
| `GET` | `/api/catalog/departments` | Department list |
| `GET` | `/api/catalog/functions/:dept_id` | Functions for a dept |
| `GET` | `/api/catalog/seniority` | Seniority levels |
| `GET` | `/health` | Health check |

## License

Proprietary. Built for the Egyptian brokerage industry.

---

**Cairo · 2026**
