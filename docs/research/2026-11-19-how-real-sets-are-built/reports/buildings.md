# How official LEGO buildings are built: category `buildings`

> **Editor's note.** This is one of the eight reports behind the study in `../README.md`, kept as its evidence. It is as its researcher wrote it, except for what this note lists. Points where the reports disagree with each other are dealt with in the README, not corrected here.
> Changed: three mentions of folders on the researcher's computer were removed.

Study for BrickSnap: how buildings and their interiors are built in four official sets.
All techniques below are described in my own words. Nothing was copied, and no page images
were saved anywhere except temporary renders kept outside the repository.

## Sources and method

- **Instructions.** `https://www.lego.com/service/buildinginstructions/<n>` answered HTTP 403 to
  plain `curl`, whether I used a generic client name or the default one. I did not get round
  that. Instead the WebFetch tool read the same public page and listed the PDF links, and
  LEGO's CDN (`/cdn/product-assets/product.bi.core.pdf/<id>.pdf`) served the PDFs directly to a
  generic client. I downloaded one booklet per file, eight files in all, each set in its own
  folder.
- **Reading.** `pdftoppm` is not installed. I rendered pages with PyMuPDF (`uv run --with
  pymupdf python -I`), using a script kept apart from the downloads.
  The renders are contact sheets of four pages each, and a few single pages at high resolution.
- **Rebrickable** returned 403 as well, so I could not check part lists there. I checked part
  numbers with the project's own part search (`bricksnap/lab/search.py`, read-only). A number
  means the part exists in the LDraw library under that description. When I identified a part
  only from an instruction drawing, I say so.
- **Tags.** [seen p.X] = in the instruction pages I read (PDF page numbers).
  [recalled] = general knowledge I did not check.

