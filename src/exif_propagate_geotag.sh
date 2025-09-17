#!/bin/bash

# Bash script to copy geotag information from an image file to (many) other image files.
# 

# TODO as improvement use exiftool Docker
# see https://hub.docker.com/r/davidanson/exiftool/tags
# to ensure we run the latest version

# TODO rewrite this in golang integrating an handy file picker e.g. from https://github.com/charmbracelet/bubbles

SEARCHPATH=""
DRYRUN=false
PHOTO_WITH_CORRECT_LOCATION="" # optional

### Functions

function copy_geotag_from_photo() {
    SOURCE_PHOTO="$1"
    nfiles=0
    echo "Adding GPS metadata by copying it from [$SOURCE_PHOTO]..."

    if [[ "$DRYRUN" == "true" ]]; then
        echo "DRYRUN: command to run would be:"
        echo "  cat /tmp/exiftool_search_no_metadata.txt | xargs -d '\n' /usr/bin/exiftool -tagsfromfile ${SOURCE_PHOTO} -gps:all -overwrite_original -progress"
        echo
    else
        # this is way faster than passing 1 file at a time to exiftool;
        # this method also works with paths containing spaces
        cat /tmp/exiftool_search_no_metadata.txt | xargs -d '\n' /usr/bin/exiftool -tagsfromfile "${SOURCE_PHOTO}" -gps:all -overwrite_original -progress
    fi
}

function parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -d|--dry-run)
                DRYRUN=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [--dry-run] [--help] <PATH to search> [<path to file with geotag to copy>]"
                exit 0
                ;;
            -*)
                echo "Error: unknown option $1"
                exit 2
                ;;
            *)
                if [[ -z "$SEARCHPATH" ]]; then
                    SEARCHPATH="$1"
                elif [[ -z "$PHOTO_WITH_CORRECT_LOCATION" ]]; then
                    PHOTO_WITH_CORRECT_LOCATION="$1"
                else
                    echo "Error: too many positional arguments"
                    exit 2
                fi
                shift
                ;;
        esac
    done

    if [[ -z "$SEARCHPATH" ]]; then
        echo "Error: missing mandatory argument (SEARCHPATH)"
        exit 2
    fi

    # debug prints
    echo "DRYRUN = $DRYRUN"
    echo "SEARCHPATH   = $SEARCHPATH"
    echo "PHOTO_WITH_CORRECT_LOCATION  = $PHOTO_WITH_CORRECT_LOCATION"
}




parse_args "$@"

echo "Searching for files WITH GPS metadata in [$SEARCHPATH]"
/usr/bin/exiftool -r -if '$GPSLatitude' -p '$FilePath' "$SEARCHPATH" >/tmp/exiftool_search_with_metadata.txt 2>/dev/null

echo "Searching for files WITHOUT GPS metadata in [$SEARCHPATH]"
/usr/bin/exiftool -r -if 'not $GPSLatitude' -p '$FilePath' "$SEARCHPATH" >/tmp/exiftool_search_no_metadata.txt 2>/dev/null

# sort the output of exiftool since exiftool analyzes files not in alphabetical order
cat /tmp/exiftool_search_with_metadata.txt | sort | sponge /tmp/exiftool_search_with_metadata.txt
cat /tmp/exiftool_search_no_metadata.txt | sort | sponge /tmp/exiftool_search_no_metadata.txt

echo "List of photos with geotag info:"
cat /tmp/exiftool_search_with_metadata.txt

echo "List of photos without geotag info:"
cat /tmp/exiftool_search_no_metadata.txt

# now loop on each line of the file and print the filename
if [ -z "$PHOTO_WITH_CORRECT_LOCATION" ]; then
    nfiles_no_geotag="$( wc -l /tmp/exiftool_search_no_metadata.txt | cut -f1 -d ' ')"
    nfiles_with_geotag="$( wc -l /tmp/exiftool_search_with_metadata.txt | cut -f1 -d ' ')"
    if [[ $nfiles_no_geotag -eq 0 ]]; then
        echo
        echo "It looks like all files ($nfiles_with_geotag files) already have a geotag... nothing to do..."
        echo
    elif [[ $nfiles_with_geotag -eq 1 ]]; then
        PHOTO_WITH_CORRECT_LOCATION="$( cat /tmp/exiftool_search_with_metadata.txt )"
        copy_geotag_from_photo "$PHOTO_WITH_CORRECT_LOCATION"

    elif [[ $nfiles_with_geotag -eq 0 ]]; then
        echo
        echo "No photo with a geotag inside has been found in [$SEARCHPATH]. Please fix the geolocation of one photo there using Digikam and retry."
        echo
    elif [[ $nfiles_with_geotag -gt 1 ]]; then
        echo
        echo "$nfiles_with_geotag photos with a geotag inside have been found in [$SEARCHPATH]."
        echo
        echo "It's ambiguous which one should be used as geotag reference for all the other ones."
        echo "Please specify one of them as second positional argument for this script"
        echo
    fi

else
    copy_geotag_from_photo "$PHOTO_WITH_CORRECT_LOCATION"
fi
