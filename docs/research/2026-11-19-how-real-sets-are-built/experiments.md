# Experiments 2 and 3: the checker on official sets, and the AI's builds against the guide

Run on 19 and 20 November 2026 by Alec's agent, with no AI build and no AI designer: these are
experiments 2 and 3 of "Experiments to run next" in [the study](README.md). The programs are in
[`scripts/`](scripts/) (the files starting `exp_`); each takes every path as an argument. The
official model files are not in this repository (see "Credits" at the end).

## The short answer

**Experiment 3: the checker cannot yet be trusted on a model built the way real sets are
built.** It raised problems on all 18 official models it was given (10 to 154 each, median 51).
In the six looked at closely (985 parts), 215 problems: 151 are the checker wrong about a legal
construction, 56 a part the library reads badly, none clearly the file author's fault, and 8 that
could not be settled. Its stud check itself is sound, sideways too: it confirmed 442 sideways or
upside-down stud joints in those six sets, and none of its 21 complaints at a sideways stud was
about the side stud as such.
What goes wrong is (A) its rough "filled body", which calls parts that only touch an overlap
(77 problems), (B) bars, which it does not know go into open studs and other hollows (60), and
(C) axles, which the library reads as axle holes (27). Those three fixes would remove 164 of the
215. The joint to prove first is the bar: 39 of the 71 joints it listed as "not checked" are a bar
in a clip, and the 60 false problems of (B) are bars too. A model built in the guide's
side-stud-core-and-panels style would **not** pass today, though nothing is wrong with its side
studs: the guide's own parts (the curved slopes 11477 and 15068, the brackets 44728, 99781 and
99207, jumper plates) are the ones that trip the checker. The BrickHeadz figure 41596 is
exactly that style; all ten of its problems are of kind (A).

**Experiment 2: the AI's builds already keep some rules and miss three badly.** Against 18
official models of 83 to 386 parts, its 20 builds miss most clearly on **building faces
sideways** (3% of stud parts sideways, against 27%; 0% in the first third of the build, against
12%), on **the order of attaching** (wheels go on 5 to 32% of the way through the file, against
84 to 97% in the five official cars that have wheels) and on **starting from an inner core
rather than from the bottom** (the first quarter of an AI build sits at the 15th height
percentile and the 55th distance-from-centre percentile; official, 35th and 32nd). It keeps
"prefer the larger part" (fewer 1 x 1 and 1 x 2 parts than the sets, 45% against 55%), covers
seams about as often as the sets (18% of seams uncovered against 19%, the 8 checked builds), and
mirrors more than the sets do. It has about two thirds of the kinds of part and half the colours
of an official set of its size, and a larger share of each model hangs on a single part (the
largest such section is 32% of a checked AI build, 11% of an official one).

## The models

**Official sets.** The LDraw community's files of official sets (the LDraw Official Model
Repository), as fetched by the study's numbers researcher: 49 files, all still on this machine.
Six were picked for experiment 3, as different as possible, all built with studs nearly
everywhere:

| Set | What it is | Parts as flattened | Why |
|---|---|---:|---|
| 41596 | BrickHeadz figure (a Disney character) | 116 | The guide's style exactly: a core of side-stud bricks, panels pressed on |
| 40441 | BrickHeadz pets: two cats on a tray | 250 | A creature, same style, with a jumper-plate stand |
| 31072 | Creator 3-in-1 racing car, main model | 109 | A small vehicle, with sub-assemblies built sideways and wheels on axles |
| 21026 | Architecture: Venice | 210 | A small building scene: plates, tiles, arches, lamp posts on bars |
| 10349 | Happy Plants: three potted plants | 217 | Plants: clips, bars, round plates on bars |
| 75075 | A small four-legged walker (Star Wars) | 83 | The one with the most clips, hinges and pins for its size |

For experiment 2 twelve more official models of 89 to 386 parts that flatten with no part
unknown were added as the yardstick (Technic sets left out): 40379, 75966, 41498, 21036, 31045,
40433, 41092, 75892, 75895, 76897, 31066, 60067. One other candidate, 60101, was left out because
it uses a sub-part the library does not have as a part.

