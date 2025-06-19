"""
Output table retrieval functionality for OpenM++ testing.
"""

import sqlite3
import pandas as pd
from pathlib import Path
import click


def get_output_tables(model_name, om_root):
    """
    Get a list of output tables available for a model.
    
    Connects to the OpenM++ database and pulls out all the output tables
    that are available for your model. This tells you what data you can
    compare between different OpenM++ versions.
    """
    click.echo(f"📊 Getting output tables for {model_name}")
    
    db_path = Path(om_root) / 'models' / f'{model_name}.db'
    
    if not db_path.exists():
        raise FileNotFoundError(f"Can't find the model database: {db_path}")
    
    try:
        conn = sqlite3.connect(str(db_path))
        
        query = """
        SELECT 
            t.table_name as name,
            t.table_hid as hid,
            t.table_digest as digest
        FROM table_dic t
        ORDER BY t.table_name
        """
        
        tables = pd.read_sql_query(query, conn)
        conn.close()
        
        click.echo(f"  Found {len(tables)} output tables")
        
        return tables
        
    except Exception as e:
        click.echo(f"  ❌ Failed to get tables: {str(e)}")
        raise


def get_table_data(model_name, om_root, table_name, run_id=None):
    """
    Get the actual data from a specific output table.
    
    If you don't specify a run_id, it'll get the latest run.
    Returns the table data as a pandas DataFrame.
    """
    db_path = Path(om_root) / 'models' / f'{model_name}.db'
    
    if not db_path.exists():
        raise FileNotFoundError(f"Can't find the model database: {db_path}")
    
    try:
        conn = sqlite3.connect(str(db_path))
        
        if run_id is None:
            run_query = "SELECT MAX(run_id) as latest_run FROM run_lst"
            latest_run = pd.read_sql_query(run_query, conn)
            run_id = latest_run.iloc[0]['latest_run']
        
        query = f"""
        SELECT * FROM {table_name}
        WHERE run_id = {run_id}
        """
        
        data = pd.read_sql_query(query, conn)
        conn.close()
        
        return data
        
    except Exception as e:
        click.echo(f"  ❌ Failed to get table data: {str(e)}")
        raise


def get_model_runs(model_name, om_root):
    """
    Get a list of all model runs in the database.
    
    Shows you what runs are available and when they were created.
    """
    db_path = Path(om_root) / 'models' / f'{model_name}.db'
    
    if not db_path.exists():
        raise FileNotFoundError(f"Can't find the model database: {db_path}")
    
    try:
        conn = sqlite3.connect(str(db_path))
        
        query = """
        SELECT 
            run_id,
            run_name,
            run_digest,
            create_dt,
            update_dt,
            run_status
        FROM run_lst
        ORDER BY create_dt DESC
        """
        
        runs = pd.read_sql_query(query, conn)
        conn.close()
        
        return runs
        
    except Exception as e:
        click.echo(f"  ❌ Failed to get model runs: {str(e)}")
        raise 