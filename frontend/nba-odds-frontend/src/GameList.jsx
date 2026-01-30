import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { API_BASE_URL } from "./config";

function GameList() {
  const [games, setGames] = useState([]);
  const [filter, setFilter] = useState(null); // Default to all games
  const [error, setError] = useState(null);

  const fetchGames = () => {
    setError(null);
    const url = filter ? `${API_BASE_URL}/games?status=${filter}` : `${API_BASE_URL}/games`;
    axios.get(url)
      .then((res) => setGames(res.data))
      .catch((err) => setError("Backend unreachable. Is API running on 8000?"));
  };

  useEffect(() => {
    fetchGames();
    const interval = setInterval(fetchGames, 15000); // auto-retry every 15s
    return () => clearInterval(interval);
  }, [filter]);

  const handleSync = () => {
    axios.post(`${API_BASE_URL}/games/sync`).then(() => {
      axios.get(`${API_BASE_URL}/games?status=${filter}`).then((res) => {
        setGames(res.data);
      });
    });
  };

  // Poll for live updates every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      if (filter === "live" || filter === "") {
        fetchGames();
      }
    }, 30000); // 30 seconds

    return () => clearInterval(interval);
  }, [filter]);

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>NBA Odds Momentum - Game List</h1>

      <div style={{ marginBottom: "1rem" }}>
        <button onClick={() => setFilter("scheduled")}>Scheduled</button>
        <button onClick={() => setFilter("live")} style={{ marginLeft: "0.5rem" }}>Live</button>
        <button onClick={() => setFilter("final")} style={{ marginLeft: "0.5rem" }}>Final</button>
        <button onClick={() => setFilter(null)} style={{ marginLeft: "0.5rem" }}>All</button>
        <button onClick={handleSync} style={{ marginLeft: "0.5rem", background: "#2e7d32", color: "white" }}>
          Sync Games
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "1rem" }}>
        {games.map((game) => (
          <div key={game.id} style={{ border: "1px solid #ccc", padding: "1rem", borderRadius: "8px" }}>
            <h3>{game.away_team} vs {game.home_team}</h3>
            <p>Status: {game.status}</p>
            <p>Start: {game.start_time ? new Date(game.start_time).toLocaleString() : "TBD"}</p>
            <p>Pregame ML: {game.pregame_ml_away ?? "—"} / {game.pregame_ml_home ?? "—"}</p>
            <p>Spread: {game.pregame_spread ?? "—"} | Total: {game.pregame_total ?? "—"}</p>
            <p>Last Polled: {game.last_polled_at ? new Date(game.last_polled_at).toLocaleString() : "Never"}</p>
            <Link to={`/game/${game.id}`}>
              <button>View Details</button>
            </Link>
          </div>
        ))}
      </div>

      {error && <p style={{ color: "red" }}>{error}</p>}
      {games.length === 0 && !error && <p>No games found with status "{filter ?? "all"}".</p>}
    </div>
  );
}

export default GameList;