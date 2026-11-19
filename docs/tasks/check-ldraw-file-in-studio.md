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

2026-11-16, Alec-42: opened the designed cat (`samples/projects/cat-designed/build.ldr`, with tiles) in
BrickLink Studio 2.26.10 on Windows. Answers so far:

1. It opens without errors and looks like our picture. Alec: "The cat works well."
2. The building steps are kept: Studio's instruction maker shows 33 steps, one picture each, the cat
   growing step by step. So Studio can make an instruction booklet straight from our file.

Not yet looked at: the pawn and the duck (for the duck, whether the slopes face the right way in Studio;
they do in LeoCAD), Studio's collision and stability checks (question 3), and the wanted list (question 4).

2026-11-18, Alec-42's agent: the pawn and the duck are now checked too, and so are the three current
showcase builds. Studio opens a file named on its command line (`Studio.exe "C:\path\file.ldr"`, when
Studio is not already running), so an agent on a computer with Studio can do questions 1 and 2 without
anyone clicking: start it that way, wait about 45 seconds, and take a picture of the window. Results in
Studio 2.26.10, each compared with the file it was given:

| File | Parts in the file | Parts Studio counts | Steps in the file | Steps Studio lists |
|---|---|---|---|---|
| pawn, bricks and plates | 294 | 294 | 58 | 58 |
| duck with slopes | 633 | 633 | 83 | 83 |
| `samples/projects/cat-showcase` | 116 | 116 | 29 | 29 |
| `samples/projects/duck-showcase` | 530 | 530 | 82 | 82 |
| `samples/projects/car-showcase` | 244 | 244 | 45 | 45 |

All five open without an error message and look like our own pictures: colours right (the car's windows
are see-through blue), the duck's slopes facing outwards and down as in LeoCAD, tiles smooth, nothing
floating or missing. Studio names every part in its step list ("Slope 30 1 x 1 x 2/3", "Tile 1 x 2",
"Plate 2 x 3"), so it recognises them as its own parts and not as unknown shapes. Questions 1 and 2 are
answered: yes and yes. The pictures are on Alec's computer in `C:\Users\AlecR\BrickSnap\Results`.

Still needs a person, because both mean pressing buttons inside Studio: question 3 (press Stability, and
look for parts drawn see-through, which is how Studio shows a collision) and question 4 (the wanted list).

2026-11-19, Alec-42's agent: a cat with two round-tile eyes on the front of its head (the first parts we
place sideways, each on a brick with a stud on its side) opens in Studio 2.26.10 with the 139 parts and
31 steps the file holds. Studio names the eyes "Tile, Round 1 x 1" in the last step and draws them flat
against the face. LeoCAD draws the same.

