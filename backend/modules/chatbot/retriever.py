import logging
from sentence_transformers import SentenceTransformer
from langdetect import detect

logger = logging.getLogger(__name__)

# Cache model globally
EMBEDDER = None

def embed_query(text: str) -> list:
    global EMBEDDER
    if not text:
        return None
    if len(text) < 3:
        logger.warning("Query too short.")
        return None
        
    try:
        # Prevent PyTorch from spawning dozens of threads on a tiny AWS VM (which freezes/crashes it)
        import os
        os.environ["OMP_NUM_THREADS"] = "1"
        os.environ["MKL_NUM_THREADS"] = "1"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        
        if EMBEDDER is None:
            logger.info("Initializing query embedder (CPU limited) to prevent AWS crash...")
            EMBEDDER = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
            
        return EMBEDDER.encode([text])[0].tolist()
    except Exception as e:
        logger.error(f"Error embedding query: {e}")
        return None

def detect_language(text: str) -> str:
    try:
        if not text or len(text) < 3: return "unknown"
        return detect(text)
    except:
        return "unknown"

def retrieve(query: str, col_posts, col_graphs, col_topics, top_k: int = 5) -> dict:
    """
    RAG Retrieval from all sources, merged and reranked.
    """
    try:
        if not query:
            return {"error": "query_too_short", "message": "Please enter at least 3 characters", "results": [], "counts": {}}
            
        if len(query) < 3:
            return {"error": "query_too_short", "message": "Please enter at least 3 characters", "results": [], "counts": {}}
            
        lang = detect_language(query)
        
        q_emb = embed_query(query)
        if q_emb is None:
            return {"error": "embed_failed", "message": "Failed to map query", "results": [], "counts": {}}

        results = []
        counts = {"posts": 0, "graph_facts": 0, "topic_summaries": 0}
        
        def fetch(collection, tag):
            if not collection: return
            try:
                # n_results must be smaller than collection size, chromadb throws error if n_results > count
                size = collection.count()
                if size == 0: return
                limit = min(top_k, size)
                
                res = collection.query(query_embeddings=[q_emb], n_results=limit)
                if res and res.get("documents") and len(res["documents"][0]) > 0:
                    for i in range(len(res["documents"][0])):
                        dist = res["distances"][0][i]
                        # Convert to similarity assuming L2 or inner product space logic (Chroma default is l2, lower dist is better)
                        sim = 1.0 / (1.0 + dist) 
                        results.append({
                            "id": res["ids"][0][i] if "ids" in res and res["ids"] else None,
                            "text": res["documents"][0][i],
                            "source_type": tag,
                            "metadata": res["metadatas"][0][i] if res["metadatas"] else {},
                            "score": sim
                        })
                        counts[tag] += 1
            except Exception as ce:
                logger.error(f"Chroma retrieval error for {tag}: {ce}")
                
        fetch(col_posts, "posts")
        fetch(col_graphs, "graph_facts")
        fetch(col_topics, "topic_summaries")
        
        if len(results) == 0:
            return {"error": "no_results", "message": "No relevant content found", "results": [], "suggestions": [], "counts": counts, "detected_language": lang}
            
        # Sort by similarity score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        # Limit to top_k overal
        merged_top = results[:top_k]
        
        # update counts based on true top_k limit applied
        final_counts = {"posts": 0, "graph_facts": 0, "topic_summaries": 0}
        for r in merged_top:
            final_counts[r["source_type"]] += 1
            
        return {
            "results": merged_top,
            "counts": final_counts,
            "detected_language": lang,
            "message": "success",
            "error": None
        }
    except Exception as e:
        logger.error(f"Error in retrieve: {e}")
        return {"error": "exception", "message": "Failed to retrieve documents", "results": [], "counts": {}}


# ══════════════════════════════════════════════════════════════════════════════
# LangGraph integration — retrieve_node wraps retrieve() as a graph node.
# The node reads query + chroma collections from state and writes context_results
# back so the synthesize_node downstream can use them without any extra glue.
# ══════════════════════════════════════════════════════════════════════════════

# def retrieve_node(state: dict, col_posts, col_graphs, col_topics, top_k: int = 5) -> dict:
#     """
#     LangGraph node wrapper around retrieve().

#     Usage inside a StateGraph:
#         graph.add_node("retrieve", lambda s: retrieve_node(s, col_posts, col_graphs, col_topics))

#     Returns a partial state dict with 'context_results' populated.
#     """
#     query = state.get("query", "")
#     ret_res = retrieve(query, col_posts, col_graphs, col_topics, top_k=top_k)

#     if ret_res.get("error"):
#         logger.warning(f"[LangGraph] retrieve_node got error: {ret_res.get('message')}")
#         return {"context_results": [], "retrieve_error": ret_res.get("message")}

#     return {
#         "context_results":   ret_res["results"],
#         "retrieve_counts":   ret_res["counts"],
#         "detected_language": ret_res["detected_language"],
#     }
