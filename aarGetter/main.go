package main

import (
	"archive/zip"
	"bufio"
	"bytes"
	"fmt"
	"io"
	"net/http"
	"os"
	"regexp"
	"strings"
	"time"
)

const (
	WORKERS       int    = 8
	AAR_CONFIG    string = `https://raw.githubusercontent.com/TacticalShift/aar/refs/heads/master/aarListConfig.ini`
	GITHUB_PREFIX        = `https://github.com/TacticalShift/aar/raw/refs/heads/master/`

	AAR_LINK_PATTERN = `"link":\s*"(.*)"`

	// "link": "aars/AAR.2024-11-12.ruha.CO16_Along_the_Track.zip"
)

func promptDateFilter() (date_filter string) {
	today := time.Now()
	year := today.Year()
	month := int(today.Month())

	fmt.Printf("Год (%d): ", year)
	fmt.Scanf("%d\n", &year)

	fmt.Printf("Месяц (%d): ", month)
	fmt.Scanf("%d\n", &month)

	return fmt.Sprintf("%d-%02d", year, month)
}

// Reads remote aarListConfig.ini and get slice of URLs to AARs that match given (filter_by)
func findReports(filter_by string) (url []string) {
	resp, err := http.Get(AAR_CONFIG)
	if resp != nil {
		defer resp.Body.Close()
	}
	if err != nil {
		panic(err)
	}

	fmt.Println(filter_by)
	filter_regexp := regexp.MustCompile(AAR_LINK_PATTERN)
	scanner := bufio.NewScanner(resp.Body)
	for scanner.Scan() {
		line := strings.Trim(scanner.Text(), " \t,\n")
		if strings.HasPrefix(line, `"link"`) && strings.Contains(line, filter_by) {
			matches := filter_regexp.FindStringSubmatch(line)
			if matches != nil {
				url = append(url, matches[1])
			}
		}
	}

	return
}

// Downloads and unzips AAR by given (url)
func getAAR(url string) {
	url = GITHUB_PREFIX + url

	resp, err := http.Get(url)
	if resp != nil {
		defer resp.Body.Close()
	}
	if err != nil {
		panic(err)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		panic(err)
	}

	zipReader, err := zip.NewReader(bytes.NewReader(body), resp.ContentLength)
	if err != nil {
		panic(err)
	}

	for _, file := range zipReader.File {
		open, err := file.Open()
		if err != nil {
			panic(err)
		}
		defer open.Close()

		create, err := os.Create(file.Name)
		if err != nil {
			panic(err)
		}
		defer create.Close()
		create.ReadFrom(open)
	}

	return
}

func worker(idx int, inCh *chan string, ctrlCh *chan int) {
	in := *inCh
	ctrl := *ctrlCh
	for {
		url, ok := <-in
		if !ok {
			ctrl <- 0
			close(ctrl)
			return
		}
		getAAR(url)
	}
}

func downloadAARs(urls []string) {
	urlCh := make(chan string, WORKERS)
	ctrlChannels := make([]chan int, WORKERS)
	for i := 0; i < WORKERS; i++ {
		ch := make(chan int)
		ctrlChannels[i] = ch
		go worker(i, &urlCh, &ch)
	}

	for _, u := range urls {
		fmt.Println(u)
		urlCh <- u
	}
	close(urlCh)

	for _, ch := range ctrlChannels {
		<-ch
	}
}

func main() {
	/*
		filter_substr := promptDateFilter()
		urls := findReports(filter_substr)
		if urls == nil {
			fmt.Printf("ОШИБКА: Не обнаружено AAR для фильтра %s\n", filter_substr)
		}

		downloadAARs(urls)
		fmt.Println("All done")
	*/

	//GetAARStats(`AAR.2024-11-05.Mountains_ACR.CO14_Bloody_Dawn.txt`)
	//GetAARStats(`AAR.2024-11-02.porto.CO20_Paradise_or_Hell_1A.txt`)
	//GetAARStats(`AAR.2024-11-05.go_map_fjord.CO22_Trojan_Horse.txt`)
	//GetAARStats(`AAR.2024-11-02.brf_sumava.CO27_Operation_Edelweiss.txt`)

	//GetAARStats(`AAR.2024-11-02.WL_Rosche.CO31_Rebuttal_Letter.txt`)
	//GetAARStats(`AAR.2024-11-07.Farabad.CO27_Operation_Cou_Noue.txt`)
	//GetAARStats(`AAR.2024-11-07.tem_vinjesvingenc.CO20_Gas_Station_King.txt`)
	GetAARStats(`AAR.2024-11-09.WL_Rosche.CO30_Hedgerow_Hell_1A.json`)
	//GetAARStats(`AAR.2024-11-12.IslaPera.CO22_Morning_Ambush.json`)
}
