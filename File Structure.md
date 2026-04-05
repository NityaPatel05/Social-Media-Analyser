# Modular Build Order & Commit Structure

---

## Core Philosophy

Each module is a self-contained unit that works independently, can be committed meaningfully, and builds on the previous one. Never build frontend and backend simultaneously — finish backend module fully, commit, then build its frontend component. This gives you a clean commit history that shows genuine iteration.

---

## Module 0: Project Skeleton (Day 1)

Do this first, commit once, never touch again except to add new files.

```
project/
├── backend/
│   ├── main.py              # FastAPI app entry
│   ├── config.py            # all env vars, constants
│   ├── database/
│   │   ├── duckdb_client.py
│   │   └── chroma_client.py
│   ├── modules/
│   │   ├── ingestion/
│   │   ├── timeseries/
│   │   ├── network/
│   │   ├── spam/
│   │   ├── topics/
│   │   ├── lifecycle/
│   │   └── chatbot/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   └── api/
│   └── package.json
├── data/
│   └── data.jsonl
├── README.md
└── docker-compose.yml
```

**Commit**: `init: project skeleton, folder structure, empty modules`

---

## Module 1: Data Ingestion (Day 1)

**Files**: `backend/modules/ingestion/loader.py`, `backend/modules/ingestion/cleaner.py`, `backend/modules/ingestion/profiler.py`

**Build order within module**:

Step 1 — Write loader.py: read JSONL with DuckDB, return raw Polars dataframe. Commit: `feat(ingestion): load raw JSONL with DuckDB`

Step 2 — Write cleaner.py: normalize timestamps, compute full_text = title + selftext, deduplicate by MD5, flag malformed rows. Commit: `feat(ingestion): clean and normalize posts, dedup by hash`

Step 3 — Write profiler.py: field null rates, post count, date range, top authors, top subreddits, value distributions. Commit: `feat(ingestion): dataset profiler for schema validation`

Step 4 — Wire to FastAPI: `GET /data/summary` returns profiler output. Commit: `feat(api): data summary endpoint`

Step 5 — Fix any bugs found when hitting the endpoint with real data. Commit: `fix(ingestion): handle null selftext and malformed timestamps`

This last fix commit is important — it shows genuine iteration, not a first-try perfect implementation.

---

## Module 2: Time-Series (Day 2)

**Files**: `backend/modules/timeseries/aggregator.py`, `backend/modules/timeseries/anomaly.py`, `backend/modules/timeseries/summarizer.py`

**Build order**:

Step 1 — aggregator.py: hourly/daily/weekly counts from created_utc, rolling 7-day average, growth rate per day. Commit: `feat(timeseries): volume aggregation with rolling average and growth rate`

Step 2 — anomaly.py: Z-score computation, flag days beyond mean + 2 std, changepoint detection with ruptures. Commit: `feat(timeseries): anomaly detection with zscore and ruptures changepoints`

Step 3 — summarizer.py: takes actual data points as input, sends to Claude API, returns plain-language summary. Commit: `feat(timeseries): dynamic LLM summary generation via Claude API`

Step 4 — Wire all three to FastAPI: `GET /timeseries` with subreddit, keyword, date range params. Commit: `feat(api): timeseries endpoint with query params`

Step 5 — Frontend: TimeSeriesPage.jsx with Recharts line chart, anomaly markers, growth rate badge, LLM summary below chart. Commit: `feat(frontend): timeseries page with chart and LLM summary`

Step 6 — Edge case fixes after testing with empty date ranges, single-day datasets, subreddits with one post. Commit: `fix(timeseries): handle edge cases for sparse data and empty filters`

---

## Module 3: Spam Detection (Day 3)

**Files**: `backend/modules/spam/signals.py`, `backend/modules/spam/isolation_forest.py`, `backend/modules/spam/scorer.py`

**Build order**:

Step 1 — signals.py: compute all 7 per-author behavioral signals from raw data. Post frequency per hour, URL-to-post ratio, domain repetition rate, score-to-activity ratio, subreddit diversity, inter-post time entropy, near-duplicate rate via MinHash LSH. Commit: `feat(spam): rule-based behavioral signal extraction per author`

Step 2 — isolation_forest.py: takes signal vectors, fits IsolationForest with contamination=0.05, returns anomaly scores normalized to 0-1. Commit: `feat(spam): isolation forest anomaly scoring`

