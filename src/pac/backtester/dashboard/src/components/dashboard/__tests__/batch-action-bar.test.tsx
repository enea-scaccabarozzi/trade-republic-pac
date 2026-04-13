import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { BatchActionBar } from "../batch-action-bar";

describe("BatchActionBar", () => {
  const defaultProps = {
    selectedCount: 3,
    onCompare: vi.fn(),
    onDelete: vi.fn(),
    onClearSelection: vi.fn(),
  };

  it("does not render when selectedCount is 0", () => {
    const { container } = render(<BatchActionBar {...defaultProps} selectedCount={0} />);
    expect(container.firstChild).toBeNull();
  });

  it("disables Compare when fewer than 2 selected", () => {
    render(<BatchActionBar {...defaultProps} selectedCount={1} />);
    expect(screen.getByRole("button", { name: /compare/i })).toBeDisabled();
  });

  it("enables Compare when 2 or more selected", () => {
    render(<BatchActionBar {...defaultProps} selectedCount={2} />);
    expect(screen.getByRole("button", { name: /compare/i })).toBeEnabled();
  });

  it("calls onDelete when Delete clicked", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(<BatchActionBar {...defaultProps} onDelete={onDelete} />);
    await user.click(screen.getByRole("button", { name: /delete/i }));
    expect(onDelete).toHaveBeenCalledOnce();
  });

  it("calls onClearSelection when Clear clicked", async () => {
    const user = userEvent.setup();
    const onClearSelection = vi.fn();
    render(<BatchActionBar {...defaultProps} onClearSelection={onClearSelection} />);
    await user.click(screen.getByRole("button", { name: /clear/i }));
    expect(onClearSelection).toHaveBeenCalledOnce();
  });
});
