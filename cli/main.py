"""
LLMFed CLI — command-line management tool for the wrestling simulation.

Usage:
    llmfed init                          Initialize database
    llmfed world create <name>           Create a new game world
    llmfed world list                    List all worlds
    llmfed world status <world_id>       Show world status
    llmfed world advance <world_id> -d N Advance world by N days
    llmfed fed list <world_id>           List federations in a world
    llmfed fed roster <fed_id>           Show federation roster
    llmfed sim run <world_id> --days N   Run simulation for N days
    llmfed match replay <match_id>       Print match play-by-play
    llmfed maintenance run               Run data cleanup
    llmfed stats                         Show database statistics
"""

import logging
import sys
import os

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Ensure project root is importable
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

app = typer.Typer(name="llmfed", help="LLMFed wrestling simulation CLI")
console = Console()

# Sub-commands
world_app = typer.Typer(help="Manage game worlds")
fed_app = typer.Typer(help="Manage federations")
sim_app = typer.Typer(help="Simulation controls")
app.add_typer(world_app, name="world")
app.add_typer(fed_app, name="fed")
app.add_typer(sim_app, name="sim")


def _get_db():
    """Get a database session."""
    from agent_service.database import SessionLocal
    return SessionLocal()


# ---------------------------------------------------------------------------
# Top-level commands
# ---------------------------------------------------------------------------

@app.command()
def init():
    """Initialize the database tables."""
    from agent_service.database import init_db
    init_db()
    console.print("[green]Database initialized successfully.[/green]")


@app.command()
def stats():
    """Show database table statistics."""
    from game_service.maintenance_service import get_table_stats
    db = _get_db()
    try:
        data = get_table_stats(db)
        table = Table(title="Database Statistics")
        table.add_column("Table", style="cyan")
        table.add_column("Row Count", justify="right", style="green")
        for name, count in sorted(data.items()):
            table.add_row(name, str(count))
        console.print(table)
    finally:
        db.close()


@app.command()
def maintenance(
    narrative_retention: int = typer.Option(10000, help="Max narrative logs to keep"),
    request_retention: int = typer.Option(5000, help="Max engine requests to keep"),
):
    """Run data lifecycle maintenance (prune old logs)."""
    from game_service.maintenance_service import run_full_maintenance
    db = _get_db()
    try:
        results = run_full_maintenance(db, narrative_retention, request_retention)
        for key, value in results.items():
            console.print(f"  {key}: {value}")
        console.print("[green]Maintenance complete.[/green]")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# World commands
# ---------------------------------------------------------------------------

@world_app.command("create")
def world_create(name: str = typer.Argument(..., help="World name")):
    """Create a new game world."""
    from game_service.world_service import create_world
    db = _get_db()
    try:
        world = create_world(db, name)
        console.print(Panel(
            f"[green]World created![/green]\n"
            f"ID: {world.id}\n"
            f"Name: {world.name}\n"
            f"Game date: {world.current_game_date}",
            title="New World",
        ))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
    finally:
        db.close()


@world_app.command("list")
def world_list():
    """List all game worlds."""
    from models.game_models import WorldDB
    db = _get_db()
    try:
        worlds = db.query(WorldDB).all()
        if not worlds:
            console.print("[yellow]No worlds found. Use 'llmfed world create <name>'.[/yellow]")
            return
        table = Table(title="Game Worlds")
        table.add_column("ID", style="cyan", max_width=12)
        table.add_column("Name", style="white")
        table.add_column("Game Date", style="green")
        table.add_column("Tick", justify="right")
        table.add_column("Active", justify="center")
        for w in worlds:
            table.add_row(
                str(w.id)[:12],
                w.name,
                getattr(w, "current_game_date", "?"),
                str(getattr(w, "current_tick", 0)),
                "Y" if getattr(w, "is_active", True) else "N",
            )
        console.print(table)
    finally:
        db.close()


@world_app.command("status")
def world_status(world_id: str = typer.Argument(..., help="World ID")):
    """Show detailed status of a game world."""
    from models.game_models import WorldDB, GameFederationDB, GameWrestlerDB
    db = _get_db()
    try:
        world = db.query(WorldDB).filter(WorldDB.id == world_id).first()
        if not world:
            console.print(f"[red]World '{world_id}' not found.[/red]")
            return

        fed_count = db.query(GameFederationDB).filter(
            GameFederationDB.world_id == world_id
        ).count()
        wrestler_count = db.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == world_id
        ).count()

        console.print(Panel(
            f"Name: {world.name}\n"
            f"Game Date: {getattr(world, 'current_game_date', '?')}\n"
            f"Tick: {getattr(world, 'current_tick', 0)}\n"
            f"Federations: {fed_count}\n"
            f"Wrestlers: {wrestler_count}\n"
            f"Active: {getattr(world, 'is_active', True)}",
            title=f"World: {world.name}",
        ))
    finally:
        db.close()


