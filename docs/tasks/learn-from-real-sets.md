# Study how real sets are built, and turn it into a guide the AI builder follows
- status: in-progress
- owner: Alec-42 (since 2026-11-19)
- stage: 4

Alec's idea, 19 November: many official sets start from a core (often beams and pins), a botanical set
does it in another style, "but they all start with a core". Rather than invent a method, study how real
sets are built across categories (Technic, vehicles, botanicals and animals, buildings, characters and
sculptures) from LEGO's own instruction booklets, and write down the patterns as a guide.

Done when:

1. `docs/research/` has a study with the evidence: for each category, what is built first and what kind
   of core it is, how it is made strong, how the outside attaches, what is built separately, where the
   moving parts sit, and what changes with size; plus numbers across many sets (when a pin-and-beam
   core appears outside Technic) and what designers themselves have written about their rules.
2. There is a guide in plain imperative sentences, one playbook per category and size, that the AI
   builder can be given (through its instructions or a tool that hands it the playbook for the subject).
3. The same subjects built with and without the guide are compared (pictures and a blind judge), and
   the guide is kept only where it helps.

## Notes
- The instructions and the sets' designs are LEGO's. We learn techniques and describe them in our own
  words; no instruction pages, images or step-by-step transcriptions go into the repository, and the
  builder is never asked to rebuild a specific set.
- The checker cannot yet confirm pin-and-beam joints (it lists them as "not checked"), so a beam frame
  is not something a free build can have verified today. The movement work (`movement-first-models.md`)
  made it able to confirm a pin's own line; confirming a pin in a hole is the natural next step if the
  study shows such cores matter at our sizes.
- Point 3 needs real AI builds, which spend Alec's Claude subscription: ask him first and report the
  count.
- 19 November: points 1 and 2 are done as far as reading goes. The study is
  `docs/research/2026-11-19-how-real-sets-are-built/README.md` (32 official sets read from LEGO's own
  instruction files by six researchers, counts over 5,935 sets' parts lists and 42 models' building
  order, and what designers have published); the draft guide is `guide.md` beside it: twelve rules for
  any subject and ten playbooks (five kinds of subject at about 100 and about 400 parts). The answer to
  the question that started it: every set starts with a core, but beams and pins are one kind among
  five and are not used at our sizes; ours are a plate base, a block of side-stud bricks with panels
  pressed on sideways, walls under a lid, and a spine.
- The guide is NOT yet given to the AI builder. Left: point 3 (the same subjects built with and
  without it: eight AI runs, which need Alec's yes), and the study's experiments that need no AI run,
  in its section "Experiments to run next": measure the AI-built models we have against the rules; run
  our checker on the community's LDraw files of small official sets; one sideways face on a converted
  model, by hand; a roof that lifts off as a declared moving thing; a clip on a bar as a proven joint;
  and reading two more booklets where the playbooks rest on thin evidence.
- 19 November, two experiments with no AI build (`experiments.md` in the study's folder). (1) Our
  checker does NOT pass official sets: about one false problem per five parts on six small sets on
  sale (215 on 985 parts), none of them at a side stud (442 sideways stud joints were confirmed). Most
  come from four causes: parts that only touch counted as overlapping (curved slopes over a plate's
  end, plates against a bracket's flange: 77), a bar pushed into an open stud or another hollow (60),
  axles read as holes (27), and the stud grid taken from the bounding box of parts with a cutout (19).
  A model built in the guide's style would be told its curved slopes are wrong, so the checker has to
  be fixed before the guide is tested with AI builds. (2) The guide has something to teach: in the
  AI's 20 existing builds 3% of studded parts face sideways against 27% in 18 official models; wheels
  go on a tenth of the way through against last; the core is always the very bottom. It already
  mirrors and already prefers larger parts.
- 20 November, experiment 4 (`experiment-4-one-sideways-face.md`): on three models the converter made
  at 16 studs, one face was rebuilt by hand with the builder's tools as a flat panel on side studs.
  By the builder's own eye: clearly better on the cat, about the same on the car's nose, worse on the
  duck (a flat board on a round head; the beak reads as teeth). Not the clear win the study asked for
  before teaching the converter to leave side studs; Alec has the pictures to judge blind. What it did
  show: a panel needs a flat face of about 6 by 4 studs on a boxy shape, a plate running back into the
  body, clear depth in front, and tiles under its bottom edge; a round head needs a whole core with
  panels, which is the AI builder's kind of work, not the converter's.
- Alec decided on 19 November that statistics worked out from Rebrickable's catalogue may be used in
  the guide, with credit (see the decision of that date).
- 20 November: the guide can now be given to the AI
  builder, behind a switch, for point 3. The builder's copy is `bricksnap/lab/guide.md`, held
  byte-equal to the study's `guide.md` by a test (change both together); `bricksnap/lab/guide.py`
  reads it by its headings. `run.build(..., guide=True)`, `python -m bricksnap.lab.run --guide`,
  `bricksnap make "..." --guide`, and a tick box (in plain view since 20 November) in the web app's
  free-build form (off by default; the model remembers it, so its changes keep it). With the
  guide on, the builder's instructions get the twelve rules (without their bracketed sources),
  a working order rewritten as one method, a paragraph on panels, and a `playbook` tool that
  hands it the nearest playbook; the closing words must say which playbook it followed. With
  it off, the prompt and the tools are byte for byte what they were (pinned by tests). Each
  run records whether it had the guide and which playbook it asked for; the page shows both.
- Panels work with today's `place`: a 2 x 4 plate on the side studs of two 1 x 1 side-stud
  bricks (87087), then tiles and curved slopes on its studs, passes the checker (the example
  is the last test in `tests/test_guide.py`). In guide mode only, `place` lists a sideways
  part's studs in its reply. A side stud of a side-stud brick is 10 LDU below its top, so a
  two-stud panel's edges sit half a plate off the core's plate lines; a bracket's (99780) do not.
- 20 November, the first build with the guide (a sitting cat, 96 parts, playbook "Creature, character
  or sculpture, 100 parts"; Alec asked to see one): clean, but not better than the 78-part cat built
  without the guide the day before. The builder's own notes say why: the checker called the curved
  slopes it tried (93273, 11477) overlapping, so it fell back to plain slopes; it put the tail on
  studs to avoid a joint the checker could not confirm; and it chose not to build the core of
  side-stud bricks. So that run tested the old checker more than the guide.
- 20 November, the checker's false problems are fixed (experiment 3's four causes; the numbers are in
  `experiments.md`, "After the fixes"): 215 false problems on the six official sets fall to 18, and
  1,000 to 226 over all 18 models. Parts that only touch are not an overlap; a bar in an open stud or
  another hollow is a joint listed as not checked; axles are axles; parts with a cutout underneath
  take their stud grid from their sockets, and `place` seats them there. The curved slopes above now
  place and check clean at all four turns. What it costs: a part moved 1 LDU into its neighbour is no
  longer caught (the real shapes cannot tell that from touching). The older lenient rules (wheel pins,
  clips and bar tubes by name) are untouched: see `the-checkers-older-joint-rules.md`.
- Left: point 3 itself. First the same cat and a car again with the guide on, now that the checker
  no longer argues with the guide (Alec said on 20 November to keep going); then the full comparison
  (eight AI runs, four subjects with and without, judged blind), and the study's experiments that
  need no AI run. If the builder still skips the core of side-stud bricks, the guide's wording about
  the core has to become firmer before the comparison means anything.
