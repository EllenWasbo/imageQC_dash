#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Standalone app for displaying trend data from automated results.
Prepared for either local host or for data saved in minio-buckets

@author: Ellen Wasbo
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import os
import sys
from pathlib import Path
import yaml


@dataclass
class DashSettingsDefault:
    """Copy from imageQC / config /config_classes/ DashSettings."""

    label: str = ''
    host: str = '127.0.0.1'
    port: int = 8050
    server: str = 'waitress'
    url_logo: str = ''
    header: str = 'Constancy controls'
    table_headers: list[
        str] = field(default_factory=lambda: [
            'Modality', 'Template', 'Last results', 'Elapsed days', 'Status'])
    days_since_limit: int = 30
    plot_height: int = 200
    colors: list[
        str] = field(default_factory=lambda: [
            '#000000', '#5165d5', '#a914a6', '#7f9955', '#efb412',
            '#97d2d1', '#b3303b'])
    override_css: bool = False

def find_user_prefs_config_folder():
    config_folder = ''
    user_prefs_fname = 'user_preferences.yaml'
    if sys.platform.startswith("win"):
        appdata = os.path.join(os.environ['APPDATA'], 'imageQC')
        tempdir = r'C:\Windows\Temp\imageQC'  # alternative to APPDATA if needed
    else:  # assume Linux for now
        appdata = os.path.expanduser('~/.config/imageQC')
        tempdir = r'/etc/opt/imageQC'

    path = os.path.join(appdata, user_prefs_fname)
    if os.path.exists(path) is False:
        path = os.path.join(tempdir, user_prefs_fname)  # try with TEMPDIR

    if os.path.exists(path):
        with open(path, 'r') as file:
            doc = yaml.safe_load(file)
            config_folder = doc['config_folder']

    return config_folder


def verify_input_dict(dict_input, default_object):
    """Verify input from yaml if config classes change on newer versions.

    Add missing keywords from input.

    Parameters
    ----------
    dict_input : dict
        dictionary to verify
    default_object : object
        object to compare attributes vs dict_input keys

    Returns
    -------
    updated_dict : dict
        updated input_dict with valid keys
    """
    
    default_dict = asdict(default_object)
    if len(dict_input) == 0:
        updated_dict = default_dict
    else:
        actual_keys = [*default_dict]
        updated_dict = {}
        for key in actual_keys:
            if key in dict_input:
                updated_dict[key] = dict_input[key]
            else:
                updated_dict[key] = default_dict[key]
    return updated_dict


def convert_OneDrive(path):
    """Test wether C:Users and OneDrive in path - replace username if not correct.

    Option to use shortcut paths in OneDrive to same sharepoint
    (shortcut name must be the same).

    Parameters
    ----------
    path_string : str

    Returns
    -------
    path : str
        as input or replaced username if OneDrive shortcut
    """
    if 'OneDrive' in path and 'C:\\Users' in path:
        username = os.getlogin()
        path_obj = Path(path)
        if path_obj.exists() is False:
            if username != path_obj.parts[2]:
                path = os.path.join(*path_obj.parts[:2], username, *path_obj.parts[3:])
    return path


def load_paramset_decimarks(config_path, client=None):
    """Load paramset (modality_dict) as dict from yaml file in config folder.

    Keep only labels and decimal mark for use in dash_app.

    Parameters
    ----------
    config_path : str or Path
        path to config folder with yaml files
    client: obj or None
        client if minio used

    Returns
    -------
    dict
        keys modality string
        items list of dict {label, decimal_mark}
    """
    path = Path(config_path)
    modalities = ['CT', 'Xray', 'Mammo', 'NM', 'SPECT', 'PET', 'MR']
    fnames = [f'paramsets_{m}' for m in modalities]
    paramsets = {
        modality: [] for modality in modalities}

    if client is None:
        bucket_name = ''
    else:
        bucket_name = os.getenv('BUCKET_NAME')
        
    def extract_label_deci(yaml_docs):
        for doc in yaml_docs:
            temp = {
                'label': doc['label'],
                'decimal_mark': doc['output']['decimal_mark']
                }
            paramsets[mod].append(temp)

    for idx, fname in enumerate(fnames):
        mod = modalities[idx]
        path_this = path / f'{fname}.yaml'
        docs = None
        if path_this.exists():
            try:
                if bucket_name:
                    response = client.get_object(bucket_name, path_this)
                    file = response.read().decode('utf-8')
                    docs = yaml.safe_load_all(file)
                    extract_label_deci(docs)
                else:
                    with open(path_this, 'r') as file:
                        docs = yaml.safe_load_all(file)
                        extract_label_deci(docs)
            except Exception as error:
                print(f'config_func_dash.py load_paramset {fname}: {str(error)}')

    return paramsets


def load_settings(fname, config_path, client=None):
    """Load settings as dict from yaml file in config folder.

    Parameters
    ----------
    fname : str
        yaml filename without folder and extension
    config_path: str or Path
        path to config folder
    client: obj or None
        client if minio used

    Returns
    -------
    dict
    """
    settings = {}
    path = Path(config_path) / f'{fname}.yaml'

    if client is None:
        bucket_name = ''
    else:
        bucket_name = os.getenv('BUCKET_NAME')

    if 'dash' in fname:
        try:
            if bucket_name:
                response = client.get_object(bucket_name, path)
                file = response.read().decode('utf-8')
                settings = yaml.safe_load(file)
            else:
                with open(path, 'r') as file:
                    settings = yaml.safe_load(file)
        except FileNotFoundError:
            print('Missing dash_settings.yaml')
            print('Trying with default settings')
        except Exception as error:
            print(f'Failed to load dash_settings.yaml: {str(error)}')
            print('Trying with default settings')

        settings = verify_input_dict(settings, DashSettingsDefault())
    else:
        try:
            docs = None
            if bucket_name:
                response = client.get_object(bucket_name, path)
                file = response.read().decode('utf-8')
                docs = yaml.safe_load(file)
            else:
                with open(path, 'r') as file:
                    docs = yaml.safe_load(file)
            if docs:
                for mod, doc in docs.items():
                    settings[mod] = []
                    for temp in doc:
                        settings[mod].append(temp)
                        if bucket_name and 'auto' in fname:
                            try:
                                for attr in [
                                        'path_input',
                                        'path_output',
                                        'path_warnings']:
                                    new_path = convert_OneDrive(
                                        settings[mod][-1][attr])
                                    settings[mod][-1][attr] = new_path
                            except (IndexError, KeyError, AttributeError):
                                pass
        except Exception as error:
            print(f'config_func_dash.py load_settings: {str(error)}')

    return settings
