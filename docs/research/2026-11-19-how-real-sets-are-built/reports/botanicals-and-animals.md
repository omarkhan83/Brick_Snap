# How official sets are built: botanicals and animals

> **Editor's note.** This is one of the eight reports behind the study in `../README.md`, kept as its evidence. It is as its researcher wrote it, except for what this note lists. Points where the reports disagree with each other are dealt with in the README, not corrected here.
> Changed: three passages that listed, part by part and in building order, how a set's core is put together (the pot of 10311, the pot of 10309, the mid-body of 31129) were cut down to the technique. Their page and step references and their evidence marks are kept.

Category: organic subjects. Three Botanical sets (a potted plant, loose stems, a group of small plants)
and two Creator 3-in-1 animals (a large one and a small one, main model only).

## Sources, and how much was read

All five instruction booklets came from LEGO's own CDN, using the PDF links listed on
`lego.com/service/buildinginstructions/<set>`. A direct `curl` of that page got HTTP 403, so I did not
retry it in another form. I read the page through the ordinary page-fetch tool, which showed the PDF
links. The PDFs then downloaded normally under a generic client name: one request per file, seven files
in all. I rendered pages locally, four to an image, and read them. Piece counts and model sizes come from
Brickset (one page per set). Rebrickable refused automated access (HTTP 402), so **no set inventory was
checked there**. The few part numbers given below were checked only for existence, with the project's own
part search (`bricksnap/lab/search.py`), and matched to the drawings by eye. Each is marked "likely".

| Set | Name | Year | Pieces | Model size | Booklet pages read |
|---|---|---|---|---|---|
| 10311 | Orchid | 2022 | 608 | 39 x 30 x 24 cm | all 64 |
| 10280 | Flower Bouquet | 2021 | 756 | not given (stems are about 32 studs long) | 52 of 84 (5-8, 13-40, 49-52, 61-64, 69-80) |
| 10309 | Succulents | 2022 | 771 | 13 x 17 x 17 cm (nine pots together) | 72 of 108 over 3 booklets (book 1: 1-36; book 2: 5-24; book 3: 9-12, 21-32) |
| 31129 | Majestic Tiger (main model) | 2022 | 755 | 14 x 33 x 7 cm | 84 of 132 in booklet 1 (1-56, 69-72, 77-80, 97-120) |
| 31136 | Exotic Parrot (main model) | 2023 | 253 | 22 x 11 x 12 cm | 60 of 68 in booklet 1 (1-56, 61-68) |

Tags: [seen p.N] means I saw it on page N of that set's booklet. [booklet note] means a designer note
printed in the booklet. [recalled] means general knowledge I did not check.

---

## 1. 10311 Orchid: a potted plant

**What is built first (the core).** Bag 1 builds only the inside of the pot [seen p.6, 8-17]. It is
**kind (c) built around (a): a drum of Technic beams over stacked rings of plates.** Each layer is a
large round plate with a round brick in the middle and a ring of 1x1 Technic bricks with holes around
the edge; a pin in each of those bricks sticks out sideways, and a ring of curved plates locks the layer
[seen p.8-14]. Four such layers, each in its own bright colours, are stacked and turned so that the pins
line up in vertical columns [seen p.10-15]. Then **sixteen vertical 7-long Technic beams** go onto the
pin columns [seen p.15-16, steps 10-12]. The result is a hollow cylinder that is pinned, not studded, at
every layer.
A designer note says so outright: "The core of the pot is a modified version of the core used in the
large tower of the Hogwarts Castle set" [booklet note p.13]. The core is finished at step 15. That is
about 15 of 96 steps, and I estimate about a fifth of the parts.

**How it is made strong.** The vertical beams join the four plate layers across their height, and each
layer is locked by its ring of curved plates [seen p.9-15]. The beams play the part that overlapping
bricks play in an ordinary wall.

