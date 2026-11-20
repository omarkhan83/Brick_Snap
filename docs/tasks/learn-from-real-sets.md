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
- Started 19 November: seven researchers (five categories, a numbers study from published parts lists
  and any machine-readable models of official sets, and a survey of what designers have written).
