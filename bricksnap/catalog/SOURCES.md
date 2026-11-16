# Where the parts and colours table comes from

The scripts that built `parts.json` and `colours.json` are in `tools/catalog/` at the top of the repository.
They need about 150 MB of downloads, which are not committed.

Built 2026-11-15. Every value comes from files downloaded during that run (kept in `downloads/`, not committed). Regenerate with:

```
sh tools/catalog/download.sh <work_dir>          # downloads + unpacks everything
python3 -I tools/catalog/build_catalog.py <work_dir>/downloads/ldraw/ldraw <work_dir>/downloads/rb <work_dir>/downloads/web <work_dir>
```

`build_catalog.py` also writes `build_report.json`, which lists warnings and the colours it dropped.

## Sources actually read

| Key | Source | What was used |
|---|---|---|
| LDRAW | `https://library.ldraw.org/library/updates/complete.zip` (LDConfig.ldr `UPDATE 2026-05-29`) | part files, sub-files and primitives (`parts/`, `parts/s/`, `p/`, `p/48/`); `LDConfig.ldr` |
| RB | Rebrickable CSV dumps `colors`, `parts`, `elements`, `part_relationships` (`cdn.rebrickable.com/media/downloads/*.csv.gz`) | part ids and names, colour ids, names and years, real part+colour elements |
| BLC | BrickLink colour guide `https://www.bricklink.com/catalogColors.asp` | BrickLink colour name to colour ID |
| BLP | BrickLink catalog pages `https://www.bricklink.com/v2/catalog/catalogitem.page?P=<id>` (`downloads/web/bl_parts/`) | whether an id is a primary BrickLink item, its name, and its "Alternate Item No" list |
| SETDB | Merlin's Bricks SetDB colour table `https://www.merlinsbricks.com/colors/` | one row per colour with BrickLink, LEGO, Rebrickable and LDraw ids |

Rebrickable's website and API were not usable. `rebrickable.com/colors/` returned 403, `/downloads/` returned 402, and the API needs a key. So Rebrickable's own `external_ids` colour mapping was **not** used.

## parts.json fields

