# Colours are matched by how they look, not by distance in RGB
- status: accepted
- by: Alec-42, 2026-11-15

A model's colours are snapped to the nearest colour in the parts table using the CIEDE2000 colour
difference, the standard measure of how different two colours look, with lightness counted half (the 2:1:1
weighting used for textiles) so that hue decides first, as it does when a person picks a brick. What each
alternative got wrong on our own test models: the prototype's weighted RGB distance turned black into Dark
Brown; plain distance in CIELAB turned a strong blue into purple; CIEDE2000 with equal weights turned the
sample car's coral red into Nougat, a skin-tone brown. `tests/test_foundation.py` pins those cases.

## Responses
