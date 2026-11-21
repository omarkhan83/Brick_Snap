# Craft findings: what makes a brick model look modern and designed

20 November 2026. The craft part of the style study. The result is `style-guide.md`; its use on our Cessna is `cessna-critique.md`. This file is the evidence.

## How it was done, and how far to trust it

- **Written sources** were found by web search and read with a page-fetch tool that returns answers and quotations from a page, not the page itself. Every quotation below was afterwards checked word for word against the page at its address, or against an archived copy where the entry says so, on 20 November 2026. Sources that refused automated reading are listed at the end.
- **Official sets** were studied by three sub-researchers (aircraft; cars; creatures, buildings and an object). They found each booklet through LEGO's building-instructions page, downloaded the file LEGO publishes, turned pages into contact sheets and read them as pictures; for sets older than about 2002 they had only box pictures and reviews. About 45 sets in all, under half of them from booklets read closely. Stud counts, widths and proportions are their estimates by eye. Nothing of LEGO's was kept outside a temporary folder; techniques are described in our own words.
- **Parts** were checked by name against the project's LDraw library (all the numbers in the guide resolve). A part "matched" in a booklet drawing is rare; most part numbers are "the current part of that kind".
- **The checker** was tested directly: small models written for the purpose and run through `bricksnap.lab.validate.check` as it is on `main` at commit bf9d675. Nothing was written to the repository.
- Marks: [said] a designer or builder said it, with the address; [seen] in a booklet or picture, with the set; [review]; [tested] on our checker; [second-hand] a search summary of a page I could not open; [inferred] my own reading.

## 1. What designers and expert builders say

### Studs: the two camps disagree, and both give reasons

