"""Tests of the five edge cases of the Streamlit app (run with: pytest tests)."""
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
APP_PATH = str(ROOT / "app" / "streamlit_app.py")

with open(ROOT / "models" / "rules.json", encoding="utf-8") as rules_file:
    RULES = json.load(rules_file)


def run_app_with_basket(basket):
    app = AppTest.from_file(APP_PATH, default_timeout=60)
    app.session_state["basket"] = basket
    app.run()
    assert not app.exception
    return app


def text_of(app):
    parts = [element.value for element in app.markdown]
    parts += [element.value for element in app.info]
    parts += [element.value for element in app.warning]
    parts += [element.value for element in app.caption]
    return "\n".join(parts)


def test_empty_basket_shows_message_and_popular_fallback():
    app = run_app_with_basket([])
    text = text_of(app)
    assert "cold start" in text
    assert "Most popular products" in text


def test_no_rule_fires_shows_message_and_fallback():
    app = run_app_with_basket(["Sac réutilisable"])
    text = text_of(app)
    assert "No rule applies to this basket" in text
    assert "Most popular products" in text


def test_items_in_basket_are_never_suggested():
    basket = ["Steak de boeuf", "Pain à hamburger", "Charbon de bois"]
    app = run_app_with_basket(basket)
    text = text_of(app)
    assert "Why this?" in text
    for item in basket:
        assert f"buy **{item}**" not in text


def test_same_product_keeps_the_rule_with_higher_lift():
    basket = ["Steak de boeuf", "Pain à hamburger", "Charbon de bois"]
    basket_set = set(basket)
    best = {}
    for rule in RULES:
        if rule["consequent"] in basket_set:
            continue
        if set(rule["antecedent"]).issubset(basket_set):
            best[rule["consequent"]] = max(best.get(rule["consequent"], 0), rule["lift"])
    app = run_app_with_basket(basket)
    shown_lifts = [float(text.split("Lift ")[1].split(" ·")[0]) for text in
                   [element.value for element in app.caption] if text.startswith("Lift ")]
    assert shown_lifts == sorted(shown_lifts, reverse=True)
    assert len(shown_lifts) <= 5
    assert abs(shown_lifts[0] - max(best.values())) < 0.01


def test_very_rare_product_is_explained():
    app = run_app_with_basket(["Caviar"])
    text = text_of(app)
    assert "never suggested" in text
    assert "minimum support" in text