import logging
import networkx as nx
import polars as pl
from itertools import combinations
from collections import defaultdict
import urllib.parse
import re

logger = logging.getLogger(__name__)

def extract_domain(text: str) -> str:
    """Extract domain from the first URL found, else return None."""
    if not text: return None
    urls = re.findall(r'(https?://[^\s]+)', text)
    if urls:
        try:
            return urllib.parse.urlparse(urls[0]).netloc
        except:
            return None
    return None

def build_graph_1(df: pl.DataFrame) -> nx.Graph:
    """
    Build Graph 1 (User-URL Bipartite).
    Nodes: authors (type=user) and domains (type=domain).
    Filter: domains shared by at least 2 authors.
    """
    try:
        G = nx.Graph()
        if df is None or len(df) == 0:
            return G

        if "url_domain" not in df.columns:
            df = df.with_columns(
                pl.col("full_text").map_elements(extract_domain, return_dtype=pl.String).alias("url_domain")
            )
            
        edge_weights = defaultdict(int)
        domain_authors = defaultdict(set)
        
        for row in df.iter_rows(named=True):
            author = row.get("author")
            domain = row.get("url_domain")
            if author and domain:
                edge_weights[(author, domain)] += 1
                domain_authors[domain].add(author)
                
        for (author, domain), weight in edge_weights.items():
            if len(domain_authors[domain]) >= 2:
                if not G.has_node(author):
                    G.add_node(author, type="user", label=author)
                if not G.has_node(domain):
                    G.add_node(domain, type="domain", label=domain)
                G.add_edge(author, domain, weight=weight)
                
        logger.info(f"Graph 1 built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        return G
    except Exception as e:
        logger.error(f"Error building Graph 1: {e}")
        return nx.Graph()

def build_graph_2(df: pl.DataFrame) -> nx.Graph:
    """
    Build Graph 2 (Author Co-Activity).
    Edge if: posted in same subreddit within 24h AND share at least 1 URL domain.
    Wait >= 2 co-occurrences.
    """
    try:
        G = nx.Graph()
        if df is None or len(df) == 0:
            return G
            
        if "url_domain" not in df.columns:
            df = df.with_columns(
                pl.col("full_text").map_elements(extract_domain, return_dtype=pl.String).alias("url_domain")
            ).with_columns(pl.col("url_domain").cast(pl.String).fill_null("").alias("url_domain"))
        else:
            df = df.with_columns(pl.col("url_domain").cast(pl.String).fill_null("").alias("url_domain"))
            
        # Add basic info per author for the domain overlap lookup
        author_domains = defaultdict(set)
        for row in df.select(["author", "url_domain"]).iter_rows():
            if row[1]: 
                author_domains[row[0]].add(row[1])

        co_occurrences = defaultdict(int)
        
        # Optimize by grouping by subreddit
        df = df.sort("created_utc")
        subreddits = df["subreddit"].unique().to_list()
        
        for sub in subreddits:
            sub_df = df.filter(pl.col("subreddit") == sub)
            posts = sub_df.select(["author", "created_utc"]).to_dicts()
            
            # Use sliding window of 24h
            n = len(posts)
            for i in range(n):
                for j in range(i + 1, n):
                    auth_i = posts[i]["author"]
                    auth_j = posts[j]["author"]
                    
                    if auth_i == auth_j:
                        continue
                        
                    delta = (posts[j]["created_utc"] - posts[i]["created_utc"]).total_seconds()
                    if delta > 86400: # 24 hours in seconds
                        break # since sorted, subsequent posts are also >24h away
                        
                    # Both conditions: within 24h (checked) AND share domain
                    if len(author_domains[auth_i].intersection(author_domains[auth_j])) > 0:
                        pair = tuple(sorted([auth_i, auth_j]))
                        co_occurrences[pair] += 1
                        
        for (u, v), weight in co_occurrences.items():
            if weight >= 2:
                if not G.has_node(u):
                    G.add_node(u, type="user", label=u)
                if not G.has_node(v):
                    G.add_node(v, type="user", label=v)
                G.add_edge(u, v, weight=weight)
                
        logger.info(f"Graph 2 built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        return G
    except Exception as e:
        logger.error(f"Error building Graph 2: {e}")
        return nx.Graph()
