# 模型价格对比分析

阿里云百炼平台：https://bailian.console.aliyun.com/cn-beijing?tab=model#/model-market/all

## 各模型详细价格

### 1. DeepSeek-V4-Flash

| 计费项 | 价格 |
|--------|------|
| 输入 | 1 元/百万 tokens |
| 输出 | 2 元/百万 tokens |
| 输入(缓存命中) | 0.2 元/百万 tokens |

### 2. Kimi-K2.5

| 计费项 | 价格 |
|--------|------|
| 输入 | 4 元/百万 tokens |
| 输出 | 21 元/百万 tokens |
| 输入(缓存命中) | 0.8 元/百万 tokens |
| 显式缓存创建 | 5 元/百万 tokens |
| 显式缓存命中 | 0.4 元/百万 tokens |

### 3. Qwen-Doc-Turbo

| 计费项 | 价格 |
|--------|------|
| 输入 | 0.6 元/百万 tokens |
| 输出 | 1 元/百万 tokens |
| 输入(缓存命中) | 0.12 元/百万 tokens |
| 显式缓存创建 | 0.75 元/百万 tokens |
| 显式缓存命中 | 0.06 元/百万 tokens |

---

## 价格对比分析

### 输入价格对比

| 模型 | 输入价格(元/百万tokens) | 缓存命中价格 |
|------|------------------------|-------------|
| Qwen-Doc-Turbo | 0.6 | 0.12 |
| DeepSeek-V4-Flash | 1 | 0.2 |
| Kimi-K2.5 | 4 | 0.8 |

### 输出价格对比

| 模型 | 输出价格(元/百万tokens) |
|------|------------------------|
| Qwen-Doc-Turbo | 1 |
| DeepSeek-V4-Flash | 2 |
| Kimi-K2.5 | 21 |

---

## 结论

1. **单位价格最低**：Qwen-Doc-Turbo 在输入(0.6元/百万tokens)和输出(1元/百万tokens)价格上都是最便宜的

2. **单位价格最高**：Kimi-K2.5 是最贵的，输入 4 元/百万tokens，输出高达 21 元/百万tokens

3. **最优选择**：考虑到 Qwen-Doc-Turbo 的纯文本输入模式最多支持 9K，结合项目已经做了分片提取，因此 **Qwen-Doc-Turbo 是成本最低的选择**

---

## 价格排序(从低到高)

**输入价格**：Qwen-Doc-Turbo (0.6) < DeepSeek-V4-Flash (1) < Kimi-K2.5 (4)

**输出价格**：Qwen-Doc-Turbo (1) < DeepSeek-V4-Flash (2) < Kimi-K2.5 (21)
