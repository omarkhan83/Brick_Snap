# How official sets build a frame of beams and pins (category: technic-and-frames)

> **Editor's note.** This is one of the eight reports behind the study in `../README.md`, kept as its evidence. It is as its researcher wrote it, except for what this note lists. Points where the reports disagree with each other are dealt with in the README, not corrected here.
> Changed: one mention of a folder on the researcher's computer was removed.

Study for BrickSnap, 2026-11-19. Five official sets, read from LEGO's own building-instruction PDFs.

## Sources and how they were used

- **The instruction booklets.** The `lego.com/service/buildinginstructions/<set>` page refused a plain
  scripted request (HTTP 403). The same page fetched through the WebFetch tool gave the PDF links. The PDFs
  on LEGO's CDN downloaded normally with a generic client name, one file per set, each in its own folder.
  No disguise was used. The pages were made into contact
  sheets (3 x 3 pages per image) with PyMuPDF, run with `-I` from a separate scripts folder. A few pages
  were zoomed. Nothing was saved into the repository.
- **Brickset.** Set facts (year, piece count, model size) came from `brickset.com/sets/<set>-1`. Part
  names and counts for 10317 came from `brickset.com/inventories/10317-1` (read in four pieces; the
  first and last pieces were not read in full).
- **Rebrickable** refused the request (HTTP 402), so it was not used.
- **Part numbers** were checked with the project's own part search (`bricksnap/lab/search.py`, read-only).
  Only numbers that it returned are given. Brickset's design number counts as a second check where
  noted.
