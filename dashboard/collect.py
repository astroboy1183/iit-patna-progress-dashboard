"""Read the course repo and work out progress: curriculum evidence, activity, projects and libraries.

Everything here is derived from the repo's tracked files and git history, so the dashboard changes
only when the repo does. Every tracked file is read and given a kind:
  code    .py files and notebook code cells: imports, patterns, providers, count rules
  notes   markdown inside a notes/ folder (lecture notes): headings rules
  docs    other markdown and text, plus notebook markdown cells: headings rules
  deps    requirements*.txt, pyproject.toml
  config  .json, .yaml, .toml, dotfiles
  data    everything else (spreadsheets, CSVs, images)
`paths` rules match any tracked file.
"""

import ast
import datetime as dt
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

import yaml

CODE_EXT = {".py", ".ipynb"}
DOC_EXT = {".md", ".markdown", ".rst", ".txt"}
CONFIG_EXT = {".json", ".yaml", ".yml", ".toml", ".cfg", ".ini"}
# Evidence order on the page: hands-on code first, then lecture notes, then other docs, READMEs last.
KIND_RANK = {"code": 0, "notes": 1, "docs": 2, "readme": 3}
STDLIB = set(sys.stdlib_module_names)


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


# ---------------------------------------------------------------- reading code


def file_kind(rel):
    p = PurePosixPath(rel)
    suffix, name = p.suffix.lower(), p.name.lower()
    if suffix in CODE_EXT:
        return "code"
    if name.startswith("requirements") or name == "pyproject.toml":
        return "deps"
    if suffix in DOC_EXT:
        return "notes" if "notes" in p.parts[:-1] else "docs"
    if suffix in CONFIG_EXT or name.startswith("."):
        return "config"
    return "data"


def notebook_parts(path):
    """(code, markdown) of a notebook: code cells (magics and shell lines removed) and markdown cells."""
    try:
        nb = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return "", ""
    code, md = [], []
    for c in nb.get("cells", []):
        src = c.get("source", "")
        src = "".join(src) if isinstance(src, list) else src
        if c.get("cell_type") == "code":
            code.append("\n".join(l for l in src.splitlines() if not l.lstrip().startswith(("%", "!"))))
        elif c.get("cell_type") == "markdown":
            md.append(src)
    return "\n\n".join(code), "\n\n".join(md)


def headings_of(text):
    """(line number, heading text) for each markdown heading, skipping fenced code blocks
    (where "# ..." is a comment, not a heading)."""
    out, fence = [], None
    for n, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            mark = stripped[:3]
            fence = None if fence == mark else (fence or mark)
            continue
        if fence:
            continue
        m = re.match(r"#{1,6}\s+(.+?)\s*#*\s*$", line)
        if m:
            out.append((n, m.group(1)))
    return out


def imports_of(code):
    """Full dotted module names imported by a piece of code (AST first, regex fallback)."""
    found = set()
    try:
        for node in ast.walk(ast.parse(code)):
            if isinstance(node, ast.Import):
                found.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                found.add(node.module)
    except SyntaxError:
        found.update(re.findall(r"^\s*(?:from|import)\s+([A-Za-z_][\w.]*)", code, re.M))
    return found


