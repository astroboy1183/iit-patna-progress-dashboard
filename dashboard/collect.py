"""Read the course repo and work out progress: curriculum evidence, activity, projects and libraries.

Everything here is derived from the repo's tracked files and git history, so the dashboard
changes only when the code does.
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
STDLIB = set(sys.stdlib_module_names)


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


# ---------------------------------------------------------------- reading code


def notebook_code(path):
    """Code cells of a notebook joined into one string (magics and shell lines removed)."""
    try:
        nb = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ""
    cells = []
    for c in nb.get("cells", []):
        if c.get("cell_type") != "code":
            continue
        src = c.get("source", "")
        src = "".join(src) if isinstance(src, list) else src
        cells.append("\n".join(l for l in src.splitlines() if not l.lstrip().startswith(("%", "!"))))
    return "\n\n".join(cells)


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


class SourceFile:
    def __init__(self, repo, rel):
        self.rel = rel
        p = repo / rel
        self.code = notebook_code(p) if rel.endswith(".ipynb") else p.read_text(encoding="utf-8", errors="replace")
        self.imports = imports_of(self.code)
        self.loc = sum(1 for l in self.code.splitlines() if l.strip() and not l.strip().startswith("#"))

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


def rule_hits(rule, files, all_paths):
    """Return a list of (path, line) evidence for one rule. Empty list = no match."""
    if "paths" in rule:
        return [(p, None) for p in all_paths if path_match(p, rule["paths"])]
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


def evaluate(evidence, files, all_paths):
    seen, out = set(), []
    for rule in evidence or []:
        for path, line in rule_hits(rule, files, all_paths):
            if path not in seen:
                seen.add(path)
                out.append({"path": path, "line": line})
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


def projects(repo, all_paths, sources, commit_list, overrides):
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
    sources = [SourceFile(repo, p) for p in all_paths if PurePosixPath(p).suffix in CODE_EXT and (repo / p).exists()]

    commit_list = commits(repo)
    days = [c["day"] for c in commit_list]
    first_day = min(days) if days else today.isoformat()
    start = dt.date.fromisoformat(cur["program"].get("start_date") or first_day)
    total_weeks = cur["program"].get("months", 6) * 26 // 6
    week_now = max(1, min(total_weeks, (today - start).days // 7 + 1))

    modules = []
    for m in cur["modules"]:
        topics = []
        for t in m["topics"]:
            ev = evaluate(t.get("evidence"), sources, all_paths) if t.get("evidence") else None
            topics.append({"name": t["name"], "trackable": bool(t.get("evidence")), "evidence": ev or []})
        proj = m.get("project") or {}
        proj_ev = evaluate(proj.get("evidence"), sources, all_paths) if proj.get("evidence") else []
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
    head = git(repo, "rev-parse", "HEAD").strip() if commit_list else ""

    return {
        "program": {**cur["program"], "start_date": start.isoformat(), "total_weeks": total_weeks,
                    "week_now": week_now, "today": today.isoformat()},
        "modules": modules,
        "totals": {
            "topics_covered": sum(m["covered"] for m in modules),
            "topics_trackable": sum(m["trackable"] for m in modules),
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
            "first_commit": first_day,
            "last_commit": max(days) if days else "",
        },
        "activity": dict(sorted(per_day.items())),
        "commits": commit_list[:10],
        "projects": projects(repo, all_paths, sources, commit_list, cur.get("projects", {})),
        "libraries": lib_counter.most_common(),
        "head": head,
    }


if __name__ == "__main__":
    data = collect(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else Path(__file__).parent.parent / "curriculum.yaml")
    json.dump(data, sys.stdout, indent=1, ensure_ascii=False)
