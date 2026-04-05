"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log"),
    ],
)

logger = logging.getLogger(__name__)

# Suppress ChromaDB's broken PostHog telemetry logging
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)

import math
import json

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import polars as pl
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from datetime import datetime


def sanitize_floats(obj):
    """Recursively walk a dict/list structure and replace any NaN/Inf float with 0."""
    if isinstance(obj, float):
        return 0.0 if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_floats(v) for v in obj]
    return obj


class SafeJSONResponse(JSONResponse):
    """JSONResponse that sanitizes NaN/Inf before serializing."""
    def render(self, content) -> bytes:
        cleaned = sanitize_floats(content)
        return json.dumps(cleaned, allow_nan=False).encode("utf-8")


from config import CORS_ORIGINS, DATA_PATH
from modules.ingestion.loader import load_data
from modules.ingestion.cleaner import clean_data
from modules.ingestion.profiler import profile_data

from modules.ingestion.profiler import profile_data

from modules.timeseries.aggregator import aggregate_timeseries
from modules.timeseries.anomaly import detect_anomalies
from modules.timeseries.summarizer import summarize_timeseries

from modules.spam.signals import compute_signals
from modules.spam.isolation_forest import run_isolation_forest
from modules.spam.scorer import compute_spam_scores

from modules.network.builder import build_graph_1, build_graph_2
from modules.network.metrics import compute_metrics
from modules.network.exporter import export_to_cytoscape, remove_node_and_recompute

from modules.topics.embedder import embed_posts
from modules.topics.clusterer import run_clustering
from modules.topics.visualizer import generate_visualization

from modules.lifecycle.curve_fitter import fit_topic_curve
from modules.lifecycle.stage_classifier import classify_stage
from modules.lifecycle.early_adopters import get_early_adopters

from database.chroma_client import get_chroma_client
from modules.chatbot.indexer import run_indexer
from modules.chatbot.retriever import retrieve
from modules.chatbot.responder import stream_response


from modules.spam.signals import compute_signals
from modules.spam.isolation_forest import run_isolation_forest
from modules.spam.scorer import compute_spam_scores

# Global state to hold data
app_data = {
    "df": pl.DataFrame(),
    "bad_rows": [],
    "profile": {},
    "spam_scores": {},
    "network": {
        "graph1": None,
        "graph2": None,
        "metrics1": {},
        "metrics2": {}
    },
    "topics": {
        "embeddings": None,
        "assignments": [],
        "top_terms": {},
        "html_map": "",
        "cached_data": {} # stores cluster outputs
    },
    "chroma": {
        "client": None,
        "col_posts": None,
        "col_graphs": None,
        "col_topics": None
    }
}

class ChatRequest(BaseModel):
    query: str

