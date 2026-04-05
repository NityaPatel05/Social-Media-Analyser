import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import PostModal from "../components/PostModal";

const TOPIC_COLORS = [
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#ec4899",
  "#8b5cf6",
  "#14b8a6",
  "#ef4444",
];

export default function TimeSeriesPage({ spamThreshold }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState("");
  const [subreddit, setSubreddit] = useState("");
  // Committed filter values — only updated after debounce or button click
  const [committed, setCommitted] = useState({ keyword: "", subreddit: "" });

  // Topic trend state
  const [topicsData, setTopicsData] = useState(null);
  const [topicsLoading, setTopicsLoading] = useState(true);

  // Modal State
  const [modalPosts, setModalPosts] = useState(null);

  const handleDotClick = async (dateStr) => {
    try {
      const res = await axios.get(`http://127.0.0.1:8000/posts?date=${dateStr}`);
      if (res.data.posts && res.data.posts.length > 0) {
        setModalPosts(res.data.posts);
      } else {
        alert("No detailed posts retrieved for this date.");
      }
    } catch (e) {
      console.error(e);
      alert("Failed to fetch posts.");
    }
  };

  const fetchData = useCallback(
    async (kw, sub) => {
      setLoading(true);
      try {
        const p = new URLSearchParams({ spam_threshold: spamThreshold });
        if (kw) p.append("keyword", kw);
        if (sub) p.append("subreddit", sub);
        const res = await axios.get(
          `http://127.0.0.1:8000/timeseries?${p.toString()}`,
        );
        setData(res.data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    },
    [spamThreshold],
  );

  // Fetch topic trends once on mount (and when spam threshold changes)
  useEffect(() => {
    const fetchTopics = async () => {
      setTopicsLoading(true);
      try {
        const res = await axios.get(
          `http://127.0.0.1:8000/topics?nr_topics=10&spam_threshold=${spamThreshold}`,
        );
        setTopicsData(res.data);
      } catch (e) {
        console.error(e);
      } finally {
        setTopicsLoading(false);
      }
    };
    fetchTopics();
  }, [spamThreshold]);

  // Initial load and when spam threshold changes
  useEffect(() => {
    fetchData(committed.keyword, committed.subreddit);
  }, [committed, spamThreshold]);

  // Debounce keyword/subreddit inputs — commits after 600ms of no typing
  useEffect(() => {
    const timer = setTimeout(() => {
      setCommitted({ keyword, subreddit });
    }, 600);
    return () => clearTimeout(timer);
  }, [keyword, subreddit]);

  // The API returns: { daily: [...], hourly: [...], weekly: [...], anomalies: {...}, summary: "..." }
  const daily = data?.daily ?? [];
  const anomalies = data?.anomalies?.anomalies ?? [];
  const changepoints = data?.anomalies?.changepoints ?? [];

  const chartData = daily.map((d) => {
    const dateStr = typeof d.date === "string" ? d.date : String(d.date);
    const isAnomaly = anomalies.find((a) => a.date === dateStr);
    const isChangepoint = changepoints.includes(dateStr);
    return {
      ...d,
      date: dateStr,
      // null values render no dot — non-null render a dot marker
      anomalyDot: isAnomaly ? d.count : null,
      changepointDot: isChangepoint ? d.count : null,
    };
  });

  // Compute recent growth rate from last two daily entries
  const recentGrowth =
    daily.length >= 2
      ? (() => {
          const prev = daily[daily.length - 2]?.count || 0;
          const curr = daily[daily.length - 1]?.count || 0;
          return prev > 0 ? (curr - prev) / prev : 0;
        })()
      : null;

  // ── Build per-topic trend chart data ──────────────────────────────────────
  const topicChartData = (() => {
    if (!topicsData?.timeseries || !topicsData?.sizes) return null;

    // Top 5 topics by post count (exclude noise cluster -1)
    const topTopicIds = Object.entries(topicsData.sizes)
      .filter(([id]) => id !== "-1")
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5)
      .map(([id]) => id);

    if (topTopicIds.length === 0) return null;

    const topTerms = topicsData.top_terms || {};

    // Collect all unique dates across selected topics
    const dateSet = new Set();
    topTopicIds.forEach((tid) => {
      const ts = topicsData.timeseries[tid] || [];
      ts.forEach((d) =>
        dateSet.add(typeof d.date === "string" ? d.date : String(d.date)),
      );
    });
    const allDates = Array.from(dateSet).sort();
    if (allDates.length === 0) return null;

    // Build merged rows: one row per date, one key per topic
    const merged = allDates.map((date) => {
      const row = { date };
      topTopicIds.forEach((tid) => {
        const ts = topicsData.timeseries[tid] || [];
        const point = ts.find(
          (d) =>
            (typeof d.date === "string" ? d.date : String(d.date)) === date,
        );
        row[`topic_${tid}`] = point ? point.count : 0;
      });
      return row;
    });

    return { merged, topTopicIds, topTerms };
  })();

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto">
      {/* Filters */}
      <div className="flex gap-4">
        <input
          type="text"
          id="ts-keyword-filter"
          placeholder="Filter by keyword… (auto-searches after typing stops)"
          className="bg-gray-800 text-white px-4 py-2 rounded flex-1 border border-gray-700"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
        <input
          type="text"
          id="ts-subreddit-filter"
          placeholder="Filter by subreddit…"
          className="bg-gray-800 text-white px-4 py-2 rounded flex-1 border border-gray-700"
          value={subreddit}
          onChange={(e) => setSubreddit(e.target.value)}
        />
        <button
          id="ts-search-btn"
          onClick={() => setCommitted({ keyword, subreddit })}
          className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded font-medium transition"
        >
          Search
        </button>
      </div>

      {/* Active filter badges */}
      {(committed.keyword || committed.subreddit) && (
        <div className="flex gap-2 flex-wrap">
          {committed.keyword && (
            <span className="bg-blue-900/50 text-blue-300 text-xs px-3 py-1 rounded-full border border-blue-700/50">
              keyword: <strong>{committed.keyword}</strong>
            </span>
          )}
          {committed.subreddit && (
            <span className="bg-purple-900/50 text-purple-300 text-xs px-3 py-1 rounded-full border border-purple-700/50">
              subreddit: <strong>{committed.subreddit}</strong>
            </span>
          )}
          <button
            onClick={() => {
              setKeyword("");
              setSubreddit("");
              setCommitted({ keyword: "", subreddit: "" });
            }}
            className="text-gray-400 text-xs hover:text-white underline"
          >
            Clear filters
          </button>
        </div>
      )}

      {/* ── Chart 1: Post Volume Over Time ─────────────────────────────────── */}
      {loading ? (
        <div className="h-96 bg-gray-800 animate-pulse rounded border border-gray-700"></div>
      ) : data?.empty ? (
        <div className="h-48 bg-gray-800 rounded border border-gray-700 flex items-center justify-center text-gray-400">
          {data.message || "No data for the selected filters."}
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="bg-gray-800 p-6 rounded border border-gray-700">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-bold">Post Volume Over Time</h3>
              {recentGrowth !== null && (
                <div
                  className={`px-3 py-1 rounded font-bold ${
                    recentGrowth > 0
                      ? "bg-green-900/50 text-green-400"
                      : "bg-red-900/50 text-red-400"
                  }`}
                >
                  Recent Growth: {(recentGrowth * 100).toFixed(1)}%
                </div>
              )}
            </div>

            {chartData.length === 0 ? (
              <div className="h-80 flex items-center justify-center text-gray-500">
                No data points to chart.
              </div>
            ) : (
              <div className="h-80 w-full mb-4">
                <ResponsiveContainer width="100%" height="100%">
                  {/* ComposedChart allows mixing Line series — Scatter inside LineChart is invalid Recharts API */}
                  <ComposedChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis
                      dataKey="date"
                      stroke="#9ca3af"
                      tick={{ fontSize: 11 }}
                    />
                    <YAxis stroke="#9ca3af" />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#1f2937",
                        borderColor: "#374151",
                      }}
                    />
                    {/* Main volume line */}
                    <Line
                      type="monotone"
                      dataKey="count"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={false}
                      name="Posts"
                    />
                    {/* 7-day rolling average */}
                    <Line
                      type="monotone"
                      dataKey="rolling_7d_avg"
                      stroke="#10b981"
                      strokeWidth={2}
                      dot={false}
                      strokeDasharray="5 5"
                      name="7-day avg"
                    />
                    {/* Anomaly markers: strokeWidth=0 hides line, dot renders only non-null values */}
                    <Line
                      type="monotone"
                      dataKey="anomalyDot"
                      stroke="#ef4444"
                      strokeWidth={0}
                      dot={{ r: 5, fill: "#ef4444", stroke: "#ef4444" }}
                      activeDot={{ r: 8, cursor: "pointer", onClick: (_, payload) => {
                          if (payload && payload.payload && payload.payload.date) {
                              handleDotClick(payload.payload.date);
                          }
                      }}}
                      connectNulls={false}
                      name="Anomaly"
                      legendType="circle"
                    />
                    {/* Changepoint markers */}
                    <Line
                      type="monotone"
                      dataKey="changepointDot"
                      stroke="#f59e0b"
                      strokeWidth={0}
                      dot={{ r: 5, fill: "#f59e0b", stroke: "#f59e0b" }}
                      activeDot={{ r: 7 }}
                      connectNulls={false}
                      name="Changepoint"
                      legendType="square"
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Legend */}
            <div className="flex gap-6 text-xs text-gray-400 mb-4">
              <span className="flex items-center gap-1">
                <span className="w-4 h-0.5 bg-blue-500 inline-block"></span>{" "}
                Posts
              </span>
              <span className="flex items-center gap-1">
                <span
                  className="w-4 h-0.5 bg-emerald-500 inline-block"
                  style={{ borderTop: "2px dashed" }}
                ></span>{" "}
                7-day avg
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block"></span>{" "}
                Anomaly
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded-sm bg-amber-500 inline-block"></span>{" "}
                Changepoint
              </span>
            </div>

            {/* GenAI Summary — dynamically generated from actual query data */}
            <div className="bg-gray-900 overflow-hidden p-4 rounded text-gray-300 border border-gray-700 relative">
              <span className="block font-bold text-gray-400 text-xs uppercase mb-2">
                🤖 AI Summary
              </span>
              {data?.summary || "No summary available."}
            </div>
          </div>

          {/* ── Community Breakdown: Key Contributors ─────────────────────── */}
          <div className="bg-gray-800 p-6 rounded border border-gray-700">
            <h3 className="text-xl font-bold mb-4">
              Community Breakdown: Key Contributors
            </h3>
            <p className="text-xs text-gray-500 mb-6">
              Top authors and subreddits driving the filtered narrative above.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* Top Authors */}
              <div className="bg-gray-900 p-4 rounded border border-gray-700">
                <h4 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4 border-b border-gray-800 pb-2">
                  Top Authors
                </h4>
                <div className="space-y-3">
                  {data?.top_authors?.length > 0 ? (
                    data.top_authors.slice(0, 5).map((author, idx) => (
                      <div
                        key={idx}
                        className="flex justify-between items-center text-sm"
                      >
                        <span
                          className="text-blue-400 font-mono select-all truncate mr-4"
                          title={author.author}
                        >
                          @{author.author}
                        </span>
                        <span className="bg-gray-800 border border-gray-700 px-2 py-0.5 rounded text-gray-300 text-xs shadow-sm font-bold shrink-0">
                          {author.count} posts
                        </span>
                      </div>
                    ))
                  ) : (
                    <div className="text-xs text-gray-500 italic">
                      No author data available.
                    </div>
                  )}
                </div>
              </div>

              {/* Top Subreddits */}
              <div className="bg-gray-900 p-4 rounded border border-gray-700">
                <h4 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4 border-b border-gray-800 pb-2">
                  Top Subreddits
                </h4>
                <div className="space-y-3">
                  {data?.top_subreddits?.length > 0 ? (
                    data.top_subreddits.slice(0, 5).map((sub, idx) => (
                      <div
                        key={idx}
                        className="flex justify-between items-center text-sm"
                      >
                        <span className="text-purple-400 font-mono select-all truncate mr-4">
                          r/{sub.subreddit}
                        </span>
                        <span className="bg-gray-800 border border-gray-700 px-2 py-0.5 rounded text-gray-300 text-xs shadow-sm font-bold shrink-0">
                          {sub.count} posts
                        </span>
                      </div>
                    ))
                  ) : (
                    <div className="text-xs text-gray-500 italic">
                      No subreddit data available.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Chart 2: Key Topic Trends Over Time ─────────────────────────────── */}
      <div className="bg-gray-800 p-6 rounded border border-gray-700">
        <div className="flex justify-between items-center mb-1">
          <h3 className="text-xl font-bold">Key Topic Trends Over Time</h3>
          <span className="text-xs text-gray-500 bg-gray-900 px-2 py-1 rounded border border-gray-700">
            Top 5 clusters · BERTopic / HDBSCAN
          </span>
        </div>
        <p className="text-xs text-gray-500 mb-5">
          Each line represents a semantically distinct narrative cluster
          discovered via BERTopic (BAAI/bge-small-en-v1.5 embeddings → UMAP →
          HDBSCAN). Peaks indicate when a topic surged in discussion activity
          across the dataset.
        </p>

        {topicsLoading ? (
          <div className="h-64 bg-gray-900 animate-pulse rounded border border-gray-700"></div>
        ) : !topicChartData ? (
          <div className="h-32 flex items-center justify-center text-gray-500 text-sm">
            Topic trend data unavailable — ensure the backend has finished
            startup clustering.
          </div>
        ) : (
          <>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={topicChartData.merged}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis
                    dataKey="date"
                    stroke="#9ca3af"
                    tick={{ fontSize: 10 }}
                  />
                  <YAxis stroke="#9ca3af" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1f2937",
                      borderColor: "#374151",
                      fontSize: 12,
                    }}
                    formatter={(value, name) => {
                      const tid = name.replace("topic_", "");
                      const rawTerms =
                        topicChartData.topTerms[tid] || `Topic ${tid}`;
                      const label = rawTerms.split(",").slice(0, 3).join(", ");
                      return [value, label];
                    }}
                  />
                  {topicChartData.topTopicIds.map((tid, i) => (
                    <Line
                      key={tid}
                      type="monotone"
                      dataKey={`topic_${tid}`}
                      stroke={TOPIC_COLORS[i % TOPIC_COLORS.length]}
                      strokeWidth={2}
                      dot={false}
                      name={`topic_${tid}`}
                      connectNulls
                    />
                  ))}
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {/* Topic legend with terms and lifecycle badge */}
            <div className="mt-4 flex flex-col gap-1.5">
              {topicChartData.topTopicIds.map((tid, i) => {
                const rawTerms = topicChartData.topTerms[tid] || `Topic ${tid}`;
                const shortLabel = rawTerms.split(",").slice(0, 4).join(", ");
                const stageInfo = topicsData?.stages?.[tid];
                const badge = stageInfo?.badge_emoji || "";
                const postCount = topicsData?.sizes?.[tid] ?? "?";
                return (
                  <div
                    key={tid}
                    className="flex items-center gap-2 text-xs text-gray-400"
                  >
                    <span
                      className="w-3 h-3 rounded-full shrink-0 inline-block"
                      style={{
                        backgroundColor: TOPIC_COLORS[i % TOPIC_COLORS.length],
                      }}
                    />
                    <span className="text-gray-300 font-medium">
                      {shortLabel}
                    </span>
                    {badge && (
                      <span
                        className="text-sm leading-none"
                        title={stageInfo?.stage}
                      >
                        {badge}
                      </span>
                    )}
                    <span className="text-gray-600 ml-auto">
                      {postCount} posts
                    </span>
                  </div>
                );
              })}
            </div>

            {/* GenAI context note for topic trends */}
            <div className="bg-gray-900 p-3 rounded text-gray-400 border border-gray-700 text-xs mt-4">
              <span className="block font-bold text-gray-500 uppercase mb-1">
                📊 How to Read This Chart
              </span>
              Each line tracks how frequently posts in a given semantic cluster
              appeared over time. Cross-reference topic spikes with the anomaly
              markers in the Post Volume chart above to identify potential
              coordinated amplification events. Lifecycle stage badges (🌱
              Emerging · 🔥 Peaking · 📉 Declining · 💀 Dead) reflect the
              BERTopic cluster's current growth trajectory.
            </div>
          </>
        )}
      </div>
      {modalPosts && <PostModal posts={modalPosts} onClose={() => setModalPosts(null)} />}
    </div>
  );
}