- **How each statement is known.** Each one is marked **[seen]** (in the pages I read; the page number
  is the PDF page, and the step numbers are the booklet's), **[review]** (Brickset), or **[recalled]**
  (general knowledge I did not check).

| Set | Name | Year | Parts | Model size | Booklet pages | Pages read |
|---|---|---|---|---|---|---|
| 42133 | Technic Telehandler | 2022 | 143 | 17 x 8 x 7 cm | 64 | all 64 |
| 42138 | Technic Ford Mustang Shelby GT500 | 2022 | 544 | 27 x 12 x 8 cm | 112 | 1-63, 64-81, 91-108 (about 99) |
| 42129 | Technic 4x4 Mercedes-Benz Zetros Trial Truck | 2021 | 2,110 | 48 x 21 x 19 cm | 384 | 1-36, 46-54, 64-72, 100-108, 127-135, 190-198, 226-234, 280-288, 334-342, 352-360, 370-378 (about 117) |
| 10317 | Icons Land Rover Classic Defender 90 | 2023 | 2,336 | 32 x 16 x 16 cm | 312 | 1-18, 28-63, 73-81, 100-108, 136-153, 163-171, 181-189, 280-288, 298-306 (about 126, plus 2 zoomed) |
| 10295 | Icons Porsche 911 (Turbo / Targa) | 2021 | 1,458 | 35 x 16 x 10 cm | 268 | 10-45, 64-72, 100-108, 145-153, 244-252 (about 72) |

Year, parts and size are from Brickset [review]. The 42133 piece count also appears in the booklet's own
parts list [seen].

---

## Set by set

### 42133 Telehandler (143 parts): a small Technic machine

1. **The set.** A small wheeled loader with a lifting boom, 17 cm long. It is a single booklet with no bags
   numbered, and I read all of it [seen].
2. **What is built first.** Kind (c), a pin-and-beam frame, but a very short one. It is a compact
   **central block**, not a ladder: a 5-long beam carries two friction pins, an H-shaped flat frame goes
   on top of them, and pin connectors go on either side (steps 1-7, p. 7-9). Two bent beams are then
   pinned on as the side plates of the boom pivot (step 8, p. 9). The block is finished at about step 33
   of 60 (p. 35), roughly half the parts [seen].
3. **How it is made strong.** Each part is held by **at least two pins**, so that it cannot turn. In
   places a short axle goes through cross holes as well. Two curved and two L-shaped flat frames are
   doubled side by side, and 3-long axles pass through all of them (steps 21-31, p. 22-34). There are no
   studded parts in the structure [seen].
4. **How the outside attaches.** There is almost no skin. One white flat panel is held by two pins on
   one side (steps 44-46, p. 46-47). Thin liftarms are pinned on as trim. The angles come from the shapes
   of the parts (bent beams and L beams), not from hinges [seen].
5. **What is built separately.** The boom: a long 13-hole beam with L beams at its ends, pinned to the
   pivot block (steps 34-36, p. 38-40). The fork: two 5-long beams on L beams (steps 48-55, p. 49-54).
   The cab sides and the four wheels go onto pins at the four corners of the block (step 58, p. 58)
   [seen].
6. **What moves.** A worm gear on an axle through the block drives a gear that lifts the boom. Three
   axle connectors hold the worm in place, and a check box shows which way round one of them must go
   (steps 9-15, p. 10-14). The fork tilts on a pin. The mechanism sits **inside** the central block, and
   the frame is built around it [seen].
7. **Inside.** Grey and black beams make up the structure. The colour of the set (azure and white) is
   on the beams people see [seen].
8. **What sets the scale.** The wheels: four tyres on hubs are the largest bought-in parts [seen in the
   parts list, p. 62]. The rest is in whole beam lengths [recalled].
9. **The order.** From the inside out: the centre block, then the worm drive inside it, then the side
   plates and the boom, then the fork, then the wheels. There are 1 to 4 parts per step. Small
   sub-assemblies are built in yellow call-out boxes [seen].
10. **Named techniques.** A doubled frame of flat frames on through-axles, used for the pivot towers. A
    worm-gear lift that holds its position by itself. Wheels on frictionless pins [seen]. The studded
    "pallet" (a large tile plate on two bricks with holes) is a loose accessory (step 59, p. 59) [seen].

### 42138 Ford Mustang Shelby GT500 (544 parts): a medium Technic car

1. **The set.** A 27 cm car with a pull-back motor. There are two bags (bag 1: chassis and side pods,
   steps 1-91; bag 2: bonnet, front, roof, wheels) [seen, p. 5].
2. **What is built first.** Kind (c), a **ladder** of beams, and it starts from the drive. A black
   15-hole beam is pinned to a pull-back motor block, and a second motor block is pinned beside it
   (steps 1-7, p. 6-10). From step 13 (p. 12) the ladder grows forward: two lime 15-hole beams carry
   rows of friction pins (6 at a time), and black 15-hole beams are pinned to them on the outside as a
   second layer (steps 13-30, p. 12-24). The axles running across sit in cross blocks between the rails.
   The ladder with seats and side frames is done at about step 61 (p. 45), roughly 40% of the parts
   [seen].
3. **How it is made strong.** The rails are **doubled**: two 15-hole beams side by side, joined by many
   friction pins. Across the car, 9-hole and 11-hole beams and axles with cross blocks hold the rails
   apart (steps 22-33, p. 18-27). Upright L beams and 2 x 4 L beams rise from the rails to carry the
   side pods and the seats. This makes **closed rectangles** in the upright plane, with no triangles
   [seen].
4. **How the outside attaches.** By **Technic panels on pins**. A curved mudguard panel gets a pin at
   each end (step 38, p. 33). The side pods are built separately on a flat lime piece full of holes and
   pinned on at two points. A long curved bonnet panel gets two pins (step 142, p. 92). Small studded
   details sit on studs. Short studded runs are made from plates and curved slopes on a plate, and that
   plate sits on the studs of a sideways stud brick fixed at the end of a panel (steps 62-73, p. 46-52).
   The angled front corners and the arches are moulded panels, not built angles [seen].
5. **What is built separately.** Two side pods, one per side as mirror copies (steps 62-75, p. 46-53).
   Front and rear fenders, two of each. Headlamp clusters, built from studded bricks with side studs,
   plates and tiles on a Technic connector, then pinned on (steps 123-124, p. 79-80). A studded engine
   block of 2 x 2 bricks, plates and slopes on a brick with a pin hole, pinned in with 2 pins (steps
   107-114, p. 71-72). The wheels go on last (step 156, p. 101) [seen].
6. **What moves.** The pull-back motors are the rear axle, and they are the first thing built. Every
   other part is placed around them. The doors and bonnet do not open [seen]. The front wheels do not
   steer [recalled].
7. **Inside.** Black and grey beams make up the structure. Lime appears on the rails that show through
   gaps. The pull-back motor bodies are dark grey [seen].
8. **What sets the scale.** The motor blocks and the wheels. Everything is laid out from the 15-hole
   rails that join the motors to the front [seen].
9. **The order.** From back to front, then outward, then upward: drive, ladder, uprights and seats, side
   pods, fenders, bonnet, lights, wheels. There are 2 to 6 parts per step. Mirror sub-assemblies are
   built twice from the same pictures ("2x") [seen].
10. **Named techniques.** A doubled-rail ladder. Hanging studded detail off a Technic part through a
    brick with side studs. Pin-on panels with two fixings. Check boxes that show which way round a
    connector or a pin goes (p. 16, 31) [seen].

### 42129 4x4 Mercedes-Benz Zetros Trial Truck (2,110 parts): a large Technic machine

1. **The set.** A 48 cm remote-controlled truck. It has three motors and a hub, and six bags. According
   to the bag overview, bags 1-3 build the chassis only and bags 4-6 add the cab, the bed and the wheels.
   Bag 4 starts at step 318, on page 194 of about 365 building pages [seen, p. 5 and p. 194].
2. **What is built first.** Kind (c), and it starts with a **box around the drivetrain**. Two large
   motors are clamped side by side between flat 3 x 11 Technic plates with holes, with a differential
   in front of them (steps 1-22, p. 6-18). Thick 11-hole beams and **open-centre frames** (the 5 x 7
   frame, LDraw 64179, which the instructions also show stood upright) close the block into a box on
   all sides (steps 23-75, p. 19-54). 15-hole beams stand upright at the box corners. Next, **ladder
   sub-frames** are built separately and attached front and rear. Each is two 11-hole beams joined by a
   5 x 7 open frame and 5-hole beams on both faces (steps 213-224, p. 130-135). The chassis takes about
   half the booklet and half the bags [seen].
3. **How it is made strong.** By **closed rectangles everywhere**: open frames, and beams pinned into
   rings. **Triangles** appear where the frame steps down or out: bent beams (for example the 3 x 7 bent
   beam) run diagonally from a long rail to a lower or wider point (steps 87-98, p. 65-72). The motors
   themselves are part of the structure, pinned through their own holes. Pins are almost always used in
   pairs or rows. Long blue 3-long friction pins join two beam thicknesses at once [seen].
4. **How the outside attaches.** Black 3 x 11 Technic panels and curved panels go onto pins (steps
   314-315, p. 190-191). The grille is a stack of thin liftarms on pins and axles (steps 506-530,
   p. 280-288). The bed is a separate ladder of 13-hole beams, pinned on at four points that the
   instructions circle (steps 605-614, p. 354-359). A small studded unit of plates and bricks forms a
   flat platform on top (steps 319-327, p. 195-197) [seen].
5. **What is built separately.** The axles, each with its differential and pendular frame, built as a
   unit and then fixed under the chassis (steps 148-170, p. 100-107). The ladder sub-frames, the cab
   frame, the grille and the bed ladder [seen]. The four wheels on portal hubs [seen, p. 100-101].
6. **What moves.** Drive, steering and differential locks [recalled: app-controlled]. The motor box
   **is** the core, and drive shafts run lengthwise through the frame to the axles. The steering servo
   sits in the front sub-frame. Steering links pass under the frame rails [seen, p. 127-135].
7. **Inside.** Almost all the structure is dark grey and black. Coloured pins and axles are
   **length codes** (blue = 3-long pin, red = axle pin, yellow and red axles by length), not decoration
   [seen; the meaning of the colours is recalled].
8. **What sets the scale.** The motors, the hub and the large tyres. The frame width follows from
   placing two motors side by side between plates [seen].
9. **The order.** From the inside out and from the middle outward: motors and differential, the box
   around them, front and rear sub-frames, axles, cab frame, panels, bed, wheels. There are 1 to 5 parts
   per step. Many steps begin with a call-out sub-assembly [seen].
10. **Named techniques.** A box frame of open-centre frames. Motors used as structure. Separate ladder
    sub-frames joined at pinned points. Diagonal bent beams as triangle braces. A thin-liftarm stack for
    the grille [seen].

### 10317 Land Rover Classic Defender 90 (2,336 parts): a non-Technic display model

1. **The set.** A 32 cm display model with suspension and opening parts. Bag 1 is accessories (a jack,
   a toolbox and a studded engine). Bags 2-11 make the vehicle and bags 12-15 the expedition parts
   [seen, p. 11].
2. **What is built first.** Kind (c), but made from **studded Technic bricks** (bricks with holes), not
   studless beams. The first steps of bag 2 build each long side rail: a 1 x 16 Technic brick with a
   1 x 8 Technic brick pinned beside it, and a 3 x 5 L beam pinned at the end (steps 1-11, p. 32-35).
   The two rails are joined across by a **4 x 4 Technic brick with an open centre**, set between them on
   pins, and by the suspension pivots. Then **large plates go on top** across both rails (steps 13-18,
   p. 36-38). The chassis with its four suspension corners is done at step 50 (p. 57): one bag of ten
   for the vehicle, and I estimate about 10% of the parts [seen].
3. **How it is made strong.** By **laminating sideways**: two Technic bricks lie side by side with their
   holes in line, pinned together, with their ends staggered so that the joints do not line up. The
   **plates on top** then bridge the studs of both rails and of the cross brick. This plate layer stops
   the rails turning about their pins and turns the ladder into a rigid tray (p. 36-39). Short plates
   (1 x 2 and 2 x 2 stacks) fill gaps at the corners (step 14, p. 36). There are no triangles in the
   chassis [seen].
4. **How the outside attaches.** **Almost entirely on studs.** The floor plates on the chassis are the
   base, and the body is built up on them in ordinary stacked bricks and plates in the body colour
   (bags 3-11; p. 100-171). Flat side surfaces use bricks with side studs and plates mounted sideways on
   them (steps 251-256, p. 146-147; 294-299, p. 164-165). The front bumper is a separate studded unit
   with Technic bricks at its ends, slid onto an axle through the chassis (steps 77-92, p. 73-79). The
   bonnet is a studded plate unit that sits on studs and can be lifted off (p. 298-306) [seen].
5. **What is built separately.** The four suspension corners, each a bent beam with a pin-mounted shock
   absorber (steps 21-22, p. 40-43; steps 32-46, p. 49-54). Front and rear are mirror pairs. The
   windscreen frame, the doors, the roof (white, studded) as one large plate unit (steps 330-346,
   p. 181-189), the bonnet, the roof rack and a winch unit (steps 527-550, p. 280-288) [seen].
6. **What moves.** Suspension at all four corners, through Technic pivots and shock absorbers fixed to
   the Technic-brick rails. Steering through the front corners. The parts list has four steering
   knuckles and four extra-hard shock absorbers [review: Brickset inventory names; the steering
   linkage was not traced in the pages I read]. Doors and bonnet open [recalled]. The mechanisms are
   all **in the chassis layer under the floor plates**, so the studded body never carries them [seen].
7. **Inside.** The chassis and the floor are black and dark grey. Hidden plates under the body are
   often grey or black. The seats are tan. The body colour (sand green) starts only where it shows
   [seen, p. 36-63].
8. **What sets the scale.** The wheels and tyres [recalled]. The windscreen panels set the cab height
   [seen, p. 136].
9. **The order.** From the bottom up: chassis rails, cross brick, floor plates, suspension corners,
   interior (seats, dashboard), then the body walls, bonnet, roof and accessories. There are 1 to 4
   parts per step in the chassis and up to 8 in the body. The suspension corners are built in mirrored
   pairs [seen].
10. **Named techniques.** A Technic-brick ladder locked by plates. Suspension hung on pins from the
    rails. A studded body stacked on the floor plates. Building sideways with bricks that have side
    studs. A plate sandwich (1 x 2 plates stacked to make up height at the corners) [seen].

The parts that matter here, from Brickset's 10317 inventory [review]: black Technic bricks 1 x 16 (2),
1 x 12 (2), 1 x 8 (2), 1 x 4 (13) and 1 x 2 with two holes (5). 2-long friction pins in black (25),
3-long friction pins in blue (10), axle pins with friction in blue (9), axle pins without friction in
tan (6), half pins with friction in red (14), long axle pins in red (4), notched 2-long axles in red
(50). Steering knuckles (4), shock absorbers (4).

### 10295 Porsche 911 (1,458 parts): a non-Technic display model

1. **The set.** A 35 cm display model that builds as either a Turbo or a Targa. The two versions differ
   at the end of the booklet (p. 244-252) [seen].
2. **What is built first.** Kind (c) in **studded Technic bricks**, like 10317. Bag 1 starts with a
   **6 x 8 Technic brick with an open centre** at the front. Long Technic bricks are pinned to it as
   rails: a red one and a blue one (13 and 15 holes, coloured so the builder can tell them apart), each
   doubled by a grey Technic brick pinned beside it (steps 1-6, p. 10-13). **Plates cover the whole
   tray** (steps 11-15, p. 17-19). A second open-centre Technic brick, with Technic bricks pinned on,
   forms the rear frame and is joined to the front tray (step 20, p. 25-26). The chassis is done at
   about step 21 of bag 1 (p. 27), roughly 6-8% of the parts [seen; the share is an estimate].
3. **How it is made strong.** In the same way as 10317: Technic bricks laminated sideways with pins,
   then plates bridging across. The open-centre bricks are **closed rectangles** at each end. There are
   no triangles [seen].
4. **How the outside attaches.** On studs, from the plate tray up. Bricks with side studs carry the
   side skins (step 16, p. 20). The front bumper and the boot are separate studded units. The doors hang
   on hinge bricks (p. 145-148). Curved slopes and wedges give the body's curves [seen].
5. **What is built separately.** The rear axle with its differential, built as a unit on axles and
   connectors and then pushed into the rear frame (steps 159-177, p. 100-107). Seats, doors (a mirror
   pair), front and rear bumpers, two alternative engine covers and roofs [seen].
6. **What moves.** A rear differential links the rear wheels to a moving engine fan [seen: the
   differential; recalled: the fan]. The front steering was not traced. The doors open on hinges [seen].
   The moving parts are in the Technic layer at the rear of the chassis [seen].
7. **Inside.** The hidden Technic bricks are coloured by length (red, blue, yellow), and the hidden
   plates are mostly black and dark grey. White is used only on the outside [seen].
8. **What sets the scale.** The wheels and the windscreen [recalled].
9. **The order.** From the bottom up and front to back: front frame, rails, plate tray, rear frame,
   interior, then body sides, front, rear, doors, roof. There are 1 to 6 parts per step [seen].
10. **Named techniques.** An open-centre Technic-brick frame at each end. A plate tray. Hidden Technic
    bricks colour-coded by length. A differential sub-assembly plugged into the chassis. Doors on hinge
    bricks [seen].

---

## The category questions

### How the frame is laid out

- **Small Technic set (42133): a central block.** A short box of beams and flat frames is the core, and
  the axles, the boom pivot and the wheel pins all come out of it. There are no long rails, because the
  whole machine is only about 20 holes long [seen].
- **Medium Technic car (42138): a ladder** of two doubled 15-hole rails. The drive unit is at one end,
  and the rails are joined by cross beams and by axles in cross blocks. Uprights (L beams) rise from the
  rails to carry the seats and side pods [seen].
- **Large Technic machine (42129): a box around the drivetrain plus ladder sub-frames.** The box is made
  of open-centre frames and thick beams around the motors. Separate ladders (two 11-hole rails and an
  open frame) go front and rear, with diagonal bent beams where the level or the width changes. The bed
  is a further ladder of 13-hole beams [seen].
- **Large display models (10317, 10295): a ladder of studded Technic bricks** joined across by
  open-centre Technic bricks (4 x 4 in 10317; 6 x 8 in 10295) and then **covered by a plate tray**. The
  frame stays in the bottom layer, and everything above it is studded building [seen].
- **Which way the holes face.** In the display models the holes of every rail run **across the car**
  (sideways), because the rails are bricks lying on their bottoms. The pins that laminate a rail, the
  suspension pivots and the bumper axle are therefore all horizontal and point sideways [seen]. In the
  Technic cars, the rails also lie with their holes sideways (beams on edge), and the **uprights turn
  90 degrees**: L beams and upright 15-hole beams have their holes facing forward or sideways, to carry
  cross axles and upper beams [seen]. In 42129 the open frames are used both flat and upright, so the
  box has holes on all three axes [seen].
- **Closed rectangles and triangles.** Rectangles are everywhere: open-centre frames and bricks, ladders
  closed by cross members, doubled flat frames. Triangles appear only in the large Technic truck, as
  diagonal bent beams where the frame changes level or width [seen, 42129 p. 65-72]. None of the cars,
  Technic or not, used a triangle in the chassis in the pages I read [seen].
- **Width in studs, and odd against even.** I could not measure widths exactly from the drawings. As far
  as the drawings show: the display models' frames are set by the open-centre bricks (4 wide inside in
  10317; 8 wide in 10295). Their outer chassis width is even, about 8 studs, so that ordinary plates
  cover it [seen, approximate]. The Technic frames are set by odd beam lengths and odd frames (5 x 7,
  11-hole, 15-hole), so that a beam has a **centre hole** for a centre axle or steering link [seen: the
  parts are all odd lengths; recalled: odd lengths exist for the sake of the centre hole].

