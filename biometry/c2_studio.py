#!/usr/bin/env python3
"""
C2 Studio - a small GUI front-end for the stress-aware interaction engine.

Why this exists
---------------
The engine already runs two ways:
  * terminal:  python run_live_adaptive.py --profile rushed --seed 2026 --actions 40
  * the HEART desktop studio's "Biometric User Mimic" tab -> touch *synthesis*
    only (a slider sets a fixed stress and samples the spatial model).

Neither gives a GUI for the *adaptive closed loop* - the research contribution:
    cognitive Markov state -> distortion -> dispatch -> FrameProbe -> stress -> ...
This window wraps the exact same `run_live_adaptive.py` the terminal uses (as a
subprocess), so the GUI and the terminal never drift apart - there is no second
copy of the engine logic here. The equivalent terminal command is shown live, so
you can always copy it and fall back to the shell.

Run it (from the biometry/ directory):
    ../.venv/bin/python c2_studio.py
"""
import os
import sys
import subprocess
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

try:
    import customtkinter as ctk
except Exception:
    sys.stderr.write("This GUI needs customtkinter:  pip install customtkinter\n")
    raise

# Populate the profile list straight from the engine so the GUI can never drift
# out of step with what the code actually offers.
try:
    from models.profiles import PROFILES
    PROFILE_CHOICES = sorted(PROFILES)
except Exception:
    PROFILE_CHOICES = ["calm", "default", "rushed", "tremor"]

