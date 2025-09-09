echo "CLEARING INDEX"
flask clear_index all
echo "REINDEXING COHORTS"
flask indexer init
flask import entities Daisy project
flask import entities Daisy dataset
flask import entities Dats project
flask import entities Dats study
flask import entities Dats dataset
flask indexer extend project
flask indexer extend study
flask indexer extend dataset
echo "EXPORT ENTITIES"
flask export entities Rems dataset
echo "GENERATE SITEMAPS"
flask generate_sitemaps
