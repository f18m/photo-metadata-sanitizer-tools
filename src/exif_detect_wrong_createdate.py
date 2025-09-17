#!/usr/bin/env python3

# This Python script can be used against a directory organized with  year-based subdirectories like:
# 
# /base/path/
# ├── 2020
# │   ├── img1.jpg
# │   ├── img2.png
# │   └── video1.mp4
# ├── 2021
# │   ├── img3.jpg
# │   └── video2.mov
# └── 2022
#     ├── img4.jpeg
#     └── video3.avi
#
# The script is able to detect both pictures and videos whose metadata "Create Date" tag is either
# missing or does not match the year of the enclosing directory.
#
# Compared to use of "exiftool" command line tool, this script is faster because with exiftool
# 3 passes on the same files are needed:
#
#    echo "Pass1: Searching for files NOT having the year $YEAR in the DateTimeOriginal field in $SEARCHPATH"
#    /usr/bin/exiftool -r -if 'not ($DateTimeOriginal =~ /^'$YEAR'/)' -p '$FilePath'  $SEARCHPATH > /tmp/exiftool_search_wrong_metadata.txt
#    echo "Pass2: Searching for files NOT having the year $YEAR in the CreateDate field in $SEARCHPATH"
#    /usr/bin/exiftool -r -if 'not ($CreateDate =~ /^'$YEAR'/)' -p '$FilePath'  $SEARCHPATH >> /tmp/exiftool_search_wrong_metadata.txt
#    echo "Pass3: Searching for files NOT having the EXIF DateTimeOriginal/CreateDate field at all in $SEARCHPATH"
#    /usr/bin/exiftool -r -if '(not $CreateDate) and (not $DateTimeOriginal)' -p '$FilePath' $SEARCHPATH >> /tmp/exiftool_search_wrong_metadata.txt
#
# While this script can detect the wrong files all in a single pass.
# This script is read-only and will not change any file.
# The script generates a text file named "<year>_non_matching_files.txt" in the current directory
# containing the list of files that do not match the expected year in their metadata.
# Usage example:
#   python3 exif_detect_wrong_createdate.py /base/path --dry-run
#
# Example of the time it takes to process 46000 pictures and 2000 videos:
#   real	33m39.110s
#   user	3m51.750s
#   sys 	1m6.454s
#


import os
import argparse
import exif
import ffmpeg
from PIL import Image, ExifTags
from enum import Enum
from typing import Tuple
from datetime import datetime

image_files_with_EXIF_metadata = (".jpg", ".jpeg", ".png", ".tiff", ".heic", ".gif")
video_files_for_ffmpeg = (".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv")
ignore_files = (".cr2")


class ProcessingResult(Enum):
    VALID_CREATION_TIMESTAMP = 1

    # errors
    FAILED_TO_READ = 2
    NO_METADATA = 3
    INVALID_TIMESTAMP_FORMAT = 4

