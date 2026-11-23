# FORGE ↔ AEGIS / forge-aegis/1

本文件是两个仓库的相同协议约定。通信载体是 UTF-8 JSON 文件，服务分别持久化各自数据库，不共享状态。

## 规范化与签名

```python
json.dumps(normalize_integral_floats(value), ensure_ascii=False, sort_keys=True,
           separators=(",", ":"), allow_nan=False).encode("utf-8")
```

`normalize_integral_floats` 递归把整数值浮点转换为整数（包括 0.0、-0.0），与浏览器 JSON.stringify 的行为兼容。SHA-256 使用以上规范化字节。HMAC-SHA256 对除 `signature` 外的整个正文签名，十六进制结果写入 `signature`。

当前实现要求两端使用本协议的 Python 规范化规则。不同语言的浮点序列化可能不同；跨语言实现需使用匹配的规范化程序和固定向量。此版没有宣称实现 RFC 8785。

原生工作台上传与导出保留原始 JSON 文本，不通过 JavaScript 数值重写签名对象，因此可以传递超出 JavaScript 安全整数范围的记录。自定义集成也应保留原始文本，或使用无损 JSON 数值解析。资源 ID 必须为非空文本且没有首尾空白，避免查找与写入使用不同标识。

## 交付包

| 字段 | 内容 |
|---|---|
| protocol / kind | `forge-aegis/1` / `delivery` |
| order_id / delivery_id | 采购单及唯一批次标识 |
| created_at | 含时区 ISO 8601 时间 |
| spec / spec_hash | 固定需求与规范化 SHA-256 |
| manifest | 全量/样本、声明总量、来源、许可及使用范围 |
| records / dataset_hash | 1–5000 个 JSON 对象与内容 SHA-256 |
| signature | 不含该字段的正文 HMAC |

AEGIS 拒绝签名或哈希不符、未知协议、无效 spec、非对象记录、空数据和虚假的随包全量计数。许可资料缺失进入业务复核，不视为解析失败。

`coverage: "full"` 只保证声明数量与随包数量一致；供应商是否隐瞒外部数据不由 HMAC 证明。

## 报告

| 字段 | 内容 |
|---|---|
| protocol / kind | `forge-aegis/1` / `report` |
| report_id | 唯一报告 ID |
| order_id / delivery_id | 对应原订单与原交付 |
| spec_hash / dataset_hash | 从验证后的交付继承 |
| envelope_hash | 原交付包去除 signature 后正文 SHA-256 |
| issued_at / expires_at | 同一个 UTC 签发时刻与最多 7 天后；accepted 最晚至许可截止日 23:59:59.999999 UTC |
| status | accepted / review / rejected |
| ruleset | `aegis-rules/1.0.1` |
| quality | 行缺陷、覆盖方式、Wilson 区间等 |
| findings | 规则、严重度、解释 |
| rights_review | 具名、具依据、有时间的人工核验，或 null |
| limitations | 检查限制 |
| signature | 不含该字段的正文 HMAC |

## 回流校验

FORGE 在应用决定前验证：

1. 签名、协议与 artifact kind。
2. 时间包含时区，签发时间不超过当前时间 5 分钟，未过期，期限不超过 7 天。
3. 订单存在，报告交付 ID 是当前交付，规格哈希一致。
4. 原交付正文哈希、记录哈希一致。
5. 报告状态属于允许集合。
6. 当前交付尚未应用不同报告。

同一报告的完全相同重放不追加事件。旧报告对已更换交付的订单被拒绝。报告 ID 冲突及同交付 ID 不同正文都被拒绝。

## 信任模型

HMAC 校验是可信本地 FORGE/AEGIS 服务间完整性凭证。两端共享密钥；拥有该密钥者能够制作有效签名。FORGE 信任 AEGIS 的结论，不再次执行 AEGIS 规则。

此协议不保证供应商身份、核验人真实身份、附件内容真实性、不可抵赖或防本机管理员篡改。公共 `DEMO_KEY` 在源码中，只用于合成演示。

生产升级应使用采购与验收角色不同的非对称签名、身份认证、受控的许可证据存储、密钥轮换、报告撤销及可信时间来源。
