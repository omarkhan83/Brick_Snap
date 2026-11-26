# An outside eye that sees only the pictures writes a free build's fixes, and polishing after a build is off by default
- status: accepted
- by: Alec-42, 2026-11-25

The builder grades its own work leniently, while a reviewer who saw only the pictures wrote four fixes
that one change run made in one go and the model looked clearly better. So "polish" is a second
clean-room session (`bricksnap/lab/critic.py`) shown the pictures, the words, the brief, the reference
pictures and the HOW IT LOOKS numbers, never the builder's transcript, notes or self-critique; its list
becomes the words of one change. "Polish once after building" on the home page is off by default and says
its cost, because it roughly doubles what a build uses of the subscription. Rejected: giving the critic
the builder's reasoning (it would inherit the leniency), and polishing every build by default.

## Responses
