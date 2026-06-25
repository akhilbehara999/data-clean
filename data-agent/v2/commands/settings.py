"""Command [S] — Settings: Configure LLM providers, models, API keys, and options."""

from __future__ import annotations
import os
import json
from typing import TYPE_CHECKING

from rich.panel import Panel
from rich.table import Table
from rich import box

from ..utils import safe_input
from ...v3.llm import (
    SUPPORTED_PROVIDERS,
    verify_api_key,
    fetch_available_models,
    get_api_key_for_provider,
    detect_provider,
    MODEL_REGISTRY,
)

if TYPE_CHECKING:
    from ..agent import DataAnalystAgentV2


def save_config(provider: str, api_key: str | None, model: str | None) -> bool:
    """Save setting values to config.json in the CWD."""
    config_path = os.path.join(os.getcwd(), "config.json")
    cfg = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass

    key_map = {
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "nvidia": "NVIDIA_API_KEY",
    }
    
    # Store API key
    if api_key:
        var_name = key_map.get(provider)
        if var_name:
            cfg[var_name] = api_key
            os.environ[var_name] = api_key  # set in env too

    # Store active provider and model
    cfg["ACTIVE_PROVIDER"] = provider
    if model:
        cfg["ACTIVE_MODEL"] = model

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        return True
    except Exception:
        return False


def run_settings(agent: DataAnalystAgentV2) -> dict | None:
    """Run interactive settings console loop."""
    con = agent.console

    # Load active configurations
    active_prov, active_key = detect_provider()
    
    config_path = os.path.join(os.getcwd(), "config.json")
    active_model = None
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                active_prov = cfg.get("ACTIVE_PROVIDER", active_prov)
                active_model = cfg.get("ACTIVE_MODEL", active_model)
        except Exception:
            pass

    if not active_prov:
        active_prov = "gemini"  # Default fallback
    if not active_model:
        active_model = MODEL_REGISTRY.get(active_prov, {}).get("default")

    while True:
        con.print()
        con.print("  ─────────────────────────────────────────────────────────")
        con.print("  ⚙️  SYSTEM SETTINGS MANAGER")
        con.print("  ─────────────────────────────────────────────────────────")
        
        # Display current configurations
        curr_key = get_api_key_for_provider(active_prov)
        key_masked = "••••••••••••" + curr_key[-4:] if curr_key else "[red]Not Configured[/red]"
        
        con.print(f"  [bold]1. Active Provider:[/bold] {active_prov.upper()}")
        con.print(f"  [bold]2. API Key:[/bold]          {key_masked}")
        con.print(f"  [bold]3. Active Model:[/bold]    {active_model or 'Default'}")
        con.print("  [bold]4. Test Connection[/bold]")
        con.print("  [bold]5. Save & Exit[/bold]")
        con.print("  [bold]6. Cancel / Back to Console[/bold]")
        con.print()

        choice = safe_input(con, "[bold bright_cyan]  Select option (1-6): [/bold bright_cyan]").strip()

        if choice == "1":
            con.print("\n  Available Providers:")
            for idx, p in enumerate(SUPPORTED_PROVIDERS, 1):
                con.print(f"    [{idx}] {p.upper()}")
            p_choice = safe_input(con, f"  Choose provider (1-{len(SUPPORTED_PROVIDERS)}): ").strip()
            if p_choice.isdigit():
                p_idx = int(p_choice)
                if 1 <= p_idx <= len(SUPPORTED_PROVIDERS):
                    active_prov = SUPPORTED_PROVIDERS[p_idx - 1]
                    active_model = MODEL_REGISTRY.get(active_prov, {}).get("default")
                    con.print(f"  [green]Provider switched to {active_prov.upper()}[/green]")

        elif choice == "2":
            new_key = safe_input(con, f"  Enter new API Key for {active_prov.upper()}: ").strip()
            if new_key:
                # Test the key instantly
                con.print("  [dim]Testing key connection...[/dim]")
                ok, err = verify_api_key(active_prov, new_key)
                if ok:
                    os.environ[f"{active_prov.upper()}_API_KEY"] = new_key
                    save_config(active_prov, new_key, active_model)
                    con.print("  [bold green]✓ API Key successfully verified and saved![/bold green]")
                else:
                    con.print(f"  [bold red]✗ Verification failed: {err}[/bold red]")
                    confirm = safe_input(con, "  Do you want to save it anyway? (y/n): ").strip().lower()
                    if confirm == "y":
                        os.environ[f"{active_prov.upper()}_API_KEY"] = new_key
                        save_config(active_prov, new_key, active_model)
                        con.print("  [yellow]API Key saved (unverified).[/yellow]")

        elif choice == "3":
            # Fetch models
            api_key = get_api_key_for_provider(active_prov)
            con.print("  [dim]Fetching available models...[/dim]")
            models = fetch_available_models(active_prov, api_key)
            if not models:
                con.print("  [yellow]No models found. Enter custom model name manually.[/yellow]")
                custom = safe_input(con, "  Model name: ").strip()
                if custom:
                    active_model = custom
            else:
                con.print("\n  Available Models:")
                m_keys = list(models.keys())
                for idx, m_id in enumerate(m_keys, 1):
                    con.print(f"    [{idx}] {models[m_id]['name']} ({m_id})")
                con.print(f"    [{len(m_keys)+1}] Custom model key...")
                
                m_choice = safe_input(con, f"  Select model (1-{len(m_keys)+1}): ").strip()
                if m_choice.isdigit():
                    m_idx = int(m_choice)
                    if 1 <= m_idx <= len(m_keys):
                        active_model = m_keys[m_idx - 1]
                        con.print(f"  [green]Selected model: {active_model}[/green]")
                    elif m_idx == len(m_keys) + 1:
                        custom = safe_input(con, "  Enter custom model key: ").strip()
                        if custom:
                            active_model = custom

        elif choice == "4":
            api_key = get_api_key_for_provider(active_prov)
            if not api_key:
                con.print("  [bold red]✗ Connection failed: No API Key configured for provider.[/bold red]")
            else:
                con.print(f"  [dim]Testing connection to {active_prov.upper()}...[/dim]")
                ok, err = verify_api_key(active_prov, api_key)
                if ok:
                    con.print(f"  [bold green]✓ Connection successful! Active model: {active_model}[/bold green]")
                else:
                    con.print(f"  [bold red]✗ Connection failed: {err}[/bold red]")

        elif choice == "5":
            success = save_config(active_prov, get_api_key_for_provider(active_prov), active_model)
            # Apply settings to current agent
            agent.llm_provider = active_prov
            agent.llm_model = active_model
            agent.api_key = get_api_key_for_provider(active_prov)
            if success:
                con.print("  [green]✓ Configuration saved to config.json. Settings applied.[/green]")
            else:
                con.print("  [yellow]⚠ Failed to write configuration to file, but settings applied for this session.[/yellow]")
            break

        elif choice == "6":
            con.print("  [dim]Settings cancelled.[/dim]")
            break
        else:
            con.print("  [dim]Invalid choice. Enter 1-6.[/dim]")

    con.print()
    con.print("[bold bright_cyan]What would you like to do next?[/bold bright_cyan]")
    return None
