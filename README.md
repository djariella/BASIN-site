# BASIN: the public pilot page

This repository holds one web page and one data file. Together they are the public face of the BASIN pilot: signals of change from across the Murray-Darling Basin, gathered from public sources and checked by a person.

**Everything here is public.** The scan, the source register and the working documents live in a separate private repository.

## What is here

| File | What it is |
|---|---|
| `index.html` | The page. One self-contained file with no outside code. |
| `data/signals.json` | The approved signals the page shows. Refreshed from the database every hour. |
| `scripts/export_signals.py` | Reads approved signals from the database and writes the data file. |
| `.github/workflows/update-signals.yml` | Runs the export every hour and saves the file if it changed. |

## How it stays current

1. Overnight, the scan in the private repository adds new signals to the BASIN database, marked for review.
2. A person approves or rejects each one in the database.
3. Every hour, the export here copies the approved signals into `data/signals.json`.
4. The page reads that file.

The page never talks to the database and holds no key. That is deliberate: anything on a public page can be read by anyone.

## The one secret

The export needs `NOCODB_TOKEN`, saved under Settings, Secrets and variables, Actions. It is never written into a file.

## Rules

- No password, key or token is ever committed here.
- The page shows every piece of text as plain text, never as HTML.
- Only approved signals are exported: a headline, a link, dates, tags and our own short summary.
