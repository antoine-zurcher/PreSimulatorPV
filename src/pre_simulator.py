import pvlib
import pandas as pd
from pvlib.pvsystem import PVSystem
import PySAM.Belpe as bp
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from base64 import b64encode
import plotly.io as pio
import time
from copy import deepcopy
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import requests

temperature_model_parameters = TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']
pio.orca.config.executable = './orca/orca.exe'
pio.orca.config.save()

simulation_state = ''


class LoadParameters:
    def __init__(self, monthly_util, occ_schedule, occupants, retrofitted, floors, t_cool, t_heat, t_sched, year_built,
                 floor_area, en_cool, en_dishwasher, en_dryer, en_fridge, en_heating, en_misc, en_stove,
                 en_washing_machine):
        self.monthly_util = monthly_util
        self.occ_schedule = occ_schedule
        self.occupants = occupants
        self.retrofitted = retrofitted
        self.floors = floors
        self.t_cool = t_cool
        self.t_heat = t_heat
        self.t_sched = t_sched
        self.year_built = year_built
        self.floor_area = floor_area
        self.en_cool = en_cool
        self.en_dishwasher = en_dishwasher
        self.en_dryer = en_dryer
        self.en_fridge = en_fridge
        self.en_heating = en_heating
        self.en_misc = en_misc
        self.en_stove = en_stove
        self.en_washing_machine = en_washing_machine

    def __eq__(self, other):
        if not isinstance(other, LoadParameters):
            # don't attempt to compare against unrelated types
            return NotImplemented

        return self.monthly_util == other.monthly_util and self.occ_schedule == other.occ_schedule and self.occupants == other.occupants and self.retrofitted == other.retrofitted and self.floors == other.floors and self.t_cool == other.t_cool and self.t_heat == other.t_heat and self.t_sched == other.t_sched and self.year_built == other.year_built and self.floor_area == other.floor_area and self.en_cool == other.en_cool and self.en_dishwasher == other.en_dishwasher and self.en_dryer == other.en_dryer and self.en_fridge == other.en_fridge and self.en_heating == other.en_heating and self.en_misc == other.en_misc and self.en_stove == other.en_stove and self.en_washing_machine == other.en_washing_machine


class OutputResults:
    def __init__(self, annual_pv_production, annual_batt_to_system, annual_pv_to_batt, annual_energy_yield, annual_load,
                 annual_import, annual_export,
                 annual_elec_bill_wo_sys, annual_elec_bill_w_sys, annual_sell, annual_savings,
                 monthly_pv_production, monthly_load, monthly_import, monthly_export, monthly_soc,
                 monthly_elec_bill_wo_sys, monthly_elec_bill_w_sys, monthly_sell, monthly_cumulated_savings,
                 profiles):
        self.annual_pv_production = annual_pv_production
        self.annual_batt_to_system = annual_batt_to_system
        self.annual_pv_to_batt = annual_pv_to_batt
        self.annual_energy_yield = annual_energy_yield
        self.annual_load = annual_load
        self.annual_import = annual_import
        self.annual_export = annual_export
        self.annual_savings = annual_savings
        self.annual_elec_bill_wo_sys = annual_elec_bill_wo_sys
        self.annual_elec_bill_w_sys = annual_elec_bill_w_sys
        self.annual_sell = annual_sell
        self.monthly_pv_production = monthly_pv_production
        self.monthly_load = monthly_load
        self.monthly_import = monthly_import
        self.monthly_export = monthly_export
        self.monthly_soc = monthly_soc
        self.monthly_elec_bill_wo_sys = monthly_elec_bill_wo_sys
        self.monthly_elec_bill_w_sys = monthly_elec_bill_w_sys
        self.monthly_sell = monthly_sell
        self.monthly_cumulated_savings = monthly_cumulated_savings
        self.profiles = profiles


old_latitude = float('nan')
old_longitude = float('nan')
old_pv_capacity = float('nan')
old_tilt = float('nan')
old_orientation = float('nan')
old_weather = None
old_load = None
old_load_parameters = LoadParameters(
    monthly_util=[1700, 1400, 1000, 700, 600, 700, 600, 600, 800, 1000, 1600, 2000],  # kWh
    occ_schedule=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
                  1.0, 1.0, 1.0, 1.0],  # frac
    occupants=float('nan'),
    retrofitted=float('nan'),
    floors=float('nan'),
    t_cool=float('nan'),  # °C
    t_heat=float('nan'),  # °C
    t_sched=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
             1.0, 1.0, 1.0],  # on/off
    year_built=float('nan'),
    floor_area=float('nan'),  # m2
    en_cool=float('nan'),
    en_dishwasher=float('nan'),
    en_dryer=float('nan'),
    en_fridge=float('nan'),
    en_heating=float('nan'),
    en_misc=float('nan'),
    en_stove=float('nan'),
    en_washing_machine=float('nan'),
)