**How the outside attaches.** The beams' holes all face outward. Bag 2 pushes **32 short connectors**
into them [seen p.18, step 16]. Then 16 small dark-grey plates go on these, facing outward [seen p.18,
step 17]. Then come **32 identical skin panels**, each a 2x4 plate carrying a small roof slope with a
long bevelled 2x4 piece over it. The panels fit sideways around the drum and make the fluted,
sand-blue pot [seen p.19, steps 18-19]. The fluting is not moulded: each flute is the ridge of one
panel, set at a slight angle on the round drum.

**The stems: kind (e).** A designer note: "The orchid's stems are built from LEGO Technic elements"
[booklet note p.37].
- The **main stem** is a chain of dark-green ridged tube connectors joined by short red axles, with a
  yellow 3-long axle at the top. Small 1x2 thin Technic links sit on the chain where branches will join
  [seen p.22-25, steps 21-32].
- It is **kept from sagging by a hidden stake**: two black 32-long axles stand in the pot as a ladder,
  joined by flat Technic L-pieces. The green stem is threaded through those cross-pieces, and further
  Technic links clamp the two together [seen p.26-28, steps 34-36]. Technic Axle 32 is `50450` in the
  project search (likely the same part).
- The **arching flower stems** are chains of dark-green **angled Technic connectors** (each holds a
  fixed bend, with a hole in the middle) joined by short axles. The bends add up to a curve, so the
  curve is set by how many angled pieces there are and which way each one turns [seen p.30-46, steps
  38-80]. Each stem ends in a curled moulded tip. It plugs into the main stem or a cross-link with a
  blue axle-pin [seen p.31-33]. The centre holes not used for flowers are capped with a pin plus a
  round green tile, so they read as nodes [seen p.32, 36, 40].
- Buds are **pink round pieces on short pins** in those holes [seen p.35-38].

**Rooted and weighted.** The stake and stem push into the pot core [seen p.24, 27]. No extra weight is
added. The heavy studded pot is the base [inference]. A mulch of small brown claw pieces goes on top at
the end [seen p.61, booklet note: "built from claw elements"].

**Leaves.** Each leaf is a sub-assembly of **large curved wedge pieces on a 2x4 plate**, ending in a
hinge or clip plate. It hangs on **clip-and-bar joints at the pot rim**, where bars stand at angles in
Technic angle connectors [seen p.20-21, 49-54, steps 13, 20, 82-84]. Built: two long leaves (one
sub-assembly built 2x), one medium and one short. The aerial roots are **dinosaur-tail pieces** in olive
[booklet note p.29].

**Flowers: bag 4, one sub-assembly built 6 times** [seen p.57-59, steps 86-94].
- The centre is a magenta Technic hub with several pins, on a short axle.
- The two big round petals are **"shoulder pad elements from large LEGO characters"** [booklet note p.57].
- The three narrow sepals are **minifigure shields from the 1995 Castle line**, held on small clip
  pieces [booklet note p.60, seen p.58].
- The pink lip is two curved pieces. The column is a **frog** [booklet note p.58].
- Each flower plugs into a stem hole on its axle, so it can be turned [seen p.59].
- The two small blossoms are **Demogorgon heads** (from the Stranger Things set) on round 1x1 bricks
  [booklet note p.55, seen p.56].

**What moves.** Nothing is a working mechanism. Leaves can swing on their clips. Stems can turn on
their axles and can be rebuilt to other lengths. Flowers turn on their axles. The booklet shows three
other arrangements of the same parts [seen p.3].

**Inside.** The pot core is built in **bright red, orange, yellow, teal, blue, lime and white**, none of
which shows [seen p.8-19]. The colours seem to code the layers and pin types for the builder
[inference]. The pot is hollow apart from the 4x4 round bricks in the middle.

**What sets the scale.** The shoulder-pad petal. Six of them set the flower size. The pot is sized to
balance the stem height, which is fixed by the 32-long stake axles [inference].

