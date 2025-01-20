# Migrate dicom files to Orthanc Pacs
A useful tool to migrate dicom files to a orthanc server

<h3> When this tool is necessary? </h3>

When you have a large volume of DICOM files and need to send them to the Orthanc server automatically.

NOTE: This tool is used when DCM files are not compressed as ZIP or 7ZIP.. If this is your case, you'll need to adapt the code to find and unpack before sending, or do this manually before running.

<h3> How to use? </h3>

1. First you need to install <a href="https://www.python.org/">Python</a> and dependencies using the following commands:
   - pip install asyncio
   - pip install aiohttp
   - pip install aiofiles
   - pip install logging
2. Open the config.py using a text editor and change the <strong>host, port, an password</strong> if your Orthanc acess need authentication.
3. Open cmd in the root directory of the tool and run the code using:
   - py migrate.py
4. Select the folder that have the DICOM files and confirm
