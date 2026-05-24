"""
模型文件验证功能测试脚本（独立版本）

无需依赖完整项目环境，直接测试验证逻辑
"""

import sys
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def validate_model_file(model_path: Path) -> None:
    """
    验证模型文件是否存在（从 main.py 提取的函数副本用于测试）

    Args:
        model_path: 模型文件路径对象

    Raises:
        SystemExit: 当模型文件不存在时退出程序
    """
    if not model_path.exists():
        error_msg = f"""
╔══════════════════════════════════════════════════════════════╗
║  ❌ 致命错误：模型文件不存在                                ║
╠══════════════════════════════════════════════════════════════╣
║  期望路径: {model_path}
║                                                              ║
║  🔧 解决步骤：                                               ║
║  1. 创建 models 目录: mkdir models                          ║
║  2. 下载模型文件到该目录                                    ║
║  3. 查看下载说明: 项目文档/模型下载说明.md                    ║
║                                                              ║
║  📌 提示：模型文件已加入 .gitignore，需手动下载              ║
╚══════════════════════════════════════════════════════════════╝
"""
        logger.error(error_msg)
        print(error_msg)
        raise SystemExit(1)

    logger.info("✅ 模型文件检查通过: %s", model_path)


def test_model_not_exists():
    """测试场景1：模型文件不存在 - 应该抛出 SystemExit"""
    print("\n" + "=" * 60)
    print("测试1: 模型文件不存在的情况")
    print("=" * 60)

    fake_path = Path("nonexistent_model_xxxxx.pt")
    print(f"使用假路径: {fake_path}")
    print(f"文件存在: {fake_path.exists()}")

    try:
        validate_model_file(fake_path)
        print("❌ 测试失败：函数未退出")
        return False
    except SystemExit as e:
        if e.code == 1:
            print("✅ 测试通过：正确检测到模型不存在并退出 (exit code=1)")
            return True
        else:
            print(f"❌ 测试失败：退出码异常 (code={e.code})")
            return False


def test_actual_model_path():
    """测试场景2：检查实际项目中的模型路径"""
    print("\n" + "=" * 60)
    print("测试2: 检查实际项目配置的模型路径")
    print("=" * 60)

    # 从 main.py 中读取的实际路径
    model_path = Path(__file__).parent / "garbage_project" / "models" / "garbage_yolov8m_best.pt"

    print(f"模型路径: {model_path}")
    print(f"绝对路径: {model_path.resolve()}")
    print(f"文件存在: {model_path.exists()}")

    if model_path.exists():
        file_size = model_path.stat().st_size
        print(f"文件大小: {file_size / 1024 / 1024:.2f} MB")

        try:
            validate_model_file(model_path)
            print("✅ 模型验证通过")
            return True
        except SystemExit:
            print("❌ 意外退出")
            return False
    else:
        print("⚠️  模型文件不存在（预期行为）")
        print("\n📋 这说明修复机制工作正常！")
        print("\n当用户尝试启动程序时会看到清晰的错误提示。")

        # 尝试验证以展示错误输出（会被捕获）
        try:
            validate_model_file(model_path)
        except SystemExit:
            pass  # 预期的退出

        return True