**Order of the build.** Inside out, then upward: pot core, then pot skin, then stake and stems, then
leaves, then flowers. Steps add 1 to 8 parts, and up to 32 when one panel is placed many times
[seen p.18-19].

**Named techniques.** A pinned beam drum; panels on sideways studs to make a round skin; a hidden
stake; angled-connector chains for curves; clip-and-bar leaves; reused parts for organic shapes
(shoulder pads, shields, tails, frogs, claws).

---

## 2. 10280 Flower Bouquet: loose stems

**What is built first.** There is no shared core. **Every flower is its own spine (e)**: a single
32-long sand-green Technic axle for the thin stems [seen p.14, 18, booklet note p.18: "The stem is made
from a 32-module LEGO Technic axle piece"]. Or, for the thick stems of the roses and snapdragons, a chain
of 8 dark-green ridged tube connectors joined by short red axles [seen p.27-29, 33]. The flower head is
a small separate core on the top end of the stem. Bag 1 holds 2 daisies and 3 roses; bag 2 two
snapdragons, a poppy and two grass plumes; bag 3 three big leaves, an aster and lavender [seen p.13-14].

**How stems stay straight.** The axle is stiff enough on its own. The connector chain stays straight
because each joint is a tight axle-in-tube fit [inference]. There is no stake, because the bouquet
stands in the buyer's own vase (no vase in the set) [inference].

**Flower-head cores (each a different small hub).**
- **Daisy**: a dark-grey moulded piece with several bars, used as a branching hub on the stem tip. Each
  of its three bloom stalks carries a tan three-pronged stem piece, a ring of eight white 1x2 rounded
  plates and a yellow round tile [seen p.16-17, steps 1-5].
- **Rose**: a 2x2 round brick with two green rings around it. On top are tan inverted brackets that
  carry inner petals sideways. Outer petals are **light-nougat curved car-bonnet pieces on clip plates**
  [seen p.19-24]. Booklet notes: "The outer petal elements are more commonly used as engine hoods and car
  roofs"; "Using traditional LEGO C-snap elements allows the petals to move" [booklet notes p.24, p.34].
  A brown bar under the head plugs into the stem [seen p.25].
- **Poppy**: a column of yellow 1x1 bricks with studs on their sides. Orange curved wing pieces hang
  on clip plates around it, and four larger petals are set on top at an angle [seen p.37-40].
  Booklet note: "The petal elements are usually used in LEGO cars and airplanes" [p.40].
- **Snapdragon**: a brown bar as spine. Sand-green round plates with bar handles around the edge are
  threaded onto it, alternating with 1x1 round bricks. Pink cones and magenta droid heads go on the
  handles, and a cube with side studs tops it [seen p.49-52]. Booklet note: the purple blossoms "are
  more commonly seen as the heads of droids and robots in Star Wars sets" [p.52].
- **Aster**: a green ring with a tiny hub. About 40 purple petal pieces, each on a 1x1 clip plate, are
  clipped round the ring in tiers [seen p.75-79, steps 1-9]. Arrows mark which way each one must face
  [seen p.77, 79].
- **Lavender**: a hub with four arms carrying bars of small lavender pieces [seen p.64].

**Leaves.** A **long leaf on a stem** is a plate stack (dark-green 2x10 with lime 2x2 plates) under
long sand-green wedge plates. At its foot is a Technic pin, which plugs into the top of a bare stem axle
[seen p.69-73]. Built three times. **Small leaves** are moulded leaf pieces on a clip ring around the
stem [seen p.29-34, 61]. A "carrot top" piece is a brown sprout [booklet note p.16].

**Repeats.** The daisy bloom is built 3x per daisy and 2 daisies; the rose 3x; the aster petal about
40x; the long leaf 3x [seen p.17, 19, 25, 73-79].

**Inside.** Tan brackets and grey hubs are hidden inside rose heads [seen p.21-22].

**Scale.** Set by the 32-long axle. Heads are made to suit it [inference].

**Order.** Each flower head is built first, then its stem, then the leaf on the stem. One to six parts
per step [seen throughout].

---

## 3. 10309 Succulents: nine small plants

**What is built first.** **Every pot is the same simple stack, kind (a)**, rebuilt nine times
[seen book 1 p.8-10, 14-16, 25-27; book 2 p.5, 10-11, 18-19; book 3 p.9-10, 21-22]: a 6x6 plate; a
filler of plates and bricks inside (the soil), sometimes with a socket for the plant; a wall one brick
high, mostly of 1x2 bricks with a cross-shaped hole on the face; and a rim of small panels on top.

The holes in the wall take **red pins that join neighbouring pots** into one arrangement [seen book 1
p.13, 33-36; book 3 p.31]. One pot is a hidden store for spare pins under a lift-off top [seen book 3
p.32]. Designer note: unlike other Botanicals, each succulent "can be built in its own individual
little pot… either connected to make a beautiful group … or showcased separately" [booklet note book 1
p.4].

