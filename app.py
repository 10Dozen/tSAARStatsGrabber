from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta
import zipfile
import json
import operator
from typing import Dict

EXPORT_FILENAME = "AAR Stats 2024-10.txt"
DATE_STARTS_WITH = '2024-10-'
# AAR_BASE_DIR = r'G:\tS\aarDataGrabber\aars'
AAR_BASE_DIR = r'D:\Github\aar\aars'

TERRAIN_CODENAME_TO_NAME = {
    'tem_kujari'.lower():           {'name': 'Kujari'},
    'WL_Rosche'.lower():            {'name': 'Rosche, Germany'},
    'cain'.lower():                 {'name': 'Kolgujev (CWR)'},
    'cup_chernarus_A3'.lower():     {'name': 'Chernarus 2020'},
    'Malden'.lower():               {'name': 'Malden (2035)'},
    'VTF_Korsac'.lower():           {'name': 'Korsac'},
    'VTF_Korsac_Winter'.lower():    {'name': 'Korsac (Winter)'},
    'MCN_Aliabad'.lower():          {'name': 'Aliabad Region'},
    'tem_ihantalaw'.lower():        {'name': 'Ihantala Winter'},
    'lingor3'.lower():              {'name': 'Lingor Island'},
    'sara_dbe1'.lower():            {'name': 'Sahrani'},
    'brf_sumava'.lower():           {'name': 'Šumava'},
    'Woodland_ACR'.lower():         {'name': 'Bystica'},
    'Altis'.lower():                {'name': 'Altis'},
    'takistan'.lower():             {'name': 'Takistan'},
    'chernarus'.lower():            {'name': 'Chernarus'},
    'chernarus_summer'.lower():     {'name': 'Chernarus (Summer)'},
    'Chernarus_winter'.lower():     {'name': 'Chernarus (Winter)'},
    'Tanoa'.lower():                {'name': 'Tanoa'},
    'ruha'.lower():                 {'name': 'Ruha'},
    'Kunduz'.lower():               {'name': 'Kunduz, Afghanistan'},
    'Zargabad'.lower():             {'name': 'Zargabad'},
    'IslaPera'.lower():             {'name': 'Isla Pera'},
    'Farabad'.lower():              {'name': 'Farabad'},
    'intro'.lower():                {'name': 'intro'},
    'ProvingGrounds_PMC'.lower():   {'name': 'Proving Grounds'},
    'Desert_E'.lower():             {'name': 'Desert'},
    'DYA'.lower():                  {'name': 'Diyala'},
    'Bootcamp_ACR'.lower():         {'name': 'Bukovina'},
    'Mountains_ACR'.lower():        {'name': 'Takistan Mountains'},
    'porto'.lower():                {'name': 'Porto'},
    'eden'.lower():                 {'name': 'Everon'},
    'go_map_fjord'.lower():         {'name': 'Fjord'},
    'cartercity'.lower():           {'name': 'Pecher'},
    'vtf_lybor'.lower():            {'name': 'Lybor'},
    'stratis'.lower():              {'name': 'Stratis'},
    'tem_vinjesvingenc'.lower():    {'name': 'Vinjesvingenc'},
}

EXPORTER = None

class AAR:
    def __init__(self,
                 mission_name, terrain, mission_time,
                 players, players_deployed, players_killed,
                 shots_fired, ai_killed,  vehicles_killed, players_count = None):
        self.mission_name = mission_name
        self.terrain = terrain
        self.mission_time = mission_time
        self.players = players
        self.players_count = len(players)
        self.players_deployed = players_deployed
        self.players_killed = players_killed
        self.ai_killed = ai_killed
        self.vehicles_killed = vehicles_killed
        self.shots_fired = shots_fired

    def serialize(self) -> Dict:
        d = self.__dict__.copy()
        d['players'] = list(d['players'])
        return d
    
    @staticmethod
    def deserialize(data):
        return AAR(**data)



