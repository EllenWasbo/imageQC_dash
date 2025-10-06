# -*- coding: utf-8 -*-
"""
Tests on imageQC_dash

@author: ewas
"""
from pathlib import Path
from imageQC_dash.scripts.ui_dash import get_data


path_data = Path(__file__).parent / 'data'


def replace_output_path_to_current(results_path):
    """Replace automation output path to current data/results folder."""
    replace_str = r'C:\Midlertidig_Lagring\res_test'
    yaml_file = path_data / 'config/auto_templates.yaml'
    with open(yaml_file) as f:
        lines = f.readlines()
        for l, line in enumerate(lines):
            if replace_str in line:
                lines[l] = line.replace(replace_str, str(results_path))

        with open(yaml_file, 'w') as f:
            for lin in lines:
                f.write(lin)


def test_read_config_and_result_files():
    config_path = path_data / 'config'
    results_path = path_data / 'results'
    replace_output_path_to_current(results_path)
    modality_dict = get_data(config_path)
    assert len(modality_dict['CT']) == 2
    assert len(modality_dict['Xray']) == 2
