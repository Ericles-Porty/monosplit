import { useEffect, useState } from "react";

import { getFresh, invalidate } from "../../api/client";
import type { Job } from "../../api/types";

/**
 * Jobs of the local server, kept in one store for the whole interface. The App starts the
 * watcher, so jobs are followed on every page, not only on the Execution page: when a job
 * finishes, cached data is dropped and every page shows the new graphs, runs and results.
 * Polled every second while a job is queued or running and every five seconds otherwise.
 */
type JobsState = { jobs: Job[]; busy: boolean; error: Error | null };

let state: JobsState = { jobs: [], busy: false, error: null };
const listeners = new Set<(next: JobsState) => void>();
// Finished jobs already reflected in the cached data. A job that finished before the page
// was opened is already in the data the page loaded.
const seen = new Set<string>();
const openedAt = Date.now();
let timer: number | undefined;
let watchers = 0;

function finishedSinceOpened(job: Job): boolean {
  return job.finished_utc ? Date.parse(job.finished_utc) >= openedAt : false;
}

export async function refreshJobs(): Promise<void> {
  try {
    const answer = await getFresh<{ jobs: Job[]; busy: boolean }>("jobs");
    const done = answer.jobs.filter((j) => !["queued", "running"].includes(j.status));
    const fresh = done.filter((j) => !seen.has(j.id));
    for (const job of fresh) seen.add(job.id);
    if (fresh.some(finishedSinceOpened)) invalidate();
    state = { jobs: answer.jobs, busy: answer.busy, error: null };
  } catch (error) {
    state = { ...state, error: error as Error };
  }
  for (const listener of listeners) listener(state);
}

async function tick(): Promise<void> {
  await refreshJobs();
  if (watchers > 0) timer = window.setTimeout(tick, state.busy ? 1000 : 5000);
}

/** Follows the jobs while mounted; the App mounts it once in the local version. */
export function useJobWatcher(enabled: boolean): void {
  useEffect(() => {
    if (!enabled) return;
    watchers += 1;
    if (watchers === 1) tick();
    return () => {
      watchers -= 1;
      if (watchers === 0) window.clearTimeout(timer);
    };
  }, [enabled]);
}

export function useJobs(): JobsState & { refresh: () => void } {
  const [current, setCurrent] = useState(state);
  useEffect(() => {
    listeners.add(setCurrent);
    setCurrent(state);
    refreshJobs();
    return () => {
      listeners.delete(setCurrent);
    };
  }, []);
  return { ...current, refresh: () => void refreshJobs() };
}
