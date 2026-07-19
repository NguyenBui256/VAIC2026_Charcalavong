"""Pure codegen: EntitySchema + UiSpec -> a React .tsx source string (story 4-5).

Deterministic, no I/O (AD-8). The generated component imports ONLY `react`
and the vendored `./sdk` (enforced by `source_guard.assert_source_safe`). No
external UI/CSS library is reachable from the sandboxed iframe, so the whole
look is a self-contained `<style>` design system (CSS custom properties +
inline SVG icons) rendered by the component itself.

The template is assembled by token replacement (NOT an f-string) so the JSX/CSS
braces stay literal and readable. Placeholders: __FIELDS__, __APP_NAME__,
__MODE__, __CSS__.
"""

from __future__ import annotations

import json
import uuid

from app.modules.mini_app.schemas import EntitySchema, UiSpec


def generate_app_source(app_id: uuid.UUID, name: str, schema: EntitySchema, ui_spec: UiSpec) -> str:
    fields_json = json.dumps([f.model_dump() for f in schema.fields])
    return (
        _TEMPLATE
        .replace("__FIELDS__", fields_json)
        .replace("__APP_NAME__", json.dumps(name))
        .replace("__MODE__", json.dumps(ui_spec.mode))
        .replace("__CSS__", json.dumps(_CSS))
    )


