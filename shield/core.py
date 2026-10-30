import csv
import re
from pathlib import Path

from .patterns import EMAIL, GENERIC, PHONE, REMOVE, REMOVED, URL, loose
from .store import Store

KIND_LABELS = {"person": "Person", "org": "Company", "email": "Email", "phone": "Phone",
               "address": "Address", "code": "Code", "link": "Link"}


def read_csv(path):
    if not path or not Path(path).exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


class Shield:
    """Swap personal details out of text before it goes to a hosted model, and back in after.

    shield.out(text)  -> text with stand-ins: "Dana Whitfield" -> "[Person 1]"
    shield.back(value) -> the real values back, in text or in a tool call's arguments

    names.csv tells it who and what to look for. categories.csv says which kinds of
    business get hidden: a dentist's name says something about you, a coffee shop's
    usually doesn't. my_numbers.txt (optional, never commit it) lists your own numbers,
    which are removed however they're punctuated.
    """

    def __init__(self, store="shield.db", names="config/names.csv", categories="config/categories.csv",
                 my_numbers=None, me=None):
        self.store = Store(store)
        self.to_token = {}   # real text as it appears -> stand-in
        self.to_real = {}    # stand-in -> the one real form to put back
        self.ignore_case = set()
        self.cats = {r["category"]: r for r in read_csv(categories)}
        self.mine = [p for p in (loose(line) for line in self._lines(my_numbers)) if p]
        self._stale = True
        if me:
            self._add(me, "[Me]")
        for real, token, kind in self.store.rows():
            self._add(real, token, ignore_case=kind in ("email", "link"))
        for r in read_csv(names):
            if r["kind"] == "org" and not self._hidden(r.get("category")):
                continue
            token = self.learn(r["name"], r["kind"], r.get("category"))
            for alias in filter(None, (a.strip() for a in r.get("aliases", "").split(";"))):
                self._add(alias, token, canonical=False)

    @staticmethod
    def _lines(path):
        if not path or not Path(path).exists():
            return []
        return [ln.split("#")[0].strip() for ln in Path(path).read_text().splitlines() if ln.split("#")[0].strip()]

    def _hidden(self, category):
        c = self.cats.get(category or "")
        return bool(c) and c.get("hide", "").lower() in ("yes", "y", "true", "1")

    def _label(self, kind, category):
        if kind == "org":
            return (self.cats.get(category or "") or {}).get("label") or "Company"
        return KIND_LABELS.get(kind, "Item")

    def _add(self, real, token, canonical=True, ignore_case=False):
        real = real.strip()
        if len(real) < 2 or real in self.to_token:
            return
        self.to_token[real] = token
        if canonical or token not in self.to_real:
            self.to_real.setdefault(token, real)
        if ignore_case:
            self.ignore_case.add(real)
        self._stale = True

    def learn(self, real, kind, category=None):
        """Give a name (or email, phone, address) a stand-in, or return the one it has."""
        real = real.strip()
        known = self.to_token.get(real) or next(
            (t for r, t in self.to_token.items() if r in self.ignore_case and r.lower() == real.lower()), None)
        if known:
            return known
        token = self.store.get_or_add(real, kind, self._label(kind, category))
        self._add(real, token, ignore_case=kind in ("email", "link"))
        self._short_form(real, token, kind)
        return token

    def _short_form(self, real, token, kind):
        # People get called by their first name and businesses by the front of theirs.
        # Both have to map to the same stand-in or the model sees two different things.
        words = real.split()
        if len(words) < 2 or kind not in ("person", "org"):
            return
        if kind == "person":
            short = words[0]
        else:
            core = list(words)
            while len(core) > 1 and core[-1].lower().strip(".,") in GENERIC:
                core.pop()
            short = " ".join(core) if core != words else ""
        if len(short) > 3 and short[0].isupper():
            self._add(short, token, canonical=False)

    def _build(self):
        if not self._stale:
            return
        # longest first, so "Dana Whitfield" wins over "Dana"
        names = sorted(self.to_token, key=len, reverse=True)
        alts = "|".join(("(?i:" + re.escape(n) + ")") if n in self.ignore_case else re.escape(n) for n in names)
        self._out_rx = re.compile(r"(?<![\w@])(?:" + alts + r")(?![\w@])") if names else None
        self._lower = {r.lower(): t for r, t in self.to_token.items() if r in self.ignore_case}
        # Models sometimes drop the brackets ("Person 1") or change the case. Numbered
        # stand-ins are distinctive enough to match either way; [Me] is not.
        self._back_key, alts = {}, []
        for t in sorted(self.to_real, key=len, reverse=True):
            inner = t[1:-1]
            self._back_key[inner.lower()] = t
            alts.append(r"\[?\b" + re.escape(inner) + r"\b\]?" if inner[-1].isdigit() else r"\[" + re.escape(inner) + r"\]")
        self._back_rx = re.compile("|".join(alts), re.I) if alts else None
        self._stale = False

    def out(self, text):
        if not text:
            return text
        for rx, repl in REMOVE:
            text = rx.sub(repl, text)
        for rx in self.mine:
            text = rx.sub(REMOVED, text)
        # contact details nobody listed are learned as they turn up
        for rx, kind in ((URL, "link"), (EMAIL, "email"), (PHONE, "phone")):
            for m in set(rx.findall(text)):
                self.learn(m, kind)
        self._build()
        if not self._out_rx:
            return text
        return self._out_rx.sub(lambda m: self.to_token.get(m.group(0)) or self._lower.get(m.group(0).lower(), m.group(0)), text)

    def back(self, value):
        self._build()
        if not self._back_rx:
            return value
        if isinstance(value, str):
            return self._back_rx.sub(lambda m: self.to_real[self._back_key[m.group(0).strip("[]").lower()]], value)
        if isinstance(value, list):
            return [self.back(v) for v in value]
        if isinstance(value, dict):
            return {k: self.back(v) for k, v in value.items()}
        return value

    def wrap(self, call):
        """Shield any function that takes a prompt and returns text or a dict (a tool call, say)."""
        def shielded(prompt, *args, **kwargs):
            return self.back(call(self.out(prompt), *args, **kwargs))
        return shielded

    def table(self):
        """What's in the lookup table, for checking it by eye. Keep this off screenshots."""
        return [{"real": r, "token": t, "kind": k} for r, t, k in self.store.rows()]
