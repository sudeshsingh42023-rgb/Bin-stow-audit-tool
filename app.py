"""
app.py — Warehouse Bin Stow-Quality Audit Tool

Simulates the core task of the Amazon "Associate, ML Data Operations,
GO-AI Operations" role: reviewing a fulfillment-center bin image, verifying
the number of items against system records, flagging anything wrong
(occlusion, misplacement, unreadable image), and doing this repeatedly
while accuracy AND speed are both tracked.

Run with:
    streamlit run app.py
"""

import csv
import os
import time
from datetime import datetime

import pandas as pd
import streamlit as st
from PIL import Image

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
IMG_DIR = os.path.join(DATA_DIR, "images")
METADATA_PATH = os.path.join(DATA_DIR, "metadata.csv")
LOG_PATH = os.path.join(DATA_DIR, "audit_log.csv")

LOG_FIELDS = [
    "timestamp", "auditor_id", "image_id", "difficulty",
    "true_count", "observed_count", "correct",
    "defect_flags", "time_taken_sec",
]

st.set_page_config(page_title="Bin Stow-Quality Audit Tool", layout="centered")


def load_metadata():
    return pd.read_csv(METADATA_PATH)


def load_log():
    if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 0:
        return pd.read_csv(LOG_PATH)
    return pd.DataFrame(columns=LOG_FIELDS)


def append_log(row: dict):
    write_header = not os.path.exists(LOG_PATH) or os.path.getsize(LOG_PATH) == 0
    with open(LOG_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def init_state():
    if "queue" not in st.session_state:
        meta = load_metadata()
        st.session_state.queue = meta.sample(frac=1, random_state=None).reset_index(drop=True)
        st.session_state.idx = 0
        st.session_state.image_start_time = time.time()


def next_image():
    st.session_state.idx += 1
    st.session_state.image_start_time = time.time()


def main():
    st.title("📦 Bin Stow-Quality Audit Tool")
    st.caption(
        "Verify the number of items in each bin image against system records, "
        "flag anything wrong, and submit — just like the video/image audit "
        "workflow in Amazon's GO-AI Operations role."
    )

    auditor_id = st.sidebar.text_input("Auditor ID", value="auditor_1")
    st.sidebar.markdown("---")

    init_state()
    queue = st.session_state.queue
    idx = st.session_state.idx

    log_df = load_log()
    if not log_df.empty:
        st.sidebar.subheader("Session stats")
        st.sidebar.metric("Audits completed", len(log_df))
        st.sidebar.metric("Accuracy", f"{log_df['correct'].mean() * 100:.1f}%")
        st.sidebar.metric("Avg time / audit", f"{log_df['time_taken_sec'].mean():.1f}s")
        hard_df = log_df[log_df["difficulty"] == "hard"]
        if not hard_df.empty:
            st.sidebar.metric("Accuracy on hard (blurry) bins", f"{hard_df['correct'].mean() * 100:.1f}%")

    if idx >= len(queue):
        st.success("✅ Queue complete — nice work.")
        if not log_df.empty:
            st.subheader("Full session log")
            st.dataframe(log_df, use_container_width=True)
            st.download_button(
                "Download audit log CSV",
                log_df.to_csv(index=False),
                file_name="audit_log.csv",
            )
        if st.button("Restart queue"):
            del st.session_state["queue"]
            del st.session_state["idx"]
            st.rerun()
        return

    row = queue.iloc[idx]
    st.progress(idx / len(queue), text=f"Bin {idx + 1} of {len(queue)}")

    img_path = os.path.join(IMG_DIR, f"{row['image_id']}.jpg")
    st.image(Image.open(img_path), caption=row["image_id"], width=350)

    with st.form(key=f"form_{idx}"):
        observed_count = st.number_input("How many items are in this bin?", min_value=0, max_value=15, step=1)
        defect_flags = st.multiselect(
            "Flag any issues (optional)",
            ["Occluded / hard to see", "Image blurry / unreadable", "Item appears misplaced", "None"],
        )
        submitted = st.form_submit_button("Submit audit")

    if submitted:
        elapsed = round(time.time() - st.session_state.image_start_time, 2)
        correct = int(observed_count) == int(row["true_count"])
        append_log({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "auditor_id": auditor_id,
            "image_id": row["image_id"],
            "difficulty": row["difficulty"],
            "true_count": row["true_count"],
            "observed_count": observed_count,
            "correct": int(correct),
            "defect_flags": "|".join(defect_flags),
            "time_taken_sec": elapsed,
        })
        if correct:
            st.toast("✅ Correct", icon="✅")
        else:
            st.toast(f"❌ System recorded {row['true_count']} items", icon="❌")
        next_image()
        st.rerun()


if __name__ == "__main__":
    main()