class RepoFile:
    """One tracked file. Only code files have `code` and `imports`; markdown files and notebook
    markdown cells have `headings`. Spreadsheets and other binary files are not read."""

    def __init__(self, repo, rel):
        self.rel = rel
        self.kind = file_kind(rel)
        self.code, self.headings, self.words = "", [], 0
        p = repo / rel
        if self.kind == "code" and rel.endswith(".ipynb"):
            self.code, md = notebook_parts(p)
            self.headings = [(None, h) for _, h in headings_of(md)]  # cell line numbers don't map to the file
        elif self.kind == "code":
            self.code = p.read_text(encoding="utf-8", errors="replace")
        elif self.kind in ("notes", "docs") and PurePosixPath(rel).suffix.lower() != ".txt":
            text = p.read_text(encoding="utf-8", errors="replace")
            self.headings = headings_of(text)
            self.words = len(text.split())
        self.imports = imports_of(self.code) if self.code else set()
        self.loc = sum(1 for l in self.code.splitlines() if l.strip() and not l.strip().startswith("#"))

    @property
    def evidence_kind(self):
        """Kind shown next to the evidence link: code, notes, docs, or readme for README files."""
        if self.kind == "docs" and PurePosixPath(self.rel).stem.lower() == "readme":
            return "readme"
        return self.kind

    def imports_any(self, prefixes):
        """True if any import is one of `prefixes`, a submodule of one, or (for a bare name like
        "langchain") a sibling package such as langchain_core or langchain_openai."""
        for i in self.imports:
            top = i.split(".")[0]
            for p in prefixes:
                if i == p or i.startswith(p + "."):
                    return True
                if "." not in p and (top == p or top.startswith(p + "_")):
                    return True
        return False

    def line_of(self, regex):
        m = re.search(regex, self.code, re.M)
        if not m:
            return None
        return self.code.count("\n", 0, m.start()) + 1


# ---------------------------------------------------------------- evidence rules


