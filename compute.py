import ast
import json
import operator
import sys
from pathlib import Path


OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.UAdd: lambda x: x,
    ast.USub: operator.neg,
}


def safe_eval(expr: str) -> float:
    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            return OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
            return OPS[type(node.op)](_eval(node.operand))
        raise ValueError("Unsupported expression")

    parsed = ast.parse(expr, mode="eval")
    return _eval(parsed)


def run(task_file: Path) -> None:
    tasks = json.loads(task_file.read_text(encoding="utf-8"))
    if not isinstance(tasks, list):
        raise ValueError("Task file must be a JSON array")

    for idx, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError(f"Task #{idx} must be an object")
        task_id = task.get("id", f"task-{idx}")
        expr = task.get("expression")
        if not isinstance(expr, str):
            raise ValueError(f"Task {task_id} missing string expression")
        result = safe_eval(expr)
        print(json.dumps({"id": task_id, "expression": expr, "result": result}, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python compute.py <task_json_file>")
    run(Path(sys.argv[1]))
