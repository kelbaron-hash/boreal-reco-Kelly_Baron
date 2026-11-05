"""Boréal Marché recommendation engine.

The app NEVER mines rules: it only loads models/rules.json and models/metadata.json.
Mining is expensive and offline (notebooks/01_mining.ipynb); recommending is instant and online.
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "models" / "rules.json"
METADATA_PATH = ROOT / "models" / "metadata.json"
PRODUCTS_PATH = ROOT / "data" / "products.csv"

MAX_SUGGESTIONS = 5

# Strength label derived from the lift (all saved rules already have lift above 1.2)
LIFT_LABELS = [
    (6.0, "Very strong"),
    (3.0, "Strong"),
    (2.0, "Moderate"),
    (0.0, "Weak"),
]


def strength_label(lift):
    for threshold, label in LIFT_LABELS:
        if lift >= threshold:
            return label
    return "Weak"


def recommend(basket_items, rules, max_suggestions=MAX_SUGGESTIONS):
    """Return the rules behind the suggestions: one rule per suggested product, sorted by lift."""
    basket_set = set(basket_items)
    best_rule_per_product = {}

    for rule in rules:
        suggested_product = rule["consequent"]

        # An item already in the basket is never suggested again
        if suggested_product in basket_set:
            continue

        # The rule fires only if ALL its antecedent items are in the basket (subset matching)
        if not set(rule["antecedent"]).issubset(basket_set):
            continue

        # Two rules suggesting the same product: keep the one with the higher lift
        current_best = best_rule_per_product.get(suggested_product)
        if current_best is None or rule["lift"] > current_best["lift"]:
            best_rule_per_product[suggested_product] = rule

    fired_rules = sorted(best_rule_per_product.values(), key=lambda rule: rule["lift"], reverse=True)
    return fired_rules[:max_suggestions]


@st.cache_data
def load_model():
    with open(RULES_PATH, encoding="utf-8") as rules_file:
        rules = json.load(rules_file)
    with open(METADATA_PATH, encoding="utf-8") as metadata_file:
        metadata = json.load(metadata_file)
    products = pd.read_csv(PRODUCTS_PATH)
    return rules, metadata, products


def add_item(item):
    if item not in st.session_state.basket:
        st.session_state.basket.append(item)


def remove_item(item):
    st.session_state.basket.remove(item)


def clear_basket():
    st.session_state.basket = []


def show_popular_products(metadata, products_by_item, basket):
    st.caption("Most popular products:")
    shown = 0
    for popular in metadata["popular_products"]:
        if popular["product"] in basket:
            continue
        info = products_by_item[popular["product"]]
        share = popular["share_of_baskets"] * 100
        st.markdown(f"**{info['Item_EN']}** · {share:.1f}% of baskets")
        shown += 1
        if shown == MAX_SUGGESTIONS:
            break


def show_recommendation(rule, products_by_item):
    info = products_by_item[rule["consequent"]]
    antecedent_names = ", ".join(products_by_item[item]["Item_EN"] for item in rule["antecedent"])
    confidence_percent = rule["confidence"] * 100
    support_percent = rule["support"] * 100

    with st.container(border=True):
        title_column, price_column = st.columns([3, 1])
        title_column.markdown(f"**{info['Item_EN']}**")
        price_column.markdown(f"**${info['Price']:.2f}**")
        st.caption(f"{info['Category']} · {rule['consequent']}")
        st.markdown(
            f"💡 **Why this?** Because your basket contains **{antecedent_names}**, customers who "
            f"buy that also buy **{info['Item_EN']}** {confidence_percent:.0f}% of the time — "
            f"that is **{rule['lift']:.1f}×** more often than average."
        )
        st.caption(
            f"Lift {rule['lift']:.2f} · Confidence {confidence_percent:.0f}% · "
            f"Support {support_percent:.2f}% · {strength_label(rule['lift'])} association"
        )


def show_rules_that_fired(fired_rules, products_by_item):
    rows = []
    for rule in fired_rules:
        rows.append({
            "If the basket contains": " + ".join(products_by_item[item]["Item_EN"] for item in rule["antecedent"]),
            "Then suggest": products_by_item[rule["consequent"]]["Item_EN"],
            "Support": f"{rule['support'] * 100:.2f}%",
            "Confidence": f"{rule['confidence'] * 100:.1f}%",
            "Lift": f"{rule['lift']:.2f}",
        })
    with st.expander("🔍 Rules that fired"):
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def never_suggested_note(item, metadata, products_by_item):
    """Explain why a product appears in no rule (rare product edge case)."""
    details = metadata["not_recommendable"].get(item)
    if details is None:
        return None
    name = products_by_item[item]["Item_EN"]
    share = details["share_of_baskets"] * 100
    if details["best_lift"] is None or share < metadata["thresholds"]["min_support"] * 100:
        return (
            f"ℹ️ **{name}** is never suggested: it appears in only {share:.2f}% of baskets, below the "
            f"{metadata['thresholds']['min_support'] * 100:.1f}% minimum support, so no rule can include it."
        )
    return (
        f"ℹ️ **{name}** is never suggested: it is bought independently of other products "
        f"(best lift {details['best_lift']:.2f}), so no rule can justify recommending it."
    )


def main():
    st.set_page_config(page_title="Boréal Marché — Recommendation Engine", page_icon="🛒", layout="wide")

    if "basket" not in st.session_state:
        st.session_state.basket = []

    rules, metadata, products = load_model()
    products_by_item = products.set_index("Item").to_dict("index")
    basket = st.session_state.basket

    st.title("🛒 Boréal Marché — Recommendation Engine")
    st.caption(
        f"Association rules · Apriori algorithm · {metadata['data']['baskets']:,} baskets · "
        f"{metadata['data']['products']} products · rules are mined offline and loaded from a file"
    )

    basket_total = sum(products_by_item[item]["Price"] for item in basket)
    metric_columns = st.columns(4)
    metric_columns[0].metric("Rules loaded", f"{len(rules):,}")
    metric_columns[1].metric("Products", len(products))
    metric_columns[2].metric("Items in basket", len(basket))
    metric_columns[3].metric("Basket total", f"${basket_total:,.2f}")

    catalogue_column, basket_column, recommendation_column = st.columns([1.2, 1, 1.4], gap="large")

    # ---------------- Zone 1: catalogue ----------------
    with catalogue_column:
        st.subheader("1 · Catalogue")
        categories = ["All categories"] + sorted(products["Category"].unique())
        selected_category = st.selectbox("Category", categories, label_visibility="collapsed")
        search_text = st.text_input("Search by name", placeholder="🔎 Search...", label_visibility="collapsed")

        visible = products
        if selected_category != "All categories":
            visible = visible[visible["Category"] == selected_category]
        if search_text:
            text = search_text.lower()
            matches_english = visible["Item_EN"].str.lower().str.contains(text, regex=False)
            matches_french = visible["Item"].str.lower().str.contains(text, regex=False)
            visible = visible[matches_english | matches_french]

        st.caption(f"{len(visible)} product(s)")
        with st.container(height=520):
            for _, product in visible.iterrows():
                name_column, button_column = st.columns([3, 1])
                name_column.markdown(f"**{product['Item_EN']}**")
                name_column.caption(f"{product['Category']} · ${product['Price']:.2f}")
                button_column.button(
                    "Add",
                    key=f"add_{product['Item']}",
                    on_click=add_item,
                    args=(product["Item"],),
                    disabled=product["Item"] in basket,
                )

    # ---------------- Zone 2: basket ----------------
    with basket_column:
        st.subheader("2 · My basket")
        if not basket:
            st.info("Your basket is empty. Add a product to see recommendations.")
        for item in basket:
            info = products_by_item[item]
            item_column, remove_column = st.columns([3, 1])
            item_column.markdown(f"**{info['Item_EN']}**")
            item_column.caption(f"{info['Category']} · ${info['Price']:.2f}")
            remove_column.button("✕", key=f"remove_{item}", on_click=remove_item, args=(item,))
        st.button("Clear basket", on_click=clear_basket, disabled=not basket)
        st.markdown(f"**Total: ${basket_total:,.2f}**")

        for item in basket:
            note = never_suggested_note(item, metadata, products_by_item)
            if note:
                st.caption(note)

    # ---------------- Zone 3: recommendations ----------------
    with recommendation_column:
        st.subheader("3 · You may also like")
        fired_rules = recommend(basket, rules)

        if not basket:
            st.info(
                "No rule can fire on an empty basket. This is the \"cold start\" case: "
                "the system falls back to the most popular products."
            )
            show_popular_products(metadata, products_by_item, basket)
        elif not fired_rules:
            st.warning(
                "No rule applies to this basket: none of the saved rules has all its conditions "
                "in your basket. Falling back to the most popular products."
            )
            show_popular_products(metadata, products_by_item, basket)
        else:
            for rule in fired_rules:
                show_recommendation(rule, products_by_item)
            show_rules_that_fired(fired_rules, products_by_item)


main()