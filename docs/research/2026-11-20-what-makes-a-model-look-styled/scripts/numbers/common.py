"""Shared definitions for the style-numbers study: part groups, colour classes, which sets count,
and the subsets of question 2. Imported by the other scripts in this folder.

Data comes from rb.pkl (made by load_rb.py from Rebrickable's catalogue downloads).
"""
import re
import statistics

# ---------------------------------------------------------------- part groups

# Rebrickable part categories that are not building elements (left out of every count)
NONBUILD_CATS = {
    "13", "27", "59", "60", "61", "62", "63", "64", "65", "70", "71", "72", "73",  # minifigs, minidolls, their accessories
    "58",  # stickers
    "4", "57", "42", "43", "48", "66", "77", "78",  # Duplo/Quatro/Primo, non-buildable figures, Belville/Scala, Znap, Clikits, Modulex, non-system, pen & watch
    "45",  # electronics (lights, motors, hubs)
}
PINBEAM_CATS = {"8", "12", "46", "51", "53", "54", "55"}
TECH_OTHER_CATS = {"17", "22", "25", "26", "40", "52", "44"}
SNOT_RE = re.compile(
    r"\bbracket\b|\bstuds? on (?:\w+ ){0,2}sides?\b|\bside studs?\b|\bstuds? on (?:1 |2 )?ends?\b|"
    r"\bstuds on \d (?:adjacent )?sides\b|with headlight", re.I)
JUMPER_EXTRA = {"88646"}  # 3 x 4 plate with 1 x 4 centre studs: half-stud offset, name lacks "jumper"

GROUPS = [
    ("brick", "Plain bricks"),
    ("plate", "Plain plates"),
    ("tile", "Tiles (all smooth flat parts)"),
    ("slope", "Plain slopes with studs (incl. inverted)"),
    ("smooth_slope", "Studless small slopes (cheese etc.)"),
    ("curved", "Curved slopes and smooth curved parts"),
    ("wedge", "Wedge plates, wedge bricks, wings"),
    ("sideways", "Brackets and side-stud bricks"),
    ("jumper", "Jumper plates (half-stud offset)"),
    ("clipbar", "Clips, bars and handles"),
    ("hinge", "Hinges"),
    ("technic", "Technic beams, bricks with holes, pins, axles"),
    ("joint_other", "Turntables, ball joints, towballs"),
    ("round", "Round bricks, round plates, cones, dishes"),
    ("plate_mod", "Other modified plates"),
    ("brick_mod", "Other modified bricks, arches"),
    ("technic_other", "Other Technic (gears, panels, steering)"),
    ("wheel", "Wheels and tyres"),
    ("window", "Windows, doors, panels, windscreens"),
    ("vehicle", "Vehicle moulds (propellers, engines, tails, hulls)"),
    ("plant", "Plants"),
    ("other", "Everything else"),
]
GROUP_KEYS = [g for g, _ in GROUPS]
SMOOTH = ("tile", "smooth_slope", "curved")


def group_of_part(name, cat):
    """Return the group key for a Rebrickable part, or None if it is not a building element."""
    n = name.lower()
    if cat in NONBUILD_CATS or n.startswith("sticker"):
        return None
    if cat in PINBEAM_CATS or n.startswith("technic brick") or n.startswith("technic plate"):
        return "technic"
    if cat in TECH_OTHER_CATS:
        return "technic_other"
    if cat == "29":
        return "wheel"
    if "turntable" in n or re.search(r"towball|tow ball|ball joint|\bball\b|socket|rotation joint", n):
        if "hinge" not in n:
            return "joint_other"
    if cat == "18" or "hinge" in n:
        return "hinge"
    if cat in ("5", "9", "23", "20", "21", "15", "19", "11", "14") and SNOT_RE.search(name):
        return "sideways"
    if "jumper" in n:
        return "jumper"
    if "clip" in n or "bar holder" in n or "handle" in n or (
            cat in ("5", "9", "15", "19", "20", "21", "32") and re.search(r"\bbars?\b", n)):
        return "clipbar"
    if cat == "11":
        return "brick"
    if cat == "14":
        return "plate"
    if cat in ("19", "15", "67") or "ingot" in n:
        return "tile"
    if cat == "3":
        if ("2/3" in n and "inverted" not in n) or "no stud" in n:
            return "smooth_slope"
        if "curved" in n:
            return "curved"
        return "slope"
    if cat == "37":
        return "brick_mod" if "arch" in n else "curved"
    if cat == "6":
        return "curved" if "curved" in n else "wedge"
    if cat == "49" or re.search(r"\bwing\b", n) and cat in ("9", "14", "49", "6"):
        return "wedge"
    if cat in ("20", "21"):
        return "round"
    if cat == "9":
        return "plate_mod"
    if cat == "5":
        return "brick_mod"
    if cat in ("16", "23", "47"):
        return "window"
    if cat in ("35", "36"):
        return "vehicle"
    if cat == "76":
        return "plant"
    return "other"


