# MediaQuery Helper - Usage Examples

The `MediaQuery` class provides a fluent interface for building database queries.
Think of it like LINQ in C# or method chaining in MATLAB.

## Setup

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from home_media_ai.media_query import MediaQuery

# Create session
engine = create_engine(DATABASE_URI)
Session = sessionmaker(bind=engine)
session = Session()

# Create query helper
query = MediaQuery(session)
```

## Basic Examples

### Get all DNG files

```python
dng_files = query.dng().all()
```

### Get all Canon RAW files with 4+ stars from 2024

```python
results = query.canon().raw().rating_min(4).year(2024).all()
```

### Get 10 random 5-star images

```python
best_images = query.rating(5).random(10)
```

### Get images from specific location

```python
madison_area = query.gps_bbox(
    min_lat=43.0, max_lat=43.5,
    min_lon=-89.5, max_lon=-89.0
).all()
```

## Return Formats

### As Media Objects (default)

```python
results = query.rating(4).all()
for media in results:
    print(media.file_path)
    print(media.camera_make)
```

### As pandas DataFrame

```python
df = query.rating_min(3).has_gps().to_dataframe()
print(df.head())
```

### As list of file paths

```python
paths = query.jpeg().year(2024).to_paths()
```

### Just count

```python
count = query.canon().rating(5).count()
print(f"Found {count} 5-star Canon images")
```

## Chaining Filters

Filters can be chained in any order:

```python
# All equivalent
query.canon().year(2024).rating(5).dng()
query.year(2024).canon().dng().rating(5)
query.dng().rating(5).year(2024).canon()
```

## Complex Queries

### High-quality images from specific timeframe

```python
from datetime import datetime

results = query \
    .rating_min(4) \
    .has_gps() \
    .date_range(
        datetime(2024, 6, 1),
        datetime(2024, 8, 31)
    ) \
    .min_resolution(12.0) \
    .sort_by_rating() \
    .all()
```

### RAW files without ratings

```python
unrated_raw = query.raw().no_rating().originals_only().all()
```

### Large files from specific camera

```python
large_canon = query \
    .canon() \
    .camera_model('EOS R5') \
    .min_file_size(20.0) \
    .sort_by_file_size(ascending=False) \
    .limit(100) \
    .all()
```

## Sorting

```python
# Newest first
query.sort_by_date(ascending=False).limit(10).all()

# Highest rated first
query.sort_by_rating(ascending=False).all()

# Random order
query.sort_random().limit(5).all()
```

## Statistics

Get summary statistics without loading all data:

```python
stats = query.canon().year(2024).stats()
print(stats)
# {
#     'count': 523,
#     'total_size_mb': 12450.5,
#     'avg_file_size_mb': 23.8,
#     'avg_rating': 3.2,
#     'rated_count': 245,
#     'with_gps': 498,
#     ...
# }
```

## Reusing Queries

Reset and build new query:

```python
query = MediaQuery(session)

# First query
results1 = query.canon().year(2024).all()

# Reset and do different query
query.reset()
results2 = query.nikon().rating(5).all()
```

Or create new instance:

```python
canon_query = MediaQuery(session).canon()
nikon_query = MediaQuery(session).nikon()
```

## Working with Results

### Media Objects

```python
results = query.rating(5).limit(10).all()

for media in results:
    print(f"File: {media.file_path}")
    print(f"Rating: {media.rating}")
    print(f"Camera: {media.camera_make} {media.camera_model}")
    print(f"GPS: ({media.gps_latitude}, {media.gps_longitude})")
    print(f"Size: {media.width}x{media.height}")
    print()
```

### DataFrame

```python
df = query.rating_min(4).year(2024).to_dataframe()

# Now use pandas operations
print(df.describe())
print(df['camera_make'].value_counts())
print(df.groupby('rating')['file_size'].mean())

# Plot
import matplotlib.pyplot as plt
df.plot(x='created', y='file_size', kind='scatter')
plt.show()
```

## Common Use Cases

### Find unrated images for curation

```python
unrated = query.no_rating().year(2024).sort_by_date().all()
```

### Find best shots from vacation

```python
vacation_best = query \
    .date_range(datetime(2024, 7, 1), datetime(2024, 7, 15)) \
    .rating_min(4) \
    .has_gps() \
    .to_dataframe()
```

### Find large files to clean up

```python
large_files = query \
    .min_file_size(50.0) \
    .derivatives_only() \
    .sort_by_file_size(ascending=False) \
    .limit(100) \
    .all()
```

### Export list of 5-star images

```python
best_paths = query.rating(5).to_paths()
with open('best_images.txt', 'w') as f:
    f.write('\n'.join(best_paths))
```

### Compare cameras

```python
canon_stats = MediaQuery(session).canon().year(2024).stats()
nikon_stats = MediaQuery(session).nikon().year(2024).stats()

print(f"Canon: {canon_stats['count']} images, avg rating: {canon_stats['avg_rating']:.2f}")
print(f"Nikon: {nikon_stats['count']} images, avg rating: {nikon_stats['avg_rating']:.2f}")
```

## Integration with Notebooks

Perfect for interactive exploration:

```python
# Start broad
query = MediaQuery(session)
print(f"Total images: {query.count()}")

# Narrow down
query.year(2024)
print(f"From 2024: {query.count()}")

query.has_gps()
print(f"With GPS: {query.count()}")

query.rating_min(4)
print(f"4+ stars: {query.count()}")

# Get results
df = query.to_dataframe()
df.head()
```

## MATLAB Analogy

This is similar to building queries in MATLAB:

```matlab
% MATLAB style (pseudocode)
results = database.query() ...
    .where('camera_make', 'Canon') ...
    .where('rating', '>=', 4) ...
    .where('year', 2024) ...
    .execute();
```

```python
# Python equivalent
results = MediaQuery(session) \
    .canon() \
    .rating_min(4) \
    .year(2024) \
    .all()
```

## Performance Tips

1. **Use `.count()` instead of `len(.all())`** when you only need the count
2. **Limit results** when exploring: `.limit(100).all()`
3. **Use `.to_paths()`** if you only need file paths
4. **Filter before sorting** - database sorts are efficient
5. **Use `.stats()`** for aggregates instead of loading all data
