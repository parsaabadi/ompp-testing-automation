"""
Model execution and comparison functionality for OpenM++ testing.
"""

import os
import shutil
import time
import pickle
from datetime import datetime
from pathlib import Path
import pandas as pd
import requests
import click
from tqdm import tqdm

from .service_manager import start_oms, stop_oms
from .compare_model_runs import compare_model_runs
from .get_output_tables import get_table_data


class OpenMppAPI:
    """Simple OpenM++ API client for model operations."""
    
    def __init__(self, base_url="http://localhost:4040"):
        self.base_url = base_url
        
    def get_model_runs(self, model_name):
        """Get list of model runs."""
        try:
            response = requests.get(f"{self.base_url}/api/model/{model_name}/run")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            click.echo(f"⚠️  Warning: Could not get model runs: {e}")
            return []
    
    def run_model(self, model_name, run_name, options):
        """Execute a model run."""
        try:
            payload = {
                "ModelName": model_name,
                "Name": run_name,
                "Opts": options.get("Opts", {}),
                "Tables": options.get("Tables", [])
            }
            
            response = requests.post(
                f"{self.base_url}/api/run",
                json=payload,
                timeout=3600  # 1 hour timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            click.echo(f"❌ Model run failed: {e}")
            raise
    
    def get_run_tables(self, model_name, run_digest):
        """Get tables for a specific run."""
        try:
            response = requests.get(
                f"{self.base_url}/api/model/{model_name}/run/{run_digest}/table"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            click.echo(f"⚠️  Warning: Could not get run tables: {e}")
            return {}


def run_models(om_root, model_name, cases=1000000, threads=8, sub_samples=8, 
               tables=None, tables_per_run=25):
    """
    Run models on different OpenM++ versions and compare the results.
    
    This is the main function that does the heavy lifting. It starts up the
    OpenM++ services, runs your model with the parameters you specify, and
    then compares the output tables between different versions.
    """
    click.echo(f"🚀 Starting model runs for {model_name}")
    click.echo(f"  Cases: {cases:,}, Threads: {threads}, Sub-samples: {sub_samples}")
    
    if not tables:
        click.echo("  No tables specified, will get all output tables")
        from .get_output_tables import get_output_tables
        output_tables = get_output_tables(model_name, om_root[0])
        tables = output_tables['name'].tolist()
    
    click.echo(f"  Will compare {len(tables)} tables across {len(om_root)} OpenM++ versions")
    
    all_results = []
    
    try:
        for i, root in enumerate(om_root):
            click.echo(f"\n📊 Running on OpenM++ version {Path(root).name}")
            
            stop_oms()
            time.sleep(2)
            
            service_url = start_oms(root, model_name)
            if not service_url:
                click.echo(f"  ❌ Failed to start service for {root}")
                continue
            
            time.sleep(3)
            
            version_results = _run_single_version(
                root, model_name, cases, threads, sub_samples, 
                tables, tables_per_run, i, service_url
            )
            
            all_results.append(version_results)
        
        click.echo("\n📈 Comparing results between versions...")
        
        from .compare_model_runs import compare_model_runs
        comparison = compare_model_runs(all_results)
        
        return comparison
        
    except Exception as e:
        click.echo(f"❌ Model run failed: {str(e)}")
        raise
    
    finally:
        stop_oms()


def _run_single_version(om_root, model_name, cases, threads, sub_samples, 
                       tables, tables_per_run, version_index, service_url):
    """Run the model on one specific OpenM++ version."""
    
    click.echo(f"  Starting model run...")
    
    base_url = f"{service_url}/api"
    
    try:
        run_params = {
            "model": model_name,
            "run_name": f"TestRun_{int(time.time())}",
            "cases": cases,
            "threads": threads,
            "sub_samples": sub_samples
        }
        
        response = requests.post(f"{base_url}/run", json=run_params, timeout=300)
        
        if response.status_code != 200:
            click.echo(f"  ❌ Failed to start model run: {response.text}")
            return None
        
        run_data = response.json()
        run_id = run_data.get('run_id')
        
        if not run_id:
            click.echo(f"  ❌ No run ID returned")
            return None
        
        click.echo(f"  Model run started with ID: {run_id}")
        
        click.echo(f"  Waiting for run to complete...")
        _wait_for_run_completion(base_url, run_id)
        
        click.echo(f"  Getting table data...")
        table_data = _get_all_table_data(om_root, model_name, run_id, tables, tables_per_run)
        
        return {
            'version': Path(om_root).name,
            'version_index': version_index,
            'run_id': run_id,
            'run_params': run_params,
            'table_data': table_data
        }
        
    except Exception as e:
        click.echo(f"  ❌ Error running model: {str(e)}")
        return None


def _wait_for_run_completion(base_url, run_id, max_wait=3600):
    """Wait for a model run to finish."""
    
    start_time = time.time()
    
    with tqdm(total=100, desc="  Run progress", leave=False) as pbar:
        while time.time() - start_time < max_wait:
            try:
                response = requests.get(f"{base_url}/run/{run_id}/status", timeout=30)
                
                if response.status_code == 200:
                    status_data = response.json()
                    status = status_data.get('status', 'unknown')
                    
                    if status == 'completed':
                        pbar.update(100 - pbar.n)
                        click.echo("  ✅ Run completed")
                        return True
                    elif status == 'failed':
                        click.echo("  ❌ Run failed")
                        return False
                    else:
                        progress = status_data.get('progress', 0)
                        pbar.n = int(progress)
                        pbar.refresh()
                
                time.sleep(5)
                
            except Exception as e:
                click.echo(f"  ⚠️  Error checking status: {str(e)}")
                time.sleep(10)
    
    click.echo("  ⚠️  Run timed out")
    return False


def _get_all_table_data(om_root, model_name, run_id, tables, tables_per_run):
    """Get data from all output tables for a model run."""
    
    table_data = {}
    
    for i in range(0, len(tables), tables_per_run):
        batch = tables[i:i + tables_per_run]
        
        click.echo(f"    Getting batch {i//tables_per_run + 1}/{(len(tables) + tables_per_run - 1)//tables_per_run}")
        
        for table_name in batch:
            try:
                data = get_table_data(model_name, om_root, table_name, run_id)
                table_data[table_name] = data
            except Exception as e:
                click.echo(f"    ⚠️  Failed to get {table_name}: {str(e)}")
                table_data[table_name] = None
    
    return table_data 