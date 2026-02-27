#!/usr/bin/env python3
"""
Parses real IIS W3C log files from logs/u_ex*.log and produces:
  logs/usage_data.json  – pre-aggregated JSON for the dashboard
"""

import glob
import json
import os
from collections import defaultdict
from datetime import datetime

# ── Page categorisation ────────────────────────────────────────────────────────
def categorise(path):
    """Return a short category name for a URI stem."""
    p = path.lower()
    if '/displayservice' in p and '/displays/' in p:
        # Extract OC area from path: .../displays/<AREA>/...
        segs = path.strip('/').split('/')
        try:
            idx = next(i for i, s in enumerate(segs) if s.lower() == 'displays')
            area = segs[idx + 1]  # e.g. OC1, OC2, PC, Plantwide
            return area
        except (StopIteration, IndexError):
            return 'Display'
    if '/visualizations' in p:
        fname = path.split('/')[-1].lower()
        if 'trend'         in fname: return 'Trends'
        if 'achart'        in fname: return 'Charts'
        if 'atable'        in fname: return 'Tables'
        if 'table'         in fname: return 'Tables'
        if 'external'      in fname: return 'External'
        if 'graphicviewer' in fname: return 'Graphics'
        return 'Visualization'
    if 'atcplus' in p:
        return 'ATCPlus'
    return 'Other'

# ── Parse all log files ────────────────────────────────────────────────────────
LOG_GLOB = os.path.join(os.path.dirname(__file__), 'logs', 'u_ex*.log')
log_files = sorted(glob.glob(LOG_GLOB))

if not log_files:
    raise FileNotFoundError(f'No log files found matching: {LOG_GLOB}')

print(f'Parsing {len(log_files)} log file(s)…')

log_entries = []
field_map = None  # column index map, parsed from #Fields header

