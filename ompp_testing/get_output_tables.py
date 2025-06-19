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
    click.echo(f"Getting output tables for {model_name}")
    
    db_path = Path(om_root) / 'models' / f'{model_name}.db'
    
    if not db_path.exists():
        raise FileNotFoundError(f"Can't find the model database: {db_path}")
    
    try:
        conn = sqlite3.connect(str(db_path))
        
        # First get the basic table info from table_dic
        table_dic_query = """
        SELECT 
            table_hid,
            table_name as name,
            table_digest as digest
        FROM table_dic
        ORDER BY table_name
        """
        
        tables_df = pd.read_sql_query(table_dic_query, conn)
        
        # Try to get descriptions from table_dic_txt (like the R version does)
        try:
            desc_query = """
            SELECT 
                table_hid,
                descr as description
            FROM table_dic_txt
            WHERE lang_id = 0
            """
            
            desc_df = pd.read_sql_query(desc_query, conn)
            
            # Join tables with descriptions
            tables = pd.merge(tables_df, desc_df, on='table_hid', how='left')
            
        except Exception as desc_e:
            # If table_dic_txt doesn't exist or query fails, just use basic info
            click.echo(f"  Note: Could not get table descriptions: {str(desc_e)}")
            tables = tables_df
            tables['description'] = 'No description available'
        
        # Clean up - remove table_hid since we don't need it in the final result
        if 'table_hid' in tables.columns:
            tables = tables.drop('table_hid', axis=1)
        
        conn.close()
        
        click.echo(f"  Found {len(tables)} output tables")
        
        return tables
        
    except Exception as e:
        click.echo(f"  ERROR: Failed to get tables: {str(e)}")
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
        click.echo(f"  ERROR: Failed to get table data: {str(e)}")
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
        click.echo(f"  ERROR: Failed to get model runs: {str(e)}")
        raise 