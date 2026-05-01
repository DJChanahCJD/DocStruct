## 推荐放入参考文献的条目（共5篇）

### 1. Docling — 工业级PDF文档转换
**推荐理由**：为DocStruct的“文档内容提取”模块提供直接可用的基础解析能力（布局分析、表格识别、OCR）。MIT许可证适合毕设原型开发。

**格式（按你的本科毕设模板，电子文献[EB/OL]）**：
```plaintext
[1] Auer C, Lysak M, Nassar A, et al. Docling Technical Report[EB/OL]. arXiv:2408.09869, 2024. https://arxiv.org/abs/2408.09869.
```

### 2. MinerU2.5 — 高效高精度文档解析（解耦VLM）
**推荐理由**：1.2B参数量，两阶段“全局布局→细节识别”范式与DocStruct的Map阶段高度吻合。2025年新工作，展示SOTA性能。

**格式**：
```plaintext
[2] Niu J, et al. MinerU2.5: A Decoupled Vision-Language Model for Efficient High-Resolution Document Parsing[EB/OL]. arXiv:2509.22186, 2025. https://arxiv.org/abs/2509.22186.
```

### 3. LLM × MapReduce — 免训练长文本分块处理框架
**推荐理由**：直接对应DocStruct中“MapReduce over hierarchical document parsing”的设计思想，为如何分块、聚合、解决块间依赖提供理论参考。

**格式**：
```plaintext
[3] Wang S, et al. LLM×MapReduce: Simplified Long-Sequence Processing using Large Language Models[EB/OL]. arXiv:2410.09342, 2024. https://arxiv.org/abs/2410.09342.
```

### 4. Ragas — RAG系统自动化评估（无需人工标注）
**推荐理由**：DocStruct本质上是一个结构化RAG系统。Ragas提供**忠实度（faithfulness）** 和**上下文相关性**指标，可直接评估你的输出是否基于真实文档。

**格式**：
```plaintext
[4] Es S, James J, Espinosa-Anke L, et al. Ragas: Automated Evaluation of Retrieval Augmented Generation[EB/OL]. arXiv:2309.15217, 2023. https://arxiv.org/abs/2309.15217.
```

### 5. ALCE — 带引用的LLM生成自动评估
**推荐理由**：强调输出必须附带**可验证的引用**，并三维评估（流畅性、正确性、引用质量）。完美契合DocStruct对“证据接地（evidence grounding）”的要求。

**格式**：
```plaintext
[5] Gao T, Yen H, Yu J, et al. ALCE: An Automatic Benchmark for Large Language Model Generations with Citations[EB/OL]. arXiv:2305.14627, 2023. https://arxiv.org/abs/2305.14627.
```