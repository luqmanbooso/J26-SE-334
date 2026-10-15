import os
import json

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

def create_postman_files():
    # =========================================================================
    # 1. ENVIRONMENT CONFIGURATION
    # =========================================================================
    environment = {
        "id": "heart-env-v1",
        "name": "HEART Engine Environment (Localhost)",
        "values": [
            {
                "key": "baseUrl",
                "value": "http://127.0.0.1:8001",
                "type": "default",
                "enabled": True
            },
            {
                "key": "authToken",
                "value": "",
                "type": "secret",
                "enabled": True
            },
            {
                "key": "targetPackage",
                "value": "de.k3b.android.androFotoFinder",
                "type": "default",
                "enabled": True
            },
            {
                "key": "themisBugId",
                "value": "THEMIS-ANKI-01",
                "type": "default",
                "enabled": True
            },
            {
                "key": "templateName",
                "value": "3g_network_drop.yaml",
                "type": "default",
                "enabled": True
            }
        ],
        "_postman_variable_scope": "environment"
    }

    # =========================================================================
    # 2. HELPER FUNCTIONS FOR COLLECTION ITEMS
    # =========================================================================
    def req_item(name, method, endpoint, body=None, description="", test_script=""):
        full_url = "{{baseUrl}}" + endpoint
        path_segments = [p for p in endpoint.strip("/").split("/") if p]
        
        request_obj = {
            "method": method,
            "header": [
                {
                    "key": "Content-Type",
                    "value": "application/json",
                    "type": "text"
                }
            ],
            "url": {
                "raw": full_url,
                "host": ["{{baseUrl}}"],
                "path": path_segments
            },
            "description": description
        }

        if body is not None:
            request_obj["body"] = {
                "mode": "raw",
                "raw": json.dumps(body, indent=2)
            }

        events = []
        if test_script:
            events.append({
                "listen": "test",
                "script": {
                    "type": "text/javascript",
                    "exec": test_script.strip().split("\n")
                }
            })

        return {
            "name": name,
            "request": request_obj,
            "response": [],
            "event": events
        }

    # Generic assertions
    std_200 = """
pm.test("Status code is 200 OK", function () {
    pm.response.to.have.status(200);
});
pm.test("Response time is acceptable (< 500ms)", function () {
    pm.expect(pm.response.responseTime).to.be.below(500);
});
pm.test("Response has valid JSON format", function () {
    var data = pm.response.json();
    pm.expect(data).to.be.an("object");
});
"""

    rq1_check = std_200 + """
pm.test("RQ1 Compliance: Injection latency satisfies <100ms SLA", function () {
    var data = pm.response.json();
    if (data.latency_ms !== undefined) {
        pm.expect(data.latency_ms).to.be.below(100.0);
    }
    if (data.injection_latency_ms !== undefined) {
        pm.expect(data.injection_latency_ms).to.be.below(100.0);
    }
    if (data.rq1_pass !== undefined) {
        pm.expect(data.rq1_pass).to.eql(true);
    }
});
"""

    # =========================================================================
    # 3. COLLECTION FOLDERS DEFINITION
    # =========================================================================
    folders = [
        # --- Folder 1: System Health & Telemetry ---
        {
            "name": "01. System & Device Telemetry",
            "description": "Endpoints for device connectivity status, telemetry snapshots, audit event log, and RQ1 latency metrics.",
            "item": [
                req_item(
                    "Get Device Status & Bridge Health",
                    "GET",
                    "/api/status",
                    description="Probes ADB bridge status, target model (Google Pixel 7), emulator/hardware status, and total active events.",
                    test_script=std_200 + """
pm.test("Device status is READY", function () {
    var data = pm.response.json();
    pm.expect(data.status).to.eql("READY");
    pm.expect(data.device).to.be.an("object");
});
"""
                ),
                req_item(
                    "Get Live Telemetry Snapshot",
                    "GET",
                    "/api/perturbation/telemetry",
                    description="Retrieves live sensor telemetry (CPU %, RAM %, Latency, Packet Loss, Chaos Score, Thermal state).",
                    test_script=std_200 + """
pm.test("Contains Chaos Score and hardware metrics", function () {
    var data = pm.response.json();
    pm.expect(data).to.have.property("chaos_score");
    pm.expect(data).to.have.property("latency_ms");
    pm.expect(data).to.have.property("cpu_stress");
});
"""
                ),
                req_item(
                    "Get Recorded Event Stream",
                    "GET",
                    "/api/perturbation/events?limit=25",
                    description="Retrieves recorded audit logs of environmental injections and benchmark results.",
                    test_script=std_200 + """
pm.test("Contains events list and total count", function () {
    var data = pm.response.json();
    pm.expect(data).to.have.property("events");
    pm.expect(data.events).to.be.an("array");
});
"""
                ),
                req_item(
                    "Get RQ1 Latency & Overhead SLA Metrics",
                    "GET",
                    "/api/performance_metrics",
                    description="Verifies empirical compliance with RQ1 requirements: injection latency < 100ms and host resource overhead < 15%.",
                    test_script=std_200 + """
pm.test("RQ1 latency and overhead constraints PASS", function () {
    var data = pm.response.json();
    pm.expect(data.latency_pass).to.eql(true);
    pm.expect(data.overhead_pass).to.eql(true);
    pm.expect(data.latency_stats.mean_ms).to.be.below(100.0);
});
"""
                )
            ]
        },

        # --- Folder 2: Multi-Factor Perturbation Deck ---
        {
            "name": "02. Multi-Factor Perturbation Control",
            "description": "Endpoints to apply synchronized compound stress profiles, execute presets, reset to nominal baseline, and correlate failures.",
            "item": [
                req_item(
                    "Apply Interactive Multi-Factor Stress",
                    "POST",
                    "/api/perturbation/apply",
                    body={
                        "name": "Interactive Stress Profile",
                        "targetModule": "Checkout Service",
                        "cpuStress": 75,
                        "ramStress": 65,
                        "diskIo": 450,
                        "latency": 950,
                        "packetLoss": 4,
                        "dnsFailure": False,
                        "thermalState": "Moderate",
                        "networkProfile": "3G HSDPA",
                        "interruptionType": "Incoming Call",
                        "interruptionFreq": 2
                    },
                    description="Applies synchronized multi-factor environmental stressors and returns updated chaos score and telemetry snapshot.",
                    test_script=std_200 + """
pm.test("Perturbations applied with valid Chaos Score", function () {
    var data = pm.response.json();
    pm.expect(data.status).to.eql("APPLIED");
    pm.expect(data.chaos_score).to.be.above(0);
});
"""
                ),
                req_item(
                    "Apply Preset Research Profile",
                    "POST",
                    "/api/perturbation/profile?profile_name=Mid-Transaction%20Stress%20Test",
                    description="Applies standardized pre-configured empirical research stress profile.",
                    test_script=std_200 + """
pm.test("Profile applied successfully", function () {
    var data = pm.response.json();
    pm.expect(data.status).to.eql("APPLIED");
    pm.expect(data.profile.name).to.eql("Mid-Transaction Stress Test");
});
"""
                ),
                req_item(
                    "Reset Environment to Nominal Baseline",
                    "POST",
                    "/api/perturbation/reset",
                    description="Reverts all hardware, network, and interruption stressors back to nominal 0% / nominal connectivity baseline.",
                    test_script=std_200 + """
pm.test("Environment returned to baseline", function () {
    var data = pm.response.json();
    pm.expect(data.status).to.eql("RESET_NOMINAL");
});
"""
                ),
                req_item(
                    "Attribute Failures to Environmental Stressors",
                    "POST",
                    "/api/perturbation/attribution",
                    body={
                        "failures": [
                            {
                                "timestamp": "2026-10-10 22:30:15",
                                "component": "com.target.checkout.PaymentGateway",
                                "error": "SocketTimeoutException: Connection timed out after 1850ms",
                                "type": "TIMEOUT"
                            },
                            {
                                "timestamp": "2026-10-10 22:30:18",
                                "component": "com.target.checkout.LocalDatabase",
                                "error": "SQLiteDatabaseLockedException: database is locked (code 5)",
                                "type": "CRASH"
                            }
                        ]
                    },
                    description="Correlates crash logs with active perturbation parameters to compute fault attribution confidence.",
                    test_script=std_200 + """
pm.test("Generates correlation attribution report", function () {
    var data = pm.response.json();
    pm.expect(data).to.have.property("correlated_failures");
    pm.expect(data).to.have.property("primary_attribution");
});
"""
                )
            ]
        },

        # --- Folder 3: Hardware Resource Starvation (Pillar 1) ---
        {
            "name": "03. Hardware Starvation (RQ1 Pillar 1)",
            "description": "Direct endpoints for CPU governor throttling, RAM pressure, thermal throttling, and battery drain.",
            "item": [
                req_item(
                    "Inject CPU Throttle Load",
                    "POST",
                    "/api/stressor/hardware/cpu",
                    body={"cpu_pct": 75},
                    description="Scales CPU governor throttle to 75% load.",
                    test_script=rq1_check
                ),
                req_item(
                    "Inject RAM Allocation Pressure & LMK Trim",
                    "POST",
                    "/api/stressor/hardware/ram",
                    body={
                        "ram_pct": 80,
                        "trim_level": "TRIM_MEMORY_RUNNING_CRITICAL",
                        "package": "{{targetPackage}}"
                    },
                    description="Allocates RAM buffers and broadcasts Low Memory Killer memory trim intents.",
                    test_script=rq1_check
                ),
                req_item(
                    "Set Thermal Throttling State",
                    "POST",
                    "/api/stressor/hardware/thermal",
                    body={"state": "Severe"},
                    description="Forces Android OS thermal state to Severe (status 3).",
                    test_script=rq1_check
                ),
                req_item(
                    "Set Battery Level & Unplug",
                    "POST",
                    "/api/stressor/hardware/battery",
                    body={"level": 4, "unplugged": True},
                    description="Simulates battery critical drain (4%) and unplugs AC charger.",
                    test_script=rq1_check
                )
            ]
        },

        # --- Folder 4: Network Chaos Engine (Pillar 2) ---
        {
            "name": "04. Network Chaos Engine (RQ1 Pillar 2)",
            "description": "Direct endpoints for RTT latency, packet loss, bandwidth throttling, DNS failures, and interface handover.",
            "item": [
                req_item(
                    "Inject RTT Network Latency Spike",
                    "POST",
                    "/api/stressor/network/latency",
                    body={"latency_ms": 1450},
                    description="Injects 1450ms RTT delay using kernel Netem emulation.",
                    test_script=rq1_check
                ),
                req_item(
                    "Inject Kernel Packet Loss",
                    "POST",
                    "/api/stressor/network/packet_loss",
                    body={"packet_loss_pct": 8},
                    description="Configures 8% deterministic TCP/UDP packet discard rate.",
                    test_script=rq1_check
                ),
                req_item(
                    "Set Bandwidth Profile (2G / EDGE)",
                    "POST",
                    "/api/stressor/network/profile",
                    body={"profile": "edge"},
                    description="Restricts bandwidth to 2G EDGE speeds (100 Kbps).",
                    test_script=rq1_check
                ),
                req_item(
                    "Simulate DNS Resolution Blackhole",
                    "POST",
                    "/api/stressor/network/dns_fail",
                    body={"enabled": True},
                    description="Blocks all outbound port 53 DNS lookup queries.",
                    test_script=rq1_check
                ),
                req_item(
                    "Simulate Wi-Fi to Cellular Handoff",
                    "POST",
                    "/api/stressor/network/handoff",
                    body={"handoff_type": "wifi_to_cellular"},
                    description="Forces network interface route mutation mid-request.",
                    test_script=rq1_check
                )
            ]
        },

        # --- Folder 5: OS System Interruptions (Pillar 3) ---
        {
            "name": "05. OS System Interruptions (RQ1 Pillar 3)",
            "description": "Endpoints to simulate telephony calls, SMS OTP alerts, app backgrounding, and Android Doze deep sleep.",
            "item": [
                req_item(
                    "Trigger Incoming Telephony GSM Call",
                    "POST",
                    "/api/stressor/interruption/call",
                    body={"number": "15550192831", "action": "ring"},
                    description="Broadcasts incoming telephony GSM call to preempt foreground UI.",
                    test_script=rq1_check + """
pm.test("Call is ringing", function () {
    var data = pm.response.json();
    pm.expect(data.status).to.eql("RINGING");
});
"""
                ),
                req_item(
                    "Accept Telephony Call (Steal Audio Focus)",
                    "POST",
                    "/api/stressor/interruption/call_accept",
                    description="Answers telephony call and asserts AUDIOFOCUS_GAIN_TRANSIENT.",
                    test_script=rq1_check
                ),
                req_item(
                    "Dismiss / Terminate Telephony Call",
                    "POST",
                    "/api/stressor/interruption/call_dismiss",
                    description="Cancels active telephony call and restores nominal audio focus.",
                    test_script=rq1_check
                ),
                req_item(
                    "Broadcast Heads-Up SMS OTP Notification",
                    "POST",
                    "/api/stressor/interruption/sms",
                    body={
                        "sender": "15550192831",
                        "message": "Your verification code is 849-204."
                    },
                    description="Dispatches system-level SMS OTP banner.",
                    test_script=rq1_check
                ),
                req_item(
                    "Background Application Lifecycle",
                    "POST",
                    "/api/stressor/interruption/lifecycle",
                    body={
                        "action": "background",
                        "duration_sec": 3.0,
                        "package_name": "{{targetPackage}}"
                    },
                    description="Simulates Android home key press to background target app.",
                    test_script=rq1_check
                ),
                req_item(
                    "Force Android Doze Deep Sleep Mode",
                    "POST",
                    "/api/stressor/interruption/doze",
                    body={"enabled": True},
                    description="Forces Android dumpsys deviceidle force-idle state.",
                    test_script=rq1_check
                )
            ]
        },

        # --- Folder 6: Context Variations (Pillar 4) ---
        {
            "name": "06. Context Variations (RQ1 Pillar 4)",
            "description": "Endpoints for device orientation, Dark/Night theme, accessibility font scaling, and mock GPS.",
            "item": [
                req_item(
                    "Set Display Orientation (Landscape)",
                    "POST",
                    "/api/stressor/context/orientation",
                    body={"mode": "landscape"},
                    description="Rotates Android device display 90 degrees.",
                    test_script=rq1_check
                ),
                req_item(
                    "Toggle Android System Dark Mode",
                    "POST",
                    "/api/stressor/context/dark_mode",
                    body={"enabled": True},
                    description="Enables night mode styling on Android OS system looper.",
                    test_script=rq1_check
                ),
                req_item(
                    "Set Accessibility Font Scale",
                    "POST",
                    "/api/stressor/context/font_scale",
                    body={"scale": 1.35},
                    description="Updates font scale factor to 1.35x to test UI truncation.",
                    test_script=rq1_check
                ),
                req_item(
                    "Inject Mock GPS Coordinates",
                    "POST",
                    "/api/stressor/context/gps",
                    body={"lat": 6.9271, "lon": 79.8612},
                    description="Sets mock latitude/longitude fixes on LocationService.",
                    test_script=rq1_check
                )
            ]
        },

        # --- Folder 7: APK Package Management & Testing ---
        {
            "name": "07. APK Package Management & Testing",
            "description": "Endpoints to list uploaded APK files, launch activities, and execute synchronized fault injection.",
            "item": [
                req_item(
                    "List Uploaded APK Packages",
                    "GET",
                    "/api/apk/list",
                    description="Lists all local APK files available on the server.",
                    test_script=std_200 + """
pm.test("Contains list of APK packages", function () {
    var data = pm.response.json();
    pm.expect(data).to.have.property("apks");
    pm.expect(data.apks).to.be.an("array");
});
"""
                ),
                req_item(
                    "Launch Target Application Activity",
                    "POST",
                    "/api/apk/launch",
                    body={"package_name": "{{targetPackage}}"},
                    description="Dispatches monkey/am start intent to launch target app.",
                    test_script=std_200
                ),
                req_item(
                    "Execute Synchronized Stress on Target APK",
                    "POST",
                    "/api/apk/stress_test",
                    body={
                        "package_name": "{{targetPackage}}",
                        "apk_name": "APhotoManager-0.6.4.apk",
                        "profile": {
                            "name": "Compound Stress Profile",
                            "cpuStress": 85,
                            "ramStress": 80,
                            "latency": 1500,
                            "packetLoss": 5,
                            "thermalState": "Warn",
                            "interruptionType": "Incoming Call"
                        }
                    },
                    description="Launches APK and injects synchronized multi-factor environmental stress.",
                    test_script=std_200 + """
pm.test("Stress test is executing", function () {
    var data = pm.response.json();
    pm.expect(data.status).to.eql("EXECUTING_STRESS_TEST");
    pm.expect(data.target_package).to.eql(pm.environment.get("targetPackage"));
});
"""
                )
            ]
        },

        # --- Folder 8: Declarative YAML Scenarios ---
        {
            "name": "08. Declarative YAML Scenarios",
            "description": "Endpoints to list templates, execute declarative Section 5 YAML scenarios on ADB, and validate AST schemas.",
            "item": [
                req_item(
                    "List YAML Scenario Templates",
                    "GET",
                    "/api/profiles/templates",
                    description="Lists pre-configured YAML scenario files from the profiles directory.",
                    test_script=std_200 + """
pm.test("Contains template list", function () {
    var data = pm.response.json();
    pm.expect(data.templates).to.be.an("array");
    pm.expect(data.count).to.be.above(0);
});
"""
                ),
                req_item(
                    "Execute YAML Scenario Template on Device",
                    "POST",
                    "/api/profiles/apply_template/{{templateName}}",
                    description="Parses and executes declarative scenario on ADB.",
                    test_script=std_200 + """
pm.test("Scenario template applied", function () {
    var data = pm.response.json();
    pm.expect(data.status).to.eql("APPLIED");
});
"""
                ),
                req_item(
                    "Validate Raw YAML Schema (AST Parser)",
                    "POST",
                    "/api/profiles/parse_yaml",
                    body={
                        "yaml_content": "version: \"1.0\"\nmetadata:\n  name: \"Postman Test Scenario\"\n  target_package: \"com.target.sample\"\ntriggers:\n  - lifecycle_step: \"CHECKOUT\"\n    injection_delay_ms: 100\nhardware:\n  cpu_throttle_pct: 80\nnetwork:\n  profile: \"3G_HSDPA\"\n  rtt_latency_ms: 1200"
                    },
                    description="Validates YAML string against Proposal Section 5 AST rules.",
                    test_script=std_200 + """
pm.test("Schema is valid AST", function () {
    var data = pm.response.json();
    pm.expect(data.status).to.eql("VALID");
    pm.expect(data.profile.name).to.eql("Postman Test Scenario");
});
"""
                )
            ]
        },

        # --- Folder 9: Themis Ground-Truth Benchmark Suite ---
        {
            "name": "09. Themis Ground-Truth Suite",
            "description": "Endpoints to retrieve ACM/IEEE FSE ground-truth benchmark bugs and trigger deterministic 100% crash reproduction.",
            "item": [
                req_item(
                    "List Ground-Truth Themis Benchmarks",
                    "GET",
                    "/api/themis/benchmarks",
                    description="Returns catalog of 52 empirical Android bugs with trigger conditions and attribution metrics.",
                    test_script=std_200 + """
pm.test("Contains benchmarks array", function () {
    var data = pm.response.json();
    pm.expect(data.benchmarks).to.be.an("array");
    pm.expect(data.count).to.be.above(0);
});
"""
                ),
                req_item(
                    "Reproduce Ground-Truth Bug Deterministically",
                    "POST",
                    "/api/themis/reproduce/{{themisBugId}}",
                    description="Executes targeted stress hook (e.g. SQLite battery lock or socket timeout) and validates attribution score.",
                    test_script=rq1_check + """
pm.test("Bug successfully reproduced with attribution > 90%", function () {
    var data = pm.response.json();
    pm.expect(data.status).to.eql("REPRODUCED");
    pm.expect(data.bug_id).to.eql(pm.environment.get("themisBugId"));
    pm.expect(data.attribution_score).to.be.above(0.90);
});
"""
                )
            ]
        },

        # --- Folder 10: Lifecycle Scheduler & Signals ---
        {
            "name": "10. Lifecycle Scheduler & Adaptive Signals",
            "description": "Endpoints to trigger lifecycle perturbation hooks and evaluate adaptive signals for runtime escalation.",
            "item": [
                req_item(
                    "Trigger Lifecycle Step Perturbation",
                    "POST",
                    "/api/scheduler/trigger_step",
                    body={"step": "MID_TRANSACTION"},
                    description="Injects coordinated perturbation corresponding to mid-transaction lifecycle phase.",
                    test_script=rq1_check + """
pm.test("Lifecycle step fired", function () {
    var data = pm.response.json();
    pm.expect(data.status).to.eql("STEP_FIRED");
});
"""
                ),
                req_item(
                    "Evaluate Runtime Telemetry Signals",
                    "POST",
                    "/api/scheduler/evaluate_signals",
                    body={
                        "fps": 22.5,
                        "latency_ms": 1850.0,
                        "cpu_pct": 88.0
                    },
                    description="Evaluates frame drops and latency against adaptive escalation thresholds.",
                    test_script=std_200 + """
pm.test("Signals evaluated", function () {
    var data = pm.response.json();
    pm.expect(data.status).to.eql("EVALUATED");
});
"""
                )
            ]
        },

        # --- Folder 11: Academic Audit & Compliance Reports ---
        {
            "name": "11. Academic Audit & Compliance Reports",
            "description": "Endpoints to generate structured research audit reports, historical execution logs, and empirical data.",
            "item": [
                req_item(
                    "Generate Comprehensive Academic Audit Report",
                    "GET",
                    "/api/audit/report",
                    description="Generates complete compliance report verifying injection latency < 100ms and host resource overhead < 15%.",
                    test_script=std_200 + """
pm.test("Contains project metadata and compliance verdict", function () {
    var data = pm.response.json();
    pm.expect(data.project_metadata.project_id).to.eql("J26-SE-334");
    pm.expect(data.rq1_empirical_compliance.injection_latency.compliance_verdict).to.eql(true);
    pm.expect(data.rq1_empirical_compliance.host_overhead.compliance_verdict).to.eql(true);
});
"""
                ),
                req_item(
                    "Get Latest Failure Attribution Report",
                    "GET",
                    "/api/attribution/report",
                    description="Retrieves persisted root-cause attribution diagnostics.",
                    test_script=std_200
                ),
                req_item(
                    "Get Historical Test Execution Runs",
                    "GET",
                    "/api/executions/history",
                    description="Returns list of recorded test execution runs and healing verdicts.",
                    test_script=std_200 + """
pm.test("Contains runs list", function () {
    var data = pm.response.json();
    pm.expect(data).to.have.property("runs");
    pm.expect(data.runs).to.be.an("array");
});
"""
                ),
                req_item(
                    "Get Research Benchmark Empirical Curves",
                    "GET",
                    "/api/research/benchmark_data",
                    description="Returns empirical latency, FPS, and failure rate comparison curves across 5 research treatment groups.",
                    test_script=std_200 + """
pm.test("Contains 5 empirical comparison groups", function () {
    var data = pm.response.json();
    pm.expect(data).to.have.property("1_baseline_nominal");
    pm.expect(data).to.have.property("5_compound_multi_factor");
});
"""
                )
            ]
        },

        # --- Folder 12: Authentication & User Management ---
        {
            "name": "12. Authentication & User Management",
            "description": "Endpoints for user login, registration, and user listing.",
            "item": [
                req_item(
                    "User Login & Token Issuance",
                    "POST",
                    "/api/auth/login",
                    body={
                        "email": "admin@heart.io",
                        "password": "password123"
                    },
                    description="Authenticates researcher credentials and sets authToken environment variable.",
                    test_script=std_200 + """
pm.test("User authenticated and token saved", function () {
    var data = pm.response.json();
    pm.expect(data.status).to.eql("AUTHENTICATED");
    pm.expect(data).to.have.property("token");
    pm.environment.set("authToken", data.token);
});
"""
                ),
                req_item(
                    "Register New Researcher Account",
                    "POST",
                    "/api/auth/register",
                    body={
                        "name": "Evaluation Examiner",
                        "email": "eval_reviewer@heart.io",
                        "password": "password123",
                        "role": "External Examiner",
                        "student_id": "EXAM-2026"
                    },
                    description="Registers a new research evaluator account.",
                    test_script="""
pm.test("Status code is 200 or 400 (if already registered)", function () {
    pm.expect(pm.response.code).to.be.oneOf([200, 400]);
});
"""
                ),
                req_item(
                    "List Authorized System Users",
                    "GET",
                    "/api/auth/users",
                    description="Retrieves list of active registered accounts.",
                    test_script=std_200 + """
pm.test("Contains users array", function () {
    var data = pm.response.json();
    pm.expect(data.users).to.be.an("array");
    pm.expect(data.users.length).to.be.above(0);
});
"""
                )
            ]
        }
    ]

    collection = {
        "info": {
            "_postman_id": "heart-engine-postman-suite-v1",
            "name": "HEART - Environmental Perturbation Engine REST API",
            "description": "Comprehensive Postman Test Collection for HEART (Context-Aware Environmental Perturbation Engine). Covers multi-factor fault injection, ADB device bridge, hardware starvation, network chaos, OS interruptions, declarative YAML scenarios, Themis ground-truth benchmarks, and RQ1 latency validation.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "item": folders
    }

    # Save to both workspace root and env testing directory
    paths = [
        (
            os.path.join(ROOT_DIR, "HEART_API_Collection.postman_collection.json"),
            os.path.join(ROOT_DIR, "HEART_API_Environment.postman_environment.json")
        ),
        (
            os.path.join(os.path.dirname(ROOT_DIR), "HEART_API_Collection.postman_collection.json"),
            os.path.join(os.path.dirname(ROOT_DIR), "HEART_API_Environment.postman_environment.json")
        )
    ]

    for col_path, env_path in paths:
        with open(col_path, "w", encoding="utf-8") as f:
            json.dump(collection, f, indent=2)
        with open(env_path, "w", encoding="utf-8") as f:
            json.dump(environment, f, indent=2)
        print(f"Generated: {col_path}")
        print(f"Generated: {env_path}")

if __name__ == "__main__":
    create_postman_files()
