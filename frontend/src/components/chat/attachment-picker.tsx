import { useEffect, useState } from "react";
import { Paperclip, X, LoaderCircle, CircleAlert } from "lucide-react";
import {
  deleteChatAttachment,
  getChatAttachment,
  uploadChatAttachment,
  type ChatAttachmentDto,
} from "../../lib/chatApi";

interface UploadItem {
  file: File;
  progress: number;
  attachment?: ChatAttachmentDto;
  error?: string;
}

export default function AttachmentPicker({
  disabled,
  onChange,
}: {
  disabled?: boolean;
  onChange: (ids: string[], ready: boolean) => void;
}) {
  const [items, setItems] = useState<UploadItem[]>([]);

  useEffect(() => {
    const extracting = items.filter((item) => item.attachment?.extraction_status === "extracting");
    if (!extracting.length) return;
    const timer = window.setInterval(async () => {
      const updates = await Promise.all(
        extracting.map((item) => getChatAttachment(item.attachment!.id).catch(() => item.attachment!)),
      );
      setItems((current) =>
        current.map((item) => {
          const update = updates.find((candidate) => candidate.id === item.attachment?.id);
          return update ? { ...item, attachment: update } : item;
        }),
      );
    }, 1200);
    return () => window.clearInterval(timer);
  }, [items]);

  useEffect(() => {
    const ids = items.flatMap((item) => item.attachment?.extraction_status === "ready" ? [item.attachment.id] : []);
    const ready = items.every((item) => item.attachment?.extraction_status === "ready");
    onChange(ids, ready);
  }, [items, onChange]);

  async function add(files: FileList | null) {
    if (!files) return;
    const selected = Array.from(files).slice(0, Math.max(0, 5 - items.length));
    for (const file of selected) {
      const item: UploadItem = { file, progress: 0 };
      setItems((current) => [...current, item]);
      try {
        const attachment = await uploadChatAttachment(file, (progress) => {
          setItems((current) => current.map((entry) => entry === item ? { ...entry, progress } : entry));
        });
        setItems((current) => current.map((entry) => entry === item ? { ...entry, progress: 100, attachment } : entry));
      } catch (error) {
        setItems((current) => current.map((entry) => entry === item ? { ...entry, error: (error as Error).message } : entry));
      }
    }
  }

  async function remove(item: UploadItem) {
    if (item.attachment) await deleteChatAttachment(item.attachment.id).catch(() => undefined);
    setItems((current) => current.filter((entry) => entry !== item));
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
      <label title="Đính kèm PDF, DOCX, TXT, MD, CSV hoặc XLSX" style={{ display: "inline-flex", cursor: disabled ? "not-allowed" : "pointer" }}>
        <Paperclip size={17} />
        <input
          hidden
          type="file"
          multiple
          disabled={disabled || items.length >= 5}
          accept=".pdf,.docx,.txt,.md,.csv,.xlsx"
          onChange={(event) => { void add(event.target.files); event.target.value = ""; }}
        />
      </label>
      {items.map((item) => {
        const status = item.error ? "failed" : item.attachment?.extraction_status ?? "uploading";
        return (
          <span key={`${item.file.name}-${item.file.lastModified}`} title={item.error ?? item.attachment?.extraction_error ?? status} style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "2px 7px", border: "1px solid var(--color-border)", borderRadius: 12, fontSize: 11 }}>
            {status === "ready" ? null : status === "failed" ? <CircleAlert size={12} /> : <LoaderCircle size={12} />}
            {item.file.name} {status === "uploading" ? `${item.progress}%` : status}
            <button type="button" aria-label={`Remove ${item.file.name}`} onClick={() => void remove(item)} style={{ border: 0, background: "none", padding: 0, cursor: "pointer", color: "inherit" }}><X size={12} /></button>
          </span>
        );
      })}
    </div>
  );
}