class NodeRemoveRequest(BaseModel):
    graph_type: int
    node_id: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI app."""
    try:
        logger.info(f"Loading data from {DATA_PATH}...")
        raw_df = load_data(DATA_PATH)
        cleaned_df, bad_rows = clean_data(raw_df)
        profile = profile_data(cleaned_df)
        
        logger.info("Loading or computing spam scores...")
        spam_scores_file = "data/spam_scores.json"
        
        # Ensure data dir exists
        os.makedirs("data", exist_ok=True)
        
        try:
            if os.path.exists(spam_scores_file):
                logger.info("Found cached spam scores. Loading from JSON...")
                with open(spam_scores_file, "r") as f:
                    spam_scores_cache = json.load(f)
            else:
                logger.info("Cache missed. Computing isolated forest spam scores...")
                signals_df = compute_signals(cleaned_df)
                signals_df = run_isolation_forest(signals_df)
                spam_scores_cache = compute_spam_scores(signals_df)
                
                # Save to cache
                with open(spam_scores_file, "w") as f:
                    json.dump(spam_scores_cache, f)
                logger.info("Saved computed spam scores to JSON cache.")
        except Exception as se:
            logger.error(f"Failed to load cache, recomputing: {se}")
            signals_df = compute_signals(cleaned_df)
            signals_df = run_isolation_forest(signals_df)
            spam_scores_cache = compute_spam_scores(signals_df)
        
        logger.info("Computing network graphs...")
        g1 = build_graph_1(cleaned_df)
        g2 = build_graph_2(cleaned_df)
        m1 = compute_metrics(g1)
        m2 = compute_metrics(g2)
        
        logger.info("Computing topic embeddings...")
        emb_res = embed_posts(cleaned_df)
        
        # Pre-cluster 10 topics to feed the indexer
        logger.info("Pre-clustering 10 topics for Chroma indexing...")
        topics_res = run_clustering(cleaned_df, emb_res["embeddings"], 10)
        
        # Calculate lifecycles for these topics
        global_max_date = cleaned_df["created_utc"].max()
        topics_res["stages"] = {}
        
        if "timeseries" in topics_res:
            for tid, ts_data in topics_res["timeseries"].items():
                if tid == "-1": continue
                
                counts = [x["count"] for x in ts_data]
                dates = [x["date"] for x in ts_data]
                
                curve = fit_topic_curve(counts)
                stage = classify_stage(dates, counts, curve["growth_rate"], global_max_date)
                early_adopters = get_early_adopters(cleaned_df, topics_res["assignments"], tid, spam_scores_cache)
                
                topics_res["stages"][tid] = {
                    "curve": curve,
                    "stage": stage["stage"],
                    "badge_emoji": stage["badge_emoji"],
                    "skewness": curve["skewness"],
                    "growth_rate": curve["growth_rate"],
                    "early_adopters": early_adopters["authors"],
                    "amplification_flag": early_adopters["amplification_flag"]
                }
        
        app_data["df"] = cleaned_df
        app_data["bad_rows"] = bad_rows
        app_data["profile"] = profile
        app_data["spam_scores"] = spam_scores_cache
        app_data["network"]["graph1"] = g1
        app_data["network"]["graph2"] = g2
        app_data["network"]["metrics1"] = m1
        app_data["network"]["metrics2"] = m2
        
        app_data["topics"]["embeddings"] = emb_res["embeddings"]
        app_data["topics"]["cached_data"] = topics_res
        app_data["topics"]["assignments"] = topics_res["assignments"]
        app_data["topics"]["top_terms"] = topics_res["top_terms"]
        
        logger.info("Initializing ChromaDB Indexer...")
        c_client, c_posts, c_graphs, c_topics = get_chroma_client()
        app_data["chroma"] = {
            "client": c_client,
            "col_posts": c_posts,
            "col_graphs": c_graphs,
            "col_topics": c_topics
        }
        
        run_indexer(cleaned_df, emb_res, app_data, c_client, c_posts, c_graphs, c_topics)

        logger.info("Data pipeline initialization complete.")
    except Exception as e:
        logger.error(f"Startup data loading failed: {e}")
    yield
    # Cleanup on shutdown
    app_data["df"] = pl.DataFrame()
    app_data["bad_rows"] = []

app = FastAPI(title="Social Media Narrative Intelligence", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    try:
        # Check DuckDB/df
        db_ok = app_data.get("df") is not None and len(app_data["df"]) > 0
        
        # Check Chroma
        chroma_ok = app_data.get("chroma", {}).get("client") is not None
        
        # Check Gemini
        gemini_ok = False
        try:
            import google.generativeai as genai
            from config import get_gemini_api_key
            api_key = get_gemini_api_key()
            if api_key:
                genai.configure(api_key=api_key)
                gemini_ok = True
            
            # Quota preservation: Do NOT make a live LLM request just for a health check ping.
            # model = genai.GenerativeModel("gemini-2.5-flash")
            # res = model.generate_content("Respond with exactly one word: OK", generation_config=genai.types.GenerationConfig(max_output_tokens=5))
            # if "OK" in res.text.upper() or "YES" in res.text.upper():
            #      gemini_ok = True
        except Exception as ge:
            logger.error(f"Gemini health check failed: {ge}")
            
        status = "ok" if db_ok and chroma_ok and gemini_ok else "degraded"
        
        return {
            "status": status,
            "db": "ok" if db_ok else "error",
            "chroma": "ok" if chroma_ok else "error",
            "gemini": "reachable" if gemini_ok else "unreachable"
        }
    except Exception as e:
        logger.error(f"Error in /health: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/data/summary")
async def get_summary():
    try:
        df = app_data.get("df")
        if df is None or len(df) == 0:
            return {"error": "Data not loaded yet"}
            
        total_posts = len(df)
        unique_authors = len(df["author"].unique())
        subreddits_count = len(df["subreddit"].unique())
        min_date = df["created_utc"].min()
        max_date = df["created_utc"].max()
        
        # global spam rate
        spam_scores = app_data.get("spam_scores", {})
        spam_count = sum(1 for v in spam_scores.values() if v.get("spam_score", 0.0) > 0.5)
        global_spam_rate = spam_count / len(spam_scores) if len(spam_scores) > 0 else 0.0
        
        # Top 10 subreddits
        subs = df.group_by("subreddit").agg(pl.len().alias("count")).sort("count", descending=True).limit(10).to_dicts()
        
        # Lifecycle badge distribution
        topics_res = app_data.get("topics", {}).get("cached_data", {})
        lifecycles = {"EMERGING": 0, "PEAKING": 0, "DECLINING": 0, "DEAD": 0}
        if topics_res and "stages" in topics_res:
            for tid, s_obj in topics_res["stages"].items():
                if tid == "-1": continue
                stage = s_obj.get("stage", "UNKNOWN")
                if stage in lifecycles: lifecycles[stage] += 1
                
        # Top 5 authors by PR
        top_authors = []
        metrics2 = app_data.get("network", {}).get("metrics2", {}).get("metrics", {})
        if metrics2:
            sorted_nodes = sorted(metrics2.items(), key=lambda item: item[1].get("pagerank", 0), reverse=True)
            # Filter to users only? Graph2 is authors only.
            for n, m in sorted_nodes[:5]:
                top_authors.append({
                    "author": n,
                    "pagerank": m.get("pagerank", 0),
                    "spam_score": spam_scores.get(n, {}).get("spam_score", 0.0)
                })
                
        # Recent anomalies
        ts_res = aggregate_timeseries(df)
        recent_anomalies = []
        if ts_res and "daily" in ts_res:
            daily = ts_res["daily"]
            from modules.timeseries.anomaly import detect_anomalies
            anoms = detect_anomalies(daily)
            if isinstance(anoms, dict):
                for a in anoms.get("anomalies", [])[-5:]: # top 5 recent
                    recent_anomalies.append(a)
                
        return {
            "total_posts": total_posts,
            "unique_authors": unique_authors,
            "subreddits_count": subreddits_count,
            "date_range": [str(min_date), str(max_date)],
            "global_spam_rate": float(global_spam_rate),
            "top_subreddits": subs,
            "lifecycles": lifecycles,
            "top_authors": top_authors,
            "recent_anomalies": recent_anomalies
        }
    except Exception as e:
        logger.error(f"Error in /data/summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/data/bad-rows")
async def get_bad_rows():
    """Return the list of malformed rows."""
    try:
        return app_data["bad_rows"]
    except Exception as e:
        logger.error(f"Error fetching bad rows: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


logger.info("FastAPI application initialized")

@app.get("/timeseries")
async def get_timeseries(subreddit: str = None, keyword: str = None, spam_threshold: float = 1.0):
    try:
        filtered_df = app_data["df"]
        if filtered_df is None or len(filtered_df) == 0:
            return {"error": "Data not loaded yet"}
            
        if spam_threshold < 1.0:
            # Filter out posts from spam authors
            spam_scores = app_data.get("spam_scores", {})
            valid_authors = [auth for auth, data in spam_scores.items() if data.get("spam_score", 0.0) <= spam_threshold]
            filtered_df = filtered_df.filter(pl.col("author").is_in(valid_authors))
            
        if subreddit:
            filtered_df = filtered_df.filter(pl.col("subreddit") == subreddit)
        if keyword:
            filtered_df = filtered_df.filter(pl.col("full_text").str.contains(f"(?i){keyword}"))
            
        # If no data left after filtering
        if len(filtered_df) == 0:
            # gracefully return empty structure
            return {"daily": [], "hourly": [], "weekly": [], "summary": "No data matches these filters.", "anomalies": []}
            
        res = aggregate_timeseries(filtered_df)
        anomalies = detect_anomalies(res.get("daily", []))
        summary = summarize_timeseries(res.get("weekly", []), anomalies)
        
        return {
            **res,
            "anomalies": anomalies,
            "summary": summary
        }
    except Exception as e:
        logger.error(f"Error in /timeseries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/spam")
async def get_spam(threshold: float = 0.5):
    try:
        results = []
        for auth, data in app_data.get("spam_scores", {}).items():
            if data["spam_score"] >= threshold:
                results.append({"author": auth, **data})
        return results
    except Exception as e:
        logger.error(f"Error in /spam: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/accounts/{username}")
async def get_account(username: str):
    try:
        user_data = app_data.get("spam_scores", {}).get(username)
        if not user_data:
            return {"author": username, "message": "Author not found in spam cache", "spam_score": 0.0, "signals": {}}
        
        # Fetch posts
        auth_df = app_data["df"].filter(pl.col("author") == username)
        posts = auth_df.to_dicts() if len(auth_df) > 0 else []
        
        return {
            "author": username,
            **user_data,
            "posts": posts,
            "network_neighborhood": [] # To be filled in Session 4
        }
    except Exception as e:
        logger.error(f"Error in /accounts/{{username}}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/network/{graph_id}")
async def get_network(graph_id: int, centrality: str = "pagerank", spam_threshold: float = 1.0):
    try:
        if graph_id == 1:
            g = app_data["network"]["graph1"]
            m = app_data["network"]["metrics1"]
        elif graph_id == 2:
            g = app_data["network"]["graph2"]
            m = app_data["network"]["metrics2"]
        else:
            raise HTTPException(status_code=400, detail="Invalid graph ID")

        elements = export_to_cytoscape(
            g,
            m.get("metrics", {}),
            m.get("assignments", {}),
            centrality,
            app_data.get("spam_scores", {}),
            spam_threshold,
        )
        return SafeJSONResponse(content={
            "elements": elements,
            "metrics": m
        })
    except Exception as e:
        logger.error(f"Error in /network/{{graph_id}}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/network/remove-node")
async def network_remove_node(req: NodeRemoveRequest):
    try:
        if req.graph_type == 1:
            g_obj = app_data["network"]["graph1"]
        elif req.graph_type == 2:
            g_obj = app_data["network"]["graph2"]
        else:
            raise HTTPException(status_code=400, detail="Invalid graph ID")
            
        if not g_obj.has_node(req.node_id):
            return {"error": True, "message": f"Node {req.node_id} does not exist"}

        res = remove_node_and_recompute(g_obj, req.node_id)

        # Persist the modified graph and recomputed metrics so subsequent
        # GET /network/{id} calls reflect the removed node.
        if res.get("new_graph") is not None:
            if req.graph_type == 1:
                app_data["network"]["graph1"] = res["new_graph"]
                app_data["network"]["metrics1"] = res["json"]
            else:
                app_data["network"]["graph2"] = res["new_graph"]
                app_data["network"]["metrics2"] = res["json"]

        return SafeJSONResponse(content={
            "elements": res["elements"],
            "metrics":  res["json"]
        })
    except Exception as e:
        logger.error(f"Error in /network/remove-node: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/topics")
async def get_topics(nr_topics: int = 10, spam_threshold: float = 1.0):
    try:
        if nr_topics < 2 or nr_topics > 50:
            return {"warning": "nr_topics must be between 2 and 50", "assignments": []}
            
        # We process clustering based on raw dataset to avoid recalculating heavy umap loops constantly.
        # But we filter the "sizes" output conditionally.
        res = app_data["topics"].get("cached_data", {})
        
        # Recluster only if nr_topics doesn't match roughly the current (taking warnings into account)
        current_len = len(res.get("sizes", {})) if res else 0
        if current_len != nr_topics and (not res.get("warning") or nr_topics < current_len):
            res = run_clustering(app_data["df"], app_data["topics"]["embeddings"], nr_topics)
            global_max_date = app_data["df"]["created_utc"].max()
            res["stages"] = {}
            if "timeseries" in res:
                for tid, ts_data in res["timeseries"].items():
                    if tid == "-1": continue
                    counts = [x["count"] for x in ts_data]
                    dates = [x["date"] for x in ts_data]
                    curve = fit_topic_curve(counts)
                    stage = classify_stage(dates, counts, curve["growth_rate"], global_max_date)
                    early_adopters = get_early_adopters(app_data["df"], res["assignments"], tid, app_data["spam_scores"])
                    res["stages"][tid] = {
                        "curve_data": curve["curve_data"], 
                        "curve_fit_success": curve["fit_success"],
                        "skewness": curve["skewness"],
                        "growth_rate": curve["growth_rate"],
                        "stage": stage["stage"],
                        "badge_emoji": stage["badge_emoji"],
                        "early_adopters": early_adopters["authors"],
                        "amplification_flag": early_adopters["amplification_flag"]
                    }
            app_data["topics"]["cached_data"] = res
            app_data["topics"]["assignments"] = res["assignments"]
            app_data["topics"]["top_terms"] = res["top_terms"]
            
        # Dynamically append filtered spam volume sizes
        if spam_threshold < 1.0 and res and "assignments" in res:
            res["spam_adjusted_sizes"] = {}
            df_authors = app_data["df"]["author"].to_list()
            spam_scores = app_data.get("spam_scores", {})
            for i, tid in enumerate(res["assignments"]):
                auth = df_authors[i]
                node_spam_score = spam_scores.get(auth, {}).get("spam_score", 0.0)
                if node_spam_score <= spam_threshold:
                    t_str = str(tid)
                    res["spam_adjusted_sizes"][t_str] = res["spam_adjusted_sizes"].get(t_str, 0) + 1
                    
        return res
    except Exception as e:
        logger.error(f"Error in /topics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/topics/embedding")
async def get_topics_embedding():
    try:
        # returns the interactive DataMapPlot HTML
        assigns = app_data["topics"].get("assignments", [])
        terms = app_data["topics"].get("top_terms", {})
        
        if not assigns:
            return HTMLResponse(content="<div style='color:white;text-align:center;'>No clustering data initialized yet.</div>")
            
        html = generate_visualization(app_data["df"], app_data["topics"]["embeddings"], assigns, terms)
        return HTMLResponse(content=html)
    except Exception as e:
        logger.error(f"Error in /topics/embedding: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """
    LangGraph-powered RAG chatbot endpoint.

    Flow:
      1. retrieve()    — embed query → search ChromaDB (posts, graphs, topics) → top-5 chunks
      2. stream_response() — LangGraph graph: synthesize_node (HF stream) → suggest_node (HF non-stream)
      3. Each SSE frame matches { type: 'meta'|'token'|'suggestions'|'error', content: ... }
    """
    try:
        query = req.query
        col_posts  = app_data["chroma"]["col_posts"]
        col_graphs = app_data["chroma"]["col_graphs"]
        col_topics = app_data["chroma"]["col_topics"]

        # Step 1 — RAG retrieval (unchanged, still uses sentence-transformers + ChromaDB)
        ret_res = retrieve(query, col_posts, col_graphs, col_topics, top_k=5)

        if ret_res.get("error"):
            # Return error as properly delimited SSE frames
            async def error_stream():
                yield f"data: {json.dumps({'type': 'error', 'content': ret_res.get('message')})}" + "\n\n"
                yield f"data: {json.dumps({'type': 'suggestions', 'content': ['Try a longer keyword', 'Search for specific subreddits']})}" + "\n\n"
            return StreamingResponse(error_stream(), media_type="text/event-stream")

        async def response_generator():
            # Send initial sources payload to UI instantly (before LLM starts)
            init_payload = {
                "type":     "meta",
                "sources":  ret_res["results"],
                "counts":   ret_res["counts"],
                "language": ret_res["detected_language"]
            }
            yield f"data: {json.dumps(init_payload)}" + "\n\n"

            # Step 2 — LangGraph: streams tokens then suggestions via HuggingFace Inference API
            async for chunk in stream_response(query, ret_res["results"]):
                yield chunk

        return StreamingResponse(response_generator(), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"Error in /chat: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        query = req.query
        col_posts = app_data["chroma"]["col_posts"]
        col_graphs = app_data["chroma"]["col_graphs"]
        col_topics = app_data["chroma"]["col_topics"]
        
        ret_res = retrieve(query, col_posts, col_graphs, col_topics, top_k=5)
        
        if ret_res.get("error"):
            # Return error as properly delimited SSE frames (actual newlines, not escaped \n)
            async def error_stream():
                yield f"data: {json.dumps({'type': 'error', 'content': ret_res.get('message')})}" + "\n\n"
                yield f"data: {json.dumps({'type': 'suggestions', 'content': ['Try a longer keyword', 'Search for specific subreddits']})}" + "\n\n"
            return StreamingResponse(error_stream(), media_type="text/event-stream")
            
        async def response_generator():
            # Send initial sources payload to UI instantly
            init_payload = {
                "type": "meta",
                "sources": ret_res["results"],
                "counts": ret_res["counts"],
                "language": ret_res["detected_language"]
            }
            # Use actual newline bytes — SSE requires \n\n between events
            yield f"data: {json.dumps(init_payload)}" + "\n\n"
            
            # Pipe tokens from responder (which also emits proper newlines)
            async for chunk in stream_response(query, ret_res["results"]):
                yield chunk
                
        return StreamingResponse(response_generator(), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"Error in /chat: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")






























# @app.post("/chat")
# async def chat_endpoint(req: ChatRequest):
#     """
#     LangGraph-powered RAG chatbot endpoint.

