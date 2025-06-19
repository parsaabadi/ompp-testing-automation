#!/usr/bin/env python3
"""
OpenM++ Testing Automation

Command-line tools for testing OpenM++ models across different versions.
"""

import os
import sys
import json
from pathlib import Path
import click
import pandas as pd

# Add the ompp_testing package to the path
sys.path.insert(0, str(Path(__file__).parent))

from ompp_testing import (
    clone_repo, build_model, start_oms, stop_oms, 
    run_models, get_output_tables, generate_html_report
)


@click.group()
@click.version_option(version='1.0.0')
def cli():
    """
    OpenM++ Testing Automation
    
    Tools for testing OpenM++ models across different versions.
    """
    pass


@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), 
              help='Path to configuration JSON file')
@click.option('--git-url', help='Git repository URL')
@click.option('--git-username', help='Git username for authentication')
@click.option('--git-password', help='Git password/token for authentication')
@click.option('--git-commit', help='Specific commit to checkout')
@click.option('--model-sln', help='Model solution file name')
@click.option('--om-root', multiple=True, help='OpenM++ root directories')
@click.option('--vs-cmd-path', help='Path to Visual Studio command prompt')
@click.option('--cases', default=1000000, type=int, help='Number of simulation cases')
@click.option('--threads', default=8, type=int, help='Number of threads')
@click.option('--sub-samples', default=8, type=int, help='Number of sub-samples')
@click.option('--tables-per-run', default=25, type=int, help='Tables per run batch')
@click.option('--output-dir', help='Output directory for reports')
def run_test(config, git_url, git_username, git_password, git_commit, model_sln, 
             om_root, vs_cmd_path, cases, threads, sub_samples, tables_per_run, output_dir):
    """
    Run the complete testing workflow.
    
    This does everything: clones the repo, builds models, runs them on different 
    OpenM++ versions, compares results, and makes an HTML report.
    """
    
    # Load configuration from file if provided
    settings = {}
    if config:
        with open(config, 'r') as f:
            settings = json.load(f)
    
    # Override with command line arguments
    if git_url:
        settings['git_url'] = git_url
    if git_username:
        settings['git_username'] = git_username
    if git_password:
        settings['git_password'] = git_password
    if git_commit:
        settings['git_commit'] = git_commit
    if model_sln:
        settings['model_sln'] = model_sln
    if om_root:
        settings['om_root'] = list(om_root)
    if vs_cmd_path:
        settings['vs_cmd_path'] = vs_cmd_path
    
    # Validate required settings
    required_settings = ['git_url', 'model_sln', 'om_root', 'vs_cmd_path']
    missing_settings = [s for s in required_settings if s not in settings]
    if missing_settings:
        click.echo(f"❌ Missing required settings: {', '.join(missing_settings)}")
        click.echo("Please provide them via command line options or configuration file.")
        sys.exit(1)
    
    try:
        click.echo("🚀 Starting OpenM++ testing workflow...")
        
        # Step 1: Clone repository
        click.echo("📥 Step 1: Cloning repository...")
        model_sln_path = clone_repo(
            git_url=settings['git_url'],
            git_username=settings.get('git_username'),
            git_password=settings.get('git_password'),
            git_commit=settings.get('git_commit'),
            model_sln=settings['model_sln']
        )
        
        # Step 2: Build models
        click.echo("🔨 Step 2: Building models...")
        model_names = build_model(
            model_sln=model_sln_path,
            om_root=settings['om_root'],
            vs_cmd_path=settings['vs_cmd_path'],
            mode="release",
            bit=64
        )
        
        if not model_names:
            raise RuntimeError("No models were built successfully")
        
        model_name = model_names[0]  # Use first model name
        click.echo(f"✅ Built model: {model_name}")
        
        # Step 3: Get output tables
        click.echo("📊 Step 3: Getting output table list...")
        output_tables = get_output_tables(
            model_name=model_name,
            om_root=settings['om_root'][0]
        )
        
        # Step 4: Run models and compare
        click.echo("⏳ Step 4: Running models and comparing results...")
        summary = run_models(
            om_root=settings['om_root'],
            model_name=model_name,
            cases=cases,
            threads=threads,
            sub_samples=sub_samples,
            tables=output_tables['name'].tolist(),
            tables_per_run=tables_per_run
        )
        
        # Step 5: Generate report
        click.echo("📄 Step 5: Generating HTML report...")
        
        # Prepare output directory
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"ompp_testing_report_{model_name}.html"
        else:
            output_file = None
        
        # Generate versions string
        om_versions = " vs ".join([f"v{Path(root).name}" for root in settings['om_root']])
        
        report_path = generate_html_report(
            summary=summary,
            output_tables=output_tables,
            title=f"Testing OpenM++ with {model_name}",
            model_name=model_name,
            git_commit=settings.get('git_commit'),
            om_versions=om_versions,
            environment_note="All testing done in Windows environment",
            output_file=str(output_file) if output_file else None
        )
        
        click.echo("🎉 Testing workflow completed successfully!")
        click.echo(f"📄 Report available at: {report_path}")
        
        # Display summary statistics
        if summary and 'summary_table' in summary and not summary['summary_table'].empty:
            total_tables = len(summary['summary_table'])
            tables_with_diffs = len(summary['summary_table'][
                summary['summary_table']['has_differences'] == True
            ])
            
            click.echo(f"📊 Summary: {total_tables} tables analyzed, {tables_with_diffs} with differences")
        
    except Exception as e:
        click.echo(f"❌ Testing workflow failed: {str(e)}")
        sys.exit(1)
    
    finally:
        # Clean up - stop any running services
        try:
            stop_oms()
        except:
            pass


