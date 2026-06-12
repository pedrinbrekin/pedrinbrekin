#!/usr/bin/env python3
"""
Gerador local de stats do GitHub  ->  3 cartoes SVG animados.
Inclui: repos proprios + orgs (membro/colaborador) + repos contribuidos.

Saida: generated/overview.svg, generated/languages.svg, generated/activity.svg

Uso:
  PowerShell:  $env:GITHUB_TOKEN="ghp_..."  ->  python gen_stats.py
  CMD:         set GITHUB_TOKEN=ghp_...     ->  python gen_stats.py

O token precisa dos escopos: repo, read:user, read:org.
"""
import os, sys, json, time, urllib.request, urllib.error
from datetime import date, timedelta

TOKEN    = os.environ.get("GITHUB_TOKEN")
USERNAME = "pedrinbrekin"

if not TOKEN:
    print("ERRO: defina GITHUB_TOKEN antes de rodar.")
    print('  PowerShell: $env:GITHUB_TOKEN="ghp_..."')
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
TPL  = os.path.join(HERE, "templates")


def graphql(query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req  = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {TOKEN}",
                 "Content-Type": "application/json",
                 "User-Agent": "gen-stats-local"})
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read().decode())
    if "errors" in data:
        print("Aviso GraphQL:", data["errors"])
    return data.get("data")


