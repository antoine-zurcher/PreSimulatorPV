import dash
from dash import dcc
from dash import html, dash_table, ctx
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
from dash_extensions.enrich import Dash, Output, Trigger
import dash_leaflet as dl
import datetime

from pre_simulator import *

load_parameters = LoadParameters(
    monthly_util=[1700, 1400, 1000, 700, 600, 700, 600, 600, 800, 1000, 1600, 2000],  # kWh
    occ_schedule=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
                  1.0, 1.0, 1.0, 1.0],  # frac
    occupants=4,
    retrofitted=0,
    floors=2,
    t_cool=24,  # °C
    t_heat=20,  # °C
    t_sched=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
             1.0, 1.0, 1.0],  # on/off
    year_built=2000,
    floor_area=200,  # m2
    en_cool=1.0,
    en_dishwasher=1.0,
    en_dryer=1.0,
    en_fridge=1.0,
    en_heating=1.0,
    en_misc=1.0,
    en_stove=1.0,
    en_washing_machine=1.0,
)

fig_energy = go.Figure()
fig_finance = go.Figure()
fig_profiles = go.Figure()
fig_bills = go.Figure()
fig_load = go.Figure()
fig_payback = go.Figure()

autonomy = 0
electric_bill_reduction = 0
electric_energy_export = 0

latitude = 45.9765878
longitude = 7.6496971

app = dash.Dash(external_stylesheets=[dbc.themes.PULSE, dbc.icons.BOOTSTRAP],
                prevent_initial_callbacks=True)
server = app.server

src_autonomy = app.get_asset_url('percent_autonomy_none.png')
src_electric_bill_reduction = app.get_asset_url('percent_bill_reduction_none.png')
src_electric_energy_export = app.get_asset_url('percent_elec_export_none.png')
src_kwh_diagram = app.get_asset_url('kwh_template.png')

simulating = False
parameter_error = False

# the style arguments for the sidebar. We use position:fixed and a fixed width
SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "19rem",
    "padding": "2rem 1rem",
    "background-color": "#0E1012",
    "overflow": "scroll",
}

# the styles for the main content position it to the right of the sidebar and
# add some padding.
CONTENT_STYLE = {
    "margin-left": "19rem",
    "margin-right": "2rem",
    "padding": "2rem 1rem",
    "background-color": "#FFFFFF",
}

