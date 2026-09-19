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

type ConflictingHold = { row: number; start_col: number; end_col: number };

/** 依据错误包络的 code/details 生成对用户友好的冲突提示。 */
function describeError(e: unknown): string {
  if (!(e instanceof ApiError)) return e instanceof Error ? e.message : String(e);
  const d = e.details as Record<string, unknown>;
  const party = typeof d.party_size === "number" ? d.party_size : undefined;

  switch (e.code) {
    case "not_found":
      return e.message || "场次不存在";
    case "seats_unavailable":
      return party ? `${e.message}：${party} 人连座已售罄，可减少人数或更换场次` : e.message;
    case "seat_overlap": {
      const hits = Array.isArray(d.conflicting_holds)
        ? (d.conflicting_holds as ConflictingHold[])
        : [];
      const where = hits
        .map((h) => `第${h.row}排 ${h.start_col}-${h.end_col}座`)
        .join("、");
      return where ? `${e.message}：所选座位与他人持座重叠（${where}），请重试` : e.message;
    }
    case "validation_error":
      return "请求参数不合法，请检查人数（1-12）与场次";
    default:
      return e.message || "操作失败，请稍后重试";
  }
}

export default function HoldPage() {
  const [shows, setShows] = useState<Show[]>([]);
  const [sid, setSid] = useState<number | "">("");
  const [party, setParty] = useState(3);
  const [prefRow, setPrefRow] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [last, setLast] = useState<Hold | null>(null);

  useEffect(() => {
    api<Show[]>("/showtimes").then((s) => {
      setShows(s);
      if (s[0]) setSid(s[0].id);
    });
  }, []);

  async function submit() {
    setMsg("");
    setErr("");
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
      {err && <div className="err">{err}</div>}
      {last && (
        <p className="mono">
          订单 {last.order_code} · {last.party_size} 人 · R{last.row} C{last.start_col}-{last.end_col}
        </p>
      )}
    </>
  );
}