@cli.command()
@click.option('--git-url', required=True, help='Git repository URL')
@click.option('--git-username', help='Git username for authentication')
@click.option('--git-password', help='Git password/token for authentication')
@click.option('--git-commit', help='Specific commit to checkout')
@click.option('--model-sln', required=True, help='Model solution file name')
def clone(git_url, git_username, git_password, git_commit, model_sln):
    """Clone a repository and find the model solution file."""
    try:
        model_sln_path = clone_repo(
            git_url=git_url,
            git_username=git_username,
            git_password=git_password,
            git_commit=git_commit,
            model_sln=model_sln
        )
        click.echo(f"✅ Model solution file found at: {model_sln_path}")
    except Exception as e:
        click.echo(f"❌ Clone failed: {str(e)}")
        sys.exit(1)


@cli.command()
@click.option('--model-sln', required=True, help='Path to model solution file')
@click.option('--om-root', multiple=True, required=True, help='OpenM++ root directories')
@click.option('--vs-cmd-path', required=True, help='Path to Visual Studio command prompt')
def build(model_sln, om_root, vs_cmd_path):
    """Build OpenM++ models."""
    try:
        model_names = build_model(
            model_sln=model_sln,
            om_root=list(om_root),
            vs_cmd_path=vs_cmd_path,
            mode="release",
            bit=64
        )
        click.echo(f"✅ Built models: {', '.join(model_names)}")
    except Exception as e:
        click.echo(f"❌ Build failed: {str(e)}")
        sys.exit(1)


@cli.command()
@click.option('--model-name', required=True, help='Name of the model')
@click.option('--om-root', required=True, help='OpenM++ root directory')
def tables(model_name, om_root):
    """List available output tables for a model."""
    try:
        output_tables = get_output_tables(model_name=model_name, om_root=om_root)
        
        click.echo(f"📊 Found {len(output_tables)} output tables:")
        for idx, row in output_tables.iterrows():
            desc = row.get('description', 'No description')
            if pd.isna(desc) or desc == 'No description available':
                click.echo(f"  {idx + 1:2d}. {row['name']}")
            else:
                click.echo(f"  {idx + 1:2d}. {row['name']:<30} {desc}")
        
    except Exception as e:
        click.echo(f"❌ Failed to get tables: {str(e)}")
        sys.exit(1)


@cli.command()
@click.argument('config_file', type=click.Path())
def create_config(config_file):
    """Create a sample configuration file."""
    
    sample_config = {
        "git_url": "https://github.com/openmpp/main.git",
        "git_username": None,
        "git_password": None,
        "git_commit": "9f4cf26ff8b7c4caf2b26621f02b4310a7380c2e",
        "model_sln": "riskpaths-ompp.sln",
        "om_root": [
            "c:/users/username/desktop/ompp/1.17.5",
            "c:/users/username/desktop/ompp/1.17.9"
        ],
        "vs_cmd_path": "c:/program files/microsoft visual studio/2022/enterprise/common7/tools/vsdevcmd.bat"
    }
    
    with open(config_file, 'w') as f:
        json.dump(sample_config, f, indent=2)
    
    click.echo(f"📄 Created sample configuration file: {config_file}")
    click.echo("Please edit the file with your specific settings before using.")


if __name__ == '__main__':
    cli() 