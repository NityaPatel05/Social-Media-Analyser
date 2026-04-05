import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import axios from "axios";
import { LineChart, Line, ResponsiveContainer, XAxis, Tooltip } from "recharts";

export default function TopicPage({ spamThreshold }) {
  const [nrTopics, setNrTopics] = useState(10);
  const [data, setData] = useState(null);
  const [htmlMap, setHtmlMap] = useState("");
  const [loading, setLoading] = useState(true);
  const [expandedTopic, setExpandedTopic] = useState(null);

  const fetchTopics = async () => {
    setLoading(true);
    try {
      const res = await axios.get(
        `http://127.0.0.1:8000/topics?nr_topics=${nrTopics}&spam_threshold=${spamThreshold}`
      );
      setData(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const fetchMap = async () => {
    try {
      const res = await axios.get(`http://127.0.0.1:8000/topics/embedding`);
      setHtmlMap(res.data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchTopics();
    fetchMap();
  }, [spamThreshold]);

  // ── Resolved stage info for the currently open modal ─────────────────────
  const stageInfo = expandedTopic && data?.stages
    ? data.stages[expandedTopic] ?? null
    : null;

  // ── Modal rendered via portal so it escapes ALL stacking contexts ─────────
  const modal = expandedTopic && (
    <div
      className="fixed inset-0 bg-black/80 flex items-center justify-center p-6 backdrop-blur-sm"
      style={{ zIndex: 9999 }}
      onClick={(e) => { if (e.target === e.currentTarget) setExpandedTopic(null) }}
    >
      <div className="bg-gray-800 rounded-lg shadow-2xl border border-gray-600 w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gray-700 flex justify-between items-center bg-gray-900">
          <h2 className="text-xl font-bold flex items-center gap-2">
            {stageInfo?.badge_emoji && <span>{stageInfo.badge_emoji}</span>}
            Cluster {expandedTopic}
            {stageInfo?.stage && (
              <span className="text-sm font-normal text-gray-400 ml-2">— {stageInfo.stage}</span>
            )}
          </h2>
          <button
            onClick={() => setExpandedTopic(null)}
            className="text-gray-400 hover:text-white px-2 py-1 text-xl leading-none"
          >
            &times;
          </button>
        </div>

        <div className="p-6 overflow-y-auto flex-1 flex flex-col gap-8">
          {stageInfo ? (
            <>
              {/* Volume Curve */}
              <div className="bg-gray-900 p-4 rounded border border-gray-700">
                <h3 className="text-md font-bold text-blue-400 mb-4">Volume Curve Tracking</h3>
                <div className="flex gap-6 mb-4">
                  <div className="flex flex-col">
                    <span className="text-xs text-gray-500 uppercase">Growth Rate</span>
                    <span
                      className={`font-mono text-lg ${
                        stageInfo.growth_rate >= 0 ? "text-green-400" : "text-red-400"
                      }`}
                    >
                      {stageInfo.growth_rate > 0 ? "↑" : "↓"}{" "}
                      {(Math.abs(stageInfo.growth_rate) * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex flex-col" title="High skew may indicate artificial amplification">
                    <span className="text-xs text-gray-500 uppercase flex items-center gap-1">
                      Skewness <span className="cursor-help">ⓘ</span>
                    </span>
                    <span className="font-mono text-lg text-orange-300">
                      {stageInfo.skewness?.toFixed(2) ?? "—"}
                    </span>
                  </div>
                </div>

                <div className="h-64 w-full">
                  {data?.timeseries?.[expandedTopic] ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={data.timeseries[expandedTopic].map((d, i) => ({
                          ...d,
                          curve: stageInfo.curve_data?.[i] ?? null,
                        }))}
                      >
                        <XAxis dataKey="date" stroke="#6b7280" />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: "#1f2937",
                            borderColor: "#374151",
                          }}
                        />
                        <Line
                          type="monotone"
                          dataKey="count"
                          stroke="#3b82f6"
                          strokeWidth={2}
                          dot={false}
                          name="Actual Posts"
                        />
                        {stageInfo.curve_fit_success && (
                          <Line
                            type="monotone"
                            dataKey="curve"
                            stroke="#f59e0b"
                            strokeWidth={2}
                            strokeDasharray="5 5"
                            dot={false}
                            name="Log-Normal Fit"
                          />
                        )}
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="text-gray-500 text-center pt-20">
                      Not enough data to plot
                    </div>
                  )}
                </div>
              </div>

              {/* Early Adopters */}
              <div className="bg-gray-900 p-4 rounded border border-gray-700">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-md font-bold text-purple-400">Early Adopters</h3>
                  {stageInfo.amplification_flag && (
                    <span className="bg-red-900 text-red-300 border border-red-700 px-3 py-1 rounded text-xs font-bold uppercase tracking-wider">
                      🚨 Amplification Detected
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {stageInfo.early_adopters?.length > 0 ? (
                    stageInfo.early_adopters.map((a, i) => (
                      <span
                        key={i}
                        className="bg-gray-800 border border-gray-600 px-3 py-1 rounded text-sm text-gray-300 font-mono flex items-center gap-2 shadow-sm"
                      >
                        {a}
                      </span>
                    ))
                  ) : (
                    <span className="text-gray-500 italic">
                      Insufficient post history to track early adopters.
                    </span>
                  )}
                </div>
              </div>
            </>
          ) : (
            /* No stage info — show basic info */
            <div className="bg-gray-900 p-6 rounded border border-gray-700 text-center">
              <p className="text-gray-400 text-sm">
                Detailed lifecycle data is available after reclustering.
              </p>
              <p className="text-gray-500 text-xs mt-2">
                Top keywords:{" "}
                <span className="text-gray-300">
                  {data?.top_terms?.[expandedTopic] ?? "N/A"}
                </span>
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Portal renders the modal at <body> level, escaping all stacking contexts */}
      {modal && createPortal(modal, document.body)}

      <div className="flex flex-col gap-6 max-w-7xl mx-auto min-h-screen">
        {/* Controls */}
        <div className="flex flex-col gap-4 bg-gray-800 p-4 rounded border border-gray-700">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-4">
              <span className="font-bold">Target Clusters: {nrTopics}</span>
              <input
                type="range"
                min="2"
                max="50"
                step="1"
                value={nrTopics}
                onChange={(e) => setNrTopics(Number(e.target.value))}
                className="w-48"
              />
              <button
                className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-1.5 rounded font-medium text-sm transition ml-4 disabled:opacity-50"
                onClick={() => { fetchTopics(); fetchMap(); }}
                disabled={loading}
              >
                {loading ? "Clustering..." : "Recluster"}
              </button>
            </div>
          </div>

          {data?.warning && (
            <div className="bg-orange-900/40 text-orange-400 px-4 py-2 rounded text-sm font-medium border border-orange-900/60 flex items-center gap-2 mt-2">
              ⚠️ {data.warning}
            </div>
          )}
        </div>

        {/* UMAP Embedding Map */}
        <div
          className="w-full bg-gray-800 rounded border border-gray-700 overflow-hidden shadow-xl"
          style={{ height: '600px' }}
        >
          {htmlMap && !htmlMap.includes("No clustering data initialized") ? (
            <iframe
              srcDoc={htmlMap}
              className="w-full h-full border-0"
              style={{ width: '100%', height: '100%', border: 'none' }}
              title="Embedding Scatter Plot"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-500 animate-pulse bg-gray-900">
              Generating UMAP Plot Layout…
            </div>
          )}
        </div>

        {/* Topic Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 pb-12">
          {data?.sizes &&
            Object.entries(data.sizes)
              .sort((a, b) => b[1] - a[1])
              .map(([tid, count]) => {
                const si = data?.stages?.[tid] ?? null;

                return (
                  <div
                    key={tid}
                    onClick={() => tid !== "-1" && setExpandedTopic(tid)}
                    className={`bg-gray-800 rounded border border-gray-700 overflow-hidden shadow-lg flex flex-col ${
                      tid !== "-1"
                        ? "cursor-pointer hover:border-blue-500 transition-colors"
                        : "opacity-75"
                    }`}
                  >
                    {/* Card header */}
                    <div className="p-4 border-b border-gray-700 bg-gray-900 flex justify-between items-start">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          {si && tid !== "-1" && (
                            <span className="text-lg" title={`Stage: ${si.stage}`}>
                              {si.badge_emoji}
                            </span>
                          )}
                          <span className="text-xs font-bold text-blue-400 uppercase tracking-widest">
                            {tid === "-1" ? "Outliers" : `Cluster ${tid}`}
                          </span>
                        </div>
                        <h3 className="font-bold text-gray-200 mt-1 line-clamp-2 leading-tight">
                          {data.top_terms[tid]
                            ? data.top_terms[tid].split(",").slice(0, 3).join(", ")
                            : "Uncategorized"}
                        </h3>
                      </div>

                      {/* Post count badge */}
                      <div className="bg-gray-800 border border-gray-600 px-2 py-1 rounded text-xs font-mono font-bold text-gray-300 shadow flex flex-col items-center shrink-0 ml-2">
                        {data.spam_adjusted_sizes?.[tid] !== undefined
                          ? data.spam_adjusted_sizes[tid]
                          : count}
                        <span className="text-[10px] text-gray-500 font-sans font-normal border-b border-gray-600 w-full text-center pb-[2px]">
                          {spamThreshold < 1.0 ? "spam-adjusted" : "posts"}
                        </span>
                        {spamThreshold < 1.0 && (
                          <span className="text-[10px] text-gray-600 line-through mt-[2px]">
                            {count} raw
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Card body */}
                    <div className="p-4 flex-1 flex flex-col gap-4">
                      <div>
                        <span className="text-xs text-gray-500 font-bold uppercase block mb-1">
                          Top Keywords
                        </span>
                        <p className="text-sm text-gray-300 leading-relaxed italic">
                          {data.top_terms[tid] || "N/A"}
                        </p>
                      </div>

                      {tid !== "-1" && si && (
                        <div className="flex justify-between items-center bg-gray-900 border border-gray-700 p-2 rounded mt-2 px-3">
                          <span className="text-xs font-bold text-gray-400 uppercase">Growth</span>
                          <span
                            className={`text-sm font-bold ${
                              si.growth_rate >= 0 ? "text-green-400" : "text-red-400"
                            }`}
                          >
                            {si.growth_rate > 0 ? "↑" : "↓"}{" "}
                            {(Math.abs(si.growth_rate) * 100).toFixed(0)}%
                          </span>
                        </div>
                      )}

                      {/* Expand hint */}
                      {tid !== "-1" && (
                        <p className="text-xs text-gray-600 mt-auto">Click to expand details →</p>
                      )}
                    </div>
                  </div>
                );
              })}
        </div>
      </div>
    </>
  );
}
