import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useRemoveUserTarget(analysisId: string) {
    const queryClient = useQueryClient();
    return useMutation<void, Error, string>({
        mutationFn: (geneSymbol) =>
            api.removeUserTarget(analysisId, geneSymbol),
        onSuccess: () => {
            queryClient.invalidateQueries({
                queryKey: ["analysis", analysisId],
            });
        },
    });
}
