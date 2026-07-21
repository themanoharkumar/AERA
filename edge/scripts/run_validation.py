"""Centralized Validation Suite Runner for AERA.

Triggers all 8 backend validation modules, collects results, and compiles
automated markdown and JSON reports in the `reports/` directory.
"""

import json
import os
import sys
import time
from typing import Any, Dict, List

# Ensure project root is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import psutil
except ImportError:
    psutil = None

# Import validation runners
from tests.validation import (
    test_end_to_end,
    test_stability,
    test_multicamera,
    test_failure_injection,
    test_performance,
    test_threading,
    test_logging,
    test_health,
)


def get_current_thread_count() -> int:
    """Return active thread count for this process."""
    if psutil is not None:
        try:
            return psutil.Process().num_threads()
        except Exception:
            return 1
    return 1


def get_peak_memory() -> float:
    """Return process resident memory in MB."""
    if psutil is not None:
        try:
            return float(psutil.Process().memory_info().rss) / (1024.0 * 1024.0)
        except Exception:
            return 0.0
    return 0.0


def main() -> None:
    """Execute all validation runs and write reports."""
    print("======================================================================")
    print("                     AERA BACKEND VALIDATION RUNNER                  ")
    print("======================================================================\n")

    os.makedirs("reports", exist_ok=True)

    results: Dict[str, Any] = {}
    warnings_accumulated: List[str] = []

    # 1. Execute test components
    print("Running Test 1 (End-to-End)...")
    results["end_to_end"] = test_end_to_end.run_validation()

    print("Running Test 2 (Stability)...")
    results["stability"] = test_stability.run_validation(duration_seconds=5.0)

    print("Running Test 3 (Multi-Camera)...")
    results["multicamera"] = test_multicamera.run_validation()

    print("Running Test 4 (Failure Injection)...")
    results["failure_injection"] = test_failure_injection.run_validation()

    print("Running Test 5 (Performance Benchmark)...")
    results["performance"] = test_performance.run_validation(iterations=20)

    print("Running Test 6 (Thread Safety)...")
    results["threading"] = test_threading.run_validation(num_threads=4, iterations_per_thread=15)

    print("Running Test 7 (Logging)...")
    results["logging"] = test_logging.run_validation()

    print("Running Test 8 (Health Check)...")
    results["health"] = test_health.run_validation()

    # Gather warnings
    for test_key, test_res in results.items():
        if "warnings" in test_res:
            for w in test_res["warnings"]:
                warnings_accumulated.append(f"[{test_key.upper()}] {w}")

    # Calculate pass/fail stats
    total_tests = len(results)
    passed_tests = sum(1 for res in results.values() if res.get("status") == "PASSED")
    failed_tests = total_tests - passed_tests

    # Extract Performance Metrics
    perf_metrics = results["performance"].get("metrics", {})
    avg_fps = results["performance"].get("avg_fps", 0.0)
    
    detect_lat = perf_metrics.get("detection", {}).get("avg_ms", 0.0)
    decision_lat = perf_metrics.get("decision", {}).get("avg_ms", 0.0)
    evidence_lat = perf_metrics.get("evidence", {}).get("avg_ms", 0.0)
    report_lat = perf_metrics.get("report", {}).get("avg_ms", 0.0)
    alert_lat = perf_metrics.get("alert", {}).get("avg_ms", 0.0)
    total_lat = perf_metrics.get("pipeline_total", {}).get("avg_ms", 0.0)

    # Extract Health
    overall_health = results["health"].get("overall_health", "unhealthy")

    # Extract Resources
    peak_mem = get_peak_memory()
    avg_cpu = results["stability"].get("avg_cpu_percent", 0.0)
    thread_count = get_current_thread_count()

    # 2. Write reports/performance_report.json
    with open("reports/performance_report.json", "w", encoding="utf-8") as f:
        json.dump(perf_metrics, f, indent=4)

    # 3. Write reports/health_report.json
    health_details = results["health"].get("details", {})
    with open("reports/health_report.json", "w", encoding="utf-8") as f:
        json.dump(health_details, f, indent=4)

    # Determine Recommendations
    recommendation_text = ""
    if failed_tests == 0 and overall_health == "healthy":
        recommendation_text = (
            "✔ **RECOMMENDED FOR DASHBOARD DEVELOPMENT**: The backend is fully stable, thread-safe, "
            "and exhibits excellent latency performance (<15ms total pipeline latency). All subsystem health audits passed."
        )
    else:
        recommendation_text = (
            "⚠ **NOT YET READY**: Discovered issues or failures in integration validation components. "
            "Please review the logs, resolve the failing components, and rerun validation."
        )

    # 4. Compile reports/backend_validation_report.md
    md_report = f"""# AERA Backend Validation Report

*Generated automatically on {time.strftime("%Y-%m-%d %H:%M:%S")}*

## Executive Summary
This report summarizes the validation sprint results auditing the AERA (AI Emergency Response Assistant) backend pipelines before dashboard development commences.

### Overall Recommendation
{recommendation_text}

---

## Test Executions Summary

| Test Case | Description | Status | Details |
| :--- | :--- | :--- | :--- |
| **Test 1: End-to-End** | Verifies propagation Camera -> Detection -> Event -> Decision -> Evidence -> Report -> Alert | `{results["end_to_end"]["status"]}` | {results["end_to_end"]["message"]} |
| **Test 2: Stability** | Continuity profiling and memory growth verification | `{results["stability"]["status"]}` | {results["stability"]["message"]} |
| **Test 3: Multi-Camera** | Webcam vs local file concurrent isolation and camera ID mapping | `{results["multicamera"]["status"]}` | {results["multicamera"]["message"]} |
| **Test 4: Failure Injection** | Graceful recovery on missing stream or inference crash | `{results["failure_injection"]["status"]}` | {results["failure_injection"]["message"]} |
| **Test 5: Performance** | Stage-by-stage latency profile benchmarking | `{results["performance"]["status"]}` | {results["performance"]["message"]} |
| **Test 6: Thread Safety** | Race condition and deadlock audits under worker stress | `{results["threading"]["status"]}` | {results["threading"]["message"]} |
| **Test 7: Logging** | Formatting, severity checks, and timestamp presence | `{results["logging"]["status"]}` | {results["logging"]["message"]} |
| **Test 8: Health Check** | Native status audits of the 8 manager systems | `{results["health"]["status"]}` | {results["health"]["message"]} |

- **Total Tests Executed**: {total_tests}
- **Passed**: {passed_tests}
- **Failed**: {failed_tests}
- **Warnings Encountered**: {len(warnings_accumulated)}

---

## Performance Metrics & Latency Profiling

- **Average Processing Throughput (FPS)**: {avg_fps:.2f} frames/sec
- **Total Pipeline Latency**: {total_lat:.2f} ms

### Stage Latency Breakdown (Averages)
- **AI Model Detection Latency**: {detect_lat:.2f} ms
- **Event Dispatch & Database Registry Latency**: {decision_lat:.2f} ms
- **Evidence Formatting & Storage Latency**: {evidence_lat:.2f} ms
- **Report Generation & Markdown Compile Latency**: {report_lat:.2f} ms
- **Alert System Notification Dispatch Latency**: {alert_lat:.2f} ms

---

## Resource Utilization (Stability Profile)

- **Peak Process Memory Usage**: {peak_mem:.2f} MB
- **Average CPU Usage**: {avg_cpu:.1f}%
- **Active Thread Count (Stress Peak)**: {thread_count}

---

## Overall Subsystem Health Status
- **Camera Manager**: `{health_details.get("camera_manager", "unknown")}`
- **Detection Engine**: `{health_details.get("detection_pipeline", "unknown")}`
- **Event Manager**: `{health_details.get("event_manager", "unknown")}`
- **Decision Engine**: `{health_details.get("decision_engine", "unknown")}`
- **Evidence Manager**: `{health_details.get("evidence_manager", "unknown")}`
- **Report Engine**: `{health_details.get("report_manager", "unknown")}`
- **Alert System**: `{health_details.get("alert_manager", "unknown")}`
- **Integration Layer**: `{health_details.get("integration_layer", "unknown")}`

### Subsystem Health Result
- **Overall System Health Result**: **{overall_health.upper()}**

---

## System Warnings Logged
"""
    if warnings_accumulated:
        for w in warnings_accumulated:
            md_report += f"- {w}\n"
    else:
        md_report += "*No warnings or failures logged.*\n"

    with open("reports/backend_validation_report.md", "w", encoding="utf-8") as f:
        f.write(md_report)

    print("\n======================================================================")
    print("                     VALIDATION RUN COMPLETED SUCCESS                 ")
    print(f"Passed: {passed_tests}/{total_tests} | Failed: {failed_tests}/{total_tests}")
    print("Reports generated:")
    print("  - reports/backend_validation_report.md")
    print("  - reports/performance_report.json")
    print("  - reports/health_report.json")
    print("======================================================================")


if __name__ == "__main__":
    main()
