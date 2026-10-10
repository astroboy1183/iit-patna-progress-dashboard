"""Build the static progress dashboard from the course repo.

Usage: python dashboard/build.py --course <path to course repo> --out site
"""

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import shutil
from collections import Counter
from pathlib import Path

from collect import collect, humanize

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

ICONS = {
    "modules": '<path d="M12 3 3 8l9 5 9-5-9-5Z"/><path d="m3 13 9 5 9-5"/>',
    "project": '<path d="M21 8 12 3 3 8v8l9 5 9-5V8Z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
    "commit": '<circle cx="12" cy="12" r="3.5"/><path d="M3 12h5.5M15.5 12H21"/>',
    "code": '<path d="m8 7-5 5 5 5M16 7l5 5-5 5"/>',
    "check": '<rect x="3.5" y="3.5" width="17" height="17" rx="3"/><path d="m8 12 3 3 5-6"/>',
    "notes": '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5v-15Z"/><path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20v3H6.5"/><path d="M8 7.5h8M8 11h6"/>',
    "flip": '<path d="M3 12a9 9 0 0 1 15.5-6.2L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15.5 6.2L3 16"/><path d="M3 21v-5h5"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "moon": '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z"/>',
    "auto": '<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5v17a8.5 8.5 0 0 0 0-17Z" fill="currentColor"/>',
    "sparkle": '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z"/>',
    "up": '<path d="M12 19V5M5 12l7-7 7 7"/>',
    "flame": '<path d="M12 21c4 0 7-2.7 7-6.6 0-3.5-2.4-5.6-4-7.4-.3 2-1.3 3.2-2.6 3.8C12.9 7.6 11 5 9 3c.3 3.3-4 5.8-4 11.2C5 18.2 8 21 12 21Z"/>',
}


