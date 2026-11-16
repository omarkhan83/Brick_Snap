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

2026-11-15, Alec-42's agent: checked on Linux with LeoCAD 26.09, an independent free program that reads
the same file format with the real part shapes. The pawn (bricks and plates), the designed cat (tiles),
and a designed duck (97 slopes) all load without error and look like our own pictures: every part in
place, the right colours, slopes facing the right way, nothing floating. LeoCAD also reads our building
steps (the cat builds up over 34 steps). This does not replace the Studio check: Studio has its own
importer, its own step handling, and its own collision and stability checks, and BrickLink Studio was not
installed on the machine used. A LeoCAD check that runs with the tests would be worth adding:
`leocad FILE.ldr -i out.png` works without a screen under `xvfb-run`.

2026-11-16, Alec-42's agent: BrickLink Studio 2.26.10 is now installed on Alec's Windows computer (in
`C:\Users\AlecR\BrickSnap`, with the three test files and a checklist beside it). Checked against the
data files Studio ships, without opening the program: all 40 of our colours have the same BrickLink colour
number as in Studio's own table; all 50 of our part files exist in Studio's parts library; and for 49 of
our 50 parts Studio pairs the same file with the same BrickLink part number. The exception is the inverted
slope: we call its file `3665b.dat`, Studio's table knows only `3665.dat`. We do not place that part yet;
before we do, write it as `3665.dat`. Still to do by a person: open the three files in Studio and answer
the four questions above.
