# Clean Google Photos Export

During export, Google Photos encloses JSON files for each element exported. Those JSON files contain metadata that may be missing from the original file, such as the Date Taken for photos.

In order to ensure proper classification in other services, and clean the folders from the extra and invalid files, I have written this little bit of code.

This code:
* searches all files recursively
* saves the proper date on the file if it is incorrect
* moves all used JSON and other tagged file extensions in folders at the root, waiting to be manually deleted (just to be safe)

In the original export, other files are present at the root; they are not concerned by this script.