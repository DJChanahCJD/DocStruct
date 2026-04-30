"""
DocStruct schema constants — all enum types used across extraction pipeline.
Split from models.py for modularity.
"""

from __future__ import annotations

from enum import Enum

class DocType(str, Enum):
    SRS = "srs" # 需求规格说明书
    API = "api" # API 文档
    HLD = "hld" # 概要设计文档
    TC = "tc" # 测试用例文档
    DBDD = "dbdd" # 数据库设计文档
    UNKNOWN = "unknown"

class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class DocumentStatus(str, Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    COMPLETED = "completed"
    FAILED = "failed"

class ElementType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    SEPARATOR = "separator"
    CODE = "code"
    TABLE = "table"
    IMAGE = "image"

class NonFunctionalCategory(str, Enum):
    PERFORMANCE = "performance"     # 性能
    SECURITY = "security"           # 安全
    AVAILABILITY = "availability"   # 可用性
    COMPATIBILITY = "compatibility" # 兼容性
    MAINTAINABILITY = "maintainability" # 可维护性
    COMPLIANCE = "compliance"         # 合规性
    STORAGE = "storage"             # 存储
    SCALABILITY = "scalability"     # 可扩展性
    OTHER = "other"

