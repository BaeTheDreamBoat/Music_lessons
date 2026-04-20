"""Debug screens for calibrating note position, accidentals, and ledger lines."""

import tkinter as tk
from PIL import ImageTk

from music_lessons import CANVAS_W, CANVAS_H, save_config


class DebugMenus:
    def __init__(self, app):
        self.app = app

    def show(self, debug_type):
        {
            "Note on scale":     self._note_on_scale,
            "sharp location":    lambda: self._accidental("sharp"),
            "flat location":     lambda: self._accidental("flat"),
            "notes above scale": lambda: self._ledger("above"),
            "notes below scale": lambda: self._ledger("below"),
        }[debug_type]()

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _frame(self, title, subtitle=""):
        app = self.app
        app._clear()
        f = tk.Frame(app.root, bg="white")
        f.pack(fill=tk.BOTH, expand=True)
        tk.Label(f, text=title, font=("Arial", 14, "bold"), bg="white").pack(pady=5)
        if subtitle:
            tk.Label(f, text=subtitle, bg="white", wraplength=720).pack()
        c = tk.Canvas(f, bg="white", width=CANVAS_W, height=CANVAS_H)
        c.pack()
        return f, c

    def _blit_staff(self, c):
        if "staff" not in self.app._imgs:
            return
        tk_s = ImageTk.PhotoImage(self.app._imgs["staff"])
        if not hasattr(c, '_refs'):
            c._refs = []
        c._refs.append(tk_s)
        c.create_image(CANVAS_W // 2, CANVAS_H // 2, image=tk_s)

    # ── Note on scale ─────────────────────────────────────────────────────────

    def _note_on_scale(self):
        f, c = self._frame(
            "Debug: Note on Scale",
            "Move A4 onto the correct staff position, then adjust offset until top note lands on C5.",
        )
        cfg   = self.app.cfg
        state = {"a4_y": cfg["a4_y"], "off": int(cfg["step_height"] * 2)}
        imgs  = self.app._imgs

        def redraw():
            c.delete("all")
            c._refs = []
            self._blit_staff(c)
            a4y = state["a4_y"]
            c5y = a4y - state["off"]
            for img, x, y, lbl in [
                (imgs.get("note"), CANVAS_W // 2 - 40, a4y, "A4"),
                (imgs.get("note"), CANVAS_W // 2 + 40, c5y, "C5"),
            ]:
                if img:
                    tk_n = ImageTk.PhotoImage(img)
                    c._refs.append(tk_n)
                    c.create_image(x, y, image=tk_n)
                    c.create_text(x - 30, y, text=lbl, font=("Arial", 11, "bold"))
            c.create_text(8, 8, anchor="nw",
                text=f"a4_y={a4y}  C5 offset={state['off']}  step={state['off']/2:.1f}px",
                font=("Arial", 10))

        redraw()

        bf = tk.Frame(f, bg="white")
        bf.pack(pady=4)
        tk.Label(bf, text="A4:", bg="white").grid(row=0, column=0, padx=4)
        tk.Button(bf, text="\u25b2", command=lambda: (state.__setitem__("a4_y", state["a4_y"] - 1), redraw())).grid(row=0, column=1)
        tk.Button(bf, text="\u25bc", command=lambda: (state.__setitem__("a4_y", state["a4_y"] + 1), redraw())).grid(row=0, column=2)
        tk.Label(bf, text="   C5 offset:", bg="white").grid(row=0, column=3, padx=4)
        tk.Button(bf, text="\u25b2", command=lambda: (state.__setitem__("off", max(2, state["off"] - 1)), redraw())).grid(row=0, column=4)
        tk.Button(bf, text="\u25bc", command=lambda: (state.__setitem__("off", state["off"] + 1), redraw())).grid(row=0, column=5)

        def save():
            cfg["a4_y"]        = state["a4_y"]
            cfg["step_height"] = state["off"] / 2.0
            save_config(cfg)
            self.app.show_menu()

        tk.Button(f, text="Save & Back", bg="#228b22", fg="white", command=save).pack(pady=5)

    # ── Sharp / flat location ─────────────────────────────────────────────────

    def _accidental(self, kind):
        f, c = self._frame(
            f"Debug: {kind} location",
            f"Move the {kind} symbol to the correct position relative to the note (A4).",
        )
        cfg    = self.app.cfg
        xk, yk = f"{kind}_x_offset", f"{kind}_y_offset"
        state  = {"x": cfg[xk], "y": cfg[yk]}
        imgs   = self.app._imgs
        nx, ny = CANVAS_W // 2, cfg["a4_y"]

        def redraw():
            c.delete("all")
            c._refs = []
            self._blit_staff(c)
            for img, x, y in [
                (imgs.get("note"), nx, ny),
                (imgs.get(kind),   nx + state["x"], ny + state["y"]),
            ]:
                if img:
                    tk_i = ImageTk.PhotoImage(img)
                    c._refs.append(tk_i)
                    c.create_image(x, y, image=tk_i)
            c.create_text(8, 8, anchor="nw",
                text=f"x_offset={state['x']}  y_offset={state['y']}", font=("Arial", 10))

        redraw()

        bf = tk.Frame(f, bg="white")
        bf.pack(pady=4)
        tk.Button(bf, text="\u2190", command=lambda: (state.__setitem__("x", state["x"] - 1), redraw())).grid(row=1, column=0)
        tk.Button(bf, text="\u25b2", command=lambda: (state.__setitem__("y", state["y"] - 1), redraw())).grid(row=0, column=1)
        tk.Button(bf, text="\u25bc", command=lambda: (state.__setitem__("y", state["y"] + 1), redraw())).grid(row=2, column=1)
        tk.Button(bf, text="\u2192", command=lambda: (state.__setitem__("x", state["x"] + 1), redraw())).grid(row=1, column=2)

        def save():
            cfg[xk] = state["x"]
            cfg[yk] = state["y"]
            save_config(cfg)
            self.app.show_menu()

        tk.Button(f, text="Save & Back", bg="#228b22", fg="white", command=save).pack(pady=5)

    # ── Ledger line calibration ───────────────────────────────────────────────

    def _ledger(self, direction):
        f, c = self._frame(
            f"Debug: notes {direction} scale",
            f"Move the ledger line to its correct position {direction} the note.",
        )
        cfg   = self.app.cfg
        key   = f"ledger_{direction}_y_offset"
        state = {"y": cfg.get(key, -15 if direction == "above" else 15)}
        imgs  = self.app._imgs
        nx, ny = CANVAS_W // 2, CANVAS_H // 2

        def redraw():
            c.delete("all")
            c._refs = []
            for img, x, y in [
                (imgs.get("note"), nx, ny),
                (imgs.get("line"), nx, ny + state["y"]),
            ]:
                if img:
                    tk_i = ImageTk.PhotoImage(img)
                    c._refs.append(tk_i)
                    c.create_image(x, y, image=tk_i)
            c.create_text(8, 8, anchor="nw",
                text=f"y_offset={state['y']}", font=("Arial", 10))

        redraw()

        bf = tk.Frame(f, bg="white")
        bf.pack(pady=4)
        tk.Button(bf, text="\u25b2", command=lambda: (state.__setitem__("y", state["y"] - 1), redraw())).pack(side=tk.LEFT, padx=6)
        tk.Button(bf, text="\u25bc", command=lambda: (state.__setitem__("y", state["y"] + 1), redraw())).pack(side=tk.LEFT, padx=6)

        def save():
            cfg[key] = state["y"]
            save_config(cfg)
            self.app.show_menu()

        tk.Button(f, text="Save & Back", bg="#228b22", fg="white", command=save).pack(pady=5)
