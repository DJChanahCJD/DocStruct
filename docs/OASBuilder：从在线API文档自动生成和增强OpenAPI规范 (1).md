# OASBuilder：从在线API文档自动生成和增强OpenAPI规范

## 摘要

OpenAPI规范（OAS）是REST API的通用描述标准，可支撑API调用、测试用例生成等关键开发任务。然而，绝大多数真实世界的API文档仅以网页形式呈现，未提供机器可读的OAS规范，人工编写OAS不仅耗时且易出错。为此，本文提出OASBuilder，一种多阶段系统，可从在线API文档自动化生成并增强OAS规范。该系统融合基于规则的算法与生成式大型语言模型（LLM），先从网页中提取API相关信息，再通过多阶段并行LLM调用生成基础OAS，最后通过AI驱动工具补全缺失元数据。实验表明，OASBuilder可有效处理各类API文档，生成的OAS能捕获文档中绝大多数关键信息，大幅降低人工工作量。

关键词：OpenAPI规范；API文档；大型语言模型；自动化生成

## 1 引言

REST API已成为现代软件系统交互的核心组件，而OpenAPI规范（OAS）作为REST API的标准化描述格式，在API开发、测试、集成中发挥着关键作用。OAS可明确定义API的端点、参数、请求/响应格式等核心信息，支撑自动化测试、代码生成、对话式API调用等下游任务。

尽管OAS优势显著，但现实中绝大多数API文档仅以自然语言和示例代码结合的网页形式呈现，未提供机器可读的OAS规范。人工编写OAS不仅需要开发人员深入理解API文档，还需严格遵循OAS语法规范，过程繁琐且易引入错误，尤其是对于参数繁多、结构复杂的API，人工编写成本极高。

现有OAS生成方法存在明显局限：部分方法依赖API流量拦截或源代码分析，无法处理仅提供网页文档的API；部分基于规则的网页解析方法适配性差，难以应对不同网站的HTML结构差异；近期基于LLM的方法则受限于上下文窗口长度，无法处理内容冗长的API文档。

为解决上述问题，本文提出OASBuilder，一种全新的多阶段自动化系统，可从在线API文档中提取信息并生成高质量OAS规范。OASBuilder的核心创新在于：（1）融合基于规则的算法与生成式LLM，兼顾解析准确性与结构适配性；（2）将OAS生成任务拆解为多个并行子任务，突破LLM上下文窗口限制；（3）设计AI驱动的增强模块，补全OAS中的缺失元数据，提升规范完整性。

实验结果表明，OASBuilder在多样化API文档数据集上表现优异，主流LLM通过该系统可生成高有效性的OAS，且能捕获文档中绝大多数关键信息，大幅降低人工编写成本。

## 2 背景与相关定义

### 2.1 OpenAPI规范（OAS）

OAS是一种机器可读的API描述格式，核心组件包括：（1）基础信息（标题、版本、描述）；（2）服务地址（servers）；（3）路径与操作（paths），包含HTTP方法、参数、请求体、响应等；（4）数据模型（components），定义请求/响应的JSON Schema等。OAS 3.0及以上版本支持丰富的元数据描述，可满足各类API的描述需求。

### 2.2 API文档网页结构

在线API文档网页通常包含两类核心信息：（1）示例型文档，如cURL命令、请求/响应示例代码；（2）描述型文档，如参数说明、功能描述、约束条件等。两类信息分布在网页的不同HTML元素中，且不同网站的HTML结构差异极大，给信息提取带来挑战。

### 2.3 上下文学习与LLM能力

生成式LLM具备强大的上下文学习能力，可通过少量示例（Few-shot Learning）学习任务模式。本文选用多款开源LLM（如llama-3-70b-instruct、codellama-34b-instruct等），基于上下文学习实现API信息到OAS的转换，无需对模型进行微调。

## 3 OASBuilder系统设计

OASBuilder采用多阶段架构，核心流程分为4个步骤：（1）文档抓取与预处理；（2）基于示例型文档生成基础OAS；（3）基于描述型文档生成OAS并合并；（4）OAS增强。系统架构如图1所示（原文图1省略，核心逻辑如下）。

### 3.1 文档抓取与预处理

系统首先通过网页抓取工具获取API文档网页的HTML内容，随后进行预处理：（1）清理HTML噪声，去除无关广告、导航栏等元素；（2）识别API操作作用域，定位包含示例型和描述型文档的HTML区域；（3）标准化示例代码（如cURL命令），统一格式以减少后续处理差异。