for fpath in log_files:
    print(f'  {os.path.basename(fpath)}')
    with open(fpath, encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.startswith('#Fields:'):
                # Parse field names from header
                names = line[len('#Fields:'):].strip().split()
                field_map = {n: i for i, n in enumerate(names)}
                continue
            if line.startswith('#'):
                continue
            if field_map is None:
                continue  # skip data lines before we have a field map

            parts = line.split()
            try:
                date_str   = parts[field_map['date']]
                time_str   = parts[field_map['time']]
                method     = parts[field_map['cs-method']]
                path       = parts[field_map['cs-uri-stem']]
                username   = parts[field_map['cs-username']]
                status     = int(parts[field_map['sc-status']])
                time_taken = int(parts[field_map['time-taken']])
            except (KeyError, IndexError, ValueError):
                continue

            # Skip non-GET requests and static assets (images, css, js, etc.)
            if method != 'GET':
                continue
            ext = path.rsplit('.', 1)[-1].lower() if '.' in path.split('/')[-1] else ''
            if ext in ('png', 'jpg', 'jpeg', 'gif', 'ico', 'css', 'js', 'woff', 'woff2', 'svg', 'map'):
                continue

            timestamp = f'{date_str}T{time_str}'
            category  = categorise(path)

            log_entries.append({
                'date':       date_str,
                'time':       time_str,
                'timestamp':  timestamp,
                'path':       path,
                'category':   category,
                'username':   username,
                'status':     status,
                'time_taken': time_taken,
            })

log_entries.sort(key=lambda x: x['timestamp'])
print(f'Parsed {len(log_entries):,} GET page requests')

# ── Basic aggregation ─────────────────────────────────────────────────────────
matrix        = defaultdict(lambda: defaultdict(int))  # user -> path -> count
user_totals   = defaultdict(int)
page_totals   = defaultdict(int)
page_cat      = {}       # path -> category
cat_totals    = defaultdict(int)
hourly        = defaultdict(int)
daily         = defaultdict(int)
status_counts = defaultdict(int)
user_avg_time = defaultdict(list)

for e in log_entries:
    matrix[e['username']][e['path']] += 1
    user_totals[e['username']]       += 1
    page_totals[e['path']]           += 1
    page_cat[e['path']]               = e['category']
    cat_totals[e['category']]        += 1
    hourly[int(e['time'][:2])]       += 1
    daily[e['date']]                 += 1
    status_counts[str(e['status'])]  += 1
    user_avg_time[e['username']].append(e['time_taken'])

# ── Category-to-category transitions ─────────────────────────────────────────
user_visit_cats = defaultdict(list)
for e in log_entries:
    user_visit_cats[e['username']].append(e['category'])

trans_all  = defaultdict(int)
trans_user = defaultdict(lambda: defaultdict(int))

for uid, cats in user_visit_cats.items():
    for i in range(len(cats) - 1):
        src, dst = cats[i], cats[i + 1]
        if src != dst:
            trans_all[(src, dst)]       += 1
            trans_user[uid][(src, dst)] += 1

def _pairs_to_list(d):
    return [{'source': s, 'target': t, 'value': v}
            for (s, t), v in sorted(d.items(), key=lambda x: -x[1])]

transitions_list      = _pairs_to_list(trans_all)
user_transitions_dict = {uid: _pairs_to_list(d) for uid, d in trans_user.items()}

# ── Page-level 5-step flow (top-20 pages, sliding windows) ───────────────────
_NUM_STEPS  = 5
_TOP20      = {p for p, _ in sorted(page_totals.items(), key=lambda x: -x[1])[:20]}

def _bucket(p):
    return p if p in _TOP20 else '(other)'

def _dedup(seq):
    return [v for i, v in enumerate(seq) if i == 0 or v != seq[i - 1]]

user_visit_pages = defaultdict(list)
for e in log_entries:
    user_visit_pages[e['username']].append(e['path'])

step_all  = [defaultdict(int) for _ in range(_NUM_STEPS - 1)]
step_user = defaultdict(lambda: [defaultdict(int) for _ in range(_NUM_STEPS - 1)])

for uid, pages in user_visit_pages.items():
    bucketed = [_bucket(p) for p in _dedup(pages)]
    for start in range(len(bucketed) - _NUM_STEPS + 1):
        window = bucketed[start:start + _NUM_STEPS]
        for k in range(_NUM_STEPS - 1):
            pair = (window[k], window[k + 1])
            step_all[k][pair]       += 1
            step_user[uid][k][pair] += 1

def _step_to_list(trans_list, min_count=1):
    return [
        [{'from': f, 'to': t, 'count': c}
         for (f, t), c in sorted(d.items(), key=lambda x: -x[1]) if c >= min_count]
        for d in trans_list
    ]

page_flow_data      = _step_to_list(step_all)
user_page_flow_data = {uid: _step_to_list(d, min_count=3)
                       for uid, d in step_user.items()}

# ── User top pages ────────────────────────────────────────────────────────────
user_top_pages = {}
for uid, pages in matrix.items():
    top = sorted(pages.items(), key=lambda x: -x[1])[:5]
    user_top_pages[uid] = [{'page': p, 'count': c} for p, c in top]

# ── Bubble matrix ─────────────────────────────────────────────────────────────
bubble_data = [
    {'user': uid, 'page': path, 'count': cnt}
    for uid, pages in matrix.items()
    for path, cnt in pages.items()
]

# ── Top-20 pages overall ──────────────────────────────────────────────────────
top_pages = sorted(page_totals.items(), key=lambda x: -x[1])[:20]

# ── Date range ────────────────────────────────────────────────────────────────
dates = sorted(daily.keys())
start_date = dates[0]  if dates else '?'
end_date   = dates[-1] if dates else '?'

# ── Users list (sorted by total requests, all assigned role "operator") ───────
sorted_users = sorted(user_totals.keys(),
                      key=lambda u: -user_totals[u])

usage_data = {
    'meta': {
        'generated_at': datetime.now().isoformat(),
        'date_range': {'start': start_date, 'end': end_date},
        'total_requests': len(log_entries),
        'unique_users':   len(sorted_users),
        'unique_pages':   len(page_totals),
    },
    'users': [
        {
            'id':               uid,
            'role':             'operator',
            'total_requests':   user_totals[uid],
            'total_bytes':      0,
            'avg_response_ms':  round(
                sum(user_avg_time[uid]) / len(user_avg_time[uid]), 1
            ) if user_avg_time[uid] else 0,
            'top_pages': user_top_pages.get(uid, []),
        }
        for uid in sorted_users
    ],
    'pages': [
        {
            'path':           path,
            'category':       page_cat[path],
            'total_requests': page_totals[path],
            'total_bytes':    0,
        }
        for path in page_totals
    ],
    'bubble_matrix':    bubble_data,
    'category_totals':  dict(cat_totals),
    'top_pages':        [{'page': p, 'count': c} for p, c in top_pages],
    'daily_series':     [{'date': d, 'count': c} for d, c in sorted(daily.items())],
    'hourly_series':    [{'hour': h, 'count': hourly.get(h, 0)} for h in range(24)],
    'status_codes':     dict(status_counts),
    'transitions':      transitions_list,
    'user_transitions': user_transitions_dict,
    'page_flow':        page_flow_data,
    'user_page_flow':   user_page_flow_data,
}

out_path = os.path.join(os.path.dirname(__file__), 'logs', 'usage_data.json')
with open(out_path, 'w') as f:
    json.dump(usage_data, f, indent=2)

print(f'Written {out_path}')
print(f'\nSummary:')
print(f'  Total requests : {len(log_entries):,}')
print(f'  Date range     : {start_date} → {end_date}')
print(f'  Unique users   : {len(sorted_users)}')
print(f'  Unique pages   : {len(page_totals)}')
print(f'\nTop 5 users by requests:')
for uid in sorted_users[:5]:
    print(f'  {uid:12} {user_totals[uid]:,}')
print(f'\nCategories:')
for cat, cnt in sorted(cat_totals.items(), key=lambda x: -x[1]):
    print(f'  {cat:15} {cnt:,}')
