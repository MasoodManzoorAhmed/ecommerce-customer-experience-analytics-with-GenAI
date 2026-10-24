"""Review themes: placeholder until GenAI Module 2 (complaint classification) is built."""

import streamlit as st

from app.ui import callout, chip, hero, section

hero(
    "GenAI Module 2 · coming next",
    "What do unhappy customers <em>complain about</em>?",
    "40,748 customer reviews include a written comment, in Portuguese. Module 2 will "
    "classify each one into a complaint theme and compare three approaches on a hand-labelled "
    "test set.",
)

section("Planned complaint themes")
st.markdown(
    "".join(
        chip(t, tone)
        for t, tone in [
            ("late delivery", "coral"),
            ("never arrived", "coral"),
            ("damaged", "coral"),
            ("wrong or missing item", "coral"),
            ("product quality", "sand"),
            ("other", "teal"),
        ]
    ),
    unsafe_allow_html=True,
)

section("Approaches to compare")
c1, c2, c3 = st.columns(3, gap="medium")
for col, (name, text) in zip(
    (c1, c2, c3),
    [
        ("TF-IDF + logistic regression", "Fast, cheap, explainable baseline on word patterns."),
        ("LoRA-tuned transformer", "A multilingual model fine-tuned on a free Colab/Kaggle GPU."),
        ("Zero-shot LLM", "The theme definitions in a prompt, no training at all."),
    ],
    strict=True,
):
    with col.container(border=True):
        st.markdown(f"**{name}**")
        st.markdown(f'<div class="cx-note">{text}</div>', unsafe_allow_html=True)

st.markdown("&nbsp;", unsafe_allow_html=True)
callout(
    "<b>How they will be judged:</b> macro-F1 on about 200 reviews labelled by hand, plus cost "
    "and speed. The winner labels every review, and the themes appear here by state, by score "
    "and over time.",
    tone="teal",
)
