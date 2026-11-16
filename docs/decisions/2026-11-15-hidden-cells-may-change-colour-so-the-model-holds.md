# Cells nobody can see may change colour so that the model holds together
- status: accepted
- by: Alec-42, 2026-11-15

A part has one colour and parts hold each other only vertically, so a feature in its own colour stuck on
the side of a model (a nose on a face) has nothing holding it. The make-buildable pass continues that
colour into cells that are hidden once the model is built, which lets the feature's parts reach into the
body. It never recolours a visible cell and never empties one, it works on a copy inside each rebuild, and
it reports what it did in the build's notes. Rejected: asking the AI designer to do this by hand (it
learned to, but it costs a round of edits every time) and teaching the solver "any colour" cells (a much
riskier change to the part of the code that guarantees the model holds).

## Responses
