#!/usr/bin/env python3
"""
Generates dummy IIS-style (W3C Extended Log Format) access logs for
10 users accessing 100 pages over 30 days, with realistic usage patterns.
Outputs:
  logs/iss_access.log  - Raw IIS W3C log file
  logs/usage_data.json - Pre-aggregated JSON for the dashboard
"""

import random
import json
import os
from datetime import datetime, timedelta

random.seed(42)

# ── Users ──────────────────────────────────────────────────────────────────────
USERS = [
    {"id": "alice",  "ip": "10.0.0.11", "weight": 18, "role": "manager"},
    {"id": "bob",    "ip": "10.0.0.12", "weight": 15, "role": "admin"},
    {"id": "carol",  "ip": "10.0.0.13", "weight": 12, "role": "analyst"},
    {"id": "dave",   "ip": "10.0.0.14", "weight": 11, "role": "analyst"},
    {"id": "eve",    "ip": "10.0.0.15", "weight": 9,  "role": "developer"},
    {"id": "frank",  "ip": "10.0.0.16", "weight": 8,  "role": "developer"},
    {"id": "grace",  "ip": "10.0.0.17", "weight": 7,  "role": "support"},
    {"id": "henry",  "ip": "10.0.0.18", "weight": 4,  "role": "support"},
    {"id": "iris",   "ip": "10.0.0.19", "weight": 3,  "role": "viewer"},
    {"id": "jack",   "ip": "10.0.0.20", "weight": 1,  "role": "viewer"},
]

# ── Pages (100 total) ──────────────────────────────────────────────────────────
PAGES = {
    # category: [(path, base_weight)]
    "navigation": [
        ("/home",           50),
        ("/login",          30),
        ("/logout",         20),
        ("/search",         35),
    ],
    "dashboard": [
        ("/dashboard",              60),
        ("/dashboard/summary",      40),
        ("/dashboard/metrics",      30),
        ("/dashboard/charts",       25),
        ("/dashboard/widgets",      15),
    ],
    "reports": [
        ("/reports",                45),
        ("/reports/annual-2025",    30),
        ("/reports/q1-2025",        35),
        ("/reports/q2-2025",        32),
        ("/reports/q3-2025",        28),
        ("/reports/q4-2025",        20),
        ("/reports/monthly/jan",    18),
        ("/reports/monthly/feb",    22),
        ("/reports/monthly/mar",    12),
        ("/reports/custom",         10),
    ],
    "calendar": [
        ("/calendar",               38),
        ("/calendar/events",        25),
        ("/calendar/meetings",      22),
        ("/calendar/holidays",      10),
        ("/calendar/tasks",         18),
    ],
    "wiki": [
        ("/wiki",                   32),
        ("/wiki/main",              28),
        ("/wiki/projects",          24),
        ("/wiki/hr-policies",       18),
        ("/wiki/tech-docs",         22),
        ("/wiki/onboarding",        15),
        ("/wiki/style-guide",       12),
        ("/wiki/api-reference",     20),
        ("/wiki/architecture",      16),
        ("/wiki/releases",          14),
    ],
    "admin": [
        ("/admin",                  20),
        ("/admin/users",            18),
        ("/admin/settings",         15),
        ("/admin/logs",             12),
        ("/admin/audit",            10),
    ],
    "help": [
        ("/help",                   25),
        ("/help/faq",               20),
        ("/help/getting-started",   15),
        ("/help/tutorials",         12),
        ("/help/contact",            8),
        ("/help/release-notes",     10),
    ],
    "projects": [
        ("/projects",               28),
        ("/projects/alpha",         24),
        ("/projects/beta",          22),
        ("/projects/gamma",         16),
        ("/projects/delta",         14),
        ("/projects/alpha/tasks",   20),
        ("/projects/alpha/docs",    18),
        ("/projects/beta/tasks",    18),
        ("/projects/beta/docs",     16),
        ("/projects/archive",        8),
    ],
    "shared": [
        ("/shared",                 30),
        ("/shared/documents",       26),
        ("/shared/templates",       20),
        ("/shared/assets",          14),
        ("/shared/forms",           18),
        ("/shared/procedures",      16),
        ("/shared/guidelines",      14),
        ("/shared/announcements",   24),
        ("/shared/resources",       18),
        ("/shared/library",         12),
    ],
    "personal": [
        ("/users/alice/profile",    20), ("/users/alice/notes",     16),
        ("/users/alice/settings",   12), ("/users/alice/bookmarks", 10),
        ("/users/alice/dashboard",  18),
        ("/users/bob/profile",      20), ("/users/bob/notes",       14),
        ("/users/bob/settings",     10), ("/users/bob/bookmarks",    8),
        ("/users/bob/dashboard",    16),
        ("/users/carol/profile",    18), ("/users/carol/notes",     14),
        ("/users/carol/settings",    8), ("/users/carol/bookmarks",  6),
        ("/users/carol/dashboard",  12),
        ("/users/dave/profile",     16), ("/users/dave/notes",      12),
        ("/users/dave/settings",     8), ("/users/dave/bookmarks",   6),
        ("/users/dave/dashboard",   10),
        ("/users/eve/profile",      14), ("/users/eve/notes",       10),
        ("/users/eve/settings",      6),
        ("/users/frank/profile",    12), ("/users/frank/notes",      8),
        ("/users/frank/settings",    5),
        ("/users/grace/profile",    10), ("/users/grace/notes",      6),
        ("/users/grace/settings",    4),
        ("/users/henry/profile",     8), ("/users/henry/settings",   4),
        ("/users/iris/profile",      6), ("/users/iris/settings",    3),
        ("/users/jack/profile",      4), ("/users/jack/settings",    2),
    ],
}

