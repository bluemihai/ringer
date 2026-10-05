#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def toml_string(value: object) -> str:
    return json.dumps(str(value))


class WorkerEnvMarkerTests(unittest.TestCase):
    def test_worker_process_sees_ringer_worker_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            home = root / "home"
            ringer_home = root / "ringer-home"
            workdir = root / "work"
            config_path = root / "config.toml"
            manifest_path = root / "manifest.json"

            home.mkdir()
            ringer_home.mkdir()

            config_path.write_text(
                "\n".join(
                    [
                        f"state_dir = {toml_string(root / 'state')}",
                        "",
                        "[eval]",
                        'backend = "jsonl"',
                        f"jsonl_path = {toml_string(root / 'runs.jsonl')}",
                        "",
                        "[artifact]",
                        "enabled = false",
                        "",
                        "[engines.envprobe]",
                        'bin = "/bin/sh"',
                        "args_template = [",
                        '  "-c",',
                        '  "printf %s \\"$RINGER_WORKER\\" > marker.txt",',
                        '  "sh",',
                        '  "{spec}",',
                        "]",
                        "sandbox_args = []",
                        "full_access_args = []",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            manifest_path.write_text(
                json.dumps(
                    {
                        "run_name": "worker-env-marker-test",
                        "workdir": str(workdir),
                        "max_parallel": 1,
                        "worktrees": False,
                        "tasks": [
                            {
                                "key": "marker-task",
                                "engine": "envprobe",
                                "spec": (
                                    "Write the value of the RINGER_WORKER environment "
                                    "variable to marker.txt so the check can verify it."
                                ),
                                "check": (
                                    "grep -qx 1 marker.txt || "
                                    "{ echo FAIL: marker.txt does not hold 1; exit 1; }"
                                ),
                                "expect_files": ["marker.txt"],
                            },
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            env = os.environ.copy()
            env.pop("RINGER_WORKER", None)
            env["RINGER_NO_SELF_UPDATE"] = "1"
            env["HOME"] = str(home)
            env["RINGER_HOME"] = str(ringer_home)
            env["XDG_CONFIG_HOME"] = str(root / "xdg-config")

            proc = subprocess.run(
                [
                    sys.executable,
                    "ringer.py",
                    "run",
                    str(manifest_path),
                    "--config",
                    str(config_path),
                    "--no-dashboard",
                    "--identity",
                    "env-marker-test",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )

            combined_output = proc.stdout + proc.stderr
            self.assertEqual(0, proc.returncode, combined_output)
            marker = workdir / "marker-task" / "marker.txt"
            self.assertTrue(marker.is_file(), combined_output)
            self.assertEqual("1", marker.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
