# File names and the model name are put into the page as HTML
- status: open
- owner: nobody

Three places build HTML strings from text the app does not control and assign them with `innerHTML`:

- `loadModel` `fail()` (around line 300): the file name, its extension, and the loader's error message.
- `showPage` cover (around line 601): the Name box, which also flows into the print view (line 615).

A file named `x.<img src=x onerror=alert(1)>` runs script when dropped on the page. Today the impact is small
(nothing is stored and there is no login), but it becomes a real hole the moment the app is hosted somewhere
or gains saved data. Done when these use `textContent` or an escape helper, per the rule in `AGENTS.md`.

## Notes
Found in the 2026-11-15 code review.
