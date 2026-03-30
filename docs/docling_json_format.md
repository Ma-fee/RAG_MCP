# Docling JSON 格式文档

本文档记录了 Docling 解析 PDF 文档后生成的 JSON 缓存文件的结构和格式。

## 文档概览

### 顶层结构

```json
{
  "schema_name": "DoclingDocument",
  "version": "1.10.0",
  "name": "文档名称",
  "origin": {
    "mimetype": "application/pdf",
    "binary_hash": "文件哈希值",
    "filename": "原始文件名.pdf",
    "uri": null
  },
  "furniture": {...},
  "body": {...},
  "groups": [...],
  "texts": [...],
  "pictures": [...],
  "tables": [...],
  "key_value_items": [...],
  "form_items": [...],
  "pages": {...}
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_name` | string | Schema 类型，固定为 "DoclingDocument" |
| `version` | string | Docling 版本号 |
| `name` | string | 文档名称 |
| `origin` | object | 原始文档信息 |
| `furniture` | object | 文档装饰元素（页眉、页脚等） |
| `body` | object | 文档主体内容 |
| `groups` | array | 内容分组（列表、章节等） |
| `texts` | array | 文本块 |
| `pictures` | array | 图片 |
| `tables` | array | 表格 |
| `key_value_items` | array | 键值对 |
| `form_items` | array | 表单项 |
| `pages` | object | 页面信息 |

## 元素统计示例

基于挖掘机维护手册的统计：
- **文本块**: 13,192个
- **图片**: 1,334个
- **表格**: 184个
- **分组**: 704个
- **页面数**: 556页

## 最小单元结构

### 1. 文本块 (Text)

文本块是文档中最基本的文本单元，包含位置信息、文本内容和格式信息。

#### 结构定义

