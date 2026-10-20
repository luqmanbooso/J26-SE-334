# HEART C4 five-minute demo

This script demonstrates the new **Self-Healing (C4)** tab. The offline path
does not require ADB, Appium, Ollama, or a model.

## Offline path (about three minutes)

1. From the repository root, run `pip install -e "component4[ui]"`.
2. Run `python heart_desktop_app.py`.
3. Click **Self-Healing (C4)** in the top tab strip.
4. In **E Offline healing demo**, click **Load sample**.
5. Click **Heal (no device)**. The result should read **healed**, with the
   original `Network and internet` locator changed to the real Settings
   hierarchy label `Network & internet`.
6. Point out the confidence/threshold, the candidate narrowing counts, the
   top candidates, rule counts, and the unified script diff.
7. Click **Load sample** in **B Journeys**, then click **Create journeys**.
   Select the displayed journey and click **Export seed (for C1/C2)**.
8. Click **Generate test (dry run)** only when a local Ollama service is
   available; the offline healing card is the no-LLM demo.

## Live path with an emulator (about two minutes)

1. Start an Android emulator and Appium server at
   `http://127.0.0.1:4723`; ensure the target JSON points at the installed
   package and activity.
2. In **A Setup**, click **Browse** beside **Target config**, select the JSON
   target configuration, choose the model and Ollama URL, and click
   **Preflight**. Explain the ADB, Device, Appium, Package, Ollama, and C3
   status chips.
3. In **B Journeys**, select a telemetry file and source, then click
   **Create journeys** and select a journey.
4. In **C Test**, click **Generate test**, review the read-only script, and
   click **Run on device**.
5. Turn on **Run + heal** before clicking **Run on device** for a failed
   locator. The **D Healing result** card shows whether the repair was healed,
   refused, or not applicable, and the run folder link identifies the
   persisted artifacts.

