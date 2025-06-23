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


def start_oms(om_root, model_name=None):
    """
    Start the OpenM++ service using a model-agnostic approach.
    
    Creates a custom startup script based on the general ompp_ui.bat,
    similar to how the R version works. This approach works for any model.
    """
    click.echo(f"Starting OpenM++ service for {om_root}")
    
    # Look for the general ompp_ui.bat in the bin directory
    bin_dir = Path(om_root) / 'bin'
    original_script = bin_dir / 'ompp_ui.bat'
    custom_script = bin_dir / 'ompp_ui_custom.bat'
    
    if not original_script.exists():
        click.echo(f"  Could not find {original_script}, trying direct method...")
        return _start_oms_direct(om_root)
    
    try:
        # Read the original script
        with open(original_script, 'r') as f:
            script_lines = f.readlines()
        
        # Modify the script to set OM_ROOT and remove browser opening
        # Follow the R version approach: insert OM_ROOT setting before the echo line
        modified_lines = []
        om_root_set = False
        
        for line in script_lines:
            # Find the line that echoes OM_ROOT and insert our setting before it
            if 'echo "OM_ROOT:" %OM_ROOT%' in line and not om_root_set:
                # Insert OM_ROOT setting before the echo line
                modified_lines.append(f'set "OM_ROOT={om_root}"\n')
                om_root_set = True
                modified_lines.append(line)
            elif 'echo OM_ROOT: %OM_ROOT%' in line and not om_root_set:
                # Handle case without quotes
                modified_lines.append(f'set "OM_ROOT={om_root}"\n')
                om_root_set = True
                modified_lines.append(line)
            elif 'START http://' not in line and 'start http://' not in line:
                # Remove browser opening commands but keep everything else
                modified_lines.append(line)
        
        # If we didn't find the echo line, fallback to old method
        if not om_root_set:
            click.echo(f"  Could not find OM_ROOT echo line, using fallback...")
            modified_lines = []
            for line in script_lines:
                if 'oms.exe' in line and not om_root_set:
                    modified_lines.append(f'set "OM_ROOT={om_root}"\n')
                    om_root_set = True
                
                if 'START http://' not in line and 'start http://' not in line:
                    modified_lines.append(line)
        
        # Write the custom script
        with open(custom_script, 'w') as f:
            f.writelines(modified_lines)
        
        click.echo(f"  Starting service using custom script...")
        
        # Start the custom script
        process = subprocess.Popen(
            [str(custom_script)],
            cwd=bin_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        
        click.echo(f"  Service started with PID {process.pid}")
        
        # Give it time to start and detect the port
        time.sleep(5)
        
        service_url = _detect_service_url()
        
        if service_url:
            click.echo(f"  OpenM++ service is running at {service_url}")
            return service_url
        else:
            click.echo("  Service started but could not detect port, using default")
            return "http://localhost:4040"
            
    except Exception as e:
        click.echo(f"  Failed to start service: {str(e)}")
        # Clean up custom script if it was created
        if custom_script.exists():
            try:
                custom_script.unlink()
            except:
                pass
        return _start_oms_direct(om_root)


def _start_oms_direct(om_root):
    """
    Fallback method: start oms.exe directly with model-agnostic parameters.
    """
    oms_path = Path(om_root) / 'bin' / 'oms.exe'
    models_dir = Path(om_root) / 'models' / 'bin'
    
    if not oms_path.exists():
        raise FileNotFoundError(f"Can't find oms.exe at {oms_path}")
    
    click.echo(f"  Starting oms.exe directly with models directory: {models_dir}")
    
    try:
        # Start with proper model directory parameter
        process = subprocess.Popen(
            [str(oms_path), '-oms.ModelDir', str(models_dir)],
            cwd=oms_path.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        
        click.echo(f"  Service started with PID {process.pid}")
        time.sleep(5)
        
        service_url = _detect_service_url()
        if service_url:
            click.echo(f"  OpenM++ service is running at {service_url}")
            return service_url
        else:
            return "http://localhost:4040"  # fallback
            
    except Exception as e:
        click.echo(f"  Failed to start service: {str(e)}")
        return None


def _detect_service_url():
    """
    Detect the actual URL the OpenM++ service is running on.
    
    Tries common ports and returns the first one that responds.
    """
    # Try common ports - start with default, then typical ranges
    ports_to_try = [4040, 4041, 4042] + list(range(50000, 60000, 500))
    
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
    Stop any running OpenM++ services and clean up custom scripts.
    """
    click.echo("Stopping OpenM++ services...")
    
    killed_count = 0
    
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == 'oms.exe':
                proc.terminate()
                killed_count += 1
                click.echo(f"  Stopped oms.exe (PID {proc.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    # Clean up any custom scripts we created
    try:
        custom_scripts = Path('.').glob('**/ompp_ui_custom.bat')
        for script in custom_scripts:
            script.unlink()
    except:
        pass
    
    if killed_count > 0:
        click.echo(f"  Stopped {killed_count} OpenM++ service(s)")
    else:
        click.echo("  No OpenM++ services were running")


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