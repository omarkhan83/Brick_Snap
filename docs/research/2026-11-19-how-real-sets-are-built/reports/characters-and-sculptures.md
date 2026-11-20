# How official LEGO sets are built: characters and sculptures

> **Editor's note.** This is one of the eight reports behind the study in `../README.md`, kept as its evidence. It is as its researcher wrote it, except for what this note lists. Points where the reports disagree with each other are dealt with in the README, not corrected here.
> Changed: three passages that listed, part by part and in building order, how a set's first steps go (the body of 40674, the hindquarters of the larger cat in 40441, the tower of 75318) were cut down to the technique. Their page and step references and their evidence marks are kept.

Category: brick-built figures and display sculptures of a single subject. This is the category closest
to what BrickSnap makes.

## Sources and method

All five booklets came from LEGO's own site. Each set's instructions page
(`lego.com/service/buildinginstructions/<set>`) lists a PDF on LEGO's product-asset CDN. A plain `curl`
of the instructions page itself got HTTP 403, so I read the page through a page fetcher instead. I then
downloaded each PDF once with a generic client name, one file per set, five files in all. The pages are
vector drawings. The usual page renderer (poppler) is not installed here, so a small script in a
separate folder rendered them to PNG with PyMuPDF (`python -I`), four pages per image, and I read those
images.

Rebrickable inventories refused automated access (HTTP 402), so I could not check a set's parts list
there. Where I give a part number, it was checked against the project's LDraw part search
(`bricksnap/lab/search.py`). That check shows only that the part exists. Which part a set uses I judged
from the drawing, and the report says so wherever it matters. I quote LEGO element IDs only where the
booklet's own parts page prints them.

Tags: **[seen]** means seen in the booklet pages I read (booklet page numbers or step numbers given).
**[recalled]** means general knowledge I did not check. I used no reviews.

| Set | Name | Booklet | Pages read |
|---|---|---|---|
| 40674 | Stitch (BrickHeadz) | 44 pp. | all 44 |
| 40441 | Shorthair Cats (BrickHeadz, two cats and a shared base) | 76 pp. | pp. 1–56 and 61–72 (about 68) |
| 10331 | Kingfisher Bird | 88 pp. | pp. 1–48 closely; 49–56, 61–72, 77–88 sampled (about 72) |
| 75318 | The Child | 164 pp. | pp. 1–64 closely; 81–84, 97–100, 105–136, 149–156 sampled (about 108) |
| 75328 | The Mandalorian Helmet | 108 pp. | pp. 1–44 closely; 49–60, 73–76, 85–88, 97–104 sampled (about 72) |

Licensed subjects were studied for technique only.

---

## 1. 40674 Stitch (BrickHeadz figure, a character)

**1. The set.** The booklet's back page carries a ©2024 date [seen p. 44]. The parts list is on pp. 42–43
[seen]. I did not check the total part count; it is about 150 to 200 judging by the parts list
[recalled/estimated]. The model is a standard BrickHeadz figure about 10 cm tall on a small black base
plate [recalled height]. I read all 44 pages.

**2. What is built first.** The body: a box about 4 × 4 studs [seen steps 1–11, pp. 3–12]. It stands on
two plates joined by a third laid across them, has a filler of odd-coloured parts in the middle (among
them a 2 × 2 brick with studs on its sides), and has grey bricks with four studs on one face at its two
sides (they look like LDraw 22885, "Brick 1 × 2 × 1.667 with Studs on 1 Side"; element 6123809 ×14 on
the parts page). Plate stacks close the back.

The head core comes next [seen steps 12–15, pp. 13–16]. A 2 × 2 column of filler bricks in odd colours
(lime, pink, brown) sits at the centre. Six of the grey side-stud bricks ring it, then six more on top:
12 in the head and 2 in the body, which matches the 14 on the parts page. The result is a solid block 4 × 4
studs across and 3⅓ bricks tall, with four studs facing out on every square of its four side faces.
This is core type **(b)**. The cores are finished by step 15 of 38, with roughly 40% of the parts.

**3. How the core is made strong.** The two layers of side-stud bricks are offset so their joints do not
line up, and the central 2 × 2 column ties the ring together. Plates cap the top [seen steps 13–17]. No
pins are used anywhere.

**4. How the outside attaches.** Almost everything attaches sideways, onto the side studs of the core.

- **Front face:** built as a separate flat panel, studs up, on a 4 × 6 base of plates [seen steps 29–35,
  pp. 31–35]. Curved slopes, cheese slopes and jumper plates make the cheeks and brow. Two printed 1 × 1
  round eye tiles sit on it, and a black dome makes the nose. The panel is then turned 90° and pressed onto
  the core's front studs [seen p. 35, step 36].
