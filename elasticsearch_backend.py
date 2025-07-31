"""functions to store and retrieve data from an Elasticsearch index"""


from typing import Any, Dict, List, Optional

from ceda_es_client import CEDAElasticsearchClient
import yaml
import os
import datetime

#load api key  
api_key = yaml.load(open(os.environ["HOME"] + "/.fbi.yml"), Loader=yaml.Loader)["ES"]["api_key"]
ES = CEDAElasticsearchClient(api_key=api_key)


INDEXNAME = "fbi-annotations"


INDEX_SETTINGS ={
  "settings": {
      "index":{"number_of_shards" : "1", "number_of_replicas" : "1"},
    "analysis": {
      "analyzer": {"path_analyzer": {"tokenizer": "cedaa_tokenizer"}},
      "tokenizer": {"cedaa_tokenizer": {"type": "path_hierarchy"}}
    }
  },
  "mappings": {"properties": {
      "directory": {
        "type": "text", "fields": {
          "tree": {"type": "text", "analyzer": "path_analyzer"},
          "analyzed": {"type": "text"}
        }
      }
    }}
}


def create_index(es: CEDAElasticsearchClient) -> None:
    """Create an index in Elasticsearch if it does not already exist."""
    if not es.indices.exists(index=INDEXNAME):
        es.indices.create(index=INDEXNAME, body=INDEX_SETTINGS)
        print(f"Index '{INDEXNAME}' created.")
    else:
        print(f"Index '{INDEXNAME}' already exists.")

def store(data: Dict[str, Any]) -> None:
    """Store data in the Elasticsearch index."""
    try:
        ES.index(index=INDEXNAME, body=data)
        print(f"Data stored successfully in index '{INDEXNAME}'.")
    except Exception as e:
        print(f"Error storing data: {e}")   



def es_find_fbi_annotations(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find annotations for a given FBI record. 
    This function lookes for annotations that apply to the record's path, extension, size, and regex date.
    The base assumption is that annotations apply globally unless they specify a restriction on scope 
    in the applies_to field. Thus the pattern for this query is
      applies_to.<attibute1> matchs fbi record OR applies_to.<attibute1> does not exist AND 
      applies_to.<attibute2> matchs fbi record OR applies_to.<attibute2> does not exist AND
      ... and so on."""

    clauses = []
    now = datetime.datetime.now().isoformat()
    query = {"bool": {
                "must": clauses,
                "must_not": [{"range": {"metadata.expires": {"lte": "2025-03-07"}}}]
            }}
    
    # add exact path clause
    clauses.append({"bool": {"should": [{"term": {"applies_to.path": record["path"]}}],
                            "should_not": [{"exists": {"field": "applies_to.path"}}]}})

    # if the record has an extention then look for annotations with extention scope.
    if record.get("ext") is not None:
        clauses.append({"bool": {"should": [{"term": {"applies_to.ext": ".nc"}}],
                                "should_not": [{"exists": {"field": "applies_to.ext"}}]}})

    # if the record has a size then look for annotations with smaller and larger fields.
    if record.get("size") is not None:
        clauses.append({"bool": {"should": [{"range": {"applies_to.smaller": {"gte": record["size"]}}}],
                                 "should_not": [{"exists": {"field": "applies_to.smaller"}}]}})
        clauses.append({"bool": {"should": [{"range": {"applies_to.larger": {"lte": record["size"]}}}],
                                 "should_not": [{"exists": {"field": "applies_to.larger"}}]}})        

    # if the record has a regex date then look for annotations with regex fields.
    if record.get("regex_date") is not None:
        age = datetime.datetime.now() - datetime.datetime.fromisoformat(record["regex_date"])

        clauses.append({"bool": {"should": [{"range": {"applies_to.before_regex_date": {"gte": record["regex_date"]}}}],
                                  "should_not": [{"exists": {"field": "applies_to.before_regex_date"}}]}})
        clauses.append({"bool": {"should": [{"range": {"applies_to.after_regex_date": {"lte": record["regex_date"]}}}],
                                  "should_not": [{"exists": {"field": "applies_to.after_regex_date"}}]}})
        clauses.append({"bool": {"should": [{"range": {"applies_to.younger_regex_date": {"lte": age.days}}}],
                                  "should_not": [{"exists": {"field": "applies_to.younger_regex_date"}}]}})    
        clauses.append({"bool": {"should": [{"range": {"applies_to.older_regex_date": {"gte": age.days}}}],
                                  "should_not": [{"exists": {"field": "applies_to.older_regex_date"}}]}})        

    # add causes for applies.under
    parent_path = record["path"]
    should_under_terms = []
    clauses.append({"bool": {"should": should_under_terms,
                             "should_not": [{"exists": {"field": "applies.under"}}]}})
    while parent_path != "":
        should_under_terms.append({"term": {"applies_to.under": parent_path}})
        parent_path = os.path.dirname(parent_path)

    result = ES.search(index=INDEXNAME, query=query, size=1000)
    results = []
    for hit in result["hits"]["hits"]:
        hit["_source"]["_id"] = hit["_id"]
        results.append(hit["_source"])
        
    return results 

    
   