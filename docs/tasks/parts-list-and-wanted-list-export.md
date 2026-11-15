# Export a parts list and a BrickLink wanted list
- status: open
- owner: nobody
- stage: 2

From a Build, write `parts.csv` (part number, name, colour, quantity) and `wanted_list.xml` in BrickLink's
upload format (an `INVENTORY` of `ITEM` entries with `ITEMTYPE` P, `ITEMID`, `COLOR` as a BrickLink colour
ID, `MINQTY`; no XML declaration line). Lives in `bricksnap/export.py`.

Done when the XML for the pawn uploads on BrickLink's wanted-list page without a rejected item.

## Notes
Starts after `stage-1-foundation`. The upload test needs a person with a BrickLink account. Format
reference: https://www.bricklink.com/help.asp?helpID=207