- **Sides of the head:** small panels of plates and curved slopes, 2 to 3 plates thick, built as
  sub-assemblies and pressed on sideways [seen steps 16–17 and 21–27].
- **Top:** plates and curved slopes, plus cheese slopes at the edges to round the corners [seen steps
  18–20].

The rounded look comes entirely from curved slopes on the surface of each flat panel. The panels meet at
square corners, and a cheese slope sits at each corner [seen pp. 17–20].

**5. What is built separately and attached.**

- The face panel: one.
- Two head side panels and two ears, built as mirror pairs [seen steps 24 and 28, pp. 24 and 29]. Each ear
  is a stack of slopes on a plate with a sideways stud, pressed onto the core's side studs.
- Two arms: small blocks on plates that carry a clip or stud on the side, fixed to the body's side studs
  [seen step 11, p. 12].
- Two legs: plate stacks under the body [seen step 37, p. 36].
- The base: a black plate with tiles [seen step 38].

**6. What moves.** Nothing.

**7. Inside.** The filler colours (lime, pink, brown, red, yellow) appear only where they will be
covered: the centre of the head and the body core. The cores are solid, not hollow [seen steps 4, 12, 14].

**8. What sets the scale.** The BrickHeadz template: a 4 × 4 head made of 12 grey side-stud bricks, and
eyes made of printed 1 × 1 round tiles [seen].

**9. The order of the build.** Body, then head core, then head skins: front, sides, top, back. Then the
face panel, legs and base. The model is turned upside down to fit the legs [seen p. 37]. Each step adds 1
to 6 parts. Left and right panels are built in mirror steps [seen steps 21–28].

**10. Named techniques.**

- **The BrickHeadz head core:** a ring of side-stud bricks round a filler column.
- **Studs-not-on-top:** the face is a panel built flat and turned to face forward.
- **Cheese slopes on corners.**
- **Jumper plates:** they centre the nose between studs [seen step 33].

---

## 2. 40441 Shorthair Cats (two BrickHeadz animals, of different size and pose)

**1. The set.** 2021, 250 parts in total [seen on the instructions page]. The cover prints 121 and 120
beside the kitten and the shorthair cat [seen p. 1]. The booklet builds the larger, sitting cat first
(pp. 3–38), then the standing kitten (pp. 39–56), then a shared oval display base (pp. 57–72) [seen].

**2. What is built first.**

*Larger, sitting cat.* The build starts with the hindquarters, from the bottom up [seen steps 1–5, pp.
3–8]: a few plates and a brick, and two mirror-image hind-leg sub-assemblies. Each hind leg is a plate
with a 1 × 1 brick with a side stud, which carries a rounded tile as the paw, and a slope as the thigh.
The chest gets its side studs from a bracket (1 × 2 – 2 × 2 [seen step 7]), and the two front legs are
identical (built "2x" [seen step 8]). Layers of plates follow, with a belly panel fixed sideways [seen
steps 11–16].

The head core [seen steps 18–21, pp. 19–22] is the same template as Stitch: 12 light-grey bricks with
studs on one side, ringed round a column of green 2 × 2 bricks, a blue round brick and a pink 2 × 2 brick.
That is core type **(b)** again.

*Kitten (about 120 parts).* The head core is one size smaller [seen steps 9–14, pp. 45–48]. One inner
1 × 1 brick (green, then pink) is ringed by eight 1 × 1 bricks: four dark-grey with a stud on one side
and four light-grey with studs on two sides. There are two such layers, giving a 3 × 3 core with side
studs all round. In LDraw these look like 87087 (1 × 1, stud on one side) and 26604 (1 × 1, studs on two
adjacent sides), or 4733 (studs on four sides); I judged this from the drawing. The kitten's body is
plain stacked bricks and plates, with one bracket for its front [seen steps 1–8].

**3. How the core is made strong.** The layers overlap. A 4 × 6 plate caps the sitting cat's body before
the head goes on [seen step 13], and yellow collar plates lock the join between body and head [seen steps
12 and 15].

**4. How the outside attaches.**

- **Sides of the head:** on the side studs, with tiles for flat cheeks and 2 × 2 curved slopes as rounded
  haunches. The haunches are built "2x" as sub-assemblies [seen step 36, p. 38].
- **Face front:** a 3 × 4 plate assembly carrying round tiles with printed eyes, a pink tile for the nose,
  and bar-like whisker elements. It is pressed on sideways [seen steps 27–29, pp. 28–30]. Two quarter-round
  curved bricks above the eyes make the brow.
