Minneapolis & St. Paul Meetings — ICS generator

What this project does
- Reads a CSV of meetings (see `data/meetings.csv`) and generates an ICS file
- Attempts to infer recurrence rules from the `Cadence` column
- Writes output to `public/minneapolis_stpaul_meetings.ics` suitable for hosting or subscribing
- Includes a GitHub Actions workflow to build daily and publish `public/` to `gh-pages`

Quick start (local)
1. Put your CSV at `data/meetings.csv` (keep headers from your file; the script reads `Agency`, `Cadence`, `Calendar link`, `Agenda link`, `Notes` etc.)
2. Create a virtualenv and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

3. Run the generator:

```bash
python generate_calendar.py --input data/meetings.csv --output public/minneapolis_stpaul_meetings.ics
```

Hosting on GitHub Pages (recommended for automatic public ICS URL)
1. Create a repository and push this project
2. Enable GitHub Pages to serve from the `gh-pages` branch (or the workflow will publish to `gh-pages` automatically)
3. The generated ICS will be available at `https://<your-username>.github.io/<repo-name>/minneapolis_stpaul_meetings.ics`

Automatic updates via Actions
- A workflow is included in `.github/workflows/generate.yml` that runs daily (UTC) and on-demand.
- The workflow installs deps, runs the generator, and deploys `public/` to `gh-pages` using the built-in `GITHUB_TOKEN`.

Notes & caveats
- The cadence parser uses heuristics and may not be perfect. Please check several events after the first run.
- For full Google Calendar integration (Option B), the next step is a script that uses the Google Calendar API.

If you want, I can:
- Tweak recurrence parsing to match special phrasing in your CSV
- Prepare a PR-ready repo and push it to GitHub for you to enable Pages
- Add an optional small web page that embeds the calendar
