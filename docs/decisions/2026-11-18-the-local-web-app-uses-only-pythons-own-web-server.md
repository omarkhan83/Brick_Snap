# The web app that runs on your own computer uses only Python's own web server
- status: accepted
- by: Alec-42, 2026-11-18

The first web app is for one person on their own machine. Uploads, a few long-running jobs with progress
the page asks for every second, and file downloads are all within reach of Python's standard library,
which the viewer's server already uses with its safety checks written and tested. So no web framework is
added for it: `uv sync` stays as light as it is, and there is one fewer thing to keep up to date. The
actions are written as plain functions behind the request handler, so a hosted copy can put them behind a
proper framework later; that will need its own decision, along with accounts and running the AI designer
on the API.

## Responses
