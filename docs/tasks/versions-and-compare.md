# Keep every version of a model, and compare any two side by side
- status: in-progress
- owner: Alec-42 (since 2026-11-19)
- stage: 4

A model changes in steps: the plain conversion, an AI design, each pass, each typed change. Today only the
latest survives. Keep each as a numbered version, show them in the web app, let a person choose which two
the 3D view puts side by side, and let them go back to one they liked better.

Done when, in the web app, a model that has been designed and then changed shows its versions; any two
can be chosen for the two 3D views; "use this version" brings one back with its downloads; and the
command line can list and restore versions too.

## Notes
2026-11-19, Alec-42's agent: `bricksnap/versions.py` keeps, lists and restores versions (its opening
comment is the contract; tests in `tests/test_versions.py`). Nothing calls it yet. Left: the web app and
command line record a version after every job that changes the model; the viewer gets the two choosers
and a "look inside" control (a cut through the model); the page gets "use this version".
