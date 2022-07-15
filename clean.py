from datetime import datetime
import json
import logging
from pathlib import Path
import os
import piexif
import typer

EXT_TO_PROCESS = (".jpg", ".jpeg", ".png", ".mp4", ".mp")
EXT_TO_ARCHIVE = (".mp", ".json")

SOURCE_FILE = Path(__file__).resolve()
SOURCE_DIR = SOURCE_FILE.parent
DATA_DIR = SOURCE_DIR / "data"
WORKING_DIR = DATA_DIR

logging.basicConfig(level=logging.DEBUG,
                    filename="clean.log",
                    filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")


def get_json_file(parent_dir, working_file):
    json_file = parent_dir / f"{working_file.name}.json"

    if not json_file.exists():
        json_file = DATA_DIR / "json" / json_file.name

    return json_file


def archive_file(path: Path):
    file_type = path.suffix.strip(".")
    output_dir = DATA_DIR / file_type
    output_dir.mkdir(exist_ok=True)

    if path.parent != output_dir:
        # duplicates are possible across folders and we want to keep all
        if Path(output_dir / path.name).exists():
            path.rename(output_dir / f"{path.stem}-{str(datetime.now().timestamp())}{path.suffix}")
        else:
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
        logging.debug(exif_dict)

        date_time = exif_dict['0th'].get(piexif.ImageIFD.DateTime)
        date_time_original = exif_dict['Exif'].get(piexif.ExifIFD.DateTimeOriginal)
        date_time_digitized = exif_dict['Exif'].get(piexif.ExifIFD.DateTimeDigitized)

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
    files_to_update = [f for f in WORKING_DIR.glob("**/*") if f.is_file() and f.suffix.lower() in EXT_TO_PROCESS]

    skipped_files = 0
    updated_files = 0
    archived_files = 0

    logging.info(f"{len(files_to_update)} files to process")

    with typer.progressbar(files_to_update) as progress:
        for f in progress:
            logging.info(f.name)

            # archive designated files
            if f.suffix.lower() in EXT_TO_ARCHIVE:
                archive_file(path=f)
                logging.debug("File archived")
                archived_files += 1
                pass

            # process valid images and videos
            # get date from google json and save on file if necessary
            else:
                parent_dir = f.parent
                json_file = get_json_file(parent_dir=parent_dir, working_file=f)

                photoTakenTime = get_photo_taken_date(json_file)
                updated = update_metadata(file_path=f, json_date_time=photoTakenTime)

                if updated:
                    updated_files += 1
                else:
                    skipped_files += 1

                archived_files += archive_file(path=json_file)

    logging.info(f"{updated_files} updated files")
    logging.info(f"{skipped_files} skipped files")
    logging.info(f"{archived_files} archived files")


if __name__ == "__main__":
    main()
