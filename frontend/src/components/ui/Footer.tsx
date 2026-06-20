import { useMatchRoute } from "@tanstack/react-router";

export function Footer() {
  const matchRoute = useMatchRoute();
  if (matchRoute({ to: "/analysis/$id" })) return null;

  return (
    <footer className="border-hf-border border-t">
      <div className="text-hf-fg-3 mx-auto max-w-6xl px-4 py-6 text-sm">Herbaflow</div>
    </footer>
  );
}
