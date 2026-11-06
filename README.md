# llm-privacy-shield

Hides names and personal details from a hosted LLM, then puts them back in the answer.

```
you write:        Dana Whitfield can't do Thursday. Move my cleaning at Bayside Family Dental to Friday
                  and text her at 512-555-0199.
the model sees:   [Person 1] can't do Thursday. Move my cleaning at [Clinic 1] to Friday
                  and text her at [Phone 1].
the model says:   reschedule(place="[Clinic 1]", then="text [Person 1] at [Phone 1]")
your code gets:   reschedule(place="Bayside Family Dental", then="text Dana Whitfield at 512-555-0199")
```

I built this for a personal data hub that sends my notes and emails to a model for filing. This is that piece on its own: no server, no dependencies.

## How well it works

500 made-up messages with 3,898 planted details, so every miss can be counted (`python evals/run_eval.py`):

| Planted detail | Caught | Rate |
|---|---:|---:|
| Listed person: full name, first name or nickname | 658 of 658 | 100% |
| Listed person, full name typed in lowercase | 223 of 223 | 100% |
| Sensitive business (clinic, bank, law office) | 227 of 227 | 100% |
| Phone, email or link, listed or not | 907 of 907 | 100% |
| SSN, card number or one of your own numbers | 637 of 637 | 100% |
| Model answer with brackets dropped or case changed, restored | 500 of 500 | 100% |
| Everyday business and ordinary words left alone (on purpose) | 599 of 599 | 100% |
| Listed person, first name typed in lowercase | 0 of 207 | 0% |
| Business called by a short name with no alias ("the Northgate office") | 0 of 218 | 0% |
| A name it was never told about | 0 of 222 | 0% |

The three misses are deliberate trade-offs, covered under Limits.

## Use

```python
from shield import Shield

shield = Shield(store="shield.db", names="config/names.csv", categories="config/categories.csv",
                my_numbers="my_numbers.txt", me="Your Name")

ask = shield.wrap(my_model_call)    # any function that takes a prompt and returns text or a dict
answer = ask("Can Dana make it Friday?")
```

Or call `shield.out(text)` before sending and `shield.back(reply)` after. `back` handles strings, lists and dicts, so tool-call arguments come back with the real values. `python examples/demo.py` runs the example above with a fake model.

Three small files set it up: `names.csv` (people and businesses, with aliases), `categories.csv` (which kinds of business to hide) and `my_numbers.txt` (your own ID numbers, git-ignored).

## Why it's built this way

- **Stand-ins keep the kind of thing.** `[Clinic 1]` instead of `XXXX`, so the model can still reason about it.
- **The same person keeps the same stand-in** across calls and days. That's why the lookup table lives in SQLite.
- **ID numbers are removed, not swapped.** A model never needs to tell two SSNs apart, and swapping would mean storing the real number.
- **A dentist is hidden, a coffee shop isn't.** Some businesses say something about you; most don't, and the model is more useful when it can see them.
- **Lowercase only counts for full names.** Matching "dana" would also mean matching "will" and "mark" for people named Will and Mark.

## Limits

- It only knows names you've listed. Add them to `names.csv`, or call `shield.learn(name, "person")` when your code finds one.
- Short business names need an alias ("Northgate" for Northgate Credit Union).
- It hides identifiers, not topics: "my physical therapy follow-up" still says something.
- `shield.db` is the key to everything. Keep it on your machine.

## Tests

`pip install -e ".[test]"`, then `pytest`. MIT license.