def make_part_group(parts):
    out = {}
    for p, (name, cat) in parts.items():
        g = group_of_part(name, cat)
        if p in JUMPER_EXTRA and g is not None:
            g = "jumper"
        out[p] = g
    return out


# ---------------------------------------------------------------- colours

CLASSIC = {0, 15, 4, 1, 14, 7, 8}  # black, white, red, blue, yellow, light gray, dark gray (old greys)
PRIMARIES = {4, 1, 14}  # bright red, blue, yellow
NEW_GREYS = {71, 72}
ALL_GREYS = {7, 8, 71, 72, 9999}
LATER_NAMED = {272, 320, 288, 379, 378, 19, 28, 84, 191, 484, 322, 321, 326, 31, 30, 70, 308, 85, 26, 5, 29,
               27, 25, 226, 212, 78, 73, 323, 1050, 158, 1136, 1062, 3}


def colour_class(cid, colors):
    """classic / new_grey / trans / metal / later / old_other / unknown."""
    if cid not in colors:
        return "unknown"
    name, trans, y1, y2 = colors[cid]
    if trans:
        return "trans"
    if cid in CLASSIC:
        return "classic"
    if cid in NEW_GREYS:
        return "new_grey"
    nl = name.lower()
    if any(k in nl for k in ("pearl", "metallic", "chrome", "flat silver", "glitter", "satin", "speckle")):
        return "metal"
    if cid in LATER_NAMED or y1 >= 1994:
        return "later"
    return "old_other"


SCHEME_SKIP_EXTRA = {9999, -1}


def scheme_colour_ok(cid, colors):
    if cid in ALL_GREYS or cid in SCHEME_SKIP_EXTRA or cid == 0 or cid not in colors:
        return False
    name, trans, _y1, _y2 = colors[cid]
    nl = name.lower()
    if trans or "gray" in nl or "grey" in nl or "silver" in nl or "titanium" in nl:
        return False
    return True


# ---------------------------------------------------------------- which sets count

EXCLUDE_THEMES = {
    "1", "324", "400", "258", "438", "504", "440", "441", "480", "318", "668", "390", "500", "254", "443", "507",
    "501", "497", "502", "535", "688", "709", "716", "277", "694", "719", "398", "408", "301", "559", "621",
    "465", "399", "34", "371", "473", "143", "369", "368", "685", "646",
}
BUCKET_RE = re.compile(
    r"bucket|\btub\b|brick box|bricks box|creative (box|suitcase|chest|bricks|building)|bricks (and|&) more|"
    r"supplementar|storage|bulk|parts pack|value pack|\bkit\b|starter set|building set$|bricks$|pieces$|"
    r"collection$|combo|bundle|super pack|\bpack\b|\bbox\b|key ?chain|magnet", re.I)


def theme_chain(tid, themes):
    chain = []
    t = tid
    while t and len(chain) < 10:
        chain.append(t)
        t = themes[t][1] if t in themes else ""
    return chain


def base_ok(s, d):
    """A set in the study's base population: system themes, not a bucket or pack. (Size is checked later.)"""
    name, year, tid, _n = d["sets"][s]
    if any(t in EXCLUDE_THEMES for t in theme_chain(tid, d["themes"])):
        return False
    if BUCKET_RE.search(name):
        return False
    return True


# ---------------------------------------------------------------- question 2 subsets

AIR_RE = re.compile(r"plane|\bjet\b|jets\b|aircraft|airliner|flyer|flier|glider|biplane|helicopter|copter|"
                    r"chopper|\bspitfire|airshow|air show|seaplane|jumbo|cessna|airbus|boeing|concorde|"
                    r"bomber|fighter jet|stunt flyer|skyway|turbo prop", re.I)
