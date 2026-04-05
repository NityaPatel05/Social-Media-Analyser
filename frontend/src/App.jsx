import {
  BrowserRouter as Router,
  Routes,
  Route,
  NavLink,
} from "react-router-dom";
import OverviewPage from "./pages/OverviewPage";
import TimeSeriesPage from "./pages/TimeSeriesPage";
import NetworkPage from "./pages/NetworkPage";
import TopicPage from "./pages/TopicPage";
import SpamPage from "./pages/SpamPage";
import ChatPage from "./pages/ChatPage";
import { useState } from "react";

const navItems = [
  { path: "/", label: "Overview" },
  { path: "/timeseries", label: "Time-Series" },
  { path: "/network", label: "Network" },
  { path: "/topics", label: "Topics" },
  { path: "/spam", label: "Spam" },
  { path: "/chat", label: "Chat" },
];

export default function App() {
  const [spamThreshold, setSpamThreshold] = useState(1.0);

  return (
    <Router>
      <div className="h-screen flex flex-col">
        {/* Top bar with spam filter */}
        <div className="bg-gray-900 border-b border-gray-800 px-4 py-2 flex items-center justify-between">
          <h1 className="text-lg font-bold text-blue-400">
            Narrative Intelligence
          </h1>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-gray-400">Spam filter:</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={spamThreshold}
              onChange={(e) => setSpamThreshold(parseFloat(e.target.value))}
              className="w-32"
            />
            <span className="text-gray-300 w-10">
              {spamThreshold.toFixed(2)}
            </span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="bg-gray-900 border-b border-gray-800 px-4 flex gap-1">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `px-4 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "text-blue-400 border-b-2 border-blue-400"
                    : "text-gray-400 hover:text-gray-200"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Page content */}
        <main className="flex-1 p-6 overflow-y-auto min-h-0">
          <Routes>
            <Route
              path="/"
              element={<OverviewPage spamThreshold={spamThreshold} />}
            />
            <Route
              path="/timeseries"
              element={<TimeSeriesPage spamThreshold={spamThreshold} />}
            />
            <Route
              path="/network"
              element={<NetworkPage spamThreshold={spamThreshold} />}
            />
            <Route
              path="/topics"
              element={<TopicPage spamThreshold={spamThreshold} />}
            />
            <Route
              path="/spam"
              element={<SpamPage spamThreshold={spamThreshold} />}
            />
            <Route
              path="/chat"
              element={<ChatPage spamThreshold={spamThreshold} />}
            />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
