#!/bin/bash

year=${1}
file_path="${2}"

create_date="${year}:01:01 00:00:00"
exiftool \
    -overwrite_original \
    -DateTimeOriginal="${create_date}" \
    -CreateDate="${create_date}" \
    -DateCreated="${create_date}" \
    "${file_path}"
