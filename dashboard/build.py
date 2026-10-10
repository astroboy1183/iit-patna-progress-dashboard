"""Build the static progress dashboard from the course repo.

Usage: python dashboard/build.py --course <path to course repo> --out site
"""

import argparse
import datetime as dt
import html
import json
import shutil
from pathlib import Path

from collect import collect

ROOT = Path(__file__).resolve().parent.parent
STATUS = {
    "completed": ("✓", "Hands-on done"),
    "in_progress": ("◐", "In progress"),
    "not_started": ("○", "Not started"),
}


def esc(t):
    return html.escape(str(t), quote=True)


def fmt_date(iso):
    if not iso:
        return ""
    d = dt.date.fromisoformat(iso[:10])
    return f"{d.day} {d.strftime('%b %Y')}"


def blob(repo, path, line=None, sha="main"):
    url = f"https://github.com/{repo}/blob/{sha}/{path}"
    return url + (f"#L{line}" if line and not path.endswith(".ipynb") else "")


# ---------------------------------------------------------------- sections


def hero(d):
    p, t, s = d["program"], d["totals"], d["stats"]
    pct = round(100 * t["topics_covered"] / t["topics_trackable"]) if t["topics_trackable"] else 0
    week_pct = round(100 * p["week_now"] / p["total_weeks"])
    return f"""
<header class="hero">
  <p class="eyebrow">{esc(p['institute'])} · {esc(p['months'])}-month certificate program · learning in public</p>
  <h1>{esc(p['owner'])}'s progress in the <span>{esc(p['name'])}</span></h1>
  <p class="lede">This page rebuilds itself every time I push code to my
  <a href="https://github.com/{esc(p['course_repo'])}">course repo</a>. Each ticked topic links to the code that shows it.</p>
  <div class="headline">
    <div class="big"><span class="num">{pct}%</span><span class="lab">of hands-on topics covered</span>
      <span class="sub">{t['topics_covered']} of {t['topics_trackable']} topics, across {t['modules']} modules</span></div>
    <div class="timeline" role="img" aria-label="Week {p['week_now']} of {p['total_weeks']}">
      <div class="tl-head"><span>Program timeline</span><span>Week {p['week_now']} of {p['total_weeks']}</span></div>
      <div class="bar"><div class="fill" style="width:{week_pct}%"></div></div>
      <div class="tl-foot"><span>Started {esc(fmt_date(p['start_date']))}</span><span>{week_pct}% of the program's time</span></div>
    </div>
  </div>
</header>"""


def tiles(d):
    s, t = d["stats"], d["totals"]
    items = [
        (t["modules_started"], "modules started", f"{t['modules_completed']} with hands-on work done"),
        (t["projects_built"], "module projects built", "detected from the code"),
        (s["commits"], "commits", f"on {s['active_days']} active days"),
        (s["lines_of_code"], "lines of code", f"{s['python_files']} Python files · {s['notebooks']} notebook{'s' if s['notebooks'] != 1 else ''}"),
        (s["practice_assignments"], "practice assignments", "solved"),
        (s["longest_streak"], "day best streak", f"current streak: {s['current_streak']} day{'s' if s['current_streak'] != 1 else ''}"),
    ]
    cells = "".join(f'<div class="tile"><span class="num">{n:,}</span><span class="lab">{esc(l)}</span>'
                    f'<span class="sub">{esc(sub)}</span></div>' for n, l, sub in items)
    return f'<section class="tiles" aria-label="Key numbers">{cells}</section>'


