import { useState } from "react";
import { RunView } from "./components/RunView";
import { SetupView } from "./components/SetupView";

export function App() {
  const [runId, setRunId] = useState<string | null>(null);
  return <main>{runId ? <RunView analysisId={runId} /> : <SetupView onCreated={setRunId} />}</main>;
}
