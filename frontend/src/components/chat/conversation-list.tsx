/* Left column: New chat button + list of conversations.
 * Double-click a title to rename (Enter/blur = save, Escape = cancel).
 * Active conversation highlighted with primary-soft.
 */

import { useState, type KeyboardEvent } from "react";
import { Plus, MessageSquare, Trash2 } from "lucide-react";
import type { Conversation } from "../../lib/chatStore";

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
}

export default function ConversationList({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onRename,
}: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  function startEdit(c: Conversation) {
    setEditingId(c.id);
    setDraft(c.title);
  }

  function commitEdit() {
    if (editingId) onRename(editingId, draft);
    setEditingId(null);
    setDraft("");
  }

  function cancelEdit() {
    setEditingId(null);
    setDraft("");
  }

  function onEditKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      commitEdit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      cancelEdit();
    }
  }

  return (
    <div
      style={{
        width: "260px",
        flexShrink: 0,
        borderRight: "1px solid var(--color-border)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "var(--color-surface)",
      }}
    >
      <div style={{ padding: "var(--space-3)" }}>
        <button
          type="button"
          onClick={onNew}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
            padding: "var(--space-2) var(--space-3)",
            borderRadius: "var(--radius-control, 8px)",
            border: "1px solid var(--color-border)",
            background: "var(--color-surface)",
            color: "var(--color-text-primary)",
            cursor: "pointer",
            fontSize: "var(--text-body)",
            fontWeight: 500,
          }}
        >
          <Plus size={16} strokeWidth={1.5} />
          <span>New chat</span>
        </button>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "0 var(--space-2)" }}>
        {conversations.length === 0 ? (
          <p
            className="text-caption"
            style={{
              color: "var(--color-text-tertiary)",
              padding: "var(--space-3)",
              textAlign: "center",
            }}
          >
            Chưa có hội thoại
          </p>
        ) : (
          conversations.map((c) => {
            const active = c.id === activeId;
            const editing = c.id === editingId;
            return (
              <div
                key={c.id}
                onClick={() => !editing && onSelect(c.id)}
                className="vaic-conv-item"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-2)",
                  padding: "var(--space-2) var(--space-3)",
                  margin: "var(--space-1) 0",
                  borderRadius: "var(--radius-control, 8px)",
                  cursor: editing ? "default" : "pointer",
                  background: active ? "var(--color-primary-soft)" : "transparent",
                  color: active
                    ? "var(--color-primary)"
                    : "var(--color-text-secondary)",
                }}
              >
                <MessageSquare size={15} strokeWidth={1.5} style={{ flexShrink: 0 }} />
                {editing ? (
                  <input
                    autoFocus
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={onEditKeyDown}
                    onBlur={commitEdit}
                    onClick={(e) => e.stopPropagation()}
                    aria-label="Đổi tên hội thoại"
                    style={{
                      flex: 1,
                      minWidth: 0,
                      padding: "2px var(--space-2)",
                      borderRadius: "var(--radius-control, 6px)",
                      border: "1px solid var(--color-border)",
                      background: "var(--color-surface)",
                      color: "var(--color-text-primary)",
                      fontSize: "var(--text-body)",
                      fontFamily: "inherit",
                      outline: "none",
                    }}
                  />
                ) : (
                  <span
                    onDoubleClick={(e) => {
                      e.stopPropagation();
                      startEdit(c);
                    }}
                    title="Double-click để đổi tên"
                    style={{
                      flex: 1,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      fontSize: "var(--text-body)",
                    }}
                  >
                    {c.title}
                  </span>
                )}
                {!editing && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(c.id);
                    }}
                    aria-label="Xóa hội thoại"
                    title="Xóa"
                    style={{
                      display: "inline-flex",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      color: "var(--color-text-tertiary)",
                      padding: 0,
                      flexShrink: 0,
                    }}
                  >
                    <Trash2 size={14} strokeWidth={1.5} />
                  </button>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