def roadmap(d):
    repo, sha = d["program"]["course_repo"], d["head"] or "main"
    cards = []
    for m in d["modules"]:
        icon, label = STATUS[m["status"]]
        pct = round(100 * m["covered"] / m["trackable"]) if m["trackable"] else 0
        topics = []
        for tp in m["topics"]:
            if tp["evidence"]:
                ev = tp["evidence"][0]
                more = f' <span class="more">+{len(tp["evidence"]) - 1} more</span>' if len(tp["evidence"]) > 1 else ""
                topics.append(f'<li class="yes"><span class="mark" aria-hidden="true">✓</span><span class="tname">{esc(tp["name"])}</span>'
                              f'<span class="evw"><a class="ev" href="{esc(blob(repo, ev["path"], ev["line"], sha))}">{esc(ev["path"].split("/")[-1])}</a>{more}</span></li>')
            elif tp["trackable"]:
                topics.append(f'<li class="no"><span class="mark" aria-hidden="true">○</span><span class="tname">{esc(tp["name"])}</span></li>')
            else:
                topics.append(f'<li class="concept"><span class="mark" aria-hidden="true">·</span><span class="tname">{esc(tp["name"])}</span>'
                              f'<span class="evw"><span class="tag">concept</span></span></li>')
        pr = m["project"]
        if pr["name"]:
            if pr["evidence"]:
                ev = pr["evidence"][0]
                proj = (f'<p class="proj yes"><span class="mark" aria-hidden="true">✓</span> <b>Project:</b> {esc(pr["name"])} '
                        f'<a class="ev" href="{esc(blob(repo, ev["path"], ev["line"], sha))}">{esc(ev["path"])}</a></p>')
            else:
                proj = f'<p class="proj"><span class="mark" aria-hidden="true">○</span> <b>Project:</b> {esc(pr["name"])}</p>'
        else:
            proj = ""
        meter = (f'<div class="meter" role="img" aria-label="{m["covered"]} of {m["trackable"]} topics">'
                 f'<div class="fill" style="width:{pct}%"></div></div>'
                 f'<span class="count">{m["covered"]}/{m["trackable"]} topics</span>') if m["trackable"] else '<span class="count">concepts only</span>'
        now = '<span class="now">Scheduled now</span>' if m["scheduled_now"] else ""
        open_attr = " open" if m["status"] != "not_started" or m["scheduled_now"] else ""
        cards.append(f"""
<details class="module {m['status']}"{open_attr}>
  <summary>
    <span class="mid">{esc(m['id'] if m['id'] != 'CAP' else '★')}</span>
    <span class="mtitle">{esc(m['title'])}<span class="sched">{esc(m['schedule'])}</span></span>
    <span class="status s-{m['status']}"><span aria-hidden="true">{icon}</span> {label}</span>
    <span class="mmeter">{meter}</span>{now}
  </summary>
  <ul class="topics">{''.join(topics)}</ul>
  {proj}
</details>""")
    return f"""
<section class="block" id="roadmap">
  <h2>Curriculum roadmap</h2>
  <p class="note">The program's 10 modules and capstone, from the brochure. A topic is ticked when my code shows it;
  "concept" topics are taught in lectures and can't be read from code. "Hands-on done" means the module's project is
  built and most of its hands-on topics appear in my code.</p>
  <div class="modules">{''.join(cards)}</div>
</section>"""


def heatmap(d):
    p = d["program"]
    start = dt.date.fromisoformat(p["start_date"])
    start -= dt.timedelta(days=start.weekday())  # align columns to Mondays
    weeks = p["total_weeks"] + 1
    today = dt.date.fromisoformat(p["today"])
    act = d["activity"]
    cell, gap, top, left = 14, 3, 18, 30
    w = left + weeks * (cell + gap)
    h = top + 7 * (cell + gap)

    def level(n):
        return 0 if n == 0 else 1 if n == 1 else 2 if n <= 3 else 3 if n <= 6 else 4

    rects, months, rows = [], [], []
    last_month = None
    for wk in range(weeks):
        for wd in range(7):
            day = start + dt.timedelta(days=wk * 7 + wd)
            n = act.get(day.isoformat(), 0)
            future = day > today
            x, y = left + wk * (cell + gap), top + wd * (cell + gap)
            cls = "future" if future else f"l{level(n)}"
            tip = f"{fmt_date(day.isoformat())}: " + ("in the future" if future else f"{n} commit{'s' if n != 1 else ''}")
            rects.append(f'<rect class="{cls}" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" data-tip="{esc(tip)}"><title>{esc(tip)}</title></rect>')
            if wd == 0 and day.month != last_month:
                months.append(f'<text class="axis" x="{x}" y="11">{day.strftime("%b")}</text>')
                last_month = day.month
        wk_start = start + dt.timedelta(days=wk * 7)
        n_week = sum(act.get((wk_start + dt.timedelta(days=i)).isoformat(), 0) for i in range(7))
        if wk_start <= today:
            rows.append(f"<tr><td>{esc(fmt_date(wk_start.isoformat()))}</td><td>{n_week}</td></tr>")
    labels = "".join(f'<text class="axis" x="0" y="{top + i * (cell + gap) + 11}">{n}</text>'
                     for i, n in ((0, "Mon"), (2, "Wed"), (4, "Fri")))
    legend = "".join(f'<span class="lg l{i}" aria-hidden="true"></span>' for i in range(5))
    return f"""
<section class="block" id="activity">
  <h2>Coding activity</h2>
  <p class="note">Commits per day to the course repo, across the program's {p['total_weeks']} weeks.</p>
  <div class="heat-wrap"><svg class="heat" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img"
    aria-label="Commits per day heatmap">{''.join(months)}{labels}{''.join(rects)}</svg></div>
  <div class="heat-legend"><span>Fewer</span>{legend}<span>More</span>
    <span class="lgk">1 · 2–3 · 4–6 · 7+ commits</span></div>
  <details class="table-view"><summary>Show as a table (commits per week)</summary>
    <table><thead><tr><th>Week starting</th><th>Commits</th></tr></thead><tbody>{''.join(rows)}</tbody></table></details>
</section>"""