- **Ears:** pointed slopes on a 1 × 2 plate on top of the head [seen step 24].
- **Bow-tie:** a separate little assembly of two slopes and a round plate [seen step 25].

**5. What is built separately and attached.**

- The face: one.
- Haunches: two, mirrored.
- Hind legs: two, mirrored.
- Front legs: two, identical.
- The tail: plates and curved slopes ending in a plate with a clip. It hangs on a bar at the cat's back,
  so it can swing [seen step 34, pp. 35–36].
- On the kitten, the tail hangs on a clip on a side stud in the same way [seen steps 23 and 26, pp. 53–56].

**6. What moves.** Only the tails, on clip-and-bar hinges.

**7. Inside.** The filler colours (teal, green, blue, pink, yellow) appear only inside the head and body
[seen steps 7, 16, 19]. The cores are solid.

**8. What sets the scale.** The BrickHeadz head: 4 × 4 for the adult cat and 3 × 3 for the kitten [seen].

**9. The order of the build.** Bottom up: feet, legs, body, collar, head core, then the head's skins on
each side. The face goes on near the end. Mirror pairs are built as two consecutive sub-assemblies, or
once marked "2x" [seen].

**10. Named techniques.**

- **Head core, two sizes:** 12 side-stud bricks for the 4 × 4 head, eight 1 × 1 side-stud bricks for the
  3 × 3 head.
- **Display base:** a plate sandwich of crossed long plates [seen pp. 61–62], with quarter-round plates at
  the corners and curved bricks forming the rim [seen pp. 63–64].

---

## 3. 10331 Kingfisher Bird (animal display model)

**1. The set.** It has about 834 parts [recalled] and is about 20 cm wide [recalled]. The back page
carries a ©2024 date [seen p. 88]. The booklet's introduction says the designers added "a support beam
that helps create an illusion of flight" [seen p. 4]. Bags: 1 is the base, 3 the body, 4 the wings; the
head and reeds come at the end [seen].

**2. What is built first: a Technic frame for the stand, not for the bird** [seen steps 1–12, pp. 9–15].

- Two Technic bricks 1 × 16 with holes (LDraw 3703 exists) are locked by plates.
- Pins and Technic connectors join them.
- A stack of Technic beams, including a bent beam, rises at an angle with a red connector on top. This is
  the support arm the bird will sit on.

This is core type **(c)** for the stand. An oval base then grows round it [seen steps 13–21, pp. 15–18].
Plates with brackets and 1 × 1 bricks with side studs (headlight-type bricks) form a ring. Curved slopes
fixed sideways on that ring make the smooth oval rim, about 2 plates thick. The top is filled with blue
plates that will be covered. Light-aqua tiles make the water, and white slopes and wedges make the splash
[seen steps 22–46, pp. 19–31]. The stand takes about 48 steps, roughly a third of the parts.

The bird's body has its own small pinned core [seen steps 49–53, p. 33]: two short beams joined by
friction pins, and Technic bricks with pins. Plates and bricks go on top, with red and tan filler inside
[seen steps 54–66, pp. 35–40].

**3. How the core is made strong.**

- The stand: long Technic bricks locked by long plates [seen step 11, p. 15], and the frame covered with
  overlapping plate layers.
- The body: pins across the beams, then plates over everything.

**4. How the outside attaches.**

- **Underside of the body:** a pre-built light-blue panel of curved slopes on a plate frame. It is
  flipped and pushed onto the body from below [seen step 63, pp. 39–40].
- **Orange breast:** a shingled panel of wedge plates and slopes over tan plates, built separately and
  fixed on the front [seen steps 79–80 and 100, pp. 44 and 51].
- **Back of the body:** blue curved slopes and tiles fixed sideways [seen steps 101–102, pp. 51–52].

**5. What is built separately and attached.**

- **The body**, which plugs onto the support arm with a Technic pin and an angled connector [seen step 67,
  p. 40].
- **Two wings, built as mirror pairs** [seen steps 82–151, pp. 46–72]. Each wing has a shoulder block
  with white bricks with side studs, carrying many feather units. Each feather unit is a few plates and
  inverted slopes under one long curved slope, with a lighter-blue tip on a jumper plate. Small grey
  fittings are pressed into the undersides of inverted slopes, and the feathers hang on them, fanned at
  different angles [seen steps 94–99, 103–112, 141–149]. At booklet scale I could not tell which part
  these fittings are: they could be clips, small bars or ball fittings.
