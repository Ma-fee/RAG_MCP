# Plan A：多模态索引构建

**日期**：2026-03-29
**设计文档**：`docs/superpowers/specs/2026-03-29-multimodal-docling-integration-design.md`
**方法**：TDD — 先写失败测试，再实现，再通过

---

## 文件变更清单

### 新增文件
| 文件 | 职责 |
|------|------|
| `src/rag_mcp/ingestion/vlm_client.py` | GLM-4.6V API 调用封装 |
| `src/rag_mcp/indexing/resource_store.py` | ResourceStore 读写，管理 resource_store.json 与 assets/ |
| `src/rag_mcp/indexing/cross_reference.py` | 交叉关联建立逻辑 |
| `tests/unit/test_vlm_client.py` | VlmClient 单元测试 |
| `tests/unit/test_resource_store.py` | ResourceStore 单元测试 |
| `tests/unit/test_cross_reference.py` | CrossReference 单元测试 |
| `tests/unit/test_docling_parser.py` | DoclingParser 单元测试 |

### 修改文件
| 文件 | 改动 |
|------|------|
| `src/rag_mcp/config.py` | 新增 multimodal_base_url/api_key/model 字段 |
| `src/rag_mcp/ingestion/docling_parser.py` | 完全重写：使用真正的 Docling 解析 PDF |
| `src/rag_mcp/indexing/rebuild.py` | 插入 ResourceStore.build + CrossReference.build 步骤 |
| `src/rag_mcp/resources/service.py` | 扩展 read()：支持 #image-<n> / #table-<n> URI |
| `.env.example` | 新增 MULTIMODAL_* 环境变量 |

---

## Task A1：扩展 AppConfig，加入 VLM 配置

**文件**：`src/rag_mcp/config.py`、`.env.example`

1. 在 `AppConfig` dataclass 新增三个字段：
   ```python
   multimodal_api_key: str
   multimodal_base_url: str
   multimodal_model: str
   ```
2. 在 `from_env()` 中读取环境变量（默认值与 .env.example 中已有的 MULTIMODAL_* 一致）：
   ```python
   multimodal_api_key=os.getenv("MULTIMODAL_API_KEY", ""),
   multimodal_base_url=os.getenv("MULTIMODAL_BASE_URL", "https://api.siliconflow.cn/v1"),
   multimodal_model=os.getenv("MULTIMODAL_MODEL", "zai-org/GLM-4.6V"),
   ```
3. 更新 `.env.example`，去掉 `# post-v1 reserved` 注释，标记为当前版本可用
4. `uv run pytest tests/` 确认现有测试不破坏
5. commit: `feat(config): add multimodal VLM config fields`

---

## Task A2：实现 VlmClient（TDD）

**测试文件**：`tests/unit/test_vlm_client.py`
**实现文件**：`src/rag_mcp/ingestion/vlm_client.py`

### 先写测试
```python
from unittest.mock import patch, MagicMock
from pathlib import Path
from rag_mcp.ingestion.vlm_client import VlmClient

def test_describe_image_returns_string(tmp_path):
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    client = VlmClient(api_key="fake", base_url="http://fake", model="fake")
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": "这是一张液压图"}}]}
        )
        result = client.describe_image(img_path)
    assert isinstance(result, str)
    assert len(result) > 0

def test_describe_image_sends_base64(tmp_path):
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    client = VlmClient(api_key="fake", base_url="http://fake", model="fake")
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": "ok"}}]}
        )
        client.describe_image(img_path)
    call_json = mock_post.call_args.kwargs["json"]
    content = call_json["messages"][0]["content"]
    assert any(item.get("type") == "image_url" for item in content)

def test_describe_image_api_error_raises(tmp_path):
    from rag_mcp.errors import ServiceException
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    client = VlmClient(api_key="fake", base_url="http://fake", model="fake")
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=401, text="Unauthorized")
        with pytest.raises(ServiceException):
            client.describe_image(img_path)
```

### 运行测试确认失败，再实现
```python
@dataclass
class VlmClient:
    api_key: str
    base_url: str
    model: str
    timeout: int = 60

    def describe_image(self, image_path: Path) -> str:
        image_data = base64.b64encode(Path(image_path).read_bytes()).decode()
        payload = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
                    {"type": "text", "text": "请描述这张图片的内容，重点说明图中展示的技术信息。"}
                ]
            }]
        }
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise ServiceException(ServiceError(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"VLM API 返回 {resp.status_code}",
                hint=resp.text[:200],
            ))
        return resp.json()["choices"][0]["message"]["content"]
```