def celsius_to_fahrenheit(celsius):
    return (celsius * 9 / 5) + 32


def sqm_to_sqft(sqm):
    sqft = sqm * 10.7639
    return sqft


def format_number(number):
    return '{:,}'.format(number).replace(',', ' ')


def cost_estimator(pv_capacity, battery_capacity):
    price_kwh_battery = 800
    price_kw_pv = 1000 * 5.102 * pv_capacity ** (-0.285)
    price_total = price_kw_pv * pv_capacity + price_kwh_battery * battery_capacity
    return round(price_total / 500) * 500


def compute_load(latitude, longitude, load_parameters):
    weather_data_epw = pvlib.iotools.get_pvgis_tmy(latitude, longitude, outputformat='epw', map_variables=True)

    template_tmy_load = pd.read_csv('template_tmy_load.csv', header=None)
    template_tmy_load.iloc[3:, 0] = weather_data_epw[0]['year']
    template_tmy_load.iloc[3:, 1] = weather_data_epw[0]['month']
    template_tmy_load.iloc[3:, 2] = weather_data_epw[0]['day']
    template_tmy_load.iloc[3:, 3] = weather_data_epw[0]['hour']
    template_tmy_load.iloc[3:, 4] = weather_data_epw[0]['minute']
    template_tmy_load.iloc[3:, 9] = weather_data_epw[0]['temp_air']
    template_tmy_load.iloc[3:, 8] = weather_data_epw[0]['temp_dew']
    template_tmy_load.iloc[3:, 10] = weather_data_epw[0]['atmospheric_pressure'] / 100
    template_tmy_load.iloc[3:, 7] = weather_data_epw[0]['ghi']
    template_tmy_load.iloc[3:, 5] = weather_data_epw[0]['dni']
    template_tmy_load.iloc[3:, 6] = weather_data_epw[0]['dhi']
    template_tmy_load.iloc[3:, 11] = weather_data_epw[0]['wind_direction']
    template_tmy_load.iloc[3:, 12] = weather_data_epw[0]['wind_speed']

    template_tmy_load.to_csv('tmy_load.csv', index=False, header=False)

    belpe_model = bp.default('PVBatteryResidential')
    belpe_model.LoadProfileEstimator.en_belpe = 1.0
    belpe_model.LoadProfileEstimator.Occ_Schedule = load_parameters.occ_schedule
    belpe_model.LoadProfileEstimator.Occupants = load_parameters.occupants
    belpe_model.LoadProfileEstimator.Retrofits = load_parameters.retrofitted
    belpe_model.LoadProfileEstimator.Stories = load_parameters.floors
    belpe_model.LoadProfileEstimator.TCool = celsius_to_fahrenheit(load_parameters.t_cool)
    belpe_model.LoadProfileEstimator.TCoolSB = celsius_to_fahrenheit(load_parameters.t_cool)
    belpe_model.LoadProfileEstimator.THeat = celsius_to_fahrenheit(load_parameters.t_heat)
    belpe_model.LoadProfileEstimator.THeatSB = celsius_to_fahrenheit(load_parameters.t_heat)
    belpe_model.LoadProfileEstimator.T_Sched = load_parameters.t_sched
    belpe_model.LoadProfileEstimator.YrBuilt = load_parameters.year_built
    belpe_model.LoadProfileEstimator.en_cool = load_parameters.en_cool
    belpe_model.LoadProfileEstimator.en_dish = load_parameters.en_dishwasher
    belpe_model.LoadProfileEstimator.en_dry = load_parameters.en_dryer
    belpe_model.LoadProfileEstimator.en_fridge = load_parameters.en_fridge
    belpe_model.LoadProfileEstimator.en_heat = load_parameters.en_heating
    belpe_model.LoadProfileEstimator.en_mels = load_parameters.en_misc
    belpe_model.LoadProfileEstimator.en_range = load_parameters.en_stove
    belpe_model.LoadProfileEstimator.en_wash = load_parameters.en_washing_machine
    belpe_model.LoadProfileEstimator.floor_area = sqm_to_sqft(load_parameters.floor_area)
    belpe_model.LoadProfileEstimator.solar_resource_file = 'tmy_load.csv'

    belpe_model.LoadProfileEstimator.Monthly_util = load_parameters.monthly_util
    belpe_model.execute()
    load = belpe_model.LoadProfileEstimator.load
    load = tuple(map(lambda x: x * 1000, load))

    return load