# Never auto-run the engine against a messaging app. The calculator is the agreed
# safe target for demos; it is pre-filled so the default can do no harm.
SAFE_PACKAGE = "com.sec.android.app.popupcalculator"

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class C2Studio(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("C2 - Stress-Aware Input Studio")
        self.geometry("860x760")
        self.minsize(720, 620)

        self._proc = None            # the running run_live_adaptive.py subprocess
        self._ctk_img = None         # keep a reference so the figure is not GC'd
        self._last_png = None

        # --- header -------------------------------------------------------
        head = ctk.CTkFrame(self, corner_radius=0, fg_color="#0C4F91")
        head.pack(fill="x")
        ctk.CTkLabel(
            head, text="C2 - Stress-Aware Input Interaction Engine",
            font=ctk.CTkFont(size=16, weight="bold"), text_color="#ffffff",
        ).pack(side="left", padx=14, pady=10)
        ctk.CTkLabel(
            head, text="GUI front-end for run_live_adaptive.py  -  terminal still works",
            font=ctk.CTkFont(size=11), text_color="#cfe2f5",
        ).pack(side="left", padx=4)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=10)

        # --- controls -----------------------------------------------------
        form = ctk.CTkFrame(body)
        form.pack(fill="x")
        for c in range(4):
            form.grid_columnconfigure(c, weight=1, uniform="f")

        # Mode: adaptive (the novelty) vs static (the control arm)
        self.mode = ctk.StringVar(value="Adaptive (closed loop)")
        ctk.CTkLabel(form, text="Mode", anchor="w",
                     font=ctk.CTkFont(size=11, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(12, 2))
        self.mode_sel = ctk.CTkSegmentedButton(
            form, values=["Adaptive (closed loop)", "Static (control)"],
            variable=self.mode, command=lambda _=None: self._sync())
        self.mode_sel.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))

        # Profile persona
        self.profile = ctk.StringVar(value="rushed" if "rushed" in PROFILE_CHOICES else PROFILE_CHOICES[0])
        ctk.CTkLabel(form, text="Behaviour profile", anchor="w",
                     font=ctk.CTkFont(size=11, weight="bold")).grid(
            row=0, column=2, sticky="w", padx=10, pady=(12, 2))
        ctk.CTkOptionMenu(form, values=PROFILE_CHOICES, variable=self.profile,
                          command=lambda _=None: self._sync()).grid(
            row=1, column=2, columnspan=2, sticky="ew", padx=10, pady=(0, 8))

        # Numeric entries: seed / actions / static stress
        self.seed = self._entry(form, "Seed", "2026", row=2, col=0)
        self.actions = self._entry(form, "Actions", "40", row=2, col=1)
        self.stress = self._entry(form, "Static stress (0-1)", "0.45", row=2, col=2)
        self.pxmm = self._entry(form, "px/mm (blank = measure)", "", row=2, col=3)

        # Optional device / package / oracle / output
        self.package = self._entry(form, "Package (blank = foreground app)", SAFE_PACKAGE, row=4, col=0, span=2)
        self.device = self._entry(form, "Device serial (blank = only device)", "", row=4, col=2)
        self.oracle = self._entry(form, "Oracle URL (blank = off)", "", row=6, col=0, span=2)
        self.out = self._entry(form, "Output prefix", "results/live_run", row=6, col=2, span=2)

        caution = ctk.CTkLabel(
            form,
            text="Safety: the calculator is pre-filled as the target. Never point this at a "
                 "messaging app - launch the calculator first (see C2-Demo-Script).",
            font=ctk.CTkFont(size=10), text_color="#B4531F", wraplength=820, justify="left")
        caution.grid(row=8, column=0, columnspan=4, sticky="w", padx=10, pady=(4, 10))

        # --- equivalent terminal command (keeps the shell first-class) ----
        cmd_row = ctk.CTkFrame(body, fg_color="transparent")
        cmd_row.pack(fill="x", pady=(6, 2))
        ctk.CTkLabel(cmd_row, text="Equivalent terminal command:",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(2, 8))
        ctk.CTkButton(cmd_row, text="Copy", width=60, command=self._copy_cmd).pack(side="right", padx=2)
        self.cmd_box = ctk.CTkTextbox(body, height=46, wrap="word",
                                      font=ctk.CTkFont(family="monospace", size=12))
        self.cmd_box.pack(fill="x", pady=(0, 8))

        # --- run / stop / open --------------------------------------------
        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x")
        self.run_btn = ctk.CTkButton(btns, text="  Run on device", fg_color="#1f6f35",
                                     hover_color="#17592a", command=self._run)
        self.run_btn.pack(side="left", padx=2)
        self.stop_btn = ctk.CTkButton(btns, text="Stop", fg_color="#B4531F",
                                      hover_color="#8f3f18", state="disabled", command=self._stop)
        self.stop_btn.pack(side="left", padx=2)
        self.open_btn = ctk.CTkButton(btns, text="Open figure", state="disabled",
                                      command=self._open_fig)
        self.open_btn.pack(side="left", padx=2)
        self.status = ctk.CTkLabel(btns, text="idle", font=ctk.CTkFont(size=11),
                                   text_color="#5a6b7b")
        self.status.pack(side="right", padx=6)

        # --- live log + figure --------------------------------------------
        split = ctk.CTkFrame(body, fg_color="transparent")
        split.pack(fill="both", expand=True, pady=(8, 0))
        self.log = ctk.CTkTextbox(split, wrap="none",
                                  font=ctk.CTkFont(family="monospace", size=12))
        self.log.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.log.configure(state="disabled")
        self.fig_label = ctk.CTkLabel(split, text="(run writes a stress/state timeline here)",
                                      width=360, fg_color="#f1f5f9", corner_radius=8,
                                      text_color="#5a6b7b")
        self.fig_label.pack(side="right", fill="y")

        self._sync()

    # -- small helpers ----------------------------------------------------
    def _entry(self, parent, label, default, row, col, span=1):
        ctk.CTkLabel(parent, text=label, anchor="w",
                     font=ctk.CTkFont(size=11, weight="bold")).grid(
            row=row, column=col, columnspan=span, sticky="w", padx=10, pady=(6, 2))
        var = ctk.StringVar(value=default)
        ent = ctk.CTkEntry(parent, textvariable=var)
        ent.grid(row=row + 1, column=col, columnspan=span, sticky="ew", padx=10, pady=(0, 6))
        var.trace_add("write", lambda *_: self._sync())
        return var

    def _build_cmd(self):
        """The argv run_live_adaptive.py is invoked with. Single source of truth
        for both the preview text and the actual subprocess."""
        cmd = [sys.executable, "run_live_adaptive.py"]
        cmd += ["--profile", self.profile.get()]
        cmd += ["--seed", (self.seed.get().strip() or "2026")]
        cmd += ["--actions", (self.actions.get().strip() or "40")]
        if self.mode.get().startswith("Static"):
            cmd += ["--static", "--stress", (self.stress.get().strip() or "0.45")]
        if self.pxmm.get().strip():
            cmd += ["--px-per-mm", self.pxmm.get().strip()]
        if self.package.get().strip():
            cmd += ["--package", self.package.get().strip()]
        if self.device.get().strip():
            cmd += ["--device", self.device.get().strip()]
        if self.oracle.get().strip():
            cmd += ["--oracle-url", self.oracle.get().strip()]
        if self.out.get().strip():
            cmd += ["--out", self.out.get().strip()]
        return cmd

    def _sync(self):
        """Refresh the command preview and enable/disable the static-stress box."""
        is_static = self.mode.get().startswith("Static")
        try:
            # grey out static stress unless in static mode (purely cosmetic)
            pass
        except Exception:
            pass
        shown = " ".join(("python" if a == sys.executable else a) for a in self._build_cmd())
        self.cmd_box.configure(state="normal")
        self.cmd_box.delete("1.0", "end")
        self.cmd_box.insert("1.0", shown)
        self.cmd_box.configure(state="disabled")

    def _copy_cmd(self):
        shown = " ".join(("python" if a == sys.executable else a) for a in self._build_cmd())
        self.clipboard_clear()
        self.clipboard_append(shown)
        self._set_status("command copied")

    def _set_status(self, text, color="#5a6b7b"):
        self.status.configure(text=text, text_color=color)

    def _append(self, line):
        self.log.configure(state="normal")
        self.log.insert("end", line)
        self.log.see("end")
        self.log.configure(state="disabled")

    # -- run / stream / stop ----------------------------------------------
    def _run(self):
        if self._proc is not None:
            return
        cmd = self._build_cmd()
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._append("$ " + " ".join(("python" if a == sys.executable else a) for a in cmd) + "\n\n")
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.open_btn.configure(state="disabled")
        self._set_status("running...", "#0C4F91")
        threading.Thread(target=self._worker, args=(cmd,), daemon=True).start()

    def _worker(self, cmd):
        try:
            self._proc = subprocess.Popen(
                cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
        except Exception as e:
            self.after(0, self._append, f"\n[failed to launch] {e}\n")
            self.after(0, self._finish, None)
            return
        for line in self._proc.stdout:
            self.after(0, self._append, line)
        rc = self._proc.wait()
        self.after(0, self._finish, rc)

    def _finish(self, rc):
        self._proc = None
        self.run_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        if rc == 0:
            self._set_status("done", "#1f6f35")
            self._show_fig()
        elif rc is None:
            self._set_status("could not start", "#B4531F")
        else:
            self._set_status(f"exited {rc}", "#B4531F")

    def _stop(self):
        if self._proc is not None:
            self._set_status("stopping...", "#B4531F")
            try:
                self._proc.terminate()
            except Exception:
                pass

    # -- figure ------------------------------------------------------------
    def _png_path(self):
        out = (self.out.get().strip() or "results/live_run")
        png = out + "_timeline.png"
        return png if os.path.isabs(png) else os.path.join(HERE, png)

    def _show_fig(self):
        png = self._png_path()
        if not os.path.exists(png):
            return
        try:
            from PIL import Image
            img = Image.open(png)
            w, h = img.size
            maxw = 360
            if w > maxw:
                h = int(h * maxw / float(w))
                w = maxw
            self._ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(w, h))
            self.fig_label.configure(image=self._ctk_img, text="")
            self._last_png = png
            self.open_btn.configure(state="normal")
        except Exception as e:
            self.fig_label.configure(text=f"(wrote {os.path.basename(png)};\ncould not preview: {e})")
            self._last_png = png
            self.open_btn.configure(state="normal")

    def _open_fig(self):
        png = self._last_png or self._png_path()
        if not png or not os.path.exists(png):
            return
        try:
            if sys.platform.startswith("darwin"):
                subprocess.Popen(["open", png])
            elif os.name == "nt":
                os.startfile(png)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", png])
        except Exception as e:
            self._set_status(f"open failed: {e}", "#B4531F")


if __name__ == "__main__":
    C2Studio().mainloop()
