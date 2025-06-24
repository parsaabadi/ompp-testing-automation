"""
Model execution and comparison functionality for OpenM++ testing.
"""

import os
import shutil
import time
import pickle
import json
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
            click.echo(f"Could not get model runs: {e}")
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
                timeout=None  # No timeout - allow for long model runs
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            click.echo(f"Model run failed: {e}")
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
            click.echo(f"Could not get run tables: {e}")
            return {}


def run_models(om_root, model_name, cases=1000000, threads=8, sub_samples=8, 
               tables=None, tables_per_run=25, max_run_time=86400):
    """
    Run models on different OpenM++ versions and compare the results.
    
    This is the main function that does the heavy lifting. It starts up the
    OpenM++ services, runs your model with the parameters you specify, and
    then compares the output tables between different versions.
    
    The function is designed to handle long-running models that may take hours
    or even days to complete. By default, it will wait up to 24 hours for each
    model run to finish, but this can be customized via the max_run_time parameter.
    
    Args:
        max_run_time: Maximum time to wait for each model run in seconds (default: 86400 = 24 hours)
                     Set to None for unlimited waiting time (not recommended)
    """
    click.echo(f"Starting model runs for {model_name}")
    click.echo(f"  Cases: {cases:,}, Threads: {threads}, Sub-samples: {sub_samples}")
    click.echo(f"  Maximum run time per version: {max_run_time//3600:.1f} hours")
    
    if not tables:
        click.echo("  No tables specified, will get all output tables")
        from .get_output_tables import get_output_tables
        output_tables = get_output_tables(model_name, om_root[0])
        tables = output_tables['name'].tolist()
    
    click.echo(f"  Will compare {len(tables)} tables across {len(om_root)} OpenM++ versions")
    
    all_results = []
    
    try:
        for i, root in enumerate(om_root):
            click.echo(f"\nRunning on OpenM++ version {Path(root).name}")
            
            stop_oms()
            time.sleep(2)
            
            service_url = start_oms(root, model_name)
            if not service_url:
                click.echo(f"  Failed to start service for {root}")
                continue
            
            time.sleep(3)
            
            version_results = _run_single_version(
                root, model_name, cases, threads, sub_samples, 
                tables, tables_per_run, i, service_url, max_run_time
            )
            
            all_results.append(version_results)
        
        click.echo("\nComparing results between versions...")
        
        from .compare_model_runs import compare_model_runs
        comparison = compare_model_runs(all_results)
        
        return comparison
        
    except Exception as e:
        click.echo(f"Model run failed: {str(e)}")
        raise
    
    finally:
        stop_oms()


def _debug_model_files(om_root, model_name):
    """Debug function to check what model files exist and their properties."""
    models_bin = Path(om_root) / 'models' / 'bin'
    model_specific_bin = Path(om_root) / 'models' / model_name / 'ompp' / 'bin'
    
    click.echo(f"    Checking models directory: {models_bin}")
    if models_bin.exists():
        files = list(models_bin.iterdir())
        click.echo(f"    Found {len(files)} files in models/bin:")
        for f in files:
            if f.suffix in ['.exe', '.sqlite']:
                click.echo(f"      {f.name} ({f.stat().st_size} bytes)")
    else:
        click.echo(f"    Models directory does not exist: {models_bin}")
    
    click.echo(f"    Checking model-specific directory: {model_specific_bin}")
    if model_specific_bin.exists():
        files = list(model_specific_bin.iterdir())
        click.echo(f"    Found {len(files)} files in model-specific bin:")
        for f in files:
            if f.suffix in ['.exe', '.sqlite']:
                click.echo(f"      {f.name} ({f.stat().st_size} bytes)")
    else:
        click.echo(f"    Model-specific directory does not exist: {model_specific_bin}")