sidebar = html.Div(
    [
        html.H2("Parameters", className="display-6", style={'color': 'white'}),
        html.Hr(style={'color': 'white'}),
        html.P(
            "Enter the parameters of your PV-Battery system here:", className="h6", style={'color': 'white'}
        ),
        html.Br(),
        dbc.Tooltip(
            "Find the latitude and the longitude of your system on a map.",
            target="button-modal-location",
            placement='right',
        ),
        dbc.Row(
            [
                dbc.Col(html.H4("Location", className="display-8", style={'color': 'white'}), width='auto'),
                dbc.Col(dbc.Button(html.Img(src=app.get_asset_url('pin-map-fill.svg')), id="button-modal-location",
                                   n_clicks=0, color="warning"), width='auto'),
            ], justify='between'
        ),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("System location")),
                dbc.ModalBody(children=[
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.FormFloating(
                                        [
                                            dbc.Input(type="number", placeholder="34.123", id='input-latitude-modal',
                                                      value=latitude),
                                            dbc.Label("Latitude (°)"),
                                        ]
                                    ),
                                ],
                                width=6,
                            ),
                            dbc.Col(
                                [
                                    dbc.FormFloating(
                                        [
                                            dbc.Input(type="number", placeholder="34.123", id='input-longitude-modal',
                                                      value=longitude),
                                            dbc.Label("Longitude (°)"),
                                        ]
                                    ),
                                ],
                                width=6,
                            ),
                        ],
                        className="g-3",
                    ),
                    html.Br(),
                    dl.Map(center=[48, 22], zoom=4, children=[dl.TileLayer(), dl.LayerGroup(id="layer"),
                                                              dl.LocateControl(options={
                                                                  'locateOptions': {'enableHighAccuracy': True}})],
                           id="map", style={'width': '100%', 'height': '60vh', 'margin': "auto", "display": "block"}),
                ], style={"padding": "2rem"}),
                dbc.ModalFooter(dbc.Button("Set", id="button-close-modal-location", color="warning")),
            ],
            id="modal-location",
            size="xl",
            is_open=False,
            backdrop="static",
            keyboard=False,
        ),
        dbc.Toast(
            "No data is available for the specified location. Please use the map.",
            id="popover-location",
            header="Location error",
            is_open=False,
            dismissable=True,
            icon="danger",
            # top: 66 positions the toast below the navbar
            style={"position": "fixed", "top": '2rem', "right": '2rem', "width": '20rem'},
        ),
        dbc.Popover(
            [
                dbc.PopoverHeader("Parameter error"),
                dbc.PopoverBody("The value of the latitude must be between -90° and 90°."),
            ],
            id="popover-latitude",
            is_open=False,
            target="input-latitude",
            placement='top',
        ),
        dbc.FormFloating(
            [
                dbc.Input(type="number", placeholder="34.123", id='input-latitude', value=45.9765878),
                dbc.Label("Latitude (°)"),
            ]
        ),
        dbc.Popover(
            [
                dbc.PopoverHeader("Parameter error"),
                dbc.PopoverBody("The value of the latitude must be between -180° and 180°."),
            ],
            id="popover-longitude",
            is_open=False,
            target="input-longitude",
            placement='top',
        ),
        dbc.FormFloating(
            [
                dbc.Input(type="number", placeholder="34.123", id='input-longitude', value=7.6496971),
                dbc.Label("Longitude (°)"),
            ]
        ),
        html.Br(),
        html.H4("System", className="display-8", style={'color': 'white'}),
        dbc.Popover(
            [
                dbc.PopoverHeader("Parameter error"),
                dbc.PopoverBody("The value of the PV peak power must be higher than 0 kWp."),
            ],
            id="popover-pv-power",
            is_open=False,
            target="input-pv-power",
            placement='top',
        ),
        dbc.FormFloating(
            [
                dbc.Input(type="number", placeholder="5.12", id='input-pv-power', value=5),
                dbc.Label("PV peak power (kWp)"),
            ]
        ),
        dbc.Tooltip(
            "Total installed PV peak power that the manufacturer declares under standard test conditions, which are a constant 1000W of solar irradiance per square meter in the plane of the array, at an array temperature of 25°C.",
            target="input-pv-power",
            placement='right',
        ),
        dbc.Popover(
            [
                dbc.PopoverHeader("Parameter error"),
                dbc.PopoverBody("The value of the tilt must be between 0° and 90°."),
            ],
            id="popover-tilt",
            is_open=False,
            target="input-tilt",
            placement='top',
        ),
        dbc.FormFloating(
            [
                dbc.Input(type="number", placeholder="34.123", id='input-tilt', value=60),
                dbc.Label("Tilt (°)"),
            ]
        ),
        dbc.Tooltip(
            "Angle of the PV modules from the horizontal plane. 0° is Horizontal and 90° is Vertical.",
            target="input-tilt",
            placement='right',
        ),
        dbc.Popover(
            [
                dbc.PopoverHeader("Parameter error"),
                dbc.PopoverBody("The value of the orientation must be between 0° and 360°."),
            ],
            id="popover-orientation",
            is_open=False,
            target="input-orientation",
            placement='top',
        ),
        dbc.FormFloating(
            [
                dbc.Input(type="number", placeholder="34.123", id='input-orientation', value=180),
                dbc.Label("Orientation (°)"),
            ]
        ),
        dbc.Tooltip(
            "Angle of the PV modules relative to the direction due South. 90° is East, 180° is South and 270° is West.",
            target="input-orientation",
            placement='right',
        ),
        dbc.Popover(
            [
                dbc.PopoverHeader("Parameter error"),
                dbc.PopoverBody("The value of the capacity must be positive or zero."),
            ],
            id="popover-battery-capacity",
            is_open=False,
            target="input-battery-capacity",
            placement='top',
        ),
        dbc.FormFloating(
            [
                dbc.Input(type="number", placeholder="34.123", id='input-battery-capacity', value=8),
                dbc.Label("Battery capacity (kWh)"),
            ]
        ),
        dbc.Tooltip(
            "Size, or energy capacity, of the battery used in the system.",
            target="input-battery-capacity",
            placement='right',
        ),
        dbc.Popover(
            [
                dbc.PopoverHeader("Parameter error"),
                dbc.PopoverBody("The value of the discharge limit must be between 0% and 100%."),
            ],
            id="popover-discharge-limit",
            is_open=False,
            target="input-discharge-limit",
            placement='top',
        ),
        dbc.FormFloating(
            [
                dbc.Input(type="number", placeholder="34.123", id='input-discharge-limit', value=10),
                dbc.Label("Discharge limit (%)"),
            ]
        ),
        dbc.Tooltip(
            "Batteries, especially Lead-acid batteries, degrade quickly if they are allowed to completely discharge too often. Therefore, a cutoff is normally imposed, so that the battery charge cannot go below a certain percentage of full charge.",
            target="input-discharge-limit",
            placement='right',
        ),
        dbc.Popover(
            [
                dbc.PopoverHeader("Parameter error"),
                dbc.PopoverBody("The value of the total installation cost must be positive."),
            ],
            id="popover-cost",
            is_open=False,
            target="input-cost",
            placement='top',
        ),
        dbc.FormFloating(
            [
                dbc.Input(type="number", placeholder="34.123", id='input-cost', value=cost_estimator(5, 8)),
                dbc.Label("Total installation cost (€)"),
            ]
        ),
        dbc.Tooltip(
            "The total installation cost of your system including PV panels, batteries, inverters, installation and subsidies. A cost estimation for your system is around {} €.".format(format_number(cost_estimator(5, 8))),
            target="input-cost",
            placement='right',
            id='tooltip-cost',
        ),
        html.Br(),
        html.H4("Grid", className="display-8", style={'color': 'white'}),
        dbc.Popover(
            [
                dbc.PopoverHeader("Parameter error"),
                dbc.PopoverBody("The value of the buy rate must be positive or zero."),
            ],
            id="popover-buy-rate",
            is_open=False,
            target="input-buy-rate",
            placement='top',
        ),
        dbc.FormFloating(
            [
                dbc.Input(type="number", placeholder="34.123", id='input-buy-rate', value=17.4),
                dbc.Label("Electricity buy rate (cts/kWh)"),
            ]
        ),
        dbc.Tooltip(
            "The price per kWh at which you buy electricity from your electricity supplier.",
            target="input-buy-rate",
            placement='right',
        ),
        dbc.Popover(
            [
                dbc.PopoverHeader("Parameter error"),
                dbc.PopoverBody("The value of the sell rate must be positive or zero."),
            ],
            id="popover-sell-rate",
            is_open=False,
            target="input-sell-rate",
            placement='top',
        ),
        dbc.FormFloating(
            [
                dbc.Input(type="number", placeholder="34.123", id='input-sell-rate', value=10.0),
                dbc.Label("Electricity sell rate (cts/kWh)"),
            ]
        ),
        dbc.Tooltip(
            "The price per kWh at which you sell electricity to your electricity supplier.",
            target="input-sell-rate",
            placement='right',
        ),
        html.Br(),
        html.H4("Load", className="display-8", style={'color': 'white'}),
        dbc.Row(
            [
                dbc.Col(dbc.Button("Set load", id="button-modal-load", n_clicks=0, color="warning"), width='auto'),
                dbc.Col(html.Div("", id='spinner-load'), width=3),
            ]
        ),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle('', id='text-computing'), close_button=False),
                dbc.ModalBody([
                    html.Br(),
                    html.Br(),
                    dbc.Spinner(html.Div(id="spinner-simulate"), color="warning"),
                    html.Br(),
                    html.Br(),
                ]),
            ],
            id="modal-simulate",
            size="lg",
            is_open=False,
            backdrop="static",
            keyboard=False,
        ),
        dcc.Interval(id="interval-simulate", n_intervals=0, interval=500),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Load parameters")),
                dbc.ModalBody(children=[
                    html.H4("Building information", className="display-8"),
                    dbc.Popover(
                        [
                            dbc.PopoverHeader("Parameter error"),
                            dbc.PopoverBody("The year of construction must be lower or equal to {}.".format(
                                datetime.datetime.now().date().strftime("%Y"))),
                        ],
                        id="popover-year-built",
                        is_open=False,
                        target="input-year-built",
                        placement='top',
                    ),
                    dbc.Popover(
                        [
                            dbc.PopoverHeader("Parameter error"),
                            dbc.PopoverBody("The floor area must be positive."),
                        ],
                        id="popover-floor-area",
                        is_open=False,
                        target="input-floor-area",
                        placement='top',
                    ),
                    dbc.Row(
                        [
                            dbc.Col(dbc.FormFloating(
                                [
                                    dbc.Input(type="number", placeholder="34.123", id='input-year-built', value=2000),
                                    dbc.Label("Year of construction"),
                                ]
                            ), ),
                            dbc.Col(dbc.FormFloating(
                                [
                                    dbc.Input(type="number", placeholder="34.123", id='input-floor-area', value=150),
                                    dbc.Label("Floor area (m2)"),
                                ]
                            ), ),
                        ]
                    ),
                    html.Br(),
                    html.H6("Occupancy:"),
                    dbc.Popover(
                        [
                            dbc.PopoverHeader("Parameter error"),
                            dbc.PopoverBody("The number of occupants must be positive."),
                        ],
                        id="popover-nb-occupants",
                        is_open=False,
                        target="input-nb-occupants",
                        placement='top',
                    ),
                    dbc.Popover(
                        [
                            dbc.PopoverHeader("Parameter error"),
                            dbc.PopoverBody("The number of floors must be positive."),
                        ],
                        id="popover-nb-floor",
                        is_open=False,
                        target="input-nb-floor",
                        placement='top',
                    ),
                    dbc.Row(
                        [
                            dbc.Col(dbc.FormFloating(
                                [
                                    dbc.Input(type="number", placeholder="34.123", id='input-nb-occupants', value=4),
                                    dbc.Label("Number of occupants"),
                                ]
                            ), ),
                            dbc.Col(dbc.FormFloating(
                                [
                                    dbc.Input(type="number", placeholder="34.123", id='input-nb-floor', value=2),
                                    dbc.Label("Number of floors"),
                                ]
                            ), ),
                        ]
                    ),
                    html.Br(),
                    dbc.Popover(
                        [
                            dbc.PopoverHeader("Parameter error"),
                            dbc.PopoverBody("The occupancy schedule must have values between 0 and 100."),
                        ],
                        id="popover-occupancy-schedule",
                        is_open=False,
                        target="table-occupancy-schedule",
                        placement='top',
                    ),
                    html.P(
                        "Please enter the occupancy schedule in percentage for every hour of a typical day (100: all of the occupants are present, 50: half of the occupants are present, 0: no occupents are present):"),
                    dash_table.DataTable(
                        id='table-occupancy-schedule',
                        columns=[{
                            'name': '{}'.format(i),
                            'id': 'column-occ-{}'.format(i)
                        } for i in range(0, 24)],
                        data=[
                            {'column-occ-{}'.format(i): 100 for i in range(0, 24)}
                        ],
                        editable=True,
                    ),
                    html.Br(),
                    dbc.Popover(
                        [
                            dbc.PopoverHeader("Parameter error"),
                            dbc.PopoverBody("The heating temperature setpoint must be between 0°C and 50°C."),
                        ],
                        id="popover-t-hot",
                        is_open=False,
                        target="input-t-hot",
                        placement='top',
                    ),
                    dbc.Popover(
                        [
                            dbc.PopoverHeader("Parameter error"),
                            dbc.PopoverBody("The cooling temperature setpoint must be between 0°C and 50°C."),
                        ],
                        id="popover-t-cold",
                        is_open=False,
                        target="input-t-cold",
                        placement='top',
                    ),
                    html.H6("Heating/Cooling parameters:"),
                    dbc.Row(
                        [
                            dbc.Col(dbc.FormFloating(
                                [
                                    dbc.Input(type="number", placeholder="34.123", id='input-t-hot', value=20),
                                    dbc.Label("Heating temperature setpoint (°C)"),
                                ]
                            ), ),
                            dbc.Col(dbc.FormFloating(
                                [
                                    dbc.Input(type="number", placeholder="34.123", id='input-t-cold', value=25),
                                    dbc.Label("Cooling temperature setpoint (°C)"),
                                ]
                            ), ),
                        ]
                    ),
                    html.Br(),
                    dbc.Popover(
                        [
                            dbc.PopoverHeader("Parameter error"),
                            dbc.PopoverBody("The heating/cooling schedule values must be ON or OFF."),
                        ],
                        id="popover-temperature-schedule",
                        is_open=False,
                        target="table-temperature-schedule",
                        placement='top',
                    ),
                    html.P(
                        "Please enter when the heating/cooling system is active for every hour of a typical day (ON/OFF):"),
                    dash_table.DataTable(
                        id='table-temperature-schedule',
                        columns=[{
                            'name': '{}'.format(i),
                            'id': 'column-temp-{}'.format(i)
                        } for i in range(0, 24)],
                        data=[
                            {'column-temp-{}'.format(i): 'ON' for i in range(0, 24)}
                        ],
                        editable=True,
                        style_data_conditional=
                        [
                            {
                                'if': {
                                    'filter_query': '{{column-temp-{col}}} = "ON"'.format(col=col),
                                    'column_id': 'column-temp-{}'.format(col)
                                },
                                'backgroundColor': 'green',
                                'color': 'white'
                            } for col in range(0, 24)
                        ] +
                        [
                            {
                                'if': {
                                    'filter_query': '{{column-temp-{col}}} = "on"'.format(col=col),
                                    'column_id': 'column-temp-{}'.format(col)
                                },
                                'backgroundColor': 'green',
                                'color': 'white'
                            } for col in range(0, 24)
                        ] +
                        [
                            {
                                'if': {
                                    'filter_query': '{{column-temp-{col}}} = "off"'.format(col=col),
                                    'column_id': 'column-temp-{}'.format(col)
                                },
                                'backgroundColor': 'red',
                                'color': 'white'
                            } for col in range(0, 24)
                        ] +
                        [
                            {
                                'if': {
                                    'filter_query': '{{column-temp-{col}}} = "OFF"'.format(col=col),
                                    'column_id': 'column-temp-{}'.format(col)
                                },
                                'backgroundColor': 'red',
                                'color': 'white'
                            } for col in range(0, 24)
                        ],
                    ),
                    html.Br(),
                    dbc.Popover(
                        [
                            dbc.PopoverHeader("Parameter error"),
                            dbc.PopoverBody("The monthly consumption must be positive or zero."),
                        ],
                        id="popover-consumption",
                        is_open=False,
                        target="table-consumption",
                        placement='top',
                    ),
                    html.H4("Monthly consumption", className="display-8"),
                    html.P("Please enter your monthly electric consumption in kWh:"),
                    dash_table.DataTable(
                        id='table-consumption',
                        columns=[{
                            'name': '{}'.format(i),
                            'id': 'column-cons-{}'.format(i)
                        } for i in range(1, 13)],
                        data=[
                            {'column-cons-1': 1200, 'column-cons-2': 1130, 'column-cons-3': 1040, 'column-cons-4': 1120,
                             'column-cons-5': 910, 'column-cons-6': 850, 'column-cons-7': 550, 'column-cons-8': 790,
                             'column-cons-9': 902, 'column-cons-10': 1020, 'column-cons-11': 1230,
                             'column-cons-12': 1187}
                        ],
                        editable=True,
                    ),
                    html.Br(),
                    html.H4("Electric equipment", className="display-8"),
                    html.Div(
                        [
                            dbc.Label("Please select all the electric appliances you run in your house:"),
                            dbc.Checklist(
                                options=[
                                    {"label": "AC cooling", "value": 1},
                                    {"label": "Electric heating system", "value": 2},
                                    {"label": "Dishwasher", "value": 3},
                                    {"label": "Washing machine", "value": 4},
                                    {"label": "Dryer", "value": 5},
                                    {"label": "Fridge", "value": 6},
                                    {"label": "Electric stove", "value": 7},
                                    {"label": "Computers", "value": 8},
                                ],
                                value=[1, 2, 3, 4, 5, 6, 7, 8],
                                id="checklist-electric-equipment",
                                inline=True,
                                input_checked_style={
                                    "backgroundColor": "#EFA31D",
                                    "borderColor": "#EFA31D",
                                },
                            ),
                        ]
                    )
                ], style={"padding": "2rem"}),
                dbc.ModalFooter(dbc.Button("Set", id="button-close-modal", color="warning")),
            ],
            id="modal-load",
            size="xl",
            is_open=False,
            backdrop="static",
            keyboard=False,
        ),
        html.Br(),
        html.Hr(style={'color': 'white'}),
        html.Div(
            [
                html.Div(id='dynamic-button-container',
                         children=[
                             dbc.Button(color="warning", id='button-simulate', children='Simulate', n_clicks=0),
                         ], className="d-grid gap-2", ),
            ],
        ),
    ],
    style=SIDEBAR_STYLE,
)

