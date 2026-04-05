# Nitya: Social Media Narrative Intelligence Platform

Nitya is a comprehensive social media narrative intelligence platform designed to ingest, process, and analyze massive troves of synthetic Reddit data. By leveraging state-of-the-art Natural Language Processing (NLP), unsupervised clustering, and anomaly detection algorithms, Nitya exposes exactly _how_ narratives spread, _who_ amplification actors are, and _when_ artificial manipulation occurs.

Nitya utilizes a synthetic dataset mimicking Reddit ecosystem structures to trace information flows, exposing exactly how organic discussions differ from coordinated bot campaigns.

## Architecture

```text
                       [ React Frontend (Vite) ]
                                |
                   (Axios / SSE Chat Streaming)
                                |
                    [ FastAPI Backend Layer ]
                   /            |            \
      [Data Profiler]   [Spam Detector]   [BERTopic Cluster]
           |                    |                 |
       (DuckDB)     (IsolationForest/LSH)   (UMAP/HDBSCAN)
           |                    |                 |
   [Time-Series API]     [Network Graphs]     [RAG Chatbot]
           |                    |                 |
        (Polars)     (NetworkX -> PyVis)     (ChromaDB)
```

## Setup Instructions

1. **Clone the Repository**

   ```bash
   git clone https://github.com/example/nitya.git
   cd nitya
   ```

2. **Configure Environment Variables**

   ```bash
   cp .env.example .env
   # Add your Google Gemini API Key inside .env
   ```

3. **Start the Backend (and Redis caching)**

   ```bash
   docker-compose up -d
   ```

4. **Launch the Frontend**

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

5. **Access the Portal**
   Navigate to `http://localhost:5173` in your browser.

## ML Component Summary

- **Anomaly Detection**: `PELT` (ruptures, pen=10, rbf model) for changepoints; `z-score` (scipy, threshold > 2.0) for spikes; `Isolation Forest` (scikit-learn, n_estimators=100, contamination=0.05) for spam.
- **Narrative Clustering**: `bge-small-en-v1.5` embeddings (sentence-transformers, dim=384); `UMAP` + `HDBSCAN` via BERTopic (tunable k=10-50 clusters, cosine distance); visualized via `datamapplot`.
- **Coordinate Graph Mapping**: `PageRank / Betweenness` (igraph, damping=0.85); `Leiden` (leidenalg, ModularityVertexPartition) capped at 7 partitions.
- **Semantic RAG Chatbot**: `Cosine Similarity` via `ChromaDB` (`bge-small-en-v1.5` 384-dim, top_k=5); `gemini-1.5-flash` via `google-generativeai` (temp=0.3) for response streaming.

## Semantic Search Examples

These three queries share **zero keyword overlap** with the indexed content — they succeed purely through semantic embedding similarity (BAAI/bge-small-en-v1.5 → ChromaDB cosine distance).

1. **Query**: `"economic anxiety driving political radicalization"`
   - **Result returned**: Posts from topic clusters centered on terms like `job, loss, economy, anger, politics` and graph facts about authors active in finance + political subreddits simultaneously.
   - **Why correct**: The embedding space maps "economic anxiety → radicalization" onto the same region as posts discussing job loss and political grievance, with no shared vocabulary.

2. **Query**: `"foreign actors shaping domestic discourse"`
   - **Result returned**: Topic summaries about coordinated URL-sharing patterns, graph facts for high-PageRank authors whose top domain is a known state-adjacent outlet, plus posts using synonyms like "propaganda", "influence operation".
   - **Why correct**: "foreign actors" semantically aligns with "coordinated inauthentic behavior" and "external influence" even though neither phrase appears in the query.

3. **Query**: `"communities resistant to new information"`
   - **Result returned**: Posts from low-diversity subreddits (single-topic, high echo-chamber score), and topic cluster summaries about repetitive content with low median post score.
   - **Why correct**: "resistant to new information" maps semantically onto "echo chamber", "low engagement diversity", and "repetitive narrative" — none of which appear verbatim in the query.

## Screenshots

- 📊 **Overview**: `docs/overview.png`
- 📈 **Time-Series**: `docs/timeseries.png`
- 🕸️ **Network Graph**: `docs/network.png`
- 🧠 **Topic Clusters**: `docs/topics.png`
- 🤖 **Chatbot Interface**: `docs/chat.png`

## Known Limitations and Future Extensions

Currently, Nitya is bound exclusively to Reddit data structures (subreddits, score thresholds). However, **multi-platform integration (Twitter/X, Telegram) is planned as a future extension**. Furthermore, real-time ingestion pipelines (Kafka) could replace the static Polars/DuckDB data-loading block for instant live streaming categorizations.

## Deployment URL

**[Nitya Dashboard (Demo)]()** _(Enter your deployed Vercel/Railway URLs here)_
