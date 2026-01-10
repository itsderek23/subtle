import pytest
from pathlib import Path

from subtle.models import SessionLogFile

PROJECTS_DIR = Path.home() / ".claude" / "projects"


@pytest.mark.skipif(not PROJECTS_DIR.exists(), reason="No Claude Code logs found")
class TestRealLogs:
    def test_all_sessions_parse_without_exceptions(self):
        sessions = SessionLogFile.all()
        stats = {
            "sessions": 0,
            "commits": 0,
            "tool_loc_added": 0,
            "tool_loc_removed": 0,
            "git_loc_added": 0,
            "git_loc_removed": 0,
            "sessions_with_commits": 0,
            "sessions_with_git_loc": 0,
        }

        for session in sessions:
            stats["sessions"] += 1

            commit_count = session.commit_count
            stats["commits"] += commit_count
            if commit_count > 0:
                stats["sessions_with_commits"] += 1

            tool_loc = session.tool_loc
            stats["tool_loc_added"] += tool_loc["added"]
            stats["tool_loc_removed"] += tool_loc["removed"]

            git_loc = session.git_loc
            if git_loc:
                stats["sessions_with_git_loc"] += 1
                stats["git_loc_added"] += git_loc["added"]
                stats["git_loc_removed"] += git_loc["removed"]

        print("\n=== Real Logs Integration Test Summary ===")
        print(f"Sessions processed: {stats['sessions']}")
        print(f"Total commits found: {stats['commits']}")
        print(f"Sessions with commits: {stats['sessions_with_commits']}")
        print(f"Tool LOC: +{stats['tool_loc_added']} / -{stats['tool_loc_removed']}")
        print(f"Git LOC: +{stats['git_loc_added']} / -{stats['git_loc_removed']}")
        print(f"Sessions with git LOC data: {stats['sessions_with_git_loc']}")

        assert stats["sessions"] >= 0

    def test_message_properties_dont_raise(self):
        sessions = SessionLogFile.all()[:10]

        for session in sessions:
            for msg in session.messages():
                _ = msg.edit_loc
                _ = msg.write_loc
                _ = msg.is_commit
                _ = msg.commit_info
                _ = msg.git_diff_loc
