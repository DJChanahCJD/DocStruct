import os
import pymupdf4llm

# 转换 PDF 为 Markdown
pdf_path = "static/examples/需求分析-广州市白云区司法局全流程智能执法辅助系统2026年建设项目立项方案v2.0-20251230.pdf"

# 使用 pymupdf4llm 进行转换
# 参数说明:
# - pages: 指定页面范围，None 表示所有页面
# - show_progress: 显示进度条
# - table_strategy: 表格识别策略 ('lines', 'text', 'markdown')
markdown = pymupdf4llm.to_markdown(
    pdf_path,
    pages=None,  # 转换所有页面
    show_progress=True,
    table_strategy="lines"  # 使用线条识别表格
)

print(f"转换完成，总字符数: {len(markdown)}")

# 保存结果
root_dir = os.path.dirname(os.path.abspath(__file__))
output_path = os.path.join(root_dir, "pymupdf4llm_output.md")

with open(output_path, "w", encoding="utf-8") as f:
    f.write(markdown)

print(f"已保存到: {output_path}")
