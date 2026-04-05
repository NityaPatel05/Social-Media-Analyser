import logging
import html
import re
import numpy as np
import polars as pl
from umap import UMAP
import datamapplot
import tempfile
import os

logger = logging.getLogger(__name__)

# ── High-contrast, perceptually distinct color palette ───────────────────────
_DISTINCT_COLORS = [
    "#e6194b",  # vivid red
    "#3cb44b",  # vivid green
    "#4363d8",  # vivid blue
    "#f58231",  # vivid orange
    "#911eb4",  # vivid purple
    "#42d4f4",  # vivid cyan
    "#f032e6",  # vivid magenta
    "#bfef45",  # vivid lime
    "#fabed4",  # pink
    "#469990",  # teal
    "#dcbeff",  # lavender
    "#9a6324",  # brown
    "#fffac8",  # cream
    "#800000",  # maroon
    "#aaffc3",  # mint
    "#808000",  # olive
    "#ffd8b1",  # apricot
    "#000075",  # navy
    "#a9a9a9",  # grey (spare)
    "#e0e0e0",  # light grey (spare)
]

# Stopwords to filter from cluster label display
_LABEL_STOPWORDS = {
    "the", "to", "and", "a", "of", "in", "is", "it", "for", "on", "that",
    "this", "was", "are", "be", "as", "at", "by", "an", "or", "but", "not",
    "with", "from", "have", "amp", "nbsp", "ampnbsp", "http", "www", "com",
    "just", "get", "got", "like", "one", "also", "do", "so", "up", "out",
    "re", "reddit", "post", "comment",
}


def _make_color_map(unique_labels: list) -> dict:
    color_map = {}
    color_idx = 0
    for label in unique_labels:
        if label == "Uncategorized":
            color_map[label] = "#4b5563"
        else:
            color_map[label] = _DISTINCT_COLORS[color_idx % len(_DISTINCT_COLORS)]
            color_idx += 1
    return color_map


def _clean_label(raw_terms: str, max_words: int = 3) -> str:
    """
    Build a clean display label from a comma-separated terms string.
    Filters stopwords and HTML noise.
    """
    if not raw_terms or not raw_terms.strip():
        return ""
    # Unescape any HTML entities that leaked into term strings
    raw_terms = html.unescape(raw_terms)
    raw_terms = re.sub(r"https?://\S+", "", raw_terms)

    words = [t.strip() for t in raw_terms.split(",")]
    clean = [
        w for w in words
        if w and w.lower() not in _LABEL_STOPWORDS and len(w) > 2
    ]
    label = ", ".join(clean[:max_words])
    return label[:35] if label else "misc"


