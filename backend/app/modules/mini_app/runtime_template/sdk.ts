declare global { interface Window { __MINIAPP__: { appId: string; token: string; apiBase: string } } }
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
};
