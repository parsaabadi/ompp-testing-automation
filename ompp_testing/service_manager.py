"""
OpenM++ service management functionality.
"""

import os
import subprocess
import time
import psutil
import requests
from pathlib import Path
import click


def start_oms(om_root):
    """
    Start the OpenM++ service (oms.exe).
    
    Looks for oms.exe in the OpenM++ bin directory and starts it up.
    Waits a bit to make sure it's actually running before continuing.
    """
    oms_path = Path(om_root) / 'bin' / 'oms.exe'
    
    if not oms_path.exists():
        raise FileNotFoundError(f"Can't find oms.exe at {oms_path}")
    
    click.echo(f"🚀 Starting OpenM++ service from {oms_path}")
    
    try:
        process = subprocess.Popen(
            [str(oms_path)],
            cwd=oms_path.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        
        click.echo(f"  Service started with PID {process.pid}")
        
        click.echo("  Waiting for service to be ready...")
        
        # Try multiple times with increasing delays
        for attempt in range(10):  # Try for up to 30 seconds
            time.sleep(3)
            if _check_oms_running():
                click.echo("  ✅ OpenM++ service is running")
                return True
            else:
                click.echo(f"  ⏳ Service not ready yet (attempt {attempt + 1}/10)...")
        
        click.echo("  ⚠️  Service did not become ready within 30 seconds")
        return False
            
    except Exception as e:
        click.echo(f"  ❌ Failed to start service: {str(e)}")
        return False


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


def _check_oms_running():
    """
    Check if the OpenM++ service is responding.
    
    Tries to connect to the default port (4040) to see if oms.exe is listening.
    """
    try:
        response = requests.get('http://localhost:4040/api/model-list', timeout=5)
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