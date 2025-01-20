import os
import asyncio
import aiohttp
import aiofiles
from aiohttp.helpers import BasicAuth
import logging
from tkinter import Tk, filedialog

# Configuração dos arquivos de log
LOG_DIR = "logs"
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
    # Seleção de pastas pelo usuário
    root_dirs = select_folders()
    if not root_dirs:
        logging.info("[INFO] Nenhuma pasta selecionada. Encerrando o programa.")
        return

    upload_url = r'http://192.168.1.200:8042/instances'
    max_concurrent_posts = 10  # Máximo de tarefas simultâneas
    semaphore = asyncio.Semaphore(max_concurrent_posts)
    
    for root_dir in root_dirs:
        logging.info(f"[INFO] Procurando diretórios na pasta raiz: {root_dir}")
        subdirectories = find_subdirectories(root_dir)

        for subdirectory in subdirectories:
            dicom_files = find_dicom_files(subdirectory)
            if dicom_files:
                logging.info(f"[INFO] Encontrado {len(dicom_files)} arquivos DICOM em {subdirectory}")
                await process_dicom_files(dicom_files, upload_url, semaphore)
            else:
                logging.info(f"[INFO] Nenhum arquivo DICOM encontrado em {subdirectory}")
    
    logging.info("[INFO] Todas as pastas processadas.")

def select_folders():
    """Permite ao usuário selecionar uma ou mais pastas."""
    Tk().withdraw()  # Oculta a janela principal do Tkinter
    logging.info("[INFO] Selecione as pastas para processar:")
    root_dirs = filedialog.askdirectory(mustexist=True, title="Selecione a(s) pasta(s) contendo os arquivos DICOM", multiple=True)
    return root_dirs

def find_subdirectories(root_dir):
    """Procura todos os subdiretórios da pasta raiz."""
    subdirectories = []
    for dirpath, dirnames, _ in os.walk(root_dir):
        for dirname in dirnames:
            logging.info(f"[DIR] {dirname}")
            subdirectories.append(os.path.join(dirpath, dirname))
    return subdirectories

def find_dicom_files(directory):
    """Procura todos os arquivos DICOM no diretório recebido."""
    dicom_files = []
    for dirpath, _, filenames in os.walk(directory):
        for filename in filenames:
            if is_dicom_file(filename):
                logging.info(f" [FILE] {filename}")
                dicom_files.append(os.path.join(dirpath, filename))
    return dicom_files

def is_dicom_file(filename):
    """Determina se um arquivo é do tipo DICOM baseado na extensão do arquivo."""
    return filename.lower().endswith('.dcm') or '.' not in filename

async def process_dicom_files(dicom_files, upload_url, semaphore):
    """Envia todos os arquivos DICOM da lista para o servidor Orthanc."""
    async with aiohttp.ClientSession() as session:
        tasks = [
            asyncio.create_task(upload_file(dicom_file, upload_url, semaphore, session))
            for dicom_file in dicom_files
        ]
        await asyncio.gather(*tasks)

async def upload_file(file_path, upload_url, semaphore, session):
    """Envia um arquivo para o servidor Orthanc com autenticação básica."""
    async with semaphore:
        max_retries = 5
        retry_interval = 5

        for attempt in range(1, max_retries + 1):
            try:
                async with aiofiles.open(file_path, 'rb') as f:
                    data = await f.read()

                auth = BasicAuth('admin', 'Fmsa@3459')
                async with session.post(upload_url, data=data, auth=auth) as resp:
                    if resp.status in {200, 201}:
                        if attempt > 1:
                            error_logger.error(
                                f"[ERROR] Arquivo {file_path} falhou inicialmente, mas foi enviado após {attempt} tentativa(s)."
                            )
                        logging.info(f"[INFO] Enviado {file_path}")
                        return
                    else:
                        logging.warning(f"[ERROR] Falha no envio de {file_path}, código do erro: {resp.status}")
            except Exception as e:
                logging.error(f"[ERROR] Falha no upload de {file_path}: {e}")

            if attempt < max_retries:
                logging.warning(f"[ERROR] Tentativa {attempt} falhou para {file_path}, tentando novamente em {retry_interval} segundos...")
                await asyncio.sleep(retry_interval)
            else:
                error_logger.error(f"[ERROR] Todas as tentativas falharam para o arquivo {file_path}.")

if __name__ == '__main__':
    asyncio.run(main())
