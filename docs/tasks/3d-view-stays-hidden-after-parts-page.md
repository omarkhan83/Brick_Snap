# After the Parts page, the 3D view disappears and printed pages come out blank
- status: open
- owner: nobody

`showPage` hides the 3D view on the Parts page (`index.html` line 605) and that is the only line that ever
shows it again. Pressing Back from the Parts page leaves the Build step with no 3D preview. Going forward
again resizes the renderer while it is hidden (width 0), so every booklet page, and every image in Print,
is blank until the window is resized.

To reproduce: build any model, go to Manual, page to Parts, press Back.

Done when leaving the Parts page by any route shows and correctly sizes the 3D view.

## Notes
Found in the 2026-11-15 code review.
