# Numbers: what official LEGO sets are made of, and in what order they go together

> **Editor's note.** This is one of the eight reports behind the study in `../README.md`, kept as its evidence. It is as its researcher wrote it, except for what this note lists. Points where the reports disagree with each other are dealt with in the README, not corrected here.
> Changed: the mention of the common brief, a remark addressed to the study's coordinator, and the list of folders and script files on the researcher's computer were removed.
> **Limits of use.** Every table in Part A is worked out from the Rebrickable catalogue (rebrickable.com), whose terms allow use with credit and say that no Rebrickable content may be used in the training of AI models. Nothing here trains a model: these are aggregate statistics, and the project's owner decided on 19 November 2026 that such figures may also be quoted in the guide beside the README. Keep this file itself out of any AI model's training data.
> **A count that does not agree with itself.** The text says 41 models had usable steps (17 + 18 + 6); the tables say 42 (49 fetched less the 7 named as unusable; 18 + 18 + 6 in B-T2 and B-T4; 42 rows in B-T3). The README uses 42, so "27 of 41" below is read as 27 of 42.

Part `numbers` of the sets study. Two sources, both checked before use:
**A**, Rebrickable's free catalogue downloads (parts lists of every set), and **B**, the LDraw
Official Model Repository (official sets drawn as LDraw files, most with building steps).

Everything here is **[measured]** from those files with my own scripts unless marked otherwise.
**[seen]** = read on a web page (address given). **[recalled]** = general knowledge, not checked.
No booklet was read for this part (see "What failed").

## Summary (the numbers that matter)

1. **Outside Technic, pin-and-beam parts are a small minority at every size.** The median share of
   Technic beams, pins, axles, connectors and Technic bricks rises from 0 % (under 100 parts) to about
   5 % at 350-500 parts and peaks at **7-8 % at 750-1,500 parts**, then falls again (5 % at 1,500-2,500,
   4.5 % at 2,500+). Liftarm beams themselves are rarer still: the median set of any size has under
   0.5 % liftarms. What changes with size is how many sets have a real *frame*: the share of sets with at
   least 10 liftarms goes 0 % (<100 parts), 2-3 % (100-350), 6 % (350-500), **17 % (500-750), 22 %
   (750-1,000), 32 % (1,000-1,500), 42-43 % (1,500+)** (table P1; 5,711 non-Technic sets).
2. **The change happens at about 500 parts, and only in some themes.** Star Wars, Ninjago, Monkie Kid,
   Super Heroes, the large adult display range and Ideas cross into frames at 500-1,000 parts (a fifth to
   two thirds of sets have 10+ liftarms); City, Friends, Creator 3-in-1, Speed Champions, Harry Potter,
   Disney and Minecraft mostly never do; Architecture, BrickHeadz and Classic never do (table P2).
   Botanicals are the exception in kind: 17 % pin/beam parts on average with almost no liftarms; their
   "Technic" parts are axles and connectors used as stems (table P2b).
3. **In the build order, a pin-and-beam core is the exception, not the rule.** In 32 non-Technic models
   with real steps that contain any pin/beam parts, those parts were at least twice as common in the first
   20 % of the build as overall in only **6**; in **13** they were at most half as common (they go on
   later). What the first tenth of a non-Technic build is made of, on average: **plates 27-30 %**,
   tiles 11-15 %, slopes, curves and wedges 10 %, pin/beam 9-12 %, bricks 5-8 %, sideways-building parts 6-8 %; joints and
   slopes are what grow later (B-T2, B-T9).
4. **Sideways building grows through the build; almost nothing is built upside down.** Of the studded parts,
   the median model places 10 % sideways in the first third of its steps, 26 % in the middle, 32 % in
   the last third; upside-down placements are about 0-2 % throughout. Wheels go on late (median position
   0.86 of the build), hinges from about a fifth of the way in (B-T5, B-T6, B-T10).

Other numbers for a builder's guide: a 100-150-part set uses a median **45 different parts in 13
colours** (52 part-and-colour combinations, so most parts appear about twice); a 1,000-1,500-part set uses
190 different parts in 24 colours. Plates are the biggest single job at every size (13 % of parts under
150, 21 % over 1,500); tiles hold steady at 10-14 %; slopes plus curved slopes about 11-12 %. Joints
(hinges, turntables, clips, bars, ball joints) are 12-14 % of a small set and 7 % of a big one.
Building steps (as reproduced in the OMR files) add a median of **2 parts per step** (mean about 3) outside Technic and **about
6 per step** in Technic, steady from the start of a build to its end.

## Sources, licences and terms

**A. Rebrickable catalogue downloads.**
- Page: `https://rebrickable.com/downloads/`. The live page is behind a browser check (HTTP 403 to a
  plain client, a "Just a moment" challenge), so I read it, and the Terms page, through the Internet
  Archive copies (`https://web.archive.org/web/20261029125803/https://rebrickable.com/downloads/` and
  `https://web.archive.org/web/20260501095206/https://rebrickable.com/terms/`). The files themselves are
  served from `https://cdn.rebrickable.com/media/downloads/<name>.csv.gz` with no check.
- Terms **[seen]** on the downloads page: "Free for personal and commercial use, provided you
  acknowledge Rebrickable as your data source." "You may automate downloading these archives at most once
  a day. Scraping our web pages is strictly against our Terms and will get you banned." I downloaded nine
  files once (themes, colors, part_categories, parts, sets, inventories, inventory_parts, inventory_sets,
  part_relationships; about 16 MB compressed), dated 19 Nov 2026, and touched no other Rebrickable page
  except the API documentation page.
- Terms of Service **[seen]**, section 5.3: "No Rebrickable content may be used in the training of AI
  models." This study only measures and summarises; it trains nothing. **If any of this data (not just
  conclusions drawn from it) is ever put into a model's training set, that would break Rebrickable's
  terms.** Putting a few derived statistics into a written guide with credit to Rebrickable is, as I read
  it, within "acknowledge Rebrickable as your data source".
- Credit line to use: "Set inventories from the Rebrickable catalogue (rebrickable.com), November 2026."

**B. LDraw Official Model Repository (OMR).**
- Exists **[seen]**: `https://library.ldraw.org/omr` (set list at `https://library.ldraw.org/omr/sets`,
  one page per set at `https://library.ldraw.org/omr/sets/<id>` with a download link to
  `https://library.ldraw.org/media/omr_models/<n>/<set>.mpd`). It "contains only LDraw replicas of sets
  (and their submodels) released by the LEGO Group" (rules page below).
- Size **[measured]** from the set list (59 pages fetched 2 s apart): **1,470 sets**, 1955-2026, but thin
  on recent years: 240 from 2015-19, 78 from 2020-24, 4 from 2025-26; **322 from 2015 onward**. Recent
  coverage by theme: Technic 82, BrickHeadz 76, Creator 3-in-1 20, Architecture 24, Ideas 12, Creator
  Expert 11, Icons 8, Star Wars 12, Harry Potter 7, Speed Champions 6, Modular Buildings 6, City 9,
  Friends 1, Botanicals 3. Over all years Town (259) and Technic (183) lead.
- Licence **[seen]**: rules page
  `https://library.ldraw.org/documentation/official-model-repository-omr-standards/rules-and-procedures-for-the-official-model-repository`:
  new models "0 !LICENSE Licensed under CC BY 4.0", older ones CC BY 2.0 and 4.0. The files I fetched:
  48 say "Redistributable under CCAL version 2.0" (= CC BY 2.0), 1 says CC BY 4.0. Attribution to each
  file's named author is required. The LDraw licence covers the files, not LEGO's designs, which stay
  LEGO's.
- Do the steps follow LEGO's booklets? The specification `https://ldraw.org/article/593.html` **[seen]**
  only asks that "any META commands used should enable any instructions generated to be as close to the
  official instructions" as possible; steps are not required. **[measured]** in my 49 files: 7 have no
  steps or far too few (more than 8 parts per step on average: 21026, 31039, 41498, 41596, 60065, 60067,
  10258) and were left out of the order measures. 9 files name their sub-models after booklet step numbers
  (for example "Shorthair Cat - Step 16", "Kitten - Steps 16 to 20", "rose-flower-step7"), which shows
  those authors worked from the booklet (10280, 10281, 21036, 21046, 21319, 40379, 40433, 40441, 75272).
  For the rest I could not compare with a booklet (see "What failed"), so **the order measures assume the
  OMR author followed the booklet; that is likely but not verified per file.**
- Fetched: 49 models (one per set; the main model where a set has several), each after its set page,
  one at a time, 2 s apart (about 100 requests in all, plus the 59 list pages). Plain client name, no
  personal or project details in any request.

## Method

**Part A.** Sets from 2015 onward (15,152 in the catalogue; 9,054 with a parts inventory). For each set
the first inventory version, spare parts excluded, printed and patterned parts folded into their plain
part (Rebrickable's P and T relationships). Left out: sets under 10 parts; Duplo, Primo, Quatro, books,
gear, collectible minifigures, LEGO Art and DOTS, mosaics, bulk and service packs, education, FIRST LEGO
League, Mindstorms, promotional and brand-store sets, and the BrickLink Designer Program (fan designs).
**5,935 sets remain.** Shares are of *build parts*: minifigure parts, minifigure accessories and stickers
are not counted. Size bands use Rebrickable's own part count for the set (`num_parts`, which includes
minifigure parts). Theme groups follow Rebrickable's theme tree: Technic, City (all City sub-themes),
Friends, Speed Champions, Creator 3-in-1, other Creator, Botanicals (theme 769, which holds the 2021-26
Botanical sets), Architecture, BrickHeadz, Ideas, Star Wars (play sets; the Ultimate Collector Series goes
into the adult display group), "Adult display" = Icons + Creator Expert + Modular Buildings + Star Wars UCS,
Ninjago, Super Heroes (Marvel and DC), Harry Potter, Minecraft, Disney, Classic, Super Mario, Jurassic
World, Dreamzzz, Monkie Kid, and "Other themes".

How parts were sorted into jobs (script `classify.py`, one job per part, first rule that matches wins):
- **pin/beam**: Rebrickable categories Technic Beams, Technic Beams Special, Technic Pins, Technic
  Connectors, Technic Axles, Technic Bushes, Technic Bricks, plus any part whose name starts "Technic
  Plate" or "Technic Brick". Sub-split into liftarm beams / pins / axles+connectors+bushes / Technic
  bricks and plates where shown.
- **other Technic**: gears, Technic panels, steering and suspension, Technic Special, pneumatics,
  electronics.
- **wheel/tyre**: category Wheels and Tyres. **wheel holder**: names with "wheel holder", "wheel pins",
  "stub axle".
- **sideways**: in the special brick, special plate, panel and round categories, names with "bracket",
  "stud(s) on ... side(s)", "side stud", "studs on ... end", or the 1 x 1 "with headlight" brick; hinge
  parts excluded.
- **hinge** (category Hinges, Arms and Turntables, or "hinge" in the name), **turntable**, **ball/towball**
  ("towball", "ball", "socket", "rotation joint"), **clip** ("clip", "bar holder"), **bar** (Bars, Ladders
  and Fences category items named bar/antenna/lever, and "bar" or "handle" in special bricks, plates and
  tiles). "Joints" = these five together.
- **brick, plate, tile, slope, curved slope, wedge, round**: Rebrickable categories Bricks, Plates, Tiles
  (+ Tiles Special + Tiles Round and Curved), Bricks Sloped (includes inverted slopes), Bricks Curved,
  Bricks/Plates Wedged, Bricks Round and Cones / Plates Round Curved and Dishes. **other special** =
  special bricks and plates not caught above (jumper plates, plates with pin holes, grilles, logs).
  **plant**, **panel/window**, **other** (windows, doors, rocks, animals, flags and the rest).

Where this sorting is rough: "sideways" counts the part type, not how it is used (a bracket can sit flat;
a plain brick can be built sideways and is not counted); "bar" includes handles and bar-holding tiles; a
"Technic brick" in a City set is often just a beam-shaped brick in a wall or chassis, so pin/beam
overstates frames there (the liftarm count is the cleaner signal of a frame); round plates and cones sit
in "round", not "plate"; Rebrickable's categories are good but not perfect (for example the "ingot" tile
is named "Gold Bar" and had to be moved to tiles by hand). Means are means of per-set shares (every set
counts the same, whatever its size).

