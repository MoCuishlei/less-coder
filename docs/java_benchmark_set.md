# Java Benchmark Set

本基准集用于 L1 最小回归，覆盖 3 类典型 Java 修复任务：

- `input-validation`：空白输入校验
- `boundary-condition`：边界值判断
- `aggregation`：集合聚合/空集行为

## 任务清单

- `java_name_service_blank`
  - 项目：`fixtures/java-benchmarks/name-service-blank`
  - 失败点：空白字符串未返回 `UNKNOWN`

- `java_range_validator_boundary`
  - 项目：`fixtures/java-benchmarks/range-validator`
  - 失败点：边界值未被视为合法

- `java_order_total_empty`
  - 项目：`fixtures/java-benchmarks/order-total`
  - 失败点：空订单错误追加固定费用

机器可读清单见：

- `benchmarks/java_benchmark_set.json`