# Flatten to list of dicts
ALL_PAGES = []
for cat, items in PAGES.items():
    for path, weight in items:
        ALL_PAGES.append({"path": path, "category": cat, "base_weight": weight})

assert len(ALL_PAGES) == 100, f"Expected 100 pages, got {len(ALL_PAGES)}"

# ── Per-user page affinity (which categories each user prefers) ───────────────
USER_AFFINITY = {
    "alice":  {"dashboard": 3.0, "reports": 2.5, "shared": 2.0, "navigation": 1.5, "personal": 2.0},
    "bob":    {"admin": 4.0,     "projects": 3.0, "calendar": 2.0, "navigation": 1.5, "personal": 2.0},
    "carol":  {"reports": 3.0,   "wiki": 2.5,     "calendar": 2.0, "shared": 1.5, "personal": 2.0},
    "dave":   {"reports": 3.5,   "projects": 2.5, "dashboard": 1.5, "personal": 2.0},
    "eve":    {"projects": 3.0,  "wiki": 2.5,     "help": 1.5, "personal": 1.5},
    "frank":  {"wiki": 3.0,      "help": 2.5,     "projects": 2.0, "personal": 1.5},
    "grace":  {"calendar": 3.5,  "shared": 2.5,   "help": 1.5, "personal": 1.5},
    "henry":  {"shared": 2.0,    "navigation": 2.0, "personal": 1.5, "help": 1.5},
    "iris":   {"navigation": 2.5, "help": 3.0,    "personal": 1.0},
    "jack":   {"navigation": 2.0, "personal": 1.0},
}

# Personal page ownership - users strongly prefer their own personal pages
PERSONAL_OWNER = {p["path"].split("/")[2]: p["path"]
                  for p in ALL_PAGES if p["category"] == "personal"}

