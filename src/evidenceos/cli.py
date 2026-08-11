import json
from pathlib import Path
import typer
from . import __version__
from .extraction_engine_v1 import ExtractionEngineV1

app = typer.Typer(help="EvidenceOS command-line interface.", no_args_is_help=True)

@app.command()
def version():
    typer.echo(__version__)

@app.command()
def extract(
    input_file: Path = typer.Argument(..., exists=True, readable=True),
    report_id: str = typer.Option(..., "--report-id"),
    title: str = typer.Option(..., "--title"),
    output: Path | None = typer.Option(None, "--output", "-o"),
):
    text = input_file.read_text(encoding="utf-8")
    payload = json.dumps(
        ExtractionEngineV1().extract(report_id, title, text).model_dump(),
        indent=2, ensure_ascii=False,
    )
    if output:
        output.write_text(payload + "\n", encoding="utf-8")
        typer.echo(str(output))
    else:
        typer.echo(payload)

@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000):
    import uvicorn
    uvicorn.run("evidenceos.api:app", host=host, port=port)

if __name__ == "__main__":
    app()