**Part B.** Scripts `omr_analyse.py` and `omr_report.py`. Each MPD is read as text; embedded unofficial
parts (any file whose `!LDRAW_ORG` line is not "Model") are treated as parts. The build is *unrolled* the
way a booklet presents it: the main file's steps in order, and when a step uses a sub-model, that
sub-model's steps are emitted first, recursively (a sub-model used in two places is built twice). Every
part gets its world position and orientation, and a job from the same classifier as Part A, through the
Rebrickable part table (LDraw and Rebrickable numbers mostly agree; prints, stickered versions and set
prefixes of embedded parts are stripped; the LDraw library's own description is the fall-back). Minifigure
and sticker parts are dropped; unknown parts (flexible hose segments, a few moved parts: at most 2 % of a
model except 42080 and 60216 with many hose segments) are dropped. "Stepped" models (at least 10 steps
and at most 8 parts per step on average) are used for the order measures: **41 of 49**.
- Height: LDraw's -y is up; OMR models stand as displayed. Height rho = Spearman rank correlation of
  build order with height; outward rho = with horizontal distance from the model's centre.
- Orientation: a studded System part (brick, plate, tile, slope, wedge, round, sideways part, other
  special) is "up" if its top points within about 25 degrees of up, "upside down" if within 25 degrees
  of down, "sideways" if within about 6 degrees of horizontal, "angled" otherwise. Technic models are
  left out (they have few studded parts and LDraw's resting orientation of beams says nothing about
  building direction).
- Sub-models: those whose own parts are mostly minifigure parts are left out. A wrapper scene (a top
  file that only places one model plus figures) is skipped when deciding what is "built in a
  sub-model".

## Part A results: what sets are made of

Read A1 for the character of each theme, A3 for theme by size. Every row gives the number of sets.
### A1. Mean share of build parts by job, by theme group (sets 2015 onward, all sizes)

| group | sets | median parts | pin/beam | other Technic | sideways | hinge | turntable | clip | bar | ball/towball | wheel/tyre | brick | plate | tile | slope | curved slope | wedge | round | other special | plant | panel/window | other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Technic | 224 | 606 | 80.8 | 10.0 | 0.1 | 0.1 | 0.0 | 0.2 | 0.4 | 0.0 | 3.0 | 0.0 | 0.8 | 1.5 | 0.3 | 0.3 | 0.1 | 1.1 | 0.4 | 0.0 | 0.0 | 0.8 |
| Speed Champions | 102 | 274 | 4.7 | 0.1 | 11.2 | 0.8 | 0.0 | 3.1 | 2.9 | 0.1 | 4.4 | 2.4 | 21.1 | 14.3 | 5.6 | 6.0 | 5.0 | 7.9 | 5.3 | 0.1 | 1.7 | 2.9 |
| Creator 3-in-1 | 182 | 286 | 6.7 | 0.8 | 6.8 | 1.1 | 0.1 | 4.1 | 3.4 | 1.5 | 1.6 | 5.3 | 19.1 | 10.4 | 6.6 | 8.5 | 3.4 | 10.6 | 5.1 | 1.2 | 1.3 | 1.8 |
| Adult display (Icons/Creator Expert/UCS/Modular) | 142 | 1779 | 9.5 | 0.8 | 6.7 | 1.2 | 0.1 | 2.9 | 3.0 | 0.4 | 0.5 | 7.3 | 22.4 | 14.2 | 5.4 | 5.3 | 2.8 | 7.2 | 6.6 | 1.2 | 1.6 | 1.2 |
| Botanicals | 53 | 372 | 17.1 | 0.9 | 3.4 | 0.9 | 0.1 | 9.4 | 7.3 | 0.3 | 0.2 | 1.0 | 6.9 | 4.7 | 1.5 | 5.1 | 1.1 | 15.7 | 3.3 | 16.5 | 0.3 | 4.4 |
| Architecture | 40 | 718 | 2.5 | 0.1 | 6.7 | 0.6 | 0.0 | 2.0 | 2.4 | 0.0 | 0.1 | 5.5 | 26.7 | 23.2 | 7.2 | 2.1 | 0.9 | 9.0 | 7.5 | 1.4 | 1.4 | 0.7 |
| BrickHeadz | 196 | 185 | 0.3 | 0.1 | 15.5 | 0.2 | 0.0 | 2.2 | 0.8 | 0.0 | 0.0 | 6.2 | 31.2 | 18.0 | 5.0 | 8.0 | 1.8 | 5.0 | 4.6 | 0.7 | 0.1 | 0.2 |
| Ideas | 98 | 1039 | 7.1 | 0.5 | 7.6 | 0.9 | 0.1 | 2.9 | 2.7 | 0.3 | 0.3 | 7.2 | 21.2 | 15.5 | 4.5 | 5.6 | 2.3 | 9.0 | 5.7 | 3.2 | 1.7 | 1.5 |
| City | 566 | 165 | 5.7 | 0.9 | 3.8 | 1.3 | 0.2 | 4.0 | 4.0 | 0.3 | 7.9 | 5.4 | 15.3 | 12.7 | 6.5 | 5.1 | 2.2 | 6.8 | 5.6 | 0.9 | 2.4 | 7.7 |
| Friends | 547 | 118 | 2.3 | 0.3 | 3.3 | 0.6 | 0.3 | 3.7 | 4.3 | 0.1 | 1.5 | 8.6 | 14.6 | 14.4 | 4.2 | 5.2 | 0.6 | 14.4 | 6.3 | 6.6 | 3.7 | 4.9 |
| Star Wars (play) | 539 | 191 | 11.5 | 0.7 | 6.3 | 1.6 | 0.1 | 4.2 | 4.4 | 1.4 | 0.3 | 3.1 | 18.1 | 9.7 | 6.7 | 5.0 | 5.8 | 11.5 | 6.1 | 0.2 | 0.5 | 2.7 |
| Ninjago | 375 | 213 | 10.1 | 1.4 | 5.9 | 1.2 | 0.1 | 7.4 | 4.1 | 2.1 | 1.2 | 3.8 | 13.3 | 7.8 | 8.0 | 5.2 | 4.8 | 10.3 | 5.2 | 0.7 | 0.7 | 6.5 |
| Super Heroes | 454 | 226 | 7.1 | 0.6 | 6.3 | 1.3 | 0.1 | 6.0 | 4.5 | 1.4 | 3.0 | 3.6 | 13.1 | 9.5 | 7.6 | 6.0 | 4.6 | 11.9 | 5.1 | 0.3 | 1.2 | 6.7 |
| Harry Potter | 142 | 400 | 4.6 | 0.3 | 5.9 | 1.0 | 0.1 | 2.6 | 3.1 | 0.3 | 0.8 | 7.8 | 17.4 | 11.7 | 6.3 | 5.1 | 2.1 | 13.7 | 8.5 | 1.7 | 3.6 | 3.0 |
| Minecraft | 170 | 256 | 3.8 | 0.1 | 3.1 | 1.7 | 0.0 | 2.0 | 2.1 | 0.5 | 0.0 | 21.4 | 28.0 | 11.6 | 0.9 | 0.2 | 0.0 | 6.6 | 12.9 | 3.2 | 0.7 | 1.2 |
| Disney | 231 | 200 | 2.5 | 0.2 | 4.2 | 0.6 | 0.3 | 3.1 | 3.2 | 0.3 | 0.9 | 7.9 | 13.3 | 11.4 | 6.8 | 7.8 | 2.1 | 12.7 | 8.8 | 5.9 | 2.7 | 5.2 |
| Creator (other) | 77 | 56 | 3.3 | 0.2 | 6.8 | 1.0 | 0.3 | 4.5 | 5.5 | 1.8 | 3.9 | 4.1 | 16.9 | 11.6 | 6.0 | 9.4 | 2.9 | 9.8 | 5.8 | 1.8 | 0.5 | 2.7 |
| Classic | 67 | 484 | 1.0 | 0.2 | 4.9 | 0.1 | 0.2 | 1.4 | 1.6 | 0.2 | 3.4 | 30.4 | 11.0 | 6.1 | 13.7 | 6.4 | 0.8 | 9.1 | 3.7 | 1.6 | 1.7 | 1.3 |
| Super Mario | 155 | 133 | 5.6 | 0.2 | 7.8 | 1.1 | 0.1 | 1.5 | 1.7 | 0.2 | 0.2 | 6.8 | 13.9 | 15.3 | 6.6 | 7.8 | 1.3 | 12.9 | 8.5 | 4.4 | 1.4 | 2.7 |
| Jurassic World | 126 | 82 | 7.0 | 0.2 | 4.2 | 0.9 | 0.2 | 7.8 | 5.3 | 0.7 | 3.7 | 4.2 | 14.9 | 9.0 | 6.9 | 5.7 | 3.3 | 7.7 | 6.2 | 2.7 | 1.4 | 7.4 |
| Dreamzzz | 58 | 335 | 9.1 | 0.8 | 8.9 | 0.6 | 0.0 | 6.0 | 5.1 | 2.3 | 0.8 | 2.0 | 12.5 | 11.5 | 3.8 | 7.4 | 2.6 | 14.4 | 4.6 | 1.5 | 0.5 | 5.5 |
| Monkie Kid | 57 | 775 | 12.6 | 0.8 | 7.9 | 1.2 | 0.1 | 5.4 | 4.2 | 1.2 | 1.4 | 3.5 | 13.3 | 8.8 | 6.0 | 6.3 | 3.8 | 10.8 | 5.4 | 1.3 | 0.9 | 4.9 |
| Other themes | 1334 | 160 | 6.2 | 2.0 | 5.4 | 0.9 | 0.2 | 4.0 | 3.1 | 1.4 | 1.3 | 6.4 | 15.5 | 12.8 | 6.4 | 5.7 | 2.2 | 11.3 | 6.6 | 3.0 | 1.1 | 4.1 |
| **all** | 5935 | 215 | 9.1 | 1.2 | 5.6 | 1.0 | 0.1 | 4.0 | 3.5 | 0.9 | 2.0 | 6.1 | 15.9 | 11.6 | 5.9 | 5.5 | 2.7 | 10.3 | 6.1 | 2.4 | 1.5 | 4.2 |

### A2. Mean share by job, by size band (all groups except Technic)

| band | sets | pin/beam | other Technic | sideways | hinge | turntable | clip | bar | ball/towball | wheel/tyre | brick | plate | tile | slope | curved slope | wedge | round | other special | plant | panel/window | other | distinct parts (median) | distinct colours (median) | distinct part+colour (median) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| <150 | 2347 | 4.8 | 1.1 | 5.1 | 0.9 | 0.2 | 5.3 | 4.4 | 1.4 | 3.3 | 4.9 | 13.7 | 11.3 | 6.0 | 5.5 | 2.5 | 12.2 | 6.4 | 3.0 | 1.2 | 6.2 | 23 | 9 | 25 |
| 150-500 | 1912 | 6.2 | 0.8 | 6.2 | 1.1 | 0.1 | 3.8 | 3.2 | 0.8 | 1.4 | 6.7 | 17.9 | 12.4 | 6.4 | 6.1 | 2.8 | 10.1 | 6.4 | 2.3 | 1.7 | 3.6 | 78 | 17 | 100 |
| 500-1500 | 1172 | 9.0 | 0.8 | 6.3 | 1.1 | 0.1 | 3.1 | 2.8 | 0.4 | 0.7 | 7.9 | 19.0 | 12.1 | 6.2 | 5.6 | 3.2 | 9.1 | 6.0 | 1.9 | 1.9 | 2.6 | 154 | 23 | 219 |
| >1500 | 280 | 7.3 | 0.6 | 6.9 | 1.0 | 0.1 | 2.6 | 2.6 | 0.3 | 0.3 | 9.4 | 21.0 | 14.0 | 5.9 | 5.3 | 2.8 | 7.8 | 6.9 | 1.8 | 2.1 | 1.4 | 244 | 28 | 440 |

### A3. By theme group and size band: shares (%) of the main jobs, and variety

Columns: pin/beam = Technic pins, beams, axles, connectors, bushes, Technic bricks/plates; sideways = brackets and bricks/plates with side studs; joints = hinges + turntables + clips + bars + ball/towball joints; basic = plain bricks + plates + tiles + slopes + curved slopes. Distinct = medians.

| group | band | sets | pin/beam | sideways | joints | brick | plate | tile | slope | curved slope | distinct parts | distinct colours |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Technic | <150 | 45 | 78.4 | 0.0 | 1.1 | 0.1 | 0.1 | 0.7 | 0.1 | 0.0 | 28 | 9 |
| Technic | 150-500 | 56 | 80.6 | 0.0 | 0.6 | 0.0 | 0.6 | 1.3 | 0.5 | 0.3 | 60 | 11 |
| Technic | 500-1500 | 85 | 81.5 | 0.2 | 0.7 | 0.0 | 1.1 | 1.8 | 0.4 | 0.5 | 121 | 14 |
| Technic | >1500 | 38 | 82.4 | 0.2 | 0.9 | 0.1 | 1.2 | 2.0 | 0.4 | 0.4 | 180 | 16 |
| Speed Champions | <150 | 9 | 2.9 | 7.5 | 3.6 | 2.3 | 19.7 | 14.2 | 2.8 | 5.9 | 29 | 6 |
| Speed Champions | 150-500 | 74 | 4.6 | 12.1 | 6.7 | 2.1 | 21.0 | 14.5 | 5.9 | 6.1 | 83 | 12 |
| Speed Champions | 500-1500 | 19 | 5.8 | 9.7 | 8.8 | 3.7 | 22.1 | 13.9 | 5.8 | 5.8 | 133 | 16 |
| Creator 3-in-1 | <150 | 38 | 6.7 | 6.8 | 12.1 | 2.2 | 19.1 | 9.6 | 5.0 | 11.6 | 39 | 10 |
| Creator 3-in-1 | 150-500 | 99 | 7.0 | 6.6 | 10.6 | 5.3 | 19.3 | 10.8 | 6.8 | 8.3 | 79 | 17 |
| Creator 3-in-1 | 500-1500 | 44 | 6.1 | 7.2 | 7.9 | 8.2 | 18.5 | 10.5 | 7.5 | 6.3 | 144 | 24 |
| Creator 3-in-1 | >1500 | 1 | (too few) |||||||||| 
| Adult display (Icons/Creator Expert/UCS/Modular) | <150 | 1 | (too few) |||||||||| 
| Adult display (Icons/Creator Expert/UCS/Modular) | 150-500 | 14 | 5.5 | 7.3 | 8.0 | 7.1 | 17.8 | 18.2 | 4.7 | 7.1 | 74 | 13 |
| Adult display (Icons/Creator Expert/UCS/Modular) | 500-1500 | 42 | 11.6 | 7.2 | 7.4 | 4.4 | 22.7 | 13.5 | 5.6 | 6.2 | 170 | 18 |
| Adult display (Icons/Creator Expert/UCS/Modular) | >1500 | 85 | 8.8 | 6.4 | 7.6 | 8.8 | 23.0 | 13.9 | 5.4 | 4.5 | 256 | 25 |
| Botanicals | <150 | 11 | 16.3 | 4.0 | 20.5 | 0.2 | 5.0 | 3.3 | 1.0 | 6.4 | 16 | 9 |
| Botanicals | 150-500 | 22 | 16.3 | 3.5 | 18.7 | 1.1 | 8.5 | 4.7 | 1.4 | 5.2 | 48 | 16 |
| Botanicals | 500-1500 | 20 | 18.3 | 3.0 | 15.7 | 1.2 | 6.1 | 5.4 | 1.9 | 4.4 | 74 | 22 |
| Architecture | 150-500 | 11 | 3.2 | 6.7 | 7.0 | 3.4 | 29.4 | 22.9 | 8.9 | 2.7 | 48 | 9 |
| Architecture | 500-1500 | 20 | 2.8 | 5.9 | 4.2 | 6.0 | 27.0 | 23.7 | 6.6 | 1.8 | 83 | 15 |
| Architecture | >1500 | 9 | 1.0 | 8.5 | 4.2 | 7.0 | 22.7 | 22.7 | 6.2 | 2.1 | 149 | 16 |
| BrickHeadz | <150 | 73 | 0.4 | 16.3 | 3.1 | 7.3 | 30.8 | 18.3 | 3.5 | 7.8 | 33 | 10 |
| BrickHeadz | 150-500 | 106 | 0.3 | 15.2 | 3.3 | 5.7 | 31.0 | 17.9 | 5.8 | 7.8 | 49 | 15 |
| BrickHeadz | 500-1500 | 17 | 0.1 | 13.9 | 2.7 | 4.4 | 33.5 | 17.8 | 6.9 | 10.3 | 70 | 22 |
| Ideas | <150 | 1 | (too few) |||||||||| 
| Ideas | 150-500 | 25 | 3.9 | 7.4 | 7.7 | 7.1 | 19.0 | 18.8 | 4.1 | 5.0 | 61 | 15 |
| Ideas | 500-1500 | 42 | 8.0 | 7.1 | 7.5 | 6.9 | 22.5 | 14.1 | 4.2 | 5.7 | 145 | 22 |
| Ideas | >1500 | 30 | 7.1 | 7.7 | 5.9 | 7.9 | 22.1 | 14.5 | 5.4 | 6.2 | 226 | 28 |
| City | <150 | 275 | 5.2 | 3.1 | 10.8 | 3.2 | 13.6 | 11.7 | 5.8 | 5.4 | 23 | 9 |
| City | 150-500 | 184 | 5.4 | 4.4 | 9.3 | 6.4 | 17.3 | 13.4 | 7.3 | 5.1 | 94 | 18 |
| City | 500-1500 | 102 | 7.8 | 4.7 | 7.9 | 9.2 | 16.3 | 14.3 | 6.7 | 4.7 | 184 | 23 |
| City | >1500 | 5 | 3.6 | 5.8 | 7.2 | 12.3 | 16.6 | 14.4 | 7.1 | 3.7 | 277 | 27 |
| Friends | <150 | 288 | 1.0 | 3.2 | 10.6 | 6.6 | 12.7 | 13.2 | 4.3 | 4.4 | 20 | 12 |
| Friends | 150-500 | 162 | 3.2 | 3.1 | 7.8 | 9.9 | 16.3 | 15.4 | 4.0 | 6.3 | 88 | 24 |
| Friends | 500-1500 | 91 | 4.5 | 3.9 | 6.3 | 12.1 | 17.5 | 15.6 | 4.0 | 5.6 | 167 | 33 |
| Friends | >1500 | 6 | 3.3 | 4.7 | 4.1 | 16.2 | 15.4 | 21.5 | 3.7 | 3.2 | 244 | 44 |
| Star Wars (play) | <150 | 248 | 9.8 | 6.5 | 15.3 | 1.9 | 14.6 | 8.9 | 6.6 | 4.6 | 24 | 7 |
| Star Wars (play) | 150-500 | 138 | 11.6 | 6.3 | 10.1 | 4.7 | 18.4 | 9.9 | 7.1 | 5.3 | 82 | 13 |
| Star Wars (play) | 500-1500 | 143 | 14.3 | 6.0 | 7.2 | 3.6 | 23.3 | 11.0 | 6.6 | 5.3 | 149 | 17 |
| Star Wars (play) | >1500 | 10 | 10.4 | 5.8 | 7.1 | 6.4 | 27.2 | 11.3 | 5.2 | 6.1 | 227 | 20 |
| Ninjago | <150 | 162 | 4.5 | 5.0 | 18.0 | 4.9 | 12.3 | 8.0 | 8.2 | 4.9 | 21 | 8 |
| Ninjago | 150-500 | 100 | 13.7 | 5.8 | 15.3 | 2.3 | 13.1 | 7.0 | 7.6 | 5.6 | 86 | 16 |
| Ninjago | 500-1500 | 96 | 15.9 | 7.4 | 10.4 | 3.3 | 14.4 | 7.5 | 8.3 | 5.3 | 170 | 21 |
| Ninjago | >1500 | 17 | 10.3 | 7.7 | 9.1 | 6.4 | 16.5 | 12.3 | 7.0 | 5.1 | 308 | 30 |
| Super Heroes | <150 | 176 | 4.4 | 5.6 | 17.5 | 2.1 | 7.5 | 8.6 | 7.1 | 5.8 | 24 | 8 |
| Super Heroes | 150-500 | 186 | 8.6 | 6.5 | 11.4 | 3.8 | 15.6 | 9.5 | 8.0 | 6.5 | 91 | 16 |
| Super Heroes | 500-1500 | 70 | 9.4 | 6.8 | 9.7 | 5.1 | 18.0 | 10.8 | 7.6 | 5.9 | 156 | 20 |
| Super Heroes | >1500 | 22 | 8.1 | 7.3 | 6.9 | 8.2 | 20.1 | 14.1 | 7.0 | 5.2 | 267 | 26 |
| Harry Potter | <150 | 30 | 3.0 | 5.9 | 6.1 | 3.6 | 15.9 | 10.2 | 5.5 | 4.4 | 17 | 8 |
| Harry Potter | 150-500 | 47 | 4.4 | 6.1 | 8.6 | 7.8 | 17.3 | 12.1 | 5.3 | 5.8 | 72 | 17 |
| Harry Potter | 500-1500 | 49 | 6.2 | 5.4 | 7.2 | 9.5 | 17.4 | 11.8 | 6.9 | 4.9 | 144 | 25 |
| Harry Potter | >1500 | 16 | 2.9 | 6.6 | 4.2 | 10.5 | 20.7 | 13.3 | 8.5 | 5.1 | 256 | 34 |
| Minecraft | <150 | 53 | 4.8 | 2.3 | 10.5 | 12.1 | 28.6 | 9.5 | 0.8 | 0.2 | 12 | 7 |
| Minecraft | 150-500 | 74 | 3.4 | 3.7 | 4.9 | 24.0 | 28.6 | 12.3 | 0.9 | 0.2 | 54 | 19 |
| Minecraft | 500-1500 | 41 | 3.1 | 3.2 | 4.0 | 27.8 | 26.9 | 13.1 | 0.9 | 0.1 | 79 | 24 |
| Minecraft | >1500 | 2 | (too few) |||||||||| 
| Disney | <150 | 91 | 1.5 | 2.9 | 8.3 | 6.8 | 10.9 | 8.8 | 7.1 | 8.1 | 33 | 14 |
| Disney | 150-500 | 79 | 2.3 | 3.8 | 7.4 | 9.3 | 12.8 | 13.2 | 6.8 | 7.3 | 81 | 23 |
| Disney | 500-1500 | 48 | 3.8 | 6.5 | 6.6 | 7.3 | 17.0 | 12.7 | 6.3 | 8.2 | 142 | 28 |
| Disney | >1500 | 13 | 4.9 | 8.2 | 5.6 | 8.6 | 19.7 | 13.1 | 6.4 | 6.8 | 237 | 31 |
| Creator (other) | <150 | 61 | 2.8 | 7.0 | 14.8 | 3.3 | 16.2 | 9.1 | 5.7 | 10.9 | 23 | 8 |
| Creator (other) | 150-500 | 16 | 5.0 | 6.0 | 6.7 | 6.9 | 19.8 | 20.9 | 7.1 | 3.9 | 54 | 18 |
| Classic | <150 | 12 | 0.2 | 6.2 | 4.6 | 15.6 | 14.4 | 7.8 | 13.4 | 7.0 | 30 | 12 |
| Classic | 150-500 | 22 | 1.3 | 6.0 | 3.6 | 29.6 | 9.5 | 5.3 | 16.8 | 7.5 | 64 | 26 |
| Classic | 500-1500 | 24 | 1.2 | 3.7 | 3.0 | 35.4 | 10.6 | 6.1 | 12.2 | 5.9 | 102 | 34 |
| Classic | >1500 | 9 | 0.4 | 3.9 | 4.1 | 38.8 | 10.7 | 5.4 | 10.7 | 4.6 | 115 | 39 |
| Super Mario | <150 | 79 | 2.5 | 8.9 | 4.7 | 5.6 | 10.0 | 16.5 | 7.0 | 8.2 | 17 | 8 |
| Super Mario | 150-500 | 44 | 7.8 | 6.4 | 4.9 | 8.0 | 16.5 | 14.2 | 6.3 | 7.4 | 92 | 19 |
| Super Mario | 500-1500 | 27 | 9.7 | 6.9 | 4.2 | 8.4 | 19.2 | 13.3 | 6.0 | 7.4 | 176 | 25 |
| Super Mario | >1500 | 5 | 11.8 | 8.8 | 3.1 | 4.6 | 23.7 | 16.5 | 5.9 | 7.6 | 263 | 22 |
| Jurassic World | <150 | 71 | 5.7 | 2.7 | 18.5 | 3.2 | 12.7 | 7.4 | 6.5 | 5.5 | 17 | 7 |
| Jurassic World | 150-500 | 33 | 7.2 | 5.7 | 11.3 | 5.3 | 18.2 | 11.7 | 7.6 | 5.5 | 93 | 18 |
| Jurassic World | 500-1500 | 19 | 10.8 | 6.8 | 9.5 | 5.8 | 16.5 | 9.6 | 7.4 | 6.0 | 164 | 25 |
| Jurassic World | >1500 | 3 | 11.2 | 9.2 | 6.3 | 6.0 | 21.6 | 10.6 | 6.5 | 9.0 | 263 | 24 |
| Dreamzzz | <150 | 21 | 5.7 | 7.3 | 19.9 | 1.4 | 10.4 | 14.2 | 3.2 | 6.6 | 19 | 7 |
| Dreamzzz | 150-500 | 20 | 12.3 | 8.7 | 11.8 | 1.7 | 12.9 | 10.5 | 3.5 | 8.3 | 94 | 19 |
| Dreamzzz | 500-1500 | 15 | 9.7 | 11.2 | 10.2 | 2.8 | 14.2 | 9.6 | 5.0 | 7.4 | 186 | 27 |
| Dreamzzz | >1500 | 2 | (too few) |||||||||| 
| Monkie Kid | <150 | 6 | 2.0 | 5.2 | 19.1 | 7.0 | 16.4 | 7.5 | 5.7 | 3.0 | 20 | 11 |
| Monkie Kid | 150-500 | 11 | 14.3 | 7.1 | 13.5 | 2.1 | 12.2 | 7.8 | 7.0 | 6.4 | 95 | 19 |
| Monkie Kid | 500-1500 | 30 | 15.0 | 9.2 | 11.0 | 2.4 | 12.7 | 8.9 | 5.8 | 6.4 | 185 | 24 |
| Monkie Kid | >1500 | 10 | 10.0 | 6.7 | 9.5 | 6.3 | 14.3 | 10.6 | 5.8 | 8.0 | 298 | 35 |
| Other themes | <150 | 641 | 5.8 | 4.9 | 11.2 | 6.2 | 13.0 | 12.8 | 6.5 | 5.0 | 23 | 9 |
| Other themes | 150-500 | 445 | 5.5 | 5.4 | 8.8 | 6.0 | 16.7 | 12.5 | 6.5 | 6.6 | 71 | 19 |
| Other themes | 500-1500 | 213 | 8.4 | 6.7 | 7.1 | 7.9 | 19.5 | 12.7 | 6.0 | 6.3 | 152 | 24 |
| Other themes | >1500 | 35 | 7.3 | 7.1 | 6.0 | 7.1 | 22.3 | 16.0 | 4.5 | 6.0 | 212 | 31 |

**What to take from A1-A3.** Plates are the backbone everywhere except Technic (13-33 % of build parts);
the theme decides the rest. Sideways-building parts are highest in BrickHeadz (16 %) and Speed Champions
(11 %), about 6-8 % in most display and play themes, and 3-4 % in City and Friends. Botanicals stand
apart: 17 % pin/beam (axles and connectors as stems), 9 % clips, 7 % bars, 16 % plant elements, and few
plain bricks or plates. Architecture is plates and tiles (27 % and 23 %). Minecraft and Classic are
bricks (21 % and 30 %). Joint parts fall with size, from about 11-21 % of small play sets to 4-8 % of
large ones. Variety climbs steadily with size, colours more slowly than parts.

## Part A: the owner's question, pin-and-beam parts against set size

### P1. All themes except Technic: pin-and-beam parts by set size

pb = all pin/beam parts (Technic beams, pins, axles, connectors, bushes, Technic bricks and plates); beam = liftarm beams only; "frame" = set has at least 10 liftarm beams.

| parts | sets | pb median % | pb mean % | beams median % | pins median % | axles+connectors median % | Technic bricks/plates median % | sets with pb >= 10 % | sets with a frame (>= 10 liftarms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0-100 | 1909 | 0.0 | 4.5 | 0.0 | 0.0 | 0.0 | 0.0 | 16 % | 0 % |
| 100-200 | 859 | 1.9 | 6.0 | 0.0 | 0.0 | 0.0 | 0.0 | 16 % | 3 % |
| 200-350 | 1000 | 2.5 | 5.7 | 0.0 | 0.9 | 0.4 | 0.8 | 19 % | 2 % |
| 350-500 | 491 | 5.2 | 7.8 | 0.0 | 1.7 | 1.1 | 1.4 | 29 % | 6 % |
| 500-750 | 555 | 5.5 | 8.7 | 0.1 | 1.7 | 1.6 | 1.4 | 32 % | 17 % |
| 750-1000 | 323 | 7.0 | 8.9 | 0.2 | 2.0 | 1.7 | 2.0 | 33 % | 22 % |
| 1000-1500 | 294 | 7.8 | 9.7 | 0.4 | 2.1 | 2.3 | 2.2 | 39 % | 32 % |
| 1500-2500 | 165 | 5.3 | 7.8 | 0.3 | 1.6 | 1.5 | 1.4 | 33 % | 43 % |
| 2500+ | 115 | 4.5 | 6.6 | 0.1 | 1.4 | 1.2 | 1.2 | 23 % | 42 % |

### P2. By theme group: median pin/beam share (%) and share of sets with a liftarm frame (>= 10 liftarms), by size

Cells: median pb % / % of sets with >= 10 liftarms (number of sets). Empty = fewer than 3 sets.

| group | 0-100 | 100-200 | 200-350 | 350-500 | 500-750 | 750-1000 | 1000-1500 | 1500-2500 | 2500+ |
|---|---|---|---|---|---|---|---|---|---|
| Speed Champions | 0 / 0% (8) | 3 / 0% (17) | 2 / 0% (48) | 6 / 0% (10) | 4 / 7% (15) | 8 / 0% (4) |  |  |  |
| Creator 3-in-1 | 0 / 0% (19) | 6 / 0% (32) | 7 / 0% (55) | 3 / 0% (31) | 4 / 4% (25) | 5 / 8% (12) | 7 / 14% (7) |  |  |
| Adult display (Icons/Creator Expert/UCS/Modular) |  |  | 4 / 0% (12) |  | 8 / 50% (4) | 8 / 45% (11) | 11 / 37% (27) | 10 / 66% (38) | 5 / 47% (47) |
| Botanicals | 0 / 0% (9) | 17 / 0% (6) | 8 / 0% (11) | 22 / 14% (7) | 15 / 25% (8) | 17 / 10% (10) |  |  |  |
| Architecture |  |  | 5 / 0% (5) | 2 / 0% (6) | 2 / 18% (11) | 0 / 0% (4) | 1 / 0% (5) | 0 / 0% (5) | 1 / 0% (4) |
| BrickHeadz | 0 / 0% (13) | 0 / 0% (90) | 0 / 0% (71) | 0 / 0% (5) | 0 / 0% (17) |  |  |  |  |
| Ideas |  | 1 / 0% (9) | 2 / 0% (14) |  | 8 / 30% (10) | 9 / 42% (12) | 5 / 15% (20) | 5 / 39% (18) | 4 / 42% (12) |
| City | 0 / 0% (241) | 2 / 0% (76) | 3 / 0% (96) | 5 / 2% (46) | 6 / 12% (41) | 7 / 5% (43) | 8 / 28% (18) | 3 / 0% (5) |  |
| Friends | 0 / 0% (259) | 1 / 0% (63) | 1 / 0% (77) | 2 / 0% (51) | 3 / 2% (42) | 4 / 8% (25) | 5 / 12% (24) | 3 / 17% (6) |  |
| Star Wars (play) | 0 / 1% (197) | 6 / 12% (82) | 7 / 6% (67) | 11 / 22% (40) | 12 / 36% (73) | 16 / 48% (33) | 15 / 65% (37) | 13 / 62% (8) |  |
| Ninjago | 0 / 0% (145) | 6 / 8% (36) | 12 / 4% (50) | 12 / 16% (31) | 16 / 33% (43) | 18 / 55% (22) | 13 / 52% (31) | 12 / 60% (10) | 7 / 43% (7) |
| Super Heroes | 0 / 0% (142) | 4 / 2% (64) | 7 / 4% (81) | 8 / 4% (75) | 6 / 20% (41) | 8 / 25% (16) | 9 / 31% (13) | 11 / 57% (7) | 5 / 40% (15) |
| Harry Potter | 0 / 0% (23) | 5 / 0% (16) | 3 / 0% (25) | 2 / 0% (13) | 7 / 14% (22) | 3 / 5% (21) | 3 / 0% (6) | 2 / 0% (7) | 2 / 22% (9) |
| Minecraft | 0 / 0% (50) | 3 / 0% (13) | 2 / 0% (42) | 4 / 0% (22) | 2 / 3% (30) | 4 / 12% (8) | 1 / 0% (3) |  |  |
| Disney | 0 / 0% (61) | 1 / 0% (54) | 1 / 0% (34) | 1 / 0% (21) | 2 / 0% (36) | 2 / 29% (7) | 3 / 20% (5) | 6 / 38% (8) | 2 / 0% (5) |
| Creator (other) | 0 / 0% (55) | 0 / 0% (10) | 0 / 0% (12) |  |  |  |  |  |  |
| Classic | 0 / 0% (9) | 0 / 0% (5) | 0 / 0% (12) | 0 / 0% (8) | 1 / 0% (9) | 0 / 0% (11) | 0 / 0% (4) | 0 / 0% (9) |  |
| Super Mario | 0 / 0% (71) | 7 / 0% (17) | 5 / 5% (20) | 8 / 13% (15) | 8 / 17% (12) | 9 / 50% (4) | 12 / 45% (11) | 12 / 100% (3) |  |
| Jurassic World | 0 / 0% (64) | 2 / 0% (15) | 5 / 0% (14) | 7 / 0% (11) | 12 / 18% (11) | 6 / 0% (4) | 7 / 25% (4) |  |  |
| Dreamzzz | 0 / 0% (19) | 0 / 0% (3) | 14 / 0% (8) | 12 / 0% (11) | 6 / 0% (3) | 9 / 25% (4) | 8 / 12% (8) |  |  |
| Monkie Kid | 0 / 0% (6) |  | 12 / 0% (6) | 20 / 50% (4) | 14 / 20% (10) | 11 / 27% (11) | 19 / 67% (9) | 10 / 60% (10) |  |
| Other themes | 0 / 1% (516) | 1 / 4% (249) | 1 / 3% (240) | 5 / 9% (81) | 7 / 21% (92) | 6 / 21% (61) | 4 / 25% (60) | 3 / 38% (26) | 6 / 56% (9) |

### P2b. What the pin/beam parts are, by group (sets of 500 parts and more): medians and means, % of build parts

| group | sets | beams (liftarms) median / mean | pins median / mean | axles+connectors+bushes median / mean | Technic bricks/plates median / mean |
|---|---:|---:|---:|---:|---:|
| Technic | 123 | 17.6 / 17.8 | 35.9 / 35.5 | 28.3 / 28.3 | 0.2 / 0.3 |
| Speed Champions | 19 | 0.0 / 0.3 | 1.8 / 2.3 | 1.5 / 1.7 | 1.5 / 1.5 |
| Creator 3-in-1 | 45 | 0.0 / 0.4 | 1.0 / 1.9 | 1.1 / 1.8 | 1.6 / 2.1 |
| Adult display (Icons/Creator Expert/UCS/Modular) | 127 | 0.5 / 0.9 | 2.7 / 3.6 | 2.5 / 3.2 | 1.8 / 2.0 |
| Botanicals | 20 | 0.0 / 0.5 | 1.3 / 3.4 | 10.7 / 12.7 | 0.4 / 1.7 |
| Architecture | 29 | 0.0 / 0.7 | 0.0 / 0.3 | 0.1 / 0.7 | 0.2 / 0.6 |
| BrickHeadz | 17 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |
| Ideas | 72 | 0.1 / 0.7 | 1.5 / 2.0 | 1.7 / 3.0 | 1.2 / 2.0 |
| City | 107 | 0.2 / 0.5 | 2.0 / 2.6 | 1.9 / 2.4 | 1.6 / 2.0 |
| Friends | 97 | 0.0 / 0.2 | 1.1 / 1.6 | 0.7 / 1.5 | 0.8 / 1.2 |
| Star Wars (play) | 153 | 1.1 / 1.6 | 4.9 / 5.7 | 2.5 / 3.6 | 2.9 / 3.0 |
| Ninjago | 113 | 0.9 / 1.2 | 3.9 / 4.7 | 5.2 / 5.5 | 3.9 / 3.7 |
| Super Heroes | 92 | 0.4 / 0.8 | 2.4 / 3.7 | 1.3 / 2.0 | 2.5 / 2.6 |
| Harry Potter | 65 | 0.0 / 0.3 | 1.1 / 1.7 | 0.5 / 1.7 | 1.4 / 1.7 |
| Minecraft | 43 | 0.0 / 0.2 | 0.4 / 1.0 | 0.4 / 0.7 | 0.7 / 1.3 |
| Disney | 61 | 0.0 / 0.2 | 0.7 / 1.1 | 0.5 / 1.5 | 0.7 / 1.2 |
| Classic | 33 | 0.0 / 0.1 | 0.0 / 0.2 | 0.0 / 0.4 | 0.0 / 0.4 |
| Super Mario | 32 | 0.9 / 1.1 | 3.2 / 3.4 | 2.8 / 3.0 | 2.5 / 2.5 |
| Jurassic World | 22 | 0.3 / 0.8 | 2.5 / 3.9 | 2.7 / 3.8 | 2.2 / 2.4 |
| Dreamzzz | 17 | 0.3 / 0.4 | 3.0 / 2.8 | 2.5 / 3.0 | 2.6 / 3.1 |
| Monkie Kid | 40 | 0.8 / 1.0 | 4.4 / 4.9 | 3.8 / 4.5 | 3.3 / 3.3 |
| Other themes | 248 | 0.2 / 0.7 | 1.6 / 2.9 | 1.7 / 2.7 | 1.5 / 1.9 |

### P3. Typical sets on each side of the change (median-ish examples)

For each group: three sets of 150-400 parts closest to the group median pb share in that band, and three of 700-2000 parts. Shows set number, name, year, parts, pb %, liftarms.

- **City**: 150-400 (median 3 %, 158 sets): 60182-1 Pickup & Caravan (2018, 344 parts, 3 %, 2 liftarms); 60500-1 The LEGO Van (2026, 276 parts, 3 %, 0 liftarms); 60355-1 Water Police Detective Missions (2022, 278 parts, 3 %, 0 liftarms) / 700-2000 (median 7 %, 74 sets): 60509-1 Harbor Freight Train with Crane & Truck (2026, 803 parts, 7 %, 7 liftarms); 60501-1 Lava Land Roller Coaster Park (2026, 1165 parts, 7 %, 0 liftarms); 60198-1 Cargo Train (2018, 1226 parts, 7 %, 9 liftarms)
- **Friends**: 150-400 (median 1 %, 130 sets): 40156-1 Organizer (2015, 171 parts, 1 %, 0 liftarms); 40694-1 River Camping Adventure (2024, 182 parts, 1 %, 0 liftarms); 41443-1 Olivia's Electric Car (2021, 183 parts, 1 %, 0 liftarms) / 700-2000 (median 4 %, 60 sets): 41748-1 Heartlake City Community Center (2023, 1513 parts, 4 %, 2 liftarms); 41757-1 Botanical Garden (2023, 1072 parts, 4 %, 0 liftarms); 41430-1 Summer Fun Water Park (2020, 1012 parts, 4 %, 0 liftarms)
- **Speed Champions**: 150-400 (median 3 %, 70 sets): 75872-1 Audi R18 e-tron quattro (2016, 169 parts, 2 %, 0 liftarms); 75880-1 McLaren 720S (2017, 168 parts, 3 %, 0 liftarms); 75887-1 Porsche 919 Hybrid (2018, 170 parts, 2 %, 0 liftarms) / 700-2000 (median 8 %, 6 sets): 75889-1 Ferrari Ultimate Garage (2018, 856 parts, 7 %, 6 liftarms); 75913-1 F14 T & Scuderia Ferrari Truck (2015, 892 parts, 10 %, 1 liftarms); 75876-1 Porsche 919 Hybrid and 917K Pit Lane (2016, 743 parts, 11 %, 8 liftarms)
- **Creator 3-in-1**: 150-400 (median 6 %, 86 sets): 31147-1 Retro Camera (2024, 261 parts, 5 %, 1 liftarms); 31379-1 Fierce Dinosaur (2026, 283 parts, 6 %, 0 liftarms); 31076-1 Daredevil Stunt Plane (2018, 200 parts, 5 %, 0 liftarms) / 700-2000 (median 5 %, 23 sets): 31386-1 Wild Animals: Majestic Lion (2026, 839 parts, 5 %, 1 liftarms); 31084-1 Pirate Roller Coaster (2018, 923 parts, 5 %, 1 liftarms); 31153-1 Modern House (2024, 939 parts, 5 %, 0 liftarms)
- **Star Wars (play)**: 150-400 (median 7 %, 113 sets): 75090-2 Ezra's Speeder Bike [Original Version] (2015, 253 parts, 7 %, 4 liftarms); 75319-1 The Armorer's Mandalorian Forge (2021, 258 parts, 7 %, 2 liftarms); 75437-1 Cobb Vanth's Speeder (2026, 207 parts, 7 %, 0 liftarms) / 700-2000 (median 13 %, 89 sets): 75103-1 First Order Transporter (2015, 792 parts, 13 %, 16 liftarms); 75244-1 Tantive IV (2019, 1768 parts, 13 %, 23 liftarms); 75389-1 The Dark Falcon (2024, 1579 parts, 13 %, 7 liftarms)
- **Ninjago**: 150-400 (median 11 %, 85 sets): 71864-1 Kai and Cole's Combiner Vehicles (2026, 394 parts, 11 %, 6 liftarms); 70602-1 Jay's Elemental Dragon (2016, 350 parts, 10 %, 0 liftarms); 71806-1 Cole's Earth Mech (2024, 235 parts, 10 %, 0 liftarms) / 700-2000 (median 16 %, 67 sets): 71786-1 Zane's Ice Dragon Creature (2023, 984 parts, 16 %, 8 liftarms); 71860-1 Lloyd's Titan Mech 15th Anniversary (2026, 1293 parts, 16 %, 16 liftarms); 71712-1 Empire Temple of Madness (2020, 820 parts, 16 %, 6 liftarms)
- **Super Heroes**: 150-400 (median 7 %, 143 sets): 76289-1 Thor vs. Surtur Construction Figure (2024, 245 parts, 7 %, 0 liftarms); 76201-1 Captain Carter & The Hydra Stomper (2021, 343 parts, 7 %, 0 liftarms); 76083-1 Beware the Vulture (2017, 376 parts, 6 %, 1 liftarms) / 700-2000 (median 8 %, 39 sets): 76314-1 Captain America: Civil War Battle (2025, 736 parts, 8 %, 2 liftarms); 76209-1 Thor's Hammer (2022, 979 parts, 8 %, 0 liftarms); 76156-1 Rise of the Domo (2021, 1049 parts, 8 %, 6 liftarms)
- **Harry Potter**: 150-400 (median 3 %, 41 sets): 75965-1 The Rise of Voldemort (2019, 185 parts, 3 %, 0 liftarms); 76442-1 Hogwarts Castle: Charms Class (2025, 203 parts, 3 %, 0 liftarms); 40598-1 Gringotts Vault (2023, 215 parts, 3 %, 0 liftarms) / 700-2000 (median 3 %, 34 sets): 75954-1 Hogwarts Great Hall (2018, 882 parts, 3 %, 1 liftarms); 76471-1 Knockturn Alley Wizarding Shops (2026, 788 parts, 3 %, 0 liftarms); 75969-1 Hogwarts Astronomy Tower (2020, 971 parts, 3 %, 0 liftarms)
- **Ideas**: 150-400 (median 1 %, 23 sets): 40595-1 Tribute to Galileo Galilei (2023, 307 parts, 1 %, 0 liftarms); 40773-1 The Goonies: The Walshes' Attic (2025, 179 parts, 1 %, 0 liftarms); 40533-1 Cosmic Cardboard Adventures (2022, 203 parts, 1 %, 0 liftarms) / 700-2000 (median 5 %, 39 sets): 21349-1 Tuxedo Cat (2024, 1710 parts, 5 %, 2 liftarms); 21376-1 Orange Cat (2026, 1755 parts, 5 %, 2 liftarms); 21369-1 The X-Files (2026, 1478 parts, 5 %, 0 liftarms)
- **Adult display (Icons/Creator Expert/UCS/Modular)**: 150-400 (median 3 %, 13 sets): 40729-1 Shackleton's Lifeboat (2024, 232 parts, 3 %, 0 liftarms); 40913-1 Vintage Parade Car (2026, 243 parts, 5 %, 0 liftarms); 40681-1 Retro Food Truck (2024, 310 parts, 0 %, 0 liftarms) / 700-2000 (median 10 %, 63 sets): 10266-1 NASA Apollo 11 Lunar Lander (2019, 1087 parts, 10 %, 0 liftarms); 75442-1 The Mandalorian's N-1 Starfighter (2026, 1809 parts, 10 %, 14 liftarms); 10295-1 Porsche 911 Turbo & 911 Targa (2021, 1458 parts, 11 %, 15 liftarms)
- **Botanicals**: 150-400 (median 12 %, 17 sets): 10343-1 Mini Orchid (2025, 274 parts, 12 %, 2 liftarms); 10368-1 Chrysanthemum (2024, 278 parts, 12 %, 3 liftarms); 11514-1 Cosmos Flowers (2026, 171 parts, 13 %, 2 liftarms) / 700-2000 (median 17 %, 14 sets): 11503-1 Flower Wall (2026, 879 parts, 20 %, 14 liftarms); 10309-1 Succulents (2022, 771 parts, 15 %, 0 liftarms); 10280-1 Flower Bouquet (2021, 756 parts, 22 %, 0 liftarms)
- **Architecture**: 150-400 (median 4 %, 7 sets): 21036-1 Arc de Triomphe (2017, 386 parts, 4 %, 0 liftarms); 21027-1 Berlin (2016, 289 parts, 5 %, 0 liftarms); 21032-1 Sydney (2017, 361 parts, 2 %, 0 liftarms) / 700-2000 (median 0 %, 14 sets): 21042-1 Statue of Liberty (2018, 1685 parts, 0 %, 0 liftarms); 21054-1 The White House (2020, 1483 parts, 0 %, 0 liftarms); 21058-1 Great Pyramid of Giza (2022, 1476 parts, 0 %, 0 liftarms)
- **BrickHeadz**: 150-400 (median 0 %, 102 sets): 41588-1 The Joker (2017, 151 parts, 0 %, 0 liftarms); 41492-1 Iron Man & Captain America (2016, 174 parts, 0 %, 0 liftarms); 41493-1 Black Panther & Dr. Strange (2016, 167 parts, 0 %, 0 liftarms) / 700-2000 (median 0 %, 2 sets): 41597-1 Go Brick Me (2018, 708 parts, 0 %, 0 liftarms); 40676-1 The Phantom Menace (2024, 732 parts, 1 %, 0 liftarms)
- **Disney**: 150-400 (median 1 %, 70 sets): 41063-1 Ariel's Undersea Palace (2015, 379 parts, 1 %, 0 liftarms); 41153-1 Ariel's Royal Celebration Boat (2018, 380 parts, 1 %, 0 liftarms); 43185-1 Boun's Boat (2021, 247 parts, 1 %, 0 liftarms) / 700-2000 (median 3 %, 23 sets): 43249-1 Stitch (2024, 730 parts, 3 %, 1 liftarms); 43300-1 Winnie the Pooh (2026, 1399 parts, 3 %, 1 liftarms); 43215-1 The Enchanted Treehouse (2023, 1016 parts, 3 %, 0 liftarms)

### P4. Non-Technic sets over 500 parts with the highest pin/beam share (top 15) and the lowest (bottom 10 among sets over 1,500 parts)

- 4002017-1 Nutcracker (Other themes, 2017, 732 parts): pb 59 %, 57 liftarms
- 75219-1 Imperial AT-Hauler (Star Wars (play), 2018, 829 parts): pb 47 %, 67 liftarms
- 10311-1 Orchid (Botanicals, 2022, 608 parts): pb 46 %, 29 liftarms
- 75177-1 First Order Heavy Scout Walker (Star Wars (play), 2017, 554 parts): pb 45 %, 62 liftarms
- 10327-1 Dune Atreides Royal Ornithopter (Adult display (Icons/Creator Expert/UCS/Modular), 2024, 1370 parts): pb 44 %, 95 liftarms
- 76086-1 Knightcrawler Tunnel Attack (Super Heroes, 2017, 623 parts): pb 40 %, 40 liftarms
- 11389-1 Project Hail Mary (Adult display (Icons/Creator Expert/UCS/Modular), 2026, 830 parts): pb 40 %, 49 liftarms
- 70227-1 King Crominus' Rescue (Other themes, 2015, 863 parts): pb 40 %, 58 liftarms
- 75191-1 Jedi Starfighter with Hyperdrive (Star Wars (play), 2017, 832 parts): pb 39 %, 32 liftarms
- 21327-1 Typewriter (Ideas, 2021, 2080 parts): pb 39 %, 204 liftarms
- 75234-1 AT-AP Walker (Star Wars (play), 2019, 689 parts): pb 39 %, 49 liftarms
- 21332-1 The Globe (Ideas, 2022, 2585 parts): pb 39 %, 58 liftarms
- 71869-1 Land Bounty (Ninjago, 2026, 1215 parts): pb 38 %, 67 liftarms
- 10374-1 Bouquet of Pink Roses (Botanicals, 2025, 789 parts): pb 37 %, 0 liftarms
- 71773-1 Kai's Golden Dragon Raider (Ninjago, 2022, 635 parts): pb 37 %, 22 liftarms

- 10654-1 XL Creative Brick Box (Classic, 2016, 1600 parts): pb 0.0 %, 0 liftarms
- 10697-1 XXXL Box (Classic, 2015, 1500 parts): pb 0.0 %, 0 liftarms
- 11011-1 Bricks and Animals (Classic, 2020, 1500 parts): pb 0.0 %, 0 liftarms
- 11022-1 Space Mission (Classic, 2022, 1700 parts): pb 0.0 %, 0 liftarms
- 11717-1 Bricks Bricks Plates (Classic, 2020, 1504 parts): pb 0.1 %, 0 liftarms
- 10717-1 Bricks Bricks Bricks (Classic, 2018, 1500 parts): pb 0.1 %, 0 liftarms
- 21046-1 Empire State Building (Architecture, 2019, 1767 parts): pb 0.2 %, 0 liftarms
- 21060-1 Himeji Castle (Architecture, 2023, 2125 parts): pb 0.2 %, 0 liftarms
- 10278-1 Police Station (Adult display (Icons/Creator Expert/UCS/Modular), 2021, 2923 parts): pb 0.2 %, 0 liftarms
- 11032-1 Creative Color Fun (Classic, 2023, 1500 parts): pb 0.3 %, 0 liftarms

### P5. Pin/beam share over time, sets of 500+ parts outside Technic

| year | sets | pb median % | sets with >= 10 liftarms |
|---|---:|---:|---:|
| 2015 | 74 | 9.7 | 36 % |
| 2016 | 77 | 8.1 | 36 % |
| 2017 | 83 | 11.7 | 45 % |
| 2018 | 80 | 8.8 | 34 % |
| 2019 | 87 | 7.3 | 30 % |
| 2020 | 94 | 6.9 | 27 % |
| 2021 | 111 | 5.6 | 24 % |
| 2022 | 137 | 5.6 | 26 % |
| 2023 | 147 | 5.2 | 18 % |
| 2024 | 168 | 5.7 | 19 % |
| 2025 | 181 | 5.1 | 24 % |
| 2026 | 213 | 5.5 | 21 % |

**Reading the curve.** Under 350 parts, pin/beam parts in non-Technic sets are mostly single Technic
bricks, pins and axles used to hold wheels, guns and joints, not frames (median liftarm share 0). From
350-500 parts the pins-and-axles share climbs, and from **500 parts** liftarm frames appear in a sizeable
minority of sets: about a sixth at 500-750 parts, a third at 1,000-1,500, over two fifths above 1,500.
Theme matters more than size: at 750-1,000 parts about half of Star Wars and Ninjago sets have a frame,
a twentieth of City sets, none of Architecture. The very largest sets (2,500+) have a *lower* pin/beam
share because they are buildings and display pieces with a great deal of plain surface; but 42 % of
them still contain a frame of at least 10 liftarms somewhere. The share has also fallen over time:
sets of 500+ parts had a median of 8-12 % pin/beam in 2015-17 and about 5 % since 2021, and the share
with 10+ liftarms fell from 36-45 % to about 20 % (P5).

## Part A: the most-used parts for each job

Counted as the number of sets that use the part at least once, in any colour, prints folded into the
plain part. Rebrickable numbers are given as they appear in Rebrickable's parts table (checked there).


### C. The twenty commonest sideways-building parts (brackets, bricks and plates with side studs), all groups except Technic (by number of sets using the part, any colour, prints folded into the plain part)

Sets: 5711

| rank | part (Rebrickable number) | name | job | sets | % of sets |
|---:|---|---|---|---:|---:|
| 1 | 99780 | Bracket 1 x 2 - 1 x 2 Inverted | sideways | 2126 | 37 |
| 2 | 11211 | Brick Special 1 x 2 with 2 Studs on 1 Side | sideways | 1983 | 35 |
| 3 | 99207 | Bracket 1 x 2 - 2 x 2 Inverted | sideways | 1874 | 33 |
| 4 | 87087 | Brick Special 1 x 1 with Stud on 1 Side | sideways | 1873 | 33 |
| 5 | 99781 | Bracket 1 x 2 - 1 x 2 | sideways | 1656 | 29 |
| 6 | 44728 | Bracket 1 x 2 - 2 x 2 | sideways | 1648 | 29 |
| 7 | 4070 | Brick Special 1 x 1 with Headlight | sideways | 1418 | 25 |
| 8 | 22885 | Brick Special 1 x 2 x 1 2/3 with 4 Studs on 1 Side | sideways | 1298 | 23 |
| 9 | 30414 | Brick Special 1 x 4 with 4 Studs on One Side | sideways | 1263 | 22 |
| 10 | 36840 | Bracket 1 x 1 - 1 x 1 Inverted | sideways | 1071 | 19 |
| 11 | 32952 | Brick Special 1 x 1 x 1 2/3 with Studs on 1 Side | sideways | 1039 | 18 |
| 12 | 99206 | Plate Special 2 x 2 x 2/3 with Two Studs On Side and Two Raised [Solid Anti-stud] | sideways | 980 | 17 |
| 13 | 36841 | Bracket 1 x 1 - 1 x 1 | sideways | 890 | 16 |
| 14 | 73825 | Bracket 1 x 1 - 1 x 2 Inverted | sideways | 733 | 13 |
| 15 | 93274 | Bracket 1 x 2 - 2 x 4 | sideways | 681 | 12 |
| 16 | 4733 | Brick Special 1 x 1 Studs on 4 Sides | sideways | 664 | 12 |
| 17 | 41682 | Bracket 2 x 2 with 1 x 2 Vertical Studs | sideways | 662 | 12 |
| 18 | 28802 | Bracket 1 x 2 - 1 x 4 [Rounded Corners at Bottom, Square Corners at Top] | sideways | 659 | 12 |
| 19 | 4304 | Plate Special 2 x 2 x 2/3 with Two Studs On Side and Two Raised [Half Hollow Anti-stud] - Updated Version | sideways | 659 | 12 |
| 20 | 26604 | Brick Special 1 x 1 with Studs on 2 Adjacent Sides | sideways | 596 | 10 |

By theme group, top 8 (number of sets using it / sets in the group):

- **Technic** (224 sets): Bracket 1 x 2 - 1 x 2 Inverted [99780] 14; Bracket 1 x 2 - 2 x 2 [44728] 11; Bracket 1 x 1 - 1 x 1 Inverted [36840] 9; Brick Special 1 x 1 with Stud on 1 Side [87087] 7; Bracket 1 x 2 - 2 x 2 Inverted [99207] 7; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 5; Bracket 1 x 1 - 1 x 1 [36841] 5; Bracket 1 x 1 - 1 x 2 Inverted [73825] 5
- **Speed Champions** (102 sets): Bracket 1 x 2 - 1 x 2 Inverted [99780] 87; Bracket 1 x 2 - 2 x 2 Inverted [99207] 73; Bracket 1 x 2 - 1 x 2 [99781] 62; Bracket 1 x 1 - 1 x 1 [36841] 61; Bracket 1 x 1 - 1 x 1 Inverted [36840] 60; Brick Special 1 x 1 with Headlight [4070] 54; Bracket 1 x 1 - 1 x 2 Inverted [73825] 49; Brick Special 1 x 1 with Stud on 1 Side [87087] 45
- **Creator 3-in-1** (182 sets): Bracket 1 x 2 - 1 x 2 Inverted [99780] 94; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 84; Bracket 1 x 2 - 2 x 2 Inverted [99207] 77; Brick Special 1 x 1 with Stud on 1 Side [87087] 77; Bracket 1 x 2 - 1 x 2 [99781] 73; Bracket 1 x 2 - 2 x 2 [44728] 67; Brick Special 1 x 1 with Headlight [4070] 57; Bracket 1 x 1 - 1 x 1 Inverted [36840] 51
- **Adult display (Icons/Creator Expert/UCS/Modular)** (142 sets): Bracket 1 x 2 - 2 x 2 Inverted [99207] 115; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 113; Bracket 1 x 2 - 1 x 2 Inverted [99780] 113; Brick Special 1 x 1 with Headlight [4070] 105; Brick Special 1 x 1 with Stud on 1 Side [87087] 104; Brick Special 1 x 4 with 4 Studs on One Side [30414] 101; Bracket 1 x 2 - 1 x 2 [99781] 98; Bracket 1 x 2 - 2 x 2 [44728] 98
- **Botanicals** (53 sets): Brick Special 1 x 1 Studs on 4 Sides [4733] 20; Plate Special 2 x 2 x 2/3 with Two Studs On Side and Two Raised [Half Hollow Anti-stud] - Updated Version [4304] 13; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 10; Bracket 1 x 2 - 2 x 2 Inverted [99207] 8; Brick Special 1 x 4 with 4 Studs on One Side [30414] 6; Brick Special 1 x 1 with Stud on 1 Side [87087] 5; Bracket 2 x 2 with 1 x 2 Vertical Studs [41682] 5; Brick Special 1 x 2 with Studs on 2 Sides [52107] 5
- **Architecture** (40 sets): Brick Special 1 x 1 with Stud on 1 Side [87087] 28; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 28; Brick Special 1 x 1 Studs on 4 Sides [4733] 21; Brick Special 1 x 1 with Headlight [4070] 21; Plate Special 2 x 2 x 2/3 with Two Studs On Side and Two Raised [Solid Anti-stud] [99206] 20; Bracket 1 x 2 - 1 x 2 Inverted [99780] 17; Plate Special 2 x 6 x 2/3 with 4 Studs on Side, 1 Support Wall on Bottom [87609] 16; Brick Special 1 x 1 x 1 2/3 with Studs on 1 Side [32952] 15
- **BrickHeadz** (196 sets): Brick Special 1 x 2 x 1 2/3 with 4 Studs on 1 Side [22885] 195; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 86; Brick Special 1 x 1 x 1 2/3 with Studs on 1 Side [32952] 85; Bracket 1 x 2 - 1 x 2 Inverted [99780] 78; Plate Special 2 x 2 x 2/3 with Two Studs On Side and Two Raised [Solid Anti-stud] [99206] 69; Brick Special 1 x 1 with Stud on 1 Side [87087] 69; Brick Special 1 x 1 with Headlight [4070] 60; Brick Special 1 x 1 with Studs on 2 Adjacent Sides [26604] 48
- **Ideas** (98 sets): Brick Special 1 x 1 with Headlight [4070] 66; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 66; Bracket 1 x 2 - 1 x 2 Inverted [99780] 63; Brick Special 1 x 1 with Stud on 1 Side [87087] 63; Bracket 1 x 2 - 2 x 2 Inverted [99207] 58; Bracket 1 x 2 - 1 x 2 [99781] 57; Bracket 1 x 1 - 1 x 1 Inverted [36840] 52; Brick Special 1 x 2 x 1 2/3 with 4 Studs on 1 Side [22885] 50
- **City** (566 sets): Bracket 1 x 2 - 1 x 2 Inverted [99780] 178; Brick Special 1 x 4 with 4 Studs on One Side [30414] 168; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 161; Bracket 1 x 2 - 2 x 2 [44728] 141; Bracket 1 x 2 - 2 x 2 Inverted [99207] 134; Brick Special 1 x 1 with Stud on 1 Side [87087] 112; Bracket 1 x 2 - 1 x 2 [99781] 109; Brick Special 1 x 2 x 1 2/3 with 4 Studs on 1 Side [22885] 92
- **Friends** (547 sets): Brick Special 1 x 1 with Stud on 1 Side [87087] 179; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 164; Bracket 1 x 2 - 1 x 2 Inverted [99780] 118; Bracket 1 x 2 - 2 x 2 Inverted [99207] 110; Brick Special 1 x 4 with 4 Studs on One Side [30414] 103; Brick Special 1 x 2 x 1 2/3 with 4 Studs on 1 Side [22885] 95; Brick Special 1 x 1 with Headlight [4070] 93; Bracket 1 x 2 - 2 x 2 [44728] 84
- **Star Wars (play)** (539 sets): Bracket 1 x 2 - 1 x 2 Inverted [99780] 225; Bracket 1 x 2 - 2 x 2 Inverted [99207] 210; Bracket 1 x 2 - 1 x 2 [99781] 208; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 196; Brick Special 1 x 1 with Stud on 1 Side [87087] 162; Bracket 1 x 2 - 2 x 2 [44728] 159; Brick Special 1 x 1 with Headlight [4070] 131; Brick Special 1 x 4 with 4 Studs on One Side [30414] 109
- **Ninjago** (375 sets): Bracket 1 x 2 - 1 x 2 Inverted [99780] 190; Bracket 1 x 2 - 2 x 2 Inverted [99207] 153; Bracket 1 x 2 - 1 x 2 [99781] 153; Bracket 1 x 2 - 2 x 2 [44728] 140; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 120; Brick Special 1 x 1 with Stud on 1 Side [87087] 96; Brick Special 1 x 4 with 4 Studs on One Side [30414] 86; Bracket 5 x 2 x 1 1/3 with Holes, Pin Bottom [11215] 75
- **Super Heroes** (454 sets): Bracket 1 x 2 - 1 x 2 Inverted [99780] 216; Bracket 1 x 2 - 1 x 2 [99781] 180; Bracket 1 x 2 - 2 x 2 Inverted [99207] 177; Bracket 1 x 2 - 2 x 2 [44728] 168; Brick Special 1 x 1 with Headlight [4070] 141; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 132; Brick Special 1 x 1 with Stud on 1 Side [87087] 116; Plate Special 2 x 2 x 2/3 with Two Studs On Side and Two Raised [Solid Anti-stud] [99206] 111
- **Harry Potter** (142 sets): Brick Special 1 x 1 with Stud on 1 Side [87087] 74; Brick Special 1 x 1 with Headlight [4070] 69; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 69; Bracket 1 x 2 - 2 x 2 Inverted [99207] 65; Bracket 1 x 2 - 1 x 2 Inverted [99780] 61; Bracket 1 x 2 - 2 x 2 [44728] 58; Bracket 1 x 2 - 1 x 2 [99781] 58; Brick Special 1 x 1 x 1 2/3 with Studs on 1 Side [32952] 56
- **Minecraft** (170 sets): Bracket 1 x 2 - 2 x 2 [44728] 51; Brick Special 1 x 1 with Stud on 1 Side [87087] 44; Bracket 2 x 2 with 1 x 2 Vertical Studs [41682] 40; Bracket 1 x 2 - 1 x 2 Inverted [99780] 38; Brick Special 1 x 1 Studs on 4 Sides [4733] 36; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 35; Bracket 1 x 2 - 2 x 2 Inverted [99207] 30; Brick Special 1 x 1 with Headlight [4070] 25
- **Disney** (231 sets): Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 86; Brick Special 1 x 1 with Stud on 1 Side [87087] 75; Brick Special 1 x 2 x 1 2/3 with 4 Studs on 1 Side [22885] 65; Bracket 1 x 2 - 2 x 2 Inverted [99207] 65; Bracket 1 x 2 - 2 x 2 [44728] 63; Bracket 1 x 2 - 1 x 2 Inverted [99780] 63; Brick Special 1 x 1 x 1 2/3 with Studs on 1 Side [32952] 50; Brick Special 1 x 4 with 4 Studs on One Side [30414] 46
- **Creator (other)** (77 sets): Bracket 1 x 2 - 1 x 2 Inverted [99780] 16; Brick Special 1 x 2 x 1 2/3 with 4 Studs on 1 Side [22885] 16; Bracket 1 x 2 - 2 x 2 Inverted [99207] 15; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 13; Brick Special 1 x 1 with Headlight [4070] 13; Bracket 1 x 2 - 2 x 2 [44728] 12; Brick Special 1 x 1 with Stud on 1 Side [87087] 11; Brick Special 1 x 1 x 1 2/3 with Studs on 1 Side [32952] 11
- **Classic** (67 sets): Brick Special 1 x 1 with Stud on 1 Side [87087] 51; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 43; Brick Special 1 x 2 x 1 2/3 with 4 Studs on 1 Side [22885] 23; Brick Special 1 x 1 with Headlight [4070] 22; Brick Special 1 x 4 with 4 Studs on One Side [30414] 21; Bracket 1 x 2 - 2 x 2 [44728] 17; Brick Special 1 x 1 with Studs on 2 Sides [47905] 15; Brick Special 1 x 1 Studs on 4 Sides [4733] 11
- **Super Mario** (155 sets): Brick Special 1 x 2 x 1 2/3 with 8 Studs on 3 Sides [67329] 74; Bracket 1 x 2 - 2 x 2 Inverted [99207] 67; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 67; Brick Special 1 x 1 with Stud on 1 Side [87087] 59; Brick Special 1 x 1 x 1 2/3 with Studs on 1 Side [32952] 56; Bracket 1 x 2 - 1 x 2 [99781] 54; Brick Special 1 x 2 x 1 2/3 with 4 Studs on 1 Side [22885] 48; Bracket 1 x 2 - 1 x 2 Inverted [99780] 48
- **Jurassic World** (126 sets): Bracket 1 x 2 - 1 x 2 Inverted [99780] 40; Bracket 1 x 2 - 2 x 2 Inverted [99207] 35; Bracket 1 x 2 - 2 x 2 [44728] 31; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 29; Brick Special 1 x 1 with Stud on 1 Side [87087] 27; Bracket 1 x 2 - 1 x 2 [99781] 25; Bracket 1 x 1 - 1 x 1 Inverted [36840] 25; Brick Special 1 x 4 with 4 Studs on One Side [30414] 23
- **Dreamzzz** (58 sets): Bracket 1 x 2 - 1 x 2 [99781] 38; Bracket 1 x 2 - 2 x 2 Inverted [99207] 29; Bracket 1 x 2 - 2 x 2 [44728] 27; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 27; Bracket 1 x 2 - 1 x 2 Inverted [99780] 26; Bracket 1 x 1 - 1 x 2 Inverted [73825] 25; Bracket 1 x 1 - 1 x 1 [36841] 24; Brick Special 1 x 1 with Stud on 1 Side [87087] 22
- **Monkie Kid** (57 sets): Bracket 1 x 2 - 1 x 2 Inverted [99780] 48; Bracket 1 x 2 - 2 x 2 Inverted [99207] 43; Bracket 1 x 2 - 1 x 2 [99781] 42; Bracket 1 x 2 - 2 x 2 [44728] 41; Bracket 1 x 1 - 1 x 1 Inverted [36840] 34; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 33; Plate Special 2 x 2 x 2/3 with Two Studs On Side and Two Raised [Solid Anti-stud] [99206] 26; Bracket 1 x 2 - 2 x 4 [93274] 25
- **Other themes** (1334 sets): Brick Special 1 x 1 with Stud on 1 Side [87087] 430; Bracket 1 x 2 - 1 x 2 Inverted [99780] 399; Brick Special 1 x 2 with 2 Studs on 1 Side [11211] 377; Bracket 1 x 2 - 2 x 2 Inverted [99207] 372; Bracket 1 x 2 - 2 x 2 [44728] 331; Bracket 1 x 2 - 1 x 2 [99781] 302; Brick Special 1 x 1 with Headlight [4070] 278; Brick Special 1 x 2 x 1 2/3 with 4 Studs on 1 Side [22885] 234

### C. The twenty commonest hinge and joint parts (hinges, turntables, clips, bars, ball and towball joints), all groups except Technic (by number of sets using the part, any colour, prints folded into the plain part)

Sets: 5711

| rank | part (Rebrickable number) | name | job | sets | % of sets |
|---:|---|---|---|---:|---:|
| 1 | 15712 | Tile Special 1 x 1 with Clip with Rounded Edges | clip | 2145 | 38 |
| 2 | 48336 | Plate Special 1 x 2 [Side Handle Closed Ends] | bar | 1677 | 29 |
| 3 | 20482 | Tile Special Round 1 x 1 with Hollow Bar | bar | 1602 | 28 |
| 4 | 60897 | Plate Special 1 x 1 with Clip Vertical [Thick Open O Clip] | clip | 1593 | 28 |
| 5 | 60478 | Plate Special 1 x 2 with Handle on End [Closed Ends] | bar | 1557 | 27 |
| 6 | 11476 | Plate Special 1 x 2 with Clip Horizontal on Side | clip | 1469 | 26 |
| 7 | 60470b | Plate Special 1 x 2 with Clips Horizontal [Open O Clips] | clip | 1361 | 24 |
| 8 | 63868 | Plate Special 1 x 2 with Clip Horizontal on End | clip | 1346 | 24 |
| 9 | 30374 | Bar 4L (Lightsaber Blade / Wand) | bar | 1300 | 23 |
| 10 | 61252 | Plate Special 1 x 1 with Clip Horizontal [Thick Open O Clip] | clip | 1295 | 23 |
| 11 | 2540 | Plate Special 1 x 2 Side Handle [Free Ends] | bar | 1209 | 21 |
| 12 | 87994 | Bar 3L | bar | 1122 | 20 |
| 13 | 26047 | Plate Special 1 x 1 Rounded with Handle | bar | 1080 | 19 |
| 14 | 3937 | Hinge Brick 1 x 2 Base | hinge | 1036 | 18 |
| 15 | 32828 | Plate Special Round 1 x 1 with Hollow Stud and Horizontal Bar 1L | bar | 1032 | 18 |
| 16 | 63965 | Bar 6L with Stop Ring | bar | 994 | 17 |
| 17 | 2432 | Tile Special 1 x 2 with Handle | bar | 965 | 17 |
| 18 | 44861 | Plate Special 1 x 2, Top Clip [Open O] | clip | 937 | 16 |
| 19 | 11090 | Bar Holder with Clip | clip | 896 | 16 |
| 20 | 6134 | Hinge Brick 2 x 2 Top Plate Thin | hinge | 883 | 15 |

By theme group, top 8 (number of sets using it / sets in the group):

- **Technic** (224 sets): Bar 3L [87994] 56; Bar 4L (Lightsaber Blade / Wand) [30374] 45; Light Cover 1 x 1 Round with Internal Bar / Bionicle Barraki Eye [58176] 23; Bar 1L with Clip [Cut Edges and One Side Hole] [Gap in Clip] [48729b] 23; Bar 1L with Clip [Cut Edges and One Side Hole] [Full Clip] [3484] 22; Bar 6L with Stop Ring [63965] 20; Bar 2L with Stop in Center [78258] 18; Hook with Towball [30395] 15
- **Speed Champions** (102 sets): Tile Special 1 x 1 with Clip with Rounded Edges [15712] 57; Tile Special Round 1 x 1 with Hollow Bar [20482] 52; Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 47; Plate Special Round 1 x 1 with Hollow Stud and Horizontal Bar 1L [32828] 43; Plate Special 1 x 1 with Clip Vertical [Thick Open O Clip] [60897] 34; Bar Holder with Hole and Bar Handle [23443] 33; Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 31; Hinge Brick 1 x 2 Base [3937] 28
- **Creator 3-in-1** (182 sets): Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 81; Tile Special 1 x 1 with Clip with Rounded Edges [15712] 77; Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 75; Plate Special 1 x 1 with Clip Vertical [Thick Open O Clip] [60897] 72; Plate Special 1 x 2 with Clips Horizontal [Open O Clips] [60470b] 71; Plate Special 1 x 2 with Clip Horizontal on End [63868] 68; Plate Special 1 x 2 5.9mm Centre Side Towball Socket [14704] 62; Plate Special 1 x 2 Side Handle [Free Ends] [2540] 61
- **Adult display (Icons/Creator Expert/UCS/Modular)** (142 sets): Tile Special 1 x 1 with Clip with Rounded Edges [15712] 118; Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 100; Bar 3L [87994] 98; Tile Special Round 1 x 1 with Hollow Bar [20482] 98; Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 96; Bar 4L (Lightsaber Blade / Wand) [30374] 95; Plate Special 1 x 1 with Clip Vertical [Thick Open O Clip] [60897] 94; Plate Special Round 1 x 1 with Hollow Stud and Horizontal Bar 1L [32828] 92
- **Botanicals** (53 sets): Bar 6L with Stop Ring [63965] 21; Tile Special 1 x 1 with Clip with Rounded Edges [15712] 20; Bar 3L [87994] 20; Plate Special 1 x 1 with Clip Horizontal [Thick Open O Clip] [61252] 19; Bar 2L with Stop in Center [78258] 19; Bar, Angled with 1 x 1 Round Plate / Stud on End [65578] 19; Bar 1L with Clip [Cut Edges and One Side Hole] [Full Clip] [3484] 19; Plate Special 2 x 2 with Bar Frame Octagonal, Reinforced, Completely Round Studs [75937] 18
- **Architecture** (40 sets): Bar 3L [87994] 21; Tile Special 1 x 1 with Clip with Rounded Edges [15712] 21; Plate Special 1 x 1 with Clip Vertical [Thick Open O Clip] [60897] 20; Bar 4L (Lightsaber Blade / Wand) [30374] 19; Tile Special Round 1 x 1 with Hollow Bar [20482] 16; Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 15; Bar 6L with Stop Ring [63965] 11; Plate Special Round 1 x 1 with Hollow Stud and Horizontal Bar 1L [32828] 11
- **BrickHeadz** (196 sets): Plate Special 1 x 2 with Clip Horizontal on Side [11476] 177; Tile Special 1 x 1 with Clip with Rounded Edges [15712] 52; Plate Special 1 x 1 with Clip Horizontal [Thick Open O Clip] [61252] 31; Plate Special 1 x 2 with Clip Horizontal on End [63868] 27; Bar 4L (Lightsaber Blade / Wand) [30374] 25; Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 25; Plate Special 1 x 1 with Clip Vertical [Thick Open O Clip] [60897] 19; Tile Special Round 1 x 1 with Hollow Bar [20482] 18
- **Ideas** (98 sets): Tile Special 1 x 1 with Clip with Rounded Edges [15712] 68; Tile Special Round 1 x 1 with Hollow Bar [20482] 60; Plate Special 1 x 1 Rounded with Handle [26047] 52; Bar 3L [87994] 51; Plate Special 1 x 1 with Clip Vertical [Thick Open O Clip] [60897] 48; Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 46; Bar 4L (Lightsaber Blade / Wand) [30374] 46; Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 45
- **City** (566 sets): Tile Special 1 x 2 with Handle [2432] 254; Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 199; Plate Special 1 x 2 with Clip Horizontal on Side [11476] 153; Tile Special 1 x 1 with Clip with Rounded Edges [15712] 151; Plate Special 1 x 1 with Clip Vertical [Thick Open O Clip] [60897] 146; Tile Special Round 1 x 1 with Hollow Bar [20482] 144; Plate Special 1 x 2 with Clips Horizontal [Open O Clips] [60470b] 133; Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 125
- **Friends** (547 sets): Tile Special Round 1 x 1 with Hollow Bar [20482] 257; Tile Special 1 x 1 with Clip with Rounded Edges [15712] 203; Plate Special 1 x 1 with Clip Vertical [Thick Open O Clip] [60897] 157; Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 145; Bar 3L [87994] 129; Brick Special 1 x 1 with Clip Vertical [Open O Clip, Hollow Stud] [60475b] 117; Bar 6L with Stop Ring [63965] 106; Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 105
- **Star Wars (play)** (539 sets): Bar 4L (Lightsaber Blade / Wand) [30374] 189; Tile Special 1 x 1 with Clip with Rounded Edges [15712] 186; Plate Special 1 x 2 with Clip Horizontal on End [63868] 152; Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 141; Plate Special 1 x 2 with Clips Horizontal [Open O Clips] [60470b] 134; Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 131; Plate Special 1 x 1 with Clip Vertical [Thick Open O Clip] [60897] 130; Plate Special 1 x 1 with Clip Horizontal [Thick Open O Clip] [61252] 121
- **Ninjago** (375 sets): Tile Special 1 x 1 with Clip with Rounded Edges [15712] 197; Plate Special 1 x 2 with Clip Horizontal on Side [11476] 144; Plate Special 1 x 2 with Clips Horizontal [Open O Clips] [60470b] 144; Plate Special 1 x 1 with Clip Vertical [Thick Open O Clip] [60897] 140; Plate Special 1 x 1 with Clip Horizontal [Thick Open O Clip] [61252] 132; Plate Special 1 x 2 Side Handle [Free Ends] [2540] 132; Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 131; Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 130
- **Super Heroes** (454 sets): Tile Special 1 x 1 with Clip with Rounded Edges [15712] 186; Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 168; Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 158; Plate Special 1 x 2 Side Handle [Free Ends] [2540] 156; Plate Special 1 x 2 with Clips Horizontal [Open O Clips] [60470b] 152; Plate Special 1 x 2 with Clip Horizontal on End [63868] 132; Plate Special 1 x 2 5.9mm Centre Side Towball Socket [14704] 126; Plate Special 1 x 1 with Clip Horizontal [Thick Open O Clip] [61252] 123
- **Harry Potter** (142 sets): Tile Special Round 1 x 1 with Hollow Bar [20482] 81; Tile Special 1 x 1 with Clip with Rounded Edges [15712] 71; Plate Special 1 x 1 with Clip Vertical [Thick Open O Clip] [60897] 60; Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 51; Brick Special 1 x 1 with Clip Vertical [Open O Clip, Hollow Stud] [60475b] 42; Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 41; Plate Special 1 x 1 Rounded with Handle [26047] 40; Plate Special 1 x 2 with Clip Horizontal on End [63868] 39
- **Minecraft** (170 sets): Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 58; Tile Special Round 1 x 1 with Hollow Bar [20482] 44; Tile Special 1 x 1 with Clip with Rounded Edges [15712] 43; Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 38; Plate Special 1 x 2 with Clip Horizontal on Side [11476] 33; Plate Special 1 x 2 with Clip Horizontal on End [63868] 33; Treasure Chest Lid [Thick Hinge] [4739a] 31; Brick Special 1 x 1 with Clip Vertical [Open O Clip, Hollow Stud] [60475b] 28
- **Disney** (231 sets): Tile Special Round 1 x 1 with Hollow Bar [20482] 90; Tile Special 1 x 1 with Clip with Rounded Edges [15712] 80; Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 75; Plate Special 1 x 2 with Clip Horizontal on Side [11476] 57; Plate Special 1 x 1 with Clip Vertical [Thick Open O Clip] [60897] 56; Bar 4L (Lightsaber Blade / Wand) [30374] 51; Brick Special 1 x 1 with Clip Vertical [Open O Clip, Hollow Stud] [60475b] 50; Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 48
- **Creator (other)** (77 sets): Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 15; Plate Special 1 x 1 with Clip Vertical [Thick Open O Clip] [60897] 14; Tile Special 1 x 1 with Clip with Rounded Edges [15712] 13; Plate Special 1 x 2 with Clip Horizontal on End [63868] 13; Plate Special 1 x 1 Rounded with Handle [26047] 13; Plate Special 1 x 2 with 5.9mm Centre Side Towball [14417] 11; Plate Special 1 x 2 with Clip Horizontal on Side [11476] 11; Plate Special 1 x 1 with Clip Horizontal [Thick Open O Clip] [61252] 11
- **Classic** (67 sets): Antenna 1 x 4 with Flat Top [3957b] 22; Lever Small Base with Black Lever [298c02] 20; Plate Special 1 x 2 with Clip Horizontal on End [63868] 19; Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 19; Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 18; Turntable 2 x 2 Plate - Top [3679] 14; Turntable 2 x 2 Plate, Base [3680] 14; Plate Special 1 x 1 with Clip Light, Bar Hole [Thick Ring] [4081b] 14
- **Super Mario** (155 sets): Hinge Brick 1 x 2 Base [3937] 48; Tile Special Round 1 x 1 with Hollow Bar [20482] 47; Hinge Brick 2 x 2 Top Plate Thin [6134] 39; Tile Special 1 x 1 with Clip with Rounded Edges [15712] 33; Antenna 1 x 4 with Flat Top [3957b] 31; Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 28; Turntable 4 x 4 Square Base, Locking [61485] 26; Plate Special 1 x 2 with Clips Horizontal [Open O Clips] [60470b] 23
- **Jurassic World** (126 sets): Tile Special 1 x 1 with Clip with Rounded Edges [15712] 52; Plate Special 1 x 1 with Clip Vertical [Thick Open O Clip] [60897] 43; Tile Special 1 x 2 with Handle [2432] 41; Plate Special 1 x 2 with Clips Horizontal [Open O Clips] [60470b] 35; Plate Special 1 x 2 Side Handle [Free Ends] [2540] 33; Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 30; Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 30; Plate Special 1 x 2 with Clip Horizontal on End [63868] 29
- **Dreamzzz** (58 sets): Plate Special 1 x 2 5.9mm Centre Side Towball Socket [14704] 32; Plate Special 1 x 1 Rounded with Handle [26047] 29; Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 27; Plate Special 1 x 1 with Clip Vertical [Thick Open O Clip] [60897] 24; Plate Special Round 1 x 1 with Hollow Stud and Horizontal Bar 1L [32828] 23; Bar Holder with Clip [11090] 23; Tile Special 1 x 1 with Clip with Rounded Edges [15712] 23; Bar 4L (Lightsaber Blade / Wand) [30374] 22
- **Monkie Kid** (57 sets): Bar 4L (Lightsaber Blade / Wand) [30374] 49; Tile Special 1 x 1 with Clip with Rounded Edges [15712] 41; Plate Special 1 x 2, Top Clip [Open O] [44861] 40; Plate Special 1 x 2 with Clip Horizontal on Side [11476] 39; Plate Special 1 x 2 with Clips Horizontal [Open O Clips] [60470b] 37; Plate Special Round 1 x 1 with Hollow Stud and Horizontal Bar 1L [32828] 33; Tile Special Round 1 x 1 with Hollow Bar [20482] 33; Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 33
- **Other themes** (1334 sets): Tile Special 1 x 1 with Clip with Rounded Edges [15712] 440; Plate Special 1 x 1 with Clip Vertical [Thick Open O Clip] [60897] 331; Plate Special 1 x 2 [Side Handle Closed Ends] [48336] 318; Plate Special 1 x 2 with Handle on End [Closed Ends] [60478] 307; Plate Special 1 x 1 with Clip Horizontal [Thick Open O Clip] [61252] 297; Tile Special Round 1 x 1 with Hollow Bar [20482] 263; Plate Special 1 x 2 with Clip Horizontal on End [63868] 251; Plate Special 1 x 2 Side Handle [Free Ends] [2540] 240

### C3. Wheel mountings: parts that go with wheels

Method: among non-Technic sets, compare sets that contain a wheel or tyre (Rebrickable category "Wheels and Tyres") with sets that do not. A part counts as a wheel mounting if its name mentions a wheel holder, stub axle, axle or pin and it is at least three times as common in wheeled sets. Ranked by number of wheeled sets using it.

Wheeled sets: 2174; sets without wheels: 3537.

| rank | part | name | wheeled sets using it | % of wheeled sets | times more common than in wheel-less sets |
|---:|---|---|---:|---:|---:|
| 1 | 3829c01 | Steering Stand 1 x 2 with Black Steering Wheel | 710 | 33 | 20.6 |
| 2 | 3749 | Technic Axle Pin without Friction Ridges Lengthwise | 516 | 24 | 4.3 |
| 3 | 3894 | Technic Brick 1 x 6 [5 Pin Holes] | 306 | 14 | 3.7 |
| 4 | 3702 | Technic Brick 1 x 8 [7 Pin Holes] | 232 | 11 | 3.8 |
| 5 | 32054 | Technic Pin Long with Friction Ridges Lengthwise and Stop Bush [3 Lateral Holes, Big Pin Hole] | 188 | 9 | 3.1 |
| 6 | 3703 | Technic Brick 1 x 16 [15 Pin Holes] | 185 | 9 | 4.3 |
| 7 | 59426 | Technic Axle 5.5 with Stop [Rounded Short End] | 174 | 8 | 3.8 |
| 8 | 3895 | Technic Brick 1 x 12 [11 Pin Holes] | 172 | 8 | 4.4 |
| 9 | 55013 | Technic Axle 8 with Stop | 167 | 8 | 3.6 |
| 10 | 6232 | Brick Special 2 x 2 with Pin and Axle Hole | 166 | 8 | 3.2 |
| 11 | 2730 | Technic Brick 1 x 10 [9 Pin Holes] | 162 | 7 | 3.9 |
| 12 | 16091 | Steering Wheel Small, 2 x 2 [Reinforced] | 158 | 7 | 4.7 |
| 13 | 32184 | Technic Axle and Pin Connector Perpendicular 3L with Centre Pin Hole | 157 | 7 | 3.2 |
| 14 | 3707 | Technic Axle 8 | 154 | 7 | 3.0 |
| 15 | 98282 | Wheel Arch, Mudguard 4 x 2 1/2 x 1 | 149 | 7 | 26.9 |
| 16 | 32018 | Technic Brick 1 x 14 [13 Pin Holes] | 148 | 7 | 4.0 |
| 17 | 2655 | Wheel Holder, Plate, Round 2 x 2 Thin with Clips | 144 | 7 | 234.3 |
| 18 | 63082 | Plate Special 2 x 2 with Towball Socket, Short, Flattened with Holes and Axle Hole in Center | 143 | 7 | 10.1 |
| 19 | 4600 | Plate Special 2 x 2 with Wheel Holders | 143 | 7 | 12.9 |
| 20 | 18671 | Bracket 3 x 2 x 1 1/3 with Pin Bottom | 143 | 7 | 3.9 |

Commonest wheels and tyres by group (top 5):

- **City** (449 wheeled sets): Wheel 11 x 12 with Hole Notched for Wheels Holder Pin [6014b] 132; Tyre 21 x 12 with Offset Tread Small Wide and Center Band [87697] 101; Wheel 18 x 14 with Pin Hole, Fake Bolts and Shallow Spokes [55981] 101; Wheel Centre 15 x 6 City Motorcycle with Stub Axles [50862] 67; Tyre 21 x 6 City Motorcycle [50861] 67
- **Speed Champions** (101 wheeled sets): Tyre 24 x 12 Low Profile [18977] 44; Wheel 18 x 12 with Axle Hole and Stud [18976] 34; Wheel Rim 24 x 12 with Black Tyre [72206] 26; Wheel Rim 24 x 13.4 with Black Slick Tyre [Hard Rubber] [105162] 17; Wheel Rim 24 x 14.9 Wide with Black Slick Tyre [110100] 13
- **Creator 3-in-1** (85 wheeled sets): Wheel 11 x 8 with Center Groove [42610] 13; Tyre Offset Tread with Center Band 23 x 7 [61254] 13; Wheel Skateboard / Trolley [2496] 11; Wheel 18mm x 14mm with Axle Hole, Fake Bolts and Shallow Spokes [55982] 11; Tyre 14 x 6 Solid Smooth [50951] 8
- **Friends** (213 wheeled sets): Wheel Skateboard / Trolley [2496] 81; Wheel 11 x 12 with Hole Notched for Wheels Holder Pin [6014b] 41; Tyre 21 x 12 with Offset Tread Small Wide and Center Band [87697] 37; Wheel Bicycle, Fixed Black Tire [92851] 25; Tyre 14 x 4 Smooth Small Single [New Style] [59895] 20
- **Super Heroes** (218 wheeled sets): Wheel 18 x 14 with Pin Hole, Fake Bolts and Shallow Spokes [55981] 61; Tyre 14 x 9 Smooth Small Wide Slick [30028] 30; Wheel 8 x 9 with Hole Notched for Wheels Holder Pin, Re-inforced Back [74967] 29; Tyre 14 x 4 Smooth Small Single [New Style] [59895] 26; Wheel 11 x 8 with Center Groove [42610] 23
- **Adult display (Icons/Creator Expert/UCS/Modular)** (90 wheeled sets): Wheel 11 x 8 with Center Groove [42610] 29; Technic Wedge Belt Wheel [aka Pulley] [4185] 19; Wheel 30 x 14 [56904] 14; Wheel Skateboard / Trolley [2496] 12; Wheel 18 x 8 with Fake Bolts and Deep Spokes with Inner Ring [13971] 11
- **Other themes** (380 wheeled sets): Wheel Skateboard / Trolley [2496] 72; Wheel 11 x 8 with Center Groove [42610] 52; Wheel 18 x 14 with Pin Hole, Fake Bolts and Shallow Spokes [55981] 39; Wheel 11 x 12 with Hole Notched for Wheels Holder Pin [6014b] 31; Tyre 21 x 12 with Offset Tread Small Wide and Center Band [87697] 27

### D1. Variety against size (all groups except Technic and Classic)

| parts | sets | distinct parts median (IQR) | distinct colours median | distinct part+colour median | parts per distinct part+colour (median) |
|---|---:|---|---:|---:|---:|
| 0-50 | 1075 | 15 (11-19) | 7 | 17 | 1.6 |
| 50-100 | 825 | 29 (24-35) | 10 | 32 | 1.9 |
| 100-150 | 435 | 45 (37-53) | 13 | 52 | 2.1 |
| 150-250 | 810 | 64 (50-75) | 16 | 78 | 2.3 |
| 250-400 | 807 | 89 (72-102) | 18 | 113 | 2.6 |
| 400-600 | 542 | 121 (99-135) | 20 | 158 | 2.9 |
| 600-1000 | 589 | 155 (129-174) | 22 | 219 | 3.3 |
| 1000-1500 | 290 | 190 (166-220) | 24 | 294 | 3.8 |
| 1500-2500 | 156 | 230 (196-258) | 26 | 390 | 4.6 |
| 2500-+ | 115 | 279 (238-313) | 32 | 547 | 6.2 |

### D2. Finish parts against size (all groups except Technic, Classic, BrickHeadz): mean % of build parts

| parts | sets | tile | slope | curved_slope | wedge | round | plate | brick | sideways | pinbeam | joints (hinge+turntable+clip+bar+ball) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0-50 | 1075 | 12.0 | 5.5 | 4.4 | 2.4 | 14.0 | 12.7 | 4.4 | 4.7 | 4.0 | 12.4 |
| 50-100 | 812 | 10.3 | 6.7 | 6.2 | 2.8 | 11.2 | 13.6 | 4.8 | 5.1 | 5.3 | 13.5 |
| 100-150 | 375 | 10.4 | 6.5 | 6.3 | 2.5 | 11.0 | 12.9 | 5.8 | 4.4 | 7.1 | 10.9 |
| 150-250 | 747 | 12.0 | 6.4 | 5.9 | 2.6 | 10.5 | 16.6 | 6.5 | 5.1 | 6.3 | 9.7 |
| 250-400 | 768 | 12.4 | 6.3 | 6.0 | 3.1 | 10.3 | 17.2 | 6.1 | 6.2 | 6.4 | 9.3 |
| 400-600 | 529 | 11.7 | 6.0 | 5.8 | 3.1 | 9.9 | 18.6 | 7.6 | 5.7 | 8.8 | 8.1 |
| 600-1000 | 581 | 12.2 | 6.0 | 5.5 | 3.0 | 9.2 | 18.6 | 7.6 | 6.3 | 9.0 | 7.9 |
| 1000-1500 | 290 | 12.7 | 6.0 | 5.5 | 3.4 | 8.8 | 20.0 | 6.9 | 6.5 | 9.8 | 7.3 |
| 1500-2500 | 156 | 14.2 | 5.7 | 6.0 | 3.0 | 7.7 | 21.1 | 7.3 | 7.2 | 8.3 | 6.6 |
| 2500-+ | 115 | 14.3 | 5.9 | 4.3 | 2.6 | 7.6 | 21.5 | 9.9 | 6.6 | 6.6 | 6.8 |

### D3. The parts found in the most sets of 80 to 150 parts (all groups except Technic)

Sets: 723

| part | name | job | % of sets |
|---|---|---|---:|
| 3023 | Plate 1 x 2 | plate | 73 |
| 3020 | Plate 2 x 4 | plate | 59 |
| 3022 | Plate 2 x 2 | plate | 55 |
| 3069b | Tile 1 x 2 with Groove | tile | 54 |
| 3710 | Plate 1 x 4 | plate | 51 |
| 6141 | Plate Round 1 x 1 with Solid Stud | round | 46 |
| 15573 | Plate Special 1 x 2 with 1 Stud with Groove and Inside Stud Holder (Jumper) | special_other | 42 |
| 98138 | Tile Round 1 x 1 | tile | 42 |
| 3004 | Brick 1 x 2 | brick | 39 |
| 3024 | Plate 1 x 1 | plate | 37 |
| 54200 | Brick Sloped 30° 1 x 1 x 2/3 (Cheese Slope) | slope | 37 |
| 85984 | Brick Sloped 30° 1 x 2 x 2/3 | slope | 37 |
| 15068 | Brick Curved 2 x 2 x 2/3 | curved_slope | 37 |
| 11477 | Brick Curved 2 x 1 No Studs [1/2 Bow] | curved_slope | 36 |
| 3021 | Plate 2 x 3 | plate | 36 |
| 2431 | Tile 1 x 4 with Groove | tile | 35 |
| 3068b | Tile 2 x 2 with Groove | tile | 32 |
| 87079 | Tile 2 x 4 with Groove | tile | 32 |
| 3005 | Brick 1 x 1 | brick | 31 |
| 4032a | Plate Round 2 x 2 with Axle Hole Type 1 (+ Opening) | round | 31 |
| 2412b | Tile Special 1 x 2 Grille with Bottom Groove | tile | 31 |
| 3003 | Brick 2 x 2 | brick | 30 |
| 3010 | Brick 1 x 4 | brick | 29 |
| 87580 | Plate Special 2 x 2 with Groove and Center Stud (Jumper) | special_other | 28 |
| 3062b | Brick Round 1 x 1 Open Stud | round | 28 |

Notes on C and D. The sideways vocabulary is small: **six parts** (the 1 x 2 - 1 x 2 bracket and its
inverted form, the 1 x 2 - 2 x 2 bracket and its inverted form, the 1 x 2 brick with two side studs, and
the 1 x 1 brick with one side stud) are each in 29-37 % of all non-Technic sets. BrickHeadz use the 1 x 2
x 1 2/3 brick with four side studs in 195 of 196 sets (it is how their faces are mounted); Super Mario
uses the 1 x 2 x 1 2/3 brick with studs on three sides; Botanicals favour the 1 x 1 brick with studs on
four sides. The joint vocabulary is dominated by clips and bar handles on plates and tiles, not hinges:
the first hinge (the 1 x 2 hinge brick base) is only 15th. The wheel-mounting table is a correlation and
picks up chassis parts (long Technic bricks) as well as true mountings; the clearest mountings are the
steering stand, the round 2 x 2 wheel holder plate (234 times more common in wheeled sets) and the 2 x 2
plate with wheel holders.

## Part B: building order from the LDraw Official Model Repository

49 models fetched, 41 with usable steps (17 non-Technic under 500 parts, 18 non-Technic of 500 parts and
more, 6 Technic). Remember that B describes the OMR author's reproduction of the booklet order.

**What the start of the build is made of ("the core" in numbers).** In non-Technic models the first
tenth of the parts is above all **plates** (27-30 %, against 19-21 % in the last two thirds), with more
plain bricks and sideways-building parts than later; slopes, curves and wedges (10 % at first, 12-21 %
later) and joints (3-6 % at first, 8-10 % later) are what the second part of a build adds. Pin/beam parts
are somewhat more common at the very start of small models (12 % against 6 %), driven by three small sets
whose first steps are a Technic skeleton (75075 AT-AT legs and body, 30285 Tiger, 31072 Extreme Engines);
in large models they are as common at the start as at the end (9 % both). Per model (B-T9), a clear
pin/beam core shows in 10252 Volkswagen Beetle (31 % of the first fifth, 7 % overall) and to a lesser
degree 10271 Fiat 500 and 60216 Downtown Fire Brigade; in most display models the pin/beam parts belong
to mechanisms and details added later (Vespa, Space Shuttle, Modern House, Hogwarts Great Hall), and the
Speed Champions cars and the Batmobile start on plates with no Technic at all. In Technic, the first tenth
is 90 % pin/beam and the proportion barely changes.

**How the model grows.** Mostly bottom up, rarely inside out: build order and height correlate
positively (rho above +0.2) in 27 of 41 stepped models (median rho +0.34 for non-Technic, +0.53 for Technic), and strongly
(rho above 0.7) in buildings and tall models (Arc de Triomphe +0.99, Guggenheim +0.87, Saturn V +0.80,
Corner Garage +0.71, Space Shuttle Explorer +0.88). Inside-out (distance from the centre growing with
order) is clear in Technic (5 of 6) and in models built around a central body: BrickHeadz (Bear +0.75,
Shorthair Cats +0.42), the Sith TIE Fighter (+0.74), Botanicals (Flower Bouquet +0.58, Bonsai +0.45), WALL-E
(+0.43). Plant sets build *downwards* or outward from the flower heads (Flower Bouquet height rho -0.43):
the stems are built first and the arrangement is assembled from separate flowers. Sub-models are the
rule: a median of 6 per small model and 36 per large one; 60-72 % of parts are placed inside a
sub-model rather than on the main line; sub-models are small (median 11 own parts in small sets, 6 in
large ones) and about a third of those in large models are used twice or more (mirrored or repeated
sub-assemblies: wheels, wings, wall sections).

**Parts per step.** Median 2 parts per step outside Technic (mean about 3), about 6 in Technic; 13 % of
steps add no loose part at all (they attach a finished sub-assembly), 20 % add one part, 26 % two. There
is no trend from the start of the build to the end (B-T4).

**Sideways and upside down.** Studded parts placed sideways rise through the build (median model: 10 % in
the first third of steps, 26 % in the middle, 32 % in the last third; pooled over all parts, 10 % in the
first tenth and 40-48 % in the last three tenths). Angled placement (neither upright nor at a right angle)
is small and comes late. Upside-down placement is about 0-2 % at every stage; no non-Technic model
places more than 6 % of its studded parts upside down (75144 Snowspeeder).

**Moving parts.** Wheels and tyres go on late: median first appearance at 62 % of the build and median
position 86 %. Hinges first appear at about 20 % of the way, with their median at the middle; ball and
towball joints first appear at 45 %. The 5 models with turntables place them right at the start (4 %), as
the base of a rotating section.

### B-T1. The sample: one row per model

parts = build parts in the OMR file (minifigure and sticker parts left out); RB = Rebrickable part count for the set (includes minifigures and spares rules of its own); steps = steps after unrolling sub-models (a sub-model used twice is counted twice); stepped = has at least 10 steps and at most 8 parts per step, the files used for the order measures; sub-models = non-minifigure sub-models; height rho = rank correlation between build order and height of the part (positive = bottom up); outward rho = rank correlation between build order and horizontal distance from the model centre (positive = inside out); sideways / upside down = share of studded System parts whose top does not point up.

| set | name | group | parts | RB | steps | parts/step | stepped | sub-models | used >1 | parts built in sub-models | height rho | outward rho | sideways | angled | upside down |
|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 10271-1 | Fiat 500 | Adult display (Icons/Creator Expert/UCS/Modular) | 955 | 960 | 282 | 3.4 | yes | 23 | 3 | 100 % | +0.39 | +0.17 | 24 % | 15 % | 0 % |
| 10298-1 | Vespa 125 | Adult display (Icons/Creator Expert/UCS/Modular) | 1086 | 1107 | 237 | 4.6 | yes | 34 | 0 | 81 % | +0.15 | +0.34 | 43 % | 19 % | 3 % |
| 10252-1 | Volkswagen Beetle | Adult display (Icons/Creator Expert/UCS/Modular) | 1148 | 1167 | 504 | 2.3 | yes | 72 | 32 | 50 % | +0.65 | -0.06 | 30 % | 7 % | 0 % |
| 10258-1 | London Bus | Adult display (Icons/Creator Expert/UCS/Modular) | 1626 | 1686 | 165 | 9.9 | no | 11 | 3 | 65 % | +0.92 | -0.03 | 26 % | 0 % | 1 % |
| 75144-1 | Snowspeeder | Adult display (Icons/Creator Expert/UCS/Modular) | 1645 | 1703 | 746 | 2.2 | yes | 91 | 34 | 32 % | +0.29 | +0.45 | 13 % | 39 % | 6 % |
| 10283-1 | NASA Space Shuttle Discovery | Adult display (Icons/Creator Expert/UCS/Modular) | 2290 | 2355 | 1020 | 2.2 | yes | 170 | 50 | 100 % | +0.52 | -0.00 | 22 % | 21 % | 4 % |
| 10264-1 | Corner Garage | Adult display (Icons/Creator Expert/UCS/Modular) | 2454 | 2569 | 876 | 2.8 | yes | 183 | 52 | 83 % | +0.71 | +0.01 | 17 % | 0 % | 0 % |
| 21026-1 | Venice | Architecture | 209 | 212 | 13 | 16.1 | no | 8 | 4 | 36 % | -0.30 | +0.49 | 13 % | 0 % | 0 % |
| 21036-1 | Arc de Triomphe | Architecture | 382 | 386 | 130 | 2.9 | yes | 10 | 8 | 61 % | +0.99 | -0.27 | 26 % | 0 % | 0 % |
| 21035-1 | Solomon R. Guggenheim Museum | Architecture | 743 | 744 | 102 | 7.3 | yes | 7 | 3 | 21 % | +0.87 | -0.30 | 36 % | 0 % | 0 % |
| 21046-1 | Empire State Building | Architecture | 1766 | 1767 | 399 | 4.4 | yes | 33 | 21 | 90 % | +0.72 | -0.24 | 63 % | 0 % | 2 % |
| 10349-1 | Happy Plants | Botanicals | 212 | 217 | 85 | 2.5 | yes | 6 | 2 | 100 % | +0.02 | -0.15 | 58 % | 0 % | 0 % |
| 10281-1 | Bonsai Tree | Botanicals | 648 | 878 | 163 | 4.0 | yes | 24 | 7 | 69 % | -0.26 | +0.45 | 9 % | 19 % | 0 % |
| 10280-1 | Flower Bouquet | Botanicals | 735 | 756 | 430 | 1.7 | yes | 39 | 28 | 100 % | -0.43 | +0.58 | 15 % | 56 % | 3 % |
| 41596-1 | Beast | BrickHeadz | 116 | 116 | 12 | 9.7 | no | 7 | 4 | 32 % | +0.28 | +0.12 | 47 % | 0 % | 2 % |
| 40379-1 | Bear | BrickHeadz | 149 | 150 | 69 | 2.2 | yes | 11 | 2 | 48 % | -0.22 | +0.75 | 43 % | 0 % | 0 % |
| 40441-1 | Shorthair Cat and Kitten | BrickHeadz | 246 | 250 | 117 | 2.1 | yes | 15 | 2 | 100 % | -0.20 | +0.42 | 35 % | 2 % | 0 % |
| 41498-1 | Boba Fett & Han Solo in Carbonite | BrickHeadz | 327 | 329 | 26 | 12.6 | no | 21 | 4 | 100 % | +0.25 | -0.15 | 51 % | 0 % | 1 % |
| 60065-1 | ATV Patrol | City | 47 | 59 | 9 | 5.2 | no | 3 | 1 | 98 % | +0.15 | +0.68 | 40 % | 0 % | 0 % |
| 60101-1 | Airport Cargo Plane | City | 141 | 157 | 23 | 6.1 | yes | 3 | 1 | 100 % | +0.50 | -0.12 | 4 % | 0 % | 1 % |
| 60067-1 | Helicopter Pursuit | City | 232 | 253 | 10 | 23.2 | no | 5 | 1 | 100 % | -0.12 | +0.48 | 7 % | 1 % | 0 % |
| 60216-1 | Downtown Fire Brigade | City | 889 | 943 | 214 | 4.2 | yes | 39 | 6 | 100 % | -0.20 | +0.37 | 13 % | 0 % | 0 % |
| 30285-1 | Tiger | Creator (other) | 73 | 73 | 15 | 4.9 | yes | 3 | 1 | 77 % | +0.55 | +0.70 | 4 % | 9 % | 0 % |
| 31072-1 | Extreme Engines | Creator 3-in-1 | 109 | 109 | 44 | 2.5 | yes | 2 | 1 | 29 % | +0.46 | -0.01 | 45 % | 6 % | 0 % |
| 31045-1 | Ocean Explorer | Creator 3-in-1 | 210 | 213 | 81 | 2.6 | yes | 6 | 0 | 43 % | +0.30 | +0.59 | 36 % | 2 % | 0 % |
| 31066-1 | Space Shuttle Explorer | Creator 3-in-1 | 277 | 285 | 40 | 6.9 | yes | 6 | 1 | 18 % | +0.88 | -0.02 | 24 % | 15 % | 0 % |
| 31039-1 | Blue Power Jet | Creator 3-in-1 | 608 | 608 | 14 | 43.4 | no | 11 | 2 | 36 % | +0.13 | -0.03 | 10 % | 1 % | 0 % |
| 31084-1 | Pirate Roller Coaster | Creator 3-in-1 | 886 | 923 | 153 | 5.8 | yes | 25 | 1 | 53 % | +0.36 | -0.13 | 7 % | 14 % | 0 % |
| 31153-1 | Modern House | Creator 3-in-1 | 908 | 939 | 302 | 3.0 | yes | 28 | 0 | 71 % | -0.09 | -0.01 | 17 % | 1 % | 3 % |
| 41092-1 | Stephanie's Pizzeria | Friends | 78 | 87 | 16 | 4.9 | yes | 5 | 1 | 100 % | +0.23 | -0.50 | 4 % | 0 % | 4 % |
| 75966-1 | Hogwarts Room of Requirement | Harry Potter | 167 | 194 | 68 | 2.5 | yes | 5 | 1 | 100 % | +0.07 | -0.06 | 12 % | 2 % | 0 % |
| 75954-1 | Hogwarts Great Hall | Harry Potter | 777 | 882 | 252 | 3.1 | yes | 15 | 3 | 29 % | +0.71 | -0.27 | 3 % | 8 % | 0 % |
| 21303-1 | WALL•E [Original Version] | Ideas | 678 | 677 | 173 | 3.9 | yes | 41 | 8 | 61 % | -0.18 | +0.43 | 26 % | 14 % | 3 % |
| 21319-1 | Central Perk | Ideas | 1003 | 1070 | 374 | 2.7 | yes | 57 | 7 | 66 % | +0.16 | -0.20 | 32 % | 1 % | 1 % |
| 21309-1 | NASA Apollo Saturn V | Ideas | 1812 | 1969 | 1068 | 1.7 | yes | 100 | 71 | 96 % | +0.80 | -0.26 | 70 % | 1 % | 3 % |
| 41075-1 | The Elves' Treetop Hideaway | Other themes | 480 | 517 | 61 | 7.9 | yes | 7 | 0 | 97 % | +0.34 | -0.35 | 6 % | 7 % | 0 % |
| 75895-1 | 1974 Porsche 911 Turbo 3.0 | Speed Champions | 166 | 180 | 69 | 2.4 | yes | 4 | 1 | 10 % | +0.34 | +0.37 | 22 % | 0 % | 2 % |
| 75892-1 | McLaren Senna | Speed Champions | 204 | 222 | 89 | 2.3 | yes | 8 | 1 | 71 % | +0.05 | +0.52 | 28 % | 0 % | 1 % |
| 76897-1 | 1985 Audi Sport quattro S1 | Speed Champions | 250 | 253 | 72 | 3.5 | yes | 7 | 1 | 28 % | +0.39 | -0.17 | 25 % | 0 % | 0 % |
| 75075-1 | AT-AT | Star Wars (play) | 83 | 88 | 31 | 2.7 | yes | 2 | 0 | 24 % | -0.25 | +0.49 | 27 % | 7 % | 0 % |
| 75272-1 | Sith TIE Fighter | Star Wars (play) | 452 | 470 | 156 | 2.9 | yes | 11 | 3 | 81 % | +0.08 | +0.74 | 69 % | 2 % | 0 % |
| 75155-1 | Rebel U-Wing Fighter | Star Wars (play) | 612 | 659 | 317 | 1.9 | yes | 30 | 9 | 73 % | -0.04 | +0.17 | 16 % | 3 % | 1 % |
| 40433-1 | 1989 Batmobile - Limited Edition | Super Heroes | 358 | 366 | 105 | 3.4 | yes | 5 | 1 | 21 % | +0.78 | +0.16 | 18 % | 0 % | 0 % |
| 42058-1 | Stunt Bike | Technic | 139 | 140 | 25 | 5.6 | yes | 6 | 0 | 49 % | +0.32 | +0.33 | 0 % | 100 % | 0 % |
| 42061-1 | Telehandler | Technic | 261 | 260 | 48 | 5.4 | yes | 7 | 1 | 63 % | +0.64 | +0.06 | 80 % | 0 % | 0 % |
| 42093-1 | Chevrolet Corvette ZR1 | Technic | 575 | 579 | 99 | 5.8 | yes | 28 | 0 | 57 % | +0.54 | +0.41 | 100 % | 0 % | 0 % |
| 42080-1 | Forest Machine | Technic | 986 | 1003 | 192 | 5.1 | yes | 48 | 3 | 87 % | +0.51 | +0.58 | 34 % | 16 % | 4 % |
| 42096-1 | Porsche 911 RSR | Technic | 1569 | 1580 | 255 | 6.2 | yes | 49 | 5 | 58 % | +0.60 | +0.21 | 46 % | 2 % | 19 % |
| 42083-1 | Bugatti Chiron | Technic | 3566 | 3599 | 552 | 6.5 | yes | 100 | 11 | 86 % | +0.29 | +0.34 | 62 % | 2 % | 0 % |

Models in the sample: 49; with usable steps: 42.


### B-T2. What the start of the build is made of (by order of parts placed): mean % of the parts in each segment, stepped models only


**non-Technic <500** (18 models)

| segment | pin/beam | other Technic | brick | plate | tile | slope/curve/wedge | round | sideways | joints | wheel | other special | plant/panel/other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| first 10% | 11.5 | 0.0 | 5.1 | 30.2 | 10.5 | 9.7 | 7.5 | 7.2 | 3.9 | 5.2 | 4.5 | 4.8 |
| first 20% | 9.4 | 0.0 | 8.1 | 29.6 | 10.6 | 9.7 | 5.6 | 8.7 | 3.6 | 3.3 | 5.8 | 5.6 |
| first third | 7.5 | 0.0 | 8.6 | 28.4 | 10.8 | 11.7 | 4.7 | 11.7 | 4.7 | 2.1 | 5.6 | 4.2 |
| last two thirds | 5.4 | 0.3 | 4.7 | 21.0 | 11.7 | 20.6 | 8.1 | 5.4 | 9.4 | 3.1 | 4.8 | 5.6 |

**non-Technic 500+** (18 models)

| segment | pin/beam | other Technic | brick | plate | tile | slope/curve/wedge | round | sideways | joints | wheel | other special | plant/panel/other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| first 10% | 9.3 | 0.0 | 7.9 | 27.1 | 15.0 | 9.5 | 5.8 | 8.1 | 6.4 | 0.0 | 6.6 | 4.2 |
| first 20% | 7.9 | 0.1 | 9.5 | 25.9 | 14.3 | 13.7 | 5.7 | 7.4 | 5.9 | 0.2 | 5.7 | 3.7 |
| first third | 6.6 | 0.1 | 10.1 | 24.5 | 14.3 | 13.5 | 6.5 | 6.8 | 6.3 | 0.3 | 5.8 | 5.4 |
| last two thirds | 8.9 | 0.9 | 6.2 | 18.6 | 17.4 | 12.1 | 7.5 | 6.8 | 8.3 | 1.1 | 6.3 | 5.9 |

**Technic** (6 models)

| segment | pin/beam | other Technic | brick | plate | tile | slope/curve/wedge | round | sideways | joints | wheel | other special | plant/panel/other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| first 10% | 92.2 | 6.8 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| first 20% | 89.1 | 9.8 | 0.0 | 0.0 | 0.1 | 0.0 | 0.7 | 0.0 | 0.3 | 0.0 | 0.0 | 0.0 |
| first third | 88.9 | 8.8 | 0.0 | 0.0 | 0.2 | 0.0 | 1.1 | 0.0 | 0.3 | 0.7 | 0.0 | 0.0 |
| last two thirds | 82.8 | 7.1 | 0.0 | 1.4 | 1.6 | 1.4 | 2.1 | 0.0 | 0.4 | 2.5 | 0.2 | 0.5 |

### B-T2. What the start of the build is made of (by share of steps): mean % of the parts in each segment, stepped models only


**non-Technic <500** (18 models)

| segment | pin/beam | other Technic | brick | plate | tile | slope/curve/wedge | round | sideways | joints | wheel | other special | plant/panel/other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| first 10% | 11.8 | 0.0 | 6.0 | 26.7 | 9.9 | 10.3 | 7.2 | 6.0 | 3.6 | 7.1 | 5.2 | 6.1 |
| first 20% | 9.2 | 0.0 | 9.3 | 29.7 | 8.4 | 9.9 | 5.1 | 9.1 | 3.4 | 6.5 | 4.8 | 4.8 |
| first third | 7.0 | 0.1 | 8.4 | 28.4 | 10.1 | 12.9 | 5.0 | 11.7 | 4.7 | 1.7 | 5.6 | 4.2 |
| last two thirds | 5.4 | 0.2 | 4.5 | 20.8 | 12.1 | 20.4 | 8.1 | 5.3 | 9.6 | 3.4 | 4.7 | 5.5 |

**non-Technic 500+** (18 models)

| segment | pin/beam | other Technic | brick | plate | tile | slope/curve/wedge | round | sideways | joints | wheel | other special | plant/panel/other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| first 10% | 8.4 | 0.1 | 8.4 | 26.5 | 14.4 | 11.4 | 4.9 | 7.8 | 6.2 | 0.3 | 7.4 | 4.2 |
| first 20% | 7.3 | 0.1 | 9.3 | 25.9 | 14.3 | 13.7 | 6.3 | 6.7 | 6.4 | 0.2 | 6.1 | 3.7 |
| first third | 6.9 | 0.1 | 9.5 | 24.5 | 13.9 | 13.4 | 6.4 | 7.1 | 6.5 | 0.4 | 6.0 | 5.2 |
| last two thirds | 8.9 | 1.0 | 6.2 | 18.5 | 17.2 | 12.1 | 7.7 | 6.7 | 8.4 | 1.1 | 6.4 | 5.8 |

**Technic** (6 models)

| segment | pin/beam | other Technic | brick | plate | tile | slope/curve/wedge | round | sideways | joints | wheel | other special | plant/panel/other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| first 10% | 90.2 | 8.8 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| first 20% | 89.8 | 9.0 | 0.0 | 0.0 | 0.1 | 0.0 | 0.8 | 0.0 | 0.3 | 0.0 | 0.0 | 0.0 |
| first third | 89.1 | 8.4 | 0.0 | 0.0 | 0.3 | 0.0 | 1.2 | 0.0 | 0.3 | 0.7 | 0.0 | 0.0 |
| last two thirds | 82.6 | 7.2 | 0.0 | 1.4 | 1.6 | 1.4 | 2.1 | 0.0 | 0.4 | 2.5 | 0.2 | 0.5 |

### B-T3. Per model: the two commonest kinds of part in the first 10 % and first third of the parts placed

| set | name | group | first 10 % | first third | rest |
|---|---|---|---|---|---|
| 10271-1 | Fiat 500 | Adult display (Icons/Creator Expert/UCS/Modular) | plate 37 %, pin/beam 25 % | plate 38 %, slope/curve/wedge 19 % | plate 23 %, slope/curve/wedge 19 % |
| 10298-1 | Vespa 125 | Adult display (Icons/Creator Expert/UCS/Modular) | plate 44 %, sideways 16 % | plate 36 %, slope/curve/wedge 23 % | plate 27 %, round 16 % |
| 10252-1 | Volkswagen Beetle | Adult display (Icons/Creator Expert/UCS/Modular) | pin/beam 44 %, tile 16 % | plate 24 %, pin/beam 18 % | plate 29 %, slope/curve/wedge 18 % |
| 75144-1 | Snowspeeder | Adult display (Icons/Creator Expert/UCS/Modular) | plate 38 %, pin/beam 13 % | plate 32 %, slope/curve/wedge 15 % | plate 18 %, tile 16 % |
| 10283-1 | NASA Space Shuttle Discovery | Adult display (Icons/Creator Expert/UCS/Modular) | slope/curve/wedge 28 %, plate 22 % | plate 24 %, slope/curve/wedge 18 % | slope/curve/wedge 24 %, plate 21 % |
| 10264-1 | Corner Garage | Adult display (Icons/Creator Expert/UCS/Modular) | tile 67 %, brick 10 % | tile 27 %, brick 20 % | plate 24 %, tile 18 % |
| 21036-1 | Arc de Triomphe | Architecture | tile 55 %, plate 34 % | plate 41 %, tile 35 % | plate 26 %, tile 18 % |
| 21035-1 | Solomon R. Guggenheim Museum | Architecture | tile 51 %, plate 45 % | plate 37 %, tile 31 % | tile 35 %, plate 25 % |
| 21046-1 | Empire State Building | Architecture | tile 40 %, plate 38 % | tile 36 %, plate 32 % | tile 53 %, sideways 23 % |
| 10349-1 | Happy Plants | Botanicals | sideways 29 %, plate 24 % | plate 27 %, round 20 % | plate 27 %, joints 25 % |
| 10281-1 | Bonsai Tree | Botanicals | sideways 28 %, slope/curve/wedge 23 % | slope/curve/wedge 24 %, tile 18 % | tile 51 %, plant/panel/other 13 % |
| 10280-1 | Flower Bouquet | Botanicals | plant/panel/other 47 %, joints 34 % | plant/panel/other 47 %, joints 24 % | pin/beam 30 %, round 28 % |
| 40379-1 | Bear | BrickHeadz | plate 64 %, pin/beam 14 % | plate 33 %, sideways 22 % | plate 25 %, tile 24 % |
| 40441-1 | Shorthair Cat and Kitten | BrickHeadz | plate 42 %, sideways 21 % | plate 44 %, sideways 24 % | plate 26 %, tile 21 % |
| 60101-1 | Airport Cargo Plane | City | wheel 36 %, tile 21 % | tile 23 %, wheel 21 % | slope/curve/wedge 28 %, plate 23 % |
| 60216-1 | Downtown Fire Brigade | City | brick 23 %, tile 23 % | brick 21 %, other special 19 % | plate 16 %, tile 15 % |
| 30285-1 | Tiger | Creator (other) | pin/beam 71 %, plate 29 % | pin/beam 38 %, plate 33 % | plate 39 %, slope/curve/wedge 22 % |
| 31072-1 | Extreme Engines | Creator 3-in-1 | pin/beam 20 %, plate 20 % | pin/beam 33 %, plate 22 % | slope/curve/wedge 29 %, joints 18 % |
| 31045-1 | Ocean Explorer | Creator 3-in-1 | plate 24 %, tile 24 % | plate 17 %, slope/curve/wedge 17 % | slope/curve/wedge 29 %, plate 19 % |
| 31066-1 | Space Shuttle Explorer | Creator 3-in-1 | plate 56 %, slope/curve/wedge 26 % | plate 39 %, slope/curve/wedge 16 % | slope/curve/wedge 17 %, pin/beam 16 % |
| 31084-1 | Pirate Roller Coaster | Creator 3-in-1 | brick 25 %, slope/curve/wedge 23 % | slope/curve/wedge 26 %, brick 25 % | slope/curve/wedge 20 %, other special 16 % |
| 31153-1 | Modern House | Creator 3-in-1 | tile 27 %, plate 23 % | tile 25 %, plate 22 % | plate 23 %, tile 17 % |
| 41092-1 | Stephanie's Pizzeria | Friends | wheel 57 %, plant/panel/other 29 % | plant/panel/other 27 %, brick 27 % | slope/curve/wedge 25 %, round 19 % |
| 75966-1 | Hogwarts Room of Requirement | Harry Potter | brick 25 %, plate 25 % | plate 25 %, brick 20 % | plate 26 %, tile 20 % |
| 75954-1 | Hogwarts Great Hall | Harry Potter | joints 26 %, plate 25 % | slope/curve/wedge 23 %, plate 17 % | plant/panel/other 23 %, slope/curve/wedge 21 % |
| 21303-1 | WALL•E [Original Version] | Ideas | plate 34 %, brick 28 % | plate 32 %, brick 17 % | pin/beam 19 %, tile 19 % |
| 21319-1 | Central Perk | Ideas | plate 61 %, joints 12 % | plate 33 %, brick 17 % | plate 23 %, brick 16 % |
| 21309-1 | NASA Apollo Saturn V | Ideas | sideways 24 %, plate 18 % | slope/curve/wedge 25 %, plate 18 % | slope/curve/wedge 23 %, plate 19 % |
| 41075-1 | The Elves' Treetop Hideaway | Other themes | slope/curve/wedge 29 %, round 29 % | brick 20 %, slope/curve/wedge 20 % | plant/panel/other 23 %, plate 18 % |
| 75895-1 | 1974 Porsche 911 Turbo 3.0 | Speed Champions | plate 44 %, round 19 % | plate 42 %, sideways 15 % | slope/curve/wedge 28 %, plate 17 % |
| 75892-1 | McLaren Senna | Speed Champions | sideways 30 %, plate 25 % | plate 22 %, other special 22 % | slope/curve/wedge 25 %, other special 18 % |
| 76897-1 | 1985 Audi Sport quattro S1 | Speed Champions | plate 40 %, other special 28 % | plate 39 %, other special 14 % | plate 23 %, slope/curve/wedge 20 % |
| 75075-1 | AT-AT | Star Wars (play) | pin/beam 75 %, plate 25 % | pin/beam 30 %, plate 19 % | round 25 %, slope/curve/wedge 21 % |
| 75272-1 | Sith TIE Fighter | Star Wars (play) | plate 36 %, slope/curve/wedge 33 % | plate 32 %, slope/curve/wedge 23 % | slope/curve/wedge 36 %, plate 30 % |
| 75155-1 | Rebel U-Wing Fighter | Star Wars (play) | pin/beam 44 %, plate 34 % | plate 37 %, slope/curve/wedge 16 % | pin/beam 26 %, plate 21 % |
| 40433-1 | 1989 Batmobile - Limited Edition | Super Heroes | plate 37 %, tile 26 % | plate 34 %, sideways 19 % | slope/curve/wedge 28 %, plate 25 % |
| 42058-1 | Stunt Bike | Technic | pin/beam 92 %, other Technic 8 % | pin/beam 87 %, other Technic 9 % | pin/beam 84 %, other Technic 9 % |
| 42061-1 | Telehandler | Technic | pin/beam 100 %, other Technic 0 % | pin/beam 95 %, other Technic 5 % | pin/beam 83 %, other Technic 9 % |
| 42093-1 | Chevrolet Corvette ZR1 | Technic | pin/beam 89 %, other Technic 11 % | pin/beam 95 %, other Technic 5 % | pin/beam 86 %, other Technic 7 % |
| 42080-1 | Forest Machine | Technic | pin/beam 94 %, round 6 % | pin/beam 86 %, round 7 % | pin/beam 76 %, round 8 % |
| 42096-1 | Porsche 911 RSR | Technic | pin/beam 88 %, other Technic 12 % | pin/beam 86 %, other Technic 13 % | pin/beam 88 %, other Technic 5 % |
| 42083-1 | Bugatti Chiron | Technic | pin/beam 90 %, other Technic 10 % | pin/beam 84 %, other Technic 15 % | pin/beam 81 %, other Technic 6 % |

### B-T4. Parts per step through the build (stepped models): median over models of the mean parts per step in each fifth of the steps

| family | models | 1st fifth | 2nd | 3rd | 4th | 5th | overall median parts/step |
|---|---:|---:|---:|---:|---:|---:|---:|
| non-Technic <500 | 18 | 2.7 | 2.6 | 2.9 | 3.0 | 2.5 | 2.0 |
| non-Technic 500+ | 18 | 3.2 | 2.7 | 3.0 | 2.8 | 3.2 | 2.0 |
| Technic | 6 | 6.1 | 6.3 | 5.7 | 5.5 | 5.3 | 6.0 |
| all | 42 | 3.6 | 3.1 | 3.4 | 3.1 | 3.3 | 2.0 |

Distribution of parts per step over all stepped models (10054 steps): 0: 13 %, 1: 20 %, 2: 26 %, 3: 10 %, 4: 9 %, 5: 5 %, 6: 5 %, 7: 3 %, 8: 3 %, 9: 2 %, 10+: 5 %


### B-T5. Studded System parts placed sideways or upside down, by tenth of the steps (stepped models, non-Technic)

| tenth | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| sideways (90 degrees) % (pooled parts) | 11 | 19 | 23 | 33 | 27 | 29 | 32 | 46 | 48 | 39 |
| angled % (pooled parts) | 4 | 8 | 6 | 7 | 5 | 13 | 8 | 15 | 10 | 17 |
| upside down % (pooled parts) | 1 | 0 | 2 | 2 | 4 | 1 | 1 | 1 | 1 | 2 |

Models: 36. Median per model over the whole build: sideways 24 %, upside down 0 %.


### B-T6. When wheels, hinges and other moving parts go on (stepped models): position in the build as a share of parts placed (0 = first part, 1 = last)

| kind | models that have it | median first appearance | median of each model's median position |
|---|---:|---:|---:|
| wheels and tyres | 26 | 0.62 | 0.86 |
| wheel holders | 6 | 0.41 | 0.53 |
| hinges | 26 | 0.20 | 0.51 |
| turntables | 5 | 0.04 | 0.05 |
| ball and towball joints | 14 | 0.45 | 0.61 |
| clips | 37 | 0.22 | 0.62 |
| bars and handles | 37 | 0.27 | 0.65 |
| gears and other Technic | 20 | 0.39 | 0.63 |
| pin/beam | 38 | 0.03 | 0.56 |
| sideways-building parts | 37 | 0.05 | 0.42 |
| tiles | 41 | 0.05 | 0.53 |
| slopes, curves, wedges | 40 | 0.06 | 0.53 |
| plain bricks | 35 | 0.06 | 0.34 |
| plates | 40 | 0.00 | 0.45 |

### B-T7. How the model grows (stepped models)

- **non-Technic <500** (18 models): height rho median +0.32 (positive in 11 of 18 above +0.2); outward rho median +0.08 (above +0.2 in 8); non-minifigure sub-models per model median 6 (range 2-15); sub-models used more than once, median 1; share of parts built inside sub-models median 66 %.
- **non-Technic 500+** (18 models): height rho median +0.33 (positive in 10 of 18 above +0.2); outward rho median +0.01 (above +0.2 in 6); non-minifigure sub-models per model median 36 (range 7-183); sub-models used more than once, median 8; share of parts built inside sub-models median 72 %.
- **Technic** (6 models): height rho median +0.53 (positive in 6 of 6 above +0.2); outward rho median +0.33 (above +0.2 in 5); non-minifigure sub-models per model median 38 (range 6-100); sub-models used more than once, median 2; share of parts built inside sub-models median 60 %.

### B-T8. Sub-model sizes (stepped models, non-minifigure sub-models, own parts only, nested sub-models not included)

- **non-Technic <500**: 116 sub-models; own parts median 10, quartiles 4-25, largest 288; used once 86, twice 20, three or more times 7; never referenced (alternates or leftovers in the file) 3.
- **non-Technic 500+**: 1011 sub-models; own parts median 6, quartiles 3-12, largest 932; used once 676, twice 238, three or more times 97; never referenced (alternates or leftovers in the file) 0.
- **Technic**: 238 sub-models; own parts median 16, quartiles 10-34, largest 664; used once 184, twice 17, three or more times 3; never referenced (alternates or leftovers in the file) 34.

### B-T9. Is there a pin-and-beam core? Share of pin/beam parts in the first 20 % of parts placed against the whole model (stepped, non-Technic models that contain any)

| set | name | group | parts | pin/beam in first 20 % | pin/beam overall | ratio |
|---|---|---|---:|---:|---:|---:|
| 40379-1 | Bear | BrickHeadz | 149 | 7 % | 1 % | 5.1 |
| 75272-1 | Sith TIE Fighter | Star Wars (play) | 452 | 3 % | 1 % | 5.0 |
| 10252-1 | Volkswagen Beetle | Adult display (Icons/Creator Expert/UCS/Modular) | 1148 | 31 % | 7 % | 4.2 |
| 75075-1 | AT-AT | Star Wars (play) | 83 | 50 % | 12 % | 4.2 |
| 30285-1 | Tiger | Creator (other) | 73 | 57 % | 16 % | 3.5 |
| 31072-1 | Extreme Engines | Creator 3-in-1 | 109 | 29 % | 11 % | 2.6 |
| 10271-1 | Fiat 500 | Adult display (Icons/Creator Expert/UCS/Modular) | 955 | 13 % | 7 % | 1.8 |
| 60216-1 | Downtown Fire Brigade | City | 889 | 14 % | 9 % | 1.5 |
| 75966-1 | Hogwarts Room of Requirement | Harry Potter | 167 | 12 % | 9 % | 1.3 |
| 10349-1 | Happy Plants | Botanicals | 212 | 10 % | 8 % | 1.3 |
| 10264-1 | Corner Garage | Adult display (Icons/Creator Expert/UCS/Modular) | 2454 | 6 % | 5 % | 1.1 |
| 75155-1 | Rebel U-Wing Fighter | Star Wars (play) | 612 | 24 % | 22 % | 1.1 |
| 21309-1 | NASA Apollo Saturn V | Ideas | 1812 | 3 % | 3 % | 1.1 |
| 10281-1 | Bonsai Tree | Botanicals | 648 | 3 % | 3 % | 1.0 |
| 75144-1 | Snowspeeder | Adult display (Icons/Creator Expert/UCS/Modular) | 1645 | 9 % | 12 % | 0.8 |
| 21303-1 | WALL•E [Original Version] | Ideas | 678 | 13 % | 18 % | 0.7 |
| 31045-1 | Ocean Explorer | Creator 3-in-1 | 210 | 2 % | 3 % | 0.7 |
| 10283-1 | NASA Space Shuttle Discovery | Adult display (Icons/Creator Expert/UCS/Modular) | 2290 | 8 % | 14 % | 0.6 |
| 10280-1 | Flower Bouquet | Botanicals | 735 | 12 % | 22 % | 0.5 |
| 10298-1 | Vespa 125 | Adult display (Icons/Creator Expert/UCS/Modular) | 1086 | 2 % | 8 % | 0.3 |
| 31084-1 | Pirate Roller Coaster | Creator 3-in-1 | 886 | 1 % | 5 % | 0.2 |
| 75954-1 | Hogwarts Great Hall | Harry Potter | 777 | 1 % | 3 % | 0.2 |
| 31153-1 | Modern House | Creator 3-in-1 | 908 | 1 % | 5 % | 0.2 |
| 21036-1 | Arc de Triomphe | Architecture | 382 | 0 % | 4 % | 0.0 |
| 21046-1 | Empire State Building | Architecture | 1766 | 0 % | 0 % | 0.0 |
| 21319-1 | Central Perk | Ideas | 1003 | 0 % | 1 % | 0.0 |
| 31066-1 | Space Shuttle Explorer | Creator 3-in-1 | 277 | 0 % | 13 % | 0.0 |
| 40433-1 | 1989 Batmobile - Limited Edition | Super Heroes | 358 | 0 % | 8 % | 0.0 |
| 41075-1 | The Elves' Treetop Hideaway | Other themes | 480 | 0 % | 5 % | 0.0 |
| 75892-1 | McLaren Senna | Speed Champions | 204 | 0 % | 3 % | 0.0 |
| 75895-1 | 1974 Porsche 911 Turbo 3.0 | Speed Champions | 166 | 0 % | 12 % | 0.0 |
| 76897-1 | 1985 Audi Sport quattro S1 | Speed Champions | 250 | 0 % | 2 % | 0.0 |

Models where pin/beam parts are at least twice as common in the first 20 % as overall: 6 of 32; where they are at most half as common: 13.


### B-T10. Sideways and angled System parts by third of the build, median over stepped non-Technic models

| third | models | sideways (90 degrees) median % | angled median % | upside down median % |
|---|---:|---:|---:|---:|
| first | 36 | 10 | 0 | 0 |
| middle | 36 | 26 | 0 | 0 |
| last | 36 | 32 | 3 | 0 |

## Limits of each measure

- **A, part shares** count part *types*, not how a part is used; a plain brick built sideways is not
  "sideways", and a bracket used flat is. Shares are of build parts, means over sets, so small sets weigh
  as much as large ones. Polybags and small promotional sets dominate the under-150 band (median 23 parts
  of variety). Inventories are Rebrickable's, which are carefully kept but crowd-sourced. Theme groups
  are Rebrickable's tree; "Other themes" mixes many lines.
- **A, the curve** uses Rebrickable's set part count (including minifigure parts) for size, and "10
  liftarms" as an arbitrary sign of a frame. A frame can also be built from Technic bricks, which this
  does not count as a frame; and 10 liftarms can be details, not a structure (21327 Typewriter has 204,
  for its mechanism).
- **A, most-used parts** rank by number of sets, so a part used once in many sets outranks one used
  heavily in few. The wheel-mounting list is by association with wheels, not by function.
- **B, sample**: 49 models chosen by me to spread over themes and sizes, but limited to what the OMR
  holds: almost nothing after 2022 (the newest is from 2026, Botanicals 10349), only one Friends-line
  set, no Ninjago, no Super Mario, only 6 Technic. City and Creator files tend to be older or less
  finely stepped.
- **B, steps** are the OMR author's: the spec does not require them to match the booklet. Nine files
  name sub-models after booklet steps; I could not check the others. The way I unroll sub-models (a
  sub-model's steps just before the step that attaches it) matches how booklets usually show them, but
  booklets sometimes build a sub-assembly pages earlier or later.
- **B, sub-model counts** depend on how the author chose to split the file: some authors make one
  sub-model per booklet call-out, others group freely (10283 has 170). Treat counts as rough and sizes as
  more telling.
- **B, orientation** is measured against LDraw's up direction and only for studded System parts. A model
  that is displayed lying down (a wing, a picture frame) shows as "sideways" throughout.
- **B, positions** in the build are by order of parts placed; a model with large final sub-assemblies (a
  roof, a stand) shifts everything else earlier.

## What failed or was not done

- Rebrickable's HTML pages (downloads, terms) refuse plain clients with a browser check; I did not get
  round it and read archived copies instead. The CSV files themselves downloaded without trouble.
- LEGO's instructions site refused my plain client (HTTP 403). Other researchers' booklets are on disk,
  and two of their sets are in the OMR (40441 Shorthair Cats, 10297 Boutique Hotel), but this machine has
  no PDF renderer (pdftoppm, pypdf and PyMuPDF are all missing), so I could not compare OMR steps with
  booklet pages. 40441 was added to the sample because its sub-models are named after booklet steps; a
  page-by-page check is still open.
- The OMR list cannot be filtered or sorted by address, so all 59 list pages were fetched (2 s apart) to
  get the catalogue; there is no bulk download (a 2013 zip is reported broken on the LDraw forum).
- No measure here of how parts are *joined* (which stud goes into which tube), so nothing on overlap,
  locking plates or bracing; the project's checker could do that on the same OMR files with
  `bricksnap/lab/ldraw_lib.py` connectors, which I did not use (I read the library zip directly,
  read-only, for part descriptions only).

## Files

The downloaded data (nine catalogue files from Rebrickable, 59 list pages and 49 models from the OMR)
and the scripts that produced these tables were kept outside the repository and are not part of this
folder. The Method section above says how every table was made.