class PlayerStat:
    def __init__(self, name):
        self.name = name
        self.playtime = 0
        self.deaths = 0
        self.deploys = 0
        self.deaths_per = 0
        self.deploys_per = 0
        self.survivability = 0

    def add_playtime(self, time):
        self.playtime += time

    def add_deaths(self, count, mission_total):
        self.deaths += count
        self.deaths_per = get_percent(self.deaths, mission_total)

    def add_deploys(self, count, mission_total):
        self.deploys += count
        self.deploys_per = get_percent(self.deploys, mission_total)
        self.survivability = 100 * (1 - self.deaths / self.deploys)


class Exporter:
    MISSIONS_GRID = {
        "title": "Missions (%s):",
        "line": "  %s"
    }
    PLAYERS_GRID = {
        "title": "Players (partaking, by %s):",
        "line": "  %-20s | %-7s | %-7s | %-20s | %-7s",
        "headers": ('Name', 'Events', '%', 'Playtime', '%')
    }
    PLAYERS_SURVIVE_GRID = {
        "title": "Players (survivability rate, by %s):",
        "line": "  %-20s | %-7s | %-7s | %-7s | %-7s | %-15s",
        "headers": ('Name', 'Deaths', '%', 'Deploys', '%', 'Survivability')
    }
    TERRAINS = {
        "title": "Terrains (by %s):",
        "line": "  %-20s | %-7s | %-7s | %-20s | %-7s",
        "headers": ('Terrain', 'Times', '%', 'Playtime', '%')
    }
    ABANDONED_VEHICLES = {
        "title": "Abandoned/Killed vehicles:",
        "line": "  %-50s | %-7s | %-7s",
        "headers": ('Vehicle', 'Count', '%')
    }

    def __init__(self, filename="AAR Stats.txt"):
        self.name = filename
        self._raw_lines = []
        self._grid_missions = []
        self._grid_players_partaking = []
        self._grid_players_survive_rate = []
        self._grid_terrains = []
        self._grid_abandoned_vehicles = []
    
    def __f_grid_title(self, grid, params=tuple()):
        out = getattr(self, grid).get("title") % params
        print()
        print(out)
        return out
    
    def __f_grid_headers(self, grid):
        out = []
        grid_info = getattr(self, grid)
        headers = grid_info.get("headers")
        if not headers:
            return []
        out = [
            grid_info.get("line") % headers,
            grid_info.get("line") % tuple(["---" for _ in range(len(headers))])
        ]
        for o in out:
            print(o)
        return out
    
    def __f_grid_line(self, grid, line_data):
        out = getattr(self, grid).get("line") % line_data
        print(out)
        return out

    # ---
    def write_raw_line(self, line):
        print(line)
        self._raw_lines.append(line)

    def __write_multi_sort_grid(self, gridname, sort_rules, data_set_reader, data_set):
        lines = []
        for subtitle, sorting_rules in sort_rules:
            lines.append(self.__f_grid_title(gridname, subtitle))
            lines.extend(self.__f_grid_headers(gridname))
            for e_data in sorted(data_set, **sorting_rules):
                lines.append(
                    self.__f_grid_line(gridname, data_set_reader(e_data))
                )
            lines.append("")
        return lines

    def write_missions_grid(self, missions):
        grid = "MISSIONS_GRID"
        lines = [self.__f_grid_title(grid, len(missions))]
        for m in missions:
            lines.append(self.__f_grid_line(grid, m))
        self._grid_missions = lines

    def write_players_partaking_grid(self, player_partaking_stats):
        self._grid_players_partaking = \
            self.__write_multi_sort_grid(
                gridname="PLAYERS_GRID",
                sort_rules=[
                    ("Events visited", {"key": lambda x: operator.getitem(x, 'count'), "reverse": True}),
                    ("Playtime", {"key": lambda x: operator.getitem(x, 'time'), "reverse": True})
                ],
                data_set_reader=lambda d: (
                    d['player'], 
                    d['count'], self.format_percent(d['count_per']),
                    self.format_time(d['time']), self.format_percent(d['time_per'])
                ),
                data_set=player_partaking_stats.values()
            )

    def write_players_survivability_grid(self, per_player_data):
        self._grid_players_survive_rate = \
            self.__write_multi_sort_grid(
                gridname="PLAYERS_SURVIVE_GRID",
                data_set=per_player_data.values(),
                data_set_reader=lambda d: (
                    d.name,
                    d.deaths,
                    self.format_percent(d.deaths_per),
                    d.deploys,
                    self.format_percent(d.deploys_per),
                    self.format_percent(d.survivability)
                ),
                sort_rules=[
                    ("Deaths", {"key": operator.attrgetter('deaths'), "reverse": True}),
                    ("Survivability", {"key": operator.attrgetter('survivability'), "reverse": True})
                ]
            )

    def write_terrain_grid(self, terrains_stats):
        self._grid_terrains = \
            self.__write_multi_sort_grid(
                gridname="TERRAINS",
                data_set=terrains_stats.values(),
                data_set_reader=lambda d: (
                    d['name'],
                    d['count'], self.format_percent(d['count_per']),
                    self.format_time(d['time']), self.format_percent(d['time_per'])
                ),
                sort_rules=[
                    ("Events", {"key": lambda x: operator.getitem(x, 'count'), "reverse": True}),
                    ("Playtime", {"key": lambda x: operator.getitem(x, 'time'), "reverse": True})
                ]
            )

    def write_abandoned_vehicles_stats(self, vehicle_stats):
        self._grid_abandoned_vehicles = \
            self.__write_multi_sort_grid(
                gridname="ABANDONED_VEHICLES",
                data_set=vehicle_stats.values(),
                data_set_reader=lambda d: (
                    d['name'], d['count'], self.format_percent(d['count_per'])
                ),
                sort_rules=[
                    (tuple(), {"key": lambda x: operator.getitem(x, 'count'), "reverse": True})
                ]
            )

    def export(self):
        # Write to console and file stored lines
        with open(self.name, 'w', encoding='utf-8') as f:
            f.writelines("\n".join(self._raw_lines))
            f.write("\n\n\n")
            f.writelines("\n".join(self._grid_missions))
            f.write("\n\n\n")
            f.writelines("\n".join(self._grid_terrains))
            f.write("\n\n\n")
            f.writelines("\n".join(self._grid_players_partaking))
            f.write("\n\n\n")
            f.writelines("\n".join(self._grid_players_survive_rate))
            f.write("\n\n\n")
            f.writelines("\n".join(self._grid_abandoned_vehicles))
            f.write("\n\n\n")

    @staticmethod
    def format_time(time_s):
        d = datetime(1,1,1) + timedelta(seconds=time_s)
        if d.day - 1 == 0:
            return "%d h %d min %d sec" % (d.hour, d.minute, d.second)
        return "%d day %d h %d min %d sec" % (d.day-1, d.hour, d.minute, d.second)
    
    @staticmethod
    def format_percent(val):
        return f"{val:.2f}%"


