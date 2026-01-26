import React, { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost, apiPut } from "./api.js";

function isoToday() {
  return new Date().toISOString().slice(0, 10);
}

function mondayOfThisWeek(d = new Date()) {
  const day = d.getDay(); // 0..6 (Sun..Sat)
  const diff = (day === 0 ? -6 : 1) - day;
  const monday = new Date(d);
  monday.setDate(d.getDate() + diff);
  return monday.toISOString().slice(0, 10);
}

function sundayOfThisWeek(d = new Date()) {
  const monday = new Date(mondayOfThisWeek(d));
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  return sunday.toISOString().slice(0, 10);
}

export default function App() {
  const [weekStart, setWeekStart] = useState(mondayOfThisWeek());
  const [weekEnd, setWeekEnd] = useState(sundayOfThisWeek());
  const [lookback, setLookback] = useState(14);
  const [confluenceIds, setConfluenceIds] = useState("");

  const [drafts, setDrafts] = useState([]);
  const [activeKind, setActiveKind] = useState("progress");
  const [activeDraftId, setActiveDraftId] = useState(null);
  const [activeTitle, setActiveTitle] = useState("");
  const [activeContent, setActiveContent] = useState("");

  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const confluencePageIds = useMemo(() => {
    const parts = confluenceIds
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    return parts.length ? parts : undefined;
  }, [confluenceIds]);

  async function refreshHistory() {
    const list = await apiGet("/weekly-drafts");
    setHistory(list);
  }

  useEffect(() => {
    refreshHistory().catch(() => {});
  }, []);

  function loadDraft(kind, fromDrafts = drafts) {
    const d = fromDrafts.find((x) => x.kind === kind);
    setActiveKind(kind);
    setActiveDraftId(d?.saved_id ?? null);
    setActiveTitle(d?.title ?? "");
    setActiveContent(d?.content_markdown ?? "");
  }

  async function generate() {
    setBusy(true);
    setError("");
    try {
      const res = await apiPost("/weekly-drafts/generate", {
        week_start: weekStart,
        week_end: weekEnd,
        jira_days_lookback: Number(lookback),
        confluence_page_ids: confluencePageIds,
        save_to_db: true,
        save_to_files: false
      });

      setDrafts(res.drafts);
      loadDraft("progress", res.drafts);
      await refreshHistory();
    } catch (e) {
      setError(String(e?.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  async function saveEdits() {
    if (!activeDraftId) {
      setError("This draft was not saved to DB yet (no draft id). Generate again with save_to_db enabled.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const updated = await apiPut(`/weekly-drafts/${activeDraftId}`, {
        title: activeTitle,
        content_markdown: activeContent
      });
      setActiveTitle(updated.title);
      setActiveContent(updated.content_markdown);
      await refreshHistory();
    } catch (e) {
      setError(String(e?.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  async function loadFromHistory(id) {
    setBusy(true);
    setError("");
    try {
      const d = await apiGet(`/weekly-drafts/${id}`);
      setDrafts([{ kind: d.kind, title: d.title, content_markdown: d.content_markdown, saved_id: d.id }]);
      setActiveKind(d.kind);
      setActiveDraftId(d.id);
      setActiveTitle(d.title);
      setActiveContent(d.content_markdown);
    } catch (e) {
      setError(String(e?.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container">
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Weekly Progress + Manager Review</h2>
        <div className="muted">
          Generates copy/paste-ready markdown drafts from Jira activity (optional Confluence context). Backend:{" "}
          <code>http://localhost:8000</code>
        </div>

        <div style={{ height: 12 }} />

        <div className="row">
          <div style={{ gridColumn: "span 2" }}>
            <label>Week start</label>
            <input type="date" value={weekStart} onChange={(e) => setWeekStart(e.target.value)} />
          </div>
          <div style={{ gridColumn: "span 2" }}>
            <label>Week end</label>
            <input type="date" value={weekEnd} onChange={(e) => setWeekEnd(e.target.value)} />
          </div>
          <div style={{ gridColumn: "span 1" }}>
            <label>Jira lookback (days)</label>
            <input type="number" min="1" max="90" value={lookback} onChange={(e) => setLookback(e.target.value)} />
          </div>
          <div style={{ gridColumn: "span 1", alignSelf: "end" }}>
            <button disabled={busy} onClick={generate}>
              {busy ? "Working…" : "Generate drafts"}
            </button>
          </div>

          <div style={{ gridColumn: "span 6" }}>
            <label>Optional Confluence page IDs (comma separated)</label>
            <input
              placeholder="123456, 789012"
              value={confluenceIds}
              onChange={(e) => setConfluenceIds(e.target.value)}
            />
          </div>
        </div>

        {error ? (
          <div style={{ marginTop: 12 }} className="error">
            {error}
          </div>
        ) : null}

        <div className="tabs">
          <div className={`tab ${activeKind === "progress" ? "active" : ""}`} onClick={() => loadDraft("progress")}>
            Progress
          </div>
          <div
            className={`tab ${activeKind === "manager_review" ? "active" : ""}`}
            onClick={() => loadDraft("manager_review")}
          >
            Manager review
          </div>
          <div style={{ flex: 1 }} />
          <button className="secondary" disabled={busy} onClick={saveEdits}>
            Save edits
          </button>
        </div>

        <div className="row">
          <div style={{ gridColumn: "span 6" }}>
            <label>Title</label>
            <input value={activeTitle} onChange={(e) => setActiveTitle(e.target.value)} />
          </div>
          <div style={{ gridColumn: "span 6" }}>
            <label>Markdown (copy/paste into Confluence)</label>
            <textarea value={activeContent} onChange={(e) => setActiveContent(e.target.value)} />
          </div>
        </div>
      </div>

      <div style={{ height: 16 }} />

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Saved drafts</h3>
        <div className="muted">Click to load a saved draft from SQLite.</div>
        <div style={{ height: 10 }} />
        {history.length ? (
          <div style={{ display: "grid", gap: 8 }}>
            {history.slice(0, 20).map((h) => (
              <button
                key={h.id}
                className="secondary"
                onClick={() => loadFromHistory(h.id)}
                disabled={busy}
                style={{ textAlign: "left" }}
              >
                <div style={{ fontWeight: 600 }}>{h.title}</div>
                <div className="muted">
                  {h.kind} · {h.week_start} → {h.week_end} · id: {h.id}
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="muted" style={{ marginTop: 8 }}>
            No drafts yet. Generate one.
          </div>
        )}
      </div>
    </div>
  );
}