**Plant cores (all small, each kind (e) or (b)).**
- **Echeveria rosettes**: a bar or axle stands up from the soil. Round plates with bar handles are
  threaded onto it, and a cube with studs on all four sides sits on top. Leaves are **curved slopes on
  1x1 clip plates**, clipped onto the handles and stacked in tiers of 4, then 8, then 8. Each tier is
  set a half step round from the last and leans further out [seen book 1 p.11-13, 29-32]. Booklet note:
  the rosette pattern comes from "the swirl top of an ice cream cone" [p.30].
- **Aloe**: a spine of round plates with clip handles. Then a **Technic three-way connector with
  ball-cup arms**, set at an angle to the stem. Its arms and the clip handles carry **claw pieces "from
  fantastic creatures"** as the spiky leaves [seen book 1 p.18-24, booklet note p.22].
- **Barrel cactus**: a vertical stack of **lime cubes with studs on four sides**, between brown round
  bricks on a bar. Four identical olive panels built sideways (a plate on curved slopes, with spines
  on top) clip round the cube stack [seen book 2 p.19-24]. Cube: `4733` "Brick 1 x 1 with Studs on Four
  Sides" in the project search (likely).
- **Lavender echeveria**: a cube on a bar. Four large round petal shells go on clips on four sides, and
  four more on the next ring up [seen book 2 p.13-16].
- **Burro's tail**: plates stacked on a short post, with **dinosaur-egg pieces** as the plump leaves
  [seen book 3 p.11-12, booklet note].
- **Red echeveria**: **two Technic wheel hubs stacked**, with pins pushed into their radial holes. A
  check box insists on the hub being the right way up [seen book 3 p.23]. Six identical leaf pods
  (a 1x1 brick with side studs wrapped in dark-red curved arch pieces, tipped with a pyramid piece)
  plug onto the pins. A smaller ring of four wedge leaves sits above, then a lime cube centre
  [seen book 3 p.23-31]. Booklet note: the pyramid tips are Nexo Knights parts [p.28].

**Repeats.** One pot design times nine. The rosette leaf times 8 per tier. The cactus panel times 4.
The red echeveria pod times 6 [seen as above].

**Inside.** The pot cores hold tan, green, dark-green and red plates where nobody looks [seen book 2
p.5, book 3 p.21].

**Scale.** Set by the 6x6 pot. Plants are sized to rise one to two pot heights above it [inference].

---

## 4. 31129 Majestic Tiger: a large animal (main model)

**What is built first.** The **middle of the body** (bag 1, steps 1-76, p.6-34). It is **kind (b): a
box of bricks with studs on their sides**, hidden in bright colours: a 2x10 plate below and another
above, 1x2 bricks with studs on two sides at one end, clip plates underneath, bricks and plates as fill
between, and 1x2 bricks with side studs along the top edge [seen p.6-10, steps 1-14].