### Where studless beams meet studded bricks and plates, and with which parts

- **Bricks with holes (Technic bricks) are the meeting point** in the display models. A pin goes
  sideways into their holes (to a studless beam, a shock absorber, an L beam or a bent beam) while their
  studs take plates on top [seen, 10317 p. 32-39; 10295 p. 10-19].
- **Bricks with side studs** carry studded detail sideways off a Technic part. In 42138 a brick with
  side studs sits at the end of a pinned panel, and plates and curved slopes go on its studs [seen,
  p. 46-52].
- **A brick with a pin hole and pins** fixes a studded block (an engine, a headlamp) into a beam frame
  with two pins (42138 p. 71-72; 10317 bumper p. 73-79) [seen].
- **Plates with a hole and bricks with an axle hole** appear in 10317's inventory: 1 x 2 bricks with a
  cross hole (14), 1 x 2 plates with a hole underneath, 1 x 1 bricks with a cross hole [review]. The
  bumper slides onto an axle through bricks of this kind [seen, p. 73].

### How outer panels and the studded skin are fixed, and how many fixings a panel gets

- **Technic models: panels on pins, two fixings each,** usually one at each end, sometimes with a short
  axle as a third locating point. Examples: the 42138 mudguard (p. 33), the 42138 bonnet panel (p. 92),
  the 42129 side panels (p. 190-191), the 42133 cab panel (p. 46) [seen]. I saw no panel held by a
  single pin.
