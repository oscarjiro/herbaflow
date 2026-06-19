import type { Problem } from "./problem";

/**
 * Parse the filename from a Content-Disposition header.
 * Handles both quoted (`filename="foo.zip"`) and unquoted (`filename=foo.zip`) forms.
 */
function filenameFromContentDisposition(header: string | null): string | null {
  if (!header) return null;
  // Quoted form: filename="foo.zip" or filename*=UTF-8''foo.zip (ignore extended)
  const quoted = header.match(/filename="([^"]+)"/i);
  if (quoted) return quoted[1] ?? null;
  // Unquoted form: filename=foo.zip
  const unquoted = header.match(/filename=([^;,\s]+)/i);
  if (unquoted) return unquoted[1] ?? null;
  return null;
}

/**
 * Fetch a server artifact and save it as a file.
 * Throws a Problem on a non-OK response.
 * No toast logic here — the caller wires toasts via a mutation.
 */
export async function fetchBlobDownload(url: string, fallbackName?: string): Promise<void> {
  const res = await fetch(url);

  if (!res.ok) {
    let problem: Problem;
    try {
      problem = (await res.json()) as Problem;
    } catch {
      problem = { status: res.status, title: res.statusText };
    }
    throw problem;
  }

  const blob = await res.blob();

  const contentDisposition = res.headers.get("Content-Disposition");
  const filename =
    filenameFromContentDisposition(contentDisposition) ??
    fallbackName ??
    url.split("/").pop() ??
    "download";

  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(objectUrl);
}
