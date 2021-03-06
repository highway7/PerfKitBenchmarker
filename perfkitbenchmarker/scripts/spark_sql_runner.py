# Lint as: python2, python3
"""Runs a Spark SQL query with preloaded temp views.

Views can be BigQuery tables or HCFS directories containing Parquet.
This is useful for Storage formats not expressible as External Hive Tables.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import logging

from pyspark.sql import SparkSession


def parse_args():
  """Parse argv."""

  def comma_separated_list(string):
    return string.split(',')

  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
      'sql_script', help='The local path to the SQL file to run')
  data_sources = parser.add_mutually_exclusive_group()
  data_sources.add_argument(
      '--bigquery-tables',
      metavar='TABLES',
      type=comma_separated_list,
      default=[],
      help='Comma separated list of fully qualified BigQuery '
      'tables. Views will share the name of the tables.')
  parser.add_argument(
      '--bigquery-record-format',
      metavar='FORMAT',
      help='Data Format for reading from BigQuery Storage')
  data_sources.add_argument(
      '--hcfs-dirs',
      metavar='DIRS',
      type=comma_separated_list,
      default=[],
      help='Comma separated list of HCFS directories containing parquet '
           'tables. Views will be named the basename of the directories.')
  return parser.parse_args()


def register_views(
    spark, bigquery_tables, hcfs_dirs, bigquery_record_format=None):
  """Pre-register BigQuery tables and Parquet directories as temporary views."""
  temp_dfs = {}
  for table in bigquery_tables:
    name = table.split('.')[-1]
    logging.info('Loading %s', table)
    reader = spark.read.format('bigquery').option('table', table)
    if bigquery_record_format:
      reader.option('readDataFormat', bigquery_record_format)
    temp_dfs[name] = reader.load()
  for hcfs_dir in hcfs_dirs:
    name = hcfs_dir.split('/')[-1]
    logging.info('Loading %s', hcfs_dir)
    temp_dfs[name] = spark.read.format('parquet').load(hcfs_dir)
  for name, df in temp_dfs.items():
    df.createTempView(name)


def main(args):
  spark = (SparkSession.builder.appName('Spark SQL Query').getOrCreate())
  register_views(
      spark, args.bigquery_tables, args.hcfs_dirs, args.bigquery_record_format)

  logging.info('Running %s', args.sql_script)
  with open(args.sql_script) as f:
    sql = f.read()

  # spark-sql does not limit it's output. Replicate that here by setting limit
  # to max Java Integer. Hopefully you limited the output in SQL or you are
  # going to have a bad time.
  # pylint: disable=protected-access
  spark.sql(sql).show(spark._jvm.java.lang.Integer.MAX_VALUE)
  # pylint: enable=protected-access


if __name__ == '__main__':
  main(parse_args())
