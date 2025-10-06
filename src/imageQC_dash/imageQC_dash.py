#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Standalone app for displaying trend data from automated results.
Prepared for either local host or for data saved in minio-buckets

@author: Ellen Wasbo
"""
from __future__ import annotations
from dataclasses import dataclass, field
import os
import io
import time
import json
import webbrowser
from pathlib import Path

import logging
from datetime import date, datetime
import numpy as np
import pandas as pd
import dash
from dash import dcc, html, ctx
from dash.dependencies import Input, Output, ALL
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import plotly.graph_objects as go

#from imageQC_dash.scripts.ui_dash import run_dash_app
from imageQC_dash.scripts import config_func_dash as cffd


@dataclass
class Template:
    """Class holding template settings and values."""

    label: str = ''
    limits_and_plot_template: dict = field(default_factory=dict)
    data: dict = field(default_factory=dict)
    newest_date: str = 'xx.xx.xxxx'  # last data found in results
    days_since: int = -1  # days since newest date (on update)
    status: int = 0  # [0 = ok, 1 = failed, 2 = watch]


def read_csv(path, decimal_mark, client=None):
    """Read csv from file or Minio bucket."""
    status = False
    dataframe = None
    if client is None:
        input_file = path
    else:
        response = client.get_object(os.getenv('BUCKET_NAME'), path)
        file = response.read().decode('utf-8') 
        input_file = io.StringIO(file)

    try:
        dataframe = pd.read_csv(
            input_file, sep='\t', decimal=decimal_mark,
            parse_dates=[0], dayfirst=True,
            on_bad_lines='error', encoding='ISO-8859-1')
        if dataframe.index.size > 1:
            status = True
    except FileNotFoundError as ferror:
        print('FileNotFoundError                                ')
        print(path)
        print(ferror)
    except OSError as oerror:
        print('OSError - could not read file                    ')
        print(path)
        print(oerror)
    except pd.errors.EmptyDataError as error:
        print(path)
        print(error)
    except pd.errors.ParserError:
        n_headers = 0
        with open(input_file) as file:
            first_line = file.readline()
            n_headers = len(first_line.split(sep='\t'))
        if n_headers > 0:
            try:
                dataframe = pd.read_csv(
                    input_file, sep='\t', decimal=decimal_mark,
                    parse_dates=[0], dayfirst=True,
                    on_bad_lines='error',
                    usecols=list(range(n_headers)),
                    encoding='ISO-8859-1')
                if dataframe.index.size > 1:
                    status = True
            except Exception as error:
                print(f'Failed reading {path}')
                print(str(error))

    return (status, dataframe)


def get_data(config_path, client):
    """Extract data from result files combined with automation templates.

    Returns
    -------
    modality_dict: dict
        keys = modalities as defined in imageQCpy
        items = list of Templates defined above
        ignored modalities and templates with no results
    """
    print('Reading templates...')
    modality_dict = {}
    auto_templates = cffd.load_settings(
        'auto_templates', config_path, client)
    auto_vendor_templates = cffd.load_settings(
        'auto_vendor_templates', config_path, client)
    paramsets = cffd.load_paramset_decimarks(config_path, client)
    lim_plots = cffd.load_settings(
        'limits_and_plot_templates', config_path, client)
    if auto_templates or auto_vendor_templates:
        lim_plots = cffd.load_settings(
            'limits_and_plot_templates', config_path, client)
    else:
        lim_plots = {}
    all_templates = [auto_templates, auto_vendor_templates]

    print('Reading data from result files...')
    n_processed_files = 0
    for auto_no, template in enumerate(all_templates):
        for mod, template_list in template.items():
            param_labels = []
            decimarks = []
            lim_labels = []
            if mod not in [*modality_dict]:
                modality_dict[mod] = []
            try:
                lim_labels = [lim['label'] for lim in lim_plots[mod]]
                if auto_no == 0:
                    param_labels = [
                        paramset['label'] for paramset in paramsets[mod]]
                    decimarks = [paramset['decimal_mark']
                                 for paramset in paramsets[mod]]
                else:
                    decimarks = [paramsets[mod][0]['decimal_mark']]
            except (KeyError, IndexError):
                pass
            for temp in template_list:
                if all([
                        temp['label'] != '',
                        temp['path_output'] != '',
                        temp['active']]):
                    proceed = True
                    try:
                        if temp['import_only']:
                            proceed = False
                        elif temp['paramset_label'] == '':
                            proceed = False
                        elif temp['quicktemp_label'] == '':
                            proceed = False
                    except KeyError:
                        pass

                    if proceed:
                        proceed = False
                        dataframe = None

                        try:
                            idx_paramset = param_labels.index(
                                temp['paramset_label'])
                            proceed, dataframe = read_csv(
                                temp['path_output'], decimarks[idx_paramset],
                                client=client)
                        except (KeyError, ValueError):
                            pass

                        if proceed:
                            print(f'Reading results for {mod}/{temp["label"]}',
                                  end='\r', flush=True)
                            dataframe.dropna(
                                how='all', inplace=True)  # ignore empty rows
                            date_header = dataframe.columns[0]
                            dataframe = dataframe.sort_values(by=[date_header])
                            try:
                                first_row_val = dataframe[date_header].iloc[-1]
                            except IndexError:
                                first_row_val = ''
                            if isinstance(first_row_val, str):
                                newest_date = 'error'
                                days_since = -1000
                            else:
                                newest_date = first_row_val.date()
                                days_since = (date.today() - newest_date).days
                            lim_label = temp['limits_and_plot_label']
                            temp_this = Template(
                                label=temp['label'],
                                limits_and_plot_template=lim_label,
                                data=dataframe,
                                newest_date=f'{newest_date}',
                                days_since=days_since
                                )
                            create_empty = True
                            if lim_label != '':
                                if lim_label in lim_labels:
                                    idx_lim = lim_labels.index(lim_label)
                                    lim_temp = lim_plots[mod][idx_lim]
                                    create_empty = False
                            if create_empty:
                                lim_temp = {'groups': [
                                    [col] for col in dataframe.columns[1:]]}
                            temp_this.limits_and_plot_template = lim_temp
                            modality_dict[mod].append(temp_this)
                            n_processed_files += 1

    print(f'Processed {n_processed_files} result files.'
          '                                                                          ')

    # remove empty modality from list dict
    len_temp_lists = [len(template_list)
                      for mod, template_list in modality_dict.items()]
    mods_orig = [*modality_dict]
    for i in range(len(modality_dict)):
        if len_temp_lists[-(i+1)] == 0:
            modality_dict.pop(mods_orig[-(i+1)])
    return modality_dict


def run_dash_app(use_minio):
    """Update content in dashboard to display automation results."""
    print('----run_dash_app')
    modality_dict = {}
    dash_settings = {}
    logger = logging.getLogger('imageQC')
    logger.setLevel(logging.ERROR)
    app = dash.Dash(
        __name__, suppress_callback_exceptions=True,
        external_stylesheets=[dbc.themes.YETI])
    
    if use_minio:
        '''
        if dash_settings['server']:
            prefix = os.environ['SHINYPROXY_PUBLIC_PATH']
        '''
        from minio import Minio
        client = Minio(os.getenv('IMAGEQC_S3_URL'),
            access_key=os.getenv('IMAGEQC_ACCESS_KEY'),
            secret_key=os.getenv('IMAGEQC_SECRET_KEY'),
            secure=False)
        bucket_name = ''  # TODO
        modality_dict = get_data('', client=client, bucket_name=bucket_name)
        dash_settings = cffd.load_settings(
            'dash_settings', '', client=client, bucket_name=bucket_name)
    else:
        # run from imageQC (config path set as env-variable)
        config_path = os.environ['IMAGEQC_CONFIG_FOLDER']
        modality_dict = get_data(config_path, None)
        dash_settings = cffd.load_settings(
            'dash_settings', config_path, None)

    def layout():
        """Build the overall layout structure."""
        print('----layout')
        return dbc.Container([
            dcc.Store(id='results'),
            dbc.Row([
                dbc.Col(html.H1(dash_settings['header'])),
                dbc.Col(html.Img(src=dash_settings['url_logo'])),
                ]),
            dbc.Row(html.Div([
                dbc.Tabs([
                    dbc.Tab(tab_overview(), label='Overview', tab_id='overview'),
                    dbc.Tab(tab_results(),
                            label='Results pr template', tab_id='results'),
                    dbc.Tab(tab_admin(),
                            label='Admin', tab_id='admin'),
                    ],
                    id='tabs',
                    active_tab='overview',
                    )
                ])),
            ])

    def tab_admin():
        content = html.Div([
            dbc.Row([
                html.Button('Close', id='close-app', n_clicks=0),
                ])
            ])
        return content

    def table_overview():
        print('----table_overview')
        mods = [[mod] * len(modality_dict[mod])
                for mod in modality_dict.keys()]
        labels = [[temp.label for temp in modality_dict[mod]]
                for mod in modality_dict.keys()]
        dates = [[temp.newest_date for temp in modality_dict[mod]]
                 for mod in modality_dict.keys()]
        days = [[temp.days_since for temp in modality_dict[mod]]
                for mod in modality_dict.keys()]
        table_data = {
            'modality': [j for i in mods for j in i],
            'template_label': [j for i in labels for j in i],
            'last_date': [j for i in dates for j in i],
            'days_since': [j for i in days for j in i],
            }
        dataframe = pd.DataFrame(table_data)
        data = dataframe.to_dict('records')

        columnDefs = [
            {
                'field': 'modality',
                'headerName': dash_settings['table_headers'][0],
                'cellDataType': 'text',
                'filter': True,
                'width': 100,
                },
            {
                'field': 'template_label',
                'headerName': dash_settings['table_headers'][1],
                'cellDataType': 'text',
                'filter': True,
                },
            {
                'field': 'last_date',
                'headerName': dash_settings['table_headers'][2],
                'cellDataType': 'dateString',
                'width': 100,
                },
            {
                'field': 'days_since',
                'headerName': dash_settings['table_headers'][3],
                'cellDataType': 'number',
                'filter': True,
                'width': 100,
                'cellStyle': {
                    'styleConditions': [
                        {
                            'condition':
                                f'params.value >= {dash_settings["days_since_limit"]}',
                            'style': {'backgroundColor': 'pink'},
                        }],
                    }

                },
            ]

        grid = dag.AgGrid(
            id='overview_modality_table',
            rowData=data,
            columnDefs=columnDefs,
            dashGridOptions={'pagination':True}
        )

        return html.Div([grid])

    def tab_overview():
        print('----tab_overview')
        return html.Div([
            dbc.Row([
                dbc.Col(table_overview()),
                ]),
            dbc.Row(dbc.Alert(
                f'Last update {datetime.today().strftime("%Y-%m-%d %H:%M:%S")}',
                color='light')),
            ], style={'marginBottom': 50, 'marginTop': 25}
            )

    def tab_results():
        print('----tab_results')
        return html.Div([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        dbc.Label('Select modality'),
                        dbc.RadioItems(
                            options=[
                                {'label': mod, 'value': i}
                                for i, mod in enumerate([*modality_dict])],
                            value=0,
                            id='modality_select'),
                    ]),
                    html.Hr(),
                    html.Div([
                        dbc.Label('Select template'),
                        dbc.RadioItems(
                            options=update_template_options(),
                            value=0,
                            id='template_select'),
                    ])
                    ],
                    width=2,
                ),
                dbc.Col([
                    html.Div(id='template_graphs')
                    ]),
                ]),
            ], style={'marginBottom': 50, 'marginTop': 25})

    def update_template_options(modality_value=0):
        print('----update_template_options')
        try:
            mod = [*modality_dict][modality_value]
            template_list = modality_dict[mod]
        except (IndexError, KeyError):
            template_list = []
        print(f'template_list {template_list}')
        return [{'label': temp.label, 'value': i}
                for i, temp in enumerate(template_list)]

    def generate_figure_list(data, lim_plots):
        print('----generate_figure_list')
        figures = []
        colorlist = dash_settings['colors']
        for group_idx, group in enumerate(lim_plots['groups']):
            fig = ''
            if lim_plots['groups_hide'][group_idx] is False:
                fig = go.Figure()
                for lineno, header in enumerate(group):
                    color = colorlist[lineno % len(colorlist)]
                    fig.add_trace(
                        go.Scatter(
                            x=data[data.columns[0]], y=data[header],
                            line_color=color,
                            name=header, 
                            mode='lines+markers',
                            showlegend=False, legendgroup=str(group_idx),
                            ),
                        )

                if any(lim_plots['groups_limits'][group_idx]):
                    lims = lim_plots['groups_limits'][group_idx]
                    lim_text = [None, None]
                    if isinstance(lims[0], str):
                        if lims[0] == 'text':
                            lims = [None, None]
                        elif lims[0] == 'relative_first':
                            first_val = data[header][0]
                            tol = first_val * 0.01 * lims[1]
                            lim_text = [f'first +/- {lims[1]}%', '']
                            lims = [first_val - tol, first_val + tol]
                        else:  # 'relative_median'
                            med_val = np.median(data[header][:-1])
                            tol = med_val * 0.01 * lims[1]
                            lim_text = [f'median +/- {lims[1]}%', '']
                            lims = [med_val - tol, med_val + tol]
                    else:
                        lim_text = [f'min {lims[0]}', f'max {lims[1]}']
                    yanchors = ['bottom', 'top']
                    for limno, lim in enumerate(lims):
                        if lim is not None:
                            label_dict = dict(
                                text=lim_text[limno], textposition='start',
                                font=dict(color='red'),
                                yanchor=yanchors[limno])
                            fig.add_hline(
                                y=lim, line_dash='dot', line_color='red',
                                label=label_dict)

                            for header in group:
                                if limno == 0:  # lower limit
                                    data_off = data[data[header] < lim]
                                else:
                                    data_off = data[data[header] > lim]
                                if len(data_off) > 0:
                                    fig.add_trace(
                                        go.Scatter(
                                            x=data_off[data_off.columns[0]],
                                            y=data_off[header],
                                            name=header,
                                            mode='markers', 
                                            marker=dict(
                                                color='red', size=15),
                                            showlegend=False,
                                            ),
                                        )

                set_range = lim_plots['groups_ranges'][group_idx]
                if set_range[0] is None and set_range[1] is None:
                    autorange = True
                elif set_range[0] is not None and set_range[1] is not None:
                    autorange = False
                elif set_range[0] is None and set_range[1] is not None:
                    autorange = "min"
                elif set_range[1] is None and set_range[0] is not None:
                    autorange = "max"
                fig.update_yaxes(
                    range=set_range, autorange=autorange)
            figures.append(fig)
        return figures

    @app.callback(
        Output('tab_admin', 'children'),
        Input('close-app', 'n_clicks'),
        prevent_intitial_call=True
        )
    def on_close_click(n):
        if n is not None:
            app.server.shutdown()

    @app.callback(
        Output('tabs', 'active_tab'),
        Output('modality_select', 'value'),
        [Input({'type': 'overview_modality_button', 'index': ALL}, 'n_clicks')],
    )
    def go_to_modality(n_clicks):
        print('----go_to_modality')
        mod_value = 0
        if ctx.triggered_id:
            mod_value = [*modality_dict].index(ctx.triggered_id.index)

        return 'results', mod_value

    @app.callback(
        Output('template_select', 'options'),
        Output('template_select', 'value'),
        [
            Input('modality_select', 'value'),
        ],
    )
    def on_modality_select(modality_value):
        print('----on_modality_select')
        return update_template_options(modality_value=modality_value), 0

    @app.callback(
        Output('template_graphs', 'children'),
        [
            Input('modality_select', 'value'),
            Input('template_select', 'value'),
        ],
    )
    def on_template_select(modality_value, template_value):
        print('----on_template_select')
        proceed = True
        try:
            mod = [*modality_dict][modality_value]
        except IndexError:
            proceed = False
        if proceed:
            data = modality_dict[mod][template_value].data
            lim_plots = modality_dict[mod][template_value].limits_and_plot_template
            titles = [title for i, title in enumerate(lim_plots['groups_title'])
                      if lim_plots['groups_hide'][i] is False]
            n_rows = len(titles)

            table_data = {'title': titles}
            df = pd.DataFrame(table_data)
            df['graph'] = ''
            figures = generate_figure_list(data, lim_plots)

            fig_height = dash_settings['plot_height'] * n_rows

            for i, r in df.iterrows():
                fig = figures[i]
                fig.update_layout(
                    margin=dict(t=0, b=0, l=0, r=0),
                    plot_bgcolor='#eee',
                    height=fig_height)
                fig.update_xaxes(showgrid=False)
                fig.update_yaxes(showgrid=False, visible=False)
                df.at[i, 'graph'] = fig

            columnDefs = [
                {'field': 'title', 'headerName': 'Plot title'},
                {
                    'field': 'graph',
                    'cellRenderer': 'DCC_GraphClickData',
                    'headerName': 'Plot',
                    'maxWidth': 500,
                    'minWidth': 300,
                }
                ]

            grid = dag.AgGrid(
                id='graph_table',
                rowData=df.to_dict("records"),
                columnDefs=columnDefs,
                style={"height": "100%"},
                dashGridOptions={"rowHeight": 100, "animateRows": False},
            )

            template_content = dcc.Loading(
                id='loading-1',
                children=[html.Div([grid])],
                type='circle')
        else:
            template_content = html.Div([])
        return template_content

    @app.callback(
        Output("custom-component-graph-output", "children"),
        Input("custom-component-graph-grid", "cellRendererData")
    )
    def graphClickData(d):
        print('----graphClickData')
        return json.dumps(d)

    @app.callback(
        Output("loading-output-1", "children"),
        Input("loadig-1", "value")
    )
    def input_triggers_spinner(value):
        time.sleep(1)
        return value

    print('----before app.layout')
    app.layout = layout
    print('----after app.layout')
    if dash_settings['server'] == 'waitress':
        print('----waitress')
        url = f'http://{dash_settings["host"]}:{dash_settings["port"]}'
        webbrowser.open_new(url=url)
        from waitress import serve
        print('----serve')
        serve(app.server,
              host=dash_settings['host'], port=dash_settings['port'])
    else:
        app.run(debug=True, host=dash_settings['host'])
    breakpoint()
    

    logger = logging.getLogger('imageQC')
    logger.setLevel(logging.INFO)



if __name__ == '__main__':

    proceed = True
    minio = False
    try:
        # if imageQC is running, use defined config path from environ
        config_path = os.environ['IMAGEQC_CONFIG_FOLDER']
    except KeyError:
        # find values from .env
        env_path = Path(__file__).parent / '.env'
        if Path.exists(env_path):
            from dotenv import load_dotenv
            load_dotenv(env_path)

            if 'IMAGEQC_CONFIG_FOLDER' in os.environ:
                print('----iQC')
            else:
                if 'IMAGEQC_BUCKET_NAME' in os.environ:
                    print('----minio')
                    minio = True
                else:
                    print('missing expected keys in .env. See Wiki.')
                    proceed = False

        else:
            print('missing .env-file. See Wiki.')
            proceed = False

    if proceed:
        run_dash_app(minio)
    else:
        print('Failed to run Dash application.')