- **Display models: the skin is built on studs**, from the plate tray upward. A wall locks to the floor
  through many studs along its whole length. Sideways surfaces go on bricks with side studs. In what I
  saw, the body has **no pin connection to the frame at all**: the plates make the joint [seen].
- **Large separate units** (the 42129 bed, the 10317 bumper, the 10295 rear axle) are fixed at **four
  points, or along a through-axle**. The 42129 instructions circle the four fixing points when the bed
  goes on (p. 359) [seen].

### Which kinds of pin are used for what

- **2-long friction pins (black)** join two beam thicknesses permanently: rail to rail, panel to beam
  [seen]. LDraw 2780 "Technic Pin with Friction and Slots"; Brickset lists the newer 61332, which the
  part search also knows ("Technic Pin with Friction Type 2") [review, checked].
- **3-long friction pins (blue)** go through two thicknesses and leave a pin end for a third part, or
  join three beams at once. They are used in rows to pin a second rail on, or to fix a flat frame onto
  a rail (42133 step 1; 42129 throughout) [seen]. LDraw 6558; 42924 in Brickset [checked].
- **Frictionless pins (tan or light grey)** go wherever something must turn: wheel stubs on 42133, the
  boom and fork pivots [seen, 42133 p. 7-9]. LDraw 3673 [checked; the colour convention is recalled].