class MetadataProcessor:
    def __init__(self, verbose=0):
        self.exif_DateTimeOriginal_tag = 0
        self.exit_DateTimeDigitized_tag = 0
        self.exif_DateTime_tag = 0
        self.verbose = verbose

        # get the actual tag IDs for DateTimeOriginal and CreateDate
        for tag, value in ExifTags.TAGS.items():
            if value == "DateTimeOriginal":
                self.exif_DateTimeOriginal_tag = tag
                #rint("DateTimeOriginal tag is", tag)
            elif value == "DateTimeDigitized":
                self.exit_DateTimeDigitized_tag = tag
                #print("DateTimeDigitized tag is", tag)
            elif value == "DateTime":
                self.exif_DateTime_tag = tag
                #print("DateTime tag is", tag)
        pass

    @staticmethod
    def try_parse_date(date_str: str, date_format: str) -> datetime:
        try:
            date_parsed = datetime.strptime(date_str, date_format)
            return date_parsed
        except ValueError:
            return None

    def get_creation_date(self, file_path: str) -> Tuple[ProcessingResult, datetime]:
        """
        Given a file path, try to extract the creation date from its metadata.
        Returns a tuple (ProcessingResult, datetime) where ProcessingResult indicates
        the outcome of the operation and datetime is the parsed creation date if successful,
        or None otherwise.
        """

        date_str = ""
        date_formats = []

        try:
            if file_path.lower().endswith(image_files_with_EXIF_metadata):
                with Image.open(file_path) as img:
                    exif_data = img._getexif()
                    if not exif_data:
                        return (ProcessingResult.NO_METADATA, None)

                    if self.verbose > 2:
                        print(f"Dump of EXIF data for [{file_path}]:")
                        for k, v in exif_data.items():
                            print(f"  Tag {k} -> Value {v}")

                    # Try DateTimeOriginal first, then DateTimeDigitized, then DateTime
                    for key in [self.exif_DateTimeOriginal_tag, self.exit_DateTimeDigitized_tag, self.exif_DateTime_tag]:
                        if key in exif_data:
                            date_str = exif_data[key]
                            # EXIF timestamp format should always be: "YYYY:MM:DD HH:MM:SS"
                            date_formats.append("%Y:%m:%d %H:%M:%S")
                            break
                    if date_str == "":
                        return (ProcessingResult.NO_METADATA, None)
                    
                    # fall through

            elif file_path.lower().endswith(video_files_for_ffmpeg):
                probe = ffmpeg.probe(file_path)
                if "format" in probe and "tags" in probe["format"]:
                    tags = probe["format"]["tags"]
                    if "creation_time" in tags:
                        # contrary to EXIF, here the format is _usually_ ISO 8601
                        # e.g.: "YYYY-MM-DDTHH:MM:SS.000000Z"
                        # however I found several .AVI files written by old cameras
                        # with a different format, so try both
                        date_str = tags["creation_time"]
                        date_formats.append("%Y-%m-%dT%H:%M:%S.%fZ")
                        date_formats.append("%Y-%m-%d %H:%M:%S.%fZ")
                        date_formats.append("%Y-%m-%d %H:%M:%S")
                        date_formats.append("%Y:%m:%d %H:%M:%S")

                        # fall through
                    else:
                        return (ProcessingResult.NO_METADATA, None)
                else:
                    return (ProcessingResult.NO_METADATA, None)
            else:
                # Unsupported file type
                return (ProcessingResult.FAILED_TO_READ, None)
        except ffmpeg.Error:
            return (ProcessingResult.FAILED_TO_READ, None)
        except Exception:
            return (ProcessingResult.FAILED_TO_READ, None)
        
        if self.verbose > 1:
            print(f"File [{file_path}] has creation date string: '{date_str}'. Trying formats: {date_formats}")

        # now try to parse the timestamp string
        for date_format in date_formats:
            date_parsed = MetadataProcessor.try_parse_date(date_str, date_format)
            if date_parsed is not None:
                return (ProcessingResult.VALID_CREATION_TIMESTAMP, date_parsed)
            #else: try next format

        if self.verbose > 1:
            print(f"File [{file_path}] has an invalid timestamp format: '{date_str}'. Tried formats: {date_formats}")

        return (ProcessingResult.INVALID_TIMESTAMP_FORMAT, None)


    def process_directory(self, search_path: str, year: int):
        matching_files = []
        non_matching_files = []
        failed_to_read_files = []

        for root, _, files in os.walk(search_path):
            for name in files:
                file_path = os.path.join(root, name)
                if file_path.lower().endswith(ignore_files):
                    continue # silently skip

                processing_result, creation_date = self.get_creation_date(file_path)
                if self.verbose > 0:
                    print(f"File [{file_path}] processing result: {processing_result.name}, creation date: {creation_date}")

                if processing_result == ProcessingResult.VALID_CREATION_TIMESTAMP and creation_date.year == year:
                    matching_files.append(file_path)
                elif processing_result == ProcessingResult.VALID_CREATION_TIMESTAMP and creation_date.year != year:
                    non_matching_files.append(file_path)
                elif processing_result == ProcessingResult.NO_METADATA:
                    non_matching_files.append(file_path)
                else:
                    # all failure conditions (no metadata, corrupted file, invalid timestamp format, etc) end up here
                    failed_to_read_files.append(file_path + f" (error code: {processing_result.name})")

        total_files = len(matching_files) + len(non_matching_files) + len(failed_to_read_files)

        # write non matching files to a text file
        output_file = f"{year}_non_matching_files.txt"
        if len(non_matching_files) > 0:
            perc = round((len(non_matching_files) / total_files) * 100, 2) if total_files > 0 else 0
            print(f"Found {len(non_matching_files)}/{total_files} ({perc}%) files that have wrong CreateDate metadata. Writing them in the output file {output_file}")
            with open(output_file, "w") as f:
                for file in non_matching_files:
                    f.write(f"{file}\n")
        else:
            if self.verbose > 0:
                print(f"All {total_files} files have correct CreateDate metadata.")
            # if the output file already exists, remove it
            if os.path.exists(output_file):
                os.remove(output_file)

        output_file = f"{year}_failed_to_read_files.txt"
        if len(failed_to_read_files) > 0:
            print(f"Found {len(failed_to_read_files)}/{total_files} files that failed to read EXIF metadata. Writing them in the output file {output_file}")
            # write failed to read files to a text file
            with open(output_file, "w") as f:
                for file in failed_to_read_files:
                    f.write(f"{file}\n")
        else:
            if self.verbose > 0:
                print(f"All {total_files} files were read successfully.")
            # if the output file already exists, remove it
            if os.path.exists(output_file):
                os.remove(output_file)

