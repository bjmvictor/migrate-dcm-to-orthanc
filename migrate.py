import os
import asyncio
import aiohttp
import aiofiles
import config
from aiohttp.helpers import BasicAuth
import logging
from tkinter import Tk, filedialog

# Logfile configuration
LOG_DIR = config.logDir
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "upload_log.txt")
ERROR_LOG_FILE = os.path.join(LOG_DIR, "error_log.txt")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ]
)

error_logger = logging.getLogger("error_logger")
error_logger.addHandler(logging.FileHandler(ERROR_LOG_FILE))

async def main():
    # Select dicom folder
    root_dirs = select_folders()
    if not root_dirs:
        logging.info("[INFO] No folder was selected, closing.")
        return
    
    prefix = 'https' if config.useHttps else 'http'
    
    upload_url = f'{prefix}://{config.host}:{config.port}/instances'
    max_concurrent_posts = config.maxTasks  # Max of tasks
    semaphore = asyncio.Semaphore(max_concurrent_posts)
    
    for root_dir in root_dirs:
        logging.info(f"[INFO] Finding for directories on root: {root_dir}")
        subdirectories = find_subdirectories(root_dir)

        for subdirectory in subdirectories:
            dicom_files = find_dicom_files(subdirectory)
            if dicom_files:
                logging.info(f"[INFO] Find {len(dicom_files)} dicom files on {subdirectory}")
                await process_dicom_files(dicom_files, upload_url, semaphore)
            else:
                logging.info(f"[INFO] No dicom files found on {subdirectory}")
    
    logging.info("[INFO] All folders have been completed.")

def select_folders():
    """Allows the user to select one or more folders."""
    Tk().withdraw()  # Hide the TKinter window
    logging.info("[INFO] Select one or more folders. Click Cancel when finished.")
    directories = []
    while True:
        folder = filedialog.askdirectory(mustexist=True, title="Select a folder containing the DICOM files")
        if not folder:  # If the user clicks "Cancel"
            break
        directories.append(folder)
        logging.info(f"[INFO] Selected: {folder}")
    return directories


def find_subdirectories(root_dir):
    """Find all subdirectories on root's folder"""
    subdirectories = []
    for dirpath, dirnames, _ in os.walk(root_dir):
        for dirname in dirnames:
            logging.info(f"[DIR] {dirname}")
            subdirectories.append(os.path.join(dirpath, dirname))
    return subdirectories

def find_dicom_files(directory):
    """Searches all DICOM files in the received directory"""
    dicom_files = []
    for dirpath, _, filenames in os.walk(directory):
        for filename in filenames:
            if is_dicom_file(filename):
                logging.info(f" [FILE] {filename}")
                dicom_files.append(os.path.join(dirpath, filename))
    return dicom_files

def is_dicom_file(filename):
    """Determines whether a file is of type DICOM based on the file extension"""
    return filename.lower().endswith('.dcm') or '.' not in filename

async def process_dicom_files(dicom_files, upload_url, semaphore):
    """Sends all DICOM files in the list to the Orthanc server"""
    async with aiohttp.ClientSession() as session:
        tasks = [
            asyncio.create_task(upload_file(dicom_file, upload_url, semaphore, session))
            for dicom_file in dicom_files
        ]
        await asyncio.gather(*tasks)

async def upload_file(file_path, upload_url, semaphore, session):
    """Sends a file to the Orthanc server with basic authentication."""
    async with semaphore:
        max_retries = config.maxRetries
        retry_interval = config.retryInterval

        for attempt in range(1, max_retries + 1):
            try:
                async with aiofiles.open(file_path, 'rb') as f:
                    data = await f.read()

                auth = BasicAuth(config.user, config.password)
                async with session.post(upload_url, data=data, auth=auth) as resp:
                    if resp.status in {200, 201}:
                        if attempt > 1:
                            error_logger.error(
                                f"[ERROR] File {file_path} has send after {attempt} trie(s)."
                            )
                        logging.info(f"[INFO] Send {file_path}")
                        return
                    else:
                        logging.warning(f"[ERROR] Failed to send {file_path}, error code: {resp.status}")
            except Exception as e:
                logging.error(f"[ERROR] Fail to upload {file_path}: {e}")

            if attempt < max_retries:
                logging.warning(f"[ERROR] Tries {attempt} failed to {file_path}, trying again in {retry_interval} seconds...")
                await asyncio.sleep(retry_interval)
            else:
                error_logger.error(f"[ERROR] All attempts failed for the file {file_path}.")

if __name__ == '__main__':
    asyncio.run(main())
