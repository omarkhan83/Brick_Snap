# Six test models and a scorecard
- status: open
- owner: nobody
- stage: 2

A fixed set of seeds (cat, another animal, hat, car, long thin object, mug) in `samples/models/` with each
licence recorded, and a command that builds all of them and prints one row each: valid or not, loose parts
(must be 0), part count, distinct part types, how closely the silhouette matches the seed from each side.
This is how we tell whether a change made things better.

Done when `uv run bricksnap bench` prints the table and saves pictures for every model.

## Notes
Collecting more openly licensed models (CC0 or CC BY only, licence written down) needs no code and can
start now: put candidates and their source links in this file's Notes.
