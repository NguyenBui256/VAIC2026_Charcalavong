/* Story 2.8 T2.2 — the tab strip: label + count badge + dirty dot, WAI-ARIA
 * tablist keyboard model (UX-DR12 / AC #9).
 *
 * `role="tablist"` on the strip, `role="tab"` on each tab, roving tabindex
 * (active tab `0`, others `-1`), arrow keys move the active tab, Home/End
 * jump to first/last, Enter/Space activate. Disabled tabs are
 * `aria-disabled` and skipped by arrow navigation (AC #7, #9).
 */

import { useRef } from "react";
import { ICON_STROKE_WIDTH } from "../../lib/icons";
import { tabIcon, tabRegistry } from "./tabRegistry";
import TabCountBadge, { type CountNoun } from "./TabCountBadge";
import type { TabCounts, TabKey } from "./agentBuilderTypes";

const COUNT_NOUNS: Record<string, CountNoun> = {
  documents: "document",
  tools: "tool",
  integrations: "integration",
};

export interface AgentTabNavProps {
  activeTab: TabKey;
  onTabChange: (tab: TabKey) => void;
  /** Tabs disabled for the new-Agent gating flow (AC #7). */
  disabledTabs: Set<TabKey>;
  dirtyTabs: Partial<Record<TabKey, boolean>>;
  counts: TabCounts;
}

export default function AgentTabNav({
  activeTab,
  onTabChange,
  disabledTabs,
  dirtyTabs,
  counts,
}: AgentTabNavProps) {
  const buttonRefs = useRef<Partial<Record<TabKey, HTMLButtonElement | null>>>({});

  const enabledKeys = tabRegistry.map((t) => t.key).filter((k) => !disabledTabs.has(k));

  function focusAndSelect(key: TabKey) {
    onTabChange(key);
    buttonRefs.current[key]?.focus();
  }

  function moveFocus(fromKey: TabKey, direction: 1 | -1) {
    if (enabledKeys.length === 0) return;
    const allKeys = tabRegistry.map((t) => t.key);
    let idx = allKeys.indexOf(fromKey);
    for (let i = 0; i < allKeys.length; i++) {
      idx = (idx + direction + allKeys.length) % allKeys.length;
      const candidate = allKeys[idx];
      if (!disabledTabs.has(candidate)) {
        focusAndSelect(candidate);
        return;
      }
    }
  }

  function handleKeyDown(e: React.KeyboardEvent, key: TabKey) {
    switch (e.key) {
      case "ArrowRight":
      case "ArrowDown":
        e.preventDefault();
        moveFocus(key, 1);
        break;
      case "ArrowLeft":
      case "ArrowUp":
        e.preventDefault();
        moveFocus(key, -1);
        break;
      case "Home":
        e.preventDefault();
        if (enabledKeys[0]) focusAndSelect(enabledKeys[0]);
        break;
      case "End":
        e.preventDefault();
        if (enabledKeys[enabledKeys.length - 1]) {
          focusAndSelect(enabledKeys[enabledKeys.length - 1]);
        }
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        if (!disabledTabs.has(key)) onTabChange(key);
        break;
      default:
        break;
    }
  }

  return (
    <nav className="vaic-tabs" role="tablist" aria-label="Agent configuration">
      {tabRegistry.map((entry) => {
        const Icon = tabIcon(entry);
        const isDisabled = disabledTabs.has(entry.key);
        const isActive = activeTab === entry.key;
        const isDirty = Boolean(dirtyTabs[entry.key]);
        const countValue = entry.countKey ? counts[entry.countKey] : undefined;
        const noun = entry.countKey ? COUNT_NOUNS[entry.countKey] : undefined;

        return (
          <button
            key={entry.key}
            ref={(el) => {
              buttonRefs.current[entry.key] = el;
            }}
            type="button"
            role="tab"
            id={`vaic-tab-${entry.key}`}
            aria-selected={isActive}
            aria-disabled={isDisabled}
            tabIndex={isActive ? 0 : -1}
            title={isDisabled ? "Save the Agent to unlock this tab" : undefined}
            className={`vaic-tab vaic-focusable ${isActive ? "vaic-tab-active" : ""}`}
            onClick={() => {
              if (!isDisabled) onTabChange(entry.key);
            }}
            onKeyDown={(e) => handleKeyDown(e, entry.key)}
            data-testid={`vaic-tab-${entry.key}`}
          >
            <Icon size={14} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
            {entry.label}
            {noun && <TabCountBadge count={countValue} noun={noun} />}
            {isDirty && (
              <span
                className="vaic-dirty-dot"
                aria-label="Unsaved changes"
                data-testid="vaic-dirty-dot"
              />
            )}
          </button>
        );
      })}
    </nav>
  );
}