#     Flow:
#       1. retrieve()    — embed query → search ChromaDB (posts, graphs, topics) → top-5 chunks
#       2. stream_response() — LangGraph graph: synthesize_node (HF stream) → suggest_node (HF non-stream)
#       3. Each SSE frame matches { type: 'meta'|'token'|'suggestions'|'error', content: ... }
#     """
#     try:
#         query = req.query
#         col_posts  = app_data["chroma"]["col_posts"]
#         col_graphs = app_data["chroma"]["col_graphs"]
#         col_topics = app_data["chroma"]["col_topics"]

#         # Step 1 — RAG retrieval (unchanged, still uses sentence-transformers + ChromaDB)
#         ret_res = retrieve(query, col_posts, col_graphs, col_topics, top_k=5)

#         if ret_res.get("error"):
#             # Return error as properly delimited SSE frames
#             async def error_stream():
#                 yield f"data: {json.dumps({'type': 'error', 'content': ret_res.get('message')})}" + "\n\n"
#                 yield f"data: {json.dumps({'type': 'suggestions', 'content': ['Try a longer keyword', 'Search for specific subreddits']})}" + "\n\n"
#             return StreamingResponse(error_stream(), media_type="text/event-stream")

#         async def response_generator():
#             # Send initial sources payload to UI instantly (before LLM starts)
#             init_payload = {
#                 "type":     "meta",
#                 "sources":  ret_res["results"],
#                 "counts":   ret_res["counts"],
#                 "language": ret_res["detected_language"]
#             }
#             yield f"data: {json.dumps(init_payload)}" + "\n\n"

