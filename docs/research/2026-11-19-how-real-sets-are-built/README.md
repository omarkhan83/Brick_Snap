# How real sets are built: a study, and a draft guide for the AI builder

Written on 19 November 2026 by the lead's agent, as editor of eight research reports. The project's owner
noticed that many official LEGO® sets start from a core, often of beams and pins, that a botanical set did
it differently, "but they all start with a core". He asked for real sets to be studied across categories
and the result turned into a guide the AI builder can follow, "rather than us try and figure it out".

This file is the study. [`guide.md`](guide.md) is the draft guide. [`reports/`](reports/) holds the eight
reports, which are the evidence. With ten minutes, read "The short answer" and "What this means for
BrickSnap"; everything between them is the evidence, set out so that each claim can be checked.

## The short answer

**Yes, they all start with a core. But the core is usually not beams and pins, and at the sizes BrickSnap
builds today it almost never is.**

In every one of the 32 official sets whose instructions were read, the first thing built for the model is
the one assembly that everything else is then attached to. In the ten sets picked to be as unlike each
other as possible, this held 10 times out of 10. The nearest thing to an exception among the other 22 is
a bunch of loose flowers, where each stem is its own core.

There are five kinds of core:

1. **A flat base**: plates laid in overlapping layers, or one moulded chassis. Every vehicle, the ground
   of every building, a ship, a small spaceship.
2. **A block of bricks that have studs on their sides**, so that a flat panel can be pressed onto each
   face. Characters, sculptures and animals.
3. **A box of thin walls closed by a plate lid.** Anything hollow with an inside.
4. **A spine**: an axle, a bar or a chain of connectors. Plants, and anything long and thin.
5. **A frame of beams joined by pins.**

The frame of beams and pins is what every Technic set is. Outside Technic we saw it only where something
particular called for it: under two display cars of 1,458 and 2,336 parts, which are 40 to 44 studs long
and have suspension or a differential; as a hollow tower inside a 1,073-part character, carrying a head
on a joint; as the arm that holds a bird of about 834 parts in the air; and as the round drum inside a
608-part flower pot, which has to carry a skin facing outward all the way round. A ship of 1,264 parts,
an aeroplane of 2,083 and a building of about 3,000 had none. No set under 600 parts outside Technic had
one. The parts lists of 5,711 sets outside Technic agree: at most 3 in 100 sets under 350 parts contain
even ten beams; 6 in 100 at 350 to 500 parts; 17 in 100 at 500 to 750; about 42 in 100 above 1,500.

**For BrickSnap, at 60 to 500 parts: do not start from beams and pins.** Start from a plate base for
anything with wheels or a footprint; from a small block of side-stud bricks with panels for a creature, a
character or a sculpture; from a box under a lid for anything with an inside; from an axle or a bar for a
plant. The first three hold together by studs alone, which is the one kind of joint our checker can
already prove. At this size pins and axles appear only as joints: a wheel on its pin, a head that turns,
a stem.

## How the study was done

Eight researchers, each an AI research agent working alone for the lead's agent, wrote one report each.
Five studied a category from four or five instruction booklets. One, asked for by the owner, read ten very
different sets without seeing the others' work, and looked only for what holds in all of them. One
measured published parts lists, and the building order of official sets that the LDraw community has
drawn as files. One read what LEGO's designers and experienced builders have published. The editor read
all eight in full, compared them, and went back to the page pictures on two points where reports
disagreed.

