# Pydantic Settings Refactor

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate PlatformConfig to pydantic-settings BaseSettings so env vars and .env files work automatically. Update get_secret() to read from env vars with PYFLOW_ prefix.

**Architecture:** PlatformConfig becomes BaseSettings with env_prefix="PYFLOW_", env_file=".env". get_secret() checks env vars first (PYFLOW_{NAME} uppercase), falls back to _PLATFORM_SECRETS dict. Secrets dict kept as secondary option.

**Tech Stack:** pydantic-settings, python-dotenv (included with pydantic-settings[dotenv])

---

### Task 1: Add pydantic-settings to dependencies

**Files:**
- Modify: `pyproject.toml`

Add `"pydantic-settings>=2.0"` to dependencies list.

Commit: `chore: add pydantic-settings to dependencies`

---

### Task 2: Migrate PlatformConfig to BaseSettings

**Files:**
- Modify: `pyflow/models/platform.py`
- Modify: `tests/models/test_platform.py`

Change PlatformConfig from `BaseModel` to `BaseSettings`. Add SettingsConfigDict with env_prefix="PYFLOW_", env_file=".env". Keep all existing fields including `secrets: dict[str, str]`.

Tests: verify env vars override defaults (monkeypatch PYFLOW_PORT, PYFLOW_LOG_LEVEL), verify .env loading, verify existing tests still pass.

Commit: `feat: migrate PlatformConfig to BaseSettings`

---

### Task 3: Update get_secret() to check env vars

**Files:**
- Modify: `pyflow/tools/base.py`
- Modify: `tests/tools/test_base.py`

Update get_secret() to check env var `PYFLOW_{name.upper()}` first, fall back to _PLATFORM_SECRETS dict.

Tests: verify env var takes priority, verify dict fallback still works, verify None when neither exists.

Commit: `feat: get_secret reads env vars with PYFLOW_ prefix`

---

### Task 4: Add .env.example and verify full suite

**Files:**
- Create: `.env.example`

Create example file showing available env vars. Run full test suite.

Commit: `docs: add .env.example with available config vars`
