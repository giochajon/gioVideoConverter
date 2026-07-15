import { useEffect, useState } from "react";
import { api, SettingsResponse } from "../api";

export default function Settings() {
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [presets, setPresets] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getSettings().then(setSettings);
    api.presets().then(setPresets);
  }, []);

  async function savePreset(preset: string) {
    const updated = await api.putSettings({ preset });
    setSettings(updated);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  async function saveBatchWindow(field: "batch_start_time" | "batch_stop_time", value: string) {
    const updated = await api.putSettings({ [field]: value });
    setSettings(updated);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  if (!settings) return <p>Loading...</p>;

  return (
    <div>
      <h1>Settings</h1>

      <div className="panel">
        <label htmlFor="preset">HandBrake Preset</label>
        <select
          id="preset"
          value={settings.preset}
          onChange={(e) => savePreset(e.target.value)}
        >
          {!presets.includes(settings.preset) && (
            <option value={settings.preset}>{settings.preset}</option>
          )}
          {presets.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        {saved && <p style={{ color: "#16a34a" }}>Saved.</p>}
      </div>

      <div className="panel">
        <h2>Batch Window</h2>
        <p style={{ color: "#9aa4b2", fontSize: "0.85rem" }}>
          Nightly batch processing runs between these times (server's local time zone).
        </p>
        <div className="radio-group">
          <div>
            <label htmlFor="batch-start">Starts</label>
            <input
              id="batch-start"
              type="time"
              value={settings.batch_start_time}
              onChange={(e) => saveBatchWindow("batch_start_time", e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="batch-stop">Stops</label>
            <input
              id="batch-stop"
              type="time"
              value={settings.batch_stop_time}
              onChange={(e) => saveBatchWindow("batch_stop_time", e.target.value)}
            />
          </div>
        </div>
        {saved && <p style={{ color: "#16a34a" }}>Saved.</p>}
      </div>

      <div className="panel">
        <h2>Configured Folders</h2>
        <p style={{ color: "#9aa4b2", fontSize: "0.85rem" }}>
          Set via the stack's .env file — not editable here.
        </p>
        <table>
          <tbody>
            <tr><th>Movies</th><td>{settings.movie_dir}</td></tr>
            <tr><th>Series</th><td>{settings.series_dir}</td></tr>
            <tr><th>Interactive</th><td>{settings.interactive_dir}</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
