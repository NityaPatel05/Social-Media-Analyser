import logging
import math
import networkx as nx
from .metrics import compute_metrics

logger = logging.getLogger(__name__)


def _safe_float(v) -> float:
    """Replace NaN/Inf/None with 0.0."""
    try:
        f = float(v)
        return 0.0 if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return 0.0


def export_to_cytoscape(
    G_nx: nx.Graph,
    centralities: dict,
    assignments: dict,
    centrality_type: str = "pagerank",
    spam_scores: dict = None,
    spam_threshold: float = 1.0,
) -> dict:
    """
    Serialize a NetworkX graph as Cytoscape.js element arrays.

    Returns:
        {
            "nodes": [ { "data": { ... } }, ... ],
            "edges": [ { "data": { ... } }, ... ]
        }
    """
    if spam_scores is None:
        spam_scores = {}

    nodes = []
    edges = []

    for node in G_nx.nodes():
        node_str = str(node)
        m = centralities.get(node, {})
        pr   = _safe_float(m.get("pagerank",    0.001))
        betw = _safe_float(m.get("betweenness", 0.0))
        deg  = _safe_float(m.get("degree",      0.0))

        # Size scaled by chosen centrality
        if centrality_type == "pagerank":
            size = max(12, min(pr * 1500, 80))
        elif centrality_type == "betweenness":
            size = max(12, min(betw * 0.4, 80))
        else:  # degree
            size = max(12, min(deg * 4, 80))

        color      = assignments.get(node, {}).get("color", "#9ca3af")
        node_type  = G_nx.nodes[node].get("type", "user")
        shape      = "rectangle" if node_type == "domain" else "ellipse"

        node_spam = _safe_float(spam_scores.get(node, {}).get("spam_score", 0.0))
        filtered  = node_spam > spam_threshold

        nodes.append({
            "data": {
                "id":             node_str,
                "label":          node_str,
                "size":           round(size, 2),
                "color":          color,
                "shape":          shape,
                "filtered":       filtered,
                "spamScore":      round(node_spam, 4),
                "pagerank":       round(pr,   6),
                "betweenness":    round(betw, 4),
                "degree":         int(deg),
                "communityGroup": assignments.get(node, {}).get("group", -1),
            }
        })

    for idx, (u, v, data) in enumerate(G_nx.edges(data=True)):
        weight = max(1, _safe_float(data.get("weight", 1)))
        edges.append({
            "data": {
                "id":     f"e-{idx}",
                "source": str(u),
                "target": str(v),
                "weight": round(weight, 2),
            }
        })

    return {"nodes": nodes, "edges": edges}


def remove_node_and_recompute(G_nx: nx.Graph, node_id: str) -> dict:
    """
    Remove a node, recompute metrics, return Cytoscape elements + metrics JSON.
    """
    try:
        if G_nx is None:
            return {"elements": {"nodes": [], "edges": []}, "json": {}}

        H = G_nx.copy()
        if H.has_node(node_id):
            H.remove_node(node_id)

        if H.number_of_nodes() <= 1:
            logger.warning("Graph too small after removal.")
            return {
                "elements": {"nodes": [], "edges": []},
                "json": {"metrics": {}, "labels": {}, "assignments": {}},
            }

        res      = compute_metrics(H)
        elements = export_to_cytoscape(
            H,
            res.get("metrics", {}),
            res.get("assignments", {}),
        )

        return {
            "elements": elements,
            "json":     res,
            "new_graph": H,
        }

    except Exception as e:
        logger.error(f"Error in node removal: {e}")
        return {"elements": {"nodes": [], "edges": []}, "json": {}}
