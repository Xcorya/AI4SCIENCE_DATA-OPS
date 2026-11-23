# AEGIS JSON API

默认根地址 `http://127.0.0.1:8042`。所有 POST 使用 `application/json`，最多 8 MiB。接口限同源本地访问，不开放 CORS。

| 方法 | 路径 | 返回 |
|---|---|---|
| GET | `/api/health` | ok / app / version |
| GET | `/api/state` | 原交付、全部报告、最近 40 条事件及演示模式 |
| GET | `/api/export/reports/{report_id}` | 服务端原始签名报告，用于无损下载 |
| POST | `/api/inspect` | 新的签名验收报告 |

## Inspect 请求

```json
{
  "delivery": {
    "protocol": "forge-aegis/1",
    "kind": "delivery",
    "signature": "replace-with-a-real-FORGE-export",
    "...": "remaining actual delivery fields"
  },
  "rights_review": {
    "confirmed": true,
    "reviewer": "Named reviewer",
    "evidence_note": "Contract reference and verified scope",
    "reviewed_at": "2026-11-23T10:00:00+00:00"
  }
}
```

以上展示的是结构，不能作为有效签名包提交。实际 delivery 应使用 FORGE 完整导出文件。rights_review 可以省略或 null，产生需要独立核验的复核项；时间必须距服务当前时间在 24 小时以内。

## 输出

报告包括固定身份与内容绑定、status、quality、findings、rights_review、ruleset、limitations、签发时间、最多 7 天有效期和 HMAC。accepted 的有效期不超过许可截止日 UTC 当天结束。具体字段见 [协议](./PROTOCOL.md)。

```json
{
  "status": "rejected",
  "quality": {
    "scanned": 24,
    "defect_rows": 3,
    "defect_rate": 0.125,
    "coverage": "full",
    "threshold": 0.05
  },
  "findings": [
    {
      "rule": "quality.census",
      "severity": "reject",
      "message": "Observed defect rate exceeds the contractual threshold."
    }
  ]
}
```

这个摘录用于说明，完整响应包含更多字段。

输入协议/签名/类型不符返回 400，不生成报告。质量或许可失败仍返回 201，并生成 status 为 rejected/review 的报告。错误统一为 `{"error":"原因"}`。

每次重复 inspect 生成新报告，原交付不被同 ID 不同内容覆盖。原始数据仅保存在本地受信任工作区；state API 会包含原交付，不应转发到公共网络。

上传/下载签名对象应保留原始 JSON 文本，避免重新序列化大整数。请求帧必须完整，读取停顿超过 5 秒返回 408；内部 GET/POST 错误返回结构化 500。资源 ID 不接受首尾空白。