运行测试，确认通过。
commit: `feat(ingestion): add VlmClient for GLM-4.6V image description`

---

## Task A3：重写 DoclingParser（TDD）

**测试文件**：`tests/unit/test_docling_parser.py`
**实现文件**：`src/rag_mcp/ingestion/docling_parser.py`

### 先写测试
```python
import pytest
from pathlib import Path
from rag_mcp.ingestion.docling_parser import DoclingParser
from rag_mcp.ingestion.document_model import Document

PDF_PATH = Path("dataset/SY55C_SY55-60C Crawler Hydraulic Excavator Maintenance Manual_en_C.1.pdf")

@pytest.fixture(scope="module")
def parsed_doc(tmp_path_factory):
    assets = tmp_path_factory.mktemp("assets")
    parser = DoclingParser(assets_dir=assets)
    return parser.parse(PDF_PATH)

def test_returns_document(parsed_doc):
    assert isinstance(parsed_doc, Document)

def test_has_elements(parsed_doc):
    assert len(parsed_doc.elements) > 0

def test_text_elements_have_real_heading_path(parsed_doc):
    text_els = [e for e in parsed_doc.elements if e.element_type == "text"]
    assert len(text_els) > 0
    # heading_path 不应该全是文件名
    assert any(e.heading_path != PDF_PATH.name for e in text_els)

def test_table_elements_have_markdown(parsed_doc):
    table_els = [e for e in parsed_doc.elements if e.element_type == "table"]
    assert len(table_els) > 0
    assert all("markdown" in e.metadata for e in table_els)

def test_image_elements_saved_to_assets(parsed_doc, tmp_path_factory):
    image_els = [e for e in parsed_doc.elements if e.element_type == "image"]
    # 维修手册应有图片
    assert len(image_els) > 0
    for img in image_els:
        assert Path(img.metadata["image_path"]).exists()
```

### 运行测试确认失败，再实现

核心实现逻辑：
```python
from docling.document_converter import DocumentConverter

class DoclingParser:
    def __init__(self, assets_dir: Path) -> None:
        self.assets_dir = Path(assets_dir)
        self._converter = DocumentConverter()

    def parse(self, path: Path) -> Document:
        result = self._converter.convert(str(path))
        dl_doc = result.document
        doc_id = _make_doc_id(path)
        elements = []
        self._extract_texts(dl_doc, elements)
        self._extract_tables(dl_doc, elements, doc_id)
        self._extract_images(dl_doc, elements, doc_id, path)
        return Document(
            doc_id=doc_id,
            title=path.stem,
            relative_path=str(path),
            file_type="pdf",
            elements=elements,
        )
```

- `_extract_texts`：遍历 `dl_doc.texts`，从 `item.prov[0].page_no` 取页码，从父级标题构建 `heading_path`
- `_extract_tables`：遍历 `dl_doc.tables`，调用 `table.export_to_markdown()` 获取 markdown
- `_extract_images`：遍历 `dl_doc.pictures`，用 PIL/PyMuPDF 按 bbox 裁剪保存到 `assets_dir/<doc_id>/image-<n>.png`

运行测试，确认通过。
commit: `feat(ingestion): rewrite DoclingParser using real Docling API`

---

## Task A4：实现 ResourceStore（TDD）

**测试文件**：`tests/unit/test_resource_store.py`
**实现文件**：`src/rag_mcp/indexing/resource_store.py`

