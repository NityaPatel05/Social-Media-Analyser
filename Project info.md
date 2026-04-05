# Final Complete System — Everything in One Place

---

## Data Layer

**Tools**: DuckDB, Polars, `dateutil`, `hashlib`, `langdetect`

**Steps**:

1. Schema profiler — detect fields, null rates, value distributions
2. Compute full_text = title + selftext
3. Normalize created_utc to UTC datetime
4. Deduplicate by (author, created_utc, MD5 of full_text)
5. Extract any hashtag-like keywords from text manually
6. Flag malformed rows into separate bad_rows collection, never drop them

---

## Time-Series Analysis

Tools: DuckDB for aggregations, Polars for rolling windows, ruptures for changepoint detection, Recharts or Plotly.js for frontend charts, Gemini API (with multi-key usage tracking) for dynamic summaries

Functionalities:

Hourly, daily, weekly post volume aggregations
Rolling 7-day average overlaid on raw counts
Z-score anomaly flagging (mean + 2 standard deviations)
Changepoint detection via ruptures to programmatically find narrative momentum shifts
Every chart gets a dynamic LLM-generated plain-language summary sent to Gemini API with actual data points as context, response streamed back, never hardcode

## Narrative Lifecycle Tracking

This is your unique feature. Used by RAND Corporation, NATO StratCom, and Graphika in real influence operation reports.

**Tools**: BERTopic for topic clusters, Polars for time-series per cluster, `scipy.stats` for skewness computation, `scipy.optimize` for curve fitting, Gemini API for per-topic summaries

**Implementation**:

For each BERTopic cluster, extract its post volume time-series. Fit a log-normal curve to the volume distribution using `scipy.optimize.curve_fit`. Compute three metrics from the actual volume shape:

Skewness via `scipy.stats.skew` — high positive skew with fast decay is the red flag for artificial amplification because coordinated accounts stop posting simultaneously, creating a cliff-drop that organic trends never show. Organic trends follow a roughly symmetric log-normal rise and fall.

Growth rate as (posts_today - posts_yesterday) / posts_yesterday — computed daily for each topic cluster, not just globally.

Early adopter ratio — identify accounts that posted within the first 10% of the topic's total volume window. High concentration of flagged spam accounts in the early adopter group is a strong artificial amplification signal. These are your origin accounts.

**Lifecycle stage assignment logic**:

- Emerging: growth rate positive and high, volume below peak, topic age young
- Peaking: growth rate near zero or slightly positive, volume at maximum
- Declining: growth rate negative, volume falling from peak
- Dead: no posts in last N days relative to dataset timeframe, or volume near zero

**Visual badges displayed on each topic card**:

- 🟢 Emerging
- 🔵 Peaking
- 🟡 Declining
- ⚫ Dead

Each topic card also shows: top terms, post count, dominant subreddits, growth rate value, skewness score, and a one-line LLM-generated summary of what the narrative is about. Clicking a topic card opens the full time-series with the fitted curve overlaid, the early adopter accounts listed, and the propagation chain visualized.

---

## Two Network Graphs

**Tools**: NetworkX for construction, iGraph for centrality, `leidenalg` for community detection, Cytoscape.js for interactive frontend rendering

**Graph 1 — User-URL Bipartite**
Nodes: authors one side, URLs other side. Edges: author shared that URL, weight = frequency. Cluster URL nodes by domain. Answers which users coordinate around the same links, which domains are pushed across communities, which authors are link spammers. This is your primary coordination evidence graph.

**Graph 2 — Author Co-Activity Graph**
Nodes: authors. Edge between two authors if they posted in same subreddit within similar time window AND share URL domain overlap. Edge weight = behavioral similarity score. Run PageRank for influence, betweenness for information brokers, degree for raw activity — togglable in UI. Leiden community detection, each community gets color and LLM-generated label. Node removal feature — remove high-centrality node, graph recomputes without crashing. Disconnected components handled explicitly.

---

## Spam Detection — 2 Layers

**Layer 1 — Rule-Based Behavioral Signals**
Tools: pure Python, `hashlib`, `datasketch` for MinHash LSH, `scipy.stats` for entropy

Per-author signals:

- Post frequency per hour from created_utc
- URL-to-post ratio
- Domain repetition rate — same domain across all posts
- Score-to-activity ratio — high activity with near-zero scores
- Subreddit diversity — posting only in one or two subreddits repeatedly with same URL
- Inter-post time entropy via Shannon entropy — near-zero means bot-like regularity
- Near-duplicate rate via MinHash LSH at 80% similarity threshold

**Layer 2 — Isolation Forest**
Tools: scikit-learn `IsolationForest`, contamination=0.05

Feed all Layer 1 signals as feature vector per author. Flags statistical outliers with no labels needed. Most widely deployed unsupervised anomaly detection algorithm in production — used by Netflix, Twitter, and cybersecurity firms for exactly this type of behavioral anomaly detection.

**Dashboard spam features**:

- Spam score (0-1) badge per account
- Stacked bar showing contribution from rule-based versus Isolation Forest
- Global filter slider — exclude accounts above spam score threshold from all views including time-series and network graphs
- Drilldown panel per account: every signal breakdown, all posts, network neighborhood

---

