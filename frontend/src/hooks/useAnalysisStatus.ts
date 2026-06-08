import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import type { AnalysisRead } from "../api/types.gen";
import { getAnalysisOptions } from "../api/@tanstack/react-query.gen";

const TERMINAL = ["complete", "failed"];

export function useAnalysisStatus(analysisId: string | null): UseQueryResult<AnalysisRead> {
  return useQuery({
    ...getAnalysisOptions({ path: { analysis_id: analysisId ?? "" } }),
    enabled: analysisId != null,
    refetchInterval: (query) => {
      const data = query.state.data as AnalysisRead | undefined;
      const status = data?.status;
      return status && TERMINAL.includes(status) ? false : 1000;
    },
  }) as UseQueryResult<AnalysisRead>;
}
