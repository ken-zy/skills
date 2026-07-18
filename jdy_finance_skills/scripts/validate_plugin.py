#!/usr/bin/env python3
"""
插件市场结构验证脚本
验证所有子插件的 skill、command、MCP 配置、plugin.json 的结构完整性
"""

import json
import re
import sys
from pathlib import Path


# 子插件列表
SUB_PLUGINS = ["tradfi", "crypto", "macro", "portfolio"]

# CLAUDE.md 中各子插件的命令映射（真实来源）
EXPECTED_COMMANDS = {
    "tradfi": ["comps", "dcf", "earnings", "screen", "thesis", "model-update", "debug-model"],
    "crypto": ["token", "defi", "airdrop", "onchain"],
    "macro": ["dashboard", "morning", "catalyst"],
    "portfolio": ["rebalance", "tlh"],
}


class PluginValidator:
    def __init__(self, root: Path, verbose: bool = False):
        self.root = root
        self.verbose = verbose
        self.errors = []
        self.warnings = []
        self.info = []
        self.checks = []

    def validate_all(self) -> dict:
        self.check_plugin_json()
        self.check_mcp_json()
        self.check_skill_frontmatter()
        self.check_command_metadata()
        self.check_command_table_consistency()
        self.check_fallback_order()
        self.check_output_naming()

        return {
            "status": "FAIL" if self.errors else "PASS",
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "checks": self.checks,
        }

    # ── plugin.json ──────────────────────────────────────────

    def check_plugin_json(self):
        check = {"check": "plugin_json", "status": "PASS", "details": []}
        required_fields = ["name", "version", "description"]

        for plugin in SUB_PLUGINS:
            path = self.root / plugin / ".claude-plugin" / "plugin.json"
            if not path.exists():
                check["details"].append(f"MISSING: {path.relative_to(self.root)}")
                self.errors.append(f"plugin.json missing: {plugin}")
                continue

            try:
                data = json.loads(path.read_text())
                for field in required_fields:
                    if field not in data:
                        msg = f"{plugin}/plugin.json missing field: {field}"
                        check["details"].append(f"ERROR: {msg}")
                        self.errors.append(msg)
                    elif self.verbose:
                        check["details"].append(f"OK: {plugin}/plugin.json has {field}")
            except json.JSONDecodeError as e:
                msg = f"{plugin}/plugin.json invalid JSON: {e}"
                check["details"].append(f"ERROR: {msg}")
                self.errors.append(msg)

        if any(d.startswith("ERROR") or d.startswith("MISSING") for d in check["details"]):
            check["status"] = "FAIL"
        self.checks.append(check)

    # ── .mcp.json ────────────────────────────────────────────

    def check_mcp_json(self):
        check = {"check": "mcp_json", "status": "PASS", "details": []}

        for plugin in SUB_PLUGINS:
            path = self.root / plugin / ".mcp.json"
            if not path.exists():
                check["details"].append(f"MISSING: {plugin}/.mcp.json")
                self.errors.append(f".mcp.json missing: {plugin}")
                continue

            try:
                data = json.loads(path.read_text())
                servers = data.get("mcpServers", {})

                for name, config in servers.items():
                    server_type = config.get("type", "")
                    has_command = "command" in config
                    has_url = "url" in config

                    if server_type == "stdio" and not has_command:
                        msg = f"{plugin}/.mcp.json: {name} type=stdio but missing command"
                        check["details"].append(f"ERROR: {msg}")
                        self.errors.append(msg)
                    elif server_type == "http" and has_command and not has_url:
                        msg = f"{plugin}/.mcp.json: {name} type=http but has command/args instead of url"
                        check["details"].append(f"ERROR: {msg}")
                        self.errors.append(msg)
                    elif server_type == "http" and not has_url:
                        msg = f"{plugin}/.mcp.json: {name} type=http but missing url"
                        check["details"].append(f"ERROR: {msg}")
                        self.errors.append(msg)
                    elif self.verbose:
                        check["details"].append(f"OK: {plugin}/{name} type={server_type} config valid")

            except json.JSONDecodeError as e:
                msg = f"{plugin}/.mcp.json invalid JSON: {e}"
                check["details"].append(f"ERROR: {msg}")
                self.errors.append(msg)

        if any(d.startswith("ERROR") or d.startswith("MISSING") for d in check["details"]):
            check["status"] = "FAIL"
        self.checks.append(check)

    # ── Skill frontmatter ────────────────────────────────────

    def check_skill_frontmatter(self):
        check = {"check": "skill_frontmatter", "status": "PASS", "details": []}

        for plugin in SUB_PLUGINS:
            skills_dir = self.root / plugin / "skills"
            if not skills_dir.exists():
                continue

            for skill_dir in sorted(skills_dir.iterdir()):
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    continue

                content = skill_md.read_text()
                rel_path = skill_md.relative_to(self.root)

                # 检查 YAML frontmatter: 必须以 --- 开头
                has_frontmatter = content.startswith("---")
                if not has_frontmatter:
                    msg = f"{rel_path}: missing YAML frontmatter delimiters (---)"
                    check["details"].append(f"ERROR: {msg}")
                    self.errors.append(msg)
                    continue

                # 提取 frontmatter
                parts = content.split("---", 2)
                if len(parts) < 3:
                    msg = f"{rel_path}: malformed YAML frontmatter (missing closing ---)"
                    check["details"].append(f"ERROR: {msg}")
                    self.errors.append(msg)
                    continue

                frontmatter = parts[1]
                has_name = bool(re.search(r"^name:", frontmatter, re.MULTILINE))
                has_desc = bool(re.search(r"^description:", frontmatter, re.MULTILINE))

                if not has_name:
                    msg = f"{rel_path}: frontmatter missing 'name:'"
                    check["details"].append(f"ERROR: {msg}")
                    self.errors.append(msg)
                if not has_desc:
                    msg = f"{rel_path}: frontmatter missing 'description:'"
                    check["details"].append(f"ERROR: {msg}")
                    self.errors.append(msg)
                if has_name and has_desc and self.verbose:
                    check["details"].append(f"OK: {rel_path} frontmatter valid")

        if any(d.startswith("ERROR") for d in check["details"]):
            check["status"] = "FAIL"
        self.checks.append(check)

    # ── Command metadata ─────────────────────────────────────

    def check_command_metadata(self):
        check = {"check": "command_metadata", "status": "PASS", "details": []}
        required_fields = ["description", "allowed-tools"]

        for plugin in SUB_PLUGINS:
            cmd_dir = self.root / plugin / "commands"
            if not cmd_dir.exists():
                continue

            for cmd_file in sorted(cmd_dir.glob("*.md")):
                content = cmd_file.read_text()
                rel_path = cmd_file.relative_to(self.root)

                # command 文件也用 YAML frontmatter
                if not content.startswith("---"):
                    msg = f"{rel_path}: missing YAML frontmatter"
                    check["details"].append(f"ERROR: {msg}")
                    self.errors.append(msg)
                    continue

                parts = content.split("---", 2)
                if len(parts) < 3:
                    msg = f"{rel_path}: malformed YAML frontmatter"
                    check["details"].append(f"ERROR: {msg}")
                    self.errors.append(msg)
                    continue

                frontmatter = parts[1]
                for field in required_fields:
                    if not re.search(rf"^{field}:", frontmatter, re.MULTILINE):
                        msg = f"{rel_path}: frontmatter missing '{field}'"
                        check["details"].append(f"ERROR: {msg}")
                        self.errors.append(msg)

                if not any(d.startswith("ERROR") and str(rel_path) in d for d in check["details"]):
                    if self.verbose:
                        check["details"].append(f"OK: {rel_path} metadata valid")

        if any(d.startswith("ERROR") for d in check["details"]):
            check["status"] = "FAIL"
        self.checks.append(check)

    # ── CLAUDE.md 命令表 vs 实际文件 ─────────────────────────

    def check_command_table_consistency(self):
        check = {"check": "command_table_consistency", "status": "PASS", "details": []}

        for plugin in SUB_PLUGINS:
            cmd_dir = self.root / plugin / "commands"
            if not cmd_dir.exists():
                actual_cmds = set()
            else:
                actual_cmds = {f.stem for f in cmd_dir.glob("*.md")}

            expected_cmds = set(EXPECTED_COMMANDS.get(plugin, []))

            missing = expected_cmds - actual_cmds
            extra = actual_cmds - expected_cmds

            for cmd in sorted(missing):
                msg = f"{plugin}: CLAUDE.md lists /{cmd} but commands/{cmd}.md not found"
                check["details"].append(f"WARNING: {msg}")
                self.warnings.append(msg)

            for cmd in sorted(extra):
                msg = f"{plugin}: commands/{cmd}.md exists but not in CLAUDE.md command table"
                check["details"].append(f"WARNING: {msg}")
                self.warnings.append(msg)

            if not missing and not extra and self.verbose:
                check["details"].append(f"OK: {plugin} command table matches files")

        if any(d.startswith("WARNING") for d in check["details"]):
            check["status"] = "WARN"
        self.checks.append(check)

    # ── Fallback 顺序 ───────────────────────────────────────

    def check_fallback_order(self):
        check = {"check": "fallback_order", "status": "PASS", "details": []}

        for plugin in SUB_PLUGINS:
            skills_dir = self.root / plugin / "skills"
            if not skills_dir.exists():
                continue

            for skill_dir in sorted(skills_dir.iterdir()):
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    continue

                content = skill_md.read_text()
                rel_path = skill_md.relative_to(self.root)

                # 查找 Layer 1 标题后的内容
                layer1_match = re.search(
                    r"###\s*Layer\s*1[:\s]*(.*?)(?=###\s*Layer|$)",
                    content,
                    re.DOTALL | re.IGNORECASE,
                )
                if not layer1_match:
                    continue

                layer1_header = layer1_match.group(0).split("\n")[0].lower()
                if "web search" in layer1_header and "mcp" not in layer1_header:
                    msg = f"{rel_path}: Layer 1 is Web Search instead of MCP"
                    check["details"].append(f"WARNING: {msg}")
                    self.warnings.append(msg)
                elif self.verbose:
                    check["details"].append(f"OK: {rel_path} fallback order correct")

        if any(d.startswith("WARNING") for d in check["details"]):
            check["status"] = "WARN"
        self.checks.append(check)

    # ── Output 文件命名 ──────────────────────────────────────

    def check_output_naming(self):
        check = {"check": "output_naming", "status": "PASS", "details": []}
        # 匹配 YYYYMMDD- 开头的命名模式
        correct_pattern = re.compile(r"`YYYYMMDD-")

        for plugin in SUB_PLUGINS:
            cmd_dir = self.root / plugin / "commands"
            if not cmd_dir.exists():
                continue

            for cmd_file in sorted(cmd_dir.glob("*.md")):
                content = cmd_file.read_text()
                rel_path = cmd_file.relative_to(self.root)

                # 查找 Output 节
                output_match = re.search(
                    r"##\s*Output(.*?)(?=##\s|$)", content, re.DOTALL
                )
                if not output_match:
                    continue

                output_section = output_match.group(1)

                # 查找文件名模式（反引号包裹的 .md 或 .xlsx）
                file_patterns = re.findall(r"`([^`]+\.(?:md|xlsx))`", output_section)
                for pattern in file_patterns:
                    if not correct_pattern.search(f"`{pattern}"):
                        msg = f"{rel_path}: output filename '{pattern}' doesn't start with YYYYMMDD-"
                        check["details"].append(f"WARNING: {msg}")
                        self.warnings.append(msg)
                    elif self.verbose:
                        check["details"].append(f"OK: {rel_path} naming '{pattern}' correct")

        if any(d.startswith("WARNING") for d in check["details"]):
            check["status"] = "WARN"
        self.checks.append(check)


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    # 找到项目根目录
    script_dir = Path(__file__).resolve().parent
    root = script_dir.parent
    if not (root / ".claude-plugin").exists():
        print(f"Error: not a plugin project root: {root}")
        sys.exit(1)

    validator = PluginValidator(root, verbose=verbose)
    results = validator.validate_all()

    print(json.dumps(results, indent=2, ensure_ascii=False))

    # 摘要
    status = results["status"]
    errors = results["error_count"]
    warnings = results["warning_count"]
    total_checks = len(results["checks"])
    passed = sum(1 for c in results["checks"] if c["status"] == "PASS")

    print(f"\n{'='*50}")
    print(f"  Status: {status}")
    print(f"  Checks: {passed}/{total_checks} passed")
    print(f"  Errors: {errors}  Warnings: {warnings}")
    print(f"{'='*50}")

    sys.exit(0 if status == "PASS" else 1)


if __name__ == "__main__":
    main()
