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
