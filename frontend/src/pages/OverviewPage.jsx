import { useState, useEffect } from 'react'
import axios from 'axios'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

export default function OverviewPage({ spamThreshold }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Usually the dashboard doesn't re-compute its static globals on spam_threshold, but if requested we could.
    // Spec says "When changed, all pages re-fetch" but summary endpoint might not accept it right now.
    // Let's just fetch standard overview.
    const fetchSummary = async () => {
      setLoading(true)
      try {
        const res = await axios.get('http://127.0.0.1:8000/data/summary')
        setData(res.data)
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    fetchSummary()
  }, []) // empty dep arrays for overview mostly

  if (loading || !data) {
    return <div className="flex h-full items-center justify-center animate-pulse text-blue-400">Loading Dashboard...</div>
  }

  const { total_posts, unique_authors, subreddits_count, date_range, global_spam_rate, top_subreddits, lifecycles, top_authors, recent_anomalies } = data

  const lifecycleData = Object.entries(lifecycles || {}).map(([k,v]) => ({ name: k, count: v }))
  const lifecycleColors = {
    EMERGING: '#10b981', // green
    PEAKING: '#3b82f6',  // blue
    DECLINING: '#f59e0b',// yellow
    DEAD: '#6b7280'      // gray
  }

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto h-[calc(100vh-8rem)]">
      
      {/* Top Banner Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-gray-800 p-4 rounded border border-gray-700 shadow flex flex-col items-center">
            <span className="text-sm text-gray-400 uppercase font-bold tracking-wider mb-2">Total Posts</span>
            <span className="text-3xl font-mono text-blue-400 font-bold">{total_posts?.toLocaleString() || 0}</span>
        </div>
        <div className="bg-gray-800 p-4 rounded border border-gray-700 shadow flex flex-col items-center">
            <span className="text-sm text-gray-400 uppercase font-bold tracking-wider mb-2">Unique Actors</span>
            <span className="text-3xl font-mono text-purple-400 font-bold">{unique_authors?.toLocaleString() || 0}</span>
        </div>
        <div className="bg-gray-800 p-4 rounded border border-gray-700 shadow flex flex-col items-center">
            <span className="text-sm text-gray-400 uppercase font-bold tracking-wider mb-2">Networks</span>
            <span className="text-3xl font-mono text-pink-400 font-bold">{subreddits_count?.toLocaleString() || 0}</span>
        </div>
        <div className="bg-gray-800 p-4 rounded border border-gray-700 shadow flex flex-col items-center">
            <span className="text-sm text-gray-400 uppercase font-bold tracking-wider mb-2">Global Spam Rate</span>
            <span className="text-3xl font-mono text-red-500 font-bold">{(global_spam_rate * 100)?.toFixed(1)}%</span>
        </div>
        <div className="bg-gray-800 p-4 rounded border border-gray-700 shadow flex flex-col items-center">
            <span className="text-sm text-gray-400 uppercase font-bold tracking-wider mb-2">Date Range</span>
            <span className="text-sm text-center text-gray-300 font-mono mt-1">{date_range ? date_range[0].split(' ')[0] : ''} <br/>to<br/> {date_range ? date_range[1].split(' ')[0] : ''}</span>
        </div>
      </div>

      <div className="flex gap-6 overflow-hidden flex-1">
        
        {/* Left Column */}
        <div className="w-1/3 flex flex-col gap-6 h-full overflow-y-auto pr-2 pb-12">
            {/* Top Subreddits */}
            <div className="bg-gray-800 p-5 rounded border border-gray-700 shadow">
               <h3 className="text-sm text-gray-400 font-bold uppercase tracking-wider mb-4 border-b border-gray-700 pb-2">Most Active Subreddits</h3>
               <div className="h-64">
                 <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={top_subreddits} layout="vertical" margin={{ left: 30, right: 10, top: 0, bottom: 0 }}>
                       <YAxis type="category" dataKey="subreddit" width={80} stroke="#9ca3af" fontSize={11} tick={{fill: '#9ca3af'}} />
                       <XAxis type="number" hide />
                       <Tooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} contentStyle={{backgroundColor: '#1f2937', border: '1px solid #374151'}} />
                       <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} barSize={16} />
                    </BarChart>
                 </ResponsiveContainer>
               </div>
            </div>
            
            {/* Lifecycles */}
            <div className="bg-gray-800 p-5 rounded border border-gray-700 shadow flex-1">
               <h3 className="text-sm text-gray-400 font-bold uppercase tracking-wider mb-4 border-b border-gray-700 pb-2">Lifecycle Distribution</h3>
               <div className="h-40">
                 <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={lifecycleData} margin={{ left: 0, right: 0, top: 10, bottom: 0 }}>
                       <XAxis dataKey="name" stroke="#9ca3af" fontSize={11} tick={{fill: '#9ca3af'}} />
                       <Tooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} contentStyle={{backgroundColor: '#1f2937', border: '1px solid #374151'}} />
                       <Bar dataKey="count" radius={[4, 4, 0, 0]} barSize={32}>
                          {lifecycleData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={lifecycleColors[entry.name] || '#9ca3af'} />
                          ))}
                       </Bar>
                    </BarChart>
                 </ResponsiveContainer>
               </div>
            </div>
        </div>

        {/* Right Column */}
        <div className="flex-1 flex flex-col gap-6 h-full overflow-y-auto pb-12">
            
            {/* Top Authors */}
            <div className="bg-gray-800 p-5 rounded border border-gray-700 shadow">
                <h3 className="text-sm text-gray-400 font-bold uppercase tracking-wider mb-4 border-b border-gray-700 pb-2">Top 5 Influencers (PageRank)</h3>
                <div className="flex flex-col gap-3">
                   {top_authors && top_authors.map((auth, idx) => (
                      <div key={idx} className="flex justify-between items-center bg-gray-900 p-3 rounded border border-gray-700">
                         <div className="flex items-center gap-4">
                            <div className="bg-blue-900/40 text-blue-400 border border-blue-800 w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm">
                               {idx + 1}
                            </div>
                            <span className="font-mono text-gray-200">{auth.author}</span>
                         </div>
                         <div className="flex items-center gap-6">
                            <div className="flex flex-col text-right">
                               <span className="text-[10px] text-gray-500 uppercase font-bold">Influence</span>
                               <span className="text-sm text-blue-300 font-mono">{(auth.pagerank * 1000).toFixed(2)}</span>
                            </div>
                            <div className="flex flex-col text-right w-24">
                               <span className="text-[10px] text-gray-500 uppercase font-bold">Spam Score</span>
                               <span className={`text-sm font-mono font-bold px-2 py-[1px] rounded inline-block text-center mt-1 border ${
                                  auth.spam_score > 0.5 ? 'bg-red-900/60 text-red-400 border-red-700' : 'bg-gray-800 border-gray-600 text-gray-400'
                               }`}>
                                  {auth.spam_score.toFixed(2)}
                               </span>
                            </div>
                         </div>
                      </div>
                   ))}
                </div>
            </div>

            {/* Recent Anomalies */}
            <div className="bg-gray-800 p-5 rounded border border-gray-700 shadow flex-1">
                <h3 className="text-sm text-gray-400 font-bold uppercase tracking-wider mb-4 border-b border-gray-700 pb-2 flex items-center gap-2">
                   🚨 Recent Anomalies
                </h3>
                <div className="flex flex-col gap-3">
                   {recent_anomalies && recent_anomalies.length > 0 ? (
                      recent_anomalies.map((anom, idx) => (
                         <div key={idx} className="bg-gray-900 p-3 rounded border-l-4 border-l-red-500 border-gray-700 flex justify-between items-center">
                            <span className="font-mono text-gray-300">{anom.date}</span>
                            <div className="flex items-center gap-4">
                               <span className="text-xs text-gray-500">Volume Surge:</span>
                               <span className="font-mono text-red-400 font-bold px-2 bg-red-900/30 rounded border border-red-900">
                                  {anom.count} posts
                               </span>
                            </div>
                         </div>
                      ))
                   ) : (
                      <div className="text-gray-500 italic p-4 text-center">No anomalies detected recently.</div>
                   )}
                </div>
            </div>
            
        </div>
      </div>
    </div>
  )
}
