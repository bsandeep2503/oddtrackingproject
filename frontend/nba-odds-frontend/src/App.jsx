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
} from "recharts";

function App() {
  console.log("App component rendering");
  const [quarters, setQuarters] = useState([]);
  const [liveSnapshots, setLiveSnapshots] = useState([]);
  const [gameInfo, setGameInfo] = useState({ home: "Home", away: "Away" });
  const GAME_ID = 2; // Match the poller's game ID
  const [liveGameId, setLiveGameId] = useState(null);
  const formatNumber = (value, digits = 2) =>
    typeof value === "number" && Number.isFinite(value)
      ? value.toFixed(digits)
      : "—";
  const normalizedQuarters = quarters.map((q) => ({
    ...q,
    stage:
      typeof q.stage === "string"
        ? q.stage.replace(/^Q0+(\d+)$/, "Q$1")
        : q.stage,
  }));

  const fetchData = () => {
    // Trigger a live scrape to refresh snapshots
    axios
      .post(`${API_BASE_URL}/games/${GAME_ID}/scrape-live`)
      .catch((err) => console.error("Error scraping live game:", err));

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

      {/* Moneyline chart */}
      <h2>Moneyline Odds by Stage</h2>
      <LineChart width={900} height={300} data={normalizedQuarters}>
        <CartesianGrid stroke="#ccc" />
        <XAxis dataKey="stage" />
        <YAxis />
        <Tooltip />
        <Legend />
        <Line
          type="monotone"
          dataKey="ml_home"
          stroke="#1f77b4"
          name="Home ML"
        />
        <Line
          type="monotone"
          dataKey="ml_away"
          stroke="#ff7f0e"
          name="Away ML"
        />
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
