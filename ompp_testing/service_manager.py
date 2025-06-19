"""
OpenM++ service management functionality.
"""

import os
import subprocess
import time
import psutil
import requests
import re
from pathlib import Path
import click


def start_oms(om_root, model_name="RiskPaths"):
    """
    Start the OpenM++ service using the same method as start-ompp-ui.bat.
    
    This starts the service from the model directory with proper parameters
    and detects the dynamic port the service actually uses.
    """
    # Look for the start-ompp-ui.bat file in the model directory
    model_dir = Path(om_root) / 'models' / model_name
    start_script = model_dir / 'start-ompp-ui.bat'
    
    if not start_script.exists():
        click.echo(f"  ⚠️  Could not find {start_script}, trying alternative method...")
        return _start_oms_direct(om_root, model_name)
    
    click.echo(f"🚀 Starting OpenM++ service using {start_script}")
    
    try:
        # Start the batch file and capture output
        process = subprocess.Popen(
            [str(start_script)],
            cwd=model_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        
        click.echo(f"  Service started with PID {process.pid}")
        
        # Give it a moment to start up and print the port info
        time.sleep(3)
        
        # Try to find the actual port by looking for running oms processes
        service_url = _detect_service_url()
        
        if service_url:
            click.echo(f"  ✅ OpenM++ service is running at {service_url}")
            return service_url
        else:
            click.echo("  ⚠️  Service started but could not detect port")
            return "http://localhost:4040"  # fallback
            
    except Exception as e:
        click.echo(f"  ❌ Failed to start service: {str(e)}")
        return None


def _start_oms_direct(om_root, model_name):
    """
    Fallback method: start oms.exe directly from model directory.
    """
    model_bin_dir = Path(om_root) / 'models' / model_name / 'ompp' / 'bin'
    oms_path = Path(om_root) / 'bin' / 'oms.exe'
    
    if not oms_path.exists():
        raise FileNotFoundError(f"Can't find oms.exe at {oms_path}")
    
    click.echo(f"🚀 Starting OpenM++ service directly from {oms_path}")
    
    try:
        # Start from the model bin directory with proper parameters
        process = subprocess.Popen(
            [str(oms_path), '-oms.ModelDir', str(model_bin_dir)],
            cwd=model_bin_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        
        click.echo(f"  Service started with PID {process.pid}")
        time.sleep(3)
        
        service_url = _detect_service_url()
        if service_url:
            click.echo(f"  ✅ OpenM++ service is running at {service_url}")
            return service_url
        else:
            return "http://localhost:4040"  # fallback
            
    except Exception as e:
        click.echo(f"  ❌ Failed to start service: {str(e)}")
        return None


def _detect_service_url():
    """
    Detect the actual URL the OpenM++ service is running on.
    
    Tries common ports and returns the first one that responds.
    """
    # Try common ports
    ports_to_try = [4040, 4041, 4042] + list(range(50000, 60000, 1000))
    
    for port in ports_to_try:
        try:
            url = f"http://localhost:{port}"
            response = requests.get(f"{url}/api/model-list", timeout=2)
            if response.status_code == 200:
                return url
        except:
            continue
    
    return None


def stop_oms():
    """
    Stop any running OpenM++ services.
    
    Finds all oms.exe processes and kills them. Useful for cleanup.
    """
    click.echo("🛑 Stopping OpenM++ services...")
    
    killed_count = 0
    
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == 'oms.exe':
                proc.terminate()
                killed_count += 1
                click.echo(f"  Stopped oms.exe (PID {proc.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if killed_count > 0:
        click.echo(f"  ✅ Stopped {killed_count} OpenM++ service(s)")
    else:
        click.echo("  ℹ️  No OpenM++ services were running")


def _check_oms_running(base_url="http://localhost:4040"):
    """
    Check if the OpenM++ service is responding at the given URL.
    """
    try:
        response = requests.get(f'{base_url}/api/model-list', timeout=5)
        return response.status_code == 200
    except:
        return False


def get_oms_status():
    """
    Get the current status of OpenM++ services.
    
    Returns info about any running oms.exe processes.
    """
    running_services = []
    
    for proc in psutil.process_iter(['pid', 'name', 'create_time']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == 'oms.exe':
                running_services.append({
                    'pid': proc.info['pid'],
                    'start_time': proc.info['create_time']
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    return running_services 