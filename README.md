# umbra
APIs for "shadow" metadata
## Creators API

### APIs used by the Data Portal:

 * __Get list of creator names__
    GET https://umbra-d.edirepository.org/creators/names
    Returns a list of all normalized names:
    [“Abbaszadegan, Morteza”,“Abbott, Benjamin”,“Abendroth, Diane”,“Aber, John”, etc. ]
    Status 200

 * __Get variants of a creator name__
    For a name in the list returned by the names API, e.g., "McKnight, Diane M"
    GET https://umbra-d.edirepository.org/creators/name_variants/McKnight, Diane M
    Returns a list of variants found for that creator name:
    [“McKnight, Diane”,“McKnight, Diane M”,“Mcknight, Diane”,“Mcnight, Diane”]
    Status 200

    For a name NOT in the list returned by the names API, e.g., "Python, Monty"
    GET https://umbra-d.edirepository.org/creators/name_variants/Python, Monty
    Returns:
    [Name “Python, Monty” not found
    Status 400

### APIs used to keep the names database up-to-date:

 * __Update creator names__
    POST https://umbra-d.edirepository.org/creators/names
    This is run as a cronjob on each umbra server. It gets the newly-added EML files from PASTA and processes them to find new creator names, if any. 

 * __Get possible duplicates__
    GET http://umbra-d.edirepository.org/creators/possible_dups

 * __Flush possible duplicates__
    POST http://umbra-d.edirepository.org/creators/possible_dups
