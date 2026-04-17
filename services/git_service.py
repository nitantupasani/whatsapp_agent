from __future__ import annotations

from pathlib import Path

from git import Repo


class WorkspaceManager:
    def __init__(self, repos_root: str) -> None:
        self.repos_root = Path(repos_root).resolve()
        self.repos_root.mkdir(parents=True, exist_ok=True)

    def ensure_workspace(self, repo_name: str) -> Path:
        safe_name = repo_name.replace("..", "").strip("/")
        workspace = (self.repos_root / safe_name).resolve()
        if not str(workspace).startswith(str(self.repos_root)):
            raise ValueError("Invalid repo path")
        workspace.mkdir(parents=True, exist_ok=True)

        git_dir = workspace / ".git"
        if not git_dir.exists():
            repo = Repo.init(workspace)
            readme = workspace / "README.md"
            if not readme.exists():
                readme.write_text(f"# {safe_name}\n")
            repo.index.add([str(readme.relative_to(workspace))])
            repo.index.commit("chore: initialize workspace")
        return workspace

    @staticmethod
    def ensure_feature_branch(workspace: Path, session_id: str) -> str:
        repo = Repo(workspace)
        branch = f"feature/whatsapp-{session_id}"
        if repo.active_branch.name != branch:
            if branch in [h.name for h in repo.heads]:
                repo.git.checkout(branch)
            else:
                repo.git.checkout("-b", branch)
        return branch

    @staticmethod
    def diff(workspace: Path) -> str:
        repo = Repo(workspace)
        return repo.git.diff()

    @staticmethod
    def changed_files(workspace: Path) -> list[str]:
        repo = Repo(workspace)
        return [item.a_path for item in repo.index.diff(None)]

    @staticmethod
    def commit_changes(workspace: Path, message: str) -> str:
        repo = Repo(workspace)
        if repo.active_branch.name in {"main", "master"}:
            raise RuntimeError("Direct commits to main/master are forbidden")
        repo.git.add(A=True)
        commit = repo.index.commit(message)
        return commit.hexsha
