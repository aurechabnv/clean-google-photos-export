# Clean Google Photos Export

During export, Google Photos encloses JSON files for each element exported. Those JSON files contain metadata that may be missing from the original file, such as the Date Taken for photos.

In order to ensure proper classification in other services, and clean the folders from the extra and invalid files, I have written this little bit of code.

This code:
* searches all files recursively
* deduplicates files by prioritizing photos in specific albums and removing them from year default albums
* get the proper Photo Taken date from the JSON and saves it on the corresponding file only if necessary
* moves all used JSON and other tagged file extensions in folders at the root, waiting to be manually deleted (just to be safe)

In the original export, other files are present at the root; they are not concerned by this script.

## How to install
Install requirements with pip
> pip install -r requirements

## How to run
Run script on default values:
> python clean.py

Show options:
> python clean.py --help

Run script for a given folder without deduplication:
> python clean.py "folder/path" --no-dedup

A log file will be produced in the working directory.


## Custom settings
Three settings can be updated directly into the JSON file `settings.json`:
* `DEFAULT_TARGET_DIR`: default directory to be searched and cleansed
* `DEDUPLICATE_FILES`: defaulted to `true`; set to `false` to skip file deduplication
* `FILES_TO_UPDATE`: list of extensions which will be updated 
* `FILES_TO_ARCHIVE`: list of extensions which will be removed (/!\ JSON files are treated along with their photo/video counterpart and should NOT be added here)
* `ARCHIVE_FOLDER_NAME`: name of the archive folder to be generated