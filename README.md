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
    GET http://umbra-d.edirepository.org/creators/possible_dups <br>
    There's information on how to use this API below in the section on maintaining the creator names database.

 * __Flush possible duplicates__ <br>
    POST http://umbra-d.edirepository.org/creators/possible_dups <br>
    There's information on how to use this API below in the section on maintaining the creator names database.


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
    

### Manual steps involved in maintaining the creator names database:
The umbra software does its best to resolve and normalize creator names programmatically. To determine if several name variants (e.g., James T Kirk, James Kirk, Jim Kirk, J Kirk) actually refer to the same person, it looks at various forms of "evidence" (email address, organization name, etc.) in the EML files. In some cases, however, it is unable confidently to conclude that two variants are the same person, and manual intervention is needed. Either evidence is lacking, or a surname may be misspelled in a particular case, for example.

The API GET http://umbra-d.edirepository.org/creators/possible_dups returns a list of cases that should be looked at manually. They are cases where a given surname has multiple normalized givennames. The list starts with dups that are new, followed by a line that reads  "==================================================". For example, a call to this API returned (partial list):
```
[
    "Adams: Byron, Henry D, Jesse B, Leslie M, Mary Beth, Phyllis C",
    "Anderson: Christopher B, Clarissa, Cody A, Craig, Iris, James, Jim, John P, Kathryn, Lucy, Lyle, Mike D, Rebecca, Robert A, Suzanne Prestrud, Thomas, William",
    "Bailey: Amey, John, Rosemary, Scott W, Vanessa L",
    "Brown: Cindi, Cynthia S, Dana Rachel, James, Jeffrey, Joseph K, Kerry, Renee F",
    "Martin: Chris A, Jonathan E, Mac, Mary",
    "McDowell: Nate G, Nathan, William H",
    "Simmons: Breana, Joseph",
    "Smith: Alexander, C Scott, Colin A, Curt, David R, Dylan J, G Jason, Jane E, Jane G, Jason M, Jayme, John W, Jonathan W, Katherine, Kerry, Lesley, Lori, Matthew, Melinda D, Michael, Ned, Nicole J, Rachel, Raymond, Richard, Sarah J, Stacy A, Thomas C",
    "Zhou: Jiayu, Jizhong, Weiqi",
    "Zimmerman: Jess, Jess K, Richard C"
    "==================================================",
    "Adams: Byron, Henry D, Jesse B, Leslie M, Mary Beth, Phyllis C",
    "Adhikari: Ashish, Bishwo",
    "Alexander: Clark R, Heather D, Mara, Pezzuoli R",
    "Allen: Dennis, Jonathan, Scott Thomas",
    "Anderson: Christopher B, Clarissa, Cody A, Craig, Iris, James, Jim, John P, Kathryn, Lucy, Lyle, Mike D, Rebecca, Robert A, Suzanne Prestrud, Thomas, William",    
    etc.
]
```

Scanning down this list, we see several cases that look suspicious: <br>
    Anderson: James, Jim <br>
    Brown: Cynthia S, Cindi <br>
    McDowell: Nate G, Nathan <br>
    Smith: Jane E, Jane G <br>
    Zimmerman: Jess, Jess K <br>

We check these out by running psql queries on the server.

```
select surname, givenname, scope, address, organization, email, url, orcid, organization_keywords from eml_files.responsible_parties_test where rp_type='creator' and surname='Anderson' and givenname in ('James','Jim') order by scope; <br>
```
shows that there is no evidence connecting Jim and James Anderson, so we do nothing.

```
select surname, givenname, scope, address, organization, email, url, orcid, organization_keywords from eml_files.responsible_parties_test where rp_type='creator' and surname='Brown' and givenname like 'C%' order by scope; <br>
```
shows that Cindi and Cynthia S Brown are almost certainly different people, so again we do nothing.

