# IIS Usage Analytics Dashboard

A self-contained, single-file HTML dashboard for visualising 30-day IIS web access logs.
No build step, no server required — open `index.html` directly in a browser.

## Quick start

```bash
# Optional: regenerate the log data
python3 generate_logs.py

# Open the dashboard
open index.html          # macOS
xdg-open index.html      # Linux
start index.html         # Windows
```

---

## Project layout

```
UsageAnalysis/
├── index.html          # Dashboard — all HTML, CSS, and JS in one file
├── generate_logs.py    # Synthetic log generator
└── logs/
    ├── iis_access.log  # Raw IIS W3C Extended Log Format output
    └── usage_data.json # Pre-aggregated JSON (also embedded in index.html)
```

---

## Generating new data

`generate_logs.py` produces both the raw log file and the aggregated JSON used by the dashboard.

```bash
python3 generate_logs.py
```

Output summary printed to stdout:

```
Generated 25,514 log entries
Written logs/iis_access.log
Written logs/usage_data.json

Total requests : 25,514
Date range     : 2026-01-20 → 2026-02-19
Users          : 10
Pages          : 100
```

To update the dashboard after regenerating data, replace the `USAGE_DATA` constant near the
bottom of `index.html` with the contents of `logs/usage_data.json`.

### Simulated users

| User  | Role      | Activity weight | Notable affinity |
|-------|-----------|-----------------|------------------|
| alice | manager   | 18              | dashboard, reports, shared |
| bob   | admin     | 15              | admin (exclusive), projects, calendar |
| carol | analyst   | 12              | reports, wiki, calendar |
| dave  | analyst   | 11              | reports, projects, dashboard |
| eve   | developer | 9               | projects, wiki, help |
| frank | developer | 8               | wiki, help, projects |
| grace | support   | 7               | calendar, shared, help |
| henry | support   | 4               | shared, navigation |
| iris  | viewer    | 3               | navigation, help |
| jack  | viewer    | 1               | navigation only |

**Access rules baked in:**
- Each user can only access their own `/users/<name>/*` personal pages.
- `/admin/*` pages are exclusive to `bob`; other users receive HTTP 403 on rare accidental visits.
- Traffic is biased towards weekdays and business hours (08:00–18:00).

### Page categories (100 pages total)

| Category   | Pages | Colour |
|------------|------:|--------|
| navigation | 4     | indigo |
| dashboard  | 5     | sky |
| reports    | 10    | emerald |
| calendar   | 5     | amber |
| wiki       | 10    | violet |
| admin      | 5     | red |
| help       | 6     | pink |
| projects   | 10    | teal |
| shared     | 10    | orange |
| personal   | 35    | lime |

---

## Dashboard sections

The sticky nav bar links directly to each section.

### 1 — Overview

Six summary cards populated from `meta` and aggregated user/page data:

- Total requests, unique users, unique pages
- Busiest user (most requests)
- Most-visited page
- Average response time across all users

### 2 — Knowledge Graph

A D3 v7 force-directed graph showing the **access relationships between users and page categories**.

**Nodes**

| Node type | Size | Colour |
|-----------|------|--------|
| User (10) | Scaled to total requests (√ scale) | Role colour — see legend |
| Category (10) | Scaled to total category requests (√ scale) | Category colour — see legend |

Category nodes also carry a faint outer glow ring to distinguish them from user nodes.

**Edges**

Each edge connects one user to one page category.
Weight = total requests from that user to any page in that category (summed from `bubble_matrix`).

| Visual property | Encodes |
|-----------------|---------|
| Stroke width | √(request count) — heavier paths are thicker |
| Stroke opacity | request count (linear) — heavier paths are more opaque |
| Stroke colour | Category colour of the target node |

**Interactions**

| Gesture | Effect |
|---------|--------|
| Drag a node | Pins it at the new position; releases when you let go |
| Scroll / pinch | Zoom the whole canvas (0.25× – 4×) |
| Pan | Click-drag on the background |
| Hover a node | Highlights direct neighbours, dims everything else; tooltip shows details |
| Move away | Resets all opacity to default |

**Force simulation parameters**

- `forceManyBody` strength −420 (repulsion keeps nodes spread)
- `forceLink` distance scales with edge weight so heavier connections sit closer
- `forceCollide` prevents node overlap with padding
- `forceCenter` with low strength (0.06) keeps the graph loosely centred without pulling nodes together

