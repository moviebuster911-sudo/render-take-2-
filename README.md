# WhatsApp Chat Viewer Web App

This is a Flask web app that converts a WhatsApp-exported .txt file into a visually similar, searchable HTML chat mimicking WhatsApp UI.

## Features

- Upload .txt chat export and optional media zip.
- Displays chat in WhatsApp-like bubbles with avatars, timestamps, and authors.
- Supports images, videos, and file attachments (displays/links them).
- Phone-like UI mockup for authentic feel.
- Sent messages (green, right-aligned) vs received (white, left-aligned) based on your name.
- Dark mode for WhatsApp dark theme.
- Long-press (hold 1 second) on messages to view full date/time info.
- Feels like reading old chats with scroll and layout.
- Print to PDF directly from browser for exact WhatsApp lookalike.

## Setup

This repository now includes a static GitHub Pages version in `index.html`, `styles.css`, and `script.js`.

### Static site

1. Open `index.html` in any browser.
2. Upload your exported WhatsApp `.txt` file or paste the exported text.
3. Select your identity and view the chat in WhatsApp style.
4. This version works on GitHub Pages because it does not require a Python backend.

## Notes on hosting

This repository contains two ways to use the project:

- A static client-side viewer (recommended for GitHub Pages): `index.html`, `styles.css`, `script.js`. This version parses chat files entirely in the browser and can be published to GitHub Pages (branch `main`, root). GitHub Pages will serve `index.html` directly.

- A Flask backend (optional): `app.py` and server files. Use this if you need server-side Google Drive downloads or media extraction. This must be deployed to a Python host (Render, Railway, etc.) — GitHub Pages cannot run `app.py`.

Important Google Drive note:
- Browsers block cross-origin requests to private Google Drive files. On GitHub Pages the static viewer will attempt a client-side download only for files that are publicly shared ("Anyone with the link"). Private Drive files require a server-side fetch (deploy the Flask app or a small proxy) to avoid CORS and permission errors.

If you want help deploying either:
- I can guide you to publish the static files to GitHub Pages.
- Or I can help deploy the Flask backend to Render and wire the static site to that backend for Drive downloads.

## Render deployment

This repo now includes `render.yaml` for Render to detect the build and start commands automatically. If you use Render, it will run:
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app --bind 0.0.0.0:$PORT`
