from datetime import datetime
import json
import logging
from pathlib import Path
import os
from typing import List, Optional

import piexif
import typer

app = typer.Typer()

# Source file constants
SOURCE_FILE = Path(__file__).resolve()
SOURCE_DIR = SOURCE_FILE.parent

# LOGGING
logging.basicConfig(level=logging.DEBUG,
                    filename=f"logs/logs-{datetime.now().timestamp()}.log",
                    filemode="w",
                    format="%(asctime)s - %(levelname)s - %(message)s")


def log_console(log_message: str):
    """
    Log a message both to the console and into the logs
    Args:
        log_message: message to print
    """
    logging.info(log_message)
    typer.echo(log_message)


def warn_console(log_message: str):
    """
    Log a warning message both to the soncole and into the logs
    Args:
        log_message: message to print
    """
    logging.warning(log_message)
    typer.secho(message=log_message, fg=typer.colors.RED)


# Load default settings from json file
SETTINGS = {}
with open(SOURCE_DIR / "settings.json", "r") as settings_file:
    SETTINGS = json.load(settings_file)

# File extensions to process must include both update and archive
EXT_TO_ARCHIVE: list = SETTINGS.get("FILES_TO_ARCHIVE")
EXT_TO_UPDATE: list = SETTINGS.get("FILES_TO_UPDATE")
EXT_TO_PROCESS = EXT_TO_UPDATE.copy()
EXT_TO_PROCESS.extend(EXT_TO_ARCHIVE)

# Processing trackers
trackers = {
    "deduplicated_files": 0,
    "skipped_files": 0,
    "updated_files": 0,
    "archived_files": 0,
}


def get_archive_dir(file: Path) -> Path:
    """
    Get the archive folder path corresponding to the passed file
    Args:
        file: File from which compute the archive path

    Returns: Archive folder path

    """
    archive_folder_name = SETTINGS.get("ARCHIVE_FOLDER_NAME")
    if archive_folder_name not in file.parts:
        # Locate the archive folder in the parent folder of targeted folder
        target_dir = Path(SETTINGS.get("target_dir"))
        archive_dir = target_dir.parent / archive_folder_name / file.parent.relative_to(target_dir)
    else:
        archive_dir = file.parent
    return archive_dir


def get_json_file(working_file: Path) -> Path:
    """
    Get the corresponding JSON file of the passed file
    Args:
        working_file: Image or video file

    Returns: JSON file

    """
    json_file = working_file.parent / f"{working_file.name}.json"
    # File might already be archived (if rerun)
    if not json_file.exists():
        json_file = get_archive_dir(working_file) / json_file.name

    return json_file


def archive_file(file: Path) -> bool:
    """
    Archive the given file for later manual deletion
    Args:
        file: File to be archived

    Returns: True if archived

    """
    output_dir = get_archive_dir(file)
    output_dir.mkdir(exist_ok=True, parents=True)

    if file.parent != output_dir:
        file.rename(output_dir / file.name)
        logging.debug(f"{file.name} has been archived")
        return True

    logging.debug(f"{file.name} already archived")
    return False


def get_photo_taken_date(json_file: Path) -> datetime:
    """
    Extract the Photo Taken Time date from the passed JSON file
    Args:
        json_file: JSON file from which extract info

    Returns: Photo Taken Time date

    """
    with open(json_file, "r") as gfile:
        google_metadata = json.load(gfile)
        photo_taken_time_timestamp = google_metadata['photoTakenTime']['timestamp']
        return datetime.fromtimestamp(int(photo_taken_time_timestamp))


def exif_date_to_datetime(exif_date: bytes) -> datetime:
    """
    Convert the exif date to datetime
    Args:
        exif_date: date coming from exif

    Returns: Converted datetime

    """
    date_string = str(exif_date).strip('b\'')
    return datetime.strptime(date_string, "%Y:%m:%d %H:%M:%S")


def update_metadata(file_path: Path, json_date_time: datetime) -> bool:
    """
    Update the dates in the file's metadata
    Args:
        file_path: File to update
        json_date_time: Date value to use

    Returns: True if updated

    """
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


