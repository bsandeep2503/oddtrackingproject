import { useEffect, useState } from "react";
import api from "./services/api";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend
} from "recharts";

interface OddsSnapshot {
  id: number;
  timestamp: string;
  moneyline_home: number;
  moneyline_away: number;
}

function App() {
  const [odds, setOdds] = useState<OddsSnapshot[]>([]);

  useEffect(() => {
    api.get("/games/1/odds")
      .then((res) => setOdds(res.data))
      .catch((err) => console.error("Error fetching odds:", err));
  }, []);

  return (
    <div style={{ padding: 20 }}>
      <h1>NBA Odds Momentum</h1>
      <LineChart width={800} height={400} data={odds}>
        <CartesianGrid stroke="#ccc" />
        <XAxis dataKey="timestamp" />
        <YAxis />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="moneyline_home" stroke="#8884d8" name="Home ML" />
        <Line type="monotone" dataKey="moneyline_away" stroke="#82ca9d" name="Away ML" />
      </LineChart>
    </div>
  );
}

export default App;