def rest(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Authorization": f"bearer {TOKEN}",
                 "User-Agent": "gen-stats-local",
                 "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req) as r:
            body = r.read().decode().strip()
            return (json.loads(body) if body else None), r.status
    except urllib.error.HTTPError as e:
        return None, e.code
    except Exception:
        return None, 0


REPO_FIELDS = """
nameWithOwner isPrivate stargazerCount forkCount
languages(first:10, orderBy:{field:SIZE, direction:DESC}) {
  edges { size node { name color } }
}
"""

print("Coletando dados do GitHub...")

all_repos    = {}
display_name = USERNAME
login        = USERNAME
followers    = 0
created_year = date.today().year

# 0. Perfil basico
prof = graphql("""
query($l:String!) {
  user(login:$l) {
    name login createdAt
    followers { totalCount }
  }
}""", {"l": USERNAME})
if prof and prof.get("user"):
    u = prof["user"]
    display_name = u["name"] or USERNAME
    login        = u["login"]
    followers    = u["followers"]["totalCount"]
    created_year = int(u["createdAt"][:4])

# 1. Proprios + org membro/colaborador
cursor = None
while True:
    d = graphql(f"""
    query($l:String!, $c:String) {{
      user(login:$l) {{
        repositories(first:100, after:$c, isFork:false,
          affiliations:[OWNER,COLLABORATOR,ORGANIZATION_MEMBER],
          ownerAffiliations:[OWNER,COLLABORATOR,ORGANIZATION_MEMBER]) {{
          pageInfo {{ hasNextPage endCursor }}
          nodes {{ {REPO_FIELDS} }}
        }}
      }}
    }}""", {"l": USERNAME, "c": cursor})
    if not d: break
    blk = d["user"]["repositories"]
    for r in blk["nodes"]: all_repos[r["nameWithOwner"]] = r
    if not blk["pageInfo"]["hasNextPage"]: break
    cursor = blk["pageInfo"]["endCursor"]

print(f"  Repos proprios/org: {len(all_repos)}")

# 2. Repos contribuidos (commits/PRs)
before = len(all_repos)
cursor = None
while True:
    d = graphql(f"""
    query($l:String!, $c:String) {{
      user(login:$l) {{
        repositoriesContributedTo(first:100, after:$c,
          includeUserRepositories:false,
          contributionTypes:[COMMIT,PULL_REQUEST,REPOSITORY]) {{
          pageInfo {{ hasNextPage endCursor }}
          nodes {{ {REPO_FIELDS} }}
        }}
      }}
    }}""", {"l": USERNAME, "c": cursor})
    if not d: break
    blk = d["user"]["repositoriesContributedTo"]
    for r in blk["nodes"]:
        if r["nameWithOwner"] not in all_repos:
            all_repos[r["nameWithOwner"]] = r
    if not blk["pageInfo"]["hasNextPage"]: break
    cursor = blk["pageInfo"]["endCursor"]

print(f"  Repos contribuidos extras: {len(all_repos) - before}")
repos = list(all_repos.values())

own   = [r for r in repos if r["nameWithOwner"].lower().startswith(USERNAME.lower()+"/")]
stars = sum(r["stargazerCount"] for r in own)
forks = sum(r["forkCount"] for r in own)

# 3. Contribuicoes ALL-TIME + calendario completo (para streaks)
print("Coletando calendario de contribuicoes (por ano)...")
contribs   = 0
commits    = 0
prs        = 0
day_counts = {}   # date -> contributionCount

# anos com atividade
years_data = graphql("""
query($l:String!) {
  user(login:$l) { contributionsCollection { contributionYears } }
}""", {"l": USERNAME})
years = []
if years_data and years_data.get("user"):
    years = years_data["user"]["contributionsCollection"]["contributionYears"]
if not years:
    years = list(range(created_year, date.today().year + 1))

for y in years:
    frm = f"{y}-01-01T00:00:00Z"
    to  = f"{y}-12-31T23:59:59Z"
    d = graphql("""
    query($l:String!, $f:DateTime!, $t:DateTime!) {
      user(login:$l) {
        contributionsCollection(from:$f, to:$t) {
          totalCommitContributions
          totalPullRequestContributions
          restrictedContributionsCount
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }""", {"l": USERNAME, "f": frm, "t": to})
    if not d or not d.get("user"): continue
    cc = d["user"]["contributionsCollection"]
    contribs += cc["contributionCalendar"]["totalContributions"]
    commits  += cc["totalCommitContributions"]
    prs      += cc["totalPullRequestContributions"]
    for w in cc["contributionCalendar"]["weeks"]:
        for day in w["contributionDays"]:
            day_counts[day["date"]] = day["contributionCount"]

# ── Streaks ─────────────────────────────────────────────────────
def parse(d): return date.fromisoformat(d)
active = sorted(d for d, c in day_counts.items() if c > 0)
first_active = parse(active[0]) if active else date.today()

# current streak (hoje sem contribuicao nao quebra a sequencia)
active_set = {parse(d) for d in active}
today = date.today()
cur = 0
cur_end = None
d = today if today in active_set else today - timedelta(days=1)
while d in active_set:
    if cur_end is None: cur_end = d
    cur += 1
    d -= timedelta(days=1)
cur_start = cur_end - timedelta(days=cur - 1) if cur else None

# longest streak
best = 0; best_start = best_end = None
run = 0; run_start = None; prev = None
for d in sorted(active_set):
    if prev is not None and (d - prev).days == 1:
        run += 1
    else:
        run = 1; run_start = d
    if run > best:
        best = run; best_start = run_start; best_end = d
    prev = d

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
def md(d):   return f"{MONTHS[d.month-1]} {d.day}"
def mdy(d):  return f"{MONTHS[d.month-1]} {d.day}, {d.year}"
def my(d):   return f"{MONTHS[d.month-1]} {d.year}"

total_range   = f"{my(first_active)} \u2014 Present"
current_range = f"{md(cur_start)} \u2014 {md(cur_end)}" if cur else "\u2014"
longest_range = f"{md(best_start)} \u2014 {mdy(best_end)}" if best else "\u2014"
ring_offset   = round(251.3 * (1 - min(1.0, cur / best if best else 0)), 1)

# 4. Linhas alteradas + views (REST)
lines_changed = 0
views         = 0
pending       = []
print(f"Analisando {len(repos)} repos (linhas + views)...")

for r in repos:
    nr = r["nameWithOwner"]
    stats, code = rest(f"/repos/{nr}/stats/contributors")
    if code == 202:
        pending.append(nr)
    elif code == 200 and stats:
        for c in stats:
            if (c.get("author") or {}).get("login","").lower() == USERNAME.lower():
                for w in c.get("weeks", []):
                    lines_changed += w.get("a",0) + w.get("d",0)
    traffic, code = rest(f"/repos/{nr}/traffic/views")
    if code == 200 and traffic:
        views += traffic.get("count", 0)

if pending:
    print(f"  Aguardando GitHub calcular stats de {len(pending)} repos...")
    time.sleep(6)
    for nr in pending:
        stats, code = rest(f"/repos/{nr}/stats/contributors")
        if code == 200 and stats:
            for c in stats:
                if (c.get("author") or {}).get("login","").lower() == USERNAME.lower():
                    for w in c.get("weeks", []):
                        lines_changed += w.get("a",0) + w.get("d",0)

# 5. Linguagens agregadas
langs = {}
for r in repos:
    edges = r["languages"]["edges"]
    repo_total = sum(e["size"] for e in edges) or 1
    for edge in edges:
        n = edge["node"]["name"]
        c = edge["node"]["color"] or "#a78bfa"
        if n not in langs: langs[n] = {"size":0.0, "color":c}
        # peso reequilibrado: cada repo vale 1, a linguagem ganha sua
        # fracao dentro do proprio repo. Assim um sistema legado gigante
        # nao domina o cartao por volume de bytes.
        langs[n]["size"] += edge["size"] / repo_total

total_size  = sum(v["size"] for v in langs.values()) or 1

# C# sempre no topo; o resto por peso decrescente.
PIN_FIRST = "C#"
lang_sorted = sorted(
    langs.items(),
    key=lambda x: (0 if x[0] == PIN_FIRST else 1, -x[1]["size"]),
)

# Paleta preferencial (combina com a estetica roxa)
PREFERRED_COLORS = {
    "C#": "#c084fc", "Visual Basic .NET": "#c084fc",
    "Delphi": "#f87171", "Pascal": "#f87171", "Object Pascal": "#f87171",
    "PLpgSQL": "#22d3ee", "TSQL": "#22d3ee", "SQL": "#22d3ee",
    "JavaScript": "#fbbf24", "TypeScript": "#60a5fa",
    "Python": "#4ade80", "HTML": "#fb923c", "CSS": "#a78bfa",
    "Dockerfile": "#7dd3fc", "Shell": "#a78bfa",
}
HIGHLIGHTED = {"C#", "Delphi", "Object Pascal", "Pascal"}

# ── Barra empilhada (segmentos clipados na faixa arredondada) ───
progress_svg = ""
offset = 24.0           # inicio x da faixa
seg_i  = 0
for name, info in lang_sorted:
    pct = 100 * info["size"] / total_size
    if pct < 0.4:
        continue
    color = PREFERRED_COLORS.get(name, info["color"])
    w = pct / 100 * 402
    progress_svg += (
        f'  <rect class="bar" x="{offset:.2f}" y="82" width="{max(0.5, w-1.5):.2f}" height="10" '
        f'fill="{color}" style="animation-delay:{0.1 + seg_i*0.07:.2f}s"></rect>\n'
    )
    offset += w
    seg_i  += 1

# ── Lista de linguagens (2 colunas x 3 linhas) ──────────────────
COLS = [24, 237]
ROWY = [120, 152, 184]
lang_rows_svg = ""
shown = 0
for i, (name, info) in enumerate(lang_sorted):
    if shown >= 6: break
    pct = 100 * info["size"] / total_size
    if pct < 0.4: continue
    col   = 0 if shown < 3 else 1
    rowY  = ROWY[shown % 3]
    colX  = COLS[col]
    color = PREFERRED_COLORS.get(name, info["color"])
    is_hl = name in HIGHLIGHTED
    name_color = "#e9d5ff" if is_hl else "#c4b5e0"
    fw    = "700" if is_hl else "500"
    barw  = pct / 100 * 150
    delay = 0.2 + shown * 0.08
    lang_rows_svg += (
        f'<g class="fade" style="animation-delay:{delay:.2f}s">\n'
        f'  <circle cx="{colX+5}" cy="{rowY-4}" r="4" fill="{color}"></circle>\n'
        f'  <text x="{colX+16}" y="{rowY}" font-size="11" font-weight="{fw}" fill="{name_color}">{name}</text>\n'
        f'  <text x="{colX+189}" y="{rowY}" text-anchor="end" font-size="10" font-weight="{fw}" fill="#8b7aa8">{pct:.1f}%</text>\n'
        f'  <rect x="{colX+16}" y="{rowY+5}" width="150" height="3" rx="1.5" fill="#16112b"></rect>\n'
        f'  <rect class="bar" x="{colX+16}" y="{rowY+5}" width="{barw:.1f}" height="3" rx="1.5" fill="{color}" style="animation-delay:{delay:.2f}s"></rect>\n'
        f'</g>\n'
    )
    shown += 1

lang_count = sum(1 for n, v in langs.items() if 100*v["size"]/total_size >= 0.4)


def fmt(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 10_000:    return f"{n/1000:.1f}k"
    if n >= 1_000:     return f"{n/1000:.1f}k"
    return f"{n:,}"


# ── Preencher templates e salvar ────────────────────────────────
os.makedirs(os.path.join(HERE, "generated"), exist_ok=True)

def fill(name, repls):
    with open(os.path.join(TPL, name), encoding="utf-8") as f:
        s = f.read()
    for k, v in repls.items():
        s = s.replace("{{ " + k + " }}", str(v))
    with open(os.path.join(HERE, "generated", name), "w", encoding="utf-8") as f:
        f.write(s)

fill("overview.svg", {
    "login": login, "name": display_name,
    "stars": fmt(stars), "forks": fmt(forks), "followers": fmt(followers),
    "repos": str(len(repos)), "commits": fmt(commits), "prs": fmt(prs),
    "contributions": fmt(contribs), "lines_changed": fmt(lines_changed),
    "views": fmt(views),
})

fill("languages.svg", {
    "progress_bar": progress_svg, "lang_rows": lang_rows_svg,
    "repo_count": str(len(repos)), "lang_count": str(lang_count),
})

fill("activity.svg", {
    "total_contribs": fmt(contribs), "total_range": total_range,
    "current_streak": str(cur), "current_range": current_range,
    "longest_streak": str(best), "longest_range": longest_range,
    "ring_offset": ring_offset,
})

print()
print("=" * 52)
print(f"  {display_name}  (@{login})")
print(f"  Stars / Forks:        {fmt(stars)} / {fmt(forks)}")
print(f"  Followers:            {fmt(followers)}")
print(f"  Commits (all-time):   {fmt(commits)}")
print(f"  Pull Requests:        {fmt(prs)}")
print(f"  Contributions:        {fmt(contribs)}")
print(f"  Linhas alteradas:     {fmt(lines_changed)}")
print(f"  Views (14 dias):      {fmt(views)}")
print(f"  Streak atual:         {cur} dias ({current_range})")
print(f"  Maior streak:         {best} dias ({longest_range})")
print(f"  Repos analisados:     {len(repos)}")
print("=" * 52)
print()
print("SVGs gerados em github-stats/generated/")
print("Suba a pasta generated/ no repo pedrinbrekin/pedrinbrekin")
print("e referencie no README (veja README.md).")
