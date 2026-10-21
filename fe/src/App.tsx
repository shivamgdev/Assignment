import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getSubmission,
  listSubmissions,
  recordDecision,
  type Decision,
} from "./api";
import { ApiError, type SortOrder, type Submission } from "./types";
import "./App.css";

const SORT_OPTIONS: { value: SortOrder; label: string }[] = [
  { value: "priority_desc", label: "Priority: highest first" },
  { value: "submitted_desc", label: "Newest submitted" },
  { value: "submitted_asc", label: "Oldest submitted" },
  { value: "applicant_asc", label: "Applicant name Aâ€“Z" },
];

const REASON_LABELS: Record<string, string> = {
  COVERAGE_MISMATCH: "Coverage mismatch",
  MISSING_INFORMATION: "Missing information",
  DUPLICATE_RECORD: "Possible duplicate",
  INCREASE_REQUIRES_REVIEW: "Coverage increase",
};

function labelFor(value: string | null | undefined): string {
  if (!value) return "Not provided";
  if (REASON_LABELS[value]) return REASON_LABELS[value];
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function display(value: string | number | null | undefined): string {
  return value === null || value === undefined || value === ""
    ? "Not provided"
    : String(value);
}

function formatMoney(cents: number | null | undefined): string {
  if (typeof cents !== "number" || !Number.isFinite(cents)) {
    return "Not provided";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(cents / 100);
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "Not provided";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Invalid date";

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function Field({
  label,
  value,
  important = false,
}: {
  label: string;
  value: string | number | null | undefined;
  important?: boolean;
}) {
  const missing = value === null || value === undefined || value === "";

  return (
    <div className={`detail-field${missing ? " is-missing" : ""}`}>
      <span className="field-label">{label}</span>
      <span
        className={important ? "field-value important-value" : "field-value"}
      >
        {display(value)}
        {missing && <span className="missing-tag">Missing</span>}
      </span>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="detail-section">
      <h3>{title}</h3>
      <div className="field-grid">{children}</div>
    </section>
  );
}

function App() {
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState("");
  const [reason, setReason] = useState("");
  const [sort, setSort] = useState<SortOrder>("priority_desc");
  const [items, setItems] = useState<Submission[]>([]);
  const [total, setTotal] = useState(0);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState<Submission | null>(null);
  const [groups, setGroups] = useState<{ id: string; name: string }[]>([]);
  const [reasons, setReasons] = useState<string[]>([]);
  const [loadingQueue, setLoadingQueue] = useState(true);
  const [queueError, setQueueError] = useState("");
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [decisionMessage, setDecisionMessage] = useState("");
  const [decisionError, setDecisionError] = useState("");
  const [decision, setDecision] = useState<Decision | null>(null);
  const [resetting, setResetting] = useState(false);

  const queueRequestId = useRef(0);
  const detailRequestId = useRef(0);
  const decisionLock = useRef(false);
  const searchTimer = useRef<number | undefined>(undefined);

  const loadQueue = useCallback(
    async (showLoading = true) => {
      const requestId = ++queueRequestId.current;
      if (showLoading) setLoadingQueue(true);
      setQueueError("");

      try {
        const result = await listSubmissions({
          query: query.trim(),
          group,
          reason,
          sort,
        });

        if (requestId !== queueRequestId.current) return;

        setItems(result.items);
        setTotal(result.total);

        setGroups((current) => {
          const all = new Map(current.map((item) => [item.id, item]));
          result.items.forEach((item) => {
            if (item.group?.id && item.group?.name) {
              all.set(item.group.id, item.group);
            }
          });
          return [...all.values()].sort((a, b) => a.name.localeCompare(b.name));
        });

        setReasons((current) =>
          [
            ...new Set([
              ...current,
              ...result.items.map((item) => item.reviewReason).filter(Boolean),
            ]),
          ].sort(),
        );
      } catch (error) {
        if (requestId !== queueRequestId.current) return;
        setQueueError(
          error instanceof Error
            ? error.message
            : "Could not load the review queue.",
        );
      } finally {
        if (requestId === queueRequestId.current) setLoadingQueue(false);
      }
    },
    [query, group, reason, sort],
  );

  useEffect(() => {
    window.clearTimeout(searchTimer.current);
    searchTimer.current = window.setTimeout(
      () => {
        void loadQueue();
      },
      query ? 250 : 0,
    );

    return () => window.clearTimeout(searchTimer.current);
  }, [loadQueue, query]);

  const loadDetail = useCallback(async (id: string) => {
    const requestId = ++detailRequestId.current;
    setDetailLoading(true);
    setDetailError("");
    setDecisionMessage("");
    setDecisionError("");
    setNote("");
    setDecision(null);

    try {
      const result = await getSubmission(id);
      if (requestId === detailRequestId.current) setDetail(result);
    } catch (error) {
      if (requestId === detailRequestId.current) {
        setDetailError(
          error instanceof Error
            ? error.message
            : "Could not load submission details.",
        );
      }
    } finally {
      if (requestId === detailRequestId.current) setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedId) return;

    const timer = window.setTimeout(() => {
      void loadDetail(selectedId);
    }, 0);

    return () => window.clearTimeout(timer);
  }, [selectedId, loadDetail]);

  const selectedInQueue = useMemo(
    () => items.find((item) => item.id === selectedId),
    [items, selectedId],
  );

  const chooseSubmission = (item: Submission) => {
    if (saving) return;
    setSelectedId(item.id);
  };

  const handleDecision = async (choice: Decision) => {
    if (!selectedId || saving || decisionLock.current) return;

    if (choice === "RETURN" && !note.trim()) {
      setDecisionError("Add a note explaining what needs correction.");
      return;
    }

    decisionLock.current = true;
    setSaving(true);
    setDecision(choice);
    setDecisionError("");
    setDecisionMessage(
      choice === "APPROVE"
        ? "Approving submissionâ€¦"
        : "Returning submissionâ€¦",
    );

    try {
      const updated = await recordDecision(selectedId, choice, note.trim());
      setDetail(updated);
      setDecisionMessage(
        choice === "APPROVE"
          ? "Submission approved successfully."
          : "Submission returned for correction successfully.",
      );
      setNote("");
      await loadQueue(false);
    } catch (error) {
      if (error instanceof ApiError && error.submission) {
        setDetail(error.submission);
        setDecisionError(
          error.status === 409
            ? "This submission was already decided by another reviewer. The latest status is shown below."
            : error.message,
        );
        await loadQueue(false);
      } else {
        setDecisionError(
          error instanceof Error
            ? error.message
            : "Decision failed. Please try again.",
        );
      }
      setDecisionMessage("");
    } finally {
      decisionLock.current = false;
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (resetting || saving) return;
    const confirmed = window.confirm(
      "Reset the mock API to its original review data? This will undo mock decisions.",
    );
    if (!confirmed) return;

    setResetting(true);
    setQueueError("");
    setDecisionMessage("");
    setDecisionError("");

    try {
      const response = await fetch("/api/reset", { method: "POST" });
      if (!response.ok) throw new Error("Could not reset the mock data.");
      setQuery("");
      setGroup("");
      setReason("");
      setSort("priority_desc");
      setSelectedId("");
      setDetail(null);
      await loadQueue();
      setDecisionMessage("Mock review data has been reset.");
    } catch (error) {
      setQueueError(
        error instanceof Error
          ? error.message
          : "Could not reset the mock data.",
      );
    } finally {
      setResetting(false);
    }
  };

  const currentStatus = detail?.status ?? selectedInQueue?.status;
  const isFinal = currentStatus === "APPROVED" || currentStatus === "RETURNED";
  const signals = detail?.reviewSignals ?? [];

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">
            ER
          </div>
          <div>
            <p className="eyebrow">OPERATIONS CONSOLE</p>
            <h1>Enrollment review</h1>
          </div>
        </div>
        <div className="topbar-right">
          <span className="service-indicator">
            <span /> Review workspace
          </span>
          <button
            className="button button-quiet reset-button"
            type="button"
            onClick={() => void handleReset()}
            disabled={resetting || saving}
          >
            {resetting ? "Resettingâ€¦" : "Reset demo data"}
          </button>
        </div>
      </header>

      <section className="page-intro">
        <div>
          <p className="eyebrow">BENEFITS OPERATIONS / INTAKE</p>
          <h2>Review workbench</h2>
          <p className="intro-copy">
            Resolve enrollment exceptions with the context you need to make a
            confident decision.
          </p>
        </div>
        <div className="queue-summary" aria-live="polite">
          <span className="summary-number">{total}</span>
          <span className="summary-label">Awaiting review</span>
        </div>
      </section>

      {decisionMessage && (
        <div className="global-notice success-notice" role="status">
          <span aria-hidden="true">âœ“</span> {decisionMessage}
        </div>
      )}
      {decisionError && (
        <div className="global-notice error-notice" role="alert">
          {decisionError}
        </div>
      )}

      <div className="workspace">
        <section className="queue-panel" aria-labelledby="queue-heading">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">INBOX</p>
              <h2 id="queue-heading">Review queue</h2>
            </div>
            <span className="count-chip">{total} records</span>
          </div>

          <div className="filter-stack">
            <label className="search-control">
              <span className="sr-only">Search applicant name or email</span>
              <span aria-hidden="true" className="search-symbol">
                âŒ•
              </span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search name or emailâ€¦"
                autoComplete="off"
              />
              {query && (
                <button
                  type="button"
                  className="clear-search"
                  onClick={() => setQuery("")}
                  aria-label="Clear search"
                >
                  Ã—
                </button>
              )}
            </label>

            <div className="filter-row">
              <label>
                <span>Employer group</span>
                <select
                  value={group}
                  onChange={(event) => setGroup(event.target.value)}
                >
                  <option value="">All groups</option>
                  {groups.map((item) => (
                    <option value={item.id} key={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Review reason</span>
                <select
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                >
                  <option value="">All reasons</option>
                  {reasons.map((item) => (
                    <option value={item} key={item}>
                      {labelFor(item)}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label className="sort-control">
              <span>Sort by</span>
              <select
                value={sort}
                onChange={(event) => setSort(event.target.value as SortOrder)}
              >
                {SORT_OPTIONS.map((option) => (
                  <option value={option.value} key={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {queueError && (
            <div className="inline-error" role="alert">
              <p>{queueError}</p>
              <button
                type="button"
                className="button button-secondary"
                onClick={() => void loadQueue()}
              >
                Try again
              </button>
            </div>
          )}

          <div className="queue-list" aria-label="Submissions">
            {loadingQueue && (
              <div className="queue-loading" role="status">
                <span className="spinner" /> Loading submissionsâ€¦
              </div>
            )}

            {!loadingQueue && !queueError && items.length === 0 && (
              <div className="empty-state">
                <div className="empty-icon" aria-hidden="true">
                  âŒ•
                </div>
                <h3>No submissions found</h3>
                <p>
                  Try another search or clear your filters to see more
                  submissions.
                </p>
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() => {
                    setQuery("");
                    setGroup("");
                    setReason("");
                  }}
                >
                  Clear filters
                </button>
              </div>
            )}

            {items.map((item) => {
              const active = selectedId === item.id;
              return (
                <button
                  type="button"
                  key={item.id}
                  className={`queue-item${active ? " is-selected" : ""}`}
                  onClick={() => chooseSubmission(item)}
                  aria-pressed={active}
                  disabled={saving}
                >
                  <div className="queue-item-top">
                    <span
                      className={`priority-marker priority-${String(item.priority).toLowerCase()}`}
                    >
                      <span aria-hidden="true">â—</span>{" "}
                      {labelFor(item.priority)} priority
                    </span>
                    <span className="queue-time">
                      {formatDate(item.submittedAt)}
                    </span>
                  </div>
                  <div className="applicant-row">
                    <span className="avatar" aria-hidden="true">
                      {(item.applicant?.name || "?")
                        .trim()
                        .charAt(0)
                        .toUpperCase()}
                    </span>
                    <div className="applicant-copy">
                      <strong>{display(item.applicant?.name)}</strong>
                      <span>{display(item.applicant?.email)}</span>
                    </div>
                  </div>
                  <div className="queue-product">
                    <span>{display(item.group?.name)}</span>
                    <span className="dot-separator" aria-hidden="true">
                      Â·
                    </span>
                    <span>{display(item.product)}</span>
                  </div>
                  <div className="queue-item-bottom">
                    <span className="reason-chip">
                      {labelFor(item.reviewReason)}
                    </span>
                    <span
                      className={`status-text status-${String(item.status).toLowerCase()}`}
                    >
                      {labelFor(item.status)}
                    </span>
                  </div>
                  <div className="queue-coverage">
                    <span>Requested coverage</span>
                    <strong>{formatMoney(item.coverageAmountCents)}</strong>
                  </div>
                </button>
              );
            })}
          </div>

          <div className="queue-footer">
            <span>
              {items.length} shown Â· {total} total
            </span>
            <span>Updated from live API</span>
          </div>
        </section>

        <section className="details-panel" aria-labelledby="details-heading">
          {!selectedId && (
            <div className="details-empty">
              <div className="details-empty-art" aria-hidden="true">
                <span className="art-card art-card-back" />
                <span className="art-card art-card-front">
                  <span />
                  <span />
                  <span />
                </span>
              </div>
              <p className="eyebrow">SUBMISSION DETAILS</p>
              <h2 id="details-heading">Choose a submission</h2>
              <p>
                Select an item in the queue to inspect enrollment information,
                review signals and available actions.
              </p>
              <div className="keyboard-hint">
                <span>TIP</span> Select queue items using Tab and Enter.
              </div>
            </div>
          )}

          {selectedId && detailLoading && (
            <div className="details-loading" role="status">
              <span className="spinner" /> Loading submission detailsâ€¦
            </div>
          )}

          {selectedId && detailError && !detailLoading && (
            <div className="details-error" role="alert">
              <h2 id="details-heading">Unable to load details</h2>
              <p>{detailError}</p>
              <button
                type="button"
                className="button button-secondary"
                onClick={() => void loadDetail(selectedId)}
              >
                Retry loading
              </button>
            </div>
          )}

          {detail && !detailLoading && (
            <div className="detail-content" key={detail.id}>
              <div className="detail-header">
                <div className="detail-header-main">
                  <p className="eyebrow">SUBMISSION / {detail.id}</p>
                  <h2 id="details-heading">
                    {display(detail.applicant?.name)}
                  </h2>
                  <p className="detail-email">
                    {display(detail.applicant?.email)}
                  </p>
                </div>
                <span
                  className={`large-status status-${String(detail.status).toLowerCase()}`}
                >
                  {labelFor(detail.status)}
                </span>
              </div>

              <div className="detail-meta-grid">
                <div>
                  <span>Employer group</span>
                  <strong>{display(detail.group?.name)}</strong>
                </div>
                <div>
                  <span>Product</span>
                  <strong>{display(detail.product)}</strong>
                </div>
                <div>
                  <span>Requested coverage</span>
                  <strong>{formatMoney(detail.coverageAmountCents)}</strong>
                </div>
                <div>
                  <span>Submitted</span>
                  <strong>{formatDate(detail.submittedAt)}</strong>
                </div>
                <div>
                  <span>Effective date</span>
                  <strong>{display(detail.effectiveDate)}</strong>
                </div>
                <div>
                  <span>Review reason</span>
                  <strong>{labelFor(detail.reviewReason)}</strong>
                </div>
              </div>

              <div className="signal-block">
                <div className="section-title-row">
                  <h3>Review signals</h3>
                  <span className="count-chip">
                    {signals.length}{" "}
                    {signals.length === 1 ? "signal" : "signals"}
                  </span>
                </div>
                {signals.length === 0 ? (
                  <p className="muted-copy">
                    No review signals were supplied for this submission.
                  </p>
                ) : (
                  <div className="signal-list">
                    {signals.map((signal, index) => (
                      <article
                        className={`signal-card signal-${String(signal.severity).toLowerCase()}`}
                        key={`${signal.code}-${index}`}
                      >
                        <div className="signal-heading">
                          <span className="signal-severity">
                            {labelFor(signal.severity)} severity
                          </span>
                          <span className="signal-code">
                            {labelFor(signal.code)}
                          </span>
                        </div>
                        <p>{signal.message}</p>
                        <span className="signal-field">
                          Field: {display(signal.field)}
                        </span>
                      </article>
                    ))}
                  </div>
                )}
              </div>

              <Section title="Employee information">
                <Field
                  label="Employee ID"
                  value={detail.employee?.employeeId}
                />
                <Field
                  label="Date of birth"
                  value={detail.employee?.dateOfBirth}
                />
                <Field label="Phone" value={detail.employee?.phone} />
                <Field
                  label="Address"
                  value={
                    detail.employee?.address
                      ? [
                          detail.employee.address.line1,
                          detail.employee.address.line2,
                          detail.employee.address.city,
                          detail.employee.address.state,
                          detail.employee.address.postalCode,
                        ]
                          .filter(Boolean)
                          .join(", ") || null
                      : null
                  }
                />
              </Section>

              <Section title="Employment">
                <Field
                  label="Employment status"
                  value={detail.employment?.employmentStatus}
                />
                <Field label="Hire date" value={detail.employment?.hireDate} />
                <Field
                  label="Annual salary"
                  value={formatMoney(detail.employment?.annualSalaryCents)}
                />
                <Field
                  label="Occupation"
                  value={detail.employment?.occupation}
                />
                <Field
                  label="Hours per week"
                  value={detail.employment?.hoursPerWeek}
                />
              </Section>

              <Section title="Enrollment election">
                <Field label="Plan name" value={detail.election?.planName} />
                <Field
                  label="Requested coverage"
                  value={formatMoney(detail.election?.requestedCoverageCents)}
                  important
                />
                <Field
                  label="Beneficiaries"
                  value={detail.election?.beneficiaryCount}
                />
                <Field
                  label="Tobacco use"
                  value={
                    detail.election?.tobaccoUse === true
                      ? "Yes"
                      : detail.election?.tobaccoUse === false
                        ? "No"
                        : null
                  }
                />
              </Section>

              <Section title="Existing coverage">
                {detail.existingCoverage ? (
                  <>
                    <Field
                      label="Current coverage"
                      value={formatMoney(
                        detail.existingCoverage.coverageAmountCents,
                      )}
                    />
                    <Field
                      label="Coverage effective date"
                      value={detail.existingCoverage.effectiveDate}
                    />
                    <Field
                      label="Policy number"
                      value={detail.existingCoverage.policyNumber}
                    />
                  </>
                ) : (
                  <div className="missing-coverage">
                    <strong>No existing coverage data supplied</strong>
                    <p>
                      Confirm whether this is a new enrollment or whether prior
                      coverage details are missing.
                    </p>
                  </div>
                )}
              </Section>

              {detail.decision && (
                <Section title="Recorded decision">
                  <Field
                    label="Decision"
                    value={labelFor(detail.decision.type)}
                  />
                  <Field
                    label="Reviewed by"
                    value={detail.decision.reviewedBy}
                  />
                  <Field label="Decision note" value={detail.decision.note} />
                  <Field
                    label="Decision date"
                    value={formatDate(detail.decidedAt)}
                  />
                </Section>
              )}

              <div className="decision-panel">
                <div className="decision-panel-heading">
                  <div>
                    <p className="eyebrow">REVIEW OUTCOME</p>
                    <h3>Record your decision</h3>
                  </div>
                  {isFinal && (
                    <span className="final-lock">
                      {decisionError
                        ? "Previously decided"
                        : "Decision recorded"}
                    </span>
                  )}
                </div>

                {isFinal ? (
                  <>
                    <div className="final-state">
                      <span className="final-state-icon" aria-hidden="true">
                        ✓
                      </span>
                      <div>
                        <strong>
                          {decisionError
                            ? "Another reviewer already decided this submission."
                            : "This submission has been decided."}
                        </strong>
                        <p>
                          {decisionError
                            ? "The latest recorded decision is shown above."
                            : detail.status === "APPROVED"
                              ? "The enrollment was approved."
                              : "The enrollment was returned for correction."}
                        </p>
                      </div>
                    </div>
                    {decisionError && (
                      <p className="decision-inline-error" role="alert">
                        {decisionError}
                      </p>
                    )}
                  </>
                ) : (
                  <>
                    <label className="note-label" htmlFor="decision-note">
                      Return note <span>(required only when returning)</span>
                    </label>
                    <textarea
                      id="decision-note"
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                      placeholder="Explain what information needs correctionâ€¦"
                      maxLength={500}
                      rows={3}
                      disabled={saving}
                      aria-describedby="note-help"
                    />
                    <div className="note-help-row" id="note-help">
                      <span>
                        A clear note helps the employee understand what to fix.
                      </span>
                      <span>{note.length}/500</span>
                    </div>

                    {decisionError && (
                      <p className="decision-inline-error" role="alert">
                        {decisionError}
                      </p>
                    )}

                    <div className="decision-actions">
                      <button
                        type="button"
                        className="button button-primary"
                        onClick={() => void handleDecision("APPROVE")}
                        disabled={saving}
                      >
                        {saving && decision === "APPROVE"
                          ? "Approvingâ€¦"
                          : "Approve enrollment"}
                      </button>
                      <button
                        type="button"
                        className="button button-return"
                        onClick={() => void handleDecision("RETURN")}
                        disabled={saving}
                      >
                        {saving && decision === "RETURN"
                          ? "Returningâ€¦"
                          : "Return for correction"}
                      </button>
                    </div>
                    <p className="decision-footnote">
                      Approval records the decision immediately. Returning
                      requires a note.
                    </p>
                  </>
                )}
              </div>
            </div>
          )}
        </section>
      </div>
      <footer className="app-footer">
        <span>Enrollment Review Workbench</span>
        <span>Decisions are recorded through the review API.</span>
      </footer>
    </main>
  );
}

export default App;
