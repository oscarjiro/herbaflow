import { createFileRoute, Outlet } from "@tanstack/react-router";

// Layout for the analysis section: renders its child route (`/analysis` index = Setup,
// `/analysis/$id` = Run) via the Outlet. Without this Outlet the `$id` child would not mount.
export const Route = createFileRoute("/analysis")({
  component: () => <Outlet />,
});