# --- Self-contained design system (banking/fintech; SHB red accent) ----------
_CSS = """
.ma-root{--bg:#eef1f6;--surface:#fff;--ink:#14181f;--muted:#667085;--line:#e7ebf2;
--line-strong:#d4dbe8;--accent:#c8102e;--accent-ink:#a10c24;--accent-soft:#fcebee;
--ok:#0f7a53;--ok-soft:#e6f4ee;--radius:16px;--radius-sm:10px;
--shadow:0 1px 2px rgba(16,24,40,.04),0 10px 30px rgba(16,24,40,.06);
box-sizing:border-box;min-height:100vh;margin:0;padding:32px 20px 56px;background:var(--bg);
color:var(--ink);font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,
"Helvetica Neue",Arial,"Noto Sans",sans-serif;font-size:15px;line-height:1.5;
-webkit-font-smoothing:antialiased;}
.ma-root *,.ma-root *::before,.ma-root *::after{box-sizing:border-box;}
.ma-shell{max-width:660px;margin:0 auto;}
.ma-shell.ma-wide{max-width:1060px;}
.ma-header{margin-bottom:22px;}
.ma-eyebrow{font-size:12px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;
color:var(--accent);margin-bottom:8px;}
.ma-title{margin:0;font-size:27px;font-weight:720;letter-spacing:-.02em;}
.ma-sub{margin:6px 0 0;color:var(--muted);font-size:14.5px;}
.ma-card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
box-shadow:var(--shadow);padding:26px 26px 22px;}
.ma-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px 18px;}
.ma-field{display:flex;flex-direction:column;min-width:0;}
.ma-col-2{grid-column:1/-1;}
.ma-label{font-size:13px;font-weight:600;color:var(--ink);margin-bottom:7px;}
.ma-req{color:var(--accent);margin-left:3px;}
.ma-input{width:100%;padding:10px 12px;font:inherit;font-size:14.5px;color:var(--ink);
background:#fff;border:1px solid var(--line-strong);border-radius:var(--radius-sm);outline:none;
transition:border-color .15s,box-shadow .15s;}
.ma-input::placeholder{color:#98a2b3;}
.ma-input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft);}
textarea.ma-input{resize:vertical;min-height:84px;}
.ma-checkbox{width:20px;height:20px;accent-color:var(--accent);cursor:pointer;align-self:flex-start;}
.ma-file-row{display:flex;flex-wrap:wrap;align-items:center;gap:10px;}
.ma-file{display:inline-flex;align-items:center;gap:8px;padding:9px 14px;font-size:13.5px;
font-weight:600;color:var(--ink);background:#f6f8fc;border:1px dashed var(--line-strong);
border-radius:var(--radius-sm);cursor:pointer;transition:border-color .15s,background .15s,color .15s;}
.ma-file:hover{border-color:var(--accent);background:var(--accent-soft);color:var(--accent-ink);}
.ma-file input{display:none;}
.ma-chip{display:inline-flex;align-items:center;gap:6px;max-width:240px;padding:5px 10px;
font-size:12.5px;font-weight:600;border-radius:999px;background:#eef2f8;color:#3a4658;
border:1px solid var(--line);}
.ma-chip .ma-ic{width:13px;height:13px;}
.ma-chip-txt{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.ma-chip-ok{background:var(--ok-soft);color:var(--ok);border-color:transparent;}
.ma-actions{display:flex;gap:10px;margin-top:22px;padding-top:20px;border-top:1px solid var(--line);}
.ma-btn{display:inline-flex;align-items:center;gap:7px;padding:11px 18px;font:inherit;
font-size:14.5px;font-weight:650;color:#fff;background:var(--accent);border:1px solid var(--accent);
border-radius:var(--radius-sm);cursor:pointer;transition:background .15s,transform .05s,box-shadow .15s;}
.ma-btn:hover{background:var(--accent-ink);border-color:var(--accent-ink);}
.ma-btn:active{transform:translateY(1px);}
.ma-btn:focus-visible{outline:none;box-shadow:0 0 0 3px var(--accent-soft);}
.ma-btn-ghost{color:var(--ink);background:#fff;border-color:var(--line-strong);}
.ma-btn-ghost:hover{background:#f6f8fc;color:var(--ink);}
.ma-btn-danger{color:var(--accent);background:#fff;border-color:transparent;}
.ma-btn-danger:hover{background:var(--accent-soft);color:var(--accent-ink);}
.ma-btn-sm{padding:7px 12px;font-size:13px;font-weight:600;}
.ma-ic{width:16px;height:16px;flex:none;}
.ma-form-head{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:650;
color:var(--accent);margin-bottom:18px;padding-bottom:14px;border-bottom:1px solid var(--line);}
.ma-alert{display:flex;align-items:center;gap:9px;padding:12px 14px;border-radius:var(--radius-sm);
font-size:14px;margin-bottom:16px;}
.ma-alert-error{background:var(--accent-soft);color:var(--accent-ink);border-left:3px solid var(--accent);}
.ma-panel{margin-top:20px;}
.ma-toolbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;}
.ma-count{font-size:13px;font-weight:600;color:var(--muted);}
.ma-table-wrap{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
box-shadow:var(--shadow);overflow-x:auto;}
.ma-table{width:100%;border-collapse:collapse;font-size:14px;}
.ma-table thead th{text-align:left;font-size:11.5px;font-weight:700;letter-spacing:.06em;
text-transform:uppercase;color:var(--muted);padding:13px 16px;background:#f7f9fc;
border-bottom:1px solid var(--line-strong);white-space:nowrap;}
.ma-table tbody td{padding:12px 16px;border-bottom:1px solid var(--line);vertical-align:middle;}
.ma-table tbody tr:last-child td{border-bottom:none;}
.ma-table tbody tr:hover{background:#f9fbfe;}
.ma-th-act,.ma-td-act{text-align:right;white-space:nowrap;}
.ma-td-act{display:flex;gap:6px;justify-content:flex-end;}
.ma-dim{color:#b0b8c6;}
.ma-empty{padding:48px 24px;text-align:center;color:var(--muted);background:var(--surface);
border:1px solid var(--line);border-radius:var(--radius);}
.ma-empty-icon{width:44px;height:44px;margin:0 auto 12px;display:flex;align-items:center;
justify-content:center;border-radius:12px;background:#f1f4f9;color:#98a2b3;}
.ma-empty-icon .ma-ic{width:22px;height:22px;}
.ma-success{text-align:center;padding:44px 26px;}
.ma-success-badge{width:56px;height:56px;margin:0 auto 16px;display:flex;align-items:center;
justify-content:center;border-radius:50%;background:var(--ok-soft);color:var(--ok);}
.ma-success-badge .ma-ic{width:28px;height:28px;}
.ma-success h2{margin:0 0 6px;font-size:20px;font-weight:700;}
.ma-success .ma-btn{margin-top:18px;}
@media (max-width:560px){.ma-root{padding:20px 14px 40px;}.ma-card{padding:20px 18px;}
.ma-title{font-size:23px;}.ma-td-act{flex-direction:column;}}
@media (prefers-reduced-motion:reduce){.ma-root *{transition:none !important;}}
"""


