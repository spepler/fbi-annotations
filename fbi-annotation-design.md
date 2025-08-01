# 📄 FBI Annotation System – Design Document

**Author:** Sam and ChatGPT 
**Date:** 7 July 2025  
**Status:** Draft  
**Version:** 1.0  

---

## 1. 🎯 Purpose

This document outlines the design for a **File-Based Index (FBI) Annotation System**, which allows structured, declarative, and mergeable annotations of files or directories in the archive based on a flexible set of matching rules.

The primary use case is to support data curation processes and metadata enrichment across heterogeneous datasets.

---

## 2. 📦 Use Cases

- **Enriching file listings** with additional metadata for display in data.ceda.ac.uk.
- **Automated curation rules**: applying actionable information e.g. if data should be considered for tape only storage.
- **Annotation layering**: e.g., combining automated and human annotations.

### 2.1 Example use

```python 
from fbi_annotations import AnnotationContext, FBIAnnotation,

# Sample annotations
a = FBIAnnotation(
    applies_to={"ext": ".nc"},
    annotation={"format": "NetCDF-4"},
    merge_strategy="default",
    metadata={"created_by": "scanner"}
    )

b = FBIAnnotation(    
    applies_to={"path": "/data/cmip5"},
    annotation={"storage_plan": "tape only"},
    merge_strategy="override",
    metadata={"created_by": "SJP"}
    )

c = FBIAnnotation(
    applies_to={"under": "/data", "smaller": 1000},
    annotation={"note": "tiny file"},
    merge_strategy="addition"
    )

d = FBIAnnotation(
    applies_to={"under": "/data", "smaller": 1000000000},
    annotation={"note": "not huge"},
    merge_strategy="addition"
    )

e = FBIAnnotation(
    applies_to={"ext": ".txt"},
    annotation={"format": "Text"},
    merge_strategy="default",
    metadata={"created_by": "scanner"}
    )


# save to elasticsearch
a.save()
b.save()
...


# delete rules
annotations = find_fbi_annotations(applies_under="/data", applies_ext=".zip", annotation_keys=["storage_plan"])
for a in annotations:
     a.delete()

# use fbi to make context
find_fbi_annotations("/data/cmip5/file123.nc")
#
# path = /data/cmip5/file123.nc
# directory = /data/cmip5
# name = file123.nc
# size = 234
# item_type = file
# last_modified = 2024-03-20
#
# Result:
# - {"ext": ".nc"} -> {"format": "NetCDF-4"}
# - {"path": "/data/cmip5"} -> {"storage_plan": "tape only"}
# - {"under": "/data", "smaller": 1000} -> {"note": "tiny file"}
# - {"under": "/data", "smaller": 1000000000} -> {"note": "not huge"}

annotated_fbi_record("/data/cmip6/file123.nc")
# {'format': 'NetCDF-4', 'note': ['tiny file', 'not huge'], 'storage_plan': 'tape only',
# 'path': '/data/cmip5/file123.nc', 'directory': '/data/cmip5', 'name': 'file123.nc',
# 'size': 234, 'item_type': 'file', 'last_modified': '2024-03-20'}

find_annotations_from_fbi_summary("/data/xxxx")
#
# summary for /data/xxxx
# exts = .nc .txt .gif
# min size = 34040
# max size = 34983493248
# ...
#
# Result: 
# - {"ext": ".nc"} -> {"format": "NetCDF-4"}
# - {"under": "/data", "smaller": 1000000000} -> {"note": "not huge"}
# - {"ext": ".txt"} -> {"format": "Text"}
```


---

## 3. 📐 Data Model Overview

Each annotation block follows a consistent schema with four main components:

```json
{
  "applies_to": { ... },
  "metadata": { ... },
  "annotation": { ... },
  "merge_strategy": "default"
}
```

---

## 4. 📁 Field Definitions

### 4.1 `applies_to` (object, required)

Defines **which files**, directories or links the annotation applies to.

| Key                | Type    | Description |
|-------------------|----------|-------------|
| `under`           | string   | Path prefix (e.g. `/badc/cmip6/data`) |
| `path`            | string   | Exact match to a path |
| `ext`             | string   | File extension (e.g. `.nc`) |
| `item_type`       | string   | One of: `file`, `dir`, `link` |
| `larger`          | number   | File must be > N bytes |
| `smaller`         | number   | File must be < N bytes |
| `before_regex_date`   | string (date) | applies to paths with date-like substrings before this date |
| `after_regex_date`    | string (date) | applies to paths with date-like substrings after this date |
| `older_regex_date`    | number (days) | applies to paths with date-like substrings that are older than this in days |    
| `younger_regex_date`  | number (days) | applies to paths with date-like substrings that are younger than this in days |  
| `before_mod_date`     | string (date) | applies to paths with modification dates before this date |
| `after_mod_date`      | string (date) | applies to paths with modification dates after this date |
| `older_mod_date`      | number (days) | applies to paths with modification dates that are older than this in days |    
| `younger_mod_date`    | number (days) | applies to paths with modification dates that are younger than this in days |  
| `filename_regex`      | regex         | applies to files with name matching regex |  


> Combine multiple filters for precision. All conditions must match (logical AND). Missing fields 
> imply match all, for example, if there is no `ext` field then all extentions match.

---

### 4.2 `metadata` (object, optional)

Freeform metadata about the annotation itself — e.g.:

```json
{
  "created_by": "jbloggs",
  "created_at": "2025-07-01T12:00:00Z",
  "source": "manual_review",
  "expires": "2027-06-01"
}
```

