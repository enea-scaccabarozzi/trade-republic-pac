import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { type WizardStep, WizardStepper } from "../wizard-stepper";

const STEPS: WizardStep[] = [
  { label: "Strategy", description: "Pick a strategy" },
  { label: "Configure", description: "Set parameters" },
  { label: "Review", description: "Confirm & launch" },
];

describe("WizardStepper", () => {
  it("renders correct number of steps", () => {
    render(<WizardStepper steps={STEPS} currentStep={0} />);
    expect(screen.getByText("Strategy")).toBeInTheDocument();
    expect(screen.getByText("Configure")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
  });

  it("highlights the active step with font-semibold", () => {
    render(<WizardStepper steps={STEPS} currentStep={1} />);
    const active = screen.getByText("Configure");
    expect(active).toHaveClass("font-semibold");
  });

  it("shows check icon for completed steps", () => {
    const { container } = render(<WizardStepper steps={STEPS} currentStep={2} />);
    // Steps 0 and 1 are completed → their circles contain an SVG (Check icon)
    const circles = container.querySelectorAll(".rounded-full");
    const completedCircles = [circles[0], circles[1]];
    for (const circle of completedCircles) {
      expect(circle?.querySelector("svg")).toBeTruthy();
    }
    // Step 2 (active) shows number "3", not an SVG
    expect(circles[2]?.textContent).toBe("3");
  });

  it("renders step labels", () => {
    const steps: WizardStep[] = [{ label: "Alpha" }, { label: "Beta" }];
    render(<WizardStepper steps={steps} currentStep={0} />);
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });

  it("applies completed styling to steps before currentStep", () => {
    const { container } = render(<WizardStepper steps={STEPS} currentStep={2} />);
    const circles = container.querySelectorAll(".rounded-full");
    // Both completed circles have bg-primary
    expect(circles[0]).toHaveClass("bg-primary");
    expect(circles[1]).toHaveClass("bg-primary");
  });
});
