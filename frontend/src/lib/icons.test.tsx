/* Test: lib/icons — locked semantic icon assignments (UX-DR10, UX-DR11).
 */

import { describe, it, expect } from "vitest";
import {
  semanticIcons,
  stateMapping,
  allRunStates,
  ICON_STROKE_WIDTH,
} from "./icons";
import {
  Bot,
  Workflow,
  LayoutGrid,
  Activity,
  Zap,
  BookOpen,
  Wrench,
  Plug,
  Cpu,
  Building2,
  Landmark,
  Play,
  AlertTriangle,
  Radio,
  Clock,
  Loader,
  Check,
  Pencil,
} from "lucide-react";

describe("semanticIcons (UX-DR10)", () => {
  it("locks Agent = Bot", () => {
    expect(semanticIcons.Agent).toBe(Bot);
  });
  it("locks Orchestrator = Workflow", () => {
    expect(semanticIcons.Orchestrator).toBe(Workflow);
  });
  it("locks MiniApp = LayoutGrid", () => {
    expect(semanticIcons.MiniApp).toBe(LayoutGrid);
  });
  it("locks Trace = Activity", () => {
    expect(semanticIcons.Trace).toBe(Activity);
  });
  it("locks Action = Zap", () => {
    expect(semanticIcons.Action).toBe(Zap);
  });
  it("locks KnowledgeBase = BookOpen", () => {
    expect(semanticIcons.KnowledgeBase).toBe(BookOpen);
  });
  it("locks Tool = Wrench", () => {
    expect(semanticIcons.Tool).toBe(Wrench);
  });
  it("locks ApiIntegration = Plug", () => {
    expect(semanticIcons.ApiIntegration).toBe(Plug);
  });
  it("locks Model = Cpu", () => {
    expect(semanticIcons.Model).toBe(Cpu);
  });
  it("locks Department = Building2", () => {
    expect(semanticIcons.Department).toBe(Building2);
  });
  it("locks Tenant = Landmark", () => {
    expect(semanticIcons.Tenant).toBe(Landmark);
  });
  it("locks Run = Play", () => {
    expect(semanticIcons.Run).toBe(Play);
  });
  it("locks Escalation = AlertTriangle", () => {
    expect(semanticIcons.Escalation).toBe(AlertTriangle);
  });
  it("locks Live = Radio", () => {
    expect(semanticIcons.Live).toBe(Radio);
  });
});

describe("stateMapping (UX-DR4, UX-DR11)", () => {
  it("has exactly 6 states", () => {
    expect(allRunStates.length).toBe(6);
    expect(allRunStates).toEqual([
      "pending",
      "running",
      "success",
      "error",
      "escalated",
      "draft",
    ]);
  });

  it("locks Pending = Clock + amber-based color token", () => {
    expect(stateMapping.pending.icon).toBe(Clock);
    expect(stateMapping.pending.colorVar).toBe("var(--color-pending)");
  });

  it("locks Running = Loader (spin) + sky", () => {
    expect(stateMapping.running.icon).toBe(Loader);
    expect(stateMapping.running.spin).toBe(true);
    expect(stateMapping.running.colorVar).toContain("running");
  });

  it("locks Success = Check + emerald", () => {
    expect(stateMapping.success.icon).toBe(Check);
    expect(stateMapping.success.colorVar).toContain("success");
  });

  it("locks Error = AlertTriangle + rose", () => {
    expect(stateMapping.error.icon).toBe(AlertTriangle);
    expect(stateMapping.error.colorVar).toContain("error");
  });

  it("locks Escalated = AlertTriangle + amber-600", () => {
    expect(stateMapping.escalated.icon).toBe(AlertTriangle);
    expect(stateMapping.escalated.colorVar).toContain("escalated");
  });

  it("locks Draft = Pencil + slate", () => {
    expect(stateMapping.draft.icon).toBe(Pencil);
    expect(stateMapping.draft.colorVar).toContain("slate");
  });

  it("all states have non-empty labels", () => {
    allRunStates.forEach((state) => {
      expect(stateMapping[state].label.length).toBeGreaterThan(0);
    });
  });

  it("only Running state has spin=true", () => {
    allRunStates.forEach((state) => {
      if (state === "running") {
        expect(stateMapping[state].spin).toBe(true);
      } else {
        expect(stateMapping[state].spin).toBe(false);
      }
    });
  });
});

describe("ICON_STROKE_WIDTH", () => {
  it("is 1.5 (UX-DR10 global stroke)", () => {
    expect(ICON_STROKE_WIDTH).toBe(1.5);
  });
});
