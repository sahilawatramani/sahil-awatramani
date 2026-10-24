from .load import load_pack
from .integrity import repair_clocks, inspect_locations, inspect_duplicates, inspect_cadence
from .peers import Peers
from .basic import basic_checks, retain_mountain_weather
from .advanced import pressure_steps, wind_steps, daylight_temperature_drift, rain_blockage


def analyze(path):
    result = load_pack(path)
    repair_clocks(result)
    inspect_locations(result)
    inspect_duplicates(result)
    inspect_cadence(result)
    peers = Peers(result)
    basic_checks(result, peers)
    pressure_steps(result, peers)
    wind_steps(result, peers)
    daylight_temperature_drift(result, peers)
    rain_blockage(result, peers)
    retain_mountain_weather(result, peers)
    result.flags.sort(key=lambda f:(f.station_id, f.start, f.channel, f.issue, f.end))
    return result
