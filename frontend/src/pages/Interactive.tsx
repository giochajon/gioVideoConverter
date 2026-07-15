import { useCallback, useEffect, useState } from "react";
import { api, BrowseResponse, BrowseRoot, RootsResponse, StatusResponse, formatBytes } from "../api";

const ROOT_LABELS: Record<BrowseRoot, string> = {
  interactive: "Interactive",
  movies: "Movies",
  series: "Series",
};

export default function Interactive() {
  const [root, setRoot] = useState<BrowseRoot>("interactive");
  const [roots, setRoots] = useState<RootsResponse | null>(null);
  const [browse, setBrowse] = useState<BrowseResponse | null>(null);
  const [cwd, setCwd] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadBrowse = useCallback((forRoot: BrowseRoot, path: string) => {
    setLoading(true);
    setError(null);
    api
      .browse(forRoot, path)
      .then((res) => {
        setBrowse(res);
        setCwd(path);
      })
      .catch((err) => setError(err.message || "failed to load folder"))
      .finally(() => setLoading(false));
  }, []);

  const loadStatus = useCallback(() => {
    api.status().then(setStatus).catch(() => {});
  }, []);

  const loadRoots = useCallback(() => {
    api.roots().then(setRoots).catch(() => {});
  }, []);

  useEffect(() => {
    loadRoots();
    loadStatus();
    const interval = setInterval(loadStatus, 2000);
    return () => clearInterval(interval);
  }, [loadRoots, loadStatus]);

  useEffect(() => {
    loadBrowse(root, "");
    setSelected(new Set());
  }, [root, loadBrowse]);

  function switchRoot(next: BrowseRoot) {
    if (next === root) return;
    setRoot(next);
  }

  function toggleSelect(path: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  async function enqueueSelected() {
    if (selected.size === 0) return;
    await api.enqueue(Array.from(selected));
    setSelected(new Set());
    loadStatus();
  }

  async function stopAll() {
    if (!confirm("Stop all conversion processes and clear the interactive queue?")) return;
    await api.stopAll();
    loadStatus();
  }

  async function resume() {
    await api.resume();
    loadStatus();
  }

  const parts = cwd.split("/").filter(Boolean);
  const currentRootInfo = roots?.[root];
  const permOk = !currentRootInfo || (currentRootInfo.readable && currentRootInfo.writable);

  return (
    <div>
      <div className="toolbar">
        <h1>Interactive Mode</h1>
        <button className="stop" onClick={stopAll}>■ STOP ALL</button>
      </div>

      {status?.halted && (
        <div className="halt-banner">
          <div>
            <strong>Processing halted</strong> — a conversion failed and the queue was left untouched for review.
            <div style={{ fontSize: "0.85rem", opacity: 0.85 }}>{status.halted.error}</div>
          </div>
          <button onClick={resume}>Resume</button>
        </div>
      )}

      <div className="panel">
        <div className="root-tabs">
          {(Object.keys(ROOT_LABELS) as BrowseRoot[]).map((key) => {
            const info = roots?.[key];
            const bad = info && (!info.readable || !info.writable);
            return (
              <button
                key={key}
                className={key === root ? "primary" : ""}
                onClick={() => switchRoot(key)}
                title={info?.path}
              >
                {ROOT_LABELS[key]}
                {bad ? " ⚠" : ""}
              </button>
            );
          })}
        </div>

        {currentRootInfo && !permOk && (
          <div className="perm-warning">
            <strong>{ROOT_LABELS[root]}</strong> ({currentRootInfo.path}):{" "}
            {!currentRootInfo.readable && "no read access — this folder can't be browsed."}
            {currentRootInfo.readable && !currentRootInfo.writable &&
              "no write access — files can be browsed but conversion will fail (can't write the output or delete the original)."}
          </div>
        )}

        <div className="breadcrumb">
          <a href="#" onClick={(e) => { e.preventDefault(); loadBrowse(root, ""); }}>{ROOT_LABELS[root]}</a>
          {parts.map((p, i) => (
            <span key={i}>
              {" / "}
              <a
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  loadBrowse(root, parts.slice(0, i + 1).join("/"));
                }}
              >
                {p}
              </a>
            </span>
          ))}
        </div>

        {loading && <p>Loading...</p>}
        {error && <p style={{ color: "#f87171" }}>{error}</p>}

        {browse?.dirs.map((d) => (
          <div className="dir-row" key={d.path}>
            <a href="#" onClick={(e) => { e.preventDefault(); loadBrowse(root, d.path); }}>📁 {d.name}</a>
          </div>
        ))}

        {browse?.files.map((f) => (
          <div className="file-row" key={f.path}>
            <input
              type="checkbox"
              checked={selected.has(f.path)}
              onChange={() => toggleSelect(f.path)}
            />
            <span>{f.name}</span>
            <span style={{ color: "#9aa4b2", fontSize: "0.85rem" }}>{formatBytes(f.size)}</span>
          </div>
        ))}

        <div style={{ marginTop: "1rem" }}>
          <button
            className="primary"
            disabled={selected.size === 0 || currentRootInfo?.writable === false}
            onClick={enqueueSelected}
          >
            Enqueue Selected ({selected.size})
          </button>
        </div>
      </div>

      <div className="panel">
        <h2>Queue &amp; Status</h2>
        <table>
          <thead>
            <tr>
              <th>File</th>
              <th>Mode</th>
              <th>Status</th>
              <th>Progress</th>
              <th>Size</th>
            </tr>
          </thead>
          <tbody>
            {status?.jobs.map((j) => (
              <tr key={j.id}>
                <td>{j.source_path.split("/").pop()}</td>
                <td>{j.mode}</td>
                <td><span className={`badge ${j.status}`}>{j.status}</span></td>
                <td>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${Number(j.progress || 0)}%` }} />
                  </div>
                </td>
                <td>
                  {formatBytes(j.initial_size)}
                  {j.final_size ? ` → ${formatBytes(j.final_size)}` : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
