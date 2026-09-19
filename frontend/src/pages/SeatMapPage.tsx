import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api/client";

type Show = { id: number; film_title: string; hall_name?: string };
type Cell = { row: number; col: number; is_aisle: boolean; occupied: boolean; heat: number };
type MapOut = { showtime_id: number; hall_name: string; rows: number; cols: number; cells: Cell[] };

export default function SeatMapPage() {
  const [shows, setShows] = useState<Show[]>([]);
  const [sid, setSid] = useState<number | "">("");
  const [map, setMap] = useState<MapOut | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api<Show[]>("/showtimes").then((s) => {
      setShows(s);
      if (s[0]) setSid(s[0].id);
    });
  }, []);

  useEffect(() => {
    if (sid === "") return;
    setErr("");
    setMap(null);
    api<MapOut>(`/seatmap/${sid}`)
      .then(setMap)
      .catch((e: unknown) => {
        setErr(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e));
      });
  }, [sid]);

  const gridStyle = useMemo(
    () => ({ gridTemplateColumns: map ? `repeat(${map.cols}, 28px)` : undefined }),
    [map]
  );

  return (
    <>
      <div className="toolbar">
        <label>
          场次{" "}
          <select value={sid} onChange={(e) => setSid(Number(e.target.value))}>
            {shows.map((s) => (
              <option key={s.id} value={s.id}>
                {s.film_title} · {s.hall_name}
              </option>
            ))}
          </select>
        </label>
        {map && (
          <span className="mono">
            {map.hall_name} · {map.rows}×{map.cols} · 热力座图
          </span>
        )}
      </div>
      <div className="screen">银 幕</div>
      {err && <div className="err">{err}</div>}
      {map && (
        <div className="seat-grid" style={gridStyle}>
          {map.cells.map((c) => (
            <div
              key={`${c.row}-${c.col}`}
              className={`seat ${c.is_aisle ? "aisle" : c.occupied ? "occ" : "free"}`}
              title={`R${c.row}C${c.col}`}
              style={
                !c.is_aisle && c.heat
                  ? { boxShadow: `inset 0 0 0 1px rgba(255,180,80,${Math.min(0.9, c.heat / 10)})` }
                  : undefined
              }
            >
              {c.is_aisle ? "" : c.col}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
