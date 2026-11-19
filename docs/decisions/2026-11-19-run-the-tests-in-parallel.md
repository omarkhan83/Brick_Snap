# Run the tests in parallel, with the pytest-xdist plugin
- status: proposed
- by: Alec-42, 2026-11-19

Proposed by Alec's agent. The everyday test run was brought down to four minutes on 18 November; one
night's work (versions, the studio, inverted slopes, the web app's new pages) added about three hundred
tests and it is back to six or more. Marking more tests "thorough" works once but not for long, and every
agent runs the suite before every push. `pytest-xdist` is the standard plugin for running test files side
by side; with four at a time the run would take about two minutes. It is a development dependency only:
nothing a user of BrickSnap installs. Rejected: trimming alone (it has to be redone every week); leaving it
(a slow suite stops being run).

## Responses
