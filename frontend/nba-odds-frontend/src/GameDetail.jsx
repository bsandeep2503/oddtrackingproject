import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
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

function GameDetail() {
  const { gameId } = useParams();
  const [quarters, setQuarters] = useState([]);
  const [liveSnapshots, setLiveSnapshots] = useState([]);
  const [gameInfo, setGameInfo] = useState({ home: "Home", away: "Away" });
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
    axios.get(`${API_BASE_URL}/games/${gameId}/replay?speed=${replaySpeed}`)
      .then(res => {
        setReplayData(res.data.snapshots);
        setReplayCursor(0);
        setReplayMode(true);
      });
  };

  useEffect(() => {
    if (!replayMode) return;
    if (replayCursor >= replayData.length - 1) return;

    const t = setInterval(() => setReplayCursor(c => c + 1), replaySpeed * 1000);
    return () => clearInterval(t);
  }, [replayMode, replayCursor, replaySpeed, replayData]);

  useEffect(() => {
    axios.get(`${API_BASE_URL}/games/${gameId}/health`)
      .then(res => setGapInfo(res.data.gaps || []));
  }, [gameId]);

  const displayed = replayMode ? replayData.slice(0, replayCursor + 1) : normalizedQuarters;

  useEffect(() => {
    const fetchData = () => {
      // Fetch game info
      axios
        .get(`${API_BASE_URL}/games/${gameId}`)
        .then((res) => {
          setGameInfo({
            home: res.data.home_team || "Home",
            away: res.data.away_team || "Away"
          });
        })
        .catch((err) => console.error("Error fetching game info:", err));

      // Fetch quarters
      axios
        .get(`${API_BASE_URL}/games/${gameId}/quarters`)
        .then((res) => setQuarters(res.data))
        .catch((err) => console.error("Error fetching quarter snapshots:", err));

      // Fetch insights
      axios
        .get(`${API_BASE_URL}/games/${gameId}/insights`)
        .then((res) => setInsights(res.data))
        .catch((err) => console.error("Error fetching insights:", err));
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [gameId]);

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <Link to="/">← Back to Game List</Link>
      <h1>NBA Odds Momentum – {gameInfo.away} vs {gameInfo.home}</h1>

      <button onClick={startReplay}>Replay Game</button>
      <button onClick={() => setReplayMode(false)} style={{ marginLeft: 8 }}>Stop Replay</button>

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

export default GameDetail;