- **Two feet**, made of tan claw pieces on clips [seen step 81, p. 45].
- **The head**, built separately [seen steps 162–171, pp. 77–80]. The beak is two long dark wedges. The
  cheek is a panel fixed with brackets. A white throat tile sits in front. The head goes onto the body on
  a Technic axle 3 with a bush (LDraw 4519 exists), so it can be turned [seen steps 170–172, p. 80].
- **Two reeds:** stacked round bricks on Technic pins and curved stems [seen steps 173–174, p. 82].
- **A small fish** in the beak [seen step 175].

**6. What moves.** The head turns on its axle, and the wings can be set at an angle [seen; how freely they
move I did not establish]. I saw no mechanism.

**7. Inside.** Blue under the water tiles, red and tan inside the body [seen pp. 19–20, 35–40]. The body is
mostly solid. The base is solid plates over a Technic frame.

**8. What sets the scale.** The real bird, at roughly life size: the booklet gives the real bird as about
18 cm long [seen p. 5]. Inside the model, the long curved slope that each feather is made of sets the
size of everything round it.

**9. The order of the build.** Stand and base first, from the bottom up. Then the body, from the inside
out: pinned core, plates, panels. Then the left and right wings in mirror steps (one wing is about 30
steps, then the same again mirrored). Then the head, the reeds and the fish. Each step adds 1 to 8 parts.

**10. Named techniques.**

- **A hidden Technic support arm:** the bird is cantilevered off the stand.
- **Shingled panels:** wedge plates overlapping like roof tiles to make feathers.
- **A curved oval rim** built from slopes on side studs.
- **Fanned feathers** on small angled fittings.
- **A head on an axle**, so it turns.

---

## 4. 75318 The Child (large brick-built character)

**1. The set.** 2020, 1,073 parts, about 20 cm tall [recalled]. The booklet has eight bags [seen p. 5].

**2. What is built first: a Technic tower** [seen steps 1–30, pp. 6–22]. This is core type **(c)**. Its
base is Technic bricks with holes and an open-centre Technic frame (7 × 5; LDraw 64179 exists). Two
15-long Technic beams (LDraw 32278 exists) stand upright on it as posts, and more open frames and Technic
bricks are pinned across the posts at two heights, which makes a cage of three floors. Plates close the
top, and an axle put crosswise through the top holds the joint piece that becomes the socket for the
head [seen step 19, p. 16].

The core is a hollow box about 8 × 8 studs and 12 bricks tall. It is roughly 60% of the body's height and
about half its width, and it is finished in bag 1 (30 steps, roughly 10% of the parts).

**3. How the core is made strong.** It is a box frame of closed rectangles:

- the open-centre frames are rigid rectangles pinned to the posts at three heights;
- the pins are friction pins;
- the plates on top lock it [seen steps 5–18].

**4. How the outside attaches.** The robe is four large tan panels, one per side, each built flat with its
studs up and then mounted sideways on the tower [seen bag 2, steps 31–70, pp. 23–42; bag 3, pp. 43–61; bag
4, p. 62 on].

- Each panel is a 6 × 8 or 8 × 8 base plate covered with plates in steps 1 to 3 plates high. Wedges and
  slopes make the folds of the cloth.
- Each panel has grey Technic bricks or brackets at its edge, which tie it to the tower [seen pp. 23–29].
- The panel's studs face outward on purpose: the robe looks textured with studs showing [seen p. 152].
- Adjacent panels overlap at the corners, and a narrow strip of plates closes each corner [seen step 110,
  p. 61].
- The skin is 2 to 4 plates thick: about one stud of depth with studs out.

**5. What is built separately and attached.**

- **The four robe panels.**
- **Two arms**, not mirrored: one sleeve lies against the body [seen step 207, p. 100] and the other
  holds a ball knob [seen steps 252–253 and 365, pp. 113 and 153]. The sleeves are built round
  side-stud bricks [seen step 226, p. 106]. The hands go on with a small clip or bar [seen p. 113].
- **The head** [bag 7, steps 254–364, pp. 114–152]:
  - The head core: dark-grey plates and bricks with side studs, in a box about 6 × 4 studs and 3 bricks
    tall. Red filler plates sit inside. Grey plates with clips sit on both sides as the ear mounts [seen
    steps 255–271].
  - The skin: green plates and curved slopes, built outward on all sides of that core [seen steps
    272–288].
  - The eyes: large black dish-like pieces on round plates. The booklet shows which way the printed
    highlight must face [seen step 285, p. 123].
  - The ears: long assemblies of plates, curved slopes and tan side-stud bricks for the inner ear. They
    hang on the head core's clips [seen steps 301–328, pp. 129–136].
  - The finished head is lowered onto the black joint at the top of the tower [seen step 364, p. 152].