A separate belly is made of a white plate, black wedge plates and tan slopes, with pink stud-side
columns at each end. It joins underneath to make a **closed rectangular ring** [seen p.11-12, steps
15-20]. The **sides** are built separately as **flat plate panels: plates stacked with stripes laid into
the layers**, with orange and black curved slopes on the edges. They go on sideways against the side
studs, two panels per side [seen p.13-18, steps 21-26]. A white top strip closes it. Then the two ends
are filled with **stripe blocks built as stacks of orange and black plates**. Their dark-grey round pieces
seem to hold these blocks to the side studs (I could not identify the part) [seen p.19-34, steps 27-76].
About 76 of roughly 300 steps, and I estimate a quarter of the parts.

**How it is made strong.** The closed ring of plate–brick–plate, with long plates (2x10, 2x8) running
the full length top and bottom [seen p.6-12]. The side panels are a second skin [seen p.13-18].

**Body sections.** The tiger is built as **separate sections joined in a row**: mid-body, then chest
with front legs (bag 2), then hip with back legs (bag 3), then tail and head (bag 4) [seen p.5]. The
chest joins the mid-body with **three small ball joints**, dark balls going into a column of grey cups
on the mid-body's front face [seen p.46, step 101]. Plate 1x2 with Socket Joint-8 is `14418`/`14704`
and with ball `14417`/`22890` in the project search; which ones the set uses is not checked.

**Chest core.** A column of **white bricks with studs on their sides**, built up with orange brackets,
then a black **ball-cup brick** for the neck. Further side studs carry the white chest skin
[seen p.35-46].

**Legs (posable).** Each leg hangs from the body on a **Technic click rotation joint**. A tan Technic
brick with a half rotation-joint ball takes the matching dark-grey half, and the booklet shows a
"CLICK" panel for it [seen p.51 step 115, p.79 step 200]. Project search: `48170`/`48171` "Technic Brick
2 x 2 with Hole, Half Rotation Joint Ball" (likely the tan part). The upper leg is a plate-built
sideways shape with curved slopes for the muscle. The **paw** joins it with a white towball, a plate
with a ball, going into a socket brick in the paw, so the paw can be angled [seen p.50-56]. The paw is
white plates and brackets with stacked orange curved slopes as toes. The paw sub-assembly is built 4
times and the legs are mirrored in pairs [seen p.53-55, 97-98].

**Tail.** Four segments, each a **dark-grey plate with a ball at one end and a socket at the other**,
dressed with orange, white or black curved bricks. They hang off a white base block that has a towball
on its front [seen p.101-103, steps 253-261]. Project search: `14419` "Plate 1 x 2 with Socket Joint-8
with Friction and Ball Joint-8" (likely).

**Head.** A block built in all directions around white and black bricks with side studs, with a
**white towball at the back** that goes into the neck socket [seen p.105-116]. Tan "horn"/claw pieces
are the teeth and fangs. A pink curved piece is the tongue. Cheek ruffs are **4x4 orange round plates
mounted sideways, edged with white claw pieces** for fur [seen p.114-115, steps 287-288]. The lower jaw is
a separate sub-assembly that hangs on hinge parts [seen p.116, step 289]. Ears are wedge pieces on
clips [seen p.113].

**What moves.** Four shoulders and hips on click rotation joints, four paws on ball joints, the head on
a ball joint, the tail in four ball joints, and the jaw on a hinge [seen as above].

**Balance.** Four legs, with the heavy body between the hip and shoulder joints. The click joints hold a
pose against the weight [inference].

**Inside.** Red, pink, magenta, blue and tan throughout the body cores [seen p.6-34, 105-109].

**Scale.** I found no single scaling part. The body length comes from the 10-long plates in the core
[inference].

**Order.** Middle first, then front, then back, then extremities and head. Left and right sides are
mirrored. One to six parts per step. Small sub-assemblies are boxed [seen throughout].

---

## 5. 31136 Exotic Parrot: a small animal (main model)

