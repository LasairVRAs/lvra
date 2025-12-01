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

- [x] **Why are there so many alert rows per `diaObjectId?`** Is it not one alert per lightcurve point maximum? What am I missing?

## Tracking down duplicate rows
For the `diObjectId` `169298433200357442`, I have 1198 rows duplicated and 209 not duplicated. 

I am tracking down in the alert json files located in `lasair@astrosurveydb1:~/data/vra_data/JSON` what might have happened. 

**Question 1: Is it because of the lasair test data (and a failure of my kafka queue)**

* **Number of alerts per file**. For a brief moment I thought that maybe my consumer was calling and empty stream and that I was filling up my data file with the 10 test alerts that lasair sends if there is nothing in the queue. However I can count how many alerts I have in each file `grep -c ^\s*\{ *.json` (since they are one big list of single layer dictionaires _NOTE THIS REGEX WILL BE WRONG IF THE KAFKA STREAM RETURNS NESTED DICTIONARIES_). **Most of the `.json` files have 4000 dictionaries/alerts** and none have only 10. 

**Conclusion 1: Duplicates are not caused by the test alerts**

* **Number of mentions per file** of this `diaObjectId`. By doing `grep -P -c 'diaObjectId":\s169298433200357442' *.json` (note the -P pearl flag needed so regex understand \s as space) I can see how many times this object is mentioned (I added ellipses when valies where repeated):

```bash
20251112_142338.json:0
20251114_125901.json:0
20251115_175901.json:1
20251117_015901.json:0
...
20251120_075901.json:0
20251123_105901.json:47
20251123_115901.json:66
20251123_125901.json:67
20251123_135901.json:26
20251123_145901.json:24
...
20251127_025902.json:24
20251127_035902.json:4
20251127_045901.json:4
...
```
There are **several days where we get 24** mentions of this objet every hour. 

**Question 2: Is it the same data at every repeat mention?**

* **`diff` on the files with the same number of mentions**: It turns out a lot of files have the same exact content! 

**Conclusion 2: Entire files are repeated!**

There is a major misunderstanding on my end with how the stream works: 
- [ ] **_Ask the Lasair team how to avoid repeats_**
- [ ] **Check if repeats happen as more alerts come in**
---
Another example of supernovae worht downloading for seed data: 
2025-11-28: 
Also this beauty: 
- https://lasair-lsst-dev.lsst.ac.uk/objects/169342391392665714/

_Note: as of 2025-12-01 we are still waiting on new alerts (for over 100 hours) so hard to check if duplication is occuring_

### What other fields in the alerts could we use for real/bogus filtering

From the Rubin [diaSource schema.](https://sdm-schemas.lsst.io/apdb.html#DiaSource)

#### Definitely
* `apFlux_flag` | `boolean`|  	General aperture flux algorithm failure flag; set if anything went wrong when measuring aperture fluxes. Another apFlux flag field should also be set to provide more information. 
* `apFlux_flag_apertureTruncated` | `boolean`  |	Aperture did not fit within measurement image. 
* `centroid_flag` | `boolean` | 	General centroid algorithm failure flag; set if anything went wrong when fitting the centroid. Another centroid flag field should also be set to provide more information. 
* `dipoleChi2` | 	`float` | 		Chi^2 statistic of the model fit.
* `dipoleFluxDiff` | 	`float` | 	(nJy) 	Maximum likelihood value for the difference of absolute fluxes of the two lobes for a dipole model.
* `dipoleMeanFlux` | 	`float` |  (nJy) 	Maximum likelihood value for the mean absolute flux of the two lobes for a dipole model. **Q: is that redundant with `dipoleFluxDiff`
* `extendedness` |	`float` | 		A measure of extendedness, computed by comparing an object's moment-based traced radius to the PSF moments. extendedness = 1 implies a high degree of confidence that the source is extended. extendedness = 0 implies a high degree of confidence that the source is point-like. 
* `forced_PsfFlux_flag` | 	`boolean` | 		Forced PSF photometry on science image failed. Another forced_PsfFlux flag field should also be set to provide more information. **Q: so can we not use that in isolation then?**
* `forced_PsfFlux_flag_edge` | `boolean` | 		Forced PSF flux on science image was too close to the edge of the image to use the full PSF model. 
* `glint_trail` | `boolean` | 	This flag is set if the source is part of a glint trail. 
* `isDipole` | `boolean` | 	Source well fit by a dipole. 
* `isNegative` | 	`boolean` | 		Source was detected as significantly negative. 
* `pixelFlags` | 	`boolean` | 		General pixel flags failure; set if anything went wrong when setting pixels flags from this footprint's mask. This implies that some pixelFlags for this source may be incorrectly set to False. 
* `pixelFlags_bad` | `boolean` | Bad pixel in the DiaSource footprint. 			
* `pixelFlags_cr` | `boolean` | Cosmic ray in the DiaSource footprint. 			
* `pixelFlags_crCenter` | `boolean` | Cosmic ray in the 3x3 region around the centroid. 			
* `pixelFlags_edge` | `boolean` | Some of the source footprint is outside usable exposure region (masked EDGE or centroid off image). 
* `pixelFlags_streakCenter` | 	`boolean` | Streak in the 3x3 region around the centroid. 
* `psfChi2` | `float` | Chi^2 statistic of the point source model fit. 
* `psfFlux_flag` | `boolean` | Failure to derive linear least-squares fit of psf model. Another psfFlux flag field should also be set to provide more information. 			
* `psfFlux_flag_edge` | `boolean` | Object was too close to the edge of the image to use the full PSF model. 			
* `psfFlux_flag_noGoodPixels` | `boolean` | Not enough non-rejected pixels in data to attempt the fit. 
* `snr` | `float` | The signal-to-noise ratio at which this source was detected in the difference image. 
* `trail_flag_edge` | `boolean` | This flag is set if a trailed source extends onto or past edge pixels. 

#### Maybe?
* Should I make a signal-to-noise feature from `apFlux` and `apFluxErr`?
* `bboxSize` |	`int` | 	pixel 	Size of the square bounding box that fully contains the detection footprint.
* `dipoleAngle` | `float` |	(degree) 	Maximum likelihood fit of the angle between the meridian through the centroid and the dipole direction (bearing, from negative to positive lobe).  **Q: I'M NOT SURE I UNDERSTAND WHAT THIS IMPLIES; THE DIRECTION OF THE DIPOLE ONLY OF THERE IS ONE OR ARE WE FITTING A DIPOLE REGARDLESS OF PSF QUALITY AND GETTING ANUMBER OUT?**
* `dipoleFitAttempted` | 	`boolean` | 		Attempted to fit a dipole model to this source. **Q: what does that imply? is that good news or bad news or no news?**
* `ixx` | `float` |	(nJy.arcsec**2) 	Adaptive second moment of the source intensity. **Q: what is this (and the other second moments of source uncdertainty)?**

Opened an [issue](https://github.com/lsst-uk/lasair-lsst/issues/400)