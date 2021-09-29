# umbra
APIs for "shadow" metadata
## Creators API

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
