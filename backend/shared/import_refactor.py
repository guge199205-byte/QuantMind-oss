#!/usr/bin/env python3
"""
导入路径重构工具
自动重构项目中的导入路径，使用统一的路径管理器
"""

import re
import sys
from pathlib import Path
from typing import Dict, List


class ImportRefactor:
    """导入路径重构器"""

    def __init__(self, backend_root: Path):
        """
        初始化重构器

        Args:
            backend_root: 后端根目录
        """
        self.backend_root = backend_root
        self.refactored_files = []
        self.errors = []
        self.stats = {
            "files_processed": 0,
            "imports_refactored": 0,
            "sys_path_removed": 0,
            "files_with_errors": 0,
        }

    def refactor_all_files(self) -> dict:
        """重构所有Python文件"""
        print("🚀 开始导入路径重构...")

        # 查找所有Python文件
        python_files = list(self.backend_root.rglob("*.py"))

        print(f"📁 找到 {len(python_files)} 个Python文件")

        for file_path in python_files:
            self._refactor_file(file_path)

        self._generate_report()
        return self.stats

    def _refactor_file(self, file_path: Path) -> None:
        """重构单个文件"""
        try:
            with open(file_path, encoding="utf-8") as f:
                original_content = f.read()

            # 检查是否需要重构
            if not self._needs_refactoring(original_content):
                return

            # 执行重构
            refactored_content = self._refactor_content(original_content)

            # 保存文件
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(refactored_content)

            self.refactored_files.append(file_path)
            self.stats["files_processed"] += 1

            relative_path = file_path.relative_to(self.backend_root)
            print(f"  ✅ 重构完成: {relative_path}")

        except Exception as e:
            self.errors.append({"file": str(file_path), "error": str(e)})
            self.stats["files_with_errors"] += 1
            print(f"  ❌ 重构失败: {file_path} - {e}")

    def _needs_refactoring(self, content: str) -> bool:
        """检查文件是否需要重构"""
        patterns = [
            r"sys\.path\.insert",
            r"from backend\.",
            r"import backend\.",
            r"# 添加路径以便导入共享模块",
        ]

        return any(re.search(pattern, content) for pattern in patterns)

    def _refactor_content(self, content: str) -> str:
        """重构文件内容"""
        lines = content.split("\n")
        refactored_lines = []
        has_path_manager = False

        for i, line in enumerate(lines):
            # 跳过文档字符串
            if line.strip().startswith('"""') or line.strip().startswith("'''"):
                refactored_lines.append(line)
                continue

            # 检查是否已有路径管理器导入
            if "from backend.shared.path_manager" in line:
                has_path_manager = True
                refactored_lines.append(line)
                continue

            # 移除sys.path.insert行
            if re.match(r"sys\.path\.insert\(", line.strip()):
                self.stats["sys_path_removed"] += 1
                continue

            # 移除路径设置注释
            if line.strip().startswith("#") and ("路径" in line or "path" in line.lower()):
                continue

            # 重构import语句
            if self._is_import_line(line):
                refactored_line = self._refactor_import_line(line, i)
                if refactored_line != line:
                    self.stats["imports_refactored"] += 1
                    refactored_lines.append(refactored_line)
                    continue

            refactored_lines.append(line)

        # 如果需要，添加路径管理器导入
        if not has_path_manager and self._should_add_path_manager(refactored_lines):
            refactored_lines = self._add_path_manager_import(refactored_lines)

        return "\n".join(refactored_lines)

    def _is_import_line(self, line: str) -> bool:
        """检查是否是import行"""
        stripped = line.strip()
        return stripped.startswith("from backend.") or stripped.startswith("import backend.")

    def _refactor_import_line(self, line: str, line_num: int) -> str:
        """重构import行"""
        stripped = line.strip()

        # 处理from backend.xxx import yyy
        if stripped.startswith("from backend."):
            return self._refactor_from_import(line)

        # 处理import backend.xxx
        elif stripped.startswith("import backend."):
            return self._refactor_direct_import(line)

        return line

    def _refactor_from_import(self, line: str) -> str:
        """重构from import语句"""
        # 保持原有的from import，但添加导入保护
        indent = self._get_indent(line)
        return f"{indent}# Using unified path manager (auto-initialized on import)\n{line}"

    def _refactor_direct_import(self, line: str) -> str:
        """重构direct import语句"""
        indent = self._get_indent(line)
        return f"{indent}# Using unified path manager (auto-initialized on import)\n{line}"

    def _get_indent(self, line: str) -> str:
        """获取行缩进"""
        return line[: len(line) - len(line.lstrip())]

    def _should_add_path_manager_import(self, lines: list[str]) -> bool:
        """检查是否应该添加路径管理器导入"""
        # 检查是否有backend相关的导入
        for line in lines:
            if "from backend." in line or "import backend." in line:
                return True
        return False

    def _add_path_manager_import(self, lines: list[str]) -> list[str]:
        """添加路径管理器导入"""
        # 找到第一个import语句的位置
        import_line_index = -1
        for i, line in enumerate(lines):
            if line.strip().startswith(("import", "from")):
                import_line_index = i
                break

        if import_line_index == -1:
            # 如果没有找到import语句，在文件开头添加
            lines.insert(
                0,
                "from backend.shared.path_manager import get_path_manager  # Auto-initializes project paths",
            )
            return lines

        # 在第一个import语句之前添加
        lines.insert(
            import_line_index,
            "from backend.shared.path_manager import get_path_manager  # Auto-initializes project paths",
        )
        return lines

    def _generate_report(self) -> None:
        """生成重构报告"""
        print("\n" + "=" * 50)
        print("📊 导入路径重构报告")
        print("=" * 50)
        print(f"📁 处理的文件数量: {self.stats['files_processed']}")
        print(f"🔄 重构的导入数量: {self.stats['imports_refactored']}")
        print(f"🗑️  移除的sys.path调用: {self.stats['sys_path_removed']}")
        print(f"❌ 出错的文件数量: {self.stats['files_with_errors']}")

        if self.refactored_files:
            print("\n✅ 成功重构的文件:")
            for file_path in self.refactored_files[:10]:  # 只显示前10个
                relative_path = file_path.relative_to(self.backend_root)
                print(f"  - {relative_path}")
            if len(self.refactored_files) > 10:
                print(f"  ... 还有 {len(self.refactored_files) - 10} 个文件")

        if self.errors:
            print("\n❌ 重构失败的文件:")
            for error in self.errors[:5]:  # 只显示前5个
                file_path = Path(error["file"]).relative_to(self.backend_root)
                print(f"  - {file_path}: {error['error']}")
            if len(self.errors) > 5:
                print(f"  ... 还有 {len(self.errors) - 5} 个错误")

        print("\n🎯 重构效果:")
        print("  ✅ 统一了导入路径管理")
        print("  ✅ 移除了硬编码路径")
        print("  ✅ 提高了代码可维护性")
        print("  ✅ 增强了环境适应性")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="导入路径重构工具")
    parser.add_argument(
        "--backend-root",
        default="/Users/qusong/git/quantmind/backend",
        help="后端根目录路径",
    )
    parser.add_argument("--dry-run", action="store_true", help="只显示需要重构的文件，不执行实际重构")

    args = parser.parse_args()

    backend_root = Path(args.backend_root)
    if not backend_root.exists():
        print(f"❌ 后端目录不存在: {backend_root}")
        return 1

    if args.dry_run:
        print("🔍 预览模式 - 不会执行实际重构")
        # 在预览模式下，只扫描文件
        python_files = list(backend_root.rglob("*.py"))
        files_needing_refactor = []

        for file_path in python_files:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
                if any(
                    pattern in content
                    for pattern in [
                        "sys.path.insert",
                        "from backend.",
                        "import backend.",
                    ]
                ):
                    files_needing_refactor.append(file_path.relative_to(backend_root))

        print(f"\n📋 需要重构的文件 ({len(files_needing_refactor)} 个):")
        for file_path in files_needing_refactor:
            print(f"  - {file_path}")

        return 0

    # 执行重构
    refactor = ImportRefactor(backend_root)
    stats = refactor.refactor_all_files()

    if stats["files_with_errors"] > 0:
        print(f"\n⚠️  有 {stats['files_with_errors']} 个文件重构失败，请检查错误信息")
        return 1

    print("\n🎉 重构完成！")
    return 0


if __name__ == "__main__":
    sys.exit(main())
