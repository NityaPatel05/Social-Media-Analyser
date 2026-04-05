import { useState, useEffect } from 'react'
import axios from 'axios'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import PostModal from '../components/PostModal'

export default function SpamPage({ spamThreshold }) {
  const [authors, setAuthors] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedUser, setSelectedUser] = useState(null)
  const [userDetails, setUserDetails] = useState(null)
  const [detailsLoading, setDetailsLoading] = useState(false)
  const [modalPosts, setModalPosts] = useState(null)

  useEffect(() => {
    const fetchSpamData = async () => {
      setLoading(true)
      try {
        const res = await axios.get(`http://35.169.145.225:8000/spam?threshold=${spamThreshold}`)
        setAuthors(res.data)
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    fetchSpamData()
  }, [spamThreshold])

  const fetchUserDetails = async (username) => {
    setSelectedUser(username)
    setDetailsLoading(true)
    try {
      const res = await axios.get(`http://35.169.145.225:8000/accounts/${username}`)
      setUserDetails(res.data)
    } catch (e) {
      console.error(e)
    } finally {
      setDetailsLoading(false)
    }
  }

  const handleOpenDetailedPosts = async (username) => {
      try {
          const res = await axios.get(`http://35.169.145.225:8000/posts?author=${username}`);
          if (res.data.posts && res.data.posts.length > 0) {
              setModalPosts(res.data.posts);
          } else {
              alert("No detailed posts available.");
          }
      } catch(e) {
          console.error(e);
      }
  }

  // Format chart data for signals
  let signalData = []
  if (userDetails?.signals) {
    signalData = [
      { name: "IF Score", value: userDetails.if_score },
      { name: "Post Freq", value: userDetails.signals.post_freq_per_hour },
      { name: "URL Ratio", value: userDetails.signals.url_to_post_ratio },
      { name: "Domain Rep", value: userDetails.signals.domain_repetition_rate },
      { name: "Duplicate Rate", value: userDetails.signals.near_duplicate_rate }
    ]
  }

  return (
    <div className="flex gap-6 max-w-7xl mx-auto h-[calc(100vh-8rem)]">
      {/* Left panel: Author list */}
      <div className="w-1/3 flex flex-col bg-gray-800 rounded border border-gray-700 overflow-hidden">
        <div className="p-4 border-b border-gray-700 flex justify-between items-center bg-gray-900">
          <h3 className="font-bold">Accounts Flagged</h3>
          <span className="bg-gray-700 px-2 py-1 rounded text-xs">{authors.length}</span>
        </div>
        
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="p-4 space-y-4">
              {[1,2,3,4].map(i => (
                <div key={i} className="h-12 bg-gray-700 animate-pulse rounded"></div>
              ))}
            </div>
          ) : (
            <ul className="divide-y divide-gray-700">
              {authors.map(a => (
                <li 
                  key={a.author}
                  onClick={() => fetchUserDetails(a.author)}
                  className={`p-4 hover:bg-gray-700 cursor-pointer flex justify-between items-center transition ${selectedUser === a.author ? 'bg-gray-700/80 border-l-4 border-blue-500' : ''}`}
                >
                  <span className="font-mono text-sm">{a.author}</span>
                  <span className={`px-2 py-1 rounded text-xs font-bold ${a.spam_score > 0.8 ? 'bg-red-900/50 text-red-500' : 'bg-orange-900/50 text-orange-400'}`}>
                    {a.spam_score.toFixed(2)}
                  </span>
                </li>
              ))}
              {authors.length === 0 && (
                <li className="p-4 text-gray-500 text-center">No accounts above threshold.</li>
              )}
            </ul>
          )}
        </div>
      </div>

      {/* Right panel: Drilldown */}
      <div className="w-2/3 flex flex-col bg-gray-800 rounded border border-gray-700 overflow-hidden">
        {selectedUser ? (
          detailsLoading ? (
            <div className="p-8 flex items-center justify-center h-full">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
            </div>
          ) : userDetails ? (
            <div className="flex flex-col h-full">
              <div className="p-6 border-b border-gray-700 bg-gray-900">
                <h2 className="text-2xl font-bold font-mono text-blue-400 mb-2">{userDetails.author}</h2>
                <p className="text-gray-400 text-sm mb-4">Overall Spam Score: <span className="text-white font-bold">{userDetails.spam_score?.toFixed(2)}</span></p>
                
                <div className="h-48 w-full">
                  <ResponsiveContainer>
                    <BarChart layout="vertical" data={signalData} margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" horizontal={false} />
                      <XAxis type="number" domain={[0, 1]} stroke="#9ca3af" />
                      <YAxis dataKey="name" type="category" stroke="#9ca3af" width={100} />
                      <Tooltip contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151' }} />
                      <Bar dataKey="value" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
              
              <div className="p-6 flex-1 overflow-y-auto">
                <div className="flex justify-between items-center mb-4">
                  <h4 className="font-bold">Post History ({userDetails.posts?.length || 0})</h4>
                  <button 
                      onClick={() => handleOpenDetailedPosts(userDetails.author)}
                      className="text-xs bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded transition shadow"
                  >
                      Expand Deep View Modal
                  </button>
                </div>
                <div className="space-y-4">
                  {userDetails.posts?.map((p, i) => (
                    <div key={i} className="bg-gray-900 border border-gray-700 p-4 rounded text-sm relative group">
                      <div className="flex justify-between text-gray-400 mb-2 text-xs">
                        <span>{new Date(p.created_utc).toLocaleString()}</span>
                        <span>{p.subreddit}</span>
                      </div>
                      <p className="text-gray-200 line-clamp-3">{p.full_text}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
             <div className="p-8 text-center text-gray-500">Could not load details</div>
          )
        ) : (
          <div className="p-8 flex items-center justify-center h-full text-gray-500">
            Select an account from the list to view drilldown analysis.
          </div>
        )}
      </div>
      {modalPosts && <PostModal posts={modalPosts} onClose={() => setModalPosts(null)} />}
    </div>
  )
}