USER_AGENTS = [
    "Mozilla/5.0+(Windows+NT+10.0;+Win64;+x64)+AppleWebKit/537.36+(KHTML,+like+Gecko)+Chrome/120.0.0.0+Safari/537.36",
    "Mozilla/5.0+(Macintosh;+Intel+Mac+OS+X+10_15_7)+AppleWebKit/537.36+(KHTML,+like+Gecko)+Chrome/119.0.0.0+Safari/537.36",
    "Mozilla/5.0+(Windows+NT+10.0;+Win64;+x64;+rv:121.0)+Gecko/20100101+Firefox/121.0",
    "Mozilla/5.0+(X11;+Linux+x86_64)+AppleWebKit/537.36+(KHTML,+like+Gecko)+Chrome/118.0.0.0+Safari/537.36",
    "Mozilla/5.0+(iPhone;+CPU+iPhone+OS+17_0+like+Mac+OS+X)+AppleWebKit/605.1.15",
]

STATUS_WEIGHTS = [200]*88 + [304]*6 + [404]*3 + [403]*2 + [500]*1

START_DATE = datetime(2026, 1, 20, 0, 0, 0)
END_DATE   = datetime(2026, 2, 19, 23, 59, 59)

def page_weight_for_user(page, user_id):
    """Compute how likely a user is to access a given page."""
    cat = page["category"]
    affinity = USER_AFFINITY.get(user_id, {})
    multiplier = affinity.get(cat, 1.0)
    # Own personal pages get huge boost; other users' personal pages get 0
    if cat == "personal":
        owner = page["path"].split("/")[2]  # e.g. "alice"
        if owner == user_id:
            multiplier *= 3.0
        else:
            multiplier = 0.0   # can't access others' personal pages
    # Admin pages: only bob has access
    if cat == "admin" and user_id != "bob":
        multiplier = 0.02      # very rare (accidentally browse, get 403)
    return page["base_weight"] * multiplier

def random_timestamp():
    """Bias towards working hours Mon-Fri."""
    while True:
        ts = START_DATE + timedelta(seconds=random.randint(0, int((END_DATE - START_DATE).total_seconds())))
        if ts.weekday() < 5:  # Mon-Fri
            if 8 <= ts.hour < 18:
                return ts
            elif random.random() < 0.1:  # some out-of-hours
                return ts
        elif random.random() < 0.05:  # rare weekend access
            return ts

# ── Generate log entries ───────────────────────────────────────────────────────
print("Generating log entries...")
log_entries = []

for user in USERS:
    uid = user["id"]
    weights = [page_weight_for_user(p, uid) for p in ALL_PAGES]
    total_w  = sum(weights)
    norm_w   = [w / total_w for w in weights]

    # Number of requests proportional to user weight (~300 per weight unit)
    n_requests = user["weight"] * 290 + random.randint(-50, 50)

    for _ in range(n_requests):
        page  = random.choices(ALL_PAGES, weights=norm_w)[0]
        ts    = random_timestamp()
        status = random.choice(STATUS_WEIGHTS)
        # Force 403 on admin pages for non-bob users
        if page["category"] == "admin" and uid != "bob" and random.random() < 0.8:
            status = 403
        bytes_sent = random.randint(512, 32768) if status == 200 else random.randint(64, 1024)
        time_taken = random.randint(12, 850)

        log_entries.append({
            "date":       ts.strftime("%Y-%m-%d"),
            "time":       ts.strftime("%H:%M:%S"),
            "timestamp":  ts.isoformat(),
            "s_ip":       "192.168.0.1",
            "method":     "GET",
            "path":       page["path"],
            "category":   page["category"],
            "s_port":     80,
            "username":   uid,
            "c_ip":       user["ip"],
            "user_agent": random.choice(USER_AGENTS),
            "referer":    "-",
            "status":     status,
            "substatus":  0,
            "win32":      0,
            "time_taken": time_taken,
            "bytes":      bytes_sent,
        })

# Sort by timestamp
log_entries.sort(key=lambda x: x["timestamp"])
print(f"Generated {len(log_entries):,} log entries")

# ── Write W3C IIS log file ─────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)