```json
{
  "self_ref": "#/texts/0",
  "parent": {
    "cref": "#/body"
  },
  "children": [],
  "content_layer": "furniture",
  "meta": null,
  "label": "page_header",
  "prov": [
    {
      "page_no": 1,
      "bbox": {
        "l": 383.754,
        "t": 767.9048662484375,
        "r": 525.51518478,
        "b": 756.8758266868991,
        "coord_origin": "BOTTOMLEFT"
      },
      "charspan": [0, 25]
    }
  ],
  "orig": "Quality Changes the World",
  "text": "Quality Changes the World",
  "formatting": null,
  "hyperlink": null
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `self_ref` | string | 自引用路径 |
| `parent` | object | 父元素引用 |
| `children` | array | 子元素引用列表 |
| `content_layer` | string | 内容层级（furniture/body） |
| `meta` | object/null | 元数据 |
| `label` | string | 标签类型 |
| `prov` | array | 位置信息数组 |
| `orig` | string | 原始文本 |
| `text` | string | 处理后的文本 |
| `formatting` | object/null | 格式信息 |
| `hyperlink` | object/null | 超链接信息 |

#### 标签类型

| 标签 | 数量 | 说明 |
|------|------|------|
| `text` | 7,954 | 正文文本 |
| `list_item` | 2,273 | 列表项 |
| `page_header` | 1,081 | 页眉 |
| `section_header` | 704 | 章节标题 |
| `caption` | 615 | 图片/表格标题 |
| `page_footer` | 558 | 页脚 |
| `footnote` | 4 | 脚注 |
| `code` | 1 | 代码 |
| `checkbox_selected` | 1 | 选中的复选框 |
| `checkbox_unselected` | 1 | 未选中的复选框 |

#### 示例

**页眉示例**:
```json
{
  "self_ref": "#/texts/0",
  "parent": {"cref": "#/body"},
  "children": [],
  "content_layer": "furniture",
  "meta": null,
  "label": "page_header",
  "prov": [{
    "page_no": 1,
    "bbox": {
      "l": 383.754,
      "t": 767.9048662484375,
      "r": 525.51518478,
      "b": 756.8758266868991,
      "coord_origin": "BOTTOMLEFT"
    },
    "charspan": [0, 25]
  }],
  "orig": "Quality Changes the World",
  "text": "Quality Changes the World",
  "formatting": null,
  "hyperlink": null
}
```

**章节标题示例**:
```json
{
  "self_ref": "#/texts/1",
  "parent": {"cref": "#/body"},
  "children": [],
  "content_layer": "body",
  "meta": null,
  "label": "section_header",
  "prov": [{
    "page_no": 1,
    "bbox": {
      "l": 86.6031723022461,
      "t": 680.1007614135742,
      "r": 525.51518478,
      "b": 660.8758266868991,
      "coord_origin": "BOTTOMLEFT"
    },
    "charspan": [0, 26]
  }],
  "orig": "Crawler Hydraulic Excavator",
  "text": "Crawler Hydraulic Excavator",
  "formatting": null,
  "hyperlink": null
}
```

**正文文本示例**:
```json
{
  "self_ref": "#/texts/2",
  "parent": {"cref": "#/body"},
  "children": [],
  "content_layer": "body",
  "meta": null,
  "label": "text",
  "prov": [{
    "page_no": 1,
    "bbox": {
      "l": 86.6031723022461,
      "t": 660.1007614135742,
      "r": 200.51518478,
      "b": 640.8758266868991,
      "coord_origin": "BOTTOMLEFT"
    },
    "charspan": [0, 10]
  }],
  "orig": "SY55C/60C",
  "text": "SY55C/60C",
  "formatting": null,
  "hyperlink": null
}
```

**列表项示例**:
```json
{
  "self_ref": "#/texts/14",
  "parent": {"cref": "#/body"},
  "children": [],
  "content_layer": "body",
  "meta": null,
  "label": "list_item",
  "prov": [{
    "page_no": 1,
    "bbox": {
      "l": 86.6031723022461,
      "t": 500.1007614135742,
      "r": 525.51518478,
      "b": 480.8758266868991,
      "coord_origin": "BOTTOMLEFT"
    },
    "charspan": [0, 150]
  }],
  "orig": "This Service Manual is prepared for experienced technical personnel, and aims to provide the technical information necessary for maintenance and repair of the machine.",
  "text": "This Service Manual is prepared for experienced technical personnel, and aims to provide the technical information necessary for maintenance and repair of the machine.",
  "formatting": null,
  "hyperlink": null
}
```

### 2. 图片 (Picture)

图片元素包含图片的位置信息和相关联的标题、引用等。

#### 结构定义

```json
{
  "self_ref": "#/pictures/0",
  "parent": {
    "cref": "#/body"
  },
  "children": [],
  "content_layer": "body",
  "meta": null,
  "label": "picture",
  "prov": [
    {
      "page_no": 1,
      "bbox": {
        "l": 86.6031723022461,
        "t": 747.1007614135742,
        "r": 288.50384521484375,
        "b": 692.2330474853516,
        "coord_origin": "BOTTOMLEFT"
      },
      "charspan": [0, 0]
    }
  ],
  "captions": [],
  "references": [],
  "footnotes": [],
  "image": null,
  "annotations": []
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `self_ref` | string | 自引用路径 |
| `parent` | object | 父元素引用 |
| `children` | array | 子元素引用列表 |
| `content_layer` | string | 内容层级 |
| `meta` | object/null | 元数据 |
| `label` | string | 标签类型（picture） |
| `prov` | array | 位置信息数组 |
| `captions` | array | 标题引用列表 |
| `references` | array | 引用列表 |
| `footnotes` | array | 脚注列表 |
| `image` | object/null | 图片数据 |
| `annotations` | array | 注释列表 |

### 3. 表格 (Table)

表格元素包含表格的结构和单元格数据。

#### 结构定义

```json
{
  "self_ref": "#/tables/0",
  "parent": {
    "cref": "#/body"
  },
  "children": [],
  "content_layer": "body",
  "meta": null,
  "label": "document_index",
  "prov": [
    {
      "page_no": 7,
      "bbox": {
        "l": 69.58246612548828,
        "t": 700.8295593261719,
        "r": 544.730224609375,
        "b": 79.15887451171875,
        "coord_origin": "BOTTOMLEFT"
      },
      "charspan": [0, 0]
    }
  ],
  "captions": [],
  "references": [],
  "footnotes": [],
  "image": null,
  "data": {
    "table_cells": [
      {
        "bbox": {
          "l": 70.8661,
          "t": 142.12059,
          "r": 544.2191444999995,
          "b": 154.98769519230768,
          "coord_origin": "TOPLEFT"
        },
        "row_span": 1,
        "col_span": 1,
        "start_row_offset_idx": 0,
        "end_row_offset_idx": 1,
        "start_col_offset_idx": 0,
        "end_col_offset_idx": 1,
        "text": "1 Preface..................................................................................................................................1-1",
        "column_header": false,
        "row_header": true,
        "row_section": false,
        "fillable": false
      }
    ]
  },
  "annotations": []
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `self_ref` | string | 自引用路径 |
| `parent` | object | 父元素引用 |
| `children` | array | 子元素引用列表 |
| `content_layer` | string | 内容层级 |
| `meta` | object/null | 元数据 |
| `label` | string | 标签类型（document_index/table） |
| `prov` | array | 位置信息数组 |
| `captions` | array | 标题引用列表 |
| `references` | array | 引用列表 |
| `footnotes` | array | 脚注列表 |
| `image` | object/null | 表格图片 |
| `data` | object | 表格数据 |
| `annotations` | array | 注释列表 |

#### 表格单元格字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `bbox` | object | 单元格边界框 |
| `row_span` | number | 行跨度 |
| `col_span` | number | 列跨度 |
| `start_row_offset_idx` | number | 起始行索引 |
| `end_row_offset_idx` | number | 结束行索引 |
| `start_col_offset_idx` | number | 起始列索引 |
| `end_col_offset_idx` | number | 结束列索引 |
| `text` | string | 单元格文本 |
| `column_header` | boolean | 是否为列标题 |
| `row_header` | boolean | 是否为行标题 |
| `row_section` | boolean | 是否为行分组 |
| `fillable` | boolean | 是否可填写 |

### 4. 分组 (Group)

分组元素用于组织相关的内容元素，如列表、章节等。

#### 结构定义

```json
{
  "self_ref": "#/groups/0",
  "parent": {
    "cref": "#/body"
  },
  "children": [
    {
      "cref": "#/texts/14"
    },
    {
      "cref": "#/texts/15"
    },
    {
      "cref": "#/texts/16"
    }
  ],
  "content_layer": "body",
  "meta": null,
  "name": "list",
  "label": "list"
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `self_ref` | string | 自引用路径 |
| `parent` | object | 父元素引用 |
| `children` | array | 子元素引用列表 |
| `content_layer` | string | 内容层级 |
| `meta` | object/null | 元数据 |
| `name` | string | 分组名称 |
| `label` | string | 标签类型（list/section等） |

### 5. 页面 (Page)

页面元素包含页面的尺寸和基本信息。

#### 结构定义

```json
{
  "size": {
    "width": 595.2760009765625,
    "height": 841.8900146484375
  },
  "image": null,
  "page_no": 1
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `size` | object | 页面尺寸 |
| `size.width` | number | 页面宽度 |
| `size.height` | number | 页面高度 |
| `image` | object/null | 页面图片 |
| `page_no` | number | 页面编号 |

## 通用字段说明

### 位置信息 (prov)

```json
{
  "page_no": 1,
  "bbox": {
    "l": 383.754,
    "t": 767.9048662484375,
    "r": 525.51518478,
    "b": 756.8758266868991,
    "coord_origin": "BOTTOMLEFT"
  },
  "charspan": [0, 25]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `page_no` | number | 页面编号 |
| `bbox` | object | 边界框 |
| `bbox.l` | number | 左边界 |
| `bbox.t` | number | 上边界 |
| `bbox.r` | number | 右边界 |
| `bbox.b` | number | 下边界 |
| `bbox.coord_origin` | string | 坐标原点（BOTTOMLEFT/TOPLEFT） |
| `charspan` | array | 字符范围 [起始, 结束] |

### 引用关系

所有元素都包含引用关系字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `self_ref` | string | 自引用路径（如 "#/texts/0"） |
| `parent` | object | 父元素引用（如 {"cref": "#/body"}） |
| `children` | array | 子元素引用列表（如 [{"cref": "#/texts/14"}]） |

## 使用建议

1. **文本提取**: 优先使用 `texts` 数组，根据 `label` 过滤需要的文本类型
2. **结构化内容**: 使用 `groups` 数组获取文档的结构信息（列表、章节等）
3. **位置信息**: 通过 `prov` 数组获取元素在页面中的精确位置
4. **引用关系**: 利用 `self_ref`、`parent`、`children` 构建文档的树形结构
5. **多模态内容**: 结合 `texts`、`pictures`、`tables` 获取完整的文档内容

## 其他重要字段

### furniture 和 body 字段

这两个字段是文档的根节点，包含所有子元素的引用。

#### furniture 结构

```json
{
  "self_ref": "#/furniture",
  "parent": null,
  "children": [],
  "content_layer": "furniture",
  "meta": null,
  "name": "_root_",
  "label": "unspecified"
}
```

#### body 结构

```json
{
  "self_ref": "#/body",
  "parent": null,
  "children": [
    {"cref": "#/texts/0"},
    {"cref": "#/pictures/0"},
    {"cref": "#/texts/1"},
    {"cref": "#/groups/0"},
    {"cref": "#/tables/0"}
  ],
  "content_layer": "body",
  "meta": null,
  "name": "_root_",
  "label": "unspecified"
}
```

**说明**:
- `furniture` 包含页眉、页脚等装饰性元素
- `body` 包含文档的主体内容
- `children` 数组按文档顺序列出所有子元素的引用

### 特殊文本块示例

#### 代码块 (code)

```json
{
  "self_ref": "#/texts/5471",
  "parent": {"cref": "#/pictures/628"},
  "children": [],
  "content_layer": "body",
  "meta": null,
  "label": "code",
  "prov": [{
    "page_no": 290,
    "bbox": {
      "l": 51.0236,
      "t": 296.48806298495583,
      "r": 524.4312717100611,
      "b": 187.0702254429034,
      "coord_origin": "BOTTOMLEFT"
    },
    "charspan": [0, 227]
  }],
  "orig": "Example : A VX 1. 25 B Color   code:  indicates the  col or Nomi nal   No.:   indicates the  dime nsion   of   wire.   Please  refer to   T able   2 Wire  symbol:  indicates the  type  of   wire.   Please  refer t o  T able   1",
  "text": "Example : A VX 1. 25 B Color   code:  indicates the  col or Nomi nal   No.:   indicates the  dime nsion   of   wire.   Please  refer to   T able   2 Wire  symbol:  indicates the  type  of   wire.   Please  refer t o  T able   1",
  "formatting": null,
  "hyperlink": null,
  "captions": [],
  "references": [],
  "footnotes": [],
  "image": null,
  "code_language": "unknown"
}
```

**特有字段**:
- `code_language`: 代码语言类型（如 "unknown"、"python"、"java" 等）

#### 选中的复选框 (checkbox_selected)

```json
{
  "self_ref": "#/texts/8997",
  "parent": {"cref": "#/groups/402"},
  "children": [],
  "content_layer": "body",
  "meta": null,
  "label": "checkbox_selected",
  "prov": [{
    "page_no": 357,
    "bbox": {
      "l": 70.86610000000005,
      "t": 485.4287128484375,
      "r": 107.69053180000004,
      "b": 475.3186138484375,
      "coord_origin": "BOTTOMLEFT"
    },
    "charspan": [0, 6]
  }],
  "orig": "① ××××",
  "text": "① ××××",
  "formatting": null,
  "hyperlink": null
}
```

#### 未选中的复选框 (checkbox_unselected)

```json
{
  "self_ref": "#/texts/9007",
  "parent": {"cref": "#/groups/402"},
  "children": [],
  "content_layer": "body",
  "meta": null,
  "label": "checkbox_unselected",
  "prov": [{
    "page_no": 357,
    "bbox": {
      "l": 115.59653640000003,
      "t": 302.87661964843755,
      "r": 442.9506336000001,
      "b": 292.76652064843756,
      "coord_origin": "BOTTOMLEFT"
    },
    "charspan": [0, 89]
  }],
  "orig": "..........................................................Method used during installation",
  "text": "..........................................................Method used during installation",
  "formatting": null,
  "hyperlink": null
}
```

#### 脚注 (footnote)

```json
{
  "self_ref": "#/texts/511",
  "parent": {"cref": "#/body"},
  "children": [],
  "content_layer": "body",
  "meta": null,
  "label": "footnote",
  "prov": [{
    "page_no": 41,
    "bbox": {
      "l": 73.87210569000001,
      "t": 117.65857163843748,
      "r": 314.5734145,
      "b": 103.75403187497591,
      "coord_origin": "BOTTOMLEFT"
    },
    "charspan": [0, 52]
  }],
  "orig": "· The torques in the table are for routine use only.",
  "text": "· The torques in the table are for routine use only.",
  "formatting": null,
  "hyperlink": null
}
```

### 包含标题的图片示例

```json
{
  "self_ref": "#/pictures/28",
  "parent": {"cref": "#/body"},
  "children": [
    {"cref": "#/texts/166"},
    {"cref": "#/texts/167"},
    {"cref": "#/texts/168"}
  ],
  "content_layer": "body",
  "meta": null,
  "label": "picture",
  "prov": [{
    "page_no": 23,
    "bbox": {
      "l": 314.75274658203125,
      "t": 746.3759689331055,
      "r": 544.7682495117188,
      "b": 589.5721130371094,
      "coord_origin": "BOTTOMLEFT"
    },
    "charspan": [0, 0]
  }],
  "captions": [
    {"cref": "#/texts/166"}
  ],
  "references": [],
  "footnotes": [],
  "image": null,
  "annotations": []
}
```

**说明**:
- `captions` 数组包含图片标题的引用
- `children` 数组包含与图片相关的所有子元素（标题、说明等）
- `references` 和 `footnotes` 数组可能包含对图片的引用和脚注

## 注意事项

- `image` 字段通常为 `null`，图片数据可能需要单独处理
- `coord_origin` 可能是 "BOTTOMLEFT" 或 "TOPLEFT"，需要根据实际情况处理坐标
- 文本内容同时包含 `orig`（原始）和 `text`（处理后）两个字段
- 某些字段（如 `key_value_items`、`form_items`）可能为空数组
- `code` 类型的文本块包含额外的 `code_language` 字段
- 图片可能包含 `captions`、`references`、`footnotes` 等关联信息
- `furniture` 和 `body` 是文档的根节点，通过 `children` 数组组织所有子元素
