## GLOBAL RULES — INCLUDE THESE IN EVERY SESSION

Paste this block at the top of every session alongside the session-specific prompt:

```
GLOBAL RULES (apply to every file you write):

1. LLM API: Use Google Gemini API (gemini-1.5-flash model) for ALL LLM calls.
   Never use Claude API or OpenAI API anywhere in the code.
   Use the official google-generativeai Python SDK.
   API key must be read from environment variable GEMINI_API_KEY.
   Example usage:
     import google.generativeai as genai
     genai.configure(api_key=os.environ["GEMINI_API_KEY"])
     model = gegenerate_contentnai.GenerativeModel("gemini-1.5-flash")
     response = model.(prompt)
     return response.text

2. LOGGING: Every Python file must import and use the standard logging module.
   Configure at module level:
     import logging
     logger = logging.getLogger(__name__)
   Use logger.info() for normal operations, logger.warning() for soft failures,
   logger.error() for caught exceptions. Never use print() statements in production code.

3. EXCEPTION HANDLING: Every function that touches external resources (file I/O,
   database queries, API calls, model inference, ChromaDB operations) must be wrapped
   in try/except. Catch specific exceptions, not bare except. Log the exception with
   logger.error(f"...: {e}") and either raise a clean HTTPException for API routes
   or return a safe fallback value for internal functions. Never let an unhandled
   exception reach the user.

4. EDGE CASES: Every function must explicitly handle:
   - Empty inputs (empty string, empty list, empty dataframe)
   - None values in any field
   - Single-row datasets
   - Division by zero in any metric computation
   - API timeouts (wrap all external API calls with a timeout parameter)

5. ENVIRONMENT VARIABLES: Never hardcode API keys or secrets. All secrets must come
   from environment variables loaded via python-dotenv. Include a .env.example file
   listing every required variable with a placeholder value.

6. MODULAR STRUCTURE: Follow File_Structure.md exactly. Each file does one thing.
   No business logic in main.py or route files — those only call module functions.

7. COMMENTS: Every function must have a one-line docstring explaining what it does
   and what it returns. No inline comments explaining obvious code.
```

---

## SESSION 0 — Project Skeleton

```
Using File_Structure.md as your guide, create the full project skeleton.

Tasks:
- Create all folders and empty __init__.py files as shown in the folder tree
- Create main.py with FastAPI app, CORS middleware, and health check endpoint GET /health
- Create config.py that loads all environment variables via python-dotenv
- Create .env.example with placeholders for: GEMINI_API_KEY, CHROMA_DB_PATH, DATA_PATH, REDIS_URL
- Create docker-compose.yml with services: backend (FastAPI), redis
- Create requirements.txt with all Python dependencies from Project_info.md plus:
  google-generativeai, python-dotenv, loguru
- Create frontend with Vite + React + TailwindCSS scaffold
- Create package.json for frontend

Apply all GLOBAL RULES. Every file needs logging even if it only logs startup.
Commit message: init: project skeleton, folder structure, empty modules
```

---

## SESSION 1 — Data Ingestion Module

```
Build Module 1 from File_Structure.md. Reference Project_info.md Data Layer section.

Files to create:
- backend/modules/ingestion/loader.py
- backend/modules/ingestion/cleaner.py
- backend/modules/ingestion/profiler.py
- backend/database/duckdb_client.py

Detailed requirements:

loader.py:
- Read data.jsonl using DuckDB, return a Polars dataframe
- Log row count and file size on successful load
- Raise a clean error if file does not exist or is malformed

cleaner.py:
- Compute full_text = title + " " + selftext, handle null selftext gracefully
- Normalize created_utc to UTC datetime using dateutil
- Deduplicate rows by MD5 hash of (author + created_utc + full_text)
- Flag malformed rows (null author, null created_utc, empty full_text after concat)
  into a separate bad_rows list, never drop them from processing
- Detect language of full_text using langdetect, store as lang field
- Log how many rows were deduplicated and how many were flagged as malformed

profiler.py:
- Return: total post count, date range, top 10 authors by post count,
  top 10 subreddits by post count, null rates per field, language distribution
- Handle dataset with only 1 row without crashing

Wire to FastAPI:
- GET /data/summary returns profiler output as JSON
- GET /data/bad-rows returns flagged malformed rows

Apply all GLOBAL RULES. Every function needs try/except and logging.
After writing all files, show me what the fix commit should address —
deliberately identify one real edge case that would break the current code.
```

