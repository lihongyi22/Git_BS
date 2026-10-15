# Codex 云端计算仓库

这是一个最小可用示例仓库，用于让 Codex 在云端自动执行计算任务。

## 功能

- 使用 `compute.py` 读取 JSON 任务并执行安全算术计算
- 通过 GitHub Actions 在云端运行计算任务
- 支持手动触发工作流，或推送计算相关文件后自动触发

## 本地运行

```bash
python compute.py tasks/sample_tasks.json
```

## 任务格式

`tasks/*.json` 文件格式：

```json
[
  { "id": "job-1", "expression": "2 + 3 * 4" },
  { "id": "job-2", "expression": "(10 - 3) / 7" }
]
```

## 云端运行

1. 打开 GitHub 仓库的 **Actions**
2. 选择 **Cloud Compute**
3. 点击 **Run workflow**
4. 在日志中查看每个任务的计算结果