**What is built first.** The **perch and its base** (steps 1-38, p.5-27), not the bird.
- The base is two half-round green plates and a 4-piece dark-green slope ring [seen p.5-7].
- The **trunk is a 9-long axle with brown round bricks and branch pieces threaded on**, kind (e)
  [seen p.8-10].
- Flowers are clip-plate petals round a small bar-handle hub [seen p.11-16].
- Two **Technic connectors on top**, each holding an axle with yellow bushings, are where the bird's
  feet go. The claws are **horn pieces on Technic connectors** [seen p.21-27].

**The bird's core: kind (b).** A tower of **white bricks with studs on their sides**, stacked with
coloured bricks between them, on a yellow lower piece with a **4-long axle through it for the legs**
[seen p.28-35, steps 39-50]. Grey clip/hinge plates on top take the head [seen p.33]. The breast and
back are sideways sub-assemblies of plates and curved slopes: blue at the back, orange and yellow at the
front. They go onto the side studs, which gives the round belly from a square core [seen p.37-40,
steps 54-59].

**Wings.** Two mirrored sub-assemblies, about 10 steps each. A plate stack with curved slopes and long
tiles for feathers. It is mounted with a **pin through a 4x4 round plate with a hole**, so each wing
swings on one pin into a side stud of the core [seen p.42-47, 53-56]. Several shades of blue are layered
from dark at the tips to light at the shoulder [seen p.43-46].

**Tail.** A long plate stack (orange, light-blue and dark-blue layers) mounted on a **click hinge plate**,
so its angle can be set [seen p.48-50, step 77].

**Head.** Bricks with studs on their sides. **Round black-and-white pieces on side studs for eyes**, a
black curved slope plus a small plate for the beak, and a teal tile cap [seen p.61-64, steps 102-107].

**What moves.** The head on hinge plates, the wings on single pins, the tail on a click hinge, the
legs on an axle [seen as above].

**Balance.** The bird does not stand by itself. Its feet fix onto the perch's Technic connectors, and the
round perch base carries the weight [seen p.29, 41, 47].

**Inside.** Red, pink, blue and orange inside the core [seen p.31-35].

**Order.** Perch, then body core, then breast and back skin, then wings (mirrored), then tail, then
head [seen].

---

## Conclusions across the five sets

### Patterns that held in every set

1. **A hidden core comes first, then a skin.** Pot drum then fluted panels (10311); pot box then plant
   (10309); body ring then stripe panels (31129); stud-side tower then breast and back (31136). The
   bouquet (10280) is the exception: each stem is its own core, and each head has a tiny hub.
2. **The core is the one part built in colours nobody sees.** All five sets [seen].
3. **Everything organic is a separate small sub-assembly, built several times and attached at one
   point**: petals, leaves, paws, wings, tail segments, flowers.
4. **Organic shapes are borrowed parts.** Shoulder pads, shields, frogs, dinosaur tails and eggs, claws,
   horns, car bonnets, droid heads, wheel hubs. Every Botanical booklet says so in its notes.

### What is different between plants and animals

- **The plant skeleton is a line: axle, bar or connector chain.** The **animal skeleton is a box:
  bricks with studs on their sides**, with joints fixed to its faces.
- **Plants attach by clips on bars** (petal clip plates, leaf clips, handle plates on bars) and by
  **pins in holes** (flowers on axles, red echeveria pods). **Animals attach by ball joints, click
  rotation joints and click hinges**, which hold a pose.
- **Plants get variety by angle and count**: the same leaf set at different tilts, tiers turned half a
  step, more angled connectors for a longer curve. **Animals get variety by mirroring**: left and right
  pairs.
- **What is the same:** a core in hidden colours, a skin of curved slopes on sideways studs, and a few
  sub-assemblies repeated.

### When a pin-and-beam core appears

- **In the potted plant at about 600 parts (10311), the pot is a pinned Technic beam drum.** Its job is
  to be round and to carry a sideways skin all round, not to bear load. The stems are Technic connector
  chains, which hold a curve and can be rebuilt. A stake of two long axles holds the main stem up.
