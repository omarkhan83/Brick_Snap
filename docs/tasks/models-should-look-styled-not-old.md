# Free builds should look styled, like a modern designed model, not like an old set
- status: in-progress
- owner: Alec-42 (since 2026-11-20)
- stage: 4

Alec, 20 November, after building a Cessna 172 with the AI builder (206 parts, guide on, checker clean):
"Most importantly for me is the style ... it looks old - it looks like an old lego set and isnt styled
quite right." He sent pictures of a fan-made Cessna with many more parts as the bar. This is now the
first priority for the AI builder: a build that passes every check and still looks dated has failed.

Done when the same subjects built before and after this work are clearly more styled to Alec's eye
(the Cessna first), and the measures of point 2 move toward what modern official sets show.

1. **A study of style**: what makes a model look modern and designed rather than old, from numbers (how
   the mix of parts and colours in sets changed over the years), from what designers and builders have
   written, and from our own builds measured against official models. `docs/research/`, with a style
   guide in plain imperative sentences as its result.
2. **Measures of style** that a program can report on any model, so the builder gets them in every
   check and we can see progress: studs left showing, the palette, how much of the surface is tiles and
   curved slopes, parts built sideways, thick members where the real thing is thin, how recent the parts
   are.
3. **Art direction before building**: the builder first writes a brief (the scale that lets the
   subject's shapes be sculpted, a livery of two or three colours with a pattern, the three to five
   shapes that make the subject, where it builds sideways), then builds, then looks at its pictures
   against the style rules and revises before it submits.
4. **The checker must not punish the techniques style needs.** The builder of the Cessna wrote that it
   "first built [the wing struts] as bars in clips, which looked finer, but the checker reported them
   loose", and used thick Technic beams with holes instead. Bars in clips at an angle, hinged and angled
   sections, and clear panels have to be buildable and checkable.
5. **Bigger models.** The builder stopped at 206 of the 300 parts asked for and said why: "closing the
   gap properly would take a 6-wide fuselage with opening doors and a lift-off wing". The form allows at
   most 300 parts and one AI session; a model with the presence of Alec's example needs more parts and
   probably building in sections.

## Notes
- What "old" looks like in the Cessna of 20 November, against the example: white with primary blue and
  red and a straight stripe (the palette of 1990s town sets) where the example has dark blue, ochre and
  white swept diagonally; a fuselage 4 studs wide made of stacked plates, so flat slab sides, where the
  example's is built sideways with curved slopes and a rounded belly; tinted brown bricks and 45-degree
  slopes as glazing where the example has raked clear panels in frames; Technic beams with holes as
  struts where the example has thin bars; bare small wheels where the example has spats. Its wing is the
  part that already looks modern: curved slopes along the leading edge, tiled, with wing plates at the
  tips.
- The example is another builder's design: it sets the bar for qualities; it is not to be reproduced,
  and its pictures do not go into the repository.
- The comparison of builds with and without the structural guide (`learn-from-real-sets.md`, point 3) is
  set aside for this: that guide is about how a model is put together, and Alec's judgement is about how
  it looks.
- Real AI builds to test this spend Alec's Claude subscription: state the count and the cost and ask.
- 20 November, point 3 built (branch `wip/Alec-42-art-direction`, not yet merged; no real build
  has used it). With the guide on ("Design it first, then build it the way set designers do"):
  the style guide is carried as `bricksnap/lab/style.md` (held equal to the study's file) and
  read by `lab/style.py`; the instructions gain "# Art direction" with the thirteen rules of
  finish; `playbook` also hands over the style guide's section for the subject (Aircraft or Car
  by its words); a `brief` tool takes the eight lines of the art direction before the first
  part (form checked: all eight, colour codes real, at most three body colours unless
  `why_more`); `submit` takes the critique (ten yes-or-no answers, a note for each no, only
  after a `look` since the last change). Each refusal happens once (`lab/art.py`). Runs keep
  the brief and critique; the free-build page shows "The AI's art direction" and "Its own
  critique". The structural guide's rules 5 and 9 gain a sentence letting a thin member hang
  on one clip. For every build, the colour list is fuller and names 10375 trans black as the
  glass smoke (the guide-off pin changed for that one line). Point 5 in part: up to 600 parts,
  with turns, checks and time growing with the parts asked for (`freebuild.limits`), and the
  form's time words come from the runs on record (`freebuild.minutes`).
