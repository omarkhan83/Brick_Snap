# The design brief: the AI decides what matters before it edits
- status: in-progress
- owner: Alec-42 (since 2026-11-15)
- stage: 2

Before editing, the designer looks at the seed and writes a short brief saved in `project.json`: what the
object is, the two or three features that make it recognisable, what to exaggerate at this size, and a
palette of real colours. The edits that follow are judged against the brief.

Done when a run on the cat produces a brief a person agrees with, and the edits that follow match it.

## Notes
A fifth designer tool, `brief`, specified in `bricksnap/designer/tools.py`.