**AI-built models.** All 20 `.ldr` files of [the earlier study](../2026-11-19-ai-as-the-builder/README.md):
`with-tools/` (7, all passed the checker), `hybrid/duck.ldr` (1, passed; 419 parts, most of them
the solver's body), `no-tools/` (6) and `from-pictures/` (6), the last twelve written with no
checker; ten of those twelve have problems, and in four of them most parts are not joined to the
ground, so the measures that need joints (seams, hanging sections) are given only for the 8
checked builds. `two-ways/` holds pictures only.

### Flattening (`exp_flatten.py`)

The checker reads one flat list of part lines and rejects `0 FILE`. The flattener follows every
reference to a sub-model, multiplying the matrices; writes a sub-model's steps where its parent
first uses it (the builder's order, the same unrolling as `omr_analyse.py`), with `0 STEP`
between steps; and keeps each line's colour, except that **colour 16** (and 24) is replaced by the
colour of the line that placed the sub-model, all the way up. **Parts the library does not
have**: 23 embedded parts named `<set> - <part>.dat` were replaced by the library's own part of
that number, and two printed tiles the library lacks (87079p0s, 69729p05) by their plain parts
(a print does not change the shape); every substitution is listed in the flattener's output.
Nothing unknown was left in the 18 models used. **Minifigures**: a figure's body parts (torso,
arms, hands, hips, legs, head, hair) are left out, as the study did; other parts named "Minifig"
(claws, horns, shields, plumes, handlebars) are kept, because the sets use them as building
elements. 31072 was flattened as its main model; 40441 includes both cats and their tray.
**The ground**: each model was moved up or down so that its lowest point is at y = 0, where the
checker expects the ground. Nothing else was moved.

## Experiment 3: does our checker pass an official set?

Run with `exp_check_sets.py` (the checker's full report per set, and for each overlap a second
opinion from the parts' real shapes: `solid.py`, the movement check's voxels of 0.5 LDU), sorted
with `exp_classify.py`, looked at with `exp_inspect.py` and pictures from `picture.py`.

| Set | Parts | Kinds | Problems | (i) checker wrong | (ii) file | (iii) library | (iv) cannot tell | Not checked: bar in clip | pin | hinge | tyre | Parts with no complaint |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 41596 BrickHeadz figure | 116 | 34 | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 87% |
| 40441 BrickHeadz cats | 250 | 62 | 45 | 26 | 0 | 16 | 3 | 2 | 0 | 2 | 0 | 53% |
| 31072 racing car | 109 | 49 | 58 | 29 | 0 | 29 | 0 | 7 | 4 | 0 | 4 | 0% |
| 21026 Venice | 210 | 46 | 21 | 21 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 90% |
| 10349 Happy Plants | 217 | 54 | 60 | 52 | 0 | 8 | 0 | 25 | 11 | 0 | 0 | 59% |
| 75075 walker | 83 | 33 | 21 | 13 | 0 | 3 | 5 | 4 | 10 | 1 | 0 | 0% |
| **All six** | **985** | | **215** | **151** | **0** | **56** | **8** | **39** | **25** | **3** | **4** | **56%** |

"Problems" counts each "loose" group once, as the checker does. The checker's summary lines, in
order: "116 parts of 34 kinds, 10 problems, 7 warnings"; "250 parts of 62 kinds, 45 problems, 14
warnings, 5 joints not checked"; "109 parts of 49 kinds, 58 problems, 15 warnings, 16 joints not
checked"; "210 parts of 46 kinds, 21 problems, 11 warnings, 1 joint not checked"; "217 parts of
54 kinds, 60 problems, 6 warnings, 37 joints not checked"; "83 parts of 33 kinds, 21 problems,
14 warnings, 15 joints not checked". No set stands without a problem, and none crashed the
checker. "No complaint" means a part named in no problem; 0% for the car and the walker is
because one false problem low down (the axles; the feet) leaves the whole model "loose". Counting
only parts named in a problem other than "loose", the checker complained about 200 of the 985
parts (20%).

The warnings (old part numbers such as 3023 for 3023b, "slight overlaps", parts standing apart)
were not sorted; they are not problems to the AI builder.

### The problems, kind by kind

**Overlaps (104 problems; 81 are the checker's, 23 the library's).**

- *Parts that only touch, at a bracket's flange or a stepped underside* (i): 77 problems in all
  six sets, the largest single cause. Two cases, both legal and very common:
  - The curved slopes 11477 (2 x 1), 15068 (2 x 2) and 93273 (4 x 1 double) have an underside
    of two levels: one half is a plate higher (seen in the library's own drawing of 15068 and
    11477). Official sets set that half over the end of a plate, so the slope sits on the plate's
    studs and on another part's at once: the BrickHeadz head's side panels in 41596 (8 of its 10
    problems), the cats' heads, the car's spoiler. The checker confirms the studs (in 41596 the
    plate's two studs seat in each slope) and then reports an overlap of about 10% where the
    plate's end meets the step.
  - The brackets 44728 and 99781 (and 99207) with plates stacked beside their flange (40441,
    31072, 40379, 75075).
  In 65 of the 77 the shared volume is one 2 LDU column thick, in the other 12 at most 4 LDU:
  the filled body (which fills each part's hollow underside, column by column) is a column too
  wide at the step or flange. Measured on the real shapes, the parts do not go into each other
  at all (10 of the 77) or only as far as a seated stud does in an ordinary plate-on-plate joint
  (3 to 4 LDU, measured the same way). Also counted here: bricks with a curved top straddling a
  plate's edge round the plant pots (10349), a grille tile against a curved slope (21026).
- *A bar inside a part the checker does not know takes one* (i): 4 in 10349: a bar through the
  hollow middle of a round brick, a bar in a Technic pin's hollow end, a three-pronged bar in an
  axle hole.
- *An axle (or the axle end of an axle pin) in a hole* (iii): 20 problems in 31072 and 10349.
  The library draws an axle's body with the axle-hole primitive (`axlehol8` in 44294, `axlehol2`
  in the axle pins 43093 and 11214), so `ldraw_lib` reads each axle as an axle hole. Two holes do
  not make a joint, so axle and wheel, axle and bush, axle pin and Technic brick are each an
  overlap. In 31072 this alone leaves the four wheels unjoined from the car, and the whole car
  (101 parts) is "loose".
- *A part with a clip or bar the library does not record* (iii): a minifigure shield clipped by the
  clip on its back (75902, no clip primitive and no word in its name), the pneumatic T-piece held
  in clips by its body and a steering wheel on its nozzle (31072).

**Stud problems (49; 21 at sideways studs, 28 at studs pointing up).**

- *A bar pushed into an open stud* (i): 27, in four sets: the lamp posts of Venice (a bar in the
  open studs of round plates and a jumper plate), the cats' whiskers (claws in open studs), the
  walker's legs (a bar in the open stud of each foot's dish), the plants (an antenna through
  open-stud round plates, palm leaves on a four-bar hub, a three-pronged bar in an open stud and
  an axle hole). The checker sees a stud pushing into a part with no sockets.
- *A part whose stud grid is read from its bounding box* (iii): 10 (and 9 loose parts that follow).
  `socket_phase` takes a part's stud grid from its bounding box when its sides are not whole
  studs; for the curved slopes with a cutout (29119, 29120: 37 LDU deep) and the curved-top slope
  30602 (48 LDU deep) that puts the grid 3 or 8 LDU off, so correctly placed parts "miss the stud
  grid". 8 of the 21 sideways stud problems are this, on the cats' cheeks.
- *A stud in a Technic pin hole* (i): 4, Venice's tooth plates.
- *A real socket in an irregular underside* (i): 5: a 4 x 4 round-corner brick on its matching
  plate (40441), a triple wedge's nose over a 1 x 2 plate (31072). The socket test wants a flat
  hollow; ribs, fillets and a tapered nose fail it.
- *Cannot tell* (iv): 3. In 40441 the kitten's feet are 1 x 2 parts centred on jumper plates, so
  each jumper's stud is between the part's two sockets, where a real 1 x 2 part has its solid
  middle tube. Either the file is drawn imprecisely or the kitten is meant to rest there
  unattached. In 75075 a 1 x 1 round plate between a bracket's 2 x 2 face and a dish is on no
  stud and not centred between four (8 and 10 LDU off).

**Loose (62 groups; each from a cause above, or a joint not recognised).** Every loose group was
traced to the joint that should have held it: the false problem between one of its parts and a
part outside it. 52 follow from causes already listed. The other 10: *a bar inside a bar tube*
(8 groups in 10349: the checker reads "Bar Tube with Handle" as a bar from its name, so bar and
tube cannot join, i), *a shield clipped by the clip on its back* (2 groups, iii; the library
records no clip on the part), and *a clip on a handle turned 15 degrees* whose mirror twin it does
see (31072, i). Three large groups carry most of the parts: the car of 31072 (92 parts; the axles,
iii), the walker's body (68 parts; bars in its feet's open studs, i), the kitten (72 parts; the
jumpers, iv).