### 先写测试
```python
import json
from unittest.mock import MagicMock
from pathlib import Path
from rag_mcp.indexing.resource_store import ResourceStore
from rag_mcp.ingestion.document_model import Document, Element

def make_doc(elements):
    return Document(doc_id="doc1", title="test", relative_path="test.pdf",
                    file_type="pdf", elements=elements)

def make_text_el(i, text="hello"):
    return Element(element_id=f"el-{i}", element_type="text", text=text,
                   heading_path="Chapter 1", section_title="Intro", section_level=1)

def make_image_el(i, image_path):
    return Element(element_id=f"el-img-{i}", element_type="image", text="",
                   heading_path="Chapter 1", section_title="Intro", section_level=1,
                   metadata={"image_path": str(image_path), "caption": f"图{i}", "page_number": 1})

def make_table_el(i):
    return Element(element_id=f"el-tbl-{i}", element_type="table", text="",
                   heading_path="Chapter 1", section_title="Intro", section_level=1,
                   metadata={"markdown": "| a | b |\n|---|---|\n| 1 | 2 |", "caption": f"表{i}", "page_number": 2})

def test_build_creates_resource_store_json(tmp_path):
    doc = make_doc([make_text_el(0)])
    store = ResourceStore(index_dir=tmp_path, corpus_id="c1", vlm_client=None)
    store.build(doc)
    assert (tmp_path / "resource_store.json").exists()

def test_text_uri_format(tmp_path):
    doc = make_doc([make_text_el(0)])
    store = ResourceStore(index_dir=tmp_path, corpus_id="c1", vlm_client=None)
    entries = store.build(doc)
    assert entries[0]["uri"] == "rag://corpus/c1/doc1#text-0"

def test_image_uri_format(tmp_path):
    img = tmp_path / "img.png"; img.write_bytes(b"fake")
    doc = make_doc([make_image_el(0, img)])
    mock_vlm = MagicMock()
    mock_vlm.describe_image.return_value = "液压图"
    store = ResourceStore(index_dir=tmp_path, corpus_id="c1", vlm_client=mock_vlm)
    entries = store.build(doc)
    assert entries[0]["uri"] == "rag://corpus/c1/doc1#image-0"
    assert entries[0]["vlm_description"] == "液压图"

def test_table_uri_format(tmp_path):
    doc = make_doc([make_table_el(0)])
    store = ResourceStore(index_dir=tmp_path, corpus_id="c1", vlm_client=None)
    entries = store.build(doc)
    assert entries[0]["uri"] == "rag://corpus/c1/doc1#table-0"
    assert "markdown" in entries[0]

def test_get_by_uri(tmp_path):
    doc = make_doc([make_text_el(0, text="测试内容")])
    store = ResourceStore(index_dir=tmp_path, corpus_id="c1", vlm_client=None)
    store.build(doc)
    result = store.get("rag://corpus/c1/doc1#text-0")
    assert result is not None
    assert result["text"] == "测试内容"
```

### 运行测试确认失败，再实现

```python
@dataclass
class ResourceStore:
    index_dir: Path
    corpus_id: str
    vlm_client: Any | None  # VlmClient | None

    _store_path: Path = field(init=False)

    def __post_init__(self):
        self._store_path = Path(self.index_dir) / "resource_store.json"

    def build(self, document: Document) -> list[dict]:
        entries = []
        text_n = image_n = table_n = 0
        for element in document.elements:
            if element.element_type == "text":
                entries.append(self._text_entry(element, document, text_n))
                text_n += 1
            elif element.element_type == "image":
                desc = self.vlm_client.describe_image(Path(element.metadata["image_path"])) \
                    if self.vlm_client else ""
                entries.append(self._image_entry(element, document, image_n, desc))
                image_n += 1
            elif element.element_type == "table":
                entries.append(self._table_entry(element, document, table_n))
                table_n += 1
        self._persist(entries)
        return entries

    def get(self, uri: str) -> dict | None:
        data = json.loads(self._store_path.read_text(encoding="utf-8"))
        return next((e for e in data["entries"] if e["uri"] == uri), None)

    def _persist(self, entries: list[dict]) -> None:
        self._store_path.write_text(
            json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
```

commit: `feat(indexing): implement ResourceStore for image/table/text resource persistence`

---

## Task A5：实现 CrossReferenceBuilder（TDD）

**测试文件**：`tests/unit/test_cross_reference.py`
**实现文件**：`src/rag_mcp/indexing/cross_reference.py`

### 先写测试
```python
from rag_mcp.indexing.cross_reference import build_cross_references

def test_regex_match_links_text_to_image():
    entries = [
        {"uri": "rag://c/d#text-0", "type": "text",
         "text": "如图3-5所示，调节阀位于泵体右侧", "related": []},
        {"uri": "rag://c/d#image-0", "type": "image",
         "caption": "图3-5", "related": []},
    ]
    result = build_cross_references(entries)
    text = next(e for e in result if e["uri"].endswith("#text-0"))
    image = next(e for e in result if e["uri"].endswith("#image-0"))
    assert "rag://c/d#image-0" in text["related"]
    assert "rag://c/d#text-0" in image["related"]

def test_heading_path_fallback_links_same_section():
    entries = [
        {"uri": "rag://c/d#text-0", "type": "text",
         "text": "无显式引用", "heading_path": "Chapter 1", "related": []},
        {"uri": "rag://c/d#image-0", "type": "image",
         "caption": "", "heading_path": "Chapter 1", "related": [], "related_weak": []},
    ]
    result = build_cross_references(entries)
    image = next(e for e in result if e["uri"].endswith("#image-0"))
    assert "rag://c/d#text-0" in image["related_weak"]
```