def icon(name):
    return (f'<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


# ---------------------------------------------------------------- sections


def hero(d):
    p, t = d["program"], d["totals"]
    pct = round(100 * t["topics_covered"] / t["topics_trackable"]) if t["topics_trackable"] else 0
    total, now = p["total_weeks"], p["week_now"]
    # progress ring
    r = 54
    circ = 2 * 3.14159265 * r
    ring = (f'<svg class="ring" viewBox="0 0 140 140" role="img" aria-label="{pct}% of curriculum topics covered">'
            f'<defs><linearGradient id="ringg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff"/>'
            f'<stop offset="1" style="stop-color:var(--glow)"/></linearGradient></defs>'
            f'<circle cx="70" cy="70" r="{r}" class="ring-track"/>'
            f'<circle cx="70" cy="70" r="{r}" class="ring-fill" stroke-dasharray="{circ * pct / 100:.1f} {circ:.1f}" '
            f'transform="rotate(-90 70 70)"/>'
            f'<text x="70" y="68" class="ring-num">{pct}%</text><text x="70" y="88" class="ring-lab">topics</text></svg>')
    # journey bar: one segment per module, sized by its scheduled weeks; each opens the module pop-up
    segs = []
    for i, m in enumerate(d["modules"]):
        w = len(m["weeks"])
        label = m["id"] if m["id"] != "CAP" else "★"
        tip = f'{m["id"]} · {m["title"]} · {m["schedule"]} · {m["covered"]}/{m["trackable"]} topics · {STATUS[m["status"]][1]}'
        segs.append(f'<button type="button" class="seg {m["status"]}" style="flex:{w};--i:{i}" data-module="{esc(m["id"])}" '
                    f'data-tip="{esc(tip)}" aria-label="{esc(tip)}. Open details"><span>{esc(label)}</span></button>')
    marker = 100 * (now - 0.5) / total
    return f"""
<header class="hero" id="top">
  <div class="fx" aria-hidden="true"><div class="aurora"></div><div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div></div>
  <canvas class="sky" aria-hidden="true"></canvas>
  <div class="hero-in">
    <div class="hero-text">
      <p class="eyebrow">{esc(p['institute'])} · {esc(p['months'])}-month certificate program · learning in public</p>
      <h1>{esc(p['name'])}</h1>
      <p class="who">{esc(p['owner'])}'s live progress, rebuilt from <a href="https://github.com/{esc(p['course_repo'])}">my code</a> on every push.
      Every ticked topic links to the file that proves it.</p>
      <div class="pills"><span class="pill">Week {now} of {total}</span><span class="pill">Started {esc(fmt_date(p['start_date']))}</span>
        <span class="pill live"><span class="dot" aria-hidden="true"></span>Auto-updating</span></div>
    </div>
    {ring}
  </div>
  <div class="journey" aria-label="Program timeline: week {now} of {total}">
    <div class="segs">{''.join(segs)}</div>
    <div class="you" style="left:{marker:.2f}%"><span>You are here · week {now}</span></div>
    <div class="jlegend"><span><i class="k completed"></i>Hands-on done</span><span><i class="k in_progress"></i>In progress</span>
      <span><i class="k not_started"></i>Not started</span><span class="muted">Segment width = scheduled weeks · click one for details</span></div>
  </div>
</header>"""


def back_rows(rows, foot=""):
    lis = "".join(f"<li><span>{esc(a)}</span><b>{esc(b)}</b></li>" for a, b in rows)
    return f'<ul class="bl">{lis}</ul>' + (f'<p class="bfoot">{esc(foot)}</p>' if foot else "")


def tiles(d):
    s, t, mods = d["stats"], d["totals"], d["modules"]
    plural = lambda n, w: f"{n} {w}{'s' if n != 1 else ''}"
    started = [m for m in mods if m["status"] != "not_started"]
    nxt = next((m for m in mods if m["status"] == "not_started"), None)
    built = [m for m in mods if m["project"]["evidence"]]
    by_week = Counter(n["week"] for n in d["notes"])
    latest = d["notes"][-1]["title"].split("·", 1)[-1].strip() if d["notes"] else ""
    practice = [(re.sub(r"^\d+_|_practice$", "", n).replace("_", " "), f"#{n.split('_')[0]}") for n in reversed(d["practice"])]
    projs = sorted(d["projects"], key=lambda p: -p["loc"])
    items = [
        ("modules", t["modules_started"], "modules started", f"{t['modules_completed']} with hands-on work done", "Where I am",
         back_rows([(SHORT.get(m["id"], m["title"]), f'{m["covered"]}/{m["trackable"]}') for m in started],
                   f'Next up: {nxt["id"]} · {SHORT.get(nxt["id"], nxt["title"])}' if nxt else "All modules started")),
        ("project", t["projects_built"], "module projects built", "detected from the code", "Projects detected",
         back_rows([(SHORT.get(m["id"], m["title"]), m["id"]) for m in built])),
        ("commit", s["commits"], "commits", f"on {s['active_days']} active days · best streak {plural(s['longest_streak'], 'day')}", "Activity",
         back_rows([("Active days", s["active_days"]), ("Best streak", plural(s["longest_streak"], "day")),
                    ("Current streak", plural(s["current_streak"], "day")), ("Started", fmt_date(s["first_commit"])),
                    ("Latest", fmt_date(s["last_commit"]))])),
        ("code", s["lines_of_code"], "lines of code", f"{s['python_files']} Python files · {plural(s['notebooks'], 'notebook')}", "Lines by project",
         back_rows([(humanize(p["path"].split("/")[-1]), f'{p["loc"]:,}') for p in projs[:5]])),
        ("check", s["practice_assignments"], "practice assignments", "solved", "Latest practice", back_rows(practice[:5])),
        ("notes", s["lecture_notes"], "lecture notes", f"{s['notes_words']:,} words · cover {t['topics_from_notes']} theory topics", "Notes by week",
         back_rows([(f"Week {w}", plural(n, "lecture")) for w, n in sorted(by_week.items(), key=lambda x: x[0] or 0)],
                   f"Latest: {latest}" if latest else "")),
    ]
    cells = "".join(
        f'<div class="tile" style="--i:{k}" tabindex="0" role="group" aria-label="{esc(l)}">'
        f'<div class="inner"><div class="face front spot">{icon(ic)}<span class="num" data-count="{n}">{n:,}</span>'
        f'<span class="lab">{esc(l)}</span><span class="sub">{esc(sub)}</span><span class="fliphint">{icon("flip")}</span></div>'
        f'<div class="face back"><h4>{esc(bt)}</h4>{back}</div></div></div>'
        for k, (ic, n, l, sub, bt, back) in enumerate(items))
    return (f'<section class="tiles" aria-label="Key numbers. Hover, focus or tap a card to flip it for details.">{cells}</section>')


def ev_label(ev):
    """Link text for a piece of evidence: the file name, or "lecture 7" for numbered lecture notes."""
    name = ev["path"].split("/")[-1]
    m = re.match(r"(\d+)_", name)
    if ev["kind"] == "notes" and m:
        return f"lecture {int(m.group(1))}"
    return name

SHORT = {"M1": "Foundations", "M2": "Models & APIs", "M3": "Apps without frameworks", "M4": "LangChain",
         "M5": "RAG", "M6": "Agents & MCP", "M7": "LangGraph", "M8": "GenAI tooling", "M9": "Automation",
         "M10": "Career & portfolio", "CAP": "Capstone"}


SOURCE = {"code": "Code", "notes": "Notes", "docs": "Docs", "readme": "README"}


def topic_rows(m, repo, sha):
    rows = []
    for k, tp in enumerate(m["topics"]):
        if tp["evidence"]:
            ev = tp["evidence"][0]
            more = f' <span class="more">+{len(tp["evidence"]) - 1} more</span>' if len(tp["evidence"]) > 1 else ""
            kind = ev["kind"]
            rows.append(f'<tr class="yes" style="--k:{k}"><td class="tcell"><span class="mark" aria-hidden="true">✓</span>{esc(tp["name"])}</td>'
                        f'<td><span class="src s-{kind}">{SOURCE.get(kind, kind)}</span></td>'
                        f'<td class="proof"><a class="ev" href="{esc(blob(repo, ev["path"], ev["line"], sha))}" title="{esc(ev["path"])}">{esc(ev_label(ev))}</a>{more}</td></tr>')
        else:
            label = "Not yet" if tp["trackable"] else "Concept"
            rows.append(f'<tr class="no" style="--k:{k}"><td class="tcell"><span class="mark" aria-hidden="true">○</span>{esc(tp["name"])}</td>'
                        f'<td><span class="src s-none">—</span></td><td class="proof"><span class="muted">{label}</span></td></tr>')
    pr = m["project"]
    foot = ""
    if pr["name"]:
        if pr["evidence"]:
            ev = pr["evidence"][0]
            foot = (f'<tfoot><tr class="projrow yes"><td colspan="3"><span class="mark" aria-hidden="true">✓</span><b>Project</b> {esc(pr["name"])}'
                    f' <a class="ev" href="{esc(blob(repo, ev["path"], ev["line"], sha))}" title="{esc(ev["path"])}">{esc(ev["path"].split("/")[-1])}</a></td></tr></tfoot>')
        else:
            foot = (f'<tfoot><tr class="projrow"><td colspan="3"><span class="mark" aria-hidden="true">○</span><b>Project</b> '
                    f'{esc(pr["name"])}</td></tr></tfoot>')
    return ("<table class=\"ttable\"><thead><tr><th scope=\"col\">Topic</th><th scope=\"col\">Covered by</th>"
            f"<th scope=\"col\">Proof</th></tr></thead><tbody>{''.join(rows)}</tbody>{foot}</table>")


def roadmap(d):
    repo, sha = d["program"]["course_repo"], d["head"] or "main"
    mods = d["modules"]
    # the tab shown first: the module scheduled now, else the last one started
    active = next((m["id"] for m in mods if m["scheduled_now"]), None) or \
        next((m["id"] for m in reversed(mods) if m["status"] != "not_started"), mods[0]["id"])
    overview, tabs, panels = [], [], []
    for k, m in enumerate(mods):
        icon_, label = STATUS[m["status"]]
        pct = round(100 * m["covered"] / m["trackable"]) if m["trackable"] else 0
        mid = m["id"] if m["id"] != "CAP" else "★"
        short = SHORT.get(m["id"], m["title"])
        pr = m["project"]
        proj = ('<span class="pmark yes" title="Project built">✓ Built</span>' if pr["evidence"]
                else '<span class="pmark">—</span>')
        now = ' <span class="now">Now</span>' if m["scheduled_now"] else ""
        overview.append(
            f'<tr class="mrow {m["status"]}" data-id="{esc(m["id"])}" style="--k:{k}">'
            f'<th scope="row"><a class="mopen" href="#panel-{esc(m["id"])}" data-tab="{esc(m["id"])}">'
            f'<span class="mid">{esc(mid)}</span><span class="mname">{esc(m["title"])}{now}<small>{esc(m["schedule"])}</small></span></a></th>'
            f'<td class="c-weeks">{esc(m["schedule"])}</td>'
            f'<td><span class="status s-{m["status"]}"><span aria-hidden="true">{icon_}</span> <span class="slbl">{label}</span></span></td>'
            f'<td><div class="mprog"><div class="meter" role="img" aria-label="{m["covered"]} of {m["trackable"]} topics">'
            f'<div class="fill" style="width:{pct}%"></div></div><span class="count">{m["covered"]}/{m["trackable"]}</span></div></td>'
            f'<td class="c-proj">{proj}</td></tr>')
        sel = m["id"] == active
        tabs.append(f'<button type="button" role="tab" class="mtab {m["status"]}" id="tab-{esc(m["id"])}" aria-controls="panel-{esc(m["id"])}" '
                    f'aria-selected="{"true" if sel else "false"}" tabindex="{0 if sel else -1}" data-tab="{esc(m["id"])}">'
                    f'<i class="sdot" aria-hidden="true"></i><b>{esc(mid)}</b><span>{esc(short)}</span></button>')
        panels.append(f"""
<section class="mpanel {m['status']}{' active' if sel else ''}" id="panel-{esc(m['id'])}" role="tabpanel" aria-labelledby="tab-{esc(m['id'])}"
  data-id="{esc(m['id'])}" data-pct="{pct}" data-short="{esc(short)}">
  <header class="phead">
    <span class="mid">{esc(mid)}</span>
    <div class="ptext"><h3 class="ptitle">{esc(m['title'])}</h3><p class="psched">{esc(m['schedule'])} · <span class="pcount">{m['covered']}/{m['trackable']} topics</span></p></div>
    <span class="status s-{m['status']}"><span aria-hidden="true">{icon_}</span> {label}</span>
  </header>
  <div class="twrap">{topic_rows(m, repo, sha)}</div>
</section>""")
    return f"""
<section class="block" id="roadmap">
  <h2>Curriculum roadmap</h2>
  <p class="note">The program's 10 modules and capstone, from the brochure. The whole repo is read on every push: a topic is ticked
  when my code uses it, or, for theory, when my lecture notes cover it. Every tick links to the file and line that proves it.
  "Hands-on done" means the module's project is built and most of its topics are covered.</p>
  <h3 class="sub-h">All modules at a glance</h3>
  <div class="mtable-wrap"><table class="mtable">
    <thead><tr><th scope="col">Module</th><th scope="col" class="c-weeks">Schedule</th><th scope="col">Status</th>
      <th scope="col">Topics</th><th scope="col" class="c-proj">Project</th></tr></thead>
    <tbody>{''.join(overview)}</tbody>
  </table></div>
  <h3 class="sub-h" id="topics-h">Topics in each module</h3>
  <div class="mtabs-wrap"><div class="mtabs" role="tablist" aria-labelledby="topics-h">{''.join(tabs)}<span class="tab-ink" aria-hidden="true"></span></div></div>
  <div class="mpanels">{''.join(panels)}</div>
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
            rects.append(f'<rect class="{cls}" style="--d:{wk}" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" data-tip="{esc(tip)}"><title>{esc(tip)}</title></rect>')
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
    for k, pr in enumerate(d["projects"]):
        libs = "".join(f"<code>{esc(l)}</code>" for l in pr["libraries"]) or '<span class="muted">standard library only</span>'
        span = fmt_date(pr["first"]) + (f" – {fmt_date(pr['last'])}" if pr["last"] != pr["first"] else "")
        cards.append(f"""<a class="pcard spot" style="--k:{k}" href="https://github.com/{esc(repo)}/tree/main/{esc(pr['path'])}">
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
    libs = d["libraries"]
    top = max((n for _, n in libs), default=1)
    rows = "".join(f'<li style="--k:{k}"><code>{esc(name)}</code><span class="lbar"><span style="width:{100 * n / top:.1f}%"></span></span>'
                   f'<span class="lcount">{n}</span></li>' for k, (name, n) in enumerate(libs))
    table = "".join(f"<tr><td>{esc(name)}</td><td>{n}</td></tr>" for name, n in libs)
    return f"""
<section class="block half" id="libraries">
  <h2>Libraries I've used</h2>
  <p class="note">Third-party imports across all my code: number of files that use each.</p>
  <ul class="liblist" role="img" aria-label="Bar chart of files per library">{rows}</ul>
  <details class="table-view"><summary>Show as a table</summary>
    <table><thead><tr><th>Library</th><th>Files</th></tr></thead><tbody>{table}</tbody></table></details>
</section>"""


def recent(d):
    repo = d["program"]["course_repo"]
    rows = "".join(f'<li style="--k:{k}"><span class="cdot" aria-hidden="true"></span><div><span class="msg">{esc(c["subject"])}</span>'
                   f'<span class="when">{esc(fmt_date(c["day"]))} · <a href="https://github.com/{esc(repo)}/commit/{c["sha"]}"><code>{c["sha"][:7]}</code></a></span></div></li>'
                   for k, c in enumerate(d["commits"]))
    return f"""
<section class="block half" id="recent">
  <h2>Recent commits</h2>
  <ul class="commits">{rows}</ul>
</section>"""


def minibar(d):
    p, t = d["program"], d["totals"]
    pct = round(100 * t["topics_covered"] / t["topics_trackable"]) if t["topics_trackable"] else 0
    circ = 2 * 3.14159265 * 15
    links = (("roadmap", "Roadmap"), ("activity", "Activity"), ("projects", "Projects"), ("libraries", "Libraries"), ("recent", "Commits"))
    nav = "".join(f'<a href="#{i}" data-sec="{i}">{t}</a>' for i, t in links)
    return f"""<div class="minibar">
  <div class="mb-in">
    <a class="mb-brand" href="#top" aria-label="Back to top: {pct}% of topics covered"><svg class="mb-ring" viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="15" class="t"/>
      <circle cx="20" cy="20" r="15" class="f" stroke-dasharray="{circ * pct / 100:.1f} {circ:.1f}" transform="rotate(-90 20 20)"/></svg>
      <span><b>{pct}%<span class="mb-long"> · GenAI program</span></b><small>{esc(p['owner'])} · week {p['week_now']} of {p['total_weeks']}</small></span></a>
    <nav class="mb-nav" aria-label="Sections">{nav}</nav>
  </div>
</div>"""


def toast(d):
    if not d["commits"]:
        return ""
    c, repo = d["commits"][0], d["program"]["course_repo"]
    return (f'<div class="toast" id="toast" role="status" hidden data-when="{esc(c["date"])}">'
            f'<span class="tdot" aria-hidden="true"></span><div class="tbody"><b>Latest push <span class="ago">{esc(fmt_date(c["day"]))}</span></b>'
            f'<span class="tmsg">{esc(c["subject"])}</span>'
            f'<a href="https://github.com/{esc(repo)}/commit/{c["sha"]}"><code>{c["sha"][:7]}</code> on GitHub</a></div>'
            f'<button type="button" class="tclose" aria-label="Dismiss">×</button><i class="tbar" aria-hidden="true"></i></div>')


def page(d, generated, ver):
    p = d["program"]
    title = f"{p['owner']} · IIT Patna GenAI program progress"
    desc = f"Live progress of {p['owner']} in IIT Patna's {p['name']}, rebuilt from code on every push."
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(desc)}"><meta name="build" content="__BUILD__">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%23256abf'/><path d='M8 22l6-7 4 4 6-9' stroke='white' stroke-width='3' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<script>try{{var r=document.documentElement,t=localStorage.getItem("theme"),c=localStorage.getItem("palette");
if(t==="light"||t==="dark")r.setAttribute("data-theme",t);if(c==="ocean"||c==="sunset"||c==="aurora")r.setAttribute("data-palette",c)}}catch(e){{}}</script>
<link rel="stylesheet" href="assets/style.css?v={ver['style.css']}">
</head><body>
<div class="sprog" aria-hidden="true"></div>
<div class="amb" aria-hidden="true"><i></i><i></i><i></i></div>
{minibar(d)}
{hero(d)}
<main>
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
{toast(d)}
<div class="dock" role="group" aria-label="Display settings">
  <button type="button" class="dbtn" id="palette-btn" aria-label="Colour theme: Aurora"><span class="swatch" aria-hidden="true"></span></button>
  <button type="button" class="dbtn" id="theme-btn" aria-label="Theme: automatic">{icon("auto")}{icon("sun")}{icon("moon")}</button>
  <button type="button" class="dbtn" id="motion-btn" aria-pressed="true" aria-label="Animations">{icon("sparkle")}</button>
  <button type="button" class="dbtn" id="top-btn" aria-label="Back to top">{icon("up")}</button>