**Is any of it the file's fault (ii)?** No problem was clearly so. The fans' drawings are exact to
the stud wherever the checker could confirm a joint, and every overlap was shallower than an
ordinary stud joint when measured on the real shapes. The 8 problems of kind (iv) are the only
candidates for (ii).

**Not checked.** 71 joints: 39 a bar in a clip, 25 a Technic pin, 4 a tyre on its wheel, 3 a
hinge. No ball joint, wheel pin or axle was listed: the axles were reported as problems instead
(above). None of the six has a ball joint; in a quick run of 30285 (not sorted) the checker
listed its two as "not checked".

### What this means

1. **On a model that is on sale the checker raises about one false problem for every five
   parts** (215 in 985; 10 to 60 per set), every one of them at a construction that official
   sets use, many of them ones the guide teaches. 70% are the checker's own rules ((i): touching counted as overlap;
   bars in open studs and other hollows; a stud in a pin hole; an irregular socket), 26% the
   library's reading of a part ((iii): axles as holes, the stud grid of a part with a cutout,
   clips and bars that are not in a part's name). They would send the AI builder to "fix" legal
   work, or teach it to avoid curved slopes, brackets and bars.
2. **Three changes to the checker would remove three quarters of them** (164 of 215):
   - (A) before calling an overlap a problem, confirm it with the parts' real shapes, which
     `solid.py` already builds for the movement check: an overlap counts only when the real
     solids go into each other deeper than a seated stud does. 77 problems.
   - (B) let a bar go into an open stud, an axle hole, a bar tube, a pin's hollow end or a round
     brick's middle, and count it as a joint ("not checked" until it can be proved). 60 problems.
   - (C) read an axle as an axle when the library draws it with axle-hole primitives (a part
     named "Technic Axle..." has an axle, whatever its primitives say). 27 problems.
   The next is (D) taking a part's stud grid from its sockets rather than its bounding box (19
   problems, and the cutout curved slopes are BrickHeadz staples). With A to D, 183 of 215 go.
3. **Make the bar checkable first.** By count across these six sets, the bar is the joint the
   checker meets most: 39 bars in clips "not checked", plus the 60 false problems of a bar in a
   hollow. Pins come next (25, in the plants, the walker and the car), then
   tyres (4) and hinges (3). This agrees with the study's order (seams and hanging sections, then
   the clip on a bar, then pins).
4. **Would a guide-style model pass today?** No, but for reasons the guide's builder cannot see.
   The side-stud core itself is checked well: 41596, a figure built exactly as the creature
   playbook says, has 82 sideways or upside-down stud connections, all confirmed, and its only problems are the
   10 overlaps where curved slopes sit over plate ends. Two more BrickHeadz files run the same way
   (40379, 41498) behave alike: of their 95 problems, 55 are kind (A), 12 (D) and 12 (B). With fix A,
   41596 passes outright; with A, B and D the other BrickHeadz would be left with 4 and 12 problems
   that were not looked at closely (jumpers again, and printed tiles 3 LDU off on jumper plates).

