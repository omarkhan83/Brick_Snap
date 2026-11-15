# The engine is a Python package with tests; the single static page becomes the legacy prototype
- status: accepted
- by: Alec-42, 2026-11-15

Supersedes the "one static page, no build step" decision. The vision needs a core that runs without a
browser (so it can be tested and driven by the AI's tools), real part data, and mesh and numeric libraries.
Those libraries and all the reusable research code are Python, and `uv` installs everything with one
command on Windows, WSL, and macOS. The web page becomes a build-free viewer over project folders.

The prototype moves to `legacy/`, keeps opening by double-click, and is not developed further.

Rejected: TypeScript everywhere (one language and runs in the browser, but every piece of part handling
would have to be written from scratch). Depending on the BrickLayer toolkit now (it is a few weeks old and
pulls in an 83 MB package and a collision library; revisit for detail sub-assemblies later).

## Responses
