import { cn } from "@/lib/cn";
import type { ReactNode } from "react";

export const Eyebrow = ({ children, className }: { children: ReactNode; className?: string }) => (
  <span className={cn("hf-eyebrow", className)}>{children}</span>
);

export const Binomial = ({ children, className }: { children: ReactNode; className?: string }) => (
  <em className={cn("hf-binomial", className)}>{children}</em>
);

export const StatNumber = ({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) => <span className={cn("hf-num tabular-nums", className)}>{children}</span>;
