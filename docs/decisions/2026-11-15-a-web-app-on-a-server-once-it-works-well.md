# BrickSnap will be a web app backed by a server, once the engine works well
- status: accepted
- by: Alec-42, 2026-11-15

Making something that works well comes first, and the command line is fine while we do. But the people this
is for do not use a terminal, so it will get a web interface: upload a model, see the plain conversion next
to the designed build, type a change, download the files. The work that cannot happen in a browser (the
solver, the passes, the AI designer) runs on a server, which is acceptable. The first version of that server
runs on your own computer, where everything stays private as it does today; a hosted copy for the group
comes after, and says plainly that models uploaded to it leave your computer.

The engine stays a library with no knowledge of the web: the command line and the web app are two front
ends over the same pipeline. Rejected: going back to a single page that does everything in the browser (the
solver and the mesh libraries are Python, and the AI designer cannot run there).

## Responses