def check_location(latitude, longitude):
    outputformat = 'json'
    usehorizon = True
    userhorizon = None
    startyear = None
    endyear = None
    url = 'https://re.jrc.ec.europa.eu/api/'
    map_variables = True
    timeout = 30
    params = {'lat': latitude, 'lon': longitude, 'outputformat': outputformat}
    # pvgis only likes 0 for False, and 1 for True, not strings, also the
    # default for usehorizon is already 1 (ie: True), so only set if False
    if not usehorizon:
        params['usehorizon'] = 0
    if userhorizon is not None:
        params['userhorizon'] = ','.join(str(x) for x in userhorizon)
    if startyear is not None:
        params['startyear'] = startyear
    if endyear is not None:
        params['endyear'] = endyear
    res = requests.get(url + 'tmy', params=params, timeout=timeout)
    if 'message' in res.json().keys():
        return False
    else:
        return True


def compute_system(row, batt_cap_prev, battery_capacity_real):
    diff = batt_cap_prev + row['NetPower']
    if diff >= 0.0:
        if diff > battery_capacity_real:
            row['BatteryCapacity'] = battery_capacity_real
            row['Export'] = diff - battery_capacity_real
            row['ToFromBattery'] = row['NetPower'] - (
                    diff - battery_capacity_real)
        else:
            row['BatteryCapacity'] = batt_cap_prev + row['NetPower']
            row['ToFromBattery'] = row['NetPower']
    else:
        row['Import'] = diff
        row['BatteryCapacity'] = batt_cap_prev + row['NetPower'] - diff
        row['ToFromBattery'] = row['NetPower'] - diff


