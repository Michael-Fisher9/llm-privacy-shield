"""Run it: python examples/demo.py

No model needed. The fake model below just answers with a tool call, the way a real one
would, so you can see what leaves your machine and what comes back."""

import json
import tempfile
from pathlib import Path

from shield import Shield

here = Path(__file__).parent.parent
shield = Shield(store=Path(tempfile.mkdtemp()) / "demo.db", names=here / "config/names.csv",
                categories=here / "config/categories.csv", me="Jordan Reyes")

note = ("Dana Whitfield can't do Thursday. Move my cleaning at Bayside Family Dental to Friday 9am "
        "and text her at 512-555-0199 once it's set.")


def fake_model(prompt):
    print("sent to the model:\n ", prompt, "\n")
    return {"tool": "reschedule", "args": {"place": "[Clinic 1]", "when": "Friday 9:00",
                                           "then": "text [Person 1] at [Phone 1]"}}


answer = shield.wrap(fake_model)(note)
print("what your code gets back:\n ", json.dumps(answer, indent=2).replace("\n", "\n  "))