- **Axle pins**: an axle end goes into a cross hole or a gear, and the pin end into a round hole. Blue
  ones have friction, tan ones have none. They were used to fix gears and to join axle parts to beams
  [seen]. LDraw 43093 with friction, 3749 without [checked].
- **Long axle pins with friction (red) and half pins (red)** appear in 10317, at the rail ends and the
  suspension mounts [seen]. Brickset 11214 and 89678, found by the part search as "Technic Axle Pin Long
  with Friction with 2L Pin" and "Technic Pin 1/2 with Friction" [review, checked].
- **Check boxes** in the instructions settle which way round a part goes, for parts that differ only by
  which end is which (axle pin or pin, which face of a connector) [seen, 42138 p. 16, 31; 42129 p. 132].

### How axles, gears and steering pass through the frame

- **Lengthwise drive** runs along the centre line of the ladder, between the rails, on axles held in
  cross blocks and in the holes of the cross beams (42138, 42129) [seen].
- **Cross axles** pass straight through the holes of both rails or of the box (42133 worm drive; the
  42138 axle lines; the 10317 bumper axle) [seen].
- **The mechanism comes first and the frame is built around it** in every Technic set: the 42133 worm,
  the 42138 pull-back motors, the 42129 motors and differential [seen]. In the display models the
  mechanism is either hung on the frame (10317 suspension corners) or plugged into it as a finished
  unit (10295 differential) [seen].