AIR_NOT = re.compile(r"airport|station|hangar|terminal|\bbase\b|carrier|island|rescue center|headquarters|"
                     r"space|star|x-wing|tie |starfighter|droid|bat|mech|robot|dragon|ninja|sea jet|land jet|fire ?fighter|"
                     r"\bhq\b|truck|transport|rover|prowler|decoder|cruiser|planet", re.I)
CAR_RE = re.compile(r"\bcar\b|\bcars\b|racer|roadster|coupe|convertible|hot rod|dragster|buggy|speedster|"
                    r"\brace\b|rally|\bf1\b|formula|limo|taxi|jeep|4x4|pick-?up|camper|beetle|mini cooper|"
                    r"cooper|mustang|porsche|ferrari|lamborghini|bugatti|mclaren|mercedes|\bbmw\b|audi|chevrolet|"
                    r"corvette|\bford\b|fiat|aston|jaguar|land rover|volkswagen|\bvw\b|toyota|nissan|dodge|"
                    r"camaro|cadillac|lotus|koenigsegg|pagani|maserati|alfa|peugeot|lancia|honda|batmobile|"
                    r"street|muscle|sports|cruiser|\bvan\b|gt\b|grand prix", re.I)
CAR_NOT = re.compile(r"truck|transporter|car wash|garage|station|showroom|crane|trailer|hauler|tow |boat|"
                     r"ship|plane|jet|helicopter|copter|train|tram|bus\b|motorbike|motorcycle|bike|kart|"
                     r"space|star|robot|mech|dragon|track|stadium|wash|park|house|shop|tower", re.I)
CREATURE_RE = re.compile(r"\bcat\b|cats|kitten|dog|puppy|puppies|bird|parrot|owl|eagle|flamingo|penguin|"
                         r"animal|creature|dragon|tiger|lion|panda|bear|rabbit|bunny|hamster|fox|wolf|horse|"
                         r"pony|unicorn|deer|reindeer|elephant|giraffe|monkey|gorilla|koala|sloth|hedgehog|"
                         r"turtle|tortoise|frog|fish|shark|whale|dolphin|octopus|crab|lobster|scorpion|"
                         r"spider|butterfly|bee|insect|bug|snake|lizard|chameleon|dinosaur|\bdino|\brex\b|"
                         r"raptor|pets?\b|duck|chicken|chick|hen|rooster|swan|peacock|toucan|hummingbird|"
                         r"kingfisher|pig|cow|sheep|goat|squirrel|mouse|mice|bat\b|beaver|otter|seal|"
                         r"walrus|polar|wild|safari|jungle|forest animals|sea animals|ocean", re.I)


def subset_of(s, d, counted):
    """Return 'aircraft', 'car', 'creature' or None. counted = building parts in the set."""
    name, year, tid, _n = d["sets"][s]
    chain = theme_chain(tid, d["themes"])
    town_city = "50" in chain or "52" in chain
    creator = "22" in chain
    icons = "721" in chain or "673" in chain
    if "610" in chain or "769" in chain:  # BrickHeadz, Botanicals
        return "creature" if 20 <= counted <= 1500 else None
    if creator and CREATURE_RE.search(name) and not AIR_RE.search(name) and not CAR_RE.search(name):
        return "creature" if 50 <= counted <= 1500 else None
    if not (90 <= counted <= 600):
        return None
    if "601" in chain:  # Speed Champions
        return "car" if counted >= 150 else None
    vehicle_theme = town_city or creator or icons or "278" in chain or "112" in chain or "365" in chain or \
        "599" in chain or "598" in chain or "576" in chain
    if not vehicle_theme:
        return None
    if AIR_RE.search(name) and not AIR_NOT.search(name):
        return "aircraft"
    if counted < 150:
        return None
    if CAR_RE.search(name) and not CAR_NOT.search(name):
        return "car"
    return None


def wmedian(pairs):
    """Median of values weighted by counts: pairs = [(value, weight)]."""
    pairs = sorted(pairs)
    tot = sum(w for _v, w in pairs)
    if tot == 0:
        return None
    acc = 0
    for v, w in pairs:
        acc += w
        if acc >= tot / 2:
            return v
    return pairs[-1][0]


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None