def get_time(time_s):
    d = datetime(1,1,1) + timedelta(seconds=time_s)
    if d.day - 1 == 0:
        return "%d h %d min %d sec" % (d.hour, d.minute, d.second)
    return "%d day %d h %d min %d sec" % (d.day-1, d.hour, d.minute, d.second)


def get_percent(v, t):
    return (v / t * 100)

def read_files(filter_by_date=DATE_STARTS_WITH):
    filtered = []
    for aar_file in Path(AAR_BASE_DIR).iterdir():
        parts = aar_file.name.split(".")
        if len(parts) == 3:
            continue
        date = parts[1]
        if date.startswith(filter_by_date):
            filtered.append(aar_file.name)

    return filtered


def read_aars(aar_files):
    missions_in_period = len(aar_files)
    mission_names = []
    total_time = 0
    total_deployed_units = 0
    players_data = []
    per_player_data: dict[str, PlayerStat] = {}
    terrains_stats = {}
    total_vehicles_abandoned = []
    total_ai_kills = 0
    total_shots_fired = 0
    total_player_lost = 0
    max_players_counts = 0

    for aar_file in aar_files:
        aar = read_aar(aar_file)
        mission_names.append(aar.mission_name)
        mission_time = aar.mission_time

        total_time += mission_time
        total_deployed_units += len(aar.players_deployed)
        players_data.extend(aar.players)
        total_vehicles_abandoned.extend(aar.vehicles_killed)
        total_ai_kills += aar.ai_killed
        total_player_lost += len(aar.players_killed)

        terrain = aar.terrain.lower()
        terrain_name = None 
        if not TERRAIN_CODENAME_TO_NAME.get(terrain):
            raise ValueError(f"Failed to find name for the [{terrain}] terrain")
            
        terrain_stat = terrains_stats.get(terrain, {
            "name": TERRAIN_CODENAME_TO_NAME.get(terrain).get("name"),
            "count": 0,
            "time": 0,
            "count_per": 0,
            "time_per": 0
        })
        terrain_stat['count'] += 1
        terrain_stat['time'] += mission_time
        terrains_stats[terrain] = terrain_stat

        if max_players_counts < aar.players_count:
            max_players_counts = aar.players_count

        total_shots_fired += aar.shots_fired

        for p in set(aar.players):
            p_stat: PlayerStat = per_player_data.get(p, PlayerStat(p))

            p_stat.add_playtime(mission_time)
            p_stat.add_deaths( len([pk for pk in aar.players_killed if pk == p]), total_player_lost )
            p_stat.add_deploys( len([pd for pd in aar.players_deployed if pd == p]), total_deployed_units )

            per_player_data[p] = p_stat

    
    mission_avg_time = total_time / missions_in_period
    EXPORTER.write_raw_line("Overall data:")
    EXPORTER.write_raw_line(f"  Total mission time: {total_time} sec ({get_time(total_time)})")
    EXPORTER.write_raw_line(f"  Mission Average play time: {mission_avg_time:.0f} sec ({get_time(mission_avg_time)})")
    EXPORTER.write_raw_line(f"  Number of unique players: {len(set(players_data))}")
    EXPORTER.write_raw_line(f"  Max players in one mission: {max_players_counts}")
    EXPORTER.write_raw_line(f"  Total players deployed: {total_deployed_units}")
    EXPORTER.write_raw_line(f"  Total muntion fired: {total_shots_fired}")
    EXPORTER.write_raw_line(f"  Total AI killed: {total_ai_kills}")
    EXPORTER.write_raw_line(f"  Abandoned/Killed vehicles: {len(total_vehicles_abandoned)}")
    EXPORTER.write_raw_line(f"  Total player losses: {total_player_lost}")
    EXPORTER.write_raw_line(f"  Avg survivability: {100 * (1 - total_player_lost/total_deployed_units):.2f}%")
    
    EXPORTER.write_missions_grid(mission_names)

    # Player partaking stats
    player_partaking_stats = {}
    for p, c in Counter(players_data).most_common():
        part_percentage = get_percent(c, missions_in_period)
        part_time = per_player_data[p].playtime
        part_time_per = get_percent(per_player_data[p].playtime, total_time)
        player_partaking_stats[p] = {
            "player": p,
            "count": c, 
            "time": part_time,
            "count_per": part_percentage,
            "time_per": part_time_per
        }

    EXPORTER.write_players_partaking_grid(player_partaking_stats)

    # Player survivabilirt stats
    EXPORTER.write_players_survivability_grid(per_player_data)

    # Terrains
    for terrain_stat in terrains_stats.values():
        terrain_stat['count_per'] = get_percent(terrain_stat['count'], missions_in_period)
        terrain_stat['time_per'] = get_percent(terrain_stat['time'], total_time)
    EXPORTER.write_terrain_grid(terrains_stats)

    # Vehicles
    abandoned_vehicles_stats = {}
    for e, c in Counter(total_vehicles_abandoned).most_common():
        abandoned_vehicles_stats[e] = {
            "name": e,
            "count": c,
            "count_per": get_percent(c, len(total_vehicles_abandoned))
        }
    EXPORTER.write_abandoned_vehicles_stats(abandoned_vehicles_stats)


