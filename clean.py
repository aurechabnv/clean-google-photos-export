from datetime import datetime
import json
import logging
from pathlib import Path
import os
import piexif
import typer

logging.basicConfig(level=logging.DEBUG,
                    filename="logs.log",
                    filemode="w",
                    format="%(asctime)s - %(levelname)s - %(message)s")


def log_console(log_message: str):
    logging.info(log_message)
    typer.echo(log_message)


def warn_console(log_message: str):
    logging.warning(log_message)
    typer.secho(message=log_message, color=typer.colors.RED)


SOURCE_FILE = Path(__file__).resolve()
SOURCE_DIR = SOURCE_FILE.parent

# load settings from json file
with open(SOURCE_DIR / "settings.json", "r") as settings_file:
    json_settings = json.load(settings_file)

# Elements to process include both update and archive
EXT_TO_ARCHIVE: list = json_settings.get("FILES_TO_ARCHIVE")
EXT_TO_PROCESS: list = json_settings.get("FILES_TO_UPDATE")
EXT_TO_PROCESS.extend(EXT_TO_ARCHIVE)

target_dir = json_settings.get("TARGET_DIR")
if bool(target_dir) and Path(target_dir).exists():
    log_console(f"Searching in target directory: {target_dir}")
    DATA_DIR = Path(target_dir)
else:
    log_console(f"Searching in default directory")
    DATA_DIR = SOURCE_DIR / "data"

if not DATA_DIR.exists():
    warn_console("A target folder must be defined.")

ARCHIVE_DIR = DATA_DIR / "ARCHIVE"
WORKING_DIR = DATA_DIR


def get_json_file(working_file):
    json_file = working_file.parent / f"{working_file.name}.json"

    # File might already be archived (if rerun)
    if not json_file.exists():
        json_file = ARCHIVE_DIR / "json" / working_file.parts[-2] / json_file.name

    return json_file


def archive_file(path: Path):
    file_type = path.suffix.strip(".")
    output_dir = ARCHIVE_DIR / file_type / path.parts[-2]
    output_dir.mkdir(exist_ok=True, parents=True)

    if path.parent != output_dir:
        path.rename(output_dir / path.name)
        logging.debug(f"{file_type.upper()} file has been archived")
        return 1

    logging.debug(f"{file_type.upper()} file already archived")
    return 0


def get_photo_taken_date(json_file):
    with open(json_file, "r") as gfile:
        google_metadata = json.load(gfile)
        photo_taken_time_timestamp = google_metadata['photoTakenTime']['timestamp']
        return datetime.fromtimestamp(int(photo_taken_time_timestamp))


def exif_date_to_datetime(exif_date):
    date_string = str(exif_date).strip('b\'')
    return datetime.strptime(date_string, "%Y:%m:%d %H:%M:%S")


def update_metadata(file_path: Path, json_date_time: datetime):
    logging.debug(f"JSON datetime: {json_date_time}")

    path = str(file_path)

    if file_path.suffix.lower() in [".jpg", ".jpeg"]:
        exif_dict: dict = piexif.load(path)

        date_time = exif_dict['0th'].get(piexif.ImageIFD.DateTime)
        date_time_original = exif_dict['Exif'].get(piexif.ExifIFD.DateTimeOriginal)
        date_time_digitized = exif_dict['Exif'].get(piexif.ExifIFD.DateTimeDigitized)
        logging.debug(f"date_time: {date_time}")
        logging.debug(f"date_time_original: {date_time_original}")
        logging.debug(f"date_time_digitized: {date_time_digitized}")

        if date_time is not None and date_time_original is not None and date_time_digitized is not None:
            date_time = exif_date_to_datetime(date_time)
            date_time_original = exif_date_to_datetime(date_time_original)
            date_time_digitized = exif_date_to_datetime(date_time_digitized)

            logging.debug(f"Original datetime: {date_time_original}")

            if date_time.date() == json_date_time.date() and date_time_original.date() == json_date_time.date() and date_time_digitized.date() == json_date_time.date():
                logging.debug("Skip update")
                return False

        json_date_time_str = json_date_time.strftime("%Y:%m:%d %H:%M:%S")

        exif_dict['0th'][piexif.ImageIFD.DateTime] = json_date_time_str
        exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = json_date_time_str
        exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = json_date_time_str

        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, path)

    os.utime(path, (datetime.timestamp(json_date_time), datetime.timestamp(json_date_time)))
    return True


def main():
    # Get all files to process recursively
    files_to_process = [f for f in WORKING_DIR.rglob("*") if f.is_file() and f.suffix.lower() in EXT_TO_PROCESS]

    if len(files_to_process) == 0:
        warn_console("No files to process")
        return

    deduplicated_files = 0
    skipped_files = 0
    updated_files = 0
    archived_files = 0

    log_console(f"{len(files_to_process)} files to process")

    # Deduplicate files
    with typer.progressbar(files_to_process, label="Deduplicating files...") as progress:
        # check if file has a duplicate
        for file in progress:
            duplicates = [file]
            files_to_dedup = files_to_process.copy()
            for f in files_to_dedup:
                found = f.parent != file.parent and f.name == file.name
                if found is True:
                    duplicates.append(f)
                    files_to_dedup.remove(f)
            if len(duplicates) > 1:
                # keep the file coming from specific albums (not year folders)
                for dup in duplicates:
                    if str(dup.parent).find("Photos from") != -1:
                        dup_json = get_json_file(dup)
                        archived_files += archive_file(dup_json)
                        deduplicated_files += archive_file(dup)
                        files_to_process.remove(dup)

    # Process remaining files
    with typer.progressbar(files_to_process, label="Processing remaining files...") as progress:
        for f in progress:
            logging.info(f.name)

            # archive designated files
            if f.suffix.lower() in EXT_TO_ARCHIVE:
                archived = archive_file(path=f)
                if archived:
                    archived_files += 1
                else:
                    skipped_files += 1
                pass

            # process valid images and videos
            # get date from google json and save on file if necessary
            else:
                # get date from google photos json file and update photo if necessary
                json_file = get_json_file(working_file=f)
                photo_taken_date = get_photo_taken_date(json_file)
                updated = update_metadata(file_path=f, json_date_time=photo_taken_date)

                if updated:
                    updated_files += 1
                else:
                    skipped_files += 1

                archived_files += archive_file(path=json_file)

    log_console(f"{deduplicated_files} deduplicated files, {updated_files} updated files, {skipped_files} skipped files, {archived_files} archived files")


if __name__ == "__main__":
    main()