content = html.Div([
    html.H2("Results", className="display-6"),
    html.P("The results are computed for a typical year using the weather data from your location."),
    html.Hr(),
    html.Img(src=src_kwh_diagram, style={'width': '100%'}, id='image-kwh-diagram'),
    html.Br(),
    html.Br(),
    html.P("", id='description'),
    html.Br(),
    html.Hr(),
    html.Br(),
    dbc.Tooltip(
        "The self-sufficiency rate of a PV battery system indicates its ability to generate and store solar energy for a home or building without relying on the grid. A high self-sufficiency rate is crucial for maximizing the benefits of a PV battery system in terms of economic savings and environmental sustainability. ",
        target="image-autonomy",
        placement='top',
    ),
    dbc.Tooltip(
        "The electric bill reduction rate of a photovoltaic (PV) battery system refers to the amount of money that can be saved on electricity bills by generating and storing solar energy rather than relying solely on the grid. A higher electric bill reduction rate means a greater percentage of energy needs are being met by solar energy, resulting in a lower overall electricity bill.",
        target="image-electric-bill",
        placement='top',
    ),
    dbc.Tooltip(
        "The electric energy export rate of a photovoltaic (PV) battery system refers to the amount of solar energy that is generated by the system and exported back to the grid. A higher electric energy export rate means a greater percentage of solar energy generated by the system is being exported back to the grid, rather than being stored or consumed on site.",
        target="image-electric-export",
        placement='top',
    ),
    dbc.Row(
        [
            dbc.Col([html.H4(
                "Self-sufficiency:",
                className="text-center",
            ),
                html.Br(),
                html.Img(src=src_autonomy,
                         style={'width': '50%', 'margin-right': 'auto', 'margin-left': 'auto', 'display': 'block'},
                         id='image-autonomy')], style={'width': '33%'}),
            dbc.Col([html.H4(
                "Electric bill reduction:",
                className="text-center",
            ),
                html.Br(),
                html.Img(src=src_electric_bill_reduction,
                         style={'width': '50%', 'margin-right': 'auto', 'margin-left': 'auto', 'display': 'block'},
                         id='image-electric-bill')],
                style={'width': '33%'}),
            dbc.Col([html.H4(
                "Electric energy export:",
                className="text-center",
            ),
                html.Br(),
                html.Img(src=src_electric_energy_export,
                         style={'width': '50%', 'margin-right': 'auto', 'margin-left': 'auto', 'display': 'block'},
                         id='image-electric-export')],
                style={'width': '33%'}),

        ]
    ),
    html.Br(),
    html.Br(),
    dbc.Row(
        [
            dbc.Col([
                html.P("", id='description-load'),
            ], style={'width': '33%'}),
            dbc.Col([
                dcc.Graph(figure=fig_load, id='fig-load', style={'height': '50vh'}),
            ], style={'width': '66%'}),
        ]
    ),
    html.Br(),
    dbc.Row(
        [
            dbc.Col([
                dcc.Graph(figure=fig_bills, id='fig-bills', style={'height': '30vh'}),
            ], style={'width': '66%'}),
            dbc.Col([
                html.P("", id='description-bills'),
            ], style={'width': '33%'}),

        ]
    ),
    html.Hr(),
    dbc.Row(
        [
            dbc.Col(html.H4("Energy analysis", className="display-8"), width='auto'),
            dbc.Col(html.Div("")),
            dbc.Col(
                dbc.Button(color="warning", id='button-expand-fig_energy', children='Expand graph', n_clicks=0,
                           outline=True,
                           className='me-1'), width='auto'),
        ]
    ),
    dcc.Graph(figure=fig_energy, id='fig-energy', style={'height': '70vh'}),
    html.P("", id='description-energy'),
    dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Energy analysis")),
            html.Div(children=[
                dcc.Graph(figure=fig_energy, id='modal-fig-energy', style={'height': '90vh'}),
            ]),
        ],
        id="modal-fig_energy",
        fullscreen=True,
    ),
    html.Br(),
    html.Hr(),
    dbc.Row(
        [
            dbc.Col(html.H4("Financial analysis", className="display-8"), width='auto'),
            dbc.Col(html.Div("")),
            dbc.Col(
                dbc.Button(color="warning", id='button-expand-fig_finance', children='Expand graph', n_clicks=0,
                           outline=True,
                           className='me-1'), width='auto'),
        ]
    ),
    dcc.Graph(figure=fig_finance, id='fig-financial', style={'height': '70vh'}),
    html.P("", id='description-financial'),
    dbc.Row(
        [
            dbc.Col(html.H4("", className="display-8"), width='auto'),
            dbc.Col(html.Div("")),
            dbc.Col(
                dbc.Button(color="warning", id='button-expand-fig_payback', children='Expand graph', n_clicks=0,
                           outline=True,
                           className='me-1'), width='auto'),
        ]
    ),
    dcc.Graph(figure=fig_payback, id='fig-payback', style={'height': '70vh'}),
    dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Financial analysis")),
            html.Div(children=[
                dcc.Graph(figure=fig_finance, id='modal-fig-financial', style={'height': '90vh'}),
            ]),
        ],
        id="modal-fig_finance",
        fullscreen=True,
    ),
    dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Financial analysis")),
            html.Div(children=[
                dcc.Graph(figure=fig_payback, id='modal-fig-payback', style={'height': '90vh'}),
            ]),
        ],
        id="modal-fig_payback",
        fullscreen=True,
    ),
    html.Br(),
    html.Hr(),
    dbc.Row(
        [
            dbc.Col(html.H4("Daily average profiles", className="display-8"), width='auto'),
            dbc.Col(html.Div("")),
            dbc.Col(
                dbc.Button(color="warning", id='button-expand-fig_profiles', children='Expand graph', n_clicks=0,
                           outline=True,
                           className='me-1'), width='auto'),
        ]
    ),
    dcc.Graph(figure=fig_profiles, id='fig-profiles', style={'height': '70vh'}),
    html.P("", id='description-profiles'),
    dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Daily average profiles")),
            html.Div(children=[
                dcc.Graph(figure=fig_profiles, id='modal-fig-profiles', style={'height': '90vh'}),
            ]),
        ],
        id="modal-fig_profiles",
        fullscreen=True,
    ),
], style=CONTENT_STYLE)

