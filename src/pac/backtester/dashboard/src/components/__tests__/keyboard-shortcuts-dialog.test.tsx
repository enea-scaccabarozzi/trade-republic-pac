import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { useShortcutsDialogStore } from "@/stores/shortcuts-dialog-store";
import { KeyboardShortcutsDialog } from "../keyboard-shortcuts-dialog";

describe("KeyboardShortcutsDialog", () => {
  afterEach(() => {
    act(() => {
      useShortcutsDialogStore.setState({ isOpen: false });
    });
  });

  it("renders nothing when closed", () => {
    render(<KeyboardShortcutsDialog />);
    expect(screen.queryByText("Keyboard Shortcuts")).not.toBeInTheDocument();
  });

  it("renders title and description when open", () => {
    act(() => {
      useShortcutsDialogStore.setState({ isOpen: true });
    });
    render(<KeyboardShortcutsDialog />);
    expect(screen.getByText("Keyboard Shortcuts")).toBeInTheDocument();
    expect(screen.getByText("Navigate the dashboard with keyboard shortcuts.")).toBeInTheDocument();
  });

  it("renders shortcut groups", () => {
    act(() => {
      useShortcutsDialogStore.setState({ isOpen: true });
    });
    render(<KeyboardShortcutsDialog />);
    expect(screen.getByText("Global")).toBeInTheDocument();
    expect(screen.getByText("Dashboard Home")).toBeInTheDocument();
    expect(screen.getByText("Focus search")).toBeInTheDocument();
    expect(screen.getByText("Go to Dashboard Home")).toBeInTheDocument();
  });

  it("closes when dialog is dismissed", async () => {
    const user = userEvent.setup();
    act(() => {
      useShortcutsDialogStore.setState({ isOpen: true });
    });
    render(<KeyboardShortcutsDialog />);
    expect(screen.getByText("Keyboard Shortcuts")).toBeInTheDocument();

    const closeButton = screen.getByRole("button", { name: /close/i });
    await user.click(closeButton);
    expect(useShortcutsDialogStore.getState().isOpen).toBe(false);
  });
});
