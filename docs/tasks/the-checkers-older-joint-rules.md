# The free-build checker still takes some joints on trust that it could test
- status: in-progress
- owner: Alec-42 (since 2026-11-20)
- stage: 4

On 20 November the checker stopped calling official techniques wrong (215 false problems on six
official sets fell to 18; see `docs/research/2026-11-19-how-real-sets-are-built/experiments.md`,
"After the fixes"). The independent review of that change found places where the checker is still
too easy, most of them older than the change. They were left out of it on purpose so that the fix
stayed small. A builder who is told "no problems" for one of these has a model that cannot be built
as drawn, so they matter more the more the AI builder uses clips, bars and wheels.

Done when each item below is either fixed with a test at its limit, or written into the checker's
CONTRACT as a stated limit; and the six official sets still give no more false problems than today.

## Notes
In rough order of how likely a builder is to meet them:

1. **A pair with a named joint skips the real-shape test** (`validate.py`, the `elif joint:` branch
   comes before the test on real shapes). So:
   - a clip plate (4085c) sitting 12 LDU above a handle (2540) and gripping nothing is "joined": the
     handle's length is taken along the primitive's own axis, not the bar's direction;
   - two "Bar Tube with Handle" (23443) placed 2 LDU apart pass although their real shapes share a
     piece 3 LDU thick; a bar tube moved 4 or 8 LDU off its bar is still a joint;
   - a wheel moved one stud off its pin sits through its own tyre and passes; a wheel-and-tyre part
     placed twice 10 LDU apart passes.
   The fix is probably to run the real-shape test on these pairs too, allowing only what the joint
   itself needs to share.
2. **Wheel pins are judged by nearness.** A part with a wheel pin moved a whole stud is missed about
   a third of the time (68 caught of 102 in the reviewer's run; 38 of 102 when moved 4 LDU).
3. **A part moved 1 LDU into its neighbour is not caught** (82 of the reviewer's 3,339 changes, the
   largest single loss of the fix). On 0.5 LDU cells a 1 LDU overlap looks the same as two faces
   touching. Two bricks overlapping sideways by 1.1 or 1.2 LDU also pass. Finer cells only for pairs
   the filled bodies flag would close it.
4. **A bar sunk 2 to 6 LDU into a solid top** is reported, but as "Loose ... There is no part under
   it", not as an overlap; from 12 LDU it is an overlap. The words should say the bar is inside the
   part.
5. **Parts the overlap test cannot see:** 106 of 5,640 indexed parts are nowhere 1.5 LDU thick (ribbed
   hoses, capes, sails, plastic sheets), so they can never raise an overlap. They are still reported
   loose.
6. **A solid that is wrong:** the wall of friction pin 11214 is not filled in its middle section, so
   the pin can read as "a bar in a pin hole".
7. **Studs in pin holes:** a stud 2 LDU short of the hole's face is joined.
8. **Bars judged on a short span:** a short bar's lean can only be measured over the length that is a
   bar, so a short bar off its axis may pass.
9. **What is still falsely reported on the six sets (18):** irregular sockets (5), a T-piece the
   library records no joint for (with the steering wheel on it), five shields, two plant groups
   resting on a handle, and a round plate on a bracket with what stands on it. On the wider 18
   models (226): an axle pin in a domed cylinder whose library shapes share 3 LDU (40433), and a
   rotor under a curved slope and a jumper under a plane's nose that sit half a stud off the grid
   (75892, 60067).
10. **A pin in a pin hole is found only at the pin connector's own point.** In 10349 two long axle
    pins (11214) sit in Technic bricks and that joint is not listed at all; they are held through
    their axle ends.
11. **A bar drawn as a tube** counts as a bar when 6 of 8 points round the axis are solid. No test
    can tell 6 from 1, because the centring rule refuses the same cases first.
12. **Movement:** a declared wheel on an axle is refused ("the checker cannot yet confirm how an axle
    turns: use a module instead"), as are clips, bars, finger hinges and balls. A clip on a bar as a
    proven module is the first one worth adding (see `movement-first-models.md`).

The reviewer's cases and pictures are on the lead's machine under
`~/.cache/bricksnap/research/review-work/` (not in the repository: they include files of official
sets from the community's LDraw collection).
