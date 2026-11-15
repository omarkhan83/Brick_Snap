# Split index.html into a few script files so people stop colliding, and test the core logic
- status: open
- owner: nobody

Everything is one 49 KB file with 200-character lines, and `build()` is a single 180-line function that mixes
page updates, geometry, brick layout, and STL export. Nearly any two people working at the same time will
touch the same lines, and none of the logic can be tested. This is the biggest obstacle to working in
parallel. **It moves files, so it needs a proposal before anyone starts**, and it should be done in one
sitting while nobody else has work in progress.

Suggested split, using plain `<script src>` files (not ES modules, which do not load from a double-clicked
file): `styles.css`; `imaging.js` (otsu, seg, autoBox, mask; already pure); `model-io.js`; `palette.js`;
`bricks.js` (carve, colours, hollow, merge, join, pillars as pure functions); `stl.js`; `scene3d.js`;
`booklet.js`; `app.js` (state, screens, event wiring, the final `render()` call).

Traps:

- Plain scripts share one scope. The same top-level `let` or `const` in two files is a syntax error; watch
  `pos`, `key`, `dist`, `tris`, `stage`. `tris` and `dist` are also local names inside `build()`.
- Load order matters: `app.js` last, since it calls `render()`.
- `build()` should become pure stages that return values plus one function that commits the result to the
  page. That also fixes the stale-state bugs in `failed-build-crashes-next-and-download.md`.
- `tools/check.mjs` must be updated to check the new files.

Done when the app behaves identically, the pure parts have node tests that `tools/check.mjs` runs, and
`AGENTS.md` describes the new layout.

## Notes
Suggested by the 2026-11-15 code review.
