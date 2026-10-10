# IIT Patna GenAI program: progress dashboard

A public dashboard of my progress in IIT Patna's **Certificate Program in Generative AI & Agentic AI for Developers**, rebuilt automatically from my course code.

**Live dashboard:** https://jayanthappalla.com/iit-patna-progress-dashboard/

**Course code:** [astroboy1183/iit-patna-certification-course](https://github.com/astroboy1183/iit-patna-certification-course)

## What it shows

- **Curriculum roadmap:** the program's 10 modules and capstone, from the brochure. The whole course repo is read: a topic is ticked when my code uses it (for example, `import streamlit` ticks "Simple UI with Streamlit or Gradio") or, for theory topics, when my lecture notes cover it, and every tick links to the file and line that proves it. Click a module on the timeline or stepper for a pop-up with its details.
- **Progress:** topics covered, modules started, module projects built, lecture notes, and where I am on the program's 26-week timeline. The stat cards flip over for a breakdown.
- **Activity:** commits per day as a heatmap, streaks, recent commits.
- **Projects and libraries:** every folder with its own `requirements.txt`, and the third-party libraries used across my code.

## How it updates

1. I push to the course repo.
2. A small workflow there ([`notify-dashboard.yml`](https://github.com/astroboy1183/iit-patna-certification-course/blob/main/.github/workflows/notify-dashboard.yml)) sends a `course-updated` event to this repo.
3. [`deploy.yml`](.github/workflows/deploy.yml) checks out both repos, runs the tests, rebuilds the page and publishes it to GitHub Pages.

An hourly scheduled run is a fallback, so the page stays current even if the event isn't sent.

## How progress is detected

Every tracked file in the course repo is read and given a kind: code (`.py` files and notebook code cells), notes (markdown in a `notes/` folder), docs (other markdown and notebook markdown cells), dependencies, config and data. [`curriculum.yaml`](curriculum.yaml) maps each topic to evidence rules:

| Rule | Matches when |
|---|---|
| `imports` | a Python file or notebook imports one of the modules (`langchain` also matches `langchain_core`, `langchain_openai`, …) |
| `patterns` | a regex matches in a Python file or notebook code cell |
| `paths` | a tracked file path matches a glob (`*` stays in one folder, `**` crosses folders) |
| `providers` | one file imports at least N of the listed modules (for "compare providers" topics) |
| `count` | one file matches a regex at least N times |
| `same_file` | all of the listed rules match within the same file |
| `headings` | a markdown heading in lecture notes, docs, READMEs or notebook markdown cells matches a regex |

Code rules only look at code, so prose that mentions a library never counts as using it, and `headings` only looks at headings, not body text (the roadmap lecture mentions most of the curriculum in passing). Evidence from code is listed before notes, and notes before other docs.

A module is **Hands-on done** when its project is detected and at least 60% of its trackable topics are covered; **In progress** when anything is detected.

The program start date defaults to the first commit in the course repo; set `program.start_date` in `curriculum.yaml` to change it. The current week is never earlier than the highest `week_NN` folder in the repo.

## Look and feel

Three colour themes (Aurora, Sunset, Ocean), each with light and dark variants, plus ambient light, a starfield hero, flip cards, pop-ups and scroll-in animations. The buttons in the bottom-left corner switch the colour theme, light/dark mode and animations. Animations follow the system's reduced-motion setting unless switched on, and only start once the browser is shown to run them, so the page is always readable without them.

## Run it locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests
.venv/bin/python dashboard/build.py --course ../iit-patna --out site
python3 -m http.server -d site 8000   # open http://localhost:8000
```
