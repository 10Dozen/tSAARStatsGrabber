package main

import (
	"archive/zip"
	"bufio"
	"bytes"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
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

// Downloads, unzips and gather stats from AAR by given (url)
func handleAAR(url string, targetDirname string) {

	// -- Get AAR from remote repo
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
	resp.Body.Close()

	// -- Unzip downloaded file
	zipReader, err := zip.NewReader(bytes.NewReader(body), resp.ContentLength)
	if err != nil {
		panic(err)
	}

	var filename string
	var unzippedContent []byte
	for _, file := range zipReader.File {
		open, err := file.Open()
		if err != nil {
			panic(err)
		}
		defer open.Close()

		filename = file.Name
		unzippedContent, err = io.ReadAll(open)
		open.Close()
	}

	// -- Retrieve AAR stats from content
	ExtractAARStats(filepath.Join(targetDirname, filename), unzippedContent)

	return
}

func worker(idx int, inCh *chan string, ctrlCh *chan int, targetDirname string) {
	in := *inCh
	ctrl := *ctrlCh
	for {
		url, ok := <-in
		if !ok {
			ctrl <- 0
			close(ctrl)
			return
		}
		handleAAR(url, targetDirname)
	}
}

func handleAARs(urls []string, dir string) {
	urlCh := make(chan string, WORKERS)
	ctrlChannels := make([]chan int, WORKERS)
	for i := 0; i < WORKERS; i++ {
		ch := make(chan int)
		ctrlChannels[i] = ch
		go worker(i, &urlCh, &ch, dir)
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
	filter_substr := promptDateFilter()
	urls := findReports(filter_substr)
	if urls == nil {
		fmt.Printf("ОШИБКА: Не обнаружено AAR для фильтра %s\n", filter_substr)
	}

	os.Mkdir(filter_substr, os.ModeAppend)
	handleAARs(urls, filter_substr)
	fmt.Println("All done")
}
