# concours (command line)

Everything the web app does, from a terminal: create a project, upload and map transactions, answer the three
questions, protect, read today's review queue, record verdicts, run improvement rounds with their gates, check
drift, and package for Apex. Python 3.10+, no dependencies.

```bash
pipx install ./cli            # or: uv tool install ./cli   (or run python3 cli/concours_cli.py directly)
concours login --url https://fraud.example.com/api --email you@company.com
concours new --name "Card fraud" --file payments.csv
concours map                   # shows the suggested mapping; --set amount=AMT to change a field; --yes to skip the prompt
concours settings --capacity 200 --review-cost 10 --fee 0 --delay 30
concours protect               # waits for version 1
concours status
concours queue --top 20        # or --csv today.csv
concours label 1474722 fraud   # fraud | not-fraud | clear
concours improve               # follows the round live, then shows each attempt's gates
concours versions
concours drift --check
concours jump --days 28        # sample data: move the simulated clock
concours package --out handoff.zip
```

Local server: `concours login --url http://127.0.0.1:8000`. With an API key from Account in the web app:
`concours login --url ... --api-key ck_...`. Scripts and CI: set `CONCOURS_URL`, `CONCOURS_API_KEY` and
`CONCOURS_PROJECT` instead of logging in. `--json` gives machine output on most commands.

The key is stored in `~/.config/concours/config.json` with mode 600; `concours logout` revokes it.
