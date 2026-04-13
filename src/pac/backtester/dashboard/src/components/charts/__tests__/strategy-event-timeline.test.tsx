import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { StrategyEvent, StrategyEventMeta } from "@/types/api";
import { StrategyEventTimeline } from "../strategy-event-timeline";

const spanMeta: StrategyEventMeta = {
  key: "pac_tilt",
  display_name: "PAC Tilt",
  kind: "span",
  color: "blue",
};

const pointMeta: StrategyEventMeta = {
  key: "hard_rebalance",
  display_name: "Hard Rebalance",
  kind: "point",
  color: "red",
};

describe("StrategyEventTimeline", () => {
  it("renders span events as rect elements", () => {
    const events: StrategyEvent[] = [
      {
        date: "2024-01-01",
        event_type: "pac_tilt",
        details: {},
        end_date: "2024-03-01",
      },
    ];
    const { container } = render(
      <StrategyEventTimeline
        events={events}
        eventMeta={[spanMeta]}
        startDate="2024-01-01"
        endDate="2024-12-31"
      />,
    );
    expect(container.querySelectorAll("rect")).toHaveLength(1);
  });

  it("renders point events as circle elements", () => {
    const events: StrategyEvent[] = [
      {
        date: "2024-06-15",
        event_type: "hard_rebalance",
        details: {},
        end_date: null,
      },
    ];
    const { container } = render(
      <StrategyEventTimeline
        events={events}
        eventMeta={[pointMeta]}
        startDate="2024-01-01"
        endDate="2024-12-31"
      />,
    );
    expect(container.querySelectorAll("circle")).toHaveLength(1);
  });

  it("renders swim lane labels from eventMeta", () => {
    const events: StrategyEvent[] = [
      {
        date: "2024-06-15",
        event_type: "hard_rebalance",
        details: {},
        end_date: null,
      },
    ];
    render(
      <StrategyEventTimeline
        events={events}
        eventMeta={[spanMeta, pointMeta]}
        startDate="2024-01-01"
        endDate="2024-12-31"
      />,
    );
    expect(screen.getByText("PAC Tilt")).toBeInTheDocument();
    expect(screen.getByText("Hard Rebalance")).toBeInTheDocument();
  });

  it("shows empty state when no events", () => {
    render(
      <StrategyEventTimeline
        events={[]}
        eventMeta={[]}
        startDate="2024-01-01"
        endDate="2024-12-31"
      />,
    );
    expect(screen.getByText("No strategy events recorded")).toBeInTheDocument();
  });
});
