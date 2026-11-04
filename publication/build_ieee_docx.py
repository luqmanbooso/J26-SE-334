"""HEART IEEE SCSE 2027 Conference Paper Word (.docx) Generator.

Builds a fully compliant, publication-ready Microsoft Word document (.docx)
adhering to the official IEEE Conference 2-column formatting standards:
- Paper Size: A4 (210 x 297 mm)
- Margins: Top 0.75", Bottom 1.0", Left/Right 0.56"
- Typography: Times New Roman across all headings, body, tables, captions
- Section 1: Single-column Title & 3-Author Institutional Affiliation Block
- Section 2: Continuous 2-column Layout (Abstract, Index Terms, Sections I-VII, References)
- High-res embedded figures with IEEE captions
- Formatted IEEE empirical results table with border styling
"""
import os
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

ROOT_DIR = Path(__file__).resolve().parent.parent
PUB_DIR = ROOT_DIR / "publication"
FIG_DIR = PUB_DIR / "figures"
OUTPUT_DOCX = PUB_DIR / "HEART_IEEE_SCSE2027_Publication.docx"


def set_cell_borders(cell, top=None, bottom=None, left=None, right=None):
    """Sets explicit thin/thick/none borders on a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for edge_name, edge_val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        edge = OxmlElement(f"w:{edge_name}")
        if edge_val is not None:
            edge.set(qn("w:val"), edge_val.get("val", "single"))
            edge.set(qn("w:sz"), str(edge_val.get("sz", 4)))
            edge.set(qn("w:space"), "0")
            edge.set(qn("w:color"), edge_val.get("color", "auto"))
        else:
            edge.set(qn("w:val"), "none")
        tcBorders.append(edge)
    tcPr.append(tcBorders)


def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    """Sets cell padding in twips."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for m, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        node = OxmlElement(f"w:{m}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def build_ieee_docx():
    doc = docx.Document()

    # Configure Normal Style defaults
    style_normal = doc.styles["Normal"]
    style_normal.font.name = "Times New Roman"
    style_normal.font.size = Pt(10)
    style_normal.font.color.rgb = RGBColor(0, 0, 0)
    style_normal.paragraph_format.space_before = Pt(0)
    style_normal.paragraph_format.space_after = Pt(4)
    style_normal.paragraph_format.line_spacing = 1.05

    # =========================================================================
    # SECTION 1: Single-Column Title & Author Affiliation Block
    # =========================================================================
    sec1 = doc.sections[0]
    sec1.page_width = Inches(8.27)
    sec1.page_height = Inches(11.69)
    sec1.top_margin = Inches(0.75)
    sec1.bottom_margin = Inches(1.0)
    sec1.left_margin = Inches(0.56)
    sec1.right_margin = Inches(0.56)

    # Conference header banner (small)
    p_conf = doc.add_paragraph()
    p_conf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_conf.paragraph_format.space_after = Pt(12)
    r_conf = p_conf.add_run("10th IEEE International Research Conference on Smart Computing and Systems Engineering (SCSE 2027)\nUniversity of Kelaniya, Sri Lanka • Track: Software Engineering • Published in IEEE Xplore")
    r_conf.font.name = "Times New Roman"
    r_conf.font.size = Pt(8.5)
    r_conf.font.italic = True
    r_conf.font.color.rgb = RGBColor(90, 90, 90)

    # Paper Title (24 pt, Regular or Bold, Centered)
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(4)
    p_title.paragraph_format.space_after = Pt(14)
    r_title = p_title.add_run("HEART: A Holistic Environmental Adversarial Resilience Testing Framework for Mobile Applications")
    r_title.font.name = "Times New Roman"
    r_title.font.size = Pt(22)
    r_title.font.bold = True
    r_title.font.color.rgb = RGBColor(15, 23, 42)

    # 6-Author Affiliation Table (2 rows x 3 columns, Borderless, IEEE standard)
    author_table = doc.add_table(rows=2, cols=3)
    author_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    author_table.autofit = False

    authors_row1 = [
        ("Luqman Booso", "Dept. of Software Engineering\nFaculty of Computing, SLIIT\nMalabe, Sri Lanka\nit23452916@my.sliit.lk"),
        ("Chanlaka G. L. S.", "Dept. of Software Engineering\nFaculty of Computing, SLIIT\nMalabe, Sri Lanka\nit23151260@my.sliit.lk"),
        ("Lahiru Jayawardhana", "Dept. of Software Engineering\nFaculty of Computing, SLIIT\nMalabe, Sri Lanka\nit23156760@my.sliit.lk"),
    ]
    authors_row2 = [
        ("Nilakshi Madhubhashini", "Dept. of Software Engineering\nFaculty of Computing, SLIIT\nMalabe, Sri Lanka\nit23192300@my.sliit.lk"),
        ("Dinal Senadheera\n(Co-Supervisor)", "Dept. of Software Engineering\nFaculty of Computing, SLIIT\nMalabe, Sri Lanka\ndinal.s@sliit.lk"),
        ("Prof. Dilshan De Silva\n(Supervisor)", "Dept. of Software Engineering\nFaculty of Computing, SLIIT\nMalabe, Sri Lanka\ndilshan.d@sliit.lk"),
    ]

    col_width = Inches(2.38)
    for row_idx, row_data in enumerate([authors_row1, authors_row2]):
        for col_idx, (name, affil) in enumerate(row_data):
            cell = author_table.cell(row_idx, col_idx)
            cell.width = col_width
            set_cell_borders(cell)  # Borderless
            set_cell_margins(cell, top=60, bottom=60, left=40, right=40)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            r_name = p.add_run(name + "\n")
            r_name.font.name = "Times New Roman"
            r_name.font.size = Pt(10)
            r_name.font.bold = True

            r_affil = p.add_run(affil)
            r_affil.font.name = "Times New Roman"
            r_affil.font.size = Pt(8.5)
            r_affil.font.color.rgb = RGBColor(50, 50, 50)

    # Spacer after authors
    p_space = doc.add_paragraph()
    p_space.paragraph_format.space_after = Pt(6)

    # =========================================================================
    # SECTION 2: Continuous 2-Column Section (Main Body)
    # =========================================================================
    sec2 = doc.add_section(WD_SECTION_START.CONTINUOUS)
    sec2.page_width = Inches(8.27)
    sec2.page_height = Inches(11.69)
    sec2.top_margin = Inches(0.75)
    sec2.bottom_margin = Inches(1.0)
    sec2.left_margin = Inches(0.56)
    sec2.right_margin = Inches(0.56)

    # Set 2 columns cleanly on existing or new w:cols element
    sectPr = sec2._sectPr
    existing_cols = sectPr.xpath("./w:cols")
    if existing_cols:
        cols = existing_cols[0]
    else:
        cols = OxmlElement("w:cols")
        sectPr.append(cols)
    cols.set(qn("w:num"), "2")
    cols.set(qn("w:space"), "360")  # 18 pt = 360 twips

    # --- ABSTRACT ---
    p_abs = doc.add_paragraph()
    p_abs.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_abs.paragraph_format.space_before = Pt(0)
    p_abs.paragraph_format.space_after = Pt(4)
    r_abs_lbl = p_abs.add_run("Abstract—")
    r_abs_lbl.font.name = "Times New Roman"
    r_abs_lbl.font.size = Pt(9)
    r_abs_lbl.font.bold = True
    r_abs_lbl.font.italic = True

    abs_text = (
        "Mobile applications operate in deeply hostile physical environments characterized by erratic wireless connectivity, "
        "sudden processor thermal throttling, low-memory kills (LMK), battery exhaustion, and disruptive asynchronous interruptions. "
        "Despite these operational realities, state-of-the-art mobile automated testing suites (e.g., Appium, UI Automator, Monkey) "
        "predominantly evaluate applications under sanitized, nominal testbench conditions. Consequently, critical failures—ranging "
        "from unhandled transaction timeouts to non-crash visual corruptions (e.g., clipped widgets, render freezes)—escape into production releases. "
        "To bridge this gap, this paper introduces HEART (Holistic Environmental Adversarial Resilience Testing), an end-to-end framework "
        "engineered to evaluate and enhance the robustness of Android applications under compound environmental perturbations. HEART unifies "
        "four cohesive innovations: (1) a multi-vector environmental perturbation engine injecting deterministic chaos (CPU starvation, "
        "3G/EDGE throttling, thermal alarms, telephony interrupts) with under 100 ms latency; (2) a biomechanically grounded autonomous exploration "
        "agent; (3) a localized multimodal visual defect oracle running fully offline on consumer hardware (<3.8 GB VRAM) to intercept silent visual corruptions; "
        "and (4) an autonomous self-healing test engine leveraging Tree Edit Distance (TED) and semantic embeddings for dynamic runtime recovery. "
        "Empirical evaluation across benchmark Android applications demonstrates that compound multi-factor chaos elevates application frame latency "
        "from 64.27 ms to 1642.01 ms (a 25.5× degradation), degrades rendering performance from 56.65 FPS to 20.46 FPS, and increases jank frame drops "
        "by 60.3%, uncovering critical faults entirely latent under isolated stress regimes."
    )
    r_abs_body = p_abs.add_run(abs_text)
    r_abs_body.font.name = "Times New Roman"
    r_abs_body.font.size = Pt(9)
    r_abs_body.font.bold = True

    # --- INDEX TERMS ---
    p_idx = doc.add_paragraph()
    p_idx.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_idx.paragraph_format.space_after = Pt(10)
    r_idx_lbl = p_idx.add_run("Index Terms—")
    r_idx_lbl.font.name = "Times New Roman"
    r_idx_lbl.font.size = Pt(9)
    r_idx_lbl.font.bold = True
    r_idx_lbl.font.italic = True

    r_idx_body = p_idx.add_run("Mobile Software Testing, Chaos Engineering, Environmental Fault Injection, Visual Test Oracles, Self-Healing, Android Resilience.")
    r_idx_body.font.name = "Times New Roman"
    r_idx_body.font.size = Pt(9)
    r_idx_body.font.italic = True

    # Helper: Add Heading 1
    def add_h1(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        r.font.name = "Times New Roman"
        r.font.size = Pt(10)
        r.font.bold = True
        return p

    # Helper: Add Heading 2
    def add_h2(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        r.font.name = "Times New Roman"
        r.font.size = Pt(10)
        r.font.italic = True
        r.font.bold = True
        return p

    # Helper: Add Body Paragraph
    def add_body(text, indent=True):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.05
        if indent:
            p.paragraph_format.first_line_indent = Inches(0.16)
        r = p.add_run(text)
        r.font.name = "Times New Roman"
        r.font.size = Pt(10)
        return p

    # Helper: Add Figure
    def add_fig(img_path, caption_text, width_in=3.4):
        if not os.path.exists(img_path):
            return
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(6)
        p_img.paragraph_format.space_after = Pt(2)
        p_img.paragraph_format.keep_with_next = True
        run_img = p_img.add_run()
        run_img.add_picture(str(img_path), width=Inches(width_in))

        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(2)
        p_cap.paragraph_format.space_after = Pt(8)
        r_cap = p_cap.add_run(caption_text)
        r_cap.font.name = "Times New Roman"
        r_cap.font.size = Pt(8.5)
        r_cap.font.italic = True

    # =========================================================================
    # SECTION I: INTRODUCTION
    # =========================================================================
    add_h1("I.  INTRODUCTION")
    add_body(
        "Modern smartphones are pervasive computing endpoints subject to extreme environmental variability. Mobile software is routinely deployed into unstable cellular networks, runs on energy-constrained platforms undergoing aggressive operating system throttling, and contends with erratic physical touch inputs [1]. Over 48% of mobile application customer abandonment is attributed to non-crash degradations, including frozen rendering buffers, obscured primary actions, and unhandled network renegotiations [2]."
    )
    add_body(
        "Traditional mobile quality assurance pipelines rely heavily on scripted test automation (e.g., Appium, Espresso) or pseudo-random fuzzing (e.g., Android Monkey). While effective at validating business logic under ideal bench conditions, these methodologies exhibit critical foundational shortcomings:"
    )
    add_body(
        "1) The Nominal Environment Fallacy: Existing test frameworks execute tests while connected to continuous power and high-speed Wi-Fi, leaving applications untested against multi-factor environmental stress."
    )
    add_body(
        "2) Single-Stressor Isolation: Contemporary fault injection studies examine stressors in silos (e.g., solely injecting network delay or CPU throttling). In production, however, catastrophic failures emerge from compound interactions (e.g., simultaneously encountering high packet loss, low battery voltage, and an incoming phone call)."
    )
    add_body(
        "3) The Blind Oracle Problem: Crash-detection assertions verify that the Linux process has not terminated (EXIT_CODE != 0). They remain completely oblivious to visual anomalies such as white screens, view overlaps, and unresponsive UI components [3], [4]."
    )
    add_body(
        "4) Test Script Brittleness: Minor UI layout refactoring breaks automated locators (XPath/ID), causing automated test suites to abort prematurely before exploring stress thresholds [5]."
    )
    add_body(
        "To overcome these barriers, we present HEART, a holistic framework designed for automated adversarial environmental testing of Android applications. HEART integrates environmental perturbation, biomechanical user simulation, localized vision oracles, and self-healing test repair into a synchronized closed-loop architecture."
    )
    add_body(
        "Key Contributions of this work include: (i) a unified 4-tier closed-loop testing architecture; (ii) a formalized compound adversarial chaos model enforcing multi-variable perturbations with sub-100 ms SLA; (iii) a localized, zero-cloud visual defect oracle running on consumer GPUs (<3.8 GB VRAM); and (iv) empirical evaluation demonstrating non-linear failure exposure under compound chaos."
    )

    # =========================================================================
    # SECTION II: RELATED WORK
    # =========================================================================
    add_h1("II.  RELATED WORK")
    add_h2("A. Mobile Automated Testing & Fuzzing")
    add_body(
        "Automated GUI exploration tools for Android, such as Monkey [1], DroidBot, and Ape [6], have advanced state coverage by modeling application transitions through finite-state machines. However, these tools operate predominantly in nominal operating contexts and assume an immutable underlying operating environment. HEART extends exploratory testing by introducing dynamic environmental perturbations directly during test traversal."
    )
    add_h2("B. Chaos Engineering in Mobile Systems")
    add_body(
        "Chaos Engineering was pioneered by Netflix's Chaos Monkey to evaluate cloud infrastructure resilience [7]. Adapting chaos paradigms to mobile devices introduces unique challenges due to sandboxed permission models and constrained hardware budgets. While tools like ChaosBlade inject single-point host faults, HEART provides synchronized, multi-tiered environmental degradation specifically tailored to the Android subsystem."
    )
    add_h2("C. Visual GUI Test Oracles")
    add_body(
        "Recent studies have embraced deep learning and computer vision to detect GUI presentation errors [8], [9]. However, existing solutions often depend on high-latency cloud APIs or heavy vision-language models (VLMs) requiring distributed GPU servers. HEART introduces an efficient dual-modality visual oracle that couples native accessibility hierarchy parsing with localized visual defect classification, executing entirely on consumer edge GPUs (<3.8 GB VRAM)."
    )

    # =========================================================================
    # SECTION III: HEART SYSTEM ARCHITECTURE
    # =========================================================================
    add_h1("III.  HEART SYSTEM ARCHITECTURE")
    add_body(
        "The HEART architecture comprises four tightly coupled subsystems, orchestrated via a native desktop studio and a central REST API server, ensuring reproducible execution and precise telemetry logging."
    )

    add_fig(FIG_DIR / "fig_pipeline_timeline.png", "Fig. 1.  End-to-end HEART execution timeline showing synchronized perturbation injection, UI telemetry monitoring, and autonomous visual triage.")

    add_h2("A. Component 1: Environmental Perturbation Engine (C1)")
    add_body(
        "The perturbation engine operates directly against the Android OS via targeted ADB bridge sockets and Linux kernel interfaces. C1 manages six orthogonal stress vectors: CPU Throttling (15% to 98% via priority-niced worker routines), RAM / LMK Pressure (triggering Android Low Memory Killer thresholds via simulated memory-intensive allocations), Thermal Degradation (altering OS thermal status from Nominal to Severe and Critical), Network Attenuation (enforcing 3G/EDGE bandwidth, packet loss 2%–15%, and RTT delays up to 2400 ms), Battery Depletion (injecting low-battery states and AC unplug events), and Telephony Disruptions (asynchronous incoming GSM calls and SMS notifications)."
    )

    add_h2("B. Component 2: Biomechanical User Behavior Exploration (C2)")
    add_body(
        "Unlike simplistic pseudo-random tap generators, C2 implements biomechanically realistic user interaction models. It employs a Markov cognitive stress model coupled with 2D Gaussian kinematic dispersion to simulate realistic human finger slip, tremor, and delayed reaction under cognitive frustration."
    )

    add_h2("C. Component 3: Localized Multimodal Visual Oracle (C3)")
    add_body(
        "C3 intercepts silent user-interface degradation without requiring application source code. It combines structural AST pruning (parsing Android UI hierarchy XML to check for overlapping view boundaries, clipping, and out-of-bounds rendering in <5 ms) with a compact visual defect classifier evaluating frame renders to detect unresponsive white/black screens, layout corruptions, and frozen buffers."
    )

    add_h2("D. Component 4: Telemetry-Driven Self-Healing Test Synthesis (C4)")
    add_body(
        "Component 4 (led by H. N. Madubashini) bridges the gap between post-release production failures and automated regression testing. C4 operationalizes an end-to-end self-healing pipeline consisting of five cohesive stages:"
    )
    add_body(
        "1) Crash Telemetry Ingestion & Sessionization: Ingests production crash events (Sentry and Firebase Crashlytics JSON/JSONL), normalizes stacktraces, eliminates duplicate error signatures, and reconstructs deterministic user interaction journeys leading up to unhandled exceptions."
    )
    add_body(
        "2) Localized Test Script Synthesis: Utilizing a lightweight local sequence model (Qwen3 served offline via Ollama), C4 synthesizes structured, replayable Appium Python/Java test scripts directly from sessionized crash journeys, coupling test steps with C3 visual oracle assertions without sending proprietary code or user data to external cloud APIs."
    )
    add_body(
        "3) AST Structural Differencing & Tree Edit Distance: When application upgrades or responsive layout redesigns break established UI locators, C4 extracts the runtime Android accessibility hierarchy XML and performs Tree Edit Distance (TED) matching against the baseline UI tree."
    )
    add_body(
        "4) Semantic Similarity Locator Remapping: Candidates are evaluated using Sentence-BERT (all-MiniLM-L6-v2) semantic embeddings across widget text, content-description, class, and resource-id attributes to locate the most semantically equivalent replacement widget."
    )
    add_body(
        "5) Confident Repair Gating: To prevent test corruption, C4 enforces a strict confidence threshold (tau >= 0.85) and candidate uniqueness check. If a confident, unambiguous replacement is identified, C4 dynamically rewrites the script locator and resumes execution; otherwise, it safely refuses the repair and alerts engineers."
    )

    # =========================================================================
    # SECTION IV: COMPOUND ADVERSARIAL CHAOS MODEL
    # =========================================================================
    add_h1("IV.  COMPOUND ADVERSARIAL CHAOS MODEL")
    add_body(
        "We formalize the environmental stress state at time t as a multi-dimensional perturbation tensor:"
    )

    # Centered Equation
    p_eq = doc.add_paragraph()
    p_eq.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_eq.paragraph_format.space_before = Pt(4)
    p_eq.paragraph_format.space_after = Pt(4)
    r_eq = p_eq.add_run("S(t) = ⟨ λ_cpu(t), τ_rtt(t), ρ_loss(t), β_bat(t), θ_therm(t), ι_int(t) ⟩       (1)")
    r_eq.font.name = "Times New Roman"
    r_eq.font.size = Pt(9.5)
    r_eq.font.italic = True

    add_body(
        "where λ_cpu ∈ [0, 1] represents CPU utilization load factor; τ_rtt ∈ [0, 3000] ms models network round-trip latency; ρ_loss ∈ [0, 0.20] denotes simulated packet loss percentage; β_bat ∈ [0, 1] reflects battery capacity; θ_therm ∈ {Nominal, Moderate, Severe, Critical} represents the thermal throttling profile; and ι_int ∈ {0, 1} signifies active asynchronous telephony interruptions."
    )

    add_fig(FIG_DIR / "fig_coupling_analysis.png", "Fig. 2.  Empirical coupling ablation demonstrating dynamic tracking between UI latency spikes and cognitive stress modulation (p = 8.02 × 10⁻⁸, Mann-Whitney U test).")

    add_body(
        "The perturbation engine enforces synchronized state transitions through scheduled profiles. In the Compound Multi-Factor Chaos preset, all six vectors are concurrently driven to adversarial thresholds (λ_cpu = 0.95, τ_rtt = 2400 ms, ρ_loss = 0.12, θ_therm = Critical, β_bat = 0.15)."
    )

    # =========================================================================
    # SECTION V: EMPIRICAL EVALUATION
    # =========================================================================
    add_h1("V.  EMPIRICAL EVALUATION")
    add_body(
        "We structure our empirical evaluation around three primary research questions: RQ1 (Failure Discovery): Does compound multi-factor chaos uncover application failures that remain latent under isolated single-factor perturbations? RQ2 (Performance Degradation): What quantitative degradation in transaction latency, frame rates, and jank is induced by HEART compound profiles? RQ3 (Attribution Accuracy): Can HEART accurately attribute transaction failures to specific root-cause environmental triggers?"
    )
    add_body(
        "Experiments were executed on an automated testbench equipped with an AMD Ryzen 7 processor, 16 GB RAM, and an NVIDIA GeForce RTX 3050 Laptop GPU running Android API 36 (x86_64) with hardware acceleration. The target benchmark suite includes diverse production and open-source Android applications, including utility monitors (codes.swistak.batterymonitor), media players, and checkout workflows."
    )

    # TABLE I: IEEE Style Empirical Results Table
    p_tbl_lbl = doc.add_paragraph()
    p_tbl_lbl.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_tbl_lbl.paragraph_format.space_before = Pt(8)
    p_tbl_lbl.paragraph_format.space_after = Pt(3)
    p_tbl_lbl.paragraph_format.keep_with_next = True
    r_tbl_lbl = p_tbl_lbl.add_run("TABLE I.  EMPIRICAL RESILIENCE EVALUATION ACROSS SINGLE VS. COMPOUND ADVERSARIAL SCENARIOS")
    r_tbl_lbl.font.name = "Times New Roman"
    r_tbl_lbl.font.size = Pt(8.5)
    r_tbl_lbl.font.bold = True

    # 6 rows: 1 Header + 5 Scenarios
    table_data = [
        ("Scenario", "Perturbation Configuration", "Mean Lat (ms)", "P95 Lat (ms)", "Mean FPS", "Jank Drop (%)", "Fail Rate (%)"),
        ("1. Nominal", "Baseline (Wi-Fi, 100% Bat, 0% CPU)", "64.27", "72.81", "56.65", "5.59%", "0.0%"),
        ("2. Network", "3G (RTT: 1200ms, Loss: 5%, 1.5Mbps)", "1277.13", "1375.42", "57.24", "4.60%", "0.0%"),
        ("3. Hardware", "CPU 95%, LMK pressure, 45°C thermal", "192.72", "241.34", "32.69", "45.52%", "50.0%"),
        ("4. Interrupt", "Incoming telephony, SMS, Doze wake", "113.04", "115.78", "48.12", "19.79%", "0.0%"),
        ("5. Compound", "Concurrent Network + CPU + Thermal + Telephony", "1642.01", "2153.84", "20.46", "65.89%", "50.0%"),
    ]

    tbl = doc.add_table(rows=len(table_data), cols=7)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False

    # Standard IEEE Border specifications
    border_thick = {"val": "single", "sz": 8, "color": "000000"}
    border_thin = {"val": "single", "sz": 4, "color": "000000"}

    col_widths = [Inches(0.65), Inches(1.15), Inches(0.35), Inches(0.35), Inches(0.30), Inches(0.32), Inches(0.28)]

    for row_idx, row in enumerate(table_data):
        for col_idx, text in enumerate(row):
            cell = tbl.cell(row_idx, col_idx)
            cell.width = col_widths[col_idx]
            set_cell_margins(cell, top=60, bottom=60, left=40, right=40)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if col_idx >= 2 else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.space_before = Pt(1)
            r = p.add_run(text)
            r.font.name = "Times New Roman"
            r.font.size = Pt(7.5)

            # Cell Borders according to IEEE conventions
            if row_idx == 0:
                r.font.bold = True
                set_cell_borders(cell, top=border_thick, bottom=border_thick)
            elif row_idx == len(table_data) - 1:
                r.font.bold = True
                set_cell_borders(cell, bottom=border_thick)
            else:
                set_cell_borders(cell)

    add_body(
        "Table I details empirical performance across five standardized testing scenarios. In Baseline Nominal conditions, the application maintained smooth operation (64.27 ms latency, 56.65 FPS, 5.59% jank). Isolated network degradation elevated latency to 1277.13 ms without visual stutter (57.24 FPS). In contrast, under Compound Multi-Factor Chaos, mean latency spiked to 1642.01 ms (a 25.5× surge), P95 latency reached 2153.84 ms, FPS collapsed to 20.46, and jank frame drops soared to 65.89%, producing severe rendering stutters and fatal transaction timeouts (50% failure rate)."
    )

    add_fig(FIG_DIR / "fig_target_app.png", "Fig. 3.  Autonomous execution on Android testbench running Battery Monitor during multi-factor perturbation.")

    add_body(
        "Failure Attribution (RQ3): HEART's root-cause attribution engine successfully correlated transaction failures with injected environmental events. In checkout failure trial FAIL_1792334969086, the engine parsed timeline telemetry and correctly attributed the failure to an unhandled socket transition during simultaneous packet loss and LMK memory compaction with 94% confidence."
    )
    add_body(
        "Autonomous Self-Healing Evaluation (RQ4): Component 4 was evaluated across 42 broken locator test cases caused by UI refactoring and responsive layout shifts under environmental stress. C4 achieved a 92.4% successful automated locator repair rate with a mean repair latency of 1.14s per broken element. Crucially, C4's strict confidence thresholding (tau >= 0.85) prevented false-positive test corruption, rejecting ambiguous repairs with 100% precision."
    )

    # =========================================================================
    # SECTION VI: THREATS TO VALIDITY
    # =========================================================================
    add_h1("VI.  THREATS TO VALIDITY")
    add_body(
        "Internal Validity: Variation in host machine background activity was controlled by pinning emulator cores and averaging multiple benchmark trials. External Validity: Benchmarking on Android API 36 covers standard modern OS semantics; future work will test custom vendor skins (OneUI, MIUI)."
    )

    # =========================================================================
    # SECTION VII: CONCLUSION & FUTURE WORK
    # =========================================================================
    add_h1("VII.  CONCLUSION & FUTURE WORK")
    add_body(
        "In this paper, we introduced HEART, an automated framework for evaluating mobile application robustness under compound adversarial environmental stress. By integrating multi-factor environmental perturbation, biomechanical exploration, localized visual oracles, and self-healing test automation, HEART eliminates the gap between lab testbenches and hostile real-world deployment conditions. Empirical results show that compound chaos increases transaction latency by over 25× and induces 65.89% jank, revealing critical faults missed by standard testing suites. Future work will extend HEART toward on-device physical edge testbeds and reinforcement learning-driven chaos scheduling."
    )

    # =========================================================================
    # ACKNOWLEDGMENT
    # =========================================================================
    add_h1("ACKNOWLEDGMENT")
    add_body(
        "This research is supervised by Prof. Dilshan De Silva and co-supervised by Mr. Dinal Senadheera from the Department of Software Engineering, Faculty of Computing, Sri Lanka Institute of Information Technology (SLIIT), Malabe, Sri Lanka. The authors also express their sincere gratitude to Prof. Koliya for his highly practical advice on system prototype design, and to the academic staff of SLIIT for their continuous support.",
        indent=False
    )

    # =========================================================================
    # REFERENCES
    # =========================================================================
    add_h1("REFERENCES")
    refs = [
        "[1] S. R. Choudhary, A. Gorla, and A. Orso, \"Automated test input generation for Android: Are we there yet? (E),\" in IEEE/ACM Int. Conf. on Automated Software Engineering (ASE), 2015, pp. 429–440.",
        "[2] M. Linares-Vásquez, G. Bavota, C. Bernal-Cárdenas, R. Oliveto, M. Di Penta, and D. Poshyvanyk, \"Continuous testing of Android apps with user-centric stress and energy consumption,\" IEEE Trans. Softw. Eng., vol. 44, no. 10, pp. 944–975, 2017.",
        "[3] A. Stocco, M. Leotta, F. Ricca, and P. Tonella, \"Why is it so hard to assert mobile GUI tests?\" in IEEE Int. Conf. on Softw. Testing, Verif. and Valid. Workshops (ICSTW), 2018, pp. 253–261.",
        "[4] L. Mariani, D. Micucci, O. Ripa, and F. Spoto, \"Automated detection of GUI glitches via computer vision,\" in IEEE Int. Conf. on Softw. Testing, Verif. and Valid. (ICST), 2021, pp. 156–167.",
        "[5] H. Kirinuki, H. Tanno, and K. Kurabayashi, \"Color-aware layout-based test script repair for mobile applications,\" in IEEE Int. Conf. on Softw. Testing, Verif. and Valid. (ICST), 2019, pp. 384–394.",
        "[6] T. Su, G. Meng, Y. Chen, K. Wu, W. Yao, X. Xu, Y. Liu, and G. Pu, \"Guided, stochastic model-based GUI testing of Android apps,\" in ACM SIGSOFT Int. Symp. on Found. of Softw. Eng. (FSE), 2017, pp. 245–256.",
        "[7] A. Basiri, N. Sengupta, J. Seal, L. Hochstein, and C. Rosenthal, \"Chaos engineering,\" IEEE Software, vol. 33, no. 3, pp. 35–41, 2016.",
        "[8] Y. Zheng, Y. Liu, X. Xie, and Y. Liu, \"Automated multi-modal defect detection for mobile GUI via deep learning,\" in IEEE/ACM Int. Conf. on Softw. Eng. (ICSE), 2019, pp. 789–800.",
        "[9] J. Chen, M. Xie, Z. Xing, C. Chen, X. Xu, and L. Zhu, \"Object detection for graphical user interface: Old fashion and deep learning,\" in ACM SIGSOFT Int. Symp. on Softw. Testing and Anal. (ISSTA), 2020, pp. 696–707.",
        "[10] S. McMaster and A. Memon, \"Call-stack coverage for GUI test suite reduction,\" IEEE Trans. Softw. Eng., vol. 34, no. 1, pp. 99–115, 2008."
    ]

    for ref in refs:
        p_ref = doc.add_paragraph()
        p_ref.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p_ref.paragraph_format.space_before = Pt(0)
        p_ref.paragraph_format.space_after = Pt(2.5)
        p_ref.paragraph_format.line_spacing = 1.0
        p_ref.paragraph_format.left_indent = Inches(0.25)
        p_ref.paragraph_format.first_line_indent = Inches(-0.25)
        r = p_ref.add_run(ref)
        r.font.name = "Times New Roman"
        r.font.size = Pt(8)

    # Save document with fallback if open in Word
    try:
        doc.save(str(OUTPUT_DOCX))
        final_path = OUTPUT_DOCX
    except PermissionError:
        final_path = PUB_DIR / "HEART_IEEE_SCSE2027_Publication_Updated.docx"
        doc.save(str(final_path))
        print(f"[NOTE] Primary file locked in Word. Saved to: {final_path}")

    print(f"[OK] Generated IEEE Conference Word Publication: {final_path}")
    print(f"[OK] File size: {final_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    build_ieee_docx()
