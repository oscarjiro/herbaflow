import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useRemoveUserDiseaseTarget(analysisId: string) {
    const queryClient = useQueryClient();
    return useMutation<void, Error, string>({
        mutationFn: (geneSymbol) =>
            api.removeUserDiseaseTarget(analysisId, geneSymbol),
        onSuccess: () => {
            queryClient.invalidateQueries({
                queryKey: ["analysis", analysisId],
            });
        },
    });
}
