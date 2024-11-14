package main

import (
	"encoding/json"
	"fmt"
	"io"
	"math"
	"os"
)

const (
	START_LEAVE_DISTANCE float64 = 100
)

type AARStats struct {
	MissionName     string   `json:"mission_name"`
	Terrain         string   `json:"terrain"`
	MisstionTime    int      `json:"mission_time"`
	Players         []string `json:"players"`
	PlayersDeployed []string `json:"players_deployed"`
	PlayersKilled   []string `json:"players_killed"`
	AIKilled        int      `json:"ai_killed"`
	VehiclesKilled  []string `json:"vehicles_killed"`
	ShotsFired      int      `json:"shots_fired"`
}

type AAR struct {
	Metadata *AARMetadata `json:"metadata"`
	Frames   []*AARFrame  `json:"timeline"`
}

type AARMetadata struct {
	Terrain  string              `json:"island"`
	Name     string              `json:"name"`
	Duration int                 `json:"time"`
	Date     string              `json:"date"`
	Summary  string              `json:"desc"`
	Players  [][]string          `json:"players"`
	Objects  *AARMetadataObjects `json:"objects"`
}

type AARMetadataObjects struct {
	Units    []*AARMetadataUnit    `json:"units"`
	Vehicles []*AARMetadataVehicle `json:"vehs"`
}

type AARMetadataUnit struct {
	Id       int
	Name     string
	Side     string
	IsPlayer int
}

func (u *AARMetadataUnit) UnmarshalJSON(buf []byte) error {
	tmp := []interface{}{&u.Id, &u.Name, &u.Side, &u.IsPlayer}
	if err := json.Unmarshal(buf, &tmp); err != nil {
		return err
	}
	return nil
}

type AARMetadataVehicle struct {
	Id   int
	Name string
}

func (u *AARMetadataVehicle) UnmarshalJSON(buf []byte) error {
	tmp := []interface{}{&u.Id, &u.Name}
	if err := json.Unmarshal(buf, &tmp); err != nil {
		return err
	}
	return nil
}

type AARFrame struct {
	Units    []*AARFrameUnit
	Vehicles []*AARFrameVehicle
	Attacks  []*AARFrameAttack
}

func (u *AARFrame) UnmarshalJSON(buf []byte) error {
	tmp := []interface{}{&u.Units, &u.Vehicles, &u.Attacks}
	if err := json.Unmarshal(buf, &tmp); err != nil {
		return err
	}
	return nil
}

type AARFrameUnit struct {
	Id        int
	PosX      int
	PosY      int
	Dir       int
	IsAlive   int
	VehicleID int
}

func (u *AARFrameUnit) UnmarshalJSON(buf []byte) error {
	tmp := []interface{}{&u.Id, &u.PosX, &u.PosY, &u.Dir, &u.IsAlive, &u.VehicleID}
	if err := json.Unmarshal(buf, &tmp); err != nil {
		return err
	}
	return nil
}

type AARFrameVehicle struct {
	Id        int
	PosX      int
	PosY      int
	Dir       int
	IsAlive   int
	Owner     int
	CargoSize int
}

func (u *AARFrameVehicle) UnmarshalJSON(buf []byte) error {
	tmp := []interface{}{&u.Id, &u.PosX, &u.PosY, &u.Dir, &u.IsAlive, &u.Owner, &u.CargoSize}
	if err := json.Unmarshal(buf, &tmp); err != nil {
		return err
	}
	return nil
}

type AARFrameAttack struct {
	FromX int
	FromY int
	ToX   int
	ToY   int
}

func (u *AARFrameAttack) UnmarshalJSON(buf []byte) error {
	tmp := []interface{}{&u.FromX, &u.FromY, &u.ToX, &u.ToY}
	if err := json.Unmarshal(buf, &tmp); err != nil {
		return err
	}
	return nil
}

func GetAARStats(filename string) {
	file, err := os.Open(filename)
	if err != nil {
		panic(err)
	}

	content, err := io.ReadAll(file)
	content = content[len([]byte("aarFileData = ")):]
	if err != nil {
		panic(err)
	}

	aar := &AAR{}
	if err := json.Unmarshal(content, aar); err != nil {
		panic(err)
	}

	shots := 0
	for _, frame := range aar.Frames {
		shots += len(frame.Attacks)
	}

	stats := &AARStats{
		MissionName:     aar.Metadata.Name,
		Terrain:         aar.Metadata.Terrain,
		MisstionTime:    aar.Metadata.Duration,
		Players:         nil,
		PlayersDeployed: nil,
		VehiclesKilled:  nil,
		PlayersKilled:   nil,
		AIKilled:        0,
		ShotsFired:      shots,
	}

	trackUnits(aar, stats)

	fmt.Printf("MissionName: %#v \n", stats.MissionName)
	fmt.Printf("Terrain: %#v \n", stats.Terrain)
	fmt.Printf("MisstionTime: %#v \n", stats.MisstionTime)
	fmt.Printf("Players: %#v \n", stats.Players)
	fmt.Printf("PlayersDeployed: %#v \n", stats.PlayersDeployed)
	fmt.Printf("PlayersKilled: %#v \n", stats.PlayersKilled)
	fmt.Printf("VehiclesKilled: %#v \n", stats.VehiclesKilled)
	fmt.Printf("AIKilled: %#v \n", stats.AIKilled)
	fmt.Printf("ShotsFired: %#v \n", stats.ShotsFired)
}