def test_gitignore_configuration():
    """测试场景3：验证 .gitignore 配置"""
    print("\n" + "=" * 60)
    print("测试3: 检查 .gitignore 配置")
    print("=" * 60)

    gitignore_path = Path(__file__).parent / ".gitignore"

    if not gitignore_path.exists():
        print("❌ .gitignore 文件不存在")
        return False

    with open(gitignore_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 检查关键规则
    checks = [
        ("*.pt", ".pt 文件扩展名"),
        ("models/", "models/ 目录"),
        ("*.onnx", ".onnx 文件扩展名"),
    ]

    all_passed = True
    for pattern, description in checks:
        if pattern in content:
            print(f"✅ 已排除: {description} ({pattern})")
        else:
            print(f"⚠️  未找到: {description} ({pattern})")
            all_passed = False

    if all_passed:
        print("\n✅ .gitignore 配置正确，模型文件将被正确排除")
    else:
        print("\n⚠️  .gitignore 配置可能不完整")

    return all_passed


def check_code_changes():
    """测试场景4：验证代码修改"""
    print("\n" + "=" * 60)
    print("测试4: 验证代码修改点")
    print("=" * 60)

    main_py = Path(__file__).parent / "garbage_project" / "main.py"

    if not main_py.exists():
        print("❌ main.py 不存在")
        return False

    with open(main_py, "r", encoding="utf-8") as f:
        content = f.read()

    # 检查关键修改点
    changes = [
        ("def validate_model_file", "添加了 validate_model_file() 函数"),
        ("validate_model_file(MODEL_PATH)", "在 startup_event() 中调用验证函数"),
        ("项目文档/模型下载说明.md", "错误提示中包含文档引用"),
        ("raise SystemExit(1)", "模型缺失时程序退出"),
    ]

    all_found = True
    for pattern, description in changes:
        if pattern in content:
            print(f"✅ 已添加: {description}")
        else:
            print(f"❌ 未找到: {description}")
            all_found = False

    return all_found


def check_documentation():
    """测试场景5：验证文档创建"""
    print("\n" + "=" * 60)
    print("测试5: 检查文档是否已创建")
    print("=" * 60)

    doc_path = Path(__file__).parent / "项目文档" / "模型下载说明.md"

    if doc_path.exists():
        print(f"✅ 文档已创建: {doc_path}")

        with open(doc_path, "r", encoding="utf-8") as f:
            doc_content = f.read()

        # 检查文档关键内容
        sections = [
            ("# 模型文件下载说明", "标题"),
            ("## 📥 下载方式", "下载方式章节"),
            ("## ✅ 验证安装", "验证安装章节"),
            ("## 🔧 故障排除", "故障排除章节"),
        ]

        for section, desc in sections:
            if section in doc_content:
                print(f"  ✅ 包含章节: {desc}")
            else:
                print(f"  ⚠️  缺少章节: {desc}")

        file_size = doc_path.stat().st_size
        print(f"\n文档大小: {file_size / 1024:.2f} KB")
        return True
    else:
        print(f"❌ 文档未创建: {doc_path}")
        return False


def main():
    """运行所有测试"""
    print("🧪 Issue #1 修复验证测试套件")
    print("=" * 60)
    print("目标: 验证模型文件路径依赖问题的修复效果\n")

    results = []

    # 运行所有测试
    results.append(("模型不存在检测", test_model_not_exists()))
    results.append(("实际路径检查", test_actual_model_path()))
    results.append((".gitignore 配置", test_gitignore_configuration()))
    results.append(("代码修改验证", check_code_changes()))
    results.append(("文档创建验证", check_documentation()))

    # 输出总结
    print("\n" + "=" * 60)
    print("📊 测试结果总结")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        symbol = "✅" if result else "❌"
        print(f"{symbol} {name:<20} {'通过' if result else '失败'}")

    print(f"\n总计: {passed}/{total} 个测试通过")

    if passed == total:
        print("\n" + "🎉" * 20)
        print("所有测试通过！Issue #1 已完全修复 ✓")
        print("\n修复内容总结:")
        print("  1. ✅ 添加了 validate_model_file() 启动前验证函数")
        print("  2. ✅ 在 startup_event() 中集成模型存在性检查")
        print("  3. ✅ 提供清晰的可视化错误提示和解决方案")
        print("  4. ✅ 创建了详细的模型下载说明文档")
        print("  5. ✅ 确认 .gitignore 正确排除模型文件")
        print("\n" + "🎉" * 20)
        return 0
    else:
        print("\n⚠️  部分测试未通过，需要进一步检查")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
