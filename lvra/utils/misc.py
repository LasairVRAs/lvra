import hashlib
from pathlib import Path
LVRA_ENV_FILE = Path(__file__).resolve().parent.parent.parent / "lvra_env.yml"
import logging
from datetime import datetime
import os
import yaml 

def set_up(settings_path: Path,
           log_name: str
          ):
    """Creates the set_up dictionary
    
    Parameters
    ----------    
    settings_path: Path
        Public settings file path. Must contain the keys: endpoint, base_dir

    Returns
    -------
    dictionary with keys:
    - kafka_server: URL of the server
    - my_topic: topic associated with filter
    - group_id: id used to keep your "place" in queue
    - base_dir: base directory for data storage
    - json_dir: where lasair input data stored
    - csv_dir: where csv feature output files stored
    - log_dir: log directory
    - log_db: sqlite log db NOT IN A YEAR/DAY SUBDIR    
    - endpoint: url endpoint Lasair
    """   
    # TODO: add a r0b_feature_version to the yaml file to put in FEATURE_SUFFIX 
        
    # The data subdirectories are organised in several levels: TYPE > YYYY > YYYYMMDD
    # so our logs and JSONS would end up in the folders:
    # $base_dir/2026/20260127 and $base_dir/JSON/2026/20260127 respectively
    # So I need the current year and day in that format to make the directories
    current_year = datetime.utcnow().strftime("%Y")
    current_day = datetime.utcnow().strftime("%Y%m%d")
    sub_dir = Path(current_year) / Path(current_day)
    

    with settings_path.open("r") as settings:
        config = yaml.safe_load(settings)
        setup_dict = {'kafka_server': config['kafka_server'],                  # URL of the server
                      'my_topic': config['my_topic'],                          # topic associated with filter
                      'group_id': config['group_id'],                          # id used to keep your "place" in queue
                      'base_dir': Path(config['base_dir']),          
                      'json_dir': Path(config['base_dir'])/ "JSON" / sub_dir,  # where lasair input data stored
                      'csv_dir':  Path(config['base_dir']) / "csv" / sub_dir,  # where csv feature output files stored
                      'log_dir':  Path(config['base_dir']) / "logs" / sub_dir, 
                      'log_db':  Path(config['base_dir']) / "db" / "log.db",   # sqlite log db NOT IN A YEAR/DAY SUBDIR    
                      'endpoint': config['endpoint'],                          # url endpoint Lasair
                     }

    logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])

    # if log file doesn't exist, create it
    setup_dict['log_dir'].mkdir(parents=True, exist_ok=True)

    logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s",
                    handlers=[logging.FileHandler(setup_dict['log_dir'] / log_name),
                        logging.StreamHandler()
                    ])
    
    logger.info(f"[INIT] - SET UP COMPLETE")

    return setup_dict, logger 


def sha256_of_file(path, chunk_size=8192):
    "Computes the SHA256 hash of a file"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()

def check_pckg_versions(env_file : Path = LVRA_ENV_FILE,
                        debug: bool = False
                        ) -> int:
    """Checks that the versions of key packages matches those required by the lvra environment file.
    The key packages checked currently are:
    - pandas
    - scikit-learn
    - numpy
    - joblib
    
    Parameters
    ----------
    env_file : Path
        Path to the lvra environment file. Default is `lvra_env.yaml` in the lvra root directory.
    
    Raises
    ------
    FileNotFoundError
        If the environment file does not exist.
    RuntimeError
        If any of the key packages do not match the required version.

    Note
    ----
    1. The key packages to check are not an input of the function because it makes it a pain to do this.
    I'm doing the low-tech version of checking by importing the packages and doing a grep on the env file.

    2. This function currently does no logging. I think that logging can be down by downstream processes, 
    e.g. if the function raises an error or does not return 0 then log the issue. 

    """

    # Check that the environment file exists
    p = Path(env_file)
    if not p.exists():
        raise FileNotFoundError(f"{p} does not exist")

    import pandas
    import sklearn
    import numpy
    import joblib
    pd_v, skl_v, np_v, joblib_v = pandas.__version__, sklearn.__version__, numpy.__version__, joblib.__version__

    from subprocess import check_output
    pd_req = check_output(f"grep -oP '(?<=pandas==).*' {env_file}", shell=True, text=True).strip()
    skl_req = check_output(f"grep -oP '(?<=scikit-learn==).*' {env_file}", shell=True, text=True).strip()
    np_req = check_output(f"grep -oP '(?<=numpy==).*' {env_file}", shell=True, text=True).strip()
    joblib_req = check_output(f"grep -oP '(?<=joblib==).*' {env_file}", shell=True, text=True).strip()

    if debug:
        print("PACKAGE      | LOADED   | REQUIRED ")
        print(f"pandas       | {pd_v}    | {pd_req}")
        print(f"sklearn      | {skl_v}    | {skl_req}")
        print(f"numpy        | {np_v}    | {np_req}")
        print(f"joblib       | {joblib_v}    | {joblib_req}")

    try:
        assert pd_v == pd_req, f"pandas version incorrect Loaded: {pd_v} | Requirement: {pd_req}"
        assert skl_v == skl_req, f"sklearn version incorrect Loaded: {skl_v} | Requirement: {skl_req}"
        assert np_v == np_req, f"numpy version incorrect Loaded: {np_v} | Requirement: {np_req}"
        assert joblib_v == joblib_req, f"joblib version incorrect Loaded: {joblib_v} | Requirement: {joblib_req} "
    except AssertionError as e:
        raise RuntimeError(f"ACTIVATE YOUR CONDA ENVIRONMENT!\n{e}")
    
    return 0