def main():
    parser = argparse.ArgumentParser(
        description="Detect files with wrong CreateDate metadata inside a base directory having per-year folders."
    )
    parser.add_argument("--verbose", type=int, help="Enable verbose output", default=0)
    parser.add_argument("--year", type=int, help="Specify the year to process (e.g., 2020). If not specified, all year-named subdirectories will be processed.")
    parser.add_argument("path", type=str, help="Base directory path where year-based subdirectories are located. Alternatively this can be a single file to test this script.")

    args = parser.parse_args()

    verbosity_level = args.verbose if args.verbose is not None else 0

    # walk over all files in the directory args.path
    if os.path.isfile(args.path):
        print(f"Processing only the specified file {args.path}")

        pp = MetadataProcessor(verbosity_level)
        processing_result, creation_date = pp.get_creation_date(args.path)
        if processing_result == ProcessingResult.VALID_CREATION_TIMESTAMP:
            print(f"The specified file {args.path} has valid creation timestamp: {creation_date} (year is {creation_date.year})")
        elif processing_result == ProcessingResult.FAILED_TO_READ:
            print(f"Error: Failed to read the specified file {args.path}")
        elif processing_result == ProcessingResult.NO_METADATA:
            print(f"Error: file {args.path} does not have the 'CreateDate' metadata tag(s)")
        elif processing_result == ProcessingResult.INVALID_TIMESTAMP_FORMAT:
            print(f"Error: file {args.path} has an invalid timestamp format within the 'CreateDate' metadata tag(s)")

        return
    elif args.year:
        chosen_path = os.path.join(args.path, str(args.year))
        if not os.path.exists(chosen_path):
            print(f"Error: The specified path for year {args.year} does not exist: {chosen_path}")
            return
        print(f"Processing only year {args.year}")
        selected_directories = [chosen_path]
    else:
        # search in all numeric directories nested in args.path
        selected_directories = []
        for dirname in sorted(os.listdir(args.path)): 
            if not dirname.isdigit() or len(dirname) != 4:
                print(f"Skipping non-year directory {dirname}")
                continue
            selected_directories.append(os.path.join(args.path, dirname))

    pp = MetadataProcessor(verbosity_level)
    for full_dir_path in sorted(selected_directories):
        dirname = os.path.basename(full_dir_path)
        year_for_path = int(dirname)
        print(f"Processing directory {full_dir_path} for year {year_for_path}")
        pp.process_directory(full_dir_path, year_for_path)

    print("All processing done.")
    print("Use the script exif_fix_createdate.py to fix the files listed in the generated text files.")


if __name__ == "__main__":
    main()
