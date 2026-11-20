# Whatever decides how a build comes out is counted in work, never in seconds
- status: accepted
- by: Alec-42, 2026-11-19

The same model must give the same build on any computer at any load. The make-buildable pass used to
stop curing weak spots after 8 seconds; once the solver was made sturdier (and slower) a 48-stud model
reached that clock and came out differently from one run to the next. The pass is now bounded by the
parts it has solved. A clock may remain only as a far-off safety net that says so in the build's notes
when it stops something. Rejected: raising the time limit, which only moves the size at which it bites.

## Responses
