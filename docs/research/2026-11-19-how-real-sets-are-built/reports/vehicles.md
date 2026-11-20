# How official LEGO vehicles are built: ordinary studded vehicles, small to medium

> **Editor's note.** This is one of the eight reports behind the study in `../README.md`, kept as its evidence. It is as its researcher wrote it, except for what this note lists. Points where the reports disagree with each other are dealt with in the README, not corrected here.
> Changed: nothing but this note.

Category: `vehicles` (not Technic). Four official sets, all studied from LEGO's own instruction PDFs.

## Sources and method

- LEGO's service page (`lego.com/service/buildinginstructions/<set>`) refused a plain `curl` request
  (Cloudflare block page, HTTP 403). I did not try to get round that. The WebFetch tool could read
  the page and gave the PDF links. The PDFs themselves are on LEGO's CDN
  (`lego.com/cdn/product-assets/product.bi.core.pdf/<id>.pdf`) and downloaded normally with a
  plain generic client name. Six files in all.
- I turned the pages into contact sheets (four pages to an image) with a script kept outside the
  download folders, then looked at them with the Read tool.
- Rebrickable returned HTTP 402 and BrickLink's inventory page came back empty, so **no part number
  in this report comes from a set inventory**. Numbers come only from the project's LDraw part
  search (`bricksnap/lab/search.py`). That search shows the part exists. Whether it is the exact
  part in the set is marked in each case.
- Markers: **[seen p. X]** means I saw it on that booklet page (page numbers printed on the page);
  **[recalled]** means general knowledge I did not check. I used no reviews.

| Set | Name, year | Parts | Booklet pages read |
|---|---|---|---|
| 60312 | City Police Car, 2022 | 94 | all 48 of 48 (single booklet) |
| 60412 | City 4x4 Fire Truck with Rescue Boat, 2024 | 301 (the truck is booklet 1, bags 1-2) | booklet 1: 68 of 72; booklet 2 (boat and trailer): cover only; booklet 3: not read |
| 76914 | Speed Champions Ferrari 812 Competizione, 2023 | 261 | 80 of 92 (pages 1-60, 65-72, 77-88) |
| 31146 | Creator 3-in-1 Flatbed Truck with Helicopter, 2024 (main model) | 270 (whole set) | booklet 1 of 3: 40 of 68 (pages 1-32, 37-40, 65-68). Tractor unit read closely; trailer sampled; helicopter only seen in the last picture |

Speed Champions sets are all licensed, so a licensed car was unavoidable there. The other three
are LEGO's own themes.

---

## Set 1: 60312 Police Car (2022, 94 parts)

**1. Set.** A minifigure-scale police sports car, about 6 studs wide and roughly 12 long (estimated
from the drawings). Booklet read in full.

**2. What is built first: (d), a large moulded chassis part.** Step 1 is a single black moulded car
base: 4 studs wide in the middle, about 10-12 long, with raised blocks at the four corners that
carry wheel pins moulded in [seen p. 6]. Steps 2-6 fill its open centre and ends with plates and
bricks and add the seat and steering wheel [seen pp. 7-11]. Steps 7-8 put the two body sides on
and lock them, so the core is done by about step 8 of 38, with roughly a fifth of the parts.

**3. Strength.** The moulded chassis does most of the work. Above it, two long 1x6 plates are laid
across the tops of the two side sub-assemblies and the filler bricks, which turns the sides and
centre into one frame round the cockpit [seen p. 14, step 8]. Coloured 2x4 and 2x3 plates bridge
the joints between chassis blocks [seen pp. 7-9].

**4. Outside to core.**
- Body sides: mirrored sub-assemblies, each an inverted slope with a printed "POLICE" brick on it
  and a white L-shaped panel behind, put on studs pointing up [seen pp. 12-13, step 7, "x2"].
