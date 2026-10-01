# State of Search Reveal.js deck

The deck follows `01_talk-outline.md`, `02_demo-plan.md`, and
`03_talk-track.md`. Speaker notes contain the detailed talk track, demo
commands, recovery cues, and source links. The main sequence also connects the
retrieval comparison to a companion Reflex on-call command center. That
companion application is not included in this repository.

## Run locally

From the `State-of-Search` repository directory:

```bash
nvm use # optional; reads the included .nvmrc when nvm is installed
npm install
npm run dev
```

Node.js 20.19.x, or 22.12 and newer, is required; Node 22 is recommended. The
repository is an npm workspace, so the root command installs and starts this
deck.

Open the local URL printed by Vite. Press `S` for speaker view and `Esc` for
the slide overview.

## Build

```bash
npm run build
```

The static site is written to `dist/`.

## Export to PDF

Start the deck, append `?print-pdf` to the URL, and print from Chrome with
landscape layout, no margins, and background graphics enabled.

## Presenter shortcuts

- `S`: speaker view with notes, next-slide preview, and timer
- `B` or `.`: blank the screen during a demo
- `Esc`: overview mode
- Arrow keys or Space: navigate

Brand assets and fonts in `assets/` come from Tiger Data's public brand page.