func trackUnits(aar *AAR, stats *AARStats) {
	type TrackedUnit struct {
		Name        string
		IsPlayer    bool
		Killed      bool
		DeathTime   int
		InitPosLeft bool
		initPosX    int
		initPosY    int
	}

	type TrackedVehicle struct {
		Name      string
		Killed    bool
		Abandoned bool
		Owned     bool
	}

	unitsMetaMap := map[int]*TrackedUnit{}
	for _, u := range aar.Metadata.Objects.Units {
		unitsMetaMap[u.Id] = &TrackedUnit{
			Name:        u.Name,
			IsPlayer:    u.IsPlayer == 1,
			Killed:      false,
			DeathTime:   0,
			InitPosLeft: false,
			initPosX:    0,
			initPosY:    0,
		}
	}
	vehMetaMap := map[int]*TrackedVehicle{}
	for _, v := range aar.Metadata.Objects.Vehicles {
		vehMetaMap[v.Id] = &TrackedVehicle{
			Name:      v.Name,
			Killed:    false,
			Abandoned: false,
			Owned:     false,
		}
	}

	killedPlayers := make([]string, 0)
	killedAICount := 0
	nonConfirmedDeadPlayers := map[string]int{} //make([]string, 0)

	timetrack_limit := len(aar.Frames) - 10
	var frame *AARFrame
	for frameId := 0; frameId < timetrack_limit; frameId++ {
		frame = aar.Frames[frameId]

		for _, u := range frame.Units {
			trackedUnit := unitsMetaMap[u.Id]
			if trackedUnit == nil {
				continue
			}

			// -- Track AI units kills
			if !trackedUnit.IsPlayer {
				if u.IsAlive == 1 || trackedUnit.Killed {
					continue
				}
				trackedUnit.Killed = true
				trackedUnit.DeathTime = frameId
				killedAICount++
				continue
			}

			// -- Track players data
			// -- Track if player left start position
			if trackedUnit.initPosX == 0 {
				trackedUnit.initPosX = u.PosX
				trackedUnit.initPosY = u.PosY
			}

			// -- u.PosX become 0 when player mounts the vehicle, so skip checks here
			if !trackedUnit.InitPosLeft && u.PosX != 0 {
				trackedUnit.InitPosLeft =
					math.Abs(float64(trackedUnit.initPosX-u.PosX)) > START_LEAVE_DISTANCE || math.Abs(float64(trackedUnit.initPosY-u.PosY)) > START_LEAVE_DISTANCE
			}

			// -- No kill event - exit
			if u.IsAlive == 1 || trackedUnit.Killed {
				continue
			}

			// -- Register kill event for unit
			trackedUnit.Killed = true
			trackedUnit.DeathTime = frameId

			// -- Track disconnected player.
			//    If player is dead, but didn't leaved init pos -- it might by a disconnection issues (or GSO killed in base, but whatever).
			//    Otherwise - register player death.
			if !trackedUnit.InitPosLeft {
				fmt.Println("Player is killed but not moved yet - not count as killed: ", trackedUnit.Name)
				count, ok := nonConfirmedDeadPlayers[trackedUnit.Name]
				if !ok {
					count = 0
				}
				nonConfirmedDeadPlayers[trackedUnit.Name] = count + 1
				continue
			}
			killedPlayers = append(killedPlayers, trackedUnit.Name)
		}

		for _, v := range frame.Vehicles {
			vehMeta := vehMetaMap[v.Id]
			if vehMeta == nil {
				continue
			}
			if v.IsAlive == 0 {
				vehMeta.Killed = true
			}

			if v.Owner > -1 {
				vehMeta.Owned = true
				vehMeta.Abandoned = false
			} else if vehMeta.Owned {
				vehMeta.Owned = false
				vehMeta.Abandoned = true
			}
		}
	}

	abandonedVehicles := make([]string, 0)
	for _, v := range vehMetaMap {
		if !v.Killed && !v.Abandoned {
			continue
		}
		abandonedVehicles = append(abandonedVehicles, v.Name)
	}

	deployed := make([]string, 0, len(aar.Metadata.Players))
	for _, p := range aar.Metadata.Objects.Units {
		if p.IsPlayer == 0 {
			continue
		}

		count, ok := nonConfirmedDeadPlayers[p.Name]
		// -- No in nonConfirmedDeaths -> count as deployed
		if !ok || count == 0 {
			deployed = append(deployed, p.Name)
			continue
		}

		fmt.Println("Player is dead but not moved - not count as deployed: ", p.Name)
		nonConfirmedDeadPlayers[p.Name] = count - 1
	}

	playersMap := make(map[string]bool)
	players := make([]string, 0, len(deployed)/3)
	for _, v := range deployed {
		if _, entry := playersMap[v]; !entry {
			playersMap[v] = true
			players = append(players, v)
		}
	}

	stats.Players = players
	stats.PlayersDeployed = deployed
	stats.PlayersKilled = killedPlayers
	stats.AIKilled = killedAICount
	stats.VehiclesKilled = abandonedVehicles
}