### After the fixes (20 November 2026)

The checker was changed (branch `wip/Alec-42-checker`; the rules are in the CONTRACT comments
of `bricksnap/lab/validate.py`, `ldraw_lib.py` and `solid.py`): (A) an overlap of the filled
bodies counts only when the real shapes share a piece at least 1.5 LDU thick; (B) a bar in an
open stud, an open tube, an axle hole, a pin hole or a pin's end is a "not checked" joint when
the other part comes in through an end, is bar-thin and in at least the hollow's depth less
1 LDU (3 of an open stud's 4), centred and leaning less than 4 degrees, and shares nothing
with the holder outside the hollow's own space (tightened after an independent review: a bar
driven through a brick's top, entering a stud by 1 LDU or leaning was first let through);
a "Bar Tube" is a tube; (C) a part named "Technic Axle ..." has axles where the library draws axle-hole
primitives, and an axle joins only along a hole's line; (D) a part with no top studs and a box
that is not whole studs takes its stud grid from the end of its box that is on the grid. Two
small ones from the leftovers: (E) a stud in a Technic pin hole is a "not checked" joint; (H)
an axle or a bar handle counts along its whole length. The model files were fetched again
from the OMR (the earlier copies were lost with a temporary folder); flattened, all 18 have the
part counts above, and the checker before the change gives exactly the numbers above.

**The six sets, before and after** (before = `main` at e48ee30, after = the branch; the same
files):

| Set | Parts | Problems before | after | After, by cause | Not checked after | No complaint before | after |
|---|---:|---:|---:|---|---|---:|---:|
| 41596 BrickHeadz figure | 116 | 10 | **0** | | none | 87% | 100% |
| 40441 BrickHeadz cats | 250 | 45 | 4 | 4 (i) irregular socket (F) | bar in an open stud 6, bar in a clip 2, hinge 2 | 53% | 97% |
| 31072 racing car | 109 | 58 | 3 | 1 (i) irregular socket (F); 2 (iii) T-piece and steering wheel (G) | axle 12, bar in a clip 8, Technic pin 4, tyre 4 | 0% | 96% |
| 21026 Venice | 210 | 21 | **0** | | bar in an open stud 6, stud in a pin hole 4, bar in a clip 1, bar in a tube 1 | 90% | 100% |
| 10349 Happy Plants | 217 | 60 | 7 | 5 (iii) shields (G); 2 (iv) plants on a handle (below) | bar in a clip 33, Technic pin 9, bar in an open stud 9, bar in a pin hole 5, bar in an axle hole 3, axle 2, bar in a tube 2, bar in a pin's end 1 | 59% | 71% |
| 75075 walker | 83 | 21 | 5 | 5 (iv) the round plate on the bracket and what follows | Technic pin 10, bar in an open stud 8, bar in a clip 4, hinge 1 | 0% | 92% |
| **All six** | **985** | **215** | **19** | | | **56%** | **92%** |

What went: all of (A) (77 by the sorting above), 58 of the 60 of (B), all of (C) (27; the car
is no longer loose) and (D) (19), the 8 of (E), the turned clip (H), and the 3 kitten
problems of kind (iv), which the change settles: the 1 x 2 part's solid middle tube goes into
the jumper's open stud, a real technique, now a "bar in an open stud" joint. The walker's body
(68 parts) and the car (92) are no longer "loose". The BrickHeadz figure 41596 passes with no
problems, as predicted.

What is left (19, against the 32 predicted): the irregular sockets (F, 5), the parts whose
clips and bars the library does not record (G, 7: five shields, the T-piece and the steering
wheel; their overlaps went with (A), the parts are still loose), the round plate on the
walker's bracket (iv, 5), and, new, two plant groups of 10349 (38 and 20 parts) that the
sorting had put under (B): each plant's 2 x 2 round plate with axle hole sits on the handle of
a "Tile 1 x 2 with Handle", the handle across the plate's underside, touching it and nothing
else. The checker knows no joint there and could not settle whether there is one (iv).

**All 18 official models**: problems before 10 to 154, median 51 (1,000 in all); after 0 to 37,
median **12** (243 in all): 0, 4, 3, 0, 7, 5 for the six, and 3, 7, 17, 13, 12, 31, 12, 27, 14,
37, 22, 29 for 40379, 75966, 41498, 21036, 31045, 40433, 41092, 75892, 75895, 76897, 31066
and 60067 (not sorted by cause). Seven of these the first version of the change had let
through and the tightened bar rule reports again, as `main` did: two cones whose open stud
holds only a short piece of another part, inside it, not coming in from outside (41498, two
stud problems and the two parts loose); a stud of a rotor half a stud off a curved slope
(75892); a jumper under a plane's front whose middle feature sits off the stud's axis
(60067); and a domed cylinder whose bar in an axle pin's end goes on 4 LDU into the pin's
solid axle end (40433; `main` gave it as a slight-overlap warning). None was looked at in the
pictures; all are reported by `main` too, except the last, which `main` only warned about.

**It is still a checker, about as strict as before** (`scripts/exp_mutate.py`, and the
reviewer's finer run). Each of the six sets and the eight AI builds that pass (`with-tools/`,
`hybrid/duck.ldr`) was mutated one change at a time, 12 parts by lot per model and class, and
checked by both versions. A mutation is caught when a new problem names the changed part (any
new problem for a removal). Two readings: (A) a "loose" problem counts only when it makes
loose a part that was not loose before; (S, strict) any new problem counts. Reading A holds
`main`'s count down, because `main` wrongly calls the car and the walker wholly loose and
every change there only changes the loose group; reading S flatters `main` for the same
reason. The honest reading of the two together is **level**, not "caught more often".

The study's own run (2,352 mutations; after the review's fixes):

