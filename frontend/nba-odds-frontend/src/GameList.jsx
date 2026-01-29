import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { API_BASE_URL } from "./config";

function GameList() {
  const [games, setGames] = useState([]);
  const [filter, setFilter] = useState("live");

  const fetchGames = () => {
    axios.get(`${API_BASE_URL}/games?status=${filter}`).then((res) => {
      setGames(res.data);
    }).catch((err) => {
      console.error("Error fetching games:", err);
    });
  };

  const syncGames = () => {
    axios.post(`${API_BASE_URL}/games/sync`).then((res) => {
      console.log("Games synced:", res.data);
      fetchGames(); // Reload the list
    }).catch((err) => {
      console.error("Error syncing games:", err);
    });
  };

  useEffect(() => {
    fetchGames();
  }, [filter]);

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
        <button onClick={() => setFilter("")} style={{ marginLeft: "0.5rem" }}>All</button>
        <button onClick={syncGames} style={{ marginLeft: "1rem", backgroundColor: "#4CAF50", color: "white" }}>Sync Games</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "1rem" }}>
        {games.map((game) => (
          <div key={game.id} style={{ border: "1px solid #ccc", padding: "1rem", borderRadius: "8px" }}>
            <h3>{game.away_team} vs {game.home_team}</h3>
            <p>Status: {game.status}</p>
            <p>Last Polled: {game.last_polled_at ? new Date(game.last_polled_at).toLocaleString() : "Never"}</p>
            <Link to={`/game/${game.id}`}>
              <button>View Details</button>
            </Link>
          </div>
        ))}
      </div>

      {games.length === 0 && <p>No games found with status "{filter}".</p>}
    </div>
  );
}

export default GameList;