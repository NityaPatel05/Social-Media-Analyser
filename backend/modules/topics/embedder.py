import logging
import os
import time
import numpy as np
import polars as pl
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

CACHE_DIR = "data/cache"

def embed_posts(df: pl.DataFrame) -> dict:
    """
    Load BAAI/bge-small-en-v1.5. Embed full_text.
    Check cache first via post counts.
    """
    try:
        if df is None or len(df) == 0:
            return {"embeddings": np.array([]), "post_ids": []}
            
        os.makedirs(CACHE_DIR, exist_ok=True)
        emb_path = os.path.join(CACHE_DIR, "embeddings.npy")
        ids_path = os.path.join(CACHE_DIR, "post_ids.npy")
        
        # We'll use index/row numbers as proxies for post_ids if dataset lacks unique ids
        # or we just rely on order. 
        count = len(df)
        
        t0 = time.time()
        
        if os.path.exists(emb_path) and os.path.exists(ids_path):
            cached_ids = np.load(ids_path, allow_pickle=True)
            if len(cached_ids) == count:
                logger.info(f"Embeddings cache HIT. Loading {count} embeddings...")
                embeddings = np.load(emb_path)
                logger.info(f"Loaded in {time.time() - t0:.2f}s")
                return {"embeddings": embeddings, "post_ids": cached_ids.tolist()}
                
        logger.info("Embeddings cache MISS. Computing embeddings...")
        
        texts = df["full_text"].to_list()
        # Handle empty text
        texts = [t if t and str(t).strip() else " " for t in texts]
        
        model = SentenceTransformer("BAAI/bge-small-en-v1.5")
        embeddings = model.encode(texts, show_progress_bar=False)
        
        # generate ids if none
        post_ids = np.arange(count)
        
        np.save(emb_path, embeddings)
        np.save(ids_path, post_ids)
        
        logger.info(f"Computed embeddings in {time.time() - t0:.2f}s")
        return {"embeddings": embeddings, "post_ids": post_ids.tolist()}
        
    except Exception as e:
        logger.error(f"Error embedding posts: {e}")
        return {"embeddings": np.array([]), "post_ids": []}
