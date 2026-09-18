"""Thingiverse authentication CLI: login, status, logout.

Invoked via bin/tv_auth. Logs in with your Thingiverse account
(password prompted, never stored) and persists tokens for the
publish/sync tooling. See openforge/thingiverse/auth.py.
"""

import logging
import sys

import click

from openforge.thingiverse.auth import (
    NotLoggedIn,
    ThingiverseAuthError,
    TokenManager,
    TwoFactorRequired,
)


def _configure_logging(verbose: int, quiet: bool):
    if quiet:
        level = logging.ERROR
    else:
        level = max(logging.WARNING - verbose * 10, logging.DEBUG)
    logging.basicConfig(level=level, stream=sys.stderr)


@click.group()
@click.option("-v", "--verbose", count=True, help="Increase verbosity (-v, -vv)")
@click.option("-q", "--quiet", is_flag=True, help="Errors only")
def cli(verbose, quiet):
    _configure_logging(verbose, quiet)


@cli.command()
@click.option(
    "--username",
    prompt="Thingiverse username or email",
    help="Thingiverse username or email",
)
def login(username):
    """Log in and store tokens for the sync tooling."""
    password = click.prompt("Password", hide_input=True)
    manager = TokenManager()
    try:
        try:
            manager.login(username, password)
        except TwoFactorRequired:
            code = click.prompt("2FA code")
            manager.login_2fa(code)
        user = manager.whoami()
    except ThingiverseAuthError as e:
        raise click.ClickException(str(e)) from e
    click.echo(
        f"Logged in as {user.get('name')} (id {user.get('id')}); "
        f"tokens stored at {manager.token_file}"
    )


@cli.command()
def status():
    """Show login state and verify the stored tokens still work."""
    manager = TokenManager()
    if not manager.is_logged_in():
        click.echo("Not logged in.", err=True)
        sys.exit(1)
    try:
        user = manager.whoami()
    except NotLoggedIn as e:
        click.echo(f"Tokens stored but unusable: {e}", err=True)
        sys.exit(1)
    except ThingiverseAuthError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"Logged in as {user.get('name')} (id {user.get('id')})")


@cli.command()
def logout():
    """Delete the stored tokens."""
    manager = TokenManager()
    manager.logout()
    click.echo("Logged out (tokens removed).")