- LEGO's designers keep some studs on purpose. Jamie Berard, on the Creator Expert vehicles: "We intentionally leave some studs visible as that is very much part of LEGO's brand." and "Generally we find that people are less impressed if something is not obviously made from LEGO bricks." But of the 2008 Beetle: "leaving so many studs exposed at that scale is not ideal, particularly where such a famously curvy car is concerned." His colleague Morten, on the London Bus: it "is perfectly suited to leaving studs visible as they could represent rivets holding the panels together." [said, 2017: https://brickset.com/article/29026/interview-with-creator-expert-designers-morten-and-jamie]
- Jens Kronvold Frederiksen (LEGO Star Wars) on testing smooth prototypes with consumers: "people really wanted to look like LEGO sets and thought, 'Hey, where are the LEGO knobs?'" [said, 2021: https://www.starwars.com/news/lego-star-wars-afols]
- Craig Callum (LEGO design manager): "I almost consider the LEGO bricks as a brand identity that we have to design within"; "It's what makes it unique, it's what makes it a LEGO model." [said, 2017: https://www.cardesignnews.com/designers/qa-craig-callum-lego-design-manager/431692]
- Fan builders name the opposite ideal. "Studless": "A building style in which visible studs are minimized or, ideally, eliminated." [said: https://www.brothers-brick.com/lego-glossary/] A reviewer of the 2023 Concorde finds its few studded plates "a little unsightly" and notes they can be swapped for tiles. [review: https://www.newelementary.com/2023/10/lego-icons-build-review-10318-concorde.html]
- **Reading:** nobody defends studs left by accident. Designers keep studs that stand for something (rivets) or mark the medium; fans remove them. "Every stud on show is one you chose" satisfies both.

### Building sideways, and offsets

- Holger Matthes's long-standing guide: with sideways building "the models become much more realistic and more detailed." [said: https://www.holgermatthes.de/bricks/en/snot.php]
- The geometry everyone repeats: "The width of two studs is the same as the height of five stacked plates". [said, O. Cederwall, 2021: https://bricknerd.com/home/snot-basics-geometry-techniques-and-pitfalls-3-18-2021]
- What it is for, beyond smooth sides: curves from "placing the curved parts sideways", stripes ("Brick-built striping can also be an alternative to using stickers", thin stripes from brackets with headlight bricks), lettering, and quarter-plate steps from jumpers. [said, Cederwall, 2022: https://bricknerd.com/home/lego-snot-advanced-techniques-and-implementations-5-12-21]
- Milan Madge on the 2023 Concorde: "The whole midsection of the aircraft is built sideways ... it also allowed us to get a smooth underside to the LEGO model." [said: https://www.lego.com/en-us/categories/adults-welcome/article/why-concorde-is-engineering-masterpiece, read from the Wayback Machine copy of 16 April 2026]
- The "Unofficial LEGO Advanced Building Techniques Guide" (Didier Enjary, 2007, 37 pages) is about exactly this: sideways building and offsets in fractions of a stud. I found where it is described and linked but did not read the file itself. [second-hand: https://www.brickpile.com/?p=94, https://www.brothers-brick.com/2007/02/13/new-advanced-building-techniques-guide-by-didier-enjary]

### Curves from curved parts

- Ralph Savelsberg rebuilding a 2008 helicopter in 2018: "Back in 2008, I built the fuselage as a fairly simple box ... The fuselage corners were slightly rounded using stepped plates." Now: "I am building the bottom studs-down, with curved slopes forming the bottom corners" and "rounding the top corners using a combination of 45-degree slopes and 1×2 and 2×2 curved slopes." "A simple box won't do!" [said: https://www.brothers-brick.com/2018/12/05/how-to-build-a-pave-low-helicopter-with-lego-part-1-feature] This is one builder dating his own model by the same step we see in official sets.
- The parts are recent: the 2 x 1 curved slope (11477) came in 2013, a quarter of the 2009 one (88930) and half of the 2011 one (93273). [said, 2013: https://www.newelementary.com/2013/07/you-got-cutest-little-baby-bow.html] A model without them looks as if it was built before them.

### Colour: blocking, liveries, palette

- Colour blocking, defined: pairing contrasting colours and "dividing them into larger sections for a graphical effect." "An even distribution of colors isn't necessarily the best way to use colors." A stripe: "try not to place it in the middle of the model". Detail colours: "choose one or two colors that you use for greebles". [said, Cederwall, 2024: https://bricknerd.com/home/using-color-theory-and-composition-in-lego-mocs-3-25-24]
- A split of 70% main colour, 20% second, 10% detail is one builder's rule of thumb. [said, 2025: https://bricknerd.com/home/building-without-limits-a-deep-dive-on-digital-lego-mocs-2-3-25]
- Each colour a job: "all the blue is dedicated to rocks or stonework, and the purple is for the leaves." [said, C. Huet, 2024: https://bricknerd.com/home/castles-and-color-using-color-in-fantasy-and-castle-builds-7-23-24]
- Colour gives form: of an early model, "there are no lines or color blocks standing out to give it form"; red accents were "band-aids slapped onto a bland color scheme." [said, B. Foster, 2024: https://bricknerd.com/home/self-scrutiny-learning-from-past-moc-mistakes-2-6-24]
- Which colours are dated: the only written statement found is a blogger's history. The early palette was a handful of basics; official sets long kept "a somewhat childish building style of bright colors and strong contrasts"; the adult lines moved to realistic palettes because "adults have a greater desire for realism"; and "There is nothing wrong with using basic colors as they have their own charm." [said, 2020: https://thebrickblogger.com/2020/07/working-with-the-lego-color-palette/] Others refuse to rule: "it all boils down to subjectivity, shaped by context, personal taste and nostalgia." [said, 2025: https://bricknerd.com/home/how-to-use-color-in-lego-builds-5-6-25]
- Designers choosing a palette cut it down: on the 2022 Boutique Hotel, "it just became about pairing it back"; a colour is "very sensitive to the other colors around it." [said, A. Ward Grubb, 2021: https://brickarchitect.com/2021/interview-secret-history-of-10297-lego-boutique-hotel-with-anderson-ward-grubb-ashwin-visser/]
- Liveries in bricks. Chris Stamp on a striped car: "We could have built the stripes with a two-module-wide grey stripe between the blue stripes very easily, but that would not be correct"; the stripes are built from sideways plates and the arches printed so the stripes carry across. [said, via the cars researcher: https://brickset.com/article/86449/nissan-skyline-designer-insights-from-chris-stamp] An airliner builder: "I realized I would have to design a fuselage with brick-built stripes of three different breadths", and chose the fuselage section to suit the stripes. [said, A. Newman, 2020: https://aaron-newman-jzer.squarespace.com/blog/2020/6/21/we-are-cleared-for-takeoff] Savelsberg uses stickers for lettering and insignia, "matching their backgrounds to the colour of the LEGO". [said: https://www.brothers-brick.com/2018/09/24/how-to-build-a-grumman-e-1-tracer-early-warning-aircraft-from-lego-part-3-feature]

### Scale

- Berard: "each model is defined by a few distinctive features and the scale develops from there"; the team "decided to alter the scale to best suit the shape of the subject matter." Morten: "More frequently the sets are constructed around the size of an appropriate wheel". [said, 2017, Brickset 29026 as above]
- Why Speed Champions went from 6 to 8 studs wide in 2020, in Chris Stamp's words: "From day one people said our cars are maybe a bit too thin." Going up "we can get those proportions correct which is more authentic, we can include two minifigures"; and "by going up in size you create more space for yourself to use bricks instead of stickers to capture certain details." [said, 2020: https://www.newelementary.com/2020/01/lego-speed-champions-2020-designer.html] Later: "The 6-wide were great but they were a bit 'caricature'" [said, 2021: https://www.newelementary.com/2021/05/lego-speed-champions-2021-interview.html]; "We wanted the cars to be as low to the ground as possible, but then also as wide as possible." [said, 2023: https://newelementary.com/2023/02/lego-speed-champions-interview.html] The team tried other widths: "We investigated seven wide, eight wide, we investigated ten wide" [said, 2020: https://www.brickfanatics.com/lego-speed-champions-changing-to-eight-wide-cars, read from the Wayback Machine copy of 13 July 2024]; and "even seven wide, which was just ridiculous – it was so confusing trying to build LEGO pieces in odd numbers". [said, 2020: https://www.brickfanatics.com/lego-speed-champions-what-is-new-for-2020, read from the Wayback Machine copy of 23 January 2025]
- A reviewer's arithmetic: at 8 wide "a stud equates to 30cm, and width-wise, 27cm"; a 2015 6-wide car's "scale width should thus be 8.4 studs". [review, via the cars researcher: https://brickset.com/article/47591/review-76895-ferrari-f8-tributo]
- Mike Psiaki scaled an early Space set (497 Galaxy Explorer) up by one and a half "to recreate the feeling" of the original for an adult. [said, 2022: https://brickset.com/article/78875/interview-with-mike-psiaki-designer-of-10497-galaxy-explorer]
- Savelsberg builds aircraft at 1/36 because drawings come at 1/72: "My planes are 1/36 mainly because I can simply scale them up by a factor of two relative to the scale drawings." [said, 2008: https://gizmodo.com/giant-lego-b-1b-bomber-escorted-by-fighters-hawkeye-ai-356469]
- **Disagreement:** scale comes from a distinctive feature (Berard), from a wheel (Morten), from the figure and the width (Stamp), or from a fixed ratio (Savelsberg). All agree on the direction: when the shape cannot be made, go up.

### Proportion and outline first

- Savelsberg: "I plan my builds." "My plan consists of a few drawings on graph paper." "I always start actually building with the difficult bits". [said: https://www.brothers-brick.com/2018/09/05/how-to-build-a-grumman-e-1-tracer-early-warning-aircraft-from-lego-part-1-feature] And on wings: "I always spend a lot of time on getting the leading and trailing edges". [said, 2010: https://militarylego.blogspot.com/2010/05/building-scale-models-of-aircraft-in.html]
- Foster on his early ships. Of one: "I became so preoccupied with the engineering that the artistic aspects became something of an afterthought", and of its shapes, "I don't get the feeling that they have a reason for existing". Of another: "Had I tried sketch-building to form a more coherent plan for the basic shape, the build would likely have come out cleaner." [said, BrickNerd 2024 as above]
- Stamp: "The four wheels, windscreen, lights, and roof are paramount." [said, 2022: https://brickset.com/article/73550/interview-with-chris-stamp-speed-champions-design-manager-part-1]

### Thin things, and angles

- No designer was found stating "thin things thin" as a rule. The nearest is a remark reported from an article on the design of the 2026 Road Bike: that going too small looks chunky, while big and thin is hard to make stable. [not verified against the source: known only from search summaries of an article that could not be opened] It rests on what sets do (section 2) and on our eye.
- Angles are an exact craft. A. Knobbe's 2025 series: a clip on a bar handle bridges a one-stud gap and its small offsets cancel within a triangle; triangles that close exactly include 3-4-5 (3 studs across, 3 bricks and a plate up, 5 along the slope) and 6-8-10 (8 studs, 5 bricks, 10); a plate turned between hinge plates lands on the grid at 53.1 degrees. [said: https://www.newelementary.com/2025/07/clip-based-lego-pythagorean-triangles.html, https://www.newelementary.com/2025/03/lego-building-at-angles-escaping-grid.html] Savelsberg said the same in 2010: "the diagonal of a right-angled triangle with sides that are 3 and 4 studs long is exactly five studs long." The Boutique Hotel's angled wall is a 3-4-5 triangle. [said, Brick Architect as above]

### Texture and detail: where to stop

- Cederwall: "Good detail distribution is ultimately about placing meaning, not just decoration." "Smooth surfaces and calm regions create contrast that makes nearby details feel sharper and more deliberate." "Too much detail without information becomes noise." "Try using greebling sparingly, and let the eye rest between patches." [said, 2026: https://bricknerd.com/home/from-noise-to-narrative-detail-distribution-in-lego-mocs-2-2-26]
- Foster: his early models were bare panel or dense detail with "the lack of a middle ground"; the middle ground is quiet texture (hollow studs, recessed half plates, offset tiles). He also warns against a new trick used everywhere: "Click hinges have since lost their novelty". [said, BrickNerd 2024 as above]
- "Nice part use" is "An unexpected way to use a LEGO element in a model." [said, Brothers Brick glossary] Stamp: "Using parts in interesting and unusual ways is paramount" [said, 2022: Brickset 73550 as above]. LEGO's own tips page gives five designers' techniques of this kind. [said: https://www.lego.com/en-gb/categories/adults-welcome/building-dream-lego-ideas-designers/lego-hacks-master-builders, read from the Wayback Machine copy of 26 April 2026]

### Gaps and lines

- Savelsberg on a round cowl: "I am not keen on some of the gaps, but it does come close to the right shape." Shape first, gaps second, but gaps are counted. [said: https://www.brothers-brick.com/2018/09/16/how-to-build-a-grumman-e-1-tracer-early-warning-aircraft-from-lego-part-2-feature]
- Official practice: black parts behind an opening so a gap reads as shadow (2020 Ferrari); a flag to block one see-through gap (2019 Mustang); gaps between rows of tiles used as the grooves of a ribbed panel (2022 Atari). [seen, sub-researchers]

### Toy against display

- Frederiksen: before, "it was about giving a great play experience. But here, it's a display experience"; people "want, when it's displayed, it should be visible that this is something that consists of a lot of pieces." [said, StarWars.com 2021]
- Stamp: "we're not a play theme, we're a collectible car product line"; "we're no longer a toy. We're now more of a die cast". On stickers: "I would not say we are seeking to avoid stickers, but we do want to build as much as we can." [said, New Elementary 2021 and 2022 (https://www.newelementary.com/2022/02/lego-speed-champions-2022-interview.html); Brickset 73550]

## 2. Old against new in official sets

### Aircraft (17 sets, 1987 to 2025, seven read closely; one more from reviews)

Sets: 6687 (1987), 6673 (1990), 6536, 6345, 1808 (1993 to 1996, pictures only), 6615 (1996), 7732 (2008), 3178 (2010), 31028 (2015), 60196 (2018), 60250 (2020), 31099 (2020), 77012 (2023), 60413 (2024), 31160 (2025), 10226 (2012); 10318 (2023) and 40450 (2021) from reviews. Booklets: `https://www.lego.com/en-us/service/building-instructions/<set>`; pictures: `https://images.brickset.com/sets/images/<set>-1.jpg`.

- **Fuselage.** Old: a 2-wide spine or a 4-wide box, shaped only by 33 and 45-degree slopes on top and inverted slopes under the ends; sides vertical. City to this day keeps flat sides at 4 and 6 wide and rounds the belly with one moulded shell. The two Creator planes are the change: a 2-wide core with side-stud bricks, curved-top bricks and tiles on the flanks, inverted curved slopes for a rising belly (31099); a 2-wide spine with one 10-long curved slope hung sideways on each flank, so the taper is one curve (31160). **Sides and belly are rounded from about 4 studs overall, and only in Creator.** [seen] The 203-part Vega (40450) makes a round 4-wide body as a sandwich of two 4 x 16 curved wedges, with "familiar sideways-building methods"; its wheel fairings are "a variety of curved pieces" with no wheels in them. [review: https://www.newelementary.com/2021/03/lego-review-40450-amelia-earhart-tribute.html, https://brickset.com/article/58075/review-40450-amelia-earhart-tribute; the width is inferred from the part, 45301]
- **Wings.** Old: one plate, every stud showing, square tips. **Unchanged in small modern sets** (60250, 60196, 77012). What is new is a second colour layer (white under azure wedge plates, 31099), tile graphics on a plain wing plate (31160), finished tips (a trans plate under the tip tile, a round-corner part), and tiled and studded bands as ribs (10226). No set read under 900 parts rounds the leading edge. Concorde's wings are built sideways, smooth on both faces. [seen; review]
- **Glass.** Old: clear or light blue, a sloped screen under a roof plate. 2008 to 2010: one moulded light-tinted canopy. New: a small smoke or trans-black canopy faired between curved parts (31160), a smoke screen with a separate roof (60250), even opaque black standing in for glass (31099). **The rake always comes from the moulded part; it is never built.** [seen]
- **Colour.** Old: white, red, blue, yellow, black, light grey; the stripe is a red or black plate layer at the waist plus stickers. New colours: dark azure, dark blue, orange, sand green, dark green, tan, dark red. New schemes are three stacked zones and one accent. **The waist line as a plate layer is used old and new alike**; new are wedge-plate layers, triangular tiles, and stacked 1 x 1 bricks for vertical bands. [seen]
- **Thin members.** **None of the small modern high-wing sets has a wing strut at all.** The 1996 set used slope bricks, the 2010 one Technic pins; a 2015 floatplane used bar-and-clip parts for float struts; the Sopwith Camel uses thin Technic links and braided string. The forked gear plate with its small wheel is unchanged from 1996 to 2025. No set has wheel fairings except the Vega. [seen]
- **Same subject, 2001 against 2012** (Sopwith Camel 3451 and 10226): the old tail was "bricks built completely studs-up" with a sticker for its colours; the new one "uses some excellent SNOT work to implement the red-white-blue pattern using only bricks". The old undercarriage's diagonal braces gave way to spring pistons and the guns moved closer together, both "more accurate to the real thing"; the reviewer prefers the old set's "extra cable rigging". [review: https://brickset.com/reviews/48039]

### Cars (13 sets, 1985 to 2022)

Sets: 6633, 6530, 6644, 6561, 5541 (pictures); 10187 (2008) against 10252 (2016); 75890 (2019, 6 wide) against 76895 (2020) and 76906 (2022), 8 wide; 10265 (2019); 31100 (2020); 60285 (2021).

- **The same Beetle twice is the cleanest evidence in the study.** 2008: every upward face is plates terraced in one-plate steps, all studs showing; a Brickset user's review of the 2008 set calls it "the big flat slap on top of the roof" [review: https://brickset.com/reviews/32044]. 2016: the same shapes in curved slopes and wedge shells, about ten studs left on the bonnet, inverted curved slopes tucking the body under at nose and tail, and far fewer parts (one review says "about 500 fewer"; it is also smaller). [seen; review: https://brickset.com/article/22507/review-10252-volkswagen-beetle, https://www.brothers-brick.com/2016/07/12/new-lego-10252-volkswagen-beetle-is-totally-radical-man-review]
- **The break is a decision, not a decade.** The 2019 6-wide Ferrari is still slab-sided with about 40 studs showing; the 2020 8-wide one shows 3 to 5, and its flanks are sub-assemblies built flat, turned and plugged on sideways. [seen]
- **Stance.** The same tyre went from half the body width to three eighths, so the car reads low and wide; the body comes down round the wheel under an arch part. Town cars showed the whole tyre under a flat base. [seen; the tyre's size is recalled]
- **Glass.** Town: one clear or light-blue screen as wide as the body under a studded roof, no side glass. New: a tinted glasshouse narrower than the body, pillars in the body colour. [seen]
- **Colour.** Old: primaries, coloured hubs, light-blue glass. New: one dark or saturated body colour over black, tan inside, metallic wheels, smoke glass. Trim is one plate course (10252's waist line). [seen]
- **Still toy today:** the City car is tidy with 89 parts because moulded parts do the shaping; its tells are the tall cabin, slab doors, high ride and bright colour. The small Creator car has Technic holes along its sill and about 25 studs. [seen]

### Creatures and characters (9 sets, 2000 to 2024)

Sets: 4507 (2004), 4884 (2005), 3450 (2000) against 21042 (2018), 31058, 31129, 31133, 31137, 21349.

- **Eyes are the change.** 2004: a transparent tooth plate, no pupil, socket or brow; 2005: a 1 x 1 transparent stud. New: a domed eye through a dark ring under an overhanging curved slope; printed round eyes two studs across on a 4-wide head; a black open-stud round with a light bar end as the glint. [seen]
- **Surface.** About half of the 2004 dinosaur is studded, with grey structure showing through. The 2017 one caps every upward face with a curved slope and keeps studs as scales, 15 to 20%. Studs kept on purpose: a poodle's coat of bare side-stud bricks beside a smooth labrador. [seen]
- **Joints are not the change.** The 2004 dinosaur is ball-jointed throughout with bare joints; the modern sets still show grey balls and sockets. New are hip discs, claws, toes, noses and tongues. Heads grew: about a quarter of the trunk in 2004, three quarters in 2017. [seen; estimates]
- **Colour.** One coat colour, its dark shade as stripes, a pale belly, one accent. Tiger stripes are black layers one plate thick seen edge-on, or black curves inlaid in a sideways panel. [seen]

### Buildings and an object

Sets: 6376 (1990), 6350 (1994) from box pictures; 10182 (2007); 10312 (2023); 10306 (2022).

- **1990s to 2007 is the step; 2007 to 2023 is refinement.** The Town buildings are a white frame, open at the back, white and red, on a studded baseplate, with no cornice. The 2007 Café Corner already has a base, a body and a crown, piers with recessed panels, an arcade, a corbelled cornice, a mansard, a brick-built sign, awnings and a tiled pavement, all from plain bricks. 2023 adds finer trim, inset windows with surrounds and sills, texture in patches only, and two unequal buildings on one plate. [seen]
- **The object** (a game console): twelve studs showing on about 2,500 parts; a ribbed top from rows of tiles whose gaps are the grooves; wood from sideways plates in two or three browns; a thin orange outline from plate rails seen edge-on; curved slopes at the corners. [seen; review: https://brickset.com/article/79528/review-10306-atari-2600]

## 3. Parts for each technique (LDraw names, all present in the library)

| Technique | Parts |
|---|---|
| Smooth tops | Tiles 3070b, 3069b, 63864, 2431, 6636, 4162, 3068b, 26603, 87079, 69729; round 98138, 14769; corners 25269, 24246, 27925; triangular 35787, angled 22385 |
| Curved tops | 11477 (2 x 1), 15068 (2 x 2), 50950 (3 x 1), 61678 (4 x 1), 93273 (4 x 1 double), 24309 (3 x 2), 93606 (4 x 2), 88930 (2 x 4), 8235 and 93604 (3 x 4), 42022 (6 x 1), 44126 (6 x 2), 42918 (8 x 2); with a cutout 29119/29120, 5093/5095; bricks 6091, 37352, 49307 |
| Curved undersides | 24201 (2 x 1), 32803 (2 x 2), 13547 (4 x 1), 42023 (6 x 1) |
| Long tapers and shells | 77180/77182 (10 x 2), 45301 (4 x 16 curved wedge) |
| Sideways cores | 87087, 26604, 47905, 4733 (1 x 1); 11211, 52107, 22885 (1 x 2); 30414 (1 x 4); 4070, 32952; brackets 99780, 99781, 99207, 44728, 2436b, 93274, 36840, 36841, 41682 |
| Offsets | Jumpers 15573, 3794b, 87580, 34103; hinge top 6134 as a quarter plate |
| Wedges and wings | 24299/24307 (2 x 2), 43722b/43723b (2 x 3), 41769b/41770b (2 x 4), 65426/65429, 78443/78444 (2 x 6), 54383/54384 (3 x 6), 50304/50305 (3 x 8), 47397/47398 (3 x 12), 48205/48208 (4 x 6), 30355/30356 (6 x 12), 2413, 51739; tips 30357, 30565 |
| Bars and what holds them | Bars 87994 (3L), 30374 (4L), 63965a (6L), 4095 (6.6L); clips 60897, 4085c, 61252, 63868, 11476, 15712; handles 2540, 48336, 60478, 26047, 78257, 18649; tubes 23443, 11090; bar with clip 48729b; levers 4592 with 4593; aerials 3957b, 2569 |
| Hinges | 3937 with 3938 or 6134; 2429 with 2430; click 30383, 44301a, 44302a, 60471; ball 14417 with 14418 or 14704 |
| Glass | Screens 30841 (2 x 4), 57783 (3 x 4), 3823, 18973 and 3384 (6 x 4), 65633 (6 x 6); panels 4865b, 30413, 87552, 87544, 60581; cabin window 2377 with 4862; small panes 54200, 85984, 3070b, 3024 in a trans colour |
| Wheels, arches, fairings | Arches 18974, 98282, 50745, 3788, 93587; small wheels 4624 with 3641, 50944 or 93593 with 50951; gear 2415, 4488, 21445, 4600; a fairing is 93273 or 50950 over a wheel with 24201 beneath |
| Detail | 6141, 85861, 3062b, 4589, 59900, 4740, 2654a, 30367a, 54200, 2412b, 15535, 20482, 60849, 4599b, 15070, 49668, 11253 |
| Buildings and objects | 98283, 15533 (embossed brick); 3839b (sills); 3659, 6005 (arches); 32028, 4510 (rails for hairlines) |

Colours the builder is not told and the modern palette needs (LDraw codes from the library): sand blue 379, sand green 378, dark azure 321, medium azure 322, dark orange 484, medium nougat 84, bright light orange 191, olive green 330, dark brown 308, flat silver 315, pearl gold 297, **trans black 10375**, trans light blue 43. Its list (`bricksnap/lab/prompt.md`) has 20 solid colours and four transparent ones, and calls 40 "transparent brown (smoke)": in the library 40 is Trans Brown (#635F52) and Trans Black (#212121) is 10375. That is why the Cessna's glass is brown.

## 4. What would stop our builder

Tested on `main` (bf9d675). Each case is a few parts on a brick; the test scripts were temporary and are not kept.

**What passes today** (counted as joined, listed as "cannot confirm"):

| Technique | Result |
|---|---|
| The clip of 11090 on a handle (48336), swung 0 to 120 degrees about the handle | joined [tested] |
| A plate strut: 1-wide plates on two clip plates (60897), on handles 8 studs across and 5 bricks up (200 LDU, 37 degrees) | no problems [tested] |
| A bar strut: clip plates gripping the handles of two 23443, a Bar 4L between the tubes, 5 studs across and 3 bricks up (36 degrees) | no problems [tested] |
| A bar lying in one or two clip plates | joined [tested] |
| Hinge brick halves (3937, 3938) held open at 20 or 30 degrees, with no joint line | joined [tested] |
| A click hinge at 22.5 degrees, placed as the library's own assembly places it (30383, 30553) | joined [tested] |
| A ball in its socket (14417, 14704) tilted 30 degrees | joined [tested] |
| A plate turned 25 or 30 degrees on a single stud | held by the stud [tested] |

**What does not:**

1. **A bar in the tube of a Bar Tube with Clip (11090) is "Loose", even straight.** [tested] The part has a clip primitive, so `_ends` in `validate.py` drops the name rule that makes a "Bar Tube" a receptacle (`end.rstrip("+-") in families`), and the bar, 20 LDU from the clip, meets no end. 23443 has no primitive and is accepted by name. The library's 11090 is hollow for 10 LDU only (a stop 20 LDU from the clip); a bar pushed further is an overlap, rightly. **This is what cost the Cessna its thin struts**: today's checker run on the builder's own attempt 3 reports two problems, both the Bar 4L "Loose"; the four 11090 on their handles are joined.
2. **On the day, more failed.** The run's own report of attempt 3 called all six strut parts loose. The clip on a handle was apparently fixed by commit c4b5d89 at 17:04, while the run (16:49 to 17:23) was under way. So the builder's conclusion, "bars in clips are loose", is half out of date already.
3. **A hinge drawn open cannot also be declared.** A module's joint must be drawn at rest: the lid hinge opened 20 degrees with its joint line is a problem ("not where the module puts it"); without the line it passes. A raked panel must be left undeclared. [tested] Declared clips, bars, finger hinges and balls are refused outright (the CONTRACT of `movement.py`), so control surfaces on clips can be posed but not said to move.
4. **The summary's words.** "203 of them only by joints the checker cannot confirm" reads as a warning against exactly the joints style needs. The task file already plans to change this.
5. **Joints known only by name are barely placed.** The task file lists a hinge top lifted 8 LDU and a bar tube 30 degrees off its bar as still passing. For style this cuts the other way: an angled panel that passes may not be buildable. A bar strut on 23443 is in this class.

**In order of how much style depends on them:** (1) bars for struts, legs, rails and aerials: blocked at 11090, open through 23443 and plain clips; (2) panels held at an angle on hinges, for raked glass, tapering tails and drooped flaps: open if undeclared; (3) clips on handles at an angle: open; (4) parts turned on one stud: open; (5) ball joints: open, and little used for look.

**What stops it besides the checker:**

- **Its instructions push the other way.** The guide's rule 5 ("Hold everything else by several studs") and rule 9 ("hang nothing on friction alone"), and the prompt's "the checker cannot confirm clips, bars, pins or hinges, so make sure each of those is a real joint", all tell it to avoid the thin joints. Nothing tells it that thick is a fault.
- **No tool places a tilted part.** `place` handles studs in any direction; everything at an angle goes through `add` as a matrix the builder computes. It computed the struts correctly.
- **The colour list** (above), and **no printed parts** in the search index: no registration, no dials.
- **Scale.** The prompt says to take the scale "from one key part". The designers say much the same, but the builder chose 4 wide with an interior nobody can see. Nothing tells it what a given width can and cannot show.
- **The 300-part limit** for anything with an interior.

## 5. Opinion against agreement

**Many sources agree** (designers, builders and the sets):
- Upward faces are finished with curved slopes and tiles; a terrace of studs is the old look.
- Sides are shaped by building sideways; a stack of plate or brick edges is the old look.
- Studs are a choice: kept where they mean something, or as a mark of the medium.
- The scale is chosen so the defining shapes can be made; wider gives truer proportions.
- A small palette, each colour with a job, detail colours few; detail gathered, calm between.
- Plan the outline and the hard parts first.

**Opinion, a single source, or our inference:**
- That bright primaries read as dated: one blogger, and the sets' own colours. Others call colour a matter of taste. The counts of colours by year (the other researchers) should settle it.
- The 70/20/10 split and the stripe a third of the way along: one builder each.
- That trans-black glass reads as modern: seen in sets, said by nobody.
- That bare Technic holes are a fault: our eye, and reviewers' complaints about bright pins. A 2020 Creator car shows them on its sill.
- "Thin things thin": seen at display level; small official planes simply leave struts off.
- The smallest scales in the guide: two Creator planes and one gift set for aircraft; one set each for the object and the small animal; the designers' own account for cars.
- A larger head on a creature: Creator 3-in-1 only; the display cat is true to life.

## Sources that could not be read

- Brick Fanatics (all pages refused; two Speed Champions eight-wide articles were later read from Wayback Machine copies): the Countach "open studs" article, the Concorde designer pieces.
- Eurobricks topics (refused). Tips & Bricks, Bricks magazine: nothing found by search.
- The Advanced Building Techniques Guide itself, and the books (Schwartz, Blackert, McNaught): not read; an excerpt address for McNaught's book returned nothing.
- Chris Stamp's Brickset interview, part 1, and Mike Psiaki's interview were read only in part.
- lego.com's Road Bike design article: search summary only.
