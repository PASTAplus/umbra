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
    pid VARCHAR NOT NULL,
    rp_type eml_files.rp_type NOT NULL,
    givenname VARCHAR,
    surname VARCHAR,
    organization VARCHAR,
    position VARCHAR,
    address VARCHAR,
    city VARCHAR,
    country VARCHAR,
    email VARCHAR,
    url VARCHAR,
    orcid VARCHAR,
    scope VARCHAR NOT NULL,
    identifier INT8 NOT NULL,
    correction_codes VARCHAR,
    organization_keywords VARCHAR,
    skip BOOLEAN
  );