def glob_regex(g):
    """Glob to regex: ** matches across folders, * and ? stay within one folder."""
    out, i = "", 0
    while i < len(g):
        if g.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif g.startswith("**", i):
            out += ".*"
            i += 2
        elif g[i] == "*":
            out += "[^/]*"
            i += 1
        elif g[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(g[i])
            i += 1
    return re.compile(out + r"\Z")


def path_match(rel, globs):
    return any(glob_regex(g).match(rel) for g in globs)


def rule_hits(rule, files):
    """Return a list of (path, line) evidence for one rule. Empty list = no match."""
    hits = []
    for f in files:
        h = file_hit(rule, f)
        if h:
            hits.append(h)
    return hits


def file_hit(rule, f):
    """Evidence (path, line) if `rule` matches source file `f`, else None."""
    if "paths" in rule:
        return (f.rel, None) if path_match(f.rel, rule["paths"]) else None
    if "imports" in rule:
        if not f.imports_any(rule["imports"]):
            return None
        mods = "|".join(re.escape(m) for m in rule["imports"])
        return (f.rel, f.line_of(rf"^\s*(?:from|import)\s+({mods})"))
    if "headings" in rule:
        for line, text in f.headings:
            if any(re.search(pat, text, re.I) for pat in rule["headings"]):
                return (f.rel, line)
        return None
    if "patterns" in rule:
        for pat in rule["patterns"]:
            line = f.line_of(pat)
            if line:
                return (f.rel, line)
        return None
    if "providers" in rule:
        spec = rule["providers"]
        used = {p for p in spec["any"] if f.imports_any([p])}
        return (f.rel, None) if len(used) >= spec.get("min", 2) else None
    if "count" in rule:
        spec = rule["count"]
        return (f.rel, f.line_of(spec["pattern"])) if len(re.findall(spec["pattern"], f.code)) >= spec["min"] else None
    if "same_file" in rule:
        parts = [file_hit(r, f) for r in rule["same_file"]]
        if all(parts):
            line = next((h[1] for h in parts if h and h[1]), None)
            return (f.rel, line)
        return None
    raise ValueError(f"unknown evidence rule: {rule}")


def evaluate(evidence, files):
    """Evidence for a topic: one entry per matching file, strongest kind first (code, notes, docs, READMEs)."""
    by_path = {f.rel: f for f in files}
    seen, out = set(), []
    for rule in evidence or []:
        for path, line in rule_hits(rule, files):
            if path not in seen:
                seen.add(path)
                kind = by_path[path].evidence_kind
                out.append({"path": path, "line": line, "kind": kind})
    out.sort(key=lambda e: KIND_RANK.get(e["kind"], 4))  # stable: rule order kept within a kind
    return out


# ---------------------------------------------------------------- activity


def commits(repo):
    out = []
    for line in git(repo, "log", "--format=%H%x1f%aI%x1f%s").splitlines():
        sha, when, subject = line.split("\x1f", 2)
        out.append({"sha": sha, "date": when, "day": when[:10], "subject": subject})
    return out


def streaks(days, today):
    if not days:
        return 0, 0
    ds = sorted({dt.date.fromisoformat(d) for d in days})
    longest = run = 1
    for a, b in zip(ds, ds[1:]):
        run = run + 1 if (b - a).days == 1 else 1
        longest = max(longest, run)
    current = 0
    day = today if today in ds else today - dt.timedelta(days=1)
    s = set(ds)
    while day in s:
        current += 1
        day -= dt.timedelta(days=1)
    return current, longest


NAMESPACE_PACKAGES = {"google", "azure"}


def library_name(module):
    """Top-level library of an import; namespace packages keep their second level (google.generativeai)."""
    parts = module.split(".")
    return ".".join(parts[:2]) if parts[0] in NAMESPACE_PACKAGES and len(parts) > 1 else parts[0]


# ---------------------------------------------------------------- projects


def humanize(name):
    name = re.sub(r"^\d+[_\- ]*", "", name)
    words = re.split(r"[_\- ]+", name)
    keep = {"api", "ai", "llm", "rag", "vs", "ui", "cli", "mcp"}
    return " ".join(w.upper() if w.lower() in keep - {"vs"} else w.lower() if w.lower() == "vs" else w.capitalize()
                    for w in words if w)


def projects(repo, all_paths, sources, overrides):
    """A project is a folder that contains a requirements.txt (the course's own convention)."""
    dirs = sorted({str(PurePosixPath(p).parent) for p in all_paths if PurePosixPath(p).name == "requirements.txt"})
    out = []
    for d in dirs:
        inside = [p for p in all_paths if p.startswith(d + "/")]
        nested = [o for o in dirs if o != d and o.startswith(d + "/")]
        own = [p for p in inside if not any(p.startswith(n + "/") for n in nested)]
        code = [s for s in sources if s.rel in own]
        libs = Counter(library_name(i) for s in code for i in s.imports)
        local = {PurePosixPath(p).stem for p in all_paths if p.endswith(".py")}
        third = sorted(l for l in libs if l.split(".")[0] not in STDLIB and l.split(".")[0] not in local)
        last = git(repo, "log", "-1", "--format=%aI", "--", d).strip()
        first = git(repo, "log", "--reverse", "--format=%aI", "--", d).splitlines()
        o = overrides.get(d, {})
        out.append({
            "path": d,
            "title": o.get("title") or humanize(PurePosixPath(d).name),
            "description": o.get("description", ""),
            "files": len([p for p in own if PurePosixPath(p).suffix in CODE_EXT]),
            "loc": sum(s.loc for s in code),
            "libraries": third,
            "first": first[0][:10] if first else "",
            "last": last[:10],
        })
    return out


# ---------------------------------------------------------------- main


def collect(repo, curriculum_path, today=None):
    repo = Path(repo).resolve()
    cur = yaml.safe_load(Path(curriculum_path).read_text())
    today = today or dt.date.today()
    all_paths = [p for p in git(repo, "ls-files").splitlines() if p]
    files = [RepoFile(repo, p) for p in all_paths if (repo / p).is_file()]
    sources = [f for f in files if f.kind == "code"]

    commit_list = commits(repo)
    days = [c["day"] for c in commit_list]
    first_day = min(days) if days else today.isoformat()
    start = dt.date.fromisoformat(cur["program"].get("start_date") or first_day)
    total_weeks = cur["program"].get("months", 6) * 26 // 6
    week_now = max(1, min(total_weeks, (today - start).days // 7 + 1))
    # The repo can be ahead of the calendar (e.g. when start_date is the first commit, not the program start):
    # never show an earlier week than the highest week_NN folder in the repo.
    folder_weeks = [int(w) for p in all_paths for w in re.findall(r"(?:^|/)week[_-]?(\d+)(?=/)", p)]
    week_now = max(week_now, min(total_weeks, max(folder_weeks, default=0)))

    modules = []
    for m in cur["modules"]:
        topics = []
        for t in m["topics"]:
            ev = evaluate(t.get("evidence"), files) if t.get("evidence") else []
            topics.append({"name": t["name"], "trackable": bool(t.get("evidence")), "evidence": ev,
                           "in_code": any(e["kind"] == "code" for e in ev)})
        proj = m.get("project") or {}
        proj_ev = evaluate(proj.get("evidence"), sources) if proj.get("evidence") else []
        trackable = [t for t in topics if t["trackable"]]
        covered = [t for t in trackable if t["evidence"]]
        ratio = len(covered) / len(trackable) if trackable else 0
        if not covered and not proj_ev:
            status = "not_started"
        elif proj_ev and ratio >= 0.6:
            status = "completed"
        else:
            status = "in_progress"
        modules.append({
            "id": m["id"], "title": m["title"], "schedule": m["schedule"], "weeks": m["weeks"],
            "topics": topics, "covered": len(covered), "trackable": len(trackable),
            "project": {"name": proj.get("name", ""), "trackable": bool(proj.get("evidence")), "evidence": proj_ev},
            "status": status, "scheduled_now": week_now in m["weeks"],
        })

    lib_counter = Counter()
    local = {PurePosixPath(p).stem for p in all_paths if p.endswith(".py")}
    for s in sources:
        for name in {library_name(i) for i in s.imports}:
            if name.split(".")[0] not in STDLIB and name.split(".")[0] not in local:
                lib_counter[name] += 1

    per_day = Counter(days)
    current_streak, longest_streak = streaks(days, today)
    ext = Counter(PurePosixPath(p).suffix or PurePosixPath(p).name for p in all_paths)
    kinds = Counter(f.kind for f in files)
    notes = sorted((f for f in files if f.kind == "notes"), key=lambda f: f.rel)
    week_of = lambda rel: next((int(w) for w in re.findall(r"(?:^|/)week[_-]?(\d+)(?=/)", rel)), None)
    practice = sorted((PurePosixPath(p).stem for p in all_paths if "_practice" in PurePosixPath(p).stem and p.endswith(".py")),
                      key=lambda n: int(m.group()) if (m := re.match(r"\d+", n)) else 0)
    all_topics = [t for m in modules for t in m["topics"]]
    head = git(repo, "rev-parse", "HEAD").strip() if commit_list else ""

    return {
        "program": {**cur["program"], "start_date": start.isoformat(), "total_weeks": total_weeks,
                    "week_now": week_now, "today": today.isoformat()},
        "modules": modules,
        "totals": {
            "topics_covered": sum(m["covered"] for m in modules),
            "topics_trackable": sum(m["trackable"] for m in modules),
            "topics_in_code": sum(t["in_code"] for t in all_topics),
            "topics_from_notes": sum(bool(t["evidence"]) and not t["in_code"] for t in all_topics),
            "modules_started": sum(m["status"] != "not_started" for m in modules),
            "modules_completed": sum(m["status"] == "completed" for m in modules),
            "projects_built": sum(bool(m["project"]["evidence"]) for m in modules),
            "modules": len(modules),
        },
        "stats": {
            "commits": len(commit_list),
            "active_days": len(per_day),
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "python_files": ext.get(".py", 0),
            "notebooks": ext.get(".ipynb", 0),
            "lines_of_code": sum(s.loc for s in sources),
            "practice_assignments": sum(1 for p in all_paths if "_practice" in PurePosixPath(p).stem),
            "lecture_notes": len(notes),
            "notes_words": sum(f.words for f in notes),
            "files": len(files),
            "files_by_kind": dict(kinds.most_common()),
            "first_commit": first_day,
            "last_commit": max(days) if days else "",
        },
        "activity": dict(sorted(per_day.items())),
        "commits": commit_list[:10],
        "projects": projects(repo, all_paths, sources, cur.get("projects", {})),
        "notes": [{"path": f.rel, "week": week_of(f.rel), "words": f.words,
                   "title": f.headings[0][1] if f.headings else PurePosixPath(f.rel).stem} for f in notes],
        "practice": practice,
        "libraries": lib_counter.most_common(),
        "head": head,
    }


if __name__ == "__main__":
    data = collect(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else Path(__file__).parent.parent / "curriculum.yaml")
    json.dump(data, sys.stdout, indent=1, ensure_ascii=False)
