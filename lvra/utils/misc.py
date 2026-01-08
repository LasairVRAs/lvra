import hashlib
from pathlib import Path
LVRA_ENV_FILE = Path(__file__).resolve().parent.parent.parent / "lvra_env.yml"

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