def _fix_model_detection(om_root, model_name):
    """Try to fix model detection by ensuring database files are in the right place."""
    models_bin = Path(om_root) / 'models' / 'bin'
    model_specific_bin = Path(om_root) / 'models' / model_name / 'ompp' / 'bin'
    
    sqlite_file = f"{model_name}.sqlite"
    exe_file = f"{model_name}.exe"
    
    target_sqlite = models_bin / sqlite_file
    target_exe = models_bin / exe_file
    
    source_locations = [
        model_specific_bin / sqlite_file,
        model_specific_bin / exe_file,
        Path(om_root) / 'bin' / sqlite_file,
        Path(om_root) / 'bin' / exe_file
    ]
    
    click.echo(f"    Ensuring model files are in service directory...")
    
    files_copied = False
    
    for source_file in source_locations:
        if source_file.exists():
            if source_file.suffix == '.sqlite':
                if not target_sqlite.exists() or target_sqlite.stat().st_size == 0:
                    try:
                        shutil.copy2(source_file, target_sqlite)
                        click.echo(f"      Copied {source_file} -> {target_sqlite}")
                        files_copied = True
                    except Exception as e:
                        click.echo(f"      Failed to copy {source_file}: {e}")
            
            elif source_file.suffix == '.exe':
                if not target_exe.exists():
                    try:
                        shutil.copy2(source_file, target_exe)
                        click.echo(f"      Copied {source_file} -> {target_exe}")
                        files_copied = True
                    except Exception as e:
                        click.echo(f"      Failed to copy {source_file}: {e}")
    
    if files_copied:
        click.echo(f"    Files copied, waiting for service to refresh...")
        time.sleep(3)
        return model_name
    
    exe_files = list(models_bin.glob("*.exe"))
    if exe_files:
        target_exe = f"{model_name}.exe"
        if any(f.name.lower() == target_exe.lower() for f in exe_files):
            click.echo(f"    Found target executable: {target_exe}, using model name: {model_name}")
            return model_name
        else:
            detected_name = exe_files[0].stem
            click.echo(f"    Target model not found, using first executable: {exe_files[0].name}")
            click.echo(f"    Available executables: {[f.name for f in exe_files]}")
            click.echo(f"    Using model name: {detected_name}")
            return detected_name
    
    return None


