from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from harmonica.bootstrap import ensure_default_rating_factors
from harmonica.config import get_settings
from harmonica.db import SessionLocal, init_db
from harmonica.playlist import export_m3u8, generate_and_persist_playlist
from harmonica.scanner import scan_library
from harmonica.serialization import export_library, import_library

app = typer.Typer(help="Harmonica local music app.")


@app.command()
def init() -> None:
    """Initialize the local Harmonica database."""
    settings = get_settings()
    init_db()
    with SessionLocal() as session:
        ensure_default_rating_factors(session)
    typer.echo(f"Initialized Harmonica at {settings.home}")


@app.command()
def scan(
    library: Annotated[
        Path,
        typer.Option("--library", "-l", help="Folder containing local media files."),
    ],
    create_tag_groups: Annotated[
        bool,
        typer.Option(help="Create initial album/artist groups from tags."),
    ] = True,
) -> None:
    """Scan a folder and create draft metadata from embedded tags."""
    init_db()
    with SessionLocal() as session:
        ensure_default_rating_factors(session)
        result = scan_library(session, library, create_tag_groups=create_tag_groups)
    typer.echo(
        f"Scanned {result.scanned} files, created {result.created_tracks} tracks and "
        f"{result.created_assets} assets "
        f"({result.skipped_existing_assets} existing assets skipped)."
    )


@app.command()
def generate(
    length: Annotated[
        int,
        typer.Option("--length", "-n", min=1, help="Number of tracks to generate."),
    ] = 100,
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Playlist path."),
    ] = Path("playlist.m3u8"),
    seed: Annotated[
        str | None,
        typer.Option("--seed", help="Seed for deterministic generation."),
    ] = None,
    explain: Annotated[
        bool,
        typer.Option(help="Write JSONL score explanations."),
    ] = True,
) -> None:
    """Generate an ordered playlist and write an .m3u8 file."""
    settings = get_settings()
    init_db()
    with SessionLocal() as session:
        ensure_default_rating_factors(session)
        run, items = generate_and_persist_playlist(
            session,
            settings,
            length=length,
            seed=seed,
            write_debug_log=explain,
        )
    export_m3u8(items, output)
    typer.echo(f"Generated run {run.id} with {len(items)} items -> {output}")


@app.command("export-json")
def export_json(
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("harmonica-library.json"),
) -> None:
    """Export library metadata to JSON."""
    init_db()
    with SessionLocal() as session:
        export_library(session, output)
    typer.echo(f"Exported library metadata -> {output}")


@app.command("import-json")
def import_json(input_path: Annotated[Path, typer.Option("--input", "-i")]) -> None:
    """Import library metadata from JSON."""
    init_db()
    with SessionLocal() as session:
        ensure_default_rating_factors(session)
        import_library(session, input_path)
    typer.echo(f"Imported library metadata <- {input_path}")


@app.command()
def serve(
    host: Annotated[str | None, typer.Option("--host", help="Host to bind.")] = None,
    port: Annotated[int | None, typer.Option("--port", help="Port to bind.")] = None,
) -> None:
    """Start the Harmonica API server."""
    import uvicorn

    settings = get_settings()
    init_db()
    with SessionLocal() as session:
        ensure_default_rating_factors(session)
    uvicorn.run(
        "harmonica.api:create_app",
        factory=True,
        host=host or settings.host,
        port=port or settings.port,
        reload=False,
    )