- **A display plaque**, built separately [seen steps 366–373].

**6. What moves.** The arm holding the knob turns; the booklet draws a yellow arrow [seen p. 153]. The
ears are on clip hinges, and the head sits on a joint [seen]. A lever at the back moves the head and ears
[recalled; not seen in the pages I read]. Any mechanism sits inside the Technic tower, and the axle at the
top carries the head.

**7. Inside.** The core shows in white, yellow, red, grey and black Technic colours, and red plates fill
the head core. The body is hollow inside the tower [seen].

**8. What sets the scale.** Life size of the character [recalled]. The size of the head sets the width of
the body.

**9. The order of the build.**

1. The core tower, bottom up.
2. The robe panels, one bag each, each built flat and then turned onto one side.
3. The arms.
4. The head core, its skin, the eyes, and the ears as two long sub-assemblies.
5. The head on the body, then the knob and the plaque.

Each step adds 1 to 5 parts; the panels go on with many small steps.

**10. Named techniques.**

- **A Technic box frame as the core.**
- **Studs-out panels** built flat and mounted sideways.
- **Stepped plates and wedges** for cloth folds.
- **Clip hinges** for the ears.
- **Inner-colour filler.**

---

## 5. 75328 The Mandalorian Helmet (display object with curved surfaces all round)

**1. The set.** 2022, 584 parts [seen on the instructions page], about 20 cm tall on its stand
[recalled]. The booklet has five bags [seen p. 5].

**2. What is built first: a box core of side-stud bricks and brackets** [seen bag 1, steps 1–38, pp.
6–28]. This is core type **(b)**.

- It starts on a 6 × 6 tan plate. Plates carrying clips at the front corners are added (yellow, a filler
  colour).
- Red and grey bricks with studs on one side are stacked in columns at the corners, facing outward.
- Brackets, both 1 × 2 – 2 × 2 and 1 × 2 – 1 × 2 (LDraw 99207, 44728, 99780 and 99781 exist), point side
  studs to the left, right and front.
- Slopes and plates in many filler colours (orange, light blue, green, white, tan) fill the gaps.
- A second 6 × 6 plate closes the first storey [seen step 18]. The second storey is built the same way and
  capped with frames of plates [seen steps 34–38].

The core is about 6 × 8 studs and 8 to 9 bricks tall, about half the helmet's width. It is a hollow box,
open in the middle where nothing will show [seen steps 31–33, p. 25]. Bag 1 is about 20% of the parts.

**3. How the core is made strong.**

- Each storey is closed by a 6 × 6 plate.
- Long plates run across the top in a frame [seen steps 34–38].
- The side-stud columns are stacked in pairs and locked by plates above and below.

**4. How the outside attaches.**

- **The dome:** separate shells made of plates stacked studs-up in shrinking outlines: each layer is a
  little smaller than the one below, like contour lines [seen steps 56–62 and 69–76, pp. 35–42]. The side
  shells are built "2x" as a mirror pair and fixed sideways onto the core's side studs [seen step 77, p.
  42]. The dome is therefore studs-out on all sides: its curve is a stepped stack of plates, smoothed only
  where needed.
- **The crest along the top:** a strip of curved slopes in a contrasting colour, laid over the steps
  [seen steps 52–53 and 63–66, pp. 33–37].
- **The lower face:** panels built flat (plates, wedge plates, curved slopes and quarter-circle plates)
  and hung from plates with clips onto bars, or fixed onto brackets [seen steps 129–139 and 179–189, pp.
  73–76 and 97–100].
- **The T-visor:** a frame of 1 × 2 × 2 panels with dark tiles on it [seen steps 156–160, pp. 85–87].

**5. What is built separately and attached.**

- Two dome side shells (a mirror pair).
- The top shell.
- The left and right cheek pieces, which are not identical [seen pp. 73–74].
- The visor frame and the chin panel.
- The stand: a black base of slopes round a spine of two yellow 9-long Technic beams on an axle, which
  plugs into the core's underside [seen steps 89–95, pp. 49–52].

**6. What moves.** Nothing.

**7. Inside.** The core is entirely in filler colours, and they show through the eye slit at the back
during the build [seen p. 59]. The core is hollow, and the dome shells are hollow behind their 2-to-4-plate
skin [seen].

**8. What sets the scale.** Roughly one-third life size [recalled]. Inside the model, the width of the
side-stud core sets the size of the dome.

**9. The order of the build.**

1. The core, bottom up.
2. The dome: top shell first, then the side shells as a mirror pair.
3. The stand, and then the helmet is turned upside down so the stand can be fixed into its underside
   [seen pp. 57–58].