_TEMPLATE = '''import { useEffect, useState } from "react";
import { sdk } from "./sdk";

const FIELDS = __FIELDS__;
const APP_NAME = __APP_NAME__;
const MODE = __MODE__;
const CSS = __CSS__;

const EYEBROW = MODE === "crm" ? "Danh sách hồ sơ" : MODE === "form" ? "Biểu mẫu đăng ký" : "Ứng dụng dữ liệu";
const SUBTITLE = MODE === "crm"
  ? "Xem và xử lý các hồ sơ đã nộp."
  : MODE === "form"
  ? "Điền thông tin và đính kèm tài liệu để gửi hồ sơ."
  : "";

const ICONS = {
  upload: "M12 16V4M6 10l6-6 6 6M4 20h16",
  check: "M20 6L9 17l-5-5",
  warn: "M10.3 3.9l-8 14A2 2 0 004 21h16a2 2 0 001.7-3l-8-14a2 2 0 00-3.4 0zM12 9v4M12 17h.01",
  edit: "M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z",
  trash: "M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6",
  refresh: "M21 12a9 9 0 11-3-6.7L21 8M21 3v5h-5",
  inbox: "M22 12h-6l-2 3h-4l-2-3H2M5 5h14l3 7v6a1 1 0 01-1 1H3a1 1 0 01-1-1v-6z",
  file: "M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8zM14 2v6h6",
};

function Icon({ name }) {
  return (
    <svg className="ma-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={ICONS[name]} />
    </svg>
  );
}

function isWide(f) { return f.type === "longtext" || f.type === "file"; }

function Widget({ f, form, setForm }) {
  const set = (v) => setForm((s) => ({ ...s, [f.name]: v }));
  const val = form[f.name] ?? "";
  if (f.type === "boolean") {
    return <input className="ma-checkbox" type="checkbox" checked={!!form[f.name]}
      onChange={(e) => set(e.target.checked)} />;
  }
  if (f.type === "longtext") {
    return <textarea className="ma-input" rows={4} value={val} onChange={(e) => set(e.target.value)} />;
  }
  if (f.type === "enum") {
    return (
      <select className="ma-input" value={val} onChange={(e) => set(e.target.value)}>
        <option value="">— Chọn —</option>
        {(f.options || []).map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }
  if (f.type === "file") {
    const cur = form[f.name];
    return (
      <div className="ma-file-row">
        <label className="ma-file">
          <input type="file" onChange={async (e) => { const file = e.target.files?.[0]; if (file) set(await sdk.uploadFile(file)); }} />
          <Icon name="upload" />
          <span>{cur?.name ? "Thay tệp khác" : "Chọn tệp để tải lên"}</span>
        </label>
        {cur?.name ? (
          <span className="ma-chip ma-chip-ok"><Icon name="check" /><span className="ma-chip-txt">{cur.name}</span></span>
        ) : null}
      </div>
    );
  }
  const t = { integer: "number", number: "number", date: "date" }[f.type] || "text";
  return (
    <input className="ma-input" type={t} value={val}
      onChange={(e) => set(f.type === "integer" || f.type === "number" ? Number(e.target.value) : e.target.value)} />
  );
}

function cell(f, r) {
  const v = r.data?.[f.name];
  if (f.type === "file") {
    return v?.name
      ? <span className="ma-chip"><Icon name="file" /><span className="ma-chip-txt">{v.name}</span></span>
      : <span className="ma-dim">—</span>;
  }
  if (f.type === "boolean") {
    return v ? <span className="ma-chip ma-chip-ok">Có</span> : <span className="ma-dim">Không</span>;
  }
  const s = v === undefined || v === null || v === "" ? "" : String(v);
  return s ? s : <span className="ma-dim">—</span>;
}

export default function MiniApp() {
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({});
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(MODE !== "form");

  async function reload() {
    if (MODE === "form") return;
    setLoading(true);
    try { setRows(await sdk.list()); setError(""); }
    catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  }
  useEffect(() => { reload(); }, []);

  async function submit(e) {
    e.preventDefault();
    try {
      if (editing) await sdk.update(editing.id, form, editing.updated_at);
      else await sdk.create(form);
      setForm({}); setEditing(null); setError(""); setDone(!editing); reload();
    } catch (err) { setError(String(err)); }
  }
  function startEdit(r) { setEditing(r); setForm(r.data || {}); setDone(false); }
  function cancel() { setEditing(null); setForm({}); }

  const showSuccess = MODE === "form" && done;
  const showForm = !showSuccess && (MODE === "form" || MODE === "full" || (MODE === "crm" && !!editing));
  const showTable = MODE !== "form";

  return (
    <div className="ma-root">
      <style>{CSS}</style>
      <div className={"ma-shell" + (MODE !== "form" ? " ma-wide" : "")}>
        <header className="ma-header">
          <div className="ma-eyebrow">{EYEBROW}</div>
          <h1 className="ma-title">{APP_NAME}</h1>
          {SUBTITLE ? <p className="ma-sub">{SUBTITLE}</p> : null}
        </header>

        {error ? <div className="ma-alert ma-alert-error"><Icon name="warn" /><span>{error}</span></div> : null}

        {showSuccess ? (
          <div className="ma-card ma-success">
            <div className="ma-success-badge"><Icon name="check" /></div>
            <h2>Đã gửi hồ sơ thành công</h2>
            <p className="ma-sub">Cảm ơn bạn. Hồ sơ đã được tiếp nhận và sẽ được xử lý.</p>
            <button className="ma-btn" type="button" onClick={() => setDone(false)}>Gửi hồ sơ khác</button>
          </div>
        ) : null}

        {showForm ? (
          <form className="ma-card" onSubmit={submit}>
            {MODE === "crm" && editing ? (
              <div className="ma-form-head"><Icon name="edit" /><span>Chỉnh sửa hồ sơ</span></div>
            ) : null}
            <div className="ma-grid">
              {FIELDS.map((f) => (
                <div key={f.name} className={"ma-field" + (isWide(f) ? " ma-col-2" : "")}>
                  <label className="ma-label">{f.label || f.name}{f.required ? <span className="ma-req">*</span> : null}</label>
                  <Widget f={f} form={form} setForm={setForm} />
                </div>
              ))}
            </div>
            <div className="ma-actions">
              <button className="ma-btn" type="submit">{editing ? "Lưu thay đổi" : "Gửi hồ sơ"}</button>
              {editing ? <button className="ma-btn ma-btn-ghost" type="button" onClick={cancel}>Hủy</button> : null}
            </div>
          </form>
        ) : null}

        {showTable ? (
          <div className="ma-panel">
            <div className="ma-toolbar">
              <span className="ma-count">{rows.length} hồ sơ</span>
              <button className="ma-btn ma-btn-ghost ma-btn-sm" type="button" onClick={reload}>
                <Icon name="refresh" />Làm mới
              </button>
            </div>
            {loading ? (
              <div className="ma-empty">Đang tải…</div>
            ) : rows.length === 0 ? (
              <div className="ma-empty">
                <div className="ma-empty-icon"><Icon name="inbox" /></div>
                <p>Chưa có hồ sơ nào.</p>
              </div>
            ) : (
              <div className="ma-table-wrap">
                <table className="ma-table">
                  <thead>
                    <tr>
                      {FIELDS.map((f) => <th key={f.name}>{f.label || f.name}</th>)}
                      <th className="ma-th-act">Thao tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.id}>
                        {FIELDS.map((f) => <td key={f.name}>{cell(f, r)}</td>)}
                        <td className="ma-td-act">
                          <button className="ma-btn ma-btn-ghost ma-btn-sm" type="button" onClick={() => startEdit(r)}>
                            <Icon name="edit" />Sửa
                          </button>
                          <button className="ma-btn ma-btn-danger ma-btn-sm" type="button" onClick={async () => { await sdk.remove(r.id); reload(); }}>
                            <Icon name="trash" />Xóa
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
'''