| Mutation | Made | A: main | branch | no longer caught | newly caught | S: main | branch | no longer caught |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| copy in the same place | 168 | 167 | 168 | 0 | 1 | 167 | 168 | 0 |
| move 4 / 8 / 20 along x | 504 | 451 | 463 | 0 | 12 | 461 | 466 | 1 |
| move 4 / 8 / 20 up | 504 | 451 | 476 | 2 | 27 | 473 | 480 | 4 |
| move 4 / 8 / 20 along z | 504 | 441 | 449 | 5 | 13 | 452 | 452 | 7 |
| sink 4 / 8 | 336 | 307 | 317 | 0 | 10 | 315 | 318 | 3 |
| quarter turn in place | 168 | 123 | 126 | 0 | 3 | 124 | 127 | 0 |
| remove a part others stand on | 168 | 35 | 44 | 1 | 10 | 64 | 44 | 20 |
| **All** | **2,352** | **1,975** | **2,043** | **8** | **76** | **2,056** | **2,055** | **35** |

The reviewer's finer run (3,339 mutations: moves of 1, 2 and 10 LDU, tilts of 5 and 15
degrees, the next size of part, a bar, axle or pin-hole joint pulled 8 and 20 LDU apart, one
side of such a joint taken away):

| Mutation | Made | A: main | branch | no longer caught | newly caught | S: main | branch | no longer caught |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| move 1 (x, z, up, down) | 672 | 103 | 28 | 82 | 7 | 103 | 28 | 82 |
| move 2 (x, z, up, down) | 672 | 623 | 641 | 2 | 20 | 633 | 642 | 6 |
| move 10 (x, z) | 336 | 319 | 323 | 1 | 5 | 321 | 324 | 2 |
| tilt 5 (x, y, z) | 504 | 151 | 159 | 1 | 9 | 153 | 160 | 2 |
| tilt 15 (x, y, z) | 504 | 437 | 447 | 0 | 10 | 440 | 448 | 0 |
| next size | 164 | 164 | 160 | 4 | 0 | 164 | 160 | 4 |
| joint pulled 8 apart | 195 | 129 | 172 | 5 | 48 | 133 | 172 | 8 |
| joint pulled 20 apart | 195 | 135 | 176 | 2 | 43 | 150 | 185 | 3 |
| one side of a joint taken away | 97 | 18 | 22 | 6 | 10 | 52 | 51 | 20 |
| **All** | **3,339** | **2,079** | **2,128** | **103** | **152** | **2,149** | **2,170** | **127** |

