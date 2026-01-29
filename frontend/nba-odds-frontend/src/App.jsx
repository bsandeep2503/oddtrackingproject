import { useEffect, useState } from "react";
import axios from "axios";
import { API_BASE_URL } from "./config";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ReferenceDot,
} from "recharts";

function App() {
  console.log("App component rendering");
  const [quarters, setQuarters] = useState([]);
  const [liveSnapshots, setLiveSnapshots] = useState([]);
  const [gameInfo, setGameInfo] = useState({ home: "Home", away: "Away" });
  const GAME_ID = 2; // Match the poller's game ID
  const [liveGameId, setLiveGameId] = useState(null);
  const [insights, setInsights] = useState({ summary: {}, events: [] });
  const [replayMode, setReplayMode] = useState(false);
  const [replayCursor, setReplayCursor] = useState(0);
  const [replaySpeed, setReplaySpeed] = useState(2);
  const [replayData, setReplayData] = useState([]);
  const [gapInfo, setGapInfo] = useState([]);
  const formatNumber = (value, digits = 2) =>
    typeof value === "number" && Number.isFinite(value)
      ? value.toFixed(digits)
      : "—";
  const normalizedQuarters = quarters.map((q, i) => {
    const probHome = q.ml_home ? 1 / q.ml_home : null;
    const probAway = q.ml_away ? 1 / q.ml_away : null;
    const prev = quarters[i - 1];
    const prevProbHome = prev?.ml_home ? 1 / prev.ml_home : null;
    const swing = (probHome != null && prevProbHome != null) ? (probHome - prevProbHome) : 0;

    return {
      ...q,
      stage: typeof q.stage === "string" ? q.stage.replace(/^Q0+(\d+)$/, "Q$1") : q.stage,
      probHome,
      probAway,
      swing,
      swingFlag: Math.abs(swing) > 0.08, // 8% threshold
    };
  });

  const startReplay = () => {
    axios.get(`${API_BASE_URL}/games/${GAME_ID}/replay?speed=${replaySpeed}`)
      .then(res => {
        setReplayData(res.data.snapshots);
        setReplayCursor(0);
        setReplayMode(true);
      });
  };

  const fetchData = () => {
    // Fetch game info
    axios
      .get(`${API_BASE_URL}/games/${GAME_ID}`)
      .then((res) => {
        setGameInfo({
          home: res.data.home_team || "Home",
          away: res.data.away_team || "Away"
        });
      })
      .catch((err) => console.error("Error fetching game info:", err));

    // Fetch quarters
    axios
      .get(`${API_BASE_URL}/games/${GAME_ID}/quarters`)
      .then((res) => setQuarters(res.data))
      .catch((err) => console.error("Error fetching quarter snapshots:", err));

    // Fetch insights
    axios
      .get(`${API_BASE_URL}/games/${GAME_ID}/insights`)
      .then((res) => setInsights(res.data))
      .catch((err) => console.error("Error fetching insights:", err));

    // Trigger a demo Pinnacle poll to populate sample data
    axios
      .post(`${API_BASE_URL}/pinnacle/demo-poll`)
      .then(() => {
        axios
          .get(`${API_BASE_URL}/pinnacle/games`)
          .then((res) => {
            if (res.data && res.data.length > 0) {
              const gid = res.data[0].game_id;
              setLiveGameId(gid);
              // fetch live snapshots for that game
              axios
                .get(`${API_BASE_URL}/games/${encodeURIComponent(gid)}/live-snapshots`)
                .then((r) => setLiveSnapshots(r.data))
                .catch((e) => console.error("Error fetching live snapshots:", e));
            }
          })
          .catch((e) => console.error("Error listing pinnacle games:", e));
      })
      .catch((err) => console.error("Error polling Pinnacle:", err));
  };

  useEffect(() => {
    // Fetch immediately on load
    fetchData();
    
    // Then refresh every 5 seconds to see real-time updates
    const interval = setInterval(fetchData, 5000);

    // Also poll live snapshots frequently if we have a liveGameId
    let liveInterval = null;
    if (liveGameId) {
      liveInterval = setInterval(() => {
        axios
          .get(`${API_BASE_URL}/games/${encodeURIComponent(liveGameId)}/live-snapshots`)
          .then((r) => setLiveSnapshots(r.data))
          .catch((e) => console.error("Error fetching live snapshots:", e));
      }, 5000);
    }

    return () => {
      clearInterval(interval);
      if (liveInterval) clearInterval(liveInterval);
    };
  }, [liveGameId]);

  useEffect(() => {
    if (!replayMode) return;
    if (replayCursor >= replayData.length - 1) return;

    const t = setInterval(() => setReplayCursor(c => c + 1), replaySpeed * 1000);
    return () => clearInterval(t);
  }, [replayMode, replayCursor, replaySpeed, replayData]);

  useEffect(() => {
    axios.get(`${API_BASE_URL}/games/${GAME_ID}/health`)
      .then(res => setGapInfo(res.data.gaps || []));
  }, []);

  const displayed = replayMode ? replayData.slice(0, replayCursor + 1) : normalizedQuarters;

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>NBA Odds Momentum – Quarter by Quarter</h1>
      <button
        onClick={() => {
          axios
            .post(`${API_BASE_URL}/games/${GAME_ID}/scrape-pregame`)
            .then(() => fetchData())
            .catch((err) => console.error("Error scraping:", err));
        }}
      >
        Scrape Pre-Game Odds Now
      </button>
      <button
        onClick={() => {
          axios
            .post(`${API_BASE_URL}/games/${GAME_ID}/scrape-live`)
            .then(() => fetchData())
            .catch((err) => console.error("Error scraping:", err));
        }}
        style={{ marginLeft: "1rem" }}
      >
        Scrape Live Odds Now
      </button>
      <button
        onClick={() => {
          axios
            .delete(`${API_BASE_URL}/games/${GAME_ID}/clear`)
            .then(() => fetchData())
            .catch((err) => console.error("Error clearing:", err));
        }}
        style={{ marginLeft: "1rem", backgroundColor: "#f44336" }}
      >
        Clear Data
      </button>
      <button onClick={startReplay} style={{ marginLeft: "1rem" }}>
        Replay Game
      </button>
      <button onClick={() => setReplayMode(false)} style={{ marginLeft: "0.5rem" }}>
        Stop Replay
      </button>

      {/* Momentum Pill */}
      {(() => {
        const lastSwing = [...normalizedQuarters].reverse().find(n => n.swingFlag);
        return lastSwing && (
          <div style={{ margin: "10px 0", padding: "6px 10px", background: "#222", color: "#fff", borderRadius: 6 }}>
            Momentum: {lastSwing.swing > 0 ? "Home surge" : "Home dip"} ({(lastSwing.swing*100).toFixed(1)}%)
          </div>
        );
      })()}

      {/* Moneyline chart */}
      <h2>Moneyline Odds by Stage</h2>
      <LineChart width={900} height={300} data={displayed}>
        <CartesianGrid stroke="#ccc" />
        <XAxis dataKey="stage" />
        <YAxis domain={[0, 1]} />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="probHome" stroke="#1f77b4" name="Home Win Prob" dot={false} />
        <Line type="monotone" dataKey="probAway" stroke="#ff7f0e" name="Away Win Prob" dot={false} />

        {displayed.map((p, i) =>
          p.swingFlag ? (
            <ReferenceDot
              key={i}
              x={p.stage}
              y={p.probHome}
              r={5}
              fill={p.swing > 0 ? "green" : "red"}
            />
          ) : null
        )}
      </LineChart>

      {/* Live market movement */}
      <h2 style={{ marginTop: "2rem" }}>Live Market Movement</h2>
      {!liveGameId && <p>No live Pinnacle games found. Click poll to populate.</p>}
      {liveGameId && (
        <div>
          <p style={{ fontSize: "0.9rem", color: "#666" }}>Live Game ID: {liveGameId}</p>
          <LineChart width={900} height={300} data={liveSnapshots.map((s, idx) => ({
            ...s,
            teamA_prob: s.teamA_ml ? (1 / s.teamA_ml).toFixed(3) : null,
            teamB_prob: s.teamB_ml ? (1 / s.teamB_ml).toFixed(3) : null,
            label: `Q${s.quarter || '?'} ${s.game_clock || ''}`
          }))}>
            <CartesianGrid stroke="#ccc" />
            <XAxis dataKey="label" />
            <YAxis domain={[0, 1]} />
            <Tooltip 
              formatter={(value) => value ? parseFloat(value).toFixed(3) : 'N/A'}
              labelFormatter={(label) => `Game State: ${label}`}
            />
            <Legend />
            <Line type="monotone" dataKey="teamA_prob" stroke="#1f77b4" name="Team A (Hornets) Win Prob" isAnimationActive={false} />
            <Line type="monotone" dataKey="teamB_prob" stroke="#ff7f0e" name="Team B (76ers) Win Prob" isAnimationActive={false} />
          </LineChart>
          <p style={{ fontSize: "0.85rem", color: "#999", marginTop: "1rem" }}>
            Snapshots: {liveSnapshots.length} | Score progression: {liveSnapshots.map(s => `${s.teamA_score}-${s.teamB_score}`).join(" → ")}
          </p>
        </div>
      )}

      {/* Spread chart */}
      <h2 style={{ marginTop: "2rem" }}>Spread Movement (Full Game)</h2>
      <LineChart width={900} height={300} data={normalizedQuarters}>
        <CartesianGrid stroke="#ccc" />
        <XAxis dataKey="stage" />
        <YAxis />
        <Tooltip />
        <Legend />
        <Line
          type="monotone"
          dataKey="spread"
          stroke="#2ca02c"
          name="Spread (Home)"
        />
      </LineChart>

      {/* Score differential chart */}
      <h2 style={{ marginTop: "2rem" }}>Score Differential (Home - Away)</h2>
      <LineChart width={900} height={300} data={normalizedQuarters}>
        <CartesianGrid stroke="#ccc" />
        <XAxis dataKey="stage" />
        <YAxis />
        <Tooltip />
        <Legend />
        <Line
          type="monotone"
          dataKey="score_diff"
          stroke="#d62728"
          name="Score Differential"
        />
      </LineChart>

      {/* Table view */}
      <h2 style={{ marginTop: "2rem" }}>Quarter Summary</h2>
      <p style={{ fontSize: "0.9rem", color: "#666" }}>
        Game: <strong>{gameInfo.away}</strong> vs <strong>{gameInfo.home}</strong>
      </p>
      <table
        style={{
          borderCollapse: "collapse",
          width: "100%",
          marginTop: "1rem",
        }}
      >
        <thead>
          <tr>
            <th style={thStyle}>Stage</th>
            <th style={thStyle}>Score</th>
            <th style={thStyle}>Differential</th>
            <th style={thStyle}>Moneyline Odds</th>
            <th style={thStyle}>Spread</th>
          </tr>
        </thead>
        <tbody>
          {normalizedQuarters.map((q) => (
            <tr key={q.id}>
              <td style={tdStyle}>{q.stage}</td>
              <td style={tdStyle}>
                {gameInfo.away} {q.score_away} - {gameInfo.home} {q.score_home}
              </td>
              <td style={tdStyle}>{q.score_diff}</td>
              <td style={tdStyle}>
                {formatNumber(q.ml_away)} / {formatNumber(q.ml_home)}
              </td>
              <td style={tdStyle}>{q.spread}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Insights Panel */}
      <h2 style={{ marginTop: "2rem" }}>Odds Insights & Momentum</h2>
      <div style={{ display: "flex", gap: "2rem", marginTop: "1rem" }}>
        <div style={{ flex: 1 }}>
          <h3>Current Summary</h3>
          <p><strong>Favorite:</strong> {insights.summary?.favorite || "N/A"}</p>
          <p><strong>Home Win Prob:</strong> {insights.summary?.current_prob_home ? `${(insights.summary.current_prob_home * 100).toFixed(1)}%` : "N/A"}</p>
          <p><strong>Away Win Prob:</strong> {insights.summary?.current_prob_away ? `${(insights.summary.current_prob_away * 100).toFixed(1)}%` : "N/A"}</p>
        </div>
        <div style={{ flex: 2 }}>
          <h3>Recent Events</h3>
          {insights.events?.length > 0 ? (
            <ul style={{ maxHeight: "200px", overflowY: "auto" }}>
              {insights.events.slice(-5).reverse().map((event, idx) => (
                <li key={idx} style={{ marginBottom: "0.5rem" }}>
                  <strong>{event.type.replace('_', ' ').toUpperCase()}:</strong> {event.detail} <br />
                  <small style={{ color: "#666" }}>{new Date(event.timestamp).toLocaleString()}</small>
                </li>
              ))}
            </ul>
          ) : (
            <p>No momentum events detected yet.</p>
          )}
        </div>
      </div>

      {/* Gap Warnings */}
      {gapInfo.length > 0 && (
        <div style={{ color: "orange", marginTop: 10 }}>
          ⚠ Missing data: {gapInfo.map((g, i) =>
            <div key={i}>{g.from} → {g.to} ({g.gap_seconds}s)</div>
          )}
        </div>
      )}
    </div>
  );
}

const thStyle = {
  border: "1px solid #ddd",
  padding: "8px",
  backgroundColor: "#f2f2f2",
  textAlign: "left",
};

const tdStyle = {
  border: "1px solid #ddd",
  padding: "8px",
};

export default App;
