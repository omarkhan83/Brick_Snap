# Open one of our LDraw files in BrickLink Studio and report what happens
- status: open
- owner: nobody
- stage: 1

Needs a person with Windows or a Mac; Studio does not run on Linux. Install BrickLink Studio (free), open
`samples/projects/pawn/build.ldr` (bricks and plates only) and `samples/projects/cat-designed/build.ldr`
(with tiles; the picture next to each is in its `renders/` folder), and answer for each:

1. Does it open without errors, and does it look like the picture next to it?
2. Are the building steps kept (Studio's step list), or is it all one step?
3. Does Studio's connectivity check or stability check complain? Screenshot if so.
4. Does "Add to Wanted List" accept every part and colour?

Done when the answers are written under Notes, with screenshots added to the same folder as the file.

## Notes
Both sample files are in place, so this can start now. Whether steps survive import is not documented by
Studio, so this is the only way to find out. For a build with slopes, make one yourself:
`uv run bricksnap new samples/models/duck.glb --studs 16` writes `projects/duck/build.ldr`. Check that
each slope faces the way the picture shows.

Also worth doing in the same sitting, with a BrickLink account: upload
`samples/projects/cat-designed/wanted_list.xml` on BrickLink's wanted-list page (Wanted, then Upload) and
note whether any item is rejected. Uploading buys nothing.