### 实现要点
- 正则扫描中英文图表引用（图/表/Figure/Table）
- 构建 `caption → uri` 映射表
- 遍历 text entries，匹配 related，同时更新对应 image/table 的 related（双向）
- 兜底：同 heading_path 下无 related 的 image/table → 写入 `related_weak`
- 文本中引用标注替换为 markdown 链接：`图3-5` → `[图3-5](rag://...#image-0)`

commit: `feat(indexing): implement CrossReferenceBuilder with regex and fallback linking`

---

## Task A6：集成进 rebuild.py（TDD）

**测试文件**：`tests/unit/test_rebuild.py`（现有，补充新 case）
**修改文件**：`src/rag_mcp/indexing/rebuild.py`

### 先写失败测试
```python
def test_rebuild_creates_resource_store(tmp_path, mock_embedding_provider):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    # 复制测试 PDF
    shutil.copy("tests/fixtures/sample.pdf", dataset)
    rebuild_index(directory_path=str(dataset), ...)
    store_path = tmp_path / "indexes" / ... / "resource_store.json"
    assert store_path.exists()
    data = json.loads(store_path.read_text())
    types = {e["type"] for e in data["entries"]}
    assert "text" in types

def test_rebuild_uri_format_uses_text_prefix(tmp_path, ...):
    ...
    for entry in data["entries"]:
        if entry["type"] == "text":
            assert "#text-" in entry["uri"]
```

### 集成步骤（在现有 rebuild 流程中插入）
```
现有：parse → chunk → keyword_store + vector_index
新增：parse → ResourceStore.build → CrossReference.build → chunk → keyword_store + vector_index
```
- `DoclingParser` 替换原有 `_parse_document`
- `ResourceStore.build` 在分块前调用
- `CrossReference.build` 更新 resource_store.json 中的 related 字段
- text chunk URI 从 `#chunk-<n>` 改为 `#text-<n>`

commit: `feat(indexing): integrate multimodal pipeline into rebuild`

---

## Task A7：扩展 ResourceService 支持 image/table URI

**测试文件**：`tests/unit/test_resource_service.py`
**修改文件**：`src/rag_mcp/resources/service.py`

### 先写测试
```python
def test_read_image_uri_returns_vlm_description(tmp_path):
    # 构造 resource_store.json，含 image entry
    # 调用 service.read("rag://...#image-0")
    # 返回值包含 vlm_description
    ...

def test_read_table_uri_returns_markdown(tmp_path):
    ...

def test_read_text_uri_still_works(tmp_path):
    # 兼容现有 keyword_store 路径
    ...
```

### 实现
- `read(uri)` 中按 `#text-` / `#image-` / `#table-` 分流：
  - `#text-` → 查 `keyword_store.json`（保留现有逻辑）
  - `#image-` / `#table-` → 查 `resource_store.json`
  - image 返回：`{uri, type, vlm_description, image_path, related}`
  - table 返回：`{uri, type, markdown, data_json, related}`

commit: `feat(resources): extend ResourceService to handle image and table URIs`

---

## Task A8：端到端验收测试

**测试文件**：`tests/integration/test_e2e_multimodal.py`

```python
def test_full_pipeline_pdf_produces_multimodal_resources(tmp_path):
    """对真实 PDF 跑完整流水线，验证三种 resource 均存在。"""
    ...

def test_search_returns_related_image_uri(tmp_path):
    """检索命中 text chunk，结果的 related 中包含 image URI。"""
    ...

def test_read_image_resource_returns_vlm_description(tmp_path):
    """通过 image URI 读取资源，返回 VLM 描述文本。"""
    ...
```

commit: `test(e2e): add multimodal pipeline integration tests`

---

## 验收标准

- `uv run pytest tests/` 全部通过
- `rag_rebuild_index` 后 `resource_store.json` 存在，包含 text/image/table 三种类型
- text chunk URI 格式为 `#text-<n>`
- 检索结果的 `related` 字段包含 image/table URI
- `rag_read_resource` 读取 image URI 返回 `vlm_description`
- 读取 table URI 返回 `markdown` 和 `data_json`

---

## 执行顺序

```
A1（配置）→ A2（VLM client）→ A3（DoclingParser）→ A4（ResourceStore）
→ A5（CrossReference）→ A6（rebuild集成）→ A7（ResourceService）→ A8（E2E）
```