def read_aar(aar_file):
    filepath = Path.joinpath(Path(AAR_BASE_DIR), Path(aar_file))
    print('Reading %s' % filepath)
    if not Path.exists(filepath):
        print('File not found...')
        return
    
    extracted = Path(aar_file.rsplit(".", maxsplit=1)[0] + '.txt')
    aar_data = read_cached_aar_data(extracted)
    if not aar_data:
        if not Path.exists(extracted):
            with zipfile.ZipFile(filepath) as zf:
                zf.extractall()
    
        with open(extracted, 'r', encoding='utf-8') as ef:
            parsed_data = json.loads(
                (ef.readlines()[0])[len('aarFileData = '):]
            )

        players = set([p[0] for p in parsed_data['metadata']['players']])
        deployed_players = [u[1] for u in parsed_data['metadata']['objects']['units'] if u[3] == 1]
        shots_fired = sum([len(tl[2]) for tl in parsed_data['timeline']])
        killed_players, killed_units_count, killed_vehicles = track_kia_units(parsed_data)

        aar_data = AAR(
            mission_name=parsed_data['metadata']['name'],
            terrain=parsed_data['metadata']['island'],
            mission_time=parsed_data['metadata']['time'],
            players=players,
            players_deployed=deployed_players,
            players_killed=killed_players,
            ai_killed=killed_units_count,
            vehicles_killed=killed_vehicles,
            shots_fired=shots_fired
        )
        
        cache_aar_data(extracted, aar_data)

    return aar_data


