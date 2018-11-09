# Via

This provides a simple Python flask implementation of the VGG Image Annotator, allowing for some python scripting to augment the experience (e.g., pulling in reports, etc)

To use, first run "python accession_filename.py" to generate a pickel file linking the accession numbers to the image filenames you will be working with.

Then run "python app.py" to start the service.  Type in the name of the pickel file you generated above, then enter your mpower username and password if you'd like to pull in reports automatically. 