import logging
import os
import polars as pl
from sentence_transformers import SentenceTransformer
import google.generativeai as genai

logger = logging.getLogger(__name__)

def _get_safe_batch_size(client, fallback: int = 100) -> int:
    """Derive a safe Chroma add() batch size across versions."""
    try:
        if client is not None and hasattr(client, "get_max_batch_size"):
            max_size = int(client.get_max_batch_size())
            if max_size > 0:
                return max_size
    except Exception as e:
        logger.warning(f"Unable to fetch Chroma max batch size, using fallback: {e}")
    return fallback

def run_indexer(df: pl.DataFrame, embeddings_res: dict, app_data: dict, client, col_posts, col_graphs, col_topics):
    """
    Index posts, graph facts, and topic summaries into ChromaDB collections.
    """
    try:
        if df is None or client is None:
            return
            
        posts_count = col_posts.count()
        if posts_count > 0 and posts_count == len(df):
            logger.info("ChromaDB collections already populated. Skipping re-indexing.")
            return

        logger.info("Starting ChromaDB Indexing...")
        
        # 1. Index Posts
        embeddings = embeddings_res.get("embeddings", [])
        post_ids = embeddings_res.get("post_ids", [])
        
        if len(embeddings) > 0 and len(embeddings) == len(df):
            docs = []
            metas = []
            ids = []
            
            # Using polars to dictionaries
            records = df.to_dicts()
            
            # If spam_scores available
            spam_scores = app_data.get("spam_scores", {})
            assignments = app_data.get("topics", {}).get("assignments", [])
            topics_data = app_data.get("topics", {}).get("cached_data", {})
            
            for i, row in enumerate(records):
                docs.append(str(row.get("full_text", " ")))
                
                auth = row.get("author", "")
                spam_s = spam_scores.get(auth, {}).get("spam_score", 0.0)
                
                # Fetch lifecycle stage? This requires topic assigning. 
                # Our lifecycle stage runs per topic. The prompt says "store in posts collection metadata: lifecycle_stage".
                # We haven't stored lifecycle stage anywhere global yet. Let's just default to UNKNOWN or pass "" and update later.
                # Actually, the user says "Source 1... metadata: subreddit, author, score, created_utc, spam_score, lifecycle_stage".
                
                stage = "UNKNOWN"
                if len(assignments) > i:
                    tid = str(assignments[i])
                    # If we generated topic stages securely:
                    topic_meta = topics_data.get("stages", {}).get(tid)
                    if topic_meta:
                        stage = topic_meta.get("stage", "UNKNOWN")
                
                meta = {
                    "subreddit": str(row.get("subreddit", "")),
                    "author": auth,
                    "score": int(row.get("score", 0)) if row.get("score") else 0,
                    "created_utc": str(row.get("created_utc", "")),
                    "spam_score": float(spam_s),
                    "lifecycle_stage": stage
                }
                metas.append(meta)
                ids.append(f"post_{post_ids[i]}")
                
            batch_size = _get_safe_batch_size(client, fallback=100)
            for i in range(0, len(docs), batch_size):
                col_posts.add(
                    documents=docs[i:i+batch_size],
                    embeddings=embeddings[i:i+batch_size].tolist(),
                    metadatas=metas[i:i+batch_size],
                    ids=ids[i:i+batch_size]
                )
            logger.info(f"Indexed {len(docs)} posts.")
        
        # We need the model for graph/topic embeddings
        model = SentenceTransformer("BAAI/bge-small-en-v1.5")
        
        # 2. Index Graph Facts
        network_metrics = app_data.get("network", {}).get("metrics2", {})
        if network_metrics and "metrics" in network_metrics:
            metrics = network_metrics["metrics"]
            assignments = network_metrics.get("assignments", {})
            labels = network_metrics.get("labels", {})
            
            # top 20 by PageRank
            sorted_nodes = sorted(metrics.items(), key=lambda item: item[1].get("pagerank", 0), reverse=True)[:20]
            
            g_docs = []
            g_metas = []
            g_ids = []
            
            for rank, (node, m) in enumerate(sorted_nodes):
                pr = m.get("pagerank", 0.0)
                group_id = str(assignments.get(node, {}).get("group", "Unknown"))
                label = labels.get(group_id, {}).get("label", "Unknown Group")
                
                # Retrieve top domain / top subreddits for this author
                auth_df = df.filter(pl.col("author") == node)
                subs = auth_df["subreddit"].unique().to_list() if len(auth_df) > 0 else []
                top_subreddits = ", ".join(subs[:3]) if subs else "Unknown"
                
                domains = auth_df.filter(pl.col("url_domain").is_not_null())["url_domain"].to_list() if "url_domain" in auth_df.columns else []
                top_domain = max(set(domains), key=domains.count) if domains else "None"
                
                s_score = spam_scores.get(node, {}).get("spam_score", 0.0)
                
                # Format: "Author {name} is a {stage} community member in the {community_label} group, with PageRank {score:.3f}, primarily sharing content from {top_domain}, active in {top_subreddits}, spam score {spam_score:.2f}"
                # prompt doesn't specify stage for author natively... perhaps "key" or "active"?
                fact = f"Author {node} is a community member in the {label} group, with PageRank {pr:.3f}, primarily sharing content from {top_domain}, active in {top_subreddits}, spam score {s_score:.2f}."
                
                g_docs.append(fact)
                g_metas.append({"author": node, "pagerank": pr, "community": label})
                g_ids.append(f"graph_{rank}_{node}")
                
            if g_docs:
                g_embs = model.encode(g_docs, show_progress_bar=False).tolist()
                batch_size = _get_safe_batch_size(client, fallback=100)
                for i in range(0, len(g_docs), batch_size):
                    col_graphs.add(
                        documents=g_docs[i:i+batch_size],
                        embeddings=g_embs[i:i+batch_size],
                        metadatas=g_metas[i:i+batch_size],
                        ids=g_ids[i:i+batch_size],
                    )
                logger.info(f"Indexed {len(g_docs)} graph facts.")
                
        # 3. Index Topic Summaries
        topics_res = app_data.get("topics", {}).get("cached_data", {})
        if topics_res and "top_terms" in topics_res:
            t_docs = []
            t_metas = []
            t_ids = []
            
            from config import get_gemini_api_key, mark_gemini_key_exhausted, increment_gemini_key_usage

            t_assigns = app_data.get("topics", {}).get("assignments", [])
            for tid, terms in topics_res["top_terms"].items():
                if tid == "-1": continue
                
                # get 5 sample post titles
                sample_titles = []
                for idx, assigned_tid in enumerate(t_assigns):
                    if str(assigned_tid) == tid:
                        t = df["title"][idx]
                        if t: sample_titles.append(str(t))
                        if len(sample_titles) >= 5: break

                prompt = f"Summarize this social media topic in EXACTLY 2 sentences. Top terms: {terms}. Sample posts: {' | '.join(sample_titles)}"
                
                api_key = get_gemini_api_key()
                if api_key:
                    try:
                        genai.configure(api_key=api_key)
                        llm = genai.GenerativeModel("gemini-2.5-flash")
                        increment_gemini_key_usage(api_key)
                        res = llm.generate_content(prompt, generation_config=genai.types.GenerationConfig(max_output_tokens=150, temperature=0.3))
                        desc = res.text.replace('"', '').strip()
                    except Exception as e:
                        err_str = str(e)
                        if "GenerateRequestsPerDay" in err_str or ("429" in err_str and "limit: 20" in err_str) or "Quota exceeded" in err_str:
                            mark_gemini_key_exhausted(api_key)
                            logger.warning("Gemini key exhausted in indexer — marked for 24h.")
                        desc = f"A discussion cluster focused on {terms}. Sample posts: {' | '.join(sample_titles)}"
                else:
                    desc = f"A discussion cluster focused on {terms}. Sample posts: {' | '.join(sample_titles)}"
                    
                stage_data = topics_res.get("stages", {}).get(tid, {})
                stage = stage_data.get("stage", "UNKNOWN")
                skew = stage_data.get("skewness", 0.0)
                gr = stage_data.get("growth_rate", 0.0)
                
                t_docs.append(desc)
                t_metas.append({
                    "topic_id": tid, 
                    "lifecycle_stage": stage, 
                    "skewness": float(skew), 
                    "growth_rate": float(gr)
                })
                t_ids.append(f"topic_{tid}")
                
            if t_docs:
                t_embs = model.encode(t_docs, show_progress_bar=False).tolist()
                batch_size = _get_safe_batch_size(client, fallback=100)
                for i in range(0, len(t_docs), batch_size):
                    col_topics.add(
                        documents=t_docs[i:i+batch_size],
                        embeddings=t_embs[i:i+batch_size],
                        metadatas=t_metas[i:i+batch_size],
                        ids=t_ids[i:i+batch_size],
                    )
                logger.info(f"Indexed {len(t_docs)} topic summaries.")
                
        logger.info("ChromaDB Indexing Complete.")
    except Exception as e:
        logger.error(f"Error in run_indexer: {e}")