app.layout = html.Div([dcc.Location(id="url"), sidebar, content])


@app.callback(
    Output("modal-load", "is_open"),
    [Input("button-modal-load", "n_clicks"), Input("button-close-modal", "n_clicks")],
    [State("modal-load", "is_open")],
)
def toggle_modal(n_open, n_close, is_open):
    if n_open or n_close:
        return not is_open
    return is_open


@app.callback(
    Output("modal-location", "is_open"),
    [Input("button-modal-location", "n_clicks"),
     Input("button-close-modal-location", "n_clicks"), ],
    [State("modal-location", "is_open")],
)
def toggle_modal(n_open, n_close, is_open):
    if n_open or n_close:
        return not is_open
    return is_open


@app.callback(
    Output("modal-fig_energy", "is_open"),
    [Input("button-expand-fig_energy", "n_clicks")],
    [State("modal-fig_energy", "is_open")],
)
def toggle_modal(n_open, is_open):
    if n_open:
        return not is_open
    return is_open


@app.callback(
    Output("modal-fig_finance", "is_open"),
    [Input("button-expand-fig_finance", "n_clicks")],
    [State("modal-fig_finance", "is_open")],
)
def toggle_modal(n_open, is_open):
    if n_open:
        return not is_open
    return is_open


@app.callback(
    Output("modal-fig_profiles", "is_open"),
    [Input("button-expand-fig_profiles", "n_clicks")],
    [State("modal-fig_profiles", "is_open")],
)
def toggle_modal(n_open, is_open):
    if n_open:
        return not is_open
    return is_open


