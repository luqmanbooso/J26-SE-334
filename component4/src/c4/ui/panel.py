"""CustomTkinter presentation for the C4 demo.

The module deliberately keeps the toolkit import inside ``build_c4_view`` so
the controller remains usable by headless tests and the C4 CLI.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from c4.ui.controller import C4DemoController, HealView


def build_c4_view(parent, theme: dict, log: Callable[[str], None] = print, root=None):
    import customtkinter as ctk
    from tkinter import filedialog

    root = root or parent.winfo_toplevel()
    try:
        from vision_oracle.core.config import C3_DIR
        c3_inbox = Path(C3_DIR) / "results" / "c4_inbox"
    except Exception:
        c3_inbox = None
    controller = C4DemoController(c3_inbox=c3_inbox)
    sample_dir = Path(__file__).parent / "samples"
    out_root = Path(__file__).parents[3] / "out"
    variables = {
        name: ctk.StringVar(value=value)
        for name, value in {
            "config": "", "model": "qwen3:8b", "ollama": "http://127.0.0.1:11434",
            "telemetry": "", "source": "sentry", "journey": "", "script": "",
            "step": "0", "hierarchy": "", "baseline": "", "status": "Ready",
            "threshold": "0.5", "c3_evidence": "(auto: match session)",
        }.items()
    }
    c3_var = ctk.BooleanVar(value=False)
    heal_var = ctk.BooleanVar(value=False)
    current_journeys = []
    action_buttons = []

    def card(title: str, subtitle: str | None = None):
        frame = ctk.CTkFrame(parent, fg_color=theme["bg_card"], corner_radius=8,
                             border_width=1, border_color=theme["border"])
        frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=theme["text_heading"]).pack(anchor="w", padx=14, pady=(10, 2))
        if subtitle:
            ctk.CTkLabel(frame, text=subtitle, font=ctk.CTkFont(size=10),
                         text_color=theme["text_muted"]).pack(anchor="w", padx=14)
        body = ctk.CTkFrame(frame, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=10)
        return body

    def row(body, label, variable, browse=False):
        line = ctk.CTkFrame(body, fg_color="transparent")
        line.pack(fill="x", pady=2)
        ctk.CTkLabel(line, text=label, width=125, anchor="w",
                     text_color=theme["text_muted"]).pack(side="left")
        entry = ctk.CTkEntry(line, textvariable=variable)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        if browse:
            ctk.CTkButton(line, text="Browse", width=70,
                          command=lambda: _browse(variable)).pack(side="right")
        return entry

    def _browse(variable):
        selected = filedialog.askopenfilename()
        if selected:
            variable.set(selected)

    def write_log(message):
        log(message)
        log_box.configure(state="normal")
        log_box.insert("end", f"{message}\n")
        log_box.see("end")
        log_box.configure(state="disabled")

    def run_async(buttons, work, done):
        for button in buttons:
            button.configure(state="disabled")
        def worker():
            try:
                result = work()
            except Exception as error:
                result = error
            root.after(0, lambda: finish(buttons, result, done))
        threading.Thread(target=worker, daemon=True).start()

    def finish(buttons, result, done):
        for button in buttons:
            button.configure(state="normal")
        done(result)

    def button(body, text, command, color=None):
        item = ctk.CTkButton(body, text=text, command=command,
                             fg_color=color or theme["primary"],
                             hover_color=theme.get("primary_hover", theme["primary"]))
        item.pack(side="left", padx=(0, 6), pady=4)
        action_buttons.append(item)
        return item

    def status_label(body):
        label = ctk.CTkLabel(body, textvariable=variables["status"],
                             text_color=theme["text_muted"])
        label.pack(anchor="w", pady=(4, 0))
        return label

    setup = card("A  Setup", "Target readiness and local inference configuration")
    row(setup, "Target config", variables["config"], True)
    row(setup, "Model", variables["model"])
    row(setup, "Ollama URL", variables["ollama"])
    ctk.CTkCheckBox(setup, text="Use C3 verdict context", variable=c3_var).pack(anchor="w", pady=3)
    c3_menu = ctk.CTkOptionMenu(setup, variable=variables["c3_evidence"], values=["(auto: match session)"])
    c3_menu.pack(anchor="w", pady=3)
    row(setup, "Heal threshold", variables["threshold"])

    def refresh_c3_evidence():
        c3_menu.configure(values=["(auto: match session)", *controller.c3_evidence()])

    def selected_c3():
        value = variables["c3_evidence"].get()
        return None if value.startswith("(auto") else value

    def heal_threshold():
        try:
            value = float(variables["threshold"].get())
        except ValueError:
            raise ValueError("Heal threshold must be a number between 0 and 1")
        if not 0.0 <= value <= 1.0:
            raise ValueError("Heal threshold must be a number between 0 and 1")
        return value

    refresh_c3_evidence()
    button(setup, "Preflight", lambda: run_async(action_buttons, lambda: controller.preflight(variables["config"].get()),
        lambda result: _show_preflight(result))).pack_forget()
    preflight_button = setup.winfo_children()[-1]
    preflight_button.pack(side="left", padx=(0, 6), pady=4)
    status_label(setup)
    preflight_chips = ctk.CTkLabel(setup, text="", text_color=theme["text_muted"])
    preflight_chips.pack(anchor="w")

    journeys_card = card("B  Journeys", "Turn Sentry or Crashlytics telemetry into reproducible flows")
    row(journeys_card, "Telemetry", variables["telemetry"], True)
    ctk.CTkOptionMenu(journeys_card, variable=variables["source"],
                      values=["sentry", "crashlytics"]).pack(anchor="w", pady=3)
    journey_menu = ctk.CTkOptionMenu(journeys_card, variable=variables["journey"], values=["(none)"])
    journey_menu.pack(anchor="w", pady=3)
    journey_list = ctk.CTkTextbox(journeys_card, height=110, state="disabled")
    journey_list.pack(fill="x", pady=4)
    step_list = ctk.CTkTextbox(journeys_card, height=70, state="disabled")
    step_list.pack(fill="x", pady=4)

    def _load_sample():
        variables["telemetry"].set(str(sample_dir / "sentry.json"))
        variables["script"].set(str(sample_dir / "generated_test.py"))
        variables["hierarchy"].set(str(sample_dir / "sample_page_source.xml"))
        write_log("[C4] Loaded offline sample paths")

    def _show_journeys(result):
        nonlocal current_journeys
        if isinstance(result, Exception):
            variables["status"].set(f"Error: {result}")
            return
        current_journeys = result
        if result and result[0].error:
            variables["status"].set(f"Error: {result[0].error}")
            write_log(f"[C4] {result[0].error}")
            return
        ids = [item.id for item in result if item.id]
        journey_menu.configure(values=ids or ["(none)"])
        if ids:
            variables["journey"].set(ids[0])
        journey_list.configure(state="normal")
        journey_list.delete("1.0", "end")
        journey_list.insert("end", "\n".join(
            f"{item.id} | origin: {item.source} ({Path(item.source_file).name}) | session {item.session_id} | "
            f"app {item.app_version or '-'} | {item.failing_screen or '-'} | {item.steps} steps | "
            f"{'reproducible' if item.reproducible else 'not reproducible'} | "
            f"hints: {'; '.join(item.hints) or 'none'}"
            for item in result
        ))
        journey_list.configure(state="disabled")
        _show_steps()

    def _show_steps(*_):
        if not variables["journey"].get() or variables["journey"].get() == "(none)":
            return
        steps = controller.journey_steps(variables["journey"].get())
        step_list.configure(state="normal")
        step_list.delete("1.0", "end")
        step_list.insert("end", "\n".join(
            f"{step.index}: {step.action} {step.name} {step.locator}" for step in steps
        ))
        step_list.configure(state="disabled")

    journey_menu.configure(command=_show_steps)
    button(journeys_card, "Load sample", _load_sample, theme["warning"])
    button(journeys_card, "Create journeys", lambda: run_async(action_buttons,
        lambda: controller.create_journeys(variables["telemetry"].get(), variables["source"].get(), str(out_root / "journeys")),
        _show_journeys))
    button(journeys_card, "Export seed (for C1/C2)", lambda: _export_seed())

    def _export_seed():
        if variables["journey"].get() and variables["journey"].get() != "(none)":
            target = filedialog.asksaveasfilename(
                defaultextension=".json", initialfile="exported_seed.json",
                initialdir=str(out_root), filetypes=[("Journey seed", "*.json")])
            if not target:
                return
            path = controller.export_seed(variables["journey"].get(), target)
            variables["status"].set(path if path.startswith("ERROR") else "Seed exported")
            write_log(f"[C4] Seed: {path}")

    test = card("C  Test", "Generate locally, execute, and optionally heal the failing run")
    script_box = ctk.CTkTextbox(test, height=130, font=ctk.CTkFont(family="Consolas", size=10))
    script_box.pack(fill="x", pady=4)
    script_box.configure(state="disabled")
    button(test, "Generate test", lambda: run_async(action_buttons,
        lambda: controller.generate_test(variables["journey"].get(), variables["model"].get(),
            variables["ollama"].get(), c3_var.get(), variables["config"].get(), selected_c3()), _show_test))
    button(test, "Run on device", lambda: run_async(action_buttons,
        lambda: controller.run_test(
            variables["journey"].get(), variables["config"].get(), str(out_root / "runs"),
            model=variables["model"].get(), ollama_url=variables["ollama"].get(),
            use_c3=c3_var.get(), c3_verdict_id=selected_c3()), _show_run))
    ctk.CTkCheckBox(test, text="Run + heal", variable=heal_var).pack(side="left", padx=5)
    status_label(test)
    run_link = ctk.CTkLabel(test, text="", text_color=theme["primary"])
    run_link.pack(anchor="w")

    def _show_test(result):
        c3_note = ""
        if c3_var.get():
            c3_note = f" | C3: {result.c3_status}" + (f" ({result.c3_verdict_id})" if result.c3_verdict_id else "")
        variables["status"].set(f"Test: {result.status}{c3_note}" + (f" - {result.error}" if result.error else ""))
        script_box.configure(state="normal")
        script_box.delete("1.0", "end")
        script_box.insert("end", result.script or result.error or "")
        script_box.configure(state="disabled")

    def _show_run(result):
        variables["status"].set(
            f"Run: {result.status} ({result.failure_kind or result.error or 'no failure'})")
        run_link.configure(text=result.run_folder or result.error or "")
        if heal_var.get() and result.execution_result is not None and result.execution_result.failure is not None:
            try:
                threshold = heal_threshold()
            except ValueError as error:
                variables["status"].set(f"Error: {error}")
                return
            run_async(action_buttons, lambda: controller.heal_last_failure(
                result, "lexical", threshold, verify=True, config_path=variables["config"].get()), _show_heal)

    healing = card("D  Healing result", "Auditable confidence, narrowing, candidates, diff, and versions")
    healing_box = ctk.CTkTextbox(healing, height=190, state="disabled", font=ctk.CTkFont(family="Consolas", size=10))
    healing_box.pack(fill="x")

    def _show_heal(result):
        if result.error:
            text = result.error
        elif result.verified:
            outcome = f"VERIFIED: re-execution passed (versions {result.versions})"
        elif result.rerun_status in (None, "not_run"):
            outcome = "SUGGESTED ONLY: not applied and not verified by re-execution"
        else:
            outcome = f"NOT VERIFIED: {result.rerun_status}" + (f" ({result.reason})" if result.reason else "")
        text = result.error or (
            f"{outcome}\n"
            f"{result.status}: {result.original_locator} -> {result.healed_locator}\n"
            f"confidence={result.confidence} threshold={result.threshold} margin={result.margin}\n"
            f"candidates={result.candidates_total} -> {result.candidates_after_narrowing}\n"
            f"rules={result.rule_counts}\n\n{result.healed_script_diff}"
        )
        healing_box.configure(state="normal")
        healing_box.delete("1.0", "end")
        healing_box.insert("end", text)
        healing_box.configure(state="disabled")

    offline = card("E  Offline healing demo", "No device or LLM required")
    row(offline, "Script", variables["script"], True)
    row(offline, "Step index", variables["step"])
    row(offline, "New hierarchy", variables["hierarchy"], True)
    row(offline, "Baseline (optional)", variables["baseline"], True)
    button(offline, "Load sample", _load_sample, theme["warning"])
    button(offline, "Heal (no device)", lambda: run_async(action_buttons,
        lambda: controller.offline_heal(variables["script"].get(), int(variables["step"].get()),
            variables["hierarchy"].get(), variables["baseline"].get() or None, "lexical"), _show_heal))

    logs = card("F  Log", "Panel messages are also sent to the shared HEART log")
    log_box = ctk.CTkTextbox(logs, height=80, state="disabled", font=ctk.CTkFont(family="Consolas", size=10))
    log_box.pack(fill="x")

    def _show_preflight(result):
        if isinstance(result, Exception):
            variables["status"].set(f"Error: {result}")
            return
        variables["status"].set("Preflight complete")
        preflight_chips.configure(text="  ".join(
            f"{name}: {'OK' if value else 'NO'}"
            for name, value in [("ADB", result.adb), ("Device", result.device),
                                ("Appium", result.appium), ("Package", result.package),
                                ("Ollama", result.ollama), ("C3", result.c3)]
        ))
        for problem in result.problems:
            write_log(f"[C4] {problem}")

    inbox_card = card('Inspection inbox', 'Visual findings received from screen inspection')
    inbox_status = ctk.CTkLabel(inbox_card, text='No inspection received in this session.', wraplength=520, justify='left')
    inbox_status.pack(anchor='w', pady=6)
    inbox_preview = ctk.CTkTextbox(inbox_card, height=150)
    inbox_preview.pack(fill='x')
    inbox_preview.configure(state='disabled')
    def receive_inspection(payload):
        import json
        from vision_oracle.core.config import C3_DIR
        receipt = controller.receive_inspection(payload, C3_DIR / 'results' / 'c4_inbox')
        refresh_c3_evidence()
        inbox_status.configure(text='Received: ' + receipt['verdict_id'] + '\nEvidence saved. Select it in "Use C3 verdict context" (Setup) to attach it to a journey.')
        inbox_preview.configure(state='normal')
        inbox_preview.delete('1.0', 'end')
        inbox_preview.insert('1.0', json.dumps(payload, indent=2))
        inbox_preview.configure(state='disabled')
        return receipt
    root.c4_receive_inspection = receive_inspection

    return parent
