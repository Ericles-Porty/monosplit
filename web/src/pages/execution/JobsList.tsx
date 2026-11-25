import { useState } from "react";

import { send } from "../../api/client";
import type { Job } from "../../api/types";
import { hrefFor } from "../../app/router";
import { useI18n } from "../../i18n/I18n";

function clock(iso: string | null): string {
  return iso ? new Date(iso).toLocaleTimeString() : "";
}

function describeParams(job: Job): string {
  const p = job.params;
  if (job.kind === "extract") return String(p.app ?? "");
  const variants = Array.isArray(p.variants) ? ` · ${(p.variants as string[]).join(", ")}` : "";
  return `${p.config ?? ""} · ${p.profile ?? ""}${variants}`;
}

export function JobsList({ jobs, knownStudies, onChange }: { jobs: Job[]; knownStudies: Set<string>; onChange: () => void }) {
  const { t, fmt } = useI18n();
  const x = t.execution;
  const [error, setError] = useState<string | null>(null);

  const cancel = async (job: Job) => {
    try {
      await send("POST", `jobs/${job.id}/cancel`);
      onChange();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
    }
  };

  if (!jobs.length) return <p className="note">{x.noJobs}</p>;
  return (
    <div>
      {error ? <p className="error">{error}</p> : null}
      {jobs.map((job) => {
        const active = job.status === "queued" || job.status === "running";
        const study = typeof job.result?.study === "string" ? (job.result.study as string) : null;
        return (
          <div key={job.id} className="job">
            <div className="job-head">
              <span className="job-title">{x.kinds[job.kind] ?? job.kind}</span>
              <span className={`chip ${job.status}`}>{x.statuses[job.status] ?? job.status}</span>
              <span className="job-meta mono">{describeParams(job)}</span>
              <span className="job-meta">
                {x.started} {clock(job.started_utc ?? job.created_utc)}
                {job.finished_utc ? ` · ${x.finished} ${clock(job.finished_utc)}` : ""}
              </span>
              {job.cost_usd > 0 ? (
                <span className="job-meta">
                  {x.cost}: {fmt.number(job.cost_usd, 4)}
                </span>
              ) : null}
              <span style={{ marginLeft: "auto" }} className="actions">
                {study && job.status === "succeeded" && knownStudies.has(study) ? (
                  <a href={hrefFor("decompositions", { study })}>{x.openResults}</a>
                ) : typeof job.result?.report === "string" ? (
                  <span className="job-meta mono">{x.report}: {String(job.result.report).replace(/^.*?experimento[\\/]/, "")}</span>
                ) : null}
                {active ? (
                  <button type="button" className="button" onClick={() => cancel(job)} disabled={job.cancel_requested}>
                    {x.cancel}
                  </button>
                ) : null}
              </span>
            </div>
            {job.cancel_requested && active ? <p className="job-meta">{x.cancelRequested}</p> : null}
            {Object.keys(job.progress).length ? (
              <div className="variant-progress">
                {Object.entries(job.progress).map(([variant, p]) => (
                  <ProgressRow key={variant} label={t.variants[variant] ?? variant} accepted={p.accepted} target={p.target}
                    text={x.progress(p.accepted, p.target, p.attempts, p.failed_runs)} />
                ))}
              </div>
            ) : null}
            {job.error ? <p className="error" style={{ whiteSpace: "pre-wrap" }}>{job.error}</p> : null}
            <details open={active}>
              <summary className="job-meta" style={{ cursor: "pointer", marginTop: 6 }}>
                {x.log}
              </summary>
              <pre className="log">{job.log.join("\n")}</pre>
            </details>
          </div>
        );
      })}
    </div>
  );
}

function ProgressRow({ label, accepted, target, text }: { label: string; accepted: number; target: number; text: string }) {
  const share = target ? Math.min(1, accepted / target) : 0;
  return (
    <>
      <span>{label}</span>
      <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={target} aria-valuenow={accepted} aria-label={label}>
        <span style={{ width: `${share * 100}%` }} />
      </div>
      <span className="job-meta">{text}</span>
    </>
  );
}
