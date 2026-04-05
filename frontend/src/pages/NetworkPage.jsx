import { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'
import cytoscape from 'cytoscape'
import PostModal from '../components/PostModal'

// ─── Cytoscape stylesheet ─────────────────────────────────────────────────────
const CY_STYLE = [
  {
    selector: 'node',
    style: {
      'background-color': 'data(color)',
      'label': 'data(label)',
      'width': 'data(size)',
      'height': 'data(size)',
      'font-size': 9,
      'color': '#e5e7eb',
      'text-valign': 'bottom',
      'text-margin-y': 4,
      'text-outline-width': 2,
      'text-outline-color': '#111827',
      'shape': 'data(shape)',
      'opacity': 1,
    }
  },
  {
    selector: 'node[?filtered]',
    style: { 'opacity': 0.15 }
  },
  {
    selector: 'node:selected',
    style: {
      'border-width': 3,
      'border-color': '#60a5fa',
      'border-opacity': 1,
    }
  },
  {
    selector: 'edge',
    style: {
      'width': 1,
      'line-color': '#374151',
      'opacity': 0.55,
      'curve-style': 'bezier',
    }
  },
  {
    selector: 'edge:selected',
    style: { 'line-color': '#60a5fa', 'opacity': 1 }
  }
]

export default function NetworkPage({ spamThreshold }) {
  const [activeTab, setActiveTab]     = useState(1)
  const [centrality, setCentrality]   = useState('pagerank')
  const [data, setData]               = useState(null)
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState(null)
  const [removeNodeId, setRemoveNodeId] = useState('')
  const [selectedNode, setSelectedNode] = useState(null)
  const [modalPosts, setModalPosts] = useState(null)

  const cyContainerRef = useRef(null)
  const cyRef          = useRef(null)

  const handleAuthorPosts = async (authorName) => {
      try {
          const res = await axios.get(`http://35.169.145.225:8000/posts?author=${authorName}`);
          if (res.data.posts && res.data.posts.length > 0) {
              setModalPosts(res.data.posts);
          } else {
              alert(`No detailed posts available for node: ${authorName}`);
          }
      } catch(e) {
          console.error(e);
      }
  }

  // ── Fetch graph data ──────────────────────────────────────────────────────
  const fetchGraph = useCallback(async () => {
    setLoading(true)
    setSelectedNode(null)
    setError(null)
    try {
      const res = await axios.get(
        `http://35.169.145.225:8000/network/${activeTab}` +
        `?centrality=${centrality}&spam_threshold=${spamThreshold}`
      )
      setData(res.data)
    } catch (e) {
      console.error(e)
      setError('Failed to load graph — is the backend running?')
    } finally {
      setLoading(false)
    }
  }, [activeTab, centrality, spamThreshold])

  useEffect(() => { fetchGraph() }, [fetchGraph])

  // ── Mount / refresh Cytoscape when elements change ────────────────────────
  useEffect(() => {
    if (!cyContainerRef.current) return
    if (!data?.elements?.nodes?.length) {
      // Nothing to render; destroy old instance if any
      if (cyRef.current) { cyRef.current.destroy(); cyRef.current = null }
      return
    }

    // Destroy previous instance
    if (cyRef.current) { cyRef.current.destroy(); cyRef.current = null }

    const { nodes = [], edges = [] } = data.elements
    const elements = [
      ...nodes.map(n => ({ group: 'nodes', data: n.data })),
      ...edges.map(e => ({ group: 'edges', data: e.data })),
    ]

    const cy = cytoscape({
      container: cyContainerRef.current,
      elements,
      style: CY_STYLE,
      layout: {
        name: 'cose',
        animate: true,
        animationDuration: 700,
        randomize: true,
        nodeRepulsion: () => 8000,
        idealEdgeLength: () => 80,
        edgeElasticity: () => 100,
        gravity: 0.25,
        numIter: 1000,
        fit: true,
        padding: 30,
      },
      wheelSensitivity: 0.3,
      minZoom: 0.05,
      maxZoom: 6,
    })

    // Node click → populate sidebar
    cy.on('tap', 'node', evt => {
      setSelectedNode(evt.target.data())
    })
    // Background click → clear selection
    cy.on('tap', evt => {
      if (evt.target === cy) setSelectedNode(null)
    })

    cyRef.current = cy

    return () => {
      if (cyRef.current) { cyRef.current.destroy(); cyRef.current = null }
    }
  }, [data])

  // ── Remove node ───────────────────────────────────────────────────────────
  const handleRemoveNode = async () => {
    if (!removeNodeId.trim()) return
    setLoading(true)
    try {
      const res = await axios.post('http://35.169.145.225:8000/network/remove-node', {
        graph_type: activeTab,
        node_id:    removeNodeId.trim(),
      })
      if (res.data.error) {
        alert(res.data.message)
      } else {
        setData(res.data)
        setSelectedNode(null)
      }
      setRemoveNodeId('')
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  // ── Sidebar derived values ────────────────────────────────────────────────
  const allMetrics  = data?.metrics?.metrics || {}
  const sid         = selectedNode?.id
  const nodeDegree  = sid ? (allMetrics[sid]?.degree      ?? selectedNode?.degree      ?? '—') : null
  const nodePR      = sid ? (allMetrics[sid]?.pagerank?.toFixed(6)    ?? selectedNode?.pagerank?.toFixed(6)    ?? '—') : null
  const nodeBetw    = sid ? (allMetrics[sid]?.betweenness?.toFixed(2) ?? selectedNode?.betweenness?.toFixed(2) ?? '—') : null

  return (
    <div
      className="flex flex-col gap-4 max-w-7xl mx-auto"
      style={{ height: 'calc(100vh - 7rem)', overflow: 'hidden' }}
    >
      {/* Controls */}
      <div className="flex justify-between items-center bg-gray-800 p-3 rounded border border-gray-700 shrink-0">
        {/* Graph-type tabs */}
        <div className="flex gap-2 bg-gray-900 rounded p-1 border border-gray-700">
          {[
            { id: 1, label: 'User-URL Bipartite' },
            { id: 2, label: 'Author Co-Activity' },
          ].map(tab => (
            <button
              key={tab.id}
              className={`px-4 py-1 rounded text-sm font-medium transition ${
                activeTab === tab.id
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex gap-4 items-center">
          {/* Centrality selector */}
          <select
            className="bg-gray-900 text-sm text-gray-300 border border-gray-700 rounded px-3 py-1.5"
            value={centrality}
            onChange={e => setCentrality(e.target.value)}
          >
            <option value="pagerank">PageRank</option>
            <option value="betweenness">Betweenness</option>
            <option value="degree">Degree</option>
          </select>

          {/* Remove node */}
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Node ID to remove"
              className="bg-gray-900 text-sm px-3 py-1.5 rounded border border-gray-700 max-w-xs text-white"
              value={removeNodeId}
              onChange={e => setRemoveNodeId(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleRemoveNode()}
            />
            <button
              className="bg-red-600/80 hover:bg-red-500 text-white px-3 py-1.5 rounded text-sm transition"
              onClick={handleRemoveNode}
            >
              Remove Node
            </button>
          </div>
        </div>
      </div>

      {/* Graph canvas + sidebars */}
      <div className="flex gap-4 flex-1 min-h-0" style={{ overflow: 'hidden' }}>

        {/* Cytoscape canvas */}
        <div
          className="bg-gray-900 rounded border border-gray-700 shadow-xl relative"
          style={{ flex: '1 1 0', height: '100%', minHeight: 0 }}
        >
          {/* Loading overlay */}
          {loading && (
            <div className="absolute inset-0 bg-gray-900/70 flex flex-col items-center justify-center z-10 backdrop-blur-sm rounded">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mb-3" />
              <span className="text-gray-400 text-sm">Loading graph…</span>
            </div>
          )}

          {/* Error */}
          {error && !loading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center z-10 gap-3">
              <p className="text-red-400 text-sm">{error}</p>
              <button
                className="text-blue-400 text-xs underline"
                onClick={fetchGraph}
              >
                Retry
              </button>
            </div>
          )}

          {/* Empty after load */}
          {!loading && !error && !data?.elements?.nodes?.length && (
            <div className="absolute inset-0 flex items-center justify-center z-10">
              <p className="text-gray-500 text-sm">No graph data available.</p>
            </div>
          )}

          {/* Cytoscape mount — always in DOM so ref is stable */}
          <div
            ref={cyContainerRef}
            style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }}
          />

          {/* Hint */}
          {!loading && !!data?.elements?.nodes?.length && (
            <div className="absolute bottom-3 left-3 text-xs text-gray-600 pointer-events-none select-none">
              Scroll to zoom · Drag to pan · Click a node for details
            </div>
          )}
        </div>

        {/* Right sidebars */}
        <div className="flex flex-col gap-4 w-64 shrink-0 min-h-0 overflow-y-auto">

          {/* Node info panel */}
          <div className="bg-gray-800 rounded border border-gray-700 p-4 shrink-0">
            <h3 className="font-bold text-gray-200 mb-3 text-sm uppercase tracking-wider">Node Info</h3>
            {selectedNode ? (
              <div className="space-y-2 text-sm">
                <div className="bg-gray-900 rounded p-2 border border-gray-700">
                  <span className="text-gray-400 text-xs uppercase">Name</span>
                  <p className="text-white font-medium break-all mt-0.5">{selectedNode.id}</p>
                </div>
                {selectedNode.filtered && (
                  <div className="bg-red-900/30 border border-red-800 rounded p-2 text-xs text-red-400">
                    🚨 Spam flagged ({selectedNode.spamScore?.toFixed(2)})
                  </div>
                )}
                <div className="grid grid-cols-3 gap-1 text-center">
                  <div className="bg-gray-900 rounded p-2 border border-gray-700">
                    <span className="text-gray-400 text-xs block">Degree</span>
                    <span className="text-blue-400 font-bold">{nodeDegree}</span>
                  </div>
                  <div className="bg-gray-900 rounded p-2 border border-gray-700">
                    <span className="text-gray-400 text-xs block">PR</span>
                    <span className="text-green-400 font-bold">{nodePR}</span>
                  </div>
                  <div className="bg-gray-900 rounded p-2 border border-gray-700">
                    <span className="text-gray-400 text-xs block">Betw.</span>
                    <span className="text-purple-400 font-bold">{nodeBetw}</span>
                  </div>
                </div>
                
                <button
                   onClick={() => handleAuthorPosts(selectedNode.id)}
                   className="w-full mt-2 bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-4 rounded transition text-xs shadow-md"
                >
                   Explore Node Posts Modal
                </button>
              </div>
            ) : (
              <p className="text-gray-500 text-xs">Click any node to see its details here.</p>
            )}
          </div>

          {/* Communities panel */}
          <div className="bg-gray-800 rounded border border-gray-700 p-4 flex-1 overflow-y-auto">
            <h3 className="font-bold text-gray-200 mb-3 text-sm uppercase tracking-wider">Communities</h3>
            <ul className="space-y-2">
              {data?.metrics?.labels
                ? Object.entries(data.metrics.labels).map(([id, info]) => (
                    <li key={id} className="flex flex-col gap-1 text-sm bg-gray-900 p-2 rounded border border-gray-700">
                      <div className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: info.color }} />
                        <span className="font-bold text-gray-200 truncate">{info.label}</span>
                      </div>
                      <span className="text-gray-500 text-xs ml-5">Group {id}</span>
                    </li>
                  ))
                : (
                    <li className="text-gray-500 text-xs">No communities detected</li>
                  )
              }
            </ul>
          </div>

        </div>
      </div>
      {modalPosts && <PostModal posts={modalPosts} onClose={() => setModalPosts(null)} />}
    </div>
  )
}
