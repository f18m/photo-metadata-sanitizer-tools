#!/bin/bash

# This script uses RawTherapee's command line interface to convert CR2 files to JPEG format.
# To install RawTherapee on Fedora Linux, use:
# sudo dnf install rawtherapee
#
# See https://rawpedia.rawtherapee.com/Command-Line_Options

DIRECTORY_WITH_CR2_FILES="$1"
#FILES=( "$DIRECTORY_WITH_CR2_FILES/*.cr2" )

OIFS="$IFS"
IFS=$'\n'
FILES=($(find "$DIRECTORY_WITH_CR2_FILES" -type f -name *.cr2))
IFS="$OIFS"

echo "Detected ${#FILES[@]} files:"
#echo "${FILES[@]}"
for f in "${FILES[@]}"; do 
    echo "  $f"
done
echo

echo "Now starting conversion to JPEG..."
for f in "${FILES[@]}"; do 

    # please note that rawtherapee-cli will create the JPEG file in the same directory as the CR2 file
    # and with the same name, just with .jpg extension
    # If a .jpg file already exists, rawtherapee-cli will just skip the conversion, so this script is safe
    # to run multiple times on the same directory
    rawtherapee-cli -c "$f"
done
