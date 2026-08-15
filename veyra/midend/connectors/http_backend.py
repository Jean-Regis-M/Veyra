"""HTTP Backend Connector for VEYRA FastAPI backend."""

from __future__ import annotations
import httpx
from typing import Any, Optional
try:
    from ..config.settings import get_settings
    from .base import BackendConnector
    from .errors import ToolNotFoundError, ToolExecutionError, ConnectorTimeoutError, ConnectorError
    from .models import BackendToolSchema, ToolExecutionResult
except ImportError:  # pragma: no cover
    from config.settings import get_settings
    from connectors.base import BackendConnector
    from connectors.errors import ToolNotFoundError, ToolExecutionError, ConnectorTimeoutError, ConnectorError
    from connectors.models import BackendToolSchema, ToolExecutionResult

TOOL_ENDPOINT_MAP = {
    "ingest": ("POST", "/ingest"),
    "ingest_file": ("POST", "/ingest"),
    "pam_scan": ("POST", "/pam/scan"),
    "pam_scan_region": ("POST", "/pam/scan-region"),
    "build_offtarget_index": ("POST", "/index/build"),
    "build_index": ("POST", "/index/build"),
    "offtarget_search": ("POST", "/offtarget/search"),
    "cas_offinder_search": ("POST", "/offtarget/search"),  # passed via backend="cas_offinder"
    "score_offtargets": ("POST", "/offtarget/score"),
    "rank_candidates": ("POST", "/rank"),
    "list_genomes": ("GET", "/genomes"),
    "genome_info": ("GET", "/genomes/{genome_id}"),
    "cache_status": ("GET", "/cache/status"),
    "clear_cache": ("POST", "/cache/clear"),
    "list_tools": ("GET", "/tools"),
    "compute_gc_content": ("POST", "/sequence/gc"),
    "check_homopolymer_runs": ("POST", "/sequence/homopolymer"),
    "compute_melting_temp": ("POST", "/sequence/tm"),
    "compute_secondary_structure": ("POST", "/sequence/secondary-structure"),
    "compute_positional_features": ("POST", "/sequence/positional-features"),
    "compute_dinucleotide_composition": ("POST", "/sequence/dinucleotide-composition"),
    "compute_seed_gc": ("POST", "/sequence/seed-gc"),
    "analyze_mismatch_seed": ("POST", "/offtarget/analyze-seed"),
    "compute_cut_site": ("POST", "/sequence/cut-site"),
    "predict_ontarget_efficiency": ("POST", "/score/ontarget"),
    "models_list_runtimes": ("GET", "/models"),
    "model_status": ("GET", "/models/{model_id}"),
    "setup_model": ("POST", "/models/{model_id}/setup"),
    "verify_model": ("POST", "/models/{model_id}/verify"),
}


class HTTPBackendConnector(BackendConnector):
    """HTTP-based connector communicating with VEYRA FastAPI backend."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        headers: Optional[dict[str, str]] = None,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.veyra_backend_url).rstrip("/")
        self.timeout = timeout or settings.midend_backend_timeout
        self.headers = headers or {"Content-Type": "application/json"}

    @property
    def connector_type(self) -> str:
        return "http"

    async def list_tools(self) -> list[BackendToolSchema]:
        """Fetch registered tools from backend GET /tools endpoint."""
        url = f"{self.base_url}/tools"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, headers=self.headers)
                res.raise_for_status()
                data = res.json()
                tools_data = data.get("tools", [])
                schemas = []
                for t in tools_data:
                    name = t.get("name")
                    schemas.append(
                        BackendToolSchema(
                            name=name,
                            description=t.get("description", f"VEYRA backend tool: {name}"),
                            argument_schema={},
                            availability="available",
                            connector_source="http",
                            tier=t.get("tier"),
                            cost=t.get("cost"),
                        )
                    )
                return schemas
        except Exception as e:
            # Fallback to known mapping if backend /tools unavailable during offline testing
            schemas = []
            for name in TOOL_ENDPOINT_MAP:
                schemas.append(
                    BackendToolSchema(
                        name=name,
                        description=f"VEYRA backend tool: {name}",
                        connector_source="http",
                    )
                )
            return schemas

    async def get_tool_schema(self, tool_name: str) -> BackendToolSchema:
        tools = await self.list_tools()
        for t in tools:
            if t.name == tool_name:
                return t
        if tool_name in TOOL_ENDPOINT_MAP:
            return BackendToolSchema(
                name=tool_name,
                description=f"VEYRA backend tool: {tool_name}",
                connector_source="http",
            )
        raise ToolNotFoundError(tool_name, "http")

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        if tool_name not in TOOL_ENDPOINT_MAP:
            raise ToolNotFoundError(tool_name, "http")

        method, path_template = TOOL_ENDPOINT_MAP[tool_name]
        
        # Handle path formatting if needed
        args = dict(arguments)
        if "{genome_id}" in path_template:
            genome_id = args.pop("genome_id", "default")
            path = path_template.format(genome_id=genome_id)
        elif "{model_id}" in path_template:
            model_id = args.pop("model_id", "rule_set_3")
            path = path_template.format(model_id=model_id)
        else:
            path = path_template

        url = f"{self.base_url}{path}"

        # Adjust specific tool defaults if required
        if tool_name == "cas_offinder_search":
            args["backend"] = "cas_offinder"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method == "GET":
                    res = await client.get(url, params=args, headers=self.headers)
                else:
                    res = await client.post(url, json=args, headers=self.headers)

                data = res.json()
                if res.status_code >= 400:
                    err_msg = data.get("detail", res.text)
                    if isinstance(err_msg, dict):
                        err_msg = err_msg.get("errors", [str(err_msg)])
                    if isinstance(err_msg, list):
                        err_msg = "; ".join(str(e) for e in err_msg)
                    return ToolExecutionResult(
                        tool=tool_name,
                        rows=[],
                        summary={},
                        errors=[str(err_msg)],
                        warnings=[],
                        metadata={},
                        raw_response=data if isinstance(data, dict) else {"detail": data},
                    )

                return ToolExecutionResult(
                    tool=data.get("tool", tool_name),
                    rows=data.get("rows", []),
                    summary=data.get("summary", {}),
                    errors=data.get("errors", []),
                    warnings=data.get("warnings", []),
                    metadata=data.get("metadata", {}),
                    raw_response=data,
                )

        except httpx.TimeoutException:
            raise ConnectorTimeoutError(tool_name, self.timeout)
        except httpx.HTTPStatusError as e:
            raise ToolExecutionError(tool_name, f"HTTP Error {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise ToolExecutionError(tool_name, str(e))
