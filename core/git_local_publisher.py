import subprocess
import os
from pathlib import Path
from typing import Dict, Any, List
from .database import Database

class LocalGitPublisher:
    def __init__(self, repo_dir: str = "."):
        self.repo_dir = Path(repo_dir).resolve()

    def run_git_cmd(self, args: List[str]) -> Dict[str, Any]:
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            return {
                "success": res.returncode == 0,
                "stdout": res.stdout.strip(),
                "stderr": res.stderr.strip()
            }
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e)}

    def sync_and_push(self, commit_msg: str = "🤖 Update daily Galectin digest docs") -> Dict[str, Any]:
        # Check if git is initialized
        if not (self.repo_dir / ".git").exists():
            init_res = self.run_git_cmd(["init"])
            if not init_res["success"]:
                return {"success": False, "message": f"Git init 失敗: {init_res['stderr']}"}
        
        # Add docs and relevant files
        self.run_git_cmd(["add", "docs"])
        
        # Check status
        status_res = self.run_git_cmd(["status", "--porcelain"])
        if not status_res["stdout"]:
            return {"success": True, "message": "docs 沒有變更需要提交。"}

        # Commit
        commit_res = self.run_git_cmd(["commit", "-m", commit_msg])
        if not commit_res["success"]:
            return {"success": False, "message": f"Git commit 失敗: {commit_res['stderr']}"}

        # Check if remote origin exists
        remote_res = self.run_git_cmd(["remote", "get-url", "origin"])
        if not remote_res["success"]:
            return {
                "success": True,
                "message": "已完成本地 Git Commit。請設定 remote origin 後即可自動 push。",
                "needs_remote": True
            }

        branch_res = self.run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"])
        branch = branch_res["stdout"] if branch_res["success"] and branch_res["stdout"] else "main"

        push_res = self.run_git_cmd(["push", "-u", "origin", branch])
        if not push_res["success"]:
            push_res = self.run_git_cmd(["push", "-u", "origin", "main"])
        if not push_res["success"]:
            push_res = self.run_git_cmd(["push", "-u", "origin", "master"])

        if push_res["success"]:
            return {"success": True, "message": "成功推送至 GitHub！"}
        else:
            return {"success": False, "message": f"Git push 失敗: {push_res['stderr']}"}
