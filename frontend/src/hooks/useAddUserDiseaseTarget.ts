import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AddUserTargetRequest, AddUserTargetResponse } from "@/types/api";

export function useAddUserDiseaseTarget(analysisId: string) {
    const queryClient = useQueryClient();
    return useMutation<AddUserTargetResponse, Error, AddUserTargetRequest>({
        mutationFn: (body) => api.addUserDiseaseTarget(analysisId, body),
        onSuccess: () => {
            queryClient.invalidateQueries({
                queryKey: ["analysis", analysisId],
            });
        },
    });
}