### 3 — User × Category Heatmap

A D3 SVG grid with one cell per (user, category) pair.
Cell colour intensity maps to request count using a sequential scale.
Hover any cell for the exact count.

### 4 — Traffic Trends

Two Chart.js line charts side by side:

- **Daily request volume** — 30-day time series, weekday peaks visible
- **Hourly traffic pattern** — aggregate distribution across hours 0–23; business-hours spike clearly visible

### 5 — Top Pages

A horizontal Chart.js bar chart for the top 20 most-visited pages across all users.
Bars are coloured by page category.

### 6 — Users

- **User request volume** — vertical bar chart, sorted descending, coloured by role
- **User profiles table** — one row per user showing role badge, total requests, data transferred, average response time, and top 5 pages

### 7 — Breakdown

Two Chart.js donut charts:

- **Page category distribution** — share of requests by category
- **HTTP status code distribution** — 200 / 304 / 403 / 404 / 500 breakdown

---

## Data format (`usage_data.json`)

```jsonc
{
  "meta": {
    "generated_at": "<ISO datetime>",
    "date_range": { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD" },
    "total_requests": 25514,
    "unique_users": 10,
    "unique_pages": 100
  },
  "users": [
    {
      "id": "alice",
      "role": "manager",
      "total_requests": 5251,
      "total_bytes": 77577968,
      "avg_response_ms": 431.3,
      "top_pages": [{ "page": "/dashboard", "count": 358 }, ...]
    }
  ],
  "pages": [
    { "path": "/dashboard", "category": "dashboard",
      "total_requests": 948, "total_bytes": 13942104 }
  ],
  "bubble_matrix": [
    { "user": "alice", "page": "/dashboard", "count": 358 }
    // one entry per non-zero (user, page) pair
  ],
  "category_totals": { "reports": 4864, "projects": 3545, ... },
  "top_pages":   [{ "page": "/dashboard", "count": 948 }, ...],
  "daily_series":  [{ "date": "2026-01-20", "count": 1086 }, ...],
  "hourly_series": [{ "hour": 8, "count": 2185 }, ...],
  "status_codes":  { "200": 22458, "304": 1513, "404": 781, ... }
}
```

The `bubble_matrix` array is sparse (zero-count pairs are omitted).
The knowledge graph aggregates it into `(user, category)` totals at render time.

---

## Colour system

All colours are defined as JavaScript constants at the top of the `<script>` block
and as CSS custom properties on `:root` for use in static styles.

```js
// Page categories
const CAT_COLORS = {
  navigation: '#818cf8',  dashboard: '#38bdf8',
  reports:    '#34d399',  calendar:  '#fbbf24',
  wiki:       '#a78bfa',  admin:     '#f87171',
  help:       '#f472b6',  projects:  '#2dd4bf',
  shared:     '#fb923c',  personal:  '#a3e635',
};

// User roles (used by the knowledge graph and role badges)
const ROLE_COLORS = {
  manager:   '#60a5fa',  admin:     '#f87171',
  analyst:   '#34d399',  developer: '#c084fc',
  support:   '#fbbf24',  viewer:    '#94a3b8',
};

// HTTP status codes
const STATUS_COLORS = {
  '200': '#34d399',  '304': '#38bdf8',
  '403': '#f87171',  '404': '#fbbf24',  '500': '#f472b6',
};
```

---

## Dependencies

Both libraries are loaded from CDN; no installation required.

| Library | Version | Used for |
|---------|---------|----------|
| [D3.js](https://d3js.org/) | v7 | Knowledge graph (force simulation, zoom, drag), heatmap |
| [Chart.js](https://www.chartjs.org/) | v4.4.1 | Bar, line, and donut charts |

---

## Architecture notes

- **Single-file** — `index.html` contains all HTML, CSS, JS, and data. It works from `file://` without a server.
- **Fault isolation** — each chart function is wrapped in a `try/catch` inside `initAll`; a rendering error in one panel never blocks the others.
- **No framework** — plain ES2020 with D3 and Chart.js; no build toolchain.
- **Static data** — `USAGE_DATA` is a JSON literal embedded directly in the script tag. To point at a live endpoint, replace the constant assignment with a `fetch()` call and pass the resolved JSON to `initAll(data)`.
