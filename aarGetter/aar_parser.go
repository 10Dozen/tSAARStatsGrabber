package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
)

type AARStats struct {
	MissionName     string   `json:"mission_name"`
	Terrain         string   `json:"terrain"`
	MisstionTime    int      `json:"mission_time"`
	Players         []string `json:"players"`
	PlayersDeployed []string `json:"players_deployed"`
	PlayersKilled   int      `json:"players_killed"`
	AIKilled        int      `json:"ai_killed"`
	VehiclesKilled  int      `json:"vehicles_killed"`
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

	players := make([]string, 0, len(aar.Metadata.Players))
	for i, p := range aar.Metadata.Players {
		players[i] = p[0]
	}
	fmt.Println(players)

	deployed := make([]string, 0, len(aar.Metadata.Players))
	for _, p := range aar.Metadata.Objects.Units {
		if p.IsPlayer == 0 {
			continue
		}
		deployed = append(deployed, p.Name)
	}

	shots := 0
	for _, frame := range aar.Frames {
		shots += len(frame.Attacks)
	}

	stats := &AARStats{
		MissionName:     aar.Metadata.Name,
		Terrain:         aar.Metadata.Terrain,
		MisstionTime:    aar.Metadata.Duration,
		Players:         players,
		PlayersDeployed: deployed,
		VehiclesKilled:  0,
		PlayersKilled:   0,
		AIKilled:        0,
		ShotsFired:      shots,
	}
	fmt.Println(stats)
}