| Set | Name | Year / parts (per LEGO's page) | Booklets used | Pages read |
|---|---|---|---|---|
| 10297 | Boutique Hotel (Modular Building) | 2022 [recalled] / 3,066 [recalled] | 1 booklet, 296 pp | about 120: pp 1-48, 53-56, 61-64, 73-76, 85-104, 109-124, 133-136, 157-160, 181-184, 205-208, 237-240, 257-260, 265-268, 277-284 |
| 31139 | Cozy House (Creator 3-in-1, main model) | 2023 / 808 [seen on lego.com page] | booklet 1/3 (main model, 144 pp); first pages of 2/3 | about 76: pp 1-48, 61-64, 73-76, 81-84, 93-96, 109-112, 133-136; booklet 2 pp 1-4 |
| 60316 | Police Station (City) | 2022 / 668 [seen on lego.com page] | booklet 2/3 (helicopter and station building, 168 pp) | about 48: pp 1-8, 17-48, 61-64, 77-80, 93-96, 109-116 |
| 21044 | Paris (Architecture skyline) | 2019 / 649 [seen on lego.com page] | 1 booklet, 112 pp | about 72: pp 1-52, 61-64, 81-84, 89-96, 101-104 |

I did not read booklets 1 and 3 of 60316 (vehicles, gate and helipad) or the two alternative
models of 31139.

---

## 10297 Boutique Hotel (large modular, about 3,000 parts)

1. **The set.** A corner hotel of three storeys plus a roof, on a 32x32 baseplate. Each storey
   is its own module, and each lifts off the one below [seen p.111-124, 205-208, 265].
   There are 14 numbered bags [seen p.5, 260].
2. **What is built first: (d) a large moulded base, then (a) a stack of bricks.** Step 1 is the
   baseplate, with a border of long grey tiles along its edges [seen p.7]. Next come the
   pavement tiles and a single course of light grey bricks. That course is the foundation: it
   traces the building's whole footprint, one stud thick [seen p.8-10]. Then the floor
   pattern, all tiles, is laid directly on the baseplate [seen p.11-20]. The walls go up
   course by course from bag 2 [seen p.25 on]. The ground floor is finished at step 153
   (p.111, bags 1-6), about 38% of the pages. Each later storey starts by building its floor
   plate as a separate sub-assembly [seen p.113-120].
3. **How the core is made strong.**
   - Walls are one stud thick and laid in running bond: 1x4, 1x6 and 1x8 bricks, each course
     offset from the one below [seen p.25-26, 41-45].
   - Corners are woven. Courses alternate which wall runs through the corner, and 1x1 or 1x2
     bricks fill the ends [seen p.25-26 step 24-25].
   - At the top of the ground floor, one course of long bricks (1x6, 1x8) runs right round the
     storey, *over* the tops of the window frames and pillars, and locks every opening into one
     ring [seen p.99-101 step 143-144].
   - Each upper floor is a two-layer plate sandwich. A top layer of large dark-tan plates (the
     floor) is laid crosswise over a bottom layer of white plates, which form the ceiling of
     the room below. The seams of one layer fall in the middle of plates in the other
     [seen p.113-120, 205-208]. The roof is made the same way in dark grey [seen p.265-266].
   - No beam-and-pin frame anywhere. The only Technic parts in the ground floor are
     2 Technic bricks 1x2 with hole (LDraw 3700) set into the foundation course, with
     Technic pins (3673) pushed into them on the side walls [seen p.9 step 3]. Their job is to
     join this building to the neighbouring modular building. Modular buildings are known to
     use pins this way [recalled].
4. **How the outside attaches.**
   - Mostly by studs pointing up: the facade is the wall.
   - The textured upper facade (sand-green "bent" pilasters, white columns, capitals) stands on
     top-studs of the wall, between the window frames [seen p.159-160, 237-240].
   - Lamps and flower boxes go on sideways, on 1x1 bricks with a stud on one side (87087)
     [seen p.54 step 72, p.237-238].
   - Picture frames go on brackets [seen p.48 steps 53-64, a sub-assembly panel].
   - **Angled facades.** The hotel has a 45-degree corner. On the ground floor, the diagonal
     wall stands on a strip of long plates, joined to the square part by a horizontal swivel
     hinge: two 1x2 plates on a pivot. From the drawing this looks like Hinge Plate 1x4
     Base/Top (2429/2430); I identified it only from the picture [seen p.31-32 steps 30-35].
     The upper floors repeat this: the wedge-shaped wing of each floor plate is a separate
     sandwich, joined at a swivel hinge drawn in blue [seen p.116 step 162, p.119 step 169,
     p.207 step 313]. Wedge plates cut the diagonal edge [seen p.115-118].
   - **Curved corners** are built from stacked 2x2 round-corner bricks (3063b by description)
     [seen p.53 step 71], and a ring of curved bricks around a 4x4 round plate
     [seen p.121 step 171, p.32 step 35].
5. **Built separately and attached.**
   - Every piece of furniture. Examples: a vending machine of about 15 parts [seen p.22-23],
     a reception desk of about 12 [seen p.38 steps 40-44], a wall cabinet panel of about 20
     [seen p.47-48], a wardrobe of about 8 [seen p.157], a bed, and stairs built as stepped
     brick blocks [seen p.133-134].
   - The rooftop stair-house, a wall with an arched window [seen p.181-184].
   - The dome. Its core of bricks with studs on their sides (and brackets) is clad with
     sand-green curved slopes all round [seen p.280-284 steps 428-441].
   - The skylight: curved transparent panels clipped over a hole in the roof plate
     [seen p.277-279].
   - Each storey is one big module that sits on the storey below.
6. **What moves.** The storeys lift off. Doors open in moulded frames [seen p.95 step 139].
   Nothing else moves.
7. **Inside.**
   - Hidden structure uses bright colours where nobody sees it: blue for the hidden swivel
     plates at the floor joint [seen p.116], red for parts under the roof plate [seen p.265].
   - The underside of each floor plate is white, because it *is* the ceiling of the room below
     [seen p.114-119].
   - The building is completely hollow. Rooms are separated by partition walls only one or two
     bricks high, in white [seen p.124 step 174, p.135-136].
8. **What sets the scale.** The minifigure: rooms are tall enough for one, and doors and windows
   are minifigure-scale frames.
9. **Order.** Bottom-up, storey by storey. Within a storey: floor, then foundation course, then
   floor pattern, then the first wall courses on two sides, then furniture *before* the walls
   close in (the vending machine and desk go in by steps 23 and 45, the facade windows only
   at steps 138-140), then windows and pillars, then a locking course on top. Typically 3 to
   20 parts per step: about 5-10 for walls, 1-4 for each sub-assembly step, up to 20 for a
   pattern of floor tiles.
10. **Named techniques.** Running bond with woven corners. A locking course over openings.
    Plate-sandwich floors with white ceilings. Swivel hinges for 45-degree walls. Sideways
    lamps on side-stud bricks. Columns of round bricks under capitals [seen p.159-160]. Stacked
    1x2 pilaster sub-assemblies with a textured face (a 1x2 profile brick, a jumper, a
    plate) [seen p.98 step 142]. A domed cap with a sideways-built core.

**How floors lift off and sit [seen p.101-124].** The top course of the walls below ends with
bare studs. The next floor plate lies on those studs, held only by the perimeter studs that
line up. Its underside is a smooth sandwich of plates, with a few bricks of the wall above set
in from the edge. The hole for the stairwell is left open in both layers [seen p.117 step 163].
How firmly a floor grips is not in the instructions: it grips on every stud it covers, but
only the wall tops lie under it. That modular floors come off easily because of this is
[recalled].

## 31139 Cozy House (Creator 3-in-1 main model, 808 parts)

1. **The set.** A two-part house. There is no baseplate: two square bases are joined by a hinge,
   so the halves swing open like a book [seen p.21 step 19, p.134 step 167 with a turning
   arrow]. Four bags.
2. **What is built first: (a) a plate stack, as a base frame.** Long green plates are laid side
   by side, with a dark-grey plate across them like the rungs of a ladder [seen p.8-9 steps
   1-3]. The frame is turned over and plates are added underneath to lock it [seen p.10 step 5].
   Then a large green plate and a brown 6x10 plate (3033 by description) go on top as ground
   and floor [seen p.9-10]. The second half's base is built the same way [seen p.35-39]. The
   base is finished by step 6, about 25 parts per half.
3. **How it is made strong.**
   - Three crossing layers of plates in the base.
   - Walls of white 1x2/1x4 bricks in running bond [seen p.24 step 22, built as a staggered
     sub-assembly then placed].
   - Corner posts of L-shaped 2x2 corner bricks (2357) stacked with 1x1s to weave them
     [seen p.46 step 45].
   - Beside a door, single columns of stacked 1x2 bricks [seen p.15 step 14]. These are weak
     on their own and are tied in by the course above.
   - The ridge of the gable is tied by a long brick across the top [seen p.82 step 89].
4. **How the outside attaches.**
   - Studs up for the walls.
   - The windows are 1x2x3 frames with a 1x2 tile with rail below as a sill and a plate above
     [seen p.14 step 13, p.45 step 44].
   - Lamps, a mailbox and a picture go on sideways bricks or brackets [seen p.17-18 step 16].
   - **Roof.** Each pitch is one flat plate panel: a 6x10 plate in sand blue, with curved slopes
     along the eaves and tiles laid diagonally as a shingle pattern. It is mounted on 2 hinge
     plates (brown, 1x2 hinge plate pair; by description 2452/4275-4276) on its top edge, so
     the panel leans at the gable angle and can be lifted [seen p.93-95 steps 104-108].
   - The gable walls are stepped courses of white bricks capped with 45-degree slopes [seen
     p.81-84 steps 88-92].
5. **Built separately.**
   - Furniture blocks of 3-12 parts each: an oven of about 6 [seen p.25 step 23], a sink unit
     of about 4 [seen p.26 step 24], an armchair of about 12 [seen p.61-62], a bed of about 12
     on flat plates [seen p.73 step 76].
   - The chimney, a stack of masonry-profile bricks [seen p.109-111].
   - The upper storey, a box with its own floor, placed on the ground floor [seen p.63 step 66].
   - The roof panels, each repeated for the two halves [seen p.93-96, 133-134].
6. **What moves.** The hinge between the two bases. The roof panels on their hinges. Doors.
   The pieces that move all sit on the base frame or on top of walls; there is no inner
   mechanism.
7. **Inside.** Grey and dark grey for hidden frame plates [seen p.8-9]. The walls are hollow
   shells. Rooms are open at the back, which is why the halves fold.
8. **Scale.** The minifigure (door 1x4x6, rooms one minifigure tall).
9. **Order.** Base, then the first wall courses, then furniture placed early against the back
   walls [seen p.25-28], then windows and doors, then the upper module, roof and chimney last.
   1-8 parts per step.
10. **Techniques.** A plate-ladder base with no baseplate. A hinge between modules. Roof panels
    on hinge plates. Stepped gables of slopes. Running-bond walls with woven corner bricks.

## 60316 Police Station (City, 668 parts)

1. **The set.** Station building, cell block, road plates, helicopter and vehicles. The building
   stands on an 8x16 plate [seen booklet 2 p.20-23].
2. **What is built first: (a) a plate, then tall moulded wall elements.** A small corner
   sub-assembly (a 4x6 plate, a course of blue bricks, a 1x6x5 panel (59349), a 1x2x5 brick
   (2454a/88393)) is placed onto the 8x16 floor plate [seen p.20-24 steps 1-5]. The walls are
   mostly a single course of blue bricks, topped by 1x2x5 pillars, 1x6x5 panels and 1x4x6
   door frames (60596) with glass [seen p.24-34].
3. **How it is made strong.** By the ceiling. Two large white plates are laid over all the
   wall tops [seen p.35 step 17], and a course of blue 1x6 bricks along the edges covers the
   seam between the two plates [seen p.37-39 steps 18-21]. Over a gap, a long plate is laid
   across two pillars as a lintel before the roof plate goes on [seen p.95 step 79, the cell].
4. **How the outside attaches.** By studs. Signs, lamps and cameras go on side-stud bricks
   [seen p.39 step 20, p.77 step 60]. The upper floors are narrower and stepped. The sloping
   roofline is made of tall 75-degree slope bricks (by description 4460b) [seen p.63 step 46].
5. **Built separately.** Furniture of 4-8 parts each [seen p.29 step 11, p.46-48 steps 25-30].
   A break-out wall section built on its own and set on loosely [seen p.110-111 steps 99-100].
   A tree [seen p.114-115].
6. **What moves.** Cell doors in moulded frames. The break-out wall. Nothing structural.
7. **Inside.** The rooms are open at the back, dollhouse-style, with no back wall above the
   ground floor [seen p.61-64]. The floors do not lift off: each storey is built directly on
   the ceiling plate below [seen p.61-64].
8. **Scale.** The minifigure.
9. **Order.** Floor plate, wall elements left to right, furniture as you go, ceiling plates,
   next storey. 1-3 parts per step.
10. **Techniques.** Large panels and tall bricks instead of brick courses. A ceiling plate as the
    lock. A long plate as a lintel. Open-back rooms.

## 21044 Paris (Architecture skyline, 649 parts)

1. **The set.** A skyline of Arc de Triomphe, Champs-Élysées houses, Tour Montparnasse, Grand
   Palais, Eiffel Tower and Louvre on a long narrow base [seen p.1, 12]. Two bags.
2. **What is built first: (a) a stack of bricks and plates, as a long base strip.** A row of
   black bricks with studs on their sides runs along the front (by description 30414, Brick 1x4
   with Studs on Side) [seen p.12-14 steps 1-6]. Plate arms branch backwards [seen p.15-18].
   The strip is turned over and long plates are laid underneath across the joints [seen p.19-22
   steps 11-14]. Long dark tiles go on the side studs as the front skirt, and a printed
   nameplate is mounted the same way [seen p.24 step 16]. The base is finished by step 24 (p.32),
   about 20% of the parts.
3. **How it is made strong.** Running-bond bricks in the base strip, with plates under it
   crossing the joints [seen p.19-22]. Each landmark is small and stands on many studs.
4. **How the outside attaches.**
   - The ground is mostly covered with tiles (streets, paving). Studs are left open only where a
     building will stand [seen p.25-32].
   - Tan jumper plates set some buildings half a stud off the grid [seen p.30 step 22].
   - The Grand Palais has a core of tan 1x1 bricks with studs on four sides (4733), carrying a
     transparent dome and transparent round-brick "glass vaults" [seen p.37-38 steps 29-30].
   - Tour Montparnasse is a pillar of alternating 1x2 plates and 1x1 bricks with studs on
     several sides, hidden in red, tan and blue. It is clad on all four faces with dark curved
     slopes and plates mounted sideways [seen p.46-52 steps 38-53].
   - The Eiffel Tower:
     - Its lower body sits on a 4x4 plate with a 2x2 open centre (64799 by description) and
       side-stud bricks [seen p.83-84 steps 84-88].
     - Its legs are 1x4 plates with clips and bars, set at an angle with clip-and-bar joints
       [seen p.91-93 steps 99-105].
     - The upper spire is a bar threaded through stacked 1x1 bricks with studs on four sides,
       skinned on all four sides with clip plates and grille tiles [seen p.94-96 steps
       106-114].
5. **Built separately.** Each landmark is its own sub-assembly placed on the base. Repeated
   elements: the 4 legs of the Eiffel Tower (4x), the 2 glass vaults (2x), trees (5x, each a
   1x1 round plate and a plant piece) [seen p.45 step 37].
6. **What moves.** Nothing.
7. **Inside.** Bright hidden colours inside cores (red plates, tan and blue side-stud bricks
   inside the black tower) [seen p.46-52]. Everything is solid at this scale.
8. **Scale.** No minifigure. The scale is set by the base depth: buildings are 2-6 studs deep.
   A 1x1 brick reads as one storey or one window bay [seen p.43-44].
9. **Order.** Base strip, ground surface, then landmarks left to right, tallest last (the Eiffel
   Tower is bag 2). 1-8 parts per step.
10. **Techniques.** Side-stud cores clad sideways. Bar through stacked side-stud bricks.
    Clip-and-bar legs. Jumper half-stud offsets. Grille tiles as ribbed roofs and glazing
    [seen p.42 step 34]. Stacks of 1x1 bricks and plates in two colours, which read as rows of
    windows [seen p.43-44].

---

## Answers to the category questions

**The core of a hollow building**
- The core is not a solid block. It is
  - a base (a baseplate, a stack of plates, or a ladder of long plates),
  - a first course traced along the whole footprint,
  - and, every storey, a horizontal plate layer that locks all the walls together.

  The ring of walls plus the plate lid is the structure, like a box [seen 10297 p.8-10,
  99-120; 31139 p.8-10; 60316 p.35].
- Walls are one stud thick, laid in running bond, with corners woven by alternating courses
  or by L-shaped corner bricks [seen 10297 p.25-26; 31139 p.46].
- How often a wall is locked:
  - at the top of every storey, by a continuous course of long bricks or by the floor plate;
  - over every opening, by a long plate or brick;
  - at the foot, by the foundation course.
- I saw no lock mid-height in the walls of 10297. The running bond itself spreads the load
  [seen p.41-45].

**Lift-off floors and roofs**
- Floors are plate sandwiches that sit on the bare studs of the wall tops.
  - Their white underside is the ceiling.
  - Stairwells are holes in the floor.
  - Only studs that line up with wall tops grip [seen 10297 p.111-124].
- Roofs come in three kinds:
  - a flat lid (10297: plate sandwich with mansard slopes round the edge and a skylight
    [seen p.265-284]);
  - plate panels on hinge plates (31139 [seen p.93-95]);
  - tall slope bricks for a stylised roofline (60316 [seen p.63]).

**Windows, doors, arches**
- Every set used moulded frames: 1x2x3 and 1x4x6 windows and doors, arched window frames in
  10297.
- Between frames, there are pillars of tall bricks (1x2x5, or stacks of 1x2) [seen 10297
  p.93-95; 60316 p.24-34; 31139 p.14-19].
- Above an opening, there is always a long plate or a long brick spanning frame and pillars
  [seen 10297 p.96 step 140, p.99-101; 60316 p.95].
- Brick-built arches appear inside 10297, as an arch under the stairs from curved arch bricks
  [seen p.46 step 52, p.73].

**Facade depth and detail**
- Sideways parts go on side-stud bricks set *into* the wall courses: lamps, signs, flower
  boxes [seen 10297 p.54, 237-238].
- Pilasters and columns stand on the wall top between windows and are capped by the locking
  course above [seen 10297 p.98, 159-160].
- Textured bricks (masonry profile, logs, round-corner bricks) give surface without depth
  [seen 31139 p.109; 10297 p.53].
- Jumper plates give half-stud offsets [seen 21044 p.30].
- In every case the decoration is tied back through studs of the wall itself; nothing hangs
  on a single stud.

**Interiors**
- Furniture sub-assemblies are tiny: 3-15 parts, most 4-8.
- They are built in a "side box" and set onto exposed studs of the floor. 10297's tile floors
  deliberately leave single studs or jumper plates where furniture will go [seen p.11-20, 39].
- They are placed *early*, while the walls are low, so hands can reach [seen 10297 p.22-24,
  38-39; 31139 p.25-28].
- A room reads with 4-8 pieces of furniture plus 2-4 wall details (a picture on a bracket, a
  lamp, a clock) [seen 10297 p.37-55; 31139 p.25-28].
- What is left open for hands:
  - the back of the room in 31139 and 60316;
  - the whole top in 10297, under a lift-off floor.

**Rigidity without a beam frame**
- Running bond.
- A plate lid each storey.
- Long plates under seams.
- Two-layer floors.
- Technic appears only as pins in Technic bricks for joining modular buildings side by side
  [seen 10297 p.9].
- I saw no pin-and-beam core in any of the four buildings, small or large.

**Very small scale**
- The base is a brick strip with side studs, clad in tiles.
- The ground is tiled, with open studs only where buildings stand.
- Buildings are cores of 1x1 bricks with studs on their sides, clad sideways.
- Repeated 1x1 bricks and plates read as storeys.
- Grille tiles read as glazing or ribs; transparent round bricks read as glass roofs.
- Bars and clips make lattice towers [seen 21044 throughout].
- Interiors disappear entirely.

## Patterns across sets, and what changes with size

- **In every set:** a flat base first (moulded baseplate, a single large plate, or built-up
  plates), and the walls stand on it. Furniture and details are separate small sub-assemblies.
  A plate or a long brick locks the top of the walls.
- **Small and micro (21044):** a solid core with sideways cladding; no hollow at all.
- **Medium (31139, 60316, 650-800 parts):** hollow shells.
  - 60316 uses tall moulded panels and pillars (few parts, fast).
  - 31139 uses real brick courses.
  - Both have rooms open at the back and storeys stacked or hinged on.
- **Large (10297, 3,000 parts):** full four-wall storeys that lift off. Plate-sandwich floors.
  Hinged angled wings. Furniture in every room.
- **Pin-and-beam core:** none in buildings of any size. Pins appear only to join separate
  buildings. A hollow box of running-bond walls under a plate lid is the building's
  equivalent of a core.

## Rules of thumb (with evidence)

1. **A plate lid over every storey.** Every storey ends with plates over all wall tops, or a
   continuous course of long bricks [10297 p.99-101; 60316 p.35-39]. Counter-example: 31139's
   upper storey is closed by roof panels on hinges instead [p.93-95], and its walls are tied
   by a ridge brick.
2. **A long part over every opening.** Every window or door opening gets a long plate or brick
   that spans both sides [10297 p.96-101; 60316 p.95].
3. **Corners alternate.** Corners alternate which wall runs through, or use L corner bricks
   [10297 p.25-26; 31139 p.46].
4. **Furniture early.** Furniture goes in when the walls are 1-3 courses high
   [10297 p.22-24, 38-39; 31139 p.25-28].
5. **Furniture on purpose-left studs.** Furniture sits on single studs left on purpose in a
   tiled floor [10297 p.11-20].
6. **Anything that opens is its own sub-assembly on two hinges.** Roof panels in 31139 have
   2 hinge plates each [p.93]. The house halves have 1 hinge plate [p.21]. Lift-off floors use
   no hinge at all.
7. **Angled walls ride on a swivel.** A non-square wall stands on its own plate strip, joined
   by a swivel hinge, and is then locked by the floor plate above [10297 p.31-32, 116].
8. **Hidden structure gets odd colours; ceilings get the ceiling colour**
   [10297 p.114-119, 116; 21044 p.46-52].
9. **Micro scale: core, then cladding.** A side-stud core clad sideways replaces a hollow
   [21044 p.37-52, 83-96].

## Playbook for a NEW hollow subject with an interior (house, shop, cabin, box with a lid)

### About 100 parts
1. Lay the base: one plate the size of the footprint (or two plates bridged by a long plate
   underneath). Parts: plate 6x8 / 8x8, plate 1x8 underneath.
2. Trace the footprint with one course of 1x2/1x4 bricks, leaving gaps for the door. Leave
   the back side open if the inside must be reachable.
3. Tile most of the floor. Leave 2-4 single studs where furniture will stand. Parts: tiles
   2x2, 1x2; jumper plate 1x2 (3794b).
4. Build 2-3 furniture blocks of 3-6 parts each (a table, a bed, a counter) and place them on
   the free studs now.
5. Raise the walls 2-3 more courses in running bond, alternating the corners. Set a door frame
   and one or two window frames; put pillars of stacked 1x2 bricks beside them.
6. Lay a long plate across the top of every opening.
7. Close the top with one plate the size of the footprint (the roof or ceiling), or with two
   plates whose seam is covered by a row of bricks. For a pitched roof, use 45-degree slopes
   stepped up the gable ends.
8. Add 2-4 details on side-stud bricks (a lamp, a sign).

### About 400 parts
1. Lay the base as a plate sandwich: long plates side by side, a crossing layer on top, a
   large plate on top of that. Parts: plates 2x12 / 1x12, plate 6x10 (3033), 8x16.
2. Lay the foundation course along the whole footprint, one stud thick, in a contrasting
   colour.
3. Lay a tiled floor pattern. Leave single studs and jumper plates where furniture and
   partitions will go.
4. Build furniture blocks of 4-12 parts each (4-8 per room) and place them while the walls are
   only 1-3 courses high.
5. Raise the walls in running bond (1x4, 1x6, 1x8). Weave corners with alternate courses or
   L corner bricks (2357). Set side-stud bricks (87087) into the courses wherever a lamp, sign
   or flower box will go.
6. Set moulded frames (window 1x2x3, door 1x4x6) between pillars of 1x2x5 bricks or stacked
   1x2s. Put a sill tile under each window.
7. Lock the storey: one continuous course of long bricks over all frames and pillars.
8. If there is a second storey or a lid, build it as a separate module: a two-layer plate
   sandwich with the ceiling colour underneath, a hole for stairs, and its own perimeter
   course. Set it on the wall tops so it lifts off.
9. Build the roof as separate panels:
   - a flat plate with curved slopes along the eaves and tiles as shingles, on 2 hinge plates
     each (2452/4275-4276);
   - or a flat lid with a slope border.
10. For any angled or curved wall, build it on its own plate strip joined by a swivel hinge
    (2429/2430). Curve corners with round-corner bricks (3063b). Lock the result from above
    with the next floor plate.
11. Finish with facade detail tied into the wall: pilasters on the wall top under the locking
    course, awnings on plates over doors, chimney or dome as a separate stacked sub-assembly.

## Part vocabulary by job

| Job | Parts (number checked in the LDraw library by description) |
|---|---|
| Base | Baseplate 32x32 (3811); Plate 6x10 (3033); Plate 1x8 (3460); long plates 1x12/2x12 (not checked) |
| Wall | Brick 1x2 (3004), 1x4 (3010); 1x6, 1x8 (not checked); Brick 2x2 Corner (2357); Brick 1x2x5 (2454a / 88393); Panel 1x6x5 (59349) |
| Lock and lintel | Plate 1x8 (3460); long bricks 1x6/1x8 (not checked); plates over the whole storey |
| Openings | Window 1x2x3 Pane (3854) with its frame (frame number not checked); Door 1x4x6 Frame (60596); Window 1x4x6 Frame (57894); Arch 1x4 (3659) |
| Sideways | Brick 1x1 with Stud on 1 Side (87087); Brick 1x1 with Studs on Four Sides (4733); Brick 1x4 with Studs on Side (30414); Brackets 1x2-2x2 (44728 / 99207) |
| Angle | Hinge Plate 1x4 Base/Top (2429/2430), identified from a drawing; Hinge Plate 1x2 with 3 Fingers / 2 Fingers (4275a/4276a, 2452); Plate 1x2 with Clip / Handle (92280 / 2540); wedge plates (not checked) |
| Joint between modules | Technic Brick 1x2 with Hole (3700) + Technic Pin (3673) |
| Skin and texture | Tile 1x2 Grille (2412b); Tile 1x8 (4162); Tile 1x2 (3069b); Brick 1x2 Log (30136); Brick 2x2 Corner Round (3063b); Slope 45 2x2 (3039); Slope Brick Curved 4x1 (61678); Slope Brick 75 2x1x3 (4460b) |
| Offset | Plate 1x2 with 1 centre stud, jumper (3794b) |
| Micro frame | Plate 4x4 with Open Centre 2x2 (64799) |

## What I could not find out, and what to look at next

- **Parts lists.** Rebrickable and LEGO's own page refused automated access, so set part counts
  for 10297 are [recalled], and several part numbers are matched from drawings only.
- **How hard floors grip.** The instructions do not say how many studs actually engage when a
  10297 floor sits on its walls. Measuring that would need the LDraw/LXF file of the set.
- **How 60316's jail block joins the station.** I saw it pushed up against the station
  [p.111-112] but not the joint itself.
- **Not read.** The rest of 10297's middle storey (pp 125-200) and 31139's alternative models.
  Booklet 2 of 31139 builds its base with no baseplate, a frame of long plates [seen p.3-4],
  which is worth a look as a second example.
- **Next.** A Friends house (for example 41730) for another medium hollow build with floors.
  Also an Ideas or Icons set with a hinged or opening building.