def _run_single_version(om_root, model_name, cases, threads, sub_samples, 
                       tables, tables_per_run, version_index, service_url, max_run_time):
    click.echo(f"  Starting model run...")
    
    try:
        model_names = []  # Initialize to avoid reference errors
        
        click.echo(f"  Debugging model detection...")
        _debug_model_files(om_root, model_name)
        
        click.echo(f"  Checking available models...")
        response = requests.get(f"{service_url}/api/model-list", timeout=10)
        
        if response.status_code == 200:
            models = response.json()
            if models:
                model_names = [m.get('Name', 'Unknown') for m in models]
                click.echo(f"  Service sees {len(model_names)} models: {model_names}")
                
                if all(name == 'Unknown' for name in model_names):
                    click.echo(f"  All models show as 'Unknown' - trying to fix model detection...")
                    fixed_name = _fix_model_detection(om_root, model_name)
                    if fixed_name:
                        actual_model_name = fixed_name
                        click.echo(f"  Using fixed model name: '{actual_model_name}'")
                    else:
                        click.echo(f"  Could not fix model detection, using original name: '{model_name}'")
                        actual_model_name = model_name
                else:
                    model_found = any(name.lower() == model_name.lower() for name in model_names)
                    if not model_found:
                        click.echo(f"  Model '{model_name}' not found in service")
                        click.echo(f"  Available models: {model_names}")
                        return None
                    
                    actual_model_name = next((name for name in model_names if name.lower() == model_name.lower()), model_name)
                    click.echo(f"  Using model name: '{actual_model_name}'")
            else:
                click.echo(f"  Service returned empty model list")
                actual_model_name = model_name
        else:
            click.echo(f"  Could not get model list (status: {response.status_code})")
            click.echo(f"  Response: {response.text}")
            actual_model_name = model_name
        
        click.echo(f"  Starting model run...")
        
        run_request = {
            "ModelName": actual_model_name,
            "RunName": f"TestRun_{int(time.time())}",
            "Opts": {
                "Parameter.SimulationCases": str(cases),
                "OpenM.Threads": str(threads),
                "OpenM.SubValues": str(sub_samples)
            },
            "Tables": tables[:10] if tables else []
        }
        
        if all(name == 'Unknown' for name in model_names) and len(model_names) == 1:
            click.echo(f"  Trying with direct model name since service shows 'Unknown'...")
            run_request["ModelName"] = model_name
        
        click.echo(f"  Sending run request to: {service_url}/api/run")
        click.echo(f"  Request payload: {json.dumps(run_request, indent=2)}")
        
        response = requests.post(
            f"{service_url}/api/run", 
            json=run_request, 
            timeout=None  # No timeout - allow for long model runs
        )
        
        click.echo(f"  Response status: {response.status_code}")
        click.echo(f"  Response headers: {dict(response.headers)}")
        click.echo(f"  Response text: {response.text}")
        
        if response.status_code != 200:
            click.echo(f"  Failed to start model run")
            click.echo(f"  Status: {response.status_code}")
            click.echo(f"  Response: {response.text}")
            
            alternative_endpoints = [
                f"{service_url}/api/model/{actual_model_name}/run",
                f"{service_url}/api/models/{actual_model_name}/run",
                f"{service_url}/api/run-model"
            ]
            
            for alt_endpoint in alternative_endpoints:
                click.echo(f"  Trying alternative endpoint: {alt_endpoint}")
                try:
                    alt_response = requests.post(alt_endpoint, json=run_request, timeout=10)
                    click.echo(f"    Status: {alt_response.status_code}, Response: {alt_response.text[:200]}")
                    if alt_response.status_code == 200:
                        response = alt_response
                        break
                except Exception as e:
                    click.echo(f"    Failed: {str(e)}")
            
            if response.status_code != 200:
                return None
        
        try:
            run_data = response.json()
        except:
            click.echo(f"  Could not parse JSON response")
            return None
        
        run_digest = (run_data.get('RunStamp') or run_data.get('RunDigest') or 
                     run_data.get('run_digest') or run_data.get('id') or 
                     run_data.get('run_stamp'))
        
        if not run_digest:
            click.echo(f"  No run digest/ID returned")
            click.echo(f"  Full response: {run_data}")
            click.echo(f"  Available keys: {list(run_data.keys())}")
            return None
        
        click.echo(f"  Model run started with ID: {run_digest}")
        
        model_digest = run_data.get('ModelDigest', '')
        if model_digest:
            click.echo(f"  Model digest: {model_digest}")
        
        click.echo(f"  Waiting for run completion...")
        
        # For small test runs, use shorter timeout
        if cases < 10000:
            actual_timeout = min(max_run_time, 300)  # Max 5 minutes for small tests
            click.echo(f"  Small test detected - using {actual_timeout//60} minute timeout")
        else:
            actual_timeout = max_run_time
            
        completed = _wait_for_run_completion(service_url, actual_model_name, run_digest, actual_timeout, cases)
        
        if not completed:
            click.echo(f"  Run status check timed out, but run may have completed")
            click.echo(f"  Will attempt to retrieve results anyway...")
        
        click.echo(f"  Retrieving table data...")
        
        # Try to get the actual database run_id by checking status
        actual_run_id = run_digest  # fallback to original
        try:
            response = requests.get(f"{service_url}/api/model/{actual_model_name}/run/{run_digest}/status", timeout=10)
            if response.status_code == 200:
                status_data = response.json()
                if status_data.get('RunId'):
                    actual_run_id = status_data['RunId']
                    click.echo(f"  Using database run_id: {actual_run_id}")
                else:
                    click.echo(f"  Using original run_id: {actual_run_id}")
        except Exception as e:
            click.echo(f"  Could not get run_id, using original: {actual_run_id}")
        
        table_data = _get_all_table_data(om_root, actual_model_name, actual_run_id, tables, tables_per_run)
        
        tables_retrieved = len([v for v in table_data.values() if v is not None])
        click.echo(f"  Successfully retrieved {tables_retrieved}/{len(tables)} tables")
        
        return {
            'version': Path(om_root).name,
            'version_index': version_index,
            'run_digest': run_digest,
            'actual_run_id': actual_run_id,
            'run_request': run_request,
            'actual_model_name': actual_model_name,
            'completed': completed,
            'table_data': table_data
        }
        
    except Exception as e:
        click.echo(f"Model run failed: {str(e)}")
        raise