def read_cached_aar_data(filename: Path) -> AAR:
    filename = Path(filename.name + '.cache')
    if not Path.exists(filename):
        return None
    
    print('AAR data was read from cache')
    parsed_data = json.load(open(filename, 'r', encoding='utf-8'))
    return AAR.deserialize(parsed_data)
    

def cache_aar_data(filename: str, aar_data: AAR) -> None: 
    with open(Path(filename.name + '.cache'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(aar_data.serialize()))



def track_kia_units(aar_data):
    units_meta = {}
    for umeta in aar_data['metadata']['objects']['units']:
        units_meta[umeta[0]] = {
            "name": umeta[1],
            "is_player": umeta[3] == 1
        }

    vehs_meta = {}
    for umeta in aar_data['metadata']['objects']['vehs']:
        vehs_meta[umeta[0]] = umeta[1]

    vehs = {}
    units = {}
    timetrack_limit = len(aar_data['timeline']) - 5
    for timelabel, t in enumerate(aar_data['timeline']):
        if timelabel > timetrack_limit:
            break

        for unit_data in t[0]:
            u_id, _, _, _, alive, _ = unit_data
            u_meta = units_meta.get(u_id)
            is_player = u_meta.get("is_player")

            unit = units.get(u_id, {
                "killed": False,
                "death_time": 0,
                "is_player": is_player,
                "name": u_meta.get("name")
            })

            if alive == 0 and not unit['killed']:
                unit['killed'] = True
                unit['death_time'] = timelabel + 1

            units[u_id] = unit

        for veh_data in t[1]:
            u_id, _, _, _, alive, owner, _ = veh_data

            vic = vehs.get(u_id, {
                "killed": False,
                "abandoned": False,
                "owned": False,
                "name": vehs_meta.get(u_id)
            })

            if alive == 0:
                vic['killed'] = True
            if owner > -1:
                vic['owned'] = True
                vic['abandoned'] = False
            elif vic['owned']:
                vic['onwed'] = False
                vic['abandoned'] = True

            vehs[u_id] = vic

    killed_players = []
    killed_units_count = 0
    for u_id, u in units.items():
        if not u['killed']:  # no kills
            continue
        if u['is_player']:
            killed_players.append(u['name'])
        else:
            killed_units_count += 1

    killed_vehicles = []
    for v in vehs.values():
        if not v['killed'] and not v['abandoned']:
            continue
        killed_vehicles.append(v['name'])

    return killed_players, killed_units_count, killed_vehicles


if __name__ == '__main__':
    EXPORTER = Exporter(EXPORT_FILENAME)
    print("----")
    read_aars(read_files())

    EXPORTER.export()
