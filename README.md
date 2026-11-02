# Sonik

A from-scratch, scriptable Android browser built entirely in Termux.

## What it is

Sonik is a native Android WebView shell with a URL bar, built using Termux's
raw toolchain (`aapt2`, `javac`, `dx`/`d8`, `apksigner`) — no Gradle, no
Android Studio. It exposes the WebView's Chrome DevTools Protocol (CDP) socket
on `127.0.0.1:9222`, so a Python process in Termux can drive it:


## Build locally (Termux)


## Build in CI

Push to `main`. GitHub Actions builds `sonik.apk` and uploads it as the
`sonik-apk` artifact.

## Layout

- `src/com/sonik/browser/SonikActivity.java` — browser shell + CDP bridge
- `res/values/strings.xml` — app name resource
- `AndroidManifest.xml` — package declaration, permissions, launcher
- `build.sh` — builds, dexes, signs the APK
- `sonik.py` — Python CDP controller
