# Chat Tab (UI Shell) — Design Spec

- **Date:** 2026-07-19
- **Scope:** Frontend only (`frontend/`). No backend.
- **Goal:** Thêm tab **Chat** ở sidebar, trang `/chat` có giao diện chatbot kiểu ChatGPT. Phản hồi bot là **mock** (chưa nối backend).

## 1. Bản chất
- Thuần frontend. User gửi tin → hiện typing indicator → bot "gõ" ra câu trả lời mock (echo lại + đoạn demo markdown/code để trình diễn UI).
- Lịch sử hội thoại lưu **localStorage** (`vaic:chat:conversations`). Refresh vẫn còn.
- Không có network call, không streaming backend.

## 2. Điều hướng
- `frontend/src/components/Sidebar.tsx`: thêm nav item `{ to: "/chat", label: "Chat", icon: MessageSquare }` **ngay sau Dashboard**. Import `MessageSquare` từ `lucide-react`.
- `frontend/src/App.tsx`: thêm `<Route path="/chat" element={<ChatPage />} />` bên trong `AppShell` (đã có auth guard `ProtectedRoute`).

## 3. Bố cục trang `/chat`
Trong khu content của AppShell:
- **Cột trái — ConversationList (~260px):** nút "+ New chat", danh sách hội thoại (chọn / rename / xóa). Hội thoại active highlight bằng `--color-primary-soft`.
- **Khu phải — ChatArea (flex-1):** message list (scroll, auto-scroll xuống mới nhất) + composer dưới cùng.
- Bubble **user**: nền `--color-primary-soft`, canh phải. Bubble **bot**: nền `--color-surface-muted`, canh trái. Mỗi bubble có timestamp; bubble bot có nút **copy**.

## 4. Components (kebab-case, mỗi file < 200 dòng)
Vị trí: `frontend/src/routes/chat/` + `frontend/src/components/chat/`.

| File | Trách nhiệm |
|------|-------------|
| `routes/chat/ChatPage.tsx` | Layout 2 cột + state "hội thoại đang chọn"; kết nối `useChat`. |
| `components/chat/conversation-list.tsx` | New chat, list, select, rename, delete. |
| `components/chat/message-list.tsx` | Render messages, auto-scroll, typing indicator. |
| `components/chat/message-bubble.tsx` | 1 bubble: role styling, timestamp, nút copy (bot). |
| `components/chat/markdown-message.tsx` | `react-markdown` + `remark-gfm`; code block dùng `shiki` (đã có sẵn). |
| `components/chat/chat-composer.tsx` | Textarea auto-grow; Enter gửi, Shift+Enter xuống dòng; disable khi bot đang "gõ". |
| `lib/chatStore.ts` | CRUD hội thoại/message trên localStorage + hook `useChat`. |
| `lib/mockReply.ts` | Sinh phản hồi mock; typing effect qua callback từng chunk. |

## 5. Data model (localStorage)
```ts
type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
};
type Conversation = {
  id: string;
  title: string;        // lấy từ tin nhắn đầu của user, cắt ~40 ký tự
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
};
```
- Key localStorage: `vaic:chat:conversations` (mảng `Conversation[]`).
- Hội thoại mới rỗng title = "New chat" cho tới khi user gửi tin đầu.

## 6. Tính năng tin nhắn (đã chốt)
- Render **Markdown + code block** (react-markdown + remark-gfm, code qua shiki).
- **Typing effect**: hiện indicator "đang trả lời…" rồi gõ dần nội dung bot.
- **Nút copy** nội dung tin nhắn bot.
- **Auto-scroll** xuống tin mới + **timestamp** mỗi tin.

## 7. Style
- Dùng design tokens hiện có (`--color-*`, `--space-*`, `--radius-*`, `--text-*`). Không thêm CSS framework.
- Đồng bộ với Sidebar/pages hiện tại (inline style + tokens như codebase đang dùng).

## 8. Dependencies thêm
- `react-markdown`
- `remark-gfm`
(Thêm vào `frontend/package.json`. `shiki` đã có sẵn cho highlight code.)

## 9. Ngoài phạm vi (YAGNI)
- Không backend, không auth riêng cho chat, không đa người dùng/đồng bộ server.
- Không đính kèm file, không voice, không chọn model.
- Không test tự động (theo Working Preferences của user — chỉ viết khi được yêu cầu).

## Unresolved questions
- Nội dung đoạn demo markdown/code trong phản hồi mock: dùng 1 đoạn cố định (giới thiệu tính năng) — sẽ chốt cụ thể lúc implement.
