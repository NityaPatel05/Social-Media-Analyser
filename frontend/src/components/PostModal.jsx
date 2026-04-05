import React, { useState } from 'react';

export default function PostModal({ posts, onClose }) {
    const [currentIndex, setCurrentIndex] = useState(0);

    if (!posts || posts.length === 0) return null;

    const post = posts[currentIndex];
    
    // Safety fallback for badly formatted strings natively returned as NaN or missing
    const spamScore = typeof post.spam_score === 'number' ? post.spam_score.toFixed(3) : 0;
    const isSpam = post.spam_score >= 0.7;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm transition-opacity">
            <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-3xl flex flex-col shadow-2xl relative max-h-[90vh]">
                
                {/* Header */}
                <div className="p-5 border-b border-gray-800 flex justify-between items-start">
                    <div>
                        <h2 className="text-xl font-bold text-gray-100 flex items-center gap-2">
                            {post.title || <span className="italic text-gray-500">No Target Title</span>}
                        </h2>
                        <div className="flex flex-wrap items-center gap-3 mt-3 text-xs">
                            <span className="font-mono text-blue-400 bg-blue-900/30 px-2 py-0.5 rounded border border-blue-800">
                                r/{post.subreddit}
                            </span>
                            <span className="text-gray-400 font-bold">
                                u/{post.author}
                            </span>
                            <span className="text-gray-500 flex items-center gap-1">
                                <svg className="w-3 h-3 text-orange-500" fill="currentColor" viewBox="0 0 20 20"><path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933a4 4 0 00-.8 2.4z" /></svg>
                                {post.score} score
                            </span>
                            
                            {/* Spam Badge */}
                            <span className={`px-2 py-0.5 rounded font-mono border ${isSpam ? 'bg-red-900/40 text-red-400 border-red-800' : 'bg-green-900/20 text-green-400 border-green-800'}`}>
                                Spam Score: {spamScore}
                            </span>

                            {/* Topic Badge */}
                            <span className="ml-auto flex items-center gap-1 bg-gray-800 border border-gray-700 px-2 py-0.5 rounded text-gray-300">
                                {post.badge} <span className="uppercase text-[10px] tracking-wider">{post.lifecycle_stage}</span>
                            </span>
                        </div>
                    </div>
                </div>

                {/* Body Details */}
                <div className="p-6 overflow-y-auto text-sm text-gray-300 leading-relaxed space-y-4">
                    {post.selftext ? (
                        <div className="bg-gray-800/50 p-4 rounded-xl border border-gray-700/50 whitespace-pre-wrap">
                            {post.selftext}
                        </div>
                    ) : (
                        <div className="text-gray-600 italic">No body text included in tracking.</div>
                    )}
                    
                    <div className="flex justify-between items-center text-xs text-gray-500 pt-4 border-t border-gray-800">
                         <span>Captured: {new Date(post.created_utc).toLocaleString()}</span>
                         
                         <a 
                            href={post.permalink} 
                            target="_blank" 
                            rel="noreferrer"
                            className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-full transition flex items-center gap-2 font-bold shadow"
                        >
                            View on Reddit
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                        </a>
                    </div>
                </div>

                {/* Footer Controls */}
                <div className="p-4 border-t border-gray-800 flex justify-between items-center bg-gray-900 rounded-b-2xl">
                    <div className="flex items-center gap-3">
                        <button 
                            disabled={posts.length <= 1 || currentIndex === 0}
                            onClick={() => setCurrentIndex(prev => prev - 1)}
                            className="p-2 bg-gray-800 text-gray-300 rounded hover:bg-gray-700 disabled:opacity-30 transition"
                        >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
                        </button>
                        <span className="text-xs text-gray-400 font-mono">
                            {currentIndex + 1} / {posts.length}
                        </span>
                        <button 
                            disabled={posts.length <= 1 || currentIndex === posts.length - 1}
                            onClick={() => setCurrentIndex(prev => prev + 1)}
                            className="p-2 bg-gray-800 text-gray-300 rounded hover:bg-gray-700 disabled:opacity-30 transition"
                        >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                        </button>
                    </div>

                    <button 
                        onClick={onClose}
                        className="text-gray-400 hover:text-white px-4 py-2 border border-gray-700 hover:bg-gray-800 rounded transition text-sm"
                    >
                        Close
                    </button>
                </div>

            </div>
        </div>
    );
}