The one case that needs fixing is Zimmerman: Jess, Jess K. <br>
The query <br>
```
select surname, givenname, scope, organization, email, organization_keywords from eml_files.responsible_parties where rp_type='creator' and surname='Zimmerman' and givenname like 'Jes%' order by scope;<br>
```
returns (partial results):<br>
```
  surname  | givenname |    scope     |                 organization                  |         email          | organization_keywords 
-----------+-----------+--------------+-----------------------------------------------+------------------------+-----------------------
 Zimmerman | Jess      | edi          | LUQ LTER                                      |                        | 
 Zimmerman | Jess      | knb-lter-luq | University of Puerto Rico, Rio Piedras Campus | jesskz@ites.upr.edu    |  UPuertoRico
 Zimmerman | Jess      | knb-lter-luq | University of Puerto Rico, Rio Piedras Campus | jesskz@ites.upr.edu    |  UPuertoRico
 Zimmerman | Jess      | knb-lter-luq |                                               | jzimmerman@lternet.edu |  UPuertoRico
 Zimmerman | Jess      | knb-lter-luq |                                               | jzimmerman@lternet.edu |  UPuertoRico
 Zimmerman | Jess      | knb-lter-luq | University of Puerto Rico, Rio Piedras Campus | jesskz@ites.upr.edu    |  UPuertoRico
 Zimmerman | Jess K    | knb-lter-luq | University of Puerto Rico - Rio Piedras       | jesskz@ites.upr.edu    |  UPuertoRico
 Zimmerman | Jess      | knb-lter-luq | University of Puerto Rico                     | jzimmerman@lternet.edu |  UPuertoRico
 Zimmerman | Jess K    | knb-lter-luq | University of Puerto Rico - Rio Piedras       | jesskz@ites.upr.edu    |  UPuertoRico
 Zimmerman | Jess      | knb-lter-luq | University of Puerto Rico, Rio Piedras Campus | jesskz@ites.upr.edu    |  UPuertoRico
```    

umbra will figure out that the Jess and Jess K Zimmerman in the knb-lter-luq scope are the same person, since they're both at the University of Puerto Rico.

The problem is the Jess Zimmerman in the edi scope. But note that here we do have LUQ LTER as the organization, so that seems to make it a safe bet that it's the same Jess Zimmerman as in knb-lter-luq. To tell umbra that they are the same person, we edit the data file __corrections_name_variants.xml__ and add these entries:
```
    <person>
        <variant>
            <surname>Zimmerman</surname>
            <givenname>Jess</givenname>
            <scope>edi</scope>
        </variant>
        <variant>
            <surname>Zimmerman</surname>
            <givenname>Jess</givenname>
            <scope>knb-lter-luq</scope>
        </variant>
        <variant>
            <surname>Zimmerman</surname>
            <givenname>Jess K</givenname>
            <scope>knb-lter-luq</scope>
        </variant>
    </person>
```
These changes should be made in Github and pulled down to the server.

Once we have resolved all of the suspicious cases, we need to tell umbra to flush the "new" possible dups so the next time we ask for possible dups we aren't given the same new cases to check out all over again. To flush, __POST http://umbra-d.edirepository.org/creators/possible_dups__.

Now, if we do a __GET http://umbra-d.edirepository.org/creators/possible_dups__, the returned list will look like:
```
[
    "==================================================",
    "Adams: Byron, Henry D, Jesse B, Leslie M, Mary Beth, Phyllis C",
    "Adhikari: Ashish, Bishwo",
    "Alexander: Clark R, Heather D, Mara, Pezzuoli R",
    "Allen: Dennis, Jonathan, Scott Thomas",
    "Anderson: Christopher B, Clarissa, Cody A, Craig, Iris, James, Jim, John P, Kathryn, Lucy, Lyle, Mike D, Rebecca, Robert A, Suzanne Prestrud, Thomas, William",    
    etc.
]
```
i.e., the list of new possible dups above the "==================================================" line is now empty.

As we update the creator names over the course of some days, new possible dups will show up, and we do the same process over again.

There are several other data files to be aware of.

__corrections_nicknames.xml__ lists nicknames that we want to recognize. E.g.,
```
    <nickname>
        <name1>jim</name1>
        <name2>james</name2>
    </nickname>
```

__corections_orcids.xml__ lists ORCIDs for creators that have incorrect ORCIDs in one or more EML files. E.g., 
```
    <correction>
        <surname>Stanley</surname>
        <givenname>Emily%</givenname>
        <orcid>0000-0003-4922-8121</orcid>
    </correction>
```

__corrections_overrides.xml__ lists cases where a name is misspelled and we want to correct the spelling, not just treat it as a variant. E.g., 
```
    <override>
        <original>
            <surname>Morse</surname>
            <givenname>Jennfier F</givenname>
        </original>
        <corrected>
            <surname>Morse</surname>
            <givenname>Jennifer F</givenname>
        </corrected>
        <scope>knb-lter-nwt</scope>
    </override>
```
Note that the name_variants API will still return the misspelled name as one of the variants so that searches will find datasets with the name misspelled.

__organizations.xml__ lists organization names and emails that correspond to a particular organization (usually a university). E.g., 
```
   <organization>
        <name>U%New Mexico</name>
        <name>U%NM</name>
        <name>UNM</name>
        <email>unm.edu</email>
        <keyword>UNM</keyword>
    </organization>
```
Any organization name, address, or email address that matches or contains one of the variants will mark a record in the database as being in the given organization (UNM, in this example). This helps umbra determine what organization a record is associated with, despite the many variations in the ways organization names, addresses, and email addresses are spelled.






    