- **Steering links** run below the rails in 42129 [seen, p. 127-135]. I did not trace the steering in
  10317 or 10295.

### At what size, and for what reason, a non-Technic model gets such a frame

The evidence from the two display models, plus what I recall but did not check:

- **Both display cars studied, at 1,458 and 2,336 parts and 32-35 cm long (40-44 studs), have a
  Technic-brick ladder** [seen].
- **The frame is made of studded Technic bricks, not studless beams.** Studless parts appear only as
  mechanism: suspension arms, bent beams, shock absorbers, axle connectors [seen]. So the "Technic
  core" of a display model is a hybrid: a pinned ladder of bricks with holes, locked by a plate tray.
- **Why it is used** (reasons I infer from what the frame carries):
  1. **Length.** A 40-plus-stud chassis made only of overlapping plates would sag or bend when the
     model is lifted by its middle. Pinned rails laminated sideways with staggered joints give a stiff
     beam on which the plates only need to tie the two sides together [inference from what I saw].
  2. **Mechanisms.** Suspension, steering, a differential and a removable bumper all need horizontal
     pin or axle holes in the bottom layer. Bricks with holes provide them and still take plates
     [seen].
  3. **Repeated pivots.** Doors and the bonnet hinge on studded parts, not on the frame. So the frame
     is there for the length and for the wheels, not for the opening parts [seen].
- **When it is not used** [recalled, not checked in this study]. Small studded vehicles (Speed
  Champions, small Creator cars around 100-400 parts, under about 20 cm) are built on plates, often
  with one long plate or a moulded chassis plate, and have no Technic-brick ladder. Under that size,
  overlapping plates are stiff enough and there is nothing to pin.
- **Best estimate of the threshold.** Use a Technic-brick ladder when the model is **longer than about
  25-30 cm (32-40 studs)** or has **any working suspension, steering or axle-driven feature**. Below
  that, and with no mechanism, use overlapping plates. The threshold is not pinned down: I studied no
  studded set between 400 and 1,400 parts. That is the gap to fill next (see the end).

### What a checking program would need to know to confirm a pin-and-beam joint is real

From the instructions, plus standard LEGO geometry, which is marked [recalled]:

- **Hole pitch.** Beam holes, and the holes of Technic bricks, are 1 stud (8 mm) apart along the part
  [recalled]. A thick beam is 1 stud thick (two holes deep for a 2-long pin across two beams); a thin
  liftarm is half a stud [recalled; seen in use, as 3-long pins through two thick beams leave one stud
  free].
- **Holes in Technic bricks sit between stud positions**, half a stud from the stud grid along the
  brick. On a stacked brick the hole centre is at a fixed height (about 5.8 mm above its bottom)
  [recalled]. **Brick + 2 plates = 2 holes of height (16 mm)**: stacking Technic bricks with two plates
  between them puts their holes 2 pitches apart, so a vertical beam can pin into both [recalled; this is
  the rule that lets beams and studded layers mix].
- **Pin length against thickness.** A 2-long pin joins exactly two 1-thick parts (or four
  half-thickness ones). A 3-long pin joins three, or two plus a free stub for a third part. A half pin
  goes into a single thickness and leaves a stub. A checker must add up the thickness on the pin's line
  and require that **both ends sit in a hole** (or that the free stub is meant to take a part) [seen in
  use; geometry recalled].
- **Round holes against cross holes.** A pin needs a round hole. An axle needs a cross hole to grip and
  turns freely in a round one. An axle pin has one end of each. Frictionless parts turn and friction
  parts hold. A checker must know, per part, which holes are round and which are cross, and per pin,
  which end is which. The instructions' own check boxes for this kind of error show it is a real risk
  [seen].
- **Holes must be coaxial.** Two holes joined by a pin must lie on the same line, at the same pitch and
  facing the same way. Any offset that is not a whole number of pitches is not a joint [recalled].
