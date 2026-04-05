import { useState, useRef, useEffect } from "react";
import axios from "axios";
import PostModal from "../components/PostModal";

export default function ChatPage() {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([]); // array of {role: 'user'|'assistant', content: str, meta: {...}}
  const [loading, setLoading] = useState(false);

  const [modalPosts, setModalPosts] = useState(null);

  const endRef = useRef(null);

  const scrollToBottom = () => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSourceClick = async (docId) => {
    if (!docId || !docId.startsWith("post_")) return;
    try {
      const res = await axios.get(`http://127.0.0.1:8000/posts?id=${docId}`);
      if (res.data.posts && res.data.posts.length > 0) {
        setModalPosts(res.data.posts);
      } else {
        alert("Detailed post data not found.");
      }
    } catch (e) {
      console.error(e);
      alert("Error loading post data.");
    }
  };

  const handleSubmit = async (e, forcedQuery = null) => {
    if (e) e.preventDefault();

    const q = forcedQuery || query.trim();
    if (!q || q.length < 3) return;

    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setQuery("");
    setLoading(true);

    // Setup generic assistant message blob
    let currentAssistantMsgIndex = messages.length + 1;

    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", meta: null, suggestions: [] },
    ]);

    try {
      const response = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q }),
      });

      if (!response.body) throw new Error("No body streamed");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let done = false;
      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;

        if (value) {
          const chunkString = decoder.decode(value, { stream: true });
          const lines = chunkString.split("\n");

          for (let line of lines) {
            if (line.startsWith("data: ")) {
              const dataStr = line.slice(6);
              if (dataStr === "[DONE]") {
                done = true;
                break;
              }
              try {
                const data = JSON.parse(dataStr);

                setMessages((prev) => {
                  const newArr = [...prev];
                  const msg = newArr[newArr.length - 1]; // The currently streaming assistant message

                  if (data.type === "meta") {
                    msg.meta = {
                      sources: data.sources,
                      counts: data.counts,
                      language: data.language,
                    };
                  } else if (data.type === "token") {
                    msg.content += data.content;
                  } else if (data.type === "error") {
                    msg.content += `\\n\\n[Error: ${data.content}]`;
                  } else if (data.type === "suggestions") {
                    msg.suggestions = data.content;
                  }

                  return newArr;
                });
              } catch (e) {
                console.error(
                  "Parse JSON error during stream line:",
                  dataStr,
                  e,
                );
              }
            }
          }
        }
      }
    } catch (err) {
      console.error("Stream failed", err);
      setMessages((prev) => {
        const newArr = [...prev];
        newArr[newArr.length - 1].content += "\\n[Network Error occurred.]";
        return newArr;
      });
    } finally {
      setLoading(false);
    }
  };

  const getSourceBadgeColor = (type) => {
    switch (type) {
      case "posts":
        return "bg-blue-900 border-blue-500 text-blue-300";
      case "graph_facts":
        return "bg-green-900 border-green-500 text-green-300";
      case "topic_summaries":
        return "bg-purple-900 border-purple-500 text-purple-300";
      default:
        return "bg-gray-800 border-gray-500 text-gray-300";
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)] max-w-4xl mx-auto bg-gray-800 rounded-xl border border-gray-700 shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-gray-700 bg-gray-900 flex justify-between items-center z-10 shadow-sm relative">
        <h2 className="text-xl font-bold font-mono tracking-tight text-gray-200">
          RAG Chat Assistant
        </h2>
        <span className="text-xs text-gray-500 flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
          Connected to Databanks
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-gray-500 gap-4 mb-20 fade-in">
            <div className="bg-gray-900 p-6 rounded-2xl border border-gray-700 shadow-xl max-w-md text-center">
              <h3 className="text-white font-bold mb-2">
                Ask the Data Anything!
              </h3>
              <p className="text-sm">
                Query the dataset securely using multi-source RAG embeddings
                across posts, topic clusters, and community graphs.
              </p>
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-5 py-4 ${
                m.role === "user"
                  ? "bg-blue-600 text-white shadow-md"
                  : "bg-gray-900 border border-gray-700 text-gray-200 shadow-lg"
              }`}
            >
              {/* Language Alert */}
              {m.meta &&
                m.meta.language !== "en" &&
                m.meta.language !== "unknown" && (
                  <div className="inline-block bg-orange-900/60 text-orange-300 border border-orange-700 px-2 py-0.5 rounded text-[10px] mb-2 font-bold uppercase tracking-wider">
                    {m.meta.language} Detected
                  </div>
                )}

              {/* Message Content */}
              <div
                className="whitespace-pre-wrap text-[15px] leading-relaxed font-sans"
                dangerouslySetInnerHTML={{
                  // Quick hack for bold markdown rendering easily in simple chat
                  __html: m.content
                    ? m.content.replace(
                        /\\*\\*(.*?)\\*\\*/g,
                        "<strong>$1</strong>",
                      )
                    : m.role === "assistant"
                      ? '<span class="animate-pulse">Thinking...</span>'
                      : "",
                }}
              ></div>

              {/* Sources Accordion */}
              {m.meta && m.meta.sources && m.meta.sources.length > 0 && (
                <div className="mt-6 pt-4 border-t border-gray-800">
                  <details className="text-sm marker:text-gray-500">
                    <summary className="cursor-pointer text-gray-500 hover:text-gray-300 font-bold tracking-tight select-none">
                      View Grounding Sources ({m.meta.sources.length})
                    </summary>
                    <div className="mt-4 space-y-3 pl-2 border-l-2 border-gray-800">
                      {m.meta.sources.map((src, sIdx) => (
                        <div
                          key={sIdx}
                          className="bg-gray-800 rounded p-3 text-xs text-gray-400"
                        >
                          <div className="flex justify-between items-center mb-2">
                            <span
                              className={`px-2 py-[2px] rounded uppercase font-bold border shrink-0 text-[10px] ${getSourceBadgeColor(src.source_type)}`}
                            >
                              {src.source_type.replace("_", " ")}
                            </span>
                            <span className="text-[10px] text-gray-600 font-mono">
                              Similarity: {(src.score * 100).toFixed(0)}%
                            </span>
                          </div>
                          <p className="italic line-clamp-3 leading-relaxed mt-1">
                            "{src.text}"
                          </p>
                          {src.source_type === "posts" && src.id && (
                            <button
                              onClick={() => handleSourceClick(src.id)}
                              className="mt-2 text-blue-400 hover:text-blue-300 transition underline font-bold"
                            >
                              View Full Post Modal ↗
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  </details>
                </div>
              )}

              {/* Follow-ups */}
              {m.suggestions && m.suggestions.length > 0 && (
                <div className="mt-4 flex flex-col gap-2 pt-4 border-t border-gray-800">
                  <span className="text-xs text-gray-500 font-bold uppercase">
                    Suggested Follow-ups:
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {m.suggestions.map((sug, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSubmit(null, sug)}
                        className="bg-gray-800 hover:bg-gray-700 hover:text-blue-400 transition text-gray-400 text-xs px-3 py-1.5 rounded-full border border-gray-700 text-left"
                      >
                        {sug}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={(e) => handleSubmit(e, null)}
        className="p-4 bg-gray-900 border-t border-gray-700 flex gap-4"
      >
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask a question..."
          className="flex-1 bg-gray-800 text-white rounded-full px-6 py-3 border border-gray-700 focus:outline-none focus:border-blue-500 transition shadow-inner"
          disabled={loading}
        />
        <button
          type="submit"
          className="bg-blue-600 hover:bg-blue-500 text-white rounded-full px-6 py-3 font-medium transition disabled:opacity-50 min-w-[100px] shadow"
          disabled={loading || !query.trim() || query.trim().length < 3}
        >
          {loading ? (
            <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin inline-block align-middle"></span>
          ) : (
            "Send"
          )}
        </button>
      </form>

      {modalPosts && (
        <PostModal posts={modalPosts} onClose={() => setModalPosts(null)} />
      )}
    </div>
  );
}
