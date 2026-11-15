# A build that fails still lets you press Next and Download
- status: open
- owner: nobody

When `build()` gives up early ("That is a very big build" or "No bricks fit", `index.html` around lines 425
and 515) it returns before setting `pages` and `stl`, but Next and Download stay enabled. Next then throws in
`showPage` (`steps[undefined].list`) and leaves a broken Manual screen. Download saves either the previous
model's kit under the new name or, on a first build, a file containing the word "undefined".

Two related cases of the app showing an old result:

- Build at Medium, then click Small and hit the size limit: Small is highlighted but the booklet and the
  download are still the Medium kit.
- In photo mode, changing a photo, an outline, or the ruler does not clear the old booklet. Jumping straight
  to Manual from the progress bar shows and downloads the previous object's kit.

The root cause is that there is no single "the build is out of date" path.

To reproduce the crash: upload `sample-models/pawn.stl`, set Real height to 600 mm, go to Build, press Next or Download.

Done when a failed build clears the old result (bricks, steps, pages, STL, 3D preview) and Next and Download
are disabled until a build succeeds, and any change to the inputs marks the build out of date.

## Notes
Found in the 2026-11-15 code review.