预处理阶段采用基于规则的算法，结合HTML标签特征（如<code>、<table>）和关键词（如“Request”“Response”），快速定位API相关内容，过滤无关信息，为后续OAS生成奠定基础。

### 3.2 基于示例型文档生成基础OAS

示例型文档（如cURL命令、请求/响应JSON）是生成OAS的核心依据，系统将其拆解为两个并行子任务，通过多阶段LLM调用生成基础OAS组件。

首先，为每个请求示例生成不含请求体的局部OAS。系统先将示例标准化为规范cURL命令，再通过并行LLM调用，为每个命令匹配2个真实场景上下文示例，生成包含服务地址、请求路径、HTTP方法、请求参数等核心元数据的局部OAS。

其次，为请求体与响应示例生成JSON Schema。针对LLM处理大型嵌套JSON结构的不足，系统基于预定义行数阈值，将复杂结构拆分为小片段，通过并行LLM调用为每个片段生成JSON Schema，确保Schema的准确性。

### 3.3 描述型OAS生成

与示例型OAS生成并行，系统基于描述型文档生成第二份OAS，再与示例型OAS合并得到完整基础OAS。

由于不同网站HTML结构差异大，基于规则的解析难以适配，系统采用LLM实现描述型信息提取与转换。首先通过检索算法，从预处理后的HTML中提取描述型文档，筛选包含参数说明、功能描述的HTML元素，过滤无关内容；随后去除HTML属性（如CSS样式）压缩输入，通过上下文学习的LLM将提取内容转换为OAS。

为提升LLM转换准确性，系统设计多样化上下文示例，覆盖不同OAS结构与属性；若出现上下文窗口溢出，使用简短备选示例重试。生成后，系统校验OAS结构，确保参数名与输入一致，避免模型幻觉。

合并阶段，优先采纳描述型文档中的描述、必填属性，以及示例型文档中的类型、位置字段，确保合并后OAS的准确性与完整性。

### 3.4 OAS增强

基础OAS生成后，系统通过AI驱动工具补全缺失元数据，支撑下游任务。增强功能主要包括两方面：

（1）从参数描述中提取元数据：参数描述中通常包含枚举值、默认值、格式等信息，系统通过LLM结合上下文示例提取这些信息，并验证提取结果与描述的一致性。为减少LLM调用次数，采用关键词过滤机制（仅当描述包含“默认”“枚举”等术语时触发调用），且提示词支持同时处理多条描述。

（2）基于OAS结构生成元数据：针对缺失的方法/参数描述、参数示例等，系统利用OAS中的相关上下文（如参数名、方法名、端点路径），通过LLM生成缺失内容，提升OAS的丰富度。

## 4 实验

本节通过句法评估与语义评估，验证OASBuilder的性能。实验选用多款开源LLM（llama-3-70b-instruct、codellama-34b-instruct等），所有提示词未针对特定模型微调；由于既往研究未提供公开基准与复现细节，未设置基线模型。

### 4.1 句法评估

评估数据集包含50个多样化API文档网页（覆盖189个API操作），评估指标包括：有效JSON比例、有效OAS比例、有效JSON中的平均错误数。

|模型|有效JSON比例|有效OAS比例|平均错误数|
|---|---|---|---|
|CODELLAMA|.99|.89|.59|
|GRANITE-CODE|1|.73|.48|
|LLAMA-3|1|.29|.78|
|MISTRAL|1|.4|.54|
|MIXTRAL|.92|.66|.64|
表1：不同LLM通过OASBuilder生成OAS的句法评估结果

结果显示，codellama与granite-code表现最优：codellama有效OAS比例最高（.89），granite-code有效JSON比例达1且错误率最低（.48）。其余模型虽能生成有效JSON，但有效OAS比例较低，说明OAS生成对LLM仍具挑战性。

扩展性测试中，使用granite-code处理291个API文档URL，有效JSON比例100%，有效OAS比例89%，平均错误数仅0.17，表明系统具备良好的泛化能力。此外，直接使用GPT-4-128K基于原始HTML生成OAS，仅25%网页能得到有效结果，验证了OASBuilder拆分任务、突破上下文限制的优势。

### 4.2 语义评估

语义评估基于人工标注数据集（108个API操作，涵盖数千个参数与属性），对比生成OAS与基准真值OAS的一致性，评估指标包括参数精确率、召回率、描述相似度及各类属性F1值。

结果显示，所有模型的参数精确率均较高（≥.94），说明模型幻觉极少；granite-code与codellama的请求参数召回率分别达0.86与0.85，能捕获绝大多数请求参数；描述相似度、必填/默认值/枚举值属性F1值均处于较高水平，表明描述型文档信息已有效整合至OAS中。

