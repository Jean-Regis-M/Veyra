"""MCP Tools: Model Runtime Management.

Expose model provisioning and verification capabilities to agents.

setup_model: Provision an isolated runtime for a model.
verify_model: Run health check on a model runtime.
models_list_runtimes: List all model runtime states.
model_status: Get detailed status for a specific model runtime.

IMPORTANT for AI agents:
- setup_model may be expensive (creates venv, installs packages)
- setup_model modifies ONLY project-local environments under data/model_envs/
- No system Python modification occurs
- Explicit model setup does NOT imply fallback to another model
- Verification is required before a model becomes auto-eligible
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.schemas import ToolResult


def models_list_runtimes_tool() -> ToolResult:
    """List all model runtime states.

    Returns the provisioning and verification status for each model,
    including whether an isolated runtime exists and is verified.

    Returns:
        ToolResult with list of runtime states per model.
    """
    from core.model_runtime import list_model_runtimes

    runtimes = list_model_runtimes()

    return ToolResult(
        tool="models_list_runtimes",
        rows=[],
        summary={"runtimes": runtimes},
    )


def model_status_tool(model_id: str) -> ToolResult:
    """Get detailed status for a specific model runtime.

    Args:
        model_id: Model identifier (rule_set_2, rule_set_3, doench_2014)

    Returns:
        ToolResult with detailed runtime status including:
        - state (not_provisioned, provisioned, verified, incompatible, failed)
        - runtime_path
        - python_version
        - dependency_status
        - verification_status
    """
    from core.model_runtime import get_model_status, get_model_spec

    if not get_model_spec(model_id):
        return ToolResult(
            tool="model_status",
            errors=[f"Unknown model: {model_id}"],
        )

    status = get_model_status(model_id)
    return ToolResult(
        tool="model_status",
        rows=[],
        summary={"model_id": model_id, "status": status},
    )


def setup_model_tool(model_id: str, force: bool = False) -> ToolResult:
    """Provision an isolated runtime for a model.

    This creates an isolated Python virtualenv under data/model_envs/
    and installs the model's required dependencies.

    IMPORTANT:
    - This may take several minutes (creates venv, installs packages)
    - Only modifies project-local environments — does NOT touch system Python
    - For rule_set_2: installs scikit-learn==0.16.1 in an isolated env (requires compatible Python)
    - For rule_set_3: installs rs3 + compatible lightgbm in isolated env
    - For doench_2014: no provisioning needed (pure Python, built-in)

    Args:
        model_id: Model to provision (rule_set_2, rule_set_3, doench_2014)
        force: If True, recreate the environment even if it exists

    Returns:
        ToolResult with provisioning outcome and runtime details
    """
    from core.model_runtime import provision_model, get_model_spec

    if not get_model_spec(model_id):
        return ToolResult(
            tool="setup_model",
            errors=[f"Unknown model: {model_id}"],
        )

    result = provision_model(model_id, force=force)

    return ToolResult(
        tool="setup_model",
        rows=[],
        summary={"model_id": model_id, "result": result},
    )


def verify_model_tool(model_id: str) -> ToolResult:
    """Verify a model runtime with reference health check.

    Runs the model's verification test case in its isolated runtime
    (or main environment for built-in models).

    A model must pass verification before it becomes eligible for
    auto-selection.

    Args:
        model_id: Model to verify (rule_set_2, rule_set_3, doench_2014)

    Returns:
        ToolResult with verification outcome (pass/fail)
    """
    from core.model_runtime import verify_model, get_model_spec

    if not get_model_spec(model_id):
        return ToolResult(
            tool="verify_model",
            errors=[f"Unknown model: {model_id}"],
        )

    result = verify_model(model_id)

    return ToolResult(
        tool="verify_model",
        rows=[],
        summary={"model_id": model_id, "result": result},
    )


# --- CLI entry points ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VEYRA model runtime management tools")
    sub = parser.add_subparsers(dest="command")

    p1 = sub.add_parser("list-runtimes", help="List all model runtime states")
    p1.set_defaults(func=lambda a: models_list_runtimes_tool())

    p2 = sub.add_parser("status", help="Get model runtime status")
    p2.add_argument("model_id", help="Model ID")
    p2.set_defaults(func=lambda a: model_status_tool(a.model_id))

    p3 = sub.add_parser("setup", help="Provision model runtime")
    p3.add_argument("model_id", help="Model ID")
    p3.add_argument("--force", action="store_true", help="Force reprovision")
    p3.set_defaults(func=lambda a: setup_model_tool(a.model_id, a.force))

    p4 = sub.add_parser("verify", help="Verify model runtime")
    p4.add_argument("model_id", help="Model ID")
    p4.set_defaults(func=lambda a: verify_model_tool(a.model_id))

    args = parser.parse_args()
    if hasattr(args, "func"):
        result = args.func(args)
        print(result.to_json(indent=2))
    else:
        parser.print_help()
