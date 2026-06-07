import { execSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";

test("eslint rejects dangerouslySetInnerHTML", () => {
  // The temp file must live INSIDE the project: eslint's flat config uses this
  // directory as its base path and silently skips files outside it, which would
  // make eslint exit 0 and pass this test for the wrong reason.
  const dir = mkdtempSync(join(process.cwd(), ".lint-tmp-"));
  const file = join(dir, "Bad.tsx");
  writeFileSync(
    file,
    `export const B = () => <div dangerouslySetInnerHTML={{ __html: "x" }} />;\n`,
  );
  let failed = false;
  try {
    execSync(`pnpm exec eslint --no-ignore "${file}"`, { stdio: "pipe" });
  } catch {
    failed = true;
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
  expect(failed).toBe(true);
});
