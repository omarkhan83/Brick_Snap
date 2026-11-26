# The checker warns when clips carry more than a thin member, even where official models do it
- status: accepted
- by: Alec-42, 2026-11-25

A group of parts that reaches the ground only through clip grips, and carries more than a 2 x 4 brick's
volume per clip or more than a 1 x 8 blade's leverage on one clip, gets a warning that names the parts
and says the checker cannot judge whether clips will carry that much. It is a warning, never a problem.
Three official models trip it (75075, 31066, 40433) and it was kept on purpose: the AI builder cannot
test a model in its hands as a set designer can, so the checker says what it cannot vouch for. Rejected:
raising the limits until no official model trips it (then a table on clip legs passes silently), and
warning only on AI builds (the same model would read differently by who made it).

## Responses