Step 3 — scorer.py: combines rule signals and IF score into final spam score, stores per author with signal breakdown. Commit: `feat(spam): final spam score aggregation with per-signal breakdown`

Step 4 — Wire to FastAPI: `GET /spam` with score threshold filter, `GET /accounts/{username}` for drilldown. Commit: `feat(api): spam endpoints with threshold filter and account drilldown`

Step 5 — Frontend: SpamPage.jsx with author list sorted by score, filter slider, stacked bar per author showing signal contributions, drilldown panel. Commit: `feat(frontend): spam investigation page with drilldown`

Step 6 — Fix after testing with authors who have only one post, authors with all nulls. Commit: `fix(spam): handle single-post authors and missing url fields`

---

## Module 4: Network Graphs (Day 4)

**Files**: `backend/modules/network/builder.py`, `backend/modules/network/metrics.py`, `backend/modules/network/exporter.py`

**Build order**:

Step 1 — builder.py: build Graph 1 (User-URL Bipartite) and Graph 2 (Author Co-Activity) as NetworkX objects from cleaned data. Commit: `feat(network): build user-url bipartite and author co-activity graphs`

Step 2 — metrics.py: compute PageRank, betweenness, degree centrality via iGraph, Leiden community detection, assign community colors and LLM-generated labels. Commit: `feat(network): centrality metrics and leiden community detection`

Step 3 — exporter.py: export graph as PyVis HTML, handle node removal recomputation, handle disconnected components without crashing. Commit: `feat(network): pyvis export with node removal and component handling`

Step 4 — Wire to FastAPI: `GET /network/{graph_type}` returning graph HTML and metrics JSON. Commit: `feat(api): network endpoints for both graph types`

Step 5 — Frontend: NetworkPage.jsx with graph selector, centrality toggle, node removal input, community legend, PyVis iframe. Commit: `feat(frontend): network explorer with centrality toggle and node removal`

Step 6 — Fix after stress testing: very small graphs, authors with one post, graphs where removal disconnects everything. Commit: `fix(network): graceful handling of post-removal disconnected graph`

---

## Module 5: Topic Clustering (Day 5)

**Files**: `backend/modules/topics/embedder.py`, `backend/modules/topics/clusterer.py`, `backend/modules/topics/visualizer.py`

**Build order**:

Step 1 — embedder.py: embed all full_text with BAAI/bge-small-en-v1.5, cache embeddings to disk so you never recompute. Commit: `feat(topics): sentence transformer embeddings with disk cache`

Step 2 — clusterer.py: BERTopic with tunable nr_topics, extract top terms per cluster, assign cluster to each post, handle outlier topic -1 as uncategorized. Commit: `feat(topics): bertopic clustering with tunable nr_topics`

Step 3 — visualizer.py: UMAP 2D reduction, prepare data for Nomic Atlas or DataMapPlot, color by cluster. Commit: `feat(topics): umap 2d reduction for embedding visualization`

Step 4 — Wire to FastAPI: `GET /topics` with nr_topics param. Commit: `feat(api): topics endpoint with nr_topics parameter`

Step 5 — Frontend: TopicPage.jsx with cluster slider, embedding scatter plot, per-cluster cards showing top terms, post count, dominant subreddits. Commit: `feat(frontend): topic explorer with cluster slider and embedding plot`

Step 6 — Fix extremes: nr_topics=2, nr_topics=50 on small dataset. Commit: `fix(topics): cap nr_topics at coherent maximum, ui warning for excess`

---

## Module 6: Narrative Lifecycle (Day 6)

This module depends on Module 5 (needs BERTopic clusters) and Module 2 (needs time-series per cluster). Build it after both.

**Files**: `backend/modules/lifecycle/curve_fitter.py`, `backend/modules/lifecycle/stage_classifier.py`, `backend/modules/lifecycle/early_adopters.py`

**Build order**:

Step 1 — curve_fitter.py: for each topic cluster extract its post volume time-series, fit log-normal curve via scipy.optimize.curve_fit, compute skewness via scipy.stats.skew. Commit: `feat(lifecycle): log-normal curve fitting and skewness per topic cluster`

Step 2 — stage_classifier.py: assign lifecycle stage per topic using growth rate + volume position + topic age logic. Output: Emerging / Peaking / Declining / Dead with badge color. Commit: `feat(lifecycle): lifecycle stage classification with growth rate logic`

