#!/usr/bin/env python3
"""
Sonik build orchestrator — the from-scratch APK pipeline.
Kept separate from sonik.py (the runtime CDP controller).

Usage:
    python3 orchestrator.py             # full build + sign
    python3 orchestrator.py --clean     # clean only
    python3 orchestrator.py --no-sign   # build unsigned only
    python3 orchestrator.py --quiet     # suppress command echo
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

GREEN, RED, YELLOW, CYAN, DIM, RESET = (
    "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[2m", "\033[0m"
)

ROOT  = Path(__file__).resolve().parent
BUILD = ROOT / "build"
LOG   = BUILD / "build.log"

def log(msg, level="INFO"):
    tag = {
        "INFO": f"{GREEN}[SONIK]{RESET}",
        "WARN": f"{YELLOW}[SONIK-WARN]{RESET}",
        "ERR":  f"{RED}[SONIK-ERR]{RESET}",
        "STEP": f"{CYAN}[SONIK-STEP]{RESET}",
    }[level]
    line = f"{tag} {msg}"
    print(line, flush=True)
    if BUILD.exists():
        with open(LOG, "a") as f:
            f.write(line + "\n")

def die(msg):
    log(msg, "ERR")
    sys.exit(1)

def run(cmd, cwd=None, timeout=300, quiet=False):
    if not quiet:
        cwd_str = f"  (cwd={cwd})" if cwd else ""
        log(f"$ {' '.join(cmd)}{cwd_str}", "STEP")
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=cwd, timeout=timeout,
                           capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        die(f"timed out after {timeout}s: {cmd[0]}")
    except FileNotFoundError:
        die(f"binary not found: {cmd[0]}")
    dt = time.time() - t0
    if r.returncode != 0:
        if r.stderr:
            print(r.stderr[-2000:], file=sys.stderr)
        die(f"{cmd[0]} exited {r.returncode} after {dt:.1f}s")
    # javac warns to stderr but exits 0 — only echo if it's non-warning noise
    if r.stderr and "warning" not in r.stderr.lower():
        log(f"  stderr: {r.stderr.strip()[:300]}", "WARN")
    log(f"  ok in {dt:.1f}s")
    return r

# ─── Environment ─────────────────────────────────────────────────────────

def verify_env():
    log("Validating toolchain…")
    mandatory = {
        "javac":     "pkg install openjdk-21",
        "keytool":   "pkg install openjdk-21",
        "aapt2":     "pkg install aapt2",
        "apksigner": "pkg install apksigner",
        "zip":       "pkg install zip",
    }
    for tool, hint in mandatory.items():
        if not shutil.which(tool):
            die(f"missing: {tool}  →  {hint}")

    has_d8 = shutil.which("d8") is not None
    has_dx = shutil.which("dx") is not None
    if not (has_d8 or has_dx):
        die("missing: d8 or dx  →  pkg install dx")

    jar = ROOT / "android.jar"
    if not jar.exists():
        die(
            "android.jar missing. Fetch it:\n"
            "  curl -fL -o platform-33.zip "
            "https://dl.google.com/android/repository/platform-33_r02.zip\n"
            "  unzip -j platform-33.zip android-13/android.jar -d .\n"
            "  rm platform-33.zip"
        )
    size_mb = jar.stat().st_size / (1024 * 1024)
    if size_mb < 5:
        die(f"android.jar is only {size_mb:.1f} MB — that's an HTML error page, not the SDK.")

    log(f"  dexer: {'d8' if has_d8 else 'dx'}")
    log(f"  android.jar: {size_mb:.1f} MB")
    log("Toolchain OK.")

# ─── Lifecycle ───────────────────────────────────────────────────────────

def clean():
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir()
    for sub in ("gen", "obj", "dex"):
        (BUILD / sub).mkdir()
    log("Cleaned build/")

def next_counter():
    cf = BUILD / "counter.txt"
    n = 1
    if cf.exists():
        try:
            n = int(cf.read_text().strip()) + 1
        except ValueError:
            n = 1
    cf.write_text(str(n))
    return n

# ─── Pipeline ────────────────────────────────────────────────────────────

def compile_resources(q):
    log("[1/5] aapt2 compile")
    run(["aapt2", "compile", "--dir", "res", "-o", "build/res.zip"],
        cwd=ROOT, quiet=q)

def link_apk(q):
    log("[2/5] aapt2 link")
    run([
        "aapt2", "link",
        "-o", "build/sonik-unsigned.apk",
        "-I", "android.jar",
        "--manifest", "AndroidManifest.xml",
        "--java", "build/gen",
        "build/res.zip",
    ], cwd=ROOT, quiet=q)

def compile_java(q):
    log("[3/5] javac")
    srcs = [
        "build/gen/com/sonik/browser/R.java",
        "src/com/sonik/browser/SonikActivity.java",
    ]
    run([
        "javac", "-source", "1.8", "-target", "1.8",
        "-classpath", "android.jar",
        "-d", "build/obj",
        *srcs,
    ], cwd=ROOT, quiet=q)

def dex(q):
    log("[4/5] dex")
    classes = sorted((ROOT / "build/obj/com/sonik/browser").glob("*.class"))
    if not classes:
        die("no .class files produced by javac — something is broken upstream")
    if shutil.which("d8"):
        run([
            "d8", "--lib", "android.jar",
            "--output", "build/dex",
            *[str(p.relative_to(ROOT)) for p in classes],
        ], cwd=ROOT, quiet=q)
    else:
        # dx validates that the path matches the class's package.
        # Run from build/obj (the package root for "com.sonik.browser")
        # and pass package-qualified relative paths.
        run([
            "dx", "--dex",
            "--output=../dex/classes.dex",   # -> build/dex/classes.dex (exists from clean())
            *[str(p.relative_to(ROOT / "build/obj")) for p in classes],
        ], cwd=ROOT / "build/obj", quiet=q)

def package_apk(q):
    log("[5/5] packaging")
    run(["zip", "-j", "sonik-unsigned.apk", "dex/classes.dex"],
        cwd=BUILD, quiet=q)

def sign(q, version):
    ks = ROOT / "sonik.keystore"
    if not ks.exists():
        log("  generating keystore…")
        run([
            "keytool", "-genkeypair",
            "-keystore", str(ks),
            "-alias", "sonik",
            "-keyalg", "RSA", "-keysize", "2048",
            "-validity", "10000",
            "-storepass", "sonik123", "-keypass", "sonik123",
            "-dname", "CN=Sonik, O=Sonik, C=US",
        ], cwd=ROOT, quiet=q)
    run([
        "apksigner", "sign",
        "--ks", str(ks),
        "--ks-pass", "pass:sonik123",
        "--key-pass", "pass:sonik123",
        "--out", "build/sonik.apk",
        "build/sonik-unsigned.apk",
    ], cwd=ROOT, quiet=q)

def report(version, counter):
    apk = BUILD / "sonik.apk"
    if not apk.exists():
        die("build finished but sonik.apk is missing")
    digest = hashlib.sha256(apk.read_bytes()).hexdigest()
    size_kb = apk.stat().st_size / 1024
    log("")
    log("─" * 56)
    log(f"  APK      : {apk}")
    log(f"  size     : {size_kb:.1f} KB")
    log(f"  version  : {version}")
    log(f"  build #  : {counter}")
    log(f"  sha256   : {digest}")
    log("─" * 56)
    log("Install:  termux-open build/sonik.apk")
    log("Test:     python3 sonik.py title")
    # also drop a plain checksum file for easy sharing
    (BUILD / "sonik.apk.sha256").write_text(f"{digest}  sonik.apk\n")

# ─── Entry ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true", help="only clean build/")
    ap.add_argument("--no-sign", action="store_true", help="skip signing")
    ap.add_argument("--quiet", "-q", action="store_true", help="suppress $ cmd echo")
    args = ap.parse_args()

    BUILD.mkdir(exist_ok=True)
    LOG.write_text("")  # reset log

    log("Sonik build orchestrator")
    if args.clean:
        clean()
        log("Done.")
        return

    verify_env()
    clean()
    counter = next_counter()
    version = os.environ.get("SONIK_VERSION", "0.1.0")
    log(f"Build #{counter} · version {version}")

    compile_resources(args.quiet)
    link_apk(args.quiet)
    compile_java(args.quiet)
    dex(args.quiet)
    package_apk(args.quiet)

    if args.no_sign:
        log("Skipping signing (--no-sign).")
        report(version + "-unsigned", counter)
    else:
        sign(args.quiet, version)
        report(version, counter)

    log("Build sequence completed successfully ⚡")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Aborted by user.", "ERR")
        sys.exit(130)
