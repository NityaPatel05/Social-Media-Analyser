import logging
import math
import hashlib
import json
import networkx as nx
import igraph as ig
import leidenalg
import os
import time
import google.generativeai as genai

logger = logging.getLogger(__name__)

COLOR_PALETTE = ["#ef4444", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#14b8a6"]

from config import get_gemini_api_key, mark_gemini_key_exhausted, increment_gemini_key_usage

# ── Persistent label cache ────────────────────────────────────────────────────
# Key: SHA-256 of sorted top-node list  →  Value: label string
# Survives for the process lifetime so the same community is only labelled once,
# even if compute_metrics() is called again after a node removal.
_label_cache: dict[str, str] = {}


def _community_key(top_nodes: list) -> str:
    """Stable hash for a community regardless of node order."""
    return hashlib.sha256(json.dumps(sorted(top_nodes)).encode()).hexdigest()[:16]


def _safe_float(v: float) -> float:
    """Replace NaN/Inf with 0.0 so JSON serialisation never fails."""
    if not isinstance(v, (int, float)):
        return 0.0
    if math.isnan(v) or math.isinf(v):
        return 0.0
    return float(v)


def get_community_label(top_nodes: list) -> str:
    """
    Use Gemini to label a community from top node names.
    Results are cached by community fingerprint — identical node sets never
    trigger a second API call.
    """
    # ── Cache hit ─────────────────────────────────────────────────────────────
    cache_key = _community_key(top_nodes)
    if cache_key in _label_cache:
        logger.info(f"Community label cache HIT for key {cache_key} — skipping Gemini call.")
        return _label_cache[cache_key]

    # ── Quota guard ───────────────────────────────────────────────────────────
    api_key = get_gemini_api_key()
    if not api_key:
        logger.info("All Gemini API keys exhausted or none provided — skipping label call.")
        return "Unknown Cluster"

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")

        prompt = f"""
        You are a social media analyst. Here are the top 5 most influential users or domains
        in a networked cluster: {', '.join(top_nodes)}.
        Please provide a concise 3-word label summarizing the nature of this community.
        Return ONLY the 3 words.
        """
        # Throttle: stay under 5 req/min rate limit
        time.sleep(13)
        increment_gemini_key_usage(api_key)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(max_output_tokens=20, temperature=0.3)
        )
        if not response.candidates or not response.candidates[0].content.parts:
            logger.warning("Gemini returned no content parts (safety filter). Using default label.")
            return "Unknown Cluster"

        label = response.text.replace('"', '').strip()
        # Store in cache so this community is never re-labelled
        _label_cache[cache_key] = label
        logger.info(f"Community label cached: '{label}' (key={cache_key})")
        return label

    except Exception as e:
        err_str = str(e)
        logger.error(f"Gemini API call failed for label: {e}")
        if "GenerateRequestsPerDay" in err_str or ("429" in err_str and "limit: 20" in err_str) or "Quota exceeded" in err_str:
            mark_gemini_key_exhausted(api_key)
            logger.warning("Gemini daily quota exhausted for this key — marked for 24h.")
        return "Unknown Cluster"


def convert_nx_to_ig(G_nx: nx.Graph) -> ig.Graph:
    """Convert NetworkX graph to iGraph with weights."""
    g = ig.Graph()
    if G_nx.number_of_nodes() == 0:
        return g

    g.add_vertices(list(G_nx.nodes()))

    for node, data in G_nx.nodes(data=True):
        g.vs.find(name=node)["type"]  = data.get("type",  "user")
        g.vs.find(name=node)["label"] = data.get("label", str(node))

    edges = list(G_nx.edges(data=True))
    g.add_edges([(e[0], e[1]) for e in edges])
    g.es["weight"] = [e[2].get("weight", 1.0) for e in edges]
    return g


def compute_metrics(G_nx: nx.Graph) -> dict:
    """
    Convert to iGraph, compute PageRank, Betweenness, Degree.
    Run Leiden community detection (capped at 7 partitions to limit
    Gemini label calls). Labels are cached — repeated calls for the same
    community composition consume zero additional quota.
    """
    try:
        if G_nx.number_of_nodes() == 0:
            return {"metrics": {}, "assignments": {}, "labels": {}}

        g = convert_nx_to_ig(G_nx)

        metrics = {}
        for comp in g.components():
            subgraph  = g.induced_subgraph(comp)
            degrees   = subgraph.degree()
            betweenness = subgraph.betweenness(directed=False)
            pageranks = subgraph.pagerank(damping=0.85)

            for idx, vertex in enumerate(subgraph.vs):
                metrics[vertex["name"]] = {
                    "degree":      _safe_float(degrees[idx]),
                    "betweenness": _safe_float(betweenness[idx]),
                    "pagerank":    _safe_float(pageranks[idx]),
                }

        # Community detection — cap at 7 so we never burn more than 7 label calls per graph
        partition = leidenalg.find_partition(
            g, leidenalg.ModularityVertexPartition, weights=g.es["weight"]
        )

        assignments = {}
        labels      = {}
        names       = g.vs["name"]

        # Merge smallest communities if over the cap
        MAX_COMMUNITIES = len(COLOR_PALETTE)  # 7
        parts = list(enumerate(partition))
        if len(parts) > MAX_COMMUNITIES:
            # Keep top MAX_COMMUNITIES by size, merge rest into last slot
            parts.sort(key=lambda x: len(x[1]), reverse=True)
            main_parts  = parts[:MAX_COMMUNITIES]
            overflow    = parts[MAX_COMMUNITIES:]
            overflow_ix = MAX_COMMUNITIES - 1  # merge into last community slot
            for _, node_indices in overflow:
                main_parts[overflow_ix][1].extend(node_indices)  # type: ignore[attr-defined]
            parts = main_parts

        for slot, (_, node_indices) in enumerate(parts):
            color = COLOR_PALETTE[slot % len(COLOR_PALETTE)]

            comm_nodes_pr = [(names[idx], metrics[names[idx]]["pagerank"]) for idx in node_indices]
            comm_nodes_pr.sort(key=lambda x: x[1], reverse=True)
            top_5 = [item[0] for item in comm_nodes_pr[:5]]

            for idx in node_indices:
                assignments[names[idx]] = {"group": slot, "color": color}

            label = get_community_label(top_5)
            labels[str(slot)] = {"label": label, "color": color}

        return {"metrics": metrics, "assignments": assignments, "labels": labels}

    except Exception as e:
        logger.error(f"Error computing metrics: {e}")
#         return {"metrics": {}, "assignments": {}, "labels": {}}

