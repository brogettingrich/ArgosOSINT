# Overnight report

Everything below was actually tested, not assumed. All 25 existing tests still pass, everything touched still compiles. This file is safe to delete once you've read it — it's not part of the app.

---

## 1. Fixed: confidence/sharpness display removed

Reverted to a plain `✓ Face detected`. The face-crop thumbnail swap (showing what actually got analyzed, not your raw upload) stayed — you didn't ask to remove that part, and it's harmless/useful on its own.

## 2. Fixed: the Kylie Jenner bug — confirmed real, root cause found, fixed

You were right to ask. Here's exactly what was happening, checked against the real code and real live sites, not guessed:

**The mechanism:** when you search by name only, `generate_permutations()` builds a list of guessed handles from "Kylie Jenner" — `kylie_jenner`, `kylie.jenner`, `kyliejenner`, `k_jenner`, etc. Exactly ONE of these becomes the "guaranteed always scanned" guess (`is_seed=True`); the rest only get checked if "Enable Delimiter & Syllable Permutations" is on.

**The bug:** the guaranteed guess was always `kylie_jenner` (with underscore) — literally just whichever variant happened to be first in the list, not the most likely real handle. I checked both variants against the real Instagram:

```
kylie_jenner   -> found: False   (not her account)
kyliejenner    -> found: True    (381M followers, "Kylie" — her real profile)
```

So if permutations were off for any reason, the app would only ever try the wrong guess and correctly report nothing found — that's not a parsing bug, `check_single_site` works perfectly once given the right handle. It's a bad first guess.

**The fix:** reordered `generate_name_permutations()` in `app/core/permutations.py` so the no-delimiter concatenation (`kyliejenner`) is what becomes the guaranteed guess, since that's what real people (and especially public figures) actually use when it's available — not the underscore version. Verified end-to-end after the fix:

```
exact_seeds (guaranteed, checkbox-independent): ['kyliejenner']
FOUND on Instagram: Kylie {'followers': '381M', 'following': '154', 'posts': '7,389'}
```

This isn't just a Kylie-specific fix — it fixes name-only search for basically anyone whose real handle is the plain concatenation, which is most people.

---

## 3. Full code review — what I found

Went through every backend module tonight, not just the face-matching code. Here's what's actually there:

### Real, worth-knowing findings

- **`app/core/email_pivot.py` — `probe_google()` is not a real check.** For any `@gmail.com`/`@googlemail.com` address, it unconditionally reports `"registered": True` with language like "Verified Google / Gmail ecosystem account" and "Active Google account endpoint" — but it never makes a network call. It's pure domain pattern-matching dressed up in the same "verified" language as the real checks (Gravatar/GitHub/Duolingo/Spotify, which do make real HTTP calls). A made-up or typo'd Gmail address gets reported exactly the same way as a real one. Worth either removing this, or clearly relabeling it as "uses Gmail" rather than "verified account" — right now it can inflate confidence on nothing.
- **`app/core/email_pivot.py` — `PUBLIC_BREACH_CATALOG` (a hardcoded list of famous breaches at the top of the file) is dead code.** Defined, never referenced anywhere else in the codebase. Either finish wiring it in or delete it — right now it's just sitting there.
- **`app/database/repository.py` — opens a brand-new SQLite connection on every single call**, including `save_scan_result()` which runs once per found profile. Not broken (SQLite connections are cheap locally), but a real optimization opportunity: a shared/pooled connection would cut real overhead on a scan with dozens of results, more noticeable on a phone's CPU than a desktop's.
- **`app/core/ai_engine.py` — one grammar glitch** in the deterministic (non-AI) fallback briefing: "Corroboration corroborates active online presence." Purely cosmetic, easy one-line fix whenever you touch that area.

### Checked and genuinely fine

- `phone_probe.py`, `email_probe.py` — reasonable fallback layering (dnspython → public resolvers → heuristic; phonenumbers → manual parsing), no correctness bugs found.
- `corroboration.py`, `username_probe.py` — already gone over these in depth earlier this session; no new issues found on this pass.
- All 25 existing tests (`tests/`) still pass after every change tonight.

---

## 4. Everything from this session, status check

| Item | Status |
|---|---|
| WebView black-screen fix | ✅ Shipped, verified on your A54 |
| Cleartext manifest fix | ✅ Shipped, verified on your A54 |
| Find With Face — UI (button, picker, preview) | ✅ Working (local preview) |
| Find With Face — backend (embed, store, score) | ✅ Working (local preview), tested with real numbers |
| Per-investigation seed scoping | ✅ Fixed, tested |
| "Why did this match" factor display | ✅ Shipped |
| Faces filter chip | ✅ Shipped, tested |
| Long-filename UI break | ✅ Fixed |
| Confidence/sharpness display | ✅ Removed per your ask tonight |
| Kylie Jenner / name-search bug | ✅ Found, fixed, verified tonight |
| Event-loop blocking during face embed | ✅ Measured, improved (modest, honest gain) |
| `source.include_exts` missing tflite/onnx | ✅ Fixed |
| **Android build (opencv/numpy/tflite-runtime in buildozer.spec)** | ❌ Not started |
| **Real device test of Find With Face** | ❌ Not started — this feature only exists in the local browser preview right now |
| `probe_google()` false "verified" claim | ⚠️ Found tonight, not fixed — needs your call on remove vs. relabel |
| `PUBLIC_BREACH_CATALOG` dead code | ⚠️ Found tonight, not fixed — cleanup whenever |
| DB connection-per-call overhead | ⚠️ Found tonight, not fixed — real but not urgent |
| `is_extreme_angle()` in face_match.py | ⚠️ Still an unvalidated placeholder, not a measured threshold |
| Model license/provenance (`facenet_int_quantized.tflite`) | ⚠️ Still unconfirmed |
| `face_experiment_DELETE_ME/` folder | ⚠️ Still sitting in the repo, logic now duplicated for real in `app/core/face_match.py` |

---

## 5. Suggested plan for what's next (your call on order)

1. **Android build (Phase 4)** — the one big remaining unknown for Find With Face. Add `opencv`, `numpy`, `tflite-runtime` to `buildozer.spec`; expect the `tflite-runtime` recipe (old TF 2.8.0 pin, compiles from source) to be a real fight, same category as the WebView saga back at the start of this session. Budget real time for this, not a quick add.
2. **`probe_google()` decision** — quick to fix once you say which way you want it (remove, or relabel honestly).
3. **Clean up `face_experiment_DELETE_ME/`** — delete it once you're confident the real `app/core/face_match.py` port covers everything it proved out.
4. **More same-person calibration data** for the face-match threshold — still resting on a small manual test set from early tonight.
5. **DB connection pooling** — worth doing before this runs real multi-hundred-candidate scans on a phone CPU.
6. Smaller: `PUBLIC_BREACH_CATALOG` cleanup, the ai_engine grammar glitch, revisiting `is_extreme_angle()` once there's real angled-photo data to calibrate against.

Nothing above was rushed past — the Kylie Jenner fix in particular was checked against the actual live sites before and after, not just theorized. Sleep well.
