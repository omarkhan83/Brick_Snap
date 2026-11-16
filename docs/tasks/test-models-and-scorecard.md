# Six test models and a scorecard
- status: in-progress
- owner: Alec-42 (since 2026-11-15)
- stage: 2

A fixed set of seeds (cat, another animal, hat, car, long thin object, mug) in `samples/models/` with each
licence recorded, and a command that builds all of them and prints one row each: valid or not, loose parts
(must be 0), part count, distinct part types, how closely the silhouette matches the seed from each side.
This is how we tell whether a change made things better.

Done when `uv run bricksnap bench` prints the table and saves pictures for every model.

## Notes
Eleven CC0 models are in `samples/models/` with their licences. The contract is the opening comment of
`bricksnap/bench.py`. Anyone may still add candidate models and their source links below.
