declare global { interface Window { __MINIAPP__: { appId: string; token: string; apiBase: string } } }

// Host page (Task 16) passes config via the URL hash instead of postMessage
// or query params, so the sandboxed iframe (sandbox="allow-scripts allow-forms",
// deliberately WITHOUT allow-same-origin) never touches the parent's storage.
// Hydrate window.__MINIAPP__ from location.hash on load if not already set.
if (!window.__MINIAPP__) {
  const hash = new URLSearchParams(location.hash.replace(/^#/, ""));
  window.__MINIAPP__ = {
    appId: hash.get("appId") || "",
    token: hash.get("token") || "",
    apiBase: hash.get("apiBase") || "",
  };
}

const cfg = () => window.__MINIAPP__;
async function call(path: string, init?: RequestInit) {
  const c = cfg();
  const resp = await fetch(`${c.apiBase}/apps/${c.appId}/rows${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${c.token}`, ...(init?.headers || {}) },
  });
  const body = await resp.json();
  if (!resp.ok) throw new Error(body?.error?.message || "request failed");
  return body.data;
}
export const sdk = {
  list: () => call(""),
  create: (data: unknown) => call("", { method: "POST", body: JSON.stringify({ data }) }),
  update: (id: string, data: unknown, expected_updated_at: string) =>
    call(`/${id}`, { method: "PATCH", body: JSON.stringify({ data, expected_updated_at }) }),
  remove: (id: string) => call(`/${id}`, { method: "DELETE" }),
  uploadFile: async (file: File) => {
    const c = cfg();
    const fd = new FormData();
    fd.append("file", file);
    const resp = await fetch(`${c.apiBase}/apps/${c.appId}/files`, {
      method: "POST",
      headers: { Authorization: `Bearer ${c.token}` },  // no Content-Type: browser sets multipart boundary
      body: fd,
    });
    const body = await resp.json();
    if (!resp.ok) throw new Error(body?.error?.message || "upload failed");
    return body.data as { id: string; name: string; mime: string; size: number };
  },
};