4. The cheeks, the visor and the chin, each as a panel.

Each step adds 1 to 6 parts.

**10. Named techniques.**

- **A side-stud box core.**
- **Contour-stacked plate shells**, studs out, mounted sideways.
- **A smooth crest strip** over a stepped dome.
- **Panels hung on clip-and-bar.**
- **A Technic beam spine** inside the stand.
- **Building upside down** to fit the stand.

---

## The category questions

### The inner core in detail

| Set (parts) | Core | Size against the model | Solid or hollow | Hidden colours |
|---|---|---|---|---|
| Kitten (≈120) | Eight 1 × 1 side-stud bricks round one 1 × 1 brick, 2 layers: 3 × 3 studs | Head core is ~75% of the head's width; skin ~½ stud | solid | yes |
| Stitch, sitting cat (≈150–200) | Twelve 1 × 2 × 1⅔ bricks with 4 side studs round a 2 × 2 column, 2 layers: 4 × 4 studs | ~65% of the head's width; skin ~1 plate to ½ stud | solid | yes |
| Helmet (584) | Two storeys of side-stud brick columns and brackets on 6 × 6 plates: 6 × 8 studs | ~50% of the width | hollow box | yes, many |
| Kingfisher (≈834) | Stand: a Technic brick-and-beam frame with an arm. Body: a small pinned beam block | body core ~⅓ of the body | solid | yes |
| The Child (1,073) | A Technic tower of beams, open frames and Technic bricks; a separate side-stud head core | ~50% of the width, 60% of the height | hollow cage | yes |

In every set, side studs are what let parts attach all round. At BrickHeadz size they come from one
special brick: 22885 at 4 × 4, and 1 × 1 side-stud bricks at 3 × 3. At larger sizes they come from
columns of side-stud bricks and brackets, or from Technic bricks and frames, whose pin holes give pinned
joints sideways [all seen].

### Rounded surfaces from flat panels

- Each face of the core gets its own panel, built flat with its studs up and then turned 90° [seen in all
  five sets].
- A panel is rounded in one of two ways. Small figures use curved slopes on top of the panel (Stitch,
  cats). Large ones use a stepped stack of plates in shrinking outlines, studs out (helmet dome, robe of
  The Child), with curved slopes only on prominent lines such as the helmet's crest [seen].
- Panels meet at square corners. The corner is softened with cheese slopes, quarter-round tiles or curved
  bricks (small sets), or the panels overlap and a strip closes the corner (large sets) [seen].
- The skin is about one plate to half a stud thick on BrickHeadz figures, and 2 to 4 plates (about 1 stud)
  on large models [seen].

### Faces at each size

- **Around 120 to 200 parts:** a separate face panel of about 10 to 20 parts on a 3 × 4 to 4 × 6 plate
  base. Printed round 1 × 1 tiles make the eyes. The nose is a 1 × 1 tile or slope, or a small dome, often
  centred with a jumper plate. Whiskers and similar details are bar-like elements. Ears are slopes on top
  or on side studs [seen 40674, 40441].
- **Around 800 parts (bird):** a separate head of about 40 parts. The beak is long wedges, the cheek is a
  bracketed panel and the eye is a printed or round part. The head is attached on an axle [seen 10331].
- **Around 1,000 parts and more:** the head is its own sub-model of 100+ parts, with its own side-stud
  core. Large printed dish-type eyes need a set orientation, and the brows and mouth are built from curved
  slopes. The ears are long sub-assemblies on clip hinges [seen 75318].
- **Printed against built:** the eyes are printed at every size. Everything else is built.

### Limbs, tails, ears and other thin features

- Plates with a clip hung on a bar give a hinge: the cats' tails, The Child's ears, the helmet's chin
  panel [seen].
- Plates with a side stud, or 1 × 1 side-stud bricks, carry small features: the cats' paws, Stitch's ears
  [seen].
- A Technic pin or axle carries anything heavy or turning: the kingfisher's body on its arm, the head on
  its axle, The Child's head on its joint [seen].
- The kingfisher's feathers hang on small fittings, which I could not identify [seen, part uncertain].
- Posable: the tails, the ears of The Child, its arm, and the kingfisher's head and feathers.

### Symmetry

- Left and right are built as mirror pairs one after the other (cat hind legs, kingfisher wings, helmet
  dome shells) or once marked "2x" when identical (cat front legs, haunches) [seen].
- Symmetry is broken on purpose: The Child's two arms differ; the helmet's cheeks and its stand's plaque
  sit on one side; the kingfisher's head is turned and its wings are set at different angles [seen].

### How the models stand