---

## SESSION 2 — Time-Series Module

```
Build Module 2 from File_Structure.md. Reference Project_info.md Time-Series section.

Files to create:
- backend/modules/timeseries/aggregator.py
- backend/modules/timeseries/anomaly.py
- backend/modules/timeseries/summarizer.py

Detailed requirements:

aggregator.py:
- Accept filter params: keyword (searches full_text), subreddit, author, date_start, date_end
- Return aggregated post counts at hourly, daily, and weekly granularity
- Compute rolling 7-day average using Polars
- Compute daily growth rate: (posts_today - posts_yesterday) / posts_yesterday
  Handle division by zero: return 0.0 if yesterday count is zero
- Handle filter that returns zero posts: return empty structure with a clear message field,
  never crash

anomaly.py:
- Compute Z-score per day, flag days where Z > 2.0 as anomalies
- Run ruptures PELT algorithm for changepoint detection
- Return list of anomaly dates and list of changepoint dates
- Handle time-series with fewer than 7 data points gracefully (skip rolling average,
  skip changepoints, return warning message in response)

summarizer.py:
- Accept actual data points (dates + counts + anomaly flags) as input dict
- Build a prompt string from the data, send to Gemini API (gemini-1.5-flash)
- Return plain-language summary suitable for non-technical audience
- If Gemini API call fails, return a fallback template-based summary using the data
  so the UI never shows an empty summary box
- Log Gemini API latency for every call

Wire to FastAPI:
- GET /timeseries with query params: keyword, subreddit, author, date_start, date_end, granularity
- Response includes: data points, anomalies, changepoints, growth_rate, llm_summary

Frontend (TimeSeriesPage.jsx):
- Search bar for keyword/subreddit filter
- Recharts LineChart with anomaly markers as red dots
- Growth rate badge (green if positive, red if negative)
- LLM summary paragraph below chart
- Loading skeleton while summary streams

Apply all GLOBAL RULES.
```

---

## SESSION 3 — Spam Detection Module

```
Build Module 3 from File_Structure.md. Reference Project_info.md Spam Detection section.

Files to create:
- backend/modules/spam/signals.py
- backend/modules/spam/isolation_forest.py
- backend/modules/spam/scorer.py

Detailed requirements:

signals.py:
- Compute per-author feature vector with exactly these 7 signals:
  1. post_freq_per_hour: total posts / total hours active
  2. url_to_post_ratio: posts with non-null URL / total posts
  3. domain_repetition_rate: most common domain count / total URL posts
  4. score_to_activity_ratio: mean score / post count (handle 0 post count)
  5. subreddit_diversity: unique subreddits / total posts (1.0 = max diversity)
  6. inter_post_entropy: Shannon entropy of inter-post time intervals in seconds
     (return 0.0 for authors with only 1 post)
  7. near_duplicate_rate: fraction of posts with Jaccard similarity > 0.8
     to any other post by same author, computed via MinHash LSH (datasketch)
- Return as Polars dataframe with author as index
- Log min/max/mean of each signal for monitoring

isolation_forest.py:
- Accept signal dataframe, fit IsolationForest with contamination=0.05, random_state=42
- Normalize anomaly scores from [-1,1] to [0,1] where 1 = most anomalous
- Return per-author anomaly scores
- Handle case where fewer than 10 authors exist: skip IF, return 0.0 for all

scorer.py:
- Combine rule signal scores and IF score into final spam_score
- Weight: IF score = 0.5, rule-based signals combined = 0.5
- For rule signals: normalize each to 0-1, weight equally
- Store per-author: spam_score, if_score, each individual signal value
- Return as dict keyed by author

Wire to FastAPI:
- GET /spam?threshold=0.5 returns authors above threshold sorted by score
- GET /accounts/{username} returns full signal breakdown + all posts by that author
  + spam score + network neighborhood (top 5 co-active authors from Graph 2)

Frontend (SpamPage.jsx):
- Author list sorted by spam score with colored score badge
- Filter slider (0 to 1) that updates list in real time
- Click author to open drilldown panel:
  - Horizontal stacked bar showing each signal contribution
  - Post history table
  - Spam score explanation in plain text

Apply all GLOBAL RULES.
```

