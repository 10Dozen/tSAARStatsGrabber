from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta
import sys
import os
import json
import operator
from typing import Dict

CONFIG_FILENAME = 'config.json'
CONFIG = None
EXPORTER = None

class AARStats:
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
        return AARStats(**data)


class ORBATStats:
    def __init__(self, mission_name: str, hq: list[str], squad_leader: list[str], team_leaders: list[str]):
        self.mission_name: str = mission_name
        self.hq: list[str] = hq
        self.squad_leaders: list[str] = squad_leader
        self.team_leaders: list[str] = team_leaders

    @staticmethod
    def deserialize(data):
        stat: ORBATStats = ORBATStats(
            mission_name=data["Mission"],
            hq=data["Leaders"]["HQ"],
            squad_leader=data["Leaders"]["SquadLeaders"],
            team_leaders=data["Leaders"]["TeamLeaders"]
        )
        return stat


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


class LeaderStat:
    def __init__(self, name: str):
        self.name = name
        self.hq_times: int = 0
        self.sl_times: int = 0
        self.ftl_times: int = 0
        self.hq_missions: list[str] = []
        self.sl_missions: list[str] = []
        self.ftl_missions: list[str] = []
    
    def add_as_hq(self, mission: str) -> None:
        self.hq_times += 1
        self.hq_missions.append(mission)
    
    def add_as_sl(self, mission: str) -> None:
        self.sl_times += 1
        self.sl_missions.append(mission)
        
    def add_as_ftl(self, mission: str) -> None:
        self.ftl_times += 1
        self.ftl_missions.append(mission)


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
    TOP_PLAYERS_SURVIVE_GRID = {
        "title": "Most-participating Players (survivability rate,  by %s):",
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
    ORBAT_HQ_GRID = {
        "title": "HQ Role (by %s)",
        "headers": ('Name', 'Times', '%'),
        "line":  "  %-20s | %-7s | %-7s"    
    }
    ORBAT_SL_GRID = {
        "title": "Squad Leader Role (by %s)",
        "headers": ('Name', 'Times', '%'),
        "line":  "  %-20s | %-7s | %-7s"    
    }
    ORBAT_FTL_GRID = {
        "title": "Fireteam Leader Role (by %s)",
        "headers": ('Name', 'Times', '%'),
        "line":  "  %-20s | %-7s | %-7s"    
    }

    def __init__(self, filename="AAR Stats.txt"):
        self.name = filename
        self._raw_lines = []
        self._grid_missions = []
        self._grid_players_partaking = []
        self._grid_players_survive_rate = []
        self._grid_terrains = []
        self._grid_abandoned_vehicles = []
        self._grid_orbat_hq_partaking = []
        self._grid_orbat_sl_partaking = []
        self._grid_orbat_ftl_partaking = []
        self._orbat_per_player_stats = []
    
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

    # -- General
    def write_raw_line(self, line):
        print(line)
        self._raw_lines.append(line)

    # -- AAR
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

    def write_players_survivability_grid(self, per_player_data, top=False):
        self._grid_players_survive_rate = \
            self.__write_multi_sort_grid(
                gridname="TOP_PLAYERS_SURVIVE_GRID" if top else "PLAYERS_SURVIVE_GRID",
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
                    ("Max Deaths", {"key": operator.attrgetter('deaths'), "reverse": True}),
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

    # -- ORBAT 
    def write_orbat_hqs(self, stats: dict[str, dict]):
        self._grid_orbat_hq_partaking = \
        self.__write_multi_sort_grid(
            gridname="ORBAT_HQ_GRID",
            sort_rules=[
                ("Events", {"key": lambda x: operator.getitem(x, 'count'), "reverse": True})
            ],
            data_set_reader=lambda d: (
                d['player'],
                d['count'],
                self.format_percent(d['count_per'])
            ),
            data_set=stats.values()
        )

    def write_orbat_squad_leaders(self, stats: dict[str, dict]):
        self._grid_orbat_sl_partaking = \
        self.__write_multi_sort_grid(
            gridname="ORBAT_SL_GRID",
            sort_rules=[
                ("Events", {"key": lambda x: operator.getitem(x, 'count'), "reverse": True})
            ],
            data_set_reader=lambda d: (
                d['player'],
                d['count'],
                self.format_percent(d['count_per'])
            ),
            data_set=stats.values()
        )

    def write_orbat_team_leaders(self, stats: dict[str, dict]):
        self._grid_orbat_ftl_partaking = \
        self.__write_multi_sort_grid(
            gridname="ORBAT_FTL_GRID",
            sort_rules=[
                ("Events", {"key": lambda x: operator.getitem(x, 'count'), "reverse": True})
            ],
            data_set_reader=lambda d: (
                d['player'],
                d['count'],
                self.format_percent(d['count_per'])
            ),
            data_set=stats.values()
        )

    def write_orbat_per_player_stats(self, per_player_data: dict[str, LeaderStat]):
        lines = []
        lines.append('Leadership stats:')
        for ps in per_player_data.values():
            lines.append("")
            lines.append('  %-20s| HQ     | SL     | FTL    ' % ps.name)
            lines.append('  ---                 | ---    | ---    | ---')
            lines.append('  %-20s| %-7d| %-7d| %-7d' % (
                "", ps.hq_times, ps.sl_times, ps.ftl_times
            ))
            if ps.hq_missions:
                lines.append('  Missions as HQ:                %s' % ", ".join(ps.hq_missions))    
            if ps.sl_missions:        
                lines.append('  Missions as Squad leader:      %s' % ", ".join(ps.sl_missions))
            if ps.ftl_missions:
                lines.append('  Missions as Fireteam leader:   %s' % ", ".join(ps.ftl_missions))
            lines.append("")

        self._orbat_per_player_stats = lines
        for l in lines:
            print(l)

        pass

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
            f.write("ORBAT Stats:\n\n")
            f.write("\n".join(self._grid_orbat_hq_partaking))
            f.write("\n")            
            f.write("\n".join(self._grid_orbat_sl_partaking))
            f.write("\n")            
            f.write("\n".join(self._grid_orbat_ftl_partaking))
            f.write("\n")
            f.write("\n".join(self._orbat_per_player_stats))
            f.write("\n")

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


def read_aars(aar_files: list[Path]):
    missions_in_period: int = len(aar_files)
    mission_names: list[str] = []
    total_time: int = 0
    total_deployed_units: int = 0
    players_data = []
    per_player_data: dict[str, PlayerStat] = {}
    terrains_stats = {}
    total_vehicles_abandoned = []
    total_ai_kills = 0
    total_shots_fired = 0
    total_player_lost = 0
    max_players_counts = 0

    for aar_file in aar_files:
        aar = read_aar_stat(aar_file)
        if not aar:
            continue
        mission_names.append(aar.mission_name)
        mission_time = aar.mission_time

        total_time += mission_time
        total_deployed_units += len(aar.players_deployed)
        players_data.extend(aar.players)
        total_vehicles_abandoned.extend(aar.vehicles_killed)
        total_ai_kills += aar.ai_killed
        total_player_lost += len(aar.players_killed)

        terrain = aar.terrain.lower()
        terrain_name = CONFIG["Terrains"].get(terrain) 
        if not terrain_name:
            raise ValueError(f"Failed to find name for the [{terrain}] terrain")
            
        terrain_stat = terrains_stats.get(terrain, {
            "name": terrain_name.get("name"),
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

    # -- Totals data
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
    
    # -- Mission list
    EXPORTER.write_missions_grid(mission_names)

    # -- Player partaking stats
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

    # -- Player survivability stats
    top_participating_players = {
        name: per_player_data[name]
        for name, stat in player_partaking_stats.items()
        if stat["count"] >= missions_in_period/2
    }
    EXPORTER.write_players_survivability_grid(top_participating_players, True)
    EXPORTER.write_players_survivability_grid(per_player_data)

    # -- Terrains
    for terrain_stat in terrains_stats.values():
        terrain_stat['count_per'] = get_percent(terrain_stat['count'], missions_in_period)
        terrain_stat['time_per'] = get_percent(terrain_stat['time'], total_time)
    EXPORTER.write_terrain_grid(terrains_stats)

    # -- Vehicles
    abandoned_vehicles_stats = {}
    for e, c in Counter(total_vehicles_abandoned).most_common():
        abandoned_vehicles_stats[e] = {
            "name": e,
            "count": c,
            "count_per": get_percent(c, len(total_vehicles_abandoned))
        }
    EXPORTER.write_abandoned_vehicles_stats(abandoned_vehicles_stats)


def read_aar_stat(file: Path) -> AARStats:
    print('Reading %s' % file)
    if not Path.exists(file):
        print('File not found...')
        return
    stats_data = json.load(open(file, 'r', encoding='utf-8'))
    return AARStats.deserialize(stats_data)


def read_orbats(orbat_files: list[Path]):
    missions_in_period: int = 0
    leaders: dict[str, LeaderStat] = dict()
    hqs: list[str] = []
    squad_leaders: list[str] = []
    team_leaders: list[str] = []

    for file in orbat_files:
        stats = read_orbat_file(file)

        for orbat in stats:
            missions_in_period += 1
            mission = orbat.mission_name

            # -- Per player data
            for leader in orbat.hq:
                player_name = leader["Name"]
                hqs.append(player_name)

                player_stat: LeaderStat = leaders.get(
                    player_name,
                    LeaderStat(player_name)
                )
                player_stat.add_as_hq(mission)
                leaders[player_name] = player_stat

            for leader in orbat.squad_leaders:
                player_name = leader["Name"]
               
                squad_leaders.append(player_name)
                player_stat: LeaderStat = leaders.get(
                    player_name,
                    LeaderStat(player_name)
                )
                player_stat.add_as_sl(mission)
                leaders[player_name] = player_stat

            for leader in orbat.team_leaders:
                player_name = leader["Name"]

                team_leaders.append(player_name)
                player_stat: LeaderStat = leaders.get(
                    player_name,
                    LeaderStat(player_name)
                )
                player_stat.add_as_ftl(mission)
                leaders[player_name] = player_stat

    # -- Export ORBAT data
    hq_stats = {}
    for p, c in Counter(hqs).most_common():
        part_percentage = get_percent(c, missions_in_period)
        hq_stats[p] = {
            "player": p,
            "count": c, 
            "count_per": part_percentage
        }
    EXPORTER.write_orbat_hqs(hq_stats)

    sl_stats = {}
    for p, c in Counter(squad_leaders).most_common():
        part_percentage = get_percent(c, missions_in_period)
        sl_stats[p] = {
            "player": p,
            "count": c, 
            "count_per": part_percentage
        }
    EXPORTER.write_orbat_squad_leaders(sl_stats)

    tl_stats = {}
    for p, c in Counter(team_leaders).most_common():
        part_percentage = get_percent(c, missions_in_period)
        tl_stats[p] = {
            "player": p,
            "count": c, 
            "count_per": part_percentage
        }
    EXPORTER.write_orbat_team_leaders(tl_stats)

    EXPORTER.write_orbat_per_player_stats(leaders)


def read_orbat_file(file: Path) -> list[ORBATStats]:
    print('Reading %s' % file)
    if not Path.exists(file):
        print('File not found...')
        return
    stats_data = json.load(open(file, 'r', encoding='utf-8'))
    stats: list[ORBATStats] = []
    for raw_data in stats_data:
        stats.append(ORBATStats.deserialize(raw_data))
    return stats


def get_files(dir: str) -> list[Path]:
    '''Returns list of the filepathes from given directory
    '''
    print(f"Отбираются файлы из директоии {dir}")
    files = []
    for aar_file in Path(dir).iterdir():
        files.append(aar_file.absolute())

    print(f"Обнаружено {len(files)} файлов")
    return files


def read_config(config_name: str):
    config_data = None 
    with open(config_name, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    return config_data


def promptDateFilter() -> str:
    current_date = datetime.today()
    target_period = [current_date.year, current_date.month - 1]

    in_year = input(f"Год ({target_period[0]}): ")
    if in_year:
        target_period[0] = int(in_year)

    in_month = input(f"Месяц ({target_period[1]}): ")
    if in_month:
        target_period[1] = int(in_month)

    return "%d-%02d" % tuple(target_period)


if __name__ == '__main__':
    print("       ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓")
    print("       ┃   tS AAR/ORBAT Analytics (v.1.2.0)   ┃")
    print("       ┃           by 10Dozen                 ┃")
    print("       ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
    print(" Убедитесь, что настроены пути до соответствующих директорий в файле config.json!")
    print()

    CONFIG = read_config(CONFIG_FILENAME)
    terrains = {}
    for k, v in CONFIG["Terrains"].items():
        terrains[k.lower()] = v
    CONFIG["Terrains"] = terrains

    period_substr = promptDateFilter()
    export_filename = CONFIG['OutputFilenameFormat'] % period_substr  
    EXPORTER = Exporter(export_filename)
    print("----")

    # AAR Stats
    
    aar_files = get_files(os.path.join(CONFIG['AARDirectory'], period_substr))    
    if aar_files:
        read_aars(aar_files)
    else:
        print(f"ПРЕДУПРЕЖДЕНИЕ: Нет файлов для периода {period_substr}")

    # ORBAT Stats
    orbat_files = get_files(CONFIG['ORBATDirectory'])
    if orbat_files:
        read_orbats(orbat_files)

    EXPORTER.export()
    sys.exit(0)
    