- **BrickHeadz:** the legs press onto a plate base. The weight is low, in a solid body under a large head
  [seen].
- **The Child:** the solid-looking robe sits on the core's base frame, and the weight is in the frame
  [seen].
- **Kingfisher:** a heavy plate base with a Technic arm that cantilevers the bird [seen].
- **Helmet:** a stand with a Technic beam spine plugs into the core's underside [seen].

### 150 parts against 1,000 parts for the same kind of subject

At about 150 parts:

- one template core;
- one face panel and four side panels;
- details from slopes and printed tiles;
- no pins.

At about 1,000 parts:

- a Technic frame as the core (a beam cage or a long brick frame);
- each side panel becomes a large flat build of 30 to 40 steps, studs out, with folds;
- the head becomes its own model with its own side-stud core;
- joints become Technic pins and axles;
- moving parts appear.

**The smallest all-round sideways core seen is the kitten's 3 × 3 ring of 1 × 1 side-stud bricks, at
about 120 parts.** Below that I have no evidence. At that size the kitten's body is plain stacked bricks
with one bracket, so even there only the head gets the all-round core. A pin-and-beam core appeared only
from about 800 parts (kingfisher and The Child), and in the kingfisher it holds the stand and a small
body block, not the whole bird. The 584-part helmet still uses a side-stud brick box, not Technic, except
in the stand's spine.

### What a program that stacks bricks studs-up from the bottom would have to do differently

1. **Build a core first and the shape second.** Stack a small, strong core in hidden colours. Make it
   solid at small sizes and a hollow box or Technic cage at large ones, and give it side studs or pin
   holes on every face that will carry skin.
2. **Build each side as a flat panel and turn it.** Front, left, right, back and top are separate flat
   builds with their studs up, rotated 90° and attached to the core's side studs. The program needs a
   notion of a sub-assembly with its own "up" and a joint to the core.
3. **Round the surface panel by panel.** Within a panel, use curved slopes on the outer layer, or plates in
   shrinking outlines. Close the corners between panels with cheese slopes or quarter tiles.
4. **Treat thin parts as separate sub-assemblies on joints.** Ears, tails, limbs, feathers and heads go
   on a clip and bar, a side stud, a pin or an axle, never in the stack itself.
5. **Build in mirror pairs.** Build one side, then mirror it, and break symmetry only on purpose.
6. **Hide the core.** Choose colours only for what will show; the inside can be any colour.
7. **Plan the stand.** Above a few hundred parts, add a beam spine or arm from the base into the core.

---

## Rules of thumb (with evidence and counter-examples)

1. **Every face that is not on top hangs on side studs.** Seen in all five sets. I saw no counter-example
   apart from the BrickHeadz legs, which are plain stacks.
2. **A head always gets its own all-round core**, even when the body does not (kitten, The Child) [seen].
3. **Core size steps up with model size:**
   - 3 × 3 core of 1 × 1 side-stud bricks at about 120 parts;
   - 4 × 4 core of 22885-type bricks at about 150 to 250 parts;
   - a storeyed side-stud box at about 600 parts;
   - a Technic cage from about 800 to 1,000 parts.
   The counter-example is the kingfisher, whose Technic part holds the stand, not the bird.
4. **Long things that must not bend get Technic:** stand arms, a reed's stem, the helmet's stand spine
   [seen].
5. **Anything that should move or tilt is its own sub-assembly on a clip hinge or an axle** (tails, ears,
   the head, the arm) [seen].
6. **Long plates cross every join between storeys:** 6 × 6 plates in the helmet, 4 × 4 plates on The
   Child's tower, long plates locking the kingfisher's frame [seen].
7. **Mirror pairs are built one after the other**; identical parts are shown once with "2x" [seen in all
   five].
8. **Hidden parts are in non-display colours, and the display colour starts at the skin** [seen in all
   five].

## Playbook for a new subject (for example, a sitting dog or an owl)

### About 100 parts (BrickHeadz-style)

1. Lay the base of the body: two 2 × 4 plates joined by a plate.
2. Build the body as a 4 × 4 or 4 × 6 stack of bricks and plates. Put a bracket or 1 × 1 side-stud brick
   wherever an arm, paw or chest panel must attach.
3. Cap the body with a plate that overlaps the joint below.
4. Build the head core: a 3 × 3 ring of 1 × 1 bricks with studs on one or two sides (87087, 26604, 4733)
   round one 1 × 1 brick in a hidden colour, two layers high. Cap it with a plate.
5. Build the face as a separate 3 × 4 plate panel. Add two printed round 1 × 1 eye tiles (or plain round
   tiles), a nose tile on a jumper plate, and a slope or curved slope for the muzzle. Press it on the
   core's front studs.