Step 3 — early_adopters.py: identify accounts that posted within first 10% of topic volume window, cross-reference with spam scores, flag clusters where early adopters are predominantly spam accounts. Commit: `feat(lifecycle): early adopter detection with spam cross-reference`

Step 4 — Update topics endpoint to include lifecycle stage, skewness score, growth rate, early adopter list per cluster. Commit: `feat(api): lifecycle fields added to topics endpoint`

Step 5 — Frontend: update topic cluster cards to show lifecycle badge 🟢🔵🟡⚫, skewness score, growth rate, early adopter accounts. Add fitted curve overlay on time-series chart when a topic is selected. Commit: `feat(frontend): lifecycle badges and curve overlay on topic cards`

Step 6 — Fix after testing topics with very few posts, single-day topics, topics that never decay within dataset timeframe. Commit: `fix(lifecycle): handle short-lived and still-active topics at dataset boundary`

---

## Module 7: Chatbot and RAG (Day 7)

This is the last backend module because it depends on embeddings from Module 5, graph facts from Module 4, and topic summaries from Module 6.

**Files**: `backend/modules/chatbot/indexer.py`, `backend/modules/chatbot/retriever.py`, `backend/modules/chatbot/responder.py`

**Build order**:

Step 1 — indexer.py: store all three knowledge sources in ChromaDB. Post embeddings with metadata, graph account facts as natural language sentences, topic cluster summaries generated by Claude API. Commit: `feat(chatbot): chromadb indexing for posts, graph facts, topic summaries`

Step 2 — retriever.py: embed query, retrieve top-5 from all three collections, merge and rerank by cosine similarity. Handle empty query, short query, non-English query. Commit: `feat(chatbot): multi-source retrieval with reranking and edge case handling`

Step 3 — responder.py: pass merged context to Claude API with system prompt, stream response, make second API call for 3 suggested follow-up queries. Commit: `feat(chatbot): claude api response with streaming and followup suggestions`

Step 4 — Wire to FastAPI: `POST /chat` with streaming response. Commit: `feat(api): streaming chat endpoint`

Step 5 — Frontend: ChatPage.jsx with full-page chat interface, source badges on each result (post / graph / topic), suggested follow-up chips as clickable buttons. Commit: `feat(frontend): chat page with source attribution and followup chips`

Step 6 — Test with the three zero-overlap semantic examples from your README. Fix retrieval quality issues. Commit: `fix(chatbot): improve retrieval for zero keyword overlap queries`

---

## Module 8: Polish and Robustness (Day 8)

**Files**: various fixes across all modules

Step 1 — Overview dashboard page: summary stats, lifecycle badge distribution across all topics, top accounts by PageRank, global spam rate, active topics count. Commit: `feat(frontend): overview dashboard with summary stats`

Step 2 — Global spam filter: wire the spam score threshold slider to affect all pages — time-series excludes spam authors, network graph dims spam nodes, topic clusters show spam-adjusted post counts. Commit: `feat(frontend): global spam filter applied across all views`

Step 3 — Stress test every edge case from the rubric: empty search, very short query, non-English input, nr_topics extremes, node removal on small graph. Fix everything that breaks. Commit: `fix(robustness): edge case handling across all modules`

Step 4 — Docker compose final, environment variables documented, README with screenshots and ML component summary. Commit: `docs: readme with screenshots, ml components, semantic search examples`

Step 5 — Deploy backend to Railway, frontend to Vercel, test all endpoints on production. Commit: `deploy: production config for railway and vercel`

---

## Commit History Shape You Want

The evaluators will see something like this and it tells the right story:

```
init: project skeleton
feat(ingestion): load raw JSONL
feat(ingestion): clean and normalize
feat(ingestion): profiler
feat(api): data summary endpoint
fix(ingestion): handle null selftext        ← shows real iteration
feat(timeseries): aggregation
feat(timeseries): anomaly detection
feat(timeseries): llm summaries
fix(timeseries): sparse data edge cases     ← shows real iteration
... and so on per module
fix(robustness): final stress test fixes    ← shows you tested seriously
docs: readme and deployment
```

Every fix commit is as valuable as every feat commit. It proves you tested your own code rather than shipping the first version that ran without crashing.
