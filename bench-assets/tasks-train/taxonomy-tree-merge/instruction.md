I need to unify job/occupation classification taxonomies from four different job platforms (LinkedIn, Indeed, Monster, and Glassdoor). Each platform has its own way of organizing job roles into categories, and we want to create one unified category catalog that works for all of them so I can use a single classification system for downstream tasks like tracking hiring trends and comparing job market data across platforms!

The available data files are in /root/data/ as your input:
- linkedin_job_categories.csv
- indeed_job_categories.csv
- monster_job_categories.csv
- glassdoor_job_categories.csv

Each file has different formats but all contain hierarchical category paths in format like `"Technology > Software Development > Backend"` under the `category_path` column. Your job is to process these files and create a unified 4-level taxonomy.

 Some rules you should follow:
 1. the top level should have 8-15 broad categories, and each deeper level should have 3-15 subcategories per parent.
 2. you should give name to category based on the available category names, use " | " as separator between words (not more than 4 words), and one category needs to be representative enough (70%+) of its subcategories
 3. standardize category text as much as possible
 4. avoid name overlap between subcategory and its parent
 5. for sibling categories, they should be distinct from each other with < 30% word overlap
 6. try to balance the cluster sizes across different hierarchy levels to form a reasonable pyramid structure
 7. ensure categories from different data sources are relatively evenly distributed across the unified taxonomy

Output two CSV files to `/root/output/`:

1. `unified_taxonomy_full.csv`
   - source (linkedin/indeed/monster/glassdoor)
   - category_path
   - depth (1-4)
   - unified_level_1, unified_level_2, unified_level_3, unified_level_4

2. `unified_taxonomy_hierarchy.csv` (include all paths from low granularity to high in below format)
   - unified_level_1, unified_level_2, unified_level_3, unified_level_4
