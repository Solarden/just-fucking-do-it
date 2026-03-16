"""Typer CLI -- thin presentation layer over service.py."""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from jfdi import art, service, sound as sound_module
from jfdi.daemon import daemon_status, start_daemon, stop_daemon

console = Console()
app = typer.Typer(
    name="jfdi",
    help="JFDI - Just Fucking Do It. Daily exercise tracker with Shia LaBeouf energy.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Sub-apps for grouped commands
config_app = typer.Typer(help="Manage configuration.", no_args_is_help=True)
message_app = typer.Typer(help="Manage notification messages.", no_args_is_help=True)
sound_app = typer.Typer(help="Manage notification sounds.", no_args_is_help=True)
daemon_app = typer.Typer(help="Manage the background notification daemon.", no_args_is_help=True)

app.add_typer(config_app, name="config")
app.add_typer(message_app, name="message")
app.add_typer(sound_app, name="sound")
app.add_typer(daemon_app, name="daemon")


# ---------------------------------------------------------------------------
# Core commands
# ---------------------------------------------------------------------------


@app.command()
def log(exercise: str, reps: int = typer.Argument(..., min=1)):
    """Log a set of reps for an exercise.  Accepts aliases (e.g. 'p' for pushups)."""
    try:
        progress = service.log_set(exercise, reps)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    cfg = service.get_config()
    if cfg.sound_enabled:
        if cfg.active_sound:
            custom = service.get_active_sound_path()
        else:
            custom = service.get_random_sound_path()
        sound_module.play_do_it(custom)

    bar_width = 30
    filled = int(bar_width * progress.pct / 100)
    bar = "[green]" + "█" * filled + "[/green]" + "[dim]░[/dim]" * (bar_width - filled)

    console.print(f"\n  [bold green]+{reps} {progress.name}![/bold green]")
    console.print(f"  [{bar}] {progress.done}/{progress.goal}")

    if progress.complete:
        console.print(f"\n  [bold yellow]{progress.name} COMPLETE![/bold yellow]")
        status = service.get_status()
        if status.all_complete:
            console.print(art.COMPLETION_ART, style="bold yellow")
            msg = service.get_random_message("completion")
            console.print(f'  [italic]"{msg}"[/italic]\n')
    else:
        console.print(f"  {progress.remaining} more to go.\n")


_MOMENTUM_LABELS = {
    "accelerating": "[green]picking up steam[/green]",
    "decelerating": "[red]slowing down[/red]",
    "steady": "[cyan]steady pace[/cyan]",
    "no_data": "",
}


@app.command()
def status():
    """Show today's progress toward each goal."""
    st = service.get_status()
    streak = service.get_streak()
    cfg = service.get_config()
    predictions = {p.name: p for p in service.get_predictions()}

    console.print(art.BANNER, style="bold cyan")

    date_str = datetime.now().strftime("%a %b %d")
    console.print(f"  [bold]Today's Progress ({date_str})[/bold]")
    console.print(f"  {'─' * 35}")

    for ex in st.exercises:
        bar_width = 30
        filled = int(bar_width * ex.pct / 100)
        bar = "[green]█[/green]" * filled + "[dim]░[/dim]" * (bar_width - filled)
        status_icon = "[green]✓[/green]" if ex.complete else " "
        console.print(
            f"  {status_icon} {ex.name:<12s} [{bar}] {ex.done}/{ex.goal}"
        )
        if ex.sets:
            sets_str = " + ".join(str(s) for s in ex.sets)
            console.print(f"    [dim]Sets: {sets_str}[/dim]")

        pred = predictions.get(ex.name)
        if pred and not ex.complete and pred.intervals_elapsed > 0:
            track_label = "[green]on track[/green]" if pred.on_track else "[red]not on track[/red]"
            momentum = _MOMENTUM_LABELS.get(pred.momentum, "")
            mom_suffix = f" ({momentum})" if momentum else ""
            console.print(
                f"    [dim]Projected: {pred.projected_total}/{pred.goal} -- {track_label}{mom_suffix}[/dim]"
            )
            if pred.pacing_str and pred.intervals_left > 0:
                console.print(
                    f"    [dim]To finish: {pred.pacing_str} over {pred.intervals_left} intervals[/dim]"
                )

    console.print()

    if streak.current > 0:
        console.print(f"  [bold yellow]Current streak: {streak.current} day{'s' if streak.current != 1 else ''}[/bold yellow]")
    if streak.best > 0 and streak.best > streak.current:
        console.print(f"  [dim]Best streak: {streak.best} days[/dim]")

    if st.daemon_running:
        adaptive = service.get_adaptive_interval()
        console.print(f"  [dim]Daemon: running (PID {st.daemon_pid}) | Interval: {adaptive}min (base {cfg.interval_minutes})[/dim]")
    else:
        console.print("  [dim]Daemon: not running (start with 'jfdi daemon start')[/dim]")

    quote = service.get_random_message("quote")
    console.print(f'\n  [italic]"{quote}"[/italic] - Shia LaBeouf\n')

    if st.all_complete:
        console.print(art.COMPLETION_ART, style="bold yellow")


@app.command()
def undo():
    """Undo the last logged set."""
    result = service.undo_last()
    console.print(f"  [yellow]{result}[/yellow]\n")


@app.command()
def history(days: int = typer.Option(7, "--days", "-d", help="Number of days to show.")):
    """Show daily totals for the last N days."""
    records = service.get_history(days)
    if not records:
        console.print("  [dim]No history yet. Start logging![/dim]\n")
        return

    table = Table(title="Exercise History", show_lines=True)
    table.add_column("Date", style="cyan")

    all_exercises: set[str] = set()
    for r in records:
        all_exercises.update(r.exercises.keys())
    for ex_name in sorted(all_exercises):
        table.add_column(ex_name.title(), justify="right")
    table.add_column("Complete", justify="center")

    for r in records:
        row = [r.date]
        for ex_name in sorted(all_exercises):
            val = r.exercises.get(ex_name, 0)
            row.append(str(val))
        row.append("[green]✓[/green]" if r.complete else "[red]✗[/red]")
        table.add_row(*row)

    console.print()
    console.print(table)
    console.print()


@app.command()
def streak():
    """Show current and best streaks."""
    info = service.get_streak()
    console.print(art.BANNER, style="bold cyan")
    console.print(f"  [bold]Current streak:[/bold] [yellow]{info.current}[/yellow] day{'s' if info.current != 1 else ''}")
    console.print(f"  [bold]Best streak:[/bold]    [yellow]{info.best}[/yellow] day{'s' if info.best != 1 else ''}")
    console.print(f"  [bold]Completed today:[/bold] {'[green]Yes[/green]' if info.completed_today else '[red]Not yet[/red]'}")
    console.print()


@app.command(name="export")
def export_cmd(
    format: str = typer.Option("csv", "--format", "-f", help="Export format: csv or json."),
    days: Optional[int] = typer.Option(None, "--days", "-d", help="Limit to last N days."),
):
    """Export exercise history to CSV or JSON."""
    try:
        path = service.export_history(fmt=format, days=days)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    console.print(f"  [green]Exported to:[/green] {path}\n")


@app.command()
def pace():
    """Show pacing predictions and optimal rep distribution."""
    predictions = service.get_predictions()
    cfg = service.get_config()

    if not predictions:
        console.print("  [dim]No active exercises.[/dim]\n")
        return

    first = predictions[0]
    console.print(f"\n  [bold]Pacing Plan[/bold] ({first.intervals_left} intervals left, every {cfg.interval_minutes}min)")
    console.print(f"  {'─' * 50}")

    for p in predictions:
        if p.remaining <= 0:
            console.print(f"  [green]✓[/green] {p.name:<12s} {p.done}/{p.goal}  [green]COMPLETE[/green]")
            continue

        track = "[green]on track[/green]" if p.on_track else "[red]behind[/red]"
        momentum = _MOMENTUM_LABELS.get(p.momentum, "")

        console.print(f"    {p.name:<12s} {p.done}/{p.goal}  Projected: {p.projected_total}  {track}")

        if p.pacing_str:
            console.print(f"    {'':12s} Need: {p.pacing_str}")

        if momentum:
            console.print(f"    {'':12s} Momentum: {momentum}")

    if any(not p.on_track and p.remaining > 0 for p in predictions):
        console.print(f"\n  [bold yellow]Pick it up! You need to push harder to hit your goals.[/bold yellow]")
    elif all(p.on_track for p in predictions):
        console.print(f"\n  [bold green]Looking good -- keep this pace and you'll crush it.[/bold green]")

    console.print()


# ---------------------------------------------------------------------------
# Config sub-commands
# ---------------------------------------------------------------------------


@config_app.command("show")
def config_show():
    """Show current configuration."""
    cfg = service.get_config()
    console.print("\n  [bold]JFDI Configuration[/bold]")
    console.print(f"  {'─' * 35}")
    console.print(f"  Interval:      {cfg.interval_minutes} min")
    console.print(f"  Sound:         {'on' if cfg.sound_enabled else 'off'}")
    console.print(f"  Quiet hours:   {cfg.quiet_hours_start}:00 - {cfg.quiet_hours_end}:00")
    console.print(f"  Active sound:  {cfg.active_sound or 'default (do_it.mp3)'}")
    console.print()
    console.print("  [bold]Exercises:[/bold]")
    for name, goal in cfg.exercises.items():
        console.print(f"    {name}: {goal}/day")
    console.print()
    console.print("  [bold]Aliases:[/bold]")
    for alias, target in cfg.aliases.items():
        console.print(f"    {alias} -> {target}")
    console.print()


@config_app.command("interval")
def config_interval(minutes: int = typer.Argument(..., min=1)):
    """Set the notification interval in minutes."""
    try:
        service.set_interval(minutes)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    console.print(f"  [green]Interval set to {minutes} minutes.[/green]\n")


@config_app.command("hours")
def config_hours(hours_range: str = typer.Argument(..., help="Active hours range, e.g. '8-22'.")):
    """Set quiet hours (notifications only within this range)."""
    try:
        start_str, end_str = hours_range.split("-")
        start, end = int(start_str), int(end_str)
        service.set_quiet_hours(start, end)
    except (ValueError, TypeError) as e:
        console.print(f"[red]Error:[/red] Invalid format. Use 'start-end', e.g. '8-22'. {e}")
        raise typer.Exit(1)
    console.print(f"  [green]Quiet hours set: notifications active {start}:00 - {end}:00[/green]\n")


@config_app.command("sound")
def config_sound(state: str = typer.Argument(..., help="'on' or 'off'.")):
    """Enable or disable sound."""
    if state.lower() not in ("on", "off"):
        console.print("[red]Error:[/red] Use 'on' or 'off'.")
        raise typer.Exit(1)
    service.set_sound(state.lower() == "on")
    console.print(f"  [green]Sound {'enabled' if state.lower() == 'on' else 'disabled'}.[/green]\n")


@config_app.command("add")
def config_add(exercise: str, goal: int = typer.Argument(..., min=1)):
    """Add or update an exercise."""
    try:
        service.add_exercise(exercise, goal)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    console.print(f"  [green]Exercise '{exercise}' set with goal {goal}/day.[/green]\n")


@config_app.command("remove")
def config_remove(exercise: str):
    """Remove (deactivate) an exercise."""
    try:
        service.remove_exercise(exercise)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    console.print(f"  [green]Exercise '{exercise}' removed.[/green]\n")


@config_app.command("alias")
def config_alias(exercise: str, key: str):
    """Set a shorthand alias for an exercise (e.g. 'pushups p')."""
    try:
        service.set_alias(exercise, key)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    console.print(f"  [green]Alias '{key}' -> '{exercise}' set.[/green]\n")


# ---------------------------------------------------------------------------
# Message sub-commands
# ---------------------------------------------------------------------------


@message_app.command("list")
def message_list(
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter: nudge, completion, quote."),
):
    """List all notification messages."""
    messages = service.list_messages(category)
    if not messages:
        console.print("  [dim]No messages found.[/dim]\n")
        return

    table = Table(title="Notification Messages")
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Category", style="cyan")
    table.add_column("Message")
    table.add_column("Built-in", justify="center")

    for m in messages:
        table.add_row(
            str(m.id),
            m.category,
            m.text,
            "yes" if m.is_builtin else "",
        )

    console.print()
    console.print(table)
    console.print()


@message_app.command("add")
def message_add(category: str, text: str):
    """Add a custom notification message."""
    try:
        msg = service.add_message(text, category)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    console.print(f"  [green]Message added (ID {msg.id}): \"{msg.text}\"[/green]\n")


@message_app.command("remove")
def message_remove(id: int):
    """Remove a notification message by ID."""
    try:
        service.remove_message(id)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    console.print(f"  [green]Message {id} removed.[/green]\n")


# ---------------------------------------------------------------------------
# Sound sub-commands
# ---------------------------------------------------------------------------


@sound_app.command("list")
def sound_list():
    """List available sounds."""
    sounds = service.list_sounds()

    console.print()
    if not sounds:
        console.print("  [dim]No custom sounds added.[/dim]")
    else:
        table = Table(title="Available Sounds")
        table.add_column("ID", style="dim", justify="right")
        table.add_column("Name", style="cyan")
        table.add_column("Path")
        table.add_column("Default", justify="center")

        for s in sounds:
            table.add_row(str(s.id), s.name, s.path, "yes" if s.is_default else "")
        console.print(table)

    console.print()
    if not sound_module.sound_available():
        console.print(sound_module.setup_sound_instructions())


@sound_app.command("add")
def sound_add(name: str, path: str):
    """Add a custom sound file (mp3/wav/m4a/aiff)."""
    try:
        entry = service.add_sound(name, path)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    console.print(f"  [green]Sound '{entry.name}' added from {path}[/green]\n")


@sound_app.command("remove")
def sound_remove(id: int):
    """Remove a custom sound by ID."""
    try:
        service.remove_sound(id)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    console.print(f"  [green]Sound {id} removed.[/green]\n")


@sound_app.command("use")
def sound_use(name: str):
    """Set which sound to play on notifications."""
    try:
        service.set_active_sound(name)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    console.print(f"  [green]Active sound set to '{name}'.[/green]\n")


# ---------------------------------------------------------------------------
# Daemon sub-commands
# ---------------------------------------------------------------------------


@daemon_app.command("start")
def daemon_start():
    """Start the background notification daemon."""
    pid = start_daemon()
    if service.is_daemon_running():
        console.print(f"  [green]Daemon running (PID {pid}).[/green]\n")
    else:
        console.print("  [red]Failed to start daemon.[/red]\n")
        raise typer.Exit(1)


@daemon_app.command("stop")
def daemon_stop():
    """Stop the background notification daemon."""
    if stop_daemon():
        console.print("  [green]Daemon stopped.[/green]\n")
    else:
        console.print("  [dim]Daemon was not running.[/dim]\n")


@daemon_app.command("status")
def daemon_status_cmd():
    """Check if the daemon is running."""
    info = daemon_status()
    if info["running"]:
        console.print(f"  [green]Daemon: running[/green] (PID {info['pid']})")
        if info["started_at"]:
            console.print(f"  [dim]Started at: {info['started_at']}[/dim]")
    else:
        console.print("  [dim]Daemon: not running[/dim]")
    console.print()


# ---------------------------------------------------------------------------
# Shorthand alias handling
# ---------------------------------------------------------------------------
# Typer doesn't natively support "catch-all" commands, so we handle aliases
# by checking sys.argv before Typer processes them.


def _maybe_handle_alias() -> None:
    """If the first arg looks like an alias + number, rewrite argv for the log command."""
    if len(sys.argv) < 3:
        return

    potential_alias = sys.argv[1]

    # Skip if it's a known command or subcommand
    known = {
        "log", "status", "undo", "history", "streak", "export", "pace",
        "config", "message", "sound", "daemon",
        "--help", "-h", "--install-completion", "--show-completion",
    }
    if potential_alias in known:
        return

    # Check if the second arg is a number (reps)
    try:
        int(sys.argv[2])
    except (ValueError, IndexError):
        return

    # Try to resolve the alias
    resolved = service.resolve_alias(potential_alias)
    if resolved != potential_alias:
        sys.argv = [sys.argv[0], "log", resolved, sys.argv[2]] + sys.argv[3:]


def main() -> None:
    service._ensure_db()
    _maybe_handle_alias()
    app()


if __name__ == "__main__":
    main()
