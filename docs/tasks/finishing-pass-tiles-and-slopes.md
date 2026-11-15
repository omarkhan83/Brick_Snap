# Finishing pass: tiles on smooth tops, slopes on steps
- status: open
- owner: nobody
- stage: 2

After the solver has placed bricks and plates, swap parts that have nothing above them for better-looking
ones: tiles where the Design's finish is smooth, 45-degree slopes where the surface steps down by a brick,
cheese slopes where it steps down by a plate. Each swap must leave every check passing, or be undone.
See "Finish" in `docs/ARCHITECTURE.md`. Lives in `bricksnap/finish.py`.

Done when a sphere and a pitched roof shape visibly lose their staircase in the pictures, every build still
passes its checks, and only part and colour pairs from the parts table are used.

## Notes
Starts after `stage-1-foundation`.