- **The other sets at 250-770 parts use no beam frame**:
  - Bouquet and Succulents: axles, bars and stacked plates.
  - Tiger and Parrot: brick boxes with side studs.
- **The owner's "different style"** is most likely one of these:
  - The orchid pot. It is Technic, but a *drum of upright beams over stacked round plates*, with the
    skin pinned onto the beams. The beams do not run the length of the model as a chassis.
  - The bouquet or succulents, which have *no shared core at all*: one axle per stem, and a small hub of
    bars, cubes and clip rings per head.

  I cannot tell which set he saw.

### Rules of thumb (with evidence)

- **A long thin stem is an axle (up to 32 long), or a chain of tube connectors on short axles.**
  10280, 10311. If it must stand on its own over about 20 studs, it gets a hidden stake. 10311 uses
  two 32-long axles tied by cross-links. Counter-example: the bouquet has no stake, because a vase holds
  it.
- **A curve is a chain of fixed-angle connectors, not a bent part.** The more pieces, the longer the
  arc. 10311.
- **A rosette is tiers of identical clip-plate leaves on a hub with bar handles.** Each tier is turned a
  half step and leans further out. 10309 (4, then 8, then 8); 10280 aster (about 40 petals in tiers).
- **A round pot is a drum carrying many identical panels sideways.** 10311 uses 32 panels on 16
  beams. A square pot is a plain brick stack. 10309.
- **An animal is joined in sections end to end, with ball joints between them.** 31129.
- **A posable limb hangs on a click rotation joint at the body and a ball joint at the foot.** 31129.
  The small parrot uses simpler pins and click hinges, and a fixed perch carries its weight.
- **Body width comes from sideways panels**, so the core can stay narrow and square. 31129, 31136.
- **Every repeated sub-assembly is boxed once with "Nx"**, and arrows mark which way each copy faces.
  10280 aster, 10309 red echeveria, 31129 paws.

### Playbook for a NEW subject in this category

**A plant at about 100 parts** (one small potted plant):
1. Lay a square base plate, 6x6 or 8x8.
2. Build the pot wall two bricks high round its edge, and top it with corner and straight panels.
3. Fill the inside with plates for soil, leaving a centre socket: a round brick or a plate with a hole.
4. Stand a bar or short axle in the socket as the spine.
5. Thread two or three round plates with bar handles onto the spine, with 1x1 round bricks between them.
6. Make one leaf as a sub-assembly (a curved slope or wedge on a 1x1 clip plate) and build it 8 to 12
   times.
7. Clip the leaves onto the handles in tiers. Turn each tier half a step from the one below. Tilt the
   lower tiers out further.
8. Cap the spine with a cube with studs on four sides, and put a small centre piece on it: a cone, a
   round tile or a flower piece.

**A plant at about 400 parts** (a potted plant with stems, leaves and flowers):
1. Build a round pot core: stacked round plates, each with a ring of Technic bricks whose pins stick out
   sideways, and upright beams pinned up the outside. Use bright colours inside.
2. Push short connectors into the beam holes. Put a small plate on each, facing outward.
3. Make one pot-panel sub-assembly and attach many copies sideways all round.
4. Stand a hidden stake of two long axles in the pot, tied with Technic cross-links.
5. Build the main stem as tube connectors on short axles, threaded through the cross-links.
6. Build each side stem as a chain of angled connectors. Plug it into a connector hole on the main stem.
   Cap unused holes with a pin and a round tile.
7. Build each leaf as a plate with large curved wedges and a clip plate at its foot. Hang the leaves on
   bars at the pot rim at different angles.
8. Build one flower sub-assembly: a hub, petals on clips, and a centre piece. Repeat it 5 to 8 times.
   Plug each flower onto an axle in a stem hole.
9. Cover the soil with small brown or green detail parts.