def compute_monthly_output(latitude, longitude, pv_capacity, battery_capacity, discharge_cutoff, battery_initial_SOC,
                           load_parameters, tilt, orientation, buy_rate, sell_rate):
    global old_latitude, old_longitude, old_load_parameters, old_weather, old_load, old_tilt, old_orientation, old_pv_capacity, simulation_state
    time_start = time.time()
    battery_capacity_real = battery_capacity * (100 - discharge_cutoff) / 100

    if latitude == old_latitude and longitude == old_longitude and pv_capacity == old_pv_capacity and tilt == old_tilt and orientation == old_orientation:
        results = old_weather
        old_latitude = latitude
        old_longitude = longitude
        old_pv_capacity = pv_capacity
        old_tilt = tilt
        old_orientation = orientation
    else:
        simulation_state = 'Computing PV energy output from weather data...'
        location = Location(latitude, longitude)
        weather_data = pvlib.iotools.get_pvgis_tmy(latitude, longitude, map_variables=True)

        pvwatts_system = PVSystem(surface_tilt=tilt, surface_azimuth=orientation,
                                  module_parameters={'pdc0': pv_capacity, 'gamma_pdc': -0.004},
                                  inverter_parameters={'pdc0': pv_capacity},
                                  temperature_model_parameters=temperature_model_parameters)

        mc = ModelChain(pvwatts_system, location,
                        aoi_model='physical', spectral_model='no_loss')

        weather = pd.DataFrame(columns=['ghi', 'dni', 'dhi', 'temp_air', 'wind_speed'],
                               index=weather_data[0].index.values)

        weather['temp_air'] = weather_data[0]['temp_air'].values
        weather['wind_speed'] = weather_data[0]['wind_speed'].values
        weather['ghi'] = weather_data[0]['ghi'].values
        weather['dni'] = weather_data[0]['dni'].values
        weather['dhi'] = weather_data[0]['dhi'].values

        mc.run_model(weather)

        results = weather
        results['DCOutput'] = mc.results.dc.values

        old_weather = results
        old_latitude = latitude
        old_longitude = longitude
        old_pv_capacity = pv_capacity
        old_tilt = tilt
        old_orientation = orientation

    if load_parameters == old_load_parameters:
        results['Load'] = old_load
        old_load_parameters = deepcopy(load_parameters)
    else:
        simulation_state = 'Computing load consumption profile...'
        load = compute_load(latitude, longitude, load_parameters)
        results['Load'] = load
        old_load = load
        old_load_parameters = deepcopy(load_parameters)

    simulation_state = 'Computing grid import and export...'
    results['NetPower'] = results['DCOutput'] - results['Load']
    results['ToFromBattery'] = 0
    results['BatteryCapacity'] = 0
    results['Import'] = 0
    results['Export'] = 0
    results = results.reset_index()
    results = results.rename(columns={'index': 'date'})
    batt_cap_prev = 0.0

    time_weather = time.time()


    if battery_capacity:
        for i in range(len(results)):
            diff = batt_cap_prev + results.loc[i, 'NetPower']
            if diff >= 0.0:
                if diff > battery_capacity_real:
                    results.loc[i, 'BatteryCapacity'] = battery_capacity_real
                    results.loc[i, 'Export'] = diff - battery_capacity_real
                    results.loc[i, 'ToFromBattery'] = results.loc[i, 'NetPower'] - (
                            diff - battery_capacity_real)
                    batt_cap_prev = results.loc[i, 'BatteryCapacity']
                else:
                    results.loc[i, 'BatteryCapacity'] = batt_cap_prev + results.loc[i, 'NetPower']
                    results.loc[i, 'ToFromBattery'] = results.loc[i, 'NetPower']
                    batt_cap_prev = results.loc[i, 'BatteryCapacity']
            else:
                results.loc[i, 'Import'] = diff
                results.loc[i, 'BatteryCapacity'] = batt_cap_prev + results.loc[i, 'NetPower'] - diff
                results.loc[i, 'ToFromBattery'] = results.loc[i, 'NetPower'] - diff
                batt_cap_prev = results.loc[i, 'BatteryCapacity']
    else:
        results['Import'] = results['NetPower'].apply(lambda x: min(0.0, x))
        results['Export'] = results['NetPower'].apply(lambda x: max(0.0, x))

    results['SOC'] = float('inf')
    if battery_capacity:
        results['SOC'] = results['BatteryCapacity'].apply(
            lambda x: 100 * (x + (battery_capacity - battery_capacity_real)) / battery_capacity)
    results['Buy'] = results['Import'].apply(lambda x: x * buy_rate / 1000)
    results['Sell'] = results['Export'].apply(lambda x: x * sell_rate / 1000)
    results['Grid'] = results['Import'] + results['Export']

    time_results = time.time()

    monthly_results = results.groupby(results.date.dt.month).sum(numeric_only=True)
    monthly_results_mean = results.groupby(results.date.dt.month).mean(numeric_only=True)

    months = [m for m in range(1, 13)]
    profiles = {}
    for m in months:
        # Create a temporary dataframe with only the data of the current month
        temp_df = results[(results.date.dt.month >= m) & (
                results.date.dt.month <= m)]
        # Calculate the average daily profile
        avg_daily_profile = temp_df.groupby(temp_df.date.dt.hour).mean(numeric_only=True).round(2)
        # Store the results in the dictionary
        profiles[f'{m}'] = avg_daily_profile

    annual_pv_production = round(results['DCOutput'].sum() / 1000, 2)
    annual_batt_to_system = round(results[results['ToFromBattery'] > 0]['ToFromBattery'].sum() / 1000, 2)
    annual_pv_to_batt = round(results[results['ToFromBattery'] < 0]['ToFromBattery'].sum() / 1000, 2)
    annual_energy_yield = round(annual_pv_production / (pv_capacity / 1000), 2)
    annual_load = round(results['Load'].sum() / 1000, 2)
    annual_import = round(results['Import'].sum() / 1000, 2)
    annual_export = round(results['Export'].sum() / 1000, 2)
    annual_elec_bill_wo_sys = round(annual_load * buy_rate, 2)
    annual_elec_bill_w_sys = round(abs(annual_import) * buy_rate - annual_export * sell_rate, 2)
    annual_sell = round(annual_export * sell_rate, 2)
    annual_savings = round(annual_elec_bill_wo_sys - annual_elec_bill_w_sys, 2)
    monthly_pv_production = (monthly_results['DCOutput'] / 1000).round(0)
    monthly_load = (monthly_results['Load'] / 1000).round(0)
    monthly_import = (monthly_results['Import'] / 1000).round(0)
    monthly_export = (monthly_results['Export'] / 1000).round(0)
    monthly_soc = (monthly_results_mean['SOC']).round(2)
    monthly_elec_bill_wo_sys = (monthly_load * buy_rate).round(2)
    monthly_elec_bill_w_sys = (abs(monthly_import) * buy_rate - monthly_export * sell_rate).round(2)
    monthly_sell = (monthly_export * sell_rate).round(2)
    monthly_savings = (monthly_elec_bill_wo_sys - monthly_elec_bill_w_sys).round(2)
    monthly_cumulated_savings = (monthly_savings.cumsum()).round(2)

    output = OutputResults(annual_pv_production, annual_batt_to_system, annual_pv_to_batt, annual_energy_yield,
                           annual_load,
                           annual_import, annual_export,
                           annual_elec_bill_wo_sys, annual_elec_bill_w_sys, annual_sell, annual_savings,
                           monthly_pv_production, monthly_load, monthly_import, monthly_export, monthly_soc,
                           monthly_elec_bill_wo_sys, monthly_elec_bill_w_sys, monthly_sell, monthly_cumulated_savings,
                           profiles)
    time_end = time.time()
    simulation_state = 'Building graphs...'
    # print("Time difference between start and end:", time_end - time_start)
    # print("Time difference between start and weather:", time_weather - time_start)
    # print("Time difference between weather and results:", time_results - time_weather)
    # print("Time difference between results and end:", time_end - time_results)

    return output


