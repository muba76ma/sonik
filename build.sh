#!/data/data/com.termux/files/usr/bin/bash
set -e

if [ ! -f android.jar ]; then
  echo "ERROR: android.jar missing."
  exit 1
fi

rm -rf build && mkdir -p build/gen build/obj build/dex

echo "[1/5] Compiling resources..."
aapt2 compile --dir res -o build/res.zip

echo "[2/5] Linking APK..."
aapt2 link -o build/sonik-unsigned.apk -I android.jar \
  --manifest AndroidManifest.xml --java build/gen build/res.zip

echo "[3/5] Compiling Java..."
javac -source 1.8 -target 1.8 -classpath android.jar -d build/obj \
  build/gen/com/sonik/browser/R.java \
  src/com/sonik/browser/SonikActivity.java

echo "[4/5] Dexing..."
if command -v d8 >/dev/null 2>&1; then
  echo "  using d8"
  d8 --lib android.jar --output build/dex build/obj/com/sonik/browser/*.class
elif command -v dx >/dev/null 2>&1; then
  echo "  using dx"
  ( cd build/obj && dx --dex --output=../dex/classes.dex com/sonik/browser/*.class )
else
  echo "ERROR: neither d8 nor dx found" ; exit 1
fi

echo "[5/5] Packaging & signing..."
( cd build && zip -j sonik-unsigned.apk dex/classes.dex )

if [ ! -f sonik.keystore ]; then
  echo "  Generating keystore..."
  keytool -genkeypair -keystore sonik.keystore -alias sonik \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass sonik123 -keypass sonik123 \
    -dname "CN=Sonik, O=Sonik, C=US" 2>/dev/null
fi

apksigner sign --ks sonik.keystore --ks-pass pass:sonik123 --key-pass pass:sonik123 \
  --out build/sonik.apk build/sonik-unsigned.apk

echo "Done -> build/sonik.apk"