## Topic Clustering and Embedding Visualization

**Tools**: BERTopic, UMAP, HDBSCAN, `sentence-transformers`, DataMapPlot

**Implementation**:

- Embed all full_text with `BAAI/bge-small-en-v1.5`
- BERTopic runs UMAP then HDBSCAN then c-TF-IDF for topic labeling
- nr_topics exposed as tunable slider in UI, range 2 to 50
- At extremes: nr_topics=2 gives broad macro-themes, nr_topics=50 on small dataset gracefully caps via BERTopic's built-in topic reduction, UI shows warning if requested clusters exceed coherent maximum
- Outlier topic (-1) displayed separately as uncategorized, never crashes layout
- Reduce to 2D with UMAP, color points by cluster and lifecycle stage badge color, embed interactively via DataMapPlot HTML iframe

Each topic cluster card displays:

- Topic label and top terms
- Post count and dominant subreddits
- Growth rate value
- Skewness score
- Lifecycle badge 🟢🔵🟡⚫
- One-line LLM summary of the narrative

---

## Chatbot — Multi-Source RAG

**Tools**: `BAAI/bge-small-en-v1.5` for embeddings, ChromaDB with tagged collections, Gemini API (with max limits & rotation), FastAPI for streaming

**Three knowledge sources in ChromaDB**:

Source 1 — Post text embeddings: every post's full_text embedded and stored, metadata tags: subreddit, author, score, created_utc, spam_score, lifecycle_stage

Source 2 — Graph-derived account facts: top 20 accounts by PageRank, their community, dominant URLs and subreddits, spam score, written as natural language sentences. Answers "who are the most influential accounts" without searching post text.

Source 3 — Topic cluster summaries: each BERTopic cluster's top terms plus sample posts converted to a paragraph by Gemini API, stored with lifecycle stage and skewness score embedded in the text. Answers thematic questions and narrative questions.

**Query flow**:

1. Embed user query with same model
2. Retrieve top-5 from all three collections simultaneously
3. Merge and rerank by cosine similarity
4. Pass combined context to Gemini API with system prompt defining role as social media research analyst
5. Stream response back to frontend
6. Second small API call after response: Gemini proposes 3 related queries based on what it just analyzed, displayed as clickable chips

**Edge case handling**:

- Empty query: return helpful message, never embed empty string
- Under 3 characters: show warning in UI
- Non-English: detect with `langdetect`, show language badge, model handles multilingual
- Zero results: show "no relevant content found" with suggested alternatives

**Three README semantic search examples to include**:

- Query "economic anxiety driving political radicalization" returns posts about job loss and far-right communities with zero keyword overlap — correct because embedding captures semantic theme not words
- Query "foreign actors shaping domestic discourse" returns posts about state-backed media sharing patterns — correct because the concept maps semantically even with different vocabulary
- Query "communities vulnerable to manipulation" returns posts from low-engagement subreddits with high spam account activity — correct because the embedding space connects vulnerability signals to the concept

---

## Backend Architecture

**Tools**: FastAPI with async endpoints, DuckDB, ChromaDB, Polars, Redis for caching centrality scores and embeddings, Docker

**Endpoints**:

- `GET /timeseries` — hashtag, keyword, subreddit, date range params
- `GET /network/{graph_type}` — returns graph JSON for graph 1 or 2
- `GET /topics` — accepts nr_topics param, returns clusters with lifecycle labels
- `GET /spam` — returns spam scores with filter params
- `GET /accounts/{username}` — full drilldown
- `POST /chat` — accepts query, returns streamed response with source attribution

---

## Frontend Architecture

**Tools**: React with Vite, Recharts for time-series, DataMapPlot iframe for embeddings, Cytoscape.js for interactive network graphs, TailwindCSS

**Pages**:

- Overview: summary stats, lifecycle badge distribution, top accounts, spam rate
- Time-Series Explorer: query bar, chart with changepoints annotated, growth rate indicator, dynamic LLM summary below
- Network Explorer: graph selector (2 graphs), centrality toggle, node removal tool, community legend
- Topic Explorer: cluster slider, embedding visualization, per-cluster cards with lifecycle badges and skewness scores
- Spam Investigation: account list sorted by spam score, filter slider, drilldown panel
- Chatbot: full page chat, source badges showing which knowledge layer each result came from (post / graph / topic), suggested follow-up chips

---

## Deployment

Backend: Railway or Render free tier, Docker container, environment variables for all API keys. Frontend: Vercel. ChromaDB: persistent volume on Railway. Total deployment under 2 hours once code is ready.

---

## README ML Component Summary (Exact Format They Want)

- Embeddings: `BAAI/bge-small-en-v1.5`, 384-dim, cosine similarity, via `sentence-transformers`
- Topic modeling: BERTopic, nr_topics tunable 2-50, UMAP 2D reduction, HDBSCAN min_cluster_size=10
- Anomaly detection: IsolationForest, contamination=0.05, 7 behavioral features, via scikit-learn
- Narrative lifecycle: log-normal curve fit via `scipy.optimize`, skewness via `scipy.stats`, growth rate computed daily per cluster
- Community detection: Leiden algorithm, modularity-based, via `leidenalg`
- Centrality: PageRank + betweenness + degree, via iGraph
