import { useState, useEffect, useRef, useCallback } from "react";
import {
  CheckCircle2,
  AlertCircle,
  Loader,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import { API_BASE, apiFetch } from "../api";
import { SCRAPER_URL_HINTS } from "../collectors";

const ACTIVE_JOB_KEY = "heal_active_job_tag";
const HISTORY_KEY = "heal_job_history";
const POLL_MS = 3000;

const URL_HINTS = SCRAPER_URL_HINTS;

const STEP_LABELS = {
  queued: "Queued",
  diagnosing: "Scraping to measure health",
  triggering: "Triggering heal",
  waiting_for_proposal: "AI analyzing scraper",
  code_fixer: "AI rewriting selectors",
  control_preview_runner: "Testing on live page",
  planner: "Planning the fix",
  user_approval: "Review AI diff",
  save_to_production: "Save to production",
  step_advance: "Advancing pipeline",
  approving: "Applying accepted fix",
  applying_fix: "Applying fix",
  rescraping: "Re-scraping same collector",
  done: "Complete",
  failed: "Failed",
};

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveHistory(history) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, 10)));
}

export default function HealDashboard() {
  const [formData, setFormData] = useState({
    scraper_name: "",
    issue_description:
      "Re-capture title and main content from the current page markup. Keep the same output field names.",
    test_url: "",
    job_tag: "",
  });
  const [scraperNames, setScraperNames] = useState([]);

  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [jobHistory, setJobHistory] = useState(loadHistory);
  const [diagnosing, setDiagnosing] = useState(false);
  const [rescrapeAfter, setRescrapeAfter] = useState(true);
  const [autoApprove, setAutoApprove] = useState(false);
  const [updateSchema, setUpdateSchema] = useState(true);
  const [collectorVersions, setCollectorVersions] = useState(null);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [urlHints, setUrlHints] = useState(URL_HINTS);
  const [batchRunning, setBatchRunning] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const pollRef = useRef(null);

  const isHealing =
    (result?.status === "healing" || diagnosing) && !cancelling;
  const needsReview = result?.status === "awaiting_review";
  const needsPublish = result?.status === "draft_ready";

  const upsertHistory = useCallback((job) => {
    setJobHistory((prev) => {
      const next = [job, ...prev.filter((j) => j.job_tag !== job.job_tag)].slice(0, 10);
      saveHistory(next);
      return next;
    });
  }, []);

  const fetchJobStatus = useCallback(async (jobTag) => {
    const res = await apiFetch(`/heal/${jobTag}`);
    if (!res.ok) {
      if (res.status === 404) {
        localStorage.removeItem(ACTIVE_JOB_KEY);
        return null;
      }
      throw new Error(`Server returned ${res.status}`);
    }
    return res.json();
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const startPolling = useCallback(
    (jobTag) => {
      stopPolling();
      localStorage.setItem(ACTIVE_JOB_KEY, jobTag);

      pollRef.current = setInterval(async () => {
        try {
          const data = await fetchJobStatus(jobTag);
          if (!data) {
            stopPolling();
            localStorage.removeItem(ACTIVE_JOB_KEY);
            setResult((prev) =>
              prev?.status === "healing"
                ? { ...prev, status: "failed", step: "failed", message: "Heal job lost after server restart." }
                : prev,
            );
            return;
          }
          setResult(data);
          setError(null);
          if (data.status !== "healing") {
            stopPolling();
            localStorage.removeItem(ACTIVE_JOB_KEY);
            upsertHistory(data);
          }
        } catch (err) {
          stopPolling();
          setError(err.message);
        }
      }, POLL_MS);
    },
    [fetchJobStatus, stopPolling, upsertHistory],
  );

  const resumeActiveJob = useCallback(async () => {
    const jobTag = localStorage.getItem(ACTIVE_JOB_KEY);
    if (!jobTag) return;

    try {
      const data = await fetchJobStatus(jobTag);
      if (!data) {
        setResult(null);
        setError(null);
        return;
      }
      setResult(data);
      setError(null);
      if (data.status === "healing") {
        startPolling(jobTag);
      } else {
        localStorage.removeItem(ACTIVE_JOB_KEY);
        upsertHistory(data);
      }
    } catch (err) {
      setError(err.message);
    }
  }, [fetchJobStatus, startPolling, upsertHistory]);

  useEffect(() => {
    apiFetch("/knowledge")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.scraper_names?.length) setScraperNames(data.scraper_names);
        if (data?.sources?.length) {
          const hints = { ...URL_HINTS };
          for (const s of data.sources) {
            if (s.scraper_name && s.example_url) hints[s.scraper_name] = s.example_url;
          }
          setUrlHints(hints);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    resumeActiveJob();
    return stopPolling;
  }, [resumeActiveJob, stopPolling]);

  useEffect(() => {
    const name = formData.scraper_name.trim();
    if (!name) {
      setCollectorVersions(null);
      return;
    }
    apiFetch(`/heal/collectors/${encodeURIComponent(name)}/versions`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setCollectorVersions(data))
      .catch(() => setCollectorVersions(null));
  }, [formData.scraper_name]);

  async function handleReview(approve, saveToProduction = false) {
    const jobTag = result?.job_tag;
    if (!jobTag || reviewBusy) return;
    setReviewBusy(true);
    setError(null);
    try {
      const res = await apiFetch(`/heal/${jobTag}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approve, save_to_production: saveToProduction }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Server returned ${res.status}`);
      setResult(data);
      if (data.status === "healing") startPolling(jobTag);
      else upsertHistory(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setReviewBusy(false);
    }
  }

  async function handleSaveProduction() {
    const jobTag = result?.job_tag;
    if (!jobTag || reviewBusy) return;
    setReviewBusy(true);
    setError(null);
    try {
      const res = await apiFetch(`/heal/${jobTag}/save-production`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ update_schema: updateSchema }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Server returned ${res.status}`);
      setResult(data);
      if (data.status === "healing") startPolling(jobTag);
      else upsertHistory(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setReviewBusy(false);
    }
  }

  async function handleDiagnose(e) {
    e.preventDefault();
    setError(null);
    setDiagnosing(true);

    const jobTag =
      formData.job_tag.trim() || `${formData.scraper_name}_heal_${Date.now()}`;
    try {
      const res = await apiFetch("/heal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scraper_name: formData.scraper_name,
          issue_description: "",
          test_url: formData.test_url,
          job_tag: jobTag,
          force_heal: false,
          rescrape_after: rescrapeAfter,
          auto_approve: autoApprove,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Server returned ${res.status}`);
      }
      const data = await res.json();
      setFormData((prev) => ({ ...prev, job_tag: jobTag }));
      setResult(data);
      startPolling(jobTag);
    } catch (err) {
      setError(err.message);
    } finally {
      setDiagnosing(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    const jobTag =
      formData.job_tag.trim() || `${formData.scraper_name}_heal_${Date.now()}`;
    const payload = {
      ...formData,
      job_tag: jobTag,
      force_heal: true,
      rescrape_after: rescrapeAfter,
      auto_approve: autoApprove,
    };

    try {
      const res = await apiFetch("/heal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Server returned ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
      setFormData((prev) => ({ ...prev, job_tag: jobTag }));
      startPolling(jobTag);
    } catch (err) {
      setError(err.message);
    }
  }

  function handleChange(e) {
    const { name, value } = e.target;
    if (name === "scraper_name") {
      setFormData((prev) => ({
        ...prev,
        scraper_name: value,
        test_url: prev.test_url.trim() ? prev.test_url : (urlHints[value] || prev.test_url),
      }));
      return;
    }
    setFormData((prev) => ({ ...prev, [name]: value }));
  }

  async function handleBatchHeal() {
    if (!window.confirm("Queue authentic heal for all 13 collectors? Runs one at a time (~minutes each).")) {
      return;
    }
    setError(null);
    setBatchRunning(true);
    try {
      const res = await apiFetch("/heal/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force_heal: true, rescrape_after: true }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Server returned ${res.status}`);
      setError(null);
      setResult({
        status: "completed",
        job_tag: "batch",
        before: { empty_title_pct: 0, empty_body_pct: 0, success_rate: 0 },
        after: null,
        improved: false,
        message: data.message || `Batch queued: ${data.count} collectors.`,
        before_source: "placeholder",
        after_source: "none",
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setBatchRunning(false);
    }
  }

  function MetricCard({
    label,
    before,
    after,
    unit = "%",
    higherIsBetter = false,
    afterMissing = false,
    trustDelta = true,
  }) {
    if (afterMissing || after == null || Number.isNaN(after)) {
      return (
        <div className="metric-card">
          <div className="metric-label">{label}</div>
          <div className="metric-values">
            <div className="metric-value">
              <span className="metric-title">Before</span>
              <span className="metric-number">
                {before.toFixed(1)}
                {unit}
              </span>
            </div>
            <div className="metric-arrow neutral">→</div>
            <div className="metric-value">
              <span className="metric-title">After</span>
              <span className="metric-number">n/a</span>
            </div>
          </div>
          <div className="metric-change">Not measured yet</div>
        </div>
      );
    }
    const unchanged = Math.abs(before - after) < 0.05;
    const improved =
      trustDelta && !unchanged && (higherIsBetter ? after > before : after < before);
    const worsened =
      trustDelta && !unchanged && !improved;
    const change = Math.abs(before - after);
    return (
      <div className="metric-card">
        <div className="metric-label">{label}</div>
        <div className="metric-values">
          <div className="metric-value">
            <span className="metric-title">Before</span>
            <span className="metric-number">
              {before.toFixed(1)}
              {unit}
            </span>
          </div>
          <div className={`metric-arrow ${improved ? "positive" : "neutral"}`}>
            {!trustDelta || unchanged
              ? "→"
              : higherIsBetter
                ? (improved ? <TrendingUp size={20} /> : <TrendingDown size={20} />)
                : (improved ? <TrendingDown size={20} /> : <TrendingUp size={20} />)}
          </div>
          <div className="metric-value">
            <span className="metric-title">After</span>
            <span className="metric-number">
              {after.toFixed(1)}
              {unit}
            </span>
          </div>
        </div>
        {!trustDelta && (
          <div className="metric-change">Before unmeasured — delta not scored</div>
        )}
        {trustDelta && improved && (
          <div className="metric-change">
            {higherIsBetter ? "↑" : "↓"} {change.toFixed(1)}
            {unit} improvement
          </div>
        )}
        {trustDelta && unchanged && <div className="metric-change">No change</div>}
        {trustDelta && worsened && (
          <div className="metric-change">
            {higherIsBetter ? "↓" : "↑"} {change.toFixed(1)}
            {unit} worse
          </div>
        )}
      </div>
    );
  }

  async function handleCancel() {
    const jobTag = result?.job_tag;
    if (!jobTag || cancelling) return;
    setCancelling(true);
    stopPolling();
    localStorage.removeItem(ACTIVE_JOB_KEY);
    try {
      const res = await apiFetch(`/heal/${jobTag}/cancel`, { method: "POST" });
      const data = res.ok ? await res.json() : null;
      setResult(
        data || {
          status: "failed",
          job_tag: jobTag,
          step: "failed",
          message: "Heal cancelled. Job was already gone on the server.",
          improved: false,
        },
      );
      setError(null);
    } catch (err) {
      setResult({
        status: "failed",
        job_tag: jobTag,
        step: "failed",
        message: `Heal stopped locally (${err.message}).`,
        improved: false,
      });
    } finally {
      setCancelling(false);
    }
  }

  return (
    <div className="heal-dashboard">
      <header className="heal-header">
        <div>
          <div className="eyebrow mono">Auto-Healing</div>
          <h1 className="mono">Scraper Self-Heal Lab</h1>
          <p className="heal-subtitle">
            Diagnose scrape → review AI diff (like Scraper Studio) → accept to draft →
            save to production → live re-scrape for before/after metrics.
          </p>
        </div>
      </header>

      {isHealing && (
        <div className="heal-banner mono">
          <Loader size={14} className="spin" />
          Healing in progress on the server — you can visit Console or refresh this page anytime.
        </div>
      )}

      <div className="heal-grid">
        {/* Form Section */}
        <div className="heal-form-section">
          <div className="section-title mono">Create Healing Job</div>
          <form onSubmit={handleSubmit} className="heal-form">
            <div className="form-group">
              <label className="form-label mono">Scraper Name</label>
              <input
                type="text"
                name="scraper_name"
                list="scraper-names"
                value={formData.scraper_name}
                onChange={handleChange}
                placeholder="Any key from BRIGHTDATA_SCRAPERS — e.g. tiangolo, mdn_web, wikipedia_ai"
                className="form-input"
                required
              />
              <datalist id="scraper-names">
                {scraperNames.map((name) => (
                  <option key={name} value={name} />
                ))}
              </datalist>
            </div>

            <div className="form-group">
              <label className="form-label mono">Issue Description</label>
              <textarea
                name="issue_description"
                value={formData.issue_description}
                onChange={handleChange}
                placeholder="Describe what's broken and what to fix..."
                rows="4"
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label className="form-label mono">Test URL</label>
              <input
                type="text"
                name="test_url"
                value={formData.test_url}
                onChange={handleChange}
                placeholder="https://example.com"
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label className="form-label mono">Job Tag</label>
              <input
                type="text"
                name="job_tag"
                value={formData.job_tag}
                onChange={handleChange}
                placeholder="e.g. openai_heal_demo_1 (auto-generated if empty)"
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label className="form-label mono checkbox-row">
                <input
                  type="checkbox"
                  checked={rescrapeAfter}
                  onChange={(e) => setRescrapeAfter(e.target.checked)}
                  disabled={isHealing}
                />
                Re-scrape after heal (recommended — authentic live after-metrics)
              </label>
            </div>

            <div className="form-group">
              <label className="form-label mono checkbox-row">
                <input
                  type="checkbox"
                  checked={autoApprove}
                  onChange={(e) => setAutoApprove(e.target.checked)}
                  disabled={isHealing}
                />
                Auto-approve (skip manual diff review — like CLI --auto-approve)
              </label>
            </div>

            {collectorVersions && (
              <div className="versions-panel">
                <div className="form-label mono">Collector & versions</div>
                <div className="versions-meta mono">
                  <a href={collectorVersions.collector_url} target="_blank" rel="noreferrer">
                    Open in Bright Data
                  </a>
                  {" · "}
                  <a href={collectorVersions.versions_url} target="_blank" rel="noreferrer">
                    Versions / rollback
                  </a>
                </div>
                {collectorVersions.recent_jobs?.length > 0 && (
                  <div className="versions-jobs mono">
                    Recent runs: {collectorVersions.recent_jobs.slice(0, 3).map((j) => j.job_id).join(", ")}
                  </div>
                )}
              </div>
            )}

            <button type="button" disabled={isHealing} className="heal-btn" onClick={handleDiagnose}>
              {diagnosing ? (
                <>
                  <Loader size={16} className="spin" />
                  Diagnosing collector...
                </>
              ) : (
                "Diagnose & auto-heal →"
              )}
            </button>

            <button type="submit" disabled={isHealing} className="heal-btn secondary">
              {isHealing && !diagnosing ? (
                <>
                  <Loader size={16} className="spin" />
                  Healing on server...
                </>
              ) : (
                "Force heal (diagnose + always run BD AI)"
              )}
            </button>

            <button
              type="button"
              disabled={isHealing || batchRunning}
              className="heal-btn secondary"
              onClick={handleBatchHeal}
            >
              {batchRunning ? "Queuing batch…" : "Heal all 13 collectors (batch)"}
            </button>

            {(isHealing || cancelling) && result?.job_tag && (
              <button
                type="button"
                className="cancel-heal-btn mono"
                disabled={cancelling}
                onClick={handleCancel}
              >
                {cancelling ? "Stopping…" : "Cancel heal"}
              </button>
            )}
          </form>
        </div>

        {/* Results Section */}
        <div className="heal-results-section">
          {error && (
            <div className="alert alert-error">
              <AlertCircle size={18} />
              <div>
                <div className="alert-title">Healing Failed</div>
                <div className="alert-message">{error}</div>
                <div className="alert-hint">
                  Make sure backend is running at {API_BASE}
                </div>
              </div>
            </div>
          )}

          {result && (
            <div className={`heal-result ${result.status}`}>
              <div className="result-header">
                {result.status === "completed" ? (
                  <>
                    <CheckCircle2 size={24} className="status-icon success" />
                    <div>
                      <div className="result-status">Healing Complete</div>
                      <div className="result-job-tag mono">
                        {result.job_tag}
                      </div>
                    </div>
                  </>
                ) : result.status === "awaiting_review" ? (
                  <>
                    <AlertCircle size={24} className="status-icon healing" />
                    <div>
                      <div className="result-status">Review required</div>
                      <div className="result-job-tag mono">{result.job_tag}</div>
                    </div>
                  </>
                ) : result.status === "draft_ready" ? (
                  <>
                    <CheckCircle2 size={24} className="status-icon healing" />
                    <div>
                      <div className="result-status">Draft ready — publish when satisfied</div>
                      <div className="result-job-tag mono">{result.job_tag}</div>
                    </div>
                  </>
                ) : result.status === "failed" ? (
                  <>
                    <AlertCircle size={24} className="status-icon failed" />
                    <div>
                      <div className="result-status">Healing Failed</div>
                      <div className="result-job-tag mono">
                        {result.job_tag}
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    <Loader size={24} className="status-icon healing spin" />
                    <div>
                      <div className="result-status">Healing in Progress</div>
                      <div className="result-job-tag mono">
                        {result.job_tag}
                      </div>
                    </div>
                  </>
                )}
              </div>

              {result.status === "healing" && result.step && (
                <div className="step-pipeline">
                  <div className="step-label mono">
                    Step: {STEP_LABELS[result.step] || result.step}
                  </div>
                  <div className="step-bar">
                    <div className="step-bar-fill" />
                  </div>
                </div>
              )}

              {(needsReview || needsPublish) && (
                <div className="review-panel">
                  <div className="review-title mono">
                    {needsReview ? "Review AI proposal" : "Save to production"}
                  </div>
                  {result.proposal?.schema_changes?.has_changes && (
                    <div className="schema-alert">
                      <div className="mono">Schema update required</div>
                      {result.proposal.schema_changes.added_fields?.length > 0 && (
                        <div>Added: {result.proposal.schema_changes.added_fields.join(", ")}</div>
                      )}
                      {result.proposal.schema_changes.removed_fields?.length > 0 && (
                        <div>Removed: {result.proposal.schema_changes.removed_fields.join(", ")}</div>
                      )}
                    </div>
                  )}
                  {result.proposal?.diff && (
                    <details className="diff-block">
                      <summary className="mono">Code diff</summary>
                      <pre>{JSON.stringify(result.proposal.diff, null, 2)}</pre>
                    </details>
                  )}
                  {result.proposal?.preview?.length > 0 && (
                    <details className="diff-block" open>
                      <summary className="mono">Extraction preview</summary>
                      <pre>{JSON.stringify(result.proposal.preview, null, 2)}</pre>
                    </details>
                  )}
                  {needsReview && (
                    <div className="review-actions">
                      <button
                        type="button"
                        className="heal-btn secondary"
                        disabled={reviewBusy}
                        onClick={() => handleReview(false)}
                      >
                        Decline
                      </button>
                      <button
                        type="button"
                        className="heal-btn secondary"
                        disabled={reviewBusy}
                        onClick={() => handleReview(true, false)}
                      >
                        Accept to draft
                      </button>
                      <button
                        type="button"
                        className="heal-btn"
                        disabled={reviewBusy}
                        onClick={() => handleReview(true, true)}
                      >
                        Accept & save to production
                      </button>
                    </div>
                  )}
                  {needsPublish && (
                    <div className="review-actions">
                      <label className="form-label mono checkbox-row">
                        <input
                          type="checkbox"
                          checked={updateSchema}
                          onChange={(e) => setUpdateSchema(e.target.checked)}
                        />
                        Update output schema (Bright Data docs step)
                      </label>
                      <button
                        type="button"
                        className="heal-btn"
                        disabled={reviewBusy}
                        onClick={handleSaveProduction}
                      >
                        Save to production
                      </button>
                      {result.collector_url && (
                        <a
                          className="mono dashboard-link"
                          href={result.collector_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Or finish in Bright Data IDE →
                        </a>
                      )}
                    </div>
                  )}
                </div>
              )}

              {result.status === "awaiting_review" && result.step && (
                <div className="step-pipeline">
                  <div className="step-label mono">
                    Step: {STEP_LABELS[result.step] || result.step}
                  </div>
                </div>
              )}

              {result.status === "draft_ready" && result.step && (
                <div className="step-pipeline">
                  <div className="step-label mono">
                    Step: {STEP_LABELS[result.step] || result.step}
                  </div>
                </div>
              )}

              {result.before && (
                <div className="metrics-grid">
                  <MetricCard
                    label="Empty Title %"
                    before={result.before.empty_title_pct}
                    after={result.after?.empty_title_pct}
                    afterMissing={!result.after}
                    trustDelta={
                      result.before_source !== "placeholder" &&
                      result.after_source !== "unchanged" &&
                      result.after_source !== "none"
                    }
                  />
                  <MetricCard
                    label="Empty Body %"
                    before={result.before.empty_body_pct}
                    after={result.after?.empty_body_pct}
                    afterMissing={!result.after}
                    trustDelta={
                      result.before_source !== "placeholder" &&
                      result.after_source !== "unchanged" &&
                      result.after_source !== "none"
                    }
                  />
                  <MetricCard
                    label="Success Rate %"
                    before={result.before.success_rate}
                    after={result.after?.success_rate}
                    afterMissing={!result.after}
                    higherIsBetter
                    trustDelta={
                      result.before_source !== "placeholder" &&
                      result.after_source !== "unchanged" &&
                      result.after_source !== "none"
                    }
                  />
                </div>
              )}

              {(result.before_source || result.after_source) && (
                <div className="result-message mono" style={{ opacity: 0.7, fontSize: "0.75rem" }}>
                  before: {result.before_source || "?"} · after: {result.after_source || "not measured"}
                </div>
              )}

              <div className="result-footer">
                {result.status === "completed" && (
                  <div
                    className={`improvement-badge ${
                      result.improved ||
                      (result.after_source === "preview" &&
                        result.before_source === "placeholder" &&
                        !/failed|left unchanged|unchanged/i.test(result.message || ""))
                        ? "improved"
                        : "unchanged"
                    }`}
                  >
                    {result.improved
                      ? "✓ Metrics Improved"
                      : result.after_source === "skipped_healthy"
                        ? "→ Already healthy — heal skipped"
                        : result.after_source === "unchanged"
                          ? "→ Heal aborted; collector unchanged"
                          : result.after_source === "preview" &&
                          result.before_source === "placeholder" &&
                          !/failed|left unchanged|unchanged/i.test(result.message || "")
                        ? "✓ Heal saved on Bright Data (preview after; before unmeasured)"
                            : result.after_source === "preview"
                              ? "✓ Heal finished — after from Bright Data preview"
                              : result.after
                                ? "→ Heal finished; metrics did not improve"
                                : "→ Heal finished; after-metrics not measured"}
                  </div>
                )}
                <div className="result-message">{result.message}</div>
              </div>
            </div>
          )}

          {diagnosing && !result && (
            <div className={`heal-result healing`}>
              <div className="result-header">
                <Loader size={24} className="status-icon healing spin" />
                <div>
                  <div className="result-status">Diagnosing collector</div>
                  <div className="result-job-tag mono">Scraping to measure extraction health…</div>
                </div>
              </div>
              <div className="step-pipeline">
                <div className="step-label mono">Step: Scraping to measure health</div>
                <div className="step-bar">
                  <div className="step-bar-fill" />
                </div>
              </div>
              <div className="result-footer">
                <div className="result-message">
                  This can take a minute. The empty-state panel is hidden while the job runs.
                </div>
              </div>
            </div>
          )}

          {!result && !error && !diagnosing && (
            <div className="empty-state">
              <div className="empty-icon spin-slow">⚙️</div>
              <div className="empty-title">No healing job yet</div>
              <div className="empty-subtitle">
                Fill scraper name + test URL, then Diagnose & auto-heal. That
                scrapes, heals only if extraction is unhealthy, and re-scrapes.
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Job History */}
      {jobHistory.length > 0 && (
        <div className="job-history">
          <div className="section-title mono">Recent Jobs</div>
          <div className="job-list">
            {jobHistory.map((job) => (
              <button
                type="button"
                key={job.job_tag}
                className="job-item job-item-btn"
                onClick={() => {
                  setResult(job);
                  if (job.status === "healing") startPolling(job.job_tag);
                }}
              >
                <div className="job-tag mono">{job.job_tag}</div>
                <div className="job-scraper">{job.scraper_name || job.job_tag.split("_")[0]}</div>
                <div className={`job-status ${job.status}`}>
                  {job.status === "completed"
                    ? "Complete"
                    : job.status === "awaiting_review"
                      ? "Review"
                      : job.status === "draft_ready"
                        ? "Draft"
                    : job.status === "failed"
                      ? "Failed"
                      : "Healing"}
                </div>
                {job.improved && <div className="job-badge">✓ Improved</div>}
              </button>
            ))}
          </div>
        </div>
      )}

      <style>{`
        .heal-dashboard {
          width: 100%;
          max-width: 1400px;
          margin: 0 auto;
          padding: 40px 20px 80px;
        }

        .heal-header {
          margin-bottom: 48px;
        }

        .heal-header h1 {
          font-size: clamp(28px, 5vw, 42px);
          margin-bottom: 12px;
          letter-spacing: -0.01em;
        }

        .heal-subtitle {
          color: var(--text-dim);
          font-size: 15px;
          margin-top: 8px;
        }

        .heal-banner {
          display: flex;
          align-items: center;
          gap: 10px;
          background: rgba(251, 191, 36, 0.08);
          border: 1px solid rgba(251, 191, 36, 0.3);
          color: #FBBF24;
          padding: 12px 16px;
          border-radius: 8px;
          font-size: 12px;
          margin-bottom: 24px;
        }

        .step-pipeline {
          margin-bottom: 20px;
        }

        .step-label {
          font-size: 12px;
          color: var(--signal);
          margin-bottom: 8px;
        }

        .step-bar {
          height: 4px;
          background: var(--border);
          border-radius: 2px;
          overflow: hidden;
        }

        .step-bar-fill {
          height: 100%;
          width: 40%;
          background: var(--signal);
          border-radius: 2px;
          animation: step-pulse 1.5s ease-in-out infinite;
        }

        @keyframes step-pulse {
          0% { width: 20%; margin-left: 0; }
          50% { width: 60%; margin-left: 20%; }
          100% { width: 20%; margin-left: 80%; }
        }

        .status-icon.failed {
          color: #EF4444;
        }

        .heal-result.failed {
          border-left: 3px solid #EF4444;
        }

        .heal-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 32px;
          margin-bottom: 48px;
        }

        @media (max-width: 1024px) {
          .heal-grid {
            grid-template-columns: 1fr;
            gap: 24px;
          }
        }

        .section-title {
          font-size: 13px;
          color: var(--signal);
          letter-spacing: 0.1em;
          text-transform: uppercase;
          margin-bottom: 20px;
        }

        /* Form Styles */
        .heal-form {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .form-group {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .form-label {
          font-size: 12px;
          color: var(--text-dim);
          letter-spacing: 0.05em;
          text-transform: uppercase;
        }

        .form-input {
          background: var(--panel);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px 14px;
          font-family: 'Inter', sans-serif;
          font-size: 14px;
          color: var(--text);
          outline: none;
          transition: border-color 0.2s;
        }

        .form-input:focus {
          border-color: var(--signal);
        }

        .form-input::placeholder {
          color: #565B65;
        }

        .checkbox-row {
          display: flex;
          align-items: center;
          gap: 8px;
          text-transform: none;
          letter-spacing: 0;
          font-size: 12px;
          cursor: pointer;
        }
        .checkbox-row input {
          accent-color: var(--signal);
        }

        .heal-btn {
          background: var(--signal);
          color: #04140B;
          border: none;
          border-radius: 8px;
          padding: 14px 20px;
          font-family: 'IBM Plex Mono', monospace;
          font-weight: 600;
          font-size: 13px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          transition: background 0.2s;
          margin-top: 8px;
        }

        .heal-btn:hover:not(:disabled) {
          background: #5FFFB4;
        }

        .heal-btn:disabled {
          background: var(--signal-dim);
          cursor: not-allowed;
          opacity: 0.7;
        }

        .heal-btn.secondary {
          background: transparent;
          color: var(--signal);
          border: 1px solid var(--signal);
        }

        .heal-btn.secondary:hover:not(:disabled) {
          background: var(--signal-glow);
        }

        .cancel-heal-btn {
          background: transparent;
          border: 1px solid var(--border);
          color: var(--text-dim);
          border-radius: 8px;
          padding: 10px 16px;
          font-size: 12px;
          cursor: pointer;
          margin-top: 4px;
        }

        .cancel-heal-btn:hover {
          border-color: #EF4444;
          color: #EF4444;
        }

        .spin {
          animation: spin 1s linear infinite;
        }

        .spin-slow {
          display: inline-block;
          animation: spin 6s linear infinite;
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        /* Results Styles */
        .heal-results-section {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .alert {
          border-radius: 8px;
          padding: 16px;
          display: flex;
          gap: 12px;
        }

        .alert-error {
          background: rgba(239, 68, 68, 0.1);
          border: 1px solid #EF4444;
        }

        .alert-error .alert-icon {
          color: #EF4444;
        }

        .alert-title {
          font-weight: 600;
          color: var(--text);
          font-size: 14px;
        }

        .alert-message {
          color: var(--text-dim);
          font-size: 13px;
          margin-top: 4px;
        }

        .alert-hint {
          font-size: 12px;
          color: #999;
          margin-top: 8px;
          font-family: 'IBM Plex Mono', monospace;
        }

        .heal-result {
          background: var(--panel);
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 24px;
        }

        .heal-result.completed {
          border-left: 3px solid var(--signal);
        }

        .heal-result.healing {
          border-left: 3px solid #FBBF24;
        }

        .result-header {
          display: flex;
          align-items: center;
          gap: 16px;
          margin-bottom: 24px;
          padding-bottom: 16px;
          border-bottom: 1px solid var(--border);
        }

        .status-icon {
          flex-shrink: 0;
        }

        .status-icon.success {
          color: var(--signal);
        }

        .status-icon.healing {
          color: #FBBF24;
        }

        .result-status {
          font-weight: 600;
          font-size: 15px;
          color: var(--text);
        }

        .result-job-tag {
          font-size: 12px;
          color: var(--text-dim);
          margin-top: 4px;
        }

        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 16px;
          margin-bottom: 20px;
        }

        .metric-card {
          background: rgba(57, 255, 158, 0.05);
          border: 1px solid rgba(57, 255, 158, 0.2);
          border-radius: 8px;
          padding: 16px;
        }

        .metric-label {
          font-size: 12px;
          color: var(--text-dim);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin-bottom: 12px;
        }

        .metric-values {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          margin-bottom: 10px;
        }

        .metric-value {
          display: flex;
          flex-direction: column;
          align-items: center;
          flex: 1;
        }

        .metric-title {
          font-size: 11px;
          color: var(--text-dim);
          margin-bottom: 4px;
        }

        .metric-number {
          font-size: 18px;
          font-weight: 700;
          color: var(--signal);
        }

        .metric-arrow {
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--text-dim);
        }

        .metric-arrow.positive {
          color: var(--signal);
        }

        .metric-change {
          font-size: 12px;
          color: var(--signal);
          font-weight: 600;
        }

        .result-footer {
          display: flex;
          flex-direction: column;
          gap: 12px;
          padding-top: 16px;
          border-top: 1px solid var(--border);
        }

        .improvement-badge {
          display: inline-block;
          padding: 8px 12px;
          border-radius: 6px;
          font-size: 12px;
          font-weight: 600;
          width: fit-content;
        }

        .improvement-badge.improved {
          background: rgba(57, 255, 158, 0.15);
          color: var(--signal);
          border: 1px solid rgba(57, 255, 158, 0.3);
        }

        .improvement-badge.unchanged {
          background: rgba(255, 193, 7, 0.1);
          color: #FFC107;
          border: 1px solid rgba(255, 193, 7, 0.3);
        }

        .result-message {
          font-size: 13px;
          color: var(--text-dim);
        }

        .empty-state {
          text-align: center;
          padding: 60px 20px;
          background: var(--panel);
          border: 1px solid var(--border);
          border-radius: 12px;
        }

        .empty-icon {
          font-size: 48px;
          margin-bottom: 16px;
        }

        .empty-title {
          font-size: 16px;
          font-weight: 600;
          color: var(--text);
          margin-bottom: 8px;
        }

        .empty-subtitle {
          font-size: 14px;
          color: var(--text-dim);
        }

        /* Job History */
        .job-history {
          border-top: 1px solid var(--border);
          padding-top: 40px;
        }

        .job-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .job-item {
          display: flex;
          align-items: center;
          gap: 16px;
          padding: 12px 16px;
          background: var(--panel);
          border: 1px solid var(--border);
          border-radius: 8px;
          font-size: 13px;
        }

        .job-item-btn {
          width: 100%;
          text-align: left;
          cursor: pointer;
          color: inherit;
          transition: border-color 0.2s;
        }

        .job-item-btn:hover {
          border-color: rgba(57, 255, 158, 0.4);
        }

        .job-tag {
          flex: 1;
          color: var(--signal);
          font-weight: 600;
        }

        .job-scraper {
          color: var(--text-dim);
          font-size: 12px;
        }

        .job-status {
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
        }

        .job-status.completed {
          background: rgba(57, 255, 158, 0.15);
          color: var(--signal);
        }

        .job-status.healing {
          background: rgba(255, 193, 7, 0.1);
          color: #FFC107;
        }

        .job-status.failed {
          background: rgba(239, 68, 68, 0.1);
          color: #EF4444;
        }

        .job-badge {
          color: var(--signal);
          font-weight: 600;
          font-size: 11px;
        }

        .versions-panel {
          padding: 12px;
          border: 1px solid var(--border);
          border-radius: 8px;
          background: rgba(0, 0, 0, 0.2);
          font-size: 12px;
        }

        .versions-meta a {
          color: var(--signal);
        }

        .versions-jobs {
          margin-top: 8px;
          color: var(--text-dim);
          font-size: 11px;
        }

        .review-panel {
          margin: 16px 0;
          padding: 16px;
          border: 1px solid rgba(57, 255, 158, 0.35);
          border-radius: 8px;
          background: rgba(57, 255, 158, 0.04);
        }

        .review-title {
          font-weight: 600;
          margin-bottom: 12px;
        }

        .schema-alert {
          margin-bottom: 12px;
          padding: 10px;
          border-radius: 6px;
          background: rgba(255, 193, 7, 0.1);
          font-size: 12px;
        }

        .diff-block {
          margin-bottom: 12px;
        }

        .diff-block pre {
          max-height: 220px;
          overflow: auto;
          font-size: 11px;
          padding: 10px;
          background: rgba(0, 0, 0, 0.35);
          border-radius: 6px;
        }

        .review-actions {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
          align-items: center;
          margin-top: 12px;
        }

        .dashboard-link {
          color: var(--signal);
          font-size: 12px;
        }

        .job-status.awaiting_review,
        .job-status.draft_ready {
          background: rgba(255, 193, 7, 0.1);
          color: #ffc107;
        }
      `}</style>
    </div>
  );
}