def create_fig_energy(output):
    x = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # pio.templates.default = 'seaborn'

    fig = make_subplots(specs=[[{'secondary_y': True}]])

    step_kwh = 500

    min_value = output.monthly_import.min()
    min_value = -(abs(min_value) // step_kwh + bool(abs(min_value) % step_kwh)) * step_kwh

    max_value = max(output.monthly_pv_production.max(), output.monthly_load.max(), output.monthly_export.max())
    max_value = (abs(max_value) // step_kwh + bool(abs(max_value) % step_kwh)) * step_kwh

    nb_steps_min = int(abs(min_value) / step_kwh)
    step_min_percent = (100 / nb_steps_min)
    nb_steps_max = int(max_value / step_kwh)
    step_max_percent = (100 / nb_steps_max)

    first_axis_tickers = [*range(int(min_value), int(max_value + 1), int(step_kwh))]
    second_axis_tickers = []
    count = -100
    for i in range(nb_steps_min + nb_steps_max + 1):
        second_axis_tickers.append(count)
        if count < 0:
            count += step_min_percent
        else:
            count += step_max_percent

        range(int(min_value), int(max_value + 1), int(step_kwh))

    fig.add_trace(go.Bar(
        visible=True,
        x=x,
        y=output.monthly_pv_production,
        name='PV production (kWh)',
        customdata=['{}'.format('PV production') for i in range(len(x))],
        hovertemplate='<b>%{customdata} </b> <br>%{x}: %{y} kWh <extra></extra>',
        marker_color='#EFA31D',
    ), secondary_y=False, )

    fig.add_trace(go.Bar(
        visible=True,
        x=x,
        y=output.monthly_load,
        name='Load (kWh)',
        customdata=['{}'.format('Load') for i in range(len(x))],
        hovertemplate='<b>%{customdata} </b> <br>%{x}: %{y} kWh <extra></extra>',
        marker_color='#636EFA',
    ), secondary_y=False, )

    fig.add_trace(go.Bar(
        visible=True,
        x=x,
        y=abs(output.monthly_import),
        name='Grid import (kWh)',
        customdata=['{}'.format('Grid import') for i in range(len(x))],
        hovertemplate='<b>%{customdata} </b> <br>%{x}: %{y} kWh <extra></extra>',
        marker_color='#EF553B',
    ), secondary_y=False, )

    fig.add_trace(go.Bar(
        visible=True,
        x=x,
        y=output.monthly_export,
        name='Grid export (kWh)',
        customdata=['{}'.format('Grid export') for i in range(len(x))],
        hovertemplate='<b>%{customdata} </b> <br>%{x}: %{y} kWh <extra></extra>',
        marker_color='#00CC96',
    ), secondary_y=False, )

    fig.add_trace(go.Scatter(
        visible=True,
        x=x,
        y=output.monthly_soc,
        name='Battery SOC (%)',
        customdata=['{}'.format('Battery SOC') for i in range(len(x))],
        hovertemplate='<b>%{customdata} </b> <br>%{x}: %{y} % <extra></extra>',
        line_shape='spline',
        mode='lines',
        line=dict(color='#AB63FA', dash='dash'),
    ), secondary_y=True, )

    fig.update_xaxes(title_text='Months')
    fig.update_yaxes(title_text='Energy (kWh)', secondary_y=False)
    fig.update_yaxes(title_text='SOC (%)', secondary_y=True)
    # fig.update_layout(yaxis1_tickvals=first_axis_tickers, yaxis2_tickvals=second_axis_tickers)
    # fig.update_layout(yaxis1_range=[min(first_axis_tickers), max(first_axis_tickers)],
    #                  yaxis2_range=[min(second_axis_tickers), max(second_axis_tickers)])

    # fig.update_layout(paper_bgcolor="#002B36")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)")

    return fig

    # fig.show()


def create_fig_financial(output):
    x = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    fig = go.Figure()

    fig.add_trace(go.Bar(
        visible=True,
        x=x,
        y=output.monthly_elec_bill_wo_sys,
        name='Electric bill w/o system',
        customdata=['{}'.format('Electric bill w/o system') for i in range(len(x))],
        hovertemplate='<b>%{customdata} </b> <br>%{x}: %{y} € <extra></extra>',
    ))

    fig.add_trace(go.Bar(
        visible=True,
        x=x,
        y=output.monthly_elec_bill_w_sys,
        name='Electric bill w/ system',
        customdata=['{}'.format('Electric bill w/ system') for i in range(len(x))],
        hovertemplate='<b>%{customdata} </b> <br>%{x}: %{y} € <extra></extra>',
    ))

    fig.add_trace(go.Bar(
        visible=True,
        x=x,
        y=output.monthly_sell,
        name='Electricity export income',
        customdata=['{}'.format('Electricity export income') for i in range(len(x))],
        hovertemplate='<b>%{customdata} </b> <br>%{x}: %{y} € <extra></extra>',
    ))

    fig.add_trace(go.Scatter(
        visible=True,
        x=x,
        y=output.monthly_cumulated_savings,
        name='Cumulated savings',
        customdata=['{}'.format('Cumulated savings') for i in range(len(x))],
        hovertemplate='<b>%{customdata} </b> <br>%{x}: %{y} € <extra></extra>',
        mode='lines',
        line_shape='spline',
    ))

    fig.update_xaxes(title_text='Months')
    fig.update_yaxes(title_text='Euros')
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)")
    fig.update_layout(uniformtext_mode='hide')

    return fig

    # fig.show()


def create_fig_payback(output, cost, buy_rate, sell_rate, rate_escalation):
    rates = [0, 0.04, 0.08]

    fig = make_subplots(rows=len(rates), cols=1, subplot_titles=(
        'Escalation: 0% per year', 'Escalation: 4% per year', 'Escalation: 8% per year'))
    buy_rate = buy_rate / 100
    sell_rate = sell_rate / 100
    tickers_year = [0, 5, 10, 15, 20, 25]

    for j in range(len(rates)):
        x = [*range(0, 26)]
        y = []
        color = []
        current_cost = -cost
        idx_payback = 0

        for i in range(len(x)):
            if i == 0:
                y.append(round(current_cost, 0))
                color.append('#EF553B')
                idx_payback += 1
            else:
                current_buy_rate = buy_rate * (1 + rates[j]) ** i
                savings = output.annual_load * current_buy_rate - (
                        abs(output.annual_import) * current_buy_rate - output.annual_export * sell_rate)
                y.append(round(current_cost + savings, 0))
                if current_cost + savings > 0:
                    color.append('#00CC96')
                else:
                    color.append('#EF553B')
                    idx_payback += 1
                current_cost = current_cost + savings

        fig.add_trace(go.Bar(
            visible=True,
            x=x,
            y=y,
            marker_color=color,
            name='Payback',
            customdata=['{}'.format('Payback') for i in range(len(x))],
            hovertemplate='<b>%{customdata} </b> <br>Year %{x}: %{y} € <extra></extra>',
            showlegend=False,
        ), row=j + 1, col=1, )

        if y[-1] > 0:
            fig.add_vline(x=idx_payback, line_width=2, line_dash="dash", line_color="black",
                          annotation_text=" Payback year: <b>{}</b>".format(idx_payback),
                          annotation_position="bottom right", row=j + 1, col=1)

        fig.add_annotation(text="Net value: <b>{} €</b>".format(format_number(int(y[-1]))),
                           xref="paper", yref="paper",
                           x=29, y=0, showarrow=False, row=j + 1, col=1)

    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)")
    fig.update_layout(uniformtext_mode='hide')
    fig['layout']['xaxis3']['title'] = 'Year'
    fig['layout']['yaxis2']['title'] = 'Value (€)'

    fig['layout']['xaxis1']['tickvals'] = tickers_year
    fig['layout']['xaxis2']['tickvals'] = tickers_year
    fig['layout']['xaxis3']['tickvals'] = tickers_year

    fig['data'][0]['marker']['line']['color'] = 'black'
    fig['data'][0]['marker']['line']['width'] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                                 0, 2]
    fig['data'][1]['marker']['line']['color'] = 'black'
    fig['data'][1]['marker']['line']['width'] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                                 0, 2]
    fig['data'][2]['marker']['line']['color'] = 'black'
    fig['data'][2]['marker']['line']['width'] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                                 0, 2]

    return fig

    # fig.show()