def generate_visualization(
    df: pl.DataFrame,
    embeddings: np.ndarray,
    assignments: list,
    top_terms: dict,
) -> str:
    """
    Generate UMAP 2D coordinates and return interactive DataMapPlot HTML.
    Uses tighter UMAP params for better cluster separation.
    """
    try:
        if df is None or len(df) == 0 or len(embeddings) == 0:
            return "<div style='color:white;'>No mapping available</div>"

        n_points = len(embeddings)
        if n_points < 5:
            return "<div style='color:white;'>Not enough data to plot UMAP</div>"

        # ── UMAP for 2D visualization ─────────────────────────────────────────
        # Use tighter min_dist for denser, more separated clusters
        # n_neighbors smaller → tighter local structure
        n_neighbors = min(20, max(5, n_points // 15))

        reducer = UMAP(
            n_neighbors=n_neighbors,
            n_components=2,
            min_dist=0.05,      # was 0.25 — lower = tighter, more separated blobs
            spread=2.5,         # was 1.5 — higher = more space between clusters
            metric="cosine",
            random_state=42,
            low_memory=n_points > 5000,
        )
        umap_embeddings = reducer.fit_transform(embeddings)

        # ── Build per-point labels (with stopword filtering) ──────────────────
        labels = []
        for tid in assignments:
            if tid == -1:
                labels.append("Uncategorized")
            else:
                raw = top_terms.get(str(tid), "")
                label = _clean_label(raw, max_words=3)
                labels.append(label if label else f"Topic {tid}")

        # Unique labels in encounter order
        seen: list = []
        for lbl in labels:
            if lbl not in seen:
                seen.append(lbl)

        color_map = _make_color_map(seen)
        point_colors = np.array([color_map[lbl] for lbl in labels])
        labels_arr = np.array(labels)

        # ── Hover text ────────────────────────────────────────────────────────
        titles = df["title"].to_list()
        hover_texts = [
            html.unescape(str(t))[:100] + "…" if len(str(t)) > 100 else html.unescape(str(t))
            for t in titles
        ]

        # ── Create the DataMapPlot ────────────────────────────────────────────
        base_kwargs = dict(
            title="Topic Embedding Space",
            darkmode=True,
            font_family="Inter, Roboto, sans-serif",
            hover_text=hover_texts,
        )

        plot = None
        attempts = [
            dict(
                color_label_map=color_map,
                point_size=4,               # smaller = less visual clutter
                point_line_width=0,
                noise_color="#4b5563",
                **base_kwargs,
            ),
            dict(
                point_colors=point_colors,
                point_size=4,
                point_line_width=0,
                noise_color="#4b5563",
                **base_kwargs,
            ),
            base_kwargs,
        ]

        for attempt_kwargs in attempts:
            try:
                plot = datamapplot.create_interactive_plot(
                    umap_embeddings,
                    labels_arr,
                    **attempt_kwargs,
                )
                break
            except TypeError:
                continue

        if plot is None:
            return "<div style='color:white;'>Datamapplot failed to render.</div>"

        # ── Export to HTML string ─────────────────────────────────────────────
        raw_html = None

        if hasattr(plot, "to_html"):
            try:
                raw_html = plot.to_html()
            except Exception:
                pass

        if not raw_html and hasattr(plot, "_repr_html_"):
            try:
                h = plot._repr_html_()
                if isinstance(h, str) and h.strip():
                    raw_html = h
            except Exception:
                pass

        if not raw_html and hasattr(plot, "save"):
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w+", suffix=".html", delete=False, encoding="utf-8"
                ) as tmp:
                    tmp_path = tmp.name
                try:
                    plot.save(tmp_path)
                    with open(tmp_path, "r", encoding="utf-8") as f:
                        raw_html = f.read()
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
            except Exception:
                pass

        if not raw_html:
            return "<div style='color:white;'>Visualization generated but HTML export unsupported.</div>"

        # ── Inject CSS + faster zoom ──────────────────────────────────────────
        inject = """
<style>
  html, body {
    height: 100% !important;
    margin: 0 !important;
    overflow: hidden !important;
    background: #111827 !important;
  }
  canvas { display: block; }
</style>
<script>
  window.addEventListener('load', function () {
    var target = document.querySelector('canvas') || document.body;
    target.addEventListener('wheel', function (e) {
      if (!e._boosted) {
        # e.preventDefault();
        e.stopImmediatePropagation();
        var boosted = new WheelEvent('wheel', {
          bubbles: true, cancelable: true, composed: true,
          deltaX: e.deltaX * 3,
          deltaY: e.deltaY * 3,
          deltaZ: e.deltaZ,
          deltaMode: e.deltaMode,
          clientX: e.clientX, clientY: e.clientY,
          ctrlKey: e.ctrlKey, shiftKey: e.shiftKey, altKey: e.altKey,
        });
        boosted._boosted = true;
        e.target.dispatchEvent(boosted);
      }
    }, { capture: true, passive: false });
  });
</script>
"""
        if "</head>" in raw_html:
            raw_html = raw_html.replace("</head>", inject + "</head>", 1)
        else:
            raw_html = inject + raw_html

        return raw_html

    except Exception as e:
        logger.error(f"Error in generate_visualization: {e}", exc_info=True)
        return "<div style='color:white;'>Error computing visualizer map.</div>"