---

## SESSION 4 — Network Graphs Module

```
Build Module 4 from File_Structure.md. Reference Project_info.md Two Network Graphs section.

Files to create:
- backend/modules/network/builder.py
- backend/modules/network/metrics.py
- backend/modules/network/exporter.py

Detailed requirements:

builder.py:
- Build Graph 1 (User-URL Bipartite):
  Nodes: authors (type=user) and domains extracted from URLs (type=domain)
  Edges: author → domain, weight = number of posts sharing that domain
  Filter: only include domains shared by at least 2 different authors
  (singleton domain nodes add noise, not signal)
- Build Graph 2 (Author Co-Activity):
  Nodes: authors
  Edge between two authors if BOTH conditions true:
    - posted in same subreddit within 24-hour window
    - share at least 1 URL domain
  Edge weight = number of such co-occurrences
  Filter: only include edges with weight >= 2
- Log node count and edge count for each graph
- Handle empty graph (zero edges after filtering) without crashing

metrics.py:
- Convert NetworkX graph to iGraph for computation
- Compute: PageRank (damping=0.85), betweenness centrality, degree centrality
- Run Leiden community detection via leidenalg
- Assign each community an integer ID and a color from a fixed palette
- For each community, send top 5 most connected node names to Gemini API
  and get a 3-word label (e.g. "climate news sharers")
- Return: per-node metrics dict, community assignments, community labels
- Handle disconnected graph: compute metrics on each component separately,
  never pass disconnected graph to a layout algorithm expecting connected input

exporter.py:
- Export graph as PyVis HTML with physics simulation enabled
- Color nodes by community, size nodes by PageRank score
- Return HTML string for embedding as iframe
- Implement node_removal(graph, node_id): remove node, recompute metrics,
  return new PyVis HTML — must not crash even if removed node was the only
  connection keeping components together
- Handle graph with 0 or 1 nodes after removal

Wire to FastAPI:
- GET /network/1 returns Graph 1 HTML + metrics JSON
- GET /network/2 returns Graph 2 HTML + metrics JSON
- POST /network/remove-node body: {graph_type, node_id} returns recomputed graph

Frontend (NetworkPage.jsx):
- Tab selector for Graph 1 vs Graph 2
- PyVis graph as iframe
- Centrality toggle (PageRank / Betweenness / Degree) updates node sizing
- Node removal: text input + button, graph refreshes without page reload
- Community legend with color swatches and LLM-generated labels

Apply all GLOBAL RULES.
```

---

## SESSION 5 — Topic Clustering Module

```
Build Module 5 from File_Structure.md. Reference Project_info.md Topic Clustering section.

Files to create:
- backend/modules/topics/embedder.py
- backend/modules/topics/clusterer.py
- backend/modules/topics/visualizer.py

Detailed requirements:

embedder.py:
- Load BAAI/bge-small-en-v1.5 via sentence-transformers
- Embed all full_text values, return numpy array
- Cache embeddings to disk at path from config (embeddings.npy + post_ids.npy)
- On startup: if cache exists and post count matches, load from cache
  If cache is stale or missing, recompute and save
- Log embedding time and cache hit/miss status
- Handle empty text: replace with single space before embedding, never crash

clusterer.py:
- Run BERTopic with nr_topics parameter (default 10, min 2, max 50)
- If nr_topics exceeds number of coherent clusters BERTopic finds,
  cap at actual number and return a warning field in response
- Assign each post its topic_id (use -1 for outliers, label as "Uncategorized")
- Extract top 10 terms per topic
- Return: per-post topic assignments, per-topic top terms, topic sizes
- Handle nr_topics=2 and nr_topics=50 without crashing
- Also return per-topic time-series (daily post counts per cluster)
  so time-series page can filter by topic

visualizer.py:
- Run UMAP on embeddings: n_components=2, n_neighbors=15, min_dist=0.1
- Return 2D coordinates + topic labels for each post
- Format output for DataMapPlot: labels, coordinates, hover text (post title truncated to 60 chars)
- Generate static DataMapPlot HTML, return as string for embedding
- Handle single-cluster case (all posts in one topic) without crashing UMAP

Wire to FastAPI:
- GET /topics?nr_topics=10 returns clusters + per-topic time-series + warning if capped
- GET /topics/embedding returns UMAP 2D data + DataMapPlot HTML

Frontend (TopicPage.jsx):
- Slider for nr_topics (2 to 50), updates on release not on drag
- Show warning banner if nr_topics was capped
- DataMapPlot visualization embedded as iframe or div
- Grid of topic cards (see topic card spec in Project_info.md)
  Cards update when slider changes

Apply all GLOBAL RULES.
```

