"""Read-only Mendix tools; the existing repository workspace is unchanged."""

import asyncio

from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes

from app.dependencies import container
from app.security import identity
from app.tools.workspace import READ

CACHE = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": False,
}


def register(server: FastMCP) -> None:
    @server.tool(annotations=READ, auth=require_scopes("repo:read"))
    def mendix_info() -> dict:
        """Show host-configured Mendix project, exporter, and supported unit types.
        Reads saved local files only. Does not change the repository workspace.
        """
        return container.mendix.info()

    @server.tool(annotations=CACHE, auth=require_scopes("repo:read", "repo:run"))
    async def mendix_start_export(
        modules: str,
        unit_types: str = "DomainModels$DomainModel,Microflows$Microflow,Pages$Page",
    ) -> dict:
        """Start background mx dump-mpr for explicit comma-separated modules.
        No project edits. Poll mendix_export_status until completed; then list units.
        Export requires repo:run because it starts the host-configured mx executable.
        """
        return await container.mendix.start_export(modules, unit_types)

    @server.tool(annotations=READ, auth=require_scopes("repo:read"))
    def mendix_export_status(export_id: str) -> dict:
        """Read export status/counts. Restart interrupts unfinished exports."""
        return container.mendix.export_status(export_id)

    @server.tool(annotations=READ, auth=require_scopes("repo:read"))
    def mendix_list_units(
        export_id: str,
        query: str = "",
        offset: int = 0,
        limit: int = 30,
    ) -> dict:
        """List/search exported unit names and IDs. Paginate using next_offset.
        Results refer to an immutable saved-model snapshot, not the live editor.
        """
        return container.mendix.list_units(export_id, query, offset, limit)

    @server.tool(annotations=READ, auth=require_scopes("repo:read"))
    def mendix_read_unit(export_id: str, unit_id: str, chunk: int = 0) -> dict:
        """Read bounded JSON evidence; follow next_chunk. Lines refer to exported
        unit JSON, not source files. Related IDs require separately reading units.
        """
        return container.mendix.read_unit(export_id, unit_id, chunk)

    @server.tool(annotations=CACHE, auth=require_scopes("repo:read", "chat"))
    async def mendix_start_report(export_id: str, unit_id: str) -> dict:
        """Create a resumable Vietnamese Ollama report for one exported unit.
        Does not call Ollama yet. Call mendix_report_step once per chunk.
        """
        return await asyncio.to_thread(
            container.mendix.start_report,
            export_id,
            unit_id,
            identity(),
        )

    @server.tool(annotations=CACHE, auth=require_scopes("repo:read", "chat"))
    async def mendix_report_step(report_id: str) -> dict:
        """Review exactly one chunk with local Ollama and persist progress.
        Repeat while pending. retry_required preserves position: inspect error,
        wait if router is busy, then retry. Report restart resumes from saved step.
        Model claims require verification; output truncation is flagged in metrics.
        """
        return await container.mendix.report_step(report_id, identity())

    @server.tool(annotations=READ, auth=require_scopes("repo:read", "chat"))
    def mendix_report_status(report_id: str, offset: int = 0, limit: int = 10) -> dict:
        """Read this identity's saved report and evidence references with pagination.
        Completed means every chunk was processed, not that the whole app was verified.
        """
        return container.mendix.report_status(report_id, identity(), offset, limit)

    @server.tool(annotations=READ, auth=require_scopes("repo:read"))
    def mendix_list_sources(offset: int = 0, limit: int = 50) -> dict:
        """List confined custom Java/JS/TS/style/XML source paths in Mendix roots.
        Does not list project data, deployment, keys or configuration files.
        """
        return container.mendix.list_sources(offset, limit)

    @server.tool(annotations=READ, auth=require_scopes("repo:read"))
    def mendix_read_source(path: str, start_line: int = 1, end_line: int = 100) -> dict:
        """Read a relative Mendix source path with real source lines and SHA256.
        Use returned code as evidence for chat or a proposed implementation.
        This tool cannot write source or edit the MPR.
        """
        return container.mendix.read_source(path, start_line, end_line)
