# IIT Patna GenAI program: progress dashboard

A public dashboard of my progress in IIT Patna's **Certificate Program in Generative AI & Agentic AI for Developers**, rebuilt automatically from my course code.

**Live dashboard:** https://jayanthappalla.com/iit-patna-progress-dashboard/

**Course code:** [astroboy1183/iit-patna-certification-course](https://github.com/astroboy1183/iit-patna-certification-course)

## What it shows

- **Curriculum roadmap:** the program's 10 modules and capstone, from the brochure. Each hands-on topic is ticked when my code shows it (for example, `import streamlit` ticks "Simple UI with Streamlit or Gradio") and links to the file that proves it. Concept-only topics are listed but not scored.
- **Progress:** hands-on topics covered, modules started, module projects built, and where I am on the program's 26-week timeline.
- **Activity:** commits per day as a heatmap, streaks, recent commits.
- **Projects and libraries:** every folder with its own `requirements.txt`, and the third-party libraries used across my code.

## How it updates

1. I push to the course repo.
2. A small workflow there ([`notify-dashboard.yml`](https://github.com/astroboy1183/iit-patna-certification-course/blob/main/.github/workflows/notify-dashboard.yml)) sends a `course-updated` event to this repo.
3. [`deploy.yml`](.github/workflows/deploy.yml) checks out both repos, runs the tests, rebuilds the page and publishes it to GitHub Pages.

An hourly scheduled run is a fallback, so the page stays current even if the event isn't sent.

## How progress is detected

[`curriculum.yaml`](curriculum.yaml) maps each topic to evidence rules:

| Rule | Matches when |
|---|---|
| `imports` | a Python file or notebook imports one of the modules (`langchain` also matches `langchain_core`, `langchain_openai`, …) |
| `patterns` | a regex matches in a Python file or notebook code cell |
| `paths` | a tracked file path matches a glob (`*` stays in one folder, `**` crosses folders) |
| `providers` | one file imports at least N of the listed modules (for "compare providers" topics) |
| `count` | one file matches a regex at least N times |
| `same_file` | all of the listed rules match within the same file |

A module is **Hands-on done** when its project is detected and at least 60% of its trackable topics are covered; **In progress** when anything is detected.

The program start date defaults to the first commit in the course repo; set `program.start_date` in `curriculum.yaml` to change it.

## Run it locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests
.venv/bin/python dashboard/build.py --course ../iit-patna --out site
python3 -m http.server -d site 8000   # open http://localhost:8000
```