---

## SESSION 6 — Narrative Lifecycle Module

```
Build Module 6 from File_Structure.md. Reference Project_info.md Narrative Lifecycle section.
This module depends on Module 5 (BERTopic clusters) and Module 2 (time-series per cluster).
Build after both are working.

Files to create:
- backend/modules/lifecycle/curve_fitter.py
- backend/modules/lifecycle/stage_classifier.py
- backend/modules/lifecycle/early_adopters.py

Detailed requirements:

curve_fitter.py:
- For each topic cluster, extract daily post count time-series
- Fit log-normal curve using scipy.optimize.curve_fit
  If fit fails (too few points, singular matrix), catch the RuntimeError,
  log a warning, and return None for curve params
- Compute skewness via scipy.stats.skew
  High positive skew (> 1.0) with fast decay = artificial amplification signal
- Compute daily growth rate per cluster: (today - yesterday) / yesterday
  Handle yesterday = 0 case
- Return per-topic: skewness, growth_rate_series, curve_params or None, fit_success flag

stage_classifier.py:
- Assign lifecycle stage per topic using this exact logic:
  EMERGING: growth_rate > 0.2 AND current_volume < peak_volume * 0.7
  PEAKING: abs(growth_rate) <= 0.2 AND current_volume >= peak_volume * 0.7
  DECLINING: growth_rate < -0.1 AND current_volume > 0
  DEAD: no posts in last 7 days of dataset timeframe OR total posts < 3
- Return stage as string and badge color:
  Emerging → "🟢", Peaking → "🔵", Declining → "🟡", Dead → "⚫"
- Edge cases: topics that appear only on a single day get DEAD
  Topics that are still growing at dataset boundary get EMERGING with
  a note field: "may still be active beyond dataset range"

early_adopters.py:
- For each topic, identify the first 10% of posts by created_utc
- Extract unique authors from those posts
- Cross-reference with spam scores from Module 3
- Return: early_adopter_authors list, spam_account_fraction in early adopters,
  amplification_flag = True if spam_account_fraction > 0.3
- Handle topic with fewer than 5 posts: return empty early adopters,
  set amplification_flag = False

Update topics endpoint:
- Add lifecycle_stage, badge_emoji, skewness, growth_rate, early_adopters,
  amplification_flag, curve_fit_success to each topic object in GET /topics response

Frontend updates:
- Add lifecycle badge emoji to each topic card
- Add skewness score tooltip: "High skew may indicate artificial amplification"
- Add growth rate indicator (arrow up/down with percentage)
- When topic card is clicked, show time-series with fitted curve overlaid
  (use dashed line for fitted curve, solid for actual data)
- Show early adopter accounts list with spam badges

Apply all GLOBAL RULES.
```

---

## SESSION 7 — Chatbot and RAG Module