- **No turning about one pin.** In every set, a part fixed to a frame had **at least two pins in two
  different holes**, or one pin plus an axle through a cross hole, or a stud connection. Display-model
  rails get their stiffness from plates across their studs [seen]. A checker should flag any part held
  by a single round pin as a **hinge**. That is acceptable only when the part is meant to move (a boom,
  a door, a suspension arm) and something else limits it.
- **Friction against free.** Turning joints use frictionless pins. Structural ones use friction pins.
  Mixing them up gives a model that holds but flops, or a mechanism that binds [seen in use; recalled
  as the convention].

---

## Across the sets

### Patterns that held in every set

1. **The core is built first, and it is the bottom or middle layer.** It is the frame, with the
   mechanism inside it or hung on it [seen, all five].
2. **Every structural joint has two fixings or more** (two pins, pin plus axle, or many studs) [seen,
   all five].
3. **Closed rectangles** (open-centre frames, open-centre bricks, ladders closed by cross members) make
   the frame rigid [seen, all five].
4. **Repeated units are built once and shown "2x"**, then placed mirrored: suspension corners, side
   pods, fenders, doors [seen, four of five].
5. **Hidden structure is in neutral or coded colours.** The body colour starts only where it shows
   [seen, all five].

### Patterns that held only at one size

- **Under about 150 parts (42133):** a single compact block is the frame. There are no rails, the
  mechanism (worm drive) is inside the block, and there is almost no skin.
- **Medium, about 500 parts (42138):** a ladder of doubled rails, built from the drive unit outward.
  Panels go on pins, two each, and small studded details hang from bricks with side studs.
- **Large Technic, 2,000 parts and up (42129):** a box around the motors plus separate ladder
  sub-frames, the first use of diagonal bent beams as triangles, and a chassis that takes about half
  the build.
- **Large display models, 1,400 parts and up (10317, 10295):** a ladder of studded Technic bricks with
  open-centre bricks across it and a plate tray on top. The chassis is only about 6-10% of the parts,
  and the rest is studded building on the tray.

### Rules of thumb, with evidence

1. **Anything that moves or carries a wheel is fixed through holes, not studs.** Evidence: the
   suspension, the bumper axle and the differential in 10317 and 10295; all the Technic sets.
   Counter-example: the doors in 10295 hang on studded hinge bricks.
2. **A long rail is two parts laminated side by side, with their joints staggered.** Evidence: a 1 x 16
   plus a 1 x 8 Technic brick in 10317, 1 x 16 / 1 x 14 pairs in 10295, doubled 15-hole beams in 42138.
3. **After a pinned ladder, lay plates across both rails.** In display models this is what stops the
   rails from turning. Evidence: 10317 p. 36-39, 10295 p. 17-19.
4. **A pinned panel gets two pins, as far apart as the panel allows.** Evidence: 42138, 42129, 42133. I
   saw no counter-example.
5. **Build the mechanism first and the frame around it.** Evidence: all three Technic sets. In display
   models, mechanisms are separate units plugged into the frame (10295) or hung on it (10317).
6. **Use odd lengths and odd frames (5 x 7, 11, 13, 15)** so that there is a centre hole for the drive
   line. Evidence: every beam in the three Technic frames was an odd length [seen]; the reason is
   recalled.
7. **Use triangles only where the frame changes level or width.** Evidence: 42129 (p. 65-72).
   Counter-example: none of the cars has a triangle.
8. **Units that open are their own sub-assembly** on hinges or on a pin pair. Evidence: the doors in
   10295 and 10317, the boom in 42133, the bonnet in 10317 (it lifts off its studs).

### Playbook for a new subject in this category (not a copy of any set)

**About 100 parts: a small machine, for example a mini excavator or a go-kart.**

1. Decide what moves (a boom, steering, a lift), and build that mechanism's axle line first: an axle
   through a 5-hole or 7-hole beam, with the gear or worm on it.
2. Close a compact block around it. Put two thick beams parallel to the axle and join them with an
   H-shaped or open flat frame on 2-long friction pins, two pins per joint. Keep the block 5-7 holes
   long.
3. Pin any pivot towers onto the block's sides, made of two bent beams or two flat frames side by side
   with through-axles, so that no tower stands on one pin.
4. Hang the moving arm on frictionless pins at the pivot, and drive it from the block's axle (worm or
   gear).
5. Put the wheels on frictionless pins or axles at the four corners of the block, at the same height,
   in mirrored pairs.
6. Add trim last: one or two thin liftarms or a single panel per side, each on two pins. Use structural
   colours inside and the theme colour outside.

Parts by step: thick beams 5/7/9 (32316, 40490 and others), an H frame or open frame (64179), 2-long
friction pins (2780), 3-long friction pins (6558), frictionless pins (3673), axle pins (43093 and 3749),
3-long and 5-long axles (4519 and others), bent beams (32140, 32526), wheels.

**About 400 parts: a vehicle, Technic or studded.**