def create_fig_profiles(output):
    rows = 3
    cols = 4
    tickers_hour = ['12:00']
    fig = make_subplots(rows=rows, cols=cols, subplot_titles=(
        'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November',
        'December'), specs=[
        [{'secondary_y': True}, {'secondary_y': True}, {'secondary_y': True}, {'secondary_y': True}],
        [{'secondary_y': True}, {'secondary_y': True}, {'secondary_y': True}, {'secondary_y': True}],
        [{'secondary_y': True}, {'secondary_y': True}, {'secondary_y': True}, {'secondary_y': True}]])
    x = ['00:00', '01:00', '02:00', '03:00', '04:00', '05:00', '06:00', '07:00', '08:00', '09:00', '10:00', '11:00',
         '12:00', '13:00', '14:00', '15:00', '16:00', '17:00', '18:00', '19:00', '20:00', '21:00', '22:00', '23:00']

    for row in range(1, rows + 1):
        for col in range(1, cols + 1):
            month = (row - 1) * 4 + col
            if month == 1:
                show_legend = True
            else:
                show_legend = False

            fig.add_trace(go.Scatter(
                visible=True,
                x=x,
                y=output.profiles[str(month)]['DCOutput'].round(0),
                name='PV (W)',
                showlegend=show_legend,
                legendgroup='pv',
                line=dict(color='orange'),
                mode='lines',
                line_shape='spline',
            ), row=row,
                col=col,
                secondary_y=False)

            fig.add_trace(go.Scatter(
                visible=True,
                x=x,
                y=output.profiles[str(month)]['Load'].round(0),
                name='Load (W)',
                showlegend=show_legend,
                legendgroup='load',
                line=dict(color='#636EFA'),
                mode='lines',
                line_shape='spline',
            ), row=row,
                col=col,
                secondary_y=False)

            fig.add_trace(go.Scatter(
                visible=True,
                x=x,
                y=output.profiles[str(month)]['Grid'].round(0),
                name='Grid (W)',
                showlegend=show_legend,
                legendgroup='grid',
                line=dict(color='#EF553B'),
                mode='lines',
                line_shape='spline',
            ), row=row,
                col=col,
                secondary_y=False)

            fig.add_trace(go.Scatter(
                visible=True,
                x=x,
                y=output.profiles[str(month)]['SOC'].round(2),
                name='BATT (%)',
                showlegend=show_legend,
                legendgroup='batt',
                line=dict(color='#AB63FA', dash='dash'),
                mode='lines',
                line_shape='spline',
            ), row=row,
                col=col,
                secondary_y=True, )

            fig['layout']['xaxis{}'.format(month)]['tickvals'] = tickers_hour
            fig['layout']['yaxis{}'.format(month * 2)]['showgrid'] = False

    fig['layout']['yaxis9']['title'] = 'Power (W)'
    fig['layout']['yaxis16']['title'] = 'SOC (%)'
    fig['layout']['xaxis9']['title'] = 'Hour'
    fig['layout']['xaxis10']['title'] = 'Hour'
    fig['layout']['xaxis11']['title'] = 'Hour'
    fig['layout']['xaxis12']['title'] = 'Hour'
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)")
    fig.update_layout(hovermode='x unified')

    return fig

    # fig.show()


