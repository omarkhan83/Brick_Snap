# In a free build, what moves is declared in the file, and the checker only believes a joint it can confirm
- status: accepted
- by: Alec-42, 2026-11-19

A model says what moves in comment lines of its LDraw file (`0 !BRICKSNAP JOINT ...`), so BrickLink
Studio and LeoCAD still open it unchanged. A joint counts only when it is one of the proven moving
modules (its parts and its turning line checked against the parts library) or a joint whose line the
library itself records (a wheel pin, a Technic pin, the hinge brick's pin). The check then turns the
moving parts through their whole range against the real shapes of everything else, studs and the
ground included. Rejected after an independent review showed each to certify movement that could not
happen: taking the builder's word for a turning line, reading a clip's line from the shape of its
surface, and testing with the parts' rough outlines without their studs. Clips, bars, finger hinges,
ball joints and axles cannot be declared yet; they need a proven module first.

## Responses
