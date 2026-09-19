import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";

type Show = { id: number; film_title: string; hall_name?: string };
type Hold = {
  id: number;
  order_code: string;
  row: number;
  start_col: number;
  end_col: number;
  party_size: number;
};

type ErrBox = { code: string; message: string; hint?: string };

function describeError(e: unknown): ErrBox {
  if (e instanceof ApiError) {
    const d = e.details as
      | { row?: number; start_col?: number; end_col?: number; party_size?: number }
      | undefined;
    let hint: string | undefined;
    if (e.code === "HOLD_OVERLAP" && d?.row != null) {
      hint = `重叠位置：第${d.row}排 ${d.start_col}-${d.end_col}列`;
    } else if (e.code === "INSUFFICIENT_CONTIGUOUS_SEATS" && d?.party_size != null) {
      hint = `本场次暂无 ${d.party_size} 人连座，可减少人数或换场次`;
    }
    return { code: e.code, message: e.message, hint };
  }
  return { code: "UNKNOWN", message: e instanceof Error ? e.message : String(e) };
}

export default function HoldPage() {
  const [shows, setShows] = useState<Show[]>([]);
  const [sid, setSid] = useState<number | "">("");
  const [party, setParty] = useState(3);
  const [prefRow, setPrefRow] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState<ErrBox | null>(null);
  const [last, setLast] = useState<Hold | null>(null);

  useEffect(() => {
    api<Show[]>("/showtimes").then((s) => {
      setShows(s);
      if (s[0]) setSid(s[0].id);
    });
  }, []);

  async function submit() {
    setMsg("");
    setErr(null);
    try {
      const body: Record<string, unknown> = { showtime_id: sid, party_size: party };
      if (prefRow) body.preferred_row = Number(prefRow);
      const hold = await api<Hold>("/holds", { method: "POST", body: JSON.stringify(body) });
      setLast(hold);
      setMsg(`已锁座 ${hold.order_code}：第${hold.row}排 ${hold.start_col}-${hold.end_col}`);
    } catch (e) {
      setErr(describeError(e));
    }
  }

  return (
    <>
      <h2>锁座</h2>
      <div className="toolbar">
        <select value={sid} onChange={(e) => setSid(Number(e.target.value))}>
          {shows.map((s) => (
            <option key={s.id} value={s.id}>
              {s.film_title} · {s.hall_name}
            </option>
          ))}
        </select>
        <label>
          人数{" "}
          <input
            type="number"
            min={1}
            max={12}
            value={party}
            onChange={(e) => setParty(Number(e.target.value))}
            style={{ width: 72 }}
          />
        </label>
        <label>
          优先排{" "}
          <input
            value={prefRow}
            onChange={(e) => setPrefRow(e.target.value)}
            placeholder="可选"
            style={{ width: 72 }}
          />
        </label>
        <button onClick={submit}>查找并锁连座</button>
      </div>
      {msg && <div className="ok">{msg}</div>}
      {err && (
        <div className="err">
          <div>{err.message}</div>
          {err.hint && <div>{err.hint}</div>}
          <div className="mono">错误码 {err.code}</div>
        </div>
      )}
      {last && (
        <p className="mono">
          订单 {last.order_code} · {last.party_size} 人 · R{last.row} C{last.start_col}-{last.end_col}
        </p>
      )}
    </>
  );
}
