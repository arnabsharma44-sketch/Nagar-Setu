# ROADGUARD AI — Bug Register

**Last Updated:** 2026-11-18
**Branch:** fix/full-system-debug-audit

---

## Bug Classification

| ID | Severity | Module | Status | Description |
|----|----------|--------|--------|-------------|
| BUG-001 | P2 | frontend/api.ts | Open | Potential infinite retry loop on 401 |
| BUG-002 | P2 | frontend/session.tsx | ✅ Fixed | Redirect loop on network errors |
| BUG-003 | P2 | frontend/useApi.ts | ✅ Fixed | Null path handling inconsistency |
| BUG-004 | P2 | frontend/AppShell.tsx | ✅ Fixed | Navigation active state bug |
| BUG-005 | P2 | frontend/videos/page.tsx | Open | Upload cleanup on navigation |
| BUG-006 | P2 | backend/videos.py | ✅ Fixed | Idempotency key missing config |
| BUG-007 | P2 | backend/videos.py | ✅ Fixed | Race condition in complete_upload |
| BUG-008 | P2 | worker/runner.py | ✅ Fixed | Progress updates create new session |
| BUG-009 | P2 | worker/runner.py | ✅ Fixed | _fail sets wrong stage |
| BUG-010 | P2 | worker/runner.py | ✅ Fixed | Job lease not extended |

---

## Legend

- **P0 - CRITICAL**: Cross-tenant exposure, auth bypass, privilege escalation, credential leak, data corruption
- **P1 - HIGH**: Core workflow failure, unauthorized sensitive ops, incorrect investigation, video corruption, security vulns, DB integrity
- **P2 - MEDIUM**: Incorrect UI behavior, non-critical API failures, incorrect analytics, recoverable worker errors, missing validation
- **P3 - LOW**: Minor layout defects, cosmetic issues, minor performance improvements

---

## Fixed Bugs (This Session)

| ID | Severity | Module | Description | Fix | Regression Test |
|----|----------|--------|-------------|-----|-----------------|
| FIX-001 | P2 | ai-engine/video/rtsp_adapter | Import sorting, type syntax, exception chaining | Ruff --fix applied | ruff check passes |
| FIX-002 | P2 | apps/api/app/services/cameras | Exception chaining in RTSP session start | Added `from e` to raise statements | pytest tests/ -v passes |
| FIX-003 | P2 | apps/web/next-env.d.ts | Minor TypeScript reference update | Updated import | tsc --noEmit clean |
| FIX-004 | P2 | apps/web/components/AppShell.tsx | Navigation active state bug | Fixed startsWith check | Build passes |
| FIX-005 | P2 | apps/web/lib/useApi.ts | Null path handling inconsistency | Fixed path transitions | TypeScript clean |
| FIX-006 | P2 | apps/web/lib/session.tsx | Redirect loop on network errors | Check 401 status before redirect | Integration tests pass |
| FIX-007 | P2 | apps/api/app/services/videos.py | Idempotency key missing config | Added all config params | Tests pass |
| FIX-008 | P2 | apps/api/app/services/videos.py | Race condition in complete_upload | SELECT FOR UPDATE | Tests pass |
| FIX-009 | P2 | ai-engine/ai_engine/workers/runner.py | Progress updates create new session | Cached session factory | Tests pass |
| FIX-010 | P2 | ai-engine/ai_engine/workers/runner.py | _fail sets wrong stage | Set stage to FAILED | Tests pass |
| FIX-011 | P2 | ai-engine/ai_engine/workers/runner.py | Job lease not extended | Extended lease on progress | Tests pass |

---

## Open Bugs (Discovered During Audit)

### BUG-001

**Severity:** P2
**Module:** apps/web/lib/api.ts
**Issue:** Potential infinite retry loop on 401

**Reproduction:**
1. User session expires
2. API call returns 401
3. `request()` calls `refreshSession()`
4. If refresh also returns 401 (e.g., refresh token expired), the retry logic doesn't prevent re-retrying

**Expected:** Should only retry once, then propagate error
**Actual:** Could loop if refresh succeeds but subsequent request also 401s

**Root Cause:** The `allowRetry` flag only prevents one retry, but doesn't handle the case where refresh succeeds but the new access token is also invalid

**Fix:** Track retry count or use a more robust retry mechanism

**Regression Test:** test_401_retry_logic

**Status:** Open

---

### BUG-005

**Severity:** P2
**Module:** apps/web/app/command/videos/page.tsx
**Issue:** Upload cleanup on navigation

**Reproduction:**
1. Start video upload (stage: signing → uploading → completing → processing)
2. Navigate away from page before upload completes
2. Upload continues in background but no UI feedback
3. No cancellation or cleanup

**Expected:** Should cancel upload or warn user
**Actual:** Silent background continuation

**Root Cause:** No cleanup in useEffect return, no beforeunload handler

**Fix:** Add cleanup logic or warning

**Regression Test:** test_upload_cleanup_on_navigate

**Status:** Open