@app.callback(
    Output("modal-fig_payback", "is_open"),
    [Input("button-expand-fig_payback", "n_clicks")],
    [State("modal-fig_payback", "is_open")],
)
def toggle_modal(n_open, is_open):
    if n_open:
        return not is_open
    return is_open


@app.callback([Output("layer", "children"),
               Output("input-latitude-modal", "value"),
               Output("input-longitude-modal", "value"), ],
              [Input("map", "click_lat_lng")])
def map_click(click_lat_lng):
    global latitude, longitude
    latitude = click_lat_lng[0]
    longitude = click_lat_lng[1]
    return [dl.Marker(position=click_lat_lng,
                      children=dl.Tooltip("({:.3f}, {:.3f})".format(latitude, longitude)))], round(latitude, 7), round(
        longitude, 7)


@app.callback(
    [Output("input-latitude", "value"),
     Output("input-longitude", "value"), ],
    [Input("button-close-modal-location", "n_clicks")]
)
def toggle_modal(n_clicks):
    global latitude, longitude
    if n_clicks:
        return round(latitude, 7), round(longitude, 7)


@app.callback(
    Output("tooltip-cost", "children"),
    [Input("input-pv-power", "value"),
     Input("input-battery-capacity", "value"),],
)
def tooltip_cost(pv_capacity, battery_capacity):
    if pv_capacity is not None and battery_capacity is not None:
        return "The total installation cost of your system including PV panels, batteries, inverters, installation and subsidies. A cost estimation for your system is around {} €.".format(format_number(cost_estimator(pv_capacity, battery_capacity)))
    else:
        return ''


@app.callback(
    [Output("popover-location", "is_open"),
     Output("popover-latitude", "is_open"),
     Output("popover-longitude", "is_open"),
     Output("input-latitude", "invalid"),
     Output("input-longitude", "invalid"), ],
    [Input("input-latitude", "value"),
     Input("input-longitude", "value"), ],
)
def toggle_popover(lat_val, long_val):
    global parameter_error
    popover_location = False
    popover_latitude = False
    popover_longitude = False

    input_latitude_inv = False
    input_longitude_inv = False

    if lat_val is not None:
        if lat_val < -90 or lat_val > 90:
            popover_latitude = True
            input_latitude_inv = True
            parameter_error = True
            return popover_location, popover_latitude, popover_longitude, input_latitude_inv, input_longitude_inv

    if long_val is not None:
        if long_val < -180 or long_val > 180:
            popover_longitude = True
            input_longitude_inv = True
            parameter_error = True
            return popover_location, popover_latitude, popover_longitude, input_latitude_inv, input_longitude_inv

    if not check_location(lat_val, long_val):
        popover_location = True
        input_latitude_inv = True
        input_longitude_inv = True
        parameter_error = True
        return popover_location, popover_latitude, popover_longitude, input_latitude_inv, input_longitude_inv

    parameter_error = False
    return popover_location, popover_latitude, popover_longitude, input_latitude_inv, input_longitude_inv


@app.callback(
    [Output("popover-pv-power", "is_open"),
     Output("input-pv-power", "invalid"), ],
    [Input("input-pv-power", "value")],
    [State("popover-pv-power", "is_open")],
)
def toggle_popover(value, is_open):
    global parameter_error
    if value is not None:
        if value <= 0:
            parameter_error = True
            return True, True
        else:
            parameter_error = False
            return False, False
    return is_open, is_open


@app.callback(
    [Output("popover-tilt", "is_open"),
     Output("input-tilt", "invalid"), ],
    [Input("input-tilt", "value")],
    [State("popover-tilt", "is_open")],
)
def toggle_popover(value, is_open):
    global parameter_error
    if value is not None:
        if value < 0 or value > 90:
            parameter_error = True
            return True, True
        else:
            parameter_error = False
            return False, False
    return is_open, is_open


@app.callback(
    [Output("popover-orientation", "is_open"),
     Output("input-orientation", "invalid"), ],
    [Input("input-orientation", "value")],
    [State("popover-orientation", "is_open")],
)
def toggle_popover(value, is_open):
    global parameter_error
    if value is not None:
        if value < 0 or value > 360:
            parameter_error = True
            return True, True
        else:
            parameter_error = False
            return False, False
    return is_open, is_open


