  CREATE SCHEMA eml_files AUTHORIZATION pasta;
  
  CREATE TYPE eml_files.rp_type AS ENUM (
    'creator', 
    'contact', 
    'associatedParty', 
    'metadataProvider', 
    'personnel');

  CREATE TABLE eml_files.responsible_parties_raw (
    pid VARCHAR(50) NOT NULL,                               
    rp_type eml_files.rp_type NOT NULL,
    givenname VARCHAR(100),
    surname VARCHAR(100),
    organization VARCHAR(1024),
    position VARCHAR(256),
    address VARCHAR(256),
    city VARCHAR(256),
    country VARCHAR(100),
    email VARCHAR(256),
    url VARCHAR(256),
    orcid VARCHAR(256),
    scope VARCHAR(100) NOT NULL,
    identifier INT8 NOT NULL
  );
  
CREATE TABLE eml_files.responsible_parties (
    serial_id SERIAL PRIMARY KEY,
    pid VARCHAR(40) NOT NULL,                               
    rp_type eml_files.rp_type NOT NULL,
    givenname VARCHAR(100),
    surname VARCHAR(100),
    organization VARCHAR(400),
    position VARCHAR(150),
    address VARCHAR(200),
    city VARCHAR(120),
    country VARCHAR(40),
    email VARCHAR(100),
    url VARCHAR(200),
    orcid VARCHAR(100),
    scope VARCHAR(15) NOT NULL,
    identifier INT8 NOT NULL,
    correction_codes VARCHAR(20),
    organization_keywords VARCHAR(100),
    skip BOOLEAN
  );

CREATE TABLE eml_files.orcid_stats (
    givenname VARCHAR(100),
    surname VARCHAR(100),
    searchname VARCHAR(100),
    num_candidates INT8,
    num_hits INT8,
    candidates VARCHAR(4096),
    hits VARCHAR(4096), 
    orcid VARCHAR(20)
);


