import os
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.datamodel.base_models import InputFormat

# 控制内存峰值，防止 std::bad_alloc
pipeline_options = PdfPipelineOptions()
pipeline_options.do_ocr = False     # TODO： 仅针对扫描型 PDF开启？或者对图片局部开启？
pipeline_options.do_table_structure = True
pipeline_options.table_structure_options.mode = TableFormerMode.FAST
pipeline_options.images_scale = 1.2                # 降低分辨率，大幅减少内存
pipeline_options.ocr_batch_size = 1          # 单页 OCR 批量，避免内存溢
pipeline_options.layout_batch_size = 1       # 单页布局批量
pipeline_options.table_batch_size = 1        # 单页表格批量

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    }
)
result = converter.convert(
    "static/examples/需求分析-广州市白云区司法局全流程智能执法辅助系统2026年建设项目立项方案v2.0-20251230.pdf"
)
markdown = result.document.export_to_markdown()

print(f"转换完成，总字符数: {len(markdown)}")

root_dir = os.path.dirname(os.path.abspath(__file__))
output_path = os.path.join(root_dir, "docling_output.md")

with open(output_path, "w", encoding="utf-8") as f:
    f.write(markdown)

print(f"已保存到: {output_path}")