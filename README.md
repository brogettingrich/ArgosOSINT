# 👁️ ArgosOSINT

> **Multi-Target Intelligence, Fuzzy Permutation & Cross-Platform Reconnaissance Platform.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite%20WAL-003B57.svg)](https://www.sqlite.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Android%20Termux-orange.svg)](#)

---

## 🌟 Overview

**ArgosOSINT** is a high-speed, local-first open-source intelligence (OSINT) suite designed for automated digital footprint discovery, heuristic handle permutation, and context clue cross-referencing.

When given an ambiguous handle like `user...34`, ArgosOSINT automatically computes dot-compressions (`user..34`, `user.34`), separator transformations (`user_34`, `user-34`), and leetspeak variants—simultaneously probing 100+ platforms in parallel with real-time streaming results and force-directed relationship graph visualization.

---

## ⚡ Key Capabilities

- **🔤 Heuristic Permutation Matrix**: Intelligently expands inputs across dot stripping, leetspeak, suffix additions, and Levenshtein similarity distance ranking.
- **🎯 Context Clue Corroboration**: Compares scraped metadata, display names, and bio tokens to assign a statistical confidence score (e.g. *95% Confirmed Match*).
- **🌐 100+ Platform Probes**: Asynchronous probing across Social, Developer, Gaming, Media, and Web3 platforms with rate-limit evasion and custom headers.
- **📧 Email Intelligence**: Format validation, domain extraction, Gravatar profile discovery, and public GitHub commit lookups.
- **📞 Phone Number Intelligence**: International E.164 parsing, ISO country codes, format permutations, and targeted search dorks.
- **🕸️ Interactive Relationship Graph**: Force-directed Canvas graph displaying connections between seed targets, handles, emails, and confirmed platforms.
- **📄 Exportable Intelligence Dossiers**: One-click export to standalone structured JSON or printable HTML reports.

---

## 🚀 Quick Start Guide

### 🪟 Windows Setup (Windows 10 / 11)

1. Clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ArgosOSINT.git
   cd ArgosOSINT
   ```
2. Run automated setup:
   ```cmd
   setup_windows.bat
   ```
3. Start the application:
   ```cmd
   run_windows.bat
   ```
4. Open your browser at **`http://127.0.0.1:8500`**.

---

### 📱 Android (Termux) Setup

1. Open Termux and clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ArgosOSINT.git ~/ArgosOSINT
   cd ~/ArgosOSINT
   ```
2. Setup and launch:
   ```bash
   chmod +x setup_termux.sh run_termux.sh
   ./setup_termux.sh
   ./run_termux.sh
   ```
3. Access at **`http://127.0.0.1:8500`** in your mobile browser. Tap **"Add to Home screen"** to install as a full-screen PWA.

---

## 🛠️ Project Structure

```text
ArgosOSINT/
├── app/
│   ├── main.py                  # FastAPI server & SSE streaming route
│   ├── config.py                # Scanner concurrency & timeout settings
│   ├── core/
│   │   ├── permutations.py      # Fuzzy username generator & Levenshtein distance
│   │   └── corroboration.py     # Profile context clue scorer & token matcher
│   ├── modules/
│   │   ├── username_probe.py    # 100+ platform probe database & status evaluator
│   │   ├── email_probe.py       # Email format, Gravatar, and GitHub footprint
│   │   └── phone_probe.py       # E.164 phone parser & country identification
│   ├── database/
│   │   ├── schema.py            # SQLite schema (dossiers & scan results)
│   │   └── repository.py        # Data access queries
│   └── static/                  # Minimalist Linear-inspired dark UI & PWA assets
├── requirements.txt
├── setup_windows.bat / run_windows.bat
├── setup_termux.sh / run_termux.sh
├── LICENSE                      # MIT License
└── README.md
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).