@app.callback(
    [Output("popover-battery-capacity", "is_open"),
     Output("input-battery-capacity", "invalid"), ],
    [Input("input-battery-capacity", "value")],
    [State("popover-battery-capacity", "is_open")],
)
def toggle_popover(value, is_open):
    global parameter_error
    if value is not None:
        if value < 0:
            parameter_error = True
            return True, True
        else:
            parameter_error = False
            return False, False
    return is_open, is_open


@app.callback(
    [Output("popover-discharge-limit", "is_open"),
     Output("input-discharge-limit", "invalid"), ],
    [Input("input-discharge-limit", "value")],
    [State("popover-discharge-limit", "is_open")],
)
def toggle_popover(value, is_open):
    global parameter_error
    if value is not None:
        if value < 0 or value > 100:
            parameter_error = True
            return True, True
        else:
            parameter_error = False
            return False, False
    return is_open, is_open


@app.callback(
    [Output("popover-cost", "is_open"),
     Output("input-cost", "invalid"), ],
    [Input("input-cost", "value")],
    [State("popover-cost", "is_open")],
)
def toggle_popover(value, is_open):
    global parameter_error
    if value is not None:
        if value <= 0:
            parameter_error = True
            return True, True
        else:
            parameter_error = False
            return False, False
    return is_open, is_open


@app.callback(
    [Output("popover-buy-rate", "is_open"),
     Output("input-buy-rate", "invalid"), ],
    [Input("input-buy-rate", "value")],
    [State("popover-buy-rate", "is_open")],
)
def toggle_popover(value, is_open):
    global parameter_error
    if value is not None:
        if value < 0:
            parameter_error = True
            return True, True
        else:
            parameter_error = False
            return False, False
    return is_open, is_open


@app.callback(
    [Output("popover-year-built", "is_open"),
     Output("input-year-built", "invalid"), ],
    [Input("input-year-built", "value")],
    [State("popover-year-built", "is_open")],
)
def toggle_popover(value, is_open):
    global parameter_error
    if value is not None:
        if value > int(datetime.datetime.now().date().strftime("%Y")):
            parameter_error = True
            return True, True
        else:
            parameter_error = False
            return False, False
    return is_open, is_open


@app.callback(
    [Output("popover-floor-area", "is_open"),
     Output("input-floor-area", "invalid"), ],
    [Input("input-floor-area", "value")],
    [State("popover-floor-area", "is_open")],
)
def toggle_popover(value, is_open):
    global parameter_error
    if value is not None:
        if value <= 0:
            parameter_error = True
            return True, True
        else:
            parameter_error = False
            return False, False
    return is_open, is_open


@app.callback(
    [Output("popover-nb-occupants", "is_open"),
     Output("input-nb-occupants", "invalid"), ],
    [Input("input-nb-occupants", "value")],
    [State("popover-nb-occupants", "is_open")],
)
def toggle_popover(value, is_open):
    global parameter_error
    if value is not None:
        if value <= 0:
            parameter_error = True
            return True, True
        else:
            parameter_error = False
            return False, False
    return is_open, is_open


@app.callback(
    [Output("popover-nb-floor", "is_open"),
     Output("input-nb-floor", "invalid"), ],
    [Input("input-nb-floor", "value")],
    [State("popover-nb-floor", "is_open")],
)
def toggle_popover(value, is_open):
    global parameter_error
    if value is not None:
        if value <= 0:
            parameter_error = True
            return True, True
        else:
            parameter_error = False
            return False, False
    return is_open, is_open


@app.callback(
    [Output("popover-t-hot", "is_open"),
     Output("input-t-hot", "invalid"), ],
    [Input("input-t-hot", "value")],
    [State("popover-t-hot", "is_open")],
)
def toggle_popover(value, is_open):
    global parameter_error
    if value is not None:
        if value < 0 or value > 50:
            parameter_error = True
            return True, True
        else:
            parameter_error = False
            return False, False
    return is_open, is_open


@app.callback(
    [Output("popover-t-cold", "is_open"),
     Output("input-t-cold", "invalid"), ],
    [Input("input-t-cold", "value")],
    [State("popover-t-cold", "is_open")],
)
def toggle_popover(value, is_open):
    global parameter_error
    if value is not None:
        if value < 0 or value > 50:
            parameter_error = True
            return True, True
        else:
            parameter_error = False
            return False, False
    return is_open, is_open


@app.callback(
    [Output("popover-sell-rate", "is_open"),
     Output("input-sell-rate", "invalid"), ],
    [Input("input-sell-rate", "value")],
    [State("popover-sell-rate", "is_open")],
)
def toggle_popover(value, is_open):
    global parameter_error
    if value is not None:
        if value < 0:
            parameter_error = True
            return True, True
        else:
            parameter_error = False
            return False, False
    return is_open, is_open


@app.callback(
    Output("popover-occupancy-schedule", "is_open"),
    [Input("table-occupancy-schedule", "data")],
    [State("popover-occupancy-schedule", "is_open")],
)
def toggle_popover(data, is_open):
    global parameter_error
    if data is not None:
        if None in data[0].values() or '' in data[0].values():
            parameter_error = True
            return True
        if not all(float(value) >= 0 and float(value) <= 100 for value in data[0].values()):
            parameter_error = True
            return True
        else:
            parameter_error = False
            return False
    return is_open


@app.callback(
    Output("popover-temperature-schedule", "is_open"),
    [Input("table-temperature-schedule", "data")],
    [State("popover-temperature-schedule", "is_open")],
)
def toggle_popover(data, is_open):
    global parameter_error
    if data is not None:
        if None in data[0].values() or '' in data[0].values():
            parameter_error = True
            return True
        if not all(value.lower() == 'on' or value.lower() == 'off' for value in data[0].values()):
            parameter_error = True
            return True
        else:
            parameter_error = False
            return False
    return is_open


@app.callback(
    Output("popover-consumption", "is_open"),
    [Input("table-consumption", "data")],
    [State("popover-consumption", "is_open")],
)
def toggle_popover(data, is_open):
    global parameter_error
    if data is not None:
        if None in data[0].values() or '' in data[0].values():
            parameter_error = True
            return True
        if not all(float(value) >= 0 for value in data[0].values()):
            parameter_error = True
            return True
        else:
            parameter_error = False
            return False
    return is_open


@app.callback(
    [Output("modal-simulate", "is_open"),
     Output("text-computing", "children"),],
    [Input("interval-simulate", "n_intervals")],
)
def toggle_modal(n):
    global simulating
    from pre_simulator import simulation_state
    if simulating:
        return True, simulation_state
    else:
        return False, ''


