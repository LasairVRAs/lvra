# Local version of lvra
`2025-12-02`

Some aspects of the lasair VRA are only used for training purposes, not for production (i.e predictions and annotation), however at the current stage I think the code should all be in one package and if further modularisation is needed I'll do it later. 

**For now I need to have a local environment that resembled the Oxford Lasair server as much as possible** for training and testing. 

## Syncing remote and local environements
I am not going to use docker for now. Since I'm on linux I'm hoping there won't be OS shenanigans getting in the way.

The main thing I have to look out for are:
1) Python environments
2) Environment variables

### Python
For the python environment I exported a `yaml` file of the remote conda environement:
```bash
conda env export --no-builds > lvra_env.yml
```
Then I copied it in my local package:

```bash
scp lasair@oxdb1:code/lvra_env.yml ./software/lvra 
```
Then I created the environment with:
```bash
conda env create -f software/lvra/lvra_env.yml  -n lvra
```

**In the future I can just update this yaml file using `conda env export`, commit and push it, and update the environement** whether it be local or remote. 

### Environment variables
I need to make sure my settings are correct for the location of the data when runing stuff locally. I've added this to my `.bashrc`

```bash
export LVRA_SETTINGS='/home/stevance/software/lvra/data/public_settings_local.yaml'
```