This section is ignored for most processes with the exception of `expires` which should cause annotations to be 
ignored after that date.  

---

### 4.3 `annotation` (object, required)

The actual annotation content to apply. Keys are flexible and may vary by use case.

Examples:

```json
{
  "format": "NetCDF-3",
  "quality_flag": "needs_review"
}
```

```json
{
  "dataset_class": "observational",
  "priority": "low"
}
```

This data is applied to matching search contexts. A single context can 
result in many matching annotations which mmay be merged 
to a single result annotation.

---

### 4.4 `merge_strategy` (string, required)

Controls how annotations are merged when multiple annotations match the search context. 

| Strategy   | Description |
|------------|-------------|
| `default`  | Apply only if no annotation is present |
| `override` | Replace any existing annotations |
| `addition` | Shallow merge (non-conflicting keys only) |

> The order of appling the merge is `default`, `addition` then `override`.

> Merge of annotations with the same `merge_strategy` are done ordering `applies_to` feilds, 
> the most specific overriding least specific. 


---

## 5. 🧪 Examples

### Example 1: Flag all `.nc` files under a directory

```json
{
  "applies_to": {
    "under": "/data/cmip6/",
    "ext": ".nc"
  },
  "metadata": {
    "created_by": "script",
    "source": "format scan"
  },
  "annotation": {
    "format": "NetCDF-4"
  },
  "merge_strategy": "default"
}
```

---

### Example 2: Annotate a specific file path with high priority

```json
{
  "applies_to": {
    "path": "/data/cmip6/CMIP/HighResMIP/file123.nc"
  },
  "annotation": {
    "priority": "high",
    "note": "Important file for delivery"
  },
  "merge_strategy": "override"
}
```

---

### Example 3: Annotate all small `.txt` files

```json
{
  "applies_to": {
    "under": "/archive/notes/",
    "ext": ".txt",
    "smaller": 1000
  },
  "annotation": {
    "category": "log",
    "keep": false
  },
  "merge_strategy": "default"
}
```

---

### Example 4: Annotate based on date-like string in filename

```json
{
  "applies_to": {
    "under": "/datasets/",
    "ext": ".csv",
    "before_regex_date": "2021-01-01"
  },
  "annotation": {
    "status": "legacy"
  },
  "merge_strategy": "default"
}
```

---

## 6. 🧩 Schema

A simplified JSON Schema (type-relaxed for metadata and annotations):

```json
{
  "type": "object",
  "properties": {
    "applies_to": {
      "type": "object",
      "properties": {
        "under": { "type": "string" },
        "path": { "type": "string" },
        "ext": { "type": "string" },
        "type": { "type": "string", "enum": ["file", "dir"] },
        "larger": { "type": "number" },
        "smaller": { "type": "number" },
        "before_regex_date": { "type": "string", "format": "date" },
        "after_regex_date": { "type": "string", "format": "date" }
      },
      "additionalProperties": false
    },
    "metadata": { "type": "object" },
    "annotation": { "type": "object" },
    "merge_strategy": {
      "type": "string",
      "enum": ["default", "override", "addition"]
    }
  },
  "required": ["applies_to", "annotation", "merge_strategy"],
  "additionalProperties": false
}
```

---

## 7. 🛠️ Implementation Notes

- Annotations should be stored in as json in Elasticsearch in an `fbi-annotaions` index.
- Performance should scale so that its possible to:
  - find all annotations for a single directory within 1 second. 
  - Apply merged annotations to 100000 files in minutes.
- The system must be a python package with an FBIAnnotation object
- The package should validate objects before writing them to Elasticsearch


## 8 functions needed for use cases

### 8.1 Where does this annotation apply?

Find all files where a specified annotation applies. This is needed to check that the annotation is 
applying to the right parts of the archive. Say  you write an annotation which you hope will apply to 
a set of jpeg files under `/a/b/c`. Using this function we can see that its as well as all the data
files `/a/b/c/data/A.jpeg`, `/a/b/c/data/A.jpeg`, ..., its also catching `/a/b/c/metadata/layout.jpeg`. 

```python
def find_fbi_items_by_annotation(anno: FBIAnnotation) -> list[FBIRecords]:
    ...
```

### 8.2 Which annotations apply to this file?

Find all the annotations that apply to an indervidal file (could be a dir or symlink). This is needed to 
show a view of a file that includes as much rich information as possible. The infomation can be rendered for 
human inspection or an API. 

```python
def find_fbi_annotations(f: str | FBIRecord) -> list[FBIAnnotation]:
    ...
```

### 8.3 Mix the annotations together with the FBI record for a file. 

Given a path, find the FBI record, and look for annotations that apply. Use precidence rules to combine them into a 
single rich record with the most relivent information.

```python
def merge_annotations(annos: list[FBIAnnotation]) -> dict:
    ...

# conviniance function
def annotated_fbi_record(f: str | FBIRecord) -> dict:
    return merge_annotations(find_fbi_annotations(f))
```
### 8.4 Which annotations are relivent for this directory?

Find all the annotations that apply with this direcory . This is needed to 
show a view of a file that includes as much rich information as possible. The infomation can be rendered for 
human inspection or an API.


### 8.5 Find annotations 

Find all annotations from search 

```python
def find_fbi_annotations(with_annotation_key: str | None = None, under: str | None = None, ... ) -> list[FBIAnnotation]:
    ...
```


---