def project_cards(d):
    repo = d["program"]["course_repo"]
    cards = []
    for pr in d["projects"]:
        libs = "".join(f"<code>{esc(l)}</code>" for l in pr["libraries"]) or '<span class="muted">standard library only</span>'
        span = fmt_date(pr["first"]) + (f" – {fmt_date(pr['last'])}" if pr["last"] != pr["first"] else "")
        cards.append(f"""<a class="pcard" href="https://github.com/{esc(repo)}/tree/main/{esc(pr['path'])}">
  <h3>{esc(pr['title'])}</h3><p class="path">{esc(pr['path'])}/</p>
  {f'<p>{esc(pr["description"])}</p>' if pr["description"] else ''}
  <p class="meta">{pr['files']} code file{'s' if pr['files'] != 1 else ''} · {pr['loc']:,} lines · {esc(span)}</p>
  <div class="libs">{libs}</div></a>""")
    return f"""
<section class="block" id="projects">
  <h2>What I've built</h2>
  <p class="note">Every folder in the course repo with its own <code>requirements.txt</code>.</p>
  <div class="pcards">{''.join(cards)}</div>
</section>"""


def libraries(d):
    rows = "".join(f'<li><code>{esc(name)}</code><span class="lcount">{n} file{"s" if n != 1 else ""}</span></li>'
                   for name, n in d["libraries"])
    return f"""
<section class="block half" id="libraries">
  <h2>Libraries I've used</h2>
  <p class="note">Third-party imports across all my code, by number of files.</p>
  <ul class="liblist">{rows}</ul>
</section>"""


def recent(d):
    repo = d["program"]["course_repo"]
    rows = "".join(f'<li><a href="https://github.com/{esc(repo)}/commit/{c["sha"]}"><code>{c["sha"][:7]}</code></a>'
                   f'<span class="msg">{esc(c["subject"])}</span><span class="when">{esc(fmt_date(c["day"]))}</span></li>'
                   for c in d["commits"])
    return f"""
<section class="block half" id="recent">
  <h2>Recent commits</h2>
  <ul class="commits">{rows}</ul>
</section>"""


def page(d, generated):
    p = d["program"]
    title = f"{p['owner']} · IIT Patna GenAI program progress"
    desc = f"Live progress of {p['owner']} in IIT Patna's {p['name']}, rebuilt from code on every push."
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(desc)}">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%23256abf'/><path d='M8 22l6-7 4 4 6-9' stroke='white' stroke-width='3' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>">
<link rel="stylesheet" href="assets/style.css">
</head><body>
<main>
{hero(d)}
{tiles(d)}
{roadmap(d)}
{heatmap(d)}
{project_cards(d)}
<div class="two">{libraries(d)}{recent(d)}</div>
<footer>
  <p>Updated {esc(generated)} from commit <a href="https://github.com/{esc(p['course_repo'])}/commit/{esc(d['head'])}"><code>{esc(d['head'][:7])}</code></a>
  of <a href="https://github.com/{esc(p['course_repo'])}">{esc(p['course_repo'])}</a> ·
  <a href="{esc(p['course_page'])}">About the program</a> ·
  <a href="https://github.com/astroboy1183/iit-patna-progress-dashboard">How this dashboard works</a> ·
  <a href="data.json">Raw data</a></p>
</footer>
</main>
<div id="tip" class="tip" role="tooltip" hidden></div>
<script src="assets/app.js"></script>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True, help="path to a clone of the course repo (full history)")
    ap.add_argument("--out", default=str(ROOT / "site"))
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD), for testing")
    args = ap.parse_args()
    today = dt.date.fromisoformat(args.today) if args.today else None
    data = collect(args.course, ROOT / "curriculum.yaml", today)
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    (out / "assets").mkdir(parents=True)
    for f in ("style.css", "app.js"):
        shutil.copy(ROOT / "dashboard" / "static" / f, out / "assets" / f)
    generated = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).strftime("%d %b %Y, %H:%M IST")
    (out / "index.html").write_text(page(data, generated))
    (out / "data.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
    (out / ".nojekyll").write_text("")
    t = data["totals"]
    print(f"built {out}: {t['topics_covered']}/{t['topics_trackable']} topics, {t['modules_started']} modules started, "
          f"{data['stats']['commits']} commits")


if __name__ == "__main__":
    main()