#             # Step 2 — LangGraph: streams tokens then suggestions via HuggingFace Inference API
#             async for chunk in stream_response(query, ret_res["results"]):
#                 yield chunk

#         return StreamingResponse(response_generator(), media_type="text/event-stream")
#     except Exception as e:
#         logger.error(f"Error in /chat: {e}")
#         raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/posts")
async def get_posts(id: str = None, author: str = None, date: str = None):
    try:
        df = app_data.get("df")
        if df is None or len(df) == 0:
            return {"error": "Data not loaded yet", "posts": []}
            
        filtered_df = df
        row_indices = []
        
        if id:
            # Handle RAG source ID (e.g., 'post_1234')
            if id.startswith("post_"):
                try:
                    idx = int(id.replace("post_", ""))
                    if 0 <= idx < len(filtered_df):
                        row_indices = [idx]
                except ValueError:
                    pass
            else:
                # If original reddit id
                if "id" in filtered_df.columns:
                    mask = filtered_df["id"] == id
                    row_indices = mask.arg_true().to_list()
        elif author:
            mask = filtered_df["author"] == author
            row_indices = mask.arg_true().to_list()
        elif date:
            mask = filtered_df["created_utc"].dt.strftime("%Y-%m-%d") == date
            row_indices = mask.arg_true().to_list()
            
        if not row_indices:
            return {"posts": []}
            
        # Cap to Top 50 to prevent huge payloads
        row_indices = row_indices[:50]
        
        posts = []
        spam_scores = app_data.get("spam_scores", {})
        assignments = app_data.get("topics", {}).get("assignments", [])
        topics_data = app_data.get("topics", {}).get("cached_data", {})
        
        for idx in row_indices:
            row = filtered_df.row(idx, named=True)
            auth = row.get("author", "")
            spam_s = spam_scores.get(auth, {}).get("spam_score", 0.0)
            
            # Extract topic assigning
            stage = "UNKNOWN"
            badge = "🟣"
            topic_id = "-1"
            if len(assignments) > idx:
                topic_id = str(assignments[idx])
                topic_meta = topics_data.get("stages", {}).get(topic_id)
                if topic_meta:
                    stage = topic_meta.get("stage", "UNKNOWN")
                    badge = topic_meta.get("badge_emoji", "🟣")
                    
            r_id = row.get("id", "")
            subreddit = row.get("subreddit", "unknown")
            permalink = row.get("permalink", f"https://reddit.com/r/{subreddit}/comments/{r_id}" if r_id else "")
            
            posts.append({
                "id": r_id,
                "internal_id": f"post_{idx}",
                "title": row.get("title", ""),
                "selftext": row.get("selftext", ""),
                "author": auth,
                "subreddit": subreddit,
                "score": row.get("score", 0),
                "permalink": permalink,
                "created_utc": str(row.get("created_utc", "")),
                "spam_score": round(float(spam_s), 3),
                "lifecycle_stage": stage,
                "badge": badge,
                "topic_id": topic_id
            })
            
        return {"posts": posts}
    except Exception as e:
        logger.error(f"Error in /posts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
