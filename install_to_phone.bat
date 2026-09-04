@echo off
title Install ArgosOSINT APK to Phone
echo ========================================================
echo Installing ArgosOSINT APK to connected Android device...
echo ========================================================

set ADB_PATH=C:\Android\platform-tools\adb.exe
if not exist "%ADB_PATH%" (
    where adb >nul 2>&1
    if %errorlevel% equ 0 (
        set ADB_PATH=adb
    ) else (
        echo [ERROR] ADB not found. Please connect phone and ensure ADB is available.
        pause
        exit /b 1
    )
)

echo [1/3] Checking connected devices...
"%ADB_PATH%" devices
echo.

echo [2/3] Uninstalling old build...
"%ADB_PATH%" uninstall org.argos.argososint

echo [3/3] Installing release APK...
"%ADB_PATH%" install "release_apk\argososint-1.0-arm64-v8a-debug.apk"

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo SUCCESS! Launching ArgosOSINT on your phone...
    echo ========================================================
    "%ADB_PATH%" shell am start -n org.argos.argososint/org.kivy.android.PythonActivity
) else (
    echo.
    echo [ERROR] Installation failed. Make sure phone is unlocked and USB debugging is ON.
)

pause
