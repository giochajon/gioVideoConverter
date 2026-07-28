import { useCallback, useEffect, useState } from "react";
import { api, BatchLogEntry, SettingsResponse, TonightEntry, formatBytes } from "../api";

function formatDuration(seconds?: number): string {
  if (seconds == null) return "-";
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function Batch() {
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [tonight, setTonight] = useState<TonightEntry[]>([]);
  const [tonightQueued, setTonightQueued] = useState(false);
  const [log, setLog] = useState<BatchLogEntry[]>([]);
  const [view, setView] = useState<"queue" | "log">("queue");

  const load = useCallback(() => {
    api.getSettings().then(setSettings);
    api.batchTonight().then((res) => {
      setTonight(res.jobs);
      setTonightQueued(res.queued);
    });
    api.batchLog().then(setLog);
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [load]);

  async function setEnabled(enabled: boolean) {
    const updated = await api.putSettings({ batch_enabled: enabled });
    setSettings(updated);
  }

  async function setTarget(target: "movies" | "series") {
    const updated = await api.putSettings({ batch_target: target, batch_enabled: true });
    setSettings(updated);
  }

  async function removeQueueItem(jobId: string) {
    await api.removeBatchQueueItem(jobId);
    load();
  }

  async function removeLogEntry(startedAt: string) {
    await api.removeBatchLogEntry(startedAt);
    load();
  }

  async function pruneLog() {
    if (!confirm("Delete all log entries older than one week?")) return;
    await api.pruneBatchLog();
    load();
  }

  if (!settings) return <p>Loading...</p>;

  return (
    <div>
      <h1>Batch Mode</h1>

      <div className="panel">
        <label>
          <input
            type="checkbox"
            checked={settings.batch_enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            disabled={settings.batch_target === "none"}
          />{" "}
          Batch mode enabled (runs nightly {settings.batch_start_time}–{settings.batch_stop_time}, configurable in Settings)
        </label>

        <div className="radio-group" style={{ marginTop: "0.75rem" }}>
          <label style={{ marginBottom: 0 }}>
            <input
              type="radio"
              name="target"
              checked={settings.batch_target === "movies"}
              onChange={() => setTarget("movies")}
            />{" "}
            Movies (top 5 files &gt; 1.5GB)
          </label>
          <label style={{ marginBottom: 0 }}>
            <input
              type="radio"
              name="target"
              checked={settings.batch_target === "series"}
              onChange={() => setTarget("series")}
            />{" "}
            Series (largest series folder, one season/night)
          </label>
        </div>
      </div>

      <div className="root-tabs">
        <button className={view === "queue" ? "primary" : ""} onClick={() => setView("queue")}>
          Queued
        </button>
        <button className={view === "log" ? "primary" : ""} onClick={() => setView("log")}>
          Recently Processed
        </button>
      </div>

      {view === "queue" && (
        <div className="panel">
          <h2>Tonight's Queue</h2>
          {tonight.length === 0 && <p style={{ color: "#9aa4b2" }}>Nothing queued yet.</p>}
          {tonight.length > 0 && !tonightQueued && (
            <p style={{ color: "#9aa4b2", fontSize: "0.85rem" }}>
              Preview — this will be queued automatically between {settings.batch_start_time}–{settings.batch_stop_time}.
            </p>
          )}
          <table>
            <thead>
              <tr>
                <th>File</th>
                <th>Status</th>
                <th>Size</th>
                {tonightQueued && <th></th>}
              </tr>
            </thead>
            <tbody>
              {tonight.map((j, i) => (
                <tr key={j.id ?? i}>
                  <td>{j.source_path.split("/").pop()}</td>
                  <td><span className={`badge ${j.status}`}>{j.status}</span></td>
                  <td>{formatBytes(j.initial_size)}</td>
                  {tonightQueued && (
                    <td>
                      {j.id && j.status === "queued" && (
                        <button onClick={() => removeQueueItem(j.id!)}>Remove</button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {view === "log" && (
        <div className="panel">
          <div className="toolbar">
            <h2>Conversion Log</h2>
            <button onClick={pruneLog}>Delete older than 1 week</button>
          </div>
          <table>
            <thead>
              <tr>
                <th>Started</th>
                <th>Finished</th>
                <th>Duration</th>
                <th>File</th>
                <th>Before</th>
                <th>After</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {log.map((entry, i) => (
                <tr key={i}>
                  <td>{new Date(entry.started_at).toLocaleString()}</td>
                  <td>{entry.finished_at ? new Date(entry.finished_at).toLocaleString() : "-"}</td>
                  <td>{formatDuration(entry.duration_seconds)}</td>
                  <td>{entry.filename}</td>
                  <td>{formatBytes(entry.initial_size)}</td>
                  <td>{entry.final_size ? formatBytes(entry.final_size) : "-"}</td>
                  <td><span className={`badge ${entry.status}`}>{entry.status}</span></td>
                  <td>
                    <button onClick={() => removeLogEntry(entry.started_at)}>Remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