6. Build the left and right head panels as a mirror pair: a plate base with tiles or curved slopes. Press
   them on.
7. Put the ears on top as slopes on a 1 × 2 plate, mirrored.
8. Hang the tail on a clip-and-bar joint at the back.
9. Build the legs as plate stacks and fix them to a small plate base.

### About 400 parts

1. Build the core box: a 6 × 6 or 6 × 8 plate, then columns of 1 × 2 × 1⅔ side-stud bricks (22885) or
   1 × 2 bricks with studs on their sides (52107) at the corners, and brackets (99780, 99207) facing
   left, right and front. Use hidden colours. Close each storey with a plate across it, and make two
   storeys.
2. If the model stands on a stand or is taller than about 15 cm, add a spine: Technic beams or Technic
   bricks pinned together, running from the base into the core.
3. Build the head core the same way, one storey smaller, and fix it on the body core.
4. For each side of the body and head, build a flat panel with its studs up: a base plate, then plates in
   shrinking outlines to give the curve, with curved slopes along prominent lines. Build left and right
   as mirror pairs. Mount each panel sideways on the core's side studs.
5. Close the corners between panels with cheese slopes, quarter-round tiles or a strip of plates.
6. Build the face as its own panel: printed or round eyes, a nose or beak from wedges or slopes. Mount it
   on the front of the head core.
7. Build ears, wings, limbs and tails as separate sub-assemblies. Join them with clip-and-bar hinges
   (posable) or side studs (fixed), and use Technic pins or axles for anything heavy.
8. Build the base or stand, and fix the model to it through the spine or the legs.

## The part vocabulary, by job

The numbers below were checked in the project's LDraw search. Whether a given set uses them was judged
from the drawings.

- **Core, sideways:**
  - Brick 1 × 2 × 1.667 with studs on 1 side (22885)
  - Brick 1 × 1 with stud on 1 side (87087)
  - Brick 1 × 1 with studs on two adjacent sides (26604)
  - Brick 1 × 1 with studs on four sides (4733)
  - Brick 1 × 2 with studs on sides (52107)
  - Brick 1 × 4 with studs on side (30414)
  - Brick 1 × 1 with headlight (4070)
  - Brackets 1 × 2 – 1 × 2 up and down (99780, 99781)
  - Brackets 1 × 2 – 2 × 2 up and down (99207, 44728)
- **Core, Technic:**
  - Technic brick 1 × 16 (3703), 1 × 2 (3700) and 1 × 1 (6541) with holes
  - Technic beam 15 (32278), beam 3 (32523), beam 3 × 5 bent 90 (32526)
  - Technic beam 7 × 5 open centre (64179)
  - Friction pins (2780) and long pins (6558)
  - Axle 3 (4519)
- **Lock:** long plates and 6 × 6 or 4 × 4 plates across storeys (numbers not checked).
- **Angle and joint:**
  - Plate 1 × 2 with clip on end (63868)
  - Plate 1 × 1 with clip (61252)
  - Plate 1 × 2 with handle on end, a bar (60478)
  - Plate 1 × 1 round with handle (26047)
  - Tile 1 × 1 with clip (15712)
- **Skin, curve:**
  - Curved slope 2 × 1 (11477)
  - Curved slope 2 × 2 × ⅔ (15068)
  - Slope 31 1 × 2 × ⅔ (85984)
  - Slope 45 2 × 1 (3040) and inverted (3665)
  - Brick 2 × 1 × 1⅓ with curved top (6091)
  - Wedge plates and cheese slopes (not checked)
- **Detail:**
  - Round tile 1 × 1 (98138; the printed eye versions are patterned and left out of the index)
  - Dish 2 × 2 (2654)
  - Jumper plates (not checked)

## What I could not find out

- **Exact part lists and counts.** Rebrickable refused automated access, so I could not confirm which
  parts the sets use or their exact numbers (for example, 40674's part count, and the identity of the
  kingfisher's feather fittings).
- **The Child's mechanism.** I did not read the pages that would show it (pp. 65–80 and 85–96). Those
  pages are the next thing to read, along with the kingfisher's pp. 57–60 and 73–76, which hold the
  wing-to-body joint.
- **Anything below about 120 parts.** A small Creator 3-in-1 animal or a BrickHeadz key-chain would show
  what replaces the side-stud core there.
- **A Creator Expert or Ideas animal of 300 to 600 parts**, for example an owl or a parrot, would show
  whether a side-stud box core or a Technic core is used at that size for a creature. The helmet suggests
  side-stud bricks.
