"""Automated Test Runner for EquiMed Software Engineering Project.

Executes all unit, black-box, and integration suites and prints formal verification report.
"""

import sys
import time
import unittest


def run_all_tests():
    print("=" * 76)
    print("  🧪 Running EquiMed Verification & Validation Test Suite")
    print("  IIIT Lucknow • Software Engineering Laboratory")
    print("=" * 76)

    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")

    start_time = time.time()
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    elapsed = time.time() - start_time

    total = result.testsRun
    failed = len(result.failures)
    errored = len(result.errors)
    passed = total - failed - errored
    pass_pct = (passed / total * 100.0) if total > 0 else 0.0

    print("\n" + "=" * 76)
    print("  📊 TEST EXECUTION SUMMARY:")
    print(f"     Total Test Cases Executed : {total}")
    print(f"     Passed                    : {passed}  (🟢 {pass_pct:.1f}%)")
    print(f"     Failed                    : {failed}")
    print(f"     Errors                    : {errored}")
    print(f"     Execution Time            : {elapsed * 1000:.2f} ms ({elapsed:.3f} s)")
    print("=" * 76)

    if failed == 0 and errored == 0:
        print("  🎉 ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!\n")
        return 0
    else:
        print("  ❌ SOME TESTS FAILED. PLEASE REVIEW LOGS ABOVE.\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
