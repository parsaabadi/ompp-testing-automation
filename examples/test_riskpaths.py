#!/usr/bin/env python3
"""
RiskPaths Model Testing Example

This script shows how to test the RiskPaths model across different OpenM++ versions.
It's a complete example of the testing workflow.
"""

import sys
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from ompp_testing import (
    clone_repo, build_model, start_oms, stop_oms,
    get_output_tables, run_models, generate_html_report
)


def main():
    """Run a complete RiskPaths testing workflow."""
    
    print("🚀 Starting RiskPaths model testing")
    
    # Configuration - change these paths to match your setup
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
        # Step 1: Clone the repository
        print("\n📥 Step 1: Cloning repository...")
        model_sln_path = clone_repo(
            git_url=config['git_url'],
            git_commit=config['git_commit'],
            model_sln=config['model_sln']
        )
        
        # Step 2: Build the model
        print("\n🔨 Step 2: Building model...")
        model_names = build_model(
            model_sln=model_sln_path,
            om_root=config['om_root'],
            vs_cmd_path=config['vs_cmd_path']
        )
        
        if not model_names:
            raise RuntimeError("No models built successfully")
        
        model_name = model_names[0]
        print(f"✅ Built model: {model_name}")
        
        # Step 3: Get output tables
        print("\n📊 Step 3: Getting output tables...")
        output_tables = get_output_tables(
            model_name=model_name,
            om_root=config['om_root'][0]
        )
        
        print(f"Found {len(output_tables)} output tables")
        
        # Step 4: Run models and compare
        print("\n⏳ Step 4: Running models and comparing results...")
        summary = run_models(
            om_root=config['om_root'],
            model_name=model_name,
            cases=100000,  # Smaller number for testing
            threads=4,
            sub_samples=4,
            tables=output_tables['name'].tolist()
        )
        
        # Step 5: Generate report
        print("\n📄 Step 5: Generating HTML report...")
        om_versions = " vs ".join([f"v{Path(root).name}" for root in config['om_root']])
        
        report_path = generate_html_report(
            summary=summary,
            output_tables=output_tables,
            title=f"Testing OpenM++ with {model_name}",
            model_name=model_name,
            git_commit=config['git_commit'],
            om_versions=om_versions,
            environment_note="All testing done in Windows environment"
        )
        
        print(f"\n🎉 Testing completed successfully!")
        print(f"📄 Report available at: {report_path}")
        
        # Show summary
        if summary and 'summary_table' in summary and not summary['summary_table'].empty:
            total_tables = len(summary['summary_table'])
            tables_with_diffs = len(summary['summary_table'][
                summary['summary_table']['has_differences'] == True
            ])
            
            print(f"📊 Summary: {total_tables} tables analyzed, {tables_with_diffs} with differences")
        
    except Exception as e:
        print(f"❌ Testing failed: {str(e)}")
        sys.exit(1)
    
    finally:
        # Always clean up
        try:
            stop_oms()
        except:
            pass


if __name__ == '__main__':
    main() 