| Field | Source and derivation |
|---|---|
| `id`, `ldraw_file` | LDRAW file stem. I checked that each file exists and is not a `~Moved to` stub. |
| `name` | LDRAW first header line, verbatim (LDraw's double spaces are kept). |
| `bricklink_id`, `bricklink_name`, `bricklink_alternates` | BLP. Candidate ids are tried in this order: the LDraw `!KEYWORDS BrickLink <id>` (when present), the Rebrickable id, the LDraw stem, then the stem without its trailing letter. The first id with a real catalog page wins. `bricklink_lookup` records every attempt. A `b`-suffixed id returning HTTP 302 is not a primary BrickLink item (the redirect was not followed). |
| `rebrickable_id`, `rebrickable_name` | RB `parts.csv`. I checked each id exists, and checked it against the LDraw `!KEYWORDS Rebrickable` value where one exists. |
| `kind` | Assigned by hand from the LDraw/BL names (the vocabulary from the request). |
| `bbox_ldu` | LDRAW, full recursive expansion through every type-1 reference with transforms applied. Includes all vertices of line types 2/3/4 and both endpoints of type 5. Excludes nothing; studs are included. |
| `body_bbox_ldu`, `h_ldu`, `h_plates` | The same expansion minus the geometry under male stud primitives (`stud.dat`, `stud2a.dat`, `stud10.dat`, `stud15.dat`, ...; full list in `ldraw_geom.MALE_STUD_RE`). `h_plates = h_ldu/8`, rounded to an integer when within 0.1 (54200/85984 are 15.6 LDU, giving 2). |
| `sx`, `sz` | Body bbox extent in X and Z divided by 20, rounded. One override: 60897's clip sticks out to z=-24.03, so its footprint is set to the 1x1 plate (noted in `origin_note`). |
| `origin_note` | Computed from where (0,0,0) sits relative to the footprint and body. **Note:** the origin is not always the centre of the top face. 54200, 85984 and 11477 have their origin on the *bottom* face. 3040b, 3665b and 4286 have it at the centre of the stud cell, not the footprint centre. |
| `studs_top` | Positions of upward-facing male stud primitives at the top-face height, as integer `[ix, iz]` cells from the footprint's min-x/min-z corner. |
| `studs_top_offgrid` | Studs that are not on the cell grid, in cell units, where a cell centre is `i + 0.5`. 15573 has `[0.5, 0.0]` (centred jumper stud) and 4740 has `[0.5, 0.5]`. |
| `studs_side` | Horizontal stud primitives: direction, cell, y and primitive name (87087, 4733). |
| `stud_primitives` | Count of each stud primitive found. `stud2a` means an open/hollow stud. |
| `has_bottom_antistuds`, `bottom_cells` | Geometric heuristic: the outline of the geometry within 0.5 LDU of the lowest point must cover every footprint cell. It is not a clutch simulation. 3665b covers only cell `[0,1]`, so false. 11477 covers only `[0,0]`, so false: in the LDraw file the underside of the tall half is recessed to y=-8. |
| `slope` | From the triangle normals of the expanded mesh. BFC winding is honoured (CERTIFY, INVERTNEXT, negative determinant), and the sign is set by the mesh's signed volume. Upward (`slope`, `curved_slope`) or downward (`slope_inverted`) non-axis faces are grouped by dominant horizontal direction, and the group with the largest area wins. `low_side` is the direction the sloped surface descends toward. `thin_side` is the side where the body is thinner (equal to `low_side` for normal slopes, opposite it for inverted ones). `angle_deg` is the area-weighted angle from horizontal. `angle_range_deg` gives min/max (meaningful for 11477). `nominal_angle_deg_in_ldraw_name` is parsed from the name. A sanity check confirms no top stud sits on the low end. |
| `colours` | RB `elements.csv`: every (part_num, color_id) pair for the Rebrickable id, mapped to LDraw codes through colours.json, and limited to the final colour list. |
| `ldraw_license`, `ldraw_author` | LDRAW part header (needed for attribution). |
| `requested_as` | What the request listed. |

## colours.json fields

| Field | Source |
|---|---|
| `bricklink_id`, `bricklink_name` | BLC, exact name match. |
| `ldraw_code`, `rebrickable_id` | SETDB row with the same BrickLink name. |
| `name`, `rgb`, `alpha`, `transparent`, `lego_id` | LDRAW `LDConfig.ldr`: `!COLOUR` line, `VALUE`, `ALPHA`, and the `// LEGOID` comment above it. `transparent` is true when ALPHA is present. |
| `rebrickable_name`, `rebrickable_years` | RB `colors.csv`. |
| `current_production` | RB `y2` ≥ 2025, i.e. the colour appears in sets that recent. All 36 solids pass, so none were dropped. |
| `num_parts_available` | Count of parts.json records whose `colours` include this code. |
| `checks` | Cross-checks per colour: BLC id = SETDB BrickLink id; LDraw code exists; Rebrickable id exists; RB name = BL name; RB vs LDraw RGB distance < 90; LDraw name ≈ BL name; SETDB LEGO id = LDConfig LEGOID. |

Every colour passes every check except one name mismatch: Dark Purple is LDraw 85 `Medium_Lilac` (LEGO 268 Medium Lilac). That is expected; the ids agree in every source.

So each BrickLink colour ID is confirmed by two sources (BLC by name, SETDB by row), and the LDraw code is confirmed through the LEGO colour number in both SETDB and LDConfig.

Transparent colours: Trans-Clear is always included. The other three were picked by availability across our parts: Trans-Light Blue 34, Trans-Red 30, Trans-Yellow 30. Dropped: Trans-Dark Blue 28, Trans-Orange 25, Trans-Green 24.

## Corrections to the candidate lists

| Candidate | What is right |
|---|---|
| Plate 1x2 `3023` | `3023.dat` is a `~Moved to 3023b` stub. Use **3023b.dat** (BL 3023, RB 3023). |
| Tiles `3070b`, `3069b`, `3068b` | LDraw and RB ids are correct, but the **BrickLink ids are 3070, 3069, 3068**. The b numbers redirect, and BL lists them as alternates. |
| Round brick `3062b` | LDraw/RB 3062b, **BrickLink 3062**. |
| Slope `3040b` | LDraw/RB 3040b, **BrickLink 3040**. The LDraw keyword agrees, and `3040b` has no BL page. |
| Inverted slope `3665` | `3665.dat` is a stub moved to 3665a. Two LDraw files exist: 3665a (without inner stopper ring) and **3665b (with stopper ring)**. Both are keyworded BL 3665 / RB 3665. Chose **3665b.dat**. |
| Round plate `4073` | LDraw renamed it to **6141.dat** (2014). Rebrickable uses **6141**, BrickLink **4073**. The open-stud variant is BL/RB 85861 and is not included. |
| Round brick 2x2 `3941` | `3941.dat` is "without Reinforcement" and has no BL/RB keyword. **6143.dat** ("Reinforced") is keyworded BL 3941 / RB 3941, and BL 3941 lists 6143 as an alternate. Chose **6143.dat** (BL 3941, RB 3941). |
| Cone `4589` | 4589 is the old mould without the top groove. The current mould is **LDraw 59900 / RB 59900 / BrickLink 4589b** "Cone 1x1 with Top Groove", found in more colours (50 Rebrickable colours vs 42). Replaced. |
| Plate 1x1 with clip | Chose **LDraw 60897 "Plate 1x1 with Clip Vertical (Thick C-Clip)" = BrickLink 4085d = RB 60897**, the current vertical clip. The horizontal one (61252) is not included. |
| Jumper `15573 or 3794` | `3794.dat` is a stub moved to 3794a (no groove). Chose **15573** (BL/RB 15573, LDraw 15573.dat), found in 42 Rebrickable colours vs 18 for 3794b. |
| Slope angles | LDraw calls 4286 "Slope 33" and BL "Slope 33 3 x 1", but its geometry measures **26.57°**. 54200 and 85984 are "30" in BL/RB and "31" in LDraw; they measure **30.96°**. |
| Colour "Dark Purple" | Its LDraw name is **Medium_Lilac** (code 85). |
| Colour "Olive Green" | The **Rebrickable id is 326, not 330**; LDraw is 330. Rebrickable colour ids do not always equal LDraw codes. |
| Colour "Trans-Light Blue" | LDraw **43**, Rebrickable **41**. LDraw 41 is Trans_Medium_Blue. Trans-Orange (dropped) is LDraw 57, RB 182. |
| Licence | Most LDraw parts are now **CC BY 4.0**, not 2.0 (see below). |

## Not verified (stated plainly)

- **Rebrickable's licence or terms of use.** I could not read them: the site returned 403/402. Check `https://rebrickable.com/downloads/` and the API terms yourself before redistributing the RB-derived fields (`rebrickable_*`, `colours`, `num_parts_available`, `current_production`).
- **Rebrickable's own LDraw/BrickLink colour mapping (`external_ids`) and Studio's colour table.** Neither was available. The colour mapping relies on SETDB (a third-party site) plus BLC and LDConfig cross-checks.
- **Part availability is not current availability.** `colours` comes from element ids ever assigned, which include retired element/colour pairs. BrickLink-side availability was not checked.
- **`current_production` for colours** only means a set released in 2025 or later uses the colour (per Rebrickable). It is not an official LEGO status.
- **Which 1x1 round plate is current** (6141/4073 solid stud vs 85861 open stud) was not established. Likewise 3665a vs 3665b, beyond the LDraw file dates.
- **`has_bottom_antistuds`** is a geometric heuristic, not a clutch simulation. The 11477 result (recessed underside under the tall half) comes straight from the LDraw geometry but has not been checked against a physical part or photo.
- **BrickLink `b` ids** (3023b, 3040b, 3062b, 3068b, 3069b, 3070b, 3665b, 6141, 6143, 59900, 60897, 2412) returned HTTP 302 and the redirects were not followed. Most appear in the alternates list of the chosen item; 3023b, 3040b, 3665b and 2412 do not.
- **RGB values** are LDraw's LDConfig values, not official LEGO values.

## Licence and attribution

**LDraw-derived data** comes from the LDraw.org Parts Library (`CAreadme.txt`). Each part is licensed under CC BY 2.0 and/or CC BY 4.0 according to its `!LICENSE` header. Our 50 parts: 49 are "CC BY 4.0" and one is "CC BY 2.0 and CC BY 4.0". Each record carries `ldraw_license` and `ldraw_author`. LDConfig.ldr is from the same library. Suggested attribution:

> Part geometry, names and colour definitions derived from the LDraw.org Parts Library (https://www.ldraw.org), © the respective LDraw part authors (see `ldraw_author` per part), licensed under CC BY 2.0 / CC BY 4.0 (https://creativecommons.org/licenses/by/2.0/, https://creativecommons.org/licenses/by/4.0/). Values were computed from the original files; the files themselves are not redistributed.

**Rebrickable**: terms not verified (see above). Credit "Data from Rebrickable (https://rebrickable.com)" as a courtesy until the terms are checked.

**BrickLink and Merlin's Bricks SetDB**: only factual ids and names were taken, from public pages. Their terms were not reviewed.

LEGO® is a trademark of the LEGO Group, which does not sponsor or endorse this data.