- Front and rear faces: a brick 1x4 with studs on its side (LDraw `30414`, "Brick 1 x 4 with Studs
  on Side"; the shape matches, not checked against the set's list) stands across each end on a 1x4
  plate [seen p. 18 rear, p. 26 front]. A face sub-assembly is pressed onto its side studs: a plate
  with round tail lights or headlights at the corners and a grille tile in the middle [seen pp.
  19-20 rear; pp. 30-34 front].
- The push bar on the front hangs from two plates with clips on top [seen p. 33, steps 28-30].
- Bonnet: plates offset by jumper plates (a 1x3 plate with 2 studs, LDraw `34103` "Plate 1 x 3 with
  2 Studs Offset"; shape matches), then grille tiles and curved slopes [seen pp. 28-29, 37-38].
- Curves: 2x1 curved slopes on the wings and bonnet, white curved slopes for the stripes, and a
  white curved roof wedge [seen pp. 22-23, 37-40].

**5. Built separately.** The two body sides (twice, mirrored) [seen p. 12-13]. The rear face [seen
p. 19-20]. The front face with its push bar [seen pp. 30-34]. The roof with the light bar (a curved
roof wedge with two studs and a transparent 1x4 tile) [seen p. 40]. The four wheels, each a rim
pressed into a tyre [seen p. 41, "4x"].

**6. What moves.** The wheels turn on the chassis's wheel pins. The roof lifts off: it sits only on
the two top studs of the two windscreen pieces [seen p. 43, green two-way arrows]. **No hinges
anywhere.**

**7. Inside.** Hidden filler parts are in loud colours: green, orange, tan, red, yellow and light
grey [seen pp. 8-11]. Almost none of them shows on the finished car. The centre of the car is a
hollow cockpit for the minifigure.

**8. Scale.** The minifigure (it has to sit in the 4-wide cockpit with a steering wheel in front)
and the moulded chassis, whose wheel pins fix the wheelbase. The windscreens are two separate
corner windscreen parts, one each side, not one wide windscreen [seen p. 39, "2x"].

**9. Order.** Chassis → interior and seat → body sides → frame-locking plates → front wheel arches
→ rear face → rear deck and rear arches → front face → bonnet → windscreens → roof → wheels → the
bonnet air scoop last, after the wheels [seen pp. 6-42]. One to four parts per step, often a
mirrored pair.

**10. Techniques.** A moulded chassis with wheel pins; a mirrored side sub-assembly; long plates
locking a frame; side-stud bricks for both end faces; clip plates for a bar accessory; jumper
plates for half-stud centring on the bonnet; a roof that lifts off on studs.

---

## Set 2: 60412 4x4 Fire Truck (2024; truck = booklet 1, 72 pages)

**1. Set.** A 6-stud-wide off-road fire truck on large balloon tyres, about 14-16 studs long. The
boat and trailer in booklet 2 are left out.

**2. What is built first: (a), a stack of plates, a "spine and floor" sandwich.** Step 1 is a single
2x16 plate. At each end of it go plates with wheel pins on their sides (they look like
2x4-wide wheel-holder plates, two pins each) [seen pp. 7-8, 11]. A 4x4 frame plate (a plate with a
hole in the middle) and small plates follow [seen pp. 9-10]. A long 2-wide brick runs down the
spine [seen p. 13, step 10]. Then **one large black plate, about 6x8, is laid across the narrow
spine, making a 6-wide floor** [seen p. 20, step 20]. The core is done at step 20 of 66, with
roughly 15-20% of the truck's parts.

**3. Strength.** Layers overlap: wheel-holder plates under the ends of the 2x16 spine; a long brick
on top of the spine; the wide floor plate across everything [seen pp. 7-20]. Higher up, yellow
2x6 and 2x8 plates cap the body side walls, spanning the joints between bricks [seen pp. 28-30].

**4. Outside to core.**
- Running boards: two mirrored sub-assemblies of inverted slopes, plates and tiles, hung under the
  floor plate's edges [seen pp. 14-16, steps 11-14].
- Front face: four light-grey 2x2 bricks with studs on their sides stand at the nose [seen p. 19,
  step 19; p. 49, step 51]. Later a grille sub-assembly is pressed onto them: a plate with round
  white plates for headlights and a grille slope [seen p. 61, step 62]. So does a bumper
  sub-assembly: a 1x4 plate, plates with clips, and a curved slope [seen p. 60, step 61].
- Body: red bricks stacked on studs pointing up, with tiles and curved slopes. Black flared wheel
  arches (a moulded arch with studs on top), one per wheel [seen pp. 26, 35].
- Rear water tanks: two sub-assemblies, each a tan 2x4 plate carrying blue curved bricks, set into
  the sides [seen p. 53, step 55].

**5. Built separately.** Running boards (twice, mirrored) [seen p. 15]. Equipment lockers: two
moulded cupboards with doors [seen p. 50, step 52]. Water tanks (twice) [seen p. 53]. The rear
roof plate with its roof rack [seen pp. 54-58]. The light bar (a 1x6 plate with three transparent
tiles) [seen p. 59]. The bumper [seen p. 60]. The grille [seen p. 61]. The hose reel, on Technic
bricks with pins [seen p. 43, step 45]. Four wheels [seen p. 62].

**6. What moves.**
- The hose reel turns on a pin through two Technic 1x1 bricks with holes, mounted at the rear
  [seen pp. 43-44].
- The locker doors open on the moulded cupboard's own hinge [seen p. 50].
- The cab roof lifts off on two studs to let the minifigure in [seen p. 68].
- A water shooter at the rear [seen pp. 64-67].
- **No hinge parts.**

**7. Inside.** Yellow plates make the whole hidden upper deck [seen pp. 28-41]. There are also blue
2x4 bricks, a lime tile in the frame plate's hole, a tan stack and coloured 1x2 plates in the core
[seen pp. 9-21]. All are covered later.

**8. Scale.** The large balloon tyres decide the ride height and the arch size. The minifigure and
the windscreen part decide the 6-stud width of the cab.

**9. Order.** Spine → running boards → front-face side-stud bricks → floor plate → cab and bonnet
body → interior (seat, steering wheel) → windscreen at the end of bag 1 (step 43). Bag 2: hose reel
→ rear body walls and lockers → rear roof and roof rack → tanks → cab roof → light bar → bumper →
grille → wheels → water shooter [seen pp. 7-66]. Two to four parts per step; the many mirrored pairs
are shown as two identical parts in one step.

**10. Techniques.** A plate sandwich (narrow spine plus wide floor); side-stud bricks for the front
face; mirrored running-board sub-assemblies; moulded cupboards for doors that open; a Technic pin
axle for a turning reel; a roof that lifts off on studs.

---

## Set 3: 76914 Speed Champions Ferrari 812 Competizione (2023, 261 parts)

**1. Set.** An 8-stud-wide sports car, about 18-20 studs long (width [recalled] for Speed Champions
from 2020; it matches the drawings).

**2. What is built first: (d), a large moulded chassis, extended by sub-assemblies.** Step 1 makes a
wheel holder: a black 2x4 brick with raised ends and an axle-pin hole at each end, with two tan
Technic axle pins in it (LDraw has `3749` "Technic Axle Pin"; the colour suggests this part, not
checked) [seen p. 8]. Plates and brackets go on it [seen pp. 8-9]. Then the large black moulded car
base is added. Its long edges carry a row of side features [seen p. 10, step 4], and the wheel
holder sits at its rear end. LDraw `65634` "Car Base 6 x 12 with 6 Studs on Each Side" fits what I
saw, but it is not checked against the set's list.

The chassis is shorter than the car. **The whole front end, with the front wheel pins, is a
separate "nose" sub-assembly pressed onto the front of the chassis** [seen pp. 46-50, steps 43-51].
In this set the core is the chassis plus the two wheel holders. Bag 1 (steps 1-36, about half the
parts) builds that core and the complete rear half of the body [seen pp. 6-39].

**3. Strength.** The moulded chassis carries the load. Plates lock the wheel-holder units to it [seen
pp. 10-12]. The nose sub-assembly is tied in by plates laid across the join and by a 2x4 brick on
top [seen pp. 51-52, steps 52-53]. Long plates across the cockpit floor tie the two sides together
[seen p. 54, step 55].

**4. Outside to core.** Most of the outer skin is put on sideways:
- Side sills: each is a long red tile on a row of black brackets, made separately and pressed onto
  the chassis's side features [seen pp. 36-39, steps 35-36, "3x" brackets each].
- Side intakes and door panels: wedge plates fixed upright on the side studs of brackets and of
  1x1 bricks with a stud on one side [seen pp. 57-60, steps 58-61].
- Rear light clusters: two mirrored sub-assemblies of side-stud bricks, wedges and round lenses,
  each fitted with a sticker [seen pp. 22-25, steps 24-25].
- Rear diffuser and exhausts: a sub-assembly of brackets and bar holders [seen pp. 20-21, step 23].
- Rear face: a plate-and-tile panel with stickers, built on its own and pressed on [seen pp. 29-31,
  step 30].
- Bonnet: a sub-assembly built upside down (wedge, plates, a curved tile with a sticker) and put on
  the nose in one piece [seen pp. 77-80, steps 76-82].
- Wheel arches: moulded red arches with studs on top, capped with curved slopes and tiles [seen pp.
  15-16, 66-70].
- Curves come from curved slopes, wedges with stickers on them, and a large printed canopy that
  serves as windscreen, side windows and roof all at once [seen pp. 32-34, 84-86].

**5. Built separately.** The rear wheel holder [p. 8]. The diffuser and exhausts [p. 20]. The rear
lights (twice, mirrored) [pp. 22-25]. The rear face panel [pp. 29-31]. The engine-cover parts [pp.
32-34]. The side sills (twice) [pp. 36-39]. The nose with the front wheel holder [pp. 46-50]. The
front corner lights (twice, mirrored) [pp. 65-68]. The bonnet [pp. 77-80]. Four wheels, each a hub
cap pressed into a tyre [p. 85].

**6. What moves.** The wheels. The canopy lifts off on studs so the driver can be put in [seen pp.
86-87, red boxes]. **No hinges, no opening doors.**

**7. Inside.** Yellow and light-grey plates and bricks fill the hidden centre and the underside of
the nose [seen pp. 10-12, 49-54, 71-72]. Black and dark grey are used where the inside shows
through the canopy.

**8. Scale.** The width: 8 studs, so that a minifigure fits beside the stub-axle wheel holders
[recalled for the reason; the width was seen]. The wheel and tyre size and the moulded wheel arches
fix the arch spacing.

**9. Order.** By halves, not by layers. Bag 1: rear wheel holder → chassis → interior floor → rear
arches → rear deck → rear lights and diffuser → rear face → engine cover → side sills. Bag 2: cockpit
seats and steering wheel → nose with front wheel holder → cockpit floor → side intakes and doors →
front lights → front arches → bonnet → mirrors → canopy → wheels last [seen pp. 8-85]. One to four
parts per step, plus many 3-6-part sub-assembly call-outs. Mirrored sub-assemblies are drawn twice
(once each).

**10. Techniques.** A moulded chassis lengthened by a plugged-on nose; stub-axle wheel holders on
Technic axle pins; heavy sideways building on brackets and side-stud bricks (sills, intakes, lights,
rear face); wedge plates set upright to make angled side surfaces; a bonnet built upside down as
one unit; stickers standing in for vents, badges and stripes (22 or more stickers [seen, numbered
up to 22 on p. 50]).

---

## Set 4: 31146 Creator 3-in-1 Flatbed Truck with Helicopter (2024, main model)

**1. Set.** An American-style tractor unit, 4 studs wide, with three axles. It pulls a flatbed
trailer that carries a helicopter. No minifigure. I read the tractor closely and sampled the trailer.

**2. What is built first: (a), a plate sandwich spine.** A light-grey 2x16 plate with a black 2x16
plate under it, offset so the two overlap [seen p. 5, steps 2-3]. Plates with wheel pins go under
and over it (2x2 plates with two wheel pins look right: LDraw `4600`/`4870`; not checked) [seen pp.
6-8]. Then 2x6, 4x4 and 2x10 plates are stacked on top to widen the cab area to 4 studs [seen pp.
9-10]. The core is done by about step 11 of 41 for the tractor, with roughly 30 parts.

**3. Strength.** Two full-length plates overlapped, then shorter plates across their joins on top
[seen pp. 5-10]. The cab is a closed box: brick walls of transparent and black bricks, capped by a
1x6 tile and plates [seen pp. 17-19].

**4. Outside to core.**
- Fuel tanks: mirrored sub-assemblies, each a 1x4 bracket carrying a red 1x4 plate and a grey curved
  slope, fixed sideways [seen p. 7, step 6, "2x"].
- Cab sides: mirrored sub-assemblies on 1x1 bricks with studs on four sides (LDraw `4733` "Brick
  1 x 1 with Studs on Four Sides"; shape matches), with slopes and tiles, set into the cab corners
  [seen pp. 21-22, steps 29-30].
- Grille: a separate sub-assembly of stacked plates and grille-pattern tiles making vertical
  slats, pressed onto the nose [seen pp. 25-26, steps 35-39].
- A red tile on the side of the bonnet goes onto side studs [seen p. 27, step 40].
- Exhaust stacks: clips holding bar-type stacks [seen p. 24, step 33].
- Front wheel arches: black moulded arches with studs on top [seen p. 8, step 8].

**5. Built separately.** The fuel tanks (twice) [p. 7]. The cab box [pp. 17-19]. The cab side panels
(twice, mirrored) [pp. 21-22]. The grille [pp. 25-26]. Six wheels, each a hub pressed into a tyre
[p. 28, "6x"]. Trailer: a separate long plate sandwich (2x16 and 2x8 plates) with its own
wheel-holder plates and a sideways rear-light unit on a bracket [seen pp. 29-32].

**6. What moves.** The fifth-wheel coupling on the tractor: a round plate with a pin and a raised
plate for the trailer to turn on [seen pp. 13-14, 17]. The wheels. **No hinges in the tractor.**

**7. Inside.** A tan 2x2 plate and red plates are buried in the spine [seen pp. 7-9]. The cab
interior shows red behind transparent bricks (red tiles behind the windows) [seen pp. 17-18].

**8. Scale.** The 4-stud width: two 1x2 transparent bricks side by side make the windscreen [seen
p. 17, step 21]. The small wheels on 2x2 wheel-pin plates set the height. The Creator model does
not have to hold a minifigure.

**9. Order.** Spine → fuel tanks → wheel mounts and front arches → floor plates → fifth wheel and
the plates behind the cab → cab box (built separately, then placed) → cab side panels → bonnet top
and stacks → grille → wheels last. Then the trailer starts from its own spine [seen pp. 5-32]. One to
three parts per step.

**10. Techniques.** A plate-sandwich spine; brackets for sideways tanks; a cab built as a separate
box; 1x1 bricks with studs on four sides as corner nodes for mirrored side panels; a slatted grille
built from grille tiles; a turning point for the trailer coupling.

---

## Category questions (all four sets)

**Chassis.** Two families.

| Chassis type | Sets | What I saw |
|---|---|---|
| One large moulded chassis | 60312, 76914 | Wheel pins or wheel holders built in or placed at its ends. 76914's chassis is shorter than the car, and the front end is a plugged-on unit. |
| Plate sandwich | 60412, 31146 | One full-length 2x16 plate as a spine; wheel-pin plates under its ends; wider plates laid across on top to make the floor (6 wide in 60412, 4 wide in 31146). In 31146 a second 2x16 plate is laid under the first. |

- The chassis is locked by the plates of the next layer up. In every set the first wide layer
  above the chassis spans the joints below it.
- In no set is the chassis made of Technic beams.

**Wheels.**

| Set | How the wheels are held | Arches and room round the tyre |
|---|---|---|
| 60312 | Wheel pins moulded into the chassis corners [seen p. 6] | Moulded arch pieces with studs on top, one per wheel; the arch sits above the tyre with visible room [seen pp. 15, 24, 41] |
| 76914 | 2x4 wheel-holder bricks with Technic axle pins at both ends, one per axle [seen pp. 8, 46] | Moulded arches, closely fitted [seen p. 85] |
| 60412 | Plates with wheel pins under the spine ends [seen pp. 8, 11] | Black flared arches with clear room over the big tyres [seen p. 63] |
| 31146 | 2x2 plates with two wheel pins [seen pp. 6-8] | Arches only over the front axle; the rear twin axles are open [seen p. 28] |

In every set the wheels push straight onto a pin. **None uses a through-axle brick** (no brick with
an axle hole and a long axle).

**Width.**

| Set | Width in studs | What decides it |
|---|---|---|
| 60312 | 6 | The minifigure in a 4-wide cockpit, plus a 1-stud wall each side |
| 60412 | 6 | The same as 60312 |
| 76914 | 8 | The minifigure plus the wheel holders and sills inside the body [recalled reason] |
| 31146 | 4 | Two 1x2 window bricks side by side. Creator vehicles at this size leave out the minifigure |

**Doors, bonnets, boots, roofs.**
- Across all four sets **not one hinge part was used.** What opens is:
  - a roof or canopy that lifts off on two studs (60312, 60412, 76914);
  - moulded cupboard doors (60412).
- Bonnets and rear panels are separate sub-assemblies that press on and stay fixed (76914, 60312).
- Opening car doors on hinge bricks or door rails do exist in other sets [recalled; for example
  older City cars with moulded 1x4x2 doors, and larger Creator cars]. I did not see them here. The
  project's part search does list "Plate 1 x 2 with Door Rail" (`32028`) and the 2x3x2 cupboard and
  door (`4532`/`4533`); I did not check whether those numbers are the ones in 60412.

**Front and rear faces.** In all four sets a face is built sideways, from parts like these:
- a brick 1x4 with studs on its side (60312, front and rear);
- 2x2 bricks with studs on their sides (60412, front);
- brackets and 1x1 side-stud bricks (76914, 31146);
- a face sub-assembly (lights, grille, bumper) built flat on a plate and pressed onto those side
  studs.

The side-stud bricks are themselves sat on studs pointing up from the chassis or the floor plate,
with a plate or tile above them, so the face is tied back in by the layers above and below.
Bumpers and push bars hang from clip plates (60312, 60412).

**Slopes and curves.**
- Curved slopes (2x1, 4x1, 2x2) for bonnets, wings and roofs (all four sets).
- Inverted slopes for sills and side panels (60312, 60412).
- Wedge plates set upright on side studs for angled side surfaces (76914).
- Moulded curved parts: roof wedge, canopy, windscreens (all four).
- Printing and stickers stand in for shape where the shape is too small to build:

| Set | Printing and stickers |
|---|---|
| 60312 | Printed parts only ("POLICE" bricks) |
| 60412 | Printed parts ("02" slopes, roof badge) |
| 76914 | 22 or more stickers: vents, badges, light outlines, stripes |
| 31146 | None seen |

**Order.**
- The general rule held: chassis first, wheels last.
- Body sides came before the front and rear faces in 60312, 60412 and 31146.
- The roof came near the end, just before the wheels.

Exceptions:
- In 60312 the rear face was built before the front.
- 60312 put the front wheel arches on before the rear face.
- 60312 put the bonnet scoop on after the wheels.
- 76914 builds the car in two halves, rear then front, each half finished to the skin before the
  next.
- 60412 fixes the front-face side-stud bricks into the core (step 19) long before its grille goes
  on (step 62).
- 31146 builds its cab as a separate box and drops it onto the spine.
- 60412 and 31146 put small accessories on after the wheels.

---

## Conclusions across the four sets

**Patterns that held in every set.**
1. The first part placed is the full-length base: a moulded chassis or a 2x16 plate.
2. The wheel attachment comes in the first few steps (wheel pins on the chassis, wheel-pin plates,
   or a wheel-holder brick). The wheels themselves go on last.
3. The first wide layer is plates laid across the base, spanning its joints.
4. Hidden parts are in contrasting colours (yellow, lime, tan, blue, orange, green). The reason —
   to make parts easy to tell apart and to find while building — is [recalled], not stated in the
   booklets.
5. End faces are made sideways on side-stud bricks or brackets fixed into the floor layer.
6. Mirrored left and right sub-assemblies are made twice: body sides, tanks, running boards,
   lights.
7. Nothing on these vehicles uses a hinge. Openings are lift-off roofs on studs, or moulded door
   parts.
8. Steps place one to four parts each. Sub-assemblies have their own numbered sub-steps.

**What changes with size.**

| Size | Sets | Typical build |
|---|---|---|
| Small (about 100 parts) | 60312 | One moulded chassis does almost all the structural work; parts go on in plain layers |
| Medium (250-300) | 60412, 31146, 76914 | A plate-sandwich spine (studded City and Creator trucks), or a moulded chassis lengthened by plug-in sub-assemblies (Speed Champions). Much more sideways building, more and larger sub-assemblies, and bags that split the build into regions |

- **A pin-and-beam core never appeared.** The only Technic parts were axle pins in a wheel holder
  (76914) and a pin for a turning reel (60412).
- For studded vehicles of up to about 300 parts, the core is a moulded chassis or a plate sandwich.
- I saw no set of 1,000 or more parts. The guess that larger studded vehicles bring in Technic
  frames is [recalled] and unchecked.

**Rules of thumb, each with its evidence.**
- *Start from one part as long as the vehicle (or nearly), and put the wheel pins on it first.*
  Seen in all four (moulded chassis, or a 2x16 plate). Counter-case: 76914's chassis is shorter
  than the car and the nose is added later. Even there, the wheel holders come before any body.
- *Widen a narrow spine with one wide plate laid across it.* Seen in 60412 (a 6x8 plate over a 2x16
  spine) and in 31146 (4-wide plates over a 2-wide spine).
- *Cap every wall with plates longer than the bricks below.* Seen in 60312 (1x6 plates over the
  side assemblies), 60412 (yellow 2x6 and 2x8 plates) and 31146 (tile and plates over the cab box).
- *Build each end face as a flat panel and press it onto side studs at the end of the floor.*
  Seen in 60312 (front and rear), 60412 (front), 31146 (grille) and 76914 (rear).
- *Make left and right panels as identical or mirrored sub-assemblies, built twice.* Seen in all
  four.
- *Arches: one moulded arch per wheel, with studs on top for the bodywork above.* Seen in 60312,
  60412 and 76914; 31146 front only.
- *Something that has to open is a lift-off panel on two studs, not a hinge.* Seen in 60312, 60412
  and 76914. Counter-case: the moulded cupboard doors in 60412.
- *Wheels go on last, roof or canopy just before.* Seen in all four. Counter-case: small
  accessories after the wheels (60312, 60412).

---

## Playbook for a new vehicle (not a copy of any set)

### About 100 parts (a car or small van, minifigure scale, 6 studs wide)

1. Place a moulded car base with wheel pins (or, without one, a 4-wide plate the length of the car
   with a 2x2 wheel-pin plate under each end). This fixes length and wheelbase.
2. Fill the base's open areas with plates and small bricks in any hidden colour. Put the seat and
   steering-wheel part on the centreline of the cockpit.
3. Build the left body side as a sub-assembly (a long inverted slope or brick with a panel behind
   it). Build its mirror image for the right. Press both onto the outer stud rows.
4. Lay one long plate along the top of each side so it spans every joint below it, framing the
   cockpit.
5. Put one moulded wheel arch over each wheel position, on studs.
6. Stand a brick with studs on its side across each end of the floor, on a plate.
7. Build each end face flat (a plate with round lights at the corners and a grille tile in the
   middle) and press it onto those side studs.
8. Cover the bonnet and rear deck with plates, using jumper plates where something has to sit
   half a stud over. Finish with curved slopes and tiles.
9. Fit the windscreen part or parts on the cockpit's front edge. Make sure their top studs line up
   with where the roof will sit.
10. Build the roof as one piece (a curved roof part or a plate with tiles) that sits on two studs
    so it lifts off.
11. Push the four wheels onto the pins. Add any small accessories last.

### About 400 parts (a truck, fire engine or large car)

1. Lay a 2x16 plate (or two, end to end with a plate across the joint) as the spine. Put
   wheel-pin plates or wheel-holder bricks under each axle position.
2. Lay a second full-length plate under or over the spine, offset from the first, so no joint lines
   up with another.
3. Hang mirrored running-board or fuel-tank sub-assemblies on the spine's sides (inverted slopes,
   or a bracket with a plate and a curved slope).
4. Fix the front-face nodes now: 2x2 or 1x4 bricks with studs on their sides at the nose (and the
   tail if needed), on the spine plates.
5. Lay one wide plate (6 or 8 wide) across the spine to make the floor, spanning all the joints
   below.
6. Build the cab and bonnet walls in bricks, with hidden colours inside. Cap each wall run with a
   plate longer than any brick beneath it.
7. Build rear bodywork, lockers and tanks as separate sub-assemblies (moulded cupboard and door
   parts for lockers; curved bricks on a plate for tanks). Set them in on studs or side studs.
8. Put a moulded arch over every wheel, or every front wheel on a tractor unit.
9. Build the grille, the bumper and the light clusters flat, as sub-assemblies, and press them onto
   the face nodes from step 4. Hang bars and bumpers from clip plates.
10. For angled side surfaces, fix wedge plates upright on brackets or side-stud bricks.
11. Place the windscreen part. Build the roof as a separate unit on two studs so it lifts off. Add
    the roof rack and light bar on top of it.
12. Add any turning feature on its own pin (a reel through Technic bricks with holes, or a
    turntable or fifth wheel).
13. Push the wheels on last, then the small accessories.

---

## Part vocabulary by job

Numbers are from the project's LDraw search. "Shape matches" means it looks like what I saw in the
booklet, but it is not checked against a set inventory.

| Job | Kinds of part | Numbers |
|---|---|---|
| Core | Moulded car base (one piece) | `65634` Car Base 6 x 12 with 6 Studs on Each Side, shape matches 76914 |
| Core | Long plate for the spine | `4282` Plate 2 x 16 |
| Core | Wide floor plates (6x8, 4x4, 2x10) | |
| Wheel mounts | Plate 2 x 2 with 2 wheel pins | `4600` / `4870`, shape matches 31146 |
| Wheel mounts | Wheel-holder brick 2x4 with Technic axle pins | `3749` Technic Axle Pin, shape matches 76914 |
| Lock | Long plates over walls; a long brick down the spine; plates across chassis joins | |
| Sideways building | Brick 1 x 4 with studs on side | `30414`, shape matches 60312 |
| Sideways building | Brick 1 x 1 with studs on four sides | `4733`, shape matches 31146 |
| Sideways building | Brick 1 x 1 with stud on one side | `87087`, not checked |
| Sideways building | Brackets 1 x 2 - 1 x 2 up and down | `99780` / `99781`, not checked |
| Sideways building | Brackets 1 x 2 - 1 x 4 | `2436b` and others, not checked |
| Sideways building | 2x2 bricks with side studs | not found in the search under that name |
| Angle and curve | Inverted slopes; curved slopes 2 x 1 and 4 x 1 | `11477`, `61678`, not checked |
| Angle and curve | Wedge plates set upright; moulded windscreens and canopies; roof wedge | |
| Joint and opening | Two studs (lift-off roof); moulded cupboard with door | cupboard `4532`/`4533`, not checked |
| Joint and opening | Plate with clip on top plus a bar | `92280` Plate 1 x 2 with Single Clip on Top, not checked |
| Joint and opening | Technic 1x1 brick with hole plus pin (turning reel); round plate with pin (fifth wheel) | |
| Skin | Tiles; curved slopes; printed bricks and slopes; stickers | |
| Skin | Moulded wheel arches with studs on top | `18974` Car Mudguard 4 x 2.5 x 2.333 and others exist, not matched |
| Detail | Grille tiles; round plates as lights | `2412b` Tile 1 x 2 Grille, shape matches 31146 |
| Detail | Jumper plates | `34103` Plate 1 x 3 with 2 Studs Offset, shape matches 60312 |
| Detail | Light-bar tiles; steering-wheel stand; seat | |

---

## What I could not find out, and what to look at next

- **Exact part numbers.** Rebrickable (402) and BrickLink (empty page) gave no inventories. The
  next step is to download each set's parts list another way, or match the element IDs printed on
  the inventory page at the back of each booklet (60312's is on pp. 46-47).
- **Large studded vehicles (1,000 parts and up)**, to see whether a Technic frame appears. The next
  sets to read would be a large Creator Expert or Icons car, and a large City vehicle.
- **Opening doors, bonnets and boots on hinges** did not appear in these four. A Creator 3-in-1 car
  with opening doors, or an older City car with moulded doors, would show the hinge practice.
- **Older Speed Champions (6-wide, before 2020)**, to compare with the 8-wide design.
- The reason for loud hidden colours, and the reason for the Speed Champions width, are
  [recalled]. Designer videos or interviews would confirm them.
- Not read: about 12 pages of 76914 (pages 61-64 and 73-76: mid-front body work), the helicopter in
  31146, and booklet 3 of 60412.
