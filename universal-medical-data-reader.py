# -*- coding: utf-8 -*-
"""
Created on Sun Oct  5 10:16:25 2025

@author: deepj
"""

import os
import pandas as pd
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import plotly.express as px

# Optional for PDF export
import pdfkit

# Load summary CSV generated from previous pipeline
def load_summary(csv_file):
    if os.path.exists(csv_file):
        df = pd.read_csv(csv_file)
        # Ensure date column is datetime
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
        return df
    else:
        raise FileNotFoundError(f"{csv_file} not found. Please run the medical data pipeline first.")

df = load_summary("medical_data_summary.csv")

# Explode measurement_name and measurement_value if multiple values separated by commas
def explode_measurements(df):
    df = df.copy()
    df['measurement_name'] = df['measurement_name'].astype(str)
    df['measurement_value'] = df['measurement_value'].astype(str)
    df = df.assign(
        measurement_name=df['measurement_name'].str.split(', '),
        measurement_value=df['measurement_value'].str.split(', ')
    ).explode(['measurement_name','measurement_value'])
    df['measurement_value'] = pd.to_numeric(df['measurement_value'], errors='coerce')
    return df

df_exploded = explode_measurements(df)

# Dash app
app = dash.Dash(__name__)
server = app.server

# Layout
app.layout = html.Div([
    html.H1("Advanced Medical Data Dashboard"),
    
    # Filters
    html.Div([
        html.Div([
            html.Label("Select Patient(s):"),
            dcc.Dropdown(
                id='patient-dropdown',
                options=[{'label': n, 'value': n} for n in df['patient_id'].dropna().unique()],
                multi=True
            )
        ], style={'width':'45%', 'display':'inline-block'}),
        
        html.Div([
            html.Label("Select Measurement(s):"),
            dcc.Dropdown(
                id='measurement-dropdown',
                options=[{'label': m, 'value': m} for m in df_exploded['measurement_name'].dropna().unique()],
                multi=True
            )
        ], style={'width':'45%', 'display':'inline-block','marginLeft':'5%'})
    ]),
    
    html.Br(),
    
    # Patient Summary Cards
    html.Div(id='summary-cards', style={'display':'flex', 'flexWrap':'wrap'}),
    
    html.Br(),
    
    # Trend chart
    dcc.Graph(id='trend-graph'),
    
    html.Br(),
    
    # Data Table
    dash_table.DataTable(
        id='patient-table',
        columns=[{"name": i, "id": i} for i in df_exploded.columns],
        data=df_exploded.to_dict('records'),
        page_size=10,
        style_table={'overflowX':'auto'},
        export_format="csv"
    ),
    
    html.Br(),
    html.Button("Download PDF Report", id="download-pdf", n_clicks=0)
])

# Callbacks
@app.callback(
    Output('trend-graph', 'figure'),
    Output('patient-table', 'data'),
    Output('summary-cards', 'children'),
    Input('patient-dropdown', 'value'),
    Input('measurement-dropdown', 'value')
)
def update_dashboard(selected_patients, selected_measurements):
    filtered_df = df_exploded.copy()
    
    # Filter by patients
    if selected_patients:
        filtered_df = filtered_df[filtered_df['patient_id'].isin(selected_patients)]
    
    # Filter by measurements
    if selected_measurements:
        filtered_df = filtered_df[filtered_df['measurement_name'].isin(selected_measurements)]
    
    # Trend chart
    if 'date' in filtered_df.columns:
        fig = px.line(
            filtered_df,
            x='date',
            y='measurement_value',
            color='measurement_name',
            line_group='patient_id',
            markers=True,
            hover_data=['patient_name']
        )
        fig.update_layout(title="Measurement Trends Over Time")
    else:
        fig = px.scatter(
            filtered_df,
            x='patient_name',
            y='measurement_value',
            color='measurement_name',
            title="Measurement Values"
        )
    
    # Patient summary cards
    summary_cards = []
    for pid in filtered_df['patient_id'].dropna().unique():
        pdata = filtered_df[filtered_df['patient_id']==pid]
        card = html.Div([
            html.H3(f"Patient: {pid}"),
            html.P(f"Name: {pdata['patient_name'].iloc[0]}"),
            html.P(f"DOB: {pdata['dob'].iloc[0]}"),
            html.P(f"Measurements: {', '.join(pdata['measurement_name'].unique())}"),
            html.P(f"Latest Measurement Date: {pdata['date'].max() if 'date' in pdata.columns else 'N/A'}")
        ], style={'border':'1px solid black','borderRadius':'5px','padding':'10px','margin':'5px','width':'22%'})
        summary_cards.append(card)
    
    return fig, filtered_df.to_dict('records'), summary_cards

# PDF Download callback (requires pdfkit + wkhtmltopdf installed)
@app.callback(
    Output("download-pdf", "n_clicks"),
    Input("download-pdf", "n_clicks"),
    State('patient-table', 'data'),
    prevent_initial_call=True
)
def generate_pdf(n_clicks, table_data):
    if n_clicks > 0 and table_data:
        pdf_html = "<h1>Patient Medical Report</h1>"
        pdf_html += "<table border='1' cellspacing='0' cellpadding='5'>"
        pdf_html += "<tr>" + "".join([f"<th>{col}</th>" for col in table_data[0].keys()]) + "</tr>"
        for row in table_data:
            pdf_html += "<tr>" + "".join([f"<td>{row[col]}</td>" for col in row.keys()]) + "</tr>"
        pdf_html += "</table>"
        
        pdfkit.from_string(pdf_html, "medical_report.pdf")
        return 0
    return n_clicks

# Run server
if __name__ == "__main__":
    app.run_server(debug=True)