</div>
<dialog id="modal" class="modal" aria-labelledby="modal-title"><div class="mcontent"></div></dialog>
<script src="assets/app.js?v={ver['app.js']}"></script>
</body></html>"""


def new_tabs(html_):
    """Every link that leaves the dashboard opens in a new tab, so the dashboard stays open.
    In-page links (#roadmap, #panel-M2, …) are left alone."""
    return re.sub(r'<a (?![^>]*\btarget=)([^>]*\bhref="(?!#)[^"]*")', r'<a target="_blank" rel="noopener" \1', html_)


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
    ver = {}
    for f in ("style.css", "app.js"):
        src = ROOT / "dashboard" / "static" / f
        shutil.copy(src, out / "assets" / f)
        ver[f] = hashlib.sha256(src.read_bytes()).hexdigest()[:10]  # cache-buster: changes whenever the file does
    generated = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).strftime("%d %b %Y, %H:%M IST")
    html_ = new_tabs(page(data, generated, ver))
    # Build id: changes only when the page content changes (the "Updated …" time is left out), so hourly rebuilds
    # with nothing new don't make open pages reload. app.js compares it with version.txt to escape stale caches.
    build_id = hashlib.sha256(html_.replace(generated, "").encode()).hexdigest()[:12]
    (out / "index.html").write_text(html_.replace("__BUILD__", build_id))
    (out / "version.txt").write_text(build_id + "\n")
    (out / "data.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
    (out / ".nojekyll").write_text("")
    t = data["totals"]
    print(f"built {out}: {t['topics_covered']}/{t['topics_trackable']} topics, {t['modules_started']} modules started, "
          f"{data['stats']['commits']} commits")


if __name__ == "__main__":
    main()