```
Build Module 7 from File_Structure.md. Reference Project_info.md Chatbot section.
This is the final backend module. Build after Modules 4, 5, and 6 are complete.

Files to create:
- backend/modules/chatbot/indexer.py
- backend/modules/chatbot/retriever.py
- backend/modules/chatbot/responder.py
- backend/database/chroma_client.py

Detailed requirements:

chroma_client.py:
- Initialize ChromaDB persistent client at path from config
- Create three named collections: "posts", "graph_facts", "topic_summaries"
- Return client and collection handles
- Handle case where ChromaDB path does not exist: create directory

indexer.py:
- Source 1 (posts): embed all full_text with BAAI/bge-small-en-v1.5,
  store in "posts" collection with metadata:
  subreddit, author, score, created_utc (as string), spam_score, lifecycle_stage
- Source 2 (graph_facts): for top 20 authors by PageRank from Graph 2,
  write natural language sentence per author:
  "Author {name} is a {stage} community member in the {community_label} group,
  with PageRank {score:.3f}, primarily sharing content from {top_domain},
  active in {top_subreddits}, spam score {spam_score:.2f}"
  Embed and store in "graph_facts" collection
- Source 3 (topic_summaries): for each BERTopic cluster, send top terms +
  5 sample post titles to Gemini API, get back a 2-sentence topic description,
  store with metadata: topic_id, lifecycle_stage, skewness, growth_rate
- Log count of documents indexed per collection
- Implement check: if collections already populated and post count matches,
  skip re-indexing (expensive operation)

retriever.py:
- embed_query(text): embed with same model, handle empty string (return None),
  handle text under 3 chars (return None with warning)
- retrieve(query, top_k=5): query all three collections, merge results,
  rerank by cosine similarity score, return top_k with source tag
- detect_language(text): use langdetect, return language code,
  handle langdetect failure (return "unknown")
- All edge cases must return structured response, never raise unhandled exception:
  empty query → {"error": "query_too_short", "message": "Please enter at least 3 characters"}
  zero results → {"results": [], "message": "No relevant content found", "suggestions": [...]}
  non-English → proceed normally, add detected_language field to response

responder.py:
- Build system prompt: "You are a social media research analyst. Answer questions
  about Reddit data using only the provided context. Be precise and cite specific
  authors, subreddits, or topics from the context when relevant."
- Build user prompt: context documents + user query
- Send to Gemini API (gemini-1.5-flash), return response text
- Follow-up suggestions: after main response, make second Gemini call:
  "Based on the query '{query}' and the analysis just performed,
  suggest exactly 3 related research questions as a JSON array of strings."
  Parse response as JSON, return as suggestions list
  If JSON parse fails, return empty suggestions list (never crash)
- Log query, retrieval count per source, response latency

Wire to FastAPI:
- POST /chat body: {query: string}
  Response: {answer, sources: [{text, source_type, metadata}], suggestions: [str, str, str],
             detected_language, retrieval_counts: {posts, graph_facts, topic_summaries}}
- Streaming: implement as Server-Sent Events so frontend can stream tokens

Frontend (ChatPage.jsx):
- Full-page chat interface
- Each assistant message shows:
  - Answer text (streamed token by token)
  - Collapsible "Sources" section showing retrieved documents with
    colored badge: blue=post, green=graph, purple=topic
  - Three suggestion chips below the answer (clickable, auto-fills query bar)
- Language badge if non-English detected
- Empty query shows helper text, does not submit

Apply all GLOBAL RULES.
Three README semantic search examples to document:
1. Query: "economic anxiety driving political radicalization"
   Expected: posts about job loss and far-right subreddits
   Why correct: semantic theme of economic fear → radicalization maps in embedding space
2. Query: "foreign actors shaping domestic discourse"
   Expected: posts about state-backed media sharing patterns
   Why correct: concept of external influence on local narratives is semantically equivalent
3. Query: "communities vulnerable to manipulation"
   Expected: posts from low-engagement subreddits with high spam account activity
   Why correct: vulnerability + manipulation maps to low-resistance + high-spam clusters
```

---

## SESSION 8 — Overview Dashboard and Global Spam Filter

```
Build the Overview page and wire the global spam filter across all pages.
Reference Module 8 in File_Structure.md.

Overview page (OverviewPage.jsx):
- Summary stats cards: total posts, unique authors, date range, subreddits count
- Lifecycle badge distribution: count of Emerging/Peaking/Declining/Dead topics
  shown as a small bar chart
- Top 5 authors by PageRank with spam score badge
- Global spam rate: percentage of authors above spam_score 0.5
- Most active subreddits: top 10 bar chart
- Recent anomalies: list of dates flagged as anomalies across all subreddits

Global spam filter:
- Add a floating filter bar at top of every page
- Slider 0.0 to 1.0, label: "Exclude accounts with spam score above:"
- When changed, all pages re-fetch their data with spam_threshold param
- Backend: all endpoints accept optional spam_threshold query param
  and exclude authors above threshold from all computations
- Network graph: dim (not remove) spam nodes with opacity 0.2
- Time-series: exclude spam author posts from counts
- Topic cards: show spam-adjusted post count alongside raw count

Apply all GLOBAL RULES.
```

