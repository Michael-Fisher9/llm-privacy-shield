"""Measure the shield on made-up messages where every planted detail is known.

    python evals/run_eval.py            # writes evals/results.md and evals/results.csv

Each message mixes listed people (full name, first name, nickname), businesses whose kind is
hidden or visible, contact details nobody listed, ID numbers, and names the shield was never
told about. Because we planted every one, we can count exactly what got through.
"""
import csv
import random
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shield import Shield  # noqa: E402

SEED, N = 7, 500
FIRST = ["Dana", "Marcus", "Priya", "Tomas", "Keiko", "Andre", "Lena", "Rafael", "Simone", "Owen",
         "Farah", "Gideon", "Mireille", "Caleb", "Yusuf", "Noor", "Elliot", "Harriet", "Dmitri", "Ines"]
LAST = ["Whitfield", "Oyelaran", "Castellano", "Brandt", "Nakamura", "Lindqvist", "Ferreira", "Okafor",
        "Delacroix", "Haverford", "Mbeki", "Sorensen", "Quintero", "Ashworth", "Petrakis", "Valdez"]
HIDDEN = [("Bayside Family Dental", "medical"), ("Northgate Credit Union", "financial"),
          ("Riverbend Physical Therapy", "medical"), ("Hollis & Grant Law", "legal"),
          ("Summit Ridge Pediatrics", "medical"), ("Cedar Lake Savings Bank", "financial")]
VISIBLE = [("Corner Grind Coffee", "food"), ("Lantern Street Books", "retail"),
           ("Bluebonnet Air", "travel"), ("Pecan Flats Diner", "food")]
NICK = {"Dana": "Dee", "Tomas": "Tom", "Rafael": "Rafa", "Elliot": "Eli", "Harriet": "Hattie",
        "Dmitri": "Dima", "Mireille": "Mimi", "Gideon": "Gid"}
SHORT = {"Northgate Credit Union": "Northgate", "Bayside Family Dental": "Bayside",
         "Riverbend Physical Therapy": "Riverbend", "Cedar Lake Savings Bank": "Cedar Lake"}
BYSTANDERS = ["Will", "May", "Austin", "Friday", "Grant", "Summit", "Lake", "Mark", "Bank", "Ask"]
UNLISTED = ["Rosalind Achterberg", "Bartholomew Kwan", "Esperanza Liddell", "Ignatius Mercer"]
MY_NUMBER = "48213907"  # stands in for a member ID in my_numbers.txt


def people(rng):
    pool = [(f, rng.choice(LAST)) for f in FIRST]
    return [(f"{f} {l}", f, NICK.get(f)) for f, l in pool]