@app.callback(
    [Output("fig-energy", "figure"),
     Output("modal-fig-energy", "figure"),
     Output("fig-financial", "figure"),
     Output("modal-fig-financial", "figure"),
     Output("fig-payback", "figure"),
     Output("modal-fig-payback", "figure"),
     Output("fig-profiles", "figure"),
     Output("modal-fig-profiles", "figure"),
     Output("fig-bills", "figure"),
     Output("fig-load", "figure"),
     Output("image-autonomy", "src"),
     Output("image-electric-bill", "src"),
     Output("image-electric-export", "src"),
     Output("image-kwh-diagram", "src"),
     Output("description", "children"),
     Output("description-bills", "children"),
     Output("description-load", "children"),
     Output("description-energy", "children"),
     Output("description-financial", "children"),
     Output("description-profiles", "children"),
     Output('dynamic-button-container', 'children'),
     Output('spinner-simulate', 'children'), ],
    [Input("button-simulate", "n_clicks")],
    [State("input-latitude", "value"),
     State("input-longitude", "value"),
     State("input-pv-power", "value"),
     State("input-tilt", "value"),
     State("input-orientation", "value"),
     State("input-battery-capacity", "value"),
     State("input-discharge-limit", "value"),
     State("input-buy-rate", "value"),
     State("input-sell-rate", "value"),
     State("input-cost", "value"),
     State('dynamic-button-container', 'children'), ],
)
def simulate(n_clicks, latitude, longitude, pv_capacity, tilt, orientation, battery_capacity, discharge_cutoff,
             buy_rate, sell_rate, cost, children):
    global fig_energy, fig_finance, fig_profiles, fig_payback, fig_bills, fig_load, autonomy, electric_bill_reduction, electric_energy_export, src_autonomy, src_electric_bill_reduction, src_electric_energy_export, src_kwh_diagram, simulating
    if n_clicks == 0:
        return fig_energy, fig_energy, fig_finance, fig_finance, fig_payback, fig_payback, fig_profiles, fig_profiles, fig_bills, fig_load, src_autonomy, src_electric_bill_reduction, src_electric_energy_export, src_kwh_diagram, "", "", "", "", "", "", children, ''
    else:
        # print('simulate')
        simulating = True
        battery_initial_SOC = discharge_cutoff
        output = compute_monthly_output(latitude, longitude, pv_capacity * 1000, battery_capacity * 1000,
                                        discharge_cutoff, battery_initial_SOC,
                                        load_parameters, tilt, orientation, buy_rate / 100, sell_rate / 100)

        time_start = time.time()

        fig_energy = create_fig_energy(output)
        fig_finance = create_fig_financial(output)
        fig_profiles = create_fig_profiles(output)
        fig_bills = create_fig_bills(output.annual_elec_bill_wo_sys, output.annual_elec_bill_w_sys)
        fig_load = create_fig_load(output.annual_pv_production, output.annual_import, output.annual_pv_to_batt,
                                   output.annual_export)
        fig_payback = create_fig_payback(output, cost, buy_rate, sell_rate, rate_escalation=0.10)

        autonomy = int(round(100 * (output.annual_load + output.annual_import) / output.annual_load, 0))
        savings_pv = output.annual_elec_bill_wo_sys - output.annual_import * buy_rate
        savings_export = output.annual_export * sell_rate
        electric_bill_reduction_pv = int(round(100 * savings_pv / output.annual_elec_bill_wo_sys, 0))
        electric_bill_reduction_export = int(round(100 * savings_export / output.annual_elec_bill_wo_sys, 0))
        electric_bill_reduction = int(round(
            100 * (output.annual_elec_bill_wo_sys - output.annual_elec_bill_w_sys) / output.annual_elec_bill_wo_sys, 0))
        electric_energy_export = int(round(100 * output.annual_export / output.annual_pv_production, 0))

        contents = create_fig_percent(autonomy, electric_bill_reduction, electric_energy_export)

        src_autonomy = contents[0]
        src_electric_bill_reduction = contents[1]
        src_electric_energy_export = contents[2]

        src_kwh_diagram = create_kwh_diagram(round(output.annual_pv_production, 0), round(output.annual_import, 0),
                                             round(output.annual_export, 0), round(output.annual_batt_to_system, 0),
                                             round(output.annual_load, 0))

        time_end = time.time()
        # print("Time difference between start and end of figures:", time_end - time_start)

        simulating = False

        new_element = dbc.Button(color="warning", id='button-simulate', children='Simulate', n_clicks=0)
        children.pop()
        children.append(new_element)

        description = dcc.Markdown(
            f"The **PV-Battery** system you simulated with **{format_number(pv_capacity)} kWp** of PV peak power and **{format_number(battery_capacity)} kWh** of battery generates annually **{format_number(int(round(output.annual_pv_production, 0)))} kWh** of electricity from solar energy." \
            f" Out of the **{format_number(int(round(output.annual_load, 0)))} kWh** of annual electric consumption, **{format_number(int(round(abs(output.annual_import), 0)))} kWh** had to be imported from the grid to cover your needs. " \
            f"The battery allowed to store **{format_number(int(round(output.annual_batt_to_system, 0)))} kWh** of electric energy over the whole year and returned to the house when the Sun was down. However, when the Sun was shining and the battery was full, the system could export **{format_number(int(round(output.annual_export, 0)))} kWh** back to the grid.",
            style={'font-size': '85%'})

        description_load = dcc.Markdown(f'''

            Currently, your system covers **{autonomy} %** of your electric consumption. A higher self-sufficiency rate means lower reliance on the grid, potentially lower energy costs, greater energy security, and a sense of self-reliance. A lower self-sufficiency rate means less solar energy is generated and stored, requiring more electricity from the grid. To improve it, one can try adding more PV panels if sufficient space is available or optimize their tilt and/or orientation if possible. Additionally, one can also try try to increase the battery capacity (up to a certain extent after which adding capacity does little effect on the self-sufficiency but costs significantly more). Finally, one can try to install energy-efficient appliances or adapt the heating/cooling parameters to lower the electric demand and therefore increase its self-sufficiency.

            The system exports **{electric_energy_export} %** of its electric generation. Whether a high or low electric energy export rate is desirable for a PV battery system depends on the specific goals and circumstances of the system owner. In general, a higher electric energy export rate may be desirable if the owner wants to generate additional revenue by selling excess solar energy back to the grid. However, exporting more energy than necessary may also result in a higher electricity bill for the owner if they are not eligible for compensation from their utility company.
            On the other hand, a lower electric energy export rate may be desirable if the owner wants to maximize self-consumption of solar energy and minimize reliance on the grid. By storing excess solar energy in a battery system, the owner can use the stored energy during times when solar energy is not being generated, such as at night or during cloudy days, rather than exporting it back to the grid. This can result in a higher self-sufficiency rate and lower electricity bills.
            One way to increase the export rate is to install more PV panels and optimize their tilt and orientation.
        ''', style={'font-size': '85%'})

        description_bills = dcc.Markdown(
            f"""Finally, it is possible to save up to **{format_number(round(output.annual_elec_bill_wo_sys - output.annual_elec_bill_w_sys, 2))} €** per year by installing this system, by reducing the bill from **{format_number(output.annual_elec_bill_wo_sys)} €** to **{format_number(output.annual_elec_bill_w_sys)} €** (if the electric bill is negative, it means that the revenue from the electricity export is higher than the import price). Having a low electric bill is desirable for a photovoltaic (PV) battery system because it means that the system is generating a significant portion of the energy used on site, reducing reliance on the grid and saving money on electricity costs.
                                                In addition, a low electric bill is important for achieving an optimal payback period, which can be determined by dividing the total system cost by the annual savings.
                                                Strategies to have a low payback period include sizing the system components appropriately, optimizing the energy usage, maximizing the solar energy generation and taking advantage of the incentives.""",
            style={'font-size': '85%'})

        idx_max_pv = output.monthly_pv_production.argmax()
        idx_min_pv = output.monthly_pv_production.argmin()
        months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
                  'November', 'December']

        description_energy = dcc.Markdown(
            f"""This graph shows the monthly behavior of your system in terms of energy analysis. It includes the PV electricity generation, the load consumption, the grid electricity import, the grid electricity export and the average battery state of charge (SOC).
                                                The month with the **highest PV electricity generation** is **{months[idx_max_pv]}** for which {format_number(output.monthly_pv_production.iloc[idx_max_pv])} kWh have been generated. And the month with the **lowest PV electricity generation** is **{months[idx_min_pv]}** for which {format_number(output.monthly_pv_production.iloc[idx_min_pv])} kWh have been generated. """,
            style={'font-size': '85%'})

        description_financial = dcc.Markdown('''
            
                The graph above shows the monthly behavior of your system in terms of financial analysis. It includes the electric bill with and without the PV-Battery system, the electricity export income and the cumulated savings over each month.
            
                The graph below indicates the payback period of the system, i.e. the time it takes for the savings generated by the system to offset the inital cost of installation, and the net value after 25 years, which is the total savings generated by the system minus the total installation cost (if the value is negative, it means that after 25 years, the total savings could not offset the total installation cost). In this case, a period of 25 years is analyzed with three different electricity import price escalation rate scenarios. The first scenario assumes a 0% escalation per year, meaning the electricity import price remains constant, the second one assumes a 4% escalation per year, meaning the electricity import price increases by 4% every year, and a last scenario with an 8% escalation per year. A shorter payback period means that the savings generated by the system will offset the initial cost of installation more quickly, allowing homeowners and building managers to recoup their investment and enjoy greater savings over the lifetime of the system. A longer payback period may mean that the savings generated by the system will take more time to offset the initial cost of installation, but can still result in significant savings over the long term. It is worth noting that, to reduce the payback period, one should look for a system without or with a small battery storage solution as this component largely increases the cost per kWh of the system.
            ''', style={'font-size': '85%'})

        description_profiles = dcc.Markdown(
            f"""This graph shows the daily average profiles of the system. For each month of the year, an average day is computed to allow a more precise analysis of how the system is behaving on an hourly scale. It includes the PV electricity generation, the load consumption, the grid electricity exchange (if the value is negative, the system imports from the grid and if the value is positive, it exports to the grid) and the battery state of charge (SOC). """,
            style={'font-size': '85%'})

        return fig_energy, fig_energy, fig_finance, fig_finance, fig_payback, fig_payback, fig_profiles, fig_profiles, fig_bills, fig_load, src_autonomy, src_electric_bill_reduction, src_electric_energy_export, src_kwh_diagram, description, description_bills, description_load, description_energy, description_financial, description_profiles, children, ''


