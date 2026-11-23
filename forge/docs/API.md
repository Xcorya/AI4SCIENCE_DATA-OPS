# FORGE JSON API

默认根地址 `http://127.0.0.1:8041`。所有 POST 使用 `Content-Type: application/json`，最多 8 MiB。接口不启用 CORS。GET 成功返回 200，POST 成功返回 201。字段或业务约束失败返回 400，未知路由 404，跨域/Host 拒绝 403，错误内容类型 415，体积错误 413。

## 端点

| 方法 | 路径 | 请求 |
|---|---|---|
| GET | `/api/health` | 无 |
| GET | `/api/state` | 全部业务记录与最近 40 条事件 |
| GET | `/api/rank/{demand_id}` | 当前需求的解释性报价排序 |
| GET | `/api/export/deliveries/{delivery_id}` | 服务端原始交付对象，用于无损下载 |
| POST | `/api/demands` | 需求 spec 本身 |
| POST | `/api/quotes` | `{"demand_id":"REQ-…","quote":{…}}` |
| POST | `/api/orders` | `{"demand_id":"REQ-…","quote_id":"QTE-…"}` |
| POST | `/api/orders/release` | `{"order_id":"PO-…"}` |
| POST | `/api/deliveries` | `{"order_id":"PO-…","manifest":{…},"records":[…]}` |
| POST | `/api/reports/import` | `{"report":{签名 AEGIS 报告}}` |

## 需求

```json
{
  "title": "Dataset batch",
  "quantity": 24,
  "budget_cents": 120000,
  "currency": "CNY",
  "max_days": 14,
  "purpose": "model_training",
  "region": "CN",
  "max_defect_rate": 0.05,
  "allow_derivatives": true,
  "allow_pii": false,
  "schema": {"id": "string", "text": "string", "language": "string"},
  "unique_key": "id"
}
```

数量 1–5000，币种 CNY/USD/EUR，缺陷阈值 0–1。schema 1–50 个必填字段，类型 string/integer/number/boolean。唯一键必须属于 schema。布尔值不能代替整数。

`allow_derivatives: true` 表示本次采购需要派生使用权限；`false` 表示本次采购不要求这一权限，不主动禁止供应商授予它。PII 标记控制检测到个人信息线索时是否要求复核。

## 报价

```json
{
  "vendor": "Example supplier",
  "unit_cents": 3200,
  "fee_cents": 6000,
  "capacity": 100,
  "lead_days": 10,
  "currency": "CNY",
  "declared_quality": 0.97,
  "evidence": "Contract or internal review reference",
  "purposes": ["model_training"],
  "regions": ["CN"],
  "derivatives": true,
  "rights_verified": true
}
```

报价核验状态是采购人员的输入，不是供应商身份或外部许可真实性校验。数值与布尔必须使用实际 JSON 类型。

## 交付 manifest

```json
{
  "coverage": "full",
  "record_count": 24,
  "source": "Documented source",
  "license": "Contract identifier",
  "evidence": "Verified contract reference",
  "rights_verified": true,
  "purposes": ["model_training"],
  "regions": ["CN"],
  "derivatives": true,
  "valid_until": "2030-12-31",
  "prohibited_source": false
}
```

完整交付的 `record_count` 必须等于提供记录数。样本可设置 `coverage: "sample"`，但不会由 AEGIS 自动通过。许可证据不完整的交付可以登记，随后由 AEGIS 复核/拒收。

工作台使用 `{"order_id":"PO-…","delivery":{"manifest":{…},"records":[…]}}` 的嵌套格式，文件内部的 order_id 不会覆盖外层选择。原有顶层 manifest/records 格式继续支持。ID 不接受首尾空白；签名下载应直接保存响应文本，避免浏览器重新序列化大整数。

## 调用示例

```bash
curl http://127.0.0.1:8041/api/health

# spec.json 按上面的需求结构保存
curl -X POST http://127.0.0.1:8041/api/demands \
  -H 'Content-Type: application/json' --data-binary @spec.json
```

错误统一为 `{"error":"原因"}`。失败不更新业务状态。`/api/state` 包含数据记录，仅适合受信任的本地工作区。

请求必须提供完整且单一的 Content-Length，不支持 Transfer-Encoding。短帧返回 400，读取停顿超过 5 秒返回 408；数据库等内部 GET/POST 失败返回结构化 500。
