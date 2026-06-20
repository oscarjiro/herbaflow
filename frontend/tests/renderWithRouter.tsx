import type { ReactNode } from "react";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { ThemeProvider } from "../src/lib/theme";

/**
 * Renders `ui` inside a minimal TanStack Router + Query context so router hooks
 * (useNavigate, <Link>, <Navigate>, useMatchRoute) and query hooks resolve.
 * The route tree stubs /, /analysis, /analysis/$id, /about (all render null);
 * the component under test is mounted in the always-on root component.
 */
export function renderWithRouter(
  ui: ReactNode,
  opts: { initialEntries?: string[]; withTheme?: boolean } = {},
) {
  const { initialEntries = ["/"], withTheme = false } = opts;
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const content = withTheme ? <ThemeProvider>{ui}</ThemeProvider> : ui;

  const rootRoute = createRootRoute({ component: () => <>{content}</> });
  const stub = (path: string) =>
    createRoute({ getParentRoute: () => rootRoute, path, component: () => null });
  const router = createRouter({
    routeTree: rootRoute.addChildren([
      stub("/"),
      stub("/analysis"),
      stub("/analysis/$id"),
      stub("/about"),
    ]),
    history: createMemoryHistory({ initialEntries }),
  });

  return {
    qc,
    router,
    ...render(
      <QueryClientProvider client={qc}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    ),
  };
}
