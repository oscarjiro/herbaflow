import { useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timeout = window.setTimeout(() => setCopied(false), 1700);
    return () => window.clearTimeout(timeout);
  }, [copied]);

  async function onCopy() {
    await window.navigator.clipboard?.writeText(text);
    setCopied(true);
    toast("Copied");
  }

  return (
    <Button type="button" size="sm" variant="outline" onClick={onCopy}>
      {copied ? (
        <Check className="size-4" aria-hidden="true" />
      ) : (
        <Copy className="size-4" aria-hidden="true" />
      )}
      {copied ? "Copied" : label}
    </Button>
  );
}