**An animal at about 100 parts:**
1. Build a body core as a tower of bricks with studs on their sides, two or three high.
2. Put a pin or axle through the bottom for the legs, and hinge or clip plates on top for the head.
3. Build the belly and back as sideways plate stacks with curved slopes, and fix them to the side studs.
4. Build the two side limbs (wings or legs) as mirrored plate stacks. Fix each with one pin into a side
   stud, so it swings.
5. Build the tail as a plate stack on a click hinge plate at the back.
6. Build the head round a cube with studs on its sides. Use round pieces on the side studs for eyes and
   a curved slope for the beak or snout. Fix it on the hinge plates.
7. If it cannot stand, give it a base with a peg that it fixes onto.

**An animal at about 400 parts:**
1. Build the mid-body as a closed ring: a long bottom plate, columns of bricks with studs on their sides
   at the ends, and a long top plate. Use hidden colours inside.
2. Make side panels as flat plate stacks, with markings laid in the layers and curved slopes on the
   edges. Fix two per side onto the side studs.
3. Build the chest and hip as separate blocks, each round its own stud-side core, with a ball-cup brick
   for the neck or tail.
4. Join chest and hip to the mid-body with two or three small ball joints on their facing ends.
5. On each side of chest and hip, fix a click rotation joint for the limb.
6. Build each upper limb as a sideways plate shape with curved slopes. Put a towball at its lower end.
7. Build one foot as a socket brick under stacked curved slopes. Repeat it four times, mirrored in pairs.
8. Build the tail as a chain of plates with a ball at one end and a socket at the other. Dress each
   link with curved bricks.
9. Build the head round a stud-side core with a towball at the back. Add a hinged jaw, side-mounted
   round plates for cheeks, and wedges on clips for ears. Fix the head into the neck socket.

### Part vocabulary by job

- **Core (plants):** Technic axle 32 (`50450`, likely), ridged tube axle connectors, angled Technic
  connectors, bars, round plates with bar handles, 1x1 round bricks, Technic wheel hubs, round 8x8
  plates, 1x1 Technic bricks with holes, 7-long Technic beams.
- **Core (animals):** bricks with studs on their sides (1x1 with four sides is `4733`, likely), 1x2 and
  2x10 plates, brackets.
- **Lock:** long plates across the core, and rings of curved plates on round layers.
- **Sideways building:** bricks with studs on their sides, brackets, cubes with studs on four sides,
  and pins sticking out of Technic bricks.
- **Angle:** angled Technic connectors, clip plates on bars, click hinge plates, and tiers turned half
  a step.
- **Joint:** ball-and-socket plates (`14417`, `14418`, `14419`, `22890`, `14704` exist; which the tiger
  uses is not checked), click rotation joint bricks (`48170`/`48171`, likely), single pins in round
  plates, axle-in-hole.
- **Skin:** curved slopes, wedge plates, car bonnets and wing pieces, plate panels.
- **Organic detail:** claws, horns, shoulder pads, shields, frogs, dinosaur tails and eggs, droid
  heads, leaf and flower pieces, pyramid tips.

### What I could not find out, and what to look at next

- **Exact part identities and counts.** Rebrickable refused automated access, so no inventory was
  checked. In particular, these are described by shape, not number: the orchid's short connectors and
  pot plates, the tiger's stripe-block fasteners, and the parrot's wing pin.
- **The share of parts in each core** is my estimate from steps, not a count.
- **Not read:** the bouquet's pages 9-12, 41-48, 53-60, 65-68 and 81-84 (lavender, grass, the second
  snapdragon); the tiger's pages 57-68, 73-76 and 81-96 (back legs, hip core); and parts of the
  succulent booklets.
- **No set over 1,000 pieces was studied.** A large Botanical, such as the Bonsai Tree (10281) or a
  big Creator animal, would show whether beam cores grow with size. That is the next thing to check,
  along with the Bonsai's trunk (recalled: brown branch pieces on a Technic core; not checked).
