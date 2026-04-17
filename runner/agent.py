from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import difflib

from backend.schemas import ParsedMessage, RunnerResult
from services.ai.base import AICoder
from services.git_service import WorkspaceManager


@dataclass
class PendingChange:
    workspace: Path
    branch: str
    files: dict[str, str]
    summary: str


class RunnerAgent:
    def __init__(self, workspace_manager: WorkspaceManager, ai: AICoder) -> None:
        self.workspace_manager = workspace_manager
        self.ai = ai
        self.pending_by_user: dict[str, PendingChange] = {}

    async def run(self, message: ParsedMessage) -> RunnerResult:
        workspace = self.workspace_manager.ensure_workspace(message.repo)
        branch = self.workspace_manager.ensure_feature_branch(workspace, message.session_id)

        if message.command == "explain":
            explanation = await self.ai.explain(message.prompt, str(workspace))
            return RunnerResult(
                summary=explanation,
                files_changed=[],
                diff="",
                requires_approval=False,
                branch=branch,
            )

        if message.command == "apply":
            return await self._apply_pending(message.user_id)

        proposal = await self.ai.propose_changes(message.prompt, str(workspace))
        diff_text, files_changed = self._build_diff(workspace, proposal.files)
        self.pending_by_user[message.user_id] = PendingChange(
            workspace=workspace,
            branch=branch,
            files=proposal.files,
            summary=proposal.summary,
        )

        return RunnerResult(
            summary=proposal.summary,
            files_changed=files_changed,
            diff=diff_text,
            requires_approval=True,
            branch=branch,
        )

    async def _apply_pending(self, user_id: str) -> RunnerResult:
        pending = self.pending_by_user.get(user_id)
        if not pending:
            return RunnerResult(
                summary="No pending change found. Send DIFF with a prompt first.",
                files_changed=[],
                diff="",
                requires_approval=False,
                branch="n/a",
            )

        for rel_path, content in pending.files.items():
            target = pending.workspace / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)

        commit_sha = self.workspace_manager.commit_changes(
            pending.workspace,
            f"feat: whatsapp assistant apply - {pending.summary}",
        )
        diff_after = self.workspace_manager.diff(pending.workspace)
        changed = self.workspace_manager.changed_files(pending.workspace)
        del self.pending_by_user[user_id]

        return RunnerResult(
            summary=f"Applied and committed changes ({commit_sha[:8]}).",
            files_changed=changed,
            diff=diff_after,
            requires_approval=False,
            branch=pending.branch,
        )

    @staticmethod
    def _build_diff(workspace: Path, files: dict[str, str]) -> tuple[str, list[str]]:
        all_diffs: list[str] = []
        changed: list[str] = []
        for rel_path, new_content in files.items():
            file_path = workspace / rel_path
            before = file_path.read_text().splitlines(keepends=True) if file_path.exists() else []
            after = new_content.splitlines(keepends=True)
            if before == after:
                continue
            changed.append(rel_path)
            one_diff = difflib.unified_diff(
                before,
                after,
                fromfile=f"a/{rel_path}",
                tofile=f"b/{rel_path}",
            )
            all_diffs.append("".join(one_diff))

        return "\n".join(all_diffs), changed
