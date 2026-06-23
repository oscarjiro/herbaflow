import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

export function ColumnInfo({ text, label }: { text: string; label?: string }) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label={label ?? "About this column"}
            className="text-hf-fg-3 hover:text-hf-fg-2 focus-visible:ring-hf-ink-focus inline-flex size-[15px] cursor-help items-center justify-center rounded-full text-[10px] leading-none font-medium focus-visible:ring-2 focus-visible:outline-none"
            data-slot="column-info"
          >
            i
          </button>
        </TooltipTrigger>
        <TooltipContent>{text}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