def deduplicate_files(files: List[Path]) -> List[Path]:
    """
    Deduplicate passed files and archive duplicates and their JSON counterparts
    Args:
        files: List of files

    Returns: Deduplicated list of files

    """
    with typer.progressbar(files, label="1/3 Deduplicating files...") as progress:
        for file in progress:
            logging.info(file.name)
            duplicates = []
            files_to_dedup = files.copy()

            # check if file has duplicates and set them aside
            for f in files_to_dedup:
                found = f.parent != file.parent and f.name == file.name
                if found:
                    duplicates.append(f)
                    files_to_dedup.remove(f)
            logging.info(f"{len(duplicates)} duplicates found")

            if len(duplicates) > 0:
                # add first file in comparison
                duplicates.append(file)

                # archive the files coming from year folders and their JSON  files
                for dup in duplicates:
                    if str(dup.parent).find("Photos from") != -1:
                        dup_json = get_json_file(dup)
                        if dup_json.exists():   
                            trackers["archived_files"] += archive_file(dup_json)
                            trackers["deduplicated_files"] += archive_file(dup)
                        files.remove(dup)
    return files


def update_files(files):
    """
    Update files according to their extensions:
        - files are processed for date update if current date and JSON date are different
        - JSON files corresponding to the processed files are archived after processing
    Args:
        files: List of files to process

    """
    do_dedup = SETTINGS.get("do_dedup")
    with typer.progressbar(files, label=f"{'2/3' if do_dedup else '1/2'} Update files...") as progress:
        for f in progress:
            logging.info(f.name)

            # get date from google photos json file and update photo if necessary
            json_file = get_json_file(working_file=f)
            if json_file.exists():
                photo_taken_date = get_photo_taken_date(json_file)
                updated = update_metadata(file_path=f, json_date_time=photo_taken_date)
            else:
                logging.debug("No JSON, skip update")
                updated = False

            if updated:
                trackers["updated_files"] += 1
            else:
                trackers["skipped_files"] += 1

            trackers["archived_files"] += archive_file(file=json_file)


def archive_files(files):
    """
    Archive files according to their extensions as defined in `EXT_TO_ARCHIVE` 
    Args:
        files: List of files to process

    """
    do_dedup = SETTINGS.get("do_dedup")
    with typer.progressbar(files, label=f"{'3/3' if do_dedup else '2/2'} Archive files...") as progress:
        for f in progress:
            logging.info(f.name)

            archived = archive_file(file=f)
            if archived:
                trackers["archived_files"] += 1
            else:
                trackers["skipped_files"] += 1


@app.command("run")
def main(directory: Optional[str] = typer.Argument(SETTINGS.get("DEFAULT_TARGET_DIR"), help="Folder to be deep-searched"),
         dedup: bool = typer.Option(SETTINGS.get("DEDUPLICATE_FILES"), help="Find and archive duplicates")):

    if bool(directory) is False or not Path(directory).exists():
        warn_console("A target folder must be defined in the JSON settings or as an argument.")
        raise typer.Exit()

    SETTINGS["target_dir"] = directory
    SETTINGS["do_dedup"] = dedup

    # Get all files to process recursively
    files_to_process = [f for f in Path(directory).rglob("*") if f.is_file() and f.suffix.lower() in EXT_TO_PROCESS]

    if len(files_to_process) == 0:
        warn_console("No files to process")
        raise typer.Exit()
    log_console(f"{len(files_to_process)} files to process")

    files_to_dedup = [f for f in files_to_process if f.suffix.lower() in EXT_TO_UPDATE]
    # 1 Deduplicate files and get new list of files
    if dedup:
        deduplicated_files = deduplicate_files(files_to_dedup)
    else:
        deduplicated_files = files_to_dedup

    # 2 Update files
    update_files(deduplicated_files)

    # 3 Archive other files
    files_to_archive = [f for f in Path(directory).rglob("*") if f.is_file() and f.suffix.lower() in EXT_TO_ARCHIVE]
    archive_files(files_to_archive)

    log_console(f"{trackers['deduplicated_files']} deduplicated files, {trackers['updated_files']} updated files, {trackers['skipped_files']} skipped files, {trackers['archived_files']} archived files")


if __name__ == "__main__":
    app()
