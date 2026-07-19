/* Story 1.9 — Barrel export for all UI primitives.
 *
 * Import from this file: `import { Button, Card, StatusPill } from "../components/ui";`
 */

export { default as Button } from "./Button";
export type { ButtonProps, ButtonVariant } from "./Button";
export { getPrimaryCount, _resetPrimaryCount } from "./Button";

export { default as StatusPill } from "./StatusPill";
export type { StatusPillProps } from "./StatusPill";

export { default as Card } from "./Card";
export type { CardProps } from "./Card";

export { default as Table } from "./Table";
export type { TableProps, TableColumn } from "./Table";

export { default as CodeBlock } from "./CodeBlock";
export type { CodeBlockProps } from "./CodeBlock";

export { default as FormField } from "./FormField";
export type { FormFieldProps } from "./FormField";

export { default as Tooltip } from "./Tooltip";
export type { TooltipProps } from "./Tooltip";

export { default as EmptyState } from "./EmptyState";
export type { EmptyStateProps } from "./EmptyState";

export { default as Skeleton } from "./Skeleton";
export type { SkeletonProps } from "./Skeleton";

export { default as ErrorState } from "./ErrorState";
export type { ErrorStateProps } from "./ErrorState";

export { ToastProvider, useToast } from "./Toast";
export type { ToastVariant } from "./Toast";

export { default as ConfirmDialog } from "./ConfirmDialog";
export type { ConfirmDialogProps } from "./ConfirmDialog";