def _wait_for_run_completion(service_url, model_name, run_id, max_wait, cases):
    """Wait for a model run to finish using OpenM++ API.
    
    Args:
        max_wait: Maximum time to wait in seconds (default: 86400 = 24 hours)
    """
    
    start_time = time.time()
    check_interval = 30  # Start with 30 seconds between checks
    
    endpoints_to_try = [
        f"{service_url}/api/model/{model_name}/run/{run_id}/status",
        f"{service_url}/api/run/{run_id}/status", 
        f"{service_url}/api/model/{model_name}/run/{run_id}",
        f"{service_url}/api/run-list"
    ]
    
    click.echo(f"    Checking run status every {check_interval}s (max {max_wait//3600:.1f} hours)...")
    
    while time.time() - start_time < max_wait:
        try:
            for endpoint in endpoints_to_try:
                try:
                    response = requests.get(endpoint, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Debug: Print status response for small runs
                        if cases < 10000:
                            click.echo(f"    Status response: {data}")
                        
                        if isinstance(data, dict):
                            # Check for completed run using OpenM++ specific fields
                            if data.get('IsFinal') == True:
                                click.echo("    Run completed")
                                return True
                            elif data.get('Status') == 's' and data.get('SubCompleted') == data.get('SubCount'):
                                click.echo("    Run completed (all sub-samples finished)")
                                return True
                            elif 'status' in data:
                                status = data.get('status', '').lower()
                                if status in ['completed', 'success', 'done', 's']:
                                    click.echo("    Run completed")
                                    return True
                                elif status in ['failed', 'error', 'f']:
                                    click.echo("    Run failed")
                                    return False
                        
                        elif isinstance(data, list):
                            for run_info in data:
                                if (run_info.get('RunStamp') == run_id or 
                                    run_info.get('RunDigest') == run_id):
                                    if run_info.get('IsFinal') == True:
                                        click.echo("    Run completed")
                                        return True
                        
                        break
                    
                except requests.exceptions.RequestException:
                    continue
            
            # Progressive check interval - start at 30s, increase to 5 minutes for long runs
            elapsed = time.time() - start_time
            if elapsed > 3600:  # After 1 hour, check every 5 minutes
                check_interval = 300
            elif elapsed > 600:  # After 10 minutes, check every 2 minutes
                check_interval = 120
            else:  # First 10 minutes, check every 30 seconds
                check_interval = 30
                
            time.sleep(check_interval)
            
        except Exception as e:
            click.echo(f"    Error checking status: {str(e)}")
            time.sleep(check_interval)
    
    elapsed = time.time() - start_time
    click.echo(f"    Run status check timed out after {elapsed//3600:.0f}h {(elapsed%3600)//60:.0f}m")
    click.echo(f"    Maximum wait time ({max_wait//3600:.1f} hours) reached")
    click.echo(f"    Run may still be processing in background - check manually if needed")
    return True


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
                click.echo(f"    Failed to get {table_name}: {str(e)}")
                table_data[table_name] = None
    
    return table_data 