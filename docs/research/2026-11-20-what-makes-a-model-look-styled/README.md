# What makes a brick model look styled, not old

20 November 2026. Started by Alec's verdict on a Cessna 172 the AI builder made that day (206 parts,
built with the structural guide, checker clean): "the style still lacks style ... it looks old - it
looks like an old lego set and isn't styled quite right", next to pictures of a fan designer's large
modern Cessna. This study asks what, concretely, an eye reads as dated or as designed, whether a program
can measure it, and what to tell the builder. The task is `docs/tasks/models-should-look-styled-not-old.md`.

No AI build was made for this study. The fan design is another person's work: it set the bar for
qualities, was not analysed part by part, and neither it nor its pictures are in the repository.

## The short answer

**The Cessna is a 1990s model underneath with a modern surface.** Three independent readings agree:

1. **Its parts list** sits level with the typical official set of 2007 and below every official
   aircraft since 2018 (`tables/how-modern-score.md`).
2. **Its surface, measured**, shows almost no studs (1% of studs left showing; official models show
   10%) but its flanks are stacks of plate edges, almost nothing is built sideways, 77% of what you see
   is one colour, and twelve bare Technic holes face outward (`tables/measured-on-the-surface.md`).
3. **Read as an art director would**, it is "a correct small plane with a good wing and an old body":
   slab flanks, a 1980s livery, a brown block of glass, thick struts, bare wheels (`cessna-critique.md`).

So "looks old" is not studs. Our builds are already smoother than official sets. It is, in order:

| What dates a build | Modern official models | Our AI builds (median of 28) | The Cessna |
|---|---|---|---|
| Flanks made of stacked plates: seams per stud of height on the sides | 0.33 | 0.68 | 0.84 |
| Nothing built sideways: share of the sides that is a tile or slope facing outward | 17% | 3% | 4% |
| Parts for building sideways (brackets, side-stud bricks), share of parts | 10% (vehicles 2018 on) | 3% | 1% |
| Plain bricks, share of parts | 2% | 21% | — |
| Clips, bars and handles, share of parts | 7% | 0% | — |
| The typical part's design year | 2009 | 1978 | 1977 |
| Colours that came after the classics, share of parts | 17% | 3% | 6% |
| Bright red, blue and yellow, share of parts | 11% | 30% | — |
| Colour in large plain areas (0 broken up, 1 one flat patch) | 0.18 | 0.44 | 0.60 |

The first two rows and the last are measured on the models' surfaces (18 official models of 2015 to
2025); the rest are counted from parts lists (official aircraft and cars of 2018 to 2026, 110 sets).

What the builder is told today works against it in four ways the study found:

- Its colour list has 20 solid colours and none of sand blue, sand green, the azures, dark orange,
  medium nougat or bright light orange; and it calls colour 40 "transparent brown (smoke)", which is
  why the Cessna's glass is brown. The neutral smoke of modern sets is Trans Black, 10375.
- The structural guide's rules "hold everything else by several studs" and "hang nothing on friction
  alone", and the prompt's warning about clips and bars, steer it away from every thin joint.
- The checker called the bar struts it first built loose (a bar in the tube of a Bar Tube with Clip,
  11090, is not recognised), so it used Technic beams with holes.
- Nothing tells it to choose the scale by what the subject's shapes need. It chose a fuselage 4 studs
  wide with four seats inside that nobody can see, and stopped 94 parts short of what was asked.

## The result: a style guide

`style-guide.md` (about 1,400 words, for the builder): (a) an art direction of eight lines to write
before the first part (scale and what forced it, colours and their jobs, pattern, the shapes that make
the subject, what is built sideways, what is thin, where studs stay, glass and stance); (b) thirteen
rules of finish, each with the parts that do it; (c) for aircraft, cars, creatures, buildings and
objects, the five things that date that kind and the smallest scale at which it can look right; (d) ten
yes-or-no questions to ask of its own pictures before finishing. Each line carries how strong its
evidence is. It is a draft: no build has used it yet.

## How it was done

Three researchers worked side by side.

- **Parts and colours over the years** (`tables/parts-and-colours-by-year.md`, `tables/how-modern-score.md`,
  `scripts/numbers/`). The mix of kinds of part, the year each part design first appeared, and the
  colours, for 7,836 official sets from 1990 to 2026, for aircraft, cars and creatures old against new,
  and for our 28 distinct AI builds and 18 official models. Since 1995, parts for building sideways
  have gone up about four times and smooth parts three times; plain bricks, plain slopes and hinges have
  more than halved. The 1 x 2 inverted bracket (99780) is in 73% of modern vehicle sets and in 1 of our
  28 builds. A "how modern does the parts list look" score from 0 to 100 (parts' age, smooth share,
  sideways share, later colours, plain bricks) puts official sets of 1995 at a median of 13 and of 2022
  at 77; our builds have a median of 40, the Cessna 40, the sports car built with the structural guide
  79. The score reads a parts list and nothing else: it cannot see shape, proportion, or where a stud
  shows.
- **The surface, measured** (`tables/measured-on-the-surface.md`; the program is on its way into the
  builder's own check). From each model's file and the parts' real shapes: what the five views show
  (studded, smooth, curved, transparent, a bare Technic hole), seams and steps, what is built sideways,
  thin members, the palette by visible area and how it is broken up. The measures that separate official
  models from ours, in order: plate seams on the sides; the share of the sides that is the face of a
  sideways part; flat upright wall; parts not upright; the classic primaries; colours over 5%; colour
  patches.
- **The craft** (`cessna-critique.md`; the evidence file with its sources is being checked quotation by
  quotation before it is added here). What LEGO's designers and long-standing builders have published
  about studs, building sideways, curves, colour, scale and detail, and about 45 official sets read old
  against new from LEGO's own published building instructions and reviews: aircraft and cars first,
  then creatures, buildings and an object. Techniques are described in our own words; no page of
  LEGO's, no step-by-step and no set's design is reproduced.

Three things the craft reading corrected in our own diagnosis: small modern official planes still have
plain studded wings, so the Cessna's wing is ahead of them; no small official high-wing plane has struts
or wheel fairings at all (those are display and fan techniques); and the change in official cars is a
decision made in 2020 (six studs wide to eight), not a slow drift.

## Limits

- The official models measured on the surface are 18, all recent, of mixed subjects; our builds include
  many one-colour ducks and cats, which inflates the colour numbers against us.
- "Bright primaries look dated" rests on the sets' own colours by year and one writer; others call
  colour a matter of taste. "No bare Technic holes" and "thin things thin" are our eye, supported by
  what display models do, stated by no designer we found.
- The smallest workable scales in the guide rest on few sets (for aircraft: two Creator planes and one
  gift set).
- The parts-list score was anchored on two clusters of years and checked against one judgement.
- Whether the guide changes what the builder makes is untested until builds are made with it.

## Credits

Set inventories from the Rebrickable catalogue (rebrickable.com), November 2026: only totals are used,
no set's parts list is reproduced, and the catalogue files are not in this repository (see the decision
of 19 November). The official models measured are community LDraw files (CC BY), by the authors listed
in `docs/research/2026-11-19-how-real-sets-are-built/README.md`; they are not in this repository
either. LEGO is a trademark of the LEGO Group, which does not sponsor or endorse this project.