def create_fig_percent(autonomy, bill_reduction, elec_export):
    autonomy = int(autonomy)
    bill_reduction = int(bill_reduction)
    elec_export = int(elec_export)
    values = [autonomy, bill_reduction, elec_export]
    names = ['autonomy', 'bill_reduction', 'elec_export']
    contents = []
    i = 0

    for value in values:
        fig = go.Figure(data=go.Pie(values=[min(int(value), 100), 100 - min(int(value), 100)],
                                    hole=0.8,
                                    sort=False))
        fig.update_traces(hoverinfo='none',
                          textinfo='none',
                          marker=dict(colors=['#EFA31D', '#D9D9D9']))
        fig.update_layout(showlegend=False)
        if i == 1:
            fig.add_annotation(x=0.5, y=0.5,

                               text='-' + str(value),
                               font=dict(size=140, family='Arial',
                                         color='black'),
                               showarrow=False)
        else:
            fig.add_annotation(x=0.5, y=0.5,
                               text=str(value),
                               font=dict(size=140, family='Arial',
                                         color='black'),
                               showarrow=False)
        fig.add_annotation(x=0.5, y=0.1,
                           text='%',
                           font=dict(size=60, family='Arial',
                                     color='black'),
                           showarrow=False)

        fig.update_layout(margin=dict(l=0, r=0, b=0, t=0))

        # fig.write_image("assets/percent_{}.png".format(names[i]), engine='orca', width=550, height=550)
        img_bytes = fig.to_image(format="png", width=500, height=500, engine='orca')
        encoding = b64encode(img_bytes).decode()
        img_b64 = "data:image/png;base64," + encoding
        contents.append(img_b64)
        i += 1

    return contents