@app.callback(
    [Output('spinner-load', 'children'), ],
    [Input("button-close-modal", "n_clicks")],
    [State("input-year-built", "value"),
     State("input-floor-area", "value"),
     State("input-nb-occupants", "value"),
     State("input-nb-floor", "value"),
     State("table-occupancy-schedule", "data"),
     State("input-t-hot", "value"),
     State("input-t-cold", "value"),
     State("table-temperature-schedule", "data"),
     State("table-consumption", "data"),
     State('checklist-electric-equipment', 'value'), ],
)
def compute_load(n_clicks, year_built, floor_area, occupants, floors, occ_schedule, t_heat, t_cool,
                 t_sched, monthly_util, equipment):
    global load_parameters
    if n_clicks:
        load_parameters.year_built = year_built
        load_parameters.floor_area = floor_area
        load_parameters.occupants = occupants
        load_parameters.floors = floors
        load_parameters.t_heat = t_heat
        load_parameters.t_cool = t_cool

        load_parameters.occ_schedule = [float(i) / 100 for i in list(occ_schedule[0].values())]
        load_parameters.monthly_util = [float(i) for i in list(monthly_util[0].values())]

        t_sched_list = []
        for val in list(t_sched[0].values()):
            if val.lower() == 'on':
                t_sched_list.append(1.0)
            else:
                t_sched_list.append(0.0)

        load_parameters.t_sched = t_sched_list

        load_parameters.en_cool = 0.0
        load_parameters.en_heating = 0.0
        load_parameters.en_dishwasher = 0.0
        load_parameters.en_washing_machine = 0.0
        load_parameters.en_dryer = 0.0
        load_parameters.en_fridge = 0.0
        load_parameters.en_stove = 0.0
        load_parameters.en_misc = 0.0

        if 1 in equipment:
            load_parameters.en_cool = 1.0
        if 2 in equipment:
            load_parameters.en_heating = 1.0
        if 3 in equipment:
            load_parameters.en_dishwasher = 1.0
        if 4 in equipment:
            load_parameters.en_washing_machine = 1.0
        if 5 in equipment:
            load_parameters.en_dryer = 1.0
        if 6 in equipment:
            load_parameters.en_fridge = 1.0
        if 7 in equipment:
            load_parameters.en_stove = 1.0
        if 8 in equipment:
            load_parameters.en_misc = 1.0

    return [""]


@app.callback(
    Output('button-simulate', 'disabled'),
    [Input('button-simulate', 'n_clicks'),
     Input("interval-simulate", "n_intervals")]
)
def disabled(n_clicks, n):
    triggered_id = ctx.triggered_id
    if triggered_id == 'button-simulate':
        return hide_newbutton(n_clicks)
    elif triggered_id == 'interval-simulate':
        return disabled_error(n)


def hide_newbutton(n_clicks):
    if n_clicks == 0:
        return False
    else:
        return True


def disabled_error(n):
    global parameter_error
    if parameter_error:
        return True
    else:
        return False


if __name__ == '__main__':
    # app.run_server(port=8051, debug=True)
    app.run_server(debug=False)