with open("logs/iss_access.log", "w") as f:
    f.write("#Software: Microsoft Internet Information Services 10.0\n")
    f.write("#Version: 1.0\n")
    f.write(f"#Date: {START_DATE.strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write("#Fields: date time s-ip cs-method cs-uri-stem cs-uri-query s-port cs-username c-ip cs(User-Agent) cs(Referer) sc-status sc-substatus sc-win32-status time-taken\n")
    for e in log_entries:
        f.write(
            f"{e['date']} {e['time']} {e['s_ip']} {e['method']} "
            f"{e['path']} - {e['s_port']} {e['username']} {e['c_ip']} "
            f"{e['user_agent']} {e['referer']} {e['status']} "
            f"{e['substatus']} {e['win32']} {e['time_taken']}\n"
        )

print("Written logs/iss_access.log")

# ── Aggregate data for dashboard ───────────────────────────────────────────────
from collections import defaultdict

# user-page matrix
matrix = defaultdict(lambda: defaultdict(int))
user_totals   = defaultdict(int)
page_totals   = defaultdict(int)
cat_totals    = defaultdict(int)
hourly        = defaultdict(int)
daily         = defaultdict(int)
status_counts = defaultdict(int)
user_bytes    = defaultdict(int)
page_bytes    = defaultdict(int)
user_avg_time = defaultdict(list)

for e in log_entries:
    matrix[e["username"]][e["path"]] += 1
    user_totals[e["username"]]   += 1
    page_totals[e["path"]]        += 1
    cat_totals[e["category"]]     += 1
    hourly[int(e["time"][:2])]    += 1
    daily[e["date"]]              += 1
    status_counts[str(e["status"])] += 1
    user_bytes[e["username"]]     += e["bytes"]
    page_bytes[e["path"]]         += e["bytes"]
    user_avg_time[e["username"]].append(e["time_taken"])

# ── Category-to-category transition counts ────────────────────────────────────
# Group each user's page visits chronologically, then walk consecutive pairs.
# Only cross-category transitions are counted (same-category pairs skipped).
user_visit_cats = defaultdict(list)
for e in log_entries:                        # log_entries already sorted by timestamp
    user_visit_cats[e["username"]].append(e["category"])

trans_all  = defaultdict(int)               # (src_cat, dst_cat) -> count  (all users)
trans_user = defaultdict(lambda: defaultdict(int))  # uid -> (src_cat, dst_cat) -> count

for uid, cats in user_visit_cats.items():
    for i in range(len(cats) - 1):
        src, dst = cats[i], cats[i + 1]
        if src != dst:                       # skip same-category self-loops
            trans_all[(src, dst)]      += 1
            trans_user[uid][(src, dst)] += 1

def _pairs_to_list(d):
    return [{"source": s, "target": t, "value": v}
            for (s, t), v in sorted(d.items(), key=lambda x: -x[1])]

transitions_list      = _pairs_to_list(trans_all)
user_transitions_dict = {uid: _pairs_to_list(d) for uid, d in trans_user.items()}

# ── Page-level 5-step flow (top 20 pages bucketed, sliding windows) ───────────
_TOP20_PAGES  = {p for p, _ in sorted(page_totals.items(), key=lambda x: -x[1])[:20]}
_NUM_STEPS    = 5

def _bucket_pg(p):
    return p if p in _TOP20_PAGES else '(other)'

def _dedup_consec(seq):
    """Remove consecutive duplicate values (e.g. page refreshes)."""
    return [v for i, v in enumerate(seq) if i == 0 or v != seq[i - 1]]

# Group per-user page paths in chronological order
user_visit_pages = defaultdict(list)
for e in log_entries:
    user_visit_pages[e["username"]].append(e["path"])

# step_all[k]  : (from_page, to_page) -> count  for transition k→k+1 (all users)
# step_user[u][k]: same, per user
step_all  = [defaultdict(int) for _ in range(_NUM_STEPS - 1)]
step_user = defaultdict(lambda: [defaultdict(int) for _ in range(_NUM_STEPS - 1)])

for uid, pages in user_visit_pages.items():
    bucketed = [_bucket_pg(p) for p in _dedup_consec(pages)]
    for start in range(len(bucketed) - _NUM_STEPS + 1):
        window = bucketed[start:start + _NUM_STEPS]
        for k in range(_NUM_STEPS - 1):
            pair = (window[k], window[k + 1])
            step_all[k][pair]      += 1
            step_user[uid][k][pair] += 1

def _step_trans_to_list(trans_list, min_count=1):
    return [
        [{"from": f, "to": t, "count": c}
         for (f, t), c in sorted(d.items(), key=lambda x: -x[1]) if c >= min_count]
        for d in trans_list
    ]

page_flow_data      = _step_trans_to_list(step_all)                           # all users
user_page_flow_data = {uid: _step_trans_to_list(d, min_count=3)               # per user
                       for uid, d in step_user.items()}

# Top pages per user
user_top_pages = {}
for uid, pages in matrix.items():
    sorted_pages = sorted(pages.items(), key=lambda x: -x[1])[:5]
    user_top_pages[uid] = [{"page": p, "count": c} for p, c in sorted_pages]

# Bubble matrix data (sparse, only non-zero cells)
bubble_data = []
for uid, pages in matrix.items():
    for path, count in pages.items():
        bubble_data.append({"user": uid, "page": path, "count": count})

# Top 20 pages overall
top_pages = sorted(page_totals.items(), key=lambda x: -x[1])[:20]

# Daily series
daily_series = [{"date": d, "count": c} for d, c in sorted(daily.items())]

# Hourly series
hourly_series = [{"hour": h, "count": hourly.get(h, 0)} for h in range(24)]

usage_data = {
    "meta": {
        "generated_at": datetime.now().isoformat(),
        "date_range": {"start": START_DATE.strftime("%Y-%m-%d"), "end": END_DATE.strftime("%Y-%m-%d")},
        "total_requests": len(log_entries),
        "unique_users": len(USERS),
        "unique_pages": len(ALL_PAGES),
    },
    "users": [
        {
            "id": u["id"],
            "role": u["role"],
            "total_requests": user_totals[u["id"]],
            "total_bytes": user_bytes[u["id"]],
            "avg_response_ms": round(sum(user_avg_time[u["id"]]) / len(user_avg_time[u["id"]]), 1)
                               if user_avg_time[u["id"]] else 0,
            "top_pages": user_top_pages.get(u["id"], []),
        }
        for u in USERS
    ],
    "pages": [
        {
            "path": p["path"],
            "category": p["category"],
            "total_requests": page_totals[p["path"]],
            "total_bytes": page_bytes[p["path"]],
        }
        for p in ALL_PAGES
    ],
    "bubble_matrix": bubble_data,
    "category_totals": dict(cat_totals),
    "top_pages": [{"page": p, "count": c} for p, c in top_pages],
    "daily_series": daily_series,
    "hourly_series": hourly_series,
    "status_codes": dict(status_counts),
    "transitions": transitions_list,
    "user_transitions": user_transitions_dict,
    "page_flow": page_flow_data,
    "user_page_flow": user_page_flow_data,
}

with open("logs/usage_data.json", "w") as f:
    json.dump(usage_data, f, indent=2)

print("Written logs/usage_data.json")
print(f"\nSummary:")
print(f"  Total requests : {len(log_entries):,}")
print(f"  Date range     : {START_DATE.date()} → {END_DATE.date()}")
print(f"  Users          : {len(USERS)}")
print(f"  Pages          : {len(ALL_PAGES)}")
print(f"\nTop 5 users by requests:")
for uid, cnt in sorted(user_totals.items(), key=lambda x: -x[1])[:5]:
    print(f"  {uid:10} {cnt:,}")
print(f"\nTop 5 pages by requests:")
for path, cnt in top_pages[:5]:
    print(f"  {path:35} {cnt:,}")