Every mutation caught before and not after (reading A), by cause (the reviewer's run first,
103; then the study's own, 8):
- **A part moved 1 LDU (82)**, sideways (74) or down or up (8), into its neighbour: `main` saw it
  through the filled bodies, which flag the same one-column overlap at every part that only
  touches (the 77 false problems of kind (A)). On the real shapes a 1 LDU overlap is a shared
  film two voxels thick, the same as two faces that touch, so the change cannot tell them
  apart: interference thinner than 1.5 LDU (0.6 mm) is not reported (stated in `solid.py`'s
  contract). The ordinary stud check passes a stud 1 LDU off too (it allows 1.5). This is the
  weakest point of the change; telling a 1 LDU overlap from touching needs finer voxels where
  the filled bodies flag a pair, a follow-up.
- **Something now held by a joint `main` did not know (11)**: the walker's dishes slid 2 LDU
  up the leg's bar, pulled 8 along it, or left on the bar when the dish under them is taken
  away (9; the bar through the dish's open stud holds it, as in the set, and `main` called
  them loose because a bar in an open stud was no joint); two axle pins in 10349 left when the
  brick their pin end was in is taken away (2): their axle ends are now axles, joined to the
  part they go into, where `main` read them as holes.
- **An overlap of the filled bodies whose real shapes share less than 1.5 LDU (4)**: a grille
  brick tilted 5 degrees in `car` (its real shapes touch); an axle pin pulled 8 or 20 out of
  its brick in 31072 and 10349, still a pin joint by an older rule (a pin near a hole).
- **The next size (4)**: a 1 x 2 tile on two open side studs swapped for a 1 x 3 tile, whose
  underside pins then stand in the two open studs, half a stud along: buildable (the jumper's
  technique).
- **The half pin with a bar** (75075 line 109; the library draws its pin's tip as an open stud)
  pulled 2 or 10 LDU along its hole (2): the pin is still in the hole.
- In the study's own run: the same dish slid 4 or 8 up its bar and dish 92 left on it (3); the
  same half pin pulled 4, 8 or 20 (3; at 20 only its tip, 4 LDU, is in the hole, read as a
  stud in a pin hole); the plate with a wheel pin in `our-car` moved 20 along the car (2):
  caught before only by a false overlap with the mudguard, whose real shapes do not meet; the
  real fault, the wheel pin out of its wheel, is missed by both versions by the older rule that
  a wheel pin near a wheel is a "not checked" joint.

A loss found on the way and fixed: a part copied in place that joins by a hinge or pin was a
"not checked" joint with itself (in both versions); the same part twice in one place is now
always an overlap.

Each limit of the bar rule, the axle rule, the pin hole and the overlap depth has a test that
fails when the limit is loosened (`scripts/` holds no such run; it was done by editing a copy
of the code: `BAR_RING` 5 to 8 or 4, `BAR_PLAY` 1 to 3, `BAR_DEG` 4 to 45, `BAR_OFF` 1 to 4,
the real-shape test outside the hollow dropped, the bar-goes-on test dropped, `AXLE_DEG` 5 to
45, `AXLE_IN` 0.5 to -4, the one-stud-per-pin-hole rule dropped, the same-part-twice rule
dropped, `REAL_MARGIN` 1 to 3: each fails at least one test in `tests/test_lab.py`).

**Speed** (one full check, `check()` with movement; "cold" is an empty parts and shapes cache in
a new process, "warm" the second check in the same process):

| Model | Parts | main: cold, first check | warm | branch: cold, first check | warm | Added, warm |
|---|---:|---:|---:|---:|---:|---:|
| 31072 | 109 | 0.81 s | 0.30 s | 1.36 s | 0.45 s | +0.15 s |
| 40379 | 149 | 0.90 s | 0.46 s | 1.35 s | 0.56 s | +0.10 s |
| 40441 | 250 | 1.51 s | 0.94 s | 2.19 s | 1.09 s | +0.15 s |

(First check in a new process with the disk cache filled: 0.35, 0.52, 1.00 s on main; 0.62,
0.74, 1.27 s on the branch. The cold cost is the real shapes of the parts the filled bodies
flag, built once and kept on disk; the cache's version was raised, so every part is read
again once after the change.)

## Experiment 2: how far are the builds we have from the guide's rules?

Run with `exp_measures.py`, tabled with `exp_tables.py`. Every measure is made the same way on
every model, from the file's part lines in order (an official model's order is the flattener's,
which is its booklet order as the file's author drew it). The definitions are in the program's
opening comment; in short:

- **Stud parts** are parts with studs or a socket in the library's geometry. A part *faces* the
  way its own top points: up, sideways (within 25 degrees of level), down, or angled.
- **Size**: a stud part's footprint in whole studs; "small" is 1 x 1 or 1 x 2.
- **An uncovered seam**: two upright stud parts whose bottoms are level, touching side to side
  along 10 LDU or more, with no third part joined by studs to both (the checker's own links).
  Rough: only upright parts turned a whole quarter count, and an official model's missing links
  (the false alarms above) can only add uncovered seams.
- **A hanging section**: parts joined by the checker's stud links, its "not checked" joints and
  any pair it names in a stud or overlap problem; a part whose removal splits that graph holds a
  section, which is everything but the largest piece left. Parts not joined to the ground at all
  are left out (this is why only the 8 checked AI builds are given).
- **Core first**: where the first quarter of the part lines sits in the model, as a percentile of
  height (0 = lowest) and of horizontal distance from the centre (0 = innermost).
- **Mirrored**: the share of parts with a twin of the same kind and colour at the mirror position
  across the best plane. Left and right versions of a part are not twins, so this is a lower bound.

**AI-built models** (20; the structural columns for the 8 checked builds only)

| Model | Parts | Kinds | Colours | Sideways (1st / last third) | 1x1, 1x2 | Footprint | Seams uncovered | Largest hanging section | 1st quarter: height / distance pct | Wheels go on at | Mirrored |
|---|---:|---:|---:|---|---:|---:|---:|---:|---|---:|---:|
| with-tools/cat | 78 | 35 | 7 | 12% (0 / 35) | 53% | 4.3 | 21% | 33 | 22 / 79 | | 85% |
| with-tools/our-cat | 114 | 32 | 4 | 17% (0 / 41) | 47% | 5.4 | 13% | 48 | 12 / 44 | | 88% |
| with-tools/car | 102 | 33 | 10 | 6% (0 / 3) | 50% | 4.3 | 38% | 58 | 15 / 59 | 13% | 91% |
| with-tools/car-by-opus | 108 | 32 | 7 | 13% (0 / 25) | 49% | 4.8 | 17% | 10 | 11 / 50 | 10% | 100% |
| with-tools/our-car | 137 | 32 | 7 | 6% (0 / 18) | 25% | 8.4 | 15% | 29 | 16 / 55 | 16% | 100% |
| with-tools/flower | 58 | 24 | 7 | 24% (0 / 58) | 43% | 7.0 | 12% | 28 | 9 / 48 | | 86% |
| with-tools/our-duck | 159 | 30 | 4 | 2% (0 / 8) | 11% | 8.6 | 20% | 2 | 17 / 57 | | 96% |
| hybrid/duck | 419 | 40 | 3 | 2% (0 / 7) | 67% | 3.4 | 33% | 10 | 14 / 61 | | 70% |
| no-tools, 6 models | 59 to 101 | 13 to 33 | 4 to 9 | 0 to 34% | 32 to 67% | 3.5 to 4.8 | | | 7 to 20 / 32 to 84 | 5%, 7% | 83 to 98% |
| from-pictures, 6 models | 89 to 170 | 17 to 32 | 3 to 8 | 0 to 4% | 5 to 55% | 5.8 to 10.2 | | | 10 to 21 / 32 to 80 | 6%, 32% | 91 to 100% |
| **Median of 20** (structure: of 8) | 100 | 29 | 7 | **3% (0 / 5)** | 45% | 5.1 | 18% | 28.5 (32% of the model) | **15 / 55** | **10%** (7 cars) | 92% |

**Official models** (18)

| Model | Parts | Kinds | Colours | Sideways (1st / last third) | 1x1, 1x2 | Footprint | Seams uncovered | Largest hanging section | 1st quarter: height / distance pct | Wheels go on at | Mirrored |
|---|---:|---:|---:|---|---:|---:|---:|---:|---|---:|---:|
| 41596 BrickHeadz | 116 | 34 | 12 | 48% (45 / 87) | 60% | 3.3 | 12% | 42 | 30 / 55 | | 100% |
| 40379 BrickHeadz | 149 | 46 | 18 | 45% (33 / 33) | 63% | 3.4 | 3% | 46 | 39 / 24 | | 78% |
| 40441 BrickHeadz pets | 250 | 62 | 10 | 37% (11 / 42) | 63% | 3.7 | 31% | 114 | 37 / 30 | | 53% |
| 41498 BrickHeadz pair | 329 | 89 | 17 | 52% (43 / 50) | 66% | 3.2 | 10% | 24 | 28 / 63 | | 51% |
| 31072 racing car | 109 | 49 | 9 | 42% (0 / 43) | 56% | 3.6 | 3% | 12 | 25 / 60 | 97% | 94% |
| 75892 car | 216 | 83 | 11 | 28% (8 / 79) | 48% | 3.9 | 31% | 24 | 42 / 18 | 84% | 80% |
| 75895 car | 176 | 64 | 12 | 22% (12 / 53) | 57% | 3.6 | 17% | 15 | 38 / 18 | 97% | 97% |
| 76897 car | 256 | 80 | 11 | 23% (18 / 22) | 53% | 4.3 | 23% | 14 | 27 / 52 | 97% | 93% |
| 40433 car | 362 | 106 | 13 | 20% (19 / 20) | 49% | 4.5 | 19% | 22 | 26 / 30 | 96% | 95% |
| 75075 walker | 83 | 33 | 6 | 25% (13 / 22) | 53% | 3.1 | 18% | 30 | 36 / 31 | | 99% |
| 10349 plants | 217 | 54 | 15 | 52% (53 / 61) | 41% | 4.6 | 26% | 15 | 55 / 67 | | 44% |
| 21026 Venice | 210 | 46 | 6 | 12% (27 / 0) | 58% | 3.5 | 30% | 35 | 80 / 19 | | 47% |
| 21036 building | 386 | 49 | 9 | 30% (2 / 51) | 68% | 3.9 | 20% | 89 | 11 / 63 | | 88% |
| 75966 scene | 169 | 57 | 14 | 12% (11 / 27) | 50% | 3.9 | 28% | 17 | 34 / 63 | | 44% |
| 31045 vessel | 213 | 70 | 13 | 34% (1 / 34) | 52% | 3.6 | 10% | 41 | 27 / 21 | | 79% |
| 31066 vehicle | 285 | 100 | 14 | 27% (7 / 36) | 38% | 6.5 | 19% | 9 | 24 / 31 | | 83% |
| 41092 scene | 89 | 53 | 20 | 4% (4 / 4) | 58% | 3.4 | 0% | 13 | 48 / 76 | | 18% |
| 60067 vehicles | 246 | 98 | 21 | 6% (0 / 17) | 31% | 8.9 | 10% | 21 | 41 / 33 | | 66% |
| **Median of 18** | 215 | 60 | 12.5 | **27% (12 / 35)** | 55% | 3.7 | 19% | 23 (11% of the model) | **35 / 32** | **97%** (5 cars) | 79% |

Five official models of under 150 parts have a median of 46 kinds and 12 colours; the study's
parts lists give 45 kinds and 13 colours at 100 to 150 parts (435 sets). The 20 AI builds, at
about 100 parts, have 29 kinds and 7 colours. Wheels: the first official wheel goes on at 63 to
94% of the way; in the seven AI cars the first wheel goes on at 1 to 28%. The six mirror figures
under 55% are scenes or pairs of separate models (two cats and a tray, three plants, two
figures, a city view, two rooms), for which one mirror plane cannot work.

I looked at the pictures behind the numbers that matter: the AI cat's 12% sideways is its eyes,
muzzle, whiskers and the curled tail; the rest is stacked. The BrickHeadz figure's 48% is its
whole face and both sides of its head.

### The guide's twelve rules, one by one

| Rule | The AI's builds | Evidence |
|---|---|---|
| 1. Build the core first | **Miss by a little** for vehicles, **badly** for creatures | They start with what everything sits on, but always at the bottom: the first quarter is at the 15th height percentile (official 35th) and not inward (55th distance percentile; official 32nd). In cars that bottom is the right core (a plate base). The cats start with stacked bricks: side-stud bricks are 0 to 4% of the first quarter of the AI cats, against 10 to 19% in the four BrickHeadz |
| 2. Attach in order, wheels late | **Miss badly** | Wheels at 10% of the way (median, 7 cars), against 97% (5 official cars). The AI puts the wheel modules on with the base |
| 3. Build apart, then join | Not measured | The AI's files have no sub-models; official files do. A flat file cannot show it |
| 4. Build a repeated unit once and copy it | **Keep** | 92% of parts have a mirror twin (official 79%; 93 to 100% in the official cars) |
| 5. One joint per moving part | Not measured | |
| 6. Cover every seam; prefer the larger part | **Keep, roughly** | 18% of seams uncovered (8 checked builds) against 19%; fewer 1 x 1 and 1 x 2 parts (45% against 55%) and a larger mean footprint (5.1 studs against 3.7). But their sections hang on single parts more: the largest is 32% of a model against 11%. Uncovered seams per 100 parts are higher (20 against 9) because more of an AI build is stacked layers |
| 7. Build shaped faces sideways | **Miss badly** | 3% of stud parts sideways (official 27%, BrickHeadz 47%); 0% in the first third (official 12%). Even the best, the checked cats, reach 12 to 17% and all of it in the last third |
| 8. A stiff spine in long thin things | Not measured | |
| 9. Only joints the parts were made for | Not measured here | The checked builds pass the checker, which is all these measures could say |
| 10. Small steps | Not measured | |
| 11. Keep weight off joints | Not measured | |
| 12. Many kinds of part, a few of each | **Miss by a little** (kinds), **badly** (colours) | 29 kinds and 7 colours at about 100 parts, against 45 and 13 in sets of 100 to 150 parts |

**The three that would change its models most**, on this evidence: rule 7 together with the
creature playbook's head core (sideways faces: 3% against 27%, the largest gap and the one that
changes how a model looks); rule 2 and the playbooks' "Order" lines (wheels, roof and what sticks
out last: the AI does the opposite with wheels); and rule 1 as the guide corrects it, an inner
core chosen for the subject rather than "from the ground up" (line order against height has a
median Spearman rho of 0.91 in the AI's builds, against 0.25 in the official ones). Rule 12 is a real gap but mostly of colour, and cheap to ask
for. Rules 4 and 6 need no teaching; the guide could drop "prefer one larger part", which the AI
already overdoes for its size.

**What these measures cannot test**: rules 3, 5, 8, 9 (beyond "it passes the checker"), 10 and 11;
how good a model looks; and whether any of this makes a better model. That is experiment 1, which
needs AI runs.

## Limits

- **Small numbers.** Experiment 3 rests on six sets looked at closely (and two more run but only
  sorted by the rules); experiment 2 on 20 AI builds and 18 official models, not drawn by lot.
  The AI's builds are of three subjects (cat, car, duck, plus two flowers), so its medians are
  medians of those subjects.
- **The sorting into causes** was done by rules written after looking at examples (in
  `exp_classify.py`, with the 23 decisions taken by hand, and two parts' joints, listed in it). Each construction was
  looked at in at least one example, with pictures and positions; not every one of the 215
  problems was looked at.
- **The real-shape measure** of an overlap is itself rough at stud joints: an ordinary seated
  stud measures 3 LDU. It was used only to tell "touching" from "going into".
- **Facing** uses a part's own top; a side-stud brick standing upright counts as up although it
  offers side studs, as in the study's numbers.
- **Line order is build order** only as far as the files' authors kept to the booklets, and the AI
  wrote its lines in the order it placed parts, which is its build order.

## Files

- `experiments.md`: this file.
- `scripts/exp_flatten.py`: multi-part LDraw file to one flat model for the checker.
- `scripts/exp_check_sets.py`: runs the checker, measures overlaps on the real shapes.
- `scripts/exp_inspect.py`: prints and draws the lines a problem names.
- `scripts/exp_classify.py`: sorts problems by cause, and by the change to the checker that would
  remove them.
- `scripts/exp_measures.py` and `scripts/exp_tables.py`: experiment 2.
- `scripts/exp_mutate.py`: the mutation run of "After the fixes" (`--code DIR` runs it with
  another copy of the code, to compare two versions of the checker).

To run again (the model files must be fetched again from the LDraw Official Model Repository,
one folder per set holding `model.mpd`): `uv run python -I scripts/exp_flatten.py <set>/model.mpd
<out>/<set>.ldr` (add `--start "31072 - main.ldr"` style options as needed), then
`exp_check_sets.py <dir> <out>/*.ldr`, `exp_classify.py <out.json> <set>.json <set>.ldr ...` and
`exp_measures.py <out.json> <models...>`.

## Credits

The official models are files of the LDraw Official Model Repository
(https://library.ldraw.org/omr), licensed CC BY 2.0 (one CC BY 4.0), by: Damien Roux (21026,
41498, 41596), Vincent Messenet (40379, 40441), Marc Belanger (31072), Chris Böhnke (10349),
folkoluck (75075), Stefan Frenz (75966), Orion Pobursky (21036, 40433), Tomas Kralicek (31045),
Philippe Hurbain (31066, 41092), Adrien Pennamen (75892, 76897), Magnus Forsberg (75895) and
Merlijn Wissink (60067), with sub-models and parts by others named inside them. No model file is
in this repository. LEGO® is a trademark of the LEGO Group, which does not sponsor, authorize or
endorse this project; the sets' designs are the LEGO Group's, and a set's number appears here only
to say where something was seen. Part shapes are from the LDraw parts library (CC BY 4.0).
