# java-sample fixture

用于 L1 真实联调的最小 Java 样例项目。

## 运行

```bash
mvn test
```

## 预期状态（当前）

- 测试可运行
- 存在 1 个已知失败用例：`shouldReturnUnknownForBlank`
- 缺陷位置：`src/main/java/com/acme/NameService.java`

## 缺陷说明

`normalizeName` 仅判断 `null`，未把纯空白字符串当作无效输入处理。  
后续修复目标：空白字符串也返回 `UNKNOWN`。