def write_config(folder, ppl):
    with open(folder / "names.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "kind", "category", "aliases"])
        for full, _, nick in ppl:
            w.writerow([full, "person", "", nick or ""])
        for name, cat in HIDDEN + VISIBLE:
            w.writerow([name, "org", cat, ""])
    here = Path(__file__).resolve().parents[1]
    (folder / "categories.csv").write_text((here / "config/categories.csv").read_text())
    (folder / "my_numbers.txt").write_text(MY_NUMBER + "\n")


def plant(rng, ppl):
    """One message and the details planted in it: (text as written, kind, what should happen)."""
    full, first, nick = rng.choice(ppl)
    other = rng.choice(ppl)
    org, _ = rng.choice(HIDDEN)
    shop, _ = rng.choice(VISIBLE)
    phone = f"512-555-{rng.randint(1000, 9999)}"
    email = f"{first.lower()}.{rng.randint(10, 99)}@example.com"
    url = f"https://portal.example.org/appt/{rng.randint(1000, 9999)}"
    ssn = f"{rng.randint(100, 899)}-{rng.randint(10, 99)}-{rng.randint(1000, 9999)}"
    card = " ".join(str(rng.randint(1000, 9999)) for _ in range(4))
    mine = rng.choice([MY_NUMBER, "48-213-907", "4821 3907", "48.21.39.07"])
    stranger = rng.choice(UNLISTED)
    odd_phone = rng.choice([f"(512) 555-{rng.randint(1000, 9999)}", f"512.555.{rng.randint(1000, 9999)}",
                            f"+1 512 555 {rng.randint(1000, 9999)}", f"512555{rng.randint(1000, 9999)}"])
    short_org = rng.choice(list(SHORT))
    words = rng.sample(BYSTANDERS, 3)
    pieces = [
        (f"{full} moved our appointment at {org}.", [(full, "listed person, full name", "hide"),
                                                        (org, "sensitive business", "hide")]),
        (f"Ask {first} if Friday works.", [(first, "listed person, first name", "hide")]),
        (f"{nick} said it's fine." if nick else f"{other[1]} said it's fine.",
         [((nick or other[1]), "listed person, nickname" if nick else "listed person, first name", "hide")]),
        (f"Call {phone} or email {email}.", [(phone, "phone number", "hide"), (email, "email address", "hide")]),
        (f"Forms are at {url}.", [(url, "link", "hide")]),
        (f"Meet at {shop} after.", [(shop, "everyday business (kept on purpose)", "keep")]),
        (f"SSN {ssn}, card {card}.", [(ssn, "ID or card number", "remove"), (card, "ID or card number", "remove")]),
        (f"My member number is {mine}.", [(mine, "my own number, any punctuation", "remove")]),
        (f"{stranger} from the front desk called.", [(stranger, "name never listed", "hide")]),
        (f"Text {odd_phone} instead.", [(odd_phone, "phone number, other formats", "hide")]),
        (f"remind {first.lower()} tomorrow.", [(first.lower(), "listed person, first name in lowercase", "hide")]),
        (f"cc {other[0].lower()} on it.", [(other[0].lower(), "listed person, full name in lowercase", "hide")]),
        (f"The {SHORT[short_org]} office closes early.", [(SHORT[short_org], "sensitive business, short name with no alias", "hide")]),
        (f"{words[0]} {words[1].lower()} check the {words[2]} sheet?",
         [(words[0], "ordinary words left alone", "keep"), (words[2], "ordinary words left alone", "keep")]),
    ]
    chosen = rng.sample(pieces, rng.randint(4, 8))
    return " ".join(p for p, _ in chosen), [d for _, ds in chosen for d in ds]


def model_echo(rng, shielded):
    """A model repeating the stand-ins back, sometimes without brackets or in another case."""
    def mangle(m):
        t = m.group(0)
        r = rng.random()
        if t == "[Me]" or r < 0.6:
            return t
        return t[1:-1] if r < 0.8 else t.upper()
    return re.sub(r"\[[A-Za-z ]+ \d+\]|\[Me\]", mangle, shielded)


def main():
    rng = random.Random(SEED)
    ppl = people(rng)
    tmp = Path(tempfile.mkdtemp())
    write_config(tmp, ppl)
    shield = Shield(store=tmp / "eval.db", names=tmp / "names.csv", categories=tmp / "categories.csv",
                    my_numbers=tmp / "my_numbers.txt")
    tally = defaultdict(lambda: [0, 0])  # kind -> [handled as intended, total]
    round_trip = [0, 0]
    for _ in range(N):
        text, planted = plant(rng, ppl)
        out = shield.out(text)
        for real, kind, want in planted:
            present = re.search(r"(?<![\w@])" + re.escape(real) + r"(?![\w@])", out) is not None
            ok = present if want == "keep" else not present
            tally[kind][0] += ok
            tally[kind][1] += 1
        # round trip: whatever was swapped (not removed) should come back exactly
        expected = shield.back(out)
        round_trip[0] += shield.back(model_echo(rng, out)) == expected
        round_trip[1] += 1

    order = ["listed person, full name", "listed person, first name", "listed person, nickname",
             "listed person, full name in lowercase", "listed person, first name in lowercase", "sensitive business", "sensitive business, short name with no alias",
             "phone number", "phone number, other formats", "email address", "link", "ID or card number",
             "my own number, any punctuation", "everyday business (kept on purpose)",
             "ordinary words left alone", "name never listed"]
    rows = [(k, *tally[k]) for k in order if k in tally]
    here = Path(__file__).parent
    with open(here / "results.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["detail", "handled", "total", "rate"])
        for k, ok, n in rows:
            w.writerow([k, ok, n, f"{ok / n:.3f}"])
        w.writerow(["round trip (model drops brackets or changes case)", *round_trip,
                    f"{round_trip[0] / round_trip[1]:.3f}"])
    lines = [f"Seed {SEED}, {N} made-up messages, {sum(n for _, _, n in rows):,} planted details.", "",
             "| Planted detail | Handled as intended | Rate |", "|---|---:|---:|"]
    lines += [f"| {k} | {ok:,} of {n:,} | {ok / n:.0%} |" for k, ok, n in rows]
    lines.append(f"| Round trip, model drops brackets or changes case | {round_trip[0]:,} of {round_trip[1]:,} "
                 f"| {round_trip[0] / round_trip[1]:.0%} |")
    (here / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