That is 33 readings of 32 different sets (the 253-part parrot was read twice, by two researchers who did
not know of each other) and about 2,300 booklet pages (the reports' own page counts, added up). It is a
small sample, and the sets were chosen by the researchers, not drawn by lot.

**Pages were read from LEGO's own instruction files**, which the LEGO Group publishes free for every set.
Each researcher found the files through LEGO's building-instructions page for the set and downloaded a
handful, one booklet per file, under a plain client name. The pages were turned into small pictures, four
to nine pages to a picture, and read as pictures. So the shape and place of a part can be trusted; the
exact identity of a small part often cannot, and the reports say where.

**What could not be obtained.**

- LEGO's page refused plain scripted requests. Nobody disguised a client to get round that: the page was
  read with an ordinary page-fetch tool and the files then downloaded normally.
- No set's parts list. Rebrickable's set pages refused automated requests from the five category
  researchers. So a part number in their reports means "a part of this name exists in the LDraw library
  and its shape matches the drawing", not "this is the part in the set". (The numbers researcher used
  Rebrickable's published catalogue files, a different route, which its terms allow.)
- No reviews or photographs of builds. Two researchers took piece counts and sizes from Brickset.
- Three piece counts (marked † in the table) are recalled, not checked.
- No large booklet was read whole: the first third closely, the rest sampled.
- Several published sources refused automated reading and were left out. The books on building were read
  only as contents pages and one free sample chapter.
- The numbers researcher could not compare the community's building steps with the booklets.

**The ten questions** each researcher answered for each set: (1) the set, and how much of its booklet was
read; (2) what is built first, and what kind of core it is; (3) how the core is made strong; (4) how the
outside attaches to it; (5) what is built separately and attached, and what is repeated; (6) what moves,
and where its mechanism sits; (7) what is hidden inside, and in which colours; (8) which one part sets the
scale; (9) the order of the build; (10) the techniques used, in ordinary words.

**How each statement is marked** in the reports: [seen] in the instruction pages read, with the page or
step; [measured] from data files; [read] in a published source; [review] from a fan site; [second-hand],
another page's account of a source; [recalled], general knowledge that was not checked. Nothing in this
file or in the guide rests on [recalled] alone unless it says "unchecked".

### The sets

| Set | Name | Theme | Parts | Booklet pages read | Report |
|---|---|---|---:|---|---|
| 60312 | Police Car | City | 94 | 48 of 48 | vehicles |
| 60412 | 4x4 Fire Truck with Rescue Boat (the truck) | City | 301 | 68 of 72 | vehicles |
| 76914 | Ferrari 812 Competizione | Speed Champions | 261 | 80 of 92 | vehicles |
| 31146 | Flatbed Truck with Helicopter (the truck) | Creator 3-in-1 | 270 | 40 of 68 | vehicles |
| 10297 | Boutique Hotel | Modular Buildings | 3,066 † | about 120 of 296 | buildings |
| 31139 | Cozy House (main model) | Creator 3-in-1 | 808 | about 76 of 144 | buildings |
| 60316 | Police Station (the building) | City | 668 | about 48 of 168 | buildings |
| 21044 | Paris | Architecture | 649 | about 72 of 112 | buildings |
| 40674 | Stitch | BrickHeadz | 150 to 200, estimated | 44 of 44 | characters-and-sculptures |
| 40441 | Shorthair Cats (two cats) | BrickHeadz | 250 | about 68 of 76 | characters-and-sculptures |
| 10331 | Kingfisher Bird | Icons ‡ | about 834 † | about 72 of 88 | characters-and-sculptures |
| 75318 | The Child | Star Wars ‡ | 1,073 † | about 108 of 164 | characters-and-sculptures |
| 75328 | The Mandalorian Helmet | Star Wars ‡ | 584 | about 72 of 108 | characters-and-sculptures |
| 10311 | Orchid | Botanicals | 608 | 64 of 64 | botanicals-and-animals |
| 10280 | Flower Bouquet | Botanicals | 756 | 52 of 84 | botanicals-and-animals |
| 10309 | Succulents | Botanicals | 771 | 72 of 108 | botanicals-and-animals |
| 31129 | Majestic Tiger (main model) | Creator 3-in-1 | 755 | 84 of 132 | botanicals-and-animals |
| 31136 | Exotic Parrot (main model) | Creator 3-in-1 | 253 | 60 of 68 | botanicals-and-animals |
| 42133 | Telehandler | Technic | 143 | 64 of 64 | technic-and-frames |
| 42138 | Ford Mustang Shelby GT500 | Technic | 544 | about 99 of 112 | technic-and-frames |
| 42129 | 4x4 Mercedes-Benz Zetros Trial Truck | Technic | 2,110 | about 117 of 384 | technic-and-frames |
| 10317 | Land Rover Classic Defender 90 | Icons | 2,336 | about 126 of 312 | technic-and-frames |
| 10295 | Porsche 911 | Icons | 1,458 | about 72 of 268 | technic-and-frames |
| 75344 | Boba Fett's Starship Microfighter | Star Wars | 85 | 54 of 56 | universal-truths |
| 42147 | Dump Truck | Technic | 177 | 60 of 104 | universal-truths |
| 40646 | Daffodils | Botanicals | 216 | 20 of 20 | universal-truths |
| 76919 | 2023 McLaren Formula 1 Race Car | Speed Champions | 245 | 54 of 84 | universal-truths |
| 31136 | Exotic Parrot (main model), second reading | Creator 3-in-1 | 253 | 56 of 68 | universal-truths |
| 21256 | The Frog House | Minecraft | 400 | 54 of 92 | universal-truths |
| 71785 | Jay's Titan Mech | Ninjago | 794 | 66 of 140 | universal-truths |
| 60414 | Fire Station with Fire Truck | City | 843 | 84 of 356 | universal-truths |
| 31109 | Pirate Ship (main model) | Creator 3-in-1 | 1,264, all three models | 60 of about 194 | universal-truths |
| 10318 | Concorde | Icons | 2,083 | 84 of 296 | universal-truths |

† Recalled by the researcher, not checked against a parts list. ‡ The theme is general knowledge; the
report does not record it. Where a set has several booklets or models, the pages are those of the
booklet for the model studied; each report says exactly which pages.

## The five kinds of core

| Subject | About 100 parts | 250 to 800 parts | 1,000 parts and more |
|---|---|---|---|
| Vehicle | One moulded chassis, or one long plate | A spine of long plates, widened by a wide floor plate | Rails of bricks with holes, pinned, under a tray of plates (two display cars) |
| Hollow thing | Not read | A plate base, thin walls, a plate lid | The same, with storeys that lift off |
| Character, creature, sculpture | A small ring of side-stud bricks for the head; a plain stack for the body | A tower, ring or two-storey box of side-stud bricks; sections on ball joints | A cage of beams in one character; a head with a side-stud core of its own |
| Plant | A pot of stacked plates and bricks; a bar or axle as the stem | Axles and connector chains as stems; in one, a pinned drum as the pot | Not read |
| Machine | A compact pinned block round the mechanism | A ladder of doubled rails | A box round the motors, with ladders pinned on |

### 1. A flat base

**Seen in** all four vehicles, the ground of all four buildings, and five of the ten very different sets
(a small spaceship, a racing car, a fire truck, a ship, a block-world house). The 2,083-part aeroplane is
the same idea turned on its side: a wing of long plates stacked on edge.

**What it is.** Two of the vehicles (94 and 261 parts) start from one moulded chassis part that carries
the wheel mounts. The other two (270 and 301 parts) start from a spine, one plate 16 studs long with
wheel-pin plates under its ends, then widened by a wide plate laid across it. Buildings start from a
baseplate, one large plate, or a ladder of long plates crossed by another layer.

**How it is made strong.** The next layer spans the seams of the one below (all four vehicles). Several
bases are turned over so that plates can go on underneath as well.

**How the outside goes on.** Mostly on studs pointing up. But in each vehicle an end face (lights, grille,
bumper) is built flat on a plate and pressed onto bricks with studs on their sides, which are fixed into
the floor layer (4 of 4). The base is finished within about the first fifth of the parts (the
researchers' estimates).

### 2. A block of side-stud bricks, with a panel on each face

**Seen in** the three smaller character and sculpture sets, the head of the large character, both
animals, the torso of the mech, and at tiny scale inside the towers of the city skyline.

**What it is.** The smallest seen, in a kitten of about 120 parts, is a ring of eight 1 x 1 bricks with
side studs round one plain brick, two layers high: three studs square, with studs facing out all round. A
cat of about the same size and a figure of 150 to 200 parts use the next size up: twelve taller bricks
with four side studs each, ringed round a 2 x 2 column, four studs square. At 584 parts the core is a
hollow box of two storeys: columns of side-stud bricks and brackets on a 6 x 6 plate, each storey closed
by a plate. A 253-part bird has a tower of side-stud bricks. A 755-part tiger has a closed ring with
side-stud bricks at its ends, and is built in sections joined end to end by ball joints.

**How the outside goes on.** Each face gets its own flat panel, built with its studs up, then turned on
its side and pressed onto the core (all five character sets). Small figures round a panel with curved
slopes. Large ones stack plates in shrinking outlines, like contour lines, and keep curved slopes for the
lines that catch the eye. Where panels meet, small slopes soften the corner or a strip of plates closes
it. The skin is thin: one plate to half a stud on the small figures, two to four plates on the large
ones. The core is about two thirds to three quarters of the head's width in the small figures, and about
half the model's width in the large ones.

**A head always gets a core of its own**, even when the body does not: the kitten's body is a plain stack
with one bracket. Nothing smaller than that kitten was read.

### 3. A box of walls under a lid

**Seen in** three of the four building sets (668, 808 and about 3,066 parts) and two of the ten (400 and
843 parts).

**What it is.** A base, one course of bricks tracing the whole footprint, walls one stud thick, and a
layer of plates over the wall tops of every storey. The ring of walls and its lid are the structure.
There is no frame at any size: the only Technic parts are two pins that join the large building to its
neighbour, and two upright beams that tie the walls of the 843-part station.

**How it is made strong.** Bricks overlap from course to course. Corners are woven. A long plate or brick
crosses the top of every opening. Every storey ends with plates over all the wall tops, or with an
unbroken course of long bricks.

**Inside.** Furniture is built apart, in units of 3 to 15 parts, and set on single studs left bare in a
tiled floor. It goes in early, while the walls are one to three courses high. Hands get in through an
open back (the two medium sets) or by lifting a storey off (the large one), where each floor is two
crossed layers of plates resting on the wall tops.

**Small buildings are not hollow.** The landmarks of the 649-part skyline are solid cores of side-stud
bricks, clad sideways: kind 2.

### 4. A spine

**Seen in** all three Botanical sets and the Daffodils; in the parrot's perch; in the masts of the ship.

**What it is.** A stem is one axle up to 32 studs long, or a chain of tube-shaped connectors on short
axles. A curve is a chain of connectors that each hold a fixed bend. A small plant is a bar or an axle
standing in its pot, with round plates that have bar handles threaded onto it.

**How it is made strong.** By the axle's own stiffness. A stem that must stand by itself gets a hidden
stake of two 32-long axles tied together (the orchid). The bouquet has none, because it stands in the
buyer's vase.

**How the outside goes on.** Petals and leaves sit on clips that grip bars, in tiers, each tier turned
half a step from the last. Flowers plug onto stems on axles. One leaf or petal is built once and repeated
(8 to a tier; about 40 in one flower). Organic shapes are borrowed parts: the booklets' own notes point
out car bonnets, shoulder armour and claws used as petals and leaves. In the Daffodils no stud carries
the structure at all.

### 5. A frame of beams and pins

**Seen in** all four Technic sets, under the two display cars, and in three special places.

**In Technic** the frame is the model. At 143 parts it is a compact block closed round the mechanism, with
no long rails. At 544 it is a ladder of two rails, each a pair of 15-hole beams pinned side by side. At
2,110 it is a box round the motors with separate ladders pinned on front and rear, and the only diagonal
braces seen in the study. The mechanism is built first and the frame round it (3 of 3 in the frames
study). Panels go on with two pins each.

**Under the two display cars** (1,458 and 2,336 parts) the frame is made of bricks with holes, not of
studless beams: two such bricks pinned side by side for each rail, an open-centre brick across the ends,
and then plates laid over everything, which is what stops the rails turning on their pins. The body
above is ordinary stacked building, with no pin joining it to the frame. The frame is only about 6 to 10%
of the parts (estimates).

**The three special places**: a cage of upright beams and open frames inside the 1,073-part character; a
frame and a slanting arm of beams in the stand of the bird of about 834 parts; a drum of sixteen upright
beams pinned round stacked round plates inside the 608-part flower pot.

**What makes a frame rigid** is the same everywhere: every part that must not move has two fixings or
more (5 of 5 sets in the frames study). A part on one pin is a hinge.

**Smaller Technic jobs** turn up in ordinary sets of every size: an axle as a spine, a pin as a pivot, a
gearbox, a pair of beams as stiffening. Those are joints and stiffeners, not cores.

## What holds in every set

These tallies are from the ten very different sets (85 to 2,083 parts; 592 pages read of roughly 1,410,
the booklets' lengths added up). They are one researcher's reading, so they are the best evidence here
for "everywhere" and weak evidence for any one category. The last column says what the other 22 sets add.

| What holds | Tally in the ten | In the category studies |
|---|---|---|
| The first thing built is what everything else is attached to | 10 of 10 | Holds; loose flower stems are the edge case |
| Things are attached in this order: core, body and skin, then limbs, wheels, wings, roof, and last whatever sticks out or is held | 10 of 10 | Holds; wheels last in 4 of 4 vehicles |
| A repeated unit is built once and marked "2x" or "4x" | 10 of 10 | Holds in every study |
| At least one sub-assembly is built apart and then joined | 10 of 10 | Holds in every study |
| Each moving thing has one joint, of a kind made for moving, on a solid assembly | 10 of 10 | Holds |
| What is fragile or held goes on last; what is inside goes in before what covers it | 10 of 10 | Holds; furniture before the walls close |
| Above about 800 parts the model is several big modules joined late | 4 of 4 | Storeys, tiger sections, truck sub-frames |
| A long thin part has a stiff spine | 8 of 8 that have one | Stems, stand arms, masts |
| A left- or right-handed unit is drawn out for both hands, never "2x" | 6 of 6 that have one | See "Where the reports disagree", point 5 |
| Shaped surfaces are attached sideways as well as on top | 7 of 7 stud-built sets with a shaped skin | 5 of 5 characters; an end face in 4 of 4 vehicles |
| Every seam in a layer that carries weight is covered by a longer part | 9 of 10 (the tenth has no studs) | 4 of 4 vehicles; every building |
| Parts nobody will see are a different, often bright colour | 8 of 10 | Bright in most; grey and black in Technic and under the display cars |

The booklets themselves share habits too (all 10 of 10 unless noted): every step lists exactly the parts
it adds; a step adds only a few kinds of part, and many parts at once only when they are identical; a
rotate sign appears whenever the model must be turned; a part that would be hidden gets a zoomed drawing.
Nine of the ten sets average 2 to 4.8 parts a step.

## What looked universal and was not

- **"Start with a base as long as the model."** 6 of 10. A flower starts with its head, a mech with its
  torso, the aeroplane with a wing standing on edge.
- **"Build from the bottom up."** 6 of 10. The mech goes torso, hips, legs, feet.
- **"Finish the core, then put on the skin."** Clearly so in only 4 of 10. Small sets put skin and core
  on together: the 85-part spaceship has outer slopes by step 6 of 42.
- **"Large models have a core of beams and pins."** Not the 1,264-part ship or the 2,083-part aeroplane.
- **"Symmetrical halves are mirror images."** The mech's legs are designed to be identical and built
  "2x".
- **"Hidden parts are a contrasting colour."** The Daffodils' hidden bars match their petals.
- **"Every seam is bridged; everything joins by studs."** The Daffodils again: stem pieces join end to
  end, and nothing in the model relies on studs.
- **"Steps add one to three parts."** One step of the Daffodils adds 13. The rule is few kinds a step.
- **"A moving part needs two connections."** It needs one: an arm on one ball joint, a head on one bar.
  Fixed joins use several; joins meant to move or come off use one.
- **"Minifigures are built first."** Only where there are any (6 of 6).

## What changes with size

| Size | What the sets read do |
|---|---|
| Under about 150 parts | One simple core: a moulded chassis, a small ring of side-stud bricks, a compact pinned block. Skin and core go on together. Studs only, but for wheel pins and a clip or two. |
| 150 to 500 | A built-up core: a plate spine with a wide floor plate, a tower or ring of side-stud bricks. More is built sideways. Left and right units are built twice. The build is split by region. |
| 500 to 1,000 | Hollow cores: a two-storey box of side-stud bricks (584), a ring with sections on ball joints (755), walls under a lid. The first pinned structures, each for a particular job (608, about 834, 843). In Technic, a ladder (544). |
| Above 1,000 | Several big modules joined late. A head becomes a model of its own, with its own core. Frames under long cars with suspension; none in a ship, an aeroplane or a building. |

## The numbers that matter

All from `reports/numbers.md`: parts lists of 5,935 sets from 2015 onward (5,711 outside Technic), and the
building order of 49 official models drawn by the LDraw community, of which 42 have usable steps (36
outside Technic). Parts-list figures are from the Rebrickable catalogue (see "Credits and limits of
use"). Parts were sorted into jobs by their names, which counts kinds of part and not how a part is used.

**Beams and pins against the size of the set** (5,711 sets outside Technic)

| Parts in the set | Sets | Median share of parts that are beams, pins, axles, connectors or bricks with holes | Sets with ten or more beams |
|---|---:|---:|---:|
| Under 100 | 1,909 | 0.0% | 0% |
| 100 to 200 | 859 | 1.9% | 3% |
| 200 to 350 | 1,000 | 2.5% | 2% |
| 350 to 500 | 491 | 5.2% | 6% |
| 500 to 750 | 555 | 5.5% | 17% |
| 750 to 1,000 | 323 | 7.0% | 22% |
| 1,000 to 1,500 | 294 | 7.8% | 32% |
| 1,500 to 2,500 | 165 | 5.3% | 43% |
| Over 2,500 | 115 | 4.5% | 42% |

The theme matters more than the size. At 750 to 1,000 parts, 55% of Ninjago sets (22 sets) and 48% of
Star Wars play sets (33) have ten or more beams, against 5% of City sets (43) and none of the
Architecture sets (4). No BrickHeadz set of any size has (196 sets). Botanicals are different in kind: on
average 17.1% of their parts fall in this class (53 sets), but they are axles and connectors used as
stems, not beams. And the habit is fading: among sets of 500 parts and more, 36 to 45% had ten or more
beams in 2015 to 2017, and 18 to 26% in 2021 to 2026.

**What a set of our size is made of** (mean share of parts, all themes except Technic; the two sums are
ours)

| Kind of part | Under 150 parts (2,347 sets) | 150 to 500 parts (1,912 sets) |
|---|---:|---:|
| Plates | 13.7% | 17.9% |
| Tiles | 11.3% | 12.4% |
| Round bricks, round plates, cones | 12.2% | 10.1% |
| Slopes | 6.0% | 6.4% |
| Curved slopes | 5.5% | 6.1% |
| Plain bricks | 4.9% | 6.7% |
| Brackets and bricks with side studs | 5.1% | 6.2% |
| Clips and bars together | 9.7% | 7.0% |
| Hinges, turntables and ball joints together | 2.5% | 2.0% |
| Beams, pins, axles, bricks with holes | 4.8% | 6.2% |

A set of 100 to 150 parts uses a median of 45 different parts in 13 colours (435 sets); one of 250 to 400
parts, 89 in 18 colours (807 sets; all themes except Technic and Classic). The AI's builds in the earlier
study, with 33 to 35 kinds of part in 78 to 102 parts, are in the range of real sets of that size (29
kinds at 50 to 100 parts, 825 sets).

**The order of a build** (official models with usable steps)

| Measure | Value | Models |
|---|---|---:|
| Plates among the first tenth of the parts placed | 30% in models under 500 parts, 27% in larger ones; 21% and 19% in the last two thirds | 18 and 18 |
| Slopes, curved slopes and wedges in the first tenth | 10% and 10%; 21% and 12% in the last two thirds | 18 and 18 |
| Studded parts facing sideways, by third of the build | 10%, then 26%, then 32% (medians); 24% over a whole model | 36 |
| Studded parts placed upside down | Median 0%; no model above 6% | 36 |
| Where wheels go on | The first at 62% of the way through; typically at 86% | 26 |
| Where hinges first appear | 20% of the way through | 26 |
| Parts placed inside a sub-assembly | 66% in models under 500 parts, 72% in larger ones | 18 and 18 |
| Size of a sub-assembly | Median 10 parts in the smaller models, 6 in the larger | 116 and 1,011 sub-assemblies |
| Parts added by one step | Median 2 | 36 |

Is there a start of beams and pins? Among the 32 models outside Technic that contain any such parts,
they are at least twice as common in the first fifth of the build as in the whole in 6 models, and half as
common or less in 13. Two of the six are tiny shares (7% against 1%, 3% against 1%). The clear cases are
a 1,167-part car and three small models of 73 to 109 parts. Nobody read those three booklets, so what
their Technic parts hold is not known; it is the one sign in the whole study of pinned parts at the very
start of a small model.

## What LEGO's designers have said

Sources are numbered as in the list at the end of this file.

- **There are rules about connections.** "The LEGO Group has internal design rules for connecting LEGO
  pieces together for stability and to avoid unnecessary stress" [S2]. The only detailed public account
  is a talk of 2006 by a LEGO designer, Jamie Berard [S1]: a connection is ruled out if it squeezes,
  bends or holds a part open. His cases are ones a checking program can test: a pin must be pushed fully
  home, into a hole made for it; a click hinge must sit on a click, in steps of 22.5 degrees; one stud may
  go into one Technic hole, never several; nothing is wedged between studs. His general principles
  include "Support Everything!" and "Can one brick replace the need for 5?".
- **Every model is built through and heat-tested.** Since a set of 2002 that damaged its own parts, each
  model is built together by designers, engineers and the instruction writers, in a review that can last
  "up to 2 or 3 days", and then heat-tested [S1].
- **Hinges carry only so much weight.** Of a large dinosaur its designers said the first version "is
  actually too heavy for LEGO hinges" and "was already unable to stand!" [S12].
- **The steps are designed by a separate team**, which "decides on the individual steps, how many pieces
  to add in each step", and builds the model "many, many times in different ways" [S14]. No number of
  parts a step is published.
- **Hidden parts are bright on purpose**: "to make the building experience better", by contrast with the
  parts round them and by making parts quicker to find, and not to use up stock (a former LEGO designer)
  [S13].
- **Plants.** "The 32 module, Technic axle just became the go-to part" for stems; a flower needs only "a
  simple core that will just hold it all together" (the designer of the Flower Bouquet) [S11].
- **Starting a model.** Designers "build sketch models that are buildable in LEGO bricks" to sell an idea,
  and the set is then worked out from the sketch [S15, S17].
- **LEGO's own model builders**, on large sculptures of stacked bricks (a 1998 study written with them)
  [S5]: use the largest bricks that fit; turn the bricks in alternate layers; cover every seam, with the
  covering brick centred on it; make a large model hollow, with a shell two to six bricks thick. Later
  research found a shell two studs thick usually enough, and gives the test for a weak spot: a part whose
  removal splits the model in two [S6].
- **From experienced builders, not from LEGO**: two studs sideways equal five plates of height [S4, S23];
  a brick with holes plus two plates puts the next row of holes exactly two holes higher [S18]; a slanted
  wall or beam must span a whole-number triangle such as 3-4-5 [S4, S18], which the designers of the
  Boutique Hotel say they used [S22].
- **What nobody has written down.** That one starts from a core: no designer says it, the booklets show
  it. How many parts go in a step. When a studded set gets a frame of beams. Any figure for how strong a
  model has to be.

## Where the reports disagree

1. **Is a core of beams and pins a matter of size?** The characters report says it comes "from about 800
   to 1,000 parts". The frames report says above about 32 to 40 studs of length, or with suspension or
   steering. The ten very different sets say not even at 2,083 parts. The parts lists say a minority at
   every size, and a different minority in each theme. *I believe the parts lists for how common it is
   and the booklets for what it is for: it follows the job (a long chassis with mechanisms, a load held
   out on an arm, a round skin, a tall hollow body), not the part count.* What the booklets pin down for
   vehicles: no frame at 20 studs long or less (four vehicles), a frame at 40 to 44 studs (two), and
   nothing read in between.
2. **Are models built from the bottom up?** The numbers report says "mostly": the order of building rises
   with height in 27 of 42 models. The ten sets say 6 of 10. LEGO's instruction writers say they "start
   building from the ground up" [S14]. The characters report calls the two-cat set bottom-up, while its
   LDraw file shows a build that grows outward from the middle more than upward. *Bottom-up is the usual
   way for things that stand on a base and is strong only in buildings and towers. The rule is core
   first.* A core goes up from its base; then skin goes on all round; a stand may come last.
3. **Flower heads or stems first?** The numbers report says of the Flower Bouquet that "the stems are
   built first". The botanicals report saw in the booklet that each head is built first, then its stem.
   The numbers report's own figures agree with the booklet: petals and clips fill the first tenth of the
   file, and later parts sit lower. *Heads first.*
4. **How the parrot's wings and tail are attached.** The set was read twice. One reading has each wing
   on a single pin and the tail on a click hinge; the other speaks of "wing clips" and a tail that "clips
   on". *I looked at the pages: the wing hangs on one pin through a round plate; the tail has two
   hinge-type plates at its root, and at that size of picture one cannot tell a click hinge from a clip.*
5. **Are mirror-image units ever marked "2x"?** The ten sets say never (6 of 6): both hands are drawn.
   The vehicles and frames reports describe "mirrored" units marked "2x". *I looked at the police car:
   its two body sides are one identical unit built twice and turned round. So the rule stands, and
   "mirrored" in the category reports often means "the same unit on both sides".* For a builder with a
   mirror tool the difference is small.
6. **Hinges in small vehicles.** None in the four vehicles of the category study. But the 85-part
   spaceship among the ten has its canopy on a clip hinge, the 1,458-part car hangs its doors on hinge
   bricks, and a plain hinge brick is in 18% of non-Technic sets. *"No hinges" is true of four sets and
   is not a rule.*
7. **Finish the core before the skin?** The characters report says so. The ten sets say it is clear in
   only 4 of 10, and that small sets put both on together. *At our sizes, start with the core but do not
   wait for it to be finished.*
8. **Hidden colours.** Bright in the vehicles, characters, plants and animals. Grey and black in Technic
   and under the display cars. Matching in the Daffodils. *Colour inside is free. Bright is a kindness to
   the person building [S13].*
9. **Parts in a step, in Technic.** The booklets show one to six (and 2 on average in the Technic set
   among the ten). The LDraw files give about 6. *The booklets: the files' steps are their authors' own.*
10. **Wheels last?** Yes in every booklet read. But two small models among the LDraw files begin with
    wheels, and the files put turntables at the very start (5 models) where the one booklet with a
    turntable fits its ladder last. *Usual, not universal.*
11. **The angle of the Boutique Hotel's corner.** The buildings report calls it 45 degrees, by eye. Its
    designers say they used a 3-4-5 triangle [S22], whose sharper angle is about 37 degrees. *The
    designers; both agree that the wall turns on a hinge and is locked by the floor above.*
12. **Slips inside reports.** The numbers report says 41 models had usable steps in one place and its
    tables say 42 (used here, so its "27 of 41" is 27 of 42); it calls the first hinge the 15th
    commonest joint part where its table has it 14th; it gives 11 as the median size of a small model's
    sub-assembly in the text and 10 in the table. The universal-truths report says its ten sets include
    "none of the eight sets studied by the others": the others studied 23, and the parrot is in both.
    The editor's notes at the head of those two reports flag the main ones.
13. **Published sources disagree among themselves** on nine points, listed in section 7 of the
    written-knowledge report. The one that matters to a checker: how far a Technic hole sits from the
    line of a side stud (0.12 mm in the LEGO designer's slides; 0.1 or 0.2 mm elsewhere).

## What the study cannot tell us

- **Whether any of this makes an AI's models better.** Nothing here has been tried in a build.
- **Why, and how strong.** Instructions show what was done, not what would have failed. No joint was
  tested and no connection counted.
- **Much beyond 32 sets.** They were chosen by the researchers, date from 2019 to 2024, and most were read
  in part. The parts lists are wider (5,935 sets) but say nothing about how parts are joined.
- **Our own sizes are thinly covered.** Under 150 parts: one car, one spaceship, one Technic machine, two
  small figures. No hollow building under 400 parts. No creature between 253 and 584 parts. No studded
  vehicle between 301 and 1,458 parts.
- **Exact parts.** No part number was checked against a set's own list.
- **Shares.** "A fifth of the parts" and the like are estimates from counting steps.
- **The building order in the LDraw files** is their authors' reproduction of the booklets. Nine files
  name their steps after the booklet's; the rest were not checked. Few are newer than 2022.
- **Reasons.** Several reasons the reports offer (why a car is eight studs wide, why beams come in odd
  lengths) are recollection and are left out here.

## What this means for BrickSnap

### For the AI builder

**What it should be told.** Its instructions today say: build "a sturdy core of bricks and plates that
holds everything", "from the ground up", then the skin. The study agrees with the first words and
corrects the rest.

- *Core first* is right (10 of 10). *From the ground up* is not a rule (6 of 10).
- The core is not just sturdy. It is chosen for the subject, and its job is to offer places to attach
  to: side studs on every face that will carry skin.
- The skin is not laid on top of a stack. It is flat panels, built apart and pressed on sideways. This
  is the largest difference between how sets are built and how a builder that thinks in stacks works: in
  the official models measured, a quarter of the studded parts face sideways (median 24%, 36 models).
- Build apart and repeat. In those models two thirds of all parts are placed inside a sub-assembly.

**In what form.** Not as one long text. The builder's instructions are about 2,000 words already, and the
whole guide is 2,500 more. The proposal: the twelve rules (about 500 words) join the standing
instructions; the planning step picks one playbook (125 to 180 words) for the subject and size, or none;
the parts table is there to be asked for. Six of the rules carry a figure from the numbers report (how
rare a core of beams is, when wheels go on, how much is built in sub-assemblies, how much faces
sideways, how many parts go on in a step, how many kinds of part and colours a set has), and two
playbooks carry one each. The playbooks are separate on purpose, so that each can be
tested and dropped on its own. The earlier study showed that the AI already does some of this unasked
(eyes on side-stud bricks, a wing built once and mirrored, wheels on pin plates), so the gain may be
smaller than the study makes it look. Only the test can say.

**What it lacks to follow the guide.** A way to build a group of parts flat, as a little model of its
own, and then attach the group by one connection. Today it can place a part sideways onto a side stud,
one part at a time. Whether that is enough is a side question of experiment 1.

**What the checker covers, and what it would have to learn.**

| Core or joint | Where the study found it at our sizes | Can the checker confirm it today? |
|---|---|---|
| Plate base; block of side-stud bricks with panels; walls under a lid | Vehicles, characters, sculptures, hollow things | Yes: they are stud joints. It does not yet judge them: it does not flag an uncovered seam or a section hanging on one part |
| A wheel on a wheel pin | Every vehicle | Yes, as a proven module |
| A roof or lid that lifts off two studs | 3 of 4 small vehicles; the storeys of the large building | The studs, yes. It has no way to say "this comes off" |
| A clip on a bar | Every plant; tails, ears, bumpers, a canopy | No: listed as "not checked" |
| A pin or an axle in a hole, as a pivot | A reel, a wing on one pin, a head on an axle | In part: a joint declared on a Technic pin is accepted about the pin's own line; that the pin sits in a real hole is not checked |
| Ball joints and click hinges | Posable animals and figures of 250 to 800 parts | No |
| A frame of beams and pins | Nowhere at our sizes outside Technic | No |

The task file asked whether confirming a pin in a hole should be the checker's next step, if cores of
beams and pins matter at our sizes. They do not. The study points to this order instead:

1. **Judge stud-built cores**: uncovered seams, and sections that hang on a single part. This needs
   nothing new from the parts library and serves three of the four cores we need.
2. **The clip on a bar.** Clips and bars together are about a tenth of the parts of a set under 150
   parts, against about one in a hundred for hinges, and without them no plant can be checked at all.
3. **A pin or an axle in a hole**, as a pivot.
4. **Ball joints and click hinges.**
5. **Whole frames** last, and only if BrickSnap comes to build machines, or models of 600 parts and more.

For 3 to 5, the frames report lists what a program must know: the spacing of holes; which holes are round
and which are cross-shaped; a pin's length against the thickness it passes through; both ends seated; and
that anything held by one round pin will turn. LEGO's published rules add: a pin goes fully in, and at
most one stud goes into a Technic hole.

### For the converter

**What real sculptures at our size do.** A character or creature of 120 to 800 parts is a core with a
flat panel facing outward on each side (all five sets of that study, and both animals). The converter
stacks parts with their studs up, from the ground, and shapes the top and now the undersides.

**The converter's way is not wrong; it is a method for a different size.** It is how LEGO's own model
builders make large sculptures: the 1998 study describes hollow shells of stacked bricks, the largest
bricks that fit, turned in alternate layers, every seam covered. That is our solver. At 12 to 16 studs
across, the sets switch method. My reading of why, from the geometry and the booklets together: a part
turned on its side steps the surface by one plate, 0.4 of a stud, where a stack steps it by a whole stud;
and a curved slope can then face any way.

**And small figures do not follow the true shape.** They turn the subject into a box with rounded faces.
The converter is asked for the opposite: to stay true to a 3D model. That difference will not go away.

**What it would take** for the converter to build a core and panels by itself:

1. A new kind of thing in a model: a group of parts with its own "up", joined to the core. Today a part
   stands upright, or is a one-stud detail on one side-stud brick. This changes the shared types, the 3D
   view, the pictures, the booklet and the parts list.
2. A way to split any shape into a core and five or six panels, and to decide what happens where panels
   meet. The sets do this by eye, differently every time.
3. A second grid. Sideways, two studs equal five plates, so a panel's cells do not line up with the
   core's. Each panel has to be measured from the shape in its own frame.
4. A solver that places rows of side-stud bricks where panels mount, keeps the space in front of them
   clear, and still proves the core holds. Today it does this for one stud at a time.
5. The solver and the finishing pass run again inside each panel, which is a small studs-up model whose
   ground is a face of the core. This part is reuse, and is the encouraging one.
6. Proof that each panel is held and that neighbours do not collide. The free builds' checker, which
   reads the parts' real shapes, could give it.
7. A new way to score likeness, since today's scorecard compares cells on one grid.

That is most of a second engine. **What should not be attempted:**

- Automatic panels all round, for any shape. The corners are unsolved design, the gain is unknown, and
  the AI builder already does this kind of work part by part with a checker behind it.
- A frame of beams, limbs on ball joints, or storeys that lift off, in the converter. Those belong to
  free builds.
- Placing parts upside down. Official models barely do (median 0%; never above 6%).
- Rings of side-stud bricks in place of the solver's interlocked core. The sets put side-stud bricks
  where a panel mounts, and plain filler everywhere else.

**The smallest step that would show whether it is worth it** needs no new engine: take one model the
converter has already made, replace one face by hand with a row of side-stud bricks and one flat panel,
and ask a blind judge (experiment 4). One face is also what the smallest sets do: one face panel on the
head of a 120-part figure; an end face on a 94-part car.

**If that works, the next step is mounts, not panels.** Let the solver leave a patch of side studs, with
clear space in front, wherever the designer asks for a face, and let the designer say what goes on it.
That extends an accepted decision (one sideways detail on one side-stud brick) and replaces nothing. It
is also the split the sets use: a hidden core that software can prove, and a face that someone designs.
The duck of the earlier study, the solver's body with features rebuilt by the AI on side studs, already
had this shape.

**One line of the vision is out of step with the sets.** The ladder of ambition puts "sideways building"
at level 5, expert and long term. In the sets read it is there from the smallest: 7 of 7 shaped,
stud-built sets among the ten, an 85-part spaceship included. If the mock-up shows a gain, sideways faces
belong at level 2. That is the lead's document to change; this is a note.

### For moving parts

**What the four small vehicles do** (94 to 301 parts). No hinge part in any of them. Wheels push straight
onto a pin (4 of 4; none has an axle through a brick). What opens is a roof or canopy that rests on two
studs and lifts off (3 of 4). One also has cupboard parts with their own small doors and a hose reel on a
pin; one has a trailer coupling that turns on a pin. The wheel mounts go on in the first steps and the
wheels last (4 of 4).

**It is four vehicles, not a law** (see point 6 above). What the ten sets do say, 10 of 10, is that each
moving thing has one joint, of a kind made for moving, on a solid assembly.

**For the movement work** (`docs/tasks/movement-first-models.md`):

- "Mechanics first" matches what was seen. In Technic the mechanism is built first and the frame round it
  (3 of 3). In studded vehicles the mechanics are the wheel mounts, placed in the first steps, with the
  wheels themselves last.
- The task's target, a car that rolls and opens its doors and hood, asks for more than these cars of 100
  to 300 parts do. The set-like default at that size is: the wheels turn and the roof lifts off. Hinged
  doors are better kept as something a person asks for.
- A part that lifts off is the cheapest moving thing to prove, because it is only studs: held by two to
  four of them, by nothing else, with nothing above it. The checker has no word for it yet (experiment
  5).
- After wheels and lift-off, the joint to prove next is the clip on a bar (a canopy, a tail, an ear, a
  leaf), ahead of ball joints. The task's notes already list it as a follow-up.
- LEGO's designers warn that a heavy part on a hinge droops [S12]. How strong a joint is remains
  something the checker lists and does not judge.

### For interiors

The buildings study gives a method, and it is not "hollow out the shape":

1. Decide how the inside will be seen: rooms open at the back (the sets of 668 and 808 parts), or storeys
   and roofs that lift off (the large one).
2. Tile the floor, leaving single studs where furniture will stand.
3. Build the furniture apart, in units of 3 to 15 parts, most of them 4 to 8. A room reads with 4 to 8
   pieces of furniture and 2 to 4 details on its walls.
4. Put the furniture in while the walls are low. Then raise the walls one stud thick, cross every opening
   with a long part, and close the storey with a lid of plates.

For BrickSnap this is work for the AI builder, since it starts with decisions (what is in the room, how
one looks in), and the workshop's fill tool can already make a hollow box with walls one stud thick.
"Furniture early" matters to the person who builds the model with their hands, so it belongs in the order
of the building steps we hand out, not only in the order the AI works. Two cautions: no hollow building
under 400 parts was read, so the 100-part playbook is scaled down, not observed; and at very small scale
the sets do not attempt an inside at all.

## Experiments to run next

Each is small. Those that need AI runs spend the owner's subscription and need his yes first.

1. **Does the guide help the AI builder?** (8 AI runs.) Four subjects of about 100 parts, one for each
   stud-built playbook: a car, a sitting animal, a potted plant, a small room with a lid. Build each twice
   from the same sentence: with today's instructions, and with the rules and the one playbook added. The
   earlier study's runs cost about $4 to $8 each at list prices. Compare the checker's report, the part
   count, the time, and a blind judge's choice from pictures. *Confirms:* the judge prefers the guided
   build in at least three of four, with no more left wrong or unchecked. *Kills:* no preference, or
   guided builds that are slower and leave more unchecked. Decide playbook by playbook. Side question:
   can the builder make panels with today's tools?
2. **How far are the builds we have from the rules?** (No AI.) Take the eight AI-built models kept from
   the earlier study and measure what was measured in official models: the share of studded parts facing
   sideways, the share of parts in repeated groups, uncovered seams, sections hanging on one part.
   *Confirms that the guide has something to teach:* clear gaps on rules the sets keep 10 of 10. *Shrinks
   the guide:* the builds already keep them.
3. **Does our checker pass an official set?** (No AI.) Run the free builds' checker on the community's
   LDraw files of two or three small official sets built with studs only, a BrickHeadz figure for one.
   *Confirms:* no false problems; and its list of "not checked" joints, by kind, says which joint to
   prove first. *Kills trust in the checker for guide-style builds:* it reports problems in a model that
   is on sale, most likely at sideways joints. Fix those before experiment 1.
4. **Is one sideways face worth it in the converter?** (No AI to build; a judge to compare.) Take a
   converted sample at 16 studs: the cat's head, or the car's nose and tail. By hand, with the workshop's
   placing tool, replace one face with a row of side-stud bricks and a flat panel, as the guide describes.
   Check it with the free builds' checker and picture both versions from the same place. *Confirms:* a
   blind judge prefers the panel version on at least two models of three, the checker passes it, and the
   part count rises by no more than a tenth. *Kills:* no clear preference. Then the converter stays
   studs-up and sideways work stays with the AI builder.
5. **A roof that lifts off, as a declared moving thing.** (No AI.) On one of the AI-built cars, by hand,
   rest the roof on two studs, and have the checker say "lifts off" when a group is held by at most four
   studs, by nothing else, and has nothing above it. *Confirms:* it says so for the two-stud roof and
   refuses a roof locked by a plate across its edge. *Kills:* it cannot tell such a group from a fixed
   one reliably.
6. **A clip on a bar as a proven joint.** (No AI.) Prove one clip plate on one bar part as a module, as
   the wheel and hinge modules were proved, and rebuild one leaf of the existing sunflower on it by hand.
   *Confirms:* the checker counts the leaf as joined and says how far it swings. *Kills:* the parts
   library does not record enough of a clip's shape to prove its grip, and plants stay "not checked".
7. **Fill the two gaps that matter most.** (Reading only.) One creature of 300 to 600 parts and one
   hollow building of 100 to 250 parts, from their booklets. *Confirms the playbooks:* a core of
   side-stud bricks in the first, walls under a lid in the second. *Changes them:* anything else.

## Credits and limits of use

**The LEGO Group.** LEGO® is a trademark of the LEGO Group, which does not sponsor, authorize or endorse
this project. The building instructions and the designs of the sets named here are the LEGO Group's. They
were studied, not copied. This folder holds no page images and no step-by-step account of any set;
techniques are described in our own words, and a set's number and name appear only to say where something
was seen. Six passages in two reports that listed a set's first steps part by part were cut down to the
technique. The guide teaches techniques and tells the builder never to rebuild or imitate a set.

**Rebrickable.** The parts statistics are worked out from the Rebrickable catalogue downloads. Credit:
"Set inventories from the Rebrickable catalogue (rebrickable.com), November 2026." Its terms, as the
numbers researcher read them on archived copies of its pages: the downloads are "Free for personal and
commercial use, provided you acknowledge Rebrickable as your data source"; "You may automate downloading
these archives at most once a day. Scraping our web pages is strictly against our Terms and will get you
banned."; and, in section 5.3 of its Terms of Service, "No Rebrickable content may be used in the
training of AI models." The data was used only to compute aggregate statistics over parts lists and to
write guidance from them, nothing was trained on it, and the project's owner decided on 19 November 2026
that such figures may appear in `guide.md` as well as here. No set's parts list is reproduced anywhere in
this folder. `reports/numbers.md` should still be kept out of any model's training data.

**The LDraw Official Model Repository** (https://library.ldraw.org/omr). The building order was measured
from 49 model files of official sets. 48 are licensed CC BY 2.0 and one CC BY 4.0, and credit is due to
their authors. The main file of each is by: Philippe Hurbain (10258, 10298, 21035, 30285, 31066, 31084,
41075, 41092, 42058, 42061, 42080, 42083, 42093, 42096, 60101, 60216); Orion Pobursky (10280, 10281,
10283, 21036, 21046, 40433); Vincent Messenet (21319, 40379, 40441, 75272); Damien Roux (21026, 41498,
41596); Merlijn Wissink (31039, 60065, 60067); Roland Dahl (10252, 75144); Jaco van der Molen (10264,
21309); Magnus Forsberg (10271, 75895); Marc Belanger (31072, 31153); Adrien Pennamen (75892, 76897);
Stefan Frenz (75954, 75966); Chris Böhnke (10349); Christophe Mitillo (21303); Tomas Kralicek (31045);
Evert Jan Boer (75155); and the author signing as folkoluck (75075). The files also contain sub-models
and parts by other authors, who are named inside them. The licences cover the files, not the designs of
the sets. No model file is in this folder.

**The LDraw parts library** (https://library.ldraw.org, CC BY 4.0, a few files CC BY 2.0) is the source
of every part number and part name in the guide and the reports.

**Brickset** (https://brickset.com) gave piece counts and sizes for ten sets and part of one inventory.

**Published sources** (the numbering is that of `reports/written-knowledge.md`, which says how much of
each was read):

- S1. Jamie Berard, *Stressing the Elements*, slides, 2006:
  https://bramlambrecht.com/tmp/jamieberard-brickstress-bf06.pdf
- S2. LEGO, help page on "illegal" building techniques:
  https://www.lego.com/en-us/service/help-topics/article/using-illegal-building-techniques-in-lego-ideas-challenges
- S3. BrickNerd, *Illegal SNOT*, 2023:
  https://bricknerd.com/home/illegal-snot-stressful-techniques-for-sideways-building-9-7-23
- S4. Bill Ward, *Brick Geometry & SNOT Building*, 2022 (CC BY-NC-SA):
  https://www.brickpile.com/wp-content/uploads/2022/06/brick-geometry-bbtb2022.pdf
- S5. Gower, Heydtmann and Petersen, *LEGO: Automated Model Construction*, 1998:
  https://miis.maths.ox.ac.uk/miis/623/1/LegoModelAutomation.pdf
- S6. Testuz, Schwartzburg and Pauly, *Automatic Generation of Constructable Brick Sculptures*, 2013:
  https://infoscience.epfl.ch/record/189856/files/lego.pdf
- S7. Deepak Shenoy, *The LEGO Builder's Handbook*, 2024, sample chapter and contents:
  https://nostarch.com/download/9781718503809_chapter7.pdf
- S8. Jordan Schwartz, *The Art of LEGO Design*, 2014, contents: https://nostarch.com/download/ALD_toc_dt.pdf
- S9. Paweł "Sariel" Kmieć, *The Unofficial LEGO Technic Builder's Guide*, 2012, contents:
  https://nostarch.com/download/samples/lego_technic_Dtoc.pdf
- S10. Allan Bedford, *The Unofficial LEGO Builder's Guide*, 2012, chapter list:
  https://nostarch.com/legobuilder2
- S11. Brickset, interview with Anderson Ward Grubb, designer of 10280 Flower Bouquet:
  https://brickset.com/article/57482/interview-with-anderson-ward-grubb-designer-of-10280-flower-bouquet
- S12. New Elementary, interview with Mark Stafford and Marcos Bessa, 2019:
  https://www.newelementary.com/2019/06/lego-75936-jurassic-stafford-bessa-designer-interview.html
- S13. Brickset, *Bright-coloured filler bricks*:
  https://brickset.com/article/107900/bright-coloured-filler-bricks-what-s-up-with-that
- S14. LEGO, *How we design our building instructions*:
  https://www.lego.com/en-us/service/help-topics/article/how-we-design-our-building-instructions
- S15. The Brothers Brick, the Mark Stafford interview, part 3, 2009:
  https://www.brothers-brick.com/2009/01/11/lego-fan-vs-lego-designer-the-mark-stafford-interview-part-3
- S16. Mental Floss, *LEGO designers' job secrets*:
  https://www.mentalfloss.com/culture/jobs/lego-designers-job-secrets
- S17. Blocks magazine, on sketch models:
  https://blocksmag.com/explaining-lego-sketch-models-with-dc-76304-batman-forever-batmobile/
- S18. MIT 6.270, *Basic LEGO Structure and Bracing*, 2005:
  https://ocw.mit.edu/courses/6-270-autonomous-robot-design-competition-january-iap-2005/4aa718211a3d9142118d5dd0f138e54b_1_basiclego.pdf
- S19. Sariel, *Scaling tutorial for vehicles*, 2009: https://sariel.pl/2009/12/scaling-tutorial-for-vehicles/
- S20. Develop3D, on Bright Bricks:
  https://develop3d.com/profiles/brick-by-brick-bright-bricks-lego-cad-solid-edge-st10-design/
- S21. Sir Bugge, *Hypo-techniques*: http://www.l3go.bugge.com/articles/technique/Hypotech1.shtml
- S22. Brick Architect, interview with the designers of 10297 Boutique Hotel:
  https://brickarchitect.com/2021/interview-secret-history-of-10297-lego-boutique-hotel-with-anderson-ward-grubb-ashwin-visser/
- S23. BrickNerd, *SNOT basics*, 2021:
  https://bricknerd.com/home/snot-basics-geometry-techniques-and-pitfalls-3-18-2021
- S24. Liu and others, *StableLego*, 2024: https://arxiv.org/html/2402.10711v2

## Files in this folder

- `README.md`: this study.
- `guide.md`: the draft guide for an AI builder. No AI build has used it yet.
- `reports/vehicles.md`, `reports/buildings.md`, `reports/characters-and-sculptures.md`,
  `reports/botanicals-and-animals.md`, `reports/technic-and-frames.md`: the five category studies.
- `reports/universal-truths.md`: the ten very different sets.
- `reports/numbers.md`: the parts lists and the building order.
- `reports/written-knowledge.md`: what designers and builders have published.
- `experiments.md`: the first two experiments, run on 19 November with no AI build: our checker on
  official sets, and the AI's existing models measured against the guide's rules.
- `scripts/`: the small programs behind `reports/numbers.md` and `experiments.md` (those named `exp_`),
  as the researchers wrote them. Each takes
  the folders of downloaded data as arguments; the data itself (Rebrickable's catalogue files and the
  LDraw model files) is not in this repository and has to be fetched again from its source.

Each report is as its researcher wrote it, with an editor's note at its head saying what was removed
(folder names on the researcher's computer, notes to the study's coordinator, and the six passages
mentioned above).
