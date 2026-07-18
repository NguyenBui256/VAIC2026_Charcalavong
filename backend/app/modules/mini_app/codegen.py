"""Pure codegen: EntitySchema + UiSpec -> a React .tsx source string (story 4-5).

Deterministic, no I/O (AD-8). The generated component imports ONLY `react`
and the vendored `./sdk` (enforced by the AST allowlist in Task 10). Field
type -> widget mapping is fixed by the meta-schema.
"""

from __future__ import annotations

import json
import uuid

from app.modules.mini_app.schemas import EntitySchema, UiSpec

_WIDGET = {
    "string": "text", "longtext": "textarea", "integer": "number",
    "number": "number", "boolean": "checkbox", "date": "date", "enum": "select",
}


def generate_app_source(app_id: uuid.UUID, name: str, schema: EntitySchema, ui_spec: UiSpec) -> str:
    fields_json = json.dumps([f.model_dump() for f in schema.fields])
    safe_name = json.dumps(name)
    return f"""import {{ useEffect, useState }} from "react";
import {{ sdk }} from "./sdk";

const FIELDS = {fields_json};
const APP_NAME = {safe_name};

export default function MiniApp() {{
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({{}});
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");

  async function reload() {{ try {{ setRows(await sdk.list()); }} catch (e) {{ setError(String(e)); }} }}
  useEffect(() => {{ reload(); }}, []);

  async function submit(e) {{
    e.preventDefault();
    try {{
      if (editing) await sdk.update(editing.id, form, editing.updated_at);
      else await sdk.create(form);
      setForm({{}}); setEditing(null); setError(""); reload();
    }} catch (err) {{ setError(String(err)); }}
  }}

  return (
    <div style={{{{ fontFamily: "system-ui", padding: 16 }}}}>
      <h2>{{APP_NAME}}</h2>
      {{error && <p style={{{{ color: "crimson" }}}}>{{error}}</p>}}
      <form onSubmit={{submit}}>
        {{FIELDS.map((f) => (
          <label key={{f.name}} style={{{{ display: "block", margin: "8px 0" }}}}>
            <span style={{{{ marginRight: 8 }}}}>{{f.label || f.name}}</span>
            {{renderWidget(f, form, setForm)}}
          </label>
        ))}}
        <button type="submit">{{editing ? "Save" : "Create"}}</button>
        {{editing && <button type="button" onClick={{() => {{ setEditing(null); setForm({{}}); }}}}>Cancel</button>}}
      </form>
      <table border={{1}} cellPadding={{6}} style={{{{ marginTop: 16, borderCollapse: "collapse" }}}}>
        <thead><tr>{{FIELDS.map((f) => <th key={{f.name}}>{{f.label || f.name}}</th>)}}<th></th></tr></thead>
        <tbody>
          {{rows.map((r) => (
            <tr key={{r.id}}>
              {{FIELDS.map((f) => <td key={{f.name}}>{{String(r.data?.[f.name] ?? "")}}</td>)}}
              <td>
                <button onClick={{() => {{ setEditing(r); setForm(r.data || {{}}); }}}}>Edit</button>
                <button onClick={{async () => {{ await sdk.remove(r.id); reload(); }}}}>Delete</button>
              </td>
            </tr>
          ))}}
        </tbody>
      </table>
    </div>
  );
}}

function renderWidget(f, form, setForm) {{
  const set = (v) => setForm((s) => ({{ ...s, [f.name]: v }}));
  const val = form[f.name] ?? "";
  if (f.type === "boolean") return <input type="checkbox" checked={{!!form[f.name]}} onChange={{(e) => set(e.target.checked)}} />;
  if (f.type === "longtext") return <textarea value={{val}} onChange={{(e) => set(e.target.value)}} />;
  if (f.type === "enum") return <select value={{val}} onChange={{(e) => set(e.target.value)}}><option value="">--</option>{{(f.options||[]).map((o) => <option key={{o}} value={{o}}>{{o}}</option>)}}</select>;
  const inputType = {{ integer: "number", number: "number", date: "date" }}[f.type] || "text";
  return <input type={{inputType}} value={{val}} onChange={{(e) => set(f.type === "integer" || f.type === "number" ? Number(e.target.value) : e.target.value)}} />;
}}
"""
