

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from .elasticsearch_backend import es_store, es_find_fbi_annotations, annotated_fbi_record
import fbi_core


@dataclass
class AppliesTo:
    """Defines the criteria for applying an annotation to a file."""
    path: Optional[str] = None
    under: Optional[str] = None
    ext: Optional[str] = None
    larger: Optional[int] = None
    smaller: Optional[int] = None
    before_regex_date: Optional[str] = None
    after_regex_date: Optional[str] = None

    def matches(self, context: 'AnnotationContext') -> bool:
        if self.path and self.path != context.path:
            return False
        if self.under and not context.path.startswith(self.under):
            return False
        if self.ext and not context.path.endswith(self.ext):
            return False
        if self.type and self.type != context.type:
            return False
        if self.larger is not None and context.size <= self.larger:
            return False
        if self.smaller is not None and context.size >= self.smaller:
            return False

        file_date = context._extract_date()
        if self.before_regex_date:
            target = datetime.fromisoformat(self.before_regex_date)
            if not file_date or file_date >= target:
                return False
        if self.after_regex_date:
            target = datetime.fromisoformat(self.after_regex_date)
            if not file_date or file_date <= target:
                return False

        return True


@dataclass
class FBIAnnotation:
    id: Optional[str] = None
    applies_to: AppliesTo
    annotation: Dict[str, Any]
    merge_strategy: str
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)


    def save(self) -> None:
        """Save the annotation to Elasticsearch."""
        data = {
            "applies_to": self.applies_to,
            "annotation": self.annotation,
            "merge_strategy": self.merge_strategy,
            "metadata": self.metadata
        }
        store(data)
        print("Annotation saved successfully.")

    def delete(self) -> None:
        """Delete the annotation from Elasticsearch."""
        # Assuming we have a method to delete by applies_to criteria
        store.delete_by_applies_to(self.applies_to)
        print("Annotation deleted successfully.")


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


find_fbi_annotations(applies_under="/data", applies_ext=".zip", annotation_keys=["storage_plan"])

# use fbi to make context
def find_annotations_from_fbi_path(path):
    """Find annotations for a given file path in the FBI."""

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

    # look up fbi recor
    record = fbi_core.get_record(path)
    # use the record as context for the annotation search
    annotations = es_find_fbi_annotations_records(
        path=record["path"],
        under=record.directory,
        name=record.name,
        size=record.size,
        item_type=record.item_type,
        last_modified=record.last_modified
    )
    #returnlist of annotations

def merge_annotations(annotations):
    """Merge annotations based on their merge strategy."""
    merged = {}
    annotations.sort()
    for annotation in annotations:
        merged.update(annotation)
    return merged

    
def annotated_fbi_record(path):
    """Get an annotated FBI record for a given path."""
    # Get the FBI record
    record = fbi_core.get_record(path)
    
    # Find annotations for the record
    annotations = es_find_fbi_annotations(record)
    
    # Merge annotations into the record
    merged_annotations = merge_annotations(annotations)
    
    # Add annotations to the record
    record.update(merged_annotations)
    
    return record


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