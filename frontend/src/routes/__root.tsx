import { createRootRoute, Outlet } from "@tanstack/react-router";
import { ThemeProvider } from "@/lib/theme";
import { Nav } from "@/components/ui/Nav";
import { Footer } from "@/components/ui/Footer";
import { Toaster } from "sonner";

export const Route = createRootRoute({
  component: () => (
    <ThemeProvider>
      <div className="bg-hf-bg text-hf-fg-1 flex min-h-dvh flex-col">
        <Nav />
        <main className="flex-1">
          <Outlet />
        </main>
        <Footer />
        <Toaster position="bottom-right" />
      </div>
    </ThemeProvider>
  ),
  errorComponent: ({ error }) => (
    <div className="mx-auto max-w-prose p-8">
      <p className="text-hf-fg-2">{error.message}</p>
    </div>
  ),
});