响应参数召回率相对较低，主要因响应结构多为高度嵌套且缺乏对应描述文档。总体而言，OASBuilder生成的OAS能大幅降低人工标注工作量，满足实际开发需求。

## 5 相关工作

现有OAS生成方法主要分为三类：（1）基于API流量或源代码分析，如SpyREST通过拦截HTTP流量生成文档，Respector通过静态分析从源代码提取OAS，但此类方法无法处理仅提供网页文档的API；（2）基于规则的网页解析，如AutoREST、D2Spec通过固定规则提取API信息，但适配性差，难以应对不同网站的HTML结构差异；（3）基于LLM的方法，如Androˇcec and Tomaši´c使用GPT-3从HTML生成OAS，但受限于上下文窗口，无法处理长文档。

OASBuilder与现有方法的核心区别在于：将OAS生成任务拆解为并行子任务，突破LLM上下文限制；融合基于规则的算法与LLM，兼顾解析效率与适配性；设计增强模块，提升OAS完整性与实用性。

## 6 结论

本文提出OASBuilder，一种多阶段自动化系统，可从在线API文档生成并增强OAS规范。该系统通过融合基于规则的算法与生成式LLM，解决了现有方法适配性差、受上下文限制的问题；实验表明，OASBuilder具备强鲁棒性与泛化能力，生成的OAS能捕获文档中绝大多数关键信息，大幅降低人工编写成本。

未来工作可进一步优化描述型文档提取算法，提升复杂HTML结构的适配能力；同时探索模型微调策略，进一步提升OAS生成的准确性与完整性。

## 参考文献（部分）

Androˇcec, D., & Tomašić, M. (2023). Using GPT-3 to automatically create RESTful service descriptions. *Proceedings of the 4th International Conference on Communications, Information, Electronic and Energy Systems (CIEES)*, 1–4.

Bahrami, M., & Chen, W.-P. (2020). Automated web service specification generation through transformation-based learning. *Services Computing (SCC 2020)*, 103–119.

Cao, H., Falleri, J.-R., & Blanc, X. (2017). Automated generation of REST API specifications from plain HTML documentation. *Service-Oriented Computing (ICSOC 2017)*, 453–461.

## 附录

### A.1 核心提示词示例 (Few-shot)

**指令：** 请根据提供的 cURL 命令生成 OpenAPI 3.0 规范（JSON 格式）。

**【示例 1】**

  * **输入：** `curl -X GET 'https://api-m.paypal.com/v1/.../XP-123?org_id=10' -H 'x-header: val'`
  * **输出：** (含 `path`, `query`, `header` 参数定义的 OAS 结构)

**【示例 2】**

  * **输入：** `curl -X GET 'https://{store}.myshopify.com/admin/api/2024-04/inventory_levels.json?location_ids=655' -H 'X-Shopify-Access-Token: {token}'`
  * **生成结果：**

<!-- end list -->

```json
{
  "openapi": "3.0.0",
  "info": { "title": "Shopify Inventory API", "version": "2024-04" },
  "paths": {
    "/admin/api/2024-04/inventory_levels.json": {
      "get": {
        "parameters": [
          { "name": "location_ids", "in": "query", "required": true, "schema": { "type": "integer" } },
          { "name": "X-Shopify-Access-Token", "in": "header", "required": true, "schema": { "type": "string" } }
        ],
        "responses": { "200": { "description": "OK" } }
      }
    }
  }
}
```

-----

### A.2 测试数据集

测试集涵盖电商、支付、社交等主流领域，确保了评估的广泛性。核心来源包括：

| 类型 | 服务商 (API 范例) |
| :--- | :--- |
| **邮件/营销** | [SendGrid Contacts API](https://docs.sendgrid.com/api-reference/contacts/add-or-update-a-contact) |
| **健康/运动** | [Fitbit Activity Log](https://dev.fitbit.com/build/reference/web-api/activity/get-activity-log-list/) |
| **支付/金融** | [Adyen Checkout](https://docs.adyen.com/api-explorer/Checkout/70/post/payments) / [PayPal Web Profile](https://www.google.com/search?q=https://developer.paypal.com/docs/api/payment-experience/v1/) |
| **气象/工具** | [OpenWeather One Call](https://openweathermap.org/api/one-call-3) |
| **协作/开发** | [GitHub Issues API](https://www.google.com/search?q=https://docs.github.com/en/rest/issues/comments) |