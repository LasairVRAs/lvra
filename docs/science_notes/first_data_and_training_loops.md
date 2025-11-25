# First data and training loops

## Gathering Seed Data
When speaking with Steve he mentioned that having a starting point for the training data 
is a good idea. This makes sense as there are a lot of alerts but few real extra gal transients
we are interested in. If we randomly sample a small subset of alerts it is likely we will have 
to wait a while until we encounter a real alert of interest.

Since I have the `oxqub-SN` filter and the dev Lasair website, I can run the filter and manually 
check a few sources to find a handful or real supernovae. 

###  A few technical details 
* The current `oxqub-SN` filter runs the following query

```sql
SELECT objects.diaObjectId,
       objects.ra,
       objects.decl,
       objects.nSources,
       objects.tns_name,
       objects.absMag,
       objects.absMagMJD,
       objects.ebv,
       objects.lastDiaSourceMjdTai,
       objects.firstDiaSourceMjdTai,
       sherlock_classifications.separationArcsec,
       sherlock_classifications.direct_distance,
       sherlock_classifications.distance,
       sherlock_classifications.z,
       sherlock_classifications.photoZ,
       sherlock_classifications.photoZErr,
       sherlock_classifications.physical_separation_kpc,
       sherlock_classifications.classification AS sherlock_classifications,
       objects.nDiaSources,
       objects.raErr,
       objects.decErr,
       objects.ra_dec_Cov
FROM objects,
     sherlock_classifications
WHERE objects.diaObjectId=sherlock_classifications.diaObjectId
  AND objects.nSources >= 4
  AND sherlock_classifications.classification IN ("SN",
                                                  "NT")
  AND objects.ebv < 1
  AND (objects.u_psfFlux >= 5000
       OR objects.g_psfFlux >= 5000
       OR objects.r_psfFlux >= 5000
       OR objects.i_psfFlux >= 5000
       OR objects.z_psfFlux >= 5000
       OR objects.y_psfFlux >= 5000)
```

* The current date is 25th November 2025
* Ranked the table by increasing ebv.  

### Seed Extra Galactic Transients
- Pretty sure that's real but the speed is CV-like for a NT location : https://lasair-lsst-dev.lsst.ac.uk/objects/169355602825839424/s
- Pretty sure that's real: https://lasair-lsst-dev.lsst.ac.uk/objects/169298433310982406/
- YEAH! https://lasair-lsst-dev.lsst.ac.uk/objects/169549116857647169/
- https://lasair-lsst-dev.lsst.ac.uk/objects/169298433200881680/
- https://lasair-lsst-dev.lsst.ac.uk/objects/169298433200357442/
- https://lasair-lsst-dev.lsst.ac.uk/objects/169575528459665431/
- https://lasair-lsst-dev.lsst.ac.uk/objects/169549124555243568/

### Example of a CV
- https://lasair-lsst-dev.lsst.ac.uk/objects/169342393025822797/


### Thoughts
As I'm doing eyeballing a few things come to mind. 
* First of all, the data I have in the filter is not going to be enough to do decent classification work: I need to get the forced photometry data. 
* Secondly, I can't see the forced phot on the lasair webpage: is it a question of latency? 
* Finally, I need to remember that we are currently doing the deep-driling fields. So the data I am gathering here is the **Wrong data to trian on for LSST**; but the logic will be the same so this is sort of rehearsals, building the pipes and practicing the workflow. Still worth doing. 

Also given the state of the data I need to create for myself a realistic first goal for the very first lasair VRA. That could be coarse helping with eyeballing, with the idea that I'll eyeball a lot by hand in the first few weeks anyway to get used to the data and build data sets? 

### To-Do:
- [x] Pick 20 random alerts from the sample I have gathered on the Oxford server
- [ ] Use the Lasair API to grab the whole data for these 20 alerts + the CV + the SNe above

---
### Grab alert stream data for 20 random objects plus pre-selected
I did this quickly in `ipython` directly on the server, here is the history:
```python
import pandas as pd
pd.read_json('./20251112_142338.json')
pd.read_json('./JSON/20251112_142338.json')
cd JSON
import os
os.listdir()
sorted(os.listdir())
json_files = sorted(os.listdir())
ls_df = []
for file in json_files:
    ls_df.append(pd.read_json(file))
pd.concat(ls_df)
data = pd.concat(ls_df)
data.diaObjectId == 169575528459665431
sum(data.diaObjectId == 169575528459665431)
selected_ids = [169575528459665431,169549124555243568,169298433200357442,169298433200881680,169549116857647169,169298433310982406,169342393025822797]
import numpy as np
mask_preselected = np.isin(data.diaObjectId, selected_ids)
data[mask_preselected]
data_preselected = data[mask_preselected]
data_leftover = data[~mask_preselected]
random_selected_id = np.random.choice(data_leftover.diaObjectId.unique(), 20, replace=False)
mask_random_selected = np.isin(data_leftover.diaObjectId, random_selected_id)
data_randomselected = data_leftover[mask_random_selected]
```
I created two files in `/storage1/scratch/vra_data/JSON/seed_data_set`:
* `preselected.csv` 
* `randomselected.csv`

I have left them separate because the preselected ids return loads of alerts data (of order 2k rows) which is more than I would expect. The random selected is around 770, still 40 rows per object roughly. More than expected. 


- [ ] **Why are there so many alert rows per `diaObjectId?`** Is it not one alert per lightcurve point maximum? What am I missing?