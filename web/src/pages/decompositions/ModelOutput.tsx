import type { RunPayload } from "../../api/types";
import { Term } from "../../components/Term";
import { useI18n } from "../../i18n/I18n";

function pretty(text: string): string {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

/** The accepted answer of the model for this run, exactly as returned, with its attempt record. */
export function ModelOutput({ run }: { run: RunPayload }) {
  const { t, fmt } = useI18n();
  const a = run.attempt;
  return (
    <details className="block">
      <summary>
        {t.decompositions.outputTitle} · {t.decompositions.outputAttempt(a.attempt, a.try)}
      </summary>
      <div className="block-body">
        <dl className="facts">
          <dt>
            <Term k="modelReported">{t.decompositions.outputModel}</Term>
          </dt>
          <dd className="mono">{a.model_returned ?? t.common.dash}</dd>
          <dt>
            <Term k="tokens">{t.decompositions.outputTokens}</Term>
          </dt>
          <dd>
            {fmt.integer(a.input_tokens)} / {fmt.integer(a.output_tokens)} / {fmt.integer(a.reasoning_tokens)}
          </dd>
          <dt>
            <Term k="latency">{t.decompositions.outputLatency}</Term>
          </dt>
          <dd>{fmt.number(a.latency_s ?? null, 1)}</dd>
          <dt>
            <Term k="cost">{t.decompositions.outputCost}</Term>
          </dt>
          <dd>{fmt.number(a.cost_usd ?? null, 5)}</dd>
        </dl>
        <pre className="output">{pretty(run.output_text)}</pre>
      </div>
    </details>
  );
}
