/* Story 2.8 T6.1 — per-tab error -> loading -> empty -> data boundary
 * (UX-DR23 branch order, mirrors components/dashboard/RecentRuns.tsx).
 *
 * The six existing tabs (Stories 2.2-2.7) already implement this branch
 * order internally against their own query hooks — this wrapper is the
 * shared seam for that pattern so any NEW tab (or a future rewrite) gets
 * the exact same order for free, without the shell needing to know each
 * tab's query internals (Dev Notes "Scope Boundaries" — integration only,
 * never re-implementing a tab's feature logic).
 */

import type { ReactNode } from "react";
import { Button, EmptyState, ErrorState, Skeleton, type SkeletonProps } from "../ui";

export interface TabBoundaryProps {
  isError: boolean;
  errorMessage?: string;
  onRetry: () => void;
  isLoading: boolean;
  skeleton?: SkeletonProps;
  isEmpty?: boolean;
  emptyState?: ReactNode;
  children: ReactNode;
}

export default function TabBoundary({
  isError,
  errorMessage,
  onRetry,
  isLoading,
  skeleton,
  isEmpty,
  emptyState,
  children,
}: TabBoundaryProps) {
  if (isError) {
    return (
      <ErrorState
        message={errorMessage ?? "Something went wrong loading this tab"}
        retry={
          <Button variant="secondary" onClick={onRetry}>
            Retry
          </Button>
        }
      />
    );
  }

  if (isLoading) {
    return <Skeleton lines={4} height="20px" {...skeleton} />;
  }

  if (isEmpty && emptyState) {
    return <>{emptyState}</>;
  }

  return <>{children}</>;
}

export { EmptyState };
