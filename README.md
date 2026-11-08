# Campus Index — final website

`dist/` contains the public browser demo. Audit history is in the Workspace menu. The browser adapter runs the Python engine and offline coach with Pyodide. Prices are synthetic. Paper state stays in each visitor's browser tab. Loading the engine requires internet access to jsDelivr. AI remains disconnected.

`backend/` contains the complete Python server project, including server-side Claude and ASI:One integration for later configuration. Read `backend/README.md` for setup. Never put an API key in `dist/`.

## Publish through GitHub

Extract the ZIP, then push this folder's contents to a GitHub repository with a `main` branch. Include `.github/workflows/pages.yml`. In the repository's Settings → Pages, choose GitHub Actions as the source. Run the Publish website workflow or push a commit. The workflow publishes `dist/` and reports the public URL. This works at both a repository subpath and a custom domain.

## Run locally

From this folder run `python3 -m http.server 8080 --directory dist`, then open http://localhost:8080. For the Python server run `python3 backend/server.py --open`.
