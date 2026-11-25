import type { ReactNode } from "react";

import { ApiError } from "../api/client";
import type { HelpKey } from "../i18n/messages-help";
import { Term } from "./Term";

export interface FormError {
  message: string;
  field: string | null;
}

export function toFormError(error: unknown): FormError {
  if (error instanceof ApiError) return { message: error.message, field: error.field };
  return { message: error instanceof Error ? error.message : String(error), field: null };
}

/** Label, control, hint and the error of this field (when the API named it). */
export function Field(props: {
  label: string;
  /** Explanation of the label, from the help messages. */
  help?: HelpKey;
  name?: string;
  error?: FormError | null;
  hint?: ReactNode;
  lockNote?: string | null;
  wide?: boolean;
  children: ReactNode;
}) {
  const fieldError = props.error && props.name && props.error.field === props.name ? props.error.message : null;
  return (
    <div className={`field${fieldError ? " has-error" : ""}${props.wide ? " wide" : ""}`}>
      <span className="label">
        {props.help ? <Term k={props.help}>{props.label}</Term> : props.label}
        {props.lockNote ? <span className="lock"> · {props.lockNote}</span> : null}
      </span>
      {props.children}
      {props.hint ? <span className="hint">{props.hint}</span> : null}
      {fieldError ? <span className="field-error">{fieldError}</span> : null}
    </div>
  );
}

export function Notice({ kind = "info", children }: { kind?: "info" | "ok" | "warn" | "error"; children: ReactNode }) {
  return (
    <div className={`notice ${kind === "info" ? "" : kind}`} role={kind === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}

/** "" -> null; otherwise a number, or NaN that the API rejects with a field message. */
export function numberOrNull(value: string): number | null {
  const text = value.trim().replace(",", ".");
  return text === "" ? null : Number(text);
}

export function integerOrNull(value: string): number | null {
  const n = numberOrNull(value);
  return n === null ? null : Number.isInteger(n) ? n : Number.NaN;
}

export function linesOf(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

export function today(): string {
  return new Date().toISOString().slice(0, 10);
}
