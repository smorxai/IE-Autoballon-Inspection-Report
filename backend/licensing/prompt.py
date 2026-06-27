"""
First-launch license key prompt.

Tries a small Tkinter dialog (nice for the installed exe); falls back to a
console prompt when Tkinter is unavailable. Returns True when the software
is activated for this machine.
"""
from __future__ import annotations

from licensing.activation import check_activation, create_activation
from licensing.machine_id import get_machine_id

_MAX_ATTEMPTS = 5


def _prompt_tkinter() -> bool:
    import tkinter as tk
    from tkinter import messagebox

    result = {"ok": False}

    root = tk.Tk()
    root.title("SmorX Inspection Report — Activation")
    root.geometry("560x230")
    root.resizable(False, False)
    try:
        root.eval("tk::PlaceWindow . center")
    except Exception:
        pass

    tk.Label(root, text="Software Activation", font=("Segoe UI", 14, "bold")).pack(pady=(16, 4))
    tk.Label(
        root,
        text=f"Machine ID: {get_machine_id()}",
        font=("Segoe UI", 9),
        fg="#555555",
    ).pack()
    tk.Label(root, text="Enter your license key:", font=("Segoe UI", 10)).pack(pady=(12, 4))

    entry = tk.Entry(root, width=72, font=("Consolas", 9), show="")
    entry.pack(padx=16)
    entry.focus_set()

    attempts = {"n": 0}

    def on_activate():
        key = entry.get().strip()
        ok, msg = create_activation(key)
        if ok:
            result["ok"] = True
            messagebox.showinfo("Activated", msg)
            root.destroy()
            return
        attempts["n"] += 1
        if attempts["n"] >= _MAX_ATTEMPTS:
            messagebox.showerror("Activation failed", "Too many invalid attempts.")
            root.destroy()
            return
        messagebox.showerror("Activation failed", msg)

    tk.Button(
        root, text="Activate", width=18, font=("Segoe UI", 10, "bold"), command=on_activate
    ).pack(pady=14)
    root.bind("<Return>", lambda e: on_activate())

    root.mainloop()
    return result["ok"]


def _prompt_console() -> bool:
    print("\n=== SmorX Inspection Report — Activation ===")
    print(f"Machine ID: {get_machine_id()}")
    for _ in range(_MAX_ATTEMPTS):
        try:
            key = input("Enter license key: ").strip()
        except (EOFError, KeyboardInterrupt):
            return False
        ok, msg = create_activation(key)
        print(msg)
        if ok:
            return True
    print("Too many invalid attempts.")
    return False


def ensure_activated() -> bool:
    """True when already activated or successfully activated now."""
    ok, _ = check_activation()
    if ok:
        return True
    try:
        return _prompt_tkinter()
    except Exception:
        return _prompt_console()
