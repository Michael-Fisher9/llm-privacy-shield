from pathlib import Path

import pytest

from shield import Shield

CONFIG = Path(__file__).parent.parent / "config"


@pytest.fixture
def shield(tmp_path):
    mine = tmp_path / "my_numbers.txt"
    mine.write_text("TX12345678  # licence\n")
    s = Shield(store=tmp_path / "shield.db", names=CONFIG / "names.csv", categories=CONFIG / "categories.csv",
               my_numbers=mine, me="Jordan Reyes")
    yield s
    s.store.close()


def test_people_and_sensitive_businesses_become_stand_ins(shield):
    text = "Dana Whitfield moved her cleaning at Bayside Family Dental to Friday. Coffee after at Corner Grind Coffee?"
    out = shield.out(text)
    assert "Dana" not in out and "Bayside" not in out
    assert "[Person 1]" in out and "[Clinic 1]" in out
    assert "Corner Grind Coffee" in out  # food isn't hidden: the model can know where coffee is


def test_first_names_aliases_and_short_business_names_share_the_stand_in(shield):
    out = shield.out("Dana said Dee is fine, and Bayside Dental called.")
    assert out == "[Person 1] said [Person 1] is fine, and [Clinic 1] called."


def test_round_trip_through_text_and_tool_arguments(shield):
    prompt = shield.out("Remind me to call Marcus Oyelaran about Northgate Credit Union.")
    assert "Marcus" not in prompt and "Northgate" not in prompt
    # what a model might send back: a tool call, with the brackets dropped in one place
    reply = {"tool": "add_reminder", "args": {"title": "Call [Person 2]", "about": "financial company 1"}}
    assert shield.back(reply) == {"tool": "add_reminder",
                                  "args": {"title": "Call Marcus Oyelaran", "about": "Northgate Credit Union"}}


def test_contact_details_are_learned_on_the_way_out(shield):
    out = shield.out("Reach me at jordan.r@example.com or (512) 555-0142, details at https://example.com/booking/AB12.")
    assert "[Email 1]" in out and "[Phone 1]" in out and "[Link 1]" in out
    assert out.endswith(".")  # the sentence keeps its full stop, the link doesn't swallow it
    assert shield.back("Emailed [EMAIL 1]") == "Emailed jordan.r@example.com"


def test_id_numbers_and_your_own_numbers_are_removed_not_swapped(shield):
    out = shield.out("SSN 123-45-6789, card 4111 1111 1111 1111, account # 0012345678, licence TX-1234-5678.")
    assert out == "SSN [removed], card [removed], account # [removed], licence [removed]."
    assert not any("123" in r["real"] for r in shield.table())  # nothing to look up, so nothing kept


def test_stand_ins_survive_a_restart(tmp_path):
    a = Shield(store=tmp_path / "s.db", names=None, categories=None)
    first = a.out("Lunch with Priya Natarajan")
    a.learn("Priya Natarajan", "person")
    a.store.close()
    b = Shield(store=tmp_path / "s.db", names=None, categories=None)
    assert b.out("Priya Natarajan again") == "[Person 1] again" and first == "Lunch with Priya Natarajan"


def test_wrap_shields_any_model_call(shield):
    seen = []

    def fake_model(prompt):
        seen.append(prompt)
        return "Sure, I'll ask [Person 1]."

    ask = shield.wrap(fake_model)
    assert ask("Can Dana Whitfield make it?") == "Sure, I'll ask Dana Whitfield."
    assert seen == ["Can [Person 1] make it?"]
