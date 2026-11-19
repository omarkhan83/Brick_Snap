"""The free-build lab: an AI builds a model itself from the whole LDraw parts library.

RESEARCH PROTOTYPE on branch wip/Alec-42-free-build; not part of the BrickSnap engine and
not meant for main as it is. It answers one question: what can an AI do when it chooses any
part (leaves, wings, wheels, clips...) and places it by coordinates, if it can find parts,
submit a model and be told exactly what is wrong, and see pictures of what it built?

Modules
- ``ldraw_lib``: read parts straight from the LDraw library zip: triangles, description,
  category, keywords, studs and other connectors as far as the geometry says, and a rough
  filled-body model used by the checks. Parsed parts are cached under
  ``~/.cache/bricksnap/lab/``.
- ``search``: an index over the official, current, plain parts and a word-overlap search.
- ``validate``: check a model written as LDraw text and report what is wrong in plain words.
- ``picture``: pictures made with LeoCAD (an independent LDraw program) without a screen.
- ``place``: place a part by connection ("put its socket on stud k of line n") instead of
  by coordinates.
- ``tools`` / ``mcp_server``: the tools the AI gets, served over MCP.
- ``run`` / ``blind``: one clean-room session through ``bricksnap.designer.runner.run_session``,
  with the tools, or with nothing but a final submit.

Nothing here changes the rest of BrickSnap.
"""