1. Decide the length in studs and whether it has any mechanism. If it is over about 32 studs long, or
   has suspension, steering or driven wheels, give it a frame of rails. Otherwise build on overlapping
   plates and stop here.
2. Build the drive or axle unit that sets the wheelbase first (the rear axle, a differential, a motor),
   as a sub-assembly.
3. Make each side rail from two long parts laminated side by side with their joints staggered, joined
   by 2-long friction pins every 2-4 holes. For a studless car use two odd-length beams (11, 13, 15
   holes). For a studded display model use two Technic bricks (1 x 16 with 1 x 8 or 1 x 14).
4. Join the rails across at both ends with a closed rectangle: an open-centre Technic brick (4 x 4 or
   6 x 8) for a studded model, or an open frame (5 x 7) or cross beams for a studless one. Pin the drive
   unit between them.
5. **Studded model:** cover the whole ladder with plates that cross both rails, using the longest
   plates that fit and staggering their seams. This tray is both the floor and the lock.
   **Studless model:** add L beams standing up from the rails to carry the seats, the body sides and the
   upper cross beams.
6. Hang the suspension or steering arms on pins in the rails' sideways holes. Use frictionless pins
   for pivots and give each arm two mounting points.
7. Build repeated units once and place them mirrored: side pods, fenders, doors, headlamp clusters.
8. **Studded model:** build the body walls on the tray in stacked bricks, use bricks with side studs
   where a side face must be smooth, and hang the doors on hinge bricks.
   **Studless model:** pin panels on with two pins each, and hang small studded details from a brick
   with side studs or a brick with a pin hole, pinned with two pins.
9. Fix large add-ons (a bed, a roof, a bumper) at four points or along one through-axle.
10. Put the wheels on last. Check that every structural part has two fixings and that every part on a
    single pin is meant to turn.

### Part vocabulary by job (numbers checked with the project's part search unless marked)

| Job | Parts |
|---|---|
| Core, studless | Technic beams 3/5/9/11/13/15 (32523, 32316, 40490, 32525, 41239, 32278); open frames 5 x 7 (64179) and 7 x 11 (39794); L beams 3 x 5 (32526) and 2 x 4 (32140); T beam 3 x 3 (60484) |
| Core, studded | Technic bricks 1 x 2 / 1 x 4 / 1 x 8 / 1 x 12 / 1 x 14 / 1 x 16 (32000 or 3700, 3701, 3702, 3895, 32018, 3703); open-centre Technic bricks 4 x 4 (32324), 4 x 6 (32531), 6 x 8 (32532); 1 x 1 brick with hole (6541) |
| Lock | Plates across the rails (any long plate); 2-long friction pins (2780, 61332); 3-long friction pins (6558, 42924); a second laminated rail |
| Joint (turning) | Frictionless pin (3673); axle pin without friction (3749); long pin with stop bush (32054) |
| Joint (fixed, with axle) | Axle pin with friction (43093); long axle pin with friction (11214); cross blocks 1 x 2 (6536), 1 x 3 (32184, 42003), 2 x 3 (32557), 2 x 2 split (41678) |
| Half-depth | Half pin with friction (89678); half pin (4274); thin liftarms 3/4/5 (33299-style, 32449, 11478) |
| Angle and brace | Bent beams 3 x 7 at 53.13 degrees (32271), 4 x 6 (6629), 4 x 4 (32348), double bent 3 x 7 at 45 degrees (32009); triangle liftarm (2905) |
| Sideways (studs to holes) | Bricks with side studs (not checked); 1 x 2 brick with axle hole (32064); pin with a perpendicular hole (15100) |
| Skin, studless | Technic panels 3 x 11 (15458), 5 x 11 (64782), smooth 11 x 2 x 3 (11954); curved moulded panels (not checked) |
| Skin, studded | Ordinary bricks, plates, curved slopes, tiles on the plate tray |
| Detail | Studded mini-builds on a brick with a hole and two pins (engines, lamps) |

### What I could not find out, and what to look at next

- **Exact frame widths in studs.** I could not measure them reliably from the isometric drawings; the
  figures above are estimates. Next: open the official LDraw/Studio files where they exist, or measure
  the plates that cover the tray.
- **The size threshold for a non-Technic frame.** I studied no studded vehicle between 400 and 1,400
  parts. Next: a Creator Expert or Icons car of 800-1,200 parts (for example 10265 Ford Mustang or
  10304 Chevrolet Camaro Z28), and a Speed Champions or Creator car under 400 parts as the negative
  case. Also a large studded ship or non-vehicle display model, to see whether a frame appears without
  wheels.
- **The steering mechanisms in 10317 and 10295.** They are in pages I did not read closely.
- **Full pin inventories for 42133, 42138, 42129 and 10295.** Only 10317's inventory was read
  (Brickset), and only in part.
- **A large Technic supercar (for example 42143)** would show whether a car frame of 3,000 parts and up
  uses the 42129 box-and-sub-frame layout or a long ladder like 42138. Its booklets are two files of
  about 150 MB each, and I chose the single-file 42129 instead.