- 20 November, after an independent review of that branch (both other branches merged in):
  the scale is now the largest the parts asked for will pay for; the structural guide has an
  Aircraft playbook; the critique answers a hand-in sheet (three views, the brief, colours as
  seen against the brief's, size, parts, glass, HOW IT LOOKS) and a first "no" is sent back to
  rebuild once; every change to the model file counts, whatever the tool said; a change run
  builds to the model's brief; the page puts the pictures first and says what happened (late
  or changed brief, no brief, no critique, changes after it). Claude Code's --max-turns limits
  replies, not tool calls (the Cessna's 102 tool calls came in 43 replies): the limit is now
  0.35 replies a part, at least 90, and each session records its replies. The form and the
  agreement say the usual time, when it is stopped and what builds that size have used of the
  subscription.
- The reviewer recommends a second, independent critic: a separate AI session shown only the
  hand-in sheet (pictures, brief and counts), not the builder's reasoning, answering the ten
  questions. Its reason: a builder grading its own work tends to say yes, and the counts can
  only contradict the questions that can be counted (colours, size, glass), not outline,
  proportion or finish. Not built: it is a second paid call, the owner's decision.
- Left: real builds with Alec's yes (the Cessna first) to see whether the brief, the hand-in
  and the rebuild change what comes out, and how many replies a 300- and 600-part build uses;
  building in sections for models beyond one session (point 5); whether a bar in 11090 still
  "reads as loose" (style rule 8 says so; the joints branch now tests bar tubes).
- 21 November, paused for the night with two branches unfinished and unmerged (point 4: the
  checker and the tools must not punish style techniques). Both are on GitHub; neither has
  been through the full checks since its last commits, so neither is on `main`.
  - `wip/Alec-42-thin-members` (tip 2d0f64c): a bar in a bar tube (11090, 23443) and a clip
    on a bar or handle are tested for fit, with each clip's grip found in its real shape; two
    builder tools with the guide on, `clip` (a clip on a bar at any angle) and `strut` (a bar
    between two handles); a warning when clips carry more than a thin member; style rule 8
    rewritten in both copies. Reviewed twice. The second review's three remaining points are
    committed (stored grips keyed by the library, the load warning, two small tool replies)
    but not yet measured: the must-hold numbers (18 official models 226 problems, no official
    clip or bar-tube fit lost, stored builds unchanged but for the Cessna's third attempt, no
    mutation catch lost) and the whole test run are still owed on that tip.
  - `wip/Alec-42-style-techniques` (tip 2bbaca0, built on thin members at 5039120): every
    technique the style guide teaches is a test (`tests/test_lab_style_techniques.py`). Fixed
    from what those found: a stud beside a wedge plate's cut corner or under a windscreen is
    no longer a "no socket" problem (35 false problems gone from the official models, 226 to
    191); 16 parts, wings among them, sit on the stud grid; `place` offers only sockets a
    stud can enter, says when another turn would catch more studs, and with the guide on
    turns a part on one stud by an angle; three wrong part descriptions and the aircraft
    body's width in the style guide. The second review blocked on two things, both committed
    since: the hinge-line rule is withdrawn (it called a correct locking hinge a problem) and
    the socket test asks the drawn surface (it had dropped true sockets on 66 parts, 4595
    among them). Still to do there: pin or remove the stud-test constants the review found
    unpinned (STUD_CORE_R, STUD_MIDDLE_R and its count, STUD_CORE_H, HALF_STUD_TOL); the
    notes it was asked to log; check the angle and guide-off parts of its last commit are
    complete; merge thin members' new tip; the must-hold numbers (191 and 13, every one of
    the 11,335 seated studs in the official models and library assemblies still offered its
    socket, no mutation catch lost) and the whole test run.
  - Then: a short third review of only what changed since 9c98c4d, the squash merge of the
    techniques branch (it contains thin members) through the full checks, and the task
    file `the-checkers-older-joint-rules.md` on those branches carries what is left over.
  - Decided on the way, to record as a decision when it merges: the clip-load warning stays
    though three official models trip it, as a warning that says what the checker cannot
    judge, never a problem.
- Still waiting for Alec's yes: rebuilding the Cessna with the art direction (300 parts,
  600, both or neither). No AI build has been made since the art direction went in.
- 25 November: both branches above are merged (squashed into one commit on `main`) after a third,
  independent review and the whole test run on the combined branch (3,938 passed). From the third
  review: `place` no longer offers the extra checker-grid cells (half went into tube walls; logged in
  `the-checkers-older-joint-rules.md`), and the clip-load warning measures reach from the grip, on
  groups held by several clips, and carries hanging weight to the clips nearer the ground. The owner
  then gave standing leave to run AI builds (25 November) and set the direction: one prompt bar, words
  or pictures in, the AI builds it; see the decision of that date.
- 26 November, overnight: real AI builds on Opus 5.5 (Fable's allowance was spent) drove these changes,
  now on `main`: a session gets one reply per part asked for (builds were running out at 60%); a first
  hand-in under three quarters of the parts asked is sent back once; HOW IT LOOKS says where the flanks
  are stacked and the hand-in sends back once on it; guide-mode tools `cap` (tiles or curved slopes over
  free studs), `skin` (a tiled panel on side studs) and `fill` with `sides` (a core ready for skins);
  `place` swaps old part numbers, refuses a covered stud, says which way a slope falls; window glass in
  its frame and a steering wheel on its peg are held; "polish": an outside critic shown only the
  pictures lists up to five fixes and one change makes them (`make --polish`, a button, an option).
  Builds of the night and their pictures: `~/.cache/bricksnap/research/overnight/` on the lead's machine.
  Left: aircraft still read boxy (best: 436 parts at 600 asked); studs seen through canopies; whether
  `skin` gets used (the builders mostly did not call it).
