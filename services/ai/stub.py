from __future__ import annotations

from pathlib import Path

from services.ai.base import AICoder, ProposedChange


class StubAICoder(AICoder):
    """Deterministic AI behavior for MVP development/testing."""

    async def propose_changes(self, prompt: str, repo_root: str) -> ProposedChange:
        normalized = prompt.lower()
        files: dict[str, str] = {}

        if "health" in normalized and "fastapi" in normalized:
            app_file = self._find_fastapi_app(repo_root) or "main.py"
            existing = Path(repo_root, app_file).read_text() if Path(repo_root, app_file).exists() else ""
            snippet = "\n\n@app.get(\"/health\")\ndef health() -> dict[str, str]:\n    return {\"status\": \"ok\"}\n"
            if "@app.get(\"/health\")" not in existing:
                files[app_file] = existing.rstrip() + snippet + "\n"
                summary = "Added /health endpoint to FastAPI app"
            else:
                summary = "Health endpoint already exists"
        else:
            readme = Path(repo_root, "README.md")
            content = readme.read_text() if readme.exists() else "# Repository\n"
            content += f"\n\n## Assistant Note\n- Request: {prompt}\n"
            files["README.md"] = content
            summary = "Added assistant note to README as placeholder change"

        return ProposedChange(summary=summary, files=files)

    async def explain(self, prompt: str, repo_root: str) -> str:
        return (
            "I will analyze the repository, propose safe file changes, and produce a diff. "
            f"Prompt interpreted as: '{prompt}'."
        )

    @staticmethod
    def _find_fastapi_app(repo_root: str) -> str | None:
        candidates = ["main.py", "app/main.py", "src/main.py"]
        for candidate in candidates:
            p = Path(repo_root, candidate)
            if p.exists() and "FastAPI" in p.read_text(errors="ignore"):
                return candidate
        return None
