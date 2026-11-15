# The seven library scripts load from CDNs with no integrity check
- status: open
- owner: nobody

`index.html` lines 106-112 load three.js r128 and its loaders from cdnjs and jsDelivr. The versions are pinned,
but there are no `integrity` hashes, so a compromised or altered CDN file would run with full access to the
page. The app also cannot run offline.

Two ways to fix it:

1. Add `integrity="sha384-..."` and `crossorigin="anonymous"` to each tag. Small, no new files.
2. Copy the seven files into a `vendor/` folder and load them from there. Also makes the app work offline,
   but adds about 1 MB to the repository, so it needs a proposal first.

Done when the scripts cannot change underneath us.

## Notes
Found in the 2026-11-15 code review. Google Fonts (lines 4-5) is also external; it only affects appearance.