"""
for i in range(3):
    fig = go.Figure(data=go.Pie(values=[min(int(0), 100), 100 - min(int(0), 100)],
                                hole=0.8,
                                sort=False))
    fig.update_traces(hoverinfo='none',
                      textinfo='none',
                      marker=dict(colors=['#EFA31D', '#D9D9D9']))
    fig.update_layout(showlegend=False)
    fig.add_annotation(x=0.5, y=0.5,
                       text='-',
                       font=dict(size=140, family='Arial',
                                 color='black'),
                       showarrow=False)
    fig.add_annotation(x=0.5, y=0.1,
                       text='%',
                       font=dict(size=60, family='Arial',
                                 color='black'),
                       showarrow=False)

    fig.update_layout(margin=dict(l=0, r=0, b=0, t=0))

    fig.write_image("assets/percent_{}_none.png".format(names[i]), engine='orca', width=500, height=500)
    """


def create_fig_bills(annual_elec_bill_wo_sys, annual_elec_bill_w_sys):
    fig = go.Figure(go.Bar(
        x=[annual_elec_bill_wo_sys, annual_elec_bill_w_sys],
        y=['Without PV system', 'With PV system'],
        marker=dict(color=['#D9D9D9', '#EFA31D']),
        hovertemplate='<b>%{y} </b> <br>%{x} € <extra></extra>',
        orientation='h'))

    fig.update_layout(xaxis_title='Bill (€)')
    fig.update_layout(yaxis=dict(autorange="reversed"))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=False)
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)",
                      title='Electric utility bill')

    return fig


def create_fig_load(annual_pv_production, annual_import, annual_pv_to_batt, annual_export):
    total = annual_pv_production + abs(annual_import)
    fig = go.Figure(go.Sunburst(
        labels=["Total", "PV", "Grid import", "Direct load", "Battery", "Grid export"],
        parents=["", "Total", "Total", "PV", "PV", "PV"],
        values=[total, annual_pv_production, abs(annual_import),
                (annual_pv_production - abs(annual_pv_to_batt) - annual_export), abs(annual_pv_to_batt), annual_export],
        branchvalues="total",
        hovertemplate='<b>%{label} </b> <br>%{value} kWh <extra></extra>',
        insidetextorientation='horizontal'
    ))
    fig.update_traces(marker=dict(colors=['#FFFFFF', '#EFA31D', '#D9D9D9', '#EFA31D', '#EFA31D', '#EFA31D'],
                                  line=dict(color='#FFFFFF', width=2)))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)")
    fig.update_layout(margin=dict(t=10, b=10, r=10, l=10))

    return fig


def pil_to_b64(im, enc_format="png", **kwargs):
    """
    Converts a PIL Image into base64 string for HTML displaying
    :param im: PIL Image object
    :param enc_format: The image format for displaying. If saved the image will have that extension.
    :return: base64 encoding
    """

    buff = io.BytesIO()
    im.save(buff, format=enc_format, **kwargs)
    encoded = base64.b64encode(buff.getvalue()).decode("utf-8")

    return encoded


def create_kwh_diagram(pv, imp, exp, batt, load):
    img = Image.open('./assets/kwh_template.png')

    # Initialize drawing
    draw = ImageDraw.Draw(img)

    # Set font
    font = ImageFont.truetype("OCRAEXT.ttf", size=70)

    length_rect = 600
    width_rect = 114
    fill = '#EAEAEA'
    outline = '#5F5F5F'
    outline_width = 15
    radius = 15

    list_pos_x = [215, 215, 215, 1574, 3172]
    list_pos_y = [185, 1870, 2005, 2165, 1850]
    text_colors = ['#6596C1', '#EE7475', '#EE7475', '#6596C1', '#99CB5F']
    texts = [str(int(pv)) + ' kWh', 'I: ' + str(int(imp)) + ' kWh', 'E: ' + str(int(exp)) + ' kWh',
             str(int(batt)) + ' kWh', str(int(load)) + ' kWh']

    for i in range(len(list_pos_x)):
        pos_x = list_pos_x[i]
        pos_y = list_pos_y[i]
        text = text_colors[i]

        # Draw textbox
        draw.rounded_rectangle(((pos_x, pos_y), (pos_x + length_rect, pos_y + width_rect)), fill=fill, outline=outline,
                               width=outline_width, radius=radius)
        draw.text((pos_x + length_rect / 2, pos_y + width_rect / 2), texts[i], fill=text, font=font, anchor='mm')

    # Save image
    # img.save('./assets/kwh_diagram.png')

    return "data:image/png;base64, " + pil_to_b64(img)
