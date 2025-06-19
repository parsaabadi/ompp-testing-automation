#!/usr/bin/env python3
"""
Example script for testing RiskPaths model with different OpenM++ versions.
"""

import sys
from pathlib import Path

# Add the parent directory to the path so we can import ompp_testing
sys.path.insert(0, str(Path(__file__).parent.parent))

from ompp_testing import (
    clone_repo, build_model, run_models, 
    get_output_tables, generate_html_report,
    generate_summary_stats
)


def test_riskpaths():
    """Test RiskPaths model across different OpenM++ versions."""
    
    print("Starting RiskPaths model testing")
    
    # Configuration
    config = {
        'git_url': 'https://github.com/openmpp/main.git',
        'git_commit': '9f4cf26ff8b7c4caf2b26621f02b4310a7380c2e',
        'model_sln': 'riskpaths-ompp.sln',
        'om_root': [
            'c:/users/username/desktop/ompp/1.17.5',
            'c:/users/username/desktop/ompp/1.17.9'
        ],
        'vs_cmd_path': 'c:/program files/microsoft visual studio/2022/enterprise/common7/tools/vsdevcmd.bat'
    }
    
    try:
        # Step 1: Clone repository
        print("\nStep 1: Cloning repository...")
        model_sln_path = clone_repo(
            git_url=config['git_url'],
            git_commit=config['git_commit'],
            model_sln=config['model_sln']
        )
        
        # Step 2: Build model
        print("\nStep 2: Building model...")
        model_names = build_model(
            model_sln=model_sln_path,
            om_root=config['om_root'],
            vs_cmd_path=config['vs_cmd_path'],
            mode="release",
            bit=64
        )
        
        if not model_names:
            raise RuntimeError("No models were built successfully")
        
        model_name = model_names[0]
        print(f"SUCCESS: Built model: {model_name}")
        
        # Step 3: Get output tables
        print("\nStep 3: Getting output tables...")
        output_tables = get_output_tables(
            model_name=model_name,
            om_root=config['om_root'][0]
        )
        
        print(f"Found {len(output_tables)} output tables")
        
        # Step 4: Run models and compare
        print("\nStep 4: Running models and comparing results...")
        results = run_models(
            om_root=config['om_root'],
            model_name=model_name,
            cases=100000,  # Smaller test run
            threads=4,
            sub_samples=4,
            tables=None,
            tables_per_run=10
        )
        
        # Step 5: Generate report
        print("\nStep 5: Generating HTML report...")
        report_path = generate_html_report(
            summary=results,
            output_tables=output_tables,
            title="RiskPaths Testing Report",
            model_name=model_name,
            git_commit=config['git_commit'],
            om_versions=' vs '.join([Path(p).name for p in config['om_root']]),
            environment_note="Example Python testing script"
        )
        
        print(f"\nCOMPLETE: Testing completed successfully!")
        print(f"Report available at: {report_path}")
        
        # Show summary
        if results and results.get('summary_table') is not None:
            summary_df = results['summary_table']
            if not summary_df.empty:
                total_tables = len(summary_df)
                tables_with_diffs = len(summary_df[summary_df['has_differences'] == True])
                print(f"Summary: {total_tables} tables analyzed, {tables_with_diffs} with differences")
        
        return results
        
    except Exception as e:
        print(f"ERROR: Testing failed: {str(e)}")
        raise


if __name__ == '__main__':
    test_riskpaths() 