---

## SESSION 9 — Robustness, Deployment, Documentation

```
Final session. Stress test every rubric edge case and prepare for deployment.

Edge cases to test and fix:
- Chatbot: empty string query
- Chatbot: single character query "a"
- Chatbot: non-English query (try Hindi: "सोशल मीडिया पर क्या हो रहा है")
- Topics: nr_topics=2
- Topics: nr_topics=50 (or max)
- Topics: nr_topics=0 (invalid — show error, do not crash)
- Network: remove the highest-PageRank node
- Network: remove a node that does not exist (show error, do not crash)
- Time-series: keyword that matches zero posts
- Time-series: date range with no data
- Spam: author with only 1 post
- Spam: dataset with fewer than 10 authors total

For each fix: write a targeted fix, not a full rewrite.
Commit each fix separately as fix(module): description.

Deployment:
- Finalize docker-compose.yml: backend + redis services
- Add Railway deployment config: railway.json with start command
- Add Vercel config: vercel.json pointing to frontend/dist
- Confirm all environment variables are in .env.example
- Write health check: GET /health returns {status: ok, db: ok, chroma: ok, gemini: reachable}
  Test Gemini reachability with a trivial 1-token call

README sections to write:
1. Project overview: what it does, what dataset it uses, what story it tells
2. Architecture diagram (simple text diagram is fine)
3. Setup instructions: clone, copy .env.example, docker-compose up, npm run dev
4. ML component summary (exact format from Project_info.md)
5. Three semantic search examples (exact format from rubric)
6. Screenshots: one per page
7. Known limitations and future extensions
   (mention multi-platform as future extension to cover the nice-to-have gap)
8. Deployment URL

Apply all GLOBAL RULES to any new code written.
```

---

## GEMINI API REFERENCE — Paste this if Claude forgets

```python
# Install: pip install google-generativeai
import google.generativeai as genai
import os
import logging

logger = logging.getLogger(__name__)

def get_gemini_response(prompt: str, max_tokens: int = 1000) -> str:
    try:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.3
            )
        )
        logger.info(f"Gemini call successful, tokens approx {len(response.text.split())}")
        return response.text
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        return ""  # always return string, never raise to caller
```

---

## LOGGING REFERENCE — Paste this if Claude forgets

```python
# At top of every file:
import logging
logger = logging.getLogger(__name__)

# In main.py, configure once for whole app:
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),           # console
        logging.FileHandler("app.log")     # file
    ]
)
```

---

## EXCEPTION HANDLING TEMPLATE — Paste this if Claude forgets

```python
# For FastAPI route functions:
from fastapi import HTTPException

async def get_something():
    try:
        result = some_module.compute()
        if result is None:
            raise HTTPException(status_code=404, detail="No data found")
        return result
    except HTTPException:
        raise  # re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Unexpected error in get_something: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# For internal module functions:
def compute_metric(data):
    try:
        if data is None or len(data) == 0:
            logger.warning("compute_metric called with empty data, returning 0.0")
            return 0.0
        result = ... # actual computation
        return result
    except ZeroDivisionError:
        logger.warning("Division by zero in compute_metric, returning 0.0")
        return 0.0
    except Exception as e:
        logger.error(f"compute_metric failed: {e}")
        return 0.0
```

---

## WHAT TO TELL CLAUDE IF IT GOES OFF-TRACK

If Claude starts rewriting files from scratch instead of making targeted edits, say:

> "Do not rewrite the entire file. Make only the targeted change needed to fix this issue.
> Show me exactly which lines change and why."

If Claude uses print() instead of logging, say:

> "Replace all print() statements with the appropriate logger call.
> Use logger.info for normal output, logger.warning for soft failures,
> logger.error for exceptions."

If Claude uses Claude API or OpenAI API instead of Gemini, say:

> "You must use Google Gemini API only. Replace this with the Gemini reference
> implementation from the GLOBAL RULES section."

If Claude skips exception handling, say:

> "Add try/except to every function that touches external resources.
> Use the exception handling template from the GLOBAL RULES section."