@world_app.command("advance")
def world_advance(
    world_id: str = typer.Argument(..., help="World ID"),
    days: int = typer.Option(1, "-d", "--days", help="Number of days to advance"),
):
    """Advance a world by N game days."""
    from game_service.world_ticker import WorldTicker
    db = _get_db()
    try:
        ticker = WorldTicker(db, world_id)
        with console.status(f"Advancing {days} day(s)..."):
            result = ticker.tick(days)
            db.commit()
        console.print(f"[green]Advanced {days} day(s). New date: {result.get('new_game_date', '?')}[/green]")
    except Exception as e:
        db.rollback()
        console.print(f"[red]Error: {e}[/red]")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Federation commands
# ---------------------------------------------------------------------------

@fed_app.command("list")
def fed_list(world_id: str = typer.Argument(..., help="World ID")):
    """List federations in a world."""
    from models.game_models import GameFederationDB
    db = _get_db()
    try:
        feds = db.query(GameFederationDB).filter(
            GameFederationDB.world_id == world_id
        ).all()
        if not feds:
            console.print("[yellow]No federations in this world.[/yellow]")
            return
        table = Table(title="Federations")
        table.add_column("ID", style="cyan", max_width=12)
        table.add_column("Name", style="white")
        table.add_column("Size", style="green")
        table.add_column("Balance", justify="right")
        for f in feds:
            table.add_row(
                str(f.id)[:12],
                f.name,
                getattr(f, "size", "?"),
                f"${getattr(f, 'balance', 0):,.0f}",
            )
        console.print(table)
    finally:
        db.close()


@fed_app.command("roster")
def fed_roster(federation_id: str = typer.Argument(..., help="Federation ID")):
    """Show a federation's wrestler roster."""
    from models.game_models import GameWrestlerDB, ContractDB
    db = _get_db()
    try:
        contracts = db.query(ContractDB).filter(
            ContractDB.federation_id == federation_id,
            ContractDB.status == "active",
        ).all()
        if not contracts:
            console.print("[yellow]No active contracts for this federation.[/yellow]")
            return
        wrestler_ids = [c.wrestler_id for c in contracts]
        wrestlers = db.query(GameWrestlerDB).filter(
            GameWrestlerDB.id.in_(wrestler_ids)
        ).all()
        table = Table(title="Roster")
        table.add_column("Name", style="white")
        table.add_column("Ring Name", style="cyan")
        table.add_column("Alignment", style="yellow")
        table.add_column("Overall", justify="right", style="green")
        for w in wrestlers:
            table.add_row(
                getattr(w, "real_name", "?"),
                w.ring_name,
                getattr(w, "alignment", "?"),
                str(getattr(w, "overall_rating", "?")),
            )
        console.print(table)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Simulation commands
# ---------------------------------------------------------------------------

@sim_app.command("run")
def sim_run(
    world_id: str = typer.Argument(..., help="World ID"),
    days: int = typer.Option(1, "--days", "-d", help="Days to simulate"),
):
    """Run the simulation for N days (alias for world advance)."""
    world_advance(world_id, days)


@sim_app.command("status")
def sim_status(world_id: str = typer.Argument(..., help="World ID")):
    """Show simulation status (alias for world status)."""
    world_status(world_id)


# ---------------------------------------------------------------------------
# Match replay
# ---------------------------------------------------------------------------

@app.command("match")
def match_replay(match_id: str = typer.Argument(..., help="Match ID")):
    """Replay a match spot-by-spot."""
    from models.show_models import MatchDB, MatchParticipantDB, MatchEventDB
    db = _get_db()
    try:
        match = db.query(MatchDB).filter(MatchDB.id == match_id).first()
        if not match:
            console.print(f"[red]Match '{match_id}' not found.[/red]")
            return

        console.print(Panel(
            f"Type: {match.match_type}\n"
            f"Stipulation: {match.stipulation or 'Standard'}\n"
            f"Rating: {match.match_rating or '?'} stars\n"
            f"Winner: {match.winner_id or 'N/A'}\n"
            f"Finish: {match.finish_type or '?'} — {match.finish_description or ''}",
            title="Match Details",
        ))

        # Show events if available
        try:
            events = db.query(MatchEventDB).filter(
                MatchEventDB.match_id == match_id
            ).order_by(MatchEventDB.sequence).all()
            if events:
                console.print("\n[bold]Play-by-Play:[/bold]")
                for ev in events:
                    console.print(f"  [{ev.sequence:3d}] {ev.description}")
        except Exception:
            console.print("[dim]No detailed play-by-play available.[/dim]")
    finally:
        db.close()


if __name__ == "__main__":
    app()
