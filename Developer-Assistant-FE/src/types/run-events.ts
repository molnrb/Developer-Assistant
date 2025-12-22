
export type RunEvent =
  | { t: "status"; step: string; state: "queued"|"running"|"done"|"failed"; ts?: number }
  | { t: "router.result"; domain: string; confidence: number; rationale: string; ts?: number }
  | { t: "plan.ready"; files: number; ts?: number }
  | { t: "log"; stream?: "stdout"|"stderr"; chunk: string; ts?: number }
  | { t: "done"; ok: boolean; ts?: number }
  | Record<string, unknown>;
