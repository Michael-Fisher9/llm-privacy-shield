# llm-privacy-shield

Swaps names, contact details and sensitive businesses for stand-ins before text goes to a hosted LLM, and swaps them back when the answer comes home.

```
you write:        Dana Whitfield can't do Thursday. Move my cleaning at Bayside Family Dental to Friday
                  and text her at 512-555-0199.
the model sees:   [Person 1] can't do Thursday. Move my cleaning at [Clinic 1] to Friday
                  and text her at [Phone 1].
the model says:   reschedule(place="[Clinic 1]", then="text [Person 1] at [Phone 1]")
your code gets:   reschedule(place="Bayside Family Dental", then="text Dana Whitfield at 512-555-0199")
```

I built the first version of this for a personal data hub that sends my notes and emails to a model to get them filed. This is that piece pulled out on its own, with no database server and no dependencies.

## Use

```python
from shield import Shield

shield = Shield(store="shield.db", names="config/names.csv", categories="config/categories.csv",
                my_numbers="my_numbers.txt", me="Your Name")

ask = shield.wrap(my_model_call)    # any function that takes a prompt and returns text or a dict
answer = ask("Can Dana make it Friday?")
```

Or call `shield.out(text)` before sending and `shield.back(reply)` after. `back` works on strings, lists and dicts, so tool-call arguments come back with the real values in them.

`python examples/demo.py` runs the example above with a fake model.

## Settings

- `config/names.csv`: people and businesses to look for, with aliases (`Dee` for Dana).
- `config/categories.csv`: which kinds of business are hidden. A dentist or a credit union says something about you; a coffee shop usually doesn't, and the model is more useful if it can see it. Each kind has a label, so a hidden dentist becomes `[Clinic 1]`, not `[Company 1]`.
- `my_numbers.txt`: your own numbers (licence, member IDs), one per line. It's in `.gitignore`. They're found however they're punctuated and removed outright.

Emails, phone numbers and links nobody listed are learned the first time they show up.

## Why it's built this way

- **Stand-ins keep the kind of thing.** `[Clinic 1]` instead of `XXXX` means the model can still reason ("book a follow-up at the clinic") and its answers still make sense.
- **Numbered and stable.** The same person is `[Person 1]` today and next week, so a conversation that spans several calls stays consistent. That's why the table lives in SQLite and not in memory.
- **ID numbers are removed, not swapped.** A model never needs to tell two SSNs apart, and a stand-in would mean storing the real number in the lookup table.
- **Matching back is forgiving.** Models drop the brackets or change case ("person 1", `[PERSON 1]`), so numbered stand-ins match either way. `[Me]` has no number and must keep its brackets, or every "me" in an answer would turn into your name.
- **First names count.** "Dana" and "Dana Whitfield" map to the same stand-in, longest match first, or the model would see two people.

## Limits

- A name it has never seen goes through the first time. Add people to `names.csv`, or call `shield.learn(name, "person")` when your own code finds one.
- Context can still give things away ("my physical therapy follow-up on Tuesday"). This hides identifiers, not topics.
- Images and PDFs can't be filtered. Don't send them through this.
- The lookup table is the key to everything. Keep `shield.db` on your machine.

## Tests

```
pip install -e ".[test]"
pytest
```
