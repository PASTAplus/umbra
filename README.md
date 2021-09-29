# umbra
APIs for "shadow" metadata
## Creator Names APIs

### APIs used by the Data Portal:

 * __Get list of creator names__ <br>
    GET https://umbra-d.edirepository.org/creators/names <br>
    Returns a list of all normalized names: <br>
    [“Abbaszadegan, Morteza”,“Abbott, Benjamin”,“Abendroth, Diane”,“Aber, John”, etc. ] <br>
    Status 200

 * __Get variants of a creator name__ <br>
    For a name in the list returned by the names API, e.g., "McKnight, Diane M" <br>
    GET https://umbra-d.edirepository.org/creators/name_variants/McKnight, Diane M <br>
    Returns a list of variants found for that creator name: <br>
    [“McKnight, Diane”,“McKnight, Diane M”,“Mcknight, Diane”,“Mcnight, Diane”] <br>
    Status 200

    For a name NOT in the list returned by the names API, e.g., "Python, Monty" <br>
    GET https://umbra-d.edirepository.org/creators/name_variants/Python, Monty <br>
    Returns: <br>
    [Name “Python, Monty” not found <br>
    Status 400

### APIs used to keep the names database up-to-date:

 * __Update creator names__ <br>
    POST https://umbra-d.edirepository.org/creators/names <br>
    This is run as a cronjob on each umbra server. It gets the newly-added EML files from PASTA and processes them to find new creator names, if any. 

 * __Get possible duplicates__ <br>
    GET http://umbra-d.edirepository.org/creators/possible_dups

 * __Flush possible duplicates__ <br>
    POST http://umbra-d.edirepository.org/creators/possible_dups
    

### Manual steps involved in maintaining the creator names database:


### Manual steps involved in creating the creator names database:
The following steps apply to a newly-instantiated umbra server. I.e., they are the steps needed to set up umbra to start with.

 * __Create the database__ <br>
     Create a psql database called pasta with user pasta (with the usual password). <br>
     Edit config.py to contain the correct password. <br>
     In the data directory, run the following to initialize the database schema: <br>
     psql -d pasta -U pasta -h localhost < create_eml_schemas.sql
     
 * __Edit the configuration file__ <br>
     Besides the database password, the configuration file config.py needs to contain the base folder path. Typically, this will be '/home/pasta/umbra'.

 * __Get the initial set of EML files__ <br>
     A newly instantiated umbra server needs to acquire a complete set of EML files from PASTA. A standalone Python program __download_eml.py__ is provided for this purpose. It uses async i/o, but still takes several hours to complete. 

 * __Initialize the "raw" responsible parties database table__ <br>
    After the EML files have been downloaded via download_eml.py, they need to be parsed and their "responsible parties" entries saved in a database table. Accomplish this via the following API: <br>
    POST https://umbra-d.edirepository.org/creators/init_raw_db
    <br>
    
* The two steps above, getting the initial set of EML files and initializing the "raw" responsible parties database table, only need to be done once. Subsequently, new EML files will be downloaded and the database updated via the update creator names API described above.
